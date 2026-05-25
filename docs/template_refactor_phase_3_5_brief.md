# Phase 3.5: Block A extension + port_check_blocked triage + wanvideo bug fix

## Outcome

Resolve the three categories of residuals from Phase 3 (`phase-3-sprint-brief-20260525-1151`):
extend the emitter's helper resolution to cover the *prep-enumerated* set of helper shapes actually present in runexx + kijai community workflows; produce a categorized triage of the 48 source-backed templates that Phase 3's T12 reported as `port_check_blocked`, with per-template disposition applied; and fix the one wanvideo template Python bug that blocks its re-emit.

Tracked in ticket `01KSG35MTEE2AASAHB3M8NQHY6` (`.megaplan/tickets/`).

## Scope

**IN scope** — concrete items:

- **A.** Extend `_resolve_helper_nodes_for_emission()` in `vibecomfy/porting/emitter.py` (and `vibecomfy/porting/helpers.py` if needed) to cover the helper shapes prep enumerates from `workflow_corpus/community/runexx/*.json` and `workflow_corpus/community/kijai/*.json` — the actual shapes present in the corpus, not the universal set.
- **B.** Build a categorized triage of the source-backed templates from `workflow_corpus/manifests/coverage.json` that currently fail `port check`. For each: name the failure category (custom-node missing / schema mismatch / unknown widget / structurally unportable / other), and assign a per-template disposition: fix the source, mark `# vibecomfy: manual` with rationale, or remove from `coverage.json` with reason.
- **C.** Apply the dispositions from B. For source-fix dispositions, patch the source JSON. For manual-marker dispositions, add the `# vibecomfy: manual` marker with a one-line rationale comment. For remove-from-coverage dispositions, edit `coverage.json` accordingly.
- **D.** Fix the `UnboundLocalError: image_b` in `ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py` and re-emit it via `port reemit`.
- **E.** Re-emit the named subset of templates that the newly-extended Block A enables to handle cleanly. Each re-emit is its own action; this is not a bulk `--all` flag.
- **F.** Add fixtures to `tests/test_broadcast_helper_resolution.py` covering each new helper shape from A.
- **G.** Update `docs/template_provenance_gaps.md` and `docs/widget_alias_resolution.md` with the triage outcomes and any new emitter-coverage notes.

**OUT of scope** — explicit:

