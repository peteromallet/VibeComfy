// ── Diagnostics Reporting Module (Sprint 1 — extracted diagnostics/reporting ownership) ──
// This module owns diagnostics capture, issue reporting, audit export, zip bundling,
// rating submission, and the "Having issues?" modal.
// Browser APIs are guarded for Node imports. Monolith-local helpers (DOM creation,
// UI widgets, clipboard, debug snapshot) are received through dependency injection.
// This module does NOT import from other vibecomfy web modules.

// ── Module-level dependency injection ────────────────────────────────────────

let _deps = {};

/**
 * Configure monolith-local dependencies required by diagnostics functions.
 *
 * Expected deps shape (all optional — functions degrade gracefully when absent):
 *   el(tag, text)               — document.createElement wrapper
 *   button(label, onClick)       — <button> factory
 *   setButtonEmphasis(btn, visible, tone) — style helper for buttons
 *   downloadBlob(blob, filename) — trigger a browser download
 *   copyTextToClipboard(text)    — async clipboard write
 *   getPanelElementById(panel, id) — DOM query scoped to a panel
 *   buildAgentPanelDebugSnapshot(panel) — full panel debug snapshot
 *   PANEL_IDS                    — { issueModal, … } frozen id map
 *
 * @param {object} deps
 */
export function configureDiagnosticsDeps(deps) {
  if (deps && typeof deps === "object") {
    _deps = { ..._deps, ...deps };
  }
}

// ── Constants ───────────────────────────────────────────────────────────────

const ISSUE_REPORT_TURN_LIMIT = 3;
const AGENT_SOLVE_TURN_LIMIT = 2;
const REPORT_FIELD_LIMIT = 360;
const REASONING_STEP_LIMIT = 8;
const REASONING_DIAG_LIMIT = 3;

// ── Internal helpers ────────────────────────────────────────────────────────

function compactReportText(value, limit = REPORT_FIELD_LIMIT) {
  if (value == null) {
    return null;
  }
  let text;
  try {
    text = typeof value === "string" ? value : JSON.stringify(value);
  } catch (_error) {
    text = String(value);
  }
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  if (!compact) {
    return null;
  }
  return compact.length > limit ? `${compact.slice(0, Math.max(0, limit - 1))}...` : compact;
}

function pageUrlForReport() {
  try {
    if (typeof window !== "undefined" && typeof window.location?.href === "string") {
      return window.location.href;
    }
    if (typeof globalThis !== "undefined" && typeof globalThis.location?.href === "string") {
      return globalThis.location.href;
    }
  } catch (_error) {
    // Best effort only; reports still work without a browser location.
  }
  return "(unknown URL)";
}

function debugSnapshotForReport(panel) {
  try {
    if (typeof window !== "undefined" && typeof window.__vibecomfyPanelDebug === "function") {
      const snapshot = window.__vibecomfyPanelDebug();
      if (snapshot && typeof snapshot === "object") {
        return snapshot;
      }
    }
  } catch (_error) {
    // Debug hook is optional in tests and degraded browser environments.
  }
  return {
    panelId: panel?.panelId || null,
    phase: panel?.state?.phase || null,
    sessionId: panel?.state?.sessionId || null,
    turnId: panel?.state?.turnId || null,
    messageCount: Array.isArray(panel?.state?.chatMessages) ? panel.state.chatMessages.length : 0,
    renderErrors: Array.isArray(panel?.__renderErrors) ? panel.__renderErrors.length : 0,
  };
}

function turnTaskForReport(entry, panel) {
  return compactReportText(
    entry?.task
    || entry?.raw_payload?.task
    || entry?.raw_payload?.user_task
    || entry?.raw_payload?.request?.task
    || entry?.raw_payload?.prompt
    || panel?.state?.lastSubmit?.task
    || null,
  );
}

function turnFailureForReport(entry) {
  const failure = entry?.failure && typeof entry.failure === "object" ? entry.failure : null;
  const raw = entry?.raw_payload && typeof entry.raw_payload === "object" ? entry.raw_payload : null;
  const outcome = entry?.outcome && typeof entry.outcome === "object" ? entry.outcome : null;
  const kind =
    entry?.failure_kind
    || failure?.kind
    || raw?.failure_kind
    || outcome?.failure_kind
    || null;
  const stage =
    entry?.failure_stage
    || failure?.stage
    || raw?.failure_stage
    || raw?.stage
    || null;
  // Only surface a failure line for an actual failure. A noop / clarify / candidate
  // turn has a message but is NOT a failure — labeling it "Failure: …" (as the old
  // message-triggered path did) is misleading. Require a genuine error signal.
  const isFailure =
    Boolean(kind)
    || Boolean(failure)
    || outcome?.kind === "error"
    || raw?.kind === "error"
    || entry?.status === "error"
    || entry?.status === "failed";
  if (!isFailure) {
    return null;
  }
  const message =
    entry?.message
    || failure?.user_facing_message
    || failure?.message
    || failure?.error
    || raw?.user_facing_message
    || raw?.message
    || raw?.error
    || null;
  return compactReportText(`${kind || "Failure"}${stage ? ` @ ${stage}` : ""}${message ? `: ${message}` : ""}`);
}

