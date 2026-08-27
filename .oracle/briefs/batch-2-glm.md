# EXECUTOR BRIEF — Batch 2 (B2-T1..T3): gate staged chrome + live switching

You advance the North Star end state ("the UI never lies about mode"); do not widen beyond the tasklist. Anti-patterns to avoid: half-gated UX (strip but keep staged copy elsewhere); speculative state containers/event buses; touching executor/stage logic or diagnostics vocabulary.

NORTH STAR:
# North Star — VibeComfy agent panel: one coherent assistant, user-fit execution

## End state
A ComfyUI artist opens the VibeComfy panel for the first time and, without reading docs, gets asked exactly once how they want the agent to work — single-thread (one instance with all tools) or pipeline (staged steps) — with an honest, concrete explanation of the tradeoff. Their choice is visible and changeable in Settings, and every piece of the UI that assumes pipeline structure honestly reflects their choice.

## Enduring qualities
- **Ask once, explain honestly** — the onboarding question states real tradeoffs (pipeline structures work into multiple steps → better results from smaller models; single-thread gives one instance all tools → better for larger models). No marketing gloss, no hidden default switcheroo.
- **Choice is discoverable and reversible** — settings reveal the same choice with the same explanation; switching modes re-syncs the live UI immediately.
- **The UI never lies about mode** — when single-thread is active, pipeline-only chrome (stage indicators like Decide→Research→Execute→Review under messages) disappears; when pipeline is active, it shows. Mode drives UX, not the other way round.
- **Compose, don't duplicate** — reuse the existing welcome/choose-engine overlay, the existing Agent-mode setting toggle, and existing persistence paths; new code is glue, not a parallel settings system.
- **Contract surfaces stay typed and tested** — browser contract tests keep proving ownership boundaries as the UX evolves.

## Anti-patterns
- A modal that asks without explaining, or explains with jargon ("protocol v2", "executor") instead of consequence.
- Two sources of truth for agent mode (onboarding localStorage vs settings key vs backend default drifting apart).
- Half-gated UX: hiding the stage row but still rendering staged spinner copy elsewhere.
- Redesigning the welcome overlay to smuggle in unrelated prompts or telemetry.
- Silent defaults: if onboarding is skipped, the mode used must be explicit and surfaced somewhere honest.

## Aligned progress feels like
First-run → one clear question with tradeoffs; Settings → the same choice, changeable, explained; after switching, the message area instantly matches the chosen mental model.

BINDING SPEC: read .oracle/tasklist.md Batch 2 first.

IMPLEMENT:
1. B2-T1 Add pipelineChromeEnabled(panel) deriving from the EXPLICIT preference getter from B1-T1 (NEVER from DEFAULT_PIPELINE_MODE fallback — A7). Gate exactly three display sites in vibecomfy/comfy_nodes/web/: panel_thread.js renderExecutorProgressRow (~:832) suppress strip + staged secondary label; populateAgentBubbleDetail (~:1390) suppress only staged Progress section; vibecomfy_roundtrip.js renderMeta phase chip (~:6248-6256). Threaded AND unset pending bubbles show neutral "Working…" (never blank); pipeline mode renders identical-to-base chrome.
2. B2-T2 Append current explicit mode into bubbleRenderSignature (~panel_thread.js:676) and bubbleDetailSignature (:661) so cached DOM invalidates on change; wire the existing Settings onchange handler (roundtrip ~:3790-3798, now helper-based from B1) to schedule THREAD render (+META if needed via existing scheduling primitive — find smallest existing mechanism, no new bus). Mid-flight switch changes presentation now; next submit uses new mode; never clear progress state or restart executor.
3. B2-T3 Paired regressions extending existing suites (pipeline_mode_surface.test.mjs, active_row_rendering.test.mjs ~:320): staged keeps four stage nodes/arrows/labels byte-equivalent behavior; threaded AND unset find ZERO data-vibecomfy-executor-stage nodes, no Decide/Research/Execute/Review strings in ordinary bubble/details/meta chip, Working… present; both switch directions through the REAL Settings handler prove repaint; keyed-DOM invalidation assertion; add explicit staged fixtures where older tests relied on implicit default.

VALIDATE focused until green:
uv run node --test tests/browser/pipeline_mode_surface.test.mjs tests/browser/active_row_rendering.test.mjs && uv run node --test tests/browser/roundtrip_smoke.test.mjs 2>&1 | tail -6
Report <200 words: files changed, counts, deviations with reason.
