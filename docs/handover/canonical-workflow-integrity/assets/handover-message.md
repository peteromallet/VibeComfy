# Copy-paste delivery instruction

Implement the VibeComfy canonical workflow integrity plan using Megado.

Clone both repositories into unused directories on this machine:

```sh
git clone --branch handover/canonical-workflow-integrity-20260908 https://github.com/peteromallet/VibeComfy.git VibeComfy-integrity
git clone https://github.com/peteromallet/poms-skills.git poms-skills
git -C poms-skills checkout --detach 63825bbb191a0539c0b99832099966ee9f23e3e2
```

Read `poms-skills/megado/SKILL.md` ([Megado](https://github.com/peteromallet/poms-skills/blob/63825bbb191a0539c0b99832099966ee9f23e3e2/megado/SKILL.md)) and follow it. You can use it directly without installing it globally. Preserve existing directories and work if either clone path is occupied.

Then read `VibeComfy-integrity/docs/handover/canonical-workflow-integrity/START-HERE.md`. That directory contains the North Star, plan, tasklist, acceptance criteria, run configuration, review contract, history, and current status. The project code is included in the same branch.

You are authorized to execute C0 and T0–T4, run the configured tests and reviews, and return validated local commits and evidence. Activate run.yaml from planning_only to delivery as documented. Do not request another approval to begin.

Use the configured role slots:

- Coordinator: Luna medium
- Normal worker: Luna medium
- XHARD worker: Sol high
- Normal reviewer: Astra medium
- XHARD reviewer: Sol high
- Oracle: Astra high
- Final reviewer: Astra medium

Remaining review ceilings: 2 save/export completion reviews and 3 final integrated completion/strategy reviews, including correction rounds and restarts; 3 separate oracle calls. These are ceilings, not quotas. Preserve the 5 historical review calls and 4 historical oracle calls, for lifetime caps of 10 reviews and 7 oracle calls. Follow the artifact-based review contract in run.yaml and its linked template.

First check repository state, Python 3.11+, development dependencies, and native delegation/model access using dependencies.md. Recipient capability is unverified; report missing access without silent substitutions. Planning is complete; implementation acceptance evidence is NOT RUN. The existing source snapshot is not certification.

Preserve trustworthy save/reload/export and valid drafts, existing rule owners, transports, and revision protection. Test Python/typed parity before changing it. No generic framework, speculative rewrite, or extra review process. Implementation push, PR, merge, deployment, and production cutover remain outside the receiving authorization.

Complete implementation and validation, then provide local commit IDs, criterion/test evidence, review outcomes, and unresolved blockers.

Prepared baseline commits:

- VibeComfy source: `79414f56d5135badef8268ef1d89861c9a5fbd06`; the handover branch adds planning documents on top.
- poms-skills: `63825bbb191a0539c0b99832099966ee9f23e3e2`.
