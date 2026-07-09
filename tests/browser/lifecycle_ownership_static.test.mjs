import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

const previewSource = source("preview_picker.js");
const replaySource = source("agentic_replay.js");
const lifecycleSource = source("agent_edit_lifecycle.js");
const roundtripSource = source("vibecomfy_roundtrip.js");

// ── Forbidden patterns ─────────────────────────────────────────────────────
// These patterns indicate that a module is directly mutating lifecycle state
// outside the `transition(...)` reducer. After the migration, preview and
// replay modules must route through `agent_lifecycle_commit.js` helpers.

const FORBIDDEN_PATTERNS = [
  {
    name: "Object.assign(panel.state",
    pattern: /Object\.assign\(\s*\w*panel\w*\.state\b/,
    message: "must not use Object.assign on panel.state",
  },
  {
    name: "Object.assign(currentPanel.state",
    pattern: /Object\.assign\(\s*currentPanel\.state\b/,
    message: "must not use Object.assign on currentPanel.state",
  },
  {
    name: "direct .state. assignment on lifecycle fields",
    pattern: /\.state\.(phase|sessionId|turnId|baselineTurnId|baselineGraphHash|candidateGraph|candidateBaselineGraph|candidateGraphHash|candidateReport|candidateScopeId|serverSubmitGraphHash|customNodeResolution|applyAllowed|applyEligibility|applyEligibilityWarning|applyEligibilityWarningKey|queueAllowed|canvasApplyAllowed|message|failure|clarification|lastSubmit|lastAppliedChanges|lastSubmitFieldChanges|changeDetails|deltaOps|transcriptMessages|responseDetails|executionEvents|auditArtifacts|debugDiagnostics|compartmentIndexes|chatRehydrateEpoch|chatRehydrateCommittedEpoch|syntheticAgentMessage|inFlightSubmit|submitAbortController|submitEpoch|submitStartedAtMs|submitDeadlineMs|inFlightApply|inFlightRebaseline|rebaselinePending|rebaselineRecovery|auditRef|debugPayload|nodePackInstallStates|chatScopeId|chatScopeFingerprint|submittingScopeId|baselineGraphHashKind|baselineGraphHashVersion|baselineSource|baselineRebaselineId|baselineGraphSourcePath)\s*=/,
    message: "must not directly assign to lifecycle-owned state fields",
  },
];

const LIFECYCLE_OWNED_FIELDS = [
  "phase", "sessionId", "turnId",
  "chatScopeId", "chatScopeFingerprint", "candidateScopeId", "submittingScopeId",
  "baselineTurnId", "baselineGraphHash", "baselineGraphHashKind",
  "baselineGraphHashVersion", "baselineSource", "baselineRebaselineId",
  "baselineGraphSourcePath",
  "candidateGraph", "candidateBaselineGraph", "candidateGraphHash", "candidateReport",
  "serverSubmitGraphHash", "customNodeResolution", "nodePackInstallStates",
  "message", "failure", "clarification",
  "applyAllowed", "applyEligibility", "applyEligibilityWarning", "applyEligibilityWarningKey",
  "queueAllowed", "canvasApplyAllowed",
  "auditRef", "debugPayload",
  "inFlightSubmit", "submitAbortController", "submitEpoch", "submitStartedAtMs", "submitDeadlineMs",
  "inFlightApply", "inFlightRebaseline",
  "rebaselinePending", "rebaselineRecovery",
  "lastSubmit", "lastAppliedChanges", "lastSubmitFieldChanges", "changeDetails",
  "transcriptMessages", "responseDetails", "executionEvents",
  "auditArtifacts", "debugDiagnostics", "compartmentIndexes",
  "chatRehydrateEpoch", "chatRehydrateCommittedEpoch",
  "syntheticAgentMessage", "deltaOps",
];

// ── Tests ───────────────────────────────────────────────────────────────────

test("preview_picker.js must not use Object.assign on panel.state", () => {
  assert.doesNotMatch(
    previewSource,
    /Object\.assign\(\s*\w*[Pp]anel\w*\.state\b/,
    "preview_picker.js must not use Object.assign on panel.state",
  );
});

test("agentic_replay.js must not use Object.assign on panel.state", () => {
  assert.doesNotMatch(
    replaySource,
    /Object\.assign\(\s*\w*[Pp]anel\w*\.state\b/,
    "agentic_replay.js must not use Object.assign on panel.state",
  );
});

test("preview_picker.js must not directly assign to lifecycle-owned state fields", () => {
  for (const field of LIFECYCLE_OWNED_FIELDS) {
    const pattern = new RegExp(
      String.raw`\.state\.${field}\s*=\s*`,
    );
    const hasDirectWrite = pattern.test(previewSource);
    if (hasDirectWrite) {
      assert.equal(
        hasDirectWrite,
        false,
        `preview_picker.js must not directly assign to lifecycle field .state.${field}`,
      );
    }
  }
});

test("agentic_replay.js must not directly assign to lifecycle-owned state fields", () => {
  for (const field of LIFECYCLE_OWNED_FIELDS) {
    const pattern = new RegExp(
      String.raw`\.state\.${field}\s*=\s*`,
    );
    const hasDirectWrite = pattern.test(replaySource);
    if (hasDirectWrite) {
      assert.equal(
        hasDirectWrite,
        false,
        `agentic_replay.js must not directly assign to lifecycle field .state.${field}`,
      );
    }
  }
});

test("preview_picker.js must not create lifecycle state via createAgentEditState", () => {
  // Preview/replay modules should not create their own lifecycle state;
  // that's the panel's responsibility. They should only commit through helpers.
  assert.doesNotMatch(
    previewSource,
    /\bcreateAgentEditState\b/,
    "preview_picker.js must not call createAgentEditState",
  );
});

test("agentic_replay.js must not create lifecycle state via createAgentEditState", () => {
  assert.doesNotMatch(
    replaySource,
    /\bcreateAgentEditState\b/,
    "agentic_replay.js must not call createAgentEditState",
  );
});

test("preview_picker.js must not reference invalid RENDER_SECTIONS.CANDIDATE", () => {
  // RENDER_SECTIONS does not include a CANDIDATE section. Using a nonexistent
  // section in dirtySections would be silently ignored by the render gateway.
  assert.doesNotMatch(
    previewSource,
    /RENDER_SECTIONS\.CANDIDATE\b/,
    "preview_picker.js must not reference nonexistent RENDER_SECTIONS.CANDIDATE",
  );
});

test("agentic_replay.js must not reference invalid RENDER_SECTIONS.CANDIDATE", () => {
  assert.doesNotMatch(
    replaySource,
    /RENDER_SECTIONS\.CANDIDATE\b/,
    "agentic_replay.js must not reference nonexistent RENDER_SECTIONS.CANDIDATE",
  );
});

test("preview_picker.js only references valid RENDER_SECTIONS values", () => {
  // Extract all RENDER_SECTIONS.* references and verify they're valid
  const matches = previewSource.matchAll(/RENDER_SECTIONS\.(\w+)\b/g);
  const validSections = new Set(["META", "THREAD", "COMPOSER", "NOTICE", "SETTINGS", "DEVELOPER"]);
  for (const match of matches) {
    const section = match[1];
    assert.ok(
      validSections.has(section),
      `preview_picker.js references invalid RENDER_SECTIONS.${section}`,
    );
  }
});

test("agentic_replay.js only references valid RENDER_SECTIONS values", () => {
  const matches = replaySource.matchAll(/RENDER_SECTIONS\.(\w+)\b/g);
  const validSections = new Set(["META", "THREAD", "COMPOSER", "NOTICE", "SETTINGS", "DEVELOPER"]);
  for (const match of matches) {
    const section = match[1];
    assert.ok(
      validSections.has(section),
      `agentic_replay.js references invalid RENDER_SECTIONS.${section}`,
    );
  }
});

// ── Forbidden detail/transcript writes ──────────────────────────────────────

test("preview_picker.js must not directly write to transcriptMessages array", () => {
  // Direct writes like panel.state.transcriptMessages.push(...) or
  // panel.state.transcriptMessages = [...] bypass the lifecycle reducer.
  assert.doesNotMatch(
    previewSource,
    /\.state\.transcriptMessages\s*(?:=|\.push|\.unshift|\.splice)/,
    "preview_picker.js must not directly write to transcriptMessages",
  );
});

test("agentic_replay.js must not directly write to transcriptMessages array", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.transcriptMessages\s*(?:=|\.push|\.unshift|\.splice)/,
    "agentic_replay.js must not directly write to transcriptMessages",
  );
});

test("preview_picker.js must not directly write to responseDetails object", () => {
  assert.doesNotMatch(
    previewSource,
    /\.state\.responseDetails\s*(?:=|\.\w+\s*=)/,
    "preview_picker.js must not directly write to responseDetails",
  );
});

test("agentic_replay.js must not directly write to responseDetails object", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.responseDetails\s*(?:=|\.\w+\s*=)/,
    "agentic_replay.js must not directly write to responseDetails",
  );
});

