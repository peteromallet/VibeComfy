# Agent Edit Robustness Finish

This residual epic completes the architecture defined by
`docs/plans/agent-edit-complete-robustness-architecture.md` without rewriting
the running history under `agent-edit-complete-robustness`.

It starts from the repaired `agent/agent-edit-robustness-foundation` history,
including every repair through `a395c243`. `FOUNDATION.md` enumerates that
stack and is a tracked, content-checked chain launch precondition. The chain
must not launch from the former `7934834f` tip. The current-state ledger in the
predecessor initiative remains the authority for what is already proved.
For clarity, `FOUNDATION.md` supersedes predecessor status text about C2a being
uncommitted and records the later repairs; predecessor ledgers remain
authoritative for M0–M2 closure and native-owner transfer.

## Routing policy

- Easy execution and bounded factual checks: DeepSeek Pro.
- Medium execution: Claude Code using the active GLM 5.2 provider.
- Hard execution: Claude Code using the active GLM 5.2 provider with higher
  reasoning.
- Exceptional escalation only: GPT-5.6 Sol.

Megaplan profile selection is an independent planning-quality dial. Every
milestone declares `vendor: claude`; the operator must prove that Claude Code
resolves to GLM 5.2 before starting the chain.

## Residual milestones

| Label | Outcome |
| --- | --- |
| R1 | Seal C2a and build a private, faithfully tested native execution core. |
| R2 | Prove cutover readiness with an exact manifest, ledger rehearsal, faithful fault harness, and real incident reproduction; move no owner. |
| R3 | Atomically cut every native consumer to the adapter, delete old owners, close M2, and prove the decisive incidents. |
| R4 | Establish the single Apply/rollback verifier. |
| R5 | Establish the workflow-scoped controller and sole transport API. |
| R6 | Make recovery, Undo, and legacy behavior exhaustive and durable. |
| R7 | Build the pinned correctness/compatibility environments and exhaustive real-ComfyUI lifecycle CI matrix. |
| R8 | Perform terminal cleanup and directly prove the nine-point architecture before emitting the completion manifest. |

The chain is strictly dependency ordered. R2 moves no production owner, R3 is
the indivisible owner transfer, and R8 cannot start until R7's composed matrix
and R6's recovery evidence exist. No partial native-owner cut may merge.

## Protected work

`scorecard.png` and
`docs/plans/vibecomfy-screen-share-recording-brief.md` are unrelated. Every
milestone must preserve them byte-for-byte and exclude them from commits,
staging, generated manifests, and cleanup.

## Completion rule

Passing tests is necessary but not sufficient. Completion requires every
proof-map entry, zero open S3/S4 native-authority rows, removal of duplicate
owners/dead exports/compatibility facades, a reduced `vibecomfy_roundtrip.js`,
the nine-point North Star audit, and a fresh content-addressed chain completion
manifest.
