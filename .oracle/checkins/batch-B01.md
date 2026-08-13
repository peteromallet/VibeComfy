Reading additional input from stdin...
2026-08-13T12:16:18.483337Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:18.483412Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:18.483422Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb0d-404d-7261-9a77-025a5d2b9be3
--------
user
# MEGADO CHECKPOINT — Batch B01 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the B01 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**B01 [HARD] — Typed failures and unified attempt provenance.** Tasks + acceptance from `.oracle/tasklist.md` (B01 section). The diff to review: `git diff 45415680..1bd1b04b` (G0R PASS SHA → B01 commit). The executor was GPT-5.6 Sol (workspace-write, 30-min clamp hit mid-verification; the orchestrator ran the focused suite to completion).

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
7. Scope: diff contains only B01-scope files; `git diff --check 45415680..1bd1b04b` clean.
8. Run the focused suite yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks); live runs skipped (orchestrator-phase).

## Output

First line: `B01 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–8) with evidence, and an issue list if FAIL (each with file:line + what to rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m applying the `megado` skill because this is an explicit MEGADO oracle checkpoint. I’ll inspect the exact B01 contract and diff read-only, independently run the permitted focused verification, and use a separate adversarial reviewer for a cross-check; no files will be modified.
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

2026-08-13T12:16:39.611000Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:39.611805Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:39.611824Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:44.068286Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:44.068342Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:16:44.068354Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
  → Read B01 acceptance criteria and map changed files
  • Audit contracts, provenance, retry policy, redaction, and unknown routes
  • Run diff hygiene and focused verification
  • Synthesize adversarial PASS/FAIL verdict with file:line evidence
exec
/bin/zsh -lc "git status --short --branch && git diff --stat 45415680..1bd1b04b && git diff --name-status 45415680..1bd1b04b && rg -n -A120 -B5 '"'^## B01|''^# B01|B01 '"\\[' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 33ms:
 .oracle/briefs/batch-B01-rework.md            |   38 +
 .oracle/briefs/batch-B01-rework2.md           |   26 +
 .oracle/briefs/batch-B01.md                   |   39 +
 .oracle/checkins/batch-B01.md                 | 7062 +++++++++++++++++++++++++
 tests/live_agentic_harness/adapter.py         |    1 +
 tests/live_agentic_harness/runner.py          |  131 +-
 tests/test_agent_runtime_adapter.py           |  237 +
 tests/test_executor_contracts.py              |   57 +
 tests/test_executor_flows.py                  |   40 +
 tests/test_headless_agent_artifacts.py        |  223 +
 tests/test_live_agentic_runner_persistence.py |  165 +-
 tests/test_runtime_worker_retry.py            |  134 +-
 vibecomfy/agent/artifacts.py                  |  133 +-
 vibecomfy/comfy_nodes/agent/provider.py       |  135 +-
 vibecomfy/comfy_nodes/agent/runtime.py        |  306 +-
 vibecomfy/comfy_nodes/agent/worker.py         |  132 +-
 vibecomfy/executor/agent_backend.py           |   71 +-
 vibecomfy/executor/contracts.py               |  234 +-
 vibecomfy/executor/core.py                    |  174 +-
 19 files changed, 8919 insertions(+), 419 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/briefs/batch-B01-rework.md
A	.oracle/briefs/batch-B01-rework2.md
A	.oracle/briefs/batch-B01.md
A	.oracle/checkins/batch-B01.md
M	tests/live_agentic_harness/adapter.py
M	tests/live_agentic_harness/runner.py
M	tests/test_agent_runtime_adapter.py
M	tests/test_executor_contracts.py
M	tests/test_executor_flows.py
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
138-### Tasks
139-
140-1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
141-2. Migrate all four verified provisional-first sites:
142-   - `_frag_research.py:874`;
143-   - `_frag_response_contract.py:793`;
144-   - `_frag_batch_loop.py:910`;
145-   - `edit_batch_repl.py:1115`.
146-3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
147-4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
148-5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
149-
150-### Acceptance
151-
152-- All seven sites are real-first.
153-- Session schema authority remains real-first across turns.
154-- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
155-- Invalid enum values are rejected before mutation for add and set.
156-- Missing local asset filenames remain warning-only.
157-
158-### Oracle checkpoint
159-
160-Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.
161-
162----
163-
164-## B03 — Canonical semantic pin comparison `[HARD]`
165-
166-### Tasks
167-
168-1. Add fixtures for:
169-   - flat Set/Get fan-out;
170-   - 1:1 reroute lowering;
171-   - loop-cloned consumer UIDs;
172-   - nested subgraphs;
173-   - multi-output nodes;
174-   - genuine removed, repointed, or orphaned consumers.
175-2. Replace raw UID-keyed multiset comparison with one canonical semantic-set helper:
176-   - preserve input/output port identity;
177-   - dedupe multiplicity;

exec
/bin/zsh -lc 'rg -n "Attempt|attempt_evidence|model_attempt|failure_type|failure_kind|empty_response|malformed|non_json|missing_required|capacity|resolved_model|requested_model|transport|endpoint|finish_reason|token_usage|raw_preview" vibecomfy tests/live_agentic_harness tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
tests/test_runtime_worker_retry.py:3:Only a canonical ``empty_response`` attempt with observed zero completion
tests/test_runtime_worker_retry.py:4:tokens may receive a fresh subprocess/transport. Timeouts, provider failures,
tests/test_runtime_worker_retry.py:5:and malformed non-empty content surface without retry.
tests/test_runtime_worker_retry.py:52:    *, outcome: str, failure_type: str | None = None, completion_tokens: int = 1
tests/test_runtime_worker_retry.py:58:        "failure_type": failure_type,
tests/test_runtime_worker_retry.py:59:        "requested_model": "requested-model",
tests/test_runtime_worker_retry.py:60:        "resolved_model": "resolved-model",
tests/test_runtime_worker_retry.py:63:        "transport": "openrouter",
tests/test_runtime_worker_retry.py:64:        "endpoint": "https://openrouter.ai/api/v1",
tests/test_runtime_worker_retry.py:65:        "finish_reason": "stop" if outcome == "success" else "unknown",
tests/test_runtime_worker_retry.py:66:        "token_usage": {
tests/test_runtime_worker_retry.py:82:    assert raised.value.model_attempts[0]["failure_type"] == "timeout"  # type: ignore[attr-defined]
tests/test_runtime_worker_retry.py:94:def test_untyped_transport_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
tests/test_runtime_worker_retry.py:111:        "model_attempts": [_attempt(outcome="failure", failure_type="provider_failure")],
tests/test_runtime_worker_retry.py:121:def test_typed_empty_zero_token_response_retries_on_fresh_transport(
tests/test_runtime_worker_retry.py:127:        "model_attempts": [
tests/test_runtime_worker_retry.py:130:                failure_type="empty_response",
tests/test_runtime_worker_retry.py:137:        "model_attempts": [_attempt(outcome="success")],
tests/test_runtime_worker_retry.py:144:    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]
tests/test_runtime_worker_retry.py:145:    assert result["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_runtime_worker_retry.py:146:    assert "raw_response_preview" not in result["model_attempts"][1]
tests/test_runtime_worker_retry.py:155:        "model_attempts": [
tests/test_runtime_worker_retry.py:156:            _attempt(outcome="failure", failure_type="empty_response", completion_tokens=2)
tests/test_runtime_worker_retry.py:163:    assert result["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_runtime_worker_retry.py:171:        outcome="failure", failure_type="empty_response", completion_tokens=0
tests/test_runtime_worker_retry.py:173:    unavailable["token_usage"] = {}
tests/test_runtime_worker_retry.py:174:    first = {"error": "empty", "model_attempts": [unavailable]}
tests/test_runtime_worker_retry.py:179:    assert result["model_attempts"][0]["token_usage"]["completion_tokens"] == "unknown"
tests/test_live_agentic_runner_persistence.py:26:        "model_attempts": [],
tests/test_live_agentic_runner_persistence.py:30:def _failed_attempt(failure_type: str, *, completion_tokens: int = 0) -> dict:
tests/test_live_agentic_runner_persistence.py:35:        "failure_type": failure_type,
tests/test_live_agentic_runner_persistence.py:36:        "requested_model": "requested",
tests/test_live_agentic_runner_persistence.py:37:        "resolved_model": "resolved",
tests/test_live_agentic_runner_persistence.py:40:        "transport": "openrouter",
tests/test_live_agentic_runner_persistence.py:41:        "endpoint": "https://openrouter.ai/api/v1",
tests/test_live_agentic_runner_persistence.py:42:        "finish_reason": "unknown",
tests/test_live_agentic_runner_persistence.py:43:        "token_usage": {
tests/test_live_agentic_runner_persistence.py:141:def test_runner_types_provider_capacity_without_retry(
tests/test_live_agentic_runner_persistence.py:147:    scenario_path = scenarios_dir / "provider-capacity.json"
tests/test_live_agentic_runner_persistence.py:149:        json.dumps({"id": "provider-capacity", "query": "do it"}),
tests/test_live_agentic_runner_persistence.py:160:        output_dir = tmp_path / "out" / tag / "provider-capacity"
tests/test_live_agentic_runner_persistence.py:162:            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
tests/test_live_agentic_runner_persistence.py:171:                    "model_attempts": [_failed_attempt("provider_failure")],
tests/test_live_agentic_runner_persistence.py:193:            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
tests/test_live_agentic_runner_persistence.py:215:    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
tests/test_live_agentic_runner_persistence.py:239:            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
tests/test_live_agentic_runner_persistence.py:256:    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:257:    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_live_agentic_runner_persistence.py:261:def test_runner_keeps_malformed_nonempty_as_product_failure(
tests/test_live_agentic_runner_persistence.py:267:    scenario_path = scenarios_dir / "malformed.json"
tests/test_live_agentic_runner_persistence.py:268:    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
tests/test_live_agentic_runner_persistence.py:276:        payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
tests/test_live_agentic_runner_persistence.py:277:        payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
tests/test_live_agentic_runner_persistence.py:279:        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
tests/test_live_agentic_runner_persistence.py:300:def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
tests/test_live_agentic_runner_persistence.py:319:                "model_attempts": [_failed_attempt("provider_failure")],
tests/test_live_agentic_runner_persistence.py:344:    assert scenario["failure_class"] == "infra_provider_capacity"
tests/test_live_agentic_runner_persistence.py:458:def test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed() -> None:
tests/test_live_agentic_runner_persistence.py:461:    Canonical ``malformed_json`` evidence with zero tokens is NOT retryable even
tests/test_live_agentic_runner_persistence.py:462:    when the summary inherited ``failure_class=infra_empty_response`` and
tests/test_live_agentic_runner_persistence.py:466:    summary["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=0)]
tests/test_live_agentic_runner_persistence.py:467:    summary["failure_class"] = "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:470:    summary["guard"]["failure_class"] = "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:484:    """Canonical empty_response + observed zero tokens is retryable regardless of flags."""
tests/test_live_agentic_runner_persistence.py:486:    summary["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
tests/test_live_agentic_runner_persistence.py:490:    assert _provider_infra_failure_class(summary) == "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:492:    assert summary["failure_class"] == "infra_empty_response"
tests/test_headless_agent_artifacts.py:206:        "model_attempts.json": False,
tests/test_headless_agent_artifacts.py:241:        "model_attempts.json": False,
tests/test_headless_agent_artifacts.py:250:def test_malformed_json_artifact_body_is_omitted(tmp_path: Path) -> None:
tests/test_headless_agent_artifacts.py:251:    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "malformed-json"
tests/test_headless_agent_artifacts.py:254:    secret = "sk-malformed-json-secret"
tests/test_headless_agent_artifacts.py:276:def test_malformed_jsonl_artifact_body_is_omitted(tmp_path: Path) -> None:
tests/test_headless_agent_artifacts.py:277:    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "malformed-jsonl"
tests/test_headless_agent_artifacts.py:306:def test_model_attempt_artifact_is_canonical_and_redacts_secrets(tmp_path: Path) -> None:
tests/test_headless_agent_artifacts.py:310:            model_attempts=(
tests/test_headless_agent_artifacts.py:315:                    "failure_type": "malformed_json",
tests/test_headless_agent_artifacts.py:316:                    "requested_model": "requested-model",
tests/test_headless_agent_artifacts.py:317:                    "resolved_model": "resolved-model",
tests/test_headless_agent_artifacts.py:320:                    "transport": "openrouter",
tests/test_headless_agent_artifacts.py:321:                    "endpoint": (
tests/test_headless_agent_artifacts.py:325:                    "finish_reason": "stop",
tests/test_headless_agent_artifacts.py:326:                    "token_usage": {
tests/test_headless_agent_artifacts.py:340:                    "requested_model": "requested-model",
tests/test_headless_agent_artifacts.py:341:                    "resolved_model": "resolved-model",
tests/test_headless_agent_artifacts.py:344:                    "transport": "unknown",
tests/test_headless_agent_artifacts.py:345:                    "endpoint": "unknown",
tests/test_headless_agent_artifacts.py:346:                    "finish_reason": "unknown",
tests/test_headless_agent_artifacts.py:347:                    "token_usage": {},
tests/test_headless_agent_artifacts.py:363:    assert "model_attempts.json" in manifest["manifest"]
tests/test_headless_agent_artifacts.py:364:    assert manifest["optional_model_artifacts"]["model_attempts.json"] is True
tests/test_headless_agent_artifacts.py:365:    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
tests/test_headless_agent_artifacts.py:366:    assert attempts[0]["endpoint"] == "https://openrouter.ai/api/v1"
tests/test_agent_runtime_adapter.py:31:def test_explicit_openrouter_route_cannot_be_hijacked_by_generic_endpoint_or_key_overrides(
tests/test_agent_runtime_adapter.py:78:    attempt = worker_result["model_attempts"][0]
tests/test_agent_runtime_adapter.py:79:    assert attempt["requested_model"] == "agent-edit"
tests/test_agent_runtime_adapter.py:80:    assert attempt["resolved_model"] == "unknown"
tests/test_agent_runtime_adapter.py:83:    assert attempt["transport"] == "unknown"
tests/test_agent_runtime_adapter.py:84:    assert attempt["endpoint"] == "unknown"
tests/test_agent_runtime_adapter.py:243:    assert request.resolved_model == "gpt-5.6-luna"
tests/test_agent_runtime_adapter.py:437:        (ValueError("empty"), "", "empty_response"),
tests/test_agent_runtime_adapter.py:438:        (json.JSONDecodeError("bad", "{bad", 1), "{bad", "malformed_json"),
tests/test_agent_runtime_adapter.py:439:        (json.JSONDecodeError("bad", "plain prose", 0), "plain prose", "non_json_content"),
tests/test_agent_runtime_adapter.py:440:        (ValueError("must include field reply"), '{"other":"x"}', "missing_required_fields"),
tests/test_agent_runtime_adapter.py:442:        (RuntimeError("capacity"), None, "provider_failure"),
tests/test_agent_runtime_adapter.py:450:    assert worker._model_attempt_failure_type(exc, raw) == expected
tests/test_agent_runtime_adapter.py:456:        "requested_model": "requested",
tests/test_agent_runtime_adapter.py:472:    unavailable = worker._model_attempt(
tests/test_agent_runtime_adapter.py:477:        failure_type="empty_response",
tests/test_agent_runtime_adapter.py:479:    observed = worker._model_attempt(
tests/test_agent_runtime_adapter.py:484:        failure_type="empty_response",
tests/test_agent_runtime_adapter.py:487:    assert unavailable["token_usage"]["completion_tokens"] == "unknown"
tests/test_agent_runtime_adapter.py:488:    assert observed["token_usage"]["completion_tokens"] == 0
tests/test_agent_runtime_adapter.py:496:        "failure_type": None,
tests/test_agent_runtime_adapter.py:497:        "requested_model": "openrouter:requested/model",
tests/test_agent_runtime_adapter.py:498:        "resolved_model": "resolved/model",
tests/test_agent_runtime_adapter.py:501:        "transport": "openrouter",
tests/test_agent_runtime_adapter.py:502:        "endpoint": "https://openrouter.ai/api/v1",
tests/test_agent_runtime_adapter.py:503:        "finish_reason": "stop",
tests/test_agent_runtime_adapter.py:504:        "token_usage": {
tests/test_agent_runtime_adapter.py:519:        base = {"model_attempts": [attempt], "deepseek_usage": attempt["token_usage"]}
tests/test_agent_runtime_adapter.py:539:        assert result["model_attempts"] == [attempt]
tests/test_agent_runtime_adapter.py:540:        assert result["deepseek_usage"] == attempt["token_usage"]
tests/test_agent_runtime_adapter.py:548:            "model_attempts": [attempt],
tests/test_agent_runtime_adapter.py:549:            "deepseek_usage": attempt["token_usage"],
tests/test_agent_runtime_adapter.py:556:    assert result.audit_metadata["model_attempts"] == [attempt]
tests/test_agent_runtime_adapter.py:557:    assert result.audit_metadata["deepseek_usage"] == attempt["token_usage"]
tests/test_agent_runtime_adapter.py:564:    first_a = {**_canonical_success_attempt(), "outcome": "failure", "failure_type": "provider_failure"}
tests/test_agent_runtime_adapter.py:568:        "token_usage": {
tests/test_agent_runtime_adapter.py:582:                return {"content": "", "model_attempts": [first_a, first_b]}
tests/test_agent_runtime_adapter.py:585:                "model_attempts": [second],
tests/test_agent_runtime_adapter.py:597:    attempts = result.audit_metadata["model_attempts"]
tests/test_agent_runtime_adapter.py:600:    assert attempts[1]["failure_type"] == "empty_response"
tests/test_agent_runtime_adapter.py:618:        return {"content": content, "json": json.loads(content), "model_attempts": [attempt]}
tests/test_agent_runtime_adapter.py:621:    token = runtime.begin_model_attempt_capture()
tests/test_agent_runtime_adapter.py:630:        attempts = runtime.snapshot_model_attempt_capture()
tests/test_agent_runtime_adapter.py:632:        runtime.end_model_attempt_capture(token)
tests/test_executor_flows.py:1349:            failure_kind="provider_error",
tests/test_executor_flows.py:1644:        assert result.failure_kind is not None
tests/test_executor_flows.py:1713:        assert result.failure_kind == "ProviderError"
tests/test_executor_flows.py:1717:    def test_classify_failure_persists_only_canonical_model_attempts(
tests/test_executor_flows.py:1726:            "failure_type": "malformed_json",
tests/test_executor_flows.py:1727:            "requested_model": "requested",
tests/test_executor_flows.py:1728:            "resolved_model": "resolved",
tests/test_executor_flows.py:1731:            "transport": "openrouter",
tests/test_executor_flows.py:1732:            "endpoint": "https://openrouter.ai/api/v1",
tests/test_executor_flows.py:1733:            "finish_reason": "stop",
tests/test_executor_flows.py:1734:            "token_usage": {
tests/test_executor_flows.py:1742:        error.model_attempts = [attempt]  # type: ignore[attr-defined]
tests/test_executor_flows.py:1750:        assert executor_report["model_attempts"] == [attempt]
tests/test_executor_flows.py:1770:        assert result.failure_kind == "ProviderError"
tests/test_executor_contracts.py:3:Covers valid classify/reply JSON, malformed JSON, optional graph handling,
tests/test_executor_contracts.py:30:    ModelAttemptEvidence,
tests/test_executor_contracts.py:638:class TestModelAttemptEvidence:
tests/test_executor_contracts.py:639:    def test_preserves_requested_and_resolved_model_and_unknown_non_hermes_fields(self) -> None:
tests/test_executor_contracts.py:640:        payload = ModelAttemptEvidence(
tests/test_executor_contracts.py:644:            requested_model="profile-alias",
tests/test_executor_contracts.py:645:            resolved_model="provider/model-v2",
tests/test_executor_contracts.py:648:            transport=None,  # type: ignore[arg-type]
tests/test_executor_contracts.py:649:            endpoint=None,  # type: ignore[arg-type]
tests/test_executor_contracts.py:650:            finish_reason=None,  # type: ignore[arg-type]
tests/test_executor_contracts.py:651:            token_usage={},
tests/test_executor_contracts.py:655:        assert payload["requested_model"] == "profile-alias"
tests/test_executor_contracts.py:656:        assert payload["resolved_model"] == "provider/model-v2"
tests/test_executor_contracts.py:658:        assert payload["transport"] == "unknown"
tests/test_executor_contracts.py:659:        assert payload["endpoint"] == "unknown"
tests/test_executor_contracts.py:660:        assert payload["finish_reason"] == "unknown"
tests/test_executor_contracts.py:661:        assert payload["token_usage"] == {
tests/test_executor_contracts.py:706:        attempt = ModelAttemptEvidence(
tests/test_executor_contracts.py:709:            failure_type="malformed_json",
tests/test_executor_contracts.py:711:        report = Report(model_attempts=(attempt,))
tests/test_executor_contracts.py:715:        assert payload["model_attempts"] == [attempt]
tests/test_executor_contracts.py:871:        assert r.failure_kind == "ProviderError"
tests/test_executor_contracts.py:894:        assert "failure_kind" not in d
tests/test_executor_contracts.py:1027:        assert d["failure_kind"] == "TimeoutError"
tests/test_executor_contracts.py:1319:    def test_malformed_json_raises(self) -> None:
tests/test_executor_contracts.py:1662:    def test_malformed_json_raises(self) -> None:
tests/test_executor_contracts.py:2112:        assert d["failure_kind"] == "ProviderError"
tests/test_executor_contracts.py:3630:        assert gf.missing_required_inputs == ()
tests/test_executor_contracts.py:3646:        assert d["missing_required_inputs"] == []
tests/test_executor_contracts.py:3665:            missing_required_inputs=(
tests/test_executor_contracts.py:3682:        assert len(d["missing_required_inputs"]) == 1
tests/test_executor_contracts.py:3683:        assert d["missing_required_inputs"][0]["missing_input"] == "model"
tests/test_executor_contracts.py:3703:    def test_has_blockers_true_with_missing_required_inputs(self) -> None:
tests/test_executor_contracts.py:3704:        gf = GraphFacts(missing_required_inputs=({"node": "1", "missing": "model"},))
tests/test_executor_contracts.py:3740:            missing_required_inputs=(
tests/test_executor_contracts.py:3748:        assert len(gf.missing_required_inputs) == 1
tests/test_executor_contracts.py:3772:            missing_required_inputs=(),
tests/test_executor_contracts.py:3775:            absent_endpoint_nodes=("99",),
tests/test_executor_contracts.py:3784:        # Even though topology has dangling_links and absent_endpoint_nodes,
tests/test_executor_contracts.py:3786:        # that GraphFacts carries (socket_type_mismatches, missing_required_inputs,
tests/test_executor_contracts.py:3790:        assert gf.missing_required_inputs == ()
tests/live_agentic_harness/adapter.py:152:        "model_attempts": result.response.get("model_attempts", []),
tests/live_agentic_harness/runner.py:140:        "retryable_infra": failure_class == "infra_empty_response",
tests/live_agentic_harness/runner.py:189:        "model_attempts": summary.get("model_attempts", []),
tests/live_agentic_harness/runner.py:193:def _latest_failed_model_attempt(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
tests/live_agentic_harness/runner.py:194:    attempts = summary.get("model_attempts")
tests/live_agentic_harness/runner.py:208:    structured evidence of an empty/transport response; absence of the record is
tests/live_agentic_harness/runner.py:211:    attempt = _latest_failed_model_attempt(summary)
tests/live_agentic_harness/runner.py:212:    usage = attempt.get("token_usage") if isinstance(attempt, Mapping) else None
tests/live_agentic_harness/runner.py:223:    attempt = _latest_failed_model_attempt(summary)
tests/live_agentic_harness/runner.py:226:    failure_type = attempt.get("failure_type")
tests/live_agentic_harness/runner.py:227:    if failure_type == "empty_response" and _summary_completion_tokens(summary) == 0:
tests/live_agentic_harness/runner.py:228:        return "infra_empty_response"
tests/live_agentic_harness/runner.py:229:    if failure_type == "timeout":
tests/live_agentic_harness/runner.py:231:    if failure_type == "provider_failure":
tests/live_agentic_harness/runner.py:232:        return "infra_provider_capacity"
tests/live_agentic_harness/runner.py:239:    summary["retryable_infra"] = failure_class == "infra_empty_response"
tests/live_agentic_harness/runner.py:263:    re-derived from the canonical ``model_attempts`` evidence on the same
tests/live_agentic_harness/runner.py:264:    summary. A summary that previously persisted ``infra_empty_response`` (from
tests/live_agentic_harness/runner.py:266:    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
tests/live_agentic_harness/runner.py:269:        summary.get("failure_class") == "infra_empty_response"
tests/live_agentic_harness/runner.py:272:    if summary.get("failure_class") == "infra_empty_response":
tests/live_agentic_harness/runner.py:280:        if guard.get("failure_class") == "infra_empty_response":
tests/live_agentic_harness/runner.py:290:    canonical ``model_attempts`` evidence supports an infra class the summary is
tests/live_agentic_harness/runner.py:308:    The decision is the latest failed ``model_attempts`` entry's failure type
tests/live_agentic_harness/runner.py:316:    return _provider_infra_failure_class(summary) == "infra_empty_response"
tests/live_agentic_harness/assessor.py:40:# Soft capacity warnings: surfaced so humans see them, but not treated as hard
tests/live_agentic_harness/assessor.py:698:            # change_details.landed_operation_count.  Missing, malformed, or
vibecomfy/ingest/snapshot.py:61:    # Build id → uid map for resolving edge endpoints to stable keys.
vibecomfy/ingest/normalize.py:53:    # malformed; structural shape is established by the rich nodes mapping.
vibecomfy/ingest/normalize.py:439:    which nodes exist.  Any malformed or mixed entry raises ``ValueError``
vibecomfy/ingest/normalize.py:623:                f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
vibecomfy/contracts/RUNTIME_CONTRACT.md:37:Non-JSON transforms are explicitly out of scope: no image, latent, tensor, or conditioning objects may be returned or processed through the runtime path. The subprocess JSON protocol cannot safely transport ComfyUI internal objects in this sprint.
vibecomfy/contracts/RUNTIME_CONTRACT.md:45:1. Runtime contract validates (malformed/schema-less contracts fail before queue).
vibecomfy/node_packs/_install.py:683:    # Attempt to read sentinel payload.
vibecomfy/comfy_nodes/agent/routes.py:805:    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - local ComfyUI endpoint.
vibecomfy/comfy_nodes/agent/routes.py:1278:        "endpoint": "/vibecomfy/agent-edit/rebaseline",
vibecomfy/contracts/ir.py:14:COMPILED_EDGE_ENDPOINT_RESOLVED: Final[str] = "ir.compile.edge_endpoint_resolved"
vibecomfy/contracts/ir.py:62:        guarantee="Every compiled edge endpoint resolves to a node present in the compiled prompt.",
vibecomfy/comfy_nodes/agent/runtime_code.py:111:    passthrough_on_non_json: bool = False,
vibecomfy/comfy_nodes/agent/runtime_code.py:131:            "passthrough_on_non_json": passthrough_on_non_json,
vibecomfy/comfy_nodes/agent/runtime_code.py:193:    resolve to ``"untrusted_source"`` so untagged or malformed dynamic code never
vibecomfy/comfy_nodes/agent/runtime_code.py:470:        raise RuntimeCodeExecutionError("runtime_protocol_non_json", "Runtime code worker emitted non-JSON output.") from exc
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
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:261:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:304:                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:393:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/porting/resolution.py:231:    """Resolved link endpoint from ResolutionContext.resolve_{source,target}_endpoint.
vibecomfy/porting/resolution.py:559:    # -- endpoint resolution ---------------------------------------------------
vibecomfy/porting/resolution.py:561:    def resolve_source_endpoint(
vibecomfy/porting/resolution.py:704:    def resolve_target_endpoint(
vibecomfy/porting/resolution.py:714:        missing but the field exists in schema, the endpoint is valid (D3
vibecomfy/workflow.py:581:                f"{operation}: malformed source ref {ref!r}; expected 'node_id' or 'node_id.output_slot'"
vibecomfy/workflow.py:591:            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
vibecomfy/workflow.py:594:            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
vibecomfy/workflow.py:1290:                "compiled_edge_missing_endpoint",
vibecomfy/workflow.py:1310:                "compiled_edge_missing_endpoint",
vibecomfy/workflow.py:1353:            "compiled_edge_missing_endpoint",
vibecomfy/workflow.py:1371:                "compiled_edge_missing_endpoint",
vibecomfy/commands/nodes.py:73:        print("to_input is required when checking a concrete node endpoint", file=sys.stderr)
vibecomfy/commands/nodes.py:284:        "endpoint": resolution.endpoint,
vibecomfy/nodes/kjnodes.py:7115:    Attempt to implement https://github.com/agwmon/self-refine-video, for testing only, MAY NOT WORK AS INTENDED.
vibecomfy/porting/emit/ui.py:2782:    - **Link endpoints exist.** Every ``links[]`` entry's ``from_node``/``to_node``
vibecomfy/porting/emit/ui.py:2796:    # 1) Link endpoints (node + slot) exist.
vibecomfy/nodes/ltxvideo.py:2075:    Selects a range of frames from the video latent. start_index and end_index define a closed interval (inclusive of both endpoints).
vibecomfy/executor/graph_inspection.py:524:    # Build undirected adjacency, skipping edges with missing endpoints
vibecomfy/executor/profile_data/openrouter.toml:4:# runtime enforces OpenRouter's canonical endpoint and OPENROUTER_API_KEY for
vibecomfy/executor/revision_evidence.py:90:    # Stringified view of node ids for type-tolerant endpoint membership.
vibecomfy/executor/revision_evidence.py:92:    # with str endpoint refs inside ``links`` (e.g. ``[3, "1", 0, "3", 0]``).
vibecomfy/executor/revision_evidence.py:97:    # Str-keyed lookup mirrors so edge endpoint refs (which may be str or int)
vibecomfy/executor/revision_evidence.py:119:    absent_endpoint_nodes: list[str] = []
vibecomfy/executor/revision_evidence.py:120:    seen_endpoints: set[int | str] = set()
vibecomfy/executor/revision_evidence.py:122:    # Collect all endpoint node ids referenced by edges.
vibecomfy/executor/revision_evidence.py:123:    edge_endpoint_ids: set[int | str] = set()
vibecomfy/executor/revision_evidence.py:136:        edge_endpoint_ids.add(edge.origin_node)
vibecomfy/executor/revision_evidence.py:137:        edge_endpoint_ids.add(edge.target_node)
vibecomfy/executor/revision_evidence.py:150:                f"(missing {', '.join(missing_parts)} endpoint(s))"
vibecomfy/executor/revision_evidence.py:155:            if absent not in absent_endpoint_nodes:
vibecomfy/executor/revision_evidence.py:156:                absent_endpoint_nodes.append(absent)
vibecomfy/executor/revision_evidence.py:159:            if absent not in absent_endpoint_nodes:
vibecomfy/executor/revision_evidence.py:160:                absent_endpoint_nodes.append(absent)
vibecomfy/executor/revision_evidence.py:162:        seen_endpoints.add(edge.origin_node)
vibecomfy/executor/revision_evidence.py:163:        seen_endpoints.add(edge.target_node)
vibecomfy/executor/revision_evidence.py:212:    missing_required_inputs: list[dict[str, Any]] = []
vibecomfy/executor/revision_evidence.py:237:                    missing_required_inputs.append({
vibecomfy/executor/revision_evidence.py:253:    if absent_endpoint_nodes:
vibecomfy/executor/revision_evidence.py:255:            f"{len(absent_endpoint_nodes)} absent endpoint node(s)"
vibecomfy/executor/revision_evidence.py:263:    if missing_required_inputs:
vibecomfy/executor/revision_evidence.py:265:            f"{len(missing_required_inputs)} missing required input(s)"
vibecomfy/executor/revision_evidence.py:275:        absent_endpoint_nodes=tuple(absent_endpoint_nodes),
vibecomfy/executor/revision_evidence.py:278:        missing_required_inputs=tuple(missing_required_inputs),
vibecomfy/executor/revision_evidence.py:483:            candidate_topology.absent_endpoint_nodes,
vibecomfy/executor/revision_evidence.py:484:            original_topology.absent_endpoint_nodes if original_topology is not None else (),
vibecomfy/executor/revision_evidence.py:495:            candidate_topology.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:496:            original_topology.missing_required_inputs if original_topology is not None else (),
vibecomfy/executor/revision_evidence.py:1158:    to a hash of the endpoint tuple.
vibecomfy/executor/revision_evidence.py:1166:        # Fallback: identity from endpoints.
vibecomfy/executor/revision_evidence.py:1341:            if topology.missing_required_inputs:
vibecomfy/executor/revision_evidence.py:1372:                facts.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:1395:        missing_required_inputs=facts.missing_required_inputs,
vibecomfy/executor/contracts.py:37:    "empty_response",
vibecomfy/executor/contracts.py:38:    "malformed_json",
vibecomfy/executor/contracts.py:39:    "non_json_content",
vibecomfy/executor/contracts.py:40:    "missing_required_fields",
vibecomfy/executor/contracts.py:58:def normalize_model_endpoint(value: Any) -> str:
vibecomfy/executor/contracts.py:59:    """Return a credential-free, query-free endpoint or ``"unknown"``.
vibecomfy/executor/contracts.py:98:        lambda match: normalize_model_endpoint(match.group(0)), normalized
vibecomfy/executor/contracts.py:109:def _model_attempt_text(value: Any) -> str:
vibecomfy/executor/contracts.py:115:def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
vibecomfy/executor/contracts.py:129:class ModelAttemptEvidence:
vibecomfy/executor/contracts.py:140:    failure_type: str | None = None
vibecomfy/executor/contracts.py:141:    requested_model: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:142:    resolved_model: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:145:    transport: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:146:    endpoint: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:147:    finish_reason: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:148:    token_usage: Mapping[str, Any] = field(default_factory=dict)
vibecomfy/executor/contracts.py:153:        failure_type = self.failure_type
vibecomfy/executor/contracts.py:155:            failure_type = None
vibecomfy/executor/contracts.py:156:        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
vibecomfy/executor/contracts.py:157:            failure_type = "provider_failure"
vibecomfy/executor/contracts.py:158:        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
vibecomfy/executor/contracts.py:161:        object.__setattr__(self, "failure_type", failure_type)
vibecomfy/executor/contracts.py:163:            "requested_model", "resolved_model", "adapter", "provider",
vibecomfy/executor/contracts.py:164:            "transport", "finish_reason",
vibecomfy/executor/contracts.py:166:            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
vibecomfy/executor/contracts.py:167:        object.__setattr__(self, "endpoint", normalize_model_endpoint(self.endpoint))
vibecomfy/executor/contracts.py:170:            "token_usage",
vibecomfy/executor/contracts.py:171:            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
vibecomfy/executor/contracts.py:181:    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
vibecomfy/executor/contracts.py:186:            failure_type=value.get("failure_type"),
vibecomfy/executor/contracts.py:187:            requested_model=value.get("requested_model", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:188:            resolved_model=value.get("resolved_model", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:191:            transport=value.get("transport", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:192:            endpoint=value.get("endpoint", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:193:            finish_reason=value.get("finish_reason", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:194:            token_usage=value.get("token_usage", {}),
vibecomfy/executor/contracts.py:203:            "failure_type": self.failure_type,
vibecomfy/executor/contracts.py:204:            "requested_model": self.requested_model,
vibecomfy/executor/contracts.py:205:            "resolved_model": self.resolved_model,
vibecomfy/executor/contracts.py:208:            "transport": self.transport,
vibecomfy/executor/contracts.py:209:            "endpoint": self.endpoint,
vibecomfy/executor/contracts.py:210:            "finish_reason": self.finish_reason,
vibecomfy/executor/contracts.py:211:            "token_usage": dict(self.token_usage),
vibecomfy/executor/contracts.py:218:def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/contracts.py:224:        if isinstance(item, ModelAttemptEvidence):
vibecomfy/executor/contracts.py:227:            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
vibecomfy/executor/contracts.py:1760:    edges, missing endpoint nodes, and schema-backed missing required inputs.
vibecomfy/executor/contracts.py:1770:    absent_endpoint_nodes: tuple[str, ...] = ()
vibecomfy/executor/contracts.py:1773:    missing_required_inputs: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:1779:        object.__setattr__(self, "absent_endpoint_nodes", tuple(self.absent_endpoint_nodes))
vibecomfy/executor/contracts.py:1786:        object.__setattr__(self, "missing_required_inputs", tuple(
vibecomfy/executor/contracts.py:1789:            for item in self.missing_required_inputs
vibecomfy/executor/contracts.py:1798:            or self.absent_endpoint_nodes
vibecomfy/executor/contracts.py:1801:            or self.missing_required_inputs
vibecomfy/executor/contracts.py:1808:            "absent_endpoint_nodes": list(self.absent_endpoint_nodes),
vibecomfy/executor/contracts.py:1811:            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
vibecomfy/executor/contracts.py:1997:                or self.topology.absent_endpoint_nodes
vibecomfy/executor/contracts.py:1998:                or self.topology.missing_required_inputs
vibecomfy/executor/contracts.py:2038:    missing_required_inputs: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:2058:        object.__setattr__(self, "missing_required_inputs", tuple(
vibecomfy/executor/contracts.py:2061:            for item in self.missing_required_inputs
vibecomfy/executor/contracts.py:2090:            missing_required_inputs=topology.missing_required_inputs,
vibecomfy/executor/contracts.py:2103:            or self.missing_required_inputs
vibecomfy/executor/contracts.py:2116:            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
vibecomfy/executor/contracts.py:2310:    model_attempts: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:2323:            "model_attempts",
vibecomfy/executor/contracts.py:2324:            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
vibecomfy/executor/contracts.py:2329:        """Compatibility view derived solely from canonical ``model_attempts``."""
vibecomfy/executor/contracts.py:2330:        if not self.model_attempts:
vibecomfy/executor/contracts.py:2333:            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
vibecomfy/executor/contracts.py:2358:        inner["model_attempts"] = [
vibecomfy/executor/contracts.py:2359:            _thaw_jsonish(item) for item in self.model_attempts
vibecomfy/executor/contracts.py:2553:    if result.failure_kind is not None:
vibecomfy/executor/contracts.py:2605:    failure_kind: str | None = None
vibecomfy/executor/contracts.py:2620:        payload["model_attempts"] = [
vibecomfy/executor/contracts.py:2621:            _thaw_jsonish(item) for item in self.report.model_attempts
vibecomfy/executor/contracts.py:2643:        if self.failure_kind is not None:
vibecomfy/executor/contracts.py:2644:            payload["failure_kind"] = self.failure_kind
vibecomfy/executor/contracts.py:2673:            failure_kind=kind,
vibecomfy/executor/contracts.py:2703:    "ModelAttemptEvidence",
vibecomfy/executor/contracts.py:2710:    "coerce_model_attempts",
vibecomfy/executor/contracts.py:2712:    "normalize_model_endpoint",
vibecomfy/executor/prompts.py:9:Both phases use strict JSON contracts with small parsers so malformed model
vibecomfy/executor/prompts.py:344:            # Defensively skip any malformed entries (non-dict, missing
vibecomfy/nodes/core.py:19502:    Generates images synchronously via OpenAI's DALL·E 2 endpoint.
vibecomfy/nodes/core.py:19540:    Generates images synchronously via OpenAI's DALL·E 3 endpoint.
vibecomfy/nodes/core.py:19582:    Generates images synchronously via OpenAI's GPT Image endpoint.
vibecomfy/nodes/core.py:19629:    Generates images via OpenAI's GPT Image endpoint.
vibecomfy/executor/core.py:35:    begin_model_attempt_capture,
vibecomfy/executor/core.py:37:    end_model_attempt_capture,
vibecomfy/executor/core.py:39:    snapshot_model_attempt_capture,
vibecomfy/executor/core.py:60:    coerce_model_attempts,
vibecomfy/executor/core.py:106:def _model_attempts_from_exception(exc: BaseException) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/core.py:112:        attempts = coerce_model_attempts(getattr(current, "model_attempts", None))
vibecomfy/executor/core.py:117:            attempts = coerce_model_attempts(worker_result.get("model_attempts"))
vibecomfy/executor/core.py:129:    attempts = _model_attempts_from_exception(exc)
vibecomfy/executor/core.py:133:    context["model_attempts"] = list(attempts)
vibecomfy/executor/core.py:137:def _failure_model_attempts(failure: Any) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/core.py:142:    return coerce_model_attempts(context.get("model_attempts"))
vibecomfy/executor/core.py:535:    Defensively tolerates malformed historical chat artifacts (non-dict
vibecomfy/executor/core.py:995:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:998:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1005:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1008:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1399:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1414:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1420:    if result.get("ok") is False or "failure_kind" in result:
vibecomfy/executor/core.py:1421:        fk = result.get("failure_kind", result.get("kind", "ValidationError"))
vibecomfy/executor/core.py:1425:            "failure_kind": fk,
vibecomfy/executor/core.py:1447:                    if key not in {"message", "stage", "failure_kind"}
vibecomfy/executor/core.py:1453:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1710:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1720:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1723:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1730:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1733:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1751:        failure_kind: str,
vibecomfy/executor/core.py:1755:        model_attempts: tuple[dict[str, Any], ...] = (),
vibecomfy/executor/core.py:1759:        self.failure_kind = failure_kind
vibecomfy/executor/core.py:1762:        self.model_attempts = coerce_model_attempts(model_attempts)
vibecomfy/executor/core.py:1850:        "input graph has dangling/absent endpoints -> refuse to compound"
vibecomfy/executor/core.py:1875:    attempt_token = begin_model_attempt_capture()
vibecomfy/executor/core.py:1883:        fallback_model_attempts: tuple[dict[str, Any], ...] = (),
vibecomfy/executor/core.py:1886:        model_attempts = snapshot_model_attempt_capture()
vibecomfy/executor/core.py:1887:        if not model_attempts:
vibecomfy/executor/core.py:1888:            model_attempts = coerce_model_attempts(fallback_model_attempts)
vibecomfy/executor/core.py:1901:            model_attempts=model_attempts,
vibecomfy/executor/core.py:1906:        end_model_attempt_capture(attempt_token)
vibecomfy/executor/core.py:2022:            fallback_model_attempts=exc.model_attempts,
vibecomfy/executor/core.py:2025:            kind=exc.failure_kind,
vibecomfy/executor/core.py:2185:                "failure_kind": exc.failure_kind,
vibecomfy/executor/core.py:2211:                kind=exc.failure_kind,
vibecomfy/executor/core.py:2321:                exc.failure_kind,
vibecomfy/executor/core.py:2327:                fallback_model_attempts=exc.model_attempts,
vibecomfy/executor/core.py:2343:            fallback_model_attempts=exc.model_attempts,
vibecomfy/executor/core.py:2346:            kind=exc.failure_kind,
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
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:472:    """Stable endpoint identity for link ops (the `to` field tuple)."""
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:483:    endpoint.  But a canonical rewire is ``remove_link(to=X)`` followed by
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:688:                raise ContractError("Inverse remove_link endpoint mismatch", "inverse_missing_prior_state")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:689:        # upsert_link inverse restores prior endpoints (accepted structurally).
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:692:            raise ContractError("Inverse upsert_link endpoint mismatch", "inverse_missing_prior_state")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:718:def _root_endpoint(value: Any) -> bool:
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
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:825:                    or not _root_endpoint(witness.get("from"))
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:826:                    or not _root_endpoint(witness.get("to"))
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
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:550:    failure_kind: FailureKind,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:569:    hard_refusal = bool(hard_codes) or failure_kind is FailureKind.UNREPRESENTABLE
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:589:        "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:600:def _batch_budget_failure_kind(turns: list[dict[str, Any]]) -> FailureKind:
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:645:     "_batch_budget_artifixer_report", "_batch_budget_failure_kind",
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:569:    and raw JSON blobs.  Only includes fields safe for wire transport.
vibecomfy/agent/artifacts.py:16:from vibecomfy.executor.contracts import normalize_model_endpoint, redact_model_preview
vibecomfy/agent/artifacts.py:33:    "model_attempts.json",
vibecomfy/agent/artifacts.py:146:    if parent_key.lower() == "endpoint":
vibecomfy/agent/artifacts.py:147:        return normalize_model_endpoint(value)
vibecomfy/agent/artifacts.py:157:    values under sensitive keys are replaced wholesale, ``endpoint`` and
vibecomfy/agent/artifacts.py:207:                # credential in malformed structured text that free-text
vibecomfy/agent/artifacts.py:429:    model_attempts = report.get("model_attempts")
vibecomfy/agent/artifacts.py:430:    if isinstance(model_attempts, (list, tuple)) and model_attempts:
vibecomfy/agent/artifacts.py:432:            output_dir / "model_attempts.json",
vibecomfy/agent/artifacts.py:433:            {"attempts": _redact(model_attempts)},
vibecomfy/agent/artifacts.py:435:        _append_manifest(manifest, "model_attempts.json")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:111:    _batch_budget_failure_kind: Any  # host: _frag_batch_reports
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:253:def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:258:    raw_preview = getattr(exc, "raw_response_preview", None)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:259:    if isinstance(raw_preview, str) and raw_preview.strip():
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:260:        detail["raw_response_preview"] = raw_preview.strip()
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:277:    return "malformed"
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:286:        detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:287:        raw_preview = detail.get("raw_response_preview")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:288:        if raw_preview:
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:292:                f"{raw_preview}"
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
vibecomfy/agent/contracts.py:80:      pre-edit "input graph has dangling/absent endpoints -> refuse to compound"
vibecomfy/agent/contracts.py:81:      precondition, and only when the dangling/absent endpoints are exactly the
vibecomfy/comfy_nodes/agent/authority_receipts.py:309:        # A present envelope is authority evidence.  If it is malformed, never
vibecomfy/comfy_nodes/agent/authority_receipts.py:422:    modes, wired endpoints, and widget values while intentionally excluding
vibecomfy/executor/agent_backend.py:29:    ModelAttemptEvidence,
vibecomfy/executor/agent_backend.py:30:    coerce_model_attempts,
vibecomfy/executor/agent_backend.py:71:    resolved model/phase/endpoint; attaching it (and the raw content preview)
vibecomfy/executor/agent_backend.py:78:        if result is not None and getattr(exc, "model_attempts", None) is None:
vibecomfy/executor/agent_backend.py:79:            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:89:def _downstream_failure_type(raw: str | None) -> str:
vibecomfy/executor/agent_backend.py:91:        return "empty_response"
vibecomfy/executor/agent_backend.py:99:        return "malformed_json" if "{" in stripped else "non_json_content"
vibecomfy/executor/agent_backend.py:100:    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"
vibecomfy/executor/agent_backend.py:104:    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
vibecomfy/executor/agent_backend.py:106:    record_model_attempts(result.get("model_attempts"))
vibecomfy/executor/agent_backend.py:110:    result: dict[str, Any], *, raw: str | None, failure_type: str
vibecomfy/executor/agent_backend.py:112:    attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/executor/agent_backend.py:118:        "failure_type": failure_type,
vibecomfy/executor/agent_backend.py:121:    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
vibecomfy/executor/agent_backend.py:123:    result["model_attempts"] = attempts
vibecomfy/executor/agent_backend.py:124:    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
vibecomfy/executor/agent_backend.py:126:    replace_last_model_attempt(revised)
vibecomfy/executor/agent_backend.py:208:                failure_type=_downstream_failure_type(raw),
vibecomfy/executor/agent_backend.py:329:                failure_type=_downstream_failure_type(raw),
vibecomfy/porting/reorganise/projection.py:224:        f"endpoints: {_json(list(fact.endpoints))}"
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:190:def malformed_execution_plan_evaluation(
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:214:        feedback="plan evaluation blocked: malformed execution plan payload.",
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:232:        evaluation = malformed_execution_plan_evaluation(
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:312:    "malformed_execution_plan_evaluation",
vibecomfy/porting/reorganise/graph_facts.py:220:    endpoints: tuple[Any, ...] = ()
vibecomfy/porting/reorganise/graph_facts.py:224:        object.__setattr__(self, "endpoints", tuple(_freeze_jsonish(item) for item in self.endpoints))
vibecomfy/porting/reorganise/graph_facts.py:233:            "endpoints": [_thaw_jsonish(item) for item in self.endpoints],
vibecomfy/porting/reorganise/graph_facts.py:769:            endpoints = payload.get("endpoints")
vibecomfy/porting/reorganise/graph_facts.py:770:            if not isinstance(endpoints, Sequence) or isinstance(endpoints, (str, bytes)):
vibecomfy/porting/reorganise/graph_facts.py:771:                endpoints = ()
vibecomfy/porting/reorganise/graph_facts.py:778:                    endpoints=tuple(endpoints),
vibecomfy/porting/reorganise/graph_facts.py:835:        # Tag effective edges whose endpoints share an SCC as feedback
vibecomfy/porting/reorganise/graph_facts.py:1058:    """Return True when both endpoints of *edge* belong to the same SCC."""
vibecomfy/runtime/eval/core.py:240:    # Filter edges to only those where both endpoints are in selected_ids
vibecomfy/executor/research.py:1555:    ``/api/download/models/<version_id>`` endpoints.  The ZIP archives for
vibecomfy/executor/research.py:1671:    # JSON endpoint in their SSR HTML.  Extractors for those platforms can be
vibecomfy/executor/research.py:2876:def _requested_model_families(query: str, graph: dict | None = None) -> set[str]:
vibecomfy/executor/research.py:3053:    requested = _requested_model_families(query, graph)
vibecomfy/executor/research.py:3142:            "code": "missing_required_pattern_nodes",
vibecomfy/executor/research.py:3343:    """A single cut edge with exactly one endpoint inside a source segment S.
vibecomfy/executor/research.py:3346:    precisely one endpoint (the producer or the consumer) belongs to the
vibecomfy/executor/research.py:3351:    inside_node_id: str  # the endpoint that IS in S
vibecomfy/executor/research.py:3352:    outside_node_id: str  # the endpoint NOT in S
vibecomfy/executor/research.py:3440:    A **cut edge** is any directed link with exactly ONE endpoint inside the
vibecomfy/executor/research.py:3446:    Edges with both endpoints inside *S* (internal) or both outside
vibecomfy/executor/research.py:3643:    """Bind each source-segment cut edge to a unique target-graph endpoint.
vibecomfy/executor/research.py:3647:    concrete socket type, endpoint existence, and target-input uniqueness all
vibecomfy/executor/research.py:3733:                # Gate 4: endpoint existence.
vibecomfy/executor/research.py:4258:    outside-of-segment endpoints.
vibecomfy/executor/research.py:4289:        # The segment-side endpoint of the cut edge is the source anchor.  For
vibecomfy/executor/research.py:4550:    endpoints are added nodes.
vibecomfy/executor/research.py:4552:    Boundary anchors: ``[node_id, output_slot]`` links where one endpoint is
vibecomfy/executor/research.py:4602:                # Both endpoints are added → internal edge.
vibecomfy/executor/research.py:4734:    requested_families = _requested_model_families(query)
vibecomfy/executor/research.py:4853:    Returns ``None`` if the inputs look malformed.
vibecomfy/executor/research.py:5565:                        reason="candidate graph construction returned a malformed graph",
vibecomfy/executor/research.py:5566:                        detail={"reason_code": "candidate_graph_malformed"},
vibecomfy/executor/research.py:5989:    terms.extend(sorted(_requested_model_families(query)))
vibecomfy/executor/research.py:6093:    requested_families = set(_requested_model_families(query))
vibecomfy/executor/research.py:6232:    research endpoints are unreachable.
vibecomfy/porting/reorganise/parse.py:335:            "missing_required_field",
vibecomfy/porting/reorganise/parse.py:577:                            "missing_helper_edge_endpoint",
vibecomfy/analysis/graph.py:332:                        "reason": "missing_required_input",
vibecomfy/executor/execution_plan_builder.py:63:    "missing_required_inputs",
vibecomfy/porting/reorganise/compile.py:4168:    over_capacity = len(cleaned) > max_columns
vibecomfy/porting/reorganise/compile.py:4178:    if not over_capacity and not imbalanced and not single_tall_column:
vibecomfy/porting/reorganise/validate.py:296:        target = _validate_optional_endpoint(
vibecomfy/porting/reorganise/validate.py:304:        source = _validate_optional_endpoint(
vibecomfy/porting/reorganise/validate.py:312:        destination = _validate_optional_endpoint(
vibecomfy/porting/reorganise/validate.py:363:                        "edge-path helper endpoints must be distinct non-helper nodes in the same scope.",
vibecomfy/porting/reorganise/validate.py:369:            for field_name, endpoint in (
vibecomfy/porting/reorganise/validate.py:374:                if endpoint is not None and endpoint.scope_path != helper.scope_path:
vibecomfy/porting/reorganise/validate.py:378:                            "helper placement endpoints must stay in the helper node scope.",
vibecomfy/porting/reorganise/validate.py:380:                            detail={"helper": helper.to_json(), "endpoint": endpoint.to_json()},
vibecomfy/porting/reorganise/validate.py:385:def _validate_optional_endpoint(
vibecomfy/porting/reorganise/validate.py:667:    An edge whose endpoints belong to different SCCs must respect topological
vibecomfy/porting/reorganise/validate.py:670:    endpoints at the same layer after SCC condensation.
vibecomfy/runtime/session.py:356:        # endpoint is unreachable the watchdog handles it gracefully.
vibecomfy/runtime/attempt.py:1:"""Attempt bundle builder — written before every queue boundary.
vibecomfy/comfy_nodes/agent/hivemind_feedback.py:275:def _default_transport(
vibecomfy/comfy_nodes/agent/hivemind_feedback.py:308:    transport: Transport | None = None,
vibecomfy/comfy_nodes/agent/hivemind_feedback.py:322:        response = (transport or _default_transport)(
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
vibecomfy/comfy_nodes/agent/graph_normalization.py:37:    The conversion is whole-graph and fail-closed: malformed or mixed mapping
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
vibecomfy/comfy_nodes/agent/runtime.py:51:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/runtime.py:52:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/runtime.py:53:    normalize_model_endpoint,
vibecomfy/comfy_nodes/agent/runtime.py:66:# A fresh worker/transport retry is deliberately narrow: only a canonical
vibecomfy/comfy_nodes/agent/runtime.py:68:# extra attempts. Timeouts, capacity/provider errors, and malformed content do
vibecomfy/comfy_nodes/agent/runtime.py:78:    "vibecomfy_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:117:def begin_model_attempt_capture() -> contextvars.Token:
vibecomfy/comfy_nodes/agent/runtime.py:121:def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
vibecomfy/comfy_nodes/agent/runtime.py:122:    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())
vibecomfy/comfy_nodes/agent/runtime.py:125:def end_model_attempt_capture(token: contextvars.Token) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:129:def record_model_attempts(value: Any) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:134:    for attempt in coerce_model_attempts(value):
vibecomfy/comfy_nodes/agent/runtime.py:140:def replace_last_model_attempts(value: Any) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:143:    normalized = coerce_model_attempts(value)
vibecomfy/comfy_nodes/agent/runtime.py:152:def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:153:    """Replace the most recent captured transport-success after domain parse failure."""
vibecomfy/comfy_nodes/agent/runtime.py:154:    replace_last_model_attempts([value])
vibecomfy/comfy_nodes/agent/runtime.py:282:        raw preview, usage, model, phase, and endpoint without re-resolving
vibecomfy/comfy_nodes/agent/runtime.py:374:    # hermes backend to a non-DeepSeek OpenAI-compatible endpoint). No-op unset.
vibecomfy/comfy_nodes/agent/runtime.py:402:    native endpoint.
vibecomfy/comfy_nodes/agent/runtime.py:414:    """Pin explicit OpenRouter turns to OpenRouter's canonical API endpoint."""
vibecomfy/comfy_nodes/agent/runtime.py:420:def _is_native_deepseek_endpoint(base_url: str | None = None) -> bool:
vibecomfy/comfy_nodes/agent/runtime.py:428:    # non-OpenRouter OpenAI-compatible endpoint such as Fireworks). Bypasses
vibecomfy/comfy_nodes/agent/runtime.py:437:    if _is_native_deepseek_endpoint() and os.getenv("DEEPSEEK_API_KEY"):
vibecomfy/comfy_nodes/agent/runtime.py:488:        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
vibecomfy/comfy_nodes/agent/runtime.py:489:        if _is_native_deepseek_endpoint(base_url):
vibecomfy/comfy_nodes/agent/runtime.py:492:            resolved_model = _normalize_native_deepseek_model(resolved_model)
vibecomfy/comfy_nodes/agent/runtime.py:494:            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
vibecomfy/comfy_nodes/agent/runtime.py:496:            model=resolved_model,
vibecomfy/comfy_nodes/agent/runtime.py:509:    attempts = coerce_model_attempts(result.get("model_attempts"))
vibecomfy/comfy_nodes/agent/runtime.py:513:    usage = latest.get("token_usage")
vibecomfy/comfy_nodes/agent/runtime.py:516:        and latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/runtime.py:522:def _runtime_provider_transport(
vibecomfy/comfy_nodes/agent/runtime.py:525:    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
vibecomfy/comfy_nodes/agent/runtime.py:527:        return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:528:    if "openrouter.ai" in endpoint:
vibecomfy/comfy_nodes/agent/runtime.py:529:        return "openrouter", "openrouter", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:530:    if "deepseek.com" in endpoint:
vibecomfy/comfy_nodes/agent/runtime.py:531:        return "deepseek", "native", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:532:    if endpoint != "unknown":
vibecomfy/comfy_nodes/agent/runtime.py:533:        return "unknown", "openai_compatible", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:534:    return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:537:def _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:541:    requested_model: str | None,
vibecomfy/comfy_nodes/agent/runtime.py:542:    resolved_model: str | None,
vibecomfy/comfy_nodes/agent/runtime.py:546:    provider, transport, endpoint = _runtime_provider_transport(
vibecomfy/comfy_nodes/agent/runtime.py:549:    return ModelAttemptEvidence(
vibecomfy/comfy_nodes/agent/runtime.py:553:        failure_type="timeout",
vibecomfy/comfy_nodes/agent/runtime.py:554:        requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:555:        resolved_model=resolved_model or agent_kwargs.get("model"),
vibecomfy/comfy_nodes/agent/runtime.py:558:        transport=transport,
vibecomfy/comfy_nodes/agent/runtime.py:559:        endpoint=endpoint,
vibecomfy/comfy_nodes/agent/runtime.py:571:    requested_model: str | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:577:    A fresh subprocess/transport is permitted only after a canonical
vibecomfy/comfy_nodes/agent/runtime.py:578:    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
vibecomfy/comfy_nodes/agent/runtime.py:579:    provider/capacity errors, and malformed non-empty content surface immediately.
vibecomfy/comfy_nodes/agent/runtime.py:594:                requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:599:            timeout_attempt = _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:602:                requested_model=requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:603:                resolved_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:608:            record_model_attempts([timeout_attempt])
vibecomfy/comfy_nodes/agent/runtime.py:609:            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/runtime.py:611:        attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/comfy_nodes/agent/runtime.py:614:            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
vibecomfy/comfy_nodes/agent/runtime.py:616:            record_model_attempts([normalized])
vibecomfy/comfy_nodes/agent/runtime.py:618:            result["model_attempts"] = list(accumulated_attempts)
vibecomfy/comfy_nodes/agent/runtime.py:643:    requested_model: str | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:663:                    "requested_model": requested_model,
vibecomfy/comfy_nodes/agent/runtime.py:675:        # Hermes adapter.  For native DeepSeek endpoints this must be the
vibecomfy/comfy_nodes/agent/runtime.py:775:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:819:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:857:        requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:1203:            requested_model=model,
vibecomfy/comfy_nodes/agent/runtime.py:1218:    "end_deepseek_usage_capture", "begin_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1219:    "snapshot_model_attempt_capture", "end_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1220:    "record_model_attempts", "replace_last_model_attempt", "replace_last_model_attempts",
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:150:        # legacy accept/reject endpoints.  This guard fails closed so a V2
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:173:                        f"Use the V2 prepare / finalize / rollback endpoints instead of {scope}."
vibecomfy/comfy_nodes/agent/worker.py:69:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/worker.py:70:    normalize_model_endpoint,
vibecomfy/comfy_nodes/agent/worker.py:106:def _model_attempt_failure_type(exc: BaseException, raw_text: str | None) -> str:
vibecomfy/comfy_nodes/agent/worker.py:109:        return "empty_response"
vibecomfy/comfy_nodes/agent/worker.py:113:        return "malformed_json" if "{" in (raw_text or "") else "non_json_content"
vibecomfy/comfy_nodes/agent/worker.py:116:        return "non_json_content"
vibecomfy/comfy_nodes/agent/worker.py:119:            return "missing_required_fields"
vibecomfy/comfy_nodes/agent/worker.py:120:        return "malformed_json"
vibecomfy/comfy_nodes/agent/worker.py:124:def _worker_provider_transport(
vibecomfy/comfy_nodes/agent/worker.py:131:    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
vibecomfy/comfy_nodes/agent/worker.py:133:        return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/worker.py:134:    if "openrouter.ai" in endpoint:
vibecomfy/comfy_nodes/agent/worker.py:135:        return "openrouter", "openrouter", endpoint
vibecomfy/comfy_nodes/agent/worker.py:136:    if "deepseek.com" in endpoint:
vibecomfy/comfy_nodes/agent/worker.py:137:        return "deepseek", "native", endpoint
vibecomfy/comfy_nodes/agent/worker.py:138:    if endpoint != "unknown":
vibecomfy/comfy_nodes/agent/worker.py:139:        return "unknown", "openai_compatible", endpoint
vibecomfy/comfy_nodes/agent/worker.py:140:    return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/worker.py:143:def _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:149:    failure_type: str | None = None,
vibecomfy/comfy_nodes/agent/worker.py:159:    provider, transport, endpoint = _worker_provider_transport(request)
vibecomfy/comfy_nodes/agent/worker.py:160:    return ModelAttemptEvidence(
vibecomfy/comfy_nodes/agent/worker.py:162:        attempt=profiling_context.get("model_attempt") or 1,
vibecomfy/comfy_nodes/agent/worker.py:164:        failure_type=failure_type,
vibecomfy/comfy_nodes/agent/worker.py:165:        requested_model=request.get("requested_model"),
vibecomfy/comfy_nodes/agent/worker.py:166:        resolved_model=agent_kwargs.get("model") or request.get("model"),
vibecomfy/comfy_nodes/agent/worker.py:169:        transport=transport,
vibecomfy/comfy_nodes/agent/worker.py:170:        endpoint=endpoint,
vibecomfy/comfy_nodes/agent/worker.py:171:        finish_reason=metadata.get("finish_reason"),
vibecomfy/comfy_nodes/agent/worker.py:172:        token_usage=usage,
vibecomfy/comfy_nodes/agent/worker.py:190:    endpoint, and finish reason so classify/reply attempts are diagnosable.
vibecomfy/comfy_nodes/agent/worker.py:197:    failure_type = _model_attempt_failure_type(exc, raw_text)
vibecomfy/comfy_nodes/agent/worker.py:202:        "empty_response": "empty",
vibecomfy/comfy_nodes/agent/worker.py:203:        "missing_required_fields": "missing_content",
vibecomfy/comfy_nodes/agent/worker.py:204:    }.get(failure_type, failure_type)
vibecomfy/comfy_nodes/agent/worker.py:211:    endpoint = agent_kwargs.get("base_url")
vibecomfy/comfy_nodes/agent/worker.py:212:    if endpoint:
vibecomfy/comfy_nodes/agent/worker.py:213:        out["endpoint"] = normalize_model_endpoint(endpoint)
vibecomfy/comfy_nodes/agent/worker.py:215:        finish_reason = worker_metadata.get("finish_reason")
vibecomfy/comfy_nodes/agent/worker.py:216:        if isinstance(finish_reason, str) and finish_reason.strip():
vibecomfy/comfy_nodes/agent/worker.py:217:            out["finish_reason"] = finish_reason.strip()
vibecomfy/comfy_nodes/agent/worker.py:225:    out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:226:        _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:231:            failure_type=failure_type,
vibecomfy/comfy_nodes/agent/worker.py:276:        resolved_model=model,
vibecomfy/comfy_nodes/agent/worker.py:462:        finish_reason: str | None = None
vibecomfy/comfy_nodes/agent/worker.py:464:            # Prefer the last assistant message's finish_reason (the run
vibecomfy/comfy_nodes/agent/worker.py:469:                value = msg.get("finish_reason")
vibecomfy/comfy_nodes/agent/worker.py:471:                    finish_reason = value.strip()
vibecomfy/comfy_nodes/agent/worker.py:473:            if finish_reason is None:
vibecomfy/comfy_nodes/agent/worker.py:474:                value = last_result.get("finish_reason")
vibecomfy/comfy_nodes/agent/worker.py:476:                    finish_reason = value.strip()
vibecomfy/comfy_nodes/agent/worker.py:484:        if finish_reason:
vibecomfy/comfy_nodes/agent/worker.py:485:            metadata["finish_reason"] = finish_reason
vibecomfy/comfy_nodes/agent/worker.py:573:            # Self-describing envelope: carry the resolved model/phase/endpoint
vibecomfy/comfy_nodes/agent/worker.py:587:            endpoint = agent_kwargs.get("base_url")
vibecomfy/comfy_nodes/agent/worker.py:588:            if endpoint:
vibecomfy/comfy_nodes/agent/worker.py:589:                out["endpoint"] = normalize_model_endpoint(endpoint)
vibecomfy/comfy_nodes/agent/worker.py:590:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:591:                _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:620:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:621:                _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:626:                    failure_type=_model_attempt_failure_type(exc, raw_text),
vibecomfy/comfy_nodes/agent/_frag_narrator.py:85:    def failure_kind(self) -> str:
vibecomfy/comfy_nodes/agent/_frag_narrator.py:426:            LOGGER.warning("Narrator malformed response, falling back: %s", exc)
vibecomfy/comfy_nodes/agent/_frag_narrator.py:427:            fallback_reason = "malformed_response"
vibecomfy/comfy_nodes/__init__.py:380:                "passthrough_on_non_json": ("BOOLEAN", {"default": False}),
vibecomfy/comfy_nodes/__init__.py:462:            "redaction_policy", "policy_version", "passthrough_on_non_json",
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:49:        failure_kind = None
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:51:            failure_kind = result.value.get("failure_kind")
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:84:            failure_kind or FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/edit.py:192:        "_batch_budget_failure_kind",
vibecomfy/comfy_nodes/agent/edit.py:308:        "_is_link_endpoint",
vibecomfy/comfy_nodes/agent/edit.py:325:        "_link_endpoint_parts",
vibecomfy/comfy_nodes/agent/edit.py:329:        "_malformed_model_json_detail",
vibecomfy/comfy_nodes/agent/edit.py:380:        "_resolve_endpoint_label",
vibecomfy/comfy_nodes/agent/diagnostics.py:21:        "missing_required_input",
vibecomfy/comfy_nodes/agent/diagnostics.py:39:    failure_kind: FailureKind | None
vibecomfy/comfy_nodes/agent/diagnostics.py:47:    failure_kind: FailureKind | None
vibecomfy/comfy_nodes/agent/diagnostics.py:120:    failure_kind: FailureKind,
vibecomfy/comfy_nodes/agent/diagnostics.py:128:        "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/diagnostics.py:187:        raw_kind = issue.get("failure_kind")
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
vibecomfy/comfy_nodes/agent/_frag_revision.py:96:        if topology.dangling_links or topology.absent_endpoint_nodes:
vibecomfy/comfy_nodes/agent/_frag_revision.py:103:    if topology.missing_graph or topology.dangling_links or topology.absent_endpoint_nodes:
vibecomfy/comfy_nodes/agent/_frag_revision.py:109:        or topology.missing_required_inputs
vibecomfy/comfy_nodes/agent/_frag_revision.py:127:    if topology.missing_graph or topology.dangling_links or topology.absent_endpoint_nodes:
vibecomfy/comfy_nodes/agent/_frag_revision.py:133:        or topology.missing_required_inputs
vibecomfy/comfy_nodes/agent/_frag_revision.py:180:        absent_endpoint_nodes=topology.absent_endpoint_nodes,
vibecomfy/comfy_nodes/agent/_frag_revision.py:203:        absent_endpoint_nodes=candidate_topology.absent_endpoint_nodes,
vibecomfy/comfy_nodes/agent/_frag_revision.py:212:        missing_required_inputs=_subtract_existing_blockers(
vibecomfy/comfy_nodes/agent/_frag_revision.py:213:            candidate_topology.missing_required_inputs,
vibecomfy/comfy_nodes/agent/_frag_revision.py:214:            topology.missing_required_inputs,
vibecomfy/comfy_nodes/agent/OWNERSHIP.md:57:   endpoint tuples; they are never emitted as typed authority identity.
vibecomfy/comfy_nodes/agent/provider.py:16:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/provider.py:17:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/provider.py:50:    "transport. Reply with one short user-facing sentence followed by exactly "
vibecomfy/comfy_nodes/agent/provider.py:207:    "model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:210:    "finish_reason",
vibecomfy/comfy_nodes/agent/provider.py:216:    "endpoint",
vibecomfy/comfy_nodes/agent/provider.py:228:    attempts = coerce_model_attempts(response.get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:230:        merged["model_attempts"] = [dict(item) for item in attempts]
vibecomfy/comfy_nodes/agent/provider.py:796:        "- Link endpoint: [scope_path, uid, slot_or_field]  e.g. from [\"\", \"115\", \"NOISE\"] to [\"\", \"113\", \"noise\"]\n"
vibecomfy/comfy_nodes/agent/provider.py:938:    # is the transport contract that pins endpoint and credential resolution.
vibecomfy/comfy_nodes/agent/provider.py:1369:    raw_preview = getattr(exc, "raw_response_preview", None)
vibecomfy/comfy_nodes/agent/provider.py:1370:    if isinstance(raw_preview, str) and raw_preview.strip():
vibecomfy/comfy_nodes/agent/provider.py:1374:            f"{raw_preview.strip()}"
vibecomfy/comfy_nodes/agent/provider.py:1379:def _batch_failure_type(exc: BaseException) -> str:
vibecomfy/comfy_nodes/agent/provider.py:1382:        return "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1385:        return "missing_required_fields"
vibecomfy/comfy_nodes/agent/provider.py:1386:    return "malformed_json"
vibecomfy/comfy_nodes/agent/provider.py:1397:    attempts = list(coerce_model_attempts(response.get("model_attempts")))
vibecomfy/comfy_nodes/agent/provider.py:1403:        "failure_type": _batch_failure_type(exc),
vibecomfy/comfy_nodes/agent/provider.py:1411:        revised_attempts.append(ModelAttemptEvidence.from_mapping(numbered).to_dict())
vibecomfy/comfy_nodes/agent/provider.py:1413:        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1415:        replace_last_model_attempts(revised_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1418:    exc.model_attempts = list(revised_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/provider.py:1426:    usage = latest.get("token_usage")
vibecomfy/comfy_nodes/agent/provider.py:1428:        latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1510:                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:1517:                    ModelAttemptEvidence.from_mapping(numbered).to_dict()
vibecomfy/comfy_nodes/agent/provider.py:1521:                    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1523:                    replace_last_model_attempts(numbered_current_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1528:                metadata["model_attempts"] = [*attempt_log, *numbered_current_attempts]
vibecomfy/comfy_nodes/agent/session.py:503:        """Attempt to recover a dead-owner or stale-lease lock.
vibecomfy/comfy_nodes/agent/session.py:550:            self._quarantine_lock("malformed_metadata")
vibecomfy/comfy_nodes/agent/session.py:1489:        "failure_kind",
vibecomfy/comfy_nodes/agent/session.py:1511:    for field, limit in (("failure_kind", 128), ("failure_message", 2048)):
vibecomfy/comfy_nodes/agent/session.py:1839:        return None, "malformed_candidate_transaction"
vibecomfy/comfy_nodes/agent/session.py:3406:            "endpoint": "/vibecomfy/agent-edit/rebaseline",
vibecomfy/comfy_nodes/agent/session.py:3505:        reason = "submitted_baseline_snapshot_malformed"
vibecomfy/comfy_nodes/agent/session.py:4186:# the legacy accept endpoint complete V2 apply flows without an independent
vibecomfy/comfy_nodes/agent/session.py:4289:                                f"must use the V2 prepare / finalize / rollback endpoints directly."
vibecomfy/comfy_nodes/agent/audit.py:401:    failure_kind = None
vibecomfy/comfy_nodes/agent/audit.py:403:        failure_kind = failure.kind.value
vibecomfy/comfy_nodes/agent/audit.py:405:        failure_kind = failure.get("kind") or failure.get("failure_kind")
vibecomfy/comfy_nodes/agent/audit.py:419:        kind=response_dict.get("kind") if response_dict else failure_kind,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:155:def _link_endpoint_parts(value: Any) -> tuple[str, int | str] | None:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:156:    """Return ``(uid, output_slot)`` for supported FieldChange link endpoint shapes.
vibecomfy/comfy_nodes/agent/_frag_humanize.py:176:def _is_link_endpoint(value: Any) -> bool:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:177:    return _link_endpoint_parts(value) is not None
vibecomfy/comfy_nodes/agent/_frag_humanize.py:198:def _resolve_endpoint_label(
vibecomfy/comfy_nodes/agent/_frag_humanize.py:199:    endpoint: Any,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:204:    """Resolve a link endpoint ``[uid, slot]`` to a label like ``'VAE Decode IMAGE'``."""
vibecomfy/comfy_nodes/agent/_frag_humanize.py:205:    parts = _link_endpoint_parts(endpoint)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:329:    return _resolve_endpoint_label({"uid": source_uid, "output_slot": source_slot}, labels, graph)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:381:        old_endpoint_graph = old_graph if isinstance(old_graph, Mapping) else graph
vibecomfy/comfy_nodes/agent/_frag_humanize.py:382:        new_endpoint_graph = new_graph if isinstance(new_graph, Mapping) else graph
vibecomfy/comfy_nodes/agent/_frag_humanize.py:383:        old_link = _is_link_endpoint(change.old)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:384:        new_link = _is_link_endpoint(change.new)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:386:            old_label = _resolve_endpoint_label(change.old, labels, old_endpoint_graph, graph, new_graph)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:387:            new_label = _resolve_endpoint_label(change.new, labels, new_endpoint_graph, graph, old_graph)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:390:            new_label = _resolve_endpoint_label(change.new, labels, new_endpoint_graph, graph, old_graph)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:393:            old_label = _resolve_endpoint_label(change.old, labels, old_endpoint_graph, graph, new_graph)
vibecomfy/comfy_nodes/agent/_frag_humanize.py:946:        if fallback_reason in {"provider_failure", "malformed_response", "timeout"}:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1107:            fallback_reason = "malformed_response"
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1245:     "_humanized_noop_message", "_is_link_endpoint", "_join_human_list",
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1246:     "_landed_edit_lead", "_link_endpoint_parts", "_looks_internal_uid",
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1255:     "_resolve_endpoint_label", "_resolve_output_slot_name",
vibecomfy/comfy_nodes/agent/contracts.py:86:    "endpoint",
vibecomfy/comfy_nodes/agent/contracts.py:145:    "failure_kind",
vibecomfy/comfy_nodes/agent/contracts.py:255:    "failure_kind",
vibecomfy/comfy_nodes/agent/contracts.py:970:def _coerce_failure_kind(value: FailureKind | str) -> FailureKind:
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
vibecomfy/comfy_nodes/agent/contracts.py:1524:            failure_kind = kind_value
vibecomfy/comfy_nodes/agent/contracts.py:1532:    if isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1534:            spec = FAILURE_SPECS[FailureKind(failure_kind)]
vibecomfy/comfy_nodes/agent/contracts.py:1543:        "failure_kind": failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1562:        not isinstance(outcome.get("failure_kind"), str)
vibecomfy/comfy_nodes/agent/contracts.py:1563:        or outcome.get("failure_kind") not in {kind.value for kind in FailureKind}
vibecomfy/comfy_nodes/agent/contracts.py:2408:    failure_kind = _coerce_failure_kind(kind)
vibecomfy/comfy_nodes/agent/contracts.py:2409:    spec = FAILURE_SPECS[failure_kind]
vibecomfy/comfy_nodes/agent/contracts.py:2412:        kind=failure_kind,
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:32:def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:37:    raw_preview = getattr(exc, "raw_response_preview", None)
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:38:    if isinstance(raw_preview, str) and raw_preview.strip():
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:39:        detail["raw_response_preview"] = raw_preview.strip()
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:56:    return "malformed"
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:63:    from vibecomfy.comfy_nodes.agent.edit import (_BATCH_PROTOCOL_RETRY_PROMPT, _malformed_model_json_detail)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:66:        detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:67:        raw_preview = detail.get("raw_response_preview")
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:68:        if raw_preview:
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:72:                f"{raw_preview}"
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:221:        # A malformed node entry means we cannot guarantee completeness.
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:941:    "_malformed_model_json_detail",
vibecomfy/comfy_nodes/web/agent_submit_flow.js:355:    const normalizedAttemptIndex = Number.isFinite(attemptIndex) ? Number(attemptIndex) : 0;
vibecomfy/comfy_nodes/web/agent_submit_flow.js:359:    if (normalizedAttemptIndex >= normalizedRetryBudget) {
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:131:            # malformed ops (unknown op kind, missing required fields,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:139:        # Envelope present but ops is malformed — fall through to delta_ops.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:257:            # malformed entries (unknown op kind, missing required fields,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:258:            # etc.) are classified as malformed rather than canonical.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:264:                    "code": "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:277:            "code": "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:487:def _normalize_link_endpoint(node_alias: Any, output_slot: Any) -> Any:
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:508:def _read_link_source_endpoint(
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:541:    return _normalize_link_endpoint(origin_uid, origin_slot)
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:584:            return (_normalize_link_endpoint(source_uid, output_slot), None)
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:589:            _read_link_source_endpoint(
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:724:    Returns the current link source endpoint ``(origin_uid, origin_slot)``
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:730:    value = _read_link_source_endpoint(
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:816:    # scope_path.  If none are present the op is malformed.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:995:        "endpoint": "/vibecomfy/agent-edit/rebaseline",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1124:        distinct buckets: *malformed_delta*, *legacy_delta_shape*,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1157:    # malformed shapes in distinct evidence buckets.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1191:        elif diag_code == "canonical_envelope_malformed_ops":
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1192:            diag_code = "malformed_delta"
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1195:                "is malformed."
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1312:    "_normalize_link_endpoint",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1314:    "_read_link_source_endpoint",
vibecomfy/comfy_nodes/web/frontend_ownership_map.md:71:  roundtrip-owned transport normalizers. They handle wire-format concerns,
vibecomfy/comfy_nodes/web/frontend_ownership_map.md:76:- The roundtrip rehydrate entry applies the transport normalizers, then calls
vibecomfy/comfy_nodes/web/frontend_ownership_map.md:79:- Per S14, lifecycle does not absorb the transport normalizers: wire-format
vibecomfy/comfy_nodes/web/frontend_ownership_map.md:80:  aliasing belongs at the transport boundary, not in canonical state.
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:882:        "the request unless you can cite the exact current node ids, fields/widgets, and/or link endpoints "
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:159:    entry?.failure_kind
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:161:    || outcome?.failure_kind
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:590:    "  - response.json: the final outcome envelope (failure_kind, user_facing_message).",
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:623:          failure_kind: turnEntry.failure_kind || null,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:710:      failure_kind: panel.state.failure.kind,
vibecomfy/environment_diagnostics.py:25:        warnings.append(f"hardware requires at least {min_vram}GB VRAM; local GPU capacity was not probed offline")
vibecomfy/environment_diagnostics.py:27:        warnings.append(f"hardware recommends {recommended_vram}GB VRAM; local GPU capacity was not probed offline")
vibecomfy/comfy_nodes/agent/candidate_transaction.py:279:        return False, "malformed_schema_witness"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:281:        return False, "malformed_schema_provider_mode"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:666:        return False, "malformed_candidate_transaction"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:697:            return False, "malformed_layout_verification_contract"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:715:        return False, "malformed_candidate_transaction_actions"
vibecomfy/comfy_nodes/web/agent_status_poller.js:13:  MALFORMED: "malformed_status",
vibecomfy/comfy_nodes/web/agent_status_poller.js:297:      issue: "malformed_status",
vibecomfy/comfy_nodes/web/agent_status_poller.js:539:  const priorAttempts =
vibecomfy/comfy_nodes/web/agent_status_poller.js:543:  const attempts = priorAttempts + 1;
vibecomfy/comfy_nodes/web/agent_status_poller.js:545:    panel.state.statusRetry = { route, model, attempts: priorAttempts, exhausted: true, timerId: null };
vibecomfy/comfy_nodes/web/agent_status_poller.js:618:  const retryAttempts =
vibecomfy/comfy_nodes/web/agent_status_poller.js:625:  panel.state.statusRetry = retryAttempts > 0
vibecomfy/comfy_nodes/web/agent_status_poller.js:626:    ? { route, model, attempts: retryAttempts, exhausted: false, timerId: null }
vibecomfy/comfy_nodes/web/agent_status_poller.js:672:      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", error);
vibecomfy/comfy_nodes/web/agent_status_poller.js:707:    if (projected.issue === "malformed_status") {
vibecomfy/comfy_nodes/web/agent_status_poller.js:708:      console.warn("[vibecomfy] malformed /vibecomfy/agent/status payload", status);
vibecomfy/comfy_nodes/web/agent_status_poller.js:832:        kind: "malformed",
vibecomfy/comfy_nodes/web/agent_status_poller.js:854:        kind: "malformed",
vibecomfy/comfy_nodes/web/panel_composer.js:98:      // Ignore malformed debug-only stage data in the composer summary.
vibecomfy/comfy_nodes/web/panel_composer.js:142:    return readApplyCandidate(source, { allowLegacy: false, endpoint: "panel-composer-state" });
vibecomfy/comfy_nodes/web/panel_composer.js:191:      message: "Submit is disabled because /vibecomfy/agent/status returned a malformed payload.",
vibecomfy/comfy_nodes/web/panel_composer.js:842:      guidanceNode.textContent = "The backend status payload is malformed. Fix /vibecomfy/agent/status and retry.";
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:63:      : typeof value?.failure_kind === "string" && value.failure_kind
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:64:        ? value.failure_kind
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:287:        ? { failure_kind: rollbackFailureKind(triggerFailure).slice(0, 128) }
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:602:        failure_kind: failure.kind || "RejectError",
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:758:            failure_kind: failure.kind || null,
vibecomfy/demo_factory/deltas.py:204:    fresh node, so a link endpoint that the golden pinned to the added node's
vibecomfy/demo_factory/deltas.py:205:    id must instead be matched by node TYPE.  When an endpoint id is in
vibecomfy/demo_factory/deltas.py:207:    the surviving-anchor id on the other endpoint) so the evaluator can accept
vibecomfy/demo_factory/deltas.py:208:    any sound re-add at a new id.  Surviving endpoints keep their absolute id
vibecomfy/demo_factory/deltas.py:241:    peer endpoint pinned by id (stable across the fault); ``widgets_values`` is
vibecomfy/demo_factory/deltas.py:244:    Known limitation: witness edges assume the peer endpoint survived the fault
vibecomfy/demo_factory/deltas.py:360:            # Missing link in broken.  If EITHER endpoint is an added node, the
vibecomfy/demo_factory/deltas.py:393:            # Skip when an endpoint is an added node (witness covers it).
vibecomfy/demo_factory/deltas.py:675:    # absent endpoints) so the broken graph stays valid for the fixer + port check.
vibecomfy/registry/pack_resolver.py:61:    endpoint: str | None = None
vibecomfy/registry/pack_resolver.py:68:    endpoint: str
vibecomfy/registry/pack_resolver.py:81:            "endpoint": self.endpoint,
vibecomfy/registry/pack_resolver.py:330:            return PackResolution(query=class_name, query_type="class", ref=ref, cache_hit=cache_hit, endpoint=exact_path)
vibecomfy/registry/pack_resolver.py:339:                endpoint="/nodes/search?comfy_node_search=...",
vibecomfy/registry/pack_resolver.py:356:                return PackResolution(query=slug_or_name, query_type="slug", ref=ref, cache_hit=cache_hit, endpoint=id_path)
vibecomfy/registry/pack_resolver.py:365:            return PackResolution(query=slug_or_name, query_type="slug", ref=exact, candidates=tuple(candidates), cache_hit=cache_hit, endpoint=search_path)
vibecomfy/registry/pack_resolver.py:373:                endpoint=search_path,
vibecomfy/registry/pack_resolver.py:390:                endpoint=versions_path,
vibecomfy/registry/pack_resolver.py:398:                endpoint=f"/nodes/{quote(ref.registry_id or ref.slug, safe='')}",
vibecomfy/registry/pack_resolver.py:413:            endpoint=schema_path,
vibecomfy/registry/pack_resolver.py:535:                endpoint=MANAGER_NODE_MAP_URL if expected else MANAGER_NODE_LIST_URL,
vibecomfy/registry/pack_resolver.py:797:            endpoint=f"{GITHUB_API_BASE_URL}/search/code",
vibecomfy/registry/pack_resolver.py:816:            endpoint=f"{GITHUB_API_BASE_URL}/search/repositories",
vibecomfy/registry/pack_resolver.py:834:        endpoint=candidate.ref.url or "",
vibecomfy/registry/pack_resolver.py:1031:        endpoint=resolution.endpoint,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3111:    endpoint: "/vibecomfy/agent-edit/rebaseline",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3137:  const extracted = readRebaselineRecovery(payload, { endpoint: "recoveryForFailure", allowLegacy: true });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3150:    endpoint: typeof recovery.endpoint === "string" ? recovery.endpoint : null,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4335:      throw new Error(payload.raw?.error || "chat endpoint returned ok: false");
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4467:  const latestApplyCandidate = readRoundtripApplyCandidate(latest, { endpoint: "chat:latest-candidate" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4468:  const latestIdentity = readRoundtripTurnIdentity(latest, { endpoint: "chat:latest-candidate" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4843:    failure_kind: extra.failure_kind || null,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4879:      endpoint: "chat:message-response",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4890:        endpoint: "chat:message-outcome",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4900:          endpoint: "chat:message-candidate",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4912:          endpoint: "chat:message-identity",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4939:    throw new Error("chat endpoint must return an object");
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5011:        ? normalizeAgentEditResponse(rawPayload.latestCandidate, { endpoint: "chat:latest_candidate", allowLegacy: true })
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5013:          ? normalizeAgentEditResponse(rawPayload.latest_candidate, { endpoint: "chat:latest_candidate", allowLegacy: true })
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5021:function normalizeAuxiliaryAgentPayload(rawPayload, endpoint) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5023:    throw new Error(`${endpoint} response must be an object`);
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5032:    return normalizeAgentEditResponse(rawPayload, { endpoint, allowLegacy: true });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5144:  const selectorChanges = readRoundtripFieldChanges(result, { endpoint: "submit:field-changes" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5182:    readRoundtripFieldChanges(message, { endpoint: "chat:message-field-changes" })
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5186:          endpoint: "chat:message-field-changes",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5646:  const identity = readRoundtripTurnIdentity(result, { endpoint: "promote-pending-response" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5665:  const applyCandidate = readRoundtripApplyCandidate(result, { endpoint: "promote-pending-response" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5746:    failure_kind: kind,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5766:      endpoint: "/vibecomfy/agent-edit/rebaseline",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5842:      return readApplyCandidate(result, { endpoint: "batch-turn-reconcile", allowLegacy: true });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7728:      // authoritative stale-response guard if the transport cannot abort.
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7875:  const customNodeResolution = readCustomNodeResolution(result, { endpoint: "submit:custom-nodes" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8223:        const failureContextForAttempt = (extras = {}) => submitFlow.buildSubmitFailureContext(panel, snapshot, {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8255:            result = normalizeAgentEditResponse(rawResult, { endpoint: "submit", allowLegacy: true });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8265:                ...failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8277:          const submitIdentity = readRoundtripTurnIdentity(result, { endpoint: "submit:identity" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8293:                    failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8305:                    failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8314:          const submitCandidate = readRoundtripApplyCandidate(result, { endpoint: "submit:candidate" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8323:              ...failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8337:            failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8416:        failure_kind: failure.kind,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8439:    const turnIdentity = readRoundtripTurnIdentity(result, { endpoint: "submit:identity" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8440:    const applyCandidate = readRoundtripApplyCandidate(result, { endpoint: "submit:candidate" });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8764:async function postAgentLifecycleAction(endpoint, body, action) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8765:  const response = await fetch(`/vibecomfy/agent-edit/${endpoint}`, {
vibecomfy/demo_factory/run_campaign.py:333:        "The clip still starts and ends on my chosen images, but it no longer passes through the composition I supplied for the middle. Please restore that timed midpoint keyframe without changing the endpoints or duration.",
vibecomfy/demo_factory/run_campaign.py:609:        raise ValueError(f"bypass endpoint missing: {source_id} -> {target_id}")
vibecomfy/demo_factory/run_campaign.py:709:        raise ValueError(f"{spec.case_id} fault contains dangling link endpoints")
vibecomfy/demo_factory/run_campaign.py:789:    # type-tolerant link endpoints (``from_node_type``) for the removed
vibecomfy/demo_factory/run_campaign.py:811:    emission produced malformed slots the apply-validator misreads.
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:5:// It has no panel, lifecycle, DOM, app, transport, or rendering dependencies.
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:38:    || entry?.failure_kind
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:106:    failure_kind: event.failure_kind || null,
vibecomfy/demo_factory/creative.py:336:            # Skip malformed proposals
vibecomfy/demo_factory/creative.py:337:            print(f"Skipping malformed proposal: {e}")
vibecomfy/demo_factory/creative.py:592:                    # Preserve original endpoint value types (ComfyUI LiteGraph
vibecomfy/demo_factory/creative.py:595:                    # absent endpoints.
vibecomfy/demo_factory/creative.py:670:    - drops any link whose endpoint touches a removed node;
vibecomfy/comfy_nodes/web/projection_registry_v1.js:284:      const error = new Error("link must be a stable endpoint object or native six-tuple.");
vibecomfy/comfy_nodes/web/projection_registry_v1.js:285:      error.code = "malformed_link";
vibecomfy/demo_factory/ledger.py:20:    "| Case | Attempt | Source | Fault family | Inquiry | Baseline | Fault proof | "
vibecomfy/demo_factory/ledger.py:135:            f"- Attempt: {case.attempt}\n",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:42:  "failure_kind",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:109:  "malformed_delta",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:167:    endpoint: asString(recovery.endpoint),
vibecomfy/demo_factory/baseline.py:244:                    "malformed_node_record",
vibecomfy/demo_factory/baseline.py:274:                "malformed_link_collection",
vibecomfy/demo_factory/baseline.py:287:                    "malformed_raw_link",
vibecomfy/demo_factory/baseline.py:289:                    message=f"Raw link {index} is malformed.",
vibecomfy/demo_factory/baseline.py:311:                    "raw_link_missing_endpoint",
vibecomfy/demo_factory/baseline.py:319:                    message=f"Raw link {link_id} references a missing endpoint.",
vibecomfy/demo_factory/baseline.py:510:def _credible_missing_required(
vibecomfy/demo_factory/baseline.py:565:    if detail.get("compile_code") != "compiled_edge_missing_endpoint":
vibecomfy/demo_factory/baseline.py:620:        "compiled_edge_missing_endpoint",
vibecomfy/demo_factory/baseline.py:765:        if code == "missing_required_input":
vibecomfy/demo_factory/baseline.py:766:            if _credible_missing_required(diag, nodes):
vibecomfy/demo_factory/baseline.py:793:                hard_blockers.append(_as_blocker(diag, reason="compiled_edge_endpoint"))
vibecomfy/porting/refuse.py:359:            for endpoint in resolved:
vibecomfy/porting/refuse.py:360:                add_ref(endpoint)
vibecomfy/demo_factory/transcript.py:63:        If JSON files are malformed or missing required fields.
vibecomfy/demo_factory/predicates.py:299:            return False, "graph contains a malformed link"
vibecomfy/demo_factory/predicates.py:307:            return False, "graph contains a link with a missing endpoint"
vibecomfy/demo_factory/predicates.py:512:            # under a fresh id), match that endpoint by node TYPE instead of id
vibecomfy/demo_factory/predicates.py:549:            # If no concrete ids resolved for a typed endpoint, fall back to
vibecomfy/demo_factory/predicates.py:649:    """Return the candidate node ids for a link endpoint.
vibecomfy/demo_factory/predicates.py:651:    If ``node_type`` is given (additive restore: the endpoint is a re-added
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:22://   * fetch / POST (transport),
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:124:    endpoint: options.endpoint || "submit:field-changes",
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:248: * The orchestrator owns transport (the actual fetch), abort-controller
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:320:  const turnIdentity = readCommitTurnIdentity(selectorSource, { endpoint: "submit:identity" });
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:321:  const applyCandidate = readCommitApplyCandidate(selectorSource, { endpoint: "submit:candidate" });
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:389:            endpoint: "submit:custom-nodes",
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:489:      // failure → treat as a malformed terminal. The orchestrator may pass an
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:491:      // failure object is synthesized (no transport/error-utility imports here).
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:521: * The orchestrator owns transport (fetch chat detail), scoped-storage writes,
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:573: * The orchestrator owns transport (the accept POST / CAS decision), canvas
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:597: * still own source metadata, graph visualization, rendering, and transport.
vibecomfy/demo_factory/fixer.py:34:    no ``compiled_api`` twin is written. ``workflow_id`` is a transport stamp
vibecomfy/porting/wrappers/discovery.py:15:``/object_info`` endpoint *filtered to a single pack* (i.e. ``{class_name:
vibecomfy/comfy_nodes/web/comfy_adapter.js:49:    this.code = code || "malformed_delta";
vibecomfy/comfy_nodes/web/comfy_adapter.js:851:    throw new Error(`Invalid ${direction} endpoint reference.`);
vibecomfy/comfy_nodes/web/comfy_adapter.js:857:    throw new Error(`Could not resolve ${direction} endpoint node ${parsed.uidOrId}.`);
vibecomfy/comfy_nodes/web/comfy_adapter.js:862:    throw new Error(`Could not resolve ${direction} endpoint slot ${String(ref[2])}.`);
vibecomfy/comfy_nodes/web/comfy_adapter.js:1052:      // that edge. This guarantees every endpoint exists before the edge is
vibecomfy/comfy_nodes/web/comfy_adapter.js:1275:    // A malformed extension node must never block review; retain server geometry.
vibecomfy/comfy_nodes/web/comfy_adapter.js:1504: * the candidate graph and that link endpoints are resolvable.
vibecomfy/comfy_nodes/web/comfy_adapter.js:1581:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1668:      // Links are applied as explicit follow-up operations once every endpoint
vibecomfy/comfy_nodes/web/comfy_adapter.js:1706:  // explicit op so all endpoints are known; restore persisted operation
vibecomfy/comfy_nodes/web/comfy_adapter.js:1813:      "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1822:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1829:        "malformed_delta",
vibecomfy/porting/cache/object_info/ComfyUI-LTXVideo@runpod-snapshot.json:4735:    "description": "Selects a range of frames from the video latent. start_index and end_index define a closed interval (inclusive of both endpoints).",
vibecomfy/comfy_nodes/web/preview_picker.js:15:// The server endpoint is the source of truth for whether demo mode exists. A
vibecomfy/comfy_nodes/web/preview_picker.js:16:// missing/disabled endpoint leaves no UI mounted and no panel state touched.
vibecomfy/comfy_nodes/web/preview_picker.js:471:      // never escape into production persistence or transport. In particular,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:180:    endpoint: asString(recovery.endpoint),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:285:    || asString(response.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:307:function normalizePublicOutcome(rawOutcome, response, { allowLegacy, endpoint }) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:312:      `Agent edit response${endpoint ? ` for ${endpoint}` : ""} is missing outcome.kind.`,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:377:      `Agent edit response${endpoint ? ` for ${endpoint}` : ""} has unsupported outcome.kind ${JSON.stringify(kind)}.`,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:391:function inferLegacyOutcome(response, { endpoint }) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:458:    `Agent edit response${endpoint ? ` for ${endpoint}` : ""} is missing outcome and could not be inferred.`,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:468:  // SD2: both session_id and turn_id must be absent for malformed/non-applyable.
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:525:  // malformed/non-applyable, never stale/rebaseline. Suppress Apply and
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:754:      endpoint: options.endpoint ? `${options.endpoint}:message-response` : "message-response",
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:887:export function normalizeAgentEditResponse(raw, { endpoint = null, allowLegacy = true } = {}) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:893:      `Agent edit response${endpoint ? ` for ${endpoint}` : ""} must be an object.`,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:898:    ? normalizePublicOutcome(raw.outcome, raw, { allowLegacy, endpoint })
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:900:      ? inferLegacyOutcome(raw, { endpoint })
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:903:          `Agent edit response${endpoint ? ` for ${endpoint}` : ""} is missing outcome.`,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:913:  // turn_id is malformed/non-applyable, never stale/rebaseline. Prevent
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:925:      endpoint: endpoint ? `${endpoint}:latest_candidate` : "latest_candidate",
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:933:    endpoint,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:994:    failureKind: asString(raw.failureKind) || asString(raw.failure_kind),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1022:      ? raw.messages.map((message) => normalizeMessage(message, { endpoint, allowLegacy }))
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1627:    failure_kind: asString(source.failure_kind) || asString(source.failureKind) || asString(outcome?.failure_kind),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1891:      asString(entry.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1921:      || asString(normalized.outcome.failure_kind)
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:97:      code: "malformed_restoration_payload",
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:123:function _endpoint(ref) {
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:124:  // delta endpoint ref shape: ["", uid, port] (root-scoped).
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:191:          from: _endpoint(op.from),
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:192:          to: _endpoint(op.to),
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:199:          to: _endpoint(op.to),
vibecomfy/porting/convert.py:167:    Captures uid, type, channel name, pos/size, and the routed endpoints for each
vibecomfy/porting/convert.py:190:        endpoints = [
vibecomfy/porting/convert.py:200:            "endpoints": endpoints,
vibecomfy/comfy_nodes/web/canonical_delta.js:24:export const DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta";
vibecomfy/comfy_nodes/web/canonical_delta.js:334:      code: "canonical_envelope_malformed_ops",
vibecomfy/porting/layout/reconcile.py:72:    # virtual wires from prior_store with at least one endpoint uid in removed
vibecomfy/porting/layout/reconcile.py:651:                _ep = _vw_entry.get("endpoints")
vibecomfy/comfy_nodes/web/agent_edit_node_pack_installer.js:23:    const res = await fetchImpl(request.endpoint || "/vibecomfy/node-packs/install", {
vibecomfy/porting/layout/lanes.py:77:    # Process every edge (undirected — one edge joins both endpoints).
vibecomfy/porting/layout/layering.py:185:    endpoints are dropped with a debug log.
vibecomfy/porting/layout_store.py:26:        "<uid>": {"type": <str>, "channel": <str>, "endpoints": [...]}
vibecomfy/porting/layout_store.py:374:    Pass 2 — re-key endpoints
vibecomfy/porting/layout_store.py:379:    ``extra['unkeyed_endpoints']`` (never silently dropped).
vibecomfy/porting/layout_store.py:384:    ``virtual_wires``, and ``unkeyed`` / ``extra.unkeyed_endpoints`` for
vibecomfy/porting/layout_store.py:411:    # ── Pass 2: re-key endpoint integers in groups, virtual_wires, definitions ─
vibecomfy/porting/layout_store.py:412:    unkeyed_endpoints: list[Any] = []
vibecomfy/porting/layout_store.py:415:        """Resolve a litegraph integer endpoint to its uid, or flag unresolved."""
vibecomfy/porting/layout_store.py:421:            unkeyed_endpoints.append(ref)
vibecomfy/porting/layout_store.py:437:    # extra — carry forward as-is but re-key virtual_wires endpoints
vibecomfy/porting/layout_store.py:448:        if isinstance(vw_copy.get("endpoints"), list):
vibecomfy/porting/layout_store.py:449:            vw_copy["endpoints"] = [_rekey(ep) for ep in vw_copy["endpoints"]]
vibecomfy/porting/layout_store.py:452:    if unkeyed_endpoints:
vibecomfy/porting/layout_store.py:453:        extra["unkeyed_endpoints"] = unkeyed_endpoints
vibecomfy/comfy_nodes/agent/_frag_ingest.py:62:        "endpoint": "/vibecomfy/agent-edit/rebaseline",
vibecomfy/comfy_nodes/agent/_frag_ingest.py:73:        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:130:            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
vibecomfy/comfy_nodes/agent/_frag_ingest.py:178:            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
vibecomfy/comfy_nodes/agent/_frag_ingest.py:384:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/porting/edit/lint.py:14:- Link indexing covers both link-id and endpoint-based lookups.
vibecomfy/porting/edit/lint.py:23:- **issues** (typed errors for unknown targets / fields / malformed ops)
vibecomfy/porting/edit/lint.py:150:    malformed ops are rejected).  ``normalizations`` records the disposition
vibecomfy/porting/edit/lint.py:658:    """Return the first existing link that matches the given endpoints.
vibecomfy/porting/edit/lint.py:957:    Resolves source/target uids, validates endpoint slots exist,
vibecomfy/porting/edit/lint.py:1009:    # No-op detection: link already exists with same endpoints
vibecomfy/porting/edit/lint.py:1057:      the target endpoint.
vibecomfy/porting/edit/lint.py:1081:        # Look for any link that matches the target endpoint
vibecomfy/porting/edit/lint.py:1117:        "malformed_op",
vibecomfy/schema/validate.py:155:                        "missing_required_input",
vibecomfy/porting/edit/apply.py:31:    _link_endpoints,
vibecomfy/porting/edit/apply.py:102:    _resolve_source_endpoint,
vibecomfy/porting/edit/apply.py:103:    _resolve_target_endpoint,
vibecomfy/porting/edit/apply.py:130:    _endpoint_port_issues,
vibecomfy/schema/call_validation.py:66:                    "missing_required_input",
vibecomfy/porting/cache/object_info/ComfyUI-KJNodes@runpod-snapshot.json:23237:    "description": "Attempt to implement https://github.com/agwmon/self-refine-video, for testing only, MAY NOT WORK AS INTENDED.",
vibecomfy/porting/edit/apply_resolve_base.py:31:    _endpoint_port_issues,
vibecomfy/porting/edit/apply_resolve_base.py:499:                "Link endpoints must resolve within the same scope.",
vibecomfy/porting/edit/apply_resolve_base.py:506:    source, source_issues = _resolve_source_endpoint(ledger, op.source, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_resolve_base.py:509:    target, target_issues = _resolve_target_endpoint(ledger, op.target, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_resolve_base.py:516:                "non_numeric_link_endpoint",
vibecomfy/porting/edit/apply_resolve_base.py:517:                "Link endpoints must have numeric LiteGraph node ids.",
vibecomfy/porting/edit/apply_resolve_base.py:620:def _resolve_source_endpoint(
vibecomfy/porting/edit/apply_resolve_base.py:627:    result = _ctx.resolve_source_endpoint(backend, ref, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_resolve_base.py:629:        return None, _endpoint_port_issues(result)
vibecomfy/porting/edit/apply_resolve_base.py:648:def _resolve_target_endpoint(
vibecomfy/porting/edit/apply_resolve_base.py:655:    result = _ctx.resolve_target_endpoint(backend, ref, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_resolve_base.py:657:        return None, _endpoint_port_issues(result)
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:61:  // Apply must never trust malformed authority. Reject is different: it only
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:62:  // discards server-held candidate state, and the reject endpoint rechecks the
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:177:      // A malformed aggregate is not downgraded to legacy browser state.
vibecomfy/porting/edit/projection.py:218:        "Link endpoints: from [scope_path, uid, output_slot] to [scope_path, uid, input_field].",
vibecomfy/schema/provider.py:188:                "passthrough_on_non_json": InputSpec("BOOLEAN", required=False),
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
vibecomfy/porting/cache/object_info/comfy_core@object_info_comfyui_0.24.0.1.json:59824:    "description": "Generates images synchronously via OpenAI's DALL·E 2 endpoint.",
vibecomfy/porting/cache/object_info/comfy_core@object_info_comfyui_0.24.0.1.json:59953:    "description": "Generates images synchronously via OpenAI's DALL·E 3 endpoint.",
vibecomfy/porting/cache/object_info/comfy_core@object_info_comfyui_0.24.0.1.json:60080:    "description": "Generates images synchronously via OpenAI's GPT Image endpoint.",
vibecomfy/porting/cache/object_info/comfy_core@object_info_comfyui_0.24.0.1.json:60289:    "description": "Generates images via OpenAI's GPT Image endpoint.",
vibecomfy/porting/widget_shape_fence.py:111:    malformed_new_raw_ui = (
vibecomfy/porting/widget_shape_fence.py:116:        # ingest) is only "malformed" if it actually has a widget-shape problem
vibecomfy/porting/widget_shape_fence.py:125:    if malformed_new_raw_ui:
vibecomfy/testing/assertions.py:452:    endpoint references a node that exists.
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:792://   - ``malformed_delta`` — structurally invalid envelope or op
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1733:    endpoint: "/vibecomfy/node-packs/install",
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1886:  // malformed/non-applyable. Override eligibility to block Apply with
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1979:    ...(missingDurableEligibility ? { debug_branch: "malformed_metadata" } : {}),
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2645:        failure_kind: event.failure_kind || null,
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3710:    endpoint: typeof recovery.endpoint === "string" ? recovery.endpoint : null,
vibecomfy/comfy_nodes/web/agent_flow_deps.js:5:// *inactivity*, not total request duration, and leaves a small transport / job
vibecomfy/porting/edit/apply_gate.py:9:from vibecomfy.porting.edit.apply_links import _link_endpoints, _link_id, _link_ids_targeting_input, _node_by_id
vibecomfy/porting/edit/apply_gate.py:211:    def allow_link_endpoint_paths(scope_path: str, link_id: int) -> None:
vibecomfy/porting/edit/apply_gate.py:213:        origin_id, _, target_id, _ = _link_endpoints(link)
vibecomfy/porting/edit/apply_gate.py:217:    def allow_candidate_link_endpoint_paths(scope_path: str, link_id: int) -> None:
vibecomfy/porting/edit/apply_gate.py:219:        origin_id, _, target_id, _ = _link_endpoints(link)
vibecomfy/porting/edit/apply_gate.py:235:                allow_link_endpoint_paths(op.target.scope_path, resolved.automatic_link_removal)
vibecomfy/porting/edit/apply_gate.py:254:                allow_candidate_link_endpoint_paths(op.target.scope_path, new_link_id)
vibecomfy/porting/edit/apply_gate.py:275:                        allow_link_endpoint_paths(op.target.scope_path, old_link_id)
vibecomfy/porting/edit/apply_gate.py:279:                    allow_link_endpoint_paths(op.target.scope_path, old_link_id)
vibecomfy/porting/edit/apply_gate.py:284:            allow_link_endpoint_paths(resolved.scope_path, resolved.link_id)
vibecomfy/porting/edit/apply_gate.py:291:                allow_link_endpoint_paths(op.target.scope_path, link_id)
vibecomfy/porting/edit/apply_gate.py:294:                allow_link_endpoint_paths(rewire.scope_path, rewire.link_id)
vibecomfy/porting/edit/apply_gate.py:306:                allow_candidate_link_endpoint_paths(resolved.scope_path, link_id)
vibecomfy/comfy_nodes/web/panel_overlay.js:1467:        // same edit.  Do not turn the serialized endpoint object into a
vibecomfy/comfy_nodes/web/panel_overlay.js:1618:          // Passing the output predicate here mirrors every live endpoint:
vibecomfy/comfy_nodes/web/panel_overlay.js:1721:        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — unresolvable removed-wire endpoint:", rem);
vibecomfy/comfy_nodes/web/panel_overlay.js:1727:        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — could not resolve removed-wire endpoint positions:", rem);
vibecomfy/comfy_nodes/web/panel_overlay.js:1751:        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — unresolvable added-wire endpoint:", add);
vibecomfy/comfy_nodes/web/panel_overlay.js:1757:        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — could not resolve added-wire endpoint positions:", add);
vibecomfy/comfy_backend.py:60:    All fields are required; missing / malformed JSON raises immediately
vibecomfy/comfy_nodes/web/panel_thread.js:2430:  if (entry.failure_kind) {
vibecomfy/comfy_nodes/web/panel_thread.js:2431:    appendTextLine(turnCard, `${entry.failure_kind}${entry.failure_stage ? ` @ ${entry.failure_stage}` : ""}`, "#ffb86c");
vibecomfy/porting/edit/ops.py:51:DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta"
vibecomfy/porting/edit/ops.py:801:        # Bridge only: current model-facing transport is still a flat list.
vibecomfy/porting/edit/apply_links.py:22:    return [link for link in links if _link_endpoints(link)[0] == node_id]
vibecomfy/porting/edit/apply_links.py:29:    return [link for link in links if _link_endpoints(link)[2] == node_id]
vibecomfy/porting/edit/apply_links.py:153:    origin_id, origin_slot, _, _ = _link_endpoints(inbound_links[0])
vibecomfy/porting/edit/apply_links.py:190:        origin_id, origin_slot, target_id, target_slot = _link_endpoints(link)
vibecomfy/porting/edit/apply_links.py:211:        _, _, found_target_id, found_target_slot = _link_endpoints(link)
vibecomfy/porting/edit/apply_links.py:237:        old_origin_slot = _link_endpoints(link)[1]
vibecomfy/porting/edit/apply_links.py:359:def _link_endpoints(link: Any) -> tuple[int | None, int | None, int | None, int | None]:
vibecomfy/porting/edit/_gates.py:10:    _changed_edge_endpoint_node_ids,
vibecomfy/porting/edit/_gates.py:320:        region.update(_changed_edge_endpoint_node_ids(original_api, working_api))
vibecomfy/porting/edit/_gates.py:321:        region.update(_changed_edge_endpoint_node_ids(original_api, candidate_api))
vibecomfy/porting/edit/apply_mutate.py:7:from vibecomfy.porting.edit.apply_links import _ensure_input_slot, _ensure_output_link_reference, _link_endpoints, _link_ids_targeting_input, _new_link_for_scope, _remove_link_from_scope, _remove_node_from_scope, _rewire_link_origin, _set_input_link_reference
vibecomfy/porting/edit/apply_mutate.py:124:        origin_id, _, target_id, _ = _link_endpoints(link) if link is not None else (None, None, None, None)
vibecomfy/porting/edit/_parse_execute.py:397:            endpoint = statement.detail.get("resolved_endpoint")
vibecomfy/porting/edit/_parse_execute.py:398:            if not isinstance(endpoint, _ResolvedOutputEndpoint):
vibecomfy/porting/edit/_parse_execute.py:400:                    _diag("missing_resolved_endpoint", "Link assignment was missing its resolved source endpoint.", severity="error"),
vibecomfy/porting/edit/_parse_execute.py:402:            source_slot: str | int = endpoint.slot_name if endpoint.slot_index is None else endpoint.slot_name
vibecomfy/porting/edit/_parse_execute.py:406:                    source=LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, source_slot),
vibecomfy/porting/edit/normalize.py:343:    """Attempt to normalize through real LiteGraph serialize→configure→serialize.
vibecomfy/porting/edit/_ir_utils.py:347:def _changed_edge_endpoint_node_ids(
vibecomfy/porting/edit/apply_types.py:462:def _endpoint_port_issues(result: Any) -> list[PortIssue]:
vibecomfy/porting/edit/apply_types.py:463:    """Convert ResolveResult issues for endpoint resolvers, remapping uid error codes."""
vibecomfy/comfy_nodes/agent/_frag_chat.py:348:    Transaction receipts use the same event schema as the reconcile endpoint.
vibecomfy/comfy_nodes/agent/_frag_chat.py:479:# endpoint is fetched on every page reload, so the embedded reasoning must stay
vibecomfy/comfy_nodes/agent/_frag_chat.py:764:        # Defensively skip malformed entries (non-dict, missing role,
vibecomfy/porting/edit/_resolve.py:559:                endpoint, endpoint_issues = self._resolve_rhs_endpoint(rhs, target=field_target)
vibecomfy/porting/edit/_resolve.py:560:                if endpoint_issues:
vibecomfy/porting/edit/_resolve.py:567:                        diagnostics=tuple(endpoint_issues),
vibecomfy/porting/edit/_resolve.py:569:                assert endpoint is not None
vibecomfy/porting/edit/_resolve.py:576:                    detail={"resolved_target": field_target, "resolved_endpoint": endpoint, "ast_node": statement, "constant_env": dict(env)},
vibecomfy/porting/edit/_resolve.py:1177:                endpoint, endpoint_issues = self._resolve_rhs_endpoint(keyword.value, target=target)
vibecomfy/porting/edit/_resolve.py:1178:                if endpoint_issues:
vibecomfy/porting/edit/_resolve.py:1179:                    issues.extend(endpoint_issues)
vibecomfy/porting/edit/_resolve.py:1181:                assert endpoint is not None
vibecomfy/porting/edit/_resolve.py:1182:                linked_inputs[name] = LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, endpoint.slot_name)
vibecomfy/porting/edit/_resolve.py:1498:    def _resolve_rhs_endpoint(
vibecomfy/porting/edit/apply_resolve_add.py:17:from vibecomfy.porting.edit.apply_resolve_base import _resolve_node, _resolve_scope, _resolve_source_endpoint
vibecomfy/porting/edit/apply_resolve_add.py:147:                    "missing_required_add_node_input",
vibecomfy/porting/edit/apply_resolve_add.py:219:                    "add_node input endpoints must resolve within the same scope.",
vibecomfy/porting/edit/apply_resolve_add.py:242:        source_ref, source_issues = _resolve_source_endpoint(ledger, source, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_resolve_add.py:249:                    "non_numeric_link_endpoint",
vibecomfy/porting/edit/session.py:83:    _changed_edge_endpoint_node_ids,
vibecomfy/porting/cache/object_info/comfy_core@runpod-snapshot.json:33755:    "description": "Generates images synchronously via OpenAI's DALL\u00b7E 2 endpoint.",
vibecomfy/porting/cache/object_info/comfy_core@runpod-snapshot.json:33878:    "description": "Generates images synchronously via OpenAI's DALL\u00b7E 3 endpoint.",
vibecomfy/porting/cache/object_info/comfy_core@runpod-snapshot.json:33999:    "description": "Generates images synchronously via OpenAI's GPT Image endpoint.",
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:78:// endpoint.  But a canonical rewire is `remove_link(to=X)` followed by
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:211:        throw _fail("Inverse remove_link endpoint mismatch", "inverse_missing_prior_state");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:216:      throw _fail("Inverse upsert_link endpoint mismatch", "inverse_missing_prior_state");
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
vibecomfy/comfy_nodes/web/agent_apply_flow.js:129:    // sequence must remove its link before either endpoint; conversely the
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
vibecomfy/porting/edit/_describe.py:481:        links = self._graph_link_endpoints()
vibecomfy/porting/edit/_describe.py:521:    def _graph_link_endpoints(self) -> list[tuple[int | None, int | None, int | None, int | None]]:

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/contracts.py | sed -n '1,290p'; nl -ba vibecomfy/executor/contracts.py | sed -n '290,520p'; git diff --unified=25 45415680..1bd1b04b -- vibecomfy/executor/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
     1	"""Typed data contracts for the embedded VibeComfy executor.
     2
     3	These are the public shapes that flow through the classify → research →
     4	implement → reply pipeline.  Every contract is a frozen dataclass with a
     5	canonical ``to_dict()`` serializer so the executor can produce the standard
     6	``success_envelope`` shape without adding new top-level response fields.
     7	"""
     8
     9	from __future__ import annotations
    10
    11	import logging
    12	import re
    13	from dataclasses import dataclass, field
    14	from types import MappingProxyType
    15	from typing import Any, Mapping
    16	from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    17
    18	from vibecomfy.agent.deepseek_usage import coerce_deepseek_usage
    19
    20	LOGGER = logging.getLogger(__name__)
    21
    22	_WARNING_DETAIL_MAX_MESSAGE = 160
    23	_SENSITIVE_QUERY_KEYS = frozenset({
    24	    "api_key",
    25	    "apikey",
    26	    "auth",
    27	    "authorization",
    28	    "key",
    29	    "password",
    30	    "secret",
    31	    "sig",
    32	    "signature",
    33	    "token",
    34	})
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
    52	_MODEL_ATTEMPT_AUTHORIZATION_HEADER_RE = re.compile(
    53	    r"(?im)\bauthorization\s*:\s*[^\r\n]*"
    54	)
    55	_MODEL_ATTEMPT_URL_RE = re.compile(r"https?://[^\s<>\"']+")
    56
    57
    58	def normalize_model_endpoint(value: Any) -> str:
    59	    """Return a credential-free, query-free endpoint or ``"unknown"``.
    60
    61	    Model-attempt evidence intentionally records only the scheme, host, port,
    62	    and normalized path. Userinfo, query parameters, and fragments are never
    63	    provenance and can contain credentials, so they are discarded wholesale.
    64	    """
    65	    if not isinstance(value, str) or not value.strip():
    66	        return _MODEL_ATTEMPT_UNKNOWN
    67	    try:
    68	        parsed = urlsplit(value.strip())
    69	    except ValueError:
    70	        return _MODEL_ATTEMPT_UNKNOWN
    71	    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
    72	        return _MODEL_ATTEMPT_UNKNOWN
    73	    host = parsed.hostname.lower()
    74	    if ":" in host and not host.startswith("["):
    75	        host = f"[{host}]"
    76	    try:
    77	        port = parsed.port
    78	    except ValueError:
    79	        return _MODEL_ATTEMPT_UNKNOWN
    80	    netloc = f"{host}:{port}" if port is not None else host
    81	    path = re.sub(r"/{2,}", "/", parsed.path or "")
    82	    if path != "/":
    83	        path = path.rstrip("/")
    84	    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))
    85
    86
    87	def redact_model_preview(value: Any, *, limit: int = _MODEL_ATTEMPT_PREVIEW_LIMIT) -> str | None:
    88	    """Return a bounded failure preview with credentials and URL queries removed."""
    89	    if not isinstance(value, str):
    90	        return None
    91	    redacted = _MODEL_ATTEMPT_AUTHORIZATION_HEADER_RE.sub(
    92	        "Authorization: <redacted>", value
    93	    )
    94	    normalized = " ".join(redacted.strip().split())
    95	    if not normalized:
    96	        return None
    97	    normalized = _MODEL_ATTEMPT_URL_RE.sub(
    98	        lambda match: normalize_model_endpoint(match.group(0)), normalized
    99	    )
   100	    normalized = _MODEL_ATTEMPT_BEARER_RE.sub("Bearer <redacted>", normalized)
   101	    normalized = _MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE.sub(
   102	        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", normalized
   103	    )
   104	    if len(normalized) > limit:
   105	        normalized = normalized[: limit - 1].rstrip() + "…"
   106	    return normalized
   107
   108
   109	def _model_attempt_text(value: Any) -> str:
   110	    if isinstance(value, str) and value.strip():
   111	        return value.strip()
   112	    return _MODEL_ATTEMPT_UNKNOWN
   113
   114
   115	def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
   116	    usage = value if isinstance(value, Mapping) else {}
   117	    normalized: dict[str, int | str] = {}
   118	    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
   119	        token_value = usage.get(key)
   120	        normalized[key] = (
   121	            max(0, int(token_value))
   122	            if isinstance(token_value, (int, float)) and not isinstance(token_value, bool)
   123	            else _MODEL_ATTEMPT_UNKNOWN
   124	        )
   125	    return normalized
   126
   127
   128	@dataclass(frozen=True)
   129	class ModelAttemptEvidence:
   130	    """Canonical evidence for one actual model-provider call.
   131
   132	    The shape is shared by worker envelopes, runtime/provider results, executor
   133	    reports, durable artifacts, and the live harness. Raw model output is never
   134	    retained on success and is bounded/redacted on failure.
   135	    """
   136
   137	    phase: str = _MODEL_ATTEMPT_UNKNOWN
   138	    attempt: int = 1
   139	    outcome: str = "failure"
   140	    failure_type: str | None = None
   141	    requested_model: str = _MODEL_ATTEMPT_UNKNOWN
   142	    resolved_model: str = _MODEL_ATTEMPT_UNKNOWN
   143	    adapter: str = _MODEL_ATTEMPT_UNKNOWN
   144	    provider: str = _MODEL_ATTEMPT_UNKNOWN
   145	    transport: str = _MODEL_ATTEMPT_UNKNOWN
   146	    endpoint: str = _MODEL_ATTEMPT_UNKNOWN
   147	    finish_reason: str = _MODEL_ATTEMPT_UNKNOWN
   148	    token_usage: Mapping[str, Any] = field(default_factory=dict)
   149	    raw_response_preview: str | None = None
   150
   151	    def __post_init__(self) -> None:
   152	        outcome = self.outcome if self.outcome in _MODEL_ATTEMPT_OUTCOMES else "failure"
   153	        failure_type = self.failure_type
   154	        if outcome == "success":
   155	            failure_type = None
   156	        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
   157	            failure_type = "provider_failure"
   158	        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
   159	        object.__setattr__(self, "attempt", max(1, int(self.attempt or 1)))
   160	        object.__setattr__(self, "outcome", outcome)
   161	        object.__setattr__(self, "failure_type", failure_type)
   162	        for name in (
   163	            "requested_model", "resolved_model", "adapter", "provider",
   164	            "transport", "finish_reason",
   165	        ):
   166	            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
   167	        object.__setattr__(self, "endpoint", normalize_model_endpoint(self.endpoint))
   168	        object.__setattr__(
   169	            self,
   170	            "token_usage",
   171	            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
   172	        )
   173	        preview = (
   174	            redact_model_preview(self.raw_response_preview)
   175	            if outcome == "failure"
   176	            else None
   177	        )
   178	        object.__setattr__(self, "raw_response_preview", preview)
   179
   180	    @classmethod
   181	    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
   182	        return cls(
   183	            phase=value.get("phase", _MODEL_ATTEMPT_UNKNOWN),
   184	            attempt=value.get("attempt", 1),
   185	            outcome=value.get("outcome", "failure"),
   186	            failure_type=value.get("failure_type"),
   187	            requested_model=value.get("requested_model", _MODEL_ATTEMPT_UNKNOWN),
   188	            resolved_model=value.get("resolved_model", _MODEL_ATTEMPT_UNKNOWN),
   189	            adapter=value.get("adapter", _MODEL_ATTEMPT_UNKNOWN),
   190	            provider=value.get("provider", _MODEL_ATTEMPT_UNKNOWN),
   191	            transport=value.get("transport", _MODEL_ATTEMPT_UNKNOWN),
   192	            endpoint=value.get("endpoint", _MODEL_ATTEMPT_UNKNOWN),
   193	            finish_reason=value.get("finish_reason", _MODEL_ATTEMPT_UNKNOWN),
   194	            token_usage=value.get("token_usage", {}),
   195	            raw_response_preview=value.get("raw_response_preview"),
   196	        )
   197
   198	    def to_dict(self) -> dict[str, Any]:
   199	        payload: dict[str, Any] = {
   200	            "phase": self.phase,
   201	            "attempt": self.attempt,
   202	            "outcome": self.outcome,
   203	            "failure_type": self.failure_type,
   204	            "requested_model": self.requested_model,
   205	            "resolved_model": self.resolved_model,
   206	            "adapter": self.adapter,
   207	            "provider": self.provider,
   208	            "transport": self.transport,
   209	            "endpoint": self.endpoint,
   210	            "finish_reason": self.finish_reason,
   211	            "token_usage": dict(self.token_usage),
   212	        }
   213	        if self.outcome == "failure" and self.raw_response_preview:
   214	            payload["raw_response_preview"] = self.raw_response_preview
   215	        return payload
   216
   217
   218	def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
   219	    """Normalize untrusted attempt mappings into the canonical serialized shape."""
   220	    if not isinstance(value, (list, tuple)):
   221	        return ()
   222	    attempts: list[dict[str, Any]] = []
   223	    for item in value:
   224	        if isinstance(item, ModelAttemptEvidence):
   225	            attempts.append(item.to_dict())
   226	        elif isinstance(item, Mapping):
   227	            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
   228	    return tuple(attempts)
   229
   230
   231	_NODE_TYPE_MARKER_RE = re.compile(
   232	    r"(?:class(?:_type|\s+type)?|node(?:\s+of)?(?:\s+type)?|of\s+type)\s*[:=]?\s*"
   233	    r"([A-Za-z_][A-Za-z0-9_.:-]*)",
   234	    re.IGNORECASE,
   235	)
   236	_NODE_TYPE_VERB_RE = re.compile(
   237	    r"\b(?:add|insert|create|restore|replace|remove|change|edit)\s+"
   238	    r"(?:(?:an?|the|new|another|some|one)\s+)*"
   239	    r"([A-Za-z_][A-Za-z0-9_.:-]*)\b",
   240	    re.IGNORECASE,
   241	)
   242	_NON_NODE_TYPE_TOKENS = frozenset({
   243	    "a", "an", "the", "node", "nodes", "class", "type", "of", "to",
   244	    "with", "for", "from", "into", "on", "in", "and", "or", "value",
   245	    "setting", "settings", "field", "fields", "widget", "widgets", "new",
   246	})
   247	_UI_ONLY_ANNOTATION_CLASS_TYPES = frozenset({
   248	    "annotation",
   249	    "annotationnode",
   250	    "comment",
   251	    "commentnode",
   252	    "markdown",
   253	    "markdownnote",
   254	    "markdownnotenode",
   255	    "note",
   256	    "notenode",
   257	    "workflowcomment",
   258	    "workflowmarkdown",
   259	    "workflownote",
   260	})
   261
   262
   263	def is_ui_only_annotation_class_type(class_type: Any) -> bool:
   264	    """Return whether a class name denotes a known no-dataflow UI annotation.
   265
   266	    Keep this deliberately conservative: reroutes, primitives, groups, and
   267	    other frontend components can participate in dataflow or component
   268	    expansion and therefore are not skipped merely because they are UI nodes.
   269	    """
   270	    normalized = re.sub(r"[^a-z0-9]", "", str(class_type or "").casefold())
   271	    return normalized in _UI_ONLY_ANNOTATION_CLASS_TYPES
   272
   273
   274	def parse_target_node_type(change_goal: str) -> str:
   275	    """Extract a likely ComfyUI class-type token from a change goal.
   276
   277	    Classifier metadata is intentionally best-effort.  The parser only uses
   278	    explicit node/type markers or an edit verb followed by a token, and returns
   279	    an empty string when the sentence is too ambiguous to bind safely.
   280	    """
   281	    if not isinstance(change_goal, str) or not change_goal.strip():
   282	        return ""
   283
   284	    candidates: list[str] = []
   285	    marker = _NODE_TYPE_MARKER_RE.search(change_goal)
   286	    if marker:
   287	        candidates.append(marker.group(1))
   288	    verb = _NODE_TYPE_VERB_RE.search(change_goal)
   289	    if verb:
   290	        candidates.append(verb.group(1))
   290	        candidates.append(verb.group(1))
   291
   292	    for candidate in candidates:
   293	        token = candidate.strip(".,;()[]{}\"'")
   294	        if token and token.casefold() not in _NON_NODE_TYPE_TOKENS:
   295	            return token
   296	    return ""
   297
   298
   299	def _freeze_jsonish(value: Any) -> Any:
   300	    if isinstance(value, Mapping):
   301	        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
   302	    if isinstance(value, (list, tuple)):
   303	        return tuple(_freeze_jsonish(v) for v in value)
   304	    return value
   305
   306
   307	def _thaw_jsonish(value: Any) -> Any:
   308	    if isinstance(value, Mapping):
   309	        return {str(k): _thaw_jsonish(v) for k, v in value.items()}
   310	    if isinstance(value, tuple):
   311	        return [_thaw_jsonish(v) for v in value]
   312	    return value
   313
   314
   315	_ADAPTATION_PLAN_FOLLOWUPS: tuple[str, ...] = (
   316	    "apply_bound_current_graph_edit_if_schema_sufficient",
   317	    "build_execution_plan_with_required_nodes_and_rewires",
   318	    "typed_refusal_or_clarification_if_authoring_surface_missing",
   319	)
   320
   321
   322	def _adaptation_plan_field(value: Any, key: str, default: Any = None) -> Any:
   323	    if isinstance(value, Mapping):
   324	        return value.get(key, default)
   325	    return getattr(value, key, default)
   326
   327
   328	def adaptation_plan_actionability(value: Any) -> tuple[str, str]:
   329	    """Return ``("actionable", "")`` or ``("non_actionable", reason)``.
   330
   331	    Validation status alone is not enough. A structurally failed plan with
   332	    concrete edit operations can still describe a current-graph direct edit,
   333	    while a passing or unevaluated plan with no candidate graph, nodes, rewires,
   334	    or edit ops is still only evidence.
   335	    """
   336
   337	    if value is None:
   338	        return "non_actionable", "missing_plan"
   339	    if not isinstance(value, Mapping) and not any(
   340	        hasattr(value, key)
   341	        for key in (
   342	            "candidate_graph",
   343	            "required_new_nodes",
   344	            "required_rewires",
   345	            "edit_ops",
   346	            "structural_validation",
   347	            "semantic_validation",
   348	        )
   349	    ):
   350	        return "non_actionable", "invalid_plan_shape"
   351
   352	    explicit = _adaptation_plan_field(value, "actionability")
   353	    if explicit == "non_actionable":
   354	        reason = _adaptation_plan_field(value, "non_actionable_reason") or "explicitly_non_actionable"
   355	        return "non_actionable", str(reason)
   356
   357	    candidate_graph = _adaptation_plan_field(value, "candidate_graph")
   358	    required_new_nodes = _adaptation_plan_field(value, "required_new_nodes") or ()
   359	    required_rewires = _adaptation_plan_field(value, "required_rewires") or ()
   360	    edit_ops = _adaptation_plan_field(value, "edit_ops") or ()
   361	    if candidate_graph or required_new_nodes or required_rewires or edit_ops:
   362	        return "actionable", ""
   363
   364	    structural = _adaptation_plan_field(value, "structural_validation")
   365	    semantic = _adaptation_plan_field(value, "semantic_validation")
   366	    if structural == "fail":
   367	        return "non_actionable", "structural_validation_failed_without_concrete_edits"
   368	    if semantic == "fail":
   369	        return "non_actionable", "semantic_validation_failed_without_concrete_edits"
   370	    return "non_actionable", "no_concrete_adaptation_edits"
   371
   372
   373	def is_actionable_adaptation_plan(value: Any) -> bool:
   374	    return adaptation_plan_actionability(value)[0] == "actionable"
   375
   376
   377	def adaptation_plan_actionability_payload(value: Any) -> dict[str, Any]:
   378	    actionability, reason = adaptation_plan_actionability(value)
   379	    payload: dict[str, Any] = {"actionability": actionability}
   380	    if actionability != "actionable":
   381	        payload["non_actionable_reason"] = reason
   382	        payload["allowed_followups"] = list(_ADAPTATION_PLAN_FOLLOWUPS)
   383	    return payload
   384
   385
   386	def _safe_exception_message(exc: BaseException) -> str:
   387	    message = " ".join(str(exc).split())
   388	    if not message:
   389	        return ""
   390	    message = re.sub(
   391	        r"https?://[^\s]+",
   392	        lambda match: _sanitize_url_for_warning(match.group(0)),
   393	        message,
   394	    )
   395	    if len(message) > _WARNING_DETAIL_MAX_MESSAGE:
   396	        return message[: _WARNING_DETAIL_MAX_MESSAGE - 3].rstrip() + "..."
   397	    return message
   398
   399
   400	def _sanitize_url_for_warning(raw_url: str) -> str:
   401	    try:
   402	        parsed = urlsplit(raw_url)
   403	    except ValueError:
   404	        return "<url>"
   405	    query_pairs = []
   406	    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
   407	        if key.lower() in _SENSITIVE_QUERY_KEYS:
   408	            query_pairs.append((key, "<redacted>"))
   409	        else:
   410	            query_pairs.append((key, value))
   411	    return urlunsplit((
   412	        parsed.scheme,
   413	        parsed.netloc,
   414	        parsed.path,
   415	        urlencode(query_pairs),
   416	        "",
   417	    ))
   418
   419
   420	def warning_detail_from_exception(exc: BaseException) -> dict[str, str]:
   421	    """Return a compact, JSON-safe exception detail for research warnings."""
   422	    return {
   423	        "type": type(exc).__name__,
   424	        "message": _safe_exception_message(exc),
   425	    }
   426
   427
   428	# ── classify decision ────────────────────────────────────────────────────────
   429
   430	# Canonical route vocabulary (SD1).  Empty string means "no route specified —
   431	# derive from legacy booleans".
   432	_ALLOWED_ROUTES = frozenset({
   433	    "",
   434	    "clarify",
   435	    "respond",
   436	    "inspect",
   437	    "research",
   438	    "requires_custom_nodes",
   439	    "revise",
   440	    "adapt",
   441	    "reorganise",
   442	})
   443
   444	# Normalized task vocabulary carried alongside route.
   445	_ALLOWED_TASKS = frozenset({
   446	    "",
   447	    "edit_graph",
   448	    "inspect_graph",
   449	    "find_assets",
   450	    "diagnose",
   451	    "preview_subgraph",
   452	    "research_precedent",
   453	    "layout_reorganise",
   454	    "respond",
   455	    "research_nodes",
   456	})
   457
   458	_ROUTE_DESCRIPTIONS: dict[str, str] = {
   459	    "clarify": "ask a clarifying question when load-bearing information is missing.",
   460	    "respond": "answer directly from existing context without research or editing.",
   461	    "inspect": "explain or analyze the current graph without outside research or editing.",
   462	    "research": "research workflows, nodes, or techniques, then answer without editing.",
   463	    "requires_custom_nodes": "return that the requested edit cannot be safely authored from current evidence without applying graph changes.",
   464	    "revise": "edit the current graph using local context only.",
   465	    "adapt": "research precedent or workflow patterns, then edit the graph.",
   466	    "reorganise": "reorganise the current canvas layout/readability without changing workflow semantics.",
   467	}
   468
   469	_PUBLIC_ROUTES = frozenset({
   470	    *_ROUTE_DESCRIPTIONS,
   471	    "requires_custom_nodes",
   472	})
   473	_APPLY_ELIGIBLE_ROUTES = frozenset({"revise", "adapt", "reorganise"})
   474	_EVIDENCE_KEYS = frozenset({
   475	    "classification",
   476	    "graph_inspection",
   477	    "research",
   478	    "implementation",
   479	    "warnings",
   480	})
   481	_NO_CANDIDATE_REASONS = frozenset({
   482	    "route_not_applyable",
   483	    "no_graph",
   484	    "implementation_skipped",
   485	    "implementation_failed",
   486	    "no_changes",
   487	    "unknown_route",
   488	})
   489
   490	_TASK_DESCRIPTIONS: dict[str, str] = {
   491	    "edit_graph": "modify the current graph.",
   492	    "inspect_graph": "inspect or explain a graph without editing.",
   493	    "find_assets": "find assets, models, or nodes.",
   494	    "diagnose": "diagnose workflow problems.",
   495	    "preview_subgraph": "preview a subgraph or node group.",
   496	    "research_precedent": "research precedent templates or techniques.",
   497	    "layout_reorganise": "reorganise canvas layout/readability without changing workflow semantics.",
   498	    "respond": "reply without graph actions.",
   499	    "research_nodes": "research nodes or workflow techniques.",
   500	}
   501
   502	if set(_ROUTE_DESCRIPTIONS) != (_ALLOWED_ROUTES - {""}):
   503	    raise ValueError("Route descriptions must cover every non-empty allowed route exactly once.")
   504
   505	if set(_TASK_DESCRIPTIONS) != (_ALLOWED_TASKS - {""}):
   506	    raise ValueError("Task descriptions must cover every non-empty allowed task exactly once.")
   507
   508
   509	def _normalize_explicit_route(
   510	    route: str,
   511	    *,
   512	    research: bool,
   513	    implement: bool,
   514	    intent: str,
   515	    task: str = "",
   516	) -> str:
   517	    """Normalize an explicit classifier route to the public route vocabulary.
   518
   519	    Legacy route names are accepted as input aliases only during the migration
   520	    window. Unknown explicit routes fail closed to ``clarify`` so serialized
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/executor/contracts.py b/vibecomfy/executor/contracts.py
index 36605241..c01eb301 100644
--- a/vibecomfy/executor/contracts.py
+++ b/vibecomfy/executor/contracts.py
@@ -11,50 +11,244 @@ from __future__ import annotations
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
+_MODEL_ATTEMPT_AUTHORIZATION_HEADER_RE = re.compile(
+    r"(?im)\bauthorization\s*:\s*[^\r\n]*"
+)
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
+    redacted = _MODEL_ATTEMPT_AUTHORIZATION_HEADER_RE.sub(
+        "Authorization: <redacted>", value
+    )
+    normalized = " ".join(redacted.strip().split())
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
@@ -2089,96 +2283,103 @@ class ImplementationResult:
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
-    # Mirrors the batch-repl model_response.json attempt artifact: parse-failure
-    # evidence (parse_reason, raw preview, usage, model, phase, endpoint) for the
-    # last classify/reply model attempt. None when the turn did not fail on a
-    # model response.
-    model_response: dict[str, Any] | None = None
+    # Canonical per-call evidence for every successful and failed model attempt
+    # observed across classify, implement/batch, and reply.
+    model_attempts: tuple[dict[str, Any], ...] = ()

     def __post_init__(self) -> None:
         object.__setattr__(
             self,
             "deepseek_usage",
             MappingProxyType({
                 str(k): _freeze_jsonish(v)
                 for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
             }),
         )
-        if self.model_response is not None:
-            object.__setattr__(
-                self,
-                "model_response",
-                _freeze_jsonish(self.model_response),
-            )
+        object.__setattr__(
+            self,
+            "model_attempts",
+            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
+        )
+
+    @property
+    def model_response(self) -> dict[str, Any] | None:
+        """Compatibility view derived solely from canonical ``model_attempts``."""
+        if not self.model_attempts:
+            return None
+        return {
+            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
+        }

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
-        if self.model_response is not None:
-            inner["model_response"] = _thaw_jsonish(self.model_response)
+        inner["model_attempts"] = [
+            _thaw_jsonish(item) for item in self.model_attempts
+        ]
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
@@ -2394,50 +2595,53 @@ class ExecutorResult:

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
@@ -2474,34 +2678,38 @@ class ExecutorResult:

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
/bin/zsh -lc "rg -n \"model_response|model_attempts\" vibecomfy/comfy_nodes/agent/{worker.py,runtime.py,provider.py} vibecomfy/executor/{agent_backend.py,contracts.py,core.py} vibecomfy/agent/artifacts.py tests/live_agentic_harness/{adapter.py,runner.py} | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
vibecomfy/executor/contracts.py:218:def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/contracts.py:2310:    model_attempts: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:2323:            "model_attempts",
vibecomfy/executor/contracts.py:2324:            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
vibecomfy/executor/contracts.py:2328:    def model_response(self) -> dict[str, Any] | None:
vibecomfy/executor/contracts.py:2329:        """Compatibility view derived solely from canonical ``model_attempts``."""
vibecomfy/executor/contracts.py:2330:        if not self.model_attempts:
vibecomfy/executor/contracts.py:2333:            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
vibecomfy/executor/contracts.py:2358:        inner["model_attempts"] = [
vibecomfy/executor/contracts.py:2359:            _thaw_jsonish(item) for item in self.model_attempts
vibecomfy/executor/contracts.py:2620:        payload["model_attempts"] = [
vibecomfy/executor/contracts.py:2621:            _thaw_jsonish(item) for item in self.report.model_attempts
vibecomfy/executor/contracts.py:2710:    "coerce_model_attempts",
tests/live_agentic_harness/runner.py:189:        "model_attempts": summary.get("model_attempts", []),
tests/live_agentic_harness/runner.py:194:    attempts = summary.get("model_attempts")
tests/live_agentic_harness/runner.py:263:    re-derived from the canonical ``model_attempts`` evidence on the same
tests/live_agentic_harness/runner.py:290:    canonical ``model_attempts`` evidence supports an infra class the summary is
tests/live_agentic_harness/runner.py:308:    The decision is the latest failed ``model_attempts`` entry's failure type
vibecomfy/comfy_nodes/agent/runtime.py:52:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/runtime.py:122:    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())
vibecomfy/comfy_nodes/agent/runtime.py:129:def record_model_attempts(value: Any) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:134:    for attempt in coerce_model_attempts(value):
vibecomfy/comfy_nodes/agent/runtime.py:140:def replace_last_model_attempts(value: Any) -> None:
vibecomfy/comfy_nodes/agent/runtime.py:143:    normalized = coerce_model_attempts(value)
vibecomfy/comfy_nodes/agent/runtime.py:154:    replace_last_model_attempts([value])
vibecomfy/comfy_nodes/agent/runtime.py:509:    attempts = coerce_model_attempts(result.get("model_attempts"))
vibecomfy/comfy_nodes/agent/runtime.py:608:            record_model_attempts([timeout_attempt])
vibecomfy/comfy_nodes/agent/runtime.py:609:            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/runtime.py:611:        attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/comfy_nodes/agent/runtime.py:616:            record_model_attempts([normalized])
vibecomfy/comfy_nodes/agent/runtime.py:618:            result["model_attempts"] = list(accumulated_attempts)
vibecomfy/comfy_nodes/agent/runtime.py:1220:    "record_model_attempts", "replace_last_model_attempt", "replace_last_model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:17:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/provider.py:115:        self.raw_response_preview = _preview_raw_model_response(raw_response)
vibecomfy/comfy_nodes/agent/provider.py:197:def _preview_raw_model_response(text: str | None, *, limit: int = 1200) -> str | None:
vibecomfy/comfy_nodes/agent/provider.py:207:    "model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:228:    attempts = coerce_model_attempts(response.get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:230:        merged["model_attempts"] = [dict(item) for item in attempts]
vibecomfy/comfy_nodes/agent/provider.py:1397:    attempts = list(coerce_model_attempts(response.get("model_attempts")))
vibecomfy/comfy_nodes/agent/provider.py:1413:        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1415:        replace_last_model_attempts(revised_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1418:    exc.model_attempts = list(revised_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/provider.py:1510:                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:1521:                    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1523:                    replace_last_model_attempts(numbered_current_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1528:                metadata["model_attempts"] = [*attempt_log, *numbered_current_attempts]
tests/live_agentic_harness/adapter.py:152:        "model_attempts": result.response.get("model_attempts", []),
vibecomfy/comfy_nodes/agent/worker.py:188:    unchanged. Mirrors the batch-repl ``model_response`` detail capture
vibecomfy/comfy_nodes/agent/worker.py:225:    out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:590:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:610:            # of losing it (mirrors the batch-repl model_response detail).
vibecomfy/comfy_nodes/agent/worker.py:620:            out["model_attempts"] = [
vibecomfy/agent/artifacts.py:33:    "model_attempts.json",
vibecomfy/agent/artifacts.py:35:    "model_response.json",
vibecomfy/agent/artifacts.py:429:    model_attempts = report.get("model_attempts")
vibecomfy/agent/artifacts.py:430:    if isinstance(model_attempts, (list, tuple)) and model_attempts:
vibecomfy/agent/artifacts.py:432:            output_dir / "model_attempts.json",
vibecomfy/agent/artifacts.py:433:            {"attempts": _redact(model_attempts)},
vibecomfy/agent/artifacts.py:435:        _append_manifest(manifest, "model_attempts.json")
vibecomfy/executor/agent_backend.py:30:    coerce_model_attempts,
vibecomfy/executor/agent_backend.py:78:        if result is not None and getattr(exc, "model_attempts", None) is None:
vibecomfy/executor/agent_backend.py:79:            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:104:    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
vibecomfy/executor/agent_backend.py:106:    record_model_attempts(result.get("model_attempts"))
vibecomfy/executor/agent_backend.py:112:    attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/executor/agent_backend.py:123:    result["model_attempts"] = attempts
vibecomfy/executor/core.py:60:    coerce_model_attempts,
vibecomfy/executor/core.py:106:def _model_attempts_from_exception(exc: BaseException) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/core.py:112:        attempts = coerce_model_attempts(getattr(current, "model_attempts", None))
vibecomfy/executor/core.py:117:            attempts = coerce_model_attempts(worker_result.get("model_attempts"))
vibecomfy/executor/core.py:129:    attempts = _model_attempts_from_exception(exc)
vibecomfy/executor/core.py:133:    context["model_attempts"] = list(attempts)
vibecomfy/executor/core.py:137:def _failure_model_attempts(failure: Any) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/core.py:142:    return coerce_model_attempts(context.get("model_attempts"))
vibecomfy/executor/core.py:998:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1008:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1723:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1733:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1755:        model_attempts: tuple[dict[str, Any], ...] = (),
vibecomfy/executor/core.py:1762:        self.model_attempts = coerce_model_attempts(model_attempts)
vibecomfy/executor/core.py:1883:        fallback_model_attempts: tuple[dict[str, Any], ...] = (),
vibecomfy/executor/core.py:1886:        model_attempts = snapshot_model_attempt_capture()
vibecomfy/executor/core.py:1887:        if not model_attempts:
vibecomfy/executor/core.py:1888:            model_attempts = coerce_model_attempts(fallback_model_attempts)
vibecomfy/executor/core.py:1901:            model_attempts=model_attempts,
vibecomfy/executor/core.py:2022:            fallback_model_attempts=exc.model_attempts,
vibecomfy/executor/core.py:2327:                fallback_model_attempts=exc.model_attempts,
vibecomfy/executor/core.py:2343:            fallback_model_attempts=exc.model_attempts,

exec
/bin/zsh -lc "nl -ba vibecomfy/agent/artifacts.py | sed -n '1,85p'; nl -ba vibecomfy/agent/artifacts.py | sed -n '360,455p'; git diff --unified=20 45415680..1bd1b04b -- vibecomfy/agent/artifacts.py | sed -n '1,280p'; rg -n \"model_response\\.json|model_response\" vibecomfy tests --glob '"'!*.pyc'"'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 113ms:
tests/test_executor_contracts.py:705:    def test_model_response_compatibility_view_is_derived_not_serialized(self) -> None:
tests/test_executor_contracts.py:713:        assert report.model_response == {"attempts": [attempt]}
tests/test_executor_contracts.py:716:        assert "model_response" not in payload
tests/test_edit_narrative.py:120:        "model_response_path": Path("/tmp/test_narrative_session/model_response.json"),
tests/test_edit_narrative.py:1020:    / "model_response.json"
tests/test_edit_narrative.py:1051:    The fixture ``tests/fixtures/editor_sessions/67785df94db647ca/model_response.json``
tests/test_comfy_nodes_agent_edit.py:761:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:955:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1008:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1081:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1152:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1230:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1325:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1404:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1479:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1597:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:1614:    assert state.model_response_path.is_file()
tests/test_comfy_nodes_agent_edit.py:1622:    response = json.loads(state.model_response_path.read_text(encoding="utf-8"))
tests/test_comfy_nodes_agent_edit.py:1788:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:2116:    assert Path(result["artifacts"]["model_response"]).name == "model_response.json"
tests/test_comfy_nodes_agent_edit.py:2135:        "model_response",
tests/test_comfy_nodes_agent_edit.py:2219:    model_response = json.loads(Path(result["artifacts"]["model_response"]).read_text(encoding="utf-8"))
tests/test_comfy_nodes_agent_edit.py:2222:    assert model_response["delta_ops_envelope"] == result["delta_ops_envelope"]
tests/test_comfy_nodes_agent_edit.py:2223:    assert model_response["delta"] == result["delta_ops"]
tests/test_comfy_nodes_agent_edit.py:2224:    assert set(model_response["delta_ops_envelope"]) == {"schema_version", "ops"}
tests/test_comfy_nodes_agent_edit.py:2231:        "model_response",
tests/test_comfy_nodes_agent_edit.py:2310:def test_agent_edit_batch_empty_model_response_is_malformed_not_provider_error(
tests/test_comfy_nodes_agent_edit.py:2354:def test_agent_edit_batch_empty_model_response_retries_once_then_commits(
tests/test_comfy_nodes_agent_edit.py:2420:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:2466:        model_response_path=tmp_path / "model_response.json",
tests/test_comfy_nodes_agent_edit.py:2531:    response_turns = json.loads(state.model_response_path.read_text(encoding="utf-8"))[
tests/test_comfy_nodes_agent_edit.py:2931:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:4740:    model_response = json.loads(
tests/test_comfy_nodes_agent_edit.py:4741:        (tmp_path / "rejected-terminal-clarify" / "turns" / "0001" / "model_response.json").read_text(
tests/test_comfy_nodes_agent_edit.py:4745:    clarification = model_response["turns"][1]["clarification"]
tests/test_comfy_nodes_agent_edit.py:4748:    assert "rejected_clarification" not in model_response["turns"][1]
tests/test_comfy_nodes_agent_edit.py:4808:    model_response = json.loads((turn_dir / "model_response.json").read_text(encoding="utf-8"))
tests/test_comfy_nodes_agent_edit.py:4810:    assert len(model_response["turns"]) == 3
tests/test_comfy_nodes_agent_edit.py:4811:    assert model_response["turns"][0]["batch_result"]["landed_op_count"] == 0
tests/test_comfy_nodes_agent_edit.py:4812:    assert "clarification" in model_response["turns"][2]
tests/test_comfy_nodes_agent_edit.py:4813:    assert "rejected_clarification" not in model_response["turns"][2]
tests/test_comfy_nodes_agent_edit.py:6226:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:6441:        assert (turn_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_edit.py:6607:    assert (turn_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_edit.py:7254:    model_response = json.loads(
tests/test_comfy_nodes_agent_edit.py:7255:        (turn_dir / "model_response.json").read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:7257:    assert model_response["turns"][0]["batch_result"]["execution_plan_status"] == first_status
tests/test_comfy_nodes_agent_edit.py:7365:        (turn_dir / "model_response.json").read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:8203:    assert (turn_dir / "model_response.json").is_file()
tests/test_comfy_nodes_agent_edit.py:8568:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:8750:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:8925:        Path(audit["artifacts"]["model_response"]["path"]).read_text(encoding="utf-8")
tests/test_comfy_nodes_agent_edit.py:12671:        "model_response_path": _Path("/tmp/test_session/model_response.json"),
tests/test_comfy_nodes_agent_edit.py:17098:        model_response_path=_Path("/tmp/test_flag_off/model_response.json"),
tests/test_comfy_nodes_agent_edit.py:17173:        model_response_path=_Path("/tmp/test_flag_off_unk/model_response.json"),
tests/browser/projection_boundary_helpers.mjs:128:  "model_response_path",
tests/test_comfy_nodes_agent_contracts.py:893:        model_response_path=tmp_path / "session" / "turns" / "0001" / "model_response.json",
tests/test_executor_flows.py:1751:        assert "model_response" not in executor_report
tests/test_agent_execution_plan_hydration.py:33:        model_response_path=turn_dir / "model_response.json",
vibecomfy/comfy_nodes/agent/worker.py:188:    unchanged. Mirrors the batch-repl ``model_response`` detail capture
vibecomfy/comfy_nodes/agent/worker.py:610:            # of losing it (mirrors the batch-repl model_response detail).
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:509:        "model_response": str(state.model_response_path),
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1042:        "model_response": str(state.model_response_path),
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1110:                "model_response": str(state.model_response_path),
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:187:        model_response_path=turn_dir / "model_response.json",
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1195:            state.model_response_path,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1228:                deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1411:        "model_response": str(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1561:                deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1621:            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1657:            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1680:        deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1734:                deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1781:                            deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1859:            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1879:                "model_response": str(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1899:                    deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2159:        deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2200:            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2216:                    deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2261:                    deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2407:                    deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2424:                deps.write_json_artifact(state.model_response_path, {"turns": response_log})
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2451:                        deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2506:                "model_response": str(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2527:                    deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2595:                    deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2639:            deps._artifact(state.model_response_path),
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:551:    `Full per-turn artifacts (the agent's actual step-by-step reasoning, the code it tried, and the engine diagnostics) are under: ${artifactPath}<NNNN>/ — see messages.jsonl, model_response.json, and response.json in each turn dir.`,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:588:    "  - model_response.json / model_request.json: the raw model reply and the",
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:845:// another machine gets the actual messages.jsonl / model_response.json /
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:912:    "messages.jsonl / model_response.json / response.json the report.txt points to,",
vibecomfy/comfy_nodes/agent/_frag_ingest.py:289:    model_response_ref = write_json_artifact(
vibecomfy/comfy_nodes/agent/_frag_ingest.py:290:        state.model_response_path,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:298:        artifacts=(_artifact(state.model_request_path), model_response_ref),
vibecomfy/comfy_nodes/agent/_frag_ingest.py:365:        model_response_ref = write_json_artifact(
vibecomfy/comfy_nodes/agent/_frag_ingest.py:366:            state.model_response_path,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:381:            artifacts=(_artifact(state.model_request_path), model_response_ref),
vibecomfy/comfy_nodes/agent/_frag_ingest.py:392:    model_response_ref = write_json_artifact(
vibecomfy/comfy_nodes/agent/_frag_ingest.py:393:        state.model_response_path,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:408:        artifacts=(_artifact(state.model_request_path), model_response_ref),
vibecomfy/agent/artifacts.py:35:    "model_response.json",
vibecomfy/comfy_nodes/agent/provider.py:115:        self.raw_response_preview = _preview_raw_model_response(raw_response)
vibecomfy/comfy_nodes/agent/provider.py:197:def _preview_raw_model_response(text: str | None, *, limit: int = 1200) -> str | None:
vibecomfy/comfy_nodes/agent/_frag_state.py:171:    model_response_path: Path
vibecomfy/comfy_nodes/agent/reorganise.py:163:    if state.model_response_path.exists():
vibecomfy/comfy_nodes/agent/reorganise.py:164:        artifact_paths["model_response"] = str(state.model_response_path)
vibecomfy/commands/_agent_edit_debug.py:233:    print("              model_request.json model_response.json audit/audit.json before.py after.py")
vibecomfy/executor/contracts.py:2328:    def model_response(self) -> dict[str, Any] | None:

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '1,260p'; nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '500,675p'; git diff --unified=15 45415680..1bd1b04b -- vibecomfy/comfy_nodes/agent/worker.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
     1	"""Isolated subprocess worker that runs one agent turn via Arnold dispatch.
     2
     3	The agent harness was renamed from ``megaplan`` to ``arnold``. Per-turn work
     4	now flows through the vendor-agnostic dispatch seam
     5	``arnold.agent.ArnoldDispatcher`` instead of constructing ``AIAgent`` directly.
     6	The default ``arnold.agent.dispatch`` pre-registers only ``"hermes" ->
     7	DeepSeekAdapter`` (a real adapter that lazily imports ``AIAgent`` and runs
     8	``run_conversation``); ``"codex"`` / ``"claude"`` are not registered yet and a
     9	dispatch to them raises ``LookupError`` (the parent's readiness gate keeps the
    10	panel from reaching them).
    11
    12	Why a subprocess? ``DeepSeekAdapter`` lazily imports the ``AIAgent`` backend,
    13	whose modules use bare top-level imports (``from utils import ...``,
    14	``from model_tools import ...``). When loaded inside the ComfyUI process those
    15	names collide with ComfyUI's own cached ``utils`` module
    16	(``sys.modules['utils']``), raising ImportError. Running in a fresh process
    17	where ComfyUI is never imported makes those bare imports resolve to the agent's
    18	own modules, and also isolates the agent's HTTP/asyncio state from ComfyUI's
    19	aiohttp event loop.
    20
    21	Protocol:
    22	    python worker.py <request.json> <result.json>
    23
    24	``request.json`` -> {"agent_id": str, "agent_kwargs": {...},
    25	                     "system_message": str|null, "user_message": str,
    26	                     "response_contract": "python"|"delta"|"batch_repl"|"json"|"text"}
    27	``result.json``  <- {"python": str, "message": str} or {"delta": list, "message": str} on success
    28	                    {"content": str} for batch_repl / json / text responses
    29	                    {"json": dict} additionally for json contract
    30	                    {"error": str, "error_type": str} on failure
    31
    32	``agent_kwargs`` are the AIAgent constructor kwargs the parent resolved for the
    33	route (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
    34	flags, ...). ``DeepSeekAdapter`` builds only a minimal kwargs set itself, so we
    35	inject a factory that merges the parent's kwargs verbatim — this reproduces the
    36	exact AIAgent construction the worker used before the dispatch seam was added.
    37
    38	stdout/stderr may contain agent chatter; the parent only reads ``result.json``.
    39	"""
    40
    41	from __future__ import annotations
    42
    43	import json
    44	import logging
    45	import os
    46	from pathlib import Path
    47	import re
    48	import sys
    49	import time
    50	from typing import Any
    51
    52
    53	def _bootstrap_repo_root() -> None:
    54	    """Make this file runnable by absolute path from a neutral cwd."""
    55	    repo_root = Path(__file__).resolve().parents[3]
    56	    repo_root_str = str(repo_root)
    57	    if repo_root_str not in sys.path:
    58	        sys.path.insert(0, repo_root_str)
    59
    60
    61	_bootstrap_repo_root()
    62
    63	from vibecomfy.agent.deepseek_usage import (
    64	    add_deepseek_usage,
    65	    coerce_deepseek_usage,
    66	    empty_deepseek_usage,
    67	)
    68	from vibecomfy.executor.contracts import (
    69	    ModelAttemptEvidence,
    70	    normalize_model_endpoint,
    71	    redact_model_preview,
    72	)
    73	from vibecomfy.executor.profiler import profiler_log, profiler_span, short_text, utc_now_iso
    74
    75	LOGGER = logging.getLogger(__name__)
    76
    77
    78	def _extract_json_object(text: str) -> dict:
    79	    stripped = (text or "").strip()
    80	    if stripped.startswith("```"):
    81	        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    82	        if match:
    83	            stripped = match.group(1).strip()
    84	    try:
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
   236
   237	def _anchor_agent_package_on_syspath() -> None:
   238	    """Put the agent package dir on sys.path so its bare top-level imports
   239	    (``utils``, ``model_tools``, ``toolsets``, ...) resolve to its own modules.
   240
   241	    Best-effort: if the legacy ``arnold.pipelines.megaplan.agent`` package is not
   242	    importable (e.g. a slimmed install), the adapter still drives its own lazy
   243	    import; we just skip the path anchor.
   244	    """
   245	    try:
   246	        import arnold.pipelines.megaplan.agent as _agent_pkg
   247	    except ImportError:
   248	        return
   249	    agent_dir = os.path.dirname(_agent_pkg.__file__)
   250	    if agent_dir and agent_dir not in sys.path:
   251	        sys.path.insert(0, agent_dir)
   252
   253
   254	def _build_request(
   255	    *,
   256	    agent_id: str,
   257	    user_message: str,
   258	    system_message: str | None,
   259	    model: str | None = None,
   260	    effort: str | None = None,
   500	    with open(request_path, encoding="utf-8") as fh:
   501	        request = json.load(fh)
   502
   503	    profiling_context = (
   504	        request.get("profiling_context")
   505	        if isinstance(request.get("profiling_context"), dict)
   506	        else {}
   507	    )
   508	    profiler_log(
   509	        LOGGER,
   510	        "worker.request",
   511	        profiling_context=profiling_context,
   512	        agent_id=request.get("agent_id") or "hermes",
   513	        response_contract=request.get("response_contract") or "python",
   514	        user_message_preview=short_text(request.get("user_message")),
   515	    )
   516
   517	    worker_started_at = utc_now_iso()
   518	    worker_started_monotonic = time.monotonic()
   519	    raw_text: str | None = None
   520	    worker_metadata: dict[str, Any] | None = None
   521	    try:
   522	        agent_id = request.get("agent_id") or "hermes"
   523	        response_contract = request.get("response_contract") or "python"
   524	        with profiler_span(
   525	            LOGGER,
   526	            "worker.run_turn",
   527	            profiling_context=profiling_context,
   528	            agent_id=agent_id,
   529	            response_contract=response_contract,
   530	        ) as span:
   531	            text, worker_metadata = _dispatch_turn(
   532	                agent_id=agent_id,
   533	                agent_kwargs=request["agent_kwargs"],
   534	                user_message=request["user_message"],
   535	                system_message=request.get("system_message"),
   536	                model=request.get("model"),
   537	                effort=request.get("effort"),
   538	            )
   539	            raw_text = text
   540	            span.update(raw_text_length=len(text or ""))
   541	            if response_contract == "batch_repl":
   542	                if not isinstance(text, str) or not text.strip():
   543	                    raise ValueError("Agent returned an empty batch_repl response.")
   544	                out = {"content": text}
   545	            elif response_contract == "text":
   546	                if not isinstance(text, str) or not text.strip():
   547	                    raise ValueError("Agent returned an empty text response.")
   548	                out = {"content": text}
   549	            elif response_contract == "json":
   550	                if not isinstance(text, str) or not text.strip():
   551	                    raise ValueError("Agent returned an empty json response.")
   552	                payload = _extract_json_object(text)
   553	                out = {"content": text, "json": payload}
   554	            elif response_contract in ("python", "delta"):
   555	                payload = _extract_json_object(text or "")
   556	                message = payload.get("message")
   557	                if not isinstance(message, str):
   558	                    raise ValueError("Agent JSON must include a string `message` field.")
   559	                if response_contract == "delta":
   560	                    delta = payload.get("delta")
   561	                    if not isinstance(delta, list):
   562	                        raise ValueError("Agent JSON must include a list `delta` field.")
   563	                    out = {"delta": delta, "message": message}
   564	                else:  # python
   565	                    python = payload.get("python")
   566	                    if not isinstance(python, str):
   567	                        raise ValueError("Agent JSON must include a string `python` field.")
   568	                    out = {"python": python, "message": message}
   569	            else:
   570	                raise ValueError(f"Unsupported response_contract {response_contract!r}.")
   571	            if isinstance(worker_metadata, dict):
   572	                out.update(worker_metadata)
   573	            # Self-describing envelope: carry the resolved model/phase/endpoint
   574	            # so upstream classify/reply evidence plumbing can persist them on a
   575	            # later parse failure without re-resolving provider internals.
   576	            agent_kwargs = (
   577	                request.get("agent_kwargs")
   578	                if isinstance(request.get("agent_kwargs"), dict)
   579	                else {}
   580	            )
   581	            model = request.get("model") or agent_kwargs.get("model")
   582	            if model:
   583	                out["model"] = model
   584	            phase = profiling_context.get("backend_phase") or "agent_turn"
   585	            if phase:
   586	                out["phase"] = phase
   587	            endpoint = agent_kwargs.get("base_url")
   588	            if endpoint:
   589	                out["endpoint"] = normalize_model_endpoint(endpoint)
   590	            out["model_attempts"] = [
   591	                _model_attempt(
   592	                    request,
   593	                    profiling_context,
   594	                    worker_metadata,
   595	                    outcome="success",
   596	                )
   597	            ]
   598	    except Exception as exc:  # noqa: BLE001 - report all failures to parent
   599	        out = {"error": str(exc), "error_type": type(exc).__name__}
   600	        # A LookupError means no adapter is registered for the requested agent id
   601	        # (e.g. codex/claude not wired into the default dispatcher yet); an
   602	        # ImportError means the backend's heavy deps are missing. Both are setup
   603	        # faults — flag them so the parent surfaces a non-retryable
   604	        # runtime-unavailable signal rather than a transient provider error.
   605	        if isinstance(exc, (LookupError, ImportError)):
   606	            out["runtime_unavailable"] = True
   607	        if raw_text is not None:
   608	            # The raw response was received but discarded on a parse/content
   609	            # failure — persist bounded evidence on the failure envelope instead
   610	            # of losing it (mirrors the batch-repl model_response detail).
   611	            _persist_parse_evidence(
   612	                out,
   613	                exc,
   614	                raw_text,
   615	                worker_metadata,
   616	                request,
   617	                profiling_context,
   618	            )
   619	        else:
   620	            out["model_attempts"] = [
   621	                _model_attempt(
   622	                    request,
   623	                    profiling_context,
   624	                    worker_metadata,
   625	                    outcome="failure",
   626	                    failure_type=_model_attempt_failure_type(exc, raw_text),
   627	                )
   628	            ]
   629
   630	    out["_profiling"] = {
   631	        **profiling_context,
   632	        "agent_id": request.get("agent_id") or "hermes",
   633	        "response_contract": request.get("response_contract") or "python",
   634	        "started_at": worker_started_at,
   635	        "ended_at": utc_now_iso(),
   636	        "elapsed_ms": max(0, int((time.monotonic() - worker_started_monotonic) * 1000)),
   637	    }
   638
   639	    with open(result_path, "w", encoding="utf-8") as fh:
   640	        json.dump(out, fh)
   641	    return 0
   642
   643
   644	if __name__ == "__main__":
   645	    raise SystemExit(main())
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/comfy_nodes/agent/worker.py b/vibecomfy/comfy_nodes/agent/worker.py
index ef9ff064..ab51a994 100644
--- a/vibecomfy/comfy_nodes/agent/worker.py
+++ b/vibecomfy/comfy_nodes/agent/worker.py
@@ -53,135 +53,197 @@ from typing import Any
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
+    if not isinstance(usage, dict) or int(usage.get("n_calls") or 0) <= 0:
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
@@ -512,52 +574,70 @@ def main() -> int:
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



exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1,190p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '450,650p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '650,880p'; git diff --unified=20 45415680..1bd1b04b -- vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1,620p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 138ms:
     1	"""Megaplan/Arnold runtime adapter for the VibeComfy agent-edit loop.
     2
     3	VibeComfy's ``agent_provider._load_arnold_runtime`` discovers a runtime module
     4	that exposes ``run_agent_turn(...)`` and (optionally) ``get_agent_status(...)``.
     5	The shipped arnold harness (``pip install`` of
     6	https://github.com/peteromallet/Arnold, importable as the ``arnold`` package;
     7	formerly ``megaplan``) does not expose those exact entry points -- its agent
     8	backend is the ``arnold.pipelines.megaplan.agent.run_agent.AIAgent`` class (the
     9	legacy ``megaplan.agent.run_agent.AIAgent`` location is still accepted as a
    10	fallback). This module is the small adapter the runbook calls for: it drives
    11	``AIAgent`` for a single, tool-free completion and returns VibeComfy's
    12	agent-edit contracts.
    13
    14	Wire it up by pointing the discovery env var at this module::
    15
    16	    export VIBECOMFY_ARNOLD_RUNTIME_MODULE="vibecomfy.comfy_nodes.agent.runtime"
    17
    18	Routes
    19	------
    20	* ``openrouter``  -> OpenRouter (``https://openrouter.ai/api/v1``), key resolved
    21	  from ``OPENROUTER_API_KEY`` or ``~/.hermes/.env`` (where the browser
    22	  credential route writes it). This is the canonical browser-key route.
    23	* ``arnold`` (also ``auto`` / ``anthropic`` / ``openai-codex`` after VibeComfy
    24	  normalises them) -> AIAgent's own provider resolution (Claude via OpenRouter
    25	  or local OAuth). Honest about availability: status reports ``ok`` only when a
    26	  usable credential resolves.
    27
    28	Everything heavy (provider routing, retries, OAuth resolution) is handled by the
    29	real ``AIAgent`` backend; this file is intentionally thin.
    30	"""
    31
    32	from __future__ import annotations
    33
    34	import contextvars
    35	import json
    36	import os
    37	import subprocess
    38	import sys
    39	import tempfile
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
   140	def replace_last_model_attempts(value: Any) -> None:
   141	    """Replace the matching captured suffix with normalized attempt evidence."""
   142	    state = _MODEL_ATTEMPT_CAPTURE.get()
   143	    normalized = coerce_model_attempts(value)
   144	    if state is None or not normalized:
   145	        return
   146	    if len(state) >= len(normalized):
   147	        state[-len(normalized):] = normalized
   148	    else:
   149	        state.extend(normalized)
   150
   151
   152	def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
   153	    """Replace the most recent captured transport-success after domain parse failure."""
   154	    replace_last_model_attempts([value])
   155
   156
   157	def _record_captured_deepseek_usage(result: Any) -> None:
   158	    state = _DEEPSEEK_USAGE_CAPTURE.get()
   159	    if not isinstance(state, dict) or not isinstance(result, dict):
   160	        return
   161	    usage = coerce_deepseek_usage(result.get("deepseek_usage"))
   162	    if usage["n_calls"] <= 0:
   163	        return
   164	    state["usage"] = add_deepseek_usage(state.get("usage"), usage)
   165	    if not result.get("deepseek_cache_breakout_complete", False):
   166	        state["cache_breakout_complete"] = False
   167
   168
   169	def _read_env_file_entries(path: Path = _HERMES_ENV_PATH) -> list[tuple[str, str]]:
   170	    """Read dotenv-style key/value pairs in file order."""
   171	    entries: list[tuple[str, str]] = []
   172	    try:
   173	        text = path.read_text(encoding="utf-8")
   174	    except (FileNotFoundError, OSError):
   175	        return entries
   176	    for line in text.splitlines():
   177	        line = line.strip()
   178	        if not line or line.startswith("#") or "=" not in line:
   179	            continue
   180	        key, _, value = line.partition("=")
   181	        key = key.strip()
   182	        value = value.strip().strip('"').strip("'")
   183	        if key:
   184	            entries.append((key, value))
   185	    return entries
   186
   187
   188	def _read_env_file(path: Path = _HERMES_ENV_PATH) -> dict[str, str]:
   189	    """Read dotenv-style key/value pairs, with later duplicate entries winning."""
   190	    values: dict[str, str] = {}
   450	    )
   451
   452
   453	def _split_messages(messages: Sequence[Mapping[str, Any]] | None) -> tuple[str | None, str | None]:
   454	    """Return (system_message, user_message) from VibeComfy's built messages."""
   455	    system_msg: str | None = None
   456	    user_msg: str | None = None
   457	    for entry in messages or []:
   458	        role = entry.get("role")
   459	        content = entry.get("content")
   460	        if not isinstance(content, str):
   461	            continue
   462	        if role == "system" and system_msg is None:
   463	            system_msg = content
   464	        elif role == "user":
   465	            user_msg = content
   466	    return system_msg, user_msg
   467
   468
   469	def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | None = None) -> dict[str, Any]:
   470	    """AIAgent constructor kwargs for a single, tool-free completion.
   471
   472	    Keyed off the resolved *dispatch agent id* (not the panel route). ``hermes``
   473	    is always configured for OpenRouter, including the legacy ``deepseek`` route
   474	    alias. For ``codex`` / ``claude`` the worker dispatches through the default
   475	    dispatcher and ignores ``agent_kwargs``, so we pass only the tool-free
   476	    single-shot flags.
   477	    """
   478	    common: dict[str, Any] = dict(
   479	        max_iterations=1,
   480	        enabled_toolsets=[],          # no tools: one-shot completion
   481	        save_trajectories=False,      # no trajectory files on disk
   482	        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
   483	        skip_memory=True,             # don't load/write the memory store
   484	        quiet_mode=True,
   485	    )
   486	    if agent_id == "hermes":
   487	        base_url = _base_url_for_route(route)
   488	        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
   489	        if _is_native_deepseek_endpoint(base_url):
   490	            # Native api.deepseek.com rejects OpenRouter-style ``deepseek/`` slugs
   491	            # with HTTP 400; normalize to the bare model name it accepts.
   492	            resolved_model = _normalize_native_deepseek_model(resolved_model)
   493	        else:
   494	            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
   495	        return dict(
   496	            model=resolved_model,
   497	            api_key=_hermes_credential_for(route, model),
   498	            base_url=base_url,
   499	            provider="openrouter",
   500	            max_tokens=_OPENROUTER_MAX_TOKENS,
   501	            **common,
   502	        )
   503	    # codex / claude -> default dispatcher resolves everything; kwargs unused.
   504	    return dict(**common)
   505
   506
   507	def _is_typed_empty_worker_result(result: Mapping[str, Any]) -> bool:
   508	    """True only for typed empty responses with observed zero completion tokens."""
   509	    attempts = coerce_model_attempts(result.get("model_attempts"))
   510	    if not attempts:
   511	        return False
   512	    latest = attempts[-1]
   513	    usage = latest.get("token_usage")
   514	    return (
   515	        latest.get("outcome") == "failure"
   516	        and latest.get("failure_type") == "empty_response"
   517	        and isinstance(usage, Mapping)
   518	        and usage.get("completion_tokens") == 0
   519	    )
   520
   521
   522	def _runtime_provider_transport(
   523	    *, agent_id: str, agent_kwargs: Mapping[str, Any]
   524	) -> tuple[str, str, str]:
   525	    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
   526	    if agent_id != "hermes":
   527	        return "unknown", "unknown", endpoint
   528	    if "openrouter.ai" in endpoint:
   529	        return "openrouter", "openrouter", endpoint
   530	    if "deepseek.com" in endpoint:
   531	        return "deepseek", "native", endpoint
   532	    if endpoint != "unknown":
   533	        return "unknown", "openai_compatible", endpoint
   534	    return "unknown", "unknown", endpoint
   535
   536
   537	def _timeout_model_attempt(
   538	    *,
   539	    agent_kwargs: Mapping[str, Any],
   540	    agent_id: str,
   541	    requested_model: str | None,
   542	    resolved_model: str | None,
   543	    profiling_context: Mapping[str, Any] | None,
   544	    attempt: int,
   545	) -> dict[str, Any]:
   546	    provider, transport, endpoint = _runtime_provider_transport(
   547	        agent_id=agent_id, agent_kwargs=agent_kwargs
   548	    )
   549	    return ModelAttemptEvidence(
   550	        phase=(profiling_context or {}).get("backend_phase") or "agent_turn",
   551	        attempt=attempt,
   552	        outcome="failure",
   553	        failure_type="timeout",
   554	        requested_model=requested_model,
   555	        resolved_model=resolved_model or agent_kwargs.get("model"),
   556	        adapter=agent_id,
   557	        provider=provider,
   558	        transport=transport,
   559	        endpoint=endpoint,
   560	    ).to_dict()
   561
   562
   563	def _run_worker(
   564	    agent_kwargs: dict[str, Any],
   565	    system_msg: str | None,
   566	    user_msg: str,
   567	    *,
   568	    response_contract: str = "python",
   569	    agent_id: str = "hermes",
   570	    model: str | None = None,
   571	    requested_model: str | None = None,
   572	    effort: str | None = None,
   573	    profiling_context: Mapping[str, Any] | None = None,
   574	) -> dict[str, Any]:
   575	    """Run one AIAgent turn in an isolated subprocess; return its result dict.
   576
   577	    A fresh subprocess/transport is permitted only after a canonical
   578	    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
   579	    provider/capacity errors, and malformed non-empty content surface immediately.
   580	    """
   581	    accumulated_attempts: list[dict[str, Any]] = []
   582	    for attempt in range(_WORKER_TRANSIENT_MAX_ATTEMPTS):
   583	        attempt_profile = dict(profiling_context or {})
   584	        if attempt:
   585	            attempt_profile["transient_retry_count"] = attempt
   586	        try:
   587	            result = _run_worker_once(
   588	                agent_kwargs,
   589	                system_msg,
   590	                user_msg,
   591	                response_contract=response_contract,
   592	                agent_id=agent_id,
   593	                model=model,
   594	                requested_model=requested_model,
   595	                effort=effort,
   596	                profiling_context=attempt_profile,
   597	            )
   598	        except TimeoutError as exc:
   599	            timeout_attempt = _timeout_model_attempt(
   600	                agent_kwargs=agent_kwargs,
   601	                agent_id=agent_id,
   602	                requested_model=requested_model,
   603	                resolved_model=model,
   604	                profiling_context=profiling_context,
   605	                attempt=len(accumulated_attempts) + 1,
   606	            )
   607	            accumulated_attempts.append(timeout_attempt)
   608	            record_model_attempts([timeout_attempt])
   609	            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
   610	            raise
   611	        attempts = list(coerce_model_attempts(result.get("model_attempts")))
   612	        for item in attempts:
   613	            item["attempt"] = len(accumulated_attempts) + 1
   614	            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
   615	            accumulated_attempts.append(normalized)
   616	            record_model_attempts([normalized])
   617	        if accumulated_attempts:
   618	            result["model_attempts"] = list(accumulated_attempts)
   619	        if (
   620	            "error" in result
   621	            and _is_typed_empty_worker_result(result)
   622	            and attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS
   623	        ):
   624	            LOGGER.warning(
   625	                "agent worker returned typed empty response (attempt %d/%d); retrying",
   626	                attempt + 1,
   627	                _WORKER_TRANSIENT_MAX_ATTEMPTS,
   628	            )
   629	            time.sleep(_WORKER_TRANSIENT_BACKOFF_SECONDS * attempt)
   630	            continue
   631	        return result
   632	    raise RuntimeError("agent worker retry loop exited without a result")
   633
   634
   635	def _run_worker_once(
   636	    agent_kwargs: dict[str, Any],
   637	    system_msg: str | None,
   638	    user_msg: str,
   639	    *,
   640	    response_contract: str = "python",
   641	    agent_id: str = "hermes",
   642	    model: str | None = None,
   643	    requested_model: str | None = None,
   644	    effort: str | None = None,
   645	    profiling_context: Mapping[str, Any] | None = None,
   646	) -> dict[str, Any]:
   647	    """Run one AIAgent turn in an isolated subprocess; return its result dict.
   648
   649	    Single attempt — no retry. See :func:`_run_worker` for the retry wrapper.
   650
   650
   651	    Isolation avoids the top-level module-name collision between megaplan's
   652	    agent (bare ``import utils`` / ``model_tools``) and ComfyUI's own ``utils``
   653	    package, and keeps the agent's asyncio/HTTP state out of ComfyUI's loop.
   654	    """
   655	    with tempfile.TemporaryDirectory(prefix="vibecomfy-agent-") as tmp:
   656	        req_path = os.path.join(tmp, "request.json")
   657	        res_path = os.path.join(tmp, "result.json")
   658	        with open(req_path, "w", encoding="utf-8") as fh:
   659	            json.dump(
   660	                {
   661	                    "agent_id": agent_id,
   662	                    "model": model,
   663	                    "requested_model": requested_model,
   664	                    "effort": effort,
   665	                    "agent_kwargs": agent_kwargs,
   666	                    "system_message": system_msg,
   667	                    "user_message": user_msg,
   668	                    "response_contract": response_contract,
   669	                    "profiling_context": dict(profiling_context or {}),
   670	                },
   671	                fh,
   672	            )
   673	        env = dict(os.environ)
   674	        # Ensure the child sees the same credential the parent resolved for the
   675	        # Hermes adapter.  For native DeepSeek endpoints this must be the
   676	        # DeepSeek key, not a stale browser/OpenRouter key from ~/.hermes/.env.
   677	        hermes_key = agent_kwargs.get("api_key") or _resolve_openrouter_key()
   678	        if isinstance(hermes_key, str) and hermes_key:
   679	            env["OPENROUTER_API_KEY"] = hermes_key
   680	            env["OPENAI_API_KEY"] = hermes_key
   681	            env["HERMES_API_KEY"] = hermes_key
   682	        # Don't leak ComfyUI's cwd/path into the child (it is what causes the
   683	        # `utils` collision); run from a neutral directory.
   684	        try:
   685	            with profiler_span(
   686	                LOGGER,
   687	                "runtime.worker_subprocess",
   688	                agent_id=agent_id,
   689	                response_contract=response_contract,
   690	                worker_path=_WORKER_PATH,
   691	                profiling_context=dict(profiling_context or {}),
   692	            ) as span:
   693	                proc = subprocess.run(
   694	                    [sys.executable, _WORKER_PATH, req_path, res_path],
   695	                    cwd=tmp,
   696	                    env=env,
   697	                    capture_output=True,
   698	                    text=True,
   699	                    timeout=_TURN_TIMEOUT_SECONDS,
   700	                )
   701	                span.update(
   702	                    returncode=proc.returncode,
   703	                    stdout_length=len(proc.stdout or ""),
   704	                    stderr_length=len(proc.stderr or ""),
   705	                )
   706	        except subprocess.TimeoutExpired as exc:
   707	            raise TimeoutError(
   708	                f"Agent worker timed out after {_TURN_TIMEOUT_SECONDS:g} seconds."
   709	            ) from exc
   710	        try:
   711	            with open(res_path, encoding="utf-8") as fh:
   712	                result = json.load(fh)
   713	                worker_profile = result.get("_profiling") if isinstance(result, dict) else None
   714	                profiler_log(
   715	                    LOGGER,
   716	                    "runtime.worker_result",
   717	                    agent_id=agent_id,
   718	                    response_contract=response_contract,
   719	                    profiling_context=dict(profiling_context or {}),
   720	                    worker_profile=worker_profile if isinstance(worker_profile, dict) else None,
   721	                    result_keys=sorted(result.keys()) if isinstance(result, dict) else None,
   722	                )
   723	                if isinstance(result, dict) and "error" in result:
   724	                    if proc.stdout:
   725	                        result.setdefault("worker_stdout_tail", proc.stdout[-4000:])
   726	                    if proc.stderr:
   727	                        result.setdefault("worker_stderr_tail", proc.stderr[-4000:])
   728	                _record_captured_deepseek_usage(result)
   729	                return result
   730	        except (FileNotFoundError, json.JSONDecodeError) as exc:
   731	            tail = (proc.stderr or proc.stdout or "")[-800:]
   732	            raise RuntimeError(
   733	                f"Agent worker produced no result (exit {proc.returncode}). {exc}. "
   734	                f"Worker output tail:\n{tail}"
   735	            ) from exc
   736
   737
   738	def run_agent_turn(
   739	    *,
   740	    task: str,
   741	    python_source: str,
   742	    route: str,
   743	    model: str | None = None,
   744	    effort: str | None = None,
   745	    messages: Sequence[Mapping[str, Any]] | None = None,
   746	) -> dict[str, Any]:
   747	    """Run one agent-edit turn through the megaplan AIAgent backend.
   748
   749	    Returns ``{"python": <str>, "message": <str>}`` as VibeComfy expects.
   750	    """
   751	    agent_id = _agent_id_for_route(route)
   752	    system_msg, user_msg = _split_messages(messages)
   753	    if user_msg is None:
   754	        # Fall back to reconstructing the user message from the raw inputs.
   755	        user_msg = (
   756	            f"User request:\n{task}\n\n"
   757	            "Current scratchpad Python:\n```python\n" + (python_source or "") + "\n```"
   758	        )
   759
   760	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   761	        raise PermissionError(
   762	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   763	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   764	            "VibeComfy panel or export OPENROUTER_API_KEY."
   765	        )
   766
   767	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   768	    result = _run_worker(
   769	        agent_kwargs,
   770	        system_msg,
   771	        user_msg,
   772	        response_contract="python",
   773	        agent_id=agent_id,
   774	        model=_runtime_model_for_route(route, model),
   775	        requested_model=model,
   776	        effort=effort,
   777	        profiling_context={"backend_phase": "implement"},
   778	    )
   779	    if "error" in result:
   780	        _raise_worker_error(result)
   781	    return dict(result)
   782
   783
   784	def run_agent_turn_delta(
   785	    *,
   786	    task: str,
   787	    projection: str,
   788	    op_schema: Mapping[str, Any],
   789	    route: str,
   790	    model: str | None = None,
   791	    effort: str | None = None,
   792	    messages: Sequence[Mapping[str, Any]] | None = None,
   793	) -> dict[str, Any]:
   794	    """Run one v2 agent-edit turn and return ``{"delta": [...], "message": str}``."""
   795	    agent_id = _agent_id_for_route(route)
   796	    system_msg, user_msg = _split_messages(messages)
   797	    if user_msg is None:
   798	        user_msg = (
   799	            f"User request:\n{task}\n\n"
   800	            "Address-preserving UI projection:\n"
   801	            f"{projection}"
   802	        )
   803
   804	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   805	        raise PermissionError(
   806	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   807	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   808	            "VibeComfy panel or export OPENROUTER_API_KEY."
   809	        )
   810
   811	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   812	    result = _run_worker(
   813	        agent_kwargs,
   814	        system_msg,
   815	        user_msg,
   816	        response_contract="delta",
   817	        agent_id=agent_id,
   818	        model=_runtime_model_for_route(route, model),
   819	        requested_model=model,
   820	        effort=effort,
   821	        profiling_context={"backend_phase": "implement"},
   822	    )
   823	    if "error" in result:
   824	        _raise_worker_error(result)
   825	    return dict(result)
   826
   827
   828	def run_agent_turn_batch(
   829	    *,
   830	    task: str,
   831	    route: str,
   832	    model: str | None = None,
   833	    effort: str | None = None,
   834	    messages: Sequence[Mapping[str, Any]] | None = None,
   835	) -> dict[str, Any]:
   836	    """Run one batch-REPL agent-edit turn and return raw model content."""
   837	    agent_id = _agent_id_for_route(route)
   838	    system_msg, user_msg = _split_messages(messages)
   839	    if user_msg is None:
   840	        user_msg = f"User request:\n{task}"
   841
   842	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   843	        raise PermissionError(
   844	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   845	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   846	            "VibeComfy panel or export OPENROUTER_API_KEY."
   847	        )
   848
   849	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   850	    result = _run_worker(
   851	        agent_kwargs,
   852	        system_msg,
   853	        user_msg,
   854	        response_contract="batch_repl",
   855	        agent_id=agent_id,
   856	        model=_runtime_model_for_route(route, model),
   857	        requested_model=model,
   858	        effort=effort,
   859	        profiling_context={"backend_phase": "batch"},
   860	    )
   861	    if "error" in result:
   862	        _raise_worker_error(result)
   863	    return dict(result)
   864
   865
   866	def _requested_route(route: str | None) -> str:
   867	    """Canonical panel route name (claude->anthropic, codex->openai-codex).
   868
   869	    The ``hermes`` dispatch agent id is exposed as a product route in headless
   870	    executor specs; for readiness/status purposes it is the same as the
   871	    OpenRouter browser-key route.
   872	    """
   873	    requested = (route or "").strip().lower()
   874	    if requested == "claude":
   875	        return "anthropic"
   876	    if requested == "codex":
   877	        return "openai-codex"
   878	    if requested in {"deepseek", "hermes"}:
   879	        return "openrouter"
   880	    return requested
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/comfy_nodes/agent/runtime.py b/vibecomfy/comfy_nodes/agent/runtime.py
index 9ebf3b26..8c1e257d 100644
--- a/vibecomfy/comfy_nodes/agent/runtime.py
+++ b/vibecomfy/comfy_nodes/agent/runtime.py
@@ -30,124 +30,147 @@ real ``AIAgent`` backend; this file is intentionally thin.
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
+def replace_last_model_attempts(value: Any) -> None:
+    """Replace the matching captured suffix with normalized attempt evidence."""
+    state = _MODEL_ATTEMPT_CAPTURE.get()
+    normalized = coerce_model_attempts(value)
+    if state is None or not normalized:
+        return
+    if len(state) >= len(normalized):
+        state[-len(normalized):] = normalized
+    else:
+        state.extend(normalized)
+
+
+def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
+    """Replace the most recent captured transport-success after domain parse failure."""
+    replace_last_model_attempts([value])
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
@@ -268,100 +291,109 @@ def _raise_worker_error(result: Mapping[str, Any]) -> None:
     if (
         error_type in {"AuthError", "AuthenticationError", "PermissionError"}
         or "authenticationerror" in lowered
         or "error code: 401" in lowered
         or "missing authentication header" in lowered
         or "invalid api key" in lowered
         or "unauthorized" in lowered
     ):
         raise _with_worker_result(PermissionError(message))
     if _is_runtime_unavailable(result):
         raise _with_worker_result(ImportError(message))
     raise _with_worker_result(RuntimeError(message))


 def _normalize_route(route: str | None) -> str:
     normalized = (route or "arnold").strip().lower()
     if normalized in {"auto", "anthropic", "openai-codex"}:
         return "arnold"
     if normalized == "hermes":
         return "openrouter"
-    return normalized or "arnold"
+    if normalized in {"arnold", "openrouter", "deepseek"}:
+        return "openrouter" if normalized == "deepseek" else normalized
+    return "unknown"


 # Panel route -> arnold dispatch agent id. The worker registers/dispatches under
 # this id. Only ``hermes`` is wired in the default dispatcher today; ``codex`` /
 # ``claude`` will raise LookupError until adapters are registered (Step B's
 # readiness gate keeps the panel from reaching them).
 _ROUTE_TO_AGENT_ID = {
     "deepseek": "hermes",
     "openrouter": "hermes",
     "openai-codex": "codex",
     "anthropic": "claude",
 }


 def _agent_id_for_route(route: str | None) -> str:
     """Map a panel route name to the arnold dispatch agent id.

     Unlike :func:`_normalize_route`, this keeps anthropic/openai-codex distinct
     so the worker can dispatch to the correct (eventual) adapter. ``auto`` and
     bare ``arnold`` fall back to ``hermes`` (the only registered backend).
     """
     requested = (route or "").strip().lower()
     if requested == "claude":
         requested = "anthropic"
     elif requested == "codex":
         requested = "openai-codex"
-    return _ROUTE_TO_AGENT_ID.get(requested, "hermes")
+    if requested in {"", "auto", "arnold", "hermes"}:
+        return "hermes"
+    return _ROUTE_TO_AGENT_ID.get(requested, "unknown")


 def _default_model_for_route(route: str, model: str | None) -> str:
+    normalized_route = _normalize_route(route)
+    if normalized_route == "unknown":
+        return "unknown"
     if _is_real_model_override(model):
         return _strip_provider_prefix(model, "openrouter")
-    if route == "openrouter":
+    if normalized_route == "openrouter":
         return _strip_provider_prefix(_OPENROUTER_MODEL, "openrouter")
     return _ARNOLD_MODEL


 def _is_real_model_override(model: str | None) -> bool:
     """True when *model* is an actual provider model, not the panel contract id."""
     normalized = (model or "").strip()
     return bool(normalized and normalized != "agent-edit")


 def _runtime_model_for_route(route: str | None, model: str | None) -> str | None:
     """Return the model slug to hand to the provider adapter.

     The browser/status contract historically used ``agent-edit`` as a product
     label.  That is not a valid OpenRouter/Anthropic/Codex model id, so keep it
     out of the provider seam and let the route resolve its real default.
     """
+    normalized_route = _normalize_route(route)
+    if normalized_route == "unknown":
+        return None
     # Explicit per-process force-override: when set, ignore the profile/judge
     # model slug and route everything through this model (e.g. swapping the
     # hermes backend to a non-DeepSeek OpenAI-compatible endpoint). No-op unset.
     forced_model = os.getenv("VIBECOMFY_FORCE_MODEL")
     if forced_model:
         return forced_model
     if _is_real_model_override(model):
         return model
-    normalized_route = _normalize_route(route)
     if normalized_route == "openrouter":
         return _OPENROUTER_MODEL
     if normalized_route in {"arnold", "anthropic", "openai-codex"}:
         return _ARNOLD_MODEL
     return None


 def _strip_provider_prefix(model: str, provider: str) -> str:
     prefix = f"{provider}:"
     return model.split(":", 1)[1] if model.lower().startswith(prefix) else model


 def _normalize_native_deepseek_model(model: str) -> str:
     """Strip provider prefixes DeepSeek's native API rejects.

     Native ``api.deepseek.com`` only accepts bare model names
     (``deepseek-v4-pro`` / ``deepseek-v4-flash``).  OpenRouter-style slugs like
     ``openrouter:deepseek/deepseek-v4-flash`` or ``deepseek/deepseek-v4-flash``
     (which the executor profile ships) are rejected with HTTP 400
     "The supported API model names are deepseek-v4-pro or deepseek-v4-flash, but
@@ -455,154 +487,197 @@ def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | No
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
@@ -680,123 +755,129 @@ def run_agent_turn(
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

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '735,955p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '955,1145p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1145,1235p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   735	            ) from exc
   736
   737
   738	def run_agent_turn(
   739	    *,
   740	    task: str,
   741	    python_source: str,
   742	    route: str,
   743	    model: str | None = None,
   744	    effort: str | None = None,
   745	    messages: Sequence[Mapping[str, Any]] | None = None,
   746	) -> dict[str, Any]:
   747	    """Run one agent-edit turn through the megaplan AIAgent backend.
   748
   749	    Returns ``{"python": <str>, "message": <str>}`` as VibeComfy expects.
   750	    """
   751	    agent_id = _agent_id_for_route(route)
   752	    system_msg, user_msg = _split_messages(messages)
   753	    if user_msg is None:
   754	        # Fall back to reconstructing the user message from the raw inputs.
   755	        user_msg = (
   756	            f"User request:\n{task}\n\n"
   757	            "Current scratchpad Python:\n```python\n" + (python_source or "") + "\n```"
   758	        )
   759
   760	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   761	        raise PermissionError(
   762	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   763	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   764	            "VibeComfy panel or export OPENROUTER_API_KEY."
   765	        )
   766
   767	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   768	    result = _run_worker(
   769	        agent_kwargs,
   770	        system_msg,
   771	        user_msg,
   772	        response_contract="python",
   773	        agent_id=agent_id,
   774	        model=_runtime_model_for_route(route, model),
   775	        requested_model=model,
   776	        effort=effort,
   777	        profiling_context={"backend_phase": "implement"},
   778	    )
   779	    if "error" in result:
   780	        _raise_worker_error(result)
   781	    return dict(result)
   782
   783
   784	def run_agent_turn_delta(
   785	    *,
   786	    task: str,
   787	    projection: str,
   788	    op_schema: Mapping[str, Any],
   789	    route: str,
   790	    model: str | None = None,
   791	    effort: str | None = None,
   792	    messages: Sequence[Mapping[str, Any]] | None = None,
   793	) -> dict[str, Any]:
   794	    """Run one v2 agent-edit turn and return ``{"delta": [...], "message": str}``."""
   795	    agent_id = _agent_id_for_route(route)
   796	    system_msg, user_msg = _split_messages(messages)
   797	    if user_msg is None:
   798	        user_msg = (
   799	            f"User request:\n{task}\n\n"
   800	            "Address-preserving UI projection:\n"
   801	            f"{projection}"
   802	        )
   803
   804	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   805	        raise PermissionError(
   806	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   807	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   808	            "VibeComfy panel or export OPENROUTER_API_KEY."
   809	        )
   810
   811	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   812	    result = _run_worker(
   813	        agent_kwargs,
   814	        system_msg,
   815	        user_msg,
   816	        response_contract="delta",
   817	        agent_id=agent_id,
   818	        model=_runtime_model_for_route(route, model),
   819	        requested_model=model,
   820	        effort=effort,
   821	        profiling_context={"backend_phase": "implement"},
   822	    )
   823	    if "error" in result:
   824	        _raise_worker_error(result)
   825	    return dict(result)
   826
   827
   828	def run_agent_turn_batch(
   829	    *,
   830	    task: str,
   831	    route: str,
   832	    model: str | None = None,
   833	    effort: str | None = None,
   834	    messages: Sequence[Mapping[str, Any]] | None = None,
   835	) -> dict[str, Any]:
   836	    """Run one batch-REPL agent-edit turn and return raw model content."""
   837	    agent_id = _agent_id_for_route(route)
   838	    system_msg, user_msg = _split_messages(messages)
   839	    if user_msg is None:
   840	        user_msg = f"User request:\n{task}"
   841
   842	    if agent_id == "hermes" and not _hermes_credential_for(route, model):
   843	        raise PermissionError(
   844	            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
   845	            "(checked environment and ~/.hermes/.env). Submit a key via the "
   846	            "VibeComfy panel or export OPENROUTER_API_KEY."
   847	        )
   848
   849	    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
   850	    result = _run_worker(
   851	        agent_kwargs,
   852	        system_msg,
   853	        user_msg,
   854	        response_contract="batch_repl",
   855	        agent_id=agent_id,
   856	        model=_runtime_model_for_route(route, model),
   857	        requested_model=model,
   858	        effort=effort,
   859	        profiling_context={"backend_phase": "batch"},
   860	    )
   861	    if "error" in result:
   862	        _raise_worker_error(result)
   863	    return dict(result)
   864
   865
   866	def _requested_route(route: str | None) -> str:
   867	    """Canonical panel route name (claude->anthropic, codex->openai-codex).
   868
   869	    The ``hermes`` dispatch agent id is exposed as a product route in headless
   870	    executor specs; for readiness/status purposes it is the same as the
   871	    OpenRouter browser-key route.
   872	    """
   873	    requested = (route or "").strip().lower()
   874	    if requested == "claude":
   875	        return "anthropic"
   876	    if requested == "codex":
   877	        return "openai-codex"
   878	    if requested in {"deepseek", "hermes"}:
   879	        return "openrouter"
   880	    return requested
   881
   882
   883	def _codex_cli_present() -> bool:
   884	    """True if a `codex` CLI binary resolves on PATH."""
   885	    import shutil
   886
   887	    return bool(shutil.which("codex"))
   888
   889
   890	def _claude_cli_present() -> bool:
   891	    """True if a `claude` CLI binary resolves on PATH."""
   892	    import shutil
   893
   894	    return bool(shutil.which("claude"))
   895
   896
   897	def _bun_present() -> bool:
   898	    """True if a `bun` binary resolves on PATH (shannon launcher dependency)."""
   899	    import shutil
   900
   901	    return bool(shutil.which("bun"))
   902
   903
   904	def _registered_agent_ids() -> set[str]:
   905	    """Best-effort introspection of the arnold default dispatcher's registry.
   906
   907	    The dispatcher exposes no public registry query, so we read its private
   908	    ``_adapters`` mapping defensively. If arnold (or the attribute) is not
   909	    importable, return an empty set rather than crashing — readiness must never
   910	    raise.
   911	    """
   912	    try:
   913	        import arnold.agent as _agent_mod
   914	    except ImportError:
   915	        return set()
   916	    dispatcher = getattr(_agent_mod, "_default", None)
   917	    adapters = getattr(dispatcher, "_adapters", None)
   918	    if isinstance(adapters, dict):
   919	        return set(adapters.keys())
   920	    return set()
   921
   922
   923	def _adapter_registered(agent_id: str) -> bool:
   924	    """True when *agent_id* has an adapter registered in the default dispatcher."""
   925	    return agent_id in _registered_agent_ids()
   926
   927
   928	def _auth_json_has_token(path: Path) -> bool:
   929	    """True if an auth.json at *path* carries a non-empty credential.
   930
   931	    Recognizes the standalone Codex CLI shape (ChatGPT OAuth: ``tokens`` dict
   932	    with ``access_token``/``id_token``, or a top-level ``OPENAI_API_KEY``) as
   933	    well as the hermes shape (``token``/``access_token``/``api_key``).
   934	    """
   935	    try:
   936	        raw = path.expanduser().read_text(encoding="utf-8")
   937	    except (FileNotFoundError, OSError):
   938	        return False
   939	    try:
   940	        data = json.loads(raw)
   941	    except json.JSONDecodeError:
   942	        return False
   943	    if not isinstance(data, dict):
   944	        return False
   945	    for key in ("token", "access_token", "api_key", "OPENAI_API_KEY", "id_token"):
   946	        value = data.get(key)
   947	        if isinstance(value, str) and value.strip():
   948	            return True
   949	    tokens = data.get("tokens")
   950	    if isinstance(tokens, dict):
   951	        for key in ("access_token", "id_token", "account_id"):
   952	            value = tokens.get(key)
   953	            if isinstance(value, str) and value.strip():
   954	                return True
   955	    return False
   955	    return False
   956
   957
   958	def _codex_auth_present() -> bool:
   959	    """True if the codex CLI is authenticated.
   960
   961	    The standalone ``codex`` CLI (ChatGPT login) stores creds in
   962	    ``~/.codex/auth.json``; the hermes-wrapped variant used ``~/.hermes/auth.json``.
   963	    Either satisfies the codex route.
   964	    """
   965	    return _auth_json_has_token(Path("~/.codex/auth.json")) or _auth_json_has_token(
   966	        Path("~/.hermes/auth.json")
   967	    )
   968
   969
   970	def readiness(*, route: str, model: str | None = None) -> dict[str, Any]:
   971	    """Report truthful, per-route backend readiness.
   972
   973	    Only the browser-key ``openrouter`` route reaches a real, registered adapter
   974	    today (``hermes`` configured for OpenRouter).
   975	    ``openai-codex`` and ``anthropic`` have no
   976	    adapter registered in the default dispatcher yet, so they report
   977	    ``ready: False`` with a clear reason — the panel must tell the truth rather
   978	    than green-light them off an unrelated OpenRouter/Anthropic key.
   979	    """
   980	    backend = "arnold.pipelines.megaplan.agent.run_agent.AIAgent"
   981	    requested = _requested_route(route)
   982
   983	    if requested == "openrouter" or (
   984	        requested in {"", "auto"} and _resolve_openrouter_key()
   985	    ):
   986	        key = _resolve_openrouter_key()
   987	        return {
   988	            "ready": bool(key),
   989	            "backend": backend,
   990	            "route": "openrouter",
   991	            "model": _default_model_for_route("openrouter", model),
   992	            "base_url": _CANONICAL_OPENROUTER_BASE_URL,
   993	            "openrouter_key_present": bool(key),
   994	            "reason": (
   995	                "OpenRouter key resolved; ready to run agent-edit turns."
   996	                if key
   997	                else "No OPENROUTER_API_KEY in environment or ~/.hermes/.env."
   998	            ),
   999	        }
  1000
  1001	    if requested == "openai-codex":
  1002	        # The codex route is ready only when (a) a ``codex`` adapter is registered
  1003	        # in the default dispatcher AND (b) codex is actually usable here: the
  1004	        # ``codex`` CLI on PATH plus a ~/.hermes/auth.json token. Never green-light
  1005	        # off an unrelated key.
  1006	        registered = _adapter_registered("codex")
  1007	        have_token = _codex_auth_present()
  1008	        have_cli = _codex_cli_present()
  1009	        if not registered:
  1010	            # Not wired yet: report honest probe details (this shape is what the
  1011	            # panel shows while the parallel codex adapter is still in flight).
  1012	            return {
  1013	                "ready": False,
  1014	                "backend": backend,
  1015	                "route": "openai-codex",
  1016	                "model": _default_model_for_route("openai-codex", model),
  1017	                "codex_adapter_registered": False,
  1018	                "codex_auth_present": have_token,
  1019	                "codex_cli_present": have_cli,
  1020	                "reason": (
  1021	                    "codex adapter not wired yet (no Codex adapter registered in the "
  1022	                    "arnold dispatcher; "
  1023	                    f"codex auth {'present' if have_token else 'absent'}, "
  1024	                    f"codex CLI {'on PATH' if have_cli else 'not on PATH'})."
  1025	                ),
  1026	            }
  1027	        usable = have_cli and have_token
  1028	        return {
  1029	            "ready": usable,
  1030	            "backend": backend,
  1031	            "route": "openai-codex",
  1032	            "model": _default_model_for_route("openai-codex", model),
  1033	            "codex_adapter_registered": True,
  1034	            "codex_auth_present": have_token,
  1035	            "codex_cli_present": have_cli,
  1036	            "reason": (
  1037	                "codex adapter registered and codex is usable (CLI on PATH + "
  1038	                "codex login present). Note: a live turn still depends on Codex "
  1039	                "account quota."
  1040	                if usable
  1041	                else (
  1042	                    "codex adapter registered but codex is not usable: "
  1043	                    f"codex CLI {'on PATH' if have_cli else 'not on PATH'}, "
  1044	                    f"codex auth {'present' if have_token else 'absent'}."
  1045	                )
  1046	            ),
  1047	        }
  1048
  1049	    if requested == "anthropic":
  1050	        # The claude route is ready only when (a) a ``claude``/``shannon`` adapter
  1051	        # is registered AND (b) Claude is usable here: ``claude`` and ``bun`` on
  1052	        # PATH (the shannon launcher's runtime deps). Never green-light off an
  1053	        # Anthropic/OpenRouter key alone.
  1054	        registered = _adapter_registered("claude") or _adapter_registered("shannon")
  1055	        if not registered:
  1056	            return {
  1057	                "ready": False,
  1058	                "backend": backend,
  1059	                "route": "anthropic",
  1060	                "model": _default_model_for_route("anthropic", model),
  1061	                "shannon_adapter_registered": False,
  1062	                "reason": (
  1063	                    "claude/shannon adapter not wired yet (no Claude/Shannon adapter "
  1064	                    "registered in the arnold dispatcher)."
  1065	                ),
  1066	            }
  1067	        have_claude = _claude_cli_present()
  1068	        have_bun = _bun_present()
  1069	        usable = have_claude and have_bun
  1070	        return {
  1071	            "ready": usable,
  1072	            "backend": backend,
  1073	            "route": "anthropic",
  1074	            "model": _default_model_for_route("anthropic", model),
  1075	            "shannon_adapter_registered": True,
  1076	            "claude_cli_present": have_claude,
  1077	            "bun_present": have_bun,
  1078	            "reason": (
  1079	                "claude/shannon adapter registered and Claude is usable (claude + "
  1080	                "bun on PATH)."
  1081	                if usable
  1082	                else (
  1083	                    "claude/shannon adapter registered but Claude is not usable: "
  1084	                    f"claude CLI {'on PATH' if have_claude else 'not on PATH'}, "
  1085	                    f"bun {'on PATH' if have_bun else 'not on PATH'}."
  1086	                )
  1087	            ),
  1088	        }
  1089
  1090	    # Bare/legacy ``arnold`` (or anything else) with no OpenRouter key: fall through
  1091	    # to the best available registered+ready backend (prefer OpenRouter). For
  1092	    # ``auto`` with no OpenRouter key, that is whatever else is wired; today only
  1093	    # hermes is guaranteed, so report not-ready honestly.
  1094	    if requested in {"", "auto", "arnold"}:
  1095	        if _adapter_registered("hermes") and _resolve_openrouter_key():
  1096	            key = _resolve_openrouter_key()
  1097	            return {
  1098	                "ready": True,
  1099	                "backend": backend,
  1100	                "route": "openrouter",
  1101	                "model": _default_model_for_route("openrouter", model),
  1102	                "base_url": _OPENROUTER_BASE_URL,
  1103	                "openrouter_key_present": bool(key),
  1104	                "reason": "OpenRouter key resolved; ready to run agent-edit turns.",
  1105	            }
  1106	    return {
  1107	        "ready": False,
  1108	        "backend": backend,
  1109	        "route": (
  1110	            "unknown"
  1111	            if requested and _normalize_route(requested) == "unknown"
  1112	            else requested or "arnold"
  1113	        ),
  1114	        "model": _default_model_for_route(_normalize_route(route), model),
  1115	        "reason": (
  1116	            "No agent adapter is wired for this route yet; only the openrouter "
  1117	            "route reaches a registered backend."
  1118	        ),
  1119	    }
  1120
  1121
  1122	def get_agent_status(*, route: str, model: str | None = None) -> dict[str, Any]:
  1123	    """Compatibility wrapper around readiness().
  1124
  1125	    Prefer readiness(); this legacy shape remains for callers that still expect
  1126	    status-like fields.
  1127	    """
  1128	    payload = readiness(route=route, model=model)
  1129	    ready = bool(payload.get("ready"))
  1130	    return {
  1131	        **payload,
  1132	        "ok": ready,
  1133	        "detail": str(payload.get("reason") or ""),
  1134	        "readiness": "ready" if ready else "unavailable",
  1135	    }
  1136
  1137
  1138
  1139
  1140	def run_model_turn(
  1141	    *,
  1142	    task: str,
  1143	    messages: Sequence[Mapping[str, Any]] | None = None,
  1144	    route: str,
  1145	    model: str | None = None,
  1145	    model: str | None = None,
  1146	    effort: str | None = None,
  1147	    response_contract: str = "json",
  1148	    profiling_context: Mapping[str, Any] | None = None,
  1149	) -> dict[str, Any]:
  1150	    """Run a generic model turn through the Arnold dispatch seam.
  1151
  1152	    Unlike ``run_agent_turn`` (which hardcodes ``response_contract="python"``
  1153	    and the python/message contract) or ``run_agent_turn_batch`` (which
  1154	    hardcodes ``response_contract="batch_repl"``), this entry point accepts
  1155	    an arbitrary *response_contract* so the executor can request ``"json"``
  1156	    or ``"text"`` responses.
  1157
  1158	    Returns the worker result dict directly.  For ``"json"`` contracts the
  1159	    dict contains ``{"content": <raw_text>, "json": <parsed_dict>}``; for
  1160	    ``"text"`` it contains ``{"content": <raw_text>}``.
  1161	    """
  1162	    agent_id = _agent_id_for_route(route)
  1163	    system_msg, user_msg = _split_messages(messages)
  1164	    if user_msg is None:
  1165	        user_msg = f"User request:\n{task}"
  1166	    effective_profile = {
  1167	        "model_turn_id": (
  1168	            str(profiling_context.get("model_turn_id"))
  1169	            if isinstance(profiling_context, Mapping) and profiling_context.get("model_turn_id")
  1170	            else new_profile_id("model")
  1171	        ),
  1172	        "route": route,
  1173	        "model": model,
  1174	        "response_contract": response_contract,
  1175	        **(dict(profiling_context or {})),
  1176	    }
  1177
  1178	    with profiler_span(
  1179	        LOGGER,
  1180	        "runtime.run_model_turn",
  1181	        model_turn_id=effective_profile.get("model_turn_id"),
  1182	        agent_id=agent_id,
  1183	        route=route,
  1184	        model=model,
  1185	        response_contract=response_contract,
  1186	        task_preview=short_text(task),
  1187	    ) as span:
  1188	        if agent_id == "hermes" and not _hermes_credential_for(route, model):
  1189	            raise PermissionError(
  1190	                "OpenRouter route selected but no OPENROUTER_API_KEY is available "
  1191	                "(checked environment and ~/.hermes/.env). Submit a key via the "
  1192	                "VibeComfy panel or export OPENROUTER_API_KEY."
  1193	            )
  1194
  1195	        agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
  1196	        result = _run_worker(
  1197	            agent_kwargs,
  1198	            system_msg,
  1199	            user_msg,
  1200	            response_contract=response_contract,
  1201	            agent_id=agent_id,
  1202	            model=_runtime_model_for_route(route, model),
  1203	            requested_model=model,
  1204	            effort=effort,
  1205	            profiling_context=effective_profile,
  1206	        )
  1207	        if "error" in result:
  1208	            _raise_worker_error(result)
  1209
  1210	        span.update(
  1211	            result_keys=sorted(result.keys()),
  1212	            worker_profile=result.get("_profiling") if isinstance(result.get("_profiling"), dict) else None,
  1213	        )
  1214	        return result
  1215
  1216	__all__ = [
  1217	    "begin_deepseek_usage_capture", "snapshot_deepseek_usage_capture",
  1218	    "end_deepseek_usage_capture", "begin_model_attempt_capture",
  1219	    "snapshot_model_attempt_capture", "end_model_attempt_capture",
  1220	    "record_model_attempts", "replace_last_model_attempt", "replace_last_model_attempts",
  1221	    "run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch",
  1222	    "run_model_turn", "readiness", "get_agent_status",
  1223	]

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '1,260p'; nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '1335,1555p'; git diff --unified=20 45415680..1bd1b04b -- vibecomfy/comfy_nodes/agent/provider.py | sed -n '1,650p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 46ms:
diff --git a/vibecomfy/comfy_nodes/agent/provider.py b/vibecomfy/comfy_nodes/agent/provider.py
index cad71ca2..8d2c58f2 100644
--- a/vibecomfy/comfy_nodes/agent/provider.py
+++ b/vibecomfy/comfy_nodes/agent/provider.py
@@ -1,34 +1,39 @@
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
@@ -173,68 +178,79 @@ def _extract_json_object(text: str) -> dict[str, Any]:
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
@@ -867,41 +883,41 @@ def _resolve_agent_route(route: str | None) -> AgentRouteDescriptor:
             browser_api_key_allowed=False,
             guidance=_ANTHROPIC_GUIDANCE,
             tos_acknowledgement_required=True,
         )
     if requested == "openai-codex":
         return AgentRouteDescriptor(
             requested_route=requested,
             normalized_route="arnold",
             browser_api_key_allowed=False,
             guidance=_CODEX_GUIDANCE,
         )
     if requested == "arnold":
         return AgentRouteDescriptor(
             requested_route=requested,
             normalized_route="arnold",
             browser_api_key_allowed=False,
             guidance=_ARNOLD_GUIDANCE,
         )
     return AgentRouteDescriptor(
         requested_route=requested,
-        normalized_route=requested,
+        normalized_route="unknown",
         browser_api_key_allowed=False,
     )


 def _credential_presence() -> dict[str, bool]:
     return {
         "arnold_api_key": bool(os.getenv("ARNOLD_API_KEY")),
         "hermes_api_key": bool(os.getenv("HERMES_API_KEY")),
         "openrouter_api_key": _openrouter_key_present(),
         "deepseek_api_key": _env_key_present("DEEPSEEK_API_KEY"),
     }


 def _non_secret_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
     redacted = redact_closed_set(dict(value)).value
     return redacted if isinstance(redacted, dict) else {}


 def _resolve_route_and_model(
     route: str | None,
@@ -1009,62 +1025,63 @@ def _load_arnold_runtime() -> Any:
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
@@ -1213,103 +1230,106 @@ def run_agent_turn_delta(
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
@@ -1339,40 +1359,95 @@ def _call_batch_runtime(
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
+    *,
+    attempt_offset: int,
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
+    attempts[-1] = latest
+    revised_attempts: list[dict[str, Any]] = []
+    for local_index, attempt in enumerate(attempts, start=1):
+        numbered = dict(attempt)
+        numbered["attempt"] = attempt_offset + local_index
+        revised_attempts.append(ModelAttemptEvidence.from_mapping(numbered).to_dict())
+    try:
+        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
+
+        replace_last_model_attempts(revised_attempts)
+    except Exception:  # noqa: BLE001 - evidence capture is additive
+        pass
+    exc.model_attempts = list(revised_attempts)  # type: ignore[attr-defined]
+    return tuple(revised_attempts)
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
@@ -1383,64 +1458,92 @@ def run_agent_turn_batch(
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
+                failed_attempts = _revise_failed_runtime_attempt(
+                    response,
+                    exc,
+                    attempt_offset=len(attempt_log),
+                )
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
+            numbered_current_attempts: list[dict[str, Any]] = []
+            for local_index, current_attempt in enumerate(current_attempts, start=1):
+                numbered = dict(current_attempt)
+                numbered["attempt"] = len(attempt_log) + local_index
+                numbered_current_attempts.append(
+                    ModelAttemptEvidence.from_mapping(numbered).to_dict()
+                )
+            if numbered_current_attempts:
+                try:
+                    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
+
+                    replace_last_model_attempts(numbered_current_attempts)
+                except Exception:  # noqa: BLE001 - evidence capture is additive
+                    pass
+            if attempt_log or numbered_current_attempts != current_attempts:
+                metadata = dict(result.audit_metadata or {})
+                metadata["model_attempts"] = [*attempt_log, *numbered_current_attempts]
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

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/core.py | sed -n '70,165p'; nl -ba vibecomfy/executor/core.py | sed -n '930,1030p'; nl -ba vibecomfy/executor/core.py | sed -n '1670,1775p'; nl -ba vibecomfy/executor/core.py | sed -n '1840,1920p'; nl -ba vibecomfy/executor/core.py | sed -n '1960,2045p'; nl -ba vibecomfy/executor/core.py | sed -n '2265,2360p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 53ms:
    70	from .research import _default_hivemind_client, research as run_research_phase
    71	from .revision_evidence import collect_graph_facts
    72
    73	LOGGER = logging.getLogger(__name__)
    74
    75	_INSTALL_RESEARCH_TERMS = (
    76	    "install",
    77	    "installation",
    78	    "provider pack",
    79	    "provider-pack",
    80	    "which pack",
    81	    "node pack",
    82	    "custom node pack",
    83	    "registry",
    84	    "local addability",
    85	    "locally addable",
    86	)
    87
    88	_INSTALL_REQUEST_TERMS = (
    89	    "install",
    90	    "installation",
    91	    "which pack",
    92	    "what pack",
    93	    "provider pack",
    94	    "provides",
    95	    "registry",
    96	    "comfyui-manager",
    97	)
    98
    99
   100	def _spec_fields(spec: AgentSpecShape | None) -> dict[str, Any]:
   101	    if spec is None:
   102	        return {}
   103	    return {"route": spec.agent, "model": spec.model, "effort": spec.effort}
   104
   105
   106	def _model_attempts_from_exception(exc: BaseException) -> tuple[dict[str, Any], ...]:
   107	    """Return the first canonical attempt sequence found in an exception chain."""
   108	    seen: set[int] = set()
   109	    current: BaseException | None = exc
   110	    while current is not None and id(current) not in seen:
   111	        seen.add(id(current))
   112	        attempts = coerce_model_attempts(getattr(current, "model_attempts", None))
   113	        if attempts:
   114	            return attempts
   115	        worker_result = getattr(current, "worker_result", None)
   116	        if isinstance(worker_result, Mapping):
   117	            attempts = coerce_model_attempts(worker_result.get("model_attempts"))
   118	            if attempts:
   119	                return attempts
   120	        current = current.__cause__
   121	    return ()
   122
   123
   124	def _enrich_failure_envelope(
   125	    failure: Any,
   126	    exc: BaseException,
   127	) -> Any:
   128	    """Attach only canonical model-attempt evidence to a failure envelope."""
   129	    attempts = _model_attempts_from_exception(exc)
   130	    if not attempts:
   131	        return failure
   132	    context = dict(failure.agent_failure_context or {})
   133	    context["model_attempts"] = list(attempts)
   134	    return replace(failure, agent_failure_context=context)
   135
   136
   137	def _failure_model_attempts(failure: Any) -> tuple[dict[str, Any], ...]:
   138	    """Read canonical attempts previously attached to a failure envelope."""
   139	    context = getattr(failure, "agent_failure_context", None)
   140	    if not isinstance(context, Mapping):
   141	        return ()
   142	    return coerce_model_attempts(context.get("model_attempts"))
   143
   144
   145	def _allows_install_or_provider_research(query: str) -> bool:
   146	    query_l = str(query or "").casefold()
   147	    return any(term in query_l for term in _INSTALL_REQUEST_TERMS)
   148
   149
   150	def _sanitize_research_hint_text(text: str, *, query: str = "") -> str | None:
   151	    """Keep classifier hints pointed at precedent unless install info was asked for."""
   152
   153	    stripped = str(text or "").strip()
   154	    if not stripped:
   155	        return None
   156	    text_l = stripped.casefold()
   157	    if (
   158	        _allows_install_or_provider_research(query)
   159	        or not any(term in text_l for term in _INSTALL_RESEARCH_TERMS)
   160	    ):
   161	        return stripped
   162
   163	    replacements = (
   164	        (r"\bnode[- ]pack installation and usage\b", "workflow precedent and usage"),
   165	        (r"\bnode[- ]pack installation\b", "workflow precedent"),
   930
   931
   932	# ── classify phase ───────────────────────────────────────────────────────────
   933
   934
   935	def _run_classify(
   936	    request: ExecutorRequest,
   937	    spec: AgentSpecShape,
   938	    *,
   939	    session_context: dict[str, Any] | None = None,
   940	    graph_reference_map: dict[str, str] | None = None,
   941	) -> ClassifyDecision:
   942	    """Run the classify model turn.
   943
   944	    Always calls the model (SD1).  Converts provider exceptions through
   945	    ``classify_failure`` so raw exceptions never leak.
   946	    """
   947	    try:
   948	        # Build enriched messages when session context carries actual data
   949	        # for reference resolution (M3).  Otherwise, let run_classify_turn
   950	        # build them from the default parameters.
   951	        graph_summary = _graph_summary(request.graph)
   952	        layout_hint = build_classify_layout_hint(request.graph)
   953	        compact_layout_hint = (
   954	            layout_hint.to_prompt_fields() if layout_hint is not None else None
   955	        )
   956	        classify_kwargs: dict[str, Any] = {
   957	            "route": spec.agent,
   958	            "model": spec.model,
   959	            "effort": spec.effort,
   960	            "has_graph": request.graph is not None,
   961	            "graph_summary": graph_summary,
   962	        }
   963	        # Pre-build messages whenever we have context beyond the bare query.
   964	        # First-turn graph edits need the node reference map just as much as
   965	        # follow-ups do; otherwise the classifier sees "a graph is attached"
   966	        # without the custom class names required for revise/adapt routing.
   967	        if graph_reference_map or compact_layout_hint or (
   968	            isinstance(session_context, dict)
   969	            and (
   970	                session_context.get("recent_messages")
   971	                or session_context.get("prior_clarification")
   972	                or session_context.get("latest_candidate")
   973	                or session_context.get("prior_route")
   974	            )
   975	        ):
   976	            classify_kwargs["messages"] = build_classify_messages(
   977	                request.query,
   978	                has_graph=request.graph is not None,
   979	                graph_summary=graph_summary,
   980	                session_context=session_context,
   981	                graph_reference_map=graph_reference_map,
   982	                layout_hint=compact_layout_hint,
   983	            )
   984
   985	        return run_classify_turn(request.query, **classify_kwargs)
   986	    except _ExecutorPhaseError:
   987	        raise
   988	    except (ProviderError, AuthError, MalformedModelJSON,
   989	            MissingRequiredField, TimeoutError) as exc:
   990	        # Map provider-level errors through the failure envelope machinery.
   991	        failure = classify_failure("agent_response", exc)
   992	        failure = _enrich_failure_envelope(failure, exc)
   993	        raise _ExecutorPhaseError(
   994	            stage="classify",
   995	            failure_kind=failure.kind.value,
   996	            message=failure.user_facing_message,
   997	            failure_envelope=failure,
   998	            model_attempts=_failure_model_attempts(failure),
   999	        ) from exc
  1000	    except Exception as exc:
  1001	        failure = classify_failure("classify", exc)
  1002	        failure = _enrich_failure_envelope(failure, exc)
  1003	        raise _ExecutorPhaseError(
  1004	            stage="classify",
  1005	            failure_kind=failure.kind.value,
  1006	            message=failure.user_facing_message,
  1007	            failure_envelope=failure,
  1008	            model_attempts=_failure_model_attempts(failure),
  1009	        ) from exc
  1010
  1011
  1012	# ── research phase ───────────────────────────────────────────────────────────
  1013
  1014
  1015	def _run_research(
  1016	    request: ExecutorRequest,
  1017	    _spec: AgentSpecShape,
  1018	    *,
  1019	    plan: ClassifyDecision | None = None,
  1020	) -> ResearchResult:
  1021	    """Run the research phase (local corpus + optional Hivemind).
  1022
  1023	    Research failures are non-fatal; they are captured as warnings in the
  1024	    :class:`ResearchResult` and never propagate as exceptions.
  1025
  1026	    When *plan* is provided and the route is ``adapt``, the query is scoped
  1027	    from classifier fields (research_goal, pattern_category, change_goal,
  1028	    model_families) instead of the raw user query, keeping implementation
  1029	    prompts free of undirected retrieval pollution.
  1030	    """
  1670	        # newer keyword arguments.
  1671	        optional_reply_kwargs = (
  1672	            "graph_summary", "adaptation_plan",
  1673	            "research_sources", "research_warnings", "research_precedent_slices",
  1674	            "effective_route", "effective_task",
  1675	            "candidate_present",
  1676	        )
  1677	        while True:
  1678	            try:
  1679	                result = run_reply_turn(request.query, **reply_kwargs)
  1680	                break
  1681	            except TypeError as exc:
  1682	                message = str(exc)
  1683	                rejected_key = next(
  1684	                    (
  1685	                        key
  1686	                        for key in optional_reply_kwargs
  1687	                        if key in reply_kwargs and key in message
  1688	                    ),
  1689	                    None,
  1690	                )
  1691	                if rejected_key is None:
  1692	                    raise
  1693	                reply_kwargs.pop(rejected_key, None)
  1694	        if isinstance(result, str):
  1695	            return result
  1696	        if isinstance(result, dict):
  1697	            for key in ("reply", "message", "text"):
  1698	                value = result.get(key)
  1699	                if isinstance(value, str) and value.strip():
  1700	                    return value
  1701	        failure = failure_envelope(
  1702	            FailureKind.VALIDATION_ERROR,
  1703	            "reply",
  1704	            agent_failure_context={
  1705	                "explanation": "Reply phase returned a response without reply text."
  1706	            },
  1707	        )
  1708	        raise _ExecutorPhaseError(
  1709	            stage="reply",
  1710	            failure_kind=failure.kind.value,
  1711	            message=failure.user_facing_message,
  1712	            failure_envelope=failure,
  1713	        )
  1714	    except (ProviderError, AuthError, MalformedModelJSON,
  1715	            MissingRequiredField, TimeoutError) as exc:
  1716	        failure = classify_failure("agent_response", exc)
  1717	        failure = _enrich_failure_envelope(failure, exc)
  1718	        raise _ExecutorPhaseError(
  1719	            stage="reply",
  1720	            failure_kind=failure.kind.value,
  1721	            message=failure.user_facing_message,
  1722	            failure_envelope=failure,
  1723	            model_attempts=_failure_model_attempts(failure),
  1724	        ) from exc
  1725	    except Exception as exc:
  1726	        failure = classify_failure("reply", exc)
  1727	        failure = _enrich_failure_envelope(failure, exc)
  1728	        raise _ExecutorPhaseError(
  1729	            stage="reply",
  1730	            failure_kind=failure.kind.value,
  1731	            message=failure.user_facing_message,
  1732	            failure_envelope=failure,
  1733	            model_attempts=_failure_model_attempts(failure),
  1734	        ) from exc
  1735
  1736
  1737	# ── internal error wrapper ───────────────────────────────────────────────────
  1738
  1739
  1740	class _ExecutorPhaseError(Exception):
  1741	    """Internal exception that carries a pre-built :class:`FailureEnvelope`.
  1742
  1743	    Caught by :func:`run_executor` and converted to an
  1744	    :class:`ExecutorResult.failure`.
  1745	    """
  1746
  1747	    def __init__(
  1748	        self,
  1749	        *,
  1750	        stage: str,
  1751	        failure_kind: str,
  1752	        message: str,
  1753	        failure_envelope: Any = None,
  1754	        warning_details: tuple[dict[str, Any], ...] = (),
  1755	        model_attempts: tuple[dict[str, Any], ...] = (),
  1756	    ) -> None:
  1757	        super().__init__(message)
  1758	        self.stage = stage
  1759	        self.failure_kind = failure_kind
  1760	        self.failure_envelope = failure_envelope
  1761	        self.warning_details = tuple(warning_details)
  1762	        self.model_attempts = coerce_model_attempts(model_attempts)
  1763
  1764
  1765	# ── public entry point ───────────────────────────────────────────────────────
  1766
  1767
  1768	def _ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None) -> None:
  1769	    """Best-effort websocket send for executor lifecycle events."""
  1770	    try:
  1771	        from server import PromptServer  # noqa: PLC0415
  1772	    except ImportError:
  1773	        return
  1774	    try:
  1775	        if hasattr(PromptServer.instance, "send_sync") and callable(
  1840	        The parsed executor request (query + optional graph/profile/etc.).
  1841	    classify_only:
  1842	        When True, run only the classify phase and return a diagnostic result
  1843	        without invoking research, implement, or reply model calls.  This is
  1844	        the honest dry-run seam: ``live=false`` is a product flag, but
  1845	        ``classify_only`` guarantees no subsequent phases run.
  1846	    additive:
  1847	        Headless-only caller hint that this is an additive restore (the caller
  1848	        removed a feature and now asks to re-add it).  Forwarded into the
  1849	        implement payload so the revise pipeline can relax ONLY the pre-edit
  1850	        "input graph has dangling/absent endpoints -> refuse to compound"
  1851	        precondition.  All post-edit validation and gates remain enforced.
  1852
  1853	    Returns
  1854	    -------
  1855	    ExecutorResult
  1856	        Always returns a result — failures are captured in the result
  1857	        shape, never raised as raw exceptions.
  1858	    """
  1859	    plan: ClassifyDecision | None = None
  1860	    research_result: ResearchResult | None = None
  1861	    implementation_result: ImplementationResult | None = None
  1862	    effective_graph: dict[str, Any] | None = request.graph
  1863	    result_graph: dict[str, Any] | None = None
  1864	    executor_id = new_profile_id("executor")
  1865	    request_fields = {
  1866	        "executor_id": executor_id,
  1867	        "profile": request.profile or "default",
  1868	        "session_id": request.session_id,
  1869	        "has_graph": request.graph is not None,
  1870	        "query_preview": short_text(request.query),
  1871	    }
  1872
  1873	    profiler_log(LOGGER, "executor.request", **request_fields)
  1874	    usage_token = begin_deepseek_usage_capture()
  1875	    attempt_token = begin_model_attempt_capture()
  1876
  1877	    def _build_report(
  1878	        *,
  1879	        plan: ClassifyDecision | None = None,
  1880	        research: ResearchResult | None = None,
  1881	        implementation: ImplementationResult | None = None,
  1882	        classification_status: str = "",
  1883	        fallback_model_attempts: tuple[dict[str, Any], ...] = (),
  1884	    ) -> Report:
  1885	        usage, cache_breakout_complete = snapshot_deepseek_usage_capture()
  1886	        model_attempts = snapshot_model_attempt_capture()
  1887	        if not model_attempts:
  1888	            model_attempts = coerce_model_attempts(fallback_model_attempts)
  1889	        est_cost_usd, cost_basis = estimate_deepseek_cost_usd(
  1890	            usage,
  1891	            cache_breakout_complete=cache_breakout_complete,
  1892	        )
  1893	        return Report(
  1894	            plan=plan,
  1895	            research=research,
  1896	            implementation=implementation,
  1897	            deepseek_usage=usage,
  1898	            deepseek_est_cost_usd=est_cost_usd,
  1899	            deepseek_cost_basis=cost_basis,
  1900	            classification_status=classification_status,
  1901	            model_attempts=model_attempts,
  1902	        )
  1903
  1904	    def _finish(result: ExecutorResult) -> ExecutorResult:
  1905	        end_deepseek_usage_capture(usage_token)
  1906	        end_model_attempt_capture(attempt_token)
  1907	        return result
  1908
  1909	    # ── Resolve profile specs ────────────────────────────────────────────
  1910	    try:
  1911	        classify_spec = _resolve_spec(request.profile, "classify")
  1912	    except Exception as exc:
  1913	        failure = classify_failure("profile", exc)
  1914	        return _finish(ExecutorResult.failure(
  1915	            kind=failure.kind.value,
  1916	            stage="profile",
  1917	            message=failure.user_facing_message,
  1918	            report=_build_report(),
  1919	        ))
  1920	    profiler_log(
  1960	                plan_task=plan.effective_task,
  1961	            )
  1962	        _emit_executor_phase_event(
  1963	            request,
  1964	            executor_id=executor_id,
  1965	            phase="classify",
  1966	            status="progress",
  1967	            plan=plan,
  1968	            client_id=client_id,
  1969	        )
  1970	        # ── Delegated clarification loop-break ───────────────────────────
  1971	        # When the user responds to a prior clarification with a delegation
  1972	        # phrase ("pick some please", "you decide", etc.), deterministically
  1973	        # continue with the previously blocked edit route instead of asking
  1974	        # again.  This check runs after classify so the model is still called
  1975	        # (preserving prompt context assembly), but the route is overridden
  1976	        # to avoid a clarification loop.
  1977	        delegated_plan: ClassifyDecision | None = None
  1978	        if plan.effective_route == "clarify":
  1979	            delegated_plan = _delegated_clarification_plan(
  1980	                request, session_context
  1981	            )
  1982	        if delegated_plan is not None:
  1983	            plan = delegated_plan
  1984	            LOGGER.info(
  1985	                "executor: delegated clarification follow-up → route=%s task=%s",
  1986	                plan.effective_route,
  1987	                plan.effective_task,
  1988	            )
  1989	        elif plan.effective_route == "clarify":
  1990	            headless_plan = _headless_clarify_research_plan(
  1991	                request,
  1992	                plan,
  1993	                additive=additive,
  1994	            )
  1995	            if headless_plan is not None:
  1996	                plan = headless_plan
  1997	                LOGGER.info(
  1998	                    "executor: clarify_route_blocked_research → headless adapt"
  1999	                )
  2000	            else:
  2001	                intended_route = "adapt" if plan.research else None
  2002	                if plan.intent == "edit":
  2003	                    intended_route = intended_route or "revise"
  2004	                _save_clarification_context(
  2005	                    request,
  2006	                    plan,
  2007	                    blocked_route=intended_route,
  2008	                    blocked_task=(
  2009	                        "edit_graph"
  2010	                        if intended_route in {"revise", "adapt"}
  2011	                        else None
  2012	                    ),
  2013	                )
  2014	    except _ExecutorPhaseError as exc:
  2015	        # The classify phase raised — the report must NOT claim a model
  2016	        # decision (respond_only) that never happened. Record
  2017	        # classification_status=failed and leave the plan None so artifacts
  2018	        # reflect reality: failed classification carries no invented
  2019	        # route/task/intent.
  2020	        report = _build_report(
  2021	            classification_status="failed",
  2022	            fallback_model_attempts=exc.model_attempts,
  2023	        )
  2024	        return _finish(ExecutorResult.failure(
  2025	            kind=exc.failure_kind,
  2026	            stage=exc.stage,
  2027	            message=str(exc),
  2028	            report=report,
  2029	        ))
  2030
  2031	    # ── Classify-only dry-run exit ─────────────────────────────────────────
  2032	    if classify_only:
  2033	        _emit_executor_phase_event(
  2034	            request,
  2035	            executor_id=executor_id,
  2036	            phase="research",
  2037	            status="skipped",
  2038	            client_id=client_id,
  2039	        )
  2040	        _emit_executor_phase_event(
  2041	            request,
  2042	            executor_id=executor_id,
  2043	            phase="implement",
  2044	            status="skipped",
  2045	            client_id=client_id,
  2265	        reply_spec = _resolve_spec(request.profile, "reply")
  2266	    except Exception as exc:
  2267	        failure = classify_failure("profile", exc)
  2268	        report = _build_report(
  2269	            plan=plan,
  2270	            research=research_result,
  2271	            implementation=implementation_result,
  2272	        )
  2273	        return _finish(ExecutorResult.failure(
  2274	            kind=failure.kind.value,
  2275	            stage="profile",
  2276	            message=failure.user_facing_message,
  2277	            report=report,
  2278	        ))
  2279	    try:
  2280	        _emit_executor_phase_event(
  2281	            request,
  2282	            executor_id=executor_id,
  2283	            phase="reply",
  2284	            status="start",
  2285	            client_id=client_id,
  2286	        )
  2287	        with profiler_span(
  2288	            LOGGER,
  2289	            "executor.phase",
  2290	            **request_fields,
  2291	            phase="reply",
  2292	            **_spec_fields(reply_spec),
  2293	        ) as span:
  2294	            reply_text = _run_reply(
  2295	                request,
  2296	                reply_spec,
  2297	                plan=plan,
  2298	                effective_graph=effective_graph,
  2299	                research_result=research_result,
  2300	                implementation_result=implementation_result,
  2301	                graph_inspection=_graph_inspection(effective_graph)
  2302	                if route_behavior.reply_uses_graph_inspection
  2303	                else None,
  2304	            )
  2305	            span.update(reply_preview=short_text(reply_text))
  2306	    except _ExecutorPhaseError as exc:
  2307	        # Preserve durable candidate when reply narration fails.
  2308	        # Narration failure is presentation-only (SD1): the durable
  2309	        # edit work (candidate, gates, proofs, receipts, eligibility)
  2310	        # must not be discarded when only the reply surface fails.
  2311	        if (
  2312	            implementation_result is not None
  2313	            and implementation_result.durable_response is not None
  2314	            and result_graph is not None
  2315	        ):
  2316	            LOGGER.warning(
  2317	                "Reply narration failed after durable edit succeeded "
  2318	                "(stage=%s, kind=%s); preserving implementation with "
  2319	                "deterministic fallback narration.",
  2320	                exc.stage,
  2321	                exc.failure_kind,
  2322	            )
  2323	            report = _build_report(
  2324	                plan=plan,
  2325	                research=research_result,
  2326	                implementation=implementation_result,
  2327	                fallback_model_attempts=exc.model_attempts,
  2328	            )
  2329	            fallback_reply = (
  2330	                implementation_result.message
  2331	                or "Edit completed. The candidate is ready to review."
  2332	            )
  2333	            return _finish(ExecutorResult.success(
  2334	                report=report,
  2335	                graph=result_graph,
  2336	                reply=fallback_reply,
  2337	            ))
  2338
  2339	        report = _build_report(
  2340	            plan=plan,
  2341	            research=research_result,
  2342	            implementation=implementation_result,
  2343	            fallback_model_attempts=exc.model_attempts,
  2344	        )
  2345	        return _finish(ExecutorResult.failure(
  2346	            kind=exc.failure_kind,
  2347	            stage=exc.stage,
  2348	            message=str(exc),
  2349	            report=report,
  2350	        ))
  2351
  2352	    # ── Guard: inspect must never return an edited graph ─────────────────
  2353	    if route_behavior.clears_result_graph:
  2354	        result_graph = None
  2355
  2356	    # ── Assemble success result ──────────────────────────────────────────
  2357	    report = _build_report(
  2358	        plan=plan,
  2359	        research=research_result,
  2360	        implementation=implementation_result,

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/agent_backend.py | sed -n '1,180p'; nl -ba vibecomfy/executor/agent_backend.py | sed -n '180,390p'; git diff --unified=20 45415680..1bd1b04b -- vibecomfy/executor/agent_backend.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 85ms:
     1	"""Executor model-call wrappers over the VibeComfy provider/runtime seam.
     2
     3	These functions bridge the executor's prompt-building + response-parsing
     4	machinery (``prompts.py``) with the provider seam (``provider.run_model_turn``)
     5	so that classify and reply model turns route through the same
     6	provider/runtime/worker stack as the agent-edit loop — preserving subprocess
     7	isolation and never importing Arnold agent backends in the ComfyUI process.
     8
     9	Every function accepts ``route`` and ``model`` kwargs and passes them through
    10	to the provider, ensuring the resolved profile specs reach the worker.
    11	"""
    12
    13	from __future__ import annotations
    14
    15	import logging
    16	import json
    17	from typing import Any, Mapping
    18
    19	from vibecomfy.executor.profiler import new_profile_id, profiler_span, short_text
    20
    21	from .prompts import (
    22	    build_classify_messages,
    23	    build_reply_messages,
    24	    parse_classify_response,
    25	    parse_reply_response,
    26	)
    27	from .contracts import (
    28	    ClassifyDecision,
    29	    ModelAttemptEvidence,
    30	    coerce_model_attempts,
    31	    redact_model_preview,
    32	)
    33
    34	LOGGER = logging.getLogger(__name__)
    35
    36
    37	def _extract_content(result: dict[str, Any]) -> str:
    38	    """Extract the raw model output text from a provider result."""
    39	    content = result.get("content")
    40	    if isinstance(content, str) and content.strip():
    41	        return content
    42	    # Fall back to the json payload's raw text if content is missing.
    43	    json_payload = result.get("json")
    44	    if isinstance(json_payload, dict):
    45	        # Re-serialise the parsed JSON so parsers get text.
    46	        import json
    47
    48	        return json.dumps(json_payload)
    49	    raise ValueError(
    50	        "Model turn result did not contain text content. "
    51	        f"Got keys: {sorted(result.keys())}"
    52	    )
    53
    54
    55	def _preview_raw(text: str | None, *, limit: int = 1200) -> str | None:
    56	    """Bounded, whitespace-normalized preview of raw model output."""
    57	    return redact_model_preview(text, limit=limit)
    58
    59
    60	def _attach_model_turn_evidence(
    61	    exc: BaseException,
    62	    result: dict[str, Any] | None,
    63	    *,
    64	    model: str,
    65	    phase: str,
    66	    raw: str | None,
    67	) -> None:
    68	    """Attach additive parse evidence to a classify/reply exception in place.
    69
    70	    The provider result dict carries the worker's deepseek_usage plus the
    71	    resolved model/phase/endpoint; attaching it (and the raw content preview)
    72	    lets the executor's failure envelope persist tokens + raw preview + context
    73	    without re-resolving provider internals.
    74	    """
    75	    try:
    76	        if result is not None and getattr(exc, "worker_result", None) is None:
    77	            exc.worker_result = dict(result)  # type: ignore[attr-defined]
    78	        if result is not None and getattr(exc, "model_attempts", None) is None:
    79	            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
    80	        if raw is not None and getattr(exc, "raw_response_preview", None) is None:
    81	            exc.raw_response_preview = _preview_raw(raw)  # type: ignore[attr-defined]
    82	        for name, value in (("model", model), ("phase", phase)):
    83	            if getattr(exc, name, None) is None:
    84	                setattr(exc, name, value)
    85	    except Exception:  # noqa: BLE001 - evidence attachment is best-effort
    86	        pass
    87
    88
    89	def _downstream_failure_type(raw: str | None) -> str:
    90	    if not isinstance(raw, str) or not raw.strip():
    91	        return "empty_response"
    92	    stripped = raw.strip()
    93	    if stripped.startswith("```"):
    94	        stripped = stripped.removeprefix("```json").removeprefix("```")
    95	        stripped = stripped.rsplit("```", 1)[0].strip()
    96	    try:
    97	        parsed = json.loads(stripped)
    98	    except (json.JSONDecodeError, TypeError):
    99	        return "malformed_json" if "{" in stripped else "non_json_content"
   100	    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"
   101
   102
   103	def _record_result_attempts(result: dict[str, Any]) -> None:
   104	    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
   105
   106	    record_model_attempts(result.get("model_attempts"))
   107
   108
   109	def _mark_last_attempt_failed(
   110	    result: dict[str, Any], *, raw: str | None, failure_type: str
   111	) -> None:
   112	    attempts = list(coerce_model_attempts(result.get("model_attempts")))
   113	    if not attempts:
   114	        return
   115	    latest = dict(attempts[-1])
   116	    latest.update({
   117	        "outcome": "failure",
   118	        "failure_type": failure_type,
   119	        "raw_response_preview": raw,
   120	    })
   121	    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
   122	    attempts[-1] = revised
   123	    result["model_attempts"] = attempts
   124	    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
   125
   126	    replace_last_model_attempt(revised)
   127
   128
   129	def run_classify_turn(
   130	    query: str,
   131	    *,
   132	    route: str,
   133	    model: str,
   134	    effort: str | None = None,
   135	    has_graph: bool = False,
   136	    graph_summary: str | None = None,
   137	    layout_hint: Mapping[str, Any] | None = None,
   138	    messages: list[dict[str, str]] | None = None,
   139	) -> ClassifyDecision:
   140	    """Run a single classify model turn through the provider seam.
   141
   142	    Builds classify-specific messages via :func:`build_classify_messages`,
   143	    dispatches through :func:`run_model_turn` with ``response_contract="json"``,
   144	    and parses the result with :func:`parse_classify_response`.
   145
   146	    When *messages* is provided, it is used directly instead of building
   147	    messages from *query* / *has_graph* / *graph_summary*.  This allows
   148	    callers to pre-enrich messages with session context and graph reference
   149	    maps without changing the classify route signature.
   150
   151	    Parameters
   152	    ----------
   153	    query:
   154	        The user's natural-language request.
   155	    route:
   156	        Provider route name (resolved from the profile's ``agent`` field).
   157	    model:
   158	        Model identifier (resolved from the profile's ``model`` field).
   159	    has_graph:
   160	        Whether a ComfyUI canvas graph is attached to the request.
   161	    graph_summary:
   162	        Optional compact summary of the attached graph (≤ 200 chars).
   163	    layout_hint:
   164	        Optional compact deterministic layout evidence for classify context.
   165	    messages:
   166	        Optional pre-built messages list.  When provided, skips the default
   167	        message building and uses this list directly.
   168	    """
   169	    if messages is None:
   170	        messages = build_classify_messages(
   171	            query,
   172	            has_graph=has_graph,
   173	            graph_summary=graph_summary,
   174	            layout_hint=layout_hint,
   175	        )
   176	    model_turn_id = new_profile_id("model")
   177	    with profiler_span(
   178	        LOGGER,
   179	        "executor.model_turn",
   180	        model_turn_id=model_turn_id,
   180	        model_turn_id=model_turn_id,
   181	        backend_phase="classify",
   182	        route=route,
   183	        model=model,
   184	        response_contract="json",
   185	        has_graph=has_graph,
   186	        graph_summary=graph_summary,
   187	        query_preview=short_text(query),
   188	    ) as span:
   189	        from vibecomfy.comfy_nodes.agent.provider import run_model_turn
   190
   191	        result = run_model_turn(
   192	            query,
   193	            messages,
   194	            route=route,
   195	            model=model,
   196	            effort=effort,
   197	            response_contract="json",
   198	            profiling_context={"backend_phase": "classify"},
   199	        )
   200	        raw: str | None = None
   201	        try:
   202	            raw = _extract_content(result)
   203	            decision = parse_classify_response(raw)
   204	        except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
   205	            _mark_last_attempt_failed(
   206	                result,
   207	                raw=raw,
   208	                failure_type=_downstream_failure_type(raw),
   209	            )
   210	            _attach_model_turn_evidence(
   211	                exc,
   212	                result,
   213	                model=model,
   214	                phase="classify",
   215	                raw=raw,
   216	            )
   217	            raise
   218	        _record_result_attempts(result)
   219	        span.update(
   220	            content_length=len(raw),
   221	            plan_research=decision.research,
   222	            plan_implement=decision.implement,
   223	            plan_reply=decision.reply,
   224	        )
   225	        return decision
   226
   227
   228	def run_reply_turn(
   229	    query: str,
   230	    *,
   231	    route: str,
   232	    model: str,
   233	    effort: str | None = None,
   234	    plan: ClassifyDecision | None = None,
   235	    research_summary: str | None = None,
   236	    research_sources: tuple[dict[str, Any], ...] | None = None,
   237	    research_warnings: tuple[str, ...] | None = None,
   238	    research_precedent_slices: tuple[dict[str, Any], ...] | None = None,
   239	    implementation_message: str | None = None,
   240	    graph_summary: str | None = None,
   241	    graph_inspection: str | None = None,
   242	    adaptation_plan: dict[str, Any] | None = None,
   243	    effective_route: str | None = None,
   244	    effective_task: str | None = None,
   245	    candidate_present: bool = False,
   246	) -> str:
   247	    """Run a single reply model turn through the provider seam.
   248
   249	    Builds reply-specific messages via :func:`build_reply_messages`,
   250	    dispatches through :func:`run_model_turn` with ``response_contract="json"``,
   251	    and parses the result with :func:`parse_reply_response`.
   252
   253	    Parameters
   254	    ----------
   255	    query:
   256	        The user's natural-language request.
   257	    route:
   258	        Provider route name (resolved from the profile's ``agent`` field).
   259	    model:
   260	        Model identifier (resolved from the profile's ``model`` field).
   261	    plan:
   262	        The classify decision (provides context for the reply).
   263	    research_summary:
   264	        Optional research findings summary.
   265	    research_sources:
   266	        Optional deduplicated research sources for reply context.
   267	    implementation_message:
   268	        Optional implementation result message.
   269	    graph_summary:
   270	        Optional compact summary of the attached graph.
   271	    graph_inspection:
   272	        Optional detailed node-by-node graph inspection for inspect-only
   273	        replies.  When provided, the model should describe the graph
   274	        structure without suggesting edits.
   275	    adaptation_plan:
   276	        Optional serialized adaptation plan for route="adapt" replies.
   277	    effective_route:
   278	        The canonical route driving the reply phase.
   279	    effective_task:
   280	        The canonical task driving the reply phase.
   281	    candidate_present:
   282	        Whether a graph edit candidate was produced.
   283	    """
   284	    messages = build_reply_messages(
   285	        query,
   286	        plan=plan,
   287	        research_summary=research_summary,
   288	        research_sources=research_sources,
   289	        research_warnings=research_warnings,
   290	        research_precedent_slices=research_precedent_slices,
   291	        implementation_message=implementation_message,
   292	        graph_summary=graph_summary,
   293	        graph_inspection=graph_inspection,
   294	        adaptation_plan=adaptation_plan,
   295	        effective_route=effective_route,
   296	        effective_task=effective_task,
   297	        candidate_present=candidate_present,
   298	    )
   299	    model_turn_id = new_profile_id("model")
   300	    with profiler_span(
   301	        LOGGER,
   302	        "executor.model_turn",
   303	        model_turn_id=model_turn_id,
   304	        backend_phase="reply",
   305	        route=route,
   306	        model=model,
   307	        response_contract="json",
   308	        query_preview=short_text(query),
   309	    ) as span:
   310	        from vibecomfy.comfy_nodes.agent.provider import run_model_turn
   311
   312	        result = run_model_turn(
   313	            query,
   314	            messages,
   315	            route=route,
   316	            model=model,
   317	            effort=effort,
   318	            response_contract="json",
   319	            profiling_context={"backend_phase": "reply"},
   320	        )
   321	        raw: str | None = None
   322	        try:
   323	            raw = _extract_content(result)
   324	            reply = parse_reply_response(raw)
   325	        except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
   326	            _mark_last_attempt_failed(
   327	                result,
   328	                raw=raw,
   329	                failure_type=_downstream_failure_type(raw),
   330	            )
   331	            _attach_model_turn_evidence(
   332	                exc,
   333	                result,
   334	                model=model,
   335	                phase="reply",
   336	                raw=raw,
   337	            )
   338	            raise
   339	        _record_result_attempts(result)
   340	        span.update(content_length=len(raw), reply_preview=short_text(reply))
   341	        return reply
   342
   343
   344	__all__ = ["run_classify_turn", "run_reply_turn"]
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/executor/agent_backend.py b/vibecomfy/executor/agent_backend.py
index 1e701f41..c7e89378 100644
--- a/vibecomfy/executor/agent_backend.py
+++ b/vibecomfy/executor/agent_backend.py
@@ -1,107 +1,148 @@
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
+from .contracts import (
+    ClassifyDecision,
+    ModelAttemptEvidence,
+    coerce_model_attempts,
+    redact_model_preview,
+)

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
@@ -144,48 +185,54 @@ def run_classify_turn(
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
@@ -259,33 +306,39 @@ def run_reply_turn(
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
/bin/zsh -lc 'rg -n "''^def run_model_turn|_normalize_model_response|_call_model_runtime|audit_metadata=_audit" vibecomfy/comfy_nodes/agent/provider.py; nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '"'1080,1265p'; nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '1265,1365p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
1250:            audit_metadata=_audit_with_runtime_attempts({
1558:def run_model_turn(
  1080	    messages = build_messages(task=task, python_source=python_source, execution_mode="sandboxed_loose")
  1081	    run_agent_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn", None)
  1082	    if callable(run_agent_turn_fn):
  1083	        return run_agent_turn_fn(
  1084	            task=task,
  1085	            python_source=python_source,
  1086	            route=route,
  1087	            model=model,
  1088	            effort=effort,
  1089	            messages=messages,
  1090	        )
  1091	    run_fn: Callable[..., Any] | None = getattr(runtime, "run", None)
  1092	    if callable(run_fn):
  1093	        return run_fn(
  1094	            task=task,
  1095	            python_source=python_source,
  1096	            route=route,
  1097	            model=model,
  1098	            effort=effort,
  1099	            messages=messages,
  1100	        )
  1101	    raise ProviderError("Arnold/Hermes runtime does not expose run_agent_turn or run.")
  1102
  1103
  1104	def _call_delta_runtime(
  1105	    runtime: Any,
  1106	    *,
  1107	    task: str,
  1108	    projection: str,
  1109	    op_schema: Mapping[str, Any],
  1110	    route: str,
  1111	    model: str | None,
  1112	    effort: str | None = None,
  1113	) -> Any:
  1114	    messages = build_delta_messages(task=task, projection=projection, op_schema=op_schema)
  1115	    run_agent_turn_delta_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn_delta", None)
  1116	    if callable(run_agent_turn_delta_fn):
  1117	        return run_agent_turn_delta_fn(
  1118	            task=task,
  1119	            projection=projection,
  1120	            op_schema=op_schema,
  1121	            route=route,
  1122	            model=model,
  1123	            effort=effort,
  1124	            messages=messages,
  1125	        )
  1126	    run_delta_agent_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_delta_agent_turn", None)
  1127	    if callable(run_delta_agent_turn_fn):
  1128	        return run_delta_agent_turn_fn(
  1129	            task=task,
  1130	            projection=projection,
  1131	            op_schema=op_schema,
  1132	            route=route,
  1133	            model=model,
  1134	            effort=effort,
  1135	            messages=messages,
  1136	        )
  1137	    run_fn: Callable[..., Any] | None = getattr(runtime, "run", None)
  1138	    if callable(run_fn):
  1139	        return run_fn(
  1140	            task=task,
  1141	            projection=projection,
  1142	            op_schema=op_schema,
  1143	            route=route,
  1144	            model=model,
  1145	            effort=effort,
  1146	            messages=messages,
  1147	            response_contract="delta",
  1148	        )
  1149	    raise ProviderError("Arnold/Hermes runtime does not expose run_agent_turn_delta or run.")
  1150
  1151
  1152	def run_agent_turn(
  1153	    task: str,
  1154	    python_source: str,
  1155	    *,
  1156	    route: str | None = None,
  1157	    model: str | None = None,
  1158	    effort: str | None = None,
  1159	) -> AgentTurnResult:
  1160	    route_descriptor = _resolve_agent_route(route)
  1161	    selected_route = route_descriptor.normalized_route
  1162	    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
  1163	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
  1164	    runtime = _load_arnold_runtime()
  1165	    try:
  1166	        response = _call_runtime(
  1167	            runtime,
  1168	            task=task,
  1169	            python_source=python_source,
  1170	            route=dispatch_route,
  1171	            model=selected_model,
  1172	            effort=effort,
  1173	        )
  1174	    except PermissionError as exc:
  1175	        raise AuthError(str(exc)) from exc
  1176	    except TimeoutError:
  1177	        raise
  1178	    except ImportError:
  1179	        # The agent runtime could not be loaded — a setup fault, not a
  1180	        # transient provider outage.  Preserve the type so it is classified
  1181	        # as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure.
  1182	        raise
  1183	    except (ProviderError, MalformedModelJSON, MissingRequiredField):
  1184	        raise
  1185	    except Exception as exc:
  1186	        raise ProviderError(str(exc)) from exc
  1187	    return _normalize_agent_response(
  1188	        response,
  1189	        route=dispatch_route,
  1190	        model=selected_model,
  1191	        audit_metadata={
  1192	            "provider": "arnold",
  1193	            "requested_route": route_descriptor.requested_route,
  1194	            "route_metadata": route_descriptor.to_dict(),
  1195	            "legacy_deepseek_fallback_enabled": False,
  1196	            "credential_presence": _credential_presence(),
  1197	        },
  1198	    )
  1199
  1200
  1201	def run_agent_turn_delta(
  1202	    task: str,
  1203	    projection: str,
  1204	    *,
  1205	    op_schema: Mapping[str, Any] | None = None,
  1206	    route: str | None = None,
  1207	    model: str | None = None,
  1208	    effort: str | None = None,
  1209	):
  1210	    from vibecomfy.porting.edit.ops import (
  1211	        EDIT_OP_RESPONSE_SCHEMA_V2,
  1212	        EditOpParseError,
  1213	        normalize_delta_agent_response,
  1214	    )
  1215
  1216	    route_descriptor = _resolve_agent_route(route)
  1217	    selected_route = route_descriptor.normalized_route
  1218	    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
  1219	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
  1220	    schema = op_schema or EDIT_OP_RESPONSE_SCHEMA_V2
  1221	    runtime = _load_arnold_runtime()
  1222	    try:
  1223	        response = _call_delta_runtime(
  1224	            runtime,
  1225	            task=task,
  1226	            projection=projection,
  1227	            op_schema=schema,
  1228	            route=dispatch_route,
  1229	            model=selected_model,
  1230	            effort=effort,
  1231	        )
  1232	    except PermissionError as exc:
  1233	        raise AuthError(str(exc)) from exc
  1234	    except TimeoutError:
  1235	        raise
  1236	    except ImportError:
  1237	        # The agent runtime could not be loaded — a setup fault, not a
  1238	        # transient provider outage.  Preserve the type so it is classified
  1239	        # as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure.
  1240	        raise
  1241	    except (ProviderError, MalformedModelJSON, MissingRequiredField):
  1242	        raise
  1243	    except Exception as exc:
  1244	        raise ProviderError(str(exc)) from exc
  1245	    try:
  1246	        return normalize_delta_agent_response(
  1247	            response,
  1248	            route=dispatch_route,
  1249	            model=selected_model,
  1250	            audit_metadata=_audit_with_runtime_attempts({
  1251	                "provider": "arnold",
  1252	                "requested_route": route_descriptor.requested_route,
  1253	                "route_metadata": route_descriptor.to_dict(),
  1254	                "legacy_deepseek_fallback_enabled": False,
  1255	                "credential_presence": _credential_presence(),
  1256	                "response_contract": "delta",
  1257	            }, response),
  1258	        )
  1259	    except EditOpParseError as exc:
  1260	        raise MalformedModelJSON(str(exc), parse_reason=exc.code) from exc
  1261
  1262
  1263	def _normalize_batch_response(
  1264	    response: Any,
  1265	    *,
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
  1331	        return run_agent_turn_batch_fn(
  1332	            task=task,
  1333	            route=route,
  1334	            model=model,
  1335	            effort=effort,
  1336	            messages=messages,
  1337	        )
  1338	    run_agent_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_agent_turn", None)
  1339	    if callable(run_agent_turn_fn):
  1340	        return run_agent_turn_fn(
  1341	            task=task,
  1342	            python_source="",
  1343	            route=route,
  1344	            model=model,
  1345	            effort=effort,
  1346	            messages=messages,
  1347	        )
  1348	    run_fn: Callable[..., Any] | None = getattr(runtime, "run", None)
  1349	    if callable(run_fn):
  1350	        return run_fn(
  1351	            task=task,
  1352	            route=route,
  1353	            model=model,
  1354	            effort=effort,
  1355	            messages=messages,
  1356	            response_contract="batch_repl",
  1357	        )
  1358	    raise ProviderError(
  1359	        "Arnold/Hermes runtime does not expose run_agent_turn_batch, "
  1360	        "run_agent_turn, or run."
  1361	    )
  1362
  1363
  1364	def _batch_retry_messages(
  1365	    messages: list[dict[str, str]],

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '1550,1665p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 6ms:
  1550	        # as a non-retryable AGENT_RUNTIME_UNAVAILABLE failure.
  1551	        raise
  1552	    except (ProviderError, MalformedModelJSON, MissingRequiredField):
  1553	        raise
  1554	    except Exception as exc:
  1555	        raise ProviderError(str(exc)) from exc
  1556
  1557
  1558	def run_model_turn(
  1559	    task: str,
  1560	    messages: list[dict[str, Any]] | None = None,
  1561	    *,
  1562	    route: str | None = None,
  1563	    model: str | None = None,
  1564	    effort: str | None = None,
  1565	    response_contract: str = "json",
  1566	    profiling_context: Mapping[str, Any] | None = None,
  1567	) -> dict[str, Any]:
  1568	    """Run a generic JSON/text model turn through the Arnold/Hermes provider.
  1569
  1570	    This is the provider-level compatibility seam used by the executor's
  1571	    classify/reply phases.  Agent-edit turns keep using the stricter
  1572	    python/batch-specific entry points above.
  1573	    """
  1574	    route_descriptor = _resolve_agent_route(route)
  1575	    selected_route = route_descriptor.normalized_route
  1576	    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
  1577	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
  1578	    phase = (
  1579	        profiling_context.get("backend_phase")
  1580	        if isinstance(profiling_context, Mapping)
  1581	        else None
  1582	    )
  1583	    runtime = _load_arnold_runtime()
  1584	    run_model_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_model_turn", None)
  1585	    try:
  1586	        if callable(run_model_turn_fn):
  1587	            response = run_model_turn_fn(
  1588	                task=task,
  1589	                messages=messages,
  1590	                route=dispatch_route,
  1591	                model=selected_model,
  1592	                effort=effort,
  1593	                response_contract=response_contract,
  1594	                profiling_context=profiling_context,
  1595	            )
  1596	        else:
  1597	            run_fn: Callable[..., Any] | None = getattr(runtime, "run", None)
  1598	            if not callable(run_fn):
  1599	                raise ProviderError("Arnold/Hermes runtime does not expose run_model_turn or run.")
  1600	            response = run_fn(
  1601	                task=task,
  1602	                messages=messages,
  1603	                route=dispatch_route,
  1604	                model=selected_model,
  1605	                effort=effort,
  1606	                response_contract=response_contract,
  1607	                profiling_context=profiling_context,
  1608	            )
  1609	    except PermissionError as exc:
  1610	        raise AuthError(str(exc)) from exc
  1611	    except TimeoutError:
  1612	        raise
  1613	    except ImportError:
  1614	        raise
  1615	    except (ProviderError, MalformedModelJSON, MissingRequiredField) as exc:
  1616	        # Same exception object propagates — keep its evidence attrs intact and
  1617	        # add the provider-known model/phase for the classify/reply envelope.
  1618	        # ``as exc`` is load-bearing: without it the name is unbound in this
  1619	        # clause and evidence attachment raises UnboundLocalError, destroying
  1620	        # the original exception type + evidence.
  1621	        _attach_provider_context(exc, model=selected_model, phase=phase)
  1622	        raise
  1623	    except Exception as exc:
  1624	        wrapped = ProviderError(str(exc))
  1625	        _forward_evidence_attrs(exc, wrapped)
  1626	        _attach_provider_context(wrapped, model=selected_model, phase=phase)
  1627	        raise wrapped from exc
  1628
  1629	    if not isinstance(response, Mapping):
  1630	        raise ProviderError("Generic model turn returned a non-dict response.")
  1631	    return dict(response)
  1632
  1633
  1634	def readiness(*, route: str | None = None, model: str | None = None) -> dict[str, Any]:
  1635	    route_descriptor, selected_route, selected_model = _resolve_route_and_model(route, model)
  1636	    LOGGER.info(
  1637	        "readiness(route=%r, model=%r) -> selected_route=%r selected_model=%r",
  1638	        route, model, selected_route, selected_model,
  1639	    )
  1640	    try:
  1641	        runtime = _load_arnold_runtime()
  1642	    except ProviderError as exc:
  1643	        LOGGER.info("readiness runtime unavailable: %s", exc)
  1644	        return {
  1645	            **_provider_status_metadata(
  1646	                route_descriptor=route_descriptor,
  1647	                selected_route=selected_route,
  1648	                selected_model=selected_model,
  1649	                provider_available=False,
  1650	            ),
  1651	            "ready": False,
  1652	            "reason": str(exc),
  1653	            "error": str(exc),
  1654	        }
  1655
  1656	    # Probe the runtime with the REQUESTED route (e.g. "anthropic" /
  1657	    # "openai-codex"), not the collapsed normalized one, so the runtime can
  1658	    # report honest per-route readiness. The surrounding provider metadata still
  1659	    # carries the normalized ``selected_route``.
  1660	    probe_route = route_descriptor.requested_route or selected_route
  1661	    readiness_fn: Callable[..., Any] | None = getattr(runtime, "readiness", None)
  1662	    if callable(readiness_fn):
  1663	        raw_status = readiness_fn(route=probe_route, model=selected_model)
  1664	    else:
  1665	        status_fn: Callable[..., Any] | None = getattr(runtime, "get_agent_status", None)

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/runner.py | sed -n '90,340p'; nl -ba tests/live_agentic_harness/runner.py | sed -n '340,460p'; git diff --unified=20 45415680..1bd1b04b -- tests/live_agentic_harness/runner.py | sed -n '1,520p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
    90	) -> dict[str, Any]:
    91	    """A failing guard for scenarios that errored/timed out in the runner itself."""
    92	    return {
    93	        "live_agentic_success": False,
    94	        "metadata_success": False,
    95	        "failure_class": failure_class,
    96	        "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
    97	        "assessment": {
    98	            "passed": False,
    99	            "expect_graph_changed": expect_graph_changed,
   100	            "issue_count": 1,
   101	            "error_count": 1,
   102	            "issues": [
   103	                {
   104	                    "check": "runner",
   105	                    "severity": "error",
   106	                    "detail": detail,
   107	                    "failure_class": failure_class,
   108	                }
   109	            ],
   110	        },
   111	    }
   112
   113
   114	def _failure_summary(
   115	    scenario_id: str,
   116	    output_base: Any,
   117	    tag: str,
   118	    detail: str,
   119	    *,
   120	    failure_class: str = "runner_error",
   121	    attempt: int | None = None,
   122	    expect_graph_changed: bool = False,
   123	    stdout_tail: str | None = None,
   124	    stderr_tail: str | None = None,
   125	    elapsed_s: float | None = None,
   126	) -> dict[str, Any]:
   127	    return {
   128	        "scenario_id": scenario_id,
   129	        "status": "error",
   130	        "ok": False,
   131	        "error": detail,
   132	        "output_dir": str(_output_dir_for(output_base, tag, scenario_id)),
   133	        "guard": _synthetic_guard(
   134	            detail,
   135	            failure_class=failure_class,
   136	            expect_graph_changed=expect_graph_changed,
   137	        ),
   138	        "failure_class": failure_class,
   139	        "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
   140	        "retryable_infra": failure_class == "infra_empty_response",
   141	        "agent_exercised": False,
   142	        "attempt": attempt,
   143	        "elapsed_s": elapsed_s,
   144	        "stdout_tail": stdout_tail,
   145	        "stderr_tail": stderr_tail,
   146	        "deepseek_usage": {},
   147	        "deepseek_est_cost_usd": 0.0,
   148	        "deepseek_cost_basis": "not_available",
   149	    }
   150
   151
   152	def _persist_scenario_summary(summary: dict[str, Any], output_base: Any, tag: str) -> None:
   153	    scenario_id = str(summary.get("scenario_id") or "")
   154	    if not scenario_id:
   155	        return
   156	    output_dir = Path(summary.get("output_dir") or _output_dir_for(output_base, tag, scenario_id))
   157	    _write_json_atomic(output_dir / "agentic_summary.json", summary)
   158
   159
   160	def _persist_canonical_scenario_summary(
   161	    summary: dict[str, Any],
   162	    output_base: Any,
   163	    tag: str,
   164	    scenario_id: str,
   165	) -> None:
   166	    _write_json_atomic(_output_dir_for(output_base, tag, scenario_id) / "agentic_summary.json", summary)
   167
   168
   169	def _attempt_tag(tag: str, scenario_id: str, attempt: int) -> str:
   170	    return f"{tag}/attempts/{scenario_id}/attempt_{attempt}"
   171
   172
   173	def _attempt_record(summary: dict[str, Any], *, attempt: int) -> dict[str, Any]:
   174	    return {
   175	        "attempt": attempt,
   176	        "scenario_id": summary.get("scenario_id"),
   177	        "status": summary.get("status"),
   178	        "ok": summary.get("ok"),
   179	        "output_dir": summary.get("output_dir"),
   180	        "error": summary.get("error"),
   181	        "failure_class": summary.get("failure_class")
   182	        or (summary.get("guard") or {}).get("failure_class")
   183	        or "product_or_assessment_failure",
   184	        "score_class": summary.get("score_class") or (summary.get("guard") or {}).get("score_class"),
   185	        "retryable_infra": bool(summary.get("retryable_infra")),
   186	        "agent_exercised": summary.get("agent_exercised"),
   187	        "elapsed_s": summary.get("elapsed_s"),
   188	        "live_agentic_success": (summary.get("guard") or {}).get("live_agentic_success"),
   189	        "model_attempts": summary.get("model_attempts", []),
   190	    }
   191
   192
   193	def _latest_failed_model_attempt(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
   194	    attempts = summary.get("model_attempts")
   195	    if not isinstance(attempts, (list, tuple)):
   196	        return None
   197	    for attempt in reversed(attempts):
   198	        if isinstance(attempt, Mapping) and attempt.get("outcome") == "failure":
   199	            return attempt
   200	    return None
   201
   202
   203	def _summary_completion_tokens(summary: dict[str, Any]) -> int | None:
   204	    """Observed completion tokens of the attempt's model call, or None when absent.
   205
   206	    The attempt summary (agentic_summary) carries ``deepseek_usage`` at the top
   207	    level — the executor result's usage dict.  ``completion_tokens == 0`` is the
   208	    structured evidence of an empty/transport response; absence of the record is
   209	    NOT evidence, so it never classifies as infra.
   210	    """
   211	    attempt = _latest_failed_model_attempt(summary)
   212	    usage = attempt.get("token_usage") if isinstance(attempt, Mapping) else None
   213	    if not isinstance(usage, Mapping):
   214	        return None
   215	    value = usage.get("completion_tokens")
   216	    if not isinstance(value, (int, float)):
   217	        return None
   218	    return int(value)
   219
   220
   221	def _provider_infra_failure_class(summary: dict[str, Any]) -> str | None:
   222	    """Map only canonical typed attempt evidence; never inspect response prose."""
   223	    attempt = _latest_failed_model_attempt(summary)
   224	    if attempt is None:
   225	        return None
   226	    failure_type = attempt.get("failure_type")
   227	    if failure_type == "empty_response" and _summary_completion_tokens(summary) == 0:
   228	        return "infra_empty_response"
   229	    if failure_type == "timeout":
   230	        return "infra_timeout"
   231	    if failure_type == "provider_failure":
   232	        return "infra_provider_capacity"
   233	    return None
   234
   235
   236	def _mark_summary_as_infra(summary: dict[str, Any], failure_class: str) -> None:
   237	    summary["failure_class"] = failure_class
   238	    summary["score_class"] = "infra_blocked"
   239	    summary["retryable_infra"] = failure_class == "infra_empty_response"
   240	    guard = summary.get("guard")
   241	    if isinstance(guard, dict):
   242	        guard["failure_class"] = failure_class
   243	        guard["score_class"] = "infra_blocked"
   244	        assessment = guard.get("assessment")
   245	        if isinstance(assessment, dict):
   246	            assessment.setdefault("issues", []).append(
   247	                {
   248	                    "check": "infra_classification",
   249	                    "severity": "warning",
   250	                    "detail": (
   251	                        f"{failure_class} failure was classified as "
   252	                        "infrastructure, not product quality."
   253	                    ),
   254	                    "failure_class": failure_class,
   255	                }
   256	            )
   257
   258
   259	def _clear_stale_retryable_infra_markers(summary: dict[str, Any]) -> None:
   260	    """Drop inherited retryable-infra markers the canonical evidence no longer supports.
   261
   262	    ``failure_class``/``retryable_infra`` are authoritative ONLY while they are
   263	    re-derived from the canonical ``model_attempts`` evidence on the same
   264	    summary. A summary that previously persisted ``infra_empty_response`` (from
   265	    an earlier attempt or a resumed run) must not keep claiming retryability
   266	    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
   267	    """
   268	    stale_retryable = (
   269	        summary.get("failure_class") == "infra_empty_response"
   270	        or summary.get("retryable_infra") is True
   271	    )
   272	    if summary.get("failure_class") == "infra_empty_response":
   273	        del summary["failure_class"]
   274	    if summary.get("retryable_infra") is True:
   275	        summary["retryable_infra"] = False
   276	    if stale_retryable and summary.get("score_class") == "infra_blocked":
   277	        del summary["score_class"]
   278	    guard = summary.get("guard")
   279	    if isinstance(guard, dict):
   280	        if guard.get("failure_class") == "infra_empty_response":
   281	            del guard["failure_class"]
   282	        if stale_retryable and guard.get("score_class") == "infra_blocked":
   283	            del guard["score_class"]
   284
   285
   286	def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
   287	    """Re-derive infra classification from canonical typed evidence only.
   288
   289	    Never trusts inherited ``failure_class``/``retryable_infra`` flags: when the
   290	    canonical ``model_attempts`` evidence supports an infra class the summary is
   291	    marked; otherwise stale retryable-infra markers are cleared so persisted
   292	    summaries cannot mislead later decisions.
   293	    """
   294	    if summary.get("guard", {}).get("live_agentic_success") is True:
   295	        _clear_stale_retryable_infra_markers(summary)
   296	        return summary
   297	    failure_class = _provider_infra_failure_class(summary)
   298	    if failure_class is not None:
   299	        _mark_summary_as_infra(summary, failure_class)
   300	    else:
   301	        _clear_stale_retryable_infra_markers(summary)
   302	    return summary
   303
   304
   305	def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
   306	    """Decide retryability from the CANONICAL typed evidence on every call.
   307
   308	    The decision is the latest failed ``model_attempts`` entry's failure type
   309	    plus the observed completion tokens — never the inherited
   310	    ``failure_class``/``retryable_infra`` flags, which can be stale from an
   311	    earlier attempt. A succeeded scenario is never retried.
   312	    """
   313	    _classify_retryable_infra_summary(summary)
   314	    if summary.get("guard", {}).get("live_agentic_success") is True:
   315	        return False
   316	    return _provider_infra_failure_class(summary) == "infra_empty_response"
   317
   318
   319	def _build_run_summary(
   320	    tag: str,
   321	    summaries: list[dict[str, Any]],
   322	    *,
   323	    total_scenarios: int,
   324	    complete: bool,
   325	) -> dict[str, Any]:
   326	    passed = sum(1 for summary in summaries if summary["guard"].get("live_agentic_success") is True)
   327	    failed = len(summaries) - passed
   328	    raw_first_attempt_passed = sum(
   329	        1
   330	        for summary in summaries
   331	        if summary.get("raw_first_attempt_success", summary["guard"].get("live_agentic_success")) is True
   332	    )
   333	    infra_failures = sum(
   334	        1
   335	        for summary in summaries
   336	        if summary["guard"].get("live_agentic_success") is not True
   337	        and str(summary.get("failure_class") or "").startswith("infra_")
   338	    )
   339	    score_classes: dict[str, int] = {}
   340	    for summary in summaries:
   340	    for summary in summaries:
   341	        score_class = (
   342	            summary.get("score_class")
   343	            or summary["guard"].get("score_class")
   344	            or ("pass" if summary["guard"].get("live_agentic_success") is True else "product_fail")
   345	        )
   346	        score_classes[str(score_class)] = score_classes.get(str(score_class), 0) + 1
   347	    deepseek_usage = add_deepseek_usage(
   348	        *[coerce_deepseek_usage(summary.get("deepseek_usage")) for summary in summaries]
   349	    )
   350	    deepseek_est_cost_usd = float(
   351	        sum(float(summary.get("deepseek_est_cost_usd") or 0.0) for summary in summaries)
   352	    )
   353	    deepseek_cost_basis = combine_deepseek_cost_bases(
   354	        [summary.get("deepseek_cost_basis") for summary in summaries]
   355	    )
   356	    return {
   357	        "tag": tag,
   358	        "scenario_count": len(summaries),
   359	        "total_scenarios": total_scenarios,
   360	        "completed": len(summaries),
   361	        "pending": max(total_scenarios - len(summaries), 0),
   362	        "passed": passed,
   363	        "failed": failed,
   364	        "final_score": f"{passed}/{len(summaries)}",
   365	        "raw_first_attempt_passed": raw_first_attempt_passed,
   366	        "raw_first_attempt_failed": len(summaries) - raw_first_attempt_passed,
   367	        "raw_first_attempt_score": f"{raw_first_attempt_passed}/{len(summaries)}",
   368	        "infra_failures": infra_failures,
   369	        "product_or_assessment_failures": failed - infra_failures,
   370	        "score_classes": score_classes,
   371	        "overall_success": complete and failed == 0 and len(summaries) == total_scenarios,
   372	        "complete": complete,
   373	        "deepseek_usage": deepseek_usage,
   374	        "deepseek_est_cost_usd": deepseek_est_cost_usd,
   375	        "deepseek_cost_basis": deepseek_cost_basis,
   376	        "scenarios": summaries,
   377	    }
   378
   379
   380	def _persist_run_summary(
   381	    tag: str,
   382	    results: list[dict[str, Any] | None],
   383	    output_base: Any,
   384	    *,
   385	    total_scenarios: int,
   386	    complete: bool,
   387	) -> dict[str, Any]:
   388	    summaries = [r for r in results if r]
   389	    summary = _build_run_summary(
   390	        tag,
   391	        summaries,
   392	        total_scenarios=total_scenarios,
   393	        complete=complete,
   394	    )
   395	    run_dir = _run_dir_for(output_base, tag)
   396	    if complete:
   397	        _write_json_atomic(run_dir / "run_summary.json", summary)
   398	        partial = run_dir / "run_summary.partial.json"
   399	        if partial.exists():
   400	            partial.unlink()
   401	    else:
   402	        _write_json_atomic(run_dir / "run_summary.partial.json", summary)
   403	    return summary
   404
   405
   406	def _analysis_index_path_for_summary(run_summary_path: Path) -> Path:
   407	    if run_summary_path.name in {"run_summary.json", "run_summary.partial.json"}:
   408	        return run_summary_path.parent / "failure_analysis" / "index.json"
   409	    return run_summary_path.with_suffix("") / "failure_analysis" / "index.json"
   410
   411
   412	def _run_failure_analysis_from_summary(
   413	    run_summary_path: Path,
   414	    *,
   415	    scenarios_dir: Path,
   416	    analyze_failures_enabled: bool,
   417	    prepare_only: bool,
   418	    recommend_fixes: bool,
   419	    analysis_model: str,
   420	    analysis_max_workers: int,
   421	    analysis_timeout: int,
   422	    resume_failure_analysis: bool,
   423	    recommendations_model: str,
   424	    recommendations_timeout: int,
   425	) -> dict[str, Any]:
   426	    result: dict[str, Any] = {
   427	        "run_summary_path": str(run_summary_path),
   428	        "analysis_index_path": None,
   429	        "recommendations_path": None,
   430	    }
   431	    index_path = _analysis_index_path_for_summary(run_summary_path)
   432	    should_prepare = prepare_only or analyze_failures_enabled or (recommend_fixes and not index_path.exists())
   433	    if should_prepare:
   434	        if analyze_failures_enabled:
   435	            index = analyze_failures(
   436	                run_summary_path,
   437	                scenarios_dir=scenarios_dir,
   438	                model=analysis_model,
   439	                max_workers=analysis_max_workers,
   440	                timeout_s=analysis_timeout,
   441	                resume=resume_failure_analysis,
   442	            )
   443	        else:
   444	            index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)
   445	        result["analysis_index_path"] = str(index_path)
   446	        result["failed_count"] = index.get("failed_count", 0)
   447	    elif index_path.exists():
   448	        result["analysis_index_path"] = str(index_path)
   449	    if recommend_fixes:
   450	        meta = recommendations_for_run(
   451	            run_summary_path,
   452	            model=recommendations_model,
   453	            timeout_s=recommendations_timeout,
   454	        )
   455	        result["recommendations_path"] = meta["output_path"]
   456	        result["recommendations_returncode"] = meta["returncode"]
   457	    return result
   458
   459
   460	def run_single(scenario_path: str, tag: str, output_base: Any, out_file: Path | None) -> dict[str, Any]:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index bbd41e73..94672531 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -1,83 +1,62 @@
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
@@ -141,41 +120,41 @@ def _failure_summary(
     failure_class: str = "runner_error",
     attempt: int | None = None,
     expect_graph_changed: bool = False,
     stdout_tail: str | None = None,
     stderr_tail: str | None = None,
     elapsed_s: float | None = None,
 ) -> dict[str, Any]:
     return {
         "scenario_id": scenario_id,
         "status": "error",
         "ok": False,
         "error": detail,
         "output_dir": str(_output_dir_for(output_base, tag, scenario_id)),
         "guard": _synthetic_guard(
             detail,
             failure_class=failure_class,
             expect_graph_changed=expect_graph_changed,
         ),
         "failure_class": failure_class,
         "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
-        "retryable_infra": failure_class.startswith("infra_"),
+        "retryable_infra": failure_class == "infra_empty_response",
         "agent_exercised": False,
         "attempt": attempt,
         "elapsed_s": elapsed_s,
         "stdout_tail": stdout_tail,
         "stderr_tail": stderr_tail,
         "deepseek_usage": {},
         "deepseek_est_cost_usd": 0.0,
         "deepseek_cost_basis": "not_available",
     }


 def _persist_scenario_summary(summary: dict[str, Any], output_base: Any, tag: str) -> None:
     scenario_id = str(summary.get("scenario_id") or "")
     if not scenario_id:
         return
     output_dir = Path(summary.get("output_dir") or _output_dir_for(output_base, tag, scenario_id))
     _write_json_atomic(output_dir / "agentic_summary.json", summary)


 def _persist_canonical_scenario_summary(
@@ -190,132 +169,168 @@ def _persist_canonical_scenario_summary(
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


+def _clear_stale_retryable_infra_markers(summary: dict[str, Any]) -> None:
+    """Drop inherited retryable-infra markers the canonical evidence no longer supports.
+
+    ``failure_class``/``retryable_infra`` are authoritative ONLY while they are
+    re-derived from the canonical ``model_attempts`` evidence on the same
+    summary. A summary that previously persisted ``infra_empty_response`` (from
+    an earlier attempt or a resumed run) must not keep claiming retryability
+    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
+    """
+    stale_retryable = (
+        summary.get("failure_class") == "infra_empty_response"
+        or summary.get("retryable_infra") is True
+    )
+    if summary.get("failure_class") == "infra_empty_response":
+        del summary["failure_class"]
+    if summary.get("retryable_infra") is True:
+        summary["retryable_infra"] = False
+    if stale_retryable and summary.get("score_class") == "infra_blocked":
+        del summary["score_class"]
+    guard = summary.get("guard")
+    if isinstance(guard, dict):
+        if guard.get("failure_class") == "infra_empty_response":
+            del guard["failure_class"]
+        if stale_retryable and guard.get("score_class") == "infra_blocked":
+            del guard["score_class"]
+
+
 def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
+    """Re-derive infra classification from canonical typed evidence only.
+
+    Never trusts inherited ``failure_class``/``retryable_infra`` flags: when the
+    canonical ``model_attempts`` evidence supports an infra class the summary is
+    marked; otherwise stale retryable-infra markers are cleared so persisted
+    summaries cannot mislead later decisions.
+    """
+    if summary.get("guard", {}).get("live_agentic_success") is True:
+        _clear_stale_retryable_infra_markers(summary)
+        return summary
     failure_class = _provider_infra_failure_class(summary)
-    if failure_class is not None and summary.get("guard", {}).get("live_agentic_success") is not True:
+    if failure_class is not None:
         _mark_summary_as_infra(summary, failure_class)
+    else:
+        _clear_stale_retryable_infra_markers(summary)
     return summary


 def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
+    """Decide retryability from the CANONICAL typed evidence on every call.
+
+    The decision is the latest failed ``model_attempts`` entry's failure type
+    plus the observed completion tokens — never the inherited
+    ``failure_class``/``retryable_infra`` flags, which can be stale from an
+    earlier attempt. A succeeded scenario is never retried.
+    """
     _classify_retryable_infra_summary(summary)
-    return bool(summary.get("retryable_infra")) or str(summary.get("failure_class") or "").startswith("infra_")
+    if summary.get("guard", {}).get("live_agentic_success") is True:
+        return False
+    return _provider_infra_failure_class(summary) == "infra_empty_response"


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

exec
/bin/zsh -lc "rg -n \"_is_retryable_infra_summary|_classify_retryable_infra_summary|attempts\\]\" tests/live_agentic_harness/runner.py | sed -n '1,220p'; nl -ba tests/live_agentic_harness/runner.py | sed -n '520,780p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
286:def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
305:def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
313:    _classify_retryable_infra_summary(summary)
473:    _classify_retryable_infra_summary(summary)
597:                    retryable_infra = _is_retryable_infra_summary(final_summary)
   520	                        f"passed={run_summary['passed']} failed={run_summary['failed']} "
   521	                        f"pending={run_summary['pending']}",
   522	                        file=sys.stderr,
   523	                        flush=True,
   524	                    )
   525
   526	        def worker(idx: int, path: Path) -> None:
   527	            sid = path.stem
   528	            scenario_for_synthetic = _load_scenario(path)
   529	            expect_graph_changed = _scenario_expect_graph_changed(scenario_for_synthetic)
   530	            attempts: list[dict[str, Any]] = []
   531	            with sem:
   532	                max_attempts = 1 + max(0, infra_retries)
   533	                final_summary: dict[str, Any] | None = None
   534	                for attempt in range(1, max_attempts + 1):
   535	                    attempt_run_tag = _attempt_tag(tag, sid, attempt)
   536	                    out_file = tmpdir / f"{idx:03d}-{attempt}.json"
   537	                    cmd = [
   538	                        sys.executable, "-m", "tests.live_agentic_harness.runner",
   539	                        "--single", str(path), "--tag", attempt_run_tag,
   540	                        "--single-out", str(out_file),
   541	                    ]
   542	                    if output_base is not None:
   543	                        cmd += ["--output-base", str(output_base)]
   544	                    started = time.monotonic()
   545	                    try:
   546	                        proc = subprocess.run(
   547	                            cmd, cwd=str(REPO), capture_output=True, text=True,
   548	                            timeout=per_scenario_timeout,
   549	                        )
   550	                        elapsed_s = time.monotonic() - started
   551	                        if out_file.exists():
   552	                            final_summary = json.loads(out_file.read_text(encoding="utf-8"))
   553	                            final_summary["attempt"] = attempt
   554	                            final_summary["elapsed_s"] = elapsed_s
   555	                            final_summary["agent_exercised"] = True
   556	                        else:
   557	                            tail = _trim((proc.stderr or ""))
   558	                            final_summary = _failure_summary(
   559	                                sid,
   560	                                output_base,
   561	                                attempt_run_tag,
   562	                                f"runner produced no summary (rc={proc.returncode}); {tail}",
   563	                                failure_class="infra_no_summary",
   564	                                attempt=attempt,
   565	                                expect_graph_changed=expect_graph_changed,
   566	                                stdout_tail=_trim(proc.stdout or ""),
   567	                                stderr_tail=tail,
   568	                                elapsed_s=elapsed_s,
   569	                            )
   570	                    except subprocess.TimeoutExpired as exc:
   571	                        elapsed_s = time.monotonic() - started
   572	                        final_summary = _failure_summary(
   573	                            sid,
   574	                            output_base,
   575	                            attempt_run_tag,
   576	                            f"scenario exceeded {per_scenario_timeout}s and was killed",
   577	                            failure_class="infra_timeout",
   578	                            attempt=attempt,
   579	                            expect_graph_changed=expect_graph_changed,
   580	                            stdout_tail=_trim((exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
   581	                            stderr_tail=_trim((exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
   582	                            elapsed_s=elapsed_s,
   583	                        )
   584	                    except Exception as exc:  # noqa: BLE001 — isolate one failure
   585	                        elapsed_s = time.monotonic() - started
   586	                        final_summary = _failure_summary(
   587	                            sid,
   588	                            output_base,
   589	                            attempt_run_tag,
   590	                            _trim(str(exc)),
   591	                            failure_class="infra_runner_exception",
   592	                            attempt=attempt,
   593	                            expect_graph_changed=expect_graph_changed,
   594	                            elapsed_s=elapsed_s,
   595	                        )
   596
   597	                    retryable_infra = _is_retryable_infra_summary(final_summary)
   598	                    attempts.append(_attempt_record(final_summary, attempt=attempt))
   599	                    if not retryable_infra:
   600	                        break
   601
   602	                if final_summary is None:
   603	                    final_summary = _failure_summary(
   604	                        sid,
   605	                        output_base,
   606	                        _attempt_tag(tag, sid, 1),
   607	                        "runner produced no attempt result",
   608	                        failure_class="infra_runner_exception",
   609	                        attempt=1,
   610	                        expect_graph_changed=expect_graph_changed,
   611	                    )
   612	                    attempts.append(_attempt_record(final_summary, attempt=1))
   613
   614	                final_summary["attempts"] = attempts
   615	                final_summary["attempt_count"] = len(attempts)
   616	                final_summary["final_attempt"] = attempts[-1]["attempt"]
   617	                final_summary["raw_first_attempt_success"] = attempts[0].get("live_agentic_success") is True
   618	                final_summary["final_success"] = final_summary["guard"].get("live_agentic_success") is True
   619	                final_summary.setdefault(
   620	                    "failure_class",
   621	                    attempts[-1].get("failure_class") or "product_or_assessment_failure",
   622	                )
   623	                final_summary.setdefault(
   624	                    "score_class",
   625	                    attempts[-1].get("score_class") or (
   626	                        "pass"
   627	                        if final_summary["guard"].get("live_agentic_success") is True
   628	                        else "product_fail"
   629	                    ),
   630	                )
   631	                record_result(idx, final_summary)
   632	                _persist_canonical_scenario_summary(
   633	                    final_summary,
   634	                    output_base,
   635	                    tag,
   636	                    sid,
   637	                )
   638
   639	        threads = [
   640	            threading.Thread(target=worker, args=(i, p), daemon=True)
   641	            for i, p in enumerate(paths)
   642	        ]
   643	        for t in threads:
   644	            t.start()
   645	        for t in threads:
   646	            t.join()
   647	    finally:
   648	        for f in tmpdir.glob("*.json"):
   649	            try:
   650	                f.unlink()
   651	            except Exception:  # noqa: BLE001
   652	                pass
   653	        try:
   654	            tmpdir.rmdir()
   655	        except Exception:  # noqa: BLE001
   656	            pass
   657
   658	    return _persist_run_summary(
   659	        tag,
   660	        results,
   661	        output_base,
   662	        total_scenarios=len(paths),
   663	        complete=True,
   664	    )
   665
   666
   667	def _build_parser() -> argparse.ArgumentParser:
   668	    parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
   669	    parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
   670	    parser.add_argument(
   671	        "--scenarios-dir",
   672	        default=None,
   673	        help="Directory containing scenario YAML/JSON files.",
   674	    )
   675	    parser.add_argument(
   676	        "--output-base",
   677	        default=None,
   678	        help="Base evidence directory (default: out/agentic).",
   679	    )
   680	    parser.add_argument(
   681	        "--json",
   682	        action="store_true",
   683	        help="Print JSON summary instead of a short report.",
   684	    )
   685	    parser.add_argument(
   686	        "--single",
   687	        default=None,
   688	        help="Run a SINGLE scenario file (subprocess entry point for parallel mode).",
   689	    )
   690	    parser.add_argument(
   691	        "--single-out",
   692	        default=None,
   693	        help="Path to write the single-scenario summary JSON (used with --single).",
   694	    )
   695	    parser.add_argument(
   696	        "--max-workers",
   697	        type=int,
   698	        default=DEFAULT_MAX_WORKERS,
   699	        help=f"max concurrent scenarios (default {DEFAULT_MAX_WORKERS}).",
   700	    )
   701	    parser.add_argument(
   702	        "--per-scenario-timeout",
   703	        type=int,
   704	        default=DEFAULT_PER_SCENARIO_TIMEOUT,
   705	        help=f"per-scenario seconds before kill (default {DEFAULT_PER_SCENARIO_TIMEOUT}).",
   706	    )
   707	    parser.add_argument(
   708	        "--infra-retries",
   709	        type=int,
   710	        default=DEFAULT_INFRA_RETRIES,
   711	        help=(
   712	            "retry subprocess-level infrastructure failures this many times "
   713	            f"(default {DEFAULT_INFRA_RETRIES}; semantic guard failures are not retried)"
   714	        ),
   715	    )
   716	    parser.add_argument(
   717	        "--progress-every",
   718	        type=int,
   719	        default=DEFAULT_PROGRESS_EVERY,
   720	        help=(
   721	            "emit and persist aggregate progress every N completed scenarios "
   722	            f"(default {DEFAULT_PROGRESS_EVERY}; 0 disables stderr progress)"
   723	        ),
   724	    )
   725	    parser.add_argument(
   726	        "--prepare-failure-analysis",
   727	        action="store_true",
   728	        help="Write per-failed-scenario analysis briefs and index without calling subagents.",
   729	    )
   730	    parser.add_argument(
   731	        "--analyze-failures",
   732	        action="store_true",
   733	        help="After the run, launch one DeepSeek/Hermes diagnosis subagent per failed scenario.",
   734	    )
   735	    parser.add_argument(
   736	        "--analysis-model",
   737	        default=DEFAULT_ANALYSIS_MODEL,
   738	        help=f"Model for per-failure diagnosis agents (default {DEFAULT_ANALYSIS_MODEL}).",
   739	    )
   740	    parser.add_argument(
   741	        "--analysis-max-workers",
   742	        type=int,
   743	        default=DEFAULT_ANALYSIS_WORKERS,
   744	        help=f"Maximum concurrent failure diagnosis agents (default {DEFAULT_ANALYSIS_WORKERS}).",
   745	    )
   746	    parser.add_argument(
   747	        "--analysis-timeout",
   748	        type=int,
   749	        default=DEFAULT_AGENT_TIMEOUT_S,
   750	        help=f"Seconds before killing one failure diagnosis agent (default {DEFAULT_AGENT_TIMEOUT_S}).",
   751	    )
   752	    parser.add_argument(
   753	        "--restart-failure-analysis",
   754	        action="store_true",
   755	        help="Rerun every failed-scenario diagnosis, including ones already marked done.",
   756	    )
   757	    parser.add_argument(
   758	        "--recommend-fixes",
   759	        action="store_true",
   760	        help="Use Codex/GPT-5.5 to synthesize all failure diagnoses into ranked fix recommendations.",
   761	    )
   762	    parser.add_argument(
   763	        "--recommendations-model",
   764	        default=DEFAULT_RECOMMENDATIONS_MODEL,
   765	        help=f"Model for aggregate fix recommendations (default {DEFAULT_RECOMMENDATIONS_MODEL}).",
   766	    )
   767	    parser.add_argument(
   768	        "--recommendations-timeout",
   769	        type=int,
   770	        default=DEFAULT_AGENT_TIMEOUT_S,
   771	        help=f"Seconds before killing aggregate recommendations (default {DEFAULT_AGENT_TIMEOUT_S}).",
   772	    )
   773	    parser.add_argument(
   774	        "--analyze-existing-summary",
   775	        default=None,
   776	        help=(
   777	            "Analyze an existing run_summary.json or redirected summary JSON instead of running scenarios."
   778	        ),
   779	    )
   780	    return parser

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/adapter.py | sed -n '120,175p'; nl -ba vibecomfy/agent/artifacts.py | sed -n '85,180p'; nl -ba vibecomfy/agent/artifacts.py | sed -n '455,585p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   120	    if graph is not None and not isinstance(graph, dict):
   121	        raise ValueError("Scenario `graph` must be a JSON object when supplied.")
   122	    if graph is not None and scenario.get("workflow_path") is not None:
   123	        raise ValueError("Scenario accepts either `graph` or `workflow_path`, not both.")
   124	    if graph is None:
   125	        graph = _load_workflow(scenario.get("workflow_path"))
   126
   127	    request = HeadlessAgentRequest(
   128	        query=query,
   129	        graph=graph,
   130	        workflow_id=scenario.get("workflow_id") or (graph.get("workflow_id") if isinstance(graph, dict) else None),
   131	        session_id=scenario.get("session_id"),
   132	        profile=scenario.get("profile"),
   133	        output_dir=output_dir,
   134	        dry_run=bool(scenario.get("dry_run", False)),
   135	        apply=bool(scenario.get("apply", False)),
   136	        network=bool(scenario.get("network", True)),
   137	        timeout=scenario.get("timeout"),
   138	        additive=bool(scenario.get("additive", False)),
   139	    )
   140
   141	    result = run_headless(request, entrypoint="live_agentic_harness")
   142	    return {
   143	        "scenario_id": scenario_id,
   144	        "status": result.status,
   145	        "ok": result.ok,
   146	        "output_dir": str(output_dir),
   147	        "readiness": result.readiness,
   148	        "error": result.error,
   149	        "deepseek_usage": result.response.get("deepseek_usage", {}),
   150	        "deepseek_est_cost_usd": result.response.get("deepseek_est_cost_usd"),
   151	        "deepseek_cost_basis": result.response.get("deepseek_cost_basis"),
   152	        "model_attempts": result.response.get("model_attempts", []),
   153	    }
    85
    86
    87	def _redact_url_credentials(url: str) -> str:
    88	    """Redact userinfo and credential-like query params inside a URL string.
    89
    90	    Only credential material is touched: userinfo is replaced wholesale and
    91	    query parameter VALUES whose names look credential-like (token/key/sig/
    92	    signature/api_key/apikey/secret + auth headers carried as query params)
    93	    become ``<redacted>``. Every other part of the URL is preserved byte for
    94	    byte (oracle finding 5).
    95	    """
    96	    try:
    97	        parsed = urlsplit(url)
    98	    except ValueError:
    99	        return url
   100	    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
   101	        return url
   102	    netloc = parsed.netloc
   103	    if parsed.username is not None:
   104	        host = parsed.hostname or ""
   105	        if parsed.port is not None:
   106	            host = f"{host}:{parsed.port}"
   107	        netloc = f"<redacted>@{host}"
   108	    query = parsed.query
   109	    if query:
   110	        parts = query.split("&")
   111	        redacted_parts: list[str] = []
   112	        query_changed = False
   113	        for part in parts:
   114	            name, sep, _value = part.partition("=")
   115	            if sep and _is_credential_like_url_param(name):
   116	                redacted_parts.append(f"{name}=<redacted>")
   117	                query_changed = True
   118	            else:
   119	                redacted_parts.append(part)
   120	        if query_changed:
   121	            query = "&".join(redacted_parts)
   122	    if netloc == parsed.netloc and query == parsed.query:
   123	        return url
   124	    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))
   125
   126
   127	def _redact_embedded_secrets(value: str) -> str:
   128	    """Redact authorization headers and credential-bearing URLs in ANY string.
   129
   130	    Ordinary leaves (``content``, ``message``, ``error``, ``url``, ...) can
   131	    persist credentials inside prose, so every string is scanned: full
   132	    ``Authorization: <scheme> <credential>`` header values (every scheme) are
   133	    replaced, and credential-like URL query params / userinfo are redacted.
   134	    Everything else is left untouched.
   135	    """
   136	    redacted = _AUTHORIZATION_HEADER_RE.sub("Authorization: <redacted>", value)
   137	    redacted = _EMBEDDED_URL_RE.sub(
   138	        lambda match: _redact_url_credentials(match.group(0)), redacted
   139	    )
   140	    return redacted
   141
   142
   143	def _redact_string(value: str, *, parent_key: str) -> str:
   144	    if _is_sensitive_key(parent_key):
   145	        return "<redacted>"
   146	    if parent_key.lower() == "endpoint":
   147	        return normalize_model_endpoint(value)
   148	    if parent_key.lower() == "raw_response_preview":
   149	        return redact_model_preview(value) or ""
   150	    return _redact_embedded_secrets(value)
   151
   152
   153	def _redact(value: Any, *, parent_key: str = "") -> Any:
   154	    """Return a JSON-safe copy with credential-like values redacted.
   155
   156	    Walks the artifact recursively and sanitizes EVERY persisted string leaf:
   157	    values under sensitive keys are replaced wholesale, ``endpoint`` and
   158	    ``raw_response_preview`` use their canonical redactors, and ordinary fields
   159	    are scanned for embedded authorization headers and credential-bearing URLs.
   160	    """
   161	    if isinstance(value, str):
   162	        return _redact_string(value, parent_key=parent_key)
   163	    if isinstance(value, Mapping):
   164	        redacted: dict[str, Any] = {}
   165	        for key, item in value.items():
   166	            key_text = str(key)
   167	            redacted[key_text] = _redact(item, parent_key=key_text)
   168	        return redacted
   169	    if isinstance(value, (list, tuple, set)):
   170	        return [_redact(item, parent_key=parent_key) for item in value]
   171	    return _json_safe(value)
   172
   173
   174	def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
   175	    detail = response.get("detail_json_path") or response.get("detail_json_path_resolved")
   176	    if isinstance(detail, str) and detail:
   177	        return Path(detail).parent
   178	    session_path = response.get("session_path") or response.get("session_path_resolved")
   179	    turn_id = response.get("turn_id")
   180	    if isinstance(session_path, str) and session_path and isinstance(turn_id, str) and turn_id:
   455	            )
   456	            _safe_write(
   457	                output_dir / "implementation_payload.json",
   458	                _redact(implementation_payload),
   459	            )
   460	            _append_manifest(manifest, "implementation_payload.json")
   461	            _safe_write(
   462	                output_dir / "implementation_result.json",
   463	                _redact(implementation),
   464	            )
   465	            _append_manifest(manifest, "implementation_result.json")
   466
   467	    turn_dir = _turn_dir_from_response(response)
   468	    copied: list[str] = []
   469	    if turn_dir is not None and turn_dir.is_dir():
   470	        copied = _copy_turn_artifacts(turn_dir, output_dir)
   471	        for copied_name in copied:
   472	            _append_manifest(manifest, copied_name)
   473
   474	    copied_set = set(copied)
   475	    optional_model_artifacts = {
   476	        name: name in copied_set or name in manifest
   477	        for name in sorted(_MODEL_ARTIFACT_NAMES)
   478	    }
   479
   480	    LOGGER.info(
   481	        "headless artifacts synthesized",
   482	        extra={"output_dir": str(output_dir), "artifact_count": len(manifest)},
   483	    )
   484	    return {
   485	        "output_dir": str(output_dir),
   486	        "manifest": manifest,
   487	        "copied_turn_artifacts": copied,
   488	        "optional_model_artifacts": optional_model_artifacts,
   489	        "turn_dir": str(turn_dir) if turn_dir else None,
   490	    }
   491
   492
   493	__all__ = ["synthesize_headless_artifacts"]

exec
/bin/zsh -lc "nl -ba tests/test_headless_agent_artifacts.py | sed -n '180,390p'; nl -ba tests/test_executor_contracts.py | sed -n '630,735p'; nl -ba tests/test_agent_runtime_adapter.py | sed -n '420,640p'; nl -ba tests/test_runtime_worker_retry.py | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   180	    (turn_dir / "response.json").write_text('{"ok": true, "route": "inspect"}\n', encoding="utf-8")
   181	    (turn_dir / "chat.json").write_text('{"messages": []}\n', encoding="utf-8")
   182
   183	    output_dir = tmp_path / "out"
   184	    manifest = synthesize_headless_artifacts(
   185	        request={"query": "synthetic"},
   186	        result=ExecutorResult.success(
   187	            report=Report(plan=ClassifyDecision(route="inspect", task="inspect_graph")),
   188	            reply="inspected",
   189	        ),
   190	        response={
   191	            "ok": True,
   192	            "route": "inspect",
   193	            "detail_json_path": str(turn_dir / "response.json"),
   194	        },
   195	        output_dir=output_dir,
   196	        status="success",
   197	    )
   198
   199	    assert sorted(manifest["copied_turn_artifacts"]) == [
   200	        "chat.json",
   201	        "request.json",
   202	        "response.json",
   203	    ]
   204	    assert manifest["optional_model_artifacts"] == {
   205	        "messages.jsonl": False,
   206	        "model_attempts.json": False,
   207	        "model_request.json": False,
   208	        "model_response.json": False,
   209	    }
   210	    assert not (output_dir / "messages.jsonl").exists()
   211	    assert not (output_dir / "model_request.json").exists()
   212	    assert not (output_dir / "model_response.json").exists()
   213	    assert _read_json(output_dir / "request.json") == {"query": "real"}
   214
   215
   216	def test_headless_artifacts_copy_model_files_when_turn_produced_them(tmp_path: Path) -> None:
   217	    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "0002"
   218	    turn_dir.mkdir(parents=True)
   219	    (turn_dir / "response.json").write_text('{"ok": true}\n', encoding="utf-8")
   220	    (turn_dir / "messages.jsonl").write_text('{"role": "user"}\n', encoding="utf-8")
   221	    (turn_dir / "model_request.json").write_text('{"messages": []}\n', encoding="utf-8")
   222	    (turn_dir / "model_response.json").write_text('{"turns": []}\n', encoding="utf-8")
   223
   224	    output_dir = tmp_path / "out"
   225	    manifest = synthesize_headless_artifacts(
   226	        request={"query": "edit"},
   227	        result=ExecutorResult.success(
   228	            report=Report(
   229	                plan=ClassifyDecision(route="revise", task="edit_graph"),
   230	                implementation=ImplementationResult(message="edited"),
   231	            ),
   232	            reply="edited",
   233	        ),
   234	        response={"ok": True, "detail_json_path": str(turn_dir / "response.json")},
   235	        output_dir=output_dir,
   236	        status="success",
   237	    )
   238
   239	    assert manifest["optional_model_artifacts"] == {
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
   250	def test_malformed_json_artifact_body_is_omitted(tmp_path: Path) -> None:
   251	    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "malformed-json"
   252	    turn_dir.mkdir(parents=True)
   253	    (turn_dir / "response.json").write_text('{"ok": false}\n', encoding="utf-8")
   254	    secret = "sk-malformed-json-secret"
   255	    (turn_dir / "model_request.json").write_text(
   256	        '{"api_key":"' + secret + '"', encoding="utf-8"
   257	    )
   258	    output_dir = tmp_path / "out"
   259
   260	    synthesize_headless_artifacts(
   261	        request={"query": "test"},
   262	        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
   263	        response={"ok": False, "detail_json_path": str(turn_dir / "response.json")},
   264	        output_dir=output_dir,
   265	        status="error",
   266	    )
   267
   268	    assert _read_json(output_dir / "model_request.json") == {
   269	        "redacted_unparseable_artifact": True
   270	    }
   271	    assert secret not in "\n".join(
   272	        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
   273	    )
   274
   275
   276	def test_malformed_jsonl_artifact_body_is_omitted(tmp_path: Path) -> None:
   277	    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "malformed-jsonl"
   278	    turn_dir.mkdir(parents=True)
   279	    (turn_dir / "response.json").write_text('{"ok": false}\n', encoding="utf-8")
   280	    credential = "dXNlcjpwYXNz"
   281	    (turn_dir / "messages.jsonl").write_text(
   282	        '{"role":"user","content":"safe"}\n'
   283	        '{"authorization":"Basic ' + credential + '"\n',
   284	        encoding="utf-8",
   285	    )
   286	    output_dir = tmp_path / "out"
   287
   288	    synthesize_headless_artifacts(
   289	        request={"query": "test"},
   290	        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
   291	        response={"ok": False, "detail_json_path": str(turn_dir / "response.json")},
   292	        output_dir=output_dir,
   293	        status="error",
   294	    )
   295
   296	    assert _read_json(output_dir / "messages.jsonl") == {
   297	        "redacted_unparseable_artifact": True
   298	    }
   299	    persisted = "\n".join(
   300	        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
   301	    )
   302	    assert credential not in persisted
   303	    assert "Basic" not in persisted
   304
   305
   306	def test_model_attempt_artifact_is_canonical_and_redacts_secrets(tmp_path: Path) -> None:
   307	    output_dir = tmp_path / "out"
   308	    result = ExecutorResult.success(
   309	        report=Report(
   310	            model_attempts=(
   311	                {
   312	                    "phase": "classify",
   313	                    "attempt": 1,
   314	                    "outcome": "failure",
   315	                    "failure_type": "malformed_json",
   316	                    "requested_model": "requested-model",
   317	                    "resolved_model": "resolved-model",
   318	                    "adapter": "hermes",
   319	                    "provider": "openrouter",
   320	                    "transport": "openrouter",
   321	                    "endpoint": (
   322	                        "https://user:password@OpenRouter.ai/api/v1/?api_key=sk-secret"
   323	                        "&signature=sig-secret"
   324	                    ),
   325	                    "finish_reason": "stop",
   326	                    "token_usage": {
   327	                        "prompt_tokens": 11,
   328	                        "completion_tokens": 4,
   329	                        "total_tokens": 15,
   330	                    },
   331	                    "raw_response_preview": (
   332	                        "Authorization: Bearer top-secret "
   333	                        "https://example.test/v1?token=url-secret"
   334	                    ),
   335	                },
   336	                {
   337	                    "phase": "reply",
   338	                    "attempt": 1,
   339	                    "outcome": "success",
   340	                    "requested_model": "requested-model",
   341	                    "resolved_model": "resolved-model",
   342	                    "adapter": "codex",
   343	                    "provider": "unknown",
   344	                    "transport": "unknown",
   345	                    "endpoint": "unknown",
   346	                    "finish_reason": "unknown",
   347	                    "token_usage": {},
   348	                    "raw_response_preview": "must never persist on success",
   349	                },
   350	            )
   351	        ),
   352	        reply="ok",
   353	    )
   354
   355	    manifest = synthesize_headless_artifacts(
   356	        request={"query": "test"},
   357	        result=result,
   358	        response={"ok": True},
   359	        output_dir=output_dir,
   360	        status="success",
   361	    )
   362
   363	    assert "model_attempts.json" in manifest["manifest"]
   364	    assert manifest["optional_model_artifacts"]["model_attempts.json"] is True
   365	    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
   366	    assert attempts[0]["endpoint"] == "https://openrouter.ai/api/v1"
   367	    assert "top-secret" not in attempts[0]["raw_response_preview"]
   368	    assert "url-secret" not in attempts[0]["raw_response_preview"]
   369	    assert "raw_response_preview" not in attempts[1]
   370	    assert attempts[1]["provider"] == "unknown"
   371	    persisted = "\n".join(
   372	        path.read_text(encoding="utf-8")
   373	        for path in output_dir.iterdir()
   374	        if path.is_file()
   375	    )
   376	    assert "sk-secret" not in persisted
   377	    assert "sig-secret" not in persisted
   378	    assert "top-secret" not in persisted
   379	    assert "url-secret" not in persisted
   380
   381
   382	def test_turn_artifact_secrets_in_ordinary_fields_are_redacted(tmp_path: Path) -> None:
   383	    """Oracle finding 5: parsed JSON artifacts with secrets in ordinary leaves.
   384
   385	    A durable turn artifact persisting ``Authorization`` headers or
   386	    credential-bearing URLs under ordinary keys (``content``, ``url``,
   387	    ``message``, ``error``) must come out fully redacted.
   388	    """
   389	    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "leaky"
   390	    turn_dir.mkdir(parents=True)
   630	        assert d["graph"] == {"n": 1}
   631	        assert d["message"] == "done"
   632	        assert d["delta"] == [{"op": "add"}]
   633
   634
   635	# ── Report ───────────────────────────────────────────────────────────────────
   636
   637
   638	class TestModelAttemptEvidence:
   639	    def test_preserves_requested_and_resolved_model_and_unknown_non_hermes_fields(self) -> None:
   640	        payload = ModelAttemptEvidence(
   641	            phase="reply",
   642	            attempt=2,
   643	            outcome="success",
   644	            requested_model="profile-alias",
   645	            resolved_model="provider/model-v2",
   646	            adapter="codex",
   647	            provider=None,  # type: ignore[arg-type]
   648	            transport=None,  # type: ignore[arg-type]
   649	            endpoint=None,  # type: ignore[arg-type]
   650	            finish_reason=None,  # type: ignore[arg-type]
   651	            token_usage={},
   652	            raw_response_preview="success content must be dropped",
   653	        ).to_dict()
   654
   655	        assert payload["requested_model"] == "profile-alias"
   656	        assert payload["resolved_model"] == "provider/model-v2"
   657	        assert payload["provider"] == "unknown"
   658	        assert payload["transport"] == "unknown"
   659	        assert payload["endpoint"] == "unknown"
   660	        assert payload["finish_reason"] == "unknown"
   661	        assert payload["token_usage"] == {
   662	            "prompt_tokens": "unknown",
   663	            "completion_tokens": "unknown",
   664	            "total_tokens": "unknown",
   665	        }
   666	        assert "raw_response_preview" not in payload
   667
   668	    @pytest.mark.parametrize("scheme", ["Basic", "Bearer", "ApiKey", "Custom"])
   669	    def test_preview_redacts_entire_authorization_header(self, scheme: str) -> None:
   670	        credential = "dXNlcjpwYXNz"
   671	        preview = redact_model_preview(
   672	            f"request failed\nAuthorization: {scheme} {credential}\nresponse invalid"
   673	        )
   674
   675	        assert preview == "request failed Authorization: <redacted> response invalid"
   676	        assert scheme not in preview
   677	        assert credential not in preview
   678
   679
   680	class TestReport:
   681	    def test_default(self) -> None:
   682	        r = Report()
   683	        assert r.plan is None
   684	        assert r.research is None
   685	        assert r.implementation is None
   686
   687	    def test_with_phases(self) -> None:
   688	        plan = ClassifyDecision(research=True, implement=True)
   689	        research = ResearchResult(summary="found")
   690	        impl = ImplementationResult(message="edited")
   691	        r = Report(plan=plan, research=research, implementation=impl)
   692	        assert r.plan == plan
   693	        assert r.research is research
   694	        assert r.implementation is impl
   695
   696	    def test_to_dict(self) -> None:
   697	        plan = ClassifyDecision(plan_summary="p")
   698	        research = ResearchResult(summary="r")
   699	        r = Report(plan=plan, research=research)
   700	        d = r.to_dict()
   701	        assert d["executor"]["plan"]["plan_summary"] == "p"
   702	        assert d["executor"]["research"]["summary"] == "r"
   703	        assert "implementation" not in d["executor"]
   704
   705	    def test_model_response_compatibility_view_is_derived_not_serialized(self) -> None:
   706	        attempt = ModelAttemptEvidence(
   707	            phase="classify",
   708	            outcome="failure",
   709	            failure_type="malformed_json",
   710	        ).to_dict()
   711	        report = Report(model_attempts=(attempt,))
   712
   713	        assert report.model_response == {"attempts": [attempt]}
   714	        payload = report.to_dict()["executor"]
   715	        assert payload["model_attempts"] == [attempt]
   716	        assert "model_response" not in payload
   717
   718
   719	# ── AgentTurnResult ──────────────────────────────────────────────────────────
   720
   721
   722	class TestAgentTurnResult:
   723	    def test_canonical_envelope_shape(self) -> None:
   724	        result = AgentTurnResult(
   725	            route="revise",
   726	            reply="Updated the graph.",
   727	            evidence=AgentEvidence(
   728	                classification={"route": "revise", "task": "edit_graph"},
   729	                graph_inspection={},
   730	                research={},
   731	                implementation={"message": "done"},
   732	                warnings=(),
   733	            ),
   734	            candidate={"graph": {"nodes": [{"id": 1}]}},
   735	            disposition="edit_graph",
   420	        lambda *args, **kwargs: {
   421	            "error": "ProviderCallError: Error code: 401 - Missing Authentication header",
   422	            "error_type": "ProviderCallError",
   423	        },
   424	    )
   425
   426	    with pytest.raises(PermissionError, match="Missing Authentication header"):
   427	        runtime.run_agent_turn_batch(
   428	            task="make it brighter",
   429	            route="openrouter",
   430	            messages=[{"role": "user", "content": "User request:\nmake it brighter"}],
   431	        )
   432
   433
   434	@pytest.mark.parametrize(
   435	    ("exc", "raw", "expected"),
   436	    [
   437	        (ValueError("empty"), "", "empty_response"),
   438	        (json.JSONDecodeError("bad", "{bad", 1), "{bad", "malformed_json"),
   439	        (json.JSONDecodeError("bad", "plain prose", 0), "plain prose", "non_json_content"),
   440	        (ValueError("must include field reply"), '{"other":"x"}', "missing_required_fields"),
   441	        (TimeoutError("late"), None, "timeout"),
   442	        (RuntimeError("capacity"), None, "provider_failure"),
   443	    ],
   444	)
   445	def test_worker_failure_taxonomy_is_structural(
   446	    exc: BaseException,
   447	    raw: str | None,
   448	    expected: str,
   449	) -> None:
   450	    assert worker._model_attempt_failure_type(exc, raw) == expected
   451
   452
   453	def test_worker_zero_filled_usage_without_calls_is_unavailable() -> None:
   454	    request = {
   455	        "agent_id": "hermes",
   456	        "requested_model": "requested",
   457	        "model": "resolved",
   458	        "agent_kwargs": {
   459	            "model": "resolved",
   460	            "base_url": "https://openrouter.ai/api/v1",
   461	        },
   462	    }
   463	    zero_usage = {
   464	        "deepseek_usage": {
   465	            "n_calls": 0,
   466	            "prompt_tokens": 0,
   467	            "completion_tokens": 0,
   468	            "total_tokens": 0,
   469	        }
   470	    }
   471
   472	    unavailable = worker._model_attempt(
   473	        request,
   474	        {"backend_phase": "classify"},
   475	        zero_usage,
   476	        outcome="failure",
   477	        failure_type="empty_response",
   478	    )
   479	    observed = worker._model_attempt(
   480	        request,
   481	        {"backend_phase": "classify"},
   482	        {"deepseek_usage": {**zero_usage["deepseek_usage"], "n_calls": 1}},
   483	        outcome="failure",
   484	        failure_type="empty_response",
   485	    )
   486
   487	    assert unavailable["token_usage"]["completion_tokens"] == "unknown"
   488	    assert observed["token_usage"]["completion_tokens"] == 0
   489
   490
   491	def _canonical_success_attempt() -> dict:
   492	    return {
   493	        "phase": "batch",
   494	        "attempt": 1,
   495	        "outcome": "success",
   496	        "failure_type": None,
   497	        "requested_model": "openrouter:requested/model",
   498	        "resolved_model": "resolved/model",
   499	        "adapter": "hermes",
   500	        "provider": "openrouter",
   501	        "transport": "openrouter",
   502	        "endpoint": "https://openrouter.ai/api/v1",
   503	        "finish_reason": "stop",
   504	        "token_usage": {
   505	            "prompt_tokens": 12,
   506	            "completion_tokens": 3,
   507	            "total_tokens": 15,
   508	        },
   509	    }
   510
   511
   512	def test_three_runtime_success_paths_preserve_worker_attempt_provenance(
   513	    monkeypatch: pytest.MonkeyPatch,
   514	) -> None:
   515	    monkeypatch.setattr(runtime, "_hermes_credential_for", lambda route, model: "key")
   516	    attempt = _canonical_success_attempt()
   517
   518	    def fake_worker(*args, response_contract, **kwargs):  # noqa: ANN001, ANN202, ARG001
   519	        base = {"model_attempts": [attempt], "deepseek_usage": attempt["token_usage"]}
   520	        if response_contract == "python":
   521	            return {**base, "python": "pass", "message": "ok"}
   522	        if response_contract == "delta":
   523	            return {**base, "delta": [], "message": "ok"}
   524	        return {**base, "content": "done\n```batch\ndone()\n```"}
   525
   526	    monkeypatch.setattr(runtime, "_run_worker", fake_worker)
   527
   528	    python_result = runtime.run_agent_turn(
   529	        task="x", python_source="", route="openrouter", model="requested/model"
   530	    )
   531	    delta_result = runtime.run_agent_turn_delta(
   532	        task="x", projection="{}", op_schema={}, route="openrouter", model="requested/model"
   533	    )
   534	    batch_result = runtime.run_agent_turn_batch(
   535	        task="x", route="openrouter", model="requested/model", messages=[]
   536	    )
   537
   538	    for result in (python_result, delta_result, batch_result):
   539	        assert result["model_attempts"] == [attempt]
   540	        assert result["deepseek_usage"] == attempt["token_usage"]
   541
   542
   543	def test_batch_provider_audit_merges_worker_attempt_provenance() -> None:
   544	    attempt = _canonical_success_attempt()
   545	    result = agent_provider._normalize_batch_response(
   546	        {
   547	            "content": "Changed it.\n```batch\ndone()\n```",
   548	            "model_attempts": [attempt],
   549	            "deepseek_usage": attempt["token_usage"],
   550	        },
   551	        route="openrouter",
   552	        model="requested/model",
   553	        audit_metadata={"provider": "arnold"},
   554	    )
   555
   556	    assert result.audit_metadata["model_attempts"] == [attempt]
   557	    assert result.audit_metadata["deepseek_usage"] == attempt["token_usage"]
   558
   559
   560	def test_batch_provider_retry_renumbers_all_worker_attempts_monotonically(
   561	    monkeypatch: pytest.MonkeyPatch,
   562	) -> None:
   563	    calls = 0
   564	    first_a = {**_canonical_success_attempt(), "outcome": "failure", "failure_type": "provider_failure"}
   565	    first_b = {
   566	        **_canonical_success_attempt(),
   567	        "attempt": 2,
   568	        "token_usage": {
   569	            "prompt_tokens": 8,
   570	            "completion_tokens": 0,
   571	            "total_tokens": 8,
   572	        },
   573	    }
   574	    second = _canonical_success_attempt()
   575
   576	    class Runtime:
   577	        @staticmethod
   578	        def run_agent_turn_batch(**kwargs):  # noqa: ANN003, ANN205, ARG004
   579	            nonlocal calls
   580	            calls += 1
   581	            if calls == 1:
   582	                return {"content": "", "model_attempts": [first_a, first_b]}
   583	            return {
   584	                "content": "done\n```batch\ndone()\n```",
   585	                "model_attempts": [second],
   586	            }
   587
   588	    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)
   589
   590	    result = agent_provider.run_agent_turn_batch(
   591	        "edit it",
   592	        [{"role": "user", "content": "edit it"}],
   593	        route="openrouter",
   594	        model="requested/model",
   595	    )
   596
   597	    attempts = result.audit_metadata["model_attempts"]
   598	    assert calls == 2
   599	    assert [attempt["attempt"] for attempt in attempts] == [1, 2, 3]
   600	    assert attempts[1]["failure_type"] == "empty_response"
   601
   602
   603	def test_successful_classify_and_reply_attempts_reach_executor_capture(
   604	    monkeypatch: pytest.MonkeyPatch,
   605	) -> None:
   606	    calls = 0
   607
   608	    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
   609	        nonlocal calls
   610	        calls += 1
   611	        phase = "classify" if calls == 1 else "reply"
   612	        content = (
   613	            '{"research":false,"implement":false,"reply":true,"route":"respond"}'
   614	            if phase == "classify"
   615	            else '{"reply":"hello"}'
   616	        )
   617	        attempt = {**_canonical_success_attempt(), "phase": phase}
   618	        return {"content": content, "json": json.loads(content), "model_attempts": [attempt]}
   619
   620	    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)
   621	    token = runtime.begin_model_attempt_capture()
   622	    try:
   623	        decision = run_classify_turn("hello", route="openrouter", model="requested/model")
   624	        assert run_reply_turn(
   625	            "hello",
   626	            route="openrouter",
   627	            model="requested/model",
   628	            plan=decision,
   629	        ) == "hello"
   630	        attempts = runtime.snapshot_model_attempt_capture()
   631	    finally:
   632	        runtime.end_model_attempt_capture(token)
   633
   634	    assert [item["phase"] for item in attempts] == ["classify", "reply"]
   635	    assert all(item["outcome"] == "success" for item in attempts)
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
   167	def test_typed_empty_without_observed_usage_is_not_retried(
   168	    monkeypatch: pytest.MonkeyPatch,
   169	) -> None:
   170	    unavailable = _attempt(
   171	        outcome="failure", failure_type="empty_response", completion_tokens=0
   172	    )
   173	    unavailable["token_usage"] = {}
   174	    first = {"error": "empty", "model_attempts": [unavailable]}
   175	    calls = _stub_once(monkeypatch, [first, {"content": "should not run"}])
   176
   177	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   178
   179	    assert result["model_attempts"][0]["token_usage"]["completion_tokens"] == "unknown"
   180	    assert len(calls) == 1
   181
   182
   183	@pytest.mark.parametrize(
   184	    "error_type",
   185	    ["ValueError", "JSONDecodeError", "AuthError", "AuthenticationError", "PermissionError"],
   186	)
   187	def test_non_transient_worker_error_is_not_retried(
   188	    monkeypatch: pytest.MonkeyPatch, error_type: str
   189	) -> None:
   190	    """Content/auth errors are owned by other layers and must not burn retry slots."""
   191	    non_transient = {"error": "boom", "error_type": error_type}
   192	    calls = _stub_once(monkeypatch, [non_transient])
   193
   194	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   195
   196	    assert result == non_transient
   197	    assert len(calls) == 1
   198
   199
   200	def test_runtime_unavailable_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
   201	    """Setup faults (missing backend / unregistered adapter) won't recover."""
   202	    unavailable = {
   203	        "error": "no adapter",
   204	        "error_type": "LookupError",
   205	        "runtime_unavailable": True,
   206	    }
   207	    calls = _stub_once(monkeypatch, [unavailable])
   208
   209	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   210
   211	    assert result == unavailable
   212	    assert len(calls) == 1
   213
   214
   215	def test_success_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
   216	    good = {"content": "ok", "_profiling": {}}
   217	    calls = _stub_once(monkeypatch, [good])
   218
   219	    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())
   220

exec
/bin/zsh -lc "nl -ba tests/test_headless_agent_artifacts.py | sed -n '382,475p'; nl -ba tests/test_live_agentic_runner_persistence.py | sed -n '130,360p'; nl -ba tests/test_live_agentic_runner_persistence.py | sed -n '440,510p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   382	def test_turn_artifact_secrets_in_ordinary_fields_are_redacted(tmp_path: Path) -> None:
   383	    """Oracle finding 5: parsed JSON artifacts with secrets in ordinary leaves.
   384
   385	    A durable turn artifact persisting ``Authorization`` headers or
   386	    credential-bearing URLs under ordinary keys (``content``, ``url``,
   387	    ``message``, ``error``) must come out fully redacted.
   388	    """
   389	    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "leaky"
   390	    turn_dir.mkdir(parents=True)
   391	    (turn_dir / "response.json").write_text('{"ok": false}\n', encoding="utf-8")
   392	    (turn_dir / "request.json").write_text(
   393	        json.dumps(
   394	            {
   395	                "content": "Authorization: Basic dXNlcjpwYXNz",
   396	                "url": "https://example.test/v1?token=url-secret&sig=abc123",
   397	                "message": "retry with Authorization: Bearer eyJhbGciOiJIUzI1NiJ9",
   398	                "error": "call https://api.example.test/v2?api_key=sk-live-123",
   399	                "safe": "plain text without secrets",
   400	            }
   401	        ),
   402	        encoding="utf-8",
   403	    )
   404
   405	    output_dir = tmp_path / "out"
   406	    synthesize_headless_artifacts(
   407	        request={"query": "test"},
   408	        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
   409	        response={"ok": False, "detail_json_path": str(turn_dir / "response.json")},
   410	        output_dir=output_dir,
   411	        status="error",
   412	    )
   413
   414	    copied = _read_json(output_dir / "request.json")
   415	    assert copied["content"] == "Authorization: <redacted>"
   416	    assert copied["url"] == "https://example.test/v1?token=<redacted>&sig=<redacted>"
   417	    assert copied["message"] == "retry with Authorization: <redacted>"
   418	    assert copied["error"] == "call https://api.example.test/v2?api_key=<redacted>"
   419	    assert copied["safe"] == "plain text without secrets"
   420	    persisted = "\n".join(
   421	        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
   422	    )
   423	    assert "dXNlcjpwYXNz" not in persisted
   424	    assert "url-secret" not in persisted
   425	    assert "abc123" not in persisted
   426	    assert "eyJhbGciOiJIUzI1NiJ9" not in persisted
   427	    assert "sk-live-123" not in persisted
   428
   429
   430	def test_synthesized_response_secrets_in_ordinary_fields_are_redacted(tmp_path: Path) -> None:
   431	    """Oracle finding 5: synthesized response with secrets in ordinary leaves.
   432
   433	    The response/request payloads synthesized by ``synthesize_headless_artifacts``
   434	    must redact authorization headers and credential-bearing URLs even when they
   435	    arrive under ordinary ``content``/``url``/``error`` fields.
   436	    """
   437	    output_dir = tmp_path / "out"
   438	    synthesize_headless_artifacts(
   439	        request={"query": "test", "url": "https://api.example.test/v1?apikey=req-secret"},
   440	        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
   441	        response={
   442	            "ok": False,
   443	            "reply": "auth failed",
   444	            "content": (
   445	                "see https://api.example.test/v1?token=url-secret "
   446	                "then Authorization: Bearer live-token"
   447	            ),
   448	            "error": "Authorization: ApiKey live-abcdef",
   449	        },
   450	        output_dir=output_dir,
   451	        status="error",
   452	    )
   453
   454	    response_json = _read_json(output_dir / "response.json")
   455	    assert response_json["reply"] == "auth failed"
   456	    assert response_json["content"] == (
   457	        "see https://api.example.test/v1?token=<redacted> then Authorization: <redacted>"
   458	    )
   459	    assert response_json["error"] == "Authorization: <redacted>"
   460	    request_json = _read_json(output_dir / "request.json")
   461	    assert request_json["url"] == "https://api.example.test/v1?apikey=<redacted>"
   462	    persisted = "\n".join(
   463	        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
   464	    )
   465	    assert "req-secret" not in persisted
   466	    assert "url-secret" not in persisted
   467	    assert "live-token" not in persisted
   468	    assert "live-abcdef" not in persisted
   130	    assert scenario["attempt_count"] == 1
   131	    assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
   132	    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
   133	    assert scenario["attempts"][0]["retryable_infra"] is False
   134	    assert scenario["attempts"][0]["agent_exercised"] is False
   135	    assert scenario["attempts"][0]["elapsed_s"] is not None
   136	    assert (
   137	        tmp_path / "out" / "tag" / "retry-me" / "agentic_summary.json"
   138	    ).exists()
   139
   140
   141	def test_runner_types_provider_capacity_without_retry(
   142	    tmp_path: Path,
   143	    monkeypatch,
   144	) -> None:  # noqa: ANN001
   145	    scenarios_dir = tmp_path / "scenarios"
   146	    scenarios_dir.mkdir()
   147	    scenario_path = scenarios_dir / "provider-capacity.json"
   148	    scenario_path.write_text(
   149	        json.dumps({"id": "provider-capacity", "query": "do it"}),
   150	        encoding="utf-8",
   151	    )
   152
   153	    calls = 0
   154
   155	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   156	        nonlocal calls
   157	        calls += 1
   158	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   159	        tag = cmd[cmd.index("--tag") + 1]
   160	        output_dir = tmp_path / "out" / tag / "provider-capacity"
   161	        if calls == 1:
   162	            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
   163	            payload.update(
   164	                {
   165	                    "status": "executor_failure",
   166	                    "error": (
   167	                        "OpenRouter rejected the request because the account does "
   168	                        "not have enough credits for the requested token budget."
   169	                    ),
   170	                    "output_dir": str(output_dir),
   171	                    "model_attempts": [_failed_attempt("provider_failure")],
   172	                    "guard": {
   173	                        "live_agentic_success": False,
   174	                        "score_class": "product_fail",
   175	                        "assessment": {
   176	                            "passed": False,
   177	                            "issues": [
   178	                                {
   179	                                    "check": "response_ok",
   180	                                    "severity": "error",
   181	                                    "detail": (
   182	                                        "response.ok is False: OpenRouter rejected "
   183	                                        "the request because the account does not "
   184	                                        "have enough credits for the requested token budget."
   185	                                    ),
   186	                                }
   187	                            ],
   188	                        },
   189	                    },
   190	                }
   191	            )
   192	        else:
   193	            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
   194	            payload["output_dir"] = str(output_dir)
   195	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   196	        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
   197
   198	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   199
   200	    summary = run_tag(
   201	        "tag",
   202	        scenarios_dir=scenarios_dir,
   203	        output_base=tmp_path / "out",
   204	        max_workers=1,
   205	        per_scenario_timeout=1,
   206	        infra_retries=1,
   207	        progress_every=0,
   208	    )
   209
   210	    scenario = summary["scenarios"][0]
   211	    assert calls == 1
   212	    assert summary["passed"] == 0
   213	    assert summary["raw_first_attempt_passed"] == 0
   214	    assert scenario["attempt_count"] == 1
   215	    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
   216	    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
   217	    assert scenario["attempts"][0]["retryable_infra"] is False
   218
   219
   220	def test_runner_retries_only_typed_empty_zero_token_attempt(
   221	    tmp_path: Path,
   222	    monkeypatch,
   223	) -> None:  # noqa: ANN001
   224	    scenarios_dir = tmp_path / "scenarios"
   225	    scenarios_dir.mkdir()
   226	    scenario_path = scenarios_dir / "typed-empty.json"
   227	    scenario_path.write_text(json.dumps({"id": "typed-empty", "query": "do it"}), encoding="utf-8")
   228	    calls = 0
   229
   230	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   231	        nonlocal calls
   232	        calls += 1
   233	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   234	        tag = cmd[cmd.index("--tag") + 1]
   235	        payload = _summary(tmp_path / "out" / tag, "typed-empty", ok=calls > 1)
   236	        payload["output_dir"] = str(tmp_path / "out" / tag / "typed-empty")
   237	        if calls == 1:
   238	            payload["error"] = "arbitrary wording that must not drive classification"
   239	            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
   240	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   241	        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
   242
   243	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   244
   245	    summary = run_tag(
   246	        "tag",
   247	        scenarios_dir=scenarios_dir,
   248	        output_base=tmp_path / "out",
   249	        max_workers=1,
   250	        infra_retries=1,
   251	        progress_every=0,
   252	    )
   253
   254	    scenario = summary["scenarios"][0]
   255	    assert calls == 2
   256	    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
   257	    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
   258	    assert scenario["attempts"][1]["live_agentic_success"] is True
   259
   260
   261	def test_runner_keeps_malformed_nonempty_as_product_failure(
   262	    tmp_path: Path,
   263	    monkeypatch,
   264	) -> None:  # noqa: ANN001
   265	    scenarios_dir = tmp_path / "scenarios"
   266	    scenarios_dir.mkdir()
   267	    scenario_path = scenarios_dir / "malformed.json"
   268	    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
   269	    calls = 0
   270
   271	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   272	        nonlocal calls
   273	        calls += 1
   274	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   275	        tag = cmd[cmd.index("--tag") + 1]
   276	        payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
   277	        payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
   278	        payload["error"] = "OpenRouter rejected / HTTP 429 wording is irrelevant"
   279	        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
   280	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   281	        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
   282
   283	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   284
   285	    summary = run_tag(
   286	        "tag",
   287	        scenarios_dir=scenarios_dir,
   288	        output_base=tmp_path / "out",
   289	        max_workers=1,
   290	        infra_retries=1,
   291	        progress_every=0,
   292	    )
   293
   294	    scenario = summary["scenarios"][0]
   295	    assert calls == 1
   296	    assert scenario["score_class"] == "product_fail"
   297	    assert scenario.get("retryable_infra") is not True
   298
   299
   300	def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
   301	    tmp_path: Path,
   302	    monkeypatch,
   303	) -> None:  # noqa: ANN001
   304	    scenarios_dir = tmp_path / "scenarios"
   305	    scenarios_dir.mkdir()
   306	    scenario_path = scenarios_dir / "provider-down.json"
   307	    scenario_path.write_text(json.dumps({"id": "provider-down", "query": "do it"}), encoding="utf-8")
   308
   309	    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
   310	        out_file = Path(cmd[cmd.index("--single-out") + 1])
   311	        tag = cmd[cmd.index("--tag") + 1]
   312	        output_dir = tmp_path / "out" / tag / "provider-down"
   313	        payload = _summary(tmp_path / "out" / tag, "provider-down", ok=False)
   314	        payload.update(
   315	            {
   316	                "status": "executor_failure",
   317	                "error": "HTTP Error 429: Too Many Requests",
   318	                "output_dir": str(output_dir),
   319	                "model_attempts": [_failed_attempt("provider_failure")],
   320	                "guard": {
   321	                    "live_agentic_success": False,
   322	                    "score_class": "product_fail",
   323	                    "assessment": {"passed": False, "issues": []},
   324	                },
   325	            }
   326	        )
   327	        out_file.write_text(json.dumps(payload), encoding="utf-8")
   328	        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
   329
   330	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   331
   332	    summary = run_tag(
   333	        "tag",
   334	        scenarios_dir=scenarios_dir,
   335	        output_base=tmp_path / "out",
   336	        max_workers=1,
   337	        per_scenario_timeout=1,
   338	        infra_retries=1,
   339	        progress_every=0,
   340	    )
   341
   342	    scenario = summary["scenarios"][0]
   343	    assert scenario["attempt_count"] == 1
   344	    assert scenario["failure_class"] == "infra_provider_capacity"
   345	    assert scenario["score_class"] == "infra_blocked"
   346	    assert summary["passed"] == 0
   347	    assert summary["infra_failures"] == 1
   348	    assert summary["product_or_assessment_failures"] == 0
   349	    assert summary["score_classes"] == {"infra_blocked": 1}
   350
   351
   352	def test_runner_does_not_classify_soft_search_429_as_infra(
   353	    tmp_path: Path,
   354	    monkeypatch,
   355	) -> None:  # noqa: ANN001
   356	    scenarios_dir = tmp_path / "scenarios"
   357	    scenarios_dir.mkdir()
   358	    scenario_path = scenarios_dir / "soft-search-warning.json"
   359	    scenario_path.write_text(
   360	        json.dumps({"id": "soft-search-warning", "query": "do it"}),
   440	    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)
   441
   442	    summary = run_tag(
   443	        "tag",
   444	        scenarios_dir=scenarios_dir,
   445	        output_base=tmp_path / "out",
   446	        max_workers=1,
   447	        per_scenario_timeout=1,
   448	        infra_retries=0,
   449	        progress_every=0,
   450	    )
   451
   452	    scenario = summary["scenarios"][0]
   453	    assert scenario["guard"]["assessment"]["expect_graph_changed"] is False
   454	    assert scenario["failure_class"] == "infra_timeout"
   455	    assert summary["infra_failures"] == 1
   456
   457
   458	def test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed() -> None:
   459	    """Oracle finding 4: persisted failure_class/retryable_infra must never drive retry.
   460
   461	    Canonical ``malformed_json`` evidence with zero tokens is NOT retryable even
   462	    when the summary inherited ``failure_class=infra_empty_response`` and
   463	    ``retryable_infra=True`` from an earlier attempt.
   464	    """
   465	    summary = _summary(Path("/tmp"), "conflicting-flags", ok=False)
   466	    summary["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=0)]
   467	    summary["failure_class"] = "infra_empty_response"
   468	    summary["retryable_infra"] = True
   469	    summary["score_class"] = "infra_blocked"
   470	    summary["guard"]["failure_class"] = "infra_empty_response"
   471	    summary["guard"]["score_class"] = "infra_blocked"
   472
   473	    assert _provider_infra_failure_class(summary) is None
   474	    assert _is_retryable_infra_summary(summary) is False
   475	    # The inherited markers were cleared, never trusted.
   476	    assert summary.get("failure_class") is None
   477	    assert summary.get("retryable_infra") is False
   478	    assert summary.get("score_class") is None
   479	    assert summary["guard"].get("failure_class") is None
   480	    assert summary["guard"].get("score_class") is None
   481
   482
   483	def test_retryability_is_derived_from_canonical_typed_evidence() -> None:
   484	    """Canonical empty_response + observed zero tokens is retryable regardless of flags."""
   485	    summary = _summary(Path("/tmp"), "canonical-empty", ok=False)
   486	    summary["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
   487	    summary["failure_class"] = "product_or_assessment_failure"  # stale conflicting flag
   488	    summary["retryable_infra"] = False  # stale conflicting flag
   489
   490	    assert _provider_infra_failure_class(summary) == "infra_empty_response"
   491	    assert _is_retryable_infra_summary(summary) is True
   492	    assert summary["failure_class"] == "infra_empty_response"
   493	    assert summary["retryable_infra"] is True

exec
/bin/zsh -lc "rg -n \"class .*Attempt|TypedDict.*Attempt|MODEL_ATTEMPT_FAILURE_TYPES|raw_response_preview.*requested_model|requested_model.*resolved_model\" vibecomfy tests/live_agentic_harness --glob '*.py'; rg -n '\"phase\".*\"attempt\".*\"outcome\"|\"failure_type\".*\"requested_model\"' vibecomfy tests/live_agentic_harness --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 110ms:
vibecomfy/executor/contracts.py:36:MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
vibecomfy/executor/contracts.py:129:class ModelAttemptEvidence:
vibecomfy/executor/contracts.py:156:        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
vibecomfy/executor/contracts.py:163:            "requested_model", "resolved_model", "adapter", "provider",

codex
The structural trace is coherent so far: there is one canonical `ModelAttemptEvidence` definition, and classify/reply/batch all feed the same `model_attempts` sequence. I’m now pressure-testing the two likeliest failure points—retry gating under conflicting/stale flags and artifact redaction of secrets embedded in ordinary strings—then I’ll run the full focused suite.
exec
/bin/zsh -lc "git diff --check 45415680..1bd1b04b; git diff --numstat 45415680..1bd1b04b; git log -1 --format='%H%n%P%n%s' 1bd1b04b; git branch --show-current" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 142ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
38	0	.oracle/briefs/batch-B01-rework.md
26	0	.oracle/briefs/batch-B01-rework2.md
39	0	.oracle/briefs/batch-B01.md
7062	0	.oracle/checkins/batch-B01.md
1	0	tests/live_agentic_harness/adapter.py
73	58	tests/live_agentic_harness/runner.py
237	0	tests/test_agent_runtime_adapter.py
57	0	tests/test_executor_contracts.py
40	0	tests/test_executor_flows.py
223	0	tests/test_headless_agent_artifacts.py
154	11	tests/test_live_agentic_runner_persistence.py
106	28	tests/test_runtime_worker_retry.py
127	6	vibecomfy/agent/artifacts.py
119	16	vibecomfy/comfy_nodes/agent/provider.py
187	119	vibecomfy/comfy_nodes/agent/runtime.py
106	26	vibecomfy/comfy_nodes/agent/worker.py
62	9	vibecomfy/executor/agent_backend.py
221	13	vibecomfy/executor/contracts.py
41	133	vibecomfy/executor/core.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
1bd1b04bae9997b1af9ab1e49c19dae9a89c125e
a8d4974aa4bc8e532809a3c3ceb4e273943b9313
megado B01 rework2: harness retry derived from canonical typed evidence (conflicting-flags regression); artifact sanitization covers every string leaf incl. ordinary content/url fields — 35 focused tests green
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
oracle-run

exec
/bin/zsh -lc "rg --files tests | rg 'classify_only|executor_contracts|executor_flows|agent_runtime_adapter|headless_agent_artifacts|live_agentic_runner_persistence|runtime_worker_retry'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
tests/test_runtime_worker_retry.py
tests/test_live_agentic_runner_persistence.py
tests/test_agent_runtime_adapter.py
tests/test_executor_contracts.py
tests/test_executor_classify_only.py
tests/test_headless_agent_artifacts.py
tests/test_executor_flows.py

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:rerunfailures -p no:cacheprovider tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 2349ms:
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
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']

codex
The full pytest invocation is blocked before collection because this oracle sandbox has no writable temporary directory (even `/tmp` is unavailable). I’ll still run the pure, no-temp contract/retry cases that pytest can execute with capture disabled, and I’ll treat the orchestrator’s completed 556-pass run as supporting—not substitute—evidence.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:rerunfailures -p no:cacheprovider tests/test_executor_contracts.py::TestModelAttemptEvidence tests/test_executor_contracts.py::TestReport::test_model_response_compatibility_view_is_derived_not_serialized tests/test_agent_runtime_adapter.py::test_worker_failure_taxonomy_is_structural tests/test_agent_runtime_adapter.py::test_worker_zero_filled_usage_without_calls_is_unavailable tests/test_agent_runtime_adapter.py::test_three_runtime_success_paths_preserve_worker_attempt_provenance tests/test_agent_runtime_adapter.py::test_batch_provider_audit_merges_worker_attempt_provenance tests/test_agent_runtime_adapter.py::test_batch_provider_retry_renumbers_all_worker_attempts_monotonically tests/test_agent_runtime_adapter.py::test_successful_classify_and_reply_attempts_reach_executor_capture tests/test_runtime_worker_retry.py tests/test_live_agentic_runner_persistence.py::test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed tests/test_live_agentic_runner_persistence.py::test_retryability_is_derived_from_canonical_typed_evidence' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 15080ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
.................................
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
33 passed, 1 warning in 7.11s

exec
/bin/zsh -lc 'rg -n "B01 CHECKPOINT VERDICT|''^Issue|''^Issues|finding [1-8]|FAIL|PASS" .oracle/checkins/batch-B01.md | tail -120; sed -n '"'1,140p' .oracle/briefs/batch-B01-rework.md; sed -n '1,140p' .oracle/briefs/batch-B01-rework2.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 72ms:
23:**B01 [HARD] — Typed failures and unified attempt provenance.** Tasks + acceptance from `.oracle/tasklist.md` (B01 section). The diff to review: `git diff 45415680..1bd1b04b` (G0R PASS SHA → B01 commit). The executor was GPT-5.6 Sol (workspace-write, 30-min clamp hit mid-verification; the orchestrator ran the focused suite to completion).
45:First line: `B01 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
46:Then per-focus findings (1–8) with evidence, and an issue list if FAIL (each with file:line + what to rework). Be adversarial but fair.
162:**2. Checkpoint — oracle review.** The check-in brief carries the batch's tasks + acceptance criteria, the delta since the last checkpoint, and the delegation mandate. The oracle dispatches verification, research, and critique passes to Flash where useful — critiques biased toward elegance (KISS, YAGNI, cut scope that isn't pulling its weight) — then judges the results. Verdict is binary: `PASS` or a list of issues.
230:  • Synthesize adversarial PASS/FAIL verdict with file:line evidence
275:53-Review scorer/narrator changes and focused fixtures. Record `PASS` as the formal G0 verdict, plus either a reconciled historical rescore or an explicit “source artifacts unavailable” statement.
614:tests/live_agentic_harness/runner.py:266:    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
723:vibecomfy/executor/contracts.py:156:        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
1222:vibecomfy/comfy_nodes/agent/diagnostics.py:270:            "failure_kind": FailureKind.LOWERING_FAILURE.value,
1324:vibecomfy/comfy_nodes/agent/contracts.py:1534:            spec = FAILURE_SPECS[FailureKind(failure_kind)]
1329:vibecomfy/comfy_nodes/agent/contracts.py:2409:    spec = FAILURE_SPECS[failure_kind]
1830:    36	MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
1950:   156	        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
2347:+MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
2467:+        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
7749:   266	    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
8011:-_PARSE_FAILURE_PATTERN = re.compile(r"The model response could not be parsed", re.IGNORECASE)
8155:-    if _PARSE_FAILURE_PATTERN.search(text):
8209:+    when the typed evidence is now, say, ``malformed_json`` (oracle finding 4).
8599:    94	    byte (oracle finding 5).
8932:   383	    """Oracle finding 5: parsed JSON artifacts with secrets in ordinary leaves.
9487:   383	    """Oracle finding 5: parsed JSON artifacts with secrets in ordinary leaves.
9535:   431	    """Oracle finding 5: synthesized response with secrets in ordinary leaves.
9823:   459	    """Oracle finding 4: persisted failure_class/retryable_infra must never drive retry.
9860:/bin/zsh -lc "rg -n \"class .*Attempt|TypedDict.*Attempt|MODEL_ATTEMPT_FAILURE_TYPES|raw_response_preview.*requested_model|requested_model.*resolved_model\" vibecomfy tests/live_agentic_harness --glob '*.py'; rg -n '\"phase\".*\"attempt\".*\"outcome\"|\"failure_type\".*\"requested_model\"' vibecomfy tests/live_agentic_harness --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
9862:vibecomfy/executor/contracts.py:36:MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
9864:vibecomfy/executor/contracts.py:156:        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
10005:/bin/zsh -lc 'rg -n "B01 CHECKPOINT VERDICT|''^Issue|''^Issues|finding [1-8]|FAIL|PASS" .oracle/checkins/batch-B01.md | tail -120; sed -n '"'1,140p' .oracle/briefs/batch-B01-rework.md; sed -n '1,140p' .oracle/briefs/batch-B01-rework2.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
# MEGADO B01 REWORK (oracle issues 1–6) — [HARD], executor: GPT-5.6 Sol, workspace-write

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). You MAY modify files and run tests. Skip formatters/linters/full suites; run focused tests only. The B01 implementation from `e33f0260` is already in the tree — fix the oracle issues on top of it, do not revert.

## Oracle issues (from `.oracle/checkins/batch-B01.md`, all lines vs `e33f0260`)

### 1. Parallel evidence format must go
`vibecomfy/executor/contracts.py:122-209` defines the canonical `ModelAttemptEvidence`; `coerce_model_attempts` at `:212-222` normalizes. But `Report` still exposes BOTH canonical `model_attempts` AND legacy `model_response` (`:2302-2309`, serialized `:2354-2358`), and `vibecomfy/executor/core.py:105-128,223-238` retains a second parse-evidence vocabulary that can emit legacy `{"turns":[{"error":...}]}`.
Fix: migrate/remove the legacy `model_response` parallel evidence — one canonical persisted format. Keep any field needed for back-compat in the report but derive it FROM `model_attempts`; no second vocabulary in core.

### 2. Truthful attempt numbers across provider-level batch retries
`vibecomfy/comfy_nodes/agent/provider.py:1492-1505`: batch retries append worker-local attempts without renumbering → `[attempt=1, attempt=1]` after a retry instead of `[1,2]`.
Fix: assign monotonically increasing attempt numbers across the full retry sequence (renumber on append or carry a running counter).

### 3. Observed zero tokens vs zero-filled unavailable usage
`vibecomfy/comfy_nodes/agent/worker.py:156-163` accepts zero-filled usage even when `n_calls == 0`; `_dispatch_turn` supplies that normalized zero usage → unobserved usage appears as `completion_tokens=0` and authorizes retry.
Fix: distinguish OBSERVED zero tokens (call returned, usage reported 0) from UNAVAILABLE usage (no usage observed — `n_calls==0` or usage absent). Only observed zero tokens may authorize the fresh-transport retry; unavailable usage must not.

### 4. Redaction: complete Authorization header values
`vibecomfy/executor/contracts.py:47-50,84-97` turns `Authorization: Basic dXNlcjpwYXNz` into `Authorization: <redacted> dXNlcjpwYXNz` — the credential survives after the marker.
Fix: redact the ENTIRE header value for every scheme (Basic, Bearer, ApiKey, custom): `Authorization: <redacted>`. Add a Basic-auth negative fixture.

### 5. Never raw-copy parse-failed artifacts
`vibecomfy/agent/artifacts.py:102-116` raw-copies an entire JSON/JSONL artifact after any parse error — malformed artifacts containing secrets persist verbatim.
Fix: on parse failure, do NOT raw-copy; sanitize (run the same redaction) or omit the body entirely (keep a bounded note). Add malformed-JSON and malformed-JSONL regressions proving secrets cannot persist.

### 6. Unsupported-route provenance must be `unknown`, never inferred
`vibecomfy/comfy_nodes/agent/provider.py:901-905` preserves arbitrary routes; `runtime.py:321-333` silently maps any unmapped route to Hermes; `:472-486` assigns OpenRouter provenance; unsupported non-Hermes paths get an inferred `_ARNOLD_MODEL` at `runtime.py:350-370`.
Fix: serialize unsupported-route provenance as explicit `unknown` with NO fallback inference — no silent Hermes mapping, no OpenRouter assignment, no `_ARNOLD_MODEL` inference. Add a route-plumbing regression exercising an unsupported route end to end (not just a manually constructed contract).

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```
Expected exit 0 (the rerunfailures plugin binds a socket and cannot run here — disable it). Add fixtures for each fix above so the suite covers them.

## Report
Return: per-issue changes (files + line refs), fixture names added, pytest output. Do NOT commit.
# MEGADO B01 REWORK 2 (oracle issues 4+5) — Flash executor

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B01 is in the tree at `a8d4974a` — fix on top, do not revert.

## Issue A — harness retry trusts stale flags (oracle finding 4)

`tests/live_agentic_harness/runner.py:266`: after typed classification returns no match, the runner still trusts preexisting `failure_class == "infra_empty_response"` and `retryable_infra is True` persisted flags. A summary with those flags PLUS canonical `malformed_json` evidence with zero tokens returns retryable — reproduced: `_provider_infra_failure_class(summary) -> None` but `_is_retryable_infra_summary(summary) -> True`.

Fix: derive retryability directly from the CANONICAL typed evidence (`model_attempts` failure type + observed completion tokens) on EVERY decision; never trust inherited `failure_class`/`retryable_infra` flags. Add a conflicting-flags regression: persisted `failure_class=infra_empty_response` + `retryable_infra=True` but canonical evidence `malformed_json` → NOT retryable.

## Issue B — artifact sanitization misses ordinary string leaves (oracle finding 5)

`vibecomfy/agent/artifacts.py:62`: sanitization applies only when the KEY is sensitive (`*_key`, `token`, `authorization` variants, `endpoint`, `raw_response_preview`). Parsed artifacts can persist secrets embedded in ordinary fields — reproduced: `{"content": "Authorization: Basic dXNlcjpwYXNz", "url": "https://example.test/v1?token=url-secret"}` persists BOTH unchanged.

Fix: sanitize authorization headers and credential-bearing URLs in EVERY persisted string leaf, including ordinary `content`, `message`, `error`, `url` fields — recursively walk the artifact, and on any string: redact full `Authorization: <scheme> <credential>` header values (every scheme), redact credential-like URL query params (token/key/sig/signature/api_key/apikey/secret + auth header inside url values), and leave everything else untouched. Add negative fixtures: a parsed JSON artifact and a synthesized response both containing secrets in ordinary fields must come out fully redacted.

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```

Add your new fixtures to those files so the slice covers them. Expected exit 0.

## Report
Return: exact changes (files + line refs), fixture names, pytest output. Do NOT commit.

exec
/bin/zsh -lc "nl -ba tests/test_agent_runtime_adapter.py | sed -n '1,110p'; rg -n \"unknown\" tests/test_agent_runtime_adapter.py vibecomfy/comfy_nodes/agent/provider.py vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1,240p'; git diff --unified=8 45415680..1bd1b04b -- . ':(exclude).oracle/checkins/batch-B01.md' | rg '"'^diff --git|''^@@'"' | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 53ms:
diff --git a/.oracle/briefs/batch-B01-rework.md b/.oracle/briefs/batch-B01-rework.md
@@ -0,0 +1,38 @@
diff --git a/.oracle/briefs/batch-B01-rework2.md b/.oracle/briefs/batch-B01-rework2.md
@@ -0,0 +1,26 @@
diff --git a/.oracle/briefs/batch-B01.md b/.oracle/briefs/batch-B01.md
@@ -0,0 +1,39 @@
diff --git a/tests/live_agentic_harness/adapter.py b/tests/live_agentic_harness/adapter.py
@@ -144,9 +144,10 @@ def run_headless_scenario(
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
@@ -5,17 +5,16 @@ kill-on-timeout via ``subprocess.run``), bounded by ``--max-workers``. Modeled
@@ -36,36 +35,16 @@ from .failure_analysis import (
@@ -153,17 +132,17 @@ def _failure_summary(
@@ -202,108 +181,144 @@ def _attempt_record(summary: dict[str, Any], *, attempt: int) -> dict[str, Any]:
diff --git a/tests/test_agent_runtime_adapter.py b/tests/test_agent_runtime_adapter.py
@@ -5,16 +5,17 @@ import os
@@ -49,16 +50,48 @@ def test_explicit_openrouter_route_cannot_be_hijacked_by_generic_endpoint_or_key
@@ -391,8 +424,212 @@ def test_openrouter_worker_401_error_is_permission_error(
diff --git a/tests/test_executor_contracts.py b/tests/test_executor_contracts.py
@@ -22,31 +22,33 @@ from vibecomfy.executor.contracts import (
@@ -628,16 +630,58 @@ class TestImplementationResult:
@@ -653,16 +697,29 @@ class TestReport:
diff --git a/tests/test_executor_flows.py b/tests/test_executor_flows.py
@@ -1708,16 +1708,56 @@ class TestExecutorFailureHandling:
diff --git a/tests/test_headless_agent_artifacts.py b/tests/test_headless_agent_artifacts.py
@@ -198,16 +198,17 @@ def test_headless_artifacts_copy_only_real_durable_turn_files(tmp_path: Path) ->
@@ -232,14 +233,236 @@ def test_headless_artifacts_copy_model_files_when_turn_produced_them(tmp_path: P
diff --git a/tests/test_live_agentic_runner_persistence.py b/tests/test_live_agentic_runner_persistence.py
@@ -1,31 +1,55 @@
@@ -58,17 +82,17 @@ def test_final_summary_replaces_partial_summary(tmp_path: Path) -> None:
@@ -95,31 +119,31 @@ def test_runner_retries_infra_timeout_and_preserves_attempts(
@@ -139,16 +163,17 @@ def test_runner_retries_provider_capacity_summary_and_preserves_attempts(
@@ -178,26 +203,105 @@ def test_runner_retries_provider_capacity_summary_and_preserves_attempts(
@@ -207,16 +311,17 @@ def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
@@ -230,17 +335,17 @@ def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
@@ -343,8 +448,46 @@ def test_runner_timeout_preserves_scenario_graph_change_expectation(
diff --git a/tests/test_runtime_worker_retry.py b/tests/test_runtime_worker_retry.py
@@ -1,17 +1,13 @@
@@ -47,64 +43,146 @@ def _common_kwargs():
diff --git a/vibecomfy/agent/artifacts.py b/vibecomfy/agent/artifacts.py
@@ -3,38 +3,58 @@
@@ -52,20 +72,99 @@ def _json_safe(value: Any) -> Any:
@@ -87,17 +186,32 @@ def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
@@ -307,16 +421,23 @@ def synthesize_headless_artifacts(
@@ -347,17 +468,17 @@ def synthesize_headless_artifacts(
diff --git a/vibecomfy/comfy_nodes/agent/provider.py b/vibecomfy/comfy_nodes/agent/provider.py
@@ -7,16 +7,21 @@ import logging
@@ -185,44 +190,55 @@ def _extract_json_object(text: str) -> dict[str, Any]:
@@ -879,17 +895,17 @@ def _resolve_agent_route(route: str | None) -> AgentRouteDescriptor:
@@ -1021,16 +1037,17 @@ def _normalize_agent_response(
@@ -1042,17 +1059,17 @@ def _normalize_agent_response(
@@ -1225,24 +1242,24 @@ def run_agent_turn_delta(
@@ -1253,51 +1270,54 @@ def _normalize_batch_response(
@@ -1351,16 +1371,71 @@ def _batch_retry_messages(
@@ -1395,16 +1470,17 @@ def run_agent_turn_batch(
@@ -1414,21 +1490,48 @@ def run_agent_turn_batch(
diff --git a/vibecomfy/comfy_nodes/agent/runtime.py b/vibecomfy/comfy_nodes/agent/runtime.py
@@ -42,70 +42,53 @@ import logging
@@ -126,16 +109,56 @@ def snapshot_deepseek_usage_capture() -> tuple[dict[str, int], bool]:
@@ -280,17 +303,19 @@ def _raise_worker_error(result: Mapping[str, Any]) -> None:
@@ -307,23 +332,28 @@ def _agent_id_for_route(route: str | None) -> str:
@@ -331,25 +361,27 @@ def _is_real_model_override(model: str | None) -> bool:
@@ -467,111 +499,153 @@ def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | No
@@ -581,16 +655,17 @@ def _run_worker_once(
@@ -692,21 +767,23 @@ def run_agent_turn(
@@ -734,21 +811,23 @@ def run_agent_turn_delta(
@@ -770,21 +849,23 @@ def run_agent_turn_batch(
@@ -1020,17 +1101,21 @@ def readiness(*, route: str, model: str | None = None) -> dict[str, Any]:
@@ -1103,53 +1188,36 @@ def run_model_turn(
diff --git a/vibecomfy/comfy_nodes/agent/worker.py b/vibecomfy/comfy_nodes/agent/worker.py
@@ -60,16 +60,21 @@ def _bootstrap_repo_root() -> None:
@@ -90,45 +95,88 @@ def _extract_json_object(text: str) -> dict:
@@ -141,40 +189,54 @@ def _persist_parse_evidence(
@@ -519,17 +581,25 @@ def main() -> int:
@@ -541,16 +611,26 @@ def main() -> int:
diff --git a/vibecomfy/executor/agent_backend.py b/vibecomfy/executor/agent_backend.py
@@ -8,27 +8,33 @@ isolation and never importing Arnold agent backends in the ComfyUI process.
@@ -43,24 +49,17 @@ def _extract_content(result: dict[str, Any]) -> str:
@@ -71,25 +70,67 @@ def _attach_model_turn_evidence(
@@ -156,24 +197,30 @@ def run_classify_turn(
@@ -271,21 +318,27 @@ def run_reply_turn(
diff --git a/vibecomfy/executor/contracts.py b/vibecomfy/executor/contracts.py
@@ -28,16 +28,210 @@ _SENSITIVE_QUERY_KEYS = frozenset({
@@ -2106,37 +2300,43 @@ class Report:
@@ -2150,18 +2350,19 @@ class Report:
@@ -2411,16 +2612,19 @@ class ExecutorResult:
@@ -2491,17 +2695,21 @@ __all__ = [
diff --git a/vibecomfy/executor/core.py b/vibecomfy/executor/core.py
@@ -27,18 +27,21 @@ from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
@@ -49,16 +52,17 @@ from .contracts import (
@@ -94,146 +98,53 @@ _INSTALL_REQUEST_TERMS = (
@@ -1073,37 +984,33 @@ def _run_classify(
@@ -1802,37 +1709,33 @@ def _run_reply(
@@ -1844,24 +1747,24 @@ class _ExecutorPhaseError(Exception):
@@ -1964,43 +1867,48 @@ def run_executor(
@@ -2106,17 +2014,17 @@ def run_executor(
@@ -2411,33 +2319,33 @@ def run_executor(

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from vibecomfy.executor.contracts import ModelAttemptEvidence, redact_model_preview; samples=[\"{\\\"api_key\\\":\\\"sk-preview-secret\\\"}\",\"{\\\"authorization\\\":\\\"Basic dXNlcjpwYXNz\\\"}\",\"{\\\"token\\\":\\\"url-ish-secret\\\"}\"]; [print(repr(s),\"=>\",repr(redact_model_preview(s)),\"=>\",repr(ModelAttemptEvidence(outcome=\"failure\",failure_type=\"malformed_json\",raw_response_preview=s).to_dict().get(\"raw_response_preview\"))) for s in samples]'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 603ms:
'{"api_key":"sk-preview-secret"}' => '{"api_key":"sk-preview-secret"}' => '{"api_key":"sk-preview-secret"}'
'{"authorization":"Basic dXNlcjpwYXNz"}' => '{"authorization":"Basic dXNlcjpwYXNz"}' => '{"authorization":"Basic dXNlcjpwYXNz"}'
'{"token":"url-ish-secret"}' => '{"token":"url-ish-secret"}' => '{"token":"url-ish-secret"}'

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '240,325p'; rg -n \"parse_reason|raw_response_preview|completion_tokens|prompt_tokens|total_tokens|getattr\\(.*model\\)|worker_result\" vibecomfy/comfy_nodes/agent/runtime.py vibecomfy/comfy_nodes/agent/provider.py vibecomfy/executor/{agent_backend.py,core.py} | sed -n '1,300p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   240	            if value:
   241	                candidates.append((key, value))
   242	    candidates.sort(key=lambda item: (item[0] != "OPENROUTER_API_KEY", item[0]))
   243	    for _, value in candidates:
   244	        if value.startswith("sk-or-"):
   245	            return value
   246	    return candidates[0][1] if candidates else None
   247
   248
   249	def _is_runtime_unavailable(result: Mapping[str, Any]) -> bool:
   250	    """True when a worker error means the agent runtime is unavailable.
   251
   252	    Covers a missing backend dependency (``ImportError`` /
   253	    ``ModuleNotFoundError``) and an unregistered dispatch adapter
   254	    (``LookupError`` — e.g. codex/claude not wired into the default dispatcher
   255	    yet). The worker also sets ``runtime_unavailable: True`` for these. All map
   256	    to a non-retryable AGENT_RUNTIME_UNAVAILABLE signal upstream, never to a
   257	    transient provider error.
   258	    """
   259	    if result.get("runtime_unavailable"):
   260	        return True
   261	    return result.get("error_type") in {"ModuleNotFoundError", "ImportError", "LookupError"}
   262
   263
   264	def _raise_worker_error(result: Mapping[str, Any]) -> None:
   265	    err = str(result.get("error") or "agent worker failed")
   266	    output_tail = "\n".join(
   267	        str(result.get(key) or "").strip()
   268	        for key in ("worker_stdout_tail", "worker_stderr_tail")
   269	        if result.get(key)
   270	    ).strip()
   271	    if output_tail:
   272	        err = f"{err}\n\nWorker output tail:\n{output_tail}"
   273	    error_type = str(result.get("error_type") or "").strip()
   274	    message = f"{error_type}: {err}" if error_type and error_type not in err else err
   275	    lowered = message.lower()
   276
   277	    def _with_worker_result(exc: BaseException) -> BaseException:
   278	        """Attach the full worker result dict additively for evidence plumbing.
   279
   280	        The exception type and message are unchanged; upstream classify/reply
   281	        failure envelopes can read ``worker_result`` to persist parse_reason,
   282	        raw preview, usage, model, phase, and endpoint without re-resolving
   283	        provider internals.
   284	        """
   285	        try:
   286	            exc.worker_result = dict(result)  # type: ignore[attr-defined]
   287	        except Exception:  # noqa: BLE001 - evidence attachment is best-effort
   288	            pass
   289	        return exc
   290
   291	    if (
   292	        error_type in {"AuthError", "AuthenticationError", "PermissionError"}
   293	        or "authenticationerror" in lowered
   294	        or "error code: 401" in lowered
   295	        or "missing authentication header" in lowered
   296	        or "invalid api key" in lowered
   297	        or "unauthorized" in lowered
   298	    ):
   299	        raise _with_worker_result(PermissionError(message))
   300	    if _is_runtime_unavailable(result):
   301	        raise _with_worker_result(ImportError(message))
   302	    raise _with_worker_result(RuntimeError(message))
   303
   304
   305	def _normalize_route(route: str | None) -> str:
   306	    normalized = (route or "arnold").strip().lower()
   307	    if normalized in {"auto", "anthropic", "openai-codex"}:
   308	        return "arnold"
   309	    if normalized == "hermes":
   310	        return "openrouter"
   311	    if normalized in {"arnold", "openrouter", "deepseek"}:
   312	        return "openrouter" if normalized == "deepseek" else normalized
   313	    return "unknown"
   314
   315
   316	# Panel route -> arnold dispatch agent id. The worker registers/dispatches under
   317	# this id. Only ``hermes`` is wired in the default dispatcher today; ``codex`` /
   318	# ``claude`` will raise LookupError until adapters are registered (Step B's
   319	# readiness gate keeps the panel from reaching them).
   320	_ROUTE_TO_AGENT_ID = {
   321	    "deepseek": "hermes",
   322	    "openrouter": "hermes",
   323	    "openai-codex": "codex",
   324	    "anthropic": "claude",
   325	}
vibecomfy/comfy_nodes/agent/runtime.py:277:    def _with_worker_result(exc: BaseException) -> BaseException:
vibecomfy/comfy_nodes/agent/runtime.py:281:        failure envelopes can read ``worker_result`` to persist parse_reason,
vibecomfy/comfy_nodes/agent/runtime.py:286:            exc.worker_result = dict(result)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/runtime.py:299:        raise _with_worker_result(PermissionError(message))
vibecomfy/comfy_nodes/agent/runtime.py:301:        raise _with_worker_result(ImportError(message))
vibecomfy/comfy_nodes/agent/runtime.py:302:    raise _with_worker_result(RuntimeError(message))
vibecomfy/comfy_nodes/agent/runtime.py:507:def _is_typed_empty_worker_result(result: Mapping[str, Any]) -> bool:
vibecomfy/comfy_nodes/agent/runtime.py:518:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/runtime.py:578:    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
vibecomfy/comfy_nodes/agent/runtime.py:621:            and _is_typed_empty_worker_result(result)
vibecomfy/comfy_nodes/agent/runtime.py:716:                    "runtime.worker_result",
vibecomfy/executor/agent_backend.py:76:        if result is not None and getattr(exc, "worker_result", None) is None:
vibecomfy/executor/agent_backend.py:77:            exc.worker_result = dict(result)  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:80:        if raw is not None and getattr(exc, "raw_response_preview", None) is None:
vibecomfy/executor/agent_backend.py:81:            exc.raw_response_preview = _preview_raw(raw)  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:119:        "raw_response_preview": raw,
vibecomfy/comfy_nodes/agent/provider.py:111:        parse_reason: str | None = None,
vibecomfy/comfy_nodes/agent/provider.py:115:        self.raw_response_preview = _preview_raw_model_response(raw_response)
vibecomfy/comfy_nodes/agent/provider.py:116:        self.parse_reason = parse_reason
vibecomfy/comfy_nodes/agent/provider.py:206:    "worker_result",
vibecomfy/comfy_nodes/agent/provider.py:208:    "parse_reason",
vibecomfy/comfy_nodes/agent/provider.py:209:    "raw_response_preview",
vibecomfy/comfy_nodes/agent/provider.py:211:    "completion_tokens",
vibecomfy/comfy_nodes/agent/provider.py:212:    "prompt_tokens",
vibecomfy/comfy_nodes/agent/provider.py:213:    "total_tokens",
vibecomfy/comfy_nodes/agent/provider.py:306:            parse_reason="empty",
vibecomfy/comfy_nodes/agent/provider.py:314:            parse_reason="missing_batch_fence",
vibecomfy/comfy_nodes/agent/provider.py:321:            parse_reason="multiple_batch_fences",
vibecomfy/comfy_nodes/agent/provider.py:1260:        raise MalformedModelJSON(str(exc), parse_reason=exc.code) from exc
vibecomfy/comfy_nodes/agent/provider.py:1304:            parse_reason="empty",
vibecomfy/comfy_nodes/agent/provider.py:1369:    raw_preview = getattr(exc, "raw_response_preview", None)
vibecomfy/comfy_nodes/agent/provider.py:1383:    reason = getattr(exc, "parse_reason", None)
vibecomfy/comfy_nodes/agent/provider.py:1404:        "raw_response_preview": getattr(exc, "raw_response", None),
vibecomfy/comfy_nodes/agent/provider.py:1430:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/provider.py:1535:                    "parse_reason": getattr(last_exc, "parse_reason", None),
vibecomfy/comfy_nodes/agent/provider.py:1536:                    "raw_response_preview": getattr(last_exc, "raw_response_preview", None),
vibecomfy/executor/core.py:115:        worker_result = getattr(current, "worker_result", None)
vibecomfy/executor/core.py:116:        if isinstance(worker_result, Mapping):
vibecomfy/executor/core.py:117:            attempts = coerce_model_attempts(worker_result.get("model_attempts"))

Static trace and diff hygiene are complete. The full suite cannot collect because the read-only sandbox has no writable temp directory; a pure subset completed 33/33. One concrete redaction escape was reproduced and is being cross-checked before the verdict.
  ✓ Read B01 acceptance criteria and map changed files
  ✓ Audit contracts, provenance, retry policy, redaction, and unknown routes
  ✓ Run diff hygiene and focused verification
  → Synthesize adversarial PASS/FAIL verdict with file:line evidence
Static trace and diff hygiene are complete. The full suite cannot collect because the read-only sandbox has no writable temp directory; a pure subset completed 33/33. One concrete redaction escape was reproduced and is being cross-checked before the verdict.
  ✓ Read B01 acceptance criteria and map changed files
  ✓ Audit contracts, provenance, retry policy, redaction, and unknown routes
  ✓ Run diff hygiene and focused verification
  → Synthesize adversarial PASS/FAIL verdict with file:line evidence
collab: Wait
collab: Wait
collab: Wait
Review complete. Criteria 1–4 and 6–8 are satisfied, but criterion 5 has a reproducible secret-persistence escape in canonical failure previews, so the binary checkpoint verdict is FAIL.
  ✓ Read B01 acceptance criteria and map changed files
  ✓ Audit contracts, provenance, retry policy, redaction, and unknown routes
  ✓ Run diff hygiene and focused verification
  ✓ Synthesize adversarial PASS/FAIL verdict with file:line evidence
codex
B01 CHECKPOINT VERDICT: FAIL — Unified provenance and retry semantics are sound, but JSON-shaped failure previews can persist API keys and authorization data.

1. One evidence contract — PASS

`ModelAttemptEvidence` is defined once in `vibecomfy/executor/contracts.py:128-215`, with normalization through `coerce_model_attempts` at `:218-228`. Worker, runtime, provider, executor, artifacts, and harness consume `model_attempts`. The legacy `Report.model_response` is derived only and is not serialized (`contracts.py:2328-2359`); no second final-attempt format remains.

2. Failure taxonomy — PASS

The six distinct values are declared at `contracts.py:36-43`:

- `empty_response`
- `malformed_json`
- `non_json_content`
- `missing_required_fields`
- `timeout`
- `provider_failure`

Structural classification is implemented at `worker.py:106-121`, with the six-way regression matrix at `tests/test_agent_runtime_adapter.py:434-450`.

3. Success-path provenance — PASS

Worker records requested/resolved model, adapter, provider, transport, endpoint, finish reason, and token usage at `worker.py:143-174`. The three former stripping seams now return complete worker results for Python, delta, and batch at `runtime.py:738-863`, covered by `tests/test_agent_runtime_adapter.py:512-540`.

Classify/reply attempts enter executor capture at `agent_backend.py:191-225,312-341`; batch metadata is merged at `provider.py:220-234,1490-1529`. Final reports snapshot the attempts at `core.py:1873-1902`, serialize them at `contracts.py:2358-2359,2620-2622`, and write `model_attempts.json` at `artifacts.py:428-435`.

4. Retry policy — PASS

Runtime retry requires typed `empty_response` plus observed `completion_tokens == 0` (`runtime.py:507-519,563-631`). Provider batch retry applies the same gate (`provider.py:1422-1431,1497-1508`). Harness classification uses typed attempts only and does not inspect prose (`runner.py:193-233,286-316`).

Malformed non-empty and stale/conflicting infra-marker regressions are present at `tests/test_live_agentic_runner_persistence.py:261-297,458-493`.

5. Redaction — FAIL

`redact_model_preview` does not recognize sensitive JSON-quoted keys. A direct read-only probe showed these remain unchanged through both `redact_model_preview()` and `ModelAttemptEvidence.to_dict()`:

```json
{"api_key":"sk-secret"}
{"authorization":"Basic dXNlcjpwYXNz"}
{"token":"tok-secret"}
```

The incomplete patterns are at `contracts.py:47-55,87-103`. The leak reaches durable artifacts because `artifacts.py:143-150` delegates `raw_response_preview` to the same redactor before `model_attempts.json` is written at `:428-435`.

Plain-text authorization headers and secret URL parameters are covered, but the required “cannot persist” guarantee is not met for JSON-shaped failure previews.

6. Unsupported routes — PASS

Unsupported routes become `unknown` in provider resolution (`provider.py:895-905`) and runtime route/adapter/model resolution (`runtime.py:305-371`). Provider/transport inference is suppressed for non-Hermes routes (`runtime.py:522-534`; `worker.py:124-140`). The end-to-end regression is `tests/test_agent_runtime_adapter.py:58-87`.

7. Scope and diff hygiene — PASS

`git diff --check 45415680..1bd1b04b` exited cleanly. The range contains 15 B01 implementation/test paths plus four B01-specific `.oracle` artifacts—19 paths total, rather than the stated 14—but no unrelated product area.

8. Focused verification — PARTIAL

The full focused command could not collect because the read-only sandbox has no writable temporary directory, including `/tmp`. With capture and cache disabled, the pure contract/provenance/retry subset completed:

```text
33 passed, 1 warning in 7.11s
```

The orchestrator’s reported 556-pass run remains the evidence for tests requiring `tmp_path`. Live runs were appropriately skipped.

Issue requiring rework:

- `vibecomfy/executor/contracts.py:47` — sanitize quoted JSON sensitive fields in failure previews, including API keys, authorization values, and tokens. Ensure malformed JSON is also safely handled. Add contract-level and durable `model_attempts.json` regressions proving those exact secrets cannot persist; `vibecomfy/agent/artifacts.py:143` must not reintroduce them.
tokens used
321,466
B01 CHECKPOINT VERDICT: FAIL — Unified provenance and retry semantics are sound, but JSON-shaped failure previews can persist API keys and authorization data.

1. One evidence contract — PASS

`ModelAttemptEvidence` is defined once in `vibecomfy/executor/contracts.py:128-215`, with normalization through `coerce_model_attempts` at `:218-228`. Worker, runtime, provider, executor, artifacts, and harness consume `model_attempts`. The legacy `Report.model_response` is derived only and is not serialized (`contracts.py:2328-2359`); no second final-attempt format remains.

2. Failure taxonomy — PASS

The six distinct values are declared at `contracts.py:36-43`:

- `empty_response`
- `malformed_json`
- `non_json_content`
- `missing_required_fields`
- `timeout`
- `provider_failure`

Structural classification is implemented at `worker.py:106-121`, with the six-way regression matrix at `tests/test_agent_runtime_adapter.py:434-450`.

3. Success-path provenance — PASS

Worker records requested/resolved model, adapter, provider, transport, endpoint, finish reason, and token usage at `worker.py:143-174`. The three former stripping seams now return complete worker results for Python, delta, and batch at `runtime.py:738-863`, covered by `tests/test_agent_runtime_adapter.py:512-540`.

Classify/reply attempts enter executor capture at `agent_backend.py:191-225,312-341`; batch metadata is merged at `provider.py:220-234,1490-1529`. Final reports snapshot the attempts at `core.py:1873-1902`, serialize them at `contracts.py:2358-2359,2620-2622`, and write `model_attempts.json` at `artifacts.py:428-435`.

4. Retry policy — PASS

Runtime retry requires typed `empty_response` plus observed `completion_tokens == 0` (`runtime.py:507-519,563-631`). Provider batch retry applies the same gate (`provider.py:1422-1431,1497-1508`). Harness classification uses typed attempts only and does not inspect prose (`runner.py:193-233,286-316`).

Malformed non-empty and stale/conflicting infra-marker regressions are present at `tests/test_live_agentic_runner_persistence.py:261-297,458-493`.

5. Redaction — FAIL

`redact_model_preview` does not recognize sensitive JSON-quoted keys. A direct read-only probe showed these remain unchanged through both `redact_model_preview()` and `ModelAttemptEvidence.to_dict()`:

```json
{"api_key":"sk-secret"}
{"authorization":"Basic dXNlcjpwYXNz"}
{"token":"tok-secret"}
```

The incomplete patterns are at `contracts.py:47-55,87-103`. The leak reaches durable artifacts because `artifacts.py:143-150` delegates `raw_response_preview` to the same redactor before `model_attempts.json` is written at `:428-435`.

Plain-text authorization headers and secret URL parameters are covered, but the required “cannot persist” guarantee is not met for JSON-shaped failure previews.

6. Unsupported routes — PASS

Unsupported routes become `unknown` in provider resolution (`provider.py:895-905`) and runtime route/adapter/model resolution (`runtime.py:305-371`). Provider/transport inference is suppressed for non-Hermes routes (`runtime.py:522-534`; `worker.py:124-140`). The end-to-end regression is `tests/test_agent_runtime_adapter.py:58-87`.

7. Scope and diff hygiene — PASS

`git diff --check 45415680..1bd1b04b` exited cleanly. The range contains 15 B01 implementation/test paths plus four B01-specific `.oracle` artifacts—19 paths total, rather than the stated 14—but no unrelated product area.

8. Focused verification — PARTIAL

The full focused command could not collect because the read-only sandbox has no writable temporary directory, including `/tmp`. With capture and cache disabled, the pure contract/provenance/retry subset completed:

```text
33 passed, 1 warning in 7.11s
```

The orchestrator’s reported 556-pass run remains the evidence for tests requiring `tmp_path`. Live runs were appropriately skipped.

Issue requiring rework:

- `vibecomfy/executor/contracts.py:47` — sanitize quoted JSON sensitive fields in failure previews, including API keys, authorization values, and tokens. Ensure malformed JSON is also safely handled. Add contract-level and durable `model_attempts.json` regressions proving those exact secrets cannot persist; `vibecomfy/agent/artifacts.py:143` must not reintroduce them.
