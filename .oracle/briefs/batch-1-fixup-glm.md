COMPLETION FIX BRIEF — Batch 1 was interrupted by timeout; code landed but 5 tests fail with unhandledRejection 'cardRegistry is not defined' / 'selectedRoute is not defined' at tests/browser/pipeline_mode_surface.test.m.js cases starting lines 239, 284, 357, 418, 457 (stack points into syncChooseEngineGate → agent_status_poller.js:773→ refreshAgentStatus path reaching vibecomfy_roundtrip.js ~3158).

TASKS:
1. In vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js find every remaining reference to identifiers cardRegistry / selectedRoute that are no longer defined in scope after the mode-flow refactor; either restore proper definitions per the current design (mode-aware choose-engine flow: sentinel chooseEngineFlowOpen; gate matrix in .oracle/tasklist.md) or reroute those call sites through the new helpers.
2. Ensure syncChooseEngineGate early-return logic doesn't depend on removed globals.
3. Re-run until green: uv run node --test tests/browser/pipeline_mode_surface.test.mjs tests/browser/agent_status_poller.test.mjs
4. Then run full focused set incl. roundtrip_smoke.test.mjs and report pass counts + list of changed lines (<150 words).

Do NOT widen scope beyond making Batch 1 acceptance true (tasklist B1-T1..T4).
