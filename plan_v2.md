# Implementation Plan: m3 Split the Panel God-File (Revised v2)

## Overview
`vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` is currently 10,337 lines and owns extension registration, panel singleton access, render scheduling, thread rendering, overlay drawing, composer/settings rendering, queue guard state, and debug instrumentation. The current singleton lives under `window.__vibecomfyAgentPanelSingleton`, but mutable runtime state is still module-local at `vibecomfy_roundtrip.js:319` through `:344`, so fresh imports can share the panel object while splitting scheduler/overlay/instrumentation state.

The existing loader mechanism is plain ESM: `vibecomfy_roundtrip.js` imports sibling modules (`agent_edit_lifecycle.js`, `comfy_adapter.js`, `agent_edit_response_contract.js`) by relative path. Browser tests copy these files into a temp Comfy web root in `tests/browser/harness.mjs:608`. The split reuses that pattern: no bundler, no build step, `vibecomfy_roundtrip.js` remains the entry file and imports the new sibling modules.

This revision addresses all 10 significant flags from the v1 critique. Key changes: splits oversized Steps 4 and 7 into sub-steps, adds explicit harness.mjs copy instructions to every extraction step, acknowledges the cache-clearing self-heal as a behavioral enhancement, adjusts the line-count target to a realistic ~6,000 lines, and adds `test_comfy_nodes_browser.py` to the validation gate.

## Phase 1: Runtime State Foundation

### Step 1: Add `panel_runtime.js` and move singleton/runtime state accessors
**Complexity: 3**

**Scope:** `vibecomfy/comfy_nodes/web/panel_runtime.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `tests/browser/harness.mjs`

1. Create `panel_runtime.js` as the only owner of the page-level singleton key `__vibecomfyAgentPanelSingleton`.
2. Preserve the existing record shape fields `panel` and `panelsCreated`, and add a nested `runtime` object for all former module globals:
   - registration: `agentSidebarTabRegistered`, `agentTurnEventListener`, `agentTurnEventListenerRegistered`, `_adapterCapabilities`, `_previewForegroundInstallReport`, `_progressPulseInjected`
   - queue guard: `queueGuardHook`, `queueGuardContext`, `queueGuardFallbackWarning`, `queueGuardFallbackWarned`, `queueGuardBlockNotice`, `queueGuardBlockedTurnKeys`
   - scheduler: `_scheduledAgentPanelRender`, `_scheduledAgentPanelRenderQueued`, `_agentPanelFlushCount`, `_lastAgentPanelFlushReason`
   - instrumentation: `_lastThreadRender`, `_lastNoticeRender`, `_statusCommitAt`, `_rehydrateCommitAt`, `_marksAfterCommit`
   - overlay feedback/cache: `changedNodeFeedbackTimer`, `changedNodeFeedbackVisuals`, `_overlayDrawModelCache`
3. Export narrow helpers such as `panelRuntime()`, `currentAgentPanel()`, `setCurrentAgentPanel(panel)`, `panelsCreatedCount()`, and `nextAgentPanelId()`.
4. Make the runtime initializer idempotently upgrade old records like `{ panel, panelsCreated }` without resetting existing panel or counters.
5. Add a `PANEL_RUNTIME_SOURCE` path constant and writeFile call in `tests/browser/harness.mjs` to copy `panel_runtime.js` into the temp web root.
6. Keep `window.__vibecomfyPanelDebug()` output shape unchanged; only its source of truth changes.
7. **Queue guard accessor note:** Functions that stay in the entry module (`installQueueGuard`, `setQueueGuardContext`, `warnQueueGuardFallbackOnce`, `getQueueGuardStateForPanel` at lines ~7348-7377) will access `panelRuntime().queueGuard.*` instead of module-level variables. This is a straightforward find-and-replace across ~6 well-identified functions.

### Step 2: Add the double-evaluation runtime-state regression test
**Complexity: 2**

**Scope:** `tests/browser/roundtrip_smoke.test.mjs`

1. Extend the existing duplicate evaluation test at `tests/browser/roundtrip_smoke.test.mjs:7062`.
2. Force one module instance to schedule or complete a render flush, then assert the second module's exported/debug view observes the same `flushCount`, `lastFlushReason`, `flushPending`, and instrumentation state.
3. Also assert `panelsCreated === 1` remains true.
4. Do not change behavioral assertions except to add runtime-state parity checks.

## Phase 2: Scheduler Extraction

### Step 3: Move dirty-section scheduling into `panel_scheduler.js`
**Complexity: 4**

**Scope:** `vibecomfy/comfy_nodes/web/panel_scheduler.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `tests/browser/harness.mjs`

