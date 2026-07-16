# Agent Edit Complete Robustness

This initiative executes
`docs/plans/agent-edit-complete-robustness-architecture.md` as seven
dependency-ordered milestones.

## Model routing requested by the operator

- Easy: DeepSeek Pro
- Medium: GPT 5.6 Luna
- Hard: GPT 5.6 Terra
- Impossible/escalation only: GPT 5.6 Sol

The executable profile mapping is recorded in `chain.yaml`. If those names are
not native runtime identifiers, the mapping must use the local aliases that
resolve to them and must be proven before the first milestone starts.

## Milestones

| Label | Deliverable | Difficulty | Status |
| --- | --- | --- | --- |
| M0 | Ratify and freeze the incident foundation | Medium | In progress |
| M1 | Versioned operation, projection, identity, Undo, and migration contracts | Hard | Pending |
| M2 | Native graph adapter and canonical mutation path | Hard | Pending |
| M3 | Single Apply/rollback verifier | Hard | Pending |
| M4 | Workflow-scoped controller and transport boundary | Hard | Pending |
| M5 | Exhaustive recovery, Undo, and legacy closure | Hard | Pending |
| M6 | Clean real-ComfyUI composition and anti-regression gate | Hard | Pending |

## Completion rule

A milestone is complete only when its declared proof artifacts exist and its
done criteria are directly verified. The epic is complete only after
`proof-map.json` is populated with current proof and the nine-point audit in
`TASKS.md` is fully green.
