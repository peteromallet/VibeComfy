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

---
## Addendum (post-wave W1, host-recorded)
Settled-wave findings accepted A1–A7 above are folded into .oracle/tasklist.md acceptance criteria at freeze time (criterion-tightening, not material plan reopening). Rejected R1 recorded with rationale. Plan remains STABLE per revision v2; no further Sol loop needed because no architectural/scope change was accepted.