1. Extract the scheduling path centered on `markAgentPanelDirty`, `consumeAgentPanelDirtySections`, `scheduleRenderAgentPanel`, `hasPendingAgentPanelFlush`, `rerenderAgentPanelIfMounted`, `renderDirtyAgentPanelSections`, and section exception/retry helpers currently around `vibecomfy_roundtrip.js:3515` and `:8409`.
2. Store scheduler state exclusively in `panelRuntime().scheduler`.
3. Convert the current if/else section dispatch at lines 8429-8443 to a callback-registration map. The entry module (`vibecomfy_roundtrip.js`) registers render callbacks keyed by `RENDER_SECTIONS.*` constants after all imports resolve. The scheduler iterates dirty sections and invokes the registered callbacks. **Fallback:** if the callback-registration indirection proves too complex during implementation, the scheduler may directly import the render modules — this avoids circular imports because the scheduler is imported by the render modules, not vice versa.
4. Preserve the rAF-vs-timeout behavior at `vibecomfy_roundtrip.js:3675` and the per-section retry semantics at `:8453`.
5. Keep existing exported names from `vibecomfy_roundtrip.js` as forwarding exports where tests or consumers import them.
6. Add a `PANEL_SCHEDULER_SOURCE` path constant and writeFile call in `tests/browser/harness.mjs` to copy `panel_scheduler.js` into the temp web root.
7. Run the targeted scheduler/browser tests after this step before moving more code.

## Phase 3: Thread Rendering Extraction and DOM Self-Heal

### Step 4a: Move thread data management and bubble reconciliation into `panel_thread.js`
**Complexity: 4**

**Scope:** `vibecomfy/comfy_nodes/web/panel_thread.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `tests/browser/harness.mjs`

1. Extract thread data/state functions: `resetThreadRenderState`, `reconcileChatBubbles` (the DOM-as-truth bubble reconciliation at line 5407), message collection helpers, display windowing, bubble signature construction, detail signature construction, and `panel.threadState` management.
2. Keep `panel.threadState` as the per-panel DOM reconciliation cache on the panel object; do not move it to module runtime because it is panel-specific.
3. Extract scroll-follow decision helpers and auto-scroll state management.
4. Add a `PANEL_THREAD_SOURCE` path constant and writeFile call in `tests/browser/harness.mjs` to copy `panel_thread.js` into the temp web root.

### Step 4b: Move renderHistory, renderActivityRows, renderThreadSection into `panel_thread.js` with DOM self-heal enhancement
**Complexity: 4**

**Scope:** `vibecomfy/comfy_nodes/web/panel_thread.js` (continued), `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`

1. Extract `renderHistory` (line 5861), `renderActivityRows` (line 5819), `renderThreadSection` (line 8261), bubble detail rendering (~line 5628+), and related DOM helpers into `panel_thread.js`.
2. **Behavioral enhancement — DOM self-heal generalization:** The current `reconcileChatBubbles` validates cached bubble entries against DOM by checking `bubbleEntry?.node?.parentNode !== messagesMount` and *skips* stale entries, but does not clear the stale cache and re-render. In this step, enhance the reconciliation to clear stale cache entries and trigger re-render when the DOM node is missing, detached, or keyed differently. This is a deliberate robustness improvement (not pure refactoring) that prevents accumulated stale cache from causing display gaps.
3. Audit batch/activity row signatures, bubble detail signatures, and developer/settings caches. Apply the same validate-against-DOM-at-render-start approach where a cache points at DOM; document in a short code comment if a cache is pure data and cannot diverge from DOM.
4. Preserve the fixed render ordering where `renderHistory(panel)` runs before `renderActivityRows(panel)` and the final scroll happens after both.

### Step 5: Add focused self-heal coverage
**Complexity: 2**

**Scope:** `tests/browser/roundtrip_smoke.test.mjs`

1. Add or extend focused browser tests near the existing thread signature tests around `tests/browser/roundtrip_smoke.test.mjs:12469`.
2. Seed stale signature/detail cache state, remove or replace the corresponding DOM node, trigger a thread render, and assert the cache is rebuilt and visible text remains correct.
3. Keep assertions behavioral; do not assert private implementation names beyond already-exposed panel debug or panel state fields.

## Phase 4: Overlay Extraction

### Step 6: Move canvas overlay and changed-node feedback into `panel_overlay.js`
**Complexity: 4**

**Scope:** `vibecomfy/comfy_nodes/web/panel_overlay.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `tests/browser/harness.mjs`

