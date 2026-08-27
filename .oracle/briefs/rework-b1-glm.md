REWORK EXECUTION — implement .oracle/rework/batch-1-attempt-1.md (RW1, RW2) exactly. Additive browser contract tests only; touch product code ONLY if a test exposes a real defect (minimal diff + explain). Reuse existing harness patterns; all cases start from cleared storage. Validate focused suites to green:
uv run node --test tests/browser/pipeline_mode_surface.test.mjs tests/browser/agent_status_poller.test.mjs && uv run node --test tests/browser/roundtrip_smoke.test.mjs 2>&1 | tail -6
Report <150 words: files changed, new case names, final counts.
