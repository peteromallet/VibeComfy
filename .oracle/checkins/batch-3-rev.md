Reading additional input from stdin...
2026-08-13T19:56:11.115879Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:56:11.115941Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:56:11.115956Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffcb2-47b0-7872-8696-b494c1a7506f
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 3 RESUBMISSION — Batch D+E task-6 rework review.

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Batch D+E commit 0d2bb176 (tasks 1-5 already PASS in your prior review). Rework commit: 6e97450a7b75551d30d8e0a48a4e529e4cf15963. Review `git diff 0d2bb176..HEAD`.

Your prior FAIL had two blockers (both now claimed fixed):
1. emit_subgraph.py:292,340 stored ["-10", slot] boundary links in real VibeNode.inputs; narrow predicate missed negative ids.
2. emit_ui_json (ui.py:2043) silently emitted links=[] for VibeNode(inputs={"image": ["1",0]}) instead of failing closed.

Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.

## Your verdict
Binary PASS or concrete issues. Specifically verify:
1. No remaining package-owned construction stores ANY link pair (incl. negative boundary ids) in VibeNode.inputs — grep emit_subgraph.py + the predicate.
2. emit_ui_json now raises (targeted error) on raw-link-only inputs and raw-link-plus-edge collisions; canonical edge-only emit unchanged.
3. The 6 blocker-regression tests exist and are meaningful (not tautological).
Do NOT edit. Read-only.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill to follow the oracle checkpoint protocol, then I’ll inspect only the rework diff, relevant constructors/predicate, and the six claimed regression tests. No files will be changed.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. GPT-5.6 Sol plans and revises, DeepSeek V4 Flash explores and executes, a GPT-5.6 Sol or Grok 4.6 oracle gates each batch. The oracle and [XHARD] tasks are managers/validators that delegate to Flash via OMP. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

Plan → explore → revise → execute → oracle-gate → sync, all in a worktree, never on main.

- **Planner** — GPT-5.6 Sol (codex exec, high reasoning): tasklist, revision, batch design.
- **Explorer / Executor** — DeepSeek V4 Flash: all exploration and normal execution.
- **Oracle** — GPT-5.6 Sol or Grok 4.6 (grok CLI): gates every batch; rework until it passes.
- **`[XHARD]` tasks** — GPT-5.6 Sol: extremely hard tasks, tagged in the tasklist.

One orchestrator (the host) drives all phases, holds the `.oracle/` artifacts, and writes every brief. Escalate Flash exploration to DeepSeek V4 Pro only on evidence that Flash's findings are thin.

## Roles

| Role | Model | Invocation | Sandbox |
| --- | --- | --- | --- |
| **Planner** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | read-only |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Oracle** | GPT-5.6 Sol or Grok 4.6 | codex as Planner · `grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high` | danger-full-access\* |
| **`[XHARD]` executor** | GPT-5.6 Sol | codex as Planner | danger-full-access\* |

\* `danger-full-access` because the mandate requires delegating to Flash via OMP, which needs outbound network. `read-only` / `--permission-mode plan` / `workspace-write` only for pure non-delegating work — planning, a review that dispatches nothing, or a task that genuinely cannot be delegated.

## Delegation mandate — verbatim in every oracle check-in brief and `[XHARD]` task brief

> DELEGATION MANDATE — You are a manager and validator of DeepSeek V4 Flash, NOT a worker. Use Flash via OMP for as much of this work as possible: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800` (research-only briefs: add `--tools read,glob,grep,web_search`). Dispatch research, execution, and critique briefs to Flash — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read Flash's output against the acceptance criteria; do work yourself only when delegation is impossible — Flash already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a Flash brief would cover it. It almost always would.

## Artifacts (in the worktree)

```
.oracle/
  plan.md            # living plan, revised until stable
  briefs/            # one brief per explorer / executor batch
  findings/          # explorer outputs: <area>.txt (+ .meta.json from fan.py)
  tasklist.md        # frozen batched task list with checkpoints + [XHARD] tags
  checkins/          # oracle verdicts: batch-<N>.md
  status.md          # current phase, batch, checkpoint state
```

## Phase 0 — Worktree

```bash
git worktree add ../<project>-oracle -b oracle-run
cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins
```

## Phase 1 — Plan (Codex, read-only)

Brief Sol: (1) a tasklist covering the **entirety** of the project, (2) **additional areas to explore** for full clarity, (3) open questions. The brief is a spec, not a memo. Save the result as `.oracle/plan.md` (host writes it; Codex stays read-only).

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/plan-brief.md)" </dev/null > /tmp/plan-v1.txt 2>&1
```

## Phase 2 — Explore (DeepSeek fan-out)

One Flash agent per area, in parallel. `fan.py` for ≥ ~5 areas; `launch_hermes_agent.py` per area below that. Each brief: "Explore area X in depth. Report verified facts with file/line evidence, unknowns, risks, and a suggested approach. Ranked findings, <300 words." Mechanical briefs — no license to architect.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
```

## Phase 3 — Revise until STABLE (Codex, read-only)

Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Sol:

> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

New material areas → re-run Phase 2 for them, then revise again. Repeat until `STABLE` (or two consecutive rounds with no material change).

## Phase 4 — Tasklist (Codex, read-only)

Convert the stable plan into `.oracle/tasklist.md` — **frozen** after this:

- **Sensible batches** — self-contained, ending at natural seams.
- **One checkpoint per batch** — with acceptance criteria the oracle will verify.
- **`[XHARD]` tags** on extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not Flash.

Plan revisions during execution go through the oracle, not silent edits.

## Phase 5 — Execute, gated per batch

Commit after each batch so the oracle sees a clean delta (`git diff <last-checkpoint-sha>..HEAD`). Then, per batch:

**1. Execute.** Flash takes every non-`[XHARD]` task, one agent per batch:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
```

`[XHARD]` tasks go to Sol instead (brief carries the delegation mandate):

```bash
timeout 1800 codex exec --sandbox danger-full-access -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/hard-task-brief.md)" </dev/null
```

**2. Checkpoint — oracle review.** The check-in brief carries the batch's tasks + acceptance criteria, the delta since the last checkpoint, and the delegation mandate. The oracle dispatches verification, research, and critique passes to Flash where useful — critiques biased toward elegance (KISS, YAGNI, cut scope that isn't pulling its weight) — then judges the results. Verdict is binary: `PASS` or a list of issues.

```bash
# GPT-5.6 Sol (danger-full-access; see Roles footnote)
timeout 1800 codex exec --sandbox danger-full-access -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/checkin-brief.md)" </dev/null > .oracle/checkins/batch-<N>.md 2>&1
# Grok 4.6 (no --permission-mode plan — the mandate requires delegating to Flash)
grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high \
  > .oracle/checkins/batch-<N>.md 2>&1
```

**3. Rework.** On issues, send them back to the executor (Flash for normal, Sol for XHARD), re-run, re-review — until the oracle passes. **Do not start batch N+1 until batch N passes.**

## Phase 6 — Completion

1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
3. `open` the worktree / project and report phase-by-phase evidence.

## Gotchas

- **Seal codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU (output file stuck at the banner size). Allow 30 min (`timeout 1800`) for write-heavy/review runs.
- **OMP delegations need outbound network** — oracle and XHARD codex runs must use `--sandbox danger-full-access`; the grok oracle must not pass `--permission-mode plan`.
- **Elegance bias is a real instruction** — Sol's revision prompt and every critique brief dispatched to Flash must name it (KISS, YAGNI, cut scope); otherwise reasoning models add scope, not subtract it.
- **Match brief shape to model mode** — Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs. Judgement stays with Sol / the Grok oracle.
- **Liveness ≠ correctness** — a live agent can still answer uselessly; read the response.
- **Checkpoint discipline is the whole game** — skipping the oracle gate to "save a cycle" collapses this into a plain Flash run.

## Quick reference

```bash
# Phase 0
git worktree add ../<project>-oracle -b oracle-run && cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins

# Phase 1 — plan (Sol, read-only)
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/plan-brief.md)" </dev/null

# Phase 2 — explore (Flash, fan N areas)
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"

# Phase 3 — revise: repeat 2↔3 until Sol says STABLE
# Phase 4 — Sol emits .oracle/tasklist.md (batches, checkpoints, [XHARD] tags)

# Phase 5 — execute (Flash per batch, one agent)
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
# [XHARD] tasks (brief carries the mandate): codex exec --sandbox danger-full-access -c model=gpt-5.6-sol -c model_reasoning_effort=high
# checkpoint (brief carries the mandate): codex exec --sandbox danger-full-access -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/checkin-brief.md)" </dev/null
#   or: grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high

# Phase 6 — commit, push, open
git add -A && git commit -m "megado: <project>" && git push && open .
```

exec
/bin/zsh -lc 'git status --short --branch && git diff --stat 0d2bb176..HEAD && git diff --check 0d2bb176..HEAD && git diff --name-only 0d2bb176..HEAD' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 2 in 163ms:
## elegance-run2
?? .oracle/checkins/batch-3-rev.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-3.md                        | 15391 +++++++++++++++++++
 tests/fixtures/recipes/example_tested_recipe.py    |     9 +-
 .../recipes/example_tested_recipe.py.snapshot.json |     4 +-
 tests/intent/test_static_lowering.py               |     6 +-
 tests/test_cli_misc.py                             |     6 +-
 tests/test_comfy_nodes_agent_backend_spine.py      |    10 +-
 tests/test_finalize_metadata.py                    |     4 +-
 tests/test_foundation_utils.py                     |     1 +
 tests/test_intent_nodes.py                         |     6 +-
 tests/test_porting_synthetic_fixtures.py           |     3 +-
 tests/test_porting_ui_emitter.py                   |   144 +-
 tests/test_testing_assertions.py                   |     2 +-
 tests/test_testing_dry_run.py                      |     2 +-
 tests/test_testing_pytest_plugin.py                |     5 +-
 tests/test_testing_snapshot.py                     |     5 +-
 tests/test_widget_shape_evidence.py                |     1 -
 vibecomfy/_compile/_graph.py                       |    21 +-
 vibecomfy/porting/emit/emit_kwargs.py              |    24 +-
 vibecomfy/porting/emit/emit_subgraph.py            |     8 +-
 vibecomfy/porting/emit/ui.py                       |     4 +-
 20 files changed, 15617 insertions(+), 39 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-3.md:320: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:322: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:324: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:326: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:328: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:330: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:332: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:334: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:336: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:338: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:340: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:342: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:344: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:346: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:348: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:350: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:352: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:354: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:356: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:358: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:360: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:362: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:364: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:366: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:368: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:370: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:372: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:374: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:376: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:378: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:380: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:382: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:384: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:386: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:388: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:390: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:392: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:394: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:396: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:398: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:400: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:402: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:404: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:406: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:408: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:410: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:412: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:414: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:416: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:418: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:420: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:422: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:424: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:426: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:428: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:430: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:432: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:434: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:436: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:438: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:440: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:442: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:444: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:446: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:448: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:450: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:452: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:454: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:456: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:458: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:460: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:462: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:464: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:466: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:468: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:470: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:472: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:474: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:476: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:478: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:480: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:482: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:484: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:486: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:488: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:490: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:492: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:494: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:496: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:498: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:500: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:502: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:504: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:506: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:508: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:510: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:512: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:514: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:516: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:518: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:520: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:522: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:524: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:526: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:528: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:530: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:532: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:534: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:536: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:538: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:540: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:542: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:544: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:546: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:548: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:550: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:552: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:554: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:556: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:558: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:560: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:562: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:564: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:566: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:568: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:570: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:572: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:574: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:576: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:578: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:580: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:582: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:584: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:586: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:588: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:590: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:592: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:594: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:596: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:598: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:600: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:602: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:604: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:606: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:608: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:610: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:612: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:614: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:616: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:618: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:620: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:622: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:624: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:626: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:628: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:630: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:632: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:634: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:636: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:638: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:640: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:642: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:644: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:646: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:648: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:650: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:652: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:654: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:656: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:658: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:660: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:662: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:664: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:666: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:668: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:670: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:672: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:674: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:676: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:678: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:680: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:682: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:684: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:686: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:688: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:690: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:692: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:694: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:696: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:698: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:700: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:702: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:704: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:706: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:708: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:710: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:712: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:714: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:716: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:718: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:720: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:722: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:724: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:726: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:728: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:730: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:732: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:734: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:736: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:738: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:740: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:742: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:744: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:746: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:748: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:750: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:752: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:754: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:756: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:758: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:760: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:762: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:764: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:766: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:768: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:770: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:772: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:774: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:776: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:778: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:780: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:782: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:784: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:786: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:788: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:790: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:792: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:794: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:796: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:798: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:800: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:802: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:804: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:806: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:808: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:810: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:812: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:814: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:816: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:818: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:820: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:822: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:824: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:826: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:828: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:830: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:832: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:834: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:836: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:838: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:840: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:842: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:844: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:846: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:848: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:850: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:852: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:854: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:856: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:858: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:860: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:862: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:864: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:866: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:868: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:870: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:872: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:874: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:876: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:878: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:880: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:882: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:884: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:886: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:888: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:890: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:892: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:894: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:896: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:898: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:900: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:902: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:904: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:906: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:908: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:910: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:912: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:914: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:916: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:918: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:920: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:922: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:924: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:926: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:928: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:930: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:932: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:934: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:936: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:938: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:940: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:942: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:944: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:946: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:948: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:950: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:952: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:954: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:956: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:958: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:960: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:962: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:964: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:966: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:968: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:970: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:972: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:974: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:976: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:978: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:980: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:982: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:984: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:986: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:988: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:990: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:992: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:994: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:996: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:998: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1000: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1002: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1004: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1006: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1008: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1010: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1012: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1014: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1016: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1018: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1020: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1022: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1024: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1026: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1028: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1030: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1032: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1034: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1036: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1038: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1040: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1042: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1044: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1046: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1048: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1050: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1052: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1054: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1056: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1058: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1060: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1062: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1064: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1066: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1068: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1070: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1072: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1074: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1076: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1078: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1080: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1082: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1084: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1086: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1088: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1090: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1092: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1094: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1096: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1098: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1100: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1102: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1104: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1106: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1108: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1110: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1112: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1114: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1116: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1118: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1120: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1122: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1124: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1126: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1128: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1130: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1132: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1134: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1136: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1138: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1140: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1142: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1144: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1146: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1148: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1150: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1152: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1154: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1156: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1158: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1160: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1162: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1164: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1166: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1168: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1170: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1172: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1174: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1176: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1178: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1180: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1182: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1184: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1186: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1188: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1190: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1192: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1194: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1196: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1198: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1200: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1202: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1204: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1206: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1208: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1210: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1212: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1214: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1216: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1218: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1220: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1222: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1224: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1226: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1228: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1230: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1232: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1234: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1236: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1238: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1240: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1242: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1244: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1246: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1248: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1250: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1252: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1254: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1256: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1258: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1260: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1262: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1264: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1266: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1268: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1270: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1272: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1274: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1276: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1278: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1280: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1282: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1284: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1286: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1288: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1290: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1292: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1294: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1296: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1298: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1300: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1302: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1304: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1306: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1308: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1310: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1312: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1314: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1316: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1318: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1320: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1322: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1324: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1326: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1328: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1330: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1332: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1334: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1336: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1338: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1340: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1342: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1344: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1346: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1348: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1350: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1352: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1354: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1356: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1358: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1360: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1362: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1364: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1366: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1368: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1370: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1372: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1374: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1376: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1378: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1380: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1382: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1384: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1386: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1388: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1390: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1392: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:1394: trailing whitespace.
