Reading additional input from stdin...
2026-08-13T12:02:19.293252Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:19.293307Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:19.293317Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb00-7114-7402-b59d-48bf4567f533
--------
user
# MEGADO CHECKPOINT — Batch B01 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the B01 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**B01 [HARD] — Typed failures and unified attempt provenance.** Tasks + acceptance from `.oracle/tasklist.md` (B01 section). The diff to review: `git diff 45415680..a8d4974a` (G0R PASS SHA → B01 commit). The executor was GPT-5.6 Sol (workspace-write, 30-min clamp hit mid-verification; the orchestrator ran the focused suite to completion).

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
7. Scope: diff contains only B01-scope files; `git diff --check 45415680..a8d4974a` clean.
8. Run the focused suite yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks); live runs skipped (orchestrator-phase).

## Output

First line: `B01 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–8) with evidence, and an issue list if FAIL (each with file:line + what to rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit MEGADO oracle checkpoint. I’ll keep the review read-only, inspect the exact commit range, and split independent contract/provenance and retry/redaction checks into parallel evidence reviews before I run the focused suite.
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
The MEGADO skill’s normal external-Flash delegation path is unavailable under this checkpoint’s read-only/restricted-network sandbox, so I’m preserving the read-only constraint and using three internal read-only reviewers for independent evidence collection. I’ll personally reconcile their findings against the tasklist and test results.
2026-08-13T12:02:42.909283Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:42.909384Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:42.909399Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:48.460045Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:48.460400Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:48.460452Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:53.902633Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:53.902846Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:02:53.902874Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short --branch && git diff --stat 45415680..a8d4974a && git diff --name-status 45415680..a8d4974a && git diff --check 45415680..a8d4974a && sed -n '/"'^## B01/,/''^## B02/p'"' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 161ms:
 .oracle/briefs/batch-B01-rework.md            |    38 +
 .oracle/briefs/batch-B01.md                   |    39 +
 .oracle/checkins/batch-B01.md                 | 10215 ++++++++++++++++++++++++
 tests/live_agentic_harness/adapter.py         |     1 +
 tests/live_agentic_harness/runner.py          |    85 +-
 tests/test_agent_runtime_adapter.py           |   237 +
 tests/test_executor_contracts.py              |    57 +
 tests/test_executor_flows.py                  |    40 +
 tests/test_headless_agent_artifacts.py        |   134 +
 tests/test_live_agentic_runner_persistence.py |   125 +-
 tests/test_runtime_worker_retry.py            |   134 +-
 vibecomfy/agent/artifacts.py                  |    34 +-
 vibecomfy/comfy_nodes/agent/provider.py       |   135 +-
 vibecomfy/comfy_nodes/agent/runtime.py        |   306 +-
 vibecomfy/comfy_nodes/agent/worker.py         |   132 +-
 vibecomfy/executor/agent_backend.py           |    71 +-
 vibecomfy/executor/contracts.py               |   234 +-
 vibecomfy/executor/core.py                    |   174 +-
 18 files changed, 11776 insertions(+), 415 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/briefs/batch-B01-rework.md
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## B01 — Typed failures and unified attempt provenance `[HARD]`

### Tasks

1. Introduce one additive model-attempt evidence contract across worker, runtime, provider/backend, executor, artifacts, and harness.
2. Distinguish:
   - empty response;
   - malformed non-empty JSON;
   - non-JSON content;
   - missing required fields;
   - timeout;
   - capacity/provider failure.
3. Persist on every successful and failed attempt:
   - phase and attempt;
   - requested and resolved model;
   - adapter;
   - actual provider and transport;
   - normalized endpoint;
   - finish reason;
   - token usage.
4. Persist bounded raw previews only for failures.
5. Fix the three success-path runtime stripping seams and merge worker-observed metadata into batch audit metadata and final report artifacts.
6. Permit a fresh-transport retry only for typed empty responses. Never derive infrastructure status from response wording.
7. Serialize unavailable non-Hermes provenance as `unknown`; never infer it.

### Acceptance

- Every failure type serializes distinctly.
- Successful classify, reply, and batch calls retain provenance through final artifacts.
- Requested and resolved models remain distinct across routing/retries.
- Typed empty evidence reaches the existing retry; malformed non-empty results remain product failures.
- Unsupported routes report explicit unknowns.
- Redaction proves keys, authorization data, and secret URL parameters cannot persist.

### Oracle checkpoint

Trace representative successful and failed calls end to end. Reject parallel evidence formats or inferred fields.

---

## D13 — Corpus integrity, satisfiability, and semantic rubrics `[HARD]`

### Tasks

1. Check in an authoritative manifest for the current 100 scenarios:
   - stable ID;
   - path;
   - descriptor SHA-256;
   - inclusion status;
   - source-workflow ID and hash where applicable.
2. Make runner discovery consume the manifest rather than an unrestricted glob. Reject missing, changed, duplicate, or unmanifested files.
3. Audit scenario/query/schema/operation/rubric coherence, prioritizing all anomalous or revised cases.
4. Correct the three mislabeled edits:
   - set edit/change expectations truthfully if satisfiable;
   - otherwise rewrite or replace them while preserving coverage;
   - never let them pass as no-ops.
5. Classify the remaining 37 query non-edits:
   - 35 semantic product scenarios receive explicit expected-answer criteria;
   - the smoke and speed-distillation cases become explicit health controls.
6. Ensure every retained edit `desired` block feeds an active judge.
7. Record every rewrite/replacement and preserve matched-versus-revised reporting.
8. Provision `external_workflows/` before accepting satisfiability or source hashes.

### Acceptance

- The manifest selects exactly 100 unique ID/stem-matched scenarios.
- The 40 no-change-routed cases reconcile as 35 semantic non-edits, 2 health controls, and 3 corrected edits.
- The three edits cannot pass without a judged graph change or legitimate grounded refusal.
- All 35 semantic non-edits have evidence-backed rubrics.
- Health controls are excluded from semantic-product rates.
- Stray scenario files cannot silently change the lane.
- Source-workflow hashes resolve before D13 passes.

### Oracle checkpoint

Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.

---

## B04 — Real-schema authority

### Tasks

1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
2. Migrate all four verified provisional-first sites:
   - `_frag_research.py:874`;
   - `_frag_response_contract.py:793`;
   - `_frag_batch_loop.py:910`;
   - `edit_batch_repl.py:1115`.
3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.

### Acceptance

- All seven sites are real-first.
- Session schema authority remains real-first across turns.
- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
- Invalid enum values are rejected before mutation for add and set.
- Missing local asset filenames remain warning-only.

### Oracle checkpoint

Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.

---

## B03 — Canonical semantic pin comparison `[HARD]`

### Tasks

1. Add fixtures for:
   - flat Set/Get fan-out;
   - 1:1 reroute lowering;
   - loop-cloned consumer UIDs;
   - nested subgraphs;
   - multi-output nodes;
   - genuine removed, repointed, or orphaned consumers.
2. Replace raw UID-keyed multiset comparison with one canonical semantic-set helper:
   - preserve input/output port identity;
   - dedupe multiplicity;
   - normalize reroutes to terminal endpoints;
   - normalize loop-cloned UIDs to their canonical consumer UID.
3. Feed the canonical before/after sets into the pin fence.
4. Refuse when semantic sets genuinely differ or endpoint resolution is ambiguous/unresolved.
5. Preserve canonical before/after sets in diagnostics.
6. Do not revive dead link-count refusal strings or construct a second topology abstraction.

### Acceptance

- Multiplicity-only Set/Get expansion passes.
- Equivalent reroute, loop-clone, link-renumbering, and nested lowering passes.
- Added, removed, repointed, orphaned, or output-port-changed consumers refuse.
- Unresolved/cyclic paths terminate deterministically and fail closed.
- Multi-output identity is preserved.
- B02 preservation tests remain green.

### Oracle checkpoint

Require both false-positive and true-topology-change fixtures to pass before B05-lite.

---

## B05-lite — Journaled unexpected-exception rollback `[HARD]`

### Tasks

1. Create a loop-entry rollback journal covering:
   - existing mutable session snapshot;
   - `value_default_context`;
   - UI payload, batch accumulators, budget, and exit fields;
   - exact bytes-or-absence of rendered Python, candidate UI, model request/response, and messages artifacts.
2. Cover the full mutating path through apply, render, `done()`, and final evidence promotion with one exception boundary.
3. On unexpected exception:
   - restore session state;
   - restore files byte-for-byte;
   - truncate appended state;
   - close the allocated durable turn as aborted;
   - re-raise.
4. Persist a separate bounded typed abort diagnostic after restoration.
5. Buffer telemetry until commit where practical; otherwise emit an explicit abort marker and ensure no event claims the rolled-back candidate committed.
6. Add no repair call, retry loop, or fingerprint.

### Acceptance

- Faults after mutation, render, candidate write, `done()`, and finalization restore exact pre-batch state and file existence.
- Ledger, hashes, name maps, and candidate state match the restored graph.
- No partial candidate is observable.
- Durable turns do not remain allocated-but-unrecorded.
- Telemetry cannot report rolled-back work as committed.
- Ordinary validation failures are unchanged.
- No additional model call occurs.

### Oracle checkpoint

Review the fault-injection matrix and byte-level before/after evidence.

---

## B06 — Universal UI evidence and semantic adjudication `[HARD]`

### Tasks

1. Persist authoritative `original.ui.json` and `final.ui.json` for every adjudicated route. Unchanged/refused/clarify routes explicitly project final from original.
2. Replace refusal-kind auto-acceptance with tri-state grounded-refusal adjudication:
   - supported blocker and no representable edit → pass;
   - unsupported/fabricated inability → fail;
   - missing evidence or judge outage → undetermined.
3. Implement one rubric-driven tri-state answer judge for the 35 D13 semantic non-edits:
   - grounded, relevant, correct response → pass;
   - hallucinated, wrong, irrelevant, vacuous, or empty-but-valid response → fail;
   - unavailable evidence/judge outage → undetermined.
4. Keep the two health controls structurally scored and separately reported.
5. Ensure the three corrected edits use the edit-intent judge.
6. Never use prose substrings as evidence.

### Acceptance

- Refusal fixtures produce pass/fail/fail/undetermined for grounded, unsupported, fabricated, and outage cases.
- A healthy but false explanation fails.
- Judge outage never passes.
- Every selected semantic non-edit has a rubric and judge result.
- All routes carry original/final UI evidence.
- Only `pass` satisfies a semantic scenario.

### Oracle checkpoint

Review refusal and semantic-answer fixture packs, evidence availability, and control/product separation.

---

## B07-lite — Explicit transport experiment

### Tasks

1. Add the smallest explicit harness selector, preferably `--transport {openrouter,native}`.
2. Eliminate ambient-credential transport selection.
3. Consume B01’s actual successful/failed provenance; do not create another metadata format.
4. If historical call artifacts are restored, determine their actual transports rather than trusting readiness labels.
5. Run an approximately ten-scenario empty-heavy matched native/OpenRouter experiment on the same commit, scenario set, profile, and configuration.
6. Keep OpenRouter canonical unless a material repeatable advantage receives later oracle approval.

### Acceptance

- Ambient credentials cannot silently change transport.
- Every attempt reports requested/resolved model, provider, transport, endpoint, finish reason, tokens, and attempt.
- Secrets remain redacted.
- The experiment reports scenario IDs, typed-empty rate, attempts, latency, and configuration digest.
- No all-Flash profile or prompt rewrite is introduced.
- A written decision retains OpenRouter or proposes a separately approved change.

### Oracle checkpoint

Review comparability and provenance before accepting any transport conclusion.

---

## B08-cut — Deterministic endpoint integrity `[HARD]`

Prompt/model quality work remains cut. This batch replaces it with the verified C8/C9 editor fix.

### Tasks

1. Add regressions for:
   - catalog output name absent from the working node’s outputs;
   - schema-derived source index out of bounds;
   - add-node link resolution;
   - unknown target input;
   - valid named multi-input/output links;
   - the late `Missing stable link from port` signature.
2. Make working-graph ports authoritative during endpoint resolution. Schema may validate or enrich but cannot return a slot absent from the node.
3. Add one shared pre-mutation endpoint invariant for upsert-link and add-node links.
4. Bounds-check source slots before `_apply_upsert_link`.
5. Remove synthetic input fabrication for unknown target names.
   - Legitimate dynamic inputs require an explicit node/schema contract.
6. Define ONE shared, concrete dynamic-port contract covering the verified node families (count-driven: `ImageConcatMulti` `image_N`, `LTXVImgToVideoInplaceKJ` `num_images.*`, `SimpleCalculator` `input_N`, `LTXVAddGuide` `guide_N`, `SimpleCalculatorKJ` payload vars, `in_N` fixed slots; helpers/proxies: `Reroute`, `GetNode`, `SetNode`, `PrimitiveNode`; dynamic `INPUT_TYPES` custom nodes) — a single predicate used by resolution, mutation, and projection (not a duplicated list at three sites). A port is valid iff present in `node["outputs"]`/`["inputs"]`, or the class matches the dynamic contract AND the schema-fallback slot is bounds-verified before link write.
7. Materialize declared ports during node construction, not opportunistically during link application (materialize-then-validate: build schema input sockets into `inputs` at `ui.py:1325` symmetric with outputs, then keep write-time bounds checks but emit diagnostics instead of silent returns at `apply_links.py:303/314`).
8. Resolve projection ports by canonical name with a validated index fallback.
9. Return typed pre-apply diagnostics instead of creating malformed links and failing during projection.

### Acceptance

- Malformed endpoints fail before mutation and roll back cleanly.
- No undeclared synthetic ports are created.
- Valid named links project correctly despite serialized ordering differences.
- Resolver, mutation, and projection share one endpoint invariant.
- C8/C9 mechanism regressions and relevant porting/edit suites pass.
- No scenario recovery count is claimed without restored run artifacts.

### Oracle checkpoint

Reject redundant defensive layers or any prompt-based workaround. Confirm one coherent invariant covers resolution, mutation, and projection.

---

## B09 — Reproducible final gate and report

### Tasks

1. Preflight required ignored data:
   - `external_workflows/` is mandatory for the canonical run;
   - historical `out/agentic/` is mandatory only for historical comparison and flaky-ID claims.
2. Emit:
   - the authoritative 100-scenario ID/file/SHA manifest;
   - source-workflow per-file hashes and `primary_source`;
   - one aggregate corpus digest;
   - commit and configuration digests.
3. Extend the B02 preservation summary or make B09 preflight the sole corpus-hash owner. Do not maintain two hash systems.
4. Embed commit, selection, configuration, and corpus digests in `run_summary.json`.
5. Cite report evidence by stable scenario ID and SHA, never checkout-relative artifact paths.
6. Run deterministic gates:
   - focused G0R/B01/D13/B04/B03/B05/B06/B07/B08 tests;
   - complete non-GPU suite;
   - B02/elegance preservation suite.
7. Run one canonical 100-scenario lane with explicit transport, profile, models, concurrency, timeout, and exactly one typed-empty infrastructure retry.
8. Report:
   - suite first-attempt and eventual rates over 100;
   - semantic-product rates over 98, excluding the two health controls;
   - the frozen infra-adjusted semantic rate;
   - health-control results separately;
   - refusal pass/fail/undetermined;
   - provenance and UI coverage;
   - matched versus D13-revised subsets;
   - remaining Class C/D ceiling.
9. Once comparable prior artifacts are restored, choose at most 5–10 scenarios with final-verdict flip rate `0.25–0.75`. Repeat only those until each has three comparable observations including B09. Exclude repeats from headline arithmetic.
10. If prior artifacts remain absent, name no flaky scenarios and make no regression-versus-variance claim.
11. Correct documentation drift:
   - update the complete-picture status/table and G0 verdict;
   - add supersession banners to historical sections;
   - mark the canonical-graph elegance plan landed;
   - remove stale “missing rich ingest” claims from the improvement document;
   - verify commit/work mapping before citing `192d4b8f` or `0f515870`.

### Acceptance

- All deterministic suites pass.
- The corpus and manifest preflight passes before model calls.
- The canonical lane completes exactly 100 manifest-selected scenarios.
- Report arithmetic reproduces from persisted artifacts.
- Product rates exclude health controls.
- Historical comparisons are made only from portable, hashed evidence.
- Flaky scenarios are reported as inconclusive/variance, not pass or fail.
- Documentation no longer describes landed work as in flight.
- The cumulative oracle verdict is `PASS`.

### Oracle checkpoint

Perform cumulative diff review, reproduce report arithmetic, verify manifests/provenance, and issue final `PASS` only after all earlier checkpoints remain satisfied.

# 2. New areas to explore

1. **Add-node port materialization:** confirm all declared ports exist before link resolution.
2. **Abort-event semantics:** determine whether the telemetry sink can buffer events or needs an explicit aborted-attempt record.
3. **Pinned edge semantics:** verify muted/bypassed broadcast helpers, duplicate Set names, and named-versus-indexed multi-output mappings.
4. **Artifact lineage:** recover the exact external corpus and historical run directories, then verify their commit/config ancestry.
5. **Flaky-set derivation:** compute scenario-level flips only after comparable historical artifacts are available.
6. **Documentation commit mapping:** establish which commit resolved the previously cited 16 regressions before documenting it.

# 3. Open questions / potential issues

1. Where will the ignored `external_workflows/` corpus be provisioned for D13 and B09?
2. Are authoritative historical `out/agentic/` runs available? Without them, historical re-binning, exact C8 recovery, and flaky-ID selection remain unavailable.
3. Which transport is canonical? The plan retains OpenRouter pending B07 evidence.
4. Does the infra-adjusted denominator exclude only final typed persistent-empty failures? This policy must be frozen before B09.
5. Can telemetry events be buffered transactionally, or must rollback emit compensating abort records?
6. Which model judges semantic non-edit answers, and what availability threshold makes a lane reportable rather than broadly `undetermined`?
7. Do the three mislabeled edits become satisfiable after B04/B08, or must any be rewritten or replaced?

codex
Initial scope evidence is already worth flagging for reconciliation: the commit range has 18 files, not 14, because it also adds two B01 briefs and a 10,215-line checkpoint transcript. The 14 implementation/test files match the executor summary, and `git diff --check` is clean. I’m now tracing whether those orchestration artifacts are acceptable B01 scope or an unintended commit payload.
exec
/bin/zsh -lc 'rg -n "Attempt|attempt_evidence|model_attempt|Failure|failure_kind|empty_response|malformed|non_json|missing_required|capacity|unknown|fresh.transport|zero.*token|completion_tokens" vibecomfy tests/live_agentic_harness tests/test_agent_runtime_adapter.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 104ms:
tests/test_runtime_worker_retry.py:3:Only a canonical ``empty_response`` attempt with observed zero completion
tests/test_runtime_worker_retry.py:5:and malformed non-empty content surface without retry.
tests/test_runtime_worker_retry.py:52:    *, outcome: str, failure_type: str | None = None, completion_tokens: int = 1
tests/test_runtime_worker_retry.py:65:        "finish_reason": "stop" if outcome == "success" else "unknown",
tests/test_runtime_worker_retry.py:68:            "completion_tokens": completion_tokens,
tests/test_runtime_worker_retry.py:69:            "total_tokens": 10 + completion_tokens,
tests/test_runtime_worker_retry.py:82:    assert raised.value.model_attempts[0]["failure_type"] == "timeout"  # type: ignore[attr-defined]
tests/test_runtime_worker_retry.py:111:        "model_attempts": [_attempt(outcome="failure", failure_type="provider_failure")],
tests/test_runtime_worker_retry.py:121:def test_typed_empty_zero_token_response_retries_on_fresh_transport(
tests/test_runtime_worker_retry.py:127:        "model_attempts": [
tests/test_runtime_worker_retry.py:130:                failure_type="empty_response",
tests/test_runtime_worker_retry.py:131:                completion_tokens=0,
tests/test_runtime_worker_retry.py:137:        "model_attempts": [_attempt(outcome="success")],
tests/test_runtime_worker_retry.py:144:    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]
tests/test_runtime_worker_retry.py:145:    assert result["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_runtime_worker_retry.py:146:    assert "raw_response_preview" not in result["model_attempts"][1]
tests/test_runtime_worker_retry.py:149:def test_typed_empty_with_nonzero_tokens_is_not_retried(
tests/test_runtime_worker_retry.py:155:        "model_attempts": [
tests/test_runtime_worker_retry.py:156:            _attempt(outcome="failure", failure_type="empty_response", completion_tokens=2)
tests/test_runtime_worker_retry.py:163:    assert result["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_runtime_worker_retry.py:171:        outcome="failure", failure_type="empty_response", completion_tokens=0
tests/test_runtime_worker_retry.py:174:    first = {"error": "empty", "model_attempts": [unavailable]}
tests/test_runtime_worker_retry.py:179:    assert result["model_attempts"][0]["token_usage"]["completion_tokens"] == "unknown"
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
tests/test_headless_agent_artifacts.py:328:                        "completion_tokens": 4,
tests/test_headless_agent_artifacts.py:343:                    "provider": "unknown",
tests/test_headless_agent_artifacts.py:344:                    "transport": "unknown",
tests/test_headless_agent_artifacts.py:345:                    "endpoint": "unknown",
tests/test_headless_agent_artifacts.py:346:                    "finish_reason": "unknown",
tests/test_headless_agent_artifacts.py:363:    assert "model_attempts.json" in manifest["manifest"]
tests/test_headless_agent_artifacts.py:364:    assert manifest["optional_model_artifacts"]["model_attempts.json"] is True
tests/test_headless_agent_artifacts.py:365:    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
tests/test_headless_agent_artifacts.py:370:    assert attempts[1]["provider"] == "unknown"
tests/test_executor_flows.py:1349:            failure_kind="provider_error",
tests/test_executor_flows.py:1644:        assert result.failure_kind is not None
tests/test_executor_flows.py:1693:# ── Failure handling smoke tests ─────────────────────────────────────────────
tests/test_executor_flows.py:1696:class TestExecutorFailureHandling:
tests/test_executor_flows.py:1713:        assert result.failure_kind == "ProviderError"
tests/test_executor_flows.py:1717:    def test_classify_failure_persists_only_canonical_model_attempts(
tests/test_executor_flows.py:1726:            "failure_type": "malformed_json",
tests/test_executor_flows.py:1736:                "completion_tokens": 2,
tests/test_executor_flows.py:1742:        error.model_attempts = [attempt]  # type: ignore[attr-defined]
tests/test_executor_flows.py:1744:        error.completion_tokens = 999  # type: ignore[attr-defined]
tests/test_executor_flows.py:1750:        assert executor_report["model_attempts"] == [attempt]
tests/test_executor_flows.py:1770:        assert result.failure_kind == "ProviderError"
tests/test_executor_flows.py:3654:        assert "missing models, unknown custom nodes" in system
tests/test_live_agentic_runner_persistence.py:24:        "model_attempts": [],
tests/test_live_agentic_runner_persistence.py:28:def _failed_attempt(failure_type: str, *, completion_tokens: int = 0) -> dict:
tests/test_live_agentic_runner_persistence.py:40:        "finish_reason": "unknown",
tests/test_live_agentic_runner_persistence.py:43:            "completion_tokens": completion_tokens,
tests/test_live_agentic_runner_persistence.py:44:            "total_tokens": 10 + completion_tokens,
tests/test_live_agentic_runner_persistence.py:139:def test_runner_types_provider_capacity_without_retry(
tests/test_live_agentic_runner_persistence.py:145:    scenario_path = scenarios_dir / "provider-capacity.json"
tests/test_live_agentic_runner_persistence.py:147:        json.dumps({"id": "provider-capacity", "query": "do it"}),
tests/test_live_agentic_runner_persistence.py:158:        output_dir = tmp_path / "out" / tag / "provider-capacity"
tests/test_live_agentic_runner_persistence.py:160:            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
tests/test_live_agentic_runner_persistence.py:169:                    "model_attempts": [_failed_attempt("provider_failure")],
tests/test_live_agentic_runner_persistence.py:191:            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
tests/test_live_agentic_runner_persistence.py:213:    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
tests/test_live_agentic_runner_persistence.py:218:def test_runner_retries_only_typed_empty_zero_token_attempt(
tests/test_live_agentic_runner_persistence.py:237:            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
tests/test_live_agentic_runner_persistence.py:254:    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:255:    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_live_agentic_runner_persistence.py:259:def test_runner_keeps_malformed_nonempty_as_product_failure(
tests/test_live_agentic_runner_persistence.py:265:    scenario_path = scenarios_dir / "malformed.json"
tests/test_live_agentic_runner_persistence.py:266:    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
tests/test_live_agentic_runner_persistence.py:274:        payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
tests/test_live_agentic_runner_persistence.py:275:        payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
tests/test_live_agentic_runner_persistence.py:277:        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
tests/test_live_agentic_runner_persistence.py:298:def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
tests/test_live_agentic_runner_persistence.py:317:                "model_attempts": [_failed_attempt("provider_failure")],
tests/test_live_agentic_runner_persistence.py:342:    assert scenario["failure_class"] == "infra_provider_capacity"
tests/test_executor_contracts.py:3:Covers valid classify/reply JSON, malformed JSON, optional graph handling,
tests/test_executor_contracts.py:30:    ModelAttemptEvidence,
tests/test_executor_contracts.py:329:    def test_unknown_explicit_route_fails_closed_to_clarify(self) -> None:
tests/test_executor_contracts.py:638:class TestModelAttemptEvidence:
tests/test_executor_contracts.py:639:    def test_preserves_requested_and_resolved_model_and_unknown_non_hermes_fields(self) -> None:
tests/test_executor_contracts.py:640:        payload = ModelAttemptEvidence(
tests/test_executor_contracts.py:657:        assert payload["provider"] == "unknown"
tests/test_executor_contracts.py:658:        assert payload["transport"] == "unknown"
tests/test_executor_contracts.py:659:        assert payload["endpoint"] == "unknown"
tests/test_executor_contracts.py:660:        assert payload["finish_reason"] == "unknown"
tests/test_executor_contracts.py:662:            "prompt_tokens": "unknown",
tests/test_executor_contracts.py:663:            "completion_tokens": "unknown",
tests/test_executor_contracts.py:664:            "total_tokens": "unknown",
tests/test_executor_contracts.py:706:        attempt = ModelAttemptEvidence(
tests/test_executor_contracts.py:709:            failure_type="malformed_json",
tests/test_executor_contracts.py:711:        report = Report(model_attempts=(attempt,))
tests/test_executor_contracts.py:715:        assert payload["model_attempts"] == [attempt]
tests/test_executor_contracts.py:769:            "unknown_route",
tests/test_executor_contracts.py:782:    def test_unknown_no_candidate_reason_fails_closed(self) -> None:
tests/test_executor_contracts.py:803:    def test_unknown_public_route_fails_closed_to_respond(self) -> None:
tests/test_executor_contracts.py:871:        assert r.failure_kind == "ProviderError"
tests/test_executor_contracts.py:894:        assert "failure_kind" not in d
tests/test_executor_contracts.py:1027:        assert d["failure_kind"] == "TimeoutError"
tests/test_executor_contracts.py:1319:    def test_malformed_json_raises(self) -> None:
tests/test_executor_contracts.py:1403:    def test_parse_unknown_explicit_route_serializes_clarify(self) -> None:
tests/test_executor_contracts.py:1409:            "plan_summary": "unknown route",
tests/test_executor_contracts.py:1653:        raw = '{"unknown": "value"}'
tests/test_executor_contracts.py:1662:    def test_malformed_json_raises(self) -> None:
tests/test_executor_contracts.py:2112:        assert d["failure_kind"] == "ProviderError"
tests/test_executor_contracts.py:3630:        assert gf.missing_required_inputs == ()
tests/test_executor_contracts.py:3631:        assert gf.unknown_class_types == ()
tests/test_executor_contracts.py:3646:        assert d["missing_required_inputs"] == []
tests/test_executor_contracts.py:3647:        assert d["unknown_class_types"] == []
tests/test_executor_contracts.py:3665:            missing_required_inputs=(
tests/test_executor_contracts.py:3668:            unknown_class_types=("BogusNode",),
tests/test_executor_contracts.py:3682:        assert len(d["missing_required_inputs"]) == 1
tests/test_executor_contracts.py:3683:        assert d["missing_required_inputs"][0]["missing_input"] == "model"
tests/test_executor_contracts.py:3684:        assert d["unknown_class_types"] == ["BogusNode"]
tests/test_executor_contracts.py:3703:    def test_has_blockers_true_with_missing_required_inputs(self) -> None:
tests/test_executor_contracts.py:3704:        gf = GraphFacts(missing_required_inputs=({"node": "1", "missing": "model"},))
tests/test_executor_contracts.py:3707:    def test_has_blockers_true_with_unknown_class_types(self) -> None:
tests/test_executor_contracts.py:3708:        gf = GraphFacts(unknown_class_types=("UnknownNode",))
tests/test_executor_contracts.py:3740:            missing_required_inputs=(
tests/test_executor_contracts.py:3743:            unknown_class_types=("CustomNode",),
tests/test_executor_contracts.py:3748:        assert len(gf.missing_required_inputs) == 1
tests/test_executor_contracts.py:3749:        assert gf.unknown_class_types == ("CustomNode",)
tests/test_executor_contracts.py:3772:            missing_required_inputs=(),
tests/test_executor_contracts.py:3773:            unknown_class_types=(),
tests/test_executor_contracts.py:3786:        # that GraphFacts carries (socket_type_mismatches, missing_required_inputs,
tests/test_executor_contracts.py:3787:        # unknown_class_types from topology; missing_models, missing_node_packs,
tests/test_executor_contracts.py:3790:        assert gf.missing_required_inputs == ()
tests/test_executor_contracts.py:3791:        assert gf.unknown_class_types == ()
tests/test_agent_runtime_adapter.py:58:def test_unsupported_route_plumbs_unknown_provenance_end_to_end(
tests/test_agent_runtime_adapter.py:63:    assert descriptor.normalized_route == "unknown"
tests/test_agent_runtime_adapter.py:64:    assert agent_provider._runtime_dispatch_route(descriptor, descriptor.normalized_route) == "unknown"
tests/test_agent_runtime_adapter.py:78:    attempt = worker_result["model_attempts"][0]
tests/test_agent_runtime_adapter.py:80:    assert attempt["resolved_model"] == "unknown"
tests/test_agent_runtime_adapter.py:81:    assert attempt["adapter"] == "unknown"
tests/test_agent_runtime_adapter.py:82:    assert attempt["provider"] == "unknown"
tests/test_agent_runtime_adapter.py:83:    assert attempt["transport"] == "unknown"
tests/test_agent_runtime_adapter.py:84:    assert attempt["endpoint"] == "unknown"
tests/test_agent_runtime_adapter.py:86:    assert readiness["route"] == "unknown"
tests/test_agent_runtime_adapter.py:87:    assert readiness["model"] == "unknown"
tests/test_agent_runtime_adapter.py:437:        (ValueError("empty"), "", "empty_response"),
tests/test_agent_runtime_adapter.py:438:        (json.JSONDecodeError("bad", "{bad", 1), "{bad", "malformed_json"),
tests/test_agent_runtime_adapter.py:439:        (json.JSONDecodeError("bad", "plain prose", 0), "plain prose", "non_json_content"),
tests/test_agent_runtime_adapter.py:440:        (ValueError("must include field reply"), '{"other":"x"}', "missing_required_fields"),
tests/test_agent_runtime_adapter.py:442:        (RuntimeError("capacity"), None, "provider_failure"),
tests/test_agent_runtime_adapter.py:450:    assert worker._model_attempt_failure_type(exc, raw) == expected
tests/test_agent_runtime_adapter.py:467:            "completion_tokens": 0,
tests/test_agent_runtime_adapter.py:472:    unavailable = worker._model_attempt(
tests/test_agent_runtime_adapter.py:477:        failure_type="empty_response",
tests/test_agent_runtime_adapter.py:479:    observed = worker._model_attempt(
tests/test_agent_runtime_adapter.py:484:        failure_type="empty_response",
tests/test_agent_runtime_adapter.py:487:    assert unavailable["token_usage"]["completion_tokens"] == "unknown"
tests/test_agent_runtime_adapter.py:488:    assert observed["token_usage"]["completion_tokens"] == 0
tests/test_agent_runtime_adapter.py:506:            "completion_tokens": 3,
tests/test_agent_runtime_adapter.py:519:        base = {"model_attempts": [attempt], "deepseek_usage": attempt["token_usage"]}
tests/test_agent_runtime_adapter.py:539:        assert result["model_attempts"] == [attempt]
tests/test_agent_runtime_adapter.py:548:            "model_attempts": [attempt],
tests/test_agent_runtime_adapter.py:556:    assert result.audit_metadata["model_attempts"] == [attempt]
tests/test_agent_runtime_adapter.py:570:            "completion_tokens": 0,
tests/test_agent_runtime_adapter.py:582:                return {"content": "", "model_attempts": [first_a, first_b]}
tests/test_agent_runtime_adapter.py:585:                "model_attempts": [second],
tests/test_agent_runtime_adapter.py:597:    attempts = result.audit_metadata["model_attempts"]
tests/test_agent_runtime_adapter.py:600:    assert attempts[1]["failure_type"] == "empty_response"
tests/test_agent_runtime_adapter.py:618:        return {"content": content, "json": json.loads(content), "model_attempts": [attempt]}
tests/test_agent_runtime_adapter.py:621:    token = runtime.begin_model_attempt_capture()
tests/test_agent_runtime_adapter.py:630:        attempts = runtime.snapshot_model_attempt_capture()
tests/test_agent_runtime_adapter.py:632:        runtime.end_model_attempt_capture(token)
tests/live_agentic_harness/adapter.py:152:        "model_attempts": result.response.get("model_attempts", []),
tests/live_agentic_harness/runner.py:140:        "retryable_infra": failure_class == "infra_empty_response",
tests/live_agentic_harness/runner.py:189:        "model_attempts": summary.get("model_attempts", []),
tests/live_agentic_harness/runner.py:193:def _latest_failed_model_attempt(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
tests/live_agentic_harness/runner.py:194:    attempts = summary.get("model_attempts")
tests/live_agentic_harness/runner.py:203:def _summary_completion_tokens(summary: dict[str, Any]) -> int | None:
tests/live_agentic_harness/runner.py:207:    level — the executor result's usage dict.  ``completion_tokens == 0`` is the
tests/live_agentic_harness/runner.py:211:    attempt = _latest_failed_model_attempt(summary)
tests/live_agentic_harness/runner.py:215:    value = usage.get("completion_tokens")
tests/live_agentic_harness/runner.py:223:    attempt = _latest_failed_model_attempt(summary)
tests/live_agentic_harness/runner.py:227:    if failure_type == "empty_response" and _summary_completion_tokens(summary) == 0:
tests/live_agentic_harness/runner.py:228:        return "infra_empty_response"
tests/live_agentic_harness/runner.py:232:        return "infra_provider_capacity"
tests/live_agentic_harness/runner.py:239:    summary["retryable_infra"] = failure_class == "infra_empty_response"
tests/live_agentic_harness/runner.py:269:        summary.get("failure_class") == "infra_empty_response"
tests/live_agentic_harness/runner.py:271:        and _summary_completion_tokens(summary) == 0
tests/live_agentic_harness/failure_analysis.py:1:"""Failure-analysis helpers for live agentic harness runs.
tests/live_agentic_harness/failure_analysis.py:39:    "unknown_needs_human",
tests/live_agentic_harness/failure_analysis.py:150:    return f"""# Live Agentic Failure Analysis: {failed.scenario_id}
tests/live_agentic_harness/failure_analysis.py:406:    return f"""# Aggregate Live Agentic Failure Recommendations
tests/live_agentic_harness/failure_analysis.py:429:## Failure Categories
tests/live_agentic_harness/failure_analysis.py:432:## Per-Failure Primary Cause
tests/live_agentic_harness/assessor.py:40:# Soft capacity warnings: surfaced so humans see them, but not treated as hard
tests/live_agentic_harness/assessor.py:597:                        "one or both effective values were unknown."
tests/live_agentic_harness/assessor.py:698:            # change_details.landed_operation_count.  Missing, malformed, or
vibecomfy/schema/extract.py:170:# to dynamic inputs. Failures are contained to the subprocess (non-zero exit ->
vibecomfy/registry/ready.py:166:    source_mode = "unknown"
vibecomfy/registry/ready.py:269:        source_mode = "unknown"
vibecomfy/schema/validate.py:53:#: Known-lying custom-node schemas that may suppress only ``unknown_input`` and
vibecomfy/schema/validate.py:59:#: ``unknown_class_type`` gating without triggering ``unknown_input`` cascade
vibecomfy/schema/validate.py:129:                    "unknown_class_type",
vibecomfy/schema/validate.py:155:                        "missing_required_input",
vibecomfy/schema/validate.py:172:                not _issue_suppressed(class_type, "unknown_input")
vibecomfy/schema/validate.py:177:                        "unknown_input",
vibecomfy/schema/validate.py:178:                        f"Node {node_id} ({class_type}) has unknown input {name}.",
vibecomfy/schema/validate.py:288:            # unknown and skip the output-index bounds check rather than emit a
vibecomfy/schema/validate.py:362:    """Drop schema-unknown payload keys and coerce equivalent choice strings.
vibecomfy/schema/validate.py:759:    return code == "unknown_input" or code.startswith("value_")
vibecomfy/schema/call_validation.py:51:            "unknown_class_type",
vibecomfy/schema/call_validation.py:66:                    "missing_required_input",
vibecomfy/schema/call_validation.py:76:                "unknown_input",
vibecomfy/schema/call_validation.py:77:                f"{class_type} has unknown input {name}.",
vibecomfy/workflow.py:59:    source_type: str = "unknown"
vibecomfy/workflow.py:219:        is unknown so callers cannot silently confirm a non-existent node.
vibecomfy/workflow.py:369:            raise ValueError(self._unknown_input_message(name))
vibecomfy/workflow.py:405:    def _unknown_input_message(self, name: str) -> str:
vibecomfy/workflow.py:581:                f"{operation}: malformed source ref {ref!r}; expected 'node_id' or 'node_id.output_slot'"
vibecomfy/workflow.py:591:            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
vibecomfy/workflow.py:594:            raise ValueError(f"{operation}: malformed target ref {ref!r}; expected 'node_id.input_name'")
vibecomfy/registry/models_loader.py:186:    raise KeyError(f"unknown model id: {model_id}")
vibecomfy/registry/models_loader.py:206:    entry_id = _required_str(raw, "id", "<unknown>")
vibecomfy/registry/models_loader.py:321:                raise ValueError(f"{entry.id}: unknown tag {tag!r}")
vibecomfy/registry/models_loader.py:339:        f"{registry_path}: {entry_id}: unknown target.node_pack {raw_name!r}; "
vibecomfy/registry/models_loader.py:499:        raise KeyError(f"unknown model id(s): {', '.join(missing)}")
vibecomfy/runtime/ensure_env.py:29:class EnsureFailure:
vibecomfy/runtime/ensure_env.py:84:    failures: tuple[EnsureFailure, ...] = ()
vibecomfy/runtime/ensure_env.py:153:    failures: list[EnsureFailure] = []
vibecomfy/runtime/ensure_env.py:162:                EnsureFailure(
vibecomfy/runtime/ensure_env.py:173:            EnsureFailure(
vibecomfy/runtime/ensure_env.py:200:                EnsureFailure(
vibecomfy/runtime/ensure_env.py:287:                EnsureFailure(
vibecomfy/runtime/ensure_env.py:310:                        EnsureFailure(
vibecomfy/runtime/ensure_env.py:319:                    EnsureFailure(
vibecomfy/runtime/ensure_env.py:342:                raise _HandledEnsureFailure()
vibecomfy/runtime/ensure_env.py:383:        except _HandledEnsureFailure:
vibecomfy/runtime/ensure_env.py:387:                EnsureFailure(
vibecomfy/runtime/ensure_env.py:485:) -> tuple[CustomNodePack | None, PackRef | None, list[EnsureWarning], list[EnsureFailure]]:
vibecomfy/runtime/ensure_env.py:487:    failures: list[EnsureFailure] = []
vibecomfy/runtime/ensure_env.py:548:def _has_blocking_preinstall_failures(failures: Sequence[EnsureFailure]) -> bool:
vibecomfy/runtime/ensure_env.py:559:) -> tuple[dict[str, CustomNodePack], dict[str, PackRef], list[EnsureWarning], list[EnsureFailure]]:
vibecomfy/runtime/ensure_env.py:563:    failures: list[EnsureFailure] = []
vibecomfy/runtime/ensure_env.py:773:class _HandledEnsureFailure(Exception):
vibecomfy/runtime/ensure_env.py:783:) -> tuple[dict[str, dict[str, dict[str, Any]]], list[EnsureFailure]]:
vibecomfy/runtime/ensure_env.py:786:            EnsureFailure(
vibecomfy/runtime/ensure_env.py:797:    failures: list[EnsureFailure] = []
vibecomfy/runtime/ensure_env.py:804:                    EnsureFailure(
vibecomfy/runtime/ensure_env.py:942:    "EnsureFailure",
vibecomfy/errors.py:252:class CanonicalParityFailure(ConversionParityError):
vibecomfy/registry/pack_resolver.py:230:    raise PackNotFoundError(f"unknown pack or class: {query}")
vibecomfy/schema/provider.py:37:    provider_name: str = "unknown"
vibecomfy/schema/provider.py:86:    source_provider: str = "unknown"
vibecomfy/schema/provider.py:188:                "passthrough_on_non_json": InputSpec("BOOLEAN", required=False),
vibecomfy/schema/provider.py:640:    Returns `None` for unknown types - never silently falls through to
vibecomfy/schema/provider.py:874:        reason = result.reason or "unknown"
vibecomfy/registry/static_contract.py:57:            "marker": "unknown",
vibecomfy/commands/doctor.py:119:            if issue.code == "unknown_class_type" and issue.detail.get("class_type")
vibecomfy/commands/runpod.py:121:    raise ValueError(f"unknown profile: {args.profile}")
vibecomfy/porting/widgets/aliases.py:333:        return ("schema_provider" if source == "unknown" else source), names
vibecomfy/porting/convert.py:511:                message=f"Strict ready-template candidate could not be validated: {validation.error or 'unknown error'}",
vibecomfy/runtime/eval/plan.py:68:            warnings=[{"code": "unknown_node_id", "message": f"Node {node_key} is not present in compiled API."}],
vibecomfy/porting/widgets/settings_contract.py:39:    """Field kind: ``int``, ``float``, ``string``, ``bool``, ``enum``, or ``unknown``."""
vibecomfy/porting/widgets/settings_contract.py:98:        return "unknown"
vibecomfy/porting/widgets/settings_contract.py:110:    return "unknown"
vibecomfy/porting/widgets/settings_contract.py:195:    kind = "unknown"
vibecomfy/porting/widgets/settings_contract.py:215:            if choices and kind == "unknown":
vibecomfy/testing/_helpers.py:32:    one) and fall back to `"<unknown>"`.
vibecomfy/testing/_helpers.py:45:        return "<unknown>"
vibecomfy/testing/_helpers.py:53:    return "<unknown>"
vibecomfy/porting/layout/reconcile.py:155:            removed_named.append({"uid": uid, "class_type": ct or "unknown"})
vibecomfy/environment_diagnostics.py:25:        warnings.append(f"hardware requires at least {min_vram}GB VRAM; local GPU capacity was not probed offline")
vibecomfy/environment_diagnostics.py:27:        warnings.append(f"hardware recommends {recommended_vram}GB VRAM; local GPU capacity was not probed offline")
vibecomfy/testing/smoke_fixtures.py:279:        parser.error(f"unknown command {args.cmd!r}")
vibecomfy/porting/object_info/consume.py:581:    lookup is offline and deterministic; unknown classes return ``{}``.
vibecomfy/porting/object_info/consume.py:608:    Fails OPEN: an unknown class (absent from both the object_info snapshot and
vibecomfy/porting/object_info/consume.py:611:    a genuinely-unknown node fails CLOSED with a named, actionable error.
vibecomfy/porting/object_info/consume.py:651:    ``"unknown"`` if the metadata file is absent or unreadable.
vibecomfy/porting/object_info/consume.py:657:        return "unknown"
vibecomfy/porting/object_info/consume.py:659:    return str(version) if version else "unknown"
vibecomfy/commands/port/_export.py:40:                lines.append(f"    uid={rn['uid']} class={rn.get('class_type', 'unknown')}")
vibecomfy/commands/port/_export.py:217:    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "unknown"
vibecomfy/porting/resolution.py:348:                "unknown_target",
vibecomfy/porting/resolution.py:354:            "unknown_target",
vibecomfy/porting/resolution.py:452:                "unknown_target",
vibecomfy/porting/resolution.py:467:                "unknown_output_slot",
vibecomfy/porting/resolution.py:527:            "unknown_output_slot",
vibecomfy/porting/resolution.py:544:                "unknown_target",
vibecomfy/porting/resolution.py:553:                "unknown_target_input",
vibecomfy/porting/resolution.py:581:                "unknown_target",
vibecomfy/porting/resolution.py:603:                    "unknown_output_slot",
vibecomfy/porting/resolution.py:681:                    "unknown_output_slot",
vibecomfy/porting/resolution.py:725:                "unknown_target",
vibecomfy/porting/resolution.py:746:                "unknown_target_input",
vibecomfy/porting/manual_repair.py:162:    return "unknown"
vibecomfy/testing/dry_run.py:166:        # in a stricter provider that warns on unknown classes).
vibecomfy/runtime/watchdog.py:488:            err_msg = st.last_error.get("exception_message") or st.last_error.get("exception_type") or "unknown"
vibecomfy/porting/layout/lanes.py:83:                "assign_lanes: unknown from_node=%r in edge; dropping",
vibecomfy/porting/layout/lanes.py:89:                "assign_lanes: unknown to_node=%r in edge; dropping",
vibecomfy/runtime/attempt.py:1:"""Attempt bundle builder — written before every queue boundary.
vibecomfy/demo_factory/oracle.py:223:                reason=f"Candidate failed UI→API conversion: {compile_error or 'unknown error'}",
vibecomfy/comfy_metadata.json:3:  "commit": "unknown",
vibecomfy/comfy_metadata.json:7:  "version": "unknown"
vibecomfy/porting/layout/layering.py:99:            logger.debug("compute_layers: unknown from_node=%r in edge; dropping", edge.from_node)
vibecomfy/porting/layout/layering.py:102:            logger.debug("compute_layers: unknown to_node=%r in edge; dropping", edge.to_node)
vibecomfy/demo_factory/case.py:298:    source: str = "unknown"
vibecomfy/demo_factory/case.py:376:            source=sd.get("source", "unknown"),
vibecomfy/demo_factory/baseline.py:157:            "unknown node",
vibecomfy/demo_factory/baseline.py:158:            "unknown class",
vibecomfy/demo_factory/baseline.py:159:            "unknown type",
vibecomfy/demo_factory/baseline.py:167:        has_unknown_node = any(
vibecomfy/demo_factory/baseline.py:170:        if msgs and not has_unknown_node:
vibecomfy/demo_factory/baseline.py:244:                    "malformed_node_record",
vibecomfy/demo_factory/baseline.py:274:                "malformed_link_collection",
vibecomfy/demo_factory/baseline.py:287:                    "malformed_raw_link",
vibecomfy/demo_factory/baseline.py:289:                    message=f"Raw link {index} is malformed.",
vibecomfy/demo_factory/baseline.py:510:def _credible_missing_required(
vibecomfy/demo_factory/baseline.py:590:_UNRESOLVED_CODES = frozenset({"unresolved_runtime_class", "unknown_class_type"})
vibecomfy/demo_factory/baseline.py:604:        "unknown_input",
vibecomfy/demo_factory/baseline.py:765:        if code == "missing_required_input":
vibecomfy/demo_factory/baseline.py:766:            if _credible_missing_required(diag, nodes):
vibecomfy/commands/port/_convert.py:129:                "failed" if result.validation and result.validation.parity_ok is False else "unknown"
vibecomfy/commands/port/_convert.py:214:            "failed" if result.validation and result.validation.parity_ok is False else ("unknown" if result.validation else "no-validation")
vibecomfy/demo_factory/transcript.py:63:        If JSON files are malformed or missing required fields.
vibecomfy/ingest/summarize.py:270:    return {"error": "unknown workflow format"}
vibecomfy/demo_factory/run_campaign.py:593:        raise ValueError(f"unknown or ambiguous multinode feature_key: {feature_key!r}")
vibecomfy/demo_factory/run_campaign.py:811:    emission produced malformed slots the apply-validator misreads.
vibecomfy/demo_factory/run_campaign.py:1246:    bug_type = str(spec.bug.get("edit_type") or "unknown")
vibecomfy/demo_factory/run_campaign.py:1392:        print(f"  Result: {result.get('verdict', 'unknown')}")
vibecomfy/demo_factory/run_campaign.py:1400:        print(f"  Result: {result.get('verdict', 'unknown')}")
vibecomfy/demo_factory/run_campaign.py:1409:        print(f"  Result: {result.get('verdict', 'unknown')}")
vibecomfy/demo_factory/run_campaign.py:1423:        print(f"  Result: {result.get('verdict', 'unknown')}")
vibecomfy/demo_factory/predicates.py:299:            return False, "graph contains a malformed link"
vibecomfy/demo_factory/predicates.py:372:        raise ValueError(f"unknown additive grading mode: {mode!r}")
vibecomfy/demo_factory/predicates.py:478:        raise ValueError(f"unknown additive grading mode: {additive_mode!r}")
vibecomfy/demo_factory/predicates.py:652:    node whose fresh id is unknown), return the ids of ALL nodes of that type.
vibecomfy/demo_factory/fixer.py:190:    status = summary.get("status", "unknown")
vibecomfy/porting/readability_inventory.py:50:    marker: str  # "generated", "manual", "reference", "authored", "unknown"
vibecomfy/porting/readability_inventory.py:294:    Returns one of: "generated", "manual", "reference", "authored", "unknown".
vibecomfy/porting/readability_inventory.py:321:    return "unknown"
vibecomfy/demo_factory/creative.py:336:            # Skip malformed proposals
vibecomfy/demo_factory/creative.py:337:            print(f"Skipping malformed proposal: {e}")
vibecomfy/node_packs/_install.py:203:            raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack") from exc
vibecomfy/node_packs/_install.py:207:    if pack is None and repo is None: raise ValueError(f"unknown custom node pack {name!r}; pass repo to install an uncatalogued pack")
vibecomfy/node_packs/_install.py:683:    # Attempt to read sentinel payload.
vibecomfy/porting/emit/emit_kwargs.py:1256:                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown kwarg {key!r}; "
vibecomfy/porting/emit/emit_kwargs.py:1299:                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown linked kwarg {to_input!r}; "
vibecomfy/ingest/normalize.py:53:    # malformed; structural shape is established by the rich nodes mapping.
vibecomfy/ingest/normalize.py:65:    return "unknown"
vibecomfy/ingest/normalize.py:147:                if not _has_unknown_widget_inputs(converted):
vibecomfy/ingest/normalize.py:385:def _has_unknown_widget_inputs(api: dict[str, Any]) -> bool:
vibecomfy/ingest/normalize.py:439:    which nodes exist.  Any malformed or mixed entry raises ``ValueError``
vibecomfy/ingest/normalize.py:475:        source_type=str(source_raw.get("source_type", "unknown")),
vibecomfy/ingest/normalize.py:1195:        "provider": getattr(schema, "source_provider", "unknown"),
vibecomfy/ingest/workflow_source.py:11:WorkflowSourceShape = Literal["api", "litegraph", "vibe", "unknown"]
vibecomfy/ingest/workflow_source.py:111:    if shape == "unknown":
vibecomfy/ingest/workflow_source.py:114:            shape="unknown",
vibecomfy/ingest/workflow_source.py:229:    return "unknown"
vibecomfy/ingest/workflow_source.py:269:        shape="unknown",
vibecomfy/comfy_nodes/agent/routes.py:26:    FailureKind,
vibecomfy/comfy_nodes/agent/routes.py:1016:    wire envelope: the v1 ``FailureEnvelope.to_dict()`` payload merged with the
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
vibecomfy/comfy_nodes/agent/routes.py:1765:    """Convert a FailureEnvelope/dataclass result to a plain dict for JSON."""
vibecomfy/comfy_nodes/agent/routes.py:1808:        FailureKind as _FK,
vibecomfy/comfy_nodes/agent/routes.py:2330:                        FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/routes.py:2355:                        FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/ingest/index.py:47:    return "unknown"
vibecomfy/commands/nodes.py:97:        print(f"output_type={output_type or 'unknown'} input_type={input_type or 'unknown'}")
vibecomfy/commands/nodes.py:813:            state = "drift_unknown"
vibecomfy/demo_factory/additive_judge.py:62:  or effect. Do not reject merely because exact golden settings are unknown.
vibecomfy/comfy_nodes/agent/runtime_code.py:111:    passthrough_on_non_json: bool = False,
vibecomfy/comfy_nodes/agent/runtime_code.py:131:            "passthrough_on_non_json": passthrough_on_non_json,
vibecomfy/comfy_nodes/agent/runtime_code.py:193:    resolve to ``"untrusted_source"`` so untagged or malformed dynamic code never
vibecomfy/comfy_nodes/agent/runtime_code.py:470:        raise RuntimeCodeExecutionError("runtime_protocol_non_json", "Runtime code worker emitted non-JSON output.") from exc
vibecomfy/comfy_nodes/agent/runtime_code.py:621:            raise RuntimeError("unknown execution mode " + repr(mode))
vibecomfy/contracts/surface.py:38:    readiness_class = index_row.get("readiness_class") or contract_payload.get("readiness_level") or "unknown"
vibecomfy/contracts/surface.py:50:        "readiness_level": contract_payload.get("readiness_level") or "unknown",
vibecomfy/demo_factory/ledger.py:20:    "| Case | Attempt | Source | Fault family | Inquiry | Baseline | Fault proof | "
vibecomfy/demo_factory/ledger.py:135:            f"- Attempt: {case.attempt}\n",
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:179:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, StageResult, _canonical_delta_ops_envelope_payload, _duration_ms, _edit_lint_enabled, _ensure_canonical_delta_ops, _json_safe, _port_issue_to_dict, write_json_artifact)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:261:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:304:                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:393:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1065:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1120:def _write_unknown_transition_audits(
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1125:    unknown_transitions: tuple[dict[str, Any], ...],
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1129:    for transition in unknown_transitions:
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1135:                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1141:                turn_state="unknown",
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1143:                metadata={"action": "unknown", **transition},
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:1161:    "_write_unknown_transition_audits",
vibecomfy/contracts/RUNTIME_CONTRACT.md:45:1. Runtime contract validates (malformed/schema-less contracts fail before queue).
vibecomfy/commands/workflows.py:617:            f"Error: unknown contract type {contract_type!r}; "
vibecomfy/_compile/_widgets.py:544:    # TODO: schema unknown -- verify against ComfyUI-Easy-Use INPUT_TYPES if
vibecomfy/_compile/_widgets.py:717:    # TODO: schema unknown — MarkdownNote is a UI display node. widget_0 holds
vibecomfy/commands/run.py:173:            print(f"unknown runtime: {args.runtime}", file=sys.stderr)
vibecomfy/comfy_nodes/agent/_frag_research.py:742:                # unknown plain names from workflow metadata are usually labels
vibecomfy/comfy_nodes/agent/_frag_research.py:878:def _hydrate_current_graph_unknown_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
vibecomfy/comfy_nodes/agent/_frag_research.py:1032:     "_hydrate_current_graph_unknown_node_schemas",
vibecomfy/porting/emit/signatures.py:18:READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS = "schema_unknown_kwarg_hidden_by_extras"
vibecomfy/executor/profiles.py:119:            f"Profile contains unknown stages: {sorted(extra)}"
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:2:Failure/success response shaping and batch/dev response contracts (T-039 extraction of the edit_response_contract fragment).
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:26:    failure: FailureEnvelope,
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:41:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, _product_failure_response, ensure_agent_edit_response_contract, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:47:                FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:804:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, TurnOutcome, _stage_audit, build_legacy_agent_edit_v1, derive_apply_eligibility, derive_gates, product_failure_envelope_fields)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:821:    if failure.kind is FailureKind.STALE_STATE_MISMATCH:
vibecomfy/executor/graph_inspection.py:9:mutates it.  Failures are signalled through exceptions so callers can
vibecomfy/contracts/model.py:50:    readiness_level: str = "unknown"
vibecomfy/contracts/model.py:108:    readiness_level = "unknown"
vibecomfy/executor/graph_facts.py:51:    value_source: str = "unknown"
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:72:    if not isinstance(value, Mapping): raise ContractError(f"{entity} must be an object", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:82:    if not isinstance(graph, Mapping): raise ContractError("graph must be an object", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:109:    if not isinstance(link, Mapping): raise ContractError("link must be an object", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:111:    if not isinstance(source, Mapping) or not isinstance(target, Mapping): raise ContractError("link endpoints are required", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:140:            raise ContractError("link must be a stable endpoint object or native six-tuple", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:144:            raise ContractError("native link endpoint cannot be resolved", "malformed_link")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:152:    if not isinstance(name, str) or name not in PROJECTIONS_V1: raise ContractError("Unknown projection version", "unknown_projection_version")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:169:    if not isinstance(raw, Mapping): raise ContractError("widgets_values must be object or list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:179:    if not isinstance(nodes, list): raise ContractError("nodes must be a list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:188:        if not isinstance(links, list): raise ContractError("links must be a list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:191:    if not isinstance(groups, list): raise ContractError("groups must be a list", "malformed_graph")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:739:        raise ContractError("Restoration strategy must be an object", "malformed_restoration_payload")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:742:        raise ContractError("Unknown restoration strategy tag", "unknown_restoration_strategy")
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
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:889:        raise ContractError("compensation must use baseline_snapshot_v1", "unknown_restoration_strategy")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:894:        raise ContractError("compensation ref must be a non-empty string", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:897:        raise ContractError("compensation fence must be an object", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:901:        raise ContractError("compensation fence key set is not closed", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:903:        raise ContractError("compensation generation must be a positive int", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:906:            raise ContractError(f"compensation fence {key} must be non-empty string", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:909:            raise ContractError(f"compensation fence {key} must be hex64", "malformed_restoration_compensation")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:947:    if not isinstance(raw, Mapping) or raw.get("contract_version") not in {CANDIDATE_AUTHORITY_V1, PREPARED_AUTHORITY_V1}: raise ContractError("Unsupported authority version", "unknown_authority_version")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:950:        raise ContractError("Authority receipt contract version must be explicit", "unknown_authority_receipt_version")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:960:    if family not in {"structural", "layout"}: raise ContractError("Unknown operation family", "unknown_operation_family")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:1008:    if raw.get("contract_version") != CANDIDATE_AUTHORITY_V1: raise ContractError("Unsupported candidate authority version", "unknown_authority_version")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:1016:    if raw.get("contract_version") != PREPARED_AUTHORITY_V1: raise ContractError("Unsupported prepared authority version", "unknown_authority_version")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:1051:            raise ContractError("restoration_strategy_compensation may not be null", "malformed_restoration_compensation")
vibecomfy/agent/artifacts.py:31:    "model_attempts.json",
vibecomfy/agent/artifacts.py:114:                # credential in malformed structured text that free-text
vibecomfy/agent/artifacts.py:336:    model_attempts = report.get("model_attempts")
vibecomfy/agent/artifacts.py:337:    if isinstance(model_attempts, (list, tuple)) and model_attempts:
vibecomfy/agent/artifacts.py:339:            output_dir / "model_attempts.json",
vibecomfy/agent/artifacts.py:340:            {"attempts": _redact(model_attempts)},
vibecomfy/agent/artifacts.py:342:        _append_manifest(manifest, "model_attempts.json")
vibecomfy/contracts/ir.py:86:    """Validate and return *code*, raising ValueError for unknown IR contract codes."""
vibecomfy/contracts/ir.py:89:        raise ValueError(f"unknown IR contract code: {code}")
vibecomfy/agent/deepseek_usage.py:16:    "completion_tokens",
vibecomfy/agent/deepseek_usage.py:57:    completion_tokens = normalized["completion_tokens"]
vibecomfy/agent/deepseek_usage.py:60:    if normalized["n_calls"] <= 0 and prompt_tokens <= 0 and completion_tokens <= 0:
vibecomfy/agent/deepseek_usage.py:66:            + (completion_tokens * DEEPSEEK_COMPLETION_USD_PER_1M)
vibecomfy/agent/deepseek_usage.py:71:        + (completion_tokens * DEEPSEEK_COMPLETION_USD_PER_1M)
vibecomfy/commands/runtime.py:45:        print(f"unknown smoke mode: {args.mode}", file=sys.stderr)
vibecomfy/commands/runtime.py:116:            print(f"unknown runtime: {runtime}", file=sys.stderr)
vibecomfy/contracts/intent_nodes.py:9:from vibecomfy.security.agent_generated_loader import ScanFailure, ScanReport, scan_python_source_with_policy
vibecomfy/contracts/intent_nodes.py:279:    passthrough_on_non_json: bool = False
vibecomfy/contracts/intent_nodes.py:291:            "passthrough_on_non_json": self.passthrough_on_non_json,
vibecomfy/contracts/intent_nodes.py:344:        raise ValueError(f"unknown intent node kind: {kind!r}")
vibecomfy/contracts/intent_nodes.py:596:    passthrough_on_non_json = runtime.get("passthrough_on_non_json", False)
vibecomfy/contracts/intent_nodes.py:714:    if not isinstance(passthrough_on_non_json, bool):
vibecomfy/contracts/intent_nodes.py:718:                "runtime.passthrough_on_non_json must be a boolean when present.",
vibecomfy/contracts/intent_nodes.py:721:    elif passthrough_on_non_json:
vibecomfy/contracts/intent_nodes.py:724:                "runtime_non_json_passthrough_unsupported",
vibecomfy/contracts/intent_nodes.py:725:                "Runtime-backed code must reject non-JSON outputs; passthrough_on_non_json must be false.",
vibecomfy/contracts/intent_nodes.py:742:            passthrough_on_non_json=False,
vibecomfy/contracts/intent_nodes.py:773:                ScanFailure(
vibecomfy/contracts/intent_nodes.py:784:                ScanFailure(
vibecomfy/contracts/intent_nodes.py:809:            ScanFailure(
vibecomfy/contracts/intent_nodes.py:811:                message=f"unknown execution mode {mode!r}",
vibecomfy/contracts/intent_nodes.py:860:                ScanFailure(
vibecomfy/contracts/intent_nodes.py:891:                ScanFailure(
vibecomfy/contracts/intent_nodes.py:915:                ScanFailure(
vibecomfy/contracts/intent_nodes.py:938:        self.failures: list[ScanFailure] = []
vibecomfy/contracts/intent_nodes.py:989:            ScanFailure(
vibecomfy/contracts/intent_nodes.py:1003:        self.failures: list[ScanFailure] = []
vibecomfy/contracts/intent_nodes.py:1040:            ScanFailure(
vibecomfy/contracts/intent_nodes.py:1134:                        "runtime_non_json_io",
vibecomfy/contracts/intent_nodes.py:1142:                        "runtime_unknown_io_type",
vibecomfy/porting/emit/emit_ready.py:522:    raw_capability = str(metadata.get("capability") or "unknown")
vibecomfy/porting/emit/emit_ready.py:523:    if raw_capability == "unknown" and output_node_class_type:
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
vibecomfy/commands/schemas.py:86:    identity = f"{result.get('pack_version', result.get('version', 'unknown'))} / {result.get('source_kind', 'unknown')}"
vibecomfy/comfy_nodes/agent/edit.py:105:        "FailureEnvelope",
vibecomfy/comfy_nodes/agent/edit.py:106:        "FailureKind",
vibecomfy/comfy_nodes/agent/edit.py:192:        "_batch_budget_failure_kind",
vibecomfy/comfy_nodes/agent/edit.py:301:        "_hydrate_current_graph_unknown_node_schemas",
vibecomfy/comfy_nodes/agent/edit.py:329:        "_malformed_model_json_detail",
vibecomfy/comfy_nodes/agent/edit.py:411:        "_selected_precedent_unknown_class_feedback",
vibecomfy/comfy_nodes/agent/edit.py:479:        "_write_unknown_transition_audits",
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:27:    from vibecomfy.comfy_nodes.agent.edit import (AgentEditState, FailureKind, PROMPT_MEMORY_MESSAGES, StageResult, _SESSION_ROOT, _StageBlocked, _agent_edit_contract, _build_batch_repl_response, _build_dev_success_response, _canonical_agent_edit_route, _conversation_with_candidate_reference, _default_runtime_schema_provider, _failure_response, _hydrate_execution_plan_from_protocol_notes, _product_failure_response, _record, _run_batch_repl_product_path, _run_delta_dev_path, _run_full_dev_path, _safe_session_id, _stage_audit, _validated_agent_edit_response, _write_turn_chat_artifact, _write_unknown_transition_audits, allocate_turn, classify_failure, failure_envelope, initialize_gates, read_session_chat, record_idempotent_response, write_allocation_failure_audit)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:33:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:43:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:50:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:79:            FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:133:    _write_unknown_transition_audits(
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:137:        unknown_transitions=allocation.unknown_transitions,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:280:                FailureKind.AUDIT_WRITE_FAILURE,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:436:            FailureKind.AUDIT_WRITE_FAILURE,
vibecomfy/porting/cache/object_info/ComfyUI-KJNodes@runpod-snapshot.json:23237:    "description": "Attempt to implement https://github.com/agwmon/self-refine-video, for testing only, MAY NOT WORK AS INTENDED.",
vibecomfy/porting/cache/object_info/ComfyUI-KJNodes@runpod-snapshot.json:24512:    "description": "\n# WORK IN PROGRESS  \nDo not count on this as part of your workflow yet,  \nprobably contains lots of bugs and stability is not  \nguaranteed!!  \n  \n## Graphical editor to create values for various   \n## schedules and/or mask batches.  \n\n**Shift + click** to add control point at end.\n**Ctrl + click** to add control point (subdivide) between two points.  \n**Right click on a point** to delete it.    \nNote that you can't delete from start/end.  \n  \nRight click on canvas for context menu:  \nNEW!:\n- Add new spline\n    - Creates a new spline on same canvas, currently these paths are only outputed  \n      as coordinates.\n- Add single point\n    - Creates a single point that only returns it's current position coords  \n- Delete spline\n    - Deletes the currently selected spline, you can select a spline by clicking on   \n    it's path, or cycle through them with the 'Next spline' -option.  \n\nThese are purely visual options, doesn't affect the output:  \n - Toggle handles visibility\n - Display sample points: display the points to be returned.  \n\n**points_to_sample** value sets the number of samples  \nreturned from the **drawn spline itself**, this is independent from the  \nactual control points, so the interpolation type matters.  \nsampling_method: \n - time: samples along the time axis, used for schedules  \n - path: samples along the path itself, useful for coordinates  \n - controlpoints: samples only the control points themselves  \n\noutput types:\n - mask batch  \n        example compatible nodes: anything that takes masks  \n - list of floats\n        example compatible nodes: IPAdapter weights  \n - pandas series\n        example compatible nodes: anything that takes Fizz'  \n        nodes Batch Value Schedule  \n - torch tensor  \n        example compatible nodes: unknown\n",
vibecomfy/porting/emit/ui.py:695:    unknown_offset = len(position)
vibecomfy/porting/emit/ui.py:699:            position.get(edge.to_input, unknown_offset),
vibecomfy/porting/emit/ui.py:719:    provider = getattr(schema, "source_provider", "unknown")
vibecomfy/porting/emit/ui.py:1223:        properties["_vibecomfy_schema_provider"] = getattr(schema, "source_provider", "unknown")
vibecomfy/porting/emit/ui.py:1379:            str(shape or "unknown"),
vibecomfy/executor/revision_evidence.py:46:        When ``False``, schema-dependent checks (unknown class types,
vibecomfy/executor/revision_evidence.py:165:    # ── unknown class types (schema-backed) ─────────────────────────────
vibecomfy/executor/revision_evidence.py:166:    unknown_class_types: list[str] = []
vibecomfy/executor/revision_evidence.py:170:                unknown_class_types.append(f"node_id={nid}: <no class_type>")
vibecomfy/executor/revision_evidence.py:172:                unknown_class_types.append(f"node_id={nid}: {ct}")
vibecomfy/executor/revision_evidence.py:212:    missing_required_inputs: list[dict[str, Any]] = []
vibecomfy/executor/revision_evidence.py:237:                    missing_required_inputs.append({
vibecomfy/executor/revision_evidence.py:259:    if unknown_class_types:
vibecomfy/executor/revision_evidence.py:261:            f"{len(unknown_class_types)} unknown class type(s)"
vibecomfy/executor/revision_evidence.py:263:    if missing_required_inputs:
vibecomfy/executor/revision_evidence.py:265:            f"{len(missing_required_inputs)} missing required input(s)"
vibecomfy/executor/revision_evidence.py:277:        unknown_class_types=tuple(unknown_class_types),
vibecomfy/executor/revision_evidence.py:278:        missing_required_inputs=tuple(missing_required_inputs),
vibecomfy/executor/revision_evidence.py:386:    # Cross-reference against object_info: flag unknown class types as
vibecomfy/executor/revision_evidence.py:388:    unknown_classes: list[str] = []
vibecomfy/executor/revision_evidence.py:392:                unknown_classes.append(ct)
vibecomfy/executor/revision_evidence.py:399:    missing_node_packs = _dedupe_strings((*missing_node_packs, *unknown_classes))
vibecomfy/executor/revision_evidence.py:491:            candidate_topology.unknown_class_types,
vibecomfy/executor/revision_evidence.py:492:            original_topology.unknown_class_types if original_topology is not None else (),
vibecomfy/executor/revision_evidence.py:495:            candidate_topology.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:496:            original_topology.missing_required_inputs if original_topology is not None else (),
vibecomfy/executor/revision_evidence.py:710:    the class is unknown, or the input is not found.
vibecomfy/executor/revision_evidence.py:746:def schema_backed_unknown_class_types(
vibecomfy/executor/revision_evidence.py:752:    and extracts the ``unknown_class_types`` field.
vibecomfy/executor/revision_evidence.py:757:    return evidence.unknown_class_types
vibecomfy/executor/revision_evidence.py:1341:            if topology.missing_required_inputs:
vibecomfy/executor/revision_evidence.py:1372:                facts.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:1373:                facts.unknown_class_types,
vibecomfy/executor/revision_evidence.py:1395:        missing_required_inputs=facts.missing_required_inputs,
vibecomfy/executor/revision_evidence.py:1396:        unknown_class_types=facts.unknown_class_types,
vibecomfy/executor/revision_evidence.py:1412:    "schema_backed_unknown_class_types",
vibecomfy/executor/contracts.py:37:    "empty_response",
vibecomfy/executor/contracts.py:38:    "malformed_json",
vibecomfy/executor/contracts.py:39:    "non_json_content",
vibecomfy/executor/contracts.py:40:    "missing_required_fields",
vibecomfy/executor/contracts.py:45:_MODEL_ATTEMPT_UNKNOWN = "unknown"
vibecomfy/executor/contracts.py:59:    """Return a credential-free, query-free endpoint or ``"unknown"``.
vibecomfy/executor/contracts.py:109:def _model_attempt_text(value: Any) -> str:
vibecomfy/executor/contracts.py:115:def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
vibecomfy/executor/contracts.py:118:    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
vibecomfy/executor/contracts.py:129:class ModelAttemptEvidence:
vibecomfy/executor/contracts.py:158:        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
vibecomfy/executor/contracts.py:166:            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
vibecomfy/executor/contracts.py:171:            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
vibecomfy/executor/contracts.py:181:    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
vibecomfy/executor/contracts.py:218:def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
vibecomfy/executor/contracts.py:224:        if isinstance(item, ModelAttemptEvidence):
vibecomfy/executor/contracts.py:227:            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
vibecomfy/executor/contracts.py:487:    "unknown_route",
vibecomfy/executor/contracts.py:598:        "executor unknown explicit route failed closed",
vibecomfy/executor/contracts.py:649:    defaults to ``""`` (unknown) when derivation is ambiguous.
vibecomfy/executor/contracts.py:1591:_ALLOWED_FRESHNESS_STATUSES = frozenset({"fresh", "stale", "unknown"})
vibecomfy/executor/contracts.py:1645:    freshness_status: str = "unknown" # "fresh" | "stale" | "unknown"
vibecomfy/executor/contracts.py:1707:            object.__setattr__(self, "freshness_status", "unknown")
vibecomfy/executor/contracts.py:1745:        if self.freshness_status != "unknown":
vibecomfy/executor/contracts.py:1772:    unknown_class_types: tuple[str, ...] = ()
vibecomfy/executor/contracts.py:1773:    missing_required_inputs: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:1785:        object.__setattr__(self, "unknown_class_types", tuple(self.unknown_class_types))
vibecomfy/executor/contracts.py:1786:        object.__setattr__(self, "missing_required_inputs", tuple(
vibecomfy/executor/contracts.py:1789:            for item in self.missing_required_inputs
vibecomfy/executor/contracts.py:1800:            or self.unknown_class_types
vibecomfy/executor/contracts.py:1801:            or self.missing_required_inputs
vibecomfy/executor/contracts.py:1810:            "unknown_class_types": list(self.unknown_class_types),
vibecomfy/executor/contracts.py:1811:            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
vibecomfy/executor/contracts.py:1998:                or self.topology.missing_required_inputs
vibecomfy/executor/contracts.py:2038:    missing_required_inputs: tuple[dict[str, Any], ...] = ()
vibecomfy/executor/contracts.py:2039:    unknown_class_types: tuple[str, ...] = ()
vibecomfy/executor/contracts.py:2058:        object.__setattr__(self, "missing_required_inputs", tuple(
vibecomfy/executor/contracts.py:2061:            for item in self.missing_required_inputs
vibecomfy/executor/contracts.py:2063:        object.__setattr__(self, "unknown_class_types",
vibecomfy/executor/contracts.py:2064:                           tuple(self.unknown_class_types))
vibecomfy/executor/contracts.py:2090:            missing_required_inputs=topology.missing_required_inputs,
vibecomfy/executor/contracts.py:2091:            unknown_class_types=topology.unknown_class_types,
vibecomfy/executor/contracts.py:2103:            or self.missing_required_inputs
vibecomfy/executor/contracts.py:2104:            or self.unknown_class_types
vibecomfy/executor/contracts.py:2116:            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
vibecomfy/executor/contracts.py:2117:            "unknown_class_types": list(self.unknown_class_types),
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
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:111:    _batch_budget_failure_kind: Any  # host: _frag_batch_reports
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:157:    _selected_precedent_unknown_class_feedback: Any  # host: _frag_batch_memory
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:165:    FailureKind: Any  # host: _frag_state
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:253:def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:277:    return "malformed"
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:286:        detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:321:        str(status.get("step_id") or "unknown_step")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:328:        str(condition.get("condition_id") or condition.get("id") or "unknown_condition")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:334:        f"plan_id={getattr(evaluation, 'plan_id', 'unknown')}",
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
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2000:                    issue.code == "unknown_target"
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2146:        selected_precedent_unknown_class_feedback = (
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2147:            deps._selected_precedent_unknown_class_feedback(state, batch_result)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2149:        if selected_precedent_unknown_class_feedback and not deps._batch_candidate_graph_changed(state):
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2151:            turn_record["clarification_message"] = selected_precedent_unknown_class_feedback
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2152:            turn_record["authoring_blocker"] = "selected_precedent_unknown_class"
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2169:        if selected_precedent_unknown_class_feedback and not deps._batch_candidate_graph_changed(state):
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2170:            message_record["authoring_blocker"] = "selected_precedent_unknown_class"
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2171:            message_record["clarification_required"] = selected_precedent_unknown_class_feedback
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2176:        if selected_precedent_unknown_class_feedback and not deps._batch_candidate_graph_changed(state):
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2181:            state.user_message = selected_precedent_unknown_class_feedback
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2187:                    "reason": "selected_precedent_unknown_class",
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2188:                    "message": selected_precedent_unknown_class_feedback,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2196:                    "message": selected_precedent_unknown_class_feedback,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2197:                    "reason": "selected_precedent_unknown_class",
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2223:                    "reason": "selected_precedent_unknown_class",
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2457:                        "failure_kind": deps.FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2615:    failure_kind = deps._batch_budget_failure_kind(state.batch_turns)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2616:    artifixer_report = deps._batch_budget_artifixer_report(state, failure_kind)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2647:                "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2652:                    "budget_classification": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2658:            "failure_kind": failure_kind.value,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2661:            "budget_classification": failure_kind.value,
vibecomfy/porting/refuse.py:97:            "reason": reasons[0] if reasons else "unknown",
vibecomfy/comfy_nodes/agent/authority_receipts.py:309:        # A present envelope is authority evidence.  If it is malformed, never
vibecomfy/comfy_nodes/agent/session.py:18:from .contracts import DiagnosticRecord, FailureEnvelope, FailureKind, TurnContext, failure_envelope
vibecomfy/comfy_nodes/agent/session.py:112:#   candidate, accepted, rejected, unknown, no_candidate
vibecomfy/comfy_nodes/agent/session.py:133:# V2 turns can also transition to unknown (superseded) from any pre-finalized state.
vibecomfy/comfy_nodes/agent/session.py:139:    "unknown",
vibecomfy/comfy_nodes/agent/session.py:187:    "unknown",
vibecomfy/comfy_nodes/agent/session.py:221:    failure: FailureEnvelope
vibecomfy/comfy_nodes/agent/session.py:232:    unknown_transitions: tuple[dict[str, Any], ...] = ()
vibecomfy/comfy_nodes/agent/session.py:256:    failure: FailureEnvelope
vibecomfy/comfy_nodes/agent/session.py:503:        """Attempt to recover a dead-owner or stale-lease lock.
vibecomfy/comfy_nodes/agent/session.py:550:            self._quarantine_lock("malformed_metadata")
vibecomfy/comfy_nodes/agent/session.py:971:        elif lifecycle == "unknown" and life.get("superseded_by_turn_id"):
vibecomfy/comfy_nodes/agent/session.py:1460:        "unknown",
vibecomfy/comfy_nodes/agent/session.py:1489:        "failure_kind",
vibecomfy/comfy_nodes/agent/session.py:1496:    unknown = sorted(str(key) for key in raw if key not in allowed)
vibecomfy/comfy_nodes/agent/session.py:1497:    if unknown:
vibecomfy/comfy_nodes/agent/session.py:1499:            f"compensation contains unsupported fields: {', '.join(unknown)}."
vibecomfy/comfy_nodes/agent/session.py:1511:    for field, limit in (("failure_kind", 128), ("failure_message", 2048)):
vibecomfy/comfy_nodes/agent/session.py:1648:    kind: FailureKind,
vibecomfy/comfy_nodes/agent/session.py:1656:) -> FailureEnvelope:
vibecomfy/comfy_nodes/agent/session.py:1839:        return None, "malformed_candidate_transaction"
vibecomfy/comfy_nodes/agent/session.py:1985:) -> dict[str, Any] | FailureEnvelope:
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
vibecomfy/comfy_nodes/agent/session.py:2242:) -> dict[str, Any] | FailureEnvelope:
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
vibecomfy/comfy_nodes/agent/session.py:2678:                other_record["unknown_at"] = other_record.get("unknown_at") or _now()
vibecomfy/comfy_nodes/agent/session.py:2679:                other_record["unknown_reason"] = "superseded_by_finalize"
vibecomfy/comfy_nodes/agent/session.py:2715:) -> dict[str, Any] | FailureEnvelope:
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
vibecomfy/comfy_nodes/agent/session.py:3841:        unknown_transitions: list[dict[str, Any]] = []
vibecomfy/comfy_nodes/agent/session.py:3847:                superseded_state = "unknown"
vibecomfy/comfy_nodes/agent/session.py:3858:            other_record["unknown_at"] = other_record.get("unknown_at") or _now()
vibecomfy/comfy_nodes/agent/session.py:3859:            other_record["unknown_reason"] = "superseded_by_new_submit"
vibecomfy/comfy_nodes/agent/session.py:3861:            transitioned_at = other_record["unknown_at"]
vibecomfy/comfy_nodes/agent/session.py:3862:            unknown_transitions.append(
vibecomfy/comfy_nodes/agent/session.py:3888:        unknown_transitions=tuple(unknown_transitions),
vibecomfy/comfy_nodes/agent/session.py:4211:) -> dict[str, Any] | FailureEnvelope:
vibecomfy/comfy_nodes/agent/session.py:4251:                        FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4275:                        FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4333:        FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4361:) -> dict[str, Any] | FailureEnvelope | None:
vibecomfy/comfy_nodes/agent/session.py:4375:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/session.py:4406:                    FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4425:                FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4445:                    FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4460:                    FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4538:) -> dict[str, Any] | FailureEnvelope:
vibecomfy/comfy_nodes/agent/session.py:4574:            FailureKind.EDITOR_AHEAD_CONFLICT,
vibecomfy/comfy_nodes/agent/session.py:4625:) -> dict[str, Any] | FailureEnvelope:
vibecomfy/comfy_nodes/agent/session.py:4633:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4642:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4650:            FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:4661:            FailureKind.MISSING_REQUIRED_FIELD,
vibecomfy/comfy_nodes/agent/session.py:4669:            FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/session.py:4710:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/executor/prompts.py:9:Both phases use strict JSON contracts with small parsers so malformed model
vibecomfy/executor/prompts.py:50:    "to the research direction; leave blank if unknown.\n"
vibecomfy/executor/prompts.py:156:    "if the broader graph has missing models, unknown custom nodes, or unrelated "
vibecomfy/executor/prompts.py:213:    "the surrounding workflow has pre-existing missing models or unknown node "
vibecomfy/executor/prompts.py:344:            # Defensively skip any malformed entries (non-dict, missing
vibecomfy/executor/prompts.py:677:                f"reference slice '{selected.get('source_class_type', 'unknown')}', "
vibecomfy/executor/core.py:7:Failures are converted through the existing failure-envelope classification
vibecomfy/executor/core.py:22:    FailureKind,
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
vibecomfy/executor/core.py:462:    type_list = ", ".join(types[:5]) if types else "unknown"
vibecomfy/executor/core.py:535:    Defensively tolerates malformed historical chat artifacts (non-dict
vibecomfy/executor/core.py:909:    used.  Failures produce a :class:`FailureEnvelope`-compatible exception
vibecomfy/executor/core.py:995:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:998:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1005:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1008:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1399:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1406:            FailureKind.VALIDATION_ERROR,
vibecomfy/executor/core.py:1414:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1420:    if result.get("ok") is False or "failure_kind" in result:
vibecomfy/executor/core.py:1421:        fk = result.get("failure_kind", result.get("kind", "ValidationError"))
vibecomfy/executor/core.py:1425:            "failure_kind": fk,
vibecomfy/executor/core.py:1440:            FailureKind(fk) if isinstance(fk, str) and fk in {k.value for k in FailureKind} else FailureKind.VALIDATION_ERROR,
vibecomfy/executor/core.py:1447:                    if key not in {"message", "stage", "failure_kind"}
vibecomfy/executor/core.py:1453:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1523:        "unknown_route",
vibecomfy/executor/core.py:1702:            FailureKind.VALIDATION_ERROR,
vibecomfy/executor/core.py:1710:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1720:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1723:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1730:            failure_kind=failure.kind.value,
vibecomfy/executor/core.py:1733:            model_attempts=_failure_model_attempts(failure),
vibecomfy/executor/core.py:1741:    """Internal exception that carries a pre-built :class:`FailureEnvelope`.
vibecomfy/executor/core.py:1751:        failure_kind: str,
vibecomfy/executor/core.py:1755:        model_attempts: tuple[dict[str, Any], ...] = (),
vibecomfy/executor/core.py:1759:        self.failure_kind = failure_kind
vibecomfy/executor/core.py:1762:        self.model_attempts = coerce_model_attempts(model_attempts)
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
vibecomfy/comfy_nodes/agent/_frag_revision.py:108:        topology.unknown_class_types
vibecomfy/comfy_nodes/agent/_frag_revision.py:109:        or topology.missing_required_inputs
vibecomfy/comfy_nodes/agent/_frag_revision.py:132:        topology.unknown_class_types
vibecomfy/comfy_nodes/agent/_frag_revision.py:133:        or topology.missing_required_inputs
vibecomfy/comfy_nodes/agent/_frag_revision.py:186:            else "pre-existing unknown/custom-node blockers ignored for localized "
vibecomfy/comfy_nodes/agent/_frag_revision.py:208:        unknown_class_types=_subtract_existing_blockers(
vibecomfy/comfy_nodes/agent/_frag_revision.py:209:            candidate_topology.unknown_class_types,
vibecomfy/comfy_nodes/agent/_frag_revision.py:210:            topology.unknown_class_types,
vibecomfy/comfy_nodes/agent/_frag_revision.py:212:        missing_required_inputs=_subtract_existing_blockers(
vibecomfy/comfy_nodes/agent/_frag_revision.py:213:            candidate_topology.missing_required_inputs,
vibecomfy/comfy_nodes/agent/_frag_revision.py:214:            topology.missing_required_inputs,
vibecomfy/comfy_nodes/agent/_frag_revision.py:218:            "pre-existing unknown/custom-node blockers subtracted for localized "
vibecomfy/comfy_nodes/agent/obligation_ledger.py:22:* ``unknown``         — the condition could not be evaluated (fail-closed default).
vibecomfy/comfy_nodes/agent/obligation_ledger.py:58:OBLIGATION_STATUS_UNKNOWN: str = "unknown"
vibecomfy/comfy_nodes/agent/obligation_ledger.py:143:def is_unknown(status: str) -> bool:
vibecomfy/comfy_nodes/agent/obligation_ledger.py:144:    """Return ``True`` when *status* is ``unknown``."""
vibecomfy/comfy_nodes/agent/obligation_ledger.py:317:    def is_unknown(self) -> bool:
vibecomfy/comfy_nodes/agent/obligation_ledger.py:318:        """``True`` when this obligation status is unknown."""
vibecomfy/comfy_nodes/agent/obligation_ledger.py:340:        ``unknown``, ``unsupported``, and ``not_evaluated`` are *never*
vibecomfy/comfy_nodes/agent/obligation_ledger.py:372:        ``unknown`` / ``required``) rather than raising.
vibecomfy/comfy_nodes/agent/obligation_ledger.py:618:    def unknown_obligations(self) -> tuple[Obligation, ...]:
vibecomfy/comfy_nodes/agent/obligation_ledger.py:619:        """Return obligations with status ``unknown``."""
vibecomfy/comfy_nodes/agent/obligation_ledger.py:620:        return tuple(o for o in self.obligations if o.is_unknown)
vibecomfy/comfy_nodes/agent/obligation_ledger.py:636:        ``unknown``, ``unsupported``, ``not_evaluated``, and
vibecomfy/comfy_nodes/agent/obligation_ledger.py:648:        This includes ``unknown``, ``unsupported``, ``not_evaluated``,
vibecomfy/comfy_nodes/agent/obligation_ledger.py:657:    def any_unknown(self) -> bool:
vibecomfy/comfy_nodes/agent/obligation_ledger.py:658:        """``True`` when any obligation has ``unknown`` status."""
vibecomfy/comfy_nodes/agent/obligation_ledger.py:659:        return any(o.is_unknown for o in self.obligations)
vibecomfy/comfy_nodes/agent/obligation_ledger.py:810:    "is_unknown",
vibecomfy/executor/agent_backend.py:29:    ModelAttemptEvidence,
vibecomfy/executor/agent_backend.py:30:    coerce_model_attempts,
vibecomfy/executor/agent_backend.py:78:        if result is not None and getattr(exc, "model_attempts", None) is None:
vibecomfy/executor/agent_backend.py:79:            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:91:        return "empty_response"
vibecomfy/executor/agent_backend.py:99:        return "malformed_json" if "{" in stripped else "non_json_content"
vibecomfy/executor/agent_backend.py:100:    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"
vibecomfy/executor/agent_backend.py:104:    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
vibecomfy/executor/agent_backend.py:106:    record_model_attempts(result.get("model_attempts"))
vibecomfy/executor/agent_backend.py:112:    attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/executor/agent_backend.py:121:    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
vibecomfy/executor/agent_backend.py:123:    result["model_attempts"] = attempts
vibecomfy/executor/agent_backend.py:124:    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt
vibecomfy/executor/agent_backend.py:126:    replace_last_model_attempt(revised)
vibecomfy/comfy_nodes/agent/completion_proofs.py:23:* ``unknown`` — the proof was expected but not available; this is the
vibecomfy/comfy_nodes/agent/completion_proofs.py:37:PROOF_STATE_UNKNOWN: str = "unknown"
vibecomfy/comfy_nodes/agent/completion_proofs.py:100:def is_unknown(state: str) -> bool:
vibecomfy/comfy_nodes/agent/completion_proofs.py:101:    """Return ``True`` when *state* is ``unknown``."""
vibecomfy/comfy_nodes/agent/completion_proofs.py:108:    Missing / ``unknown`` / ``not_run`` / ``fail`` are *never* success.
vibecomfy/comfy_nodes/agent/completion_proofs.py:121:    or ``unknown``.  Missing or absent proof is represented as
vibecomfy/comfy_nodes/agent/completion_proofs.py:122:    ``unknown`` — the fail-closed default.
vibecomfy/comfy_nodes/agent/completion_proofs.py:212:    def any_unknown(self) -> bool:
vibecomfy/comfy_nodes/agent/completion_proofs.py:213:        """True when any domain is ``unknown`` (including missing)."""
vibecomfy/comfy_nodes/agent/completion_proofs.py:257:        When *_coerce* is ``True`` (default), unknown or absent state
vibecomfy/comfy_nodes/agent/completion_proofs.py:258:        values are normalized to ``unknown`` rather than raising.
vibecomfy/comfy_nodes/agent/completion_proofs.py:259:        Missing domains also default to ``unknown``.
vibecomfy/comfy_nodes/agent/completion_proofs.py:288:        """Return a proof with all domains set to ``unknown``.
vibecomfy/comfy_nodes/agent/completion_proofs.py:341:    "is_unknown",
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:63:        condition_id=str(payload.get("condition_id") or payload.get("id") or "unknown_condition"),
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:86:        step_id=str(payload.get("step_id") or payload.get("id") or "unknown_step"),
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:109:    role = str(payload.get("role") or "unknown_role")
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:114:        confidence=str(payload.get("confidence") or "unknown"),
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:136:        plan_id=str(value.get("plan_id") or "unknown"),
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:190:def malformed_execution_plan_evaluation(
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:214:        feedback="plan evaluation blocked: malformed execution plan payload.",
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:232:        evaluation = malformed_execution_plan_evaluation(
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:263:            str(condition.get("condition_id") or condition.get("id") or "unknown_condition")
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:295:    blocking = status["blocking"] if status["blocking"] is not None else "unknown"
vibecomfy/comfy_nodes/agent/execution_plan_runtime.py:312:    "malformed_execution_plan_evaluation",
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
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:301:            "unknown_contract",
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:334:        raise _fail("layout operation envelope must be an object", "malformed_layout_operation")
vibecomfy/comfy_nodes/agent/_frag_ingest.py:14:from vibecomfy.comfy_nodes.agent.contracts import FailureKind, StageResult, TurnContext
vibecomfy/comfy_nodes/agent/_frag_ingest.py:73:        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
vibecomfy/comfy_nodes/agent/_frag_ingest.py:130:            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
vibecomfy/comfy_nodes/agent/_frag_ingest.py:178:            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
vibecomfy/comfy_nodes/agent/_frag_ingest.py:384:                "failure_kind": FailureKind.VALIDATION_ERROR.value,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:33:from .contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:131:            # malformed ops (unknown op kind, missing required fields,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:139:        # Envelope present but ops is malformed — fall through to delta_ops.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:257:            # malformed entries (unknown op kind, missing required fields,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:258:            # etc.) are classified as malformed rather than canonical.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:264:                    "code": "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:277:            "code": "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:816:    # scope_path.  If none are present the op is malformed.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1089:) -> FailureEnvelope:
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1097:        FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1124:        distinct buckets: *malformed_delta*, *legacy_delta_shape*,
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1157:    # malformed shapes in distinct evidence buckets.
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1191:        elif diag_code == "canonical_envelope_malformed_ops":
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1192:            diag_code = "malformed_delta"
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1195:                "is malformed."
vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py:1277:            f"Turn {turn_id} has unknown V2 state {current_state!r}."
vibecomfy/executor/research.py:1558:    archive.  Failures are swallowed and returned as an empty list so the
vibecomfy/executor/research.py:1727:                source_type=f"domain_workflow_json:{_domain(url) or 'unknown'}",
vibecomfy/executor/research.py:2375:    Returns 86400 (24h) for unknown tiers as a safe default.
vibecomfy/executor/research.py:2386:    """Return ``"fresh"``, ``"stale"``, or ``"unknown"`` for a source.
vibecomfy/executor/research.py:2388:    When *retrieval_time* is empty, returns ``"unknown"``.
vibecomfy/executor/research.py:2393:        return "unknown"
vibecomfy/executor/research.py:2409:        return "unknown"
vibecomfy/executor/research.py:2411:        return "unknown"
vibecomfy/executor/research.py:3066:            class_type = str(source.get("class_type") or "<unknown>")
vibecomfy/executor/research.py:3079:            class_type = str(source.get("class_type") or "<unknown>")
vibecomfy/executor/research.py:3142:            "code": "missing_required_pattern_nodes",
vibecomfy/executor/research.py:3555:    """Normalise a raw socket type to an UPPER token, or ``None`` if unknown.
vibecomfy/executor/research.py:3572:    falls back to permissive acceptance: any unknown/wildcard/dynamic side, or
vibecomfy/executor/research.py:3747:                        f"{target_id}.{t_input_name}: unknown type"
vibecomfy/executor/research.py:3752:                        f"{target_id}.{t_input_name}: unknown type"
vibecomfy/executor/research.py:3925:    #                "unknown_type" | "occupied_input" | "ok"
vibecomfy/executor/research.py:3985:    if "unknown type" in low:
vibecomfy/executor/research.py:3986:        return "unknown_type", diag_text or "socket type unknown on both sides"
vibecomfy/executor/research.py:3993:        # These are not "unknown_type"; surface as direction_mismatch so the
vibecomfy/executor/research.py:4009:    tie/occupied conflict), ``unknown_type`` / ``direction_mismatch`` /
vibecomfy/executor/research.py:4139:    resolve so the matcher fails closed on unknown types — no guessing, no
vibecomfy/executor/research.py:4853:    Returns ``None`` if the inputs look malformed.
vibecomfy/executor/research.py:5565:                        reason="candidate graph construction returned a malformed graph",
vibecomfy/executor/research.py:5566:                        detail={"reason_code": "candidate_graph_malformed"},
vibecomfy/executor/research.py:6044:    freshness = str(source.get("_freshness_status") or "unknown")
vibecomfy/executor/research.py:6045:    if freshness != "unknown":
vibecomfy/executor/research.py:6134:    freshness_status = str(source.get("_freshness_status") or "unknown")
vibecomfy/executor/research.py:6163:        freshness_status=freshness_status if freshness_status in ("fresh", "stale") else "unknown",
vibecomfy/comfy_nodes/agent/execution_plan.py:207:    confidence: str = "unknown"
vibecomfy/comfy_nodes/agent/execution_plan.py:459:    return str(_condition_value(condition, "id") or "unknown_condition")
vibecomfy/comfy_nodes/agent/execution_plan.py:477:    return {"id": _condition_id(condition), "kind": "unknown"}
vibecomfy/comfy_nodes/agent/execution_plan.py:992:        step_id = str(_mapping_value(step, "step_id") or _mapping_value(step, "id") or "unknown_step")
vibecomfy/comfy_nodes/agent/execution_plan.py:1048:        plan_id=str(_mapping_value(plan, "plan_id") or "unknown"),
vibecomfy/comfy_nodes/agent/execution_plan.py:1078:        plan_id=str(_mapping_value(evaluation, "plan_id") or "unknown"),
vibecomfy/comfy_nodes/agent/execution_plan.py:1123:            plan_id=str(_mapping_value(evaluation, "plan_id") or "unknown"),
vibecomfy/comfy_nodes/agent/execution_plan.py:1262:        step_id = str(_mapping_value(step, "step_id") or _mapping_value(step, "id") or "unknown_step")
vibecomfy/comfy_nodes/agent/execution_plan.py:1309:        plan_id=str(_mapping_value(plan, "plan_id") or "unknown"),
vibecomfy/porting/reorganise/diagnostics.py:39:            raise ValueError(f"unknown diagnostic severity: {self.severity!r}")
vibecomfy/nodes/kjnodes.py:7115:    Attempt to implement https://github.com/agwmon/self-refine-video, for testing only, MAY NOT WORK AS INTENDED.
vibecomfy/nodes/kjnodes.py:7704:            example compatible nodes: unknown
vibecomfy/porting/widget_shape_fence.py:111:    malformed_new_raw_ui = (
vibecomfy/porting/widget_shape_fence.py:116:        # ingest) is only "malformed" if it actually has a widget-shape problem
vibecomfy/porting/widget_shape_fence.py:125:    if malformed_new_raw_ui:
vibecomfy/executor/execution_plan_builder.py:63:    "missing_required_inputs",
vibecomfy/executor/execution_plan_builder.py:64:    "unknown_class_types",
vibecomfy/executor/execution_plan_builder.py:631:    unknown = set(_unique_stable_strings(graph_mapping.get("unknown_class_types")))
vibecomfy/executor/execution_plan_builder.py:635:        if class_type in unknown:
vibecomfy/executor/execution_plan_builder.py:636:            provenance[class_type] = "graph_facts.unknown_class_types"
vibecomfy/porting/reorganise/parse.py:335:            "missing_required_field",
vibecomfy/porting/reorganise/parse.py:365:                "unknown_field",
vibecomfy/porting/reorganise/parse.py:439:                "unknown_role_hint",
vibecomfy/porting/reorganise/parse.py:469:                    "unknown_section_kind",
vibecomfy/porting/reorganise/parse.py:551:                    "unknown_helper_placement_kind",
vibecomfy/porting/reorganise/parse.py:628:                    "unknown_sampler_relation_kind",
vibecomfy/porting/reorganise/parse.py:706:                    "unknown_unassigned_policy",
vibecomfy/comfy_nodes/agent/_artifact_store.py:328:        raise ValueError(f"unknown transaction event type: {event_type!r}")
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:28:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, StageResult, _StageBlocked, _classify_stage_failure, _is_provider_exception, _record, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:49:        failure_kind = None
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:51:            failure_kind = result.value.get("failure_kind")
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:84:            failure_kind or FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:108:        if failure.kind is FailureKind.STALE_STATE_MISMATCH and public_stage in {"ingest", "ingest_v2"}:
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:134:) -> FailureEnvelope:
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:135:    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, classify_failure, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:137:    if stage in {"ingest", "ingest_v2"} and failure.kind is FailureKind.UNSUPPORTED_NON_DAG:
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:141:                FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:377:    class as ``unknown_add_node_class_type`` (even a perfectly-installed ``PreviewImage``).
vibecomfy/porting/edit/lint.py:23:- **issues** (typed errors for unknown targets / fields / malformed ops)
vibecomfy/porting/edit/lint.py:31:- *unknown target* – any node, link, or field reference that cannot be
vibecomfy/porting/edit/lint.py:150:    malformed ops are rejected).  ``normalizations`` records the disposition
vibecomfy/porting/edit/lint.py:358:        """Return input names for *uid* in *scope_path* (empty if unknown)."""
vibecomfy/porting/edit/lint.py:363:        """Return output names for *uid* in *scope_path* (empty if unknown)."""
vibecomfy/porting/edit/lint.py:703:    # the same aliases as apply or it emits false unknown_field warnings after
vibecomfy/porting/edit/lint.py:774:        # hard-reject genuinely unknown fields.
vibecomfy/porting/edit/lint.py:791:                "unknown_field",
vibecomfy/porting/edit/lint.py:804:            "unknown_field",
vibecomfy/porting/edit/lint.py:859:            "unknown_scope",
vibecomfy/porting/edit/lint.py:873:                "unknown_class_type",
vibecomfy/porting/edit/lint.py:1056:    - target-based: rejects unknown nodes; detects no-op when no link matches
vibecomfy/porting/edit/lint.py:1064:                "unknown_link",
vibecomfy/porting/edit/lint.py:1117:        "malformed_op",
vibecomfy/porting/edit/lint.py:1240:    # incorrectly classifies those dependent ops as ``unknown_target``.  The
vibecomfy/porting/edit/lint.py:1258:        # apply engine.  Failure to materialise the virtual graph is left for
vibecomfy/porting/edit/lint.py:1275:                "unknown_op",
vibecomfy/comfy_nodes/agent/contracts.py:145:    "failure_kind",
vibecomfy/comfy_nodes/agent/contracts.py:255:    "failure_kind",
vibecomfy/comfy_nodes/agent/contracts.py:304:class FailureKind(str, Enum):
vibecomfy/comfy_nodes/agent/contracts.py:306:    AST_SCAN_FAILURE = "ASTScanFailure"
vibecomfy/comfy_nodes/agent/contracts.py:321:    LOWERING_FAILURE = "LoweringFailure"
vibecomfy/comfy_nodes/agent/contracts.py:326:    AUDIT_WRITE_FAILURE = "AuditWriteFailure"
vibecomfy/comfy_nodes/agent/contracts.py:690:SCAN_CODE_FAILURE_KIND: Mapping[str, FailureKind] = MappingProxyType(
vibecomfy/comfy_nodes/agent/contracts.py:692:        "syntax_error": FailureKind.SYNTAX_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:693:        "source_too_large": FailureKind.OVERSIZED_PAYLOAD,
vibecomfy/comfy_nodes/agent/contracts.py:694:        "source_type": FailureKind.VALIDATION_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:695:        "forbidden_node": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:696:        "forbidden_import": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:697:        "forbidden_name": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:698:        "forbidden_call": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:699:        "dunder_access": FailureKind.AST_SCAN_FAILURE,
vibecomfy/comfy_nodes/agent/contracts.py:705:class FailureSpec:
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
vibecomfy/comfy_nodes/agent/contracts.py:1122:        "unknown",
vibecomfy/comfy_nodes/agent/contracts.py:1166:class FailureEnvelope:
vibecomfy/comfy_nodes/agent/contracts.py:1167:    kind: FailureKind
vibecomfy/comfy_nodes/agent/contracts.py:1261:AgentError = FailureEnvelope
vibecomfy/comfy_nodes/agent/contracts.py:1269:    failure_kind: FailureKind | None = None
vibecomfy/comfy_nodes/agent/contracts.py:1280:        if self.failure_kind is not None:
vibecomfy/comfy_nodes/agent/contracts.py:1281:            object.__setattr__(self, "failure_kind", _coerce_failure_kind(self.failure_kind))
vibecomfy/comfy_nodes/agent/contracts.py:1284:                "failure_kind": self.failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1293:                    "Failure TurnOutcome requires "
vibecomfy/comfy_nodes/agent/contracts.py:1298:                self.failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1339:    def from_failure(cls, failure: FailureEnvelope) -> "TurnOutcome":
vibecomfy/comfy_nodes/agent/contracts.py:1342:            failure_kind=failure.kind,
vibecomfy/comfy_nodes/agent/contracts.py:1358:                    "failure_kind": self.failure_kind.value,
vibecomfy/comfy_nodes/agent/contracts.py:1518:    failure_kind = response.get("failure_kind")
vibecomfy/comfy_nodes/agent/contracts.py:1519:    if not isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1520:        failure_kind = response.get("failureKind")
vibecomfy/comfy_nodes/agent/contracts.py:1521:    if not isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1523:        if isinstance(kind_value, str) and kind_value in {kind.value for kind in FailureKind}:
vibecomfy/comfy_nodes/agent/contracts.py:1524:            failure_kind = kind_value
vibecomfy/comfy_nodes/agent/contracts.py:1531:    spec: FailureSpec | None = None
vibecomfy/comfy_nodes/agent/contracts.py:1532:    if isinstance(failure_kind, str):
vibecomfy/comfy_nodes/agent/contracts.py:1534:            spec = FAILURE_SPECS[FailureKind(failure_kind)]
vibecomfy/comfy_nodes/agent/contracts.py:1543:        "failure_kind": failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:1562:        not isinstance(outcome.get("failure_kind"), str)
vibecomfy/comfy_nodes/agent/contracts.py:1563:        or outcome.get("failure_kind") not in {kind.value for kind in FailureKind}
vibecomfy/comfy_nodes/agent/contracts.py:1573:    failure: FailureEnvelope,
vibecomfy/comfy_nodes/agent/contracts.py:1672:def _public_agent_failure_context(failure: FailureEnvelope) -> dict[str, Any]:
vibecomfy/comfy_nodes/agent/contracts.py:1675:        FailureKind.PROVIDER_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:1676:        FailureKind.PROVIDER_CREDIT_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:1677:        FailureKind.AUTH_ERROR,
vibecomfy/comfy_nodes/agent/contracts.py:1684:    failure: FailureEnvelope,
vibecomfy/comfy_nodes/agent/contracts.py:1694:def product_failure_envelope_fields(failure: FailureEnvelope) -> dict[str, Any]:
vibecomfy/comfy_nodes/agent/contracts.py:2178:) -> FailureEnvelope:
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
vibecomfy/comfy_nodes/agent/contracts.py:2407:) -> FailureEnvelope:
vibecomfy/comfy_nodes/agent/contracts.py:2408:    failure_kind = _coerce_failure_kind(kind)
vibecomfy/comfy_nodes/agent/contracts.py:2409:    spec = FAILURE_SPECS[failure_kind]
vibecomfy/comfy_nodes/agent/contracts.py:2411:    return FailureEnvelope(
vibecomfy/comfy_nodes/agent/contracts.py:2412:        kind=failure_kind,
vibecomfy/comfy_nodes/agent/contracts.py:2616:    "FailureEnvelope",
vibecomfy/comfy_nodes/agent/contracts.py:2617:    "FailureKind",
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
vibecomfy/porting/edit/apply_resolve_base.py:48:                "unknown_scope_path",
vibecomfy/porting/edit/apply_resolve_base.py:70:                "unknown_node_target",
vibecomfy/porting/edit/apply_resolve_base.py:84:                "unknown_node_target",
vibecomfy/porting/edit/apply_resolve_base.py:272:                "unknown_node_field",
vibecomfy/porting/edit/apply_resolve_base.py:562:                    "unknown_link_id",
vibecomfy/porting/edit/apply_resolve_base.py:586:                "unknown_link_target_input",
vibecomfy/comfy_nodes/agent/provider.py:16:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/provider.py:17:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/provider.py:207:    "model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:211:    "completion_tokens",
vibecomfy/comfy_nodes/agent/provider.py:228:    attempts = coerce_model_attempts(response.get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:230:        merged["model_attempts"] = [dict(item) for item in attempts]
vibecomfy/comfy_nodes/agent/provider.py:378:        "unrelated or unknown, call `clarify()` with a typed refusal instead "
vibecomfy/comfy_nodes/agent/provider.py:422:        "Exception: if Revision evidence or the Research brief says an existing custom/provisional class has an unknown schema and that exact class is the edit target, search that exact class to hydrate its schema before editing. "
vibecomfy/comfy_nodes/agent/provider.py:514:                role = msg.get("role", "unknown")
vibecomfy/comfy_nodes/agent/provider.py:903:        normalized_route="unknown",
vibecomfy/comfy_nodes/agent/provider.py:1382:        return "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1385:        return "missing_required_fields"
vibecomfy/comfy_nodes/agent/provider.py:1386:    return "malformed_json"
vibecomfy/comfy_nodes/agent/provider.py:1397:    attempts = list(coerce_model_attempts(response.get("model_attempts")))
vibecomfy/comfy_nodes/agent/provider.py:1411:        revised_attempts.append(ModelAttemptEvidence.from_mapping(numbered).to_dict())
vibecomfy/comfy_nodes/agent/provider.py:1413:        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1415:        replace_last_model_attempts(revised_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1418:    exc.model_attempts = list(revised_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/provider.py:1428:        latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1430:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/provider.py:1510:                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:1517:                    ModelAttemptEvidence.from_mapping(numbered).to_dict()
vibecomfy/comfy_nodes/agent/provider.py:1521:                    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1523:                    replace_last_model_attempts(numbered_current_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1528:                metadata["model_attempts"] = [*attempt_log, *numbered_current_attempts]
vibecomfy/comfy_nodes/agent/provider.py:1827:        "provider": provider or "unknown",
vibecomfy/comfy_nodes/agent/_frag_state.py:40:    FailureEnvelope,
vibecomfy/comfy_nodes/agent/_frag_state.py:41:    FailureKind,
vibecomfy/comfy_nodes/agent/_frag_state.py:255:    def __init__(self, result: StageResult, failure: FailureEnvelope | None = None) -> None:
vibecomfy/comfy_nodes/agent/_frag_state.py:512:     "FailureEnvelope", "FailureKind", "FieldChange", "LOGGER", "MalformedModelJSON",
vibecomfy/comfy_nodes/agent/audit.py:10:from .contracts import ArtifactRef, DiagnosticRecord, FailureEnvelope, StageResult, TurnContext
vibecomfy/comfy_nodes/agent/audit.py:337:    failure: FailureEnvelope | Mapping[str, Any] | None = None,
vibecomfy/comfy_nodes/agent/audit.py:363:    if isinstance(failure, FailureEnvelope):
vibecomfy/comfy_nodes/agent/audit.py:401:    failure_kind = None
vibecomfy/comfy_nodes/agent/audit.py:402:    if isinstance(failure, FailureEnvelope):
vibecomfy/comfy_nodes/agent/audit.py:403:        failure_kind = failure.kind.value
vibecomfy/comfy_nodes/agent/audit.py:405:        failure_kind = failure.get("kind") or failure.get("failure_kind")
vibecomfy/comfy_nodes/agent/audit.py:419:        kind=response_dict.get("kind") if response_dict else failure_kind,
vibecomfy/comfy_nodes/agent/audit.py:451:    failure: FailureEnvelope | Mapping[str, Any],
vibecomfy/comfy_nodes/agent/audit.py:454:    digest = hashlib.sha256(_json_bytes(request or failure.to_dict() if isinstance(failure, FailureEnvelope) else failure)).hexdigest()[:12]
vibecomfy/porting/reorganise/compile.py:334:            raise ValueError(f"unknown spacing preset: {self.spacing_preset!r}")
vibecomfy/porting/reorganise/compile.py:344:            raise ValueError(f"unknown existing group policy: {self.existing_group_policy!r}")
vibecomfy/porting/reorganise/compile.py:346:            raise ValueError(f"unknown grouping policy: {self.grouping_policy!r}")
vibecomfy/porting/reorganise/compile.py:760:    layout_behavior: str = "unknown"
vibecomfy/porting/reorganise/compile.py:775:            layout_behavior = str(getattr(fact, "layout_behavior", "unknown") or "unknown")
vibecomfy/porting/reorganise/compile.py:4168:    over_capacity = len(cleaned) > max_columns
vibecomfy/porting/reorganise/compile.py:4178:    if not over_capacity and not imbalanced and not single_tall_column:
vibecomfy/porting/reorganise/compile.py:4311:    """Return the ``layout_behavior`` string for *ref*, defaulting to ``"unknown"``."""
vibecomfy/porting/reorganise/compile.py:4314:            return str(getattr(fact, "layout_behavior", "unknown") or "unknown")
vibecomfy/porting/reorganise/compile.py:4315:    return "unknown"
vibecomfy/porting/reorganise/compile.py:4690:    and nodes with an ``unknown`` role hint are also never flagged.
vibecomfy/porting/reorganise/compile.py:4706:                # Helpers, UI, unknown, shared, subgraph-container are not
vibecomfy/comfy_nodes/agent/_frag_revision_stages.py:37:    from vibecomfy.comfy_nodes.agent.edit import (RevisionEvidence, StageResult, _canonical_agent_edit_route, _duration_ms, _extract_readiness_diagnostics, _extract_ready_metadata, _hydrate_current_graph_unknown_node_schemas, _request_no_gpu_detected, _revision_no_candidate_reason, _runtime_execution_requested, _schema_provider_available, _write_revision_evidence_artifact, collect_graph_facts, collect_readiness_evidence, collect_topology_evidence)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_revision_stages.py:44:            _hydrate_current_graph_unknown_node_schemas(state)
vibecomfy/comfy_nodes/agent/_frag_revision_stages.py:86:    hydrated_candidates = _hydrate_current_graph_unknown_node_schemas(state)
vibecomfy/porting/reorganise/validate.py:101:                    "unknown_section_id",
vibecomfy/porting/reorganise/validate.py:162:                    "unknown_section_id",
vibecomfy/porting/reorganise/validate.py:335:                        "unknown_section_id",
vibecomfy/porting/reorganise/validate.py:876:                "unknown_ref",
vibecomfy/comfy_nodes/agent/OWNERSHIP.md:24:   No other module may define a competing `FieldChange`, `FailureEnvelope`,
vibecomfy/porting/edit/projection.py:87:    # unknown_add_node_class_type. Feeding the real registry is the anti-hallucination
vibecomfy/porting/edit/projection.py:289:        # apply_delta then rejects as unknown_node_field. Listing the names — capped to
vibecomfy/porting/edit/apply_mutate.py:265:    # deterministic fallback only for dynamic/unknown inputs.
vibecomfy/porting/cache/object_info/comfy_core@object_info_comfyui_0.24.0.1.json:83112:              "unknown"
vibecomfy/porting/edit/normalize.py:343:    """Attempt to normalize through real LiteGraph serialize→configure→serialize.
vibecomfy/porting/edit/apply_values.py:151:    # look path-shaped, or (conservatively for unknown schemas) the proposed string
vibecomfy/comfy_nodes/agent/_frag_chat.py:37:    JSON-canonical UI convenience.  Failures here are logged and swallowed.
vibecomfy/comfy_nodes/agent/_frag_chat.py:764:        # Defensively skip malformed entries (non-dict, missing role,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:16:from vibecomfy.comfy_nodes.agent.contracts import ApplyEligibility, FailureEnvelope, FailureKind, StageResult, TurnContext, TurnOutcome, _ABSENT_FIELD_OLD, _MISSING_FIELD_CHANGE_OLD, _iter_ui_graph_nodes, _ui_node_uid, _ui_node_uid_aliases, _ui_widget_value_for_field
vibecomfy/comfy_nodes/agent/_frag_humanize.py:207:        return "unknown source"
vibecomfy/comfy_nodes/agent/_frag_humanize.py:223:    return "unknown source"
vibecomfy/comfy_nodes/agent/_frag_humanize.py:860:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:870:    internal_kind = outcome.kind if outcome is not None else ("failure" if failure is not None else "unknown")
vibecomfy/comfy_nodes/agent/_frag_humanize.py:920:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:926:        if state.batch_exit_mode == _BATCH_EXIT_BUDGET or failure.kind is FailureKind.BATCH_BUDGET_EXHAUSTED:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:946:        if fallback_reason in {"provider_failure", "malformed_response", "timeout"}:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:992:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1107:            fallback_reason = "malformed_response"
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1166:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1171:        if failure.kind is FailureKind.STALE_STATE_MISMATCH:
vibecomfy/comfy_nodes/agent/_frag_humanize.py:1197:    failure: FailureEnvelope | None = None,
vibecomfy/porting/reorganise/plan_types.py:94:    "unknown",
vibecomfy/porting/reorganise/plan_types.py:109:ROLE_HINT_UNKNOWN: RoleHint = "unknown"
vibecomfy/porting/reorganise/plan_types.py:144:    "unknown",        # Cannot determine (unclassifiable)
vibecomfy/porting/reorganise/plan_types.py:153:PIPELINE_STAGE_UNKNOWN: PipelineStage = "unknown"
vibecomfy/porting/reorganise/plan_types.py:183:LayoutBehavior = Literal["primary", "sidecar", "wall", "note", "unknown"]
vibecomfy/porting/reorganise/plan_types.py:188:LAYOUT_BEHAVIOR_UNKNOWN: LayoutBehavior = "unknown"
vibecomfy/porting/reorganise/plan_types.py:274:            raise ValueError(f"unknown section kind: {self.kind!r}")
vibecomfy/porting/reorganise/plan_types.py:276:            raise ValueError(f"unknown role hint: {self.role_hint!r}")
vibecomfy/porting/reorganise/plan_types.py:305:            raise ValueError(f"unknown role hint: {self.role_hint!r}")
vibecomfy/porting/reorganise/plan_types.py:331:            raise ValueError(f"unknown helper placement kind: {self.kind!r}")
vibecomfy/porting/reorganise/plan_types.py:361:            raise ValueError(f"unknown sampler relation kind: {self.kind!r}")
vibecomfy/porting/reorganise/plan_types.py:388:            raise ValueError(f"unknown role hint: {self.role_hint!r}")
vibecomfy/porting/reorganise/plan_types.py:413:    layout_behavior: LayoutBehavior = "unknown"
vibecomfy/porting/reorganise/plan_types.py:425:            raise ValueError(f"unknown role hint: {self.role_hint!r}")
vibecomfy/porting/reorganise/plan_types.py:427:            raise ValueError(f"unknown layout behavior: {self.layout_behavior!r}")
vibecomfy/porting/reorganise/plan_types.py:429:            raise ValueError(f"unknown pipeline stage: {self.pipeline_stage!r}")
vibecomfy/porting/reorganise/plan_types.py:541:            raise ValueError(f"unknown diagnostic severity: {self.severity!r}")
vibecomfy/porting/reorganise/plan_types.py:592:            raise ValueError(f"unknown unassigned policy: {self.unassigned_policy!r}")
vibecomfy/porting/reorganise/classify.py:67:REASON_UNKNOWN_UNASSIGNED = "unknown_unassigned"
vibecomfy/porting/reorganise/classify.py:142:            raise ValueError(f"unknown role hint: {self.role_hint!r}")
vibecomfy/porting/reorganise/classify.py:146:            raise ValueError(f"unknown layout behavior: {self.layout_behavior!r}")
vibecomfy/porting/reorganise/classify.py:148:            raise ValueError(f"unknown pipeline stage: {self.pipeline_stage!r}")
vibecomfy/porting/reorganise/classify.py:475:    fallback       ``unknown`` (genuinely unrecognized nodes)
vibecomfy/porting/reorganise/classify.py:507:    # ----- unknown / fallback → inspect class_type ---------------------------
vibecomfy/comfy_nodes/agent/executor_durable.py:74:        # pass through unchanged. Failures fall through to the outer
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:32:def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:56:    return "malformed"
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:63:    from vibecomfy.comfy_nodes.agent.edit import (_BATCH_PROTOCOL_RETRY_PROMPT, _malformed_model_json_detail)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:66:        detail = _malformed_model_json_detail(exc)
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:103:        str(status.get("step_id") or "unknown_step")
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:110:        str(condition.get("condition_id") or condition.get("id") or "unknown_condition")
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:116:        f"plan_id={getattr(evaluation, 'plan_id', 'unknown')}",
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:221:        # A malformed node entry means we cannot guarantee completeness.
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:941:    "_malformed_model_json_detail",
vibecomfy/porting/workbench.py:888:            message=_unknown_class_message(class_type),
vibecomfy/porting/workbench.py:892:            recommendation=_unknown_class_message(class_type),
vibecomfy/porting/workbench.py:918:def _unknown_class_message(class_type: str) -> str:
vibecomfy/porting/workbench.py:919:    return f"unknown class: {class_type}. Run 'nodes lookup {class_type}' to find the providing pack, then 'nodes install <slug>'."
vibecomfy/porting/edit/apply_types.py:459:_RESOLUTION_CODE_REMAP: dict[str, str] = {"unknown_target": "unknown_node_target"}
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
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:267:            "unknown_contract",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:295:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:300:            "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:307:                "malformed_materialization",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:382:                        "malformed_materialization_entry",
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:388:                    "malformed_materialization_entry",
vibecomfy/porting/helper_resolve.py:92:                code="primitive_unknown_type_token",
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:273:        title = str(opt.get("source_class_type") or "(unknown)")
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:434:def _selected_precedent_unknown_class_feedback(
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:438:    """Return a terminal authoring blocker for unknown classes after precedent use."""
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:446:    unknown_classes: list[str] = []
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:454:            if code != "unknown_add_node_class_type":
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:457:                if match not in unknown_classes:
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:458:                    unknown_classes.append(match)
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:460:    if not unknown_classes:
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:483:        class_type for class_type in unknown_classes if class_type not in precedent_classes
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:909:            "video node's custom class is unknown. Insert a minimal local `vibecomfy.exec` frame "
vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:948:     "_selected_precedent_unknown_class_feedback", "_summarize_precedent_packet",
vibecomfy/comfy_nodes/agent/candidate_transaction.py:90:    "unknown": "superseded",
vibecomfy/comfy_nodes/agent/candidate_transaction.py:279:        return False, "malformed_schema_witness"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:281:        return False, "malformed_schema_provider_mode"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:380:            sources[str(class_type)] = str(source or "unknown")
vibecomfy/comfy_nodes/agent/candidate_transaction.py:666:        return False, "malformed_candidate_transaction"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:697:            return False, "malformed_layout_verification_contract"
vibecomfy/comfy_nodes/agent/candidate_transaction.py:715:        return False, "malformed_candidate_transaction_actions"
vibecomfy/comfy_nodes/agent/graph_normalization.py:37:    The conversion is whole-graph and fail-closed: malformed or mixed mapping
vibecomfy/comfy_nodes/agent/runtime.py:51:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/runtime.py:52:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/runtime.py:67:# empty-response failure with observed zero completion tokens may consume the
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
vibecomfy/comfy_nodes/agent/runtime.py:154:    replace_last_model_attempts([value])
vibecomfy/comfy_nodes/agent/runtime.py:313:    return "unknown"
vibecomfy/comfy_nodes/agent/runtime.py:342:    return _ROUTE_TO_AGENT_ID.get(requested, "unknown")
vibecomfy/comfy_nodes/agent/runtime.py:347:    if normalized_route == "unknown":
vibecomfy/comfy_nodes/agent/runtime.py:348:        return "unknown"
vibecomfy/comfy_nodes/agent/runtime.py:370:    if normalized_route == "unknown":
vibecomfy/comfy_nodes/agent/runtime.py:508:    """True only for typed empty responses with observed zero completion tokens."""
vibecomfy/comfy_nodes/agent/runtime.py:509:    attempts = coerce_model_attempts(result.get("model_attempts"))
vibecomfy/comfy_nodes/agent/runtime.py:516:        and latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/runtime.py:518:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/runtime.py:527:        return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:532:    if endpoint != "unknown":
vibecomfy/comfy_nodes/agent/runtime.py:533:        return "unknown", "openai_compatible", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:534:    return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/runtime.py:537:def _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:549:    return ModelAttemptEvidence(
vibecomfy/comfy_nodes/agent/runtime.py:578:    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
vibecomfy/comfy_nodes/agent/runtime.py:579:    provider/capacity errors, and malformed non-empty content surface immediately.
vibecomfy/comfy_nodes/agent/runtime.py:599:            timeout_attempt = _timeout_model_attempt(
vibecomfy/comfy_nodes/agent/runtime.py:608:            record_model_attempts([timeout_attempt])
vibecomfy/comfy_nodes/agent/runtime.py:609:            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/runtime.py:611:        attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/comfy_nodes/agent/runtime.py:614:            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
vibecomfy/comfy_nodes/agent/runtime.py:616:            record_model_attempts([normalized])
vibecomfy/comfy_nodes/agent/runtime.py:618:            result["model_attempts"] = list(accumulated_attempts)
vibecomfy/comfy_nodes/agent/runtime.py:1110:            "unknown"
vibecomfy/comfy_nodes/agent/runtime.py:1111:            if requested and _normalize_route(requested) == "unknown"
vibecomfy/comfy_nodes/agent/runtime.py:1218:    "end_deepseek_usage_capture", "begin_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1219:    "snapshot_model_attempt_capture", "end_model_attempt_capture",
vibecomfy/comfy_nodes/agent/runtime.py:1220:    "record_model_attempts", "replace_last_model_attempt", "replace_last_model_attempts",
vibecomfy/comfy_nodes/agent/worker.py:69:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/worker.py:106:def _model_attempt_failure_type(exc: BaseException, raw_text: str | None) -> str:
vibecomfy/comfy_nodes/agent/worker.py:109:        return "empty_response"
vibecomfy/comfy_nodes/agent/worker.py:113:        return "malformed_json" if "{" in (raw_text or "") else "non_json_content"
vibecomfy/comfy_nodes/agent/worker.py:116:        return "non_json_content"
vibecomfy/comfy_nodes/agent/worker.py:119:            return "missing_required_fields"
vibecomfy/comfy_nodes/agent/worker.py:120:        return "malformed_json"
vibecomfy/comfy_nodes/agent/worker.py:133:        return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/worker.py:138:    if endpoint != "unknown":
vibecomfy/comfy_nodes/agent/worker.py:139:        return "unknown", "openai_compatible", endpoint
vibecomfy/comfy_nodes/agent/worker.py:140:    return "unknown", "unknown", endpoint
vibecomfy/comfy_nodes/agent/worker.py:143:def _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:160:    return ModelAttemptEvidence(
vibecomfy/comfy_nodes/agent/worker.py:162:        attempt=profiling_context.get("model_attempt") or 1,
vibecomfy/comfy_nodes/agent/worker.py:197:    failure_type = _model_attempt_failure_type(exc, raw_text)
vibecomfy/comfy_nodes/agent/worker.py:202:        "empty_response": "empty",
vibecomfy/comfy_nodes/agent/worker.py:203:        "missing_required_fields": "missing_content",
vibecomfy/comfy_nodes/agent/worker.py:221:            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
vibecomfy/comfy_nodes/agent/worker.py:225:    out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:226:        _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:364:            completion_tokens = _usage_int(raw_usage, "completion_tokens")
vibecomfy/comfy_nodes/agent/worker.py:368:            if completion_tokens is None:
vibecomfy/comfy_nodes/agent/worker.py:369:                completion_tokens = max(0, int(getattr(canonical_usage, "output_tokens", 0) or 0))
vibecomfy/comfy_nodes/agent/worker.py:371:                total_tokens = prompt_tokens + completion_tokens
vibecomfy/comfy_nodes/agent/worker.py:392:                    "completion_tokens": completion_tokens,
vibecomfy/comfy_nodes/agent/worker.py:454:                    "completion_tokens": last_result.get("completion_tokens"),
vibecomfy/comfy_nodes/agent/worker.py:590:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:591:                _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:620:            out["model_attempts"] = [
vibecomfy/comfy_nodes/agent/worker.py:621:                _model_attempt(
vibecomfy/comfy_nodes/agent/worker.py:626:                    failure_type=_model_attempt_failure_type(exc, raw_text),
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:33:from .contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:64:) -> dict[str, Any] | FailureEnvelope:
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:119:                FailureKind.STALE_STATE_MISMATCH,
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:128:        if current_state == "unknown":
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
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:514:        unknown_transitions: list[dict[str, Any]] = []
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:531:                other_record["state"] = "unknown"
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:532:                other_record["unknown_at"] = other_record.get("unknown_at") or _now()
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:533:                other_record["unknown_reason"] = "superseded_by_accept"
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:535:                transitioned_at = other_record["unknown_at"]
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:536:                unknown_transitions.append(
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:541:                        "to_state": "unknown",
vibecomfy/comfy_nodes/agent/_turn_state_machine.py:571:            "unknown_transitions": unknown_transitions,
vibecomfy/comfy_nodes/__init__.py:122:        "served_asset_kind": "unknown",
vibecomfy/comfy_nodes/__init__.py:380:                "passthrough_on_non_json": ("BOOLEAN", {"default": False}),
vibecomfy/comfy_nodes/__init__.py:462:            "redaction_policy", "policy_version", "passthrough_on_non_json",
vibecomfy/porting/edit/ops.py:51:DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta"
vibecomfy/porting/edit/_resolve.py:1410:                    "unknown_graph_name",
vibecomfy/porting/edit/_resolve.py:1443:        node_ref, issues = self._resolve_attribute_base(target, code_unknown="unknown_target_name")
vibecomfy/porting/edit/_resolve.py:1483:                    "unknown_target_field",
vibecomfy/porting/edit/_resolve.py:1511:        node_ref, issues = self._resolve_attribute_base(value, code_unknown="unknown_source_name")
vibecomfy/porting/edit/_resolve.py:1523:        code_unknown: str,
vibecomfy/porting/edit/_resolve.py:1536:        if issues and issues[0].code == "unknown_graph_name":
vibecomfy/porting/edit/_resolve.py:1539:                    code_unknown,
vibecomfy/porting/edit/_resolve.py:1595:                    "unknown_output_slot",
vibecomfy/porting/edit/_resolve.py:1616:                "unknown_output_slot",
vibecomfy/porting/edit/_parse_execute.py:445:                        "unknown_mode_label",
vibecomfy/comfy_nodes/web/intent_graph_adapter.js:440:function retagFailure(result, operation) {
vibecomfy/comfy_nodes/web/intent_graph_adapter.js:485:    if (!result.ok) return retagFailure(result, "capture_normalized");
vibecomfy/comfy_nodes/web/intent_graph_adapter.js:495:    if (!result.ok) return retagFailure(result, "capture_draw_snapshot");
vibecomfy/comfy_nodes/web/intent_graph_adapter.js:531:    if (!result.ok) return retagFailure(result, "enumerate_nodes");
vibecomfy/comfy_nodes/web/intent_graph_adapter.js:648:    if (!captured.ok) return retagFailure(captured, "project");
vibecomfy/comfy_nodes/web/intent_graph_adapter.js:678:    if (!captured.ok) return retagFailure(captured, "projection_reference");
vibecomfy/comfy_nodes/agent/_frag_narrator.py:85:    def failure_kind(self) -> str:
vibecomfy/comfy_nodes/agent/_frag_narrator.py:140:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_narrator.py:169:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_narrator.py:210:    Failures are logged and swallowed; artifacts are best-effort only.
vibecomfy/comfy_nodes/agent/_frag_narrator.py:357:    failure: FailureEnvelope | None = None,
vibecomfy/comfy_nodes/agent/_frag_narrator.py:426:            LOGGER.warning("Narrator malformed response, falling back: %s", exc)
vibecomfy/comfy_nodes/agent/_frag_narrator.py:427:            fallback_reason = "malformed_response"
vibecomfy/comfy_nodes/web/agent_submit_flow.js:39:    agentPanelFailure,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:142:  function readSubmitFailureMessage(error) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:152:  function buildSubmitFailureContext(panel, snapshot = null, extras = {}) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:177:  function mergeSubmitFailureContext(error, diagnosticContext = {}) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:206:  function buildSubmitTimeoutFailure(panel, snapshot, deadlineMs, timeoutKind = "inactivity") {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:208:    return agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_submit_flow.js:217:        ...buildSubmitFailureContext(panel, snapshot, {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:290:        settle(reject, buildSubmitTimeoutFailure(panel, snapshot, elapsedLimitMs, timeoutKind));
vibecomfy/comfy_nodes/web/agent_submit_flow.js:304:  function normalizeSubmitFailure(error, diagnosticContext = {}) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:306:      return mergeSubmitFailureContext(error, diagnosticContext);
vibecomfy/comfy_nodes/web/agent_submit_flow.js:308:    return agentPanelFailure("NetworkError", readSubmitFailureMessage(error), {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:310:      ...mergeSubmitFailureContext({
vibecomfy/comfy_nodes/web/agent_submit_flow.js:316:  function isValidationSubmitFailure(failure) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:322:  function isStaleSubmitFailure(failure) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:327:  function markBackendSubmitFailure(error, metadata = {}) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:339:  function shouldAutoRetrySubmitFailure(error, failure, { attemptIndex, maxAutomaticRetryCount } = {}) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:349:    if (isValidationSubmitFailure(failure)) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:352:    if (isStaleSubmitFailure(failure)) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:355:    const normalizedAttemptIndex = Number.isFinite(attemptIndex) ? Number(attemptIndex) : 0;
vibecomfy/comfy_nodes/web/agent_submit_flow.js:359:    if (normalizedAttemptIndex >= normalizedRetryBudget) {
vibecomfy/comfy_nodes/web/agent_submit_flow.js:396:    readSubmitFailureMessage,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:397:    buildSubmitFailureContext,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:398:    mergeSubmitFailureContext,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:399:    buildSubmitTimeoutFailure,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:401:    normalizeSubmitFailure,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:402:    isValidationSubmitFailure,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:403:    isStaleSubmitFailure,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:404:    markBackendSubmitFailure,
vibecomfy/comfy_nodes/web/agent_submit_flow.js:405:    shouldAutoRetrySubmitFailure,
vibecomfy/comfy_nodes/agent/gates.py:154:        condition_ids.append(str(condition_id or "unknown_condition"))
vibecomfy/porting/edit/schemas/v2/obligation_ledger.schema.json:42:        "unknown",
vibecomfy/porting/edit/apply_resolve_add.py:55:                "unknown_add_node_class_type",
vibecomfy/porting/edit/apply_resolve_add.py:147:                    "missing_required_add_node_input",
vibecomfy/porting/edit/apply_resolve_add.py:172:                    "unknown_add_node_field",
vibecomfy/porting/edit/apply_resolve_add.py:237:                    "unknown_add_node_input",
vibecomfy/porting/edit/apply_resolve_add.py:587:                    "unknown_group_anchor",
vibecomfy/security/capabilities.py:4:``class_type`` values to edit-time capabilities and treats unknown classes as
vibecomfy/security/capabilities.py:57:    :func:`unknown_class_policy`.
vibecomfy/security/capabilities.py:63:    return unknown_class_policy()
vibecomfy/security/capabilities.py:72:def unknown_class_policy() -> frozenset[Capability]:
vibecomfy/security/capabilities.py:73:    """Quarantine default for unknown node classes."""
vibecomfy/porting/edit/_session_types.py:256:    "unknown_graph_name": "This name is not known. Render the session to refresh name bindings, or check for typos.",
vibecomfy/porting/edit/_session_types.py:258:    "unknown_target_field": "Check the available field and input names. Use describe(name) to see the node's shape.",
vibecomfy/porting/edit/_session_types.py:259:    "unknown_output_slot": "Check the available output slot names. Use describe(name) to see available outputs.",
vibecomfy/security/__init__.py:14:    unknown_class_policy,
vibecomfy/security/__init__.py:42:    "unknown_class_policy",
vibecomfy/comfy_nodes/web/frontend_ownership_map.md:61:  `renderFailure`, or `renderQueue`.
vibecomfy/analysis/corpus.py:97:        category = template_id.split("/")[0] if "/" in template_id else "unknown"
vibecomfy/analysis/corpus.py:211:    return "unknown"
vibecomfy/security/agent_generated_loader.py:140:class ScanFailure:
vibecomfy/security/agent_generated_loader.py:167:    failures: tuple[ScanFailure, ...] = field(default_factory=tuple)
vibecomfy/security/agent_generated_loader.py:218:            ScanFailure(
vibecomfy/security/agent_generated_loader.py:226:            ScanFailure(
vibecomfy/security/agent_generated_loader.py:239:            ScanFailure(
vibecomfy/security/agent_generated_loader.py:251:            ScanFailure(
vibecomfy/security/agent_generated_loader.py:315:def _report(*failures: ScanFailure) -> ScanReport:
vibecomfy/security/agent_generated_loader.py:330:        self.failures: list[ScanFailure] = []
vibecomfy/security/agent_generated_loader.py:403:            ScanFailure(
vibecomfy/security/agent_generated_loader.py:424:    "ScanFailure",
vibecomfy/analysis/node_coverage.py:130:                "pack": pack or "unknown",
vibecomfy/analysis/workflow_summary.py:316:        # Skip empty/unknown
vibecomfy/analysis/graph.py:332:                        "reason": "missing_required_input",
vibecomfy/analysis/graph.py:380:    return "unknown"
vibecomfy/comfy_nodes/web/_intent_graph_receipt_core.mjs:170:      throw _fail(`Unknown fence key: ${key}`, "unknown_fence_key", { key });
vibecomfy/comfy_nodes/web/_intent_graph_receipt_core.mjs:381:      throw _fail("Receipt is unknown to this instance", "forged_receipt");
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:86:  return { ok: false, diagnostic: { code: code || "unknown_error", detail: detail || {} } };
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:97:      code: "malformed_restoration_payload",
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:143:      return { kind: "unknown_op", op_index: index };
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:203:        return { kind: "unknown_op", op_index: index };
vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs:241:        return { kind: "unknown_op", op_index: index };
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
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:164:    throw _fail("Unknown materialization contract version", "unknown_contract");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:186:    throw _fail("accompanyingOps must be a non-empty array of canonical delta ops", "malformed_materialization");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:190:      throw _fail("accompanyingOps must be canonical delta ops", "malformed_materialization");
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:232:          throw _fail("vibecomfy.exec widgets_values must be array or object", "malformed_materialization_entry", { field: "widgets_values" });
vibecomfy/comfy_nodes/web/mutation_materialization_v1.js:235:        throw _fail("widgets_values must be an array for non-vibecomfy.exec nodes", "malformed_materialization_entry", { field: "widgets_values" });
vibecomfy/comfy_nodes/web/panel_scheduler.js:200:  // Validate dirty sections before any early-return so unknown
vibecomfy/comfy_nodes/web/agent_turn_feed.js:80:    status: asString(entry.status) || "unknown",
vibecomfy/comfy_nodes/web/agent_turn_feed.js:465:      status: "unknown",
vibecomfy/comfy_nodes/web/agent_turn_feed.js:468:      outcome: { kind: "unknown", summary: null },
vibecomfy/comfy_nodes/web/agent_turn_feed.js:1270:  const updateStatus = asString(update.status) || "unknown";
vibecomfy/comfy_nodes/web/agent_turn_feed.js:1322:    const existingStatus = asString(existing.status) || "unknown";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:85:  return "(unknown URL)";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:155:function turnFailureForReport(entry) {
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:159:    entry?.failure_kind
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:161:    || outcome?.failure_kind
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:168:  // turn has a message but is NOT a failure — labeling it "Failure: …" (as the old
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:170:  const isFailure =
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:176:  if (!isFailure) {
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:185:  return compactReportText(`${kind || "Failure"}${stage ? ` @ ${stage}` : ""}${message ? `: ${message}` : ""}`);
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:232:// unknown_output_slot with the `available_slots`). This is where the genuine
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:427:      status: message.status || message.phase || message.outcome?.kind || "unknown",
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:451:    status: compactReportText(entry?.status || entry?.phase || "unknown", 80),
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:462:    failure: turnFailureForReport(entry),
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:475:    `  Status/outcome: ${turn.status || "unknown"}${turn.outcome ? `; ${turn.outcome}` : ""}`,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:531:  const phase = panel?.state?.phase || debug.phase || "(unknown)";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:543:    `Panel id: ${debug.panelId || panel?.panelId || "(unknown)"}`,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:558:  const sessionId = panel?.state?.sessionId || debug.sessionId || "(unknown-session)";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:559:  const phase = panel?.state?.phase || debug.phase || "(unknown)";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:590:    "  - response.json: the final outcome envelope (failure_kind, user_facing_message).",
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:616:          status: turnEntry.status || "unknown",
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:623:          failure_kind: turnEntry.failure_kind || null,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:655:  const status = turnEntry.status || "unknown";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:671:  const status = turnEntry.status || "unknown";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:710:      failure_kind: panel.state.failure.kind,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:733:  const status = panel.state.phase || "unknown";
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:907:    `Session path: ${payload?.session_path || "(unknown)"}`,
vibecomfy/comfy_nodes/web/diagnostics_reporting.js:918:      manifest.push(`  - ${item?.name || "(unknown)"}: ${item?.reason || "?"}${item?.size ? ` (${_formatBundleBytes(item.size)})` : ""}`);
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:111:function hasFailureHints(response) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:259:    response.agentFailureContext,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:261:    response.outcome?.agentFailureContext,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:263:    response.debug?.failure?.agentFailureContext,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:285:    || asString(response.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:296:  const failureContext = response.agentFailureContext || response.agent_failure_context;
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:298:    payload.agentFailureContext = deep_plain(failureContext);
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:330:      if (isObject(errorOutcome.agent_failure_context) && !errorOutcome.agentFailureContext) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:331:        errorOutcome.agentFailureContext = deep_plain(errorOutcome.agent_failure_context);
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:395:  if (response.ok === false || hasFailureHints(response)) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:468:  // SD2: both session_id and turn_id must be absent for malformed/non-applyable.
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:525:  // malformed/non-applyable, never stale/rebaseline. Suppress Apply and
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:913:  // turn_id is malformed/non-applyable, never stale/rebaseline. Prevent
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:994:    failureKind: asString(raw.failureKind) || asString(raw.failure_kind),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1446:        message: `Node ${node?.id ?? "unknown"} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1627:    failure_kind: asString(source.failure_kind) || asString(source.failureKind) || asString(outcome?.failure_kind),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1880:    status: compactReportText(asString(entry.status) || asString(entry.phase) || statusFromOutcome(outcome) || "unknown", 80),
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1891:      asString(entry.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1912:export function readUserFailure(value, options) {
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1921:      || asString(normalized.outcome.failure_kind)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1935:    agentFailureContext:
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1936:      isObject(normalized.outcome.agentFailureContext)
vibecomfy/comfy_nodes/web/agent_edit_response_contract.js:1937:        ? deep_plain(normalized.outcome.agentFailureContext)
vibecomfy/comfy_nodes/web/agent_status_poller.js:13:  MALFORMED: "malformed_status",
vibecomfy/comfy_nodes/web/agent_status_poller.js:60:const INFO_ASSET_KINDS = new Set(["source", "cache_busted_dist", "unknown"]);
vibecomfy/comfy_nodes/web/agent_status_poller.js:195: * contract.  Do not retain unknown values: the diagnostic panel is visible to
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
vibecomfy/comfy_nodes/web/canonical_delta.js:24:export const DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta";
vibecomfy/comfy_nodes/web/canonical_delta.js:334:      code: "canonical_envelope_malformed_ops",
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:303:  const explicitFailure = payload.failure || null;
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:306:  if (explicitFailure) {
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:309:      failure: explicitFailure,
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:312:        ...explicitFailure,
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:489:      // failure → treat as a malformed terminal. The orchestrator may pass an
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:493:        explicitFailure || {
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:666:export function commitPrepareFailure(panel, payload = {}) {
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:699:export function commitVerifyCanvasFailure(panel, payload = {}) {
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:744:export function commitFinalizeFailure(panel, payload = {}) {
vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js:787:export function commitRollbackFailure(panel, payload = {}) {
vibecomfy/comfy_nodes/web/panel_composer.js:98:      // Ignore malformed debug-only stage data in the composer summary.
vibecomfy/comfy_nodes/web/panel_composer.js:191:      message: "Submit is disabled because /vibecomfy/agent/status returned a malformed payload.",
vibecomfy/comfy_nodes/web/panel_composer.js:597:function normalizedRuntimeInfoString(value, fallback = "unknown") {
vibecomfy/comfy_nodes/web/panel_composer.js:675:    `infoContractVersion: ${runtimeInfo?.info_contract_version ?? "unknown"}`,
vibecomfy/comfy_nodes/web/panel_composer.js:709:    `routeStatus: ${applyDisplayState.routeStatus?.kind || "unknown"}`,
vibecomfy/comfy_nodes/web/panel_composer.js:842:      guidanceNode.textContent = "The backend status payload is malformed. Fix /vibecomfy/agent/status and retry.";
vibecomfy/comfy_nodes/web/active_canvas_scope_guard.js:336:      reason: `canvas_scope_mismatch:${canvasAssertion.reason || "unknown"}`,
vibecomfy/comfy_nodes/web/comfy_adapter.js:49:    this.code = code || "malformed_delta";
vibecomfy/comfy_nodes/web/comfy_adapter.js:1275:    // A malformed extension node must never block review; retain server geometry.
vibecomfy/comfy_nodes/web/comfy_adapter.js:1581:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1813:      "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1822:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:1829:        "malformed_delta",
vibecomfy/comfy_nodes/web/comfy_adapter.js:2514:  const version = String(frontendVersion || "unknown").trim() || "unknown";
vibecomfy/comfy_nodes/web/comfy_adapter.js:2559:      frontendVersion: capabilities.frontendVersion || "unknown",
vibecomfy/comfy_nodes/web/comfy_adapter.js:2566:    const name = extension?.name || "unknown";
vibecomfy/comfy_nodes/web/preview_picker.js:974:          scope_mismatch: scopeCheck.reason || "unknown",
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:9:    agentPanelFailure,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:21:    commitRollbackFailure,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:43:    syntheticFailureAgentMessage,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:56:      : "unknown";
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:60:  function rollbackFailureKind(value) {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:63:      : typeof value?.failure_kind === "string" && value.failure_kind
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:64:        ? value.failure_kind
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:68:  function rollbackFailureMessage(value) {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:161:      triggerFailure = null,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:254:      const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:264:        const obligations = commitRollbackFailure(panel, {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:286:      ...(rollbackFailureKind(triggerFailure)
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:287:        ? { failure_kind: rollbackFailureKind(triggerFailure).slice(0, 128) }
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:289:      ...(rollbackFailureMessage(triggerFailure)
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:290:        ? { failure_message: rollbackFailureMessage(triggerFailure) }
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:357:        : agentPanelFailure("RollbackError", String(error), {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:363:        const obligations = commitRollbackFailure(panel, {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:412:      const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:432:      const failure = agentPanelFailure("SerializeError", String(e), {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:439:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:469:          const failure = agentPanelFailure("ReconcileError", String(error), {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:506:        const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:581:        : agentPanelFailure("RejectError", String(e), {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:588:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:602:        failure_kind: failure.kind || "RejectError",
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:675:      throw agentPanelFailure("MissingRequiredField", "Cannot rebaseline without a session_id.", {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:746:          : agentPanelFailure("RebaselineError", String(e), {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:758:            failure_kind: failure.kind || null,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:870:      const normalizedFailure = failure && typeof failure === "object"
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:872:        : agentPanelFailure("RebaselineError", String(failure), {
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:879:        failure: normalizedFailure,
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:880:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, normalizedFailure, "frontend"),
vibecomfy/comfy_nodes/web/agent_rebaseline_undo.js:882:          recoveryForPanelState(extractRebaselineRecovery(normalizedFailure)) || panel.state.rebaselineRecovery,
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:114://   (unknown)           — no-op, returns { render: false }
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:466:      return _handleSubmitReadinessFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:469:      return _handleSubmitFailure(panel, {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:477:      return _handleSubmitFailure(panel, {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:486:      return _handleSubmitFailure(panel, {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:517:      return _handleSubmitNetworkFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:520:      return _handleSubmitNetworkFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:541:      return _handleArrivalSerializeFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:586:      return _handleChatRehydrateFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:596:      return _handleApplyBlockedFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:612:      return _handleCanvasApplyFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:631:      return _handlePrepareFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:640:      return _handleVerifyCanvasFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:649:      return _handleFinalizeFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:658:      return _handleRollbackFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:668:      return _handleRejectFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:685:      return _handleRebaselineFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:703:      return _handleStaleRecoveryRebaselineFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:713:      return _handleUndoRebaselineFailure(panel, payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:727:// `dirtySections` array. Throws for unknown render section names.
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:792://   - ``malformed_delta`` — structurally invalid envelope or op
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1500:function _handleSubmitReadinessFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1507:function _handleSubmitFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1544:function _handleSubmitNetworkFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1598:  const recoveryFailure = {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1610:  return _handleSubmitNetworkFailure(panel, { ...(payload || {}), failure: recoveryFailure });
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1863:function _handleArrivalSerializeFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1886:  // malformed/non-applyable. Override eligibility to block Apply with
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:1979:    ...(missingDurableEligibility ? { debug_branch: "malformed_metadata" } : {}),
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2645:        failure_kind: event.failure_kind || null,
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2748:export function projectCompensatedFailure(payload = {}) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2888:function _handleChatRehydrateFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2916:function _handleApplyBlockedFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2987:function _handleCanvasApplyFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:2988:  const compensation = projectCompensatedFailure(payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3133:function _handlePrepareFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3134:  const compensation = projectCompensatedFailure(payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3195:function _handleVerifyCanvasFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3196:  const compensation = projectCompensatedFailure(payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3280:function _handleFinalizeFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3281:  const compensation = projectCompensatedFailure(payload);
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3358:function _handleRollbackFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3491:function _handleRejectFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3556:function _handleRebaselineFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3604:function _handleStaleRecoveryRebaselineFailure(panel, payload) {
vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3664:function _handleUndoRebaselineFailure(panel, payload) {
vibecomfy/fetch.py:121:        name = str(entry.get("name", "<unknown>"))
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:296:    throw _fail("Restoration strategy must be an object", "malformed_restoration_payload");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:300:    throw _fail("Unknown restoration strategy tag", "unknown_restoration_strategy");
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
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:456:    throw _fail("compensation must use baseline_snapshot_v1", "unknown_restoration_strategy");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:463:    throw _fail("compensation ref must be a non-empty string", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:467:    throw _fail("compensation fence must be an object", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:472:    throw _fail("compensation fence key set is not closed", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:475:    throw _fail("compensation generation must be a positive int", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:479:      throw _fail(`compensation fence ${key} must be non-empty string`, "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:484:      throw _fail(`compensation fence ${key} must be hex64`, "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:567:  if (!raw || raw.contract_version !== contract) { throw _fail("Unsupported authority version.", "unknown_authority_version"); }
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:569:  if (raw.authority_receipt_contract_version !== AUTHORITY_RECEIPT_CONTRACT_VERSION) { throw _fail("Authority receipt contract version must be explicit.", "unknown_authority_receipt_version"); }
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:574:  if (!["structural", "layout"].includes(raw.operation_family)) { throw _fail("Unknown operation family.", "unknown_operation_family"); }
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:632:    throw _fail("restoration_strategy_compensation may not be null.", "malformed_restoration_compensation");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:648://   * A malformed legacy shape (missing/typed restoration_strategy, unknown
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:657:    throw _fail("Legacy restoration_strategy carries an unknown tag.", "unknown_restoration_strategy");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:662:    throw _fail("Legacy restoration payload and ref are mutually exclusive.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:665:    throw _fail("Legacy restoration requires payload or ref.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:669:      throw _fail("Legacy baseline_snapshot_v1 restoration must use ref.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:672:      throw _fail("Legacy baseline_snapshot_v1 ref must be a non-empty string.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:678:    throw _fail("Legacy inverse restoration must use payload.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:681:    throw _fail("Legacy inverse restoration payload must be an object.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:691:    throw _fail("Legacy authority must be an object.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:694:    throw _fail("Not a candidate_authority_v0_legacy envelope.", "unknown_authority_version");
vibecomfy/comfy_nodes/web/prepared_authority_v1.js:698:    throw _fail("Legacy authority requires a restoration_strategy object.", "malformed_legacy_authority");
vibecomfy/comfy_nodes/web/agent_apply_flow.js:9:    agentPanelFailure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:23:    commitFinalizeFailure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:26:    commitPrepareFailure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:29:    commitVerifyCanvasFailure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:32:    compensatedFailurePayload,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:54:    recoveryForFailure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:92:      throw agentPanelFailure("CanvasApplyError", "The live LiteGraph instance does not support in-place graph application.", {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:238:      const failure = agentPanelFailure("MissingRequiredField", "Cannot apply a candidate without session_id and turn_id.", {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:261:      const failure = agentPanelFailure("ScopeMismatch", `Apply blocked: ${applyScopeCheck.reason || "scope/session inconsistency"}.`, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:313:        const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:339:          const failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas before Apply: ${String(e)}`, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:366:          const failure = agentPanelFailure("StaleStateMismatch", String(error?.message || error), {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:385:          const failure = agentPanelFailure("StaleStateMismatch", eligibility.message || "Apply is blocked for this candidate.", {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:474:                triggerFailure: error,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:487:                  triggerFailure: error,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:500:            : agentPanelFailure("PrepareError", String(error), {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:506:          const compensation = compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:517:              || recoveryForFailure(failure, panel, prepareBody),
vibecomfy/comfy_nodes/web/agent_apply_flow.js:519:          const obligations = commitPrepareFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:569:                triggerFailure: localPrecheck,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:572:              const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:588:              const obligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:589:                ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:632:              triggerFailure: error,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:639:          const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:651:          const obligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:652:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:710:            triggerFailure: error,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:713:          const failure = agentPanelFailure("CanvasApplyError", String(error), {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:726:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:757:            triggerFailure: serializeErr,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:760:          const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:770:          const serializeObligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:771:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:799:            triggerFailure: localPostcheck,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:802:          const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:813:          const obligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:814:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:868:            triggerFailure: error,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:871:          const failure = agentPanelFailure("StaleStateMismatch", String(error?.message || error), {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:877:          const obligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:878:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:911:            triggerFailure: {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:917:          const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:929:          const hashObligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:930:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:962:            triggerFailure: {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:970:          const failure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:985:          const obligations = commitVerifyCanvasFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:986:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1119:            const projectionFailure = boundedBrowserTransactionError(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1132:                  post_finalize_projection_failure: projectionFailure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1150:            : agentPanelFailure("FinalizeError", String(error), {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1163:            triggerFailure: failure,
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1170:          const obligations = commitFinalizeFailure(panel, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1171:            ...compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1208:    const legacyFailure = agentPanelFailure(
vibecomfy/comfy_nodes/web/agent_apply_flow.js:1218:      failure: legacyFailure,
vibecomfy/comfy_nodes/web/native_normalization_ledger.md:12:rows, unknown enum values, placeholder metadata, and unknown keys.
vibecomfy/comfy_nodes/web/projection_registry_v1.js:285:      error.code = "malformed_link";
vibecomfy/comfy_nodes/web/projection_registry_v1.js:317:    error.code = "unknown_projection_version";
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:30:  const status = entry?.status || "unknown";
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:38:    || entry?.failure_kind
vibecomfy/comfy_nodes/web/agent_turn_reducer.js:106:    failure_kind: event.failure_kind || null,
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:42:  "failure_kind",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:53:/** Proof states: pass, fail, not_run, unknown.  Missing proof is never success. */
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:58:  "unknown",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:87:  "unknown",
vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js:109:  "malformed_delta",
vibecomfy/comfy_backend.py:60:    All fields are required; missing / malformed JSON raises immediately
vibecomfy/comfy_backend.py:304:        reason_code="comfyui_version_unknown",
vibecomfy/comfy_nodes/web/panel_runtime.js:201:  "__renderFailureCounts",
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
vibecomfy/comfy_nodes/web/layout_operation_v1.js:238:    throw _fail("Unknown layout operation contract version", "unknown_contract");
vibecomfy/comfy_nodes/web/layout_operation_v1.js:260:    throw _fail("layout operation envelope must be an object", "malformed_layout_operation");
vibecomfy/comfy_nodes/web/panel_thread.js:420:      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
vibecomfy/comfy_nodes/web/panel_thread.js:542:export function appendFailureDetail(body, panel, snapshot = null, deps = {}) {
vibecomfy/comfy_nodes/web/panel_thread.js:554:  appendTextLine(body, `${failure.kind || "Error"} @ ${failure.stage || "unknown"}`, "#ffd6d6");
vibecomfy/comfy_nodes/web/panel_thread.js:564:      `backend stage: ${stageInfo.stage || "unknown"}${stageInfo.progress != null ? ` (${stageInfo.progress})` : ""}`,
vibecomfy/comfy_nodes/web/panel_thread.js:655:    appendTextLine(body, `Applied turn ${queueGuard.activeContext.turnId || "unknown"} remains queue-blocked.`, "#ff7f7f");
vibecomfy/comfy_nodes/web/panel_thread.js:1335:    appendFailureDetail,
vibecomfy/comfy_nodes/web/panel_thread.js:1439:  const failureSection = createBubbleDetailSection("Failure");
vibecomfy/comfy_nodes/web/panel_thread.js:1440:  appendFailureDetail(failureSection.body, panel, ordinarySnapshot);
vibecomfy/comfy_nodes/web/panel_thread.js:2405:  const statusBadge = el("span", isPending ? "in progress" : (entry.status || "unknown"));
vibecomfy/comfy_nodes/web/panel_thread.js:2430:  if (entry.failure_kind) {
vibecomfy/comfy_nodes/web/panel_thread.js:2431:    appendTextLine(turnCard, `${entry.failure_kind}${entry.failure_stage ? ` @ ${entry.failure_stage}` : ""}`, "#ffb86c");
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:36:  unknown: TRANSACTION_STATE.SUPERSEDED,
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:61:  // Apply must never trust malformed authority. Reject is different: it only
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:177:      // A malformed aggregate is not downgraded to legacy browser state.
vibecomfy/comfy_nodes/web/agent_edit_transaction.js:319:    substage: String(substage || "unknown").slice(0, 128),
vibecomfy/comfy_nodes/web/panel_overlay.js:17:  return `${candidateHash}:${liveRevision == null ? "unknown" : liveRevision}${deltaDerivedTag}`;
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:33:  appendFailureDetail as appendFailureDetailImpl,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:92:  projectCompensatedFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:102:  commitPrepareFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:105:  commitVerifyCanvasFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:108:  commitFinalizeFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:111:  commitRollbackFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:383:// ── Failure Envelope (4xx/5xx) ────────────────────────────────────────────
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:386://   kind: FailureKind — see agent_contracts.py FailureKind enum:
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:387://     SyntaxError, ASTScanFailure, OversizedPayload, MalformedModelJSON,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:393://     EditorOnlyNodeQueueBlocker, AuditWriteWarning, AuditWriteFailure
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:410:// matching FailureKind.
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:482:  agentPanelFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:515:  agentPanelFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:529:  commitFinalizeFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:532:  commitPrepareFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:535:  commitVerifyCanvasFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:538:  compensatedFailurePayload,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:561:  recoveryForFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:2117:  let version = "unknown";
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:2121:    version = stats?.system?.comfyui_frontend_package || "unknown";
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:2123:    version = "unknown";
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:2126:  if (version === "unknown" || !String(version).startsWith(major)) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:2872:  const nodeId = detail.node_id || "unknown";
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:2985:          `Node ${node?.id || "unknown"} (${classType}) is an editor-only intent node and cannot be queued until it is lowered.`,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3136:function recoveryForFailure(payload, panel = null, actionBody = null) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3137:  const extracted = readRebaselineRecovery(payload, { endpoint: "recoveryForFailure", allowLegacy: true });
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:3896:    __renderFailureCounts: {},
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4745:  "unknown",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:4843:    failure_kind: extra.failure_kind || null,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5399:  return `legacy:${index}:${role || "unknown"}:${textSlice}`;
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5722:function syntheticFailureAgentMessage(panel, failure, fallbackStage = "frontend") {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5746:    failure_kind: kind,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5755:function compensatedFailurePayload(panel, failure, {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5763:    || recoveryForFailure(failure, panel, actionBody)
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5772:  return projectCompensatedFailure({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:5777:    syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, fallbackStage),
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6140:    appendFailureDetail,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6159:    appendFailureDetail,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6247:    renderFailureCounts: panel?.__renderFailureCounts && typeof panel.__renderFailureCounts === "object"
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6248:      ? { ...panel.__renderFailureCounts }
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6300:    appendFailureDetail,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6333:      text: `removed_named: ${item.uid} (${item.class_type || "unknown"})`,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6340:      text: `virtual_wires_degraded: ${item.uid || item.node_id || "unknown"}`,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6350:    const uid = item?.uid || item?.source_node_uid || "unknown";
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6405:      label: `Removed ${item?.uid || "unknown"} (${item?.class_type || "unknown"})`,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6418:      label: `Virtual wire degraded ${uid || "unknown"}`,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6849:          message: `Queue blocked for turn ${blockInfo.turnId || "unknown"} because queue_allowed=false.`,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6895:function appendFailureDetail(body, panel, snapshot = null) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6896:  return appendFailureDetailImpl(body, panel, snapshot, {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:6966:          status: event.status || "unknown",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7284:    frontendVersion: typeof SUPPORTED_FRONTEND === "string" ? SUPPORTED_FRONTEND : "unknown",
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7407:    appendFailureDetail,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7474:  if (!panel.__renderFailureCounts || typeof panel.__renderFailureCounts !== "object") {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7475:    panel.__renderFailureCounts = {};
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7477:  const nextCount = (panel.__renderFailureCounts[section] || 0) + 1;
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7478:  panel.__renderFailureCounts[section] = nextCount;
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7494:  if (!panel?.__renderFailureCounts || typeof section !== "string" || !section) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7497:  delete panel.__renderFailureCounts[section];
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:7596:function agentPanelFailure(kind, message, extra = {}) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8056:        const failure = agentPanelFailure("ScopeMismatch", "The active canvas scope does not match the panel scope. Submit is blocked.", {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8081:      const failure = agentPanelFailure("MissingTask", "Enter an edit instruction before submitting.", {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8087:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8130:      const failure = agentPanelFailure("SerializeError", String(e), {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8137:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8223:        const failureContextForAttempt = (extras = {}) => submitFlow.buildSubmitFailureContext(panel, snapshot, {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8258:              throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8265:                ...failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8289:            const backendFailure = result.raw && typeof result.raw === "object"
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8290:              ? submitFlow.markBackendSubmitFailure(
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8291:                  submitFlow.mergeSubmitFailureContext(
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8293:                    failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8299:              : submitFlow.markBackendSubmitFailure(
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8300:                  submitFlow.mergeSubmitFailureContext(
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8305:                    failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8311:            throw backendFailure;
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8317:            throw agentPanelFailure("MalformedResponse", "The backend returned an incomplete candidate envelope.", {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8323:              ...failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8335:          const failure = submitFlow.normalizeSubmitFailure(
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8337:            failureContextForAttempt({
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8348:          if (submitFlow.shouldAutoRetrySubmitFailure(error, failure, { attemptIndex, maxAutomaticRetryCount: automaticRetryCount })) {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8396:      const failure = submitFlow.normalizeSubmitFailure(
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8398:        submitFlow.buildSubmitFailureContext(panel, snapshot, {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8407:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8416:        failure_kind: failure.kind,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8576:      const failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas after the candidate arrived: ${String(e)}`, {
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8585:        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8810:  agentPanelFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8822:  commitRollbackFailure,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js:8844:  syntheticFailureAgentMessage,

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/contracts.py | sed -n '1,280p'; nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '1,360p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1,460p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 149ms:
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
   261	):
   262	    """Construct the tool-free single-shot AgentRequest for a panel turn.
   263
   264	    Tool-free single-shot: empty ``toolsets`` in metadata -> the DeepSeekAdapter
   265	    does not enable any toolset, and the parent kwargs already carry
   266	    ``enabled_toolsets=[]`` / ``max_iterations=1``. No ``output_schema`` /
   267	    ``response_format``: the panel parses its own python/delta/batch fences from
   268	    the raw text, so the adapter returns ``raw_output`` unchanged.
   269	    """
   270	    from arnold.agent import AgentRequest
   271
   272	    return AgentRequest(
   273	        agent=agent_id,
   274	        mode="default",
   275	        model=model,
   276	        resolved_model=model,
   277	        effort=effort,
   278	        prompt=user_message,
   279	        system_prompt=system_message,
   280	        read_only=True,
   281	        metadata={"toolsets": []},
   282	    )
   283
   284
   285	def _dispatch_turn(
   286	    *,
   287	    agent_id: str,
   288	    agent_kwargs: dict,
   289	    user_message: str,
   290	    system_message: str | None,
   291	    model: str | None = None,
   292	    effort: str | None = None,
   293	) -> tuple[str, dict[str, Any]]:
   294	    """Run one agent turn through the Arnold dispatch seam; return raw text.
   295
   296	    * ``hermes`` (DeepSeek): the parent resolved the full DeepSeek kwargs
   297	      (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
   298	      flags). The module-level default ``DeepSeekAdapter()`` reads only from
   299	      ``HERMES_API_KEY``/``OPENAI_API_KEY`` + metadata, so it would NOT carry the
   300	      parent's DeepSeek configuration through. We therefore register a dedicated
   301	      :class:`DeepSeekAdapter` on a local dispatcher whose ``AIAgent`` factory
   302	      merges those kwargs verbatim — reproducing the exact construction the
   303	      worker used before the dispatch seam existed.
   304	    * ``codex`` / ``claude`` (and any other id): dispatch through the *default*
   305	      dispatcher (``arnold.agent.dispatch``). The adapters for those ids are
   306	      registered by their owning components; if none is registered yet,
   307	      ``dispatch`` raises :class:`LookupError`, which the parent maps to the
   308	      runtime-unavailable signal. We never silently route them through DeepSeek.
   309	    """
   310	    _anchor_agent_package_on_syspath()
   311	    request = _build_request(
   312	        agent_id=agent_id,
   313	        user_message=user_message,
   314	        system_message=system_message,
   315	        model=model,
   316	        effort=effort,
   317	    )
   318
   319	    if agent_id == "hermes":
   320	        from arnold.agent import ArnoldDispatcher
   321	        from arnold.agent.adapters.deepseek import DeepSeekAdapter
   322	        from arnold.agent.run_agent import AIAgent
   323	        import arnold.agent.run_agent as run_agent_module
   324
   325	        usage_tracker: dict[str, Any] = {
   326	            "usage": empty_deepseek_usage(),
   327	            "cache_breakout_calls": 0,
   328	        }
   329	        last_result: dict[str, Any] = {}
   330
   331	        def _usage_int(raw: Any, *names: str) -> int | None:
   332	            candidates: list[Any] = [raw]
   333	            if hasattr(raw, "model_extra"):
   334	                candidates.append(getattr(raw, "model_extra"))
   335	            for candidate in candidates:
   336	                if candidate is None:
   337	                    continue
   338	                for name in names:
   339	                    if isinstance(candidate, dict):
   340	                        value = candidate.get(name)
   341	                    else:
   342	                        value = getattr(candidate, name, None)
   343	                    if value is None:
   344	                        continue
   345	                    try:
   346	                        return max(0, int(value))
   347	                    except (TypeError, ValueError):
   348	                        continue
   349	            return None
   350
   351	        def _prompt_tokens_details(raw: Any) -> Any:
   352	            details = getattr(raw, "prompt_tokens_details", None)
   353	            if details is not None:
   354	                return details
   355	            if isinstance(raw, dict):
   356	                return raw.get("prompt_tokens_details")
   357	            model_extra = getattr(raw, "model_extra", None)
   358	            if isinstance(model_extra, dict):
   359	                return model_extra.get("prompt_tokens_details")
   360	            return None
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
   191	    for key, value in _read_env_file_entries(path):
   192	        values[key] = value
   193	    return values
   194
   195
   196	def _load_env_file_into_environ(path: Path = _HERMES_ENV_PATH) -> None:
   197	    """Best-effort: hydrate os.environ from ~/.hermes/.env without overwriting.
   198
   199	    The browser credential route writes ``OPENROUTER_API_KEY=...`` here, so a
   200	    ComfyUI process started without the key in its environment still picks it up.
   201	    """
   202	    for key, value in _read_env_file(path).items():
   203	        if key and key not in os.environ:
   204	            os.environ[key] = value
   205
   206
   207	# Hydrate on import so credential presence + provider calls see the stored key.
   208	_load_env_file_into_environ()
   209
   210
   211	def _resolve_openrouter_key() -> str | None:
   212	    # Re-read the env file each call so a freshly browser-submitted key is seen
   213	    # without restarting the server. Duplicate OPENROUTER_API_KEY lines can
   214	    # exist; prefer the OpenRouter-shaped key over stale generic sk-* entries.
   215	    file_values = _read_env_file()
   216	    for key, value in file_values.items():
   217	        if key and value and key not in os.environ:
   218	            os.environ[key] = value
   219	    file_keys = [
   220	        value.strip()
   221	        for key, value in _read_env_file_entries()
   222	        if key == "OPENROUTER_API_KEY" and value.strip()
   223	    ]
   224	    for file_key in file_keys:
   225	        if file_key.startswith("sk-or-"):
   226	            os.environ["OPENROUTER_API_KEY"] = file_key
   227	            return file_key
   228	    if file_keys:
   229	        os.environ["OPENROUTER_API_KEY"] = file_keys[-1]
   230	    _load_env_file_into_environ()
   231	    candidates: list[tuple[str, str]] = []
   232	    for key, value in file_values.items():
   233	        if key == "OPENROUTER_API_KEY" or key.startswith("OPENROUTER_API_KEY_"):
   234	            value = value.strip()
   235	            if value:
   236	                candidates.append((key, value))
   237	    for key, value in os.environ.items():
   238	        if key == "OPENROUTER_API_KEY" or key.startswith("OPENROUTER_API_KEY_"):
   239	            value = value.strip()
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
   326
   327
   328	def _agent_id_for_route(route: str | None) -> str:
   329	    """Map a panel route name to the arnold dispatch agent id.
   330
   331	    Unlike :func:`_normalize_route`, this keeps anthropic/openai-codex distinct
   332	    so the worker can dispatch to the correct (eventual) adapter. ``auto`` and
   333	    bare ``arnold`` fall back to ``hermes`` (the only registered backend).
   334	    """
   335	    requested = (route or "").strip().lower()
   336	    if requested == "claude":
   337	        requested = "anthropic"
   338	    elif requested == "codex":
   339	        requested = "openai-codex"
   340	    if requested in {"", "auto", "arnold", "hermes"}:
   341	        return "hermes"
   342	    return _ROUTE_TO_AGENT_ID.get(requested, "unknown")
   343
   344
   345	def _default_model_for_route(route: str, model: str | None) -> str:
   346	    normalized_route = _normalize_route(route)
   347	    if normalized_route == "unknown":
   348	        return "unknown"
   349	    if _is_real_model_override(model):
   350	        return _strip_provider_prefix(model, "openrouter")
   351	    if normalized_route == "openrouter":
   352	        return _strip_provider_prefix(_OPENROUTER_MODEL, "openrouter")
   353	    return _ARNOLD_MODEL
   354
   355
   356	def _is_real_model_override(model: str | None) -> bool:
   357	    """True when *model* is an actual provider model, not the panel contract id."""
   358	    normalized = (model or "").strip()
   359	    return bool(normalized and normalized != "agent-edit")
   360
   361
   362	def _runtime_model_for_route(route: str | None, model: str | None) -> str | None:
   363	    """Return the model slug to hand to the provider adapter.
   364
   365	    The browser/status contract historically used ``agent-edit`` as a product
   366	    label.  That is not a valid OpenRouter/Anthropic/Codex model id, so keep it
   367	    out of the provider seam and let the route resolve its real default.
   368	    """
   369	    normalized_route = _normalize_route(route)
   370	    if normalized_route == "unknown":
   371	        return None
   372	    # Explicit per-process force-override: when set, ignore the profile/judge
   373	    # model slug and route everything through this model (e.g. swapping the
   374	    # hermes backend to a non-DeepSeek OpenAI-compatible endpoint). No-op unset.
   375	    forced_model = os.getenv("VIBECOMFY_FORCE_MODEL")
   376	    if forced_model:
   377	        return forced_model
   378	    if _is_real_model_override(model):
   379	        return model
   380	    if normalized_route == "openrouter":
   381	        return _OPENROUTER_MODEL
   382	    if normalized_route in {"arnold", "anthropic", "openai-codex"}:
   383	        return _ARNOLD_MODEL
   384	    return None
   385
   386
   387	def _strip_provider_prefix(model: str, provider: str) -> str:
   388	    prefix = f"{provider}:"
   389	    return model.split(":", 1)[1] if model.lower().startswith(prefix) else model
   390
   391
   392	def _normalize_native_deepseek_model(model: str) -> str:
   393	    """Strip provider prefixes DeepSeek's native API rejects.
   394
   395	    Native ``api.deepseek.com`` only accepts bare model names
   396	    (``deepseek-v4-pro`` / ``deepseek-v4-flash``).  OpenRouter-style slugs like
   397	    ``openrouter:deepseek/deepseek-v4-flash`` or ``deepseek/deepseek-v4-flash``
   398	    (which the executor profile ships) are rejected with HTTP 400
   399	    "The supported API model names are deepseek-v4-pro or deepseek-v4-flash, but
   400	    you passed deepseek/deepseek-v4-flash."  Strip both the ``openrouter:``
   401	    route prefix and any ``deepseek/`` provider segment when pointed at the
   402	    native endpoint.
   403	    """
   404	    stripped = _strip_provider_prefix(model, "openrouter")
   405	    # Drop a leading "deepseek/" provider segment (OpenRouter-format slug).
   406	    if "/" in stripped:
   407	        provider_seg, _, model_seg = stripped.partition("/")
   408	        if provider_seg.lower() == "deepseek" and model_seg:
   409	            stripped = model_seg
   410	    return stripped
   411
   412
   413	def _base_url_for_route(route: str | None) -> str:
   414	    """Pin explicit OpenRouter turns to OpenRouter's canonical API endpoint."""
   415	    if (route or "").strip().lower() == "openrouter":
   416	        return _CANONICAL_OPENROUTER_BASE_URL
   417	    return _OPENROUTER_BASE_URL
   418
   419
   420	def _is_native_deepseek_endpoint(base_url: str | None = None) -> bool:
   421	    return "deepseek.com" in (base_url or _OPENROUTER_BASE_URL or "").lower()
   422
   423
   424	def _hermes_credential_for(route: str | None, model: str | None) -> str | None:
   425	    if (route or "").strip().lower() == "openrouter":
   426	        return _resolve_openrouter_key()
   427	    # Explicit per-process override (e.g. pointing the hermes backend at a
   428	    # non-OpenRouter OpenAI-compatible endpoint such as Fireworks). Bypasses
   429	    # _resolve_openrouter_key(), which force-clobbers OPENROUTER_API_KEY from
   430	    # ~/.hermes/.env and would ignore a freshly-exported key. No-op when unset.
   431	    explicit_key = os.getenv("VIBECOMFY_HERMES_API_KEY")
   432	    if explicit_key:
   433	        return explicit_key
   434	    # When pointed at DeepSeek's native API, prefer DEEPSEEK_API_KEY directly so a
   435	    # stale OpenRouter ``sk-or-*`` pool key in ~/.hermes/.env can't win —
   436	    # _resolve_openrouter_key() force-prefers any sk-or-* entry it finds there.
   437	    if _is_native_deepseek_endpoint() and os.getenv("DEEPSEEK_API_KEY"):
   438	        return os.getenv("DEEPSEEK_API_KEY")
   439	    return _resolve_openrouter_key()
   440
   441
   442	def _has_arnold_credential() -> bool:
   443	    return bool(
   444	        os.getenv("ANTHROPIC_API_KEY")
   445	        or os.getenv("ANTHROPIC_TOKEN")
   446	        or os.getenv("OPENROUTER_API_KEY")
   447	        or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
   448	        or Path("~/.claude/.credentials.json").expanduser().exists()
   449	        or Path("~/.hermes/.anthropic_oauth.json").expanduser().exists()
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

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '100,310p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '520,820p'; nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '820,1120p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
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
   261	):
   262	    """Construct the tool-free single-shot AgentRequest for a panel turn.
   263
   264	    Tool-free single-shot: empty ``toolsets`` in metadata -> the DeepSeekAdapter
   265	    does not enable any toolset, and the parent kwargs already carry
   266	    ``enabled_toolsets=[]`` / ``max_iterations=1``. No ``output_schema`` /
   267	    ``response_format``: the panel parses its own python/delta/batch fences from
   268	    the raw text, so the adapter returns ``raw_output`` unchanged.
   269	    """
   270	    from arnold.agent import AgentRequest
   271
   272	    return AgentRequest(
   273	        agent=agent_id,
   274	        mode="default",
   275	        model=model,
   276	        resolved_model=model,
   277	        effort=effort,
   278	        prompt=user_message,
   279	        system_prompt=system_message,
   280	        read_only=True,
   281	        metadata={"toolsets": []},
   282	    )
   283
   284
   285	def _dispatch_turn(
   286	    *,
   287	    agent_id: str,
   288	    agent_kwargs: dict,
   289	    user_message: str,
   290	    system_message: str | None,
   291	    model: str | None = None,
   292	    effort: str | None = None,
   293	) -> tuple[str, dict[str, Any]]:
   294	    """Run one agent turn through the Arnold dispatch seam; return raw text.
   295
   296	    * ``hermes`` (DeepSeek): the parent resolved the full DeepSeek kwargs
   297	      (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
   298	      flags). The module-level default ``DeepSeekAdapter()`` reads only from
   299	      ``HERMES_API_KEY``/``OPENAI_API_KEY`` + metadata, so it would NOT carry the
   300	      parent's DeepSeek configuration through. We therefore register a dedicated
   301	      :class:`DeepSeekAdapter` on a local dispatcher whose ``AIAgent`` factory
   302	      merges those kwargs verbatim — reproducing the exact construction the
   303	      worker used before the dispatch seam existed.
   304	    * ``codex`` / ``claude`` (and any other id): dispatch through the *default*
   305	      dispatcher (``arnold.agent.dispatch``). The adapters for those ids are
   306	      registered by their owning components; if none is registered yet,
   307	      ``dispatch`` raises :class:`LookupError`, which the parent maps to the
   308	      runtime-unavailable signal. We never silently route them through DeepSeek.
   309	    """
   310	    _anchor_agent_package_on_syspath()
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

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '285,620p'; rg -n \"model_attempts|ModelAttemptEvidence|coerce_model_attempts\" vibecomfy/comfy_nodes/agent/provider.py vibecomfy/executor/agent_backend.py vibecomfy/executor/core.py vibecomfy/agent/artifacts.py tests/live_agentic_harness/adapter.py tests/live_agentic_harness/runner.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   285	def _dispatch_turn(
   286	    *,
   287	    agent_id: str,
   288	    agent_kwargs: dict,
   289	    user_message: str,
   290	    system_message: str | None,
   291	    model: str | None = None,
   292	    effort: str | None = None,
   293	) -> tuple[str, dict[str, Any]]:
   294	    """Run one agent turn through the Arnold dispatch seam; return raw text.
   295
   296	    * ``hermes`` (DeepSeek): the parent resolved the full DeepSeek kwargs
   297	      (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
   298	      flags). The module-level default ``DeepSeekAdapter()`` reads only from
   299	      ``HERMES_API_KEY``/``OPENAI_API_KEY`` + metadata, so it would NOT carry the
   300	      parent's DeepSeek configuration through. We therefore register a dedicated
   301	      :class:`DeepSeekAdapter` on a local dispatcher whose ``AIAgent`` factory
   302	      merges those kwargs verbatim — reproducing the exact construction the
   303	      worker used before the dispatch seam existed.
   304	    * ``codex`` / ``claude`` (and any other id): dispatch through the *default*
   305	      dispatcher (``arnold.agent.dispatch``). The adapters for those ids are
   306	      registered by their owning components; if none is registered yet,
   307	      ``dispatch`` raises :class:`LookupError`, which the parent maps to the
   308	      runtime-unavailable signal. We never silently route them through DeepSeek.
   309	    """
   310	    _anchor_agent_package_on_syspath()
   311	    request = _build_request(
   312	        agent_id=agent_id,
   313	        user_message=user_message,
   314	        system_message=system_message,
   315	        model=model,
   316	        effort=effort,
   317	    )
   318
   319	    if agent_id == "hermes":
   320	        from arnold.agent import ArnoldDispatcher
   321	        from arnold.agent.adapters.deepseek import DeepSeekAdapter
   322	        from arnold.agent.run_agent import AIAgent
   323	        import arnold.agent.run_agent as run_agent_module
   324
   325	        usage_tracker: dict[str, Any] = {
   326	            "usage": empty_deepseek_usage(),
   327	            "cache_breakout_calls": 0,
   328	        }
   329	        last_result: dict[str, Any] = {}
   330
   331	        def _usage_int(raw: Any, *names: str) -> int | None:
   332	            candidates: list[Any] = [raw]
   333	            if hasattr(raw, "model_extra"):
   334	                candidates.append(getattr(raw, "model_extra"))
   335	            for candidate in candidates:
   336	                if candidate is None:
   337	                    continue
   338	                for name in names:
   339	                    if isinstance(candidate, dict):
   340	                        value = candidate.get(name)
   341	                    else:
   342	                        value = getattr(candidate, name, None)
   343	                    if value is None:
   344	                        continue
   345	                    try:
   346	                        return max(0, int(value))
   347	                    except (TypeError, ValueError):
   348	                        continue
   349	            return None
   350
   351	        def _prompt_tokens_details(raw: Any) -> Any:
   352	            details = getattr(raw, "prompt_tokens_details", None)
   353	            if details is not None:
   354	                return details
   355	            if isinstance(raw, dict):
   356	                return raw.get("prompt_tokens_details")
   357	            model_extra = getattr(raw, "model_extra", None)
   358	            if isinstance(model_extra, dict):
   359	                return model_extra.get("prompt_tokens_details")
   360	            return None
   361
   362	        def _record_usage(raw_usage: Any, canonical_usage: Any) -> None:
   363	            prompt_tokens = _usage_int(raw_usage, "prompt_tokens")
   364	            completion_tokens = _usage_int(raw_usage, "completion_tokens")
   365	            total_tokens = _usage_int(raw_usage, "total_tokens")
   366	            if prompt_tokens is None:
   367	                prompt_tokens = max(0, int(getattr(canonical_usage, "prompt_tokens", 0) or 0))
   368	            if completion_tokens is None:
   369	                completion_tokens = max(0, int(getattr(canonical_usage, "output_tokens", 0) or 0))
   370	            if total_tokens is None:
   371	                total_tokens = prompt_tokens + completion_tokens
   372
   373	            cache_hit_tokens = _usage_int(raw_usage, "prompt_cache_hit_tokens")
   374	            cache_miss_tokens = _usage_int(raw_usage, "prompt_cache_miss_tokens")
   375	            cache_breakout_available = (
   376	                cache_hit_tokens is not None or cache_miss_tokens is not None
   377	            )
   378	            if not cache_breakout_available:
   379	                details = _prompt_tokens_details(raw_usage)
   380	                cached_tokens = _usage_int(details, "cached_tokens")
   381	                if cached_tokens is not None:
   382	                    cache_hit_tokens = cached_tokens
   383	                    cache_miss_tokens = max(0, prompt_tokens - cached_tokens)
   384	                    cache_breakout_available = True
   385	            if cache_breakout_available:
   386	                usage_tracker["cache_breakout_calls"] += 1
   387
   388	            usage_tracker["usage"] = add_deepseek_usage(
   389	                usage_tracker["usage"],
   390	                {
   391	                    "prompt_tokens": prompt_tokens,
   392	                    "completion_tokens": completion_tokens,
   393	                    "total_tokens": total_tokens,
   394	                    "prompt_cache_hit_tokens": cache_hit_tokens or 0,
   395	                    "prompt_cache_miss_tokens": cache_miss_tokens or 0,
   396	                    "n_calls": 1,
   397	                },
   398	            )
   399
   400	        original_normalize_usage = run_agent_module.normalize_usage
   401
   402	        def _tracking_normalize_usage(
   403	            response_usage: Any,
   404	            *,
   405	            provider: str | None = None,
   406	            api_mode: str | None = None,
   407	        ):
   408	            canonical_usage = original_normalize_usage(
   409	                response_usage,
   410	                provider=provider,
   411	                api_mode=api_mode,
   412	            )
   413	            try:
   414	                _record_usage(response_usage, canonical_usage)
   415	            except Exception:
   416	                pass
   417	            return canonical_usage
   418
   419	        class _TrackingAIAgent(AIAgent):
   420	            def run_conversation(self, *args, **kwargs):
   421	                result = super().run_conversation(*args, **kwargs)
   422	                if isinstance(result, dict):
   423	                    last_result.clear()
   424	                    last_result.update(result)
   425	                return result
   426
   427	        def _factory(**adapter_kwargs):
   428	            # Start from the adapter's resolved kwargs (toolsets/session_db_path
   429	            # it derives from the request), then let the PARENT-resolved values
   430	            # win — the parent deliberately resolved the panel's proven DeepSeek
   431	            # config (model=deepseek-v4-pro, provider, base_url, api_key,
   432	            # max_tokens). The adapter's generic default model
   433	            # ("deepseek/deepseek-chat") is NOT a valid DeepSeek API name, so it
   434	            # must never override the parent's model.
   435	            merged = dict(adapter_kwargs)
   436	            for key, value in agent_kwargs.items():
   437	                if value is not None:
   438	                    merged[key] = value
   439	            return _TrackingAIAgent(**merged)
   440
   441	        dispatcher = ArnoldDispatcher()
   442	        dispatcher.register(agent_id, DeepSeekAdapter(agent_factory=_factory))
   443	        run_agent_module.normalize_usage = _tracking_normalize_usage
   444	        try:
   445	            result = dispatcher.dispatch(request)
   446	        finally:
   447	            run_agent_module.normalize_usage = original_normalize_usage
   448
   449	        tracked_usage = coerce_deepseek_usage(usage_tracker["usage"])
   450	        if tracked_usage["n_calls"] <= 0 and last_result:
   451	            tracked_usage = coerce_deepseek_usage(
   452	                {
   453	                    "prompt_tokens": last_result.get("prompt_tokens"),
   454	                    "completion_tokens": last_result.get("completion_tokens"),
   455	                    "total_tokens": last_result.get("total_tokens"),
   456	                    "prompt_cache_hit_tokens": last_result.get("cache_read_tokens"),
   457	                    "prompt_cache_miss_tokens": last_result.get("input_tokens"),
   458	                    "n_calls": last_result.get("api_calls"),
   459	                }
   460	            )
   461	            usage_tracker["cache_breakout_calls"] = tracked_usage["n_calls"]
   462	        finish_reason: str | None = None
   463	        if last_result:
   464	            # Prefer the last assistant message's finish_reason (the run
   465	            # result's own key is only populated for some API modes).
   466	            for msg in reversed(last_result.get("messages") or []):
   467	                if not isinstance(msg, dict):
   468	                    continue
   469	                value = msg.get("finish_reason")
   470	                if isinstance(value, str) and value.strip():
   471	                    finish_reason = value.strip()
   472	                    break
   473	            if finish_reason is None:
   474	                value = last_result.get("finish_reason")
   475	                if isinstance(value, str) and value.strip():
   476	                    finish_reason = value.strip()
   477	        metadata: dict[str, Any] = {
   478	            "deepseek_usage": tracked_usage,
   479	            "deepseek_cache_breakout_complete": (
   480	                tracked_usage["n_calls"] > 0
   481	                and usage_tracker["cache_breakout_calls"] >= tracked_usage["n_calls"]
   482	            ),
   483	        }
   484	        if finish_reason:
   485	            metadata["finish_reason"] = finish_reason
   486	        return result.raw_output or "", metadata
   487
   488	    # codex / claude / anything else: route through the shared default
   489	    # dispatcher. Raises LookupError if the adapter is not registered.
   490	    from arnold.agent import dispatch as _default_dispatch
   491
   492	    result = _default_dispatch(request)
   493	    return result.raw_output or "", {}
   494
   495
   496	def main() -> int:
   497	    if not logging.getLogger().handlers:
   498	        logging.basicConfig(level=logging.INFO)
   499	    request_path, result_path = sys.argv[1], sys.argv[2]
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
tests/live_agentic_harness/adapter.py:152:        "model_attempts": result.response.get("model_attempts", []),
tests/live_agentic_harness/runner.py:189:        "model_attempts": summary.get("model_attempts", []),
tests/live_agentic_harness/runner.py:194:    attempts = summary.get("model_attempts")
vibecomfy/agent/artifacts.py:31:    "model_attempts.json",
vibecomfy/agent/artifacts.py:336:    model_attempts = report.get("model_attempts")
vibecomfy/agent/artifacts.py:337:    if isinstance(model_attempts, (list, tuple)) and model_attempts:
vibecomfy/agent/artifacts.py:339:            output_dir / "model_attempts.json",
vibecomfy/agent/artifacts.py:340:            {"attempts": _redact(model_attempts)},
vibecomfy/agent/artifacts.py:342:        _append_manifest(manifest, "model_attempts.json")
vibecomfy/executor/agent_backend.py:29:    ModelAttemptEvidence,
vibecomfy/executor/agent_backend.py:30:    coerce_model_attempts,
vibecomfy/executor/agent_backend.py:78:        if result is not None and getattr(exc, "model_attempts", None) is None:
vibecomfy/executor/agent_backend.py:79:            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
vibecomfy/executor/agent_backend.py:104:    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts
vibecomfy/executor/agent_backend.py:106:    record_model_attempts(result.get("model_attempts"))
vibecomfy/executor/agent_backend.py:112:    attempts = list(coerce_model_attempts(result.get("model_attempts")))
vibecomfy/executor/agent_backend.py:121:    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
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
vibecomfy/comfy_nodes/agent/provider.py:16:    ModelAttemptEvidence,
vibecomfy/comfy_nodes/agent/provider.py:17:    coerce_model_attempts,
vibecomfy/comfy_nodes/agent/provider.py:207:    "model_attempts",
vibecomfy/comfy_nodes/agent/provider.py:228:    attempts = coerce_model_attempts(response.get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:230:        merged["model_attempts"] = [dict(item) for item in attempts]
vibecomfy/comfy_nodes/agent/provider.py:1397:    attempts = list(coerce_model_attempts(response.get("model_attempts")))
vibecomfy/comfy_nodes/agent/provider.py:1411:        revised_attempts.append(ModelAttemptEvidence.from_mapping(numbered).to_dict())
vibecomfy/comfy_nodes/agent/provider.py:1413:        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1415:        replace_last_model_attempts(revised_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1418:    exc.model_attempts = list(revised_attempts)  # type: ignore[attr-defined]
vibecomfy/comfy_nodes/agent/provider.py:1510:                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
vibecomfy/comfy_nodes/agent/provider.py:1517:                    ModelAttemptEvidence.from_mapping(numbered).to_dict()
vibecomfy/comfy_nodes/agent/provider.py:1521:                    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
vibecomfy/comfy_nodes/agent/provider.py:1523:                    replace_last_model_attempts(numbered_current_attempts)
vibecomfy/comfy_nodes/agent/provider.py:1528:                metadata["model_attempts"] = [*attempt_log, *numbered_current_attempts]

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/worker.py | sed -n '598,700p'; nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '180,250p'; nl -ba vibecomfy/comfy_nodes/agent/provider.py | sed -n '1350,1545p'; nl -ba vibecomfy/executor/agent_backend.py | sed -n '1,150p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 39ms:
   180	        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
   181	        if match:
   182	            stripped = match.group(1).strip()
   183	    try:
   184	        parsed = json.loads(stripped)
   185	    except json.JSONDecodeError as exc:
   186	        raise MalformedModelJSON(
   187	            "Agent response was not valid JSON with keys `python` and `message`."
   188	        ) from exc
   189	    if not isinstance(parsed, dict):
   190	        raise MalformedModelJSON("Agent response must be a JSON object.")
   191	    return parsed
   192
   193
   194	_BATCH_FENCE_RE = re.compile(r"```batch\s*\n(.*?)```", re.DOTALL)
   195
   196
   197	def _preview_raw_model_response(text: str | None, *, limit: int = 1200) -> str | None:
   198	    return redact_model_preview(text, limit=limit)
   199
   200
   201	# Additive evidence attributes that classify/reply failure plumbing forwards
   202	# across provider boundaries (worker envelope -> runtime error -> provider
   203	# error -> executor failure envelope). The failure envelope's public shape is
   204	# unchanged; these attributes only ride on exceptions in between.
   205	_EVIDENCE_ATTRS = (
   206	    "worker_result",
   207	    "model_attempts",
   208	    "parse_reason",
   209	    "raw_response_preview",
   210	    "finish_reason",
   211	    "completion_tokens",
   212	    "prompt_tokens",
   213	    "total_tokens",
   214	    "model",
   215	    "phase",
   216	    "endpoint",
   217	)
   218
   219
   220	def _audit_with_runtime_attempts(
   221	    audit_metadata: Mapping[str, Any] | None,
   222	    response: Any,
   223	) -> dict[str, Any]:
   224	    """Merge worker-observed canonical attempt evidence into provider audit data."""
   225	    merged = dict(audit_metadata or {})
   226	    if not isinstance(response, Mapping):
   227	        return merged
   228	    attempts = coerce_model_attempts(response.get("model_attempts"))
   229	    if attempts:
   230	        merged["model_attempts"] = [dict(item) for item in attempts]
   231	    usage = response.get("deepseek_usage")
   232	    if isinstance(usage, Mapping):
   233	        merged["deepseek_usage"] = dict(usage)
   234	    return merged
   235
   236
   237	def _forward_evidence_attrs(source: BaseException, target: BaseException) -> None:
   238	    """Copy additive evidence attributes from *source* onto *target*."""
   239	    for name in _EVIDENCE_ATTRS:
   240	        if getattr(target, name, None) is not None:
   241	            continue
   242	        value = getattr(source, name, None)
   243	        if value is None:
   244	            continue
   245	        try:
   246	            setattr(target, name, value)
   247	        except Exception:  # noqa: BLE001 - evidence attachment is best-effort
   248	            pass
   249
   250
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
  1392	    *,
  1393	    attempt_offset: int,
  1394	) -> tuple[dict[str, Any], ...]:
  1395	    if not isinstance(response, Mapping):
  1396	        return ()
  1397	    attempts = list(coerce_model_attempts(response.get("model_attempts")))
  1398	    if not attempts:
  1399	        return ()
  1400	    latest = dict(attempts[-1])
  1401	    latest.update({
  1402	        "outcome": "failure",
  1403	        "failure_type": _batch_failure_type(exc),
  1404	        "raw_response_preview": getattr(exc, "raw_response", None),
  1405	    })
  1406	    attempts[-1] = latest
  1407	    revised_attempts: list[dict[str, Any]] = []
  1408	    for local_index, attempt in enumerate(attempts, start=1):
  1409	        numbered = dict(attempt)
  1410	        numbered["attempt"] = attempt_offset + local_index
  1411	        revised_attempts.append(ModelAttemptEvidence.from_mapping(numbered).to_dict())
  1412	    try:
  1413	        from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
  1414
  1415	        replace_last_model_attempts(revised_attempts)
  1416	    except Exception:  # noqa: BLE001 - evidence capture is additive
  1417	        pass
  1418	    exc.model_attempts = list(revised_attempts)  # type: ignore[attr-defined]
  1419	    return tuple(revised_attempts)
  1420
  1421
  1422	def _typed_empty_attempt(attempts: tuple[dict[str, Any], ...]) -> bool:
  1423	    if not attempts:
  1424	        return False
  1425	    latest = attempts[-1]
  1426	    usage = latest.get("token_usage")
  1427	    return (
  1428	        latest.get("failure_type") == "empty_response"
  1429	        and isinstance(usage, Mapping)
  1430	        and usage.get("completion_tokens") == 0
  1431	    )
  1432
  1433
  1434	def run_agent_turn_batch(
  1435	    task: str,
  1436	    messages: list[dict[str, str]],
  1437	    *,
  1438	    route: str | None = None,
  1439	    model: str | None = None,
  1440	    effort: str | None = None,
  1441	) -> BatchTurnResult:
  1442	    """Run a single batch-REPL turn through the Arnold/Hermes provider.
  1443
  1444	    Sends *messages* (built by :func:`build_batch_messages`) to the model
  1445	    and normalizes the response through :func:`extract_batch_fence` instead
  1446	    of JSON parsing.  Returns a :class:`BatchTurnResult` with the fenced
  1447	    batch code and surrounding prose.
  1448
  1449	    Parameters
  1450	    ----------
  1451	    task:
  1452	        The user's natural-language edit request.
  1453	    messages:
  1454	        Pre-built chat messages from :func:`build_batch_messages`.
  1455	    route:
  1456	        Optional provider route name.  Resolved via :func:`_resolve_agent_route`.
  1457	    model:
  1458	        Optional model identifier.  Falls back to ``VIBECOMFY_AGENT_MODEL``.
  1459	    """
  1460	    route_descriptor = _resolve_agent_route(route)
  1461	    selected_route = route_descriptor.normalized_route
  1462	    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
  1463	    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
  1464	    runtime = _load_arnold_runtime()
  1465	    audit_metadata: dict[str, Any] = {
  1466	        "provider": "arnold",
  1467	        "requested_route": route_descriptor.requested_route,
  1468	        "route_metadata": route_descriptor.to_dict(),
  1469	        "legacy_deepseek_fallback_enabled": False,
  1470	        "credential_presence": _credential_presence(),
  1471	        "response_contract": "batch_repl",
  1472	    }
  1473	    try:
  1474	        attempts = 3
  1475	        retry_count = 0
  1476	        last_exc: MalformedModelJSON | MissingRequiredField | None = None
  1477	        current_messages = messages
  1478	        attempt_log: list[dict[str, Any]] = []
  1479	        for attempt_index in range(attempts):
  1480	            if attempt_index > 0 and last_exc is not None:
  1481	                current_messages = _batch_retry_messages(messages, last_exc)
  1482	            response = _call_batch_runtime(
  1483	                runtime,
  1484	                task=task,
  1485	                messages=current_messages,
  1486	                route=dispatch_route,
  1487	                model=selected_model,
  1488	                effort=effort,
  1489	            )
  1490	            try:
  1491	                result = _normalize_batch_response(
  1492	                    response,
  1493	                    route=dispatch_route,
  1494	                    model=selected_model,
  1495	                    audit_metadata=audit_metadata,
  1496	                )
  1497	            except (MalformedModelJSON, MissingRequiredField) as exc:
  1498	                failed_attempts = _revise_failed_runtime_attempt(
  1499	                    response,
  1500	                    exc,
  1501	                    attempt_offset=len(attempt_log),
  1502	                )
  1503	                attempt_log.extend(failed_attempts)
  1504	                last_exc = exc
  1505	                if attempt_index >= attempts - 1 or not _typed_empty_attempt(failed_attempts):
  1506	                    raise
  1507	                retry_count += 1
  1508	                continue
  1509	            current_attempts = list(
  1510	                coerce_model_attempts((result.audit_metadata or {}).get("model_attempts"))
  1511	            )
  1512	            numbered_current_attempts: list[dict[str, Any]] = []
  1513	            for local_index, current_attempt in enumerate(current_attempts, start=1):
  1514	                numbered = dict(current_attempt)
  1515	                numbered["attempt"] = len(attempt_log) + local_index
  1516	                numbered_current_attempts.append(
  1517	                    ModelAttemptEvidence.from_mapping(numbered).to_dict()
  1518	                )
  1519	            if numbered_current_attempts:
  1520	                try:
  1521	                    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempts
  1522
  1523	                    replace_last_model_attempts(numbered_current_attempts)
  1524	                except Exception:  # noqa: BLE001 - evidence capture is additive
  1525	                    pass
  1526	            if attempt_log or numbered_current_attempts != current_attempts:
  1527	                metadata = dict(result.audit_metadata or {})
  1528	                metadata["model_attempts"] = [*attempt_log, *numbered_current_attempts]
  1529	                result = dataclasses.replace(result, audit_metadata=metadata)
  1530	            if retry_count:
  1531	                metadata = dict(result.audit_metadata or {})
  1532	                metadata["batch_repl_retry"] = {
  1533	                    "count": retry_count,
  1534	                    "reason": str(last_exc) if last_exc is not None else "",
  1535	                    "parse_reason": getattr(last_exc, "parse_reason", None),
  1536	                    "raw_response_preview": getattr(last_exc, "raw_response_preview", None),
  1537	                }
  1538	                result = dataclasses.replace(result, audit_metadata=metadata)
  1539	            return result
  1540	        if last_exc is not None:
  1541	            raise last_exc
  1542	        raise ProviderError("Agent batch_repl provider exited without a response.")
  1543	    except PermissionError as exc:
  1544	        raise AuthError(str(exc)) from exc
  1545	    except TimeoutError:
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

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/runner.py | sed -n '120,290p'; rg -n -i \"empty response|empty_response|no content|completion_tokens|response wording|in .*message|message.*empty|error.*empty\" tests/live_agentic_harness/runner.py vibecomfy/comfy_nodes/agent/runtime.py vibecomfy/comfy_nodes/agent/provider.py vibecomfy/executor/agent_backend.py vibecomfy/executor/core.py | head -n 240" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
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
   259	def _classify_retryable_infra_summary(summary: dict[str, Any]) -> dict[str, Any]:
   260	    failure_class = _provider_infra_failure_class(summary)
   261	    if failure_class is not None and summary.get("guard", {}).get("live_agentic_success") is not True:
   262	        _mark_summary_as_infra(summary, failure_class)
   263	    return summary
   264
   265
   266	def _is_retryable_infra_summary(summary: dict[str, Any]) -> bool:
   267	    _classify_retryable_infra_summary(summary)
   268	    return (
   269	        summary.get("failure_class") == "infra_empty_response"
   270	        and summary.get("retryable_infra") is True
   271	        and _summary_completion_tokens(summary) == 0
   272	    )
   273
   274
   275	def _build_run_summary(
   276	    tag: str,
   277	    summaries: list[dict[str, Any]],
   278	    *,
   279	    total_scenarios: int,
   280	    complete: bool,
   281	) -> dict[str, Any]:
   282	    passed = sum(1 for summary in summaries if summary["guard"].get("live_agentic_success") is True)
   283	    failed = len(summaries) - passed
   284	    raw_first_attempt_passed = sum(
   285	        1
   286	        for summary in summaries
   287	        if summary.get("raw_first_attempt_success", summary["guard"].get("live_agentic_success")) is True
   288	    )
   289	    infra_failures = sum(
   290	        1
vibecomfy/executor/core.py:313:    raise ValueError("Route behaviors must cover every non-empty allowed route exactly once.")
vibecomfy/executor/core.py:566:                for msg in raw_messages:
vibecomfy/executor/core.py:606:                    msg for msg in reversed(raw_messages if isinstance(raw_messages, list) else [])
vibecomfy/executor/core.py:1447:                    if key not in {"message", "stage", "failure_kind"}
vibecomfy/executor/core.py:1687:                        if key in reply_kwargs and key in message
vibecomfy/executor/core.py:1697:            for key in ("reply", "message", "text"):
vibecomfy/executor/agent_backend.py:91:        return "empty_response"
tests/live_agentic_harness/runner.py:140:        "retryable_infra": failure_class == "infra_empty_response",
tests/live_agentic_harness/runner.py:203:def _summary_completion_tokens(summary: dict[str, Any]) -> int | None:
tests/live_agentic_harness/runner.py:207:    level — the executor result's usage dict.  ``completion_tokens == 0`` is the
tests/live_agentic_harness/runner.py:215:    value = usage.get("completion_tokens")
tests/live_agentic_harness/runner.py:227:    if failure_type == "empty_response" and _summary_completion_tokens(summary) == 0:
tests/live_agentic_harness/runner.py:228:        return "infra_empty_response"
tests/live_agentic_harness/runner.py:239:    summary["retryable_infra"] = failure_class == "infra_empty_response"
tests/live_agentic_harness/runner.py:269:        summary.get("failure_class") == "infra_empty_response"
tests/live_agentic_harness/runner.py:271:        and _summary_completion_tokens(summary) == 0
vibecomfy/comfy_nodes/agent/runtime.py:457:    for entry in messages or []:
vibecomfy/comfy_nodes/agent/runtime.py:508:    """True only for typed empty responses with observed zero completion tokens."""
vibecomfy/comfy_nodes/agent/runtime.py:516:        and latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/runtime.py:518:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/runtime.py:578:    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
vibecomfy/comfy_nodes/agent/runtime.py:579:    provider/capacity errors, and malformed non-empty content surface immediately.
vibecomfy/comfy_nodes/agent/runtime.py:625:                "agent worker returned typed empty response (attempt %d/%d); retrying",
vibecomfy/comfy_nodes/agent/provider.py:69:    messages = [msg for msg in conversation_messages if isinstance(msg, dict)]
vibecomfy/comfy_nodes/agent/provider.py:81:            for msg in reversed(messages[:-1])
vibecomfy/comfy_nodes/agent/provider.py:211:    "completion_tokens",
vibecomfy/comfy_nodes/agent/provider.py:511:            for msg in conversation_messages:
vibecomfy/comfy_nodes/agent/provider.py:799:        "\"value\": \"a serene mountain lake\"}], \"message\": \"Set the prompt text.\"}\n"
vibecomfy/comfy_nodes/agent/provider.py:803:        "`delta` and explain the limitation in `message`. The `message` may use "
vibecomfy/comfy_nodes/agent/provider.py:981:        for fallback_key in ("detail", "error", "message"):
vibecomfy/comfy_nodes/agent/provider.py:1382:        return "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1428:        latest.get("failure_type") == "empty_response"
vibecomfy/comfy_nodes/agent/provider.py:1430:        and usage.get("completion_tokens") == 0
vibecomfy/comfy_nodes/agent/provider.py:1715:        raise ValueError("DeepSeek API key must be a non-empty string.")
vibecomfy/comfy_nodes/agent/provider.py:1751:        raise ValueError("OpenRouter API key must be a non-empty string.")

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/runtime.py | sed -n '470,525p'; nl -ba vibecomfy/executor/agent_backend.py | sed -n '85,260p'; nl -ba vibecomfy/executor/core.py | sed -n '90,155p'; nl -ba vibecomfy/executor/core.py | sed -n '1840,1920p'; nl -ba vibecomfy/executor/contracts.py | sed -n '780,900p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 2ms:
   780	            result["source_preferences"] = list(self.source_preferences)
   781	        if self.avoid:
   782	            result["avoid"] = list(self.avoid)
   783	        if self.known_graph_context:
   784	            result["known_graph_context"] = self.known_graph_context
   785	        if self.model_families:
   786	            result["model_families"] = list(self.model_families)
   787	        if self.pattern_category:
   788	            result["pattern_category"] = self.pattern_category
   789	        if self.change_goal:
   790	            result["change_goal"] = self.change_goal
   791	        if self.target_node_type:
   792	            result["target_node_type"] = self.target_node_type
   793	        if self.clarification_question:
   794	            result["clarification_question"] = self.clarification_question
   795	        if self.clarification_options:
   796	            result["clarification_options"] = list(self.clarification_options)
   797	        return result
   798
   799	    # ── convenience constructors ─────────────────────────────────────────
   800
   801	    @classmethod
   802	    def respond_only(
   803	        cls,
   804	        *,
   805	        effort: str = "low",
   806	        plan_summary: str = "",
   807	        route: str = "",
   808	        task: str = "",
   809	    ) -> "ClassifyDecision":
   810	        """Convenience: classify as a respond-only turn (no research, no edit)."""
   811	        return cls(
   812	            research=False,
   813	            implement=False,
   814	            reply=True,
   815	            effort=effort,
   816	            plan_summary=plan_summary,
   817	            intent="respond",
   818	            route=route,
   819	            task=task,
   820	        )
   821
   822	    @classmethod
   823	    def edit(
   824	        cls,
   825	        *,
   826	        research: bool = True,
   827	        effort: str = "medium",
   828	        plan_summary: str = "",
   829	        route: str = "",
   830	        task: str = "",
   831	    ) -> "ClassifyDecision":
   832	        """Convenience: classify as an edit turn (with research by default)."""
   833	        return cls(
   834	            research=research,
   835	            implement=True,
   836	            reply=True,
   837	            effort=effort,
   838	            plan_summary=plan_summary,
   839	            intent="edit",
   840	            route=route,
   841	            task=task,
   842	        )
   843
   844
   845	# ── route / task derivation (legacy compatibility) ───────────────────────────
   846
   847
   848	def _derive_route(*, research: bool, implement: bool, intent: str) -> str:
   849	    """Derive a normalized route from legacy boolean + intent fields.
   850
   851	    This follows the locked route vocabulary for the no-edit contract repair:
   852	    * revise → implement without research
   853	    * adapt → research + implement (legacy booleans are unambiguous here)
   854	    * research → research without implementation and research intent
   855	    * inspect → explain_graph intent without implementation
   856	    * respond → respond intent without research or implementation
   857	    * clarify → neither research nor implementation when intent is ambiguous
   858	    """
   859	    if implement and research:
   860	        return "adapt"
   861	    if implement and not research:
   862	        return "revise"
   863	    if research and not implement:
   864	        return "research"
   865	    if not research and not implement:
   866	        if intent == "explain_graph":
   867	            return "inspect"
   868	        if intent == "respond":
   869	            return "respond"
   870	        return "clarify"
   871	    return ""
   872
   873
   874	def _derive_task(*, research: bool, implement: bool, intent: str) -> str:
   875	    """Derive a normalized task label from legacy fields.
   876
   877	    Returns ``""`` when the mapping is ambiguous.
   878	    """
   879	    if implement and research:
   880	        return "research_precedent"
   881	    if implement and not research:
   882	        return "edit_graph"
   883	    if research and not implement:
   884	        return "research_nodes"
   885	    if not research and not implement:
   886	        if intent == "explain_graph":
   887	            return "inspect_graph"
   888	        if intent == "respond":
   889	            return "respond"
   890	        return "respond"
   891	    return ""
   892
   893
   894	# ── request ──────────────────────────────────────────────────────────────────
   895
   896
   897	@dataclass(frozen=True)
   898	class ExecutorRequest:
   899	    """Public input shape for ``POST /vibecomfy/agent-executor``.
   900

exec
/bin/zsh -lc "git log --oneline --decorate -5; git show --stat --oneline --summary a8d4974a; git diff --unified=40 45415680..a8d4974a -- vibecomfy/executor/contracts.py vibecomfy/comfy_nodes/agent/runtime.py vibecomfy/comfy_nodes/agent/provider.py vibecomfy/executor/agent_backend.py vibecomfy/executor/core.py vibecomfy/agent/artifacts.py tests/live_agentic_harness/adapter.py tests/live_agentic_harness/runner.py > /tmp/b01-core.diff; wc -l /tmp/b01-core.diff; sed -n '1,240p' /tmp/b01-core.diff" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 41ms:
a8d4974a megado B01 rework: oracle issues 1-6 — single canonical attempt evidence (legacy model_response removed), monotonic batch retry attempts, observed-vs-unavailable zero tokens, full Authorization redaction, no raw-copy of malformed artifacts, unsupported-route=unknown — 568 focused tests green
 .oracle/briefs/batch-B01-rework.md            |    38 +
 .oracle/checkins/batch-B01.md                 | 10215 ++++++++++++++++++++++++
 tests/live_agentic_harness/runner.py          |     2 +-
 tests/test_agent_runtime_adapter.py           |   113 +
 tests/test_executor_contracts.py              |    25 +
 tests/test_executor_flows.py                  |    40 +
 tests/test_headless_agent_artifacts.py        |    57 +
 tests/test_live_agentic_runner_persistence.py |     1 +
 tests/test_runtime_worker_retry.py            |    16 +
 vibecomfy/agent/artifacts.py                  |    10 +-
 vibecomfy/comfy_nodes/agent/provider.py       |    44 +-
 vibecomfy/comfy_nodes/agent/runtime.py        |    42 +-
 vibecomfy/comfy_nodes/agent/worker.py         |     7 +-
 vibecomfy/executor/agent_backend.py           |    16 +-
 vibecomfy/executor/contracts.py               |    30 +-
 vibecomfy/executor/core.py                    |   177 +-
 16 files changed, 10633 insertions(+), 200 deletions(-)
 create mode 100644 .oracle/briefs/batch-B01-rework.md
 create mode 100644 .oracle/checkins/batch-B01.md
zsh:1: operation not permitted: /tmp/b01-core.diff
wc: /tmp/b01-core.diff: open: No such file or directory
sed: /tmp/b01-core.diff: No such file or directory

exec
/bin/zsh -lc "sed -n '1,240p' .oracle/briefs/batch-B01.md; sed -n '1,240p' .oracle/briefs/batch-B01-rework.md; rg -n \"pytest|556|568|rerunfailures\" .oracle/checkins/batch-B01.md | tail -n 60" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
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
23:**B01 [HARD] — Typed failures and unified attempt provenance.** Tasks + acceptance from `.oracle/tasklist.md` (B01 section). The diff to review: `git diff 45415680..a8d4974a` (G0R PASS SHA → B01 commit). The executor was GPT-5.6 Sol (workspace-write, 30-min clamp hit mid-verification; the orchestrator ran the focused suite to completion).
30:- Orchestrator verification: **556 passed** (`-p no:rerunfailures`; the socket-binding rerunfailures plugin cannot run in this environment) across classify_only, contracts, flows, runtime_adapter, headless_agent_artifacts, runner_persistence, runtime_worker_retry.
40:7. Scope: diff contains only B01-scope files; `git diff --check 45415680..a8d4974a` clean.
41:8. Run the focused suite yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks); live runs skipped (orchestrator-phase).
233:/bin/zsh -lc "git status --short --branch && git diff --stat 45415680..a8d4974a && git diff --name-status 45415680..a8d4974a && git diff --check 45415680..a8d4974a && sed -n '/"'^## B01/,/''^## B02/p'"' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
788:tests/test_agent_runtime_adapter.py:556:    assert result.audit_metadata["model_attempts"] == [attempt]
1601:vibecomfy/executor/research.py:5565:                        reason="candidate graph construction returned a malformed graph",
1602:vibecomfy/executor/research.py:5566:                        detail={"reason_code": "candidate_graph_malformed"},
2361:vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js:3556:function _handleRebaselineFailure(panel, payload) {
3957:   556	        adapter=agent_id,
3969:   568	    response_contract: str = "python",
4798:   556	                message = payload.get("message")
4810:   568	                    out = {"python": python, "message": message}
5676:/bin/zsh -lc "git log --oneline --decorate -5; git show --stat --oneline --summary a8d4974a; git diff --unified=40 45415680..a8d4974a -- vibecomfy/executor/contracts.py vibecomfy/comfy_nodes/agent/runtime.py vibecomfy/comfy_nodes/agent/provider.py vibecomfy/executor/agent_backend.py vibecomfy/executor/core.py vibecomfy/agent/artifacts.py tests/live_agentic_harness/adapter.py tests/live_agentic_harness/runner.py > /tmp/b01-core.diff; wc -l /tmp/b01-core.diff; sed -n '1,240p' /tmp/b01-core.diff" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
5678:a8d4974a megado B01 rework: oracle issues 1-6 — single canonical attempt evidence (legacy model_response removed), monotonic batch retry attempts, observed-vs-unavailable zero tokens, full Authorization redaction, no raw-copy of malformed artifacts, unsupported-route=unknown — 568 focused tests green

codex
The post-rework code now has the intended single canonical `ModelAttemptEvidence` shape and the narrow retry predicate (`failure_type == empty_response` plus observed `completion_tokens == 0`). I’m running the seven-file focused suite with both rerun and pytest cache plugins disabled so verification remains compatible with the read-only sandbox.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:rerunfailures -p no:cacheprovider -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 958ms:
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

codex
The focused suite cannot start in this sandbox: pytest fails before collection because no writable temporary directory exists (`FileNotFoundError: No usable temporary directory`). This is a sandbox limitation, not a test failure. I’ll complete the gate from static trace evidence plus the orchestrator’s completed run; live/model calls remain skipped as required.
exec
/bin/zsh -lc "rg -n \"class Report|model_response|model_attempts|def to_dict\" vibecomfy/executor/contracts.py | tail -n 80; nl -ba vibecomfy/executor/contracts.py | sed -n '2250,2390p'; nl -ba vibecomfy/agent/artifacts.py | sed -n '1,145p'; nl -ba vibecomfy/agent/artifacts.py | sed -n '300,355p'; nl -ba tests/test_headless_agent_artifacts.py | sed -n '240,390p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
198:    def to_dict(self) -> dict[str, Any]:
218:def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
759:    def to_dict(self) -> dict[str, Any]:
929:    def to_dict(self) -> dict[str, Any]:
1068:    def to_dict(self) -> dict[str, Any]:
1133:    def to_dict(self) -> dict[str, Any]:
1234:    def to_dict(self) -> dict[str, Any]:
1371:    def to_dict(self) -> dict[str, Any]:
1530:    def to_dict(self) -> dict[str, Any]:
1573:    def to_dict(self) -> dict[str, Any]:
1709:    def to_dict(self) -> dict[str, Any]:
1804:    def to_dict(self) -> dict[str, Any]:
1864:    def to_dict(self) -> dict[str, Any]:
1938:    def to_dict(self) -> dict[str, Any]:
2004:    def to_dict(self) -> dict[str, Any]:
2111:    def to_dict(self) -> dict[str, Any]:
2174:    def to_dict(self) -> dict[str, Any]:
2268:    def to_dict(self) -> dict[str, Any]:
2290:class Report:
2310:    model_attempts: tuple[dict[str, Any], ...] = ()
2323:            "model_attempts",
2324:            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
2328:    def model_response(self) -> dict[str, Any] | None:
2329:        """Compatibility view derived solely from canonical ``model_attempts``."""
2330:        if not self.model_attempts:
2333:            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
2336:    def to_dict(self) -> dict[str, Any]:
2358:        inner["model_attempts"] = [
2359:            _thaw_jsonish(item) for item in self.model_attempts
2405:    def to_dict(self) -> dict[str, Any]:
2457:    def to_dict(self) -> dict[str, Any]:
2613:    def to_dict(self) -> dict[str, Any]:
2620:        payload["model_attempts"] = [
2621:            _thaw_jsonish(item) for item in self.report.model_attempts
2710:    "coerce_model_attempts",
  2250	    @property
  2251	    def durable_session_id(self) -> str | None:
  2252	        """Return the session_id from the durable response, if present."""
  2253	        dr = self.durable_response
  2254	        if dr is None:
  2255	            return None
  2256	        sid = dr.get("session_id")
  2257	        return sid if isinstance(sid, str) and sid.strip() else None
  2258
  2259	    @property
  2260	    def durable_turn_id(self) -> str | None:
  2261	        """Return the turn_id from the durable response, if present."""
  2262	        dr = self.durable_response
  2263	        if dr is None:
  2264	            return None
  2265	        tid = dr.get("turn_id")
  2266	        return tid if isinstance(tid, str) and tid.strip() else None
  2267
  2268	    def to_dict(self) -> dict[str, Any]:
  2269	        payload: dict[str, Any] = {"message": self.message}
  2270	        if self.graph is not None:
  2271	            payload["graph"] = self.graph
  2272	        if self.delta:
  2273	            payload["delta"] = _thaw_jsonish(self.delta)
  2274	        if self.diagnostics is not None:
  2275	            payload["diagnostics"] = _thaw_jsonish(self.diagnostics)
  2276	        if self.failure is not None:
  2277	            payload["failure"] = _thaw_jsonish(self.failure)
  2278	            diagnostics = self.failure.get("diagnostics")
  2279	            if diagnostics is not None:
  2280	                payload["diagnostics"] = _thaw_jsonish(diagnostics)
  2281	        # Durable metadata is internal; only exposed through the
  2282	        # candidate payload in AgentTurnResult, not here.
  2283	        return payload
  2284
  2285
  2286	# ── report (nested executor metadata) ────────────────────────────────────────
  2287
  2288
  2289	@dataclass(frozen=True)
  2290	class Report:
  2291	    """Executor metadata nested under ``report`` in the final envelope.
  2292
  2293	    Every phase's output is captured here so the envelope stays a stable
  2294	    ``{message, outcome, candidate, eligibility, report}`` shape without
  2295	    new top-level fields.
  2296	    """
  2297
  2298	    plan: ClassifyDecision | None = None
  2299	    research: ResearchResult | None = None
  2300	    implementation: ImplementationResult | None = None
  2301	    deepseek_usage: dict[str, Any] = field(default_factory=dict)
  2302	    deepseek_est_cost_usd: float | None = None
  2303	    deepseek_cost_basis: str | None = None
  2304	    # Truthful classification lifecycle signal: "failed" means classify raised
  2305	    # (the plan is then None — no invented respond_only placeholder). Empty
  2306	    # string means the signal was not recorded (legacy paths).
  2307	    classification_status: str = ""
  2308	    # Canonical per-call evidence for every successful and failed model attempt
  2309	    # observed across classify, implement/batch, and reply.
  2310	    model_attempts: tuple[dict[str, Any], ...] = ()
  2311
  2312	    def __post_init__(self) -> None:
  2313	        object.__setattr__(
  2314	            self,
  2315	            "deepseek_usage",
  2316	            MappingProxyType({
  2317	                str(k): _freeze_jsonish(v)
  2318	                for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
  2319	            }),
  2320	        )
  2321	        object.__setattr__(
  2322	            self,
  2323	            "model_attempts",
  2324	            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
  2325	        )
  2326
  2327	    @property
  2328	    def model_response(self) -> dict[str, Any] | None:
  2329	        """Compatibility view derived solely from canonical ``model_attempts``."""
  2330	        if not self.model_attempts:
  2331	            return None
  2332	        return {
  2333	            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
  2334	        }
  2335
  2336	    def to_dict(self) -> dict[str, Any]:
  2337	        inner: dict[str, Any] = {}
  2338	        if self.plan is not None:
  2339	            plan_payload = self.plan.to_dict()
  2340	            route = _public_route_for_plan(self.plan)
  2341	            plan_payload["route"] = route
  2342	            task = self.plan.effective_task
  2343	            if task:
  2344	                plan_payload["task"] = task
  2345	            inner["plan"] = plan_payload
  2346	        if self.research is not None:
  2347	            inner["research"] = self.research.to_dict()
  2348	        if self.implementation is not None:
  2349	            inner["implementation"] = self.implementation.to_dict()
  2350	        usage_payload = coerce_deepseek_usage(self.deepseek_usage)
  2351	        inner["deepseek_usage"] = usage_payload
  2352	        if self.deepseek_est_cost_usd is not None:
  2353	            inner["deepseek_est_cost_usd"] = float(self.deepseek_est_cost_usd)
  2354	        if isinstance(self.deepseek_cost_basis, str) and self.deepseek_cost_basis:
  2355	            inner["deepseek_cost_basis"] = self.deepseek_cost_basis
  2356	        if self.classification_status:
  2357	            inner["classification_status"] = self.classification_status
  2358	        inner["model_attempts"] = [
  2359	            _thaw_jsonish(item) for item in self.model_attempts
  2360	        ]
  2361	        return {"executor": inner}
  2362
  2363
  2364	# ── canonical turn envelope ──────────────────────────────────────────────────
  2365
  2366
  2367	def _public_route_for_plan(plan: ClassifyDecision) -> str:
  2368	    route = plan.effective_route
  2369	    if route in _PUBLIC_ROUTES:
  2370	        return route
  2371	    if plan.implement and plan.research:
  2372	        return "adapt"
  2373	    if plan.implement:
  2374	        return "revise"
  2375	    if plan.research:
  2376	        return "research"
  2377	    return "respond"
  2378
  2379
  2380	@dataclass(frozen=True)
  2381	class AgentEvidence:
  2382	    """Bounded evidence object for public executor turn responses."""
  2383
  2384	    classification: dict[str, Any] = field(default_factory=dict)
  2385	    graph_inspection: dict[str, Any] = field(default_factory=dict)
  2386	    research: dict[str, Any] = field(default_factory=dict)
  2387	    implementation: dict[str, Any] = field(default_factory=dict)
  2388	    warnings: tuple[str, ...] = ()
  2389
  2390	    def __post_init__(self) -> None:
     1	"""Artifact synthesis for the headless VibeComfy agent surface.
     2
     3	Writes a stable, redacted artifact directory that harnesses and external
     4	consumers (e.g. Astrid) can grade without parsing narrative output.
     5	"""
     6
     7	from __future__ import annotations
     8
     9	import json
    10	import logging
    11	from pathlib import Path
    12	from typing import Any, Mapping
    13
    14	from vibecomfy.executor.contracts import normalize_model_endpoint, redact_model_preview
    15
    16	LOGGER = logging.getLogger(__name__)
    17
    18
    19	_FLOW_KIND = "live_agentic_headless"
    20	_SENSITIVE_KEY_PARTS = frozenset({
    21	    "api_key",
    22	    "apikey",
    23	    "authorization",
    24	    "bearer",
    25	    "password",
    26	    "secret",
    27	    "token",
    28	})
    29	_MODEL_ARTIFACT_NAMES = frozenset({
    30	    "messages.jsonl",
    31	    "model_attempts.json",
    32	    "model_request.json",
    33	    "model_response.json",
    34	})
    35
    36
    37	def _safe_write(path: Path, data: Any) -> None:
    38	    path.parent.mkdir(parents=True, exist_ok=True)
    39	    path.write_text(
    40	        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
    41	        encoding="utf-8",
    42	    )
    43
    44
    45	def _json_safe(value: Any) -> Any:
    46	    if value is None or isinstance(value, (str, int, float, bool)):
    47	        return value
    48	    if hasattr(value, "to_dict") and callable(value.to_dict):
    49	        return _json_safe(value.to_dict())
    50	    if isinstance(value, Mapping):
    51	        return {str(key): _json_safe(item) for key, item in value.items()}
    52	    if isinstance(value, (list, tuple, set)):
    53	        return [_json_safe(item) for item in value]
    54	    return str(value)
    55
    56
    57	def _is_sensitive_key(key: str) -> bool:
    58	    lower = key.lower()
    59	    return any(part in lower for part in _SENSITIVE_KEY_PARTS)
    60
    61
    62	def _redact(value: Any, *, parent_key: str = "") -> Any:
    63	    """Return a JSON-safe copy with credential-like values redacted."""
    64	    if _is_sensitive_key(parent_key) and isinstance(value, str):
    65	        return "<redacted>"
    66	    if parent_key.lower() == "endpoint" and isinstance(value, str):
    67	        return normalize_model_endpoint(value)
    68	    if parent_key.lower() == "raw_response_preview" and isinstance(value, str):
    69	        return redact_model_preview(value)
    70	    if isinstance(value, Mapping):
    71	        redacted: dict[str, Any] = {}
    72	        for key, item in value.items():
    73	            key_text = str(key)
    74	            redacted[key_text] = _redact(item, parent_key=key_text)
    75	        return redacted
    76	    if isinstance(value, (list, tuple, set)):
    77	        return [_redact(item, parent_key=parent_key) for item in value]
    78	    return _json_safe(value)
    79
    80
    81	def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
    82	    detail = response.get("detail_json_path") or response.get("detail_json_path_resolved")
    83	    if isinstance(detail, str) and detail:
    84	        return Path(detail).parent
    85	    session_path = response.get("session_path") or response.get("session_path_resolved")
    86	    turn_id = response.get("turn_id")
    87	    if isinstance(session_path, str) and session_path and isinstance(turn_id, str) and turn_id:
    88	        candidate = Path(session_path) / "turns" / turn_id
    89	        if candidate.is_dir():
    90	            return candidate
    91	    return None
    92
    93
    94	def _copy_turn_artifacts(turn_dir: Path, output_dir: Path) -> list[str]:
    95	    copied: list[str] = []
    96	    if not turn_dir.is_dir():
    97	        return copied
    98	    for source in sorted(turn_dir.iterdir()):
    99	        if source.is_file() and source.suffix in {".json", ".jsonl"}:
   100	            dest = output_dir / source.name
   101	            try:
   102	                if source.suffix == ".json":
   103	                    parsed = json.loads(source.read_text(encoding="utf-8"))
   104	                    _safe_write(dest, _redact(parsed))
   105	                else:
   106	                    rendered: list[str] = []
   107	                    for line in source.read_text(encoding="utf-8").splitlines():
   108	                        if not line.strip():
   109	                            continue
   110	                        rendered.append(json.dumps(_redact(json.loads(line)), sort_keys=True))
   111	                    dest.write_text("\n".join(rendered) + ("\n" if rendered else ""), encoding="utf-8")
   112	            except (OSError, json.JSONDecodeError):
   113	                # Never raw-copy an unparseable model artifact: it may contain a
   114	                # credential in malformed structured text that free-text
   115	                # redaction cannot classify safely. Persist no source body.
   116	                _safe_write(dest, {"redacted_unparseable_artifact": True})
   117	            copied.append(str(dest.relative_to(output_dir)))
   118	    return copied
   119
   120
   121	def _executor_report(result: Any) -> dict[str, Any]:
   122	    result_payload = _json_safe(result)
   123	    if isinstance(result_payload, Mapping):
   124	        report = result_payload.get("report")
   125	        if isinstance(report, Mapping):
   126	            executor = report.get("executor")
   127	            if isinstance(executor, Mapping):
   128	                return dict(executor)
   129
   130	    report_obj = getattr(result, "report", None)
   131	    report_payload = _json_safe(report_obj)
   132	    if isinstance(report_payload, Mapping):
   133	        executor = report_payload.get("executor")
   134	        if isinstance(executor, Mapping):
   135	            return dict(executor)
   136	    return {}
   137
   138
   139	def _implementation_payload_from_report(
   140	    *,
   141	    request: Mapping[str, Any],
   142	    classification: Mapping[str, Any],
   143	    research: Mapping[str, Any] | None,
   144	) -> dict[str, Any]:
   145	    route = classification.get("route")
   300	    entrypoint: str = "headless_cli",
   301	) -> dict[str, Any]:
   302	    """Write the standard headless artifact directory and return a manifest.
   303
   304	    The manifest lists every file written relative to *output_dir*.  Real durable
   305	    turn artifacts are copied from the underlying agent-edit turn when they exist;
   306	    synthetic summaries are always written so callers have a stable contract.
   307	    """
   308	    output_dir.mkdir(parents=True, exist_ok=True)
   309	    manifest: list[str] = []
   310
   311	    request_path = output_dir / "request.json"
   312	    _safe_write(request_path, _redact(request))
   313	    _append_manifest(manifest, "request.json")
   314
   315	    response_path = output_dir / "response.json"
   316	    _safe_write(response_path, _redact(response))
   317	    _append_manifest(manifest, "response.json")
   318
   319	    flow_metadata = {
   320	        "flow_kind": _FLOW_KIND,
   321	        "dispatcher": "real",
   322	        "model_behavior": "agentic",
   323	        "frontend": "not_used",
   324	        "entrypoint": entrypoint,
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
   351	        if isinstance(research, Mapping):
   352	            research_payload = _redact(research)
   353	            _safe_write(output_dir / "research.json", research_payload)
   354	            _append_manifest(manifest, "research.json")
   355
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

exec
/bin/zsh -lc "nl -ba tests/test_executor_contracts.py | sed -n '630,740p'; rg -n \"Authorization|api_key|apikey|secret URL|url-secret|redact_model_preview|raw_response_preview\" tests/test_executor_contracts.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_executor_flows.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 44ms:
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
   736	        )
   737
   738	        payload = result.to_dict()
   739	        assert set(payload) == {
   740	            "route",
tests/test_executor_contracts.py:46:    redact_model_preview,
tests/test_executor_contracts.py:652:            raw_response_preview="success content must be dropped",
tests/test_executor_contracts.py:666:        assert "raw_response_preview" not in payload
tests/test_executor_contracts.py:671:        preview = redact_model_preview(
tests/test_executor_contracts.py:672:            f"request failed\nAuthorization: {scheme} {credential}\nresponse invalid"
tests/test_executor_contracts.py:675:        assert preview == "request failed Authorization: <redacted> response invalid"
tests/test_headless_agent_artifacts.py:27:            "api_key": "sk-secret",
tests/test_headless_agent_artifacts.py:43:                    {"class_type": "wrong_ltx", "api_key": "source-secret"},
tests/test_headless_agent_artifacts.py:70:        readiness={"ready": True, "api_key": "readiness-secret"},
tests/test_headless_agent_artifacts.py:83:    assert _read_json(output_dir / "request.json")["extra"]["api_key"] == "<redacted>"
tests/test_headless_agent_artifacts.py:88:    assert _read_json(output_dir / "flow_metadata.json")["readiness"]["api_key"] == "<redacted>"
tests/test_headless_agent_artifacts.py:91:    assert research_json["sources"][0]["api_key"] == "<redacted>"
tests/test_headless_agent_artifacts.py:256:        '{"api_key":"' + secret + '"', encoding="utf-8"
tests/test_headless_agent_artifacts.py:322:                        "https://user:password@OpenRouter.ai/api/v1/?api_key=sk-secret"
tests/test_headless_agent_artifacts.py:331:                    "raw_response_preview": (
tests/test_headless_agent_artifacts.py:332:                        "Authorization: Bearer top-secret "
tests/test_headless_agent_artifacts.py:333:                        "https://example.test/v1?token=url-secret"
tests/test_headless_agent_artifacts.py:348:                    "raw_response_preview": "must never persist on success",
tests/test_headless_agent_artifacts.py:367:    assert "top-secret" not in attempts[0]["raw_response_preview"]
tests/test_headless_agent_artifacts.py:368:    assert "url-secret" not in attempts[0]["raw_response_preview"]
tests/test_headless_agent_artifacts.py:369:    assert "raw_response_preview" not in attempts[1]
tests/test_headless_agent_artifacts.py:379:    assert "url-secret" not in persisted
tests/test_agent_runtime_adapter.py:47:    assert kwargs["api_key"] == "sk-or-v1-openrouter-key"
tests/test_agent_runtime_adapter.py:188:        {"api_key": "sk-or-v1-test-key"},
tests/test_agent_runtime_adapter.py:217:            "api_key": "sk-native-deepseek-key",
tests/test_agent_runtime_adapter.py:360:        {"api_key": "sk-or-v1-test-key"},
tests/test_executor_flows.py:1739:            "raw_response_preview": "{broken",

codex
An adversarial counterexample has surfaced: the harness retry decision can still trust preexisting `failure_class`/`retryable_infra` flags after typed classification returns no match. I’m reproducing that exact pure-function case and checking whether artifact redaction also leaves secrets embedded in ordinary string-valued fields, outside the canonical preview/endpoint keys.
exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/runner.py | sed -n '600,760p'; nl -ba tests/live_agentic_harness/runner.py | sed -n '760,940p'; nl -ba tests/test_live_agentic_runner_persistence.py | sed -n '130,310p'; git diff --unified=12 45415680..a8d4974a -- tests/live_agentic_harness/runner.py vibecomfy/agent/artifacts.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 47ms:
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index bbd41e73..c86fcd92 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -1,25 +1,24 @@
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
@@ -32,44 +31,24 @@ from .failure_analysis import (
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
@@ -149,25 +128,25 @@ def _failure_summary(
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
@@ -198,116 +177,108 @@ def _attempt_record(summary: dict[str, Any], *, attempt: int) -> dict[str, Any]:
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
diff --git a/vibecomfy/agent/artifacts.py b/vibecomfy/agent/artifacts.py
index 753c1257..95e0b635 100644
--- a/vibecomfy/agent/artifacts.py
+++ b/vibecomfy/agent/artifacts.py
@@ -1,41 +1,43 @@
 """Artifact synthesis for the headless VibeComfy agent surface.

 Writes a stable, redacted artifact directory that harnesses and external
 consumers (e.g. Astrid) can grade without parsing narrative output.
 """

 from __future__ import annotations

 import json
 import logging
-import shutil
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

@@ -52,24 +54,28 @@ def _json_safe(value: Any) -> Any:
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
@@ -83,25 +89,40 @@ def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
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
+                # Never raw-copy an unparseable model artifact: it may contain a
+                # credential in malformed structured text that free-text
+                # redaction cannot classify safely. Persist no source body.
+                _safe_write(dest, {"redacted_unparseable_artifact": True})
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
@@ -303,24 +324,31 @@ def synthesize_headless_artifacts(
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
@@ -343,25 +371,25 @@ def synthesize_headless_artifacts(
             )
             _append_manifest(manifest, "implementation_result.json")

     turn_dir = _turn_dir_from_response(response)
     copied: list[str] = []
     if turn_dir is not None and turn_dir.is_dir():
         copied = _copy_turn_artifacts(turn_dir, output_dir)
         for copied_name in copied:
             _append_manifest(manifest, copied_name)

     copied_set = set(copied)
     optional_model_artifacts = {
-        name: name in copied_set
+        name: name in copied_set or name in manifest
         for name in sorted(_MODEL_ARTIFACT_NAMES)
     }

     LOGGER.info(
         "headless artifacts synthesized",
         extra={"output_dir": str(output_dir), "artifact_count": len(manifest)},
     )
     return {
         "output_dir": str(output_dir),
         "manifest": manifest,
         "copied_turn_artifacts": copied,
         "optional_model_artifacts": optional_model_artifacts,

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'from tests.live_agentic_harness.runner import _provider_infra_failure_class, _is_retryable_infra_summary; s={\"failure_class\":\"infra_empty_response\",\"retryable_infra\":True,\"guard\":{\"live_agentic_success\":False},\"model_attempts\":[{\"outcome\":\"failure\",\"failure_type\":\"malformed_json\",\"token_usage\":{\"completion_tokens\":0}}]}; print(_provider_infra_failure_class(s)); print(_is_retryable_infra_summary(s))' && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c 'from vibecomfy.agent.artifacts import _redact; print(_redact({\"content\":\"Authorization: Basic dXNlcjpwYXNz\", \"url\":\"https://example.test/v1?token=[REDACTED_SECRET]"}))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 241ms:
None
True
{'content': 'Authorization: Basic dXNlcjpwYXNz', 'url': 'https://example.test/v1?token=url-secret'}

codex
B01 CHECKPOINT VERDICT: FAIL — canonical provenance is sound, but harness retry and artifact redaction each retain an acceptance-level bypass.

1. **Unified evidence contract — PASS.** `ModelAttemptEvidence` is defined once in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/executor/contracts.py:128), with `coerce_model_attempts` as the shared normalizer at line 218. Worker, runtime, provider/backend, executor, artifacts, and harness all consume `model_attempts`. The legacy `model_response` property is derived only and is not serialized.

2. **Failure taxonomy — PASS.** The closed set at [contracts.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/executor/contracts.py:36) distinctly represents `empty_response`, `malformed_json`, `non_json_content`, `missing_required_fields`, `timeout`, and `provider_failure`. Serialization preserves each value. Structural classification and fixtures cover all six.

3. **Success-path provenance — PASS.** Worker success evidence includes requested/resolved model, adapter, actual provider/transport, normalized endpoint, finish reason, usage, phase, and attempt. Python, delta, and batch runtime helpers now return the complete result at [runtime.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/runtime.py:781), lines 825 and 863. Provider audit merging, classify/reply capture, final `Report`, harness forwarding, and `model_attempts.json` persistence retain the canonical shape.

4. **Retry policy — FAIL.** Runtime and provider predicates correctly require typed empty plus observed zero completion tokens. However, [runner.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:266) still trusts preexisting `failure_class == "infra_empty_response"` and `retryable_infra is True` after typed classification returns no match. A summary containing those flags plus canonical `malformed_json` evidence with zero tokens returns retryable. Direct reproduction produced:

   ```text
   _provider_infra_failure_class(summary) -> None
   _is_retryable_infra_summary(summary)   -> True
   ```

   Thus malformed non-empty output can still trigger a fresh subprocess/transport retry through conflicting persisted flags.

5. **Redaction — FAIL.** Canonical endpoints and failure previews are correctly sanitized, authorization schemes are tested, success previews are removed, and malformed JSON/JSONL artifacts are omitted. But [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/artifacts.py:62) sanitizes strings only when their key is sensitive, `endpoint`, or `raw_response_preview`. Parsed artifacts can therefore persist secrets embedded in ordinary fields. Direct reproduction left both unchanged:

   ```python
   {
       "content": "Authorization: Basic dXNlcjpwYXNz",
       "url": "https://example.test/v1?token=url-secret",
   }
   ```

   This violates the categorical requirement that authorization data and secret URL parameters cannot persist.

6. **Unsupported routes — PASS.** Unsupported routes normalize to explicit `unknown`; resolved model and adapter fail closed, and non-Hermes provider/transport are not inferred from endpoints. The end-to-end regression verifies requested model remains distinct while unavailable provenance is `unknown`.

7. **Scope and diff hygiene — PASS.** `git diff --check 45415680..a8d4974a` is clean. All 18 changed paths are B01 implementation, tests, or B01 oracle bookkeeping. The supplied “14 files” count is inaccurate—the range contains 15 non-oracle files plus three `.oracle` files—but no unrelated scope was found.

8. **Focused verification — UNAVAILABLE LOCALLY.** Pytest could not initialize because the read-only sandbox exposes no writable temporary directory, even with rerun and cache plugins disabled. No tests were collected. The supplied orchestrator result reports 556 passing tests; the final commit message reports 568, so the exact count is inconsistent. Live runs were appropriately skipped.

Issues requiring rework:

- [tests/live_agentic_harness/runner.py:266](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:266): derive retry directly from canonical typed evidence on every decision; do not trust inherited `failure_class` or `retryable_infra`. Add a conflicting-flags regression with `malformed_json`.
- [vibecomfy/agent/artifacts.py:62](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/artifacts.py:62): sanitize authorization headers and credential-bearing URLs in every persisted string leaf, including ordinary `content`, `message`, `error`, and `url` fields. Add parsed JSON/JSONL and synthesized response negative fixtures.
tokens used
121,557
B01 CHECKPOINT VERDICT: FAIL — canonical provenance is sound, but harness retry and artifact redaction each retain an acceptance-level bypass.

1. **Unified evidence contract — PASS.** `ModelAttemptEvidence` is defined once in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/executor/contracts.py:128), with `coerce_model_attempts` as the shared normalizer at line 218. Worker, runtime, provider/backend, executor, artifacts, and harness all consume `model_attempts`. The legacy `model_response` property is derived only and is not serialized.

2. **Failure taxonomy — PASS.** The closed set at [contracts.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/executor/contracts.py:36) distinctly represents `empty_response`, `malformed_json`, `non_json_content`, `missing_required_fields`, `timeout`, and `provider_failure`. Serialization preserves each value. Structural classification and fixtures cover all six.

3. **Success-path provenance — PASS.** Worker success evidence includes requested/resolved model, adapter, actual provider/transport, normalized endpoint, finish reason, usage, phase, and attempt. Python, delta, and batch runtime helpers now return the complete result at [runtime.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/runtime.py:781), lines 825 and 863. Provider audit merging, classify/reply capture, final `Report`, harness forwarding, and `model_attempts.json` persistence retain the canonical shape.

4. **Retry policy — FAIL.** Runtime and provider predicates correctly require typed empty plus observed zero completion tokens. However, [runner.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:266) still trusts preexisting `failure_class == "infra_empty_response"` and `retryable_infra is True` after typed classification returns no match. A summary containing those flags plus canonical `malformed_json` evidence with zero tokens returns retryable. Direct reproduction produced:

   ```text
   _provider_infra_failure_class(summary) -> None
   _is_retryable_infra_summary(summary)   -> True
   ```

   Thus malformed non-empty output can still trigger a fresh subprocess/transport retry through conflicting persisted flags.

5. **Redaction — FAIL.** Canonical endpoints and failure previews are correctly sanitized, authorization schemes are tested, success previews are removed, and malformed JSON/JSONL artifacts are omitted. But [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/artifacts.py:62) sanitizes strings only when their key is sensitive, `endpoint`, or `raw_response_preview`. Parsed artifacts can therefore persist secrets embedded in ordinary fields. Direct reproduction left both unchanged:

   ```python
   {
       "content": "Authorization: Basic dXNlcjpwYXNz",
       "url": "https://example.test/v1?token=url-secret",
   }
   ```

   This violates the categorical requirement that authorization data and secret URL parameters cannot persist.

6. **Unsupported routes — PASS.** Unsupported routes normalize to explicit `unknown`; resolved model and adapter fail closed, and non-Hermes provider/transport are not inferred from endpoints. The end-to-end regression verifies requested model remains distinct while unavailable provenance is `unknown`.

7. **Scope and diff hygiene — PASS.** `git diff --check 45415680..a8d4974a` is clean. All 18 changed paths are B01 implementation, tests, or B01 oracle bookkeeping. The supplied “14 files” count is inaccurate—the range contains 15 non-oracle files plus three `.oracle` files—but no unrelated scope was found.

8. **Focused verification — UNAVAILABLE LOCALLY.** Pytest could not initialize because the read-only sandbox exposes no writable temporary directory, even with rerun and cache plugins disabled. No tests were collected. The supplied orchestrator result reports 556 passing tests; the final commit message reports 568, so the exact count is inconsistent. Live runs were appropriately skipped.

Issues requiring rework:

- [tests/live_agentic_harness/runner.py:266](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:266): derive retry directly from canonical typed evidence on every decision; do not trust inherited `failure_class` or `retryable_infra`. Add a conflicting-flags regression with `malformed_json`.
- [vibecomfy/agent/artifacts.py:62](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/artifacts.py:62): sanitize authorization headers and credential-bearing URLs in every persisted string leaf, including ordinary `content`, `message`, `error`, and `url` fields. Add parsed JSON/JSONL and synthesized response negative fixtures.
