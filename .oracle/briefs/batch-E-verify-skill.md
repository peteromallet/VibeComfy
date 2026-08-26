# PROBE — Batch E SKILL.md + four-item contract (read-only)

You are Spark probing docs and contract presence for Batch E at HEAD `d2975269` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not run pytest.

Executor claim (4): SKILL.md mechanical section covers missing blocks preflight, ensure flow, tier acceptance, stub rejection, strict flag, doctor/validate-coverage pointer.

## What to do

1. Confirm `docs/plans/**` was NOT edited:
   ```
   git diff --stat 86e4a6ba..d2975269 -- docs/plans
   git diff --name-only 86e4a6ba..d2975269 -- . ':!.oracle/**'
   ```

2. Read the SKILL.md delta:
   ```
   git diff 86e4a6ba..d2975269 -- docs/agent-skill/SKILL.md
   ```
   Quote the new section (or say ABSENT). It must be one mechanical section, not a tutorial.

3. Checklist — each must be PRESENT in the new section (cite the sentence), or ABSENT:
   - missing capture blocks preflight
   - `vibecomfy schemas ensure --manifest <m>` (registry → ephemeral clone → r1/r2/r3 → cache + provenance tier). r3 may be documented as deferred/fail-closed; that is OK if r1/r2 are described honestly
   - preflight accepts `on_demand_*` as those tiers (not as `authoritative_object_info`)
   - `@stub.json` never accepted
   - campaign-grade: `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1`
   - doctor / `schemas validate-coverage --manifest` print the command
   FAIL if the section claims a static parse is a runtime capture, or documents `on_demand_runtime` as a persist/preflight token (canonical tokens are `on_demand_static` | `on_demand_import` | `on_demand_embedded`; no `on_demand_runtime` alias).

4. Four agent-goal items present in CODE (not just docs). For each: PRESENT + file, or ABSENT:
   1. `schemas ensure --manifest` (Batch C already; E may only reuse)
   2. Preflight bridge + strict flag (Batch D already; E may only point at it)
   3. Doctor / coverage gap + exact command (this batch)
   4. Tests + SKILL.md (this batch)
   Use `.oracle/plan.md` Traceability table (lines ~24–29) as the four items.

5. Evidence matrix: `.oracle/evidence/batch-E-matrix.md` and/or test docstrings. Columns required: command, source_kind, commit, rung, preflight verdict, strict verdict, stub verdict. Note if matrix is only in `.oracle/` (allowed) vs `docs/plans/**` (forbidden).

6. North Star anti-pattern scan of the SKILL text only: stub-as-truth, permanent install, unactionable wall, parallel schema system, silent tier upgrade. Flag any sentence that would teach an agent the wrong trust story.

## Return (max 350 words)

- docs/plans dirty: yes/no
- SKILL section: quoted or ABSENT
- 6-bullet checklist PRESENT/ABSENT
- Four agent-goal items PRESENT/ABSENT
- Evidence matrix: present + location
- SKILL trust-story: aligned or issue
- Overall: PASS or issue list