test("preview_picker.js must not directly write to executionEvents array", () => {
  assert.doesNotMatch(
    previewSource,
    /\.state\.executionEvents\s*(?:=|\.push|\.unshift|\.splice)/,
    "preview_picker.js must not directly write to executionEvents",
  );
});

test("agentic_replay.js must not directly write to executionEvents array", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.executionEvents\s*(?:=|\.push|\.unshift|\.splice)/,
    "agentic_replay.js must not directly write to executionEvents",
  );
});

test("preview_picker.js must not directly write to auditArtifacts array", () => {
  assert.doesNotMatch(
    previewSource,
    /\.state\.auditArtifacts\s*(?:=|\.push|\.unshift|\.splice)/,
    "preview_picker.js must not directly write to auditArtifacts",
  );
});

test("agentic_replay.js must not directly write to auditArtifacts array", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.auditArtifacts\s*(?:=|\.push|\.unshift|\.splice)/,
    "agentic_replay.js must not directly write to auditArtifacts",
  );
});

test("preview_picker.js must not directly write to debugDiagnostics object", () => {
  assert.doesNotMatch(
    previewSource,
    /\.state\.debugDiagnostics\s*(?:=|\.\w+\s*=)/,
    "preview_picker.js must not directly write to debugDiagnostics",
  );
});

