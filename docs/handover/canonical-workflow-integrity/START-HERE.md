# VibeComfy canonical workflow integrity handover

Execute the existing two-segment plan; do not restart planning. This public handover contains current working source plus the portable plan. The preparer has not implemented or certified the product plan.

Source snapshot: `79414f56d5135badef8268ef1d89861c9a5fbd06`. Handover branch: `handover/canonical-workflow-integrity-20260908`. Pinned skills: `63825bbb191a0539c0b99832099966ee9f23e3e2` from public poms-skills. See [provenance](./provenance.md) for intentional dirty-source inclusion and omitted logs.

Read in order: [goal/authority](./agent_goal.md), [North Star](./northstar.md), [configuration](./run.yaml), [plan](./plan.md), [tasks](./tasklist.md), [acceptance/evidence](./acceptance-ledger.md), [status/counters](./status.md), [history/rulings](./history.md), [dependencies](./dependencies.md). The [review packet template](./review-packet-template.md) is a template, not actual executable evidence.

## Start safely

```sh
git clone --branch handover/canonical-workflow-integrity-20260908 --single-branch https://github.com/peteromallet/VibeComfy.git VibeComfy-integrity
cd VibeComfy-integrity
git merge-base --is-ancestor 79414f56d5135badef8268ef1d89861c9a5fbd06 HEAD
git status --short
```

Clone fails rather than overwriting an existing checkout. Record the handover HEAD as the receiving base; it includes source snapshot and documents. Fetch/read the exact skill pin using dependencies.md; verify model/tool prerequisites. Prepare isolated delivery custody using the pinned execution mechanics and ordinary Git tools. Carry these documents to the run control directory and rebase only filesystem locations, preserving logical run identity `canonical-integrity-plan-20260908`, accepted decisions and every consumed counter.

On accepting authorized delivery, change run.yaml mode to delivery in the receiving run's single authoritative copy. Do not alter bindings, ceilings or stage scopes just because the default skill evolved. Source fixes already present in this snapshot may satisfy parts of the old plan; verify before changing. No new scope or compatibility framework.

Finish with a validated local implementation commit, per-criterion evidence, configured review results and unresolved risks. No implementation push, PR, merge, deployment or cutover is granted. The preparer's authorized handover publication is separate.

The ready-to-forward instruction is [assets/handover-message.md](./assets/handover-message.md). All relative artifact links resolve from this directory; historical local receipt references inside planning notes are descriptions, with portable outcomes preserved in history.md.
