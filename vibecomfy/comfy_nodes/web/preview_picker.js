// vibecomfy/comfy_nodes/web/preview_picker.js
// Hideable "Preview query" picker for the VibeComfy chat panel.
//
// This module is a dev/demo-only, self-contained installer. It reads
// `localStorage["vibecomfy_demo_picker_enabled"]`: when that key is not `"0"`,
// the installer probes `/vibecomfy/demo/scenarios`. A successful manifest
// response mounts a small "▦ Demo" toggle in the panel header and a hideable
// toolbar that lists curated demo scenarios.
// Selecting a scenario and clicking "Load & Play" replays it as a fake agent
// turn: the original graph is applied to the canvas, a user query + agent reply
// are pushed to the chat thread, and the panel state is populated to mirror a
// normal AWAITING_REVIEW candidate (including `__demoMode` for the demo-only
// Apply/Reject branches defined later in the lifecycle).
//
// The server endpoint is the source of truth for whether demo mode exists. A
// missing/disabled endpoint leaves no UI mounted and no panel state touched.

import { app } from "../../scripts/app.js";
import { applyGraphCandidateInPlace } from "./comfy_adapter.js";
import { createIntentGraphAdapter } from "./intent_graph_adapter.js";
import { scheduleRenderAgentPanel } from "./panel_scheduler.js";
import { currentAgentPanel } from "./panel_runtime.js";
import { PANEL_STATE, RENDER_SECTIONS } from "./agent_edit_lifecycle.js";
import {
  commitApplyResolved,
  commitLifecycleBaselineRestore,
  commitLifecycleReset,
  normalizeCommitFieldChangesFromSubmit,
  commitOptimisticSubmit,
  commitTerminalResponse,
  commitTranscriptRehydrate,
} from "./agent_lifecycle_commit.js";

const LS_DEMO_PICKER_ENABLED = "vibecomfy_demo_picker_enabled";
const SCENARIOS_ENDPOINT = "/vibecomfy/demo/scenarios";
const SCENARIO_ENDPOINT = "/vibecomfy/demo/scenario";
const DEMO_STAGES = Object.freeze(["before_send", "sent_loading", "ready_to_apply", "applied"]);
const DEMO_PRODUCTION_IDENTITY_FIELDS = Object.freeze([
  "sessionId",
  "turnId",
  "baselineTurnId",
  "baselineGraphHash",
  "baselineGraphHashKind",
  "baselineGraphHashVersion",
  "baselineSource",
  "baselineRebaselineId",
  "baselineGraphSourcePath",
]);

function makeHelpers(overrides = {}) {
  // T8: Pass through ALL provided helpers so callers can inject roundtrip
  // functions (fulfillLifecycleTransitionObligations, pushHistory, etc.)
  // without creating circular imports.
  return {
    app: overrides.app || app,
    applyGraphCandidateInPlace: overrides.applyGraphCandidateInPlace || applyGraphCandidateInPlace,
    scheduleRenderAgentPanel: overrides.scheduleRenderAgentPanel || scheduleRenderAgentPanel,
    currentAgentPanel: overrides.currentAgentPanel || currentAgentPanel,
    PANEL_STATE: overrides.PANEL_STATE || PANEL_STATE,
    RENDER_SECTIONS: overrides.RENDER_SECTIONS || RENDER_SECTIONS,
    ...overrides,
  };
}

function isPickerEnabled() {
  if (globalThis.__VIBECOMFY_FORCE_DEMO_PICKER__ === true) {
    return true;
  }
  try {
    return localStorage.getItem(LS_DEMO_PICKER_ENABLED) !== "0";
  } catch (_e) {
    return true;
  }
}

function isDemoUnavailableError(error) {
  return error?.code === "demo_unavailable" || error?.status === 404;
}

function el(tag, text = "") {
  const element = document.createElement(tag);
  if (text !== "") {
    element.textContent = String(text);
  }
  return element;
}

function button(label, onClick) {
  const btn = el("button", label);
  btn.type = "button";
  if (typeof onClick === "function") {
    btn.addEventListener("click", onClick);
  }
  return btn;
}

function setVisible(element, visible) {
  if (element) {
    element.style.display = visible ? "flex" : "none";
  }
}

async function sha256Hex(text) {
  try {
    if (typeof crypto !== "undefined" && crypto.subtle && typeof TextEncoder !== "undefined") {
      const data = new TextEncoder().encode(text);
      const hash = await crypto.subtle.digest("SHA-256", data);
      return Array.from(new Uint8Array(hash))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    }
  } catch (_e) {
    // fall through to deterministic fallback
  }
  return `demo-${text.length}-${String(text).slice(0, 16)}`;
}

