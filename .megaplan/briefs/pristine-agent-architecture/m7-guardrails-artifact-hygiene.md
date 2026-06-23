# M7: Guardrails And Artifact Hygiene

## Outcome

Lock in the new structure with tests, cleanup policy, and lightweight architecture documentation. Remove confirmed stale compatibility paths and repo clutter so the pristine architecture stays understandable after the epic ends.

Overall plan difficulty: 5/5; selected profile: partnered-5; because this sprint decides which old paths are safe to delete and which guardrails prevent future architecture drift.

## Scope

In scope:

- Add regression tests for:
  - internal sentinel strings never appearing in normal UI
  - stage display still showing the correct user-facing stage
  - apply candidate/eligibility consistency
  - session rehydrate safety
  - explicit audit/debug evidence availability
- Add lint/static checks for forbidden normal-render imports or raw field reads after the selector/render module boundaries are stable. If a check would be brittle, add a targeted test and document the skipped static check with a reason.
- Write `docs/architecture/agent_panel.md` documenting the canonical model and owner modules.
- Add `docs/architecture/ARTIFACTS.md` with path, lifecycle, committed status, generator, check command, cleanup command, and owner.
- Add `docs/architecture/compatibility-ledger.md` with owner, caller evidence, fixture coverage, and deletion trigger for every remaining legacy alias/path.
- Delete confirmed stale compatibility aliases, dead renderers, stale fixtures, generated artifacts, and loose cleanup files that no longer belong in the repo.
- Document any compatibility paths that remain, with owners and deletion triggers.

Out of scope:

- Starting a new major architecture direction.
- Cosmetic cleanup without structural value.
- Deleting compatibility paths that still protect real persisted sessions.

## Locked Decisions

- Guardrails encode the new boundaries in tests before old paths are removed.
- Generated artifacts and local diagnostic outputs do not become committed source unless intentionally documented.
- Architecture notes are short and enforceable, not a second design system.

## Execution Defaults

- Invariant behavior belongs in tests. Import/read bans belong in lint/static checks once module boundaries are stable.
- `cleanup.md` is planning scratch. Fold still-relevant content into `docs/architecture/agent_panel.md`, `docs/architecture/ARTIFACTS.md`, or `docs/architecture/compatibility-ledger.md`, then remove or relocate the root file.
- Old aliases without caller evidence, fixture coverage, and deletion trigger are removed.
- Artifact categories are fixed to: source, generated committed source, generated local build output, runtime output, diagnostic export, scratch.

## Constraints

- Do not break local developer workflows.
- Do not remove evidence paths needed by support/debugging.
- Keep the final cleanup reviewable.

## Done Criteria

- Tests fail if raw internal execution data becomes visible in normal UI.
- Tests prove the intended stage display still works.
- Explicit audit/debug evidence paths remain covered.
- Stale compatibility paths and repo clutter are removed or documented.
- `docs/architecture/agent_panel.md` names the canonical contracts, owner modules, and allowed data flow.
- `docs/architecture/ARTIFACTS.md` classifies generated/runtime/diagnostic/scratch paths.
- Remaining compatibility has an owner, caller evidence, fixture coverage, and deletion trigger.
- `docs/architecture/compatibility-ledger.md` records every retained compatibility path.
- Root `cleanup.md` no longer remains as unclassified planning scratch.

## Handoff Artifacts

- `docs/architecture/agent_panel.md`.
- `docs/architecture/ARTIFACTS.md`.
- `docs/architecture/compatibility-ledger.md`.
- Static check/test inventory and commands.

## Touchpoints

- `tests/browser/*.test.mjs`
- Python tests around agent/session/audit contracts
- `docs/architecture/agent_panel.md`
- `docs/architecture/ARTIFACTS.md`
- `docs/architecture/compatibility-ledger.md`
- Frontend modules touched by prior milestones
- Backend modules touched by prior milestones
