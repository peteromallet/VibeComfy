# Phase 2 sprint brief — VibeComfy template refactor cleanup

Drafted 2026-05-23 by audit against `/tmp/phase2_audit_table.md`. Block A
(scratchpad emitter parity, 4-8h) has been absorbed into Phase 1 as Family K;
this brief covers Blocks B/C/D/E/F only.

## 1. Outcome

After Phase 2: the doctor exposes a readability tier with stable diagnostic
codes for the issues the original umbrella plan identified, `def build()`
shape lands its cosmetic polish (`READY_OUTPUTS` module-level, drop
`new_workflow()` context manager), public input names follow the capability-
level canon, the known-failing `test_testing_dry_run` import test goes green,
and the small recoverability checkpoints get cleaned up.

## 2. Scope (IN) — grounded in live-residual rows

Hour estimates are honest. Lower-end design choice priced.

**Block B — Doctor readability tier**

- B1. Implement first wave of readability diagnostics: `avoidable_positional_output`, `schema_backed_widget_alias_not_resolved`, `uuid_class_type_in_ready_template`, `model_filename_not_declared`, `generated_template_has_local_node_helper`. Surface through `python -m vibecomfy.cli doctor <wf> --readability --json` and extend `port check --strict-ready-template --json` to include them. Severity = warning on first ship. **6-8 h**.
- B2. Snapshot tests for diagnostic code names + JSON shape. Stability contract before any future CI promotion. **1-2 h**.

**Block C — Cosmetic emitter polish (template `def build()` shape)**

- C1. Lift `READY_OUTPUTS` to module level mirroring `PUBLIC_INPUTS`. Regenerate the 64 templates. Update Phase 0 A.3 goldens. **1-2 h**.
- C2. Drop the `with new_workflow(...) as wf:` context manager wrapper — replace with `wf = new_workflow(READY_METADATA, source_path=__file__)`. Saves one indentation level across ~80 lines of body per template. Less magic than the `inspect.stack()` alternative. **1-2 h**.

**Block D — Test infrastructure fix**

- D1. Fix `tests/test_testing_dry_run.py::test_importing_dry_run_does_not_pull_runtime_at_import_time`. Trace the import edge that pulls `runtime.client`/`runtime.server` and apply the lazy-import pattern already used in `parity.py`. **0.5-1 h**.

**Block E — Public input naming canonical**

- E1. Grep all 64 templates' `public()` calls; rename non-canonical names to capability-level standard from `readable_ready_template_cleanup_plan.md:L176-182`. Examples: `length`→`frames`; standardize `seed_first`/`seed_last` policy; output prefix names. Run `tools/refresh_template_index --check` after to verify `template_index.json[*].id` and public-input names stay stable in shape (the actual name values change — Reigh worker per p1:30-35 reads only `templates[*].id`, not public-input names, so the rename is safe). **2-3 h** including parity verification.

**Block F — Cleanups**

- F1. Delete recoverability checkpoints (`stash@{0}`, `stash@{1}`, `/tmp/desloppify_lifeboat_20260523/`) once all of A/B/C/D/E land. **0.25 h**.
- F2. Decide and document whether `errors.py` agent-facing enhancements (`to_dict()`, `severity`, `default_next_action`, semantic subclass names) are already on current tip (per Phase 0 D.3) or if a small graft is owed. Conditional. **0.5-2 h**.

**Total honest IN scope: 12.25 – 20.25 hours**, midpoint ~16 h. **~2 days of focused work.**

## 3. Scope (OUT)

Anti-scope — tempting items that should NOT land in Phase 2:

- **`port ready` staged orchestrator** (plan: Sprint 5). Its own sprint.
- **App-active template list + manual curation** (plan: Sprint 7). Policy work; needs Reigh-worker coordination.
- **Subgraph promotion to named Python functions returning typed Handles** (plan: L640-723). Architectural change — needs its own scoping pass.
- **CI gate promotion (warnings → errors)** (plan: Sprint 8). Premature until B1's diagnostic codes soak for a release cycle.
- **Strict ban on UUID class types in strict-ready templates**. Family I in Phase 1 conditionally addresses one case; a blanket ban is policy work.
- **Composite schema provider rewrite with provenance precedence** (plan: L427-477). The typed-wrapper world arguably side-stepped most of this. Out unless audit shows it's still needed.
- **Example-driven acceptance tests** (plan: L933-944). Worth doing but only after B1 + Family K ship.
- **Manual repair codemod tooling** (plan: Sprint 7). Premature until any post-Phase-1 `manual`-marker templates exist.
- **Scratchpad emitter parity (was Block A)**. ABSORBED INTO PHASE 1 AS FAMILY K. Don't double-do it.

## 4. Locked decisions

- **Marker semantics** — as locked in Phase 0 LD1: `# vibecomfy: manual` reserved for future hand-authored; current 23 broken-regen flip to `generated` after Phase 1.
- **Doctor surface (B1)** — readability diagnostics surface through `doctor --readability` AND `port check --strict-ready-template`, sharing a structured diagnostic model. Source: `readable_ready_template_cleanup_plan.md` Decisions L1262.
- **Diagnostic stability (B2)** — code names + severity + JSON fields + text/JSON consistency snapshotted before any future CI promotion. Source: same plan, Decisions L1263.
- **`def build()` cosmetic choice (C2)** — prefer **option 2 (drop context manager)** over option 1 (implicit `inspect.stack()` discovery). Less magic; one-level-of-indentation win is real; emission errors can be wrapped at the loader.
- **READY_OUTPUTS symmetry (C1)** — mirror `PUBLIC_INPUTS` shape per `template_cleanup_followups.md:D L175-176`.
- **Public input rename safety (E1)** — confirmed safe by Phase 1 cross-repo audits; Reigh worker reads only `templates[*].id`, not public-input names.

