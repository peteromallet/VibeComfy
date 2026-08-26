MECHANICAL RESEARCH BRIEF — read-only. Repo: this worktree (base 8a4ff90b).

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

RUN CONTEXT: Objective: fresh-profile onboarding asks single-thread vs pipeline once with consequence copy; choice persists into the SAME store the Settings 'Agent mode' select uses; settings reveal + explain it; threaded mode hides staged progress chrome under messages; live switching re-renders. Non-goals: no executor/stage logic changes, no telemetry, no redesign.

Explore area E3 — staged-chrome inventory & render invalidation:
1. renderExecutorProgressRow() in vibecomfy/comfy_nodes/web/panel_thread.js (~832): how the Decide→Research→Execute→Review strip renders; what DOM markers/data attributes exist (e.g. data-vibecomfy-executor-stage); what spinner copy shows per stage.
2. Expanded Progress section (~1388): where staged phase lists render inside bubble details; what must stay (candidate changes, failures, diagnostics).
3. bubbleRenderSignature()/bubbleDetailSignature() (~661): what inputs key cached DOM; would adding current mode force correct repaint on settings change?
4. The Settings onchange handler (~roundtrip 3790) and how the select persists which value; does anything dirty the thread section after change today?
5. Inventory OTHER user-facing spots that assume staged flow (agent_turn_feed.js ~332, executor_progress.js ~468, renderMeta() roundtrip ~6248). Classify each hit: ordinary chrome (should gate) vs lifecycle/diagnostic terminology (leave).
6. Existing tests: tests/browser/pipeline_mode_surface.test.mjs, active_row_rendering.test.mjs (~320), agent_status_poller.test.mjs (~1203) — what they already cover.

Report <450 words, file:line evidence, the classified inventory table, and RECOMMENDED gating boundary (single function?) for B2 implementation.