++   719	
.oracle/checkins/batch-3.md:1396: trailing whitespace.
++   726	
.oracle/checkins/batch-3.md:1398: trailing whitespace.
++   728	
.oracle/checkins/batch-3.md:1400: trailing whitespace.
++   730	
.oracle/checkins/batch-3.md:1402: trailing whitespace.
++   731	
.oracle/checkins/batch-3.md:1404: trailing whitespace.
++   734	
.oracle/checkins/batch-3.md:1406: trailing whitespace.
++   740	
.oracle/checkins/batch-3.md:1408: trailing whitespace.
++   741	
.oracle/checkins/batch-3.md:1410: trailing whitespace.
++   769	
.oracle/checkins/batch-3.md:1412: trailing whitespace.
++   770	
.oracle/checkins/batch-3.md:1414: trailing whitespace.
++   786	
.oracle/checkins/batch-3.md:1416: trailing whitespace.
++   787	
.oracle/checkins/batch-3.md:1418: trailing whitespace.
++   794	
.oracle/checkins/batch-3.md:1420: trailing whitespace.
++   795	
.oracle/checkins/batch-3.md:1422: trailing whitespace.
++   829	
.oracle/checkins/batch-3.md:1424: trailing whitespace.
++   830	
.oracle/checkins/batch-3.md:1426: trailing whitespace.
++     2	
.oracle/checkins/batch-3.md:1428: trailing whitespace.
++     6	
.oracle/checkins/batch-3.md:1430: trailing whitespace.
++     7	
.oracle/checkins/batch-3.md:1432: trailing whitespace.
++    14	
.oracle/checkins/batch-3.md:1434: trailing whitespace.
++    15	
.oracle/checkins/batch-3.md:1436: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:1438: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:1440: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:1442: trailing whitespace.
+++    15	
.oracle/checkins/batch-3.md:1444: trailing whitespace.
+++    31	
.oracle/checkins/batch-3.md:1446: trailing whitespace.
+++    35	
.oracle/checkins/batch-3.md:1448: trailing whitespace.
+++    37	
.oracle/checkins/batch-3.md:1450: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:1452: trailing whitespace.
+++    43	
.oracle/checkins/batch-3.md:1454: trailing whitespace.
+++    45	
.oracle/checkins/batch-3.md:1456: trailing whitespace.
+++    53	
.oracle/checkins/batch-3.md:1458: trailing whitespace.
+++    58	
.oracle/checkins/batch-3.md:1460: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:1462: trailing whitespace.
+++    65	
.oracle/checkins/batch-3.md:1464: trailing whitespace.
+++    66	
.oracle/checkins/batch-3.md:1466: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:1468: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:1470: trailing whitespace.
+++    83	
.oracle/checkins/batch-3.md:1472: trailing whitespace.
+++    84	
.oracle/checkins/batch-3.md:1474: trailing whitespace.
+++    88	
.oracle/checkins/batch-3.md:1476: trailing whitespace.
+++    89	
.oracle/checkins/batch-3.md:1478: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:1480: trailing whitespace.
+++    98	
.oracle/checkins/batch-3.md:1482: trailing whitespace.
+++   110	
.oracle/checkins/batch-3.md:1484: trailing whitespace.
+++   111	
.oracle/checkins/batch-3.md:1486: trailing whitespace.
+++   116	
.oracle/checkins/batch-3.md:1488: trailing whitespace.
+++   117	
.oracle/checkins/batch-3.md:1490: trailing whitespace.
+++   135	
.oracle/checkins/batch-3.md:1492: trailing whitespace.
+++   136	
.oracle/checkins/batch-3.md:1494: trailing whitespace.
+++   149	
.oracle/checkins/batch-3.md:1496: trailing whitespace.
+++   150	
.oracle/checkins/batch-3.md:1498: trailing whitespace.
+++   163	
.oracle/checkins/batch-3.md:1500: trailing whitespace.
+++   164	
.oracle/checkins/batch-3.md:1502: trailing whitespace.
+++   173	
.oracle/checkins/batch-3.md:1504: trailing whitespace.
+++   174	
.oracle/checkins/batch-3.md:1506: trailing whitespace.
+++   180	
.oracle/checkins/batch-3.md:1508: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:1510: trailing whitespace.
+++   191	
.oracle/checkins/batch-3.md:1512: trailing whitespace.
+++   192	
.oracle/checkins/batch-3.md:1514: trailing whitespace.
+++   198	
.oracle/checkins/batch-3.md:1516: trailing whitespace.
+++   199	
.oracle/checkins/batch-3.md:1518: trailing whitespace.
+++   206	
.oracle/checkins/batch-3.md:1520: trailing whitespace.
+++   207	
.oracle/checkins/batch-3.md:1522: trailing whitespace.
+++   223	
.oracle/checkins/batch-3.md:1524: trailing whitespace.
+++   224	
.oracle/checkins/batch-3.md:1526: trailing whitespace.
+++   228	
.oracle/checkins/batch-3.md:1528: trailing whitespace.
+++   229	
.oracle/checkins/batch-3.md:1530: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:1532: trailing whitespace.
+++   233	
.oracle/checkins/batch-3.md:1534: trailing whitespace.
+++   237	
.oracle/checkins/batch-3.md:1536: trailing whitespace.
+++   238	
.oracle/checkins/batch-3.md:1538: trailing whitespace.
+++   242	
.oracle/checkins/batch-3.md:1540: trailing whitespace.
+++   243	
.oracle/checkins/batch-3.md:1542: trailing whitespace.
+++   250	
.oracle/checkins/batch-3.md:1544: trailing whitespace.
+++   251	
.oracle/checkins/batch-3.md:1546: trailing whitespace.
+++   254	
.oracle/checkins/batch-3.md:1548: trailing whitespace.
+++   271	
.oracle/checkins/batch-3.md:1550: trailing whitespace.
+++   275	
.oracle/checkins/batch-3.md:1552: trailing whitespace.
+++   278	
.oracle/checkins/batch-3.md:1554: trailing whitespace.
+++   288	
.oracle/checkins/batch-3.md:1556: trailing whitespace.
+++   307	
.oracle/checkins/batch-3.md:1558: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:1560: trailing whitespace.
+++   324	
.oracle/checkins/batch-3.md:1562: trailing whitespace.
+++   336	
.oracle/checkins/batch-3.md:1564: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:1566: trailing whitespace.
+++     8	
.oracle/checkins/batch-3.md:1568: trailing whitespace.
+++    10	
.oracle/checkins/batch-3.md:1570: trailing whitespace.
+++    21	
.oracle/checkins/batch-3.md:1572: trailing whitespace.
+++    24	
.oracle/checkins/batch-3.md:1574: trailing whitespace.
+++    25	
.oracle/checkins/batch-3.md:1576: trailing whitespace.
+++    28	
.oracle/checkins/batch-3.md:1578: trailing whitespace.
+++    29	
.oracle/checkins/batch-3.md:1580: trailing whitespace.
+++    55	
.oracle/checkins/batch-3.md:1582: trailing whitespace.
+++    56	
.oracle/checkins/batch-3.md:1584: trailing whitespace.
+++    61	
.oracle/checkins/batch-3.md:1586: trailing whitespace.
+++    62	
.oracle/checkins/batch-3.md:1588: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:1590: trailing whitespace.
+++    72	
.oracle/checkins/batch-3.md:1592: trailing whitespace.
+++    79	
.oracle/checkins/batch-3.md:1594: trailing whitespace.
+++    80	
.oracle/checkins/batch-3.md:1596: trailing whitespace.
+++    94	
.oracle/checkins/batch-3.md:1598: trailing whitespace.
+++    95	
.oracle/checkins/batch-3.md:1600: trailing whitespace.
+++   102	
.oracle/checkins/batch-3.md:1602: trailing whitespace.
+++   104	
.oracle/checkins/batch-3.md:1604: trailing whitespace.
+++   111	
.oracle/checkins/batch-3.md:1606: trailing whitespace.
+++   113	
.oracle/checkins/batch-3.md:1608: trailing whitespace.
+++   119	
.oracle/checkins/batch-3.md:1610: trailing whitespace.
+++   128	
.oracle/checkins/batch-3.md:1612: trailing whitespace.
+++   140	
.oracle/checkins/batch-3.md:1614: trailing whitespace.
+++   162	
.oracle/checkins/batch-3.md:1616: trailing whitespace.
+++   171	
.oracle/checkins/batch-3.md:1618: trailing whitespace.
+++   201	
.oracle/checkins/batch-3.md:1620: trailing whitespace.
+++   202	
.oracle/checkins/batch-3.md:1622: trailing whitespace.
+++   214	
.oracle/checkins/batch-3.md:1624: trailing whitespace.
+++   215	
.oracle/checkins/batch-3.md:1626: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:1628: trailing whitespace.
+++   245	
.oracle/checkins/batch-3.md:1630: trailing whitespace.
+++   248	
.oracle/checkins/batch-3.md:1632: trailing whitespace.
+++   266	
.oracle/checkins/batch-3.md:1634: trailing whitespace.
+++   313	
.oracle/checkins/batch-3.md:1636: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:1638: trailing whitespace.
+++   335	
.oracle/checkins/batch-3.md:1640: trailing whitespace.
+++   339	
.oracle/checkins/batch-3.md:1642: trailing whitespace.
+++   360	
.oracle/checkins/batch-3.md:1644: trailing whitespace.
+++   361	
.oracle/checkins/batch-3.md:1646: trailing whitespace.
+++   385	
.oracle/checkins/batch-3.md:1648: trailing whitespace.
+++   386	
.oracle/checkins/batch-3.md:1650: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1652: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1654: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1656: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1658: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1660: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1662: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1664: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1666: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1668: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1670: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1672: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1674: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1676: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1678: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1680: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1682: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1684: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1686: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1688: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1690: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1692: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1694: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1696: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1698: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1700: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1702: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1704: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1706: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1708: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1710: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1712: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1714: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1716: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1718: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:1720: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:1722: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:1724: trailing whitespace.
+++    15	
.oracle/checkins/batch-3.md:1726: trailing whitespace.
+++    31	
.oracle/checkins/batch-3.md:1728: trailing whitespace.
+++    35	
.oracle/checkins/batch-3.md:1730: trailing whitespace.
+++    37	
.oracle/checkins/batch-3.md:1732: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:1734: trailing whitespace.
+++    43	
.oracle/checkins/batch-3.md:1736: trailing whitespace.
+++    45	
.oracle/checkins/batch-3.md:1738: trailing whitespace.
+++    53	
.oracle/checkins/batch-3.md:1740: trailing whitespace.
+++    58	
.oracle/checkins/batch-3.md:1742: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:1744: trailing whitespace.
+++    65	
.oracle/checkins/batch-3.md:1746: trailing whitespace.
+++    66	
.oracle/checkins/batch-3.md:1748: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:1750: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:1752: trailing whitespace.
+++    83	
.oracle/checkins/batch-3.md:1754: trailing whitespace.
+++    84	
.oracle/checkins/batch-3.md:1756: trailing whitespace.
+++    88	
.oracle/checkins/batch-3.md:1758: trailing whitespace.
+++    89	
.oracle/checkins/batch-3.md:1760: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:1762: trailing whitespace.
+++    98	
.oracle/checkins/batch-3.md:1764: trailing whitespace.
+++   110	
.oracle/checkins/batch-3.md:1766: trailing whitespace.
+++   111	
.oracle/checkins/batch-3.md:1768: trailing whitespace.
+++   116	
.oracle/checkins/batch-3.md:1770: trailing whitespace.
+++   117	
.oracle/checkins/batch-3.md:1772: trailing whitespace.
+++   135	
.oracle/checkins/batch-3.md:1774: trailing whitespace.
+++   136	
.oracle/checkins/batch-3.md:1776: trailing whitespace.
+++   149	
.oracle/checkins/batch-3.md:1778: trailing whitespace.
+++   150	
.oracle/checkins/batch-3.md:1780: trailing whitespace.
+++   163	
.oracle/checkins/batch-3.md:1782: trailing whitespace.
+++   164	
.oracle/checkins/batch-3.md:1784: trailing whitespace.
+++   173	
.oracle/checkins/batch-3.md:1786: trailing whitespace.
+++   174	
.oracle/checkins/batch-3.md:1788: trailing whitespace.
+++   180	
.oracle/checkins/batch-3.md:1790: trailing whitespace.
+++   180	
.oracle/checkins/batch-3.md:1792: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:1794: trailing whitespace.
+++   191	
.oracle/checkins/batch-3.md:1796: trailing whitespace.
+++   192	
.oracle/checkins/batch-3.md:1798: trailing whitespace.
+++   198	
.oracle/checkins/batch-3.md:1800: trailing whitespace.
+++   199	
.oracle/checkins/batch-3.md:1802: trailing whitespace.
+++   206	
.oracle/checkins/batch-3.md:1804: trailing whitespace.
+++   207	
.oracle/checkins/batch-3.md:1806: trailing whitespace.
+++   223	
.oracle/checkins/batch-3.md:1808: trailing whitespace.
+++   224	
.oracle/checkins/batch-3.md:1810: trailing whitespace.
+++   228	
.oracle/checkins/batch-3.md:1812: trailing whitespace.
+++   229	
.oracle/checkins/batch-3.md:1814: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:1816: trailing whitespace.
+++   233	
.oracle/checkins/batch-3.md:1818: trailing whitespace.
+++   237	
.oracle/checkins/batch-3.md:1820: trailing whitespace.
+++   238	
.oracle/checkins/batch-3.md:1822: trailing whitespace.
+++   242	
.oracle/checkins/batch-3.md:1824: trailing whitespace.
+++   243	
.oracle/checkins/batch-3.md:1826: trailing whitespace.
+++   250	
.oracle/checkins/batch-3.md:1828: trailing whitespace.
+++   251	
.oracle/checkins/batch-3.md:1830: trailing whitespace.
+++   254	
.oracle/checkins/batch-3.md:1832: trailing whitespace.
+++   271	
.oracle/checkins/batch-3.md:1834: trailing whitespace.
+++   275	
.oracle/checkins/batch-3.md:1836: trailing whitespace.
+++   278	
.oracle/checkins/batch-3.md:1838: trailing whitespace.
+++   288	
.oracle/checkins/batch-3.md:1840: trailing whitespace.
+++   307	
.oracle/checkins/batch-3.md:1842: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:1844: trailing whitespace.
+++   324	
.oracle/checkins/batch-3.md:1846: trailing whitespace.
+++   336	
.oracle/checkins/batch-3.md:1848: trailing whitespace.
+++   347	
.oracle/checkins/batch-3.md:1850: trailing whitespace.
+++   352	
.oracle/checkins/batch-3.md:1852: trailing whitespace.
+++   374	
.oracle/checkins/batch-3.md:1854: trailing whitespace.
+++   388	
.oracle/checkins/batch-3.md:1856: trailing whitespace.
+++   423	
.oracle/checkins/batch-3.md:1858: trailing whitespace.
+++   436	
.oracle/checkins/batch-3.md:1860: trailing whitespace.
+++   462	
.oracle/checkins/batch-3.md:1862: trailing whitespace.
+++   477	
.oracle/checkins/batch-3.md:1864: trailing whitespace.
+++   479	
.oracle/checkins/batch-3.md:1866: trailing whitespace.
+++   480	
.oracle/checkins/batch-3.md:1868: trailing whitespace.
+++   486	
.oracle/checkins/batch-3.md:1870: trailing whitespace.
+++   487	
.oracle/checkins/batch-3.md:1872: trailing whitespace.
+++   491	
.oracle/checkins/batch-3.md:1874: trailing whitespace.
+++   492	
.oracle/checkins/batch-3.md:1876: trailing whitespace.
+++   507	
.oracle/checkins/batch-3.md:1878: trailing whitespace.
+++   508	
.oracle/checkins/batch-3.md:1880: trailing whitespace.
+++   511	
.oracle/checkins/batch-3.md:1882: trailing whitespace.
+++   531	
.oracle/checkins/batch-3.md:1884: trailing whitespace.
+++   532	
.oracle/checkins/batch-3.md:1886: trailing whitespace.
+++   539	
.oracle/checkins/batch-3.md:1888: trailing whitespace.
+++   584	
.oracle/checkins/batch-3.md:1890: trailing whitespace.
+++   601	
.oracle/checkins/batch-3.md:1892: trailing whitespace.
+++   613	
.oracle/checkins/batch-3.md:1894: trailing whitespace.
+++   614	
.oracle/checkins/batch-3.md:1896: trailing whitespace.
+++   627	
.oracle/checkins/batch-3.md:1898: trailing whitespace.
+++   628	
.oracle/checkins/batch-3.md:1900: trailing whitespace.
+++   632	
.oracle/checkins/batch-3.md:1902: trailing whitespace.
+++   633	
.oracle/checkins/batch-3.md:1904: trailing whitespace.
+++   647	
.oracle/checkins/batch-3.md:1906: trailing whitespace.
+++   654	
.oracle/checkins/batch-3.md:1908: trailing whitespace.
+++   655	
.oracle/checkins/batch-3.md:1910: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1912: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1914: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1916: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1918: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1920: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1922: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1924: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1926: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1928: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1930: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1932: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1934: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1936: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1938: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1940: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1942: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1944: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1946: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1948: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1950: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1952: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1954: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1956: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1958: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1960: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1962: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1964: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:1966: trailing whitespace.
+++   174	
.oracle/checkins/batch-3.md:1968: trailing whitespace.
+++   177	
.oracle/checkins/batch-3.md:1970: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:1972: trailing whitespace.
+++   185	
.oracle/checkins/batch-3.md:1974: trailing whitespace.
+++   193	
.oracle/checkins/batch-3.md:1976: trailing whitespace.
+++   196	
.oracle/checkins/batch-3.md:1978: trailing whitespace.
+++   140	
.oracle/checkins/batch-3.md:1980: trailing whitespace.
+++   162	
.oracle/checkins/batch-3.md:1982: trailing whitespace.
+++   171	
.oracle/checkins/batch-3.md:1984: trailing whitespace.
+++   201	
.oracle/checkins/batch-3.md:1986: trailing whitespace.
+++   202	
.oracle/checkins/batch-3.md:1988: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:1990: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:1992: trailing whitespace.
+++    77	
.oracle/checkins/batch-3.md:1994: trailing whitespace.
+++    78	
.oracle/checkins/batch-3.md:1996: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:1998: trailing whitespace.
+++    98	
.oracle/checkins/batch-3.md:2000: trailing whitespace.
+++   104	
.oracle/checkins/batch-3.md:2002: trailing whitespace.
+++   105	
.oracle/checkins/batch-3.md:2004: trailing whitespace.
+++   113	
.oracle/checkins/batch-3.md:2006: trailing whitespace.
+++   114	
.oracle/checkins/batch-3.md:2008: trailing whitespace.
+++   127	
.oracle/checkins/batch-3.md:2010: trailing whitespace.
+++   128	
.oracle/checkins/batch-3.md:2012: trailing whitespace.
+++   142	
.oracle/checkins/batch-3.md:2014: trailing whitespace.
+++   143	
.oracle/checkins/batch-3.md:2016: trailing whitespace.
+++   161	
.oracle/checkins/batch-3.md:2018: trailing whitespace.
+++   173	
.oracle/checkins/batch-3.md:2020: trailing whitespace.
+++   176	
.oracle/checkins/batch-3.md:2022: trailing whitespace.
+++   177	
.oracle/checkins/batch-3.md:2024: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:2026: trailing whitespace.
+++   182	
.oracle/checkins/batch-3.md:2028: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2030: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2032: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2034: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2036: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2038: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2040: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2042: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2044: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2046: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:2048: trailing whitespace.
+++     8	
.oracle/checkins/batch-3.md:2050: trailing whitespace.
+++    10	
.oracle/checkins/batch-3.md:2052: trailing whitespace.
+++    21	
.oracle/checkins/batch-3.md:2054: trailing whitespace.
+++    24	
.oracle/checkins/batch-3.md:2056: trailing whitespace.
+++    25	
.oracle/checkins/batch-3.md:2058: trailing whitespace.
+++    28	
.oracle/checkins/batch-3.md:2060: trailing whitespace.
+++    29	
.oracle/checkins/batch-3.md:2062: trailing whitespace.
+++    55	
.oracle/checkins/batch-3.md:2064: trailing whitespace.
+++    56	
.oracle/checkins/batch-3.md:2066: trailing whitespace.
+++    61	
.oracle/checkins/batch-3.md:2068: trailing whitespace.
+++    62	
.oracle/checkins/batch-3.md:2070: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:2072: trailing whitespace.
+++    72	
.oracle/checkins/batch-3.md:2074: trailing whitespace.
+++    79	
.oracle/checkins/batch-3.md:2076: trailing whitespace.
+++    80	
.oracle/checkins/batch-3.md:2078: trailing whitespace.
+++    94	
.oracle/checkins/batch-3.md:2080: trailing whitespace.
+++    95	
.oracle/checkins/batch-3.md:2082: trailing whitespace.
+++   102	
.oracle/checkins/batch-3.md:2084: trailing whitespace.
+++   104	
.oracle/checkins/batch-3.md:2086: trailing whitespace.
+++   111	
.oracle/checkins/batch-3.md:2088: trailing whitespace.
+++   113	
.oracle/checkins/batch-3.md:2090: trailing whitespace.
+++   119	
.oracle/checkins/batch-3.md:2092: trailing whitespace.
+++   128	
.oracle/checkins/batch-3.md:2094: trailing whitespace.
+++   140	
.oracle/checkins/batch-3.md:2096: trailing whitespace.
+++   162	
.oracle/checkins/batch-3.md:2098: trailing whitespace.
+++   171	
.oracle/checkins/batch-3.md:2100: trailing whitespace.
+++   201	
.oracle/checkins/batch-3.md:2102: trailing whitespace.
+++   202	
.oracle/checkins/batch-3.md:2104: trailing whitespace.
+++   214	
.oracle/checkins/batch-3.md:2106: trailing whitespace.
+++   215	
.oracle/checkins/batch-3.md:2108: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:2110: trailing whitespace.
+++   245	
.oracle/checkins/batch-3.md:2112: trailing whitespace.
+++   248	
.oracle/checkins/batch-3.md:2114: trailing whitespace.
+++   266	
.oracle/checkins/batch-3.md:2116: trailing whitespace.
+++   313	
.oracle/checkins/batch-3.md:2118: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:2120: trailing whitespace.
+++   335	
.oracle/checkins/batch-3.md:2122: trailing whitespace.
+++   339	
.oracle/checkins/batch-3.md:2124: trailing whitespace.
+++   360	
.oracle/checkins/batch-3.md:2126: trailing whitespace.
+++   361	
.oracle/checkins/batch-3.md:2128: trailing whitespace.
+++   385	
.oracle/checkins/batch-3.md:2130: trailing whitespace.
+++   386	
.oracle/checkins/batch-3.md:2132: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:2134: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:2136: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:2138: trailing whitespace.
+++    14	
.oracle/checkins/batch-3.md:2140: trailing whitespace.
+++    21	
.oracle/checkins/batch-3.md:2142: trailing whitespace.
+++    23	
.oracle/checkins/batch-3.md:2144: trailing whitespace.
+++    27	
.oracle/checkins/batch-3.md:2146: trailing whitespace.
+++    28	
.oracle/checkins/batch-3.md:2148: trailing whitespace.
+++    30	
.oracle/checkins/batch-3.md:2150: trailing whitespace.
+++    31	
.oracle/checkins/batch-3.md:2152: trailing whitespace.
+++    35	
.oracle/checkins/batch-3.md:2154: trailing whitespace.
+++    36	
.oracle/checkins/batch-3.md:2156: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:2158: trailing whitespace.
+++    41	
.oracle/checkins/batch-3.md:2160: trailing whitespace.
+++    62	
.oracle/checkins/batch-3.md:2162: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:2164: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:2166: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:2168: trailing whitespace.
+++    77	
.oracle/checkins/batch-3.md:2170: trailing whitespace.
+++    78	
.oracle/checkins/batch-3.md:2172: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:2174: trailing whitespace.
+++    98	
.oracle/checkins/batch-3.md:2176: trailing whitespace.
+++   104	
.oracle/checkins/batch-3.md:2178: trailing whitespace.
+++   105	
.oracle/checkins/batch-3.md:2180: trailing whitespace.
+++   113	
.oracle/checkins/batch-3.md:2182: trailing whitespace.
+++   114	
.oracle/checkins/batch-3.md:2184: trailing whitespace.
+++   127	
.oracle/checkins/batch-3.md:2186: trailing whitespace.
+++   128	
.oracle/checkins/batch-3.md:2188: trailing whitespace.
+++   142	
.oracle/checkins/batch-3.md:2190: trailing whitespace.
+++   143	
.oracle/checkins/batch-3.md:2192: trailing whitespace.
+++   161	
.oracle/checkins/batch-3.md:2194: trailing whitespace.
+++   173	
.oracle/checkins/batch-3.md:2196: trailing whitespace.
+++   176	
.oracle/checkins/batch-3.md:2198: trailing whitespace.
+++   177	
.oracle/checkins/batch-3.md:2200: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:2202: trailing whitespace.
+++   182	
.oracle/checkins/batch-3.md:2204: trailing whitespace.
+++   204	
.oracle/checkins/batch-3.md:2206: trailing whitespace.
+++   205	
.oracle/checkins/batch-3.md:2208: trailing whitespace.
+++   208	
.oracle/checkins/batch-3.md:2210: trailing whitespace.
+++   319	
.oracle/checkins/batch-3.md:2212: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:2214: trailing whitespace.
+++   326	
.oracle/checkins/batch-3.md:2216: trailing whitespace.
+++   334	
.oracle/checkins/batch-3.md:2218: trailing whitespace.
+++   338	
.oracle/checkins/batch-3.md:2220: trailing whitespace.
+++   341	
.oracle/checkins/batch-3.md:2222: trailing whitespace.
+++   344	
.oracle/checkins/batch-3.md:2224: trailing whitespace.
+++   345	
.oracle/checkins/batch-3.md:2226: trailing whitespace.
+++   348	
.oracle/checkins/batch-3.md:2228: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:2230: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:2232: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:2234: trailing whitespace.
+++    15	
.oracle/checkins/batch-3.md:2236: trailing whitespace.
+++    31	
.oracle/checkins/batch-3.md:2238: trailing whitespace.
+++    35	
.oracle/checkins/batch-3.md:2240: trailing whitespace.
+++    37	
.oracle/checkins/batch-3.md:2242: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:2244: trailing whitespace.
+++    43	
.oracle/checkins/batch-3.md:2246: trailing whitespace.
+++    45	
.oracle/checkins/batch-3.md:2248: trailing whitespace.
+++    53	
.oracle/checkins/batch-3.md:2250: trailing whitespace.
+++    58	
.oracle/checkins/batch-3.md:2252: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:2254: trailing whitespace.
+++    65	
.oracle/checkins/batch-3.md:2256: trailing whitespace.
+++    66	
.oracle/checkins/batch-3.md:2258: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:2260: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:2262: trailing whitespace.
+++    83	
.oracle/checkins/batch-3.md:2264: trailing whitespace.
+++    84	
.oracle/checkins/batch-3.md:2266: trailing whitespace.
+++    88	
.oracle/checkins/batch-3.md:2268: trailing whitespace.
+++    89	
.oracle/checkins/batch-3.md:2270: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:2272: trailing whitespace.
+++    98	
.oracle/checkins/batch-3.md:2274: trailing whitespace.
+++   110	
.oracle/checkins/batch-3.md:2276: trailing whitespace.
+++   111	
.oracle/checkins/batch-3.md:2278: trailing whitespace.
+++   116	
.oracle/checkins/batch-3.md:2280: trailing whitespace.
+++   117	
.oracle/checkins/batch-3.md:2282: trailing whitespace.
+++   135	
.oracle/checkins/batch-3.md:2284: trailing whitespace.
+++   136	
.oracle/checkins/batch-3.md:2286: trailing whitespace.
+++   149	
.oracle/checkins/batch-3.md:2288: trailing whitespace.
+++   150	
.oracle/checkins/batch-3.md:2290: trailing whitespace.
+++   163	
.oracle/checkins/batch-3.md:2292: trailing whitespace.
+++   164	
.oracle/checkins/batch-3.md:2294: trailing whitespace.
+++   173	
.oracle/checkins/batch-3.md:2296: trailing whitespace.
+++   174	
.oracle/checkins/batch-3.md:2298: trailing whitespace.
+++   180	
.oracle/checkins/batch-3.md:2300: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:2302: trailing whitespace.
+++   191	
.oracle/checkins/batch-3.md:2304: trailing whitespace.
+++   192	
.oracle/checkins/batch-3.md:2306: trailing whitespace.
+++   198	
.oracle/checkins/batch-3.md:2308: trailing whitespace.
+++   199	
.oracle/checkins/batch-3.md:2310: trailing whitespace.
+++   206	
.oracle/checkins/batch-3.md:2312: trailing whitespace.
+++   207	
.oracle/checkins/batch-3.md:2314: trailing whitespace.
+++   223	
.oracle/checkins/batch-3.md:2316: trailing whitespace.
+++   224	
.oracle/checkins/batch-3.md:2318: trailing whitespace.
+++   228	
.oracle/checkins/batch-3.md:2320: trailing whitespace.
+++   229	
.oracle/checkins/batch-3.md:2322: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:2324: trailing whitespace.
+++   233	
.oracle/checkins/batch-3.md:2326: trailing whitespace.
+++   237	
.oracle/checkins/batch-3.md:2328: trailing whitespace.
+++   238	
.oracle/checkins/batch-3.md:2330: trailing whitespace.
+++   242	
.oracle/checkins/batch-3.md:2332: trailing whitespace.
+++   243	
.oracle/checkins/batch-3.md:2334: trailing whitespace.
+++   250	
.oracle/checkins/batch-3.md:2336: trailing whitespace.
+++   251	
.oracle/checkins/batch-3.md:2338: trailing whitespace.
+++   254	
.oracle/checkins/batch-3.md:2340: trailing whitespace.
+++   271	
.oracle/checkins/batch-3.md:2342: trailing whitespace.
+++   275	
.oracle/checkins/batch-3.md:2344: trailing whitespace.
+++   278	
.oracle/checkins/batch-3.md:2346: trailing whitespace.
+++   288	
.oracle/checkins/batch-3.md:2348: trailing whitespace.
+++   307	
.oracle/checkins/batch-3.md:2350: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:2352: trailing whitespace.
+++   324	
.oracle/checkins/batch-3.md:2354: trailing whitespace.
+++   336	
.oracle/checkins/batch-3.md:2356: trailing whitespace.
+++   347	
.oracle/checkins/batch-3.md:2358: trailing whitespace.
+++   352	
.oracle/checkins/batch-3.md:2360: trailing whitespace.
+++   374	
.oracle/checkins/batch-3.md:2362: trailing whitespace.
+++   388	
.oracle/checkins/batch-3.md:2364: trailing whitespace.
+++   423	
.oracle/checkins/batch-3.md:2366: trailing whitespace.
+++   436	
.oracle/checkins/batch-3.md:2368: trailing whitespace.
+++   462	
.oracle/checkins/batch-3.md:2370: trailing whitespace.
+++   477	
.oracle/checkins/batch-3.md:2372: trailing whitespace.
+++   479	
.oracle/checkins/batch-3.md:2374: trailing whitespace.
+++   480	
.oracle/checkins/batch-3.md:2376: trailing whitespace.
+++   486	
.oracle/checkins/batch-3.md:2378: trailing whitespace.
+++   487	
.oracle/checkins/batch-3.md:2380: trailing whitespace.
+++   491	
.oracle/checkins/batch-3.md:2382: trailing whitespace.
+++   492	
.oracle/checkins/batch-3.md:2384: trailing whitespace.
+++   507	
.oracle/checkins/batch-3.md:2386: trailing whitespace.
+++   508	
.oracle/checkins/batch-3.md:2388: trailing whitespace.
+++   511	
.oracle/checkins/batch-3.md:2390: trailing whitespace.
+++   531	
.oracle/checkins/batch-3.md:2392: trailing whitespace.
+++   532	
.oracle/checkins/batch-3.md:2394: trailing whitespace.
+++   539	
.oracle/checkins/batch-3.md:2396: trailing whitespace.
+++   584	
.oracle/checkins/batch-3.md:2398: trailing whitespace.
+++   601	
.oracle/checkins/batch-3.md:2400: trailing whitespace.
+++   613	
.oracle/checkins/batch-3.md:2402: trailing whitespace.
+++   614	
.oracle/checkins/batch-3.md:2404: trailing whitespace.
+++   627	
.oracle/checkins/batch-3.md:2406: trailing whitespace.
+++   628	
.oracle/checkins/batch-3.md:2408: trailing whitespace.
+++   632	
.oracle/checkins/batch-3.md:2410: trailing whitespace.
+++   633	
.oracle/checkins/batch-3.md:2412: trailing whitespace.
+++   647	
.oracle/checkins/batch-3.md:2414: trailing whitespace.
+++   654	
.oracle/checkins/batch-3.md:2416: trailing whitespace.
+++   655	
.oracle/checkins/batch-3.md:2418: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:2420: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:2422: trailing whitespace.
+++     9	
.oracle/checkins/batch-3.md:2424: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:2426: trailing whitespace.
+++    15	
.oracle/checkins/batch-3.md:2428: trailing whitespace.
+++    20	
.oracle/checkins/batch-3.md:2430: trailing whitespace.
+++    21	
.oracle/checkins/batch-3.md:2432: trailing whitespace.
+++    24	
.oracle/checkins/batch-3.md:2434: trailing whitespace.
+++    25	
.oracle/checkins/batch-3.md:2436: trailing whitespace.
+++    30	
.oracle/checkins/batch-3.md:2438: trailing whitespace.
+++    38	
.oracle/checkins/batch-3.md:2440: trailing whitespace.
+++    43	
.oracle/checkins/batch-3.md:2442: trailing whitespace.
+++    44	
.oracle/checkins/batch-3.md:2444: trailing whitespace.
+++    49	
.oracle/checkins/batch-3.md:2446: trailing whitespace.
+++    50	
.oracle/checkins/batch-3.md:2448: trailing whitespace.
+++    54	
.oracle/checkins/batch-3.md:2450: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:2452: trailing whitespace.
+++    11	
.oracle/checkins/batch-3.md:2454: trailing whitespace.
+++    16	
.oracle/checkins/batch-3.md:2456: trailing whitespace.
+++    18	
.oracle/checkins/batch-3.md:2458: trailing whitespace.
+++    22	
.oracle/checkins/batch-3.md:2460: trailing whitespace.
+++    23	
.oracle/checkins/batch-3.md:2462: trailing whitespace.
+++    36	
.oracle/checkins/batch-3.md:2464: trailing whitespace.
+++    37	
.oracle/checkins/batch-3.md:2466: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:2468: trailing whitespace.
+++    56	
.oracle/checkins/batch-3.md:2470: trailing whitespace.
+++    57	
.oracle/checkins/batch-3.md:2472: trailing whitespace.
+++    60	
.oracle/checkins/batch-3.md:2474: trailing whitespace.
+++    61	
.oracle/checkins/batch-3.md:2476: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:2478: trailing whitespace.
+++    64	
.oracle/checkins/batch-3.md:2480: trailing whitespace.
+++    68	
.oracle/checkins/batch-3.md:2482: trailing whitespace.
+++    69	
.oracle/checkins/batch-3.md:2484: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:2486: trailing whitespace.
+++    72	
.oracle/checkins/batch-3.md:2488: trailing whitespace.
+++    76	
.oracle/checkins/batch-3.md:2490: trailing whitespace.
+++    77	
.oracle/checkins/batch-3.md:2492: trailing whitespace.
+++    79	
.oracle/checkins/batch-3.md:2494: trailing whitespace.
+++    80	
.oracle/checkins/batch-3.md:2496: trailing whitespace.
+++    84	
.oracle/checkins/batch-3.md:2498: trailing whitespace.
+++    85	
.oracle/checkins/batch-3.md:2500: trailing whitespace.
+++   100	
.oracle/checkins/batch-3.md:2502: trailing whitespace.
+++   106	
.oracle/checkins/batch-3.md:2504: trailing whitespace.
+++   107	
.oracle/checkins/batch-3.md:2506: trailing whitespace.
+++   153	
.oracle/checkins/batch-3.md:2508: trailing whitespace.
+++   162	
.oracle/checkins/batch-3.md:2510: trailing whitespace.
+++   213	
.oracle/checkins/batch-3.md:2512: trailing whitespace.
+++   219	
.oracle/checkins/batch-3.md:2514: trailing whitespace.
+++   220	
.oracle/checkins/batch-3.md:2516: trailing whitespace.
+++   222	
.oracle/checkins/batch-3.md:2518: trailing whitespace.
+++   223	
.oracle/checkins/batch-3.md:2520: trailing whitespace.
+++   229	
.oracle/checkins/batch-3.md:2522: trailing whitespace.
+++   230	
.oracle/checkins/batch-3.md:2524: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:2526: trailing whitespace.
+++   233	
.oracle/checkins/batch-3.md:2528: trailing whitespace.
+++   242	
.oracle/checkins/batch-3.md:2530: trailing whitespace.
+++   243	
.oracle/checkins/batch-3.md:2532: trailing whitespace.
+++   245	
.oracle/checkins/batch-3.md:2534: trailing whitespace.
+++   246	
.oracle/checkins/batch-3.md:2536: trailing whitespace.
+++   249	
.oracle/checkins/batch-3.md:2538: trailing whitespace.
+++   256	
.oracle/checkins/batch-3.md:2540: trailing whitespace.
+++   259	
.oracle/checkins/batch-3.md:2542: trailing whitespace.
+++   264	
.oracle/checkins/batch-3.md:2544: trailing whitespace.
+++   265	
.oracle/checkins/batch-3.md:2546: trailing whitespace.
+++   269	
.oracle/checkins/batch-3.md:2548: trailing whitespace.
+++   270	
.oracle/checkins/batch-3.md:2550: trailing whitespace.
+++   274	
.oracle/checkins/batch-3.md:2552: trailing whitespace.
+++   278	
.oracle/checkins/batch-3.md:2554: trailing whitespace.
+++   279	
.oracle/checkins/batch-3.md:2556: trailing whitespace.
+++   285	
.oracle/checkins/batch-3.md:2558: trailing whitespace.
+++   292	
.oracle/checkins/batch-3.md:2560: trailing whitespace.
+++   293	
.oracle/checkins/batch-3.md:2562: trailing whitespace.
+++   297	
.oracle/checkins/batch-3.md:2564: trailing whitespace.
+++   303	
.oracle/checkins/batch-3.md:2566: trailing whitespace.
+++   309	
.oracle/checkins/batch-3.md:2568: trailing whitespace.
+++   310	
.oracle/checkins/batch-3.md:2570: trailing whitespace.
+++   316	
.oracle/checkins/batch-3.md:2572: trailing whitespace.
+++   329	
.oracle/checkins/batch-3.md:2574: trailing whitespace.
+++   330	
.oracle/checkins/batch-3.md:2576: trailing whitespace.
+++   335	
.oracle/checkins/batch-3.md:2578: trailing whitespace.
+++   341	
.oracle/checkins/batch-3.md:2580: trailing whitespace.
+++   342	
.oracle/checkins/batch-3.md:2582: trailing whitespace.
+++   344	
.oracle/checkins/batch-3.md:2584: trailing whitespace.
+++   345	
.oracle/checkins/batch-3.md:2586: trailing whitespace.
+++   352	
.oracle/checkins/batch-3.md:2588: trailing whitespace.
+++   353	
.oracle/checkins/batch-3.md:2590: trailing whitespace.
+++   356	
.oracle/checkins/batch-3.md:2592: trailing whitespace.
+++   357	
.oracle/checkins/batch-3.md:2594: trailing whitespace.
+++   380	
.oracle/checkins/batch-3.md:2596: trailing whitespace.
+++   381	
.oracle/checkins/batch-3.md:2598: trailing whitespace.
+++   391	
.oracle/checkins/batch-3.md:2600: trailing whitespace.
+++   392	
.oracle/checkins/batch-3.md:2602: trailing whitespace.
+++   400	
.oracle/checkins/batch-3.md:2604: trailing whitespace.
+++   401	
.oracle/checkins/batch-3.md:2606: trailing whitespace.
+++   407	
.oracle/checkins/batch-3.md:2608: trailing whitespace.
+++   408	
.oracle/checkins/batch-3.md:2610: trailing whitespace.
+++   417	
.oracle/checkins/batch-3.md:2612: trailing whitespace.
+++   418	
.oracle/checkins/batch-3.md:2614: trailing whitespace.
+++   421	
.oracle/checkins/batch-3.md:2616: trailing whitespace.
+++   428	
.oracle/checkins/batch-3.md:2618: trailing whitespace.
+++   432	
.oracle/checkins/batch-3.md:2620: trailing whitespace.
+++   434	
.oracle/checkins/batch-3.md:2622: trailing whitespace.
+++   440	
.oracle/checkins/batch-3.md:2624: trailing whitespace.
+++   441	
.oracle/checkins/batch-3.md:2626: trailing whitespace.
+++   445	
.oracle/checkins/batch-3.md:2628: trailing whitespace.
+++   451	
.oracle/checkins/batch-3.md:2630: trailing whitespace.
+++   452	
.oracle/checkins/batch-3.md:2632: trailing whitespace.
+++   455	
.oracle/checkins/batch-3.md:2634: trailing whitespace.
+++   463	
.oracle/checkins/batch-3.md:2636: trailing whitespace.
+++   468	
.oracle/checkins/batch-3.md:2638: trailing whitespace.
+++   471	
.oracle/checkins/batch-3.md:2640: trailing whitespace.
+++   472	
.oracle/checkins/batch-3.md:2642: trailing whitespace.
+++   475	
.oracle/checkins/batch-3.md:2644: trailing whitespace.
+++   481	
.oracle/checkins/batch-3.md:2646: trailing whitespace.
+++   488	
.oracle/checkins/batch-3.md:2648: trailing whitespace.
+++   494	
.oracle/checkins/batch-3.md:2650: trailing whitespace.
+++   495	
.oracle/checkins/batch-3.md:2652: trailing whitespace.
+++   498	
.oracle/checkins/batch-3.md:2654: trailing whitespace.
+++   506	
.oracle/checkins/batch-3.md:2656: trailing whitespace.
+++   517	
.oracle/checkins/batch-3.md:2658: trailing whitespace.
+++   532	
.oracle/checkins/batch-3.md:2660: trailing whitespace.
+++   533	
.oracle/checkins/batch-3.md:2662: trailing whitespace.
+++   536	
.oracle/checkins/batch-3.md:2664: trailing whitespace.
+++   543	
.oracle/checkins/batch-3.md:2666: trailing whitespace.
+++   547	
.oracle/checkins/batch-3.md:2668: trailing whitespace.
+++   554	
.oracle/checkins/batch-3.md:2670: trailing whitespace.
+++   557	
.oracle/checkins/batch-3.md:2672: trailing whitespace.
+++   558	
.oracle/checkins/batch-3.md:2674: trailing whitespace.
+++   562	
.oracle/checkins/batch-3.md:2676: trailing whitespace.
+++   565	
.oracle/checkins/batch-3.md:2678: trailing whitespace.
+++   576	
.oracle/checkins/batch-3.md:2680: trailing whitespace.
+++   584	
.oracle/checkins/batch-3.md:2682: trailing whitespace.
+++   587	
.oracle/checkins/batch-3.md:2684: trailing whitespace.
+++   588	
.oracle/checkins/batch-3.md:2686: trailing whitespace.
+++   592	
.oracle/checkins/batch-3.md:2688: trailing whitespace.
+++   595	
.oracle/checkins/batch-3.md:2690: trailing whitespace.
+++   606	
.oracle/checkins/batch-3.md:2692: trailing whitespace.
+++   615	
.oracle/checkins/batch-3.md:2694: trailing whitespace.
+++   619	
.oracle/checkins/batch-3.md:2696: trailing whitespace.
+++   620	
.oracle/checkins/batch-3.md:2698: trailing whitespace.
+++   624	
.oracle/checkins/batch-3.md:2700: trailing whitespace.
+++   629	
.oracle/checkins/batch-3.md:2702: trailing whitespace.
+++   630	
.oracle/checkins/batch-3.md:2704: trailing whitespace.
+++   633	
.oracle/checkins/batch-3.md:2706: trailing whitespace.
+++   634	
.oracle/checkins/batch-3.md:2708: trailing whitespace.
+++   655	
.oracle/checkins/batch-3.md:2710: trailing whitespace.
+++   656	
.oracle/checkins/batch-3.md:2712: trailing whitespace.
+++   661	
.oracle/checkins/batch-3.md:2714: trailing whitespace.
+++   663	
.oracle/checkins/batch-3.md:2716: trailing whitespace.
+++   672	
.oracle/checkins/batch-3.md:2718: trailing whitespace.
+++   676	
.oracle/checkins/batch-3.md:2720: trailing whitespace.
+++   679	
.oracle/checkins/batch-3.md:2722: trailing whitespace.
+++   682	
.oracle/checkins/batch-3.md:2724: trailing whitespace.
+++   694	
.oracle/checkins/batch-3.md:2726: trailing whitespace.
+++   706	
.oracle/checkins/batch-3.md:2728: trailing whitespace.
+++   707	
.oracle/checkins/batch-3.md:2730: trailing whitespace.
+++   711	
.oracle/checkins/batch-3.md:2732: trailing whitespace.
+++   714	
.oracle/checkins/batch-3.md:2734: trailing whitespace.
+++   720	
.oracle/checkins/batch-3.md:2736: trailing whitespace.
+++   721	
.oracle/checkins/batch-3.md:2738: trailing whitespace.
+++   724	
.oracle/checkins/batch-3.md:2740: trailing whitespace.
+++   731	
.oracle/checkins/batch-3.md:2742: trailing whitespace.
+++   733	
.oracle/checkins/batch-3.md:2744: trailing whitespace.
+++   738	
.oracle/checkins/batch-3.md:2746: trailing whitespace.
+++   744	
.oracle/checkins/batch-3.md:2748: trailing whitespace.
+++   745	
.oracle/checkins/batch-3.md:2750: trailing whitespace.
+++   749	
.oracle/checkins/batch-3.md:2752: trailing whitespace.
+++   752	
.oracle/checkins/batch-3.md:2754: trailing whitespace.
+++   758	
.oracle/checkins/batch-3.md:2756: trailing whitespace.
+++   760	
.oracle/checkins/batch-3.md:2758: trailing whitespace.
+++   762	
.oracle/checkins/batch-3.md:2760: trailing whitespace.
+++   763	
.oracle/checkins/batch-3.md:2762: trailing whitespace.
+++   767	
.oracle/checkins/batch-3.md:2764: trailing whitespace.
+++   772	
.oracle/checkins/batch-3.md:2766: trailing whitespace.
+++   777	
.oracle/checkins/batch-3.md:2768: trailing whitespace.
+++   782	
.oracle/checkins/batch-3.md:2770: trailing whitespace.
+++   787	
.oracle/checkins/batch-3.md:2772: trailing whitespace.
+++   792	
.oracle/checkins/batch-3.md:2774: trailing whitespace.
+++   793	
.oracle/checkins/batch-3.md:2776: trailing whitespace.
+++   797	
.oracle/checkins/batch-3.md:2778: trailing whitespace.
+++   804	
.oracle/checkins/batch-3.md:2780: trailing whitespace.
+++   811	
.oracle/checkins/batch-3.md:2782: trailing whitespace.
+++   818	
.oracle/checkins/batch-3.md:2784: trailing whitespace.
+++   819	
.oracle/checkins/batch-3.md:2786: trailing whitespace.
+++   823	
.oracle/checkins/batch-3.md:2788: trailing whitespace.
+++   829	
.oracle/checkins/batch-3.md:2790: trailing whitespace.
+++   834	
.oracle/checkins/batch-3.md:2792: trailing whitespace.
+++   839	
.oracle/checkins/batch-3.md:2794: trailing whitespace.
+++   840	
.oracle/checkins/batch-3.md:2796: trailing whitespace.
+++   844	
.oracle/checkins/batch-3.md:2798: trailing whitespace.
+++   845	
.oracle/checkins/batch-3.md:2800: trailing whitespace.
+++   849	
.oracle/checkins/batch-3.md:2802: trailing whitespace.
+++   861	
.oracle/checkins/batch-3.md:2804: trailing whitespace.
+++   867	
.oracle/checkins/batch-3.md:2806: trailing whitespace.
+++   881	
.oracle/checkins/batch-3.md:2808: trailing whitespace.
+++   882	
.oracle/checkins/batch-3.md:2810: trailing whitespace.
+++   886	
.oracle/checkins/batch-3.md:2812: trailing whitespace.
+++   932	
.oracle/checkins/batch-3.md:2814: trailing whitespace.
+++   948	
.oracle/checkins/batch-3.md:2816: trailing whitespace.
+++   949	
.oracle/checkins/batch-3.md:2818: trailing whitespace.
+++   953	
.oracle/checkins/batch-3.md:2820: trailing whitespace.
+++   973	
.oracle/checkins/batch-3.md:2822: trailing whitespace.
+++   985	
.oracle/checkins/batch-3.md:2824: trailing whitespace.
+++   990	
.oracle/checkins/batch-3.md:2826: trailing whitespace.
+++   995	
.oracle/checkins/batch-3.md:2828: trailing whitespace.
+++  1000	
.oracle/checkins/batch-3.md:2830: trailing whitespace.
+++  1004	
.oracle/checkins/batch-3.md:2832: trailing whitespace.
+++  1005	
.oracle/checkins/batch-3.md:2834: trailing whitespace.
+++  1009	
.oracle/checkins/batch-3.md:2836: trailing whitespace.
+++  1010	
.oracle/checkins/batch-3.md:2838: trailing whitespace.
+++  1015	
.oracle/checkins/batch-3.md:2840: trailing whitespace.
+++  1028	
.oracle/checkins/batch-3.md:2842: trailing whitespace.
+++  1029	
.oracle/checkins/batch-3.md:2844: trailing whitespace.
+++  1042	
.oracle/checkins/batch-3.md:2846: trailing whitespace.
+++  1043	
.oracle/checkins/batch-3.md:2848: trailing whitespace.
+++  1051	
.oracle/checkins/batch-3.md:2850: trailing whitespace.
+++  1052	
.oracle/checkins/batch-3.md:2852: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:2854: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:2856: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:2858: trailing whitespace.
+++    15	
.oracle/checkins/batch-3.md:2860: trailing whitespace.
+++    31	
.oracle/checkins/batch-3.md:2862: trailing whitespace.
+++    35	
.oracle/checkins/batch-3.md:2864: trailing whitespace.
+++    37	
.oracle/checkins/batch-3.md:2866: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:2868: trailing whitespace.
+++    43	
.oracle/checkins/batch-3.md:2870: trailing whitespace.
+++    45	
.oracle/checkins/batch-3.md:2872: trailing whitespace.
+++    53	
.oracle/checkins/batch-3.md:2874: trailing whitespace.
+++    58	
.oracle/checkins/batch-3.md:2876: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:2878: trailing whitespace.
+++    65	
.oracle/checkins/batch-3.md:2880: trailing whitespace.
+++    66	
.oracle/checkins/batch-3.md:2882: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:2884: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:2886: trailing whitespace.
+++    83	
.oracle/checkins/batch-3.md:2888: trailing whitespace.
+++    84	
.oracle/checkins/batch-3.md:2890: trailing whitespace.
+++    88	
.oracle/checkins/batch-3.md:2892: trailing whitespace.
+++    89	
.oracle/checkins/batch-3.md:2894: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:2896: trailing whitespace.
+++    98	
.oracle/checkins/batch-3.md:2898: trailing whitespace.
+++   110	
.oracle/checkins/batch-3.md:2900: trailing whitespace.
+++   111	
.oracle/checkins/batch-3.md:2902: trailing whitespace.
+++   116	
.oracle/checkins/batch-3.md:2904: trailing whitespace.
+++   117	
.oracle/checkins/batch-3.md:2906: trailing whitespace.
+++   135	
.oracle/checkins/batch-3.md:2908: trailing whitespace.
+++   136	
.oracle/checkins/batch-3.md:2910: trailing whitespace.
+++   149	
.oracle/checkins/batch-3.md:2912: trailing whitespace.
+++   150	
.oracle/checkins/batch-3.md:2914: trailing whitespace.
+++   163	
.oracle/checkins/batch-3.md:2916: trailing whitespace.
+++   164	
.oracle/checkins/batch-3.md:2918: trailing whitespace.
+++   173	
.oracle/checkins/batch-3.md:2920: trailing whitespace.
+++   174	
.oracle/checkins/batch-3.md:2922: trailing whitespace.
+++   180	
.oracle/checkins/batch-3.md:2924: trailing whitespace.
+++   181	
.oracle/checkins/batch-3.md:2926: trailing whitespace.
+++   191	
.oracle/checkins/batch-3.md:2928: trailing whitespace.
+++   192	
.oracle/checkins/batch-3.md:2930: trailing whitespace.
+++   198	
.oracle/checkins/batch-3.md:2932: trailing whitespace.
+++   199	
.oracle/checkins/batch-3.md:2934: trailing whitespace.
+++   206	
.oracle/checkins/batch-3.md:2936: trailing whitespace.
+++   207	
.oracle/checkins/batch-3.md:2938: trailing whitespace.
+++   223	
.oracle/checkins/batch-3.md:2940: trailing whitespace.
+++   224	
.oracle/checkins/batch-3.md:2942: trailing whitespace.
+++   228	
.oracle/checkins/batch-3.md:2944: trailing whitespace.
+++   229	
.oracle/checkins/batch-3.md:2946: trailing whitespace.
+++   232	
.oracle/checkins/batch-3.md:2948: trailing whitespace.
+++   233	
.oracle/checkins/batch-3.md:2950: trailing whitespace.
+++   237	
.oracle/checkins/batch-3.md:2952: trailing whitespace.
+++   238	
.oracle/checkins/batch-3.md:2954: trailing whitespace.
+++   531	
.oracle/checkins/batch-3.md:2956: trailing whitespace.
+++   532	
.oracle/checkins/batch-3.md:2958: trailing whitespace.
+++   539	
.oracle/checkins/batch-3.md:2960: trailing whitespace.
+++   584	
.oracle/checkins/batch-3.md:2962: trailing whitespace.
+++   601	
.oracle/checkins/batch-3.md:2964: trailing whitespace.
+++   613	
.oracle/checkins/batch-3.md:2966: trailing whitespace.
+++   614	
.oracle/checkins/batch-3.md:2968: trailing whitespace.
+++   627	
.oracle/checkins/batch-3.md:2970: trailing whitespace.
+++   628	
.oracle/checkins/batch-3.md:2972: trailing whitespace.
+++   632	
.oracle/checkins/batch-3.md:2974: trailing whitespace.
+++   633	
.oracle/checkins/batch-3.md:2976: trailing whitespace.
+++   647	
.oracle/checkins/batch-3.md:2978: trailing whitespace.
+++   654	
.oracle/checkins/batch-3.md:2980: trailing whitespace.
+++   655	
.oracle/checkins/batch-3.md:2982: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2984: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2986: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2988: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2990: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2992: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2994: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2996: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:2998: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3000: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3002: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3004: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3006: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3008: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3010: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3012: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3014: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3016: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3018: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3020: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3022: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3024: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3026: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3028: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3030: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3032: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3034: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3036: trailing whitespace.
+++   242	
.oracle/checkins/batch-3.md:3038: trailing whitespace.
+++   243	
.oracle/checkins/batch-3.md:3040: trailing whitespace.
+++   250	
.oracle/checkins/batch-3.md:3042: trailing whitespace.
+++   251	
.oracle/checkins/batch-3.md:3044: trailing whitespace.
+++   254	
.oracle/checkins/batch-3.md:3046: trailing whitespace.
+++   271	
.oracle/checkins/batch-3.md:3048: trailing whitespace.
+++   275	
.oracle/checkins/batch-3.md:3050: trailing whitespace.
+++   278	
.oracle/checkins/batch-3.md:3052: trailing whitespace.
+++   288	
.oracle/checkins/batch-3.md:3054: trailing whitespace.
+++   307	
.oracle/checkins/batch-3.md:3056: trailing whitespace.
+++   320	
.oracle/checkins/batch-3.md:3058: trailing whitespace.
+++   324	
.oracle/checkins/batch-3.md:3060: trailing whitespace.
+++   336	
.oracle/checkins/batch-3.md:3062: trailing whitespace.
+++   347	
.oracle/checkins/batch-3.md:3064: trailing whitespace.
+++   352	
.oracle/checkins/batch-3.md:3066: trailing whitespace.
+++   374	
.oracle/checkins/batch-3.md:3068: trailing whitespace.
+++   388	
.oracle/checkins/batch-3.md:3070: trailing whitespace.
+++   423	
.oracle/checkins/batch-3.md:3072: trailing whitespace.
+++   436	
.oracle/checkins/batch-3.md:3074: trailing whitespace.
+++   462	
.oracle/checkins/batch-3.md:3076: trailing whitespace.
+++   477	
.oracle/checkins/batch-3.md:3078: trailing whitespace.
+++   479	
.oracle/checkins/batch-3.md:3080: trailing whitespace.
+++   480	
.oracle/checkins/batch-3.md:3082: trailing whitespace.
+++   486	
.oracle/checkins/batch-3.md:3084: trailing whitespace.
+++   487	
.oracle/checkins/batch-3.md:3086: trailing whitespace.
+++   491	
.oracle/checkins/batch-3.md:3088: trailing whitespace.
+++   492	
.oracle/checkins/batch-3.md:3090: trailing whitespace.
+++   507	
.oracle/checkins/batch-3.md:3092: trailing whitespace.
+++   508	
.oracle/checkins/batch-3.md:3094: trailing whitespace.
+++   511	
.oracle/checkins/batch-3.md:3096: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3098: trailing whitespace.
+++ 
.oracle/checkins/batch-3.md:3100: trailing whitespace.
+++   280	
.oracle/checkins/batch-3.md:3102: trailing whitespace.
+++   283	
.oracle/checkins/batch-3.md:3104: trailing whitespace.
+++   300	
.oracle/checkins/batch-3.md:3106: trailing whitespace.
+++   311	
.oracle/checkins/batch-3.md:3108: trailing whitespace.
+++   317	
.oracle/checkins/batch-3.md:3110: trailing whitespace.
+++   326	
.oracle/checkins/batch-3.md:3112: trailing whitespace.
+++   365	
.oracle/checkins/batch-3.md:3114: trailing whitespace.
+++   370	
.oracle/checkins/batch-3.md:3116: trailing whitespace.
+++   392	
.oracle/checkins/batch-3.md:3118: trailing whitespace.
+++   404	
.oracle/checkins/batch-3.md:3120: trailing whitespace.
+++   423	
.oracle/checkins/batch-3.md:3122: trailing whitespace.
+++   451	
.oracle/checkins/batch-3.md:3124: trailing whitespace.
+++   465	
.oracle/checkins/batch-3.md:3126: trailing whitespace.
+++   469	
.oracle/checkins/batch-3.md:3128: trailing whitespace.
+++   472	
.oracle/checkins/batch-3.md:3130: trailing whitespace.
+++   481	
.oracle/checkins/batch-3.md:3132: trailing whitespace.
+++   492	
.oracle/checkins/batch-3.md:3134: trailing whitespace.
+++   496	
.oracle/checkins/batch-3.md:3136: trailing whitespace.
+++   241	
.oracle/checkins/batch-3.md:3138: trailing whitespace.
+++   252	
.oracle/checkins/batch-3.md:3140: trailing whitespace.
+++   255	
.oracle/checkins/batch-3.md:3142: trailing whitespace.
+++   264	
.oracle/checkins/batch-3.md:3144: trailing whitespace.
+++   268	
.oracle/checkins/batch-3.md:3146: trailing whitespace.
+++   275	
.oracle/checkins/batch-3.md:3148: trailing whitespace.
+++   277	
.oracle/checkins/batch-3.md:3150: trailing whitespace.
+++   280	
.oracle/checkins/batch-3.md:3152: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:3154: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:3156: trailing whitespace.
+++    79	
.oracle/checkins/batch-3.md:3158: trailing whitespace.
+++    80	
.oracle/checkins/batch-3.md:3160: trailing whitespace.
+++    92	
.oracle/checkins/batch-3.md:3162: trailing whitespace.
+++    97	
.oracle/checkins/batch-3.md:3164: trailing whitespace.
+++    99	
.oracle/checkins/batch-3.md:3166: trailing whitespace.
+++   100	
.oracle/checkins/batch-3.md:3168: trailing whitespace.
+++   107	
.oracle/checkins/batch-3.md:3170: trailing whitespace.
+++   108	
.oracle/checkins/batch-3.md:3172: trailing whitespace.
+++     2	
.oracle/checkins/batch-3.md:3174: trailing whitespace.
+++     7	
.oracle/checkins/batch-3.md:3176: trailing whitespace.
+++    12	
.oracle/checkins/batch-3.md:3178: trailing whitespace.
+++    15	
.oracle/checkins/batch-3.md:3180: trailing whitespace.
+++    31	
.oracle/checkins/batch-3.md:3182: trailing whitespace.
+++    35	
.oracle/checkins/batch-3.md:3184: trailing whitespace.
+++    37	
.oracle/checkins/batch-3.md:3186: trailing whitespace.
+++    40	
.oracle/checkins/batch-3.md:3188: trailing whitespace.
+++    43	
.oracle/checkins/batch-3.md:3190: trailing whitespace.
+++    45	
.oracle/checkins/batch-3.md:3192: trailing whitespace.
+++    53	
.oracle/checkins/batch-3.md:3194: trailing whitespace.
+++    58	
.oracle/checkins/batch-3.md:3196: trailing whitespace.
+++    63	
.oracle/checkins/batch-3.md:3198: trailing whitespace.
+++    65	
.oracle/checkins/batch-3.md:3200: trailing whitespace.
+++    66	
.oracle/checkins/batch-3.md:3202: trailing whitespace.
+++    70	
.oracle/checkins/batch-3.md:3204: trailing whitespace.
+++    71	
.oracle/checkins/batch-3.md:3206: trailing whitespace.
+++    83	
.oracle/checkins/batch-3.md:3208: trailing whitespace.
+++    84	
.oracle/checkins/batch-3.md:3210: trailing whitespace.
++    80	
.oracle/checkins/batch-3.md:3212: trailing whitespace.
++    92	
.oracle/checkins/batch-3.md:3214: trailing whitespace.
++    97	
.oracle/checkins/batch-3.md:3216: trailing whitespace.
++    99	
.oracle/checkins/batch-3.md:3218: trailing whitespace.
++   100	
.oracle/checkins/batch-3.md:3220: trailing whitespace.
++   107	
.oracle/checkins/batch-3.md:3222: trailing whitespace.
++   108	
.oracle/checkins/batch-3.md:3224: trailing whitespace.
++   121	
.oracle/checkins/batch-3.md:3226: trailing whitespace.
++   125	
.oracle/checkins/batch-3.md:3228: trailing whitespace.
++   129	
.oracle/checkins/batch-3.md:3230: trailing whitespace.
++   130	
.oracle/checkins/batch-3.md:3232: trailing whitespace.
++   140	
.oracle/checkins/batch-3.md:3234: trailing whitespace.
++   141	
.oracle/checkins/batch-3.md:3236: trailing whitespace.
++   148	
.oracle/checkins/batch-3.md:3238: trailing whitespace.
++   149	
.oracle/checkins/batch-3.md:3240: trailing whitespace.
++   154	
.oracle/checkins/batch-3.md:3242: trailing whitespace.
++   155	
.oracle/checkins/batch-3.md:3244: trailing whitespace.
++   158	
.oracle/checkins/batch-3.md:3246: trailing whitespace.
++   170	
.oracle/checkins/batch-3.md:3248: trailing whitespace.
++   171	
.oracle/checkins/batch-3.md:3250: trailing whitespace.
++   275	
.oracle/checkins/batch-3.md:3252: trailing whitespace.
++   277	
.oracle/checkins/batch-3.md:3254: trailing whitespace.
++   280	
.oracle/checkins/batch-3.md:3256: trailing whitespace.
++   283	
.oracle/checkins/batch-3.md:3258: trailing whitespace.
++   300	
.oracle/checkins/batch-3.md:3260: trailing whitespace.
++   311	
.oracle/checkins/batch-3.md:3262: trailing whitespace.
++   317	
.oracle/checkins/batch-3.md:3264: trailing whitespace.
++   326	
.oracle/checkins/batch-3.md:3266: trailing whitespace.
++   365	
.oracle/checkins/batch-3.md:3268: trailing whitespace.
++   370	
.oracle/checkins/batch-3.md:3270: trailing whitespace.
++   392	
.oracle/checkins/batch-3.md:3272: trailing whitespace.
++   404	
.oracle/checkins/batch-3.md:3274: trailing whitespace.
++   423	
.oracle/checkins/batch-3.md:3276: trailing whitespace.
++   451	
.oracle/checkins/batch-3.md:3278: trailing whitespace.
++   465	
.oracle/checkins/batch-3.md:3280: trailing whitespace.
++   469	
.oracle/checkins/batch-3.md:3282: trailing whitespace.
++   472	
.oracle/checkins/batch-3.md:3284: trailing whitespace.
++   481	
.oracle/checkins/batch-3.md:3286: trailing whitespace.
++   492	
.oracle/checkins/batch-3.md:3288: trailing whitespace.
++   496	
.oracle/checkins/batch-3.md:3290: trailing whitespace.
++   513	
.oracle/checkins/batch-3.md:3292: trailing whitespace.
++   515	
.oracle/checkins/batch-3.md:3294: trailing whitespace.
++   538	
.oracle/checkins/batch-3.md:3296: trailing whitespace.
++   550	
.oracle/checkins/batch-3.md:3298: trailing whitespace.
++   556	
.oracle/checkins/batch-3.md:3300: trailing whitespace.
++   568	
.oracle/checkins/batch-3.md:3302: trailing whitespace.
++   584	
.oracle/checkins/batch-3.md:3304: trailing whitespace.
++   596	
.oracle/checkins/batch-3.md:3306: trailing whitespace.
++   604	
.oracle/checkins/batch-3.md:3308: trailing whitespace.
++   620	
.oracle/checkins/batch-3.md:3310: trailing whitespace.
++   631	
.oracle/checkins/batch-3.md:3312: trailing whitespace.
++   634	
.oracle/checkins/batch-3.md:3314: trailing whitespace.
++   733	
.oracle/checkins/batch-3.md:3316: trailing whitespace.
++   759	
.oracle/checkins/batch-3.md:3318: trailing whitespace.
++   764	
.oracle/checkins/batch-3.md:3320: trailing whitespace.
++   768	
.oracle/checkins/batch-3.md:3322: trailing whitespace.
++   784	
.oracle/checkins/batch-3.md:3324: trailing whitespace.
++   787	
.oracle/checkins/batch-3.md:3326: trailing whitespace.
++   794	
.oracle/checkins/batch-3.md:3328: trailing whitespace.
++   796	
.oracle/checkins/batch-3.md:3330: trailing whitespace.
++   803	
.oracle/checkins/batch-3.md:3332: trailing whitespace.
++   813	
.oracle/checkins/batch-3.md:3334: trailing whitespace.
++   820	
.oracle/checkins/batch-3.md:3336: trailing whitespace.
++   823	
.oracle/checkins/batch-3.md:3338: trailing whitespace.
++   826	
.oracle/checkins/batch-3.md:3340: trailing whitespace.
++   840	
.oracle/checkins/batch-3.md:3342: trailing whitespace.
++   847	
.oracle/checkins/batch-3.md:3344: trailing whitespace.
++   857	
.oracle/checkins/batch-3.md:3346: trailing whitespace.
++   995	
.oracle/checkins/batch-3.md:3348: trailing whitespace.
++   996	
.oracle/checkins/batch-3.md:3350: trailing whitespace.
++  1007	
.oracle/checkins/batch-3.md:3352: trailing whitespace.
++  1008	
.oracle/checkins/batch-3.md:3354: trailing whitespace.
++  1019	
.oracle/checkins/batch-3.md:3356: trailing whitespace.
++  1020	
.oracle/checkins/batch-3.md:3358: trailing whitespace.
++  1027	
.oracle/checkins/batch-3.md:3360: trailing whitespace.
++  1031	
.oracle/checkins/batch-3.md:3362: trailing whitespace.
++  1032	
.oracle/checkins/batch-3.md:3364: trailing whitespace.
++  1043	
.oracle/checkins/batch-3.md:3366: trailing whitespace.
++  1044	
.oracle/checkins/batch-3.md:3368: trailing whitespace.
++  1049	
.oracle/checkins/batch-3.md:3370: trailing whitespace.
++  1050	
.oracle/checkins/batch-3.md:3372: trailing whitespace.
++  1054	
.oracle/checkins/batch-3.md:3374: trailing whitespace.
++  1055	
.oracle/checkins/batch-3.md:3376: trailing whitespace.
++  1066	
.oracle/checkins/batch-3.md:3378: trailing whitespace.
++  1067	
.oracle/checkins/batch-3.md:3380: trailing whitespace.
++  1070	
.oracle/checkins/batch-3.md:3382: trailing whitespace.
++  1071	
.oracle/checkins/batch-3.md:3384: trailing whitespace.
++  1078	
.oracle/checkins/batch-3.md:3386: trailing whitespace.
++  1079	
.oracle/checkins/batch-3.md:3388: trailing whitespace.
++  1083	
.oracle/checkins/batch-3.md:3390: trailing whitespace.
++  1087	
.oracle/checkins/batch-3.md:3392: trailing whitespace.
++  1088	
.oracle/checkins/batch-3.md:3394: trailing whitespace.
++  1107	
.oracle/checkins/batch-3.md:3396: trailing whitespace.
++  1108	
.oracle/checkins/batch-3.md:3398: trailing whitespace.
++  1150	
.oracle/checkins/batch-3.md:3400: trailing whitespace.
++  1151	
.oracle/checkins/batch-3.md:3402: trailing whitespace.
++  1154	
.oracle/checkins/batch-3.md:3404: trailing whitespace.
++  1155	
.oracle/checkins/batch-3.md:3406: trailing whitespace.
++  1158	
.oracle/checkins/batch-3.md:3408: trailing whitespace.
++  1172	
.oracle/checkins/batch-3.md:3410: trailing whitespace.
++  1173	
.oracle/checkins/batch-3.md:3412: trailing whitespace.
++  1178	
.oracle/checkins/batch-3.md:3414: trailing whitespace.
++  1191	
.oracle/checkins/batch-3.md:3416: trailing whitespace.
++  1192	
.oracle/checkins/batch-3.md:3418: trailing whitespace.
++  1199	
.oracle/checkins/batch-3.md:3420: trailing whitespace.
++  1206	
.oracle/checkins/batch-3.md:3422: trailing whitespace.
++  1211	
.oracle/checkins/batch-3.md:3424: trailing whitespace.
++  1215	
.oracle/checkins/batch-3.md:3426: trailing whitespace.
++  1232	
.oracle/checkins/batch-3.md:3428: trailing whitespace.
++  1250	
.oracle/checkins/batch-3.md:3430: trailing whitespace.
++  1251	
.oracle/checkins/batch-3.md:3432: trailing whitespace.
++  1261	
.oracle/checkins/batch-3.md:3434: trailing whitespace.
++  1262	
.oracle/checkins/batch-3.md:3436: trailing whitespace.
++  1753	
.oracle/checkins/batch-3.md:3438: trailing whitespace.
++  1754	
.oracle/checkins/batch-3.md:3440: trailing whitespace.
++  1773	
.oracle/checkins/batch-3.md:3442: trailing whitespace.
++  1774	
.oracle/checkins/batch-3.md:3444: trailing whitespace.
++  1782	
.oracle/checkins/batch-3.md:3446: trailing whitespace.
++  1789	
.oracle/checkins/batch-3.md:3448: trailing whitespace.
++  1797	
.oracle/checkins/batch-3.md:3450: trailing whitespace.
++  1798	
.oracle/checkins/batch-3.md:3452: trailing whitespace.
++  1801	
.oracle/checkins/batch-3.md:3454: trailing whitespace.
++  1807	
.oracle/checkins/batch-3.md:3456: trailing whitespace.
++  1808	
.oracle/checkins/batch-3.md:3458: trailing whitespace.
++  1812	
.oracle/checkins/batch-3.md:3460: trailing whitespace.
++  1815	
.oracle/checkins/batch-3.md:3462: trailing whitespace.
++  1816	
.oracle/checkins/batch-3.md:3464: trailing whitespace.
++   733	
.oracle/checkins/batch-3.md:3466: trailing whitespace.
++   759	
.oracle/checkins/batch-3.md:3468: trailing whitespace.
++   764	
.oracle/checkins/batch-3.md:3470: trailing whitespace.
++   768	
.oracle/checkins/batch-3.md:3472: trailing whitespace.
++   784	
.oracle/checkins/batch-3.md:3474: trailing whitespace.
++   787	
.oracle/checkins/batch-3.md:3476: trailing whitespace.
++   794	
.oracle/checkins/batch-3.md:3478: trailing whitespace.
++   796	
.oracle/checkins/batch-3.md:3480: trailing whitespace.
++   803	
.oracle/checkins/batch-3.md:3482: trailing whitespace.
++   813	
.oracle/checkins/batch-3.md:3484: trailing whitespace.
++   820	
.oracle/checkins/batch-3.md:3486: trailing whitespace.
++   823	
.oracle/checkins/batch-3.md:3488: trailing whitespace.
++   826	
.oracle/checkins/batch-3.md:3490: trailing whitespace.
++   840	
.oracle/checkins/batch-3.md:3492: trailing whitespace.
++   847	
.oracle/checkins/batch-3.md:3494: trailing whitespace.
++   995	
.oracle/checkins/batch-3.md:3496: trailing whitespace.
++   996	
.oracle/checkins/batch-3.md:3498: trailing whitespace.
++  1007	
.oracle/checkins/batch-3.md:3500: trailing whitespace.
++  1008	
.oracle/checkins/batch-3.md:3502: trailing whitespace.
++  1019	
.oracle/checkins/batch-3.md:3504: trailing whitespace.
++  1020	
.oracle/checkins/batch-3.md:3506: trailing whitespace.
++  1027	
.oracle/checkins/batch-3.md:3508: trailing whitespace.
++  1031	
.oracle/checkins/batch-3.md:3510: trailing whitespace.
++  1032	
.oracle/checkins/batch-3.md:3512: trailing whitespace.
++  1043	
.oracle/checkins/batch-3.md:3514: trailing whitespace.
++  1044	
.oracle/checkins/batch-3.md:3516: trailing whitespace.
++  1049	
.oracle/checkins/batch-3.md:3518: trailing whitespace.
++  1050	
.oracle/checkins/batch-3.md:3520: trailing whitespace.
++  1054	
.oracle/checkins/batch-3.md:3522: trailing whitespace.
++  1055	
.oracle/checkins/batch-3.md:3524: trailing whitespace.
++  1270	
.oracle/checkins/batch-3.md:3526: trailing whitespace.
++  1325	
.oracle/checkins/batch-3.md:3528: trailing whitespace.
++  1326	
.oracle/checkins/batch-3.md:3530: trailing whitespace.
++  1338	
.oracle/checkins/batch-3.md:3532: trailing whitespace.
++  1339	
.oracle/checkins/batch-3.md:3534: trailing whitespace.
++   187	
.oracle/checkins/batch-3.md:3536: trailing whitespace.
++   190	
.oracle/checkins/batch-3.md:3538: trailing whitespace.
++   206	
.oracle/checkins/batch-3.md:3540: trailing whitespace.
++   209	
.oracle/checkins/batch-3.md:3542: trailing whitespace.
++   214	
.oracle/checkins/batch-3.md:3544: trailing whitespace.
++   217	
.oracle/checkins/batch-3.md:3546: trailing whitespace.
++   222	
.oracle/checkins/batch-3.md:3548: trailing whitespace.
++   226	
.oracle/checkins/batch-3.md:3550: trailing whitespace.
++   229	
.oracle/checkins/batch-3.md:3552: trailing whitespace.
++   232	
.oracle/checkins/batch-3.md:3554: trailing whitespace.
++   235	
.oracle/checkins/batch-3.md:3556: trailing whitespace.
++   238	
.oracle/checkins/batch-3.md:3558: trailing whitespace.
++   241	
.oracle/checkins/batch-3.md:3560: trailing whitespace.
++   252	
.oracle/checkins/batch-3.md:3562: trailing whitespace.
++   255	
.oracle/checkins/batch-3.md:3564: trailing whitespace.
++   264	
.oracle/checkins/batch-3.md:3566: trailing whitespace.
++   268	
.oracle/checkins/batch-3.md:3568: trailing whitespace.
++   430	
.oracle/checkins/batch-3.md:3570: trailing whitespace.
++   431	
.oracle/checkins/batch-3.md:3572: trailing whitespace.
++   434	
.oracle/checkins/batch-3.md:3574: trailing whitespace.
++   441	
.oracle/checkins/batch-3.md:3576: trailing whitespace.
++   449	
.oracle/checkins/batch-3.md:3578: trailing whitespace.
++   458	
.oracle/checkins/batch-3.md:3580: trailing whitespace.
++   478	
.oracle/checkins/batch-3.md:3582: trailing whitespace.
++   482	
.oracle/checkins/batch-3.md:3584: trailing whitespace.
++   503	
.oracle/checkins/batch-3.md:3586: trailing whitespace.
++   507	
.oracle/checkins/batch-3.md:3588: trailing whitespace.
++   511	
.oracle/checkins/batch-3.md:3590: trailing whitespace.
++   513	
.oracle/checkins/batch-3.md:3592: trailing whitespace.
++   522	
.oracle/checkins/batch-3.md:3594: trailing whitespace.
++   607	
.oracle/checkins/batch-3.md:3596: trailing whitespace.
++   634	
.oracle/checkins/batch-3.md:3598: trailing whitespace.
++   685	
.oracle/checkins/batch-3.md:3600: trailing whitespace.
++    37	
.oracle/checkins/batch-3.md:3602: trailing whitespace.
++    47	
.oracle/checkins/batch-3.md:3604: trailing whitespace.
++    58	
.oracle/checkins/batch-3.md:3606: trailing whitespace.
++    60	
.oracle/checkins/batch-3.md:3608: trailing whitespace.
++    65	
.oracle/checkins/batch-3.md:3610: trailing whitespace.
++    69	
.oracle/checkins/batch-3.md:3612: trailing whitespace.
++    70	
.oracle/checkins/batch-3.md:3614: trailing whitespace.
++   345	
.oracle/checkins/batch-3.md:3616: trailing whitespace.
++   347	
.oracle/checkins/batch-3.md:3618: trailing whitespace.
++   354	
.oracle/checkins/batch-3.md:3620: trailing whitespace.
++   940	
.oracle/checkins/batch-3.md:3622: trailing whitespace.
++   948	
.oracle/checkins/batch-3.md:3624: trailing whitespace.
++   949	
.oracle/checkins/batch-3.md:3626: trailing whitespace.
++   964	
.oracle/checkins/batch-3.md:3628: trailing whitespace.
++   965	
.oracle/checkins/batch-3.md:3630: trailing whitespace.
++   719	
.oracle/checkins/batch-3.md:3632: trailing whitespace.
++   726	
.oracle/checkins/batch-3.md:3634: trailing whitespace.
++   728	
.oracle/checkins/batch-3.md:3636: trailing whitespace.
++   730	
.oracle/checkins/batch-3.md:3638: trailing whitespace.
++   731	
.oracle/checkins/batch-3.md:3640: trailing whitespace.
++   734	
.oracle/checkins/batch-3.md:3642: trailing whitespace.
++   740	
.oracle/checkins/batch-3.md:3644: trailing whitespace.
++   741	
.oracle/checkins/batch-3.md:3646: trailing whitespace.
++   769	
.oracle/checkins/batch-3.md:3648: trailing whitespace.
++   770	
.oracle/checkins/batch-3.md:3650: trailing whitespace.
++   786	
.oracle/checkins/batch-3.md:3652: trailing whitespace.
++   787	
.oracle/checkins/batch-3.md:3654: trailing whitespace.
++   794	
.oracle/checkins/batch-3.md:3656: trailing whitespace.
++   795	
.oracle/checkins/batch-3.md:3658: trailing whitespace.
++   829	
.oracle/checkins/batch-3.md:3660: trailing whitespace.
++   830	
.oracle/checkins/batch-3.md:3662: trailing whitespace.
++   830	
.oracle/checkins/batch-3.md:3664: trailing whitespace.
++   951	
.oracle/checkins/batch-3.md:3666: trailing whitespace.
++   967	
.oracle/checkins/batch-3.md:3668: trailing whitespace.
++   969	
.oracle/checkins/batch-3.md:3670: trailing whitespace.
++   974	
.oracle/checkins/batch-3.md:3672: trailing whitespace.
++   981	
.oracle/checkins/batch-3.md:3674: trailing whitespace.
++   982	
.oracle/checkins/batch-3.md:3676: trailing whitespace.
++   985	
.oracle/checkins/batch-3.md:3678: trailing whitespace.
++   986	
.oracle/checkins/batch-3.md:3680: trailing whitespace.
++   989	
.oracle/checkins/batch-3.md:3682: trailing whitespace.
++   998	
.oracle/checkins/batch-3.md:3684: trailing whitespace.
++   999	
.oracle/checkins/batch-3.md:3686: trailing whitespace.
++  1018	
.oracle/checkins/batch-3.md:3688: trailing whitespace.
++  1019	
.oracle/checkins/batch-3.md:3690: trailing whitespace.
++  1043	
.oracle/checkins/batch-3.md:3692: trailing whitespace.
++  1044	
.oracle/checkins/batch-3.md:3694: trailing whitespace.
++     2	
.oracle/checkins/batch-3.md:3696: trailing whitespace.
++     4	
.oracle/checkins/batch-3.md:3698: trailing whitespace.
++     5	
.oracle/checkins/batch-3.md:3700: trailing whitespace.
++     7	
.oracle/checkins/batch-3.md:3702: trailing whitespace.
++     8	
.oracle/checkins/batch-3.md:3704: trailing whitespace.
++    19	
.oracle/checkins/batch-3.md:3706: trailing whitespace.
++    25	
.oracle/checkins/batch-3.md:3708: trailing whitespace.
++    29	
.oracle/checkins/batch-3.md:3710: trailing whitespace.
++    38	
.oracle/checkins/batch-3.md:3712: trailing whitespace.
++    39	
.oracle/checkins/batch-3.md:3714: trailing whitespace.
++    42	
.oracle/checkins/batch-3.md:3716: trailing whitespace.
++    48	
.oracle/checkins/batch-3.md:3718: trailing whitespace.
++    49	
.oracle/checkins/batch-3.md:3720: trailing whitespace.
++    53	
.oracle/checkins/batch-3.md:3722: trailing whitespace.
++    54	
.oracle/checkins/batch-3.md:3724: trailing whitespace.
++    50	
.oracle/checkins/batch-3.md:3726: trailing whitespace.
++    51	
.oracle/checkins/batch-3.md:3728: trailing whitespace.
++    54	
.oracle/checkins/batch-3.md:3730: trailing whitespace.
++    81	
.oracle/checkins/batch-3.md:3732: trailing whitespace.
++     2	
.oracle/checkins/batch-3.md:3734: trailing whitespace.
++     4	
.oracle/checkins/batch-3.md:3736: trailing whitespace.
++     7	
.oracle/checkins/batch-3.md:3738: trailing whitespace.
++    12	
.oracle/checkins/batch-3.md:3740: trailing whitespace.
++    13	
.oracle/checkins/batch-3.md:3742: trailing whitespace.
++    16	
.oracle/checkins/batch-3.md:3744: trailing whitespace.
++    23	
.oracle/checkins/batch-3.md:3746: trailing whitespace.
++    26	
.oracle/checkins/batch-3.md:3748: trailing whitespace.
++    31	
.oracle/checkins/batch-3.md:3750: trailing whitespace.
++    44	
.oracle/checkins/batch-3.md:3752: trailing whitespace.
++    79	
.oracle/checkins/batch-3.md:3754: trailing whitespace.
++    97	
.oracle/checkins/batch-3.md:3756: trailing whitespace.
++   104	
.oracle/checkins/batch-3.md:3758: trailing whitespace.
++   107	
.oracle/checkins/batch-3.md:3760: trailing whitespace.
++   117	
.oracle/checkins/batch-3.md:3762: trailing whitespace.
++   124	
.oracle/checkins/batch-3.md:3764: trailing whitespace.
++   383	
.oracle/checkins/batch-3.md:3766: trailing whitespace.
++   384	
.oracle/checkins/batch-3.md:3768: trailing whitespace.
++   393	
.oracle/checkins/batch-3.md:3770: trailing whitespace.
++   394	
.oracle/checkins/batch-3.md:3772: trailing whitespace.
++   402	
.oracle/checkins/batch-3.md:3774: trailing whitespace.
++   403	
.oracle/checkins/batch-3.md:3776: trailing whitespace.
++   406	
.oracle/checkins/batch-3.md:3778: trailing whitespace.
++   416	
.oracle/checkins/batch-3.md:3780: trailing whitespace.
++   417	
.oracle/checkins/batch-3.md:3782: trailing whitespace.
++   430	
.oracle/checkins/batch-3.md:3784: trailing whitespace.
++  1670	
.oracle/checkins/batch-3.md:3786: trailing whitespace.
++  1671	
.oracle/checkins/batch-3.md:3788: trailing whitespace.
++  1680	
.oracle/checkins/batch-3.md:3790: trailing whitespace.
++  1681	
.oracle/checkins/batch-3.md:3792: trailing whitespace.
++  1690	
.oracle/checkins/batch-3.md:3794: trailing whitespace.
++  1691	
.oracle/checkins/batch-3.md:3796: trailing whitespace.
++  1699	
.oracle/checkins/batch-3.md:3798: trailing whitespace.
++  1700	
.oracle/checkins/batch-3.md:3800: trailing whitespace.
++  1710	
.oracle/checkins/batch-3.md:3802: trailing whitespace.
++  1711	
.oracle/checkins/batch-3.md:3804: trailing whitespace.
++  1724	
.oracle/checkins/batch-3.md:3806: trailing whitespace.
++  1725	
.oracle/checkins/batch-3.md:3808: trailing whitespace.
++  1753	
.oracle/checkins/batch-3.md:3810: trailing whitespace.
++  1754	
.oracle/checkins/batch-3.md:3812: trailing whitespace.
++  1773	
.oracle/checkins/batch-3.md:3814: trailing whitespace.
++  1774	
.oracle/checkins/batch-3.md:3816: trailing whitespace.
++  1782	
.oracle/checkins/batch-3.md:3818: trailing whitespace.
++  1789	
.oracle/checkins/batch-3.md:3820: trailing whitespace.
++  1797	
.oracle/checkins/batch-3.md:3822: trailing whitespace.
++  1798	
.oracle/checkins/batch-3.md:3824: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3826: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3828: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3830: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3832: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3834: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3836: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3838: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3840: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3842: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3844: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3846: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3848: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3850: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3852: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3854: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3856: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3858: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3860: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3862: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3864: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3866: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3868: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3870: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3872: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3874: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3876: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3878: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3880: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3882: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3884: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3886: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3888: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3890: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3892: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3894: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3896: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3898: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3900: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3902: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3904: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3906: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3908: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3910: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3912: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3914: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3916: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3918: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3920: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3922: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3924: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3926: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3928: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3930: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3932: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3934: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3936: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3938: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3940: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3942: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3944: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3946: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3948: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3950: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3952: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3954: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3956: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3958: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3960: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3962: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3964: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3966: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3968: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3970: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3972: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3974: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3976: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3978: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3980: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3982: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3984: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3986: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3988: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3990: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3992: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3994: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3996: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:3998: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4000: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4002: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4004: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4006: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4008: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4010: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4012: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4014: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4016: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4018: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4020: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4022: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4024: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4026: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4028: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4030: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4032: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4034: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:4213: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4215: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4216: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4218: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4219: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4230: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4239: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4243: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4253: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4254: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4268: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4274: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4275: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4279: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4280: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4294: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4297: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4300: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4315: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4316: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4325: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4326: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4329: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4333: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4334: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4337: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4338: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4341: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4342: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4345: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4346: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4353: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4354: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4357: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4358: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4407: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4408: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4424: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4437: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4438: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4450: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4451: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4459: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4460: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4473: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4474: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4477: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4478: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4484: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4485: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4496: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4497: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4507: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4508: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4518: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4519: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4524: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4525: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4555: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4559: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4566: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4567: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4574: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4575: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4606: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4607: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4643: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4646: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4656: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4657: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4669: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4670: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4681: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4682: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4698: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4699: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4712: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4713: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4720: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4721: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4730: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4731: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4737: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4738: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4740: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4741: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4759: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4760: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4763: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4764: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4769: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4770: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4773: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4780: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4788: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4789: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4795: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4796: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4803: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4808: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4816: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4822: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4829: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4832: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4833: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4841: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4846: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4847: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4852: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4853: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4868: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4869: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4876: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4877: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4885: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4886: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4894: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4895: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4914: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4917: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4933: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4936: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4941: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4944: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4949: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4953: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4956: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4959: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4962: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4965: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4968: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4979: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4982: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4992: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:4996: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5003: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5005: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5008: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5011: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5028: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5039: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5045: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5054: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5073: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5084: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5087: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5096: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5117: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5120: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5128: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5178: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5183: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5186: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5189: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5204: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5231: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5236: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5240: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5256: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5259: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5266: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5268: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5275: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5285: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5295: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5296: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5318: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5319: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5331: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5342: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5343: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5350: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5354: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5355: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5366: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5367: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5437: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5438: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5442: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5443: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5454: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5455: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5458: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5459: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5466: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5467: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5471: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5475: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5476: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5495: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5496: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5523: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5539: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5556: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5584: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5585: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5592: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5593: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5604: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5605: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5610: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5611: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:5668: trailing whitespace.
+     2	
.oracle/checkins/batch-3.md:5674: trailing whitespace.
+     8	
.oracle/checkins/batch-3.md:5681: trailing whitespace.
+    15	
.oracle/checkins/batch-3.md:5684: trailing whitespace.
+    18	
.oracle/checkins/batch-3.md:5685: trailing whitespace.
+    19	
.oracle/checkins/batch-3.md:5693: trailing whitespace.
+    27	
.oracle/checkins/batch-3.md:5698: trailing whitespace.
+    32	
.oracle/checkins/batch-3.md:5699: trailing whitespace.
+    33	
.oracle/checkins/batch-3.md:5704: trailing whitespace.
+    38	
.oracle/checkins/batch-3.md:5705: trailing whitespace.
+    39	
.oracle/checkins/batch-3.md:5720: trailing whitespace.
+    54	
.oracle/checkins/batch-3.md:5721: trailing whitespace.
+    55	
.oracle/checkins/batch-3.md:5728: trailing whitespace.
+    62	
.oracle/checkins/batch-3.md:5729: trailing whitespace.
+    63	
.oracle/checkins/batch-3.md:5737: trailing whitespace.
+    71	
.oracle/checkins/batch-3.md:5738: trailing whitespace.
+    72	
.oracle/checkins/batch-3.md:5746: trailing whitespace.
+    80	
.oracle/checkins/batch-3.md:5747: trailing whitespace.
+    81	
.oracle/checkins/batch-3.md:5759: trailing whitespace.
+    93	
.oracle/checkins/batch-3.md:5764: trailing whitespace.
+    98	
.oracle/checkins/batch-3.md:5766: trailing whitespace.
+   100	
.oracle/checkins/batch-3.md:5767: trailing whitespace.
+   101	
.oracle/checkins/batch-3.md:5774: trailing whitespace.
+   108	
.oracle/checkins/batch-3.md:5775: trailing whitespace.
+   109	
.oracle/checkins/batch-3.md:5788: trailing whitespace.
+   122	
.oracle/checkins/batch-3.md:5792: trailing whitespace.
+   126	
.oracle/checkins/batch-3.md:5796: trailing whitespace.
+   130	
.oracle/checkins/batch-3.md:5797: trailing whitespace.
+   131	
.oracle/checkins/batch-3.md:5807: trailing whitespace.
+   141	
.oracle/checkins/batch-3.md:5808: trailing whitespace.
+   142	
.oracle/checkins/batch-3.md:5815: trailing whitespace.
+   149	
.oracle/checkins/batch-3.md:5816: trailing whitespace.
+   150	
.oracle/checkins/batch-3.md:5821: trailing whitespace.
+   155	
.oracle/checkins/batch-3.md:5822: trailing whitespace.
+   156	
.oracle/checkins/batch-3.md:5825: trailing whitespace.
+   159	
.oracle/checkins/batch-3.md:5837: trailing whitespace.
+   171	
.oracle/checkins/batch-3.md:5838: trailing whitespace.
+   172	
.oracle/checkins/batch-3.md:5854: trailing whitespace.
+   188	
.oracle/checkins/batch-3.md:5857: trailing whitespace.
+   191	
.oracle/checkins/batch-3.md:5873: trailing whitespace.
+   207	
.oracle/checkins/batch-3.md:5876: trailing whitespace.
+   210	
.oracle/checkins/batch-3.md:5881: trailing whitespace.
+   215	
.oracle/checkins/batch-3.md:5884: trailing whitespace.
+   218	
.oracle/checkins/batch-3.md:5889: trailing whitespace.
+   223	
.oracle/checkins/batch-3.md:5893: trailing whitespace.
+   227	
.oracle/checkins/batch-3.md:5896: trailing whitespace.
+   230	
.oracle/checkins/batch-3.md:5899: trailing whitespace.
+   233	
.oracle/checkins/batch-3.md:5902: trailing whitespace.
+   236	
.oracle/checkins/batch-3.md:5905: trailing whitespace.
+   239	
.oracle/checkins/batch-3.md:5908: trailing whitespace.
+   242	
.oracle/checkins/batch-3.md:5919: trailing whitespace.
+   253	
.oracle/checkins/batch-3.md:5922: trailing whitespace.
+   256	
.oracle/checkins/batch-3.md:5932: trailing whitespace.
+   266	
.oracle/checkins/batch-3.md:5936: trailing whitespace.
+   270	
.oracle/checkins/batch-3.md:5943: trailing whitespace.
+   277	
.oracle/checkins/batch-3.md:5945: trailing whitespace.
+   279	
.oracle/checkins/batch-3.md:5948: trailing whitespace.
+   282	
.oracle/checkins/batch-3.md:5951: trailing whitespace.
+   285	
.oracle/checkins/batch-3.md:5968: trailing whitespace.
+   302	
.oracle/checkins/batch-3.md:5979: trailing whitespace.
+   313	
.oracle/checkins/batch-3.md:5985: trailing whitespace.
+   319	
.oracle/checkins/batch-3.md:5994: trailing whitespace.
+   328	
.oracle/checkins/batch-3.md:6033: trailing whitespace.
+   367	
.oracle/checkins/batch-3.md:6038: trailing whitespace.
+   372	
.oracle/checkins/batch-3.md:6060: trailing whitespace.
+   394	
.oracle/checkins/batch-3.md:6072: trailing whitespace.
+   406	
.oracle/checkins/batch-3.md:6091: trailing whitespace.
+   425	
.oracle/checkins/batch-3.md:6099: trailing whitespace.
+   782	
.oracle/checkins/batch-3.md:6115: trailing whitespace.
+   798	
.oracle/checkins/batch-3.md:6118: trailing whitespace.
+   801	
.oracle/checkins/batch-3.md:6125: trailing whitespace.
+   808	
.oracle/checkins/batch-3.md:6127: trailing whitespace.
+   810	
.oracle/checkins/batch-3.md:6134: trailing whitespace.
+   817	
.oracle/checkins/batch-3.md:6144: trailing whitespace.
+   827	
.oracle/checkins/batch-3.md:6151: trailing whitespace.
+   834	
.oracle/checkins/batch-3.md:6154: trailing whitespace.
+   837	
.oracle/checkins/batch-3.md:6157: trailing whitespace.
+   840	
.oracle/checkins/batch-3.md:6171: trailing whitespace.
+   854	
.oracle/checkins/batch-3.md:6178: trailing whitespace.
+   861	
.oracle/checkins/batch-3.md:6188: trailing whitespace.
+   871	
.oracle/checkins/batch-3.md:6203: trailing whitespace.
+   886	
.oracle/checkins/batch-3.md:6215: trailing whitespace.
+   898	
.oracle/checkins/batch-3.md:6221: trailing whitespace.
+   904	
.oracle/checkins/batch-3.md:6224: trailing whitespace.
+   907	
.oracle/checkins/batch-3.md:6234: trailing whitespace.
+   917	
.oracle/checkins/batch-3.md:6249: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6253: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6255: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6286: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6289: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6290: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6293: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6316: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6317: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6326: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6397: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6424: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6484: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6506: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6513: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6514: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6548: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6549: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6671: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6688: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6690: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6695: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6702: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6703: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6706: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6707: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6710: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6719: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6720: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6739: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6740: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:6765: trailing whitespace.
+   418	
.oracle/checkins/batch-3.md:6766: trailing whitespace.
+   419	
.oracle/checkins/batch-3.md:6779: trailing whitespace.
+   432	
.oracle/checkins/batch-3.md:6780: trailing whitespace.
+   433	
.oracle/checkins/batch-3.md:6783: trailing whitespace.
+   436	
.oracle/checkins/batch-3.md:6790: trailing whitespace.
+   443	
.oracle/checkins/batch-3.md:6798: trailing whitespace.
+   451	
.oracle/checkins/batch-3.md:6807: trailing whitespace.
+   460	
.oracle/checkins/batch-3.md:6827: trailing whitespace.
+   480	
.oracle/checkins/batch-3.md:6831: trailing whitespace.
+   484	
.oracle/checkins/batch-3.md:6852: trailing whitespace.
+   505	
.oracle/checkins/batch-3.md:6856: trailing whitespace.
+   509	
.oracle/checkins/batch-3.md:6860: trailing whitespace.
+   513	
.oracle/checkins/batch-3.md:6862: trailing whitespace.
+   515	
.oracle/checkins/batch-3.md:6871: trailing whitespace.
+   524	
.oracle/checkins/batch-3.md:6956: trailing whitespace.
+   609	
.oracle/checkins/batch-3.md:6983: trailing whitespace.
+   636	
.oracle/checkins/batch-3.md:6993: trailing whitespace.
+   646	
.oracle/checkins/batch-3.md:7033: trailing whitespace.
+   840	
.oracle/checkins/batch-3.md:7034: trailing whitespace.
+   841	
.oracle/checkins/batch-3.md:7149: trailing whitespace.
+   956	
.oracle/checkins/batch-3.md:7159: trailing whitespace.
+   966	
.oracle/checkins/batch-3.md:7161: trailing whitespace.
+   968	
.oracle/checkins/batch-3.md:7166: trailing whitespace.
+   973	
.oracle/checkins/batch-3.md:7173: trailing whitespace.
+   980	
.oracle/checkins/batch-3.md:7174: trailing whitespace.
+   981	
.oracle/checkins/batch-3.md:7177: trailing whitespace.
+   984	
.oracle/checkins/batch-3.md:7178: trailing whitespace.
+   985	
.oracle/checkins/batch-3.md:7181: trailing whitespace.
+   988	
.oracle/checkins/batch-3.md:7272: trailing whitespace.
+19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 345) 
.oracle/checkins/batch-3.md:7274: trailing whitespace.
+19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 347) 
.oracle/checkins/batch-3.md:7484: trailing whitespace.
+    90	
.oracle/checkins/batch-3.md:7491: trailing whitespace.
+    97	
.oracle/checkins/batch-3.md:7492: trailing whitespace.
+    98	
.oracle/checkins/batch-3.md:7519: trailing whitespace.
+   125	
.oracle/checkins/batch-3.md:7520: trailing whitespace.
+   126	
.oracle/checkins/batch-3.md:7534: trailing whitespace.
+   140	
.oracle/checkins/batch-3.md:7535: trailing whitespace.
+   141	
.oracle/checkins/batch-3.md:7543: trailing whitespace.
+   149	
.oracle/checkins/batch-3.md:7544: trailing whitespace.
+   150	
.oracle/checkins/batch-3.md:7560: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7568: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7573: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7574: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7620: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7621: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7628: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7640: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7641: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7648: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7653: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7662: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7667: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7671: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7685: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7688: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7689: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7698: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7699: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7702: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7726: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7749: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7762: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7828: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7850: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7873: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7879: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7881: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7890: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7899: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7904: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7913: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7917: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7923: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7925: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7937: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7956: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7959: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7962: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7965: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7970: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7974: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7980: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7985: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7989: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:7990: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8020: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8031: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8032: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8050: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8051: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8054: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8060: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8061: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8064: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8079: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8080: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8083: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8097: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8098: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8101: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8119: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8120: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8127: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8130: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8145: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8174: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8200: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8210: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8211: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8214: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8232: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8233: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8237: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8238: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8241: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8259: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8260: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8266: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8267: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8270: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8281: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8282: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8290: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8291: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8300: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8317: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8318: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8321: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8324: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8326: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8327: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8354: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8355: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8422: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8423: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8428: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8436: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8450: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8464: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8477: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8478: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8484: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8493: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8501: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8557: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8562: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8584: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8585: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8609: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8651: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8676: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8719: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8753: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8770: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8776: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8784: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8791: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8795: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8854: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8863: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8883: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8895: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8907: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8944: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8946: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8959: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8980: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:8989: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9000: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9002: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9006: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9012: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9036: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9047: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9062: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9071: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9080: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9084: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9086: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9087: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9094: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9099: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9106: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9113: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9114: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9129: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9133: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9156: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9159: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9165: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9171: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9175: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9178: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9180: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9192: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9193: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9200: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9201: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9204: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9208: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9209: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9213: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9220: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9221: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9224: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9239: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9240: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9243: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9266: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9267: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9272: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9297: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9298: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9301: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9321: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9324: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9338: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9346: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9359: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9367: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9371: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9372: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9375: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9386: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9387: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9390: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9404: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9424: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9436: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9437: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9440: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:9468: trailing whitespace.
+   387	
.oracle/checkins/batch-3.md:9469: trailing whitespace.
+   388	
.oracle/checkins/batch-3.md:9478: trailing whitespace.
+   397	
.oracle/checkins/batch-3.md:9495: trailing whitespace.
+   414	
.oracle/checkins/batch-3.md:9496: trailing whitespace.
+   415	
.oracle/checkins/batch-3.md:9499: trailing whitespace.
+   418	
.oracle/checkins/batch-3.md:9502: trailing whitespace.
+   421	
.oracle/checkins/batch-3.md:9504: trailing whitespace.
+   423	
.oracle/checkins/batch-3.md:9505: trailing whitespace.
+   424	
.oracle/checkins/batch-3.md:9508: trailing whitespace.
+   427	
.oracle/checkins/batch-3.md:9532: trailing whitespace.
+   451	
.oracle/checkins/batch-3.md:9533: trailing whitespace.
+   452	
.oracle/checkins/batch-3.md:9540: trailing whitespace.
+   459	
.oracle/checkins/batch-3.md:9548: trailing whitespace.
+   467	
.oracle/checkins/batch-3.md:9559: trailing whitespace.
+   478	
.oracle/checkins/batch-3.md:9569: trailing whitespace.
+   488	
.oracle/checkins/batch-3.md:9594: trailing whitespace.
+   513	
.oracle/checkins/batch-3.md:9595: trailing whitespace.
+   514	
.oracle/checkins/batch-3.md:9600: trailing whitespace.
+   519	
.oracle/checkins/batch-3.md:9601: trailing whitespace.
+   520	
.oracle/checkins/batch-3.md:9605: trailing whitespace.
+  1343	
.oracle/checkins/batch-3.md:9610: trailing whitespace.
+  1348	
.oracle/checkins/batch-3.md:9644: trailing whitespace.
+  1382	
.oracle/checkins/batch-3.md:9645: trailing whitespace.
+  1383	
.oracle/checkins/batch-3.md:9653: trailing whitespace.
+  1391	
.oracle/checkins/batch-3.md:9654: trailing whitespace.
+  1392	
.oracle/checkins/batch-3.md:9663: trailing whitespace.
+  1401	
.oracle/checkins/batch-3.md:9664: trailing whitespace.
+  1402	
.oracle/checkins/batch-3.md:9683: trailing whitespace.
+  1421	
.oracle/checkins/batch-3.md:9688: trailing whitespace.
+  1426	
.oracle/checkins/batch-3.md:9690: trailing whitespace.
+  1428	
.oracle/checkins/batch-3.md:9691: trailing whitespace.
+  1429	
.oracle/checkins/batch-3.md:9696: trailing whitespace.
+  1434	
.oracle/checkins/batch-3.md:9707: trailing whitespace.
+  1445	
.oracle/checkins/batch-3.md:9752: trailing whitespace.
+  2014	
.oracle/checkins/batch-3.md:9757: trailing whitespace.
+  2019	
.oracle/checkins/batch-3.md:9779: trailing whitespace.
+  2041	
.oracle/checkins/batch-3.md:9780: trailing whitespace.
+  2042	
.oracle/checkins/batch-3.md:9803: trailing whitespace.
+  2065	
.oracle/checkins/batch-3.md:9858: trailing whitespace.
+  2394	
.oracle/checkins/batch-3.md:9875: trailing whitespace.
+  2411	
.oracle/checkins/batch-3.md:9881: trailing whitespace.
+  2417	
.oracle/checkins/batch-3.md:9889: trailing whitespace.
+  2425	
.oracle/checkins/batch-3.md:9896: trailing whitespace.
+  2432	
.oracle/checkins/batch-3.md:9900: trailing whitespace.
+  2436	
.oracle/checkins/batch-3.md:9920: trailing whitespace.
+  1480	
.oracle/checkins/batch-3.md:9937: trailing whitespace.
+  1497	
.oracle/checkins/batch-3.md:9965: trailing whitespace.
+  1525	
.oracle/checkins/batch-3.md:9966: trailing whitespace.
+  1526	
.oracle/checkins/batch-3.md:9973: trailing whitespace.
+  1533	
.oracle/checkins/batch-3.md:9974: trailing whitespace.
+  1534	
.oracle/checkins/batch-3.md:10088: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10092: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10102: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10103: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10106: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10107: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10112: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10113: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10129: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10130: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10134: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10135: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10144: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10145: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10149: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10150: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10154: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10155: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10160: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10161: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10170: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10175: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10176: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10187: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10191: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10192: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10198: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10202: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10208: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10209: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10216: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10225: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10226: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10256: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10259: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10267: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10273: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10274: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10281: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10285: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10286: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10293: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10300: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10301: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10305: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10306: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10313: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10314: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10319: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10327: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10334: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10337: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10338: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10345: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10348: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10352: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10355: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10356: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10360: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10361: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10364: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10368: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10379: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10384: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10385: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10393: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10396: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10407: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10422: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10427: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10435: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10442: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10448: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10450: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10458: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10459: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10462: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10472: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10473: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10476: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10478: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10479: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10484: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10499: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10505: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10506: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10510: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10512: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10515: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10516: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10519: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10524: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10527: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10551: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10552: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10556: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10559: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10561: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10562: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10566: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10568: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10570: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10583: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10584: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10589: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10591: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10593: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10597: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10598: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10602: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10606: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10611: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10615: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10616: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10619: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10621: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10647: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10648: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10668: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10669: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10673: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10676: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10682: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10683: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10686: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10693: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10695: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10700: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10706: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10707: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10711: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10714: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10720: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10724: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10726: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10727: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10731: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10736: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10741: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10746: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10751: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10756: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10757: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10761: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10768: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10775: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10782: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10783: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10793: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10794: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10798: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10799: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10803: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10805: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10809: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10813: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10824: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10825: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10829: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10830: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10835: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10839: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10844: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10852: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10856: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10861: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10862: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10866: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10867: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10872: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10884: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10887: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10891: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10899: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10900: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10904: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10905: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10910: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10919: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10924: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10927: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10937: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10943: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10944: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10948: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10949: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10953: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10960: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10966: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:10972: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11015: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11016: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11022: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11035: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11036: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11040: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11041: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11050: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11064: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11075: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11076: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11092: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11095: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11102: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11103: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11110: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11113: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11118: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11119: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11127: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11137: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11142: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11143: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11150: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11159: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11164: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11165: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11182: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11195: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11202: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11203: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11272: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11273: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11276: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11293: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11299: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11304: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11305: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11308: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11319: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11336: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11339: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11340: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11343: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11359: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11368: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11371: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11376: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11380: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11384: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11389: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11390: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11400: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11402: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11408: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11411: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11412: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11417: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11434: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11435: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11442: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11446: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11452: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11457: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11458: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11466: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11469: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11473: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11477: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11478: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11482: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11483: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11486: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11493: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11495: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11502: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11506: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11509: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11513: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11514: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11518: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11519: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11523: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11527: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11530: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11535: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11537: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11542: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11550: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11554: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11565: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11566: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11570: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11571: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11588: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11606: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11623: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11629: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11630: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11640: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11650: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11656: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11657: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11666: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11670: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11681: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11684: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11686: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11696: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11697: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11701: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11704: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11707: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11708: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11713: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11714: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11717: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11718: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11721: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11722: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11726: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11730: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11731: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11735: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11739: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11740: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11744: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11754: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11755: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11771: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11773: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11780: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11781: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11806: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11808: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11812: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11813: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11846: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11848: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11853: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11854: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11876: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11878: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11885: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11886: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11903: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11905: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11908: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11909: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11926: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11929: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11938: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11939: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11945: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11953: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11954: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11970: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11974: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11975: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11988: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11991: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:11992: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12009: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12011: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12013: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12015: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12016: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12023: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12024: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12031: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12032: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12039: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12040: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12047: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12057: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12062: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12078: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12080: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12087: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12092: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12097: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12112: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12119: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12124: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12133: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12139: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12148: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12149: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12152: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12158: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12165: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12182: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12189: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12197: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12199: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12221: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12222: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12226: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12229: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12230: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12237: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12239: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12258: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12259: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12373: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12375: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12377: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12378: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12381: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12382: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12385: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12388: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12391: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12392: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12399: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12402: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12407: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12409: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12410: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12438: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12439: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12444: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12447: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12448: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12454: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12457: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12462: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12463: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12474: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12477: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12483: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12484: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12496: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12499: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12504: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12505: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12518: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12521: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12526: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12527: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12532: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12534: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12538: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12539: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12543: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12546: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12549: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12550: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12556: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12563: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12564: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12616: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12618: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12631: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12647: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12663: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12664: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12680: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12682: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12686: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12695: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12696: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12701: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12715: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12720: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12725: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12726: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12731: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12733: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12737: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12741: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12742: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12751: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12763: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12764: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12770: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12771: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12781: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12783: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12784: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12790: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12792: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12796: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12797: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12806: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12808: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12811: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12812: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12829: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12831: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12834: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12835: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12855: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12857: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12860: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12861: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12869: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12871: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12874: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12875: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12883: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12885: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12888: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12889: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12896: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12898: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12902: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12903: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12911: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12913: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12916: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12917: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12931: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12933: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12936: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12937: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12947: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12949: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12952: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12953: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12966: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12968: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12971: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12972: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:12998: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13000: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13002: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13004: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13006: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13016: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13019: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13023: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13024: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13029: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13032: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13035: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13036: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13042: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13049: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13050: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13056: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13059: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13064: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13065: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13073: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13075: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13081: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13082: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13087: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13092: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13094: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13098: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13099: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13104: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13106: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13113: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13114: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13117: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13119: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13123: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13127: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13130: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13135: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13138: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13142: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13143: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13154: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13157: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13167: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13168: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13178: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13180: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13185: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13186: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13197: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13200: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13205: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13206: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13217: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13220: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13225: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13226: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13235: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13238: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13244: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13245: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13253: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13256: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13261: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13262: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13265: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13270: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13273: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13276: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13284: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13286: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13289: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13290: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13317: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13319: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13330: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13331: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13364: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13366: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13375: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13376: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13411: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13413: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13460: trailing whitespace.
+    50	
.oracle/checkins/batch-3.md:13462: trailing whitespace.
+    52	
.oracle/checkins/batch-3.md:13481: trailing whitespace.
+    71	
.oracle/checkins/batch-3.md:13482: trailing whitespace.
+    72	
.oracle/checkins/batch-3.md:13498: trailing whitespace.
+    88	
.oracle/checkins/batch-3.md:13513: trailing whitespace.
+   103	
.oracle/checkins/batch-3.md:13522: trailing whitespace.
+   112	
.oracle/checkins/batch-3.md:13523: trailing whitespace.
+   113	
.oracle/checkins/batch-3.md:13530: trailing whitespace.
+   120	
.oracle/checkins/batch-3.md:13532: trailing whitespace.
+   122	
.oracle/checkins/batch-3.md:13536: trailing whitespace.
+   126	
.oracle/checkins/batch-3.md:13537: trailing whitespace.
+   127	
.oracle/checkins/batch-3.md:13544: trailing whitespace.
+   134	
.oracle/checkins/batch-3.md:13549: trailing whitespace.
+   139	
.oracle/checkins/batch-3.md:13555: trailing whitespace.
+   145	
.oracle/checkins/batch-3.md:13556: trailing whitespace.
+   146	
.oracle/checkins/batch-3.md:13573: trailing whitespace.
+   163	
.oracle/checkins/batch-3.md:13576: trailing whitespace.
+   166	
.oracle/checkins/batch-3.md:13580: trailing whitespace.
+   170	
.oracle/checkins/batch-3.md:13581: trailing whitespace.
+   171	
.oracle/checkins/batch-3.md:13589: trailing whitespace.
+   179	
.oracle/checkins/batch-3.md:13592: trailing whitespace.
+   182	
.oracle/checkins/batch-3.md:13593: trailing whitespace.
+   183	
.oracle/checkins/batch-3.md:13596: trailing whitespace.
+   186	
.oracle/checkins/batch-3.md:13598: trailing whitespace.
+   188	
.oracle/checkins/batch-3.md:13600: trailing whitespace.
+   190	
.oracle/checkins/batch-3.md:13601: trailing whitespace.
+   191	
.oracle/checkins/batch-3.md:13604: trailing whitespace.
+   194	
.oracle/checkins/batch-3.md:13605: trailing whitespace.
+   195	
.oracle/checkins/batch-3.md:13608: trailing whitespace.
+   198	
.oracle/checkins/batch-3.md:13624: trailing whitespace.
+  2193	
.oracle/checkins/batch-3.md:13637: trailing whitespace.
+  2206	
.oracle/checkins/batch-3.md:13643: trailing whitespace.
+  2212	
.oracle/checkins/batch-3.md:13644: trailing whitespace.
+  2213	
.oracle/checkins/batch-3.md:13669: trailing whitespace.
+  2238	
.oracle/checkins/batch-3.md:13671: trailing whitespace.
+  2240	
.oracle/checkins/batch-3.md:13674: trailing whitespace.
+  2243	
.oracle/checkins/batch-3.md:13675: trailing whitespace.
+  2244	
.oracle/checkins/batch-3.md:13697: trailing whitespace.
+  2266	
.oracle/checkins/batch-3.md:13699: trailing whitespace.
+  2268	
.oracle/checkins/batch-3.md:13708: trailing whitespace.
+  2277	
.oracle/checkins/batch-3.md:13709: trailing whitespace.
+  2278	
.oracle/checkins/batch-3.md:13713: trailing whitespace.
+  2282	
.oracle/checkins/batch-3.md:13714: trailing whitespace.
+  2283	
.oracle/checkins/batch-3.md:13717: trailing whitespace.
+  2286	
.oracle/checkins/batch-3.md:13734: trailing whitespace.
+  2303	
.oracle/checkins/batch-3.md:13740: trailing whitespace.
+  2309	
.oracle/checkins/batch-3.md:13745: trailing whitespace.
+  2314	
.oracle/checkins/batch-3.md:13746: trailing whitespace.
+  2315	
.oracle/checkins/batch-3.md:13749: trailing whitespace.
+  2318	
.oracle/checkins/batch-3.md:13759: trailing whitespace.
+  2327	
.oracle/checkins/batch-3.md:13769: trailing whitespace.
+  2337	
.oracle/checkins/batch-3.md:13775: trailing whitespace.
+  2343	
.oracle/checkins/batch-3.md:13778: trailing whitespace.
+  2346	
.oracle/checkins/batch-3.md:13779: trailing whitespace.
+  2347	
.oracle/checkins/batch-3.md:13782: trailing whitespace.
+  2350	
.oracle/checkins/batch-3.md:13798: trailing whitespace.
+  2366	
.oracle/checkins/batch-3.md:13807: trailing whitespace.
+  2375	
.oracle/checkins/batch-3.md:13819: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13824: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13825: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13832: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13838: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13839: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13842: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13843: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13851: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13855: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13865: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13893: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13895: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13900: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13904: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13905: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13911: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13912: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13915: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13916: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13922: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13924: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13925: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13931: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13933: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13934: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13939: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13940: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13945: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13946: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13951: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13952: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13955: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13956: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13959: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13960: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13973: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13976: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13977: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13984: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13988: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:13992: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14001: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14003: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14004: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14008: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14009: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14020: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14026: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14032: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14053: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14062: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14063: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14074: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14076: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14082: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14088: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14107: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14120: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14129: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14130: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14145: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14146: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14158: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14159: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14163: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14164: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14176: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14180: trailing whitespace.
+ 
.oracle/checkins/batch-3.md:14365: trailing whitespace.
+  1010	
.oracle/checkins/batch-3.md:14377: trailing whitespace.
+  1022	
.oracle/checkins/batch-3.md:14380: trailing whitespace.
+  1025	
.oracle/checkins/batch-3.md:14386: trailing whitespace.
+  1031	
.oracle/checkins/batch-3.md:14395: trailing whitespace.
+  1040	
.oracle/checkins/batch-3.md:14400: trailing whitespace.
+  1045	
.oracle/checkins/batch-3.md:14404: trailing whitespace.
+  1049	
.oracle/checkins/batch-3.md:14438: trailing whitespace.
+  1083	
.oracle/checkins/batch-3.md:14441: trailing whitespace.
+  1086	
.oracle/checkins/batch-3.md:14442: trailing whitespace.
+  1087	
.oracle/checkins/batch-3.md:14446: trailing whitespace.
+  1091	
.oracle/checkins/batch-3.md:14447: trailing whitespace.
+  1092	
.oracle/checkins/batch-3.md:14450: trailing whitespace.
+  1095	
.oracle/checkins/batch-3.md:14457: trailing whitespace.
+  1102	
.oracle/checkins/batch-3.md:14460: trailing whitespace.
+  1105	
.oracle/checkins/batch-3.md:14684: trailing whitespace.
+     4	
.oracle/checkins/batch-3.md:14717: trailing whitespace.
+   356	
.oracle/checkins/batch-3.md:14718: trailing whitespace.
+   357	
.oracle/checkins/batch-3.md:14721: trailing whitespace.
+   360	
.oracle/checkins/batch-3.md:14724: trailing whitespace.
+   363	
.oracle/checkins/batch-3.md:14735: trailing whitespace.
+   374	
.oracle/checkins/batch-3.md:14766: trailing whitespace.
+   405	
.oracle/checkins/batch-3.md:14772: trailing whitespace.
+   411	
.oracle/checkins/batch-3.md:14779: trailing whitespace.
+   418	
.oracle/checkins/batch-3.md:14788: trailing whitespace.
+   427	
.oracle/checkins/batch-3.md:14815: trailing whitespace.
+   488	
.oracle/checkins/batch-3.md:14816: trailing whitespace.
+   489	
.oracle/checkins/batch-3.md:14825: trailing whitespace.
+   498	
.oracle/checkins/batch-3.md:14826: trailing whitespace.
+   499	
.oracle/checkins/batch-3.md:14831: trailing whitespace.
+   504	
.oracle/checkins/batch-3.md:14834: trailing whitespace.
+   507	
.oracle/checkins/batch-3.md:14851: trailing whitespace.
+   524	
.oracle/checkins/batch-3.md:14852: trailing whitespace.
+   525	
.oracle/checkins/batch-3.md:14856: trailing whitespace.
+   873	
.oracle/checkins/batch-3.md:14865: trailing whitespace.
+   882	
.oracle/checkins/batch-3.md:14866: trailing whitespace.
+   883	
.oracle/checkins/batch-3.md:14869: trailing whitespace.
+   886	
.oracle/checkins/batch-3.md:14871: trailing whitespace.
+   888	
.oracle/checkins/batch-3.md:14872: trailing whitespace.
+   889	
.oracle/checkins/batch-3.md:14879: trailing whitespace.
+   896	
.oracle/checkins/batch-3.md:14885: trailing whitespace.
+   902	
.oracle/checkins/batch-3.md:14886: trailing whitespace.
+   903	
.oracle/checkins/batch-3.md:14892: trailing whitespace.
+   909	
.oracle/checkins/batch-3.md:14895: trailing whitespace.
+   912	
.oracle/checkins/batch-3.md:14900: trailing whitespace.
+   917	
.oracle/checkins/batch-3.md:14902: trailing whitespace.
+   919	
.oracle/checkins/batch-3.md:14907: trailing whitespace.
+   924	
.oracle/checkins/batch-3.md:14973: trailing whitespace.
+   710	
.oracle/checkins/batch-3.md:15055: trailing whitespace.
+  1142	
.oracle/checkins/batch-3.md:15059: trailing whitespace.
+  1146	
.oracle/checkins/batch-3.md:15070: trailing whitespace.
+  1157	
.oracle/checkins/batch-3.md:15077: trailing whitespace.
+  1164	
.oracle/checkins/batch-3.md:15082: trailing whitespace.
+  1169	
.oracle/checkins/batch-3.md:15091: trailing whitespace.
+  1178	
.oracle/checkins/batch-3.md:15119: trailing whitespace.
+  1206	
.oracle/checkins/batch-3.md:15157: trailing whitespace.
+   968	
.oracle/checkins/batch-3.md:15177: trailing whitespace.
+  1087	
.oracle/checkins/batch-3.md:15199: trailing whitespace.
+  1109	
.oracle/checkins/batch-3.md:15215: trailing whitespace.
+  2170	
.oracle/checkins/batch-3.md:15230: trailing whitespace.
+  2185	
.oracle/checkins/batch-3.md:15236: trailing whitespace.
+  2191	
.oracle/checkins/batch-3.md:15244: trailing whitespace.
+  2199	
.oracle/checkins/batch-3.md:15248: trailing whitespace.
+  2203	
.oracle/checkins/batch-3.md:15262: trailing whitespace.
+  2217	
.oracle/checkins/batch-3.md:15265: trailing whitespace.
+  2220	
.oracle/checkins/batch-3.md:15273: trailing whitespace.
+  2228	
.oracle/checkins/batch-3.md:15292: trailing whitespace.
+compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 

