# Settled-plan wave W1 — synthesis (snapshot f758b074b43753e7814f2b3417a04c86af134b6c3bac14d6a4edcaca171d5307)

## Accepted
A1 [contracts+simplify] Submit-guard must sit at the verified single funnel (buildSubmitSnapshot / createSubmitFlow); add a static single-funnel ownership assertion. Evidence: roundtrip ~3213, agent_submit_flow.js:22+, pipeline_mode_surface.test.mjs:110 covers only main button.
A2 [contracts] B1-T3 needs mapped tests: unset placeholder state, live-field sync through helper writes, exact copy-parity (string-equality) between overlay choice copy and Settings subtext. Replaces non-mechanical "without documentation".
A3 [simplify g3 + E2] Verify BEFORE implementation that chooseEngineFlowOpen sentinel survives the overlay destroy-and-rebuild mount; if panel.state does not survive, hold sentinel on a surviving holder (existing overlay element presence check).
A4 [simplify g4 + contracts g3] Trim matrix: rehydrate cases = conflicting + absent; refresh-race cases = mode-selection + research screens. Legacy staged stored value needs no special cohort row (E1/contracts: key written only by Settings onchange + buggy rehydrate).
A5 [contracts g5] All new onboarding cases start from cleared storage (vacuous-pass guard).
A6 [contracts g2 + simplify g2] Name the flip: pipeline_mode_surface.test.mjs:23–27 normalizer assertions gain explicit staged fixtures/unset cases rather than silent weakening; _lsSet throw mocked case asserts recoverable explicit-choice flow (no dedicated recovery design).
A7 [simplify 3] pipelineChromeEnabled() kept; MUST derive from the new explicit-mode getter, never from DEFAULT_PIPELINE_MODE fallback.

## Rejected
R1 [simplify 1] Merge B2 into Batch 1: distinct ownership seams (preference/onboarding vs rendering/repaint); marginal handoff saving does not justify weaker checkpoint discipline. Review-count policy unchanged.

## Investigate-during-execution (non-blocking)
I1 [contracts 7] Possible predicate collapse (modeUnset && !sentinelOpen) — executor discretion.
