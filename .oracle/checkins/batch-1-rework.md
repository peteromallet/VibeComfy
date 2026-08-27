# ORACLE RE-REVIEW — Batch 1 rework attempt 1 (independent pass, 2026-08-26)

Delta reviewed: `git diff 1447e6fe..f4367eb5` — strictly additive (347 insertions, 0 deletions): `pipeline_mode_surface.test.mjs` (+181), `roundtrip_smoke.test.mjs` (+151), `.oracle/rework/batch-1-attempt-1.md`, `.oracle/findings/rework-b1-report.txt`. No product surface touched; anchors from prior verdict re-verified unchanged by independent scout sweep (8/8 HOLD).

## VERDICT: PASS

## Evidence
1. **RW1 [G1] real-path sentinel-clear** (`pipeline_mode_surface.test.mjs:374–536`): drives production deps via `invokeCommand("VibeComfy.AgentEdit")` → `openAgentPanel` → `syncChooseEngineGate` with the real `isChooseEngineFlowOpen` closure (:3157) — zero injected fakes. Refresh-during-engine-cards asserts overlay element identity + full child-node identity + selection survival; decline→thanks→natural countdown expiry routes through `teardownOverlay` (:9558 via :10066) then storage removeItem flips mode-missing and the gate REMOUNTS at the mode step — passes only if the WeakSet entry was genuinely cleared (the exact regression-silence G1 froze). Re-mark guard + mode-only Continue (:9984) close without research prompt.
2. **RW2 [G2] refresh races** (`roundtrip_smoke.test.mjs:8448–8591`): synthetic refresh DURING research screen and DURING live thank-you countdown both preserve box node identity, button references, enabled state; natural expiry completes the open→close leg; unset re-asks as a genuinely fresh mount (`assert.notEqual`), starts at mode step, mode-only choice persists.
3. **Suites green (run by reviewer)**: focused triple `pipeline_mode_surface` + `agent_status_poller` + `roundtrip_smoke` → 333 tests, 331 pass, 0 fail, 2 skipped (pre-existing retired-migration skips, untouched by this campaign).
4. **Prior-PASS items re-spot-checked**: single store key :410; all pref writes via `writePipelineModeChoice` :448 (callsites :3937 settings, :9977 overlay); WeakSet :488/mark :9506/clears :3211+:9564; phase guard :3199 verbatim; copy constant :414–417 verbatim, Settings hint :474 + tiles :9934 consume it, no duplicated literals; funnel guard throws before serialize (:3320–3340), handler restores draft + opens mode step (:8486–8507); static single-funnel ownership test present; `pipelineChromeEnabled` absent (B2 not started early); no `localStorage.setItem` bypass.

## Residual (non-blocking, defer to B3)
Clear site A (`closeChooseEngineOverlay`:3211) is executed on real paths but its effect after a *real* mark through a gate-mediated close is not discriminated (gate SKIPs close while flowOpen, so that path is near-unreachable by design; site A also runs harmlessly on already-closed panels). RW1's frozen scope was exactly countdown-teardown + unset re-ask, which is met.

## North Star alignment disposition
Ask-once-explain-honest ✓ (verbatim consequence-first copy; completed flow never flappily re-asked — now proven behaviorally); discoverable+reversible ✓; compose-don't-duplicate ✓ (one store, one helper, no new chrome or systems); no silent defaults ✓ (unset blocks submit honestly and re-ask path is contract-tested both directions). UI never lies: B2 untouched early, phase guard now regression-fenced. Batch 1 conforms to the North Star; campaign proceeds to Batch 2 unchanged.
