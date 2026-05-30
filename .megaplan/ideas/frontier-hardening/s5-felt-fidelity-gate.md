# S5 — felt-fidelity-gate: the trust lens, the buildable-now slice

## Outcome
A re-emit that is semantically faithful but **visually jarring** is caught before it ships: untouched
nodes and surviving reroutes that move unexpectedly, or a round-trip that is too slow, **fail a gate** —
not just a `print`. (The preview/undo UX itself belongs to the future write-enabled editor, NOT here.)

## Why (the gremlin)
Roadmap §14 lens 1. Every gate measures API-equality or geometric Δpos on uid-matched nodes; none measures
what the USER feels: untouched nodes subtly re-laid-out, the user's organizational reroutes silently
rationalized by ingest's many-to-one normalization (felt-catastrophic, geometrically invisible), or a
multi-second round-trip that kills the magic. The "change report" is a `print`, not an approvable artifact.
Latency is gated nowhere. Trust is a single-surprise cliff.

## Scope — IN
- A **felt-delta gate**: assert that nodes/reroutes the agent did NOT touch do not move or get rationalized
  unexpectedly on re-emit. Reuse scratchpad-emitter m5's **system-computed touched/untouched delta**
  (§0 Step 0); block on any unintended visual move of an untouched node OR a collapsed-without-cause reroute.
- A **latency budget gate**: measure the full `ingest→emit (+oracle)` wall-time on the ~90-node music-video
  monster; fail if it exceeds a declared budget.
- Promote the change-report from a `print` into a **structured artifact** (the data a future preview UI
  renders) — persisted, not logged.

## Scope — OUT
- The previewable/approvable diff UI and one-keystroke undo — those are the WRITE-ENABLED editor (future m8);
  they can't exist for a read-only surface. This sprint builds the MEASUREMENT, not the UX.

## Locked decisions
- Felt-fidelity is a THIRD axis alongside semantic + geometric fidelity, with its own gate.
- The change-report becomes structured data (consumable by a UI), not a human-only log line.

## Open questions (resolve in planning)
- The felt-delta threshold (what magnitude of untouched-node movement is "unexpected" vs acceptable reflow).
- The latency budget number (measure first, then set).
- Reroute-rationalization detection: how to flag "the user's Get/Set furniture changed without a structural cause".

## Constraints
- Depends on m5's touched/untouched delta being on `main` (ordered LAST for this reason). If absent, compute
  a minimal delta locally rather than blocking.
- Offline/deterministic; the latency gate must be machine-stable enough to not flake CI.

## Done criteria
- A synthetic "+8px on one untouched node" (and a "reroute collapsed without cause") fixture **fails** the
  felt-delta gate — proving falsifiability (land it RED first).
- The latency gate fails on a deliberately-slowed run and passes within budget on the monster.
- The change-report is emitted as structured JSON (preserved / new-auto-placed / removed / moved), persisted.

## Touchpoints
- `vibecomfy/porting/ui_emitter.py` (re-emit path + the report), `vibecomfy/porting/layout/` (felt-delta
  over positions), the touched/untouched delta from m5, `tests/` (felt-delta + latency fixtures).

## Anti-scope
- No editor JS / preview UI / undo wiring (future m8). Don't rebuild m5's delta — consume it.
- Don't change semantic or geometric gates; ADD the felt axis alongside them.

## Handoff artifact
A structured change-report + the felt-delta + latency gates — the measurement substrate a future
write-enabled editor's preview/undo UX will render.
