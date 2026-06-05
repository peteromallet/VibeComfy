import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

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
  NOT_LATEST: "not_latest",
  SUPERSEDED: "superseded",
  SERVER_BLOCKED: "server_blocked",
  STALE_CANVAS: "stale_canvas",
  QUEUE_BLOCKED_WARNING: "queue_blocked_warning",
});

const PANEL_IDS = Object.freeze({
  root: "vibecomfy-agent-panel-root",
  shell: "vibecomfy-agent-panel-shell",
  status: "vibecomfy-agent-panel-status",
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
  promptRegion: "vibecomfy-agent-panel-region-prompt",
  settingsRegion: "vibecomfy-agent-panel-region-settings",
  historyRegion: "vibecomfy-agent-panel-region-history",
  candidateRegion: "vibecomfy-agent-panel-region-candidate",
  failureRegion: "vibecomfy-agent-panel-region-failure",
  queueRegion: "vibecomfy-agent-panel-region-queue",
  auditRegion: "vibecomfy-agent-panel-region-audit",
  debugRegion: "vibecomfy-agent-panel-region-debug",
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

const FALLBACK_ROUTE_OPTIONS = Object.freeze({
  auto: {
    requested_route: "auto",
    normalized_route: "arnold",
    browser_api_key_allowed: false,
    guidance: "Use local Arnold/Hermes setup for this route. Browser-submitted API keys are not stored.",
    tos_acknowledgement_required: false,
  },
  deepseek: {
    requested_route: "deepseek",
    normalized_route: "deepseek",
    browser_api_key_allowed: true,
    guidance: "DeepSeek browser key submission is supported and stored locally.",
    tos_acknowledgement_required: false,
  },
  anthropic: {
    requested_route: "anthropic",
    normalized_route: "arnold",
    browser_api_key_allowed: false,
    guidance: "Anthropic/Claude runs through local Arnold/Hermes. Browser keys are not accepted.",
    tos_acknowledgement_required: true,
  },
  "openai-codex": {
    requested_route: "openai-codex",
    normalized_route: "arnold",
    browser_api_key_allowed: false,
    guidance: "OpenAI Codex runs through local Arnold/Hermes. Browser keys are not accepted.",
    tos_acknowledgement_required: false,
  },
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
let _progressPulseInjected = false;

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
  const width = Array.isArray(node?.size) ? Number(node.size[0] || 180) : 180;
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
  const graph = getLiveGraph();
  if (!graph || typeof graph.clear !== "function" || typeof graph.configure !== "function") {
    throw agentPanelFailure("CanvasApplyError", "The live LiteGraph instance does not support in-place graph application.", {
      retryable: true,
      graph_unchanged: true,
      next_action: "Retry after the ComfyUI frontend finishes loading, or use the legacy round-trip command.",
    });
  }
  decorateIntentGraphPayload(candidate);
  graph.clear();
  graph.configure(candidate);
  decorateLiveIntentNodes();
  // graph.configure() updates the data model but does NOT repaint the canvas,
  // so an applied edit (added/removed/rewired nodes) is invisible until some
  // other interaction forces a redraw. Trigger a repaint explicitly so the
  // result of Apply is immediately visible in the UI.
  try {
    if (typeof graph.change === "function") graph.change();
    if (typeof graph.setDirtyCanvas === "function") {
      graph.setDirtyCanvas(true, true);
    } else if (app?.canvas?.setDirty) {
      app.canvas.setDirty(true, true);
    }
    app?.canvas?.draw?.(true, true);
  } catch (e) {
    // Best-effort: the candidate is already applied to the graph data; a failed
    // redraw must not turn a successful Apply into an error.
    console.warn("[vibecomfy] post-apply canvas redraw failed (data applied):", e);
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
  // Draw the pending-candidate preview overlay onto whatever canvas/context
  // LiteGraph is currently rendering.
  const overlayDraw = function (ctx) {
    const panel = agentPanel;
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

  // This ComfyUI build assigns an INSTANCE-level `app.canvas.onDrawForeground`
  // (the prototype method is null) AND reassigns it after we patch — on graph
  // load / canvas recreation — which silently discards a one-shot wrapper. So we
  // TAG our wrapper and re-install it via a lightweight guard whenever the live
  // method is no longer ours, chaining to whatever the build last set.
  const protoFn = window.LiteGraph?.LGraphCanvas?.prototype?.onDrawForeground;
  const ensurePatched = function () {
    const canvas = app?.canvas;
    if (!canvas) {
      return;
    }
    const current = canvas.onDrawForeground;
    if (current && current.__vibecomfyOverlayWrapper) {
      return;
    }
    const orig = current;
    const wrapper = function (ctx, ...args) {
      try {
        if (orig && orig !== wrapper) {
          orig.call(this, ctx, ...args);
        } else if (protoFn) {
          protoFn.call(this, ctx, ...args);
        }
      } catch (e) {
        console.warn("[vibecomfy] original onDrawForeground threw:", e);
      }
      overlayDraw.call(this, ctx);
    };
    wrapper.__vibecomfyOverlayWrapper = true;
    canvas.onDrawForeground = wrapper;
  };
  ensurePatched();
  // Re-assert the wrapper periodically; the build re-creates the canvas method.
  setInterval(ensurePatched, 1000);
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
    return value.map((entry) => canonicalizeJsonValue(entry));
  }
  if (value && typeof value === "object") {
    return canonicalizeJsonValue(value);
  }
  return value;
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

export function buildStructuralGraphProjection(graph) {
  const nodes = Array.isArray(graph?.nodes)
    ? graph.nodes.map((node) => ({
        id: node?.id ?? null,
        type: node?.type ?? null,
        mode: node?.mode ?? null,
        inputs: Array.isArray(node?.inputs)
          ? node.inputs.map((input) => ({
              name: input?.name ?? null,
              link: input?.link ?? null,
            }))
          : [],
        outputs: Array.isArray(node?.outputs)
          ? node.outputs.map((output) => ({
              name: output?.name ?? null,
              links: Array.isArray(output?.links) ? [...output.links].sort() : output?.links ?? null,
            }))
          : [],
        widgets_values: _normalizeStructuralWidgetValue(node?.widgets_values ?? []),
      }))
    : [];
  nodes.sort((left, right) => {
    const leftId = String(left.id ?? "");
    const rightId = String(right.id ?? "");
    const idCmp = leftId.localeCompare(rightId, undefined, { numeric: true });
    return idCmp || String(left.type ?? "").localeCompare(String(right.type ?? ""));
  });
  const links = Array.isArray(graph?.links)
    ? graph.links.map((link) => _normalizeStructuralLink(link))
    : [];
  links.sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
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
  const pre = el("pre", safeJson(value));
  Object.assign(pre.style, {
    margin: "8px 0 0 0",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    color: "#b9ffcc",
    fontSize: "11px",
  });
  details.appendChild(heading);
  details.appendChild(pre);
  return details;
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

function getRouteOptions(panel) {
  const options = panel.state.statusSnapshot?.route_options;
  return options && typeof options === "object" ? options : FALLBACK_ROUTE_OPTIONS;
}

function getRouteDescriptor(panel, route = panel.fields.route.value) {
  const normalized = normalizeRoutePreference(route);
  return getRouteOptions(panel)[normalized] || FALLBACK_ROUTE_OPTIONS[normalized] || FALLBACK_ROUTE_OPTIONS.auto;
}

function populateRouteSelect(selectNode, routeOptions) {
  const existing = Array.from(selectNode.children || []).map((child) => child.value);
  const desired = Object.keys(ROUTE_LABELS);
  if (existing.length === desired.length && desired.every((value, index) => existing[index] === value)) {
    return;
  }
  clearNode(selectNode);
  for (const route of desired) {
    const descriptor = routeOptions?.[route] || FALLBACK_ROUTE_OPTIONS[route];
    const label = ROUTE_LABELS[route];
    const node = option(route, label);
    if (descriptor?.normalized_route && descriptor.normalized_route !== route) {
      node.title = `${label} → ${descriptor.normalized_route}`;
    }
    selectNode.appendChild(node);
  }
}

async function refreshAgentStatus(panel, { quiet = false } = {}) {
  const route = normalizeRoutePreference(panel.fields.route.value);
  const model = normalizeModelPreference(panel.fields.model.value);
  try {
    const res = await fetch(buildStatusUrl(route, model));
    const status = await res.json();
    if (
      normalizeRoutePreference(panel.fields.route.value) !== route
      || normalizeModelPreference(panel.fields.model.value) !== model
    ) {
      return;
    }
    panel.state.statusSnapshot = status;
    populateRouteSelect(panel.fields.route, status?.route_options || FALLBACK_ROUTE_OPTIONS);
    panel.fields.route.value = normalizeRoutePreference(status?.requested_route || route);
    if (typeof status?.model === "string" && !panel.fields.model.value.trim()) {
      panel.fields.model.value = status.model;
    }
    if (!quiet) {
      const availability = status?.provider_available === false ? "provider unavailable" : "provider ready";
      panel.state.settingsMessage = `${status?.requested_route || route} → ${status?.route || route} (${availability})`;
    }
  } catch (e) {
    panel.state.settingsMessage = `Status unavailable: ${String(e)}`;
    panel.state.statusSnapshot = null;
  }
  if (typeof document === "undefined") {
    return;
  }
  renderAgentPanel(panel);
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

function compatibilityApplyEligibility(panel) {
  if (!panel?.state?.candidateGraph) {
    return {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.NO_CANDIDATE,
      message: "No candidate is available to apply.",
      warnings: [],
    };
  }
  if (panel.state.canvasApplyAllowed !== true) {
    return {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.SERVER_BLOCKED,
      message: "Server validation gates blocked Apply.",
      warnings: [],
    };
  }
  if (panel.state.queueAllowed !== true) {
    return {
      applyable: true,
      reason: APPLY_ELIGIBILITY_REASON.QUEUE_BLOCKED_WARNING,
      message: "Apply is allowed, but Queue remains blocked for this candidate.",
      warnings: ["queue_blocked"],
    };
  }
  return {
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Apply is allowed.",
    warnings: [],
  };
}

export function syncBaselineFromResponse(panel, payload) {
  if (!panel?.state || !payload || typeof payload !== "object") {
    return;
  }
  const hadExplicitSource = Object.prototype.hasOwnProperty.call(payload, "baseline_source");
  if ("baseline_turn_id" in payload) {
    panel.state.baselineTurnId = typeof payload.baseline_turn_id === "string"
      ? payload.baseline_turn_id
      : null;
  }
  if ("baseline_graph_hash" in payload) {
    panel.state.baselineGraphHash = typeof payload.baseline_graph_hash === "string"
      ? payload.baseline_graph_hash
      : null;
  }
  if ("baseline_graph_hash_kind" in payload) {
    panel.state.baselineGraphHashKind = typeof payload.baseline_graph_hash_kind === "string"
      ? payload.baseline_graph_hash_kind
      : null;
  }
  if ("baseline_graph_hash_version" in payload) {
    panel.state.baselineGraphHashVersion = Number.isFinite(payload.baseline_graph_hash_version)
      ? payload.baseline_graph_hash_version
      : null;
  }
  if ("baseline_source" in payload) {
    panel.state.baselineSource = typeof payload.baseline_source === "string"
      ? payload.baseline_source
      : "none";
  }
  if ("baseline_rebaseline_id" in payload) {
    panel.state.baselineRebaselineId = typeof payload.baseline_rebaseline_id === "string"
      ? payload.baseline_rebaseline_id
      : null;
  }
  if ("baseline_graph_source_path" in payload) {
    panel.state.baselineGraphSourcePath = typeof payload.baseline_graph_source_path === "string"
      ? payload.baseline_graph_source_path
      : null;
  }
  if (!hadExplicitSource && payload.action === "accept" && payload.ok === true) {
    panel.state.baselineSource = "turn";
    panel.state.baselineRebaselineId = null;
    panel.state.baselineGraphSourcePath = typeof payload.turn_id === "string"
      ? `turns/${payload.turn_id}/candidate.ui.json`
      : null;
  } else if (
    !hadExplicitSource
    && panel.state.baselineTurnId
    && typeof panel.state.baselineGraphHash === "string"
    && panel.state.baselineGraphHash
  ) {
    panel.state.baselineSource = "turn";
    panel.state.baselineRebaselineId = null;
    if (!panel.state.baselineGraphSourcePath) {
      panel.state.baselineGraphSourcePath = `turns/${panel.state.baselineTurnId}/candidate.ui.json`;
    }
  } else if (
    !hadExplicitSource
    && panel.state.baselineTurnId == null
    && panel.state.baselineGraphHash == null
  ) {
    panel.state.baselineSource = "none";
    panel.state.baselineRebaselineId = null;
    panel.state.baselineGraphSourcePath = null;
  }
  const recovery = extractRebaselineRecovery(payload);
  if (recovery) {
    panel.state.rebaselineRecovery = recovery;
  } else if (payload.ok === true) {
    panel.state.rebaselineRecovery = null;
  }
}

function normalizeRebaselineRecovery(recovery) {
  if (!recovery || typeof recovery !== "object") {
    return null;
  }
  return {
    action: typeof recovery.action === "string" ? recovery.action : null,
    endpoint: typeof recovery.endpoint === "string" ? recovery.endpoint : null,
    reason: typeof recovery.reason === "string" ? recovery.reason : null,
    last_known_baseline_graph_hash:
      typeof recovery.last_known_baseline_graph_hash === "string"
        ? recovery.last_known_baseline_graph_hash
        : null,
    submit_graph_hash:
      typeof recovery.submit_graph_hash === "string" ? recovery.submit_graph_hash : null,
    submit_structural_graph_hash:
      typeof recovery.submit_structural_graph_hash === "string"
        ? recovery.submit_structural_graph_hash
        : null,
    client_graph_hash:
      typeof recovery.client_graph_hash === "string" ? recovery.client_graph_hash : null,
    client_structural_graph_hash:
      typeof recovery.client_structural_graph_hash === "string"
        ? recovery.client_structural_graph_hash
        : null,
  };
}

function extractRebaselineRecovery(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const topLevel = normalizeRebaselineRecovery(payload.rebaseline_recovery);
  if (topLevel) {
    return topLevel;
  }
  const issues = payload.agent_failure_context?.issues;
  if (!Array.isArray(issues)) {
    return null;
  }
  for (const issue of issues) {
    const recovery = normalizeRebaselineRecovery(issue?.rebaseline_recovery);
    if (recovery) {
      return recovery;
    }
  }
  return null;
}

function applyEligibility(panel, liveCanvasSnapshot = null) {
  if (!panel?.state?.candidateGraph) {
    return compatibilityApplyEligibility(panel);
  }
  const submitStructuralHash = panel.state.lastSubmit?.client_structural_graph_hash;
  const liveStructuralHash = liveCanvasSnapshot?.structuralHash;
  if (
    typeof submitStructuralHash === "string"
    && submitStructuralHash
    && typeof liveStructuralHash === "string"
    && liveStructuralHash
    && liveStructuralHash !== submitStructuralHash
  ) {
    return {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.STALE_CANVAS,
      message: "The live canvas no longer matches the submitted candidate baseline.",
      warnings: [],
    };
  }
  return normalizeApplyEligibility(panel.state.applyEligibility) || compatibilityApplyEligibility(panel);
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

function createAgentPanel() {
  const root = el("aside");
  root.id = PANEL_IDS.root;
  root.className = "vibecomfy-agent-panel-root";
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
    height: "100%",
    display: "grid",
    gridTemplateRows: "auto auto 1fr auto",
    background: "#101115",
    color: "#edf2f7",
    borderLeft: "1px solid #282a32",
    boxShadow: "-10px 0 28px rgba(0,0,0,0.38)",
    fontFamily: "monospace",
    pointerEvents: "auto",
  });

  const header = el("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    padding: "12px 14px 8px 14px",
    borderBottom: "1px solid #282a32",
  });
  const headerText = el("div");
  const title = el("div", "VibeComfy Agent Edit");
  title.style.fontWeight = "700";
  title.style.fontSize = "13px";
  headerText.appendChild(title);
  const sub = el("div", "Durable panel shell. Round-trip modal remains unchanged.");
  sub.style.fontSize = "11px";
  sub.style.color = "#8d93a1";
  headerText.appendChild(sub);
  header.appendChild(headerText);

  const status = el("div", "Idle");
  status.id = PANEL_IDS.status;
  Object.assign(status.style, {
    fontSize: "11px",
    color: "#9da1ac",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  });
  header.appendChild(status);

  const metaRow = el("div");
  Object.assign(metaRow.style, {
    display: "flex",
    gap: "12px",
    padding: "8px 14px",
    borderBottom: "1px solid #282a32",
    background: "#14161b",
    fontSize: "11px",
    color: "#8d93a1",
    flexWrap: "wrap",
  });

  const body = el("div");
  Object.assign(body.style, {
    overflowY: "auto",
    padding: "12px 14px",
    display: "grid",
    gap: "12px",
    alignContent: "start",
  });

  const promptRegion = panelSection(PANEL_IDS.promptRegion, "Prompt");
  const textarea = document.createElement("textarea");
  textarea.id = PANEL_IDS.prompt;
  textarea.placeholder = "Describe the workflow change...";
  Object.assign(textarea.style, {
    width: "100%",
    minHeight: "120px",
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

  const settingsRegion = panelSection(PANEL_IDS.settingsRegion, "Settings");
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
  populateRouteSelect(routeSelect, FALLBACK_ROUTE_OPTIONS);
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
  const settingsSave = button("Save Settings", () => saveAgentSettings(agentPanel));
  settingsSave.id = PANEL_IDS.settingsSave;
  const settingsTest = button("Test Provider", () => testAgentSettings(agentPanel));
  settingsTest.id = PANEL_IDS.settingsTest;
  routeSelect.onchange = () => {
    if (agentPanel) {
      agentPanel.fields.route.value = normalizeRoutePreference(routeSelect.value);
      renderAgentPanel(agentPanel);
      refreshAgentStatus(agentPanel, { quiet: true });
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

  const historyRegion = panelSection(PANEL_IDS.historyRegion, "Activity");
  const candidateRegion = panelSection(PANEL_IDS.candidateRegion, "Candidate");
  const failureRegion = panelSection(PANEL_IDS.failureRegion, "Failure");
  const queueRegion = panelSection(PANEL_IDS.queueRegion, "Queue");
  const auditRegion = panelSection(PANEL_IDS.auditRegion, "Audit");
  const debugRegion = panelSection(PANEL_IDS.debugRegion, "Debug");

  // History carries the LIVE turn feed during a run, so it sits directly below
  // the prompt (the "chat box") — the user reads progress right where they typed.
  // Settings drops below it.
  body.appendChild(promptRegion.section);
  body.appendChild(historyRegion.section);
  body.appendChild(settingsRegion.section);
  body.appendChild(candidateRegion.section);
  body.appendChild(failureRegion.section);
  body.appendChild(queueRegion.section);
  body.appendChild(auditRegion.section);
  body.appendChild(debugRegion.section);

  const footer = el("div");
  Object.assign(footer.style, {
    display: "flex",
    gap: "8px",
    justifyContent: "flex-end",
    flexWrap: "wrap",
    padding: "12px 14px",
    borderTop: "1px solid #282a32",
    background: "#14161b",
  });

  const submitBtn = button("Submit", () => submitAgentEdit(agentPanel));
  submitBtn.id = PANEL_IDS.submit;
  const applyBtn = button("Apply Candidate", () => applyAgentCandidate(agentPanel));
  applyBtn.id = PANEL_IDS.apply;
  const rejectBtn = button("Reject Candidate", () => rejectAgentCandidate(agentPanel));
  rejectBtn.id = PANEL_IDS.reject;
  const undoBtn = button("Undo Last Apply", () => undoLastApply(agentPanel));
  undoBtn.id = PANEL_IDS.undo;
  const closeBtn = button("Close", () => closeAgentPanel(agentPanel));
  closeBtn.id = PANEL_IDS.close;
  footer.appendChild(submitBtn);
  footer.appendChild(applyBtn);
  footer.appendChild(rejectBtn);
  footer.appendChild(undoBtn);
  footer.appendChild(closeBtn);

  // Preview is ALWAYS-ON: no toggle. The overlay draws automatically whenever a
  // candidate is pending (AWAITING_REVIEW). (Previously a "Preview changes" checkbox.)

  shell.appendChild(header);
  shell.appendChild(metaRow);
  shell.appendChild(body);
  shell.appendChild(footer);
  root.appendChild(shell);
  document.body.appendChild(root);

  return {
    root,
    shell,
    metaRow,
    status,
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
    },
    sections: {
      history: historyRegion.body,
      candidate: candidateRegion.body,
      failure: failureRegion.body,
      queue: queueRegion.body,
      audit: auditRegion.body,
      debug: debugRegion.body,
    },
    state: {
      phase: PANEL_STATE.IDLE,
      sessionId: null,
      turnId: null,
      baselineTurnId: null,
      baselineGraphHash: null,
      baselineGraphHashKind: null,
      baselineGraphHashVersion: null,
      baselineSource: "none",
      baselineRebaselineId: null,
      baselineGraphSourcePath: null,
      candidateGraph: null,
      candidateGraphHash: null,
      candidateReport: null,
      serverSubmitGraphHash: null,
      message: null,
      failure: null,
      applyAllowed: false,
      applyEligibility: null,
      queueAllowed: false,
      canvasApplyAllowed: false,
      auditRef: null,
      debugPayload: null,
      history: [],
      turns: [],
      undoStack: [],
      inFlightSubmit: null,
      inFlightApply: null,
      inFlightRebaseline: null,
      rebaselinePending: null,
      rebaselineRecovery: null,
      lastSubmit: null,
      settingsMessage: null,
      statusSnapshot: null,
      lastAppliedChanges: null,
      queueGuard: getQueueGuardStateForPanel(),
      previewEnabled: false,
      expandedTurnKeys: {},
    },
  };
}

export function ensureAgentPanel() {
  if (!agentPanel) {
    agentPanel = createAgentPanel();
  }
  return agentPanel;
}

function openAgentPanel() {
  const panel = ensureAgentPanel();
  panel.root.dataset.open = "1";
  panel.root.style.pointerEvents = "auto";
  panel.root.style.transform = "translateX(0)";
  panel.state.queueGuard = getQueueGuardStateForPanel();
  renderAgentPanel(panel);
  refreshAgentStatus(panel, { quiet: true });
  return panel;
}

function closeAgentPanel(panel) {
  panel.root.dataset.open = "0";
  panel.root.style.pointerEvents = "none";
  panel.root.style.transform = "translateX(432px)";
}

function option(value, label) {
  const node = document.createElement("option");
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
  panel.state.turns.unshift(entry);
  panel.state.turns = sortPanelTurns(panel.state.turns);
  return entry;
}

// ── Typed response adapter (M2) ──────────────────────────────────────────────
// Prefers typed envelope fields (contract_version, outcome, candidate, eligibility)
// and falls back to top-level compatibility fields.  Does NOT change broader
// M4 UI behavior — this is a narrow mapping shim that will be removed when
// compatibility fields are deprecated during M4 UI migration planning.
function adaptTypedResponse(result) {
  if (!result || typeof result !== "object") {
    return result;
  }

  // candidate.graph → top-level graph (typed envelope candidate payload)
  if (
    result.candidate
    && typeof result.candidate === "object"
    && result.candidate.graph
    && typeof result.candidate.graph === "object"
  ) {
    if (!result.graph || typeof result.graph !== "object") {
      result.graph = result.candidate.graph;
    }
  }

  // eligibility (canonical) → apply_eligibility compatibility mirror
  if (
    result.eligibility
    && typeof result.eligibility === "object"
    && !result.apply_eligibility
  ) {
    result.apply_eligibility = result.eligibility;
  }

  // outcome.{kind,question} → clarify compatibility fields
  if (result.outcome && typeof result.outcome === "object") {
    if (
      (result.outcome.kind === "clarify" || result.outcome.kind === "edit+clarify")
      && result.clarification_required === undefined
    ) {
      result.clarification_required = true;
    }
    if (
      typeof result.outcome.question === "string"
      && result.outcome.question
      && !result.clarification_message
    ) {
      result.clarification_message = result.outcome.question;
    }
  }

  return result;
}

function normalizeBatchTurn(payload, { source = "response", sessionId = null, status = null } = {}) {
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
  const normalizedStatus =
    status
    || (typeof payload.status === "string" && payload.status)
    || (payload.clarification_required ? "clarify" : "in_progress");
  return {
    entry_type: "batch",
    turn_key: batchTurnKey(resolvedSessionId, turnNumber),
    session_id: resolvedSessionId,
    turn_id: typeof payload.turn_id === "string" && payload.turn_id ? payload.turn_id : null,
    turn_number: turnNumber,
    status: normalizedStatus,
    message: typeof payload.message === "string" ? payload.message : null,
    timestamp: typeof payload.timestamp === "string" ? payload.timestamp : null,
    clarification_required: Boolean(payload.clarification_required),
    clarification_message:
      typeof payload.clarification_message === "string" ? payload.clarification_message : null,
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
  for (let index = 0; index < result.batch_turns.length; index += 1) {
    const turn = result.batch_turns[index];
    let status = null;
    if (turn?.clarification_required) {
      status = "clarify";
    } else if (index === finalIndex && typeof result?.done_summary === "string" && result.done_summary) {
      status = "done";
    } else {
      status = "in_progress";
    }
    upsertBatchTurn(panel, turn, {
      source: "response",
      sessionId: responseSessionId,
      status,
    });
  }
  restoreExpandedTurnKeys(panel, previousExpanded);
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
  const panel = agentPanel;
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
  renderAgentPanel(panel);
}

function ensureAgentTurnListener() {
  if (agentTurnEventListenerRegistered || typeof api?.addEventListener !== "function") {
    return;
  }
  agentTurnEventListener = handleAgentTurnEvent;
  // Event name MUST match the backend emit string in agent_edit.py (_ws_send).
  api.addEventListener("vibecomfy.agent_edit.turn", agentTurnEventListener);
  agentTurnEventListenerRegistered = true;
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
  const shortMsg = _truncateMessage(entry.message || entry.done_summary, 80);
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

function renderHistory(panel) {
  _injectProgressPulseStyle();
  const body = panel.sections.history;
  clearNode(body);
  if (!panel.state.turns.length && !panel.state.history.length) {
    body.appendChild(muted("No turn history yet. Open the panel once and submit a prompt to seed durable state."));
    return;
  }

  for (let index = 0; index < panel.state.turns.length; index += 1) {
    const entry = panel.state.turns[index];
    if (entry && entry.entry_type === "batch") {
      _renderBatchTurnRow(body, panel, entry, index);
    } else {
      _renderDurableTurnRow(body, panel, entry, index);
    }
  }

  // Also render legacy history entries that don't have turn counterparts
  for (const hEntry of panel.state.history) {
    const hasTurn = panel.state.turns.some(
      (t) => t.timestamp === hEntry.at,
    );
    if (hasTurn) {
      continue;
    }
    const line = el("div");
    line.style.borderLeft = "2px solid #3d8bfd";
    line.style.paddingLeft = "8px";
    appendTextLine(line, `${hEntry.kind} \u2014 ${hEntry.message}`, "#edf2f7");
    appendTextLine(line, hEntry.at, "#8d93a1");
    body.appendChild(line);
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

function invalidateCandidateState(panel, { repaint = true } = {}) {
  if (!panel) {
    return;
  }
  // Clear candidate review fields
  panel.state.candidateGraph = null;
  panel.state.candidateGraphHash = null;
  panel.state.candidateReport = null;
  panel.state.serverSubmitGraphHash = null;
  panel.state.applyEligibility = null;
  // Clear preview diff caches (same as clearCandidatePreviewState)
  delete panel.state._previewDiff;
  delete panel.state._previewDiffGraphHash;
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
    const panel = agentPanel;
    const candidateGraphHash = panel?.state?.candidateGraphHash;
    if (
      candidateGraphHash
      && panel.state._previewDiffGraphHash === candidateGraphHash
      && panel.state._previewDiff
      && Array.isArray(panel.state._previewDiff.added_links)
      && Array.isArray(panel.state._previewDiff.removed_links)
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
      // link may be an array [origin_id, origin_slot, target_id, target_slot, …]
      // or an object { origin_id, origin_slot, target_id, target_slot, … }
      const originId = Array.isArray(link) ? link[0] : link?.origin_id;
      const originSlot = Array.isArray(link) ? link[1] : link?.origin_slot;
      const targetId = Array.isArray(link) ? link[2] : link?.target_id;
      const targetSlot = Array.isArray(link) ? link[3] : link?.target_slot;

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

    const diff = {
      edited,
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
  const panel = agentPanel;
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
    Array.isArray(panel.state._previewDiff.removed_links)
  ) {
    return panel.state._previewDiff;
  }
  return computePreviewDiff(candidateGraph, candidateReport);
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
    var addedColor = VC_COLORS.added;
    var addedFill = hexToRgba(VC_COLORS.added, 0.18);
    var addedTextColor = hexToRgba(VC_COLORS.added, 0.92);
    var removedColor = VC_COLORS.removed;
    var lineWidth = 3;
    var TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
    var SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
    var WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;

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

    // ── Truncation helper (Unicode ellipsis, SD3) ────────────────────────
    var _trunc = function (text, maxChars) {
      text = String(text || "").trim();
      if (!text) return "";
      return text.length > maxChars ? text.slice(0, maxChars - 1) + "\u2026" : text;
    };

    // ── Edited nodes (amber outline) ────────────────────────────────────
    // LiteGraph: node.pos[1] is the top of the node BODY; the title bar is drawn
    // ABOVE it (getBounding() top = pos[1] - NODE_TITLE_HEIGHT) and node.size is
    // the body size, excluding the title. So the full visual box is
    // [pos[0], pos[1]-TITLE_H, size[0], size[1]+TITLE_H].
    for (var _ei = 0; _ei < (diff.edited || []).length; _ei += 1) {
      var eitem = diff.edited[_ei];
      var enode = lookupLiveNodeByUid(eitem.uid);
      if (!enode || !enode.pos) {
        continue;
      }
      var ex = enode.pos[0];
      var ey = enode.pos[1];
      var ew = Array.isArray(enode.size) ? enode.size[0] : 200;
      var collapsed = !!(enode.flags && enode.flags.collapsed);
      var eh = collapsed ? 0 : (Array.isArray(enode.size) ? enode.size[1] : 100);
      ctx.setLineDash([]);
      ctx.strokeStyle = editedColor;
      ctx.lineWidth = lineWidth;
      // Box the WHOLE node: title bar (above pos[1]) + body.
      ctx.strokeRect(ex - 2, ey - TITLE_H - 2, ew + 4, eh + TITLE_H + 4);
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
      ctx.fillStyle = hexToRgba(VC_COLORS.edited, 0.22);
      for (var _wi = 0; _wi < (eitem.changedWidgetIndices || []).length; _wi += 1) {
        var widx = eitem.changedWidgetIndices[_wi];
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
        ctx.fillRect(ex, rowTop, ew, Math.max(rowH - 2, 4));
      }
    }

    // ── Removed nodes (red outline + "− will be removed" badge) ─────────
    var removedItems = (diff.removed || []).concat(diff.removed_named || []);
    for (var _ri = 0; _ri < removedItems.length; _ri += 1) {
      var ritem = removedItems[_ri];
      var rnode = lookupLiveNodeByUid(ritem.uid);
      if (!rnode || !rnode.pos) {
        continue;
      }
      var rx = rnode.pos[0];
      var ry = rnode.pos[1];
      var rw = Array.isArray(rnode.size) ? rnode.size[0] : 200;
      var rh = Array.isArray(rnode.size) ? rnode.size[1] : 100;
      ctx.setLineDash([]);
      ctx.strokeStyle = removedColor;
      ctx.lineWidth = lineWidth;
      ctx.strokeRect(rx - 2, ry - 2, rw + 4, rh + 4);
      _drawBadge(rx + rw - 2 - 140, ry + rh - 2, "\u2212 will be removed", removedColor);
    }

    // ── Added nodes (translucent green ghost + "+ new" badge; candidate pos) ─
    var candidateGraph = (diff && diff._candidateGraph) || (agentPanel && agentPanel.state && agentPanel.state.candidateGraph);
    if (candidateGraph && diff.added && diff.added.length > 0) {
      var addedByUid = new Map();
      for (var _ai = 0; _ai < diff.added.length; _ai += 1) {
        addedByUid.set(diff.added[_ai].uid, diff.added[_ai]);
      }
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
        if (!pos || !Array.isArray(pos) || pos.length < 2) {
          continue;
        }
        var cx = pos[0];
        var cy = pos[1];

        // ── Dimension resolution: use cn.size only when plausible ────────
        var sizeValid = false;
        var cw, ch;
        if (Array.isArray(cn.size)) {
          var rawW = cn.size[0];
          var rawH = cn.size[1];
          if (typeof rawW === "number" && typeof rawH === "number" && rawW > 40 && rawH > 20) {
            cw = rawW;
            ch = rawH;
            sizeValid = true;
          }
        }
        if (!sizeValid) {
          var dims = _computeGhostDimensions(cn, ctx);
          cw = dims.w;
          ch = dims.h;
        }

        // ── Ghost fill + dashed border ───────────────────────────────────
        ctx.fillStyle = addedFill;
        ctx.fillRect(cx - 2, cy - 2, cw + 4, ch + 4);
        ctx.strokeStyle = addedColor;
        ctx.lineWidth = lineWidth;
        ctx.setLineDash([6, 3]);
        ctx.strokeRect(cx - 2, cy - 2, cw + 4, ch + 4);
        ctx.setLineDash([]);

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
      // Build candidate-by-uid map once for ghost endpoint lookups.
      var _candByUid = new Map();
      var _candNodes = Array.isArray(candidateGraph.nodes) ? candidateGraph.nodes : [];
      for (var _ci = 0; _ci < _candNodes.length; _ci += 1) {
        var _candNode = _candNodes[_ci];
        var _candUid = _candNode && _candNode.properties ? _candNode.properties.vibecomfy_uid : undefined;
        if (_candUid) _candByUid.set(_candUid, _candNode);
      }

      var _unresWarn = 0;
      var _MAX_UNRES_WARN = 5;

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
        if (node && node.pos && Array.isArray(node.pos) && node.pos.length >= 2) {
          var _nx = node.pos[0];
          var _ny = node.pos[1];
          var _nw = Array.isArray(node.size) ? node.size[0] : 200;
          if (isInput) return [_nx, _ny + TITLE_H + slotIdx * SLOT_H + SLOT_H / 2];
          return [_nx + _nw, _ny + TITLE_H + slotIdx * SLOT_H + SLOT_H / 2];
        }
        // Ghost geometry (candidate-only node)
        if (ghostPos && Array.isArray(ghostPos) && ghostPos.length >= 2) {
          var _gx = ghostPos[0];
          var _gy = ghostPos[1];
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
        if (Array.isArray(cn.size)) {
          var _rw = cn.size[0], _rh = cn.size[1];
          if (typeof _rw === 'number' && typeof _rh === 'number' && _rw > 40 && _rh > 20) {
            return { w: _rw, h: _rh };
          }
        }
        return _computeGhostDimensions(cn, ctx);
      }

      // ── Removed wires: dashed red beziers (drawn first) ──────────────
      var _remLinks = diff.removed_links || [];
      for (var _rli = 0; _rli < _remLinks.length; _rli += 1) {
        var _p = _parseKey(_remLinks[_rli]);
        if (!_p) continue;

        var _fNode = lookupLiveNodeByUid(_p.fromUid);
        var _tNode = lookupLiveNodeByUid(_p.toUid);

        var _fSlot = _slotIdx(_fNode, _p.fromPort, 'outputs');
        var _tSlot = _slotIdx(_tNode, _p.toPort, 'inputs');

        if (_fSlot < 0 || _tSlot < 0) {
          if (_unresWarn < _MAX_UNRES_WARN) { _unresWarn += 1; console.warn('[vibecomfy] drawPreviewOverlay — unresolvable removed-wire endpoint:', _remLinks[_rli]); }
          continue;
        }

        var _fp = _connPos(_fNode, false, _fSlot, null, 0);
        var _tp = _connPos(_tNode, true, _tSlot, null, 0);
        if (_fp && _tp) {
          _strokeWire(_fp[0], _fp[1], _tp[0], _tp[1], removedColor, true);
        } else if (_unresWarn < _MAX_UNRES_WARN) {
          _unresWarn += 1; console.warn('[vibecomfy] drawPreviewOverlay — could not resolve removed-wire endpoint positions:', _remLinks[_rli]);
        }
      }

      // ── Added wires: solid green beziers (drawn second) ───────────────
      var _addLinks = diff.added_links || [];
      for (var _ali = 0; _ali < _addLinks.length; _ali += 1) {
        var _p2 = _parseKey(_addLinks[_ali]);
        if (!_p2) continue;

        var _fNode2 = lookupLiveNodeByUid(_p2.fromUid);
        var _tNode2 = lookupLiveNodeByUid(_p2.toUid);

        // Ghost fallback for endpoints not in the live graph
        var _fGhostPos = null, _fGhostW = 0;
        if (!_fNode2) {
          var _fc = _candByUid.get(_p2.fromUid);
          if (_fc && _fc.pos && Array.isArray(_fc.pos) && _fc.pos.length >= 2) {
            _fGhostPos = _fc.pos;
            _fGhostW = _ghostDims(_fc).w;
          }
        }
        var _tGhostPos = null, _tGhostW = 0;
        if (!_tNode2) {
          var _tc = _candByUid.get(_p2.toUid);
          if (_tc && _tc.pos && Array.isArray(_tc.pos) && _tc.pos.length >= 2) {
            _tGhostPos = _tc.pos;
            _tGhostW = _ghostDims(_tc).w;
          }
        }

        // Resolve port → slot on whichever node we have (live or candidate)
        var _fNodeR = _fNode2 || _candByUid.get(_p2.fromUid) || null;
        var _tNodeR = _tNode2 || _candByUid.get(_p2.toUid) || null;

        var _fSlot2 = _slotIdx(_fNodeR, _p2.fromPort, 'outputs');
        var _tSlot2 = _slotIdx(_tNodeR, _p2.toPort, 'inputs');

        if (_fSlot2 < 0 || _tSlot2 < 0) {
          if (_unresWarn < _MAX_UNRES_WARN) { _unresWarn += 1; console.warn('[vibecomfy] drawPreviewOverlay — unresolvable added-wire endpoint:', _addLinks[_ali]); }
          continue;
        }

        var _fp2 = _connPos(_fNode2, false, _fSlot2, _fGhostPos, _fGhostW);
        var _tp2 = _connPos(_tNode2, true, _tSlot2, _tGhostPos, _tGhostW);
        if (_fp2 && _tp2) {
          _strokeWire(_fp2[0], _fp2[1], _tp2[0], _tp2[1], addedColor, false);
        } else if (_unresWarn < _MAX_UNRES_WARN) {
          _unresWarn += 1; console.warn('[vibecomfy] drawPreviewOverlay — could not resolve added-wire endpoint positions:', _addLinks[_ali]);
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
    panel.state.lastAppliedChanges = null;
    return;
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
  panel.state.lastAppliedChanges = feedback;
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
  if (agentPanel) {
    agentPanel.state.queueGuard = getQueueGuardStateForPanel();
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
  const candidate = {
    owner: app,
    key: "queuePrompt",
    path: "app.queuePrompt",
  };
  const original = candidate.owner?.[candidate.key];
  if (typeof original !== "function") {
    queueGuardFallbackWarning = "Native queue hook unavailable: `app.queuePrompt` was not found. Queue warnings remain panel-only.";
    warnQueueGuardFallbackOnce("missing app.queuePrompt");
    queueGuardHook = { installed: false, path: candidate.path, original: null, wrapper: null };
    return false;
  }

  const wrapper = function guardedQueuePrompt(...args) {
    const active = queueGuardContext;
    if (active?.queueAllowed === false) {
      const blockKey = queueGuardTurnKey(active);
      if (!queueGuardBlockedTurnKeys.has(blockKey)) {
        queueGuardBlockedTurnKeys.add(blockKey);
        queueGuardBlockNotice = {
          at: new Date().toISOString(),
          message: `Queue blocked for turn ${active.turnId || "unknown"} because queue_allowed=false.`,
          turnId: active.turnId || null,
          sessionId: active.sessionId || null,
        };
      }
      if (agentPanel) {
        agentPanel.state.queueGuard = getQueueGuardStateForPanel();
        renderAgentPanel(agentPanel);
      }
      toast("Queue blocked: this applied turn is canvas-reviewable only.");
      return null;
    }
    return original.apply(this, args);
  };

  try {
    candidate.owner[candidate.key] = wrapper;
    candidate.owner[candidate.key] = original;
  } catch (error) {
    queueGuardFallbackWarning = `Native queue hook could not be installed safely on \`${candidate.path}\`: ${String(error)}`;
    warnQueueGuardFallbackOnce(`unsafe ${candidate.path}`);
    queueGuardHook = { installed: false, path: candidate.path, original, wrapper: null };
    return false;
  }

  candidate.owner[candidate.key] = wrapper;
  queueGuardHook = { installed: true, path: candidate.path, original, wrapper };
  queueGuardFallbackWarning = null;
  return true;
}

function renderCandidate(panel) {
  const body = panel.sections.candidate;
  clearNode(body);
  if (!panel.state.candidateGraph) {
    // Clarify turn: the agent asked a question and produced no candidate. Show the
    // question as the headline (not "No candidate yet") and point the user at the
    // prompt box, which is open for their answer in the same session.
    if (panel.state.phase === PANEL_STATE.CLARIFY && panel.state.clarification?.message) {
      const q = el("div", "❓ The agent needs your input:");
      q.style.color = "#ffc107";
      q.style.fontWeight = "600";
      body.appendChild(q);
      const msg = el("div", panel.state.clarification.message);
      msg.style.whiteSpace = "pre-wrap";
      msg.style.color = "#edf2f7";
      msg.style.borderLeft = "2px solid #ffc107";
      msg.style.paddingLeft = "8px";
      msg.style.margin = "4px 0";
      body.appendChild(msg);
      body.appendChild(muted("Answer in the prompt box above and submit — it continues this session."));
      return;
    }
    const feedback = panel.state.lastAppliedChanges;
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
    body.appendChild(muted("No candidate yet. The legacy round-trip modal remains available through its original command."));
    return;
  }
  const stageInfo = getBackendStageInfo(panel.state.debugPayload);
  if (stageInfo) {
    appendTextLine(
      body,
      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
      "#9ed0ff",
    );
  }
  if (panel.state.message) {
    const msg = el("div", panel.state.message);
    msg.style.whiteSpace = "pre-wrap";
    msg.style.color = "#edf2f7";
    body.appendChild(msg);
  }
  const eligibility = applyEligibility(panel);
  appendTextLine(body, `canvas_apply_allowed=${String(panel.state.canvasApplyAllowed)}`, panel.state.canvasApplyAllowed ? "#4caf50" : "#ffb86c");
  appendTextLine(body, `apply_eligibility=${eligibility.reason}`, eligibility.applyable ? "#4caf50" : "#ffb86c");
  appendTextLine(body, `queue_allowed=${String(panel.state.queueAllowed)}`, panel.state.queueAllowed ? "#4caf50" : "#ffb86c");
  if (eligibility.message) {
    appendTextLine(body, eligibility.message, "#9ed0ff");
  }
  const rows = collectDiffRows(panel.state.candidateReport);
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
  const issues = collectQueueIssues(panel.state.candidateReport);
  if (issues.length) {
    for (const issue of issues) {
      appendTextLine(body, `${issue.code}: ${issue.message}`, issue.severity === "error" ? "#ffb86c" : "#9ed0ff");
      if (issue.detail && Object.keys(issue.detail).length) {
        body.appendChild(createDetails("queue blocker detail", issue.detail));
      }
    }
  }
  const artifacts = panel.state.debugPayload?.artifacts;
  if (artifacts && typeof artifacts === "object") {
    for (const [name, value] of Object.entries(artifacts)) {
      appendCodeLine(body, `${name}: ${value}`);
    }
  }
  if (panel.state.auditRef?.path) {
    appendCodeLine(body, `audit: ${panel.state.auditRef.path}`, "#9ed0ff");
  }
  body.appendChild(createDetails("raw report", panel.state.candidateReport || {}));
}

function renderFailure(panel) {
  const body = panel.sections.failure;
  clearNode(body);
  const failure = panel.state.failure;
  if (!failure) {
    body.appendChild(muted("No failure envelope."));
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
    const recoveryButton = button("Rebaseline Current Canvas", () => rebaselineCurrentCanvas(panel));
    recoveryButton.disabled = Boolean(panel.state.inFlightRebaseline);
    body.appendChild(recoveryButton);
  }
  if (failure.agent_failure_context && Object.keys(failure.agent_failure_context).length) {
    body.appendChild(createDetails("agent failure context", failure.agent_failure_context));
  }
  body.appendChild(createDetails("raw failure", failure));
}

function renderQueue(panel) {
  const body = panel.sections.queue;
  clearNode(body);
  const queueGuard = panel.state.queueGuard || getQueueGuardStateForPanel();
  const issues = collectQueueIssues(panel.state.candidateReport);
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
  if (panel.state.queueAllowed) {
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

function renderAudit(panel) {
  const body = panel.sections.audit;
  clearNode(body);
  if (panel.state.auditRef?.path) {
    appendCodeLine(body, panel.state.auditRef.path, "#edf2f7");
    if (panel.state.auditRef.sha256) {
      appendCodeLine(body, `sha256: ${panel.state.auditRef.sha256}`, "#8d93a1");
    }
  } else if (Array.isArray(panel.state.turns) && panel.state.turns.length) {
    const latest = panel.state.turns[0];
    if (latest?.audit_ref?.path) {
      appendCodeLine(body, latest.audit_ref.path, "#edf2f7");
      if (latest.audit_ref.sha256) {
        appendCodeLine(body, `sha256: ${latest.audit_ref.sha256}`, "#8d93a1");
      }
    } else {
      body.appendChild(muted("No audit artifact linked yet."));
    }
  } else {
    body.appendChild(muted("No audit artifact linked yet."));
  }
  // Download button for current audit envelope
  const dlBtn = button("Download Audit Envelope", () => downloadCurrentAudit(panel));
  dlBtn.style.fontSize = "11px";
  dlBtn.style.padding = "4px 8px";
  body.appendChild(dlBtn);
}

function renderDebug(panel) {
  const body = panel.sections.debug;
  clearNode(body);
  // Tuck the raw envelope behind a collapsed <details>. It is a developer aid;
  // left always-open it dumps the full response (incl. batch_turns) as a wall of
  // JSON that buries the Activity feed. Collapsed by default — click to expand.
  const details = el("details");
  details.open = !!panel.state.debugExpanded;
  details.ontoggle = function () {
    panel.state.debugExpanded = details.open;
  };
  const summary = el("summary", "Raw response (debug)");
  Object.assign(summary.style, {
    cursor: "pointer",
    color: "#8d93a1",
    fontSize: "11px",
    userSelect: "none",
  });
  details.appendChild(summary);
  const pre = el("pre", safeJson(panel.state.debugPayload || { state: panel.state.phase }));
  Object.assign(pre.style, {
    margin: "6px 0 0",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    color: "#b9ffcc",
    fontSize: "11px",
  });
  details.appendChild(pre);
  body.appendChild(details);
}

function renderSettings(panel) {
  const descriptor = getRouteDescriptor(panel);
  const apiKeyVisible = Boolean(descriptor.browser_api_key_allowed);
  setVisible(panel.fields.apiKey, apiKeyVisible, "");
  panel.fields.apiKey.placeholder = apiKeyVisible
    ? "DeepSeek API key"
    : "Browser API keys are not accepted for this route";
  if (!apiKeyVisible) {
    clearCredentialInput(panel);
  }

  const statusNode = document.getElementById(PANEL_IDS.settingsStatus);
  const guidanceNode = document.getElementById(PANEL_IDS.settingsGuidance);
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

export function renderAgentPanel(panel) {
  renderMeta(panel);

  const phase = panel.state.phase;
  panel.status.textContent = phase === PANEL_STATE.CLARIFY ? "NEEDS YOUR INPUT" : phase;
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

  renderHistory(panel);
  renderSettings(panel);
  renderCandidate(panel);
  renderFailure(panel);
  renderQueue(panel);
  renderAudit(panel);
  renderDebug(panel);

  const submitting = phase === PANEL_STATE.SUBMITTING;
  const reviewing = phase === PANEL_STATE.AWAITING_REVIEW;
  const applying = phase === PANEL_STATE.APPLYING;
  const canSubmit = phase === PANEL_STATE.IDLE || phase === PANEL_STATE.ERROR || phase === PANEL_STATE.CLARIFY;
  const eligibility = applyEligibility(panel);
  const rebaselineReason = panel.state.rebaselinePending?.reason || null;
  const rebaselinePending = Boolean(panel.state.rebaselinePending || panel.state.inFlightRebaseline);
  const undoPending = rebaselineReason === "undo";

  panel.buttons.submit.disabled = submitting || rebaselinePending;
  panel.buttons.submit.textContent = submitting ? "Submitting..." : "Submit";
  panel.buttons.apply.disabled = applying || !eligibility.applyable;
  panel.buttons.reject.disabled = !panel.state.candidateGraph || submitting || applying;
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
  panel.buttons.settingsSave.disabled = submitting || applying;
  panel.buttons.settingsTest.disabled = submitting || applying;

  // Always-on preview (no toggle): previewEnabled simply tracks whether there is
  // a pending candidate to preview.
  panel.state.previewEnabled = !!(reviewing && panel.state.candidateGraph);

  setButtonEmphasis(panel.buttons.submit, canSubmit || submitting, "primary");
  setButtonEmphasis(panel.buttons.apply, reviewing || applying, "primary");
  setButtonEmphasis(panel.buttons.reject, reviewing || applying, "danger");
  setButtonEmphasis(panel.buttons.undo, panel.state.undoStack.length > 0, "neutral");
  setButtonEmphasis(panel.buttons.close, true, "neutral");
  setButtonEmphasis(panel.buttons.settingsSave, true, "neutral");
  setButtonEmphasis(panel.buttons.settingsTest, true, "neutral");
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
  renderAgentPanel(panel);
  await refreshAgentStatus(panel);
}

async function submitAgentEdit(panel) {
  if (panel?.state?.rebaselinePending || panel?.state?.inFlightRebaseline) {
    renderAgentPanel(panel);
    return panel.state.inFlightRebaseline || undefined;
  }
  if (panel.state.inFlightSubmit) {
    return panel.state.inFlightSubmit;
  }
  panel.state.inFlightSubmit = (async () => {
    // Re-resolve the prompt element from the live DOM at submit time: a durable
    // panel re-render can replace the textarea, leaving panel.fields.prompt as a
    // stale, detached reference whose .value reads empty — a false "MissingTask".
    const promptEl = document.getElementById(PANEL_IDS.prompt) || panel.fields.prompt;
    if (promptEl && promptEl !== panel.fields.prompt) {
      panel.fields.prompt = promptEl;
    }
    const task = (promptEl && typeof promptEl.value === "string" ? promptEl.value : "").trim();
    if (!task) {
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = agentPanelFailure("MissingTask", "Enter an edit instruction before submitting.", {
        retryable: true,
        next_action: "Describe the workflow change in the prompt region, then submit again.",
      });
      panel.state.debugPayload = panel.state.failure;
      renderAgentPanel(panel);
      return;
    }

    let snapshot;
    try {
      snapshot = await buildSubmitSnapshot(panel);
    } catch (e) {
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = agentPanelFailure("SerializeError", String(e), {
        retryable: true,
        next_action: "Make sure the canvas can serialize, then retry.",
      });
      panel.state.debugPayload = panel.state.failure;
      renderAgentPanel(panel);
      return;
    }

    panel.state.phase = PANEL_STATE.SUBMITTING;
    invalidateCandidateState(panel);
    panel.state.failure = null;
    panel.state.lastAppliedChanges = null;
    clearChangedNodeFeedbackVisuals();
    panel.state.lastSubmit = {
      task,
      route: snapshot.route,
      model: snapshot.model,
      client_graph_hash: snapshot.graphHash,
      client_structural_graph_hash: snapshot.structuralHash,
      client_live_canvas_token: snapshot.liveCanvasToken,
      idempotency_key: snapshot.idempotencyKey,
    };
    pushHistory(panel, "pending", `Submitting: ${task.slice(0, 80)}${task.length > 80 ? "..." : ""}`);
    pushTurnStatus(panel, "pending", {
      task,
      message: `Submitting: ${task.slice(0, 80)}${task.length > 80 ? "..." : ""}`,
    });
    panel.state.debugPayload = {
      task,
      route: snapshot.route,
      model: snapshot.model,
      client_graph_hash: snapshot.graphHash,
      client_structural_graph_hash: snapshot.structuralHash,
      client_live_canvas_token: snapshot.liveCanvasToken,
      idempotency_key: snapshot.idempotencyKey,
    };
    renderAgentPanel(panel);

    let result;
    try {
      const body = {
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
      const res = await fetch("/vibecomfy/agent-edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      result = await res.json();
      // Prefer typed envelope fields; fall back to compatibility fields.
      result = adaptTypedResponse(result);
      if (!res.ok || result?.ok === false || result?.error) {
        throw result || { kind: "RequestError", message: res.statusText };
      }
      if (!result || typeof result !== "object" || !result.graph || typeof result.graph !== "object") {
        throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
          stage: result?.stage || "agent-edit",
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry the request or inspect the raw response in the debug panel.",
          raw_response: result,
        });
      }
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("NetworkError", String(e), {
            retryable: true,
            next_action: "Retry once the local ComfyUI backend responds again.",
          });
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = failure;
      panel.state.turnId = failure.turn_id || panel.state.turnId;
      panel.state.sessionId = failure.session_id || panel.state.sessionId;
      syncBaselineFromResponse(panel, failure);
      panel.state.auditRef = failure.audit_ref || null;
      panel.state.queueGuard = getQueueGuardStateForPanel();
      panel.state.debugPayload = {
        ...failure,
        last_submit: panel.state.lastSubmit,
      };
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
      renderAgentPanel(panel);
      return;
    } finally {
      panel.state.inFlightSubmit = null;
    }

    // Clarify terminal: the agent ended the turn with `clarify("...")` instead of
    // landing edits. The backend honestly reports clarification_required + a
    // byte-identical graph (graph_unchanged) + canvas_apply_allowed:false. Branch
    // out BEFORE the candidate path so we never store result.graph as a candidate
    // or enter AWAITING_REVIEW — doing so would render an "Apply Candidate" button
    // over an unchanged graph that does nothing (the original no-op bug). Instead
    // surface the question and leave the prompt open so the user can answer in the
    // same session (session_id is preserved for the follow-up turn).
    if (result.clarification_required === true) {
      const clarifyMessage =
        (typeof result.clarification_message === "string" && result.clarification_message.trim())
          ? result.clarification_message.trim()
          : (typeof result.message === "string" && result.message.trim())
            ? result.message.trim()
            : "The agent needs clarification before it can edit the graph.";
      panel.state.phase = PANEL_STATE.CLARIFY;
      panel.state.sessionId = result.session_id || panel.state.sessionId;
      panel.state.turnId = result.turn_id || null;
      syncBaselineFromResponse(panel, result);
      invalidateCandidateState(panel);
      panel.state.clarification = {
        message: clarifyMessage,
        turn_id: result.turn_id || null,
        session_id: result.session_id || null,
      };
      panel.state.message = clarifyMessage;
      panel.state.failure = null;
      panel.state.canvasApplyAllowed = false;
      panel.state.applyAllowed = false;
      panel.state.applyEligibility = null;
      panel.state.queueAllowed = false;
      panel.state.auditRef = result.audit_ref || null;
      panel.state.queueGuard = getQueueGuardStateForPanel();
      reconcileResponseBatchTurns(panel, result);
      panel.state.debugPayload = {
        ...result,
        last_submit: panel.state.lastSubmit,
      };
      pushHistory(panel, "clarify", clarifyMessage);
      pushTurnStatus(panel, "clarify", {
        session_id: result.session_id,
        turn_id: result.turn_id,
        baseline_turn_id: result.baseline_turn_id,
        task,
        message: clarifyMessage,
        clarification_required: true,
        clarification_message: clarifyMessage,
        audit_ref: result.audit_ref,
        raw_payload: result,
      });
      renderAgentPanel(panel);
      return;
    }

    let arrivalSnapshot;
    try {
      arrivalSnapshot = await buildCanvasSnapshot();
    } catch (e) {
      panel.state.phase = PANEL_STATE.ERROR;
      syncBaselineFromResponse(panel, result);
      panel.state.failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas after the candidate arrived: ${String(e)}`, {
        retryable: true,
        graph_unchanged: true,
        next_action: "Make sure the current canvas can serialize, then submit again.",
      });
      panel.state.debugPayload = {
        ...panel.state.failure,
        last_submit: panel.state.lastSubmit,
        response: result,
      };
      renderAgentPanel(panel);
      return;
    }

    const expectedArrivalHash = panel.state.lastSubmit?.client_graph_hash;
    const expectedArrivalStructuralHash = panel.state.lastSubmit?.client_structural_graph_hash;
    if (
      typeof expectedArrivalStructuralHash === "string"
      && expectedArrivalStructuralHash
      && arrivalSnapshot.structuralHash !== expectedArrivalStructuralHash
    ) {
      const failure = agentPanelFailure("StaleResponseArrival", "The canvas changed before this candidate arrived. Review is blocked.", {
        retryable: true,
        graph_unchanged: true,
        next_action: "Submit a new edit from the current canvas.",
        client_graph_hash: arrivalSnapshot.graphHash,
        client_structural_graph_hash: arrivalSnapshot.structuralHash,
        expected_graph_hash: expectedArrivalHash,
        expected_structural_graph_hash: expectedArrivalStructuralHash,
        client_live_canvas_token: arrivalSnapshot.liveCanvasToken,
        session_id: result.session_id,
        turn_id: result.turn_id,
        baseline_turn_id: result.baseline_turn_id,
        audit_ref: result.audit_ref || null,
        raw_response: result,
      });
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = failure;
      panel.state.sessionId = result.session_id || panel.state.sessionId;
      panel.state.turnId = result.turn_id || null;
      syncBaselineFromResponse(panel, result);
      panel.state.auditRef = result.audit_ref || null;
      panel.state.queueGuard = getQueueGuardStateForPanel();
      panel.state.debugPayload = {
        ...failure,
        last_submit: panel.state.lastSubmit,
      };
      pushHistory(panel, "failure", failure.kind || "StaleResponseArrival");
      pushTurnStatus(panel, "failed", {
        session_id: result.session_id,
        turn_id: result.turn_id,
        baseline_turn_id: result.baseline_turn_id,
        task,
        failure_kind: failure.kind,
        failure_stage: failure.stage,
        message: failure.user_facing_message || failure.message,
        audit_ref: result.audit_ref,
        raw_payload: failure,
      });
      renderAgentPanel(panel);
      return;
    }

    const candidateGraphHash = typeof result.candidate_graph_hash === "string"
      ? result.candidate_graph_hash
      : await sha256HexUtf8(canonicalJsonString(result.graph));
    panel.state.phase = PANEL_STATE.AWAITING_REVIEW;
    panel.state.sessionId = result.session_id || panel.state.sessionId;
    panel.state.turnId = result.turn_id || null;
    syncBaselineFromResponse(panel, result);
    invalidateCandidateState(panel);
    panel.state.candidateGraph = result.graph || null;
    panel.state.candidateGraphHash = candidateGraphHash;
    panel.state.candidateReport = result.report || null;
    panel.state.serverSubmitGraphHash = typeof result.submit_graph_hash === "string" ? result.submit_graph_hash : null;
    panel.state.message = result.message || null;
    panel.state.failure = null;
    panel.state.applyEligibility = normalizeApplyEligibility(result.apply_eligibility);
    panel.state.applyAllowed = result.apply_allowed !== false && result.canvas_apply_allowed !== false;
    panel.state.canvasApplyAllowed = Boolean(result.canvas_apply_allowed);
    panel.state.queueAllowed = Boolean(result.queue_allowed);
    panel.state.auditRef = result.audit_ref || null;
    panel.state.queueGuard = getQueueGuardStateForPanel();
    reconcileResponseBatchTurns(panel, result);
    panel.state.debugPayload = {
      ...result,
      last_submit: panel.state.lastSubmit,
    };
    pushHistory(panel, "candidate", result.turn_id ? `turn ${result.turn_id}` : "candidate");
    pushTurnStatus(panel, "candidate", {
      session_id: result.session_id,
      turn_id: result.turn_id,
      baseline_turn_id: result.baseline_turn_id,
      task,
      message: result.message || (result.turn_id ? `turn ${result.turn_id}` : "candidate"),
      audit_ref: result.audit_ref,
      raw_payload: result,
    });
    renderAgentPanel(panel);

    if (panel.state.previewEnabled) {
      if (app?.canvas?.setDirty) {
        app.canvas.setDirty(true, true);
      }
      if (app?.canvas?.draw) {
        app.canvas.draw(true, true);
      }
    }
  })();

  return panel.state.inFlightSubmit;
}

async function applyAgentCandidate(panel) {
  if (!panel.state.candidateGraph) {
    return;
  }
  if (!panel.state.sessionId || !panel.state.turnId) {
    panel.state.phase = PANEL_STATE.ERROR;
    panel.state.failure = agentPanelFailure("MissingRequiredField", "Cannot apply a candidate without session_id and turn_id.", {
      retryable: false,
      graph_unchanged: true,
      next_action: "Submit the edit again to get a complete candidate envelope.",
    });
    panel.state.debugPayload = panel.state.failure;
    renderAgentPanel(panel);
    return;
  }
  if (panel.state.inFlightApply) {
    return panel.state.inFlightApply;
  }

  panel.state.inFlightApply = (async () => {
    let beforeApply;
    try {
      beforeApply = await buildCanvasSnapshot();
    } catch (e) {
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas before Apply: ${String(e)}`, {
        retryable: true,
        graph_unchanged: true,
      });
      panel.state.debugPayload = panel.state.failure;
      renderAgentPanel(panel);
      return;
    }

    const expectedHash = panel.state.lastSubmit?.client_graph_hash;
    const eligibility = applyEligibility(panel, beforeApply);
    if (!eligibility.applyable) {
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = agentPanelFailure(
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
      panel.state.debugPayload = panel.state.failure;
      clearCandidatePreviewState(panel);
      renderAgentPanel(panel);
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

    panel.state.phase = PANEL_STATE.APPLYING;
    panel.state.failure = null;
    panel.state.debugPayload = {
      applying_turn_id: panel.state.turnId,
      accept_request: acceptBody,
    };
    renderAgentPanel(panel);

    let accepted;
    try {
      const res = await fetch("/vibecomfy/agent-edit/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(acceptBody),
      });
      accepted = await res.json();
      if (!res.ok || accepted?.ok === false || accepted?.error) {
        throw accepted || { kind: "AcceptError", message: res.statusText };
      }
      if (!accepted || typeof accepted !== "object" || accepted.action !== "accept" || !accepted.session_id || !accepted.turn_id) {
        throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete accept envelope.", {
          stage: accepted?.stage || "accept",
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry Apply or inspect the raw response in the debug panel.",
          raw_response: accepted,
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
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = failure;
      syncBaselineFromResponse(panel, failure);
      panel.state.auditRef = failure.audit_ref || panel.state.auditRef;
      panel.state.debugPayload = {
        ...failure,
        accept_request: acceptBody,
      };
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
      renderAgentPanel(panel);
      return;
    }

    const currentBeforeLoad = await buildCanvasSnapshot();
    if (currentBeforeLoad.liveCanvasToken !== beforeApply.liveCanvasToken) {
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = agentPanelFailure("StaleStateMismatch", "The canvas changed while Apply was waiting for backend acceptance. Candidate loading is blocked.", {
        retryable: true,
        graph_unchanged: true,
        next_action: "Submit a new edit from the current canvas.",
        client_graph_hash: currentBeforeLoad.graphHash,
        client_structural_graph_hash: currentBeforeLoad.structuralHash,
        expected_graph_hash: stateCheckGraphHash,
        client_live_canvas_token: currentBeforeLoad.liveCanvasToken,
        expected_live_canvas_token: beforeApply.liveCanvasToken,
        accept_response: accepted,
      });
      panel.state.debugPayload = panel.state.failure;
      clearCandidatePreviewState(panel);
      renderAgentPanel(panel);
      return;
    }

    panel.state.undoStack.push({
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
      graph: currentBeforeLoad.graph,
      client_graph_hash: currentBeforeLoad.graphHash,
      accepted_baseline_graph_hash: accepted.baseline_graph_hash || panel.state.baselineGraphHash || null,
      captured_at: new Date().toISOString(),
    });
    panel.state.undoStack = panel.state.undoStack.slice(-16);

    try {
      applyGraphInPlaceWithIntentDecoration(panel.state.candidateGraph);
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("CanvasApplyError", String(e), {
            retryable: true,
            graph_unchanged: false,
            next_action: "Retry Apply or inspect the raw response in the debug panel.",
            accept_response: accepted,
          });
      panel.state.phase = PANEL_STATE.ERROR;
      panel.state.failure = failure;
      panel.state.auditRef = failure.audit_ref || panel.state.auditRef;
      panel.state.debugPayload = {
        ...failure,
        accepted,
        undo_stack_depth: panel.state.undoStack.length,
      };
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
      renderAgentPanel(panel);
      return;
    }
    announceChangedNodes(panel, extractChangedNodeFeedback(panel.state.candidateReport));
    pushHistory(panel, "applied", panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate");
    pushTurnStatus(panel, "applied", {
      turn_id: panel.state.turnId,
      baseline_turn_id: accepted.baseline_turn_id || panel.state.turnId,
      message: panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate",
      audit_ref: accepted.audit_ref || panel.state.auditRef,
      raw_payload: accepted,
    });
    panel.state.phase = PANEL_STATE.IDLE;
    syncBaselineFromResponse(panel, accepted);
    panel.state.baselineTurnId = panel.state.baselineTurnId || panel.state.turnId || null;
    panel.state.auditRef = accepted.audit_ref || panel.state.auditRef;
    // applyGraphInPlaceWithIntentDecoration already repainted the canvas above and
    // the panel is now IDLE (overlay won't draw), so skip the redundant repaint.
    invalidateCandidateState(panel, { repaint: false });
    panel.state.message = "Candidate accepted and applied locally.";
    setQueueGuardContext({
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
      queueAllowed: Boolean(accepted.queue_allowed ?? panel.state.queueAllowed),
    });
    panel.state.queueGuard = getQueueGuardStateForPanel();
    panel.state.debugPayload = {
      accepted,
      undo_stack_depth: panel.state.undoStack.length,
    };
    renderAgentPanel(panel);
    toast("Agent candidate applied");
  })();

  try {
    return await panel.state.inFlightApply;
  } finally {
    panel.state.inFlightApply = null;
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
    panel.state.phase = PANEL_STATE.ERROR;
    panel.state.failure = agentPanelFailure("SerializeError", String(e), {
      retryable: true,
      graph_unchanged: true,
      next_action: "Make sure the canvas can serialize, then retry Reject.",
    });
    panel.state.debugPayload = panel.state.failure;
    renderAgentPanel(panel);
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

  panel.state.phase = PANEL_STATE.APPLYING;
  panel.state.failure = null;
  panel.state.debugPayload = {
    rejecting_turn_id: panel.state.turnId,
    reject_request: rejectBody,
  };
  renderAgentPanel(panel);

  let rejected;
  try {
    const res = await fetch("/vibecomfy/agent-edit/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rejectBody),
    });
    rejected = await res.json();
    if (!res.ok || rejected?.ok === false || rejected?.error) {
      throw rejected || { kind: "RejectError", message: res.statusText };
    }
  } catch (e) {
    const failure = e?.ok === false
      ? e
      : agentPanelFailure("RejectError", String(e), {
          retryable: true,
          graph_unchanged: true,
          next_action: "Retry Reject after the backend responds again.",
        });
    panel.state.phase = PANEL_STATE.ERROR;
    panel.state.failure = failure;
    syncBaselineFromResponse(panel, failure);
    panel.state.auditRef = failure.audit_ref || panel.state.auditRef;
    panel.state.debugPayload = {
      ...failure,
      reject_request: rejectBody,
    };
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
    renderAgentPanel(panel);
    return;
  }

  pushHistory(panel, "rejected", panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate");
  pushTurnStatus(panel, "rejected", {
    turn_id: panel.state.turnId,
    baseline_turn_id: rejected.baseline_turn_id || panel.state.baselineTurnId,
    message: panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate",
    audit_ref: rejected.audit_ref || panel.state.auditRef,
    raw_payload: rejected,
  });
  panel.state.phase = PANEL_STATE.IDLE;
  syncBaselineFromResponse(panel, rejected);
  invalidateCandidateState(panel);
  panel.state.message = "Candidate rejected and cleared from the panel.";
  panel.state.failure = null;
  panel.state.auditRef = rejected.audit_ref || panel.state.auditRef;
  panel.state.queueGuard = getQueueGuardStateForPanel();
  panel.state.debugPayload = {
    rejected,
    graph_unchanged: true,
  };
  renderAgentPanel(panel);
  toast("Agent candidate rejected");
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

  panel.state.inFlightRebaseline = (async () => {
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
      panel.state.rebaselinePending = {
        reason: rebaselineReason,
        last_known_baseline_graph_hash: expectedBaselineGraphHash,
        client_graph_hash: snapshot.graphHash,
        client_structural_graph_hash: snapshot.structuralHash,
        idempotency_key: idempotencyKey,
      };
      renderAgentPanel(panel);

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
      const result = await res.json();
      if (!res.ok || result?.ok === false || result?.error) {
        throw result || { kind: "RebaselineError", message: res.statusText };
      }
      syncBaselineFromResponse(panel, result);
      panel.state.auditRef = result.audit_ref || panel.state.auditRef;
      panel.state.rebaselinePending = null;
      panel.state.debugPayload = {
        rebaseline_request: body,
        rebaseline_response: result,
      };
      return result;
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("RebaselineError", String(e), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry the rebaseline request after the backend responds again.",
          });
      syncBaselineFromResponse(panel, failure);
      panel.state.rebaselinePending = {
        ...(panel.state.rebaselinePending || {}),
        reason: rebaselineReason,
        retryable: Boolean(failure.retryable),
        failure_kind: failure.kind || null,
        failure_stage: failure.stage || null,
        message: failure.user_facing_message || failure.message || failure.error || null,
      };
      panel.state.auditRef = failure.audit_ref || panel.state.auditRef;
      panel.state.debugPayload = {
        ...failure,
        rebaseline_request: body,
      };
      throw failure;
    } finally {
      panel.state.inFlightRebaseline = null;
      renderAgentPanel(panel);
    }
  })();

  return panel.state.inFlightRebaseline;
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
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.message = "Current canvas queued for stale-state recovery rebaseline.";
  renderAgentPanel(panel);
  try {
    const result = await postAgentRebaseline(panel, {
      reason: "stale_state_recovery",
      lastKnownBaselineGraphHash: recovery.last_known_baseline_graph_hash ?? null,
    });
    invalidateCandidateState(panel);
    panel.state.failure = null;
    panel.state.rebaselineRecovery = null;
    panel.state.phase = PANEL_STATE.IDLE;
    panel.state.message = "Current canvas rebaselined. Submit again from this canvas.";
    panel.state.auditRef = result.audit_ref || panel.state.auditRef;
    panel.state.debugPayload = {
      stale_state_recovery: true,
      rebaseline_response: result,
    };
    renderAgentPanel(panel);
    toast("Current canvas rebaselined");
    return result;
  } catch (failure) {
    panel.state.rebaselineRecovery = extractRebaselineRecovery(failure) || recovery;
    panel.state.phase = PANEL_STATE.ERROR;
    panel.state.message = "Current canvas rebaseline failed. Review the evidence and retry.";
    panel.state.debugPayload = {
      ...(panel.state.debugPayload || {}),
      stale_state_recovery: true,
    };
    renderAgentPanel(panel);
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
  clearChangedNodeFeedbackVisuals();
  app.loadGraphData(previous.graph);
  panel.state.lastAppliedChanges = null;
  setQueueGuardContext(null);
  panel.state.phase = PANEL_STATE.IDLE;
  panel.state.failure = null;
  panel.state.message = "Previous graph restored locally. Rebaselining undo state...";
  panel.state.queueGuard = getQueueGuardStateForPanel();
  panel.state.debugPayload = {
    undone_turn_id: previous.turn_id || null,
    restored_graph_hash: previous.client_graph_hash || null,
    undo_stack_depth: panel.state.undoStack.length,
  };
  renderAgentPanel(panel);
  try {
    const result = await postAgentRebaseline(panel, {
      reason: "undo",
      lastKnownBaselineGraphHash:
        previous.accepted_baseline_graph_hash
        ?? panel.state.rebaselinePending?.last_known_baseline_graph_hash
        ?? panel.state.baselineGraphHash
        ?? null,
    });
    panel.state.undoStack.pop();
    pushHistory(panel, "undo", previous.turn_id ? `restored pre-apply graph for turn ${previous.turn_id}` : "restored previous graph");
    pushTurnStatus(panel, "undone", {
      turn_id: previous.turn_id || null,
      baseline_turn_id: result.baseline_turn_id || null,
      message: previous.turn_id ? `restored pre-apply graph for turn ${previous.turn_id}` : "restored previous graph",
      audit_ref: result.audit_ref || panel.state.auditRef,
      raw_payload: result,
    });
    panel.state.phase = PANEL_STATE.IDLE;
    panel.state.failure = null;
    panel.state.auditRef = result.audit_ref || panel.state.auditRef;
    panel.state.message = "Previous graph restored and rebaselined locally.";
    panel.state.queueGuard = getQueueGuardStateForPanel();
    panel.state.debugPayload = {
      rebaseline_response: result,
      undone_turn_id: previous.turn_id || null,
      restored_graph_hash: previous.client_graph_hash || null,
      undo_stack_depth: panel.state.undoStack.length,
    };
    renderAgentPanel(panel);
    toast("Previous graph restored");
    return result;
  } catch (failure) {
    panel.state.phase = PANEL_STATE.ERROR;
    panel.state.message = "Previous graph restored locally, but the undo rebaseline failed. Retry Undo Rebaseline.";
    panel.state.debugPayload = {
      ...(panel.state.debugPayload || {}),
      undone_turn_id: previous.turn_id || null,
      restored_graph_hash: previous.client_graph_hash || null,
      undo_stack_depth: panel.state.undoStack.length,
    };
    renderAgentPanel(panel);
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
  const panel = openAgentPanel();
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
    if (panel.root.dataset.open === "1") {
      closeAgentPanel(panel);
    } else {
      openAgentEdit();
    }
  });
  document.body.appendChild(btn);
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
    ensureAgentLauncher();
  },
});
