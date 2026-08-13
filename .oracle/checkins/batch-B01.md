Reading additional input from stdin...
2026-08-13T11:37:17.682795Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:17.682864Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:17.682974Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffae9-87a9-7d72-a157-e68bbbfbb52b
--------
user
# MEGADO CHECKPOINT — Batch B01 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the B01 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**B01 [HARD] — Typed failures and unified attempt provenance.** Tasks + acceptance from `.oracle/tasklist.md` (B01 section). The diff to review: `git diff 16d80bbe..e33f0260` (G0R PASS SHA → B01 commit). The executor was GPT-5.6 Sol (workspace-write, 30-min clamp hit mid-verification; the orchestrator ran the focused suite to completion).

## Executor evidence

- Implementation across 14 files (+1141/−252): worker.py, runtime.py, provider.py, agent_backend.py, contracts.py, core.py, artifacts.py, harness adapter.py + runner.py, and 6 test files.
- Canonical attempt shape flows worker → runtime/provider → executor reports; successful batch metadata merged (was discarded at 3 runtime helpers: python/delta/batch).
- Harness prose matching replaced with typed failure inspection; only `empty_response` + observed zero completion tokens trigger fresh-transport retry.
- Orchestrator verification: **556 passed** (`-p no:rerunfailures`; the socket-binding rerunfailures plugin cannot run in this environment) across classify_only, contracts, flows, runtime_adapter, headless_agent_artifacts, runner_persistence, runtime_worker_retry.

## Review focus (adversarial)

1. Confirm the ONE additive evidence contract — no parallel formats (grep for the attempt shape; verify contracts.py defines it once and all boundaries consume it).
2. Failure taxonomy distinct: empty response / malformed non-empty JSON / non-JSON content / missing required fields / timeout / capacity — each serializes distinctly (find the enum/type).
3. Success-path provenance: classify, reply, AND batch calls retain requested+resolved model, adapter, provider, transport, endpoint, finish reason, token usage through final artifacts (the 3 stripping seams fixed).
4. Retry policy: fresh-transport retry fires ONLY for typed empty + observed zero tokens; never derived from response wording; malformed non-empty stays product_fail.
5. Redaction: negative fixture proves keys/auth headers/secret URL params cannot persist.
6. Unsupported routes → explicit `unknown`, never inferred.
7. Scope: diff contains only B01-scope files; `git diff --check 16d80bbe..e33f0260` clean.
8. Run the focused suite yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks); live runs skipped (orchestrator-phase).

## Output

First line: `B01 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–8) with evidence, and an issue list if FAIL (each with file:line + what to rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` guidance for this checkpoint review, and I’ll keep the work strictly read-only. I’ll inspect the acceptance contract and diff first, then independently run the focused tests and report evidence against all eight gates.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
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
The `megado` checkpoint protocol calls for delegated adversarial checks, so I’m splitting the read-only inspection into independent passes while I perform the integrative review. No files will be changed.
2026-08-13T11:37:40.773725Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:40.773803Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:40.773817Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:45.015591Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:45.015965Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:45.015999Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:52.819604Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:52.819862Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T11:37:52.819894Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc 'git status --short --branch && git rev-parse --show-toplevel && git log --oneline -5' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "rg -n -A80 -B8 '"'^##? B01|B01 '"\\[' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git diff --stat 16d80bbe..e33f0260 && git diff --name-status 16d80bbe..e33f0260 && git diff --check 16d80bbe..e33f0260' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 51ms:
49-- Focused G0 tests pass.
50-
51-### Oracle checkpoint
52-
53-Review scorer/narrator changes and focused fixtures. Record `PASS` as the formal G0 verdict, plus either a reconciled historical rescore or an explicit “source artifacts unavailable” statement.
54-
55----
56-
57:## B01 — Typed failures and unified attempt provenance `[HARD]`
58-
59-### Tasks
60-
61-1. Introduce one additive model-attempt evidence contract across worker, runtime, provider/backend, executor, artifacts, and harness.
62-2. Distinguish:
63-   - empty response;
64-   - malformed non-empty JSON;
65-   - non-JSON content;
66-   - missing required fields;
67-   - timeout;
68-   - capacity/provider failure.
69-3. Persist on every successful and failed attempt:
70-   - phase and attempt;
71-   - requested and resolved model;
72-   - adapter;
73-   - actual provider and transport;
74-   - normalized endpoint;
75-   - finish reason;
76-   - token usage.
77-4. Persist bounded raw previews only for failures.
78-5. Fix the three success-path runtime stripping seams and merge worker-observed metadata into batch audit metadata and final report artifacts.
79-6. Permit a fresh-transport retry only for typed empty responses. Never derive infrastructure status from response wording.
80-7. Serialize unavailable non-Hermes provenance as `unknown`; never infer it.
81-
82-### Acceptance
83-
84-- Every failure type serializes distinctly.
85-- Successful classify, reply, and batch calls retain provenance through final artifacts.
86-- Requested and resolved models remain distinct across routing/retries.
87-- Typed empty evidence reaches the existing retry; malformed non-empty results remain product failures.
88-- Unsupported routes report explicit unknowns.
89-- Redaction proves keys, authorization data, and secret URL parameters cannot persist.
90-
91-### Oracle checkpoint
92-
93-Trace representative successful and failed calls end to end. Reject parallel evidence formats or inferred fields.
94-
95----
96-
97-## D13 — Corpus integrity, satisfiability, and semantic rubrics `[HARD]`
98-
99-### Tasks
100-
101-1. Check in an authoritative manifest for the current 100 scenarios:
102-   - stable ID;
103-   - path;
104-   - descriptor SHA-256;
105-   - inclusion status;
106-   - source-workflow ID and hash where applicable.
107-2. Make runner discovery consume the manifest rather than an unrestricted glob. Reject missing, changed, duplicate, or unmanifested files.
108-3. Audit scenario/query/schema/operation/rubric coherence, prioritizing all anomalous or revised cases.
109-4. Correct the three mislabeled edits:
110-   - set edit/change expectations truthfully if satisfiable;
111-   - otherwise rewrite or replace them while preserving coverage;
112-   - never let them pass as no-ops.
113-5. Classify the remaining 37 query non-edits:
114-   - 35 semantic product scenarios receive explicit expected-answer criteria;
115-   - the smoke and speed-distillation cases become explicit health controls.
116-6. Ensure every retained edit `desired` block feeds an active judge.
117-7. Record every rewrite/replacement and preserve matched-versus-revised reporting.
118-8. Provision `external_workflows/` before accepting satisfiability or source hashes.
119-
120-### Acceptance
121-
122-- The manifest selects exactly 100 unique ID/stem-matched scenarios.
123-- The 40 no-change-routed cases reconcile as 35 semantic non-edits, 2 health controls, and 3 corrected edits.
124-- The three edits cannot pass without a judged graph change or legitimate grounded refusal.
125-- All 35 semantic non-edits have evidence-backed rubrics.
126-- Health controls are excluded from semantic-product rates.
127-- Stray scenario files cannot silently change the lane.
128-- Source-workflow hashes resolve before D13 passes.
129-
130-### Oracle checkpoint
131-
132-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
133-
134----
135-
136-## B04 — Real-schema authority
137-

 succeeded in 77ms:
## oracle-run
?? .oracle/checkins/batch-B01.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
e33f0260 megado B01: unified model-attempt evidence contract (typed failures: empty/malformed/non-JSON/missing-field/timeout/capacity), success-path provenance preserved, fresh-transport retry only on typed empty+zero-tokens, redaction — 556 focused tests green
45415680 megado: record G0R oracle PASS (16d80bbe)
9d003159 megado: tasklist revision — B08 task numbering 7->8/9 (no content change; post-freeze revision recorded per protocol)
16d80bbe megado G0R rework: landed-count guard reads canonical route — edit-route self-relabeling and route_not_applyable fail closed; 5 new controls; 54 guard tests green
833b3476 megado G0R: remove residual unchanged prose gate, restore landed-count guard, narrator write-failure preserves message, prompt contradiction fixed — 406 focused tests green

 exited 2 in 150ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/briefs/batch-B01.md                   |   39 +
 .oracle/checkins/batch-G0R.md                 | 5087 +++++++++++++++++++++++++
 .oracle/tasklist.md                           |    4 +-
 tests/live_agentic_harness/adapter.py         |    1 +
 tests/live_agentic_harness/runner.py          |   83 +-
 tests/test_agent_runtime_adapter.py           |  124 +
 tests/test_executor_contracts.py              |   32 +
 tests/test_headless_agent_artifacts.py        |   77 +
 tests/test_live_agentic_runner_persistence.py |  124 +-
 tests/test_runtime_worker_retry.py            |  118 +-
 vibecomfy/agent/artifacts.py                  |   30 +-
 vibecomfy/comfy_nodes/agent/provider.py       |  109 +-
 vibecomfy/comfy_nodes/agent/runtime.py        |  278 +-
 vibecomfy/comfy_nodes/agent/worker.py         |  137 +-
 vibecomfy/executor/agent_backend.py           |   57 +-
 vibecomfy/executor/contracts.py               |  206 +
 vibecomfy/executor/core.py                    |   17 +
 17 files changed, 6269 insertions(+), 254 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/briefs/batch-B01.md
A	.oracle/checkins/batch-G0R.md
M	.oracle/tasklist.md
M	tests/live_agentic_harness/adapter.py
M	tests/live_agentic_harness/runner.py
M	tests/test_agent_runtime_adapter.py
M	tests/test_executor_contracts.py
M	tests/test_headless_agent_artifacts.py
M	tests/test_live_agentic_runner_persistence.py
M	tests/test_runtime_worker_retry.py
M	vibecomfy/agent/artifacts.py
M	vibecomfy/comfy_nodes/agent/provider.py
M	vibecomfy/comfy_nodes/agent/runtime.py
M	vibecomfy/comfy_nodes/agent/worker.py
M	vibecomfy/executor/agent_backend.py
M	vibecomfy/executor/contracts.py
M	vibecomfy/executor/core.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-G0R.md:917: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:929: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:938: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:952: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:975: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:981: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:984: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1000: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1004: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1014: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1018: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1020: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1025: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1027: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1029: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1031: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1038: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1045: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1059: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1068: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1069: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1081: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1082: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1092: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1093: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1096: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1119: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1120: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1138: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1139: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1197: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1205: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1208: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1212: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1214: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1215: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1231: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1242: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1254: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1272: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1334: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1343: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1375: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1381: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1394: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1404: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1431: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1433: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1443: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1464: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1479: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1482: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1485: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1488: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1489: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1491: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1524: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1525: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1566: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1578: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1612: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1626: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1627: trailing whitespace.
+
.oracle/checkins/batch-G0R.md:1898: trailing whitespace.
+   225
.oracle/checkins/batch-G0R.md:1899: trailing whitespace.
+   226
.oracle/checkins/batch-G0R.md:1902: trailing whitespace.
+   229
.oracle/checkins/batch-G0R.md:1926: trailing whitespace.
+   253
.oracle/checkins/batch-G0R.md:1927: trailing whitespace.
+   254
.oracle/checkins/batch-G0R.md:1930: trailing whitespace.
+   257
.oracle/checkins/batch-G0R.md:1942: trailing whitespace.
+   269
.oracle/checkins/batch-G0R.md:1943: trailing whitespace.
+   270
.oracle/checkins/batch-G0R.md:1950: trailing whitespace.
+   277
.oracle/checkins/batch-G0R.md:1951: trailing whitespace.
+   278
.oracle/checkins/batch-G0R.md:1957: trailing whitespace.
+   284
.oracle/checkins/batch-G0R.md:1959: trailing whitespace.
+   620
.oracle/checkins/batch-G0R.md:1961: trailing whitespace.
+   622
.oracle/checkins/batch-G0R.md:1970: trailing whitespace.
+   631
.oracle/checkins/batch-G0R.md:1976: trailing whitespace.
+   637
.oracle/checkins/batch-G0R.md:1986: trailing whitespace.
+   647
.oracle/checkins/batch-G0R.md:2004: trailing whitespace.
+   665
.oracle/checkins/batch-G0R.md:2016: trailing whitespace.
+   677
.oracle/checkins/batch-G0R.md:2034: trailing whitespace.
+   695
.oracle/checkins/batch-G0R.md:2064: trailing whitespace.
+   725
.oracle/checkins/batch-G0R.md:2086: trailing whitespace.
+   747
.oracle/checkins/batch-G0R.md:2096: trailing whitespace.
+   757
.oracle/checkins/batch-G0R.md:2112: trailing whitespace.
+   877
.oracle/checkins/batch-G0R.md:2122: trailing whitespace.
+   887
.oracle/checkins/batch-G0R.md:2138: trailing whitespace.
+   903
.oracle/checkins/batch-G0R.md:2140: trailing whitespace.
+   905
.oracle/checkins/batch-G0R.md:2146: trailing whitespace.
+   485
.oracle/checkins/batch-G0R.md:2148: trailing whitespace.
+   487
.oracle/checkins/batch-G0R.md:2151: trailing whitespace.
+   490
.oracle/checkins/batch-G0R.md:2152: trailing whitespace.
+   491
.oracle/checkins/batch-G0R.md:2167: trailing whitespace.
+   506
.oracle/checkins/batch-G0R.md:2179: trailing whitespace.
+   518
.oracle/checkins/batch-G0R.md:2318: trailing whitespace.
+   657
.oracle/checkins/batch-G0R.md:2319: trailing whitespace.
+   658
.oracle/checkins/batch-G0R.md:2334: trailing whitespace.
+   673
.oracle/checkins/batch-G0R.md:2344: trailing whitespace.
+   683
.oracle/checkins/batch-G0R.md:2352: trailing whitespace.
+   691
.oracle/checkins/batch-G0R.md:2353: trailing whitespace.
+   692
.oracle/checkins/batch-G0R.md:2358: trailing whitespace.
+   697
.oracle/checkins/batch-G0R.md:2378: trailing whitespace.
+   717
.oracle/checkins/batch-G0R.md:2384: trailing whitespace.
+   723
.oracle/checkins/batch-G0R.md:2392: trailing whitespace.
+   850
.oracle/checkins/batch-G0R.md:2401: trailing whitespace.
+   859
.oracle/checkins/batch-G0R.md:2402: trailing whitespace.
+   860
.oracle/checkins/batch-G0R.md:2411: trailing whitespace.
+   869
.oracle/checkins/batch-G0R.md:2412: trailing whitespace.
+   870
.oracle/checkins/batch-G0R.md:2444: trailing whitespace.
+   902
.oracle/checkins/batch-G0R.md:2450: trailing whitespace.
+   908
.oracle/checkins/batch-G0R.md:2458: trailing whitespace.
+   916
.oracle/checkins/batch-G0R.md:2459: trailing whitespace.
+   917
.oracle/checkins/batch-G0R.md:2480: trailing whitespace.
+   938
.oracle/checkins/batch-G0R.md:2488: trailing whitespace.
+   946
.oracle/checkins/batch-G0R.md:2496: trailing whitespace.
+   954
.oracle/checkins/batch-G0R.md:2497: trailing whitespace.
+   955
.oracle/checkins/batch-G0R.md:2517: trailing whitespace.
+   975
.oracle/checkins/batch-G0R.md:2528: trailing whitespace.
+   986
.oracle/checkins/batch-G0R.md:2537: trailing whitespace.
+   995
.oracle/checkins/batch-G0R.md:2538: trailing whitespace.
+   996
.oracle/checkins/batch-G0R.md:2558: trailing whitespace.
+  1016
.oracle/checkins/batch-G0R.md:2566: trailing whitespace.
+  1024
.oracle/checkins/batch-G0R.md:2574: trailing whitespace.
+  1032
.oracle/checkins/batch-G0R.md:2575: trailing whitespace.
+  1033
.oracle/checkins/batch-G0R.md:2594: trailing whitespace.
+  1052
.oracle/checkins/batch-G0R.md:2602: trailing whitespace.
+  1060
.oracle/checkins/batch-G0R.md:2610: trailing whitespace.
+  1068
.oracle/checkins/batch-G0R.md:2611: trailing whitespace.
+  1069
.oracle/checkins/batch-G0R.md:2631: trailing whitespace.
+  1089
.oracle/checkins/batch-G0R.md:2639: trailing whitespace.
+  1097
.oracle/checkins/batch-G0R.md:2647: trailing whitespace.
+  1105
.oracle/checkins/batch-G0R.md:2648: trailing whitespace.
+  1106
.oracle/checkins/batch-G0R.md:2671: trailing whitespace.
+  1129
.oracle/checkins/batch-G0R.md:2683: trailing whitespace.
+  1141
.oracle/checkins/batch-G0R.md:2690: trailing whitespace.
+  1148
.oracle/checkins/batch-G0R.md:2691: trailing whitespace.
+  1149
.oracle/checkins/batch-G0R.md:2713: trailing whitespace.
+  1171
.oracle/checkins/batch-G0R.md:2721: trailing whitespace.
+  1179
.oracle/checkins/batch-G0R.md:2732: trailing whitespace.
+  1190
.oracle/checkins/batch-G0R.md:2733: trailing whitespace.
+  1191
.oracle/checkins/batch-G0R.md:2743: trailing whitespace.
+   145
.oracle/checkins/batch-G0R.md:2748: trailing whitespace.
+   150
.oracle/checkins/batch-G0R.md:2752: trailing whitespace.
+   154
.oracle/checkins/batch-G0R.md:2753: trailing whitespace.
+   155
.oracle/checkins/batch-G0R.md:2757: trailing whitespace.
+   159
.oracle/checkins/batch-G0R.md:2783: trailing whitespace.
+   185
.oracle/checkins/batch-G0R.md:2807: trailing whitespace.
+   209
.oracle/checkins/batch-G0R.md:2814: trailing whitespace.
+   216
.oracle/checkins/batch-G0R.md:2847: trailing whitespace.
+   249
.oracle/checkins/batch-G0R.md:2851: trailing whitespace.
+   253
.oracle/checkins/batch-G0R.md:2852: trailing whitespace.
+   254
.oracle/checkins/batch-G0R.md:2857: trailing whitespace.
+   259
.oracle/checkins/batch-G0R.md:2884: trailing whitespace.
+   286
.oracle/checkins/batch-G0R.md:2889: trailing whitespace.
+   291
.oracle/checkins/batch-G0R.md:2902: trailing whitespace.
+   258
.oracle/checkins/batch-G0R.md:2903: trailing whitespace.
+   259
.oracle/checkins/batch-G0R.md:2905: trailing whitespace.
+   261
.oracle/checkins/batch-G0R.md:2906: trailing whitespace.
+   262
.oracle/checkins/batch-G0R.md:2917: trailing whitespace.
+   273
.oracle/checkins/batch-G0R.md:2941: trailing whitespace.
+   297
.oracle/checkins/batch-G0R.md:2942: trailing whitespace.
+   298
.oracle/checkins/batch-G0R.md:2944: trailing whitespace.
+   300
.oracle/checkins/batch-G0R.md:2945: trailing whitespace.
+   301
.oracle/checkins/batch-G0R.md:2963: trailing whitespace.
+   908
.oracle/checkins/batch-G0R.md:2970: trailing whitespace.
+   915
.oracle/checkins/batch-G0R.md:2973: trailing whitespace.
+   918
.oracle/checkins/batch-G0R.md:2979: trailing whitespace.
+   924
.oracle/checkins/batch-G0R.md:2986: trailing whitespace.
+   931
.oracle/checkins/batch-G0R.md:2991: trailing whitespace.
+   936
.oracle/checkins/batch-G0R.md:2994: trailing whitespace.
+   939
.oracle/checkins/batch-G0R.md:2999: trailing whitespace.
+   944
.oracle/checkins/batch-G0R.md:3019: trailing whitespace.
+   964
.oracle/checkins/batch-G0R.md:3026: trailing whitespace.
+   971
.oracle/checkins/batch-G0R.md:3029: trailing whitespace.
+   974
.oracle/checkins/batch-G0R.md:3030: trailing whitespace.
+   975
.oracle/checkins/batch-G0R.md:3032: trailing whitespace.
+   977
.oracle/checkins/batch-G0R.md:3033: trailing whitespace.
+   978
.oracle/checkins/batch-G0R.md:3046: trailing whitespace.
+   232
.oracle/checkins/batch-G0R.md:3049: trailing whitespace.
+   235
.oracle/checkins/batch-G0R.md:3052: trailing whitespace.
+   238
.oracle/checkins/batch-G0R.md:3055: trailing whitespace.
+   241
.oracle/checkins/batch-G0R.md:3056: trailing whitespace.
+   242
.oracle/checkins/batch-G0R.md:3058: trailing whitespace.
+   244
.oracle/checkins/batch-G0R.md:3089: trailing whitespace.
+   275
.oracle/checkins/batch-G0R.md:3090: trailing whitespace.
+   276
.oracle/checkins/batch-G0R.md:3100: trailing whitespace.
+   403
.oracle/checkins/batch-G0R.md:3105: trailing whitespace.
+   408
.oracle/checkins/batch-G0R.md:3135: trailing whitespace.
+   438
.oracle/checkins/batch-G0R.md:3147: trailing whitespace.
+   450
.oracle/checkins/batch-G0R.md:3174: trailing whitespace.
+   477
.oracle/checkins/batch-G0R.md:3188: trailing whitespace.
+   491
.oracle/checkins/batch-G0R.md:3189: trailing whitespace.
+   492
.oracle/checkins/batch-G0R.md:3198: trailing whitespace.
+   850
.oracle/checkins/batch-G0R.md:3207: trailing whitespace.
+   859
.oracle/checkins/batch-G0R.md:3208: trailing whitespace.
+   860
.oracle/checkins/batch-G0R.md:3217: trailing whitespace.
+   869
.oracle/checkins/batch-G0R.md:3218: trailing whitespace.
+   870
.oracle/checkins/batch-G0R.md:3250: trailing whitespace.
+   902
.oracle/checkins/batch-G0R.md:3256: trailing whitespace.
+   908
.oracle/checkins/batch-G0R.md:3264: trailing whitespace.
+   916
.oracle/checkins/batch-G0R.md:3265: trailing whitespace.
+   917
.oracle/checkins/batch-G0R.md:3286: trailing whitespace.
+   938
.oracle/checkins/batch-G0R.md:3294: trailing whitespace.
+   946
.oracle/checkins/batch-G0R.md:3302: trailing whitespace.
+   954
.oracle/checkins/batch-G0R.md:3303: trailing whitespace.
+   955
.oracle/checkins/batch-G0R.md:3323: trailing whitespace.
+   975
.oracle/checkins/batch-G0R.md:3334: trailing whitespace.
+   986
.oracle/checkins/batch-G0R.md:3343: trailing whitespace.
+   995
.oracle/checkins/batch-G0R.md:3344: trailing whitespace.
+   996
.oracle/checkins/batch-G0R.md:3364: trailing whitespace.
+  1016
.oracle/checkins/batch-G0R.md:3372: trailing whitespace.
+  1024
.oracle/checkins/batch-G0R.md:3380: trailing whitespace.
+  1032
.oracle/checkins/batch-G0R.md:3381: trailing whitespace.
+  1033
.oracle/checkins/batch-G0R.md:3400: trailing whitespace.
+  1052
.oracle/checkins/batch-G0R.md:3408: trailing whitespace.
+  1060
.oracle/checkins/batch-G0R.md:3416: trailing whitespace.
+  1068
.oracle/checkins/batch-G0R.md:3417: trailing whitespace.
+  1069
.oracle/checkins/batch-G0R.md:3437: trailing whitespace.
+  1089
.oracle/checkins/batch-G0R.md:3445: trailing whitespace.
+  1097
.oracle/checkins/batch-G0R.md:3453: trailing whitespace.
+  1105
.oracle/checkins/batch-G0R.md:3454: trailing whitespace.
+  1106
.oracle/checkins/batch-G0R.md:3477: trailing whitespace.
+  1129
.oracle/checkins/batch-G0R.md:3489: trailing whitespace.
+  1141
.oracle/checkins/batch-G0R.md:3496: trailing whitespace.
+  1148
.oracle/checkins/batch-G0R.md:3497: trailing whitespace.
+  1149
.oracle/checkins/batch-G0R.md:3519: trailing whitespace.
+  1171
.oracle/checkins/batch-G0R.md:3527: trailing whitespace.
+  1179
.oracle/checkins/batch-G0R.md:3538: trailing whitespace.
+  1190
.oracle/checkins/batch-G0R.md:3539: trailing whitespace.
+  1191
.oracle/checkins/batch-G0R.md:3682: trailing whitespace.
+   657
.oracle/checkins/batch-G0R.md:3683: trailing whitespace.
+   658
.oracle/checkins/batch-G0R.md:3698: trailing whitespace.
+   673
.oracle/checkins/batch-G0R.md:3708: trailing whitespace.
+   683
.oracle/checkins/batch-G0R.md:3716: trailing whitespace.
+   691
.oracle/checkins/batch-G0R.md:3717: trailing whitespace.
+   692
.oracle/checkins/batch-G0R.md:3757: trailing whitespace.
+     2
.oracle/checkins/batch-G0R.md:3763: trailing whitespace.
+     8
.oracle/checkins/batch-G0R.md:3765: trailing whitespace.
+    10
.oracle/checkins/batch-G0R.md:3772: trailing whitespace.
+    17
.oracle/checkins/batch-G0R.md:3774: trailing whitespace.
+    19
.oracle/checkins/batch-G0R.md:3776: trailing whitespace.
+    21
.oracle/checkins/batch-G0R.md:3790: trailing whitespace.
+    35
.oracle/checkins/batch-G0R.md:3791: trailing whitespace.
+    36
.oracle/checkins/batch-G0R.md:3822: trailing whitespace.
+    67
.oracle/checkins/batch-G0R.md:3823: trailing whitespace.
+    68
.oracle/checkins/batch-G0R.md:3826: trailing whitespace.
+    71
.oracle/checkins/batch-G0R.md:3833: trailing whitespace.
+    78
.oracle/checkins/batch-G0R.md:3834: trailing whitespace.
+    79
.oracle/checkins/batch-G0R.md:3837: trailing whitespace.
+    82
.oracle/checkins/batch-G0R.md:3844: trailing whitespace.
+    89
.oracle/checkins/batch-G0R.md:3852: trailing whitespace.
+    97
.oracle/checkins/batch-G0R.md:3858: trailing whitespace.
+   103
.oracle/checkins/batch-G0R.md:3859: trailing whitespace.
+   104
.oracle/checkins/batch-G0R.md:3866: trailing whitespace.
+   111
.oracle/checkins/batch-G0R.md:3867: trailing whitespace.
+   112
.oracle/checkins/batch-G0R.md:3874: trailing whitespace.
+   119
.oracle/checkins/batch-G0R.md:3875: trailing whitespace.
+   120
.oracle/checkins/batch-G0R.md:3881: trailing whitespace.
+   126
.oracle/checkins/batch-G0R.md:3882: trailing whitespace.
+   127
.oracle/checkins/batch-G0R.md:3887: trailing whitespace.
+   132
.oracle/checkins/batch-G0R.md:3888: trailing whitespace.
+   133
.oracle/checkins/batch-G0R.md:3891: trailing whitespace.
+   136
.oracle/checkins/batch-G0R.md:3897: trailing whitespace.
+   142
.oracle/checkins/batch-G0R.md:3912: trailing whitespace.
+   157
.oracle/checkins/batch-G0R.md:3917: trailing whitespace.
+   162
.oracle/checkins/batch-G0R.md:3924: trailing whitespace.
+   169
.oracle/checkins/batch-G0R.md:3932: trailing whitespace.
+   177
.oracle/checkins/batch-G0R.md:3933: trailing whitespace.
+   178
.oracle/checkins/batch-G0R.md:3936: trailing whitespace.
+   181
.oracle/checkins/batch-G0R.md:3937: trailing whitespace.
+   182
.oracle/checkins/batch-G0R.md:3945: trailing whitespace.
+   190
.oracle/checkins/batch-G0R.md:3946: trailing whitespace.
+   191
.oracle/checkins/batch-G0R.md:3959: trailing whitespace.
+   204
.oracle/checkins/batch-G0R.md:3960: trailing whitespace.
+   205
.oracle/checkins/batch-G0R.md:3979: trailing whitespace.
+   224
.oracle/checkins/batch-G0R.md:3980: trailing whitespace.
+   225
.oracle/checkins/batch-G0R.md:3987: trailing whitespace.
+   232
.oracle/checkins/batch-G0R.md:3988: trailing whitespace.
+   233
.oracle/checkins/batch-G0R.md:3990: trailing whitespace.
+   235
.oracle/checkins/batch-G0R.md:4274: trailing whitespace.
+   235
.oracle/checkins/batch-G0R.md:4288: trailing whitespace.
+   249
.oracle/checkins/batch-G0R.md:4302: trailing whitespace.
+   263
.oracle/checkins/batch-G0R.md:4313: trailing whitespace.
+   274
.oracle/checkins/batch-G0R.md:4333: trailing whitespace.
+  2203
.oracle/checkins/batch-G0R.md:4346: trailing whitespace.
+  2216
.oracle/checkins/batch-G0R.md:4347: trailing whitespace.
+  2217
.oracle/checkins/batch-G0R.md:4351: trailing whitespace.
+  2221
.oracle/checkins/batch-G0R.md:4356: trailing whitespace.
+  2226
.oracle/checkins/batch-G0R.md:4363: trailing whitespace.
+  2233
.oracle/checkins/batch-G0R.md:4367: trailing whitespace.
+  2237
.oracle/checkins/batch-G0R.md:4379: trailing whitespace.
+  2249
.oracle/checkins/batch-G0R.md:4381: trailing whitespace.
+  2251
.oracle/checkins/batch-G0R.md:4385: trailing whitespace.
+  2255
.oracle/checkins/batch-G0R.md:4395: trailing whitespace.
+  2265
.oracle/checkins/batch-G0R.md:4401: trailing whitespace.
+  2271
.oracle/checkins/batch-G0R.md:4420: trailing whitespace.
+  2290
.oracle/checkins/batch-G0R.md:4424: trailing whitespace.
+  2294
.oracle/checkins/batch-G0R.md:4429: trailing whitespace.
+  2299
.oracle/checkins/batch-G0R.md:4433: trailing whitespace.
+  2303
.oracle/checkins/batch-G0R.md:4436: trailing whitespace.
+  2306
.oracle/checkins/batch-G0R.md:4833: trailing whitespace.
+   275
.oracle/checkins/batch-G0R.md:4834: trailing whitespace.
+   276
.oracle/checkins/batch-G0R.md:4857: trailing whitespace.
+   299
.oracle/checkins/batch-G0R.md:4858: trailing whitespace.
+   300
.oracle/checkins/batch-G0R.md:4860: trailing whitespace.
+   302
.oracle/checkins/batch-G0R.md:4870: trailing whitespace.
+   312
.oracle/checkins/batch-G0R.md:4873: trailing whitespace.
+   315
.oracle/checkins/batch-G0R.md:4893: trailing whitespace.
+   335
.oracle/checkins/batch-G0R.md:4900: trailing whitespace.
+   342
.oracle/checkins/batch-G0R.md:4904: trailing whitespace.
+   346
.oracle/checkins/batch-G0R.md:4906: trailing whitespace.
+   348
.oracle/checkins/batch-G0R.md:4907: trailing whitespace.
+   349
.oracle/checkins/batch-G0R.md:4909: trailing whitespace.
+   351
.oracle/checkins/batch-G0R.md:4921: trailing whitespace.
+   363
.oracle/checkins/batch-G0R.md:4927: trailing whitespace.
+   369
.oracle/checkins/batch-G0R.md:4932: trailing whitespace.
+   374
.oracle/checkins/batch-G0R.md:4948: trailing whitespace.
+   390
.oracle/checkins/batch-G0R.md:4952: trailing whitespace.
+   394
.oracle/checkins/batch-G0R.md:4961: trailing whitespace.
+   403

codex
The first hard gate has already surfaced a material mismatch: the requested commit range is not clean and includes a 5,087-line prior-checkpoint artifact plus tasklist/brief changes; `git diff --check` reports many whitespace errors. I’m continuing the product-code review so the verdict distinguishes this scope failure from any implementation defects.
exec
/bin/zsh -lc 'rg -n "ModelAttempt|AttemptEvidence|attempt_evidence|model_attempt|failure_kind|FailureKind|empty_response|malformed|non_json|missing_required|capacity|completion_tokens|fresh_transport|provenance|requested_model|resolved_model|normalized_endpoint" vibecomfy tests/live_agentic_harness tests/test_agent_runtime_adapter.py tests/test_executor_contracts.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 131ms:
vibecomfy/porting/object_info/consume.py:288:    lookup semantics. Identity-aware callers get a provenance-sensitive result
vibecomfy/porting/object_info/consume.py:342:        code = "provenanced_cache_miss_fallback"
vibecomfy/porting/object_info/consume.py:345:            f"{_identity_label(normalized_identity)}; using a different provenanced class cache entry."
vibecomfy/porting/object_info/consume.py:348:        code = "unprovenanced_cache_fallback"
vibecomfy/demo_factory/run_campaign.py:811:    emission produced malformed slots the apply-validator misreads.
vibecomfy/security/provenance.py:4:defines the provenance literal, the metadata key, and pure helpers to read,
vibecomfy/security/provenance.py:5:tag, and confirm provenance on a node-like object exposing a ``metadata``
vibecomfy/security/provenance.py:26:PROVENANCE_KEY = "provenance"
vibecomfy/security/provenance.py:32:    """Return the provenance tag on ``node``.
vibecomfy/security/provenance.py:55:            f"invalid provenance {value!r}; expected one of {sorted(_VALID)}"
vibecomfy/security/provenance.py:59:        raise TypeError("node.metadata must be a dict to tag provenance")
vibecomfy/demo_factory/creative.py:336:            # Skip malformed proposals
vibecomfy/demo_factory/creative.py:337:            print(f"Skipping malformed proposal: {e}")
vibecomfy/security/gate.py:1:"""S4 capability fence — provenance request scope and confirmation gate.
vibecomfy/security/gate.py:5:1. ``requesting_provenance`` / ``untrusted_scope`` — a ContextVar that ambient
vibecomfy/security/gate.py:18:   restricted generated-Python loader is allowed to mint that provenance.
vibecomfy/security/gate.py:33:from vibecomfy.security.provenance import Provenance
vibecomfy/security/gate.py:35:requesting_provenance: ContextVar[Provenance] = ContextVar(
vibecomfy/security/gate.py:36:    "requesting_provenance", default="agent_authored"
vibecomfy/security/gate.py:42:    """Set ``requesting_provenance`` to ``"untrusted_source"`` for the block.
vibecomfy/security/gate.py:47:    token = requesting_provenance.set("untrusted_source")
vibecomfy/security/gate.py:51:        requesting_provenance.reset(token)
vibecomfy/security/gate.py:63:    class_type, provenance, capabilities, reason, details). The CLI ``main``
vibecomfy/security/gate.py:125:    provenance: Provenance,
vibecomfy/security/gate.py:134:        "provenance": provenance,
vibecomfy/security/gate.py:147:    provenance: Provenance,
vibecomfy/security/gate.py:155:      - ``provenance`` ∈ {agent_authored, agent_generated, user_confirmed}
vibecomfy/security/gate.py:167:    # Trusted or restricted-loader provenance. `agent_generated` must remain
vibecomfy/security/gate.py:169:    # provenance once present so headless execution can proceed.
vibecomfy/security/gate.py:170:    if provenance in ("agent_authored", "agent_generated", "user_confirmed"):
vibecomfy/security/gate.py:176:            provenance=provenance,
vibecomfy/security/gate.py:179:            reason="trusted_provenance",
vibecomfy/security/gate.py:189:            provenance=provenance,
vibecomfy/security/gate.py:202:            provenance=provenance,
vibecomfy/security/gate.py:221:            "provenance": provenance,
vibecomfy/security/gate.py:230:            provenance=provenance,
vibecomfy/security/gate.py:243:        f"  provenance: {provenance}",
vibecomfy/security/gate.py:262:            provenance=provenance,
vibecomfy/security/gate.py:273:        "provenance": provenance,
vibecomfy/security/gate.py:283:        provenance=provenance,
vibecomfy/security/gate.py:296:    "requesting_provenance",
vibecomfy/porting/emitter.py:55:    _is_derivable_provenance,
vibecomfy/security/__init__.py:4:provenance tags, untrusted-source scoping, confirmation gates, and graph-text
vibecomfy/security/__init__.py:16:from vibecomfy.security import provenance
vibecomfy/security/__init__.py:22:    requesting_provenance,
vibecomfy/security/__init__.py:26:from vibecomfy.security.provenance import PROVENANCE_KEY, Provenance
vibecomfy/security/__init__.py:38:    "provenance",
vibecomfy/security/__init__.py:40:    "requesting_provenance",
vibecomfy/porting/provenance.py:112:    unprovenanced: list[ProvenanceRecord] = field(default_factory=list)
vibecomfy/porting/provenance.py:125:            "unprovenanced": [record.to_json() for record in self.unprovenanced],
vibecomfy/porting/provenance.py:131:def extract_provenance(workflow: Mapping[str, Any] | str | Path) -> ProvenanceReport:
vibecomfy/porting/provenance.py:163:                    code="aux_only_git_provenance",
vibecomfy/porting/provenance.py:164:                    message=f"{record.class_type} has aux_id provenance without cnr_id",
vibecomfy/porting/provenance.py:172:            report.unprovenanced.append(record)
vibecomfy/porting/provenance.py:176:                    code="unprovenanced_execution_node",
vibecomfy/porting/provenance.py:177:                    message=f"{record.class_type} has no cnr_id or aux_id provenance",
vibecomfy/porting/provenance.py:205:                    message=f"{record.class_type} is helper/UI-only and is excluded from execution provenance requirements",
vibecomfy/porting/provenance.py:398:        return "unprovenanced"
vibecomfy/porting/provenance.py:422:    "extract_provenance",
vibecomfy/demo_factory/baseline.py:244:                    "malformed_node_record",
vibecomfy/demo_factory/baseline.py:274:                "malformed_link_collection",
vibecomfy/demo_factory/baseline.py:287:                    "malformed_raw_link",
vibecomfy/demo_factory/baseline.py:289:                    message=f"Raw link {index} is malformed.",
vibecomfy/demo_factory/baseline.py:510:def _credible_missing_required(
vibecomfy/demo_factory/baseline.py:765:        if code == "missing_required_input":
vibecomfy/demo_factory/baseline.py:766:            if _credible_missing_required(diag, nodes):
vibecomfy/security/loader_provenance.py:1:"""S4 Step 10 — provenance classifier for `exec_module` loader call sites.
vibecomfy/security/loader_provenance.py:19:from vibecomfy.security.provenance import Provenance
vibecomfy/security/loader_provenance.py:41:def _provenance_for_path(path: Path) -> Provenance:
vibecomfy/security/loader_provenance.py:61:__all__ = ["_provenance_for_path"]
vibecomfy/security/agent_generated_loader.py:3:This module is the only path that may mint ``agent_generated`` provenance for
vibecomfy/security/agent_generated_loader.py:18:from vibecomfy.security.gate import current_gate_context, requesting_provenance, require_confirmation
vibecomfy/security/agent_generated_loader.py:288:        provenance="agent_generated",
vibecomfy/security/agent_generated_loader.py:298:    token = requesting_provenance.set("agent_generated")
vibecomfy/security/agent_generated_loader.py:306:        requesting_provenance.reset(token)
vibecomfy/demo_factory/transcript.py:63:        If JSON files are malformed or missing required fields.
vibecomfy/contracts/RUNTIME_CONTRACT.md:45:1. Runtime contract validates (malformed/schema-less contracts fail before queue).
vibecomfy/demo_factory/predicates.py:99:        # Comfy model paths use both separators depending on their provenance.
vibecomfy/demo_factory/predicates.py:299:            return False, "graph contains a malformed link"
vibecomfy/porting/emit/emit_constants.py:28:from vibecomfy.porting._provenance_utils import _normalize_provenance_paths
vibecomfy/porting/emit/emit_constants.py:29:from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
vibecomfy/porting/emit/emit_constants.py:97:    "_is_derivable_provenance",
vibecomfy/porting/emit/emit_constants.py:868:    return resolve_widget_key_with_provenance(
vibecomfy/porting/emit/emit_constants.py:1031:    provenance = metadata.get("provenance")
vibecomfy/porting/emit/emit_constants.py:1032:    if isinstance(provenance, Mapping) and not _is_derivable_provenance(provenance):
vibecomfy/porting/emit/emit_constants.py:1033:        extras["provenance"] = _normalize_provenance_paths(provenance)
vibecomfy/porting/emit/emit_constants.py:1037:def _is_derivable_provenance(provenance: Mapping[str, Any]) -> bool:
vibecomfy/porting/emit/emit_constants.py:1038:    """Return true when ReadyMetadata.build can recreate the provenance."""
vibecomfy/porting/emit/emit_constants.py:1040:    return set(provenance).issubset({"source_workflow", "source_role"})
vibecomfy/porting/emit/emit_kwargs.py:22:from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
vibecomfy/porting/emit/emit_kwargs.py:1177:        return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name
vibecomfy/contracts/intent_nodes.py:279:    passthrough_on_non_json: bool = False
vibecomfy/contracts/intent_nodes.py:291:            "passthrough_on_non_json": self.passthrough_on_non_json,
vibecomfy/contracts/intent_nodes.py:596:    passthrough_on_non_json = runtime.get("passthrough_on_non_json", False)
vibecomfy/contracts/intent_nodes.py:714:    if not isinstance(passthrough_on_non_json, bool):
vibecomfy/contracts/intent_nodes.py:718:                "runtime.passthrough_on_non_json must be a boolean when present.",
vibecomfy/contracts/intent_nodes.py:721:    elif passthrough_on_non_json:
vibecomfy/contracts/intent_nodes.py:724:                "runtime_non_json_passthrough_unsupported",
vibecomfy/contracts/intent_nodes.py:725:                "Runtime-backed code must reject non-JSON outputs; passthrough_on_non_json must be false.",
vibecomfy/contracts/intent_nodes.py:742:            passthrough_on_non_json=False,
vibecomfy/contracts/intent_nodes.py:1134:                        "runtime_non_json_io",
vibecomfy/ingest/normalize.py:25:from vibecomfy.security.provenance import PROVENANCE_KEY
vibecomfy/ingest/normalize.py:53:    # malformed; structural shape is established by the rich nodes mapping.
vibecomfy/ingest/normalize.py:168:        input_provenance: dict[str, str] = {}
vibecomfy/ingest/normalize.py:185:                input_provenance[str(name)] = "edge"
vibecomfy/ingest/normalize.py:193:                input_provenance[str(name)] = "widget"
vibecomfy/ingest/normalize.py:206:                input_provenance[str(name)] = "widget"
vibecomfy/ingest/normalize.py:211:            "_input_provenance": input_provenance,
vibecomfy/ingest/normalize.py:439:    which nodes exist.  Any malformed or mixed entry raises ``ValueError``
vibecomfy/ingest/normalize.py:469:    source_provenance = source_raw.get("provenance")
vibecomfy/ingest/normalize.py:470:    if source_provenance is not None and not isinstance(source_provenance, dict):
vibecomfy/ingest/normalize.py:471:        raise ValueError("source.provenance must be a mapping or null")
vibecomfy/ingest/normalize.py:476:        provenance=deepcopy(source_provenance) if isinstance(source_provenance, dict) else {},
vibecomfy/ingest/normalize.py:888:        input_provenance = node.get("_input_provenance")
vibecomfy/ingest/normalize.py:889:        if not isinstance(input_provenance, dict):
vibecomfy/ingest/normalize.py:890:            input_provenance = {}
vibecomfy/ingest/normalize.py:895:            if input_provenance.get(key) != "widget" and is_api_link(
vibecomfy/ingest/normalize.py:925:                "_input_provenance",
vibecomfy/ingest/normalize.py:966:        schema_source = _schema_source_provenance(schema_provider, class_type)
vibecomfy/ingest/normalize.py:993:        input_provenance = node.get("_input_provenance")
vibecomfy/ingest/normalize.py:994:        if not isinstance(input_provenance, dict):
vibecomfy/ingest/normalize.py:995:            input_provenance = {}
vibecomfy/ingest/normalize.py:997:            if input_provenance.get(name) != "widget" and is_api_link(
vibecomfy/ingest/normalize.py:1190:def _schema_source_provenance(schema_provider: SchemaProvider | None, class_type: str) -> dict[str, Any] | None:
vibecomfy/porting/emit/identity.py:53:    "unprovenanced_cache_fallback": "unprovenanced_class_fallback",
vibecomfy/porting/emit/identity.py:54:    "provenanced_cache_miss_fallback": "provenance_identity_cache_miss",
vibecomfy/porting/emit/identity.py:55:    "identity_cache_miss": "provenance_identity_cache_miss",
vibecomfy/analysis/graph.py:12:from vibecomfy.security import provenance as _provenance
vibecomfy/analysis/graph.py:217:    provenance reads ``untrusted_source`` (fail-closed via
vibecomfy/analysis/graph.py:218:    :func:`vibecomfy.security.provenance.read`), every string value outside the
vibecomfy/analysis/graph.py:229:    untrusted = _provenance.read(node) == "untrusted_source"
vibecomfy/analysis/graph.py:332:                        "reason": "missing_required_input",
vibecomfy/analysis/graph.py:369:    for source in (workflow.metadata, workflow.source.provenance):
vibecomfy/scratchpad_loader.py:9:from vibecomfy.security.loader_provenance import _provenance_for_path
vibecomfy/scratchpad_loader.py:10:from vibecomfy.security.provenance import Provenance
vibecomfy/scratchpad_loader.py:24:    provenance_override: Provenance | None = None,
vibecomfy/scratchpad_loader.py:27:    if provenance_override == "agent_generated":
vibecomfy/scratchpad_loader.py:29:            "agent_generated provenance is reserved for "
vibecomfy/scratchpad_loader.py:32:    provenance = provenance_override or _provenance_for_path(path)
vibecomfy/scratchpad_loader.py:40:        provenance=provenance,
vibecomfy/schema/validate.py:155:                        "missing_required_input",
vibecomfy/schema/call_validation.py:66:                    "missing_required_input",
vibecomfy/schema/provider.py:85:    # -- provenance fields (defaults so existing code works unchanged) ------
vibecomfy/schema/provider.py:188:                "passthrough_on_non_json": InputSpec("BOOLEAN", required=False),
vibecomfy/schema/provider.py:283:        self._provenance: dict[str, SchemaSourceInfo] = {}
vibecomfy/schema/provider.py:293:    def provenance_for(self, class_type: str) -> SchemaSourceInfo | None:
vibecomfy/schema/provider.py:294:        return self._provenance.get(class_type)
vibecomfy/schema/provider.py:323:            if schema is not None or class_type in self._provenance:
vibecomfy/schema/provider.py:333:            if schema is not None or class_type in self._provenance:
vibecomfy/schema/provider.py:346:            self._provenance[class_type] = info
vibecomfy/schema/provider.py:369:            self._provenance[class_type] = SchemaSourceInfo(
vibecomfy/schema/provider.py:637:    Each `get_schema` hit records a `SchemaSourceInfo` provenance note
vibecomfy/schema/provider.py:684:            return self._with_provenance(
vibecomfy/schema/provider.py:708:                return self._with_provenance(schema, cache_info)
vibecomfy/schema/provider.py:726:                return self._with_provenance(
vibecomfy/schema/provider.py:734:            source_info = self._source.provenance_for(class_type) or SchemaSourceInfo(
vibecomfy/schema/provider.py:745:            return self._with_provenance(schema, source_info)
vibecomfy/schema/provider.py:756:            return self._with_provenance(
vibecomfy/schema/provider.py:773:                return self._with_provenance(
vibecomfy/schema/provider.py:926:    def _with_provenance(schema: NodeSchema, info: SchemaSourceInfo) -> NodeSchema:
vibecomfy/schema/provider.py:927:        # NodeSchema is frozen, so we must construct a new one with provenance.
vibecomfy/node_packs/_install.py:13:from vibecomfy.security.gate import current_gate_context, require_confirmation, requesting_provenance
vibecomfy/node_packs/_install.py:239:        provenance=requesting_provenance.get(),
vibecomfy/porting/emit/entrypoints.py:42:    provenance: dict[str, Any] | None = None,
vibecomfy/porting/emit/entrypoints.py:77:            source_provenance=provenance or {},
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:33:from .contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:119:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:130:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:140:                FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:154:                FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:167:                FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:182:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:194:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:219:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:237:                FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:254:                    FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:273:                    FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:289:                    FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:296:                    FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:310:                    FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:322:                    FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:482:                    FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/routes.py:26:    FailureKind,
vibecomfy/comfy_nodes/agent/routes.py:1051:        FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/routes.py:1094:                    FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1184:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1205:                FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/routes.py:1259:    if response.get("kind") != FailureKind.STALE_STATE_MISMATCH.value:
vibecomfy/comfy_nodes/agent/routes.py:1373:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1383:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1440:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1450:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1516:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1552:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1562:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1572:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1582:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1618:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1680:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:1808:        FailureKind as _FK,
vibecomfy/comfy_nodes/agent/routes.py:2330:                        FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:2355:                        FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/_compile/_widgets.py:761:def resolve_widget_name_with_provenance(
vibecomfy/_compile/_widgets.py:798:    return resolve_widget_name_with_provenance(class_type, idx).name
vibecomfy/_compile/_widgets.py:823:        resolution = resolve_widget_name_with_provenance(
vibecomfy/_compile/_widgets.py:851:def resolve_widget_key_with_provenance(
vibecomfy/_compile/_widgets.py:864:    return resolve_widget_name_with_provenance(
vibecomfy/_compile/_widgets.py:912:    "resolve_widget_key_with_provenance",
vibecomfy/_compile/_widgets.py:914:    "resolve_widget_name_with_provenance",
vibecomfy/comfy_nodes/agent/execution_plan.py:325:    schema_provenance: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/comfy_nodes/agent/execution_plan.py:326:    runtime_provenance: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/comfy_nodes/agent/execution_plan.py:336:        object.__setattr__(self, "schema_provenance", _freeze_jsonish(self.schema_provenance))
vibecomfy/comfy_nodes/agent/execution_plan.py:337:        object.__setattr__(self, "runtime_provenance", _freeze_jsonish(self.runtime_provenance))
vibecomfy/comfy_nodes/agent/execution_plan.py:360:            "schema_provenance": _thaw_jsonish(self.schema_provenance),
vibecomfy/comfy_nodes/agent/execution_plan.py:361:            "runtime_provenance": _thaw_jsonish(self.runtime_provenance),
vibecomfy/comfy_nodes/agent/execution_plan.py:390:    schema_provenance: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/comfy_nodes/agent/execution_plan.py:391:    runtime_provenance: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/comfy_nodes/agent/execution_plan.py:406:        object.__setattr__(self, "schema_provenance", _freeze_jsonish(self.schema_provenance))
vibecomfy/comfy_nodes/agent/execution_plan.py:407:        object.__setattr__(self, "runtime_provenance", _freeze_jsonish(self.runtime_provenance))
vibecomfy/comfy_nodes/agent/execution_plan.py:425:            "schema_provenance": _thaw_jsonish(self.schema_provenance),
vibecomfy/comfy_nodes/agent/execution_plan.py:426:            "runtime_provenance": _thaw_jsonish(self.runtime_provenance),
vibecomfy/comfy_nodes/agent/execution_plan.py:1064:        schema_provenance=_mapping_value(plan, "schema_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1065:        runtime_provenance=_mapping_value(plan, "runtime_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1094:        schema_provenance=_mapping_value(evaluation, "schema_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1095:        runtime_provenance=_mapping_value(evaluation, "runtime_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1132:            schema_provenance=_mapping_value(evaluation, "schema_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1133:            runtime_provenance=_mapping_value(evaluation, "runtime_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1293:    runtime_provenance = {
vibecomfy/comfy_nodes/agent/execution_plan.py:1301:    plan_runtime = _mapping_value(plan, "runtime_provenance")
vibecomfy/comfy_nodes/agent/execution_plan.py:1303:        runtime_provenance = {
vibecomfy/comfy_nodes/agent/execution_plan.py:1305:            **runtime_provenance,
vibecomfy/comfy_nodes/agent/execution_plan.py:1318:        schema_provenance=_mapping_value(plan, "schema_provenance") or {},
vibecomfy/comfy_nodes/agent/execution_plan.py:1319:        runtime_provenance=runtime_provenance,
vibecomfy/comfy_nodes/agent/execution_plan.py:1337:    """Return the set of evidence tiers referenced by *plan* runtime provenance.
vibecomfy/comfy_nodes/agent/execution_plan.py:1339:    Walk ``runtime_provenance`` on the plan and every required step looking
vibecomfy/comfy_nodes/agent/execution_plan.py:1354:    # plan-level runtime_provenance
vibecomfy/comfy_nodes/agent/execution_plan.py:1355:    rp = _mapping_value(plan, "runtime_provenance")
vibecomfy/comfy_nodes/agent/execution_plan.py:1359:    # step-level runtime_provenance (in case individual steps carry their own)
vibecomfy/comfy_nodes/agent/execution_plan.py:1364:                step_rp = step.get("runtime_provenance")
vibecomfy/comfy_nodes/agent/_frag_narrator.py:85:    def failure_kind(self) -> str:
vibecomfy/comfy_nodes/agent/_frag_narrator.py:426:            LOGGER.warning("Narrator malformed response, falling back: %s", exc)
vibecomfy/comfy_nodes/agent/_frag_narrator.py:427:            fallback_reason = "malformed_response"
vibecomfy/comfy_nodes/agent/gates.py:96:                rp = step.get("runtime_provenance") or {}
vibecomfy/comfy_nodes/agent/gates.py:102:                rp = getattr(step, "runtime_provenance", None)
vibecomfy/comfy_nodes/agent/runtime_code.py:24:from vibecomfy.security.provenance import PROVENANCE_KEY, Provenance
vibecomfy/comfy_nodes/agent/runtime_code.py:111:    passthrough_on_non_json: bool = False,
vibecomfy/comfy_nodes/agent/runtime_code.py:131:            "passthrough_on_non_json": passthrough_on_non_json,
vibecomfy/comfy_nodes/agent/runtime_code.py:179:# Permitted S4 provenance tags for dynamic runtime-code execution. The gate's
vibecomfy/comfy_nodes/agent/runtime_code.py:180:# trusted-provenance allow rule covers ``agent_authored`` / ``agent_generated`` /
vibecomfy/comfy_nodes/agent/runtime_code.py:186:def _resolve_runtime_provenance(vibecomfy_props: Mapping[str, Any]) -> Provenance:
vibecomfy/comfy_nodes/agent/runtime_code.py:187:    """Resolve the S4 provenance tag carried in ``vibecomfy_props``.
vibecomfy/comfy_nodes/agent/runtime_code.py:190:    where the ambient ``requesting_provenance`` ContextVar is unavailable, so
vibecomfy/comfy_nodes/agent/runtime_code.py:191:    provenance is read from the per-node ``vibecomfy_props`` metadata instead.
vibecomfy/comfy_nodes/agent/runtime_code.py:193:    resolve to ``"untrusted_source"`` so untagged or malformed dynamic code never
vibecomfy/comfy_nodes/agent/runtime_code.py:196:    unchanged and are then allowed by the gate's existing trusted-provenance
vibecomfy/comfy_nodes/agent/runtime_code.py:270:    # are preserved by the gate's existing trusted-provenance allow rule, so
vibecomfy/comfy_nodes/agent/runtime_code.py:275:        provenance=_resolve_runtime_provenance(props),
vibecomfy/comfy_nodes/agent/runtime_code.py:470:        raise RuntimeCodeExecutionError("runtime_protocol_non_json", "Runtime code worker emitted non-JSON output.") from exc
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:111:    _batch_budget_failure_kind: Any  # host: _frag_batch_reports
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:165:    FailureKind: Any  # host: _frag_state
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:253:def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:277:    return "malformed"
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:286:        detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:382:    Only ID-free selectors and hash-only provenance fields are carried.  No
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:438:        # A malformed node entry means we cannot guarantee completeness.
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1530:                first_detail = _malformed_model_json_detail(first_exc)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1584:            exc_detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1585:            malformed_diagnostic = {
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1586:                "code": "malformed_batch_response",
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1602:                "diagnostics": [malformed_diagnostic],
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1616:                            malformed_diagnostic,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1759:                    failure_kind = deps._batch_budget_failure_kind(state.batch_turns)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1789:                                "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1794:                                    "budget_classification": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1799:                            "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1802:                            "budget_classification": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2457:                        "failure_kind": deps.FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2615:    failure_kind = deps._batch_budget_failure_kind(state.batch_turns)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2616:    artifixer_report = deps._batch_budget_artifixer_report(state, failure_kind)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2647:                "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2652:                    "budget_classification": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2658:            "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2661:            "budget_classification": failure_kind.value,
vibecomfy/comfy_nodes/agent/authority_receipts.py:309:        # A present envelope is authority evidence.  If it is malformed, never
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:97:    from vibecomfy.comfy_nodes.agent.edit import (StageResult, _artifact, _duration_ms, _inject_lowering_provenance)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:142:    _inject_lowering_provenance(state)
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:179:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, StageResult, _canonical_delta_ops_envelope_payload, _duration_ms, _edit_lint_enabled, _ensure_canonical_delta_ops, _json_safe, _port_issue_to_dict, write_json_artifact)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:261:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:304:                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:393:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/templates.py:93:    provenance = metadata.get("provenance")
vibecomfy/templates.py:97:        provenance=provenance if isinstance(provenance, Mapping) else None,
vibecomfy/templates.py:505:        provenance = extras.get("provenance")
vibecomfy/templates.py:506:        if not isinstance(provenance, Mapping) and source_workflow:
vibecomfy/templates.py:507:            provenance = {"source_workflow": source_workflow}
vibecomfy/templates.py:508:            extras["provenance"] = provenance
vibecomfy/templates.py:509:        elif isinstance(provenance, Mapping) and source_workflow and "source_workflow" not in provenance:
vibecomfy/templates.py:510:            provenance = {**dict(provenance), "source_workflow": source_workflow}
vibecomfy/templates.py:511:            extras["provenance"] = provenance
vibecomfy/templates.py:512:        if isinstance(provenance, Mapping):
vibecomfy/templates.py:515:                for key, value in provenance.items()
vibecomfy/templates.py:862:    provenance = extras.get("provenance")
vibecomfy/templates.py:863:    if isinstance(provenance, Mapping) and isinstance(provenance.get("source_workflow"), str):
vibecomfy/templates.py:864:        return provenance["source_workflow"]
vibecomfy/comfy_nodes/agent/edit.py:106:        "FailureKind",
vibecomfy/comfy_nodes/agent/edit.py:192:        "_batch_budget_failure_kind",
vibecomfy/comfy_nodes/agent/edit.py:304:        "_inject_lowering_provenance",
vibecomfy/comfy_nodes/agent/edit.py:329:        "_malformed_model_json_detail",
vibecomfy/comfy_nodes/agent/contracts.py:145:    "failure_kind",
vibecomfy/comfy_nodes/agent/contracts.py:255:    "failure_kind",
vibecomfy/comfy_nodes/agent/contracts.py:304:class FailureKind(str, Enum):
vibecomfy/comfy_nodes/agent/contracts.py:690:SCAN_CODE_FAILURE_KIND: Mapping[str, FailureKind] = MappingProxyType(
vibecomfy/comfy_nodes/agent/contracts.py:692:        "syntax_error": FailureKind.SYNTAX_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:693:        "source_too_large": FailureKind.OVERSIZED_PAYLOAD,
vibecomfy/comfy_nodes/agent/contracts.py:694:        "source_type": FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:695:        "forbidden_node": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:696:        "forbidden_import": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:697:        "forbidden_name": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:698:        "forbidden_call": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:699:        "dunder_access": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:712:FAILURE_SPECS: Mapping[FailureKind, FailureSpec] = MappingProxyType(
vibecomfy/comfy_nodes/agent/contracts.py:714:        FailureKind.SYNTAX_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:723:        FailureKind.AST_SCAN_FAILURE: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:732:        FailureKind.OVERSIZED_PAYLOAD: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:741:        FailureKind.MALFORMED_MODEL_JSON: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:749:        FailureKind.MISSING_REQUIRED_FIELD: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:757:        FailureKind.PROVIDER_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:765:        FailureKind.PROVIDER_CREDIT_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:774:        FailureKind.AGENT_RUNTIME_UNAVAILABLE: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:783:        FailureKind.AUTH_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:792:        FailureKind.TIMEOUT_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:800:        FailureKind.VALIDATION_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:809:        FailureKind.UNSATISFIED_INPUT_ERROR: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:817:        FailureKind.REFUSED_EMIT: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:826:        FailureKind.EDITOR_AHEAD_CONFLICT: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:835:        FailureKind.STALE_STATE_MISMATCH: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:843:        FailureKind.UNSUPPORTED_NON_DAG: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:852:        FailureKind.LOWERING_FAILURE: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:861:        FailureKind.SCHEMA_LESS_QUEUE_BLOCKER: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:870:        FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:879:        FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:888:        FailureKind.AUDIT_WRITE_WARNING: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:897:        FailureKind.AUDIT_WRITE_FAILURE: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:906:        FailureKind.BATCH_BUDGET_EXHAUSTED: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:915:        FailureKind.CLARIFICATION_REQUIRED: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:923:        FailureKind.MODEL_MISTAKE: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:932:        FailureKind.UNREPRESENTABLE: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:941:        FailureKind.SCHEMA_GAP: FailureSpec(
vibecomfy/comfy_nodes/agent/contracts.py:970:def _coerce_failure_kind(value: FailureKind | str) -> FailureKind:
vibecomfy/comfy_nodes/agent/contracts.py:971:    if isinstance(value, FailureKind):
vibecomfy/comfy_nodes/agent/contracts.py:973:    return FailureKind(value)
vibecomfy/comfy_nodes/agent/contracts.py:1167:    kind: FailureKind
vibecomfy/comfy_nodes/agent/contracts.py:1269:    failure_kind: FailureKind | None = None
vibecomfy/comfy_nodes/agent/contracts.py:1280:        if self.failure_kind is not None:
vibecomfy/comfy_nodes/agent/contracts.py:1281:            object.__setattr__(self, "failure_kind", _coerce_failure_kind(self.failure_kind))
vibecomfy/comfy_nodes/agent/contracts.py:1284:                "failure_kind": self.failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1298:                self.failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1342:            failure_kind=failure.kind,
vibecomfy/comfy_nodes/agent/contracts.py:1358:                    "failure_kind": self.failure_kind.value,
vibecomfy/comfy_nodes/agent/contracts.py:1518:    failure_kind = response.get("failure_kind")
vibecomfy/comfy_nodes/agent/contracts.py:1519:    if not isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1520:        failure_kind = response.get("failureKind")
vibecomfy/comfy_nodes/agent/contracts.py:1521:    if not isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1523:        if isinstance(kind_value, str) and kind_value in {kind.value for kind in FailureKind}:
vibecomfy/comfy_nodes/agent/contracts.py:1524:            failure_kind = kind_value
vibecomfy/comfy_nodes/agent/contracts.py:1532:    if isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1534:            spec = FAILURE_SPECS[FailureKind(failure_kind)]
vibecomfy/comfy_nodes/agent/contracts.py:1543:        "failure_kind": failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1562:        not isinstance(outcome.get("failure_kind"), str)
vibecomfy/comfy_nodes/agent/contracts.py:1563:        or outcome.get("failure_kind") not in {kind.value for kind in FailureKind}
vibecomfy/comfy_nodes/agent/contracts.py:1675:        FailureKind.PROVIDER_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:1676:        FailureKind.PROVIDER_CREDIT_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:1677:        FailureKind.AUTH_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2194:            FailureKind.AUTH_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2207:            FailureKind.PROVIDER_CREDIT_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2217:            FailureKind.REFUSED_EMIT,
vibecomfy/comfy_nodes/agent/contracts.py:2227:            FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/contracts.py:2239:            FailureKind.TIMEOUT_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2256:            FailureKind.AGENT_RUNTIME_UNAVAILABLE,
vibecomfy/comfy_nodes/agent/contracts.py:2269:                FailureKind.AUTH_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2276:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/contracts.py:2283:                FailureKind.MALFORMED_MODEL_JSON,
vibecomfy/comfy_nodes/agent/contracts.py:2290:                FailureKind.MALFORMED_MODEL_JSON,
vibecomfy/comfy_nodes/agent/contracts.py:2297:                FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/contracts.py:2304:                FailureKind.MALFORMED_MODEL_JSON,
vibecomfy/comfy_nodes/agent/contracts.py:2310:            FailureKind.PROVIDER_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2322:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/contracts.py:2329:                FailureKind.UNSUPPORTED_NON_DAG,
vibecomfy/comfy_nodes/agent/contracts.py:2335:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/contracts.py:2343:            FailureKind.UNSATISFIED_INPUT_ERROR
vibecomfy/comfy_nodes/agent/contracts.py:2345:            else FailureKind.VALIDATION_ERROR
vibecomfy/comfy_nodes/agent/contracts.py:2356:            FailureKind.LOWERING_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:2364:            kind = FailureKind.SCHEMA_LESS_QUEUE_BLOCKER
vibecomfy/comfy_nodes/agent/contracts.py:2366:            kind = FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER
vibecomfy/comfy_nodes/agent/contracts.py:2368:            kind = FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER
vibecomfy/comfy_nodes/agent/contracts.py:2378:            FailureKind.AUDIT_WRITE_WARNING
vibecomfy/comfy_nodes/agent/contracts.py:2380:            else FailureKind.AUDIT_WRITE_FAILURE
vibecomfy/comfy_nodes/agent/contracts.py:2390:        FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:2398:    kind: FailureKind | str,
vibecomfy/comfy_nodes/agent/contracts.py:2408:    failure_kind = _coerce_failure_kind(kind)
vibecomfy/comfy_nodes/agent/contracts.py:2409:    spec = FAILURE_SPECS[failure_kind]
vibecomfy/comfy_nodes/agent/contracts.py:2412:        kind=failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:2617:    "FailureKind",
vibecomfy/comfy_nodes/agent/_frag_research.py:99:# boundary selectors and hash-only provenance replace the path-bearing
vibecomfy/comfy_nodes/agent/_frag_research.py:100:# selected-slice and provenance blocks, and raw ``candidate_graph`` is never
vibecomfy/comfy_nodes/agent/_frag_research.py:135:    # candidate_graph, provenance paths, or slice paths here.
vibecomfy/comfy_nodes/agent/_frag_research.py:168:    hash-only provenance substitute for the path-bearing provenance and
vibecomfy/comfy_nodes/agent/_frag_research.py:190:            "provenance. When no qualified prior exists (including absent, "
vibecomfy/comfy_nodes/agent/_frag_research.py:210:            "and value as a prior with its provenance and confidence; it is not "
vibecomfy/comfy_nodes/agent/_frag_research.py:222:    # selectors + hash-only provenance replace it.  byte-identical otherwise.
vibecomfy/comfy_nodes/agent/_frag_research.py:289:                "Role-preserving provenance priors (one line per source instance; "
vibecomfy/comfy_nodes/agent/audit.py:401:    failure_kind = None
vibecomfy/comfy_nodes/agent/audit.py:403:        failure_kind = failure.kind.value
vibecomfy/comfy_nodes/agent/audit.py:405:        failure_kind = failure.get("kind") or failure.get("failure_kind")
vibecomfy/comfy_nodes/agent/audit.py:419:        kind=response_dict.get("kind") if response_dict else failure_kind,
vibecomfy/porting/emit/emit_ready.py:42:from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
vibecomfy/porting/emit/emit_ready.py:96:from vibecomfy.porting._provenance_utils import _normalize_provenance_paths
vibecomfy/porting/emit/emit_ready.py:319:            resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
vibecomfy/porting/emit/emit_ready.py:784:            source_provenance=None,
vibecomfy/porting/emit/emit_ready.py:900:    provenance = metadata.get("provenance")
vibecomfy/porting/emit/emit_ready.py:901:    if isinstance(provenance, Mapping):
vibecomfy/porting/emit/emit_ready.py:902:        source = provenance.get("source_workflow") or provenance.get("source_path")
vibecomfy/porting/emit/emit_ready.py:942:    source_provenance: dict[str, Any] | None,
vibecomfy/porting/emit/emit_ready.py:1022:    provenance_part = ""
vibecomfy/porting/emit/emit_ready.py:1023:    if source_provenance is not None:
vibecomfy/porting/emit/emit_ready.py:1024:        provenance_part = f",\n            provenance={_format_value(source_provenance)}"
vibecomfy/porting/emit/emit_ready.py:1051:            f"{provenance_part},\n"
vibecomfy/porting/emit/emit_ready.py:1291:                resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
vibecomfy/porting/emit/emit_ready.py:1574:    provenanced nodes are validated against their pinned schema rather than the
vibecomfy/agent/artifacts.py:32:    "model_attempts.json",
vibecomfy/agent/artifacts.py:336:    model_attempts = report.get("model_attempts")
vibecomfy/agent/artifacts.py:337:    if isinstance(model_attempts, (list, tuple)) and model_attempts:
vibecomfy/agent/artifacts.py:339:            output_dir / "model_attempts.json",
vibecomfy/agent/artifacts.py:340:            {"attempts": _redact(model_attempts)},
vibecomfy/agent/artifacts.py:342:        _append_manifest(manifest, "model_attempts.json")
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:41:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, _product_failure_response, ensure_agent_edit_response_contract, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:47:                FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:804:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, TurnOutcome, _stage_audit, build_legacy_agent_edit_v1, derive_apply_eligibility, derive_gates, product_failure_envelope_fields)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:821:    if failure.kind is FailureKind.STALE_STATE_MISMATCH:
vibecomfy/porting/emit/emit_subgraph.py:537:                source_provenance=None,
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:148:        schema_provenance=_mapping_or_empty(value.get("schema_provenance")),
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:149:        runtime_provenance=_mapping_or_empty(value.get("runtime_provenance")),
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:190:def malformed_execution_plan_evaluation(
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:214:        feedback="plan evaluation blocked: malformed execution plan payload.",
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:215:        schema_provenance=plan.schema_provenance,
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:216:        runtime_provenance=plan.runtime_provenance,
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:232:        evaluation = malformed_execution_plan_evaluation(
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:312:    "malformed_execution_plan_evaluation",
vibecomfy/agent/deepseek_usage.py:16:    "completion_tokens",
vibecomfy/agent/deepseek_usage.py:57:    completion_tokens = normalized["completion_tokens"]
vibecomfy/agent/deepseek_usage.py:60:    if normalized["n_calls"] <= 0 and prompt_tokens <= 0 and completion_tokens <= 0:
vibecomfy/agent/deepseek_usage.py:66:            + (completion_tokens * DEEPSEEK_COMPLETION_USD_PER_1M)
vibecomfy/agent/deepseek_usage.py:71:        + (completion_tokens * DEEPSEEK_COMPLETION_USD_PER_1M)
vibecomfy/comfy_nodes/agent/_frag_chat.py:764:        # Defensively skip malformed entries (non-dict, missing role,
vibecomfy/comfy_nodes/agent/session.py:18:from .contracts import DiagnosticRecord, FailureEnvelope, FailureKind, TurnContext, failure_envelope
vibecomfy/comfy_nodes/agent/session.py:550:            self._quarantine_lock("malformed_metadata")
vibecomfy/comfy_nodes/agent/session.py:1489:        "failure_kind",
vibecomfy/comfy_nodes/agent/session.py:1511:    for field, limit in (("failure_kind", 128), ("failure_message", 2048)):
vibecomfy/comfy_nodes/agent/session.py:1648:    kind: FailureKind,
vibecomfy/comfy_nodes/agent/session.py:1839:        return None, "malformed_candidate_transaction"
vibecomfy/comfy_nodes/agent/session.py:1995:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2006:                kind=FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:2016:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2064:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2080:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2090:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2123:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2147:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2166:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2180:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2270:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2280:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2298:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2334:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2349:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2368:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2379:                kind=FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:2390:                kind=FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:2401:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2411:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2424:                kind=FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:2458:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2501:                        kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2519:                    kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2544:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2559:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2731:                kind=FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:2755:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2764:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2775:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2792:                kind=FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:2828:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2845:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:2875:                kind=FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:3170:def _conflict_kind(scope: OperationScope) -> FailureKind:
vibecomfy/comfy_nodes/agent/session.py:3172:        return FailureKind.STALE_STATE_MISMATCH
vibecomfy/comfy_nodes/agent/session.py:3173:    return FailureKind.EDITOR_AHEAD_CONFLICT
vibecomfy/comfy_nodes/agent/session.py:3505:        reason = "submitted_baseline_snapshot_malformed"
vibecomfy/comfy_nodes/agent/session.py:3683:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:3747:                    FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4251:                        FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4275:                        FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4333:        FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4375:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:4406:                    FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4425:                FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4445:                    FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4460:                    FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4574:            FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4633:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4642:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4650:            FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:4661:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4669:            FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:4710:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:72:    if not isinstance(value, Mapping): raise ContractError(f"{entity} must be an object", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:82:    if not isinstance(graph, Mapping): raise ContractError("graph must be an object", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:109:    if not isinstance(link, Mapping): raise ContractError("link must be an object", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:111:    if not isinstance(source, Mapping) or not isinstance(target, Mapping): raise ContractError("link endpoints are required", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:140:            raise ContractError("link must be a stable endpoint object or native six-tuple", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:144:            raise ContractError("native link endpoint cannot be resolved", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:169:    if not isinstance(raw, Mapping): raise ContractError("widgets_values must be object or list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:179:    if not isinstance(nodes, list): raise ContractError("nodes must be a list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:188:        if not isinstance(links, list): raise ContractError("links must be a list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:191:    if not isinstance(groups, list): raise ContractError("groups must be a list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:739:        raise ContractError("Restoration strategy must be an object", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:746:        raise ContractError("Restoration payload and ref are mutually exclusive", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:748:        raise ContractError("Restoration requires payload or ref", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:750:        raise ContractError("Restoration digest must be hex64", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:754:            raise ContractError("baseline_snapshot_v1 restoration must use ref", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:757:            raise ContractError("baseline_snapshot_v1 ref must be a non-empty string", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:764:        raise ContractError("inverse restoration must use payload", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:775:        raise ContractError("Restoration payload must be an object", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:792:            raise ContractError(f"{tag} payload has extra keys", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:795:            raise ContractError(f"{tag} payload requires ops", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:801:            raise ContractError("mutation_materialization presence parity violated", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:803:            raise ContractError("add_node inverse requires materialization", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:805:            raise ContractError("materialization without add_node inverse", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:815:                raise ContractError("forward_operation_digest must be hex64", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:818:                raise ContractError("prior_link_witnesses must be an array", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:828:                    raise ContractError("prior-link witness must be exactly {from,to} root endpoints", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:831:                    raise ContractError("duplicate prior-link witness destination", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:856:            raise ContractError("inverse_layout_operation_v1 payload has extra keys", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:859:            raise ContractError("inverse_layout_operation_v1 requires layout_operation", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:884:        raise ContractError("restoration_strategy_compensation must be an object", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:887:        raise ContractError("restoration_strategy_compensation has extra keys", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:894:        raise ContractError("compensation ref must be a non-empty string", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:897:        raise ContractError("compensation fence must be an object", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:901:        raise ContractError("compensation fence key set is not closed", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:903:        raise ContractError("compensation generation must be a positive int", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:906:            raise ContractError(f"compensation fence {key} must be non-empty string", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:909:            raise ContractError(f"compensation fence {key} must be hex64", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:1051:            raise ContractError("restoration_strategy_compensation may not be null", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/_frag_humanize.py:16:from vibecomfy.comfy_nodes.agent.contracts import ApplyEligibility, FailureEnvelope, FailureKind, StageResult, TurnContext, TurnOutcome, _ABSENT_FIELD_OLD, _MISSING_FIELD_CHANGE_OLD, _iter_ui_graph_nodes, _ui_node_uid, _ui_node_uid_aliases, _ui_widget_value_for_field
vibecomfy/comfy_nodes/agent/_frag_humanize.py:926:        if state.batch_exit_mode == _BATCH_EXIT_BUDGET or failure.kind is FailureKind.BATCH_BUDGET_EXHAUSTED:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:946:        if fallback_reason in {"provider_failure", "malformed_response", "timeout"}:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1107:            fallback_reason = "malformed_response"
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1171:        if failure.kind is FailureKind.STALE_STATE_MISMATCH:
vibecomfy/comfy_nodes/__init__.py:380:                "passthrough_on_non_json": ("BOOLEAN", {"default": False}),
vibecomfy/comfy_nodes/__init__.py:462:            "redaction_policy", "policy_version", "passthrough_on_non_json",
vibecomfy/comfy_nodes/agent/_frag_revision.py:109:        or topology.missing_required_inputs
vibecomfy/comfy_nodes/agent/_frag_revision.py:133:        or topology.missing_required_inputs
vibecomfy/comfy_nodes/agent/_frag_revision.py:212:        missing_required_inputs=_subtract_existing_blockers(
vibecomfy/comfy_nodes/agent/_frag_revision.py:213:            candidate_topology.missing_required_inputs,
vibecomfy/comfy_nodes/agent/_frag_revision.py:214:            topology.missing_required_inputs,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:14:from vibecomfy.comfy_nodes.agent.contracts import FailureKind, StageResult, TurnContext
vibecomfy/comfy_nodes/agent/_frag_ingest.py:73:        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:130:            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
vibecomfy/comfy_nodes/agent/_frag_ingest.py:178:            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
vibecomfy/comfy_nodes/agent/_frag_ingest.py:384:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:32:def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:56:    return "malformed"
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:63:    from vibecomfy.comfy_nodes.agent.edit import (_BATCH_PROTOCOL_RETRY_PROMPT, _malformed_model_json_detail)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:66:        detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:165:    Only ID-free selectors and hash-only provenance fields are carried.  No
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:221:        # A malformed node entry means we cannot guarantee completeness.
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:941:    "_malformed_model_json_detail",
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:15:from vibecomfy.comfy_nodes.agent.contracts import FailureKind
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:550:    failure_kind: FailureKind,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:569:    hard_refusal = bool(hard_codes) or failure_kind is FailureKind.UNREPRESENTABLE
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:589:        "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:600:def _batch_budget_failure_kind(turns: list[dict[str, Any]]) -> FailureKind:
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:609:        FailureKind.MODEL_MISTAKE: 0,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:610:        FailureKind.UNREPRESENTABLE: 0,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:611:        FailureKind.SCHEMA_GAP: 0,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:614:        turn_categories: set[FailureKind] = set()
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:622:                turn_categories.add(FailureKind.SCHEMA_GAP)
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:625:                turn_categories.add(FailureKind.UNREPRESENTABLE)
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:627:            turn_categories.add(FailureKind.MODEL_MISTAKE)
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:632:        key=lambda item: (item[1], item[0] == FailureKind.SCHEMA_GAP, item[0] == FailureKind.UNREPRESENTABLE),
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:637:    return FailureKind.MODEL_MISTAKE
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:645:     "_batch_budget_artifixer_report", "_batch_budget_failure_kind",
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:27:    from vibecomfy.comfy_nodes.agent.edit import (AgentEditState, FailureKind, PROMPT_MEMORY_MESSAGES, StageResult, _SESSION_ROOT, _StageBlocked, _agent_edit_contract, _build_batch_repl_response, _build_dev_success_response, _canonical_agent_edit_route, _conversation_with_candidate_reference, _default_runtime_schema_provider, _failure_response, _hydrate_execution_plan_from_protocol_notes, _product_failure_response, _record, _run_batch_repl_product_path, _run_delta_dev_path, _run_full_dev_path, _safe_session_id, _stage_audit, _validated_agent_edit_response, _write_turn_chat_artifact, _write_unknown_transition_audits, allocate_turn, classify_failure, failure_envelope, initialize_gates, read_session_chat, record_idempotent_response, write_allocation_failure_audit)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:33:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:43:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:50:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:79:            FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:280:                FailureKind.AUDIT_WRITE_FAILURE,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:436:            FailureKind.AUDIT_WRITE_FAILURE,
vibecomfy/porting/emit/ui.py:707:def _get_node_schema_provenance(
vibecomfy/porting/emit/ui.py:711:    """Return a provenance dict describing how the schema was sourced."""
vibecomfy/porting/emit/ui.py:1070:    return bool(metadata.get("provenance"))
vibecomfy/porting/emit/ui.py:1878:    provenance = _get_node_schema_provenance(node.class_type, schema)
vibecomfy/porting/emit/ui.py:1942:    if schema_widget_count is not None and not provenance["schema_less"]:
vibecomfy/porting/emit/ui.py:1984:        schema_less=bool(provenance["schema_less"]),
vibecomfy/porting/emit/ui.py:1985:        confidence=provenance.get("confidence"),
vibecomfy/porting/emit/ui.py:1997:        provider=provenance.get("provider"),
vibecomfy/porting/emit/ui.py:2048:        recovery_report: Optional mutable list.  If provided, one provenance dict
vibecomfy/porting/emit/ui.py:2245:    # Per-node provenance (keyed by node_id)
vibecomfy/porting/emit/ui.py:2250:        prov = _get_node_schema_provenance(ct, schema)
vibecomfy/porting/emit/ui.py:2499:                pass  # appended after the loop; diagnostic is in the provenance entry
vibecomfy/porting/parity.py:102:    # 2. Shared resolver fallback. This uses the same provenance ladder as
vibecomfy/porting/parity.py:105:        from vibecomfy.porting.widgets.aliases import resolve_widget_name_with_provenance
vibecomfy/porting/parity.py:108:    return resolve_widget_name_with_provenance(class_type, idx).name
vibecomfy/comfy_nodes/agent/candidate_transaction.py:194:    provenance_fields = (
vibecomfy/comfy_nodes/agent/candidate_transaction.py:228:        "provenance": {
vibecomfy/comfy_nodes/agent/candidate_transaction.py:230:            for field in provenance_fields
vibecomfy/comfy_nodes/agent/candidate_transaction.py:279:        return False, "malformed_schema_witness"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:281:        return False, "malformed_schema_provider_mode"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:334:            provenance = raw.get("provenance")
vibecomfy/comfy_nodes/agent/candidate_transaction.py:335:            provenance = provenance if isinstance(provenance, Mapping) else {}
vibecomfy/comfy_nodes/agent/candidate_transaction.py:341:                source_provider=str(provenance.get("source_provider") or "persisted_witness"),
vibecomfy/comfy_nodes/agent/candidate_transaction.py:342:                source_path=provenance.get("source_path") if isinstance(provenance.get("source_path"), str) else None,
vibecomfy/comfy_nodes/agent/candidate_transaction.py:343:                source_cache_path=provenance.get("source_cache_path") if isinstance(provenance.get("source_cache_path"), str) else None,
vibecomfy/comfy_nodes/agent/candidate_transaction.py:345:                source_package=provenance.get("source_package") if isinstance(provenance.get("source_package"), str) else None,
vibecomfy/comfy_nodes/agent/candidate_transaction.py:346:                source_version=provenance.get("source_version") if isinstance(provenance.get("source_version"), str) else None,
vibecomfy/comfy_nodes/agent/candidate_transaction.py:347:                source_hash=provenance.get("source_hash") if isinstance(provenance.get("source_hash"), str) else None,
vibecomfy/comfy_nodes/agent/candidate_transaction.py:348:                confidence=float(provenance.get("confidence", 1.0)) if isinstance(provenance.get("confidence"), (int, float)) else 1.0,
vibecomfy/comfy_nodes/agent/candidate_transaction.py:349:                conflicts=tuple(str(item) for item in provenance.get("conflicts", []) if isinstance(item, str)),
vibecomfy/comfy_nodes/agent/candidate_transaction.py:350:                ignored_evidence=tuple(str(item) for item in provenance.get("ignored_evidence", []) if isinstance(item, str)),
vibecomfy/comfy_nodes/agent/candidate_transaction.py:373:def schema_provenance_summary(witness: Mapping[str, Any]) -> dict[str, Any]:
vibecomfy/comfy_nodes/agent/candidate_transaction.py:378:            provenance = raw.get("provenance") if isinstance(raw, Mapping) else None
vibecomfy/comfy_nodes/agent/candidate_transaction.py:379:            source = provenance.get("source_provider") if isinstance(provenance, Mapping) else None
vibecomfy/comfy_nodes/agent/candidate_transaction.py:531:            "schema_provenance": schema_provenance_summary(schema_witness),
vibecomfy/comfy_nodes/agent/candidate_transaction.py:666:        return False, "malformed_candidate_transaction"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:697:            return False, "malformed_layout_verification_contract"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:715:        return False, "malformed_candidate_transaction_actions"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:765:    "schema_provenance_summary",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:94:            "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:101:                "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:111:            "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:118:            "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:125:            "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:131:            "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:146:                "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:152:                "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:165:                "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:184:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:255:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:261:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:295:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:300:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:307:                "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:382:                        "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:388:                    "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:33:from .contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:131:            # malformed ops (unknown op kind, missing required fields,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:139:        # Envelope present but ops is malformed — fall through to delta_ops.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:257:            # malformed entries (unknown op kind, missing required fields,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:258:            # etc.) are classified as malformed rather than canonical.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:264:                    "code": "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:277:            "code": "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:816:    # scope_path.  If none are present the op is malformed.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1097:        FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1124:        distinct buckets: *malformed_delta*, *legacy_delta_shape*,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1157:    # malformed shapes in distinct evidence buckets.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1191:        elif diag_code == "canonical_envelope_malformed_ops":
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1192:            diag_code = "malformed_delta"
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1195:                "is malformed."
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:101:            "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:110:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:126:        raise _fail("layout op must be an object", "malformed_layout_op")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:131:            "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:145:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:160:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:169:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:176:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:192:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:200:                "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:210:                    "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:219:                    "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:230:            "malformed_layout_op",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:246:        raise _fail("layout ops must be an array", "malformed_layout_operation")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:289:            "malformed_layout_operation",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:295:            "malformed_layout_operation",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:334:        raise _fail("layout operation envelope must be an object", "malformed_layout_operation")
vibecomfy/porting/readability_inventory.py:57:    missing_source_provenance: bool = True
vibecomfy/porting/readability_inventory.py:97:                    "missing_source_provenance": e.missing_source_provenance,
vibecomfy/porting/readability_inventory.py:430:        # Missing source provenance: no source_workflow and not manual/reference
vibecomfy/porting/readability_inventory.py:446:            missing_source_provenance=missing_source,
vibecomfy/porting/readability_inventory.py:464:    summary["missing_source_provenance"] = summary_missing_source
vibecomfy/comfy_nodes/agent/graph_normalization.py:37:    The conversion is whole-graph and fail-closed: malformed or mixed mapping
vibecomfy/comfy_nodes/agent/runtime.py:51:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/runtime.py:52:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/runtime.py:68:# extra attempts. Timeouts, capacity/provider errors, and malformed content do
vibecomfy/comfy_nodes/agent/runtime.py:78:    "vibecomfy_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:117:def begin_model_attempt_capture() -> contextvars.Token:
vibecomfy/comfy_nodes/agent/runtime.py:121:def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
vibecomfy/comfy_nodes/agent/runtime.py:122:    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())
vibecomfy/comfy_nodes/agent/runtime.py:125:def end_model_attempt_capture(token: contextvars.Token) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:129:def record_model_attempts(value: Any) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:134:    for attempt in coerce_model_attempts(value):
vibecomfy/comfy_nodes/agent/runtime.py:140:def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:143:    normalized = coerce_model_attempts([value])
vibecomfy/comfy_nodes/agent/runtime.py:474:        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
vibecomfy/comfy_nodes/agent/runtime.py:478:            resolved_model = _normalize_native_deepseek_model(resolved_model)
vibecomfy/comfy_nodes/agent/runtime.py:480:            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
vibecomfy/comfy_nodes/agent/runtime.py:482:            model=resolved_model,
vibecomfy/comfy_nodes/agent/runtime.py:495:    attempts = coerce_model_attempts(result.get("model_attempts"))
vibecomfy/comfy_nodes/agent/runtime.py:502:        and latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/runtime.py:504:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/runtime.py:523:def _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:527:    requested_model: str | None,
vibecomfy/comfy_nodes/agent/runtime.py:528:    resolved_model: str | None,
vibecomfy/comfy_nodes/agent/runtime.py:535:    return ModelAttemptEvidence(
vibecomfy/comfy_nodes/agent/runtime.py:540:        requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:541:        resolved_model=resolved_model or agent_kwargs.get("model"),
vibecomfy/comfy_nodes/agent/runtime.py:557:    requested_model: str | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:564:    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
vibecomfy/comfy_nodes/agent/runtime.py:565:    provider/capacity errors, and malformed non-empty content surface immediately.
vibecomfy/comfy_nodes/agent/runtime.py:580:                requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:585:            timeout_attempt = _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:588:                requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:589:                resolved_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:594:            record_model_attempts([timeout_attempt])
vibecomfy/comfy_nodes/agent/runtime.py:595:            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/runtime.py:597:        attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/comfy_nodes/agent/runtime.py:600:            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
vibecomfy/comfy_nodes/agent/runtime.py:602:            record_model_attempts([normalized])
vibecomfy/comfy_nodes/agent/runtime.py:604:            result["model_attempts"] = list(accumulated_attempts)
vibecomfy/comfy_nodes/agent/runtime.py:629:    requested_model: str | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:649:                    "requested_model": requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:761:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:805:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:843:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:1185:            requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:1200:    "end_deepseek_usage_capture", "begin_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1201:    "snapshot_model_attempt_capture", "end_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1202:    "record_model_attempts", "replace_last_model_attempt",
vibecomfy/comfy_nodes/agent/worker.py:69:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/worker.py:106:def _model_attempt_failure_type(exc: BaseException, raw_text: str | None) -> str:
vibecomfy/comfy_nodes/agent/worker.py:109:        return "empty_response"
vibecomfy/comfy_nodes/agent/worker.py:113:        return "malformed_json" if "{" in (raw_text or "") else "non_json_content"
vibecomfy/comfy_nodes/agent/worker.py:116:        return "non_json_content"
vibecomfy/comfy_nodes/agent/worker.py:119:            return "missing_required_fields"
vibecomfy/comfy_nodes/agent/worker.py:120:        return "malformed_json"
vibecomfy/comfy_nodes/agent/worker.py:143:def _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:160:            "prompt_tokens", "completion_tokens", "total_tokens"
vibecomfy/comfy_nodes/agent/worker.py:165:    return ModelAttemptEvidence(
vibecomfy/comfy_nodes/agent/worker.py:167:        attempt=profiling_context.get("model_attempt") or 1,
vibecomfy/comfy_nodes/agent/worker.py:170:        requested_model=request.get("requested_model"),
vibecomfy/comfy_nodes/agent/worker.py:171:        resolved_model=agent_kwargs.get("model") or request.get("model"),
vibecomfy/comfy_nodes/agent/worker.py:202:    failure_type = _model_attempt_failure_type(exc, raw_text)
vibecomfy/comfy_nodes/agent/worker.py:207:        "empty_response": "empty",
vibecomfy/comfy_nodes/agent/worker.py:208:        "missing_required_fields": "missing_content",
vibecomfy/comfy_nodes/agent/worker.py:226:            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
vibecomfy/comfy_nodes/agent/worker.py:230:    out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:231:        _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:281:        resolved_model=model,
vibecomfy/comfy_nodes/agent/worker.py:369:            completion_tokens = _usage_int(raw_usage, "completion_tokens")
vibecomfy/comfy_nodes/agent/worker.py:373:            if completion_tokens is None:
vibecomfy/comfy_nodes/agent/worker.py:374:                completion_tokens = max(0, int(getattr(canonical_usage, "output_tokens", 0) or 0))
vibecomfy/comfy_nodes/agent/worker.py:376:                total_tokens = prompt_tokens + completion_tokens
vibecomfy/comfy_nodes/agent/worker.py:397:                    "completion_tokens": completion_tokens,
vibecomfy/comfy_nodes/agent/worker.py:459:                    "completion_tokens": last_result.get("completion_tokens"),
vibecomfy/comfy_nodes/agent/worker.py:595:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:596:                _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:625:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:626:                _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:631:                    failure_type=_model_attempt_failure_type(exc, raw_text),
vibecomfy/commands/analyze.py:14:from vibecomfy.security import provenance as _provenance
vibecomfy/commands/analyze.py:354:    naming the sentinel marker plus a ``provenance_summary`` of per-tag counts,
vibecomfy/commands/analyze.py:362:        tag = _provenance.read(node)
vibecomfy/commands/analyze.py:369:            "provenance": tag,
vibecomfy/commands/analyze.py:374:        "provenance_summary": dict(sorted(summary.items())),
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:28:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, StageResult, _StageBlocked, _classify_stage_failure, _is_provider_exception, _record, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:49:        failure_kind = None
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:51:            failure_kind = result.value.get("failure_kind")
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:84:            failure_kind or FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:108:        if failure.kind is FailureKind.STALE_STATE_MISMATCH and public_stage in {"ingest", "ingest_v2"}:
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:135:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, classify_failure, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:137:    if stage in {"ingest", "ingest_v2"} and failure.kind is FailureKind.UNSUPPORTED_NON_DAG:
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:141:                FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/provider.py:16:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/provider.py:17:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/provider.py:207:    "model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:211:    "completion_tokens",
vibecomfy/comfy_nodes/agent/provider.py:228:    attempts = coerce_model_attempts(response.get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:230:        merged["model_attempts"] = [dict(item) for item in attempts]
vibecomfy/comfy_nodes/agent/provider.py:1382:        return "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1385:        return "missing_required_fields"
vibecomfy/comfy_nodes/agent/provider.py:1386:    return "malformed_json"
vibecomfy/comfy_nodes/agent/provider.py:1395:    attempts = list(coerce_model_attempts(response.get("model_attempts")))
vibecomfy/comfy_nodes/agent/provider.py:1404:    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
vibecomfy/comfy_nodes/agent/provider.py:1407:        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
vibecomfy/comfy_nodes/agent/provider.py:1409:        replace_last_model_attempt(revised)
vibecomfy/comfy_nodes/agent/provider.py:1412:    exc.model_attempts = list(attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/provider.py:1422:        latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1424:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/provider.py:1500:                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:1504:                metadata["model_attempts"] = [*attempt_log, *current_attempts]
vibecomfy/porting/reorganise/parse.py:335:            "missing_required_field",
vibecomfy/comfy_nodes/agent/_frag_state.py:41:    FailureKind,
vibecomfy/comfy_nodes/agent/_frag_state.py:332:def _inject_lowering_provenance(state: AgentEditState) -> None:
vibecomfy/comfy_nodes/agent/_frag_state.py:512:     "FailureEnvelope", "FailureKind", "FieldChange", "LOGGER", "MalformedModelJSON",
vibecomfy/comfy_nodes/agent/_frag_state.py:525:     "_hydrate_execution_plan_from_protocol_notes", "_inject_lowering_provenance",
vibecomfy/comfy_nodes/agent/diagnostics.py:17:from .contracts import FailureKind, StageResult
vibecomfy/comfy_nodes/agent/diagnostics.py:21:        "missing_required_input",
vibecomfy/comfy_nodes/agent/diagnostics.py:39:    failure_kind: FailureKind | None
vibecomfy/comfy_nodes/agent/diagnostics.py:47:    failure_kind: FailureKind | None
vibecomfy/comfy_nodes/agent/diagnostics.py:101:def classify_validation_issues(issues: tuple[dict[str, Any], ...]) -> FailureKind | None:
vibecomfy/comfy_nodes/agent/diagnostics.py:107:        return FailureKind.UNSUPPORTED_NON_DAG
vibecomfy/comfy_nodes/agent/diagnostics.py:109:        return FailureKind.VALIDATION_ERROR
vibecomfy/comfy_nodes/agent/diagnostics.py:111:        return FailureKind.UNSATISFIED_INPUT_ERROR
vibecomfy/comfy_nodes/agent/diagnostics.py:112:    return FailureKind.VALIDATION_ERROR
vibecomfy/comfy_nodes/agent/diagnostics.py:120:    failure_kind: FailureKind,
vibecomfy/comfy_nodes/agent/diagnostics.py:128:        "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/diagnostics.py:185:def classify_queue_issues(issues: tuple[dict[str, Any], ...]) -> FailureKind | None:
vibecomfy/comfy_nodes/agent/diagnostics.py:187:        raw_kind = issue.get("failure_kind")
vibecomfy/comfy_nodes/agent/diagnostics.py:189:            return FailureKind(raw_kind)
vibecomfy/comfy_nodes/agent/diagnostics.py:223:    failure_kind = classify_validation_issues(deduped)
vibecomfy/comfy_nodes/agent/diagnostics.py:225:        ok=failure_kind is None,
vibecomfy/comfy_nodes/agent/diagnostics.py:226:        blocking=failure_kind is not None,
vibecomfy/comfy_nodes/agent/diagnostics.py:227:        failure_kind=failure_kind,
vibecomfy/comfy_nodes/agent/diagnostics.py:243:            "failure_kind": diagnostics.failure_kind.value
vibecomfy/comfy_nodes/agent/diagnostics.py:244:            if diagnostics.failure_kind is not None
vibecomfy/comfy_nodes/agent/diagnostics.py:259:                "failure_kind": None,
vibecomfy/comfy_nodes/agent/diagnostics.py:270:            "failure_kind": FailureKind.LOWERING_FAILURE.value,
vibecomfy/comfy_nodes/agent/diagnostics.py:325:                    failure_kind=FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER,
vibecomfy/comfy_nodes/agent/diagnostics.py:351:                    failure_kind=FailureKind.SCHEMA_LESS_QUEUE_BLOCKER,
vibecomfy/comfy_nodes/agent/diagnostics.py:369:                    failure_kind=FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER,
vibecomfy/comfy_nodes/agent/diagnostics.py:387:                    failure_kind=FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER,
vibecomfy/comfy_nodes/agent/diagnostics.py:398:                failure_kind=FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER,
vibecomfy/comfy_nodes/agent/diagnostics.py:406:        failure_kind=classify_queue_issues(deduped),
vibecomfy/comfy_nodes/agent/diagnostics.py:425:            "failure_kind": diagnostics.failure_kind.value
vibecomfy/comfy_nodes/agent/diagnostics.py:426:            if diagnostics.failure_kind is not None
vibecomfy/commands/port/_inventory.py:27:    flag_count = sum(1 for e in entries if e.missing_source_provenance)
vibecomfy/commands/port/_inventory.py:31:        f"missing source provenance: {flag_count}",
vibecomfy/commands/port/_inventory.py:58:    flagged = [e for e in entries if e.missing_source_provenance]
vibecomfy/commands/port/_inventory.py:61:        lines.append("Flagged (no source provenance):")
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:159:    entry?.failure_kind
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:161:    || outcome?.failure_kind
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:590:    "  - response.json: the final outcome envelope (failure_kind, user_facing_message).",
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:623:          failure_kind: turnEntry.failure_kind || null,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:710:      failure_kind: panel.state.failure.kind,
vibecomfy/porting/reorganise/compile.py:4168:    over_capacity = len(cleaned) > max_columns
vibecomfy/porting/reorganise/compile.py:4178:    if not over_capacity and not imbalanced and not single_tall_column:
vibecomfy/comfy_nodes/web/agent_status_poller.js:13:  MALFORMED: "malformed_status",
vibecomfy/comfy_nodes/web/agent_status_poller.js:297:      issue: "malformed_status",
vibecomfy/comfy_nodes/web/agent_status_poller.js:672:      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", error);
vibecomfy/comfy_nodes/web/agent_status_poller.js:707:    if (projected.issue === "malformed_status") {
vibecomfy/comfy_nodes/web/agent_status_poller.js:708:      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", status);
vibecomfy/comfy_nodes/web/agent_status_poller.js:832:        kind: "malformed",
vibecomfy/comfy_nodes/web/agent_status_poller.js:854:        kind: "malformed",
vibecomfy/commands/port/_export.py:91:    warn-and-emit path.  It records per-node provenance for schema-less nodes,
vibecomfy/commands/port/_shared.py:207:                ready_id=(report.workflow_id or (report.provenance or {}).get("indexed_id")),
vibecomfy/commands/port/_shared.py:208:                source_path=(report.provenance or {}).get("source_path"),
vibecomfy/comfy_nodes/web/panel_composer.js:98:      // Ignore malformed debug-only stage data in the composer summary.
vibecomfy/comfy_nodes/web/panel_composer.js:191:      message: "Submit is disabled because /vibecomfy/agent/status returned a malformed payload.",
vibecomfy/comfy_nodes/web/panel_composer.js:842:      guidanceNode.textContent = "The backend status payload is malformed. Fix /vibecomfy/agent/status and retry.";
vibecomfy/commands/port/_convert.py:82:            provenance=report.provenance,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:60:  function rollbackFailureKind(value) {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:63:      : typeof value?.failure_kind === "string" && value.failure_kind
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:64:        ? value.failure_kind
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:286:      ...(rollbackFailureKind(triggerFailure)
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:287:        ? { failure_kind: rollbackFailureKind(triggerFailure).slice(0, 128) }
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:602:        failure_kind: failure.kind || "RejectError",
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:758:            failure_kind: failure.kind || null,
vibecomfy/executor/revision_evidence.py:212:    missing_required_inputs: list[dict[str, Any]] = []
vibecomfy/executor/revision_evidence.py:237:                    missing_required_inputs.append({
vibecomfy/executor/revision_evidence.py:263:    if missing_required_inputs:
vibecomfy/executor/revision_evidence.py:265:            f"{len(missing_required_inputs)} missing required input(s)"
vibecomfy/executor/revision_evidence.py:278:        missing_required_inputs=tuple(missing_required_inputs),
vibecomfy/executor/revision_evidence.py:495:            candidate_topology.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:496:            original_topology.missing_required_inputs if original_topology is not None else (),
vibecomfy/executor/revision_evidence.py:1341:            if topology.missing_required_inputs:
vibecomfy/executor/revision_evidence.py:1372:                facts.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:1395:        missing_required_inputs=facts.missing_required_inputs,
vibecomfy/commands/validate.py:188:            if kw.arg in {"source_workflow", "provenance"}:
vibecomfy/executor/contracts.py:37:    "empty_response",
vibecomfy/executor/contracts.py:38:    "malformed_json",
vibecomfy/executor/contracts.py:39:    "non_json_content",
vibecomfy/executor/contracts.py:40:    "missing_required_fields",
vibecomfy/executor/contracts.py:60:    provenance and can contain credentials, so they are discarded wholesale.
vibecomfy/executor/contracts.py:103:def _model_attempt_text(value: Any) -> str:
vibecomfy/executor/contracts.py:109:def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
vibecomfy/executor/contracts.py:112:    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
vibecomfy/executor/contracts.py:123:class ModelAttemptEvidence:
vibecomfy/executor/contracts.py:135:    requested_model: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:136:    resolved_model: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:152:        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
vibecomfy/executor/contracts.py:157:            "requested_model", "resolved_model", "adapter", "provider",
vibecomfy/executor/contracts.py:160:            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
vibecomfy/executor/contracts.py:165:            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
vibecomfy/executor/contracts.py:175:    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
vibecomfy/executor/contracts.py:181:            requested_model=value.get("requested_model", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:182:            resolved_model=value.get("resolved_model", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:198:            "requested_model": self.requested_model,
vibecomfy/executor/contracts.py:199:            "resolved_model": self.resolved_model,
vibecomfy/executor/contracts.py:212:def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/contracts.py:218:        if isinstance(item, ModelAttemptEvidence):
vibecomfy/executor/contracts.py:221:            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
vibecomfy/executor/contracts.py:1348:    # source provenance — content hash + retrieval rank + tier ONLY (no path/filename)
vibecomfy/executor/contracts.py:1767:    missing_required_inputs: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:1780:        object.__setattr__(self, "missing_required_inputs", tuple(
vibecomfy/executor/contracts.py:1783:            for item in self.missing_required_inputs
vibecomfy/executor/contracts.py:1795:            or self.missing_required_inputs
vibecomfy/executor/contracts.py:1805:            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
vibecomfy/executor/contracts.py:1992:                or self.topology.missing_required_inputs
vibecomfy/executor/contracts.py:2032:    missing_required_inputs: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:2052:        object.__setattr__(self, "missing_required_inputs", tuple(
vibecomfy/executor/contracts.py:2055:            for item in self.missing_required_inputs
vibecomfy/executor/contracts.py:2084:            missing_required_inputs=topology.missing_required_inputs,
vibecomfy/executor/contracts.py:2097:            or self.missing_required_inputs
vibecomfy/executor/contracts.py:2110:            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
vibecomfy/executor/contracts.py:2304:    model_attempts: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:2322:            "model_attempts",
vibecomfy/executor/contracts.py:2323:            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
vibecomfy/executor/contracts.py:2354:        inner["model_attempts"] = [
vibecomfy/executor/contracts.py:2355:            _thaw_jsonish(item) for item in self.model_attempts
vibecomfy/executor/contracts.py:2551:    if result.failure_kind is not None:
vibecomfy/executor/contracts.py:2603:    failure_kind: str | None = None
vibecomfy/executor/contracts.py:2618:        payload["model_attempts"] = [
vibecomfy/executor/contracts.py:2619:            _thaw_jsonish(item) for item in self.report.model_attempts
vibecomfy/executor/contracts.py:2641:        if self.failure_kind is not None:
vibecomfy/executor/contracts.py:2642:            payload["failure_kind"] = self.failure_kind
vibecomfy/executor/contracts.py:2671:            failure_kind=kind,
vibecomfy/executor/contracts.py:2701:    "ModelAttemptEvidence",
vibecomfy/executor/contracts.py:2708:    "coerce_model_attempts",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:386://   kind: FailureKind — see agent_contracts.py FailureKind enum:
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:410:// matching FailureKind.
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4843:    failure_kind: extra.failure_kind || null,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5746:    failure_kind: kind,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6348:  // lowered entries from static lowering provenance
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8416:        failure_kind: failure.kind,
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:38:    || entry?.failure_kind
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:106:    failure_kind: event.failure_kind || null,
vibecomfy/executor/prompts.py:9:Both phases use strict JSON contracts with small parsers so malformed model
vibecomfy/executor/prompts.py:344:            # Defensively skip any malformed entries (non-dict, missing
vibecomfy/comfy_nodes/web/projection_registry_v1.js:285:      error.code = "malformed_link";
vibecomfy/porting/widget_shape_fence.py:111:    malformed_new_raw_ui = (
vibecomfy/porting/widget_shape_fence.py:116:        # ingest) is only "malformed" if it actually has a widget-shape problem
vibecomfy/porting/widget_shape_fence.py:125:    if malformed_new_raw_ui:
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:42:  "failure_kind",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:109:  "malformed_delta",
vibecomfy/executor/core.py:22:    FailureKind,
vibecomfy/executor/core.py:35:    begin_model_attempt_capture,
vibecomfy/executor/core.py:37:    end_model_attempt_capture,
vibecomfy/executor/core.py:39:    snapshot_model_attempt_capture,
vibecomfy/executor/core.py:113:    "model_attempts",
vibecomfy/executor/core.py:117:    "completion_tokens",
vibecomfy/executor/core.py:127:_PARSE_REASON_MALFORMED_JSON = "malformed_json"
vibecomfy/executor/core.py:128:_PARSE_REASON_NON_JSON_CONTENT = "non_json_content"
vibecomfy/executor/core.py:146:    if "not an object" in message or "non_json" in message:
vibecomfy/executor/core.py:187:                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
vibecomfy/executor/core.py:228:    attempts = context.get("model_attempts")
vibecomfy/executor/core.py:437:def _graph_has_provenance_breadcrumb(graph: Mapping[str, Any] | None) -> bool:
vibecomfy/executor/core.py:487:    """Return iterable uncertainty reasons that permit provenance research."""
vibecomfy/executor/core.py:488:    if not _graph_has_provenance_breadcrumb(request.graph):
vibecomfy/executor/core.py:523:    Revise route: prefetches only when provenance exists and the named
vibecomfy/executor/core.py:631:    Defensively tolerates malformed historical chat artifacts (non-dict
vibecomfy/executor/core.py:1093:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1105:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1243:        "provenance": {
vibecomfy/executor/core.py:1372:            provenance_slices = [
vibecomfy/executor/core.py:1377:            if provenance_slices:
vibecomfy/executor/core.py:1380:                protocol_notes["precedent_slices"] = provenance_slices
vibecomfy/executor/core.py:1381:                payload["precedent_slices"] = provenance_slices
vibecomfy/executor/core.py:1499:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1506:            FailureKind.VALIDATION_ERROR,
vibecomfy/executor/core.py:1514:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1520:    if result.get("ok") is False or "failure_kind" in result:
vibecomfy/executor/core.py:1521:        fk = result.get("failure_kind", result.get("kind", "ValidationError"))
vibecomfy/executor/core.py:1525:            "failure_kind": fk,
vibecomfy/executor/core.py:1540:            FailureKind(fk) if isinstance(fk, str) and fk in {k.value for k in FailureKind} else FailureKind.VALIDATION_ERROR,
vibecomfy/executor/core.py:1547:                    if key not in {"message", "stage", "failure_kind"}
vibecomfy/executor/core.py:1553:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1802:            FailureKind.VALIDATION_ERROR,
vibecomfy/executor/core.py:1810:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1822:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1834:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1855:        failure_kind: str,
vibecomfy/executor/core.py:1863:        self.failure_kind = failure_kind
vibecomfy/executor/core.py:1979:    attempt_token = begin_model_attempt_capture()
vibecomfy/executor/core.py:1990:        model_attempts = snapshot_model_attempt_capture()
vibecomfy/executor/core.py:1991:        if not model_attempts and isinstance(model_response, Mapping):
vibecomfy/executor/core.py:1994:                model_attempts = tuple(
vibecomfy/executor/core.py:2009:            model_attempts=model_attempts,
vibecomfy/executor/core.py:2015:        end_model_attempt_capture(attempt_token)
vibecomfy/executor/core.py:2134:            kind=exc.failure_kind,
vibecomfy/executor/core.py:2294:                "failure_kind": exc.failure_kind,
vibecomfy/executor/core.py:2320:                kind=exc.failure_kind,
vibecomfy/executor/core.py:2430:                exc.failure_kind,
vibecomfy/executor/core.py:2455:            kind=exc.failure_kind,
vibecomfy/executor/agent_backend.py:27:from .contracts import ClassifyDecision, ModelAttemptEvidence, coerce_model_attempts
vibecomfy/executor/agent_backend.py:80:        if result is not None and getattr(exc, "model_attempts", None) is None:
vibecomfy/executor/agent_backend.py:81:            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:93:        return "empty_response"
vibecomfy/executor/agent_backend.py:101:        return "malformed_json" if "{" in stripped else "non_json_content"
vibecomfy/executor/agent_backend.py:102:    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"
vibecomfy/executor/agent_backend.py:106:    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
vibecomfy/executor/agent_backend.py:108:    record_model_attempts(result.get("model_attempts"))
vibecomfy/executor/agent_backend.py:114:    attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/executor/agent_backend.py:123:    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
vibecomfy/executor/agent_backend.py:125:    result["model_attempts"] = attempts
vibecomfy/executor/agent_backend.py:126:    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
vibecomfy/executor/agent_backend.py:128:    replace_last_model_attempt(revised)
vibecomfy/porting/edit/lint.py:23:- **issues** (typed errors for unknown targets / fields / malformed ops)
vibecomfy/porting/edit/lint.py:150:    malformed ops are rejected).  ``normalizations`` records the disposition
vibecomfy/porting/edit/lint.py:1117:        "malformed_op",
vibecomfy/porting/edit/apply_resolve_base.py:381:        provenance_label = ""
vibecomfy/porting/edit/apply_resolve_base.py:385:            provenance_label = "existing_bound_value"
vibecomfy/porting/edit/apply_resolve_base.py:389:            provenance_label = "user"
vibecomfy/porting/edit/apply_resolve_base.py:402:                provenance_label = "schema_default"
vibecomfy/porting/edit/apply_resolve_base.py:432:            provenance=provenance_label,
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:489:      // failure → treat as a malformed terminal. The orchestrator may pass an
vibecomfy/origin.py:13:    """Record authoring-boundary provenance on ``workflow.metadata``.
vibecomfy/porting/wrappers/codegen.py:137:    provenance = _provenance_line(specs)
vibecomfy/porting/wrappers/codegen.py:138:    source_input = _provenance_fingerprint_input(pack_slug, specs)
vibecomfy/porting/wrappers/codegen.py:143:        provenance=provenance,
vibecomfy/porting/wrappers/codegen.py:199:    provenance: str,
vibecomfy/porting/wrappers/codegen.py:208:        f"# source: {provenance}",
vibecomfy/porting/wrappers/codegen.py:257:    lines.append(f"        Source: {spec.source_provenance}")
vibecomfy/porting/wrappers/codegen.py:456:def _provenance_line(specs: Sequence[ClassSpec]) -> str:
vibecomfy/porting/wrappers/codegen.py:459:    unique = sorted({spec.source_provenance for spec in specs})
vibecomfy/porting/wrappers/codegen.py:463:def _provenance_fingerprint_input(pack_slug: str, specs: Sequence[ClassSpec]) -> str:
vibecomfy/porting/wrappers/codegen.py:522:        provenance = spec.source_provenance.replace('"', '\\"')
vibecomfy/porting/wrappers/codegen.py:523:        lines.append(f"    # source: {provenance}")
vibecomfy/workflow.py:60:    provenance: dict[str, Any] = field(default_factory=dict)
vibecomfy/workflow.py:94:    def provenance(self) -> str:
vibecomfy/workflow.py:95:        """Read-through to the S4 provenance tag; fail-closed on missing/None."""
vibecomfy/workflow.py:96:        from vibecomfy.security import provenance as _prov
vibecomfy/workflow.py:216:        """Promote ``untrusted_source`` provenance on ``node_id`` → ``user_confirmed``.
vibecomfy/workflow.py:221:        from vibecomfy.security import provenance as _prov
vibecomfy/workflow.py:488:        _provenance: "Provenance | None" = None,
vibecomfy/workflow.py:497:        ``_provenance`` is a reserved keyword-only parameter declared BEFORE
vibecomfy/workflow.py:499:        dict. When ``None`` it falls back to the ``requesting_provenance``
vibecomfy/workflow.py:503:        ``node.inputs``. ``_provenance`` is a reserved kwarg name and must not
vibecomfy/workflow.py:509:            requesting_provenance,
vibecomfy/workflow.py:512:        from vibecomfy.security.provenance import PROVENANCE_KEY, tag as _tag_provenance
vibecomfy/workflow.py:514:        effective = _provenance if _provenance is not None else requesting_provenance.get()
vibecomfy/workflow.py:528:                if not isinstance(v, Handle) and k != "_provenance"
vibecomfy/workflow.py:533:                provenance=effective,
vibecomfy/workflow.py:545:        _tag_provenance(node, effective)
vibecomfy/workflow.py:547:        node.inputs.pop("_provenance", None)
vibecomfy/workflow.py:554:        explicit_provenance = kwargs.pop("_provenance", None)
vibecomfy/workflow.py:558:        node = self.add_node(class_type, _id=explicit_id, _provenance=explicit_provenance)
vibecomfy/workflow.py:581:                f"{operation}: malformed source ref {ref!r}; expected 'node_id' or 'node_id.output_slot'"
vibecomfy/workflow.py:591:            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
vibecomfy/workflow.py:594:            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
vibecomfy/workflow.py:805:        provenance = node.metadata.get("provenance")
vibecomfy/workflow.py:807:        if isinstance(provenance, dict):
vibecomfy/workflow.py:808:            sp = provenance.get("source_path")
vibecomfy/workflow.py:816:        if isinstance(provenance, dict):
vibecomfy/workflow.py:817:            sl = provenance.get("source_line")
vibecomfy/executor/research.py:66:from . import provenance
vibecomfy/executor/research.py:2592:            "provenance": "source_template",
vibecomfy/executor/research.py:2638:            "provenance": prior["provenance"],
vibecomfy/executor/research.py:2694:def _provenance_precedent_sources(
vibecomfy/executor/research.py:2709:        source_workflow = provenance.load_source_workflow(graph)
vibecomfy/executor/research.py:2710:        instances = provenance.collect_type_instances(source_workflow, target_node_type)
vibecomfy/executor/research.py:2723:        "provenance_instances": tuple(instances),
vibecomfy/executor/research.py:2727:        "provenance_lookup": True,
vibecomfy/executor/research.py:2728:        "reasons": ("graph provenance breadcrumb",),
vibecomfy/executor/research.py:2766:        provenance_instances = source.get("provenance_instances")
vibecomfy/executor/research.py:2767:        if isinstance(provenance_instances, (list, tuple)) and provenance_instances:
vibecomfy/executor/research.py:2769:                instance for instance in provenance_instances
vibecomfy/executor/research.py:2876:def _requested_model_families(query: str, graph: dict | None = None) -> set[str]:
vibecomfy/executor/research.py:3053:    requested = _requested_model_families(query, graph)
vibecomfy/executor/research.py:3142:            "code": "missing_required_pattern_nodes",
vibecomfy/executor/research.py:4098:# provenance (``manifest_provenance``) for the candidate slice and (b) the
vibecomfy/executor/research.py:4102:# anchor-binding behaviour byte-for-byte; the breadcrumb/provenance branch
vibecomfy/executor/research.py:4734:    requested_families = _requested_model_families(query)
vibecomfy/executor/research.py:4853:    Returns ``None`` if the inputs look malformed.
vibecomfy/executor/research.py:5204:    provenance: Mapping[str, Any],
vibecomfy/executor/research.py:5211:    provenance is incomplete, the projector rejects (no added nodes), or
vibecomfy/executor/research.py:5218:    tier + rank from retrieved-evidence provenance are consumed.  No
vibecomfy/executor/research.py:5221:    # ── provenance: content_hash + tier + rank ONLY (no path/filename) ────
vibecomfy/executor/research.py:5222:    content_hash = str(provenance.get("content_hash") or "").strip()
vibecomfy/executor/research.py:5223:    tier = str(provenance.get("tier") or "").strip()
vibecomfy/executor/research.py:5224:    rank_raw = provenance.get("rank")
vibecomfy/executor/research.py:5233:    # provenance; otherwise hash the candidate's structural signature.
vibecomfy/executor/research.py:5234:    evidence_hash = str(provenance.get("evidence_hash") or "").strip()
vibecomfy/executor/research.py:5331:    manifest_provenance: Mapping[str, Mapping[str, Any]] | None = None,
vibecomfy/executor/research.py:5339:    *manifest_provenance* (W-05) optionally maps a slice's
vibecomfy/executor/research.py:5340:    ``source_class_type`` to a retrieved-evidence provenance dict carrying a
vibecomfy/executor/research.py:5468:                # When retrieved-evidence provenance is available for THIS
vibecomfy/executor/research.py:5478:                    manifest_provenance is not None
vibecomfy/executor/research.py:5480:                        manifest_provenance.get(candidate_slice.source_class_type),
vibecomfy/executor/research.py:5565:                        reason="candidate graph construction returned a malformed graph",
vibecomfy/executor/research.py:5566:                        detail={"reason_code": "candidate_graph_malformed"},
vibecomfy/executor/research.py:5646:                "here (provenance: "
vibecomfy/executor/research.py:5647:                f"{widget.get('provenance', 'none')}, confidence: "
vibecomfy/executor/research.py:5677:    # retrieved-evidence provenance (path-free hash + tier + rank) is
vibecomfy/executor/research.py:5688:        and manifest_provenance
vibecomfy/executor/research.py:5690:        provenance = manifest_provenance.get(selected_slice.source_class_type)
vibecomfy/executor/research.py:5691:        if isinstance(provenance, Mapping):
vibecomfy/executor/research.py:5696:                provenance=provenance,
vibecomfy/executor/research.py:5989:    terms.extend(sorted(_requested_model_families(query)))
vibecomfy/executor/research.py:6093:    requested_families = set(_requested_model_families(query))
vibecomfy/executor/research.py:6270:    provenance_sources = _provenance_precedent_sources(graph, target_node_type)
vibecomfy/executor/research.py:6272:        sources = list(provenance_sources)
vibecomfy/executor/research.py:6279:            sources = list(provenance_sources)
vibecomfy/executor/research.py:6283:            sources = list(provenance_sources) + list(local.sources)
vibecomfy/executor/research.py:6405:            0 if s.get("provenance_lookup") is True else 1,
vibecomfy/executor/research.py:6480:    # ── W-05: path-free retrieved-evidence provenance for manifest emission ──
vibecomfy/executor/research.py:6484:    manifest_provenance: dict[str, Mapping[str, Any]] = {}
vibecomfy/executor/research.py:6489:        if not class_type or class_type in manifest_provenance:
vibecomfy/executor/research.py:6495:        manifest_provenance[class_type] = MappingProxyType({
vibecomfy/executor/research.py:6505:        manifest_provenance=manifest_provenance or None,
vibecomfy/porting/wrappers/discovery.py:20:care which source the spec came from beyond ``ClassSpec.source_provenance``.
vibecomfy/porting/wrappers/discovery.py:106:    source_provenance: str = ""
vibecomfy/porting/wrappers/discovery.py:234:    provenance = f"object_info live {server_url}"
vibecomfy/porting/wrappers/discovery.py:235:    return _specs_from_object_info(pack_slug, payload, provenance, filter_by_pack=True)
vibecomfy/porting/wrappers/discovery.py:260:    provenance = f"object_info {kind} {path.name} sha256:{sha256_of_path(path)[:12]}"
vibecomfy/porting/wrappers/discovery.py:262:    return _specs_from_object_info(pack_slug, payload, provenance, filter_by_pack=False)
vibecomfy/porting/wrappers/discovery.py:373:    provenance = f"source {source_file}"
vibecomfy/porting/wrappers/discovery.py:382:        source_provenance=provenance,
vibecomfy/porting/wrappers/discovery.py:468:    provenance: str,
vibecomfy/porting/wrappers/discovery.py:500:                source_provenance=provenance,
vibecomfy/porting/edit/ops.py:51:DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta"
vibecomfy/executor/execution_plan_builder.py:63:    "missing_required_inputs",
vibecomfy/executor/execution_plan_builder.py:267:    schema_provenance: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/executor/execution_plan_builder.py:268:    runtime_provenance: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/executor/execution_plan_builder.py:284:        object.__setattr__(self, "schema_provenance", _freeze_jsonish(self.schema_provenance))
vibecomfy/executor/execution_plan_builder.py:285:        object.__setattr__(self, "runtime_provenance", _freeze_jsonish(self.runtime_provenance))
vibecomfy/executor/execution_plan_builder.py:303:            "schema_provenance": _thaw_jsonish(self.schema_provenance),
vibecomfy/executor/execution_plan_builder.py:304:            "runtime_provenance": _thaw_jsonish(self.runtime_provenance),
vibecomfy/executor/execution_plan_builder.py:626:def _runtime_provenance_for_classes(
vibecomfy/executor/execution_plan_builder.py:633:    provenance: dict[str, str] = {}
vibecomfy/executor/execution_plan_builder.py:636:            provenance[class_type] = "graph_facts.unknown_class_types"
vibecomfy/executor/execution_plan_builder.py:638:            provenance[class_type] = "graph_facts.current_output_node_types"
vibecomfy/executor/execution_plan_builder.py:640:            provenance[class_type] = "graph_facts.not_reported"
vibecomfy/executor/execution_plan_builder.py:642:            provenance[class_type] = "not_checked"
vibecomfy/executor/execution_plan_builder.py:643:    return provenance
vibecomfy/executor/execution_plan_builder.py:646:def _schema_provenance_for_role(
vibecomfy/executor/execution_plan_builder.py:669:    runtime facts are serialized as provenance/unresolved evidence instead of
vibecomfy/executor/execution_plan_builder.py:720:    schema_provenance: dict[str, Any] = {}
vibecomfy/executor/execution_plan_builder.py:735:        schema_ref, class_schema = _schema_provenance_for_role(class_type, sources)
vibecomfy/executor/execution_plan_builder.py:736:        schema_provenance[class_type] = schema_ref
vibecomfy/executor/execution_plan_builder.py:810:    runtime_provenance = _runtime_provenance_for_classes(graph_facts, required_classes)
vibecomfy/executor/execution_plan_builder.py:821:        schema_provenance=schema_provenance,
vibecomfy/executor/execution_plan_builder.py:822:        runtime_provenance=runtime_provenance,
vibecomfy/executor/execution_plan_builder.py:880:def _plan_provenance(normalized: NormalizedPrecedentEvidence) -> dict[str, Any]:
vibecomfy/executor/execution_plan_builder.py:1150:            schema_source=str(normalized.schema_provenance.get(class_type or "", "not_available")),
vibecomfy/executor/execution_plan_builder.py:1151:            runtime_availability=str(normalized.runtime_provenance.get(class_type or "", "not_checked")),
vibecomfy/executor/execution_plan_builder.py:1273:        schema_provenance={
vibecomfy/executor/execution_plan_builder.py:1274:            **_thaw_jsonish(normalized.schema_provenance),
vibecomfy/executor/execution_plan_builder.py:1275:            "execution_plan_builder": _plan_provenance(normalized),
vibecomfy/executor/execution_plan_builder.py:1277:        runtime_provenance=_thaw_jsonish(normalized.runtime_provenance),
vibecomfy/comfy_nodes/web/comfy_adapter.js:49:    this.code = code || "malformed_delta";
vibecomfy/comfy_nodes/web/comfy_adapter.js:1053:      // executed while preserving monotonic persisted-op provenance.
vibecomfy/comfy_nodes/web/comfy_adapter.js:1275:    // A malformed extension node must never block review; retain server geometry.
vibecomfy/comfy_nodes/web/comfy_adapter.js:1581:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1813:      "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1822:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1829:        "malformed_delta",
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:792://   - ``malformed_delta`` — structurally invalid envelope or op
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1886:  // malformed/non-applyable. Override eligibility to block Apply with
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1979:    ...(missingDurableEligibility ? { debug_branch: "malformed_metadata" } : {}),
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2645:        failure_kind: event.failure_kind || null,
vibecomfy/porting/edit/apply_resolve_add.py:147:                    "missing_required_add_node_input",
vibecomfy/porting/edit/apply_resolve_add.py:385:        provenance = ""
vibecomfy/porting/edit/apply_resolve_add.py:393:            provenance = "user"
vibecomfy/porting/edit/apply_resolve_add.py:401:            provenance = prior.provenance
vibecomfy/porting/edit/apply_resolve_add.py:444:                provenance=provenance,
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:61:  // Apply must never trust malformed authority. Reject is different: it only
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:177:      // A malformed aggregate is not downgraded to legacy browser state.
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:277:      throw new Error("Landed mutation contains an operation without persisted provenance.");
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:281:      throw new Error(`Landed operation provenance differs at persisted op ${index}.`);
vibecomfy/porting/edit/apply_types.py:55:    provenance: str
vibecomfy/porting/edit/apply_types.py:93:    provenance: str
vibecomfy/porting/edit/apply_types.py:110:            "provenance": self.provenance,
vibecomfy/porting/edit/apply_types.py:137:    allowed_provenance: frozenset[str] = frozenset({"source_template"})
vibecomfy/porting/edit/apply_types.py:155:            "allowed_provenance",
vibecomfy/porting/edit/apply_types.py:156:            frozenset(str(value) for value in self.allowed_provenance),
vibecomfy/porting/edit/apply_types.py:191:                    provenance=str(field_record.get("provenance") or ""),
vibecomfy/porting/edit/apply_types.py:253:            and binding.provenance in self.allowed_provenance
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:38:    this.code = code || "malformed_materialization";
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:69:    throw _fail(`${field} must be a list of ${length} finite numbers`, "malformed_materialization_entry", { field });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:73:      throw _fail(`${field} must contain finite numbers`, "malformed_materialization_entry", { field });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:81:    throw _fail("materialization entry must be an object", "malformed_materialization_entry");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:86:    throw _fail(`materialization entry carries forbidden key(s): ${forbidden.join(", ")}`, "malformed_materialization_entry", { keys: forbidden });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:90:    throw _fail(`Unknown materialization entry key(s): ${extras.join(", ")}`, "malformed_materialization_entry", { keys: extras });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:93:    throw _fail("materialization entry requires source_op_index", "malformed_materialization_entry", { field: "source_op_index" });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:102:      throw _fail("widgets_values may not be null (absent or a value)", "malformed_materialization_entry", { field: "widgets_values" });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:105:      throw _fail("widgets_values must be an array (or object for vibecomfy.exec)", "malformed_materialization_entry", { field: "widgets_values" });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:117:      throw _fail("opaque must be a JSON object", "malformed_materialization_entry", { field: "opaque" });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:126:    throw _fail("materialization entries must be an array", "malformed_materialization");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:157:    throw _fail("materialization envelope must be an object", "malformed_materialization");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:161:    throw _fail(`Unknown materialization envelope key(s): ${extras.join(", ")}`, "malformed_materialization", { keys: extras });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:186:    throw _fail("accompanyingOps must be a non-empty array of canonical delta ops", "malformed_materialization");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:190:      throw _fail("accompanyingOps must be canonical delta ops", "malformed_materialization");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:232:          throw _fail("vibecomfy.exec widgets_values must be array or object", "malformed_materialization_entry", { field: "widgets_values" });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:235:        throw _fail("widgets_values must be an array for non-vibecomfy.exec nodes", "malformed_materialization_entry", { field: "widgets_values" });
vibecomfy/porting/__init__.py:32:    "ProvenanceConflict": "vibecomfy.porting.provenance",
vibecomfy/porting/__init__.py:33:    "ProvenanceRecord": "vibecomfy.porting.provenance",
vibecomfy/porting/__init__.py:34:    "ProvenanceReport": "vibecomfy.porting.provenance",
vibecomfy/porting/__init__.py:35:    "ProvenanceRequirement": "vibecomfy.porting.provenance",
vibecomfy/porting/__init__.py:36:    "ProvenanceVersionPin": "vibecomfy.porting.provenance",
vibecomfy/porting/__init__.py:37:    "ProvenanceWarning": "vibecomfy.porting.provenance",
vibecomfy/porting/__init__.py:64:    "extract_provenance": "vibecomfy.porting.provenance",
vibecomfy/registry/ready.py:14:from vibecomfy.security.loader_provenance import _provenance_for_path
vibecomfy/registry/ready.py:122:    provenance = _provenance_for_path(path)
vibecomfy/registry/ready.py:123:    if provenance == "untrusted_source" and is_dynamic_ready_template:
vibecomfy/registry/ready.py:124:        provenance = "user_confirmed"
vibecomfy/registry/ready.py:128:        provenance=provenance,
vibecomfy/porting/workbench.py:127:        provenance=_provenance(loaded),
vibecomfy/porting/workbench.py:737:        workflow = load_scratchpad(source_path, provenance_override="user_confirmed")
vibecomfy/porting/workbench.py:760:        workflow = load_scratchpad(resolved, provenance_override="user_confirmed")
vibecomfy/porting/workbench.py:809:def _provenance(loaded: LoadedPortSource) -> dict[str, Any]:
vibecomfy/porting/workbench.py:810:    provenance = dict(loaded.workflow.source.provenance)
vibecomfy/porting/workbench.py:811:    provenance.update(
vibecomfy/porting/workbench.py:822:        provenance["raw_workflow_shape"] = detect_workflow_shape(loaded.raw_workflow)
vibecomfy/porting/workbench.py:823:    return provenance
vibecomfy/comfy_nodes/web/layout_operation_v1.js:66:    this.code = code || "malformed_layout_operation";
vibecomfy/comfy_nodes/web/layout_operation_v1.js:102:    throw _fail(`${field} must be a list of ${length} finite numbers`, "malformed_layout_op", { field });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:106:      throw _fail(`${field} must contain finite numbers`, "malformed_layout_op", { field });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:117:    throw _fail(`Unknown layout op key(s): ${extras.join(", ")}`, "malformed_layout_op", {
vibecomfy/comfy_nodes/web/layout_operation_v1.js:126:    throw _fail("layout op must be an object", "malformed_layout_op");
vibecomfy/comfy_nodes/web/layout_operation_v1.js:130:    throw _fail('layout op must have a non-empty string "op"', "malformed_layout_op");
vibecomfy/comfy_nodes/web/layout_operation_v1.js:152:      throw _fail("add_group title must be a string", "malformed_layout_op", { field: "title" });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:155:      throw _fail("add_group color must be a string or null", "malformed_layout_op", { field: "color" });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:167:        "malformed_layout_op",
vibecomfy/comfy_nodes/web/layout_operation_v1.js:176:        throw _fail("set_group_geometry title must be a string", "malformed_layout_op", { field: "title" });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:182:        throw _fail("set_group_geometry color must be a string or null", "malformed_layout_op", { field: "color" });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:201:    throw _fail("layout ops must be an array", "malformed_layout_operation");
vibecomfy/comfy_nodes/web/layout_operation_v1.js:229:    throw _fail("layout operation envelope must be an object", "malformed_layout_operation");
vibecomfy/comfy_nodes/web/layout_operation_v1.js:235:    throw _fail(`Unknown layout operation envelope key(s): ${extras.join(", ")}`, "malformed_layout_operation", { keys: extras });
vibecomfy/comfy_nodes/web/layout_operation_v1.js:260:    throw _fail("layout operation envelope must be an object", "malformed_layout_operation");
vibecomfy/porting/_provenance_utils.py:1:"""Shared provenance path helpers used by both convert.py and emitter.py.
vibecomfy/porting/_provenance_utils.py:22:def _normalize_provenance_paths(provenance: Mapping[str, Any]) -> dict[str, Any]:
vibecomfy/porting/_provenance_utils.py:23:    normalized = dict(provenance)
vibecomfy/porting/_provenance_utils.py:27:            normalized[key] = _repo_relative_provenance_path(value)
vibecomfy/porting/_provenance_utils.py:31:def _repo_relative_provenance_path(path: str) -> str:
vibecomfy/porting/_provenance_utils.py:35:            "provenance path is outside the repo; keeping absolute path: %s",
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:285:    || asString(response.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:468:  // SD2: both session_id and turn_id must be absent for malformed/non-applyable.
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:525:  // malformed/non-applyable, never stale/rebaseline. Suppress Apply and
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:913:  // turn_id is malformed/non-applyable, never stale/rebaseline. Prevent
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:994:    failureKind: asString(raw.failureKind) || asString(raw.failure_kind),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1627:    failure_kind: asString(source.failure_kind) || asString(source.failureKind) || asString(outcome?.failure_kind),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1891:      asString(entry.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1921:      || asString(normalized.outcome.failure_kind)
vibecomfy/comfy_backend.py:60:    All fields are required; missing / malformed JSON raises immediately
vibecomfy/comfy_backend.py:214:    commit in ``direct_url.json``; use that as the provenance pin instead of a
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:97:      code: "malformed_restoration_payload",
vibecomfy/comfy_nodes/web/panel_thread.js:2430:  if (entry.failure_kind) {
vibecomfy/comfy_nodes/web/panel_thread.js:2431:    appendTextLine(turnCard, `${entry.failure_kind}${entry.failure_stage ? ` @ ${entry.failure_stage}` : ""}`, "#ffb86c");
vibecomfy/porting/simulate.py:209:                provenance=getattr(loaded, "provenance", None),
vibecomfy/porting/rules_registry.py:117:            "provenance are omitted from READY_METADATA to reduce redundancy."
vibecomfy/porting/rules_registry.py:200:        description="Source provenance recorded in WorkflowSource.provenance",
vibecomfy/porting/rules_registry.py:202:            "The WorkflowSource.provenance dict records source_path, "
vibecomfy/porting/rules_registry.py:210:        description="Conversion provenance includes schema source metadata",
vibecomfy/porting/rules_registry.py:222:            "followed by a provenance summary so automated tools can identify "
vibecomfy/porting/rules_registry.py:297:        description="custom_node_packs provenance injected for custom node classes",
vibecomfy/porting/rules_registry.py:300:            "adds provenance metadata linking the template to the pack name "
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:296:    throw _fail("Restoration strategy must be an object", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:305:    throw _fail("Restoration payload and ref are mutually exclusive", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:308:    throw _fail("Restoration requires payload or ref", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:311:    throw _fail("Restoration digest must be hex64", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:315:      throw _fail("baseline_snapshot_v1 restoration must use ref", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:319:      throw _fail("baseline_snapshot_v1 ref must be a non-empty string", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:329:    throw _fail("inverse restoration must use payload", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:341:    throw _fail("Restoration payload must be an object", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:362:      throw _fail(`${tag} payload has extra keys`, "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:366:      throw _fail(`${tag} payload requires ops`, "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:374:      throw _fail("mutation_materialization presence parity violated", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:377:      throw _fail("add_node inverse requires materialization", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:380:      throw _fail("materialization without add_node inverse", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:392:        throw _fail("forward_operation_digest must be hex64", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:395:        throw _fail("prior_link_witnesses must be an array", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:402:          throw _fail("prior-link witness must be exactly {from,to} root endpoints", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:406:          throw _fail("duplicate prior-link witness destination", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:432:      throw _fail("inverse_layout_operation_v1 payload has extra keys", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:436:      throw _fail("inverse_layout_operation_v1 requires layout_operation", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:449:    throw _fail("restoration_strategy_compensation must be an object", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:453:    throw _fail("restoration_strategy_compensation has extra keys", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:463:    throw _fail("compensation ref must be a non-empty string", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:467:    throw _fail("compensation fence must be an object", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:472:    throw _fail("compensation fence key set is not closed", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:475:    throw _fail("compensation generation must be a positive int", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:479:      throw _fail(`compensation fence ${key} must be non-empty string`, "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:484:      throw _fail(`compensation fence ${key} must be hex64`, "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:632:    throw _fail("restoration_strategy_compensation may not be null.", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:648://   * A malformed legacy shape (missing/typed restoration_strategy, unknown
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:662:    throw _fail("Legacy restoration payload and ref are mutually exclusive.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:665:    throw _fail("Legacy restoration requires payload or ref.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:669:      throw _fail("Legacy baseline_snapshot_v1 restoration must use ref.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:672:      throw _fail("Legacy baseline_snapshot_v1 ref must be a non-empty string.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:678:    throw _fail("Legacy inverse restoration must use payload.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:681:    throw _fail("Legacy inverse restoration payload must be an object.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:691:    throw _fail("Legacy authority must be an object.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:698:    throw _fail("Legacy authority requires a restoration_strategy object.", "malformed_legacy_authority");
vibecomfy/registry/library.py:78:        return load_scratchpad(value, provenance_override="user_confirmed")
vibecomfy/porting/convert.py:78:    # True when conversion emitted low-confidence provenance diagnostics.
vibecomfy/porting/convert.py:206:    """Derive a node_id -> ObjectInfoIdentity map from raw workflow provenance."""
vibecomfy/porting/convert.py:207:    from vibecomfy.porting.provenance import extract_provenance
vibecomfy/porting/convert.py:210:        report = extract_provenance(raw_workflow)
vibecomfy/porting/convert.py:239:    provenance: dict[str, Any] | None = None,
vibecomfy/porting/convert.py:334:        complete_provenance = _conversion_provenance(
vibecomfy/porting/convert.py:337:            provenance=provenance,
vibecomfy/porting/convert.py:347:            provenance=complete_provenance,
vibecomfy/porting/convert.py:356:        complete_provenance = _conversion_provenance(
vibecomfy/porting/convert.py:359:            provenance=provenance,
vibecomfy/porting/convert.py:367:            ready_metadata=_ready_metadata(workflow, ready_id=ready_id, source_path=source_path, provenance=complete_provenance),
vibecomfy/porting/convert.py:639:def _source_provenance(workflow: VibeWorkflow, *, source_path: str | None) -> dict[str, Any]:
vibecomfy/porting/convert.py:640:    provenance = dict(workflow.source.provenance)
vibecomfy/porting/convert.py:642:        provenance.setdefault("source_path", _repo_relative_provenance_path(source_path))
vibecomfy/porting/convert.py:643:    provenance.setdefault("source_id", workflow.source.id)
vibecomfy/porting/convert.py:644:    provenance.setdefault("source_type", workflow.source.source_type)
vibecomfy/porting/convert.py:646:        provenance.setdefault("source_workflow_path", _repo_relative_provenance_path(workflow.source.path))
vibecomfy/porting/convert.py:647:    return _normalize_provenance_paths(provenance)
vibecomfy/porting/convert.py:650:def _conversion_provenance(
vibecomfy/porting/convert.py:654:    provenance: dict[str, Any] | None,
vibecomfy/porting/convert.py:660:    merged = _source_provenance(workflow, source_path=source_path)
vibecomfy/porting/convert.py:661:    if provenance:
vibecomfy/porting/convert.py:662:        merged.update(provenance)
vibecomfy/porting/convert.py:727:    provenance: dict[str, Any] | None,
vibecomfy/porting/convert.py:732:        metadata.setdefault("source_workflow", _repo_relative_provenance_path(source_path))
vibecomfy/porting/convert.py:733:    if provenance:
vibecomfy/porting/convert.py:734:        metadata.setdefault("provenance", _normalize_provenance_paths(provenance))
vibecomfy/porting/convert.py:739:def _normalize_provenance_paths(provenance: dict[str, Any]) -> dict[str, Any]:
vibecomfy/porting/convert.py:740:    normalized = dict(provenance)
vibecomfy/porting/convert.py:744:            normalized[key] = _repo_relative_provenance_path(value)
vibecomfy/porting/convert.py:748:def _repo_relative_provenance_path(path: str) -> str:
vibecomfy/porting/convert.py:751:        logger.warning("provenance path is outside the repo; keeping absolute path: %s", normalized)
vibecomfy/comfy_nodes/web/canonical_delta.js:24:export const DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta";
vibecomfy/comfy_nodes/web/canonical_delta.js:334:      code: "canonical_envelope_malformed_ops",
vibecomfy/cli_loader.py:32:        return load_scratchpad(path, provenance_override="user_confirmed")
vibecomfy/registry/ready_template.py:55:    provenance = metadata.get("provenance")
vibecomfy/registry/ready_template.py:56:    if isinstance(provenance, Mapping):
vibecomfy/registry/ready_template.py:57:        metadata.update({str(key): value for key, value in provenance.items() if key not in metadata})
vibecomfy/registry/ready_template.py:209:    provenance: Mapping[str, Any] | None = None,
vibecomfy/registry/ready_template.py:223:            provenance=dict(provenance) if provenance else {},
vibecomfy/registry/static_contract.py:732:    provenance = result.get("provenance")
vibecomfy/registry/static_contract.py:733:    if isinstance(provenance, dict):
vibecomfy/registry/static_contract.py:734:        for key, value in provenance.items():
vibecomfy/registry/static_contract.py:890:    provenance = metadata.get("provenance")
vibecomfy/registry/static_contract.py:891:    if isinstance(provenance, dict) and isinstance(provenance.get("source_workflow"), str):
vibecomfy/registry/static_contract.py:892:        return provenance["source_workflow"]

exec
/bin/zsh -lc 'git diff --unified=80 16d80bbe..e33f0260 -- vibecomfy/executor/contracts.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 99ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/executor/contracts.py b/vibecomfy/executor/contracts.py
index 36605241..671e6d06 100644
--- a/vibecomfy/executor/contracts.py
+++ b/vibecomfy/executor/contracts.py
@@ -1,115 +1,303 @@
 """Typed data contracts for the embedded VibeComfy executor.

 These are the public shapes that flow through the classify → research →
 implement → reply pipeline.  Every contract is a frozen dataclass with a
 canonical ``to_dict()`` serializer so the executor can produce the standard
 ``success_envelope`` shape without adding new top-level response fields.
 """

 from __future__ import annotations

 import logging
 import re
 from dataclasses import dataclass, field
 from types import MappingProxyType
 from typing import Any, Mapping
 from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

 from vibecomfy.agent.deepseek_usage import coerce_deepseek_usage

 LOGGER = logging.getLogger(__name__)

 _WARNING_DETAIL_MAX_MESSAGE = 160
 _SENSITIVE_QUERY_KEYS = frozenset({
     "api_key",
     "apikey",
     "auth",
     "authorization",
     "key",
     "password",
     "secret",
     "sig",
     "signature",
     "token",
 })

+MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
+    "empty_response",
+    "malformed_json",
+    "non_json_content",
+    "missing_required_fields",
+    "timeout",
+    "provider_failure",
+})
+_MODEL_ATTEMPT_OUTCOMES = frozenset({"success", "failure"})
+_MODEL_ATTEMPT_UNKNOWN = "unknown"
+_MODEL_ATTEMPT_PREVIEW_LIMIT = 1200
+_MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE = re.compile(
+    r"(?i)\b(api[_-]?key|authorization|bearer[_-]?token|access[_-]?token|secret|token)"
+    r"(\s*[:=]\s*)([^\s,;]+)"
+)
+_MODEL_ATTEMPT_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
+_MODEL_ATTEMPT_URL_RE = re.compile(r"https?://[^\s<>\"']+")
+
+
+def normalize_model_endpoint(value: Any) -> str:
+    """Return a credential-free, query-free endpoint or ``"unknown"``.
+
+    Model-attempt evidence intentionally records only the scheme, host, port,
+    and normalized path. Userinfo, query parameters, and fragments are never
+    provenance and can contain credentials, so they are discarded wholesale.
+    """
+    if not isinstance(value, str) or not value.strip():
+        return _MODEL_ATTEMPT_UNKNOWN
+    try:
+        parsed = urlsplit(value.strip())
+    except ValueError:
+        return _MODEL_ATTEMPT_UNKNOWN
+    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
+        return _MODEL_ATTEMPT_UNKNOWN
+    host = parsed.hostname.lower()
+    if ":" in host and not host.startswith("["):
+        host = f"[{host}]"
+    try:
+        port = parsed.port
+    except ValueError:
+        return _MODEL_ATTEMPT_UNKNOWN
+    netloc = f"{host}:{port}" if port is not None else host
+    path = re.sub(r"/{2,}", "/", parsed.path or "")
+    if path != "/":
+        path = path.rstrip("/")
+    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))
+
+
+def redact_model_preview(value: Any, *, limit: int = _MODEL_ATTEMPT_PREVIEW_LIMIT) -> str | None:
+    """Return a bounded failure preview with credentials and URL queries removed."""
+    if not isinstance(value, str):
+        return None
+    normalized = " ".join(value.strip().split())
+    if not normalized:
+        return None
+    normalized = _MODEL_ATTEMPT_URL_RE.sub(
+        lambda match: normalize_model_endpoint(match.group(0)), normalized
+    )
+    normalized = _MODEL_ATTEMPT_BEARER_RE.sub("Bearer <redacted>", normalized)
+    normalized = _MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE.sub(
+        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", normalized
+    )
+    if len(normalized) > limit:
+        normalized = normalized[: limit - 1].rstrip() + "…"
+    return normalized
+
+
+def _model_attempt_text(value: Any) -> str:
+    if isinstance(value, str) and value.strip():
+        return value.strip()
+    return _MODEL_ATTEMPT_UNKNOWN
+
+
+def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
+    usage = value if isinstance(value, Mapping) else {}
+    normalized: dict[str, int | str] = {}
+    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
+        token_value = usage.get(key)
+        normalized[key] = (
+            max(0, int(token_value))
+            if isinstance(token_value, (int, float)) and not isinstance(token_value, bool)
+            else _MODEL_ATTEMPT_UNKNOWN
+        )
+    return normalized
+
+
+@dataclass(frozen=True)
+class ModelAttemptEvidence:
+    """Canonical evidence for one actual model-provider call.
+
+    The shape is shared by worker envelopes, runtime/provider results, executor
+    reports, durable artifacts, and the live harness. Raw model output is never
+    retained on success and is bounded/redacted on failure.
+    """
+
+    phase: str = _MODEL_ATTEMPT_UNKNOWN
+    attempt: int = 1
+    outcome: str = "failure"
+    failure_type: str | None = None
+    requested_model: str = _MODEL_ATTEMPT_UNKNOWN
+    resolved_model: str = _MODEL_ATTEMPT_UNKNOWN
+    adapter: str = _MODEL_ATTEMPT_UNKNOWN
+    provider: str = _MODEL_ATTEMPT_UNKNOWN
+    transport: str = _MODEL_ATTEMPT_UNKNOWN
+    endpoint: str = _MODEL_ATTEMPT_UNKNOWN
+    finish_reason: str = _MODEL_ATTEMPT_UNKNOWN
+    token_usage: Mapping[str, Any] = field(default_factory=dict)
+    raw_response_preview: str | None = None
+
+    def __post_init__(self) -> None:
+        outcome = self.outcome if self.outcome in _MODEL_ATTEMPT_OUTCOMES else "failure"
+        failure_type = self.failure_type
+        if outcome == "success":
+            failure_type = None
+        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
+            failure_type = "provider_failure"
+        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
+        object.__setattr__(self, "attempt", max(1, int(self.attempt or 1)))
+        object.__setattr__(self, "outcome", outcome)
+        object.__setattr__(self, "failure_type", failure_type)
+        for name in (
+            "requested_model", "resolved_model", "adapter", "provider",
+            "transport", "finish_reason",
+        ):
+            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
+        object.__setattr__(self, "endpoint", normalize_model_endpoint(self.endpoint))
+        object.__setattr__(
+            self,
+            "token_usage",
+            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
+        )
+        preview = (
+            redact_model_preview(self.raw_response_preview)
+            if outcome == "failure"
+            else None
+        )
+        object.__setattr__(self, "raw_response_preview", preview)
+
+    @classmethod
+    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
+        return cls(
+            phase=value.get("phase", _MODEL_ATTEMPT_UNKNOWN),
+            attempt=value.get("attempt", 1),
+            outcome=value.get("outcome", "failure"),
+            failure_type=value.get("failure_type"),
+            requested_model=value.get("requested_model", _MODEL_ATTEMPT_UNKNOWN),
+            resolved_model=value.get("resolved_model", _MODEL_ATTEMPT_UNKNOWN),
+            adapter=value.get("adapter", _MODEL_ATTEMPT_UNKNOWN),
+            provider=value.get("provider", _MODEL_ATTEMPT_UNKNOWN),
+            transport=value.get("transport", _MODEL_ATTEMPT_UNKNOWN),
+            endpoint=value.get("endpoint", _MODEL_ATTEMPT_UNKNOWN),
+            finish_reason=value.get("finish_reason", _MODEL_ATTEMPT_UNKNOWN),
+            token_usage=value.get("token_usage", {}),
+            raw_response_preview=value.get("raw_response_preview"),
+        )
+
+    def to_dict(self) -> dict[str, Any]:
+        payload: dict[str, Any] = {
+            "phase": self.phase,
+            "attempt": self.attempt,
+            "outcome": self.outcome,
+            "failure_type": self.failure_type,
+            "requested_model": self.requested_model,
+            "resolved_model": self.resolved_model,
+            "adapter": self.adapter,
+            "provider": self.provider,
+            "transport": self.transport,
+            "endpoint": self.endpoint,
+            "finish_reason": self.finish_reason,
+            "token_usage": dict(self.token_usage),
+        }
+        if self.outcome == "failure" and self.raw_response_preview:
+            payload["raw_response_preview"] = self.raw_response_preview
+        return payload
+
+
+def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
+    """Normalize untrusted attempt mappings into the canonical serialized shape."""
+    if not isinstance(value, (list, tuple)):
+        return ()
+    attempts: list[dict[str, Any]] = []
+    for item in value:
+        if isinstance(item, ModelAttemptEvidence):
+            attempts.append(item.to_dict())
+        elif isinstance(item, Mapping):
+            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
+    return tuple(attempts)
+

 _NODE_TYPE_MARKER_RE = re.compile(
     r"(?:class(?:_type|\s+type)?|node(?:\s+of)?(?:\s+type)?|of\s+type)\s*[:=]?\s*"
     r"([A-Za-z_][A-Za-z0-9_.:-]*)",
     re.IGNORECASE,
 )
 _NODE_TYPE_VERB_RE = re.compile(
     r"\b(?:add|insert|create|restore|replace|remove|change|edit)\s+"
     r"(?:(?:an?|the|new|another|some|one)\s+)*"
     r"([A-Za-z_][A-Za-z0-9_.:-]*)\b",
     re.IGNORECASE,
 )
 _NON_NODE_TYPE_TOKENS = frozenset({
     "a", "an", "the", "node", "nodes", "class", "type", "of", "to",
     "with", "for", "from", "into", "on", "in", "and", "or", "value",
     "setting", "settings", "field", "fields", "widget", "widgets", "new",
 })
 _UI_ONLY_ANNOTATION_CLASS_TYPES = frozenset({
     "annotation",
     "annotationnode",
     "comment",
     "commentnode",
     "markdown",
     "markdownnote",
     "markdownnotenode",
     "note",
     "notenode",
     "workflowcomment",
     "workflowmarkdown",
     "workflownote",
 })


 def is_ui_only_annotation_class_type(class_type: Any) -> bool:
     """Return whether a class name denotes a known no-dataflow UI annotation.

     Keep this deliberately conservative: reroutes, primitives, groups, and
     other frontend components can participate in dataflow or component
     expansion and therefore are not skipped merely because they are UI nodes.
     """
     normalized = re.sub(r"[^a-z0-9]", "", str(class_type or "").casefold())
     return normalized in _UI_ONLY_ANNOTATION_CLASS_TYPES


 def parse_target_node_type(change_goal: str) -> str:
     """Extract a likely ComfyUI class-type token from a change goal.

     Classifier metadata is intentionally best-effort.  The parser only uses
     explicit node/type markers or an edit verb followed by a token, and returns
     an empty string when the sentence is too ambiguous to bind safely.
     """
     if not isinstance(change_goal, str) or not change_goal.strip():
         return ""

     candidates: list[str] = []
     marker = _NODE_TYPE_MARKER_RE.search(change_goal)
     if marker:
         candidates.append(marker.group(1))
     verb = _NODE_TYPE_VERB_RE.search(change_goal)
     if verb:
         candidates.append(verb.group(1))

     for candidate in candidates:
         token = candidate.strip(".,;()[]{}\"'")
         if token and token.casefold() not in _NON_NODE_TYPE_TOKENS:
             return token
     return ""


 def _freeze_jsonish(value: Any) -> Any:
     if isinstance(value, Mapping):
         return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
     if isinstance(value, (list, tuple)):
         return tuple(_freeze_jsonish(v) for v in value)
     return value


 def _thaw_jsonish(value: Any) -> Any:
     if isinstance(value, Mapping):
         return {str(k): _thaw_jsonish(v) for k, v in value.items()}
@@ -2034,204 +2222,215 @@ class ImplementationResult:
                     for k, v in self.durable_response.items()
                 }),
             )
         if self.diagnostics is not None:
             object.__setattr__(
                 self,
                 "diagnostics",
                 MappingProxyType({
                     str(k): _freeze_jsonish(v)
                     for k, v in self.diagnostics.items()
                 }),
             )
         if self.failure is not None:
             object.__setattr__(
                 self,
                 "failure",
                 MappingProxyType({
                     str(k): _freeze_jsonish(v)
                     for k, v in self.failure.items()
                 }),
             )

     @property
     def durable_session_id(self) -> str | None:
         """Return the session_id from the durable response, if present."""
         dr = self.durable_response
         if dr is None:
             return None
         sid = dr.get("session_id")
         return sid if isinstance(sid, str) and sid.strip() else None

     @property
     def durable_turn_id(self) -> str | None:
         """Return the turn_id from the durable response, if present."""
         dr = self.durable_response
         if dr is None:
             return None
         tid = dr.get("turn_id")
         return tid if isinstance(tid, str) and tid.strip() else None

     def to_dict(self) -> dict[str, Any]:
         payload: dict[str, Any] = {"message": self.message}
         if self.graph is not None:
             payload["graph"] = self.graph
         if self.delta:
             payload["delta"] = _thaw_jsonish(self.delta)
         if self.diagnostics is not None:
             payload["diagnostics"] = _thaw_jsonish(self.diagnostics)
         if self.failure is not None:
             payload["failure"] = _thaw_jsonish(self.failure)
             diagnostics = self.failure.get("diagnostics")
             if diagnostics is not None:
                 payload["diagnostics"] = _thaw_jsonish(diagnostics)
         # Durable metadata is internal; only exposed through the
         # candidate payload in AgentTurnResult, not here.
         return payload


 # ── report (nested executor metadata) ────────────────────────────────────────


 @dataclass(frozen=True)
 class Report:
     """Executor metadata nested under ``report`` in the final envelope.

     Every phase's output is captured here so the envelope stays a stable
     ``{message, outcome, candidate, eligibility, report}`` shape without
     new top-level fields.
     """

     plan: ClassifyDecision | None = None
     research: ResearchResult | None = None
     implementation: ImplementationResult | None = None
     deepseek_usage: dict[str, Any] = field(default_factory=dict)
     deepseek_est_cost_usd: float | None = None
     deepseek_cost_basis: str | None = None
     # Truthful classification lifecycle signal: "failed" means classify raised
     # (the plan is then None — no invented respond_only placeholder). Empty
     # string means the signal was not recorded (legacy paths).
     classification_status: str = ""
+    # Canonical per-call evidence for every successful and failed model attempt
+    # observed across classify, implement/batch, and reply.
+    model_attempts: tuple[dict[str, Any], ...] = ()
     # Mirrors the batch-repl model_response.json attempt artifact: parse-failure
     # evidence (parse_reason, raw preview, usage, model, phase, endpoint) for the
     # last classify/reply model attempt. None when the turn did not fail on a
     # model response.
     model_response: dict[str, Any] | None = None

     def __post_init__(self) -> None:
         object.__setattr__(
             self,
             "deepseek_usage",
             MappingProxyType({
                 str(k): _freeze_jsonish(v)
                 for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
             }),
         )
+        object.__setattr__(
+            self,
+            "model_attempts",
+            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
+        )
         if self.model_response is not None:
             object.__setattr__(
                 self,
                 "model_response",
                 _freeze_jsonish(self.model_response),
             )

     def to_dict(self) -> dict[str, Any]:
         inner: dict[str, Any] = {}
         if self.plan is not None:
             plan_payload = self.plan.to_dict()
             route = _public_route_for_plan(self.plan)
             plan_payload["route"] = route
             task = self.plan.effective_task
             if task:
                 plan_payload["task"] = task
             inner["plan"] = plan_payload
         if self.research is not None:
             inner["research"] = self.research.to_dict()
         if self.implementation is not None:
             inner["implementation"] = self.implementation.to_dict()
         usage_payload = coerce_deepseek_usage(self.deepseek_usage)
         inner["deepseek_usage"] = usage_payload
         if self.deepseek_est_cost_usd is not None:
             inner["deepseek_est_cost_usd"] = float(self.deepseek_est_cost_usd)
         if isinstance(self.deepseek_cost_basis, str) and self.deepseek_cost_basis:
             inner["deepseek_cost_basis"] = self.deepseek_cost_basis
         if self.classification_status:
             inner["classification_status"] = self.classification_status
+        inner["model_attempts"] = [
+            _thaw_jsonish(item) for item in self.model_attempts
+        ]
         if self.model_response is not None:
             inner["model_response"] = _thaw_jsonish(self.model_response)
         return {"executor": inner}


 # ── canonical turn envelope ──────────────────────────────────────────────────


 def _public_route_for_plan(plan: ClassifyDecision) -> str:
     route = plan.effective_route
     if route in _PUBLIC_ROUTES:
         return route
     if plan.implement and plan.research:
         return "adapt"
     if plan.implement:
         return "revise"
     if plan.research:
         return "research"
     return "respond"


 @dataclass(frozen=True)
 class AgentEvidence:
     """Bounded evidence object for public executor turn responses."""

     classification: dict[str, Any] = field(default_factory=dict)
     graph_inspection: dict[str, Any] = field(default_factory=dict)
     research: dict[str, Any] = field(default_factory=dict)
     implementation: dict[str, Any] = field(default_factory=dict)
     warnings: tuple[str, ...] = ()

     def __post_init__(self) -> None:
         object.__setattr__(self, "classification", MappingProxyType({
             str(k): _freeze_jsonish(v) for k, v in self.classification.items()
         }))
         object.__setattr__(self, "graph_inspection", MappingProxyType({
             str(k): _freeze_jsonish(v) for k, v in self.graph_inspection.items()
         }))
         object.__setattr__(self, "research", MappingProxyType({
             str(k): _freeze_jsonish(v) for k, v in self.research.items()
         }))
         object.__setattr__(self, "implementation", MappingProxyType({
             str(k): _freeze_jsonish(v) for k, v in self.implementation.items()
         }))
         object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings))

     def to_dict(self) -> dict[str, Any]:
         payload = {
             "classification": _thaw_jsonish(self.classification),
             "graph_inspection": _thaw_jsonish(self.graph_inspection),
             "research": _thaw_jsonish(self.research),
             "implementation": _thaw_jsonish(self.implementation),
             "warnings": list(self.warnings),
         }
         extra_keys = set(payload) - _EVIDENCE_KEYS
         if extra_keys:
             raise ValueError(f"Unexpected evidence keys: {sorted(extra_keys)}")
         return payload


 @dataclass(frozen=True)
 class AgentTurnResult:
     """Canonical public response envelope for one executor turn.

     ``disposition`` is internal execution metadata. It is intentionally omitted
     from serialization so public ``route`` remains the only route vocabulary
     consumers see.
     """

     route: str
     reply: str
     evidence: AgentEvidence = field(default_factory=AgentEvidence)
     candidate: dict[str, Any] | None = None
     no_candidate_reason: str | None = None
     disposition: str = ""

     def __post_init__(self) -> None:
         route = self.route if self.route in _PUBLIC_ROUTES else "respond"
         object.__setattr__(self, "route", route)

@@ -2339,169 +2538,176 @@ class AgentTurnResult:

 def _derive_no_candidate_reason(
     *,
     route: str,
     result: "ExecutorResult",
     implementation: Mapping[str, Any],
 ) -> str | None:
     if route not in _APPLY_ELIGIBLE_ROUTES:
         return "route_not_applyable"
     if result.graph is not None:
         return None
     if result.failure_stage == "implement":
         return "implementation_failed"
     if result.failure_kind is not None:
         return "implementation_failed"
     if result.report.implementation is None:
         return "implementation_skipped"
     if implementation and implementation.get("graph") is None:
         return "no_changes"
     return "no_graph"


 # ── executor result (final envelope leaf) ────────────────────────────────────

 # Keys from the durable handle_agent_edit response that the executor propagates
 # to the top-level serialized envelope (SD1, SD2).  Executor-owned fields
 # (graph, message, route, candidate, apply_eligible) always take priority.
 _DURABLE_ENVELOPE_TOP_LEVEL_KEYS: tuple[str, ...] = (
     "session_id",
     "turn_id",
     "baseline_turn_id",
     "baseline_graph_hash",
     "submit_graph_hash",
     "submit_structural_graph_hash",
     "submitted_client_graph_hash",
     "submitted_client_structural_graph_hash",
     "candidate_graph_hash",
     "candidate_structural_graph_hash",
     "outcome",
     "apply_eligibility",
     "graph_unchanged",
     "no_candidate_reason",
     "change_details",
     "runtime_dependencies",
     "audit_ref",
     "artifacts",
     "gates",
     "debug",
     "contract_version",
 )


 @dataclass(frozen=True)
 class ExecutorResult:
     """Final executor output.

     ``ok`` mirrors the existing success/failure convention.  ``report`` carries
     plan + phase outputs.  ``graph`` is the (optionally edited) canvas.
     ``reply`` is the user-facing prose produced by the reply phase.
     """

     ok: bool = True
     report: Report = field(default_factory=Report)
     graph: dict[str, Any] | None = None
     reply: str | None = None
     failure_kind: str | None = None
     failure_stage: str | None = None
     failure_message: str | None = None

     @property
     def turn(self) -> AgentTurnResult:
         return AgentTurnResult.from_executor_result(self)

     def to_dict(self) -> dict[str, Any]:
         payload: dict[str, Any] = {
             "ok": self.ok,
             "report": self.report.to_dict(),
         }
         usage_payload = coerce_deepseek_usage(self.report.deepseek_usage)
         payload["deepseek_usage"] = usage_payload
+        payload["model_attempts"] = [
+            _thaw_jsonish(item) for item in self.report.model_attempts
+        ]
         if self.report.deepseek_est_cost_usd is not None:
             payload["deepseek_est_cost_usd"] = float(self.report.deepseek_est_cost_usd)
         if isinstance(self.report.deepseek_cost_basis, str) and self.report.deepseek_cost_basis:
             payload["deepseek_cost_basis"] = self.report.deepseek_cost_basis
         # Propagate durable envelope fields from the implementation
         # response (SD1, SD2) so downstream consumers see session_id,
         # turn_id, hashes, outcome, apply_eligibility, change_details,
         # audit/artifact refs, gates, debug, and contract_version at
         # the top level.  Executor-owned fields (graph, message, route,
         # candidate, apply_eligible) take priority over any collisions.
         impl = self.report.implementation
         if impl is not None and impl.durable_response is not None:
             dr = impl.durable_response
             for key in _DURABLE_ENVELOPE_TOP_LEVEL_KEYS:
                 value = dr.get(key)
                 if value is not None:
                     payload[key] = _thaw_jsonish(value)
         payload.update(self.turn.to_dict())
         if self.graph is not None:
             payload["graph"] = self.graph
         if self.failure_kind is not None:
             payload["failure_kind"] = self.failure_kind
         if self.failure_stage is not None:
             payload["failure_stage"] = self.failure_stage
         if self.failure_message is not None:
             payload["failure_message"] = self.failure_message
         return payload

     @classmethod
     def success(
         cls,
         *,
         report: Report | None = None,
         graph: dict[str, Any] | None = None,
         reply: str | None = None,
     ) -> "ExecutorResult":
         return cls(ok=True, report=report or Report(), graph=graph, reply=reply)

     @classmethod
     def failure(
         cls,
         *,
         kind: str,
         stage: str,
         message: str,
         report: Report | None = None,
     ) -> "ExecutorResult":
         return cls(
             ok=False,
             report=report or Report(),
             failure_kind=kind,
             failure_stage=stage,
             failure_message=message,
         )


 __all__ = [
     "AgentEvidence",
     "AgentTurnResult",
     "ClassifyDecision",
     "ExecutorRequest",
     "ExecutorResult",
     "GraphFacts",
     "ImplementationResult",
     "InspectionSummary",
     "PrecedentAdaptationPlan",
     "PrecedentOption",
     "PrecedentPacket",
     "ReadinessReport",
     "Report",
     "ResearchResult",
     "RevisionEvidence",
     "ScopedDiff",
     "SelectedPrecedent",
     "ManifestBoundaryAnchor",
     "ManifestInquiryCoverage",
     "ManifestInternalEdge",
     "ManifestNode",
     "ManifestOversized",
     "ManifestValidation",
+    "ModelAttemptEvidence",
     "TopologyFindings",
     "TopologyManifest",
     "WorkflowSlice",
     "adaptation_plan_actionability",
     "adaptation_plan_actionability_payload",
     "build_topology_manifest",
+    "coerce_model_attempts",
     "is_actionable_adaptation_plan",
+    "normalize_model_endpoint",
+    "redact_model_preview",
     "warning_detail_from_exception",
 ]

exec
/bin/zsh -lc "sed -n '1,240p' .oracle/briefs/batch-B01.md && git show e33f0260:.oracle/briefs/batch-B01.md | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
# MEGADO BATCH B01 [HARD] — Typed failures and unified attempt provenance

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — you are the executor (GPT-5.6 Sol, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context
G0-T4 already added failed-call evidence (parse_reason, raw preview, finish reason, tokens, model, phase, endpoint) at classify+reply, and G0R closed the scorer/narrator. B01 makes model-attempt evidence a UNIFIED contract across success AND failure, typed, with redaction. B07-lite consumes this contract — do not create a second metadata format.

## Tasks (from .oracle/tasklist.md B01)

1. **One additive model-attempt evidence contract** across worker, runtime, provider/backend, executor, artifacts, and harness.
2. **Distinguish failure types**: empty response; malformed non-empty JSON; non-JSON content; missing required fields; timeout; capacity/provider failure.
3. **Persist on every successful AND failed attempt**: phase and attempt; requested and resolved model; adapter; actual provider and transport; normalized endpoint; finish reason; token usage.
4. **Persist bounded raw previews only for failures** (never for success).
5. **Fix the three success-path runtime stripping seams** (find where successful-call provenance is currently stripped/dropped in runtime/worker/agent_backend) and merge worker-observed metadata into batch audit metadata and final report artifacts.
6. **Permit a fresh-transport retry ONLY for typed empty responses** — never derive infra status from response wording (G0-T3 already gates on completion_tokens==0; keep that).
7. **Serialize unavailable non-Hermes provenance as `unknown`**; never infer.

## Key files
- vibecomfy/comfy_nodes/agent/worker.py, runtime.py, provider.py
- vibecomfy/executor/agent_backend.py, core.py, contracts.py, provenance.py
- vibecomfy/agent/artifacts.py
- tests/test_agent_runtime_adapter.py, tests/test_headless_agent_artifacts.py, tests/test_executor_contracts.py, tests/test_live_agentic_runner_persistence.py

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```
Expected exit 0. Add focused tests for the typed failure distinctions and success-path provenance (fixtures: empty vs malformed non-empty vs non-JSON vs missing-field vs timeout vs capacity).

## Acceptance
- Every failure type serializes distinctly.
- Successful classify, reply, and batch calls retain provenance through final artifacts.
- Requested vs resolved model remain distinct across routing/retries.
- Typed empty evidence reaches the existing retry; malformed non-empty stays product_fail.
- Unsupported routes report explicit unknowns.
- Redaction: keys, authorization data, secret URL params cannot persist (negative fixture).

## Report
Return: contract shape (field names), files changed, failure-type taxonomy, success-path seam fixes, redaction proof, pytest output. Do NOT commit.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
# MEGADO BATCH B01 [HARD] — Typed failures and unified attempt provenance

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — you are the executor (GPT-5.6 Sol, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context
G0-T4 already added failed-call evidence (parse_reason, raw preview, finish reason, tokens, model, phase, endpoint) at classify+reply, and G0R closed the scorer/narrator. B01 makes model-attempt evidence a UNIFIED contract across success AND failure, typed, with redaction. B07-lite consumes this contract — do not create a second metadata format.

## Tasks (from .oracle/tasklist.md B01)

1. **One additive model-attempt evidence contract** across worker, runtime, provider/backend, executor, artifacts, and harness.
2. **Distinguish failure types**: empty response; malformed non-empty JSON; non-JSON content; missing required fields; timeout; capacity/provider failure.
3. **Persist on every successful AND failed attempt**: phase and attempt; requested and resolved model; adapter; actual provider and transport; normalized endpoint; finish reason; token usage.
4. **Persist bounded raw previews only for failures** (never for success).
5. **Fix the three success-path runtime stripping seams** (find where successful-call provenance is currently stripped/dropped in runtime/worker/agent_backend) and merge worker-observed metadata into batch audit metadata and final report artifacts.
6. **Permit a fresh-transport retry ONLY for typed empty responses** — never derive infra status from response wording (G0-T3 already gates on completion_tokens==0; keep that).
7. **Serialize unavailable non-Hermes provenance as `unknown`**; never infer.

## Key files
- vibecomfy/comfy_nodes/agent/worker.py, runtime.py, provider.py
- vibecomfy/executor/agent_backend.py, core.py, contracts.py, provenance.py
- vibecomfy/agent/artifacts.py
- tests/test_agent_runtime_adapter.py, tests/test_headless_agent_artifacts.py, tests/test_executor_contracts.py, tests/test_live_agentic_runner_persistence.py

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```
Expected exit 0. Add focused tests for the typed failure distinctions and success-path provenance (fixtures: empty vs malformed non-empty vs non-JSON vs missing-field vs timeout vs capacity).

## Acceptance
- Every failure type serializes distinctly.
- Successful classify, reply, and batch calls retain provenance through final artifacts.
- Requested vs resolved model remain distinct across routing/retries.
- Typed empty evidence reaches the existing retry; malformed non-empty stays product_fail.
- Unsupported routes report explicit unknowns.
- Redaction: keys, authorization data, secret URL params cannot persist (negative fixture).

## Report
Return: contract shape (field names), files changed, failure-type taxonomy, success-path seam fixes, redaction proof, pytest output. Do NOT commit.

exec
/bin/zsh -lc 'git diff --unified=50 16d80bbe..e33f0260 -- vibecomfy/comfy_nodes/agent/worker.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/comfy_nodes/agent/worker.py b/vibecomfy/comfy_nodes/agent/worker.py
index ef9ff064..da5c7909 100644
--- a/vibecomfy/comfy_nodes/agent/worker.py
+++ b/vibecomfy/comfy_nodes/agent/worker.py
@@ -18,205 +18,272 @@ where ComfyUI is never imported makes those bare imports resolve to the agent's
 own modules, and also isolates the agent's HTTP/asyncio state from ComfyUI's
 aiohttp event loop.

 Protocol:
     python worker.py <request.json> <result.json>

 ``request.json`` -> {"agent_id": str, "agent_kwargs": {...},
                      "system_message": str|null, "user_message": str,
                      "response_contract": "python"|"delta"|"batch_repl"|"json"|"text"}
 ``result.json``  <- {"python": str, "message": str} or {"delta": list, "message": str} on success
                     {"content": str} for batch_repl / json / text responses
                     {"json": dict} additionally for json contract
                     {"error": str, "error_type": str} on failure

 ``agent_kwargs`` are the AIAgent constructor kwargs the parent resolved for the
 route (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
 flags, ...). ``DeepSeekAdapter`` builds only a minimal kwargs set itself, so we
 inject a factory that merges the parent's kwargs verbatim — this reproduces the
 exact AIAgent construction the worker used before the dispatch seam was added.

 stdout/stderr may contain agent chatter; the parent only reads ``result.json``.
 """

 from __future__ import annotations

 import json
 import logging
 import os
 from pathlib import Path
 import re
 import sys
 import time
 from typing import Any


 def _bootstrap_repo_root() -> None:
     """Make this file runnable by absolute path from a neutral cwd."""
     repo_root = Path(__file__).resolve().parents[3]
     repo_root_str = str(repo_root)
     if repo_root_str not in sys.path:
         sys.path.insert(0, repo_root_str)


 _bootstrap_repo_root()

 from vibecomfy.agent.deepseek_usage import (
     add_deepseek_usage,
     coerce_deepseek_usage,
     empty_deepseek_usage,
 )
+from vibecomfy.executor.contracts import (
+    ModelAttemptEvidence,
+    normalize_model_endpoint,
+    redact_model_preview,
+)
 from vibecomfy.executor.profiler import profiler_log, profiler_span, short_text, utc_now_iso

 LOGGER = logging.getLogger(__name__)


 def _extract_json_object(text: str) -> dict:
     stripped = (text or "").strip()
     if stripped.startswith("```"):
         match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
         if match:
             stripped = match.group(1).strip()
     try:
         parsed = json.loads(stripped)
     except json.JSONDecodeError:
         # The model often emits the JSON object followed by EXTRA data (a second
         # object, or trailing prose / reasoning), which makes a strict json.loads
         # raise "Extra data" and fail the whole turn. A greedy {.*} regex is worse —
         # on "{obj}{extra}" it captures BOTH and still fails. Decode the FIRST
         # complete object from the first '{' with raw_decode and ignore the rest.
         start = stripped.find("{")
         if start == -1:
             raise
         parsed, _ = json.JSONDecoder().raw_decode(stripped[start:])
     if not isinstance(parsed, dict):
         raise ValueError("Agent response JSON was not an object.")
     return parsed


 def _raw_response_preview(text: str | None, *, limit: int = 1200) -> str | None:
     """Return a bounded, whitespace-normalized preview of a raw model response."""
-    if not isinstance(text, str):
-        return None
-    normalized = " ".join(text.strip().split())
-    if not normalized:
-        return None
-    if len(normalized) <= limit:
-        return normalized
-    return normalized[: limit - 1].rstrip() + "…"
-
-
-def _parse_failure_reason(exc: BaseException, raw_text: str | None) -> str:
-    """Classify a worker response-parse failure into the shared evidence vocabulary.
-
-    Values are ``empty`` | ``missing_content`` | ``malformed_json`` |
-    ``non_json_content`` — the same vocabulary the classify/reply evidence
-    plumbing persists upstream.
-    """
+    return redact_model_preview(text, limit=limit)
+
+
+def _model_attempt_failure_type(exc: BaseException, raw_text: str | None) -> str:
+    """Classify an observed failed call without consulting response wording."""
     if raw_text is not None and not str(raw_text).strip():
-        return "empty"
+        return "empty_response"
+    if isinstance(exc, TimeoutError):
+        return "timeout"
     if isinstance(exc, json.JSONDecodeError):
-        return "malformed_json"
+        return "malformed_json" if "{" in (raw_text or "") else "non_json_content"
     message = str(exc).lower()
-    if "not an object" in message or "non_json" in message:
+    if "not an object" in message:
         return "non_json_content"
     if isinstance(exc, ValueError):
-        if "must include" in message or "field" in message or "empty" in message:
-            return "missing_content"
+        if "must include" in message or "field" in message:
+            return "missing_required_fields"
         return "malformed_json"
-    return "missing_content"
+    return "provider_failure"
+
+
+def _worker_provider_transport(
+    request: dict[str, Any],
+) -> tuple[str, str, str]:
+    agent_id = str(request.get("agent_id") or "hermes")
+    agent_kwargs = request.get("agent_kwargs")
+    if not isinstance(agent_kwargs, dict):
+        agent_kwargs = {}
+    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
+    if agent_id != "hermes":
+        return "unknown", "unknown", endpoint
+    if "openrouter.ai" in endpoint:
+        return "openrouter", "openrouter", endpoint
+    if "deepseek.com" in endpoint:
+        return "deepseek", "native", endpoint
+    if endpoint != "unknown":
+        return "unknown", "openai_compatible", endpoint
+    return "unknown", "unknown", endpoint
+
+
+def _model_attempt(
+    request: dict[str, Any],
+    profiling_context: dict[str, Any],
+    worker_metadata: dict[str, Any] | None,
+    *,
+    outcome: str,
+    failure_type: str | None = None,
+    raw_text: str | None = None,
+) -> dict[str, Any]:
+    agent_kwargs = request.get("agent_kwargs")
+    if not isinstance(agent_kwargs, dict):
+        agent_kwargs = {}
+    metadata = worker_metadata if isinstance(worker_metadata, dict) else {}
+    usage = metadata.get("deepseek_usage")
+    if not isinstance(usage, dict) or not (
+        int(usage.get("n_calls") or 0) > 0
+        or any(isinstance(usage.get(key), (int, float)) for key in (
+            "prompt_tokens", "completion_tokens", "total_tokens"
+        ))
+    ):
+        usage = {}
+    provider, transport, endpoint = _worker_provider_transport(request)
+    return ModelAttemptEvidence(
+        phase=profiling_context.get("backend_phase") or "agent_turn",
+        attempt=profiling_context.get("model_attempt") or 1,
+        outcome=outcome,
+        failure_type=failure_type,
+        requested_model=request.get("requested_model"),
+        resolved_model=agent_kwargs.get("model") or request.get("model"),
+        adapter=request.get("agent_id") or "hermes",
+        provider=provider,
+        transport=transport,
+        endpoint=endpoint,
+        finish_reason=metadata.get("finish_reason"),
+        token_usage=usage,
+        raw_response_preview=raw_text if outcome == "failure" else None,
+    ).to_dict()


 def _persist_parse_evidence(
     out: dict[str, Any],
     exc: BaseException,
     raw_text: str,
     worker_metadata: dict[str, Any] | None,
     request: dict[str, Any],
     profiling_context: dict[str, Any],
 ) -> None:
     """Persist bounded parse-failure evidence on the worker failure envelope.

     Additive only — the existing ``error`` / ``error_type`` envelope shape is
     unchanged. Mirrors the batch-repl ``model_response`` detail capture
     (parse_reason + raw preview) and adds the observed usage, model, phase,
     endpoint, and finish reason so classify/reply attempts are diagnosable.
     """
     agent_kwargs = (
         request.get("agent_kwargs")
         if isinstance(request.get("agent_kwargs"), dict)
         else {}
     )
+    failure_type = _model_attempt_failure_type(exc, raw_text)
     preview = _raw_response_preview(raw_text)
     if preview:
         out["raw_response_preview"] = preview
-    out["parse_reason"] = _parse_failure_reason(exc, raw_text)
+    out["parse_reason"] = {
+        "empty_response": "empty",
+        "missing_required_fields": "missing_content",
+    }.get(failure_type, failure_type)
     model = request.get("model") or agent_kwargs.get("model")
     if model:
         out["model"] = model
     phase = profiling_context.get("backend_phase") or "agent_turn"
     if phase:
         out["phase"] = phase
     endpoint = agent_kwargs.get("base_url")
     if endpoint:
-        out["endpoint"] = endpoint
+        out["endpoint"] = normalize_model_endpoint(endpoint)
     if isinstance(worker_metadata, dict):
         finish_reason = worker_metadata.get("finish_reason")
         if isinstance(finish_reason, str) and finish_reason.strip():
             out["finish_reason"] = finish_reason.strip()
         usage = worker_metadata.get("deepseek_usage")
         if isinstance(usage, dict):
             out["deepseek_usage"] = usage
             for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                 value = usage.get(key)
                 if isinstance(value, int):
                     out[key] = value
+    out["model_attempts"] = [
+        _model_attempt(
+            request,
+            profiling_context,
+            worker_metadata,
+            outcome="failure",
+            failure_type=failure_type,
+            raw_text=raw_text,
+        )
+    ]


 def _anchor_agent_package_on_syspath() -> None:
     """Put the agent package dir on sys.path so its bare top-level imports
     (``utils``, ``model_tools``, ``toolsets``, ...) resolve to its own modules.

     Best-effort: if the legacy ``arnold.pipelines.megaplan.agent`` package is not
     importable (e.g. a slimmed install), the adapter still drives its own lazy
     import; we just skip the path anchor.
     """
     try:
         import arnold.pipelines.megaplan.agent as _agent_pkg
     except ImportError:
         return
     agent_dir = os.path.dirname(_agent_pkg.__file__)
     if agent_dir and agent_dir not in sys.path:
         sys.path.insert(0, agent_dir)


 def _build_request(
     *,
     agent_id: str,
     user_message: str,
     system_message: str | None,
     model: str | None = None,
     effort: str | None = None,
 ):
     """Construct the tool-free single-shot AgentRequest for a panel turn.

     Tool-free single-shot: empty ``toolsets`` in metadata -> the DeepSeekAdapter
     does not enable any toolset, and the parent kwargs already carry
     ``enabled_toolsets=[]`` / ``max_iterations=1``. No ``output_schema`` /
     ``response_format``: the panel parses its own python/delta/batch fences from
     the raw text, so the adapter returns ``raw_output`` unchanged.
     """
     from arnold.agent import AgentRequest

     return AgentRequest(
         agent=agent_id,
         mode="default",
         model=model,
         resolved_model=model,
         effort=effort,
         prompt=user_message,
         system_prompt=system_message,
         read_only=True,
         metadata={"toolsets": []},
     )


@@ -477,89 +544,107 @@ def main() -> int:
             raw_text = text
             span.update(raw_text_length=len(text or ""))
             if response_contract == "batch_repl":
                 if not isinstance(text, str) or not text.strip():
                     raise ValueError("Agent returned an empty batch_repl response.")
                 out = {"content": text}
             elif response_contract == "text":
                 if not isinstance(text, str) or not text.strip():
                     raise ValueError("Agent returned an empty text response.")
                 out = {"content": text}
             elif response_contract == "json":
                 if not isinstance(text, str) or not text.strip():
                     raise ValueError("Agent returned an empty json response.")
                 payload = _extract_json_object(text)
                 out = {"content": text, "json": payload}
             elif response_contract in ("python", "delta"):
                 payload = _extract_json_object(text or "")
                 message = payload.get("message")
                 if not isinstance(message, str):
                     raise ValueError("Agent JSON must include a string `message` field.")
                 if response_contract == "delta":
                     delta = payload.get("delta")
                     if not isinstance(delta, list):
                         raise ValueError("Agent JSON must include a list `delta` field.")
                     out = {"delta": delta, "message": message}
                 else:  # python
                     python = payload.get("python")
                     if not isinstance(python, str):
                         raise ValueError("Agent JSON must include a string `python` field.")
                     out = {"python": python, "message": message}
             else:
                 raise ValueError(f"Unsupported response_contract {response_contract!r}.")
             if isinstance(worker_metadata, dict):
                 out.update(worker_metadata)
             # Self-describing envelope: carry the resolved model/phase/endpoint
             # so upstream classify/reply evidence plumbing can persist them on a
             # later parse failure without re-resolving provider internals.
             agent_kwargs = (
                 request.get("agent_kwargs")
                 if isinstance(request.get("agent_kwargs"), dict)
                 else {}
             )
             model = request.get("model") or agent_kwargs.get("model")
             if model:
                 out["model"] = model
             phase = profiling_context.get("backend_phase") or "agent_turn"
             if phase:
                 out["phase"] = phase
             endpoint = agent_kwargs.get("base_url")
             if endpoint:
-                out["endpoint"] = endpoint
+                out["endpoint"] = normalize_model_endpoint(endpoint)
+            out["model_attempts"] = [
+                _model_attempt(
+                    request,
+                    profiling_context,
+                    worker_metadata,
+                    outcome="success",
+                )
+            ]
     except Exception as exc:  # noqa: BLE001 - report all failures to parent
         out = {"error": str(exc), "error_type": type(exc).__name__}
         # A LookupError means no adapter is registered for the requested agent id
         # (e.g. codex/claude not wired into the default dispatcher yet); an
         # ImportError means the backend's heavy deps are missing. Both are setup
         # faults — flag them so the parent surfaces a non-retryable
         # runtime-unavailable signal rather than a transient provider error.
         if isinstance(exc, (LookupError, ImportError)):
             out["runtime_unavailable"] = True
         if raw_text is not None:
             # The raw response was received but discarded on a parse/content
             # failure — persist bounded evidence on the failure envelope instead
             # of losing it (mirrors the batch-repl model_response detail).
             _persist_parse_evidence(
                 out,
                 exc,
                 raw_text,
                 worker_metadata,
                 request,
                 profiling_context,
             )
+        else:
+            out["model_attempts"] = [
+                _model_attempt(
+                    request,
+                    profiling_context,
+                    worker_metadata,
+                    outcome="failure",
+                    failure_type=_model_attempt_failure_type(exc, raw_text),
+                )
+            ]

     out["_profiling"] = {
         **profiling_context,
         "agent_id": request.get("agent_id") or "hermes",
         "response_contract": request.get("response_contract") or "python",
         "started_at": worker_started_at,
         "ended_at": utc_now_iso(),
         "elapsed_ms": max(0, int((time.monotonic() - worker_started_monotonic) * 1000)),
     }

     with open(result_path, "w", encoding="utf-8") as fh:
         json.dump(out, fh)
     return 0


 if __name__ == "__main__":
     raise SystemExit(main())

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- vibecomfy/comfy_nodes/agent/provider.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/comfy_nodes/agent/provider.py b/vibecomfy/comfy_nodes/agent/provider.py
index cad71ca2..935aa56f 100644
--- a/vibecomfy/comfy_nodes/agent/provider.py
+++ b/vibecomfy/comfy_nodes/agent/provider.py
@@ -1,39 +1,44 @@
 from __future__ import annotations

 import importlib
 import dataclasses
 import json
 import logging
 import os
 import re
 from dataclasses import dataclass
 from pathlib import Path
 from typing import Any, Callable, Mapping

 from .audit import redact_closed_set
 from .contracts import AGENT_EDIT_TURN_CONTRACT_VERSION
+from vibecomfy.executor.contracts import (
+    ModelAttemptEvidence,
+    coerce_model_attempts,
+    redact_model_preview,
+)


 LOGGER = logging.getLogger(__name__)

 DEFAULT_ROUTE = "arnold"
 DEFAULT_MODEL = "agent-edit"
 DEFAULT_HERMES_ENV_PATH = Path("~/.hermes/.env")
 SUPPORTED_BROWSER_ROUTES = ("auto", "openrouter", "anthropic", "openai-codex")

 _ARNOLD_GUIDANCE = (
     "Use local Arnold/Hermes setup for this route. Configure ARNOLD_API_KEY or "
     "HERMES_API_KEY locally; browser-submitted API keys are not stored."
 )
 _ANTHROPIC_GUIDANCE = (
     "Anthropic/Claude runs through local Arnold/Hermes. Acknowledge the ToS in "
     "the UI and configure local ARNOLD_API_KEY or HERMES_API_KEY; browser keys "
     "are not accepted."
 )
 _CODEX_GUIDANCE = (
     "OpenAI Codex runs through local Arnold/Hermes. Configure local "
     "ARNOLD_API_KEY or HERMES_API_KEY; browser keys are not accepted."
 )
 _WORKFLOW_RESEARCH_GUIDANCE = (
     "When Research findings mention workflows/templates, explain that users can explore ready "
     "templates with `vibecomfy workflows list --ready`, copy one with "
@@ -168,78 +173,89 @@ class AgentRouteDescriptor:
             "tos_acknowledgement_required": self.tos_acknowledgement_required,
         }


 def _extract_json_object(text: str) -> dict[str, Any]:
     stripped = text.strip()
     if stripped.startswith("```"):
         match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
         if match:
             stripped = match.group(1).strip()
     try:
         parsed = json.loads(stripped)
     except json.JSONDecodeError as exc:
         raise MalformedModelJSON(
             "Agent response was not valid JSON with keys `python` and `message`."
         ) from exc
     if not isinstance(parsed, dict):
         raise MalformedModelJSON("Agent response must be a JSON object.")
     return parsed


 _BATCH_FENCE_RE = re.compile(r"```batch\s*\n(.*?)```", re.DOTALL)


 def _preview_raw_model_response(text: str | None, *, limit: int = 1200) -> str | None:
-    if not isinstance(text, str):
-        return None
-    normalized = " ".join(text.strip().split())
-    if not normalized:
-        return None
-    if len(normalized) <= limit:
-        return normalized
-    return normalized[: limit - 1].rstrip() + "…"
+    return redact_model_preview(text, limit=limit)


 # Additive evidence attributes that classify/reply failure plumbing forwards
 # across provider boundaries (worker envelope -> runtime error -> provider
 # error -> executor failure envelope). The failure envelope's public shape is
 # unchanged; these attributes only ride on exceptions in between.
 _EVIDENCE_ATTRS = (
     "worker_result",
+    "model_attempts",
     "parse_reason",
     "raw_response_preview",
     "finish_reason",
     "completion_tokens",
     "prompt_tokens",
     "total_tokens",
     "model",
     "phase",
     "endpoint",
 )


+def _audit_with_runtime_attempts(
+    audit_metadata: Mapping[str, Any] | None,
+    response: Any,
+) -> dict[str, Any]:
+    """Merge worker-observed canonical attempt evidence into provider audit data."""
+    merged = dict(audit_metadata or {})
+    if not isinstance(response, Mapping):
+        return merged
+    attempts = coerce_model_attempts(response.get("model_attempts"))
+    if attempts:
+        merged["model_attempts"] = [dict(item) for item in attempts]
+    usage = response.get("deepseek_usage")
+    if isinstance(usage, Mapping):
+        merged["deepseek_usage"] = dict(usage)
+    return merged
+
+
 def _forward_evidence_attrs(source: BaseException, target: BaseException) -> None:
     """Copy additive evidence attributes from *source* onto *target*."""
     for name in _EVIDENCE_ATTRS:
         if getattr(target, name, None) is not None:
             continue
         value = getattr(source, name, None)
         if value is None:
             continue
         try:
             setattr(target, name, value)
         except Exception:  # noqa: BLE001 - evidence attachment is best-effort
             pass


 def _attach_provider_context(
     exc: BaseException,
     *,
     model: str | None,
     phase: str | None,
 ) -> None:
     """Fill provider-known model/phase evidence when the exception lacks it."""
     if model and getattr(exc, "model", None) is None:
         try:
             setattr(exc, "model", model)
         except Exception:  # noqa: BLE001 - evidence attachment is best-effort
@@ -1004,72 +1020,73 @@ def _load_arnold_runtime() -> Any:
             "run_agent_turn_batch, run_agent_turn, or run"
         )
     LOGGER.warning("Arnold/Hermes runtime unavailable: %s", "; ".join(errors))
     raise ProviderError(
         "Arnold/Hermes runtime is unavailable. Install/configure Arnold or set "
         "VIBECOMFY_ARNOLD_RUNTIME_MODULE. Import attempts: " + "; ".join(errors)
     )


 def _runtime_has_execution_entrypoint(runtime: Any) -> bool:
     return any(
         callable(getattr(runtime, name, None))
         for name in ("run_model_turn", "run_agent_turn_batch", "run_agent_turn", "run")
     )


 def _normalize_agent_response(
     response: Any,
     *,
     route: str,
     model: str | None,
     audit_metadata: Mapping[str, Any] | None = None,
 ) -> AgentTurnResult:
     if isinstance(response, AgentTurnResult):
         return response
+    merged_audit = _audit_with_runtime_attempts(audit_metadata, response)
     if isinstance(response, str):
         payload = _extract_json_object(response)
     elif isinstance(response, Mapping):
         payload = dict(response)
         content = payload.get("content")
         if isinstance(content, str) and "python" not in payload:
             payload = _extract_json_object(content)
     else:
         raise MalformedModelJSON("Agent response must be a JSON string or object.")

     python = payload.get("python")
     message = payload.get("message")
     if not isinstance(python, str):
         raise MissingRequiredField("Agent JSON must include string key `python`.")
     if not isinstance(message, str):
         raise MissingRequiredField("Agent JSON must include string key `message`.")
     return AgentTurnResult(
         python=python,
         message=message,
         route=route,
         model=model,
-        audit_metadata=audit_metadata or {},
+        audit_metadata=merged_audit,
     )


 def _call_runtime(
     runtime: Any,
     *,
     task: str,
     python_source: str,
     route: str,
     model: str | None,
     effort: str | None = None,
 ) -> Any:
     messages = build_messages(task=task, python_source=python_source, execution_mode="sandboxed_loose")
     run_agent_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn", None)
     if callable(run_agent_turn_fn):
         return run_agent_turn_fn(
             task=task,
             python_source=python_source,
             route=route,
             model=model,
             effort=effort,
             messages=messages,
         )
     run_fn: Callable[..., Any] | None = getattr(runtime, "run", None)
     if callable(run_fn):
@@ -1208,113 +1225,116 @@ def run_agent_turn_delta(
             task=task,
             projection=projection,
             op_schema=schema,
             route=dispatch_route,
             model=selected_model,
             effort=effort,
         )
     except PermissionError as exc:
         raise AuthError(str(exc)) from exc
     except TimeoutError:
         raise
     except ImportError:
         # The agent runtime could not be loaded — a setup fault, not a
         # transient provider outage.  Preserve the type so it is classified
         # as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure.
         raise
     except (ProviderError, MalformedModelJSON, MissingRequiredField):
         raise
     except Exception as exc:
         raise ProviderError(str(exc)) from exc
     try:
         return normalize_delta_agent_response(
             response,
             route=dispatch_route,
             model=selected_model,
-            audit_metadata={
+            audit_metadata=_audit_with_runtime_attempts({
                 "provider": "arnold",
                 "requested_route": route_descriptor.requested_route,
                 "route_metadata": route_descriptor.to_dict(),
                 "legacy_deepseek_fallback_enabled": False,
                 "credential_presence": _credential_presence(),
                 "response_contract": "delta",
-            },
+            }, response),
         )
     except EditOpParseError as exc:
         raise MalformedModelJSON(str(exc), parse_reason=exc.code) from exc


 def _normalize_batch_response(
     response: Any,
     *,
     route: str,
     model: str | None,
     audit_metadata: Mapping[str, Any] | None = None,
 ) -> BatchTurnResult:
     """Normalize a raw runtime response into a :class:`BatchTurnResult`.

     Extracts the ```batch fenced block and surrounding prose via
     :func:`extract_batch_fence`.  The runtime may return a string (the raw
     model response) or a mapping with a ``content`` key.
     """
     if isinstance(response, BatchTurnResult):
         return response
+    merged_audit = _audit_with_runtime_attempts(audit_metadata, response)
     if isinstance(response, str):
         text = response
     elif isinstance(response, Mapping):
         payload = dict(response)
         content = payload.get("content")
         if isinstance(content, str) and "batch" not in payload:
             text = content
         elif isinstance(payload.get("batch"), str):
             batch_code = payload["batch"]
             message = normalize_user_markdown_message(payload.get("message", ""))
             return BatchTurnResult(
                 batch=batch_code,
                 message=message,
                 route=route,
                 model=model,
-                audit_metadata=audit_metadata or {},
+                audit_metadata=merged_audit,
             )
         else:
             text = str(response)
     else:
         raise MalformedModelJSON("Agent response must be a string or object.")
     if not text.strip():
         raise MalformedModelJSON(
-            "Agent batch_repl response was empty. Expected exactly one ```batch fenced block."
+            "Agent batch_repl response was empty. Expected exactly one ```batch fenced block.",
+            raw_response=text,
+            parse_reason="empty",
         )
     batch_code, prose = extract_batch_fence(text)
     # Preserve prose as-is (possibly empty); the backend synthesizer
     # (_synthesize_batch_repl_message) owns final message filling.
     message = prose.strip()
     return BatchTurnResult(
         batch=batch_code,
         message=message,
         route=route,
         model=model,
-        audit_metadata=audit_metadata or {},
+        audit_metadata=merged_audit,
     )


 def _call_batch_runtime(
     runtime: Any,
     *,
     task: str,
     messages: list[dict[str, str]],
     route: str,
     model: str | None,
     effort: str | None = None,
 ) -> Any:
     """Call the Arnold/Hermes runtime for a batch-REPL turn."""
     run_agent_turn_batch_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn_batch", None)
     if callable(run_agent_turn_batch_fn):
         return run_agent_turn_batch_fn(
             task=task,
             route=route,
             model=model,
             effort=effort,
             messages=messages,
         )
     run_agent_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn", None)
     if callable(run_agent_turn_fn):
         return run_agent_turn_fn(
@@ -1334,118 +1354,177 @@ def _call_batch_runtime(
             effort=effort,
             messages=messages,
             response_contract="batch_repl",
         )
     raise ProviderError(
         "Arnold/Hermes runtime does not expose run_agent_turn_batch, "
         "run_agent_turn, or run."
     )


 def _batch_retry_messages(
     messages: list[dict[str, str]],
     exc: BaseException,
 ) -> list[dict[str, str]]:
     prompt = _BATCH_REPL_PARSE_RETRY_PROMPT
     raw_preview = getattr(exc, "raw_response_preview", None)
     if isinstance(raw_preview, str) and raw_preview.strip():
         prompt = (
             f"{prompt}\n\n"
             "Previous response preview, for correction only:\n"
             f"{raw_preview.strip()}"
         )
     return [*messages, {"role": "system", "content": prompt}]


+def _batch_failure_type(exc: BaseException) -> str:
+    raw = getattr(exc, "raw_response", None)
+    if isinstance(raw, str) and not raw.strip():
+        return "empty_response"
+    reason = getattr(exc, "parse_reason", None)
+    if reason in {"missing_batch_fence"}:
+        return "missing_required_fields"
+    return "malformed_json"
+
+
+def _revise_failed_runtime_attempt(
+    response: Any,
+    exc: BaseException,
+) -> tuple[dict[str, Any], ...]:
+    if not isinstance(response, Mapping):
+        return ()
+    attempts = list(coerce_model_attempts(response.get("model_attempts")))
+    if not attempts:
+        return ()
+    latest = dict(attempts[-1])
+    latest.update({
+        "outcome": "failure",
+        "failure_type": _batch_failure_type(exc),
+        "raw_response_preview": getattr(exc, "raw_response", None),
+    })
+    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
+    attempts[-1] = revised
+    try:
+        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
+
+        replace_last_model_attempt(revised)
+    except Exception:  # noqa: BLE001 - evidence capture is additive
+        pass
+    exc.model_attempts = list(attempts)  # type: ignore[attr-defined]
+    return tuple(attempts)
+
+
+def _typed_empty_attempt(attempts: tuple[dict[str, Any], ...]) -> bool:
+    if not attempts:
+        return False
+    latest = attempts[-1]
+    usage = latest.get("token_usage")
+    return (
+        latest.get("failure_type") == "empty_response"
+        and isinstance(usage, Mapping)
+        and usage.get("completion_tokens") == 0
+    )
+
+
 def run_agent_turn_batch(
     task: str,
     messages: list[dict[str, str]],
     *,
     route: str | None = None,
     model: str | None = None,
     effort: str | None = None,
 ) -> BatchTurnResult:
     """Run a single batch-REPL turn through the Arnold/Hermes provider.

     Sends *messages* (built by :func:`build_batch_messages`) to the model
     and normalizes the response through :func:`extract_batch_fence` instead
     of JSON parsing.  Returns a :class:`BatchTurnResult` with the fenced
     batch code and surrounding prose.

     Parameters
     ----------
     task:
         The user's natural-language edit request.
     messages:
         Pre-built chat messages from :func:`build_batch_messages`.
     route:
         Optional provider route name.  Resolved via :func:`_resolve_agent_route`.
     model:
         Optional model identifier.  Falls back to ``VIBECOMFY_AGENT_MODEL``.
     """
     route_descriptor = _resolve_agent_route(route)
     selected_route = route_descriptor.normalized_route
     dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
     selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
     runtime = _load_arnold_runtime()
     audit_metadata: dict[str, Any] = {
         "provider": "arnold",
         "requested_route": route_descriptor.requested_route,
         "route_metadata": route_descriptor.to_dict(),
         "legacy_deepseek_fallback_enabled": False,
         "credential_presence": _credential_presence(),
         "response_contract": "batch_repl",
     }
     try:
         attempts = 3
         retry_count = 0
         last_exc: MalformedModelJSON | MissingRequiredField | None = None
         current_messages = messages
+        attempt_log: list[dict[str, Any]] = []
         for attempt_index in range(attempts):
             if attempt_index > 0 and last_exc is not None:
                 current_messages = _batch_retry_messages(messages, last_exc)
             response = _call_batch_runtime(
                 runtime,
                 task=task,
                 messages=current_messages,
                 route=dispatch_route,
                 model=selected_model,
                 effort=effort,
             )
             try:
                 result = _normalize_batch_response(
                     response,
                     route=dispatch_route,
                     model=selected_model,
                     audit_metadata=audit_metadata,
                 )
             except (MalformedModelJSON, MissingRequiredField) as exc:
+                failed_attempts = _revise_failed_runtime_attempt(response, exc)
+                attempt_log.extend(failed_attempts)
                 last_exc = exc
-                if attempt_index >= attempts - 1:
+                if attempt_index >= attempts - 1 or not _typed_empty_attempt(failed_attempts):
                     raise
                 retry_count += 1
                 continue
+            current_attempts = list(
+                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
+            )
+            if attempt_log:
+                metadata = dict(result.audit_metadata or {})
+                metadata["model_attempts"] = [*attempt_log, *current_attempts]
+                result = dataclasses.replace(result, audit_metadata=metadata)
             if retry_count:
                 metadata = dict(result.audit_metadata or {})
                 metadata["batch_repl_retry"] = {
                     "count": retry_count,
                     "reason": str(last_exc) if last_exc is not None else "",
                     "parse_reason": getattr(last_exc, "parse_reason", None),
                     "raw_response_preview": getattr(last_exc, "raw_response_preview", None),
                 }
                 result = dataclasses.replace(result, audit_metadata=metadata)
             return result
         if last_exc is not None:
             raise last_exc
         raise ProviderError("Agent batch_repl provider exited without a response.")
     except PermissionError as exc:
         raise AuthError(str(exc)) from exc
     except TimeoutError:
         raise
     except ImportError:
         # The agent runtime could not be loaded — a setup fault, not a
         # transient provider outage.  Preserve the type so it is classified
         # as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure.
         raise
     except (ProviderError, MalformedModelJSON, MissingRequiredField):
         raise
     except Exception as exc:

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- vibecomfy/comfy_nodes/agent/runtime.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/comfy_nodes/agent/runtime.py b/vibecomfy/comfy_nodes/agent/runtime.py
index 9ebf3b26..5a1c05a0 100644
--- a/vibecomfy/comfy_nodes/agent/runtime.py
+++ b/vibecomfy/comfy_nodes/agent/runtime.py
@@ -25,134 +25,152 @@ Routes
   or local OAuth). Honest about availability: status reports ``ok`` only when a
   usable credential resolves.

 Everything heavy (provider routing, retries, OAuth resolution) is handled by the
 real ``AIAgent`` backend; this file is intentionally thin.
 """

 from __future__ import annotations

 import contextvars
 import json
 import os
 import subprocess
 import sys
 import tempfile
 import time
 import logging
 from pathlib import Path
 from typing import Any, Mapping, Sequence

 from vibecomfy.agent.deepseek_usage import (
     add_deepseek_usage,
     coerce_deepseek_usage,
     empty_deepseek_usage,
 )
+from vibecomfy.executor.contracts import (
+    ModelAttemptEvidence,
+    coerce_model_attempts,
+    normalize_model_endpoint,
+)
 from vibecomfy.executor.profiler import (
     new_profile_id,
     profiler_log,
     profiler_span,
     short_text,
 )

 # How long to wait for a single agent turn (subprocess) before giving up.
 _TURN_TIMEOUT_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "180"))
 _WORKER_PATH = str(Path(__file__).with_name("worker.py"))

-# A single model turn can stall on a transient provider/transport hiccup — a
-# connection that opens but never returns a byte. When that happens the whole
-# worker subprocess runs into the hard ``_TURN_TIMEOUT_SECONDS`` kill. Before
-# this retry layer existed, that one flaky network moment became a hard turn
-# failure (``TimeoutError``) the user had to re-submit by hand — exactly the
-# "make it img2img" symptom: one turn timed out at 180s, the identical retry
-# succeeded on a fresh connection. So: on a transient stall, spawn a fresh
-# worker (fresh connection) a bounded number of times before surfacing failure.
-# Worst case is ``_WORKER_TRANSIENT_MAX_ATTEMPTS`` * ``_TURN_TIMEOUT_SECONDS``.
+# A fresh worker/transport retry is deliberately narrow: only a canonical
+# empty-response failure with observed zero completion tokens may consume the
+# extra attempts. Timeouts, capacity/provider errors, and malformed content do
+# not retry here.
 _WORKER_TRANSIENT_MAX_ATTEMPTS = max(1, int(os.getenv("VIBECOMFY_AGENT_TURN_RETRIES", "3")))
 _WORKER_TRANSIENT_BACKOFF_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_RETRY_BACKOFF", "2.0"))
-
-# Worker-reported ``error_type`` values that are NOT transient infra failures
-# and so must not consume a retry slot. Auth and setup/import faults will not
-# recover by retrying; ``JSONDecodeError``/``ValueError`` are content problems
-# that the response-contract retry layer (``run_model_turn``) handles by
-# re-prompting with a JSON nudge, so they are excluded here to avoid double
-# handling. Everything else a worker reports (connection reset, read timeout,
-# 429, 5xx, ...) is treated as transient.
-_WORKER_NON_TRANSIENT_ERROR_TYPES = {
-    "AuthError",
-    "AuthenticationError",
-    "PermissionError",
-    "JSONDecodeError",
-    "ValueError",
-}
 LOGGER = logging.getLogger(__name__)
 _DEEPSEEK_USAGE_CAPTURE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
     "vibecomfy_deepseek_usage_capture",
     default=None,
 )
+_MODEL_ATTEMPT_CAPTURE: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
+    "vibecomfy_model_attempt_capture",
+    default=None,
+)

 _CANONICAL_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
 _OPENROUTER_MODEL = os.getenv("VIBECOMFY_OPENROUTER_MODEL", "openrouter:deepseek/deepseek-v4-pro")
 _OPENROUTER_BASE_URL = os.getenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
 _OPENROUTER_MAX_TOKENS = int(os.getenv("VIBECOMFY_OPENROUTER_MAX_TOKENS", "2048"))

-_JSON_RETRY_NUDGE = (
-    "Your previous reply was not valid JSON. Reply with ONLY one strict JSON "
-    "object matching the requested schema. Do not include markdown fences, "
-    "comments, reasoning text, or trailing prose."
-)
-
 # Arnold/Hermes (Claude etc.) default model when a non-browser-key route is used.
 _ARNOLD_MODEL = os.getenv("VIBECOMFY_ARNOLD_MODEL", "anthropic/claude-opus-4.6")
 _ARNOLD_BASE_URL = os.getenv("VIBECOMFY_ARNOLD_BASE_URL") or None

 _HERMES_ENV_PATH = Path("~/.hermes/.env").expanduser()


 def begin_deepseek_usage_capture() -> contextvars.Token:
     return _DEEPSEEK_USAGE_CAPTURE.set(
         {
             "usage": empty_deepseek_usage(),
             "cache_breakout_complete": True,
         }
     )


 def snapshot_deepseek_usage_capture() -> tuple[dict[str, int], bool]:
     state = _DEEPSEEK_USAGE_CAPTURE.get()
     if not isinstance(state, dict):
         return empty_deepseek_usage(), False
     usage = coerce_deepseek_usage(state.get("usage"))
     if usage["n_calls"] <= 0:
         return usage, False
     return usage, bool(state.get("cache_breakout_complete"))


 def end_deepseek_usage_capture(token: contextvars.Token) -> None:
     _DEEPSEEK_USAGE_CAPTURE.reset(token)


+def begin_model_attempt_capture() -> contextvars.Token:
+    return _MODEL_ATTEMPT_CAPTURE.set([])
+
+
+def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
+    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())
+
+
+def end_model_attempt_capture(token: contextvars.Token) -> None:
+    _MODEL_ATTEMPT_CAPTURE.reset(token)
+
+
+def record_model_attempts(value: Any) -> None:
+    """Append canonical attempts to the active executor capture, without duplicates."""
+    state = _MODEL_ATTEMPT_CAPTURE.get()
+    if state is None:
+        return
+    for attempt in coerce_model_attempts(value):
+        if state and state[-1] == attempt:
+            continue
+        state.append(attempt)
+
+
+def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
+    """Replace the most recent captured transport-success after domain parse failure."""
+    state = _MODEL_ATTEMPT_CAPTURE.get()
+    normalized = coerce_model_attempts([value])
+    if state is None or not normalized:
+        return
+    if state:
+        state[-1] = normalized[0]
+    else:
+        state.append(normalized[0])
+
+
 def _record_captured_deepseek_usage(result: Any) -> None:
     state = _DEEPSEEK_USAGE_CAPTURE.get()
     if not isinstance(state, dict) or not isinstance(result, dict):
         return
     usage = coerce_deepseek_usage(result.get("deepseek_usage"))
     if usage["n_calls"] <= 0:
         return
     state["usage"] = add_deepseek_usage(state.get("usage"), usage)
     if not result.get("deepseek_cache_breakout_complete", False):
         state["cache_breakout_complete"] = False


 def _read_env_file_entries(path: Path = _HERMES_ENV_PATH) -> list[tuple[str, str]]:
     """Read dotenv-style key/value pairs in file order."""
     entries: list[tuple[str, str]] = []
     try:
         text = path.read_text(encoding="utf-8")
     except (FileNotFoundError, OSError):
         return entries
     for line in text.splitlines():
         line = line.strip()
         if not line or line.startswith("#") or "=" not in line:
             continue
         key, _, value = line.partition("=")
         key = key.strip()
@@ -450,164 +468,207 @@ def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | No
         skip_context_files=True,      # don't load SOUL.md / AGENTS.md
         skip_memory=True,             # don't load/write the memory store
         quiet_mode=True,
     )
     if agent_id == "hermes":
         base_url = _base_url_for_route(route)
         resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
         if _is_native_deepseek_endpoint(base_url):
             # Native api.deepseek.com rejects OpenRouter-style ``deepseek/`` slugs
             # with HTTP 400; normalize to the bare model name it accepts.
             resolved_model = _normalize_native_deepseek_model(resolved_model)
         else:
             resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
         return dict(
             model=resolved_model,
             api_key=_hermes_credential_for(route, model),
             base_url=base_url,
             provider="openrouter",
             max_tokens=_OPENROUTER_MAX_TOKENS,
             **common,
         )
     # codex / claude -> default dispatcher resolves everything; kwargs unused.
     return dict(**common)


-def _is_transient_worker_result(result: Mapping[str, Any]) -> bool:
-    """True when a worker result is a transient failure worth retrying.
-
-    A worker reports failure by returning ``{"error": ..., "error_type": ...}``.
-    That is transient (and so retryable) unless it is a setup/auth fault that
-    will not recover (``runtime_unavailable``) or one of the content errors the
-    contract retry layer owns (see ``_WORKER_NON_TRANSIENT_ERROR_TYPES``).
-    """
-    if not isinstance(result, Mapping) or "error" not in result:
-        return False
-    if _is_runtime_unavailable(result):
+def _is_typed_empty_worker_result(result: Mapping[str, Any]) -> bool:
+    """True only for typed empty responses with observed zero completion tokens."""
+    attempts = coerce_model_attempts(result.get("model_attempts"))
+    if not attempts:
         return False
-    error_type = str(result.get("error_type") or "").strip()
-    return error_type not in _WORKER_NON_TRANSIENT_ERROR_TYPES
+    latest = attempts[-1]
+    usage = latest.get("token_usage")
+    return (
+        latest.get("outcome") == "failure"
+        and latest.get("failure_type") == "empty_response"
+        and isinstance(usage, Mapping)
+        and usage.get("completion_tokens") == 0
+    )
+
+
+def _runtime_provider_transport(
+    *, agent_id: str, agent_kwargs: Mapping[str, Any]
+) -> tuple[str, str, str]:
+    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
+    if agent_id != "hermes":
+        return "unknown", "unknown", endpoint
+    if "openrouter.ai" in endpoint:
+        return "openrouter", "openrouter", endpoint
+    if "deepseek.com" in endpoint:
+        return "deepseek", "native", endpoint
+    if endpoint != "unknown":
+        return "unknown", "openai_compatible", endpoint
+    return "unknown", "unknown", endpoint
+
+
+def _timeout_model_attempt(
+    *,
+    agent_kwargs: Mapping[str, Any],
+    agent_id: str,
+    requested_model: str | None,
+    resolved_model: str | None,
+    profiling_context: Mapping[str, Any] | None,
+    attempt: int,
+) -> dict[str, Any]:
+    provider, transport, endpoint = _runtime_provider_transport(
+        agent_id=agent_id, agent_kwargs=agent_kwargs
+    )
+    return ModelAttemptEvidence(
+        phase=(profiling_context or {}).get("backend_phase") or "agent_turn",
+        attempt=attempt,
+        outcome="failure",
+        failure_type="timeout",
+        requested_model=requested_model,
+        resolved_model=resolved_model or agent_kwargs.get("model"),
+        adapter=agent_id,
+        provider=provider,
+        transport=transport,
+        endpoint=endpoint,
+    ).to_dict()


 def _run_worker(
     agent_kwargs: dict[str, Any],
     system_msg: str | None,
     user_msg: str,
     *,
     response_contract: str = "python",
     agent_id: str = "hermes",
     model: str | None = None,
+    requested_model: str | None = None,
     effort: str | None = None,
     profiling_context: Mapping[str, Any] | None = None,
 ) -> dict[str, Any]:
     """Run one AIAgent turn in an isolated subprocess; return its result dict.

-    Wraps :func:`_run_worker_once` with a bounded retry for transient stalls.
-    A single model turn can hang on a flaky provider connection until the hard
-    ``_TURN_TIMEOUT_SECONDS`` kill, or come back as a transient transport error
-    (connection reset, read timeout, 429, 5xx). Both used to surface immediately
-    as an unrecoverable turn failure. Retrying spawns a fresh subprocess — and
-    thus a fresh connection — which is what makes a manual re-submit recover. We
-    do that automatically here, with backoff, before giving up.
-
-    Non-transient results (success, auth faults, setup faults, content errors)
-    are returned immediately without consuming retry slots.
+    A fresh subprocess/transport is permitted only after a canonical
+    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
+    provider/capacity errors, and malformed non-empty content surface immediately.
     """
-    last_result: dict[str, Any] | None = None
+    accumulated_attempts: list[dict[str, Any]] = []
     for attempt in range(_WORKER_TRANSIENT_MAX_ATTEMPTS):
         attempt_profile = dict(profiling_context or {})
         if attempt:
             attempt_profile["transient_retry_count"] = attempt
         try:
             result = _run_worker_once(
                 agent_kwargs,
                 system_msg,
                 user_msg,
                 response_contract=response_contract,
                 agent_id=agent_id,
                 model=model,
+                requested_model=requested_model,
                 effort=effort,
                 profiling_context=attempt_profile,
             )
-        except TimeoutError:
-            if attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS:
-                LOGGER.warning(
-                    "agent worker timed out after %ss (attempt %d/%d); retrying",
-                    _TURN_TIMEOUT_SECONDS,
-                    attempt + 1,
-                    _WORKER_TRANSIENT_MAX_ATTEMPTS,
-                )
-                time.sleep(_WORKER_TRANSIENT_BACKOFF_SECONDS * attempt)
-                continue
+        except TimeoutError as exc:
+            timeout_attempt = _timeout_model_attempt(
+                agent_kwargs=agent_kwargs,
+                agent_id=agent_id,
+                requested_model=requested_model,
+                resolved_model=model,
+                profiling_context=profiling_context,
+                attempt=len(accumulated_attempts) + 1,
+            )
+            accumulated_attempts.append(timeout_attempt)
+            record_model_attempts([timeout_attempt])
+            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
             raise
-        # Worker returned a result dict. Hand non-transient results straight back.
-        if "error" not in result or not _is_transient_worker_result(result):
-            return result
-        last_result = result
-        if attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS:
+        attempts = list(coerce_model_attempts(result.get("model_attempts")))
+        for item in attempts:
+            item["attempt"] = len(accumulated_attempts) + 1
+            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
+            accumulated_attempts.append(normalized)
+            record_model_attempts([normalized])
+        if accumulated_attempts:
+            result["model_attempts"] = list(accumulated_attempts)
+        if (
+            "error" in result
+            and _is_typed_empty_worker_result(result)
+            and attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS
+        ):
             LOGGER.warning(
-                "agent worker returned transient %s (attempt %d/%d); retrying: %s",
-                result.get("error_type") or "error",
+                "agent worker returned typed empty response (attempt %d/%d); retrying",
                 attempt + 1,
                 _WORKER_TRANSIENT_MAX_ATTEMPTS,
-                str(result.get("error"))[:200],
             )
             time.sleep(_WORKER_TRANSIENT_BACKOFF_SECONDS * attempt)
             continue
         return result
-    # Exhausted every retry on a returned transient error.
-    assert last_result is not None
-    return last_result
+    raise RuntimeError("agent worker retry loop exited without a result")


 def _run_worker_once(
     agent_kwargs: dict[str, Any],
     system_msg: str | None,
     user_msg: str,
     *,
     response_contract: str = "python",
     agent_id: str = "hermes",
     model: str | None = None,
+    requested_model: str | None = None,
     effort: str | None = None,
     profiling_context: Mapping[str, Any] | None = None,
 ) -> dict[str, Any]:
     """Run one AIAgent turn in an isolated subprocess; return its result dict.

     Single attempt — no retry. See :func:`_run_worker` for the retry wrapper.

     Isolation avoids the top-level module-name collision between megaplan's
     agent (bare ``import utils`` / ``model_tools``) and ComfyUI's own ``utils``
     package, and keeps the agent's asyncio/HTTP state out of ComfyUI's loop.
     """
     with tempfile.TemporaryDirectory(prefix="vibecomfy-agent-") as tmp:
         req_path = os.path.join(tmp, "request.json")
         res_path = os.path.join(tmp, "result.json")
         with open(req_path, "w", encoding="utf-8") as fh:
             json.dump(
                 {
                     "agent_id": agent_id,
                     "model": model,
+                    "requested_model": requested_model,
                     "effort": effort,
                     "agent_kwargs": agent_kwargs,
                     "system_message": system_msg,
                     "user_message": user_msg,
                     "response_contract": response_contract,
                     "profiling_context": dict(profiling_context or {}),
                 },
                 fh,
             )
         env = dict(os.environ)
         # Ensure the child sees the same credential the parent resolved for the
         # Hermes adapter.  For native DeepSeek endpoints this must be the
         # DeepSeek key, not a stale browser/OpenRouter key from ~/.hermes/.env.
         hermes_key = agent_kwargs.get("api_key") or _resolve_openrouter_key()
         if isinstance(hermes_key, str) and hermes_key:
             env["OPENROUTER_API_KEY"] = hermes_key
             env["OPENAI_API_KEY"] = hermes_key
             env["HERMES_API_KEY"] = hermes_key
         # Don't leak ComfyUI's cwd/path into the child (it is what causes the
         # `utils` collision); run from a neutral directory.
         try:
             with profiler_span(
                 LOGGER,
                 "runtime.worker_subprocess",
                 agent_id=agent_id,
@@ -675,133 +736,139 @@ def run_agent_turn(
     """
     agent_id = _agent_id_for_route(route)
     system_msg, user_msg = _split_messages(messages)
     if user_msg is None:
         # Fall back to reconstructing the user message from the raw inputs.
         user_msg = (
             f"User request:\n{task}\n\n"
             "Current scratchpad Python:\n```python\n" + (python_source or "") + "\n```"
         )

     if agent_id == "hermes" and not _hermes_credential_for(route, model):
         raise PermissionError(
             "OpenRouter route selected but no OPENROUTER_API_KEY is available "
             "(checked environment and ~/.hermes/.env). Submit a key via the "
             "VibeComfy panel or export OPENROUTER_API_KEY."
         )

     agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
     result = _run_worker(
         agent_kwargs,
         system_msg,
         user_msg,
         response_contract="python",
         agent_id=agent_id,
         model=_runtime_model_for_route(route, model),
+        requested_model=model,
         effort=effort,
+        profiling_context={"backend_phase": "implement"},
     )
     if "error" in result:
         _raise_worker_error(result)
-    return {"python": result["python"], "message": result["message"]}
+    return dict(result)


 def run_agent_turn_delta(
     *,
     task: str,
     projection: str,
     op_schema: Mapping[str, Any],
     route: str,
     model: str | None = None,
     effort: str | None = None,
     messages: Sequence[Mapping[str, Any]] | None = None,
 ) -> dict[str, Any]:
     """Run one v2 agent-edit turn and return ``{"delta": [...], "message": str}``."""
     agent_id = _agent_id_for_route(route)
     system_msg, user_msg = _split_messages(messages)
     if user_msg is None:
         user_msg = (
             f"User request:\n{task}\n\n"
             "Address-preserving UI projection:\n"
             f"{projection}"
         )

     if agent_id == "hermes" and not _hermes_credential_for(route, model):
         raise PermissionError(
             "OpenRouter route selected but no OPENROUTER_API_KEY is available "
             "(checked environment and ~/.hermes/.env). Submit a key via the "
             "VibeComfy panel or export OPENROUTER_API_KEY."
         )

     agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
     result = _run_worker(
         agent_kwargs,
         system_msg,
         user_msg,
         response_contract="delta",
         agent_id=agent_id,
         model=_runtime_model_for_route(route, model),
+        requested_model=model,
         effort=effort,
+        profiling_context={"backend_phase": "implement"},
     )
     if "error" in result:
         _raise_worker_error(result)
-    return {"delta": result["delta"], "message": result["message"]}
+    return dict(result)


 def run_agent_turn_batch(
     *,
     task: str,
     route: str,
     model: str | None = None,
     effort: str | None = None,
     messages: Sequence[Mapping[str, Any]] | None = None,
 ) -> dict[str, Any]:
     """Run one batch-REPL agent-edit turn and return raw model content."""
     agent_id = _agent_id_for_route(route)
     system_msg, user_msg = _split_messages(messages)
     if user_msg is None:
         user_msg = f"User request:\n{task}"

     if agent_id == "hermes" and not _hermes_credential_for(route, model):
         raise PermissionError(
             "OpenRouter route selected but no OPENROUTER_API_KEY is available "
             "(checked environment and ~/.hermes/.env). Submit a key via the "
             "VibeComfy panel or export OPENROUTER_API_KEY."
         )

     agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
     result = _run_worker(
         agent_kwargs,
         system_msg,
         user_msg,
         response_contract="batch_repl",
         agent_id=agent_id,
         model=_runtime_model_for_route(route, model),
+        requested_model=model,
         effort=effort,
+        profiling_context={"backend_phase": "batch"},
     )
     if "error" in result:
         _raise_worker_error(result)
-    return {"content": result["content"]}
+    return dict(result)


 def _requested_route(route: str | None) -> str:
     """Canonical panel route name (claude->anthropic, codex->openai-codex).

     The ``hermes`` dispatch agent id is exposed as a product route in headless
     executor specs; for readiness/status purposes it is the same as the
     OpenRouter browser-key route.
     """
     requested = (route or "").strip().lower()
     if requested == "claude":
         return "anthropic"
     if requested == "codex":
         return "openai-codex"
     if requested in {"deepseek", "hermes"}:
         return "openrouter"
     return requested


 def _codex_cli_present() -> bool:
     """True if a `codex` CLI binary resolves on PATH."""
     import shutil

     return bool(shutil.which("codex"))

@@ -1086,70 +1153,53 @@ def run_model_turn(
         ),
         "route": route,
         "model": model,
         "response_contract": response_contract,
         **(dict(profiling_context or {})),
     }

     with profiler_span(
         LOGGER,
         "runtime.run_model_turn",
         model_turn_id=effective_profile.get("model_turn_id"),
         agent_id=agent_id,
         route=route,
         model=model,
         response_contract=response_contract,
         task_preview=short_text(task),
     ) as span:
         if agent_id == "hermes" and not _hermes_credential_for(route, model):
             raise PermissionError(
                 "OpenRouter route selected but no OPENROUTER_API_KEY is available "
                 "(checked environment and ~/.hermes/.env). Submit a key via the "
                 "VibeComfy panel or export OPENROUTER_API_KEY."
             )

         agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
-        attempts = 3 if response_contract == "json" else 1
-        result: dict[str, Any] | None = None
-        last_error: Mapping[str, Any] | None = None
-        for attempt in range(attempts):
-            attempt_system_msg = system_msg
-            if attempt > 0:
-                attempt_system_msg = (
-                    f"{system_msg}\n\n{_JSON_RETRY_NUDGE}"
-                    if system_msg
-                    else _JSON_RETRY_NUDGE
-                )
-            result = _run_worker(
-                agent_kwargs,
-                attempt_system_msg,
-                user_msg,
-                response_contract=response_contract,
-                agent_id=agent_id,
-                model=_runtime_model_for_route(route, model),
-                effort=effort,
-                profiling_context={
-                    **effective_profile,
-                    **({"json_retry_count": attempt} if attempt else {}),
-                },
-            )
-            if "error" not in result:
-                break
-            last_error = result
-            if not (
-                response_contract == "json"
-                and attempt < attempts - 1
-                and result.get("error_type") in {"JSONDecodeError", "ValueError"}
-            ):
-                _raise_worker_error(result)
-        if result is None:
-            result = dict(last_error or {"error": "agent worker failed"})
+        result = _run_worker(
+            agent_kwargs,
+            system_msg,
+            user_msg,
+            response_contract=response_contract,
+            agent_id=agent_id,
+            model=_runtime_model_for_route(route, model),
+            requested_model=model,
+            effort=effort,
+            profiling_context=effective_profile,
+        )
         if "error" in result:
             _raise_worker_error(result)

         span.update(
             result_keys=sorted(result.keys()),
             worker_profile=result.get("_profiling") if isinstance(result.get("_profiling"), dict) else None,
         )
         return result

-__all__ = ["run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch", "run_model_turn", "readiness", "get_agent_status"]
+__all__ = [
+    "begin_deepseek_usage_capture", "snapshot_deepseek_usage_capture",
+    "end_deepseek_usage_capture", "begin_model_attempt_capture",
+    "snapshot_model_attempt_capture", "end_model_attempt_capture",
+    "record_model_attempts", "replace_last_model_attempt",
+    "run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch",
+    "run_model_turn", "readiness", "get_agent_status",
+]

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- vibecomfy/executor/agent_backend.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 16ms:
diff --git a/vibecomfy/executor/agent_backend.py b/vibecomfy/executor/agent_backend.py
index 1e701f41..7dc02508 100644
--- a/vibecomfy/executor/agent_backend.py
+++ b/vibecomfy/executor/agent_backend.py
@@ -1,51 +1,52 @@
 """Executor model-call wrappers over the VibeComfy provider/runtime seam.

 These functions bridge the executor's prompt-building + response-parsing
 machinery (``prompts.py``) with the provider seam (``provider.run_model_turn``)
 so that classify and reply model turns route through the same
 provider/runtime/worker stack as the agent-edit loop — preserving subprocess
 isolation and never importing Arnold agent backends in the ComfyUI process.

 Every function accepts ``route`` and ``model`` kwargs and passes them through
 to the provider, ensuring the resolved profile specs reach the worker.
 """

 from __future__ import annotations

 import logging
+import json
 from typing import Any, Mapping

 from vibecomfy.executor.profiler import new_profile_id, profiler_span, short_text

 from .prompts import (
     build_classify_messages,
     build_reply_messages,
     parse_classify_response,
     parse_reply_response,
 )
-from .contracts import ClassifyDecision
+from .contracts import ClassifyDecision, ModelAttemptEvidence, coerce_model_attempts

 LOGGER = logging.getLogger(__name__)


 def _extract_content(result: dict[str, Any]) -> str:
     """Extract the raw model output text from a provider result."""
     content = result.get("content")
     if isinstance(content, str) and content.strip():
         return content
     # Fall back to the json payload's raw text if content is missing.
     json_payload = result.get("json")
     if isinstance(json_payload, dict):
         # Re-serialise the parsed JSON so parsers get text.
         import json

         return json.dumps(json_payload)
     raise ValueError(
         "Model turn result did not contain text content. "
         f"Got keys: {sorted(result.keys())}"
     )


 def _preview_raw(text: str | None, *, limit: int = 1200) -> str | None:
     """Bounded, whitespace-normalized preview of raw model output."""
     if not isinstance(text, str):
@@ -54,59 +55,101 @@ def _preview_raw(text: str | None, *, limit: int = 1200) -> str | None:
     if not normalized:
         return None
     if len(normalized) <= limit:
         return normalized
     return normalized[: limit - 1].rstrip() + "…"


 def _attach_model_turn_evidence(
     exc: BaseException,
     result: dict[str, Any] | None,
     *,
     model: str,
     phase: str,
     raw: str | None,
 ) -> None:
     """Attach additive parse evidence to a classify/reply exception in place.

     The provider result dict carries the worker's deepseek_usage plus the
     resolved model/phase/endpoint; attaching it (and the raw content preview)
     lets the executor's failure envelope persist tokens + raw preview + context
     without re-resolving provider internals.
     """
     try:
         if result is not None and getattr(exc, "worker_result", None) is None:
             exc.worker_result = dict(result)  # type: ignore[attr-defined]
+        if result is not None and getattr(exc, "model_attempts", None) is None:
+            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
         if raw is not None and getattr(exc, "raw_response_preview", None) is None:
             exc.raw_response_preview = _preview_raw(raw)  # type: ignore[attr-defined]
         for name, value in (("model", model), ("phase", phase)):
             if getattr(exc, name, None) is None:
                 setattr(exc, name, value)
     except Exception:  # noqa: BLE001 - evidence attachment is best-effort
         pass


+def _downstream_failure_type(raw: str | None) -> str:
+    if not isinstance(raw, str) or not raw.strip():
+        return "empty_response"
+    stripped = raw.strip()
+    if stripped.startswith("```"):
+        stripped = stripped.removeprefix("```json").removeprefix("```")
+        stripped = stripped.rsplit("```", 1)[0].strip()
+    try:
+        parsed = json.loads(stripped)
+    except (json.JSONDecodeError, TypeError):
+        return "malformed_json" if "{" in stripped else "non_json_content"
+    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"
+
+
+def _record_result_attempts(result: dict[str, Any]) -> None:
+    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
+
+    record_model_attempts(result.get("model_attempts"))
+
+
+def _mark_last_attempt_failed(
+    result: dict[str, Any], *, raw: str | None, failure_type: str
+) -> None:
+    attempts = list(coerce_model_attempts(result.get("model_attempts")))
+    if not attempts:
+        return
+    latest = dict(attempts[-1])
+    latest.update({
+        "outcome": "failure",
+        "failure_type": failure_type,
+        "raw_response_preview": raw,
+    })
+    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
+    attempts[-1] = revised
+    result["model_attempts"] = attempts
+    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
+
+    replace_last_model_attempt(revised)
+
+
 def run_classify_turn(
     query: str,
     *,
     route: str,
     model: str,
     effort: str | None = None,
     has_graph: bool = False,
     graph_summary: str | None = None,
     layout_hint: Mapping[str, Any] | None = None,
     messages: list[dict[str, str]] | None = None,
 ) -> ClassifyDecision:
     """Run a single classify model turn through the provider seam.

     Builds classify-specific messages via :func:`build_classify_messages`,
     dispatches through :func:`run_model_turn` with ``response_contract="json"``,
     and parses the result with :func:`parse_classify_response`.

     When *messages* is provided, it is used directly instead of building
     messages from *query* / *has_graph* / *graph_summary*.  This allows
     callers to pre-enrich messages with session context and graph reference
     maps without changing the classify route signature.

     Parameters
     ----------
     query:
@@ -139,58 +182,64 @@ def run_classify_turn(
         model_turn_id=model_turn_id,
         backend_phase="classify",
         route=route,
         model=model,
         response_contract="json",
         has_graph=has_graph,
         graph_summary=graph_summary,
         query_preview=short_text(query),
     ) as span:
         from vibecomfy.comfy_nodes.agent.provider import run_model_turn

         result = run_model_turn(
             query,
             messages,
             route=route,
             model=model,
             effort=effort,
             response_contract="json",
             profiling_context={"backend_phase": "classify"},
         )
         raw: str | None = None
         try:
             raw = _extract_content(result)
             decision = parse_classify_response(raw)
         except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
+            _mark_last_attempt_failed(
+                result,
+                raw=raw,
+                failure_type=_downstream_failure_type(raw),
+            )
             _attach_model_turn_evidence(
                 exc,
                 result,
                 model=model,
                 phase="classify",
                 raw=raw,
             )
             raise
+        _record_result_attempts(result)
         span.update(
             content_length=len(raw),
             plan_research=decision.research,
             plan_implement=decision.implement,
             plan_reply=decision.reply,
         )
         return decision


 def run_reply_turn(
     query: str,
     *,
     route: str,
     model: str,
     effort: str | None = None,
     plan: ClassifyDecision | None = None,
     research_summary: str | None = None,
     research_sources: tuple[dict[str, Any], ...] | None = None,
     research_warnings: tuple[str, ...] | None = None,
     research_precedent_slices: tuple[dict[str, Any], ...] | None = None,
     implementation_message: str | None = None,
     graph_summary: str | None = None,
     graph_inspection: str | None = None,
     adaptation_plan: dict[str, Any] | None = None,
     effective_route: str | None = None,
@@ -254,38 +303,44 @@ def run_reply_turn(
         LOGGER,
         "executor.model_turn",
         model_turn_id=model_turn_id,
         backend_phase="reply",
         route=route,
         model=model,
         response_contract="json",
         query_preview=short_text(query),
     ) as span:
         from vibecomfy.comfy_nodes.agent.provider import run_model_turn

         result = run_model_turn(
             query,
             messages,
             route=route,
             model=model,
             effort=effort,
             response_contract="json",
             profiling_context={"backend_phase": "reply"},
         )
         raw: str | None = None
         try:
             raw = _extract_content(result)
             reply = parse_reply_response(raw)
         except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
+            _mark_last_attempt_failed(
+                result,
+                raw=raw,
+                failure_type=_downstream_failure_type(raw),
+            )
             _attach_model_turn_evidence(
                 exc,
                 result,
                 model=model,
                 phase="reply",
                 raw=raw,
             )
             raise
+        _record_result_attempts(result)
         span.update(content_length=len(raw), reply_preview=short_text(reply))
         return reply


 __all__ = ["run_classify_turn", "run_reply_turn"]

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- vibecomfy/executor/core.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/executor/core.py b/vibecomfy/executor/core.py
index 448ae678..053ead93 100644
--- a/vibecomfy/executor/core.py
+++ b/vibecomfy/executor/core.py
@@ -10,52 +10,55 @@ contracts module) — raw exceptions never leak out of this module.
 """

 from __future__ import annotations

 import logging
 import re
 from dataclasses import dataclass, replace
 from datetime import datetime, timezone
 from types import MappingProxyType
 from typing import Any, Mapping

 from vibecomfy.comfy_nodes.agent.contracts import (
     FailureKind,
     classify_failure,
     failure_envelope,
 )
 from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
 from vibecomfy.comfy_nodes.agent.provider import (
     AuthError,
     MalformedModelJSON,
     MissingRequiredField,
     ProviderError,
 )
 from vibecomfy.comfy_nodes.agent.runtime import (
     begin_deepseek_usage_capture,
+    begin_model_attempt_capture,
     end_deepseek_usage_capture,
+    end_model_attempt_capture,
     snapshot_deepseek_usage_capture,
+    snapshot_model_attempt_capture,
 )
 from vibecomfy.agent.deepseek_usage import estimate_deepseek_cost_usd
 from vibecomfy.executor.profiler import (
     new_profile_id,
     profiler_log,
     profiler_span,
     short_text,
 )

 from .agent_backend import run_classify_turn, run_reply_turn
 from .prompts import build_classify_messages
 from .contracts import (
     ClassifyDecision,
     ExecutorRequest,
     ExecutorResult,
     ImplementationResult,
     Report,
     ResearchResult,
     _ALLOWED_ROUTES,
     adaptation_plan_actionability_payload,
     warning_detail_from_exception,
 )
 from .graph_inspection import _graph_inspection
 from .execution_plan_builder import build_execution_plan, needs_precedent_plan
 from .layout_hints import build_classify_layout_hint
@@ -85,50 +88,51 @@ _INSTALL_REQUEST_TERMS = (
     "install",
     "installation",
     "which pack",
     "what pack",
     "provider pack",
     "provides",
     "registry",
     "comfyui-manager",
 )


 def _spec_fields(spec: AgentSpecShape | None) -> dict[str, Any]:
     if spec is None:
         return {}
     return {"route": spec.agent, "model": spec.model, "effort": spec.effort}


 # ── model-response parse evidence (classify/reply) ──────────────────────────
 # Additive evidence persisted when a classify/reply model turn fails to parse.
 # Mirrors the batch-repl model_response.json detail (parse_reason + raw
 # preview) plus observed usage, model, phase, and endpoint so a failed attempt
 # is diagnosable from the final failure envelope without re-resolving provider
 # internals. The failure envelope's public shape is unchanged.

 _MODEL_RESPONSE_EVIDENCE_KEYS = (
+    "model_attempts",
     "parse_reason",
     "raw_response_preview",
     "finish_reason",
     "completion_tokens",
     "prompt_tokens",
     "total_tokens",
     "model",
     "phase",
     "endpoint",
 )

 _PARSE_REASON_EMPTY = "empty"
 _PARSE_REASON_MISSING_CONTENT = "missing_content"
 _PARSE_REASON_MALFORMED_JSON = "malformed_json"
 _PARSE_REASON_NON_JSON_CONTENT = "non_json_content"


 def _evidence_value(value: Any) -> bool:
     if value is None:
         return False
     if isinstance(value, str):
         return bool(value.strip())
     return True


@@ -199,50 +203,53 @@ def _enrich_failure_envelope(
     exc: BaseException,
     *,
     phase: str,
     model: str | None,
 ) -> Any:
     """Merge parse evidence into a failure envelope's agent_failure_context.

     Additive only: the envelope's existing keys (``explanation``, ...) are kept.
     """
     evidence = _model_response_evidence_from_exception(exc)
     evidence.setdefault("phase", phase)
     if model:
         evidence.setdefault("model", model)
     if not evidence:
         return failure
     context = dict(failure.agent_failure_context or {})
     context.update(evidence)
     return replace(failure, agent_failure_context=context)


 def _model_response_artifact(failure: Any) -> dict[str, Any] | None:
     """Shape parse evidence into a batch-repl-style ``model_response`` artifact."""
     context = getattr(failure, "agent_failure_context", None)
     if not isinstance(context, Mapping):
         return None
+    attempts = context.get("model_attempts")
+    if isinstance(attempts, (list, tuple)) and attempts:
+        return {"attempts": [dict(item) for item in attempts if isinstance(item, Mapping)]}
     evidence = {
         key: context[key]
         for key in _MODEL_RESPONSE_EVIDENCE_KEYS
         if context.get(key) is not None
     }
     if not evidence:
         return None
     return {"turns": [{"error": dict(evidence)}]}


 def _allows_install_or_provider_research(query: str) -> bool:
     query_l = str(query or "").casefold()
     return any(term in query_l for term in _INSTALL_REQUEST_TERMS)


 def _sanitize_research_hint_text(text: str, *, query: str = "") -> str | None:
     """Keep classifier hints pointed at precedent unless install info was asked for."""

     stripped = str(text or "").strip()
     if not stripped:
         return None
     text_l = stripped.casefold()
     if (
         _allows_install_or_provider_research(query)
         or not any(term in text_l for term in _INSTALL_RESEARCH_TERMS)
@@ -1947,77 +1954,87 @@ def run_executor(
         "input graph has dangling/absent endpoints -> refuse to compound"
         precondition.  All post-edit validation and gates remain enforced.

     Returns
     -------
     ExecutorResult
         Always returns a result — failures are captured in the result
         shape, never raised as raw exceptions.
     """
     plan: ClassifyDecision | None = None
     research_result: ResearchResult | None = None
     implementation_result: ImplementationResult | None = None
     effective_graph: dict[str, Any] | None = request.graph
     result_graph: dict[str, Any] | None = None
     executor_id = new_profile_id("executor")
     request_fields = {
         "executor_id": executor_id,
         "profile": request.profile or "default",
         "session_id": request.session_id,
         "has_graph": request.graph is not None,
         "query_preview": short_text(request.query),
     }

     profiler_log(LOGGER, "executor.request", **request_fields)
     usage_token = begin_deepseek_usage_capture()
+    attempt_token = begin_model_attempt_capture()

     def _build_report(
         *,
         plan: ClassifyDecision | None = None,
         research: ResearchResult | None = None,
         implementation: ImplementationResult | None = None,
         classification_status: str = "",
         model_response: dict[str, Any] | None = None,
     ) -> Report:
         usage, cache_breakout_complete = snapshot_deepseek_usage_capture()
+        model_attempts = snapshot_model_attempt_capture()
+        if not model_attempts and isinstance(model_response, Mapping):
+            raw_attempts = model_response.get("attempts")
+            if isinstance(raw_attempts, (list, tuple)):
+                model_attempts = tuple(
+                    dict(item) for item in raw_attempts if isinstance(item, Mapping)
+                )
         est_cost_usd, cost_basis = estimate_deepseek_cost_usd(
             usage,
             cache_breakout_complete=cache_breakout_complete,
         )
         return Report(
             plan=plan,
             research=research,
             implementation=implementation,
             deepseek_usage=usage,
             deepseek_est_cost_usd=est_cost_usd,
             deepseek_cost_basis=cost_basis,
             classification_status=classification_status,
+            model_attempts=model_attempts,
             model_response=model_response,
         )

     def _finish(result: ExecutorResult) -> ExecutorResult:
         end_deepseek_usage_capture(usage_token)
+        end_model_attempt_capture(attempt_token)
         return result

     # ── Resolve profile specs ────────────────────────────────────────────
     try:
         classify_spec = _resolve_spec(request.profile, "classify")
     except Exception as exc:
         failure = classify_failure("profile", exc)
         return _finish(ExecutorResult.failure(
             kind=failure.kind.value,
             stage="profile",
             message=failure.user_facing_message,
             report=_build_report(),
         ))
     profiler_log(
         LOGGER,
         "executor.profile_resolved",
         **request_fields,
         classify=_spec_fields(classify_spec),
     )

     # ── Build session context and graph reference map (M3) ────────────────
     session_context: dict[str, Any] | None = None
     if request.session_id:
         session_context = _build_session_context(request)
     graph_reference_map = _build_graph_reference_map(request.graph)

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- vibecomfy/agent/artifacts.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/agent/artifacts.py b/vibecomfy/agent/artifacts.py
index 753c1257..c6c19667 100644
--- a/vibecomfy/agent/artifacts.py
+++ b/vibecomfy/agent/artifacts.py
@@ -1,120 +1,141 @@
 """Artifact synthesis for the headless VibeComfy agent surface.

 Writes a stable, redacted artifact directory that harnesses and external
 consumers (e.g. Astrid) can grade without parsing narrative output.
 """

 from __future__ import annotations

 import json
 import logging
 import shutil
 from pathlib import Path
 from typing import Any, Mapping

+from vibecomfy.executor.contracts import normalize_model_endpoint, redact_model_preview
+
 LOGGER = logging.getLogger(__name__)


 _FLOW_KIND = "live_agentic_headless"
 _SENSITIVE_KEY_PARTS = frozenset({
     "api_key",
     "apikey",
     "authorization",
     "bearer",
     "password",
     "secret",
     "token",
 })
 _MODEL_ARTIFACT_NAMES = frozenset({
     "messages.jsonl",
+    "model_attempts.json",
     "model_request.json",
     "model_response.json",
 })


 def _safe_write(path: Path, data: Any) -> None:
     path.parent.mkdir(parents=True, exist_ok=True)
     path.write_text(
         json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
         encoding="utf-8",
     )


 def _json_safe(value: Any) -> Any:
     if value is None or isinstance(value, (str, int, float, bool)):
         return value
     if hasattr(value, "to_dict") and callable(value.to_dict):
         return _json_safe(value.to_dict())
     if isinstance(value, Mapping):
         return {str(key): _json_safe(item) for key, item in value.items()}
     if isinstance(value, (list, tuple, set)):
         return [_json_safe(item) for item in value]
     return str(value)


 def _is_sensitive_key(key: str) -> bool:
     lower = key.lower()
     return any(part in lower for part in _SENSITIVE_KEY_PARTS)


 def _redact(value: Any, *, parent_key: str = "") -> Any:
     """Return a JSON-safe copy with credential-like values redacted."""
     if _is_sensitive_key(parent_key) and isinstance(value, str):
         return "<redacted>"
+    if parent_key.lower() == "endpoint" and isinstance(value, str):
+        return normalize_model_endpoint(value)
+    if parent_key.lower() == "raw_response_preview" and isinstance(value, str):
+        return redact_model_preview(value)
     if isinstance(value, Mapping):
         redacted: dict[str, Any] = {}
         for key, item in value.items():
             key_text = str(key)
             redacted[key_text] = _redact(item, parent_key=key_text)
         return redacted
     if isinstance(value, (list, tuple, set)):
         return [_redact(item, parent_key=parent_key) for item in value]
     return _json_safe(value)


 def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
     detail = response.get("detail_json_path") or response.get("detail_json_path_resolved")
     if isinstance(detail, str) and detail:
         return Path(detail).parent
     session_path = response.get("session_path") or response.get("session_path_resolved")
     turn_id = response.get("turn_id")
     if isinstance(session_path, str) and session_path and isinstance(turn_id, str) and turn_id:
         candidate = Path(session_path) / "turns" / turn_id
         if candidate.is_dir():
             return candidate
     return None


 def _copy_turn_artifacts(turn_dir: Path, output_dir: Path) -> list[str]:
     copied: list[str] = []
     if not turn_dir.is_dir():
         return copied
     for source in sorted(turn_dir.iterdir()):
         if source.is_file() and source.suffix in {".json", ".jsonl"}:
             dest = output_dir / source.name
-            shutil.copy2(source, dest)
+            try:
+                if source.suffix == ".json":
+                    parsed = json.loads(source.read_text(encoding="utf-8"))
+                    _safe_write(dest, _redact(parsed))
+                else:
+                    rendered: list[str] = []
+                    for line in source.read_text(encoding="utf-8").splitlines():
+                        if not line.strip():
+                            continue
+                        rendered.append(json.dumps(_redact(json.loads(line)), sort_keys=True))
+                    dest.write_text("\n".join(rendered) + ("\n" if rendered else ""), encoding="utf-8")
+            except (OSError, json.JSONDecodeError):
+                # Preserve non-JSON diagnostic files for compatibility. Canonical
+                # model-attempt artifacts are always JSON and take the redacted path.
+                shutil.copy2(source, dest)
             copied.append(str(dest.relative_to(output_dir)))
     return copied


 def _executor_report(result: Any) -> dict[str, Any]:
     result_payload = _json_safe(result)
     if isinstance(result_payload, Mapping):
         report = result_payload.get("report")
         if isinstance(report, Mapping):
             executor = report.get("executor")
             if isinstance(executor, Mapping):
                 return dict(executor)

     report_obj = getattr(result, "report", None)
     report_payload = _json_safe(report_obj)
     if isinstance(report_payload, Mapping):
         executor = report_payload.get("executor")
         if isinstance(executor, Mapping):
             return dict(executor)
     return {}


 def _implementation_payload_from_report(
     *,
     request: Mapping[str, Any],
@@ -290,50 +311,57 @@ def synthesize_headless_artifacts(
     request_path = output_dir / "request.json"
     _safe_write(request_path, _redact(request))
     _append_manifest(manifest, "request.json")

     response_path = output_dir / "response.json"
     _safe_write(response_path, _redact(response))
     _append_manifest(manifest, "response.json")

     flow_metadata = {
         "flow_kind": _FLOW_KIND,
         "dispatcher": "real",
         "model_behavior": "agentic",
         "frontend": "not_used",
         "entrypoint": entrypoint,
         "status": status,
         "live": bool(request.get("live", True)),
         "dry_run": bool(request.get("dry_run", False)),
         "apply": bool(request.get("apply", False)),
         "network": bool(request.get("network", True)),
         "readiness": dict(readiness) if readiness else {},
     }
     _safe_write(output_dir / "flow_metadata.json", _redact(flow_metadata))
     _append_manifest(manifest, "flow_metadata.json")

     report = _executor_report(result)
+    model_attempts = report.get("model_attempts")
+    if isinstance(model_attempts, (list, tuple)) and model_attempts:
+        _safe_write(
+            output_dir / "model_attempts.json",
+            {"attempts": _redact(model_attempts)},
+        )
+        _append_manifest(manifest, "model_attempts.json")
     classification = report.get("plan")
     if isinstance(classification, Mapping):
         classification_payload = _redact(classification)
         _safe_write(output_dir / "classification.json", classification_payload)
         _append_manifest(manifest, "classification.json")

         research = report.get("research")
         research_payload: dict[str, Any] | None = None
         if isinstance(research, Mapping):
             research_payload = _redact(research)
             _safe_write(output_dir / "research.json", research_payload)
             _append_manifest(manifest, "research.json")

         implementation = report.get("implementation")
         if isinstance(implementation, Mapping):
             implementation_payload = _implementation_payload_from_report(
                 request=request,
                 classification=classification_payload,
                 research=research_payload,
             )
             _safe_write(
                 output_dir / "implementation_payload.json",
                 _redact(implementation_payload),
             )
             _append_manifest(manifest, "implementation_payload.json")

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- tests/live_agentic_harness/runner.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index bbd41e73..9286c3fc 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -1,88 +1,67 @@
 """Live agentic harness runner for VibeComfy headless scenarios.

 Scenarios run CONCURRENTLY — each in its own subprocess (process isolation +
 kill-on-timeout via ``subprocess.run``), bounded by ``--max-workers``. Modeled
 on the subagent-launcher fanout: one process per task, a bounded pool, a
 per-task timeout. ``--single`` is the per-scenario subprocess entry point.
 """

 from __future__ import annotations

 import argparse
 import json
-import re
 import subprocess
 import sys
 import tempfile
 import threading
 import time
 from pathlib import Path
 from typing import Any, Mapping

 from vibecomfy.agent.deepseek_usage import (
     add_deepseek_usage,
     coerce_deepseek_usage,
     combine_deepseek_cost_bases,
 )

 from .failure_analysis import (
     DEFAULT_AGENT_TIMEOUT_S,
     DEFAULT_ANALYSIS_MODEL,
     DEFAULT_ANALYSIS_WORKERS,
     DEFAULT_RECOMMENDATIONS_MODEL,
     analyze_failures,
     prepare_failure_analysis,
     recommendations_for_run,
 )

 DEFAULT_MAX_WORKERS = 12
 DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
 DEFAULT_PROGRESS_EVERY = 10
 DEFAULT_INFRA_RETRIES = 1
 REPO = Path(__file__).resolve().parents[2]

-_PROVIDER_INFRA_PATTERNS: tuple[re.Pattern[str], ...] = (
-    re.compile(r"OpenRouter rejected", re.IGNORECASE),
-    re.compile(r"model provider is temporarily unavailable", re.IGNORECASE),
-    re.compile(r"provider is temporarily unavailable", re.IGNORECASE),
-    re.compile(r"not have enough credits", re.IGNORECASE),
-    re.compile(r"insufficient credits", re.IGNORECASE),
-    re.compile(r"insufficient balance", re.IGNORECASE),
-    re.compile(r"quota exceeded", re.IGNORECASE),
-    re.compile(r"rate limit", re.IGNORECASE),
-    re.compile(r"too many requests", re.IGNORECASE),
-    re.compile(r"HTTP Error 429", re.IGNORECASE),
-)
-
-# "The model response could not be parsed" is infra ONLY with zero-token
-# evidence (an empty/transport response) — never on the phrase alone.  A
-# nonzero-token parse failure (e.g. markdown instead of JSON) is a product
-# failure.  See ``_provider_infra_failure_class``.
-_PARSE_FAILURE_PATTERN = re.compile(r"The model response could not be parsed", re.IGNORECASE)
-
-
 def _scenario_paths(scenarios_dir: Path) -> list[Path]:
     if not scenarios_dir.is_dir():
         return []
     return sorted(p for p in scenarios_dir.iterdir() if p.suffix in {".yaml", ".yml", ".json"})


 def _load_scenario(path: Path) -> dict[str, Any]:
     if path.suffix == ".json":
         return json.loads(path.read_text(encoding="utf-8"))
     import yaml

     return yaml.safe_load(path.read_text(encoding="utf-8"))


 def _output_dir_for(output_base: Any, tag: str, scenario_id: str) -> Path:
     base = Path(output_base) if output_base else Path("out/agentic")
     return Path(base) / tag / scenario_id


 def _run_dir_for(output_base: Any, tag: str) -> Path:
     base = Path(output_base) if output_base else Path("out/agentic")
     return Path(base) / tag


 def _trim(s: str) -> str:
@@ -185,142 +164,134 @@ def _persist_canonical_scenario_summary(
     scenario_id: str,
 ) -> None:
     _write_json_atomic(_output_dir_for(output_base, tag, scenario_id) / "agentic_summary.json", summary)


 def _attempt_tag(tag: str, scenario_id: str, attempt: int) -> str:
     return f"{tag}/attempts/{scenario_id}/attempt_{attempt}"


 def _attempt_record(summary: dict[str, Any], *, attempt: int) -> dict[str, Any]:
     return {
         "attempt": attempt,
         "scenario_id": summary.get("scenario_id"),
         "status": summary.get("status"),
         "ok": summary.get("ok"),
         "output_dir": summary.get("output_dir"),
         "error": summary.get("error"),
         "failure_class": summary.get("failure_class")
         or (summary.get("guard") or {}).get("failure_class")
         or "product_or_assessment_failure",
         "score_class": summary.get("score_class") or (summary.get("guard") or {}).get("score_class"),
         "retryable_infra": bool(summary.get("retryable_infra")),
         "agent_exercised": summary.get("agent_exercised"),
         "elapsed_s": summary.get("elapsed_s"),
         "live_agentic_success": (summary.get("guard") or {}).get("live_agentic_success"),
+        "model_attempts": summary.get("model_attempts", []),
     }


-def _summary_text_for_infra_classification(summary: dict[str, Any]) -> str:
-    parts: list[str] = []
-    for key in ("error", "stdout_tail", "stderr_tail"):
-        value = summary.get(key)
-        if isinstance(value, str):
-            parts.append(value)
-
-    guard = summary.get("guard")
-    if isinstance(guard, dict):
-        assessment = guard.get("assessment")
-        if isinstance(assessment, dict):
-            for issue in assessment.get("issues") or []:
-                if not isinstance(issue, dict):
-                    continue
-                if issue.get("check") == "soft_warning":
-                    continue
-                detail = issue.get("detail")
-                if isinstance(detail, str):
-                    parts.append(detail)
-    return "\n".join(parts)
+def _latest_failed_model_attempt(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
+    attempts = summary.get("model_attempts")
+    if not isinstance(attempts, (list, tuple)):
+        return None
+    for attempt in reversed(attempts):
+        if isinstance(attempt, Mapping) and attempt.get("outcome") == "failure":
+            return attempt
+    return None


 def _summary_completion_tokens(summary: dict[str, Any]) -> int | None:
     """Observed completion tokens of the attempt's model call, or None when absent.

     The attempt summary (agentic_summary) carries ``deepseek_usage`` at the top
     level — the executor result's usage dict.  ``completion_tokens == 0`` is the
     structured evidence of an empty/transport response; absence of the record is
     NOT evidence, so it never classifies as infra.
     """
-    usage = summary.get("deepseek_usage")
+    attempt = _latest_failed_model_attempt(summary)
+    usage = attempt.get("token_usage") if isinstance(attempt, Mapping) else None
     if not isinstance(usage, Mapping):
         return None
     value = usage.get("completion_tokens")
     if not isinstance(value, (int, float)):
         return None
     return int(value)


 def _provider_infra_failure_class(summary: dict[str, Any]) -> str | None:
-    text = _summary_text_for_infra_classification(summary)
-    if not text:
-        return None
-    if _PARSE_FAILURE_PATTERN.search(text):
-        # The parse phrase alone is never infra: markdown instead of JSON is a
-        # product failure.  Only an empty model response — structured evidence
-        # that the call observed zero completion tokens (a transport-level
-        # reply) — is retryable infrastructure.
-        if _summary_completion_tokens(summary) == 0:
-            return "infra_empty_response"
+    """Map only canonical typed attempt evidence; never inspect response prose."""
+    attempt = _latest_failed_model_attempt(summary)
+    if attempt is None:
         return None
-    if any(pattern.search(text) for pattern in _PROVIDER_INFRA_PATTERNS):
+    failure_type = attempt.get("failure_type")
+    if failure_type == "empty_response" and _summary_completion_tokens(summary) == 0:
+        return "infra_empty_response"
+    if failure_type == "timeout":
+        return "infra_timeout"
+    if failure_type == "provider_failure":
         return "infra_provider_capacity"
     return None


 def _mark_summary_as_infra(summary: dict[str, Any], failure_class: str) -> None:
     summary["failure_class"] = failure_class
     summary["score_class"] = "infra_blocked"
-    summary["retryable_infra"] = True
+    summary["retryable_infra"] = failure_class == "infra_empty_response"
     guard = summary.get("guard")
     if isinstance(guard, dict):
         guard["failure_class"] = failure_class
         guard["score_class"] = "infra_blocked"
         assessment = guard.get("assessment")
         if isinstance(assessment, dict):
             assessment.setdefault("issues", []).append(
                 {
                     "check": "infra_classification",
                     "severity": "warning",
                     "detail": (
-                        f"{failure_class} failure was classified as retryable "
+                        f"{failure_class} failure was classified as "
                         "infrastructure, not product quality."
                     ),
                     "failure_class": failure_class,
                 }
             )


 def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
     failure_class = _provider_infra_failure_class(summary)
     if failure_class is not None and summary.get("guard", {}).get("live_agentic_success") is not True:
         _mark_summary_as_infra(summary, failure_class)
     return summary


 def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
     _classify_retryable_infra_summary(summary)
-    return bool(summary.get("retryable_infra")) or str(summary.get("failure_class") or "").startswith("infra_")
+    return (
+        summary.get("failure_class") == "infra_empty_response"
+        and summary.get("retryable_infra") is True
+        and _summary_completion_tokens(summary) == 0
+    )


 def _build_run_summary(
     tag: str,
     summaries: list[dict[str, Any]],
     *,
     total_scenarios: int,
     complete: bool,
 ) -> dict[str, Any]:
     passed = sum(1 for summary in summaries if summary["guard"].get("live_agentic_success") is True)
     failed = len(summaries) - passed
     raw_first_attempt_passed = sum(
         1
         for summary in summaries
         if summary.get("raw_first_attempt_success", summary["guard"].get("live_agentic_success")) is True
     )
     infra_failures = sum(
         1
         for summary in summaries
         if summary["guard"].get("live_agentic_success") is not True
         and str(summary.get("failure_class") or "").startswith("infra_")
     )
     score_classes: dict[str, int] = {}
     for summary in summaries:
         score_class = (

exec
/bin/zsh -lc 'git diff --unified=25 16d80bbe..e33f0260 -- tests/live_agentic_harness/adapter.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 8ms:
diff --git a/tests/live_agentic_harness/adapter.py b/tests/live_agentic_harness/adapter.py
index c522f2c3..bd39ab5c 100644
--- a/tests/live_agentic_harness/adapter.py
+++ b/tests/live_agentic_harness/adapter.py
@@ -127,26 +127,27 @@ def run_headless_scenario(
     request = HeadlessAgentRequest(
         query=query,
         graph=graph,
         workflow_id=scenario.get("workflow_id") or (graph.get("workflow_id") if isinstance(graph, dict) else None),
         session_id=scenario.get("session_id"),
         profile=scenario.get("profile"),
         output_dir=output_dir,
         dry_run=bool(scenario.get("dry_run", False)),
         apply=bool(scenario.get("apply", False)),
         network=bool(scenario.get("network", True)),
         timeout=scenario.get("timeout"),
         additive=bool(scenario.get("additive", False)),
     )

     result = run_headless(request, entrypoint="live_agentic_harness")
     return {
         "scenario_id": scenario_id,
         "status": result.status,
         "ok": result.ok,
         "output_dir": str(output_dir),
         "readiness": result.readiness,
         "error": result.error,
         "deepseek_usage": result.response.get("deepseek_usage", {}),
         "deepseek_est_cost_usd": result.response.get("deepseek_est_cost_usd"),
         "deepseek_cost_basis": result.response.get("deepseek_cost_basis"),
+        "model_attempts": result.response.get("model_attempts", []),
     }

exec
/bin/zsh -lc "rg -n \"model_attempt|attempt_capture|requested_model|resolved_model|replace_last|_run_worker|fresh|completion_tokens|return \\{\" vibecomfy/comfy_nodes/agent/runtime.py vibecomfy/executor/agent_backend.py vibecomfy/executor/core.py vibecomfy/agent/artifacts.py vibecomfy/comfy_nodes/agent/provider.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
vibecomfy/executor/agent_backend.py:27:from .contracts import ClassifyDecision, ModelAttemptEvidence, coerce_model_attempts
vibecomfy/executor/agent_backend.py:80:        if result is not None and getattr(exc, "model_attempts", None) is None:
vibecomfy/executor/agent_backend.py:81:            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:106:    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
vibecomfy/executor/agent_backend.py:108:    record_model_attempts(result.get("model_attempts"))
vibecomfy/executor/agent_backend.py:114:    attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/executor/agent_backend.py:125:    result["model_attempts"] = attempts
vibecomfy/executor/agent_backend.py:126:    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
vibecomfy/executor/agent_backend.py:128:    replace_last_model_attempt(revised)
vibecomfy/comfy_nodes/agent/provider.py:17:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/provider.py:92:    return {"prior_request": prior_request, "question": question}
vibecomfy/comfy_nodes/agent/provider.py:132:        return {
vibecomfy/comfy_nodes/agent/provider.py:150:        return {
vibecomfy/comfy_nodes/agent/provider.py:168:        return {
vibecomfy/comfy_nodes/agent/provider.py:207:    "model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:211:    "completion_tokens",
vibecomfy/comfy_nodes/agent/provider.py:228:    attempts = coerce_model_attempts(response.get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:230:        merged["model_attempts"] = [dict(item) for item in attempts]
vibecomfy/comfy_nodes/agent/provider.py:418:        "Example: `pil = vibecomfy.exec(source='import torch; return {\"image\": image[0]}', io={'inputs': {'image': 'IMAGE'}, 'outputs': {'image': 'IMAGE'}}, in_0=decode.IMAGE)` "
vibecomfy/comfy_nodes/agent/provider.py:815:    return {
vibecomfy/comfy_nodes/agent/provider.py:909:    return {
vibecomfy/comfy_nodes/agent/provider.py:953:    return {
vibecomfy/comfy_nodes/agent/provider.py:1395:    attempts = list(coerce_model_attempts(response.get("model_attempts")))
vibecomfy/comfy_nodes/agent/provider.py:1407:        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
vibecomfy/comfy_nodes/agent/provider.py:1409:        replace_last_model_attempt(revised)
vibecomfy/comfy_nodes/agent/provider.py:1412:    exc.model_attempts = list(attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/provider.py:1424:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/provider.py:1500:                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:1504:                metadata["model_attempts"] = [*attempt_log, *current_attempts]
vibecomfy/comfy_nodes/agent/provider.py:1620:        return {
vibecomfy/comfy_nodes/agent/provider.py:1716:    return {
vibecomfy/comfy_nodes/agent/provider.py:1751:    return {
vibecomfy/comfy_nodes/agent/provider.py:1791:        return {
vibecomfy/comfy_nodes/agent/provider.py:1800:    return {
vibecomfy/executor/core.py:35:    begin_model_attempt_capture,
vibecomfy/executor/core.py:37:    end_model_attempt_capture,
vibecomfy/executor/core.py:39:    snapshot_model_attempt_capture,
vibecomfy/executor/core.py:101:        return {}
vibecomfy/executor/core.py:102:    return {"route": spec.agent, "model": spec.model, "effort": spec.effort}
vibecomfy/executor/core.py:113:    "model_attempts",
vibecomfy/executor/core.py:117:    "completion_tokens",
vibecomfy/executor/core.py:187:                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
vibecomfy/executor/core.py:228:    attempts = context.get("model_attempts")
vibecomfy/executor/core.py:230:        return {"attempts": [dict(item) for item in attempts if isinstance(item, Mapping)]}
vibecomfy/executor/core.py:238:    return {"turns": [{"error": dict(evidence)}]}
vibecomfy/executor/core.py:1241:    return {
vibecomfy/executor/core.py:1979:    attempt_token = begin_model_attempt_capture()
vibecomfy/executor/core.py:1990:        model_attempts = snapshot_model_attempt_capture()
vibecomfy/executor/core.py:1991:        if not model_attempts and isinstance(model_response, Mapping):
vibecomfy/executor/core.py:1994:                model_attempts = tuple(
vibecomfy/executor/core.py:2009:            model_attempts=model_attempts,
vibecomfy/executor/core.py:2015:        end_model_attempt_capture(attempt_token)
vibecomfy/comfy_nodes/agent/runtime.py:52:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/runtime.py:66:# A fresh worker/transport retry is deliberately narrow: only a canonical
vibecomfy/comfy_nodes/agent/runtime.py:78:    "vibecomfy_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:117:def begin_model_attempt_capture() -> contextvars.Token:
vibecomfy/comfy_nodes/agent/runtime.py:121:def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
vibecomfy/comfy_nodes/agent/runtime.py:122:    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())
vibecomfy/comfy_nodes/agent/runtime.py:125:def end_model_attempt_capture(token: contextvars.Token) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:129:def record_model_attempts(value: Any) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:134:    for attempt in coerce_model_attempts(value):
vibecomfy/comfy_nodes/agent/runtime.py:140:def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:143:    normalized = coerce_model_attempts([value])
vibecomfy/comfy_nodes/agent/runtime.py:207:    # Re-read the env file each call so a freshly browser-submitted key is seen
vibecomfy/comfy_nodes/agent/runtime.py:416:    # ~/.hermes/.env and would ignore a freshly-exported key. No-op when unset.
vibecomfy/comfy_nodes/agent/runtime.py:474:        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
vibecomfy/comfy_nodes/agent/runtime.py:478:            resolved_model = _normalize_native_deepseek_model(resolved_model)
vibecomfy/comfy_nodes/agent/runtime.py:480:            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
vibecomfy/comfy_nodes/agent/runtime.py:482:            model=resolved_model,
vibecomfy/comfy_nodes/agent/runtime.py:495:    attempts = coerce_model_attempts(result.get("model_attempts"))
vibecomfy/comfy_nodes/agent/runtime.py:504:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/runtime.py:523:def _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:527:    requested_model: str | None,
vibecomfy/comfy_nodes/agent/runtime.py:528:    resolved_model: str | None,
vibecomfy/comfy_nodes/agent/runtime.py:540:        requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:541:        resolved_model=resolved_model or agent_kwargs.get("model"),
vibecomfy/comfy_nodes/agent/runtime.py:549:def _run_worker(
vibecomfy/comfy_nodes/agent/runtime.py:557:    requested_model: str | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:563:    A fresh subprocess/transport is permitted only after a canonical
vibecomfy/comfy_nodes/agent/runtime.py:564:    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
vibecomfy/comfy_nodes/agent/runtime.py:573:            result = _run_worker_once(
vibecomfy/comfy_nodes/agent/runtime.py:580:                requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:585:            timeout_attempt = _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:588:                requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:589:                resolved_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:594:            record_model_attempts([timeout_attempt])
vibecomfy/comfy_nodes/agent/runtime.py:595:            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/runtime.py:597:        attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/comfy_nodes/agent/runtime.py:602:            record_model_attempts([normalized])
vibecomfy/comfy_nodes/agent/runtime.py:604:            result["model_attempts"] = list(accumulated_attempts)
vibecomfy/comfy_nodes/agent/runtime.py:621:def _run_worker_once(
vibecomfy/comfy_nodes/agent/runtime.py:629:    requested_model: str | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:635:    Single attempt — no retry. See :func:`_run_worker` for the retry wrapper.
vibecomfy/comfy_nodes/agent/runtime.py:649:                    "requested_model": requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:754:    result = _run_worker(
vibecomfy/comfy_nodes/agent/runtime.py:761:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:798:    result = _run_worker(
vibecomfy/comfy_nodes/agent/runtime.py:805:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:836:    result = _run_worker(
vibecomfy/comfy_nodes/agent/runtime.py:843:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:973:        return {
vibecomfy/comfy_nodes/agent/runtime.py:998:            return {
vibecomfy/comfy_nodes/agent/runtime.py:1014:        return {
vibecomfy/comfy_nodes/agent/runtime.py:1042:            return {
vibecomfy/comfy_nodes/agent/runtime.py:1056:        return {
vibecomfy/comfy_nodes/agent/runtime.py:1083:            return {
vibecomfy/comfy_nodes/agent/runtime.py:1092:    return {
vibecomfy/comfy_nodes/agent/runtime.py:1112:    return {
vibecomfy/comfy_nodes/agent/runtime.py:1178:        result = _run_worker(
vibecomfy/comfy_nodes/agent/runtime.py:1185:            requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:1200:    "end_deepseek_usage_capture", "begin_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1201:    "snapshot_model_attempt_capture", "end_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1202:    "record_model_attempts", "replace_last_model_attempt",
vibecomfy/agent/artifacts.py:32:    "model_attempts.json",
vibecomfy/agent/artifacts.py:52:        return {str(key): _json_safe(item) for key, item in value.items()}
vibecomfy/agent/artifacts.py:136:    return {}
vibecomfy/agent/artifacts.py:336:    model_attempts = report.get("model_attempts")
vibecomfy/agent/artifacts.py:337:    if isinstance(model_attempts, (list, tuple)) and model_attempts:
vibecomfy/agent/artifacts.py:339:            output_dir / "model_attempts.json",
vibecomfy/agent/artifacts.py:340:            {"attempts": _redact(model_attempts)},
vibecomfy/agent/artifacts.py:342:        _append_manifest(manifest, "model_attempts.json")
vibecomfy/agent/artifacts.py:391:    return {

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '40,170p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
    40	import time
    41	import logging
    42	from pathlib import Path
    43	from typing import Any, Mapping, Sequence
    44
    45	from vibecomfy.agent.deepseek_usage import (
    46	    add_deepseek_usage,
    47	    coerce_deepseek_usage,
    48	    empty_deepseek_usage,
    49	)
    50	from vibecomfy.executor.contracts import (
    51	    ModelAttemptEvidence,
    52	    coerce_model_attempts,
    53	    normalize_model_endpoint,
    54	)
    55	from vibecomfy.executor.profiler import (
    56	    new_profile_id,
    57	    profiler_log,
    58	    profiler_span,
    59	    short_text,
    60	)
    61
    62	# How long to wait for a single agent turn (subprocess) before giving up.
    63	_TURN_TIMEOUT_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "180"))
    64	_WORKER_PATH = str(Path(__file__).with_name("worker.py"))
    65
    66	# A fresh worker/transport retry is deliberately narrow: only a canonical
    67	# empty-response failure with observed zero completion tokens may consume the
    68	# extra attempts. Timeouts, capacity/provider errors, and malformed content do
    69	# not retry here.
    70	_WORKER_TRANSIENT_MAX_ATTEMPTS = max(1, int(os.getenv("VIBECOMFY_AGENT_TURN_RETRIES", "3")))
    71	_WORKER_TRANSIENT_BACKOFF_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_RETRY_BACKOFF", "2.0"))
    72	LOGGER = logging.getLogger(__name__)
    73	_DEEPSEEK_USAGE_CAPTURE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    74	    "vibecomfy_deepseek_usage_capture",
    75	    default=None,
    76	)
    77	_MODEL_ATTEMPT_CAPTURE: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    78	    "vibecomfy_model_attempt_capture",
    79	    default=None,
    80	)
    81
    82	_CANONICAL_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    83	_OPENROUTER_MODEL = os.getenv("VIBECOMFY_OPENROUTER_MODEL", "openrouter:deepseek/deepseek-v4-pro")
    84	_OPENROUTER_BASE_URL = os.getenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    85	_OPENROUTER_MAX_TOKENS = int(os.getenv("VIBECOMFY_OPENROUTER_MAX_TOKENS", "2048"))
    86
    87	# Arnold/Hermes (Claude etc.) default model when a non-browser-key route is used.
    88	_ARNOLD_MODEL = os.getenv("VIBECOMFY_ARNOLD_MODEL", "anthropic/claude-opus-4.6")
    89	_ARNOLD_BASE_URL = os.getenv("VIBECOMFY_ARNOLD_BASE_URL") or None
    90
    91	_HERMES_ENV_PATH = Path("~/.hermes/.env").expanduser()
    92
    93
    94	def begin_deepseek_usage_capture() -> contextvars.Token:
    95	    return _DEEPSEEK_USAGE_CAPTURE.set(
    96	        {
    97	            "usage": empty_deepseek_usage(),
    98	            "cache_breakout_complete": True,
    99	        }
   100	    )
   101
   102
   103	def snapshot_deepseek_usage_capture() -> tuple[dict[str, int], bool]:
   104	    state = _DEEPSEEK_USAGE_CAPTURE.get()
   105	    if not isinstance(state, dict):
   106	        return empty_deepseek_usage(), False
   107	    usage = coerce_deepseek_usage(state.get("usage"))
   108	    if usage["n_calls"] <= 0:
   109	        return usage, False
   110	    return usage, bool(state.get("cache_breakout_complete"))
   111
   112
   113	def end_deepseek_usage_capture(token: contextvars.Token) -> None:
   114	    _DEEPSEEK_USAGE_CAPTURE.reset(token)
   115
   116
   117	def begin_model_attempt_capture() -> contextvars.Token:
   118	    return _MODEL_ATTEMPT_CAPTURE.set([])
   119
   120
   121	def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
   122	    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())
   123
   124
   125	def end_model_attempt_capture(token: contextvars.Token) -> None:
   126	    _MODEL_ATTEMPT_CAPTURE.reset(token)
   127
   128
   129	def record_model_attempts(value: Any) -> None:
   130	    """Append canonical attempts to the active executor capture, without duplicates."""
   131	    state = _MODEL_ATTEMPT_CAPTURE.get()
   132	    if state is None:
   133	        return
   134	    for attempt in coerce_model_attempts(value):
   135	        if state and state[-1] == attempt:
   136	            continue
   137	        state.append(attempt)
   138
   139
   140	def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
   141	    """Replace the most recent captured transport-success after domain parse failure."""
   142	    state = _MODEL_ATTEMPT_CAPTURE.get()
   143	    normalized = coerce_model_attempts([value])
   144	    if state is None or not normalized:
   145	        return
   146	    if state:
   147	        state[-1] = normalized[0]
   148	    else:
   149	        state.append(normalized[0])
   150
   151
   152	def _record_captured_deepseek_usage(result: Any) -> None:
   153	    state = _DEEPSEEK_USAGE_CAPTURE.get()
   154	    if not isinstance(state, dict) or not isinstance(result, dict):
   155	        return
   156	    usage = coerce_deepseek_usage(result.get("deepseek_usage"))
   157	    if usage["n_calls"] <= 0:
   158	        return
   159	    state["usage"] = add_deepseek_usage(state.get("usage"), usage)
   160	    if not result.get("deepseek_cache_breakout_complete", False):
   161	        state["cache_breakout_complete"] = False
   162
   163
   164	def _read_env_file_entries(path: Path = _HERMES_ENV_PATH) -> list[tuple[str, str]]:
   165	    """Read dotenv-style key/value pairs in file order."""
   166	    entries: list[tuple[str, str]] = []
   167	    try:
   168	        text = path.read_text(encoding="utf-8")
   169	    except (FileNotFoundError, OSError):
   170	        return entries

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '440,675p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   440	    """Return (system_message, user_message) from VibeComfy's built messages."""
   441	    system_msg: str | None = None
   442	    user_msg: str | None = None
   443	    for entry in messages or []:
   444	        role = entry.get("role")
   445	        content = entry.get("content")
   446	        if not isinstance(content, str):
   447	            continue
   448	        if role == "system" and system_msg is None:
   449	            system_msg = content
   450	        elif role == "user":
   451	            user_msg = content
   452	    return system_msg, user_msg
   453
   454
   455	def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | None = None) -> dict[str, Any]:
   456	    """AIAgent constructor kwargs for a single, tool-free completion.
   457
   458	    Keyed off the resolved *dispatch agent id* (not the panel route). ``hermes``
   459	    is always configured for OpenRouter, including the legacy ``deepseek`` route
   460	    alias. For ``codex`` / ``claude`` the worker dispatches through the default
   461	    dispatcher and ignores ``agent_kwargs``, so we pass only the tool-free
   462	    single-shot flags.
   463	    """
   464	    common: dict[str, Any] = dict(
   465	        max_iterations=1,
   466	        enabled_toolsets=[],          # no tools: one-shot completion
   467	        save_trajectories=False,      # no trajectory files on disk
   468	        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
   469	        skip_memory=True,             # don't load/write the memory store
   470	        quiet_mode=True,
   471	    )
   472	    if agent_id == "hermes":
   473	        base_url = _base_url_for_route(route)
   474	        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
   475	        if _is_native_deepseek_endpoint(base_url):
   476	            # Native api.deepseek.com rejects OpenRouter-style ``deepseek/`` slugs
   477	            # with HTTP 400; normalize to the bare model name it accepts.
   478	            resolved_model = _normalize_native_deepseek_model(resolved_model)
   479	        else:
   480	            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
   481	        return dict(
   482	            model=resolved_model,
   483	            api_key=_hermes_credential_for(route, model),
   484	            base_url=base_url,
   485	            provider="openrouter",
   486	            max_tokens=_OPENROUTER_MAX_TOKENS,
   487	            **common,
   488	        )
   489	    # codex / claude -> default dispatcher resolves everything; kwargs unused.
   490	    return dict(**common)
   491
   492
   493	def _is_typed_empty_worker_result(result: Mapping[str, Any]) -> bool:
   494	    """True only for typed empty responses with observed zero completion tokens."""
   495	    attempts = coerce_model_attempts(result.get("model_attempts"))
   496	    if not attempts:
   497	        return False
   498	    latest = attempts[-1]
   499	    usage = latest.get("token_usage")
   500	    return (
   501	        latest.get("outcome") == "failure"
   502	        and latest.get("failure_type") == "empty_response"
   503	        and isinstance(usage, Mapping)
   504	        and usage.get("completion_tokens") == 0
   505	    )
   506
   507
   508	def _runtime_provider_transport(
   509	    *, agent_id: str, agent_kwargs: Mapping[str, Any]
   510	) -> tuple[str, str, str]:
   511	    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
   512	    if agent_id != "hermes":
   513	        return "unknown", "unknown", endpoint
   514	    if "openrouter.ai" in endpoint:
   515	        return "openrouter", "openrouter", endpoint
   516	    if "deepseek.com" in endpoint:
   517	        return "deepseek", "native", endpoint
   518	    if endpoint != "unknown":
   519	        return "unknown", "openai_compatible", endpoint
   520	    return "unknown", "unknown", endpoint
   521
   522
   523	def _timeout_model_attempt(
   524	    *,
   525	    agent_kwargs: Mapping[str, Any],
   526	    agent_id: str,
   527	    requested_model: str | None,
   528	    resolved_model: str | None,
   529	    profiling_context: Mapping[str, Any] | None,
   530	    attempt: int,
   531	) -> dict[str, Any]:
   532	    provider, transport, endpoint = _runtime_provider_transport(
   533	        agent_id=agent_id, agent_kwargs=agent_kwargs
   534	    )
   535	    return ModelAttemptEvidence(
   536	        phase=(profiling_context or {}).get("backend_phase") or "agent_turn",
   537	        attempt=attempt,
   538	        outcome="failure",
   539	        failure_type="timeout",
   540	        requested_model=requested_model,
   541	        resolved_model=resolved_model or agent_kwargs.get("model"),
   542	        adapter=agent_id,
   543	        provider=provider,
   544	        transport=transport,
   545	        endpoint=endpoint,
   546	    ).to_dict()
   547
   548
   549	def _run_worker(
   550	    agent_kwargs: dict[str, Any],
   551	    system_msg: str | None,
   552	    user_msg: str,
   553	    *,
   554	    response_contract: str = "python",
   555	    agent_id: str = "hermes",
   556	    model: str | None = None,
   557	    requested_model: str | None = None,
   558	    effort: str | None = None,
   559	    profiling_context: Mapping[str, Any] | None = None,
   560	) -> dict[str, Any]:
   561	    """Run one AIAgent turn in an isolated subprocess; return its result dict.
   562
   563	    A fresh subprocess/transport is permitted only after a canonical
   564	    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
   565	    provider/capacity errors, and malformed non-empty content surface immediately.
   566	    """
   567	    accumulated_attempts: list[dict[str, Any]] = []
   568	    for attempt in range(_WORKER_TRANSIENT_MAX_ATTEMPTS):
   569	        attempt_profile = dict(profiling_context or {})
   570	        if attempt:
   571	            attempt_profile["transient_retry_count"] = attempt
   572	        try:
   573	            result = _run_worker_once(
   574	                agent_kwargs,
   575	                system_msg,
   576	                user_msg,
   577	                response_contract=response_contract,
   578	                agent_id=agent_id,
   579	                model=model,
   580	                requested_model=requested_model,
   581	                effort=effort,
   582	                profiling_context=attempt_profile,
   583	            )
   584	        except TimeoutError as exc:
   585	            timeout_attempt = _timeout_model_attempt(
   586	                agent_kwargs=agent_kwargs,
   587	                agent_id=agent_id,
   588	                requested_model=requested_model,
   589	                resolved_model=model,
   590	                profiling_context=profiling_context,
   591	                attempt=len(accumulated_attempts) + 1,
   592	            )
   593	            accumulated_attempts.append(timeout_attempt)
   594	            record_model_attempts([timeout_attempt])
   595	            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
   596	            raise
   597	        attempts = list(coerce_model_attempts(result.get("model_attempts")))
   598	        for item in attempts:
   599	            item["attempt"] = len(accumulated_attempts) + 1
   600	            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
   601	            accumulated_attempts.append(normalized)
   602	            record_model_attempts([normalized])
   603	        if accumulated_attempts:
   604	            result["model_attempts"] = list(accumulated_attempts)
   605	        if (
   606	            "error" in result
   607	            and _is_typed_empty_worker_result(result)
   608	            and attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS
   609	        ):
   610	            LOGGER.warning(
   611	                "agent worker returned typed empty response (attempt %d/%d); retrying",
   612	                attempt + 1,
   613	                _WORKER_TRANSIENT_MAX_ATTEMPTS,
   614	            )
   615	            time.sleep(_WORKER_TRANSIENT_BACKOFF_SECONDS * attempt)
   616	            continue
   617	        return result
   618	    raise RuntimeError("agent worker retry loop exited without a result")
   619
   620
   621	def _run_worker_once(
   622	    agent_kwargs: dict[str, Any],
   623	    system_msg: str | None,
   624	    user_msg: str,
   625	    *,
   626	    response_contract: str = "python",
   627	    agent_id: str = "hermes",
   628	    model: str | None = None,
   629	    requested_model: str | None = None,
   630	    effort: str | None = None,
   631	    profiling_context: Mapping[str, Any] | None = None,
   632	) -> dict[str, Any]:
   633	    """Run one AIAgent turn in an isolated subprocess; return its result dict.
   634
   635	    Single attempt — no retry. See :func:`_run_worker` for the retry wrapper.
   636
   637	    Isolation avoids the top-level module-name collision between megaplan's
   638	    agent (bare ``import utils`` / ``model_tools``) and ComfyUI's own ``utils``
   639	    package, and keeps the agent's asyncio/HTTP state out of ComfyUI's loop.
   640	    """
   641	    with tempfile.TemporaryDirectory(prefix="vibecomfy-agent-") as tmp:
   642	        req_path = os.path.join(tmp, "request.json")
   643	        res_path = os.path.join(tmp, "result.json")
   644	        with open(req_path, "w", encoding="utf-8") as fh:
   645	            json.dump(
   646	                {
   647	                    "agent_id": agent_id,
   648	                    "model": model,
   649	                    "requested_model": requested_model,
   650	                    "effort": effort,
   651	                    "agent_kwargs": agent_kwargs,
   652	                    "system_message": system_msg,
   653	                    "user_message": user_msg,
   654	                    "response_contract": response_contract,
   655	                    "profiling_context": dict(profiling_context or {}),
   656	                },
   657	                fh,
   658	            )
   659	        env = dict(os.environ)
   660	        # Ensure the child sees the same credential the parent resolved for the
   661	        # Hermes adapter.  For native DeepSeek endpoints this must be the
   662	        # DeepSeek key, not a stale browser/OpenRouter key from ~/.hermes/.env.
   663	        hermes_key = agent_kwargs.get("api_key") or _resolve_openrouter_key()
   664	        if isinstance(hermes_key, str) and hermes_key:
   665	            env["OPENROUTER_API_KEY"] = hermes_key
   666	            env["OPENAI_API_KEY"] = hermes_key
   667	            env["HERMES_API_KEY"] = hermes_key
   668	        # Don't leak ComfyUI's cwd/path into the child (it is what causes the
   669	        # `utils` collision); run from a neutral directory.
   670	        try:
   671	            with profiler_span(
   672	                LOGGER,
   673	                "runtime.worker_subprocess",
   674	                agent_id=agent_id,
   675	                response_contract=response_contract,

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '725,865p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   725	    *,
   726	    task: str,
   727	    python_source: str,
   728	    route: str,
   729	    model: str | None = None,
   730	    effort: str | None = None,
   731	    messages: Sequence[Mapping[str, Any]] | None = None,
   732	) -> dict[str, Any]:
   733	    """Run one agent-edit turn through the megaplan AIAgent backend.
   734
   735	    Returns ``{"python": <str>, "message": <str>}`` as VibeComfy expects.
   736	    """
   737	    agent_id = _agent_id_for_route(route)
   738	    system_msg, user_msg = _split_messages(messages)
   739	    if user_msg is None:
   740	        # Fall back to reconstructing the user message from the raw inputs.
   741	        user_msg = (
   742	            f"User request:\n{task}\n\n"
   743	            "Current scratchpad Python:\n```python\n" + (python_source or "") + "\n```"
   744	        )
   745
   746	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   747	        raise PermissionError(
   748	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   749	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   750	            "VibeComfy panel or export OPENROUTER_API_KEY."
   751	        )
   752
   753	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   754	    result = _run_worker(
   755	        agent_kwargs,
   756	        system_msg,
   757	        user_msg,
   758	        response_contract="python",
   759	        agent_id=agent_id,
   760	        model=_runtime_model_for_route(route, model),
   761	        requested_model=model,
   762	        effort=effort,
   763	        profiling_context={"backend_phase": "implement"},
   764	    )
   765	    if "error" in result:
   766	        _raise_worker_error(result)
   767	    return dict(result)
   768
   769
   770	def run_agent_turn_delta(
   771	    *,
   772	    task: str,
   773	    projection: str,
   774	    op_schema: Mapping[str, Any],
   775	    route: str,
   776	    model: str | None = None,
   777	    effort: str | None = None,
   778	    messages: Sequence[Mapping[str, Any]] | None = None,
   779	) -> dict[str, Any]:
   780	    """Run one v2 agent-edit turn and return ``{"delta": [...], "message": str}``."""
   781	    agent_id = _agent_id_for_route(route)
   782	    system_msg, user_msg = _split_messages(messages)
   783	    if user_msg is None:
   784	        user_msg = (
   785	            f"User request:\n{task}\n\n"
   786	            "Address-preserving UI projection:\n"
   787	            f"{projection}"
   788	        )
   789
   790	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   791	        raise PermissionError(
   792	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   793	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   794	            "VibeComfy panel or export OPENROUTER_API_KEY."
   795	        )
   796
   797	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   798	    result = _run_worker(
   799	        agent_kwargs,
   800	        system_msg,
   801	        user_msg,
   802	        response_contract="delta",
   803	        agent_id=agent_id,
   804	        model=_runtime_model_for_route(route, model),
   805	        requested_model=model,
   806	        effort=effort,
   807	        profiling_context={"backend_phase": "implement"},
   808	    )
   809	    if "error" in result:
   810	        _raise_worker_error(result)
   811	    return dict(result)
   812
   813
   814	def run_agent_turn_batch(
   815	    *,
   816	    task: str,
   817	    route: str,
   818	    model: str | None = None,
   819	    effort: str | None = None,
   820	    messages: Sequence[Mapping[str, Any]] | None = None,
   821	) -> dict[str, Any]:
   822	    """Run one batch-REPL agent-edit turn and return raw model content."""
   823	    agent_id = _agent_id_for_route(route)
   824	    system_msg, user_msg = _split_messages(messages)
   825	    if user_msg is None:
   826	        user_msg = f"User request:\n{task}"
   827
   828	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   829	        raise PermissionError(
   830	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   831	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   832	            "VibeComfy panel or export OPENROUTER_API_KEY."
   833	        )
   834
   835	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   836	    result = _run_worker(
   837	        agent_kwargs,
   838	        system_msg,
   839	        user_msg,
   840	        response_contract="batch_repl",
   841	        agent_id=agent_id,
   842	        model=_runtime_model_for_route(route, model),
   843	        requested_model=model,
   844	        effort=effort,
   845	        profiling_context={"backend_phase": "batch"},
   846	    )
   847	    if "error" in result:
   848	        _raise_worker_error(result)
   849	    return dict(result)
   850
   851
   852	def _requested_route(route: str | None) -> str:
   853	    """Canonical panel route name (claude->anthropic, codex->openai-codex).
   854
   855	    The ``hermes`` dispatch agent id is exposed as a product route in headless
   856	    executor specs; for readiness/status purposes it is the same as the
   857	    OpenRouter browser-key route.
   858	    """
   859	    requested = (route or "").strip().lower()
   860	    if requested == "claude":
   861	        return "anthropic"
   862	    if requested == "codex":
   863	        return "openai-codex"
   864	    if requested in {"deepseek", "hermes"}:
   865	        return "openrouter"

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1150,1210p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
  1150	            str(profiling_context.get("model_turn_id"))
  1151	            if isinstance(profiling_context, Mapping) and profiling_context.get("model_turn_id")
  1152	            else new_profile_id("model")
  1153	        ),
  1154	        "route": route,
  1155	        "model": model,
  1156	        "response_contract": response_contract,
  1157	        **(dict(profiling_context or {})),
  1158	    }
  1159
  1160	    with profiler_span(
  1161	        LOGGER,
  1162	        "runtime.run_model_turn",
  1163	        model_turn_id=effective_profile.get("model_turn_id"),
  1164	        agent_id=agent_id,
  1165	        route=route,
  1166	        model=model,
  1167	        response_contract=response_contract,
  1168	        task_preview=short_text(task),
  1169	    ) as span:
  1170	        if agent_id == "hermes" and not _hermes_credential_for(route, model):
  1171	            raise PermissionError(
  1172	                "OpenRouter route selected but no OPENROUTER_API_KEY is available "
  1173	                "(checked environment and ~/.hermes/.env). Submit a key via the "
  1174	                "VibeComfy panel or export OPENROUTER_API_KEY."
  1175	            )
  1176
  1177	        agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
  1178	        result = _run_worker(
  1179	            agent_kwargs,
  1180	            system_msg,
  1181	            user_msg,
  1182	            response_contract=response_contract,
  1183	            agent_id=agent_id,
  1184	            model=_runtime_model_for_route(route, model),
  1185	            requested_model=model,
  1186	            effort=effort,
  1187	            profiling_context=effective_profile,
  1188	        )
  1189	        if "error" in result:
  1190	            _raise_worker_error(result)
  1191
  1192	        span.update(
  1193	            result_keys=sorted(result.keys()),
  1194	            worker_profile=result.get("_profiling") if isinstance(result.get("_profiling"), dict) else None,
  1195	        )
  1196	        return result
  1197
  1198	__all__ = [
  1199	    "begin_deepseek_usage_capture", "snapshot_deepseek_usage_capture",
  1200	    "end_deepseek_usage_capture", "begin_model_attempt_capture",
  1201	    "snapshot_model_attempt_capture", "end_model_attempt_capture",
  1202	    "record_model_attempts", "replace_last_model_attempt",
  1203	    "run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch",
  1204	    "run_model_turn", "readiness", "get_agent_status",
  1205	]

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '300,445p'; nl -ba vibecomfy/executor/agent_backend.py | sed -n '1,190p'; nl -ba vibecomfy/executor/core.py | sed -n '80,255p'; nl -ba vibecomfy/executor/core.py | sed -n '1940,2030p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 4ms:
  1940
  1941	    Parameters
  1942	    ----------
  1943	    request:
  1944	        The parsed executor request (query + optional graph/profile/etc.).
  1945	    classify_only:
  1946	        When True, run only the classify phase and return a diagnostic result
  1947	        without invoking research, implement, or reply model calls.  This is
  1948	        the honest dry-run seam: ``live=false`` is a product flag, but
  1949	        ``classify_only`` guarantees no subsequent phases run.
  1950	    additive:
  1951	        Headless-only caller hint that this is an additive restore (the caller
  1952	        removed a feature and now asks to re-add it).  Forwarded into the
  1953	        implement payload so the revise pipeline can relax ONLY the pre-edit
  1954	        "input graph has dangling/absent endpoints -> refuse to compound"
  1955	        precondition.  All post-edit validation and gates remain enforced.
  1956
  1957	    Returns
  1958	    -------
  1959	    ExecutorResult
  1960	        Always returns a result — failures are captured in the result
  1961	        shape, never raised as raw exceptions.
  1962	    """
  1963	    plan: ClassifyDecision | None = None
  1964	    research_result: ResearchResult | None = None
  1965	    implementation_result: ImplementationResult | None = None
  1966	    effective_graph: dict[str, Any] | None = request.graph
  1967	    result_graph: dict[str, Any] | None = None
  1968	    executor_id = new_profile_id("executor")
  1969	    request_fields = {
  1970	        "executor_id": executor_id,
  1971	        "profile": request.profile or "default",
  1972	        "session_id": request.session_id,
  1973	        "has_graph": request.graph is not None,
  1974	        "query_preview": short_text(request.query),
  1975	    }
  1976
  1977	    profiler_log(LOGGER, "executor.request", **request_fields)
  1978	    usage_token = begin_deepseek_usage_capture()
  1979	    attempt_token = begin_model_attempt_capture()
  1980
  1981	    def _build_report(
  1982	        *,
  1983	        plan: ClassifyDecision | None = None,
  1984	        research: ResearchResult | None = None,
  1985	        implementation: ImplementationResult | None = None,
  1986	        classification_status: str = "",
  1987	        model_response: dict[str, Any] | None = None,
  1988	    ) -> Report:
  1989	        usage, cache_breakout_complete = snapshot_deepseek_usage_capture()
  1990	        model_attempts = snapshot_model_attempt_capture()
  1991	        if not model_attempts and isinstance(model_response, Mapping):
  1992	            raw_attempts = model_response.get("attempts")
  1993	            if isinstance(raw_attempts, (list, tuple)):
  1994	                model_attempts = tuple(
  1995	                    dict(item) for item in raw_attempts if isinstance(item, Mapping)
  1996	                )
  1997	        est_cost_usd, cost_basis = estimate_deepseek_cost_usd(
  1998	            usage,
  1999	            cache_breakout_complete=cache_breakout_complete,
  2000	        )
  2001	        return Report(
  2002	            plan=plan,
  2003	            research=research,
  2004	            implementation=implementation,
  2005	            deepseek_usage=usage,
  2006	            deepseek_est_cost_usd=est_cost_usd,
  2007	            deepseek_cost_basis=cost_basis,
  2008	            classification_status=classification_status,
  2009	            model_attempts=model_attempts,
  2010	            model_response=model_response,
  2011	        )
  2012
  2013	    def _finish(result: ExecutorResult) -> ExecutorResult:
  2014	        end_deepseek_usage_capture(usage_token)
  2015	        end_model_attempt_capture(attempt_token)
  2016	        return result
  2017
  2018	    # ── Resolve profile specs ────────────────────────────────────────────
  2019	    try:
  2020	        classify_spec = _resolve_spec(request.profile, "classify")
  2021	    except Exception as exc:
  2022	        failure = classify_failure("profile", exc)
  2023	        return _finish(ExecutorResult.failure(
  2024	            kind=failure.kind.value,
  2025	            stage="profile",
  2026	            message=failure.user_facing_message,
  2027	            report=_build_report(),
  2028	        ))
  2029	    profiler_log(
  2030	        LOGGER,

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/agent_backend.py | sed -n '170,390p'; nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '1360,1530p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   170	    """
   171	    if messages is None:
   172	        messages = build_classify_messages(
   173	            query,
   174	            has_graph=has_graph,
   175	            graph_summary=graph_summary,
   176	            layout_hint=layout_hint,
   177	        )
   178	    model_turn_id = new_profile_id("model")
   179	    with profiler_span(
   180	        LOGGER,
   181	        "executor.model_turn",
   182	        model_turn_id=model_turn_id,
   183	        backend_phase="classify",
   184	        route=route,
   185	        model=model,
   186	        response_contract="json",
   187	        has_graph=has_graph,
   188	        graph_summary=graph_summary,
   189	        query_preview=short_text(query),
   190	    ) as span:
   191	        from vibecomfy.comfy_nodes.agent.provider import run_model_turn
   192
   193	        result = run_model_turn(
   194	            query,
   195	            messages,
   196	            route=route,
   197	            model=model,
   198	            effort=effort,
   199	            response_contract="json",
   200	            profiling_context={"backend_phase": "classify"},
   201	        )
   202	        raw: str | None = None
   203	        try:
   204	            raw = _extract_content(result)
   205	            decision = parse_classify_response(raw)
   206	        except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
   207	            _mark_last_attempt_failed(
   208	                result,
   209	                raw=raw,
   210	                failure_type=_downstream_failure_type(raw),
   211	            )
   212	            _attach_model_turn_evidence(
   213	                exc,
   214	                result,
   215	                model=model,
   216	                phase="classify",
   217	                raw=raw,
   218	            )
   219	            raise
   220	        _record_result_attempts(result)
   221	        span.update(
   222	            content_length=len(raw),
   223	            plan_research=decision.research,
   224	            plan_implement=decision.implement,
   225	            plan_reply=decision.reply,
   226	        )
   227	        return decision
   228
   229
   230	def run_reply_turn(
   231	    query: str,
   232	    *,
   233	    route: str,
   234	    model: str,
   235	    effort: str | None = None,
   236	    plan: ClassifyDecision | None = None,
   237	    research_summary: str | None = None,
   238	    research_sources: tuple[dict[str, Any], ...] | None = None,
   239	    research_warnings: tuple[str, ...] | None = None,
   240	    research_precedent_slices: tuple[dict[str, Any], ...] | None = None,
   241	    implementation_message: str | None = None,
   242	    graph_summary: str | None = None,
   243	    graph_inspection: str | None = None,
   244	    adaptation_plan: dict[str, Any] | None = None,
   245	    effective_route: str | None = None,
   246	    effective_task: str | None = None,
   247	    candidate_present: bool = False,
   248	) -> str:
   249	    """Run a single reply model turn through the provider seam.
   250
   251	    Builds reply-specific messages via :func:`build_reply_messages`,
   252	    dispatches through :func:`run_model_turn` with ``response_contract="json"``,
   253	    and parses the result with :func:`parse_reply_response`.
   254
   255	    Parameters
   256	    ----------
   257	    query:
   258	        The user's natural-language request.
   259	    route:
   260	        Provider route name (resolved from the profile's ``agent`` field).
   261	    model:
   262	        Model identifier (resolved from the profile's ``model`` field).
   263	    plan:
   264	        The classify decision (provides context for the reply).
   265	    research_summary:
   266	        Optional research findings summary.
   267	    research_sources:
   268	        Optional deduplicated research sources for reply context.
   269	    implementation_message:
   270	        Optional implementation result message.
   271	    graph_summary:
   272	        Optional compact summary of the attached graph.
   273	    graph_inspection:
   274	        Optional detailed node-by-node graph inspection for inspect-only
   275	        replies.  When provided, the model should describe the graph
   276	        structure without suggesting edits.
   277	    adaptation_plan:
   278	        Optional serialized adaptation plan for route="adapt" replies.
   279	    effective_route:
   280	        The canonical route driving the reply phase.
   281	    effective_task:
   282	        The canonical task driving the reply phase.
   283	    candidate_present:
   284	        Whether a graph edit candidate was produced.
   285	    """
   286	    messages = build_reply_messages(
   287	        query,
   288	        plan=plan,
   289	        research_summary=research_summary,
   290	        research_sources=research_sources,
   291	        research_warnings=research_warnings,
   292	        research_precedent_slices=research_precedent_slices,
   293	        implementation_message=implementation_message,
   294	        graph_summary=graph_summary,
   295	        graph_inspection=graph_inspection,
   296	        adaptation_plan=adaptation_plan,
   297	        effective_route=effective_route,
   298	        effective_task=effective_task,
   299	        candidate_present=candidate_present,
   300	    )
   301	    model_turn_id = new_profile_id("model")
   302	    with profiler_span(
   303	        LOGGER,
   304	        "executor.model_turn",
   305	        model_turn_id=model_turn_id,
   306	        backend_phase="reply",
   307	        route=route,
   308	        model=model,
   309	        response_contract="json",
   310	        query_preview=short_text(query),
   311	    ) as span:
   312	        from vibecomfy.comfy_nodes.agent.provider import run_model_turn
   313
   314	        result = run_model_turn(
   315	            query,
   316	            messages,
   317	            route=route,
   318	            model=model,
   319	            effort=effort,
   320	            response_contract="json",
   321	            profiling_context={"backend_phase": "reply"},
   322	        )
   323	        raw: str | None = None
   324	        try:
   325	            raw = _extract_content(result)
   326	            reply = parse_reply_response(raw)
   327	        except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
   328	            _mark_last_attempt_failed(
   329	                result,
   330	                raw=raw,
   331	                failure_type=_downstream_failure_type(raw),
   332	            )
   333	            _attach_model_turn_evidence(
   334	                exc,
   335	                result,
   336	                model=model,
   337	                phase="reply",
   338	                raw=raw,
   339	            )
   340	            raise
   341	        _record_result_attempts(result)
   342	        span.update(content_length=len(raw), reply_preview=short_text(reply))
   343	        return reply
   344
   345
   346	__all__ = ["run_classify_turn", "run_reply_turn"]
  1360	        "run_agent_turn, or run."
  1361	    )
  1362
  1363
  1364	def _batch_retry_messages(
  1365	    messages: list[dict[str, str]],
  1366	    exc: BaseException,
  1367	) -> list[dict[str, str]]:
  1368	    prompt = _BATCH_REPL_PARSE_RETRY_PROMPT
  1369	    raw_preview = getattr(exc, "raw_response_preview", None)
  1370	    if isinstance(raw_preview, str) and raw_preview.strip():
  1371	        prompt = (
  1372	            f"{prompt}\n\n"
  1373	            "Previous response preview, for correction only:\n"
  1374	            f"{raw_preview.strip()}"
  1375	        )
  1376	    return [*messages, {"role": "system", "content": prompt}]
  1377
  1378
  1379	def _batch_failure_type(exc: BaseException) -> str:
  1380	    raw = getattr(exc, "raw_response", None)
  1381	    if isinstance(raw, str) and not raw.strip():
  1382	        return "empty_response"
  1383	    reason = getattr(exc, "parse_reason", None)
  1384	    if reason in {"missing_batch_fence"}:
  1385	        return "missing_required_fields"
  1386	    return "malformed_json"
  1387
  1388
  1389	def _revise_failed_runtime_attempt(
  1390	    response: Any,
  1391	    exc: BaseException,
  1392	) -> tuple[dict[str, Any], ...]:
  1393	    if not isinstance(response, Mapping):
  1394	        return ()
  1395	    attempts = list(coerce_model_attempts(response.get("model_attempts")))
  1396	    if not attempts:
  1397	        return ()
  1398	    latest = dict(attempts[-1])
  1399	    latest.update({
  1400	        "outcome": "failure",
  1401	        "failure_type": _batch_failure_type(exc),
  1402	        "raw_response_preview": getattr(exc, "raw_response", None),
  1403	    })
  1404	    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
  1405	    attempts[-1] = revised
  1406	    try:
  1407	        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
  1408
  1409	        replace_last_model_attempt(revised)
  1410	    except Exception:  # noqa: BLE001 - evidence capture is additive
  1411	        pass
  1412	    exc.model_attempts = list(attempts)  # type: ignore[attr-defined]
  1413	    return tuple(attempts)
  1414
  1415
  1416	def _typed_empty_attempt(attempts: tuple[dict[str, Any], ...]) -> bool:
  1417	    if not attempts:
  1418	        return False
  1419	    latest = attempts[-1]
  1420	    usage = latest.get("token_usage")
  1421	    return (
  1422	        latest.get("failure_type") == "empty_response"
  1423	        and isinstance(usage, Mapping)
  1424	        and usage.get("completion_tokens") == 0
  1425	    )
  1426
  1427
  1428	def run_agent_turn_batch(
  1429	    task: str,
  1430	    messages: list[dict[str, str]],
  1431	    *,
  1432	    route: str | None = None,
  1433	    model: str | None = None,
  1434	    effort: str | None = None,
  1435	) -> BatchTurnResult:
  1436	    """Run a single batch-REPL turn through the Arnold/Hermes provider.
  1437
  1438	    Sends *messages* (built by :func:`build_batch_messages`) to the model
  1439	    and normalizes the response through :func:`extract_batch_fence` instead
  1440	    of JSON parsing.  Returns a :class:`BatchTurnResult` with the fenced
  1441	    batch code and surrounding prose.
  1442
  1443	    Parameters
  1444	    ----------
  1445	    task:
  1446	        The user's natural-language edit request.
  1447	    messages:
  1448	        Pre-built chat messages from :func:`build_batch_messages`.
  1449	    route:
  1450	        Optional provider route name.  Resolved via :func:`_resolve_agent_route`.
  1451	    model:
  1452	        Optional model identifier.  Falls back to ``VIBECOMFY_AGENT_MODEL``.
  1453	    """
  1454	    route_descriptor = _resolve_agent_route(route)
  1455	    selected_route = route_descriptor.normalized_route
  1456	    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
  1457	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
  1458	    runtime = _load_arnold_runtime()
  1459	    audit_metadata: dict[str, Any] = {
  1460	        "provider": "arnold",
  1461	        "requested_route": route_descriptor.requested_route,
  1462	        "route_metadata": route_descriptor.to_dict(),
  1463	        "legacy_deepseek_fallback_enabled": False,
  1464	        "credential_presence": _credential_presence(),
  1465	        "response_contract": "batch_repl",
  1466	    }
  1467	    try:
  1468	        attempts = 3
  1469	        retry_count = 0
  1470	        last_exc: MalformedModelJSON | MissingRequiredField | None = None
  1471	        current_messages = messages
  1472	        attempt_log: list[dict[str, Any]] = []
  1473	        for attempt_index in range(attempts):
  1474	            if attempt_index > 0 and last_exc is not None:
  1475	                current_messages = _batch_retry_messages(messages, last_exc)
  1476	            response = _call_batch_runtime(
  1477	                runtime,
  1478	                task=task,
  1479	                messages=current_messages,
  1480	                route=dispatch_route,
  1481	                model=selected_model,
  1482	                effort=effort,
  1483	            )
  1484	            try:
  1485	                result = _normalize_batch_response(
  1486	                    response,
  1487	                    route=dispatch_route,
  1488	                    model=selected_model,
  1489	                    audit_metadata=audit_metadata,
  1490	                )
  1491	            except (MalformedModelJSON, MissingRequiredField) as exc:
  1492	                failed_attempts = _revise_failed_runtime_attempt(response, exc)
  1493	                attempt_log.extend(failed_attempts)
  1494	                last_exc = exc
  1495	                if attempt_index >= attempts - 1 or not _typed_empty_attempt(failed_attempts):
  1496	                    raise
  1497	                retry_count += 1
  1498	                continue
  1499	            current_attempts = list(
  1500	                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
  1501	            )
  1502	            if attempt_log:
  1503	                metadata = dict(result.audit_metadata or {})
  1504	                metadata["model_attempts"] = [*attempt_log, *current_attempts]
  1505	                result = dataclasses.replace(result, audit_metadata=metadata)
  1506	            if retry_count:
  1507	                metadata = dict(result.audit_metadata or {})
  1508	                metadata["batch_repl_retry"] = {
  1509	                    "count": retry_count,
  1510	                    "reason": str(last_exc) if last_exc is not None else "",
  1511	                    "parse_reason": getattr(last_exc, "parse_reason", None),
  1512	                    "raw_response_preview": getattr(last_exc, "raw_response_preview", None),
  1513	                }
  1514	                result = dataclasses.replace(result, audit_metadata=metadata)
  1515	            return result
  1516	        if last_exc is not None:
  1517	            raise last_exc
  1518	        raise ProviderError("Agent batch_repl provider exited without a response.")
  1519	    except PermissionError as exc:
  1520	        raise AuthError(str(exc)) from exc
  1521	    except TimeoutError:
  1522	        raise
  1523	    except ImportError:
  1524	        # The agent runtime could not be loaded — a setup fault, not a
  1525	        # transient provider outage.  Preserve the type so it is classified
  1526	        # as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure.
  1527	        raise
  1528	    except (ProviderError, MalformedModelJSON, MissingRequiredField):
  1529	        raise
  1530	    except Exception as exc:

exec
/bin/zsh -lc "nl -ba tests/test_agent_runtime_adapter.py | sed -n '390,540p'; nl -ba tests/test_runtime_worker_retry.py | sed -n '1,230p'; nl -ba tests/test_headless_agent_artifacts.py | sed -n '240,335p'; nl -ba tests/test_live_agentic_runner_persistence.py | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   390	            "error_type": "ProviderCallError",
   391	        },
   392	    )
   393
   394	    with pytest.raises(PermissionError, match="Missing Authentication header"):
   395	        runtime.run_agent_turn_batch(
   396	            task="make it brighter",
   397	            route="openrouter",
   398	            messages=[{"role": "user", "content": "User request:\nmake it brighter"}],
   399	        )
   400
   401
   402	@pytest.mark.parametrize(
   403	    ("exc", "raw", "expected"),
   404	    [
   405	        (ValueError("empty"), "", "empty_response"),
   406	        (json.JSONDecodeError("bad", "{bad", 1), "{bad", "malformed_json"),
   407	        (json.JSONDecodeError("bad", "plain prose", 0), "plain prose", "non_json_content"),
   408	        (ValueError("must include field reply"), '{"other":"x"}', "missing_required_fields"),
   409	        (TimeoutError("late"), None, "timeout"),
   410	        (RuntimeError("capacity"), None, "provider_failure"),
   411	    ],
   412	)
   413	def test_worker_failure_taxonomy_is_structural(
   414	    exc: BaseException,
   415	    raw: str | None,
   416	    expected: str,
   417	) -> None:
   418	    assert worker._model_attempt_failure_type(exc, raw) == expected
   419
   420
   421	def _canonical_success_attempt() -> dict:
   422	    return {
   423	        "phase": "batch",
   424	        "attempt": 1,
   425	        "outcome": "success",
   426	        "failure_type": None,
   427	        "requested_model": "openrouter:requested/model",
   428	        "resolved_model": "resolved/model",
   429	        "adapter": "hermes",
   430	        "provider": "openrouter",
   431	        "transport": "openrouter",
   432	        "endpoint": "https://openrouter.ai/api/v1",
   433	        "finish_reason": "stop",
   434	        "token_usage": {
   435	            "prompt_tokens": 12,
   436	            "completion_tokens": 3,
   437	            "total_tokens": 15,
   438	        },
   439	    }
   440
   441
   442	def test_three_runtime_success_paths_preserve_worker_attempt_provenance(
   443	    monkeypatch: pytest.MonkeyPatch,
   444	) -> None:
   445	    monkeypatch.setattr(runtime, "_hermes_credential_for", lambda route, model: "key")
   446	    attempt = _canonical_success_attempt()
   447
   448	    def fake_worker(*args, response_contract, **kwargs):  # noqa: ANN001, ANN202, ARG001
   449	        base = {"model_attempts": [attempt], "deepseek_usage": attempt["token_usage"]}
   450	        if response_contract == "python":
   451	            return {**base, "python": "pass", "message": "ok"}
   452	        if response_contract == "delta":
   453	            return {**base, "delta": [], "message": "ok"}
   454	        return {**base, "content": "done\n```batch\ndone()\n```"}
   455
   456	    monkeypatch.setattr(runtime, "_run_worker", fake_worker)
   457
   458	    python_result = runtime.run_agent_turn(
   459	        task="x", python_source="", route="openrouter", model="requested/model"
   460	    )
   461	    delta_result = runtime.run_agent_turn_delta(
   462	        task="x", projection="{}", op_schema={}, route="openrouter", model="requested/model"
   463	    )
   464	    batch_result = runtime.run_agent_turn_batch(
   465	        task="x", route="openrouter", model="requested/model", messages=[]
   466	    )
   467
   468	    for result in (python_result, delta_result, batch_result):
   469	        assert result["model_attempts"] == [attempt]
   470	        assert result["deepseek_usage"] == attempt["token_usage"]
   471
   472
   473	def test_batch_provider_audit_merges_worker_attempt_provenance() -> None:
   474	    attempt = _canonical_success_attempt()
   475	    result = agent_provider._normalize_batch_response(
   476	        {
   477	            "content": "Changed it.\n```batch\ndone()\n```",
   478	            "model_attempts": [attempt],
   479	            "deepseek_usage": attempt["token_usage"],
   480	        },
   481	        route="openrouter",
   482	        model="requested/model",
   483	        audit_metadata={"provider": "arnold"},
   484	    )
   485
   486	    assert result.audit_metadata["model_attempts"] == [attempt]
   487	    assert result.audit_metadata["deepseek_usage"] == attempt["token_usage"]
   488
   489
   490	def test_successful_classify_and_reply_attempts_reach_executor_capture(
   491	    monkeypatch: pytest.MonkeyPatch,
   492	) -> None:
   493	    calls = 0
   494
   495	    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
   496	        nonlocal calls
   497	        calls += 1
   498	        phase = "classify" if calls == 1 else "reply"
   499	        content = (
   500	            '{"research":false,"implement":false,"reply":true,"route":"respond"}'
   501	            if phase == "classify"
   502	            else '{"reply":"hello"}'
   503	        )
   504	        attempt = {**_canonical_success_attempt(), "phase": phase}
   505	        return {"content": content, "json": json.loads(content), "model_attempts": [attempt]}
   506
   507	    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)
   508	    token = runtime.begin_model_attempt_capture()
   509	    try:
   510	        decision = run_classify_turn("hello", route="openrouter", model="requested/model")
   511	        assert run_reply_turn(
   512	            "hello",
   513	            route="openrouter",
   514	            model="requested/model",
   515	            plan=decision,
   516	        ) == "hello"
   517	        attempts = runtime.snapshot_model_attempt_capture()
   518	    finally:
   519	        runtime.end_model_attempt_capture(token)
   520
   521	    assert [item["phase"] for item in attempts] == ["classify", "reply"]
   522	    assert all(item["outcome"] == "success" for item in attempts)
     1	"""Tests for the typed-empty-only retry wrapper around ``_run_worker``.
     2
     3	Only a canonical ``empty_response`` attempt with observed zero completion
     4	tokens may receive a fresh subprocess/transport. Timeouts, provider failures,
     5	and malformed non-empty content surface without retry.
     6
     7	These tests drive the wrapper directly by stubbing ``_run_worker_once`` (the
     8	single-shot subprocess call), so no real subprocess or network is involved.
     9	"""
    10	from __future__ import annotations
    11
    12	import pytest
    13
    14	from vibecomfy.comfy_nodes.agent import runtime
    15
    16
    17	def _stub_once(monkeypatch: pytest.MonkeyPatch, behaviors: list) -> list:
    18	    """Replace ``_run_worker_once`` with a recorder that replays ``behaviors``.
    19
    20	    Each behavior is either an ``Exception`` instance/class to raise, or a dict
    21	    to return. Returns the list of (args, kwargs) it was called with.
    22	    """
    23	    calls: list = []
    24	    queue = list(behaviors)
    25
    26	    def fake_once(*args, **kwargs):
    27	        calls.append((args, kwargs))
    28	        behavior = queue.pop(0)
    29	        if isinstance(behavior, BaseException) or (
    30	            isinstance(behavior, type) and issubclass(behavior, BaseException)
    31	        ):
    32	            raise behavior
    33	        return behavior
    34
    35	    monkeypatch.setattr(runtime, "_run_worker_once", fake_once)
    36	    # Don't actually sleep between retries.
    37	    monkeypatch.setattr(runtime.time, "sleep", lambda _s: None)
    38	    return calls
    39
    40
    41	def _common_kwargs():
    42	    return {
    43	        "response_contract": "batch_repl",
    44	        "agent_id": "hermes",
    45	        "model": "openrouter:deepseek/deepseek-v4-pro",
    46	        "effort": "low",
    47	        "profiling_context": {"model_turn_id": "test-turn"},
    48	    }
    49
    50
    51	def _attempt(
    52	    *, outcome: str, failure_type: str | None = None, completion_tokens: int = 1
    53	) -> dict:
    54	    return {
    55	        "phase": "batch",
    56	        "attempt": 1,
    57	        "outcome": outcome,
    58	        "failure_type": failure_type,
    59	        "requested_model": "requested-model",
    60	        "resolved_model": "resolved-model",
    61	        "adapter": "hermes",
    62	        "provider": "openrouter",
    63	        "transport": "openrouter",
    64	        "endpoint": "https://openrouter.ai/api/v1",
    65	        "finish_reason": "stop" if outcome == "success" else "unknown",
    66	        "token_usage": {
    67	            "prompt_tokens": 10,
    68	            "completion_tokens": completion_tokens,
    69	            "total_tokens": 10 + completion_tokens,
    70	        },
    71	    }
    72
    73
    74	def test_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    75	    good = {"content": "ok", "_profiling": {}}
    76	    calls = _stub_once(monkeypatch, [TimeoutError("Agent worker timed out after 180.0 seconds."), good])
    77
    78	    with pytest.raises(TimeoutError) as raised:
    79	        runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
    80
    81	    assert len(calls) == 1
    82	    assert raised.value.model_attempts[0]["failure_type"] == "timeout"  # type: ignore[attr-defined]
    83
    84
    85	def test_timeout_surfaces_after_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    86	    calls = _stub_once(monkeypatch, [TimeoutError, TimeoutError, TimeoutError])
    87
    88	    with pytest.raises(TimeoutError):
    89	        runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
    90
    91	    assert len(calls) == 1
    92
    93
    94	def test_untyped_transport_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    95	    transient = {"error": "connection reset", "error_type": "ConnectionError"}
    96	    good = {"content": "ok", "_profiling": {}}
    97	    calls = _stub_once(monkeypatch, [transient, good])
    98
    99	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   100
   101	    assert result == transient
   102	    assert len(calls) == 1
   103
   104
   105	def test_typed_provider_failure_is_not_retried(
   106	    monkeypatch: pytest.MonkeyPatch,
   107	) -> None:
   108	    transient = {
   109	        "error": "503",
   110	        "error_type": "APIStatusError",
   111	        "model_attempts": [_attempt(outcome="failure", failure_type="provider_failure")],
   112	    }
   113	    calls = _stub_once(monkeypatch, [transient, transient, transient])
   114
   115	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   116
   117	    assert result == transient
   118	    assert len(calls) == 1
   119
   120
   121	def test_typed_empty_zero_token_response_retries_on_fresh_transport(
   122	    monkeypatch: pytest.MonkeyPatch,
   123	) -> None:
   124	    empty = {
   125	        "error": "empty",
   126	        "error_type": "ValueError",
   127	        "model_attempts": [
   128	            _attempt(
   129	                outcome="failure",
   130	                failure_type="empty_response",
   131	                completion_tokens=0,
   132	            )
   133	        ],
   134	    }
   135	    good = {
   136	        "content": "ok",
   137	        "model_attempts": [_attempt(outcome="success")],
   138	    }
   139	    calls = _stub_once(monkeypatch, [empty, good])
   140
   141	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   142
   143	    assert len(calls) == 2
   144	    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]
   145	    assert result["model_attempts"][0]["failure_type"] == "empty_response"
   146	    assert "raw_response_preview" not in result["model_attempts"][1]
   147
   148
   149	def test_typed_empty_with_nonzero_tokens_is_not_retried(
   150	    monkeypatch: pytest.MonkeyPatch,
   151	) -> None:
   152	    inconsistent = {
   153	        "error": "empty",
   154	        "error_type": "ValueError",
   155	        "model_attempts": [
   156	            _attempt(outcome="failure", failure_type="empty_response", completion_tokens=2)
   157	        ],
   158	    }
   159	    calls = _stub_once(monkeypatch, [inconsistent])
   160
   161	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   162
   163	    assert result["model_attempts"][0]["failure_type"] == "empty_response"
   164	    assert len(calls) == 1
   165
   166
   167	@pytest.mark.parametrize(
   168	    "error_type",
   169	    ["ValueError", "JSONDecodeError", "AuthError", "AuthenticationError", "PermissionError"],
   170	)
   171	def test_non_transient_worker_error_is_not_retried(
   172	    monkeypatch: pytest.MonkeyPatch, error_type: str
   173	) -> None:
   174	    """Content/auth errors are owned by other layers and must not burn retry slots."""
   175	    non_transient = {"error": "boom", "error_type": error_type}
   176	    calls = _stub_once(monkeypatch, [non_transient])
   177
   178	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   179
   180	    assert result == non_transient
   181	    assert len(calls) == 1
   182
   183
   184	def test_runtime_unavailable_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
   185	    """Setup faults (missing backend / unregistered adapter) won't recover."""
   186	    unavailable = {
   187	        "error": "no adapter",
   188	        "error_type": "LookupError",
   189	        "runtime_unavailable": True,
   190	    }
   191	    calls = _stub_once(monkeypatch, [unavailable])
   192
   193	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   194
   195	    assert result == unavailable
   196	    assert len(calls) == 1
   197
   198
   199	def test_success_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
   200	    good = {"content": "ok", "_profiling": {}}
   201	    calls = _stub_once(monkeypatch, [good])
   202
   203	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   204
   205	    assert result == good
   206	    assert len(calls) == 1
   240	        "messages.jsonl": True,
   241	        "model_attempts.json": False,
   242	        "model_request.json": True,
   243	        "model_response.json": True,
   244	    }
   245	    assert (output_dir / "messages.jsonl").read_text(encoding="utf-8") == '{"role": "user"}\n'
   246	    assert (output_dir / "model_request.json").is_file()
   247	    assert (output_dir / "model_response.json").is_file()
   248
   249
   250	def test_model_attempt_artifact_is_canonical_and_redacts_secrets(tmp_path: Path) -> None:
   251	    output_dir = tmp_path / "out"
   252	    result = ExecutorResult.success(
   253	        report=Report(
   254	            model_attempts=(
   255	                {
   256	                    "phase": "classify",
   257	                    "attempt": 1,
   258	                    "outcome": "failure",
   259	                    "failure_type": "malformed_json",
   260	                    "requested_model": "requested-model",
   261	                    "resolved_model": "resolved-model",
   262	                    "adapter": "hermes",
   263	                    "provider": "openrouter",
   264	                    "transport": "openrouter",
   265	                    "endpoint": (
   266	                        "https://user:password@OpenRouter.ai/api/v1/?api_key=sk-secret"
   267	                        "&signature=sig-secret"
   268	                    ),
   269	                    "finish_reason": "stop",
   270	                    "token_usage": {
   271	                        "prompt_tokens": 11,
   272	                        "completion_tokens": 4,
   273	                        "total_tokens": 15,
   274	                    },
   275	                    "raw_response_preview": (
   276	                        "Authorization: Bearer top-secret "
   277	                        "https://example.test/v1?token=url-secret"
   278	                    ),
   279	                },
   280	                {
   281	                    "phase": "reply",
   282	                    "attempt": 1,
   283	                    "outcome": "success",
   284	                    "requested_model": "requested-model",
   285	                    "resolved_model": "resolved-model",
   286	                    "adapter": "codex",
   287	                    "provider": "unknown",
   288	                    "transport": "unknown",
   289	                    "endpoint": "unknown",
   290	                    "finish_reason": "unknown",
   291	                    "token_usage": {},
   292	                    "raw_response_preview": "must never persist on success",
   293	                },
   294	            )
   295	        ),
   296	        reply="ok",
   297	    )
   298
   299	    manifest = synthesize_headless_artifacts(
   300	        request={"query": "test"},
   301	        result=result,
   302	        response={"ok": True},
   303	        output_dir=output_dir,
   304	        status="success",
   305	    )
   306
   307	    assert "model_attempts.json" in manifest["manifest"]
   308	    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
   309	    assert attempts[0]["endpoint"] == "https://openrouter.ai/api/v1"
   310	    assert "top-secret" not in attempts[0]["raw_response_preview"]
   311	    assert "url-secret" not in attempts[0]["raw_response_preview"]
   312	    assert "raw_response_preview" not in attempts[1]
   313	    assert attempts[1]["provider"] == "unknown"
   314	    persisted = "\n".join(
   315	        path.read_text(encoding="utf-8")
   316	        for path in output_dir.iterdir()
   317	        if path.is_file()
   318	    )
   319	    assert "sk-secret" not in persisted
   320	    assert "sig-secret" not in persisted
   321	    assert "top-secret" not in persisted
   322	    assert "url-secret" not in persisted
     1	from __future__ import annotations
     2
     3	import json
     4	import subprocess
     5	from pathlib import Path
     6
     7	from tests.live_agentic_harness.runner import (
     8	    _persist_run_summary,
     9	    _persist_scenario_summary,
    10	    run_tag,
    11	)
    12
    13
    14	def _summary(tmp_path: Path, scenario_id: str, *, ok: bool) -> dict:
    15	    output_dir = tmp_path / "tag" / scenario_id
    16	    return {
    17	        "scenario_id": scenario_id,
    18	        "status": "success" if ok else "error",
    19	        "output_dir": str(output_dir),
    20	        "guard": {"live_agentic_success": ok},
    21	        "deepseek_usage": {},
    22	        "deepseek_est_cost_usd": 0.0,
    23	        "deepseek_cost_basis": "not_available",
    24	        "model_attempts": [],
    25	    }
    26
    27
    28	def _failed_attempt(failure_type: str, *, completion_tokens: int = 0) -> dict:
    29	    return {
    30	        "phase": "classify",
    31	        "attempt": 1,
    32	        "outcome": "failure",
    33	        "failure_type": failure_type,
    34	        "requested_model": "requested",
    35	        "resolved_model": "resolved",
    36	        "adapter": "hermes",
    37	        "provider": "openrouter",
    38	        "transport": "openrouter",
    39	        "endpoint": "https://openrouter.ai/api/v1",
    40	        "finish_reason": "unknown",
    41	        "token_usage": {
    42	            "prompt_tokens": 10,
    43	            "completion_tokens": completion_tokens,
    44	            "total_tokens": 10 + completion_tokens,
    45	        },
    46	    }
    47
    48
    49	def test_persists_per_scenario_and_incremental_run_summary(tmp_path: Path) -> None:
    50	    passing = _summary(tmp_path, "passing", ok=True)
    51	    failing = _summary(tmp_path, "failing", ok=False)
    52
    53	    _persist_scenario_summary(passing, tmp_path, "tag")
    54	    _persist_scenario_summary(failing, tmp_path, "tag")
    55	    partial = _persist_run_summary(
    56	        "tag",
    57	        [passing, failing, None],
    58	        tmp_path,
    59	        total_scenarios=3,
    60	        complete=False,
    61	    )
    62
    63	    assert partial["passed"] == 1
    64	    assert partial["failed"] == 1
    65	    assert partial["pending"] == 1
    66	    assert partial["complete"] is False
    67	    assert (tmp_path / "tag" / "passing" / "agentic_summary.json").exists()
    68	    assert (tmp_path / "tag" / "failing" / "agentic_summary.json").exists()
    69	    assert (tmp_path / "tag" / "run_summary.partial.json").exists()
    70
    71	    persisted = json.loads((tmp_path / "tag" / "run_summary.partial.json").read_text())
    72	    assert persisted["passed"] == 1
    73	    assert persisted["failed"] == 1
    74
    75
    76	def test_final_summary_replaces_partial_summary(tmp_path: Path) -> None:
    77	    passing = _summary(tmp_path, "passing", ok=True)
    78
    79	    _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=False)
    80	    final = _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=True)
    81
    82	    assert final["complete"] is True
    83	    assert final["overall_success"] is True
    84	    assert (tmp_path / "tag" / "run_summary.json").exists()
    85	    assert not (tmp_path / "tag" / "run_summary.partial.json").exists()
    86
    87
    88	def test_runner_does_not_retry_outer_timeout(
    89	    tmp_path: Path,
    90	    monkeypatch,
    91	) -> None:  # noqa: ANN001
    92	    scenarios_dir = tmp_path / "scenarios"
    93	    scenarios_dir.mkdir()
    94	    scenario_path = scenarios_dir / "retry-me.json"
    95	    scenario_path.write_text(json.dumps({"id": "retry-me", "query": "do it"}), encoding="utf-8")
    96
    97	    calls = 0
    98
    99	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
   100	        nonlocal calls
   101	        calls += 1
   102	        if calls == 1:
   103	            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))
   104	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   105	        tag = cmd[cmd.index("--tag") + 1]
   106	        output_dir = tmp_path / "out" / tag / "retry-me"
   107	        payload = _summary(tmp_path / "out" / tag, "retry-me", ok=True)
   108	        payload["output_dir"] = str(output_dir)
   109	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   110	        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
   111
   112	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   113
   114	    summary = run_tag(
   115	        "tag",
   116	        scenarios_dir=scenarios_dir,
   117	        output_base=tmp_path / "out",
   118	        max_workers=1,
   119	        per_scenario_timeout=1,
   120	        infra_retries=1,
   121	        progress_every=0,
   122	    )
   123
   124	    scenario = summary["scenarios"][0]
   125	    assert calls == 1
   126	    assert summary["passed"] == 0
   127	    assert summary["raw_first_attempt_passed"] == 0
   128	    assert scenario["attempt_count"] == 1
   129	    assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
   130	    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
   131	    assert scenario["attempts"][0]["agent_exercised"] is False
   132	    assert scenario["attempts"][0]["elapsed_s"] is not None
   133	    assert (
   134	        tmp_path / "out" / "tag" / "retry-me" / "agentic_summary.json"
   135	    ).exists()
   136
   137
   138	def test_runner_types_provider_capacity_without_retry(
   139	    tmp_path: Path,
   140	    monkeypatch,
   141	) -> None:  # noqa: ANN001
   142	    scenarios_dir = tmp_path / "scenarios"
   143	    scenarios_dir.mkdir()
   144	    scenario_path = scenarios_dir / "provider-capacity.json"
   145	    scenario_path.write_text(
   146	        json.dumps({"id": "provider-capacity", "query": "do it"}),
   147	        encoding="utf-8",
   148	    )
   149
   150	    calls = 0
   151
   152	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   153	        nonlocal calls
   154	        calls += 1
   155	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   156	        tag = cmd[cmd.index("--tag") + 1]
   157	        output_dir = tmp_path / "out" / tag / "provider-capacity"
   158	        if calls == 1:
   159	            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
   160	            payload.update(
   161	                {
   162	                    "status": "executor_failure",
   163	                    "error": (
   164	                        "OpenRouter rejected the request because the account does "
   165	                        "not have enough credits for the requested token budget."
   166	                    ),
   167	                    "output_dir": str(output_dir),
   168	                    "model_attempts": [_failed_attempt("provider_failure")],
   169	                    "guard": {
   170	                        "live_agentic_success": False,
   171	                        "score_class": "product_fail",
   172	                        "assessment": {
   173	                            "passed": False,
   174	                            "issues": [
   175	                                {
   176	                                    "check": "response_ok",
   177	                                    "severity": "error",
   178	                                    "detail": (
   179	                                        "response.ok is False: OpenRouter rejected "
   180	                                        "the request because the account does not "
   181	                                        "have enough credits for the requested token budget."
   182	                                    ),
   183	                                }
   184	                            ],
   185	                        },
   186	                    },
   187	                }
   188	            )
   189	        else:
   190	            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
   191	            payload["output_dir"] = str(output_dir)
   192	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   193	        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
   194
   195	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   196
   197	    summary = run_tag(
   198	        "tag",
   199	        scenarios_dir=scenarios_dir,
   200	        output_base=tmp_path / "out",
   201	        max_workers=1,
   202	        per_scenario_timeout=1,
   203	        infra_retries=1,
   204	        progress_every=0,
   205	    )
   206
   207	    scenario = summary["scenarios"][0]
   208	    assert calls == 1
   209	    assert summary["passed"] == 0
   210	    assert summary["raw_first_attempt_passed"] == 0
   211	    assert scenario["attempt_count"] == 1
   212	    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
   213	    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
   214	    assert scenario["attempts"][0]["retryable_infra"] is False
   215
   216
   217	def test_runner_retries_only_typed_empty_zero_token_attempt(
   218	    tmp_path: Path,
   219	    monkeypatch,
   220	) -> None:  # noqa: ANN001
   221	    scenarios_dir = tmp_path / "scenarios"
   222	    scenarios_dir.mkdir()
   223	    scenario_path = scenarios_dir / "typed-empty.json"
   224	    scenario_path.write_text(json.dumps({"id": "typed-empty", "query": "do it"}), encoding="utf-8")
   225	    calls = 0
   226
   227	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   228	        nonlocal calls
   229	        calls += 1
   230	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   231	        tag = cmd[cmd.index("--tag") + 1]
   232	        payload = _summary(tmp_path / "out" / tag, "typed-empty", ok=calls > 1)
   233	        payload["output_dir"] = str(tmp_path / "out" / tag / "typed-empty")
   234	        if calls == 1:
   235	            payload["error"] = "arbitrary wording that must not drive classification"
   236	            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
   237	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   238	        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
   239
   240	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   241
   242	    summary = run_tag(
   243	        "tag",
   244	        scenarios_dir=scenarios_dir,
   245	        output_base=tmp_path / "out",
   246	        max_workers=1,
   247	        infra_retries=1,
   248	        progress_every=0,
   249	    )
   250
   251	    scenario = summary["scenarios"][0]
   252	    assert calls == 2
   253	    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
   254	    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
   255	    assert scenario["attempts"][1]["live_agentic_success"] is True
   256
   257
   258	def test_runner_keeps_malformed_nonempty_as_product_failure(
   259	    tmp_path: Path,
   260	    monkeypatch,
   261	) -> None:  # noqa: ANN001
   262	    scenarios_dir = tmp_path / "scenarios"
   263	    scenarios_dir.mkdir()
   264	    scenario_path = scenarios_dir / "malformed.json"
   265	    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
   266	    calls = 0
   267
   268	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   269	        nonlocal calls
   270	        calls += 1
   271	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   272	        tag = cmd[cmd.index("--tag") + 1]
   273	        payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
   274	        payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
   275	        payload["error"] = "OpenRouter rejected / HTTP 429 wording is irrelevant"
   276	        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
   277	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   278	        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
   279
   280	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   281
   282	    summary = run_tag(
   283	        "tag",
   284	        scenarios_dir=scenarios_dir,
   285	        output_base=tmp_path / "out",
   286	        max_workers=1,
   287	        infra_retries=1,
   288	        progress_every=0,
   289	    )
   290
   291	    scenario = summary["scenarios"][0]
   292	    assert calls == 1
   293	    assert scenario["score_class"] == "product_fail"
   294	    assert scenario.get("retryable_infra") is not True
   295
   296
   297	def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
   298	    tmp_path: Path,
   299	    monkeypatch,
   300	) -> None:  # noqa: ANN001
   301	    scenarios_dir = tmp_path / "scenarios"
   302	    scenarios_dir.mkdir()
   303	    scenario_path = scenarios_dir / "provider-down.json"
   304	    scenario_path.write_text(json.dumps({"id": "provider-down", "query": "do it"}), encoding="utf-8")
   305
   306	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   307	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   308	        tag = cmd[cmd.index("--tag") + 1]
   309	        output_dir = tmp_path / "out" / tag / "provider-down"
   310	        payload = _summary(tmp_path / "out" / tag, "provider-down", ok=False)
   311	        payload.update(
   312	            {
   313	                "status": "executor_failure",
   314	                "error": "HTTP Error 429: Too Many Requests",
   315	                "output_dir": str(output_dir),
   316	                "model_attempts": [_failed_attempt("provider_failure")],
   317	                "guard": {
   318	                    "live_agentic_success": False,
   319	                    "score_class": "product_fail",
   320	                    "assessment": {"passed": False, "issues": []},
   321	                },
   322	            }
   323	        )
   324	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   325	        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
   326
   327	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   328
   329	    summary = run_tag(
   330	        "tag",
   331	        scenarios_dir=scenarios_dir,
   332	        output_base=tmp_path / "out",
   333	        max_workers=1,
   334	        per_scenario_timeout=1,
   335	        infra_retries=1,
   336	        progress_every=0,
   337	    )
   338
   339	    scenario = summary["scenarios"][0]
   340	    assert scenario["attempt_count"] == 1
   341	    assert scenario["failure_class"] == "infra_provider_capacity"
   342	    assert scenario["score_class"] == "infra_blocked"
   343	    assert summary["passed"] == 0
   344	    assert summary["infra_failures"] == 1
   345	    assert summary["product_or_assessment_failures"] == 0
   346	    assert summary["score_classes"] == {"infra_blocked": 1}
   347
   348
   349	def test_runner_does_not_classify_soft_search_429_as_infra(
   350	    tmp_path: Path,
   351	    monkeypatch,
   352	) -> None:  # noqa: ANN001
   353	    scenarios_dir = tmp_path / "scenarios"
   354	    scenarios_dir.mkdir()
   355	    scenario_path = scenarios_dir / "soft-search-warning.json"
   356	    scenario_path.write_text(
   357	        json.dumps({"id": "soft-search-warning", "query": "do it"}),
   358	        encoding="utf-8",
   359	    )
   360

exec
/bin/zsh -lc 'rg -n "agent_failure_context|model_response" vibecomfy/executor/core.py vibecomfy/executor/contracts.py vibecomfy/agent/artifacts.py tests | head -200' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 81ms:
vibecomfy/agent/artifacts.py:34:    "model_response.json",
vibecomfy/executor/core.py:107:# Mirrors the batch-repl model_response.json detail (parse_reason + raw
vibecomfy/executor/core.py:158:def _model_response_evidence_from_exception(exc: BaseException) -> dict[str, Any]:
vibecomfy/executor/core.py:208:    """Merge parse evidence into a failure envelope's agent_failure_context.
vibecomfy/executor/core.py:212:    evidence = _model_response_evidence_from_exception(exc)
vibecomfy/executor/core.py:218:    context = dict(failure.agent_failure_context or {})
vibecomfy/executor/core.py:220:    return replace(failure, agent_failure_context=context)
vibecomfy/executor/core.py:223:def _model_response_artifact(failure: Any) -> dict[str, Any] | None:
vibecomfy/executor/core.py:224:    """Shape parse evidence into a batch-repl-style ``model_response`` artifact."""
vibecomfy/executor/core.py:225:    context = getattr(failure, "agent_failure_context", None)
vibecomfy/executor/core.py:1096:            model_response=_model_response_artifact(failure),
vibecomfy/executor/core.py:1108:            model_response=_model_response_artifact(failure),
vibecomfy/executor/core.py:1508:            agent_failure_context={
vibecomfy/executor/core.py:1523:        failure_context = result.get("agent_failure_context")
vibecomfy/executor/core.py:1534:            failure_payload["agent_failure_context"] = failure_context
vibecomfy/executor/core.py:1542:            agent_failure_context={
vibecomfy/executor/core.py:1804:            agent_failure_context={
vibecomfy/executor/core.py:1825:            model_response=_model_response_artifact(failure),
vibecomfy/executor/core.py:1837:            model_response=_model_response_artifact(failure),
vibecomfy/executor/core.py:1859:        model_response: dict[str, Any] | None = None,
vibecomfy/executor/core.py:1866:        self.model_response = model_response
vibecomfy/executor/core.py:1987:        model_response: dict[str, Any] | None = None,
vibecomfy/executor/core.py:1991:        if not model_attempts and isinstance(model_response, Mapping):
vibecomfy/executor/core.py:1992:            raw_attempts = model_response.get("attempts")
vibecomfy/executor/core.py:2010:            model_response=model_response,
vibecomfy/executor/core.py:2131:            model_response=exc.model_response,
vibecomfy/executor/core.py:2301:                context_payload = getattr(envelope, "agent_failure_context", None)
vibecomfy/executor/core.py:2303:                    failure_payload["agent_failure_context"] = context_payload
vibecomfy/executor/core.py:2436:                model_response=exc.model_response,
vibecomfy/executor/core.py:2452:            model_response=exc.model_response,
vibecomfy/executor/contracts.py:2305:    # Mirrors the batch-repl model_response.json attempt artifact: parse-failure
vibecomfy/executor/contracts.py:2309:    model_response: dict[str, Any] | None = None
vibecomfy/executor/contracts.py:2325:        if self.model_response is not None:
vibecomfy/executor/contracts.py:2328:                "model_response",
vibecomfy/executor/contracts.py:2329:                _freeze_jsonish(self.model_response),
vibecomfy/executor/contracts.py:2357:        if self.model_response is not None:
vibecomfy/executor/contracts.py:2358:            inner["model_response"] = _thaw_jsonish(self.model_response)
tests/test_comfy_roundtrip_route.py:210:        agent_failure_context={
tests/test_comfy_roundtrip_route.py:226:    assert payload["agent_failure_context"]["issues"] == [
tests/test_agent_edit_artifact_replay.py:57:def _load_model_response(key: str) -> dict[str, Any]:
tests/test_agent_edit_artifact_replay.py:58:    return _load_fixture_json(key, "model_response.json")
tests/test_agent_edit_artifact_replay.py:177:    def test_model_response_encodes_add_node_with_alias_class(self) -> None:
tests/test_agent_edit_artifact_replay.py:178:        response = _load_model_response(ALIAS_FIXTURE_KEY)
tests/test_agent_edit_artifact_replay.py:235:        response = _load_model_response(ALIAS_FIXTURE_KEY)
tests/test_agent_edit_artifact_replay.py:268:    def test_model_response_add_node_has_uid_and_node_id(self) -> None:
tests/test_agent_edit_artifact_replay.py:269:        response = _load_model_response(CANONICAL_UID_FIXTURE_KEY)
tests/test_agent_edit_artifact_replay.py:634:    def test_model_response_statements_encode_canonical_set_field(self) -> None:
tests/test_agent_edit_artifact_replay.py:635:        """The parity fixture's model_response encodes set_node_field with
tests/test_agent_edit_artifact_replay.py:637:        response = _load_model_response(PARITY_FIXTURE_KEY)
tests/test_agent_edit_artifact_replay.py:644:    def test_model_response_statements_encode_canonical_set_mode(self) -> None:
tests/test_agent_edit_artifact_replay.py:645:        """The parity fixture's model_response encodes set_mode with
tests/test_agent_edit_artifact_replay.py:647:        response = _load_model_response(PARITY_FIXTURE_KEY)
tests/test_headless_agent_artifacts.py:208:        "model_response.json": False,
tests/test_headless_agent_artifacts.py:212:    assert not (output_dir / "model_response.json").exists()
tests/test_headless_agent_artifacts.py:222:    (turn_dir / "model_response.json").write_text('{"turns": []}\n', encoding="utf-8")
tests/test_headless_agent_artifacts.py:243:        "model_response.json": True,
tests/test_headless_agent_artifacts.py:247:    assert (output_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_contracts.py:290:    assert raw_detail not in product_payload["outcome"].get("agent_failure_context", {})
tests/test_comfy_nodes_agent_contracts.py:291:    assert raw_detail not in product_payload["agent_failure_context"].get("explanation", "")
tests/test_comfy_nodes_agent_contracts.py:292:    assert payload["agent_failure_context"]["explanation"] == raw_detail
tests/test_comfy_nodes_agent_contracts.py:294:        product_payload["debug"]["failure"]["agent_failure_context"]["explanation"]
tests/test_comfy_nodes_agent_contracts.py:298:        "$.debug.failure.agent_failure_context.explanation"
tests/test_comfy_nodes_agent_contracts.py:551:    assert failure.agent_failure_context["scan_code"] == "source_type"
tests/test_comfy_nodes_agent_contracts.py:560:        agent_failure_context={"explanation": "missing python"},
tests/test_comfy_nodes_agent_contracts.py:576:    assert payload["agent_failure_context"] == {"explanation": "missing python"}
tests/test_comfy_nodes_agent_contracts.py:581:        failure.agent_failure_context["other"] = "nope"  # type: ignore[index]
tests/test_comfy_nodes_agent_contracts.py:638:        agent_failure_context={"explanation": "provider timed out"},
tests/test_comfy_nodes_agent_contracts.py:718:        agent_failure_context={
tests/test_comfy_nodes_agent_contracts.py:735:        "agent_failure_context": {
tests/test_comfy_nodes_agent_contracts.py:752:        agent_failure_context={"explanation": "missing python"},
tests/test_comfy_nodes_agent_contracts.py:771:        agent_failure_context={"explanation": "missing python"},
tests/test_comfy_nodes_agent_contracts.py:781:        "agent_failure_context": {"explanation": "missing python"},
tests/test_comfy_nodes_agent_contracts.py:794:        agent_failure_context={
tests/test_comfy_nodes_agent_contracts.py:810:    assert payload["agent_failure_context"] == {
tests/test_comfy_nodes_agent_contracts.py:839:            "agent_failure_context": {
tests/test_comfy_nodes_agent_contracts.py:855:    assert payload["agent_failure_context"]["issues"][0]["rebaseline_recovery"] == recovery
tests/test_comfy_nodes_agent_contracts.py:893:        model_response_path=tmp_path / "session" / "turns" / "0001" / "model_response.json",
tests/test_comfy_nodes_agent_contracts.py:933:            "agent_failure_context": {"reason": "stale_state_recovery"},
tests/test_comfy_nodes_agent_contracts.py:960:    assert payload["agent_failure_context"]["issues"][0]["rebaseline_recovery"] == recovery
tests/test_comfy_nodes_agent_contracts.py:963:        set(payload["agent_failure_context"]["issues"][0]["rebaseline_recovery"])
tests/test_comfy_nodes_agent_contracts.py:1028:            agent_failure_context={"explanation": "provider timed out"},
tests/test_comfy_nodes_agent_contracts.py:1512:        "message", "user_facing_message", "agent_failure_context",
tests/test_comfy_nodes_agent_contracts.py:1594:    assert fe.agent_failure_context["http_status"] == 401
tests/test_comfy_nodes_agent_contracts.py:1610:    assert fe.agent_failure_context["http_status"] == 403
tests/test_comfy_nodes_agent_contracts.py:1618:    assert fe.agent_failure_context["http_status"] == 401
tests/test_comfy_nodes_agent_contracts.py:1626:    assert fe.agent_failure_context["http_status"] == 403
tests/test_comfy_nodes_agent_contracts.py:2000:            "agent_failure_context": {"explanation": "timed out"},
tests/test_comfy_nodes_agent_contracts.py:2014:        agent_failure_context={"explanation": "no graph"},
tests/test_comfy_nodes_agent_contracts.py:2146:        "agent_failure_context",
tests/test_comfy_nodes_agent_contracts.py:2162:            "agent_failure_context": {"explanation": "HTTP 401"},
tests/test_comfy_nodes_agent_contracts.py:2174:        "agent_failure_context": {"explanation": "HTTP 401"},
tests/test_edit_narrative.py:120:        "model_response_path": Path("/tmp/test_narrative_session/model_response.json"),
tests/test_edit_narrative.py:1020:    / "model_response.json"
tests/test_edit_narrative.py:1051:    The fixture ``tests/fixtures/editor_sessions/67785df94db647ca/model_response.json``
tests/test_comfy_nodes_agent_backend_spine.py:998:        stale.conflict.failure.agent_failure_context["reason"]
tests/test_comfy_nodes_agent_backend_spine.py:1122:        failure.agent_failure_context["reason"]
tests/test_comfy_nodes_agent_backend_spine.py:1167:    assert conflict.agent_failure_context["idempotency_key"] == "reb-replay"
tests/test_comfy_nodes_agent_backend_spine.py:1270:    assert failure.agent_failure_context["reason"] == "invalid-reason"
tests/test_comfy_nodes_agent_backend_spine.py:1271:    assert list(failure.agent_failure_context["allowed_reasons"]) == [
tests/test_comfy_nodes_agent_backend_spine.py:1359:    assert failure.agent_failure_context["reason"] == "baseline_cas_mismatch"
tests/test_comfy_nodes_agent_backend_spine.py:1424:    assert failure.agent_failure_context["reason"] == "baseline_cas_mismatch"
tests/test_comfy_nodes_agent_backend_spine.py:1425:    assert failure.agent_failure_context["expected_baseline_graph_hash"] == structural_graph_hash(
tests/test_comfy_nodes_agent_backend_spine.py:1560:    assert failure.agent_failure_context["legacy_migration"]["classification"] == "legacy_prepared_nonresumable"
tests/test_comfy_nodes_agent_backend_spine.py:2008:        agent_failure_context={"explanation": "broken", "provider_secret": "hide-me"},
tests/test_comfy_nodes_agent_backend_spine.py:2036:    assert first["failure"]["agent_failure_context"]["provider_secret"] == REDACTED
tests/test_comfy_nodes_agent_backend_spine.py:2050:        agent_failure_context={"api_key": "secret"},
tests/test_comfy_nodes_agent_backend_spine.py:2062:    assert audit["failure"]["agent_failure_context"]["api_key"] == REDACTED
tests/test_comfy_nodes_agent_backend_spine.py:2071:        agent_failure_context={"provider_secret": "secret"},
tests/test_comfy_nodes_agent_backend_spine.py:2079:    assert audit["failure"]["agent_failure_context"]["provider_secret"] == REDACTED
tests/test_comfy_nodes_agent_backend_spine.py:2523:        model_response_path=tmp_path / "session" / "turns" / "0001" / "model_response.json",
tests/test_comfy_nodes_agent_backend_spine.py:2544:        agent_failure_context={
tests/test_comfy_nodes_agent_backend_spine.py:2558:        response["agent_failure_context"]["issues"][0]["rebaseline_recovery"]
tests/test_comfy_nodes_agent_backend_spine.py:2583:        model_response_path=tmp_path / "session" / "turns" / "0001" / "model_response.json",
tests/test_comfy_nodes_agent_backend_spine.py:2607:        agent_failure_context={
tests/test_comfy_nodes_agent_backend_spine.py:5531:    migration = failure.agent_failure_context["legacy_migration"]
tests/test_comfy_nodes_agent_backend_spine.py:7809:    issues = failure.agent_failure_context.get("issues", [])
tests/test_comfy_nodes_agent_backend_spine.py:7811:        f"Expected evidence-loading issues, got: {failure.agent_failure_context}"
tests/test_comfy_nodes_agent_backend_spine.py:8082:    issues = failure.agent_failure_context.get("issues", [])
tests/test_comfy_nodes_agent_backend_spine.py:8440:    issues = failure.agent_failure_context.get("issues", [])
tests/test_comfy_nodes_agent_backend_spine.py:8442:        f"Expected scoped issue details in agent_failure_context.issues, "
tests/test_comfy_nodes_agent_backend_spine.py:8443:        f"got: {failure.agent_failure_context}"
tests/test_comfy_nodes_agent_backend_spine.py:8582:    explanation = failure.agent_failure_context.get("explanation", "")
tests/test_comfy_nodes_agent_backend_spine.py:8585:        f"got: {failure.agent_failure_context}"
tests/test_comfy_nodes_agent_backend_spine.py:8589:    issues = failure.agent_failure_context.get("issues", [])
tests/test_comfy_nodes_agent_backend_spine.py:8592:        f"got: {failure.agent_failure_context}"
tests/test_comfy_nodes_agent_backend_spine.py:8749:        failure.agent_failure_context["reason"]
tests/test_comfy_nodes_agent_backend_spine.py:8753:        failure.agent_failure_context["expected_baseline_graph_hash"]
tests/test_comfy_nodes_agent_backend_spine.py:8757:        failure.agent_failure_context["submitted_baseline_graph_hash"]
tests/test_comfy_nodes_agent_backend_spine.py:12623:        assert rejected.agent_failure_context["required_action"] == "rollback"
tests/test_agent_route_families.py:408:            agent_failure_context={"explanation": "Request body must be a JSON object."},
tests/test_execution_plan_runtime.py:45:        model_response_path=turn_dir / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:761:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:955:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1008:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1081:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1152:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1230:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1325:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1404:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1479:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1541:                agent_failure_context={"explanation": "runner blocked"},
tests/test_comfy_nodes_agent_edit.py:1573:    assert result["agent_failure_context"]["explanation"] == "runner blocked"
tests/test_comfy_nodes_agent_edit.py:1597:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1614:    assert state.model_response_path.is_file()
tests/test_comfy_nodes_agent_edit.py:1622:    response = json.loads(state.model_response_path.read_text(encoding="utf-8"))
tests/test_comfy_nodes_agent_edit.py:1788:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:2026:                agent_failure_context={"explanation": "dev runner blocked"},
tests/test_comfy_nodes_agent_edit.py:2116:    assert Path(result["artifacts"]["model_response"]).name == "model_response.json"
tests/test_comfy_nodes_agent_edit.py:2135:        "model_response",
tests/test_comfy_nodes_agent_edit.py:2219:    model_response = json.loads(Path(result["artifacts"]["model_response"]).read_text(encoding="utf-8"))
tests/test_comfy_nodes_agent_edit.py:2222:    assert model_response["delta_ops_envelope"] == result["delta_ops_envelope"]
tests/test_comfy_nodes_agent_edit.py:2223:    assert model_response["delta"] == result["delta_ops"]
tests/test_comfy_nodes_agent_edit.py:2224:    assert set(model_response["delta_ops_envelope"]) == {"schema_version", "ops"}
tests/test_comfy_nodes_agent_edit.py:2231:        "model_response",
tests/test_comfy_nodes_agent_edit.py:2305:    assert result["agent_failure_context"]["explanation"] == (
tests/test_comfy_nodes_agent_edit.py:2310:def test_agent_edit_batch_empty_model_response_is_malformed_not_provider_error(
tests/test_comfy_nodes_agent_edit.py:2351:    assert "batch_repl response was empty" in result["agent_failure_context"]["explanation"]
tests/test_comfy_nodes_agent_edit.py:2354:def test_agent_edit_batch_empty_model_response_retries_once_then_commits(
tests/test_comfy_nodes_agent_edit.py:2420:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:2466:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:2531:    response_turns = json.loads(state.model_response_path.read_text(encoding="utf-8"))[
tests/test_comfy_nodes_agent_edit.py:2579:    assert "Unsupported edit op 'bogus'." == result["agent_failure_context"]["explanation"]
tests/test_comfy_nodes_agent_edit.py:2931:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:4730:    assert "agent_failure_context" not in result
tests/test_comfy_nodes_agent_edit.py:4740:    model_response = json.loads(
tests/test_comfy_nodes_agent_edit.py:4741:        (tmp_path / "rejected-terminal-clarify" / "turns" / "0001" / "model_response.json").read_text(
tests/test_comfy_nodes_agent_edit.py:4745:    clarification = model_response["turns"][1]["clarification"]
tests/test_comfy_nodes_agent_edit.py:4748:    assert "rejected_clarification" not in model_response["turns"][1]
tests/test_comfy_nodes_agent_edit.py:4801:    assert "agent_failure_context" not in result
tests/test_comfy_nodes_agent_edit.py:4808:    model_response = json.loads((turn_dir / "model_response.json").read_text(encoding="utf-8"))
tests/test_comfy_nodes_agent_edit.py:4810:    assert len(model_response["turns"]) == 3
tests/test_comfy_nodes_agent_edit.py:4811:    assert model_response["turns"][0]["batch_result"]["landed_op_count"] == 0
tests/test_comfy_nodes_agent_edit.py:4812:    assert "clarification" in model_response["turns"][2]
tests/test_comfy_nodes_agent_edit.py:4813:    assert "rejected_clarification" not in model_response["turns"][2]
tests/test_comfy_nodes_agent_edit.py:6195:    issue = result["agent_failure_context"]["issues"][0]
tests/test_comfy_nodes_agent_edit.py:6201:    diagnostics = result["agent_failure_context"]["diagnostics"]
tests/test_comfy_nodes_agent_edit.py:6226:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:6441:        assert (turn_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_edit.py:6607:    assert (turn_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_edit.py:7254:    model_response = json.loads(
tests/test_comfy_nodes_agent_edit.py:7255:        (turn_dir / "model_response.json").read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:7257:    assert model_response["turns"][0]["batch_result"]["execution_plan_status"] == first_status
tests/test_comfy_nodes_agent_edit.py:7365:        (turn_dir / "model_response.json").read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:8203:    assert (turn_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_edit.py:8568:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:8631:    issue = result["agent_failure_context"]["issues"][0]
tests/test_comfy_nodes_agent_edit.py:8750:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:8925:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:9755:    assert result["agent_failure_context"]["explanation"] == explanation
tests/test_comfy_nodes_agent_edit.py:10310:    assert result["agent_failure_context"]["scan_code"] == "forbidden_import"
tests/test_comfy_nodes_agent_edit.py:10413:    assert conflict["agent_failure_context"]["idempotency_key"] == "same-key"
tests/test_comfy_nodes_agent_edit.py:10414:    assert conflict["debug"]["failure"]["agent_failure_context"] == conflict[
tests/test_comfy_nodes_agent_edit.py:10415:        "agent_failure_context"
tests/test_comfy_nodes_agent_edit.py:10422:        audit["failure"]["agent_failure_context"]["idempotency_key"]
tests/test_comfy_nodes_agent_edit.py:10527:    assert "agent_failure_context" not in rebaselined
tests/test_comfy_nodes_agent_edit.py:10601:        in accepted["agent_failure_context"]["explanation"]
tests/test_comfy_nodes_agent_edit.py:10604:        accepted["agent_failure_context"]["legacy_migration"]["classification"]
tests/test_comfy_nodes_agent_edit.py:10680:        in accepted["agent_failure_context"]["explanation"]
tests/test_comfy_nodes_agent_edit.py:10927:    assert unexpected["agent_failure_context"]["explanation"] == "boom"
tests/test_comfy_nodes_agent_edit.py:10941:        agent_failure_context={"explanation": "provider unavailable"},

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/core.py | sed -n '1040,1125p'; nl -ba vibecomfy/executor/core.py | sed -n '1780,1875p'; nl -ba vibecomfy/executor/core.py | sed -n '2090,2160p'; nl -ba vibecomfy/executor/core.py | sed -n '2400,2470p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 2ms:
  2400	            phase="reply",
  2401	            **_spec_fields(reply_spec),
  2402	        ) as span:
  2403	            reply_text = _run_reply(
  2404	                request,
  2405	                reply_spec,
  2406	                plan=plan,
  2407	                effective_graph=effective_graph,
  2408	                research_result=research_result,
  2409	                implementation_result=implementation_result,
  2410	                graph_inspection=_graph_inspection(effective_graph)
  2411	                if route_behavior.reply_uses_graph_inspection
  2412	                else None,
  2413	            )
  2414	            span.update(reply_preview=short_text(reply_text))
  2415	    except _ExecutorPhaseError as exc:
  2416	        # Preserve durable candidate when reply narration fails.
  2417	        # Narration failure is presentation-only (SD1): the durable
  2418	        # edit work (candidate, gates, proofs, receipts, eligibility)
  2419	        # must not be discarded when only the reply surface fails.
  2420	        if (
  2421	            implementation_result is not None
  2422	            and implementation_result.durable_response is not None
  2423	            and result_graph is not None
  2424	        ):
  2425	            LOGGER.warning(
  2426	                "Reply narration failed after durable edit succeeded "
  2427	                "(stage=%s, kind=%s); preserving implementation with "
  2428	                "deterministic fallback narration.",
  2429	                exc.stage,
  2430	                exc.failure_kind,
  2431	            )
  2432	            report = _build_report(
  2433	                plan=plan,
  2434	                research=research_result,
  2435	                implementation=implementation_result,
  2436	                model_response=exc.model_response,
  2437	            )
  2438	            fallback_reply = (
  2439	                implementation_result.message
  2440	                or "Edit completed. The candidate is ready to review."
  2441	            )
  2442	            return _finish(ExecutorResult.success(
  2443	                report=report,
  2444	                graph=result_graph,
  2445	                reply=fallback_reply,
  2446	            ))
  2447
  2448	        report = _build_report(
  2449	            plan=plan,
  2450	            research=research_result,
  2451	            implementation=implementation_result,
  2452	            model_response=exc.model_response,
  2453	        )
  2454	        return _finish(ExecutorResult.failure(
  2455	            kind=exc.failure_kind,
  2456	            stage=exc.stage,
  2457	            message=str(exc),
  2458	            report=report,
  2459	        ))
  2460
  2461	    # ── Guard: inspect must never return an edited graph ─────────────────
  2462	    if route_behavior.clears_result_graph:
  2463	        result_graph = None
  2464
  2465	    # ── Assemble success result ──────────────────────────────────────────
  2466	    report = _build_report(
  2467	        plan=plan,
  2468	        research=research_result,
  2469	        implementation=implementation_result,
  2470	    )

exec
/bin/zsh -lc 'git diff 16d80bbe..e33f0260 -- tests | rg -n "model_response|model_attempts|parse_reason|raw_response_preview"' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 26ms:
9:+        "model_attempts": result.response.get("model_attempts", []),
54:+        "model_attempts": summary.get("model_attempts", []),
79:+    attempts = summary.get("model_attempts")
223:+        base = {"model_attempts": [attempt], "deepseek_usage": attempt["token_usage"]}
243:+        assert result["model_attempts"] == [attempt]
252:+            "model_attempts": [attempt],
260:+    assert result.audit_metadata["model_attempts"] == [attempt]
279:+        return {"content": content, "json": json.loads(content), "model_attempts": [attempt]}
327:+            raw_response_preview="success content must be dropped",
341:+        assert "raw_response_preview" not in payload
355:+        "model_attempts.json": False,
357:         "model_response.json": False,
363:+        "model_attempts.json": False,
365:         "model_response.json": True,
369:     assert (output_dir / "model_response.json").is_file()
376:+            model_attempts=(
397:+                    "raw_response_preview": (
414:+                    "raw_response_preview": "must never persist on success",
429:+    assert "model_attempts.json" in manifest["manifest"]
430:+    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
432:+    assert "top-secret" not in attempts[0]["raw_response_preview"]
433:+    assert "url-secret" not in attempts[0]["raw_response_preview"]
434:+    assert "raw_response_preview" not in attempts[1]
453:+        "model_attempts": [],
516:+                    "model_attempts": [_failed_attempt("provider_failure")],
556:+            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
574:+    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
596:+        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
624:+                "model_attempts": [_failed_attempt("provider_failure")],
703:+    assert raised.value.model_attempts[0]["failure_type"] == "timeout"  # type: ignore[attr-defined]
741:+        "model_attempts": [_attempt(outcome="failure", failure_type="provider_failure")],
758:+        "model_attempts": [
768:+        "model_attempts": [_attempt(outcome="success")],
775:+    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]
776:+    assert result["model_attempts"][0]["failure_type"] == "empty_response"
777:+    assert "raw_response_preview" not in result["model_attempts"][1]
786:+        "model_attempts": [
794:+    assert result["model_attempts"][0]["failure_type"] == "empty_response"

codex
The implementation does define a single canonical dataclass, but I’m now checking whether the final executor envelope duplicates that evidence through the legacy `model_response` path—an important distinction between “one definition” and “one persisted format.” I’m also starting the requested 556-test focused suite with the socket plugin disabled.
exec
/bin/zsh -lc '.venv/bin/python -m pytest -q -p no:rerunfailures tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 1362ms:
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pytest/__main__.py", line 9, in <module>
    raise SystemExit(pytest.console_main())
                     ^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
           ^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1192, in pytest_cmdline_parse
    self.parse(args)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1562, in parse
    self.hook.pytest_load_initial_conftests(
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py", line 628, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py", line 127, in _sanitize_params
    dir = gettempdir()
          ^^^^^^^^^^^^
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py", line 316, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py", line 309, in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/contracts.py | sed -n '35,205p'; nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '85,235p'; nl -ba vibecomfy/executor/contracts.py | sed -n '2290,2370p'; nl -ba vibecomfy/executor/contracts.py | sed -n '2525,2565p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
    35
    36	MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
    37	    "empty_response",
    38	    "malformed_json",
    39	    "non_json_content",
    40	    "missing_required_fields",
    41	    "timeout",
    42	    "provider_failure",
    43	})
    44	_MODEL_ATTEMPT_OUTCOMES = frozenset({"success", "failure"})
    45	_MODEL_ATTEMPT_UNKNOWN = "unknown"
    46	_MODEL_ATTEMPT_PREVIEW_LIMIT = 1200
    47	_MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE = re.compile(
    48	    r"(?i)\b(api[_-]?key|authorization|bearer[_-]?token|access[_-]?token|secret|token)"
    49	    r"(\s*[:=]\s*)([^\s,;]+)"
    50	)
    51	_MODEL_ATTEMPT_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
    52	_MODEL_ATTEMPT_URL_RE = re.compile(r"https?://[^\s<>\"']+")
    53
    54
    55	def normalize_model_endpoint(value: Any) -> str:
    56	    """Return a credential-free, query-free endpoint or ``"unknown"``.
    57
    58	    Model-attempt evidence intentionally records only the scheme, host, port,
    59	    and normalized path. Userinfo, query parameters, and fragments are never
    60	    provenance and can contain credentials, so they are discarded wholesale.
    61	    """
    62	    if not isinstance(value, str) or not value.strip():
    63	        return _MODEL_ATTEMPT_UNKNOWN
    64	    try:
    65	        parsed = urlsplit(value.strip())
    66	    except ValueError:
    67	        return _MODEL_ATTEMPT_UNKNOWN
    68	    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
    69	        return _MODEL_ATTEMPT_UNKNOWN
    70	    host = parsed.hostname.lower()
    71	    if ":" in host and not host.startswith("["):
    72	        host = f"[{host}]"
    73	    try:
    74	        port = parsed.port
    75	    except ValueError:
    76	        return _MODEL_ATTEMPT_UNKNOWN
    77	    netloc = f"{host}:{port}" if port is not None else host
    78	    path = re.sub(r"/{2,}", "/", parsed.path or "")
    79	    if path != "/":
    80	        path = path.rstrip("/")
    81	    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))
    82
    83
    84	def redact_model_preview(value: Any, *, limit: int = _MODEL_ATTEMPT_PREVIEW_LIMIT) -> str | None:
    85	    """Return a bounded failure preview with credentials and URL queries removed."""
    86	    if not isinstance(value, str):
    87	        return None
    88	    normalized = " ".join(value.strip().split())
    89	    if not normalized:
    90	        return None
    91	    normalized = _MODEL_ATTEMPT_URL_RE.sub(
    92	        lambda match: normalize_model_endpoint(match.group(0)), normalized
    93	    )
    94	    normalized = _MODEL_ATTEMPT_BEARER_RE.sub("Bearer <redacted>", normalized)
    95	    normalized = _MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE.sub(
    96	        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", normalized
    97	    )
    98	    if len(normalized) > limit:
    99	        normalized = normalized[: limit - 1].rstrip() + "…"
   100	    return normalized
   101
   102
   103	def _model_attempt_text(value: Any) -> str:
   104	    if isinstance(value, str) and value.strip():
   105	        return value.strip()
   106	    return _MODEL_ATTEMPT_UNKNOWN
   107
   108
   109	def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
   110	    usage = value if isinstance(value, Mapping) else {}
   111	    normalized: dict[str, int | str] = {}
   112	    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
   113	        token_value = usage.get(key)
   114	        normalized[key] = (
   115	            max(0, int(token_value))
   116	            if isinstance(token_value, (int, float)) and not isinstance(token_value, bool)
   117	            else _MODEL_ATTEMPT_UNKNOWN
   118	        )
   119	    return normalized
   120
   121
   122	@dataclass(frozen=True)
   123	class ModelAttemptEvidence:
   124	    """Canonical evidence for one actual model-provider call.
   125
   126	    The shape is shared by worker envelopes, runtime/provider results, executor
   127	    reports, durable artifacts, and the live harness. Raw model output is never
   128	    retained on success and is bounded/redacted on failure.
   129	    """
   130
   131	    phase: str = _MODEL_ATTEMPT_UNKNOWN
   132	    attempt: int = 1
   133	    outcome: str = "failure"
   134	    failure_type: str | None = None
   135	    requested_model: str = _MODEL_ATTEMPT_UNKNOWN
   136	    resolved_model: str = _MODEL_ATTEMPT_UNKNOWN
   137	    adapter: str = _MODEL_ATTEMPT_UNKNOWN
   138	    provider: str = _MODEL_ATTEMPT_UNKNOWN
   139	    transport: str = _MODEL_ATTEMPT_UNKNOWN
   140	    endpoint: str = _MODEL_ATTEMPT_UNKNOWN
   141	    finish_reason: str = _MODEL_ATTEMPT_UNKNOWN
   142	    token_usage: Mapping[str, Any] = field(default_factory=dict)
   143	    raw_response_preview: str | None = None
   144
   145	    def __post_init__(self) -> None:
   146	        outcome = self.outcome if self.outcome in _MODEL_ATTEMPT_OUTCOMES else "failure"
   147	        failure_type = self.failure_type
   148	        if outcome == "success":
   149	            failure_type = None
   150	        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
   151	            failure_type = "provider_failure"
   152	        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
   153	        object.__setattr__(self, "attempt", max(1, int(self.attempt or 1)))
   154	        object.__setattr__(self, "outcome", outcome)
   155	        object.__setattr__(self, "failure_type", failure_type)
   156	        for name in (
   157	            "requested_model", "resolved_model", "adapter", "provider",
   158	            "transport", "finish_reason",
   159	        ):
   160	            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
   161	        object.__setattr__(self, "endpoint", normalize_model_endpoint(self.endpoint))
   162	        object.__setattr__(
   163	            self,
   164	            "token_usage",
   165	            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
   166	        )
   167	        preview = (
   168	            redact_model_preview(self.raw_response_preview)
   169	            if outcome == "failure"
   170	            else None
   171	        )
   172	        object.__setattr__(self, "raw_response_preview", preview)
   173
   174	    @classmethod
   175	    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
   176	        return cls(
   177	            phase=value.get("phase", _MODEL_ATTEMPT_UNKNOWN),
   178	            attempt=value.get("attempt", 1),
   179	            outcome=value.get("outcome", "failure"),
   180	            failure_type=value.get("failure_type"),
   181	            requested_model=value.get("requested_model", _MODEL_ATTEMPT_UNKNOWN),
   182	            resolved_model=value.get("resolved_model", _MODEL_ATTEMPT_UNKNOWN),
   183	            adapter=value.get("adapter", _MODEL_ATTEMPT_UNKNOWN),
   184	            provider=value.get("provider", _MODEL_ATTEMPT_UNKNOWN),
   185	            transport=value.get("transport", _MODEL_ATTEMPT_UNKNOWN),
   186	            endpoint=value.get("endpoint", _MODEL_ATTEMPT_UNKNOWN),
   187	            finish_reason=value.get("finish_reason", _MODEL_ATTEMPT_UNKNOWN),
   188	            token_usage=value.get("token_usage", {}),
   189	            raw_response_preview=value.get("raw_response_preview"),
   190	        )
   191
   192	    def to_dict(self) -> dict[str, Any]:
   193	        payload: dict[str, Any] = {
   194	            "phase": self.phase,
   195	            "attempt": self.attempt,
   196	            "outcome": self.outcome,
   197	            "failure_type": self.failure_type,
   198	            "requested_model": self.requested_model,
   199	            "resolved_model": self.resolved_model,
   200	            "adapter": self.adapter,
   201	            "provider": self.provider,
   202	            "transport": self.transport,
   203	            "endpoint": self.endpoint,
   204	            "finish_reason": self.finish_reason,
   205	            "token_usage": dict(self.token_usage),
    85	        parsed = json.loads(stripped)
    86	    except json.JSONDecodeError:
    87	        # The model often emits the JSON object followed by EXTRA data (a second
    88	        # object, or trailing prose / reasoning), which makes a strict json.loads
    89	        # raise "Extra data" and fail the whole turn. A greedy {.*} regex is worse —
    90	        # on "{obj}{extra}" it captures BOTH and still fails. Decode the FIRST
    91	        # complete object from the first '{' with raw_decode and ignore the rest.
    92	        start = stripped.find("{")
    93	        if start == -1:
    94	            raise
    95	        parsed, _ = json.JSONDecoder().raw_decode(stripped[start:])
    96	    if not isinstance(parsed, dict):
    97	        raise ValueError("Agent response JSON was not an object.")
    98	    return parsed
    99
   100
   101	def _raw_response_preview(text: str | None, *, limit: int = 1200) -> str | None:
   102	    """Return a bounded, whitespace-normalized preview of a raw model response."""
   103	    return redact_model_preview(text, limit=limit)
   104
   105
   106	def _model_attempt_failure_type(exc: BaseException, raw_text: str | None) -> str:
   107	    """Classify an observed failed call without consulting response wording."""
   108	    if raw_text is not None and not str(raw_text).strip():
   109	        return "empty_response"
   110	    if isinstance(exc, TimeoutError):
   111	        return "timeout"
   112	    if isinstance(exc, json.JSONDecodeError):
   113	        return "malformed_json" if "{" in (raw_text or "") else "non_json_content"
   114	    message = str(exc).lower()
   115	    if "not an object" in message:
   116	        return "non_json_content"
   117	    if isinstance(exc, ValueError):
   118	        if "must include" in message or "field" in message:
   119	            return "missing_required_fields"
   120	        return "malformed_json"
   121	    return "provider_failure"
   122
   123
   124	def _worker_provider_transport(
   125	    request: dict[str, Any],
   126	) -> tuple[str, str, str]:
   127	    agent_id = str(request.get("agent_id") or "hermes")
   128	    agent_kwargs = request.get("agent_kwargs")
   129	    if not isinstance(agent_kwargs, dict):
   130	        agent_kwargs = {}
   131	    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
   132	    if agent_id != "hermes":
   133	        return "unknown", "unknown", endpoint
   134	    if "openrouter.ai" in endpoint:
   135	        return "openrouter", "openrouter", endpoint
   136	    if "deepseek.com" in endpoint:
   137	        return "deepseek", "native", endpoint
   138	    if endpoint != "unknown":
   139	        return "unknown", "openai_compatible", endpoint
   140	    return "unknown", "unknown", endpoint
   141
   142
   143	def _model_attempt(
   144	    request: dict[str, Any],
   145	    profiling_context: dict[str, Any],
   146	    worker_metadata: dict[str, Any] | None,
   147	    *,
   148	    outcome: str,
   149	    failure_type: str | None = None,
   150	    raw_text: str | None = None,
   151	) -> dict[str, Any]:
   152	    agent_kwargs = request.get("agent_kwargs")
   153	    if not isinstance(agent_kwargs, dict):
   154	        agent_kwargs = {}
   155	    metadata = worker_metadata if isinstance(worker_metadata, dict) else {}
   156	    usage = metadata.get("deepseek_usage")
   157	    if not isinstance(usage, dict) or int(usage.get("n_calls") or 0) <= 0:
   158	        usage = {}
   159	    provider, transport, endpoint = _worker_provider_transport(request)
   160	    return ModelAttemptEvidence(
   161	        phase=profiling_context.get("backend_phase") or "agent_turn",
   162	        attempt=profiling_context.get("model_attempt") or 1,
   163	        outcome=outcome,
   164	        failure_type=failure_type,
   165	        requested_model=request.get("requested_model"),
   166	        resolved_model=agent_kwargs.get("model") or request.get("model"),
   167	        adapter=request.get("agent_id") or "hermes",
   168	        provider=provider,
   169	        transport=transport,
   170	        endpoint=endpoint,
   171	        finish_reason=metadata.get("finish_reason"),
   172	        token_usage=usage,
   173	        raw_response_preview=raw_text if outcome == "failure" else None,
   174	    ).to_dict()
   175
   176
   177	def _persist_parse_evidence(
   178	    out: dict[str, Any],
   179	    exc: BaseException,
   180	    raw_text: str,
   181	    worker_metadata: dict[str, Any] | None,
   182	    request: dict[str, Any],
   183	    profiling_context: dict[str, Any],
   184	) -> None:
   185	    """Persist bounded parse-failure evidence on the worker failure envelope.
   186
   187	    Additive only — the existing ``error`` / ``error_type`` envelope shape is
   188	    unchanged. Mirrors the batch-repl ``model_response`` detail capture
   189	    (parse_reason + raw preview) and adds the observed usage, model, phase,
   190	    endpoint, and finish reason so classify/reply attempts are diagnosable.
   191	    """
   192	    agent_kwargs = (
   193	        request.get("agent_kwargs")
   194	        if isinstance(request.get("agent_kwargs"), dict)
   195	        else {}
   196	    )
   197	    failure_type = _model_attempt_failure_type(exc, raw_text)
   198	    preview = _raw_response_preview(raw_text)
   199	    if preview:
   200	        out["raw_response_preview"] = preview
   201	    out["parse_reason"] = {
   202	        "empty_response": "empty",
   203	        "missing_required_fields": "missing_content",
   204	    }.get(failure_type, failure_type)
   205	    model = request.get("model") or agent_kwargs.get("model")
   206	    if model:
   207	        out["model"] = model
   208	    phase = profiling_context.get("backend_phase") or "agent_turn"
   209	    if phase:
   210	        out["phase"] = phase
   211	    endpoint = agent_kwargs.get("base_url")
   212	    if endpoint:
   213	        out["endpoint"] = normalize_model_endpoint(endpoint)
   214	    if isinstance(worker_metadata, dict):
   215	        finish_reason = worker_metadata.get("finish_reason")
   216	        if isinstance(finish_reason, str) and finish_reason.strip():
   217	            out["finish_reason"] = finish_reason.strip()
   218	        usage = worker_metadata.get("deepseek_usage")
   219	        if isinstance(usage, dict):
   220	            out["deepseek_usage"] = usage
   221	            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
   222	                value = usage.get(key)
   223	                if isinstance(value, int):
   224	                    out[key] = value
   225	    out["model_attempts"] = [
   226	        _model_attempt(
   227	            request,
   228	            profiling_context,
   229	            worker_metadata,
   230	            outcome="failure",
   231	            failure_type=failure_type,
   232	            raw_text=raw_text,
   233	        )
   234	    ]
   235
  2290	    """
  2291
  2292	    plan: ClassifyDecision | None = None
  2293	    research: ResearchResult | None = None
  2294	    implementation: ImplementationResult | None = None
  2295	    deepseek_usage: dict[str, Any] = field(default_factory=dict)
  2296	    deepseek_est_cost_usd: float | None = None
  2297	    deepseek_cost_basis: str | None = None
  2298	    # Truthful classification lifecycle signal: "failed" means classify raised
  2299	    # (the plan is then None — no invented respond_only placeholder). Empty
  2300	    # string means the signal was not recorded (legacy paths).
  2301	    classification_status: str = ""
  2302	    # Canonical per-call evidence for every successful and failed model attempt
  2303	    # observed across classify, implement/batch, and reply.
  2304	    model_attempts: tuple[dict[str, Any], ...] = ()
  2305	    # Mirrors the batch-repl model_response.json attempt artifact: parse-failure
  2306	    # evidence (parse_reason, raw preview, usage, model, phase, endpoint) for the
  2307	    # last classify/reply model attempt. None when the turn did not fail on a
  2308	    # model response.
  2309	    model_response: dict[str, Any] | None = None
  2310
  2311	    def __post_init__(self) -> None:
  2312	        object.__setattr__(
  2313	            self,
  2314	            "deepseek_usage",
  2315	            MappingProxyType({
  2316	                str(k): _freeze_jsonish(v)
  2317	                for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
  2318	            }),
  2319	        )
  2320	        object.__setattr__(
  2321	            self,
  2322	            "model_attempts",
  2323	            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
  2324	        )
  2325	        if self.model_response is not None:
  2326	            object.__setattr__(
  2327	                self,
  2328	                "model_response",
  2329	                _freeze_jsonish(self.model_response),
  2330	            )
  2331
  2332	    def to_dict(self) -> dict[str, Any]:
  2333	        inner: dict[str, Any] = {}
  2334	        if self.plan is not None:
  2335	            plan_payload = self.plan.to_dict()
  2336	            route = _public_route_for_plan(self.plan)
  2337	            plan_payload["route"] = route
  2338	            task = self.plan.effective_task
  2339	            if task:
  2340	                plan_payload["task"] = task
  2341	            inner["plan"] = plan_payload
  2342	        if self.research is not None:
  2343	            inner["research"] = self.research.to_dict()
  2344	        if self.implementation is not None:
  2345	            inner["implementation"] = self.implementation.to_dict()
  2346	        usage_payload = coerce_deepseek_usage(self.deepseek_usage)
  2347	        inner["deepseek_usage"] = usage_payload
  2348	        if self.deepseek_est_cost_usd is not None:
  2349	            inner["deepseek_est_cost_usd"] = float(self.deepseek_est_cost_usd)
  2350	        if isinstance(self.deepseek_cost_basis, str) and self.deepseek_cost_basis:
  2351	            inner["deepseek_cost_basis"] = self.deepseek_cost_basis
  2352	        if self.classification_status:
  2353	            inner["classification_status"] = self.classification_status
  2354	        inner["model_attempts"] = [
  2355	            _thaw_jsonish(item) for item in self.model_attempts
  2356	        ]
  2357	        if self.model_response is not None:
  2358	            inner["model_response"] = _thaw_jsonish(self.model_response)
  2359	        return {"executor": inner}
  2360
  2361
  2362	# ── canonical turn envelope ──────────────────────────────────────────────────
  2363
  2364
  2365	def _public_route_for_plan(plan: ClassifyDecision) -> str:
  2366	    route = plan.effective_route
  2367	    if route in _PUBLIC_ROUTES:
  2368	        return route
  2369	    if plan.implement and plan.research:
  2370	        return "adapt"
  2525	            reply=reply,
  2526	            evidence=AgentEvidence(
  2527	                classification=classification,
  2528	                graph_inspection=graph_inspection,
  2529	                research=research,
  2530	                implementation=implementation,
  2531	                warnings=tuple(warnings),
  2532	            ),
  2533	            candidate=candidate,
  2534	            no_candidate_reason=reason,
  2535	            disposition=disposition,
  2536	        )
  2537
  2538
  2539	def _derive_no_candidate_reason(
  2540	    *,
  2541	    route: str,
  2542	    result: "ExecutorResult",
  2543	    implementation: Mapping[str, Any],
  2544	) -> str | None:
  2545	    if route not in _APPLY_ELIGIBLE_ROUTES:
  2546	        return "route_not_applyable"
  2547	    if result.graph is not None:
  2548	        return None
  2549	    if result.failure_stage == "implement":
  2550	        return "implementation_failed"
  2551	    if result.failure_kind is not None:
  2552	        return "implementation_failed"
  2553	    if result.report.implementation is None:
  2554	        return "implementation_skipped"
  2555	    if implementation and implementation.get("graph") is None:
  2556	        return "no_changes"
  2557	    return "no_graph"
  2558
  2559
  2560	# ── executor result (final envelope leaf) ────────────────────────────────────
  2561
  2562	# Keys from the durable handle_agent_edit response that the executor propagates
  2563	# to the top-level serialized envelope (SD1, SD2).  Executor-owned fields
  2564	# (graph, message, route, candidate, apply_eligible) always take priority.
  2565	_DURABLE_ENVELOPE_TOP_LEVEL_KEYS: tuple[str, ...] = (

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/worker.py | nl -ba | sed -n '150,165p'; git hash-object vibecomfy/comfy_nodes/agent/worker.py; git rev-parse e33f0260:vibecomfy/comfy_nodes/agent/worker.py; git status --porcelain=v2" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 135ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
ab51a994fa4e5987a9ce25d8f3f3faf601277ebf
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
da5c790954fcab1c3ad49971a3ecd201edcb727e
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
1 .M N... 100644 100644 100644 9286c3fc7f613ed3705435f549cf2042b2cae868 9286c3fc7f613ed3705435f549cf2042b2cae868 tests/live_agentic_harness/runner.py
1 .M N... 100644 100644 100644 f5e275c78e3dbd623b52bc6291108f1ae0df0411 f5e275c78e3dbd623b52bc6291108f1ae0df0411 tests/test_live_agentic_runner_persistence.py
1 .M N... 100644 100644 100644 c6c196671609c54624bb1d4bb7e1c867f9618832 c6c196671609c54624bb1d4bb7e1c867f9618832 vibecomfy/agent/artifacts.py
1 .M N... 100644 100644 100644 935aa56f65b59d30a68af6a23c8e0bceeb19814b 935aa56f65b59d30a68af6a23c8e0bceeb19814b vibecomfy/comfy_nodes/agent/provider.py
1 .M N... 100644 100644 100644 da5c790954fcab1c3ad49971a3ecd201edcb727e da5c790954fcab1c3ad49971a3ecd201edcb727e vibecomfy/comfy_nodes/agent/worker.py
1 .M N... 100644 100644 100644 7dc02508f41cef9410d10fcf1f7078543aa4285c 7dc02508f41cef9410d10fcf1f7078543aa4285c vibecomfy/executor/agent_backend.py
? .oracle/checkins/batch-B01.md

codex
The live worktree changed during review (six tracked files now differ from `e33f0260`), so I’m freezing all remaining analysis to the named commit object and range rather than reviewing moving working-tree content. I will not touch or attribute those concurrent edits; the verdict will apply specifically to `16d80bbe..e33f0260`.
exec
/bin/zsh -lc 'git diff --stat && git diff -- vibecomfy/comfy_nodes/agent/worker.py vibecomfy/executor/agent_backend.py vibecomfy/comfy_nodes/agent/provider.py vibecomfy/agent/artifacts.py tests/live_agentic_harness/runner.py tests/test_live_agentic_runner_persistence.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 93ms:
 tests/live_agentic_harness/runner.py          |  2 +-
 tests/test_headless_agent_artifacts.py        |  1 +
 tests/test_live_agentic_runner_persistence.py |  1 +
 vibecomfy/agent/artifacts.py                  | 13 ++++++----
 vibecomfy/comfy_nodes/agent/provider.py       | 16 +++++++++++--
 vibecomfy/comfy_nodes/agent/worker.py         |  7 +-----
 vibecomfy/executor/agent_backend.py           | 16 ++++++-------
 vibecomfy/executor/core.py                    | 34 +++++++++++++++++++++++++--
 8 files changed, 65 insertions(+), 25 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index 9286c3fc..c86fcd92 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -137,7 +137,7 @@ def _failure_summary(
         ),
         "failure_class": failure_class,
         "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
-        "retryable_infra": failure_class.startswith("infra_"),
+        "retryable_infra": failure_class == "infra_empty_response",
         "agent_exercised": False,
         "attempt": attempt,
         "elapsed_s": elapsed_s,
diff --git a/tests/test_live_agentic_runner_persistence.py b/tests/test_live_agentic_runner_persistence.py
index f5e275c7..61cf4723 100644
--- a/tests/test_live_agentic_runner_persistence.py
+++ b/tests/test_live_agentic_runner_persistence.py
@@ -128,6 +128,7 @@ def test_runner_does_not_retry_outer_timeout(
     assert scenario["attempt_count"] == 1
     assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
     assert scenario["attempts"][0]["score_class"] == "infra_blocked"
+    assert scenario["attempts"][0]["retryable_infra"] is False
     assert scenario["attempts"][0]["agent_exercised"] is False
     assert scenario["attempts"][0]["elapsed_s"] is not None
     assert (
diff --git a/vibecomfy/agent/artifacts.py b/vibecomfy/agent/artifacts.py
index c6c19667..5325cf80 100644
--- a/vibecomfy/agent/artifacts.py
+++ b/vibecomfy/agent/artifacts.py
@@ -8,7 +8,6 @@ from __future__ import annotations

 import json
 import logging
-import shutil
 from pathlib import Path
 from typing import Any, Mapping

@@ -111,9 +110,13 @@ def _copy_turn_artifacts(turn_dir: Path, output_dir: Path) -> list[str]:
                         rendered.append(json.dumps(_redact(json.loads(line)), sort_keys=True))
                     dest.write_text("\n".join(rendered) + ("\n" if rendered else ""), encoding="utf-8")
             except (OSError, json.JSONDecodeError):
-                # Preserve non-JSON diagnostic files for compatibility. Canonical
-                # model-attempt artifacts are always JSON and take the redacted path.
-                shutil.copy2(source, dest)
+                # Never raw-copy an unparseable model artifact: it may contain a
+                # credential in free text. Keep a bounded, redacted diagnostic.
+                try:
+                    preview = redact_model_preview(source.read_text(encoding="utf-8"))
+                except OSError:
+                    preview = None
+                _safe_write(dest, {"redacted_unparseable_artifact": preview or ""})
             copied.append(str(dest.relative_to(output_dir)))
     return copied

@@ -380,7 +383,7 @@ def synthesize_headless_artifacts(

     copied_set = set(copied)
     optional_model_artifacts = {
-        name: name in copied_set
+        name: name in copied_set or name in manifest
         for name in sorted(_MODEL_ARTIFACT_NAMES)
     }

diff --git a/vibecomfy/comfy_nodes/agent/provider.py b/vibecomfy/comfy_nodes/agent/provider.py
index 935aa56f..8698fc4c 100644
--- a/vibecomfy/comfy_nodes/agent/provider.py
+++ b/vibecomfy/comfy_nodes/agent/provider.py
@@ -1389,6 +1389,8 @@ def _batch_failure_type(exc: BaseException) -> str:
 def _revise_failed_runtime_attempt(
     response: Any,
     exc: BaseException,
+    *,
+    attempt_number: int,
 ) -> tuple[dict[str, Any], ...]:
     if not isinstance(response, Mapping):
         return ()
@@ -1397,6 +1399,7 @@ def _revise_failed_runtime_attempt(
         return ()
     latest = dict(attempts[-1])
     latest.update({
+        "attempt": attempt_number,
         "outcome": "failure",
         "failure_type": _batch_failure_type(exc),
         "raw_response_preview": getattr(exc, "raw_response", None),
@@ -1489,7 +1492,11 @@ def run_agent_turn_batch(
                     audit_metadata=audit_metadata,
                 )
             except (MalformedModelJSON, MissingRequiredField) as exc:
-                failed_attempts = _revise_failed_runtime_attempt(response, exc)
+                failed_attempts = _revise_failed_runtime_attempt(
+                    response,
+                    exc,
+                    attempt_number=attempt_index + 1,
+                )
                 attempt_log.extend(failed_attempts)
                 last_exc = exc
                 if attempt_index >= attempts - 1 or not _typed_empty_attempt(failed_attempts):
@@ -1499,9 +1506,14 @@ def run_agent_turn_batch(
             current_attempts = list(
                 coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
             )
+            for current_attempt in current_attempts:
+                current_attempt["attempt"] = attempt_index + 1
             if attempt_log:
                 metadata = dict(result.audit_metadata or {})
-                metadata["model_attempts"] = [*attempt_log, *current_attempts]
+                metadata["model_attempts"] = [
+                    ModelAttemptEvidence.from_mapping(item).to_dict()
+                    for item in (*attempt_log, *current_attempts)
+                ]
                 result = dataclasses.replace(result, audit_metadata=metadata)
             if retry_count:
                 metadata = dict(result.audit_metadata or {})
diff --git a/vibecomfy/comfy_nodes/agent/worker.py b/vibecomfy/comfy_nodes/agent/worker.py
index da5c7909..ab51a994 100644
--- a/vibecomfy/comfy_nodes/agent/worker.py
+++ b/vibecomfy/comfy_nodes/agent/worker.py
@@ -154,12 +154,7 @@ def _model_attempt(
         agent_kwargs = {}
     metadata = worker_metadata if isinstance(worker_metadata, dict) else {}
     usage = metadata.get("deepseek_usage")
-    if not isinstance(usage, dict) or not (
-        int(usage.get("n_calls") or 0) > 0
-        or any(isinstance(usage.get(key), (int, float)) for key in (
-            "prompt_tokens", "completion_tokens", "total_tokens"
-        ))
-    ):
+    if not isinstance(usage, dict) or int(usage.get("n_calls") or 0) <= 0:
         usage = {}
     provider, transport, endpoint = _worker_provider_transport(request)
     return ModelAttemptEvidence(
diff --git a/vibecomfy/executor/agent_backend.py b/vibecomfy/executor/agent_backend.py
index 7dc02508..c7e89378 100644
--- a/vibecomfy/executor/agent_backend.py
+++ b/vibecomfy/executor/agent_backend.py
@@ -24,7 +24,12 @@ from .prompts import (
     parse_classify_response,
     parse_reply_response,
 )
-from .contracts import ClassifyDecision, ModelAttemptEvidence, coerce_model_attempts
+from .contracts import (
+    ClassifyDecision,
+    ModelAttemptEvidence,
+    coerce_model_attempts,
+    redact_model_preview,
+)

 LOGGER = logging.getLogger(__name__)

@@ -49,14 +54,7 @@ def _extract_content(result: dict[str, Any]) -> str:

 def _preview_raw(text: str | None, *, limit: int = 1200) -> str | None:
     """Bounded, whitespace-normalized preview of raw model output."""
-    if not isinstance(text, str):
-        return None
-    normalized = " ".join(text.strip().split())
-    if not normalized:
-        return None
-    if len(normalized) <= limit:
-        return normalized
-    return normalized[: limit - 1].rstrip() + "…"
+    return redact_model_preview(text, limit=limit)


 def _attach_model_turn_evidence(

exec
/bin/zsh -lc 'git diff -- vibecomfy/executor/core.py tests/test_headless_agent_artifacts.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/test_headless_agent_artifacts.py b/tests/test_headless_agent_artifacts.py
index 5fe462d4..d0787010 100644
--- a/tests/test_headless_agent_artifacts.py
+++ b/tests/test_headless_agent_artifacts.py
@@ -305,6 +305,7 @@ def test_model_attempt_artifact_is_canonical_and_redacts_secrets(tmp_path: Path)
     )

     assert "model_attempts.json" in manifest["manifest"]
+    assert manifest["optional_model_artifacts"]["model_attempts.json"] is True
     attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
     assert attempts[0]["endpoint"] == "https://openrouter.ai/api/v1"
     assert "top-secret" not in attempts[0]["raw_response_preview"]
diff --git a/vibecomfy/executor/core.py b/vibecomfy/executor/core.py
index 053ead93..242ee5e3 100644
--- a/vibecomfy/executor/core.py
+++ b/vibecomfy/executor/core.py
@@ -53,6 +53,7 @@ from .contracts import (
     ExecutorRequest,
     ExecutorResult,
     ImplementationResult,
+    ModelAttemptEvidence,
     Report,
     ResearchResult,
     _ALLOWED_ROUTES,
@@ -221,7 +222,7 @@ def _enrich_failure_envelope(


 def _model_response_artifact(failure: Any) -> dict[str, Any] | None:
-    """Shape parse evidence into a batch-repl-style ``model_response`` artifact."""
+    """Shape legacy exception evidence into the canonical attempt contract."""
     context = getattr(failure, "agent_failure_context", None)
     if not isinstance(context, Mapping):
         return None
@@ -235,7 +236,36 @@ def _model_response_artifact(failure: Any) -> dict[str, Any] | None:
     }
     if not evidence:
         return None
-    return {"turns": [{"error": dict(evidence)}]}
+    parse_reason = str(evidence.get("parse_reason") or "")
+    failure_type = {
+        "empty": "empty_response",
+        "empty_response": "empty_response",
+        "malformed_json": "malformed_json",
+        "non_json_content": "non_json_content",
+        "missing_content": "missing_required_fields",
+        "missing_required_fields": "missing_required_fields",
+    }.get(parse_reason, "provider_failure")
+    token_usage = {
+        key: evidence.get(key)
+        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
+        if evidence.get(key) is not None
+    }
+    attempt = ModelAttemptEvidence(
+        phase=evidence.get("phase"),
+        attempt=1,
+        outcome="failure",
+        failure_type=failure_type,
+        requested_model=evidence.get("requested_model") or evidence.get("model"),
+        resolved_model=evidence.get("resolved_model") or evidence.get("model"),
+        adapter=evidence.get("adapter"),
+        provider=evidence.get("provider"),
+        transport=evidence.get("transport"),
+        endpoint=evidence.get("endpoint"),
+        finish_reason=evidence.get("finish_reason"),
+        token_usage=token_usage,
+        raw_response_preview=evidence.get("raw_response_preview"),
+    ).to_dict()
+    return {"attempts": [attempt]}


 def _allows_install_or_provider_research(query: str) -> bool:

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/agent/artifacts.py | nl -ba | sed -n '55,125p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 40ms:
exec
/bin/zsh -lc "git show e33f0260:vibecomfy/executor/agent_backend.py | nl -ba | sed -n '45,90p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 40ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
    45	        "Model turn result did not contain text content. "
    46	        f"Got keys: {sorted(result.keys())}"
    47	    )
    48
    49
    50	def _preview_raw(text: str | None, *, limit: int = 1200) -> str | None:
    51	    """Bounded, whitespace-normalized preview of raw model output."""
    52	    if not isinstance(text, str):
    53	        return None
    54	    normalized = " ".join(text.strip().split())
    55	    if not normalized:
    56	        return None
    57	    if len(normalized) <= limit:
    58	        return normalized
    59	    return normalized[: limit - 1].rstrip() + "…"
    60
    61
    62	def _attach_model_turn_evidence(
    63	    exc: BaseException,
    64	    result: dict[str, Any] | None,
    65	    *,
    66	    model: str,
    67	    phase: str,
    68	    raw: str | None,
    69	) -> None:
    70	    """Attach additive parse evidence to a classify/reply exception in place.
    71
    72	    The provider result dict carries the worker's deepseek_usage plus the
    73	    resolved model/phase/endpoint; attaching it (and the raw content preview)
    74	    lets the executor's failure envelope persist tokens + raw preview + context
    75	    without re-resolving provider internals.
    76	    """
    77	    try:
    78	        if result is not None and getattr(exc, "worker_result", None) is None:
    79	            exc.worker_result = dict(result)  # type: ignore[attr-defined]
    80	        if result is not None and getattr(exc, "model_attempts", None) is None:
    81	            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
    82	        if raw is not None and getattr(exc, "raw_response_preview", None) is None:
    83	            exc.raw_response_preview = _preview_raw(raw)  # type: ignore[attr-defined]
    84	        for name, value in (("model", model), ("phase", phase)):
    85	            if getattr(exc, name, None) is None:
    86	                setattr(exc, name, value)
    87	    except Exception:  # noqa: BLE001 - evidence attachment is best-effort
    88	        pass
    89
    90

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/executor/core.py | nl -ba | sed -n '105,245p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   105	# ── model-response parse evidence (classify/reply) ──────────────────────────
   106	# Additive evidence persisted when a classify/reply model turn fails to parse.
   107	# Mirrors the batch-repl model_response.json detail (parse_reason + raw
   108	# preview) plus observed usage, model, phase, and endpoint so a failed attempt
   109	# is diagnosable from the final failure envelope without re-resolving provider
   110	# internals. The failure envelope's public shape is unchanged.
   111
   112	_MODEL_RESPONSE_EVIDENCE_KEYS = (
   113	    "model_attempts",
   114	    "parse_reason",
   115	    "raw_response_preview",
   116	    "finish_reason",
   117	    "completion_tokens",
   118	    "prompt_tokens",
   119	    "total_tokens",
   120	    "model",
   121	    "phase",
   122	    "endpoint",
   123	)
   124
   125	_PARSE_REASON_EMPTY = "empty"
   126	_PARSE_REASON_MISSING_CONTENT = "missing_content"
   127	_PARSE_REASON_MALFORMED_JSON = "malformed_json"
   128	_PARSE_REASON_NON_JSON_CONTENT = "non_json_content"
   129
   130
   131	def _evidence_value(value: Any) -> bool:
   132	    if value is None:
   133	        return False
   134	    if isinstance(value, str):
   135	        return bool(value.strip())
   136	    return True
   137
   138
   139	def _infer_parse_reason(exc: BaseException) -> str:
   140	    """Derive a parse_reason from an exception when none was attached."""
   141	    if type(exc).__name__ == "JSONDecodeError":
   142	        return _PARSE_REASON_MALFORMED_JSON
   143	    message = str(exc).lower()
   144	    if "could not extract a json object" in message or "jsondecodeerror" in message:
   145	        return _PARSE_REASON_MALFORMED_JSON
   146	    if "not an object" in message or "non_json" in message:
   147	        return _PARSE_REASON_NON_JSON_CONTENT
   148	    if (
   149	        "did not contain" in message
   150	        or "must include" in message
   151	        or ("missing" in message and "field" in message)
   152	        or "empty" in message
   153	    ):
   154	        return _PARSE_REASON_MISSING_CONTENT
   155	    return ""
   156
   157
   158	def _model_response_evidence_from_exception(exc: BaseException) -> dict[str, Any]:
   159	    """Pull additive parse evidence off an exception and its cause chain.
   160
   161	    Reads evidence attrs attached by the worker / runtime / provider /
   162	    agent-backend hops (including the worker result dict) and walks
   163	    ``__cause__`` so evidence survives provider wrapping. First non-empty value
   164	    wins.
   165	    """
   166	    evidence: dict[str, Any] = {}
   167	    seen: set[int] = set()
   168	    current: BaseException | None = exc
   169	    while current is not None and id(current) not in seen:
   170	        seen.add(id(current))
   171	        for key in _MODEL_RESPONSE_EVIDENCE_KEYS:
   172	            if key in evidence:
   173	                continue
   174	            value = getattr(current, key, None)
   175	            if _evidence_value(value):
   176	                evidence[key] = value
   177	        worker_result = getattr(current, "worker_result", None)
   178	        if isinstance(worker_result, Mapping):
   179	            for key in _MODEL_RESPONSE_EVIDENCE_KEYS:
   180	                if key in evidence:
   181	                    continue
   182	                value = worker_result.get(key)
   183	                if _evidence_value(value):
   184	                    evidence[key] = value
   185	            usage = worker_result.get("deepseek_usage")
   186	            if isinstance(usage, Mapping):
   187	                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
   188	                    if key in evidence:
   189	                        continue
   190	                    value = usage.get(key)
   191	                    if isinstance(value, int) and value >= 0:
   192	                        evidence[key] = value
   193	        current = current.__cause__
   194	    if "parse_reason" not in evidence:
   195	        reason = _infer_parse_reason(exc)
   196	        if reason:
   197	            evidence["parse_reason"] = reason
   198	    return evidence
   199
   200
   201	def _enrich_failure_envelope(
   202	    failure: Any,
   203	    exc: BaseException,
   204	    *,
   205	    phase: str,
   206	    model: str | None,
   207	) -> Any:
   208	    """Merge parse evidence into a failure envelope's agent_failure_context.
   209
   210	    Additive only: the envelope's existing keys (``explanation``, ...) are kept.
   211	    """
   212	    evidence = _model_response_evidence_from_exception(exc)
   213	    evidence.setdefault("phase", phase)
   214	    if model:
   215	        evidence.setdefault("model", model)
   216	    if not evidence:
   217	        return failure
   218	    context = dict(failure.agent_failure_context or {})
   219	    context.update(evidence)
   220	    return replace(failure, agent_failure_context=context)
   221
   222
   223	def _model_response_artifact(failure: Any) -> dict[str, Any] | None:
   224	    """Shape parse evidence into a batch-repl-style ``model_response`` artifact."""
   225	    context = getattr(failure, "agent_failure_context", None)
   226	    if not isinstance(context, Mapping):
   227	        return None
   228	    attempts = context.get("model_attempts")
   229	    if isinstance(attempts, (list, tuple)) and attempts:
   230	        return {"attempts": [dict(item) for item in attempts if isinstance(item, Mapping)]}
   231	    evidence = {
   232	        key: context[key]
   233	        for key in _MODEL_RESPONSE_EVIDENCE_KEYS
   234	        if context.get(key) is not None
   235	    }
   236	    if not evidence:
   237	        return None
   238	    return {"turns": [{"error": dict(evidence)}]}
   239
   240
   241	def _allows_install_or_provider_research(query: str) -> bool:
   242	    query_l = str(query or "").casefold()
   243	    return any(term in query_l for term in _INSTALL_REQUEST_TERMS)
   244
   245

exec
/bin/zsh -lc "git show e33f0260:tests/live_agentic_harness/runner.py | nl -ba | sed -n '110,290p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 7ms:
exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/provider.py | nl -ba | sed -n '1380,1520p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
  1380	    raw = getattr(exc, "raw_response", None)
  1381	    if isinstance(raw, str) and not raw.strip():
  1382	        return "empty_response"
  1383	    reason = getattr(exc, "parse_reason", None)
  1384	    if reason in {"missing_batch_fence"}:
  1385	        return "missing_required_fields"
  1386	    return "malformed_json"
  1387
  1388
  1389	def _revise_failed_runtime_attempt(
  1390	    response: Any,
  1391	    exc: BaseException,
  1392	) -> tuple[dict[str, Any], ...]:
  1393	    if not isinstance(response, Mapping):
  1394	        return ()
  1395	    attempts = list(coerce_model_attempts(response.get("model_attempts")))
  1396	    if not attempts:
  1397	        return ()
  1398	    latest = dict(attempts[-1])
  1399	    latest.update({
  1400	        "outcome": "failure",
  1401	        "failure_type": _batch_failure_type(exc),
  1402	        "raw_response_preview": getattr(exc, "raw_response", None),
  1403	    })
  1404	    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
  1405	    attempts[-1] = revised
  1406	    try:
  1407	        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
  1408
  1409	        replace_last_model_attempt(revised)
  1410	    except Exception:  # noqa: BLE001 - evidence capture is additive
  1411	        pass
  1412	    exc.model_attempts = list(attempts)  # type: ignore[attr-defined]
  1413	    return tuple(attempts)
  1414
  1415
  1416	def _typed_empty_attempt(attempts: tuple[dict[str, Any], ...]) -> bool:
  1417	    if not attempts:
  1418	        return False
  1419	    latest = attempts[-1]
  1420	    usage = latest.get("token_usage")
  1421	    return (
  1422	        latest.get("failure_type") == "empty_response"
  1423	        and isinstance(usage, Mapping)
  1424	        and usage.get("completion_tokens") == 0
  1425	    )
  1426
  1427
  1428	def run_agent_turn_batch(
  1429	    task: str,
  1430	    messages: list[dict[str, str]],
  1431	    *,
  1432	    route: str | None = None,
  1433	    model: str | None = None,
  1434	    effort: str | None = None,
  1435	) -> BatchTurnResult:
  1436	    """Run a single batch-REPL turn through the Arnold/Hermes provider.
  1437
  1438	    Sends *messages* (built by :func:`build_batch_messages`) to the model
  1439	    and normalizes the response through :func:`extract_batch_fence` instead
  1440	    of JSON parsing.  Returns a :class:`BatchTurnResult` with the fenced
  1441	    batch code and surrounding prose.
  1442
  1443	    Parameters
  1444	    ----------
  1445	    task:
  1446	        The user's natural-language edit request.
  1447	    messages:
  1448	        Pre-built chat messages from :func:`build_batch_messages`.
  1449	    route:
  1450	        Optional provider route name.  Resolved via :func:`_resolve_agent_route`.
  1451	    model:
  1452	        Optional model identifier.  Falls back to ``VIBECOMFY_AGENT_MODEL``.
  1453	    """
  1454	    route_descriptor = _resolve_agent_route(route)
  1455	    selected_route = route_descriptor.normalized_route
  1456	    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
  1457	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
  1458	    runtime = _load_arnold_runtime()
  1459	    audit_metadata: dict[str, Any] = {
  1460	        "provider": "arnold",
  1461	        "requested_route": route_descriptor.requested_route,
  1462	        "route_metadata": route_descriptor.to_dict(),
  1463	        "legacy_deepseek_fallback_enabled": False,
  1464	        "credential_presence": _credential_presence(),
  1465	        "response_contract": "batch_repl",
  1466	    }
  1467	    try:
  1468	        attempts = 3
  1469	        retry_count = 0
  1470	        last_exc: MalformedModelJSON | MissingRequiredField | None = None
  1471	        current_messages = messages
  1472	        attempt_log: list[dict[str, Any]] = []
  1473	        for attempt_index in range(attempts):
  1474	            if attempt_index > 0 and last_exc is not None:
  1475	                current_messages = _batch_retry_messages(messages, last_exc)
  1476	            response = _call_batch_runtime(
  1477	                runtime,
  1478	                task=task,
  1479	                messages=current_messages,
  1480	                route=dispatch_route,
  1481	                model=selected_model,
  1482	                effort=effort,
  1483	            )
  1484	            try:
  1485	                result = _normalize_batch_response(
  1486	                    response,
  1487	                    route=dispatch_route,
  1488	                    model=selected_model,
  1489	                    audit_metadata=audit_metadata,
  1490	                )
  1491	            except (MalformedModelJSON, MissingRequiredField) as exc:
  1492	                failed_attempts = _revise_failed_runtime_attempt(response, exc)
  1493	                attempt_log.extend(failed_attempts)
  1494	                last_exc = exc
  1495	                if attempt_index >= attempts - 1 or not _typed_empty_attempt(failed_attempts):
  1496	                    raise
  1497	                retry_count += 1
  1498	                continue
  1499	            current_attempts = list(
  1500	                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
  1501	            )
  1502	            if attempt_log:
  1503	                metadata = dict(result.audit_metadata or {})
  1504	                metadata["model_attempts"] = [*attempt_log, *current_attempts]
  1505	                result = dataclasses.replace(result, audit_metadata=metadata)
  1506	            if retry_count:
  1507	                metadata = dict(result.audit_metadata or {})
  1508	                metadata["batch_repl_retry"] = {
  1509	                    "count": retry_count,
  1510	                    "reason": str(last_exc) if last_exc is not None else "",
  1511	                    "parse_reason": getattr(last_exc, "parse_reason", None),
  1512	                    "raw_response_preview": getattr(last_exc, "raw_response_preview", None),
  1513	                }
  1514	                result = dataclasses.replace(result, audit_metadata=metadata)
  1515	            return result
  1516	        if last_exc is not None:
  1517	            raise last_exc
  1518	        raise ProviderError("Agent batch_repl provider exited without a response.")
  1519	    except PermissionError as exc:
  1520	        raise AuthError(str(exc)) from exc

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/worker.py | nl -ba | sed -n '145,180p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 2ms:
   145	    profiling_context: dict[str, Any],
   146	    worker_metadata: dict[str, Any] | None,
   147	    *,
   148	    outcome: str,
   149	    failure_type: str | None = None,
   150	    raw_text: str | None = None,
   151	) -> dict[str, Any]:
   152	    agent_kwargs = request.get("agent_kwargs")
   153	    if not isinstance(agent_kwargs, dict):
   154	        agent_kwargs = {}
   155	    metadata = worker_metadata if isinstance(worker_metadata, dict) else {}
   156	    usage = metadata.get("deepseek_usage")
   157	    if not isinstance(usage, dict) or not (
   158	        int(usage.get("n_calls") or 0) > 0
   159	        or any(isinstance(usage.get(key), (int, float)) for key in (
   160	            "prompt_tokens", "completion_tokens", "total_tokens"
   161	        ))
   162	    ):
   163	        usage = {}
   164	    provider, transport, endpoint = _worker_provider_transport(request)
   165	    return ModelAttemptEvidence(
   166	        phase=profiling_context.get("backend_phase") or "agent_turn",
   167	        attempt=profiling_context.get("model_attempt") or 1,
   168	        outcome=outcome,
   169	        failure_type=failure_type,
   170	        requested_model=request.get("requested_model"),
   171	        resolved_model=agent_kwargs.get("model") or request.get("model"),
   172	        adapter=request.get("agent_id") or "hermes",
   173	        provider=provider,
   174	        transport=transport,
   175	        endpoint=endpoint,
   176	        finish_reason=metadata.get("finish_reason"),
   177	        token_usage=usage,
   178	        raw_response_preview=raw_text if outcome == "failure" else None,
   179	    ).to_dict()
   180

exec
/bin/zsh -lc "git show e33f0260:tests/test_headless_agent_artifacts.py | nl -ba | sed -n '245,325p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 4ms:
   245	    assert (output_dir / "messages.jsonl").read_text(encoding="utf-8") == '{"role": "user"}\n'
   246	    assert (output_dir / "model_request.json").is_file()
   247	    assert (output_dir / "model_response.json").is_file()
   248
   249
   250	def test_model_attempt_artifact_is_canonical_and_redacts_secrets(tmp_path: Path) -> None:
   251	    output_dir = tmp_path / "out"
   252	    result = ExecutorResult.success(
   253	        report=Report(
   254	            model_attempts=(
   255	                {
   256	                    "phase": "classify",
   257	                    "attempt": 1,
   258	                    "outcome": "failure",
   259	                    "failure_type": "malformed_json",
   260	                    "requested_model": "requested-model",
   261	                    "resolved_model": "resolved-model",
   262	                    "adapter": "hermes",
   263	                    "provider": "openrouter",
   264	                    "transport": "openrouter",
   265	                    "endpoint": (
   266	                        "https://user:password@OpenRouter.ai/api/v1/?api_key=sk-secret"
   267	                        "&signature=sig-secret"
   268	                    ),
   269	                    "finish_reason": "stop",
   270	                    "token_usage": {
   271	                        "prompt_tokens": 11,
   272	                        "completion_tokens": 4,
   273	                        "total_tokens": 15,
   274	                    },
   275	                    "raw_response_preview": (
   276	                        "Authorization: Bearer top-secret "
   277	                        "https://example.test/v1?token=url-secret"
   278	                    ),
   279	                },
   280	                {
   281	                    "phase": "reply",
   282	                    "attempt": 1,
   283	                    "outcome": "success",
   284	                    "requested_model": "requested-model",
   285	                    "resolved_model": "resolved-model",
   286	                    "adapter": "codex",
   287	                    "provider": "unknown",
   288	                    "transport": "unknown",
   289	                    "endpoint": "unknown",
   290	                    "finish_reason": "unknown",
   291	                    "token_usage": {},
   292	                    "raw_response_preview": "must never persist on success",
   293	                },
   294	            )
   295	        ),
   296	        reply="ok",
   297	    )
   298
   299	    manifest = synthesize_headless_artifacts(
   300	        request={"query": "test"},
   301	        result=result,
   302	        response={"ok": True},
   303	        output_dir=output_dir,
   304	        status="success",
   305	    )
   306
   307	    assert "model_attempts.json" in manifest["manifest"]
   308	    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
   309	    assert attempts[0]["endpoint"] == "https://openrouter.ai/api/v1"
   310	    assert "top-secret" not in attempts[0]["raw_response_preview"]
   311	    assert "url-secret" not in attempts[0]["raw_response_preview"]
   312	    assert "raw_response_preview" not in attempts[1]
   313	    assert attempts[1]["provider"] == "unknown"
   314	    persisted = "\n".join(
   315	        path.read_text(encoding="utf-8")
   316	        for path in output_dir.iterdir()
   317	        if path.is_file()
   318	    )
   319	    assert "sk-secret" not in persisted
   320	    assert "sig-secret" not in persisted
   321	    assert "top-secret" not in persisted
   322	    assert "url-secret" not in persisted

exec
/bin/zsh -lc "git show e33f0260:tests/live_agentic_harness/runner.py | nl -ba | sed -n '420,650p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 324ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   420	    """
   421	    from .adapter import run_headless_scenario
   422	    from .guard import guard_output_dir
   423
   424	    path = Path(scenario_path)
   425	    scenario = _load_scenario(path)
   426	    scenario.setdefault("id", path.stem)
   427	    summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
   428	    summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
   429	    _classify_retryable_infra_summary(summary)
   430	    _persist_scenario_summary(summary, output_base, tag)
   431	    if out_file is not None:
   432	        out_file.parent.mkdir(parents=True, exist_ok=True)
   433	        out_file.write_text(json.dumps(summary, default=str), encoding="utf-8")
   434	    return summary
   435
   436
   437	def run_tag(
   438	    tag: str,
   439	    *,
   440	    scenarios_dir: Path | None = None,
   441	    output_base: Path | str | None = None,
   442	    max_workers: int = DEFAULT_MAX_WORKERS,
   443	    per_scenario_timeout: int = DEFAULT_PER_SCENARIO_TIMEOUT,
   444	    progress_every: int = DEFAULT_PROGRESS_EVERY,
   445	    infra_retries: int = DEFAULT_INFRA_RETRIES,
   446	) -> dict[str, Any]:
   447	    """Run every scenario under *scenarios_dir* CONCURRENTLY — each in its own
   448	    subprocess (process-isolated + kill-on-timeout), bounded by *max_workers*."""
   449	    if scenarios_dir is None:
   450	        scenarios_dir = Path(__file__).with_name("scenarios")
   451	    paths = _scenario_paths(scenarios_dir)
   452	    results: list[dict[str, Any] | None] = [None] * len(paths)
   453	    sem = threading.Semaphore(max(1, max_workers))
   454	    lock = threading.Lock()
   455	    tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
   456	    try:
   457	        def record_result(idx: int, summary: dict[str, Any]) -> None:
   458	            results[idx] = summary
   459	            results[idx].setdefault("scenario_id", paths[idx].stem)
   460	            _persist_scenario_summary(results[idx], output_base, tag)
   461	            with lock:
   462	                completed = sum(1 for r in results if r)
   463	                run_summary = _persist_run_summary(
   464	                    tag,
   465	                    results,
   466	                    output_base,
   467	                    total_scenarios=len(paths),
   468	                    complete=False,
   469	                )
   470	                if progress_every > 0 and (
   471	                    completed == len(paths) or completed % progress_every == 0
   472	                ):
   473	                    print(
   474	                        "[agentic-progress] "
   475	                        f"tag={tag} completed={completed}/{len(paths)} "
   476	                        f"passed={run_summary['passed']} failed={run_summary['failed']} "
   477	                        f"pending={run_summary['pending']}",
   478	                        file=sys.stderr,
   479	                        flush=True,
   480	                    )
   481
   482	        def worker(idx: int, path: Path) -> None:
   483	            sid = path.stem
   484	            scenario_for_synthetic = _load_scenario(path)
   485	            expect_graph_changed = _scenario_expect_graph_changed(scenario_for_synthetic)
   486	            attempts: list[dict[str, Any]] = []
   487	            with sem:
   488	                max_attempts = 1 + max(0, infra_retries)
   489	                final_summary: dict[str, Any] | None = None
   490	                for attempt in range(1, max_attempts + 1):
   491	                    attempt_run_tag = _attempt_tag(tag, sid, attempt)
   492	                    out_file = tmpdir / f"{idx:03d}-{attempt}.json"
   493	                    cmd = [
   494	                        sys.executable, "-m", "tests.live_agentic_harness.runner",
   495	                        "--single", str(path), "--tag", attempt_run_tag,
   496	                        "--single-out", str(out_file),
   497	                    ]
   498	                    if output_base is not None:
   499	                        cmd += ["--output-base", str(output_base)]
   500	                    started = time.monotonic()
   501	                    try:
   502	                        proc = subprocess.run(
   503	                            cmd, cwd=str(REPO), capture_output=True, text=True,
   504	                            timeout=per_scenario_timeout,
   505	                        )
   506	                        elapsed_s = time.monotonic() - started
   507	                        if out_file.exists():
   508	                            final_summary = json.loads(out_file.read_text(encoding="utf-8"))
   509	                            final_summary["attempt"] = attempt
   510	                            final_summary["elapsed_s"] = elapsed_s
   511	                            final_summary["agent_exercised"] = True
   512	                        else:
   513	                            tail = _trim((proc.stderr or ""))
   514	                            final_summary = _failure_summary(
   515	                                sid,
   516	                                output_base,
   517	                                attempt_run_tag,
   518	                                f"runner produced no summary (rc={proc.returncode}); {tail}",
   519	                                failure_class="infra_no_summary",
   520	                                attempt=attempt,
   521	                                expect_graph_changed=expect_graph_changed,
   522	                                stdout_tail=_trim(proc.stdout or ""),
   523	                                stderr_tail=tail,
   524	                                elapsed_s=elapsed_s,
   525	                            )
   526	                    except subprocess.TimeoutExpired as exc:
   527	                        elapsed_s = time.monotonic() - started
   528	                        final_summary = _failure_summary(
   529	                            sid,
   530	                            output_base,
   531	                            attempt_run_tag,
   532	                            f"scenario exceeded {per_scenario_timeout}s and was killed",
   533	                            failure_class="infra_timeout",
   534	                            attempt=attempt,
   535	                            expect_graph_changed=expect_graph_changed,
   536	                            stdout_tail=_trim((exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
   537	                            stderr_tail=_trim((exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
   538	                            elapsed_s=elapsed_s,
   539	                        )
   540	                    except Exception as exc:  # noqa: BLE001 — isolate one failure
   541	                        elapsed_s = time.monotonic() - started
   542	                        final_summary = _failure_summary(
   543	                            sid,
   544	                            output_base,
   545	                            attempt_run_tag,
   546	                            _trim(str(exc)),
   547	                            failure_class="infra_runner_exception",
   548	                            attempt=attempt,
   549	                            expect_graph_changed=expect_graph_changed,
   550	                            elapsed_s=elapsed_s,
   551	                        )
   552
   553	                    retryable_infra = _is_retryable_infra_summary(final_summary)
   554	                    attempts.append(_attempt_record(final_summary, attempt=attempt))
   555	                    if not retryable_infra:
   556	                        break
   557
   558	                if final_summary is None:
   559	                    final_summary = _failure_summary(
   560	                        sid,
   561	                        output_base,
   562	                        _attempt_tag(tag, sid, 1),
   563	                        "runner produced no attempt result",
   564	                        failure_class="infra_runner_exception",
   565	                        attempt=1,
   566	                        expect_graph_changed=expect_graph_changed,
   567	                    )
   568	                    attempts.append(_attempt_record(final_summary, attempt=1))
   569
   570	                final_summary["attempts"] = attempts
   571	                final_summary["attempt_count"] = len(attempts)
   572	                final_summary["final_attempt"] = attempts[-1]["attempt"]
   573	                final_summary["raw_first_attempt_success"] = attempts[0].get("live_agentic_success") is True
   574	                final_summary["final_success"] = final_summary["guard"].get("live_agentic_success") is True
   575	                final_summary.setdefault(
   576	                    "failure_class",
   577	                    attempts[-1].get("failure_class") or "product_or_assessment_failure",
   578	                )
   579	                final_summary.setdefault(
   580	                    "score_class",
   581	                    attempts[-1].get("score_class") or (
   582	                        "pass"
   583	                        if final_summary["guard"].get("live_agentic_success") is True
   584	                        else "product_fail"
   585	                    ),
   586	                )
   587	                record_result(idx, final_summary)
   588	                _persist_canonical_scenario_summary(
   589	                    final_summary,
   590	                    output_base,
   591	                    tag,
   592	                    sid,
   593	                )
   594
   595	        threads = [
   596	            threading.Thread(target=worker, args=(i, p), daemon=True)
   597	            for i, p in enumerate(paths)
   598	        ]
   599	        for t in threads:
   600	            t.start()
   601	        for t in threads:
   602	            t.join()
   603	    finally:
   604	        for f in tmpdir.glob("*.json"):
   605	            try:
   606	                f.unlink()
   607	            except Exception:  # noqa: BLE001
   608	                pass
   609	        try:
   610	            tmpdir.rmdir()
   611	        except Exception:  # noqa: BLE001
   612	            pass
   613
   614	    return _persist_run_summary(
   615	        tag,
   616	        results,
   617	        output_base,
   618	        total_scenarios=len(paths),
   619	        complete=True,
   620	    )
   621
   622
   623	def _build_parser() -> argparse.ArgumentParser:
   624	    parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
   625	    parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
   626	    parser.add_argument(
   627	        "--scenarios-dir",
   628	        default=None,
   629	        help="Directory containing scenario YAML/JSON files.",
   630	    )
   631	    parser.add_argument(
   632	        "--output-base",
   633	        default=None,
   634	        help="Base evidence directory (default: out/agentic).",
   635	    )
   636	    parser.add_argument(
   637	        "--json",
   638	        action="store_true",
   639	        help="Print JSON summary instead of a short report.",
   640	    )
   641	    parser.add_argument(
   642	        "--single",
   643	        default=None,
   644	        help="Run a SINGLE scenario file (subprocess entry point for parallel mode).",
   645	    )
   646	    parser.add_argument(
   647	        "--single-out",
   648	        default=None,
   649	        help="Path to write the single-scenario summary JSON (used with --single).",
   650	    )

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/worker.py | nl -ba | sed -n '390,575p'; git show e33f0260:vibecomfy/agent/deepseek_usage.py | nl -ba | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
collab: Wait
collab: Wait
exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/provider.py | nl -ba | sed -n '875,925p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   875	            normalized_route="openrouter",
   876	            browser_api_key_allowed=True,
   877	            guidance="OpenRouter browser key submission is supported and stored locally.",
   878	        )
   879	    if requested == "anthropic":
   880	        return AgentRouteDescriptor(
   881	            requested_route=requested,
   882	            normalized_route="arnold",
   883	            browser_api_key_allowed=False,
   884	            guidance=_ANTHROPIC_GUIDANCE,
   885	            tos_acknowledgement_required=True,
   886	        )
   887	    if requested == "openai-codex":
   888	        return AgentRouteDescriptor(
   889	            requested_route=requested,
   890	            normalized_route="arnold",
   891	            browser_api_key_allowed=False,
   892	            guidance=_CODEX_GUIDANCE,
   893	        )
   894	    if requested == "arnold":
   895	        return AgentRouteDescriptor(
   896	            requested_route=requested,
   897	            normalized_route="arnold",
   898	            browser_api_key_allowed=False,
   899	            guidance=_ARNOLD_GUIDANCE,
   900	        )
   901	    return AgentRouteDescriptor(
   902	        requested_route=requested,
   903	        normalized_route=requested,
   904	        browser_api_key_allowed=False,
   905	    )
   906
   907
   908	def _credential_presence() -> dict[str, bool]:
   909	    return {
   910	        "arnold_api_key": bool(os.getenv("ARNOLD_API_KEY")),
   911	        "hermes_api_key": bool(os.getenv("HERMES_API_KEY")),
   912	        "openrouter_api_key": _openrouter_key_present(),
   913	        "deepseek_api_key": _env_key_present("DEEPSEEK_API_KEY"),
   914	    }
   915
   916
   917	def _non_secret_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
   918	    redacted = redact_closed_set(dict(value)).value
   919	    return redacted if isinstance(redacted, dict) else {}
   920
   921
   922	def _resolve_route_and_model(
   923	    route: str | None,
   924	    model: str | None,
   925	) -> tuple[AgentRouteDescriptor, str, str]:

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/runtime.py | nl -ba | sed -n '300,375p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   300	def _normalize_route(route: str | None) -> str:
   301	    normalized = (route or "arnold").strip().lower()
   302	    if normalized in {"auto", "anthropic", "openai-codex"}:
   303	        return "arnold"
   304	    if normalized == "hermes":
   305	        return "openrouter"
   306	    return normalized or "arnold"
   307
   308
   309	# Panel route -> arnold dispatch agent id. The worker registers/dispatches under
   310	# this id. Only ``hermes`` is wired in the default dispatcher today; ``codex`` /
   311	# ``claude`` will raise LookupError until adapters are registered (Step B's
   312	# readiness gate keeps the panel from reaching them).
   313	_ROUTE_TO_AGENT_ID = {
   314	    "deepseek": "hermes",
   315	    "openrouter": "hermes",
   316	    "openai-codex": "codex",
   317	    "anthropic": "claude",
   318	}
   319
   320
   321	def _agent_id_for_route(route: str | None) -> str:
   322	    """Map a panel route name to the arnold dispatch agent id.
   323
   324	    Unlike :func:`_normalize_route`, this keeps anthropic/openai-codex distinct
   325	    so the worker can dispatch to the correct (eventual) adapter. ``auto`` and
   326	    bare ``arnold`` fall back to ``hermes`` (the only registered backend).
   327	    """
   328	    requested = (route or "").strip().lower()
   329	    if requested == "claude":
   330	        requested = "anthropic"
   331	    elif requested == "codex":
   332	        requested = "openai-codex"
   333	    return _ROUTE_TO_AGENT_ID.get(requested, "hermes")
   334
   335
   336	def _default_model_for_route(route: str, model: str | None) -> str:
   337	    if _is_real_model_override(model):
   338	        return _strip_provider_prefix(model, "openrouter")
   339	    if route == "openrouter":
   340	        return _strip_provider_prefix(_OPENROUTER_MODEL, "openrouter")
   341	    return _ARNOLD_MODEL
   342
   343
   344	def _is_real_model_override(model: str | None) -> bool:
   345	    """True when *model* is an actual provider model, not the panel contract id."""
   346	    normalized = (model or "").strip()
   347	    return bool(normalized and normalized != "agent-edit")
   348
   349
   350	def _runtime_model_for_route(route: str | None, model: str | None) -> str | None:
   351	    """Return the model slug to hand to the provider adapter.
   352
   353	    The browser/status contract historically used ``agent-edit`` as a product
   354	    label.  That is not a valid OpenRouter/Anthropic/Codex model id, so keep it
   355	    out of the provider seam and let the route resolve its real default.
   356	    """
   357	    # Explicit per-process force-override: when set, ignore the profile/judge
   358	    # model slug and route everything through this model (e.g. swapping the
   359	    # hermes backend to a non-DeepSeek OpenAI-compatible endpoint). No-op unset.
   360	    forced_model = os.getenv("VIBECOMFY_FORCE_MODEL")
   361	    if forced_model:
   362	        return forced_model
   363	    if _is_real_model_override(model):
   364	        return model
   365	    normalized_route = _normalize_route(route)
   366	    if normalized_route == "openrouter":
   367	        return _OPENROUTER_MODEL
   368	    if normalized_route in {"arnold", "anthropic", "openai-codex"}:
   369	        return _ARNOLD_MODEL
   370	    return None
   371
   372
   373	def _strip_provider_prefix(model: str, provider: str) -> str:
   374	    prefix = f"{provider}:"
   375	    return model.split(":", 1)[1] if model.lower().startswith(prefix) else model

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/runtime.py | nl -ba | sed -n '455,490p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 72ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   455	def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | None = None) -> dict[str, Any]:
   456	    """AIAgent constructor kwargs for a single, tool-free completion.
   457
   458	    Keyed off the resolved *dispatch agent id* (not the panel route). ``hermes``
   459	    is always configured for OpenRouter, including the legacy ``deepseek`` route
   460	    alias. For ``codex`` / ``claude`` the worker dispatches through the default
   461	    dispatcher and ignores ``agent_kwargs``, so we pass only the tool-free
   462	    single-shot flags.
   463	    """
   464	    common: dict[str, Any] = dict(
   465	        max_iterations=1,
   466	        enabled_toolsets=[],          # no tools: one-shot completion
   467	        save_trajectories=False,      # no trajectory files on disk
   468	        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
   469	        skip_memory=True,             # don't load/write the memory store
   470	        quiet_mode=True,
   471	    )
   472	    if agent_id == "hermes":
   473	        base_url = _base_url_for_route(route)
   474	        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
   475	        if _is_native_deepseek_endpoint(base_url):
   476	            # Native api.deepseek.com rejects OpenRouter-style ``deepseek/`` slugs
   477	            # with HTTP 400; normalize to the bare model name it accepts.
   478	            resolved_model = _normalize_native_deepseek_model(resolved_model)
   479	        else:
   480	            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
   481	        return dict(
   482	            model=resolved_model,
   483	            api_key=_hermes_credential_for(route, model),
   484	            base_url=base_url,
   485	            provider="openrouter",
   486	            max_tokens=_OPENROUTER_MAX_TOKENS,
   487	            **common,
   488	        )
   489	    # codex / claude -> default dispatcher resolves everything; kwargs unused.
   490	    return dict(**common)

exec
/bin/zsh -lc "git show e33f0260:tests/test_executor_contracts.py | nl -ba | sed -n '630,670p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 64ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   630	        assert d["message"] == "done"
   631	        assert d["delta"] == [{"op": "add"}]
   632
   633
   634	# ── Report ───────────────────────────────────────────────────────────────────
   635
   636
   637	class TestModelAttemptEvidence:
   638	    def test_preserves_requested_and_resolved_model_and_unknown_non_hermes_fields(self) -> None:
   639	        payload = ModelAttemptEvidence(
   640	            phase="reply",
   641	            attempt=2,
   642	            outcome="success",
   643	            requested_model="profile-alias",
   644	            resolved_model="provider/model-v2",
   645	            adapter="codex",
   646	            provider=None,  # type: ignore[arg-type]
   647	            transport=None,  # type: ignore[arg-type]
   648	            endpoint=None,  # type: ignore[arg-type]
   649	            finish_reason=None,  # type: ignore[arg-type]
   650	            token_usage={},
   651	            raw_response_preview="success content must be dropped",
   652	        ).to_dict()
   653
   654	        assert payload["requested_model"] == "profile-alias"
   655	        assert payload["resolved_model"] == "provider/model-v2"
   656	        assert payload["provider"] == "unknown"
   657	        assert payload["transport"] == "unknown"
   658	        assert payload["endpoint"] == "unknown"
   659	        assert payload["finish_reason"] == "unknown"
   660	        assert payload["token_usage"] == {
   661	            "prompt_tokens": "unknown",
   662	            "completion_tokens": "unknown",
   663	            "total_tokens": "unknown",
   664	        }
   665	        assert "raw_response_preview" not in payload
   666
   667
   668	class TestReport:
   669	    def test_default(self) -> None:
   670	        r = Report()

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/executor/contracts.py | nl -ba | sed -n '190,230p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   190	        )
   191
   192	    def to_dict(self) -> dict[str, Any]:
   193	        payload: dict[str, Any] = {
   194	            "phase": self.phase,
   195	            "attempt": self.attempt,
   196	            "outcome": self.outcome,
   197	            "failure_type": self.failure_type,
   198	            "requested_model": self.requested_model,
   199	            "resolved_model": self.resolved_model,
   200	            "adapter": self.adapter,
   201	            "provider": self.provider,
   202	            "transport": self.transport,
   203	            "endpoint": self.endpoint,
   204	            "finish_reason": self.finish_reason,
   205	            "token_usage": dict(self.token_usage),
   206	        }
   207	        if self.outcome == "failure" and self.raw_response_preview:
   208	            payload["raw_response_preview"] = self.raw_response_preview
   209	        return payload
   210
   211
   212	def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
   213	    """Normalize untrusted attempt mappings into the canonical serialized shape."""
   214	    if not isinstance(value, (list, tuple)):
   215	        return ()
   216	    attempts: list[dict[str, Any]] = []
   217	    for item in value:
   218	        if isinstance(item, ModelAttemptEvidence):
   219	            attempts.append(item.to_dict())
   220	        elif isinstance(item, Mapping):
   221	            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
   222	    return tuple(attempts)
   223
   224
   225	_NODE_TYPE_MARKER_RE = re.compile(
   226	    r"(?:class(?:_type|\s+type)?|node(?:\s+of)?(?:\s+type)?|of\s+type)\s*[:=]?\s*"
   227	    r"([A-Za-z_][A-Za-z0-9_.:-]*)",
   228	    re.IGNORECASE,
   229	)
   230	_NODE_TYPE_VERB_RE = re.compile(

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/executor/contracts.py | nl -ba | sed -n '2600,2630p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 63ms:
  2600	    report: Report = field(default_factory=Report)
  2601	    graph: dict[str, Any] | None = None
  2602	    reply: str | None = None
  2603	    failure_kind: str | None = None
  2604	    failure_stage: str | None = None
  2605	    failure_message: str | None = None
  2606
  2607	    @property
  2608	    def turn(self) -> AgentTurnResult:
  2609	        return AgentTurnResult.from_executor_result(self)
  2610
  2611	    def to_dict(self) -> dict[str, Any]:
  2612	        payload: dict[str, Any] = {
  2613	            "ok": self.ok,
  2614	            "report": self.report.to_dict(),
  2615	        }
  2616	        usage_payload = coerce_deepseek_usage(self.report.deepseek_usage)
  2617	        payload["deepseek_usage"] = usage_payload
  2618	        payload["model_attempts"] = [
  2619	            _thaw_jsonish(item) for item in self.report.model_attempts
  2620	        ]
  2621	        if self.report.deepseek_est_cost_usd is not None:
  2622	            payload["deepseek_est_cost_usd"] = float(self.report.deepseek_est_cost_usd)
  2623	        if isinstance(self.report.deepseek_cost_basis, str) and self.report.deepseek_cost_basis:
  2624	            payload["deepseek_cost_basis"] = self.report.deepseek_cost_basis
  2625	        # Propagate durable envelope fields from the implementation
  2626	        # response (SD1, SD2) so downstream consumers see session_id,
  2627	        # turn_id, hashes, outcome, apply_eligibility, change_details,
  2628	        # audit/artifact refs, gates, debug, and contract_version at
  2629	        # the top level.  Executor-owned fields (graph, message, route,
  2630	        # candidate, apply_eligible) take priority over any collisions.

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/agent/artifacts.py | nl -ba | sed -n '325,350p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   325	        "status": status,
   326	        "live": bool(request.get("live", True)),
   327	        "dry_run": bool(request.get("dry_run", False)),
   328	        "apply": bool(request.get("apply", False)),
   329	        "network": bool(request.get("network", True)),
   330	        "readiness": dict(readiness) if readiness else {},
   331	    }
   332	    _safe_write(output_dir / "flow_metadata.json", _redact(flow_metadata))
   333	    _append_manifest(manifest, "flow_metadata.json")
   334
   335	    report = _executor_report(result)
   336	    model_attempts = report.get("model_attempts")
   337	    if isinstance(model_attempts, (list, tuple)) and model_attempts:
   338	        _safe_write(
   339	            output_dir / "model_attempts.json",
   340	            {"attempts": _redact(model_attempts)},
   341	        )
   342	        _append_manifest(manifest, "model_attempts.json")
   343	    classification = report.get("plan")
   344	    if isinstance(classification, Mapping):
   345	        classification_payload = _redact(classification)
   346	        _safe_write(output_dir / "classification.json", classification_payload)
   347	        _append_manifest(manifest, "classification.json")
   348
   349	        research = report.get("research")
   350	        research_payload: dict[str, Any] | None = None

exec
/bin/zsh -lc "git show e33f0260:.oracle/tasklist.md | nl -ba | sed -n '300,320p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 71ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   300	1. Add regressions for:
   301	   - catalog output name absent from the working node’s outputs;
   302	   - schema-derived source index out of bounds;
   303	   - add-node link resolution;
   304	   - unknown target input;
   305	   - valid named multi-input/output links;
   306	   - the late `Missing stable link from port` signature.
   307	2. Make working-graph ports authoritative during endpoint resolution. Schema may validate or enrich but cannot return a slot absent from the node.
   308	3. Add one shared pre-mutation endpoint invariant for upsert-link and add-node links.
   309	4. Bounds-check source slots before `_apply_upsert_link`.
   310	5. Remove synthetic input fabrication for unknown target names.
   311	   - Legitimate dynamic inputs require an explicit node/schema contract.
   312	6. Define ONE shared, concrete dynamic-port contract covering the verified node families (count-driven: `ImageConcatMulti` `image_N`, `LTXVImgToVideoInplaceKJ` `num_images.*`, `SimpleCalculator` `input_N`, `LTXVAddGuide` `guide_N`, `SimpleCalculatorKJ` payload vars, `in_N` fixed slots; helpers/proxies: `Reroute`, `GetNode`, `SetNode`, `PrimitiveNode`; dynamic `INPUT_TYPES` custom nodes) — a single predicate used by resolution, mutation, and projection (not a duplicated list at three sites). A port is valid iff present in `node["outputs"]`/`["inputs"]`, or the class matches the dynamic contract AND the schema-fallback slot is bounds-verified before link write.
   313	7. Materialize declared ports during node construction, not opportunistically during link application (materialize-then-validate: build schema input sockets into `inputs` at `ui.py:1325` symmetric with outputs, then keep write-time bounds checks but emit diagnostics instead of silent returns at `apply_links.py:303/314`).
   314	8. Resolve projection ports by canonical name with a validated index fallback.
   315	9. Return typed pre-apply diagnostics instead of creating malformed links and failing during projection.
   316
   317	### Acceptance
   318
   319	- Malformed endpoints fail before mutation and roll back cleanly.
   320	- No undeclared synthetic ports are created.

exec
/bin/zsh -lc 'git diff --unified=6 16d80bbe..e33f0260 -- .oracle/tasklist.md' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/.oracle/tasklist.md b/.oracle/tasklist.md
index 6b0a6c4d..15d4b28b 100644
--- a/.oracle/tasklist.md
+++ b/.oracle/tasklist.md
@@ -308,14 +308,14 @@ Prompt/model quality work remains cut. This batch replaces it with the verified
 3. Add one shared pre-mutation endpoint invariant for upsert-link and add-node links.
 4. Bounds-check source slots before `_apply_upsert_link`.
 5. Remove synthetic input fabrication for unknown target names.
    - Legitimate dynamic inputs require an explicit node/schema contract.
 6. Define ONE shared, concrete dynamic-port contract covering the verified node families (count-driven: `ImageConcatMulti` `image_N`, `LTXVImgToVideoInplaceKJ` `num_images.*`, `SimpleCalculator` `input_N`, `LTXVAddGuide` `guide_N`, `SimpleCalculatorKJ` payload vars, `in_N` fixed slots; helpers/proxies: `Reroute`, `GetNode`, `SetNode`, `PrimitiveNode`; dynamic `INPUT_TYPES` custom nodes) — a single predicate used by resolution, mutation, and projection (not a duplicated list at three sites). A port is valid iff present in `node["outputs"]`/`["inputs"]`, or the class matches the dynamic contract AND the schema-fallback slot is bounds-verified before link write.
 7. Materialize declared ports during node construction, not opportunistically during link application (materialize-then-validate: build schema input sockets into `inputs` at `ui.py:1325` symmetric with outputs, then keep write-time bounds checks but emit diagnostics instead of silent returns at `apply_links.py:303/314`).
-7. Resolve projection ports by canonical name with a validated index fallback.
-8. Return typed pre-apply diagnostics instead of creating malformed links and failing during projection.
+8. Resolve projection ports by canonical name with a validated index fallback.
+9. Return typed pre-apply diagnostics instead of creating malformed links and failing during projection.

 ### Acceptance

 - Malformed endpoints fail before mutation and roll back cleanly.
 - No undeclared synthetic ports are created.
 - Valid named links project correctly despite serialized ordering differences.

exec
/bin/zsh -lc 'git diff --check 16d80bbe..e33f0260 2>&1 | wc -l && git diff --numstat 16d80bbe..e33f0260 -- .oracle/checkins/batch-G0R.md .oracle/tasklist.md .oracle/briefs/batch-B01.md' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "git log --format='%h %s' 16d80bbe..e33f0260" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
e33f0260 megado B01: unified model-attempt evidence contract (typed failures: empty/malformed/non-JSON/missing-field/timeout/capacity), success-path provenance preserved, fresh-transport retry only on typed empty+zero-tokens, redaction — 556 focused tests green
45415680 megado: record G0R oracle PASS (16d80bbe)
9d003159 megado: tasklist revision — B08 task numbering 7->8/9 (no content change; post-freeze revision recorded per protocol)

 succeeded in 18ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
39	0	.oracle/briefs/batch-B01.md
5087	0	.oracle/checkins/batch-G0R.md
2	2	.oracle/tasklist.md

exec
/bin/zsh -lc "git diff --check 16d80bbe..e33f0260 2>&1 | rg -c 'trailing whitespace'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 29ms:
320

exec
/bin/zsh -lc "git show e33f0260:vibecomfy/comfy_nodes/agent/provider.py | nl -ba | sed -n '920,970p'; git show e33f0260:vibecomfy/comfy_nodes/agent/provider.py | nl -ba | sed -n '1260,1330p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   920
   921
   922	def _resolve_route_and_model(
   923	    route: str | None,
   924	    model: str | None,
   925	) -> tuple[AgentRouteDescriptor, str, str]:
   926	    route_descriptor = _resolve_agent_route(route)
   927	    selected_route = route_descriptor.normalized_route
   928	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
   929	    return route_descriptor, selected_route, selected_model
   930
   931
   932	def _runtime_dispatch_route(route_descriptor: AgentRouteDescriptor, selected_route: str) -> str:
   933	    requested = route_descriptor.requested_route
   934	    if requested in {"anthropic", "openai-codex"}:
   935	        return requested
   936	    # Preserve an explicit OpenRouter selection through the runtime boundary.
   937	    # The runtime still uses the Hermes adapter internally, but the route name
   938	    # is the transport contract that pins endpoint and credential resolution.
   939	    if requested == "openrouter":
   940	        return "openrouter"
   941	    if requested == "deepseek":
   942	        return "deepseek"
   943	    return selected_route
   944
   945
   946	def _provider_status_metadata(
   947	    *,
   948	    route_descriptor: AgentRouteDescriptor,
   949	    selected_route: str,
   950	    selected_model: str,
   951	    provider_available: bool,
   952	) -> dict[str, Any]:
   953	    return {
   954	        "route": selected_route,
   955	        "requested_route": route_descriptor.requested_route,
   956	        "model": selected_model,
   957	        "provider": "arnold",
   958	        "provider_available": provider_available,
   959	        "contract_version": AGENT_EDIT_TURN_CONTRACT_VERSION,
   960	        "route_metadata": route_descriptor.to_dict(),
   961	        "route_options": _supported_browser_route_options(),
   962	        "credential_presence": _credential_presence(),
   963	        "legacy_deepseek_fallback_enabled": False,
   964	    }
   965
   966
   967	def _normalize_readiness_payload(
   968	    payload: Mapping[str, Any] | None,
   969	    *,
   970	    provider_available: bool,
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
  1260	        raise MalformedModelJSON(str(exc), parse_reason=exc.code) from exc
  1261
  1262
  1263	def _normalize_batch_response(
  1264	    response: Any,
  1265	    *,
  1266	    route: str,
  1267	    model: str | None,
  1268	    audit_metadata: Mapping[str, Any] | None = None,
  1269	) -> BatchTurnResult:
  1270	    """Normalize a raw runtime response into a :class:`BatchTurnResult`.
  1271
  1272	    Extracts the ```batch fenced block and surrounding prose via
  1273	    :func:`extract_batch_fence`.  The runtime may return a string (the raw
  1274	    model response) or a mapping with a ``content`` key.
  1275	    """
  1276	    if isinstance(response, BatchTurnResult):
  1277	        return response
  1278	    merged_audit = _audit_with_runtime_attempts(audit_metadata, response)
  1279	    if isinstance(response, str):
  1280	        text = response
  1281	    elif isinstance(response, Mapping):
  1282	        payload = dict(response)
  1283	        content = payload.get("content")
  1284	        if isinstance(content, str) and "batch" not in payload:
  1285	            text = content
  1286	        elif isinstance(payload.get("batch"), str):
  1287	            batch_code = payload["batch"]
  1288	            message = normalize_user_markdown_message(payload.get("message", ""))
  1289	            return BatchTurnResult(
  1290	                batch=batch_code,
  1291	                message=message,
  1292	                route=route,
  1293	                model=model,
  1294	                audit_metadata=merged_audit,
  1295	            )
  1296	        else:
  1297	            text = str(response)
  1298	    else:
  1299	        raise MalformedModelJSON("Agent response must be a string or object.")
  1300	    if not text.strip():
  1301	        raise MalformedModelJSON(
  1302	            "Agent batch_repl response was empty. Expected exactly one ```batch fenced block.",
  1303	            raw_response=text,
  1304	            parse_reason="empty",
  1305	        )
  1306	    batch_code, prose = extract_batch_fence(text)
  1307	    # Preserve prose as-is (possibly empty); the backend synthesizer
  1308	    # (_synthesize_batch_repl_message) owns final message filling.
  1309	    message = prose.strip()
  1310	    return BatchTurnResult(
  1311	        batch=batch_code,
  1312	        message=message,
  1313	        route=route,
  1314	        model=model,
  1315	        audit_metadata=merged_audit,
  1316	    )
  1317
  1318
  1319	def _call_batch_runtime(
  1320	    runtime: Any,
  1321	    *,
  1322	    task: str,
  1323	    messages: list[dict[str, str]],
  1324	    route: str,
  1325	    model: str | None,
  1326	    effort: str | None = None,
  1327	) -> Any:
  1328	    """Call the Arnold/Hermes runtime for a batch-REPL turn."""
  1329	    run_agent_turn_batch_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn_batch", None)
  1330	    if callable(run_agent_turn_batch_fn):

codex
B01 CHECKPOINT VERDICT: FAIL — canonical contract exists, but parallel evidence, provenance/retry defects, redaction bypasses, unsupported-route inference, and a dirty/out-of-scope diff violate acceptance.

All line references are against `e33f0260`; concurrent working-tree changes were excluded.

1. **Unified attempt contract — FAIL.** `ModelAttemptEvidence` is defined once in `vibecomfy/executor/contracts.py:122-209` and normalized via `coerce_model_attempts` at `:212-222`. However, `Report` still exposes both canonical `model_attempts` and legacy `model_response` (`:2302-2309`, serialized at `:2354-2358`). `vibecomfy/executor/core.py:105-128,223-238` retains a second parse-evidence vocabulary and can emit legacy `{"turns":[{"error":...}]}`. This is a parallel persisted format.

2. **Failure taxonomy — PASS.** The closed set at `vibecomfy/executor/contracts.py:36-43` distinctly represents `empty_response`, `malformed_json`, `non_json_content`, `missing_required_fields`, `timeout`, and `provider_failure`. Serialization preserves valid values distinctly (`:145-155,192-209`), with six structural regression cases at `tests/test_agent_runtime_adapter.py:402-418`.

3. **Success provenance — FAIL.** Normal classify, reply, and batch calls carry the required fields through worker, runtime, provider audit, executor report, and `model_attempts.json`. But provider-level batch retries append worker-local attempts without renumbering (`vibecomfy/comfy_nodes/agent/provider.py:1492-1505`), producing `[attempt=1, attempt=1]` after a retry rather than `[1,2]`. Attempt provenance is therefore not truthful across all retries.

4. **Retry policy — FAIL.** Runtime/provider/harness predicates are typed and wording-independent, and malformed non-empty output remains non-retryable/product failure (`runtime.py:493-505,605-617`; `provider.py:1416-1425,1491-1498`; `runner.py:221-272`). However, `worker.py:156-163` accepts zero-filled usage even when `n_calls == 0`; `_dispatch_turn` supplies that normalized zero usage. Consequently unobserved usage can appear as `completion_tokens=0` and authorize retry, violating the requirement for *observed* zero tokens.

5. **Redaction — FAIL.** The fixture at `tests/test_headless_agent_artifacts.py:250-322` covers Bearer tokens, endpoint credentials, API-key/signature parameters, and secret URL parameters. It misses two bypasses:

   - `contracts.py:47-50,84-97` turns `Authorization: Basic dXNlcjpwYXNz` into `Authorization: <redacted> dXNlcjpwYXNz`, leaving the credential.
   - `vibecomfy/agent/artifacts.py:102-116` raw-copies an entire JSON/JSONL artifact after any parse error, allowing malformed artifacts containing secrets to persist verbatim.

6. **Unsupported routes — FAIL.** Non-Hermes provider/transport fields nominally become `unknown` (`worker.py:124-140`), but unsupported routing still infers provenance. `provider.py:901-905` preserves arbitrary routes, while `runtime.py:321-333` silently maps any unmapped route to Hermes and `:472-486` assigns OpenRouter provenance. Unsupported non-Hermes paths also receive an inferred `_ARNOLD_MODEL` at `runtime.py:350-370`. The existing test only manually constructs an unknown-valued contract (`tests/test_executor_contracts.py:637-665`) and does not exercise route plumbing.

7. **Scope and diff hygiene — FAIL.** `git diff --check 16d80bbe..e33f0260` reports 320 trailing-whitespace violations in `.oracle/checkins/batch-G0R.md`. The range also contains unrelated work:

   - `.oracle/checkins/batch-G0R.md`: 5,087 added lines from prior checkpoint commit `45415680`.
   - `.oracle/tasklist.md:314-315`: unrelated B08 numbering revision from `9d003159`.

   The narrower B01-only range is clean, but the mandated checkpoint range is not.

8. **Focused verification — NOT REPRODUCED.** The exact seven-file suite was attempted with `-p no:rerunfailures`, but pytest exited before collection because the read-only sandbox had no usable temporary directory. The orchestrator’s reported `556 passed` result therefore remains external evidence; live runs were not attempted.

Issue list:

- `vibecomfy/executor/core.py:105-128,223-238` and `vibecomfy/executor/contracts.py:2302-2309`: migrate/remove legacy parallel model-response evidence.
- `vibecomfy/comfy_nodes/agent/provider.py:1492-1505`: assign truthful monotonically increasing batch attempt numbers.
- `vibecomfy/comfy_nodes/agent/worker.py:156-163`: distinguish observed zero tokens from zero-filled unavailable usage.
- `vibecomfy/executor/contracts.py:47-50,84-97`: redact complete Authorization header values for every scheme.
- `vibecomfy/agent/artifacts.py:102-116`: never raw-copy parse-failed model artifacts; sanitize or omit them and add malformed JSON/JSONL regressions.
- `vibecomfy/comfy_nodes/agent/provider.py:901-905` and `runtime.py:321-333,350-370,472-486`: serialize unsupported-route provenance as `unknown` without fallback inference.
- `.oracle/checkins/batch-G0R.md:917` onward and `.oracle/tasklist.md:314-315`: clean whitespace and reconcile unrelated range contents.
tokens used
275,986
B01 CHECKPOINT VERDICT: FAIL — canonical contract exists, but parallel evidence, provenance/retry defects, redaction bypasses, unsupported-route inference, and a dirty/out-of-scope diff violate acceptance.

All line references are against `e33f0260`; concurrent working-tree changes were excluded.

1. **Unified attempt contract — FAIL.** `ModelAttemptEvidence` is defined once in `vibecomfy/executor/contracts.py:122-209` and normalized via `coerce_model_attempts` at `:212-222`. However, `Report` still exposes both canonical `model_attempts` and legacy `model_response` (`:2302-2309`, serialized at `:2354-2358`). `vibecomfy/executor/core.py:105-128,223-238` retains a second parse-evidence vocabulary and can emit legacy `{"turns":[{"error":...}]}`. This is a parallel persisted format.

2. **Failure taxonomy — PASS.** The closed set at `vibecomfy/executor/contracts.py:36-43` distinctly represents `empty_response`, `malformed_json`, `non_json_content`, `missing_required_fields`, `timeout`, and `provider_failure`. Serialization preserves valid values distinctly (`:145-155,192-209`), with six structural regression cases at `tests/test_agent_runtime_adapter.py:402-418`.

3. **Success provenance — FAIL.** Normal classify, reply, and batch calls carry the required fields through worker, runtime, provider audit, executor report, and `model_attempts.json`. But provider-level batch retries append worker-local attempts without renumbering (`vibecomfy/comfy_nodes/agent/provider.py:1492-1505`), producing `[attempt=1, attempt=1]` after a retry rather than `[1,2]`. Attempt provenance is therefore not truthful across all retries.

4. **Retry policy — FAIL.** Runtime/provider/harness predicates are typed and wording-independent, and malformed non-empty output remains non-retryable/product failure (`runtime.py:493-505,605-617`; `provider.py:1416-1425,1491-1498`; `runner.py:221-272`). However, `worker.py:156-163` accepts zero-filled usage even when `n_calls == 0`; `_dispatch_turn` supplies that normalized zero usage. Consequently unobserved usage can appear as `completion_tokens=0` and authorize retry, violating the requirement for *observed* zero tokens.

5. **Redaction — FAIL.** The fixture at `tests/test_headless_agent_artifacts.py:250-322` covers Bearer tokens, endpoint credentials, API-key/signature parameters, and secret URL parameters. It misses two bypasses:

   - `contracts.py:47-50,84-97` turns `Authorization: Basic dXNlcjpwYXNz` into `Authorization: <redacted> dXNlcjpwYXNz`, leaving the credential.
   - `vibecomfy/agent/artifacts.py:102-116` raw-copies an entire JSON/JSONL artifact after any parse error, allowing malformed artifacts containing secrets to persist verbatim.

6. **Unsupported routes — FAIL.** Non-Hermes provider/transport fields nominally become `unknown` (`worker.py:124-140`), but unsupported routing still infers provenance. `provider.py:901-905` preserves arbitrary routes, while `runtime.py:321-333` silently maps any unmapped route to Hermes and `:472-486` assigns OpenRouter provenance. Unsupported non-Hermes paths also receive an inferred `_ARNOLD_MODEL` at `runtime.py:350-370`. The existing test only manually constructs an unknown-valued contract (`tests/test_executor_contracts.py:637-665`) and does not exercise route plumbing.

7. **Scope and diff hygiene — FAIL.** `git diff --check 16d80bbe..e33f0260` reports 320 trailing-whitespace violations in `.oracle/checkins/batch-G0R.md`. The range also contains unrelated work:

   - `.oracle/checkins/batch-G0R.md`: 5,087 added lines from prior checkpoint commit `45415680`.
   - `.oracle/tasklist.md:314-315`: unrelated B08 numbering revision from `9d003159`.

   The narrower B01-only range is clean, but the mandated checkpoint range is not.

8. **Focused verification — NOT REPRODUCED.** The exact seven-file suite was attempted with `-p no:rerunfailures`, but pytest exited before collection because the read-only sandbox had no usable temporary directory. The orchestrator’s reported `556 passed` result therefore remains external evidence; live runs were not attempted.

Issue list:

- `vibecomfy/executor/core.py:105-128,223-238` and `vibecomfy/executor/contracts.py:2302-2309`: migrate/remove legacy parallel model-response evidence.
- `vibecomfy/comfy_nodes/agent/provider.py:1492-1505`: assign truthful monotonically increasing batch attempt numbers.
- `vibecomfy/comfy_nodes/agent/worker.py:156-163`: distinguish observed zero tokens from zero-filled unavailable usage.
- `vibecomfy/executor/contracts.py:47-50,84-97`: redact complete Authorization header values for every scheme.
- `vibecomfy/agent/artifacts.py:102-116`: never raw-copy parse-failed model artifacts; sanitize or omit them and add malformed JSON/JSONL regressions.
- `vibecomfy/comfy_nodes/agent/provider.py:901-905` and `runtime.py:321-333,350-370,472-486`: serialize unsupported-route provenance as `unknown` without fallback inference.
- `.oracle/checkins/batch-G0R.md:917` onward and `.oracle/tasklist.md:314-315`: clean whitespace and reconcile unrelated range contents.
