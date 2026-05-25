# Megaplan Critique-Iteration Trace

What every iteration phase actually **sees**, read straight from the prompt
builders in `megaplan/prompts/` and the handler context-assembly in
`megaplan/handlers/{plan,critique,gate}.py`. Each section quotes the code path
that builds the prompt and lists the concrete inputs that land in it.

The phases run in the order: **prep → plan → (critique-evaluator → critique
work → gate → revise) × N iterations → finalize**. Iteration 1 has no prior
flags, no plan diff, no gate verdict; iteration N≥2 layers those in.

---

## prep

- **Builder:** `megaplan/prompts/planning.py::_prep_prompt`
- **Inputs in the prompt:**
  - `state["idea"]` — the original user task.
  - `project_dir` — repo root.
  - `output_path` — where the prep brief will be written.
  - `direction_block`, `notes_block` from `_prep_context_sections` (any
    `meta.notes` / direction guidance the operator supplied).
- **Does it see prior-iteration state?** No. Prep runs once before plan and
  has no concept of iteration.
- **Does it see the plan?** No, plan does not exist yet.
- **Notable shape:** prep first decides `skip: true/false`. When not skipped
  it produces a structured `prep.json` with `task_summary`, `key_evidence`,
  `relevant_code`, `test_expectations`, `constraints`, `suggested_approach`.
  The artifact becomes a load-bearing input for every downstream phase via
  `_render_prep_block` in `planning.py:139` and the prep dossier/metrics
  reads in `critique.py:109-118`.

---

## plan

- **Builder:** `megaplan/prompts/planning.py::_plan_prompt`
- **Inputs in the prompt:**
  - `prep_block` (prep.json rendered, plus the prep instruction).
  - `intent_and_notes_block(state)` — task intent + operator notes.
  - `project_dir`.
  - `output_path_block` for doc/creative modes.
  - `prior_doc_block` if `--from-doc` set (with `imported_decisions`).
  - `clarification_block` (`state["clarification"]`).
  - `tickets_block` — open tickets in this repo (`_render_open_tickets`).
  - The hard-coded `PLAN_TEMPLATE` structural contract.
- **Does it see prior-iteration state?** No, this is plan v1. Subsequent
  plan versions come from `revise`, not from re-running plan.
- **Does it see prep findings?** Yes, fully — prep.json is inlined via the
  prep_block.
- **Output contract:** `plan` markdown + `questions` + `success_criteria`
  (with `priority` and `requires`) + `assumptions`.

---

## critique_evaluator (the lens picker — the broken phase)

- **Builder:** `megaplan/prompts/critique_evaluator.py::_critique_evaluator_prompt`
- **Handler:** `megaplan/handlers/critique.py:84-199` (the `adaptive_path`
  branch, guarded by `adaptive_critique_enabled(state) and not creative`).
- **What it *should* receive:**
  - Always: `latest_plan` markdown, `latest_plan_meta`, `intent_block`,
    project_dir, the critic model roster, the 9-lens catalog, the
    assignment contract.
  - From iteration 1 onward: prep dossier text + prep metrics (gaps,
    contradictions) via `_eval_prompt_kwargs = {"prep_dossier_text",
    "prep_metrics"}` (`critique.py:119-123`). This goes into the
    "Prep that preceded this plan" section (`_render_prep_section`).
  - From iteration 2 onward (`critique.py:124-147`):
    - `flag_lifecycle` — full `load_flag_registry(plan_dir)` payload.
    - `iteration_pressure` — `compute_iteration_pressure(plan_dir, state)`
      (recurring/reopened flag groups across iterations).
    - `gate_signals` — `build_gate_signals(plan_dir, state, root)` (the
      same signals the gate consumes).
    - `revise_resolutions` — list of `{id, concern, evidence, resolution}`
      for every flag the reviser claimed to handle, with the resolution
      `claim` and `where`.
    - `plan_diff` — `_plan_version_unified_diff(plan_dir, iteration)`,
      i.e. `difflib.unified_diff` between `plan_v{N-1}.md` and
      `plan_v{N}.md`.
  - **The verify block** renders only when `iteration >= 2 and
    revise_resolutions and plan_diff` are all present
    (`critique_evaluator.py:286`). It asks the evaluator to adjudicate
    each resolution against the diff and emit `flag_verifications`.
- **What it actually sees on the broken run:** nothing — the worker
  KeyErrored on `STEP_SCHEMA_FILENAMES["critique_evaluator"]` in
  `workers/shannon.py:944` and `workers/_impl.py:2137` (no schema entry
  was registered). The handler's broad `except Exception` at
  `critique.py:186` caught the KeyError, wrote a `fallback: true`
  evaluator_verdict, appended a single string to `state.meta.
  critique_evaluator_warnings`, and continued. No stderr signal, no event,
  no events.ndjson row. The fix registers the schema and prints a loud
  stderr warning when the fallback fires.

