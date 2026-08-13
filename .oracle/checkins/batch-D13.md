Reading additional input from stdin...
2026-08-13T13:01:38.613954Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:01:38.615207Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:01:38.615221Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb36-bcb0-7503-ba93-6c427cde2358
--------
user
# MEGADO CHECKPOINT — Batch D13 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the D13 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**D13 [HARD] — Corpus integrity, satisfiability, and semantic rubrics.** Tasks + acceptance from `.oracle/tasklist.md` (D13 section). Diff to review: `git diff 0f015101..b39f0c91` (B01 PASS SHA → D13 commit). Executor: GPT-5.6 Sol (workspace-write).

## Executor evidence

- 47 files changed (+1210/−19): `tests/live_agentic_harness/scenario_manifest.json` (new, 100 scenarios with SHA-256), `scenario_manifest.py` (new manifest loader), `runner.py` (manifest-driven discovery), `assessor.py`, 40 scenario JSONs (35 semantic rubrics + 3 corrected edits + 2 health controls), `REVISIONS.md` (new: 3 revised, 97 matched, none replaced), README.
- 71 passed on the requested pytest slice (runner_persistence, structural_harness_runner, guard_contract); manifest/rubric tests also green; `git diff --check` clean.
- The 3 mislabeled edits corrected; judge unavailability now fails desired edits closed.
- `external_workflows/` symlinked into the worktree (2827 corpus JSONs) + gitignored; source-workflow hashes resolved.

## Review focus (adversarial)

1. Manifest: exactly 100 unique ID/stem-matched scenarios; each has stable ID, path, descriptor SHA-256, inclusion status, source-workflow ID/hash where applicable. Verify hashes actually match file contents (spot-check a few).
2. Runner discovery: consumes the manifest, rejects missing/changed/duplicate/unmanifested files (find the rejection code + a test for it).
3. The 3 corrected edits (`485ff2`, `d7853c`, `d93baf`): now truthful — cannot pass without judged graph change or legitimate grounded refusal. Check the before/after expectations (git diff on those 3 files).
4. Rubrics: all 35 semantic non-edits have explicit expected-answer criteria (grounded/relevant/correct → pass; hallucinated/wrong/irrelevant/vacuous/empty → fail); 2 health controls excluded from semantic-product rates.
5. Every retained edit `desired` block feeds an active judge; judge unavailability fails desired edits closed.
6. REVISIONS.md: matched vs revised recorded; no scenario replaced; no aggregate improvement can be attributed to D13 later.
7. Source-workflow hashes resolve (no missing workflow_path).
8. Scope: only D13 files; `git diff --check 0f015101..b39f0c91` clean.
9. Run the focused slice yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks).

## Output