function turnChangeDetailsForReport(entry) {
  const raw = entry?.raw_payload && typeof entry.raw_payload === "object" ? entry.raw_payload : null;
  const changeDetails =
    entry?.change_details
    || entry?.changeDetails
    || raw?.change_details
    || raw?.changeDetails
    || null;
  if (changeDetails && typeof changeDetails === "object") {
    const summary = compactReportText(changeDetails.done_summary || changeDetails.summary || null);
    const count = Number.isFinite(changeDetails.landed_operation_count)
      ? changeDetails.landed_operation_count
      : (Array.isArray(changeDetails.operations) ? changeDetails.operations.length : null);
    const ops = Array.isArray(changeDetails.operations)
      ? changeDetails.operations
        .map((op) => compactReportText(op?.summary || op?.field_path || op, 120))
        .filter(Boolean)
        .slice(0, 3)
      : [];
    return compactReportText([
      summary,
      count != null ? `${count} operation${count === 1 ? "" : "s"}` : null,
      ops.length ? ops.join("; ") : null,
    ].filter(Boolean).join(" | "));
  }
  if (entry?.done_summary) {
    return compactReportText(entry.done_summary);
  }
  if (Number.isFinite(entry?.landed_op_count)) {
    return `${entry.landed_op_count} landed operation${entry.landed_op_count === 1 ? "" : "s"}`;
  }
  const fieldChanges = entry?.field_changes || raw?.field_changes || null;
  if (Array.isArray(fieldChanges) && fieldChanges.length) {
    return compactReportText(
      fieldChanges
        .map((change) => change?.field_path || change?.path || null)
        .filter(Boolean)
        .slice(0, 5)
        .join("; "),
    );
  }
  return null;
}

// Map an agent outcome to a terminal turn status string.
function _turnStatusFromOutcome(outcome) {
  const kind = outcome && typeof outcome === "object" ? outcome.kind : null;
  if (outcome && typeof outcome === "object" && outcome.failure_kind) {
    return "error";
  }
  if (kind === "clarification" || kind === "clarify") {
    return "clarify";
  }
  if (kind === "noop" || kind === "candidate" || kind === "error") {
    return kind;
  }
  return kind || "done";
}

// Rebuild durable-shaped turn entries from the rehydrated chat transcript.
//
// `state.turns` is purely in-memory: it is populated as turns run live, but a
// page reload restores only `state.chatMessages` (see _handleChatRehydrateSuccess)
// and leaves `state.turns` empty. Without this fallback every diagnostic built
// after a reload reports "No recent turn records were captured" even though the
// full history (including per-step agent reasoning under change_details) is
// sitting in the rehydrated messages.
function turnsFromChatMessages(panel) {
  const messages = Array.isArray(panel?.state?.chatMessages) ? panel.state.chatMessages : [];
  const order = [];
  const byKey = new Map();
  let counter = 0;
  for (const msg of messages) {
    if (!msg || typeof msg !== "object") {
      continue;
    }
    const raw = msg.raw && typeof msg.raw === "object" ? msg.raw : msg;
    const turnId = msg.turnId || msg.turn_id || raw.turn_id || null;
    const key = turnId || `__idx_${counter}`;
    counter += 1;
    let entry = byKey.get(key);
    if (!entry) {
      entry = { entry_type: "durable", turn_id: turnId || null };
      byKey.set(key, entry);
      order.push(entry);
    }
    const role = msg.role || raw.role || null;
    const text = typeof msg.text === "string" ? msg.text : (typeof raw.text === "string" ? raw.text : null);
    if (role === "user") {
      if (!entry.task && text) {
        entry.task = text;
      }
      continue;
    }
    // Any non-user message is the agent side of the turn.
    const outcome = msg.outcome || raw.outcome || null;
    const changeDetails = msg.change_details || raw.change_details || null;
    if (text) {
      entry.message = text;
    }
    if (outcome) {
      entry.outcome = outcome;
    }
    if (changeDetails) {
      entry.change_details = changeDetails;
    }
    entry.status = _turnStatusFromOutcome(outcome);
    entry.failure_kind = (outcome && typeof outcome === "object" && outcome.failure_kind) || null;
    entry.raw_payload = raw;
  }
  // Chat is chronological; most-recent-first matches live `state.turns` order.
  return order.reverse();
}

// Surface the agent's actual per-step reasoning for a turn: the message it
// wrote, whether the batch landed, and the engine diagnostics (which carry the
// real root data — e.g. value_not_in_enum with the list of valid `choices`, or
// unknown_output_slot with the `available_slots`). This is where the genuine
// "why did it do that" lives, so the issue report / coding-agent prompt embed
// it rather than only the one-line outcome summary.
function turnReasoningForReport(entry) {
  const raw = entry?.raw_payload && typeof entry.raw_payload === "object" ? entry.raw_payload : null;
  const changeDetails =
    entry?.change_details
    || entry?.changeDetails
    || raw?.change_details
    || raw?.changeDetails
    || null;
  const steps =
    changeDetails && typeof changeDetails === "object" && Array.isArray(changeDetails.batch_turns)
      ? changeDetails.batch_turns
      : null;
  if (!steps || !steps.length) {
    return null;
  }
  const lines = [];
  const shown = steps.slice(0, REASONING_STEP_LIMIT);
  for (let i = 0; i < shown.length; i += 1) {
    const step = shown[i];
    if (!step || typeof step !== "object") {
      continue;
    }
    const num = Number.isFinite(step.turn_number) ? step.turn_number : i;
    const status = step.batch_ok === true ? "landed" : (step.batch_ok === false ? "rejected" : null);
    const message = compactReportText(step.message, 240) || "(no message)";
    lines.push(`    step ${num}${status ? ` [${status}]` : ""}: ${message}`);
    const code = compactReportText(step.batch, 200);
    if (code) {
      lines.push(`      code: ${code}`);
    }
    const diagnostics = Array.isArray(step.diagnostics) ? step.diagnostics : [];
    for (const diag of diagnostics.slice(0, REASONING_DIAG_LIMIT)) {
      if (!diag || typeof diag !== "object") {
        continue;
      }
      const detail = diag.detail && typeof diag.detail === "object" ? diag.detail : null;
      const choices = detail && Array.isArray(detail.choices)
        ? ` (valid: [${detail.choices.slice(0, 12).join(", ")}])`
        : "";
      const slots = detail && Array.isArray(detail.available_slots)
        ? ` (slots: [${detail.available_slots.slice(0, 12).join(", ")}])`
        : "";
      const head = diag.code ? `${diag.code}: ` : "";
      const diagText = compactReportText(`${head}${diag.message || ""}${choices}${slots}`, 260);
      if (diagText) {
        lines.push(`      - ${diagText}`);
      }
    }
  }
  if (steps.length > shown.length) {
    lines.push(`    (+${steps.length - shown.length} more step(s) — see messages.jsonl)`);
  }
  return lines.length ? lines.join("\n") : null;
}

