# Task: Consume provenance breadcrumbs in additive-edit evidence (~1 week)

**Status:** ready to scope/implement
**Parent context:** `docs/failure-analysis/v2/PLAN.md` (broad-view plan), case docs in `docs/failure-analysis/v2/`
**Size:** ~1 week · **Risk:** medium (touches the research/fixer evidence path) · **Confidence:** medium-high

## Goal (one line)

Make the additive-edit pipeline **read its own provenance breadcrumbs** (`source_template` / `prior_path`) and pass **role-preserving, all-instances, per-node-value** evidence to the fixer — so the agent uses the references that already exist instead of guessing.

## Why

The stabilized rerun showed 4 of 6 real failures (cases 01, 05, 08, 09) share one root: the correct values/wiring **already exist** in the workflow's own source template, but the pipeline never consults them. VibeComfy already *writes* `source_template`/`prior_path` into the emitted graph (`vibecomfy/porting/emit/ui.py:384-390`) — it just never *reads* them back. This is the fastest real capability gain available, and it's independently worth doing regardless of the bigger real-editor vision.

## ⚠️ The generalizable framing — read before implementing

This sliver sits on a fault line. Two implementations look similar but generalize very differently. **Build only the first.**

### ✅ Build this (generalizable): provenance as ranked priors
- Consume `source_template` / `prior_path` to locate the exact source workflow the current graph came from.
- When the agent must add/restore a node, fetch that source's **neighborhood** around the relevant node type.
- Preserve in the evidence: **ALL** same-type instances (not the first match), each instance's named widget values, its incoming/outgoing peer classes + sockets, and an inferred role label.
- Bind precedent instances to current-graph anchors by role/neighborhood, not by assuming same-class = same-role.
- Treat precedent values as **ranked priors with a provenance/confidence tag**, ranked alongside schema defaults and sibling values. The fixer sees "the source workflow used X here (provenance: source_template, confidence: high)" — not "you must use X."

**Why this generalizes:** it helps *any* precedent-based edit on *any* workflow that came from a template, including ones never in the test suite. It improves the agent's evidence; it does not dictate its answer.

### 🚫 Do NOT build this (demo-shaped, forbidden by PLAN.md §6)
- Extracting the source template's values per node-id and **copying them verbatim** into the fixer prompt.
- Injecting hidden-golden values, hard-coding class names / LoRA filenames / sigma strings / interpolation modes.
- Anything where "success" means "reproduced the source template's exact values."

The demo cases (01/08/09) will move *faster* if you build the forbidden version. Don't. The generalizable version moves them more slowly but builds real capability. If the generalizable version isn't moving them, the right response is to improve role-binding — not to fall back to copying.

## Scope

