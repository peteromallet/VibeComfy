MECHANICAL CRITIQUE BRIEF — read-only. Do NOT rewrite the plan; rank concrete simplifications/gaps with evidence (<350 words).

IMMUTABLE PLAN SNAPSHOT sha256=f758b074b43753e7814f2b3417a04c86af134b6c3bac14d6a4edcaca171d5307:
codex
Material changes. The plan now treats missing mode as a real third state, makes the onboarding gate depend on both provider and mode, prevents status refreshes from disrupting the active flow, and gates the newly identified `renderMeta()` phase chip. Resolved backend/default investigations and the redundant broad chrome audit are removed.

# Revised plan

All work remains **normal**, assigned to the user-pinned **GLM 5.3 Flash**. No task meets `[XHARD]`.

## Batch 1 — One explicit preference, one uninterrupted onboarding flow

### B1-T1 — Preserve explicit `unset | staged | threaded` semantics

- Add small read/write helpers around `vibecomfy_agent_pipeline_mode`.
- Treat missing, blank, and invalid stored values as `unset`; do not use `normalizePipelineMode()` to detect whether the user has chosen.
- Keep localStorage as the sole preference store. `panel.fields.pipelineMode.value` is only its synchronized live projection.
- Stop `CHAT_REHYDRATE_SUCCESS` from writing recovered session mode into either the preference or live Settings field.
- Before panel submission reaches the existing normalization/body builder, require an explicit mode. If absent, cancel submission and open the mode step.

Acceptance:

- No choice remains distinguishable from both valid modes.
- Onboarding and Settings write the same key through the same helper.
- Rehydration never promotes historical session metadata into the global preference.
- Every successful panel request contains the explicit chosen mode.
- Missing or corrupted preference data reopens onboarding instead of silently becoming staged.
- No backend preference, status field, or second client key is introduced.

This explicitly rejects the **silent defaults** anti-pattern. The E1 suggestion to auto-resolve and persist staged as a last resort is not adopted for the browser panel; it would manufacture a user choice. The existing normalizer may remain for canonicalization after the submit guard.

### B1-T2 — Make the existing overlay a mode-aware flow

Extend `openChooseEngineOverlay()` with a mode screen and a single transient `chooseEngineFlowOpen` sentinel. This sentinel protects flow ownership only; it is not preference state.

Flow matrix:

| Provider | Explicit mode | Result |
|---|---|---|
| Missing | Missing | Mode → existing engine flow → existing research/thanks flow |
| Present or auto-detected | Missing | Open directly at mode → close when chosen |
| Missing | Present | Existing engine flow only |
| Present or auto-detected | Present | No overlay |

Additional behavior:

- `syncChooseEngineGate()` must evaluate missing mode before taking either provider-based close path.
- Auto-detecting and persisting a ready provider must not bypass mode onboarding.
- While the sentinel is active, status refreshes must neither rebuild nor close the overlay.
- Clear the sentinel through every normal and external close path, including countdown cleanup.
- The new mode-only route must not expose the research-contribution prompt; that prompt remains only in its existing provider-selection flow.

Acceptance:

- A fresh profile cannot submit before selecting a mode.
- Both choices use the approved consequence-first copy.
- Mode is asked exactly once per explicit stored choice.
- A known or auto-detected provider opens directly at mode when mode is missing.
- Pre-commit refresh cannot erase card selection or a partially typed key.
- Post-commit refresh cannot interrupt research or thank-you screens.
- No unrelated prompt, telemetry, or overlay redesign is added.

### B1-T3 — Keep Settings honest and consistent

- Retain the existing Agent mode select.
- When no explicit choice exists, show a disabled “Choose agent mode…” placeholder rather than displaying staged as if selected.
- Share the consequence copy with onboarding so the explanations cannot drift.
- Settings writes through the same preference helper and updates the live field immediately.

Acceptance:

- After onboarding, the selected mode is visible and reversible.
- Before onboarding, Settings does not imply a choice that was never made.
- Both consequences are available without documentation.
- No additional control or settings framework is created.

### B1-T4 — Lock preference and onboarding contracts

Extend the existing browser suites to cover:

- Provider missing/present × mode missing/present.
- Ready-provider auto-detection with missing mode.
- Both mode choices.
- Missing, invalid, and persisted values.
- Submit attempted before choosing.
- Second panel open after choosing.
- Rehydration with matching, conflicting, and absent historical mode.
- Refreshes during mode, engine selection, key entry, research, and thank-you screens.
- Sentinel cleanup through every close path.

**Batch 1 checkpoint:** focused browser tests plus review confirming one preference key, no implicit browser default, and no backend mode plumbing.

---

## Batch 2 — Gate every identified piece of staged chrome

### B2-T1 — Centralize the display decision and gate all three sites

Add one small `pipelineChromeEnabled(panel)` helper. It returns true only for an explicit staged preference.

Use it at:

1. `renderExecutorProgressRow()` — suppress the four-stage strip and staged secondary label in threaded or unset mode.
2. `populateAgentBubbleDetail()` — suppress only the staged Progress section.
3. `renderMeta()` — suppress the executor phase chip.

Threaded pending bubbles show neutral `Working…`.

Keep unchanged:

- Executor events and reducers.
- Candidate changes and “Review Changes.”
- Failures, feedback, queue state, canonical activity, and backend diagnostics.
- Lifecycle terminology inside `agent_turn_feed.js`.
- Derivation helpers in `executor_progress.js`.

Acceptance:

- Staged retains the existing four stages and behavior.
- Threaded and unset modes expose no Decide/Research/Execute/Review chrome or phase chip.
- Threaded pending bubbles are not blank.
- Diagnostics are not removed merely because they mention a stage or review.

### B2-T2 — Repaint existing messages on live switching

- Add current explicit mode to both bubble render signatures.
- Dirty and render THREAD and any required META surface from the existing Settings handler.
- Do not clear progress state or restart the executor.
- Mid-flight switching updates the current UI immediately; only the next submission uses the new execution mode.

Acceptance:

- Staged → threaded removes all three staged display surfaces without reload.
- Threaded → staged restores them without altering executor state.
- Cached expanded details cannot retain stale phase lists.
- Submitted mode, Settings, and visible chrome remain synchronized.
- No per-turn mode stamp, event bus, or new state container is added.

### B2-T3 — Add paired rendering regressions

Extend existing suites with staged/threaded/unset assertions for:

- Stage nodes, arrows, secondary labels, and neutral `Working…`.
- Expanded Progress details.
- `renderMeta()` phase chip.
- Switching in both directions through the real Settings handler.
- Keyed-DOM invalidation.
- Explicit staged fixtures for older tests that previously relied on the implicit default.

**Batch 2 checkpoint:** paired rendering evidence plus review explicitly checking for half-gated strip, detail, spinner, and meta copy.

---

## Batch 3 — Authoritative validation and completion evidence

### B3-T1 — Run validation

Run once after focused tests pass:

```text
uv run node --test tests/browser/*.mjs
uv run make fast
uv run python scripts/check_ir_boundary.py
```

All commands must exit zero. Do not weaken existing staged assertions or characterize unrelated failures as success.

### B3-T2 — Produce the evidence matrix

Preserve focused and full outputs under `.oracle/evidence/` and create a new onboarding-mode matrix covering:

- Mode choice and single-source ownership.
- Provider/mode gate matrix.
- Overlay refresh-race protection.
- Rehydration precedence.
- All three staged-chrome boundaries.
- Live switching.
- North Star and anti-pattern disposition.

Do not overwrite prior campaign evidence.

**Batch 3 checkpoint:** all done criteria, full validation, clean IR boundary, and final oracle review. Push may follow review; merge and deployment remain unauthorized.

# Explicit anti-pattern rejections

- **Modal without consequences or with jargon:** rejected; both choices use the same consequence-first copy.
- **Two sources of truth:** rejected; localStorage remains the sole preference, while the field is only a synchronized projection and session metadata stays historical.
- **Half-gated UX:** rejected; strip, secondary pending text, expanded Progress section, and `renderMeta()` phase chip are gated together.
- **Unrelated overlay redesign or prompts:** rejected; the existing flow is extended minimally, and research contribution is not added to mode-only onboarding.
- **Silent defaults:** rejected; missing or invalid mode blocks submission and asks the question. The browser does not inherit the backend environment default or silently select staged.

