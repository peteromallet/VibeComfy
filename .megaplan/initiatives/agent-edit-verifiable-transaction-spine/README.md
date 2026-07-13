# Agent Edit Verifiable Transaction Spine

Two-sprint hardening of VibeComfy agent-edit authority, evidence, transactionality, and topology-truthful reorganisation.

## Milestones

1. Authority Preservation and Canonical Candidate
2. Transactional Apply and Topology-Truthful Reorganisation

The initiative is designed for unattended cloud execution with automatic merge
between milestones. Its current operator endpoint is **prepared but not
launched**: preflight and remote sync may be performed without starting the
chain.

## Preparation commands

```bash
python -m arnold_pipelines.megaplan cloud preflight \
  .megaplan/initiatives/agent-edit-verifiable-transaction-spine/chain.yaml \
  --cloud-yaml .megaplan/initiatives/agent-edit-verifiable-transaction-spine/cloud.yaml

python -m arnold_pipelines.megaplan cloud sync-megaplan \
  .megaplan/initiatives/agent-edit-verifiable-transaction-spine/chain.yaml \
  --cloud-yaml .megaplan/initiatives/agent-edit-verifiable-transaction-spine/cloud.yaml \
  --clean
```

The launch command is intentionally omitted to prevent accidental start during
preparation.