function normalizeEligibility(raw) {
  if (raw && typeof raw === "object" && typeof raw.reason === "string") {
    const knownReasons = new Set([
      "applyable",
      "no_candidate",
      "missing_contract",
      "missing_durable_turn_metadata",
      "not_latest",
      "superseded",
      "server_blocked",
      "stale_canvas",
      "queue_blocked_warning",
    ]);
    const reason = knownReasons.has(raw.reason) ? raw.reason : "applyable";
    return {
      applyable: raw.applyable !== false,
      reason,
      message: typeof raw.message === "string" ? raw.message : "",
      warnings: Array.isArray(raw.warnings) ? raw.warnings.slice() : [],
    };
  }
  return {
    applyable: true,
    reason: "applyable",
    message: "Demo candidate is ready to apply.",
    warnings: [],
  };
}

function makeMessage({ role, text, sessionId, turnId, response = null }) {
  const now = new Date().toISOString();
  const message = {
    role: String(role || ""),
    text: String(text || ""),
    session_id: sessionId,
    turn_id: turnId,
    source: "demo",
    timestamp: now,
    synthetic: false,
    optimistic: false,
  };
  if (role === "agent" && response && typeof response === "object") {
    message.outcome = clonePlainData(response.outcome);
    message.change_details = clonePlainData(response.changeDetails);
    message.changes = clonePlainData(response.fieldChanges);
    message.candidateGraphHash = response.candidateGraphHash || null;
    message.apply_eligibility = clonePlainData(response.eligibility);
    message.report = clonePlainData(response.report);
  }
  return message;
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

function nodeIdentity(node) {
  const uid = node?.properties?.vibecomfy_uid;
  if (uid != null && String(uid)) {
    return String(uid);
  }
  return node?.id == null ? null : String(node.id);
}

function previewFocusGraph(payload) {
  const { originalGraph, candidateGraph } = payload;
  const originalNodes = Array.isArray(originalGraph?.nodes) ? originalGraph.nodes : [];
  const candidateNodes = Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : [];
  const originalById = new Map(
    originalNodes.map((node) => [nodeIdentity(node), node]).filter(([uid]) => uid != null),
  );
  const candidateById = new Map(
    candidateNodes.map((node) => [nodeIdentity(node), node]).filter(([uid]) => uid != null),
  );
  const changedIds = new Set(
    (Array.isArray(payload?.fieldChanges?.all) ? payload.fieldChanges.all : [])
      .map((change) => change?.uid)
      .filter((uid) => uid != null)
      .map(String),
  );
  for (const uid of originalById.keys()) {
    if (!candidateById.has(uid)) {
      changedIds.add(uid);
    }
  }
  for (const uid of candidateById.keys()) {
    if (!originalById.has(uid)) {
      changedIds.add(uid);
    }
  }
  // Older archived fixtures may not contain semantic change evidence. Retain a
  // deterministic graph comparison only as their viewport fallback; preview
  // content itself remains governed by the canonical response projection.
  if (changedIds.size === 0) {
    for (const [uid, node] of originalById) {
      const candidateNode = candidateById.get(uid);
      if (!candidateNode || JSON.stringify(node) !== JSON.stringify(candidateNode)) {
        changedIds.add(uid);
      }
    }
    for (const [uid, node] of candidateById) {
      const originalNode = originalById.get(uid);
      if (!originalNode || JSON.stringify(node) !== JSON.stringify(originalNode)) {
        changedIds.add(uid);
      }
    }
  }
  const nodes = [
    ...originalNodes.filter((node) => changedIds.has(nodeIdentity(node))),
    ...candidateNodes.filter((node) => changedIds.has(nodeIdentity(node))),
  ];
  return nodes.length > 0 ? { nodes, links: [] } : candidateGraph;
}

function buildErrorDisplay() {
  const node = el("div");
  Object.assign(node.style, {
    color: "#ff6c6c",
    fontSize: "11px",
    marginTop: "6px",
    display: "none",
  });
  return node;
}

/**
 * Install the demo preview picker on a panel shell.
 *
 * @param {object} panel - An agent panel object (must have a `.shell` element).
 * @param {object} [options] - Optional mount configuration.
 * @param {HTMLElement} [options.headerRight] - The header right container to
 *   receive the "▦ Demo" toggle button. If omitted, the toggle is placed inside
 *   the picker container itself.
 * @param {HTMLElement} [options.mountContainer] - Where to mount the picker
 *   toolbar; defaults to `panel.shell`.
 * @param {object} [options.helpers] - Optional overrides for the helpers used
 *   by the picker (app, applyGraphCandidateInPlace, scheduleRenderAgentPanel,
 *   currentAgentPanel, PANEL_STATE, RENDER_SECTIONS). Defaults to the module's
 *   own ES module imports so the picker is still self-contained when called
 *   without options.
 * @returns {object|null} - Picker controls object, or `null` if disabled or
 *   the panel has no shell.
 */
export function installPreviewPicker(panel, options = {}) {
  if (!isPickerEnabled()) {
    return null;
  }
  if (!panel?.shell || typeof document === "undefined") {
    console.warn("[vibecomfy] installPreviewPicker requires a panel with .shell and a document");
    return null;
  }

  const helpers = makeHelpers(options.helpers);
  const headerRight = options.headerRight || null;
  const mountContainer = options.mountContainer || panel.shell;

  const pickerContainer = el("div");
  Object.assign(pickerContainer.style, {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    padding: "8px 14px",
    borderBottom: "1px solid #282a32",
    background: "#14161b",
  });

  const controlsRow = el("div");
  Object.assign(controlsRow.style, {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    flexWrap: "wrap",
  });

  const select = el("select");
  Object.assign(select.style, {
    flex: "1 1 auto",
    minWidth: "120px",
    background: "#101115",
    color: "#edf2f7",
    border: "1px solid #282a32",
    borderRadius: "4px",
    padding: "4px 6px",
    fontSize: "11px",
    fontFamily: "monospace",
  });
  const placeholder = el("option", "No demo (use my current edit)");
  placeholder.value = "";
  // Keep the placeholder selectable (not disabled) so the user can explicitly
  // clear an active demo and return the picker to its default inert state — it
  // must never interfere with a real generation by default.
  placeholder.selected = true;
  select.appendChild(placeholder);

  const loadBtn = button("Load & Play", null);
  Object.assign(loadBtn.style, {
    padding: "4px 10px",
    fontSize: "11px",
    whiteSpace: "nowrap",
  });
  loadBtn.disabled = true;

  const prevBtn = button("◀", null);
  const nextBtn = button("▶", null);
  for (const navBtn of [prevBtn, nextBtn]) {
    Object.assign(navBtn.style, {
      padding: "4px 8px",
      fontSize: "11px",
      lineHeight: "1",
      whiteSpace: "nowrap",
    });
    navBtn.disabled = true;
  }
  prevBtn.title = "Previous demo stage";
  nextBtn.title = "Next demo stage";

  const errorDisplay = buildErrorDisplay();

  controlsRow.appendChild(select);
  controlsRow.appendChild(prevBtn);
  controlsRow.appendChild(nextBtn);
  controlsRow.appendChild(loadBtn);
  pickerContainer.appendChild(controlsRow);
  pickerContainer.appendChild(errorDisplay);

  let selectedScenarioId = null;
  let loadedScenario = null;
  let stageIndex = -1;
  let loadingScenario = false;
  let demoViewportFramed = false;
  let demoRehydrateEpoch = null;
  let productionIdentityBaseline = null;

  function showError(message) {
    errorDisplay.textContent = String(message || "");
    errorDisplay.style.display = message ? "block" : "none";
  }

  async function fetchScenarios() {
    const res = await fetch(SCENARIOS_ENDPOINT);
    if (!res.ok) {
      const error = new Error(`Failed to fetch demo scenarios: ${res.status}`);
      error.status = res.status;
      if (res.status === 404) {
        error.code = "demo_unavailable";
      }
      throw error;
    }
    const data = await res.json();
    if (!data?.ok || !Array.isArray(data.scenarios)) {
      throw new Error("Invalid demo scenarios response");
    }
    return data.scenarios;
  }

  async function fetchScenario(id) {
    const res = await fetch(`${SCENARIO_ENDPOINT}?id=${encodeURIComponent(id)}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch scenario: ${res.status}`);
    }
    const data = await res.json();
    if (!data?.ok) {
      throw new Error("Invalid demo scenario response");
    }
    return data;
  }

  function stagePayload() {
    if (!loadedScenario) {
      return null;
    }
    const originalGraph = loadedScenario.original_graph;
    const candidateGraph = loadedScenario.candidate_graph;
    const sessionId = loadedScenario.session_id;
    const turnId = loadedScenario.turn_id;
    const query = loadedScenario.scenario?.query || loadedScenario.query || "";
    const agentReply = loadedScenario.agent_reply || "";
    const outcome = {
      ...(loadedScenario.outcome && typeof loadedScenario.outcome === "object"
        ? clonePlainData(loadedScenario.outcome)
        : {}),
      kind: "candidate",
    };
    const changeDetails = loadedScenario.change_details || null;
    const report = loadedScenario.report || {};
    const candidateGraphHash = loadedScenario.__candidateGraphHash || null;
    const eligibility = normalizeEligibility(loadedScenario.eligibility);
    const userMessage = makeMessage({ role: "user", text: query, sessionId, turnId });
    const responseEnvelope = {
      outcome,
      changeDetails,
      candidateGraphHash,
      eligibility,
      report,
    };
    const fieldChanges = normalizeCommitFieldChangesFromSubmit({
      outcome,
      change_details: changeDetails,
    });
    const agentMessage = makeMessage({
      role: "agent",
      text: agentReply,
      sessionId,
      turnId,
      response: { ...responseEnvelope, fieldChanges },
    });
    return {
      originalGraph,
      candidateGraph,
      sessionId,
      turnId,
      query,
      agentReply,
      userMessage,
      agentMessage,
      candidateGraphHash,
      eligibility,
      outcome,
      changeDetails,
      report,
      fieldChanges,
    };
  }

  function updateStageButtons() {
    const hasStage = Boolean(loadedScenario) && stageIndex >= 0;
    prevBtn.disabled = loadingScenario || !hasStage || stageIndex <= 0;
    nextBtn.disabled = loadingScenario || !hasStage || stageIndex >= DEMO_STAGES.length - 1;
    loadBtn.disabled = loadingScenario || !selectedScenarioId;
    if (hasStage) {
      loadBtn.textContent = "Reload";
    } else {
      loadBtn.textContent = loadingScenario ? "Loading..." : "Load & Play";
    }
  }

  function schedulePanelRender(currentPanel) {
    helpers.scheduleRenderAgentPanel(
      "demo-picker",
      currentPanel,
      [
        helpers.RENDER_SECTIONS.THREAD,
        helpers.RENDER_SECTIONS.META,
        helpers.RENDER_SECTIONS.COMPOSER,
        helpers.RENDER_SECTIONS.NOTICE,
      ].filter(Boolean),
    );
  }

  function fulfillLifecycleObligations(currentPanel, obligations) {
    if (!obligations || typeof obligations !== "object") {
      return;
    }
    if (typeof helpers.fulfillLifecycleTransitionObligations === "function") {
      // Demo stages deliberately share the production reducer so their panel
      // projection stays realistic, but their synthetic session identity must
      // never escape into production persistence or transport. In particular,
      // terminal candidate/apply commits normally ask the orchestrator to bind
      // the session and rehydrate durable chat. Doing that for a demo races the
      // staged transcript with a real `/chat` response and makes messages
      // disappear as the user navigates.
      const demoSafeObligations = { ...obligations };
      for (const productionSideEffect of [
        "persistSession",
        "rehydrateChat",
        "persistScope",
        "forgetSession",
        "forgetScope",
        "setQueueGuardContext",
        "refreshQueueGuard",
        "queueGuardClear",
        "queueGuardClearScope",
      ]) {
        delete demoSafeObligations[productionSideEffect];
      }
      helpers.fulfillLifecycleTransitionObligations(currentPanel, demoSafeObligations);
    }
  }

  function captureProductionIdentity(currentPanel) {
    const baseline = {};
    for (const field of DEMO_PRODUCTION_IDENTITY_FIELDS) {
      baseline[field] = clonePlainData(currentPanel?.state?.[field] ?? null);
    }
    productionIdentityBaseline = baseline;
  }

  function restoreProductionIdentity(currentPanel) {
    if (!currentPanel?.state) {
      return;
    }
    if (!productionIdentityBaseline) {
      productionIdentityBaseline = Object.fromEntries(
        DEMO_PRODUCTION_IDENTITY_FIELDS.map((field) => [field, null]),
      );
    }
    // Keep the staged demo transcript visible, but return production routing
    // and baseline authority to exactly what it was before playback. This lets
    // a later real submit continue the user's real conversation rather than
    // addressing the packaged demo session or unnecessarily forking.
    commitLifecycleBaselineRestore(currentPanel, {
      baseline: productionIdentityBaseline,
      debugPayload: currentPanel.state.debugPayload,
    });
  }

  function requestPreviewOverlayRepaint() {
    // Candidate arrival is not visually complete until its semantic fields
    // have been projected. Do this synchronously after the lifecycle commit;
    // a requestAnimationFrame callback may run after observers/screenshots
    // have already mistaken an older draw-model cache for readiness.
    if (typeof helpers.refreshPreviewDomOverlay === "function") {
      helpers.refreshPreviewDomOverlay();
    }
    const repaint = () => {
      try {
        const result = createIntentGraphAdapter(helpers.app).repaint();
        if (!result.ok) {
          console.warn("[vibecomfy] demo preview repaint unavailable:", result.diagnostic);
        }
        if (typeof helpers.refreshPreviewDomOverlay === "function") {
          helpers.refreshPreviewDomOverlay();
        }
      } catch (error) {
        console.warn("[vibecomfy] demo preview repaint failed:", error);
      }
    };

    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(repaint);
      return;
    }
    setTimeout(repaint, 0);
  }

  function commitDemoTranscript(currentPanel, payload, messages, latestCandidate = null) {
    commitTranscriptRehydrate(currentPanel, {
      requestEpoch: demoRehydrateEpoch,
      messages,
      sessionId: payload.sessionId,
      latestTurnId: payload.turnId,
      latestCandidate,
    });
    if (typeof helpers.resetThreadRenderState === "function") {
      helpers.resetThreadRenderState(currentPanel);
    }
  }

  function replaceDemoGraphPreservingViewport(graph) {
    const viewport = typeof helpers.captureCanvasViewportSnapshot === "function"
      ? helpers.captureCanvasViewportSnapshot()
      : null;
    try {
      helpers.applyGraphCandidateInPlace(
        helpers.app,
        clonePlainData(graph),
        { repaint: viewport == null },
      );
    } catch (graphError) {
      console.warn("[vibecomfy] demo graph apply failed:", graphError);
    } finally {
      if (viewport && typeof helpers.restoreCanvasViewportSnapshot === "function") {
        helpers.restoreCanvasViewportSnapshot(viewport);
      }
    }
    if (viewport) {
      try {
        createIntentGraphAdapter(helpers.app).repaint();
      } catch (error) {
        console.warn("[vibecomfy] demo viewport-preserving repaint failed:", error);
      }
    }
  }

  function applyOriginalGraph(payload) {
    replaceDemoGraphPreservingViewport(payload.originalGraph);
  }

  function frameDemoViewportOnce(payload) {
    if (
      demoViewportFramed
      || typeof helpers.fitCanvasViewportToGraphPayload !== "function"
    ) {
      return;
    }
    // Choose one camera for the entire scenario. It includes the changed
    // before/after region so review additions remain visible, but navigating
    // between stages never pans or zooms the user's view.
    helpers.fitCanvasViewportToGraphPayload(
      previewFocusGraph(payload),
    );
    demoViewportFramed = true;
  }

  function applyCandidateGraph(payload) {
    replaceDemoGraphPreservingViewport(payload.candidateGraph);
  }

  function isLayoutPreviewScenario() {
    const report = loadedScenario?.report;
    return Boolean(
      report
      && typeof report === "object"
      && (report.kind === "reorganise" || report.route === "reorganise" || report.reorganise),
    );
  }

  function renderDemoStage(nextStageIndex, options = {}) {
    const currentPanel = panel || helpers.currentAgentPanel();
    const payload = stagePayload();
    if (!currentPanel?.state || !payload) {
      return;
    }
    const boundedStage = Math.max(0, Math.min(DEMO_STAGES.length - 1, nextStageIndex));
    stageIndex = boundedStage;
    const stage = DEMO_STAGES[stageIndex];

    currentPanel.state.__demoMode = true;
    currentPanel.state.__demoStage = stage;
    currentPanel.state.__demoStageIndex = stageIndex;
    currentPanel.state.__demoScenarioId = loadedScenario?.scenario?.id || loadedScenario?.id || null;

    if (stage === "before_send") {
      applyOriginalGraph(payload);
      frameDemoViewportOnce(payload);
      const obligations = commitLifecycleReset(currentPanel, {
        rejected: {},
        message: null,
        debugPayload: { source: "demo", stage },
      });
      commitDemoTranscript(currentPanel, payload, [], null);
      fulfillLifecycleObligations(currentPanel, obligations);
    } else if (stage === "sent_loading") {
      applyOriginalGraph(payload);
      const resetObligations = commitLifecycleReset(currentPanel, {
        rejected: {},
        message: null,
        debugPayload: { source: "demo", stage, reset: true },
      });
      fulfillLifecycleObligations(currentPanel, resetObligations);
      const submitObligations = commitOptimisticSubmit(currentPanel, {
        lastSubmit: { prompt: payload.query, source: "demo" },
        debugPayload: { source: "demo", stage },
      });
      commitDemoTranscript(currentPanel, payload, [payload.userMessage], null);
      fulfillLifecycleObligations(currentPanel, submitObligations);
    } else if (stage === "ready_to_apply") {
      if (isLayoutPreviewScenario()) {
        applyCandidateGraph(payload);
      } else {
        applyOriginalGraph(payload);
      }
      const terminalResult = {
        ok: true,
        session_id: payload.sessionId,
        turn_id: payload.turnId,
        baseline_turn_id: null,
        message: payload.agentReply || null,
        outcome: payload.outcome,
        eligibility: payload.eligibility,
        report: payload.report,
        change_details: payload.changeDetails || null,
        candidate_graph_hash: payload.candidateGraphHash,
      };
      const obligations = commitTerminalResponse(currentPanel, {
        result: terminalResult,
        outcome: payload.outcome,
        candidateGraph: payload.candidateGraph,
        candidateGraphHash: payload.candidateGraphHash,
        applyEligibility: payload.eligibility,
        queueAllowed: false,
        changeDetails: payload.changeDetails,
        lastSubmitFieldChanges: payload.fieldChanges,
        debugPayload: {
          source: "demo",
          stage,
          scenarioId: loadedScenario?.scenario?.id || loadedScenario?.id || null,
        },
      });
      commitDemoTranscript(currentPanel, payload, [payload.userMessage, payload.agentMessage], terminalResult);
      fulfillLifecycleObligations(currentPanel, obligations);
    } else if (stage === "applied") {
      if (!options.alreadyApplied) {
        applyCandidateGraph(payload);
      }
      const obligations = commitApplyResolved(currentPanel, {
        accepted: { ok: true, session_id: payload.sessionId, turn_id: payload.turnId },
        lastAppliedChanges: options.lastAppliedChanges || payload.changeDetails || {
          summary: "Demo candidate applied.",
        },
        debugPayload: { source: "demo", stage },
      });
      commitDemoTranscript(currentPanel, payload, [payload.userMessage, payload.agentMessage], null);
      fulfillLifecycleObligations(currentPanel, obligations);
      currentPanel.state.__demoMode = false;
      restoreProductionIdentity(currentPanel);
    }

    if (stage === "before_send" || stage === "sent_loading") {
      restoreProductionIdentity(currentPanel);
    }
    // Non-layout demos keep the original graph live during review and rely on
    // the overlay to show exactly what the candidate would change. Make that
    // preview explicit for the review stage, and never let it leak into the
    // before/send/applied stages.
    currentPanel.state.previewEnabled = stage === "ready_to_apply";
    // Lifecycle commits intentionally know nothing about demo navigation.
    // Reassert the local playback cursor after every shared reducer commit so
    // backward/forward navigation cannot render a correct transcript under a
    // stale stage label.
    currentPanel.state.__demoStage = stage;
    currentPanel.state.__demoStageIndex = stageIndex;
    updateStageButtons();
    showError("");
    schedulePanelRender(currentPanel);
    requestPreviewOverlayRepaint();
  }

  async function loadScenarioById(id, { readyToApply = false } = {}) {
    if (!id) {
      showError("Select a scenario first");
      return null;
    }
    showError("");
    loadingScenario = true;
    updateStageButtons();

    try {
      const scenario = await fetchScenario(id);
      const currentPanel = panel || helpers.currentAgentPanel();
      if (!currentPanel?.state) {
        throw new Error("No active agent panel");
      }

      const originalGraph = scenario.original_graph;
      const candidateGraph = scenario.candidate_graph;
      const agentReply = scenario.agent_reply || "";
      const sessionId = scenario.session_id;
      const turnId = scenario.turn_id;
      const query = scenario.scenario?.query || scenario.query || "";

      if (!originalGraph || !candidateGraph) {
        throw new Error("Scenario response missing required graph data");
      }

      const candidateGraphHash = scenario.candidate_graph_hash
        || await sha256Hex(JSON.stringify(candidateGraph));
      // Capture only after all awaited scenario preparation, then fence in the
      // same synchronous turn. A production rehydrate that resolves while the
      // scenario/hash is loading is therefore included in the saved identity;
      // anything older that resolves afterward is rejected by the new epoch.
      if (currentPanel.state.__demoMode !== true) {
        captureProductionIdentity(currentPanel);
      }
      demoRehydrateEpoch = typeof helpers.fenceChatRehydrateForDemo === "function"
        ? helpers.fenceChatRehydrateForDemo(currentPanel)
        : null;
      loadedScenario = {
        ...scenario,
        original_graph: clonePlainData(originalGraph),
        candidate_graph: clonePlainData(candidateGraph),
        __candidateGraphHash: candidateGraphHash,
      };
      demoViewportFramed = false;
      renderDemoStage(0);
      if (readyToApply) {
        renderDemoStage(1);
        renderDemoStage(2);
      }
      return loadedScenario;
    } catch (error) {
      showError(error?.message || String(error));
      return null;
    } finally {
      loadingScenario = false;
      updateStageButtons();
    }
  }

  async function loadAndPlay() {
    return loadScenarioById(selectedScenarioId);
  }

  // Tear down any active demo playback and return the picker to its default
  // inert state. Safe to call at any time: it is a no-op when no demo is
  // staged, so the real submit path can call it unconditionally to guarantee a
  // real edit is never masked by lingering demo state (__demoMode would
  // otherwise route Apply/Reject to the demo handlers).
  function clearActiveDemo(currentPanel) {
    const target = currentPanel || panel || helpers.currentAgentPanel();
    const demoActive = target?.state?.__demoMode === true || loadedScenario != null;
    if (!demoActive) {
      return false;
    }
    loadedScenario = null;
    selectedScenarioId = null;
    stageIndex = -1;
    demoViewportFramed = false;
    select.value = "";
    if (target?.state) {
      // Drive the panel out of the demo's AWAITING_REVIEW the same way a demo
      // reject does. The composer re-derives previewEnabled from the review
      // state on every render, so merely toggling the flag is overwritten;
      // clearing the candidate through the lifecycle is what actually drops
      // the demo overlay and frees Apply/Reject to route to the real path.
      const obligations = commitLifecycleReset(target, {
        rejected: { demo: true, cleared: true },
        message: null,
        debugPayload: { source: "demo", cleared: true },
      });
      fulfillLifecycleObligations(target, obligations);
      delete target.state.__demoMode;
      delete target.state.__demoStage;
      delete target.state.__demoStageIndex;
      delete target.state.__demoScenarioId;
      target.state.previewEnabled = false;
      if (productionIdentityBaseline) {
        restoreProductionIdentity(target);
      }
    }
    productionIdentityBaseline = null;
    updateStageButtons();
    showError("");
    if (target) {
      schedulePanelRender(target);
    }
    return true;
  }

  select.addEventListener("change", () => {
    const value = select.value || "";
    if (!value) {
      // Explicit "No demo": tear down any active demo so it cannot interfere
      // with the user's real generation or edit.
      clearActiveDemo(panel || helpers.currentAgentPanel());
      return;
    }
    selectedScenarioId = value;
    loadedScenario = null;
    stageIndex = -1;
    demoViewportFramed = false;
    loadBtn.disabled = !selectedScenarioId;
    updateStageButtons();
    showError("");
  });

  loadBtn.addEventListener("click", loadAndPlay);
  prevBtn.addEventListener("click", () => {
    if (loadedScenario && stageIndex > 0) {
      renderDemoStage(stageIndex - 1);
    }
  });
  nextBtn.addEventListener("click", () => {
    if (loadedScenario && stageIndex < DEMO_STAGES.length - 1) {
      renderDemoStage(stageIndex + 1);
    }
  });

  const toggleBtn = button("▦ Demo", () => {
    const expanded = pickerContainer.style.display === "none";
    setVisible(pickerContainer, expanded);
    toggleBtn.style.opacity = expanded ? "1" : "0.7";
  });
  Object.assign(toggleBtn.style, {
    padding: "4px 8px",
    fontSize: "11px",
    lineHeight: "1",
    opacity: "0.7",
  });
  toggleBtn.title = "Demo scenario picker";

  let mounted = false;

  function mountPicker() {
    if (mounted) {
      return;
    }
    mounted = true;
    if (headerRight) {
      headerRight.appendChild(toggleBtn);
    } else {
      pickerContainer.appendChild(toggleBtn);
    }

    // Insert the picker toolbar right after the panel header (the first child of
    // mountContainer is expected to be the header).
    const firstChild = mountContainer.firstChild;
    if (firstChild) {
      mountContainer.insertBefore(pickerContainer, firstChild.nextSibling);
    } else {
      mountContainer.appendChild(pickerContainer);
    }
  }

  function unmountPicker() {
    mounted = false;
    if (toggleBtn.parentNode) {
      toggleBtn.parentNode.removeChild(toggleBtn);
    }
    if (pickerContainer.parentNode) {
      pickerContainer.parentNode.removeChild(pickerContainer);
    }
  }

  // Load scenario list. This is the only network traffic the module emits,
  // and it only happens when the picker is enabled and installed.
  fetchScenarios()
    .then((scenarios) => {
      for (const scenario of scenarios) {
        const option = el("option", scenario.title || scenario.id);
        option.value = scenario.id;
        select.appendChild(option);
      }
      mountPicker();
      if (scenarios.length === 0) {
        showError("No demo scenarios available");
      }
    })
    .catch((error) => {
      if (isDemoUnavailableError(error)) {
        unmountPicker();
        return;
      }
      mountPicker();
      showError(error?.message || String(error));
    });

  // ── T8: Demo Apply/Reject handlers ──────────────────────────────────
  // These are called by applyAgentCandidate / rejectAgentCandidate when
  // __demoMode is true.  They keep demo flows local (no POST) and route
  // lifecycle reflection through commit helpers.

  function handleDemoApply(currentPanel) {
    const payload = stagePayload();
    if (!currentPanel?.state || !payload) {
      return;
    }
    if (!currentPanel.state.candidateGraph) {
      // Guard: no candidate to apply (handled in roundtrip, but double-check)
      return;
    }

    // T12: Demo apply must respect the active canvas scope, mirroring the
    // production apply authority (which calls assertApplyScopeConsistency in
    // vibecomfy_roundtrip.js before touching the canvas).  A scope mismatch
    // means the demo candidate does not belong to the currently visible
    // workflow tab and must be refused locally: no POST, no graph mutation.
    // The helper is optional so isolation tests that don't track scope (and
    // have no chatScopeId) treat this as a no-op pass-through.
    const scopeCheck = typeof helpers.assertApplyScopeConsistency === "function"
      ? helpers.assertApplyScopeConsistency(currentPanel, currentPanel.state.sessionId || null)
      : { ok: true, reason: null, details: null };
    if (!scopeCheck.ok) {
      const blockedObligations = commitLifecycleReset(currentPanel, {
        rejected: { demo: true, scope_mismatch: true },
        message: `Demo apply blocked: ${scopeCheck.reason || "scope/session inconsistency"}.`,
        toast: "Demo apply blocked (scope mismatch)",
        debugPayload: {
          demo: true,
          scope_mismatch: scopeCheck.reason || "unknown",
          details: scopeCheck.details || null,
        },
      });
      if (typeof helpers.fulfillLifecycleTransitionObligations === "function") {
        helpers.fulfillLifecycleTransitionObligations(currentPanel, blockedObligations);
      }
      schedulePanelRender(currentPanel);
      return;
    }

    // Apply the candidate graph to the canvas (simple path without intent
    // repairs; demo scenarios use basic graphs).
    applyCandidateGraph(payload);

    // Build change feedback mirroring the production apply path.
    const lastAppliedChanges = helpers.announceChangedNodes
      ? helpers.announceChangedNodes(currentPanel, helpers.extractChangedNodeFeedback
        ? helpers.extractChangedNodeFeedback(currentPanel.state.candidateReport)
        : null)
      : (payload.changeDetails || { summary: "Demo candidate applied." });

    // Push undo history.
    if (typeof helpers.pushHistory === "function") {
      helpers.pushHistory(currentPanel, "applied",
        currentPanel.state.turnId ? `turn ${currentPanel.state.turnId}` : "candidate");
    }

    // Move to the "applied" stage. That stage owns the one and only
    // commitApplyResolved call, transcript replacement, candidate cleanup,
    // obligation filtering, and render.
    renderDemoStage(3, { alreadyApplied: true, lastAppliedChanges });
  }

  function handleDemoReject(currentPanel) {
    if (!currentPanel?.state?.candidateGraph
        || !currentPanel.state.sessionId
        || !currentPanel.state.turnId) {
      return;
    }

    // Push undo history.
    if (typeof helpers.pushHistory === "function") {
      helpers.pushHistory(currentPanel, "rejected",
        currentPanel.state.turnId ? `turn ${currentPanel.state.turnId}` : "candidate");
    }

    // Lifecycle reflection through commit helper.
    const obligations = commitLifecycleReset(currentPanel, {
      rejected: { demo: true },
      message: "Demo candidate rejected and cleared from the panel.",
      toast: "Demo candidate rejected",
      debugPayload: {
        demo: true,
        graph_unchanged: true,
      },
    });

    // Fulfill + restore layout baseline.
    if (typeof helpers.fulfillLifecycleTransitionObligations === "function") {
      helpers.fulfillLifecycleTransitionObligations(currentPanel, obligations);
    }
    if (typeof helpers.restoreLayoutPreviewBaseline === "function") {
      helpers.restoreLayoutPreviewBaseline(currentPanel);
    }

    // Clear demo mode.
    delete currentPanel.state.__demoMode;
    currentPanel.state.previewEnabled = false;
    restoreProductionIdentity(currentPanel);

    // Schedule render.
    schedulePanelRender(currentPanel);
  }

  return {
    toggle: toggleBtn,
    container: pickerContainer,
    select,
    prevButton: prevBtn,
    nextButton: nextBtn,
    loadButton: loadBtn,
    loadScenarioById,
    clearActiveDemo,
    get mounted() {
      return mounted;
    },
    showAppliedStage(options = {}) {
      if (loadedScenario) {
        renderDemoStage(3, { ...options, alreadyApplied: true });
      }
    },
    handleDemoApply,
    handleDemoReject,
  };
}

export function isDemoPickerEnabled() {
  return isPickerEnabled();
}