### In scope
1. **Research consumes provenance.** `vibecomfy/executor/research.py` currently ignores `source_template`/`prior_path`. Add a provenance-first lookup: when the current graph carries breadcrumbs, retrieve the source workflow's neighborhoods for the target node type *before* falling back to corpus/Hivemind similarity search. (Confirm exact sites; the breadcrumbs are written at `porting/emit/ui.py:384-390`.)
2. **Role-preserving slices.** When research builds a workflow slice / adaptation plan for the fixer, preserve: every same-type instance (not first-match), per-instance named widget values, per-instance incident edges (peer class + socket), and a role label inferred from neighborhood. Today slices collapse duplicate nodes and lose per-node values — that's the bug behind case 01 (only the first-stage sigma schedule survived).
3. **Risk-based research gating.** `revise` currently hard-disables research (`executor/contracts.py` ~437-449, `executor/core.py` ~240-253). Do NOT force research for every additive request (case 00 proves it's unneeded when type + insertion + defaults are all obvious). Instead: allow research when provenance exists AND role/placement/values are uncertain (duplicate node types, parallel branches, role-specific settings). Keep the cheap path cheap.
4. **Provenance tag on values.** Where the fixer receives a value suggestion, attach `(value, source, confidence)` so it's a prior, not a prescription.

### Out of scope (belong to the mid-term epic, not this sliver)
- The `EditIntent` validity contract / validity oracle.
- Role-aware placement planning (enumerating loci, ranking placements) — this sliver only *labels* role from neighborhood; full placement is the epic.
- Typed candidate construction / sibling-splice primitive.
- Runtime verification.
- Rebuilding the benchmark.

## Concrete targets (confirm line numbers before editing — code has shifted)

| File | Change |
|------|--------|
| `vibecomfy/executor/research.py` | Provenance-first source lookup; role-preserving slice construction (all instances, per-node values, peer edges, role label) |
| `vibecomfy/executor/contracts.py` / `core.py` | Risk-based research gating (provenance + uncertainty → allow research; keep revise-cheap-path) |
| Fixer evidence handoff (adaptation plan / slices) | Carry provenance-tagged value priors |
| `porting/emit/ui.py` | Read-only — confirm breadcrumb field names/shape (already written here) |

## Acceptance criteria

**Generalization test (primary):** On a workflow **not** in the 10-case suite that came from a ready_template, requesting an additive edit of a node type present in the source template → the fixer's evidence includes the source's neighborhood + per-node values + role labels + provenance tags. The improvement must be visible without the demo suite existing.

**Anti-gaming test (must pass):** No code path extracts source values to copy verbatim. No class names / filenames / sigma strings are hard-coded. A code review can confirm the fixer receives *priors*, not *answers*.

**Regression test:** Existing agent-edit + demo_factory tests stay green. Case 00 (the cheap path) is unaffected — it must not suddenly require research.

**Honest demo signal (secondary, trailing indicator only):** Cases 01/08/09 may flip as a side effect. Case 05 may improve (it found references but couldn't apply — this sliver improves the *evidence*, not the *application*; case 05 likely needs the epic's typed-construction work). Do not treat the demo count as the success metric.

## Test plan

1. **Unit:** research produces a role-preserving slice with all same-type instances given a fixture graph that has duplicate node types (e.g. two `ManualSigmas`). Assert both appear with distinct values + role labels.
2. **Provenance:** given a graph carrying `source_template`, research retrieves the source neighborhood first (mockable).
3. **Gating:** a case-00-shaped request (unambiguous type, linear insertion) still routes without research.
4. **Anti-gaming:** grep/AST check that no value is copied without a provenance/confidence tag — or a review checklist item if a static check is impractical.
5. **Live:** re-run the 10-case campaign; report honestly which moved and why. Expect value-case improvement, not a guaranteed pass count.

## Explicit non-goals

- Do not build the validity oracle or weaken the existing exact-match oracle.
- Do not re-pair the campaign or change the benchmark.
- Do not "make the cases pass" — improve the evidence path; the cases are a trailing signal.
- Do not touch the witness-oracle / poisoning / cycle-detection work already shipped (preserve it).

## Expected outcome (honest)

- **Real capability:** the agent stops ignoring its own corpus/provenance on any template-derived workflow. Genuine, generalizable.
- **Demo (trailing):** value cases (01/08/09) plausibly improve; fixer-failure cases (05/06) mostly unchanged (they need epic work). Net demo movement is a side effect, not the deliverable.

## Work breakdown by difficulty

Honest sizing so an implementer knows what's plumbing vs research. "Impossible" = genuinely outside this sliver's scope (belongs to the epic `real-additive-editor` or is research-bounded) — listed so nobody burns time trying to do it inside a 1-week task.

### Easy (plumbing / data, low-risk, high-confidence)
- **E1 — Confirm breadcrumb schema.** Read `vibecomfy/porting/emit/ui.py:384-390`; document the exact field names/shape of `source_template` / `prior_path` on the emitted graph. Read-only.
- **E2 — Load the source workflow from a breadcrumb.** Given the breadcrumb value, resolve + load the ready_template file (reuse existing template loaders). Handle missing/stale/invalid gracefully (fall through to corpus search).
- **E3 — Collect target-type instances in the source.** Given the node type to add (from the inquiry/classification), gather ALL nodes of that `class_type` in the loaded source — not the first match.
- **E4 — Provenance/confidence tags on values.** Attach `(value, source, confidence)` to every value in the evidence payload. Pure data tagging.
- **E5 — Anti-gaming lint + live validation.** A check (grep/AST/test) that no value is copied without a provenance tag; then re-run the 10-case campaign and report honestly.

### Medium (real implementation; extends existing machinery; moderate risk)
- **M1 — Role-preserving slice construction.** Extend `executor/research.py`'s slice builder so each same-type instance carries its named widget values + incident edges (peer class + socket), instead of collapsing to first-match. The machinery exists; the change is "don't collapse — preserve all instances + named fields + edges." (This is the core of the sliver and the fix for case 01.)
- **M2 — Wire the slice into the fixer evidence handoff.** Thread the new slice through research output → adaptation plan → fixer context. Find the handoff point, extend the data structure.
- **M3 — Heuristic role labels from neighborhood.** Assign a role label per instance from signals (peer node types, input/output types, pipeline position, widget values) — e.g. "this `ManualSigmas` feeds the second sampler → refinement." Heuristic only; confident inference is Difficult (D1).
- **M4 — Risk-based research gating.** Allow research when provenance exists AND role/placement/values are uncertain (duplicate types, parallel branches, role-specific settings); keep the case-00 cheap path research-free. Touches `executor/contracts.py` + `core.py`.
- **M5 — Unit tests.** Duplicate-node-type slice (two `ManualSigmas` → distinct evidence with distinct values), provenance-lookup (mocked source), gating (case-00-shaped request still routes without research).

### Difficult (research-bounded / judgment-dense; do a heuristic version, don't aim for confident)
- **D1 — Confident role inference for custom/unknown nodes.** Accurately labeling role beyond heuristics is the m2 research problem. The sliver ships heuristic labels (M3) and explicitly does NOT solve this; flag low-confidence labels for the fixer rather than guessing.
- **D2 — Reliable uncertainty detection for gating.** Deciding WHEN research is needed (vs the cheap path) is itself a judgment call. Get it wrong → over-research (latency/cost) or under-research (missed evidence). Iterate on the trigger conditions; accept it'll be imperfect.
- **D3 — Role-binding precedent → current anchors under ambiguity.** Matching source instances to current-graph anchors correctly when two same-type nodes exist and the role signal is weak. Depends on D1; degrades to "surface both as priors" when ambiguous.

### Impossible within this sliver (belongs to the epic or out of scope — do not attempt here)
- **I1 — Guarantee cases 01/08/09 pass.** The sliver improves the *evidence*; it cannot guarantee the *fixer* uses it correctly. That's m4 (typed construction). Expect improvement, not guaranteed passes.
- **I2 — Fix the fixer-failure cases 05/06.** Those are candidate-construction failures (schema loops, broken links), not evidence failures. Needs m4. Out of scope.
- **I3 — Additive edits on provenance-less workflows.** The sliver is provenance-first; hand-built/pasted graphs with no breadcrumbs degrade to the current corpus-search path (which is the failing path). Out of scope — a different problem.
- **I4 — Confidently pick the correct value when roles are ambiguous and there's no disambiguating signal.** If role inference can't tell the two `ManualSigmas` apart, the sliver surfaces priors but cannot choose. Needs m2 (roles) + m4 (construction). Surface-and-tag, don't force-pick.
- **I5 — Aesthetic / quality judgment of chosen values.** Entirely out of scope (later epic / research).

### Suggested order
E1 → E2 → E3 → M1 → M3 (heuristic) → M2 → E4 → M4 → M5 → E5. Treat D1/D2/D3 as "do the heuristic version, flag the rest" — don't block the sliver on them.