---

## critique work (the lens runs)

- **Builder:** `megaplan/prompts/critique.py::_critique_prompt` →
  `_build_critique_prompt`
- **Inputs in the prompt:**
  - `project_dir`, `intent_brief_reference(state)`.
  - `latest_plan` markdown + `latest_plan_meta`.
  - `structure_warnings` (`latest_meta["structure_warnings"]`).
  - `unresolved` — `load_flag_registry(plan_dir)` filtered to
    `{addressed, open, disputed}` flags (id, concern, status, severity).
    Note: this lists prior-iteration flags by id and status, but **does
    not include their evidence**, only concern text.
  - `debt_block` — `_planning_debt_block`.
  - `settled_decisions` from `tiebreaker_decisions.json`.
  - `robustness` level + a per-robustness instruction.
  - **Selection-why block** (adaptive only): per-lens `why` strings the
    evaluator emitted (`selection_why={check_id: why}`). On the broken
    fallback path this is empty.
  - **Revise context block** (adaptive only, iteration ≥ 2): the same
    unified plan diff and per-flag resolution claims that the evaluator
    receives. Built in `critique.py:209-230` and passed as
    `revise_context`.
  - The output template path (`critique_output.json`) and the structural
    contract for findings.
- **Prior-iteration awareness — IMPORTANT:** the *template* the critic
  writes to includes `prior_findings` per check id (built by
  `_build_checks_template` at `critique.py:174-221`). When iteration > 1,
  `prior_path = plan_dir / f"critique_v{iteration - 1}.json"` is read
  (`critique.py:191`), and per-finding `status` is pulled from the flag
  registry. So critique v2's *output template* shows v1's findings and
  their flag statuses, even though the textual prompt only summarises
  prior flag concerns. The model is instructed (line 350-355): *"This
  is critique iteration {iteration}. The template file includes prior
  findings with their status. Verify addressed flags were actually fixed,
  re-flag if inadequate, and check for new issues."*
- **Does it see the plan delta?** Only in adaptive mode via
  `revise_context`. In the static / fallback path, it does **not** see
  the diff — only `latest_plan` (the new version) and the list of prior
  flags.
- **Does it see the prior gate verdict?** No, only the unresolved-flag
  list which the gate updated. The gate's `signals_assessment`,
  `warnings`, and `recommendation` are not surfaced in the critique
  prompt.

---

## gate

- **Builder:** `megaplan/prompts/gate.py::_gate_prompt`
- **Inputs in the prompt:**
  - `project_dir`, `intent_brief_reference(state)`.
  - `latest_plan` + `latest_plan_meta`.
  - `gate_signals` — `current_iteration_artifact(plan_dir, "gate_signals",
    iteration)` (score, plan delta percent, recurring critiques, preflight,
    etc.).
  - `critique_checks_block` — per-lens flagged counts read from the
    current iteration's `critique_v{N}.json`. Just "N flagged" / "clear",
    not the finding text.
  - `open_flags` — full `unresolved_significant_flags` registry filtered
    to {open, disputed}, with `id, concern, evidence, revise_summary,
    category, severity, status, weight`. This is the gate's primary
    decision artifact.
  - `debt_block` and `iteration_pressure_block` (recurring/reopened
    flag groups across all iterations to date).
  - `robustness`.
- **Does it see prior gate verdicts?** Indirectly — `gate_signals`
  includes plan_delta_percent and recurring_critiques across iterations,
  and `iteration_pressure_block` lists groups that have re-opened. The
  literal text of `gate_v{N-1}.json` is not inlined.
- **Does it see the plan delta?** Yes via `gate_signals.plan_delta_percent`
  and `gate_signals.recurring_critiques` (numeric / id lists, not the
  unified diff itself).
- **Output contract:** `recommendation ∈ {PROCEED, ITERATE, ESCALATE,
  TIEBREAKER}` plus `signals_assessment`, `warnings`, `flag_resolutions`
  per blocking flag, `accepted_tradeoffs`, `settled_decisions`.

---

## revise

- **Builder:** `megaplan/prompts/critique.py::_revise_prompt`
- **Inputs in the prompt:**
  - `project_dir`, `intent_brief_reference(state)`.
  - `latest_plan` markdown + `latest_plan_meta`.
  - **`gate` — the full `read_json(plan_dir / "gate.json")` payload is
    inlined.** That includes the gate's `recommendation`, `rationale`,
    `signals_assessment`, `warnings`, `flag_resolutions`,
    `accepted_tradeoffs`, `settled_decisions`. Revise gets the most gate
    context of any phase.
  - `open_flags` — `unresolved_significant_flags` with full
    `{id, severity, status, concern, evidence}`.
  - `settled_block` from `tiebreaker_decisions.json`.
