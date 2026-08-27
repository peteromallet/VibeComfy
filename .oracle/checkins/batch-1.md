# ORACLE CHECK-IN REVIEW — Batch 1 (independent pass, 2026-08-26)

Delta: `git diff 9a6552b0..1447e6fe` (commit 1447e6fe, worktree oracle-onboard-20260826).

## Checks
1. **Coverage** — Most B1 acceptance criteria have code site + test (below). Two tasklist-mandated cases have NO test.
2. **Single source of truth** — Only browser store is `vibecomfy_agent_pipeline_mode` (vibecomfy_roundtrip.js#3B67:410; grep across web/ shows no second key). Writes go exclusively through `writePipelineModeChoice` (:448); callsites: settings onchange :3937, overlay continue :9977. Rehydrate (:4439–4560) reads `payload.pipelineMode` into lifecyclePayload only — writes nothing to pref or field; proven by tests :418/:457. In-memory session mirror :430 is cache, not a second store; `_lsSet`-throw recovery keeps explicit choice submit-eligible (test :357).
3. **Sentinel** — Module-scope `WeakSet` keyed by panel object (:488–504). Panel object survives the overlay destroy-and-rebuild mount, so A3 durability holds structurally (marked :9506 before mount rebuild; A3 was verified-before-code per comment). Cleared on both teardown paths: `closeChooseEngineOverlay` :3211 and in-overlay `teardownOverlay` :9564 (covers countdown expiry :10066 and mode-only completion :9984). Post-commit research/thanks screens own lifetime via phase guard :3199. No click-outside/ESC path exists. Unit gate tests fake `isChooseEngineFlowOpen`, so real-WeakSet cleanup is covered only indirectly (see issue G1).
4. **Copy** — `AGENT_PIPELINE_MODE_COPY` (roundtrip:414–417) verbatim vs frozen wording incl. "multiple steps"; shared constant feeds Settings hint (:473–475) and overlay tiles; parity enforced against independent string literals in pipeline_mode_surface.test.mjs:21–23, asserted at :266/:272/:325–326. Placeholder "Choose agent mode…" disabled option :3781–3785, tested :261. No jargon anywhere in shipped strings.
5. **Scope** — No stage-chrome gating (`pipelineChromeEnabled` absent; renderExecutorProgressRow untouched) → B2 not started early. No telemetry, no new deps (7-file stat confirmed); harness gains only `seedPipelineMode`. The funnel guard sits at buildSubmitSnapshot (:3326, error code at single funnel) + STOP_ABORT handler restores draft and opens mode step (:8496–8507); static single-funnel ownership test :204 (A1 ✓).
6. **Tests** — `uv run node --test tests/browser/pipeline_mode_surface.test.mjs tests/browser/agent_status_poller.test.mjs` exit 0; `uv run node --test tests/browser/roundtrip_smoke.test.mjs` exit 0, 256 pass / 0 fail. Gate grid covered: persisted×unset opens-at-mode-not-close (poller :1330), ready-autoadopt cannot bypass + second-open skip (:1352), unset×LOADING defer (:1392), no-shell (:1409). Surface: blocked-submit→overlay→no-request→draft-returned→honest thread narration→threaded chosen→same prompt submits `pipeline_mode:"threaded"` (:284–356); DeepSeek auto-adopt smoke now expects mode-first screen and research-skip (:8514–8527).
7. Alignment/disposition below.

## Issues (both small, additive-test-sized)
- **G1 — listed sentinel cleanup coverage absent.** B1-T4 froze "sentinel cleanup all paths"; no test drives a real open→close cycle through the live `WeakSet` (gate unit tests inject fake `isChooseEngineFlowOpen`). Code reads correct (two clear sites, co-located), so risk is regression-silence, not current behavior.
- **G2 — listed research refresh-race case untested.** B1-T4 froze "refresh races (mode-selection, research)". Mode-selection race is covered (poller :1392, :1352 second-call). The NEW phase guard at roundtrip:3199 (research/thanks survive a status-refresh close attempt) has zero test exercise; `git show 9a6552b0` confirms the guard is new code, so a silent weakening would go unnoticed.

Non-blocking notes: `writePipelineModeChoice`'s junk→staged coercion fallback is dead-in-practice (both callers pre-guard with `matchPipelineMode`) — harmless, consider tightening in B3. IR boundary / `make fast` remain B3-T1 scope per plan.

## Disposition
Fix-forward within Batch 3: add one smoke case cycling open→close→blocked-submit-reopen (kills G1+G2 together by asserting the research screen survives a synthetic refresh), then final full validation stands unchanged.

## North Star alignment
Ask-once-explain-honest ✓ (consequence-first copy, mode leads flow); discoverable+reversible ✓ (shared constant, helper-mediated writes, live field sync); compose-don't-duplicate ✓ (one store, no parallel settings, no event bus); no silent defaults ✓ (submit refused unset, cancel narrated honestly). Anti-patterns clear. B1 advances the North Star as specified except for the two frozen-case coverage gaps above.
