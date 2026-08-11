import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import * as lifecycle from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";
import { createBrowserHarness } from "./harness.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

const roundtripSource = source("vibecomfy_roundtrip.js");
const lifecycleSource = source("agent_edit_lifecycle.js");

// ── T-056 helpers ──────────────────────────────────────────────────────────
// Mirror the definition-detection regex of frontend_ownership_regression.test.mjs
// so "roundtrip must not define X" and "roundtrip must not own factory X" use
// the same convention.
function assertNoDefinition(moduleSource, name, message) {
  const definitionPattern = new RegExp(
    String.raw`(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+${name}\s*\(|(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+${name}\b`,
  );
  assert.equal(definitionPattern.test(moduleSource), false, message);
}

function makePanel(overrides = {}) {
  const state = lifecycle.createAgentEditState();
  Object.assign(state, overrides);
  return { state };
}

test("submit flow keeps exactly TWO module-level WeakMaps and one scalar deps object (S12)", () => {
  // Exactly two WeakMap singletons in the whole module — any third WeakMap
  // (e.g. a preview cache) breaks this pin.
  const weakMapDeclarations = roundtripSource.match(/const\s+(\w+)\s*=\s*new WeakMap\(\)/g) || [];
  assert.deepEqual(
    weakMapDeclarations.map((declaration) => declaration.match(/const\s+(\w+)/)[1]).sort(),
    ["pendingTransactionSnapshotByPanel", "submitActivityByPanel"],
    "vibecomfy_roundtrip.js must declare exactly submitActivityByPanel and pendingTransactionSnapshotByPanel as WeakMaps",
  );
  assert.equal(
    (roundtripSource.match(/new WeakMap\(/g) || []).length,
    2,
    "no other WeakMap may exist in vibecomfy_roundtrip.js (preview caching must stay on panel.state)",
  );

  // The watchdog deps carrier is a PLAIN OBJECT literal spreading the frozen
  // scalar defaults — NOT a WeakMap.
  assert.match(roundtripSource, /const\s+submitWatchdogDepsState\s*=\s*\{\s*\.\.\.DEFAULT_SUBMIT_WATCHDOG_DEPS,\s*\};/);
  assert.match(roundtripSource, /const\s+DEFAULT_SUBMIT_WATCHDOG_DEPS\s*=\s*Object\.freeze\(\{/);
  for (const scalarKey of [
    "nowMs()",
    "setTimeoutFn(handler, delayMs)",
    "clearTimeoutFn(timeoutId)",
    "submitDeadlineMs: DEFAULT_SUBMIT_DEADLINE_MS,",
    "submitAbsoluteDeadlineMs: DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS,",
    "submitAutomaticRetryCount: DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT,",
  ]) {
    assert.match(roundtripSource, new RegExp(scalarKey.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
      `submitWatchdogDepsState must carry scalar dep ${scalarKey}`);
  }

  // Accessor seam is exported (get/inject/reset).
  assert.match(roundtripSource, /export\s+function\s+configureSubmitWatchdogDeps\(/);
  assert.match(roundtripSource, /export\s+function\s+resetSubmitWatchdogDeps\(/);
});

test("submit watchdog deps seam behaves as a plain-object singleton (behavioral via harness)", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();

    // Getter path returns a plain copy — not a WeakMap.
    const defaults = mod.configureSubmitWatchdogDeps();
    assert.equal(Object.getPrototypeOf(defaults), Object.prototype);
    assert.equal(defaults instanceof WeakMap, false);
    assert.equal(typeof defaults.set, "undefined", "plain objects have no WeakMap .set");

    // Inject scalar deps and round-trip through the getter.
    const nowMs = () => 42;
    const configured = mod.configureSubmitWatchdogDeps({
      nowMs,
      submitDeadlineMs: 123456,
      submitAbsoluteDeadlineMs: 654321,
      submitAutomaticRetryCount: 3,
    });
    assert.equal(configured.nowMs, nowMs);
    assert.equal(configured.nowMs(), 42);
    assert.equal(configured.submitDeadlineMs, 123456);
    assert.equal(configured.submitAbsoluteDeadlineMs, 654321);
    assert.equal(configured.submitAutomaticRetryCount, 3);

    // The getter returns a COPY — mutating it must not corrupt the singleton.
    configured.submitDeadlineMs = 999999;
    assert.equal(mod.configureSubmitWatchdogDeps().submitDeadlineMs, 123456);

    // Reset path restores frozen defaults.
    const reset = mod.resetSubmitWatchdogDeps();
    assert.equal(reset.submitDeadlineMs, 210000);
    assert.equal(reset.submitAbsoluteDeadlineMs, 900000);
    assert.equal(reset.submitAutomaticRetryCount, 1);
    assert.notEqual(reset.nowMs, nowMs, "reset restores the default nowMs, not the injected one");
    mod.resetSubmitWatchdogDeps();
  } finally {
    await harness.dispose();
  }
});

test("preview cache stays on panel.state keyed by primitive strings (S13)", () => {
  // Cache write sites — all on panel.state, none in a WeakMap.
  assert.match(roundtripSource, /panel\.state\._previewDiff\s*=\s*diff;/);
  assert.match(roundtripSource, /panel\.state\._previewDiffGraphHash\s*=\s*candidateGraphHash;/);
  assert.match(roundtripSource, /panel\.state\._previewDiffCacheTag\s*=\s*deltaOpsCacheTag;/);
  assert.match(roundtripSource, /panel\.state\._previewDiffLiveCanvasRevision\s*=\s*liveCanvasRevision;/);
  assert.match(roundtripSource, /panel\.state\._previewDiffInputSignature\s*=\s*inputSignature;/);
  // Cache hit reads — keyed by the same primitives.
  assert.match(roundtripSource, /panel\.state\._previewDiffGraphHash\s*===\s*candidateGraphHash/);
  assert.match(roundtripSource, /panel\.state\._previewDiffCacheTag\s*===\s*deltaOpsCacheTag/);

  // The cache tag is a primitive string: `delta:N` or "graph" — never an object key.
  assert.match(roundtripSource, /deltaOpsCacheTag\s*=\s*[^;]*`delta:\$\{deltaOps\.length\}`\s*:\s*"graph"/);

  // Layout preview cache shares the same panel.state home, keyed by
  // candidateGraphHash (primitive string), cleared by delete.
  assert.match(roundtripSource, /panel\.state\._layoutPreviewCandidateGraphHash\s*=\s*panel\.state\.candidateGraphHash;/);
  assert.match(roundtripSource, /panel\.state\._layoutPreviewCandidateGraphHash\s*===\s*panel\.state\.candidateGraphHash/);
  assert.match(roundtripSource, /delete\s+panel\.state\._layoutPreviewCandidateGraphHash;/);
});

test("lifecycle module is the authority and roundtrip delegates (no duplicate factory)", () => {
  // Authority exports exist in agent_edit_lifecycle.js.
  assert.match(lifecycleSource, /export\s+const\s+PANEL_STATE\s*=\s*Object\.freeze\(\{/);
  assert.match(lifecycleSource, /export\s+const\s+LIFECYCLE_STATE_FIELDS\s*=\s*Object\.freeze\(\[/);
  assert.match(lifecycleSource, /export\s+function\s+createAgentEditState\(\)/);
  assert.match(lifecycleSource, /export\s+function\s+transition\(panel,\s*event,\s*payload\s*=\s*\{\}\)/);

  // Roundtrip imports the factory from the lifecycle module...
  assert.match(roundtripSource, /from\s+["']\.\/agent_edit_lifecycle\.js["']/);
  assert.match(roundtripSource, /createAgentEditState,?\s*$/m, "roundtrip must import createAgentEditState from the lifecycle module");
  assert.match(roundtripSource, /\.\.\.createAgentEditState\(\)/, "roundtrip must spread the lifecycle factory into panel.state");

  // ...and does NOT re-implement it.
  assertNoDefinition(roundtripSource, "createAgentEditState", "vibecomfy_roundtrip.js must not define its own createAgentEditState");
});

test("lifecycle-owned-by-clear removes the preview diff cache fields (behavioral)", () => {
  const panel = makePanel({
    _previewDiff: { added_links: [], removed_links: [], edited_fields: [], layout_moved: [], layout_groups: [] },
    _previewDiffGraphHash: "candidate-graph-hash",
    _previewDiffCacheTag: "delta:3",
    _previewDiffLiveCanvasRevision: "42",
    _previewDiffInputSignature: "input-signature",
    _layoutPreviewCandidateGraphHash: "layout-candidate-graph-hash",
  });

  // The lifecycle clear path for candidate-derived data is the exported
  // transition INVALIDATE_CANDIDATE event.
  const obligations = lifecycle.transition(panel, "INVALIDATE_CANDIDATE");
  assert.deepEqual(obligations, { render: true });

  // Lifecycle-owned-by-clear: the five transient _previewDiff* fields are gone.
  assert.equal(panel.state._previewDiff, undefined);
  assert.equal(panel.state._previewDiffGraphHash, undefined);
  assert.equal(panel.state._previewDiffCacheTag, undefined);
  assert.equal(panel.state._previewDiffLiveCanvasRevision, undefined);
  assert.equal(panel.state._previewDiffInputSignature, undefined);

  // The LAYOUT preview cache is NOT lifecycle-owned: INVALIDATE_CANDIDATE
  // deliberately leaves _layoutPreviewCandidateGraphHash alone — its clear is
  // roundtrip-owned via clearLayoutPreviewState (pinned statically above).
  // Freeze that division so a future merge of the two clear paths is a
  // deliberate, reviewed change.
  assert.equal(panel.state._layoutPreviewCandidateGraphHash, "layout-candidate-graph-hash",
    "layout preview cache clear is roundtrip-owned (clearLayoutPreviewState), not lifecycle-owned");
});

test("lifecycle authority exports are behaviorally present", () => {
  assert.equal(typeof lifecycle.createAgentEditState, "function");
  assert.equal(typeof lifecycle.transition, "function");
  assert.equal(typeof lifecycle.PANEL_STATE, "object");
  assert.equal(lifecycle.PANEL_STATE.IDLE, "IDLE");
  assert.ok(Array.isArray(lifecycle.LIFECYCLE_STATE_FIELDS));
  assert.ok(lifecycle.LIFECYCLE_STATE_FIELDS.includes("phase"));

  // Fresh state carries lifecycle defaults and no preview cache residue.
  const state = lifecycle.createAgentEditState();
  assert.equal(state.phase, lifecycle.PANEL_STATE.IDLE);
  assert.equal(state._previewDiff, undefined);
  assert.equal(state._layoutPreviewCandidateGraphHash, undefined);
});