function collectRecentTurnSummaries(panel, limit = ISSUE_REPORT_TURN_LIMIT) {
  let turns = Array.isArray(panel?.state?.turns) ? panel.state.turns : [];
  if (turns.length === 0) {
    // Reloaded panel: derive from the rehydrated chat transcript so the report
    // is not blank just because the in-memory turn array was never refilled.
    turns = turnsFromChatMessages(panel);
  }
  return turns.slice(0, limit).map((entry, index) => ({
    label: entry?.turn_id || (Number.isFinite(entry?.turn_number) ? `turn ${entry.turn_number}` : `entry ${index + 1}`),
    status: compactReportText(entry?.status || entry?.phase || "unknown", 80),
    task: turnTaskForReport(entry, panel) || "(not captured)",
    outcome: compactReportText(
      entry?.done_summary
      || entry?.outcome?.reason
      || entry?.outcome?.clarification?.message
      || entry?.message
      || entry?.outcome?.kind
      || entry?.exit_mode
      || null,
    ) || "(not captured)",
    failure: turnFailureForReport(entry),
    changes: turnChangeDetailsForReport(entry),
    reasoning: turnReasoningForReport(entry),
  }));
}

function formatTurnSummaries(summaries) {
  if (!Array.isArray(summaries) || summaries.length === 0) {
    return "- No recent turn records were captured in the panel state.";
  }
  return summaries.map((turn, index) => [
    `- Turn ${index + 1}${turn.label ? ` (${turn.label})` : ""}`,
    `  Task: ${turn.task}`,
    `  Status/outcome: ${turn.status || "unknown"}${turn.outcome ? `; ${turn.outcome}` : ""}`,
    turn.failure ? `  Error/failure: ${turn.failure}` : null,
    turn.changes ? `  Key changes: ${turn.changes}` : null,
    turn.reasoning ? `  Agent reasoning (per step — what it tried and why it was rejected):\n${turn.reasoning}` : null,
  ].filter(Boolean).join("\n")).join("\n");
}

function sessionArtifactPathForReport(panel, sessionId) {
  const state = panel?.state || {};
  const resolved = typeof state.chatSessionPathResolved === "string" && state.chatSessionPathResolved
    ? state.chatSessionPathResolved
    : null;
  const sessionPath = typeof state.chatSessionPath === "string" && state.chatSessionPath
    ? state.chatSessionPath
    : null;
  const base = resolved || sessionPath || `out/editor_sessions/${sessionId}`;
  return `${base.replace(/\/$/, "")}/turns/`;
}

function sessionArtifactPathNoteForReport(panel) {
  const state = panel?.state || {};
  if (typeof state.chatSessionPathResolved === "string" && state.chatSessionPathResolved) {
    return null;
  }
  return "If that path is relative, resolve it from the running ComfyUI checkout, not necessarily from the VibeComfy repo.";
}

/**
 * Persist session artifact paths from an agent-edit response onto the panel state.
 * Call AFTER a successful submit/accept/rebaseline/rehydrate to keep diagnostics
 * pointing at the right on-disk turn directories.
 */
export function commitSessionArtifactPathsFromResponse(panel, result) {
  if (!panel?.state || !result || typeof result !== "object") {
    return;
  }
  if (typeof result.sessionPath === "string" && result.sessionPath) {
    panel.state.chatSessionPath = result.sessionPath;
  }
  if (typeof result.detailJsonPath === "string" && result.detailJsonPath) {
    panel.state.chatDetailJsonPath = result.detailJsonPath;
  }
  if (typeof result.sessionPathResolved === "string" && result.sessionPathResolved) {
    panel.state.chatSessionPathResolved = result.sessionPathResolved;
  }
  if (typeof result.detailJsonPathResolved === "string" && result.detailJsonPathResolved) {
    panel.state.chatDetailJsonPathResolved = result.detailJsonPathResolved;
  }
}

// ── Exported issue-report builders ──────────────────────────────────────────

