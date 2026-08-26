FRESH INDEPENDENT PRE-EXECUTION CONTRACT REVIEW (attempt 2 after mechanical tag fixes). Read-only. Verdict exactly PASS or issues list (<200 words).

Verify vs NORTH STAR:
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

and AGENT GOAL:
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

that the corrected TASKLIST is operationally complete and aligned; specifically re-check every task now carries a DC+NS citation or explicit none, no [XHARD] without evidence exists, single preference source of truth holds, and validation/sync clauses are unchanged and consistent:

TASKLIST (corrected):
# Tasklist — onboarding mode choice (FROZEN after pre-execution review)

Base: 8a4ff90b | Branch: oracle-onboard-20260826 | Plan snapshot: f758b074b43753e7814f2b3417a04c86af134b6c3bac14d6a4edcaca171d5307 (+A1–A7 from W1 synthesis 29808c39)
Classifications finalized by oracle: ALL NORMAL (none meet the exceptional [XHARD] threshold; evidence: bounded UI-surface edits at file:line-known seams with mechanical acceptance criteria). Executor for every task: GLM 5.3 Flash (user pin).
Traceability column = agent-goal done criteria (DC1..DC5) + North Star principle/anti-pattern.

## Batch 1 — preference + uninterrupted onboarding flow
- B1-T1 explicit unset|staged|threaded semantics around key vibecomfy_agent_pipeline_mode; helpers distinguish unset; rehydrate never writes pref/field (kills roundtrip 4430–4433 violation); submit guard cancels + opens mode step when unset; no second store/backend plumbing. [DC1 DC2 DC3-partial | NS: compose-don't-duplicate, no silent defaults]
- B1-T2 mode-aware overlay flow per gate matrix {provider×mode}; syncChooseEngineGate evaluates missing-mode BEFORE provider close paths; auto-adopt cannot bypass mode ask; chooseEngineFlowOpen sentinel (A3: verify survives destroy-rebuild mount BEFORE coding, else holder swap); sentinel cleared on EVERY close path; mode-only route never shows research prompt; consequence-first copy exact:
    * Staged pipeline: "Structures each request into steps (Decide → Research → Execute → Review). Works better with smaller models."
    * Single-thread: "One instance gets all tools in one pass. Works better with larger models." [DC1 DC2 | NS: ask-once-explain-honestly, no jargon modal]
- B1-T3 Settings: disabled "Choose agent mode…" placeholder when unset; same copy via shared constant (no drift); writes through B1-T1 helper; live field sync. [DC2 | NS: discoverable+reversible]
- B1-T4 tests (A4-trimmed matrix; A5 all start cleared-storage; A6 name the flip in pipeline_mode_surface.test.mjs normalizer cases): provider×mode grid, ready-provider auto-adopt, both choices, invalid values, submit-before-choice blocked→overlay, second open skips, rehydrate conflicting+absent, refresh races (mode-selection, research), sentinel cleanup all paths, single-funnel ownership static test (A1), copy-parity + placeholder + field-sync tests (A2), _lsSet throw recoverable case (A6). Batch checkpoint: focused browser tests green. [DC1 DC2 DC4 | NS: contract surfaces typed+tested]
## Batch 2 — gate staged chrome + live switching
- B2-T1 pipelineChromeEnabled(panel) from EXPLICIT getter only (A7); gate renderExecutorProgressRow (:832), populateAgentBubbleDetail Progress section (:1390), renderMeta phase chip (:6254); threaded pending neutral Working…; keep diagnostics/candidates/failure/queue/feed vocabulary untouched. [DC3 | NS: UI never lies; anti half-gated UX]
- B2-T2 add current mode to bubbleRenderSignature+bubbleDetailSignature; dirty THREAD(+META as needed) from Settings onchange; next-submit-only execution semantics; no event bus/per-turn stamps. [DC2 DC3 | NS: mode drives UX]
- B2-T3 paired staged/threaded/unset regressions incl. zero data-vibecomfy-executor-stage nodes in threaded; Working… present; meta chip gone; both switch directions via real handler; keyed-DOM invalidation; explicit staged fixtures for legacy tests. Checkpoint: paired evidence green. [DC2 DC3 | NS: UI never lies; anti half-gated UX]
## Batch 3 — validation + evidence
- B3-T1 run once: node --test tests/browser/*.mjs; make fast; check_ir_boundary.py → all exit 0, no weakening of unrelated assertions. [DC4 | NS: contract surfaces typed+tested]
- B3-T2 evidence under .oracle/evidence/onboarding-*.{log,md} + matrix mapping DC1–DC5 incl. NS disposition. [DC5 | NS: ask-once-explain-honest; discoverable+reversible; UI never lies]
Checkpoint/final: fresh independent full review passes → push branch to origin ONLY (no merge/deploy).