codex
The checkout is on the expected branch and has only an untracked oracle note, but `0d2bb176..HEAD` includes a large committed `.oracle/checkins/batch-3.md` transcript whose whitespace makes a whole-diff cleanliness check noisy. I’m isolating the product/test changes and confirming whether `HEAD` is exactly the stated rework commit before judging the blocker fixes.
exec
/bin/zsh -lc "git rev-parse HEAD && git log --oneline --decorate -5 && git show --stat --oneline --no-renames 6e97450a7b75551d30d8e0a48a4e529e4cf15963 && git diff --stat 0d2bb176..6e97450a7b75551d30d8e0a48a4e529e4cf15963 -- . ':(exclude).oracle/**' && git diff --check 0d2bb176..6e97450a7b75551d30d8e0a48a4e529e4cf15963 -- . ':(exclude).oracle/**'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 133ms:
6e97450a megado run2 Batch D+E rework (oracle issues): subgraph boundary links to VibeEdge, emit fails closed on embedded links
 .oracle/checkins/batch-3.md                        | 15391 +++++++++++++++++++
 tests/fixtures/recipes/example_tested_recipe.py    |     9 +-
 .../recipes/example_tested_recipe.py.snapshot.json |     4 +-
 tests/intent/test_static_lowering.py               |     6 +-
 tests/test_cli_misc.py                             |     6 +-
 tests/test_comfy_nodes_agent_backend_spine.py      |    10 +-
 tests/test_finalize_metadata.py                    |     4 +-
 tests/test_foundation_utils.py                     |     1 +
 tests/test_intent_nodes.py                         |     6 +-
 tests/test_porting_synthetic_fixtures.py           |     3 +-
 tests/test_porting_ui_emitter.py                   |   144 +-
 tests/test_testing_assertions.py                   |     2 +-
 tests/test_testing_dry_run.py                      |     2 +-
 tests/test_testing_pytest_plugin.py                |     5 +-
 tests/test_testing_snapshot.py                     |     5 +-
 tests/test_widget_shape_evidence.py                |     1 -
 vibecomfy/_compile/_graph.py                       |    21 +-
 vibecomfy/porting/emit/emit_kwargs.py              |    24 +-
 vibecomfy/porting/emit/emit_subgraph.py            |     8 +-
 vibecomfy/porting/emit/ui.py                       |     4 +-
 20 files changed, 15617 insertions(+), 39 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 tests/fixtures/recipes/example_tested_recipe.py    |   9 +-
 .../recipes/example_tested_recipe.py.snapshot.json |   4 +-
 tests/intent/test_static_lowering.py               |   6 +-
 tests/test_cli_misc.py                             |   6 +-
 tests/test_comfy_nodes_agent_backend_spine.py      |  10 +-
 tests/test_finalize_metadata.py                    |   4 +-
 tests/test_foundation_utils.py                     |   1 +
 tests/test_intent_nodes.py                         |   6 +-
 tests/test_porting_synthetic_fixtures.py           |   3 +-
 tests/test_porting_ui_emitter.py                   | 144 ++++++++++++++++++++-
 tests/test_testing_assertions.py                   |   2 +-
 tests/test_testing_dry_run.py                      |   2 +-
 tests/test_testing_pytest_plugin.py                |   5 +-
 tests/test_testing_snapshot.py                     |   5 +-
 tests/test_widget_shape_evidence.py                |   1 -
 vibecomfy/_compile/_graph.py                       |  21 ++-
 vibecomfy/porting/emit/emit_kwargs.py              |  24 +++-
 vibecomfy/porting/emit/emit_subgraph.py            |   8 +-
 vibecomfy/porting/emit/ui.py                       |   4 +-
 19 files changed, 226 insertions(+), 39 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc "git diff --no-ext-diff --unified=80 0d2bb176..HEAD -- vibecomfy/porting/emit/emit_subgraph.py vibecomfy/porting/emit/ui.py tests/test_porting_ui_emitter.py && rg -n --glob '*.py' 'VibeNode\\(|inputs\\s*=|\\[\\s*[\"'\"']-?[0-9]+[\"'\"']\\s*,\\s*[0-9]+\\s*\\]' vibecomfy/porting/emit/emit_subgraph.py vibecomfy/porting/emit/ui.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 0ms:
