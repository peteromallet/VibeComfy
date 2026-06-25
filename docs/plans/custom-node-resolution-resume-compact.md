# Rules
* Finish the whole `custom-node-resolution` megaplan; no partial/best-effort cleanup.
* Continue in:
```text
/Users/peteromalley/Documents/reigh-workspace/vibecomfy
```
* Use subagents via `/Users/peteromalley/Documents/poms_skills/subagent-launcher/SKILL.md`.
* Fix root causes in agent-edit harness, custom-node resolution, research/search tools, tests, runner, docs, or scripts.
* Do not add deterministic local-only filtering. The agent must choose searches/sources and inspect results before deciding next steps.
* Local ComfyUI schema absence must not block registry/web/workflow/message research.
* Preserve profile/model selections. Fix Arnold harness bugs at root if they recur.

# Files
```text
Brief: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/briefs/custom-node-resolution.md
Plan dir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.megaplan/plans/custom-node-resolution-and-20260624-1752
Resume detail: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/docs/plans/custom-node-resolution-megaplan-resume-goal.md
```

# State
Plan `custom-node-resolution-and-20260624-1752` is `planned`, iteration 2, next `critique`. Last step `revise` succeeded and produced `plan_v2.md`. Lock file exists but is not held. No active step. Do not restart from `prep`, `plan`, or `plan_v1`. Other unrelated megaplan runners exist; do not duplicate or kill them.

# Resume
```bash
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy
ps -axo pid,ppid,command | rg 'custom-node-resolution-and-20260624-1752|custom-node-resolution|arnold_pipelines.megaplan|arnold.pipelines.megaplan' | rg -v 'rg '
PYTHONPATH=/Users/peteromalley/Documents/Arnold python -m arnold_pipelines.megaplan status --plan custom-node-resolution-and-20260624-1752
PYTHONPATH=/Users/peteromalley/Documents/Arnold python -m arnold_pipelines.megaplan critique --plan custom-node-resolution-and-20260624-1752
```