## 5. Open questions

These MUST be resolved during Phase 2 execution, not before:

- **Q1.** Are the 12 `test_cli_port.py` failures fu:B.2 references actually still failing on current tip? Phase 1's brief claims "34/34 test_cli_port.py passing" — reconcile early.
- **Q2.** Does `vibecomfy/errors.py` on current tip already have `to_dict()`/`severity`/`default_next_action`, or only the bare base-class hierarchy? Resolves F2 scope (0 h vs 2 h).
- **Q3.** For C1 (READY_OUTPUTS module-level), what happens when a template has multiple output nodes (multi-artifact, e.g. `SaveImage` + `SaveAnimatedWEBP`)? `OutputSpec` per name; how does `wf.finalize` consume the dict?
- **Q4.** For B1 readability diagnostics, what is the JSON shape of a diagnostic? Recommend `{"code": str, "severity": "warning"|"error", "node_id": str|None, "field": str|None, "message": str, "next_action": str|None}` — confirm shape before B2 snapshots it.

## 6. Constraints

- **Reigh-worker blast radius:** Verified by Phase 1 audits as zero outside `template_index.json[*].id`. E1 (renames) and C1 (output shape) must preserve `template_index.json` template IDs and the per-template public input/output set as exposed in the index. Run `tools/refresh_template_index --check` after each block.
- **Backward compat:** No remaining `# vibecomfy: manual` templates post-Phase 1 (per LD1), but the marker contract persists. Phase 2 must not auto-touch any template that gains the `manual` marker between Phase 1 and Phase 2.
- **Golden tests from Phase 0 A.1/A.3:** C1 will move them. Land C1 with its golden update commit; don't batch.
- **Phase 1 ordering:** Phase 2 must come AFTER Phase 1 family fixes including Family K. Doing it before would chase moving emitter behavior.
- **No new CLI surface beyond `doctor --readability`.** Existing `port`, `inspect`, `workflows list`, `nodes`, `analyze` stay as-is.

## 7. Done criteria

- `python -m vibecomfy.cli doctor <any-ready-template> --readability --json` returns a stable structured doctor report containing at minimum the 5 diagnostic codes from B1.
- `tests/test_doctor_diagnostics.py` (new) pins diagnostic code names + severity + JSON shape via snapshot.
- All 64 ready templates conform to: `READY_METADATA`, `PUBLIC_INPUTS`, `READY_OUTPUTS` (new), `def build()`, `wf = new_workflow(...)` (no `with` wrapper), `wf.finalize(PUBLIC_INPUTS, READY_OUTPUTS)`. Verified by load-and-validate sweep (from Phase 0 A.4) extended with shape assertion.
- `tests/test_testing_dry_run.py` green.
- Public input names across templates match capability-level canon per plan:L176-182. Verified by new `tests/test_public_input_naming.py` audit.
- `template_index.json` shape stable (template IDs unchanged); public-input rename diffs reviewed and committed alongside E1.
- All recoverability checkpoints from `template_cleanup_followups.md:C` deleted.
- `template_cleanup_followups.md` either deleted or marked CLOSED.

## 8. Touchpoints

- `vibecomfy/diagnostics/` (present per gitStatus) — B1, B2.
- `vibecomfy/commands/inspect.py`, `vibecomfy/commands/port.py` — wire `--readability` flag.
- `vibecomfy/porting/emitter.py` — C1 (READY_OUTPUTS emission), C2 (drop context manager).
- `vibecomfy/templates.py` — C2 (`new_workflow` signature change if needed).
- `tools/convert_ready_templates.py` — regen pass for C1 and E1.
- `tools/refresh_template_index.py` — verify shape stability after each block.
- `tests/test_porting_convert.py`, `tests/test_porting_emitter.py`, `tests/test_cli_port.py`, `tests/test_testing_dry_run.py`, `tests/test_doctor_diagnostics.py` (new), `tests/test_public_input_naming.py` (new).
- `docs/template_porting_workbench.md`, `docs/errors_and_doctor.md`, `AGENTS.md` — doc updates per Phase 0 doc-hygiene posture.

## 9. Sizing verdict

**Honest hour total: 12.25 – 20.25 h, midpoint ~16 h. ~2 days of focused work.**

This is under a 2-week sprint but justifies a **1-week `directed/full` megaplan** for the clean ship boundary after Phase 1. Rationale:

- Cross-cutting touchpoints (doctor + emitter + tests + templates) benefit from full robustness critique/gate even if the work is mechanical.
- `directed/light` skips prep + gate + review — fine for one-shot mechanical work but here the diagnostic code names (B1) are a public API surface that benefits from second-mind review.
- `partnered/full` would be overkill — there's no real architectural design risk; the design calls are all locked.
- Slack budget = remaining ~4 days of the 1-week sprint, used for surprises (Q1 reconciliation, Q3 shape decisions, regen diffs).

Sequencing: D1 → B1 → B2 → C1 → C2 → E1 → F1 → F2 (conditional).

If Phase 1 surfaces unexpected complexity that consumes its slack budget, Phase 2 absorbs the overflow as additional slack — it is the natural buffer.