test("agentic_replay.js must not directly write to debugDiagnostics object", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.debugDiagnostics\s*(?:=|\.\w+\s*=)/,
    "agentic_replay.js must not directly write to debugDiagnostics",
  );
});

test("preview_picker.js must not directly write to compartmentIndexes object", () => {
  assert.doesNotMatch(
    previewSource,
    /\.state\.compartmentIndexes\s*(?:=|\.\w+\s*=)/,
    "preview_picker.js must not directly write to compartmentIndexes",
  );
});

test("agentic_replay.js must not directly write to compartmentIndexes object", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.compartmentIndexes\s*(?:=|\.\w+\s*=)/,
    "agentic_replay.js must not directly write to compartmentIndexes",
  );
});

// ── Expanded-detail guard: preview/replay must not write thread detail state ─

test("preview_picker.js must not directly set expanded detail state", () => {
  // The expanded detail state is managed by panel_thread.js, not preview/replay.
  assert.doesNotMatch(
    previewSource,
    /\.state\.(?:expandedDetail|_expanded|detailExpanded)/,
    "preview_picker.js must not write to expanded detail state",
  );
});

test("agentic_replay.js must not directly set expanded detail state", () => {
  assert.doesNotMatch(
    replaySource,
    /\.state\.(?:expandedDetail|_expanded|detailExpanded)/,
    "agentic_replay.js must not write to expanded detail state",
  );
});

// ── Verify that lifecycle.js does NOT contain CANDIDATE render section ─────

test("RENDER_SECTIONS does not contain a CANDIDATE entry", () => {
  const match = lifecycleSource.match(
    /export const RENDER_SECTIONS = Object\.freeze\(\{([\s\S]*?)\}\);/,
  );
  assert.ok(match, "RENDER_SECTIONS must be defined in agent_edit_lifecycle.js");
  assert.doesNotMatch(
    match[1],
    /\bCANDIDATE\b/,
    "RENDER_SECTIONS must not include CANDIDATE",
  );
});

// ── Summary guardrails ─────────────────────────────────────────────────────
// These tests prevent preview/replay modules from reintroducing lifecycle
// mutations that must flow through the reducer and commit helpers.

