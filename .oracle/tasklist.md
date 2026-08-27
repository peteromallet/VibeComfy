# Tasklist — onboarding mode choice (FROZEN after pre-execution review)

Base: 8a4ff90b | Branch: oracle-onboard-20260826 | Plan snapshot: f758b074b43753e7814f2b3417a04c86af134b6c3bac14d6a4edcaca171d5307 (+A1–A7 from W1 synthesis 29808c39)
Classifications finalized by oracle: ALL NORMAL (none meet the exceptional [XHARD] threshold; evidence: bounded UI-surface edits at file:line-known seams with mechanical acceptance criteria). Executor for every task: GLM 5.3 Flash (user pin).
Traceability column = agent-goal done criteria (DC1..DC5) + North Star principle/anti-pattern.

## Batch 1 — preference + uninterrupted onboarding flow
- B1-T1 explicit unset|staged|threaded semantics around key vibecomfy_agent_pipeline_mode; helpers distinguish unset; rehydrate never writes pref/field (kills roundtrip 4430–4433 violation); submit guard cancels + opens mode step when unset; no second store/backend plumbing. [DC1 DC2 DC3-partial | NS: compose-don't-duplicate, no silent defaults]
- B1-T2 mode-aware overlay flow per gate matrix {provider×mode}; syncChooseEngineGate evaluates missing-mode BEFORE provider close paths; auto-adopt cannot bypass mode ask; chooseEngineFlowOpen sentinel (A3: verify survives destroy-rebuild mount BEFORE coding, else holder swap); sentinel cleared on EVERY close path; mode-only route never shows research prompt; consequence-first copy exact:
    * Staged pipeline: "Structures each request into multiple steps (Decide → Research → Execute → Review). Works better with smaller models."
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

---
FROZEN 2026-08-26 after pre-execution contract review PASS (attempt 3, reviewer glm-5.3-flash independent). Classifications final: all NORMAL / GLM 5.3 Flash. Residual nit from v3 is stale-cache (uv run prefixes ARE in this file, line for B3-T1).