zsh:1: unmatched '

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=80 0d2bb176..HEAD -- vibecomfy/porting/emit/emit_subgraph.py vibecomfy/porting/emit/ui.py tests/test_porting_ui_emitter.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 28ms:
diff --git a/tests/test_porting_ui_emitter.py b/tests/test_porting_ui_emitter.py
index c7cc6368..2c85e2fa 100644
--- a/tests/test_porting_ui_emitter.py
+++ b/tests/test_porting_ui_emitter.py
@@ -1,215 +1,357 @@
 """Focused tests for emit_ui_json slot/type resolution, provenance, and strict mode (T5)."""
 from __future__ import annotations
 
 import json
 import sys
 import types
 import warnings
 from typing import Any
 
 import pytest
 
+from vibecomfy._compile._graph import is_canonical_api_link
+from vibecomfy.porting.emitter import _build_subgraph_def, _emit_subgraph_functions
 from vibecomfy.porting.refuse import RefusedEmit
 from vibecomfy.porting.emit.ui import emit_ui_json
 from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
-from vibecomfy.workflow import RawWidgetPayload, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
+from vibecomfy.workflow import (
+    RawWidgetPayload,
+    VibeEdge,
+    VibeNode,
+    VibeWorkflow,
+    WorkflowCompileError,
+    WorkflowSource,
+)
 
 
 # ---------------------------------------------------------------------------
 # Helpers
 # ---------------------------------------------------------------------------
 
 
 def _wf(wf_id: str = "test") -> VibeWorkflow:
     return VibeWorkflow(wf_id, WorkflowSource(wf_id))
 
 
 class _Provider:
     """Minimal schema provider backed by an explicit class→NodeSchema dict."""
 
     def __init__(self, schemas: dict[str, NodeSchema]) -> None:
         self._schemas = schemas
 
     def get_schema(self, class_type: str) -> NodeSchema | None:
         return self._schemas.get(class_type)
 
 
 def _schema(class_type: str, outputs: list[OutputSpec], *, confidence: float = 1.0, provider: str = "node_index") -> NodeSchema:
     return NodeSchema(
         class_type=class_type,
         pack=None,
         inputs={},
         outputs=outputs,
         source_provider=provider,
         confidence=confidence,
     )
 
 
 def _require_comfy_import():
     """Hard-import the installed ComfyUI converter.
 
     When ``VIBECOMFY_COMFY_SMOKE=1`` the oracle gate MUST NOT silently skip
     if the optional dependency is absent — return the converter callable on success or
     raise a loud diagnostic on failure.
     """
     from vibecomfy.comfy_backend import ensure_nodes
 
     ensure_nodes()
     try:
         from comfy.component_model.workflow_convert import convert_ui_to_api  # noqa: F811
     except ImportError as exc:
         raise ImportError(
             f"Cannot import comfy.component_model.workflow_convert. "
             "Install VibeComfy with the pinned [comfy] extra."
         ) from exc
     _install_comfy_nodes_context_stub()
     return convert_ui_to_api
 
 
 def _install_comfy_nodes_context_stub() -> None:
     """Provide Comfy's converter with node INPUT_TYPES from authoring schemas.
 
     ``workflow_convert.convert_ui_to_api`` imports ``comfy.nodes_context`` lazily
     at call time. Booting Comfy's real node workspace drags in runtime packages
     such as torch and OpenTelemetry, but this oracle gate is about the pinned
     converter's graph semantics. A local registry backed by the same object-info
     snapshots used for porting keeps the gate deterministic and focused.
     """
 
     from vibecomfy.schema import get_authoring_schema_provider
     from vibecomfy.schema.provider import InputSpec, NodeSchema
 
     def _entry_for_input(spec: InputSpec):
         opts: dict[str, object] = {}
         if spec.default is not None:
             opts["default"] = spec.default
         if spec.min is not None:
             opts["min"] = spec.min
         if spec.max is not None:
             opts["max"] = spec.max
         if spec.choices is not None:
             return (list(spec.choices), opts)
         return (spec.type or "STRING", opts)
 
     def _class_for_schema(schema: NodeSchema):
         def input_types(schema: NodeSchema = schema):
             required: dict[str, object] = {}
             optional: dict[str, object] = {}
             for name, spec in schema.inputs.items():
                 target = required if spec.required else optional
                 target[name] = _entry_for_input(spec)
             return {"required": required, "optional": optional}
 
         safe_name = "".join(ch if ch.isalnum() else "_" for ch in schema.class_type)
         return type(f"_VibeComfyStub_{safe_name}", (), {"INPUT_TYPES": staticmethod(input_types)})
 
     def get_nodes():
         provider = get_authoring_schema_provider()
         schemas = provider.schemas()
         return {class_type: _class_for_schema(schema) for class_type, schema in schemas.items()}
 
     module = types.ModuleType("comfy.nodes_context")
     module.get_nodes = get_nodes
     sys.modules["comfy.nodes_context"] = module
 
 
 # ---------------------------------------------------------------------------
 # Numeric slot pass-through (from_output is a digit string)
 # ---------------------------------------------------------------------------
 
 
 def test_numeric_from_output_resolves_directly() -> None:
     wf = _wf()
     wf.nodes["1"] = VibeNode("1", "LoadImage")
     wf.nodes["2"] = VibeNode("2", "SaveImage")
     wf.connect("1.0", "2.images")
 
     provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
     result = emit_ui_json(wf, schema_provider=provider)
 
     assert len(result["links"]) == 1
     link = result["links"][0]
     assert link[2] == 0  # from_slot
     assert link[5] == "IMAGE"  # socket type from OutputSpec
 
 