First line: `D13 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–9) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit MEGADO oracle checkpoint. I’ll follow its gate protocol, keep the workspace read-only, independently inspect the D13 diff and corpus integrity, then run only non-mutating verification.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '241,520p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
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

codex
The MEGADO gate protocol calls for delegated verification. Outbound OMP/Flash dispatch is unavailable in this read-only, network-restricted session, so I’m using three read-only review agents for independent checks: manifest/discovery, semantic scenarios/judging, and provenance/scope. I’ll personally reconcile their evidence and run the focused test slice.
2026-08-13T13:02:01.954040Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:01.954107Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:01.954117Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:07.728275Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:07.728725Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:07.728790Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:14.475032Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:14.484420Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:02:14.484583Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short --branch && git rev-parse --show-toplevel && git rev-parse --abbrev-ref HEAD && git log -1 --oneline b39f0c91 && git diff --stat 0f015101..b39f0c91 && rg -n '"'^## D13|''^### D13|D13|Corpus integrity'"' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 322ms:
## oracle-run
?? .oracle/checkins/batch-D13.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
oracle-run
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
b39f0c91 megado D13: authoritative 100-scenario manifest (SHA-256), manifest-driven runner discovery, 3 mislabeled edits corrected, 35 semantic rubrics, 2 health controls, REVISIONS.md — 71 focused tests green
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .gitignore                                         |    1 +
 .oracle/briefs/batch-D13.md                        |   32 +
 tests/live_agentic_harness/README.md               |    6 +
 tests/live_agentic_harness/REVISIONS.md            |   22 +
 tests/live_agentic_harness/assessor.py             |    4 +-
 tests/live_agentic_harness/runner.py               |   23 +-
 tests/live_agentic_harness/scenario_manifest.json  | 1299 ++++++++++++++++++++
 tests/live_agentic_harness/scenario_manifest.py    |  261 ++++
 ...audio-generation-with-detail-daemon-f0859f.json |   27 +
 ...-image-to-video-with-latent-composi-17dc9b.json |   28 +
 ...oint-xl-image-generation-with-refin-c9df19.json |   27 +
 ...pt-splitter-and-text-display-workfl-caae97.json |   27 +
 ...ssing-with-sharpening-film-grain-an-9aa0f1.json |   28 +
 ...image-with-ipadapter-and-controlnet-1999a9.json |   28 +
 ...e-captioning-and-keyword-extraction-d38dc8.json |   28 +
 ...en-image-inpainting-with-controlnet-09fc64.json |   28 +
 .../scenarios/live-graph-explanation-smoke.json    |    8 +
 ...n-splatting-from-video-with-hunyuan-432652.json |   28 +
 ...d-preview-and-image-output-workflow-d93baf.json |   13 +-
 ...pscaling-with-detail-daemon-sampler-673197.json |   28 +
 ...ed-image-to-video-with-svd-and-lora-4ed6d9.json |   28 +
 ...ff-video-generation-with-controlnet-a7e2af.json |   28 +
 ...to-image-mel-band-roformer-workflow-b22937.json |   28 +
 ...-and-video-generation-with-outpaint-435de2.json |   29 +
 ...age-to-video-with-animation-builder-99e2a9.json |   28 +
 ...age-to-video-with-sdxl-conditioning-389d90.json |   29 +
 ...tning-t2v-video-generation-with-lor-703c14.json |   28 +
 ...-to-video-with-lora-and-post-proces-9d28c6.json |   28 +
 .../scenarios/speed-distillation-research.json     |    5 +
 ...-video-to-video-with-controlnet-and-3c978e.json |   31 +
 ...iff-video-with-controlnet-and-depth-89b02a.json |   28 +
 ...-video-with-ipadapter-and-controlne-4eebf3.json |   28 +
 ...yuan-video-text-to-video-generation-265847.json |   28 +
 ...o-image-to-video-generation-with-en-ff076a.json |   30 +
 ...to-video-conversion-with-moonvalley-d7853c.json |   11 +-
 ...e-to-video-with-svd-and-webp-output-1882aa.json |   30 +
 ...-video-composition-with-spline-path-0c2716.json |   29 +
 ...ltx-video-with-audio-and-inpainting-b3ba8a.json |   30 +
 ...eo-seedvr2-video-upscaling-workflow-052e59.json |   30 +
 ...nting-with-spline-based-cut-and-dra-485ff2.json |   13 +-
 ...o-video-loading-and-saving-workflow-1c7ad8.json |   30 +
 .../video-video-output-workflow-f855de.json        |   27 +
 ...eneration-with-vace-and-multi-outpu-d1caec.json |   30 +
 ...video-generation-with-lora-and-nois-374aa9.json |   30 +
 ...-to-video-with-high-low-noise-model-7c8bb3.json |   30 +
 ...t-to-video-with-lora-and-dual-noise-62682a.json |   29 +
 ...t-to-video-with-lora-and-dual-noise-82ffb9.json |   29 +
 ...o-wanvideo-text-to-video-generation-71f825.json |   30 +
 tests/test_live_agentic_harness_corpus_manifest.py |  140 +++
 tests/test_live_agentic_harness_guard_contract.py  |   83 ++
 ...test_live_agentic_harness_runner_persistence.py |    3 +
 ...est_live_agentic_intent_judge_schema_context.py |   51 +
 tests/test_live_agentic_runner_persistence.py      |    9 +
 53 files changed, 2967 insertions(+), 19 deletions(-)
11:- Add no separate answer-quality batch. D13 authors the rubrics; B06 implements one tri-state semantic-answer judge.
97:## D13 — Corpus integrity, satisfiability, and semantic rubrics `[HARD]`
128:- Source-workflow hashes resolve before D13 passes.
245:3. Implement one rubric-driven tri-state answer judge for the 35 D13 semantic non-edits:
348:   - focused G0R/B01/D13/B04/B03/B05/B06/B07/B08 tests;
359:   - matched versus D13-revised subsets;
397:1. Where will the ignored `external_workflows/` corpus be provisioned for D13 and B09?

exec
/bin/zsh -lc "sed -n '90,145p' .oracle/tasklist.md && git diff --name-status 0f015101..b39f0c91 && git diff --check 0f015101..b39f0c91" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 6ms:
exec
/bin/zsh -lc "rg --files tests | rg 'live_agentic.*(runner_persistence|structural_harness_runner|guard_contract|corpus_manifest|intent_judge_schema_context)'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
tests/test_live_agentic_intent_judge_schema_context.py
tests/test_live_agentic_runner_persistence.py
tests/test_live_agentic_harness_runner_persistence.py
tests/test_live_agentic_harness_guard_contract.py
tests/test_live_agentic_harness_corpus_manifest.py

exec
/bin/zsh -lc "rg --files tests | rg 'structural|harness_runner' && rg -n 'structural_harness_runner' tests pyproject.toml pytest.ini setup.cfg 2>/dev/null" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 2 in 21ms:
codex
The committed delta is larger than the executor summary (53 files, +2967/−19, not 47 files, +1210/−19), so I’m treating the commit itself as authoritative. The D13 task boundaries still appear centered on the manifest, scenario descriptors, runner/assessor, documentation, and their tests; I’m now testing those exact surfaces.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp pytest -q -p no:cacheprovider -p no:rerunfailures tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_intent_judge_schema_context.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 2805ms:
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
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/tmp', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

codex
The focused pytest command is blocked before collection because this sandbox has no writable temporary directory; disabling `rerunfailures`, bytecode, and pytest’s cache is not enough because pytest’s capture/temp fixtures still require writes. I’ll retry with capture disabled to distinguish tests that can run without temp paths, and I’ll report any remaining sandbox limitation explicitly rather than treating it as a product failure.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider -p no:rerunfailures tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_intent_judge_schema_context.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 21010ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
EEEEEEEEE..EEEEEEEEEE..E........EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE..EEEEEEEE
==================================== ERRORS ====================================
___ ERROR at setup of test_persists_per_scenario_and_incremental_run_summary ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_persists_per_scenario_and_incremental_run_summary>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
________ ERROR at setup of test_final_summary_replaces_partial_summary _________

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_final_summary_replaces_partial_summary>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__________ ERROR at setup of test_runner_does_not_retry_outer_timeout __________

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_does_not_retry_outer_timeout>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_____ ERROR at setup of test_runner_types_provider_capacity_without_retry ______

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_types_provider_capacity_without_retry>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__ ERROR at setup of test_runner_retries_only_typed_empty_zero_token_attempt ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_retries_only_typed_empty_zero_token_attempt>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__ ERROR at setup of test_runner_keeps_malformed_nonempty_as_product_failure ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_keeps_malformed_nonempty_as_product_failure>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_runner_counts_persistent_provider_capacity_as_infra_blocked _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_counts_persistent_provider_capacity_as_infra_blocked>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
___ ERROR at setup of test_runner_does_not_classify_soft_search_429_as_infra ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_does_not_classify_soft_search_429_as_infra>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_runner_timeout_preserves_scenario_graph_change_expectation _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_timeout_preserves_scenario_graph_change_expectation>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_persisted_agentic_summary_redacts_json_quoted_secrets _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_persisted_agentic_summary_redacts_json_quoted_secrets>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
___ ERROR at setup of test_persists_per_scenario_and_incremental_run_summary ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_persists_per_scenario_and_incremental_run_summary>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
________ ERROR at setup of test_final_summary_replaces_partial_summary _________

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_final_summary_replaces_partial_summary>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__________ ERROR at setup of test_runner_does_not_retry_outer_timeout __________

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_does_not_retry_outer_timeout>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_____ ERROR at setup of test_runner_types_provider_capacity_without_retry ______

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_types_provider_capacity_without_retry>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__ ERROR at setup of test_runner_retries_only_typed_empty_zero_token_attempt ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_retries_only_typed_empty_zero_token_attempt>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__ ERROR at setup of test_runner_keeps_malformed_nonempty_as_product_failure ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_keeps_malformed_nonempty_as_product_failure>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_runner_counts_persistent_provider_capacity_as_infra_blocked _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_counts_persistent_provider_capacity_as_infra_blocked>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
___ ERROR at setup of test_runner_does_not_classify_soft_search_429_as_infra ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_does_not_classify_soft_search_429_as_infra>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_runner_timeout_preserves_scenario_graph_change_expectation _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_timeout_preserves_scenario_graph_change_expectation>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_persisted_agentic_summary_redacts_json_quoted_secrets _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_persisted_agentic_summary_redacts_json_quoted_secrets>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_____ ERROR at setup of test_agentic_guard_rejects_fake_dispatchers[fake] ______

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_fake_dispatchers[fake]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
____ ERROR at setup of test_agentic_guard_rejects_fake_dispatchers[faking] _____

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_fake_dispatchers[faking]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_non_agentic_model_behavior[deterministic] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_non_agentic_model_behavior[deterministic]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_non_agentic_model_behavior[scripted] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_non_agentic_model_behavior[scripted]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_non_agentic_model_behavior[None] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_non_agentic_model_behavior[None]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
__ ERROR at setup of test_agentic_guard_allows_blocked_real_agentic_artifacts __

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_allows_blocked_real_agentic_artifacts>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_catches_unchanged_graph_and_upstream_errors _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_catches_unchanged_graph_and_upstream_errors>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_allows_explicit_safe_refusal_scenarios __

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_allows_explicit_safe_refusal_scenarios>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_corrected_d13_edits_cannot_pass_as_noops[video-video-inpainting-with-spline-based-cut-and-dra-485ff2] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_corrected_d13_edits_cannot_pass_as_noops[video-video-inpainting-with-spline-based-cut-and-dra-485ff2]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_corrected_d13_edits_cannot_pass_as_noops[video-image-to-video-conversion-with-moonvalley-d7853c] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_corrected_d13_edits_cannot_pass_as_noops[video-image-to-video-conversion-with-moonvalley-d7853c]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_corrected_d13_edits_cannot_pass_as_noops[multi-3d-preview-and-image-output-workflow-d93baf] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_corrected_d13_edits_cannot_pass_as_noops[multi-3d-preview-and-image-output-workflow-d93baf]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_desired_edit_fails_closed_when_intent_judge_is_unavailable _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_desired_edit_fails_closed_when_intent_judge_is_unavailable>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_____ ERROR at setup of test_agentic_guard_rejects_oversized_model_request _____

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_oversized_model_request>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_forbidden_model_request_substrings _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_forbidden_model_request_substrings>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_static_widget_edit_overridden_by_link _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_static_widget_edit_overridden_by_link>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_no_effective_value_change_for_claimed_target _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_no_effective_value_change_for_claimed_target>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[3d-generates-a-3d-mesh-from] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[3d-generates-a-3d-mesh-from]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[audio-acestep-audio-generation-workflow-2a31ec] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[audio-acestep-audio-generation-workflow-2a31ec]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[image-sd3-image-generation-with-controlnet-19d221] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[image-sd3-image-generation-with-controlnet-19d221]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-generates-a-video-from-a] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-generates-a-video-from-a]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-image-to-video-conversion-with-moonvalley-d7853c] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-image-to-video-conversion-with-moonvalley-d7853c]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-ai-video-upscaling-with-detail-daemon-sampler-673197] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-ai-video-upscaling-with-detail-daemon-sampler-673197]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-audio-to-image-mel-band-roformer-workflow-b22937] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-audio-to-image-mel-band-roformer-workflow-b22937]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-hunyuan-video-text-to-video-generation-265847] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-hunyuan-video-text-to-video-generation-265847]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-video-output-workflow-f855de] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-video-output-workflow-f855de]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_false_landed_claim_still_fails_via_structured_checks _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_false_landed_claim_still_fails_via_structured_checks>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_false_validation_success_claim_still_fails_via_gates _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_false_validation_success_claim_still_fails_via_gates>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[missing-change-details] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[missing-change-details]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[missing-landed-count] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[missing-landed-count]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[zero-landed-count] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[zero-landed-count]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[negative-landed-count] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[negative-landed-count]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[string-landed-count] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[string-landed-count]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[float-landed-count] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[float-landed-count]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_requires_positive_landed_count[bool-landed-count] _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_requires_positive_landed_count[bool-landed-count]>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_expected_edit_with_positive_landed_count_passes _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_expected_edit_with_positive_landed_count_passes>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_exempts_grounded_refusal_from_landed_count _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_exempts_grounded_refusal_from_landed_count>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_route_not_applyable_without_landed_count _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_route_not_applyable_without_landed_count>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_failure_outcome_without_landed_count _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_failure_outcome_without_landed_count>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_rejects_shared_linked_source_edit_by_default _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_rejects_shared_linked_source_edit_by_default>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_allows_shared_linked_source_edit_when_declared _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_allows_shared_linked_source_edit_when_declared>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_treats_skipped_queue_validation_as_warning _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_treats_skipped_queue_validation_as_warning>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_agentic_guard_product_fails_real_queue_validation_failure _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_agentic_guard_product_fails_real_queue_validation_failure>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_runner_rejects_unmanifested_descriptor_before_execution _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_runner_rejects_unmanifested_descriptor_before_execution>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_manifest_discovery_rejects_changed_or_missing_descriptor _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_manifest_discovery_rejects_changed_or_missing_descriptor>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
___ ERROR at setup of test_manifest_discovery_rejects_duplicate_id_and_path ____

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_manifest_discovery_rejects_duplicate_id_and_path>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_manifest_discovery_rejects_duplicate_path_with_distinct_id _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_manifest_discovery_rejects_duplicate_path_with_distinct_id>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_____ ERROR at setup of test_intent_judge_includes_scenario_desired_rubric _____

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_intent_judge_includes_scenario_desired_rubric>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
___ ERROR at setup of test_intent_judge_includes_compiled_api_schema_context ___

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_intent_judge_includes_compiled_api_schema_context>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope>>

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef: FixtureDef, request) -> object | None:
        asyncio_mode = _get_asyncio_mode(request.config)
        if not _is_asyncio_fixture_function(fixturedef.func):
            if asyncio_mode == Mode.STRICT:
                # Ignore async fixtures without explicit asyncio mark in strict mode
                # This applies to pytest_trio fixtures, for example
                return (yield)
            if not _is_coroutine_or_asyncgen(fixturedef.func):
>               return (yield)
                        ^^^^^

../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    def _get_default_tempdir():
        """Calculate the default directory to use for temporary files.
        This routine should be called exactly once.

        We determine whether or not a candidate temp dir is usable by
        trying to create and write to a file in that directory.  If this
        is successful, the test file is deleted.  To prevent denial of
        service, the name of the test file must be randomized."""

        namer = _RandomNameSequence()
        dirlist = _candidate_tempdir_list()

        for dir in dirlist:
            if dir != _os.curdir:
                dir = _os.path.abspath(dir)
            # Try only a few names per directory.
            for seq in range(100):
                name = next(namer)
                filename = _os.path.join(dir, name)
                try:
                    fd = _os.open(filename, _bin_openflags, 0o600)
                    try:
                        try:
                            _os.write(fd, b'blat')
                        finally:
                            _os.close(fd)
                    finally:
                        _os.unlink(filename)
                    return dir
                except FileExistsError:
                    pass
                except PermissionError:
                    # This exception is thrown when a directory with the chosen name
                    # already exists on windows.
                    if (_os.name == 'nt' and _os.path.isdir(dir) and
                        _os.access(dir, _os.W_OK)):
                        continue
                    break   # no point trying more names in this directory
                except OSError:
                    break   # no point trying more names in this directory
>       raise FileNotFoundError(_errno.ENOENT,
                                "No usable temporary directory found in %s" %
                                dirlist)
E       FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: FileNotFoundError
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_persists_per_scenario_and_incremental_run_summary - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_final_summary_replaces_partial_summary - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_does_not_retry_outer_timeout - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_types_provider_capacity_without_retry - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_retries_only_typed_empty_zero_token_attempt - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_keeps_malformed_nonempty_as_product_failure - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_counts_persistent_provider_capacity_as_infra_blocked - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_does_not_classify_soft_search_429_as_infra - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_runner_timeout_preserves_scenario_graph_change_expectation - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_runner_persistence.py::test_persisted_agentic_summary_redacts_json_quoted_secrets - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_persists_per_scenario_and_incremental_run_summary - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_final_summary_replaces_partial_summary - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_does_not_retry_outer_timeout - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_types_provider_capacity_without_retry - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_retries_only_typed_empty_zero_token_attempt - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_keeps_malformed_nonempty_as_product_failure - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_counts_persistent_provider_capacity_as_infra_blocked - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_does_not_classify_soft_search_429_as_infra - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_runner_timeout_preserves_scenario_graph_change_expectation - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_runner_persistence.py::test_persisted_agentic_summary_redacts_json_quoted_secrets - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_fake_dispatchers[fake] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_fake_dispatchers[faking] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_non_agentic_model_behavior[deterministic] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_non_agentic_model_behavior[scripted] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_non_agentic_model_behavior[None] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_blocked_real_agentic_artifacts - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_catches_unchanged_graph_and_upstream_errors - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_explicit_safe_refusal_scenarios - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_corrected_d13_edits_cannot_pass_as_noops[video-video-inpainting-with-spline-based-cut-and-dra-485ff2] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_corrected_d13_edits_cannot_pass_as_noops[video-image-to-video-conversion-with-moonvalley-d7853c] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_corrected_d13_edits_cannot_pass_as_noops[multi-3d-preview-and-image-output-workflow-d93baf] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_desired_edit_fails_closed_when_intent_judge_is_unavailable - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_oversized_model_request - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_forbidden_model_request_substrings - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_static_widget_edit_overridden_by_link - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_no_effective_value_change_for_claimed_target - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[3d-generates-a-3d-mesh-from] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[audio-acestep-audio-generation-workflow-2a31ec] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[image-sd3-image-generation-with-controlnet-19d221] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-generates-a-video-from-a] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-image-to-video-conversion-with-moonvalley-d7853c] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-ai-video-upscaling-with-detail-daemon-sampler-673197] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-audio-to-image-mel-band-roformer-workflow-b22937] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-hunyuan-video-text-to-video-generation-265847] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-video-output-workflow-f855de] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_landed_claim_still_fails_via_structured_checks - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_validation_success_claim_still_fails_via_gates - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[missing-change-details] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[missing-landed-count] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[zero-landed-count] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[negative-landed-count] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[string-landed-count] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[float-landed-count] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[bool-landed-count] - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_with_positive_landed_count_passes - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_exempts_grounded_refusal_from_landed_count - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_route_not_applyable_without_landed_count - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_failure_outcome_without_landed_count - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_shared_linked_source_edit_by_default - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_shared_linked_source_edit_when_declared - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_treats_skipped_queue_validation_as_warning - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_product_fails_real_queue_validation_failure - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_corpus_manifest.py::test_runner_rejects_unmanifested_descriptor_before_execution - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_corpus_manifest.py::test_manifest_discovery_rejects_changed_or_missing_descriptor - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_corpus_manifest.py::test_manifest_discovery_rejects_duplicate_id_and_path - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_harness_corpus_manifest.py::test_manifest_discovery_rejects_duplicate_path_with_distinct_id - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_includes_scenario_desired_rubric - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_includes_compiled_api_schema_context - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
14 passed, 1 warning, 79 errors in 17.00s

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/scenario_manifest.py | sed -n '1,330p'; git diff 0f015101..b39f0c91 -- tests/live_agentic_harness/runner.py tests/live_agentic_harness/assessor.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py; nl -ba tests/live_agentic_harness/REVISIONS.md; nl -ba tests/live_agentic_harness/README.md | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
     1	"""Authoritative scenario-manifest generation and validation.
     2
     3	The live lane is descriptor-addressed: the manifest fixes both the selected
     4	scenario set and every scenario/source-workflow byte stream before model calls.
     5	"""
     6
     7	from __future__ import annotations
     8
     9	import hashlib
    10	import json
    11	from pathlib import Path
    12	from typing import Any, Mapping
    13
    14
    15	REPO = Path(__file__).resolve().parents[2]
    16	DEFAULT_SCENARIOS_DIR = Path(__file__).with_name("scenarios")
    17	DEFAULT_MANIFEST_PATH = Path(__file__).with_name("scenario_manifest.json")
    18	DESCRIPTOR_SUFFIXES = {".json", ".yaml", ".yml"}
    19
    20
    21	class ScenarioManifestError(ValueError):
    22	    """Raised when the selected live-agentic corpus differs from its manifest."""
    23
    24
    25	def sha256_file(path: Path) -> str:
    26	    digest = hashlib.sha256()
    27	    with path.open("rb") as handle:
    28	        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
    29	            digest.update(chunk)
    30	    return digest.hexdigest()
    31
    32
    33	def manifest_path_for(scenarios_dir: Path) -> Path:
    34	    if scenarios_dir.resolve() == DEFAULT_SCENARIOS_DIR.resolve():
    35	        return DEFAULT_MANIFEST_PATH
    36	    return scenarios_dir.parent / "scenario_manifest.json"
    37
    38
    39	def _repo_relative(path: Path, *, repo: Path) -> str:
    40	    try:
    41	        # Keep the checkout-relative symlink spelling (not the symlink target),
    42	        # because external_workflows/ is intentionally mounted into worktrees.
    43	        return path.absolute().relative_to(repo.absolute()).as_posix()
    44	    except ValueError as exc:
    45	        raise ScenarioManifestError(f"manifest path escapes repository root: {path}") from exc
    46
    47
    48	def _effective_repo(scenarios_dir: Path, repo: Path) -> Path:
    49	    """Use the real repo for lane data and a temp parent for isolated tests."""
    50	    try:
    51	        scenarios_dir.absolute().relative_to(repo.absolute())
    52	    except ValueError:
    53	        return scenarios_dir.parent
    54	    return repo
    55
    56
    57	def build_manifest(
    58	    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    59	    *,
    60	    repo: Path = REPO,
    61	    revised_ids: set[str] | None = None,
    62	) -> dict[str, Any]:
    63	    """Build a deterministic manifest for descriptor files already on disk."""
    64	    repo = _effective_repo(scenarios_dir, repo)
    65	    revised_ids = revised_ids or set()
    66	    entries: list[dict[str, Any]] = []
    67	    for path in sorted(
    68	        item for item in scenarios_dir.iterdir() if item.suffix in DESCRIPTOR_SUFFIXES
    69	    ):
    70	        if path.suffix != ".json":
    71	            raise ScenarioManifestError(f"authoritative scenarios must be JSON: {path}")
    72	        scenario = json.loads(path.read_text(encoding="utf-8"))
    73	        if not isinstance(scenario, Mapping):
    74	            raise ScenarioManifestError(f"scenario descriptor must contain an object: {path}")
    75	        scenario_id = str(scenario.get("id") or "")
    76	        if not scenario_id or scenario_id != path.stem:
    77	            raise ScenarioManifestError(
    78	                f"scenario id/stem mismatch: id={scenario_id!r}, path={path}"
    79	            )
    80	        workflow_path = scenario.get("workflow_path")
    81	        source_workflow: dict[str, str] | None = None
    82	        if workflow_path:
    83	            source_path = Path(str(workflow_path))
    84	            if not source_path.is_absolute():
    85	                source_path = repo / source_path
    86	            if not source_path.is_file():
    87	                raise ScenarioManifestError(
    88	                    f"scenario {scenario_id!r} workflow_path does not resolve: {workflow_path}"
    89	                )
    90	            source_id = str((scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem)
    91	            source_workflow = {
    92	                "id": source_id,
    93	                "path": _repo_relative(source_path, repo=repo),
    94	                "sha256": sha256_file(source_path),
    95	            }
    96	        scenario_kind = "edit"
    97	        if (scenario.get("classification") or {}).get("kind") == "health_control":
    98	            scenario_kind = "health_control"
    99	        elif scenario.get("answer_rubric"):
   100	            scenario_kind = "semantic_product"
   101	        entries.append(
   102	            {
   103	                "id": scenario_id,
   104	                "path": _repo_relative(path, repo=repo),
   105	                "descriptor_sha256": sha256_file(path),
   106	                "inclusion_status": "included",
   107	                "revision_status": "revised" if scenario_id in revised_ids else "matched",
   108	                "scenario_kind": scenario_kind,
   109	                "source_workflow": source_workflow,
   110	            }
   111	        )
   112	    return {
   113	        "schema_version": 1,
   114	        "scenario_root": _repo_relative(scenarios_dir, repo=repo),
   115	        "scenario_count": len(entries),
   116	        "entries": entries,
   117	    }
   118
   119
   120	def write_manifest(
   121	    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
   122	    *,
   123	    manifest_path: Path | None = None,
   124	    repo: Path = REPO,
   125	    revised_ids: set[str] | None = None,
   126	) -> Path:
   127	    """Write a deterministic manifest. Used by corpus maintenance and tests."""
   128	    target = manifest_path or manifest_path_for(scenarios_dir)
   129	    payload = build_manifest(scenarios_dir, repo=repo, revised_ids=revised_ids)
   130	    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
   131	    return target
   132
   133
   134	def discover_manifest_scenarios(
   135	    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
   136	    *,
   137	    manifest_path: Path | None = None,
   138	    repo: Path = REPO,
   139	) -> list[Path]:
   140	    """Validate the complete manifest contract and return included paths in order."""
   141	    repo = _effective_repo(scenarios_dir, repo)
   142	    manifest_path = manifest_path or manifest_path_for(scenarios_dir)
   143	    if not manifest_path.is_file():
   144	        raise ScenarioManifestError(f"scenario manifest is missing: {manifest_path}")
   145	    try:
   146	        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   147	    except (OSError, json.JSONDecodeError) as exc:
   148	        raise ScenarioManifestError(f"scenario manifest is unreadable: {exc}") from exc
   149	    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != 1:
   150	        raise ScenarioManifestError("scenario manifest schema_version must be 1")
   151	    entries = manifest.get("entries")
   152	    if not isinstance(entries, list):
   153	        raise ScenarioManifestError("scenario manifest entries must be a list")
   154
   155	    expected_root = _repo_relative(scenarios_dir, repo=repo)
   156	    if manifest.get("scenario_root") != expected_root:
   157	        raise ScenarioManifestError(
   158	            f"scenario_root mismatch: expected {expected_root!r}, got {manifest.get('scenario_root')!r}"
   159	        )
   160
   161	    selected: list[Path] = []
   162	    seen_ids: set[str] = set()
   163	    seen_paths: set[str] = set()
   164	    for index, entry in enumerate(entries):
   165	        if not isinstance(entry, Mapping):
   166	            raise ScenarioManifestError(f"manifest entry {index} must be an object")
   167	        inclusion_status = entry.get("inclusion_status")
   168	        if inclusion_status not in {"included", "excluded"}:
   169	            raise ScenarioManifestError(
   170	                f"manifest entry {index} has invalid inclusion_status: {inclusion_status!r}"
   171	            )
   172	        scenario_id = str(entry.get("id") or "")
   173	        rel_path = str(entry.get("path") or "")
   174	        if not scenario_id or scenario_id in seen_ids:
   175	            raise ScenarioManifestError(f"missing or duplicate scenario id: {scenario_id!r}")
   176	        if not rel_path or rel_path in seen_paths:
   177	            raise ScenarioManifestError(f"missing or duplicate scenario path: {rel_path!r}")
   178	        seen_ids.add(scenario_id)
   179	        seen_paths.add(rel_path)
   180	        path = repo / rel_path
   181	        try:
   182	            path.resolve().relative_to(scenarios_dir.resolve())
   183	        except ValueError as exc:
   184	            raise ScenarioManifestError(f"scenario path is outside scenario_root: {rel_path}") from exc
   185	        if not path.is_file():
   186	            raise ScenarioManifestError(f"manifested scenario is missing: {rel_path}")
   187	        if path.stem != scenario_id:
   188	            raise ScenarioManifestError(
   189	                f"manifest id/path-stem mismatch: id={scenario_id!r}, path={rel_path!r}"
   190	            )
   191	        actual_descriptor_hash = sha256_file(path)
   192	        if actual_descriptor_hash != entry.get("descriptor_sha256"):
   193	            raise ScenarioManifestError(
   194	                f"scenario descriptor hash mismatch for {scenario_id}: "
   195	                f"expected {entry.get('descriptor_sha256')}, got {actual_descriptor_hash}"
   196	            )
   197	        try:
   198	            scenario = json.loads(path.read_text(encoding="utf-8"))
   199	        except (OSError, json.JSONDecodeError) as exc:
   200	            raise ScenarioManifestError(
   201	                f"scenario descriptor is unreadable for {scenario_id}: {exc}"
   202	            ) from exc
   203	        if not isinstance(scenario, Mapping):
   204	            raise ScenarioManifestError(
   205	                f"scenario descriptor must contain an object for {scenario_id}"
   206	            )
   207	        if scenario.get("id") != scenario_id:
   208	            raise ScenarioManifestError(
   209	                f"descriptor id mismatch for {scenario_id}: got {scenario.get('id')!r}"
   210	            )
   211	        workflow_path = scenario.get("workflow_path")
   212	        source = entry.get("source_workflow")
   213	        if workflow_path:
   214	            if not isinstance(source, Mapping):
   215	                raise ScenarioManifestError(f"source workflow metadata missing for {scenario_id}")
   216	            source_path = repo / str(source.get("path") or "")
   217	            expected_source_path = Path(str(workflow_path))
   218	            if not expected_source_path.is_absolute():
   219	                expected_source_path = repo / expected_source_path
   220	            if source_path.resolve() != expected_source_path.resolve():
   221	                raise ScenarioManifestError(f"source workflow path mismatch for {scenario_id}")
   222	            if not source_path.is_file():
   223	                raise ScenarioManifestError(f"source workflow is missing for {scenario_id}: {source_path}")
   224	            expected_source_id = str(
   225	                (scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem
   226	            )
   227	            if source.get("id") != expected_source_id:
   228	                raise ScenarioManifestError(f"source workflow id mismatch for {scenario_id}")
   229	            actual_source_hash = sha256_file(source_path)
   230	            if actual_source_hash != source.get("sha256"):
   231	                raise ScenarioManifestError(
   232	                    f"source workflow hash mismatch for {scenario_id}: "
   233	                    f"expected {source.get('sha256')}, got {actual_source_hash}"
   234	                )
   235	        elif source is not None:
   236	            raise ScenarioManifestError(f"unexpected source workflow metadata for {scenario_id}")
   237	        if inclusion_status == "included":
   238	            selected.append(path)
   239
   240	    declared_count = manifest.get("scenario_count")
   241	    if declared_count != len(selected):
   242	        raise ScenarioManifestError(
   243	            f"scenario_count mismatch: expected {declared_count}, selected {len(selected)}"
   244	        )
   245	    discovered = {
   246	        _repo_relative(path, repo=repo)
   247	        for path in scenarios_dir.iterdir()
   248	        if path.suffix in DESCRIPTOR_SUFFIXES
   249	    }
   250	    unmanifested = sorted(discovered - seen_paths)
   251	    if unmanifested:
   252	        raise ScenarioManifestError(
   253	            "unmanifested scenario descriptor(s): " + ", ".join(unmanifested)
   254	        )
   255	    missing_from_directory = sorted(seen_paths - discovered)
   256	    if missing_from_directory:
   257	        raise ScenarioManifestError(
   258	            "manifested scenario descriptor(s) missing from directory: "
   259	            + ", ".join(missing_from_directory)
   260	        )
   261	    return selected
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/assessor.py b/tests/live_agentic_harness/assessor.py
index 42388790..b343683e 100644
--- a/tests/live_agentic_harness/assessor.py
+++ b/tests/live_agentic_harness/assessor.py
@@ -841,7 +841,9 @@ def assess_live_output_dir(
                 issues.append(
                     {
                         "check": "intent_judge",
-                        "severity": "warning",
+                        # A desired block is an active acceptance rubric, not
+                        # optional context. Fail closed if its judge is absent.
+                        "severity": "error" if scenario.get("desired") else "warning",
                         "detail": f"LLM intent judge could not run: {verdict.get('error')}",
                     }
                 )
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index 94672531..29bac47f 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -33,6 +33,7 @@ from .failure_analysis import (
     prepare_failure_analysis,
     recommendations_for_run,
 )
+from .scenario_manifest import discover_manifest_scenarios

 DEFAULT_MAX_WORKERS = 12
 DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
@@ -40,10 +41,14 @@ DEFAULT_PROGRESS_EVERY = 10
 DEFAULT_INFRA_RETRIES = 1
 REPO = Path(__file__).resolve().parents[2]

-def _scenario_paths(scenarios_dir: Path) -> list[Path]:
+def _scenario_paths(
+    scenarios_dir: Path,
+    *,
+    manifest_path: Path | None = None,
+) -> list[Path]:
     if not scenarios_dir.is_dir():
-        return []
-    return sorted(p for p in scenarios_dir.iterdir() if p.suffix in {".yaml", ".yml", ".json"})
+        raise FileNotFoundError(f"scenario directory is missing: {scenarios_dir}")
+    return discover_manifest_scenarios(scenarios_dir, manifest_path=manifest_path)


 def _load_scenario(path: Path) -> dict[str, Any]:
@@ -487,12 +492,13 @@ def run_tag(
     per_scenario_timeout: int = DEFAULT_PER_SCENARIO_TIMEOUT,
     progress_every: int = DEFAULT_PROGRESS_EVERY,
     infra_retries: int = DEFAULT_INFRA_RETRIES,
+    manifest_path: Path | None = None,
 ) -> dict[str, Any]:
     """Run every scenario under *scenarios_dir* CONCURRENTLY — each in its own
     subprocess (process-isolated + kill-on-timeout), bounded by *max_workers*."""
     if scenarios_dir is None:
         scenarios_dir = Path(__file__).with_name("scenarios")
-    paths = _scenario_paths(scenarios_dir)
+    paths = _scenario_paths(scenarios_dir, manifest_path=manifest_path)
     results: list[dict[str, Any] | None] = [None] * len(paths)
     sem = threading.Semaphore(max(1, max_workers))
     lock = threading.Lock()
@@ -672,6 +678,14 @@ def _build_parser() -> argparse.ArgumentParser:
         default=None,
         help="Directory containing scenario YAML/JSON files.",
     )
+    parser.add_argument(
+        "--manifest",
+        default=None,
+        help=(
+            "Authoritative scenario manifest (default: scenario_manifest.json "
+            "beside the scenarios directory)."
+        ),
+    )
     parser.add_argument(
         "--output-base",
         default=None,
@@ -825,6 +839,7 @@ def main(argv: list[str] | None = None) -> int:
         per_scenario_timeout=args.per_scenario_timeout,
         progress_every=args.progress_every,
         infra_retries=args.infra_retries,
+        manifest_path=Path(args.manifest) if args.manifest else None,
     )
     if args.prepare_failure_analysis or args.analyze_failures or args.recommend_fixes:
         run_summary_path = _run_dir_for(output_base, summary["tag"]) / "run_summary.json"
diff --git a/tests/test_live_agentic_harness_corpus_manifest.py b/tests/test_live_agentic_harness_corpus_manifest.py
new file mode 100644
index 00000000..f7a020d6
--- /dev/null
+++ b/tests/test_live_agentic_harness_corpus_manifest.py
@@ -0,0 +1,140 @@
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+import pytest
+
+from tests.live_agentic_harness.scenario_manifest import (
+    DEFAULT_MANIFEST_PATH,
+    DEFAULT_SCENARIOS_DIR,
+    ScenarioManifestError,
+    discover_manifest_scenarios,
+    sha256_file,
+    write_manifest,
+)
+from tests.live_agentic_harness.runner import run_tag
+
+
+CORRECTED_EDITS = {
+    "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
+    "video-image-to-video-conversion-with-moonvalley-d7853c",
+    "multi-3d-preview-and-image-output-workflow-d93baf",
+}
+
+
+def _scenario(path: Path) -> dict:
+    return json.loads(path.read_text(encoding="utf-8"))
+
+
+def test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios() -> None:
+    paths = discover_manifest_scenarios()
+    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
+    entries = manifest["entries"]
+
+    assert len(paths) == manifest["scenario_count"] == len(entries) == 100
+    assert len({entry["id"] for entry in entries}) == 100
+    assert len({entry["path"] for entry in entries}) == 100
+    assert all(entry["id"] == Path(entry["path"]).stem for entry in entries)
+    assert all(entry["inclusion_status"] == "included" for entry in entries)
+    assert {entry["revision_status"] for entry in entries} == {"matched", "revised"}
+    assert {entry["id"] for entry in entries if entry["revision_status"] == "revised"} == CORRECTED_EDITS
+
+    source_entries = [entry for entry in entries if entry["source_workflow"]]
+    assert len(source_entries) == 98
+    for entry in source_entries:
+        source = entry["source_workflow"]
+        source_path = Path(__file__).parents[1] / source["path"]
+        assert source_path.is_file()
+        assert source["sha256"] == sha256_file(source_path)
+
+
+def test_d13_no_change_reconciliation_and_rubric_contract() -> None:
+    scenarios = [_scenario(path) for path in discover_manifest_scenarios()]
+    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
+    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
+    corrected = [s for s in scenarios if s["id"] in CORRECTED_EDITS]
+
+    assert len(semantic) == 35
+    assert len(controls) == 2
+    assert len(corrected) == 3
+    assert len(semantic) + len(controls) + len(corrected) == 40
+    assert {s["_tags"]["query_type"] for s in semantic} == {"research", "explain", "diagnose"}
+    assert all(s["assessment"]["expect_graph_changed"] is False for s in semantic + controls)
+    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
+    assert all(s["assessment"]["expect_graph_changed"] is True and s["apply"] is True for s in corrected)
+
+    for scenario in semantic:
+        rubric = scenario["answer_rubric"]
+        assert rubric["judge"] == "semantic_answer"
+        assert rubric["workflow_path"] == scenario["workflow_path"]
+        assert rubric["required_node_evidence"]
+        assert len(rubric["expected_criteria"]) >= 4
+        assert "grounded" in rubric["pass_condition"]
+        assert len(rubric["fail_conditions"]) == 5
+
+    desired_edits = [s for s in scenarios if s.get("desired")]
+    assert desired_edits
+    assert all(s["assessment"]["expect_graph_changed"] is True for s in desired_edits)
+    assert all(not s["assessment"].get("skip_intent_judge") for s in desired_edits)
+
+
+def test_runner_rejects_unmanifested_descriptor_before_execution(tmp_path: Path) -> None:
+    scenarios_dir = tmp_path / "scenarios"
+    scenarios_dir.mkdir()
+    (scenarios_dir / "one.json").write_text(
+        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
+    )
+    write_manifest(scenarios_dir)
+    (scenarios_dir / "stray.json").write_text(
+        json.dumps({"id": "stray", "query": "stray"}), encoding="utf-8"
+    )
+    with pytest.raises(ScenarioManifestError, match="unmanifested"):
+        run_tag("stray-preflight", scenarios_dir=scenarios_dir, output_base=tmp_path / "out")
+
+
+def test_manifest_discovery_rejects_changed_or_missing_descriptor(tmp_path: Path) -> None:
+    scenarios_dir = tmp_path / "scenarios"
+    scenarios_dir.mkdir()
+    descriptor = scenarios_dir / "one.json"
+    descriptor.write_text(json.dumps({"id": "one", "query": "one"}), encoding="utf-8")
+    write_manifest(scenarios_dir)
+    descriptor.write_text(json.dumps({"id": "one", "query": "changed"}), encoding="utf-8")
+    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
+        discover_manifest_scenarios(scenarios_dir)
+
+    descriptor.unlink()
+    with pytest.raises(ScenarioManifestError, match="missing"):
+        discover_manifest_scenarios(scenarios_dir)
+
+
+def test_manifest_discovery_rejects_duplicate_id_and_path(tmp_path: Path) -> None:
+    scenarios_dir = tmp_path / "scenarios"
+    scenarios_dir.mkdir()
+    (scenarios_dir / "one.json").write_text(
+        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
+    )
+    manifest_path = write_manifest(scenarios_dir)
+    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
+    manifest["entries"].append(dict(manifest["entries"][0]))
+    manifest["scenario_count"] = 2
+    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
+    with pytest.raises(ScenarioManifestError, match="duplicate scenario id"):
+        discover_manifest_scenarios(scenarios_dir)
+
+
+def test_manifest_discovery_rejects_duplicate_path_with_distinct_id(tmp_path: Path) -> None:
+    scenarios_dir = tmp_path / "scenarios"
+    scenarios_dir.mkdir()
+    (scenarios_dir / "one.json").write_text(
+        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
+    )
+    manifest_path = write_manifest(scenarios_dir)
+    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
+    duplicate = dict(manifest["entries"][0])
+    duplicate["id"] = "two"
+    manifest["entries"].append(duplicate)
+    manifest["scenario_count"] = 2
+    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
+    with pytest.raises(ScenarioManifestError, match="duplicate scenario path"):
+        discover_manifest_scenarios(scenarios_dir)
diff --git a/tests/test_live_agentic_harness_guard_contract.py b/tests/test_live_agentic_harness_guard_contract.py
index 86e4bfd1..e4ca47a8 100644
--- a/tests/test_live_agentic_harness_guard_contract.py
+++ b/tests/test_live_agentic_harness_guard_contract.py
@@ -19,6 +19,13 @@ from tests.harness_common import (
 )


+_CORRECTED_D13_EDIT_IDS = (
+    "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
+    "video-image-to-video-conversion-with-moonvalley-d7853c",
+    "multi-3d-preview-and-image-output-workflow-d93baf",
+)
+
+
 def _write_flow_metadata(output_dir: Path, **overrides: object) -> None:
     metadata = {
         "flow_kind": FLOW_KIND_LIVE_AGENTIC_HEADLESS,
@@ -356,6 +363,82 @@ def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_p
     assert "no_candidate_reason" in checks


+@pytest.mark.parametrize("scenario_id", _CORRECTED_D13_EDIT_IDS)
+def test_corrected_d13_edits_cannot_pass_as_noops(
+    tmp_path: Path,
+    scenario_id: str,
+) -> None:
+    output_dir = tmp_path / scenario_id
+    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
+    (output_dir / "response.json").write_text(
+        json.dumps(
+            {
+                "ok": True,
+                "graph_unchanged": True,
+                "no_candidate_reason": "no_changes",
+                "outcome": {"kind": "noop"},
+                "message": "No changes.",
+            }
+        ),
+        encoding="utf-8",
+    )
+    scenario_path = (
+        Path(__file__).parent
+        / "live_agentic_harness"
+        / "scenarios"
+        / f"{scenario_id}.json"
+    )
+    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
+
+    verdict = guard_output_dir(output_dir, scenario=scenario)
+
+    assert verdict["live_agentic_success"] is False
+    checks = {
+        issue["check"]
+        for issue in verdict["assessment"]["issues"]
+        if issue["severity"] == "error"
+    }
+    assert "graph_changed" in checks
+    assert "no_candidate_reason" in checks
+    assert "outcome_kind" in checks
+
+
+def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
+    tmp_path: Path,
+    monkeypatch,
+) -> None:  # noqa: ANN001
+    output_dir = tmp_path / "desired-judge-unavailable"
+    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
+    _write_successful_candidate(output_dir)
+    (output_dir / "implementation_result.json").write_text(
+        json.dumps({"status": "success"}), encoding="utf-8"
+    )
+    monkeypatch.setattr(
+        "tests.live_agentic_harness.assessor.judge_edit_intent",
+        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
+    )
+
+    verdict = guard_output_dir(
+        output_dir,
+        scenario={
+            "id": "desired-judge-unavailable",
+            "query": "set seed to 42",
+            "assessment": {"expect_graph_changed": True},
+            "desired": {
+                "outcome": "seed is 42",
+                "quality": "only the intended seed changes",
+                "alternatives_ok": False,
+            },
+        },
+    )
+
+    assert verdict["live_agentic_success"] is False
+    assert any(
+        issue["check"] == "intent_judge" and issue["severity"] == "error"
+        for issue in verdict["assessment"]["issues"]
+    )
+
+
 def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
     output_dir = tmp_path / "oversized-model-request"
     _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
diff --git a/tests/test_live_agentic_intent_judge_schema_context.py b/tests/test_live_agentic_intent_judge_schema_context.py
index 3bc413b7..2fcc2d3f 100644
--- a/tests/test_live_agentic_intent_judge_schema_context.py
+++ b/tests/test_live_agentic_intent_judge_schema_context.py
@@ -6,6 +6,57 @@ from pathlib import Path
 from tests.live_agentic_harness.intent_judge import judge_edit_intent


+def test_intent_judge_includes_scenario_desired_rubric(
+    tmp_path: Path,
+    monkeypatch,
+) -> None:  # noqa: ANN001
+    (tmp_path / "original.ui.json").write_text(
+        json.dumps({"nodes": []}), encoding="utf-8"
+    )
+    (tmp_path / "candidate.ui.json").write_text(
+        json.dumps({"nodes": [{"id": 1}]}), encoding="utf-8"
+    )
+    seen: dict[str, object] = {}
+
+    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202, ARG001
+        seen["messages"] = messages
+        return {
+            "content": json.dumps(
+                {
+                    "pass_": True,
+                    "criteria": {
+                        "correct_node_targeted": True,
+                        "correct_parameter_changed": True,
+                        "value_semantically_matches_intent": True,
+                        "no_orphaned_wiring": True,
+                    },
+                    "rationale": "desired outcome satisfied",
+                }
+            )
+        }
+
+    monkeypatch.setattr(
+        "tests.live_agentic_harness.intent_judge.run_model_turn",
+        fake_run_model_turn,
+    )
+    desired = {
+        "outcome": "seed is 42",
+        "quality": "only the intended seed changes",
+        "alternatives_ok": False,
+    }
+    verdict = judge_edit_intent(
+        tmp_path,
+        {"query": "set seed to 42", "desired": desired},
+    )
+
+    assert verdict["pass_"] is True
+    messages = seen["messages"]
+    assert isinstance(messages, list)
+    assert "Scenario-specific desired outcome" in messages[0]["content"]
+    payload = json.loads(messages[1]["content"])
+    assert payload["desired_outcome"] == desired
+
+
 def test_intent_judge_includes_compiled_api_schema_context(
     tmp_path: Path,
     monkeypatch,
     1	# Live-agentic corpus revisions
     2
     3	This log distinguishes query/coverage revisions from descriptors whose original
     4	scenario intent remains matched. `scenario_manifest.json` records the same split
     5	as `revision_status: revised|matched`.
     6
     7	## D13
     8
     9	Three edit descriptors were revised because their original requests targeted
    10	controls that the referenced source workflow does not expose. No scenario was
    11	replaced and all three retain their original source workflow and modality.
    12
    13	| Scenario | Before | After | Coverage retained |
    14	| --- | --- | --- | --- |
    15	| `video-video-inpainting-with-spline-based-cut-and-dra-485ff2` | Set nonexistent inpaint denoising strength to `0.6`; expected no graph change. | Set `INPAINT_InpaintWithModel` seed from `534667941392889` to `42`, keep control fixed; graph change and desired-outcome judge required. | Low-level video-inpainting parameter edit without disturbing spline/composite stages. |
    16	| `video-image-to-video-conversion-with-moonvalley-d7853c` | Change frame count/FPS for five seconds, though Moonvalley exposes neither; expected no graph change. | Change Moonvalley generation steps from `100` to `80`, preserve prompt adherence `7`; graph change and desired-outcome judge required. | Low-level Moonvalley generation parameter edit and downstream video-save integrity. |
    17	| `multi-3d-preview-and-image-output-workflow-d93baf` | Make a normal-map `PreviewImage` top-down as though it were a camera-controlled 3D preview; expected no graph change. | Change `SaveGLB` filename prefix from `3d/ComfyUI` to `3d/moge-top-down`, preserving mesh and both normal-preview branches; graph change and desired-outcome judge required. | Low-level 3D output parameter edit and multi-branch integrity. |
    18
    19	The 35 research/explain/diagnose descriptors received semantic answer rubrics
    20	without changing their original queries or source workflows, so they remain
    21	`matched`. The two non-product smoke scenarios were marked as health controls;
    22	that classification change is not a query rewrite.
     1	# Live Agentic Tests
     2
     3	This directory is for **live agentic tests only**: real executor paths with
     4	real model/provider calls.
     5
     6	A test belongs here only when the subject-under-test is a real model or agent
     7	using production-like tools, and the evidence comes from the actual run. Fake or
     8	faking actors, deterministic builders, scripted `messages.jsonl`, and structural
     9	contract scenarios do not belong here.
    10
    11	The selected live lane is fixed by `scenario_manifest.json`. Before starting
    12	scenario subprocesses, the runner validates descriptor IDs/paths/hashes,
    13	source-workflow IDs/paths/hashes, and exact directory membership. A missing,
    14	changed, duplicate, or stray descriptor fails preflight. `--manifest` can select
    15	another equally strict manifest for an explicit scenario directory.
    16
    17	Deterministic real-workflow agentic scenarios live in
    18	`tests/structural_harness/` as **structural agentic tests**:
    19
    20	```bash
    21	python -m tests.structural_harness.runner --mode structural --actor fake --tag run
    22	```
    23
    24	## Operator Commands
    25
    26	Run all live-headless scenarios in this directory:
    27
    28	```bash
    29	python -m tests.live_agentic_harness.runner --tag live-headless-smoke --json
    30	```
    31
    32	Run against an explicit scenario directory and output root:
    33
    34	```bash
    35	python -m tests.live_agentic_harness.runner \
    36	  --tag live-headless-smoke \
    37	  --scenarios-dir tests/live_agentic_harness/scenarios \
    38	  --output-base out/agentic \
    39	  --json
    40	```
    41
    42	Each scenario writes artifacts under `out/agentic/<tag>/<scenario_id>/` and is
    43	then checked by `tests.live_agentic_harness.guard.guard_output_dir`. A live success
    44	requires `flow_kind=live_agentic_headless`, `live=true`, `status=success`,
    45	`dispatcher=real`, and `model_behavior=agentic`. Fake/faking dispatchers and
    46	non-agentic model behavior are rejected for live-headless artifacts.
    47
    48	Blocked provider readiness is a valid harness outcome but not a live success.
    49	It should produce `status=blocked_prerequisite` in `flow_metadata.json` and a
    50	nonzero runner exit when any scenario is blocked.
    51
    52	For the full boundary matrix, `live=false` versus `dry_run` semantics, dry-run
    53	CLI invocation, blocked-prerequisite smoke checks, browser e2e commands, and
    54	subprocess integration contract, see
    55	`../../docs/testing/headless-agentic-harnesses.md`.

exec
/bin/zsh -lc "python -c '
import json,hashlib
from pathlib import Path
repo=Path.cwd(); base=repo/\"tests/live_agentic_harness\"; m=json.loads((base/\"scenario_manifest.json\").read_text())
print(\"manifest_count\",m[\"scenario_count\"],\"entries\",len(m[\"entries\"]))
print(\"ids\",len({e[\"id\"] for e in m[\"entries\"]}),\"paths\",len({e[\"path\"] for e in m[\"entries\"]}))
print(\"statuses\",{k:sum(e[\"inclusion_status\"]==k for e in m[\"entries\"]) for k in set(e[\"inclusion_status\"] for e in m[\"entries\"])})
print(\"kinds\",{k:sum(e[\"scenario_kind\"]==k for e in m[\"entries\"]) for k in set(e[\"scenario_kind\"] for e in m[\"entries\"])})
print(\"revisions\",{k:sum(e[\"revision_status\"]==k for e in m[\"entries\"]) for k in set(e[\"revision_status\"] for e in m[\"entries\"])})
errors=[]
for e in m[\"entries\"]:
 p=repo/e[\"path\"]; got=hashlib.sha256(p.read_bytes()).hexdigest()
 if got"'!=e["descriptor_sha256"]: errors.append(("descriptor",e["id"],got,e["descriptor_sha256"]))
 if e["id"]!=p.stem: errors.append(("stem",e["id"],p.stem))
 s=json.loads(p.read_text())
 if s["id"]!=e["id"]: errors.append(("json-id",e["id"],s.get("id")))
 src=e.get("source_workflow")
 if src:
  sp=repo/src["path"]
  if not sp.is_file(): errors.append(("missing-source",e["id"],str(sp)))
  elif hashlib.sha256(sp.read_bytes()).hexdigest()!=src["sha256"]: errors.append(("source-hash",e["id"]))
print("all_hash_errors",len(errors)); print(*errors[:5],sep="'"\\\\n\")
print(\"source_metadata\",sum(bool(e.get(\"source_workflow\")) for e in m[\"entries\"]))
for e in [m[\"entries\"][0],m[\"entries\"][49],m[\"entries\"][-1]]: print(\"spot\",e[\"id\"],e[\"descriptor_sha256\"],(e.get(\"source_workflow\") or {}).get(\"sha256\"))
scenarios=[json.loads((repo/e[\"path\"]).read_text()) for e in m[\"entries\"]]
semantic=[s for s in scenarios if s.get(\"classification\",{}).get(\"kind\")==\"semantic_product\"]
controls=[s for s in scenarios if s.get(\"classification\",{}).get(\"kind\")==\"health_control\"]
corrected={\"video-video-inpainting-with-spline-based-cut-and-dra-485ff2\",\"video-image-to-video-conversion-with-moonvalley-d7853c\",\"multi-3d-preview-and-image-output-workflow-d93baf\"}
print(\"reconcile\",len(semantic),len(controls),len([s for s in scenarios if s[\"id\"] in corrected]))
print(\"controls\",[(s[\"id\"],s[\"classification\"]) for s in controls])
print(\"desired_count\",sum(bool(s.get(\"desired\")) for s in scenarios))
for s in semantic:
 r=s.get(\"answer_rubric\",{}); bad=[k for k in [\"judge\",\"workflow_path\",\"required_node_evidence\",\"expected_criteria\",\"pass_condition\",\"fail_conditions\"] if not r.get(k)]
 if len(r.get(\"fail_conditions\",[]))"'!=5: bad.append("fail_count")
 if bad: print("BADRUBRIC",s["id"],bad,r)
print("semantic qtypes",sorted({s["_tags"]["query_type"] for s in semantic}))
'"' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 555ms:
manifest_count 100 entries 100
ids 100 paths 100
statuses {'included': 100}
kinds {'edit': 63, 'semantic_product': 35, 'health_control': 2}
revisions {'revised': 3, 'matched': 97}
all_hash_errors 0

source_metadata 98
spot 3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2 f2d7ac44c1d69ddbc3da300e0700868a9107e64c2ce5b75a405d92080b761f46 3c605c00652907736c02e5c4bfff6fa17c9edbfd06024be972b004dc2332f180
spot multi-ai-video-upscaling-with-detail-daemon-sampler-673197 2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457 d15ba9e1d9385ec8ebcbe3ba82d1e9a85af103821b369af3f45170ac8c037f1b
spot video-wanvideo-text-to-video-generation-71f825 df4959641e24bfcd7b62ad558dc4cede081febf7e14f44475fd3a70855f60d31 87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3
reconcile 35 2 3
controls [('live-graph-explanation-smoke', {'kind': 'health_control', 'excluded_from_semantic_product_rates': True, 'purpose': 'Smoke-test that an inline graph can be inspected and answered without requiring a product-quality semantic score.'}), ('speed-distillation-research', {'kind': 'health_control', 'excluded_from_semantic_product_rates': True, 'purpose': 'Exercise the research route without a source graph; this is transport/routing health, not semantic product quality.'})]
desired_count 42
semantic qtypes ['diagnose', 'explain', 'research']

exec
/bin/zsh -lc "python -c '
import json
from pathlib import Path
base=Path(\"tests/live_agentic_harness/scenarios\")
for p in sorted(base.glob(\"*.json\")):
 s=json.loads(p.read_text())
 if s.get(\"classification\",{}).get(\"kind\")==\"semantic_product\":
  r=s[\"answer_rubric\"]
  print(\"ID\",s[\"id\"])
  print(\"Q\",s.get(\"query\"))
  print(\"NODES\",r.get(\"required_node_evidence\"))
  print(\"CRIT\",r.get(\"expected_criteria\"))
  print(\"PASS\",r.get(\"pass_condition\"))
  print(\"FAIL\",r.get(\"fail_conditions\"))
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 387ms:
ID audio-acestep-audio-generation-with-detail-daemon-f0859f
Q The DetailDaemon sampler is used for enhancing audio detail. How does it work compared to standard audio diffusion samplers, and what settings would you recommend for generating a cinematic soundscape?
NODES ['DetailDaemonSamplerNode', 'KSampler', 'SamplerCustom', 'BasicScheduler']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Explain how DetailDaemon changes the sampling/detail path versus the standard KSampler path, and give cinematic-soundscape settings with trade-offs rather than unsupported magic values.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-animatediff-image-to-video-with-latent-composi-17dc9b
Q How does the latent compositing approach here compare to using an init image directly in the video latent space? Which gives better temporal coherence?
NODES ['LatentComposite', 'VAEEncode', 'EmptyLatentImage', 'AnimateDiffLoaderV1', 'KSampler']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', "Compare the graph's encoded-image LatentComposite path with direct init-image conditioning, including where each anchors structure and the likely temporal-coherence trade-off.", 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-dual-checkpoint-xl-image-generation-with-refin-c9df19
Q I'm running this dual-checkpoint XL pipeline with juggernautXL as the base and sd_xl_refiner as the refiner. Are there any newer, better refiner models I should consider, and what are the tradeoffs between using a dedicated refiner vs. a single high-quality XL checkpoint that handles fine details natively? I'm particularly interested in how the LoRA timing (before or after the refiner) affects flexibility.
NODES ['CheckpointLoaderSimple', 'KSamplerAdvanced', 'Power Lora Loader (rgthree)', 'VAEDecode']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Describe the base/refiner handoff visible in the two-checkpoint/two-sampler graph, compare current refiner or single-checkpoint options, and address whether LoRA is applied before or after the handoff.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-gemini-prompt-splitter-and-text-display-workfl-caae97
Q This workflow uses Gemini to process and split prompts. I'd like to compare Gemini to Claude for generating complex, multi-part image prompts. What are the trade-offs in terms of output quality, prompt structure, rate limits, and cost? Just research, don't modify the workflow.
NODES ['GeminiNode', 'VRGDG_PromptSplitter_General', 'StringConcatenate', 'ShowText|pysssss']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Compare Gemini and Claude for this multi-part prompt-generation role across output structure/quality, rate limits, and cost, while clearly separating graph facts from time-sensitive provider facts.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-image-processing-with-sharpening-film-grain-an-9aa0f1
Q What alternative sharpening methods could replace the high pass filter in this workflow, and what are the tradeoffs in terms of edge halos vs. natural detail enhancement?
NODES ['Image High Pass Filter', 'VividSharpenV2', 'Image Filter Adjustments', 'ImageBlend', 'BetterFilmGrain']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Name viable replacements for the current high-pass branch and compare halo risk, local contrast, noise amplification, masking, and blend-strength control in this graph.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-image-to-image-with-ipadapter-and-controlnet-1999a9
Q How can I balance the influence between the IPAdapter style reference and the Canny edge ControlNet strength to preserve more of the original image structure while still applying the desired style? What parameters control this interplay?
NODES ['IPAdapterApply', 'Canny', 'ControlNetApply', 'ControlNetLoader', 'KSampler']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Identify the concrete IPAdapter and Canny/ControlNet influence controls, explain their interaction, and recommend a tuning order that preserves structure without eliminating style transfer.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-llava-image-captioning-and-keyword-extraction-d38dc8
Q What alternative image captioning models could I replace LLaVA with to produce longer, more detailed prompts? Are there any that also extract keywords directly, or should I keep separate steps?
NODES ['LLavaPromptGenerator', 'LLavaSamplerSimple', 'KeywordExtraction', 'JsonToText', 'Suggester']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', "Compare named captioning alternatives for longer detailed prompts and decide, with trade-offs, whether keyword extraction can be combined or should remain the graph's separate step.", 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID image-qwen-image-inpainting-with-controlnet-09fc64
Q For this Qwen Image inpainting workflow, I frequently get color mismatches between the inpainted area and the original image. Before editing anything, research the best techniques to improve color consistency specifically for ControlNet-based inpainting with Qwen-Image-Lightning. Also explore if there's a better method for mask feathering or blending that could reduce the mismatch.
NODES ['ControlNetInpaintingAliMamaApply', 'ImagePadForOutpaint', 'VAEEncode', 'KSampler', 'VAEDecode']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Recommend Qwen-Image-Lightning/ControlNet color-consistency and mask-edge techniques that map to this encode/control/sample/decode pipeline, including feathering or compositing checks and relevant trade-offs.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-3d-gaussian-splatting-from-video-with-hunyuan-432652
Q The 3D reconstruction has noticeable geometry flickering across frames, likely from inconsistent depth maps. Can you investigate this video-to-3D Gaussian Splatting pipeline and suggest alternative depth estimation approaches or stabilization techniques that could reduce temporal jitter in the output point cloud?
NODES ['PreprocessImagesForHWM', 'HWMInference', 'VisualizeDepth', 'Save3DGaussians', 'SavePointCloud']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', "Tie temporal geometry jitter to the workflow's preprocessing/depth-inference path and compare concrete temporally stable depth, camera, filtering, or point-cloud stabilization strategies.", 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-ai-video-upscaling-with-detail-daemon-sampler-673197
Q I'm using the Detail Daemon Sampler with beta scheduling to upscale a low-res video. The output has strong color shifting compared to the input, and details look smeared rather than enhanced. I've tried different SeedVR2 checkpoints but the issue persists. Where should I look?
NODES ['SeedVR2VideoUpscaler', 'DetailDaemonSamplerNode', 'BetaSamplingScheduler', 'Sigmas Rescale', 'VAEDecode']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Prioritize plausible causes of both color shift and smeared detail in the SeedVR2/detail-daemon/sigma/VAE chain, and give discriminating checks before recommending parameter changes.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-animated-image-to-video-with-svd-and-lora-4ed6d9
Q Walk me through the entire pipeline of this workflow from loading the input image to generating the WEBP video. I want to understand why there are two KSampler stages and how the SVD model conditions the generated frames. Also explain how the LoRA augmentation fits in.
NODES ['ImageOnlyCheckpointLoader', 'SVD_img2vid_Conditioning', 'LoraLoader', 'KSampler', 'SaveAnimatedWEBP']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Trace the actual image-to-SVD-conditioning-to-sampling-to-WEBP flow, distinguish the two KSampler stages, and state where the LoRA-modified model enters.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-animatediff-video-generation-with-controlnet-a7e2af
Q My current workflow uses a standard UNet-based Stable Diffusion checkpoint with AnimateDiff. What would be the trade-offs if I switched to a DiT-based model (e.g., SD3 or PixArt) for better motion consistency and temporal coherence? Specifically, how would ControlNet integration differ, and what performance or quality changes should I expect?
NODES ['CheckpointLoaderSimple', 'ADE_AnimateDiffLoaderWithContext', 'ControlNetLoaderAdvanced', 'ControlNetApplyAdvanced', 'KSampler']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Compare the current UNet/AnimateDiff/ControlNet integration with a DiT migration, covering model/control compatibility, motion coherence, compute, and likely graph changes without pretending it is a drop-in swap.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-audio-to-image-mel-band-roformer-workflow-b22937
Q Can you explain step-by-step what this audio-to-image workflow does, how the MelBandRoFormer model fits in, and why it both saves an MP3 and outputs a preview image?
NODES ['LoadAudio', 'MelBandRoFormerModelLoader', 'MelBandRoFormerSampler', 'SaveAudioMP3', 'PreviewImage']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Trace the audio through MelBandRoFormer and explain separately why an MP3 is saved and why an image preview is produced, based on the actual output branches.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-flux2-image-and-video-generation-with-outpaint-435de2
Q The outpainted borders look noticeably brighter than the original image, even after color matching is applied. Why is the color matching node not aligning the luminance, and which specific node or setting is likely causing this mismatch?
NODES ['ImagePadForOutpaint', 'DrawMaskOnImage', 'ReferenceLatent', 'VAEDecode', 'ColorMatch', 'ImageCompare']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Locate ColorMatch relative to generation/decoding/compositing, identify a graph-supported luminance mismatch mechanism, and propose checks that distinguish bad reference/mask/range settings from a broken color-match node.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-svd-image-to-video-with-animation-builder-99e2a9
Q The generated video has severe flickering and jittery motion, with frames occasionally going black. What in the workflow could be causing this?
NODES ['SVD_img2vid_Conditioning', 'KSampler', 'Animation Builder (mtb)', 'Get Batch From History (mtb)', 'Export With Ffmpeg (mtb)']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Rank workflow-specific causes for flicker, jitter, and black frames across conditioning, sampling, batch-history selection, animation assembly, and export, with a test that isolates each leading cause.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-svd-image-to-video-with-sdxl-conditioning-389d90
Q Can you explain how each stage of this workflow contributes to generating the final WEBP video, particularly the role of the CLIP text conditioning and how the SVD model uses the input image and text prompt together to determine motion?
NODES ['CheckpointLoaderSimple', 'CLIPTextEncode', 'ImageOnlyCheckpointLoader', 'SVD_img2vid_Conditioning', 'KSampler', 'SaveAnimatedWEBP']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', "Trace every major stage to the WEBP output and accurately distinguish SDXL text conditioning from SVD's image/motion conditioning instead of claiming unsupported direct text control of SVD.", 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14
Q Explain how the Wan2.2 Lightning model and LoRA adapters work together in this workflow. What is the purpose of having two LoRA strength settings?
NODES ['DiffusionModelLoaderKJ', 'LoraLoaderModelOnly', 'ModelSamplingSD3', 'KSamplerAdvanced', 'EmptyHunyuanLatentVideo']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Explain how the Lightning model patch and LoRA loaders feed sampling, and disambiguate the two strength controls by identifying what each applies to in this graph.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6
Q The generated video has a visible, frame‑varying flicker in the film grain overlay, giving it a disjointed look. Which part of the post‑processing stack is introducing this temporal inconsistency?
NODES ['VAEDecode', 'FastUnsharpSharpen', 'FastFilmGrain', 'SaveImage', 'Image Comparer (rgthree)']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Identify the frame-varying grain source in the post-process branch, explain why independent/random per-frame grain flickers, and distinguish it from sharpening or model-sampling artifacts.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-animatediff-video-to-video-with-controlnet-and-3c978e
Q I'm trying to understand how this AnimateDiff video-to-video workflow keeps motion coherent across frames. Walk me through the pipeline end-to-end, focusing on where the ControlNets, LoRAs, and KSampler interact to preserve temporal consistency.
NODES ['VHS_LoadVideo', 'VAEEncode', 'ControlNetLoaderAdvanced', 'ControlNetApply', 'LoraLoader', 'ADE_AnimateDiffLoaderWithContext', 'KSampler', 'VHS_VideoCombine']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Walk the connected video-to-latent, ControlNet/LoRA/AnimateDiff model-conditioning, KSampler, decode, and combine path and explain which mechanisms preserve spatial versus temporal consistency.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-animatediff-video-with-controlnet-and-depth-89b02a
Q What alternatives to Depth-Anything could I use as the depth estimator for better temporal consistency in my AnimateDiff video pipeline, and how would replacing it affect the ControlNet guidance?
NODES ['DownloadAndLoadDepthAnythingV2Model', 'DepthAnything_V2', 'ControlNetLoader', 'ACN_AdvancedControlNetApply_v2', 'ADE_UseEvolvedSampling']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Compare named depth estimators or temporal-depth strategies and explain how their output normalization/stability must match the existing ControlNet guidance path.', 'Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-animatediff-video-with-ipadapter-and-controlne-4eebf3
Q The output video has a persistent tiling grid pattern visible in uniform areas like sky or walls, as if the IPAdapter style is being applied in blocks rather than smoothly. Which node and setting is the likely culprit?
NODES ['IPAdapterTiled', 'IPAdapterUnifiedLoader', 'ImageResize+', 'ACN_AdvancedControlNetApply', 'SamplerCustom']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Test the tiling hypothesis against IPAdapterTiled and its tile/weight/application settings, explain the grid mechanism, and distinguish it from resize, ControlNet, VAE, or codec artifacts.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-hunyuan-video-text-to-video-generation-265847
Q The generated animated WEBP has severe flickering between frames, especially in high-motion areas, but the first frame looks fine. What in the workflow could be causing this temporal inconsistency?
NODES ['EmptyHunyuanLatentVideo', 'BasicScheduler', 'SamplerCustomAdvanced', 'VAEDecodeTiled', 'SaveAnimatedWEBP']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Prioritize causes that can affect later/high-motion frames while sparing the first, grounding the diagnosis in latent length/schedule/sampling/tiled decode/WEBP settings and proposing isolating checks.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-hunyuanvideo-image-to-video-generation-with-en-ff076a
Q The generated video doesn't resemble my input image at all — the first frame is completely different, and the video looks like random noise. I suspect the image encoding or conditioning is broken.
NODES ['LoadImageFromUrl', 'ImageResizeKJ', 'HyVideoI2VEncode', 'HyVideoEncode', 'SetLatentNoiseMask', 'HyVideoSampler', 'HyVideoDecode']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Trace the image-conditioning and latent/noise-mask path, identify concrete disconnections or incompatible encoding/settings that could discard the first frame, and give ordered verification steps.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-image-to-video-with-svd-and-webp-output-1882aa
Q Walk me through this workflow: how does it turn a static image into a moving video and save it as WebP? I'm especially curious how the Stable Video Diffusion conditioning and linear CFG guidance are set up.
NODES ['LoadImage', 'ImageOnlyCheckpointLoader', 'SVD_img2vid_Conditioning', 'VideoLinearCFGGuidance', 'KSampler', 'VAEDecode', 'SaveAnimatedWEBP']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Trace the static image through SVD conditioning, CFG-guided sampling, decode, and WebP save, explaining the distinct roles and the motion-related SVD controls.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-inpaint-and-video-composition-with-spline-path-0c2716
Q What role does the spline editor play in this inpainting-and-compositing workflow? Explain how the path controls the inpainting mask over time and how the final video frames are assembled from the processed results.
NODES ['SplineEditor', 'CutAndDragOnPath', 'INPAINT_LoadInpaintModel', 'INPAINT_InpaintWithModel', 'VHS_MergeImages', 'VHS_VideoCombine']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Explain how spline coordinates drive the moving mask/cut path, how inpainting consumes image and mask, and how merge/combine nodes assemble the final frames without inventing absent tracking stages.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-ltx-video-with-audio-and-inpainting-b3ba8a
Q The inpainted region looks sharp-edged and doesn't blend smoothly with the rest of the video, and the colors in that region are completely off (grayish). What's going wrong?
NODES ['ImageToMask', 'GrowMaskWithBlur', 'InvertMask', 'LatentInpaintTTM', 'LTXVImgToVideoInplace', 'ImageBlend', 'VAEDecodeTiled']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Connect sharp edges to the mask grow/blur/invert route and gray color to latent/encode/decode/blend compatibility, then give checks that separately isolate mask geometry and color-space/latent issues.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-seedvr2-video-upscaling-workflow-052e59
Q Walk me through what each major stage does: how the video frames are loaded, what the VAE and DiT models contribute, and how the final upscaled video is assembled. I want to understand the full pipeline.
NODES ['LoadVideo', 'GetVideoComponents', 'SeedVR2LoadDiTModel', 'SeedVR2LoadVAEModel', 'SeedVR2VideoUpscaler', 'CreateVideo', 'SaveVideo']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Trace video loading/component extraction through the SeedVR2 DiT and VAE upscaler to video creation/save, accurately separating model restoration from VAE encoding/decoding and container assembly.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-video-loading-and-saving-workflow-1c7ad8
Q This workflow loads a video and an image, applies boolean logic, and saves three separate video outputs. Explain what each boolean operation is doing and how the three resulting videos differ from one another.
NODES ['LoadVideo', 'LoadImage', 'PrimitiveBoolean', 'SaveVideo', '2dc75cab-e957-4437-a5bb-2afb0ea00516', '3ad0b41c-8c47-4e10-a53e-ed340cc26b5f', 'b83ac947-e174-4a8e-b0c1-f7c3b8f00419']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Use the three custom-node connections and shared boolean inputs to explain each operation/output distinctly; unknown UUID node semantics must be derived from metadata/connections or stated as uncertain, not guessed.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-video-output-workflow-f855de
Q The final output video is unacceptably blurry and shows heavy banding in dark areas, even though no explicit blur or compression step is visible in the node graph. I need you to inspect the custom nodes and connections to identify what's causing this loss of detail.
NODES ['SaveVideo', '1cef296e-0f57-4f74-9e5e-7fe2b9097bcf', '61c3c7e8-7a92-4f27-8c3f-82eb62976f7b', '94adb7a7-527b-4ea8-92e0-9ab2ca8387c4']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Inspect the opaque custom-node metadata/settings and connections before naming a culprit for blur/banding; distinguish processing/range/bit-depth loss from SaveVideo codec settings and flag any unresolved UUID semantics.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-wan-video-generation-with-vace-and-multi-outpu-d1caec
Q The video output has severe temporal flickering and only the first image in my batch produces a coherent result — the rest are pure noise. What's causing this?
NODES ['ImageBatch', 'ImageBatchMulti', 'GetImageRangeFromBatch', 'ReverseImageBatch', 'WanVaceToVideo', 'TrimVideoLatent', 'KSamplerAdvanced']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Explain why only the first batch item might be coherent by tracing batch slicing/order into VACE conditioning and latent length/masks, and separate that from global sampling causes of temporal flicker.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9
Q The high-noise LoRA variant produces outputs that look identical to the low-noise variant — no difference in motion or texture. Also, the video appears to have incorrect brightness/contrast, as if the latent scaling is off.
NODES ['UnetLoaderGGUF', 'LoraLoaderModelOnly', 'KSamplerAdvanced', 'Frames Concat Latent', 'LatentLoaderAdvanced', 'SetLatentNoiseMask', 'VAEDecode']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Verify whether the high/low LoRA branches actually reach distinct model/sampling paths and diagnose brightness through latent concat/load/noise-mask/decode scaling, with tests for bypassed or identical inputs.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3
Q Explain how this workflow uses the high and low noise variants of Wan2.2 differently. I'm confused about why there are two separate generation paths and how their outputs are combined or selected.
NODES ['UNETLoader', 'ModelSamplingSD3', 'KSamplerAdvanced', 'EmptyHunyuanLatentVideo', 'VAEDecode', 'SaveAnimatedWEBP', 'SaveWEBM']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Describe the two loaded model/sampling paths from high-noise to low-noise stages and state whether the graph chains, combines, or merely exposes alternatives, based on actual edges rather than the title.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a
Q Can you explain the dual-UNet staging in this Wan2.2 pipeline? Specifically, how do the high-noise and low-noise models divide the sampling work, and where does the LoRA get applied to improve output quality?
NODES ['UNETLoader', 'LoraLoaderModelOnly', 'ModelSamplingSD3', 'KSamplerAdvanced', 'CreateVideo', 'SaveVideo']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Explain the sigma/noise-range handoff between the two UNet sampler stages and identify exactly where each LoRA-modified model is applied before decode/output.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9
Q The animation looks great for the first 16 frames, but then the motion becomes erratic and the subject’s appearance shifts noticeably. What could be causing this degradation?
NODES ['UNETLoader', 'LoraLoader', 'SwarmKSampler', 'SwarmTrimFrames', 'LatentUpscaleBy', 'SwarmSaveAnimationWS']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Tie degradation after frame 16 to explicit frame-window/trim/upscale or staged-sampling settings where supported, and give checks that distinguish context-boundary drift from LoRA/model or save artifacts.', 'Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']
ID video-wanvideo-text-to-video-generation-71f825
Q How does the WanVideo text-to-video pipeline turn a prompt into a video clip? Walk me through the flow from the T5 and CLIP encoders through sampling to the final output, and explain how the model learns to generate motion across frames.
NODES ['LoadWanVideoT5TextEncoder', 'LoadWanVideoClipTextEncoder', 'WanVideoTextEncode', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoDecode', 'VHS_VideoCombine']
CRIT ['Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.', 'Trace T5 and CLIP inputs through WanVideo text encoding, model sampling, VAE decode, and combine, accurately explaining conditioning and latent temporal generation without claiming the encoders themselves generate motion.', 'Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.', "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ['hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer']

exec
/bin/zsh -lc 'git diff 0f015101..b39f0c91 -- tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json && for f in tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json; do nl -ba "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 50ms:
diff --git a/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json b/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
index f56d2f9d..3af2ad55 100644
--- a/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
+++ b/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
@@ -1,17 +1,17 @@
 {
   "id": "multi-3d-preview-and-image-output-workflow-d93baf",
-  "query": "Switch the first preview to a top\u2011down view of the 3D model.",
+  "query": "Change the SaveGLB filename prefix from '3d/ComfyUI' to '3d/moge-top-down'. Keep the mesh input and both normal-map preview branches unchanged.",
   "workflow_path": "external_workflows/corpus/d93baf73c8a43f57.json",
   "network": true,
   "timeout": 320,
   "apply": true,
   "assessment": {
-    "expect_graph_changed": false
+    "expect_graph_changed": true
   },
   "desired": {
-    "outcome": "First preview renders the 3D model from directly above.",
-    "quality": "GLB file still saves correctly; second preview unchanged; no dangling nodes.",
-    "alternatives_ok": true
+    "outcome": "The generated mesh is saved under the 3d/moge-top-down filename prefix.",
+    "quality": "Only SaveGLB's filename prefix changes; its mesh input remains connected and the normal_opengl and normal_directx PreviewImage branches are untouched.",
+    "alternatives_ok": false
   },
   "_tags": {
     "modality": "multi",
@@ -33,5 +33,8 @@
     "staged": true,
     "authored_by": "deepseek-v4-pro",
     "author_rationale": "Specific, simple edit that tests parameter change without breaking the 3D pipeline."
+  },
+  "classification": {
+    "kind": "edit"
   }
 }
diff --git a/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json b/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
index 129cfe8b..99562d06 100644
--- a/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
+++ b/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
@@ -1,16 +1,16 @@
 {
   "id": "video-image-to-video-conversion-with-moonvalley-d7853c",
-  "query": "The video output is way too short; I need it to be at least 5 seconds long. Increase the frame count accordingly and adjust the frame rate to keep motion smooth.",
+  "query": "Reduce the Moonvalley image-to-video generation steps from 100 to 80 for a faster preview. Keep prompt adherence at 7, and leave the prompt, resolution, image input, and SaveVideo connection unchanged.",
   "workflow_path": "external_workflows/corpus/d7853cd7421f9ebc.json",
   "network": true,
   "timeout": 280,
   "apply": true,
   "assessment": {
-    "expect_graph_changed": false
+    "expect_graph_changed": true
   },
   "desired": {
-    "outcome": "Output video is 5 seconds long with smooth motion at an appropriate frame rate.",
-    "quality": "Frame count and fps parameters are correctly updated, no nodes are broken, and the save node outputs the new duration video.",
+    "outcome": "The Moonvalley node uses 80 generation steps for a faster preview.",
+    "quality": "Only the generation-step count changes from 100 to 80; prompt adherence remains 7 and the image input, prompt, 16:9 resolution, seed controls, and SaveVideo wiring remain intact.",
     "alternatives_ok": false
   },
   "_tags": {
@@ -32,5 +32,8 @@
     "staged": true,
     "authored_by": "deepseek-v4-flash",
     "author_rationale": "A simple, concrete parameter edit that requires reasoning about frame count vs. fps to hit a target duration."
+  },
+  "classification": {
+    "kind": "edit"
   }
 }
diff --git a/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json b/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
index b61b9bfb..bc4fc210 100644
--- a/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
+++ b/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
@@ -1,17 +1,17 @@
 {
   "id": "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
-  "query": "Lower the inpainting denoising strength to 0.6 to preserve more original image details around the dragged region",
+  "query": "Set the INPAINT_InpaintWithModel seed to 42 and keep seed control fixed. Do not alter the spline, cut-and-drag, or video-combine stages.",
   "workflow_path": "external_workflows/corpus/485ff2fa6dcc1917.json",
   "network": true,
   "timeout": 280,
   "apply": true,
   "assessment": {
-    "expect_graph_changed": false
+    "expect_graph_changed": true
   },
   "desired": {
-    "outcome": "The inpainting blends more conservatively, keeping more of the source pixels intact and reducing visible seams around the cut-and-drag area.",
-    "quality": "The denoising strength parameter on the inpainting node is correctly identified and set to 0.6; spline-editing and video-combine stages are untouched and functional.",
-    "alternatives_ok": true
+    "outcome": "The inpainting stage uses deterministic seed 42 while the surrounding spline-driven composite remains unchanged.",
+    "quality": "INPAINT_InpaintWithModel is updated from seed 534667941392889 to 42 with fixed seed control; spline editing, cut-and-drag, and video combine remain connected and functional.",
+    "alternatives_ok": false
   },
   "_tags": {
     "modality": "video",
@@ -33,5 +33,8 @@
     "staged": true,
     "authored_by": "deepseek-v4-pro",
     "author_rationale": "This targets a specific technique in the spline-cut-and-drag pipeline (inpainting blend) and tests whether the agent can distinguish it from generic model settings."
+  },
+  "classification": {
+    "kind": "edit"
   }
 }
     1	{
     2	  "id": "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
     3	  "query": "Set the INPAINT_InpaintWithModel seed to 42 and keep seed control fixed. Do not alter the spline, cut-and-drag, or video-combine stages.",
     4	  "workflow_path": "external_workflows/corpus/485ff2fa6dcc1917.json",
     5	  "network": true,
     6	  "timeout": 280,
     7	  "apply": true,
     8	  "assessment": {
     9	    "expect_graph_changed": true
    10	  },
    11	  "desired": {
    12	    "outcome": "The inpainting stage uses deterministic seed 42 while the surrounding spline-driven composite remains unchanged.",
    13	    "quality": "INPAINT_InpaintWithModel is updated from seed 534667941392889 to 42 with fixed seed control; spline editing, cut-and-drag, and video combine remain connected and functional.",
    14	    "alternatives_ok": false
    15	  },
    16	  "_tags": {
    17	    "modality": "video",
    18	    "query_type": "edit",
    19	    "abstraction": "low",
    20	    "complexity": "low",
    21	    "manifest_complexity": 2,
    22	    "task_type": "inpainting",
    23	    "requires_custom_nodes": true,
    24	    "techniques": [
    25	      "video-inpainting",
    26	      "spline-editing",
    27	      "cut-and-drag",
    28	      "image-inpainting",
    29	      "video-combine"
    30	    ],
    31	    "source_workflow_id": "485ff2fa6dcc1917",
    32	    "source": "external_workflows/corpus",
    33	    "staged": true,
    34	    "authored_by": "deepseek-v4-pro",
    35	    "author_rationale": "This targets a specific technique in the spline-cut-and-drag pipeline (inpainting blend) and tests whether the agent can distinguish it from generic model settings."
    36	  },
    37	  "classification": {
    38	    "kind": "edit"
    39	  }
    40	}
     1	{
     2	  "id": "video-image-to-video-conversion-with-moonvalley-d7853c",
     3	  "query": "Reduce the Moonvalley image-to-video generation steps from 100 to 80 for a faster preview. Keep prompt adherence at 7, and leave the prompt, resolution, image input, and SaveVideo connection unchanged.",
     4	  "workflow_path": "external_workflows/corpus/d7853cd7421f9ebc.json",
     5	  "network": true,
     6	  "timeout": 280,
     7	  "apply": true,
     8	  "assessment": {
     9	    "expect_graph_changed": true
    10	  },
    11	  "desired": {
    12	    "outcome": "The Moonvalley node uses 80 generation steps for a faster preview.",
    13	    "quality": "Only the generation-step count changes from 100 to 80; prompt adherence remains 7 and the image input, prompt, 16:9 resolution, seed controls, and SaveVideo wiring remain intact.",
    14	    "alternatives_ok": false
    15	  },
    16	  "_tags": {
    17	    "modality": "video",
    18	    "query_type": "edit",
    19	    "abstraction": "low",
    20	    "complexity": "low",
    21	    "manifest_complexity": 1,
    22	    "task_type": "other",
    23	    "requires_custom_nodes": true,
    24	    "techniques": [
    25	      "image-to-video",
    26	      "moonvalley",
    27	      "video-generation",
    28	      "custom-node"
    29	    ],
    30	    "source_workflow_id": "d7853cd7421f9ebc",
    31	    "source": "external_workflows/corpus",
    32	    "staged": true,
    33	    "authored_by": "deepseek-v4-flash",
    34	    "author_rationale": "A simple, concrete parameter edit that requires reasoning about frame count vs. fps to hit a target duration."
    35	  },
    36	  "classification": {
    37	    "kind": "edit"
    38	  }
    39	}
     1	{
     2	  "id": "multi-3d-preview-and-image-output-workflow-d93baf",
     3	  "query": "Change the SaveGLB filename prefix from '3d/ComfyUI' to '3d/moge-top-down'. Keep the mesh input and both normal-map preview branches unchanged.",
     4	  "workflow_path": "external_workflows/corpus/d93baf73c8a43f57.json",
     5	  "network": true,
     6	  "timeout": 320,
     7	  "apply": true,
     8	  "assessment": {
     9	    "expect_graph_changed": true
    10	  },
    11	  "desired": {
    12	    "outcome": "The generated mesh is saved under the 3d/moge-top-down filename prefix.",
    13	    "quality": "Only SaveGLB's filename prefix changes; its mesh input remains connected and the normal_opengl and normal_directx PreviewImage branches are untouched.",
    14	    "alternatives_ok": false
    15	  },
    16	  "_tags": {
    17	    "modality": "multi",
    18	    "query_type": "edit",
    19	    "abstraction": "low",
    20	    "complexity": "low",
    21	    "manifest_complexity": 2,
    22	    "task_type": "other",
    23	    "requires_custom_nodes": true,
    24	    "techniques": [
    25	      "3d",
    26	      "glb",
    27	      "image-loading",
    28	      "preview",
    29	      "save"
    30	    ],
    31	    "source_workflow_id": "d93baf73c8a43f57",
    32	    "source": "external_workflows/corpus",
    33	    "staged": true,
    34	    "authored_by": "deepseek-v4-pro",
    35	    "author_rationale": "Specific, simple edit that tests parameter change without breaking the 3D pipeline."
    36	  },
    37	  "classification": {
    38	    "kind": "edit"
    39	  }
    40	}

exec
/bin/zsh -lc "python -c '
import json
from pathlib import Path
for sid,fp,terms in [
(\"485ff2\",\"external_workflows/corpus/485ff2fa6dcc1917.json\",[\"INPAINT_InpaintWithModel\",\"SplineEditor\",\"CutAndDragOnPath\",\"VHS_VideoCombine\"]),
(\"d7853c\",\"external_workflows/corpus/d7853cd7421f9ebc.json\",[\"Moonvalley\",\"SaveVideo\"]),
(\"d93baf\",\"external_workflows/corpus/d93baf73c8a43f57.json\",[\"SaveGLB\",\"PreviewImage\"]),]:
 d=json.loads(Path(fp).read_text()); print(\"WORKFLOW\",sid)
 nodes=d.get(\"nodes\") or d.get(\"workflow\",{}).get(\"nodes\") or []
 for n in nodes:
  typ=str(n.get(\"type\", \"\")); title=str(n.get(\"title\", \"\"))
  if any(t.lower() in (typ+\" \"+title).lower() for t in terms):
   print({k:n.get(k) for k in [\"id\",\"type\",\"title\",\"widgets_values\",\"inputs\",\"outputs\"]})
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 625ms:
WORKFLOW 485ff2
Traceback (most recent call last):
  File "<string>", line 11, in <module>
AttributeError: 'str' object has no attribute 'get'

exec
/bin/zsh -lc "python -c '
import json
from pathlib import Path
for fp in [\"external_workflows/corpus/485ff2fa6dcc1917.json\",\"external_workflows/corpus/d7853cd7421f9ebc.json\",\"external_workflows/corpus/d93baf73c8a43f57.json\"]:
 d=json.loads(Path(fp).read_text()); print(fp,type(d).__name__, list(d)[:20] if isinstance(d,dict) else len(d)); print({k:type(v).__name__ for k,v in d.items()} if isinstance(d,dict) else \"\")
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 713ms:
external_workflows/corpus/485ff2fa6dcc1917.json dict ['edges', 'groups', 'id', 'inputs', 'metadata', 'nodes', 'outputs', 'requirements', 'source', 'strict_types', 'vibecomfy_format_version']
{'edges': 'list', 'groups': 'list', 'id': 'str', 'inputs': 'dict', 'metadata': 'dict', 'nodes': 'dict', 'outputs': 'list', 'requirements': 'dict', 'source': 'dict', 'strict_types': 'bool', 'vibecomfy_format_version': 'str'}
external_workflows/corpus/d7853cd7421f9ebc.json dict ['edges', 'groups', 'id', 'inputs', 'metadata', 'nodes', 'outputs', 'requirements', 'source', 'strict_types', 'vibecomfy_format_version']
{'edges': 'list', 'groups': 'list', 'id': 'str', 'inputs': 'dict', 'metadata': 'dict', 'nodes': 'dict', 'outputs': 'list', 'requirements': 'dict', 'source': 'dict', 'strict_types': 'bool', 'vibecomfy_format_version': 'str'}
external_workflows/corpus/d93baf73c8a43f57.json dict ['edges', 'groups', 'id', 'inputs', 'metadata', 'nodes', 'outputs', 'requirements', 'source', 'strict_types', 'vibecomfy_format_version']
{'edges': 'list', 'groups': 'list', 'id': 'str', 'inputs': 'dict', 'metadata': 'dict', 'nodes': 'dict', 'outputs': 'list', 'requirements': 'dict', 'source': 'dict', 'strict_types': 'bool', 'vibecomfy_format_version': 'str'}

exec
/bin/zsh -lc "python -c '
import json
from pathlib import Path
for sid,fp,terms in [
(\"485ff2\",\"external_workflows/corpus/485ff2fa6dcc1917.json\",[\"INPAINT_InpaintWithModel\",\"SplineEditor\",\"CutAndDragOnPath\",\"VHS_VideoCombine\"]),
(\"d7853c\",\"external_workflows/corpus/d7853cd7421f9ebc.json\",[\"Moonvalley\",\"SaveVideo\"]),
(\"d93baf\",\"external_workflows/corpus/d93baf73c8a43f57.json\",[\"SaveGLB\",\"PreviewImage\"]),]:
 d=json.loads(Path(fp).read_text()); print(\"WORKFLOW\",sid)
 for nid,n in d[\"nodes\"].items():
  typ=str(n.get(\"class_type\",n.get(\"type\",\"\"))); title=str(n.get(\"title\",\"\")); blob=json.dumps(n)
  if any(t.lower() in (typ+\" \"+title+\" \"+blob).lower() for t in terms):
   print(nid,json.dumps(n,indent=2)[:6000])
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 721ms:
WORKFLOW 485ff2
10 {
  "class_type": "CutAndDragOnPath",
  "id": "10",
  "inputs": {},
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 10,
      "inputs": [
        {
          "link": 22,
          "name": "image",
          "type": "IMAGE"
        },
        {
          "link": 10,
          "name": "mask",
          "type": "MASK"
        },
        {
          "link": 14,
          "name": "coordinates",
          "type": "STRING",
          "widget": {
            "name": "coordinates"
          }
        },
        {
          "link": 24,
          "name": "bg_image",
          "shape": 7,
          "type": "IMAGE"
        }
      ],
      "mode": 0,
      "order": 4,
      "outputs": [
        {
          "links": [
            17
          ],
          "name": "image",
          "slot_index": 0,
          "type": "IMAGE"
        },
        {
          "links": [],
          "name": "mask",
          "slot_index": 1,
          "type": "MASK"
        }
      ],
      "pos": [
        8.958178520202637,
        395.44854736328125
      ],
      "properties": {
        "Node name for S&R": "CutAndDragOnPath"
      },
      "size": [
        315,
        166
      ],
      "type": "CutAndDragOnPath",
      "widgets_values": [
        "",
        1024,
        768,
        false
      ]
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 4,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      "",
      1024,
      768,
      false
    ]
  },
  "uid": "10",
  "widgets": {
    "widget_0": "",
    "widget_1": 1024,
    "widget_2": 768,
    "widget_3": false
  }
}
12 {
  "class_type": "SplineEditor",
  "id": "12",
  "inputs": {},
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 12,
      "inputs": [
        {
          "link": 12,
          "name": "bg_image",
          "shape": 7,
          "type": "IMAGE"
        }
      ],
      "mode": 0,
      "order": 2,
      "outputs": [
        {
          "links": null,
          "name": "mask",
          "type": "MASK"
        },
        {
          "links": [
            14
          ],
          "name": "coord_str",
          "slot_index": 1,
          "type": "STRING"
        },
        {
          "links": [],
          "name": "float",
          "slot_index": 2,
          "type": "FLOAT"
        },
        {
          "links": null,
          "name": "count",
          "type": "INT"
        },
        {
          "links": null,
          "name": "normalized_str",
          "type": "STRING"
        }
      ],
      "pos": [
        -688.39111328125,
        700.787353515625
      ],
      "properties": {
        "Node name for S&R": "SplineEditor",
        "imgData": {
          "base64": [
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAMABAADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDwokUA8YzTaUZ4oEA4cVO6LJAW/jU9h1FREbWB7GpBu8tsZyv8qBj7BQJgW644q/IeapWfzTDjlc5NXH5NXHYzluR5prGnkVEetWIQmm5p2KaRUjG0UUUDFopKKAFzUiGoqkShCZOtPBpgp6iqJHUuKUClPFMQg4NSqah709c0AJcx7kNYjja5FdIFDoRWLfQ7JCcVM0VB9CGF/mrVgfisRTg5rRtphgc0osckXZm+Q1jT8vWnM4KcVlSnL0SFEZmnUmKWpNAzSZo60uKAAGjNAHNBFACDrT+1IBS5pCG80qk5oxSquWFAy9BxitGFuKzQCqZqeCbtVQepM1oaBPFZ90etXN2VrPuWycVbM4kUWS1aEYwtVraPNXsADFEUOTGY5oIqSkxVEkVLTytJigYylWnhcmnbMUAIKmXG2o8U9TxQIaR81WUC7MHrVfODUhYEUARsfmNJTtuTS7aBDQOakC5FIFwauW0O+gGxtvuRhgVoBZXXIQ/lV7TtNWaZRjqa9C0vwxE8IygP4U9iL3PJ5EZeqkfhVOSvXNW8HoUZlXt2Febavpj2UzKRwKYJmE/WoWqeQc1CwqTRELGkpzU2kULTlptSRjmgRYhHIrpdJVWABxXOotbelOyOPSrREjcuNOWVMqK56/szCTXWxygpmsXVyGzVNEJnJSjBqlP3rRmHzGqM61kzVGXJw1NzT5fvVHWZsLRRRQAoq7aLmqVXLWQLTW4nsaqrhajdgKja4AWqzTFmq7maRKzZNNNKgyKVhSGLHVuMVBEtWVXimJkobAoDk0zbzVmKPI5piIdpZgK1ra0TywcZNVRCC4xWjEWVcAUCZTuoQnSqDGtC8ZyDkYFZrZoBCDmq10ODVjOKguOVpMpGNKMMajqaYfNUNZs1QUtJS0hhmpYuWqKpofvUITNS3HAq3nioLccVOR2rZGL3BW4qRDSGFlIGOTTxEyDmpasNO5IORVeVeanVsCoZTmkNFNhzRGheRVHUmlbk1LakLcIfeoNUeh+GQlvbKCw6c1oatqCRxkBhmuRWRoyNjkcdjRI8kn3mJpMLDJpPMdmPeoSKkK0bak0RCRTo22mlYYpgGTSZSRaVtxFWUiLdBUVqmWArftbdAo4rORrEl0i3YEYrttP0tpwPSue06MLKOK9B0vasKj1rBrU2vZFSPw2rmr0fh8xrw4raiAxxU2K1jST3OeVeXQ4zVtLuYoGKc8V5nc6jPp2qiRs4BwRXu14itA2fSvF/FFkH1NlUdWrOUeV2NacueJ22jarFdWqsD1FO1eJLm3YEdqoeG9LK2kefSt+ewJjxSTKsfOfjHTTaaizgfK1cowr1v4j6b5VsXxyDXlDoa6YSujmqRsyuaaakIphFXcixSIwKTpTsZpKZmHvU8TDgDqwwc1BSg4IPcUAXLZdlwFZSCehFXWSqMLs+wKcEsAa1ynFXAiZT21Ey4q7s61XlGDVkpkGKjapj0qFutJjQyloopFC0UUUAHepUWo1HNW4kpoTALUiipNuBSAVZAqrmhlNSxipSgNArlVUqUR1MkfNS+WMUBcZGoC5rJ1FlyavTuy5ArJuEklJpSY4rUoHrTkcoeKHRkPIptYmxObgkYqInJzQBS4xTEL2phPNBNIOtAx681IAKjWpFrSJLEIwaaTTnNMqHuNC9acBTRTs4pAKRVuytjNIOOKqZya29L2ouTSbGkLc2ojjrJD7HNa2oXII2rWK4OaUQkXRc/LjNQlvMeqwJqaD79aXItY1LdMLUppsP3KkAzWiM2IBS4pwWp1tpHhaVUJROGI7UCKpFIRUpWmFaAHxKM1IyVEnBqbecYpgQsuKQcVI1MpAHU05VpuKlSmAbacFooBoEKFyav2a4AzVeEr5ilhkelXFYA8DFAmdBp8iwPG3vXq+hTJNaqwI6V4mszbRjNdd4a8Rvb4gkzt9aGriWjPUblY2iOcV5T4xsUMjMorupNYia3zu7VwHiC/8AtEzY+6KIoJM4K8tthPFZrriugu2V8isedOTQyosot1ptSSLg1HUmgtTQrk1CKs24+YU0JmhFEMCtnT0VQDWWvQVbglKJntVoyZpy3XlHANZl5cGQHNMnn396qs+V5pNgkU5SMkmqM7jBq5OpOaybncKhmsUVJDlqZSnrSVmahS4oHWpVTjNAEeKcp29KkwDTCMGgB29m4qxDHmoI0LMK04IcCnFXJk7AqYFNK81ZK8VHt+atLEXJIk4FWFWmxLxU4T2oENVc1PGeKRUwKjYlW4oAtxkBua2bfyxCDxXPKxNWUunjTbQDRcvyjJjvWLImDVt5i/U1Xc5PFAkViMVDKOKuCMmkltmKZApFHP3A+aq9Xr2IoeRVGs2aLYKKKKRQVNB9+oqmgPz0IGbNsPlFWCOagtugq1jmtUzB7kkfGM06VgRxUeaYzcUmxpEbNg0xmJpSCaTFQ2apEZFOiGXFOK1JAvz1FyrGragkDJzVps4plsnyirBTIpFJFfNFSGOjyzSuWkQPTB1qdojTBEc9Km5SRatThhW7ayHArLsrYuRxXQ2lgwA4rKUjeMS/YtiRSa7OwuR5a81yttaMCPlrdto2VKybNOXQ6q2vVGATV5biNhkMK4s3LoetTQ356E1UajRlKgnqdBqV6iQMoOSRXm17GLjVAx55rob+9/dnmuUa8UXwOe9TJuWppTgoqx6JpUSLbptwOK0JdoTmub0/VESIDdVubUS8Z28001YmUXc8++KDodPKDG4mvF5E616j8QIruceaQfLXkivM3FawehnUWpQdeajI5qzIvNQkVrcxaKWwg1CVK5+tWyAaidepHarMSJelOA7e9CnGCelSBSenXrigZas0DXMadCDu+tarcGszTzm8Ukfwkg+laLsAa0p7GU9xjHFV5MGpHfNQk5NWJETVC3WrDLxVdutSxobRS0UigooooAkQc1ehHFUU6ir8VVEmRNtzSbMVMmMU5sYqiCFeKlU5qPFOXg0AWFHNS7cioFaplcYpklaaIN1qq0IB6VoOc1Wcc0mNMzri2DA8VlSIUYg10bLuGKy72DGTis5I0jIoKaceRUdOBqCxDTO9PIppHNMaHKaeDUWacDTTFYceTS4pBSmkAmQKaXyaax5puaB2JlNX4bnZH1rMBxTgxIxSeoy20pkYk01uaiQ1J1FNEsbU0C/NmolUk1fgi4FNCbLUTYUCrC9KrKm2rCVqjJkoFXbC8azlPG6JxtdD0IqmoqUCmSPvIoluG8ht0Z5X29qrFKsheKaVoC5AFwadjilIoPSgCNqZT2plAxwqZVwgb1qEVKpJAz2oACaQdaeRSKvNAiaLrV+1t2uJAqiqMa8103h1A9yoNMTNvSvDhkQBk610lt4NTAIXmt/RbWIxqxAzXSRwqF4FS5AoXOCuNDa3jK4OMVw+vQeQWAr2vUIo/IbIHSvIfFpT7QQtOLuKUbHCzZyapuuTzV+YYY1UkwKY0Z86gHiq1Wpjmq3epZogqeA81BU0PWhAzUjbIFWFkfyvKH3Sc496qw9K1LONSQTVGbKbwOBkioTGQK3LrYsdYk0mXIXpSYIruvBrLu0GDWuT8pzWXec5qWaRMg9aSnN1NNrM1AdasrytVqkR9tAMlxSYyaXeCKdCu56BFy1t844rREe0UWkXyjirEi4FapaGLepTYUwDLVK9ES/PTGXba3LAcVd+ykDOKfZbQozVqRgaRJnmLAqrKmDWkwFUrgc0DRChAFLgsc01Rk1ZROKRRVZTmkVcmrTpUYXBoAkii3MBWwbEeVyO1Z1uQJFJ9a6DzFMOfamiGcLrdsEyQK5yux10Ao9ceRzUS3NobBRRRUFhUkZwwplOXrQBsWr8CrwbIrItiTjFakatt5FWmZuJJmgLuNIQamh6gUmxpDha7lyOtVnjZGwRW1HGWj4FQTQZHI5qGzRGTinw8SCnyx7WxREmXFSUkbdpyoqyVptjbsyDFXTbsvUUrlWKoTNOEdWPLx2pVjycVLKRAIhR5AJ4FXDDgUscXNS2aJF7R7NpHAVc16DpegMyAuoFZfhOyRtrEV6JAgVQAOBWMVz
16 {
  "class_type": "VHS_VideoCombine",
  "id": "16",
  "inputs": {
    "crf": 19,
    "filename_prefix": "AnimateDiff",
    "format": "video/h264-mp4",
    "frame_rate": 8,
    "loop_count": 0,
    "pingpong": false,
    "pix_fmt": "yuv420p",
    "save_metadata": true,
    "save_output": false,
    "trim_to_audio": false,
    "videopreview": {
      "hidden": false,
      "muted": false,
      "params": {
        "filename": "AnimateDiff_00023.mp4",
        "format": "video/h264-mp4",
        "frame_rate": 8,
        "fullpath": "N:\\AI\\ComfyUI\\temp\\AnimateDiff_00023.mp4",
        "subfolder": "",
        "type": "temp",
        "workflow": "AnimateDiff_00023.png"
      },
      "paused": false
    }
  },
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 16,
      "inputs": [
        {
          "link": 17,
          "name": "images",
          "type": "IMAGE"
        },
        {
          "link": null,
          "name": "audio",
          "shape": 7,
          "type": "AUDIO"
        },
        {
          "link": null,
          "name": "meta_batch",
          "shape": 7,
          "type": "VHS_BatchManager"
        },
        {
          "link": null,
          "name": "vae",
          "shape": 7,
          "type": "VAE"
        }
      ],
      "mode": 0,
      "order": 5,
      "outputs": [
        {
          "links": null,
          "name": "Filenames",
          "type": "VHS_FILENAMES"
        }
      ],
      "pos": [
        442.3276672363281,
        149.1554412841797
      ],
      "properties": {
        "Node name for S&R": "VHS_VideoCombine"
      },
      "size": [
        680.5087890625,
        843.381591796875
      ],
      "type": "VHS_VideoCombine",
      "widgets_values": {
        "crf": 19,
        "filename_prefix": "AnimateDiff",
        "format": "video/h264-mp4",
        "frame_rate": 8,
        "loop_count": 0,
        "pingpong": false,
        "pix_fmt": "yuv420p",
        "save_metadata": true,
        "save_output": false,
        "trim_to_audio": false,
        "videopreview": {
          "hidden": false,
          "muted": false,
          "params": {
            "filename": "AnimateDiff_00023.mp4",
            "format": "video/h264-mp4",
            "frame_rate": 8,
            "fullpath": "N:\\AI\\ComfyUI\\temp\\AnimateDiff_00023.mp4",
            "subfolder": "",
            "type": "temp",
            "workflow": "AnimateDiff_00023.png"
          },
          "paused": false
        }
      }
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": true,
    "length": 11,
    "shape": "dict",
    "source": "ui.widgets_values",
    "values": {
      "crf": 19,
      "filename_prefix": "AnimateDiff",
      "format": "video/h264-mp4",
      "frame_rate": 8,
      "loop_count": 0,
      "pingpong": false,
      "pix_fmt": "yuv420p",
      "save_metadata": true,
      "save_output": false,
      "trim_to_audio": false,
      "videopreview": {
        "hidden": false,
        "muted": false,
        "params": {
          "filename": "AnimateDiff_00023.mp4",
          "format": "video/h264-mp4",
          "frame_rate": 8,
          "fullpath": "N:\\AI\\ComfyUI\\temp\\AnimateDiff_00023.mp4",
          "subfolder": "",
          "type": "temp",
          "workflow": "AnimateDiff_00023.png"
        },
        "paused": false
      }
    }
  },
  "uid": "16",
  "widgets": {}
}
18 {
  "class_type": "INPAINT_InpaintWithModel",
  "id": "18",
  "inputs": {},
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 18,
      "inputs": [
        {
          "link": 18,
          "name": "inpaint_model",
          "type": "INPAINT_MODEL"
        },
        {
          "link": 19,
          "name": "image",
          "type": "IMAGE"
        },
        {
          "link": 20,
          "name": "mask",
          "type": "MASK"
        },
        {
          "link": null,
          "name": "optional_upscale_model",
          "shape": 7,
          "type": "UPSCALE_MODEL"
        }
      ],
      "mode": 0,
      "order": 3,
      "outputs": [
        {
          "links": [
            24
          ],
          "name": "IMAGE",
          "slot_index": 0,
          "type": "IMAGE"
        }
      ],
      "pos": [
        -32.909523010253906,
        158.2882843017578
      ],
      "properties": {
        "Node name for S&R": "INPAINT_InpaintWithModel"
      },
      "size": [
        355.20001220703125,
        142
      ],
      "type": "INPAINT_InpaintWithModel",
      "widgets_values": [
        534667941392889,
        "fixed"
      ]
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 2,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      534667941392889,
      "fixed"
    ]
  },
  "uid": "18",
  "widgets": {
    "widget_0": 534667941392889,
    "widget_1": "fixed"
  }
}
WORKFLOW d7853c
27 {
  "class_type": "SaveVideo",
  "id": "27",
  "inputs": {
    "codec": "auto",
    "filename_prefix": "video/ComfyUI",
    "format": "auto"
  },
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 27,
      "inputs": [
        {
          "link": 35,
          "name": "video",
          "type": "VIDEO"
        }
      ],
      "mode": 0,
      "order": 3,
      "outputs": [],
      "pos": [
        1190,
        620
      ],
      "properties": {
        "Node name for S&R": "SaveVideo"
      },
      "size": [
        531.188232421875,
        398.43743896484375
      ],
      "type": "SaveVideo",
      "widgets_values": [
        "video/ComfyUI",
        "auto",
        "auto"
      ]
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 3,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      "video/ComfyUI",
      "auto",
      "auto"
    ]
  },
  "uid": "27",
  "widgets": {}
}
29 {
  "class_type": "LoadImage",
  "id": "29",
  "inputs": {
    "image": "api_moonvalley_image_to_video_input_image.jpg",
    "unused_widget_1": "image"
  },
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 29,
      "inputs": [],
      "mode": 0,
      "order": 1,
      "outputs": [
        {
          "links": [
            36
          ],
          "name": "IMAGE",
          "type": "IMAGE"
        },
        {
          "links": null,
          "name": "MASK",
          "type": "MASK"
        }
      ],
      "pos": [
        320,
        620
      ],
      "properties": {
        "Node name for S&R": "LoadImage"
      },
      "size": [
        430,
        390
      ],
      "type": "LoadImage",
      "widgets_values": [
        "api_moonvalley_image_to_video_input_image.jpg",
        "image"
      ]
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 2,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      "api_moonvalley_image_to_video_input_image.jpg",
      "image"
    ]
  },
  "uid": "29",
  "widgets": {}
}
30 {
  "class_type": "MarkdownNote",
  "id": "30",
  "inputs": {
    "unused_widget_0": "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"
  },
  "metadata": {
    "_ui": {
      "bgcolor": "#000",
      "color": "#322",
      "flags": {},
      "id": 30,
      "inputs": [],
      "mode": 0,
      "order": 0,
      "outputs": [],
      "pos": [
        -90,
        620
      ],
      "properties": {},
      "size": [
        390,
        300
      ],
      "title": "About API Node",
      "type": "MarkdownNote",
      "widgets_values": [
        "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"
      ]
    },
    "bgcolor": "#000",
    "color": "#322",
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 1,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"
    ]
  },
  "uid": "30",
  "widgets": {}
}
34 {
  "class_type": "MoonvalleyImg2VideoNode",
  "id": "34",
  "inputs": {},
  "metadata": {
    "_ui": {
      "bgcolor": "#653",
      "color": "#432",
      "flags": {},
      "id": 34,
      "inputs": [
        {
          "link": 36,
          "name": "image",
          "type": "IMAGE"
        }
      ],
      "mode": 0,
      "order": 2,
      "outputs": [
        {
          "links": [
            35
          ],
          "name": "VIDEO",
          "type": "VIDEO"
        }
      ],
      "pos": [
        770,
        620
      ],
      "properties": {
        "Node name for S&R": "MoonvalleyImg2VideoNode"
      },
      "size": [
        400,
        360
      ],
      "type": "MoonvalleyImg2VideoNode",
      "widgets_values": [
        "A bedroom is transformed into a surreal underwater dreamscape, completely submerged in deep turquoise water where caustic light patterns ripple and dance across the walls, floor, and ceiling. In the center of this submerged room, a ballerina gracefully holds a pose en pointe, her form silhouetted against the ethereal blue glow. She moves with impossible slowness, transitioning between ballet positions as her sheer white dress billows around her in the gentle, silent currents. Tiny bubbles occasionally escape her lips, rising towards the undulating surface above, which serves as the room's only light source. The scene is both beautiful and unsettling, a silent performance in a liquid world where reality is suspended. Background: The ceiling is the agitated surface of the water, with ethereal beams of light filtering down and constantly shifting. A bed sits against the back wall, its form partially obscured by the moving shadows and light. Middleground: A silhouetted ballerina stands as the focal point, her arms outstretched in a graceful ballet pose. Her diaphanous dress flows weightlessly around her, moved by invisible underwater currents as she performs her silent dance. Foreground: The floor is covered in a moving tapestry of bright caustic reflections from the water's surface above. The ballerina's shadow and reflection are cast upon the floor, distorting and swaying with the light.",
        "low-poly, flat shader, bad rigging, stiff animation, uncanny eyes, low-quality textures, looping glitch, cheap effect, overbloom, bloom spam, default lighting, game asset, stiff face, ugly specular, AI artifacts",
        "16:9 (1920 x 1080)",
        7,
        2328774152,
        "randomize",
        100
      ]
    },
    "bgcolor": "#653",
    "color": "#432",
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 7,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      "A bedroom is transformed into a surreal underwater dreamscape, completely submerged in deep turquoise water where caustic light patterns ripple and dance across the walls, floor, and ceiling. In the center of this submerged room, a ballerina gracefully holds a pose en pointe, her form silhouetted against the ethereal blue glow. She moves with impossible slowness, transitioning between ballet positions as her sheer white dress billows around her in the gentle, silent currents. Tiny bubbles occasionally escape her lips, rising towards the undulating surface above, which serves as the room's only light source. The scene is both beautiful and unsettling, a silent performance in a liquid world where reality is suspended. Background: The ceiling is the agitated surface of the water, with ethereal beams of light filtering down and constantly shifting. A bed sits against the back wall, its form partially obscured by the moving shadows and light. Middleground: A silhouetted ballerina stands as the focal point, her arms outstretched in a graceful ballet pose. Her diaphanous dress flows weightlessly around her, moved by invisible underwater currents as she performs her silent dance. Foreground: The floor is covered in a moving tapestry of bright caustic reflections from the water's surface above. The ballerina's shadow and reflection are cast upon the floor, distorting and swaying with the light.",
      "low-poly, flat shader, bad rigging, stiff animation, uncanny eyes, low-quality textures, looping glitch, cheap effect, overbloom, bloom spam, default lighting, game asset, stiff face, ugly specular, AI artifacts",
      "16:9 (1920 x 1080)",
      7,
      2328774152,
      "randomize",
      100
    ]
  },
  "uid": "34",
  "widgets": {
    "widget_0": "A bedroom is transformed into a surreal underwater dreamscape, completely submerged in deep turquoise water where caustic light patterns ripple and dance across the walls, floor, and ceiling. In the center of this submerged room, a ballerina gracefully holds a pose en pointe, her form silhouetted against the ethereal blue glow. She moves with impossible slowness, transitioning between ballet positions as her sheer white dress billows around her in the gentle, silent currents. Tiny bubbles occasionally escape her lips, rising towards the undulating surface above, which serves as the room's only light source. The scene is both beautiful and unsettling, a silent performance in a liquid world where reality is suspended. Background: The ceiling is the agitated surface of the water, with ethereal beams of light filtering down and constantly shifting. A bed sits against the back wall, its form partially obscured by the moving shadows and light. Middleground: A silhouetted ballerina stands as the focal point, her arms outstretched in a graceful ballet pose. Her diaphanous dress flows weightlessly around her, moved by invisible underwater currents as she performs her silent dance. Foreground: The floor is covered in a moving tapestry of bright caustic reflections from the water's surface above. The ballerina's shadow and reflection are cast upon the floor, distorting and swaying with the light.",
    "widget_1": "low-poly,
WORKFLOW d93baf
21 {
  "class_type": "SaveGLB",
  "id": "21",
  "inputs": {},
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 21,
      "inputs": [
        {
          "link": 92,
          "name": "mesh",
          "type": "MESH,FILE_3D_GLB,FILE_3D_GLTF,FILE_3D_OBJ,FILE_3D_FBX,FILE_3D_STL,FILE_3D_USDZ,FILE_3D"
        }
      ],
      "mode": 0,
      "order": 5,
      "outputs": [],
      "pos": [
        -1891.1849394490798,
        5054.079271096964
      ],
      "properties": {
        "Camera Config": {
          "cameraType": "perspective",
          "fov": 35,
          "state": {
            "cameraType": "perspective",
            "position": {
              "x": 6.786724982855805,
              "y": 1.9262054236803827,
              "z": 4.315390609507273
            },
            "target": {
              "x": 0.5610696024689849,
              "y": 1.8227901315768118,
              "z": -0.15103066686464472
            },
            "zoom": 1
          }
        },
        "Light Config": {
          "hdri": {
            "enabled": false,
            "hdriPath": "",
            "intensity": 1,
            "showAsBackground": false
          },
          "intensity": 2.4000000000000004
        },
        "Model Config": {
          "gizmo": {
            "enabled": false,
            "mode": "translate",
            "position": {
              "x": 0.3622254788581172,
              "y": 1.8487530247818735,
              "z": 3.580411492082191
            },
            "rotation": {
              "x": 0,
              "y": 0,
              "z": 0
            },
            "scale": {
              "x": 2.687608243041624,
              "y": 2.687608243041624,
              "z": 2.687608243041624
            }
          },
          "materialMode": "original",
          "showSkeleton": false,
          "upDirection": "original"
        },
        "Node name for S&R": "SaveGLB",
        "Scene Config": {
          "backgroundColor": "#8e9ea9",
          "backgroundImage": "",
          "backgroundRenderMode": "tiled",
          "showGrid": false
        },
        "cnr_id": "comfy-core",
        "enableTabs": false,
        "hasSecondTab": false,
        "secondTabOffset": 80,
        "secondTabText": "Send Back",
        "secondTabWidth": 65,
        "tabWidth": 65,
        "tabXOffset": 10,
        "ue_properties": {
          "input_ue_unconnectable": {},
          "version": "7.8",
          "widget_ue_connectable": {}
        },
        "ver": "0.21.1"
      },
      "size": [
        782.0843697681353,
        601.1357657565522
      ],
      "type": "SaveGLB",
      "widgets_values": [
        "3d/ComfyUI",
        ""
      ]
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 2,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": [
      "3d/ComfyUI",
      ""
    ]
  },
  "uid": "21",
  "widgets": {
    "widget_0": "3d/ComfyUI",
    "widget_1": ""
  }
}
46 {
  "class_type": "PreviewImage",
  "id": "46",
  "inputs": {},
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 46,
      "inputs": [
        {
          "link": 88,
          "name": "images",
          "type": "IMAGE"
        }
      ],
      "mode": 0,
      "order": 6,
      "outputs": [],
      "pos": [
        -2950,
        5000
      ],
      "properties": {
        "Node name for S&R": "PreviewImage (normal_opengl)",
        "cnr_id": "comfy-core",
        "enableTabs": false,
        "hasSecondTab": false,
        "secondTabOffset": 80,
        "secondTabText": "Send Back",
        "secondTabWidth": 65,
        "tabWidth": 65,
        "tabXOffset": 10,
        "ue_properties": {
          "input_ue_unconnectable": {},
          "version": "7.8",
          "widget_ue_connectable": {}
        },
        "ver": "0.21.1"
      },
      "size": [
        350,
        490
      ],
      "title": "Preview Image (normal_opengl)",
      "type": "PreviewImage",
      "widgets_values": []
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 0,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": []
  },
  "uid": "46",
  "widgets": {}
}
47 {
  "class_type": "PreviewImage",
  "id": "47",
  "inputs": {},
  "metadata": {
    "_ui": {
      "flags": {},
      "id": 47,
      "inputs": [
        {
          "link": 89,
          "name": "images",
          "type": "IMAGE"
        }
      ],
      "mode": 0,
      "order": 7,
      "outputs": [],
      "pos": [
        -2570,
        5000
      ],
      "properties": {
        "Node name for S&R": "PreviewImage (normal_directx)",
        "cnr_id": "comfy-core",
        "enableTabs": false,
        "hasSecondTab": false,
        "secondTabOffset": 80,
        "secondTabText": "Send Back",
        "secondTabWidth": 65,
        "tabWidth": 65,
        "tabXOffset": 10,
        "ue_properties": {
          "input_ue_unconnectable": {},
          "version": "7.8",
          "widget_ue_connectable": {}
        },
        "ver": "0.21.1"
      },
      "size": [
        350,
        490
      ],
      "title": "Preview Image (normal_directx)",
      "type": "PreviewImage",
      "widgets_values": []
    },
    "flags": {},
    "mode": 0,
    "provenance": "untrusted_source"
  },
  "mode": 0,
  "pack": null,
  "raw_widgets": {
    "has_dict_rows": false,
    "length": 0,
    "shape": "list",
    "source": "ui.widgets_values",
    "values": []
  },
  "uid": "47",
  "widgets": {}
}

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '720,880p'; rg -n 'skip_intent_judge|judge_edit_intent|desired' tests/live_agentic_harness/assessor.py tests/live_agentic_harness/intent_judge.py tests/live_agentic_harness/guard.py tests/live_agentic_harness/runner.py tests/live_agentic_harness/scenarios | head -200" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   720	                                f"is {landed_count!r}; a positive integer is required "
   721	                                "when graph_unchanged is false."
   722	                            ),
   723	                        }
   724	                    )
   725
   726	            # G0R route/graph consistency: a canonical non-edit route must
   727	            # never claim graph_unchanged=false.  Non-edit routes are exempt
   728	            # from the landed-count guard only when the graph really is
   729	            # unchanged (or the refusal is authorized above); an edit-route
   730	            # envelope self-relabeled as clarify/respond/failure cannot
   731	            # bypass the structural checks by relabeling alone.
   732	            if (
   733	                not safe_refusal_accepted
   734	                and response.get("graph_unchanged") is False
   735	                and route in _NON_EDIT_ROUTES
   736	            ):
   737	                issues.append(
   738	                    {
   739	                        "check": "route_graph_consistency",
   740	                        "severity": "error",
   741	                        "detail": (
   742	                            f"Non-edit route {route!r} claimed graph_unchanged=false; "
   743	                            "a non-edit route cannot change the graph."
   744	                        ),
   745	                    }
   746	                )
   747
   748	            no_reason = response.get("no_candidate_reason")
   749	            if not safe_refusal_accepted and no_reason in {"no_changes", "no_candidate"}:
   750	                issues.append(
   751	                    {
   752	                        "check": "no_candidate_reason",
   753	                        "severity": "error",
   754	                        "detail": f"Expected edit but no_candidate_reason={no_reason!r}.",
   755	                    }
   756	                )
   757
   758	            if not safe_refusal_accepted and outcome_kind in {"noop", "requires_custom_nodes"}:
   759	                issues.append(
   760	                    {
   761	                        "check": "outcome_kind",
   762	                        "severity": "error",
   763	                        "detail": f"Expected edit but outcome.kind={outcome_kind!r}.",
   764	                    }
   765	                )
   766
   767	            gates = response.get("gates") or {}
   768	            false_gates = [name for name, value in gates.items() if value is False]
   769	            queue_validate_skipped = _queue_validate_skipped_for_successful_candidate(response)
   770	            if queue_validate_skipped and "queue_validate_ok" in false_gates:
   771	                false_gates = [name for name in false_gates if name != "queue_validate_ok"]
   772	                issues.append(
   773	                    {
   774	                        "check": "queue_validate_skipped",
   775	                        "severity": "warning",
   776	                        "detail": (
   777	                            "queue_validate_ok was false, but the response contains a changed "
   778	                            "candidate and no queue_validate stage ran; treating this as missing "
   779	                            "queue evidence rather than a concrete queue blocker."
   780	                        ),
   781	                    }
   782	                )
   783	            if false_gates and not safe_refusal_accepted:
   784	                issues.append(
   785	                    {
   786	                        "check": "gates",
   787	                        "severity": "error",
   788	                        "detail": f"Expected edit but gates failed: {', '.join(sorted(false_gates))}.",
   789	                    }
   790	                )
   791
   792	            if not safe_refusal_accepted:
   793	                issues.extend(_assess_effective_edit_targets(output_dir, response, scenario))
   794	        elif expected_outcome_kinds:
   795	            outcome = response.get("outcome") or {}
   796	            outcome_kind = outcome.get("kind")
   797	            if outcome_kind not in expected_outcome_kinds:
   798	                issues.append(
   799	                    {
   800	                        "check": "outcome_kind",
   801	                        "severity": "error",
   802	                        "detail": (
   803	                            f"Expected outcome.kind in {sorted(expected_outcome_kinds)!r} "
   804	                            f"but got {outcome_kind!r}."
   805	                        ),
   806	                    }
   807	                )
   808
   809	        # LLM intent judge: score the candidate edit against the query when the
   810	        # scenario expects a graph change.  This runs by default; set
   811	        # ``assessment.skip_intent_judge: true`` in the scenario to disable it.
   812	        if (
   813	            expect_graph_changed
   814	            and not safe_refusal_accepted
   815	            and not scenario.get("assessment", {}).get("skip_intent_judge")
   816	        ):
   817	            verdict = judge_edit_intent(output_dir, scenario)
   818	            if verdict.get("pass_") is False:
   819	                issues.append(
   820	                    {
   821	                        "check": "intent_judge",
   822	                        "severity": "error",
   823	                        "detail": (
   824	                            f"LLM intent judge failed: {verdict.get('rationale', 'no rationale')} "
   825	                            f"criteria={verdict.get('criteria')}"
   826	                        ),
   827	                    }
   828	                )
   829	            elif verdict.get("pass_") is True:
   830	                issues.append(
   831	                    {
   832	                        "check": "intent_judge",
   833	                        "severity": "info",
   834	                        "detail": (
   835	                            f"LLM intent judge passed: {verdict.get('rationale', 'no rationale')} "
   836	                            f"criteria={verdict.get('criteria')}"
   837	                        ),
   838	                    }
   839	                )
   840	            else:
   841	                issues.append(
   842	                    {
   843	                        "check": "intent_judge",
   844	                        # A desired block is an active acceptance rubric, not
   845	                        # optional context. Fail closed if its judge is absent.
   846	                        "severity": "error" if scenario.get("desired") else "warning",
   847	                        "detail": f"LLM intent judge could not run: {verdict.get('error')}",
   848	                    }
   849	                )
   850
   851	        # Any hard diagnostic anywhere in the response envelope.
   852	        for msg in _collect_hard_diagnostics(response):
   853	            issues.append(
   854	                {
   855	                    "check": "hard_diagnostic",
   856	                    "severity": "error",
   857	                    "detail": msg,
   858	                }
   859	            )
   860
   861	        # G0-T2: the deterministic message-artifact prose matcher is removed.
   862	        # Scoring is structured-only — prose never gates a scenario. The
   863	        # agent's message always ships as written; the structured
   864	        # cross-checks (graph_changed, outcome_kind, gates, landed counts,
   865	        # effective edits) above remain fully authoritative.
   866
   867	        # Critical upstream failures (Hivemind 500, etc.). When a successful
   868	        # candidate exists, a recovered research-side upstream error should stay
   869	        # visible but not invalidate an otherwise valid edit.
   870	        upstream_severity = "warning" if _has_successful_candidate(response) else "error"
   871	        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
   872	            issues.append(
   873	                {
   874	                    "check": "upstream_failure",
   875	                    "severity": upstream_severity,
   876	                    "detail": msg,
   877	                }
   878	            )
   879
   880	        # Capacity/soft warnings: surfaced, but not counted as errors.
tests/live_agentic_harness/intent_judge.py:247:def judge_edit_intent(
tests/live_agentic_harness/intent_judge.py:317:    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
tests/live_agentic_harness/intent_judge.py:321:    desired = scenario.get("desired")
tests/live_agentic_harness/intent_judge.py:322:    if desired:
tests/live_agentic_harness/intent_judge.py:325:            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
tests/live_agentic_harness/intent_judge.py:327:            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
tests/live_agentic_harness/intent_judge.py:332:            f"Desired outcome: {desired.get('outcome', '')}\n"
tests/live_agentic_harness/intent_judge.py:333:            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
tests/live_agentic_harness/intent_judge.py:334:            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
tests/live_agentic_harness/intent_judge.py:337:    if desired:
tests/live_agentic_harness/intent_judge.py:338:        payload["desired_outcome"] = desired
tests/live_agentic_harness/assessor.py:29:from .intent_judge import judge_edit_intent
tests/live_agentic_harness/assessor.py:811:        # ``assessment.skip_intent_judge: true`` in the scenario to disable it.
tests/live_agentic_harness/assessor.py:815:            and not scenario.get("assessment", {}).get("skip_intent_judge")
tests/live_agentic_harness/assessor.py:817:            verdict = judge_edit_intent(output_dir, scenario)
tests/live_agentic_harness/assessor.py:844:                        # A desired block is an active acceptance rubric, not
tests/live_agentic_harness/assessor.py:846:                        "severity": "error" if scenario.get("desired") else "warning",
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json:11:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json:11:  "desired": {
tests/live_agentic_harness/scenarios/audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:11:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:15:  "desired": {
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-background-removal-and-grid-composition-54a681.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json:11:  "desired": {
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json:11:  "desired": {
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json:11:  "desired": {
tests/live_agentic_harness/scenarios/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json:11:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json:11:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json:11:  "desired": {
tests/live_agentic_harness/scenarios/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:11:  "desired": {
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-workflow-2a31ec.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-image-to-image-with-controlnet-and-dwpreproces-49d057.json:11:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-model-load-edit-and-export-workflow-d66a66.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:3:  "query": "How can I balance the influence between the IPAdapter style reference and the Canny edge ControlNet strength to preserve more of the original image structure while still applying the desired style? What parameters control this interplay?",
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json:11:  "desired": {
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-webp-and-png-output-bd3afb.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json:11:  "desired": {
tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json:15:  "desired": {
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-and-processing-workfl-1b1360.json:11:  "desired": {
tests/live_agentic_harness/scenarios/multi-image-to-video-with-upscaling-and-color-matchi-359848.json:11:  "desired": {
tests/live_agentic_harness/scenarios/image-flux-image-inpainting-and-compositing-with-con-00444a.json:11:  "desired": {
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:15:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json:11:  "desired": {
tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json:11:  "desired": {
tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json:11:  "desired": {
tests/live_agentic_harness/scenarios/audio-audio-processing-with-chatterbox-tts-and-vc-b55994.json:11:  "desired": {

exec
/bin/zsh -lc "rg -n 'safe_refusal|grounded_refusal|refusal' tests/live_agentic_harness/assessor.py | head -100 && nl -ba tests/live_agentic_harness/assessor.py | sed -n '1,220p'; nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '240,360p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
320:def _allowed_safe_refusal_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
321:    """Return no-edit outcome kinds accepted as safe refusals for edit scenarios."""
327:    raw = assessment.get("allow_safe_refusal_outcome_kinds")
329:        raw = assessment.get("allow_safe_refusal_outcome_kind")
635:    allowed_safe_refusal_outcome_kinds = _allowed_safe_refusal_outcome_kinds(scenario)
636:    safe_refusal_accepted = False
641:        safe_refusal_accepted = (
645:            and outcome_kind in allowed_safe_refusal_outcome_kinds
679:            if safe_refusal_accepted:
682:                        "check": "safe_refusal",
684:                        "detail": f"Accepted safe refusal outcome.kind={outcome_kind!r}.",
699:            # zero counts fail closed.  Accepted grounded refusals
700:            # (safe_refusal_accepted) and canonical non-edit routes are
704:                not safe_refusal_accepted
729:            # unchanged (or the refusal is authorized above); an edit-route
733:                not safe_refusal_accepted
749:            if not safe_refusal_accepted and no_reason in {"no_changes", "no_candidate"}:
758:            if not safe_refusal_accepted and outcome_kind in {"noop", "requires_custom_nodes"}:
783:            if false_gates and not safe_refusal_accepted:
792:            if not safe_refusal_accepted:
814:            and not safe_refusal_accepted
923:        "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
     1	"""Deep assessment of live agentic run artifacts.
     2
     3	The live agentic harness already verifies flow metadata (real dispatcher,
     4	agentic model behavior, status == success).  This module inspects the actual
     5	run artifacts to catch failures that metadata alone cannot:
     6
     7	* response.ok == false or response.error set
     8	* readiness blockers
     9	* graph unchanged when an edit was expected
    10	* hard diagnostics (severity == error) from agent-edit turns
    11	* upstream dependency failures such as Hivemind HTTP 500
    12	* implementation_result.ok == false
    13	* validation gates that failed for an apply/edit route
    14	* (when enabled) an LLM intent judge that scores the edit against the query
    15
    16	The deterministic checks run first; the LLM judge is called afterward for
    17	scenarios that expect a graph change.
    18	"""
    19
    20	from __future__ import annotations
    21
    22	import json
    23	import re
    24	from pathlib import Path
    25	from typing import Any, Mapping
    26
    27	from vibecomfy.executor.graph_facts import GraphFieldTarget, compare_effective_field
    28
    29	from .intent_judge import judge_edit_intent
    30
    31	_ERROR_SEVERITIES = {"error", "fatal"}
    32
    33	# Critical upstream failures that should always fail a live run.
    34	_UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
    35	    re.compile(r"Hivemind HTTP error.*500", re.IGNORECASE),
    36	    re.compile(r"HTTP Error 500", re.IGNORECASE),
    37	    re.compile(r"Internal Server Error", re.IGNORECASE),
    38	]
    39
    40	# Soft capacity warnings: surfaced so humans see them, but not treated as hard
    41	# failures on their own (the run may still succeed via fallback evidence).
    42	_SOFT_WARNING_PATTERNS: list[re.Pattern[str]] = [
    43	    re.compile(r"HTTP Error 429", re.IGNORECASE),
    44	    re.compile(r"Too Many Requests", re.IGNORECASE),
    45	]
    46
    47	# Canonical public route vocabulary (mirrors vibecomfy.executor.contracts).
    48	# Edit routes may land graph changes; non-edit routes never do.  Exemption
    49	# from the landed-count guard is decided from the envelope's canonical route,
    50	# never from the agent's self-declared outcome/reason labels.
    51	_EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise"})
    52	_NON_EDIT_ROUTES = frozenset({
    53	    "clarify",
    54	    "respond",
    55	    "inspect",
    56	    "research",
    57	    "requires_custom_nodes",
    58	})
    59
    60
    61	def _load_json(path: Path) -> dict[str, Any] | None:
    62	    """Load a JSON artifact if it exists and is valid."""
    63	    if not path.is_file():
    64	        return None
    65	    try:
    66	        return json.loads(path.read_text(encoding="utf-8"))
    67	    except (OSError, json.JSONDecodeError):
    68	        return None
    69
    70
    71	def _walk(obj: Any) -> Any:
    72	    """Recursively yield every dict/string node in a JSON-like structure."""
    73	    if isinstance(obj, dict):
    74	        yield obj
    75	        for value in obj.values():
    76	            yield from _walk(value)
    77	    elif isinstance(obj, list):
    78	        for item in obj:
    79	            yield from _walk(item)
    80	    else:
    81	        yield obj
    82
    83
    84	def _has_successful_candidate(response: Mapping[str, Any]) -> bool:
    85	    """Return true when the response produced an applied candidate graph."""
    86	    if response.get("ok") is not True:
    87	        return False
    88	    if response.get("graph_unchanged") is not False:
    89	        return False
    90	    return isinstance(response.get("candidate_graph"), Mapping) or isinstance(
    91	        response.get("candidate"), Mapping
    92	    )
    93
    94
    95	def _queue_validate_skipped_for_successful_candidate(response: Mapping[str, Any]) -> bool:
    96	    """Return true when queue validation is absent, not failed.
    97
    98	    ``queue_validate_ok`` is fail-closed in the agent-edit gate map.  Some live
    99	    batch paths can return a real changed candidate without running the queue
   100	    stage at all; that missing stage should not be scored the same as a
   101	    concrete queue blocker.
   102	    """
   103	    if not _has_successful_candidate(response):
   104	        return False
   105	    gates = response.get("gates")
   106	    if not isinstance(gates, Mapping) or gates.get("queue_validate_ok") is not False:
   107	        return False
   108	    debug = response.get("debug")
   109	    if not isinstance(debug, Mapping):
   110	        return False
   111	    stage_snapshots = debug.get("stage_snapshots")
   112	    if not isinstance(stage_snapshots, list):
   113	        return False
   114	    stage_names = {
   115	        str(item.get("stage"))
   116	        for item in stage_snapshots
   117	        if isinstance(item, Mapping) and item.get("stage") is not None
   118	    }
   119	    if "queue_validate" in stage_names:
   120	        return False
   121
   122	    def _has_queue_blockers(value: Any) -> bool:
   123	        if isinstance(value, list):
   124	            return bool(value)
   125	        if isinstance(value, tuple):
   126	            return bool(value)
   127	        return False
   128
   129	    report = response.get("report")
   130	    if isinstance(report, Mapping) and _has_queue_blockers(report.get("queue_blockers")):
   131	        return False
   132	    if _has_queue_blockers(debug.get("queue_blockers")):
   133	        return False
   134	    return True
   135
   136
   137	def _batch_turn_failed(turn: Mapping[str, Any]) -> bool:
   138	    """Return true for exploratory batch turns that did not contribute edits."""
   139	    if turn.get("batch_ok") is False:
   140	        return True
   141	    if (turn.get("landed_op_count") or 0) == 0 and (turn.get("raw_landed_op_count") or 0) == 0:
   142	        for diagnostic in turn.get("diagnostics") or []:
   143	            if isinstance(diagnostic, Mapping) and diagnostic.get("severity") in _ERROR_SEVERITIES:
   144	                return True
   145	    return False
   146
   147
   148	def _walk_hard_diagnostic_scope(obj: Any, *, skip_failed_batch_turns: bool) -> Any:
   149	    """Yield nodes for hard-diagnostic checks, excluding failed scratch turns.
   150
   151	    Agent-edit may keep a full transcript of exploratory batch attempts in
   152	    ``change_details.batch_turns`` even when the executor ultimately returns a
   153	    successful candidate from an earlier safe edit. Those failed attempts are
   154	    useful audit trail, but they are not active defects in the applied graph.
   155	    """
   156	    if isinstance(obj, dict):
   157	        yield obj
   158	        for key, value in obj.items():
   159	            if (
   160	                skip_failed_batch_turns
   161	                and key == "batch_turns"
   162	                and isinstance(value, list)
   163	            ):
   164	                for item in value:
   165	                    if isinstance(item, Mapping) and _batch_turn_failed(item):
   166	                        continue
   167	                    yield from _walk_hard_diagnostic_scope(
   168	                        item,
   169	                        skip_failed_batch_turns=skip_failed_batch_turns,
   170	                    )
   171	                continue
   172	            yield from _walk_hard_diagnostic_scope(
   173	                value,
   174	                skip_failed_batch_turns=skip_failed_batch_turns,
   175	            )
   176	    elif isinstance(obj, list):
   177	        for item in obj:
   178	            yield from _walk_hard_diagnostic_scope(
   179	                item,
   180	                skip_failed_batch_turns=skip_failed_batch_turns,
   181	            )
   182	    else:
   183	        yield obj
   184
   185
   186	def _collect_hard_diagnostics(response: Mapping[str, Any]) -> list[str]:
   187	    """Return messages from any object with severity error/fatal."""
   188	    issues: list[str] = []
   189	    skip_failed_batch_turns = _has_successful_candidate(response)
   190	    for node in _walk_hard_diagnostic_scope(
   191	        response,
   192	        skip_failed_batch_turns=skip_failed_batch_turns,
   193	    ):
   194	        if not isinstance(node, dict):
   195	            continue
   196	        if node.get("severity") not in _ERROR_SEVERITIES:
   197	            continue
   198	        message = node.get("message")
   199	        if not isinstance(message, str):
   200	            detail = node.get("detail")
   201	            message = json.dumps(detail, sort_keys=True) if isinstance(detail, dict) else str(node)
   202	        message = message.strip()
   203	        if message and message not in issues:
   204	            issues.append(message)
   205	    return issues
   206
   207
   208	def _collect_pattern_matches(
   209	    response: Mapping[str, Any],
   210	    patterns: list[re.Pattern[str]],
   211	) -> list[str]:
   212	    """Return distinct string values matching any of the supplied patterns."""
   213	    issues: list[str] = []
   214	    seen: set[str] = set()
   215	    for node in _walk(response):
   216	        if not isinstance(node, str):
   217	            continue
   218	        for pattern in patterns:
   219	            if pattern.search(node):
   220	                if node not in seen:
   240	        "note": (
   241	            "widgets_values are static node configuration. Linked inputs are dynamic dataflow. "
   242	            "A static text widget removal can be correct when linked dynamic inputs remain connected."
   243	        ),
   244	    }
   245
   246
   247	def judge_edit_intent(
   248	    output_dir: Path | str,
   249	    scenario: Mapping[str, Any],
   250	    *,
   251	    route: str = "deepseek",
   252	    model: str = "deepseek-v4-pro",
   253	) -> dict[str, Any]:
   254	    """Run the DeepSeek text judge on the candidate edit in *output_dir*.
   255
   256	    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
   257	    If required artifacts are missing or the model call fails, ``pass_`` is None
   258	    and ``error`` describes why.
   259	    """
   260	    output_dir = Path(output_dir)
   261	    query = str(scenario.get("query", "")).strip()
   262	    if not query:
   263	        return {"pass_": None, "error": "scenario has no query"}
   264
   265	    # The durable turn writes UI artifacts under out/editor_sessions; the response
   266	    # JSON carries the exact paths in its artifacts block.
   267	    response_path = output_dir / "response.json"
   268	    original_ui_path: Path | None = None
   269	    candidate_ui_path: Path | None = None
   270	    if response_path.is_file():
   271	        try:
   272	            response = json.loads(response_path.read_text(encoding="utf-8"))
   273	            artifacts = response.get("artifacts", {}) or {}
   274	            if isinstance(artifacts.get("original_ui"), str):
   275	                original_ui_path = Path(artifacts["original_ui"])
   276	            if isinstance(artifacts.get("candidate_ui"), str):
   277	                candidate_ui_path = Path(artifacts["candidate_ui"])
   278	        except (OSError, json.JSONDecodeError):
   279	            pass
   280
   281	    # Fallback to common in-directory locations if response artifacts are absent.
   282	    if original_ui_path is None:
   283	        original_ui_path = output_dir / "original.ui.json"
   284	    if candidate_ui_path is None:
   285	        candidate_ui_path = output_dir / "candidate.ui.json"
   286
   287	    if not original_ui_path.is_file() or not candidate_ui_path.is_file():
   288	        return {
   289	            "pass_": None,
   290	            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
   291	        }
   292
   293	    try:
   294	        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
   295	        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
   296	    except (OSError, json.JSONDecodeError) as exc:
   297	        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}
   298
   299	    system_prompt = _load_prompt()
   300	    implementation_payload = _load_implementation_payload(output_dir)
   301	    schema_context = _schema_context_from_payload(implementation_payload) or {}
   302	    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
   303	    if dataflow_context:
   304	        schema_context["dataflow_context"] = dataflow_context
   305	    if schema_context:
   306	        system_prompt = (
   307	            system_prompt.rstrip()
   308	            + "\n\n## Schema and widget evidence\n"
   309	            "When schema_context is provided, use it to map opaque widget_N fields "
   310	            "to semantic input names. Treat literal widget values as static node "
   311	            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
   312	            "widget's meaning from index order when compiled_api names are available. "
   313	            "If a static widget containing stale or fabricated text is removed while "
   314	            "the relevant linked dynamic input path remains connected, do not treat "
   315	            "that removal as deleting the dynamic dataflow."
   316	        )
   317	    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
   318	    # present, it grounds the judge on what a GOOD result achieves (the outcome +
   319	    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
   320	    # alternative approaches that reach the same outcome count as correct.
   321	    desired = scenario.get("desired")
   322	    if desired:
   323	        system_prompt = (
   324	            system_prompt.rstrip()
   325	            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
   326	            "The scenario author described what a GOOD result looks like below. Use it to "
   327	            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
   328	            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
   329	            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
   330	            "it fully wired/complete (no dangling or broken connections, existing pipeline "
   331	            "not broken), and is the approach a sensible one?\n\n"
   332	            f"Desired outcome: {desired.get('outcome', '')}\n"
   333	            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
   334	            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
   335	        )
   336	    payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
   337	    if desired:
   338	        payload["desired_outcome"] = desired
   339	    if schema_context:
   340	        payload["schema_context"] = schema_context
   341	    user_content = json.dumps(payload, indent=2)
   342
   343	    try:
   344	        response = run_model_turn(
   345	            "evaluate workflow edit against intent",
   346	            messages=[
   347	                {"role": "system", "content": system_prompt},
   348	                {"role": "user", "content": user_content},
   349	            ],
   350	            route=route,
   351	            model=model,
   352	            response_contract="json",
   353	        )
   354	    except Exception as exc:  # noqa: BLE001
   355	        return {"pass_": None, "error": f"model call failed: {exc}"}
   356
   357	    raw = response.get("content") or ""
   358	    if not raw:
   359	        return {"pass_": None, "error": "model returned empty content"}
   360

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '300,355p'; nl -ba tests/live_agentic_harness/assessor.py | sed -n '600,715p'; python -c '
import json
from pathlib import Path
base=Path(\"tests/live_agentic_harness/scenarios\")
for p in sorted(base.glob(\"*.json\")):
 s=json.loads(p.read_text())
 if s.get(\"desired\"):
  a=s.get(\"assessment\",{})
  if not a.get(\"expect_graph_changed\") or a.get(\"skip_intent_judge\"):
   print(\"BAD\",s[\"id\"],a)
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 705ms:
   600	            )
   601	        else:
   602	            issues.append(
   603	                {
   604	                    "check": "effective_edit",
   605	                    "severity": "error",
   606	                    "detail": (
   607	                        f"Expected effective value change for target {label!r}, "
   608	                        f"but it remained {change.after.effective_value!r}."
   609	                    ),
   610	                }
   611	            )
   612	    return issues
   613
   614
   615	def assess_live_output_dir(
   616	    output_dir: Path | str,
   617	    scenario: Mapping[str, Any] | None = None,
   618	) -> dict[str, Any]:
   619	    """Inspect live artifacts under *output_dir* and return an assessment.
   620
   621	    The returned dict has:
   622
   623	    * ``passed`` — True iff no error-level issues were found.
   624	    * ``expect_graph_changed`` — whether the scenario expected an edit.
   625	    * ``issue_count`` / ``error_count`` — counts.
   626	    * ``issues`` — list of ``{"check", "severity", "detail"}`` dicts.
   627	    """
   628	    output_dir = Path(output_dir)
   629	    response = _load_json(output_dir / "response.json")
   630	    impl_result = _load_json(output_dir / "implementation_result.json")
   631
   632	    issues: list[dict[str, Any]] = []
   633	    expect_graph_changed = _expects_graph_changed(scenario, response)
   634	    expected_outcome_kinds = _expected_outcome_kinds(scenario)
   635	    allowed_safe_refusal_outcome_kinds = _allowed_safe_refusal_outcome_kinds(scenario)
   636	    safe_refusal_accepted = False
   637
   638	    if response is not None:
   639	        outcome = response.get("outcome") or {}
   640	        outcome_kind = outcome.get("kind")
   641	        safe_refusal_accepted = (
   642	            expect_graph_changed
   643	            and response.get("graph_unchanged") is True
   644	            and isinstance(outcome_kind, str)
   645	            and outcome_kind in allowed_safe_refusal_outcome_kinds
   646	        )
   647
   648	        # Top-level response health.
   649	        if response.get("ok") is False:
   650	            issues.append(
   651	                {
   652	                    "check": "response_ok",
   653	                    "severity": "error",
   654	                    "detail": f"response.ok is False: {response.get('error') or response.get('message')}",
   655	                }
   656	            )
   657	        elif response.get("error"):
   658	            issues.append(
   659	                {
   660	                    "check": "response_error_field",
   661	                    "severity": "error",
   662	                    "detail": f"response.error set: {response['error']}",
   663	                }
   664	            )
   665
   666	        # Readiness is also captured in flow_metadata, but surface it here if
   667	        # the response carries it (e.g. blocked-prerequisite runs).
   668	        readiness = response.get("readiness") or {}
   669	        if readiness.get("ready") is False:
   670	            issues.append(
   671	                {
   672	                    "check": "response_readiness",
   673	                    "severity": "error",
   674	                    "detail": f"Readiness not ready: {readiness.get('reason')}",
   675	                }
   676	            )
   677
   678	        if expect_graph_changed:
   679	            if safe_refusal_accepted:
   680	                issues.append(
   681	                    {
   682	                        "check": "safe_refusal",
   683	                        "severity": "info",
   684	                        "detail": f"Accepted safe refusal outcome.kind={outcome_kind!r}.",
   685	                    }
   686	                )
   687	            elif response.get("graph_unchanged") is True:
   688	                issues.append(
   689	                    {
   690	                        "check": "graph_changed",
   691	                        "severity": "error",
   692	                        "detail": "Expected graph change but response.graph_unchanged is True.",
   693	                    }
   694	                )
   695
   696	            # G0R structural expected-edit guard: a claimed edit
   697	            # (graph_unchanged is False) must be backed by a positive integer
   698	            # change_details.landed_operation_count.  Missing, malformed, or
   699	            # zero counts fail closed.  Accepted grounded refusals
   700	            # (safe_refusal_accepted) and canonical non-edit routes are
   701	            # exempt — they are scored by their own structured checks.
   702	            route = _canonical_route(response)
   703	            if (
   704	                not safe_refusal_accepted
   705	                and response.get("graph_unchanged") is False
   706	                and not _explicitly_non_edit_route(response)
   707	            ):
   708	                landed_count = _landed_operation_count(response)
   709	                if not (
   710	                    isinstance(landed_count, int)
   711	                    and not isinstance(landed_count, bool)
   712	                    and landed_count > 0
   713	                ):
   714	                    issues.append(
   715	                        {

exec
/bin/zsh -lc "rg -n 'semantic_product|answer_rubric|health_control|excluded_from_semantic_product_rates|semantic.*rate|product.*rate' . --glob '"'!external_workflows/**'"' --glob '"'!.git/**'"' --glob '"'!out/**'"' | head -300" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 210ms:
./docs/failure-analysis/v2/PLAN.md:5:VibeComfy should be built as a **real additive editor**, with the remove→restore demo retained as a subordinate regression suite rather than treated as the product specification. This is a staged verification strategy, not “finish the benchmark, then pivot”: the product path should accept any edit that satisfies an explicit validity contract, while a separate restoration track may require exact functional settings when the user asked to restore prior behavior and trustworthy provenance actually exists. That split changes all three boundaries. The real-editor oracle judges schema validity, role-correct topology, task postconditions, preservation, and—when available—runtime behavior; the restoration oracle may additionally compare against provenance. Research supplies patterns and constraints rather than an answer key. The agent must form and test a placement/value hypothesis, not copy a hidden node. The prior proposal is therefore right that evidence is being lost, but wrong to make exact provenance values the dominant product lever.
./docs/failure-analysis/v2/PLAN.md:53:1. **Make `EditIntent` + validity evaluation the product contract.** Generalize the existing `ExecutionPlan`/plan-evaluation seam so every nontrivial additive edit can express anchors, required roles, ordering/path coverage, value constraints, preservation scope, and acceptable uncertainty. Split verdicts into structural, semantic, runtime, and provenance evidence; retain a separate exact-restore mode. **Why:** this replaces the hidden golden with an explicit definition of success and gives retries actionable failures. **Effort:** 1–2 weeks for the contract, evaluator shell, and several feature validators. **Confidence:** high on architecture, medium on first-pass role coverage. **Cases moved:** directly changes how structurally sound alternatives in 01 and 08 are judged and makes 09's wrong stage an explicit semantic failure; it supplies useful retry evidence for 05 and 06 but does not by itself make their edits land.
./docs/failure-analysis/v2/splice-pipeline-design.md:9:- **`quantized_generation_head` (`68920e773786`)**: the selected Flux precedent contains `7b34ab90-…` as a runtime `class_type`, so semantic validation rejects it as unresolved (`cases/68920e773786/attempts/003/research.json:89-109`). In the source it is actually a subgraph instance whose definition lives under `definitions.subgraphs` (`ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json:111,225-228`). The generated recipe proves the hidden topology is a real loader/conditioning/sampler/decode chain (`ready_templates/image/flux2_klein_9b_gguf_t2i.py:16-77`).
./docs/failure-analysis/v2/value-default-emission-spec.md:64:The existing exact type + incident-edge + positional-widget witness should remain a dedicated restore regression predicate. NORTHSTAR's product-grade oracle should instead issue tiered verdicts for schema validity, role-correct wiring, task postconditions, preservation, and optional runtime evidence. A novel valid addition must not fail merely because its values differ from a hidden golden. Restore identity and product validity are separate claims.
./docs/failure-analysis/v2/capability-transfer-epic-recast.md:11:This also corrects `add-functionality-architecture.md`. Keep its typed boundaries, parameter policies, authoritative schema use, atomic transaction, and semantic postconditions. Reject its reviewed `capability × family × topology` catalog: that is an enumerated implementation table. The durable abstraction is a corpus-extracted `CapabilityModule`; family is provenance and validation context, never a lookup dimension.
./docs/failure-analysis/v2/role-inference-design.md:33:There is a useful cheap proxy before D1 is mature: count viable loci after type filtering, count demanded consumers/parallel paths, count same-class or same-signature siblings along those paths, and flag custom/unresolved schema plus high-impact unspecified values. It is intentionally conservative. It cannot know that two opaque nodes have different semantic roles, so it must record “role unknown” and escalate when the edit depends on choosing one. Mature D1 improves the trigger by replacing duplicate-type counts with calibrated role entropy; it does not eliminate the separate intent and coverage signals.
./docs/failure-analysis/v2/add-functionality-architecture.md:58:The current batch REPL demonstrates rollback and fresh graph-name binding, but the product API should not generate synthetic Python to exploit it. Introduce symbolic handles such as `new:refiner` and a native transaction executor that preallocates or resolves identities while applying ordered operations. This is required for edges between multiple new nodes and outgoing rewires. The transaction should retain ordinary landed operations and receipts for auditability, but a late link or postcondition failure must discard the whole candidate. The existing `PrecedentAdaptationPlan` can inform a new `BoundCapabilityPlan`; its current first-slice/first-role matching and whole-source copying are not safe runtime planning.
./docs/failure-analysis/widget_name_resolution_risks.md:284:3. **Fail closed on semantic gaps.** ACN `strength` cannot be inferred from current evidence. The safe fix leaves it unresolved until a real AdvControlNet schema/curated entry is added.
./docs/templates/readable_ready_template_cleanup_plan.md:720:Moving to semantic node ids is a separate migration that requires a source-id
./docs/templates/readable_ready_template_cleanup_plan.md:1265:| Reusable subgraph promotion | Sprint 5-7 | Promote repeated or semantically coherent imported subgraphs into named Python functions/blocks when that makes the generated workflow easier to read or reuse. Do not preserve opaque wrappers as the final app-active shape. |
./docs/megaplan_chains/excellence_epic/m7-plugin-verbs-release.md:50:Do NOT redesign the runtime factory (sprint 6a) or RunPod session boundary (sprint 6b). Do NOT re-decompose modules (sprint 5). Do NOT change IR-core or emitter semantics (sprints 1/3 own those). Do NOT turn the deferred user-testing idea into a separate framework unless the required acceptance tests force a tiny helper extraction. Do NOT attempt full plugin sandboxing, pip hash enforcement, git signature verification, or run-history UX in this sprint; name those as follow-up work with owners/severity.
./docs/megaplan_chains/excellence_epic/m1-net-and-correctness.md:12:2. **Build a differential round-trip harness** (`tests/test_template_roundtrip.py` + helper): for every ready_template, load → `compile("api")` → compare semantically against the source corpus JSON (widget values, value *types*, edges). Must catch seed→steps, control_after_generate→cfg, voice=bignum, unload_models=bignum.
./tests/browser/agentic_replay.test.mjs:637:// semantics T-032 must preserve when the JSON clones are migrated.
./tests/live_agentic_harness/scenario_manifest.json:142:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:272:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:337:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:376:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:428:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:454:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:519:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:532:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:610:      "scenario_kind": "health_control",
./tests/live_agentic_harness/scenario_manifest.json:619:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:645:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:658:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:684:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:697:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:736:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:814:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:827:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:892:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:905:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:931:      "scenario_kind": "health_control",
./tests/live_agentic_harness/scenario_manifest.json:940:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:953:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:966:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1005:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1018:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1044:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1057:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1083:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1096:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1174:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1187:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1213:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1226:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1252:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1265:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1278:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenario_manifest.json:1291:      "scenario_kind": "semantic_product",
./tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json:37:  "answer_rubric": {
./tests/browser/preview_picker.test.mjs:400:      "demo lifecycle never starts production chat rehydrate",
./tests/browser/preview_picker.test.mjs:440:      "demo agent bubble receives the same projected semantic changes as live rehydrate",
./tests/browser/preview_picker.test.mjs:457:    assert.equal(staleProductionResult.stale, true, "late production rehydrate is fenced");
./docs/megaplan_chains/technical_debt_cleanup/area-digest.md:11:7. Hash/JSON normalization — THREE semantic families: A = _canonical_contract_primitives.py (agent-edit authority; session.py + candidate_transaction.py are facades); B = porting/reorganise/orchestrate.py independent (_freeze_jsonish/_canonical_bytes sort_keys=True); C = web/canonical_hash.js mirror (docstring WRONG: cites orchestrate.py but behavior matches _canonical_contract_primitives). Fix docstring; keep families, document boundaries.
./tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json:37:  "answer_rubric": {
./docs/megaplan_chains/technical_debt_cleanup/resolutions-digest.md:12:S8 deep_plain: MUST implement Family-A manual recursive semantics (map/entries; pass primitives/null/undefined/functions/symbol values through; drop symbol keys; discard prototypes; do NOT preserve repeated refs). Add explicit WeakSet cycle guard (decide throw vs return-original deliberately — both families currently mishandle cycles; JSON family aliases on cycle = bug). Family-B (JSON) call sites must be audited for undefined/fn loss. NO JS tests exist for any clone helper today — add them.
./vibecomfy/porting/edit/_resolve.py:165:    for index, (semantic_name, _socket_type) in enumerate(entries):
./tests/browser/agent_edit_response_contract.test.mjs:1898:// reimplementing Python semantics.  The JS generated module provides
./tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json:32:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json:34:  "answer_rubric": {
./docs/megaplan_chains/technical_debt_cleanup/README.md:88:- ORACLE-5 (after WP-4.5): deep_plain sole clone owner, Group-B semantics explicit, golden fixtures drive constants, generated JS committed. Cmds: clone/contract node tests, codegen pytest, generator diff, `make check`.
./tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json:34:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json:36:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json:34:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json:36:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json:35:  "answer_rubric": {
./tests/browser/roundtrip_smoke.test.mjs:25166:// semantics T-032 must preserve when the JSON clones are migrated.
./docs/megaplan_chains/pristine_cleanup/audit/04-layer2-architecture.md:9:   `vibecomfy/patches/gguf_unet.py:21-38` — Swaps `UNETLoader` → `UnetLoaderGGUF` and changes VAE filenames. This **changes what handles the loader produces** (different node class = different output semantics). The CLAUDE.md rule: *changes-handles → block; decorates-handles → patch*. This should live in `vibecomfy/blocks/`, not patches.
./tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/speed-distillation-research.json:8:    "kind": "health_control",
./tests/live_agentic_harness/scenarios/speed-distillation-research.json:9:    "excluded_from_semantic_product_rates": true,
./tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenario_manifest.py:97:        if (scenario.get("classification") or {}).get("kind") == "health_control":
./tests/live_agentic_harness/scenario_manifest.py:98:            scenario_kind = "health_control"
./tests/live_agentic_harness/scenario_manifest.py:99:        elif scenario.get("answer_rubric"):
./tests/live_agentic_harness/scenario_manifest.py:100:            scenario_kind = "semantic_product"
./tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json:42:    "kind": "health_control",
./tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json:43:    "excluded_from_semantic_product_rates": true,
./tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:37:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json:33:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json:35:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:36:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:38:  "answer_rubric": {
./tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json:35:    "kind": "semantic_product"
./tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json:37:  "answer_rubric": {
./tests/test_refuse.py:3:The spike T4 reproduction (``test_refuses_control_after_generate_slot_drop``)
./tests/test_refuse.py:259:    """Spike T4 reproduction: dropping ``control_after_generate`` from the
./tests/fixtures/node_resolution/ideogram4_t2i.json:2737:              "[META]\nfrozen: false\ndescription: Slim single-shot magic prompt — splatter planning + v15 output discipline, deduped for faster inference. Thinking off.\nthinking_mode: disabled\n\n[SYSTEM]\nYou convert a natural-language user idea into a structured JSON caption an image renderer can consume. You receive the user idea plus a target aspect ratio, and you emit one JSON object.\n\n## OUTPUT CONTRACT — exactly three top-level keys, in this order:\n\n```json\n{\"aspect_ratio\":\"W:H\",\"high_level_description\":\"...\",\"compositional_deconstruction\":{\"background\":\"...\",\"elements\":[ ... ]}}\n```\n\n- Emit a SINGLE-LINE MINIFIED JSON object — no markdown fences, no commentary, no other top-level keys.\n- Preserve non-ASCII characters as-is (CJK, Cyrillic, Devanagari, Arabic, accented Latin). Never escape with `\\uNNNN`, transliterate, or replace `café` with `cafe`.\n- Use SINGLE quotes for embedded text references in prose fields (`'Joe's Diner'`, not `\\\"Joe's Diner\\\"`). The `text` field of text elements is the exception — that field holds the user's verbatim characters, may use any characters, and follows QUOTED SPAN FIDELITY below.\n\n### `aspect_ratio` (first field, always required)\n\nA string in `W:H` form with positive integers (`1:1`, `16:9`, `9:16`, `4:5`, `3:1`, `2:3`, etc.).\n- If the user message gives a concrete `W:H`, echo it verbatim.\n- If the user message says `auto`, pick a concrete ratio that matches the medium and composition (panoramic subjects → wide ratios like `16:9` or `3:1`; portrait subjects → tall like `9:16` or `4:5`; designed artifacts → format conventions like `2:3` book cover, `3:4` poster; ambiguous → `1:1`). NEVER emit the literal string `auto`.\n- The aspect ratio you commit to drives every bbox decision. Pick it first.\n\n### `high_level_description` — observational summary (50-word hard cap)\n\n- ONE long sentence preferred, never more than two.\n- Reads like a short natural-language prompt, not an analysis. Starts immediately with the subject — no \"this image shows\", \"depicts\", \"captures\".\n- Identifies subject(s), medium, and overall composition. Names recognized pop-culture entities by full name (`Nike Air Jordan 1`, `Eiffel Tower`, `Mario (Nintendo character)`).\n- Don't enumerate granular features (every color, every grid dimension, every typography choice). That detail belongs in element descs or `background`.\n- `various`, `multiple`, general categories ARE appropriate here. Specificity rule (below) applies to element descs and `background`, NOT this field.\n- For transparent backgrounds, include the literal phrase `on a transparent background`.\n\nGOOD: `A full-action shot of a male soccer player in a red kit and black Adidas cleats kicking a soccer ball on a green turf field, with a blurred crowd in the stadium background.`\nBAD (over-specifies): `A male soccer player captured mid-kick on a bright green grass pitch, right leg fully extended through the follow-through at the precise moment his black-and-white studded boot makes contact with a white-and-black size-5 ball...`\n\n## ELEMENTS — what they are, what they're not\n\nEach element is one of:\n```\n{\"type\":\"obj\",\"bbox\":[y1,x1,y2,x2],\"desc\":\"...\"}\n{\"type\":\"text\",\"bbox\":[y1,x1,y2,x2],\"text\":\"LINE ONE\\nLINE TWO\",\"desc\":\"...\"}\n```\n\n`bbox` is optional per-element (see BBOX section below).\n\n### SINGLE SUBJECT = SINGLE ELEMENT\n\nA coherent subject — one animal, person, vehicle, building, plant, instrument, machine — is exactly ONE `obj` element. Anatomical and structural parts are descriptive attributes inside that element's `desc`, NOT separate elements.\n\nFORBIDDEN: a bee split into 8 elements (thorax/abdomen/wings/eyes/legs/...); a car split into 6 (body/wheels/windshield/...); a person split into 7 (head/torso/each limb/...); a building split into 5 (foundation/walls/windows/roof/door); a flower split into 3 (petals/stem/leaves).\n\nWhen MULTIPLE distinct subjects appear (a person AND a dog; two bees; three runners), use MULTIPLE elements — one per subject.\n\n**Test:** part-of-one-thing → goes in that thing's desc. Separate thing → its own element.\n\n**Transparent enclosure + featured contents = ONE element.** Display cases, snow globes, terrariums, aquariums, specimen jars, bell jars, vitrines containing a featured subject: name the enclosure + contents as a single unified desc.\n\n**Configured parts + revealed interior = ONE element.** A car with an open door, a machine with raised hood, a building with drawn curtains: the open state and any revealed interior are attributes of the single subject's desc, not separate elements.\n\n### Element desc — what to write (30–60 words, 60-word HARD CAP)\n\nIdentity first, then major attributes briefly, then one distinguishing detail if relevant. Each desc is a standalone catalog entry — open with the subject's identity, not a referring phrase like \"the X\" that assumes the reader has seen the scene.\n\nGOOD (introduces from scratch):\n- `Woman walking on the platform, medium size. Shoulder-length dark wavy hair, medium skin tone, light blue button-down shirt and grey trousers. Small bag slung over the right shoulder.`\n- `Circular concrete tunnel entrance with glowing blue ring lights along the interior. Train tracks lead directly into the dark opening.`\n\n**Major attributes — always name:**\n- People: skin tone, hair (color + style), each visible garment with color, expression/gaze, pose, distinguishing feature (mole, glasses, jewelry, held prop).\n- Objects: shape, material, color, distinctive parts (handle, label, logo, marking).\n- Scenes/structures: type, primary material, color, distinctive structural elements.\n\n**Skip (eat word budget for marginal benefit):**\n- Surface-finish micro-prose (`finely granular matte texture with subtle sheen along the elytral ridges`). Pick one short descriptor (matte/glossy/metallic/textured) or omit.\n- Pose mechanics per-limb. Pick ONE summary action phrase plus the major attributes.\n- Camera/shadow/lighting micro-detail per element. Belongs in `background`.\n- Fabric weave, skin texture nuances, micro-anatomy.\n\n### Element desc — what NOT to include\n\n**No shadows.** Cast shadows, drop shadows, ground shadows, contact shadows, ambient occlusion — describe in `background` only when scene-wide, otherwise omit (the renderer infers them). Forbidden: `casts a thin hard shadow to the lower right`, `with a soft drop shadow beneath`.\n\n**No camera or render language.** Depth of field, focus, sharpness, bokeh, exposure, motion blur, lens flare, chromatic aberration, film grain — render properties belong in `high_level_description` or `background` as natural prose ONLY when the user prompt explicitly named them. NEVER inside an obj desc.\n  - EXCEPTION — viewpoint/angle (`from a low-angle perspective`, `bird's-eye view`, `eye-level`) IS allowed in obj descs when the prompt calls for it. Place once, usually in the focal subject's desc or background.\n\n**No describing impressions instead of physical reality.** Avoid `luminous`, `radiant`, `vibrant`, `lush`, `dynamic`, `glowing` (metaphorically), `gorgeous`, `stunning`, `breathtaking`, `mesmerizing`. Use observable properties: `cheekbone catches a small highlight`, not `luminous complexion`.\n\n**No scene-context repetition per-element.** Lighting direction, ambient surface, mounting context, weather → describe ONCE in `background`. Each element's desc focuses on what's UNIQUE to that element.\n\n### Anchor placements to named references\n\nSpecify body parts, surfaces, spatial landmarks.\n- CORRECT: `applied to the forehead near the hairline above the left eyebrow`.\n- INCORRECT: `pressed against the skin`.\n- CORRECT: `resting on the lower-right corner of the table directly in front of the laptop`.\n- INCORRECT: `sitting on the surface`.\n\n## BACKGROUND — what goes here, what doesn't (CRITICAL)\n\n`background` describes the scene SHELL: walls and finishes, floor/ground and surface state, ceiling and architectural fixtures, windows as architecture, atmospheric context (sky, clouds, fog, dust, mist), scene-wide ambient lighting, distant out-of-focus context (horizon, blurred crowds, distant scenery).\n\n### No double-counting\n\nAnything described in `background` CANNOT also appear as an obj element. Each scene component lives in EXACTLY ONE field. Decide once and commit. Before emitting an obj element, scan `background` — if the component is named there, omit the obj element.\n\n### ALWAYS-BACKGROUND — these live in `background` only, never as obj elements:\n\n- sky, clouds, atmospheric color\n- horizon\n- distant mountains, hills, tree lines\n- atmospheric weather (fog, haze, mist, smoke)\n- distant cityscape or stadium architecture\n- distant blurred or simplified crowds\n- the floor / ground / turf / paving surface the scene sits on\n- ambient walls or studio backdrop behind focal subjects\n\nYou cannot split these by region. `sky upper-left portion`, `sky behind the fortress`, `sky upper two-thirds` are the SAME component — describe in `background` once. Same for crowd, ground, horizon.\n\nIf you want technique-level detail on an atmospheric component (watercolor wet-on-wet sky blooms, fog with directional density variation), put that detail in `background`. The `background` field is allowed to be long.\n\n### Ground/floor/pavement is ALWAYS background — zero tolerance\n\nThe surface the scene sits on — floor, ground, turf, grass, dirt, sand, asphalt, pavement, road, sidewalk, deck, water surface, snow, tile floor, hardwood, marble — lives in `background` only. This holds REGARDLESS of how the input formats it: if the prompt lists `Wet rain-slicked pavement below` as a foreground bullet, RE-CLASSIFY it into background.\n\n**Surface character that belongs in background, not as a separate obj:** wet / rain-slicked / mud-streaked / dusty / cracked / polished / weathered surface state; reflective neon pools, fragmented color reflections, puddles, wet patches, mud patches, ice patches, frost, snow on the floor, water pooled on the ground, oil slicks, footprints, tire tracks; surface material (asphalt, cobblestone, hardwood, tile, marble, packed dirt); texture words for the floor (glassy, mirror-like, matte, polished, rough).\n\n**Puddles, reflections, wet patches are part of the ground surface** — never separate obj elements, regardless of whether they reflect the hero's silhouette or carry visible content.\n\n**Failure mode this prevents:** when a standing hero is the focal element and the floor is also emitted as an obj at the bottom of the frame, the renderer treats the floor obj as a 2D frame band rather than a perspectival receding plane, and clips the hero's legs into it — figure rendered half-in-the-ground with feet/calves buried.\n\n**Discrete objects ON the floor are still elements:** broken glass shards, crushed cans, scattered debris, leaves, rocks, dropped tools, brick fragments, foreground litter remain obj elements. The rule applies to the SURFACE itself and any state of that surface (wet, frozen, muddy, puddled), never to solid objects resting on it.\n\n### Background is the shell only — no individually-placeable things\n\nFurniture, vehicles, equipment, people, animals, decor (artwork, signs, plants in pots, stacks of books), free-standing lamps → obj elements, never `background`.\n\n### Shell-affixed prominent objects → DUAL MENTION\n\nSome objects are simultaneously part of the shell AND focal elements that define the room's identity: a chalkboard covering the back wall of a classroom, a fireplace built into a living-room wall, a large mounted TV, a stage proscenium, a built-in altar, a built-in bookshelf, a large fixed reception desk, a fixed sign/banner.\n\nFor these, MANDATORY all three steps:\n1. **MENTION in `background`** as part of the shell — anchors the object to the wall.\n2. **EMIT as an obj element** with the qualifier `\"the primary background element\"` (or similar) at the start of its desc. The obj carries the detail (material, content, frame, mounting).\n3. **PLACE FIRST in the elements list** so painter's-algorithm draws it behind foreground items.\n\nSkipping step 1 (the most common failure) makes the renderer float the object in mid-room or render it in front of foreground subjects.\n\nThis is an EXCEPTION to the shell rule's \"no individually placeable things\". Applies ONLY to objects that genuinely define the room's architectural identity. Free-standing items (chairs, table lamps, plants in pots, framed pictures on a wall) get the normal treatment: elements only, no background mention.\n\n### Recession/arrangement is not architecture\n\nDo not smuggle furniture or people into `background` by describing them as a receding arrangement. Forbidden background phrasings: `rows of desks recede toward the back`, `a grid of desks fills the room`, `students seated at the desks`, `chairs arranged in front of the podium`, `the room is filled with people`, `cars parked along the street`, `customers seated at the tables`. The arrangement IS the foreground content — emit elements.\n\n### No medium/post-processing effects in background\n\n`background` describes WHAT is in the scene, not HOW it was made. Forbidden in `background` — even when the prompt names the effect (route those to HLD instead):\n- Film grain, Kodak/Portra/Tri-X grain, ISO noise\n- Lens flare, chromatic aberration, vignetting, bokeh quality\n- Color cast / film-stock shift (warm shift, cool shift)\n- Paper texture, paper grain, canvas texture\n- Brushstroke texture, palette-knife texture\n- Halftone dots, screen-print texture, risograph texture\n\n**Test:** read `background` aloud. If you can picture the EMPTY room from the description — no furniture, no people, no equipment, no wall decor — you're in the shell. If anything disappears when you remove the room's contents, the background has leaked.\n\n## BBOX STRATEGY\n\nINCLUDE bboxes on elements where precise positioning matters — portrait subjects, products on a surface, logos, signs on a wall, distinct individually-placeable objects.\n\nOMIT bboxes on elements that represent dense or hard-to-enumerate visuals — crowds, fields of wildflowers, scattered particles, starry skies. Per-element judgment.\n\n### Coordinate system\n\nCoordinates are normalized to the target image shape: `x` runs left→right along full width (0 = left edge, 1000 = right), `y` runs top→bottom along full height (0 = top, 1000 = bottom). Top-left origin. Format `[y1, x1, y2, x2]` with `y1 < y2`, `x1 < x2`.\n\n### Shape warning (common failure)\n\nBbox values are normalized to 0–1000 in BOTH axes. A square `[0, 0, 500, 500]` is square only on a square frame; on 16:9 it becomes a wide rectangle, on 9:16 a tall rectangle. Most bbox failures (extra subjects, duplicates, mis-scaled objects) come from this mismatch.\n\nFor round objects or square on-screen regions, scale spans so `(x2-x1)/(y2-y1) ≈ W/H`. For single-subject prompts on wide frames, prefer narrower x-spans. For multi-subject prompts, give each a tight bbox so no one bbox dominates and invites a duplicate.\n\n## SPECIFICITY — commit to one value\n\nThis JSON feeds a diffusion model. Leave nothing for the model to invent or choose.\n\n**Banned hedge phrasings** (in elements and background): `things like`, `such as`, `e.g.`, `for example`, `or similar`, `various`, `could include`, `might be`, `some kind of`, `style of`. Replace with concrete nouns, counts, colors, materials, poses.\n\n**Banned alternative listings for one property:** `pale institutional off-white or pale green`, `oak or walnut`, `cream or ivory`, `late afternoon or early evening`, `italic serif or italic sans-serif`, `bold or semibold`. Pick ONE and commit. `or` is reserved for the loader's exclusive-choice idiom (`'YES' or 'NO'`), not captioner hedging.\n\n**Typography specifically:** name ONE typeface category (serif OR sans-serif OR display OR script OR monospace), ONE weight (bold/regular/light/medium), ONE style (italic OR upright). Never two joined by `or`.\n\n**Banned \"implied/suggested\" hedges:** `a desk corner implied`, `a chair suggested beneath the figure`, `a building hinted at`, `a shadow that reads as a person`. If it's in the scene, paint it concretely. If it isn't, leave it out. Forbidden words: `implied, suggested, hinted, barely visible, possibly, perhaps, maybe, might be, could be, reads as, almost`.\n\n**Exhaustive content preservation.** When the user provides enumerable content — schedules, itineraries, lists, menu items, steps, names, times — every item must appear in the output. Use as many text elements as needed; never sacrifice completeness for layout.\n\n**Named prompt elements MUST appear.** Every explicitly-named visual unit in the user prompt MUST appear as its own element:\n- Input `text:` sections — every entry becomes its own text element, verbatim. Zero tolerance: 3 entries in input → ≥3 text elements in output. Empty `text: []` is the only case where text elements may be omitted on that basis.\n- Quoted strings (single or double quotes) — each is its own text element.\n- Speech bubbles / dialogue callouts / thought bubbles / captions — each gets a text element for the quoted string AND an obj element for the bubble/balloon/container.\n- Named decorative elements (`small medical cross icon top-left`, `airplane arc trajectory`, `flame-lick flourish at the tail`) — each gets its own obj.\n- Named badges / chips / CTAs / strips — each gets its own obj (and text if it carries a quoted string).\n- Named accents / graphic devices (`hairline rule`, `dot grid`, `accent line`, `divider`) — each gets its own obj UNLESS it's a scene-wide overlay belonging in `background`.\n\n**Test before emitting:** count named visual units in the user prompt; element list must contain at least that many.\n\n**No placeholder enumeration.** When the imagined image contains a sequentially-numbered, alphabetically-labeled, or otherwise individually-identified set (stones numbered 1–50, parking spaces A1–A20, place cards `1st`–`12th`, a periodic table of 118 elements, a calendar grid of 31 dates, a 22-name team roster), EACH item is its own element. No `etc.`, no `and so on`, no `6 through 49`, no single obj grouping all into one cluster. List ALL of them.\n\nThe \"dense unenumerable group\" exception (crowd of thousands, field of wildflowers, starry sky) does NOT apply to enumerable sets — if items are sequentially identified, they're enumerable BY DEFINITION.\n\n**Don't invent visual concepts the user didn't ask for.** Forbidden without explicit user request: `glitch art`, `wireframe overlay`, `mesh that fragments the body`, `digital artifacts`, `dissolved`, `decompose`. If the prompt asks for a cinematic photo of a journalist, render a cinematic photo of a journalist — not a glitch-art composite.\n\n## PLANNING — turn the user idea into elements\n\n### 1. Pick a medium\n\n`photograph | illustration | 3D render | graphic design` — applies as natural-language framing inside HLD/background, NOT as a structured slot.\n\nDecision: **DESIGNED artifact vs CAPTURED / DRAWN / RENDERED moment.**\n- **graphic design** — poster, book cover, album cover, magazine cover, flyer, banner, social post, sticker, logo, wordmark, packaging, app icon, UI mockup, infographic, menu, greeting card, ticket, signage. If a human designer would sit at a desk to make it.\n- **photograph** — portrait, landscape, lifestyle, street, sport, wildlife, food, product, fashion editorial (when described as a photograph). Default for ambiguous everyday scenes.\n- **illustration** — cartoon, anime, manga, comic, watercolor, oil painting, ink, vector, pixel art, children's book illustration, named studios (Ghibli, KyoAni, Pixar 2D).\n- **3D render** — CGI, octane/unreal/blender, hyperrealistic product render, arch viz, isometric low-poly, voxel, named 3D studios.\n\nSilent / ambiguous → photograph (default). The subject's reality status does NOT override this default — wizards, dragons, aliens, robots in a photograph are valid; the brief must explicitly ASK for illustration / painting / render to get one.\n\nImperative verbs at the start (\"Illustrate a…\", \"Paint a…\", \"Draw a…\", \"Render a…\") are NOT medium signals — they mean \"depict / show\". Default to photograph unless an explicit medium-noun or style name appears.\n\n### 2. Style commitment\n\nInside HLD/background prose, name the style ONCE (`Studio Ghibli animation`, `Pixar 3D animation`, `35mm film photograph`, `iPhone photo`, `editorial digital painting`, `flat vector illustration`). Keep it short — recognizable style names are enough; the renderer knows them. Don't append technique detail (`with hand-painted gouache backgrounds`) on top of well-known names.\n\n**\"Professional picture/photo/portrait\" of a person means PROFESSIONAL CONTEXT, not professional camera equipment.** Read as corporate headshot, LinkedIn profile, business bio — neutral business attire, soft even daylight, neutral backdrop, friendly approachable expression. NOT dramatic studio rim-lighting, creamy DSLR bokeh, dark moody backdrop.\n\n### 3. Photoreal defaults — AVOID \"warm\"\n\nFor photographic prompts (no specified medium beyond `photo`/`photorealistic`/`selfie`/real-world scene):\n- Default to iPhone aesthetic — phone snapshot, ambient natural light, neutral white balance, accurate (not flattering) skin tones, ordinary framing. AVOID DSLR-magazine markers (creamy bokeh, telephoto compression, dramatic rim lighting, cinematic grade) — those signal AI-generation.\n- Default lighting framing: `natural daylight`, `overcast daylight`, `diffused daylight`, `cool-neutral white balance`. The word **\"warm\"** (in any phrase: `warm light`, `warm window light`, `warm tone`, `warm grading`) is BANNED as a grading adjective — it triggers the amber/golden AI look that ruins photorealism. When a scene physically has a warm-coloured light source (candle, sodium streetlamp, sunset), describe the SOURCE concretely (`candle flame`, `sodium streetlamp`) and the colour of the LIGHT POOL (`amber pool from the candle`) — but the global grade stays neutral.\n- Default composition: prefer non-centered framing (off-center, rule-of-thirds, asymmetrical, leading lines) for portraits, products, single-subject scenes. Use centered framing ONLY when the prompt explicitly calls for it (`centered`, `symmetrical`, `mandala`, `kaleidoscope`) or when the genre is inherently symmetric.\n- No motion blur in candid/realistic/iPhone-aesthetic photos. Motion blur is a craft signature (long-exposure pans, light streaks); using it in a candid signals AI. Real phone snapshots freeze the moment.\n- Saturation: don't stack `vibrant + bright + intense + saturated + electric + neon` for a neutral subject. Mention saturation ONCE (in HLD or background) only when the prompt explicitly asks.\n\n### 4. Populate underspecified scenes\n\nWhen the brief is sparse, don't render only what's explicitly named. Real scenes are populated. Add believable secondary subjects, micro-props that imply the subject's life, environmental texture, small narrative moments. Each invented element should belong in the world the brief implies — a paddy-field food stall plausibly has a chicken, a sauce bowl, a hand-painted price sign, a lantern.\n\n**Populate by depth layer.** Foreground (often-skipped), midground, background — each gets its own content. A foreground crop (an out-of-focus leaf at the bottom corner, the rim of a bowl, a fly mid-air close to camera) separates a real photograph from a postcard.\n\n**Commit to a specific cultural / regional identity.** \"Southeast Asian village\" is a hedge that produces generic AI visuals. \"Vietnamese pho stall by the rice paddies outside Hoi An\" is a real place. Specific commitment shapes architecture, signage script, food, dress, props.\n\n**Built environments need text everywhere.** Real shops, stalls, restaurants, vehicles, signage carry text on practically every surface. Generate text generously: shop name sign, sub-signs (`OPEN` / `TODAY'S SPECIAL`), menu board with handwritten items, price labels, jar/bottle labels, name tags, posters, fortune slips, vehicle/equipment labels, sponsor logos. `text: []` is almost always wrong for built environments — if your scene has a shop/stall/restaurant/workshop/market/vehicle, populate text. Specific content, never `various labels` or `menu items`.\n\n**Override:** when the brief explicitly says `minimal`, `sparse`, `empty`, `lonely`, `isolated`, `quiet`, `still`, `negative space`, `alone`, `single subject`, `in the middle of nowhere`, respect the restraint and skip populate.\n\n**Fantastical / sci-fi / fantasy / futuristic briefs get a populate bonus.** Stack sky drama (galaxies, ringed planets, multiple moons, nebulae), opposing focal points (volcano right / waterfall left), mid-distance scale anchors (crystal columns, futuristic cityscape, megastructures), light/energy effects throughout, exotic architecture/geology, deeply saturated palettes.\n\n## TEXT HANDLING\n\nFor each text element:\n- `text` — literal characters appearing in the image, verbatim. Preserve diacritics, capitalization, punctuation. Never transliterate or strip.\n- `bbox` — optional, same coordinate system as obj elements.\n- `desc` — free-form prose covering size, location, font style, color, orientation, visual effects.\n\n**Sources of text to include:**\n1. **User-quoted text** (single OR double quotes) — verbatim, exact characters.\n2. **Format-required text** — headlines, taglines, author names, dates, venues, CTA copy, brand names, publisher marks, edition numbers (when format implies them).\n3. **In-scene contextual text** — signage, labels, license plates, badges, jersey numbers, t-shirt prints, awnings, neon signs, name tags.\n4. **Numeric content** — race numbers, jersey numbers, dates, prices, scores, time displays, address numbers. Numbers ARE text.\n5. **Prominent product brand text** — if an element names a prominent product (bottle, cosmetic, package, beverage) and the user didn't supply a real brand, invent a complete brand identity and list every label as text elements.\n\n**Rules:**\n- Exhaustive: if a viewer could read it, it goes in the list.\n- Each text element appears ONCE in the list. Do NOT also describe its characters in `description` — refer by role/position instead.\n- Use `\\n` for line breaks WITHIN a single text element (multi-line sign, stacked headline). Use SEPARATE list items for visually distinct text blocks.\n- For stylized hero typography where each letter is a distinct visual unit, stack with `\\n` at natural word breaks — long single-line stylized titles produce typos and dropped letters. e.g., `\"ENTRE\\nVERSOS E\\nCONTOS\"` not `\"ENTRE VERSOS E CONTOS\"`.\n- **Language scoping:** `scene`/`elements`/`description`/position descriptors are always in ENGLISH regardless of the user's brief language. Only the literal `text` field characters follow the user's brief language. Portuguese brief → English prose + Portuguese `text:` content.\n\n## POP CULTURE, BRANDS, NAMED REFERENCES\n\nWhen the user idea names or clearly implies a brand, trademark, product (sneaker/car/device), public figure, athlete, musician, actor, fictional character, film, show, game, franchise, team — the output MUST carry an explicit named reference in the relevant element `desc`, not a generic stand-in describing the look.\n\nDon't replace `Nike Dunk Low Panda` with `black and white retro sneakers`, `Spider-Man` with `a red-and-blue masked superhero`, `The Beatles` with `four men in matching suits` — unless the user asked for an anonymous lookalike. Name the specific thing the user pointed at.\n\n## TRANSPARENT BACKGROUND\n\nIf the user's idea calls for transparent background, transparent canvas, alpha channel, cutout/isolated subject, sticker-style with no backdrop, or similar, the `background` field MUST be exactly this string, verbatim and nothing else: `transparent background`\n\nDo not paraphrase (no `clear backdrop`, `empty alpha`, `no background`, `PNG transparency`).\n\nIn `high_level_description`, include the literal phrase `on a transparent background`.\n\n[USER]\nTARGET IMAGE ASPECT RATIO: {{width}}:{{height}} (width:height).\nUser idea: {{original_prompt}}"
./tests/fixtures/node_resolution/ideogram4_t2i.expected_emit.py:12:    definitions={'subgraphs': [{'id': '83e6e004-48ea-408e-9024-eb49c3d7dc14', 'version': 1, 'state': {'lastGroupId': 9, 'lastNodeId': 176, 'lastLinkId': 252, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': 'Text to Image (Ideogram v4)', 'inputNode': {'id': -10, 'bounding': [3490, 920, 154.921875, 228]}, 'outputNode': {'id': -20, 'bounding': [6850, 936, 128, 68]}, 'inputs': [{'id': '4bc742d1-7b4b-452c-90d9-0d76ebcdae76', 'name': 'text', 'type': 'STRING', 'linkIds': [152], 'label': 'prompt', 'pos': [3620.921875, 944]}, {'id': '8d4038eb-73c7-45e9-bba1-f068f55e8d32', 'name': 'value', 'type': 'INT', 'linkIds': [153], 'label': 'width', 'pos': [3620.921875, 964]}, {'id': '281550e6-6acf-4cbe-aec1-9eb803b4dec1', 'name': 'value_1', 'type': 'INT', 'linkIds': [154], 'label': 'height', 'pos': [3620.921875, 984]}, {'id': 'fae56884-2f1a-470b-a25f-40e7a87ef69d', 'name': 'noise_seed', 'type': 'INT', 'linkIds': [155], 'pos': [3620.921875, 1004]}, {'id': '3497309c-a7d7-4e28-9330-142c15881632', 'name': 'unet_name', 'type': 'COMBO', 'linkIds': [156], 'pos': [3620.921875, 1024]}, {'id': 'e87126db-7147-465e-b129-370ed2c6cc22', 'name': 'clip_name', 'type': 'COMBO', 'linkIds': [157], 'pos': [3620.921875, 1044]}, {'id': 'a1e6c080-b11b-4d5c-a3a8-fcf4df654cf7', 'name': 'vae_name', 'type': 'COMBO', 'linkIds': [158], 'pos': [3620.921875, 1064]}, {'id': 'b0d16516-95de-44d9-bea8-3cd2e7c78e9a', 'name': 'unet_name_1', 'type': 'COMBO', 'linkIds': [216], 'label': 'unconditional_unet', 'pos': [3620.921875, 1084]}, {'id': '249fd825-e6b3-489d-a341-6d8050500f5e', 'name': 'choice', 'type': 'COMBO', 'linkIds': [219], 'label': 'mode', 'pos': [3620.921875, 1104]}], 'outputs': [{'id': 'b81e4f60-e543-4f02-875b-b0f1bdc274f2', 'name': 'IMAGE', 'type': 'IMAGE', 'linkIds': [25], 'localized_name': 'IMAGE', 'pos': [6874, 960]}], 'widgets': [], 'nodes': [{'id': 9, 'type': 'VAELoader', 'pos': [4730, 1220], 'size': [470, 110], 'flags': {}, 'order': 1, 'mode': 0, 'inputs': [{'localized_name': 'vae_name', 'name': 'vae_name', 'type': 'COMBO', 'widget': {'name': 'vae_name'}, 'link': 158}], 'outputs': [{'localized_name': 'VAE', 'name': 'VAE', 'type': 'VAE', 'links': [17]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'VAELoader', 'models': [{'name': 'flux2-vae.safetensors', 'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors', 'directory': 'vae'}]}, 'widgets_values': ['flux2-vae.safetensors']}, {'id': 10, 'type': 'ConditioningZeroOut', 'pos': [5450, 960], 'size': [250, 80], 'flags': {'collapsed': False}, 'order': 2, 'mode': 0, 'inputs': [{'localized_name': 'conditioning', 'name': 'conditioning', 'type': 'CONDITIONING', 'link': 8}], 'outputs': [{'localized_name': 'CONDITIONING', 'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [214]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.9.1', 'Node name for S&R': 'ConditioningZeroOut'}, 'widgets_values': []}, {'id': 11, 'type': 'EmptyFlux2LatentImage', 'pos': [5330, 1180], 'size': [270, 170], 'flags': {}, 'order': 3, 'mode': 0, 'inputs': [{'localized_name': 'width', 'name': 'width', 'type': 'INT', 'widget': {'name': 'width'}, 'link': 33}, {'localized_name': 'height', 'name': 'height', 'type': 'INT', 'widget': {'name': 'height'}, 'link': 36}], 'outputs': [{'localized_name': 'LATENT', 'name': 'LATENT', 'type': 'LATENT', 'links': [15]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'EmptyFlux2LatentImage'}, 'widgets_values': [1024, 1024, 1]}, {'id': 12, 'type': 'SamplerCustomAdvanced', 'pos': [6160, 500], 'size': [290, 170], 'flags': {}, 'order': 4, 'mode': 0, 'inputs': [{'localized_name': 'noise', 'name': 'noise', 'type': 'NOISE', 'link': 11}, {'localized_name': 'guider', 'name': 'guider', 'type': 'GUIDER', 'link': 215}, {'localized_name': 'sampler', 'name': 'sampler', 'type': 'SAMPLER', 'link': 13}, {'localized_name': 'sigmas', 'name': 'sigmas', 'type': 'SIGMAS', 'link': 14}, {'localized_name': 'latent_image', 'name': 'latent_image', 'type': 'LATENT', 'link': 15}], 'outputs': [{'localized_name': 'output', 'name': 'output', 'type': 'LATENT', 'links': [16]}, {'localized_name': 'denoised_output', 'name': 'denoised_output', 'type': 'LATENT', 'links': []}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'SamplerCustomAdvanced'}, 'widgets_values': []}, {'id': 13, 'type': 'VAEDecode', 'pos': [6560, 500], 'size': [230, 100], 'flags': {}, 'order': 5, 'mode': 0, 'inputs': [{'localized_name': 'samples', 'name': 'samples', 'type': 'LATENT', 'link': 16}, {'localized_name': 'vae', 'name': 'vae', 'type': 'VAE', 'link': 17}], 'outputs': [{'localized_name': 'IMAGE', 'name': 'IMAGE', 'type': 'IMAGE', 'slot_index': 0, 'links': [25]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'VAEDecode'}, 'widgets_values': []}, {'id': 16, 'type': 'KSamplerSelect', 'pos': [5790, 1100], 'size': [270, 110], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [{'localized_name': 'SAMPLER', 'name': 'SAMPLER', 'type': 'SAMPLER', 'links': [13]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'KSamplerSelect'}, 'widgets_values': ['euler']}, {'id': 17, 'type': 'Ideogram4Scheduler', 'pos': [5790, 1260], 'size': [270, 240], 'flags': {}, 'order': 7, 'mode': 0, 'inputs': [{'localized_name': 'steps', 'name': 'steps', 'type': 'INT', 'widget': {'name': 'steps'}, 'link': 207}, {'localized_name': 'width', 'name': 'width', 'type': 'INT', 'widget': {'name': 'width'}, 'link': 34}, {'localized_name': 'height', 'name': 'height', 'type': 'INT', 'widget': {'name': 'height'}, 'link': 37}, {'localized_name': 'mu', 'name': 'mu', 'type': 'FLOAT', 'widget': {'name': 'mu'}, 'link': 208}, {'localized_name': 'std', 'name': 'std', 'type': 'FLOAT', 'widget': {'name': 'std'}, 'link': 209}], 'outputs': [{'localized_name': 'SIGMAS', 'name': 'SIGMAS', 'type': 'SIGMAS', 'links': [14]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'Ideogram4Scheduler'}, 'widgets_values': [20, 1024, 1024, 0.5, 1.75]}, {'id': 18, 'type': 'RandomNoise', 'pos': [5780, 490], 'size': [270, 110], 'flags': {}, 'order': 8, 'mode': 0, 'inputs': [{'localized_name': 'noise_seed', 'name': 'noise_seed', 'type': 'INT', 'widget': {'name': 'noise_seed'}, 'link': 155}], 'outputs': [{'localized_name': 'NOISE', 'name': 'NOISE', 'type': 'NOISE', 'links': [11]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'RandomNoise'}, 'widgets_values': [885894517601261, 'randomize']}, {'id': 23, 'type': 'UNETLoader', 'pos': [4720, 520], 'size': [470, 170], 'flags': {}, 'order': 9, 'mode': 0, 'showAdvanced': True, 'inputs': [{'localized_name': 'unet_name', 'name': 'unet_name', 'type': 'COMBO', 'widget': {'name': 'unet_name'}, 'link': 156}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [222]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'UNETLoader', 'models': [{'name': 'ideogram4_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/diffusion_models/ideogram4_fp8_scaled.safetensors', 'directory': 'diffusion_models'}]}, 'widgets_values': ['ideogram4_fp8_scaled.safetensors', 'default']}, {'id': 24, 'type': 'CLIPTextEncode', 'pos': [5270, 500], 'size': [430, 420], 'flags': {}, 'order': 10, 'mode': 0, 'inputs': [{'localized_name': 'clip', 'name': 'clip', 'type': 'CLIP', 'link': 24}, {'localized_name': 'text', 'name': 'text', 'type': 'STRING', 'widget': {'name': 'text'}, 'link': 152}], 'outputs': [{'localized_name': 'CONDITIONING', 'name': 'CONDITIONING', 'type': 'CONDITIONING', 'slot_index': 0, 'links': [8, 213]}], 'title': 'CLIP Text Encode (Positive Prompt)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'CLIPTextEncode'}, 'widgets_values': ['{\n    "high_level_description": "A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling \'COMFY\'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying an effortless, cozy vibe.",\n    "style_description": {\n        "aesthetics": "Retro magazine cutout style, mixed-media digital collage, high-contrast streetwear graphic, featuring rough ripped paper edges and distressed grunge textures.",\n        "lighting": "High-contrast flash mixed with harsh midday sunlight on the skater cutout, contrasting with flat, bright graphic lighting on the 3D typography.",\n        "photo": "Vintage grainy 35mm film with distressed halftone scan textures and subtle light leaks.",\n        "medium": "Mixed-media digital collage",\n        "color_palette": ["#1E73BE", "#FDFDFD", "#C82A2A", "#657C9C", "#EFEFEF"]\n    },\n    "compositional_deconstruction": {\n        "background": "A vibrant, clear blue sky layered with a vintage grainy film texture and subtle halftone dot patterns, transitioning down to an implied pale gray concrete ramp at the very bottom edge.",\n        "elements": [\n            {\n                "type": "obj",\n                "bbox": [128, 149, 354, 810],\n                "desc": "Massive 3D puffy, inflatable white typography spelling \'COMFY\'. The letters stretch across the upper half of the canvas, acting as a surreal, soft cloud-like backdrop.",\n                "color_palette": ["#FDFDFD", "#E0E0E0", "#D3DBE2"]\n            },\n            {\n                "type": "obj",\n                "bbox": [459, 37, 727, 264],\n                "desc": "A cluster of oversized, distressed red stamped circles and dots, applied loosely to the midground like a grunge ink stamp, partially obscuring the bottom left of the text.",\n                "color_palette": ["#C82A2A", "#A11D1D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [23, 366, 153, 666],\n                "desc": "A vertically oriented, torn paper side banner pinned to the left edge. The rough-edged paper displays the bold, stamped text \'STAY COZY\' in high-contrast black ink.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [287, 210, 756, 819],\n                "desc": "A sharp photographic cutout of a skateboarder mid-air in a relaxed pose. He wears loose-fitting washed denim jeans and a plain white tee, appearing to effortlessly float above the concrete ramp. A distinct white cutout border surrounds his silhouette.",\n                "color_palette": ["#FDFDFD", "#657C9C", "#2B2B2B", "#DCA57D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [773, 39, 973, 187],\n                "desc": "A surreal, miniature floating skateboard cutout, positioned playfully in the upper right sky as if defying gravity.",\n                "color_palette": ["#D2A679", "#2B2B2B", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [105, 830, 905, 980],\n                "desc": "A wide, horizontal strip of heavily textured torn paper spanning the lower third of the composition. It features the bold typographic phrase \'BEYOND THE COMFORT ZONE\' intermixed with \'EFFORTLESS RIDE\' alongside ripped edges that reveal the background.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#999999"]\n            }\n        ]\n    }\n}']}, {'id': 14, 'type': 'CLIPLoader', 'pos': [4730, 990], 'size': [470, 170], 'flags': {}, 'order': 6, 'mode': 0, 'inputs': [{'localized_name': 'clip_name', 'name': 'clip_name', 'type': 'COMBO', 'widget': {'name': 'clip_name'}, 'link': 157}], 'outputs': [{'localized_name': 'CLIP', 'name': 'CLIP', 'type': 'CLIP', 'links': [24]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'CLIPLoader', 'models': [{'name': 'qwen3vl_8b_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors', 'directory': 'text_encoders'}]}, 'widgets_values': ['qwen3vl_8b_fp8_scaled.safetensors', 'ideogram4', 'default']}, {'id': 27, 'type': 'PrimitiveInt', 'pos': [4240, 1610], 'size': [270, 110], 'flags': {}, 'order': 11, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'INT', 'widget': {'name': 'value'}, 'link': 153}], 'outputs': [{'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [32]}], 'title': 'Int (Width)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveInt'}, 'widgets_values': [1024, 'fixed']}, {'id': 28, 'type': 'PrimitiveInt', 'pos': [4250, 1800], 'size': [270, 110], 'flags': {}, 'order': 12, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'INT', 'widget': {'name': 'value'}, 'link': 154}], 'outputs': [{'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [35]}], 'title': 'Int (Height)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveInt'}, 'widgets_values': [1024, 'fixed']}, {'id': 31, 'type': 'ComfyMathExpression', 'pos': [5340, 1400], 'size': [230, 80], 'flags': {'collapsed': True}, 'order': 13, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 32}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [33, 34]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 32, 'type': 'ComfyMathExpression', 'pos': [5350, 1470], 'size': [230, 80], 'flags': {'collapsed': True}, 'order': 14, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 35}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [36, 37]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 144, 'type': 'ComfyNumberConvert', 'pos': [5920, 1870], 'size': [230, 100], 'flags': {}, 'order': 15, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 195}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': [208]}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 145, 'type': 'JsonExtractString', 'pos': [5450, 1870], 'size': [400, 200], 'flags': {}, 'order': 16, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 196}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [195]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'mu']}, {'id': 146, 'type': 'ComfyNumberConvert', 'pos': [5930, 2110], 'size': [230, 100], 'flags': {}, 'order': 17, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 197}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': [209]}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 147, 'type': 'JsonExtractString', 'pos': [5010, 1630], 'size': [410, 470], 'flags': {}, 'order': 18, 'mode': 0, 'inputs': [{'localized_name': 'key', 'name': 'key', 'type': 'STRING', 'widget': {'name': 'key'}, 'link': 218}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [199]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['{\n  "Quality": {\n    "num_steps": 48,\n    "mu": 0.0,\n    "std": 1.5,\n    "preset_id": "V4_QUALITY_48"\n  },\n  "Default": {\n    "num_steps": 20,\n    "mu": 0.0,\n    "std": 1.75,\n    "preset_id": "V4_DEFAULT_20"\n  },\n  "Turbo": {\n    "num_steps": 12,\n    "mu": 0.5,\n    "std": 1.75,\n    "preset_id": "V4_TURBO_12"\n  }\n}', 'Default']}, {'id': 148, 'type': 'StringReplace', 'pos': [5050, 2150], 'size': [230, 40], 'flags': {'collapsed': True}, 'order': 19, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 199}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [196, 200, 201]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', "'", '"']}, {'id': 149, 'type': 'JsonExtractString', 'pos': [5460, 1610], 'size': [400, 200], 'flags': {}, 'order': 20, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 200}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [202]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'num_steps']}, {'id': 150, 'type': 'JsonExtractString', 'pos': [5450, 2110], 'size': [400, 200], 'flags': {}, 'order': 21, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 201}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [197]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'std']}, {'id': 151, 'type': 'ComfyNumberConvert', 'pos': [5920, 1620], 'size': [230, 100], 'flags': {}, 'order': 22, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 202}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': []}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [207]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 154, 'type': 'UNETLoader', 'pos': [4730, 740], 'size': [470, 170], 'flags': {}, 'order': 23, 'mode': 0, 'showAdvanced': True, 'inputs': [{'localized_name': 'unet_name', 'name': 'unet_name', 'type': 'COMBO', 'widget': {'name': 'unet_name'}, 'link': 216}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [211]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'UNETLoader', 'models': [{'name': 'ideogram4_unconditional_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors', 'directory': 'diffusion_models'}]}, 'widgets_values': ['ideogram4_unconditional_fp8_scaled.safetensors', 'default']}, {'id': 155, 'type': 'DualModelGuider', 'pos': [5790, 870], 'size': [270, 180], 'flags': {}, 'order': 24, 'mode': 0, 'inputs': [{'localized_name': 'model', 'name': 'model', 'type': 'MODEL', 'link': 223}, {'localized_name': 'positive', 'name': 'positive', 'type': 'CONDITIONING', 'link': 213}, {'localized_name': 'model_negative', 'name': 'model_negative', 'shape': 7, 'type': 'MODEL', 'link': 211}, {'localized_name': 'negative', 'name': 'negative', 'shape': 7, 'type': 'CONDITIONING', 'link': 214}], 'outputs': [{'localized_name': 'GUIDER', 'name': 'GUIDER', 'type': 'GUIDER', 'links': [215]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'DualModelGuider'}, 'widgets_values': [7]}, {'id': 156, 'type': 'CustomCombo', 'pos': [4720, 1630], 'size': [270, 280], 'flags': {}, 'order': 25, 'mode': 0, 'inputs': [{'localized_name': 'choice', 'name': 'choice', 'type': 'COMBO', 'widget': {'name': 'choice'}, 'link': 219}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [218]}, {'localized_name': 'INDEX', 'name': 'INDEX', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'CustomCombo'}, 'widgets_values': ['Default', 1, 'Quality', 'Default', 'Turbo', '']}, {'id': 157, 'type': 'CFGOverride', 'pos': [5790, 650], 'size': [260, 170], 'flags': {}, 'order': 26, 'mode': 0, 'inputs': [{'localized_name': 'model', 'name': 'model', 'type': 'MODEL', 'link': 222}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [223]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'CFGOverride'}, 'widgets_values': [3, 0.7, 1]}], 'groups': [{'id': 1, 'title': 'Models', 'bounding': [4700, 420, 530, 1100], 'color': '#3f789e', 'flags': {}}, {'id': 2, 'title': 'Latent Size', 'bounding': [5260, 1080, 450, 440], 'color': '#3f789e', 'flags': {}}, {'id': 3, 'title': 'Sampling', 'bounding': [5740, 420, 780, 1100], 'color': '#3f789e', 'flags': {}}, {'id': 4, 'title': 'Prompt', 'bounding': [5260, 420, 450, 640], 'color': '#3f789e', 'flags': {}}, {'id': 5, 'title': 'Image Size', 'bounding': [4130, 1540, 530, 420], 'color': '#3f789e', 'flags': {}}, {'id': 9, 'title': 'Preset', 'bounding': [4700, 1540, 1820, 780], 'color': '#3f789e', 'flags': {}}], 'links': [{'id': 8, 'origin_id': 24, 'origin_slot': 0, 'target_id': 10, 'target_slot': 0, 'type': 'CONDITIONING'}, {'id': 33, 'origin_id': 31, 'origin_slot': 1, 'target_id': 11, 'target_slot': 0, 'type': 'INT'}, {'id': 36, 'origin_id': 32, 'origin_slot': 1, 'target_id': 11, 'target_slot': 1, 'type': 'INT'}, {'id': 11, 'origin_id': 18, 'origin_slot': 0, 'target_id': 12, 'target_slot': 0, 'type': 'NOISE'}, {'id': 13, 'origin_id': 16, 'origin_slot': 0, 'target_id': 12, 'target_slot': 2, 'type': 'SAMPLER'}, {'id': 14, 'origin_id': 17, 'origin_slot': 0, 'target_id': 12, 'target_slot': 3, 'type': 'SIGMAS'}, {'id': 15, 'origin_id': 11, 'origin_slot': 0, 'target_id': 12, 'target_slot': 4, 'type': 'LATENT'}, {'id': 16, 'origin_id': 12, 'origin_slot': 0, 'target_id': 13, 'target_slot': 0, 'type': 'LATENT'}, {'id': 17, 'origin_id': 9, 'origin_slot': 0, 'target_id': 13, 'target_slot': 1, 'type': 'VAE'}, {'id': 34, 'origin_id': 31, 'origin_slot': 1, 'target_id': 17, 'target_slot': 1, 'type': 'INT'}, {'id': 37, 'origin_id': 32, 'origin_slot': 1, 'target_id': 17, 'target_slot': 2, 'type': 'INT'}, {'id': 24, 'origin_id': 14, 'origin_slot': 0, 'target_id': 24, 'target_slot': 0, 'type': 'CLIP'}, {'id': 32, 'origin_id': 27, 'origin_slot': 0, 'target_id': 31, 'target_slot': 0, 'type': 'INT'}, {'id': 35, 'origin_id': 28, 'origin_slot': 0, 'target_id': 32, 'target_slot': 0, 'type': 'INT'}, {'id': 25, 'origin_id': 13, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'IMAGE'}, {'id': 152, 'origin_id': -10, 'origin_slot': 0, 'target_id': 24, 'target_slot': 1, 'type': 'STRING'}, {'id': 153, 'origin_id': -10, 'origin_slot': 1, 'target_id': 27, 'target_slot': 0, 'type': 'INT'}, {'id': 154, 'origin_id': -10, 'origin_slot': 2, 'target_id': 28, 'target_slot': 0, 'type': 'INT'}, {'id': 155, 'origin_id': -10, 'origin_slot': 3, 'target_id': 18, 'target_slot': 0, 'type': 'INT'}, {'id': 156, 'origin_id': -10, 'origin_slot': 4, 'target_id': 23, 'target_slot': 0, 'type': 'COMBO'}, {'id': 157, 'origin_id': -10, 'origin_slot': 5, 'target_id': 14, 'target_slot': 0, 'type': 'COMBO'}, {'id': 158, 'origin_id': -10, 'origin_slot': 6, 'target_id': 9, 'target_slot': 0, 'type': 'COMBO'}, {'id': 195, 'origin_id': 145, 'origin_slot': 0, 'target_id': 144, 'target_slot': 0, 'type': 'STRING'}, {'id': 196, 'origin_id': 148, 'origin_slot': 0, 'target_id': 145, 'target_slot': 0, 'type': 'STRING'}, {'id': 197, 'origin_id': 150, 'origin_slot': 0, 'target_id': 146, 'target_slot': 0, 'type': 'STRING'}, {'id': 199, 'origin_id': 147, 'origin_slot': 0, 'target_id': 148, 'target_slot': 0, 'type': 'STRING'}, {'id': 200, 'origin_id': 148, 'origin_slot': 0, 'target_id': 149, 'target_slot': 0, 'type': 'STRING'}, {'id': 201, 'origin_id': 148, 'origin_slot': 0, 'target_id': 150, 'target_slot': 0, 'type': 'STRING'}, {'id': 202, 'origin_id': 149, 'origin_slot': 0, 'target_id': 151, 'target_slot': 0, 'type': 'STRING'}, {'id': 207, 'origin_id': 151, 'origin_slot': 1, 'target_id': 17, 'target_slot': 0, 'type': 'INT'}, {'id': 208, 'origin_id': 144, 'origin_slot': 0, 'target_id': 17, 'target_slot': 3, 'type': 'FLOAT'}, {'id': 209, 'origin_id': 146, 'origin_slot': 0, 'target_id': 17, 'target_slot': 4, 'type': 'FLOAT'}, {'id': 211, 'origin_id': 154, 'origin_slot': 0, 'target_id': 155, 'target_slot': 2, 'type': 'MODEL'}, {'id': 213, 'origin_id': 24, 'origin_slot': 0, 'target_id': 155, 'target_slot': 1, 'type': 'CONDITIONING'}, {'id': 214, 'origin_id': 10, 'origin_slot': 0, 'target_id': 155, 'target_slot': 3, 'type': 'CONDITIONING'}, {'id': 215, 'origin_id': 155, 'origin_slot': 0, 'target_id': 12, 'target_slot': 1, 'type': 'GUIDER'}, {'id': 216, 'origin_id': -10, 'origin_slot': 7, 'target_id': 154, 'target_slot': 0, 'type': 'COMBO'}, {'id': 218, 'origin_id': 156, 'origin_slot': 0, 'target_id': 147, 'target_slot': 0, 'type': 'STRING'}, {'id': 219, 'origin_id': -10, 'origin_slot': 8, 'target_id': 156, 'target_slot': 0, 'type': 'COMBO'}, {'id': 222, 'origin_id': 23, 'origin_slot': 0, 'target_id': 157, 'target_slot': 0, 'type': 'MODEL'}, {'id': 223, 'origin_id': 157, 'origin_slot': 0, 'target_id': 155, 'target_slot': 0, 'type': 'MODEL'}], 'extra': {}}, {'id': 'f5f04613-ee09-4cd9-9ada-a880360891d4', 'version': 1, 'state': {'lastGroupId': 9, 'lastNodeId': 176, 'lastLinkId': 252, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': 'Ideogram4 Caption Prompt Template', 'inputNode': {'id': -10, 'bounding': [4830, 2840, 128, 108]}, 'outputNode': {'id': -20, 'bounding': [6270, 2700, 128, 68]}, 'inputs': [{'id': 'b96a4263-d942-4b93-9225-03d8aff697ed', 'name': 'value', 'type': 'STRING', 'linkIds': [180], 'label': 'user_prompt', 'pos': [4934, 2864]}, {'id': '1292f2e8-bc8b-4896-956a-77cbfe7f7482', 'name': 'source', 'type': '*', 'linkIds': [234], 'label': 'width', 'pos': [4934, 2884]}, {'id': '52396a95-c41b-4e06-94be-b6000d977bec', 'name': 'source_1', 'type': '*', 'linkIds': [236], 'label': 'height', 'pos': [4934, 2904]}], 'outputs': [{'id': '6527ba64-e7bb-474f-b015-bd6931e990ca', 'name': 'STRING', 'type': 'STRING', 'linkIds': [247], 'pos': [6294, 2724]}], 'widgets': [], 'nodes': [{'id': 114, 'type': 'PrimitiveStringMultiline', 'pos': [5070, 2580], 'size': [430, 520], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [228]}], 'title': 'System Prompt', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveStringMultiline'}, 'widgets_values': ['[META]\nfrozen: false\ndescription: Slim single-shot magic prompt — splatter planning + v15 output discipline, deduped for faster inference. Thinking off.\nthinking_mode: disabled\n\n[SYSTEM]\nYou convert a natural-language user idea into a structured JSON caption an image renderer can consume. You receive the user idea plus a target aspect ratio, and you emit one JSON object.\n\n## OUTPUT CONTRACT — exactly three top-level keys, in this order:\n\n```json\n{"aspect_ratio":"W:H","high_level_description":"...","compositional_deconstruction":{"background":"...","elements":[ ... ]}}\n```\n\n- Emit a SINGLE-LINE MINIFIED JSON object — no markdown fences, no commentary, no other top-level keys.\n- Preserve non-ASCII characters as-is (CJK, Cyrillic, Devanagari, Arabic, accented Latin). Never escape with `\\uNNNN`, transliterate, or replace `café` with `cafe`.\n- Use SINGLE quotes for embedded text references in prose fields (`\'Joe\'s Diner\'`, not `\\"Joe\'s Diner\\"`). The `text` field of text elements is the exception — that field holds the user\'s verbatim characters, may use any characters, and follows QUOTED SPAN FIDELITY below.\n\n### `aspect_ratio` (first field, always required)\n\nA string in `W:H` form with positive integers (`1:1`, `16:9`, `9:16`, `4:5`, `3:1`, `2:3`, etc.).\n- If the user message gives a concrete `W:H`, echo it verbatim.\n- If the user message says `auto`, pick a concrete ratio that matches the medium and composition (panoramic subjects → wide ratios like `16:9` or `3:1`; portrait subjects → tall like `9:16` or `4:5`; designed artifacts → format conventions like `2:3` book cover, `3:4` poster; ambiguous → `1:1`). NEVER emit the literal string `auto`.\n- The aspect ratio you commit to drives every bbox decision. Pick it first.\n\n### `high_level_description` — observational summary (50-word hard cap)\n\n- ONE long sentence preferred, never more than two.\n- Reads like a short natural-language prompt, not an analysis. Starts immediately with the subject — no "this image shows", "depicts", "captures".\n- Identifies subject(s), medium, and overall composition. Names recognized pop-culture entities by full name (`Nike Air Jordan 1`, `Eiffel Tower`, `Mario (Nintendo character)`).\n- Don\'t enumerate granular features (every color, every grid dimension, every typography choice). That detail belongs in element descs or `background`.\n- `various`, `multiple`, general categories ARE appropriate here. Specificity rule (below) applies to element descs and `background`, NOT this field.\n- For transparent backgrounds, include the literal phrase `on a transparent background`.\n\nGOOD: `A full-action shot of a male soccer player in a red kit and black Adidas cleats kicking a soccer ball on a green turf field, with a blurred crowd in the stadium background.`\nBAD (over-specifies): `A male soccer player captured mid-kick on a bright green grass pitch, right leg fully extended through the follow-through at the precise moment his black-and-white studded boot makes contact with a white-and-black size-5 ball...`\n\n## ELEMENTS — what they are, what they\'re not\n\nEach element is one of:\n```\n{"type":"obj","bbox":[y1,x1,y2,x2],"desc":"..."}\n{"type":"text","bbox":[y1,x1,y2,x2],"text":"LINE ONE\\nLINE TWO","desc":"..."}\n```\n\n`bbox` is optional per-element (see BBOX section below).\n\n### SINGLE SUBJECT = SINGLE ELEMENT\n\nA coherent subject — one animal, person, vehicle, building, plant, instrument, machine — is exactly ONE `obj` element. Anatomical and structural parts are descriptive attributes inside that element\'s `desc`, NOT separate elements.\n\nFORBIDDEN: a bee split into 8 elements (thorax/abdomen/wings/eyes/legs/...); a car split into 6 (body/wheels/windshield/...); a person split into 7 (head/torso/each limb/...); a building split into 5 (foundation/walls/windows/roof/door); a flower split into 3 (petals/stem/leaves).\n\nWhen MULTIPLE distinct subjects appear (a person AND a dog; two bees; three runners), use MULTIPLE elements — one per subject.\n\n**Test:** part-of-one-thing → goes in that thing\'s desc. Separate thing → its own element.\n\n**Transparent enclosure + featured contents = ONE element.** Display cases, snow globes, terrariums, aquariums, specimen jars, bell jars, vitrines containing a featured subject: name the enclosure + contents as a single unified desc.\n\n**Configured parts + revealed interior = ONE element.** A car with an open door, a machine with raised hood, a building with drawn curtains: the open state and any revealed interior are attributes of the single subject\'s desc, not separate elements.\n\n### Element desc — what to write (30–60 words, 60-word HARD CAP)\n\nIdentity first, then major attributes briefly, then one distinguishing detail if relevant. Each desc is a standalone catalog entry — open with the subject\'s identity, not a referring phrase like "the X" that assumes the reader has seen the scene.\n\nGOOD (introduces from scratch):\n- `Woman walking on the platform, medium size. Shoulder-length dark wavy hair, medium skin tone, light blue button-down shirt and grey trousers. Small bag slung over the right shoulder.`\n- `Circular concrete tunnel entrance with glowing blue ring lights along the interior. Train tracks lead directly into the dark opening.`\n\n**Major attributes — always name:**\n- People: skin tone, hair (color + style), each visible garment with color, expression/gaze, pose, distinguishing feature (mole, glasses, jewelry, held prop).\n- Objects: shape, material, color, distinctive parts (handle, label, logo, marking).\n- Scenes/structures: type, primary material, color, distinctive structural elements.\n\n**Skip (eat word budget for marginal benefit):**\n- Surface-finish micro-prose (`finely granular matte texture with subtle sheen along the elytral ridges`). Pick one short descriptor (matte/glossy/metallic/textured) or omit.\n- Pose mechanics per-limb. Pick ONE summary action phrase plus the major attributes.\n- Camera/shadow/lighting micro-detail per element. Belongs in `background`.\n- Fabric weave, skin texture nuances, micro-anatomy.\n\n### Element desc — what NOT to include\n\n**No shadows.** Cast shadows, drop shadows, ground shadows, contact shadows, ambient occlusion — describe in `background` only when scene-wide, otherwise omit (the renderer infers them). Forbidden: `casts a thin hard shadow to the lower right`, `with a soft drop shadow beneath`.\n\n**No camera or render language.** Depth of field, focus, sharpness, bokeh, exposure, motion blur, lens flare, chromatic aberration, film grain — render properties belong in `high_level_description` or `background` as natural prose ONLY when the user prompt explicitly named them. NEVER inside an obj desc.\n  - EXCEPTION — viewpoint/angle (`from a low-angle perspective`, `bird\'s-eye view`, `eye-level`) IS allowed in obj descs when the prompt calls for it. Place once, usually in the focal subject\'s desc or background.\n\n**No describing impressions instead of physical reality.** Avoid `luminous`, `radiant`, `vibrant`, `lush`, `dynamic`, `glowing` (metaphorically), `gorgeous`, `stunning`, `breathtaking`, `mesmerizing`. Use observable properties: `cheekbone catches a small highlight`, not `luminous complexion`.\n\n**No scene-context repetition per-element.** Lighting direction, ambient surface, mounting context, weather → describe ONCE in `background`. Each element\'s desc focuses on what\'s UNIQUE to that element.\n\n### Anchor placements to named references\n\nSpecify body parts, surfaces, spatial landmarks.\n- CORRECT: `applied to the forehead near the hairline above the left eyebrow`.\n- INCORRECT: `pressed against the skin`.\n- CORRECT: `resting on the lower-right corner of the table directly in front of the laptop`.\n- INCORRECT: `sitting on the surface`.\n\n## BACKGROUND — what goes here, what doesn\'t (CRITICAL)\n\n`background` describes the scene SHELL: walls and finishes, floor/ground and surface state, ceiling and architectural fixtures, windows as architecture, atmospheric context (sky, clouds, fog, dust, mist), scene-wide ambient lighting, distant out-of-focus context (horizon, blurred crowds, distant scenery).\n\n### No double-counting\n\nAnything described in `background` CANNOT also appear as an obj element. Each scene component lives in EXACTLY ONE field. Decide once and commit. Before emitting an obj element, scan `background` — if the component is named there, omit the obj element.\n\n### ALWAYS-BACKGROUND — these live in `background` only, never as obj elements:\n\n- sky, clouds, atmospheric color\n- horizon\n- distant mountains, hills, tree lines\n- atmospheric weather (fog, haze, mist, smoke)\n- distant cityscape or stadium architecture\n- distant blurred or simplified crowds\n- the floor / ground / turf / paving surface the scene sits on\n- ambient walls or studio backdrop behind focal subjects\n\nYou cannot split these by region. `sky upper-left portion`, `sky behind the fortress`, `sky upper two-thirds` are the SAME component — describe in `background` once. Same for crowd, ground, horizon.\n\nIf you want technique-level detail on an atmospheric component (watercolor wet-on-wet sky blooms, fog with directional density variation), put that detail in `background`. The `background` field is allowed to be long.\n\n### Ground/floor/pavement is ALWAYS background — zero tolerance\n\nThe surface the scene sits on — floor, ground, turf, grass, dirt, sand, asphalt, pavement, road, sidewalk, deck, water surface, snow, tile floor, hardwood, marble — lives in `background` only. This holds REGARDLESS of how the input formats it: if the prompt lists `Wet rain-slicked pavement below` as a foreground bullet, RE-CLASSIFY it into background.\n\n**Surface character that belongs in background, not as a separate obj:** wet / rain-slicked / mud-streaked / dusty / cracked / polished / weathered surface state; reflective neon pools, fragmented color reflections, puddles, wet patches, mud patches, ice patches, frost, snow on the floor, water pooled on the ground, oil slicks, footprints, tire tracks; surface material (asphalt, cobblestone, hardwood, tile, marble, packed dirt); texture words for the floor (glassy, mirror-like, matte, polished, rough).\n\n**Puddles, reflections, wet patches are part of the ground surface** — never separate obj elements, regardless of whether they reflect the hero\'s silhouette or carry visible content.\n\n**Failure mode this prevents:** when a standing hero is the focal element and the floor is also emitted as an obj at the bottom of the frame, the renderer treats the floor obj as a 2D frame band rather than a perspectival receding plane, and clips the hero\'s legs into it — figure rendered half-in-the-ground with feet/calves buried.\n\n**Discrete objects ON the floor are still elements:** broken glass shards, crushed cans, scattered debris, leaves, rocks, dropped tools, brick fragments, foreground litter remain obj elements. The rule applies to the SURFACE itself and any state of that surface (wet, frozen, muddy, puddled), never to solid objects resting on it.\n\n### Background is the shell only — no individually-placeable things\n\nFurniture, vehicles, equipment, people, animals, decor (artwork, signs, plants in pots, stacks of books), free-standing lamps → obj elements, never `background`.\n\n### Shell-affixed prominent objects → DUAL MENTION\n\nSome objects are simultaneously part of the shell AND focal elements that define the room\'s identity: a chalkboard covering the back wall of a classroom, a fireplace built into a living-room wall, a large mounted TV, a stage proscenium, a built-in altar, a built-in bookshelf, a large fixed reception desk, a fixed sign/banner.\n\nFor these, MANDATORY all three steps:\n1. **MENTION in `background`** as part of the shell — anchors the object to the wall.\n2. **EMIT as an obj element** with the qualifier `"the primary background element"` (or similar) at the start of its desc. The obj carries the detail (material, content, frame, mounting).\n3. **PLACE FIRST in the elements list** so painter\'s-algorithm draws it behind foreground items.\n\nSkipping step 1 (the most common failure) makes the renderer float the object in mid-room or render it in front of foreground subjects.\n\nThis is an EXCEPTION to the shell rule\'s "no individually placeable things". Applies ONLY to objects that genuinely define the room\'s architectural identity. Free-standing items (chairs, table lamps, plants in pots, framed pictures on a wall) get the normal treatment: elements only, no background mention.\n\n### Recession/arrangement is not architecture\n\nDo not smuggle furniture or people into `background` by describing them as a receding arrangement. Forbidden background phrasings: `rows of desks recede toward the back`, `a grid of desks fills the room`, `students seated at the desks`, `chairs arranged in front of the podium`, `the room is filled with people`, `cars parked along the street`, `customers seated at the tables`. The arrangement IS the foreground content — emit elements.\n\n### No medium/post-processing effects in background\n\n`background` describes WHAT is in the scene, not HOW it was made. Forbidden in `background` — even when the prompt names the effect (route those to HLD instead):\n- Film grain, Kodak/Portra/Tri-X grain, ISO noise\n- Lens flare, chromatic aberration, vignetting, bokeh quality\n- Color cast / film-stock shift (warm shift, cool shift)\n- Paper texture, paper grain, canvas texture\n- Brushstroke texture, palette-knife texture\n- Halftone dots, screen-print texture, risograph texture\n\n**Test:** read `background` aloud. If you can picture the EMPTY room from the description — no furniture, no people, no equipment, no wall decor — you\'re in the shell. If anything disappears when you remove the room\'s contents, the background has leaked.\n\n## BBOX STRATEGY\n\nINCLUDE bboxes on elements where precise positioning matters — portrait subjects, products on a surface, logos, signs on a wall, distinct individually-placeable objects.\n\nOMIT bboxes on elements that represent dense or hard-to-enumerate visuals — crowds, fields of wildflowers, scattered particles, starry skies. Per-element judgment.\n\n### Coordinate system\n\nCoordinates are normalized to the target image shape: `x` runs left→right along full width (0 = left edge, 1000 = right), `y` runs top→bottom along full height (0 = top, 1000 = bottom). Top-left origin. Format `[y1, x1, y2, x2]` with `y1 < y2`, `x1 < x2`.\n\n### Shape warning (common failure)\n\nBbox values are normalized to 0–1000 in BOTH axes. A square `[0, 0, 500, 500]` is square only on a square frame; on 16:9 it becomes a wide rectangle, on 9:16 a tall rectangle. Most bbox failures (extra subjects, duplicates, mis-scaled objects) come from this mismatch.\n\nFor round objects or square on-screen regions, scale spans so `(x2-x1)/(y2-y1) ≈ W/H`. For single-subject prompts on wide frames, prefer narrower x-spans. For multi-subject prompts, give each a tight bbox so no one bbox dominates and invites a duplicate.\n\n## SPECIFICITY — commit to one value\n\nThis JSON feeds a diffusion model. Leave nothing for the model to invent or choose.\n\n**Banned hedge phrasings** (in elements and background): `things like`, `such as`, `e.g.`, `for example`, `or similar`, `various`, `could include`, `might be`, `some kind of`, `style of`. Replace with concrete nouns, counts, colors, materials, poses.\n\n**Banned alternative listings for one property:** `pale institutional off-white or pale green`, `oak or walnut`, `cream or ivory`, `late afternoon or early evening`, `italic serif or italic sans-serif`, `bold or semibold`. Pick ONE and commit. `or` is reserved for the loader\'s exclusive-choice idiom (`\'YES\' or \'NO\'`), not captioner hedging.\n\n**Typography specifically:** name ONE typeface category (serif OR sans-serif OR display OR script OR monospace), ONE weight (bold/regular/light/medium), ONE style (italic OR upright). Never two joined by `or`.\n\n**Banned "implied/suggested" hedges:** `a desk corner implied`, `a chair suggested beneath the figure`, `a building hinted at`, `a shadow that reads as a person`. If it\'s in the scene, paint it concretely. If it isn\'t, leave it out. Forbidden words: `implied, suggested, hinted, barely visible, possibly, perhaps, maybe, might be, could be, reads as, almost`.\n\n**Exhaustive content preservation.** When the user provides enumerable content — schedules, itineraries, lists, menu items, steps, names, times — every item must appear in the output. Use as many text elements as needed; never sacrifice completeness for layout.\n\n**Named prompt elements MUST appear.** Every explicitly-named visual unit in the user prompt MUST appear as its own element:\n- Input `text:` sections — every entry becomes its own text element, verbatim. Zero tolerance: 3 entries in input → ≥3 text elements in output. Empty `text: []` is the only case where text elements may be omitted on that basis.\n- Quoted strings (single or double quotes) — each is its own text element.\n- Speech bubbles / dialogue callouts / thought bubbles / captions — each gets a text element for the quoted string AND an obj element for the bubble/balloon/container.\n- Named decorative elements (`small medical cross icon top-left`, `airplane arc trajectory`, `flame-lick flourish at the tail`) — each gets its own obj.\n- Named badges / chips / CTAs / strips — each gets its own obj (and text if it carries a quoted string).\n- Named accents / graphic devices (`hairline rule`, `dot grid`, `accent line`, `divider`) — each gets its own obj UNLESS it\'s a scene-wide overlay belonging in `background`.\n\n**Test before emitting:** count named visual units in the user prompt; element list must contain at least that many.\n\n**No placeholder enumeration.** When the imagined image contains a sequentially-numbered, alphabetically-labeled, or otherwise individually-identified set (stones numbered 1–50, parking spaces A1–A20, place cards `1st`–`12th`, a periodic table of 118 elements, a calendar grid of 31 dates, a 22-name team roster), EACH item is its own element. No `etc.`, no `and so on`, no `6 through 49`, no single obj grouping all into one cluster. List ALL of them.\n\nThe "dense unenumerable group" exception (crowd of thousands, field of wildflowers, starry sky) does NOT apply to enumerable sets — if items are sequentially identified, they\'re enumerable BY DEFINITION.\n\n**Don\'t invent visual concepts the user didn\'t ask for.** Forbidden without explicit user request: `glitch art`, `wireframe overlay`, `mesh that fragments the body`, `digital artifacts`, `dissolved`, `decompose`. If the prompt asks for a cinematic photo of a journalist, render a cinematic photo of a journalist — not a glitch-art composite.\n\n## PLANNING — turn the user idea into elements\n\n### 1. Pick a medium\n\n`photograph | illustration | 3D render | graphic design` — applies as natural-language framing inside HLD/background, NOT as a structured slot.\n\nDecision: **DESIGNED artifact vs CAPTURED / DRAWN / RENDERED moment.**\n- **graphic design** — poster, book cover, album cover, magazine cover, flyer, banner, social post, sticker, logo, wordmark, packaging, app icon, UI mockup, infographic, menu, greeting card, ticket, signage. If a human designer would sit at a desk to make it.\n- **photograph** — portrait, landscape, lifestyle, street, sport, wildlife, food, product, fashion editorial (when described as a photograph). Default for ambiguous everyday scenes.\n- **illustration** — cartoon, anime, manga, comic, watercolor, oil painting, ink, vector, pixel art, children\'s book illustration, named studios (Ghibli, KyoAni, Pixar 2D).\n- **3D render** — CGI, octane/unreal/blender, hyperrealistic product render, arch viz, isometric low-poly, voxel, named 3D studios.\n\nSilent / ambiguous → photograph (default). The subject\'s reality status does NOT override this default — wizards, dragons, aliens, robots in a photograph are valid; the brief must explicitly ASK for illustration / painting / render to get one.\n\nImperative verbs at the start ("Illustrate a…", "Paint a…", "Draw a…", "Render a…") are NOT medium signals — they mean "depict / show". Default to photograph unless an explicit medium-noun or style name appears.\n\n### 2. Style commitment\n\nInside HLD/background prose, name the style ONCE (`Studio Ghibli animation`, `Pixar 3D animation`, `35mm film photograph`, `iPhone photo`, `editorial digital painting`, `flat vector illustration`). Keep it short — recognizable style names are enough; the renderer knows them. Don\'t append technique detail (`with hand-painted gouache backgrounds`) on top of well-known names.\n\n**"Professional picture/photo/portrait" of a person means PROFESSIONAL CONTEXT, not professional camera equipment.** Read as corporate headshot, LinkedIn profile, business bio — neutral business attire, soft even daylight, neutral backdrop, friendly approachable expression. NOT dramatic studio rim-lighting, creamy DSLR bokeh, dark moody backdrop.\n\n### 3. Photoreal defaults — AVOID "warm"\n\nFor photographic prompts (no specified medium beyond `photo`/`photorealistic`/`selfie`/real-world scene):\n- Default to iPhone aesthetic — phone snapshot, ambient natural light, neutral white balance, accurate (not flattering) skin tones, ordinary framing. AVOID DSLR-magazine markers (creamy bokeh, telephoto compression, dramatic rim lighting, cinematic grade) — those signal AI-generation.\n- Default lighting framing: `natural daylight`, `overcast daylight`, `diffused daylight`, `cool-neutral white balance`. The word **"warm"** (in any phrase: `warm light`, `warm window light`, `warm tone`, `warm grading`) is BANNED as a grading adjective — it triggers the amber/golden AI look that ruins photorealism. When a scene physically has a warm-coloured light source (candle, sodium streetlamp, sunset), describe the SOURCE concretely (`candle flame`, `sodium streetlamp`) and the colour of the LIGHT POOL (`amber pool from the candle`) — but the global grade stays neutral.\n- Default composition: prefer non-centered framing (off-center, rule-of-thirds, asymmetrical, leading lines) for portraits, products, single-subject scenes. Use centered framing ONLY when the prompt explicitly calls for it (`centered`, `symmetrical`, `mandala`, `kaleidoscope`) or when the genre is inherently symmetric.\n- No motion blur in candid/realistic/iPhone-aesthetic photos. Motion blur is a craft signature (long-exposure pans, light streaks); using it in a candid signals AI. Real phone snapshots freeze the moment.\n- Saturation: don\'t stack `vibrant + bright + intense + saturated + electric + neon` for a neutral subject. Mention saturation ONCE (in HLD or background) only when the prompt explicitly asks.\n\n### 4. Populate underspecified scenes\n\nWhen the brief is sparse, don\'t render only what\'s explicitly named. Real scenes are populated. Add believable secondary subjects, micro-props that imply the subject\'s life, environmental texture, small narrative moments. Each invented element should belong in the world the brief implies — a paddy-field food stall plausibly has a chicken, a sauce bowl, a hand-painted price sign, a lantern.\n\n**Populate by depth layer.** Foreground (often-skipped), midground, background — each gets its own content. A foreground crop (an out-of-focus leaf at the bottom corner, the rim of a bowl, a fly mid-air close to camera) separates a real photograph from a postcard.\n\n**Commit to a specific cultural / regional identity.** "Southeast Asian village" is a hedge that produces generic AI visuals. "Vietnamese pho stall by the rice paddies outside Hoi An" is a real place. Specific commitment shapes architecture, signage script, food, dress, props.\n\n**Built environments need text everywhere.** Real shops, stalls, restaurants, vehicles, signage carry text on practically every surface. Generate text generously: shop name sign, sub-signs (`OPEN` / `TODAY\'S SPECIAL`), menu board with handwritten items, price labels, jar/bottle labels, name tags, posters, fortune slips, vehicle/equipment labels, sponsor logos. `text: []` is almost always wrong for built environments — if your scene has a shop/stall/restaurant/workshop/market/vehicle, populate text. Specific content, never `various labels` or `menu items`.\n\n**Override:** when the brief explicitly says `minimal`, `sparse`, `empty`, `lonely`, `isolated`, `quiet`, `still`, `negative space`, `alone`, `single subject`, `in the middle of nowhere`, respect the restraint and skip populate.\n\n**Fantastical / sci-fi / fantasy / futuristic briefs get a populate bonus.** Stack sky drama (galaxies, ringed planets, multiple moons, nebulae), opposing focal points (volcano right / waterfall left), mid-distance scale anchors (crystal columns, futuristic cityscape, megastructures), light/energy effects throughout, exotic architecture/geology, deeply saturated palettes.\n\n## TEXT HANDLING\n\nFor each text element:\n- `text` — literal characters appearing in the image, verbatim. Preserve diacritics, capitalization, punctuation. Never transliterate or strip.\n- `bbox` — optional, same coordinate system as obj elements.\n- `desc` — free-form prose covering size, location, font style, color, orientation, visual effects.\n\n**Sources of text to include:**\n1. **User-quoted text** (single OR double quotes) — verbatim, exact characters.\n2. **Format-required text** — headlines, taglines, author names, dates, venues, CTA copy, brand names, publisher marks, edition numbers (when format implies them).\n3. **In-scene contextual text** — signage, labels, license plates, badges, jersey numbers, t-shirt prints, awnings, neon signs, name tags.\n4. **Numeric content** — race numbers, jersey numbers, dates, prices, scores, time displays, address numbers. Numbers ARE text.\n5. **Prominent product brand text** — if an element names a prominent product (bottle, cosmetic, package, beverage) and the user didn\'t supply a real brand, invent a complete brand identity and list every label as text elements.\n\n**Rules:**\n- Exhaustive: if a viewer could read it, it goes in the list.\n- Each text element appears ONCE in the list. Do NOT also describe its characters in `description` — refer by role/position instead.\n- Use `\\n` for line breaks WITHIN a single text element (multi-line sign, stacked headline). Use SEPARATE list items for visually distinct text blocks.\n- For stylized hero typography where each letter is a distinct visual unit, stack with `\\n` at natural word breaks — long single-line stylized titles produce typos and dropped letters. e.g., `"ENTRE\\nVERSOS E\\nCONTOS"` not `"ENTRE VERSOS E CONTOS"`.\n- **Language scoping:** `scene`/`elements`/`description`/position descriptors are always in ENGLISH regardless of the user\'s brief language. Only the literal `text` field characters follow the user\'s brief language. Portuguese brief → English prose + Portuguese `text:` content.\n\n## POP CULTURE, BRANDS, NAMED REFERENCES\n\nWhen the user idea names or clearly implies a brand, trademark, product (sneaker/car/device), public figure, athlete, musician, actor, fictional character, film, show, game, franchise, team — the output MUST carry an explicit named reference in the relevant element `desc`, not a generic stand-in describing the look.\n\nDon\'t replace `Nike Dunk Low Panda` with `black and white retro sneakers`, `Spider-Man` with `a red-and-blue masked superhero`, `The Beatles` with `four men in matching suits` — unless the user asked for an anonymous lookalike. Name the specific thing the user pointed at.\n\n## TRANSPARENT BACKGROUND\n\nIf the user\'s idea calls for transparent background, transparent canvas, alpha channel, cutout/isolated subject, sticker-style with no backdrop, or similar, the `background` field MUST be exactly this string, verbatim and nothing else: `transparent background`\n\nDo not paraphrase (no `clear backdrop`, `empty alpha`, `no background`, `PNG transparency`).\n\nIn `high_level_description`, include the literal phrase `on a transparent background`.\n\n[USER]\nTARGET IMAGE ASPECT RATIO: {{width}}:{{height}} (width:height).\nUser idea: {{original_prompt}}']}, {'id': 115, 'type': 'PrimitiveStringMultiline', 'pos': [5070, 3150], 'size': [400, 200], 'flags': {}, 'order': 1, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'STRING', 'widget': {'name': 'value'}, 'link': 180}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [238]}], 'title': 'User Prompt', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveStringMultiline'}, 'widgets_values': ["A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling 'COMFY'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying "]}, {'id': 163, 'type': 'StringReplace', 'pos': [5580, 2540], 'size': [400, 280], 'flags': {}, 'order': 2, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 228}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 238}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [239]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{original_prompt}}', '']}, {'id': 164, 'type': 'PreviewAny', 'pos': [5420, 3420], 'size': [230, 180], 'flags': {}, 'order': 3, 'mode': 0, 'inputs': [{'localized_name': 'source', 'name': 'source', 'type': '*', 'link': 235}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [240]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'PreviewAny'}, 'widgets_values': [None, None, None]}, {'id': 165, 'type': 'PreviewAny', 'pos': [5400, 3680], 'size': [230, 180], 'flags': {}, 'order': 4, 'mode': 0, 'inputs': [{'localized_name': 'source', 'name': 'source', 'type': '*', 'link': 237}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [242]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'PreviewAny'}, 'widgets_values': [None, None, None]}, {'id': 166, 'type': 'ComfyMathExpression', 'pos': [5100, 3420], 'size': [230, 190], 'flags': {'collapsed': False}, 'order': 5, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 234}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [235]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 167, 'type': 'ComfyMathExpression', 'pos': [5110, 3670], 'size': [230, 190], 'flags': {'collapsed': False}, 'order': 6, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 236}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [237]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 169, 'type': 'StringReplace', 'pos': [5710, 3250], 'size': [400, 280], 'flags': {}, 'order': 7, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 239}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 240}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [241]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{width}}', '']}, {'id': 170, 'type': 'StringReplace', 'pos': [5690, 3670], 'size': [400, 280], 'flags': {}, 'order': 8, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 241}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 242}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [247]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{height}}', '']}], 'groups': [], 'links': [{'id': 180, 'origin_id': -10, 'origin_slot': 0, 'target_id': 115, 'target_slot': 0, 'type': 'STRING'}, {'id': 228, 'origin_id': 114, 'origin_slot': 0, 'target_id': 163, 'target_slot': 0, 'type': 'STRING'}, {'id': 234, 'origin_id': -10, 'origin_slot': 1, 'target_id': 166, 'target_slot': 0, 'type': 'FLOAT,INT,BOOLEAN'}, {'id': 235, 'origin_id': 166, 'origin_slot': 1, 'target_id': 164, 'target_slot': 0, 'type': 'INT'}, {'id': 236, 'origin_id': -10, 'origin_slot': 2, 'target_id': 167, 'target_slot': 0, 'type': 'FLOAT,INT,BOOLEAN'}, {'id': 237, 'origin_id': 167, 'origin_slot': 1, 'target_id': 165, 'target_slot': 0, 'type': 'INT'}, {'id': 238, 'origin_id': 115, 'origin_slot': 0, 'target_id': 163, 'target_slot': 1, 'type': 'STRING'}, {'id': 239, 'origin_id': 163, 'origin_slot': 0, 'target_id': 169, 'target_slot': 0, 'type': 'STRING'}, {'id': 240, 'origin_id': 164, 'origin_slot': 0, 'target_id': 169, 'target_slot': 1, 'type': 'STRING'}, {'id': 241, 'origin_id': 169, 'origin_slot': 0, 'target_id': 170, 'target_slot': 0, 'type': 'STRING'}, {'id': 242, 'origin_id': 165, 'origin_slot': 0, 'target_id': 170, 'target_slot': 1, 'type': 'STRING'}, {'id': 247, 'origin_id': 170, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'STRING'}], 'extra': {}}]},
./tests/test_porting_edit_apply.py:723:    assert semantic_aliases["control_after_generate"] == "widget_1"
./tests/test_porting_edit_apply.py:801:    assert detail["semantic_aliases"].get("control_after_generate") == "widget_1"
./tests/test_live_agentic_harness_corpus_manifest.py:54:    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
./tests/test_live_agentic_harness_corpus_manifest.py:55:    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
./tests/test_live_agentic_harness_corpus_manifest.py:64:    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
./tests/test_live_agentic_harness_corpus_manifest.py:68:        rubric = scenario["answer_rubric"]
./docs/architecture/canonical-graph-elegance-plan.md:193:Python `contracts.py:70-78` matches the *generated* file, including `candidate_transaction`. The handwritten production file drops it. The generated file is drift-guarded (`tests/test_agent_contract_codegen.py`) and listed in the ownership map as "do not hand-edit," but nothing in production imports it.
./docs/text-to-graph/mvp.md:700:   prompt. In the first canvas product, represent this as a generated
./docs/roadmap_agentic_comfyui.md:367:the `convert_ui_to_api`-gated property test as a *semantic* gate over the regenerated output, the
./docs/agent-skill/skills/reorganise-comfy-workflow/SKILL.md:8:Use this when the graph should become easier to review, share, or maintain, but the workflow semantics must stay unchanged. This is a layout-only path: it may move, resize, group, color, flag, or annotate UI furniture, but it must not edit topology, node classes, links, widget values, prompts, runtime payloads, or generated graph state.
./docs/plans/reorganise-comfy-workflow-plan.md:606:Disconnected islands are sorted by terminal path importance, then semantic minimum order, then original canvas position. Islands that contain no terminal output and only model/utility setup should attach visually to the nearest consuming island when virtual/effective edges exist; otherwise they become a separate stacked island titled from their dominant role, for example `MODEL SETUP ISLAND`, `UTILITY ISLAND`, or `DISCONNECTED ISLAND 2`. Mixed top-row/bottom-row islands keep the two-row template inside each island rather than floating unrelated model-only islands across another island's generation row.
./docs/plans/loose-work-consolidation-plan.md:24:| `epic/pristine-agent-architecture-followup/work` | 7 ahead / 0 behind; dirty `custom_nodes.lock` placeholder change | Keep and land after messaging, resolving semantic overlap deliberately |
./docs/plans/agent-edit-complete-robustness-architecture.md:397:prior state. Snapshot restoration remains the safe production strategy when
./docs/plans/deeper-badness-greenfield-swarm-2026-07-09.md:297:Build content-addressed workflow revisions with semantic diffs, rollback, and lineage. This should grow naturally out of diff-over-original rather than as a separate greenfield island.
./docs/agent-edit/regression-report-m4.md:73:| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_runtime.py tests/test_comfy_nodes_agent_edit.py -q` after T4 | 371 passed, 7 failed | Complete HotShotXL semantic validation passes; queue blocker remains separate |
./docs/agent-edit/research-plan-execute-overhaul.md:95:Those are research/context contracts. In current semantics, `PrecedentAdaptationPlan` can be neutral, can leave validation as `not_evaluated`, and can omit concrete required rewires. Treat it as evidence. The new object should be a separate typed `ExecutionPlan`.
./docs/agent-edit/executor-durability-repair-plan.md:66:- Cross-session retrieval, semantic search over past sessions, or "remember what user said yesterday across sessions" are **out of scope** for this repair. These would require a separate memory/search subsystem (e.g., vector embeddings, session indexing) that is not part of the current durable-conversation contract.
./docs/agent-edit/preview-replay-production-parity-plan.md:411:- production rehydrate with an open candidate
./docs/agent-edit/sprint-1-authority-handoff.md:376:| **Deletion checklist** | 1. Audit all production sessions for `agent_edit_protocol: "v1"`.  2. Migrate or archive historical sessions.  3. Remove the V1 protocol branch. |
./vibecomfy/comfy_nodes/agent/_frag_response_contract.py:933:    from vibecomfy.comfy_nodes.agent.edit import (ApplyEligibility, LOGGER, TurnIdentity, TurnOutcome, _BATCH_EXIT_BUDGET, _BATCH_EXIT_DONE, _BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_NOOP, _BATCH_EXIT_PURE_CLARIFY, _build_candidate_payload, _build_compatibility_response_fields, _build_precedent_semantic_check_entries, _canonical_agent_edit_route, _change_details_payload, _execution_plan_debug_fields, _execution_plan_response_fields, _execution_plan_task_satisfaction_entries, _fallback_narrative_message, _json_safe, _legacy_narrative_debug_status, _narrate_final_message, _narrative_debug_fields, _net_field_changes, _plan_validation_allows_candidate, _prepare_narrative_artifact_paths, _record_narrative_artifacts, _record_post_edit_reorganisation_advisory, _resolver_candidate_is_authoring_capability, _resolver_candidates_from_batch_turns, _response_artifacts_with_execution_plan, _response_contract_candidate_present, _route_blocks_apply, _route_change_focus_label, _sanitize_pure_clarify_response, _session_artifact_response_fields, _stage_snapshot_payloads, _strip_clarify_forbidden_response_fields, _sync_narrated_clarify_outcome, _v2_candidate_mutation_plan_fields, _validate_delta_evidence_for_apply, build_legacy_agent_edit_v1, derive_apply_eligibility, format_compact_plan_feedback, public_outcome_from_turn_outcome, success_envelope, turn_envelope)  # T-039 late import: host namespace lookup; resolved at call time
./vibecomfy/comfy_nodes/agent/_frag_response_contract.py:1178:    from vibecomfy.comfy_nodes.agent.edit import (ApplyEligibility, LOGGER, TurnIdentity, TurnOutcome, _build_candidate_payload, _build_compatibility_response_fields, _build_precedent_semantic_check_entries, _canonical_agent_edit_route, _canonical_delta_ops_envelope_payload, _execution_plan_debug_fields, _execution_plan_response_fields, _execution_plan_task_satisfaction_entries, _has_enough_grounded_facts_for_dev_narrative, _json_safe, _legacy_narrative_debug_status, _narrate_final_message, _narrative_debug_fields, _plan_validation_allows_candidate, _prepare_narrative_artifact_paths, _record_narrative_artifacts, _record_post_edit_reorganisation_advisory, _response_artifacts_with_execution_plan, _route_blocks_apply, _route_change_focus_label, _sanitize_pure_clarify_response, _session_artifact_response_fields, _stage_snapshot_payloads, _sync_narrated_clarify_outcome, _v2_candidate_mutation_plan_fields, build_legacy_agent_edit_v1, derive_apply_eligibility, format_compact_plan_feedback, public_outcome_from_turn_outcome, success_envelope, turn_envelope)  # T-039 late import: host namespace lookup; resolved at call time
./vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3975:      // production rehydrate already in flight with the reducer's existing
./vibecomfy/comfy_nodes/web/preview_picker.js:763:      // same synchronous turn. A production rehydrate that resolves while the

codex
Independent checks now confirm all 100 descriptor hashes and all 98 applicable source-workflow hashes, not just spot checks. The three revised edits also map to real exposed controls in their source graphs (seed/fixed control, Moonvalley steps, and SaveGLB prefix), so their rewritten requests are satisfiable rather than merely relabeled.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest --collect-only -q -s -p no:cacheprovider -p no:rerunfailures tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_intent_judge_schema_context.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 14627ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
tests/test_live_agentic_harness_runner_persistence.py::test_persists_per_scenario_and_incremental_run_summary
tests/test_live_agentic_harness_runner_persistence.py::test_final_summary_replaces_partial_summary
tests/test_live_agentic_harness_runner_persistence.py::test_runner_does_not_retry_outer_timeout
tests/test_live_agentic_harness_runner_persistence.py::test_runner_types_provider_capacity_without_retry
tests/test_live_agentic_harness_runner_persistence.py::test_runner_retries_only_typed_empty_zero_token_attempt
tests/test_live_agentic_harness_runner_persistence.py::test_runner_keeps_malformed_nonempty_as_product_failure
tests/test_live_agentic_harness_runner_persistence.py::test_runner_counts_persistent_provider_capacity_as_infra_blocked
tests/test_live_agentic_harness_runner_persistence.py::test_runner_does_not_classify_soft_search_429_as_infra
tests/test_live_agentic_harness_runner_persistence.py::test_runner_timeout_preserves_scenario_graph_change_expectation
tests/test_live_agentic_harness_runner_persistence.py::test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed
tests/test_live_agentic_harness_runner_persistence.py::test_retryability_is_derived_from_canonical_typed_evidence
tests/test_live_agentic_harness_runner_persistence.py::test_persisted_agentic_summary_redacts_json_quoted_secrets
tests/test_live_agentic_runner_persistence.py::test_persists_per_scenario_and_incremental_run_summary
tests/test_live_agentic_runner_persistence.py::test_final_summary_replaces_partial_summary
tests/test_live_agentic_runner_persistence.py::test_runner_does_not_retry_outer_timeout
tests/test_live_agentic_runner_persistence.py::test_runner_types_provider_capacity_without_retry
tests/test_live_agentic_runner_persistence.py::test_runner_retries_only_typed_empty_zero_token_attempt
tests/test_live_agentic_runner_persistence.py::test_runner_keeps_malformed_nonempty_as_product_failure
tests/test_live_agentic_runner_persistence.py::test_runner_counts_persistent_provider_capacity_as_infra_blocked
tests/test_live_agentic_runner_persistence.py::test_runner_does_not_classify_soft_search_429_as_infra
tests/test_live_agentic_runner_persistence.py::test_runner_timeout_preserves_scenario_graph_change_expectation
tests/test_live_agentic_runner_persistence.py::test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed
tests/test_live_agentic_runner_persistence.py::test_retryability_is_derived_from_canonical_typed_evidence
tests/test_live_agentic_runner_persistence.py::test_persisted_agentic_summary_redacts_json_quoted_secrets
tests/test_structural_harness_runner.py::test_runner_help_exposes_repo_local_options
tests/test_structural_harness_runner.py::test_main_forwards_actor_tag_defaults_and_filters
tests/test_structural_harness_runner.py::test_run_chaining_family_adapts_to_reports_dir_api_shape
tests/test_structural_harness_runner.py::test_structural_runner_rejects_live_agent_actors
tests/test_structural_harness_runner.py::test_structural_runner_rejects_live_mode
tests/test_structural_harness_runner.py::test_assessor_parse_failure_is_retried_once
tests/test_structural_harness_runner.py::test_assessor_parse_failure_retry_is_bounded
tests/test_structural_harness_runner.py::test_assessor_rubric_failure_is_not_retried
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_fake_dispatchers[fake]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_fake_dispatchers[faking]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_non_agentic_model_behavior[deterministic]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_non_agentic_model_behavior[scripted]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_non_agentic_model_behavior[None]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_blocked_real_agentic_artifacts
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_catches_unchanged_graph_and_upstream_errors
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_explicit_safe_refusal_scenarios
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected
tests/test_live_agentic_harness_guard_contract.py::test_corrected_d13_edits_cannot_pass_as_noops[video-video-inpainting-with-spline-based-cut-and-dra-485ff2]
tests/test_live_agentic_harness_guard_contract.py::test_corrected_d13_edits_cannot_pass_as_noops[video-image-to-video-conversion-with-moonvalley-d7853c]
tests/test_live_agentic_harness_guard_contract.py::test_corrected_d13_edits_cannot_pass_as_noops[multi-3d-preview-and-image-output-workflow-d93baf]
tests/test_live_agentic_harness_guard_contract.py::test_desired_edit_fails_closed_when_intent_judge_is_unavailable
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_oversized_model_request
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_forbidden_model_request_substrings
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_static_widget_edit_overridden_by_link
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_no_effective_value_change_for_claimed_target
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[3d-generates-a-3d-mesh-from]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[audio-acestep-audio-generation-workflow-2a31ec]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[image-sd3-image-generation-with-controlnet-19d221]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-generates-a-video-from-a]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-image-to-video-conversion-with-moonvalley-d7853c]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-ai-video-upscaling-with-detail-daemon-sampler-673197]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[multi-audio-to-image-mel-band-roformer-workflow-b22937]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-hunyuan-video-text-to-video-generation-265847]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating[video-video-output-workflow-f855de]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_landed_claim_still_fails_via_structured_checks
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_false_validation_success_claim_still_fails_via_gates
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[missing-change-details]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[missing-landed-count]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[zero-landed-count]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[negative-landed-count]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[string-landed-count]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[float-landed-count]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_requires_positive_landed_count[bool-landed-count]
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_expected_edit_with_positive_landed_count_passes
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_exempts_grounded_refusal_from_landed_count
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_route_not_applyable_without_landed_count
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_failure_outcome_without_landed_count
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_rejects_shared_linked_source_edit_by_default
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_allows_shared_linked_source_edit_when_declared
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_treats_skipped_queue_validation_as_warning
tests/test_live_agentic_harness_guard_contract.py::test_agentic_guard_product_fails_real_queue_validation_failure
tests/test_live_agentic_harness_corpus_manifest.py::test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios
tests/test_live_agentic_harness_corpus_manifest.py::test_d13_no_change_reconciliation_and_rubric_contract
tests/test_live_agentic_harness_corpus_manifest.py::test_runner_rejects_unmanifested_descriptor_before_execution
tests/test_live_agentic_harness_corpus_manifest.py::test_manifest_discovery_rejects_changed_or_missing_descriptor
tests/test_live_agentic_harness_corpus_manifest.py::test_manifest_discovery_rejects_duplicate_id_and_path
tests/test_live_agentic_harness_corpus_manifest.py::test_manifest_discovery_rejects_duplicate_path_with_distinct_id
tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_includes_scenario_desired_rubric
tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_includes_compiled_api_schema_context
tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input
tests/test_live_agentic_intent_judge_schema_context.py::test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope

=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
93 tests collected in 8.24s

exec
/bin/zsh -lc 'for f in tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json; do nl -ba "$f" | sed -n '"'1,28p'; done; nl -ba tests/test_live_agentic_harness_guard_contract.py | sed -n '275,445p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 36ms:
     1	{
     2	  "id": "3d-3d-shape-generation-and-export-workflow-8800a9",
     3	  "query": "Lower the shape refinement strength to 0.4 so the final mesh stays closer to the input coarse mesh.",
     4	  "workflow_path": "external_workflows/corpus/8800a945cff8d090.json",
     5	  "network": true,
     6	  "timeout": 360,
     7	  "apply": true,
     8	  "assessment": {
     9	    "expect_graph_changed": true,
    10	    "allow_safe_refusal_outcome_kinds": [
    11	      "clarify",
    12	      "requires_custom_nodes"
    13	    ]
    14	  },
    15	  "desired": {
    16	    "outcome": "The refined mesh resembles the input coarse mesh more closely, with less aggressive reshaping.",
    17	    "quality": "All existing nodes remain intact, the GLB export still works, and the preview shows the updated mesh.",
    18	    "alternatives_ok": true
    19	  },
    20	  "_tags": {
    21	    "modality": "3d",
    22	    "query_type": "edit",
    23	    "abstraction": "med",
    24	    "complexity": "med",
    25	    "manifest_complexity": 3,
    26	    "task_type": "other",
    27	    "requires_custom_nodes": true,
    28	    "techniques": [
     1	{
     2	  "id": "audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf",
     3	  "query": "Replace the MelBand RoFormer audio sampler with AudioLDM2 for audio generation, integrating it with the LTX video generation pipeline and LoRA, so that audio and video remain synchronized.",
     4	  "workflow_path": "external_workflows/corpus/c80bbf22890fc8df.json",
     5	  "network": true,
     6	  "timeout": 380,
     7	  "apply": true,
     8	  "assessment": {
     9	    "expect_graph_changed": true,
    10	    "allow_safe_refusal_outcome_kinds": [
    11	      "clarify",
    12	      "requires_custom_nodes"
    13	    ]
    14	  },
    15	  "desired": {
    16	    "outcome": "The audio generation component uses AudioLDM2 instead of MelBand RoFormer, and it is fed appropriate conditioning from the video or separate audio conditioning, producing synchronized audio latents that are decoded to MP3 alongside the video output.",
    17	    "quality": "The new AudioLDM2 stage is fully wired into the pipeline, receives the correct inputs (e.g., text conditioning or latent inputs), the video generation path is unchanged, and the workflow runs without errors."
    18	  },
    19	  "_tags": {
    20	    "modality": "audio",
    21	    "query_type": "big_adjustment",
    22	    "abstraction": "high",
    23	    "complexity": "high",
    24	    "manifest_complexity": 5,
    25	    "task_type": "image_to_video",
    26	    "requires_custom_nodes": true,
    27	    "techniques": [
    28	      "ltx",
     1	{
     2	  "id": "image-face-detection-and-cropping-workflow-949658",
     3	  "query": "Replace the YOLOv8 face detection with a different face detection model like MTCNN or RetinaFace, and update the cropping logic accordingly.",
     4	  "workflow_path": "external_workflows/corpus/949658825bc5999a.json",
     5	  "network": true,
     6	  "timeout": 260,
     7	  "apply": true,
     8	  "assessment": {
     9	    "expect_graph_changed": true,
    10	    "allow_safe_refusal_outcome_kinds": [
    11	      "clarify",
    12	      "requires_custom_nodes"
    13	    ]
    14	  },
    15	  "desired": {
    16	    "outcome": "The workflow now uses a different face detection model (e.g., MTCNN or RetinaFace) with appropriately adjusted cropping parameters to maintain correct region detection.",
    17	    "quality": "All original functionality (image loading, face detection, cropping, uncropping, preview) is preserved; the new model integrates seamlessly without dangling nodes or broken connections.",
    18	    "alternatives_ok": true
    19	  },
    20	  "_tags": {
    21	    "modality": "image",
    22	    "query_type": "big_adjustment",
    23	    "abstraction": "high",
    24	    "complexity": "high",
    25	    "manifest_complexity": 4,
    26	    "task_type": "image_to_image",
    27	    "requires_custom_nodes": true,
    28	    "techniques": [
   275	        "assessment": {
   276	            "expect_graph_changed": False,
   277	            "expected_outcome_kind": "clarify",
   278	        },
   279	    }
   280	    verdict = guard_output_dir(output_dir, scenario=scenario)
   281
   282	    assert verdict["live_agentic_success"] is False
   283	    assessment = verdict["assessment"]
   284	    assert assessment["passed"] is False
   285	    assert {issue["check"] for issue in assessment["issues"]} == {"outcome_kind"}
   286
   287
   288	def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
   289	    output_dir = tmp_path / "edit-or-refuse"
   290	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   291	    (output_dir / "response.json").write_text(
   292	        json.dumps(
   293	            {
   294	                "ok": True,
   295	                "graph_unchanged": True,
   296	                "no_candidate_reason": "no_changes",
   297	                "outcome": {"kind": "requires_custom_nodes"},
   298	                "gates": {
   299	                    "ir_validate_ok": False,
   300	                    "lower_ok": False,
   301	                    "python_load_ok": False,
   302	                    "queue_validate_ok": False,
   303	                    "state_match_ok": True,
   304	                    "ui_emit_ok": False,
   305	                    "ui_fidelity_ok": False,
   306	                    "ui_load_safe_ok": False,
   307	                },
   308	                "message": "No schema-backed replacement node was found.",
   309	            }
   310	        ),
   311	        encoding="utf-8",
   312	    )
   313	    (output_dir / "implementation_result.json").write_text(
   314	        json.dumps({"message": "The graph is unchanged."}),
   315	        encoding="utf-8",
   316	    )
   317
   318	    scenario = {
   319	        "id": "edit-or-refuse",
   320	        "assessment": {
   321	            "expect_graph_changed": True,
   322	            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
   323	        },
   324	    }
   325	    verdict = guard_output_dir(output_dir, scenario=scenario)
   326
   327	    assert verdict["live_agentic_success"] is True
   328	    assessment = verdict["assessment"]
   329	    assert assessment["passed"] is True
   330	    assert assessment["expect_graph_changed"] is True
   331	    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
   332	    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}
   333
   334
   335	def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_path: Path) -> None:
   336	    output_dir = tmp_path / "edit-or-refuse-noop"
   337	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   338	    (output_dir / "response.json").write_text(
   339	        json.dumps(
   340	            {
   341	                "ok": True,
   342	                "graph_unchanged": True,
   343	                "no_candidate_reason": "no_changes",
   344	                "outcome": {"kind": "noop"},
   345	                "message": "No changes.",
   346	            }
   347	        ),
   348	        encoding="utf-8",
   349	    )
   350
   351	    scenario = {
   352	        "id": "edit-or-refuse-noop",
   353	        "assessment": {
   354	            "expect_graph_changed": True,
   355	            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
   356	        },
   357	    }
   358	    verdict = guard_output_dir(output_dir, scenario=scenario)
   359
   360	    assert verdict["live_agentic_success"] is False
   361	    checks = {issue["check"] for issue in verdict["assessment"]["issues"] if issue["severity"] == "error"}
   362	    assert "graph_changed" in checks
   363	    assert "no_candidate_reason" in checks
   364
   365
   366	@pytest.mark.parametrize("scenario_id", _CORRECTED_D13_EDIT_IDS)
   367	def test_corrected_d13_edits_cannot_pass_as_noops(
   368	    tmp_path: Path,
   369	    scenario_id: str,
   370	) -> None:
   371	    output_dir = tmp_path / scenario_id
   372	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   373	    (output_dir / "response.json").write_text(
   374	        json.dumps(
   375	            {
   376	                "ok": True,
   377	                "graph_unchanged": True,
   378	                "no_candidate_reason": "no_changes",
   379	                "outcome": {"kind": "noop"},
   380	                "message": "No changes.",
   381	            }
   382	        ),
   383	        encoding="utf-8",
   384	    )
   385	    scenario_path = (
   386	        Path(__file__).parent
   387	        / "live_agentic_harness"
   388	        / "scenarios"
   389	        / f"{scenario_id}.json"
   390	    )
   391	    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
   392
   393	    verdict = guard_output_dir(output_dir, scenario=scenario)
   394
   395	    assert verdict["live_agentic_success"] is False
   396	    checks = {
   397	        issue["check"]
   398	        for issue in verdict["assessment"]["issues"]
   399	        if issue["severity"] == "error"
   400	    }
   401	    assert "graph_changed" in checks
   402	    assert "no_candidate_reason" in checks
   403	    assert "outcome_kind" in checks
   404
   405
   406	def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
   407	    tmp_path: Path,
   408	    monkeypatch,
   409	) -> None:  # noqa: ANN001
   410	    output_dir = tmp_path / "desired-judge-unavailable"
   411	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   412	    _write_successful_candidate(output_dir)
   413	    (output_dir / "implementation_result.json").write_text(
   414	        json.dumps({"status": "success"}), encoding="utf-8"
   415	    )
   416	    monkeypatch.setattr(
   417	        "tests.live_agentic_harness.assessor.judge_edit_intent",
   418	        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
   419	    )
   420
   421	    verdict = guard_output_dir(
   422	        output_dir,
   423	        scenario={
   424	            "id": "desired-judge-unavailable",
   425	            "query": "set seed to 42",
   426	            "assessment": {"expect_graph_changed": True},
   427	            "desired": {
   428	                "outcome": "seed is 42",
   429	                "quality": "only the intended seed changes",
   430	                "alternatives_ok": False,
   431	            },
   432	        },
   433	    )
   434
   435	    assert verdict["live_agentic_success"] is False
   436	    assert any(
   437	        issue["check"] == "intent_judge" and issue["severity"] == "error"
   438	        for issue in verdict["assessment"]["issues"]
   439	    )
   440
   441
   442	def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
   443	    output_dir = tmp_path / "oversized-model-request"
   444	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   445	    (output_dir / "response.json").write_text(

codex
An adversarial edge case is checkpoint-blocking: three pre-existing `desired` edits allow a “safe refusal” outcome that bypasses the intent judge entirely. The assessor accepts the outcome label plus unchanged graph without adjudicating whether the refusal is grounded, and an existing test explicitly blesses that behavior. This violates D13’s requirement that every retained `desired` block feed an active judge. I’m completing the remaining read-only-compatible tests and line-level issue record.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider -p no:rerunfailures tests/test_live_agentic_harness_corpus_manifest.py::test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios tests/test_live_agentic_harness_corpus_manifest.py::test_d13_no_change_reconciliation_and_rubric_contract tests/test_structural_harness_runner.py::test_runner_help_exposes_repo_local_options tests/test_structural_harness_runner.py::test_structural_runner_rejects_live_agent_actors tests/test_structural_harness_runner.py::test_structural_runner_rejects_live_mode' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 5623ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
.....
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
5 passed, 1 warning in 2.58s

exec
/bin/zsh -lc "python -c '
import json
from pathlib import Path
base=Path(\"tests/live_agentic_harness/scenarios\")
rows=[]
for p in sorted(base.glob(\"*.json\")):
 s=json.loads(p.read_text()); a=s.get(\"assessment\",{})
 if s.get(\"desired\"):
  rows.append((s[\"id\"], bool(a.get(\"expect_graph_changed\")), bool(a.get(\"skip_intent_judge\")), a.get(\"allow_safe_refusal_outcome_kinds\")))
print(\"desired\",len(rows),\"expected_change\",sum(r[1] for r in rows),\"skip\",sum(r[2] for r in rows),\"safe_refusal_bypass\",sum(bool(r[3]) for r in rows))
for r in rows:
 if r[3]: print(*r)
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 587ms:
desired 42 expected_change 42 skip 0 safe_refusal_bypass 3
3d-3d-shape-generation-and-export-workflow-8800a9 True False ['clarify', 'requires_custom_nodes']
audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf True False ['clarify', 'requires_custom_nodes']
image-face-detection-and-cropping-workflow-949658 True False ['clarify', 'requires_custom_nodes']

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest --collect-only -q -s -p no:cacheprovider -p no:rerunfailures tests/test_live_agentic_harness_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py | tail -n 3' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 5321ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
71 tests collected in 2.56s

codex
D13 CHECKPOINT VERDICT: FAIL — Three retained `desired` edits can pass via an unjudged, ungrounded refusal, violating the active-judge requirement.

1. **Manifest — PASS.** Exactly 100 included entries, with 100 unique IDs and paths and complete ID/stem agreement. Independent recomputation found zero mismatches across all 100 descriptor hashes and all 98 applicable source-workflow hashes. The remaining two entries are source-less health controls. Validation is implemented in `tests/live_agentic_harness/scenario_manifest.py:134-260` and tested at `tests/test_live_agentic_harness_corpus_manifest.py:30-49`.

2. **Runner discovery — PASS.** Batch discovery delegates exclusively to `discover_manifest_scenarios()` at `tests/live_agentic_harness/runner.py:44-51`. The validator rejects missing, changed, duplicate, path-mismatched, and unmanifested descriptors at `scenario_manifest.py:143-260`. Tests cover stray files, changed/missing descriptors, duplicate IDs, and duplicate paths at `test_live_agentic_harness_corpus_manifest.py:82-140`.

3. **Three corrected edits — PASS.**

   - `485ff2`: nonexistent denoising edit replaced with real seed `534667941392889 → 42`.
   - `d7853c`: unsupported duration/FPS request replaced with real Moonvalley steps `100 → 80`.
   - `d93baf`: impossible PreviewImage camera request replaced with real SaveGLB prefix edit.

   All now set `expect_graph_changed: true`, carry precise `desired` blocks, target controls present in the source workflows, and disallow alternatives. Their no-op rejection regression is at `tests/test_live_agentic_harness_guard_contract.py:366-404`.

4. **Semantic rubrics and controls — PASS.** Independent traversal found exactly 35 semantic products, two health controls, and three corrected edits. Every semantic rubric has workflow/node evidence, scenario-specific positive criteria, explicit grounded/relevant/correct pass conditions, and hallucinated/wrong/irrelevant/vacuous/empty failure conditions. Both controls set `excluded_from_semantic_product_rates: true`. Contract assertions are at `test_live_agentic_harness_corpus_manifest.py:52-75`.

5. **Desired-block judging — FAIL.** Normal changed edits invoke `judge_edit_intent()` at `tests/live_agentic_harness/assessor.py:812-817`, and judge unavailability becomes an error for `desired` scenarios at `assessor.py:840-848`. However, three retained desired edits permit allowlisted safe refusals:

   - `scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:8-18`
   - `scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:8-17`
   - `scenarios/image-face-detection-and-cropping-workflow-949658.json:8-18`

   `assessor.py:641-646` accepts the outcome label, after which `assessor.py:812-817` skips the judge. No evidence establishes that the refusal is grounded. The existing regression at `test_live_agentic_harness_guard_contract.py:288-332` explicitly permits this path with only prose and failed edit gates.

6. **Revision accounting — PASS.** `tests/live_agentic_harness/REVISIONS.md:3-22` records three revised, 97 matched, and no replacements. Base/head comparison found exactly three query changes, zero ID or workflow-path changes, and no scenario additions/deletions. Manifest `revision_status` supports the matched-versus-revised B09 reporting required by `.oracle/tasklist.md:352-360`.

7. **Source workflows — PASS.** The symlinked corpus contains 2,827 JSON files. All 98 source-backed manifest entries resolve, source IDs match, and SHA-256 values recompute correctly; no `workflow_path` is missing.

8. **Scope and whitespace — PASS.** The range is one D13 commit containing only D13 scenarios, harness code/docs/tests, the D13 brief, and corpus-mount ignore rule. `git diff --check 0f015101..b39f0c91` exits clean. Non-blocking evidence discrepancy: the actual range is 53 files, +2967/−19, not the stated 47 files, +1210/−19.

9. **Focused tests — LIMITED BY SANDBOX.** The requested slice collects exactly 71 tests. Full execution cannot use `tmp_path` because no writable temporary directory exists in this read-only sandbox. A broader attempt produced 14 passes and 79 setup errors, all from that restriction rather than assertions. Five read-only-compatible manifest/runner tests passed independently.

### Required rework

- `tests/live_agentic_harness/assessor.py:641-646,812-817`: do not let a `desired` scenario bypass all judging merely through an allowlisted refusal label. Require an active grounded-refusal judge, failing closed when unavailable, or remove the refusal bypass for these scenarios.
- `tests/test_live_agentic_harness_guard_contract.py:288-332`: add coverage proving an unsupported or fabricated `clarify`/`requires_custom_nodes` refusal cannot pass.
- `tests/test_live_agentic_harness_corpus_manifest.py:76-79`: extend the desired-edit corpus assertion to detect judge-bypassing refusal configurations.
tokens used
205,510
D13 CHECKPOINT VERDICT: FAIL — Three retained `desired` edits can pass via an unjudged, ungrounded refusal, violating the active-judge requirement.

1. **Manifest — PASS.** Exactly 100 included entries, with 100 unique IDs and paths and complete ID/stem agreement. Independent recomputation found zero mismatches across all 100 descriptor hashes and all 98 applicable source-workflow hashes. The remaining two entries are source-less health controls. Validation is implemented in `tests/live_agentic_harness/scenario_manifest.py:134-260` and tested at `tests/test_live_agentic_harness_corpus_manifest.py:30-49`.

2. **Runner discovery — PASS.** Batch discovery delegates exclusively to `discover_manifest_scenarios()` at `tests/live_agentic_harness/runner.py:44-51`. The validator rejects missing, changed, duplicate, path-mismatched, and unmanifested descriptors at `scenario_manifest.py:143-260`. Tests cover stray files, changed/missing descriptors, duplicate IDs, and duplicate paths at `test_live_agentic_harness_corpus_manifest.py:82-140`.

3. **Three corrected edits — PASS.**

   - `485ff2`: nonexistent denoising edit replaced with real seed `534667941392889 → 42`.
   - `d7853c`: unsupported duration/FPS request replaced with real Moonvalley steps `100 → 80`.
   - `d93baf`: impossible PreviewImage camera request replaced with real SaveGLB prefix edit.

   All now set `expect_graph_changed: true`, carry precise `desired` blocks, target controls present in the source workflows, and disallow alternatives. Their no-op rejection regression is at `tests/test_live_agentic_harness_guard_contract.py:366-404`.

4. **Semantic rubrics and controls — PASS.** Independent traversal found exactly 35 semantic products, two health controls, and three corrected edits. Every semantic rubric has workflow/node evidence, scenario-specific positive criteria, explicit grounded/relevant/correct pass conditions, and hallucinated/wrong/irrelevant/vacuous/empty failure conditions. Both controls set `excluded_from_semantic_product_rates: true`. Contract assertions are at `test_live_agentic_harness_corpus_manifest.py:52-75`.

5. **Desired-block judging — FAIL.** Normal changed edits invoke `judge_edit_intent()` at `tests/live_agentic_harness/assessor.py:812-817`, and judge unavailability becomes an error for `desired` scenarios at `assessor.py:840-848`. However, three retained desired edits permit allowlisted safe refusals:

   - `scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:8-18`
   - `scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:8-17`
   - `scenarios/image-face-detection-and-cropping-workflow-949658.json:8-18`

   `assessor.py:641-646` accepts the outcome label, after which `assessor.py:812-817` skips the judge. No evidence establishes that the refusal is grounded. The existing regression at `test_live_agentic_harness_guard_contract.py:288-332` explicitly permits this path with only prose and failed edit gates.

6. **Revision accounting — PASS.** `tests/live_agentic_harness/REVISIONS.md:3-22` records three revised, 97 matched, and no replacements. Base/head comparison found exactly three query changes, zero ID or workflow-path changes, and no scenario additions/deletions. Manifest `revision_status` supports the matched-versus-revised B09 reporting required by `.oracle/tasklist.md:352-360`.

7. **Source workflows — PASS.** The symlinked corpus contains 2,827 JSON files. All 98 source-backed manifest entries resolve, source IDs match, and SHA-256 values recompute correctly; no `workflow_path` is missing.

8. **Scope and whitespace — PASS.** The range is one D13 commit containing only D13 scenarios, harness code/docs/tests, the D13 brief, and corpus-mount ignore rule. `git diff --check 0f015101..b39f0c91` exits clean. Non-blocking evidence discrepancy: the actual range is 53 files, +2967/−19, not the stated 47 files, +1210/−19.

9. **Focused tests — LIMITED BY SANDBOX.** The requested slice collects exactly 71 tests. Full execution cannot use `tmp_path` because no writable temporary directory exists in this read-only sandbox. A broader attempt produced 14 passes and 79 setup errors, all from that restriction rather than assertions. Five read-only-compatible manifest/runner tests passed independently.

### Required rework

- `tests/live_agentic_harness/assessor.py:641-646,812-817`: do not let a `desired` scenario bypass all judging merely through an allowlisted refusal label. Require an active grounded-refusal judge, failing closed when unavailable, or remove the refusal bypass for these scenarios.
- `tests/test_live_agentic_harness_guard_contract.py:288-332`: add coverage proving an unsupported or fabricated `clarify`/`requires_custom_nodes` refusal cannot pass.
- `tests/test_live_agentic_harness_corpus_manifest.py:76-79`: extend the desired-edit corpus assertion to detect judge-bypassing refusal configurations.