# Remaining exploration before implementation

Only narrow implementation checks remain:

1. Map every overlay exit path so the sentinel and thank-you countdown are always cleaned up.
2. Identify the smallest existing render-scheduling primitive that reliably repaints both THREAD and META.
3. Verify mode-only completion can close cleanly without invoking provider-selection callbacks or research onboarding.
4. Confirm localStorage failure handling leaves the user in a recoverable explicit-choice flow rather than a reopen loop.
5. Check whether any nonstandard submit entry point bypasses the main panel submit guard.

# Potential issues

- A stale sentinel could permanently suppress onboarding if an exceptional close path misses cleanup.
- Status refresh may arrive between persisting mode and advancing to the next screen; the sentinel must cover the entire sequence.
- Existing tests that implicitly assume staged mode will need explicit staged fixtures, not relaxed expectations.
- The disabled unset option must not accidentally be submitted as a valid value.
- Switching mid-flight deliberately changes the current bubble’s presentation while leaving its running executor unchanged; tests should make that resolved behavior unmistakable.
- Shared consequence copy should remain UI-neutral and avoid importing rendering concerns into submission code.

The resolved backend-default, rehydration-ownership, broad chrome-inventory, and curated Makefile-target questions are removed from exploration. Estimated effort tightens to **3–5 working days**; this remains a single non-huge run.

NORTH STAR:
# North Star — VibeComfy agent panel: one coherent assistant, user-fit execution

## End state
A ComfyUI artist opens the VibeComfy panel for the first time and, without reading docs, gets asked exactly once how they want the agent to work — single-thread (one instance with all tools) or pipeline (staged steps) — with an honest, concrete explanation of the tradeoff. Their choice is visible and changeable in Settings, and every piece of the UI that assumes pipeline structure honestly reflects their choice.

## Enduring qualities
- **Ask once, explain honestly** — the onboarding question states real tradeoffs (pipeline structures work into multiple steps → better results from smaller models; single-thread gives one instance all tools → better for larger models). No marketing gloss, no hidden default switcheroo.
- **Choice is discoverable and reversible** — settings reveal the same choice with the same explanation; switching modes re-syncs the live UI immediately.
- **The UI never lies about mode** — when single-thread is active, pipeline-only chrome (stage indicators like Decide→Research→Execute→Review under messages) disappears; when pipeline is active, it shows. Mode drives UX, not the other way round.
- **Compose, don't duplicate** — reuse the existing welcome/choose-engine overlay, the existing Agent-mode setting toggle, and existing persistence paths; new code is glue, not a parallel settings system.
- **Contract surfaces stay typed and tested** — browser contract tests keep proving ownership boundaries as the UX evolves.

## Anti-patterns
- A modal that asks without explaining, or explains with jargon ("protocol v2", "executor") instead of consequence.
- Two sources of truth for agent mode (onboarding localStorage vs settings key vs backend default drifting apart).
- Half-gated UX: hiding the stage row but still rendering staged spinner copy elsewhere.
- Redesigning the welcome overlay to smuggle in unrelated prompts or telemetry.
- Silent defaults: if onboarding is skipped, the mode used must be explicit and surfaced somewhere honest.

## Aligned progress feels like
First-run → one clear question with tradeoffs; Settings → the same choice, changeable, explained; after switching, the message area instantly matches the chosen mental model.

FROZEN AGENT GOAL:
# Agent goal — onboarding mode choice (single-thread vs pipeline)

Source ref: `8a4ff90b356a07d43021e3d6255adae36678b227` (`origin/main`, branch `main`)
Worktree: `../vibecomfy-oracle-onboard` branch `oracle-onboard-20260826`
Previous campaign North Star snapshot: `.oracle/findings/northstar-previous-schema-campaign-snapshot.md`
(sha256 of pre-existing northstar.md at snapshot time: d9b4d1d294e11054bb145ab539f1fea28b1cd031234955c4a5393b49aa9928bd, source path `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.oracle/northstar.md` — campaign-scoped, superseded for this run by [North Star](./northstar.md))

