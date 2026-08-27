# ORACLE CHECK-IN REVIEW — Batch 2 (independent pass, 2026-08-26)

## VERDICT: **PASS**

Delta audited: `git diff HEAD~1..HEAD` = c8406830 (B2 only, 5 files, +355/−9).

**1. Gate sites real, explicit-only.** Three sites present: pending row panel_thread.js:884, Progress detail :1455, meta chip vibecomfy_roundtrip.js:6414. `pipelineChromeEnabled` = `readPipelineModeChoice().mode === "staged"`; thread-side `stagedChromeForDeps` ← `explicitPipelineModeForDeps` ← strict `matchPipelineMode`, getter fallback to raw storage read. DEFAULT_PIPELINE_MODE touches only backend-payload parse (:5289) and request boundary (agent_submit_flow.js:110) — never display. A7 satisfied. All three renderer entry points inject the shared getter (roundtrip :6450/:6471/:6611); unwired fallback still explicit-storage-only, so no leak path exists either way.

**2. Threaded/unset honesty.** active_row_rendering.test.mjs asserts zero `data-vibecomfy-executor-stage`, zero phase chips, exactly one neutral `Working…` (dataset.vibecomfyPendingNeutral), no stage vocabulary in bubble OR opened details pane (half-gated tripwire exercised: Progress section stays hidden while snapshot.progress exists). Staged bytes pinned by two explicit localStorage fixtures added to legacy staged tests (A6 honored, no weakening); round-trip switch restores deep-equal stage-node dataset sequence.

**3. Signatures + switching.** Mode appended to both bubbleDetailSignature (:715) and bubbleRenderSignature (:754 area), source-contract-tested ≥2 occurrences. Live test drives real Settings `onchange()` both directions mid-flight: keyed bubble object identity reused (no remount), storage written, THREAD+META repaint via pre-existing `scheduleRenderAgentPanel` (16 refs at HEAD~1 — no event bus/container), executorProgress and message objects untouched → next-submit-only semantics hold by construction (submit-time reads at :3333/:8574).

**4. Scope clean.** Only the three gates + signatures + onchange repaint changed; diagnostics/candidate/failure/queue/feed vocabulary untouched; executor logic untouched.

**5. Focused suites self-run:** `node --test pipeline_mode_surface active_row_rendering roundtrip_smoke` → **297 pass / 0 fail / 2 skipped** (pre-existing retired-migration `test.skip` at smoke:6869/:6999), exit 0, 142s.

**6. NS disposition.** "UI never lies about mode" front and center: explicit-staged-or-nothing gating, honest Working… placeholder for threaded *and* unset (no silent defaults), live reversible switching, composed from existing store/scheduler/render paths. No half-gated UX observed anywhere in shipped surfaces.

Notes (non-blocking, none require action): gated sites take an unused `panel` arg (signature-compat cosmetics); unset-details-pane path untested directly but shares the identical single-condition gate pinned by source contract; `writePipelineModeChoice` junk→staged coercion remains dead-in-practice (batch-1 note, B3 tightening).
