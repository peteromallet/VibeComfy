# M3: Agent Skill And CLI Preview

## Outcome

Expose the reorganiser explicitly through a CLI and `/reorganise_comfy_workflow` skill, producing previewable layout-only candidates, reports, and safe apply behavior.

## Scope

In scope:

- Add `vibecomfy reorganise` command:
  - `--assess`
  - `--preview --out cleaned.json`
  - `--apply`
  - spacing preset option: `compact|balanced|wide`
  - group policy options including `--force-regroup`
- Add a Python API surface for assessment, projection, plan validation, compilation, and candidate creation.
- Add agent skill doc at `docs/agent-skill/skills/reorganise-comfy-workflow/SKILL.md`.
- Register the skill in `docs/agent-skill/SKILL.md`.
- Implement explicit `/reorganise_comfy_workflow` handling in the agent surface.
- Wire a model call for semantic grouping where needed, using the Pythonic projection and strict `LayoutPlan v1` output contract.
- Add second-stage intra-group planning only for groups above complexity thresholds or ambiguous multi-sampler groups.
- Produce artifacts:
  - `reorganisation_plan.json`
  - candidate UI JSON
  - `reorganisation_report.md`
  - structured metrics
  - structural no-op evidence
- Candidate generation must use the existing agent-edit discipline: patch the lossless UI substrate, do not regenerate unrelated graph state.
- Apply must be preview-first and guarded.

Out of scope:

- Main-flow automatic suggestion integration.
- Browser/e2e rollout.
- Fully automated reorganisation without user action.

## Locked Decisions

- Explicit skill/CLI path is the first user-facing surface.
- `--assess` and preview are safe defaults.
- In-place `--apply` requires explicit user intent and should preserve/backup the original file where relevant.
- Agent output is strict JSON; invalid plans fail closed with diagnostics.
- Second-stage agent work sees only the complex group plus boundary nodes, not the whole workflow again.

## Open Questions

- Should CLI `--apply` default to writing a `.bak` backup for raw workflow JSON?
- Which provider/model should the explicit skill use by default for semantic grouping?
- Should there be a pure deterministic mode that skips the semantic agent and uses role-classification fallback only?

## Constraints

- Do not expose raw filesystem paths in user-facing reports where existing agent-report policy avoids them.
- Keep apply eligibility explicit.
- Do not allow stale candidates to be applied after the source graph changes.
- Keep CLI tests offline by mocking agent plan generation.

## Done Criteria

- `vibecomfy reorganise --assess` returns a structured quality report.
- `vibecomfy reorganise --preview` writes valid candidate UI JSON and report artifacts.
- `/reorganise_comfy_workflow` produces a candidate and report in the existing agent panel flow.
- Bad agent output produces clear diagnostics and no candidate.
- Layout-only candidates pass structural no-op guard.
- Tests cover CLI assess/preview/apply, skill routing, artifact production, bad plan rejection, stale graph blocking, and second-stage intra-group planning trigger.

## Touchpoints

- `vibecomfy/commands/reorganise.py`
- `vibecomfy/commands/__init__.py`
- `vibecomfy/comfy_nodes/agent/*`
- `vibecomfy/porting/reorganise/*`
- `docs/agent-skill/SKILL.md`
- `docs/agent-skill/skills/reorganise-comfy-workflow/SKILL.md`
- `tests/test_cli_reorganise.py`
- `tests/test_comfy_nodes_agent_edit.py`
- `tests/test_reorganise_skill.py`

## Anti-Scope

- Do not make main-flow agent-edit auto-suggest yet.
- Do not add new frontend widgets beyond existing candidate/apply surfaces.
- Do not ship Set/Get conversion.

## Rubric

Overall plan difficulty: 4/5; selected profile: partnered-4; because this milestone crosses CLI, skill docs, agent model contract, candidate artifacts, and apply safety.

