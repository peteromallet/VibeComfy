# EXECUTOR BRIEF — Batch 1 (B1-T1..T4), single model group: GLM 5.3 Flash

You advance this North Star end state; do NOT widen scope beyond the frozen tasklist below.
Avoid these anti-patterns explicitly: jargon modal; two sources of truth; half-gated UX; unrelated overlay redesign/telemetry; silent defaults.

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

WORKTREE: current repo checkout (base 8a4ff90b). READ .oracle/tasklist.md FIRST — it is the binding spec incl. exact copy strings and the A1–A7 acceptance refinements (.oracle/findings/plan-settled-w1-synthesis.md).

IMPLEMENT:
1. B1-T1 helpers around localStorage key "vibecomfy_agent_pipeline_mode" in vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js (:409 key; settings init :3679-3681; onchange :3790-3797): distinguish unset/blank/invalid from staged/threaded (do NOT use normalizePipelineMode for presence); stop CHAT_REHYDRATE_SUCCESS path writing recovered mode into pref OR panel field (write at :4430-4433 becomes display-only historical metadata if used at all); submit guard so an unset preference CANNOT reach buildSubmitSnapshot body build (~:3213 route; funnel through createSubmitFlow agent_submit_flow.js) — cancel + open overlay mode step instead. No backend changes.
2. B1-T2 extend openChooseEngineOverlay() (~:9317) per the gate matrix in the tasklist: new mode screen as first step when explicit mode missing (even when provider present/auto-detected — syncChooseEngineGate agent_status_poller.js:895-932 evaluates missing-mode BEFORE both provider close paths); EXACT copy strings verbatim from tasklist; persist via same helper + set panel.fields.pipelineMode.value; sentinel chooseEngineFlowOpen (FIRST verify it survives the destroy-and-rebuild mount at :9321-9325 — if not, hold sentinel where it survives); every close path clears it (teardownOverlay :9399, closeChooseEngineOverlay :3096, thank-you countdown); pre-commit refresh may not wipe card selection/half-typed key; post-commit may not interrupt research/thank-you; mode-only completion closes cleanly WITHOUT research prompt or provider callbacks.
3. B1-T3 Settings select keeps staged/threaded options; unset state renders disabled placeholder option "Choose agent mode…" (never submitted as a value); subtext under select uses THE SAME shared copy constants imported by overlay (single source); onchange writes helper + field immediately.
4. B1-T4 extend existing suites (tests/browser/pipeline_mode_surface.test.mjs, roundtrip_smoke.test.mjs onboarding region ~8376+, agent_status_poller.test.mjs ~1203+): FULL matrix per tasklist incl. A1 single-funnel static ownership test (repo precedent *_ownership_static.test.mjs), A2 copy-parity string-equality + placeholder + live-field-sync tests, A5 every new case starts cleared-storage, A6 flip normalizer assertions explicitly (explicit staged fixtures/unset cases; _lsSet mocked-throw recoverable case), A4 trimmed rows (rehydrate conflicting+absent; refresh races during mode-selection + research screens; second-open-skip; auto-adopt-with-missing-mode opens AT mode).

CONSTRAINTS: no new deps; no telemetry; minimal diff; JS style matches surrounding modules; keep exports/factories patterns used by harness (tests/browser/harness.mjs). If a listed line number drifted, locate by symbol name.

VALIDATE (focused only): uv run node --test tests/browser/pipeline_mode_surface.test.mjs tests/browser/agent_status_poller.test.mjs tests/browser/roundtrip_smoke.test.mjs — iterate until green. Report files changed + test results summary (<250 words) plus any deviation from tasklist with reason.