+def test_emit_ui_json_rejects_embedded_api_link_without_edge() -> None:
+    wf = _wf("raw-link")
+    wf.nodes["1"] = VibeNode("1", "Source")
+    wf.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
+
+    with pytest.raises(WorkflowCompileError) as exc_info:
+        emit_ui_json(wf)
+
+    assert exc_info.value.code == "embedded_api_link"
+    assert exc_info.value.detail["edge_collision"] == "none"
+
+
+def test_emit_ui_json_rejects_embedded_subgraph_boundary_link() -> None:
+    wf = _wf("boundary-link")
+    wf.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["-10", 0]})
+
+    with pytest.raises(WorkflowCompileError) as exc_info:
+        emit_ui_json(wf)
+
+    assert exc_info.value.code == "embedded_api_link"
+    assert exc_info.value.detail["embedded_source"] == ["-10", 0]
+
+
+@pytest.mark.parametrize(
+    ("edge", "expected_collision"),
+    [
+        (VibeEdge("1", "0", "2", "image"), "identical"),
+        (VibeEdge("3", "1", "2", "image"), "conflicting"),
+    ],
+)
+def test_emit_ui_json_rejects_embedded_api_link_edge_collision(
+    edge: VibeEdge, expected_collision: str
+) -> None:
+    wf = _wf("raw-link-collision")
+    wf.nodes["1"] = VibeNode("1", "Source")
+    wf.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
+    wf.nodes["3"] = VibeNode("3", "OtherSource")
+    wf.edges.append(edge)
+
+    with pytest.raises(WorkflowCompileError) as exc_info:
+        emit_ui_json(wf)
+
+    assert exc_info.value.code == "embedded_api_link"
+    assert exc_info.value.detail["edge_collision"] == expected_collision
+
+
+def test_emit_ui_json_preserves_edge_only_connectivity() -> None:
+    wf = _wf("edge-only")
+    wf.nodes["1"] = VibeNode("1", "Source")
+    wf.nodes["2"] = VibeNode("2", "Sink")
+    wf.edges.append(VibeEdge("1", "0", "2", "image"))
+
+    result = emit_ui_json(wf)
+
+    assert result["links"] == [[1, 1, 0, 2, 0, ""]]
+    sink = next(node for node in result["nodes"] if node["id"] == 2)
+    assert sink["inputs"] == [{"name": "image", "type": "UNKNOWN", "link": 1}]
+
+
+def test_subgraph_boundary_connectivity_uses_edges_not_node_inputs() -> None:
+    subgraph = _build_subgraph_def(
+        {
+            "id": "sg-boundary",
+            "name": "Boundary",
+            "inputs": [{"name": "switch", "type": "BOOLEAN", "linkIds": [1]}],
+            "outputs": [{"name": "out", "type": "BOOLEAN"}],
+            "nodes": [
+                {
+                    "id": 10,
+                    "type": "LazySwitchKJ",
+                    "inputs": [
+                        {"name": "switch", "link": 1},
+                        {"name": "external", "link": 2},
+                    ],
+                    "outputs": [{"name": "out"}],
+                    "widgets_values": [],
+                }
+            ],
+            "links": [
+                {
+                    "id": 1,
+                    "origin_id": -10,
+                    "origin_slot": 0,
+                    "target_id": 10,
+                    "target_slot": 0,
+                    "type": "BOOLEAN",
+                },
+                {
+                    "id": 2,
+                    "origin_id": 99,
+                    "origin_slot": 0,
+                    "target_id": 10,
+                    "target_slot": 1,
+                    "type": "BOOLEAN",
+                },
+                {
+                    "id": 3,
+                    "origin_id": 10,
+                    "origin_slot": 0,
+                    "target_id": -20,
+                    "target_slot": 0,
+                    "type": "BOOLEAN",
+                },
+            ],
+        },
+        slug="boundary",
+        source_path=None,
+    )
+
+    assert all(
+        not is_canonical_api_link(value)
+        for node in subgraph.nodes.values()
+        for value in node.inputs.values()
+    )
+    assert subgraph.edges_in["10"] == [
+        VibeEdge("-10", "0", "10", "switch"),
+        VibeEdge("-10", "1", "10", "external"),
+    ]
+    assert subgraph.input_refs == {
+        ("10", "switch"): "switch",
+        ("10", "external"): "external",
+    }
+    source = "\n".join(
+        _emit_subgraph_functions(
+            {"subgraph_definitions": {subgraph.id: subgraph}},
+            diagnostics=[],
+            constant_map={},
+        )
+    )
+    assert "external=external" in source
+    assert "switch=switch" in source
+
+
 # ---------------------------------------------------------------------------
 # NAME→slot resolution via OutputSpec list position
 # ---------------------------------------------------------------------------
 
 
 def test_name_from_output_resolves_to_slot_index() -> None:
     """from_output='clip' resolves to slot 1 for a [MODEL, CLIP] outputs list."""
     wf = _wf()
     wf.nodes["1"] = VibeNode("1", "CLIPLoader")
     wf.nodes["2"] = VibeNode("2", "Consumer")
     wf.edges.append(VibeEdge("1", "clip", "2", "clip_in"))
 
     provider = _Provider(
         {
             "CLIPLoader": _schema(
                 "CLIPLoader",
                 [OutputSpec("MODEL", "model"), OutputSpec("CLIP", "clip")],
             )
         }
     )
     result = emit_ui_json(wf, schema_provider=provider)
 
     assert len(result["links"]) == 1
     link = result["links"][0]
     assert link[2] == 1  # slot index = list position of 'clip'
     assert link[5] == "CLIP"  # socket type
 
 
 def test_linked_inputs_and_links_follow_schema_socket_order_not_name_order() -> None:
     """LiteGraph target slots must follow ComfyUI's physical input order.
 
     Alphabetical ordering makes KSampler's ``latent_image`` occupy target slot
     zero and sends MODEL to its positive-conditioning socket.  That payload is
     structurally invalid when the browser applies it to a live ComfyUI graph.
     """
     wf = _wf()
     wf.nodes["model"] = VibeNode("model", "ModelSource")
     wf.nodes["positive"] = VibeNode("positive", "ConditioningSource")
     wf.nodes["negative"] = VibeNode("negative", "ConditioningSource")
     wf.nodes["latent"] = VibeNode("latent", "LatentSource")
     wf.nodes["sampler"] = VibeNode("sampler", "KSampler")
     wf.edges.extend(
         [
             VibeEdge("model", "MODEL", "sampler", "model"),
             VibeEdge("positive", "CONDITIONING", "sampler", "positive"),
             VibeEdge("negative", "CONDITIONING", "sampler", "negative"),
             VibeEdge("latent", "LATENT", "sampler", "latent_image"),
         ]
     )
     provider = _Provider(
         {
             "ModelSource": _schema("ModelSource", [OutputSpec("MODEL", "MODEL")]),
             "ConditioningSource": _schema("ConditioningSource", [OutputSpec("CONDITIONING", "CONDITIONING")]),
             "LatentSource": _schema("LatentSource", [OutputSpec("LATENT", "LATENT")]),
             "KSampler": NodeSchema(
                 class_type="KSampler",
                 pack=None,
                 inputs={
                     "model": InputSpec("MODEL"),
                     "positive": InputSpec("CONDITIONING"),
                     "negative": InputSpec("CONDITIONING"),
                     "latent_image": InputSpec("LATENT"),
                 },
                 outputs=[OutputSpec("LATENT", "LATENT")],
             ),
         }
     )
 
     result = emit_ui_json(wf, schema_provider=provider)
     sampler = next(node for node in result["nodes"] if node["id"] == 5)
 
     assert [entry["name"] for entry in sampler["inputs"]] == [
         "model",
         "positive",
         "negative",
         "latent_image",
     ]
     assert {link[4] for link in result["links"] if link[3] == 5} == {0, 1, 2, 3}
 
 
diff --git a/vibecomfy/porting/emit/emit_subgraph.py b/vibecomfy/porting/emit/emit_subgraph.py
index d438c215..15983986 100644
--- a/vibecomfy/porting/emit/emit_subgraph.py
+++ b/vibecomfy/porting/emit/emit_subgraph.py
@@ -213,208 +213,212 @@ def _disambiguated_subgraph_slugs(raw_by_id: Mapping[str, Mapping[str, Any]]) ->
     slugs: dict[str, str] = {}
     for base, entries in grouped.items():
         if len(entries) == 1:
             slugs[entries[0][0]] = base
             continue
         ordered = sorted(entries, key=lambda item: (len(item[1].get("inputs") or ()), item[0]))
         min_inputs = len(ordered[0][1].get("inputs") or ())
         dual_used = False
         for index, (subgraph_id, raw) in enumerate(ordered):
             if index == 0:
                 slugs[subgraph_id] = base
                 continue
             input_count = len(raw.get("inputs") or ())
             if input_count > min_inputs and not dual_used:
                 slugs[subgraph_id] = f"{base}_dual"
                 dual_used = True
             else:
                 slugs[subgraph_id] = f"{base}_{subgraph_id[:8].lower()}"
     return slugs
 
 
 def _build_subgraph_def(raw: Mapping[str, Any], *, slug: str, source_path: str | None) -> _SubgraphDef:
     from vibecomfy.ingest.normalize import normalize_to_api
     from vibecomfy.identity.uid import make_uid, mint_local_uid
     from vibecomfy.workflow import VibeEdge as _Edge, VibeNode as _Node
 
     subgraph_id = str(raw["id"])
     used_input_names: set[str] = set()
     input_ports: list[_SubgraphPort] = []
     for index, item in enumerate(raw.get("inputs") or ()):
         if not isinstance(item, Mapping):
             continue
         source_name = str(item.get("name") or f"input_{index}")
         emitted_name = _unique_port_name(
             _subgraph_input_kwarg_name(item, fallback=f"input_{index}"),
             used_input_names,
         )
         input_ports.append(
             _SubgraphPort(
                 emitted_name,
                 str(item.get("type") or "") or None,
                 source_name=source_name,
             )
         )
     declared_inputs = tuple(input_ports)
 
     used_output_names: set[str] = set()
     output_ports: list[_SubgraphPort] = []
     for index, item in enumerate(raw.get("outputs") or ()):
         if not isinstance(item, Mapping):
             continue
         source_name = str(item.get("name") or f"output_{index}")
         emitted_name = _unique_port_name(
             _safe_kwarg_name(source_name, fallback=f"output_{index}"),
             used_output_names,
         )
         output_ports.append(
             _SubgraphPort(
                 emitted_name,
                 str(item.get("type") or "") or None,
                 source_name=source_name,
             )
         )
     outputs = tuple(output_ports)
 
     api = normalize_to_api({"nodes": list(raw.get("nodes") or ()), "links": list(raw.get("links") or ())}, use_comfy_converter=False)
     nodes: dict[str, Any] = {}
     edges_in: dict[str, list[Any]] = {}
     input_refs: dict[tuple[str, str], str] = {}
     defaults = _subgraph_default_args(raw, declared_inputs)
 
     for node_id, node in api.items():
         class_type = str(node.get("class_type", "Unknown"))
         if class_type in UI_ONLY_CLASS_TYPES:
             continue
         raw_inputs = dict(node.get("inputs", {}))
         static_inputs: dict[str, Any] = {}
         widgets: dict[str, Any] = {}
         for key, value in raw_inputs.items():
             if _is_any_link(value) and str(value[0]) == "-10":
-                static_inputs[str(key)] = value
                 continue
             if _is_any_link(value):
                 continue
             if str(key).startswith("widget_"):
                 widgets[str(key)] = value
             else:
                 static_inputs[str(key)] = value
         metadata = {key: value for key, value in node.items() if key not in {"class_type", "inputs"}}
         output_names = _ui_output_names(metadata.get("_ui"))
         if output_names:
             metadata.setdefault("output_names", output_names)
         nodes[str(node_id)] = _Node(
             str(node_id),
             class_type,
             inputs=static_inputs,
             widgets=widgets,
             metadata=metadata,
             uid=make_uid(subgraph_id, mint_local_uid(metadata.get("_ui"), str(node_id))),
         )
 
     for node_id, node in api.items():
         if not isinstance(node, Mapping):
             continue
         for key, value in dict(node.get("inputs", {})).items():
             if not _is_any_link(value):
                 continue
             from_node, from_slot = str(value[0]), int(value[1])
             if from_node == "-10":
                 if 0 <= from_slot < len(input_ports):
                     input_refs[(str(node_id), str(key))] = input_ports[from_slot].name
+                    edges_in.setdefault(str(node_id), []).append(
+                        _Edge(from_node, str(from_slot), str(node_id), str(key))
+                    )
             else:
                 if str(node_id) not in nodes:
                     continue
                 if from_node not in nodes:
                     input_name = _unique_port_name(
                         _safe_kwarg_name(str(key), fallback=f"input_{len(input_ports)}"),
                         used_input_names,
                     )
                     input_ports.append(
                         _SubgraphPort(
                             input_name,
                             None,
                             source_name=str(key),
                             external_ref=(from_node, from_slot),
                         )
                     )
-                    nodes[str(node_id)].inputs[str(key)] = ["-10", len(input_ports) - 1]
+                    edges_in.setdefault(str(node_id), []).append(
+                        _Edge("-10", str(len(input_ports) - 1), str(node_id), str(key))
+                    )
                     input_refs[(str(node_id), str(key))] = input_name
                     continue
                 edge = _Edge(from_node, str(from_slot), str(node_id), str(key))
                 edges_in.setdefault(str(node_id), []).append(edge)
 
     inputs = tuple(input_ports)
 
     return_refs: list[tuple[str, int]] = []
     links = [link for link in raw.get("links") or () if isinstance(link, Mapping)]
     for index, _output in enumerate(outputs):
         target = next((link for link in links if str(link.get("target_id")) == "-20" and int(link.get("target_slot", -1)) == index), None)
         if target is not None:
             return_refs.append((str(target.get("origin_id")), int(target.get("origin_slot", 0))))
 
     return _SubgraphDef(
         id=subgraph_id,
         raw_name=str(raw.get("name") or ""),
         slug=slug,
         inputs=inputs,
         outputs=outputs,
         nodes=nodes,
         edges_in=edges_in,
         input_refs=input_refs,
         default_args=defaults,
         return_refs=tuple(return_refs),
         source_hash=subgraph_source_hash(
             raw,
             slug=slug,
             input_names=[port.name for port in inputs],
             return_refs=return_refs,
             runtime_graph=api,
         ),
         source_path=source_path,
     )
 
 
 def subgraph_source_hash(
     raw: Mapping[str, Any],
     *,
     slug: str | None = None,
     input_names: list[str] | None = None,
     return_refs: list[tuple[str, int]] | None = None,
     runtime_graph: Mapping[str, Any] | None = None,
 ) -> str:
     payload = {
         "id": str(raw.get("id") or ""),
         "name": str(raw.get("name") or ""),
         "slug": slug,
         "runtime_graph": runtime_graph or {},
         "inputs": raw.get("inputs") or [],
         "outputs": raw.get("outputs") or [],
         "nodes": raw.get("nodes") or [],
         "links": raw.get("links") or [],
         "emitted_input_names": input_names or [],
         "return_refs": return_refs or [],
     }
     rendered = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))
     return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
 
 
 def _subgraph_default_args(raw: Mapping[str, Any], inputs: tuple[_SubgraphPort, ...]) -> dict[str, Any]:
     nodes = {str(node.get("id")): node for node in raw.get("nodes") or () if isinstance(node, Mapping)}
     links = {int(link.get("id")): link for link in raw.get("links") or () if isinstance(link, Mapping) and link.get("id") is not None}
     defaults: dict[str, Any] = {}
     for index, input_item in enumerate(raw.get("inputs") or ()):
         if not isinstance(input_item, Mapping) or index >= len(inputs):
             continue
         for link_id in input_item.get("linkIds") or ():
             link = links.get(int(link_id))
             if link is None:
                 continue
             node = nodes.get(str(link.get("target_id")))
             if node is None:
                 continue
             value = _widget_default_for_target(node, int(link.get("target_slot", -1)))
             if value is not None:
                 defaults[inputs[index].name] = value
                 break
     return defaults
 
