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