- Speculative emitter extension for helper shapes not present in the in-corpus JSONs prep enumerates.
- Bulk modification of the 48 blocked templates without per-template triage (avoid Phase 3 T12's failure mode of conflating blocked with succeeded).
- A new external `verify` phase (that's a separate megaplan effort, tracked in megaplan ticket `01KSG32AJZ0YC21T3JVKXVB0HD` and the conversation that birthed it).
- Refactoring `_resolve_helper_nodes_for_emission()` for clarity unrelated to the new coverage.
- `music_video_low_ram.py` rewrites if prep reveals the workflow is structurally unportable — accept `# vibecomfy: manual` and document, do NOT extend the emitter for one template's worth of work.
- Phase 2's lifecycle / PUBLIC_INPUTS / VibeComfyError work is closed — do not revisit.

## Locked decisions

- **Brief follows the "enumerate before promising completeness" rule.** Universal quantifiers ("all", "every", "no", "100%", "complete") are not in success criteria. Every criterion targets a named or prep-enumerated set.
- **Single-type sprint (execution-after-prep).** Prep produces the enumerations (A and B); execute targets the enumerated items. Audit work belongs to prep, not execute.
- **Validation is external.** Sprint does not include "run pytest" or "verify nothing broke" as execute tasks. The existing pytest suite + `tools.refresh_template_index --check` are run by the human/CI after the sprint lands. The sprint produces the commits; the truth signal comes from the test runner.
- **Use `port reemit` per template, never a bulk regen flag.** Per-template visibility prevents the batch-success-overstating pattern that bit Phase 3 T12.
- **Per-template `# vibecomfy: manual` decisions require a one-line rationale comment** explaining why it's manual. Auditable, not arbitrary.
- **Build on top of `scratchpad-emitter`**, do not rebase or modify Phase 3 commits.
- **`--vendor codex`** for this sprint per user direction.

## Open questions (for prep)

These are exactly the things prep should answer; the planner should not invent answers:

1. What helper-node shapes (class_type / `_outputs` / `widget_N` / kwargs patterns) are *actually* present in `workflow_corpus/community/runexx/*.json` and `workflow_corpus/community/kijai/*.json`? Enumerate.
2. For each shape, does the current `_resolve_helper_nodes_for_emission()` handle it? Map each shape to handled / unhandled.
3. What are the failure-categories of the 57 source-backed templates that currently fail `port check`? Categorize each by reason. (Phase 3 T12 reported 48 blocked; verify the current number.)
4. Of the categorized blockers: which deserve source-side fixes, which should become `# vibecomfy: manual`, which should be removed from `coverage.json`? Prep proposes; plan locks in.
5. Does a `port check --batch` mode exist already, or does prep need a small ad-hoc script to aggregate per-template port_check results?

## Constraints

- **Test suite stays green.** Phase 3 baseline: 1561 passed / 0 failed / 12 skipped / 15 xfailed. No regression. Validation happens externally; the criterion is "after the sprint lands, pytest still shows ≥1561 passing and 0 failures."
- **`tools.refresh_template_index --check` stays exit 0.**
- **No regression** in the 25 templates Phase 3 already re-emitted cleanly. Specifically: if the new Block A coverage changes their byte-identical output, that's a regression; treat as a fail.
- **Each port_check_blocked disposition requires a rationale.** Marker-without-comment is rejected.
- **Compile-only** for any template the sprint touches: `wf.compile("api")` must succeed.

## Done criteria

Phrased to be locally falsifiable, no universal quantifiers:

- **DC-1.** Block A covers the N helper shapes prep enumerated as unhandled in workflow_corpus/community/runexx + kijai (N comes from prep). For each shape: a test fixture in `tests/test_broadcast_helper_resolution.py` asserts the emitter resolves it without raw_call leakage.
- **DC-2.** The categorized port_check triage report exists as a markdown file (e.g. `docs/port_check_triage_phase_3_5.md`) with per-template disposition for every source-backed template currently failing port_check.
- **DC-3.** Every template flagged in DC-2 has its disposition applied: source patched (visible in diff), `# vibecomfy: manual` marker added (with rationale comment), or removed from `workflow_corpus/manifests/coverage.json` (with reason in commit message).
- **DC-4.** `ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py` re-emits cleanly: `port reemit` succeeds with no `UnboundLocalError`, raw_call count is strictly less than the pre-fix count.
- **DC-5.** Each Block-A-eligible runexx template re-emitted by the sprint has its raw_call(`'GetNode'`|`'Reroute'`) count strictly less than the Phase 3 baseline. (Per-template, not aggregate.)
- **DC-6.** `docs/template_provenance_gaps.md` and `docs/widget_alias_resolution.md` reflect the new Block A coverage and the triage outcomes.

## Touchpoints

Files the sprint is expected to modify or read:

- `vibecomfy/porting/emitter.py` (especially `_resolve_helper_nodes_for_emission()`)
- `vibecomfy/porting/helpers.py`
- `vibecomfy/commands/port.py` (only if a new `port check --batch` mode is added)
- `tests/test_broadcast_helper_resolution.py` (new fixtures)
- `ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py` (manual fix + re-emit)
- `ready_templates/video/ltx2_3_runexx_*.py` (named subset re-emitted)
- `workflow_corpus/manifests/coverage.json` (removals)
- `workflow_corpus/community/runexx/*.json` and `workflow_corpus/community/kijai/*.json` (read-only for enumeration)
- `docs/template_provenance_gaps.md`, `docs/widget_alias_resolution.md`, new `docs/port_check_triage_phase_3_5.md`

## Anti-scope

- Do **not** modify or rebase any Phase 0/1/2/3 commits on `scratchpad-emitter`.
- Do **not** opportunistically regenerate templates that aren't covered by the prep enumeration.
- Do **not** extend Block A for hypothetical shapes — only what prep enumerates.
- Do **not** change widget alias resolution logic (Phase 3 Block B/C is closed).
- Do **not** touch the `megaplan` repo from this sprint — fixes there are separate tickets.
- Do **not** add `# vibecomfy: manual` markers without rationale comments.
- Do **not** run pytest as an execute task — validation is external.

## Provenance + related work

- Originating ticket: `01KSG35MTEE2AASAHB3M8NQHY6` (vibecomfy) — captured the Phase 3 residuals.
- Related megaplan tickets:
  - `01KSFEA4BPWJMK5QE36SS75GJZ` — make batching planner-visible (shipped as `f44c9899` on megaplan main)
  - `01KSG32AJZ0YC21T3JVKXVB0HD` — auto-emit followups as tickets, ingest in prep (open)
- Phase 3 final state: `phase-3-sprint-brief-20260525-1151` review verdict `needs_rework`, force-finalized as `done`. See `.megaplan/plans/phase-3-sprint-brief-20260525-1151/review.json` for the exact rework items.
- Phase 3 commits this sprint builds on: `fe03111 0ccbac0 ff59afd 1063fbe d1d9824 99261c2` on `scratchpad-emitter`.

## Dial notation

`partnered/full/medium @codex +prep` — picked per `/megaplan-decision`. Reasoning: Block A is cross-cutting (tier 3), brief is grounded by prep so `full` robustness suffices, planner has real judgment calls so `medium` depth, codex vendor per user, `+prep` is the textbook case (enumerate-before-promising directly addresses Phase 3's failure mode).