diff --git a/vibecomfy/porting/emit/ui.py b/vibecomfy/porting/emit/ui.py
index 922d1c14..bcaea9d0 100644
--- a/vibecomfy/porting/emit/ui.py
+++ b/vibecomfy/porting/emit/ui.py
@@ -3,161 +3,161 @@
 This is the inverse direction of ingest: ``from_ui`` reads litegraph
 JSON into the ``VibeWorkflow`` IR; :func:`emit_ui_json` renders an IR back out to the
 litegraph shape that the ComfyUI web editor loads. It is a NEW standalone function and
 deliberately NOT a ``VibeWorkflow.compile`` backend — ``compile("api")`` must stay
 byte-for-byte identical and only ever produces the runtime API dict.
 
 Identity preservation is **best-effort**, not lossless:
 
 - ``properties["vibecomfy_uid"]`` is the stable identity key for nodes that carry a uid
   (source-derived nodes ingested from litegraph JSON). Use this for round-trip lookup.
 - ``properties["vibecomfy_id"]`` is a display-only forward label (the emitter's
   variable / role name, ``{class_type}_{order}``). It renumbers on edits and must NEVER
   be used as a match key. Always present as a fallback when uid is absent.
 - ``properties["Node name for S&R"]`` is the litegraph node type, as the editor expects.
 - ``properties["ir_node_id"]`` is **no longer emitted** (demoted in M5). Any stale
   ``ir_node_id`` value from a captured properties blob is scrubbed before emission.
 
 Node ids in the litegraph envelope are integers (the editor format requires it): digit
 VibeNode ids keep their numeric value (``"98"`` → ``98``); non-digit ids are assigned
 fresh integers above the highest digit id. Parity is unaffected because the normalizer
 ``str()``-coerces every node id on read-back. The top-level ``links[]`` are 6-element
 arrays ``[link_id, from_node, from_slot, to_node, to_slot, type]`` over those integer
 ids; ``definitions.subgraphs[].links[]`` (emitted only when the IR carries definitions)
 use the litegraph OBJECT shape. ``SetNode``/``GetNode`` broadcast helpers are resolved
 into direct links via :func:`collect_broadcast_sources` and omitted from ``nodes``.
 
 No promise of lossless preservation is made. The envelope is byte-deterministic for a
 given IR: same IR in → same JSON out. All node geometry is stubbed and isolated in the
 single :func:`_stub_layout` helper, which M2 will replace with real layout; this module
 carries no layout-quality logic of its own.
 
 ``widgets_values`` emission rule (verified empirically against the Comfy oracle)
 -------------------------------------------------------------------------------
 ComfyUI's ``convert_ui_to_api`` reads ``widgets_values`` *positionally* against the
 raw object-info widget order, including ``None``-named UI-only slots such as
 KSampler's ``control_after_generate`` position. Therefore the emitted array is laid
 out against that raw order: named positions take the node's current value, ``None``
 positions preserve the captured source value when available, and seed control slots
 fall back to the documented ``"fixed"`` value. Trailing ``None`` is trimmed.
 
 The retained ``VibeNode.metadata["control_after_generate"]`` — or the documented
 ``"fixed"`` default when absent — is recorded in the recovery report under
 ``control_after_generate`` with a ``control_after_generate_defaulted`` flag.
 
 Input-slot ``widget`` objects: only inputs that are actually LINKED get an entry in the
 node ``inputs`` array; an entry whose name is a widget-type input additionally carries
 ``"widget": {"name": <name>}`` (a widget converted to a link). Unlinked widget-type
 inputs get NO input-slot entry — they live in ``widgets_values``.
 """
 
 from __future__ import annotations
 
 import hashlib
 import json
 import re
 import uuid
 import warnings
 from collections import defaultdict
 from copy import deepcopy
 from pathlib import Path
 from collections.abc import Mapping
 from dataclasses import dataclass
 from typing import Any
 
 from vibecomfy._compile._helpers import (
     broadcast_name,
     collect_broadcast_sources,
     is_broadcast_helper_class_type,
 )
 from vibecomfy.contracts.intent_nodes import (
     CLASS_TYPE_TO_KIND,
     KIND_TO_CLASS_TYPE,
     is_intent_class_type,
     intent_node_payload_from_metadata,
     validate_intent_node_contract,
     validate_runtime_code_contract,
 )
 from vibecomfy.identity.uid import mint_local_uid
 from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
 from vibecomfy.porting.widgets.aliases import widget_names_for_class, widget_names_from_schema
-from vibecomfy.workflow import VibeEdge, VibeNode, _get_node_mode
+from vibecomfy.workflow import VibeEdge, VibeNode, _get_node_mode, _raise_embedded_api_links
 
 # Documented default control_after_generate mode when none is retained in metadata.
 _CONTROL_AFTER_GENERATE_DEFAULT = "fixed"
 
 # Stable namespace so a given workflow id always yields the same envelope id.
 _ENVELOPE_ID_NAMESPACE = uuid.UUID("6f1d2c3a-4b5e-4a6c-8d9e-0f1a2b3c4d5e")
 
 # Litegraph editor format version this emitter targets.
 _LITEGRAPH_VERSION = 1.0
 
 # Layout-schema version stamped into the breadcrumb (extra.vibecomfy.layout_version).
 # M2 replaces _stub_layout with real layout and will bump this. M3 preserve-mode keys
 # off the breadcrumb, so the version travels with the file.
 _LAYOUT_VERSION = "m4"
 
 # Default directory and subdirectory for emitted UI exports.
 _DEFAULT_OUT_DIR = "out"
 _UI_EXPORT_SUBDIR = "ui_export"
 
 # Deterministic grid geometry constants used only by ``_stub_layout``.
 _STUB_COLUMN_WIDTH = 400
 _STUB_ROW_HEIGHT = 200
 _STUB_COLUMNS = 4
 _STUB_NODE_SIZE = [320, 180]
 
 # M2 canonicalization precision (2 decimal places) for all emitted coordinates.
 # Every pos/size/group-bounding value is rounded through this precision so two
 # machines emit byte-identical JSON regardless of CWD, env, or float quirks.
 _M2_PRECISION = 2
 
 # Fixed default canvas drag/scale state for ``extra.ds`` when
 # ``include_main_positions=True`` and no sidecar ``extra`` provides overrides.
 _DEFAULT_DS = {"scale": 1.0, "offset": [0.0, 0.0]}
 
 
 def _intent_recovery_fields(node: Any) -> dict[str, Any]:
     class_type = str(getattr(node, "class_type", ""))
     payload = intent_node_payload_from_metadata(getattr(node, "metadata", None))
     intent_result = validate_intent_node_contract(
         node_id=str(getattr(node, "id", "")),
         class_type=class_type,
         metadata=getattr(node, "metadata", None),
     )
     runtime_result = validate_runtime_code_contract(
         class_type=class_type,
         payload=payload,
         require_runtime=True,
     )
     runtime_backed = (
         class_type == KIND_TO_CLASS_TYPE["code"]
         and intent_result.ok
         and runtime_result.ok
     )
     return {
         "uid": getattr(node, "uid", None) or intent_result.vibecomfy_uid,
         "kind": intent_result.kind or CLASS_TYPE_TO_KIND.get(class_type),
         "lowered": False,
         "runtime_backed": runtime_backed,
         "runtime_contract_valid": runtime_result.ok,
         "intent_contract_valid": intent_result.ok,
         "contract_problem_codes": [
             problem.code for problem in (*intent_result.problems, *runtime_result.problems)
         ],
     }
 
 # Confidence threshold at or below which a node is considered low-confidence.
 # widget_schema_fallback tier uses confidence=0.3; strict=True rejects it.
 _LOW_CONFIDENCE_THRESHOLD = 0.3
 _STATIC_WIDGET_OVERFLOW_TOLERANCE = 4
 _STATIC_RAW_WIDGET_SLACK_CLASSES = frozenset(
     {"CheckpointLoaderSimple", "KSampler", "KSamplerAdvanced"}
 )
 _PRIMITIVE_CONTROL_WIDGET_CLASSES = frozenset(
     {"PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt"}
 )
 
 
 @dataclass(frozen=True, slots=True)
 class WidgetShapeEvidence:
     node_id: str
@@ -2031,160 +2031,162 @@ def derive_widget_shape_evidence(
             if name is not None and name != f"widget_{index}"
         ),
         raw_widget_shape=raw_widget_shape,
         has_dict_rows=has_dict_rows,
         overflow=overflow,
         provider=provenance.get("provider"),
         explicit_widget_overflow=explicit_widget_overflow,
         raw_widget_length_recovered=raw_widget_length_recovered,
         value_domain=value_domain,
     )
 
 
 def emit_ui_json(
     wf: Any,
     *,
     schema_provider: Any = None,
     prior_store: Mapping[str, Any] | None = None,
     layout: Any = None,
     anchors: dict[str, Any] | None = None,
     strict: bool = False,
     recovery_report: list[dict[str, Any]] | None = None,
     source_template: str | None = None,
     prior_path: str | None = None,
     include_main_positions: bool = False,
     include_virtual_wires: bool = True,
     extra: dict[str, Any] | None = None,
     definitions: dict[str, Any] | None = None,
     change_report_out: list | None = None,
     guard_original_ui: Mapping[str, Any] | None = None,
     guard_resolved_ops: Any = None,
     prior_ui_payload: Mapping[str, Any] | None = None,
     force_drop_editor_only: bool = False,
 ) -> dict[str, Any]:
     """Render ``wf`` (a ``VibeWorkflow``) to a litegraph JSON envelope.
 
     Args:
         wf: The IR workflow to emit.
         schema_provider: Schema source used for slot/type resolution.  Consulted
             via ``get_schema(class_type)`` for each node.  Pass ``None`` to skip
             schema resolution (all edges emit with slot 0 and empty type).
         prior_store: Full prior-store envelope (``{entries, groups, extra,
             definitions, virtual_wires}``) from a previously written sidecar.
             ``entries`` (keyed by node uid) feeds the legacy
             ``_resolve_furniture`` precedence chain and is passed as ``pinned``
             to the layout engine.  The full envelope is also handed to
             :func:`reconcile` once at the top of the function; the resulting
             ``ReconcileResult`` is exposed to the per-node loop as a local
             (``reconcile_result``) for later steps (Step 9b+).
         anchors: New-node placement hints ``{new_uid: anchor_uid, ...}``.
             Routed to :func:`~vibecomfy.porting.layout.placement.place_constrained`
             in the engine (Phase 8) as a dedicated kwarg.  Passing ``None`` or
             ``{}`` leaves existing behavior unchanged.
         strict: When ``True``, raises ``ValueError`` if any node has a schema-less
             class type (``get_schema() == None``) or a low-confidence schema
             (``confidence <= 0.3``, i.e. the ``widget_schema_fallback`` tier).
         recovery_report: Optional mutable list.  If provided, one provenance dict
             is appended per node with keys ``node_id``, ``class_type``,
             ``provider``, ``confidence``, ``schema_less``.  This is the
             **authoritative** record of which schema tier supplied each node's
             output/input resolution.
         extra: Optional ``extra`` dict (canvas drag/scale state under ``extra.ds``).
             When provided, merged with the ``vibecomfy`` breadcrumb; otherwise
             only the breadcrumb is emitted.
         definitions: Optional subgraph definitions blob.  When provided from a
             sidecar envelope, used directly instead of re-emitting from IR
             metadata via ``_emit_definitions``.  The caller is responsible for
             passing definitions as they appear in the sidecar's envelope.
         prior_ui_payload: Optional full raw LiteGraph UI JSON used only as raw
             node evidence for future dynamic widget pin/refuse decisions.
             ``prior_store`` remains furniture-only and is not treated as a raw
             node payload source.
 
     Returns:
         A litegraph envelope dict: ``version``, deterministic ``id``,
         ``last_node_id``, ``last_link_id``, ``groups``, ``nodes``, and ``links``.
         Every node carries stamped ``properties`` and stub geometry.  Node outputs
         include ``slot_index``, ``name``, ``type``, and ``links`` (``null`` for
         unwired outputs).  The global ``links`` list holds 6-element arrays
         ``[link_id, from_node, from_slot, to_node, to_slot, type]``.
     """
+    _raise_embedded_api_links(wf, surface="UI serialization")
+
     # T9a: prior_store is the full envelope ({entries, groups, extra, definitions,
     # virtual_wires}); reconcile() is called once at top and the result exposed to
     # the per-node loop as a local. The legacy ``_resolve_furniture`` chain still
     # reads from ``layout`` (= prior_store['entries']) for this batch — Step 9b
     # will replace that precedence chain with ``reconcile_result.matched``.
     from vibecomfy.porting.layout.reconcile import reconcile as _reconcile  # noqa: PLC0415
     _prior_store: dict[str, Any] = dict(prior_store) if prior_store else {}
     raw_ui_node_map = extract_raw_ui_node_map(prior_ui_payload)
     # Back-compat: callers that still pass the flat ``layout=`` kwarg are wrapped
     # into a minimal envelope so reconcile() sees the entries. Step 9b retires
     # ``layout`` entirely once all call sites migrate to prior_store.
     if layout is not None and not _prior_store:
         _prior_store = {"entries": dict(layout) if isinstance(layout, dict) else {}}
     reconcile_result = _reconcile(wf, _prior_store)
     layout = _prior_store.get("entries", {}) or {}
     anchors = anchors or {}
 
     # ── Editor-ahead detection (T3) ───────────────────────────────────────────
     # When guard_original_ui is supplied, detect editor-only uids early (before
     # expensive emission) and raise EditorAheadError so the caller can abort.
     # An editor-only uid is in the prior store, absent from the IR, and NOT in
     # the VibeComfy-authored set.
     #
     # Authored-uid heuristic: if the prior-store breadcrumb's prior_path matches
     # the current workflow's source path, all prior-store uids were authored by a
     # previous VibeComfy emit of this file → treat them all as authored.
     # If no breadcrumb or path mismatch → authored set is EMPTY so every
     # prior-only uid is conservatively flagged as editor-added.
     if guard_original_ui is not None:
         _prior_store_uids: set[str] = set(_prior_store.get("entries", {}).keys())
         _ir_uids: set[str] = set(wf.nodes.keys())
         _prior_breadcrumb: dict = (_prior_store.get("extra") or {}).get("vibecomfy") or {}
         _bc_prior_path = _prior_breadcrumb.get("prior_path")
         _wf_source_path = _source_prior_path(wf)
         if (
             _bc_prior_path is not None
             and _wf_source_path is not None
             and _bc_prior_path == _wf_source_path
         ):
             _vibecomfy_authored: set[str] = set(_prior_store_uids)
         else:
             _vibecomfy_authored = set()
         _editor_only: set[str] = _prior_store_uids - _ir_uids - _vibecomfy_authored
         if _editor_only:
             _entries = _prior_store.get("entries", {})
             if force_drop_editor_only:
                 # Suppress the editor-ahead error: fold editor-only uids into
                 # reconcile_result.removed so build_change_report can populate
                 # removed_named with class_type information.
                 _sorted_editor_only = sorted(_editor_only)
                 reconcile_result.removed.extend(_sorted_editor_only)
             else:
                 from vibecomfy.porting.refuse import EditorAheadError as _EditorAheadError  # noqa: PLC0415
                 raise _EditorAheadError(
                     [
                         {"uid": u, "class_type": _entries.get(u, {}).get("class_type", "")}
                         for u in sorted(_editor_only)
                     ]
                 )
 
     # Build ChangeReport if the caller requested it via change_report_out.
     _change_report_ref: list = []  # mutable container so we can set stripped_helpers later
     if change_report_out is not None:
         from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
         from vibecomfy.porting.layout.reconcile import build_change_report  # noqa: PLC0415
         _snapshot = (wf.metadata or {}).get("_ingest_snapshot", {})
         _field_delta = compute_field_delta(_snapshot, wf) if _snapshot else {}
         _report = build_change_report(
             reconcile_result,
             _field_delta,
             prior_store_entries=_prior_store.get("entries"),
         )
         change_report_out.append(_report)
         _change_report_ref.append(_report)
 
     # ── Resolve broadcast helpers (SetNode / GetNode) into direct edges ────
     # effective_edges: direct links for the EXECUTION (flat) graph
     # broadcast_ids: SetNode/GetNode node ids to drop from flat graph
     # orphaned_get_ids: GetNode ids whose broadcast name has no SetNode source
     effective_edges, broadcast_ids, orphaned_get_ids = _resolve_broadcast_edges(wf)

exec
/bin/zsh -lc "rg -n \"def (is_canonical_api_link|_is_any_link|_raise_embedded_api_links)|is_canonical_api_link|_is_any_link|_raise_embedded_api_links|VibeNode\\(\" vibecomfy/porting/emit/emit_subgraph.py vibecomfy/_compile/_graph.py vibecomfy/workflow.py vibecomfy -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/_compile/_graph.py:22:    boundaries must use :func:`is_canonical_api_link`, whose stricter shape
vibecomfy/_compile/_graph.py:44:def is_canonical_api_link(value: Any) -> bool:
vibecomfy/_compile/_graph.py:83:    "is_canonical_api_link",
vibecomfy/porting/emit/emit_subgraph.py:36:    _is_any_link,
vibecomfy/porting/emit/emit_subgraph.py:292:            if _is_any_link(value) and str(value[0]) == "-10":
vibecomfy/porting/emit/emit_subgraph.py:294:            if _is_any_link(value):
vibecomfy/porting/emit/emit_subgraph.py:317:            if not _is_any_link(value):
vibecomfy/workflow.py:12:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/workflow.py:262:        _raise_embedded_api_links(self, surface="envelope serialization")
vibecomfy/workflow.py:544:        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
vibecomfy/workflow.py:748:        _raise_embedded_api_links(self, surface=f"{backend} compilation")
vibecomfy/workflow.py:1073:            if not is_canonical_api_link(value):
vibecomfy/workflow.py:1108:def _raise_embedded_api_links(workflow: VibeWorkflow, *, surface: str) -> None:
vibecomfy/schema/validate.py:7:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/schema/validate.py:717:    return is_canonical_api_link(value)
vibecomfy/porting/readability_inventory.py:265:    # Also look for VibeNode('<uuid>', ...) patterns
vibecomfy/_compile/_graph.py:22:    boundaries must use :func:`is_canonical_api_link`, whose stricter shape
vibecomfy/_compile/_graph.py:44:def is_canonical_api_link(value: Any) -> bool:
vibecomfy/_compile/_graph.py:83:    "is_canonical_api_link",
vibecomfy/runtime/eval/core.py:248:    preview_node = VibeNode(
vibecomfy/runtime/eval/core.py:300:    decode_node = VibeNode(
vibecomfy/runtime/eval/core.py:315:    preview_node = VibeNode(
vibecomfy/workflow.py:12:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/workflow.py:262:        _raise_embedded_api_links(self, surface="envelope serialization")
vibecomfy/workflow.py:544:        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
vibecomfy/workflow.py:748:        _raise_embedded_api_links(self, surface=f"{backend} compilation")
vibecomfy/workflow.py:1073:            if not is_canonical_api_link(value):
vibecomfy/workflow.py:1108:def _raise_embedded_api_links(workflow: VibeWorkflow, *, surface: str) -> None:
vibecomfy/porting/emit/emit_kwargs.py:33:    "_is_any_link",
vibecomfy/porting/emit/emit_kwargs.py:142:def _is_any_link(value: Any) -> bool:
vibecomfy/porting/emit/emit_kwargs.py:1195:        if _is_any_link(value) and str(value[0]) == "-10":
vibecomfy/porting/emit/emit_kwargs.py:1208:        if _is_any_link(value) and str(value[0]) == "-10":
vibecomfy/ingest/normalize.py:9:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/ingest/normalize.py:598:        workflow.nodes[node_id] = VibeNode(
vibecomfy/ingest/normalize.py:868:            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
vibecomfy/ingest/normalize.py:942:        workflow.nodes[str(node_id)] = VibeNode(
vibecomfy/ingest/normalize.py:964:            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
vibecomfy/porting/emit/emit_subgraph.py:36:    _is_any_link,
vibecomfy/porting/emit/emit_subgraph.py:292:            if _is_any_link(value) and str(value[0]) == "-10":
vibecomfy/porting/emit/emit_subgraph.py:294:            if _is_any_link(value):
vibecomfy/porting/emit/emit_subgraph.py:317:            if not _is_any_link(value):
vibecomfy/porting/reorganise/graph_facts.py:905:        wf.nodes[node_id] = VibeNode(
vibecomfy/porting/emit/ui.py:83:from vibecomfy.workflow import VibeEdge, VibeNode, _get_node_mode, _raise_embedded_api_links
vibecomfy/porting/emit/ui.py:1349:    node = VibeNode(
vibecomfy/porting/emit/ui.py:2111:    _raise_embedded_api_links(wf, surface="UI serialization")
vibecomfy/porting/edit/_resolve.py:1281:        return estimate_node_size(VibeNode(id="__batch__", class_type=class_type, uid="__batch__"), schema)[0]

exec
/bin/zsh -lc "sed -n '1,105p' vibecomfy/_compile/_graph.py && sed -n '120,160p' vibecomfy/porting/emit/emit_kwargs.py && sed -n '1040,1145p' vibecomfy/workflow.py && git diff --unified=40 0d2bb176..HEAD -- vibecomfy/_compile/_graph.py vibecomfy/porting/emit/emit_kwargs.py vibecomfy/workflow.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
from __future__ import annotations

from typing import Any


UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})


def is_api_link(
    value: Any,
    *,
    allow_tuple: bool = False,
    require_string_node_id: bool = False,
    require_numeric_node_id: bool = True,
    allow_negative_node_id: bool = False,
    allow_compound_node_id: bool = False,
    require_int_slot: bool = False,
) -> bool:
    """Return whether ``value`` is a ComfyUI API link pair.

    The defaults retain the legacy configurable helper contract.  IR authority
    boundaries must use :func:`is_canonical_api_link`, whose stricter shape
    keeps ordinary two-item literal lists out of connectivity logic.
    """

    allowed_types = (list, tuple) if allow_tuple else (list,)
    if not (isinstance(value, allowed_types) and len(value) == 2):
        return False

    source_id, slot = value
    if require_string_node_id and not isinstance(source_id, str):
        return False
    if require_numeric_node_id and not _is_numeric_node_id(
        source_id,
        allow_negative=allow_negative_node_id,
        allow_compound=allow_compound_node_id,
    ):
        return False
    if require_int_slot and (isinstance(slot, bool) or not isinstance(slot, int)):
        return False
    return True


def is_canonical_api_link(value: Any) -> bool:
    """Return whether *value* has the canonical stored Comfy API link shape."""
    return is_api_link(
        value,
        allow_tuple=False,
        require_string_node_id=True,
        require_numeric_node_id=True,
        allow_negative_node_id=True,
        require_int_slot=True,
    )


def node_id_sort_key(node_id: Any, *, allow_compound: bool = False) -> tuple[Any, ...]:
    """Sort node ids numerically when possible, with a stable text fallback."""

    text = str(node_id)
    parts = text.split(":") if allow_compound else [text]
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, text)


def _is_numeric_node_id(
    node_id: Any,
    *,
    allow_negative: bool = False,
    allow_compound: bool,
) -> bool:
    parts = str(node_id).split(":") if allow_compound else [str(node_id)]
    return all(
        part.isdigit()
        or (allow_negative and part.startswith("-") and part[1:].isdigit())
        for part in parts
    )


__all__ = [
    "UI_ONLY_CLASS_TYPES",
    "is_api_link",
    "is_canonical_api_link",
    "node_id_sort_key",
]
# UUID pattern (used by _safe_var and _is_single_output_ref)
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Link-type checks
# ---------------------------------------------------------------------------

def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


def _is_any_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[1], int)


def _ui_output_names(ui: Any) -> list[str]:
    if not isinstance(ui, Mapping):
        return []
    names: list[str] = []
    for item in ui.get("outputs") or ():
        if isinstance(item, Mapping):
            names.append(str(item.get("name") or ""))
    return names


# ---------------------------------------------------------------------------
# Variable-name helpers
# ---------------------------------------------------------------------------

def _safe_var(class_type: str) -> str:
        from vibecomfy.schema import get_authoring_schema_provider

        return get_authoring_schema_provider().get_schema(node.class_type)
    except Exception:
        return None


def _compile_node_inputs(node: VibeNode) -> dict[str, Any]:
    inputs = dict(node.widgets)
    inputs.update(node.inputs)
    _apply_positional_widget_aliases(inputs, node)
    _drop_unused_positional_aliases(inputs)
    return {
        key: value
        for key, value in inputs.items()
        if not _is_ui_only_prompt_input(key, value)
    }


def _embedded_api_link_details(workflow: VibeWorkflow) -> list[dict[str, Any]]:
    """Describe canonical API links illegally embedded in IR node inputs."""
    details: list[dict[str, Any]] = []
    edges_by_target: dict[tuple[str, str], list[list[Any]]] = {}
    for edge in workflow.edges:
        key = (str(edge.to_node), str(edge.to_input))
        try:
            output_slot: Any = int(edge.from_output)
        except (TypeError, ValueError):
            output_slot = str(edge.from_output)
        edges_by_target.setdefault(key, []).append([str(edge.from_node), output_slot])

    for node_id, node in workflow.nodes.items():
        for input_name, value in node.inputs.items():
            if not is_canonical_api_link(value):
                continue
            embedded_source = [str(value[0]), int(value[1])]
            edge_sources = edges_by_target.get((str(node_id), str(input_name)), [])
            if not edge_sources:
                collision = "none"
            elif all(source == embedded_source for source in edge_sources):
                collision = "identical"
            else:
                collision = "conflicting"
            details.append(
                {
                    "node_id": str(node_id),
                    "input_name": str(input_name),
                    "embedded_source": embedded_source,
                    "edge_sources": edge_sources,
                    "edge_collision": collision,
                }
            )
    return details


def _embedded_api_link_message(detail: dict[str, Any], *, surface: str) -> str:
    collision = detail["edge_collision"]
    collision_text = ""
    if collision != "none":
        collision_text = f"; the socket also has {collision} VibeEdge connectivity"
    return (
        f"{surface} rejected node {detail['node_id']!r} input "
        f"{detail['input_name']!r}: embedded Comfy API link "
        f"{detail['embedded_source']!r}{collision_text}. "
        "VibeEdge is the sole IR connectivity authority."
    )


def _raise_embedded_api_links(workflow: VibeWorkflow, *, surface: str) -> None:
    details = _embedded_api_link_details(workflow)
    if not details:
        return
    detail = details[0]
    raise WorkflowCompileError(
        "embedded_api_link",
        _embedded_api_link_message(detail, surface=surface),
        detail=detail,
        next_action=(
            "Normalize raw workflows with from_api()/from_ui(), or replace the embedded "
            "pair with a VibeEdge before continuing."
        ),
    )


def _normalize_input_aliases(aliases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if aliases is None:
        return ()
    return tuple(str(alias) for alias in aliases)


def _format_available_names(names: Any) -> str:
    values = sorted(str(name) for name in names)
    return ", ".join(repr(value) for value in values) if values else "<none>"


def _is_ui_only_prompt_input(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key == "control_after_generate":
        return True
    if key == "add_noise_to_samples" and value == "":
        return True
    if key in {"videopreview", "preview", "preview_image"} and isinstance(value, dict):
        return True
    return False

git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/_compile/_graph.py b/vibecomfy/_compile/_graph.py
index ef3e7c07..a53139b2 100644
--- a/vibecomfy/_compile/_graph.py
+++ b/vibecomfy/_compile/_graph.py
@@ -1,70 +1,85 @@
 from __future__ import annotations
 
 from typing import Any
 
 
 UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})
 
 
 def is_api_link(
     value: Any,
     *,
     allow_tuple: bool = False,
     require_string_node_id: bool = False,
     require_numeric_node_id: bool = True,
+    allow_negative_node_id: bool = False,
     allow_compound_node_id: bool = False,
     require_int_slot: bool = False,
 ) -> bool:
     """Return whether ``value`` is a ComfyUI API link pair.
 
     The defaults retain the legacy configurable helper contract.  IR authority
     boundaries must use :func:`is_canonical_api_link`, whose stricter shape
     keeps ordinary two-item literal lists out of connectivity logic.
     """
 
     allowed_types = (list, tuple) if allow_tuple else (list,)
     if not (isinstance(value, allowed_types) and len(value) == 2):
         return False
 
     source_id, slot = value
     if require_string_node_id and not isinstance(source_id, str):
         return False
-    if require_numeric_node_id and not _is_numeric_node_id(source_id, allow_compound=allow_compound_node_id):
+    if require_numeric_node_id and not _is_numeric_node_id(
+        source_id,
+        allow_negative=allow_negative_node_id,
+        allow_compound=allow_compound_node_id,
+    ):
         return False
     if require_int_slot and (isinstance(slot, bool) or not isinstance(slot, int)):
         return False
     return True
 
 
 def is_canonical_api_link(value: Any) -> bool:
     """Return whether *value* has the canonical stored Comfy API link shape."""
     return is_api_link(
         value,
         allow_tuple=False,
         require_string_node_id=True,
         require_numeric_node_id=True,
+        allow_negative_node_id=True,
         require_int_slot=True,
     )
 
 
 def node_id_sort_key(node_id: Any, *, allow_compound: bool = False) -> tuple[Any, ...]:
     """Sort node ids numerically when possible, with a stable text fallback."""
 
     text = str(node_id)
     parts = text.split(":") if allow_compound else [text]
     if all(part.isdigit() for part in parts):
         return tuple(int(part) for part in parts)
     return (1 << 31, text)
 
 
-def _is_numeric_node_id(node_id: Any, *, allow_compound: bool) -> bool:
+def _is_numeric_node_id(
+    node_id: Any,
+    *,
+    allow_negative: bool = False,
+    allow_compound: bool,
+) -> bool:
     parts = str(node_id).split(":") if allow_compound else [str(node_id)]
-    return all(part.isdigit() for part in parts)
+    return all(
+        part.isdigit()
+        or (allow_negative and part.startswith("-") and part[1:].isdigit())
+        for part in parts
+    )
 
 
 __all__ = [
     "UI_ONLY_CLASS_TYPES",
     "is_api_link",
     "is_canonical_api_link",
     "node_id_sort_key",
 ]
diff --git a/vibecomfy/porting/emit/emit_kwargs.py b/vibecomfy/porting/emit/emit_kwargs.py
index 6b7254f1..eb86e169 100644
--- a/vibecomfy/porting/emit/emit_kwargs.py
+++ b/vibecomfy/porting/emit/emit_kwargs.py
@@ -1125,94 +1125,108 @@ def _node_kwargs(
     diagnostics: "list[Any] | None" = None,
     constant_map: dict[tuple[str, str], str] | None = None,
     use_ui_widget_aliases: bool = False,
     strip_schema_defaults: bool = False,
     omit_single_output_metadata: bool = False,
     bare_single_output_refs: bool = False,
     emit_reserved_keyword_args: bool = False,
     preserve_fields: set[str] | None = None,
     external_refs: dict[tuple[str, str], str] | None = None,
 ) -> list[tuple[str, str]]:
     # Lazy imports to avoid circular dependency
     from vibecomfy.porting.emitter import (  # noqa: PLC0415
         RESERVED_WRAPPER_INPUT_NAMES,
         _ui_widget_aliases,
         READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
         EmissionDiagnostic,
     )
 
     cls = node.class_type
     schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
     schema_set = set(schema)
 
     # Per-node widget alias metadata populated by the schema provider during
     # from_api.  Prefer this over the static WIDGET_SCHEMA so
     # that schema-source evidence wins - the static table is only a fallback.
     node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
     input_aliases: list[str | None] | None = None
     compact_names = compact_widget_names_for_node(node, cls).names
     if compact_names:
         input_aliases = list(compact_names)
     elif use_ui_widget_aliases:
         input_aliases = _ui_widget_aliases(node)
 
     if constant_map is None:
         constant_map = {}
     if preserve_fields is None:
         preserve_fields = set()
     if external_refs is None:
         external_refs = {}
 
-    incoming: dict[str, tuple[str, int]] = {}
-    incoming_exprs: dict[str, str] = {}
-    for edge in edges_in.get(node.id, []):
-        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))
-
     def _translate_widget(key: str, value: Any = None) -> str | None:
         if key.startswith("unused_widget_"):
             return None
         if cls == "Power Lora Loader (rgthree)":
             return _translate_power_lora_loader_widget(key, value)
         if not key.startswith("widget_"):
             return key
         return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name
 
+    incoming: dict[str, tuple[str, int]] = {}
+    incoming_exprs: dict[str, str] = {}
+    for edge in edges_in.get(node.id, []):
+        target_name = str(edge.to_input)
+        if str(edge.from_node) == "-10":
+            translated_link = _translate_widget(target_name)
+            if translated_link is not None:
+                expr = external_refs.get(
+                    (str(getattr(node, "id", "")), translated_link)
+                )
+                if expr is None and translated_link != target_name:
+                    expr = external_refs.get(
+                        (str(getattr(node, "id", "")), target_name)
+                    )
+                if expr is not None:
+                    incoming_exprs[translated_link] = expr
+            continue
+        incoming[target_name] = (str(edge.from_node), int(edge.from_output))
+
     raw_inputs: dict[str, Any] = {}
     for key, value in node.inputs.items():
         if _is_any_link(value) and str(value[0]) == "-10":
             translated_link = _translate_widget(key, value)
             if translated_link is not None:
                 expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                 if expr is not None:
                     incoming_exprs[translated_link] = expr
         elif _is_link(value):
             translated_link = _translate_widget(key, value)
             if translated_link is not None:
                 incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
         else:
             raw_inputs[key] = value
     for key, value in node.widgets.items():
         if _is_any_link(value) and str(value[0]) == "-10":
             translated_link = _translate_widget(key, value)
             if translated_link is not None:
                 expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                 if expr is not None:
                     incoming_exprs[translated_link] = expr
         elif _is_link(value):
             translated_link = _translate_widget(key, value)
             if translated_link is not None:
                 incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
         elif key not in raw_inputs:
             raw_inputs[key] = value
 
     static_inputs: dict[str, Any] = {}
     for key, value in raw_inputs.items():
         translated = _translate_widget(key, value)
         if translated is None:
             continue
         value = _resolve_graph_field_get_string(value, workflow_nodes)
         if translated != key and translated not in raw_inputs and translated not in static_inputs:
             if translated not in incoming and translated not in incoming_exprs:
                 static_inputs[translated] = value
             # else: translated name already connected via an edge — drop the shadow widget value
         else:
             static_inputs[key] = value

exec
/bin/zsh -lc "rg -n -U --glob '*.py' '(VibeNode|_Node)\\(["'^'"\\)]{0,500}inputs\\s*=|\\.inputs\\s*\\[["'^'"\\]]+\\]\\s*=|\\.inputs\\s*=|inputs\\s*=\\{["'^'"\\n]*\\[["'^'"\\]]+\\]' vibecomfy | head -300 && rg -n --glob '*.py' '\\[\"-?[0-9]+\",\\s*[0-9]+\\]|\\['\"'\"'-?[0-9]+'\"'\"',\\s*[0-9]+\\]' vibecomfy" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 31ms:
vibecomfy/registry/ready_template.py:265:                builder.node.inputs[key] = value
vibecomfy/templates.py:366:            wf.inputs[alias] = VibeInput(
vibecomfy/runtime/eval/core.py:248:    preview_node = VibeNode(
vibecomfy/runtime/eval/core.py:249:        id=preview_id,
vibecomfy/runtime/eval/core.py:250:        class_type=preview.class_type,
vibecomfy/runtime/eval/core.py:251:        inputs=dict(preview.extra_inputs or {}),
vibecomfy/runtime/eval/core.py:300:    decode_node = VibeNode(
vibecomfy/runtime/eval/core.py:301:        id=decode_id,
vibecomfy/runtime/eval/core.py:302:        class_type="VAEDecode",
vibecomfy/runtime/eval/core.py:303:        inputs={},
vibecomfy/runtime/eval/core.py:315:    preview_node = VibeNode(
vibecomfy/runtime/eval/core.py:316:        id=preview_id,
vibecomfy/runtime/eval/core.py:317:        class_type="PreviewImage",
vibecomfy/runtime/eval/core.py:318:        inputs={},
vibecomfy/_compile/_resolve.py:346:    node.inputs[field_name] = literal
vibecomfy/porting/emit/node_kwargs.py:169:                    node.inputs[new] = node.inputs.pop(old)
vibecomfy/porting/emit/node_kwargs.py:174:                    node.inputs[key] = value
vibecomfy/ingest/normalize.py:598:        workflow.nodes[node_id] = VibeNode(
vibecomfy/ingest/normalize.py:599:            id=node_id,
vibecomfy/ingest/normalize.py:600:            class_type=class_type,
vibecomfy/ingest/normalize.py:601:            pack=pack,
vibecomfy/ingest/normalize.py:602:            inputs=deepcopy(entry["inputs"]),
vibecomfy/ingest/normalize.py:684:        workflow.inputs[str(input_name)] = VibeInput(
vibecomfy/intent/render_diff.py:71:        node.inputs[seed_field] = seed
vibecomfy/intent/render_diff.py:73:            node.inputs[control_field] = "fixed"
vibecomfy/porting/lowering.py:543:            cloned.inputs[target.target_field] = iteration_value
vibecomfy/workflow.py:353:        self.inputs[name] = VibeInput(
vibecomfy/workflow.py:381:            node.inputs[target.field] = value
vibecomfy/workflow.py:544:        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
vibecomfy/workflow.py:568:                node.inputs[key] = value
vibecomfy/workflow.py:655:        self.inputs = {
vibecomfy/porting/reorganise/graph_facts.py:905:        wf.nodes[node_id] = VibeNode(
vibecomfy/porting/reorganise/graph_facts.py:906:            id=node_id,
vibecomfy/porting/reorganise/graph_facts.py:907:            class_type=fact.class_type,
vibecomfy/porting/reorganise/graph_facts.py:908:            inputs=_workflow_inputs(raw_node),
vibecomfy/porting/emit/emit_ready.py:1530:                    node.inputs[new] = node.inputs.pop(old)
vibecomfy/porting/emit/emit_ready.py:1535:                    node.inputs[key] = value
vibecomfy/porting/emit/emit_ready.py:1732:                builder.node.inputs[key] = value
vibecomfy/patches/save_prefix.py:19:                node.inputs["filename_prefix"] = value
vibecomfy/patches/gguf_unet.py:25:                node.inputs["unet_name"] = GGUF_MODEL
vibecomfy/patches/gguf_unet.py:33:                node.inputs["vae_name"] = "flux2-vae.safetensors"
vibecomfy/patches/ltx_lowvram.py:51:        node.inputs = {"ckpt_name": FP8_CHECKPOINT}
vibecomfy/patches/ltx_lowvram.py:56:        node.inputs = {"ckpt_name": FP8_CHECKPOINT}
vibecomfy/patches/ltx_lowvram.py:156:            node.inputs[key] = value
vibecomfy/patches/ltx_lowvram.py:166:        node.inputs = {"sampler_name": PORTABLE_SAMPLER}
vibecomfy/patches/ltx_lowvram.py:198:        node.inputs["skip_blocks"] = node.inputs.pop("widget_0", node.widgets.pop("widget_0", "28"))
vibecomfy/metadata.py:77:            workflow.inputs["prompt"] = VibeInput("prompt", node_id, field, value)
vibecomfy/metadata.py:84:            workflow.inputs["seed"] = VibeInput("seed", node_id, field, value)
vibecomfy/metadata.py:92:            workflow.inputs["steps"] = VibeInput("steps", node_id, field, value)
vibecomfy/metadata.py:94:            workflow.inputs["model"] = VibeInput("model", node_id, field, value)

exec
/bin/zsh -lc "sed -n '540,625p' vibecomfy/ingest/normalize.py && sed -n '915,985p' vibecomfy/ingest/normalize.py && sed -n '520,580p' vibecomfy/workflow.py && sed -n '880,925p' vibecomfy/porting/reorganise/graph_facts.py && sed -n '1325,1365p' vibecomfy/porting/emit/ui.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
            raise ValueError(f"node {node_id!r}: pack must be a string or null")
        for field_name in ("inputs", "widgets", "metadata"):
            value = entry.get(field_name)
            if not isinstance(value, dict):
                raise ValueError(f"node {node_id!r}: {field_name} must be a mapping")
        raw_widgets = entry.get("raw_widgets")
        raw_widget_payload: RawWidgetPayload | None = None
        if raw_widgets is not None:
            if not isinstance(raw_widgets, dict) or not {
                "values",
                "shape",
                "source",
                "has_dict_rows",
                "length",
            } <= set(raw_widgets):
                raise ValueError(
                    f"node {node_id!r}: raw_widgets must be a RawWidgetPayload mapping or null"
                )
            length = raw_widgets["length"]
            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.length must be a nonnegative integer"
                )
            shape = raw_widgets["shape"]
            source_name = raw_widgets["source"]
            has_dict_rows = raw_widgets["has_dict_rows"]
            if not isinstance(shape, str) or not shape.strip():
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.shape must be a nonblank string"
                )
            if not isinstance(source_name, str) or not source_name.strip():
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.source must be a nonblank string"
                )
            if not isinstance(has_dict_rows, bool):
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.has_dict_rows must be a boolean"
                )
            raw_widget_payload = RawWidgetPayload(
                values=deepcopy(raw_widgets["values"]),
                shape=shape,
                source=source_name,
                has_dict_rows=has_dict_rows,
                length=length,
            )
        node_metadata = deepcopy(entry["metadata"])
        # S4 capability fence: ingest is the external-JSON boundary, so every
        # decoded node is tagged untrusted_source. Unconditional set — never
        # `setdefault` — so hostile JSON cannot pre-declare itself trusted.
        node_metadata[PROVENANCE_KEY] = "untrusted_source"
        # Mode is first-class: prefer the serialized node-level ``mode`` field
        # (written by to_envelope's dataclass walk), falling back to the legacy
        # ``_ui.mode`` / ``metadata["mode"]`` locations for old envelopes.
        # ``_ui`` stays verbatim so the emitter's furniture keeps re-emitting it.
        entry_mode = entry.get("mode")
        node_mode = (
            entry_mode if isinstance(entry_mode, int) else _node_mode_from_metadata(node_metadata)
        )
        workflow.nodes[node_id] = VibeNode(
            id=node_id,
            class_type=class_type,
            pack=pack,
            inputs=deepcopy(entry["inputs"]),
            widgets=deepcopy(entry["widgets"]),
            metadata=node_metadata,
            uid=uid,
            raw_widgets=raw_widget_payload,
            mode=node_mode,
        )

    # ── edges ──────────────────────────────────────────────────────────────
    edges_raw = raw.get("edges")
    if not isinstance(edges_raw, list):
        raise ValueError("serialized vibe envelope 'edges' must be a list")
    for index, edge in enumerate(edges_raw):
        if not isinstance(edge, dict):
            raise ValueError(
                f"edge {index}: edge entries must be mappings, got {type(edge).__name__}"
            )
        for field_name in ("from_node", "from_output", "to_node", "to_input"):
            value = edge.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"edge {index}: {field_name} must be a nonblank string")
        if edge["from_node"] not in workflow.nodes or edge["to_node"] not in workflow.nodes:
            raise ValueError(
                f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
            # The _ui dict may alias the input API node's _ui (pure-Python path);
            # deepcopy so the caller's node dict is never corrupted.
            # Only assign when a real _ui was present — do not invent {}.
            _ui_node = deepcopy(_ui_raw)
            metadata["_ui"] = _ui_node
            for _vis_field in ("flags", "color", "bgcolor"):
                if _vis_field in _ui_node:
                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
        # ── enrich node metadata from schema ──
        output_names = _schema_output_names(schema_provider, class_type)
        if output_names:
            metadata.setdefault("output_names", output_names)
        output_types = _schema_output_types(schema_provider, class_type)
        if output_types:
            metadata.setdefault("output_types", output_types)
        input_aliases = _schema_input_aliases(schema_provider, class_type)
        if input_aliases:
            metadata.setdefault("input_aliases", input_aliases)
        schema_source = _schema_source_provenance(schema_provider, class_type)
        if schema_source is not None:
            metadata.setdefault("schema_source", schema_source)
        if class_type == EXEC_CLASS_TYPE:
            _rebuild_exec_reload_metadata(metadata, widgets.get("io"))
        # S4 capability fence: ingest is the external-JSON boundary, so every
        # ingested node is tagged untrusted_source. Unconditional set — never
        # `setdefault` — so a hostile JSON cannot pre-declare itself trusted.
        metadata[PROVENANCE_KEY] = "untrusted_source"
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_id),
            class_type=class_type,
            inputs=inputs,
            widgets=widgets,
            metadata=metadata,
            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
            raw_widgets=raw_widgets,
            mode=_node_mode_from_metadata(metadata),
        )
        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))

    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        input_provenance = node.get("_input_provenance")
        if not isinstance(input_provenance, dict):
            input_provenance = {}
        for name, value in dict(node.get("inputs", {})).items():
            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))

    workflow.requirements = _infer_requirements(workflow)

    # Stash an ingest-time snapshot immediately after uid minting and edge setup.
    # Captured once here so downstream delta computation can detect edits.
    from vibecomfy.ingest.snapshot import capture_ingest_snapshot  # local to avoid circular at module level
    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(api_workflow, workflow)

    # ``workflow.metadata`` is ``dict[str, Any]`` and transparently accepts
    # any extra keys.  In particular, ``summary`` (a ``WorkflowSummary`` dict)
    # may be present when re-ingesting a corpus JSON that was enriched with
    # LLM-generated summaries.  It is left untouched here — no validation,
    # no stripping — so it survives round-trips through this pipeline intact.
    return workflow


def _is_exec_widget_key(class_type: str, key: str) -> bool:
    return class_type == EXEC_CLASS_TYPE and key in {"source", "io"}


        # compile path at ``_compile_graphbuilder`` below (GraphBuilder.node
        # from ``comfy_execution.graph_utils``) is INTENTIONALLY NOT gated —
        # gating happens at edit-time, not at compile-time. By the time a
        # workflow compiles, every node has already passed this gate (or was
        # tagged trusted by its authoring path).
        if is_side_effecting(class_type):
            caps = capabilities_for(class_type)
            risky = {
                k: v
                for k, v in inputs.items()
                if not isinstance(v, Handle) and k != "_provenance"
            }
            require_confirmation(
                operation="add_node",
                class_type=class_type,
                provenance=effective,
                capabilities=caps,
                details={"params": risky},
                ctx=current_gate_context(),
            )

        node_id = str(_id) if _id is not None else self._next_node_id()
        if node_id in self.nodes:
            raise ValueError(f"Node id {node_id!r} already exists in workflow {self.id!r}")
        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
        if uid is not None:
            node.uid = uid
        _tag_provenance(node, effective)
        # Defensive: ensure the reserved kwarg never leaked into inputs.
        node.inputs.pop("_provenance", None)
        self.nodes[node_id] = node
        return node

    def node(self, class_type: str, **kwargs: Any) -> "_NodeBuilder":
        pass_raw = bool(kwargs.pop("pass_raw", False))
        explicit_id = kwargs.pop("_id", None)
        explicit_provenance = kwargs.pop("_provenance", None)
        from vibecomfy.templates import coerce_node_kwargs

        kwargs = coerce_node_kwargs(self, class_type, kwargs, pass_raw=pass_raw)
        node = self.add_node(class_type, _id=explicit_id, _provenance=explicit_provenance)
        # Mint extrinsic uid: seed from explicit id when provided, else creation order.
        seed = f"id:{explicit_id}" if explicit_id is not None else None
        node.uid = self._mint_uid(seed=seed)
        for key, value in kwargs.items():
            if isinstance(value, Handle):
                self.connect(value, f"{node.id}.{key}")
            else:
                node.inputs[key] = value
        return _NodeBuilder(workflow=self, node=node)

    def _parse_source_ref(self, ref: str | Handle, *, operation: str) -> tuple[str, str, Handle | None]:
        if isinstance(ref, Handle):
            return str(ref.node_id), str(ref.output_slot), ref
        if not isinstance(ref, str):
            raise ValueError(f"{operation}: source ref must be a Handle or string, got {type(ref).__name__}")
        if not ref:
            raise ValueError(f"{operation}: source ref must not be empty")
        if "." not in ref:
            return ref, "0", None
        node_id, output_slot = ref.split(".", 1)
) -> dict[str, tuple[CanonicalRefFact, ...]]:
    rows: dict[str, list[CanonicalRefFact]] = {}
    for fact in canonical_refs:
        rows.setdefault(fact.ref.scope_path, []).append(fact)
    return {scope: tuple(facts) for scope, facts in rows.items()}


def _topology_adapter(
    scope_path: str,
    scope: ScopeState,
    node_facts: Sequence[CanonicalRefFact],
) -> _ScopeTopologyAdapter:
    id_to_ref: dict[str, CanonicalNodeRef] = {}
    id_to_node: dict[str, Mapping[str, Any]] = {}
    wf = VibeWorkflow(id=f"reorganise:{scope_path or 'root'}", source=WorkflowSource(id="reorganise"))
    for fact in node_facts:
        if fact.litegraph_id is None:
            continue
        node_id = str(fact.litegraph_id)
        node = scope.graph.get("nodes")
        raw_node = _node_by_id(node, fact.litegraph_id)
        if raw_node is None:
            continue
        id_to_ref[node_id] = fact.ref
        id_to_node[node_id] = raw_node
        wf.nodes[node_id] = VibeNode(
            id=node_id,
            class_type=fact.class_type,
            inputs=_workflow_inputs(raw_node),
            widgets=_workflow_widgets(raw_node),
            uid=fact.ref.uid,
        )

    raw_edges = tuple(
        edge
        for edge in _raw_edges(scope.graph)
        if edge.from_node in id_to_ref and edge.to_node in id_to_ref
    )
    wf.edges = [
        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        for edge in raw_edges
    ]
    return _ScopeTopologyAdapter(
        scope_path=scope_path,
        workflow=wf,
        id_to_ref=id_to_ref,
    node_id: int,
    uid: str,
    pos: list[float] | tuple[float, float],
) -> dict[str, Any]:
    """Materialize one unlinked LiteGraph node using emitter-equivalent defaults.

    This is the creation-path substrate helper for agent-edit v2. It deliberately
    reuses the same widget ordering, property stamping, size defaults, and output
    slot construction that :func:`emit_ui_json` uses for a single node.
    """
    merged_fields: dict[str, Any] = {}
    schema_inputs = getattr(schema, "inputs", None)
    if isinstance(schema_inputs, dict):
        for name, spec in schema_inputs.items():
            default = getattr(spec, "default", None)
            if default is not None:
                merged_fields[name] = deepcopy(default)
    merged_fields.update(dict(fields))

    metadata: dict[str, Any] = {}
    retained_control = merged_fields.pop("control_after_generate", None)
    if isinstance(retained_control, str):
        metadata["control_after_generate"] = retained_control

    node = VibeNode(
        id=str(node_id),
        class_type=class_type,
        inputs=merged_fields,
        metadata=metadata,
        uid=uid,
    )
    geometry = {
        "pos": [
            _canonicalize_coord(float(pos[0])),
            _canonicalize_coord(float(pos[1])),
        ],
        "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
    }
    furniture = _resolve_furniture(node, None)
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = _schema_outputs_for_unwired_node(schema)

exec
/bin/zsh -lc "sed -n '820,950p' vibecomfy/ingest/normalize.py && sed -n '625,700p' vibecomfy/ingest/normalize.py && rg -n \"def _workflow_inputs\" vibecomfy/porting/reorganise/graph_facts.py && sed -n '830,880p' vibecomfy/porting/reorganise/graph_facts.py && git show --format=fuller --no-patch 6e97450a" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
        return from_ui(
            raw,
            source_path=source_path,
            workflow_id=workflow_id,
            schema_provider=schema_provider,
            use_comfy_converter=use_comfy_converter,
            comfy_converter_strict=comfy_converter_strict,
        )
    api = normalize_to_api(
        raw,
        schema_provider=schema_provider,
        use_comfy_converter=use_comfy_converter,
        comfy_converter_strict=comfy_converter_strict,
    )
    return from_api(
        api,
        source_path=source_path,
        workflow_id=workflow_id,
        schema_provider=schema_provider,
    )


def _from_api_impl(
    api_workflow: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
) -> VibeWorkflow:
    """Ingest a Comfy prompt dict. Caller holds :func:`untrusted_scope`."""
    _enforce_exec_source_limits(api_workflow, surface="api.ingest")
    source = WorkflowSource(
        id=workflow_id or (Path(source_path).stem if source_path else "workflow"),
        path=source_path,
        source_type="api",
    )
    workflow = VibeWorkflow(id=source.id, source=source)
    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        raw_inputs = dict(node.get("inputs", {}))
        input_provenance = node.get("_input_provenance")
        if not isinstance(input_provenance, dict):
            input_provenance = {}
        inputs: dict[str, Any] = {}
        widgets: dict[str, Any] = {}
        class_type = str(node.get("class_type", "Unknown"))
        for key, value in raw_inputs.items():
            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
                continue
            if key.startswith("widget_") or _is_exec_widget_key(class_type, key):
                widgets[key] = value
            else:
                inputs[key] = value
        raw_widgets = _coerce_raw_widget_payload(
            node.get("_raw_widgets", node.get("raw_widgets"))
        )
        if raw_widgets is None:
            raw_ui = node.get("_ui")
            if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
                raw_widgets = _coerce_raw_widget_payload(
                    _raw_widget_payload_dict(raw_ui["widgets_values"], source="ui.widgets_values")
                )
        metadata = {
            key: value
            for key, value in node.items()
            if key
            not in {
                "class_type",
                "inputs",
                "_raw_widgets",
                "raw_widgets",
                "_input_provenance",
            }
        }
        # ── retain control_after_generate (UI-only) into metadata ──
        # Captured here, before the compile-time `_is_ui_only_prompt_input` filter
        # (workflow.py:471) drops it from the compiled API dict, so the emitter can
        # re-render it. Metadata-only: it never re-enters `inputs`/`widgets`, so
        # `compile("api")` stays byte-for-byte identical. Never guessed — when no
        # recognized control token is present, metadata stays unset and the emitter
        # emits the documented `fixed` default itself.
        control_value = _capture_control_after_generate(node, class_type)
        if control_value is not None:
            metadata.setdefault("control_after_generate", control_value)
        # ── retain flags/color/bgcolor from _ui into top-level metadata ──
        # Both paths: pure-Python path stores the full raw node in _ui (line 99);
        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
        # Captured as metadata DATA only — never enters inputs/widgets (K3 invariant).
        # mode is first-class on VibeNode (the compile mute/bypass signal): the
        # field is populated below from `_ui.mode` (fallback metadata["mode"]) and
        # `_ui.mode` is LEFT IN PLACE so emit_ui_json's furniture keeps re-emitting
        # it.  No duplicate metadata["mode"] is written on new ingests.
        _ui_raw = metadata.get("_ui")
        if isinstance(_ui_raw, dict):
            # The _ui dict may alias the input API node's _ui (pure-Python path);
            # deepcopy so the caller's node dict is never corrupted.
            # Only assign when a real _ui was present — do not invent {}.
            _ui_node = deepcopy(_ui_raw)
            metadata["_ui"] = _ui_node
            for _vis_field in ("flags", "color", "bgcolor"):
                if _vis_field in _ui_node:
                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
        # ── enrich node metadata from schema ──
        output_names = _schema_output_names(schema_provider, class_type)
        if output_names:
            metadata.setdefault("output_names", output_names)
        output_types = _schema_output_types(schema_provider, class_type)
        if output_types:
            metadata.setdefault("output_types", output_types)
        input_aliases = _schema_input_aliases(schema_provider, class_type)
        if input_aliases:
            metadata.setdefault("input_aliases", input_aliases)
        schema_source = _schema_source_provenance(schema_provider, class_type)
        if schema_source is not None:
            metadata.setdefault("schema_source", schema_source)
        if class_type == EXEC_CLASS_TYPE:
            _rebuild_exec_reload_metadata(metadata, widgets.get("io"))
        # S4 capability fence: ingest is the external-JSON boundary, so every
        # ingested node is tagged untrusted_source. Unconditional set — never
        # `setdefault` — so a hostile JSON cannot pre-declare itself trusted.
        metadata[PROVENANCE_KEY] = "untrusted_source"
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_id),
            class_type=class_type,
            inputs=inputs,
            widgets=widgets,
            metadata=metadata,
            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
            raw_widgets=raw_widgets,
            mode=_node_mode_from_metadata(metadata),
                f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
                "must exist in nodes"
            )
        workflow.edges.append(
            VibeEdge(
                from_node=edge["from_node"],
                from_output=edge["from_output"],
                to_node=edge["to_node"],
                to_input=edge["to_input"],
            )
        )

    # ── top-level inputs / outputs ─────────────────────────────────────────
    embedded_links = _embedded_api_link_details(workflow)
    if embedded_links:
        raise ValueError(
            "embedded_api_link: "
            + _embedded_api_link_message(
                embedded_links[0], surface="serialized vibe envelope decode"
            )
        )

    inputs_raw = raw.get("inputs")
    if not isinstance(inputs_raw, dict):
        raise ValueError("serialized vibe envelope 'inputs' must be a mapping")
    for name, entry in inputs_raw.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"input {name!r}: input entries must be mappings, got {type(entry).__name__}"
            )
        input_name = entry.get("name")
        node_id = entry.get("node_id")
        field = entry.get("field")
        if not isinstance(input_name, str) or not input_name.strip():
            raise ValueError(f"input {name!r}: name must be a nonblank string")
        if str(name) != input_name:
            raise ValueError(
                f"input mapping key {name!r} must equal input.name {input_name!r}"
            )
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"input {name!r}: node_id must be a nonblank string")
        if node_id not in workflow.nodes:
            raise ValueError(f"input {name!r}: node_id {node_id!r} must exist in nodes")
        if not isinstance(field, str) or not field.strip():
            raise ValueError(f"input {name!r}: field must be a nonblank string")
        required = entry.get("required", False)
        if not isinstance(required, bool):
            raise ValueError(f"input {name!r}: required must be a boolean")
        aliases = entry.get("aliases", ())
        if not isinstance(aliases, (list, tuple)) or not all(
            isinstance(alias, str) for alias in aliases
        ):
            raise ValueError(f"input {name!r}: aliases must be a list of strings")
        media_semantics = entry.get("media_semantics")
        if media_semantics is not None and not isinstance(media_semantics, str):
            raise ValueError(f"input {name!r}: media_semantics must be a string or null")
        input_type = entry.get("type")
        if input_type is not None and not isinstance(input_type, str):
            raise ValueError(f"input {name!r}: type must be a string or null")
        workflow.inputs[str(input_name)] = VibeInput(
            name=str(input_name),
            node_id=str(node_id),
            field=str(field),
            value=deepcopy(entry.get("value")),
            type=input_type,
            default=deepcopy(entry.get("default")),
            required=required,
            range=deepcopy(entry.get("range")),
            aliases=tuple(aliases),
            media_semantics=media_semantics,
        )

    outputs_raw = raw.get("outputs")
    if not isinstance(outputs_raw, list):
        raise ValueError("serialized vibe envelope 'outputs' must be a list")
    for index, entry in enumerate(outputs_raw):
950:def _workflow_inputs(node: Mapping[str, Any]) -> dict[str, Any]:
            key=lambda uid: uid.zfill(20),
        )
        ordered_roots = sorted(set(scc_raw_roots.get(uid, uid) for uid in all_uids), key=lambda uid: uid.zfill(20))
        root_to_scc_id = {root: f"scc{index}" for index, root in enumerate(ordered_roots)}
        scc_by_uid = {uid: root_to_scc_id.get(scc_raw_roots.get(uid, uid), "scc0") for uid in all_uids}
        # Tag effective edges whose endpoints share an SCC as feedback
        id_to_uid = {node.id: node.uid for node in adapter.workflow.nodes.values()}
        effective_edges = tuple(
            _edge_fact(
                adapter,
                edge,
                passthrough=True,
                feedback=_edge_is_feedback(edge, id_to_uid, scc_by_uid),
            )
            for edge in effective_raw_edges
        )
        wcc_by_uid = _wcc_ids(lanes)
        node_topology = tuple(
            _node_topology_fact(
                adapter,
                node,
                layers,
                lanes,
                fan_in,
                fan_out,
                scc_by_uid,
                wcc_by_uid,
            )
            for node in _sorted_workflow_nodes(adapter.workflow)
        )
        terminal_paths, paths_truncated = _terminal_paths(adapter, adjacency, reverse_adjacency)
        parallel_candidates = tuple(_parallel_branch_candidates(adapter, adjacency))
        sampler_candidates = tuple(_sampler_relation_candidates(adapter, adjacency, scc_by_uid, wcc_by_uid))
        topologies.append(
            ScopeTopologyFacts(
                scope_path=scope_path,
                raw_edges=raw_edges,
                effective_edges=effective_edges,
                node_topology=node_topology,
                terminal_paths=terminal_paths,
                parallel_branch_candidates=parallel_candidates,
                sampler_relation_candidates=sampler_candidates,
                truncated=paths_truncated,
            )
        )
    return topologies


def _canonical_facts_by_scope(
    canonical_refs: Sequence[CanonicalRefFact],
) -> dict[str, tuple[CanonicalRefFact, ...]]:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 6e97450a7b75551d30d8e0a48a4e529e4cf15963
Author:     POM <peter@omalley.io>
AuthorDate: Thu Aug 13 21:56:01 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Thu Aug 13 21:56:01 2026 +0200

    megado run2 Batch D+E rework (oracle issues): subgraph boundary links to VibeEdge, emit fails closed on embedded links

exec
/bin/zsh -lc "sed -n '940,980p' vibecomfy/porting/reorganise/graph_facts.py && git diff --name-status 0d2bb176..HEAD -- . ':(exclude).oracle/**' && git diff --numstat 0d2bb176..HEAD -- tests/test_porting_ui_emitter.py vibecomfy/porting/emit/emit_subgraph.py vibecomfy/porting/emit/ui.py vibecomfy/_compile/_graph.py vibecomfy/porting/emit/emit_kwargs.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:

def _node_by_id(raw_nodes: Any, node_id: Any) -> Mapping[str, Any] | None:
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, (str, bytes)):
        return None
    for node in raw_nodes:
        if isinstance(node, Mapping) and str(node.get("id")) == str(node_id):
            return node
    return None


def _workflow_inputs(node: Mapping[str, Any]) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    raw_inputs = node.get("inputs")
    if isinstance(raw_inputs, Mapping):
        inputs.update({str(key): value for key, value in raw_inputs.items()})
    elif isinstance(raw_inputs, Sequence) and not isinstance(raw_inputs, (str, bytes)):
        for index, slot in enumerate(raw_inputs):
            if not isinstance(slot, Mapping):
                continue
            name = slot.get("name")
            if name is not None:
                inputs[str(name)] = slot.get("link")
            inputs[f"slot_{index}"] = slot.get("link")
    return inputs


def _workflow_widgets(node: Mapping[str, Any]) -> dict[str, Any]:
    widgets: dict[str, Any] = {}
    values = node.get("widgets_values")
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        for index, value in enumerate(values):
            widgets[f"widget_{index}"] = value
    elif isinstance(values, Mapping):
        widgets.update({str(key): value for key, value in values.items()})
    raw_widgets = node.get("widgets")
    if isinstance(raw_widgets, Mapping):
        widgets.update({str(key): value for key, value in raw_widgets.items()})
    return widgets


def _raw_edges(graph: Mapping[str, Any]) -> list[_RawEdge]:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	tests/fixtures/recipes/example_tested_recipe.py
M	tests/fixtures/recipes/example_tested_recipe.py.snapshot.json
M	tests/intent/test_static_lowering.py
M	tests/test_cli_misc.py
M	tests/test_comfy_nodes_agent_backend_spine.py
M	tests/test_finalize_metadata.py
M	tests/test_foundation_utils.py
M	tests/test_intent_nodes.py
M	tests/test_porting_synthetic_fixtures.py
M	tests/test_porting_ui_emitter.py
M	tests/test_testing_assertions.py
M	tests/test_testing_dry_run.py
M	tests/test_testing_pytest_plugin.py
M	tests/test_testing_snapshot.py
M	tests/test_widget_shape_evidence.py
M	vibecomfy/_compile/_graph.py
M	vibecomfy/porting/emit/emit_kwargs.py
M	vibecomfy/porting/emit/emit_subgraph.py
M	vibecomfy/porting/emit/ui.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
143	1	tests/test_porting_ui_emitter.py
18	3	vibecomfy/_compile/_graph.py
19	5	vibecomfy/porting/emit/emit_kwargs.py
6	2	vibecomfy/porting/emit/emit_subgraph.py
3	1	vibecomfy/porting/emit/ui.py

codex
The code path now strips both declared `-10` boundary links and inferred external links from node inputs, records them in `edges_in`, and the canonical-link predicate now accepts negative numeric IDs. The UI guard is invoked before any emission/reconciliation. I’m running the six regression cases directly and then a narrow surrounding suite to check edge-only behavior and false-positive risk.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -q tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_api_link_without_edge tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_subgraph_boundary_link tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_api_link_edge_collision tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity tests/test_porting_ui_emitter.py::test_subgraph_boundary_connectivity_uses_edges_not_node_inputs' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 1606ms:
Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/bin/pytest", line 6, in <module>
    sys.exit(console_main())
             ^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
           ^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1186, in pytest_cmdline_parse
    self.parse(args)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1556, in parse
    self.hook.pytest_load_initial_conftests(
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 628, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 127, in _sanitize_params
    dir = gettempdir()
          ^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 316, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 309, in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2']

codex
The first test invocation was blocked before collection because this read-only sandbox has no writable temporary directory; it did not expose a code failure. I’ll retry without pytest’s file-backed capture and keep cache/bytecode writes disabled.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -s -p no:cacheprovider -q tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_api_link_without_edge tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_subgraph_boundary_link tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_api_link_edge_collision tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity tests/test_porting_ui_emitter.py::test_subgraph_boundary_connectivity_uses_edges_not_node_inputs' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 4842ms:
.OMP: Warning #179: Function Can't set size of /tmp file failed:
.....
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:197: UserWarning: emit_ui_json: schema-less node 1(Source); emitting best-effort slots. Pass strict=True to hard-fail.
    result = emit_ui_json(wf)

tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:197: UserWarning: emit_ui_json: schema-less node 2(Sink); emitting best-effort slots. Pass strict=True to hard-fail.
    result = emit_ui_json(wf)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
6 passed, 3 warnings in 2.23s

exec
/bin/zsh -lc 'rg -n -C 3 "116 passed|blocker-regression|link or edge or collision|6 blocker" .oracle tests vibecomfy | head -200' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 73ms:
.oracle/checkins/batch-3-rev.md-22-1. emit_subgraph.py:292,340 stored ["-10", slot] boundary links in real VibeNode.inputs; narrow predicate missed negative ids.
.oracle/checkins/batch-3-rev.md-23-2. emit_ui_json (ui.py:2043) silently emitted links=[] for VibeNode(inputs={"image": ["1",0]}) instead of failing closed.
.oracle/checkins/batch-3-rev.md-24-
.oracle/checkins/batch-3-rev.md:25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.
.oracle/checkins/batch-3-rev.md-26-
.oracle/checkins/batch-3-rev.md-27-## Your verdict
.oracle/checkins/batch-3-rev.md-28-Binary PASS or concrete issues. Specifically verify:
.oracle/checkins/batch-3-rev.md-29-1. No remaining package-owned construction stores ANY link pair (incl. negative boundary ids) in VibeNode.inputs — grep emit_subgraph.py + the predicate.
.oracle/checkins/batch-3-rev.md-30-2. emit_ui_json now raises (targeted error) on raw-link-only inputs and raw-link-plus-edge collisions; canonical edge-only emit unchanged.
.oracle/checkins/batch-3-rev.md:31:3. The 6 blocker-regression tests exist and are meaningful (not tautological).
.oracle/checkins/batch-3-rev.md-32-Do NOT edit. Read-only.
.oracle/checkins/batch-3-rev.md-33-warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
.oracle/checkins/batch-3-rev.md-34-codex

exec
/bin/zsh -lc "git diff --no-ext-diff --unified=25 0d2bb176..HEAD -- . ':(exclude).oracle/**' ':(exclude)tests/test_porting_ui_emitter.py' ':(exclude)vibecomfy/porting/emit/emit_subgraph.py' ':(exclude)vibecomfy/porting/emit/ui.py' ':(exclude)vibecomfy/_compile/_graph.py' ':(exclude)vibecomfy/porting/emit/emit_kwargs.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 5ms:
e:
     assert is_api_link([1, 0])
     assert is_api_link(["1", 0])
     assert is_api_link(["1", "slot"])
 
 
 def test_canonical_api_link_requires_json_string_id_and_integer_slot() -> None:
     assert is_canonical_api_link(["1", 0])
+    assert is_canonical_api_link(["-10", 0])
     assert not is_canonical_api_link([1, 0])
     assert not is_canonical_api_link(["1", "0"])
     assert not is_canonical_api_link(["1", False])
     assert not is_canonical_api_link([640, 480])
 
 
 def test_is_api_link_rejects_bad_shapes() -> None:
     assert not is_api_link(None)
     assert not is_api_link({"node": "1", "slot": 0})
     assert not is_api_link(["1"])
     assert not is_api_link(["1", 0, "extra"])
     assert not is_api_link(["abc", 0])
     assert not is_api_link(["", 0])
 
 
 def test_is_api_link_can_allow_tuple_links() -> None:
     assert not is_api_link(("1", 0))
     assert is_api_link(("1", 0), allow_tuple=True)
 
 
 def test_is_api_link_can_preserve_schema_style_string_source_ids() -> None:
     assert is_api_link(
         ("source_node", 0),
         allow_tuple=True,
         require_string_node_id=True,
diff --git a/tests/test_intent_nodes.py b/tests/test_intent_nodes.py
index 6dabb644..68f6f968 100644
--- a/tests/test_intent_nodes.py
+++ b/tests/test_intent_nodes.py
@@ -1,51 +1,51 @@
 from __future__ import annotations
 
 import pytest
 
 from vibecomfy.contracts import (
     INTENT_CODE_MAX_BYTES,
     INTENT_LOOP_MAX_ITERATIONS,
     INTENT_NODE_CONTRACT_INVALID_CODE,
     INTENT_NODE_EDITOR_ONLY_CODE,
     RUNTIME_CODE_CONTRACT_VERSION,
     RUNTIME_CODE_EXECUTION_MODE,
     RUNTIME_CODE_POLICY_VERSION,
     intent_node_payload_from_metadata,
     intent_node_properties,
     intent_node_properties_from_metadata,
     is_intent_class_type,
     validate_intent_node_contract,
     validate_runtime_code_contract,
 )
 from vibecomfy.contracts.intent_nodes import INTENT_SPEC_MAX_BYTES
 from vibecomfy.contracts.validation import comfyui_node_issue_specs
 from vibecomfy.ingest.normalize import from_ui
 from vibecomfy.porting.emit.ui import emit_ui_json
 from vibecomfy.schema.provider import NodeSchema, schema_for
 from vibecomfy.schema.validate import sanitize_api_against_schema, validate_api_against_schema
-from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
+from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
 
 
 def _metadata(properties: dict[str, object]) -> dict[str, object]:
     return {"_ui": {"properties": properties}}
 
 
 def _runtime_contract(**overrides: object) -> dict[str, object]:
     contract: dict[str, object] = {
         "runtime_backed": True,
         "runtime_contract_version": RUNTIME_CODE_CONTRACT_VERSION,
         "execution_mode": RUNTIME_CODE_EXECUTION_MODE,
         "timeout_ms": 1000,
         "max_source_bytes": INTENT_CODE_MAX_BYTES,
         "allowed_builtins": ["abs", "len", "min", "max", "round"],
         "redaction_policy": ["source_hash_only", "closed_set_redaction"],
         "policy_version": RUNTIME_CODE_POLICY_VERSION,
         "passthrough_on_non_json": False,
     }
     contract.update(overrides)
     return contract
 
 
 def test_intent_node_properties_builds_programmatic_properties_blob() -> None:
     properties = intent_node_properties(
         kind="code",
@@ -768,55 +768,55 @@ def test_exec_node_registered_and_not_intent() -> None:
         assert input_types["optional"][f"in_{i}"] == ("*",)
 
     # --- execute path: declared outputs padded to fixed arity ---------------
     instance = VibeComfyExec()
     result = instance.execute(
         source="return {'result': value + 1}",
         io={"inputs": [["value", "INT"]], "outputs": [["result", "INT"]]},
         in_0=41,
         in_5="ignored",
     )
     assert result == (42,) + tuple([None] * (EXEC_SLOT_COUNT - 1))
     assert len(result) == EXEC_SLOT_COUNT
 
     # --- execute path: empty body defaults to empty dict / padded outputs ---
     result_empty = instance.execute(io={"outputs": []})
     assert result_empty == tuple([None] * EXEC_SLOT_COUNT)
 
 
 def test_exec_node_survives_compile_api() -> None:
     from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
 
     workflow = VibeWorkflow("exec-compile", WorkflowSource("exec-compile"))
     workflow.nodes["10"] = VibeNode(
         "10",
         "vibecomfy.exec",
-        inputs={"in_0": ["20", 0], "source": "return 42"},
+        inputs={"source": "return 42"},
         widgets={"io": {}},
     )
     workflow.nodes["20"] = VibeNode("20", "CheckpointLoaderSimple", inputs={"ckpt_name": "model.safetensors"})
-    workflow.edges = []
+    workflow.edges.append(VibeEdge("20", "0", "10", "in_0"))
 
     compiled = workflow.compile("api")
 
     assert "10" in compiled
     assert compiled["10"]["class_type"] == "vibecomfy.exec"
     assert compiled["10"]["inputs"] == {"in_0": ["20", 0], "source": "return 42", "io": {}}
 
 
 def test_exec_node_has_builtin_schema_and_widget_aliases() -> None:
     from vibecomfy._compile._widgets import WIDGET_SCHEMA
     from vibecomfy.schema.provider import schema_for
 
     schema = schema_for(None, "vibecomfy.exec")
 
     assert schema is not None
     assert schema.source_provider == "vibecomfy_builtin"
     assert list(schema.inputs)[:2] == ["source", "io"]
     assert {f"in_{index}" for index in range(16)} <= set(schema.inputs)
     assert [output.name for output in schema.outputs] == [f"out_{index}" for index in range(16)]
     assert WIDGET_SCHEMA["vibecomfy.exec"] == ["source", "io"]
 
 
 def test_runtime_code_executor_returns_json_result_from_child_process() -> None:
     from vibecomfy.comfy_nodes.agent.runtime_code import execute_runtime_code
 
diff --git a/tests/test_porting_synthetic_fixtures.py b/tests/test_porting_synthetic_fixtures.py
index a68f0d98..aa5fd020 100644
--- a/tests/test_porting_synthetic_fixtures.py
+++ b/tests/test_porting_synthetic_fixtures.py
@@ -292,39 +292,40 @@ def test_agent_edit_safety_add_delete_add(tmp_path: Path):
     assert pos_new != [0, 0], "New node must not inherit deleted node's position"
 
 
 # ---------------------------------------------------------------------------
 # T15.6: mode:2 mute-parity — compile('api') byte-identical
 # ---------------------------------------------------------------------------
 
 
 def test_mode2_mute_compile_parity():
     """A mode:2 (muted) node compiles byte-identically to the same node without mode.
 
     mode is metadata DATA only and must never enter compile('api') (K3).
     """
     import json
 
     def _build_wf_with_mode(mode: int | None) -> VibeWorkflow:
         wf = _wf("mute-test")
         metadata: dict = {
             "_ui": {"pos": [0, 0], "size": [300, 100]},
         }
         if mode is not None:
             metadata["mode"] = mode
         n = VibeNode("1", "KSampler", inputs={"seed": 42, "steps": 20}, metadata=metadata)
         n.uid = "mute-node"
         wf.nodes["1"] = n
-        n2 = VibeNode("2", "SaveImage", inputs={"images": ["1", 0]}, metadata={})
+        n2 = VibeNode("2", "SaveImage", metadata={})
         n2.uid = "save-node"
         wf.nodes["2"] = n2
+        wf.edges.append(VibeEdge("1", "0", "2", "images"))
         return wf
 
     wf_normal = _build_wf_with_mode(None)
     wf_muted = _build_wf_with_mode(2)
 
     api_normal = wf_normal.compile("api")
     api_muted = wf_muted.compile("api")
 
     assert json.dumps(api_normal, sort_keys=True) == json.dumps(api_muted, sort_keys=True), (
         "compile('api') must be byte-identical regardless of mode:2 (K3 mute-parity)"
     )
diff --git a/tests/test_testing_assertions.py b/tests/test_testing_assertions.py
index ccfe0954..6c3c5092 100644
--- a/tests/test_testing_assertions.py
+++ b/tests/test_testing_assertions.py
@@ -1,46 +1,46 @@
 """Tests for vibecomfy.testing.assertions (T5)."""
 from __future__ import annotations
 
 import pytest
 
 from vibecomfy.testing import (
     assert_compiles_cleanly,
     assert_edge,
     assert_input_value,
     assert_node_present,
     assert_no_dangling_handles,
     assert_output_kind,
 )
 from vibecomfy.testing.fixtures import make_workflow_factory
 from vibecomfy.workflow import VibeEdge, VibeNode
 
 
 def _basic_wf():
     wf = make_workflow_factory()(id="basic")
     wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "x.safetensors"})
-    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"images": ["1", 0], "filename_prefix": "out"})
+    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"filename_prefix": "out"})
     wf.edges.append(VibeEdge(from_node="1", from_output=0, to_node="2", to_input="images"))
     return wf
 
 
 def test_assert_node_present_positive():
     wf = _basic_wf()
     assert_node_present(wf, "SaveImage", count=1)
 
 
 def test_assert_node_present_negative_count():
     wf = _basic_wf()
     with pytest.raises(AssertionError) as exc:
         assert_node_present(wf, "SaveImage", count=2)
     assert wf.id in str(exc.value)
 
 
 def test_assert_edge_positive():
     wf = _basic_wf()
     assert_edge(wf, "1", "2", to_input="images")
 
 
 def test_assert_edge_negative_missing():
     wf = _basic_wf()
     with pytest.raises(AssertionError):
         assert_edge(wf, "1", "2", to_input="latent")
diff --git a/tests/test_testing_dry_run.py b/tests/test_testing_dry_run.py
index e993fa7a..b47a7da2 100644
--- a/tests/test_testing_dry_run.py
+++ b/tests/test_testing_dry_run.py
@@ -1,38 +1,38 @@
 """Tests for vibecomfy.testing.dry_run (T5)."""
 from __future__ import annotations
 
 import sys
 
 from vibecomfy.testing import dry_run
 from vibecomfy.testing.fixtures import make_workflow_factory
 from vibecomfy.workflow import VibeEdge, VibeNode
 
 
 def _simple_wf():
     wf = make_workflow_factory()(id="dryrun")
     wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "x.safetensors"})
-    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"images": ["1", 0], "filename_prefix": "out"})
+    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"filename_prefix": "out"})
     wf.edges.append(VibeEdge(from_node="1", from_output=0, to_node="2", to_input="images"))
     return wf
 
 
 def test_dry_run_returns_result_with_invocations():
     wf = _simple_wf()
     result = dry_run(wf)
     class_types = {r.class_type for r in result.would_invoke}
     assert "CheckpointLoaderSimple" in class_types
     assert "SaveImage" in class_types
 
 
 def test_importing_dry_run_does_not_pull_runtime_at_import_time():
     """Import-time contract: just importing the dry_run module must not load runtime.client/server."""
     import subprocess
     code = (
         "from vibecomfy.testing.dry_run import dry_run; "
         "import sys; "
         "forbidden = {'vibecomfy.runtime.client', 'vibecomfy.runtime.server'}; "
         "loaded = forbidden & set(sys.modules); "
         "assert not loaded, sorted(loaded)"
     )
     r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
     assert r.returncode == 0, r.stderr
diff --git a/tests/test_testing_pytest_plugin.py b/tests/test_testing_pytest_plugin.py
index f8183bea..430fbb08 100644
--- a/tests/test_testing_pytest_plugin.py
+++ b/tests/test_testing_pytest_plugin.py
@@ -1,29 +1,30 @@
 """Tests for the pytest-vibecomfy plugin (T10)."""
 from __future__ import annotations
 
 
 def test_plugin_collects_test_workflow_file(pytester):
     pytester.makepyfile(
         test_workflow_demo="""
