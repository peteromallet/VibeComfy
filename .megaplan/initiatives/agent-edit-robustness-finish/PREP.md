# Megaplan Prep Decision

## Sizing

The residual work is materially larger than one two-week plan and contains eight
sequential authority and proof boundaries. It is therefore an eight-milestone epic. Each
milestone is sized to roughly two weeks of skilled human implementation and
review, and each produces a durable handoff consumed by the next.

## Sources and accepted foundation

- `docs/plans/agent-edit-complete-robustness-architecture.md`
- `.megaplan/initiatives/agent-edit-complete-robustness/NORTHSTAR.md`
- `.megaplan/initiatives/agent-edit-complete-robustness/TASKS.md`
- `.megaplan/initiatives/agent-edit-complete-robustness/current-execution-state.md`
- `.megaplan/initiatives/agent-edit-complete-robustness/proof-map.json`
- accepted foundation through `a395c243`, as enumerated by the tracked
  `FOUNDATION.md` launch receipt
- foundation includes the committed C2a receipt core and incident repairs for empty
  canvases, native port identity, projection normalization, hash authority,
  finalized chat retention, scope migration, and native widget resolution

M0 and M1 are closed. M2 observation/contract checkpoints are accepted, but
the public adapter remains observation-only, coupled native ownership remains
0/27 transferred, seven S4 debt rows remain, and the C2 atomic cut is open.
M3–M6 are residual work, not assumed foundation.

The chain may launch only from `agent/agent-edit-robustness-foundation` after
the tracked foundation receipt and its `a395c243` content check pass. This
prevents a launch from the former `7934834f` branch tip.
Before R1, record a zero exit from `git merge-base --is-ancestor a395c243
agent/agent-edit-robustness-foundation`; the current chain schema cannot express
that ancestry assertion directly.

`FOUNDATION.md` supersedes predecessor status text only for C2a's committed
state and the later incident repairs. The predecessor remains authoritative
for M0–M2 closure and native-owner transfer state.

## Dial decisions

| Sprint | Difficulty and failure guarded against | Profile | Robustness | Depth |
| --- | --- | --- | --- | --- |
| R1 | 4/5: wrong native-shape modeling poisons the later cut | partnered-4 | full | high |
| R2 | 4/5: an incomplete rehearsal can make the later indivisible cut unsafe | partnered-4 | full | high |
| R3 | 5/5: a locally green partial owner migration can corrupt non-local behavior | partnered-5 | thorough | xhigh |
| R4 | 4/5: duplicated or misplaced equivalence semantics can pass narrow tests | partnered-4 | full | high |
| R5 | 5/5: async/controller topology can leak authority despite green unit tests | partnered-5 | thorough | xhigh |
| R6 | 5/5: recovery and legacy migration can silently damage durable authority | partnered-5 | thorough | high |
| R7 | 4/5: environment or matrix gaps can hide composed runtime failures | partnered-4 | full | high |
| R8 | 4/5: a weak deletion/proof audit can falsely declare the architecture clean | partnered-4 | thorough | high |

All milestones use prep because each begins with an explicit inventory or
composition discovery boundary. Critique/review effort follows profile defaults;
depth is spent on author phases, consistent with the asymmetry principle.

## Execution policy

Close a bounded unit after two independent acceptances, focused adversarial
coverage, and the relevant broad green gates. Do not commission a third review
without contradictory evidence. This reduces repetitive review, not product
scope. No milestone may waive an ownership cut, deletion audit, recovery row,
real-ComfyUI scenario, proof-map item, or final audit condition.

On a timing flake, rerun the exact failure once and the full relevant suite
once. If both pass, record it and proceed unless the failure reproduces.

## Deferred boundary

Nested scopes/subgraphs, universal third-party compatibility, arbitrary manual
graph repair, and product tuning beyond safe retention defaults are deferred.
They must not be implemented opportunistically in this chain.