1. Extract preview overlay install/draw/model-cache functions around `vibecomfy_roundtrip.js:1177`, `:6172`, `:6518`, and `:6655`.
2. Extract changed-node feedback functions around `vibecomfy_roundtrip.js:7271`.
3. Store overlay draw cache and changed-node timer/visuals in `panelRuntime().overlay`.
4. Keep `drawPreviewOverlay(ctx, diff)` exported through `vibecomfy_roundtrip.js` for existing tests.
5. Preserve adapter integration with `installPreviewForegroundOverlay` from `comfy_adapter.js` and keep the app-level overlay wrapper markers unchanged.
6. Add a `PANEL_OVERLAY_SOURCE` path constant and writeFile call in `tests/browser/harness.mjs` to copy `panel_overlay.js` into the temp web root.

## Phase 5: Composer, Settings, Notices, and Developer Panel Extraction

### Step 7a: Move composer button sync and notice rendering into `panel_composer.js`
**Complexity: 3**

**Scope:** `vibecomfy/comfy_nodes/web/panel_composer.js`, `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, `tests/browser/harness.mjs`

1. Extract composer button sync (`renderComposerActions` at RENDER_SECTIONS.COMPOSER dispatch line 8435), composer notice rendering (`renderComposerNoticeSection` at line 8437), and related small DOM helpers.
2. Store notice instrumentation (`lastNoticeRender`) through `panelRuntime().instrumentation`.
3. Add a `PANEL_COMPOSER_SOURCE` path constant and writeFile call in `tests/browser/harness.mjs` to copy `panel_composer.js` into the temp web root.

### Step 7b: Move settings rendering and developer/debug panel rendering into `panel_composer.js`
**Complexity: 3**

**Scope:** `vibecomfy/comfy_nodes/web/panel_composer.js` (continued), `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`

1. Extract settings rendering (`renderSettingsSection` at RENDER_SECTIONS.SETTINGS dispatch line 8439) and developer/debug panel rendering (`renderDeveloperSection` at line 8443) into `panel_composer.js`.
2. Keep action handlers (`submit`, `apply`, `reject`, `rebaseline`, settings save/test) wired from the entry module unless moving them is strictly needed to break a dependency cycle.
3. Preserve all text, IDs, CSS values, button labels, and section IDs.

## Phase 6: Slim Entry Module and Documentation

### Step 8: Reduce `vibecomfy_roundtrip.js` to shell, wiring, network, and graph mutation
**Complexity: 5**

**Scope:** `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`

1. Leave `vibecomfy_roundtrip.js` as the ComfyUI extension entrypoint: imports, constants, panel shell construction, extension registration, menu/sidebar setup, network request construction, lifecycle obligation fulfillment, graph serialization/mutation, and forwarding exports.
2. Remove all module-level mutable state from the entry file; runtime state must be accessed through `panel_runtime.js`.
3. Keep the boundary modules from m1 unchanged unless import paths must be copied into the harness.
4. Add exactly five new files: `panel_runtime.js`, `panel_scheduler.js`, `panel_thread.js`, `panel_overlay.js`, `panel_composer.js`.
5. Target ~6,000 lines or fewer for `vibecomfy_roundtrip.js` after extraction (down from 10,337). This is a "should" criterion; the primary success condition is that all rendering/scheduling/overlay code is extracted and the file contains only shell, wiring, network, and graph mutation. The submitAgentEdit handler (line ~8659+) and its apply/reject/rebaseline siblings, plus graph mutation functions (applyGraphInPlaceWithIntentDecoration, applyGraphDeltaInPlace, validateScopedCanvasPreconditions, verifyScopedCanvasResults), constitute most of the remaining line count.

### Step 9: Update client lifecycle documentation
**Complexity: 2**

**Scope:** `docs/agent-edit-client-lifecycle.md`

1. Update the ownership table currently saying roundtrip owns all DOM/rendering at `docs/agent-edit-client-lifecycle.md:108` through `:121`.
2. Add a concise module map section naming the new files and their responsibilities.
3. Document the load/order rule: `vibecomfy_roundtrip.js` remains the only extension entrypoint; sibling modules are loaded by static ESM imports; `panel_runtime.js` is imported by all panel modules and is idempotent under re-evaluation.
4. Preserve the debug hook contract section and explicitly state the output shape is unchanged.

## Phase 7: Verification

### Step 10: Run cheap structural checks, then full characterization gates
**Complexity: 3**

**Scope:** `vibecomfy/comfy_nodes/web/*`, `tests/browser/*`, `tests/test_comfy_nodes_agent_*.py`, `tests/test_comfy_nodes_browser.py`

1. Run cheap grep checks first:
   - `rg '^let _|^var _' vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js vibecomfy/comfy_nodes/web/panel_*.js`
   - `wc -l vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
2. Run targeted browser tests while iterating:
   - `node --test tests/browser/roundtrip_smoke.test.mjs --test-name-pattern 'duplicate extension evaluation|scheduled render|thread|overlay|composer|settings'`
   - `node --test tests/browser/agent_edit_lifecycle.test.mjs`
3. Run the required full gates:
   - `node --test tests/browser/roundtrip_smoke.test.mjs`
   - `node --test tests/browser/agent_edit_lifecycle.test.mjs`
   - `pytest tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_edit.py`
   - `pytest tests/test_comfy_nodes_browser.py`
4. If available in the worker environment, perform the documented live smoke on `:8199`: panel open, submit, apply, and inspect `window.__vibecomfyPanelDebug()` before and after.

## Execution Order
1. Create `panel_runtime.js` and harness copying before extracting any modules. (Step 1)
2. Add the double-evaluation runtime-state test early so every later extraction is guarded. (Step 2)
3. Extract scheduler because every render seam depends on it; register render callbacks from entry module. (Step 3)
4. Extract thread data management + reconcileChatBubbles into `panel_thread.js` first. (Step 4a)
5. Extract renderHistory/renderActivityRows/renderThreadSection + DOM self-heal enhancement next. (Step 4b)
6. Add self-heal coverage tests after thread extraction is complete. (Step 5)
7. Extract overlay after thread extraction stabilizes. (Step 6)
8. Extract composer button sync + notice rendering first. (Step 7a)
9. Extract settings + developer/debug rendering next. (Step 7b)
10. Slim the entry module only after all forwarding exports and tests are green. (Step 8)
11. Update docs after the final module map is real. (Step 9)
12. Run full verification. (Step 10)

## Validation Order
1. Cheap grep and line-count checks after each extraction.
2. Focused browser tests for the touched seam after each step.
3. Full browser characterization suites once all modules are split.
4. Python agent-node tests last, because they include source-text parity checks such as frontend/backend event-name matching.
5. Python browser integration test (`test_comfy_nodes_browser.py`) last, verifying end-to-end harness smoke.

## Ticket Linking Proposal
No listed open ticket directly tracks this frontend panel decomposition. I would not propose `resolves_on_complete=true` links for the current ticket set.
