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

const roundtripSource = source("vibecomfy_roundtrip.js");
const panelOverlaySource = source("panel_overlay.js");

function declarationPattern(name) {
  return new RegExp(
    String.raw`(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+${name}\s*\(`
      + String.raw`|(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+${name}\b`,
  );
}

function functionBody(name) {
  const match = roundtripSource.match(
    new RegExp(String.raw`(?:export\s+)?function\s+${name}\s*\([^)]*\)\s*\{([\s\S]*?)\n\}`),
  );
  assert.ok(match, `expected ${name} wrapper in vibecomfy_roundtrip.js`);
  return match[1];
}

test("panel_overlay owns preview overlay implementation details", () => {
  for (const name of [
    "drawPreviewOverlay",
    "buildOverlayDrawModel",
    "computeGhostDimensions",
    "overlayDrawCacheKey",
    "safePreviewOverlayText",
    "clearPreviewDomOverlay",
    "syncPreviewDomOverlay",
    "ensurePreviewDomOverlayRoot",
    "appendPreviewDomChip",
  ]) {
    assert.match(panelOverlaySource, declarationPattern(name), `panel_overlay.js must declare ${name}`);
  }

  for (const removedDomOwner of [
    "previewChipGeometry",
  ]) {
    assert.doesNotMatch(
      panelOverlaySource,
      declarationPattern(removedDomOwner),
      `panel_overlay.js must not keep the removed DOM preview renderer ${removedDomOwner}`,
    );
  }
});

test("roundtrip preview overlay export stays a thin owner-module facade", () => {
  for (const forbidden of [
    "_overlayDrawCacheKey",
    "_buildOverlayDrawModel",
    "_computeGhostDimensions",
    "_warnOverlayUnresolved",
    "FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS",
    "safePreviewOverlayText",
    "syncPreviewDomOverlay",
    "clearPreviewDomOverlay",
    "ensurePreviewDomOverlayRoot",
    "appendPreviewDomChip",
  ]) {
    assert.equal(
      declarationPattern(forbidden).test(roundtripSource),
      false,
      `vibecomfy_roundtrip.js must not declare preview overlay owner symbol ${forbidden}`,
    );
  }

  assert.match(
    roundtripSource,
    /import\s*\{[\s\S]*?drawPreviewOverlay\s+as\s+panelOverlayDrawPreviewOverlay[\s\S]*?\}\s*from\s*["']\.\/panel_overlay\.js["']/,
    "roundtrip must import the canonical panel_overlay drawPreviewOverlay",
  );

  const body = functionBody("drawPreviewOverlay");
  assert.match(body, /panelOverlayDrawPreviewOverlay\(ctx,\s*diff,\s*previewOverlayDeps\(\)\)/);
  assert.doesNotMatch(body, /\bctx\.(?:fillRect|strokeRect|fillText|measureText|beginPath|bezierCurveTo|roundRect)\b/);
  assert.doesNotMatch(body, /\b(?:liveByUid|candidateByUid|ghostDimsByUid|editedFieldsByUid)\b/);
});

test("runtime installer passes the owner renderer and syncs live DOM chips from the owner module", () => {
  const installBody = functionBody("installAgentPreviewOverlay");
  assert.match(installBody, /installAgentPreviewOverlayImpl\(app,\s*\{/);
  assert.match(installBody, /drawPreviewOverlay:\s*panelOverlayDrawPreviewOverlay/);
  assert.doesNotMatch(installBody, /drawPreviewOverlay:\s*drawPreviewOverlay\b/);
  assert.doesNotMatch(installBody, /syncPreviewDomOverlay/);

  const ownerInstallMatch = panelOverlaySource.match(
    /export\s+function\s+installAgentPreviewOverlay\s*\([^)]*\)\s*\{([\s\S]*?)\n\}/,
  );
  assert.ok(ownerInstallMatch, "panel_overlay installAgentPreviewOverlay must exist");
  assert.match(
    ownerInstallMatch[1],
    /syncPreviewDomOverlay\(app,\s*ctx/,
    "live preview draw loop must sync fixed-position DOM preview chips above Comfy text widgets",
  );
});

// ── T12: Diagnostic detail must not leak into preview overlay text ───────

test("FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS blocks diagnostic-detail-structured text", () => {
  // Extract the FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS array from panel_overlay source
  const forbiddenMatch = panelOverlaySource.match(
    /const FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS\s*=\s*\[([\s\S]*?)\];/,
  );
  assert.ok(forbiddenMatch, "FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS must be declared in panel_overlay.js");

  // Reconstruct the function body for safePreviewOverlayText
  const safeFuncMatch = panelOverlaySource.match(
    /function safePreviewOverlayText\(text,\s*fallback\s*=\s*""\)\s*\{([\s\S]*?)\n\}/,
  );
  assert.ok(safeFuncMatch, "safePreviewOverlayText must be declared in panel_overlay.js");

  // Verify existing blocked patterns catch diagnostic-like payloads
  const forbiddenSource = forbiddenMatch[1];

  // The existing patterns must already block common diagnostic markers
  assert.match(forbiddenSource, /engine diagnostics/,
    "FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS must block 'engine diagnostics'");
  assert.match(forbiddenSource, /raw diagnostic/,
    "FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS must block 'raw diagnostic'");

  // The forbidden patterns array is used by safePreviewOverlayText — every
  // string that matches a pattern is rejected.  Verify key diagnostic
  // patterns are blocked so choices/valid_fields/available_slots cannot
  // appear as free-standing preview text.
  const patterns = [
    "engine diagnostics",
    "raw diagnostic",
    "ProviderError",
    "Traceback",
    "stack trace",
    "debug_payload",
    "debugPayload",
  ];
  for (const pattern of patterns) {
    assert.match(forbiddenSource, new RegExp(pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"),
      `FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS must block '${pattern}'`);
  }
});

test("roundtrip does not re-export or inline safePreviewOverlayText", () => {
  // safePreviewOverlayText must only be defined in panel_overlay.js,
  // never inlined or re-declared in vibecomfy_roundtrip.js.
  const roundtripMatch = roundtripSource.match(
    /function\s+safePreviewOverlayText\s*\(/,
  );
  assert.equal(roundtripMatch, null,
    "vibecomfy_roundtrip.js must not declare its own safePreviewOverlayText");
});

test("safePreviewOverlayText usage path only flows through field values and labels, never through diagnostics", () => {
  // Verify that safePreviewOverlayText is called only on:
  //   - field.new_value (via fieldNewValueLabel)
  //   - title/type strings
  //   - input/output slot names
  //   - widget value text
  // It must never be called on diagnostic payloads or activity feed entries.
  const safeCalls = panelOverlaySource.match(
    /safePreviewOverlayText\(/g,
  );
  assert.ok(safeCalls && safeCalls.length > 0,
    "safePreviewOverlayText must be called in panel_overlay.js");

  // safePreviewOverlayText must never receive a full diagnostic object
  assert.doesNotMatch(panelOverlaySource, /safePreviewOverlayText\(\s*diag/,
    "safePreviewOverlayText must not operate on diagnostic objects");
  assert.doesNotMatch(panelOverlaySource, /safePreviewOverlayText\(\s*activity/,
    "safePreviewOverlayText must not operate on activity state objects");
});