test("preview_picker.js must not reintroduce direct lifecycle writes", () => {
  const hasObjectAssign = /Object\.assign\(\s*\w*[Pp]anel\w*\.state\b/.test(previewSource);
  const hasCreateState = /\bcreateAgentEditState\b/.test(previewSource);

  const hasDirectFieldWrite = LIFECYCLE_OWNED_FIELDS.some((field) => {
    const pattern = new RegExp(String.raw`\.state\.${field}\s*=\s*`);
    return pattern.test(previewSource);
  });

  const hasTranscriptWrite = /\.state\.transcriptMessages\s*(?:=|\.push|\.unshift|\.splice)/.test(previewSource);
  const hasResponseDetailWrite = /\.state\.responseDetails\s*(?:=|\.\w+\s*=)/.test(previewSource);
  const hasExecutionEventWrite = /\.state\.executionEvents\s*(?:=|\.push|\.unshift|\.splice)/.test(previewSource);
  const hasAuditArtifactWrite = /\.state\.auditArtifacts\s*(?:=|\.push|\.unshift|\.splice)/.test(previewSource);
  const hasDebugDiagWrite = /\.state\.debugDiagnostics\s*(?:=|\.\w+\s*=)/.test(previewSource);
  const hasCompartmentWrite = /\.state\.compartmentIndexes\s*(?:=|\.\w+\s*=)/.test(previewSource);

  const anyForbidden = hasObjectAssign || hasCreateState || hasDirectFieldWrite
    || hasTranscriptWrite || hasResponseDetailWrite || hasExecutionEventWrite
    || hasAuditArtifactWrite || hasDebugDiagWrite || hasCompartmentWrite;

  assert.equal(
    anyForbidden,
    false,
    "preview_picker.js still contains forbidden lifecycle writes. "
      + `Object.assign=${hasObjectAssign} createState=${hasCreateState} `
      + `fieldWrite=${hasDirectFieldWrite} transcript=${hasTranscriptWrite} `
      + `responseDetail=${hasResponseDetailWrite} executionEvents=${hasExecutionEventWrite} `
      + `auditArtifacts=${hasAuditArtifactWrite} debugDiag=${hasDebugDiagWrite} `
      + `compartment=${hasCompartmentWrite}`,
  );
});

test("agentic_replay.js must not reintroduce direct lifecycle writes", () => {
  const hasObjectAssign = /Object\.assign\(\s*\w*[Pp]anel\w*\.state\b/.test(replaySource);
  const hasCreateState = /\bcreateAgentEditState\b/.test(replaySource);

  const hasDirectFieldWrite = LIFECYCLE_OWNED_FIELDS.some((field) => {
    const pattern = new RegExp(String.raw`\.state\.${field}\s*=\s*`);
    return pattern.test(replaySource);
  });

  const hasTranscriptWrite = /\.state\.transcriptMessages\s*(?:=|\.push|\.unshift|\.splice)/.test(replaySource);
  const hasResponseDetailWrite = /\.state\.responseDetails\s*(?:=|\.\w+\s*=)/.test(replaySource);
  const hasExecutionEventWrite = /\.state\.executionEvents\s*(?:=|\.push|\.unshift|\.splice)/.test(replaySource);
  const hasAuditArtifactWrite = /\.state\.auditArtifacts\s*(?:=|\.push|\.unshift|\.splice)/.test(replaySource);
  const hasDebugDiagWrite = /\.state\.debugDiagnostics\s*(?:=|\.\w+\s*=)/.test(replaySource);
  const hasCompartmentWrite = /\.state\.compartmentIndexes\s*(?:=|\.\w+\s*=)/.test(replaySource);

  const anyForbidden = hasObjectAssign || hasCreateState || hasDirectFieldWrite
    || hasTranscriptWrite || hasResponseDetailWrite || hasExecutionEventWrite
    || hasAuditArtifactWrite || hasDebugDiagWrite || hasCompartmentWrite;

  assert.equal(
    anyForbidden,
    false,
    "agentic_replay.js still contains forbidden lifecycle writes. "
      + `Object.assign=${hasObjectAssign} createState=${hasCreateState} `
      + `fieldWrite=${hasDirectFieldWrite} transcript=${hasTranscriptWrite} `
      + `responseDetail=${hasResponseDetailWrite} executionEvents=${hasExecutionEventWrite} `
      + `auditArtifacts=${hasAuditArtifactWrite} debugDiag=${hasDebugDiagWrite} `
      + `compartment=${hasCompartmentWrite}`,
  );
});

test("only the lifecycle reducer deletes transient preview diff state", () => {
  for (const [name, moduleSource] of [
    ["preview_picker.js", previewSource],
    ["agentic_replay.js", replaySource],
    ["vibecomfy_roundtrip.js", roundtripSource],
  ]) {
    assert.doesNotMatch(
      moduleSource,
      /delete\s+[^;\n]*\.state\._previewDiff(?:GraphHash|CacheTag)?\b/,
      `${name} must not clear _previewDiff* directly; use lifecycle obligations`,
    );
  }

  assert.match(lifecycleSource, /delete\s+panel\.state\._previewDiff\b/);
  assert.match(lifecycleSource, /delete\s+panel\.state\._previewDiffGraphHash\b/);
  assert.match(lifecycleSource, /delete\s+panel\.state\._previewDiffCacheTag\b/);
});
