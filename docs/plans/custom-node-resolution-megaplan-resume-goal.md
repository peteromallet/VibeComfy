# /goal

## Objective

Drive the VibeComfy custom-node resolution megaplan to completion. Do not stop at
plan cleanup or partial diagnosis. The goal is an implemented and verified
workflow where the agent can resolve missing ComfyUI custom nodes through
agent-chosen research/registry/workflow sources, build a usable candidate graph,
and hand ComfyUI enough information for installation/review instead of falsely
blocking on local schema absence.

## Rules

- Drive the megaplan to completion; no partial cleanup.
- Worktree:

```text
/Users/peteromalley/Documents/reigh-workspace/vibecomfy
```

- Arnold engine:

```text
/Users/peteromalley/Documents/Arnold
```

- Use subagents via:

```text
/Users/peteromalley/Documents/poms_skills/subagent-launcher/SKILL.md
```

- Fix root causes in the agent-edit harness, search/research tool contract,
  custom-node registry resolution, tests, runner, docs, or scripts.
- Do not paper over missing nodes by adding deterministic local-only filtering.
  The agent should choose the research path and should be able to inspect the
  result before deciding whether to search elsewhere.
- Do not preserve the old failure mode where local ComfyUI schema absence blocks
  online/registry/workflow research.
- Preserve existing profile/model choices unless the user explicitly changes
  them.
- Watch for Arnold runner bugs discovered during this work:
  - local dev turn caps should not block by default;
  - malformed tool calls must not become `read_file("")`;
  - engine isolation should not fail in valid local-dev split-root runs;
  - duplicate Arnold package trees can produce stale-copy behavior.
- If those harness issues recur, fix the root in Arnold rather than working
  around it in VibeComfy.

## Files

```text
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/briefs/custom-node-resolution.md
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/docs/plans/custom-node-resolution-install-plan.md
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/plans/custom-node-resolution-and-20260624-1752/plan_v1.md
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/plans/custom-node-resolution-and-20260624-1752/plan_v2.md
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/plans/custom-node-resolution-and-20260624-1752/critique_v1.json
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/plans/custom-node-resolution-and-20260624-1752/gate.json
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/plans/custom-node-resolution-and-20260624-1752/state.json
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/telemetry/custom-node-resolution-and-20260624-1752.ndjson
```

Relevant Arnold root-fix note:

```text
/Users/peteromalley/Documents/Arnold/docs/arnold/megaplan-single-implementation-root-fix.md
```

## Current State

Plan: `custom-node-resolution-and-20260624-1752`.

Current status as of 2026-06-24:

- State: `planned`
- Iteration: `2`
- Next step: `critique`
- Last step: `revise`
- Last result: `success`
- Last output: `plan_v2.md`
- Active step: none
- Lock file present: yes
- Lock held: no
- Total cost so far: about `$1.90`

Earlier state was `critiqued` with next step `revise`, but the interrupted
revise later completed successfully. Do not restart from `prep` or `plan_v1`.
Continue from `plan_v2.md` by running the next valid step.

There are other megaplan processes running on this machine, including Reigh and
other VibeComfy worktrees. They are not this custom-node plan. Do not kill or
duplicate unrelated runners.

## Resume

```bash
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy

ps -axo pid,ppid,command \
  | rg 'custom-node-resolution-and-20260624-1752|custom-node-resolution|arnold_pipelines.megaplan|arnold.pipelines.megaplan' \
  | rg -v 'rg '

PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  python -m arnold_pipelines.megaplan status \
  --plan custom-node-resolution-and-20260624-1752
```

If no active step is shown for `custom-node-resolution-and-20260624-1752`, run:

```bash
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy

PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  python -m arnold_pipelines.megaplan critique \
  --plan custom-node-resolution-and-20260624-1752
```

Then continue the normal sequence until completion:

```bash
PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  python -m arnold_pipelines.megaplan gate \
  --plan custom-node-resolution-and-20260624-1752

PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  python -m arnold_pipelines.megaplan execute \
  --plan custom-node-resolution-and-20260624-1752

PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  python -m arnold_pipelines.megaplan review \
  --plan custom-node-resolution-and-20260624-1752

PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  python -m arnold_pipelines.megaplan finalize \
  --plan custom-node-resolution-and-20260624-1752
```

Before each step, check status again. If a watcher has restarted the same plan,
do not duplicate it.

## What To Verify

- The agent-edit tool exposes research choices that the model can decide between,
  such as local schema, workflow corpus, message corpus, node registry, GitHub,
  and web search.
- Web/registry/workflow research is not gated by local ComfyUI schema matches.
- The model can inspect research results and decide whether to search again with
  different terms or sources.
- Missing local custom nodes can produce a candidate graph or installable-node
  review state instead of a false hard block.
- The Hotshot/AnimateDiff-style case is covered by tests or an agentic fixture:
  local schema search can fail, broader research can find the relevant package or
  workflow, and the tool can carry that evidence forward.
- Browser/panel behavior at `http://127.0.0.1:8190/` still works after changes.
- If ComfyUI needs a restart, relaunch it only after confirming no unrelated
  process will be interrupted.

## Known Hazards

- Do not use `python -m arnold.pipelines.megaplan` for new work. Use
  `python -m arnold_pipelines.megaplan`.
- If `engine_write_isolation_unverified` appears in a valid local dev split-root
  run, check Arnold duplicate-package drift before treating it as a VibeComfy
  issue.
- If `read_file` errors with an empty path, check Arnold Hermes/tool parsing
  rather than patching the specific prompt only.
- If a turn cap blocks progress in local dev, check Arnold turn-cap defaults and
  stale lock metadata before assuming real concurrent premium turns exist.