export function buildIssueReport(panel) {
  const debug = debugSnapshotForReport(panel);
  const sessionId = panel?.state?.sessionId || debug.sessionId || "(none)";
  const phase = panel?.state?.phase || debug.phase || "(unknown)";
  const summaries = collectRecentTurnSummaries(panel, ISSUE_REPORT_TURN_LIMIT);
  const artifactPath = sessionArtifactPathForReport(panel, sessionId);
  const artifactPathNote = sessionArtifactPathNoteForReport(panel);
  return [
    "VibeComfy agent-edit issue report",
    "",
    "I ran into a problem while using the VibeComfy ComfyUI agent-edit tool. Here is the browser-panel context that may help reproduce or diagnose it.",
    "",
    `Page URL: ${pageUrlForReport()}`,
    `Panel session id: ${sessionId}`,
    `Panel phase: ${phase}`,
    `Panel id: ${debug.panelId || panel?.panelId || "(unknown)"}`,
    `Current turn id: ${panel?.state?.turnId || debug.turnId || "(none)"}`,
    `Message count: ${debug.messageCount ?? "(unknown)"}`,
    `Render errors: ${Array.isArray(debug.renderErrors) ? debug.renderErrors.length : (debug.renderErrors ?? 0)}`,
    "",
    "Last turns:",
    formatTurnSummaries(summaries),
    "",
    `Full per-turn artifacts (the agent's actual step-by-step reasoning, the code it tried, and the engine diagnostics) are under: ${artifactPath}<NNNN>/ — see messages.jsonl, model_response.json, and response.json in each turn dir.`,
    artifactPathNote,
  ].filter(Boolean).join("\n");
}

export function buildAgentSolvePrompt(panel) {
  const debug = debugSnapshotForReport(panel);
  const sessionId = panel?.state?.sessionId || debug.sessionId || "(unknown-session)";
  const phase = panel?.state?.phase || debug.phase || "(unknown)";
  const summaries = collectRecentTurnSummaries(panel, AGENT_SOLVE_TURN_LIMIT);
  const artifactPath = sessionArtifactPathForReport(panel, sessionId);
  const artifactPathNote = sessionArtifactPathNoteForReport(panel);
  return [
    "Can you spot what's going wrong here?",
    "",
    "I'm using the VibeComfy ComfyUI agent-edit tool.",
    `Here's the page URL: ${pageUrlForReport()}`,
    `Panel session id: ${sessionId}`,
    `Panel phase: ${phase}`,
    `Current turn id: ${panel?.state?.turnId || debug.turnId || "(none)"}`,
    "",
    "Here are the logs from my last 2 turns:",
    formatTurnSummaries(summaries),
    "",
    "The tool's code lives at /Users/peteromalley/Documents/reigh-workspace/vibecomfy.",
    "Browser panel code is under vibecomfy/comfy_nodes/web/.",
    "Server code is under vibecomfy/comfy_nodes/agent/.",
    `Turn artifacts are under ${artifactPath}`,
    artifactPathNote,
    "Each numbered turn dir holds the agent's ACTUAL reasoning — read these, not",
    "just the summary above:",
    "  - messages.jsonl: the per-step transcript — each line has the agent's",
    "    `message` (its reasoning), the `batch` (the code it tried), and the",
    "    engine's `report`/`diagnostics` (why each statement landed or was",
    "    rejected, including the valid enum `choices` / `available_slots`).",
    "  - model_response.json / model_request.json: the raw model reply and the",
    "    prompt it was given.",
    "  - response.json: the final outcome envelope (failure_kind, user_facing_message).",
    "The single most useful thing you can do is read messages.jsonl for the failing",
    "turn and trace what the agent believed vs. what the engine actually allowed.",
    "",
    "Please diagnose the failure and propose a fix. Don't settle for a superficial",
    "patch that just makes the symptom go away — get to the very root of the issue.",
    "Keep digging until you genuinely understand the foundational problem (why it",
    "happens, not just where it surfaces), and then fix that underlying cause.",
    "",
    "Once you have a fix, test it yourself in the browser, or with me, to confirm it",
    "actually resolves the problem. When you're confident it's fixed and verified,",
    "offer to open a pull request against the original repo",
    "(https://github.com/peteromallet/VibeComfy) so the fix helps everyone.",
  ].join("\n");
}

// ── Audit download helpers ─────────────────────────────────────────────────

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

export function downloadTurnAudit(panel, turnIndex) {
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
  const downloadBlob = _deps.downloadBlob;
  if (typeof downloadBlob === "function") {
    downloadBlob(blob, `vibecomfy-audit-${status}-${turnId}.json`);
  }
}

export function downloadTurnAuditEntry(turnEntry, turnIndex = 0) {
  if (!turnEntry) {
    return;
  }
  const envelope = buildAuditEnvelope(turnEntry);
  const blob = new Blob([JSON.stringify(envelope, null, 2)], {
    type: "application/json",
  });
  const turnId = turnEntry.turn_id || turnEntry.parent_turn_id || `turn-${turnIndex}`;
  const status = turnEntry.status || "unknown";
  const downloadBlob = _deps.downloadBlob;
  if (typeof downloadBlob === "function") {
    downloadBlob(blob, `vibecomfy-audit-${status}-${turnId}.json`);
  }
}

export function buildCurrentAuditEnvelope(panel) {
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
  return envelope;
}

export function downloadCurrentAudit(panel) {
  if (!panel) {
    return;
  }
  const envelope = buildCurrentAuditEnvelope(panel);
  const blob = new Blob([JSON.stringify(envelope, null, 2)], {
    type: "application/json",
  });
  const turnId = panel.state.turnId || "current";
  const status = panel.state.phase || "unknown";
  const downloadBlob = _deps.downloadBlob;
  if (typeof downloadBlob === "function") {
    downloadBlob(blob, `vibecomfy-audit-${status}-${turnId}.json`);
  }
}

// ── Minimal stored-mode ZIP writer (no external deps) ──────────────────────

