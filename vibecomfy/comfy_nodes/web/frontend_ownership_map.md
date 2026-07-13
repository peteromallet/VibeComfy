# Frontend Module Ownership Map

This document records the settled frontend ownership boundaries for the
non-messaging hardening work. It describes current source ownership only; stale
line-number inventories from the temporary extraction state have been removed.

## 1. Module Inventory

Scope note: this inventory covers the status/settings, composer/developer,
scheduler, candidate-action, and shell/dependency seams touched by the
non-messaging boundary work. It is not a complete ownership audit of every
frontend helper.

| Module | Path | Owner Role |
|--------|------|------------|
| `vibecomfy_roundtrip.js` | `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | Orchestration shell: imports owner modules, assembles dependency objects, wires events, owns panel DOM construction, dispatches render sections, and coordinates submit/apply/rebaseline flows. |
| `agent_status_poller.js` | `vibecomfy/comfy_nodes/web/agent_status_poller.js` | Status polling, route/model status projection, route-select population, provider persistence, OpenRouter credential storage, settings persistence, provider test flow, and choose-engine gate sync. |
| `panel_composer.js` | `vibecomfy/comfy_nodes/web/panel_composer.js` | Composer button rendering, submit-readiness state, notice rendering, settings rendering, and developer/debug rendering. |
| `agent_candidate_actions.js` | `vibecomfy/comfy_nodes/web/agent_candidate_actions.js` | Candidate apply/reject visibility and eligibility selectors. |
| `panel_scheduler.js` | `vibecomfy/comfy_nodes/web/panel_scheduler.js` | Dirty-section tracking, render scheduling, render gateway registration, root-connectedness checks, and the status-driven render-section list. |
| `panel_thread.js` | `vibecomfy/comfy_nodes/web/panel_thread.js` | Chat thread bubble rendering, entry collection, display computation, history expansion, rating widget, and audit detail rendering. |
| `panel_overlay.js` | `vibecomfy/comfy_nodes/web/panel_overlay.js` | Preview overlay install, invalidation, canvas ghost/value rendering, ghost dimension computation, and draw model cache. |
| `panel_runtime.js` | `vibecomfy/comfy_nodes/web/panel_runtime.js` | Singleton panel instance tracking, runtime state creation/backfill, and panel ID allocation. |
| `agent_edit_lifecycle.js` | `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js` | Panel state machine, `RENDER_SECTIONS`, obligation normalization, delta-op normalization, and chat message reconciliation. |
| `preview_picker.js` | `vibecomfy/comfy_nodes/web/preview_picker.js` | Dev/demo preview picker UI and scenario playback. It may commit demo lifecycle transitions through `agent_lifecycle_commit.js` and must fulfill returned obligations instead of mutating lifecycle-owned preview state directly. |
| `agent_edit_response_contract.js` | `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js` | Response normalizers, field readers, turn identity readers, stage snapshot readers, and route-apply affordance checks. |
| `agent_edit_response_contract_generated.js` | `vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js` | Auto-generated contract shapes. Do not hand-edit. |
| `comfy_adapter.js` | `vibecomfy/comfy_nodes/web/comfy_adapter.js` | Graph apply/delta in-place, queue guard installation, preview foreground overlay installation, typed socket labels, and exec-node normalization. |
| `agent_turn_feed.js` | `vibecomfy/comfy_nodes/web/agent_turn_feed.js` | Turn payload normalization, activity state derivation, activity feed reduction, progress labels, and statement formatting. |
| `executor_progress.js` | `vibecomfy/comfy_nodes/web/executor_progress.js` | Executor phase normalization, progress snapshots, phase-to-progress mapping, and decision/progress labels. |
| `diagnostics_reporting.js` | `vibecomfy/comfy_nodes/web/diagnostics_reporting.js` | Issue report building, audit envelopes, artifact path commits, issue modal, rating submission, and browser diagnostics capture. |
| `markdown.js` | `vibecomfy/comfy_nodes/web/markdown.js` | Markdown-to-HTML rendering used by thread bubbles. |

## 2. Allowed Responsibilities

### `vibecomfy_roundtrip.js`

- Import and wire dependencies from owner modules.
- Keep orchestration and event-handler wrappers that assemble already-required
  deps or bind UI events before delegating to an owner module.
- Define facade entry points such as `normalizeForSerialize`,
  `normalizeForDisplay`, `normalizeForApply`, and `repairLiveNodes`.
- Define shell-scoped constants such as `PANEL_IDS`,
  `AGENT_PANEL_MOUNT_MODE`, `AGENT_SIDEBAR_TAB_ID`, intent class/type maps,
  preview limits, and palette colors.
- Own `ensureAgentPanel()` panel creation and DOM construction.
- Own submit/apply/rebaseline orchestration, including calls into lifecycle,
  adapters, status/composer deps, and render scheduling.
- Own render dispatch in `renderAgentPanelSections()`, while delegating each
  section body to the module that owns that surface.
- Must not define status polling implementations, settings/developer renderer
  implementations, composer renderer implementations, preview overlay
  implementations, route/provider constants, or candidate eligibility selectors.
- Must not define old shell thread-detail renderers such as `renderCandidate`,
  `renderFailure`, or `renderQueue`.

Acceptable shell wrappers include dependency assembly functions such as
`agentStatusDeps()`, `composerRenderDeps()`, and
`agentPanelThreadRenderDeps()`, plus thin render wrappers that call imported
owner functions.

### `agent_status_poller.js`

- Owns `ROUTE_STATUS_KIND`, `AGENT_STATUS_RETRY_DELAYS_MS`,
  `ROUTE_ALIASES`, `ROUTE_LABELS`, and `CANONICAL_AGENT_PROVIDERS`.
- DeepSeek is a distinct route and provider. `ROUTE_ALIASES.deepseek` maps to
  `"deepseek"`, `ROUTE_LABELS` includes `deepseek`, and
  `CANONICAL_AGENT_PROVIDERS` includes `"deepseek"` alongside
  `"openrouter"`.
- Owns provider persistence and localStorage helpers:
  `getPersistedAgentProvider`, `setPersistedAgentProvider`, `_lsGet`,
  `_lsSet`, and `_lsRemove`. Persisted `"deepseek"` values remain valid.
- Owns route/model normalization and status projection:
  `normalizeRoutePreference`, `normalizeModelPreference`,
  `routeOptionsFromStatus`, `projectRouteStatus`, `routeStatusState`,
  `getRouteOptions`, and `getRouteDescriptor`.
- Owns status fetch/retry and route control behavior:
  `buildStatusUrl`, `refreshAgentStatus`, `scheduleAgentStatusRetry`,
  `clearAgentStatusRetry`, `populateRouteSelect`, and
  `syncChooseEngineGate`.
- Owns settings save/test flows and credential storage:
  `persistAgentSettings`, `testAgentSettings`, and
  `storeOpenRouterCredential`.
- Receives shell callbacks through deps for rendering, dirty marking, overlay
  invalidation, macrotask scheduling, and retry re-entry.

### `panel_scheduler.js`

- Owns `SETTINGS_STATUS_RENDER_SECTIONS`.
- The canonical status-driven render-section list is
  `[RENDER_SECTIONS.THREAD, RENDER_SECTIONS.SETTINGS,
  RENDER_SECTIONS.COMPOSER, RENDER_SECTIONS.NOTICE]`.
- `RENDER_SECTIONS.NOTICE` is intentionally included because route/status
  changes refresh the composer submit-readiness notice.
- `RENDER_SECTIONS.DEVELOPER` is intentionally excluded from the status-specific
  list; developer rendering remains composer-owned and is only rerendered when a
  caller explicitly requests the developer section.
- Owns dirty-section normalization, pending dirty-section queues, status/rehydrate
  commit notes, scheduled flushes, and render gateway registration.

### `panel_composer.js`

- Owns composer actions: `renderComposerActions`, `syncComposerButtons`, and
  `submitReadinessState`.
- Owns submit-readiness notice rendering:
  `renderComposerNotice` and `renderComposerNoticeSection`.
- Owns settings rendering:
  `renderSettings` and `renderSettingsSection`.
- Owns developer/debug rendering:
  `renderDeveloper`, `renderDeveloperDisclosure`, and
  `renderDeveloperSection`.
- Owns `composerApplyDisplayState`; candidate action decisions themselves come
  from the injected `candidateActionState` selector.
- Receives status helpers, credential helpers, route descriptors, DOM helpers,
  and debug helpers through deps from the shell.

### `agent_candidate_actions.js`

- Owns `APPLY_ELIGIBILITY_REASON`.
- Exports `normalizeApplyEligibility`, `applyEligibility`,
  `disabledApplyEligibility`, `candidateGraphPresentForBubble`, and
  `candidateActionState`.
- Keeps warning construction, missing-contract handling, no-candidate payloads,
  active turn-id selection, and historical snapshot eligibility internal unless
  an actual caller needs a new exported surface.
- `panel_thread.js` and `panel_composer.js` consume candidate action state only
  through injected dependencies from the shell; they do not import this owner
  module directly.

### `panel_thread.js`

- Owns thread collection and rendering.
- Owns candidate/failure/queue audit detail rendering for thread bubbles.
- May receive candidate-action state as an injected dependency for bubble action
  affordances.
- Must not own candidate eligibility decisions or import
  `agent_candidate_actions.js` directly.

### `panel_overlay.js`

- Owns preview overlay installation and all preview drawing implementation.
- Canvas rendering is the only active preview text path.
- `clearPreviewDomOverlay` may remain as a compatibility cleanup for stale
  browser sessions, but DOM preview-chip creation helpers must not be
  reintroduced.
- Owns draw-model cache keys, overlay text normalization, ghost dimensions, and
  port/node fallback logic for preview wires.

### `agent_edit_lifecycle.js`

- Owns candidate/preview state invalidation when reducer transitions leave
  preview mode.
- Stop/abort, apply success, authoritative accept rejection, and rebaseline
  success clear candidate preview state through the lifecycle invalidation
  primitive.
- Reject failure intentionally preserves candidate preview state because the
  reject did not complete.
- Transient preview diff fields (`_previewDiff`, `_previewDiffGraphHash`,
  `_previewDiffCacheTag`, `_previewDiffLiveCanvasRevision`, and
  `_previewDiffInputSignature`) are cleared only by lifecycle candidate invalidation.
  Shell/demo code may fulfill cleanup obligations, but must not hand-clear those
  fields.

### `preview_picker.js`

- Owns demo picker controls and local scenario playback only.
- Uses `agent_lifecycle_commit.js` helpers to reflect demo stages into panel
  state.
- Must fulfill lifecycle obligations returned from those helpers when the
  production shell provides an obligation fulfiller.
- Must not clear lifecycle-owned candidate/preview fields directly.

## 3. Settled Boundary Status

| Boundary | Final Status |
|----------|--------------|
| Status poller | `vibecomfy_roundtrip.js` imports the poller APIs and delegates status refresh, retries, route select population, choose-engine gate sync, settings persistence, credential storage, and provider testing through `agentStatusDeps()`. |
| DeepSeek route | DeepSeek remains distinct from OpenRouter in aliases, labels, persisted providers, route options, descriptors, and browser-visible provider behavior. |
| Scheduler status sections | `panel_scheduler.js` owns `SETTINGS_STATUS_RENDER_SECTIONS` with `NOTICE` included and `DEVELOPER` excluded. |
| Composer/settings/developer | `panel_composer.js` owns the settings and developer renderers. The shell imports `renderSettingsSection` and `renderDeveloperSection` with composer aliases and calls them with `composerRenderDeps()`. |
| Candidate actions | `agent_candidate_actions.js` owns candidate action visibility and eligibility selectors. The shell imports the exported selector surface and injects it into composer/thread render deps. |
| Thread rendering | `panel_thread.js` owns thread rendering and receives required callbacks/deps from the shell. |
| Preview overlay | `panel_overlay.js` owns preview overlay implementation. The shell imports and delegates to it; DOM preview-chip rendering is removed. |
| Diagnostics mirrors | Runtime diagnostics use `_lastThreadRender` and `_lastNoticeRender` as canonical fields. Duplicate `last*Render` mirrors should not be reintroduced. |
| Demo preview picker | `preview_picker.js` owns demo UI only. Lifecycle state projection goes through commit helpers, and preview cleanup goes through returned obligations. |

## 4. Ownership Principles

1. `vibecomfy_roundtrip.js` is orchestration-first. It may assemble deps and
   coordinate flows, but it should not duplicate owner-module logic.
2. One module owns each render surface or selector family. Imports and explicit
   deps are preferred over closure-bound copies in the shell.
3. DeepSeek route/provider behavior is not a cleanup target. It is a distinct
   user-visible/browser provider route.
4. Status-triggered UI refreshes use the scheduler-owned
   `SETTINGS_STATUS_RENDER_SECTIONS` list so settings, composer controls, and
   the submit-readiness notice stay in sync.
5. Static ownership tests should guard against reintroducing local shell copies
   of status-poller, composer/developer/settings, scheduler status-section,
   preview overlay, thread-detail, and candidate-action owner symbols.
