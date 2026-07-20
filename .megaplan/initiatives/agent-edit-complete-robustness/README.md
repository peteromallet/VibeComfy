# Agent Edit Complete Robustness

This initiative executes
`docs/plans/agent-edit-complete-robustness-architecture.md` as seven
dependency-ordered milestones.

## Model routing requested by the operator

- Easy: DeepSeek Pro
- Medium: Claude Code routed through GLM 5.2
- Hard: Claude Code routed through GLM 5.2 with higher reasoning
- Exceptional escalation only: GPT 5.6 Sol

The executable profile mapping is recorded in `chain.yaml`. If those names are
not native runtime identifiers, the mapping must use the local aliases that
resolve to them and must be proven before the first milestone starts.
Megaplan profiles use parser-valid effort-only `claude:*` specs; the active
Claude Code provider must be configured for GLM 5.2 before medium or hard work.

Historical context for why the regression cluster appeared after the prior
transaction-spine epic is recorded in
[`post-epic-regression-history.md`](post-epic-regression-history.md).

## Operator execution policy

The M0–M6 outcome is fixed. Execute it integration-first: a bounded unit closes
after two independent acceptances, focused adversarial coverage, and broad
green gates. Do not spend a third or fourth review on the same unit unless new
contradictory evidence appears; move to the next integration boundary.

For an isolated timing flake, run the exact failing test once and then the full
relevant suite once. If both are green, record the flake and continue. Further
polishing requires reproducible failure evidence. This diminishing-returns
rule does not waive any milestone proof, real-ComfyUI gate, ownership transfer,
recovery requirement, or final audit item.

## Milestones

| Label | Deliverable | Difficulty | Status |
| --- | --- | --- | --- |
| M0 | Ratify and freeze the incident foundation | Medium | Complete |
| M1 | Versioned operation, projection, identity, Undo, and migration contracts | Hard | Complete |
| M2 | Native graph adapter and canonical mutation path | Hard | In progress — S1/S2 accepted; C2a receipt core accepted 20/20 but uncommitted/unintegrated; C2b resolver next; S3–S6 pending |
| M3 | Single Apply/rollback verifier | Hard | Pending |
| M4 | Workflow-scoped controller and transport boundary | Hard | Pending |
| M5 | Exhaustive recovery, Undo, and legacy closure | Hard | Pending |
| M6 | Clean real-ComfyUI composition and anti-regression gate | Hard | Pending |

## Completion rule

A milestone is complete only when its declared proof artifacts exist and its
done criteria are directly verified. The epic is complete only after
`proof-map.json` is populated with current proof and the nine-point audit in
`TASKS.md` is fully green.
