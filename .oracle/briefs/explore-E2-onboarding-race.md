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

Explore area E2 — welcome overlay structure & races:
1. Map openChooseEngineOverlay() in vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js (~9317): current screens/steps (provider choose, research-contribution ack?), how buttons write choices, how the overlay closes.
2. commitRoute() (~9411): what happens when provider status refresh lands while overlay is open — can it tear down/reopen mid-flow (race with syncChooseEngineGate() in agent_status_poller.js ~895)?
3. Rehydration: normalizeChatRehydratePayload() (~5128), CHAT_REHYDRATE_SUCCESS lifecycle path, and the write near line 4430 — confirm whether recovering an old session writes its historical pipeline_mode into the global localStorage key (would violate single-source precedence).
4. Where does the overlay sequence decide "first run"? What exactly triggers reopen?

Report <400 words, file:line evidence, ranked facts, and RECOMMENDED minimal insertion point for a new mode-choice step (independent of engine/provider step), incl. how to keep overlay alive across status refreshes. No redesign proposals.
