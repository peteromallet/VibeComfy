# Copy-paste delivery instruction

Continue VibeComfy canonical workflow integrity from the public branch `handover/canonical-workflow-integrity-20260908` at https://github.com/peteromallet/VibeComfy.git. Its intentional current-source snapshot is `79414f56d5135badef8268ef1d89861c9a5fbd06`; the handover-doc commit descends from it. Exact inspected Megado skills: https://github.com/peteromallet/poms-skills.git at `c919ed5c51508d1c1678e88172ba8366e07038fb`.

```sh
git clone --branch handover/canonical-workflow-integrity-20260908 --single-branch https://github.com/peteromallet/VibeComfy.git VibeComfy-integrity
cd VibeComfy-integrity
git merge-base --is-ancestor 79414f56d5135badef8268ef1d89861c9a5fbd06 HEAD
```

Read `docs/handover/canonical-workflow-integrity/START-HERE.md` and its linked pinned Megado skill/dependencies. Planning is complete; implementation evidence is NOT RUN. The user authorizes you to execute the bounded plan on an isolated local branch and return validated local commits/evidence. Activate delivery in the single run.yaml copy; retain its roles, model/reasoning bindings, review/oracle caps and historical counters. Do not restart planning or treat old planning PASS as product proof.

Objective: trustworthy save/reload/export preserving intended workflow content and valid drafts, then test-first Python/typed parity and accurate docs. Keep existing rule owners, transports and revision protection; no generic framework or speculative rewrite. Stage triggers/scopes/budgets come from run.yaml: save/export completion and final integrated completion/strategy, with inclusive round/restart caps and separate bounded oracle decisions. Prior spending remains in status.md/history.md; do not reset it.

Check Git/Python/dev dependencies and native delegation/model access as described in dependencies.md. Luna/Astra were used by the preparer; Sol is reserved and untested here; recipient access is unverified. Report missing capabilities rather than substituting. Assemble real review packets from actual candidate/test artifacts later.

Finish: report implementation commit ID, criterion/test evidence, review outcomes and unresolved risks. No PR, implementation push, merge, deploy or production cutover unless separately authorized.
