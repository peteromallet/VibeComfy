# Frontend Module Ownership Map

> Generated for M5: Frontend Module And Poller Decomposition.
> Documents current ownership, allowed responsibilities, and duplicate/stale candidates
> still resident in `vibecomfy_roundtrip.js`.

---

## 1. Module Inventory

| Module | Path | Owner Role |
|--------|------|------------|
| `vibecomfy_roundtrip.js` | `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | **Orchestration shell only** (post-M5 target): wire events, call normalizers/reducers/selectors, invoke graph adapters, schedule render. No renderer implementations. |
| `agent_status_poller.js` | `vibecomfy/comfy_nodes/web/agent_status_poller.js` | Status polling, route-select population, settings persistence, OpenRouter credential storage, provider test flow, choose-engine gate sync. |
| `panel_composer.js` | `vibecomfy/comfy_nodes/web/panel_composer.js` | Composer button rendering (submit/apply/reject/undo), readiness state, notice section, settings rendering, developer/debug rendering. |
| `panel_thread.js` | `vibecomfy/comfy_nodes/web/panel_thread.js` | Chat thread bubble rendering, entry collection, display computation, history expansion, rating widget, audit detail rendering. |
| `panel_overlay.js` | `vibecomfy/comfy_nodes/web/panel_overlay.js` | Preview overlay install, invalidation, ghost dimension computation, draw model cache. |
| `panel_scheduler.js` | `vibecomfy/comfy_nodes/web/panel_scheduler.js` | Dirty-section tracking, render scheduling (microtask batching), render gateway, root-connectedness checks. |
| `panel_runtime.js` | `vibecomfy/comfy_nodes/web/panel_runtime.js` | Singleton panel instance tracker, runtime state creation/backfill, panel ID counter. |
| `agent_edit_lifecycle.js` | `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js` | Panel state machine (PANEL_STATE, transition), render section enum (RENDER_SECTIONS), obligation normalization, delta-ops normalization, chat message reconciliation. |
| `agent_edit_response_contract.js` | `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js` | Response normalizers (`normalizeAgentEditResponse`), field readers (`readApplyCandidate`, `readFieldChanges`, `readLatestCandidate`, `readRebaselineRecovery`, `readTurnIdentity`, `readStageSnapshot`), route-apply-affordance checks. |
| `agent_edit_response_contract_generated.js` | `vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js` | Auto-generated contract shapes (not hand-edited). |
| `comfy_adapter.js` | `vibecomfy/comfy_nodes/web/comfy_adapter.js` | Graph apply/delta in-place, queue guard installation, preview foreground overlay installation, typed socket labels, exec node normalization. |
| `agent_turn_feed.js` | `vibecomfy/comfy_nodes/web/agent_turn_feed.js` | Turn payload normalization, activity state derivation, activity feed reduction, progress labels, statement formatting. |
| `executor_progress.js` | `vibecomfy/comfy_nodes/web/executor_progress.js` | Executor phase normalization, progress snapshots, phase-to-progress mapping, decision/progress labels. |
| `diagnostics_reporting.js` | `vibecomfy/comfy_nodes/web/diagnostics_reporting.js` | Issue report building, audit envelopes, artifact path commits, issue modal, rating submission, browser diagnostics capture. |
| `markdown.js` | `vibecomfy/comfy_nodes/web/markdown.js` | Markdown-to-HTML rendering used by thread bubbles. |

### Planned future owner

| Module | Status | Owner Role |
|--------|--------|------------|
| `agent_candidate_actions.js` | **To be created (T4/T5)** | Candidate apply/reject visibility, eligibility selectors, `candidateActionState()`, `applyEligibility()`, `APPLY_ELIGIBILITY_REASON`. Moves existing logic; no new behavioral contract. |

---

## 2. Allowed Responsibilities per Module

### `vibecomfy_roundtrip.js` (post-M5 target)

- Import and wire dependencies from all owner modules.
- Define facade entry points: `normalizeForSerialize`, `normalizeForDisplay`, `normalizeForApply`, `repairLiveNodes`.
- Define constants scoped to orchestration: `PANEL_IDS`, `AGENT_PANEL_MOUNT_MODE`, `AGENT_SIDEBAR_TAB_ID`, `INTENT_NODE_CLASS_TYPES`, `INTENT_KIND_BY_CLASS_TYPE`, `INTENT_STYLE_BY_KIND`, `INTENT_PREVIEW_MAX`, palette colors.
- `ensureAgentPanel()` — panel creation and DOM construction.
- `submitAgentEdit()` and `postAgentRebaseline()` — submit/rebaseline orchestration (these call into lifecycle, adapters, and render scheduling).
- `renderDirtyAgentPanelSections()` / `renderAgentPanel()` — render dispatch loop (delegates to owner renderers).
- `renderAgentPanelSections()` — the dispatch switch that routes each `RENDER_SECTIONS.*` to its owning renderer.
- `fulfillLifecycleTransitionObligations()` — lifecyle obligation side effects.
- Event wiring: SSE turn events, executor phase events, canvas change listeners, queue prompt hook.
- **Must NOT contain**: status polling implementations, settings/developer/composer renderer implementations, candidate eligibility logic, stale activity strip DOM.

### `agent_status_poller.js`

- Status URL construction (`buildStatusUrl`).
- Status polling (`refreshAgentStatus`, `scheduleAgentStatusRetry`, `clearAgentStatusRetry`).
- Route status projection (`projectRouteStatus`, `routeStatusState`, `routeOptionsFromStatus`).
- Route select population (`populateRouteSelect`).
- Provider persistence (`getPersistedAgentProvider`, `setPersistedAgentProvider`).
- Credential storage (`storeOpenRouterCredential`).
- Settings persistence (`persistAgentSettings`, `testAgentSettings`).
- Choose-engine gate sync (`syncChooseEngineGate`).
- Route constants: `ROUTE_STATUS_KIND`, `ROUTE_ALIASES`, `ROUTE_LABELS`, `CANONICAL_AGENT_PROVIDERS`.
- localStorage helpers: `_lsGet`, `_lsSet`, `_lsRemove`.

### `panel_composer.js`

- Composer button rendering: `renderComposerActions`, `syncComposerButtons`, `submitReadinessState`.
- Notice section rendering: `renderComposerNotice`, `renderComposerNoticeSection`.
- Apply display state: `composerApplyDisplayState`.
- Settings rendering: `renderSettings`, `renderSettingsSection`.
- Developer/debug rendering: `renderDeveloper`, `renderDeveloperDisclosure`, `renderDeveloperSection`.

### Other modules

Each module owns the functions it exports. The shell (`vibecomfy_roundtrip.js`) imports and wires them; it should never duplicate an implementation already owned by another module.

---

## 3. Duplicate / Stale Candidates Still in `vibecomfy_roundtrip.js`

These items currently exist in `vibecomfy_roundtrip.js` but are **also owned by** (or planned to be owned by) another module. They are candidates for deletion from the shell once the replacement owner is wired in.

### 3.1 Status Poller Duplicates (owned by `agent_status_poller.js`)

| Duplicate in roundtrip | Line(s) | Canonical owner | Status |
|------------------------|---------|-----------------|--------|
| `ROUTE_STATUS_KIND` | 347–353 | `agent_status_poller.js:9` | Duplicate const; shell still references local copy |
| `ROUTE_ALIASES` | 328–337 | `agent_status_poller.js:19` | Duplicate const; different values (roundtrip has `deepseek: "openrouter"`, poller has `deepseek: "openrouter"` — same) |
| `ROUTE_LABELS` | 339–345 | `agent_status_poller.js:30` | Duplicate const; roundtrip has `deepseek` key, poller does not |
| `CANONICAL_AGENT_PROVIDERS` | 443 | `agent_status_poller.js:37` | Duplicate; roundtrip includes `"deepseek"`, poller does not |
| `getPersistedAgentProvider()` | 445–450 | `agent_status_poller.js:76` | Duplicate function; roundtrip version tolerates `deepseek`, poller remaps it |
| `setPersistedAgentProvider()` | 452–458 | `agent_status_poller.js:84` | Duplicate function |
| `_lsGet()` | 401–413 | `agent_status_poller.js:43` | Duplicate localStorage helper |
| `_lsSet()` | 415–427 | `agent_status_poller.js:54` | Duplicate localStorage helper |
| `_lsRemove()` | 429–441 | `agent_status_poller.js:65` | Duplicate localStorage helper |
| `buildStatusUrl()` | 2856–2865 | `agent_status_poller.js:94` | Duplicate function |
| `routeStatusState()` | 2868–2870 | `agent_status_poller.js:106` | Duplicate function |
| `routeOptionsFromStatus()` | 2872–2893 | `agent_status_poller.js:110` | Duplicate function |
| `clearAgentStatusRetry()` | 2896–2904 | `agent_status_poller.js:335` | Duplicate function |
| `scheduleAgentStatusRetry()` | 2906–2929 | `agent_status_poller.js:347` | Duplicate function |
| `populateRouteSelect()` | 2931–2962 | `agent_status_poller.js:377` | Duplicate function |
| `refreshAgentStatus()` | 2964–3100+ | `agent_status_poller.js:412` | **Large duplicate** — the primary poller implementation is ~200 lines in roundtrip; the canonical version is in the poller module |
| `syncChooseEngineGate()` | 3158–3186 | `agent_status_poller.js:577` | Duplicate function |

### 3.2 Settings / Developer / Composer Renderer Duplicates (owned by `panel_composer.js`)

| Duplicate in roundtrip | Line(s) | Canonical owner | Status |
|------------------------|---------|-----------------|--------|
| `renderSettings()` | 8285–8344 | `panel_composer.js:629` | Full duplicate renderer implementation |
| `renderSettingsSection()` | 8482–8485 | `panel_composer.js:703` | Thin wrapper; delegates to local `renderSettings()` |
| `renderDeveloper()` | 8121–8245 | `panel_composer.js:475` | Full duplicate renderer implementation |
| `renderDeveloperDisclosure()` | 8246–8262 | `panel_composer.js:608` | Duplicate renderer |
| `renderDeveloperSubsection()` | 8264–8283 | `panel_composer.js` (internal helper) | Duplicate helper; only exists in roundtrip |
| `renderDeveloperSection()` | 8487–8491 | `panel_composer.js:709` | Thin wrapper; delegates to local `renderDeveloper()` + `renderDeveloperDisclosure()` |

### 3.3 Candidate Apply/Eligibility Logic (planned owner: `agent_candidate_actions.js`)

| Candidate in roundtrip | Line(s) | Planned owner | Status |
|------------------------|---------|---------------|--------|
| `APPLY_ELIGIBILITY_REASON` | 263–273 | `agent_candidate_actions.js` | Defined only in roundtrip; needs extraction |
| `normalizeApplyEligibility()` | 3188–3201 | `agent_candidate_actions.js` | Eligibility normalizer |
| `noCandidateApplyEligibility()` | 3203–3210 | `agent_candidate_actions.js` | Sentinel "no candidate" eligibility |
| `ensureMissingEligibilityWarning()` | 3212–3234 | `agent_candidate_actions.js` | Warning dedup + storage |
| `missingContractApplyEligibility()` | 3236–3253 | `agent_candidate_actions.js` | "missing contract" eligibility |
| `applyEligibility()` | 3358–3369 | `agent_candidate_actions.js` | Main eligibility selector |
| `candidateActionState()` | 3420–3511 | `agent_candidate_actions.js` | Per-message candidate action state |

### 3.4 Stale State Mirrors / Legacy Compatibility (to be audited for T6/T7)

| Item | Location (approx.) | Concern |
|------|-------------------|---------|
| `AGENT_STATUS_RETRY_DELAYS_MS` | 282 | Duplicate of same const in `agent_status_poller.js:17` |
| `SETTINGS_STATUS_RENDER_SECTIONS` | 276–281 | Duplicate of same const in `panel_scheduler.js:5`; values also differ (roundtrip uses `NOTICE`, scheduler uses `DEVELOPER`) |
| `ALL_AGENT_PANEL_RENDER_SECTIONS` | 275 | Duplicate of `panel_scheduler.js:4` |
| `AGENT_PANEL_SECTION_RENDER_ERROR_LIMIT` / `AGENT_PANEL_SECTION_RENDER_RETRY_LIMIT` | 283–284 | Only used locally in render dispatch |
| `DEFAULT_EXECUTION_MODE_*` helpers | 461–494 | Settings registration that may belong in `agent_status_poller.js` or a dedicated settings module |
| `renderPendingChanges()` / activity strip DOM | TBD (audit in T6) | Legacy activity mount; may be dead code |

### 3.5 Imports Already Wired but Wrapper Functions Remain

These are correctly imported from their owners but still have thin wrappers in the shell that construct dependency objects. These wrappers are **acceptable as orchestration glue** (not duplicates) but are listed for completeness:

| Wrapper in roundtrip | Line(s) | Delegates to |
|----------------------|---------|-------------|
| `renderThreadSection()` | 8410–8412 | `renderThreadSectionImpl` (from `panel_thread.js`) |
| `renderComposerActions()` | 8451–8463 | `renderComposerActionsImpl` (from `panel_composer.js`) |
| `renderComposerNoticeSection()` | 8465–8480 | `renderComposerNoticeSectionImpl` (from `panel_composer.js`) |
| `agentPanelThreadRenderDeps()` | 8414–8449 | Deps assembly for `panel_thread.js` renderers |

---

## 4. Ownership Principles (Locked Decisions)

1. **SD1**: `vibecomfy_roundtrip.js` becomes orchestration-only: wire events in, call normalizers/reducers/selectors, invoke graph adapters, and schedule render. No renderer implementations, no poller logic, no candidate eligibility decisions.

2. **SD2**: One module owns each render surface; imports are preferred over closure-bound copies. Prevents duplicate implementations and ensures canonical ownership.

3. **SD3**: A small internal module (`agent_candidate_actions.js`) for candidate/apply selectors is acceptable as a move of existing logic, not a new behavioral contract.

---

## 5. Migration Order

| Step | Task ID(s) | Description |
|------|-----------|-------------|
| 1 | T1 | Land this ownership map **(current task)** |
| 2 | T2 | Status poller migration: delete local poller duplicates, wire `agent_status_poller.js` |
| 3 | T3 | Composer/settings delegation: delete local renderer duplicates, wire `panel_composer.js` |
| 4 | T4, T5 | Extract candidate action selectors into `agent_candidate_actions.js`, delete state mirrors |
| 5 | T6, T7 | Delete stale activity code and state mirrors |
| 6 | T8 | Shell audit of `vibecomfy_roundtrip.js` |
| 7 | T9, T10, T11 | Browser smoke test parity + final tests |