let _crc32Table = null;
function crc32(bytes) {
  if (!_crc32Table) {
    _crc32Table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      _crc32Table[n] = c >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) {
    crc = _crc32Table[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

// Build an uncompressed (stored) ZIP archive from [{ name, text }] entries.
function buildZipBlob(files) {
  const encoder = new TextEncoder();
  const u16 = (n) => new Uint8Array([n & 0xff, (n >>> 8) & 0xff]);
  const u32 = (n) => new Uint8Array([
    n & 0xff,
    (n >>> 8) & 0xff,
    (n >>> 16) & 0xff,
    (n >>> 24) & 0xff,
  ]);

  const localParts = [];
  const centralParts = [];
  let offset = 0;
  let entryCount = 0;

  for (const file of files) {
    const nameBytes = encoder.encode(file.name);
    const dataBytes = file.bytes instanceof Uint8Array
      ? file.bytes
      : encoder.encode(String(file.text ?? ""));
    const crc = crc32(dataBytes);
    const size = dataBytes.length;

    // Local file header (30 bytes + name) then data.
    localParts.push(
      u32(0x04034b50), u16(20), u16(0), u16(0), u16(0), u16(0),
      u32(crc), u32(size), u32(size), u16(nameBytes.length), u16(0),
      nameBytes, dataBytes,
    );

    // Central directory header (46 bytes + name).
    centralParts.push(
      u32(0x02014b50), u16(20), u16(20), u16(0), u16(0), u16(0), u16(0),
      u32(crc), u32(size), u32(size), u16(nameBytes.length), u16(0), u16(0),
      u16(0), u16(0), u32(0), u32(offset), nameBytes,
    );

    offset += 30 + nameBytes.length + size;
    entryCount += 1;
  }

  const centralStart = offset;
  let centralSize = 0;
  for (const part of centralParts) centralSize += part.length;

  const endParts = [
    u32(0x06054b50), u16(0), u16(0), u16(entryCount), u16(entryCount),
    u32(centralSize), u32(centralStart), u16(0),
  ];

  return new Blob([...localParts, ...centralParts, ...endParts], {
    type: "application/zip",
  });
}

function _base64ToBytes(b64) {
  // Guard: atob is only available in browser contexts
  if (typeof atob !== "function") {
    throw new Error("atob is not available — binary ZIP entries require a browser environment");
  }
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function _formatBundleBytes(n) {
  if (!Number.isFinite(n)) {
    return "?";
  }
  if (n < 1024) {
    return `${n} B`;
  }
  if (n < 1024 * 1024) {
    return `${(n / 1024).toFixed(1)} KiB`;
  }
  return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
}

// Fetch every artifact under the session dir and add it to the ZIP under
// `session/`, so the downloaded report is self-contained — a recipient on
// another machine gets the actual messages.jsonl / model_response.json /
// response.json etc., not just local paths pointing at files they don't have.
async function appendSessionBundleFiles(panel, files) {
  const sessionId = panel?.state?.sessionId || null;
  if (!sessionId) {
    files.push({ name: "session/_bundle_missing.txt", text: "No session id on the panel; turn artifacts were not bundled." });
    return;
  }
  // Guard: fetch is a browser/Node global; degrade gracefully when absent.
  if (typeof fetch !== "function") {
    files.push({
      name: "session/_bundle_error.txt",
      text: "fetch is not available — session artifacts were not bundled (non-browser environment).",
    });
    return;
  }
  let payload;
  try {
    const res = await fetch(`/vibecomfy/agent-edit/session-bundle?session_id=${encodeURIComponent(sessionId)}`);
    if (!res.ok) {
      throw new Error(`session-bundle returned ${res.status}`);
    }
    payload = await res.json();
  } catch (error) {
    files.push({
      name: "session/_bundle_error.txt",
      text: `Failed to fetch session artifacts: ${String(error?.message || error)}\n`
        + "The report above still points at the on-disk turn artifacts.",
    });
    return;
  }
  if (payload?.ok === false || payload?.exists === false) {
    files.push({
      name: "session/_bundle_missing.txt",
      text: `No on-disk artifacts found for session ${sessionId} (exists=${payload?.exists}).`,
    });
    return;
  }
  const bundleFiles = Array.isArray(payload?.files) ? payload.files : [];
  let added = 0;
  for (const entry of bundleFiles) {
    if (!entry || typeof entry.name !== "string") {
      continue;
    }
    const name = `session/${entry.name}`;
    if (typeof entry.text === "string") {
      files.push({ name, text: entry.text });
      added += 1;
    } else if (typeof entry.base64 === "string") {
      try {
        files.push({ name, bytes: _base64ToBytes(entry.base64) });
        added += 1;
      } catch (_error) {
        // Skip an undecodable binary blob rather than abort the whole ZIP.
      }
    }
  }
  const skipped = Array.isArray(payload?.skipped) ? payload.skipped : [];
  const manifest = [
    "VibeComfy session artifact bundle",
    "",
    `Session: ${sessionId}`,
    `Session path: ${payload?.session_path || "(unknown)"}`,
    `Files bundled: ${added}`,
    `Total bytes: ${_formatBundleBytes(payload?.total_bytes)}`,
    "",
    "These files under session/ are the agent's actual turn artifacts — the same",
    "messages.jsonl / model_response.json / response.json the report.txt points to,",
    "copied here so this ZIP is self-contained.",
  ];
  if (skipped.length) {
    manifest.push("", "Skipped (not bundled):");
    for (const item of skipped) {
      manifest.push(`  - ${item?.name || "(unknown)"}: ${item?.reason || "?"}${item?.size ? ` (${_formatBundleBytes(item.size)})` : ""}`);
    }
  }
  files.push({ name: "session/_bundle_manifest.txt", text: manifest.join("\n") });
}

export async function collectIssueReportFiles(panel) {
  const files = [{ name: "report.txt", text: buildIssueReport(panel) }];
  try {
    const envelope = buildCurrentAuditEnvelope(panel);
    files.push({ name: "audit.json", text: JSON.stringify(envelope, null, 2) });
  } catch (error) {
    files.push({ name: "audit-error.txt", text: String(error?.stack || error) });
  }
  try {
    const buildSnapshot = _deps.buildAgentPanelDebugSnapshot;
    if (typeof buildSnapshot === "function") {
      const snapshot = buildSnapshot(panel);
      files.push({ name: "debug-snapshot.json", text: JSON.stringify(snapshot, null, 2) });
    }
  } catch (error) {
    files.push({ name: "debug-snapshot-error.txt", text: String(error?.stack || error) });
  }
  // Also embed the agent-solve prompt so a recipient has the framed ask too.
  try {
    files.push({ name: "coding-agent-prompt.txt", text: buildAgentSolvePrompt(panel) });
  } catch (error) {
    files.push({ name: "coding-agent-prompt-error.txt", text: String(error?.stack || error) });
  }
  await appendSessionBundleFiles(panel, files);
  return files;
}

export async function downloadIssueReportZip(panel) {
  const blob = buildZipBlob(await collectIssueReportFiles(panel));
  const sessionId = panel?.state?.sessionId || "session";
  const safeSession = String(sessionId).replace(/[^a-zA-Z0-9_-]+/g, "-").slice(0, 60);
  const downloadBlob = _deps.downloadBlob;
  if (typeof downloadBlob === "function") {
    downloadBlob(blob, `vibecomfy-issue-report-${safeSession}.zip`);
  }
}

// ── Clipboard helper ────────────────────────────────────────────────────────

async function copyTextToClipboard(text) {
  // Guard: navigator.clipboard is a browser API.
  if (
    typeof navigator !== "undefined"
    && navigator.clipboard
    && typeof navigator.clipboard.writeText === "function"
  ) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  if (typeof document === "undefined" || typeof document.createElement !== "function") {
    return false;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  const parent = document.body || null;
  if (!parent || typeof parent.appendChild !== "function") {
    return false;
  }
  parent.appendChild(textarea);
  if (typeof textarea.focus === "function") {
    textarea.focus();
  }
  if (typeof textarea.select === "function") {
    textarea.select();
  }
  let ok = false;
  try {
    ok = typeof document.execCommand === "function" && document.execCommand("copy");
  } finally {
    textarea.remove();
  }
  return ok;
}

// ── Issue modal option card (used inside showIssueModal) ────────────────────

function issueModalOption({ title, copyLabel, description, onCopy, link, statusNode }) {
  const el = _deps.el;
  const button = _deps.button;
  const setButtonEmphasis = _deps.setButtonEmphasis;
  if (typeof el !== "function") {
    return null;
  }

  const optionBox = el("div");
  Object.assign(optionBox.style, {
    border: "1px solid #2a313c",
    borderRadius: "8px",
    background: "#0d0f14",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    minWidth: "0",
  });

  const heading = el("div", title);
  Object.assign(heading.style, {
    color: "#edf2f7",
    fontSize: "13px",
    fontWeight: "700",
  });
  optionBox.appendChild(heading);

  const body = el("div", description);
  Object.assign(body.style, {
    color: "#9da1ac",
    fontSize: "11px",
    lineHeight: "1.45",
  });
  optionBox.appendChild(body);

  const actions = el("div");
  Object.assign(actions.style, {
    display: "flex",
    flexWrap: "nowrap",
    alignItems: "center",
    gap: "12px",
  });

  const copyBtn = typeof button === "function"
    ? button(copyLabel, onCopy)
    : el("button", copyLabel);
  if (typeof button === "function" && copyBtn && typeof setButtonEmphasis === "function") {
    setButtonEmphasis(copyBtn, true, "neutral");
  }
  Object.assign(copyBtn.style, {
    fontSize: "11px",
    padding: "6px 9px",
  });
  actions.appendChild(copyBtn);

  if (link && link.href) {
    const iconOnly = link.iconOnly === true;
    const linkEl = el("a", iconOnly ? null : `${link.label || "File an issue"} ↗`);
    linkEl.href = link.href;
    linkEl.target = "_blank";
    linkEl.rel = "noopener noreferrer";
    linkEl.title = link.title || link.label || link.href;
    if (iconOnly) {
      linkEl.innerHTML = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path></svg>';
      Object.assign(linkEl.style, {
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#edf2f7",
        textDecoration: "none",
        border: "1px solid #414855",
        borderRadius: "6px",
        background: "#272b33",
        padding: "6px 9px",
        whiteSpace: "nowrap",
      });
    } else {
      Object.assign(linkEl.style, {
        fontSize: "11px",
        color: "#9ed0ff",
        textDecoration: "none",
        whiteSpace: "nowrap",
      });
    }
    actions.appendChild(linkEl);
  }

  optionBox.appendChild(actions);

  if (statusNode) {
    optionBox.appendChild(statusNode);
  }

  return optionBox;
}

// ── "Having issues?" modal ──────────────────────────────────────────────────

export function showIssueModal(panel) {
  const el = _deps.el;
  const button = _deps.button;
  const PANEL_IDS = _deps.PANEL_IDS;
  const getPanelElementById = _deps.getPanelElementById;

  if (!panel?.shell || typeof document === "undefined") {
    return null;
  }
  if (typeof el !== "function") {
    return null;
  }

  const existing = typeof getPanelElementById === "function" && PANEL_IDS
    ? getPanelElementById(panel, PANEL_IDS.issueModal)
    : null;
  if (existing && typeof existing.remove === "function") {
    existing.remove();
  }

  const overlay = el("div");
  if (PANEL_IDS) {
    overlay.id = PANEL_IDS.issueModal;
  }
  overlay.dataset.vibecomfyIssueModal = "1";
  Object.assign(overlay.style, {
    position: "absolute",
    inset: "0",
    zIndex: "10001",
    background: "rgba(0,0,0,0.58)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "16px",
    boxSizing: "border-box",
  });

  const closeModal = () => {
    if (typeof document.removeEventListener === "function") {
      document.removeEventListener("keydown", onKeyDown);
    }
    overlay.remove();
  };
  const onKeyDown = (event) => {
    if (event?.key === "Escape") {
      closeModal();
    }
  };
  overlay.onclick = (event) => {
    if (event?.target === overlay) {
      closeModal();
    }
  };
  if (typeof document.addEventListener === "function") {
    document.addEventListener("keydown", onKeyDown);
  }

  const modal = el("div");
  Object.assign(modal.style, {
    width: "min(720px, 100%)",
    maxHeight: "calc(100vh - 48px)",
    overflow: "auto",
    background: "#14161b",
    border: "1px solid #343b47",
    borderRadius: "8px",
    boxShadow: "0 14px 42px rgba(0,0,0,0.55)",
    padding: "14px",
    color: "#edf2f7",
    fontFamily: "monospace",
    boxSizing: "border-box",
  });
  overlay.appendChild(modal);

  const header = el("div");
  Object.assign(header.style, {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "12px",
  });
  const title = el("div", "Having issues?");
  Object.assign(title.style, {
    fontSize: "14px",
    fontWeight: "700",
  });
  header.appendChild(title);
  const closeBtn = typeof button === "function"
    ? button("X", closeModal)
    : el("button", "X");
  if (typeof button === "function") {
    closeBtn.title = "Close";
    Object.assign(closeBtn.style, {
      width: "28px",
      height: "28px",
      padding: "0",
      fontSize: "13px",
      lineHeight: "1",
    });
  }
  header.appendChild(closeBtn);
  modal.appendChild(header);

  const status = el("div");
  Object.assign(status.style, {
    minHeight: "14px",
    color: "#9ed0ff",
    fontSize: "11px",
    marginTop: "12px",
    padding: "0 2px",
  });

  const copyAndConfirm = async (builder) => {
    const text = builder(panel);
    try {
      const ok = await copyTextToClipboard(text);
      status.textContent = ok ? "Copied!" : "Copy failed. Select and copy the generated text manually.";
      status.style.color = ok ? "#9ed0ff" : "#ffb86c";
    } catch (error) {
      status.textContent = `Copy failed: ${String(error?.message || error)}`;
      status.style.color = "#ffb86c";
    }
  };

  const downloadReportAndCopyIntro = async () => {
    try {
      await downloadIssueReportZip(panel);
    } catch (error) {
      status.textContent = `Download failed: ${String(error?.message || error)}`;
      status.style.color = "#ffb86c";
      return;
    }
    try {
      await copyTextToClipboard(buildIssueReport(panel));
    } catch (_) {
      // Clipboard copy is best-effort; the zip download is the primary action.
    }
    status.textContent = "";
    status.appendChild(document.createTextNode("Please share this "));
    const githubLink = el("a", "on Github");
    githubLink.href = "https://github.com/peteromallet/VibeComfy/issues/new";
    githubLink.target = "_blank";
    githubLink.rel = "noopener noreferrer";
    Object.assign(githubLink.style, {
      color: "#9ed0ff",
      textDecoration: "underline",
    });
    status.appendChild(githubLink);
    status.appendChild(document.createTextNode(". Intro text also copied to your clipboard."));
    status.style.color = "#9ed0ff";
  };

  const options = el("div");
  Object.assign(options.style, {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "10px",
  });
  options.appendChild(issueModalOption({
    title: "Report an issue",
    description: "Found a bug? Download a ready-to-share report (zip) of what's happening so you can file it or send it to us.",
    copyLabel: "Download report",
    onCopy: downloadReportAndCopyIntro,
    link: {
      href: "https://github.com/peteromallet/VibeComfy/issues/new",
      title: "File a GitHub issue",
      iconOnly: true,
    },
  }));
  options.appendChild(issueModalOption({
    title: "Solve it",
    description: "Copy this for your coding agent — it'll work with you to get to the bottom of the issue and solve it, for you and others!",
    copyLabel: "Copy for your coding agent",
    onCopy: () => copyAndConfirm(buildAgentSolvePrompt),
  }));
  modal.appendChild(options);
  modal.appendChild(status);

  panel.shell.appendChild(overlay);
  return overlay;
}

// ── submitRating ────────────────────────────────────────────────────────────

/**
 * Submit a user rating for an agent response to the backend.
 *
 * Expected payload shape:
 *   { rating: number (1-10), comment: string|null, pack_shared: boolean,
 *     pack_comment: string|null, response_id: string, session_id: string,
 *     turn_id: string }
 *
 * Returns { ok: boolean, ... } or { ok: false, error: string } on failure.
 */
function _bytesToBase64(bytes) {
  // Browser-safe base64 encoding; degrades to an empty string when btoa is missing.
  if (typeof btoa !== "function") {
    return "";
  }
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

async function _zipBlobToBase64(blob) {
  const buffer = await blob.arrayBuffer();
  return _bytesToBase64(new Uint8Array(buffer));
}

export async function submitRating(panel, options = {}) {
  if (typeof fetch !== "function") {
    return { ok: false, error: "fetch unavailable — rating requires a browser or Node 18+ environment" };
  }

  const sessionId = panel?.state?.sessionId ?? options?.session_id ?? null;
  const turnId = panel?.state?.turnId ?? options?.turn_id ?? null;

  if (!sessionId || typeof sessionId !== "string") {
    return { ok: false, error: "validation", detail: "Missing session_id" };
  }
  if (!turnId || typeof turnId !== "string") {
    return { ok: false, error: "validation", detail: "Missing turn_id" };
  }

  const rating = Number(options?.rating ?? options?.rating_value);
  if (!Number.isFinite(rating) || rating < 1 || rating > 10) {
    return { ok: false, error: "validation", detail: "Rating must be an integer between 1 and 10" };
  }

  const comment = options?.comment ?? options?.rating_comment ?? null;
  const packShared = Boolean(options?.pack_shared ?? options?.packShared);
  const packComment = options?.pack_comment ?? options?.packComment ?? null;
  const maxZipBytes = Number.isFinite(options?.maxZipBytes) ? options.maxZipBytes : 2 * 1024 * 1024;

  const payload = {
    response_id: `${sessionId}/${turnId}`,
    session_id: sessionId,
    turn_id: turnId,
    rating: Math.round(rating),
    comment: comment == null ? null : String(comment),
    pack_shared: packShared,
    pack_comment: packComment == null ? null : String(packComment),
  };

  if (packShared) {
    try {
      const bundleFiles = [];
      await appendSessionBundleFiles(panel, bundleFiles);
      const zipBlob = buildZipBlob(bundleFiles);
      const zipBuffer = await zipBlob.arrayBuffer();
      if (zipBuffer.byteLength > maxZipBytes) {
        return {
          ok: false,
          error: "pack_too_large",
          detail: `Debug pack is ${_formatBundleBytes(zipBuffer.byteLength)}; limit is ${_formatBundleBytes(maxZipBytes)}`,
        };
      }
      payload.pack_zip_base64 = _bytesToBase64(new Uint8Array(zipBuffer));
    } catch (error) {
      return { ok: false, error: "pack_build_failed", detail: String(error?.message || error) };
    }
  }

  try {
    const res = await fetch("/vibecomfy/agent-edit/rating", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return { ok: false, error: `Server returned ${res.status}${text ? `: ${text}` : ""}` };
    }
    return await res.json();
  } catch (error) {
    return { ok: false, error: String(error?.message || error) };
  }
}

// ── installBrowserDiagnosticsCapture ────────────────────────────────────────

/**
 * Install global browser error/unhandled-rejection capture that feeds into
 * the panel debug snapshot for richer diagnostics reports.
 *
 * Stores captured errors on `panel.__diagnosticsCapture` so they surface in
 * debug snapshots and issue-report zip downloads.
 *
 * Safe to call multiple times — subsequent calls are no-ops if already installed.
 */
export function installBrowserDiagnosticsCapture(panel) {
  if (!panel) {
    return;
  }
  // Ensure a capture bucket exists on the panel.
  if (!Array.isArray(panel.__diagnosticsCapture)) {
    panel.__diagnosticsCapture = [];
  }

  // Avoid double-installing on the same panel instance.
  if (panel.__diagnosticsCaptureInstalled) {
    return;
  }
  panel.__diagnosticsCaptureInstalled = true;

  // Guard: only install in browser contexts.
  if (typeof window === "undefined") {
    return;
  }

  const capture = (entry) => {
    if (!Array.isArray(panel.__diagnosticsCapture)) {
      panel.__diagnosticsCapture = [];
    }
    // Cap at 50 entries to avoid unbounded memory growth.
    if (panel.__diagnosticsCapture.length >= 50) {
      panel.__diagnosticsCapture.shift();
    }
    panel.__diagnosticsCapture.push(entry);
  };

  // Hook into window.onerror if not already captured by another handler.
  const prevOnError = window.onerror;
  window.onerror = function diagnosticsOnError(message, source, lineno, colno, error) {
    capture({
      kind: "window.onerror",
      message: typeof message === "string" ? message : String(message),
      source: typeof source === "string" ? source : null,
      lineno: Number.isFinite(lineno) ? lineno : null,
      colno: Number.isFinite(colno) ? colno : null,
      stack: error && typeof error.stack === "string" ? error.stack : null,
      timestamp: new Date().toISOString(),
    });
    // Chain to the previous handler if one existed.
    if (typeof prevOnError === "function") {
      return prevOnError.apply(this, arguments);
    }
    return false;
  };

  // Hook into unhandledrejection.
  const prevUnhandledRejection = window.onunhandledrejection;
  window.addEventListener("unhandledrejection", function diagnosticsUnhandledRejection(event) {
    capture({
      kind: "unhandledrejection",
      reason: event?.reason ? (typeof event.reason === "string" ? event.reason : String(event.reason?.message || event.reason)) : null,
      stack: event?.reason && typeof event.reason?.stack === "string" ? event.reason.stack : null,
      timestamp: new Date().toISOString(),
    });
  });
  // Also call the previous handler if it was set on the property.
  if (typeof prevUnhandledRejection === "function") {
    window.addEventListener("unhandledrejection", prevUnhandledRejection);
  }
}

// ── Configuration helper ────────────────────────────────────────────────────

/**
 * Return an object whose keys are the pre-bound diagnostics functions wired
 * with the current deps. Useful when the monolith wants to re-export these
 * under its own names with dependency closure already applied.
 */
export function configureDiagnosticsBindings() {
  return {
    buildIssueReport,
    buildAgentSolvePrompt,
    buildCurrentAuditEnvelope,
    downloadCurrentAudit,
    collectIssueReportFiles,
    downloadIssueReportZip,
    showIssueModal,
    submitRating,
    installBrowserDiagnosticsCapture,
    commitSessionArtifactPathsFromResponse,
    downloadTurnAudit,
    downloadTurnAuditEntry,
  };
}