[North Star](./northstar.md) — this run advances "one coherent assistant, user-fit execution": first-run asks the mode question with honest tradeoffs; settings reveal it; pipeline chrome respects the choice.

## Objective
1. **Onboarding ask** — when the agent panel first runs for a user (fresh browser profile / no prior choice persisted), the existing welcome overlay additionally asks: single-thread vs pipeline, with consequence-first copy:
   - Pipeline: structures each request into multiple steps (Decide → Research → Execute → Review). Works better with smaller models.
   - Single-thread: one instance gets all tools in one pass. Works better with larger models.
2. **Persistence** — choice lands in the SAME store the settings Agent-mode toggle reads/writes today (single source of truth; backend default respected unless user chose).
3. **Settings reveal** — Settings keeps/extends the existing "Agent mode: Staged pipeline | Threaded agent" control so it shows which mode is active and carries the same tradeoff explanation (tooltip/subtext), changeable at any time.
4. **Mode-honest UX** — when single-thread is active the staged indicator below messages ("Decide→Research→Execute→Review" / stage chips) is not rendered; any other pipeline-only affordances discovered during exploration get the same treatment. Switching modes live updates without reload if feasible.

## In scope
- Frontend: welcome overlay flow, settings panel agent-mode control, message-stage rendering gate, persistence glue.
- Minimal backend/config touch ONLY to expose current mode to the UI or honor a stored preference if not already wired.
- Browser contract tests updated/added for: onboarding ask appears once + persists; settings reflects choice; stage row hidden in single-thread.

## Non-goals
- No new model providers, no changes to executor internals/stage logic itself.
- No redesign beyond mode-gating and copy.
- No telemetry/analytics additions.
- No migration of unrelated settings.

## Settled decisions
- Reuse existing welcomeOverlay + existing agent-mode setting key; do not invent a parallel store.
- Tradeoff copy wording as in Objective 1 (consequence-first, plain language).

## Open boundaries
- Exact visual placement inside the welcome overlay = explorer's call within current overlay structure.
- Whether backend already persists agent-mode preference per session/profile — explorer verifies; if server-side default exists, frontend must show what will actually be used before first submit.

## Model policy (user-declared)
- Normal tasks: **GLM 5.3 Flash** (user pin).
- [XHARD] tasks: **Grok 4.6** (user pin). Expected count: 0 — this is scoped UI work.

## Authorization boundaries
- Mutations only inside worktree `../vibecomfy-oracle-onboard`.
- Sync to origin: stage reviewed paths onto `oracle-onboard-20260826`; push that branch to `origin` explicitly. NO merge to `main`, NO deploy. Merge-to-main is a separate user-authorized action after review.

## Done criteria (all required)
1. Fresh-profile panel open surfaces the mode question once; answering persists; second open does NOT re-ask (already-chosen state skips to ready) but Settings can still change it.
2. Settings control reflects chosen mode, explains tradeoffs, switching takes effect (stage row visibility matches immediately or on next render).
3. Single-thread: no staged indicator under messages; pipeline: unchanged behavior from base.
4. `uv run node --test tests/browser/*.mjs` green (incl. new tests); `make fast` green; IR boundary clean.
5. Evidence matrix maps each done criterion to command output under `.oracle/evidence/`.

## Stop criteria
All done criteria met and final oracle review passes; OR blocked/failed classification recorded in status.md.

## Final validation commands
- `uv run node --test tests/browser/*.mjs`
- `uv run make fast`
- `uv run python scripts/check_ir_boundary.py`
- Targeted: the new onboarding/settings contract test files.

## Sync/promotion policy
Push reviewed `oracle-onboard-20260826` to origin only. Report PR-readiness; do not merge.

Lens: STREAMLINING. Challenge whether the outcome can be reached with less work/fewer handoffs; whether any proposed abstraction/interface/helper is speculative (e.g., is pipelineChromeEnabled() justified vs inline checks? Is chooseEngineFlowOpen sentinel minimal? Are there batches that should merge?); whether existing mechanisms suffice; flag overengineering specifically.
