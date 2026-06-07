import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyGraphCandidateInPlace, installPreviewForegroundOverlay, installQueueGuard as installQueueGuardAdapter } from "./comfy_adapter.js";
import {
  createAgentEditState,
  RENDER_SECTIONS,
  normalizeObligationDirtySections,
  transition,
} from "./agent_edit_lifecycle.js";
import {
  normalizeAgentEditResponse,
  readLatestCandidate,
  readRebaselineRecovery,
  extractRebaselineRecovery,
} from "./agent_edit_response_contract.js";

export { RENDER_SECTIONS };

// ── VibeComfy Contract (S2 — Durable Frontend Panel) ─────────────────────
// This file captures the frontend↔backend contract before feature work.
// Backend contract authority: vibecomfy/comfy_nodes/agent_contracts.py.

// ── Panel States ──────────────────────────────────────────────────────────
// The panel lifecycle during an agent-edit turn:
//   IDLE            — shell open, ready for prompt entry
//   SUBMITTING      — POST /vibecomfy/agent-edit in-flight
//   AWAITING_REVIEW — candidate received; Apply / Reject available
//   APPLYING        — local proof-only in-place graph apply in progress
//   ERROR           — request failed; failure region becomes primary

// ── Turn Metadata ─────────────────────────────────────────────────────────
// Each agent-edit interaction is a "turn" within a "session".
// Backend allocates these; frontend receives them in responses:
//   session_id (str)      — stable id for the editor session
//   turn_id (str)         — "0000", "0001", … per session; allocated by backend
//   baseline_turn_id      — last accepted turn; returned by backend, NEVER sent
//                            by frontend as a submit input
//   idempotency_key (str) — optional client-generated dedup key
//   client_graph_hash     — SHA-256 of serialized graph at submit time (opt)
//   client_structural_graph_hash — SHA-256 of structural graph projection (opt)

// ── Submit Fields (POST /vibecomfy/agent-edit) ────────────────────────────
//   graph   (object, required) — ComfyUI UI JSON (app.canvas.graph.serialize())
//   task    (string, required) — natural-language edit instruction
//   route   (string, optional) — "deepseek" (default when absent)
//   model   (string, optional) — model id for the provider
//   session_id        (string, optional) — reuse existing session
//   idempotency_key   (string, optional) — client dedup key
//   client_graph_hash (string, optional) — SHA-256 of `graph` for diagnostics
//   client_structural_graph_hash (string, optional) — structural graph hash
//   client_live_canvas_token (string, optional) — live canvas lock token

// ── Accept Fields (POST /vibecomfy/agent-edit/accept) ─────────────────────
//   session_id        (string, required)
//   turn_id           (string, required)
//   client_graph_hash (string, optional) — hash of current canvas
//   client_live_canvas_token (string, optional) — current live canvas lock token
//   submit_graph_hash (string, optional) — v2 server-side submit hash echo
//   candidate_graph_hash (string, optional) — v2 accepted candidate hash
//   idempotency_key   (string, optional)

// ── Reject Fields (POST /vibecomfy/agent-edit/reject) ─────────────────────
//   session_id        (string, required)
//   turn_id           (string, required)
//   client_graph_hash (string, optional)
//   idempotency_key   (string, optional)

// ── Success Envelope (200) ─────────────────────────────────────────────────
// {
//   ok: true,
//   session_id, turn_id, baseline_turn_id,
//   canvas_apply_allowed, apply_allowed, queue_allowed,
//   gates: { python_load_ok, ir_validate_ok, ui_emit_ok, … },
//   message: "…",
//   graph: { … ComfyUI UI JSON … },
//   report: { change: { preserved, edited, removed_named, … },
//             recovery: […], felt: … },
//   artifacts: { … },
//   audit_ref: { … },
//   version: 1
// }

// ── Failure Envelope (4xx/5xx) ────────────────────────────────────────────
// {
//   ok: false,
//   kind: FailureKind — see agent_contracts.py FailureKind enum:
//     SyntaxError, ASTScanFailure, OversizedPayload, MalformedModelJSON,
//     MissingRequiredField, ProviderError, AuthError, TimeoutError,
//     ValidationError, UnsatisfiedInputError, RefusedEmit,
//     EditorAheadConflict, StaleStateMismatch, UnsupportedNonDAG,
//     SchemaLessQueueBlocker, LowConfidenceQueueBlocker,
//     EditorOnlyNodeQueueBlocker, AuditWriteWarning, AuditWriteFailure
//   stage: str          — pipeline stage that failed
//   retryable: bool,
//   next_action: str,
//   graph_unchanged: bool,
//   user_facing_message: str,
//   agent_failure_context: { explanation, … },
//   session_id, turn_id, baseline_turn_id,
//   canvas_apply_allowed: bool,
//   queue_allowed: bool,
//   audit_ref: { … } | null,
//   audit_error: str | null
// }
//
// Frontend failure handling: the JS currently maps network errors to
// { kind: "NetworkError" } and serialization errors to
// { kind: "SerializeError" }. Backend failures carry a `kind` field
// matching FailureKind.

const SUPPORTED_FRONTEND = "1.39.x";
const PANEL_STATE = Object.freeze({
  IDLE: "IDLE",
  SUBMITTING: "SUBMITTING",
  AWAITING_REVIEW: "AWAITING_REVIEW",
  APPLYING: "APPLYING",
  // CLARIFY — the agent asked a question instead of producing a candidate.
  // There is NO candidate to review (the graph is byte-identical), so we never
  // enter AWAITING_REVIEW for these turns; the prompt stays open for the answer.
  CLARIFY: "CLARIFY",
  ERROR: "ERROR",
});

const APPLY_ELIGIBILITY_REASON = Object.freeze({
  APPLYABLE: "applyable",
  NO_CANDIDATE: "no_candidate",
  MISSING_CONTRACT: "missing_contract",
  NOT_LATEST: "not_latest",
  SUPERSEDED: "superseded",
  SERVER_BLOCKED: "server_blocked",
  STALE_CANVAS: "stale_canvas",
  QUEUE_BLOCKED_WARNING: "queue_blocked_warning",
});

const ALL_AGENT_PANEL_RENDER_SECTIONS = Object.freeze(Object.values(RENDER_SECTIONS));
const SETTINGS_STATUS_RENDER_SECTIONS = Object.freeze([
  RENDER_SECTIONS.THREAD,
  RENDER_SECTIONS.SETTINGS,
  RENDER_SECTIONS.COMPOSER,
  RENDER_SECTIONS.NOTICE,
]);
const AGENT_STATUS_RETRY_DELAYS_MS = Object.freeze([250, 1000, 3000]);
const AGENT_PANEL_RENDER_TIMEOUT_MS = 100;
const AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT = 20;
const AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT = 3;
const AGENT_SIDEBAR_TAB_ID = "vibecomfy.agent-edit";
const AGENT_PANEL_SINGLETON_KEY = "__vibecomfyAgentPanelSingleton";
const AGENT_PANEL_MOUNT_MODE = Object.freeze({
  LAUNCHER: "launcher",
  SIDEBAR: "sidebar",
});

const PANEL_IDS = Object.freeze({
  root: "vibecomfy-agent-panel-root",
  shell: "vibecomfy-agent-panel-shell",
  status: "vibecomfy-agent-panel-status",
  composerNotice: "vibecomfy-agent-panel-composer-notice",
  prompt: "vibecomfy-agent-panel-prompt",
  route: "vibecomfy-agent-panel-route",
  model: "vibecomfy-agent-panel-model",
  apiKey: "vibecomfy-agent-panel-api-key",
  settingsStatus: "vibecomfy-agent-panel-settings-status",
  settingsGuidance: "vibecomfy-agent-panel-settings-guidance",
  settingsSave: "vibecomfy-agent-panel-settings-save",
  settingsTest: "vibecomfy-agent-panel-settings-test",
  submit: "vibecomfy-agent-panel-submit",
  apply: "vibecomfy-agent-panel-apply",
  reject: "vibecomfy-agent-panel-reject",
  undo: "vibecomfy-agent-panel-undo",
  close: "vibecomfy-agent-panel-close",
  threadRegion: "vibecomfy-agent-panel-region-thread",
  promptRegion: "vibecomfy-agent-panel-region-prompt",
  settingsRegion: "vibecomfy-agent-panel-region-settings",
  chatRegion: "vibecomfy-agent-panel-region-chat",
  historyRegion: "vibecomfy-agent-panel-region-history",
  candidateRegion: "vibecomfy-agent-panel-region-candidate",
  failureRegion: "vibecomfy-agent-panel-region-failure",
  queueRegion: "vibecomfy-agent-panel-region-queue",
  auditRegion: "vibecomfy-agent-panel-region-audit",
  debugRegion: "vibecomfy-agent-panel-region-debug",
  developerRegion: "vibecomfy-agent-panel-region-developer",
  previewToggle: "vibecomfy-agent-preview-toggle",
});

const ROUTE_ALIASES = Object.freeze({
  auto: "auto",
  arnold: "auto",
  deepseek: "deepseek",
  anthropic: "anthropic",
  claude: "anthropic",
  "openai-codex": "openai-codex",
  codex: "openai-codex",
});

const ROUTE_LABELS = Object.freeze({
  auto: "auto",
  deepseek: "deepseek",
  anthropic: "anthropic",
  "openai-codex": "openai-codex",
});

const ROUTE_STATUS_KIND = Object.freeze({
  LOADING: "loading_status",
  READY: "ready",
  MISSING_OPTIONS: "missing_route_options",
  MALFORMED: "malformed_status",
  UNAVAILABLE: "status_unavailable",
});

const INTENT_NODE_CLASS_TYPES = new Set(["vibecomfy.code", "vibecomfy.loop"]);
const INTENT_KIND_BY_CLASS_TYPE = Object.freeze({
  "vibecomfy.code": "code",
  "vibecomfy.loop": "loop",
});
const INTENT_PREVIEW_MAX = 120;
const INTENT_STYLE_BY_KIND = Object.freeze({
  code: {
    color: "#2d2643",
    bgcolor: "#171229",
    boxcolor: "#e39cff",
  },
  loop: {
    color: "#17363b",
    bgcolor: "#10252a",
    boxcolor: "#6ee7f2",
  },
  degraded: {
    color: "#3a2a1f",
    bgcolor: "#231811",
    boxcolor: "#ffb86c",
  },
});

const LOWERED_DIFF_COLOR = "#02d4b3";
const LOWERED_BADGE = "lowered";

// ── localStorage helpers (safe wrappers — tolerate missing/throwing storage) ─
const LS_ACTIVE_SESSION_KEY = "vibecomfy_active_session_id";

function _lsGet(key) {
  try {
    if (typeof localStorage === "undefined" || localStorage === null) {
      return null;
    }
    return localStorage.getItem(key);
  } catch (_e) {
    return null;
  }
}

function _lsSet(key, value) {
  try {
    if (typeof localStorage === "undefined" || localStorage === null) {
      return;
    }
    localStorage.setItem(key, value);
  } catch (_e) {
    // Best-effort: silently swallow set errors (private browsing, quota, etc.)
  }
}

function _lsRemove(key) {
  try {
    if (typeof localStorage === "undefined" || localStorage === null) {
      return;
    }
    localStorage.removeItem(key);
  } catch (_e) {
    // Best-effort.
  }
}

// ── Shared VibeComfy palette ────────────────────────────────────────────────
// Union of both feature palettes kept in ONE block: the preview-overlay diff
// keys (added/edited/removed/pending) and the turn-progress status-feed keys
// (active/success/warning/error/muted + bg* tints). Each feature reads its own
// keys; neither is broken by the merge.
const VC_COLORS = Object.freeze({
  // preview-overlay node/wire diff
  added: "#4caf50",
  edited: "#ffc107",
  removed: "#f44336",
  pending: "#7db6ff",
  // turn-progress status feed
  active: "#3d8bfd",
  success: "#02d4b3",
  warning: "#ffb86c",
  error: "#ff6c6c",
  muted: "#8d93a1",
  bgActive: "#1a2436",
  bgSuccess: "#0f2a26",
  bgWarning: "#2a1f14",
  bgError: "#2a1616",
});

// ── Alpha helper ────────────────────────────────────────────────────────────
function hexToRgba(hex, alpha) {
  let h = String(hex || "").replace(/^#/, "").trim();
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  }
  if (h.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(h)) {
    return `rgba(0,0,0,${typeof alpha === "number" ? alpha : 1})`;
  }
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${typeof alpha === "number" ? alpha : 1})`;
}
let agentPanel = null;
let agentSidebarTabRegistered = false;
let agentTurnEventListener = null;
let agentTurnEventListenerRegistered = false;
let changedNodeFeedbackTimer = null;
let changedNodeFeedbackVisuals = [];
let queueGuardHook = null;
let queueGuardContext = null;
let queueGuardFallbackWarning = null;
let queueGuardFallbackWarned = false;
let queueGuardBlockNotice = null;
let queueGuardBlockedTurnKeys = new Set();
let _previewForegroundInstallReport = null;
let _adapterCapabilities = null;
let _progressPulseInjected = false;
let _scheduledAgentPanelRender = null;
let _scheduledAgentPanelRenderQueued = false;
let _agentPanelFlushCount = 0;
let _lastAgentPanelFlushReason = "";
let _agentPanelCreationCounter = 0;
let _lastThreadRender = null;
let _lastNoticeRender = null;
let _statusCommitAt = null;
let _rehydrateCommitAt = null;
let _marksAfterCommit = 0;
let _overlayDrawModelCache = null;

function agentPanelSingletonHost() {
  return typeof window !== "undefined" ? window : null;
}

function agentPanelSingletonRecord(create = false) {
  const host = agentPanelSingletonHost();
  if (!host) {
    return null;
  }
  const current = host[AGENT_PANEL_SINGLETON_KEY];
  if (current && typeof current === "object") {
    return current;
  }
  if (!create) {
    return null;
  }
  const record = { panel: null, panelsCreated: 0 };
  host[AGENT_PANEL_SINGLETON_KEY] = record;
  return record;
}

function currentAgentPanel() {
  const sharedPanel = agentPanelSingletonRecord(false)?.panel || null;
  if (sharedPanel) {
    agentPanel = sharedPanel;
    return sharedPanel;
  }
  return agentPanel;
}

function setCurrentAgentPanel(panel) {
  agentPanel = panel || null;
  const record = agentPanelSingletonRecord(true);
  if (record) {
    record.panel = agentPanel;
  }
  return agentPanel;
}

function panelsCreatedCount() {
  const sharedCount = agentPanelSingletonRecord(false)?.panelsCreated;
  return Number.isFinite(sharedCount) ? sharedCount : _agentPanelCreationCounter;
}

function nextAgentPanelId() {
  const record = agentPanelSingletonRecord(true);
  if (record) {
    const nextCount = Number.isFinite(record.panelsCreated) ? record.panelsCreated + 1 : 1;
    record.panelsCreated = nextCount;
    _agentPanelCreationCounter = nextCount;
    return `${Date.now()}-${nextCount}`;
  }
  _agentPanelCreationCounter += 1;
  return `${Date.now()}-${_agentPanelCreationCounter}`;
}

function isIntentClassType(classType) {
  return INTENT_NODE_CLASS_TYPES.has(String(classType || "").trim());
}

function getIntentClassType(node, fallback = null) {
  const classType = String(
    node?.type
      || node?.comfyClass
      || node?.properties?.["Node name for S&R"]
      || fallback
      || "",
  ).trim();
  return isIntentClassType(classType) ? classType : "";
}

function truncateIntentPreview(value) {
  const text = String(value || "").trim().replace(/\s+/g, " ");
  if (!text) {
    return "";
  }
  return text.length > INTENT_PREVIEW_MAX
    ? `${text.slice(0, INTENT_PREVIEW_MAX - 1)}…`
    : text;
}

function normalizeIntentTypedIo(io, key) {
  const entries = io?.[key];
  if (!Array.isArray(entries)) {
    return [];
  }
  return entries
    .map((entry) => {
      if (!Array.isArray(entry) || entry.length < 2) {
        return null;
      }
      const [name, type] = entry;
      if (!name || !type) {
        return null;
      }
      return { name: String(name), type: String(type) };
    })
    .filter(Boolean);
}

function readIntentMetadata(node, fallbackClassType = null) {
  const properties = node?.properties && typeof node.properties === "object" ? node.properties : {};
  const classType = getIntentClassType(node, fallbackClassType);
  const payload = properties?.vibecomfy && typeof properties.vibecomfy === "object"
    ? properties.vibecomfy
    : null;
  const typedInputs = normalizeIntentTypedIo(payload?.io, "inputs");
  const typedOutputs = normalizeIntentTypedIo(payload?.io, "outputs");
  const kind = typeof payload?.kind === "string" && payload.kind
    ? payload.kind
    : INTENT_KIND_BY_CLASS_TYPE[classType] || "intent";
  const sourcePreview = truncateIntentPreview(payload?.intent?.source);
  const specPreview = truncateIntentPreview(payload?.intent?.spec);
  const valid = Boolean(
    payload
      && typeof payload === "object"
      && payload.intent
      && typeof payload.intent === "object",
  );
  return {
    classType,
    kind,
    valid,
    badgeStatus: valid ? "editor-only" : "metadata missing",
    typedInputs,
    typedOutputs,
    sourcePreview,
    specPreview,
  };
}

function buildIntentBadge(meta) {
  return `${meta.kind} · ${meta.badgeStatus}`;
}

function styleForIntentMeta(meta) {
  if (!meta.valid) {
    return INTENT_STYLE_BY_KIND.degraded;
  }
  return INTENT_STYLE_BY_KIND[meta.kind] || INTENT_STYLE_BY_KIND.degraded;
}

function applyTypedSocketLabels(slots, typedEntries) {
  if (!Array.isArray(slots) || !Array.isArray(typedEntries) || !typedEntries.length) {
    return;
  }
  const count = Math.min(slots.length, typedEntries.length);
  for (let index = 0; index < count; index += 1) {
    const slot = slots[index];
    const typed = typedEntries[index];
    if (!slot || !typed) {
      continue;
    }
    const label = `${typed.name}: ${typed.type}`;
    slot.name = label;
    if ("label" in slot || typeof slot === "object") {
      slot.label = label;
    }
  }
}

function decorateIntentNode(node, fallbackClassType = null) {
  const classType = getIntentClassType(node, fallbackClassType);
  if (!classType) {
    return false;
  }
  const meta = readIntentMetadata(node, classType);
  const style = styleForIntentMeta(meta);
  node.properties = node?.properties && typeof node.properties === "object" ? node.properties : {};
  node.color = style.color;
  node.bgcolor = style.bgcolor;
  node.boxcolor = style.boxcolor;
  node.properties.vibecomfy_intent_badge = buildIntentBadge(meta);
  node.properties["VibeComfy Intent Kind"] = meta.kind;
  node.properties["VibeComfy Intent Badge"] = node.properties.vibecomfy_intent_badge;
  if (meta.sourcePreview) {
    node.properties["VibeComfy Intent Source"] = meta.sourcePreview;
  }
  if (meta.specPreview) {
    node.properties["VibeComfy Intent Spec"] = meta.specPreview;
  }
  applyTypedSocketLabels(node.inputs, meta.typedInputs);
  applyTypedSocketLabels(node.outputs, meta.typedOutputs);
  node.__vibecomfyIntentMeta = meta;
  return true;
}

function drawIntentBadge(ctx, node) {
  if (!ctx || typeof ctx.fillText !== "function") {
    return;
  }
  const meta = node?.__vibecomfyIntentMeta || readIntentMetadata(node);
  if (!meta.classType) {
    return;
  }
  const badge = buildIntentBadge(meta);
  const width = readNodeSize(node, 180, 100).w;
  const style = styleForIntentMeta(meta);
  if (typeof ctx.save === "function") {
    ctx.save();
  }
  try {
    ctx.fillStyle = style.boxcolor;
    if (typeof ctx.fillRect === "function") {
      ctx.fillRect(10, 6, Math.max(112, Math.min(width - 20, badge.length * 7.25)), 18);
    }
    ctx.fillStyle = "#111418";
    ctx.font = "bold 11px monospace";
    ctx.fillText(badge, 16, 19);
  } finally {
    if (typeof ctx.restore === "function") {
      ctx.restore();
    }
  }
}

function patchIntentNodePrototype(nodeType, nodeData) {
  const proto = nodeType?.prototype;
  const classType = String(nodeData?.name || nodeData?.type || "").trim();
  if (!proto || !isIntentClassType(classType) || proto.__vibecomfyIntentPatched === classType) {
    return;
  }
  proto.__vibecomfyIntentPatched = classType;

  const originalCreated = proto.onNodeCreated;
  proto.onNodeCreated = function patchedIntentNodeCreated(...args) {
    const result = typeof originalCreated === "function" ? originalCreated.apply(this, args) : undefined;
    this.type = this.type || classType;
    decorateIntentNode(this, classType);
    return result;
  };

  const originalConfigure = proto.onConfigure;
  proto.onConfigure = function patchedIntentNodeConfigure(...args) {
    const result = typeof originalConfigure === "function" ? originalConfigure.apply(this, args) : undefined;
    this.type = this.type || classType;
    decorateIntentNode(this, classType);
    return result;
  };

  const originalDrawForeground = proto.onDrawForeground;
  proto.onDrawForeground = function patchedIntentNodeDrawForeground(ctx, ...args) {
    const result = typeof originalDrawForeground === "function"
      ? originalDrawForeground.call(this, ctx, ...args)
      : undefined;
    this.type = this.type || classType;
    decorateIntentNode(this, classType);
    drawIntentBadge(ctx, this);
    return result;
  };
}

function decorateIntentGraphPayload(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  for (const node of nodes) {
    decorateIntentNode(node);
  }
}

function decorateLiveIntentNodes() {
  const graph = getLiveGraph();
  for (const node of getLiveGraphNodes(graph)) {
    decorateIntentNode(node);
  }
}

function applyGraphInPlaceWithIntentDecoration(candidate) {
  try {
    applyGraphCandidateInPlace(app, candidate, {
      beforeConfigure(nextCandidate) {
        decorateIntentGraphPayload(nextCandidate);
      },
      afterConfigure() {
        decorateLiveIntentNodes();
      },
    });
  } catch (e) {
    if (e?.code !== "GRAPH_APPLY_UNAVAILABLE") {
      throw e;
    }
    throw agentPanelFailure("CanvasApplyError", "The live LiteGraph instance does not support in-place graph application.", {
      retryable: true,
      graph_unchanged: true,
      next_action: "Retry after the ComfyUI frontend finishes loading, or use the legacy round-trip command.",
    });
  }
}

function installIntentNodeFallback() {
  if (app.__vibecomfyIntentFallbackInstalled) {
    return;
  }
  const originalLoadGraphData = app?.loadGraphData;
  if (typeof originalLoadGraphData !== "function") {
    return;
  }
  app.loadGraphData = function vibecomfyIntentLoadGraphData(nextGraph, ...args) {
    decorateIntentGraphPayload(nextGraph);
    const result = originalLoadGraphData.call(this, nextGraph, ...args);
    decorateLiveIntentNodes();
    return result;
  };
  app.__vibecomfyIntentFallbackInstalled = true;
}

function installAgentPreviewOverlay() {
  if (app?.__vibecomfyAgentPreviewOverlayInstalled && _previewForegroundInstallReport) {
    return;
  }
  // Draw the pending-candidate preview overlay onto whatever canvas/context
  // LiteGraph is currently rendering.
  const overlayDraw = app.__vibecomfyAgentPreviewOverlayDraw || function (ctx) {
    const panel = currentAgentPanel();
    if (!panel) {
      return;
    }
    if (panel.state.phase !== PANEL_STATE.AWAITING_REVIEW) {
      return;
    }
    if (!panel.state.candidateGraph) {
      return;
    }
    try {
      const diff = getOrBuildPreviewDiff();
      if (diff) {
        drawPreviewOverlay(ctx, diff);
      }
    } catch (e) {
      console.warn("[vibecomfy] drawPreviewOverlay threw:", e);
    }
  };
  app.__vibecomfyAgentPreviewOverlayDraw = overlayDraw;
  try {
    const install = installPreviewForegroundOverlay(app, overlayDraw, { windowObj: window });
    _previewForegroundInstallReport = install;
    app.__vibecomfyAgentPreviewOverlayInstalled = true;
    if (install.polling) {
      console.warn(`[vibecomfy] preview overlay install degraded: ${install.detail}`);
    }
  } catch (e) {
    if (e?.code === "PREVIEW_FOREGROUND_UNAVAILABLE") {
      _previewForegroundInstallReport = { capability: e.capability, strategy: "unavailable", degraded: true, detail: e.message };
      console.warn(`[vibecomfy] preview overlay unavailable: ${e.capability?.detail || e.message}`);
      return;
    }
    throw e;
  }
}

async function checkFrontendVersion() {
  let version = "unknown";
  try {
    const res = await fetch("/system_stats");
    const stats = await res.json();
    version = stats?.system?.comfyui_frontend_package || "unknown";
  } catch (e) {
    version = "unknown";
  }
  const major = SUPPORTED_FRONTEND.split(".").slice(0, 2).join(".");
  if (version === "unknown" || !String(version).startsWith(major)) {
    console.warn(`VibeComfy: frontend version ${version} outside supported range, activating anyway`);
  }
}

function errorModal(err) {
  const kind = err?.kind || "Error";
  const message = err?.message || err?.error || String(err);
  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", `${kind}: ${message}`));
  const close = button("Close", () => overlay.remove());
  box.appendChild(close);
}

function clearNode(node) {
  while (node.children.length) {
    node.removeChild(node.children[0]);
  }
}

function appendChildOnce(parent, child) {
  if (!parent || !child) {
    return child;
  }
  if (child.parentNode && typeof child.parentNode.removeChild === "function") {
    child.parentNode.removeChild(child);
  }
  return parent.appendChild(child);
}

function panelSection(id, title) {
  const section = el("section");
  section.id = id;
  section.className = "vibecomfy-agent-panel-region";
  Object.assign(section.style, {
    border: "1px solid #34343a",
    borderRadius: "6px",
    background: "#17171c",
    padding: "10px",
    display: "grid",
    gap: "8px",
    minWidth: "0",
    maxWidth: "100%",
    overflow: "hidden",
  });

  const heading = el("div", title);
  Object.assign(heading.style, {
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#9da1ac",
    fontWeight: "600",
  });

  const body = el("div");
  body.className = "vibecomfy-agent-panel-region-body";
  Object.assign(body.style, {
    display: "grid",
    gap: "6px",
    fontSize: "12px",
    lineHeight: "1.4",
    minWidth: "0",
    maxWidth: "100%",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  });

  section.appendChild(heading);
  section.appendChild(body);
  return { section, body };
}

function muted(text) {
  const node = el("div", text);
  node.style.color = "#8d93a1";
  return node;
}

function labelValue(label, value) {
  const node = el("div");
  const key = el("span", `${label}: `);
  key.style.color = "#9da1ac";
  const val = el("span", value);
  val.style.color = "#f3f5f7";
  node.appendChild(key);
  node.appendChild(val);
  return node;
}

function setVisible(node, visible, display = "") {
  node.style.display = visible ? display : "none";
}

function setButtonEmphasis(buttonNode, visible, tone) {
  setVisible(buttonNode, visible, "inline-flex");
  buttonNode.style.opacity = visible ? "1" : "0";
  if (tone === "primary") {
    buttonNode.style.background = "#3d8bfd";
    buttonNode.style.borderColor = "#4d98ff";
    buttonNode.style.color = "#f6fbff";
  } else if (tone === "danger") {
    buttonNode.style.background = "#492222";
    buttonNode.style.borderColor = "#8f4747";
    buttonNode.style.color = "#ffd8d8";
  } else {
    buttonNode.style.background = "#272b33";
    buttonNode.style.borderColor = "#414855";
    buttonNode.style.color = "#edf2f7";
  }
}

function appendTextLine(target, text, color = "#edf2f7") {
  const node = el("div", text);
  node.style.color = color;
  node.style.minWidth = "0";
  node.style.overflowWrap = "anywhere";
  target.appendChild(node);
}

function appendCodeLine(target, text, color = "#b9ffcc") {
  const node = el("code", text);
  Object.assign(node.style, {
    color,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: "11px",
  });
  target.appendChild(node);
}

function safeJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch (e) {
    return String(value);
  }
}

function scrubDebugPayload(value, depth = 0) {
  if (value == null || typeof value !== "object") {
    return value;
  }
  if (depth > 5) {
    return "[truncated]";
  }
  if (Array.isArray(value)) {
    if (value.length > 50) {
      return {
        kind: "array",
        length: value.length,
        preview: value.slice(0, 8).map((item) => scrubDebugPayload(item, depth + 1)),
      };
    }
    return value.map((item) => scrubDebugPayload(item, depth + 1));
  }
  const result = {};
  for (const [key, entry] of Object.entries(value)) {
    if (key === "graph" || key === "candidate" || key === "candidate_graph") {
      const graph = key === "candidate" && entry?.graph ? entry.graph : entry;
      result[key] = {
        graph_omitted: true,
        node_count: Array.isArray(graph?.nodes) ? graph.nodes.length : null,
        link_count: Array.isArray(graph?.links) ? graph.links.length : null,
      };
      continue;
    }
    if (key === "raw_payload" && entry && typeof entry === "object") {
      result[key] = scrubDebugPayload({
        ok: entry.ok,
        kind: entry.kind,
        stage: entry.stage,
        session_id: entry.session_id,
        turn_id: entry.turn_id,
        candidate_graph_hash: entry.candidate_graph_hash,
        audit_ref: entry.audit_ref,
        apply_eligibility: entry.apply_eligibility,
        rebaseline_recovery: entry.rebaseline_recovery,
      }, depth + 1);
      continue;
    }
    result[key] = scrubDebugPayload(entry, depth + 1);
  }
  return result;
}

function compactDetailsPreview(value) {
  if (value == null || typeof value !== "object") {
    return "";
  }
  const parts = [];
  const pushPart = (key, entry) => {
    if (parts.length >= 12) {
      return;
    }
    if (entry == null || typeof entry === "number" || typeof entry === "boolean") {
      parts.push(`${key}: ${String(entry)}; "${key}": ${String(entry)}`);
    } else if (typeof entry === "string") {
      const quoted = /(?:^|_)turn_id$|(?:^|_)id$/.test(key) ? ` (${JSON.stringify(entry)})` : "";
      parts.push(`${key}: ${entry}${quoted}`);
    } else if (Array.isArray(entry)) {
      parts.push(`${key}: [${entry.length}]`);
    } else if (entry && typeof entry === "object") {
      const message = entry.message || entry.user_facing_message || entry.path;
      if (typeof message === "string" && message) {
        parts.push(`${key}: ${message}`);
      } else {
        parts.push(`${key}: {...}`);
      }
    }
  };
  for (const [key, entry] of Object.entries(value)) {
    if (key === "graph" || key === "candidate_graph" || key === "candidate") {
      continue;
    }
    pushPart(key, entry);
    if (parts.length >= 8) {
      break;
    }
  }
  const wanted = new Set([
    "expected_structural_graph_hash",
    "expected_live_canvas_token",
    "expected_graph_hash",
    "expected_baseline_graph_hash",
    "rebaseline_response",
    "accept_response",
  ]);
  const visit = (node, depth = 0) => {
    if (!node || typeof node !== "object" || depth > 4 || parts.length >= 12) {
      return;
    }
    for (const [key, entry] of Object.entries(node)) {
      if (key === "graph" || key === "candidate_graph" || key === "candidate") {
        continue;
      }
      if (wanted.has(key) && !parts.some((part) => part.startsWith(`${key}:`))) {
        pushPart(key, entry);
      }
      if (entry && typeof entry === "object" && !Array.isArray(entry)) {
        visit(entry, depth + 1);
      }
    }
  };
  visit(value);
  return parts.join("; ");
}

function clonePlainData(value) {
  if (value == null) {
    return value;
  }
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (_e) {
    return value;
  }
}

// ── Audit download helpers ─────────────────────────────────────────────────
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function buildAuditEnvelope(turnEntry) {
  const envelope = {
    generated_at: new Date().toISOString(),
    frontend_source: "vibecomfy_roundtrip.js",
    turn: turnEntry
      ? {
          entry_type: turnEntry.entry_type || null,
          turn_key: turnEntry.turn_key || null,
          status: turnEntry.status || "unknown",
          session_id: turnEntry.session_id || null,
          turn_id: turnEntry.turn_id || null,
          turn_number: Number.isFinite(turnEntry.turn_number) ? turnEntry.turn_number : null,
          baseline_turn_id: turnEntry.baseline_turn_id || null,
          task: turnEntry.task || null,
          timestamp: turnEntry.timestamp || null,
          failure_kind: turnEntry.failure_kind || null,
          failure_stage: turnEntry.failure_stage || null,
          message: turnEntry.message || null,
          audit_ref: turnEntry.audit_ref || null,
          parent_turn_id: turnEntry.parent_turn_id || null,
        }
      : null,
  };
  // Merge the raw response payload if available
  if (turnEntry?.raw_payload && typeof turnEntry.raw_payload === "object") {
    envelope.response_payload = turnEntry.raw_payload;
  }
  return envelope;
}

function downloadTurnAudit(panel, turnIndex) {
  if (!panel || !Array.isArray(panel.state.turns)) {
    return;
  }
  const turnEntry = panel.state.turns[turnIndex];
  if (!turnEntry) {
    return;
  }
  const envelope = buildAuditEnvelope(turnEntry);
  const blob = new Blob([JSON.stringify(envelope, null, 2)], {
    type: "application/json",
  });
  const turnId = turnEntry.turn_id || `turn-${turnIndex}`;
  const status = turnEntry.status || "unknown";
  downloadBlob(blob, `vibecomfy-audit-${status}-${turnId}.json`);
}

function downloadTurnAuditEntry(turnEntry, turnIndex = 0) {
  if (!turnEntry) {
    return;
  }
  const envelope = buildAuditEnvelope(turnEntry);
  const blob = new Blob([JSON.stringify(envelope, null, 2)], {
    type: "application/json",
  });
  const turnId = turnEntry.turn_id || turnEntry.parent_turn_id || `turn-${turnIndex}`;
  const status = turnEntry.status || "unknown";
  downloadBlob(blob, `vibecomfy-audit-${status}-${turnId}.json`);
}

function downloadCurrentAudit(panel) {
  if (!panel) {
    return;
  }
  const latestTurn =
    Array.isArray(panel.state.turns) && panel.state.turns.length
      ? panel.state.turns[0]
      : null;
  const envelope = buildAuditEnvelope(latestTurn);
  // Attach any current audit_ref
  if (panel.state.auditRef && !envelope.turn?.audit_ref) {
    if (!envelope.turn) {
      envelope.turn = { audit_ref: panel.state.auditRef };
    } else {
      envelope.turn.audit_ref = panel.state.auditRef;
    }
  }
  // Attach current failure if in error state
  if (panel.state.failure && !envelope.turn) {
    envelope.turn = {
      status: "failed",
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
      baseline_turn_id: panel.state.baselineTurnId,
      failure_kind: panel.state.failure.kind,
      failure_stage: panel.state.failure.stage,
      message: panel.state.failure.user_facing_message || panel.state.failure.message,
    };
    if (panel.state.failure.audit_ref) {
      envelope.turn.audit_ref = panel.state.failure.audit_ref;
    }
    if (panel.state.failure && typeof panel.state.failure === "object") {
      envelope.response_payload = panel.state.failure;
    }
  }
  const blob = new Blob([JSON.stringify(envelope, null, 2)], {
    type: "application/json",
  });
  const turnId = panel.state.turnId || "current";
  const status = panel.state.phase || "unknown";
  downloadBlob(blob, `vibecomfy-audit-${status}-${turnId}.json`);
}

function canonicalizeJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => canonicalizeJsonValue(entry));
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entryValue]) => [key, canonicalizeJsonValue(entryValue)]);
    return Object.fromEntries(entries);
  }
  return value;
}

function canonicalJsonString(value) {
  return JSON.stringify(canonicalizeJsonValue(value));
}

async function sha256HexUtf8(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function captureLiveCanvasRevision() {
  const graph = app?.canvas?.graph;
  const revision = graph?.getRevision?.()
    ?? graph?.revision
    ?? graph?._vibecomfyLiveCanvasToken
    ?? graph?._vibecomfy_live_canvas_token
    ?? graph?._version
    ?? graph?._revision
    ?? null;
  return revision == null ? null : String(revision);
}

// Apply-state freshness must ignore editor-only serialization churn. ComfyUI can
// rewrite layout, preview, and other non-execution fields between submit and
// apply even when the graph the user edits is unchanged. This projection keeps
// only execution identity: node ids/classes, link endpoints, widget values, and
// mode. A real add/remove/rewire/widget edit changes it; pos/size/flags/groups,
// view state, properties, and preview blobs do not.
function _normalizeStructuralLink(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => _normalizeStructuralLink(entry));
  }
  if (value && typeof value === "object") {
    return canonicalizeJsonValue(value);
  }
  return value;
}

function _naturalStructuralNodeIdKey(value) {
  const text = String(value ?? "");
  if (/^-?\d+$/.test(text)) {
    return { kind: 0, value: Number.parseInt(text, 10) };
  }
  return { kind: 1, value: text };
}

function _compareNaturalStructuralNodeIds(left, right) {
  const leftKey = _naturalStructuralNodeIdKey(left);
  const rightKey = _naturalStructuralNodeIdKey(right);
  if (leftKey.kind !== rightKey.kind) {
    return leftKey.kind - rightKey.kind;
  }
  if (leftKey.value < rightKey.value) {
    return -1;
  }
  if (leftKey.value > rightKey.value) {
    return 1;
  }
  return 0;
}

function _isPreviewLikeKey(key) {
  return /(?:^|_)(?:video)?preview(?:_|$)/i.test(String(key || ""));
}

function _normalizeStructuralWidgetValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => _normalizeStructuralWidgetValue(entry));
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value)
      .filter(([key]) => !_isPreviewLikeKey(key))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entryValue]) => [key, _normalizeStructuralWidgetValue(entryValue)]);
    return Object.fromEntries(entries);
  }
  return value;
}

function _structuralSocketNames(sockets) {
  return Array.isArray(sockets)
    ? sockets.map((socket) => (socket && typeof socket === "object" ? socket.name ?? null : null))
    : [];
}

function _structuralSlotName(names, slot) {
  if (Number.isInteger(slot) && slot >= 0 && slot < names.length) {
    return names[slot] ?? null;
  }
  return slot ?? null;
}

export function buildStructuralGraphProjection(graph) {
  if (!graph || typeof graph !== "object") {
    return { nodes: [], links: [] };
  }
  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const inputNames = new Map();
  const outputNames = new Map();
  for (const rawNode of rawNodes) {
    if (!rawNode || typeof rawNode !== "object") {
      continue;
    }
    const nodeId = rawNode.id ?? null;
    inputNames.set(nodeId, _structuralSocketNames(rawNode.inputs));
    outputNames.set(nodeId, _structuralSocketNames(rawNode.outputs));
  }

  const nodes = rawNodes.map((rawNode) => {
    const node = rawNode && typeof rawNode === "object" ? rawNode : {};
    const wiredInputs = Array.isArray(node.inputs)
      ? node.inputs
          .filter((input) => input && typeof input === "object" && input.link != null && input.name != null)
          .map((input) => String(input.name))
          .sort()
      : [];
    const liveOutputs = Array.isArray(node.outputs)
      ? node.outputs
          .filter((output) => {
            if (!output || typeof output !== "object" || output.name == null) {
              return false;
            }
            return Array.isArray(output.links) ? output.links.length > 0 : Boolean(output.links);
          })
          .map((output) => String(output.name))
          .sort()
      : [];
    return {
      id: node.id ?? null,
      type: node.type ?? null,
      mode: node.mode ?? null,
      inputs: wiredInputs,
      outputs: liveOutputs,
      widgets_values: _normalizeStructuralWidgetValue(node.widgets_values ?? []),
    };
  });
  nodes.sort((left, right) => {
    const idCmp = _compareNaturalStructuralNodeIds(left.id, right.id);
    if (idCmp) {
      return idCmp;
    }
    const leftType = String(left.type ?? "");
    const rightType = String(right.type ?? "");
    if (leftType < rightType) {
      return -1;
    }
    if (leftType > rightType) {
      return 1;
    }
    return 0;
  });
  const links = Array.isArray(graph?.links)
    ? graph.links
        .map((link) => {
          let originId;
          let originSlot;
          let targetId;
          let targetSlot;
          let linkType;
          if (Array.isArray(link) && link.length >= 6) {
            [, originId, originSlot, targetId, targetSlot, linkType] = link;
          } else if (link && typeof link === "object") {
            originId = link.origin_id;
            originSlot = link.origin_slot;
            targetId = link.target_id;
            targetSlot = link.target_slot;
            linkType = link.type;
          } else {
            return null;
          }
          return {
            from: originId ?? null,
            out: _structuralSlotName(outputNames.get(originId ?? null) ?? [], originSlot),
            to: targetId ?? null,
            in: _structuralSlotName(inputNames.get(targetId ?? null) ?? [], targetSlot),
            type: linkType ?? null,
          };
        })
        .filter((link) => link != null)
    : [];
  links.sort((left, right) =>
    JSON.stringify(canonicalizeJsonValue(_normalizeStructuralLink(left))).localeCompare(
      JSON.stringify(canonicalizeJsonValue(_normalizeStructuralLink(right))),
    ),
  );
  return { nodes, links };
}

async function structuralGraphHash(graph) {
  return sha256HexUtf8(canonicalJsonString(buildStructuralGraphProjection(graph)));
}

function captureLiveCanvasToken(_graphHash, structuralHash) {
  const revision = captureLiveCanvasRevision();
  if (revision != null) {
    return `live:${revision}`;
  }
  return structuralHash ? `structure:${structuralHash}` : `hash:${_graphHash}`;
}

function normalizeRoutePreference(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  return ROUTE_ALIASES[normalized] || "deepseek";
}

function normalizeModelPreference(value) {
  const normalized = String(value || "").trim();
  return normalized ? normalized : null;
}

function buildSubmitIdempotencyKey({ sessionId, graphHash, route, model }) {
  const unique = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
  const modelPart = model || "default";
  const sessionPart = sessionId || "new";
  return `submit:${sessionPart}:${route}:${modelPart}:${graphHash.slice(0, 12)}:${unique}`;
}

function buildActionIdempotencyKey({ action, sessionId, turnId, graphHash }) {
  const unique = typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
  return `${action}:${sessionId}:${turnId}:${graphHash.slice(0, 12)}:${unique}`;
}

function buildRebaselineIdempotencyKey({ sessionId, reason, baselineGraphHash, structuralHash }) {
  const sessionPart = sessionId || "new";
  const reasonPart = String(reason || "continue_from_canvas").trim() || "continue_from_canvas";
  const baselinePart = typeof baselineGraphHash === "string" && baselineGraphHash
    ? baselineGraphHash.slice(0, 12)
    : "none";
  const structuralPart = typeof structuralHash === "string" && structuralHash
    ? structuralHash.slice(0, 12)
    : "unknown";
  return `rebaseline:${sessionPart}:${reasonPart}:${baselinePart}:${structuralPart}`;
}

function createDetails(summary, value) {
  const details = el("details");
  const heading = el("summary", summary);
  heading.style.cursor = "pointer";
  let rendered = false;
  const pre = el("pre", "");
  Object.assign(pre.style, {
    margin: "8px 0 0 0",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
    color: "#b9ffcc",
    fontSize: "11px",
    maxWidth: "100%",
    minWidth: "0",
  });
  const renderValue = () => {
    if (rendered) {
      return;
    }
    rendered = true;
    pre.textContent = safeJson(value);
  };
  details.addEventListener("toggle", () => {
    if (details.open) {
      renderValue();
    }
  });
  details.appendChild(heading);
  const preview = compactDetailsPreview(value);
  if (preview) {
    const previewNode = el("div", preview);
    Object.assign(previewNode.style, {
      marginTop: "4px",
      color: "#8d93a1",
      fontSize: "10px",
      overflowWrap: "anywhere",
      wordBreak: "break-word",
    });
    details.appendChild(previewNode);
  }
  details.appendChild(pre);
  return details;
}

function createBubbleDetailSection(title) {
  const section = el("div");
  Object.assign(section.style, {
    display: "grid",
    gap: "4px",
    minWidth: "0",
    maxWidth: "100%",
  });
  const heading = el("div", title);
  Object.assign(heading.style, {
    fontSize: "10px",
    fontWeight: "700",
    color: "#6b7080",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  });
  const body = el("div");
  Object.assign(body.style, {
    display: "grid",
    gap: "4px",
    minWidth: "0",
    maxWidth: "100%",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  });
  section.appendChild(heading);
  section.appendChild(body);
  return { section, body };
}

function createQueueIssue(code, message, detail = {}, severity = "error") {
  return { code, message, detail, severity };
}

function collectArrayAtPath(root, path) {
  let value = root;
  for (const key of path) {
    value = value?.[key];
    if (value == null) {
      return [];
    }
  }
  return Array.isArray(value) ? value : [];
}

function backendQueueIssueCandidates(report) {
  return [
    ...collectArrayAtPath(report, ["queue_blockers"]),
    ...collectArrayAtPath(report, ["diagnostics", "issues"]),
    ...collectArrayAtPath(report, ["gates", "queue_validate_ok", "evidence", "blockers"]),
    ...collectArrayAtPath(report, ["gates", "queue_validate_ok", "evidence", "queue_blockers"]),
  ];
}

function normalizeBackendIntentQueueIssue(issue) {
  if (!issue || issue.code !== "intent_node_queue_blocker") {
    return null;
  }
  const detail = issue.detail && typeof issue.detail === "object"
    ? { ...issue.detail }
    : {};
  for (const key of ["node_id", "class_type", "kind", "uid", "lowered", "runtime_backed", "provider", "confidence", "diagnostic"]) {
    if (detail[key] == null && issue[key] != null) {
      detail[key] = issue[key];
    }
  }
  const nodeId = detail.node_id || "unknown";
  const classType = detail.class_type || "vibecomfy.*";
  return createQueueIssue(
    issue.code,
    issue.message || issue.user_facing_message || `Node ${nodeId} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
    detail,
    issue.severity || "error",
  );
}

function collectQueueIssues(report) {
  const issues = backendQueueIssueCandidates(report)
    .map(normalizeBackendIntentQueueIssue)
    .filter(Boolean);
  const hasBackendIntentBlocker = issues.some((issue) => issue.code === "intent_node_queue_blocker");
  const recovery = Array.isArray(report?.recovery) ? report.recovery : [];
  for (const entry of recovery) {
    const nodeId = entry?.node_id;
    const classType = entry?.class_type;
    if (isIntentClassType(classType)) {
      if (entry?.lowered === true) {
        // lowered entries are informational — the intent node was already
        // statically lowered to native nodes; no queue blocker needed
        continue;
      }
      if (hasBackendIntentBlocker) {
        continue;
      }
      const kind = entry?.kind
        || INTENT_KIND_BY_CLASS_TYPE[classType]
        || "intent";
      const runtimeBacked = Boolean(entry?.runtime_backed);
      issues.push(createQueueIssue(
        "intent_node_queue_blocker",
        `Node ${nodeId} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
        {
          node_id: nodeId,
          class_type: classType,
          kind,
          uid: entry?.uid || null,
          lowered: false,
          runtime_backed: runtimeBacked,
          provider: entry?.provider || null,
          confidence: entry?.confidence ?? null,
          diagnostic: entry?.diagnostic || null,
        },
      ));
      continue;
    }
    if (entry?.schema_less === true) {
      issues.push(createQueueIssue(
        "schema_less_queue_blocker",
        `Node ${nodeId} (${classType}) has no schema evidence and cannot be queued safely.`,
        {
          node_id: nodeId,
          class_type: classType,
          provider: entry?.provider,
          confidence: entry?.confidence,
          diagnostic: entry?.diagnostic,
        },
      ));
      continue;
    }
    const confidence = entry?.confidence;
    if (typeof confidence === "number" && confidence <= 0.3) {
      issues.push(createQueueIssue(
        "low_confidence_queue_blocker",
        `Node ${nodeId} (${classType}) has low-confidence schema evidence and cannot be queued safely.`,
        {
          node_id: nodeId,
          class_type: classType,
          provider: entry?.provider,
          confidence,
          diagnostic: entry?.diagnostic,
        },
      ));
      continue;
    }
    if (confidence == null && entry?.schema_less !== true) {
      issues.push(createQueueIssue(
        "low_confidence_queue_blocker",
        `Node ${nodeId} (${classType}) has unresolved model/widget evidence and cannot be queued safely.`,
        {
          node_id: nodeId,
          class_type: classType,
          provider: entry?.provider,
          confidence: null,
          diagnostic: entry?.diagnostic || "unresolved model/widget: confidence could not be determined",
        },
      ));
    }
  }

  const strippedHelpers = report?.change?.content_edits?.stripped_helpers;
  if (Array.isArray(strippedHelpers) && strippedHelpers.length) {
    issues.push(createQueueIssue(
      "editor_only_node_queue_blocker",
      "Editor-only helper nodes would be stripped from the queued API graph.",
      { stripped_helpers: strippedHelpers.slice() },
    ));
  }

  if (!issues.some((issue) => issue.code === "intent_node_queue_blocker")) {
    const graphNodes = Array.isArray(report?.graph?.nodes)
      ? report.graph.nodes
      : report?.nodes
        ? (Array.isArray(report.nodes) ? report.nodes : [])
        : [];
    for (const node of graphNodes) {
      const classType = node?.type || node?.class_type;
      if (isIntentClassType(classType)) {
        issues.push(createQueueIssue(
          "intent_node_queue_blocker",
          `Node ${node?.id || "unknown"} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
          {
            node_id: node?.id || null,
            class_type: classType,
            kind: INTENT_KIND_BY_CLASS_TYPE[classType] || "intent",
            uid: node?.properties?.vibecomfy_uid || null,
            lowered: false,
            runtime_backed: false,
            provider: null,
            confidence: null,
            diagnostic: "detected from graph nodes (fallback for older report format)",
          },
        ));
      }
    }
  }

  return issues;
}

function getBackendStageInfo(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const stage = payload.backend_stage || payload.stage || null;
  const progress = payload.backend_progress ?? payload.progress ?? null;
  if (stage == null && progress == null) {
    return null;
  }
  return { stage, progress };
}

function buildStatusUrl(route, model) {
  const params = new URLSearchParams();
  if (route) {
    params.set("route", route);
  }
  if (model) {
    params.set("model", model);
  }
  const query = params.toString();
  return query ? `/vibecomfy/agent/status?${query}` : "/vibecomfy/agent/status";
}

function routeStatusState(panel) {
  return panel?.state?.routeStatus || { kind: ROUTE_STATUS_KIND.LOADING };
}

function routeOptionsFromStatus(status) {
  if (!status || typeof status !== "object" || Array.isArray(status)) {
    return null;
  }
  const options = status.route_options;
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    return null;
  }
  return options;
}

function getRouteOptions(panel) {
  return routeOptionsFromStatus(panel.state.statusSnapshot);
}

function getRouteDescriptor(panel, route = panel.fields.route.value) {
  const normalized = normalizeRoutePreference(route);
  return getRouteOptions(panel)?.[normalized] || null;
}

function nextMacrotask() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function clearAgentStatusRetry(panel) {
  const retry = panel?.state?.statusRetry;
  if (retry?.timerId) {
    clearTimeout(retry.timerId);
  }
  if (panel?.state) {
    panel.state.statusRetry = null;
  }
}

function scheduleAgentStatusRetry(panel, route, model, { quiet = true } = {}) {
  if (!panel?.state) {
    return;
  }
  const prior = panel.state.statusRetry;
  const priorAttempts =
    prior?.route === route && prior?.model === model && Number.isFinite(prior?.attempts)
      ? prior.attempts
      : 0;
  const attempts = priorAttempts + 1;
  if (attempts > AGENT_STATUS_RETRY_DELAYS_MS.length) {
    panel.state.statusRetry = { route, model, attempts: priorAttempts, exhausted: true, timerId: null };
    return;
  }
  const delayMs = AGENT_STATUS_RETRY_DELAYS_MS[attempts - 1];
  const timerId = setTimeout(() => {
    if (!panel?.state?.statusRetry || panel.state.statusRetry.timerId !== timerId) {
      return;
    }
    panel.state.statusRetry.timerId = null;
    refreshAgentStatus(panel, { quiet });
  }, delayMs);
  panel.state.statusRetry = { route, model, attempts, exhausted: false, timerId };
}

function populateRouteSelect(selectNode, routeOptions, {
  placeholderLabel = "Loading route/model status…",
  selectedRoute = selectNode.value,
} = {}) {
  const ownerDocument = selectNode?.ownerDocument || (typeof document !== "undefined" ? document : null);
  if (!ownerDocument) {
    return;
  }
  const preferredRoute = normalizeRoutePreference(selectedRoute);
  const knownRoutes = Object.keys(ROUTE_LABELS).filter((route) => routeOptions?.[route]);
  const extraRoutes = Object.keys(routeOptions || {}).filter((route) => !ROUTE_LABELS[route]);
  const desired = [...knownRoutes, ...extraRoutes];
  clearNode(selectNode);
  if (!desired.length) {
    const node = option(preferredRoute, placeholderLabel, ownerDocument);
    node.disabled = true;
    node.selected = true;
    selectNode.appendChild(node);
    selectNode.value = preferredRoute;
    return;
  }
  for (const route of desired) {
    const descriptor = routeOptions?.[route] || null;
    const label = ROUTE_LABELS[route] || route;
    const node = option(route, label, ownerDocument);
    if (descriptor?.normalized_route && descriptor.normalized_route !== route) {
      node.title = `${label} → ${descriptor.normalized_route}`;
    }
    selectNode.appendChild(node);
  }
  selectNode.value = desired.includes(preferredRoute) ? preferredRoute : desired[0];
}

async function refreshAgentStatus(panel, { quiet = false } = {}) {
  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  const requestEpoch =
    (Number.isFinite(panel.state.statusRequestEpoch) ? panel.state.statusRequestEpoch : 0) + 1;
  panel.state.statusRequestEpoch = requestEpoch;
  const priorRetry = panel.state.statusRetry;
  const retryAttempts =
    priorRetry?.route === route && priorRetry?.model === model && Number.isFinite(priorRetry?.attempts)
      ? priorRetry.attempts
      : 0;
  if (priorRetry?.timerId) {
    clearTimeout(priorRetry.timerId);
  }
  panel.state.statusRetry = retryAttempts > 0
    ? { route, model, attempts: retryAttempts, exhausted: false, timerId: null }
    : null;
  panel.state.routeStatus = {
    kind: ROUTE_STATUS_KIND.LOADING,
    requestedRoute: route,
    model,
  };
  if (typeof document !== "undefined") {
    renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
  }
  try {
    // Keep the initial "loading" paint observable, then let tests/users observe
    // the completed state after the request has actually been issued.
    await nextMacrotask();
    const res = await fetch(buildStatusUrl(route, model));
    let status = null;
    try {
      status = await res.json();
    } catch (error) {
      if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
        return;
      }
      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", error);
      panel.state.statusSnapshot = null;
      panel.state.routeStatus = {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        requestedRoute: route,
        model,
        detail: String(error),
      };
      panel.state.settingsMessage = "Malformed status payload; route/model controls disabled.";
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: "Malformed status payload",
        selectedRoute: route,
      });
      panel.fields.route.value = route;
      if (typeof document !== "undefined") {
        markAgentPanelDirtyAfterCommit(panel, SETTINGS_STATUS_RENDER_SECTIONS, "status");
      }
      return;
    }
    if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
      return;
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    clearAgentStatusRetry(panel);
    panel.state.statusSnapshot = status;
    const requestedRoute = normalizeRoutePreference(status?.requested_route || route);
    const routeOptions = routeOptionsFromStatus(status);
    if (!status || typeof status !== "object" || Array.isArray(status)) {
      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", status);
      panel.state.routeStatus = {
        kind: ROUTE_STATUS_KIND.MALFORMED,
        requestedRoute,
        model,
      };
      panel.state.settingsMessage = "Malformed status payload; route/model controls disabled.";
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: "Malformed status payload",
        selectedRoute: requestedRoute,
      });
      panel.fields.route.value = requestedRoute;
    } else if (!routeOptions) {
      console.warn("[vibecomfy] status payload missing route_options", status);
      panel.state.routeStatus = {
        kind: ROUTE_STATUS_KIND.MISSING_OPTIONS,
        requestedRoute,
        model,
      };
      panel.state.settingsMessage = "Status missing route options; route/model controls disabled.";
      populateRouteSelect(panel.fields.route, null, {
        placeholderLabel: "Route options unavailable",
        selectedRoute: requestedRoute,
      });
      panel.fields.route.value = requestedRoute;
    } else {
      populateRouteSelect(panel.fields.route, routeOptions, { selectedRoute: requestedRoute });
      panel.fields.route.value = requestedRoute;
      if (!routeOptions[requestedRoute]) {
        console.warn("[vibecomfy] status payload missing descriptor for requested route", {
          requestedRoute,
          routeOptions,
        });
        panel.state.routeStatus = {
          kind: ROUTE_STATUS_KIND.MALFORMED,
          requestedRoute,
          model,
        };
        panel.state.settingsMessage = "Malformed status payload; route/model controls disabled.";
      } else {
        panel.state.routeStatus = {
          kind: ROUTE_STATUS_KIND.READY,
          requestedRoute,
          model,
        };
        if (!quiet) {
          const availability = status?.provider_available === false ? "provider unavailable" : "provider ready";
          panel.state.settingsMessage = `${status?.requested_route || route} → ${status?.route || route} (${availability})`;
        }
      }
    }
    if (typeof status?.model === "string" && !panel.fields.model.value.trim()) {
      panel.fields.model.value = status.model;
    }
  } catch (e) {
    if (Number.isFinite(requestEpoch) && panel.state.statusRequestEpoch !== requestEpoch) {
      return;
    }
    panel.state.settingsMessage = `Status unavailable: ${String(e)}`;
    panel.state.statusSnapshot = null;
    panel.state.routeStatus = {
      kind: ROUTE_STATUS_KIND.UNAVAILABLE,
      requestedRoute: route,
      model,
      detail: String(e),
    };
    populateRouteSelect(panel.fields.route, null, {
      placeholderLabel: "Status unavailable",
      selectedRoute: route,
    });
    panel.fields.route.value = route;
    scheduleAgentStatusRetry(panel, route, model, { quiet: true });
  }
  if (typeof document === "undefined") {
    return;
  }
  const statusDirtySections = Array.isArray(panel?.state?.chatMessages) && panel.state.chatMessages.length
    ? [...SETTINGS_STATUS_RENDER_SECTIONS, RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD]
    : SETTINGS_STATUS_RENDER_SECTIONS;
  markAgentPanelDirtyAfterCommit(panel, statusDirtySections, "status");
}

function submitReadinessState(panel) {
  const routeStatus = routeStatusState(panel);
  if (routeStatus.kind === ROUTE_STATUS_KIND.LOADING) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Waiting for /vibecomfy/agent/status before enabling Submit.",
    };
  }
  if (routeStatus.kind === ROUTE_STATUS_KIND.MISSING_OPTIONS) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Submit is disabled because /vibecomfy/agent/status returned no route_options.",
    };
  }
  if (routeStatus.kind === ROUTE_STATUS_KIND.MALFORMED) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Submit is disabled because /vibecomfy/agent/status returned a malformed payload.",
    };
  }
  if (routeStatus.kind === ROUTE_STATUS_KIND.UNAVAILABLE) {
    return {
      ready: false,
      reason: routeStatus.kind,
      message: "Submit is disabled because /vibecomfy/agent/status is unavailable.",
    };
  }
  const status = panel?.state?.statusSnapshot;
  if (!status || typeof status !== "object" || Array.isArray(status)) {
    return {
      ready: false,
      reason: "missing_status",
      message: "Submit is disabled until /vibecomfy/agent/status returns a valid ready=true payload.",
    };
  }
  if (status.ready === true) {
    return { ready: true, reason: "ready", message: "" };
  }
  const statusMessage =
    (typeof status.readiness_message === "string" && status.readiness_message.trim())
    || (typeof status.message === "string" && status.message.trim())
    || (typeof status.reason === "string" && status.reason.trim())
    || "";
  return {
    ready: false,
    reason: status.ready === false ? "not_ready" : "missing_ready",
    message: statusMessage || "Submit is disabled until /vibecomfy/agent/status returns ready=true.",
  };
}

function clearCredentialInput(panel) {
  panel.fields.apiKey.value = "";
}

function normalizeApplyEligibility(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if (!Object.values(APPLY_ELIGIBILITY_REASON).includes(payload.reason)) {
    return null;
  }
  return {
    applyable: payload.applyable !== false,
    reason: payload.reason,
    message: typeof payload.message === "string" ? payload.message : "",
    warnings: Array.isArray(payload.warnings) ? payload.warnings.slice() : [],
  };
}

function noCandidateApplyEligibility() {
  return {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.NO_CANDIDATE,
    message: "No candidate is available to apply.",
    warnings: [],
  };
}

function ensureMissingEligibilityWarning(panel, detail) {
  if (!panel?.state) {
    console.warn(`[vibecomfy] ${detail.message}`);
    return;
  }
  const warningKey = [
    detail.reason,
    panel.state.turnId || "no-turn",
    panel.state.candidateGraphHash || "no-candidate-hash",
  ].join(":");
  if (panel.state.applyEligibilityWarningKey === warningKey) {
    return;
  }
  panel.state.applyEligibilityWarningKey = warningKey;
  panel.state.applyEligibilityWarning = detail;
  panel.state.debugPayload = {
    ...(panel.state.debugPayload && typeof panel.state.debugPayload === "object"
      ? panel.state.debugPayload
      : {}),
    apply_eligibility_warning: detail,
  };
  console.warn(`[vibecomfy] ${detail.message}`);
}

function missingContractApplyEligibility(panel, detail = {}) {
  const message = typeof detail.message === "string" && detail.message
    ? detail.message
    : "Backend response omitted canonical eligibility for this candidate. Apply is disabled until the contract is present.";
  const warning = {
    reason: APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT,
    message,
    turn_id: panel?.state?.turnId || null,
    candidate_graph_hash: panel?.state?.candidateGraphHash || null,
  };
  ensureMissingEligibilityWarning(panel, warning);
  return {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT,
    message,
    warnings: ["missing_contract"],
  };
}

export function syncBaselineFromResponse(panel, payload) {
  if (!panel?.state || !payload || typeof payload !== "object") {
    return;
  }
  const recovery = payload.rebaselineRecovery || null;
  transition(panel, "SYNC_BASELINE", {
    ...payload,
    ...(recovery
      ? { rebaselineRecovery: recovery }
      : (payload.ok === true ? { clearRebaselineRecovery: true } : {})),
  });
}



function synthesizeStaleRebaselineRecovery(payload, panel = null, actionBody = null) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if (String(payload.kind || "") !== "StaleStateMismatch") {
    return null;
  }
  const stage = String(payload.stage || "");
  if (stage && !["accept", "frontend", "ingest"].includes(stage)) {
    return null;
  }
  const lastSubmit = panel?.state?.lastSubmit || {};
  return {
    action: "rebaseline",
    endpoint: "/vibecomfy/agent-edit/rebaseline",
    reason: "stale_state_recovery",
    last_known_baseline_graph_hash:
      typeof payload.baseline_graph_hash === "string" ? payload.baseline_graph_hash
        : typeof payload.expected_baseline_graph_hash === "string" ? payload.expected_baseline_graph_hash
          : typeof panel?.state?.baselineGraphHash === "string" ? panel.state.baselineGraphHash
            : typeof lastSubmit.client_structural_graph_hash === "string" ? lastSubmit.client_structural_graph_hash
              : null,
    submit_graph_hash:
      typeof actionBody?.submit_graph_hash === "string" ? actionBody.submit_graph_hash
        : typeof panel?.state?.serverSubmitGraphHash === "string" ? panel.state.serverSubmitGraphHash
          : null,
    submit_structural_graph_hash:
      typeof lastSubmit.client_structural_graph_hash === "string" ? lastSubmit.client_structural_graph_hash : null,
    client_graph_hash:
      typeof actionBody?.client_graph_hash === "string" ? actionBody.client_graph_hash
        : typeof lastSubmit.client_graph_hash === "string" ? lastSubmit.client_graph_hash
          : null,
    client_structural_graph_hash:
      typeof payload.client_structural_graph_hash === "string" ? payload.client_structural_graph_hash
        : typeof lastSubmit.client_structural_graph_hash === "string" ? lastSubmit.client_structural_graph_hash
          : null,
  };
}

function recoveryForFailure(payload, panel = null, actionBody = null) {
  const extracted = readRebaselineRecovery(payload, { endpoint: "recoveryForFailure", allowLegacy: true });
  if (extracted) {
    return extracted;
  }
  return synthesizeStaleRebaselineRecovery(payload, panel, actionBody);
}

function applyEligibility(panel, liveCanvasSnapshot = null) {
  if (!panel?.state?.candidateGraph) {
    return noCandidateApplyEligibility();
  }
  const canonicalEligibility = normalizeApplyEligibility(panel.state.applyEligibility);
  if (canonicalEligibility) {
    panel.state.applyEligibilityWarning = null;
    panel.state.applyEligibilityWarningKey = null;
    return canonicalEligibility;
  }
  return missingContractApplyEligibility(panel);
}

function disabledApplyEligibility(reason, message, warnings = []) {
  return {
    applyable: false,
    reason,
    message: typeof message === "string" ? message : "",
    warnings: Array.isArray(warnings) ? warnings.slice() : [],
  };
}

function candidateTurnId(message, snapshot = null) {
  if (typeof snapshot?.turn_id === "string" && snapshot.turn_id) {
    return snapshot.turn_id;
  }
  if (typeof message?.turn_id === "string" && message.turn_id) {
    return message.turn_id;
  }
  return null;
}

function candidateGraphPresentForBubble(message, snapshot = null) {
  if (snapshot && Object.prototype.hasOwnProperty.call(snapshot, "candidateGraphPresent")) {
    return Boolean(snapshot.candidateGraphPresent);
  }
  const candidateGraph = message?.candidateGraph
    || message?.candidate?.graph
    || message?.response?.candidateGraph
    || message?.response?.candidate?.graph
    || null;
  return Boolean(candidateGraph && typeof candidateGraph === "object");
}

function snapshotEligibilityForBubble(message, snapshot = null) {
  const normalizedSnapshot = normalizeApplyEligibility(snapshot?.applyEligibility);
  if (normalizedSnapshot) {
    return normalizedSnapshot;
  }
  const normalizedMessage = normalizeApplyEligibility(
    message?.eligibility
      || message?.response?.eligibility
      || message?.apply_eligibility
      || message?.response?.apply_eligibility
      || null,
  );
  if (normalizedMessage) {
    return normalizedMessage;
  }
  return null;
}

function candidateActionState(panel, message = null, snapshot = null) {
  const submitting = panel?.state?.phase === PANEL_STATE.SUBMITTING;
  const applying = panel?.state?.phase === PANEL_STATE.APPLYING;
  const activeTurnId =
    panel?.state?.candidateGraph && typeof panel.state.turnId === "string" && panel.state.turnId
      ? panel.state.turnId
      : null;
  const turnId = candidateTurnId(message, snapshot) || activeTurnId;
  const candidatePresent = message || snapshot
    ? candidateGraphPresentForBubble(message, snapshot)
    : Boolean(panel?.state?.candidateGraph);

  if (!candidatePresent) {
    return {
      visible: false,
      active: false,
      turnId,
      eligibility: noCandidateApplyEligibility(),
      applyDisabled: true,
      rejectDisabled: true,
    };
  }

  const active =
    !message && !snapshot
      ? Boolean(candidatePresent && activeTurnId)
      : Boolean(activeTurnId && turnId && activeTurnId === turnId);
  let eligibility;
  if (!message && !snapshot) {
    eligibility = applyEligibility(panel);
  } else if (active) {
    eligibility = applyEligibility(panel);
  } else {
    const historicalEligibility = snapshotEligibilityForBubble(message, snapshot);
    if (historicalEligibility?.reason === APPLY_ELIGIBILITY_REASON.SUPERSEDED) {
      eligibility = historicalEligibility;
    } else {
      eligibility = disabledApplyEligibility(
        APPLY_ELIGIBILITY_REASON.NOT_LATEST,
        "Only the latest candidate can be applied.",
        ["not_latest"],
      );
    }
  }

  const blockerMessage =
    !eligibility.applyable
      ? (eligibility.message || (Array.isArray(eligibility.warnings) ? eligibility.warnings[0] : "") || "")
      : "";

  return {
    visible: true,
    active,
    turnId,
    eligibility,
    blockerMessage,
    applyDisabled: applying || !active || !eligibility.applyable,
    rejectDisabled: submitting || applying || !active,
  };
}

async function buildSubmitSnapshot(panel) {
  const graph = app.canvas.graph.serialize();
  const graphJson = canonicalJsonString(graph);
  const graphHash = await sha256HexUtf8(graphJson);
  const structuralHash = await structuralGraphHash(graph);
  const liveCanvasToken = captureLiveCanvasToken(graphHash, structuralHash);
  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  const idempotencyKey = buildSubmitIdempotencyKey({
    sessionId: panel.state.sessionId,
    graphHash,
    route,
    model,
  });
  return { graph, graphJson, graphHash, structuralHash, liveCanvasToken, route, model, idempotencyKey };
}

async function buildCanvasSnapshot() {
  const graph = app.canvas.graph.serialize();
  const graphJson = canonicalJsonString(graph);
  const graphHash = await sha256HexUtf8(graphJson);
  const structuralHash = await structuralGraphHash(graph);
  const liveCanvasToken = captureLiveCanvasToken(graphHash, structuralHash);
  return { graph, graphJson, graphHash, structuralHash, liveCanvasToken };
}

function createAgentPanelShell() {
  const root = el("aside");
  const panelId = nextAgentPanelId();
  root.id = PANEL_IDS.root;
  root.className = "vibecomfy-agent-panel-root";
  root.dataset.vibecomfyPanelId = panelId;
  root.dataset.vibecomfyPanelRoot = "1";
  root.dataset.open = "0";
  Object.assign(root.style, {
    position: "fixed",
    top: "0",
    right: "0",
    width: "420px",
    height: "100vh",
    zIndex: "9999",
    pointerEvents: "none",
    transform: "translateX(432px)",
    transition: "transform 140ms ease",
  });

  const shell = el("div");
  shell.id = PANEL_IDS.shell;
  shell.className = "vibecomfy-agent-panel-shell";
  Object.assign(shell.style, {
    position: "relative",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    minHeight: "0",
    background: "#101115",
    color: "#edf2f7",
    borderLeft: "1px solid #282a32",
    boxShadow: "-10px 0 28px rgba(0,0,0,0.38)",
    fontFamily: "monospace",
    pointerEvents: "auto",
  });

  // ── Header (title, status, settings gear, close) ────────────────────────
  const header = el("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
    padding: "10px 14px 6px 14px",
    borderBottom: "1px solid #282a32",
    flexWrap: "wrap",
  });
  const headerLeft = el("div");
  Object.assign(headerLeft.style, {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  });
  const title = el("div", "VibeComfy Agent Edit");
  title.style.fontWeight = "700";
  title.style.fontSize = "13px";
  headerLeft.appendChild(title);
  const sub = el("div", "Durable agent edit panel.");
  sub.style.fontSize = "11px";
  sub.style.color = "#8d93a1";
  headerLeft.appendChild(sub);
  header.appendChild(headerLeft);

  const headerRight = el("div");
  Object.assign(headerRight.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexShrink: "0",
  });

  const status = el("div", "Idle");
  status.id = PANEL_IDS.status;
  Object.assign(status.style, {
    fontSize: "11px",
    color: "#9da1ac",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  });
  headerRight.appendChild(status);

  const settingsGearBtn = button("\u2699", () => {
    const panel = currentAgentPanel();
    if (panel) {
      const popover = panel.settingsPopover;
      if (popover) {
        const isOpen = popover.style.display !== "none";
        if (!isOpen && !panel.__settingsPopoverEverOpened) {
          panel.__settingsPopoverEverOpened = true;
          renderAgentPanel(panel, { dirtySections: [RENDER_SECTIONS.SETTINGS, RENDER_SECTIONS.DEVELOPER] });
        }
        popover.style.display = isOpen ? "none" : "block";
      }
    }
  });
  settingsGearBtn.title = "Settings";
  Object.assign(settingsGearBtn.style, {
    padding: "4px 8px",
    fontSize: "14px",
    lineHeight: "1",
  });

  const closeBtn = button("Close", () => closeAgentPanel(currentAgentPanel()));
  closeBtn.id = PANEL_IDS.close;
  closeBtn.style.padding = "4px 8px";
  closeBtn.style.fontSize = "11px";

  headerRight.appendChild(settingsGearBtn);
  headerRight.appendChild(closeBtn);
  header.appendChild(headerRight);

  // ── Compact meta row (now inside header area, not a full grid row) ──────
  const metaRow = el("div");
  Object.assign(metaRow.style, {
    display: "flex",
    gap: "10px",
    padding: "4px 14px 6px 14px",
    borderBottom: "1px solid #282a32",
    background: "#14161b",
    fontSize: "10px",
    color: "#8d93a1",
    flexWrap: "wrap",
  });

  // ── Thread mount (scrollable chat + activity region) ────────────────────
  const thread = el("div");
  thread.dataset.vibecomfyAgentThread = "1";
  Object.assign(thread.style, {
    flex: "1 1 auto",
    minHeight: "0",
    overflowY: "auto",
    padding: "12px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  });

  const threadRegion = panelSection(PANEL_IDS.threadRegion, "Thread");
  threadRegion.section.style.border = "none";
  threadRegion.section.style.background = "transparent";
  threadRegion.section.style.padding = "0";
  // The section is a flex child of the scrollable `thread` wrapper. Without
  // flexShrink:0 it shrinks to the wrapper's height and (overflow:hidden from
  // panelSection) CLIPS the conversation instead of letting the wrapper scroll.
  threadRegion.section.style.flexShrink = "0";
  threadRegion.body.style.gap = "10px";

  // Chat section: persisted conversation bubbles (M3).
  const chatRegion = panelSection(PANEL_IDS.chatRegion, "Chat");
  threadRegion.body.appendChild(chatRegion.section);

  const historyRegion = panelSection(PANEL_IDS.historyRegion, "");
  historyRegion.section.style.display = "none";
  threadRegion.body.appendChild(historyRegion.section);

  const candidateRegion = panelSection(PANEL_IDS.candidateRegion, "");
  candidateRegion.section.style.display = "none";
  threadRegion.body.appendChild(candidateRegion.section);

  const failureRegion = panelSection(PANEL_IDS.failureRegion, "");
  failureRegion.section.style.display = "none";
  threadRegion.body.appendChild(failureRegion.section);

  const queueRegion = panelSection(PANEL_IDS.queueRegion, "");
  queueRegion.section.style.display = "none";
  threadRegion.body.appendChild(queueRegion.section);

  const auditRegion = panelSection(PANEL_IDS.auditRegion, "");
  auditRegion.section.style.display = "none";
  threadRegion.body.appendChild(auditRegion.section);

  const debugRegion = panelSection(PANEL_IDS.debugRegion, "");
  debugRegion.section.style.display = "none";
  threadRegion.body.appendChild(debugRegion.section);

  thread.appendChild(threadRegion.section);

  // ── Composer (bottom mount: prompt + action buttons) ────────────────────
  const composer = el("div");
  Object.assign(composer.style, {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    padding: "10px 14px 12px 14px",
    borderTop: "1px solid #282a32",
    background: "#14161b",
  });

  const promptRegion = panelSection(PANEL_IDS.promptRegion, "Prompt");
  promptRegion.section.style.border = "none";
  promptRegion.section.style.background = "transparent";
  promptRegion.section.style.padding = "0";
  const textarea = document.createElement("textarea");
  textarea.id = PANEL_IDS.prompt;
  textarea.placeholder = "Describe the workflow change...";
  Object.assign(textarea.style, {
    width: "100%",
    minHeight: "80px",
    resize: "vertical",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  promptRegion.body.appendChild(textarea);
  composer.appendChild(promptRegion.section);

  const composerButtons = el("div");
  Object.assign(composerButtons.style, {
    display: "flex",
    gap: "6px",
    flexWrap: "wrap",
  });

  const submitBtn = button("Submit", () => submitAgentEdit(currentAgentPanel()));
  submitBtn.id = PANEL_IDS.submit;
  const stopBtn = button("Stop", () => stopAgentSubmit(currentAgentPanel()));
  stopBtn.style.display = "none";
  const applyBtn = button("Apply Candidate", () => applyAgentCandidate(currentAgentPanel()));
  applyBtn.id = PANEL_IDS.apply;
  const rejectBtn = button("Reject Candidate", () => rejectAgentCandidate(currentAgentPanel()));
  rejectBtn.id = PANEL_IDS.reject;
  const undoBtn = button("Undo Last Apply", () => undoLastApply(currentAgentPanel()));
  undoBtn.id = PANEL_IDS.undo;
  const newConvBtn = button("New conversation", () => newAgentConversation(currentAgentPanel()));
  newConvBtn.id = "vibecomfy-agent-panel-new-conversation";

  composerButtons.appendChild(submitBtn);
  composerButtons.appendChild(stopBtn);
  composerButtons.appendChild(applyBtn);
  composerButtons.appendChild(rejectBtn);
  composerButtons.appendChild(undoBtn);
  composerButtons.appendChild(newConvBtn);
  composer.appendChild(composerButtons);

  const composerNotice = el("div");
  composerNotice.id = PANEL_IDS.composerNotice;
  Object.assign(composerNotice.style, {
    display: "none",
    padding: "8px 10px",
    borderRadius: "6px",
    border: "1px solid #2a313c",
    background: "#0d1118",
    color: "#c4ccd6",
    fontSize: "11px",
    lineHeight: "1.45",
    whiteSpace: "pre-wrap",
  });
  composer.appendChild(composerNotice);

  // ── Settings popover (absolutely positioned overlay) ────────────────────
  const settingsPopover = el("div");
  settingsPopover.className = "vibecomfy-agent-panel-settings-popover";
  Object.assign(settingsPopover.style, {
    display: "none",
    position: "absolute",
    top: "44px",
    right: "14px",
    width: "360px",
    maxWidth: "calc(100% - 28px)",
    background: "#17171c",
    border: "1px solid #34343a",
    borderRadius: "8px",
    boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
    zIndex: "10000",
    padding: "12px",
  });

  const settingsRegion = panelSection(PANEL_IDS.settingsRegion, "Settings");
  settingsRegion.section.style.border = "none";
  settingsRegion.section.style.background = "transparent";
  settingsRegion.section.style.padding = "0";

  const routeSelect = document.createElement("select");
  routeSelect.id = PANEL_IDS.route;
  Object.assign(routeSelect.style, {
    width: "100%",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
  });
  populateRouteSelect(routeSelect, null, { selectedRoute: "auto" });
  routeSelect.value = "auto";
  const modelInput = document.createElement("input");
  modelInput.id = PANEL_IDS.model;
  modelInput.placeholder = "Model override (optional)";
  Object.assign(modelInput.style, {
    width: "100%",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  const apiKeyInput = document.createElement("input");
  apiKeyInput.id = PANEL_IDS.apiKey;
  apiKeyInput.type = "password";
  apiKeyInput.placeholder = "DeepSeek API key";
  Object.assign(apiKeyInput.style, {
    width: "100%",
    background: "#0d0e12",
    color: "#edf2f7",
    border: "1px solid #373c46",
    borderRadius: "6px",
    padding: "6px 8px",
    fontFamily: "monospace",
    fontSize: "12px",
    boxSizing: "border-box",
  });
  const settingsStatus = el("div");
  settingsStatus.id = PANEL_IDS.settingsStatus;
  settingsStatus.style.color = "#8d93a1";
  settingsStatus.style.fontSize = "11px";
  const settingsGuidance = el("div");
  settingsGuidance.id = PANEL_IDS.settingsGuidance;
  settingsGuidance.style.whiteSpace = "pre-wrap";
  settingsGuidance.style.color = "#edf2f7";
  const settingsButtons = el("div");
  Object.assign(settingsButtons.style, {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
  });
  const settingsSave = button("Save Settings", () => saveAgentSettings(currentAgentPanel()));
  settingsSave.id = PANEL_IDS.settingsSave;
  const settingsTest = button("Test Provider", () => testAgentSettings(currentAgentPanel()));
  settingsTest.id = PANEL_IDS.settingsTest;
  routeSelect.onchange = () => {
    const panel = currentAgentPanel();
    if (panel) {
      panel.fields.route.value = normalizeRoutePreference(routeSelect.value);
      renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
      refreshAgentStatus(panel, { quiet: true });
    }
  };
  settingsButtons.appendChild(settingsSave);
  settingsButtons.appendChild(settingsTest);
  settingsRegion.body.appendChild(routeSelect);
  settingsRegion.body.appendChild(modelInput);
  settingsRegion.body.appendChild(apiKeyInput);
  settingsRegion.body.appendChild(settingsButtons);
  settingsRegion.body.appendChild(settingsStatus);
  settingsRegion.body.appendChild(settingsGuidance);
  settingsPopover.appendChild(settingsRegion.section);

  // ── Developer section inside settings popover ────────────────────────────
  const developerRegion = panelSection(PANEL_IDS.developerRegion, "Developer");
  developerRegion.section.style.border = "none";
  developerRegion.section.style.background = "transparent";
  developerRegion.section.style.padding = "0";
  developerRegion.section.style.marginTop = "12px";
  developerRegion.section.style.borderTop = "1px solid #34343a";
  developerRegion.section.style.paddingTop = "10px";
  settingsPopover.appendChild(developerRegion.section);

  // ── Assemble shell ──────────────────────────────────────────────────────
  shell.appendChild(header);
  shell.appendChild(metaRow);
  shell.appendChild(thread);
  shell.appendChild(composer);
  shell.appendChild(settingsPopover);
  root.appendChild(shell);

  return {
    panelId,
    root,
    shell,
    thread,
    metaRow,
    status,
    settingsPopover,
    fields: {
      prompt: textarea,
      route: routeSelect,
      model: modelInput,
      apiKey: apiKeyInput,
    },
    buttons: {
      submit: submitBtn,
      apply: applyBtn,
      reject: rejectBtn,
      undo: undoBtn,
      close: closeBtn,
      settingsSave,
      settingsTest,
      stop: stopBtn,
      newConversation: newConvBtn,
    },
    sections: {
      thread: threadRegion.body,
      chat: chatRegion.body,
      history: historyRegion.body,
      candidate: candidateRegion.body,
      failure: failureRegion.body,
      queue: queueRegion.body,
      audit: auditRegion.body,
      debug: debugRegion.body,
      developer: developerRegion.body,
      composerNotice,
    },
    composerButtons,
    pendingDirtySections: [],
    __renderErrors: [],
    __renderFailureCounts: {},
    state: {
      // Lifecycle-owned fields (authority: agent_edit_lifecycle.js)
      ...createAgentEditState(),
      // Non-lifecycle fields (read by store handlers but write-owned elsewhere)
      history: [],
      turns: [],
      undoStack: [],
      settingsMessage: null,
      statusSnapshot: null,
      statusRetry: null,
      statusRequestEpoch: 0,
      routeStatus: {
        kind: ROUTE_STATUS_KIND.LOADING,
        requestedRoute: "auto",
        model: null,
      },
      queueGuard: getQueueGuardStateForPanel(),
      previewEnabled: false,
      expandedTurnKeys: {},
      expandedBubbleTurnKeys: {},
      turnDetailSnapshots: {},
      // Chat / session rehydration state (M3)
      chatMessages: [],
      chatLoaded: false,
      chatError: null,
      chatSessionPath: null,
      chatDetailJsonPath: null,
      mountMode: AGENT_PANEL_MOUNT_MODE.LAUNCHER,
      mountContainer: null,
    },
  };
}

function createAgentPanel() {
  const panel = createAgentPanelShell();
  document.body.appendChild(panel.root);
  return panel;
}

function getPanelElementById(panel, id) {
  if (!id) {
    return null;
  }
  if (panel?.root?.querySelector) {
    const match = panel.root.querySelector(`#${id}`);
    if (match) {
      return match;
    }
  }
  if (panel?.root?.querySelectorAll) {
    try {
      const matches = panel.root.querySelectorAll((node) => node?.id === id);
      if (matches?.[0]) {
        return matches[0];
      }
    } catch (_error) {
      // Browser querySelectorAll expects a selector string; the function
      // predicate path is for the local smoke-test DOM shim.
    }
  }
  if (typeof document !== "undefined" && typeof document.getElementById === "function") {
    return document.getElementById(id);
  }
  return null;
}

function isAppendableElement(value) {
  return Boolean(value && typeof value.appendChild === "function");
}

function resolveAgentSidebarMountContainer(candidate) {
  if (isAppendableElement(candidate)) {
    return candidate;
  }
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  const directKeys = ["container", "element", "el", "root", "target", "mount", "$el"];
  for (const key of directKeys) {
    if (isAppendableElement(candidate[key])) {
      return candidate[key];
    }
  }
  for (const key of directKeys) {
    const nested = candidate[key];
    if (!nested || typeof nested !== "object") {
      continue;
    }
    for (const nestedKey of directKeys) {
      if (isAppendableElement(nested[nestedKey])) {
        return nested[nestedKey];
      }
    }
  }
  return null;
}

function applyAgentPanelMount(panel, { mode = AGENT_PANEL_MOUNT_MODE.LAUNCHER, container = null } = {}) {
  if (!panel?.root || typeof document === "undefined") {
    return null;
  }
  const sidebarContainer =
    mode === AGENT_PANEL_MOUNT_MODE.SIDEBAR
      ? resolveAgentSidebarMountContainer(container)
      : null;
  const target = sidebarContainer || document.body;
  if (target && panel.root.parentNode !== target) {
    target.appendChild(panel.root);
  }

  panel.state.mountMode = sidebarContainer
    ? AGENT_PANEL_MOUNT_MODE.SIDEBAR
    : AGENT_PANEL_MOUNT_MODE.LAUNCHER;
  panel.state.mountContainer = sidebarContainer;
  panel.root.dataset.mountMode = panel.state.mountMode;

  if (sidebarContainer) {
    // The ComfyUI sidebar content container is often height:auto, so
    // height:100% resolves to auto and the panel grows with the conversation
    // instead of scrolling internally (the outer sidebar then scrolls the
    // WHOLE panel, composer included). Pin the panel to the visible viewport
    // below the container's top edge so the thread wrapper scrolls.
    let boundedHeight = "100%";
    try {
      const rect = typeof sidebarContainer.getBoundingClientRect === "function"
        ? sidebarContainer.getBoundingClientRect()
        : null;
      const viewportH = typeof window !== "undefined" && Number.isFinite(window.innerHeight)
        ? window.innerHeight
        : 0;
      if (rect && viewportH > 0 && Number.isFinite(rect.top) && viewportH - rect.top >= 240) {
        boundedHeight = `${Math.round(viewportH - rect.top)}px`;
      }
    } catch (_e) {
      // keep 100%
    }
    Object.assign(panel.root.style, {
      position: "relative",
      inset: "auto",
      top: "auto",
      right: "auto",
      width: "100%",
      height: boundedHeight,
      maxHeight: boundedHeight,
      minHeight: "0",
      overflow: "hidden",
      zIndex: "auto",
      pointerEvents: "auto",
      transform: "none",
      transition: "none",
    });
    Object.assign(panel.shell.style, {
      borderLeft: "none",
      boxShadow: "none",
    });
  } else {
    Object.assign(panel.root.style, {
      position: "fixed",
      top: "0",
      right: "0",
      width: "420px",
      height: "100vh",
      minHeight: "",
      zIndex: "9999",
      pointerEvents: "none",
      transform: "translateX(432px)",
      transition: "transform 140ms ease",
    });
    Object.assign(panel.shell.style, {
      borderLeft: "1px solid #282a32",
      boxShadow: "-10px 0 28px rgba(0,0,0,0.38)",
    });
  }
  return target;
}

// ── Chat rehydration ──────────────────────────────────────────────────────
async function _rehydrateChat(panel) {
  if (!panel || !panel.state) {
    return;
  }
  const startObligations = transition(panel, "CHAT_REHYDRATE_START");
  fulfillLifecycleTransitionObligations(panel, startObligations);
  const requestEpoch = startObligations.requestEpoch;
  const savedId = _lsGet(LS_ACTIVE_SESSION_KEY);
  if (!savedId) {
    const noSessionObligations = transition(panel, "CHAT_REHYDRATE_NO_SESSION", { requestEpoch });
    fulfillAgentPanelCommitObligations(panel, noSessionObligations, "rehydrate");
    resetThreadRenderState(panel);
    return;
  }

  try {
    await nextMacrotask();
    const res = await fetch(`/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(savedId)}`);
    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }
    const rawPayload = await res.json();
    const payload = normalizeChatRehydratePayload(rawPayload);
    if (payload && payload.ok === true) {
      if (payload.exists === false) {
        const missingSessionObligations = transition(panel, "CHAT_REHYDRATE_MISSING_SESSION", {
          requestEpoch,
          sessionId: savedId,
        });
        fulfillAgentPanelCommitObligations(panel, missingSessionObligations, "rehydrate");
        resetThreadRenderState(panel);
        return;
      }
      const messages = Array.isArray(payload.messages) ? payload.messages : [];
      // Normalize field changes on each rehydrated message for chat-bubble rendering (M4b).
      for (const msg of messages) {
        if (msg && typeof msg === "object") {
          msg.field_changes = normalizeFieldChangesFromMessage(msg.raw || msg);
        }
      }
      const successObligations = transition(panel, "CHAT_REHYDRATE_SUCCESS", {
        requestEpoch,
        messages,
        chatSessionPath: payload.sessionPath,
        chatDetailJsonPath: payload.detailJsonPath,
        sessionId: payload.sessionId,
      });
      if (successObligations.stale) {
        return;
      }
      fulfillAgentPanelCommitObligations(panel, successObligations, "rehydrate");
      resetThreadRenderState(panel);
      renderAgentPanel(panel, { dirtySections: [RENDER_SECTIONS.META, RENDER_SECTIONS.THREAD] });
      restoreLatestCandidateFromChat(panel, payload);
    } else {
      throw new Error(payload.raw?.error || "chat endpoint returned ok: false");
    }
  } catch (_e) {
    const failureObligations = transition(panel, "CHAT_REHYDRATE_FAILURE", {
      requestEpoch,
      chatError: String(_e),
    });
    if (failureObligations.stale) {
      return;
    }
    fulfillAgentPanelCommitObligations(panel, failureObligations, "rehydrate");
    resetThreadRenderState(panel);
  }
}

function _persistActiveSession(sessionId) {
  if (typeof sessionId === "string" && sessionId) {
    _lsSet(LS_ACTIVE_SESSION_KEY, sessionId);
  }
}

function restoreLatestCandidateFromChat(panel, payload) {
  const latest = payload?.latestCandidate || null;
  if (!panel?.state || !latest || typeof latest !== "object") {
    return;
  }
  switch (latest.outcome?.kind || null) {
    case "candidate":
      break;
    case "noop":
    case "clarify":
    case "error":
    default:
      return;
  }
  const candidateGraph = latest.candidateGraph;
  if (!candidateGraph || typeof candidateGraph !== "object") {
    return;
  }
  const eligibility = latest.eligibility;
  const restoreObligations = transition(panel, "CHAT_REHYDRATE_RESTORE_LATEST_CANDIDATE", {
    sessionId: latest.sessionId || null,
    turnId: latest.turnId || null,
    baseline: latest,
    candidateGraph,
    candidateGraphHash: latest.candidateGraphHash || null,
    candidateReport: latest.report && typeof latest.report === "object" ? clonePlainData(latest.report) : null,
    serverSubmitGraphHash: latest.submitGraphHash || null,
    message: typeof latest.message === "string" ? latest.message : null,
    applyEligibility: normalizeApplyEligibility(eligibility),
    applyAllowed: latest.applyAllowed !== false && latest.canvasApplyAllowed !== false,
    canvasApplyAllowed: Boolean(latest.canvasApplyAllowed),
    queueAllowed: Boolean(latest.queueAllowed),
    auditRef: latest.auditRef || panel.state.auditRef || null,
    changeDetails: latest.raw?.change_details && typeof latest.raw.change_details === "object"
      ? clonePlainData(latest.raw.change_details)
      : null,
    debugPayload: scrubDebugPayload({
      ...(latest.raw || latest),
      restored_from_chat: true,
    }),
    lastSubmitFieldChanges: normalizeFieldChangesFromSubmit(latest.raw || latest),
  });
  if (!restoreObligations.restored) {
    return;
  }
  fulfillAgentPanelCommitObligations(panel, restoreObligations, "rehydrate");
  reconcileResponseBatchTurns(panel, latest);
  rememberTurnDetailSnapshot(panel, {
    turn_id: panel.state.turnId,
    session_id: panel.state.sessionId,
    candidateGraphPresent: true,
    candidateReport: panel.state.candidateReport,
    applyEligibility: panel.state.applyEligibility,
    queueAllowed: panel.state.queueAllowed,
    canvasApplyAllowed: panel.state.canvasApplyAllowed,
    auditRef: panel.state.auditRef,
    debugPayload: panel.state.debugPayload,
    fieldChanges: panel.state.lastSubmitFieldChanges,
    changeDetails: panel.state.changeDetails,
    message: panel.state.message,
  });
}

function forgetActiveSession() {
  _lsRemove(LS_ACTIVE_SESSION_KEY);
}

function normalizeDirtySectionList(sections) {
  if (sections === undefined) {
    return undefined;
  }
  if (sections == null) {
    return [];
  }
  const normalized = normalizeObligationDirtySections({
    render: false,
    dirtySections: sections,
  });
  return Array.isArray(normalized?.dirtySections) ? normalized.dirtySections : [];
}

function agentPanelPendingDirtySections(panel) {
  if (!panel) {
    return [];
  }
  if (!Array.isArray(panel.pendingDirtySections)) {
    panel.pendingDirtySections = [];
  }
  return panel.pendingDirtySections;
}

function isAgentPanelRootConnected(panel) {
  if (typeof document === "undefined") {
    return false;
  }
  return Boolean(panel?.root?.isConnected);
}

function hasPendingAgentPanelFlush() {
  return Boolean(_scheduledAgentPanelRenderQueued || _scheduledAgentPanelRender);
}

function noteAgentPanelCommit(panel, commitKind) {
  const at = new Date().toISOString();
  if (commitKind === "status") {
    _statusCommitAt = at;
    if (panel?.state) {
      panel.state.statusCommitAt = at;
    }
  } else if (commitKind === "rehydrate") {
    _rehydrateCommitAt = at;
    if (panel?.state) {
      panel.state.rehydrateCommitAt = at;
    }
  }
  return at;
}

function markAgentPanelDirtyAfterCommit(panel, sections, commitKind) {
  if (!panel) {
    return [];
  }
  noteAgentPanelCommit(panel, commitKind);
  const normalized = normalizeDirtySectionList(sections);
  if (Array.isArray(normalized) && normalized.length) {
    _marksAfterCommit += 1;
    if (panel.state) {
      panel.state.marksAfterCommit = _marksAfterCommit;
    }
  }
  return markAgentPanelDirty(panel, normalized);
}

function fulfillAgentPanelCommitObligations(panel, obligations = {}, commitKind) {
  if (Array.isArray(obligations?.dirtySections) && obligations.dirtySections.length) {
    markAgentPanelDirtyAfterCommit(panel, obligations.dirtySections, commitKind);
    fulfillLifecycleTransitionObligations(panel, {
      ...obligations,
      dirtySections: [],
    });
    return;
  }
  noteAgentPanelCommit(panel, commitKind);
  fulfillLifecycleTransitionObligations(panel, obligations);
}

function ensureScheduledAgentPanelDirtyFlush(panel, reason = "dirty-sections") {
  if (
    panel
    && agentPanelPendingDirtySections(panel).length
    && !hasPendingAgentPanelFlush()
    && isAgentPanelRootConnected(panel)
  ) {
    scheduleRenderAgentPanel(reason, panel, undefined, { dirtyOnly: true });
  }
}

export function markAgentPanelDirty(panel, sections, options = {}) {
  if (!panel) {
    return [];
  }
  const nextSections = normalizeDirtySectionList(sections);
  if (!Array.isArray(nextSections) || !nextSections.length) {
    return agentPanelPendingDirtySections(panel);
  }
  const pending = agentPanelPendingDirtySections(panel);
  const seen = new Set(pending);
  for (const section of nextSections) {
    if (!seen.has(section)) {
      pending.push(section);
      seen.add(section);
    }
  }
  if (options.schedule !== false && isAgentPanelRootConnected(panel)) {
    scheduleRenderAgentPanel("dirty-sections", panel, undefined, { dirtyOnly: true });
  }
  return pending;
}

export function markAllAgentPanelDirty(panel) {
  return markAgentPanelDirty(panel, ALL_AGENT_PANEL_RENDER_SECTIONS);
}

export function consumeAgentPanelDirtySections(panel, fallbackSections = ALL_AGENT_PANEL_RENDER_SECTIONS) {
  if (!panel) {
    return [];
  }
  const pending = agentPanelPendingDirtySections(panel).slice();
  panel.pendingDirtySections = [];
  const fallback = normalizeDirtySectionList(fallbackSections);
  if (!pending.length && (!Array.isArray(fallback) || !fallback.length)) {
    return ALL_AGENT_PANEL_RENDER_SECTIONS.slice();
  }
  return normalizeDirtySectionList([
    ...pending,
    ...(Array.isArray(fallback) ? fallback : []),
  ]) || [];
}

function rerenderAgentPanelIfMounted(panel = currentAgentPanel()) {
  if (!panel?.root) {
    return;
  }
  if (!isAgentPanelRootConnected(panel)) {
    return;
  }
  renderDirtyAgentPanelSections(panel);
}

export function scheduleRenderAgentPanel(reason = "scheduled", panel = currentAgentPanel(), fallbackSections = undefined, options = {}) {
  if (!isAgentPanelRootConnected(panel)) {
    return;
  }
  if (fallbackSections !== undefined) {
    markAgentPanelDirty(panel, fallbackSections, { schedule: false });
  }
  _scheduledAgentPanelRender = {
    panel,
    reason,
    fallbackSections,
    dirtyOnly: Boolean(options.dirtyOnly),
  };
  const flush = () => {
    const scheduled = _scheduledAgentPanelRender;
    _scheduledAgentPanelRender = null;
    _scheduledAgentPanelRenderQueued = false;
    _agentPanelFlushCount += 1;
    _lastAgentPanelFlushReason = typeof scheduled?.reason === "string" ? scheduled.reason : "";
    if (isAgentPanelRootConnected(scheduled?.panel)) {
      if (
        scheduled.dirtyOnly
        && scheduled.fallbackSections === undefined
        && !agentPanelPendingDirtySections(scheduled.panel).length
      ) {
        return;
      }
      renderDirtyAgentPanelSections(scheduled.panel, {
        render: true,
        dirtySections: scheduled.fallbackSections,
      });
    }
  };
  if (_scheduledAgentPanelRenderQueued) {
    return;
  }
  _scheduledAgentPanelRenderQueued = true;
  let flushed = false;
  let timeoutId = null;
  const flushOnce = () => {
    if (flushed) {
      return;
    }
    flushed = true;
    if (timeoutId !== null && typeof clearTimeout === "function") {
      clearTimeout(timeoutId);
    }
    flush();
  };
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(flushOnce);
    if (typeof setTimeout === "function") {
      timeoutId = setTimeout(flushOnce, AGENT_PANEL_RENDER_TIMEOUT_MS);
    }
  } else if (typeof queueMicrotask === "function") {
    queueMicrotask(flushOnce);
  } else if (typeof Promise !== "undefined") {
    Promise.resolve().then(flushOnce);
  } else if (typeof setTimeout === "function") {
    timeoutId = setTimeout(flushOnce, 0);
  } else {
    flushOnce();
  }
}

export function ensureAgentPanel() {
  const existingPanel = currentAgentPanel();
  if (existingPanel) {
    return existingPanel;
  }
  if (!agentPanel) {
    // Create the panel shell only. Chat rehydration happens on open
    // (openAgentPanel), not on mere creation, so extension setup and launcher
    // wiring don't trigger a premature/duplicate chat fetch.
    setCurrentAgentPanel(createAgentPanel());
  }
  return currentAgentPanel();
}

export function debugAgentPanelSnapshot(panel = currentAgentPanel()) {
  return buildAgentPanelDebugSnapshot(panel);
}

function openAgentPanel({ mode = AGENT_PANEL_MOUNT_MODE.LAUNCHER, container = null } = {}) {
  const panel = ensureAgentPanel();
  applyAgentPanelMount(panel, { mode, container });
  panel.root.dataset.open = "1";
  panel.root.style.pointerEvents = "auto";
  panel.root.style.transform = "translateX(0)";
  panel.state.queueGuard = getQueueGuardStateForPanel();
  // Rehydrate chat on open (best-effort) — exactly one fetch per open.
  // Creation (ensureAgentPanel) intentionally does not fetch, so this single
  // call covers both first open and reopen.
  _rehydrateChat(panel).then(() => {
    scheduleRenderAgentPanel("rehydrate", panel);
  }).catch((err) => {
    console.warn("[vibecomfy] chat rehydration render failed", err);
  });
  renderAgentPanel(panel);
  refreshAgentStatus(panel, { quiet: true });
  ensureScheduledAgentPanelDirtyFlush(panel, "open-backstop");
  return panel;
}

function mountAgentSidebarPanel(container = null) {
  const panel = openAgentPanel({
    mode: AGENT_PANEL_MOUNT_MODE.SIDEBAR,
    container,
  });
  panel.root.dataset.lastCommand = "agent-sidebar";
  renderAgentPanel(panel);
  return panel.root;
}

function closeAgentPanel(panel) {
  panel.root.dataset.open = "0";
  panel.root.style.pointerEvents = "none";
  panel.root.style.transform = "translateX(432px)";
}

function option(value, label, ownerDocument = null) {
  const doc = ownerDocument || (typeof document !== "undefined" ? document : null);
  if (!doc) {
    throw new ReferenceError("document is not defined");
  }
  const node = doc.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

function pushHistory(panel, kind, message) {
  panel.state.history.unshift({
    kind,
    message,
    at: new Date().toISOString(),
  });
  panel.state.history = panel.state.history.slice(0, 8);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
}

const PANEL_TURN_LIMIT = 64;
const BATCH_SOURCE_PRIORITY = {
  websocket: 1,
  response: 2,
};
const BATCH_TERMINAL_STATUSES = new Set(["clarify", "done", "budget_exhausted"]);

function stableTurnSessionId(value) {
  return typeof value === "string" && value ? value : "none";
}

function batchTurnKey(sessionId, turnNumber) {
  return `batch:${stableTurnSessionId(sessionId)}:${turnNumber}`;
}

function durableTurnKey(entry) {
  const sessionId = stableTurnSessionId(entry?.session_id);
  const status = entry?.status || "unknown";
  if (entry?.turn_id) {
    return `durable:${sessionId}:${entry.turn_id}:${status}`;
  }
  const fallback =
    entry?.timestamp
    || entry?.message
    || entry?.task
    || entry?.failure_kind
    || "pending";
  return `durable:${sessionId}:${status}:${fallback}`;
}

function sortPanelTurns(turns) {
  const durable = [];
  const batch = [];
  const other = [];
  for (const entry of Array.isArray(turns) ? turns : []) {
    if (entry?.entry_type === "durable") {
      durable.push(entry);
    } else if (entry?.entry_type === "batch") {
      batch.push(entry);
    } else {
      other.push(entry);
    }
  }
  batch.sort((left, right) => {
    const leftNumber = Number.isFinite(left?.turn_number) ? left.turn_number : -1;
    const rightNumber = Number.isFinite(right?.turn_number) ? right.turn_number : -1;
    return rightNumber - leftNumber;
  });
  return [...durable, ...batch, ...other].slice(0, PANEL_TURN_LIMIT);
}

function pushTurnStatus(panel, status, extra = {}) {
  const entry = {
    entry_type: "durable",
    status,
    session_id: extra.session_id || panel.state.sessionId || null,
    turn_id: extra.turn_id || panel.state.turnId || null,
    baseline_turn_id: extra.baseline_turn_id || panel.state.baselineTurnId || null,
    task: extra.task || (panel.state.lastSubmit?.task) || null,
    timestamp: new Date().toISOString(),
    failure_kind: extra.failure_kind || null,
    failure_stage: extra.failure_stage || null,
    message: extra.message || null,
    audit_ref: extra.audit_ref || null,
    raw_payload: extra.raw_payload || null,
  };
  entry.turn_key = durableTurnKey(entry);
  if (status !== "pending") {
    panel.state.turns = Array.isArray(panel.state.turns)
      ? panel.state.turns.filter((existing) => !(existing?.entry_type === "durable" && existing.status === "pending"))
      : [];
  }
  panel.state.turns.unshift(entry);
  panel.state.turns = sortPanelTurns(panel.state.turns);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
  return entry;
}

function outcomeRequiresClarification(outcome) {
  if (!outcome || typeof outcome !== "object") {
    return false;
  }
  return outcome.kind === "clarify";
}

function outcomeIsNoop(outcome) {
  return Boolean(outcome && typeof outcome === "object" && outcome.kind === "noop");
}

function clarificationMessageFromOutcome(outcome, fallbackMessage = null) {
  if (!outcome || typeof outcome !== "object") {
    return fallbackMessage;
  }
  if (typeof outcome.question === "string" && outcome.question.trim()) {
    return outcome.question.trim();
  }
  return fallbackMessage;
}

function outcomeHasClarificationPrompt(outcome) {
  return typeof clarificationMessageFromOutcome(outcome) === "string";
}

function normalizeChatMessagePayload(message) {
  if (!message || typeof message !== "object") {
    return message;
  }
  const response = message.response && typeof message.response === "object"
    ? normalizeAgentEditResponse(message.response, {
      endpoint: "chat:message-response",
      allowLegacy: true,
    })
    : null;
  const outcome = message.outcome && typeof message.outcome === "object"
    ? normalizeAgentEditResponse(
      {
        ...message,
        outcome: message.outcome,
      },
      {
        endpoint: "chat:message-outcome",
        allowLegacy: true,
      },
    ).outcome
    : response?.outcome || null;
  const candidateGraph = message.candidateGraph
    || message.candidate?.graph
    || message.candidate_graph
    || message.graph
    || response?.candidateGraph
    || null;
  const eligibility = message.eligibility
    || message.apply_eligibility
    || response?.eligibility
    || null;
  return {
    ...message,
    raw: message,
    role: typeof message.role === "string" ? message.role : null,
    text: typeof message.text === "string" ? message.text : null,
    turnId: typeof message.turnId === "string" ? message.turnId : (typeof message.turn_id === "string" ? message.turn_id : null),
    sessionId: typeof message.sessionId === "string" ? message.sessionId : (typeof message.session_id === "string" ? message.session_id : null),
    entryType: typeof message.entryType === "string" ? message.entryType : (typeof message.entry_type === "string" ? message.entry_type : null),
    timestamp: typeof message.timestamp === "string" ? message.timestamp : null,
    response,
    outcome,
    candidateGraph,
    eligibility,
  };
}

function normalizeChatRehydratePayload(rawPayload) {
  if (!rawPayload || typeof rawPayload !== "object") {
    throw new Error("chat endpoint must return an object");
  }
  return {
    ...rawPayload,
    raw: rawPayload,
    ok: typeof rawPayload.ok === "boolean" ? rawPayload.ok : null,
    exists: typeof rawPayload.exists === "boolean" ? rawPayload.exists : null,
    sessionId: typeof rawPayload.sessionId === "string"
      ? rawPayload.sessionId
      : (typeof rawPayload.session_id === "string" ? rawPayload.session_id : null),
    sessionPath: typeof rawPayload.sessionPath === "string"
      ? rawPayload.sessionPath
      : (typeof rawPayload.session_path === "string" ? rawPayload.session_path : null),
    detailJsonPath: typeof rawPayload.detailJsonPath === "string"
      ? rawPayload.detailJsonPath
      : (typeof rawPayload.detail_json_path === "string" ? rawPayload.detail_json_path : null),
    latestCandidate:
      rawPayload.latestCandidate && typeof rawPayload.latestCandidate === "object"
        ? normalizeAgentEditResponse(rawPayload.latestCandidate, { endpoint: "chat:latest_candidate", allowLegacy: true })
        : (rawPayload.latest_candidate && typeof rawPayload.latest_candidate === "object"
          ? normalizeAgentEditResponse(rawPayload.latest_candidate, { endpoint: "chat:latest_candidate", allowLegacy: true })
          : null),
    messages: Array.isArray(rawPayload.messages)
      ? rawPayload.messages.map((message) => normalizeChatMessagePayload(message))
      : [],
  };
}

function normalizeAuxiliaryAgentPayload(rawPayload, endpoint) {
  if (!rawPayload || typeof rawPayload !== "object") {
    throw new Error(`${endpoint} response must be an object`);
  }
  const looksLikeOutcomeEnvelope =
    (rawPayload.outcome && typeof rawPayload.outcome === "object")
    || (rawPayload.candidate && typeof rawPayload.candidate === "object")
    || (rawPayload.graph && typeof rawPayload.graph === "object")
    || rawPayload.clarification_required === true
    || rawPayload.graph_unchanged === true;
  if (looksLikeOutcomeEnvelope) {
    return normalizeAgentEditResponse(rawPayload, { endpoint, allowLegacy: true });
  }
  return {
    ...rawPayload,
    raw: rawPayload,
    ok: typeof rawPayload.ok === "boolean" ? rawPayload.ok : null,
    action: typeof rawPayload.action === "string" ? rawPayload.action : null,
    message: typeof rawPayload.message === "string" ? rawPayload.message : null,
    sessionId: typeof rawPayload.sessionId === "string"
      ? rawPayload.sessionId
      : (typeof rawPayload.session_id === "string" ? rawPayload.session_id : null),
    turnId: typeof rawPayload.turnId === "string"
      ? rawPayload.turnId
      : (typeof rawPayload.turn_id === "string" ? rawPayload.turn_id : null),
    baselineTurnId: typeof rawPayload.baselineTurnId === "string"
      ? rawPayload.baselineTurnId
      : (typeof rawPayload.baseline_turn_id === "string" ? rawPayload.baseline_turn_id : null),
    baselineGraphHash: typeof rawPayload.baselineGraphHash === "string"
      ? rawPayload.baselineGraphHash
      : (typeof rawPayload.baseline_graph_hash === "string" ? rawPayload.baseline_graph_hash : null),
    baselineGraphHashKind: typeof rawPayload.baselineGraphHashKind === "string"
      ? rawPayload.baselineGraphHashKind
      : (typeof rawPayload.baseline_graph_hash_kind === "string" ? rawPayload.baseline_graph_hash_kind : null),
    baselineGraphHashVersion:
      rawPayload.baselineGraphHashVersion ?? rawPayload.baseline_graph_hash_version ?? null,
    baselineSource: typeof rawPayload.baselineSource === "string"
      ? rawPayload.baselineSource
      : (typeof rawPayload.baseline_source === "string" ? rawPayload.baseline_source : null),
    baselineRebaselineId: typeof rawPayload.baselineRebaselineId === "string"
      ? rawPayload.baselineRebaselineId
      : (typeof rawPayload.baseline_rebaseline_id === "string" ? rawPayload.baseline_rebaseline_id : null),
    baselineGraphSourcePath: typeof rawPayload.baselineGraphSourcePath === "string"
      ? rawPayload.baselineGraphSourcePath
      : (typeof rawPayload.baseline_graph_source_path === "string" ? rawPayload.baseline_graph_source_path : null),
    submitGraphHash: typeof rawPayload.submitGraphHash === "string"
      ? rawPayload.submitGraphHash
      : (typeof rawPayload.submit_graph_hash === "string" ? rawPayload.submit_graph_hash : null),
    queueAllowed:
      typeof rawPayload.queueAllowed === "boolean"
        ? rawPayload.queueAllowed
        : (typeof rawPayload.queue_allowed === "boolean" ? rawPayload.queue_allowed : null),
    auditRef: rawPayload.auditRef && typeof rawPayload.auditRef === "object"
      ? clonePlainData(rawPayload.auditRef)
      : (rawPayload.audit_ref && typeof rawPayload.audit_ref === "object" ? clonePlainData(rawPayload.audit_ref) : null),
    rebaselineRecovery: extractRebaselineRecovery(rawPayload),
  };
}

// ── FieldChange normalization helpers ─────────────────────────────────────
// Normalize FieldChange objects without positional widget inference.
// A FieldChange has the canonical shape: { uid, field_path, old, new }
// These helpers extract and validate FieldChange arrays from submit responses
// and rehydrate chat messages, storing results on panel state and per-message
// detail for later chat-bubble rendering (M4b).

function _isFieldChangeLike(item) {
  return item && typeof item === "object"
    && typeof item.uid === "string" && item.uid
    && typeof item.field_path === "string" && item.field_path;
}

function _normalizeFieldChange(raw) {
  if (!raw || typeof raw !== "object") return null;
  if (!_isFieldChangeLike(raw)) return null;
  return {
    uid: raw.uid,
    field_path: raw.field_path,
    old: "old" in raw ? raw.old : undefined,
    new: "new" in raw ? raw.new : undefined,
  };
}

function _normalizeFieldChangeList(rawList) {
  if (!Array.isArray(rawList)) return [];
  const result = [];
  for (const raw of rawList) {
    const normalized = _normalizeFieldChange(raw);
    if (normalized) result.push(normalized);
  }
  return result;
}

// Read field changes from a submit response: outcome.changes and
// batch_turns[].field_changes. Returns normalized arrays without
// positional widget inference.
function normalizeFieldChangesFromSubmit(result) {
  if (!result || typeof result !== "object") {
    return { outcomeChanges: [], batchTurnChanges: [] };
  }

  const outcomeChanges = _normalizeFieldChangeList(
    result.outcome && typeof result.outcome === "object" ? result.outcome.changes : null,
  );

  const batchTurnChanges = [];
  if (Array.isArray(result.batch_turns)) {
    for (const turn of result.batch_turns) {
      if (turn && typeof turn === "object") {
        const turnNumber = typeof turn.turn_number === "number" ? turn.turn_number : null;
        const changes = _normalizeFieldChangeList(turn.field_changes);
        batchTurnChanges.push({ turn_number: turnNumber, changes });
      }
    }
  }

  return { outcomeChanges, batchTurnChanges };
}

// Read field changes from a rehydrate chat message and its nested
// canonical detail (message.changes, message.outcome?.changes).
function normalizeFieldChangesFromMessage(message) {
  if (!message || typeof message !== "object") {
    return { directChanges: [], outcomeChanges: [] };
  }

  const directChanges = _normalizeFieldChangeList(message.changes);

  const outcomeChanges = _normalizeFieldChangeList(
    message.outcome && typeof message.outcome === "object" ? message.outcome.changes : null,
  );

  return { directChanges, outcomeChanges };
}

function changeDetailsForMessage(panel, message, snapshot = null) {
  if (message?.change_details && typeof message.change_details === "object") {
    return message.change_details;
  }
  if (snapshot?.changeDetails && typeof snapshot.changeDetails === "object") {
    return snapshot.changeDetails;
  }
  return panel?.state?.changeDetails || null;
}

function normalizeBatchTurn(payload, { source = "response", sessionId = null, status = null, parentTurnId = null } = {}) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const resolvedSessionId =
    typeof payload.session_id === "string" && payload.session_id
      ? payload.session_id
      : (typeof sessionId === "string" && sessionId ? sessionId : null);
  const rawTurnNumber = payload.turn_number;
  const turnNumber =
    Number.isInteger(rawTurnNumber)
      ? rawTurnNumber
      : (typeof rawTurnNumber === "number" && Number.isFinite(rawTurnNumber)
        ? Math.trunc(rawTurnNumber)
        : null);
  if (!resolvedSessionId || turnNumber == null) {
    return null;
  }
  const outcome = payload.outcome && typeof payload.outcome === "object" ? payload.outcome : null;
  const normalizedStatus =
    status
    || (typeof payload.status === "string" && payload.status)
    || (outcomeRequiresClarification(outcome) ? "clarify" : "in_progress");
  const clarificationMessage = clarificationMessageFromOutcome(outcome);
  return {
    entry_type: "batch",
    turn_key: batchTurnKey(resolvedSessionId, turnNumber),
    session_id: resolvedSessionId,
    turn_id: typeof payload.turn_id === "string" && payload.turn_id ? payload.turn_id : null,
    parent_turn_id:
      typeof payload.parent_turn_id === "string" && payload.parent_turn_id
        ? payload.parent_turn_id
        : (typeof parentTurnId === "string" && parentTurnId ? parentTurnId : null),
    turn_number: turnNumber,
    status: normalizedStatus,
    message: typeof payload.message === "string" ? payload.message : null,
    timestamp: typeof payload.timestamp === "string" ? payload.timestamp : null,
    clarification_required: outcomeRequiresClarification(outcome),
    clarification_message: clarificationMessage,
    batch_ok: typeof payload.batch_ok === "boolean" ? payload.batch_ok : null,
    statement_count:
      typeof payload.statement_count === "number" && Number.isFinite(payload.statement_count)
        ? payload.statement_count
        : null,
    landed_op_count:
      typeof payload.landed_op_count === "number" && Number.isFinite(payload.landed_op_count)
        ? payload.landed_op_count
        : null,
    statements: Array.isArray(payload.statements) ? payload.statements : null,
    diagnostics: Array.isArray(payload.diagnostics) ? payload.diagnostics : null,
    budget: payload.budget && typeof payload.budget === "object" ? payload.budget : null,
    exit_mode: typeof payload.exit_mode === "string" ? payload.exit_mode : null,
    done_summary: typeof payload.done_summary === "string" ? payload.done_summary : null,
    audit_ref: payload.audit_ref && typeof payload.audit_ref === "object" ? payload.audit_ref : null,
    raw_payload: source === "response" ? payload : null,
    source,
    source_priority: BATCH_SOURCE_PRIORITY[source] || 0,
  };
}

function mergeBatchTurnEntry(existing, incoming) {
  if (!existing) {
    return incoming;
  }
  const existingPriority = existing.source_priority || 0;
  const incomingPriority = incoming.source_priority || 0;
  const keepExistingStatus =
    existingPriority > incomingPriority
    && BATCH_TERMINAL_STATUSES.has(existing.status)
    && !BATCH_TERMINAL_STATUSES.has(incoming.status);
  return {
    ...existing,
    ...incoming,
    status: keepExistingStatus ? existing.status : incoming.status,
    statements:
      Array.isArray(incoming.statements) && incoming.statements.length
        ? incoming.statements
        : (Array.isArray(existing.statements) ? existing.statements : null),
    diagnostics:
      Array.isArray(incoming.diagnostics) && incoming.diagnostics.length
        ? incoming.diagnostics
        : (Array.isArray(existing.diagnostics) ? existing.diagnostics : null),
    budget:
      incoming.budget && typeof incoming.budget === "object"
        ? incoming.budget
        : (existing.budget && typeof existing.budget === "object" ? existing.budget : null),
    raw_payload: incoming.raw_payload || existing.raw_payload || null,
    source_priority: Math.max(existingPriority, incomingPriority),
  };
}

function captureExpandedTurnKeys(panel) {
  if (!panel?.state || !panel.state.expandedTurnKeys || typeof panel.state.expandedTurnKeys !== "object") {
    return {};
  }
  return { ...panel.state.expandedTurnKeys };
}

function restoreExpandedTurnKeys(panel, previous) {
  if (!panel?.state) {
    return;
  }
  const restored = {};
  for (const entry of panel.state.turns) {
    const turnKey = entry?.turn_key;
    if (turnKey && previous?.[turnKey]) {
      restored[turnKey] = true;
    }
  }
  panel.state.expandedTurnKeys = restored;
}

function rememberTurnDetailSnapshot(panel, detail = {}) {
  if (!panel?.state) {
    return null;
  }
  const turnId =
    typeof detail.turn_id === "string" && detail.turn_id
      ? detail.turn_id
      : (typeof panel.state.turnId === "string" && panel.state.turnId ? panel.state.turnId : null);
  if (!turnId) {
    return null;
  }
  if (!panel.state.turnDetailSnapshots || typeof panel.state.turnDetailSnapshots !== "object") {
    panel.state.turnDetailSnapshots = {};
  }
  const snapshot = {
    turn_id: turnId,
    session_id:
      typeof detail.session_id === "string" && detail.session_id
        ? detail.session_id
        : (typeof panel.state.sessionId === "string" && panel.state.sessionId ? panel.state.sessionId : null),
    phase: detail.phase || panel.state.phase,
    message:
      detail.message
      || panel.state.message
      || panel.state.clarification?.message
      || panel.state.failure?.user_facing_message
      || panel.state.failure?.message
      || panel.state.failure?.error
      || null,
    clarification: clonePlainData(detail.clarification ?? panel.state.clarification ?? null),
    failure: clonePlainData(detail.failure ?? panel.state.failure ?? null),
    candidateGraphPresent: Boolean(detail.candidateGraphPresent ?? panel.state.candidateGraph),
    candidateReport: clonePlainData(detail.candidateReport ?? panel.state.candidateReport ?? null),
    applyEligibility: clonePlainData(detail.applyEligibility ?? panel.state.applyEligibility ?? null),
    queueAllowed: detail.queueAllowed ?? panel.state.queueAllowed,
    canvasApplyAllowed: detail.canvasApplyAllowed ?? panel.state.canvasApplyAllowed,
    auditRef: clonePlainData(detail.auditRef ?? panel.state.auditRef ?? null),
    debugPayload: clonePlainData(detail.debugPayload ?? panel.state.debugPayload ?? null),
    queueGuard: clonePlainData(detail.queueGuard ?? panel.state.queueGuard ?? getQueueGuardStateForPanel()),
    fieldChanges: clonePlainData(detail.fieldChanges ?? panel.state.lastSubmitFieldChanges ?? null),
    changeDetails: clonePlainData(detail.changeDetails ?? panel.state.changeDetails ?? null),
    lastAppliedChanges: clonePlainData(detail.lastAppliedChanges ?? panel.state.lastAppliedChanges ?? null),
  };
  panel.state.turnDetailSnapshots[turnId] = snapshot;
  return snapshot;
}

function detailSnapshotForMessage(panel, message) {
  const turnId =
    typeof message?.turn_id === "string" && message.turn_id
      ? message.turn_id
      : (typeof message?.detail_turn_id === "string" && message.detail_turn_id ? message.detail_turn_id : null);
  if (!turnId) {
    return null;
  }
  return panel?.state?.turnDetailSnapshots?.[turnId] || null;
}

// ── Chat message identity and thread render-state helpers (T10) ─────────

/**
 * Compute a stable key for a chat message used for thread reconciliation.
 *
 * Priority:
 *   1. turn_id + role       → `turn:<turn_id>:<role>`
 *   2. local_id             → `local:<local_id>`
 *   3. synthetic flag       → `synthetic:<index>`
 *   4. Legacy index fallback → `legacy:<index>:<role>:<text-prefix>`
 *
 * The index fallback is intentionally temporary — it is only stable for the
 * current array snapshot and must not be treated as durable across mutations.
 */
export function messageStableKey(msg, index = 0) {
  if (!msg || typeof msg !== "object") {
    return `empty:${index}`;
  }
  const turnId = typeof msg.turn_id === "string" && msg.turn_id ? msg.turn_id : null;
  const role = typeof msg.role === "string" && msg.role ? msg.role : null;
  if (turnId && role) {
    return `turn:${turnId}:${role}`;
  }
  const localId = typeof msg.local_id === "string" && msg.local_id ? msg.local_id : null;
  if (localId) {
    return `local:${localId}`;
  }
  if (msg.synthetic === true) {
    return `synthetic:${index}`;
  }
  // Legacy fallback — only stable for the current array snapshot.
  const textSlice = typeof msg.text === "string" ? msg.text.slice(0, 40) : "";
  return `legacy:${index}:${role || "unknown"}:${textSlice}`;
}

/**
 * Lightweight content signature for a chat message.
 * Used to detect content changes without deep comparison during reconciliation.
 */
export function messageSignature(msg) {
  if (!msg || typeof msg !== "object") {
    return "empty";
  }
  const parts = [
    msg.role || "",
    String(msg.text || "").slice(0, 200),
    msg.turn_id || "",
    msg.synthetic ? "1" : "0",
    msg.local_id || "",
  ];
  return parts.join("|");
}

/**
 * Reset the thread render state stored on the panel object.
 *
 * Call this whenever chatMessages is replaced wholesale — new conversation,
 * rehydrate success/replacement, or any full thread reset path.
 */
export function resetThreadRenderState(panel) {
  if (!panel) {
    return;
  }
  panel.threadState = {
    renderedKeyOrder: [],
    bubbleMap: {},
    expandedOlder: false,
    forceScrollOnNextRender: true,
    signatures: {},
    lastVisibleKeySet: null,
    bubbleDetailSignatures: {},
  };
}

// ── End T10 helpers ──────────────────────────────────────────────────────

function buildSyntheticAgentMessage(panel) {
  if (!panel?.state) {
    return null;
  }
  if (panel.state.syntheticAgentMessage && typeof panel.state.syntheticAgentMessage === "object") {
    const synthetic = panel.state.syntheticAgentMessage;
    const text = typeof synthetic.text === "string" ? synthetic.text : "";
    const turnId =
      typeof synthetic.turn_id === "string" && synthetic.turn_id
        ? synthetic.turn_id
        : (typeof synthetic.detail_turn_id === "string" && synthetic.detail_turn_id ? synthetic.detail_turn_id : null);
    const alreadyInThread = Array.isArray(panel.state.chatMessages)
      ? panel.state.chatMessages.some((msg) => (
          msg?.role === "agent"
          && typeof msg.text === "string"
          && msg.text === text
          && (!turnId || msg.turn_id === turnId)
        ))
      : false;
    return alreadyInThread ? null : synthetic;
  }
  const turnId = typeof panel.state.turnId === "string" && panel.state.turnId ? panel.state.turnId : null;
  if (!turnId) {
    return null;
  }
  const existing = Array.isArray(panel.state.chatMessages)
    ? panel.state.chatMessages.some((msg) => msg?.role === "agent" && msg?.turn_id === turnId)
    : false;
  if (existing) {
    return null;
  }
  const text =
    panel.state.message
    || panel.state.clarification?.message
    || panel.state.failure?.user_facing_message
    || panel.state.failure?.message
    || panel.state.failure?.error
    || null;
  if (!text) {
    return null;
  }
  return {
    role: "agent",
    text,
    turn_id: turnId,
    session_id: panel.state.sessionId || null,
    synthetic: true,
  };
}

function syntheticFailureAgentMessage(panel, failure, fallbackStage = "frontend") {
  if (!failure || typeof failure !== "object") {
    return null;
  }
  const text = failure.user_facing_message || failure.message || failure.error || null;
  if (!text) {
    return null;
  }
  const detailTurnId =
    typeof failure.turn_id === "string" && failure.turn_id
      ? failure.turn_id
      : (typeof panel?.state?.turnId === "string" && panel.state.turnId ? panel.state.turnId : null);
  const stage = failure.stage || fallbackStage || "frontend";
  const kind = failure.kind || "Error";
  return {
    role: "agent",
    text,
    detail_turn_id: detailTurnId,
    session_id: failure.session_id || panel?.state?.sessionId || null,
    synthetic: true,
    failure_kind: kind,
    failure_stage: stage,
    local_id: `failure:${detailTurnId || "local"}:${kind}:${stage}`,
  };
}

function upsertBatchTurn(panel, payload, options = {}) {
  if (!panel || !panel.state) {
    return null;
  }
  const previousExpanded = captureExpandedTurnKeys(panel);
  const normalized = normalizeBatchTurn(payload, options);
  if (!normalized) {
    return null;
  }
  const existingIndex = panel.state.turns.findIndex(
    (entry) => entry?.entry_type === "batch" && entry.turn_key === normalized.turn_key,
  );
  if (existingIndex >= 0) {
    panel.state.turns[existingIndex] = mergeBatchTurnEntry(panel.state.turns[existingIndex], normalized);
  } else {
    panel.state.turns.push(normalized);
  }
  panel.state.turns = sortPanelTurns(panel.state.turns);
  restoreExpandedTurnKeys(panel, previousExpanded);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
  return normalized;
}

function reconcileResponseBatchTurns(panel, result) {
  if (!Array.isArray(result?.batch_turns)) {
    return;
  }
  const previousExpanded = captureExpandedTurnKeys(panel);
  const responseSessionId =
    typeof result?.session_id === "string" && result.session_id
      ? result.session_id
      : (typeof panel?.state?.sessionId === "string" && panel.state.sessionId ? panel.state.sessionId : null);
  const nextTurns = [];
  for (const entry of Array.isArray(panel?.state?.turns) ? panel.state.turns : []) {
    if (entry?.entry_type !== "batch") {
      nextTurns.push(entry);
      continue;
    }
    if (responseSessionId && entry.session_id === responseSessionId) {
      continue;
    }
    nextTurns.push(entry);
  }
  panel.state.turns = nextTurns;
  const finalIndex = result.batch_turns.length - 1;
  const resultHasCandidate = Boolean(result?.candidateGraph && typeof result.candidateGraph === "object");
  for (let index = 0; index < result.batch_turns.length; index += 1) {
    const turn = result.batch_turns[index];
    const turnPayload =
      index === finalIndex
      && typeof result?.done_summary === "string"
      && result.done_summary
        ? { ...turn, done_summary: turn.done_summary || result.done_summary }
        : turn;
    const turnOutcome =
      (index === finalIndex && result?.outcome && typeof result.outcome === "object")
        ? result.outcome
        : (turnPayload?.outcome && typeof turnPayload.outcome === "object" ? turnPayload.outcome : null);
    let status = null;
    if (outcomeRequiresClarification(turnOutcome)) {
      status = "clarify";
    } else if (
      result?.ok === true
      || resultHasCandidate
      || (typeof result?.done_summary === "string" && result.done_summary)
      || index === finalIndex
    ) {
      status = "done";
    } else {
      status = "in_progress";
    }
    upsertBatchTurn(panel, turnPayload, {
      source: "response",
      sessionId: responseSessionId,
      status,
      parentTurnId: typeof result?.turn_id === "string" && result.turn_id ? result.turn_id : null,
    });
  }
  restoreExpandedTurnKeys(panel, previousExpanded);
  markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
}

function getAgentTurnEventPayload(event) {
  if (event?.detail && typeof event.detail === "object") {
    return event.detail;
  }
  return event && typeof event === "object" ? event : null;
}

function shouldAcceptAgentTurnEvent(panel, payload) {
  if (!panel?.state || panel.root?.dataset?.open !== "1") {
    return false;
  }
  const payloadSessionId =
    typeof payload?.session_id === "string" && payload.session_id ? payload.session_id : null;
  if (!payloadSessionId) {
    return false;
  }
  const currentSessionId =
    typeof panel.state.sessionId === "string" && panel.state.sessionId ? panel.state.sessionId : null;
  if (currentSessionId) {
    return currentSessionId === payloadSessionId;
  }
  // No bound session yet (fresh first run — the server assigns the session_id):
  // intentionally drop live events rather than risk binding a foreign session.
  // The authoritative batch_turns in the submit response reconcile the feed at
  // completion, and every run after the first is fully live once bound.
  const batchSessionIds = new Set(
    (Array.isArray(panel.state.turns) ? panel.state.turns : [])
      .filter((entry) => entry?.entry_type === "batch" && typeof entry.session_id === "string" && entry.session_id)
      .map((entry) => entry.session_id),
  );
  if (batchSessionIds.size > 0) {
    return batchSessionIds.size === 1 && batchSessionIds.has(payloadSessionId);
  }
  return false;
}

function handleAgentTurnEvent(event) {
  const panel = currentAgentPanel();
  if (!panel || panel.root?.dataset?.open !== "1") {
    return;
  }
  const payload = getAgentTurnEventPayload(event);
  if (!payload || !shouldAcceptAgentTurnEvent(panel, payload)) {
    return;
  }
  if (!panel.state.sessionId && typeof payload.session_id === "string" && payload.session_id) {
    panel.state.sessionId = payload.session_id;
  }
  const normalized = upsertBatchTurn(panel, payload, { source: "websocket" });
  if (!normalized) {
    return;
  }
  scheduleRenderAgentPanel("websocket", panel);
}

function ensureAgentTurnListener() {
  if (api?.__vibecomfyAgentTurnListenerRegistered || typeof api?.addEventListener !== "function") {
    return;
  }
  agentTurnEventListener = handleAgentTurnEvent;
  // Event name MUST match the backend emit string in agent_edit.py (_ws_send).
  api.addEventListener("vibecomfy.agent_edit.turn", agentTurnEventListener);
  agentTurnEventListenerRegistered = true;
  api.__vibecomfyAgentTurnListenerRegistered = true;
}

function renderMeta(panel) {
  clearNode(panel.metaRow);
  panel.metaRow.appendChild(labelValue("state", panel.state.phase));
  panel.metaRow.appendChild(labelValue("session", panel.state.sessionId || "new"));
  panel.metaRow.appendChild(labelValue("turn", panel.state.turnId || "pending"));
  panel.metaRow.appendChild(labelValue("baseline", panel.state.baselineTurnId || "none"));
}

// ── Progress pulse animation (injected once) ──────────────────────────────
function _injectProgressPulseStyle() {
  if (_progressPulseInjected) return;
  _progressPulseInjected = true;
  const style = el("style");
  style.textContent = `
    @keyframes vibecomfy-progress-pulse {
      0%, 100% { opacity: 0.35; }
      50% { opacity: 1; }
    }
    .vibecomfy-batch-progress-dot {
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #3d8bfd;
      animation: vibecomfy-progress-pulse 1.2s ease-in-out infinite;
      margin-right: 4px;
      vertical-align: middle;
    }
    .vibecomfy-batch-row {
      cursor: pointer;
      user-select: none;
      transition: background 0.15s;
    }
    .vibecomfy-batch-row:hover {
      background: #1a1d24;
    }
    .vibecomfy-batch-expanded {
      margin-top: 4px;
      padding-left: 4px;
      border-left: 2px solid #282a32;
    }
  `;
  document.head.appendChild(style);
}

// ── Batch row helpers ─────────────────────────────────────────────────────
const BATCH_STATUS_COLORS = Object.freeze({
  in_progress: VC_COLORS.active,
  clarify: VC_COLORS.warning,
  done: VC_COLORS.success,
  budget_exhausted: VC_COLORS.warning,
});

const DURABLE_STATUS_COLORS = Object.freeze({
  pending: "#ffd36f",
  candidate: "#7db6ff",
  applied: "#4caf50",
  rejected: "#ff7f7f",
  failed: "#ff8d8d",
});

function _statusColor(status) {
  return DURABLE_STATUS_COLORS[status] || BATCH_STATUS_COLORS[status] || VC_COLORS.muted;
}

const ACTIVITY_TERMINAL_STATUSES = new Set([
  "applied",
  "budget_exhausted",
  "cancelled",
  "candidate",
  "clarify",
  "done",
  "error",
  "failed",
  "noop",
  "rejected",
  "undone",
]);

function isLiveActivityTurn(entry) {
  if (!entry || typeof entry !== "object") {
    return false;
  }
  const status = typeof entry.status === "string" && entry.status ? entry.status : null;
  if (!status || ACTIVITY_TERMINAL_STATUSES.has(status)) {
    return false;
  }
  return entry.entry_type === "batch" || entry.entry_type === "durable";
}

function _truncateMessage(text, maxLen = 80) {
  if (typeof text !== "string" || !text) return null;
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen - 1) + "\u2026" : cleaned;
}

function _safeSummaryText(entry) {
  // Extract a compact summary suitable for the "reasoning" toggle.
  // Sources (in priority order): done_summary, clarification_message,
  // aggregated teaching_hints from statements.
  if (typeof entry.done_summary === "string" && entry.done_summary.trim()) {
    return entry.done_summary.trim();
  }
  if (typeof entry.clarification_message === "string" && entry.clarification_message.trim()) {
    return entry.clarification_message.trim();
  }
  const hints = [];
  if (Array.isArray(entry.statements)) {
    for (const stmt of entry.statements) {
      if (stmt && typeof stmt.teaching_hint === "string" && stmt.teaching_hint.trim()) {
        hints.push(stmt.teaching_hint.trim());
      }
    }
  }
  return hints.length ? hints.join(" | ") : null;
}

const BATCH_STATEMENT_CAP = 5;

function _statementBullet(stmt, index) {
  const row = el("div");
  Object.assign(row.style, {
    display: "flex",
    alignItems: "flex-start",
    gap: "4px",
    fontSize: "11px",
    lineHeight: "1.35",
    marginBottom: "2px",
  });

  // Landed / failed badge
  const landed = stmt.landed;
  const ok = stmt.ok;
  const statusIcon = landed ? "\u2713" : (ok === false ? "\u2717" : "\u25cb");
  const statusColor = landed ? VC_COLORS.success : (ok === false ? VC_COLORS.error : VC_COLORS.muted);
  const badge = el("span", statusIcon);
  Object.assign(badge.style, {
    color: statusColor,
    fontWeight: "700",
    minWidth: "12px",
    textAlign: "center",
  });
  row.appendChild(badge);

  // Op kind label
  const kind = typeof stmt.op_kind === "string" && stmt.op_kind ? stmt.op_kind : "stmt";
  const kindEl = el("span", `${kind}${Number.isFinite(stmt.statement_index) ? ` #${stmt.statement_index}` : ""}`);
  kindEl.style.color = "#9da1ac";
  row.appendChild(kindEl);

  const targetText =
    (typeof stmt.field_path === "string" && stmt.field_path)
    || (typeof stmt.target === "string" && stmt.target)
    || (typeof stmt.target_field === "string" && stmt.target_field)
    || null;
  if (targetText) {
    const targetEl = el("span", targetText);
    targetEl.style.color = "#c4ccd6";
    targetEl.style.fontSize = "10px";
    targetEl.style.marginLeft = "2px";
    targetEl.style.overflowWrap = "anywhere";
    row.appendChild(targetEl);
  }

  // First diagnostic (compact)
  if (Array.isArray(stmt.diagnostics) && stmt.diagnostics.length) {
    const firstDiag = stmt.diagnostics[0];
    if (firstDiag && typeof firstDiag === "object") {
      const code = typeof firstDiag.code === "string" ? firstDiag.code : "";
      const msg = typeof firstDiag.message === "string" ? firstDiag.message : "";
      const diagText = code && msg ? `${code}: ${msg}` : (code || msg);
      if (diagText) {
        const diagEl = el("span", _truncateMessage(diagText, 50) || diagText);
        diagEl.style.color = "#8d93a1";
        diagEl.style.fontSize = "10px";
        diagEl.style.marginLeft = "4px";
        row.appendChild(diagEl);
      }
    }
  }

  return row;
}

function _renderOutcomeFooter(entry) {
  const parts = [];
  if (typeof entry.exit_mode === "string" && entry.exit_mode) {
    parts.push(`exit: ${entry.exit_mode}`);
  }
  if (entry.budget && typeof entry.budget === "object") {
    if (Number.isFinite(entry.budget.remaining_batches)) {
      parts.push(`budget: ${entry.budget.remaining_batches} left`);
    } else if (Number.isFinite(entry.budget.consecutive_errors)) {
      parts.push(`errors: ${entry.budget.consecutive_errors}`);
    }
  }
  if (typeof entry.batch_ok === "boolean") {
    parts.push(entry.batch_ok ? "ok" : "not ok");
  }
  if (!parts.length) return null;
  const footer = el("div", parts.join(" \u00b7 "));
  Object.assign(footer.style, {
    fontSize: "10px",
    color: "#8d93a1",
    marginTop: "4px",
    fontStyle: "italic",
  });
  return footer;
}

function _renderBatchTurnRow(body, panel, entry, index) {
  const turnKey = entry.turn_key;
  const expanded = !!(panel.state.expandedTurnKeys && panel.state.expandedTurnKeys[turnKey]);
  const isInProgress = entry.status === "in_progress";
  const statusColor = _statusColor(entry.status);
  const turnLabel = Number.isFinite(entry.turn_number)
    ? `Turn ${entry.turn_number + 1}`
    : (typeof entry.turn_id === "string" && entry.turn_id ? `turn ${entry.turn_id}` : "batch turn");

  const row = el("div");
  row.className = "vibecomfy-batch-row";
  Object.assign(row.style, {
    borderLeft: `3px solid ${statusColor}`,
    paddingLeft: "8px",
    marginBottom: "6px",
    display: "grid",
    gap: "3px",
  });
  row.onclick = function () {
    if (!panel.state.expandedTurnKeys || typeof panel.state.expandedTurnKeys !== "object") {
      panel.state.expandedTurnKeys = {};
    }
    if (panel.state.expandedTurnKeys[turnKey]) {
      delete panel.state.expandedTurnKeys[turnKey];
    } else {
      panel.state.expandedTurnKeys[turnKey] = true;
    }
    renderHistory(panel);
    renderActivityRows(panel);
  };

  // ── Collapsed view (always visible) ──────────────────────────────────
  const collapsedLine = el("div");
  Object.assign(collapsedLine.style, {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexWrap: "wrap",
    fontSize: "12px",
  });

  // In-progress indicator
  if (isInProgress) {
    const dot = el("span");
    dot.className = "vibecomfy-batch-progress-dot";
    collapsedLine.appendChild(dot);
  }

  // Turn label
  const labelEl = el("span", turnLabel);
  labelEl.style.color = statusColor;
  labelEl.style.fontWeight = "700";
  collapsedLine.appendChild(labelEl);

  // Status badge
  const statusEl = el("span", entry.status || "unknown");
  Object.assign(statusEl.style, {
    color: statusColor,
    fontSize: "9px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontWeight: "600",
  });
  collapsedLine.appendChild(statusEl);

  // Truncated message
  const shortMsg = _truncateMessage(
    entry.status === "done"
      ? (
        entry.done_summary && entry.message && entry.done_summary !== entry.message
          ? `${entry.done_summary} ${entry.message}`
          : (entry.done_summary || entry.message)
      )
      : (entry.message || entry.done_summary),
    80,
  );
  if (shortMsg) {
    const msgEl = el("span", shortMsg);
    msgEl.style.color = "#9da1ac";
    msgEl.style.fontSize = "11px";
    msgEl.style.flex = "1 1 auto";
    msgEl.style.minWidth = "0";
    msgEl.style.overflow = "hidden";
    msgEl.style.textOverflow = "ellipsis";
    msgEl.style.whiteSpace = "nowrap";
    collapsedLine.appendChild(msgEl);
  }

  // Expand chevron
  const chevron = el("span", expanded ? "\u25bc" : "\u25b6");
  chevron.style.color = "#8d93a1";
  chevron.style.fontSize = "9px";
  collapsedLine.appendChild(chevron);

  row.appendChild(collapsedLine);

  // ── Expanded view ────────────────────────────────────────────────────
  if (expanded) {
    const expandedBox = el("div");
    expandedBox.className = "vibecomfy-batch-expanded";
    Object.assign(expandedBox.style, {
      display: "grid",
      gap: "4px",
      marginTop: "3px",
    });

    // Audit download for expanded batch rows
    const auditBtnRow = el("div");
    Object.assign(auditBtnRow.style, {
      display: "flex",
      justifyContent: "flex-end",
    });
    const auditBtn = button("Audit \u2193", (e) => {
      e.stopPropagation();
      downloadTurnAudit(panel, index);
    });
    auditBtn.style.fontSize = "10px";
    auditBtn.style.padding = "2px 5px";
    auditBtnRow.appendChild(auditBtn);
    expandedBox.appendChild(auditBtnRow);

    // Reasoning toggle
    const summary = _safeSummaryText(entry);
    if (summary) {
      const reasoningRow = el("div");
      const reasoningToggle = el("span", "\u25b6 Reasoning");
      Object.assign(reasoningToggle.style, {
        color: "#9ed0ff",
        fontSize: "11px",
        cursor: "pointer",
        userSelect: "none",
      });
      let reasoningShown = false;
      const reasoningBody = el("div");
      Object.assign(reasoningBody.style, {
        display: "none",
        fontSize: "11px",
        color: "#c4ccd6",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        marginTop: "2px",
        paddingLeft: "12px",
        borderLeft: "2px solid #282a32",
      });
      reasoningBody.textContent = summary;
      reasoningToggle.onclick = function (e) {
        e.stopPropagation();
        reasoningShown = !reasoningShown;
        reasoningToggle.textContent = reasoningShown ? "\u25bc Reasoning" : "\u25b6 Reasoning";
        reasoningBody.style.display = reasoningShown ? "block" : "none";
      };
      reasoningRow.appendChild(reasoningToggle);
      reasoningRow.appendChild(reasoningBody);
      expandedBox.appendChild(reasoningRow);
    }

    // Statement bullets (up to BATCH_STATEMENT_CAP)
    const stmts = Array.isArray(entry.statements) ? entry.statements : [];
    const showStmts = stmts.slice(0, BATCH_STATEMENT_CAP);
    const moreCount = stmts.length - BATCH_STATEMENT_CAP;
    if (showStmts.length) {
      const stmtsHeader = el("div", "Statements:");
      stmtsHeader.style.fontSize = "10px";
      stmtsHeader.style.color = "#9da1ac";
      stmtsHeader.style.textTransform = "uppercase";
      stmtsHeader.style.letterSpacing = "0.04em";
      expandedBox.appendChild(stmtsHeader);
      for (let s = 0; s < showStmts.length; s += 1) {
        expandedBox.appendChild(_statementBullet(showStmts[s], s));
      }
      // Capped-more line
      if (moreCount > 0) {
        const moreLine = el("div", `+${moreCount} more statement${moreCount !== 1 ? "s" : ""}\u2026`);
        moreLine.style.fontSize = "10px";
        moreLine.style.color = "#8d93a1";
        moreLine.style.fontStyle = "italic";
        expandedBox.appendChild(moreLine);
      }
    } else if (Number.isFinite(entry.statement_count) && entry.statement_count > 0) {
      const stmtsNote = el("div", `${entry.statement_count} statement${entry.statement_count !== 1 ? "s" : ""} (details unavailable)`);
      stmtsNote.style.fontSize = "10px";
      stmtsNote.style.color = "#8d93a1";
      expandedBox.appendChild(stmtsNote);
    }

    // Outcome footer
    const footer = _renderOutcomeFooter(entry);
    if (footer) {
      expandedBox.appendChild(footer);
    }

    // Turn-level diagnostics (compact)
    if (Array.isArray(entry.diagnostics) && entry.diagnostics.length) {
      const diagHeader = el("div", "Diagnostics:");
      diagHeader.style.fontSize = "10px";
      diagHeader.style.color = "#9da1ac";
      diagHeader.style.textTransform = "uppercase";
      diagHeader.style.letterSpacing = "0.04em";
      expandedBox.appendChild(diagHeader);
      const maxDiags = Math.min(entry.diagnostics.length, 5);
      for (let d = 0; d < maxDiags; d += 1) {
        const diag = entry.diagnostics[d];
        if (diag && typeof diag === "object") {
          const code = typeof diag.code === "string" ? diag.code : "";
          const msg = typeof diag.message === "string" ? diag.message : "";
          const diagText = code && msg ? `${code}: ${msg}` : (code || msg);
          if (diagText) {
            const diagLine = el("div", diagText);
            diagLine.style.fontSize = "10px";
            diagLine.style.color = "#8d93a1";
            expandedBox.appendChild(diagLine);
          }
        }
      }
    }

    // Timestamp
    if (typeof entry.timestamp === "string" && entry.timestamp) {
      const tsLine = el("div", entry.timestamp);
      tsLine.style.fontSize = "9px";
      tsLine.style.color = "#6b7080";
      expandedBox.appendChild(tsLine);
    }

    row.appendChild(expandedBox);
  }

  body.appendChild(row);
}

function _renderDurableTurnRow(body, panel, entry, index) {
  const turnCard = el("div");
  turnCard.style.borderLeft = "3px solid #3d8bfd";
  turnCard.style.paddingLeft = "8px";
  turnCard.style.marginBottom = "8px";
  turnCard.style.display = "grid";
  turnCard.style.gap = "4px";

  const statusColor = _statusColor(entry.status);

  const headerRow = el("div");
  headerRow.style.display = "flex";
  headerRow.style.justifyContent = "space-between";
  headerRow.style.alignItems = "center";
  headerRow.style.gap = "8px";

  const statusBadge = el("span", entry.status || "unknown");
  statusBadge.style.color = statusColor;
  statusBadge.style.fontWeight = "700";
  statusBadge.style.textTransform = "uppercase";
  statusBadge.style.fontSize = "10px";
  statusBadge.style.letterSpacing = "0.05em";
  headerRow.appendChild(statusBadge);

  const downloadBtn = button("Audit \u2193", () => downloadTurnAudit(panel, index));
  downloadBtn.style.fontSize = "10px";
  downloadBtn.style.padding = "3px 6px";
  headerRow.appendChild(downloadBtn);

  turnCard.appendChild(headerRow);

  if (entry.turn_id) {
    appendTextLine(turnCard, `turn ${entry.turn_id}`, "#8d93a1");
  }
  if (entry.task) {
    appendTextLine(turnCard, entry.task, "#edf2f7");
  }
  if (entry.failure_kind) {
    appendTextLine(turnCard, `${entry.failure_kind}${entry.failure_stage ? ` @ ${entry.failure_stage}` : ""}`, "#ffb86c");
  }
  if (entry.message) {
    appendTextLine(turnCard, entry.message, "#9da1ac");
  }
  if (entry.audit_ref?.path) {
    appendCodeLine(turnCard, `audit: ${entry.audit_ref.path}`, "#9ed0ff");
  }
  if (entry.timestamp) {
    appendTextLine(turnCard, entry.timestamp, "#8d93a1");
  }

  body.appendChild(turnCard);
}

// ── Chat thread rendering (M4b — newest-at-bottom bubble list) ────────────

const THREAD_WINDOW_SIZE = 30;
// How close to the bottom (px) the user must be for new content to keep
// auto-following. 8px was effectively "exactly at the bottom" — any expanded
// details or late-appended row left the thread permanently un-followed.
const THREAD_NEAR_BOTTOM_TOLERANCE_PX = 120;

function ensureThreadRenderState(panel) {
  if (!panel?.threadState || typeof panel.threadState !== "object") {
    resetThreadRenderState(panel);
  }
  return panel.threadState;
}

function collectThreadMessageEntries(panel) {
  const threadMessages = Array.isArray(panel?.state?.chatMessages)
    ? panel.state.chatMessages.slice()
    : [];
  const syntheticAgentMessage = buildSyntheticAgentMessage(panel);
  if (syntheticAgentMessage) {
    threadMessages.push(syntheticAgentMessage);
  }
  return threadMessages.map((msg, index) => ({
    msg,
    index,
    key: messageStableKey(msg, index),
  }));
}

function ensureChatThreadMounts(body) {
  const mounts = {
    sessionRow: [],
    olderMount: [],
    messagesMount: [],
    emptyMount: [],
    activityMount: [],
  };
  for (const child of Array.from(body.children || [])) {
    if (child?.dataset?.vibecomfyChatSessionRow === "1") {
      mounts.sessionRow.push(child);
    } else if (child?.dataset?.vibecomfyChatOlderMount === "1") {
      mounts.olderMount.push(child);
    } else if (child?.dataset?.vibecomfyChatMessages === "1") {
      mounts.messagesMount.push(child);
    } else if (child?.dataset?.vibecomfyChatEmpty === "1") {
      mounts.emptyMount.push(child);
    } else if (child?.dataset?.vibecomfyChatActivity === "1") {
      mounts.activityMount.push(child);
    }
  }
  let sessionRow = mounts.sessionRow[0] || null;
  let olderMount = mounts.olderMount[0] || null;
  let messagesMount = mounts.messagesMount[0] || null;
  let emptyMount = mounts.emptyMount[0] || null;
  let activityMount = mounts.activityMount[0] || null;
  for (const list of Object.values(mounts)) {
    for (const duplicate of list.slice(1)) {
      if (duplicate?.parentNode === body) {
        body.removeChild(duplicate);
      }
    }
  }
  if (!sessionRow) {
    sessionRow = el("div");
    sessionRow.dataset.vibecomfyChatSessionRow = "1";
    Object.assign(sessionRow.style, {
      display: "none",
      alignItems: "center",
      gap: "6px",
      marginBottom: "8px",
      paddingBottom: "6px",
      borderBottom: "1px solid #282a32",
      minWidth: "0",
      maxWidth: "100%",
    });
  }
  if (!messagesMount) {
    messagesMount = el("div");
    messagesMount.dataset.vibecomfyChatMessages = "1";
    Object.assign(messagesMount.style, {
      display: "grid",
      gap: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  if (!emptyMount) {
    emptyMount = el("div");
    emptyMount.dataset.vibecomfyChatEmpty = "1";
    Object.assign(emptyMount.style, {
      display: "none",
      gap: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  if (!olderMount) {
    olderMount = el("div");
    olderMount.dataset.vibecomfyChatOlderMount = "1";
    Object.assign(olderMount.style, {
      display: "none",
      marginBottom: "6px",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  if (!activityMount) {
    activityMount = el("div");
    activityMount.dataset.vibecomfyChatActivity = "1";
    Object.assign(activityMount.style, {
      display: "none",
      marginTop: "8px",
      paddingTop: "8px",
      borderTop: "1px solid #282a32",
      minWidth: "0",
      maxWidth: "100%",
      overflowWrap: "anywhere",
    });
  }
  sessionRow.dataset.vibecomfyChatSessionRow = "1";
  olderMount.dataset.vibecomfyChatOlderMount = "1";
  messagesMount.dataset.vibecomfyChatMessages = "1";
  activityMount.dataset.vibecomfyChatActivity = "1";
  emptyMount.dataset.vibecomfyChatEmpty = "1";
  appendChildOnce(body, sessionRow);
  appendChildOnce(body, olderMount);
  appendChildOnce(body, messagesMount);
  appendChildOnce(body, activityMount);
  appendChildOnce(body, emptyMount);
  return { sessionRow, olderMount, messagesMount, emptyMount, activityMount };
}

function renderChatSessionLink(sessionRow, panel) {
  const sessionLabel = panel?.state?.chatSessionPath || (panel?.state?.sessionId ? `out/editor_sessions/${panel.state.sessionId}` : null);
  if (!sessionLabel) {
    clearNode(sessionRow);
    sessionRow.style.display = "none";
    return;
  }
  const href = `/vibecomfy/agent-edit/session-json?session_id=${encodeURIComponent(panel.state.sessionId || "")}`;
  let link = sessionRow.querySelectorAll("a")[0] || null;
  if (!link) {
    clearNode(sessionRow);
    link = el("a");
    link.target = "_blank";
    link.rel = "noopener";
    Object.assign(link.style, {
      color: "#9ed0ff",
      fontSize: "10px",
      fontFamily: "monospace",
      textDecoration: "none",
      cursor: "pointer",
      minWidth: "0",
      overflowWrap: "anywhere",
      wordBreak: "break-word",
    });
    sessionRow.appendChild(link);
  }
  link.textContent = `session: ${sessionLabel}`;
  link.href = href;
  sessionRow.style.display = "flex";
}

function bubbleRenderSignature(panel, msg) {
  const snapshot = detailSnapshotForMessage(panel, msg);
  const actionState = candidateActionState(panel, msg, snapshot);
  const signatureParts = [
    messageSignature(msg),
    snapshot?.phase || "",
    snapshot?.message || "",
    snapshot?.auditRef?.path || "",
    snapshot?.changeDetails?.done_summary || msg?.change_details?.done_summary || "",
    Array.isArray(snapshot?.fieldChanges) ? String(snapshot.fieldChanges.length) : "",
    Array.isArray(msg?.field_changes) ? String(msg.field_changes.length) : "",
    actionState.turnId || "",
    actionState.eligibility?.reason || "",
    actionState.eligibility?.message || "",
    actionState.active ? "1" : "0",
    actionState.applyDisabled ? "1" : "0",
    actionState.rejectDisabled ? "1" : "0",
  ];
  return signatureParts.join("|");
}

function renderChatBubbleNode(bubble, panel, msg, messageKey, messageIndex) {
  clearNode(bubble);
  bubble.dataset.vibecomfyMessageKey = messageKey;
  const isUser = msg.role === "user";
  Object.assign(bubble.style, {
    display: "flex",
    flexDirection: "column",
    alignItems: isUser ? "flex-end" : "flex-start",
    marginBottom: "6px",
    maxWidth: "100%",
    minWidth: "0",
  });

  const label = el("span", isUser ? "You" : "Agent");
  Object.assign(label.style, {
    fontSize: "9px",
    fontWeight: "700",
    color: isUser ? "#7db6ff" : "#02d4b3",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "2px",
  });
  bubble.appendChild(label);

  const text = el("div", String(msg.text || ""));
  Object.assign(text.style, {
    fontSize: "12px",
    color: isUser ? "#d1d6e0" : "#c4ccd6",
    background: isUser ? "#1a2436" : "#0f2a26",
    padding: "6px 10px",
    borderRadius: isUser ? "10px 10px 3px 10px" : "10px 10px 10px 3px",
    maxWidth: "92%",
    wordBreak: "break-word",
    overflowWrap: "anywhere",
    whiteSpace: "pre-wrap",
    lineHeight: "1.4",
    minWidth: "0",
  });
  bubble.appendChild(text);

  if (isUser) {
    return;
  }

  const detailTurnKey =
    typeof msg.turn_id === "string" && msg.turn_id
      ? `turn:${msg.turn_id}`
      : (typeof msg.detail_turn_id === "string" && msg.detail_turn_id
        ? `turn:${msg.detail_turn_id}:failure:${messageKey || messageIndex}`
        : `agent:${messageKey || messageIndex}:${String(msg.text || "").slice(0, 24)}`);
  const detailSnapshot = detailSnapshotForMessage(panel, msg);
  const detailRow = el("div");
  Object.assign(detailRow.style, {
    marginTop: "3px",
    fontSize: "10px",
    maxWidth: "100%",
    minWidth: "0",
    overflowWrap: "anywhere",
  });

  const detailToggle = el("span", "\u25b6 details");
  Object.assign(detailToggle.style, {
    color: "#8d93a1",
    cursor: "pointer",
    userSelect: "none",
  });

  const detailBody = el("div");
  Object.assign(detailBody.style, {
    display: "none",
    marginTop: "4px",
    padding: "6px 8px",
    background: "#0d0f14",
    border: "1px solid #282a32",
    borderRadius: "4px",
    fontSize: "10px",
    color: "#8d93a1",
    gridTemplateColumns: "minmax(0, 1fr)",
    gap: "4px 8px",
    alignItems: "baseline",
    maxWidth: "100%",
    minWidth: "0",
    maxHeight: "360px",
    overflow: "auto",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  });

  // ── Lazy detail population (T13) ────────────────────────────────────
  // Build a detail-content signature so we can skip re-population when
  // nothing changed and avoid prebuilding detail panes for collapsed bubbles.
  const detailSigParts = [
    detailSnapshot?.phase || "",
    detailSnapshot?.message || "",
    detailSnapshot?.auditRef?.path || "",
    detailSnapshot?.changeDetails?.done_summary || msg?.change_details?.done_summary || "",
    Array.isArray(detailSnapshot?.fieldChanges) ? String(detailSnapshot.fieldChanges.length) : "",
    Array.isArray(msg?.field_changes) ? String(msg.field_changes.length) : "",
    msg?.turn_id || "",
    msg?.detail_turn_id || "",
    String(msg?.text || "").slice(0, 80),
  ];
  const detailSignature = detailSigParts.join("|");

  const ts = ensureThreadRenderState(panel);
  if (!ts.bubbleDetailSignatures) {
    ts.bubbleDetailSignatures = {};
  }

  let detailShown = !!panel.state.expandedBubbleTurnKeys?.[detailTurnKey];
  const needsPopulate = detailShown && (
    !ts.bubbleDetailSignatures[detailTurnKey] ||
    ts.bubbleDetailSignatures[detailTurnKey] !== detailSignature
  );

  if (needsPopulate) {
    populateAgentBubbleDetail(detailBody, panel, msg, detailSnapshot);
    ts.bubbleDetailSignatures[detailTurnKey] = detailSignature;
  } else if (!detailShown) {
    // Collapsed bubble: ensure stale populated flag is cleared so next
    // expand will repopulate when the signature changed.
    if (ts.bubbleDetailSignatures[detailTurnKey] &&
        ts.bubbleDetailSignatures[detailTurnKey] !== detailSignature) {
      delete ts.bubbleDetailSignatures[detailTurnKey];
    }
  }

  detailToggle.textContent = detailShown ? "\u25bc details" : "\u25b6 details";
  detailBody.style.display = detailShown ? "grid" : "none";

  detailToggle.onclick = function () {
    detailShown = !detailShown;
    if (!panel.state.expandedBubbleTurnKeys || typeof panel.state.expandedBubbleTurnKeys !== "object") {
      panel.state.expandedBubbleTurnKeys = {};
    }
    if (detailShown) {
      panel.state.expandedBubbleTurnKeys[detailTurnKey] = true;
    } else {
      delete panel.state.expandedBubbleTurnKeys[detailTurnKey];
    }
    detailToggle.textContent = detailShown ? "\u25bc details" : "\u25b6 details";
    detailBody.style.display = detailShown ? "grid" : "none";

    // Populate lazily on first expand or when the detail signature changed.
    if (detailShown) {
      const curTs = ensureThreadRenderState(panel);
      if (!curTs.bubbleDetailSignatures) {
        curTs.bubbleDetailSignatures = {};
      }
      if (!curTs.bubbleDetailSignatures[detailTurnKey] ||
          curTs.bubbleDetailSignatures[detailTurnKey] !== detailSignature) {
        populateAgentBubbleDetail(detailBody, panel, msg, detailSnapshot);
        curTs.bubbleDetailSignatures[detailTurnKey] = detailSignature;
      }
    }
  };

  detailRow.appendChild(detailToggle);
  detailRow.appendChild(detailBody);
  bubble.appendChild(detailRow);
}

function reconcileChatBubbles(panel, messagesMount, displayEntries) {
  const threadState = ensureThreadRenderState(panel);
  const rawBubbleMap = threadState.bubbleMap || {};
  const priorBubbleMap = {};
  const knownMountedNodes = new Set();
  for (const [key, bubbleEntry] of Object.entries(rawBubbleMap)) {
    if (bubbleEntry?.node?.parentNode !== messagesMount) {
      continue;
    }
    priorBubbleMap[key] = bubbleEntry;
    knownMountedNodes.add(bubbleEntry.node);
  }
  for (const child of Array.from(messagesMount?.children || [])) {
    if (!knownMountedNodes.has(child)) {
      messagesMount.removeChild(child);
    }
  }
  const nextBubbleMap = {};
  const nextSignatures = {};
  const nextKeyOrder = [];

  for (const entry of displayEntries) {
    const { msg, index, key } = entry;
    if (!msg || typeof msg !== "object" || !msg.role) {
      continue;
    }
    const signature = bubbleRenderSignature(panel, msg);
    let bubbleEntry = priorBubbleMap[key] || null;
    if (!bubbleEntry?.node) {
      bubbleEntry = { node: el("div") };
      renderChatBubbleNode(bubbleEntry.node, panel, msg, key, index);
    } else if (bubbleEntry.signature !== signature) {
      renderChatBubbleNode(bubbleEntry.node, panel, msg, key, index);
    }
    bubbleEntry.signature = signature;
    nextBubbleMap[key] = bubbleEntry;
    nextSignatures[key] = signature;
    nextKeyOrder.push(key);
    appendChildOnce(messagesMount, bubbleEntry.node);
  }

  for (const [key, bubbleEntry] of Object.entries(priorBubbleMap)) {
    if (nextBubbleMap[key]) {
      continue;
    }
    if (bubbleEntry?.node?.parentNode === messagesMount) {
      messagesMount.removeChild(bubbleEntry.node);
    }
  }

  threadState.renderedKeyOrder = nextKeyOrder;
  threadState.bubbleMap = nextBubbleMap;
  threadState.signatures = nextSignatures;
  threadState.lastVisibleKeySet = new Set(nextKeyOrder);
}

function renderShowEarlierMessages(panel, olderMount, hiddenCount) {
  if (!olderMount) {
    return;
  }
  if (!Number.isFinite(hiddenCount) || hiddenCount <= 0) {
    clearNode(olderMount);
    olderMount.style.display = "none";
    return;
  }
  clearNode(olderMount);
  const showEarlierButton = button("Show earlier messages", () => {
    const threadState = ensureThreadRenderState(panel);
    if (threadState.expandedOlder) {
      return;
    }
    threadState.expandedOlder = true;
    markAgentPanelDirty(panel, [RENDER_SECTIONS.THREAD]);
    renderAgentPanel(panel, { dirtySections: [RENDER_SECTIONS.THREAD] });
  });
  showEarlierButton.dataset.vibecomfyShowEarlierMessages = "1";
  showEarlierButton.title = `${hiddenCount} earlier message${hiddenCount === 1 ? "" : "s"} hidden`;
  Object.assign(showEarlierButton.style, {
    padding: "4px 8px",
    fontSize: "10px",
    lineHeight: "1.3",
  });
  olderMount.appendChild(showEarlierButton);
  olderMount.style.display = "block";
}

function computeThreadDisplayEntries(panel, threadEntries) {
  const threadState = ensureThreadRenderState(panel);
  if (threadState.expandedOlder || threadEntries.length <= THREAD_WINDOW_SIZE) {
    return {
      displayEntries: threadEntries,
      hiddenCount: 0,
    };
  }
  return {
    displayEntries: threadEntries.slice(-THREAD_WINDOW_SIZE),
    hiddenCount: Math.max(0, threadEntries.length - THREAD_WINDOW_SIZE),
  };
}

function renderChatThread(panel) {
  const body = panel.sections.chat;
  const { sessionRow, olderMount, messagesMount, emptyMount, activityMount } = ensureChatThreadMounts(body);
  // Keep the legacy internal activity mount empty when the canonical history
  // region is present; renderActivityRows owns panel.sections.history.
  if (activityMount) {
    activityMount.style.display = "none";
  }
  renderChatSessionLink(sessionRow, panel);

  const threadEntries = collectThreadMessageEntries(panel);
  if (!threadEntries.length) {
    _lastThreadRender = {
      panelId: panel?.panelId || null,
      messagesSeen: 0,
      branch: "picker",
      at: new Date().toISOString(),
    };
    if (panel) {
      panel.lastThreadRender = _lastThreadRender;
    }
    renderShowEarlierMessages(panel, olderMount, 0);
    clearNode(messagesMount);
    ensureThreadRenderState(panel).renderedKeyOrder = [];
    panel.threadState.bubbleMap = {};
    panel.threadState.forceScrollOnNextRender = true;
    panel.threadState.signatures = {};
    panel.threadState.lastVisibleKeySet = null;
    clearNode(emptyMount);
    if (panel.state.chatError) {
      const errEl = el("div", `Chat unavailable: ${panel.state.chatError}`);
      errEl.style.color = "#ffb86c";
      errEl.style.fontSize = "11px";
      emptyMount.appendChild(errEl);
    }
    _renderWelcomeExamples(emptyMount);
    emptyMount.style.display = "grid";
    return false;
  }

  emptyMount.style.display = "none";
  clearNode(emptyMount);
  const { displayEntries, hiddenCount } = computeThreadDisplayEntries(panel, threadEntries);
  _lastThreadRender = {
    panelId: panel?.panelId || null,
    messagesSeen: threadEntries.length,
    branch: "messages",
    at: new Date().toISOString(),
  };
  if (panel) {
    panel.lastThreadRender = _lastThreadRender;
  }
  renderShowEarlierMessages(panel, olderMount, hiddenCount);
  reconcileChatBubbles(panel, messagesMount, displayEntries);
  return true;
}

function buildAgentPanelDebugSnapshot(panel = currentAgentPanel()) {
  const routeStatus = routeStatusState(panel);
  const readinessState = submitReadinessState(panel);
  let threadEntries = [];
  let displayEntries = [];
  let debugError = null;
  try {
    threadEntries = collectThreadMessageEntries(panel);
    ({ displayEntries } = computeThreadDisplayEntries(panel, threadEntries));
  } catch (err) {
    debugError = String(err);
  }
  return {
    panelId: panel?.panelId || null,
    panelsCreated: panelsCreatedCount(),
    lastThreadRender: _lastThreadRender,
    lastNoticeRender: _lastNoticeRender,
    statusCommitAt: _statusCommitAt,
    rehydrateCommitAt: _rehydrateCommitAt,
    marksAfterCommit: _marksAfterCommit,
    phase: panel?.state?.phase || null,
    readiness: {
      kind: routeStatus.kind || null,
      ready: Boolean(readinessState.ready),
      reason: readinessState.reason || null,
    },
    sessionId: panel?.state?.sessionId || null,
    turnId: panel?.state?.turnId || null,
    baselineTurnId: panel?.state?.baselineTurnId || null,
    messageCount: threadEntries.length,
    visibleMessageCount: displayEntries.length,
    dirtySections: Array.isArray(panel?.pendingDirtySections) ? panel.pendingDirtySections.slice() : [],
    renderCounts: panel?.__renderCounts && typeof panel.__renderCounts === "object"
      ? { ...panel.__renderCounts }
      : {},
    renderErrors: Array.isArray(panel?.__renderErrors) ? panel.__renderErrors.slice() : [],
    renderFailureCounts: panel?.__renderFailureCounts && typeof panel.__renderFailureCounts === "object"
      ? { ...panel.__renderFailureCounts }
      : {},
    debugError,
    mountMode: panel?.state?.mountMode || null,
    flushPending: hasPendingAgentPanelFlush(),
    flushCount: _agentPanelFlushCount,
    lastFlushReason: _lastAgentPanelFlushReason,
    mountedCheck: isAgentPanelRootConnected(panel),
    epochs: {
      status: Number.isFinite(panel?.state?.statusRequestEpoch) ? panel.state.statusRequestEpoch : 0,
      chatRehydrate: Number.isFinite(panel?.state?.chatRehydrateEpoch) ? panel.state.chatRehydrateEpoch : 0,
      chatRehydrateCommitted: Number.isFinite(panel?.state?.chatRehydrateCommittedEpoch)
        ? panel.state.chatRehydrateCommittedEpoch
        : 0,
      submit: Number.isFinite(panel?.state?.submitEpoch) ? panel.state.submitEpoch : 0,
    },
  };
}

function installAgentPanelDebugHook() {
  const targetWindow = typeof window !== "undefined" ? window : null;
  if (!targetWindow) {
    return;
  }
  targetWindow.__vibecomfyPanelDebug = () => buildAgentPanelDebugSnapshot(currentAgentPanel());
}

function populateAgentBubbleDetail(target, panel, message, snapshot = null) {
  clearNode(target);

  const metaSection = createBubbleDetailSection("Turn");
  appendTurnMeta(metaSection.body, panel, message, snapshot);
  target.appendChild(metaSection.section);

  // Live turn-progress rows are now rendered once in the shared activity
  // section (renderActivityRows) instead of being duplicated inside every
  // expanded bubble detail (T13 deduplication).

  const changeDetails = changeDetailsForMessage(panel, message, snapshot);
  if (changeDetails) {
    const changesSection = createBubbleDetailSection("Changes");
    const count = Number.isFinite(changeDetails.landed_operation_count)
      ? changeDetails.landed_operation_count
      : (Array.isArray(changeDetails.operations) ? changeDetails.operations.length : 0);
    appendTextLine(changesSection.body, `${count} operation${count === 1 ? "" : "s"}`, "#c4ccd6");
    if (changeDetails.done_summary) {
      appendTextLine(changesSection.body, changeDetails.done_summary, "#9ed0ff");
    }
    if (Array.isArray(changeDetails.operations) && changeDetails.operations.length) {
      const opList = el("div");
      Object.assign(opList.style, {
        display: "grid",
        gap: "3px",
        minWidth: "0",
      });
      for (const op of changeDetails.operations) {
        appendTextLine(opList, op?.summary || `${op?.field_path || "field"} changed`, "#b9ffcc");
      }
      changesSection.body.appendChild(opList);
    }
    changesSection.body.appendChild(createDetails("full change details", changeDetails));
    target.appendChild(changesSection.section);
  }

  const candidateSection = createBubbleDetailSection("Candidate");
  appendCandidateDetail(candidateSection.body, panel, message, snapshot);
  if (candidateSection.body.children.length) {
    target.appendChild(candidateSection.section);
  }

  const failureSection = createBubbleDetailSection("Failure");
  appendFailureDetail(failureSection.body, panel, snapshot);
  if (failureSection.body.children.length) {
    target.appendChild(failureSection.section);
  }

  const queueSection = createBubbleDetailSection("Queue");
  appendQueueDetail(queueSection.body, panel, snapshot);
  if (queueSection.body.children.length) {
    target.appendChild(queueSection.section);
  }

  const auditSection = createBubbleDetailSection("Audit");
  appendAuditDetail(auditSection.body, panel, message, snapshot);
  if (auditSection.body.children.length) {
    target.appendChild(auditSection.section);
  }

  const debugSection = createBubbleDetailSection("Debug");
  appendDebugDetail(debugSection.body, panel, snapshot);
  if (debugSection.body.children.length) {
    target.appendChild(debugSection.section);
  }
}

function appendTurnMeta(target, panel, message, snapshot = null) {
  const turnId = typeof message?.turn_id === "string" && message.turn_id ? message.turn_id : snapshot?.turn_id;
  if (turnId) {
    appendTextLine(target, `turn: ${turnId}`, "#8d93a1");
  }

  const fieldChanges = message?.field_changes || snapshot?.fieldChanges;
  if (fieldChanges && typeof fieldChanges === "object") {
    const directChanges = Array.isArray(fieldChanges.directChanges) ? fieldChanges.directChanges : [];
    const outcomeChanges = Array.isArray(fieldChanges.outcomeChanges) ? fieldChanges.outcomeChanges : [];
    const batchTurnChanges = Array.isArray(fieldChanges.batchTurnChanges) ? fieldChanges.batchTurnChanges : [];
    const allChanges = directChanges.concat(outcomeChanges, batchTurnChanges);
    if (allChanges.length > 0) {
      appendTextLine(target, allChanges.map(function (change) {
        if (!change || typeof change.field_path !== "string") {
          return "";
        }
        const nextValue =
          typeof change.new_value !== "undefined"
            ? change.new_value
            : change.new;
        return `${change.field_path}${typeof nextValue !== "undefined" ? ` \u2192 ${String(nextValue).slice(0, 40)}` : ""}`;
      }).filter(Boolean).join("; "), "#c4ccd6");
    }
  }

  if (panel.state.chatDetailJsonPath && turnId) {
    const detailLink = el("a", "view response \u2197");
    detailLink.href = `/vibecomfy/agent-edit/session-json?session_id=${encodeURIComponent(panel.state.sessionId || "")}`;
    detailLink.target = "_blank";
    detailLink.rel = "noopener";
    Object.assign(detailLink.style, {
      color: "#9ed0ff",
      textDecoration: "none",
    });
    target.appendChild(detailLink);
  }
}

// ── Welcome examples (shown in thread when no messages exist) ────────────

function _renderWelcomeExamples(body) {
  const welcome = el("div");
  Object.assign(welcome.style, {
    border: "1px solid #2d6fb5",
    borderRadius: "6px",
    background: "#111722",
    padding: "10px",
    display: "grid",
    gap: "6px",
  });
  const heading = el("div", "Try an example");
  Object.assign(heading.style, {
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#9da1ac",
    fontWeight: "600",
    marginBottom: "2px",
  });
  welcome.appendChild(heading);

  const examplePrompts = [
    "Add a code node that processes images with PIL",
    "Connect the output of LoadImage to a PreviewImage node",
    "Replace the CLIPTextEncode prompt text with something new",
    "Add a VAE Decode after the sampler output",
    "Wire the model output into a SaveImage node",
  ];
  for (const example of examplePrompts) {
    const row = el("div", example);
    Object.assign(row.style, {
      fontSize: "11px",
      color: "#9ed0ff",
      cursor: "pointer",
      padding: "4px 8px",
      borderRadius: "4px",
      background: "#0a1628",
      border: "1px solid #1e3355",
    });
    row.onclick = () => {
      const panel = currentAgentPanel();
      if (panel?.fields?.prompt) {
        panel.fields.prompt.value = example;
        panel.fields.prompt.focus();
      }
    };
    welcome.appendChild(row);
  }
  body.appendChild(welcome);
}

// ── Activity row rendering (live turn progress) ───────────────────────────

function populateActivityRows(body, panel, { sessionId = null } = {}) {
  _injectProgressPulseStyle();
  clearNode(body);

  const relevantTurns = Array.isArray(panel?.state?.turns)
    ? panel.state.turns.filter((entry) => {
      if (!entry) {
        return false;
      }
      if (sessionId && entry.session_id && entry.session_id !== sessionId) {
        return false;
      }
      return isLiveActivityTurn(entry);
    })
    : [];

  for (let index = 0; index < relevantTurns.length; index += 1) {
    const entry = relevantTurns[index];
    if (entry.entry_type === "batch") {
      _renderBatchTurnRow(body, panel, entry, index);
    } else {
      _renderDurableTurnRow(body, panel, entry, index);
    }
  }

  // Terminal durable turns and completed batch rows intentionally do not fall
  // back to the old persistent history cards. They live in bubble details.
}

function renderActivityRows(panel) {
  const mount = panel?.sections?.history;
  if (!mount) {
    return;
  }
  populateActivityRows(mount, panel);
  // Show the shared activity mount only when it contains rows; hide it when
  // empty to avoid consuming space in the thread area unnecessarily.
  const hasContent = mount.children.length > 0;
  mount.style.display = hasContent ? "" : "none";
  if (mount.parentNode?.className === "vibecomfy-agent-panel-region") {
    mount.parentNode.style.display = hasContent ? "" : "none";
  }
}

function scrollChatThreadToBottom(panel) {
  const container = panel?.thread;
  if (!container) {
    return;
  }
  const target = Number.isFinite(container.scrollHeight)
    ? container.scrollHeight
    : Math.max(0, (container.children?.length || 0) * 100);
  container.scrollTop = target;
  container.dataset.vibecomfyScrolledToBottom = "1";
}

function isChatThreadNearBottom(panel) {
  const container = panel?.thread;
  if (!container) {
    return true;
  }
  const scrollHeight = Number(container.scrollHeight);
  const clientHeight = Number(container.clientHeight);
  const scrollTop = Number(container.scrollTop);
  if (Number.isFinite(scrollHeight) && Number.isFinite(clientHeight) && Number.isFinite(scrollTop)) {
    const distanceFromBottom = scrollHeight - clientHeight - scrollTop;
    return distanceFromBottom <= THREAD_NEAR_BOTTOM_TOLERANCE_PX;
  }
  return container.dataset?.vibecomfyScrolledToBottom === "1";
}

function renderHistory(panel) {
  const threadState = ensureThreadRenderState(panel);
  const shouldAutoScroll = Boolean(threadState.forceScrollOnNextRender) || isChatThreadNearBottom(panel);
  const hasMessages = renderChatThread(panel);
  if (hasMessages && shouldAutoScroll) {
    scrollChatThreadToBottom(panel);
    threadState.forceScrollOnNextRender = false;
  } else if (panel?.thread) {
    panel.thread.dataset.vibecomfyScrolledToBottom = "0";
  }
}

function collectDiffRows(report) {
  const ce = report?.change?.content_edits || {};
  const rows = [];
  for (const uid of ce.preserved || []) {
    rows.push({ text: `preserved: ${uid}`, color: "#4caf50", title: null });
  }
  for (const uid of ce.edited || []) {
    rows.push({ text: `edited: ${uid}`, color: "#ffc107", title: null });
  }
  for (const uid of ce.new_auto_placed || []) {
    rows.push({ text: `new_auto_placed: ${uid}`, color: VC_COLORS.pending, title: null });
  }
  for (const uid of ce.removed || []) {
    rows.push({ text: `removed: ${uid}`, color: "#ff7f7f", title: null });
  }
  for (const item of ce.removed_named || []) {
    rows.push({
      text: `removed_named: ${item.uid} (${item.class_type || "unknown"})`,
      color: "#f44336",
      title: null,
    });
  }
  for (const item of ce.virtual_wires_degraded || []) {
    rows.push({
      text: `virtual_wires_degraded: ${item.uid || item.node_id || "unknown"}`,
      color: "#ffb86c",
      title: safeJson(item),
    });
  }
  for (const uid of ce.stripped_helpers || []) {
    rows.push({ text: `stripped_helper: ${uid}`, color: "#ff8f59", title: null });
  }
  // lowered entries from static lowering provenance
  for (const item of report?.change?.lowered || []) {
    const uid = item?.uid || item?.source_node_uid || "unknown";
    const count = item?.lowered_native_count ?? 0;
    rows.push({
      text: `lowered: ${uid} -> ${count} native node(s)`,
      color: LOWERED_DIFF_COLOR,
      title: null,
    });
  }
  return rows;
}

function extractChangedNodeFeedback(report) {
  const ce = report?.change?.content_edits || {};
  const items = [];
  for (const uid of ce.edited || []) {
    items.push({ uid, kind: "edited", color: "#ffc107", label: `Edited ${uid}` });
  }
  for (const uid of ce.new_auto_placed || []) {
    items.push({ uid, kind: "new_auto_placed", color: VC_COLORS.pending, label: `Added ${uid}` });
  }
  for (const uid of ce.removed || []) {
    items.push({ uid, kind: "removed", color: "#ff7f7f", label: `Removed ${uid}` });
  }
  for (const item of ce.removed_named || []) {
    items.push({
      uid: item?.uid || null,
      kind: "removed_named",
      color: "#f44336",
      label: `Removed ${item?.uid || "unknown"} (${item?.class_type || "unknown"})`,
      class_type: item?.class_type || null,
    });
  }
  for (const uid of ce.stripped_helpers || []) {
    items.push({ uid, kind: "stripped_helper", color: "#ff8f59", label: `Stripped helper ${uid}` });
  }
  for (const item of ce.virtual_wires_degraded || []) {
    const uid = item?.uid || item?.node_id || null;
    items.push({
      uid,
      kind: "virtual_wires_degraded",
      color: "#ffb86c",
      label: `Virtual wire degraded ${uid || "unknown"}`,
      detail: item || null,
    });
  }
  return items;
}

function getLiveGraph() {
  return app?.canvas?.graph || null;
}

function getLiveGraphNodes(graph) {
  if (!graph) {
    return [];
  }
  if (Array.isArray(graph._nodes)) {
    return graph._nodes;
  }
  if (Array.isArray(graph.nodes)) {
    return graph.nodes;
  }
  return [];
}

// ── Diff preview data model ───────────────────────────────────────────────

function getUid(node) {
  return node?.properties?.vibecomfy_uid || null;
}

function readWidgetValues(node) {
  if (Array.isArray(node?.widgets_values)) {
    return node.widgets_values;
  }
  if (Array.isArray(node?.widgets)) {
    return node.widgets.map((w) => (w && typeof w === "object" ? w.value : undefined));
  }
  return [];
}

function clearCandidatePreviewState(panel) {
  if (!panel) {
    return;
  }
  delete panel.state._previewDiff;
  delete panel.state._previewDiffGraphHash;
  _overlayDrawModelCache = null;
  try {
    const graph = getLiveGraph();
    if (graph) {
      if (typeof graph.setDirtyCanvas === "function") {
        graph.setDirtyCanvas(true, true);
      }
    }
  } catch (e) {
    // Best-effort: a failed dirty-canvas call should not block cleanup.
    console.warn("[vibecomfy] clearCandidatePreviewState canvas dirty failed:", e);
  }
}

function clearCandidateInvalidationSideEffects(repaint = true) {
  // Roundtrip-owned side effect: clear overlay draw model cache.
  _overlayDrawModelCache = null;
  // Repaint to clear the always-on candidate preview overlay from the canvas.
  // Callers that have ALREADY repainted (e.g. the post-Apply path, which just
  // ran applyGraphInPlaceWithIntentDecoration -> setDirtyCanvas and is now IDLE
  // so the overlay can't draw anyway) pass { repaint: false } to avoid a second,
  // redundant repaint of the same frame.
  if (repaint) {
    try {
      const graph = getLiveGraph();
      if (graph) {
        if (typeof graph.setDirtyCanvas === "function") {
          graph.setDirtyCanvas(true, true);
        }
      }
    } catch (e) {
      // Best-effort
    }
  }
}

export function computePreviewDiff(candidateGraph, candidateReport) {
  try {
    const panel = currentAgentPanel();
    const candidateGraphHash = panel?.state?.candidateGraphHash;
    if (
      candidateGraphHash
      && panel.state._previewDiffGraphHash === candidateGraphHash
      && panel.state._previewDiff
      && Array.isArray(panel.state._previewDiff.added_links)
      && Array.isArray(panel.state._previewDiff.removed_links)
      && Array.isArray(panel.state._previewDiff.edited_fields)
    ) {
      return panel.state._previewDiff;
    }

    const liveNodes = getLiveGraphNodes(getLiveGraph());
    const candidateNodes = Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : [];

    // ── Index by uid ──────────────────────────────────────────────────────
    // The candidate (server round-trip) stamps vibecomfy_uid on every node, but a
    // live canvas node may have none yet (a stock graph before any Apply). Map
    // candidate uid by LiteGraph node id so a uid-less live node can recover its
    // uid from its id — otherwise EVERY candidate node falsely looks "added".
    const candidateByUid = new Map();
    const candidateUidById = new Map();
    for (const node of candidateNodes) {
      const uid = getUid(node);
      if (uid) {
        candidateByUid.set(uid, node);
        if (node.id != null) {
          candidateUidById.set(String(node.id), uid);
        }
      }
    }
    const liveByUid = new Map();
    for (const node of liveNodes) {
      const uid = getUid(node)
        || (node.id != null ? candidateUidById.get(String(node.id)) : null);
      if (uid) {
        liveByUid.set(uid, node);
      }
    }

    // ── Edited: nodes present in both whose widget values differ ──────────
    const edited = [];
    for (const [uid, liveNode] of liveByUid) {
      const candidateNode = candidateByUid.get(uid);
      if (!candidateNode) {
        continue;
      }
      const liveValues = readWidgetValues(liveNode);
      const candidateValues = readWidgetValues(candidateNode);
      const maxLen = Math.max(liveValues.length, candidateValues.length);
      const changedWidgetIndices = [];
      for (let i = 0; i < maxLen; i += 1) {
        const a = liveValues[i];
        const b = candidateValues[i];
        if (!Object.is(a, b) && JSON.stringify(a) !== JSON.stringify(b)) {
          changedWidgetIndices.push(i);
        }
      }
      if (changedWidgetIndices.length > 0) {
        edited.push({
          uid,
          changedWidgetIndices,
        });
      }
    }

    // ── Added: candidate-only nodes with unwired required inputs ──────────
    const added = [];
    for (const [uid, candidateNode] of candidateByUid) {
      if (liveByUid.has(uid)) {
        continue;
      }
      const unwiredRequiredInputs = (Array.isArray(candidateNode.inputs) ? candidateNode.inputs : [])
        .filter((input) => !input?.link && !input?.widget)
        .map((input) => input?.name || null)
        .filter(Boolean);
      added.push({
        uid,
        class_type: candidateNode.type || candidateNode.class_type || null,
        unwiredRequiredInputs,
      });
    }

    // ── Removed: live-only nodes (by uid) ─────────────────────────────────
    const removed = [];
    for (const [uid, liveNode] of liveByUid) {
      if (!candidateByUid.has(uid)) {
        removed.push({
          uid,
          class_type: liveNode.type || liveNode.comfyClass || null,
        });
      }
    }

    // ── Removed named: from the backend report ────────────────────────────
    const removedNamed = (
      Array.isArray(candidateReport?.change?.content_edits?.removed_named)
        ? candidateReport.change.content_edits.removed_named
        : []
    ).map((item) => ({
      uid: item?.uid || null,
      class_type: item?.class_type || null,
    }));

    // ── Unresolved: report entries we cannot square with either graph ─────
    const unresolved = [];
    const reportEdited = Array.isArray(candidateReport?.change?.content_edits?.edited)
      ? candidateReport.change.content_edits.edited
      : [];
    const reportNew = Array.isArray(candidateReport?.change?.content_edits?.new_auto_placed)
      ? candidateReport.change.content_edits.new_auto_placed
      : [];
    const reportRemoved = Array.isArray(candidateReport?.change?.content_edits?.removed)
      ? candidateReport.change.content_edits.removed
      : [];

    for (const uid of reportEdited) {
      if (!liveByUid.has(uid) && !candidateByUid.has(uid)) {
        unresolved.push({ uid, kind: "edited", reason: "not found in live or candidate graph" });
      }
    }
    for (const uid of reportNew) {
      if (!candidateByUid.has(uid)) {
        unresolved.push({ uid, kind: "new_auto_placed", reason: "not found in candidate graph" });
      }
    }
    for (const uid of reportRemoved) {
      if (!liveByUid.has(uid)) {
        unresolved.push({ uid, kind: "removed", reason: "not found in live graph" });
      }
    }

    if (unresolved.length > 0) {
      console.warn("[vibecomfy] computePreviewDiff — unresolved report entries:", unresolved);
    }

    // ── Edited Fields: from normalized FieldChange data (T10) ────────────
    // Read panel.state.lastSubmitFieldChanges (populated by submitAgentEdit
    // after a round-trip response) and merge outcomeChanges with all batch
    // turn changes into a flat uid+field_path-keyed view for the overlay.
    // Resolve uids through the existing liveByUid/candidateByUid maps (which
    // already use getUid()/LiteGraph id fallback).
    const editedFields = [];
    if (panel?.state?.lastSubmitFieldChanges) {
      const seenFieldKeys = new Set();
      const lfs = panel.state.lastSubmitFieldChanges;

      // Collect all changes: outcome first, then batch turns
      const allFieldChanges = [
        ...(Array.isArray(lfs.outcomeChanges) ? lfs.outcomeChanges : []),
      ];
      if (Array.isArray(lfs.batchTurnChanges)) {
        for (const btc of lfs.batchTurnChanges) {
          if (Array.isArray(btc.changes)) {
            allFieldChanges.push(...btc.changes);
          }
        }
      }

      for (const fc of allFieldChanges) {
        if (!fc || !fc.uid || !fc.field_path) continue;
        // Resolve uid through liveByUid or candidateByUid (getUid/LiteGraph id fallback)
        if (!liveByUid.has(fc.uid) && !candidateByUid.has(fc.uid)) continue;
        const fieldKey = `${fc.uid}::${fc.field_path}`;
        if (seenFieldKeys.has(fieldKey)) continue;
        seenFieldKeys.add(fieldKey);

        // Format the new value for display
        let newValueDisplay;
        if (!("new" in fc)) {
          newValueDisplay = null;
        } else if (fc.new === null) {
          newValueDisplay = "null";
        } else if (fc.new === undefined) {
          newValueDisplay = null;
        } else if (typeof fc.new === "string") {
          newValueDisplay = fc.new;
        } else if (typeof fc.new === "number" || typeof fc.new === "boolean") {
          newValueDisplay = String(fc.new);
        } else if (Array.isArray(fc.new)) {
          newValueDisplay = "[…]";
        } else if (typeof fc.new === "object") {
          newValueDisplay = "{…}";
        } else {
          newValueDisplay = String(fc.new);
        }

        editedFields.push({
          uid: fc.uid,
          field_path: fc.field_path,
          new_value: newValueDisplay,
        });
      }
    }

    // ── Link diff: normalize by endpoint UID + port name ──────────────────
    // Build supplementary maps for link endpoint resolution.
    const candidateNodesById = new Map();
    for (const node of candidateNodes) {
      if (node.id != null) {
        candidateNodesById.set(String(node.id), node);
      }
    }
    const liveNodesById = new Map();
    for (const node of liveNodes) {
      if (node.id != null) {
        liveNodesById.set(String(node.id), node);
      }
    }
    const liveUidById = new Map();
    for (const node of liveNodes) {
      const uid = getUid(node);
      if (uid && node.id != null) {
        liveUidById.set(String(node.id), uid);
      }
    }

    let _unresolvableLinkWarnCount = 0;
    const _MAX_UNRESOLVABLE_LINK_WARNS = 5;

    function _resolvePortName(node, slotIndex, portsKey) {
      const ports = Array.isArray(node?.[portsKey]) ? node[portsKey] : [];
      const port = ports[slotIndex];
      if (port && typeof port.name === "string" && port.name) {
        return port.name;
      }
      return String(slotIndex);
    }

    function _normalizeLinkEndpoint(link, uidById, nodesById) {
      // link may be an array [origin_id, origin_slot, target_id, target_slot, …],
      // a LiteGraph array [link_id, origin_id, origin_slot, target_id, target_slot, …],
      // or an object { origin_id, origin_slot, target_id, target_slot, … }
      const hasLeadingLinkId = Array.isArray(link) && link.length >= 6;
      const originId = Array.isArray(link) ? link[hasLeadingLinkId ? 1 : 0] : link?.origin_id;
      const originSlot = Array.isArray(link) ? link[hasLeadingLinkId ? 2 : 1] : link?.origin_slot;
      const targetId = Array.isArray(link) ? link[hasLeadingLinkId ? 3 : 2] : link?.target_id;
      const targetSlot = Array.isArray(link) ? link[hasLeadingLinkId ? 4 : 3] : link?.target_slot;

      const fromUid = uidById.get(String(originId));
      const toUid = uidById.get(String(targetId));

      if (!fromUid || !toUid) {
        return null;
      }

      const fromNode = nodesById.get(String(originId));
      const toNode = nodesById.get(String(targetId));

      const fromPortName = _resolvePortName(fromNode, originSlot, "outputs");
      const toPortName = _resolvePortName(toNode, targetSlot, "inputs");

      return `${fromUid}::${fromPortName}->${toUid}::${toPortName}`;
    }

    function _collectNormalizedLinkKeys(linkEntries, uidById, nodesById) {
      const keys = new Set();
      for (const link of linkEntries) {
        if (!link) continue;
        const key = _normalizeLinkEndpoint(link, uidById, nodesById);
        if (key) {
          keys.add(key);
        } else if (_unresolvableLinkWarnCount < _MAX_UNRESOLVABLE_LINK_WARNS) {
          _unresolvableLinkWarnCount += 1;
          console.warn("[vibecomfy] computePreviewDiff — unresolvable link endpoint:", link);
        }
      }
      return keys;
    }

    // Live links: LiteGraph stores links as an object map keyed by link id.
    const liveLinkEntries = (() => {
      const liveGraph = getLiveGraph();
      const raw = liveGraph?.links;
      if (!raw || typeof raw !== "object") return [];
      return Array.isArray(raw) ? raw : Object.values(raw);
    })();
    const candidateLinkEntries = Array.isArray(candidateGraph?.links) ? candidateGraph.links : [];

    const liveLinkKeys = _collectNormalizedLinkKeys(
      liveLinkEntries,
      liveUidById,
      liveNodesById,
    );
    const candidateLinkKeys = _collectNormalizedLinkKeys(
      candidateLinkEntries,
      candidateUidById,
      candidateNodesById,
    );

    const added_links = [];
    for (const key of candidateLinkKeys) {
      if (!liveLinkKeys.has(key)) {
        added_links.push(key);
      }
    }
    const removed_links = [];
    for (const key of liveLinkKeys) {
      if (!candidateLinkKeys.has(key)) {
        removed_links.push(key);
      }
    }

    const linkEditedUids = new Set();
    const _parseLinkKey = (key) => {
      const text = String(key || "");
      const arrowIndex = text.indexOf("->");
      if (arrowIndex < 0) return null;
      const sourceText = text.slice(0, arrowIndex);
      const targetText = text.slice(arrowIndex + 2);
      const sourceSep = sourceText.indexOf("::");
      const targetSep = targetText.indexOf("::");
      if (sourceSep < 0 || targetSep < 0) return null;
      const fromUid = sourceText.slice(0, sourceSep);
      const fromPort = sourceText.slice(sourceSep + 2);
      const toUid = targetText.slice(0, targetSep);
      const toPort = targetText.slice(targetSep + 2);
      if (!fromUid || !toUid) return null;
      return {
        fromUid,
        fromPort,
        toUid,
        toPort,
        sourceKey: `${fromUid}::${fromPort}`,
        targetKey: `${toUid}::${toPort}`,
      };
    };
    const _sourcesByTarget = (keys) => {
      const grouped = new Map();
      for (const key of keys) {
        const parsed = _parseLinkKey(key);
        if (!parsed) continue;
        if (!grouped.has(parsed.targetKey)) {
          grouped.set(parsed.targetKey, { uid: parsed.toUid, sources: new Set() });
        }
        grouped.get(parsed.targetKey).sources.add(parsed.sourceKey);
      }
      return grouped;
    };
    const _sameSet = (left, right) => {
      if (left.size !== right.size) return false;
      for (const value of left) {
        if (!right.has(value)) return false;
      }
      return true;
    };
    const addedSourcesByTarget = _sourcesByTarget(added_links);
    const removedSourcesByTarget = _sourcesByTarget(removed_links);
    const changedTargetKeys = new Set([
      ...addedSourcesByTarget.keys(),
      ...removedSourcesByTarget.keys(),
    ]);
    for (const targetKey of changedTargetKeys) {
      const addedTarget = addedSourcesByTarget.get(targetKey);
      const removedTarget = removedSourcesByTarget.get(targetKey);
      const uid = addedTarget?.uid || removedTarget?.uid || null;
      if (!uid || !liveByUid.has(uid) || !candidateByUid.has(uid)) {
        continue;
      }
      const addedSources = addedTarget?.sources || new Set();
      const removedSources = removedTarget?.sources || new Set();
      if (!_sameSet(addedSources, removedSources)) {
        linkEditedUids.add(uid);
      }
    }
    const editedByUid = new Map(edited.map((entry) => [entry.uid, entry]));
    for (const uid of linkEditedUids) {
      if (!editedByUid.has(uid)) {
        const entry = { uid, changedWidgetIndices: [] };
        editedByUid.set(uid, entry);
        edited.push(entry);
      }
    }

    const diff = {
      edited,
      edited_fields: editedFields,
      added,
      removed,
      removed_named: removedNamed,
      unresolved,
      added_links,
      removed_links,
    };

    // ── Cache on panel state ──────────────────────────────────────────────
    if (panel && candidateGraphHash) {
      panel.state._previewDiff = diff;
      panel.state._previewDiffGraphHash = candidateGraphHash;
    }

    return diff;
  } catch (e) {
    console.warn("[vibecomfy] computePreviewDiff failed, returning empty diff:", e);
    return {
      edited: [],
      edited_fields: [],
      added: [],
      removed: [],
      removed_named: [],
      unresolved: [],
      added_links: [],
      removed_links: [],
    };
  }
}

function getOrBuildPreviewDiff() {
  const panel = currentAgentPanel();
  if (!panel) {
    return null;
  }
  const candidateGraph = panel.state.candidateGraph;
  const candidateReport = panel.state.candidateReport;
  if (!candidateGraph || !candidateReport) {
    return null;
  }
  const candidateGraphHash = panel.state.candidateGraphHash;
  if (
    panel.state._previewDiff &&
    panel.state._previewDiffGraphHash === candidateGraphHash &&
    Array.isArray(panel.state._previewDiff.added_links) &&
    Array.isArray(panel.state._previewDiff.removed_links) &&
    Array.isArray(panel.state._previewDiff.edited_fields)
  ) {
    return panel.state._previewDiff;
  }
  return computePreviewDiff(candidateGraph, candidateReport);
}

function _graphNodeCount(graph) {
  return Array.isArray(graph?.nodes) ? graph.nodes.length : 0;
}

export function vecNumber(vec, i, fb) {
  const value = vec != null ? Number(vec[i]) : NaN;
  return Number.isFinite(value) ? value : fb;
}

export function readNodeSize(node, fbW = 200, fbH = 100) {
  return {
    w: vecNumber(node?.size, 0, fbW),
    h: vecNumber(node?.size, 1, fbH),
  };
}

function readNodePos(node, fbX = 0, fbY = 0) {
  return {
    x: vecNumber(node?.pos, 0, fbX),
    y: vecNumber(node?.pos, 1, fbY),
  };
}

function readNodeBounding(node, titleHeight) {
  if (node && typeof node.getBounding === "function") {
    try {
      const bounds = node.getBounding();
      if (bounds) {
        if (Array.isArray(bounds) || typeof bounds.length === "number") {
          const x = vecNumber(bounds, 0, NaN);
          const y = vecNumber(bounds, 1, NaN);
          const w = vecNumber(bounds, 2, NaN);
          const h = vecNumber(bounds, 3, NaN);
          if ([x, y, w, h].every(Number.isFinite)) {
            return { x, y, w, h };
          }
        } else if (typeof bounds === "object") {
          const x = Number(bounds.x);
          const y = Number(bounds.y);
          const w = Number(bounds.w ?? bounds.width);
          const h = Number(bounds.h ?? bounds.height);
          if ([x, y, w, h].every(Number.isFinite)) {
            return { x, y, w, h };
          }
        }
      }
    } catch (_ignored) {
      // Fall back to pos/size below.
    }
  }
  const pos = readNodePos(node);
  const size = readNodeSize(node);
  return { x: pos.x, y: pos.y - titleHeight, w: size.w, h: size.h + titleHeight };
}

function _overlayDrawCacheKey(diff, candidateGraph) {
  const candidateHash =
    diff?._candidateGraphHash
    || currentAgentPanel()?.state?.candidateGraphHash
    || `inline:${_graphNodeCount(candidateGraph)}:${Array.isArray(candidateGraph?.links) ? candidateGraph.links.length : 0}`;
  const liveRevision = captureLiveCanvasRevision();
  return `${candidateHash}:${liveRevision == null ? "unknown" : liveRevision}`;
}

function _buildOverlayDrawModel(ctx, diff, candidateGraph) {
  const key = _overlayDrawCacheKey(diff, candidateGraph);
  if (_overlayDrawModelCache?.key === key) {
    return _overlayDrawModelCache.model;
  }
  const liveByUid = new Map();
  for (const node of getLiveGraphNodes(getLiveGraph())) {
    const uid = getUid(node);
    if (uid) {
      liveByUid.set(uid, node);
    }
  }
  const candidateByUid = new Map();
  for (const node of Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : []) {
    const uid = getUid(node);
    if (uid) {
      candidateByUid.set(uid, node);
    }
  }
  const addedByUid = new Map();
  for (const item of Array.isArray(diff?.added) ? diff.added : []) {
    if (item?.uid) {
      addedByUid.set(item.uid, item);
    }
  }
  const ghostDimsByUid = new Map();
  for (const [uid, node] of candidateByUid) {
    if (!addedByUid.has(uid)) {
      continue;
    }
    const nodeSize = readNodeSize(node, NaN, NaN);
    if (nodeSize.w > 40 && nodeSize.h > 20) {
      ghostDimsByUid.set(uid, nodeSize);
      continue;
    }
    ghostDimsByUid.set(uid, _computeGhostDimensions(node, ctx));
  }
  const model = {
    liveByUid,
    candidateByUid,
    addedByUid,
    ghostDimsByUid,
    unresolvedWarnCount: 0,
  };
  _overlayDrawModelCache = { key, model };
  return model;
}

function _warnOverlayUnresolved(model, message, detail) {
  if (!model || model.unresolvedWarnCount >= 5) {
    return;
  }
  model.unresolvedWarnCount += 1;
  console.warn(message, detail);
}

// ── Ghost dimension computation (T3) ──────────────────────────────────────
// Compute plausible width and height from node content when cn.size is
// missing or implausible (w ≤ 40 or h ≤ 20). Uses LiteGraph constants,
// title text, non-empty slot labels, truncated widget_values, slot counts,
// widget rows, and padding.
function _computeGhostDimensions(cn, ctx) {
  var TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
  var SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
  var WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
  var PAD_X = 32; // room for slot circles + margins
  var PAD_Y = 12;
  var MIN_W = 140;

  var title = (typeof cn.title === "string" && cn.title) || (typeof cn.type === "string" && cn.type) || "Node";
  var inputs = Array.isArray(cn.inputs) ? cn.inputs : [];
  var outputs = Array.isArray(cn.outputs) ? cn.outputs : [];
  var widgetValues = readWidgetValues(cn);

  // Truncate helper — uses Unicode ellipsis (SD3).
  var _trunc = function (text, maxChars) {
    text = String(text || "").trim();
    if (!text) return "";
    return text.length > maxChars ? text.slice(0, maxChars - 1) + "\u2026" : text;
  };

  ctx.save();
  try {
    ctx.font = "12px Arial, sans-serif";
    ctx.textBaseline = "top";

    var titleW = ctx.measureText(_trunc(title, 40)).width;

    var maxSlotW = 0;
    for (var s = 0; s < inputs.length; s += 1) {
      var lbl = inputs[s] && inputs[s].name;
      if (lbl) maxSlotW = Math.max(maxSlotW, ctx.measureText(_trunc(lbl, 30)).width);
    }
    for (var t = 0; t < outputs.length; t += 1) {
      var olbl = outputs[t] && outputs[t].name;
      if (olbl) maxSlotW = Math.max(maxSlotW, ctx.measureText(_trunc(olbl, 30)).width);
    }

    var maxWidgetW = 0;
    for (var wi = 0; wi < widgetValues.length; wi += 1) {
      var wvText = _trunc(widgetValuePreviewText(widgetValues[wi]), 35);
      if (wvText) maxWidgetW = Math.max(maxWidgetW, ctx.measureText(wvText).width);
    }

    var contentW = Math.max(titleW, maxSlotW, maxWidgetW);
    var gw = Math.max(MIN_W, Math.ceil(contentW + PAD_X));

    var inCount = inputs.length;
    var outCount = outputs.length;
    var wRows = widgetValues.length;
    var slotRows = Math.max(inCount, outCount);
    var gh = TITLE_H + slotRows * SLOT_H + wRows * WIDGET_H + PAD_Y;

    return { w: gw, h: gh };
  } finally {
    ctx.restore();
  }
}

// ── Widget-value preview text (T3) ────────────────────────────────────────
function widgetValuePreviewText(value) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return "[…]";
  return "{…}";
}

export function drawPreviewOverlay(ctx, diff) {
  if (!ctx || !diff) {
    return;
  }
  ctx.save();
  try {
    if (ctx.setLineDash) {
      ctx.setLineDash([]);
    }

    var editedColor = VC_COLORS.edited;
    var editedFill = hexToRgba(VC_COLORS.edited, 0.16);
    var addedColor = VC_COLORS.added;
    var addedFill = hexToRgba(VC_COLORS.added, 0.18);
    var addedTextColor = hexToRgba(VC_COLORS.added, 0.92);
    var removedColor = VC_COLORS.removed;
    var removedFill = hexToRgba(VC_COLORS.removed, 0.16);
    var TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
    var SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
    var WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
    var panel = currentAgentPanel();
    var candidateGraph = (diff && diff._candidateGraph) || (panel && panel.state && panel.state.candidateGraph);
    var drawModel = _buildOverlayDrawModel(ctx, diff, candidateGraph);
    var liveByUid = drawModel.liveByUid;
    var candidateByUid = drawModel.candidateByUid;
    var addedByUid = drawModel.addedByUid;

    var _drawBadge = function (bx, by, text, color) {
      ctx.save();
      if (ctx.setLineDash) {
        ctx.setLineDash([]);
      }
      ctx.font = "bold 12px sans-serif";
      var padX = 5;
      var bw = ctx.measureText(text).width + padX * 2;
      var bh = 18;
      ctx.fillStyle = color;
      ctx.fillRect(bx, by - bh, bw, bh);
      ctx.fillStyle = "#000000";
      ctx.textBaseline = "middle";
      ctx.fillText(text, bx + padX, by - bh / 2 + 1);
      ctx.restore();
    };

    var _drawFullBoxMarker = function (bounds, strokeColor, fillColor, dashed) {
      ctx.setLineDash(dashed ? [6, 3] : []);
      ctx.fillStyle = fillColor;
      ctx.fillRect(bounds.x - 2, bounds.y - 2, bounds.w + 4, bounds.h + 4);
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 2;
      ctx.strokeRect(bounds.x - 2, bounds.y - 2, bounds.w + 4, bounds.h + 4);
      ctx.setLineDash([]);
    };

    var _drawRoundedPanel = function (x, y, w, h, radius, fillStyle, strokeStyle) {
      ctx.fillStyle = fillStyle;
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 1;
      if (typeof ctx.roundRect === "function") {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, radius);
        ctx.fill();
        ctx.stroke();
        return;
      }
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x, y, w, h);
    };

    // ── Truncation helper (Unicode ellipsis, SD3) ────────────────────────
    var _trunc = function (text, maxChars) {
      text = String(text || "").trim();
      if (!text) return "";
      return text.length > maxChars ? text.slice(0, maxChars - 1) + "\u2026" : text;
    };

    var _fitTextToWidth = function (text, maxWidth) {
      text = String(text == null ? "" : text);
      if (!text || maxWidth <= 0) return "";
      if (ctx.measureText(text).width <= maxWidth) return text;
      var ellipsis = "\u2026";
      var lo = 0;
      var hi = text.length;
      while (lo < hi) {
        var mid = Math.ceil((lo + hi) / 2);
        if (ctx.measureText(text.slice(0, mid) + ellipsis).width <= maxWidth) {
          lo = mid;
        } else {
          hi = mid - 1;
        }
      }
      return lo > 0 ? text.slice(0, lo) + ellipsis : ellipsis;
    };

    var _widgetIndexFromFieldPath = function (fieldPath) {
      var path = String(fieldPath || "");
      var direct = /(?:^|\.)(?:widgets_values|widgets)\.(\d+)(?:\.|$)/.exec(path);
      if (direct) return Number(direct[1]);
      var widgetKey = /^widget_(\d+)$/.exec(path);
      if (widgetKey) return Number(widgetKey[1]);
      return null;
    };

    var _fieldNameCandidates = function (fieldPath) {
      var path = String(fieldPath || "");
      if (!path) return [];
      var normalized = path.replace(/\[(\d+)\]/g, ".$1");
      var parts = normalized.split(".").filter(Boolean);
      var last = parts.length ? parts[parts.length - 1] : normalized;
      return [normalized, last];
    };

    var _resolveWidgetFieldIndex = function (field, node) {
      var directIndex = _widgetIndexFromFieldPath(field && field.field_path);
      if (directIndex != null && Number.isFinite(directIndex)) {
        return directIndex;
      }
      var widgetsForNode = Array.isArray(node && node.widgets) ? node.widgets : [];
      if (widgetsForNode.length === 0) {
        return null;
      }
      var candidates = _fieldNameCandidates(field && field.field_path);
      for (var ci = 0; ci < candidates.length; ci += 1) {
        var candidateName = candidates[ci];
        for (var wi = 0; wi < widgetsForNode.length; wi += 1) {
          var widget = widgetsForNode[wi];
          var widgetNames = [widget && widget.name, widget && widget.label].filter(Boolean);
          for (var ni = 0; ni < widgetNames.length; ni += 1) {
            if (String(widgetNames[ni]) === candidateName) {
              return wi;
            }
          }
        }
      }
      return null;
    };

    var _formatFieldLabel = function (field) {
      var label = field && field.field_path ? String(field.field_path) : "field";
      if (field && field.new_value !== null && field.new_value !== undefined) {
        label += ": " + field.new_value;
      }
      return _trunc(label, 48);
    };

    var _fieldNewValueLabel = function (field) {
      if (!field || field.new_value === null || field.new_value === undefined) {
        return "";
      }
      return String(field.new_value);
    };

    var editedFieldsByUid = new Map();
    if (diff.edited_fields && diff.edited_fields.length > 0) {
      for (var _efg = 0; _efg < diff.edited_fields.length; _efg += 1) {
        var groupedField = diff.edited_fields[_efg];
        if (!groupedField || !groupedField.uid) continue;
        if (!editedFieldsByUid.has(groupedField.uid)) {
          editedFieldsByUid.set(groupedField.uid, []);
        }
        editedFieldsByUid.get(groupedField.uid).push(groupedField);
      }
    }

    var _hasEditedLinkTarget = function (uid) {
      if (!uid) return false;
      var needle = "->" + uid + "::";
      var addedLinks = Array.isArray(diff.added_links) ? diff.added_links : [];
      var removedLinks = Array.isArray(diff.removed_links) ? diff.removed_links : [];
      for (var ai = 0; ai < addedLinks.length; ai += 1) {
        if (String(addedLinks[ai]).indexOf(needle) !== -1) return true;
      }
      for (var ri = 0; ri < removedLinks.length; ri += 1) {
        if (String(removedLinks[ri]).indexOf(needle) !== -1) return true;
      }
      return false;
    };

    var _drawWidgetValueOverlay = function (bounds, valueText, labelText) {
      var padX = 7;
      var rightPad = 8;
      // Cover the WHOLE value area (everything right of the field label) so a
      // long old value (e.g. a 15-digit seed) cannot peek out beside the panel.
      var labelReserve = 56; // "◀ " arrow + minimum label room
      try {
        ctx.font = "11px Arial, sans-serif";
        if (typeof labelText === "string" && labelText && typeof ctx.measureText === "function") {
          var lm = ctx.measureText(labelText);
          if (lm && Number.isFinite(lm.width)) {
            labelReserve = Math.max(labelReserve, lm.width + 34);
          }
        }
      } catch (_e) { /* keep default reserve */ }
      var overlayW = Math.max(48, bounds.w - rightPad - labelReserve);
      overlayW = Math.min(overlayW, bounds.w - 12);
      if (!Number.isFinite(overlayW) || overlayW <= 0) return;
      var overlayX = bounds.x + bounds.w - rightPad - overlayW;
      var overlayY = bounds.y + 2;
      var overlayH = Math.max(bounds.h - 4, 12);
      _drawRoundedPanel(
        overlayX,
        overlayY,
        overlayW,
        overlayH,
        5,
        "rgba(20,18,8,0.92)",
        hexToRgba(VC_COLORS.edited, 0.95),
      );
      ctx.save();
      try {
        if (typeof ctx.rect === "function" && typeof ctx.clip === "function") {
          ctx.beginPath();
          ctx.rect(overlayX, overlayY, overlayW, overlayH);
          ctx.clip();
        }
        ctx.font = "11px Arial, sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = "right";
        ctx.fillStyle = hexToRgba(VC_COLORS.edited, 0.98);
        var fitted = _fitTextToWidth(valueText, Math.max(overlayW - padX * 2, 4));
        ctx.fillText(fitted, overlayX + overlayW - padX, overlayY + overlayH / 2);
      } finally {
        ctx.restore();
      }
    };

    // ── Edited nodes (amber outline) ────────────────────────────────────
    // LiteGraph: node.pos[1] is the top of the node BODY; the title bar is drawn
    // ABOVE it (getBounding() top = pos[1] - NODE_TITLE_HEIGHT) and node.size is
    // the body size, excluding the title. So the full visual box is
    // [pos[0], pos[1]-TITLE_H, size[0], size[1]+TITLE_H].
    for (var _ei = 0; _ei < (diff.edited || []).length; _ei += 1) {
      var eitem = diff.edited[_ei];
      var enode = liveByUid.get(eitem.uid);
      if (!enode || !enode.pos) {
        continue;
      }
      var epos = readNodePos(enode);
      var ex = epos.x;
      var ey = epos.y;
      var esize = readNodeSize(enode);
      var ew = esize.w;
      var collapsed = !!(enode.flags && enode.flags.collapsed);
      var eh = collapsed ? 0 : esize.h;
      var eb = readNodeBounding(enode, TITLE_H);
      // Mark the WHOLE node: title bar (above pos[1]) + body.
      _drawFullBoxMarker(eb, editedColor, editedFill, false);
      if (collapsed) {
        continue; // no widget rows to tint when collapsed
      }
      // Tint the changed widget rows. Prefer the live node's own per-widget
      // geometry (widget.last_y, set by LiteGraph each draw in body-local
      // coords) for pixel-faithful placement; fall back to computed row
      // geometry below the slot area when last_y is unavailable.
      var widgets = Array.isArray(enode.widgets) ? enode.widgets : [];
      var inCount = Array.isArray(enode.inputs) ? enode.inputs.length : 0;
      var outCount = Array.isArray(enode.outputs) ? enode.outputs.length : 0;
      var slotRows = Math.max(inCount, outCount);
      var computedRowsTop = ey + slotRows * SLOT_H;
      var widgetRowBounds = new Map();
      var _rowBoundsForWidgetIndex = function (widx) {
        if (widgetRowBounds.has(widx)) {
          return widgetRowBounds.get(widx);
        }
        var w = widgets[widx];
        var rowTop;
        var rowH = WIDGET_H;
        if (w && typeof w.last_y === "number") {
          // last_y is body-local (relative to pos[1]).
          rowTop = ey + w.last_y;
          if (typeof w.computeSize === "function") {
            try {
              var cs = w.computeSize(ew);
              if (cs && typeof cs[1] === "number" && cs[1] > 0) {
                rowH = cs[1];
              }
            } catch (e) { /* fall back to WIDGET_H */ }
          }
        } else {
          rowTop = computedRowsTop + widx * WIDGET_H;
        }
        var bounds = { x: ex, y: rowTop, w: ew, h: rowH };
        widgetRowBounds.set(widx, bounds);
        return bounds;
      };
      ctx.fillStyle = hexToRgba(VC_COLORS.edited, 0.22);
      for (var _wi = 0; _wi < (eitem.changedWidgetIndices || []).length; _wi += 1) {
        var widx = eitem.changedWidgetIndices[_wi];
        var rowBounds = _rowBoundsForWidgetIndex(widx);
        ctx.fillRect(rowBounds.x, rowBounds.y, rowBounds.w, Math.max(rowBounds.h - 2, 4));
      }

      var fieldsForNode = editedFieldsByUid.get(eitem.uid) || [];
      var nonWidgetFields = [];
      var drawnWidgetFieldIndexes = new Set();
      for (var _efi = 0; _efi < fieldsForNode.length; _efi += 1) {
        var ef = fieldsForNode[_efi];
        var resolvedWidgetIndex = _resolveWidgetFieldIndex(ef, enode);
        if (resolvedWidgetIndex != null && Number.isFinite(resolvedWidgetIndex) && resolvedWidgetIndex >= 0) {
          if (!drawnWidgetFieldIndexes.has(resolvedWidgetIndex)) {
            drawnWidgetFieldIndexes.add(resolvedWidgetIndex);
            var _overlayWidget = widgets[resolvedWidgetIndex];
            _drawWidgetValueOverlay(
              _rowBoundsForWidgetIndex(resolvedWidgetIndex),
              _fieldNewValueLabel(ef),
              _overlayWidget && typeof _overlayWidget.name === "string" ? _overlayWidget.name : null,
            );
          }
        } else {
          nonWidgetFields.push(ef);
        }
      }

      if (nonWidgetFields.length > 0 || _hasEditedLinkTarget(eitem.uid)) {
        var chipLabel = nonWidgetFields.length > 0
          ? _formatFieldLabel(nonWidgetFields[0])
          : "inputs changed";
        _drawBadge(ex + 4, ey + eh - 2, chipLabel, editedColor);
      }
    }

    // ── Removed nodes (red outline + "− will be removed" badge) ─────────
    var removedItems = (diff.removed || []).concat(diff.removed_named || []);
    for (var _ri = 0; _ri < removedItems.length; _ri += 1) {
      var ritem = removedItems[_ri];
      var rnode = liveByUid.get(ritem.uid);
      if (!rnode || !rnode.pos) {
        continue;
      }
      var rb = readNodeBounding(rnode, TITLE_H);
      var rx = rb.x;
      var ry = rb.y;
      var rw = rb.w;
      var rh = rb.h;
      _drawFullBoxMarker(rb, removedColor, removedFill, false);
      _drawBadge(rx + rw - 2 - 140, ry + rh - 2, "\u2212 will be removed", removedColor);
    }

    // ── Added nodes (translucent green ghost + "+ new" badge; candidate pos) ─
    if (candidateGraph && diff.added && diff.added.length > 0) {
      var candidateNodes = Array.isArray(candidateGraph.nodes)
        ? candidateGraph.nodes
        : [];
      for (var i = 0; i < candidateNodes.length; i += 1) {
        var cn = candidateNodes[i];
        var uid =
          cn && cn.properties ? cn.properties.vibecomfy_uid : undefined;
        if (!uid || !addedByUid.has(uid)) {
          continue;
        }
        var pos = cn.pos;
        if (!pos || typeof pos.length !== "number" || pos.length < 2) {
          continue;
        }
        var cpos = readNodePos(cn);
        var cx = cpos.x;
        var cy = cpos.y;

        // ── Dimension resolution: use cn.size only when plausible ────────
        var sizeValid = false;
        var cw, ch;
        var csize = readNodeSize(cn, NaN, NaN);
        if (csize.w > 40 && csize.h > 20) {
          cw = csize.w;
          ch = csize.h;
          sizeValid = true;
        }
        if (!sizeValid) {
          var dims = drawModel.ghostDimsByUid.get(uid) || _computeGhostDimensions(cn, ctx);
          cw = dims.w;
          ch = dims.h;
        }

        // ── Ghost full-box marker + dashed border ────────────────────────
        _drawFullBoxMarker({ x: cx, y: cy, w: cw, h: ch }, addedColor, addedFill, true);

        // ── Render ghost content: title, slot labels, widget rows ────────
        ctx.save();
        try {
          ctx.font = "12px Arial, sans-serif";
          ctx.textBaseline = "top";

          // Title
          var titleText = (typeof cn.title === "string" && cn.title) || (typeof cn.type === "string" && cn.type) || "Node";
          var displayTitle = _trunc(titleText, 40);
          ctx.fillStyle = addedTextColor;
          ctx.fillText(displayTitle, cx + 10, cy + (TITLE_H - 14) / 2);

          // Slot labels
          var inputs = Array.isArray(cn.inputs) ? cn.inputs : [];
          var outputs = Array.isArray(cn.outputs) ? cn.outputs : [];
          var widgetValues = readWidgetValues(cn);
          var maxSlots = Math.max(inputs.length, outputs.length);

          for (var si = 0; si < maxSlots; si += 1) {
            var slotY = cy + TITLE_H + si * SLOT_H + 2;
            // Input label (left side)
            if (si < inputs.length && inputs[si] && inputs[si].name) {
              ctx.fillStyle = addedTextColor;
              ctx.textAlign = "left";
              ctx.fillText(_trunc(inputs[si].name, 30), cx + 16, slotY);
            }
            // Output label (right side)
            if (si < outputs.length && outputs[si] && outputs[si].name) {
              ctx.fillStyle = addedTextColor;
              ctx.textAlign = "right";
              ctx.fillText(_trunc(outputs[si].name, 30), cx + cw - 16, slotY);
            }
          }

          // Widget-value rows (below slots)
          ctx.textAlign = "left";
          ctx.fillStyle = hexToRgba(VC_COLORS.added, 0.55);
          var widgetTop = cy + TITLE_H + maxSlots * SLOT_H;
          for (var wri = 0; wri < widgetValues.length; wri += 1) {
            var wvPreview = widgetValuePreviewText(widgetValues[wri]);
            if (wvPreview) {
              ctx.fillText(_trunc(wvPreview, 35), cx + 10, widgetTop + wri * WIDGET_H + 2);
            }
          }
        } finally {
          ctx.restore();
        }

        // ── "+ new" badge at bottom-right ────────────────────────────────
        _drawBadge(cx + cw - 2 - 64, cy + ch - 2, "+ new", addedColor);

        // Red dot on each unwired required input port of the added node.
        var addedEntry = addedByUid.get(uid);
        var unwired = (addedEntry && addedEntry.unwiredRequiredInputs) || [];
        if (unwired.length > 0) {
          var cinputs = Array.isArray(cn.inputs) ? cn.inputs : [];
          ctx.fillStyle = removedColor;
          for (var si = 0; si < cinputs.length; si += 1) {
            var inm = cinputs[si] && cinputs[si].name;
            if (inm && unwired.indexOf(inm) !== -1) {
              ctx.beginPath();
              ctx.arc(cx, cy + TITLE_H + (si + 0.5) * SLOT_H, 4, 0, Math.PI * 2);
              ctx.fill();
            }
          }
        }
      }
    }

    // ── Wire overlay: removed (dashed red) then added (solid green) ──────
    // Uses VC_COLORS for palette consistency.  Resolves link endpoints by
    // port name to slot indexes at draw time.  Live nodes prefer
    // node.getConnectionPos(isInput, slotIndex); ghost (candidate-only)
    // nodes use geometry derived from ghost rect slot rows.
    if (candidateGraph && ((diff.removed_links && diff.removed_links.length > 0) || (diff.added_links && diff.added_links.length > 0))) {
      // Parse link key "fromUid::fromPortName->toUid::toPortName"
      function _parseKey(k) {
        var m = k.match(/^(.+?)::(.+?)->(.+?)::(.+?)$/);
        if (!m) return null;
        return { fromUid: m[1], fromPort: m[2], toUid: m[3], toPort: m[4] };
      }

      // Slot index by port name
      function _slotIdx(node, portName, portsKey) {
        var ports = Array.isArray(node && node[portsKey]) ? node[portsKey] : [];
        for (var _pi = 0; _pi < ports.length; _pi += 1) {
          if (ports[_pi] && ports[_pi].name === portName) return _pi;
        }
        return -1;
      }

      // Connection position: live node.getConnectionPos, then geometry fallback
      function _connPos(node, isInput, slotIdx, ghostPos, ghostW) {
        if (node && typeof node.getConnectionPos === 'function') {
          try {
            return node.getConnectionPos(isInput, slotIdx);
          } catch (_ignored) { /* fall through */ }
        }
        // Live geometry
        if (node && node.pos && typeof node.pos.length === "number" && node.pos.length >= 2) {
          var _npos = readNodePos(node);
          var _nx = _npos.x;
          var _ny = _npos.y;
          var _nw = readNodeSize(node).w;
          if (isInput) return [_nx, _ny + TITLE_H + slotIdx * SLOT_H + SLOT_H / 2];
          return [_nx + _nw, _ny + TITLE_H + slotIdx * SLOT_H + SLOT_H / 2];
        }
        // Ghost geometry (candidate-only node)
        if (ghostPos && typeof ghostPos.length === "number" && ghostPos.length >= 2) {
          var _gx = vecNumber(ghostPos, 0, 0);
          var _gy = vecNumber(ghostPos, 1, 0);
          if (isInput) return [_gx, _gy + TITLE_H + slotIdx * SLOT_H + SLOT_H / 2];
          return [_gx + ghostW, _gy + TITLE_H + slotIdx * SLOT_H + SLOT_H / 2];
        }
        return null;
      }

      // Bezier wire stroke helper
      function _strokeWire(x1, y1, x2, y2, color, dashed) {
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        if (ctx.setLineDash) ctx.setLineDash(dashed ? [8, 4] : []);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        var _dx = Math.abs(x2 - x1) * 0.5;
        ctx.bezierCurveTo(x1 + _dx, y1, x2 - _dx, y2, x2, y2);
        ctx.stroke();
        ctx.restore();
      }

      // Ghost dimension helper (mirrors added-node logic)
      function _ghostDims(cn) {
        var _uid = getUid(cn);
        if (_uid && drawModel.ghostDimsByUid.has(_uid)) {
          return drawModel.ghostDimsByUid.get(_uid);
        }
        var _rs = readNodeSize(cn, NaN, NaN);
        if (_rs.w > 40 && _rs.h > 20) {
          return _rs;
        }
        return _computeGhostDimensions(cn, ctx);
      }

      // ── Removed wires: dashed red beziers (drawn first) ──────────────
      var _remLinks = diff.removed_links || [];
      for (var _rli = 0; _rli < _remLinks.length; _rli += 1) {
        var _p = _parseKey(_remLinks[_rli]);
        if (!_p) continue;

        var _fNode = liveByUid.get(_p.fromUid);
        var _tNode = liveByUid.get(_p.toUid);

        var _fSlot = _slotIdx(_fNode, _p.fromPort, 'outputs');
        var _tSlot = _slotIdx(_tNode, _p.toPort, 'inputs');

        if (_fSlot < 0 || _tSlot < 0) {
          _warnOverlayUnresolved(drawModel, '[vibecomfy] drawPreviewOverlay — unresolvable removed-wire endpoint:', _remLinks[_rli]);
          continue;
        }

        var _fp = _connPos(_fNode, false, _fSlot, null, 0);
        var _tp = _connPos(_tNode, true, _tSlot, null, 0);
        if (_fp && _tp) {
          _strokeWire(_fp[0], _fp[1], _tp[0], _tp[1], removedColor, true);
        } else {
          _warnOverlayUnresolved(drawModel, '[vibecomfy] drawPreviewOverlay — could not resolve removed-wire endpoint positions:', _remLinks[_rli]);
        }
      }

      // ── Added wires: solid green beziers (drawn second) ───────────────
      var _addLinks = diff.added_links || [];
      for (var _ali = 0; _ali < _addLinks.length; _ali += 1) {
        var _p2 = _parseKey(_addLinks[_ali]);
        if (!_p2) continue;

        var _fNode2 = liveByUid.get(_p2.fromUid);
        var _tNode2 = liveByUid.get(_p2.toUid);

        // Ghost fallback for endpoints not in the live graph
        var _fGhostPos = null, _fGhostW = 0;
        if (!_fNode2) {
          var _fc = candidateByUid.get(_p2.fromUid);
          if (_fc && _fc.pos && typeof _fc.pos.length === "number" && _fc.pos.length >= 2) {
            _fGhostPos = _fc.pos;
            _fGhostW = _ghostDims(_fc).w;
          }
        }
        var _tGhostPos = null, _tGhostW = 0;
        if (!_tNode2) {
          var _tc = candidateByUid.get(_p2.toUid);
          if (_tc && _tc.pos && typeof _tc.pos.length === "number" && _tc.pos.length >= 2) {
            _tGhostPos = _tc.pos;
            _tGhostW = _ghostDims(_tc).w;
          }
        }

        // Resolve port → slot on whichever node we have (live or candidate)
        var _fNodeR = _fNode2 || candidateByUid.get(_p2.fromUid) || null;
        var _tNodeR = _tNode2 || candidateByUid.get(_p2.toUid) || null;

        var _fSlot2 = _slotIdx(_fNodeR, _p2.fromPort, 'outputs');
        var _tSlot2 = _slotIdx(_tNodeR, _p2.toPort, 'inputs');

        if (_fSlot2 < 0 || _tSlot2 < 0) {
          _warnOverlayUnresolved(drawModel, '[vibecomfy] drawPreviewOverlay — unresolvable added-wire endpoint:', _addLinks[_ali]);
          continue;
        }

        var _fp2 = _connPos(_fNode2, false, _fSlot2, _fGhostPos, _fGhostW);
        var _tp2 = _connPos(_tNode2, true, _tSlot2, _tGhostPos, _tGhostW);
        if (_fp2 && _tp2) {
          _strokeWire(_fp2[0], _fp2[1], _tp2[0], _tp2[1], addedColor, false);
        } else {
          _warnOverlayUnresolved(drawModel, '[vibecomfy] drawPreviewOverlay — could not resolve added-wire endpoint positions:', _addLinks[_ali]);
        }
      }

      // Restore dash state
      if (ctx.setLineDash) ctx.setLineDash([]);
    }
  } finally {
    ctx.restore();
  }
}

function lookupLiveNodeByUid(uid) {
  if (!uid) {
    return null;
  }
  const graph = getLiveGraph();
  for (const node of getLiveGraphNodes(graph)) {
    if (node?.properties?.vibecomfy_uid === uid) {
      return node;
    }
  }
  return null;
}

function clearChangedNodeFeedbackVisuals() {
  if (changedNodeFeedbackTimer != null && typeof clearTimeout === "function") {
    clearTimeout(changedNodeFeedbackTimer);
  }
  changedNodeFeedbackTimer = null;
  for (const entry of changedNodeFeedbackVisuals) {
    if (!entry?.node) {
      continue;
    }
    entry.node.color = entry.original.color;
    entry.node.bgcolor = entry.original.bgcolor;
    entry.node.boxcolor = entry.original.boxcolor;
  }
  changedNodeFeedbackVisuals = [];
}

function announceChangedNodes(panel, items) {
  clearChangedNodeFeedbackVisuals();
  const feedback = {
    items: items || [],
    mode: "none",
    unresolved: [],
    highlighted: [],
  };
  if (!feedback.items.length) {
    return null;
  }

  const liveHighlightable = feedback.items.filter((item) => item.uid && (item.kind === "edited" || item.kind === "new_auto_placed"));
  for (const item of liveHighlightable) {
    const node = lookupLiveNodeByUid(item.uid);
    if (!node) {
      feedback.unresolved.push(item);
      continue;
    }
    changedNodeFeedbackVisuals.push({
      node,
      original: {
        color: node.color,
        bgcolor: node.bgcolor,
        boxcolor: node.boxcolor,
      },
    });
    node.color = "#fff5c4";
    node.bgcolor = item.kind === "new_auto_placed" ? "#1d3f56" : "#574313";
    node.boxcolor = item.kind === "new_auto_placed" ? VC_COLORS.pending : VC_COLORS.edited;
    feedback.highlighted.push(item);
  }

  if (changedNodeFeedbackVisuals.length) {
    feedback.mode = "visual";
    if (typeof setTimeout === "function") {
      changedNodeFeedbackTimer = setTimeout(() => {
        clearChangedNodeFeedbackVisuals();
      }, 4000);
      if (typeof changedNodeFeedbackTimer?.unref === "function") {
        changedNodeFeedbackTimer.unref();
      }
    }
  } else {
    feedback.mode = "panel";
  }

  for (const item of feedback.items) {
    if (!item.uid || item.kind === "removed" || item.kind === "removed_named" || item.kind === "stripped_helper" || item.kind === "virtual_wires_degraded") {
      feedback.unresolved.push(item);
    }
  }
  return feedback;
}

function queueGuardTurnKey(context) {
  if (!context) {
    return "none";
  }
  return `${context.sessionId || "none"}:${context.turnId || "none"}`;
}

function getQueueGuardStateForPanel() {
  return {
    hookInstalled: Boolean(queueGuardHook?.installed),
    hookPath: queueGuardHook?.path || null,
    fallbackWarning: queueGuardFallbackWarning,
    activeContext: queueGuardContext,
    lastBlockNotice: queueGuardBlockNotice,
  };
}

function setQueueGuardContext(nextContext) {
  queueGuardContext = nextContext || null;
  if (!queueGuardContext || queueGuardContext.queueAllowed !== false) {
    queueGuardBlockNotice = null;
  }
  const panel = currentAgentPanel();
  if (panel) {
    panel.state.queueGuard = getQueueGuardStateForPanel();
  }
}

function warnQueueGuardFallbackOnce(reason) {
  if (queueGuardFallbackWarned) {
    return;
  }
  queueGuardFallbackWarned = true;
  console.warn(`VibeComfy: queue guard fallback active (${reason})`);
}

function installQueueGuard() {
  if (queueGuardHook) {
    return queueGuardHook.installed;
  }

  const report = installQueueGuardAdapter(app, {
    shouldBlock() {
      const active = queueGuardContext;
      if (active?.queueAllowed === false) {
        return {
          turnId: active.turnId || null,
          sessionId: active.sessionId || null,
          blockKey: queueGuardTurnKey(active),
        };
      }
      return null;
    },
    onBlock(blockInfo) {
      if (!queueGuardBlockedTurnKeys.has(blockInfo.blockKey)) {
        queueGuardBlockedTurnKeys.add(blockInfo.blockKey);
        queueGuardBlockNotice = {
          at: new Date().toISOString(),
          message: `Queue blocked for turn ${blockInfo.turnId || "unknown"} because queue_allowed=false.`,
          turnId: blockInfo.turnId,
          sessionId: blockInfo.sessionId,
        };
      }
      const panel = currentAgentPanel();
      if (panel) {
        panel.state.queueGuard = getQueueGuardStateForPanel();
        renderAgentPanel(panel);
      }
      toast("Queue blocked: this applied turn is canvas-reviewable only.");
    },
  });

  if (!report.installed) {
    const fallbackDetail = report.capability?.detail || "app.queuePrompt unavailable";
    queueGuardFallbackWarning = `Native queue hook unavailable: \`app.queuePrompt\` was not found. Queue warnings remain panel-only.`;
    warnQueueGuardFallbackOnce(`missing app.queuePrompt (${fallbackDetail})`);
    queueGuardHook = { installed: false, path: report.path, original: null, wrapper: null };
    return false;
  }

  queueGuardHook = { installed: true, path: report.path, original: report.original, wrapper: report.wrapper };
  queueGuardFallbackWarning = null;
  return true;
}

function appendCandidateDetail(body, panel, message = null, snapshot = null) {
  const candidateGraphPresent = candidateGraphPresentForBubble(message, snapshot)
    || (!message && !snapshot && Boolean(panel.state.candidateGraph));
  const phase = snapshot?.phase || panel.state.phase;
  const clarification = snapshot?.clarification || panel.state.clarification;
  if (!candidateGraphPresent) {
    // Clarify turn: the agent asked a question and produced no candidate. Show the
    // question as the headline (not "No candidate yet") and point the user at the
    // prompt box, which is open for their answer in the same session.
    if (phase === PANEL_STATE.CLARIFY && clarification?.message) {
      const q = el("div", "❓ The agent needs your input:");
      q.style.color = "#ffc107";
      q.style.fontWeight = "600";
      body.appendChild(q);
      const msg = el("div", clarification.message);
      msg.style.whiteSpace = "pre-wrap";
      msg.style.color = "#edf2f7";
      msg.style.borderLeft = "2px solid #ffc107";
      msg.style.paddingLeft = "8px";
      msg.style.margin = "4px 0";
      body.appendChild(msg);
      body.appendChild(muted("Answer in the prompt box above and submit — it continues this session."));
      return;
    }
    const feedback = snapshot?.lastAppliedChanges || panel.state.lastAppliedChanges;
    if (feedback?.items?.length) {
      appendTextLine(
        body,
        feedback.mode === "visual"
          ? "Applied candidate feedback: changed nodes were highlighted on the canvas temporarily."
          : "Applied candidate feedback: changed nodes listed here because live node lookup was unavailable.",
        feedback.mode === "visual" ? "#9ed0ff" : "#ffb86c",
      );
      for (const item of feedback.items) {
        const rowNode = el("div", item.label);
        rowNode.style.color = item.color;
        rowNode.style.borderLeft = `2px solid ${item.color}`;
        rowNode.style.paddingLeft = "8px";
        body.appendChild(rowNode);
      }
      if (feedback.unresolved?.length && feedback.mode === "visual") {
        body.appendChild(createDetails("panel fallback for unresolved nodes", feedback.unresolved));
      }
      return;
    }
    return;
  }
  const debugPayload = snapshot?.debugPayload || panel.state.debugPayload;
  const stageInfo = getBackendStageInfo(debugPayload);
  if (stageInfo) {
    appendTextLine(
      body,
      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
      "#9ed0ff",
    );
  }
  const candidateMessage = snapshot?.message || message?.text || panel.state.message;
  if (candidateMessage) {
    const msg = el("div", candidateMessage);
    msg.style.whiteSpace = "pre-wrap";
    msg.style.color = "#edf2f7";
    body.appendChild(msg);
  }
  const actionState = candidateActionState(panel, message, snapshot);
  const eligibility = actionState.eligibility;
  const canvasApplyAllowed = snapshot?.canvasApplyAllowed ?? panel.state.canvasApplyAllowed;
  const queueAllowed = snapshot?.queueAllowed ?? panel.state.queueAllowed;
  appendTextLine(body, `canvas_apply_allowed=${String(canvasApplyAllowed)}`, canvasApplyAllowed ? "#4caf50" : "#ffb86c");
  appendTextLine(body, `apply_eligibility=${eligibility.reason}`, eligibility.applyable ? "#4caf50" : "#ffb86c");
  appendTextLine(body, `queue_allowed=${String(queueAllowed)}`, queueAllowed ? "#4caf50" : "#ffb86c");
  if (eligibility.message) {
    appendTextLine(body, eligibility.message, "#9ed0ff");
  }
  if (actionState.visible) {
    const controlsRow = el("div");
    controlsRow.dataset.vibecomfyCandidateControls = "1";
    Object.assign(controlsRow.style, {
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      alignItems: "center",
      marginTop: "2px",
    });

    const applyBtn = button("Apply", () => applyAgentCandidate(panel));
    applyBtn.dataset.vibecomfyCandidateAction = "apply";
    applyBtn.dataset.vibecomfyCandidateTurnId = actionState.turnId || "";
    applyBtn.disabled = actionState.applyDisabled;
    applyBtn.style.fontSize = "11px";
    applyBtn.style.padding = "4px 8px";
    setButtonEmphasis(applyBtn, actionState.active || panel.state.phase === PANEL_STATE.APPLYING, "primary");
    controlsRow.appendChild(applyBtn);

    const rejectBtn = button("Reject", () => rejectAgentCandidate(panel));
    rejectBtn.dataset.vibecomfyCandidateAction = "reject";
    rejectBtn.dataset.vibecomfyCandidateTurnId = actionState.turnId || "";
    rejectBtn.disabled = actionState.rejectDisabled;
    rejectBtn.style.fontSize = "11px";
    rejectBtn.style.padding = "4px 8px";
    setButtonEmphasis(rejectBtn, actionState.active || panel.state.phase === PANEL_STATE.APPLYING, "danger");
    controlsRow.appendChild(rejectBtn);

    const stateLabel = el(
      "span",
      actionState.active
        ? (eligibility.applyable ? "latest" : eligibility.reason)
        : eligibility.reason,
    );
    stateLabel.dataset.vibecomfyCandidateReason = eligibility.reason || "";
    stateLabel.dataset.vibecomfyCandidateTurnId = actionState.turnId || "";
    Object.assign(stateLabel.style, {
      fontSize: "10px",
      color: eligibility.applyable ? "#4caf50" : "#ffb86c",
      textTransform: "uppercase",
      letterSpacing: "0.04em",
      fontWeight: "700",
    });
    controlsRow.appendChild(stateLabel);

    body.appendChild(controlsRow);
    if (actionState.blockerMessage && actionState.blockerMessage !== eligibility.message) {
      appendTextLine(body, actionState.blockerMessage, "#9ed0ff");
    }
  }
  const rows = collectDiffRows(snapshot?.candidateReport || message?.report || panel.state.candidateReport);
  if (!rows.length) {
    body.appendChild(muted("Candidate returned without report rows."));
  }
  for (const item of rows) {
    const rowNode = el("div", item.text);
    rowNode.style.color = item.color;
    rowNode.style.borderLeft = `2px solid ${item.color}`;
    rowNode.style.paddingLeft = "8px";
    if (item.title) {
      rowNode.title = item.title;
    }
    body.appendChild(rowNode);
  }
  const affected = {
    preserved: rows.filter((item) => item.text.startsWith("preserved:")).length,
    edited: rows.filter((item) => item.text.startsWith("edited:")).length,
    added: rows.filter((item) => item.text.startsWith("new_auto_placed:")).length,
    removed: rows.filter((item) => item.text.startsWith("removed:") || item.text.startsWith("removed_named:")).length,
    helpers: rows.filter((item) => item.text.startsWith("stripped_helper:") || item.text.startsWith("virtual_wires_degraded:")).length,
    lowered: rows.filter((item) => item.text.startsWith("lowered:")).length,
  };
  body.appendChild(createDetails("affected node preview", affected));
  const issues = collectQueueIssues(snapshot?.candidateReport || message?.report || panel.state.candidateReport);
  if (issues.length) {
    for (const issue of issues) {
      appendTextLine(body, `${issue.code}: ${issue.message}`, issue.severity === "error" ? "#ffb86c" : "#9ed0ff");
      if (issue.detail && Object.keys(issue.detail).length) {
        body.appendChild(createDetails("queue blocker detail", issue.detail));
      }
    }
  }
  const artifacts = debugPayload?.artifacts;
  if (artifacts && typeof artifacts === "object") {
    for (const [name, value] of Object.entries(artifacts)) {
      appendCodeLine(body, `${name}: ${value}`);
    }
  }
  const auditRef = snapshot?.auditRef || panel.state.auditRef;
  if (auditRef?.path) {
    appendCodeLine(body, `audit: ${auditRef.path}`, "#9ed0ff");
  }
  body.appendChild(createDetails("raw report", snapshot?.candidateReport || message?.report || panel.state.candidateReport || {}));
}

function renderCandidate(panel) {
  if (!panel?.sections?.candidate) {
    return;
  }
  const body = panel.sections.candidate;
  clearNode(body);
  appendCandidateDetail(body, panel, null, null);
}

function appendFailureDetail(body, panel, snapshot = null) {
  const failure = snapshot?.failure || panel.state.failure;
  if (!failure) {
    return;
  }
  appendTextLine(body, `${failure.kind || "Error"} @ ${failure.stage || "unknown"}`, "#ffd6d6");
  appendTextLine(body, failure.user_facing_message || failure.message || failure.error || "Unknown failure", "#edf2f7");
  appendTextLine(body, `retryable=${String(Boolean(failure.retryable))} graph_unchanged=${String(Boolean(failure.graph_unchanged))}`, "#8d93a1");
  appendTextLine(body, `canvas_apply_allowed=${String(Boolean(failure.canvas_apply_allowed))} queue_allowed=${String(Boolean(failure.queue_allowed))}`, "#8d93a1");
  const stageInfo = getBackendStageInfo(failure);
  if (stageInfo) {
    appendTextLine(
      body,
      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
      "#9ed0ff",
    );
  }
  if (failure.next_action) {
    appendTextLine(body, `next: ${failure.next_action}`, "#8d93a1");
  }
  if (panel.state.rebaselinePending) {
    const pending = panel.state.rebaselinePending;
    const pendingLabel =
      panel.state.inFlightRebaseline
        ? `rebaseline pending: ${pending.reason} (in flight)`
        : pending.retryable
          ? `rebaseline pending: ${pending.reason} (retryable)`
          : `rebaseline pending: ${pending.reason}`;
    appendTextLine(body, pendingLabel, "#9ed0ff");
    if (pending.last_known_baseline_graph_hash) {
      appendCodeLine(body, `expected_baseline: ${pending.last_known_baseline_graph_hash}`, "#8d93a1");
    }
  }
  if (failure.session_id || failure.turn_id || failure.baseline_turn_id) {
    appendTextLine(
      body,
      `session=${failure.session_id || "new"} turn=${failure.turn_id || "pending"} baseline=${failure.baseline_turn_id || "none"}`,
      "#8d93a1",
    );
  }
  if (failure.audit_ref?.path) {
    appendCodeLine(body, `audit: ${failure.audit_ref.path}`, "#9ed0ff");
  }
  if (failure.audit_error) {
    appendTextLine(body, `audit_error: ${failure.audit_error}`, "#ffb86c");
  }
  const recovery = panel.state.rebaselineRecovery;
  if (recovery?.action === "rebaseline" && recovery.reason === "stale_state_recovery") {
    appendTextLine(body, "The current canvas can be promoted to the new baseline.", "#9ed0ff");
    if (recovery.last_known_baseline_graph_hash) {
      appendCodeLine(body, `expected_baseline: ${recovery.last_known_baseline_graph_hash}`, "#8d93a1");
    }
  }
  if (failure.agent_failure_context && Object.keys(failure.agent_failure_context).length) {
    body.appendChild(createDetails("agent failure context", failure.agent_failure_context));
  }
  body.appendChild(createDetails("raw failure", failure));
}

function renderFailure(panel) {
  if (!panel?.sections?.failure) {
    return;
  }
  const body = panel.sections.failure;
  clearNode(body);
  appendFailureDetail(body, panel);
}

function appendQueueDetail(body, panel, snapshot = null) {
  const queueGuard = snapshot?.queueGuard || panel.state.queueGuard || getQueueGuardStateForPanel();
  const issues = collectQueueIssues(snapshot?.candidateReport || panel.state.candidateReport);
  if (queueGuard.fallbackWarning) {
    appendTextLine(body, queueGuard.fallbackWarning, "#ffb86c");
  }
  if (queueGuard.lastBlockNotice?.message) {
    appendTextLine(body, queueGuard.lastBlockNotice.message, "#ff7f7f");
  }
  if (queueGuard.hookInstalled) {
    appendTextLine(body, `native queue guard: active via ${queueGuard.hookPath}`, "#4caf50");
  } else {
    appendTextLine(body, "native queue guard: panel warning fallback only", "#8d93a1");
  }
  const queueAllowed = snapshot?.queueAllowed ?? panel.state.queueAllowed;
  if (queueAllowed) {
    appendTextLine(body, "Queue-eligible candidate. Native queue path remains unchanged.", "#4caf50");
  } else if (issues.length) {
    for (const issue of issues) {
      appendTextLine(body, issue.message, "#ffb86c");
    }
  } else if (queueGuard.activeContext?.queueAllowed === false) {
    appendTextLine(body, `Applied turn ${queueGuard.activeContext.turnId || "unknown"} remains queue-blocked.`, "#ff7f7f");
  } else {
    appendTextLine(body, "Queue disabled in this proof shell. Candidate review remains local-only for now.", "#8d93a1");
  }
}

function renderQueue(panel) {
  if (!panel?.sections?.queue) {
    return;
  }
  const body = panel.sections.queue;
  clearNode(body);
  appendQueueDetail(body, panel);
}

function turnIdForBubbleDetail(message = null, snapshot = null) {
  if (typeof message?.turn_id === "string" && message.turn_id) {
    return message.turn_id;
  }
  if (typeof message?.detail_turn_id === "string" && message.detail_turn_id) {
    return message.detail_turn_id;
  }
  if (typeof snapshot?.turn_id === "string" && snapshot.turn_id) {
    return snapshot.turn_id;
  }
  return null;
}

function turnEntriesForBubbleDetail(panel, message = null, snapshot = null) {
  const turnId = turnIdForBubbleDetail(message, snapshot);
  if (!turnId || !Array.isArray(panel?.state?.turns)) {
    return [];
  }
  return panel.state.turns
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => (
      entry
      && (
        entry.turn_id === turnId
        || entry.parent_turn_id === turnId
        || entry.raw_payload?.turn_id === turnId
      )
    ));
}

function appendAuditRefLines(body, auditRef) {
  if (!auditRef?.path) {
    return false;
  }
  appendCodeLine(body, auditRef.path, "#edf2f7");
  if (auditRef.sha256) {
    appendCodeLine(body, `sha256: ${auditRef.sha256}`, "#8d93a1");
  }
  return true;
}

function appendBatchTurnBreakdown(body, entry) {
  const summary = _safeSummaryText(entry);
  if (summary) {
    appendTextLine(body, summary, "#9ed0ff");
  }
  const stmts = Array.isArray(entry.statements) ? entry.statements : [];
  const showStmts = stmts.slice(0, BATCH_STATEMENT_CAP);
  if (showStmts.length) {
    const header = el("div", "Statements:");
    header.style.fontSize = "10px";
    header.style.color = "#9da1ac";
    body.appendChild(header);
    for (let s = 0; s < showStmts.length; s += 1) {
      body.appendChild(_statementBullet(showStmts[s], s));
    }
    const moreCount = stmts.length - BATCH_STATEMENT_CAP;
    if (moreCount > 0) {
      appendTextLine(body, `+${moreCount} more statement${moreCount !== 1 ? "s" : ""}...`, "#8d93a1");
    }
  } else if (Number.isFinite(entry.statement_count) && entry.statement_count > 0) {
    appendTextLine(body, `${entry.statement_count} statement${entry.statement_count !== 1 ? "s" : ""} (details unavailable)`, "#8d93a1");
  }

  const footer = _renderOutcomeFooter(entry);
  if (footer) {
    body.appendChild(footer);
  }

  if (Array.isArray(entry.diagnostics) && entry.diagnostics.length) {
    const maxDiags = Math.min(entry.diagnostics.length, 5);
    for (let d = 0; d < maxDiags; d += 1) {
      const diag = entry.diagnostics[d];
      const code = typeof diag?.code === "string" ? diag.code : "";
      const msg = typeof diag?.message === "string" ? diag.message : "";
      const text = code && msg ? `${code}: ${msg}` : (code || msg);
      if (text) {
        appendTextLine(body, text, "#8d93a1");
      }
    }
  }
}

function appendTurnAuditEntry(body, panel, entry, index) {
  const box = el("div");
  Object.assign(box.style, {
    borderLeft: `2px solid ${_statusColor(entry.status)}`,
    paddingLeft: "8px",
    display: "grid",
    gap: "3px",
  });

  const label =
    entry.entry_type === "batch"
      ? (Number.isFinite(entry.turn_number) ? `batch turn ${entry.turn_number + 1}` : "batch turn")
      : (entry.status || "turn");
  appendTextLine(box, `${label}${entry.status ? ` · ${entry.status}` : ""}`, _statusColor(entry.status));
  const effectiveTurnId = entry.turn_id || entry.parent_turn_id;
  if (effectiveTurnId) {
    appendTextLine(box, `turn ${effectiveTurnId}`, "#8d93a1");
  }
  if (entry.message) {
    appendTextLine(box, entry.message, "#c4ccd6");
  }
  appendAuditRefLines(box, entry.audit_ref);
  if (entry.entry_type === "batch") {
    appendBatchTurnBreakdown(box, entry);
  }
  if (entry.timestamp) {
    appendTextLine(box, entry.timestamp, "#6b7080");
  }

  const auditBtn = button("Audit \u2193", () => downloadTurnAuditEntry(entry, index));
  auditBtn.style.fontSize = "10px";
  auditBtn.style.padding = "3px 6px";
  auditBtn.style.justifySelf = "start";
  box.appendChild(auditBtn);
  body.appendChild(box);
}

function appendAuditDetail(body, panel, message = null, snapshot = null) {
  const matchedTurns = turnEntriesForBubbleDetail(panel, message, snapshot);
  if (matchedTurns.length) {
    for (const { entry, index } of matchedTurns) {
      appendTurnAuditEntry(body, panel, entry, index);
    }
    return;
  }

  const auditRef =
    (message?.audit_ref && typeof message.audit_ref === "object" ? message.audit_ref : null)
    || snapshot?.auditRef
    || panel.state.auditRef;
  if (!appendAuditRefLines(body, auditRef)) {
    body.appendChild(muted("No audit artifact linked yet."));
  }
  const dlBtn = button("Download Audit Envelope", () => downloadCurrentAudit(panel));
  dlBtn.style.fontSize = "11px";
  dlBtn.style.padding = "4px 8px";
  body.appendChild(dlBtn);
}

function renderAudit(panel) {
  if (!panel?.sections?.audit) {
    return;
  }
  const body = panel.sections.audit;
  clearNode(body);
  appendAuditDetail(body, panel);
}

function appendDebugDetail(body, panel, snapshot = null) {
  const debugPayload = scrubDebugPayload(snapshot?.debugPayload || panel.state.debugPayload || { state: snapshot?.phase || panel.state.phase });
  body.appendChild(createDetails("Raw response (debug)", debugPayload));
}

function renderDebug(panel) {
  if (!panel?.sections?.debug) {
    return;
  }
  const body = panel.sections.debug;
  clearNode(body);
  appendDebugDetail(body, panel);
}

// ── Adapter capability snapshot for developer section ──────────────────────
function adapterCapabilitySnapshot() {
  const graphApply = {
    available: typeof app?.canvas?.graph?.clear === "function" && typeof app?.canvas?.graph?.configure === "function",
    detail: typeof app?.canvas?.graph?.clear === "function" && typeof app?.canvas?.graph?.configure === "function"
      ? "Live graph supports in-place clear + configure."
      : "No live graph instance with clear + configure found.",
    path: "app.canvas.graph",
  };
  const previewForeground = _previewForegroundInstallReport?.capability || {
    available: false,
    detail: "Preview foreground install not attempted.",
    path: "app.canvas.onDrawForeground",
  };
  const previewStrategy = _previewForegroundInstallReport?.strategy || null;
  const previewPolling = _previewForegroundInstallReport?.polling === true;
  const queueGuard = {
    available: Boolean(queueGuardHook?.installed),
    detail: queueGuardHook?.installed ? "app.queuePrompt is wrapped." : "app.queuePrompt guard not installed.",
    path: queueGuardHook?.path || "app.queuePrompt",
    fallbackWarning: queueGuardFallbackWarning || null,
  };
  return {
    graphApply,
    previewForeground,
    previewStrategy,
    previewPolling,
    queueGuard,
    frontendVersion: typeof SUPPORTED_FRONTEND === "string" ? SUPPORTED_FRONTEND : "unknown",
    supportsAll: graphApply.available && previewForeground.available && queueGuard.available,
  };
}

function renderDeveloper(panel) {
  const body = panel?.sections?.developer;
  if (!body) {
    return;
  }
  clearNode(body);

  const caps = adapterCapabilitySnapshot();

  const devData = el("div");
  Object.assign(devData.style, {
    display: "grid",
    gap: "4px",
    fontSize: "10px",
    color: "#8d93a1",
    lineHeight: "1.4",
  });

  // ── Adapter capability state ──────────────────────────────────────────
  const adapterSection = renderDeveloperSubsection("Adapter Capabilities");
  const capLines = [
    `graphApply: ${caps.graphApply.available ? "✓" : "✗"} (${caps.graphApply.detail})`,
    `previewForeground: ${caps.previewForeground.available ? "✓" : "✗"} (${caps.previewForeground.detail})`,
    caps.previewStrategy ? `preview strategy: ${caps.previewStrategy}${caps.previewPolling ? " (polling fallback)" : ""}` : null,
    `queueGuard: ${caps.queueGuard.available ? "✓" : "✗"} (${caps.queueGuard.detail})`,
    caps.queueGuard.fallbackWarning ? `queueGuard fallback: ${caps.queueGuard.fallbackWarning}` : null,
    `supportsAll: ${caps.supportsAll ? "yes" : "no"} (frontend ${caps.frontendVersion})`,
  ].filter(Boolean);
  for (const line of capLines) {
    const div = el("div", line);
    div.style.color = line.startsWith("graphApply: ✗") || line.startsWith("previewForeground: ✗") || line.startsWith("queueGuard: ✗") ? "#ff8d8d" : "#8d93a1";
    adapterSection.appendChild(div);
  }
  devData.appendChild(adapterSection);

  // ── Queue guard state ─────────────────────────────────────────────────
  const qgSection = renderDeveloperSubsection("Queue Guard State");
  const qgState = getQueueGuardStateForPanel();
  const qgLines = [
    `hookInstalled: ${qgState.hookInstalled}`,
    `hookPath: ${qgState.hookPath || "none"}`,
    qgState.fallbackWarning ? `fallbackWarning: ${qgState.fallbackWarning}` : null,
    qgState.activeContext ? `activeContext: turn=${qgState.activeContext.turnId || "?"} queueAllowed=${qgState.activeContext.queueAllowed}` : "activeContext: none",
    qgState.lastBlockNotice ? `lastBlock: ${qgState.lastBlockNotice.at || "?"} — ${qgState.lastBlockNotice.message}` : "lastBlockNotice: none",
    `blockedTurnKeys: ${queueGuardBlockedTurnKeys.size}`,
  ].filter(Boolean);
  for (const line of qgLines) {
    qgSection.appendChild(el("div", line));
  }
  devData.appendChild(qgSection);

  // ── Hashes ────────────────────────────────────────────────────────────
  const hashSection = renderDeveloperSubsection("Hashes");
  const hashLines = [
    `baselineGraphHash: ${panel.state.baselineGraphHash || "none"}`,
    panel.state.baselineGraphHashKind ? `baselineGraphHashKind: ${panel.state.baselineGraphHashKind}` : null,
    panel.state.baselineGraphHashVersion != null ? `baselineGraphHashVersion: ${panel.state.baselineGraphHashVersion}` : null,
    `candidateGraphHash: ${panel.state.candidateGraphHash || "none"}`,
    `serverSubmitGraphHash: ${panel.state.serverSubmitGraphHash || "none"}`,
    panel.state.lastSubmit?.client_graph_hash ? `lastSubmit.client_graph_hash: ${panel.state.lastSubmit.client_graph_hash}` : null,
    panel.state.lastSubmit?.client_structural_graph_hash ? `lastSubmit.client_structural_graph_hash: ${panel.state.lastSubmit.client_structural_graph_hash}` : null,
  ].filter(Boolean);
  for (const line of hashLines) {
    hashSection.appendChild(el("div", line));
  }
  devData.appendChild(hashSection);

  // ── Raw booleans ──────────────────────────────────────────────────────
  const boolSection = renderDeveloperSubsection("Raw Booleans");
  const boolLines = [
    `canvasApplyAllowed: ${panel.state.canvasApplyAllowed}`,
    `queueAllowed: ${panel.state.queueAllowed}`,
    `applyAllowed: ${panel.state.applyAllowed}`,
    `applyEligibility: ${JSON.stringify(panel.state.applyEligibility)}`,
    panel.state.applyEligibilityWarning ? `applyEligibilityWarning: ${JSON.stringify(panel.state.applyEligibilityWarning)}` : null,
  ].filter(Boolean);
  for (const line of boolLines) {
    boolSection.appendChild(el("div", line));
  }
  devData.appendChild(boolSection);

  // ── Missing-contract warning ──────────────────────────────────────────
  if (panel.state.applyEligibilityWarning && panel.state.applyEligibilityWarning.reason === APPLY_ELIGIBILITY_REASON.MISSING_CONTRACT) {
    const mcSection = renderDeveloperSubsection("Missing Contract");
    mcSection.style.color = "#ffc107";
    mcSection.appendChild(el("div", `turn_id: ${panel.state.applyEligibilityWarning.turn_id || "?"}`));
    mcSection.appendChild(el("div", `message: ${panel.state.applyEligibilityWarning.message}`));
    if (panel.state.applyEligibilityWarning.candidate_graph_hash) {
      mcSection.appendChild(el("div", `candidate_graph_hash: ${panel.state.applyEligibilityWarning.candidate_graph_hash}`));
    }
    devData.appendChild(mcSection);
  }

  // ── Raw JSON ──────────────────────────────────────────────────────────
  const rawSection = renderDeveloperSubsection("Raw JSON");
  const statusSnapshot = scrubDebugPayload(panel.state.statusSnapshot);
  const debugPayload = scrubDebugPayload(panel.state.debugPayload);
  if (statusSnapshot || debugPayload) {
    if (statusSnapshot) {
      rawSection.appendChild(createDetails("Status snapshot", statusSnapshot));
    }
    if (debugPayload) {
      rawSection.appendChild(createDetails("Debug payload", debugPayload));
    }
    devData.appendChild(rawSection);
  }

  body.appendChild(devData);
  if (Object.prototype.hasOwnProperty.call(body, "textContent")) {
    const summaryText = [
      "Adapter Capabilities",
      ...capLines,
      "Queue Guard State",
      ...qgLines,
      "Raw Booleans",
      ...boolLines,
    ].join("\n");
    body.textContent = summaryText;
    if (body.parentNode && Object.prototype.hasOwnProperty.call(body.parentNode, "textContent")) {
      body.parentNode.textContent = summaryText;
    }
  }
}

function renderDeveloperSubsection(title) {
  const section = el("div");
  Object.assign(section.style, {
    border: "1px solid #282a32",
    borderRadius: "4px",
    padding: "6px",
    background: "#0d0f14",
  });
  const heading = el("div", title);
  Object.assign(heading.style, {
    fontSize: "10px",
    fontWeight: "700",
    color: "#9da1ac",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    marginBottom: "4px",
  });
  section.appendChild(heading);
  return section;
}

function renderSettings(panel) {
  const routeStatus = routeStatusState(panel);
  const descriptor = getRouteDescriptor(panel);
  const controlsReady =
    Boolean(descriptor)
    && (
      routeStatus.kind === ROUTE_STATUS_KIND.READY
      || routeStatus.kind === ROUTE_STATUS_KIND.LOADING
    );
  const apiKeyVisible = controlsReady && Boolean(descriptor.browser_api_key_allowed);
  panel.fields.route.disabled = !controlsReady;
  panel.fields.model.disabled = !controlsReady;
  setVisible(panel.fields.apiKey, apiKeyVisible, "");
  panel.fields.apiKey.placeholder = apiKeyVisible
    ? "DeepSeek API key"
    : "Browser API keys are not accepted for this route";
  if (!apiKeyVisible) {
    clearCredentialInput(panel);
  }

  const statusNode = getPanelElementById(panel, PANEL_IDS.settingsStatus);
  const guidanceNode = getPanelElementById(panel, PANEL_IDS.settingsGuidance);
  if (!statusNode || !guidanceNode) {
    return;
  }
  if (!controlsReady) {
    if (routeStatus.kind === ROUTE_STATUS_KIND.LOADING) {
      statusNode.textContent = panel.state.settingsMessage || "Loading route/model status…";
      guidanceNode.textContent = "Waiting for /vibecomfy/agent/status before enabling route/model controls.";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.MISSING_OPTIONS) {
      statusNode.textContent = panel.state.settingsMessage || "Status missing route options; route/model controls disabled.";
      guidanceNode.textContent = "The backend returned status without route_options. Check /vibecomfy/agent/status and retry.";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.MALFORMED) {
      statusNode.textContent = panel.state.settingsMessage || "Malformed status payload; route/model controls disabled.";
      guidanceNode.textContent = "The backend status payload is malformed. Fix /vibecomfy/agent/status and retry.";
    } else if (routeStatus.kind === ROUTE_STATUS_KIND.UNAVAILABLE) {
      statusNode.textContent = panel.state.settingsMessage || "Status unavailable.";
      guidanceNode.textContent = "Could not reach /vibecomfy/agent/status. Retry with Test Provider after restoring the backend.";
    } else {
      statusNode.textContent = panel.state.settingsMessage || "Route/model controls unavailable.";
      guidanceNode.textContent = "";
    }
    return;
  }

  const normalizedRoute = descriptor.normalized_route || normalizeRoutePreference(panel.fields.route.value);
  const providerAvailable = panel.state.statusSnapshot?.provider_available;
  const availability = providerAvailable === false ? "provider unavailable" : "provider ready";
  statusNode.textContent = panel.state.settingsMessage
    || `${descriptor.requested_route} → ${normalizedRoute} (${availability})`;
  guidanceNode.textContent = descriptor.guidance || "";
  if (descriptor.requested_route === "anthropic") {
    guidanceNode.textContent += "\nTODO(S0): Claude/Anthropic ToS acknowledgement placeholder.";
  }
}

function syncComposerButtons(panel, { submitting = false, showUndo = false } = {}) {
  const row = panel?.composerButtons;
  if (!row) {
    return;
  }
  const orderedButtons = [
    panel.buttons.submit,
    panel.buttons.stop,
    panel.buttons.apply,
    panel.buttons.reject,
    panel.buttons.undo,
    panel.buttons.newConversation,
  ];
  for (const btn of orderedButtons) {
    if (btn.parentNode !== row) {
      row.appendChild(btn);
    }
  }
  panel.buttons.stop.style.display = submitting ? "inline-flex" : "none";
  panel.buttons.undo.style.display = showUndo ? "inline-flex" : "none";
}

function renderComposerNotice(panel, readinessState) {
  const notice = panel?.sections?.composerNotice;
  if (!notice) {
    return;
  }
  _lastNoticeRender = {
    panelId: panel?.panelId || null,
    readySeen: Boolean(readinessState?.ready),
    at: new Date().toISOString(),
  };
  if (panel) {
    panel.lastNoticeRender = _lastNoticeRender;
  }
  clearNode(notice);
  let hasContent = false;
  const recovery = panel.state.phase === PANEL_STATE.ERROR ? panel.state.rebaselineRecovery : null;
  if (recovery?.action === "rebaseline" && recovery.reason === "stale_state_recovery") {
    const heading = el("div", "Canvas changed");
    heading.style.color = "#ffb86c";
    heading.style.fontWeight = "700";
    heading.style.marginBottom = "4px";
    notice.appendChild(heading);
    const message = el("div", "Rebaseline from the current canvas and retry the edit in one step.");
    message.style.color = "#edf2f7";
    notice.appendChild(message);
    const actionRow = el("div");
    Object.assign(actionRow.style, {
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      marginTop: "8px",
    });
    const recoveryButton = button("Rebaseline & retry", () => rebaselineCurrentCanvas(panel));
    recoveryButton.dataset.vibecomfyRecoveryAction = "stale-rebaseline-retry";
    recoveryButton.disabled = Boolean(panel.state.inFlightRebaseline);
    recoveryButton.style.fontSize = "12px";
    recoveryButton.style.padding = "6px 10px";
    setButtonEmphasis(recoveryButton, true, "primary");
    actionRow.appendChild(recoveryButton);
    notice.appendChild(actionRow);
    hasContent = true;
  }
  const clarification = panel?.state?.clarification;
  if (
    (panel.state.phase === PANEL_STATE.CLARIFY || panel.state.phase === PANEL_STATE.AWAITING_REVIEW)
    && clarification?.message
  ) {
    if (hasContent) {
      const divider = el("div");
      divider.style.height = "1px";
      divider.style.background = "#2a313c";
      divider.style.margin = "8px 0";
      notice.appendChild(divider);
    }
    const heading = el("div", "Reply in the prompt");
    heading.style.color = "#ffc107";
    heading.style.fontWeight = "700";
    heading.style.marginBottom = "4px";
    notice.appendChild(heading);
    const followUp = el("div", "Your answer continues this same session.");
    followUp.style.color = "#9da1ac";
    notice.appendChild(followUp);
    hasContent = true;
  }
  if (!readinessState.ready) {
    if (hasContent) {
      const divider = el("div");
      divider.style.height = "1px";
      divider.style.background = "#2a313c";
      divider.style.margin = "8px 0";
      notice.appendChild(divider);
    }
    const readinessLabel = el("div", "Send unavailable");
    readinessLabel.style.color = "#ffb86c";
    readinessLabel.style.fontWeight = "700";
    readinessLabel.style.marginBottom = "4px";
    notice.appendChild(readinessLabel);
    notice.appendChild(el("div", readinessState.message));
    hasContent = true;
  } else if (panel.state.phase === PANEL_STATE.SUBMITTING) {
    const submittingLabel = el("div", "Submitting edit request.");
    submittingLabel.style.color = "#ffd36f";
    submittingLabel.style.fontWeight = "700";
    notice.appendChild(submittingLabel);
    const stopHint = el("div", "Stop cancels this request locally and marks the visible turn cancelled.");
    stopHint.style.color = "#9da1ac";
    stopHint.style.marginTop = "4px";
    notice.appendChild(stopHint);
    hasContent = true;
  }
  notice.style.display = hasContent ? "block" : "none";
}

function recordAgentPanelRenderCount(panel, section) {
  if (!panel || typeof section !== "string" || !section) {
    return 0;
  }
  if (!panel.__renderCounts || typeof panel.__renderCounts !== "object") {
    panel.__renderCounts = {};
  }
  const nextCount = (panel.__renderCounts[section] || 0) + 1;
  panel.__renderCounts[section] = nextCount;
  return nextCount;
}

function renderPanelMetaAndStatus(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.META);
  renderMeta(panel);

  const phase = panel.state.phase;
  const STATUS_LABELS = {
    [PANEL_STATE.IDLE]: "Ready",
    [PANEL_STATE.SUBMITTING]: "\u2026",
    [PANEL_STATE.CLARIFY]: "Needs Your Input",
    [PANEL_STATE.AWAITING_REVIEW]: "Review Changes",
    [PANEL_STATE.APPLYING]: "\u2026",
    [PANEL_STATE.ERROR]: "Error",
  };
  panel.status.textContent = STATUS_LABELS[phase] || phase;
  panel.status.style.color =
    phase === PANEL_STATE.ERROR
      ? "#ff8d8d"
      : phase === PANEL_STATE.AWAITING_REVIEW
        ? "#7db6ff"
        : phase === PANEL_STATE.SUBMITTING
          ? "#ffd36f"
      : phase === PANEL_STATE.CLARIFY
            ? "#ffc107"
            : "#9da1ac";
}

function renderThreadSection(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.THREAD);
  // Capture the auto-scroll decision BEFORE any DOM mutation: renderHistory
  // scrolls internally, but renderActivityRows appends progress rows AFTER
  // that scroll, leaving the viewport above the new content. Re-scroll at the
  // end of the full section render when the user was following the bottom.
  const threadState = ensureThreadRenderState(panel);
  const shouldAutoScroll =
    Boolean(threadState.forceScrollOnNextRender) || isChatThreadNearBottom(panel);
  renderHistory(panel);
  // Shared live turn-progress rows rendered once per panel thread render (T13).
  renderActivityRows(panel);
  if (shouldAutoScroll) {
    scrollChatThreadToBottom(panel);
  }
}

function renderComposerActions(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.COMPOSER);
  const phase = panel.state.phase;
  const submitting = phase === PANEL_STATE.SUBMITTING;
  const reviewing = phase === PANEL_STATE.AWAITING_REVIEW;
  const applying = phase === PANEL_STATE.APPLYING;
  const canSubmit =
    phase === PANEL_STATE.IDLE
    || phase === PANEL_STATE.ERROR
    || phase === PANEL_STATE.CLARIFY
    || phase === PANEL_STATE.AWAITING_REVIEW;
  const actionState = candidateActionState(panel);
  const rebaselineReason = panel.state.rebaselinePending?.reason || null;
  const rebaselinePending = Boolean(panel.state.rebaselinePending || panel.state.inFlightRebaseline);
  const undoPending = rebaselineReason === "undo";
  const readinessState = submitReadinessState(panel);

  panel.buttons.submit.disabled =
    submitting
    || rebaselinePending
    || !canSubmit
    || !readinessState.ready;
  panel.buttons.submit.textContent = submitting ? "Submitting..." : "Submit";
  panel.buttons.stop.disabled = !submitting;
  panel.buttons.apply.disabled = actionState.applyDisabled;
  panel.buttons.reject.disabled = actionState.rejectDisabled;
  panel.buttons.undo.disabled =
    panel.state.undoStack.length < 1
    || submitting
    || applying
    || Boolean(panel.state.inFlightRebaseline)
    || (rebaselinePending && !undoPending);
  panel.buttons.undo.textContent =
    panel.state.inFlightRebaseline && undoPending
      ? "Undo Rebaseline..."
      : undoPending
        ? "Retry Undo Rebaseline"
        : "Undo Last Apply";
  panel.buttons.settingsSave.disabled =
    submitting
    || applying
    || routeStatusState(panel).kind !== ROUTE_STATUS_KIND.READY;
  panel.buttons.settingsTest.disabled = submitting || applying;

  // Always-on preview (no toggle): previewEnabled simply tracks whether there is
  // a pending candidate to preview.
  panel.state.previewEnabled = !!(reviewing && panel.state.candidateGraph);

  syncComposerButtons(panel, {
    submitting,
    showUndo: panel.state.undoStack.length > 0,
  });

  setButtonEmphasis(panel.buttons.submit, (canSubmit && readinessState.ready) || submitting, "primary");
  if (canSubmit && !submitting) {
    panel.buttons.submit.style.display = "inline-flex";
    panel.buttons.submit.style.opacity = "1";
  }
  setButtonEmphasis(panel.buttons.stop, submitting, "danger");
  setButtonEmphasis(panel.buttons.apply, reviewing || applying, "primary");
  setButtonEmphasis(panel.buttons.reject, reviewing || applying, "danger");
  setButtonEmphasis(panel.buttons.undo, panel.state.undoStack.length > 0, "neutral");
  setButtonEmphasis(panel.buttons.close, true, "neutral");
  setButtonEmphasis(panel.buttons.settingsSave, true, "neutral");
  setButtonEmphasis(panel.buttons.settingsTest, true, "neutral");
}

function renderComposerNoticeSection(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.NOTICE);
  renderComposerNotice(panel, submitReadinessState(panel));
}

function renderSettingsSection(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.SETTINGS);
  renderSettings(panel);
}

function renderDeveloperSection(panel) {
  recordAgentPanelRenderCount(panel, RENDER_SECTIONS.DEVELOPER);
  renderDeveloper(panel);
}

function recordAgentPanelRenderError(panel, section, err) {
  if (!panel || typeof section !== "string" || !section) {
    return 0;
  }
  if (!Array.isArray(panel.__renderErrors)) {
    panel.__renderErrors = [];
  }
  if (!panel.__renderFailureCounts || typeof panel.__renderFailureCounts !== "object") {
    panel.__renderFailureCounts = {};
  }
  const nextCount = (panel.__renderFailureCounts[section] || 0) + 1;
  panel.__renderFailureCounts[section] = nextCount;
  panel.__renderErrors.push({
    section,
    error: String(err),
    at: new Date().toISOString(),
  });
  if (panel.__renderErrors.length > AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT) {
    panel.__renderErrors.splice(0, panel.__renderErrors.length - AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT);
  }
  if (nextCount <= AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT && typeof console !== "undefined" && console?.error) {
    console.error("[vibecomfy] section render failed", section, err);
  }
  return nextCount;
}

function recordAgentPanelRenderSuccess(panel, section) {
  if (!panel?.__renderFailureCounts || typeof section !== "string" || !section) {
    return;
  }
  delete panel.__renderFailureCounts[section];
}

function runAgentPanelSectionRenderer(panel, section, renderer, result) {
  try {
    renderer(panel);
    recordAgentPanelRenderSuccess(panel, section);
    result.succeededSections.push(section);
    return true;
  } catch (err) {
    const failureCount = recordAgentPanelRenderError(panel, section, err);
    result.failedSections.push(section);
    if (failureCount < AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT) {
      result.retrySections.push(section);
    }
    return false;
  }
}

function renderAgentPanelSections(panel, dirtySections = ALL_AGENT_PANEL_RENDER_SECTIONS) {
  const result = {
    requestedSections: [],
    succeededSections: [],
    failedSections: [],
    retrySections: [],
  };
  if (!panel?.root) {
    return result;
  }
  if (!isAgentPanelRootConnected(panel)) {
    return result;
  }
  const requestedSections = Array.isArray(dirtySections)
    ? (normalizeDirtySectionList(dirtySections) || [])
    : ALL_AGENT_PANEL_RENDER_SECTIONS.slice();
  result.requestedSections = requestedSections.slice();
  if (!panel.__sectionsEverRendered) {
    panel.__sectionsEverRendered = {};
  }
  for (const section of requestedSections) {
    if (section === RENDER_SECTIONS.META) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.META, renderPanelMetaAndStatus, result);
    } else if (section === RENDER_SECTIONS.THREAD) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.THREAD, renderThreadSection, result);
    } else if (section === RENDER_SECTIONS.COMPOSER) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.COMPOSER, renderComposerActions, result);
    } else if (section === RENDER_SECTIONS.NOTICE) {
      runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.NOTICE, renderComposerNoticeSection, result);
    } else if (section === RENDER_SECTIONS.SETTINGS) {
      if (runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.SETTINGS, renderSettingsSection, result)) {
        panel.__sectionsEverRendered.SETTINGS = true;
      }
    } else if (section === RENDER_SECTIONS.DEVELOPER) {
      if (runAgentPanelSectionRenderer(panel, RENDER_SECTIONS.DEVELOPER, renderDeveloperSection, result)) {
        panel.__sectionsEverRendered.DEVELOPER = true;
      }
    }
  }
  panel.lastRenderedDirtySections = result.succeededSections.slice();
  panel.lastFailedDirtySections = result.failedSections.slice();
  return result;
}

export function renderDirtyAgentPanelSections(panel, obligations = {}) {
  if (!panel?.root) {
    return [];
  }
  if (!isAgentPanelRootConnected(panel)) {
    return [];
  }
  const normalized = normalizeObligationDirtySections(obligations) || obligations;
  const fallbackSections =
    normalized && typeof normalized === "object" && "dirtySections" in normalized
      ? normalized.dirtySections
      : ALL_AGENT_PANEL_RENDER_SECTIONS;
  const dirtySections = consumeAgentPanelDirtySections(panel, fallbackSections);
  const result = renderAgentPanelSections(panel, dirtySections);
  if (Array.isArray(result?.retrySections) && result.retrySections.length) {
    markAgentPanelDirty(panel, result.retrySections);
  }
  return dirtySections;
}

export function renderAgentPanel(panel, obligations = {}) {
  return renderDirtyAgentPanelSections(panel, obligations);
}

function agentPanelFailure(kind, message, extra = {}) {
  return {
    ok: false,
    kind,
    stage: extra.stage || "frontend",
    retryable: Boolean(extra.retryable),
    graph_unchanged: extra.graph_unchanged !== false,
    next_action: extra.next_action || "Retry the request after fixing the issue.",
    user_facing_message: message,
    ...extra,
  };
}

async function saveAgentSettings(panel) {
  if (!panel) {
    return;
  }
  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  const descriptor = getRouteDescriptor(panel, route);
  if (routeStatusState(panel).kind !== ROUTE_STATUS_KIND.READY || !descriptor) {
    panel.state.settingsMessage = "Route/model controls are unavailable until /vibecomfy/agent/status returns a valid payload.";
    renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
    return;
  }
  const apiKey = panel.fields.apiKey.value;

  panel.state.settingsMessage = `Saved route=${route} model=${model || "default"}`;
  if (apiKey) {
    try {
      const res = await fetch("/vibecomfy/agent/credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: route, api_key: apiKey }),
      });
      const result = await res.json();
      panel.state.settingsMessage = result?.stored
        ? `Stored browser credential for ${result.provider || route}.`
        : (result?.reason || descriptor.guidance || "Browser credential was not stored.");
    } catch (e) {
      panel.state.settingsMessage = `Credential save failed: ${String(e)}`;
    } finally {
      clearCredentialInput(panel);
    }
  }
  await refreshAgentStatus(panel, { quiet: Boolean(apiKey) });
}

async function testAgentSettings(panel) {
  if (!panel) {
    return;
  }
  panel.state.settingsMessage = "Testing provider status…";
  renderAgentPanel(panel, { dirtySections: SETTINGS_STATUS_RENDER_SECTIONS });
  await refreshAgentStatus(panel);
}

async function newAgentConversation(panel) {
  if (!panel) {
    return;
  }
  if (panel.state.submitAbortController) {
    panel.state.submitAbortController.abort();
  }
  const obligations = transition(panel, "NEW_CONVERSATION");
  // Clear chat / session state
  panel.state.chatMessages = [];
  resetThreadRenderState(panel);
  panel.state.chatLoaded = false;
  panel.state.chatError = null;
  panel.state.chatSessionPath = null;
  panel.state.chatDetailJsonPath = null;
  panel.state.expandedBubbleTurnKeys = {};
  panel.state.turnDetailSnapshots = {};
  panel.state.syntheticAgentMessage = null;
  // Clear activity / history
  panel.state.turns = [];
  panel.state.history = [];
  panel.state.undoStack = [];
  panel.state.previewEnabled = false;
  fulfillLifecycleTransitionObligations(panel, obligations);
  renderLifecycleTransition(panel, obligations);
}

// ── Submit helpers (extracted from submitAgentEdit; pure data transformations) ──

/** Build the POST body for /vibecomfy/agent-edit. */
function buildSubmitBody(snapshot, task, panel) {
  return {
    graph: snapshot.graph,
    task,
    route: snapshot.route,
    model: snapshot.model || undefined,
    session_id: panel.state.sessionId || undefined,
    client_id: api?.clientId || undefined,
    client_graph_hash: snapshot.graphHash,
    client_structural_graph_hash: snapshot.structuralHash,
    client_live_canvas_token: snapshot.liveCanvasToken,
    idempotency_key: snapshot.idempotencyKey,
  };
}

/** Normalize a caught error into a failure envelope that submitAgentEdit can store. */
function normalizeSubmitFailure(error) {
  if (error?.ok === false) {
    return error;
  }
  return agentPanelFailure("NetworkError", String(error), {
    retryable: true,
    next_action: "Retry once the local ComfyUI backend responds again.",
  });
}

/** Validate that a result payload is a usable success envelope (clarify or candidate). */
function isSubmitResponseValid(outcome, candidateGraph) {
  if (!outcome || typeof outcome !== "object") {
    return false;
  }
  switch (outcome.kind) {
    case "clarify":
    case "noop":
      return true;
    case "candidate":
      return Boolean(candidateGraph && typeof candidateGraph === "object");
    case "error":
      return false;
    default:
      return false;
  }
}

export function fulfillLifecycleTransitionObligations(panel, obligations = {}) {
  if (Array.isArray(obligations?.dirtySections) && obligations.dirtySections.length) {
    markAgentPanelDirty(panel, obligations.dirtySections);
  }
  if (obligations.invalidateCandidate) {
    clearCandidateInvalidationSideEffects(false);
  }
  if (obligations.clearCandidatePreview) {
    clearCandidatePreviewState(panel);
  }
  if (obligations.clearChangedNodeFeedbackVisuals) {
    clearChangedNodeFeedbackVisuals();
  }
  if (obligations.persistSession !== undefined) {
    _persistActiveSession(obligations.persistSession || null);
  }
  if (obligations.forgetSession) {
    forgetActiveSession();
  }
  if (obligations.queueGuardClear) {
    setQueueGuardContext(null);
  }
  if (obligations.setQueueGuardContext) {
    setQueueGuardContext(obligations.setQueueGuardContext);
  }
  if (obligations.refreshQueueGuard) {
    panel.state.queueGuard = getQueueGuardStateForPanel();
  }
  if (obligations.toast) {
    toast(obligations.toast);
  }
}

function renderLifecycleTransition(panel, obligations = {}) {
  if (obligations.render) {
    renderDirtyAgentPanelSections(panel, obligations);
  }
  if (obligations.focusPrompt) {
    const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel?.fields?.prompt;
    if (promptEl && typeof promptEl.focus === "function") {
      panel.fields.prompt = promptEl;
      promptEl.focus();
    }
  }
  if (obligations.rehydrateChat) {
    _rehydrateChat(panel)
      .then(() => { scheduleRenderAgentPanel("rehydrate", panel); })
      .catch((err) => { console.warn("[vibecomfy] chat rehydration render failed", err); });
  }
}

async function submitAgentEdit(panel) {
  if (panel?.state?.rebaselinePending || panel?.state?.inFlightRebaseline) {
    renderAgentPanel(panel);
    return panel.state.inFlightRebaseline || undefined;
  }
  if (panel.state.inFlightSubmit) {
    return panel.state.inFlightSubmit;
  }
  const submitPromise = (async () => {
    let submitEpoch = null;
    let submitAbortController = null;
    const isCurrentSubmit = () => panel?.state?.submitEpoch === submitEpoch;
    // Re-resolve the prompt element from the live DOM at submit time: a durable
    // panel re-render can replace the textarea, leaving panel.fields.prompt as a
    // stale, detached reference whose .value reads empty — a false "MissingTask".
    const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel.fields.prompt;
    if (promptEl && promptEl !== panel.fields.prompt) {
      panel.fields.prompt = promptEl;
    }
    const readinessState = submitReadinessState(panel);
    if (!readinessState.ready) {
      const obligations = transition(panel, "SUBMIT_READINESS_FAILURE", {
        debugPayload: {
          failure: null,
          readiness: readinessState,
          route_status: clonePlainData(panel.state.routeStatus),
          status_snapshot: clonePlainData(panel.state.statusSnapshot),
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const task = (promptEl && typeof promptEl.value === "string" ? promptEl.value : "").trim();
    if (!task) {
      const failure = agentPanelFailure("MissingTask", "Enter an edit instruction before submitting.", {
        retryable: true,
        next_action: "Describe the workflow change in the prompt region, then submit again.",
      });
      const obligations = transition(panel, "SUBMIT_MISSING_TASK", {
        failure,
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const pendingMessage = `Submitting: ${task.slice(0, 80)}${task.length > 80 ? "..." : ""}`;
    // The user just sent a message — always jump the thread to the newest
    // content regardless of where they had scrolled.
    ensureThreadRenderState(panel).forceScrollOnNextRender = true;
    const startObligations = transition(panel, "SUBMIT_START", {
      lastSubmit: null,
      debugPayload: {
        task,
      },
    });
    submitEpoch = startObligations.submitEpoch;

    let snapshot;
    try {
      snapshot = await buildSubmitSnapshot(panel);
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
    } catch (e) {
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      const failure = agentPanelFailure("SerializeError", String(e), {
        retryable: true,
        next_action: "Make sure the canvas can serialize, then retry.",
      });
      const obligations = transition(panel, "SUBMIT_SERIALIZE_ERROR", {
        failure,
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const submitStartObligations = transition(panel, "SUBMIT_START", {
      submitEpoch,
      lastSubmit: {
        task,
        route: snapshot.route,
        model: snapshot.model,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        client_live_canvas_token: snapshot.liveCanvasToken,
        idempotency_key: snapshot.idempotencyKey,
      },
      debugPayload: {
        task,
        route: snapshot.route,
        model: snapshot.model,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        client_live_canvas_token: snapshot.liveCanvasToken,
        idempotency_key: snapshot.idempotencyKey,
      },
    });
    fulfillLifecycleTransitionObligations(panel, submitStartObligations);
    // Preserve the epoch allocated before serialization; SUBMIT_START above
    // returns the current epoch when payload.submitEpoch is supplied.
    submitEpoch = panel.state.submitEpoch;
    pushHistory(panel, "pending", pendingMessage);
    pushTurnStatus(panel, "pending", {
      task,
      message: pendingMessage,
    });
    renderLifecycleTransition(panel, submitStartObligations);

    let result;
    try {
      submitAbortController = new AbortController();
      transition(panel, "SUBMIT_ABORT_CONTROLLER", { controller: submitAbortController });
      const body = buildSubmitBody(snapshot, task, panel);
      const res = await fetch("/vibecomfy/agent-edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: submitAbortController.signal,
      });
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      const rawResult = await res.json();
      try {
        result = normalizeAgentEditResponse(rawResult, { endpoint: "submit", allowLegacy: true });
      } catch (error) {
        if (res.ok) {
          throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
            stage: rawResult?.stage || "agent-edit",
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry the request or inspect the raw response in the debug panel.",
            raw_response: rawResult,
            cause: String(error),
          });
        }
        throw error;
      }
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      if (typeof result.sessionId === "string" && result.sessionId) {
        // Persisting the value remains a side effect, but sessionId itself is
        // committed through the terminal submit transition below.
        _persistActiveSession(result.sessionId);
      }
      if (!res.ok || result?.ok === false || result.raw?.error) {
        throw result.raw || { kind: "RequestError", message: res.statusText };
      }
      const outcome = result.outcome;
      const candidateGraph = result.candidateGraph;
      if (!isSubmitResponseValid(outcome, candidateGraph)) {
        throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
          stage: result.raw?.stage || "agent-edit",
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry the request or inspect the raw response in the debug panel.",
          raw_response: result.raw,
        });
      }
    } catch (e) {
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      if (e?.name === "AbortError") {
        const obligations = transition(panel, "SUBMIT_ABORT", {
          message: "Request cancelled.",
          syntheticAgentMessage: {
            role: "agent",
            text: "Request cancelled.",
            session_id: panel.state.sessionId || null,
            synthetic: true,
            local_id: `cancelled:${Date.now()}`,
          },
          debugPayload: {
            cancelled: true,
            last_submit: panel.state.lastSubmit,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        pushHistory(panel, "cancelled", task);
        pushTurnStatus(panel, "cancelled", {
          session_id: panel.state.sessionId,
          task,
          message: "Request cancelled.",
        });
        renderLifecycleTransition(panel, obligations);
        return;
      }
      const failure = normalizeSubmitFailure(e);
      const obligations = transition(panel, "SUBMIT_NETWORK_FAILURE", {
        failure,
        debugPayload: {
          ...failure,
          last_submit: panel.state.lastSubmit,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      pushHistory(panel, "failure", failure.kind || "NetworkError");
      pushTurnStatus(panel, "failed", {
        session_id: failure.session_id,
        turn_id: failure.turn_id,
        baseline_turn_id: failure.baseline_turn_id,
        task,
        failure_kind: failure.kind,
        failure_stage: failure.stage,
        message: failure.user_facing_message || failure.message || failure.error,
        audit_ref: failure.audit_ref,
        raw_payload: failure,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: failure.turn_id,
        session_id: failure.session_id,
        failure,
        message: failure.user_facing_message || failure.message || failure.error,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    } finally {
      transition(panel, "SUBMIT_FINALLY", {
        clearAbortController: isCurrentSubmit() || panel.state.submitAbortController === submitAbortController,
        clearInFlightSubmit: isCurrentSubmit() || panel.state.inFlightSubmit === submitPromise,
      });
    }

    // Clarify terminal: the agent ended the turn with `clarify("...")` instead of
    // landing edits. The canonical outcome can arrive without any candidate graph,
    // so branch out BEFORE the candidate path and never enter AWAITING_REVIEW for
    // clarify-only turns. Otherwise we'd render an "Apply Candidate" button over a
    // no-op/unchanged graph. Instead surface the question and leave the prompt open
    // so the user can answer in the same session.
    const outcome = result.outcome;
    const candidateGraph = result.candidateGraph;
    const eligibility = result.eligibility;
    if (outcomeRequiresClarification(outcome) && !candidateGraph) {
      const fallbackMessage =
        (typeof result.message === "string" && result.message.trim())
          ? result.message.trim()
          : null;
      const clarifyMessage =
        clarificationMessageFromOutcome(outcome, fallbackMessage)
          || fallbackMessage
          || "The agent needs clarification before it can edit the graph.";
      const clarification = {
        message: clarifyMessage,
        turn_id: result.turnId || null,
        session_id: result.sessionId || null,
      };
      const obligations = transition(panel, "CLARIFY_ONLY_RESPONSE", {
        result: result.raw || result,
        clarification,
        message: clarifyMessage,
        lastSubmitFieldChanges: normalizeFieldChangesFromSubmit(result.raw || result),
        debugPayload: {
          ...(result.raw || result),
          last_submit: panel.state.lastSubmit,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      reconcileResponseBatchTurns(panel, result.raw || result);
      pushHistory(panel, "clarify", clarifyMessage);
      pushTurnStatus(panel, "clarify", {
        session_id: result.sessionId,
        turn_id: result.turnId,
        baseline_turn_id: result.baselineTurnId,
        task,
        message: clarifyMessage,
        clarification_required: true,
        clarification_message: clarifyMessage,
        audit_ref: result.auditRef,
        raw_payload: result.raw || result,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: result.turnId,
        session_id: result.sessionId,
        clarification: panel.state.clarification,
        message: clarifyMessage,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    if (outcomeIsNoop(outcome)) {
      const noopMessage =
        (typeof result.message === "string" && result.message.trim())
          ? result.message.trim()
          : (typeof outcome.reason === "string" && outcome.reason.trim())
            ? outcome.reason.trim()
            : "No change needed.";
      const lastSubmitFieldChanges = normalizeFieldChangesFromSubmit(result.raw || result);
      const changeDetails = result.raw?.change_details && typeof result.raw.change_details === "object"
        ? clonePlainData(result.raw.change_details)
        : null;
      const obligations = transition(panel, "NOOP_RESPONSE", {
        result: result.raw || result,
        message: noopMessage,
        lastSubmitFieldChanges,
        changeDetails,
        debugPayload: {
          ...(result.raw || result),
          last_submit: panel.state.lastSubmit,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      reconcileResponseBatchTurns(panel, result.raw || result);
      pushHistory(panel, "noop", noopMessage);
      pushTurnStatus(panel, "noop", {
        session_id: result.sessionId,
        turn_id: result.turnId,
        baseline_turn_id: result.baselineTurnId,
        task,
        message: noopMessage,
        graph_unchanged: true,
        audit_ref: result.auditRef,
        raw_payload: result.raw || result,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: result.turnId,
        session_id: result.sessionId,
        outcome,
        message: noopMessage,
        changeDetails,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    let arrivalSnapshot;
    try {
      arrivalSnapshot = await buildCanvasSnapshot();
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
    } catch (e) {
      if (!isCurrentSubmit()) {
        transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
        return;
      }
      const failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas after the candidate arrived: ${String(e)}`, {
        retryable: true,
        graph_unchanged: true,
        next_action: "Make sure the current canvas can serialize, then submit again.",
      });
      const obligations = transition(panel, "ARRIVAL_SERIALIZE_FAILURE", {
        result: result.raw || result,
        failure,
        debugPayload: {
          ...failure,
          last_submit: panel.state.lastSubmit,
          response: result.raw || result,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const expectedArrivalStructuralHash = panel.state.lastSubmit?.client_structural_graph_hash;
    const structuralChangedForDiagnostics =
      typeof expectedArrivalStructuralHash === "string"
      && expectedArrivalStructuralHash
      && arrivalSnapshot.structuralHash !== expectedArrivalStructuralHash;

    const candidateGraphHash = result.candidateGraphHash
      || (result.raw?.candidate_graph_hash && typeof result.raw.candidate_graph_hash === "string"
        ? result.raw.candidate_graph_hash
        : null)
      || await sha256HexUtf8(canonicalJsonString(candidateGraph));
    if (!isCurrentSubmit()) {
      transition(panel, "SUBMIT_STALE_EPOCH", { submitEpoch });
      return;
    }
    const normalizedEligibility = normalizeApplyEligibility(eligibility);
    const changeDetails = result.raw?.change_details && typeof result.raw.change_details === "object"
      ? clonePlainData(result.raw.change_details)
      : null;
    const lastSubmitFieldChanges = normalizeFieldChangesFromSubmit(result.raw || result);
    const candidateDebugPayload = scrubDebugPayload({
      ...(result.raw || result),
      last_submit: panel.state.lastSubmit,
      arrival_structural_mismatch: structuralChangedForDiagnostics,
      arrival_client_graph_hash: arrivalSnapshot.graphHash,
      arrival_client_structural_graph_hash: arrivalSnapshot.structuralHash,
    });
    const candidateObligations = transition(panel,
      outcomeHasClarificationPrompt(outcome) ? "EDIT_CLARIFY_RESPONSE" : "OK_CANDIDATE_RESPONSE",
      {
        result: result.raw || result,
        candidateGraph,
        candidateGraphHash,
        clarification: outcomeHasClarificationPrompt(outcome)
          ? {
              message: clarificationMessageFromOutcome(outcome, result.message || null),
              turn_id: result.turnId || null,
              session_id: result.sessionId || null,
            }
          : null,
        applyEligibility: normalizedEligibility,
        lastSubmitFieldChanges,
        changeDetails,
        debugPayload: candidateDebugPayload,
      },
    );
    fulfillLifecycleTransitionObligations(panel, candidateObligations);
    reconcileResponseBatchTurns(panel, result.raw || result);
    pushHistory(panel, "candidate", result.turnId ? `turn ${result.turnId}` : "candidate");
    pushTurnStatus(panel, "candidate", {
      session_id: result.sessionId,
      turn_id: result.turnId,
      baseline_turn_id: result.baselineTurnId,
      task,
      message: result.message || (result.turnId ? `turn ${result.turnId}` : "candidate"),
      audit_ref: result.auditRef,
      raw_payload: result.raw || result,
    });
    rememberTurnDetailSnapshot(panel, {
      turn_id: result.turnId,
      session_id: result.sessionId,
      candidateGraphPresent: Boolean(candidateGraph),
      candidateReport: result.report || null,
      applyEligibility: normalizedEligibility,
      queueAllowed: Boolean(result.queueAllowed),
      canvasApplyAllowed: Boolean(result.canvasApplyAllowed),
      auditRef: result.auditRef || null,
      debugPayload: {
        ...scrubDebugPayload(result.raw || result),
        last_submit: panel.state.lastSubmit,
      },
      fieldChanges: panel.state.lastSubmitFieldChanges,
      changeDetails: panel.state.changeDetails,
      message: result.message || null,
    });
    renderLifecycleTransition(panel, candidateObligations);

    if (panel.state.previewEnabled) {
      if (app?.canvas?.setDirty) {
        app.canvas.setDirty(true, true);
      }
      if (app?.canvas?.draw) {
        app.canvas.draw(true, true);
      }
    }
  })();

  transition(panel, "SUBMIT_IN_FLIGHT", { promise: submitPromise });
  return panel.state.inFlightSubmit;
}

function stopAgentSubmit(panel) {
  const controller = panel?.state?.submitAbortController;
  if (!controller) {
    renderAgentPanel(panel);
    return false;
  }
  controller.abort();
  const obligations = transition(panel, "STOP_ABORT", {
    message: "Request cancelled.",
    syntheticAgentMessage: {
      role: "agent",
      text: "Request cancelled.",
      session_id: panel.state.sessionId || null,
      synthetic: true,
      local_id: `cancelled:${Date.now()}`,
    },
    debugPayload: {
      cancelled: true,
      last_submit: panel.state.lastSubmit,
    },
  });
  fulfillLifecycleTransitionObligations(panel, obligations);
  const task = panel.state.lastSubmit?.task || "";
  pushHistory(panel, "cancelled", task);
  pushTurnStatus(panel, "cancelled", {
    session_id: panel.state.sessionId,
    task,
    message: "Request cancelled.",
  });
  renderLifecycleTransition(panel, obligations);
  return true;
}

async function applyAgentCandidate(panel) {
  if (!panel.state.candidateGraph) {
    transition(panel, "APPLY_PREFLIGHT_BLOCKED", { reason: "no_candidate" });
    return;
  }
  if (!panel.state.sessionId || !panel.state.turnId) {
    const failure = agentPanelFailure("MissingRequiredField", "Cannot apply a candidate without session_id and turn_id.", {
      retryable: false,
      graph_unchanged: true,
      next_action: "Submit the edit again to get a complete candidate envelope.",
    });
    const obligations = transition(panel, "APPLY_MISSING_FIELDS", {
      failure,
      debugPayload: failure,
    });
    fulfillLifecycleTransitionObligations(panel, obligations);
    renderLifecycleTransition(panel, obligations);
    return;
  }
  if (panel.state.inFlightApply) {
    return panel.state.inFlightApply;
  }

  const applyPromise = (async () => {
    let beforeApply;
    try {
      beforeApply = await buildCanvasSnapshot();
    } catch (e) {
      const failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas before Apply: ${String(e)}`, {
        retryable: true,
        graph_unchanged: true,
      });
      const obligations = transition(panel, "APPLY_SERIALIZE_ERROR", {
        failure,
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const expectedHash = panel.state.lastSubmit?.client_graph_hash;
    const eligibility = applyEligibility(panel, beforeApply);
    if (!eligibility.applyable) {
      const failure = agentPanelFailure(
        eligibility.reason === APPLY_ELIGIBILITY_REASON.STALE_CANVAS
          ? "StaleStateMismatch"
          : "ApplyBlocked",
        eligibility.reason === APPLY_ELIGIBILITY_REASON.STALE_CANVAS
          ? "The canvas changed after this candidate was generated. Apply is blocked."
          : (eligibility.message || "Apply is blocked for this candidate."),
        {
          retryable: eligibility.reason !== APPLY_ELIGIBILITY_REASON.NO_CANDIDATE,
          graph_unchanged: true,
          next_action:
            eligibility.reason === APPLY_ELIGIBILITY_REASON.STALE_CANVAS
              ? "Submit a new edit from the current canvas."
              : "Submit a new edit or resolve the server-side blockers before retrying Apply.",
          client_graph_hash: beforeApply.graphHash,
          client_structural_graph_hash: beforeApply.structuralHash,
          expected_graph_hash: expectedHash,
          expected_structural_graph_hash: panel.state.lastSubmit?.client_structural_graph_hash,
          apply_eligibility: eligibility,
        },
      );
      const obligations = transition(panel, "APPLY_ELIGIBILITY_BLOCKED", {
        failure,
        debugPayload: failure,
        clearCandidatePreview: true,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const stateCheckGraphHash = expectedHash || beforeApply.graphHash;
    const acceptKey = buildActionIdempotencyKey({
      action: "accept",
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
      graphHash: stateCheckGraphHash,
    });
    const acceptBody = {
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
      client_graph_hash: stateCheckGraphHash,
      client_live_canvas_token: beforeApply.liveCanvasToken,
      submit_graph_hash: panel.state.serverSubmitGraphHash || undefined,
      candidate_graph_hash: panel.state.candidateGraphHash || undefined,
      idempotency_key: acceptKey,
    };

    const startedObligations = transition(panel, "APPLY_STARTED", {
      acceptBody,
      debugPayload: {
        applying_turn_id: panel.state.turnId,
        accept_request: acceptBody,
      },
    });
    fulfillLifecycleTransitionObligations(panel, startedObligations);
    renderLifecycleTransition(panel, startedObligations);

    let accepted;
    try {
      const res = await fetch("/vibecomfy/agent-edit/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(acceptBody),
      });
      const rawAccepted = await res.json();
      accepted = normalizeAuxiliaryAgentPayload(rawAccepted, "accept");
      if (!res.ok || accepted?.ok === false || accepted.raw?.error) {
        throw accepted.raw || { kind: "AcceptError", message: res.statusText };
      }
      if (
        !accepted
        || typeof accepted !== "object"
        || (accepted.raw?.action && accepted.raw.action !== "accept")
        || !accepted.sessionId
        || !accepted.turnId
      ) {
        throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete accept envelope.", {
          stage: accepted.raw?.stage || "accept",
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry Apply or inspect the raw response in the debug panel.",
          raw_response: accepted.raw,
        });
      }
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("AcceptError", String(e), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry Apply after the backend accepts the turn.",
          });
      const authoritativeBackendReject =
        e?.ok === false
        && !["MalformedResponse", "AcceptError", "NetworkError"].includes(String(e?.kind || ""));
      const recovery = accepted?.rebaselineRecovery || recoveryForFailure(failure, panel, acceptBody);
      const obligations = transition(panel, "ACCEPT_REJECTED", {
        failure,
        acceptBody,
        authoritativeBackendReject,
        ...(recovery ? { rebaselineRecovery: recovery } : {}),
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "accept"),
        disabledApplyEligibility: authoritativeBackendReject
          ? disabledApplyEligibility(
              APPLY_ELIGIBILITY_REASON.SUPERSEDED,
              failure.user_facing_message || failure.message || "The backend rejected this candidate.",
              ["backend_rejected"],
            )
          : null,
        debugPayload: {
          ...failure,
          accept_request: acceptBody,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      pushHistory(panel, "failure", failure.kind || "AcceptError");
      pushTurnStatus(panel, "failed", {
        session_id: failure.session_id || panel.state.sessionId,
        turn_id: failure.turn_id || panel.state.turnId,
        baseline_turn_id: failure.baseline_turn_id || panel.state.baselineTurnId,
        failure_kind: failure.kind || "AcceptError",
        failure_stage: failure.stage || "accept",
        message: failure.user_facing_message || failure.message || failure.error,
        audit_ref: failure.audit_ref,
        raw_payload: failure,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: failure.turn_id || panel.state.turnId,
        session_id: failure.session_id || panel.state.sessionId,
        failure,
        message: failure.user_facing_message || failure.message || failure.error,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    const currentBeforeLoad = await buildCanvasSnapshot();
    if (currentBeforeLoad.liveCanvasToken !== beforeApply.liveCanvasToken) {
      const failure = agentPanelFailure("StaleStateMismatch", "The canvas changed while Apply was waiting for backend acceptance. Candidate loading is blocked.", {
        retryable: true,
        graph_unchanged: true,
        next_action: "Rebaseline and retry from the current canvas.",
        client_graph_hash: currentBeforeLoad.graphHash,
        client_structural_graph_hash: currentBeforeLoad.structuralHash,
        expected_graph_hash: stateCheckGraphHash,
        client_live_canvas_token: currentBeforeLoad.liveCanvasToken,
        expected_live_canvas_token: beforeApply.liveCanvasToken,
        accept_response: accepted.raw || accepted,
      });
      const obligations = transition(panel, "STALE_CANVAS_APPLY", {
        failure,
        rebaselineRecovery: recoveryForFailure(failure, panel, acceptBody),
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      pushHistory(panel, "failure", failure.kind || "StaleStateMismatch");
      pushTurnStatus(panel, "failed", {
        session_id: failure.session_id || panel.state.sessionId,
        turn_id: failure.turn_id || panel.state.turnId,
        baseline_turn_id: failure.baseline_turn_id || panel.state.baselineTurnId,
        failure_kind: failure.kind || "StaleStateMismatch",
        failure_stage: failure.stage || "frontend",
        message: failure.user_facing_message || failure.message || failure.error,
        audit_ref: failure.audit_ref,
        raw_payload: failure,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: failure.turn_id || panel.state.turnId,
        session_id: failure.session_id || panel.state.sessionId,
        failure,
        message: failure.user_facing_message || failure.message || failure.error,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }

    panel.state.undoStack.push({
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
      graph: currentBeforeLoad.graph,
      client_graph_hash: currentBeforeLoad.graphHash,
      accepted_baseline_graph_hash: accepted.baselineGraphHash || panel.state.baselineGraphHash || null,
      captured_at: new Date().toISOString(),
    });
    panel.state.undoStack = panel.state.undoStack.slice(-16);
    markAgentPanelDirty(panel, [RENDER_SECTIONS.META]);

    try {
      applyGraphInPlaceWithIntentDecoration(panel.state.candidateGraph);
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("CanvasApplyError", String(e), {
            retryable: true,
            graph_unchanged: false,
            next_action: "Retry Apply or inspect the raw response in the debug panel.",
            accept_response: accepted.raw || accepted,
          });
      const obligations = transition(panel, "CANVAS_APPLY_FAILURE", {
        failure,
        accepted: accepted.raw || accepted,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "canvas_apply"),
        undoStackDepth: panel.state.undoStack.length,
        debugPayload: {
          ...failure,
          accepted: accepted.raw || accepted,
          undo_stack_depth: panel.state.undoStack.length,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      pushHistory(panel, "failure", failure.kind || "CanvasApplyError");
      pushTurnStatus(panel, "failed", {
        session_id: failure.session_id || panel.state.sessionId,
        turn_id: failure.turn_id || panel.state.turnId,
        baseline_turn_id: failure.baseline_turn_id || panel.state.baselineTurnId,
        failure_kind: failure.kind || "CanvasApplyError",
        failure_stage: failure.stage || "canvas_apply",
        message: failure.user_facing_message || failure.message || failure.error,
        audit_ref: failure.audit_ref,
        raw_payload: failure,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: failure.turn_id || panel.state.turnId,
        session_id: failure.session_id || panel.state.sessionId,
        failure,
        message: failure.user_facing_message || failure.message || failure.error,
      });
      renderLifecycleTransition(panel, obligations);
      return;
    }
    const lastAppliedChanges = announceChangedNodes(panel, extractChangedNodeFeedback(panel.state.candidateReport));
    pushHistory(panel, "applied", panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate");
    pushTurnStatus(panel, "applied", {
      turn_id: panel.state.turnId,
      baseline_turn_id: accepted.baselineTurnId || panel.state.turnId,
      message: panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate",
      audit_ref: accepted.auditRef || panel.state.auditRef,
      raw_payload: accepted.raw || accepted,
    });
    const successObligations = transition(panel, "APPLY_SUCCESS", {
      accepted: accepted.raw || accepted,
      lastAppliedChanges,
      undoStackDepth: panel.state.undoStack.length,
      message: "Candidate accepted and applied locally.",
      toast: "Agent candidate applied",
      debugPayload: {
        accepted,
        undo_stack_depth: panel.state.undoStack.length,
      },
    });
    fulfillLifecycleTransitionObligations(panel, successObligations);
    rememberTurnDetailSnapshot(panel, {
      turn_id: accepted.turnId || panel.state.turnId,
      session_id: accepted.sessionId || panel.state.sessionId,
      auditRef: accepted.auditRef || panel.state.auditRef,
      debugPayload: {
        accepted: accepted.raw || accepted,
        undo_stack_depth: panel.state.undoStack.length,
      },
      message: panel.state.message,
    });
    renderLifecycleTransition(panel, successObligations);
  })();

  transition(panel, "APPLY_IN_FLIGHT", { promise: applyPromise });
  try {
    return await panel.state.inFlightApply;
  } finally {
    transition(panel, "APPLY_FINALLY", { clearInFlightApply: true });
  }
}

async function rejectAgentCandidate(panel) {
  if (!panel?.state?.candidateGraph) {
    return;
  }

  let snapshot;
  try {
    snapshot = await buildCanvasSnapshot();
  } catch (e) {
    const failure = agentPanelFailure("SerializeError", String(e), {
      retryable: true,
      graph_unchanged: true,
      next_action: "Make sure the canvas can serialize, then retry Reject.",
    });
    const obligations = transition(panel, "REJECT_FAILURE", {
      failure,
      debugPayload: failure,
    });
    if (obligations.render) renderAgentPanel(panel);
    return;
  }

  const rejectKey = buildActionIdempotencyKey({
    action: "reject",
    sessionId: panel.state.sessionId,
    turnId: panel.state.turnId,
    graphHash: snapshot.graphHash,
  });
  const rejectBody = {
    session_id: panel.state.sessionId,
    turn_id: panel.state.turnId,
    client_graph_hash: snapshot.graphHash,
    idempotency_key: rejectKey,
  };

  const startObligations = transition(panel, "REJECT_STARTED", {
    rejectBody,
    debugPayload: {
      rejecting_turn_id: panel.state.turnId,
      reject_request: rejectBody,
    },
  });
  if (startObligations.render) renderAgentPanel(panel);

  let rejected;
  try {
    const res = await fetch("/vibecomfy/agent-edit/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rejectBody),
    });
    const rawRejected = await res.json();
    rejected = normalizeAuxiliaryAgentPayload(rawRejected, "reject");
    if (!res.ok || rejected?.ok === false || rejected.raw?.error) {
      throw rejected.raw || { kind: "RejectError", message: res.statusText };
    }
  } catch (e) {
    const failure = e?.ok === false
      ? e
      : agentPanelFailure("RejectError", String(e), {
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry Reject after the backend responds again.",
        });
    const obligations = transition(panel, "REJECT_FAILURE", {
      failure,
      rejectBody,
      debugPayload: {
        ...failure,
        reject_request: rejectBody,
      },
    });
    const recovery = extractRebaselineRecovery(failure);
    transition(panel, "REBASELINE_RECOVERY_SYNC", { rebaselineRecovery: recovery });
    pushHistory(panel, "failure", failure.kind || "RejectError");
      pushTurnStatus(panel, "failed", {
        session_id: failure.session_id || panel.state.sessionId,
        turn_id: failure.turn_id || panel.state.turnId,
      baseline_turn_id: failure.baseline_turn_id || panel.state.baselineTurnId,
      failure_kind: failure.kind || "RejectError",
      failure_stage: failure.stage || "reject",
      message: failure.user_facing_message || failure.message || failure.error,
        audit_ref: failure.audit_ref,
        raw_payload: failure,
      });
      rememberTurnDetailSnapshot(panel, {
        turn_id: failure.turn_id || panel.state.turnId,
        session_id: failure.session_id || panel.state.sessionId,
        failure,
        message: failure.user_facing_message || failure.message || failure.error,
      });
      if (obligations.render) renderAgentPanel(panel);
    return;
  }

  pushHistory(panel, "rejected", panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate");
  pushTurnStatus(panel, "rejected", {
    turn_id: panel.state.turnId,
    baseline_turn_id: rejected.baselineTurnId || panel.state.baselineTurnId,
    message: panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate",
    audit_ref: rejected.auditRef || panel.state.auditRef,
    raw_payload: rejected.raw || rejected,
  });

  const obligations = transition(panel, "REJECT_SUCCESS", {
    rejected: rejected.raw || rejected,
    message: "Candidate rejected and cleared from the panel.",
    toast: "Agent candidate rejected",
    debugPayload: {
      rejected: rejected.raw || rejected,
      graph_unchanged: true,
    },
  });

  fulfillLifecycleTransitionObligations(panel, obligations);

  const recovery = rejected.rebaselineRecovery || null;
  transition(panel, "REBASELINE_RECOVERY_SYNC", {
    ...(recovery ? { rebaselineRecovery: recovery } : { clearRebaselineRecovery: rejected.ok === true }),
  });

  rememberTurnDetailSnapshot(panel, {
    turn_id: rejected.turnId || panel.state.turnId,
    session_id: rejected.sessionId || panel.state.sessionId,
    auditRef: rejected.auditRef || panel.state.auditRef,
    debugPayload: {
      rejected: rejected.raw || rejected,
      graph_unchanged: true,
    },
    message: panel.state.message,
  });

  renderLifecycleTransition(panel, obligations);
}

export async function postAgentRebaseline(
  panel,
  { reason, graphSnapshot = null, lastKnownBaselineGraphHash = undefined } = {},
) {
  if (!panel?.state) {
    return null;
  }
  if (panel.state.inFlightRebaseline) {
    return panel.state.inFlightRebaseline;
  }
  if (!panel.state.sessionId) {
    throw agentPanelFailure("MissingRequiredField", "Cannot rebaseline without a session_id.", {
      retryable: false,
      graph_unchanged: true,
      next_action: "Submit an agent edit first so the session exists.",
    });
  }

  const rebaselinePromise = (async () => {
    let body = null;
    let rebaselineReason = "continue_from_canvas";
    try {
      let snapshot = graphSnapshot;
      if (!snapshot) {
        snapshot = await buildCanvasSnapshot();
      }
      rebaselineReason = String(reason || "continue_from_canvas").trim() || "continue_from_canvas";
      const expectedBaselineGraphHash =
        lastKnownBaselineGraphHash !== undefined
          ? lastKnownBaselineGraphHash
          : (panel.state.baselineGraphHash || null);
      const idempotencyKey = buildRebaselineIdempotencyKey({
        sessionId: panel.state.sessionId,
        reason: rebaselineReason,
        baselineGraphHash: expectedBaselineGraphHash,
        structuralHash: snapshot.structuralHash,
      });
      const rebaselinePending = {
        reason: rebaselineReason,
        last_known_baseline_graph_hash: expectedBaselineGraphHash,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        idempotency_key: idempotencyKey,
      };
      const startedObligations = transition(panel, "REBASELINE_STARTED", {
        rebaselinePending,
      });
      renderLifecycleTransition(panel, startedObligations);

      body = {
        session_id: panel.state.sessionId,
        graph: snapshot.graph,
        reason: rebaselineReason,
        last_known_baseline_graph_hash: expectedBaselineGraphHash,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        idempotency_key: idempotencyKey,
      };

      const res = await fetch("/vibecomfy/agent-edit/rebaseline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const rawRebaseline = await res.json();
      const result = normalizeAuxiliaryAgentPayload(rawRebaseline, "rebaseline");
      if (!res.ok || result?.ok === false || result.raw?.error) {
        throw result.raw || { kind: "RebaselineError", message: res.statusText };
      }
      const successObligations = transition(panel, "REBASELINE_SUCCESS", {
        result: result.raw || result,
        rebaselineRequest: body,
        debugPayload: {
          rebaseline_request: body,
          rebaseline_response: result.raw || result,
        },
      });
      fulfillLifecycleTransitionObligations(panel, successObligations);
      return result;
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("RebaselineError", String(e), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry the rebaseline request after the backend responds again.",
          });
      const failureObligations = transition(panel, "REBASELINE_FAILURE", {
        failure,
        rebaselineRequest: body,
        rebaselineRecovery: extractRebaselineRecovery(failure),
        rebaselinePendingPatch: {
          reason: rebaselineReason,
          retryable: Boolean(failure.retryable),
          failure_kind: failure.kind || null,
          failure_stage: failure.stage || null,
          message: failure.user_facing_message || failure.message || failure.error || null,
        },
        debugPayload: {
          ...failure,
          rebaseline_request: body,
        },
      });
      fulfillLifecycleTransitionObligations(panel, failureObligations);
      throw failure;
    } finally {
      const finallyObligations = transition(panel, "REBASELINE_FINALLY", {
        clearInFlightRebaseline: true,
      });
      renderLifecycleTransition(panel, finallyObligations);
    }
  })();

  transition(panel, "REBASELINE_IN_FLIGHT", { promise: rebaselinePromise });

  return rebaselinePromise;
}

async function rebaselineCurrentCanvas(panel) {
  const recovery = panel?.state?.rebaselineRecovery;
  if (!recovery) {
    renderAgentPanel(panel);
    return null;
  }
  if (panel.state.inFlightRebaseline) {
    return panel.state.inFlightRebaseline;
  }
  const queuedObligations = transition(panel, "STALE_RECOVERY_REBASELINE_QUEUED");
  renderLifecycleTransition(panel, queuedObligations);
  try {
    const result = await postAgentRebaseline(panel, {
      reason: "stale_state_recovery",
      lastKnownBaselineGraphHash: recovery.last_known_baseline_graph_hash ?? null,
    });
    const successObligations = transition(panel, "STALE_RECOVERY_REBASELINE_SUCCESS", {
      auditRef: result.auditRef || panel.state.auditRef,
      message: "Current canvas rebaselined. Resubmitting from this canvas...",
      toast: "Current canvas rebaselined",
      debugPayload: {
        stale_state_recovery: true,
        rebaseline_response: result.raw || result,
      },
    });
    fulfillLifecycleTransitionObligations(panel, successObligations);
    renderLifecycleTransition(panel, successObligations);
    await submitAgentEdit(panel);
    return result;
  } catch (failure) {
    const failureObligations = transition(panel, "STALE_RECOVERY_REBASELINE_FAILURE", {
      rebaselineRecovery: extractRebaselineRecovery(failure) || recovery,
      message: "Current canvas rebaseline failed. Review the evidence and retry.",
      debugPayload: {
        ...(panel.state.debugPayload || {}),
        stale_state_recovery: true,
      },
    });
    renderLifecycleTransition(panel, failureObligations);
    return null;
  }
}

async function undoLastApply(panel) {
  const undoStack = panel?.state?.undoStack;
  const previous = Array.isArray(undoStack) ? undoStack[undoStack.length - 1] : null;
  if (!previous?.graph) {
    renderAgentPanel(panel);
    return null;
  }
  if (panel.state.inFlightRebaseline) {
    return panel.state.inFlightRebaseline;
  }
  await app.loadGraphData(previous.graph);
  const restoreObligations = transition(panel, "UNDO_LOCAL_RESTORE", {
    previous,
    undoStackDepth: panel.state.undoStack.length,
  });
  fulfillLifecycleTransitionObligations(panel, restoreObligations);
  renderLifecycleTransition(panel, restoreObligations);
  try {
    const result = await postAgentRebaseline(panel, {
      reason: "undo",
      lastKnownBaselineGraphHash:
        previous.accepted_baseline_graph_hash
        ?? panel.state.rebaselinePending?.last_known_baseline_graph_hash
        ?? panel.state.baselineGraphHash
        ?? null,
    });
    pushHistory(panel, "undo", previous.turn_id ? `restored pre-apply graph for turn ${previous.turn_id}` : "restored previous graph");
    pushTurnStatus(panel, "undone", {
      turn_id: previous.turn_id || null,
      baseline_turn_id: result.baselineTurnId || null,
      message: previous.turn_id ? `restored pre-apply graph for turn ${previous.turn_id}` : "restored previous graph",
      audit_ref: result.auditRef || panel.state.auditRef,
      raw_payload: result.raw || result,
    });
    const successObligations = transition(panel, "UNDO_REBASELINE_SUCCESS", {
      previous,
      result: result.raw || result,
      undoStackDepth: panel.state.undoStack.length - 1,
      toast: "Previous graph restored",
    });
    fulfillLifecycleTransitionObligations(panel, successObligations);
    renderLifecycleTransition(panel, successObligations);
    return result;
  } catch (failure) {
    const normalizedFailure = failure && typeof failure === "object"
      ? failure
      : agentPanelFailure("RebaselineError", String(failure), {
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry Undo Rebaseline after the backend responds again.",
        });
    const failureObligations = transition(panel, "UNDO_REBASELINE_FAILURE", {
      previous,
      failure: normalizedFailure,
      rebaselineRecovery: extractRebaselineRecovery(normalizedFailure) || panel.state.rebaselineRecovery,
      undoStackDepth: panel.state.undoStack.length,
    });
    renderLifecycleTransition(panel, failureObligations);
    return null;
  }
}

async function openRoundtrip() {
  let graph;
  try {
    graph = app.canvas.graph.serialize();
  } catch (e) {
    return errorModal({ kind: "SerializeError", message: String(e) });
  }
  let result;
  try {
    const res = await fetch("/vibecomfy/roundtrip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph }),
    });
    result = await res.json();
    if (!res.ok || result?.error) {
      return errorModal({ kind: result?.kind, message: result?.error || res.statusText });
    }
  } catch (e) {
    return errorModal({ kind: "NetworkError", message: String(e) });
  }
  renderDiffModal({ graph: result.graph, report: result.report });
}

function openAgentEdit() {
  const panel = openAgentPanel({ mode: AGENT_PANEL_MOUNT_MODE.LAUNCHER });
  panel.root.dataset.lastCommand = "agent-edit";
  renderAgentPanel(panel);
}

// Always-visible edge tab so the agent panel is discoverable without hunting
// through the right-click / Extensions menu. Toggles the panel open/closed.
function ensureAgentLauncher() {
  if (document.getElementById("vibecomfy-agent-launcher")) {
    return;
  }
  const btn = document.createElement("button");
  btn.id = "vibecomfy-agent-launcher";
  btn.type = "button";
  btn.textContent = "✨ VibeComfy Agent";
  btn.title = "Open the VibeComfy agent edit panel";
  Object.assign(btn.style, {
    position: "fixed",
    right: "0px",
    top: "45%",
    zIndex: "100000",
    writingMode: "vertical-rl",
    padding: "12px 7px",
    background: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px 0 0 8px",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: "600",
    letterSpacing: "0.04em",
    boxShadow: "0 2px 12px rgba(0,0,0,0.45)",
  });
  btn.addEventListener("click", () => {
    const panel = ensureAgentPanel();
    if (
      panel.root.dataset.open === "1"
      && panel.state.mountMode === AGENT_PANEL_MOUNT_MODE.LAUNCHER
    ) {
      closeAgentPanel(panel);
    } else {
      openAgentEdit();
    }
  });
  document.body.appendChild(btn);
}

function ensureAgentSidebarTab() {
  const manager = app?.extensionManager;
  if (!manager || typeof manager.registerSidebarTab !== "function") {
    return false;
  }
  if (agentSidebarTabRegistered) {
    return true;
  }
  const tab = {
    id: AGENT_SIDEBAR_TAB_ID,
    title: "VibeComfy Agent",
    tooltip: "Open the VibeComfy agent edit panel",
    icon: "pi pi-sparkles",
    type: "custom",
    render: mountAgentSidebarPanel,
    mount: mountAgentSidebarPanel,
  };
  try {
    manager.registerSidebarTab(tab);
    agentSidebarTabRegistered = true;
    return true;
  } catch (error) {
    try {
      manager.registerSidebarTab(
        AGENT_SIDEBAR_TAB_ID,
        "VibeComfy Agent",
        "pi pi-sparkles",
        mountAgentSidebarPanel,
      );
      agentSidebarTabRegistered = true;
      return true;
    } catch (fallbackError) {
      console.warn("[vibecomfy] failed to register agent sidebar tab", fallbackError || error);
      return false;
    }
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────
function el(tag, text) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  return node;
}

function button(label, onClick) {
  const node = el("button", label);
  node.onclick = onClick;
  Object.assign(node.style, {
    margin: "0",
    padding: "7px 10px",
    borderRadius: "6px",
    border: "1px solid #414855",
    background: "#272b33",
    color: "#edf2f7",
    cursor: "pointer",
    fontFamily: "monospace",
    fontSize: "12px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  });
  return node;
}

function makeOverlay() {
  const overlay = el("div");
  Object.assign(overlay.style, {
    position: "fixed",
    inset: "0",
    background: "rgba(0,0,0,0.6)",
    zIndex: "10000",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  });
  document.body.appendChild(overlay);
  return overlay;
}

function makeBox(overlay) {
  const box = el("div");
  Object.assign(box.style, {
    background: "#222",
    color: "#eee",
    padding: "16px",
    maxHeight: "80vh",
    overflow: "auto",
    borderRadius: "8px",
    minWidth: "360px",
    fontFamily: "monospace",
  });
  overlay.appendChild(box);
  return box;
}

function row(uid, color, label, tooltip) {
  const node = el("div", `${label} ${uid}`);
  node.style.color = color;
  if (tooltip) node.title = tooltip;
  return node;
}

// ── Diff modal (legacy round-trip command) ───────────────────────────────
function renderDiffModal({ graph, report, message = null }) {
  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", "Round-trip (VibeComfy)"));
  if (message) {
    const msg = el("p", message);
    msg.style.whiteSpace = "pre-wrap";
    msg.style.maxWidth = "640px";
    box.appendChild(msg);
  }

  const rows = collectDiffRows(report);
  for (const item of rows) {
    const line = el("div", item.text);
    line.style.color = item.color;
    if (item.title) {
      line.title = item.title;
    }
    box.appendChild(line);
  }

  const removedNamed = report?.change?.content_edits?.removed_named || [];
  const schemaLess = (report?.recovery || []).filter((item) => item?.schema_less === true);
  const needsConfirm = removedNamed.length > 0 || schemaLess.length > 0;
  const applyBtn = button("Apply", () => doApply(graph, overlay, applyBtn, needsConfirm, removedNamed.length, schemaLess.length));
  if (needsConfirm) {
    applyBtn.style.opacity = "0.7";
    applyBtn.style.background = "#555";
  }
  box.appendChild(applyBtn);
  box.appendChild(button("Cancel", () => overlay.remove()));
}

function doApply(graph, overlay, applyBtn, needsConfirm, removedCount, schemaLessCount) {
  if (needsConfirm && applyBtn.dataset.confirmed !== "1") {
    applyBtn.dataset.confirmed = "1";
    applyBtn.textContent = `${removedCount} nodes will be removed and ${schemaLessCount} are schema-less; apply anyway?`;
    return;
  }
  app.loadGraphData(graph);
  overlay.remove();
  toast("Round-trip applied");
}

function toast(msg) {
  if (app.extensionManager?.toast?.add) {
    app.extensionManager.toast.add({ severity: "success", summary: msg, life: 3000 });
  } else {
    console.log(`VibeComfy: ${msg}`);
  }
}

app.registerExtension({
  name: "VibeComfy.Roundtrip",
  commands: [
    { id: "VibeComfy.Roundtrip", label: "Round-trip (VibeComfy)", function: openRoundtrip },
    { id: "VibeComfy.AgentEdit", label: "Edit with DeepSeek (VibeComfy)", function: openAgentEdit },
  ],
  menuCommands: [{ path: ["Extensions", "VibeComfy"], commands: ["VibeComfy.Roundtrip", "VibeComfy.AgentEdit"] }],
  async beforeRegisterNodeDef(nodeType, nodeData) {
    patchIntentNodePrototype(nodeType, nodeData);
  },
  async setup() {
    await checkFrontendVersion();
    installIntentNodeFallback();
    installAgentPreviewOverlay();
    decorateLiveIntentNodes();
    installQueueGuard();
    ensureAgentTurnListener();
    installAgentPanelDebugHook();
    const proto = window.LiteGraph?.LGraphCanvas?.prototype;
    if (proto && !proto.__vibecomfyRoundtripPatched) {
      proto.__vibecomfyRoundtripPatched = true;
      const orig = proto.getCanvasMenuOptions;
      proto.getCanvasMenuOptions = function () {
        const opts = orig ? orig.apply(this, arguments) : [];
        opts.push({ content: "Round-trip (VibeComfy)", callback: openRoundtrip });
        opts.push({ content: "Edit with DeepSeek (VibeComfy)", callback: openAgentEdit });
        return opts;
      };
    }
    ensureAgentPanel();
    ensureAgentSidebarTab();
    ensureAgentLauncher();
  },
});
