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

Explore area E1 — submit-path mode resolution & backend default semantics:
1. Trace how a panel submit resolves pipeline_mode today: buildSubmitSnapshot() in vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js (~line 3213), buildSubmitBody()/pipeline_mode handling in vibecomfy/comfy_nodes/web/agent_submit_flow.js (~line 22+60), and the localStorage key vibecomfy_agent_pipeline_mode (~line 409 area).
2. Can any real submit path bypass the mandatory welcome overlay while NO explicit preference is persisted? Identify exact gate conditions (syncChooseEngineGate() in vibecomfy/comfy_nodes/web/agent_status_poller.js ~895).
3. Backend: resolve_orchestration_mode() in vibecomfy/executor/contracts.py (~148) + VIBECOMFY_EXECUTOR_PIPELINE_MODE usage across vibecomfy/. Is that env var consumed by browser-panel sessions or only headless? Does /vibecomfy/agent/status (_handle_agent_status in vibecomfy/comfy_nodes/agent/routes.py ~502) expose any effective/default mode?
4. Answer Sol's open questions: Q1 can a submit bypass overlay without stored preference? Q2 should env default be surfaced as panel default or stays backend-only?

Report <400 words, ranked facts with file:line evidence, then a RECOMMENDED approach for preference precedence (missing vs staged vs threaded distinguished; no second store). No architecture invention.
