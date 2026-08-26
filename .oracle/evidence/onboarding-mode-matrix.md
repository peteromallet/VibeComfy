# Evidence matrix — DC → evidence (run base 8a4ff90b356a07d43021e3d6255adae36678b227 → 5454de9b9b686b60dbadf24191216b7ef4e03932)

| DC | Criterion | Evidence |
|---|---|---|
| DC1 | Fresh profile asked once; persists; no re-ask; auto-adopt cannot bypass; submit-before-choice blocked | tests/browser/pipeline_mode_surface.test.mjs (gate-matrix + funnel-guard + re-ask cases, :239-536 region), roundtrip_smoke onboarding block (:8448-8591); checkins/batch-1-rework.md PASS |
| DC2 | Settings reflect/explain/switch live; copy parity | shared copy constant consumed overlay+Settings; parity + placeholder + field-sync tests; B2 real-handler both-direction switch tests; checkins/batch-2.md PASS |
| DC3 | Threaded/unset hide staged chrome incl meta chip; staged byte-equivalent; Working… present | active_row_rendering + surface paired regressions (zero stage nodes/chips, neutral row); B2 gate sites roundtrip:464/:6414, panel_thread:884/:1455 |
| DC4 | Broad suites green | evidence/onboarding-browser.log (1670 total, 1668 pass, 0 fail, 2 pre-existing skips); evidence/onboarding-fast.log (571 passed, 9 skipped = base parity); evidence/onboarding-ir.log clean. Note: first fast attempt exit 2 = missing pytest in fresh worktree venv (host env error), superseded by logged 571-pass rerun after uv sync --extra dev |
| DC5 | This matrix + NS disposition | this file + checkins/final-overall.md |

Model policy honored: normal=GLM 5.3 Flash (user pin) executed all tasks/checkins; [XHARD]=Grok 4.6 unused (0 qualifying tasks).