-from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
+from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
 
 def test_compiles_cleanly():
     wf = VibeWorkflow(id='plugin-demo', source=WorkflowSource(id='plugin-demo'))
     wf.nodes['1'] = VibeNode(id='1', class_type='CheckpointLoaderSimple', inputs={'ckpt_name': 'x.safetensors'})
-    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'images': ['1', 0], 'filename_prefix': 'out'})
+    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'filename_prefix': 'out'})
+    wf.edges.append(VibeEdge(from_node='1', from_output=0, to_node='2', to_input='images'))
     return wf
 """
     )
     result = pytester.runpytest("-q", "--tb=short")
     result.assert_outcomes(passed=1)
 
 
 def test_plain_test_functions_in_workflow_files_still_run(pytester):
     pytester.makepyfile(
         test_workflow_mixed="""
 def test_just_arithmetic():
     assert 1 + 1 == 2
 """
     )
     result = pytester.runpytest("-q")
     result.assert_outcomes(passed=1)
diff --git a/tests/test_testing_snapshot.py b/tests/test_testing_snapshot.py
index c98c36ff..418b840d 100644
--- a/tests/test_testing_snapshot.py
+++ b/tests/test_testing_snapshot.py
@@ -1,52 +1,53 @@
 """Tests for snapshot canonicalization + CLI round-trip (T8)."""
 from __future__ import annotations
 
 import subprocess
 import sys
 from pathlib import Path
 
 import pytest
 
 from vibecomfy.testing.fixtures import make_workflow_factory
 from vibecomfy.testing.snapshot import canonicalize_api
 from vibecomfy.workflow import VibeNode
 
 
 REPO_ROOT = Path(__file__).resolve().parents[1]
 
 
 def _tiny_recipe(tmp_path: Path) -> Path:
     p = tmp_path / "tiny_recipe.py"
     p.write_text(
         """