- **Does it see prior critique findings?** Not as a prompt input, but
  the open_flags list is derived from accumulated critique runs. The
  *full per-finding text* from `critique_v{N}.json` is not inlined —
  only flags that survived into the registry.
- **Does it see the plan delta?** No — revise sees the current plan and
  the gate verdict; it produces plan v{N+1}.
- **Output contract:** `plan` (full revised markdown), `changes_summary`,
  `flags_addressed`, `assumptions`, `success_criteria`, `questions`.

---

## critique v2 (subsequent iteration)

Same builder, same code path. The differences from v1 are:

- The `iteration_context` line is appended to the review block:
  *"This is critique iteration {iteration}. The template file includes
  prior findings with their status."*
- The output template `critique_output.json` now contains v1's findings
  as `prior_findings` per check, with per-finding `status` pulled from
  the flag registry.
- In **adaptive mode only**, the prompt includes a `revise_context`
  block with the unified plan diff (`plan_v{N-1}.md` → `plan_v{N}.md`)
  and per-flag resolution claims (`flag_resolution_summary` from the
  registry). In static/fallback mode, the diff is **not** in the
  prompt — the critic gets the new plan, the prior flag list, and the
  iteration-context sentence.
- Selection-why notes per lens, when the evaluator emitted them.

So: critique v2's **textual** awareness of "what changed" is gated on the
adaptive path running. With the evaluator broken, the diff disappears.

---

## gate v2 (subsequent iteration)

Same builder, same code path. The differences from v1:

- `critique_checks_block` reads the current iteration's `critique_v{N}.json`,
  so it shows v2's flagged counts (not v1's).
- `gate_signals` accumulates across iterations: `plan_delta_percent`
  (between plan_v{N-1} and plan_v{N}), `recurring_critiques` (flag ids
  surfaced in both critique_v{N-1} and critique_v{N}), and preflight
  results. Built in `megaplan/orchestration/evaluation.py` —
  `compute_plan_delta_percent` and `compute_recurring_critiques`.
- `iteration_pressure_block` enumerates flag groups that have re-opened
  across iterations (the load-bearing input for the `TIEBREAKER`
  recommendation).

The gate **does not see** the literal gate v1 verdict text — only its
downstream effects (which flags survived, which got resolved, what the
plan looks like now).

---

## Summary — where context is thin

| Phase | Sees prior-iteration findings? | Sees plan diff? | Sees prior gate verdict? |
|---|---|---|---|
| prep | n/a | n/a | n/a |
| plan | n/a | n/a | n/a |
| critique_evaluator | yes (registry + iteration_pressure + revise_resolutions) | yes (unified diff) | yes (gate_signals) |
| critique work (adaptive) | yes (prior_findings template + revise_context) | yes (unified diff) | partially (open flags, not gate text) |
| critique work (static/fallback) | partially (prior_findings template only) | **no** | partially (open flags only) |
| gate | partially (open flag registry + flagged counts) | yes (delta percent + recurring ids, not the diff) | partially (gate_signals, not gate text) |
| revise | partially (open flag registry) | **no** | yes (full gate.json inlined) |
| critique v2 | same as v1 + iteration_context note + template prior_findings | adaptive: yes / static: no | partially (open flags only) |
| gate v2 | same as v1 + larger iteration_pressure | yes (cumulative delta + recurring) | partially (gate_signals only) |

**Concrete loop weaknesses surfaced by this trace:**

1. **Critic loses the diff in fallback mode.** When `critique_evaluator`
   fails silently (the bug being fixed), the critic prompt has no
   `revise_context` and no unified diff. It re-litigates against a
   fresh plan with only "here are old flag concerns" as context — which
   matches the symptom of "same 6 lenses every iteration."
2. **Revise never sees the plan delta.** It only sees the current plan
   + gate verdict. It cannot reason about *what was previously tried
   and rejected* unless the gate inlined that into `warnings`.
3. **Gate never sees gate v1's text.** It infers continuity from
   `gate_signals.recurring_critiques` and `iteration_pressure`. A
   recommendation that was previously TIEBREAKER but rejected by the
   operator is not visible.
4. **The critique prompt drops finding *evidence* on prior-iteration
   flags.** `unresolved` only carries `id/concern/status/severity`, not
   `evidence`. The template carries it, but only for the same check_id;
   cross-check evidence is invisible.
