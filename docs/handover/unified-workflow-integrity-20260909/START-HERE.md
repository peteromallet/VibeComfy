# Unified workflow integrity handover

This is a portable, planning-only Megado handover for VibeComfy's canonical workflow integrity and editable Python work. It consolidates the save/export integrity plan with the absorbed Pythonic-emission contract. It does not claim implementation, tests, review PASS, merge, deployment, or generated-video success.

Project: `VibeComfy`

Remote: `https://github.com/peteromallet/VibeComfy.git`

Base: `20975e25f0401b64f51dfeef5d1250cfbd97600f`

Receiving branch: `handover/unified-workflow-integrity-20260909`

Receiving mode: `planning_only`

The handover preserves D1, I1–I10, E0–E2, C0/T0–T4, review counters, and the two existing review stages. Source closure is resolved and pinned dependency reads are verified: no dirty source patch is required. Verify your checkout and available environment/capabilities as described in provenance.md and dependencies.md.

## Start

```sh
git clone --branch handover/unified-workflow-integrity-20260909 --single-branch https://github.com/peteromallet/VibeComfy.git VibeComfy-unified-workflow
git -C VibeComfy-unified-workflow rev-parse HEAD
```

Read `goal.md`, `northstar.md`, `run.yaml`, `status.md`, `consolidation.md`, `plan.md`, `tasklist.md`, `acceptance-ledger.md`, and `execution-start.md`. The H3 source input is `assets/h3/MiniMax_H3_AV_EncodeDecode_Inpaint.json`; its SHA-256 is recorded in `evidence/h3-main-baseline.md`.

Planning-only means no implementation or product tests are authorized by this package. If explicit execution authority arrives, update only the authoritative `run.yaml` mode while preserving roles, counters, stages, caps, and boundaries.

The ready-to-send message is [assets/handover-message.md](assets/handover-message.md). Publication is limited to this handover branch; the receiver retains planning-only mode until explicit delivery instruction.

Latest requested [Astra end-state sense check](evidence/astra-end-state-sense-check.md): two evidence clarifications are adopted in the acceptance ledger and task briefs. No product tests or implementation are claimed.