-from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
+from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
 
 def build():
     wf = VibeWorkflow(id='tiny', source=WorkflowSource(id='tiny'))
     wf.nodes['1'] = VibeNode(id='1', class_type='CheckpointLoaderSimple', inputs={'ckpt_name': 'x.safetensors'})
-    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'images': ['1', 0], 'filename_prefix': 'out'})
+    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'filename_prefix': 'out'})
+    wf.edges.append(VibeEdge(from_node='1', from_output=0, to_node='2', to_input='images'))
     return wf
 """.lstrip(),
         encoding='utf-8',
     )
     return p
 
 
 def test_regenerate_snapshots_check_exits_zero():
     """The committed snapshot baselines stay in sync with the regenerator."""
     result = subprocess.run(
         [sys.executable, "-m", "tools.regenerate_snapshots", "--check"],
         capture_output=True,
         text=True,
         cwd=str(REPO_ROOT),
         timeout=120,
     )
     assert result.returncode == 0, result.stdout + result.stderr
 
 
 def test_vibecomfy_test_verify_recipes_passes():
     result = subprocess.run(
         [sys.executable, "-m", "vibecomfy.cli", "test", "verify", str(REPO_ROOT / "tests" / "fixtures" / "recipes"), "--json"],
         capture_output=True,
         text=True,
         cwd=str(REPO_ROOT),
diff --git a/tests/test_widget_shape_evidence.py b/tests/test_widget_shape_evidence.py
index af4489a3..2ce57550 100644
--- a/tests/test_widget_shape_evidence.py
+++ b/tests/test_widget_shape_evidence.py
@@ -130,51 +130,50 @@ def test_programmatic_widget_overflow_uses_candidate_count_without_raw_payload()
         widgets={"widget_0": "a", "widget_1": "b", "widget_2": "c"},
     )
     provider = _Provider(
         {
             "ProgrammaticOverflow": _schema(
                 "ProgrammaticOverflow",
                 {"value": InputSpec("STRING")},
             )
         }
     )
 
     evidence = _evidence(node, provider)
 
     assert evidence.raw_widget_count is None
     assert evidence.raw_widget_shape is None
     assert evidence.candidate_widget_count == 3
     assert evidence.schema_widget_count == 1
     assert evidence.has_dict_rows is False
     assert evidence.overflow is True
 
 
 def test_showtext_pysssss_two_widget_shape_is_committed_schema_backed() -> None:
     node = VibeNode(
         "180",
         "ShowText|pysssss",
-        inputs={"text": ["179", 0]},
         widgets={"widget_1": ""},
     )
     provider = _Provider(
         {
             "ShowText|pysssss": _schema(
                 "ShowText|pysssss",
                 {"text": InputSpec("STRING")},
             )
         }
     )
 
     evidence = _evidence(node, provider)
 
     assert evidence.schema_less is False
     assert evidence.raw_widget_count is None
     assert evidence.candidate_widget_count == 2
     assert evidence.schema_widget_count == 2
     assert evidence.compacted_widget_names == ("text",)
     assert evidence.overflow is False
 
 
 def test_primitive_int_control_after_generate_metadata_adds_ui_slot() -> None:
     from vibecomfy.porting.object_info.consume import object_info_widget_order
     from vibecomfy.porting.object_info.consume import CACHE_DIR
     from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

exec
/bin/zsh -lc "rg -n -F 'mode_authority or group or emit' .oracle/checkins/batch-3.md .oracle/checkins/batch-3-rev.md | tail -20 && rg -n -F '116 passed' .oracle/checkins/batch-3.md | tail -20" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
.oracle/checkins/batch-3-rev.md:25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.
.oracle/checkins/batch-3-rev.md:9034:.oracle/checkins/batch-3-rev.md:25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.

exec
/bin/zsh -lc 'rg -n "pytest .*test_porting_ui_emitter|test_porting_ui_emitter.py .*test_|pytest -k" .oracle/checkins/batch-3.md | tail -80' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
10079:/bin/zsh -lc 'git diff --unified=60 8a8300bb..0d2bb176 -- tests/test_workflow_core.py tests/test_schema_validate.py tests/test_foundation_utils.py tests/test_patches.py tests/test_porting_normalize_ingest.py tests/test_porting_synthetic_fixtures.py tests/test_porting_ui_emitter.py tests/test_layout_store.py tests/test_ui_layout.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
10978:diff --git a/tests/test_porting_ui_emitter.py b/tests/test_porting_ui_emitter.py
13426:/bin/zsh -lc 'rg -n "embedded_api_link|raw_link|edge_only|collision|canonical.*round|literal.*list|mode_authority|group_member|source.*UID|uid.*group" tests/test_workflow_core.py tests/test_schema_validate.py tests/test_porting_ui_emitter.py tests/test_ui_layout.py tests/test_porting_normalize_ingest.py tests/test_foundation_utils.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
13453:/bin/zsh -lc "nl -ba tests/test_workflow_core.py | sed -n '45,200p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '2180,2325p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '2325,2375p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
14218:/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_foundation_utils.py tests/test_layout_store.py tests/test_patches.py tests/test_porting_normalize_ingest.py tests/test_porting_synthetic_fixtures.py tests/test_porting_ui_emitter.py tests/test_schema_validate.py tests/test_ui_layout.py tests/test_workflow_core.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
14297:/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_from_api_normalizes_links_into_edges tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
14306:/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_workflow_mutation_and_export_round_trip tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
14331:/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_api_workflow_converts_to_vibe_workflow tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
14679:/bin/zsh -lc "nl -ba tests/quarantine/emitter_parity_surface.txt | sed -n '1,30p' && nl -ba tests/conftest.py | sed -n '350,455p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '480,525p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '870,925p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2

exec
/bin/zsh -lc "sed -n '1,120p' .oracle/checkins/batch-3-rev.md && rg -n \"116 passed|3 skipped|8 quarantined|6 passed\" .oracle/checkins/batch-3-rev.md | head -40" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
Reading additional input from stdin...
2026-08-13T19:56:11.115879Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:56:11.115941Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:56:11.115956Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffcb2-47b0-7872-8696-b494c1a7506f
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 3 RESUBMISSION — Batch D+E task-6 rework review.

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Batch D+E commit 0d2bb176 (tasks 1-5 already PASS in your prior review). Rework commit: 6e97450a7b75551d30d8e0a48a4e529e4cf15963. Review `git diff 0d2bb176..HEAD`.

Your prior FAIL had two blockers (both now claimed fixed):
1. emit_subgraph.py:292,340 stored ["-10", slot] boundary links in real VibeNode.inputs; narrow predicate missed negative ids.
2. emit_ui_json (ui.py:2043) silently emitted links=[] for VibeNode(inputs={"image": ["1",0]}) instead of failing closed.

Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.

## Your verdict
Binary PASS or concrete issues. Specifically verify:
1. No remaining package-owned construction stores ANY link pair (incl. negative boundary ids) in VibeNode.inputs — grep emit_subgraph.py + the predicate.
2. emit_ui_json now raises (targeted error) on raw-link-only inputs and raw-link-plus-edge collisions; canonical edge-only emit unchanged.
3. The 6 blocker-regression tests exist and are meaningful (not tautological).
Do NOT edit. Read-only.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill to follow the oracle checkpoint protocol, then I’ll inspect only the rework diff, relevant constructors/predicate, and the six claimed regression tests. No files will be changed.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. GPT-5.6 Sol plans and revises, DeepSeek V4 Flash explores and executes, a GPT-5.6 Sol or Grok 4.6 oracle gates each batch. The oracle and [XHARD] tasks are managers/validators that delegate to Flash via OMP. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

Plan → explore → revise → execute → oracle-gate → sync, all in a worktree, never on main.

- **Planner** — GPT-5.6 Sol (codex exec, high reasoning): tasklist, revision, batch design.
- **Explorer / Executor** — DeepSeek V4 Flash: all exploration and normal execution.
- **Oracle** — GPT-5.6 Sol or Grok 4.6 (grok CLI): gates every batch; rework until it passes.
- **`[XHARD]` tasks** — GPT-5.6 Sol: extremely hard tasks, tagged in the tasklist.

One orchestrator (the host) drives all phases, holds the `.oracle/` artifacts, and writes every brief. Escalate Flash exploration to DeepSeek V4 Pro only on evidence that Flash's findings are thin.

## Roles

| Role | Model | Invocation | Sandbox |
| --- | --- | --- | --- |
| **Planner** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | read-only |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Oracle** | GPT-5.6 Sol or Grok 4.6 | codex as Planner · `grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high` | danger-full-access\* |
| **`[XHARD]` executor** | GPT-5.6 Sol | codex as Planner | danger-full-access\* |

\* `danger-full-access` because the mandate requires delegating to Flash via OMP, which needs outbound network. `read-only` / `--permission-mode plan` / `workspace-write` only for pure non-delegating work — planning, a review that dispatches nothing, or a task that genuinely cannot be delegated.

## Delegation mandate — verbatim in every oracle check-in brief and `[XHARD]` task brief

> DELEGATION MANDATE — You are a manager and validator of DeepSeek V4 Flash, NOT a worker. Use Flash via OMP for as much of this work as possible: `omp -p @<brief>.md --model deepseek-v4-flash --cwd <worktree> --no-session --auto-approve --max-time=1800` (research-only briefs: add `--tools read,glob,grep,web_search`). Dispatch research, execution, and critique briefs to Flash — critique passes optimize for elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag overengineering, not just bugs. Your job is to direct, then validate: read Flash's output against the acceptance criteria; do work yourself only when delegation is impossible — Flash already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off. If you catch yourself implementing or researching directly, stop and ask whether a Flash brief would cover it. It almost always would.

## Artifacts (in the worktree)

```
.oracle/
  plan.md            # living plan, revised until stable
  briefs/            # one brief per explorer / executor batch
  findings/          # explorer outputs: <area>.txt (+ .meta.json from fan.py)
  tasklist.md        # frozen batched task list with checkpoints + [XHARD] tags
  checkins/          # oracle verdicts: batch-<N>.md
  status.md          # current phase, batch, checkpoint state
```

## Phase 0 — Worktree

```bash
git worktree add ../<project>-oracle -b oracle-run
cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins
```

## Phase 1 — Plan (Codex, read-only)

Brief Sol: (1) a tasklist covering the **entirety** of the project, (2) **additional areas to explore** for full clarity, (3) open questions. The brief is a spec, not a memo. Save the result as `.oracle/plan.md` (host writes it; Codex stays read-only).

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/plan-brief.md)" </dev/null > /tmp/plan-v1.txt 2>&1
```

## Phase 2 — Explore (DeepSeek fan-out)

One Flash agent per area, in parallel. `fan.py` for ≥ ~5 areas; `launch_hermes_agent.py` per area below that. Each brief: "Explore area X in depth. Report verified facts with file/line evidence, unknowns, risks, and a suggested approach. Ranked findings, <300 words." Mechanical briefs — no license to architect.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
```

## Phase 3 — Revise until STABLE (Codex, read-only)

Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Sol:

> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

New material areas → re-run Phase 2 for them, then revise again. Repeat until `STABLE` (or two consecutive rounds with no material change).

## Phase 4 — Tasklist (Codex, read-only)

25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.
9026:6 passed, 3 warnings in 2.23s
9029:/bin/zsh -lc 'rg -n -C 3 "116 passed|blocker-regression|link or edge or collision|6 blocker" .oracle tests vibecomfy | head -200' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
9034:.oracle/checkins/batch-3-rev.md:25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.
9494:/bin/zsh -lc "rg -n -F 'mode_authority or group or emit' .oracle/checkins/batch-3.md .oracle/checkins/batch-3-rev.md | tail -20 && rg -n -F '116 passed' .oracle/checkins/batch-3.md | tail -20" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
9496:.oracle/checkins/batch-3-rev.md:25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.
9497:.oracle/checkins/batch-3-rev.md:9034:.oracle/checkins/batch-3-rev.md:25:Claimed rework (codex): subgraph boundary links now VibeEdge with -10 predicate covered; UI emit raises on raw links and collisions; edge-only unchanged. Verification run: pytest -k "link or edge or collision or subgraph or mode_authority or group or emit" on 4 files → 116 passed, 3 skipped, 8 quarantined baseline, 6 blocker-regression tests passed; git diff --check clean.

exec
/bin/zsh -lc 'rg -n "def test_.*(embedded|raw_api_link|edge_only|noncanonical|api_link|subgraph|collision)" tests/test_workflow_core.py tests/test_foundation_utils.py tests/test_porting_ui_emitter.py tests/test_schema_validate.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
tests/test_schema_validate.py:339:def test_range_enum_skipped_when_value_is_api_link() -> None:
tests/test_porting_ui_emitter.py:145:def test_emit_ui_json_rejects_embedded_api_link_without_edge() -> None:
tests/test_porting_ui_emitter.py:157:def test_emit_ui_json_rejects_embedded_subgraph_boundary_link() -> None:
tests/test_porting_ui_emitter.py:175:def test_emit_ui_json_rejects_embedded_api_link_edge_collision(
tests/test_porting_ui_emitter.py:191:def test_emit_ui_json_preserves_edge_only_connectivity() -> None:
tests/test_porting_ui_emitter.py:204:def test_subgraph_boundary_connectivity_uses_edges_not_node_inputs() -> None:
tests/test_porting_ui_emitter.py:1697:def test_breadcrumb_stamped_on_each_subgraph_definition() -> None:
tests/test_porting_ui_emitter.py:1967:def test_inner_subgraph_nodes_carry_vibecomfy_uid() -> None:
tests/test_foundation_utils.py:21:def test_is_api_link_accepts_legacy_numeric_and_string_list_links() -> None:
tests/test_foundation_utils.py:27:def test_canonical_api_link_requires_json_string_id_and_integer_slot() -> None:
tests/test_foundation_utils.py:36:def test_is_api_link_rejects_bad_shapes() -> None:
tests/test_foundation_utils.py:45:def test_is_api_link_can_allow_tuple_links() -> None:
tests/test_foundation_utils.py:50:def test_is_api_link_can_preserve_schema_style_string_source_ids() -> None:
tests/test_foundation_utils.py:60:def test_is_api_link_strict_string_node_id_rejects_numeric_source_ids() -> None:
tests/test_foundation_utils.py:65:def test_is_api_link_strict_int_slot_rejects_non_int_slots() -> None:
tests/test_foundation_utils.py:70:def test_is_api_link_can_allow_compound_numeric_node_ids() -> None:
tests/test_foundation_utils.py:76:def test_is_api_link_tool_mode_is_string_source_strict_with_compound_ids() -> None:
tests/test_foundation_utils.py:91:def test_workflow_helpers_is_api_link_narrowing_rejects_string_and_float_slots() -> None:
tests/test_workflow_core.py:73:def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
tests/test_workflow_core.py:114:def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
tests/test_workflow_core.py:128:def test_raw_api_link_input_fails_validation_serialization_and_compile() -> None:
tests/test_workflow_core.py:154:def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
tests/test_workflow_core.py:172:def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
tests/test_workflow_core.py:431:def test_register_input_rejects_alias_collisions() -> None:

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -s -p no:cacheprovider -q tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_api_link_without_edge tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_subgraph_boundary_link tests/test_porting_ui_emitter.py::test_emit_ui_json_rejects_embedded_api_link_edge_collision tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity tests/test_porting_ui_emitter.py::test_subgraph_boundary_connectivity_uses_edges_not_node_inputs' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 5823ms:
.OMP: Warning #179: Function Can't set size of /tmp file failed:
............
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:197: UserWarning: emit_ui_json: schema-less node 1(Source); emitting best-effort slots. Pass strict=True to hard-fail.
    result = emit_ui_json(wf)

tests/test_porting_ui_emitter.py::test_emit_ui_json_preserves_edge_only_connectivity
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:197: UserWarning: emit_ui_json: schema-less node 2(Sink); emitting best-effort slots. Pass strict=True to hard-fail.
    result = emit_ui_json(wf)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
13 passed, 3 warnings in 2.69s

exec
/bin/zsh -lc 'for p in /dev/shm /tmp /var/tmp; do if [ -d "$p" ] && [ -w "$p" ]; then echo "$p writable-mode"; else echo "$p unavailable"; fi; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
/dev/shm unavailable
/tmp unavailable
/var/tmp unavailable

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/emit_subgraph.py | sed -n '278,352p'; nl -ba vibecomfy/_compile/_graph.py | sed -n '10,75p'; nl -ba vibecomfy/porting/emit/ui.py | sed -n '2098,2118p'; nl -ba vibecomfy/workflow.py | sed -n '1060,1130p'; nl -ba tests/test_porting_ui_emitter.py | sed -n '135,275p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 17ms:
   135	
   136	    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
   137	    result = emit_ui_json(wf, schema_provider=provider)
   138	
   139	    assert len(result["links"]) == 1
   140	    link = result["links"][0]
   141	    assert link[2] == 0  # from_slot
   142	    assert link[5] == "IMAGE"  # socket type from OutputSpec
   143	
   144	
   145	def test_emit_ui_json_rejects_embedded_api_link_without_edge() -> None:
   146	    wf = _wf("raw-link")
   147	    wf.nodes["1"] = VibeNode("1", "Source")
   148	    wf.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
   149	
   150	    with pytest.raises(WorkflowCompileError) as exc_info:
   151	        emit_ui_json(wf)
   152	
   153	    assert exc_info.value.code == "embedded_api_link"
   154	    assert exc_info.value.detail["edge_collision"] == "none"
   155	
   156	
   157	def test_emit_ui_json_rejects_embedded_subgraph_boundary_link() -> None:
   158	    wf = _wf("boundary-link")
   159	    wf.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["-10", 0]})
   160	
   161	    with pytest.raises(WorkflowCompileError) as exc_info:
   162	        emit_ui_json(wf)
   163	
   164	    assert exc_info.value.code == "embedded_api_link"
   165	    assert exc_info.value.detail["embedded_source"] == ["-10", 0]
   166	
   167	
   168	@pytest.mark.parametrize(
   169	    ("edge", "expected_collision"),
   170	    [
   171	        (VibeEdge("1", "0", "2", "image"), "identical"),
   172	        (VibeEdge("3", "1", "2", "image"), "conflicting"),
   173	    ],
   174	)
   175	def test_emit_ui_json_rejects_embedded_api_link_edge_collision(
   176	    edge: VibeEdge, expected_collision: str
   177	) -> None:
   178	    wf = _wf("raw-link-collision")
   179	    wf.nodes["1"] = VibeNode("1", "Source")
   180	    wf.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
   181	    wf.nodes["3"] = VibeNode("3", "OtherSource")
   182	    wf.edges.append(edge)
   183	
   184	    with pytest.raises(WorkflowCompileError) as exc_info:
   185	        emit_ui_json(wf)
   186	
   187	    assert exc_info.value.code == "embedded_api_link"
   188	    assert exc_info.value.detail["edge_collision"] == expected_collision
   189	
   190	
   191	def test_emit_ui_json_preserves_edge_only_connectivity() -> None:
   192	    wf = _wf("edge-only")
   193	    wf.nodes["1"] = VibeNode("1", "Source")
   194	    wf.nodes["2"] = VibeNode("2", "Sink")
   195	    wf.edges.append(VibeEdge("1", "0", "2", "image"))
   196	
   197	    result = emit_ui_json(wf)
   198	
   199	    assert result["links"] == [[1, 1, 0, 2, 0, ""]]
   200	    sink = next(node for node in result["nodes"] if node["id"] == 2)
   201	    assert sink["inputs"] == [{"name": "image", "type": "UNKNOWN", "link": 1}]
   202	
   203	
   204	def test_subgraph_boundary_connectivity_uses_edges_not_node_inputs() -> None:
   205	    subgraph = _build_subgraph_def(
   206	        {
   207	            "id": "sg-boundary",
   208	            "name": "Boundary",
   209	            "inputs": [{"name": "switch", "type": "BOOLEAN", "linkIds": [1]}],
   210	            "outputs": [{"name": "out", "type": "BOOLEAN"}],
   211	            "nodes": [
   212	                {
   213	                    "id": 10,
   214	                    "type": "LazySwitchKJ",
   215	                    "inputs": [
   216	                        {"name": "switch", "link": 1},
   217	                        {"name": "external", "link": 2},
   218	                    ],
   219	                    "outputs": [{"name": "out"}],
   220	                    "widgets_values": [],
   221	                }
   222	            ],
   223	            "links": [
   224	                {
   225	                    "id": 1,
   226	                    "origin_id": -10,
   227	                    "origin_slot": 0,
   228	                    "target_id": 10,
   229	                    "target_slot": 0,
   230	                    "type": "BOOLEAN",
   231	                },
   232	                {
   233	                    "id": 2,
   234	                    "origin_id": 99,
   235	                    "origin_slot": 0,
   236	                    "target_id": 10,
   237	                    "target_slot": 1,
   238	                    "type": "BOOLEAN",
   239	                },
   240	                {
   241	                    "id": 3,
   242	                    "origin_id": 10,
   243	                    "origin_slot": 0,
   244	                    "target_id": -20,
   245	                    "target_slot": 0,
   246	                    "type": "BOOLEAN",
   247	                },
   248	            ],
   249	        },
   250	        slug="boundary",
   251	        source_path=None,
   252	    )
   253	
   254	    assert all(
   255	        not is_canonical_api_link(value)
   256	        for node in subgraph.nodes.values()
   257	        for value in node.inputs.values()
   258	    )
   259	    assert subgraph.edges_in["10"] == [
   260	        VibeEdge("-10", "0", "10", "switch"),
   261	        VibeEdge("-10", "1", "10", "external"),
   262	    ]
   263	    assert subgraph.input_refs == {
   264	        ("10", "switch"): "switch",
   265	        ("10", "external"): "external",
   266	    }
   267	    source = "\n".join(
   268	        _emit_subgraph_functions(
   269	            {"subgraph_definitions": {subgraph.id: subgraph}},
   270	            diagnostics=[],
   271	            constant_map={},
   272	        )
   273	    )
   274	    assert "external=external" in source
   275	    assert "switch=switch" in source

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/emit_kwargs.py | sed -n '1155,1225p'; git diff --check 0d2bb176..HEAD -- . ':(exclude).oracle/**'; git diff --check 0d2bb176..HEAD -- .oracle/checkins/batch-3.md 2>&1 | sed -n '1,12p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 73ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-3.md:320: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:322: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:324: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:326: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:328: trailing whitespace.
++ 
.oracle/checkins/batch-3.md:330: trailing whitespace.

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=8 0d2bb176..HEAD -- vibecomfy | rg -n "''^'"\\+.*(inputs|\\[\\\"-?[0-9]+\\\"|_Edge|VibeEdge|is_canonical|embedded_api)\"" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
174:+                        _Edge(from_node, str(from_slot), str(node_id), str(key))
194:+                        _Edge("-10", str(len(input_ports) - 1), str(node_id), str(key))
218:+from vibecomfy.workflow import VibeEdge, VibeNode, _get_node_mode, _raise_embedded_api_links
236:+    _raise_embedded_api_links(wf, surface="UI serialization")

codex
PASS

All three blocker checks pass:

- `emit_subgraph` excludes every link-shaped input from `VibeNode.inputs`; declared and inferred `-10` boundaries are represented as `VibeEdge` entries ([emit_subgraph.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/emit_subgraph.py:292)).
- The canonical predicate now recognizes negative numeric IDs ([\_graph.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/_compile/_graph.py:44)).
- `emit_ui_json` performs the targeted `embedded_api_link` preflight before emission ([ui.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/ui.py:2111)), including identical/conflicting edge collision details. Edge-only output remains unchanged.
- The six regression cases are substantive: raw-only, negative-boundary, two collision variants, edge-only preservation, and subgraph edge conversion/source emission ([test_porting_ui_emitter.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:145)).

Verification: all 6 new cases passed; 13/13 targeted and adjacent authority tests passed.

Non-blocking artifact note: product/test files pass `git diff --check`; the literal whole diff reports trailing whitespace only inside the committed `.oracle/checkins/batch-3.md` transcript.
tokens used
94,594
PASS

All three blocker checks pass:

- `emit_subgraph` excludes every link-shaped input from `VibeNode.inputs`; declared and inferred `-10` boundaries are represented as `VibeEdge` entries ([emit_subgraph.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/emit_subgraph.py:292)).
- The canonical predicate now recognizes negative numeric IDs ([\_graph.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/_compile/_graph.py:44)).
- `emit_ui_json` performs the targeted `embedded_api_link` preflight before emission ([ui.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/ui.py:2111)), including identical/conflicting edge collision details. Edge-only output remains unchanged.
- The six regression cases are substantive: raw-only, negative-boundary, two collision variants, edge-only preservation, and subgraph edge conversion/source emission ([test_porting_ui_emitter.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:145)).

Verification: all 6 new cases passed; 13/13 targeted and adjacent authority tests passed.

Non-blocking artifact note: product/test files pass `git diff --check`; the literal whole diff reports trailing whitespace only inside the committed `.oracle/checkins/batch-3.md` transcript.
