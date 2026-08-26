# Rework tasklist — batch-1 attempt 1 (from checkins/batch-1.md)
Classification: NORMAL → GLM 5.3 Flash (additive tests only; no product-code change expected).
- RW1 [G1] Contract-test the REAL WeakSet sentinel clear sites (roundtrip :3211, :9564): open overlay → close via each path incl. thank-you countdown teardown → assert isChooseEngineFlowOpen false via panel (not injected fake). [DC1 | NS: ask-once]
- RW2 [G2] Exercise phase-guard at :3199: synthetic refresh during research screen must not rebuild box or reset selection/countdown. Extend smoke case per reviewer suggestion (open→close→unset-reopen cycle). [DC1 DC2 | NS: no silent defaults]
- Left-as-is rationale (reviewer note): `writePipelineModeChoice`'s junk→staged coercion fallback stays — it is dead in practice (both callers pre-guard with `matchPipelineMode`; normalizer tests pin alias coercion at the boundary), harmless, and tightening it belongs to B3-T1 scope alongside the IR boundary work.
Acceptance: both new cases green in focused suites; zero product diffs unless a real bug surfaces (then minimal fix + note). Also record reviewer's non-blocking junk→staged coercion fallback as left-as-is rationale here.
