Reading additional input from stdin...
2026-08-13T10:57:28.030018Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:57:28.030059Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:57:28.030065Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffac5-1426-7973-a6d2-47c800cbeaba
--------
user
# MEGADO CHECKPOINT — Batch G0R (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the G0R oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**G0R — Truthful scorer/narrator and formal re-verdict.** Tasks + acceptance from `.oracle/tasklist.md` (G0R section). The diff to review: `git diff a890884f..16d80bbe` (post-revision SHA → G0R commit (tasklist numbering fix isolated in 23bddc6f, not part of this diff)). Plus `.gitignore` (.venv symlink) and `.oracle/briefs/batch-G0R.md`.

This batch closes the 4 unresolved issues from the ORIGINAL G0 oracle FAIL (`.oracle/checkins/G0.md` on main — issues 1–4 claimed fixed in `bfcde5a9` which contained zero code changes; issues 5–7 were genuinely fixed earlier in `ec732251`/`b85e173f`):

1. Residual `"unchanged"` implementation-message substring gate (was `assessor.py:774`, error severity) — must be REMOVED (only a comment reference may remain).
2. Missing structural expected-edit guard — `graph_unchanged=false` must require a positive integer `landed_operation_count`; missing/malformed/zero fails closed; grounded-refusal + non-edit routes exempt.
3. Narrator artifact-write failure must not replace the already-selected agent message (`_frag_narrator.py` outer fallback catch `:457-477`).
4. Narrator prompt contradiction around `validation.passed` (`:245` region) — prompt must not forbid mentioning validation while requiring `validation.passed` description.

## Executor evidence (DeepSeek V4 Flash)

- 20 passed (guard-contract + score-honesty slice incl. new fixtures), 324 deselected.
- `tests/test_edit_narrative.py`: 38 passed (37 + 1 new regression `test_artifact_write_failure_preserves_selected_agent_message`).
- `test_classify_provider_error_preserves_type_and_worker_evidence_on_wrap`, `test_classify_failure_report_has_no_invented_respond_plan`, `tests/test_executor_contracts.py`: 348 passed (G0-T4/issues 5–6 regressions still green).
- Regression effectiveness proven: reverting the narrator guard makes `test_artifact_write_failure_preserves_selected_agent_message` fail (fallback returned instead of selected message); guard restored.
- Historical rescore: `out/agentic/` artifacts ABSENT in this worktree → re-binning recorded as unavailable (no inference from docs).

## Review focus (adversarial)

1. Confirm NO residual substring/phrasing/implementation-message gate remains in `assessor.py` (grep for `"unchanged"`, `message_artifact`, `_MESSAGE_`, `_NARRATIVE_`).
2. Confirm the landed-count guard is structural (reads `change_details.landed_operation_count`), fails closed on missing/malformed/zero, exempts grounded refusals + non-edits, and has negative controls.
3. Confirm the narrator change preserves the already-selected message when the artifact write itself raises — check the call site + the regression actually forces the write to raise.
4. Confirm the prompt contradiction is resolved (single consistent instruction about `validation.passed`).
5. Confirm the diff contains ONLY G0R-scope changes (scorer/narrator/tests) — no unrelated edits, no weakened criteria.
6. Run the focused verification yourself where sandbox permits:
   - `.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py`
   - `.venv/bin/python -m pytest -q tests/test_edit_narrative.py`
   - `git diff --check a890884f..16d80bbe`
   (Live runs and the full suite are orchestrator-phase; skip them.)
7. Sanity-check the nine former matcher counterexample fixtures exist and pass with zero matcher failures.

## Output

First line: `G0R CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–7) with evidence, and an issue list if FAIL (each with file:line + what to rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’ll use the repository’s megado review instructions and delegate the wide, read-only checks so the final verdict is independently cross-checked. I’ll first read the applicable skill guidance, then inspect the requested diff and run only the permitted focused tests.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, high reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where an oracle (GPT-5.6 Sol or Grok 4.6 via the grok CLI) reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

A delivery pipeline for a whole project: **Codex plans, DeepSeek explores, Codex revises, DeepSeek executes, Codex oracles** — all in a worktree, opened and synced when done. Two workhorse models — **DeepSeek V4 Flash** and **GPT-5.6 Sol** — plus **Grok 4.6** via the grok CLI as an optional oracle.

The shape (from the original ask, normalized):

1. In a worktree, Codex (GPT-5.6 Sol, high reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at high reasoning produces this structure.
5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol — or **Grok 4.6** via the grok CLI — acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
6. Open it and sync.

## Roles

| Role | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Planner / Oracle** | GPT-5.6 Sol (oracle may also be **Grok 4.6** via the grok CLI) | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` · oracle: `grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high --permission-mode plan` | read-only for planning/review; `workspace-write` when it implements — oracle delegates verification/research to Flash per the mandate |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Hard-task executor** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | `workspace-write`; `danger-full-access` to orchestrate Flash per the mandate |

The whole pipeline runs on two workhorse models — **DeepSeek V4 Flash** (cheap, fast, coding-tuned — exploration and normal execution) and **GPT-5.6 Sol** (frontier planning, revision, hard tasks) — with **Grok 4.6** via the grok CLI as an alternative oracle for checkpoint review. Escalate exploration to DeepSeek V4 Pro only on evidence that Flash's findings are thin.

One orchestrator (the host agent) drives all phases and holds the artifacts; each subagent gets a self-contained brief and returns only its conclusion.

## Delegation mandate — oracle & XHARD run as manager/validator

Both the **oracle** (checkpoint review) and the **`[XHARD]` executor** are **managers and validators of DeepSeek V4 Flash, not workers**. Every oracle check-in brief and every `[XHARD]` task brief MUST carry the following instruction verbatim — it is not optional:

> DELEGATION MANDATE — You are a manager and validator of DeepSeek V4 Flash, NOT a worker. Use DeepSeek V4 Flash via OMP for as much of this work as possible — `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" --query-file=<brief> --project-dir=<worktree>` (research-only briefs: `--toolsets="file,web"`).
>
> - Research needed? Dispatch it to Flash. Execution needed? Dispatch it to Flash. Decompose the work into Flash-sized briefs and fan them out.
> - Your own job is to **direct, then validate**: read what Flash produced, check it against the acceptance criteria, and only do work yourself when delegation is impossible — Flash already failed at it, or the piece is too small / too tightly coupled to your own reasoning to hand off.
> - Do NOT default to doing the work yourself. If you catch yourself implementing or researching directly, stop and ask whether a Flash brief would cover it. It almost always would.

Hosts: build the briefs for the oracle / XHARD runs around this mandate — the prompt must tell the model what to direct, what to verify, and that Flash does the hands-on work.

## Artifacts (in the worktree)

```
.oracle/
  plan.md            # living plan: v1 from Codex, revised each loop
  briefs/            # one brief per explorer / executor batch
  findings/          # explorer outputs: <area>.txt (+ .meta.json from fan.py)
  tasklist.md        # frozen batched task list with checkpoints + [XHARD] tags
  checkins/          # oracle verdicts: batch-<N>.md
  status.md          # current phase, batch, checkpoint state
```

## Phase 0 — Worktree

Run the whole pipeline on a branch, never on main.

```bash
git worktree add ../<project>-oracle -b oracle-run
cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins
```

## Phase 1 — Initial plan (Codex)

Brief GPT-5.6 Sol at high reasoning. Demand three outputs, in order:

1. A tasklist covering the **entirety** of the project (not just the obvious path).
2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
3. Open questions / potential issues.

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/plan-brief.md)" </dev/null > /tmp/plan-v1.txt 2>&1
```

The brief is a spec, not a memo: project path, goal, constraints, "list every area you'd explore for full clarity — don't stop at what's obvious." Save the result as `.oracle/plan.md` (host writes it; Codex stays read-only).

## Phase 2 — Deep exploration (DeepSeek fan-out)

One DeepSeek V4 Flash agent per area, in parallel. `fan.py` for ≥ ~5 areas; `launch_hermes_agent.py` per area below that.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
```

Each brief: "Explore area X in depth. Report verified facts with file/line evidence, unknowns, risks, and a suggested approach. Ranked findings, <300 words." Exploration answers the *plan's* questions — mechanical briefs, no license to architect.

## Phase 3 — Revise-until-stable loop

Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Codex (GPT-5.6 Sol, high reasoning):

> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

- New material areas → re-run Phase 2 for those, then revise again.
- Repeat until Codex returns `STABLE` (or two consecutive rounds with no material change).
- The plan is a living doc during this loop; it freezes at Phase 4.

## Phase 4 — Batched tasklist with checkpoints (Codex)

Ask Codex (GPT-5.6 Sol, high reasoning) to convert the stable plan into an execution structure:

- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
- **`[XHARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
- **Per-batch acceptance criteria** the oracle will verify.

Emit as markdown (or JSON if the host will script it) into `.oracle/tasklist.md`. This file is **frozen** — execution follows it; plan revisions during execution go through the oracle, not silent edits.

## Phase 5 — Execute, with oracle checkpoints

Per batch, in order:

**1. Execute the batch.** DeepSeek Flash takes every non-`[XHARD]` task — one agent per batch, terminal toolset so it can run code and tests:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
```

`[XHARD]` tasks go to GPT-5.6 Sol instead (brief carries the delegation mandate):

```bash
timeout 1800 codex exec --sandbox danger-full-access -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/hard-task-brief.md)" </dev/null
```

The `[XHARD]` executor is expected to orchestrate Flash subagents, so it runs `danger-full-access` — hermes agents need outbound network. Use `--sandbox workspace-write` only when a task genuinely cannot be delegated.

**2. Checkpoint — oracle review.** Send the batch's completed work to the oracle — GPT-5.6 Sol (high reasoning) or Grok 4.6 (via the grok CLI):

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/checkin-brief.md)" </dev/null > .oracle/checkins/batch-<N>.md 2>&1
```

Or, with Grok 4.6 as the oracle (headless single-turn; `--permission-mode plan` keeps it read-only):

```bash
grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high \
  --permission-mode plan > .oracle/checkins/batch-<N>.md 2>&1
```

The check-in brief carries: the batch's tasks + acceptance criteria from `tasklist.md`, the diff since the last checkpoint (`git diff <last-checkpoint-sha>..HEAD` — commit after each batch so the oracle sees a clean delta), and the delegation mandate. The oracle reviews by dispatching verification/research to Flash where useful, then judging the results; when it delegates, the codex run needs `--sandbox danger-full-access` and the grok variant must drop `--permission-mode plan` (hermes agents need outbound network + terminal). Verdict is binary: `PASS` or a list of issues.

**3. Rework loop.** On issues, send them back to the executor (Flash for normal, GPT-5.6 Sol for XHARD), re-run, re-review — until the oracle passes. **Do not start batch N+1 until batch N passes.**

## Phase 6 — Completion

1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
3. `open` the worktree / project for the user, and report phase-by-phase evidence.

## Gotchas

- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. That is exactly why oracle and XHARD runs default to `danger-full-access` under the delegation mandate; host-side orchestration still applies to plain explorer/executor batches.
- **Match brief shape to model mode.** Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs derived straight from the tasklist. Judgement (exploration, revision, oracle) stays at GPT-5.6 Sol — or at Grok 4.6 via the grok CLI for the oracle role; escalate Flash exploration to DeepSeek V4 Pro only on evidence.
- **Liveness ≠ correctness.** Watch `fan.py` `.meta.json` files and the stderr `[tool]`/`[done]` heartbeat; check 30–60 s after launch, not 10 minutes in. But a live agent can still answer uselessly — read the response.
- **Checkpoint discipline is the whole game.** The oracle gate is what makes quality; skipping it to "save a cycle" collapses this into a plain DeepSeek run.
- **Elegance bias is a real instruction.** Codex's revision prompt must name it; otherwise reasoning models add scope, not subtract it.

## Quick reference

```bash
# Phase 0
git worktree add ../<project>-oracle -b oracle-run && cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins

# Phase 1 — initial plan (GPT-5.6 Sol, high reasoning)
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/plan-brief.md)" </dev/null

# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"

# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [XHARD] tags)

# Phase 5 — execute (DeepSeek V4 Flash, one agent per batch)
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
# [XHARD] tasks (brief carries delegation mandate): codex exec --sandbox danger-full-access -c model=gpt-5.6-sol -c model_reasoning_effort=high
# checkpoint (oracle: GPT-5.6 Sol or Grok 4.6; brief carries delegation mandate, so use danger-full-access / drop --permission-mode plan when it delegates to Flash): codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/checkin-brief.md)" </dev/null
#   or: grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high --permission-mode plan

# Phase 6 — commit, push, open
git add -A && git commit -m "megado: <project>" && git push && open .
```

exec
/bin/zsh -lc "sed -n '1,280p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.

Three pathways:

| Pathway | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Hermes agentic** *(default)* | DeepSeek V4 (Pro/Flash), Kimi K2.7, Zhipu GLM, … | `launch_hermes_agent.py` — or `fan.py` to run N in one process | `file`, `web`, optional `terminal` |
| **Codex** | GPT-5.5 | `codex exec` (CLI) | sandboxed workspace |
| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |

**Default to the hermes agentic pathway, and to DeepSeek Flash within it** — different model family, cheap, fast, tool-using. Reach for DeepSeek Pro only when the task needs reasoning judgement; reach for Codex or Claude only when you specifically want their strengths.

> **⚠️ Network sandbox warning for Codex subagents**
> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Hermes agents (DeepSeek/Kimi/MiMo/GLM/OpenRouter) need outbound network to reach their provider APIs, so **launching them from inside a `codex exec` subagent will fail**. The launcher itself is fine; it fails only because the parent process has no network.
>
> **Workarounds:**
> 1. Launch the hermes subagent directly from a normal shell or Bash tool.
> 2. If you need a **Codex subagent to orchestrate hermes subagents**, run the
>    outer Codex command with `--sandbox danger-full-access` and seal stdin with
>    `</dev/null`, for example:
>
>    ```bash
>    timeout 3600 codex exec --sandbox danger-full-access \
>      -c model_reasoning_effort=high \
>      "$(cat /tmp/brief.md)" </dev/null
>    ```
>
>    `read-only` and `workspace-write` both disable outbound network for the
>    Codex subprocess; only `danger-full-access` allows nested Hermes provider
>    API calls from inside `codex exec`. Tell Codex explicitly to use
>    `launch_hermes_agent.py` or `fan.py`, and to spend its own context budget
>    by delegating broad searches, file mapping, and independent reviews to
>    DeepSeek/Kimi subagents wherever practical.
>
> This network restriction does not affect Codex or Claude subagents.

## Picking a pathway

- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
- **Already have the answer?** → don't dispatch. Subagents aren't free.

## Use the cheapest subagent that can do the job

Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.

1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`, **the default**) — non-reasoning, fast, cheap. The default for most dispatches: implementation, mechanical edits, focused investigation, verification. Escalate to Pro only on evidence that reasoning is needed.
3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`) — reasoning model. Use when the task needs judgement: root-cause analysis, "is this sound", "should this merge".
4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.

Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.

Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.

---

## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default

A real tool-using agent in a non-Claude model's voice, far lighter than a `megaplan` run. It wraps megaplan's `AIAgent` primitive as a standalone CLI: the agent reads files, searches the codebase, fetches URLs, and (with `terminal`) runs commands — single-turn, no plan state or critique loop. For a pure-chat opinion with no repo access, run the same command with `--toolsets=""`.

The launcher discovers the active runtime itself. It first tries an installed legacy `megaplan.agent` distribution, then falls back to the current Arnold checkout (`~/Documents/Arnold` by default, or `ARNOLD_PATH=/path/to/Arnold`). Do not add an `arnold_pipelines.megaplan.agent` compatibility package to fix import failures; the real Hermes runtime lives under `arnold_pipelines.megaplan.agent` in the Arnold checkout.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --toolsets="file,web" \
  --query-file=/tmp/brief.md \
  --max-tokens=65536 \
  --project-dir="$PWD"
# Final response → stdout; tool progress/timings → stderr.
```

Key flags:

- **`--model`** (default `deepseek:deepseek-v4-flash`). Prefix convention from the megaplan key pool:
  - `fast`, `mimo`, `mimo-fast` → `mimo:mimo-v2.5-pro-ultraspeed` (very fast MiMo path; requires `MIMO_API_KEY`)
  - `deepseek:deepseek-v4-flash` (default, non-reasoning) / `deepseek:deepseek-v4-pro` (reasoning) → DeepSeek API
  - `kimi:kimi-k2.7-code` → Kimi coding API (requires `KIMI_API_KEY` or `MOONSHOT_API_KEY`)
  - `zhipu:glm-5.2` / `zhipu:glm-4.6` → Zhipu GLM API (requires `ZHIPU_API_KEY`)
  - `google:gemini-…`, `minimax:MiniMax-M2`, … — see `megaplan/runtime/key_pool.py:resolve_model`
- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.

Output is **freeform text** — if you want JSON, ask for it in the prompt and parse defensively; for an *enforced* schema, use megaplan, not this pathway.

### Fan out N at once — `fan.py`

`launch_hermes_agent.py` is one subprocess per call; each re-imports the Arnold/Hermes runtime. For **≥ ~5 parallel agents or programmatic batches**, `fan.py` runs N `AIAgent`s in one process (imports once, ~5–15× less RAM). Same flags, plus a briefs directory and per-task output:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=/tmp/briefs --output-dir=/tmp/results \
  --max-workers=5 --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --max-tokens=65536 --task-timeout=1800 --project-dir="$PWD"
# Or positional brief paths instead of --briefs-dir.
# Per-brief models: --model-map="fast:scan-*.md,pro:verdict-*.md"
```

Each brief `<stem>.md` yields `<stem>.txt` (response), `<stem>.meta.json` (status/timing/tool_calls), and an aggregate `_report.json`. Kill a running fan from another shell: `fan_kill.py --output-dir=… [--hard]`. Default `--task-timeout=1800` (30 min — forensic work with ≥10 tool calls routinely exceeds 10 min; the old 600s default would silently SIGKILL agents mid-investigation). Bump higher for very heavy briefs (e.g. `--task-timeout=3600` for cross-file audits). Add `--isolation=processes` if you need to SIGKILL one task without touching the rest. Below ~5 parallel, just launch `launch_hermes_agent.py` N times in parallel Bash calls — simpler.

### Use `megaplan` instead when you need

multi-phase orchestration (plan → critique → revise → execute → gate → review), schema-enforced output, persistent plan state / approval gates, or the megaplan sandbox. See *Multi-phase delegation* below.

### Liveness

The script logs `[tool]` / `[done]` to stderr every 1–5 s while alive and ends with `[launch_hermes_agent] done in N.Ns`. No new tool lines for minutes = wedged. For `fan.py`, watch `.meta.json` files appearing under `--output-dir`.

---

## 2. Codex (GPT-5.5)

`codex exec` from Bash (the `/codex:*` plugin wraps the same call).

```bash
codex exec --sandbox read-only "$(cat /tmp/prompt.md)" </dev/null > /tmp/out.txt 2>&1
```

- `--sandbox read-only | workspace-write | danger-full-access` — analysis / let it edit files / full shell.
- `-c model_reasoning_effort=low|medium|high` — `medium` default.
- `codex exec review [--pr <n>]` for PR review; `codex apply` to apply its last diff.
- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).

## 3. Claude (Opus/Sonnet/Haiku)

Use the Claude CLI launcher when you need an explicit model selector from any
host, including Codex sessions where the platform `spawn_agent` tool does not
expose a model field:

```bash
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus \
  --query-file=/tmp/brief.md \
  --project-dir="$PWD" \
  --tools="Read,Grep,Glob" \
  --timeout=1800
```

`--model` accepts Claude Code aliases such as `opus` / `sonnet` / `haiku` or a
full model name such as `claude-opus-4-8`. The launcher invokes
`claude --print --model <model>` with `--project-dir` as the subprocess cwd and
prints the final answer to stdout while diagnostics go to stderr. It leaves
Claude Code's default tool policy alone unless you pass `--tools`; use
`--permission-mode` deliberately. It adds `--no-session-persistence` by default
so one-off subagents do not clutter Claude history; pass `--keep-session` when
you want resumability.

When you are already inside Claude Code and the `Agent` tool is available,
you can still dispatch through it — cleanly-scoped, no memory of the outer
conversation, so the prompt must be self-contained. Subagent types:
`general-purpose` (full tools), `Explore` (fast read-only search), `Plan`
(architect, no code), `claude-code-guide`, `code-reviewer`.

```
Agent({ description: "…", subagent_type: "general-purpose",
        prompt: "<self-contained brief: working dir, files, what to return, length cap>" })
```

Prefer Claude over Codex when you want the *same family* of judgement isolated from this thread (keeping the main context clean), or specifically want Opus judgement. For genuinely different model-family judgement, prefer Codex, DeepSeek, or Kimi.

---

## Multi-phase delegation (when a single-turn agent isn't enough)

When DeepSeek/Kimi need a full plan-execute-review cycle across many files, route through megaplan:

```bash
PYENV_VERSION=3.11.11 megaplan init --project-dir "$PWD" \
  --profile all-deepseek-pro-direct --robustness light "<task>"
# Kimi: --profile all-open
```

`--robustness light` is a fast single pass; drop it for the full workflow (default `full`). The **`megaplan-decision`** skill covers the profile / robustness / depth dials.

## Writing the prompt (any pathway)

The receiving model has **zero context** from your conversation. Brief it like a smart colleague who just walked in:

**Is your brief a spec or a memo?** A spec lists inputs and outputs (do X at line Y, then Z). A memo explains context and asks for judgement. Reasoning models will treat any memo as license to architect — even if the underlying ask was 5 mechanical edits. If the work is mechanical, strip the rationale; the "why" belongs in the commit message, not the brief.

- Working directory and **exact** file paths (not "the relevant files").
- Goal + why it matters; what you've already ruled out.
- Output shape and a length cap ("ranked list, < 300 words").
- For adversarial / second-opinion work, tell it to take a position and not hedge — otherwise it hedges.
- Anti-pattern: the options menu. "Pick whichever of A/B/C fits" reliably invites a reasoning model to optimize across the options and often produce a fourth one you didn't ask for. One ask, one solution path. Save options menus for genuine judgement calls — and when you do use them, route the work to a non-reasoning model that can't optimize past them.

Don't dispatch what you already know, and don't re-ask what you've answered — add a twist (rank these, find the flaw, argue the other side) or skip it.

## Judge / jury for high-stakes calls

Send the same unbiased prompt to several models in parallel (Codex + hermes-DeepSeek + hermes-Kimi, optionally a Claude `Agent`) and compare — convergence on a subtle call is far stronger than one model's confidence; divergence is signal. Reserve it for risky pre-merge reviews, hard-to-reverse architecture calls, security-sensitive paths. Don't fan out routine work. For a multi-lens sense-check of one proposal (human-user / agent-user / abstraction lenses), give each agent only its own lens and never show one's output to another.

## Detecting hangs

Check liveness **30–60 s after launch**, not 10 minutes in.

- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.

**Liveness ≠ correctness.** A subagent can stream for 10 minutes and still answer uselessly — read the response; there's no shortcut.

## Quick reference

```bash
# 1. Hermes agentic (default) — DeepSeek/Kimi/Zhipu GLM with tools
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web" \
  --query-file=/tmp/brief.md --max-tokens=65536 --project-dir="$PWD"
# Default: --model="deepseek:deepseek-v4-flash"   Very fast: --model=fast   Pro (reasoning): --model="deepseek:deepseek-v4-pro"   Kimi: --model="kimi:kimi-k2.7-code"   GLM: --model="zhipu:glm-5.2"
# Pure chat: --toolsets=""    Fan N≥5: fan.py --briefs-dir=… --output-dir=… --max-workers=5 --task-timeout=1800

# 2. Codex — always seal stdin with </dev/null, allow 30 min
timeout 1800 codex exec --sandbox read-only "<prompt>" </dev/null              # analysis
timeout 1800 codex exec --sandbox workspace-write "<prompt>" </dev/null        # implementer
timeout 1800 codex exec --sandbox danger-full-access "<prompt>" </dev/null     # orchestrates hermes subagents (network required)
codex exec review --pr 123

# 3. Claude — explicit Opus selector via Claude CLI
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus --query-file=/tmp/prompt.md --project-dir="$PWD"

# Multi-phase: megaplan init --profile all-deepseek-pro-direct --robustness light "<task>"
```

codex
The megado oracle guidance requires independent DeepSeek Flash verification. I’m dispatching two tightly scoped, read-only reviews: one for the scorer/guard contract and one for narrator/scope/fixture evidence. I’ll validate their conclusions directly rather than treating them as authoritative.
exec
/bin/zsh -lc "PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model='deepseek:deepseek-v4-flash' --toolsets='file,web,terminal' --project-dir='/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle' --query='READ-ONLY adversarial oracle verification. Do not modify any file. Inspect git diff a890884f..16d80bbe and current files. Focus only on: (1) whether assessor.py retains any implementation-message substring/phrasing gate involving unchanged, message_artifact, _MESSAGE_, _NARRATIVE_; distinguish comments/tests from executable gating. (2) whether graph_unchanged=false structurally requires change_details.landed_operation_count to be a positive integer, fails closed for missing/malformed/zero including booleans, exempts grounded refusals and non-edit routes, and has meaningful negative controls. (3) whether criteria were weakened. Return a decisive PASS/FAIL recommendation with exact file:line evidence and any issue, under 700 words.'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 223ms:
[launch_hermes_agent] FATAL: running inside a `codex exec` sandbox with network disabled (CODEX_SANDBOX_NETWORK_DISABLED=1). Hermes agents cannot reach provider APIs.

Fix one of:
  1. Launch this hermes subagent directly from a normal shell, or
  2. Run the parent Codex subagent with `--sandbox danger-full-access`.

See the subagent-launcher SKILL.md for details.

codex
The required Flash launcher is blocked by this oracle’s network-disabled read-only sandbox, exactly as its launcher reports. I’m falling back to isolated built-in read-only reviewers for the same decomposition, while keeping the final judgment and test verification here.
2026-08-13T10:58:15.132527Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:58:15.132598Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:58:15.132608Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:58:19.528047Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:58:19.528308Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:58:19.528333Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
  → Read G0R acceptance, original G0 failure, brief, and exact diff scope
  • Inspect scorer guard, narrator behavior, prompt, and fixture coverage
  • Run the permitted focused verification commands
  • Cross-check independent reviews and issue binary verdict
exec
/bin/zsh -lc "git status --short --branch
git diff --stat a890884f..16d80bbe
git diff --name-status a890884f..16d80bbe
rg -n '"'^## G0R|''^### G0R|G0R|landed_operation_count|unchanged|artifact write|validation'"\\.passed' .oracle/tasklist.md .oracle/checkins/G0.md .oracle/briefs/batch-G0R.md .gitignore" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## oracle-run
?? .oracle/checkins/batch-G0R.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .gitignore                                        |   1 +
 .oracle/briefs/batch-G0R-rework.md                |  41 +++
 .oracle/briefs/batch-G0R.md                       |  56 ++++
 tests/live_agentic_harness/assessor.py            | 137 ++++++++-
 tests/test_edit_narrative.py                      |  56 ++++
 tests/test_live_agentic_assessor_score_honesty.py |  56 +++-
 tests/test_live_agentic_harness_guard_contract.py | 339 +++++++++++++++++++++-
 vibecomfy/comfy_nodes/agent/_frag_narrator.py     |  30 +-
 8 files changed, 693 insertions(+), 23 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	.gitignore
A	.oracle/briefs/batch-G0R-rework.md
A	.oracle/briefs/batch-G0R.md
M	tests/live_agentic_harness/assessor.py
M	tests/test_edit_narrative.py
M	tests/test_live_agentic_assessor_score_honesty.py
M	tests/test_live_agentic_harness_guard_contract.py
M	vibecomfy/comfy_nodes/agent/_frag_narrator.py
.oracle/briefs/batch-G0R.md:1:# MEGADO BATCH G0R — Truthful scorer/narrator and formal re-verdict
.oracle/briefs/batch-G0R.md:9:1. `tests/live_agentic_harness/assessor.py:774` — residual `"unchanged"` implementation-message substring gate (error severity) still gates scoring.
.oracle/briefs/batch-G0R.md:10:2. Missing structural expected-edit guard: `graph_unchanged=false` with zero/missing `landed_operation_count` passes.
.oracle/briefs/batch-G0R.md:12:4. `_frag_narrator.py:245` region — narrator prompt contradiction: it forbids mentioning validation while requiring `validation.passed` to be described.
.oracle/briefs/batch-G0R.md:16:1. **Remove the residual `"unchanged"` prose gate** in `tests/live_agentic_harness/assessor.py` (around `:774`): delete the substring failure over `implementation_result.message`. Add a counterexample fixture: an edit message like "Updated the sampler; other nodes are unchanged" must NOT affect scoring.
.oracle/briefs/batch-G0R.md:18:2. **Restore the structural expected-edit guard** (around `assessor.py:613`): for an expected successful edit, `graph_unchanged=false` must be accompanied by a positive integer `change_details.landed_operation_count`. Missing, malformed, or zero counts fail closed. Grounded-refusal and explicitly non-edit routes are exempt. Add a negative control fixture.
.oracle/briefs/batch-G0R.md:22:4. **Remove the narrator prompt contradiction** around `_frag_narrator.py:245`: the prompt must not simultaneously forbid mentioning validation and require describing `validation.passed`. Make the instruction consistent (describe validation outcome truthfully).
.oracle/tasklist.md:25:## G0R — Truthful scorer/narrator and formal re-verdict
.oracle/tasklist.md:29:1. Remove the remaining `"unchanged"` implementation-message substring gate.
.oracle/tasklist.md:31:   - `graph_unchanged=false` requires a positive integer `landed_operation_count`;
.oracle/tasklist.md:35:4. Remove the narrator prompt contradiction around `validation.passed`.
.oracle/tasklist.md:227:- Ordinary validation failures are unchanged.
.oracle/tasklist.md:348:   - focused G0R/B01/D13/B04/B03/B05/B06/B07/B08 tests;
.oracle/checkins/G0.md:26:2. G0-T2 prose-gating removal + fact-grounded synthesis — assessor `message_artifact` collector + all `_MESSAGE_*` patterns removed (structured checks untouched); producer-side `_validate_narrative_message` + `_guard_narrative_message` + `_narrator_fast_path_applies` deleted; the LLM narrator is the sole path and its message ALWAYS ships (deterministic fallback only when no agent message exists — provider failure); narrator prompt now REQUIRES describing graph_unchanged/outcome.kind/landed_operation_count/validation.passed. 9 counterexample fixtures + 4 structured controls in the guard-contract tests. edit.__all__ 472→462 (10 dead narrative-guard helpers removed; frozen manifest + PINNED_EDIT_EXPORT_COUNT updated).
.oracle/checkins/G0.md:27:3. G0-T3 infra reclassification — runner.py: "could not be parsed" + observed completion_tokens==0 → retryable_infra (`infra_empty_response`); nonzero or no usage evidence stays product_fail; retry loop unchanged so the harness retry now fires.
.oracle/checkins/G0.md:608:- Production code unchanged in this task.
.oracle/checkins/G0.md:613:- End state (three clauses): (a) the agent ALWAYS writes the message — no deterministic substitute ever ships (producer-side discard-and-replace removed); (b) the message is written FROM the facts — the synthesis prompt feeds the agent the structured outcome (`graph_unchanged`, `outcome.kind`, `landed_operation_count`, validation details) and requires the narrative to describe exactly those facts; (c) scoring is structured-only — prose never gates a scenario.
.oracle/checkins/G0.md:801:- The known Set/Get broadcast pattern that expands one raw link to four lowered links emits successfully when terminal consumers are unchanged.
.oracle/checkins/G0.md:872:   - Feed the model the failed batch, typed exception/traceback, and unchanged authoritative state. Permit exactly one repair attempt for NameError-class deterministic batch exceptions.
.oracle/checkins/G0.md:923:   - Always persist `original.ui.json` and `final.ui.json`; for an unchanged/refused turn, final is an explicit copy/projection of the authoritative original. Keep `candidate.ui.json` for edit-candidate compatibility where applicable.
.oracle/checkins/G0.md:1277:docs/failure-analysis/agentic-pipeline-improvement-2026-08.md:35:- A1 **message_artifact regex false positives**: naive word-boundary matchers (`assessor.py:47-53`) — "I have **not applied**" matches `\bapplied\b`; "nodes are **unchanged**" matches `\bunchanged\b` against a changed graph; "not **connected**" matches `\bconnected\b`. 9 matcher-only failures; ~27 scenarios carry message_artifact errors. Check added 2026-07-01 (`0e524b33`) — after baseline.
.oracle/checkins/G0.md:1297:.oracle/tasklist.md:300:   - Feed the model the failed batch, typed exception/traceback, and unchanged authoritative state. Permit exactly one repair attempt for NameError-class deterministic batch exceptions.
.oracle/checkins/G0.md:1310:.oracle/checkins/G0.md:872:   - Feed the model the failed batch, typed exception/traceback, and unchanged authoritative state. Permit exactly one repair attempt for NameError-class deterministic batch exceptions.
.oracle/checkins/G0.md:1444:            "detail": "Expected graph change but response.graph_unchanged is True."
.oracle/checkins/G0.md:1966:- A1 **message_artifact regex false positives**: naive word-boundary matchers (`assessor.py:47-53`) — "I have **not applied**" matches `\bapplied\b`; "nodes are **unchanged**" matches `\bunchanged\b` against a changed graph; "not **connected**" matches `\bconnected\b`. 9 matcher-only failures; ~27 scenarios carry message_artifact errors. Check added 2026-07-01 (`0e524b33`) — after baseline.
.oracle/checkins/G0.md:2339:/bin/zsh -lc "rg -n \"_MESSAGE_|message_artifact|_validate_narrative_message|refused_narrative|_NARRATIVE_\" vibecomfy tests || true; rg -n \"graph_changed|graph_unchanged|outcome_kind|landed_operation_count|gates|validation\\.passed|validation\" tests/live_agentic_harness/assessor.py vibecomfy/comfy_nodes/agent/{edit_humanize.py,_frag_humanize.py,edit_narrator.py,_frag_narrator.py} | sed -n '1,260p'; git diff --unified=12 fa06a300..HEAD -- tests/live_agentic_harness/assessor.py | sed -n '1,300p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy
.oracle/checkins/G0.md:2347:vibecomfy/comfy_nodes/agent/_frag_narrator.py:71:    def landed_operation_count(self) -> int:
.oracle/checkins/G0.md:2348:vibecomfy/comfy_nodes/agent/_frag_narrator.py:74:            return int(change.get("landed_operation_count") or 0)
.oracle/checkins/G0.md:2359:vibecomfy/comfy_nodes/agent/_frag_narrator.py:264:    "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
.oracle/checkins/G0.md:2360:vibecomfy/comfy_nodes/agent/_frag_narrator.py:266:    "  - change.landed_operation_count: how many operations actually landed.\n"
.oracle/checkins/G0.md:2361:vibecomfy/comfy_nodes/agent/_frag_narrator.py:267:    "  - validation.passed: whether post-edit validation passed.\n"
.oracle/checkins/G0.md:2362:vibecomfy/comfy_nodes/agent/_frag_narrator.py:268:    "Never claim an edit you did not land: when graph_unchanged is true or "
.oracle/checkins/G0.md:2363:vibecomfy/comfy_nodes/agent/_frag_narrator.py:269:    "landed_operation_count is 0, you MUST NOT say the graph was edited, "
.oracle/checkins/G0.md:2365:vibecomfy/comfy_nodes/agent/_frag_narrator.py:271:    "when validation.passed is false. The message must be consistent with "
.oracle/checkins/G0.md:2366:vibecomfy/comfy_nodes/agent/_frag_narrator.py:370:    (``change.graph_unchanged``, ``outcome.kind``,
.oracle/checkins/G0.md:2367:vibecomfy/comfy_nodes/agent/_frag_narrator.py:371:    ``change.landed_operation_count``, ``validation.passed``) and requires the
.oracle/checkins/G0.md:2372:vibecomfy/comfy_nodes/agent/_frag_humanize.py:599:        "landed_operation_count": _total_landed_edit_count(state),
.oracle/checkins/G0.md:2374:vibecomfy/comfy_nodes/agent/_frag_humanize.py:623:        "changed (change.graph_changed / change.graph_unchanged), the outcome kind "
.oracle/checkins/G0.md:2375:vibecomfy/comfy_nodes/agent/_frag_humanize.py:624:        "(outcome.kind), and how many operations landed (change.landed_operation_count). "
.oracle/checkins/G0.md:2376:vibecomfy/comfy_nodes/agent/_frag_humanize.py:625:        "Never claim an edit you did not land: when graph_unchanged is true or "
.oracle/checkins/G0.md:2377:vibecomfy/comfy_nodes/agent/_frag_humanize.py:626:        "landed_operation_count is 0, you MUST NOT say the graph was edited, applied, "
.oracle/checkins/G0.md:2379:vibecomfy/comfy_nodes/agent/_frag_humanize.py:628:        "validation.passed is false. Describe exactly those facts."
.oracle/checkins/G0.md:2381:vibecomfy/comfy_nodes/agent/_frag_humanize.py:645:                "(change.graph_unchanged), the outcome kind (outcome.kind), and the landed "
.oracle/checkins/G0.md:2382:vibecomfy/comfy_nodes/agent/_frag_humanize.py:646:                "operation count (change.landed_operation_count).",
.oracle/checkins/G0.md:2384:vibecomfy/comfy_nodes/agent/_frag_humanize.py:652:                "applied, or a connection was made when graph_unchanged is true or "
.oracle/checkins/G0.md:2385:vibecomfy/comfy_nodes/agent/_frag_humanize.py:653:                "landed_operation_count is 0",
.oracle/checkins/G0.md:2386:vibecomfy/comfy_nodes/agent/_frag_humanize.py:654:                "Claiming validation passed when validation.passed is false",
.oracle/checkins/G0.md:2389:vibecomfy/comfy_nodes/agent/_frag_humanize.py:814:        "landed_operation_count": int(change_details.get("landed_operation_count") or 0),
.oracle/checkins/G0.md:2390:vibecomfy/comfy_nodes/agent/_frag_humanize.py:868:    landed_operation_count = int(compact_change_details.get("landed_operation_count") or 0)
.oracle/checkins/G0.md:2391:vibecomfy/comfy_nodes/agent/_frag_humanize.py:869:    graph_changed = bool(_batch_candidate_graph_changed(state) or landed_operation_count > 0)
.oracle/checkins/G0.md:2394:vibecomfy/comfy_nodes/agent/_frag_humanize.py:890:            "graph_unchanged": not graph_changed,
.oracle/checkins/G0.md:2395:vibecomfy/comfy_nodes/agent/_frag_humanize.py:891:            "landed_operation_count": landed_operation_count,
.oracle/checkins/G0.md:2397:vibecomfy/comfy_nodes/agent/_frag_humanize.py:909:            "graph_unchanged": failure.graph_unchanged,
.oracle/checkins/G0.md:2398:vibecomfy/comfy_nodes/agent/_frag_humanize.py:976:        if isinstance(change, Mapping) and int(change.get("landed_operation_count") or 0) > 0:
.oracle/checkins/G0.md:2417:vibecomfy/comfy_nodes/agent/edit_narrator.py:59:    def landed_operation_count(self) -> int:
.oracle/checkins/G0.md:2418:vibecomfy/comfy_nodes/agent/edit_narrator.py:62:            return int(change.get("landed_operation_count") or 0)
.oracle/checkins/G0.md:2429:vibecomfy/comfy_nodes/agent/edit_narrator.py:249:    "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
.oracle/checkins/G0.md:2430:vibecomfy/comfy_nodes/agent/edit_narrator.py:251:    "  - change.landed_operation_count: how many operations actually landed.\n"
.oracle/checkins/G0.md:2431:vibecomfy/comfy_nodes/agent/edit_narrator.py:252:    "  - validation.passed: whether post-edit validation passed.\n"
.oracle/checkins/G0.md:2432:vibecomfy/comfy_nodes/agent/edit_narrator.py:253:    "Never claim an edit you did not land: when graph_unchanged is true or "
.oracle/checkins/G0.md:2433:vibecomfy/comfy_nodes/agent/edit_narrator.py:254:    "landed_operation_count is 0, you MUST NOT say the graph was edited, "
.oracle/checkins/G0.md:2435:vibecomfy/comfy_nodes/agent/edit_narrator.py:256:    "when validation.passed is false. The message must be consistent with "
.oracle/checkins/G0.md:2436:vibecomfy/comfy_nodes/agent/edit_narrator.py:352:    (``change.graph_unchanged``, ``outcome.kind``,
.oracle/checkins/G0.md:2437:vibecomfy/comfy_nodes/agent/edit_narrator.py:353:    ``change.landed_operation_count``, ``validation.passed``) and requires the
.oracle/checkins/G0.md:2442:vibecomfy/comfy_nodes/agent/edit_humanize.py:580:        "landed_operation_count": _total_landed_edit_count(state),
.oracle/checkins/G0.md:2444:vibecomfy/comfy_nodes/agent/edit_humanize.py:604:        "changed (change.graph_changed / change.graph_unchanged), the outcome kind "
.oracle/checkins/G0.md:2445:vibecomfy/comfy_nodes/agent/edit_humanize.py:605:        "(outcome.kind), and how many operations landed (change.landed_operation_count). "
.oracle/checkins/G0.md:2446:vibecomfy/comfy_nodes/agent/edit_humanize.py:606:        "Never claim an edit you did not land: when graph_unchanged is true or "
.oracle/checkins/G0.md:2447:vibecomfy/comfy_nodes/agent/edit_humanize.py:607:        "landed_operation_count is 0, you MUST NOT say the graph was edited, applied, "
.oracle/checkins/G0.md:2449:vibecomfy/comfy_nodes/agent/edit_humanize.py:609:        "validation.passed is false. Describe exactly those facts."
.oracle/checkins/G0.md:2451:vibecomfy/comfy_nodes/agent/edit_humanize.py:626:                "(change.graph_unchanged), the outcome kind (outcome.kind), and the landed "
.oracle/checkins/G0.md:2452:vibecomfy/comfy_nodes/agent/edit_humanize.py:627:                "operation count (change.landed_operation_count).",
.oracle/checkins/G0.md:2454:vibecomfy/comfy_nodes/agent/edit_humanize.py:633:                "applied, or a connection was made when graph_unchanged is true or "
.oracle/checkins/G0.md:2455:vibecomfy/comfy_nodes/agent/edit_humanize.py:634:                "landed_operation_count is 0",
.oracle/checkins/G0.md:2456:vibecomfy/comfy_nodes/agent/edit_humanize.py:635:                "Claiming validation passed when validation.passed is false",
.oracle/checkins/G0.md:2459:vibecomfy/comfy_nodes/agent/edit_humanize.py:795:        "landed_operation_count": int(change_details.get("landed_operation_count") or 0),
.oracle/checkins/G0.md:2460:vibecomfy/comfy_nodes/agent/edit_humanize.py:849:    landed_operation_count = int(compact_change_details.get("landed_operation_count") or 0)
.oracle/checkins/G0.md:2461:vibecomfy/comfy_nodes/agent/edit_humanize.py:850:    graph_changed = bool(_batch_candidate_graph_changed(state) or landed_operation_count > 0)
.oracle/checkins/G0.md:2464:vibecomfy/comfy_nodes/agent/edit_humanize.py:871:            "graph_unchanged": not graph_changed,
.oracle/checkins/G0.md:2465:vibecomfy/comfy_nodes/agent/edit_humanize.py:872:            "landed_operation_count": landed_operation_count,
.oracle/checkins/G0.md:2467:vibecomfy/comfy_nodes/agent/edit_humanize.py:890:            "graph_unchanged": failure.graph_unchanged,
.oracle/checkins/G0.md:2468:vibecomfy/comfy_nodes/agent/edit_humanize.py:956:        if isinstance(change, Mapping) and int(change.get("landed_operation_count") or 0) > 0:
.oracle/checkins/G0.md:2483:tests/live_agentic_harness/assessor.py:75:    if response.get("graph_unchanged") is not False:
.oracle/checkins/G0.md:2502:tests/live_agentic_harness/assessor.py:578:            and response.get("graph_unchanged") is True
.oracle/checkins/G0.md:2507:tests/live_agentic_harness/assessor.py:622:            elif response.get("graph_unchanged") is True:
.oracle/checkins/G0.md:2509:tests/live_agentic_harness/assessor.py:627:                        "detail": "Expected graph change but response.graph_unchanged is True.",
.oracle/checkins/G0.md:2529:tests/live_agentic_harness/assessor.py:774:            if expect_graph_changed and not safe_refusal_accepted and "unchanged" in impl_message.lower():
.oracle/checkins/G0.md:2555:-    re.compile(r"\b(no (?:change|changes|edit|edits|updates?) needed|unchanged|left the graph unchanged|nothing needed changing)\b", re.I),
.oracle/checkins/G0.md:2617:-    graph_unchanged = response.get("graph_unchanged")
.oracle/checkins/G0.md:2623:-    landed_operation_count = (
.oracle/checkins/G0.md:2624:-        int(change_details.get("landed_operation_count") or 0)
.oracle/checkins/G0.md:2629:-    if graph_unchanged is True and claims_edit:
.oracle/checkins/G0.md:2630:-        contradictions.append("message claims edits even though response.graph_unchanged is True")
.oracle/checkins/G0.md:2631:-    if graph_unchanged is False and landed_operation_count > 0 and claims_no_edit:
.oracle/checkins/G0.md:2656:-    if landed_operation_count == 0 and claims_edit:
.oracle/checkins/G0.md:2657:-        contradictions.append("message claims landed edits even though landed_operation_count=0")
.oracle/checkins/G0.md:2658:-    if landed_operation_count > 0 and claims_no_edit:
.oracle/checkins/G0.md:2660:-            "message claims no change even though landed_operation_count is positive"
.oracle/checkins/G0.md:2663:-        if int(match.group(1)) != landed_operation_count:
.oracle/checkins/G0.md:3036:/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '600,790p'; git show fa06a300:tests/live_agentic_harness/assessor.py | nl -ba | sed -n '690,900p'; rg -n \"landed_operation_count\" tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/live_agentic_harness/assessor.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy
.oracle/checkins/G0.md:3060:   622	            elif response.get("graph_unchanged") is True:
.oracle/checkins/G0.md:3065:   627	                        "detail": "Expected graph change but response.graph_unchanged is True.",
.oracle/checkins/G0.md:3212:   774	            if expect_graph_changed and not safe_refusal_accepted and "unchanged" in impl_message.lower():
.oracle/checkins/G0.md:3217:   779	                        "detail": f"implementation_result reports unchanged: {impl_message}",
.oracle/checkins/G0.md:3240:   701	            and response.get("graph_unchanged") is True
.oracle/checkins/G0.md:3284:   745	            elif response.get("graph_unchanged") is True:
.oracle/checkins/G0.md:3289:   750	                        "detail": "Expected graph change but response.graph_unchanged is True.",
.oracle/checkins/G0.md:3439:   900	            if expect_graph_changed and not safe_refusal_accepted and "unchanged" in impl_message.lower():
.oracle/checkins/G0.md:3440:tests/test_live_agentic_assessor_score_honesty.py:168:        "change_details": {"landed_operation_count": 1},
.oracle/checkins/G0.md:3441:tests/test_live_agentic_assessor_score_honesty.py:211:        "change_details": {"landed_operation_count": 0},
.oracle/checkins/G0.md:3442:tests/test_live_agentic_harness_guard_contract.py:528:            "change_details": {"landed_operation_count": 1},
.oracle/checkins/G0.md:3443:tests/test_live_agentic_harness_guard_contract.py:542:            "change_details": {"landed_operation_count": 1},
.oracle/checkins/G0.md:3444:tests/test_live_agentic_harness_guard_contract.py:557:            "change_details": {"landed_operation_count": 1},
.oracle/checkins/G0.md:3445:tests/test_live_agentic_harness_guard_contract.py:571:            "change_details": {"landed_operation_count": 1},
.oracle/checkins/G0.md:3446:tests/test_live_agentic_harness_guard_contract.py:585:            "change_details": {"landed_operation_count": 2},
.oracle/checkins/G0.md:3447:tests/test_live_agentic_harness_guard_contract.py:601:            "change_details": {"landed_operation_count": 0},
.oracle/checkins/G0.md:3448:tests/test_live_agentic_harness_guard_contract.py:616:            "change_details": {"landed_operation_count": 0},
.oracle/checkins/G0.md:3449:tests/test_live_agentic_harness_guard_contract.py:632:            "change_details": {"landed_operation_count": 0},
.oracle/checkins/G0.md:3450:tests/test_live_agentic_harness_guard_contract.py:647:            "change_details": {"landed_operation_count": 0},
.oracle/checkins/G0.md:3451:tests/test_live_agentic_harness_guard_contract.py:707:                "change_details": {"landed_operation_count": 0},
.oracle/checkins/G0.md:3452:tests/test_live_agentic_harness_guard_contract.py:747:                "change_details": {"landed_operation_count": 1},
.oracle/checkins/G0.md:3455:The audit is now definitively trending FAIL on implementation, independent of the measurement mismatch: I found a residual free-form prose gate in the assessor (`implementation_result.message` containing “unchanged”), the classify-failure path still serializes a fake `respond_only` plan, and a newly edited provider exception handler references an unbound `exc`. I’m completing the requested verification runs and checking exact rework boundaries so the issue list is actionable rather than merely diagnostic.
.oracle/checkins/G0.md:3485:   264	    "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
.oracle/checkins/G0.md:3487:   266	    "  - change.landed_operation_count: how many operations actually landed.\n"
.oracle/checkins/G0.md:3488:   267	    "  - validation.passed: whether post-edit validation passed.\n"
.oracle/checkins/G0.md:3489:   268	    "Never claim an edit you did not land: when graph_unchanged is true or "
.oracle/checkins/G0.md:3490:   269	    "landed_operation_count is 0, you MUST NOT say the graph was edited, "
.oracle/checkins/G0.md:3492:   271	    "when validation.passed is false. The message must be consistent with "
.oracle/checkins/G0.md:3625:   249	    "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
.oracle/checkins/G0.md:3627:   251	    "  - change.landed_operation_count: how many operations actually landed.\n"
.oracle/checkins/G0.md:3628:   252	    "  - validation.passed: whether post-edit validation passed.\n"
.oracle/checkins/G0.md:3629:   253	    "Never claim an edit you did not land: when graph_unchanged is true or "
.oracle/checkins/G0.md:3630:   254	    "landed_operation_count is 0, you MUST NOT say the graph was edited, "
.oracle/checkins/G0.md:3632:   256	    "when validation.passed is false. The message must be consistent with "
.oracle/checkins/G0.md:3895:    36	- Production code unchanged in this task.
.oracle/checkins/G0.md:3900:    41	- End state (three clauses): (a) the agent ALWAYS writes the message — no deterministic substitute ever ships (producer-side discard-and-replace removed); (b) the message is written FROM the facts — the synthesis prompt feeds the agent the structured outcome (`graph_unchanged`, `outcome.kind`, `landed_operation_count`, validation details) and requires the narrative to describe exactly those facts; (c) scoring is structured-only — prose never gates a scenario.
.oracle/checkins/G0.md:10380:   The named `_MESSAGE_*`, `_NARRATIVE_*`, `message_artifact`, and narrative-validator gates are gone from executable code. But [assessor.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/live_agentic_harness/assessor.py:771) still fails a scenario solely because free-form `implementation_result.message` contains `"unchanged"`. A valid edit saying “Updated the sampler; all other nodes are unchanged” therefore fails.
.oracle/checkins/G0.md:10383:   Graph state, outcome, gates, and effective-target checks remain active at [assessor.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/live_agentic_harness/assessor.py:613). However, `landed_operation_count` is no longer read by the assessor despite the claim at line 745. A candidate with `graph_unchanged=false`, passing gates, and zero landed operations passes. The four controls do not cover this inconsistency.
.oracle/checkins/G0.md:10410:- [assessor.py:771](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/live_agentic_harness/assessor.py:771): remove/demote the residual `"unchanged"` prose matcher; add an `implementation_result.message` counterexample.
.oracle/checkins/G0.md:10413:- [_frag_narrator.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/vibecomfy/comfy_nodes/agent/_frag_narrator.py:253): resolve the prompt contradiction between forbidding mention of validation and requiring `validation.passed` to be described.
.oracle/checkins/G0.md:10427:   The named `_MESSAGE_*`, `_NARRATIVE_*`, `message_artifact`, and narrative-validator gates are gone from executable code. But [assessor.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/live_agentic_harness/assessor.py:771) still fails a scenario solely because free-form `implementation_result.message` contains `"unchanged"`. A valid edit saying “Updated the sampler; all other nodes are unchanged” therefore fails.
.oracle/checkins/G0.md:10430:   Graph state, outcome, gates, and effective-target checks remain active at [assessor.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/live_agentic_harness/assessor.py:613). However, `landed_operation_count` is no longer read by the assessor despite the claim at line 745. A candidate with `graph_unchanged=false`, passing gates, and zero landed operations passes. The four controls do not cover this inconsistency.
.oracle/checkins/G0.md:10457:- [assessor.py:771](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/tests/live_agentic_harness/assessor.py:771): remove/demote the residual `"unchanged"` prose matcher; add an `implementation_result.message` counterexample.
.oracle/checkins/G0.md:10460:- [_frag_narrator.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy/vibecomfy/comfy_nodes/agent/_frag_narrator.py:253): resolve the prompt contradiction between forbidding mention of validation and requiring `validation.passed` to be described.

exec
/bin/zsh -lc "sed -n '1,95p' .oracle/tasklist.md
sed -n '1,140p' .oracle/briefs/batch-G0R.md
sed -n '1,120p' .oracle/briefs/batch-G0R-rework.md
git diff --unified=80 a890884f..16d80bbe -- .gitignore" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
# 1. Tasklist for the remaining project

## Scope decisions

- B02 and elegance P0–P10 remain closed through `0f515870`.
- The checkout contains exactly **100** scenario JSON files, not 150. The exploration finding claiming 150 is rejected by direct inventory.
- The apparent no-change population is **40**:
  - 35 semantic research/explain/diagnose scenarios;
  - 2 explicit health controls: `live-graph-explanation-smoke` and `speed-distillation-research`;
  - 3 mislabeled edits with `apply:true`, a `desired` rubric, and `expect_graph_changed:false`.
- Add no separate answer-quality batch. D13 authors the rubrics; B06 implements one tri-state semantic-answer judge.
- Replace the speculative B08 decision gate with the now-justified deterministic C8/C9 endpoint-integrity batch.
- Keep cut:
  - semantic repair turns and fingerprints;
  - generic prompt cleanup/compression;
  - all-Flash profiles;
  - the 400-run matrix;
  - speculative interrupted-run resume.
- Expand B01’s single provenance contract to successful and failed calls. B07 consumes it rather than creating a second evidence system.
- Historical `out/agentic/` and `external_workflows/` are absent. Deterministic fixes may proceed, but scenario-level recovery, baseline, or stochasticity claims require those artifacts.
- Each batch ends in a binary read-only oracle checkpoint. Rework the owning batch until `PASS`.

---

## G0R — Truthful scorer/narrator and formal re-verdict

### Tasks

1. Remove the remaining `"unchanged"` implementation-message substring gate.
2. Restore the structural expected-edit guard:
   - `graph_unchanged=false` requires a positive integer `landed_operation_count`;
   - missing, malformed, or zero fails closed;
   - non-edits and accepted grounded refusals are exempt.
3. Ensure narrator artifact-write failures cannot replace an already-selected narrator response.
4. Remove the narrator prompt contradiction around `validation.passed`.
5. Preserve regressions for:
   - provider-exception evidence;
   - nullable failed classification;
   - no invented route, task, or intent.
6. If authoritative prior artifacts are restored, deterministically rescore them and produce the residual class inventory without new model calls. Otherwise record historical re-binning as unavailable; do not infer it from documentation.

### Acceptance

- No substring matcher, narrator phrasing, or implementation message gates scoring.
- Prose affects semantic quality only through B06’s explicit rubric-driven judge.
- Zero/missing landed-operation fixtures fail structurally.
- Narrator artifact-write failure preserves the selected response.
- The nine former matcher cases have zero matcher failures, though independent structured failures may remain.
- Focused G0 tests pass.

### Oracle checkpoint

Review scorer/narrator changes and focused fixtures. Record `PASS` as the formal G0 verdict, plus either a reconciled historical rescore or an explicit “source artifacts unavailable” statement.

---

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
# MEGADO BATCH G0R — Truthful scorer/narrator and formal re-verdict

Repo (worktree): /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python` (symlinked to main's venv). You have file/web/terminal tools. Skip formatters, linters, and project-wide test suites; run only the focused tests below.

## Context

The G0 quick-win gate landed on main (`5daad9e6`), but its oracle checkpoint FAILED with 7 issues. Issues 5–7 were genuinely fixed (`ec732251`, `b85e173f`). Issues 1–4 were claimed fixed in `bfcde5a9` but that commit contained ZERO code changes — they remain live:

1. `tests/live_agentic_harness/assessor.py:774` — residual `"unchanged"` implementation-message substring gate (error severity) still gates scoring.
2. Missing structural expected-edit guard: `graph_unchanged=false` with zero/missing `landed_operation_count` passes.
3. `vibecomfy/comfy_nodes/agent/_frag_narrator.py` — artifact-write failure inside the outer fallback catch can replace an already-selected narrator message.
4. `_frag_narrator.py:245` region — narrator prompt contradiction: it forbids mentioning validation while requiring `validation.passed` to be described.

## Tasks

1. **Remove the residual `"unchanged"` prose gate** in `tests/live_agentic_harness/assessor.py` (around `:774`): delete the substring failure over `implementation_result.message`. Add a counterexample fixture: an edit message like "Updated the sampler; other nodes are unchanged" must NOT affect scoring.

2. **Restore the structural expected-edit guard** (around `assessor.py:613`): for an expected successful edit, `graph_unchanged=false` must be accompanied by a positive integer `change_details.landed_operation_count`. Missing, malformed, or zero counts fail closed. Grounded-refusal and explicitly non-edit routes are exempt. Add a negative control fixture.

3. **Preserve the selected narrator message if artifact persistence fails**: in `vibecomfy/comfy_nodes/agent/_frag_narrator.py`, ensure the already-selected agent message still ships even when `_write_narrative_artifacts` itself raises (the call is currently inside the outer fallback catch around `:457–477`). Add a regression that forces the write to raise and proves the selected message is preserved. Refactor only as much as the regression requires.

4. **Remove the narrator prompt contradiction** around `_frag_narrator.py:245`: the prompt must not simultaneously forbid mentioning validation and require describing `validation.passed`. Make the instruction consistent (describe validation outcome truthfully).

5. **Preserve regressions for** (these already exist from G0-T4/issues 5–6 rework; verify they still pass, fix only if broken):
   - provider-exception evidence (`test_agent_edit_*` or executor tests for `ProviderError` evidence);
   - nullable failed classification (no invented route/task/intent after classify failure);
   - no invented `respond_only`.

6. **Historical rescore**: check whether `out/agentic/` artifacts exist in this worktree (they do NOT — gitignored/absent). If absent, record "historical re-binning unavailable; source artifacts absent" in the batch report. Do NOT infer re-binning from documentation.

## Verification (run these, retain output)

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py -x
```

Add your new fixtures to the guard-contract / score-honesty files so the above slice covers them. Also run:

```bash
.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_backend_spine.py -k 'narrative or message' tests/test_live_agentic_assessor_score_honesty.py tests/test_live_agentic_harness_guard_contract.py
```

Expected: focused G0 tests pass; the nine former matcher counterexample cases have zero matcher failures.

## Acceptance (from tasklist)

- No substring matcher, narrator phrasing, or implementation message gates scoring.
- Prose affects semantic quality only through B06's explicit rubric-driven judge (not this batch).
- Zero/missing landed-operation fixtures fail structurally.
- Narrator artifact-write failure preserves the selected response.
- The nine former matcher cases have zero matcher failures, though independent structured failures may remain.
- Focused G0 tests pass.

## Report

Return: what you changed (files + line refs), the fixture names you added, the pytest output (pass counts), and the historical-artifacts verdict (present or "unavailable"). Do NOT commit — the orchestrator commits after you finish.
# MEGADO G0R REWORK (oracle issues) — landed-count guard fail-open

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run only the focused tests.

## The oracle issue (G0R checkpoint FAIL, finding 2)

The landed-count guard is sound at the core check (`assessor.py:670` reads `change_details.landed_operation_count`, requires int > 0, rejects missing/zero/negative/string/float/bool), but the exemption helper **`_explicitly_non_edit_route` at `tests/live_agentic_harness/assessor.py:214` fails open**: it never reads `response.route`; it trusts self-declared `outcome.kind` and `no_candidate_reason`. Demonstrated fail-open cases:

- `route="revise"`, `graph_unchanged=false`, `outcome.kind="clarify"`, no count → passes with zero errors.
- `graph_unchanged=false`, `no_candidate_reason="route_not_applyable"`, no count → passes with zero errors.
- Conversely, `route="respond"` with `outcome.kind="candidate"` is NOT recognized as a non-edit route.

Also: `tests/test_live_agentic_harness_guard_contract.py:995` currently LOCKS IN the first fail-open case (accepts `graph_unchanged=false` + `outcome.kind=clarify`) — that test must be replaced with negative controls.

## What to change

1. **Make `_explicitly_non_edit_route` (or the guard path around it) use the canonical route**, not self-declared outcome/reason:
   - Read the actual `response.route` (find how route is carried in the assessor response envelope — check `implementation_result`, `response`/`turn`/`classification` fields; grep for `"route"` in assessor.py and the harness artifacts to find the authoritative field).
   - A non-edit route claiming `graph_unchanged=false` must fail a separate route/graph consistency check (edit-route self-relabeling cannot bypass all structured checks).
   - Accepted grounded refusals remain configuration-authorized (`allow_safe_refusal`) and structurally unchanged — those are legitimately exempt.
   - Known canonical non-edit routes (e.g. `respond`, `clarify`, `research`-only, `explain`-only) are exempt ONLY when the response actually took that route AND the graph is unchanged or the refusal is authorized. An edit-route envelope (`revise`/`apply`) with `graph_unchanged=false` and no positive landed count must fail closed even if it self-labels `outcome.kind=clarify` or `no_candidate_reason=route_not_applyable`.

2. **Replace the fail-open test at `test_live_agentic_harness_guard_contract.py:995`** with negative controls proving:
   - edit-route self-relabeling (`route=revise` + `outcome.kind=clarify` + `graph_unchanged=false`, no count) → FAILS;
   - `no_candidate_reason="route_not_applyable"` with `graph_unchanged=false`, no count → FAILS;
   - failure outcomes cannot bypass all structured checks;
   - and keep a positive control: a genuine non-edit route with unchanged graph still exempt.

3. **Preserve** the existing positive controls (missing/zero/negative/string/float/bool landed counts fail; grounded-refusal with `allow_safe_refusal` exempt; explicit non-edit routes exempt when truthful).

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py -x
```

Add your new negative controls to the guard-contract file so the slice covers them. Expected: all G0R fixtures pass including the new fail-closed negative controls.

## Report

Return: exact changes (files + line refs, especially how you read the canonical route), the fixture names added/replaced, and the pytest output. Do NOT commit.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/.gitignore b/.gitignore
index b4013a6e..c3dd200c 100644
--- a/.gitignore
+++ b/.gitignore
@@ -1,77 +1,78 @@
 .venv/
 __pycache__/
 .pytest_cache/
 .ruff_cache/
 .import_linter_cache/
 .DS_Store
 *.pyc
 
 # Generated indexes and runtime artifacts
 .coverage
 coverage.xml
 workflow_index.json
 external_workflow_index.json
 node_index.json
 out/
 /output/
 temp/
 /input/
 /input/.DS_Store
 
 # Large local runtime/vendor checkouts
 /recipes/
 /vendor/ComfyUI/
 /vendor/workflow_templates/
 /vendor/external_workflows/
 /external_workflows/
 /custom_nodes/
 /user/
 
 # Tool working directories
 .agents/
 .claude/
 .desloppify/
 .megaplan/*
 !.megaplan/briefs/
 .megaplan/briefs/*
 !.megaplan/briefs/pristine-agent-architecture/
 .megaplan/briefs/pristine-agent-architecture/*
 !.megaplan/briefs/pristine-agent-architecture/**
 !.megaplan/briefs/messaging-boundary-cleanup.md
 docs/megaplan_chains/**/.megaplan/
 *.patch
 
 # Agent task briefs and prompts — historical scratchpads, not project docs
 docs/megaplan_briefs/
 docs/subagent_prompts/
 docs/megaplan_chains/node_resolution_epic/evidence/object_info_*.json
 docs/local_agent_text_to_graph_e2e.md
 .env
 this.env
 _debug_*.py
 _fix_t6.py
 _regen_templates.py
 finalize.json
 install.log
 .hypothesis/
 .tmp/
 node_modules/
 *.pid
 *.zip
 comfyui_*.png
 comfyui_screenshot*.png
 comfyui_panel_open*.png
 agent_edit_e2e.mjs
 local_env.sh
 
 # e2e test tier — isolated dependency management
 tests/e2e/node_modules/
 tests/e2e/playwright-report/
 tests/e2e/test-results/
 test-results/
 
 # Generated cache-busted web assets
 vibecomfy/comfy_nodes/web_dist/
 
 # Live agentic watchdog run artifacts (logs, backups, baselines, codex outputs)
 .watchdog-runs/
+.venv

exec
/bin/zsh -lc 'git diff --unified=40 a890884f..16d80bbe -- tests/live_agentic_harness/assessor.py
git diff --unified=40 a890884f..16d80bbe -- vibecomfy/comfy_nodes/agent/_frag_narrator.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/assessor.py b/tests/live_agentic_harness/assessor.py
index 251718eb..42388790 100644
--- a/tests/live_agentic_harness/assessor.py
+++ b/tests/live_agentic_harness/assessor.py
@@ -1,86 +1,99 @@
 """Deep assessment of live agentic run artifacts.
 
 The live agentic harness already verifies flow metadata (real dispatcher,
 agentic model behavior, status == success).  This module inspects the actual
 run artifacts to catch failures that metadata alone cannot:
 
 * response.ok == false or response.error set
 * readiness blockers
 * graph unchanged when an edit was expected
 * hard diagnostics (severity == error) from agent-edit turns
 * upstream dependency failures such as Hivemind HTTP 500
-* implementation_result.json reporting the graph is unchanged
+* implementation_result.ok == false
 * validation gates that failed for an apply/edit route
 * (when enabled) an LLM intent judge that scores the edit against the query
 
 The deterministic checks run first; the LLM judge is called afterward for
 scenarios that expect a graph change.
 """
 
 from __future__ import annotations
 
 import json
 import re
 from pathlib import Path
 from typing import Any, Mapping
 
 from vibecomfy.executor.graph_facts import GraphFieldTarget, compare_effective_field
 
 from .intent_judge import judge_edit_intent
 
 _ERROR_SEVERITIES = {"error", "fatal"}
 
 # Critical upstream failures that should always fail a live run.
 _UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
     re.compile(r"Hivemind HTTP error.*500", re.IGNORECASE),
     re.compile(r"HTTP Error 500", re.IGNORECASE),
     re.compile(r"Internal Server Error", re.IGNORECASE),
 ]
 
 # Soft capacity warnings: surfaced so humans see them, but not treated as hard
 # failures on their own (the run may still succeed via fallback evidence).
 _SOFT_WARNING_PATTERNS: list[re.Pattern[str]] = [
     re.compile(r"HTTP Error 429", re.IGNORECASE),
     re.compile(r"Too Many Requests", re.IGNORECASE),
 ]
 
+# Canonical public route vocabulary (mirrors vibecomfy.executor.contracts).
+# Edit routes may land graph changes; non-edit routes never do.  Exemption
+# from the landed-count guard is decided from the envelope's canonical route,
+# never from the agent's self-declared outcome/reason labels.
+_EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise"})
+_NON_EDIT_ROUTES = frozenset({
+    "clarify",
+    "respond",
+    "inspect",
+    "research",
+    "requires_custom_nodes",
+})
+
 
 def _load_json(path: Path) -> dict[str, Any] | None:
     """Load a JSON artifact if it exists and is valid."""
     if not path.is_file():
         return None
     try:
         return json.loads(path.read_text(encoding="utf-8"))
     except (OSError, json.JSONDecodeError):
         return None
 
 
 def _walk(obj: Any) -> Any:
     """Recursively yield every dict/string node in a JSON-like structure."""
     if isinstance(obj, dict):
         yield obj
         for value in obj.values():
             yield from _walk(value)
     elif isinstance(obj, list):
         for item in obj:
             yield from _walk(item)
     else:
         yield obj
 
 
 def _has_successful_candidate(response: Mapping[str, Any]) -> bool:
     """Return true when the response produced an applied candidate graph."""
     if response.get("ok") is not True:
         return False
     if response.get("graph_unchanged") is not False:
         return False
     return isinstance(response.get("candidate_graph"), Mapping) or isinstance(
         response.get("candidate"), Mapping
     )
 
 
 def _queue_validate_skipped_for_successful_candidate(response: Mapping[str, Any]) -> bool:
     """Return true when queue validation is absent, not failed.
 
     ``queue_validate_ok`` is fail-closed in the agent-edit gate map.  Some live
     batch paths can return a real changed candidate without running the queue
@@ -174,80 +187,132 @@ def _collect_hard_diagnostics(response: Mapping[str, Any]) -> list[str]:
     """Return messages from any object with severity error/fatal."""
     issues: list[str] = []
     skip_failed_batch_turns = _has_successful_candidate(response)
     for node in _walk_hard_diagnostic_scope(
         response,
         skip_failed_batch_turns=skip_failed_batch_turns,
     ):
         if not isinstance(node, dict):
             continue
         if node.get("severity") not in _ERROR_SEVERITIES:
             continue
         message = node.get("message")
         if not isinstance(message, str):
             detail = node.get("detail")
             message = json.dumps(detail, sort_keys=True) if isinstance(detail, dict) else str(node)
         message = message.strip()
         if message and message not in issues:
             issues.append(message)
     return issues
 
 
 def _collect_pattern_matches(
     response: Mapping[str, Any],
     patterns: list[re.Pattern[str]],
 ) -> list[str]:
     """Return distinct string values matching any of the supplied patterns."""
     issues: list[str] = []
     seen: set[str] = set()
     for node in _walk(response):
         if not isinstance(node, str):
             continue
         for pattern in patterns:
             if pattern.search(node):
                 if node not in seen:
                     seen.add(node)
                     issues.append(node)
                 break
     return issues
 
 
+def _canonical_route(response: Mapping[str, Any]) -> str:
+    """Return the canonical public route carried by the response envelope.
+
+    The authoritative field is the top-level ``route`` (written by
+    ``AgentTurnResult.to_dict`` in vibecomfy.executor.contracts); the same
+    public route is mirrored in ``evidence.classification.route`` and
+    ``report.executor.plan.route``.  Missing/non-string routes resolve to
+    the empty string so an envelope without a route can never claim a
+    non-edit exemption (fail closed).
+    """
+    route = response.get("route")
+    if isinstance(route, str):
+        return route
+    evidence = response.get("evidence")
+    if isinstance(evidence, Mapping):
+        classification = evidence.get("classification")
+        if isinstance(classification, Mapping) and isinstance(classification.get("route"), str):
+            return classification["route"]
+    report = response.get("report")
+    if isinstance(report, Mapping):
+        executor = report.get("executor")
+        if isinstance(executor, Mapping):
+            plan = executor.get("plan")
+            if isinstance(plan, Mapping) and isinstance(plan.get("route"), str):
+                return plan["route"]
+    return ""
+
+
+def _explicitly_non_edit_route(response: Mapping[str, Any]) -> bool:
+    """Return True when the envelope's canonical route is a non-edit route.
+
+    The route is read from the envelope (``response.route``) — never from the
+    agent's self-declared ``no_candidate_reason`` / ``outcome.kind``.  An
+    edit-route envelope self-labeling ``outcome.kind=clarify`` or
+    ``no_candidate_reason=route_not_applyable`` is NOT exempt: a claimed edit
+    (graph_unchanged=false) must still be backed by a positive landed count.
+    These routes are scored by their own structured checks
+    (``no_candidate_reason`` / ``outcome_kind``) and by the route/graph
+    consistency check; demanding a positive landed operation count for them
+    would be wrong — a truthful non-edit route has no operations to count.
+    """
+    return _canonical_route(response) in _NON_EDIT_ROUTES
+
+
+def _landed_operation_count(response: Mapping[str, Any]) -> Any:
+    """Return ``change_details.landed_operation_count`` (any JSON value)."""
+    change_details = response.get("change_details")
+    if isinstance(change_details, Mapping):
+        return change_details.get("landed_operation_count")
+    return None
+
+
 def _expects_graph_changed(
     scenario: Mapping[str, Any] | None,
     response: Mapping[str, Any] | None,
 ) -> bool:
     """Decide whether this scenario should have produced a graph change.
 
     Explicit scenario configuration wins, then we fall back to reading the
     agent's own classification/plan from the response.
     """
     if scenario is not None:
         assessment = scenario.get("assessment")
         if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
             return bool(assessment["expect_graph_changed"])
 
     if response is None:
         return False
 
     plan = response.get("report", {}).get("executor", {}).get("plan") or {}
     if plan.get("implement") is True and plan.get("route") in {"adapt", "revise"}:
         return True
 
     return False
 
 
 def _expected_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
     """Return explicitly accepted public outcome kinds for this scenario."""
     if scenario is None:
         return set()
     assessment = scenario.get("assessment")
     if not isinstance(assessment, Mapping):
         return set()
     raw = assessment.get("expected_outcome_kinds")
     if raw is None:
         raw = assessment.get("expected_outcome_kind")
     if isinstance(raw, str):
         return {raw}
     if isinstance(raw, list):
         return {item for item in raw if isinstance(item, str)}
     return set()
 
@@ -591,80 +656,132 @@ def assess_live_output_dir(
             )
         elif response.get("error"):
             issues.append(
                 {
                     "check": "response_error_field",
                     "severity": "error",
                     "detail": f"response.error set: {response['error']}",
                 }
             )
 
         # Readiness is also captured in flow_metadata, but surface it here if
         # the response carries it (e.g. blocked-prerequisite runs).
         readiness = response.get("readiness") or {}
         if readiness.get("ready") is False:
             issues.append(
                 {
                     "check": "response_readiness",
                     "severity": "error",
                     "detail": f"Readiness not ready: {readiness.get('reason')}",
                 }
             )
 
         if expect_graph_changed:
             if safe_refusal_accepted:
                 issues.append(
                     {
                         "check": "safe_refusal",
                         "severity": "info",
                         "detail": f"Accepted safe refusal outcome.kind={outcome_kind!r}.",
                     }
                 )
             elif response.get("graph_unchanged") is True:
                 issues.append(
                     {
                         "check": "graph_changed",
                         "severity": "error",
                         "detail": "Expected graph change but response.graph_unchanged is True.",
                     }
                 )
 
+            # G0R structural expected-edit guard: a claimed edit
+            # (graph_unchanged is False) must be backed by a positive integer
+            # change_details.landed_operation_count.  Missing, malformed, or
+            # zero counts fail closed.  Accepted grounded refusals
+            # (safe_refusal_accepted) and canonical non-edit routes are
+            # exempt — they are scored by their own structured checks.
+            route = _canonical_route(response)
+            if (
+                not safe_refusal_accepted
+                and response.get("graph_unchanged") is False
+                and not _explicitly_non_edit_route(response)
+            ):
+                landed_count = _landed_operation_count(response)
+                if not (
+                    isinstance(landed_count, int)
+                    and not isinstance(landed_count, bool)
+                    and landed_count > 0
+                ):
+                    issues.append(
+                        {
+                            "check": "landed_operation_count",
+                            "severity": "error",
+                            "detail": (
+                                "Expected edit but change_details.landed_operation_count "
+                                f"is {landed_count!r}; a positive integer is required "
+                                "when graph_unchanged is false."
+                            ),
+                        }
+                    )
+
+            # G0R route/graph consistency: a canonical non-edit route must
+            # never claim graph_unchanged=false.  Non-edit routes are exempt
+            # from the landed-count guard only when the graph really is
+            # unchanged (or the refusal is authorized above); an edit-route
+            # envelope self-relabeled as clarify/respond/failure cannot
+            # bypass the structural checks by relabeling alone.
+            if (
+                not safe_refusal_accepted
+                and response.get("graph_unchanged") is False
+                and route in _NON_EDIT_ROUTES
+            ):
+                issues.append(
+                    {
+                        "check": "route_graph_consistency",
+                        "severity": "error",
+                        "detail": (
+                            f"Non-edit route {route!r} claimed graph_unchanged=false; "
+                            "a non-edit route cannot change the graph."
+                        ),
+                    }
+                )
+
             no_reason = response.get("no_candidate_reason")
             if not safe_refusal_accepted and no_reason in {"no_changes", "no_candidate"}:
                 issues.append(
                     {
                         "check": "no_candidate_reason",
                         "severity": "error",
                         "detail": f"Expected edit but no_candidate_reason={no_reason!r}.",
                     }
                 )
 
             if not safe_refusal_accepted and outcome_kind in {"noop", "requires_custom_nodes"}:
                 issues.append(
                     {
                         "check": "outcome_kind",
                         "severity": "error",
                         "detail": f"Expected edit but outcome.kind={outcome_kind!r}.",
                     }
                 )
 
             gates = response.get("gates") or {}
             false_gates = [name for name, value in gates.items() if value is False]
             queue_validate_skipped = _queue_validate_skipped_for_successful_candidate(response)
             if queue_validate_skipped and "queue_validate_ok" in false_gates:
                 false_gates = [name for name in false_gates if name != "queue_validate_ok"]
                 issues.append(
                     {
                         "check": "queue_validate_skipped",
                         "severity": "warning",
                         "detail": (
                             "queue_validate_ok was false, but the response contains a changed "
                             "candidate and no queue_validate stage ran; treating this as missing "
                             "queue evidence rather than a concrete queue blocker."
                         ),
                     }
                 )
             if false_gates and not safe_refusal_accepted:
                 issues.append(
                     {
                         "check": "gates",
                         "severity": "error",
@@ -732,81 +849,77 @@ def assess_live_output_dir(
         # Any hard diagnostic anywhere in the response envelope.
         for msg in _collect_hard_diagnostics(response):
             issues.append(
                 {
                     "check": "hard_diagnostic",
                     "severity": "error",
                     "detail": msg,
                 }
             )
 
         # G0-T2: the deterministic message-artifact prose matcher is removed.
         # Scoring is structured-only — prose never gates a scenario. The
         # agent's message always ships as written; the structured
         # cross-checks (graph_changed, outcome_kind, gates, landed counts,
         # effective edits) above remain fully authoritative.
 
         # Critical upstream failures (Hivemind 500, etc.). When a successful
         # candidate exists, a recovered research-side upstream error should stay
         # visible but not invalidate an otherwise valid edit.
         upstream_severity = "warning" if _has_successful_candidate(response) else "error"
         for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
             issues.append(
                 {
                     "check": "upstream_failure",
                     "severity": upstream_severity,
                     "detail": msg,
                 }
             )
 
         # Capacity/soft warnings: surfaced, but not counted as errors.
         for msg in _collect_pattern_matches(response, _SOFT_WARNING_PATTERNS):
             issues.append(
                 {
                     "check": "soft_warning",
                     "severity": "warning",
                     "detail": msg,
                 }
             )
 
     if impl_result is not None:
-        impl_message = impl_result.get("message", "")
-        if isinstance(impl_message, str):
-            if expect_graph_changed and not safe_refusal_accepted and "unchanged" in impl_message.lower():
-                issues.append(
-                    {
-                        "check": "implementation_result",
-                        "severity": "error",
-                        "detail": f"implementation_result reports unchanged: {impl_message}",
-                    }
-                )
+        # G0R: the residual "unchanged" substring gate over the
+        # implementation_result message is removed — prose never gates
+        # scoring.  Only the structured ok flag is authoritative.
         if impl_result.get("ok") is False:
             issues.append(
                 {
                     "check": "implementation_result_ok",
                     "severity": "error",
-                    "detail": f"implementation_result.ok is False: {impl_result.get('error') or impl_message}",
+                    "detail": (
+                        "implementation_result.ok is False: "
+                        f"{impl_result.get('error') or impl_result.get('message', '')}"
+                    ),
                 }
             )
 
     issues.extend(_assess_model_request_artifact(output_dir, scenario))
 
     # Deduplicate while preserving order.
     seen: set[tuple[str, str, str]] = set()
     deduped: list[dict[str, Any]] = []
     for issue in issues:
         key = (issue["check"], issue["severity"], issue["detail"])
         if key in seen:
             continue
         seen.add(key)
         deduped.append(issue)
 
     errors = [issue for issue in deduped if issue["severity"] == "error"]
     return {
         "passed": len(errors) == 0,
         "expect_graph_changed": expect_graph_changed,
         "expected_outcome_kinds": sorted(expected_outcome_kinds),
         "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
         "issue_count": len(deduped),
         "error_count": len(errors),
         "issues": deduped,
     }
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/comfy_nodes/agent/_frag_narrator.py b/vibecomfy/comfy_nodes/agent/_frag_narrator.py
index 45e2d9e4..0f796a25 100644
--- a/vibecomfy/comfy_nodes/agent/_frag_narrator.py
+++ b/vibecomfy/comfy_nodes/agent/_frag_narrator.py
@@ -213,82 +213,83 @@ def _write_narrative_artifacts(
     try:
         turn_dir.mkdir(parents=True, exist_ok=True)
     except OSError:
         pass
 
     def _safe_write(rel_path: str, data: Any) -> None:
         try:
             target = turn_dir / rel_path
             target.write_text(
                 json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
                 encoding="utf-8",
             )
         except (OSError, ValueError, TypeError) as exc:
             LOGGER.warning(
                 "Narrative artifact %s write failed for turn %s (best-effort): %s",
                 rel_path,
                 getattr(state, "turn_dir", None),
                 exc,
             )
 
     _safe_write("narrative_context.json", narrative_context.payload)
     _safe_write("narrative_validation.json", validation)
 
     if request_messages is not None:
         _safe_write("narrator_request.json", request_messages)
 
     if llm_response is not None:
         _safe_write("narrator_response.json", llm_response)
 
 
 # ── Prompt construction helpers ───────────────────────────────────────────
 
 _NARRATOR_SYSTEM_PROMPT = (
     "You are a concise, honest narrative synthesizer for a visual programming "
     "agent. The agent just completed a graph-editing turn. Your job is to "
     "produce a single user-facing sentence that accurately describes what "
     "happened.\n\n"
     "Rules:\n"
     "- Respond with exactly one JSON object: {\"message\": \"...\"}\n"
     "- The message must be one natural-language sentence ending in punctuation.\n"
-    "- Never mention internal agent machinery (gates, validation, scoring, "
-    "batch REPL, field changes). Use the user-facing narrative context only.\n"
+    "- Never mention internal agent machinery (gate names, scoring, batch REPL, "
+    "field-level diffs). Describe the validation outcome truthfully — "
+    "validation.passed below is user-facing and must be reported as-is.\n"
     "- If the outcome is a clarification question, the message should ask it "
     "politely.\n"
     "- If the outcome is a failure, be honest but helpful about what went wrong.\n"
     "- If edits landed, describe what changed in plain language.\n"
     "- If nothing changed, say so honestly without inventing edits.\n"
     "- Never include markdown, code fences, or structured data in the message.\n"
     "- Keep the message under 300 characters.\n"
     "You MUST state what happened per these structured facts and describe "
     "exactly those facts:\n"
     "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
     "  - outcome.kind: the public outcome kind (e.g. candidate, noop, clarify, failure).\n"
     "  - change.landed_operation_count: how many operations actually landed.\n"
     "  - validation.passed: whether post-edit validation passed.\n"
     "Never claim an edit you did not land: when graph_unchanged is true or "
     "landed_operation_count is 0, you MUST NOT say the graph was edited, "
     "applied, updated, connected, or changed. Never claim validation passed "
     "when validation.passed is false. The message must be consistent with "
     "every one of these fields."
 )
 
 
 def _build_narrator_messages(
     narrative_context: NarrativeContext,
     *,
     raw_executor_message: str = "",
     fallback_message: str = "",
 ) -> list[dict[str, str]]:
     from vibecomfy.comfy_nodes.agent.edit import (_NARRATOR_SYSTEM_PROMPT)  # T-039 late import: host namespace lookup; resolved at call time
     """Build the message list for the LLM narrator call."""
     context_json = json.dumps(narrative_context.payload, indent=2, sort_keys=True)
     user_content_parts: list[str] = [
         "Turn narrative context (JSON):",
         context_json,
     ]
     if raw_executor_message:
         user_content_parts.append(f"\nRaw executor message: {raw_executor_message[:240]}")
     if fallback_message:
         user_content_parts.append(f"\nFallback message (use as reference): {fallback_message}")
     user_content_parts.append("\nProduce the user-facing message as a JSON object.")
     return [
@@ -417,78 +418,89 @@ def _narrate_final_message(
                 llm_request,
                 route=route,
                 model=model,
             )
         except ProviderError as exc:
             LOGGER.warning("Narrator provider error (%s), falling back: %s", type(exc).__name__, exc)
             fallback_reason = "provider_failure"
         except MalformedModelJSON as exc:
             LOGGER.warning("Narrator malformed response, falling back: %s", exc)
             fallback_reason = "malformed_response"
         except TimeoutError:
             LOGGER.warning("Narrator LLM call timed out, falling back.")
             fallback_reason = "provider_failure"
         except Exception as exc:
             LOGGER.warning(
                 "Narrator LLM unexpected error (%s), falling back: %s",
                 type(exc).__name__,
                 exc,
             )
             fallback_reason = "provider_failure"
 
         # ── Select the message: the agent's own message ALWAYS ships. ──
         # There is no prose gate and no discard-and-replace: when the LLM
         # narrator produced a message, that message IS the final message.
         # The deterministic fallback ships only when no agent message exists.
         if llm_message is not None and fallback_reason is None:
             selected_source = "narrator"
             selected_message = llm_message
         else:
             selected_source = "fallback"
             selected_message = fallback_message
             fallback_reason = fallback_reason or "no_narrator_message"
 
         validation: dict[str, Any] = {
             "ok": True,
             "message": selected_message,
             "issues": [],
             "selected_source": selected_source,
             "fallback_reason": fallback_reason,
         }
-        _write_narrative_artifacts(
-            state,
-            narrative_context,
-            validation,
-            request_messages=llm_request,
-            llm_response=llm_response,
-        )
+        # Artifact persistence is best-effort: even if the writer itself
+        # raises (not just per-file write errors), the already-selected agent
+        # message must still ship.  The outer fallback catch below must never
+        # replace a selected narrator message with the deterministic fallback.
+        try:
+            _write_narrative_artifacts(
+                state,
+                narrative_context,
+                validation,
+                request_messages=llm_request,
+                llm_response=llm_response,
+            )
+        except Exception as exc:  # noqa: BLE001 - artifacts are presentation-only
+            LOGGER.warning(
+                "Narrative artifact write raised for turn %s (best-effort; selected message preserved): %s",
+                getattr(state, "turn_dir", None),
+                exc,
+            )
         return selected_message
 
     except Exception as exc:
         LOGGER.warning(
             "Narrator unrecoverable error (%s), returning raw fallback: %s",
             type(exc).__name__,
             exc,
         )
         return _deterministic_narrative_fallback(
             state,
             outcome=outcome,
             failure=failure,
             narrative_context=None,
             fallback_reason="narrator_unrecoverable_error",
         )
 
 
 __all__ = (
     "NarrativeContext",
     "_NARRATOR_DEFAULT_MODEL",
     "_NARRATOR_DEFAULT_ROUTE",
     "_NARRATOR_SYSTEM_PROMPT",
     "_assemble_narrative_context",
     "_build_narrator_messages",
     "_call_narrator_llm",
     "_deterministic_narrative_fallback",
     "_narrate_final_message",
     "_narrator_model",
     "_narrator_route",
     "_write_narrative_artifacts",
 )

exec
/bin/zsh -lc "rg -n 'unchanged|message_artifact|_MESSAGE_|_NARRATIVE_|implementation_result|landed_operation_count|route_graph_consistency|explicitly_non_edit|canonical_route' tests/live_agentic_harness/assessor.py
rg -n '"'^def test_|matcher|unchanged|landed_operation_count|artifact_write|validation'"\\.passed|route_graph_consistency|non_edit|grounded|safe_refusal' tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_edit_narrative.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
9:* graph unchanged when an edit was expected
12:* implementation_result.ok == false
88:    if response.get("graph_unchanged") is not False:
227:def _canonical_route(response: Mapping[str, Any]) -> str:
255:def _explicitly_non_edit_route(response: Mapping[str, Any]) -> bool:
262:    (graph_unchanged=false) must still be backed by a positive landed count.
268:    return _canonical_route(response) in _NON_EDIT_ROUTES
271:def _landed_operation_count(response: Mapping[str, Any]) -> Any:
272:    """Return ``change_details.landed_operation_count`` (any JSON value)."""
275:        return change_details.get("landed_operation_count")
630:    impl_result = _load_json(output_dir / "implementation_result.json")
643:            and response.get("graph_unchanged") is True
687:            elif response.get("graph_unchanged") is True:
692:                        "detail": "Expected graph change but response.graph_unchanged is True.",
697:            # (graph_unchanged is False) must be backed by a positive integer
698:            # change_details.landed_operation_count.  Missing, malformed, or
702:            route = _canonical_route(response)
705:                and response.get("graph_unchanged") is False
706:                and not _explicitly_non_edit_route(response)
708:                landed_count = _landed_operation_count(response)
716:                            "check": "landed_operation_count",
719:                                "Expected edit but change_details.landed_operation_count "
721:                                "when graph_unchanged is false."
727:            # never claim graph_unchanged=false.  Non-edit routes are exempt
729:            # unchanged (or the refusal is authorized above); an edit-route
734:                and response.get("graph_unchanged") is False
739:                        "check": "route_graph_consistency",
742:                            f"Non-edit route {route!r} claimed graph_unchanged=false; "
889:        # G0R: the residual "unchanged" substring gate over the
890:        # implementation_result message is removed — prose never gates
895:                    "check": "implementation_result_ok",
898:                        "implementation_result.ok is False: "
tests/test_live_agentic_assessor_score_honesty.py:9:def test_recovered_upstream_500_is_warning_when_candidate_succeeded(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:12:        "graph_unchanged": False,
tests/test_live_agentic_assessor_score_honesty.py:14:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_assessor_score_honesty.py:30:def test_upstream_500_remains_error_without_candidate(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:33:        "graph_unchanged": True,
tests/test_live_agentic_assessor_score_honesty.py:49:def test_skipped_queue_validation_is_warning_when_candidate_succeeded(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:52:        "graph_unchanged": False,
tests/test_live_agentic_assessor_score_honesty.py:54:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_assessor_score_honesty.py:83:def test_skipped_queue_validation_does_not_hide_other_failed_gates(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:86:        "graph_unchanged": False,
tests/test_live_agentic_assessor_score_honesty.py:88:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_assessor_score_honesty.py:123:def test_queue_validation_stage_failure_still_fails(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:126:        "graph_unchanged": False,
tests/test_live_agentic_assessor_score_honesty.py:128:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_assessor_score_honesty.py:156:def test_message_prose_never_affects_score(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:161:    pass both with a grounded message and with message prose that the old
tests/test_live_agentic_assessor_score_honesty.py:162:    deterministic matcher misread as a contradiction ("unchanged" parts of the
tests/test_live_agentic_assessor_score_honesty.py:169:        "graph_unchanged": False,
tests/test_live_agentic_assessor_score_honesty.py:172:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_assessor_score_honesty.py:188:        "Updated the KSampler; the other nodes are unchanged.",
tests/test_live_agentic_assessor_score_honesty.py:189:        "Node connections are unchanged; only the seed changed.",
tests/test_live_agentic_assessor_score_honesty.py:201:        # same "unchanged"-wording message in implementation_result.json must
tests/test_live_agentic_assessor_score_honesty.py:219:        "graph_unchanged": True,
tests/test_live_agentic_assessor_score_honesty.py:222:        "change_details": {"landed_operation_count": 0},
tests/test_live_agentic_assessor_score_honesty.py:255:def test_implementation_result_unchanged_prose_does_not_gate_scoring(tmp_path: Path) -> None:
tests/test_live_agentic_assessor_score_honesty.py:257:    nodes are unchanged must NOT affect scoring when the structured record
tests/test_live_agentic_assessor_score_honesty.py:260:    The residual ``"unchanged"`` substring gate (assessor.py:774 pre-G0R)
tests/test_live_agentic_assessor_score_honesty.py:266:        "graph_unchanged": False,
tests/test_live_agentic_assessor_score_honesty.py:269:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_assessor_score_honesty.py:283:        json.dumps({"message": "Updated the sampler; other nodes are unchanged."}),
tests/test_edit_narrative.py:5:Tests exercise the fact-grounded prompt construction, deterministic fallback,
tests/test_edit_narrative.py:48:def test_net_field_changes_collapses_revisions_and_drops_reverted_edits() -> None:
tests/test_edit_narrative.py:77:            "landed_operation_count": 1,
tests/test_edit_narrative.py:139:def test_total_landed_edit_count_includes_add_only_structural_edits() -> None:
tests/test_edit_narrative.py:151:def test_total_landed_edit_count_combines_fields_and_node_structure() -> None:
tests/test_edit_narrative.py:170:def test_total_landed_edit_count_trusts_empty_canonical_envelope() -> None:
tests/test_edit_narrative.py:192:            change={"graph_changed": True, "landed_operation_count": 3},
tests/test_edit_narrative.py:200:        assert ctx.landed_operation_count == 3
tests/test_edit_narrative.py:212:        assert ctx.landed_operation_count == 0
tests/test_edit_narrative.py:225:                "graph_unchanged": True,
tests/test_edit_narrative.py:260:# ── Fact-grounded synthesis prompt (G0-T2) ──────────────────────────────────
tests/test_edit_narrative.py:267:        assert "graph_unchanged" in prompt
tests/test_edit_narrative.py:269:        assert "landed_operation_count" in prompt
tests/test_edit_narrative.py:270:        assert "validation.passed" in prompt
tests/test_edit_narrative.py:275:        """The narrator request embeds graph_unchanged, outcome.kind, and
tests/test_edit_narrative.py:276:        landed_operation_count so the agent writes the message FROM the facts."""
tests/test_edit_narrative.py:286:                "graph_unchanged": False,
tests/test_edit_narrative.py:287:                "landed_operation_count": 2,
tests/test_edit_narrative.py:293:        assert '"graph_unchanged": false' in content
tests/test_edit_narrative.py:295:        assert '"landed_operation_count": 2' in content
tests/test_edit_narrative.py:358:            graph_unchanged=True,
tests/test_edit_narrative.py:625:    def test_unchanged_graph_edit_calls_llm_and_ships_message(
tests/test_edit_narrative.py:654:        context = TurnContext(session_id="unchanged", turn_id="0001")
tests/test_edit_narrative.py:665:        assert llm_called, "LLM should be called when graph is unchanged"
tests/test_edit_narrative.py:755:        ("The graph is unchanged." for an edit that landed). Under the old
tests/test_edit_narrative.py:762:            lambda **_kwargs: {"json": {"message": "The graph is unchanged."}},
tests/test_edit_narrative.py:792:        assert message == "The graph is unchanged."
tests/test_edit_narrative.py:919:    def test_artifact_write_failure_preserves_selected_agent_message(
tests/test_edit_narrative.py:937:        def _failing_artifact_write(*args: Any, **kwargs: Any) -> None:
tests/test_edit_narrative.py:942:            _failing_artifact_write,
tests/test_edit_narrative.py:972:        # The selected agent message ships unchanged — never the fallback.
tests/test_edit_narrative.py:1107:            graph_unchanged=True,
tests/test_live_agentic_harness_guard_contract.py:37:        "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:40:        "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:119:def test_agentic_guard_rejects_fake_dispatchers(tmp_path: Path, dispatcher: str) -> None:
tests/test_live_agentic_harness_guard_contract.py:128:def test_agentic_guard_rejects_non_agentic_model_behavior(
tests/test_live_agentic_harness_guard_contract.py:139:def test_agentic_guard_allows_blocked_real_agentic_artifacts(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:150:def test_agentic_guard_catches_unchanged_graph_and_upstream_errors(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:157:        "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:182:        json.dumps({"message": "The graph is unchanged."}),
tests/test_live_agentic_harness_guard_contract.py:200:    # "The graph is unchanged." message must not produce its own check.
tests/test_live_agentic_harness_guard_contract.py:204:def test_agentic_guard_allows_explicit_safe_refusal_scenarios(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:211:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:250:def test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:257:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:281:def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:288:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:307:        json.dumps({"message": "The graph is unchanged."}),
tests/test_live_agentic_harness_guard_contract.py:315:            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
tests/test_live_agentic_harness_guard_contract.py:324:    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
tests/test_live_agentic_harness_guard_contract.py:325:    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}
tests/test_live_agentic_harness_guard_contract.py:328:def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:335:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:348:            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
tests/test_live_agentic_harness_guard_contract.py:359:def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:366:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:369:                "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:395:def test_agentic_guard_rejects_forbidden_model_request_substrings(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:402:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:405:                "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:434:def test_agentic_guard_rejects_static_widget_edit_overridden_by_link(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:455:def test_agentic_guard_rejects_no_effective_value_change_for_claimed_target(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:476:def test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:494:# The nine matcher-only scenarios (Dig2 counterfactual rescore,
tests/test_live_agentic_harness_guard_contract.py:496:# ONLY because the deterministic message-artifact matcher misread prose:
tests/test_live_agentic_harness_guard_contract.py:497:#   - group A: the message says parts of the graph are "unchanged" while the
tests/test_live_agentic_harness_guard_contract.py:498:#     structured record proves an edit landed (the old \bunchanged\b matcher
tests/test_live_agentic_harness_guard_contract.py:502:#     (the old \bconnected\b/\bapplied\b matchers produced "message claims
tests/test_live_agentic_harness_guard_contract.py:503:#     edits even though response.graph_unchanged is True").
tests/test_live_agentic_harness_guard_contract.py:519:# (scenario_id, response) — prose excerpts are grounded in the persisted
tests/test_live_agentic_harness_guard_contract.py:520:# response.json artifacts of the recorded matcher-only failures.
tests/test_live_agentic_harness_guard_contract.py:529:                "other widgets are unchanged (structure validated)."
tests/test_live_agentic_harness_guard_contract.py:531:            "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:533:            "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:543:                "the SFT chain (audio input, prompt, LoRA, and save) is preserved unchanged."
tests/test_live_agentic_harness_guard_contract.py:545:            "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:547:            "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:558:                "(0 / 0.75) stay unchanged."
tests/test_live_agentic_harness_guard_contract.py:560:            "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:562:            "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:572:                "`Modelscopet2v` and `CR Prompt Text` nodes are unchanged."
tests/test_live_agentic_harness_guard_contract.py:574:            "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:576:            "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:586:                "LoadImage and SaveVideo are unchanged and still connected as before."
tests/test_live_agentic_harness_guard_contract.py:588:            "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:590:            "change_details": {"landed_operation_count": 2},
tests/test_live_agentic_harness_guard_contract.py:604:            "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:606:            "change_details": {"landed_operation_count": 0},
tests/test_live_agentic_harness_guard_contract.py:619:            "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:621:            "change_details": {"landed_operation_count": 0},
tests/test_live_agentic_harness_guard_contract.py:635:            "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:637:            "change_details": {"landed_operation_count": 0},
tests/test_live_agentic_harness_guard_contract.py:650:            "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:652:            "change_details": {"landed_operation_count": 0},
tests/test_live_agentic_harness_guard_contract.py:664:def test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating(
tests/test_live_agentic_harness_guard_contract.py:669:    """The nine matcher-only scenarios now pass: prose never gates scoring."""
tests/test_live_agentic_harness_guard_contract.py:674:    expect_edit = bool(response.get("graph_unchanged") is False)
tests/test_live_agentic_harness_guard_contract.py:693:def test_agentic_guard_false_landed_claim_still_fails_via_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:709:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:712:                "change_details": {"landed_operation_count": 0},
tests/test_live_agentic_harness_guard_contract.py:734:def test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:743:    output_dir = tmp_path / "false-unchanged-claim"
tests/test_live_agentic_harness_guard_contract.py:750:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:752:                "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:760:        "id": "false-unchanged-claim",
tests/test_live_agentic_harness_guard_contract.py:778:def test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check(
tests/test_live_agentic_harness_guard_contract.py:810:def test_agentic_guard_false_validation_success_claim_still_fails_via_gates(
tests/test_live_agentic_harness_guard_contract.py:825:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:828:                "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:861:# ── G0R: structural expected-edit guard (landed_operation_count) ──────────
tests/test_live_agentic_harness_guard_contract.py:863:# A claimed edit (graph_unchanged is False) must be backed by a positive
tests/test_live_agentic_harness_guard_contract.py:864:# integer change_details.landed_operation_count.  Missing, malformed, or
tests/test_live_agentic_harness_guard_contract.py:865:# zero counts fail closed; accepted grounded refusals and canonical
tests/test_live_agentic_harness_guard_contract.py:876:        pytest.param({"landed_operation_count": 0}, id="zero-landed-count"),
tests/test_live_agentic_harness_guard_contract.py:877:        pytest.param({"landed_operation_count": -1}, id="negative-landed-count"),
tests/test_live_agentic_harness_guard_contract.py:878:        pytest.param({"landed_operation_count": "1"}, id="string-landed-count"),
tests/test_live_agentic_harness_guard_contract.py:879:        pytest.param({"landed_operation_count": 1.5}, id="float-landed-count"),
tests/test_live_agentic_harness_guard_contract.py:880:        pytest.param({"landed_operation_count": True}, id="bool-landed-count"),
tests/test_live_agentic_harness_guard_contract.py:883:def test_agentic_guard_expected_edit_requires_positive_landed_count(
tests/test_live_agentic_harness_guard_contract.py:888:    """G0R negative control: graph_unchanged=false with a missing, malformed,
tests/test_live_agentic_harness_guard_contract.py:889:    or zero landed_operation_count fails closed structurally."""
tests/test_live_agentic_harness_guard_contract.py:894:        "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:915:    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
tests/test_live_agentic_harness_guard_contract.py:918:def test_agentic_guard_expected_edit_with_positive_landed_count_passes(
tests/test_live_agentic_harness_guard_contract.py:921:    """G0R positive control: graph_unchanged=false with a positive integer
tests/test_live_agentic_harness_guard_contract.py:922:    landed_operation_count passes the structural guard."""
tests/test_live_agentic_harness_guard_contract.py:929:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:932:                "change_details": {"landed_operation_count": 1},
tests/test_live_agentic_harness_guard_contract.py:952:        if issue["check"] == "landed_operation_count"
tests/test_live_agentic_harness_guard_contract.py:956:def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
tests/test_live_agentic_harness_guard_contract.py:959:    """G0R: an accepted grounded refusal (graph_unchanged=true, allowed
tests/test_live_agentic_harness_guard_contract.py:960:    outcome kind) is exempt from the landed_operation_count requirement."""
tests/test_live_agentic_harness_guard_contract.py:967:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:982:                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
tests/test_live_agentic_harness_guard_contract.py:989:    assert {issue["check"] for issue in verdict["assessment"]["issues"]} == {"safe_refusal"}
tests/test_live_agentic_harness_guard_contract.py:993:        if issue["check"] == "landed_operation_count"
tests/test_live_agentic_harness_guard_contract.py:997:def test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:999:    graph_unchanged=false, no landed count, self-labeling outcome.kind=clarify
tests/test_live_agentic_harness_guard_contract.py:1001:    from the landed_operation_count guard."""
tests/test_live_agentic_harness_guard_contract.py:1009:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:1031:    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
tests/test_live_agentic_harness_guard_contract.py:1034:def test_agentic_guard_rejects_route_not_applyable_without_landed_count(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1035:    """G0R negative control: graph_unchanged=false with
tests/test_live_agentic_harness_guard_contract.py:1045:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:1067:    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
tests/test_live_agentic_harness_guard_contract.py:1070:def test_agentic_guard_rejects_failure_outcome_without_landed_count(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1073:    graph_unchanged=false and no landed count still fails the
tests/test_live_agentic_harness_guard_contract.py:1074:    landed_operation_count guard."""
tests/test_live_agentic_harness_guard_contract.py:1082:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:1104:    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
tests/test_live_agentic_harness_guard_contract.py:1107:def test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph(
tests/test_live_agentic_harness_guard_contract.py:1111:    graph_unchanged=true and an authorized refusal outcome kind is still
tests/test_live_agentic_harness_guard_contract.py:1121:                "graph_unchanged": True,
tests/test_live_agentic_harness_guard_contract.py:1136:                "allow_safe_refusal_outcome_kinds": ["respond", "clarify"],
tests/test_live_agentic_harness_guard_contract.py:1145:    assert "safe_refusal" in checks
tests/test_live_agentic_harness_guard_contract.py:1146:    assert "landed_operation_count" not in checks
tests/test_live_agentic_harness_guard_contract.py:1147:    assert "route_graph_consistency" not in checks
tests/test_live_agentic_harness_guard_contract.py:1150:def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1154:    graph_unchanged=false is exempt from the landed-count guard but still
tests/test_live_agentic_harness_guard_contract.py:1164:                "graph_unchanged": False,
tests/test_live_agentic_harness_guard_contract.py:1186:    assert "route_graph_consistency" in error_checks
tests/test_live_agentic_harness_guard_contract.py:1189:    assert "landed_operation_count" not in error_checks
tests/test_live_agentic_harness_guard_contract.py:1192:def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1213:def test_agentic_guard_allows_shared_linked_source_edit_when_declared(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1231:def test_agentic_guard_treats_skipped_queue_validation_as_warning(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1268:def test_agentic_guard_product_fails_real_queue_validation_failure(tmp_path: Path) -> None:

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '210,285p;620,760p;865,910p'
nl -ba tests/test_live_agentic_harness_guard_contract.py | sed -n '485,730p;850,1200p'
nl -ba tests/test_live_agentic_assessor_score_honesty.py | sed -n '145,310p'
nl -ba tests/test_edit_narrative.py | sed -n '250,310p;900,990p'
nl -ba vibecomfy/comfy_nodes/agent/_frag_narrator.py | sed -n '232,282p;400,495p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
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
   221	                    seen.add(node)
   222	                    issues.append(node)
   223	                break
   224	    return issues
   225	
   226	
   227	def _canonical_route(response: Mapping[str, Any]) -> str:
   228	    """Return the canonical public route carried by the response envelope.
   229	
   230	    The authoritative field is the top-level ``route`` (written by
   231	    ``AgentTurnResult.to_dict`` in vibecomfy.executor.contracts); the same
   232	    public route is mirrored in ``evidence.classification.route`` and
   233	    ``report.executor.plan.route``.  Missing/non-string routes resolve to
   234	    the empty string so an envelope without a route can never claim a
   235	    non-edit exemption (fail closed).
   236	    """
   237	    route = response.get("route")
   238	    if isinstance(route, str):
   239	        return route
   240	    evidence = response.get("evidence")
   241	    if isinstance(evidence, Mapping):
   242	        classification = evidence.get("classification")
   243	        if isinstance(classification, Mapping) and isinstance(classification.get("route"), str):
   244	            return classification["route"]
   245	    report = response.get("report")
   246	    if isinstance(report, Mapping):
   247	        executor = report.get("executor")
   248	        if isinstance(executor, Mapping):
   249	            plan = executor.get("plan")
   250	            if isinstance(plan, Mapping) and isinstance(plan.get("route"), str):
   251	                return plan["route"]
   252	    return ""
   253	
   254	
   255	def _explicitly_non_edit_route(response: Mapping[str, Any]) -> bool:
   256	    """Return True when the envelope's canonical route is a non-edit route.
   257	
   258	    The route is read from the envelope (``response.route``) — never from the
   259	    agent's self-declared ``no_candidate_reason`` / ``outcome.kind``.  An
   260	    edit-route envelope self-labeling ``outcome.kind=clarify`` or
   261	    ``no_candidate_reason=route_not_applyable`` is NOT exempt: a claimed edit
   262	    (graph_unchanged=false) must still be backed by a positive landed count.
   263	    These routes are scored by their own structured checks
   264	    (``no_candidate_reason`` / ``outcome_kind``) and by the route/graph
   265	    consistency check; demanding a positive landed operation count for them
   266	    would be wrong — a truthful non-edit route has no operations to count.
   267	    """
   268	    return _canonical_route(response) in _NON_EDIT_ROUTES
   269	
   270	
   271	def _landed_operation_count(response: Mapping[str, Any]) -> Any:
   272	    """Return ``change_details.landed_operation_count`` (any JSON value)."""
   273	    change_details = response.get("change_details")
   274	    if isinstance(change_details, Mapping):
   275	        return change_details.get("landed_operation_count")
   276	    return None
   277	
   278	
   279	def _expects_graph_changed(
   280	    scenario: Mapping[str, Any] | None,
   281	    response: Mapping[str, Any] | None,
   282	) -> bool:
   283	    """Decide whether this scenario should have produced a graph change.
   284	
   285	    Explicit scenario configuration wins, then we fall back to reading the
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
   716	                            "check": "landed_operation_count",
   717	                            "severity": "error",
   718	                            "detail": (
   719	                                "Expected edit but change_details.landed_operation_count "
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
   865	        # Critical upstream failures (Hivemind 500, etc.). When a successful
   866	        # candidate exists, a recovered research-side upstream error should stay
   867	        # visible but not invalidate an otherwise valid edit.
   868	        upstream_severity = "warning" if _has_successful_candidate(response) else "error"
   869	        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
   870	            issues.append(
   871	                {
   872	                    "check": "upstream_failure",
   873	                    "severity": upstream_severity,
   874	                    "detail": msg,
   875	                }
   876	            )
   877	
   878	        # Capacity/soft warnings: surfaced, but not counted as errors.
   879	        for msg in _collect_pattern_matches(response, _SOFT_WARNING_PATTERNS):
   880	            issues.append(
   881	                {
   882	                    "check": "soft_warning",
   883	                    "severity": "warning",
   884	                    "detail": msg,
   885	                }
   886	            )
   887	
   888	    if impl_result is not None:
   889	        # G0R: the residual "unchanged" substring gate over the
   890	        # implementation_result message is removed — prose never gates
   891	        # scoring.  Only the structured ok flag is authoritative.
   892	        if impl_result.get("ok") is False:
   893	            issues.append(
   894	                {
   895	                    "check": "implementation_result_ok",
   896	                    "severity": "error",
   897	                    "detail": (
   898	                        "implementation_result.ok is False: "
   899	                        f"{impl_result.get('error') or impl_result.get('message', '')}"
   900	                    ),
   901	                }
   902	            )
   903	
   904	    issues.extend(_assess_model_request_artifact(output_dir, scenario))
   905	
   906	    # Deduplicate while preserving order.
   907	    seen: set[tuple[str, str, str]] = set()
   908	    deduped: list[dict[str, Any]] = []
   909	    for issue in issues:
   910	        key = (issue["check"], issue["severity"], issue["detail"])
   485	
   486	    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())
   487	
   488	    assert verdict["live_agentic_success"] is True
   489	    assert verdict["assessment"]["passed"] is True
   490	
   491	
   492	# ── G0-T2: structured-only scoring — prose never gates a scenario ──────────
   493	#
   494	# The nine matcher-only scenarios (Dig2 counterfactual rescore,
   495	# docs/failure-analysis/agentic-pipeline-improvement-2026-08.md §9) failed
   496	# ONLY because the deterministic message-artifact matcher misread prose:
   497	#   - group A: the message says parts of the graph are "unchanged" while the
   498	#     structured record proves an edit landed (the old \bunchanged\b matcher
   499	#     produced "message claims no change even though response graph changed");
   500	#   - group B: the message is an explanation that uses words like
   501	#     "connected"/"applied" while the structured record proves no edit landed
   502	#     (the old \bconnected\b/\bapplied\b matchers produced "message claims
   503	#     edits even though response.graph_unchanged is True").
   504	# With deterministic prose gating removed, every one of these must PASS on the
   505	# structured record alone — the message never flips pass/fail.
   506	
   507	_ALL_GATES_PASS = {
   508	    "ir_validate_ok": True,
   509	    "lower_ok": True,
   510	    "plan_validate_ok": True,
   511	    "python_load_ok": True,
   512	    "queue_validate_ok": True,
   513	    "state_match_ok": True,
   514	    "ui_emit_ok": True,
   515	    "ui_fidelity_ok": True,
   516	    "ui_load_safe_ok": True,
   517	}
   518	
   519	# (scenario_id, response) — prose excerpts are grounded in the persisted
   520	# response.json artifacts of the recorded matcher-only failures.
   521	_MATCHER_ONLY_COUNTEREXAMPLES: tuple[tuple[str, dict[str, object]], ...] = (
   522	    (
   523	        "3d-generates-a-3d-mesh-from",
   524	        {
   525	            "message": (
   526	                "Done — I tuned the mesh-generation path to reduce floating bits and noise. "
   527	                "Concretely, `KSampler` steps went from 20 to 50 so the sampler converges "
   528	                "further before `VAEDecodeHunyuan3D` extracts the mesh; node connections and "
   529	                "other widgets are unchanged (structure validated)."
   530	            ),
   531	            "graph_unchanged": False,
   532	            "outcome": {"kind": "candidate"},
   533	            "change_details": {"landed_operation_count": 1},
   534	            "gates": _ALL_GATES_PASS,
   535	        },
   536	    ),
   537	    (
   538	        "audio-acestep-audio-generation-workflow-2a31ec",
   539	        {
   540	            "message": (
   541	                "The AceStepSFTGenerate node now uses acestep-sft-v2.safetensors as its base "
   542	                "model checkpoint (widget_0), replacing acestep-v15.safetensors. The rest of "
   543	                "the SFT chain (audio input, prompt, LoRA, and save) is preserved unchanged."
   544	            ),
   545	            "graph_unchanged": False,
   546	            "outcome": {"kind": "candidate"},
   547	            "change_details": {"landed_operation_count": 1},
   548	            "gates": _ALL_GATES_PASS,
   549	        },
   550	    ),
   551	    (
   552	        "image-sd3-image-generation-with-controlnet-19d221",
   553	        {
   554	            "message": (
   555	                "I lowered the ControlNet influence to give your text prompt the upper hand: "
   556	                "the `strength` widget on `ACN_AdvancedControlNetApply` (node 60) is now 0.5, "
   557	                "down from 0.6, while the tile ControlNet loader and its start/end percent "
   558	                "(0 / 0.75) stay unchanged."
   559	            ),
   560	            "graph_unchanged": False,
   561	            "outcome": {"kind": "candidate"},
   562	            "change_details": {"landed_operation_count": 1},
   563	            "gates": _ALL_GATES_PASS,
   564	        },
   565	    ),
   566	    (
   567	        "video-generates-a-video-from-a",
   568	        {
   569	            "message": (
   570	                "Done — I set the video output to 24 fps by updating the `frame_rate` widget "
   571	                "on VHS_VideoCombine from 15 to 24. No other nodes were touched; the "
   572	                "`Modelscopet2v` and `CR Prompt Text` nodes are unchanged."
   573	            ),
   574	            "graph_unchanged": False,
   575	            "outcome": {"kind": "candidate"},
   576	            "change_details": {"landed_operation_count": 1},
   577	            "gates": _ALL_GATES_PASS,
   578	        },
   579	    ),
   580	    (
   581	        "video-image-to-video-conversion-with-moonvalley-d7853c",
   582	        {
   583	            "message": (
   584	                "Updated MoonvalleyImg2VideoNode so the output videos are 5.0 seconds long: "
   585	                "frame count (widget_3) 7 -> 120, frame rate (widget_6) 100 -> 24 fps. "
   586	                "LoadImage and SaveVideo are unchanged and still connected as before."
   587	            ),
   588	            "graph_unchanged": False,
   589	            "outcome": {"kind": "candidate"},
   590	            "change_details": {"landed_operation_count": 2},
   591	            "gates": _ALL_GATES_PASS,
   592	        },
   593	    ),
   594	    (
   595	        "multi-ai-video-upscaling-with-detail-daemon-sampler-673197",
   596	        {
   597	            "message": (
   598	                "Here's what your graph (29 nodes) actually does, and where the color-shift "
   599	                "suspects live. Pipeline as connected: 1. Conditioning — CLIPLoader encodes "
   600	                "the prompt via CLIPTextEncode; 2. Sampling chain — UNETLoader feeds three "
   601	                "BetaSamplingScheduler nodes. Since the SeedVR2 nodes are disconnected here, "
   602	                "I'd verify whether the upscaler is being used."
   603	            ),
   604	            "graph_unchanged": True,
   605	            "outcome": {"kind": "noop"},
   606	            "change_details": {"landed_operation_count": 0},
   607	            "gates": _ALL_GATES_PASS,
   608	        },
   609	    ),
   610	    (
   611	        "multi-audio-to-image-mel-band-roformer-workflow-b22937",
   612	        {
   613	            "message": (
   614	                "This graph is an audio-enhancement pipeline: load a WAV, process it with a "
   615	                "Mel-band separation model, then upscale the result. The sampler applies "
   616	                "MelBandRoFormer to do the core audio processing. Portability note: the "
   617	                "model loader isn't connected to the data flow; no changes were made."
   618	            ),
   619	            "graph_unchanged": True,
   620	            "outcome": {"kind": "noop"},
   621	            "change_details": {"landed_operation_count": 0},
   622	            "gates": _ALL_GATES_PASS,
   623	        },
   624	    ),
   625	    (
   626	        "video-hunyuan-video-text-to-video-generation-265847",
   627	        {
   628	            "message": (
   629	                "This is a Hunyuan Video T2V workflow: UNETLoader -> ModelSamplingSD3 -> "
   630	                "SamplerCustomAdvanced with euler / 20 steps / denoise=1, starting from "
   631	                "EmptyHunyuanLatentVideo (73 frames). There is a VAEDecode (node 8) that is "
   632	                "not connected to the save node; the animated WEBP is saved from "
   633	                "VAEDecodeTiled at 24 fps."
   634	            ),
   635	            "graph_unchanged": True,
   636	            "outcome": {"kind": "noop"},
   637	            "change_details": {"landed_operation_count": 0},
   638	            "gates": _ALL_GATES_PASS,
   639	        },
   640	    ),
   641	    (
   642	        "video-video-output-workflow-f855de",
   643	        {
   644	            "message": (
   645	                "This graph makes a low-resolution image, upscales it, decodes latents, and "
   646	                "writes the video directly. Likely causes of blur: both upscale stages are "
   647	                "toggled off, so the saved frames are the tiny base resolution. Note the "
   648	                "detail-enhancement edits I have not applied."
   649	            ),
   650	            "graph_unchanged": True,
   651	            "outcome": {"kind": "noop"},
   652	            "change_details": {"landed_operation_count": 0},
   653	            "gates": _ALL_GATES_PASS,
   654	        },
   655	    ),
   656	)
   657	
   658	
   659	@pytest.mark.parametrize(
   660	    ("scenario_id", "response"),
   661	    _MATCHER_ONLY_COUNTEREXAMPLES,
   662	    ids=[scenario_id for scenario_id, _ in _MATCHER_ONLY_COUNTEREXAMPLES],
   663	)
   664	def test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating(
   665	    tmp_path: Path,
   666	    scenario_id: str,
   667	    response: dict[str, object],
   668	) -> None:
   669	    """The nine matcher-only scenarios now pass: prose never gates scoring."""
   670	    output_dir = tmp_path / scenario_id
   671	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   672	    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
   673	
   674	    expect_edit = bool(response.get("graph_unchanged") is False)
   675	    scenario = {
   676	        "id": scenario_id,
   677	        "assessment": {
   678	            "expect_graph_changed": expect_edit,
   679	            "skip_intent_judge": True,
   680	        },
   681	    }
   682	    verdict = guard_output_dir(output_dir, scenario=scenario)
   683	
   684	    assert verdict["live_agentic_success"] is True, verdict["assessment"]["issues"]
   685	    assert verdict["score_class"] == "pass"
   686	    assert verdict["assessment"]["passed"] is True
   687	    assert all(
   688	        issue["check"] != "message_artifact"
   689	        for issue in verdict["assessment"]["issues"]
   690	    ), "prose must never produce an error-severity issue"
   691	
   692	
   693	def test_agentic_guard_false_landed_claim_still_fails_via_structured_checks(
   694	    tmp_path: Path,
   695	) -> None:
   696	    """Control: a message claiming edits that never landed still fails the run.
   697	
   698	    The failure comes from the STRUCTURED record (no edit landed while one was
   699	    expected — graph_changed / outcome_kind / no_candidate_reason), never from
   700	    matching the message's words.
   701	    """
   702	    output_dir = tmp_path / "false-landed-claim"
   703	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   704	    (output_dir / "response.json").write_text(
   705	        json.dumps(
   706	            {
   707	                "ok": True,
   708	                "message": "Applied 2 edits and rewired the sampler.",
   709	                "graph_unchanged": True,
   710	                "no_candidate_reason": "no_changes",
   711	                "outcome": {"kind": "noop"},
   712	                "change_details": {"landed_operation_count": 0},
   713	            }
   714	        ),
   715	        encoding="utf-8",
   716	    )
   717	
   718	    scenario = {
   719	        "id": "false-landed-claim",
   720	        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
   721	    }
   722	    verdict = guard_output_dir(output_dir, scenario=scenario)
   723	
   724	    assert verdict["live_agentic_success"] is False
   725	    error_checks = {
   726	        issue["check"]
   727	        for issue in verdict["assessment"]["issues"]
   728	        if issue["severity"] == "error"
   729	    }
   730	    assert {"graph_changed", "outcome_kind", "no_candidate_reason"} <= error_checks
   850	
   851	    assert verdict["live_agentic_success"] is False
   852	    error_checks = {
   853	        issue["check"]
   854	        for issue in verdict["assessment"]["issues"]
   855	        if issue["severity"] == "error"
   856	    }
   857	    assert "gates" in error_checks
   858	    assert "message_artifact" not in error_checks
   859	
   860	
   861	# ── G0R: structural expected-edit guard (landed_operation_count) ──────────
   862	#
   863	# A claimed edit (graph_unchanged is False) must be backed by a positive
   864	# integer change_details.landed_operation_count.  Missing, malformed, or
   865	# zero counts fail closed; accepted grounded refusals and canonical
   866	# non-edit routes (read from response.route — never from self-declared
   867	# outcome/no_candidate_reason labels) are exempt (they are scored by
   868	# their own checks, including the route/graph consistency check).
   869	
   870	
   871	@pytest.mark.parametrize(
   872	    "change_details",
   873	    [
   874	        pytest.param(None, id="missing-change-details"),
   875	        pytest.param({}, id="missing-landed-count"),
   876	        pytest.param({"landed_operation_count": 0}, id="zero-landed-count"),
   877	        pytest.param({"landed_operation_count": -1}, id="negative-landed-count"),
   878	        pytest.param({"landed_operation_count": "1"}, id="string-landed-count"),
   879	        pytest.param({"landed_operation_count": 1.5}, id="float-landed-count"),
   880	        pytest.param({"landed_operation_count": True}, id="bool-landed-count"),
   881	    ],
   882	)
   883	def test_agentic_guard_expected_edit_requires_positive_landed_count(
   884	    tmp_path: Path,
   885	    change_details: dict[str, object] | None,
   886	    request: pytest.FixtureRequest,
   887	) -> None:
   888	    """G0R negative control: graph_unchanged=false with a missing, malformed,
   889	    or zero landed_operation_count fails closed structurally."""
   890	    output_dir = tmp_path / f"landed-count-{request.node.callspec.id}"
   891	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   892	    response = {
   893	        "ok": True,
   894	        "graph_unchanged": False,
   895	        "outcome": {"kind": "candidate"},
   896	        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
   897	        "gates": _ALL_GATES_PASS,
   898	    }
   899	    if change_details is not None:
   900	        response["change_details"] = change_details
   901	    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
   902	
   903	    scenario = {
   904	        "id": f"landed-count-{change_details!r}",
   905	        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
   906	    }
   907	    verdict = guard_output_dir(output_dir, scenario=scenario)
   908	
   909	    assert verdict["live_agentic_success"] is False
   910	    error_checks = {
   911	        issue["check"]
   912	        for issue in verdict["assessment"]["issues"]
   913	        if issue["severity"] == "error"
   914	    }
   915	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
   916	
   917	
   918	def test_agentic_guard_expected_edit_with_positive_landed_count_passes(
   919	    tmp_path: Path,
   920	) -> None:
   921	    """G0R positive control: graph_unchanged=false with a positive integer
   922	    landed_operation_count passes the structural guard."""
   923	    output_dir = tmp_path / "landed-count-positive"
   924	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   925	    (output_dir / "response.json").write_text(
   926	        json.dumps(
   927	            {
   928	                "ok": True,
   929	                "graph_unchanged": False,
   930	                "outcome": {"kind": "candidate"},
   931	                "candidate_graph": {"nodes": [{"id": 1}], "links": []},
   932	                "change_details": {"landed_operation_count": 1},
   933	                "gates": _ALL_GATES_PASS,
   934	            }
   935	        ),
   936	        encoding="utf-8",
   937	    )
   938	
   939	    verdict = guard_output_dir(
   940	        output_dir,
   941	        scenario={
   942	            "id": "landed-count-positive",
   943	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
   944	        },
   945	    )
   946	
   947	    assert verdict["live_agentic_success"] is True
   948	    assert verdict["assessment"]["passed"] is True
   949	    assert not [
   950	        issue
   951	        for issue in verdict["assessment"]["issues"]
   952	        if issue["check"] == "landed_operation_count"
   953	    ]
   954	
   955	
   956	def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
   957	    tmp_path: Path,
   958	) -> None:
   959	    """G0R: an accepted grounded refusal (graph_unchanged=true, allowed
   960	    outcome kind) is exempt from the landed_operation_count requirement."""
   961	    output_dir = tmp_path / "landed-count-refusal-exempt"
   962	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   963	    (output_dir / "response.json").write_text(
   964	        json.dumps(
   965	            {
   966	                "ok": True,
   967	                "graph_unchanged": True,
   968	                "no_candidate_reason": "no_changes",
   969	                "outcome": {"kind": "requires_custom_nodes"},
   970	                "message": "No schema-backed replacement node was found.",
   971	            }
   972	        ),
   973	        encoding="utf-8",
   974	    )
   975	
   976	    verdict = guard_output_dir(
   977	        output_dir,
   978	        scenario={
   979	            "id": "landed-count-refusal-exempt",
   980	            "assessment": {
   981	                "expect_graph_changed": True,
   982	                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
   983	            },
   984	        },
   985	    )
   986	
   987	    assert verdict["live_agentic_success"] is True
   988	    assert verdict["assessment"]["passed"] is True
   989	    assert {issue["check"] for issue in verdict["assessment"]["issues"]} == {"safe_refusal"}
   990	    assert not [
   991	        issue
   992	        for issue in verdict["assessment"]["issues"]
   993	        if issue["check"] == "landed_operation_count"
   994	    ]
   995	
   996	
   997	def test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify(tmp_path: Path) -> None:
   998	    """G0R negative control: an edit-route envelope (route=revise) with
   999	    graph_unchanged=false, no landed count, self-labeling outcome.kind=clarify
  1000	    must fail closed — self-declared outcome labels cannot buy an exemption
  1001	    from the landed_operation_count guard."""
  1002	    output_dir = tmp_path / "landed-count-edit-route-clarify-relabel"
  1003	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1004	    (output_dir / "response.json").write_text(
  1005	        json.dumps(
  1006	            {
  1007	                "ok": True,
  1008	                "route": "revise",
  1009	                "graph_unchanged": False,
  1010	                "outcome": {"kind": "clarify"},
  1011	                "message": "Which node should I edit next?",
  1012	            }
  1013	        ),
  1014	        encoding="utf-8",
  1015	    )
  1016	
  1017	    verdict = guard_output_dir(
  1018	        output_dir,
  1019	        scenario={
  1020	            "id": "landed-count-edit-route-clarify-relabel",
  1021	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1022	        },
  1023	    )
  1024	
  1025	    assert verdict["live_agentic_success"] is False
  1026	    error_checks = {
  1027	        issue["check"]
  1028	        for issue in verdict["assessment"]["issues"]
  1029	        if issue["severity"] == "error"
  1030	    }
  1031	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
  1032	
  1033	
  1034	def test_agentic_guard_rejects_route_not_applyable_without_landed_count(tmp_path: Path) -> None:
  1035	    """G0R negative control: graph_unchanged=false with
  1036	    no_candidate_reason=route_not_applyable and no landed count must fail
  1037	    closed — a self-declared no-candidate reason cannot bypass the guard when
  1038	    no canonical non-edit route backs it."""
  1039	    output_dir = tmp_path / "landed-count-route-not-applyable"
  1040	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1041	    (output_dir / "response.json").write_text(
  1042	        json.dumps(
  1043	            {
  1044	                "ok": True,
  1045	                "graph_unchanged": False,
  1046	                "no_candidate_reason": "route_not_applyable",
  1047	                "message": "This request is not applicable to the current graph.",
  1048	            }
  1049	        ),
  1050	        encoding="utf-8",
  1051	    )
  1052	
  1053	    verdict = guard_output_dir(
  1054	        output_dir,
  1055	        scenario={
  1056	            "id": "landed-count-route-not-applyable",
  1057	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1058	        },
  1059	    )
  1060	
  1061	    assert verdict["live_agentic_success"] is False
  1062	    error_checks = {
  1063	        issue["check"]
  1064	        for issue in verdict["assessment"]["issues"]
  1065	        if issue["severity"] == "error"
  1066	    }
  1067	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
  1068	
  1069	
  1070	def test_agentic_guard_rejects_failure_outcome_without_landed_count(tmp_path: Path) -> None:
  1071	    """G0R negative control: failure outcomes cannot bypass all structured
  1072	    checks — an edit-route envelope with outcome.kind=failure,
  1073	    graph_unchanged=false and no landed count still fails the
  1074	    landed_operation_count guard."""
  1075	    output_dir = tmp_path / "landed-count-failure-outcome"
  1076	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1077	    (output_dir / "response.json").write_text(
  1078	        json.dumps(
  1079	            {
  1080	                "ok": True,
  1081	                "route": "revise",
  1082	                "graph_unchanged": False,
  1083	                "outcome": {"kind": "failure"},
  1084	                "message": "The edit could not be completed.",
  1085	            }
  1086	        ),
  1087	        encoding="utf-8",
  1088	    )
  1089	
  1090	    verdict = guard_output_dir(
  1091	        output_dir,
  1092	        scenario={
  1093	            "id": "landed-count-failure-outcome",
  1094	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1095	        },
  1096	    )
  1097	
  1098	    assert verdict["live_agentic_success"] is False
  1099	    error_checks = {
  1100	        issue["check"]
  1101	        for issue in verdict["assessment"]["issues"]
  1102	        if issue["severity"] == "error"
  1103	    }
  1104	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
  1105	
  1106	
  1107	def test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph(
  1108	    tmp_path: Path,
  1109	) -> None:
  1110	    """G0R positive control: a canonical non-edit route (route=respond) with
  1111	    graph_unchanged=true and an authorized refusal outcome kind is still
  1112	    exempt — the route-aware exemption must not over-correct truthful non-edit
  1113	    responses."""
  1114	    output_dir = tmp_path / "landed-count-genuine-non-edit-route-exempt"
  1115	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1116	    (output_dir / "response.json").write_text(
  1117	        json.dumps(
  1118	            {
  1119	                "ok": True,
  1120	                "route": "respond",
  1121	                "graph_unchanged": True,
  1122	                "no_candidate_reason": "route_not_applyable",
  1123	                "outcome": {"kind": "respond"},
  1124	                "message": "I answered directly; no graph change was needed.",
  1125	            }
  1126	        ),
  1127	        encoding="utf-8",
  1128	    )
  1129	
  1130	    verdict = guard_output_dir(
  1131	        output_dir,
  1132	        scenario={
  1133	            "id": "landed-count-genuine-non-edit-route-exempt",
  1134	            "assessment": {
  1135	                "expect_graph_changed": True,
  1136	                "allow_safe_refusal_outcome_kinds": ["respond", "clarify"],
  1137	                "skip_intent_judge": True,
  1138	            },
  1139	        },
  1140	    )
  1141	
  1142	    assert verdict["live_agentic_success"] is True
  1143	    assert verdict["assessment"]["passed"] is True
  1144	    checks = {issue["check"] for issue in verdict["assessment"]["issues"]}
  1145	    assert "safe_refusal" in checks
  1146	    assert "landed_operation_count" not in checks
  1147	    assert "route_graph_consistency" not in checks
  1148	
  1149	
  1150	def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
  1151	    tmp_path: Path,
  1152	) -> None:
  1153	    """G0R control: a canonical non-edit route (route=respond) claiming
  1154	    graph_unchanged=false is exempt from the landed-count guard but still
  1155	    fails through its own structured checks (route/graph consistency,
  1156	    no_candidate_reason, outcome_kind) when an edit was expected."""
  1157	    output_dir = tmp_path / "landed-count-noop-not-exempt-from-noop-check"
  1158	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1159	    (output_dir / "response.json").write_text(
  1160	        json.dumps(
  1161	            {
  1162	                "ok": True,
  1163	                "route": "respond",
  1164	                "graph_unchanged": False,
  1165	                "no_candidate_reason": "no_changes",
  1166	                "outcome": {"kind": "noop"},
  1167	            }
  1168	        ),
  1169	        encoding="utf-8",
  1170	    )
  1171	
  1172	    verdict = guard_output_dir(
  1173	        output_dir,
  1174	        scenario={
  1175	            "id": "landed-count-noop-check",
  1176	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1177	        },
  1178	    )
  1179	
  1180	    assert verdict["live_agentic_success"] is False
  1181	    error_checks = {
  1182	        issue["check"]
  1183	        for issue in verdict["assessment"]["issues"]
  1184	        if issue["severity"] == "error"
  1185	    }
  1186	    assert "route_graph_consistency" in error_checks
  1187	    assert "no_candidate_reason" in error_checks
  1188	    assert "outcome_kind" in error_checks
  1189	    assert "landed_operation_count" not in error_checks
  1190	
  1191	
  1192	def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
  1193	    output_dir = tmp_path / "shared-linked-source-effective-change"
  1194	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1195	    _write_successful_candidate(output_dir)
  1196	    _write_ui_pair(
  1197	        output_dir,
  1198	        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
  1199	        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
  1200	    )
   145	
   146	    assessment = assess_live_output_dir(
   147	        tmp_path,
   148	        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
   149	    )
   150	
   151	    assert assessment["passed"] is False
   152	    assert [issue["check"] for issue in assessment["issues"]] == ["gates"]
   153	    assert "queue_validate_ok" in assessment["issues"][0]["detail"]
   154	
   155	
   156	def test_message_prose_never_affects_score(tmp_path: Path) -> None:
   157	    """G0-T2: scoring is structured-only — identical structured records score
   158	    identically no matter what prose the message carries.
   159	
   160	    The same record (an edit landed, candidate produced, gates passed) must
   161	    pass both with a grounded message and with message prose that the old
   162	    deterministic matcher misread as a contradiction ("unchanged" parts of the
   163	    graph).  The reverse also holds: a record with no landed edit and failed
   164	    gates fails identically whether the message admits it or falsely claims
   165	    success.
   166	    """
   167	    base = {
   168	        "ok": True,
   169	        "graph_unchanged": False,
   170	        "candidate_graph": {"1": {"class_type": "KSampler"}},
   171	        "outcome": {"kind": "candidate"},
   172	        "change_details": {"landed_operation_count": 1},
   173	        "gates": {
   174	            "ir_validate_ok": True,
   175	            "lower_ok": True,
   176	            "python_load_ok": True,
   177	            "queue_validate_ok": True,
   178	            "state_match_ok": True,
   179	            "ui_emit_ok": True,
   180	            "ui_fidelity_ok": True,
   181	            "ui_load_safe_ok": True,
   182	        },
   183	    }
   184	    scenario = {"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}}
   185	
   186	    passing_messages = (
   187	        "Applied 1 edit.",
   188	        "Updated the KSampler; the other nodes are unchanged.",
   189	        "Node connections are unchanged; only the seed changed.",
   190	        "I have not applied any further changes; this edit is complete.",
   191	    )
   192	    scores = []
   193	    for index, message in enumerate(passing_messages):
   194	        run_dir = tmp_path / f"pass-{index}"
   195	        run_dir.mkdir(parents=True, exist_ok=True)
   196	        (run_dir / "response.json").write_text(
   197	            json.dumps({**base, "message": message}),
   198	            encoding="utf-8",
   199	        )
   200	        # G0R: the residual implementation_result prose gate is removed — the
   201	        # same "unchanged"-wording message in implementation_result.json must
   202	        # not affect scoring either.
   203	        (run_dir / "implementation_result.json").write_text(
   204	            json.dumps({"message": message}),
   205	            encoding="utf-8",
   206	        )
   207	        assessment = assess_live_output_dir(run_dir, scenario=scenario)
   208	        scores.append((assessment["passed"], assessment["error_count"]))
   209	
   210	    assert scores == [(True, 0)] * len(passing_messages), scores
   211	    assert all(
   212	        issue["check"] not in {"message_artifact", "implementation_result"}
   213	        for index in range(len(passing_messages))
   214	        for issue in assess_live_output_dir(tmp_path / f"pass-{index}", scenario=scenario)["issues"]
   215	    )
   216	
   217	    failing_base = {
   218	        "ok": True,
   219	        "graph_unchanged": True,
   220	        "no_candidate_reason": "no_changes",
   221	        "outcome": {"kind": "noop"},
   222	        "change_details": {"landed_operation_count": 0},
   223	        "gates": {
   224	            "ir_validate_ok": False,
   225	            "lower_ok": False,
   226	            "python_load_ok": False,
   227	            "queue_validate_ok": False,
   228	            "state_match_ok": True,
   229	            "ui_emit_ok": False,
   230	            "ui_fidelity_ok": False,
   231	            "ui_load_safe_ok": False,
   232	        },
   233	    }
   234	    failing_messages = (
   235	        "No changes were needed.",
   236	        "Applied 3 edits and the candidate is ready to apply.",
   237	        "Validation passed; everything landed.",
   238	    )
   239	    failing_scores = []
   240	    for index, message in enumerate(failing_messages):
   241	        run_dir = tmp_path / f"fail-{index}"
   242	        run_dir.mkdir(parents=True, exist_ok=True)
   243	        (run_dir / "response.json").write_text(
   244	            json.dumps({**failing_base, "message": message}),
   245	            encoding="utf-8",
   246	        )
   247	        assessment = assess_live_output_dir(run_dir, scenario=scenario)
   248	        failing_scores.append((assessment["passed"], assessment["error_count"]))
   249	
   250	    # Four structured errors: graph_changed, no_candidate_reason,
   251	    # outcome_kind, and gates — identical for every message wording.
   252	    assert failing_scores == [(False, 4)] * len(failing_messages), failing_scores
   253	
   254	
   255	def test_implementation_result_unchanged_prose_does_not_gate_scoring(tmp_path: Path) -> None:
   256	    """G0R counterexample: an implementation_result message saying other
   257	    nodes are unchanged must NOT affect scoring when the structured record
   258	    proves an edit landed.
   259	
   260	    The residual ``"unchanged"`` substring gate (assessor.py:774 pre-G0R)
   261	    turned this into an error-severity ``implementation_result`` issue; it is
   262	    gone — prose never gates scoring.
   263	    """
   264	    response = {
   265	        "ok": True,
   266	        "graph_unchanged": False,
   267	        "candidate_graph": {"1": {"class_type": "KSampler"}},
   268	        "outcome": {"kind": "candidate"},
   269	        "change_details": {"landed_operation_count": 1},
   270	        "gates": {
   271	            "ir_validate_ok": True,
   272	            "lower_ok": True,
   273	            "python_load_ok": True,
   274	            "queue_validate_ok": True,
   275	            "state_match_ok": True,
   276	            "ui_emit_ok": True,
   277	            "ui_fidelity_ok": True,
   278	            "ui_load_safe_ok": True,
   279	        },
   280	    }
   281	    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")
   282	    (tmp_path / "implementation_result.json").write_text(
   283	        json.dumps({"message": "Updated the sampler; other nodes are unchanged."}),
   284	        encoding="utf-8",
   285	    )
   286	
   287	    assessment = assess_live_output_dir(
   288	        tmp_path,
   289	        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
   290	    )
   291	
   292	    assert assessment["passed"] is True, assessment["issues"]
   293	    assert not [
   294	        issue for issue in assessment["issues"] if issue["check"] == "implementation_result"
   295	    ]
   250	        ctx = _make_narrative_context(
   251	            outcome={
   252	                "internal_kind": "clarify",
   253	                "public_kind": "clarify",
   254	                "clarification_question": "Which node should I edit?",
   255	            },
   256	        )
   257	        assert ctx.clarification_question == "Which node should I edit?"
   258	
   259	
   260	# ── Fact-grounded synthesis prompt (G0-T2) ──────────────────────────────────
   261	
   262	
   263	class TestNarratorPromptFactGrounded:
   264	    def test_system_prompt_requires_describing_structured_facts(self) -> None:
   265	        from vibecomfy.comfy_nodes.agent.edit import _NARRATOR_SYSTEM_PROMPT
   266	        prompt = _NARRATOR_SYSTEM_PROMPT
   267	        assert "graph_unchanged" in prompt
   268	        assert "outcome.kind" in prompt
   269	        assert "landed_operation_count" in prompt
   270	        assert "validation.passed" in prompt
   271	        assert "Never claim an edit you did not land" in prompt
   272	        assert "describe exactly those facts" in prompt
   273	
   274	    def test_user_message_feeds_the_structured_outcome(self) -> None:
   275	        """The narrator request embeds graph_unchanged, outcome.kind, and
   276	        landed_operation_count so the agent writes the message FROM the facts."""
   277	        ctx = _make_narrative_context(
   278	            outcome={
   279	                "kind": "candidate",
   280	                "internal_kind": "edit",
   281	                "public_kind": "candidate",
   282	                "clarification_question": "",
   283	            },
   284	            change={
   285	                "graph_changed": True,
   286	                "graph_unchanged": False,
   287	                "landed_operation_count": 2,
   288	            },
   289	            validation={"passed": True},
   290	        )
   291	        messages = _build_narrator_messages(ctx)
   292	        content = messages[1]["content"]
   293	        assert '"graph_unchanged": false' in content
   294	        assert '"kind": "candidate"' in content
   295	        assert '"landed_operation_count": 2' in content
   296	        assert '"passed": true' in content
   297	
   298	
   299	# ── Deterministic fallback ──────────────────────────────────────────────────
   300	
   301	
   302	class TestDeterministicNarrativeFallback:
   303	    def test_edit_outcome_produces_humanized_message(self, tmp_path: Path) -> None:
   304	        state = _make_state(
   305	            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
   306	            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
   307	            batch_field_changes=(
   308	                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
   309	            ),
   310	            batch_exit_mode="done",
   900	            narrative_response_path=Path("narrative_response.json"),
   901	            narrative_validation_path=Path("narrative_validation.json"),
   902	            artifacts={},
   903	        )
   904	        state.turn_dir.mkdir(parents=True, exist_ok=True)
   905	        context = TurnContext(session_id="artifacts-check", turn_id="0001")
   906	        for gate_name in context.gate_results:
   907	            context.set_gate(gate_name, True)
   908	
   909	        _narrate_final_message(
   910	            state,
   911	            context,
   912	            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
   913	            public_outcome="candidate",
   914	        )
   915	
   916	        assert (state.turn_dir / "narrative_context.json").is_file()
   917	        assert (state.turn_dir / "narrative_validation.json").is_file()
   918	
   919	    def test_artifact_write_failure_preserves_selected_agent_message(
   920	        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
   921	    ) -> None:
   922	        """G0R: a raise from _write_narrative_artifacts must not replace the
   923	        already-selected narrator message with the deterministic fallback.
   924	
   925	        The write call sits inside the outer fallback catch; without the
   926	        best-effort guard, a raising writer would discard the selected agent
   927	        message and ship the deterministic fallback instead.
   928	        """
   929	        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
   930	            return {"json": {"message": "Changed the sampler seed to 42."}}
   931	
   932	        monkeypatch.setattr(
   933	            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
   934	            _fake_run_model_turn,
   935	        )
   936	
   937	        def _failing_artifact_write(*args: Any, **kwargs: Any) -> None:
   938	            raise RuntimeError("artifact write exploded")
   939	
   940	        monkeypatch.setattr(
   941	            "vibecomfy.comfy_nodes.agent.edit._write_narrative_artifacts",
   942	            _failing_artifact_write,
   943	        )
   944	
   945	        state = _make_state(
   946	            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
   947	            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
   948	            batch_field_changes=(
   949	                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
   950	            ),
   951	            batch_exit_mode="done",
   952	            session_dir=tmp_path / "session",
   953	            turn_dir=tmp_path / "turns" / "0001",
   954	            narrative_context_path=Path("narrative_context.json"),
   955	            narrative_request_path=Path("narrative_request.json"),
   956	            narrative_response_path=Path("narrative_response.json"),
   957	            narrative_validation_path=Path("narrative_validation.json"),
   958	            artifacts={},
   959	        )
   960	        state.turn_dir.mkdir(parents=True, exist_ok=True)
   961	        context = TurnContext(session_id="artifact-write-fail", turn_id="0001")
   962	        for gate_name in context.gate_results:
   963	            context.set_gate(gate_name, True)
   964	
   965	        message = _narrate_final_message(
   966	            state,
   967	            context,
   968	            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
   969	            public_outcome="candidate",
   970	        )
   971	
   972	        # The selected agent message ships unchanged — never the fallback.
   973	        assert message == "Changed the sampler seed to 42."
   974	
   975	
   976	# ── _assemble_narrative_context integration ────────────────────────────────
   977	
   978	
   979	class TestAssembleNarrativeContext:
   980	    def test_builds_context_from_state_and_context(self, tmp_path: Path) -> None:
   981	        state = _make_state(
   982	            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
   983	            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
   984	            batch_field_changes=(
   985	                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
   986	            ),
   987	            batch_exit_mode="done",
   988	            task="change filename",
   989	            route="openrouter",
   990	            session_dir=tmp_path / "session",
   232	
   233	    _safe_write("narrative_context.json", narrative_context.payload)
   234	    _safe_write("narrative_validation.json", validation)
   235	
   236	    if request_messages is not None:
   237	        _safe_write("narrator_request.json", request_messages)
   238	
   239	    if llm_response is not None:
   240	        _safe_write("narrator_response.json", llm_response)
   241	
   242	
   243	# ── Prompt construction helpers ───────────────────────────────────────────
   244	
   245	_NARRATOR_SYSTEM_PROMPT = (
   246	    "You are a concise, honest narrative synthesizer for a visual programming "
   247	    "agent. The agent just completed a graph-editing turn. Your job is to "
   248	    "produce a single user-facing sentence that accurately describes what "
   249	    "happened.\n\n"
   250	    "Rules:\n"
   251	    "- Respond with exactly one JSON object: {\"message\": \"...\"}\n"
   252	    "- The message must be one natural-language sentence ending in punctuation.\n"
   253	    "- Never mention internal agent machinery (gate names, scoring, batch REPL, "
   254	    "field-level diffs). Describe the validation outcome truthfully — "
   255	    "validation.passed below is user-facing and must be reported as-is.\n"
   256	    "- If the outcome is a clarification question, the message should ask it "
   257	    "politely.\n"
   258	    "- If the outcome is a failure, be honest but helpful about what went wrong.\n"
   259	    "- If edits landed, describe what changed in plain language.\n"
   260	    "- If nothing changed, say so honestly without inventing edits.\n"
   261	    "- Never include markdown, code fences, or structured data in the message.\n"
   262	    "- Keep the message under 300 characters.\n"
   263	    "You MUST state what happened per these structured facts and describe "
   264	    "exactly those facts:\n"
   265	    "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
   266	    "  - outcome.kind: the public outcome kind (e.g. candidate, noop, clarify, failure).\n"
   267	    "  - change.landed_operation_count: how many operations actually landed.\n"
   268	    "  - validation.passed: whether post-edit validation passed.\n"
   269	    "Never claim an edit you did not land: when graph_unchanged is true or "
   270	    "landed_operation_count is 0, you MUST NOT say the graph was edited, "
   271	    "applied, updated, connected, or changed. Never claim validation passed "
   272	    "when validation.passed is false. The message must be consistent with "
   273	    "every one of these fields."
   274	)
   275	
   276	
   277	def _build_narrator_messages(
   278	    narrative_context: NarrativeContext,
   279	    *,
   280	    raw_executor_message: str = "",
   281	    fallback_message: str = "",
   282	) -> list[dict[str, str]]:
   400	            failure=failure,
   401	            narrative_context=narrative_context,
   402	        )
   403	
   404	        llm_request: list[dict[str, str]] | None = None
   405	        llm_response: dict[str, Any] | None = None
   406	        llm_message: str | None = None
   407	        fallback_reason: str | None = None
   408	
   409	        try:
   410	            raw_executor_message = " ".join((state.raw_executor_message or "").split())
   411	            llm_request = _build_narrator_messages(
   412	                narrative_context,
   413	                raw_executor_message=raw_executor_message,
   414	                fallback_message=fallback_message,
   415	            )
   416	            llm_message, llm_response = _call_narrator_llm(
   417	                narrative_context,
   418	                llm_request,
   419	                route=route,
   420	                model=model,
   421	            )
   422	        except ProviderError as exc:
   423	            LOGGER.warning("Narrator provider error (%s), falling back: %s", type(exc).__name__, exc)
   424	            fallback_reason = "provider_failure"
   425	        except MalformedModelJSON as exc:
   426	            LOGGER.warning("Narrator malformed response, falling back: %s", exc)
   427	            fallback_reason = "malformed_response"
   428	        except TimeoutError:
   429	            LOGGER.warning("Narrator LLM call timed out, falling back.")
   430	            fallback_reason = "provider_failure"
   431	        except Exception as exc:
   432	            LOGGER.warning(
   433	                "Narrator LLM unexpected error (%s), falling back: %s",
   434	                type(exc).__name__,
   435	                exc,
   436	            )
   437	            fallback_reason = "provider_failure"
   438	
   439	        # ── Select the message: the agent's own message ALWAYS ships. ──
   440	        # There is no prose gate and no discard-and-replace: when the LLM
   441	        # narrator produced a message, that message IS the final message.
   442	        # The deterministic fallback ships only when no agent message exists.
   443	        if llm_message is not None and fallback_reason is None:
   444	            selected_source = "narrator"
   445	            selected_message = llm_message
   446	        else:
   447	            selected_source = "fallback"
   448	            selected_message = fallback_message
   449	            fallback_reason = fallback_reason or "no_narrator_message"
   450	
   451	        validation: dict[str, Any] = {
   452	            "ok": True,
   453	            "message": selected_message,
   454	            "issues": [],
   455	            "selected_source": selected_source,
   456	            "fallback_reason": fallback_reason,
   457	        }
   458	        # Artifact persistence is best-effort: even if the writer itself
   459	        # raises (not just per-file write errors), the already-selected agent
   460	        # message must still ship.  The outer fallback catch below must never
   461	        # replace a selected narrator message with the deterministic fallback.
   462	        try:
   463	            _write_narrative_artifacts(
   464	                state,
   465	                narrative_context,
   466	                validation,
   467	                request_messages=llm_request,
   468	                llm_response=llm_response,
   469	            )
   470	        except Exception as exc:  # noqa: BLE001 - artifacts are presentation-only
   471	            LOGGER.warning(
   472	                "Narrative artifact write raised for turn %s (best-effort; selected message preserved): %s",
   473	                getattr(state, "turn_dir", None),
   474	                exc,
   475	            )
   476	        return selected_message
   477	
   478	    except Exception as exc:
   479	        LOGGER.warning(
   480	            "Narrator unrecoverable error (%s), returning raw fallback: %s",
   481	            type(exc).__name__,
   482	            exc,
   483	        )
   484	        return _deterministic_narrative_fallback(
   485	            state,
   486	            outcome=outcome,
   487	            failure=failure,
   488	            narrative_context=None,
   489	            fallback_reason="narrator_unrecoverable_error",
   490	        )
   491	
   492	
   493	__all__ = (
   494	    "NarrativeContext",
   495	    "_NARRATOR_DEFAULT_MODEL",

exec
/bin/zsh -lc "nl -ba tests/test_live_agentic_harness_guard_contract.py | sed -n '850,1195p'
nl -ba tests/test_live_agentic_harness_guard_contract.py | sed -n '519,692p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   850	
   851	    assert verdict["live_agentic_success"] is False
   852	    error_checks = {
   853	        issue["check"]
   854	        for issue in verdict["assessment"]["issues"]
   855	        if issue["severity"] == "error"
   856	    }
   857	    assert "gates" in error_checks
   858	    assert "message_artifact" not in error_checks
   859	
   860	
   861	# ── G0R: structural expected-edit guard (landed_operation_count) ──────────
   862	#
   863	# A claimed edit (graph_unchanged is False) must be backed by a positive
   864	# integer change_details.landed_operation_count.  Missing, malformed, or
   865	# zero counts fail closed; accepted grounded refusals and canonical
   866	# non-edit routes (read from response.route — never from self-declared
   867	# outcome/no_candidate_reason labels) are exempt (they are scored by
   868	# their own checks, including the route/graph consistency check).
   869	
   870	
   871	@pytest.mark.parametrize(
   872	    "change_details",
   873	    [
   874	        pytest.param(None, id="missing-change-details"),
   875	        pytest.param({}, id="missing-landed-count"),
   876	        pytest.param({"landed_operation_count": 0}, id="zero-landed-count"),
   877	        pytest.param({"landed_operation_count": -1}, id="negative-landed-count"),
   878	        pytest.param({"landed_operation_count": "1"}, id="string-landed-count"),
   879	        pytest.param({"landed_operation_count": 1.5}, id="float-landed-count"),
   880	        pytest.param({"landed_operation_count": True}, id="bool-landed-count"),
   881	    ],
   882	)
   883	def test_agentic_guard_expected_edit_requires_positive_landed_count(
   884	    tmp_path: Path,
   885	    change_details: dict[str, object] | None,
   886	    request: pytest.FixtureRequest,
   887	) -> None:
   888	    """G0R negative control: graph_unchanged=false with a missing, malformed,
   889	    or zero landed_operation_count fails closed structurally."""
   890	    output_dir = tmp_path / f"landed-count-{request.node.callspec.id}"
   891	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   892	    response = {
   893	        "ok": True,
   894	        "graph_unchanged": False,
   895	        "outcome": {"kind": "candidate"},
   896	        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
   897	        "gates": _ALL_GATES_PASS,
   898	    }
   899	    if change_details is not None:
   900	        response["change_details"] = change_details
   901	    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
   902	
   903	    scenario = {
   904	        "id": f"landed-count-{change_details!r}",
   905	        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
   906	    }
   907	    verdict = guard_output_dir(output_dir, scenario=scenario)
   908	
   909	    assert verdict["live_agentic_success"] is False
   910	    error_checks = {
   911	        issue["check"]
   912	        for issue in verdict["assessment"]["issues"]
   913	        if issue["severity"] == "error"
   914	    }
   915	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
   916	
   917	
   918	def test_agentic_guard_expected_edit_with_positive_landed_count_passes(
   919	    tmp_path: Path,
   920	) -> None:
   921	    """G0R positive control: graph_unchanged=false with a positive integer
   922	    landed_operation_count passes the structural guard."""
   923	    output_dir = tmp_path / "landed-count-positive"
   924	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   925	    (output_dir / "response.json").write_text(
   926	        json.dumps(
   927	            {
   928	                "ok": True,
   929	                "graph_unchanged": False,
   930	                "outcome": {"kind": "candidate"},
   931	                "candidate_graph": {"nodes": [{"id": 1}], "links": []},
   932	                "change_details": {"landed_operation_count": 1},
   933	                "gates": _ALL_GATES_PASS,
   934	            }
   935	        ),
   936	        encoding="utf-8",
   937	    )
   938	
   939	    verdict = guard_output_dir(
   940	        output_dir,
   941	        scenario={
   942	            "id": "landed-count-positive",
   943	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
   944	        },
   945	    )
   946	
   947	    assert verdict["live_agentic_success"] is True
   948	    assert verdict["assessment"]["passed"] is True
   949	    assert not [
   950	        issue
   951	        for issue in verdict["assessment"]["issues"]
   952	        if issue["check"] == "landed_operation_count"
   953	    ]
   954	
   955	
   956	def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
   957	    tmp_path: Path,
   958	) -> None:
   959	    """G0R: an accepted grounded refusal (graph_unchanged=true, allowed
   960	    outcome kind) is exempt from the landed_operation_count requirement."""
   961	    output_dir = tmp_path / "landed-count-refusal-exempt"
   962	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   963	    (output_dir / "response.json").write_text(
   964	        json.dumps(
   965	            {
   966	                "ok": True,
   967	                "graph_unchanged": True,
   968	                "no_candidate_reason": "no_changes",
   969	                "outcome": {"kind": "requires_custom_nodes"},
   970	                "message": "No schema-backed replacement node was found.",
   971	            }
   972	        ),
   973	        encoding="utf-8",
   974	    )
   975	
   976	    verdict = guard_output_dir(
   977	        output_dir,
   978	        scenario={
   979	            "id": "landed-count-refusal-exempt",
   980	            "assessment": {
   981	                "expect_graph_changed": True,
   982	                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
   983	            },
   984	        },
   985	    )
   986	
   987	    assert verdict["live_agentic_success"] is True
   988	    assert verdict["assessment"]["passed"] is True
   989	    assert {issue["check"] for issue in verdict["assessment"]["issues"]} == {"safe_refusal"}
   990	    assert not [
   991	        issue
   992	        for issue in verdict["assessment"]["issues"]
   993	        if issue["check"] == "landed_operation_count"
   994	    ]
   995	
   996	
   997	def test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify(tmp_path: Path) -> None:
   998	    """G0R negative control: an edit-route envelope (route=revise) with
   999	    graph_unchanged=false, no landed count, self-labeling outcome.kind=clarify
  1000	    must fail closed — self-declared outcome labels cannot buy an exemption
  1001	    from the landed_operation_count guard."""
  1002	    output_dir = tmp_path / "landed-count-edit-route-clarify-relabel"
  1003	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1004	    (output_dir / "response.json").write_text(
  1005	        json.dumps(
  1006	            {
  1007	                "ok": True,
  1008	                "route": "revise",
  1009	                "graph_unchanged": False,
  1010	                "outcome": {"kind": "clarify"},
  1011	                "message": "Which node should I edit next?",
  1012	            }
  1013	        ),
  1014	        encoding="utf-8",
  1015	    )
  1016	
  1017	    verdict = guard_output_dir(
  1018	        output_dir,
  1019	        scenario={
  1020	            "id": "landed-count-edit-route-clarify-relabel",
  1021	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1022	        },
  1023	    )
  1024	
  1025	    assert verdict["live_agentic_success"] is False
  1026	    error_checks = {
  1027	        issue["check"]
  1028	        for issue in verdict["assessment"]["issues"]
  1029	        if issue["severity"] == "error"
  1030	    }
  1031	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
  1032	
  1033	
  1034	def test_agentic_guard_rejects_route_not_applyable_without_landed_count(tmp_path: Path) -> None:
  1035	    """G0R negative control: graph_unchanged=false with
  1036	    no_candidate_reason=route_not_applyable and no landed count must fail
  1037	    closed — a self-declared no-candidate reason cannot bypass the guard when
  1038	    no canonical non-edit route backs it."""
  1039	    output_dir = tmp_path / "landed-count-route-not-applyable"
  1040	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1041	    (output_dir / "response.json").write_text(
  1042	        json.dumps(
  1043	            {
  1044	                "ok": True,
  1045	                "graph_unchanged": False,
  1046	                "no_candidate_reason": "route_not_applyable",
  1047	                "message": "This request is not applicable to the current graph.",
  1048	            }
  1049	        ),
  1050	        encoding="utf-8",
  1051	    )
  1052	
  1053	    verdict = guard_output_dir(
  1054	        output_dir,
  1055	        scenario={
  1056	            "id": "landed-count-route-not-applyable",
  1057	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1058	        },
  1059	    )
  1060	
  1061	    assert verdict["live_agentic_success"] is False
  1062	    error_checks = {
  1063	        issue["check"]
  1064	        for issue in verdict["assessment"]["issues"]
  1065	        if issue["severity"] == "error"
  1066	    }
  1067	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
  1068	
  1069	
  1070	def test_agentic_guard_rejects_failure_outcome_without_landed_count(tmp_path: Path) -> None:
  1071	    """G0R negative control: failure outcomes cannot bypass all structured
  1072	    checks — an edit-route envelope with outcome.kind=failure,
  1073	    graph_unchanged=false and no landed count still fails the
  1074	    landed_operation_count guard."""
  1075	    output_dir = tmp_path / "landed-count-failure-outcome"
  1076	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1077	    (output_dir / "response.json").write_text(
  1078	        json.dumps(
  1079	            {
  1080	                "ok": True,
  1081	                "route": "revise",
  1082	                "graph_unchanged": False,
  1083	                "outcome": {"kind": "failure"},
  1084	                "message": "The edit could not be completed.",
  1085	            }
  1086	        ),
  1087	        encoding="utf-8",
  1088	    )
  1089	
  1090	    verdict = guard_output_dir(
  1091	        output_dir,
  1092	        scenario={
  1093	            "id": "landed-count-failure-outcome",
  1094	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1095	        },
  1096	    )
  1097	
  1098	    assert verdict["live_agentic_success"] is False
  1099	    error_checks = {
  1100	        issue["check"]
  1101	        for issue in verdict["assessment"]["issues"]
  1102	        if issue["severity"] == "error"
  1103	    }
  1104	    assert "landed_operation_count" in error_checks, verdict["assessment"]["issues"]
  1105	
  1106	
  1107	def test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph(
  1108	    tmp_path: Path,
  1109	) -> None:
  1110	    """G0R positive control: a canonical non-edit route (route=respond) with
  1111	    graph_unchanged=true and an authorized refusal outcome kind is still
  1112	    exempt — the route-aware exemption must not over-correct truthful non-edit
  1113	    responses."""
  1114	    output_dir = tmp_path / "landed-count-genuine-non-edit-route-exempt"
  1115	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1116	    (output_dir / "response.json").write_text(
  1117	        json.dumps(
  1118	            {
  1119	                "ok": True,
  1120	                "route": "respond",
  1121	                "graph_unchanged": True,
  1122	                "no_candidate_reason": "route_not_applyable",
  1123	                "outcome": {"kind": "respond"},
  1124	                "message": "I answered directly; no graph change was needed.",
  1125	            }
  1126	        ),
  1127	        encoding="utf-8",
  1128	    )
  1129	
  1130	    verdict = guard_output_dir(
  1131	        output_dir,
  1132	        scenario={
  1133	            "id": "landed-count-genuine-non-edit-route-exempt",
  1134	            "assessment": {
  1135	                "expect_graph_changed": True,
  1136	                "allow_safe_refusal_outcome_kinds": ["respond", "clarify"],
  1137	                "skip_intent_judge": True,
  1138	            },
  1139	        },
  1140	    )
  1141	
  1142	    assert verdict["live_agentic_success"] is True
  1143	    assert verdict["assessment"]["passed"] is True
  1144	    checks = {issue["check"] for issue in verdict["assessment"]["issues"]}
  1145	    assert "safe_refusal" in checks
  1146	    assert "landed_operation_count" not in checks
  1147	    assert "route_graph_consistency" not in checks
  1148	
  1149	
  1150	def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
  1151	    tmp_path: Path,
  1152	) -> None:
  1153	    """G0R control: a canonical non-edit route (route=respond) claiming
  1154	    graph_unchanged=false is exempt from the landed-count guard but still
  1155	    fails through its own structured checks (route/graph consistency,
  1156	    no_candidate_reason, outcome_kind) when an edit was expected."""
  1157	    output_dir = tmp_path / "landed-count-noop-not-exempt-from-noop-check"
  1158	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1159	    (output_dir / "response.json").write_text(
  1160	        json.dumps(
  1161	            {
  1162	                "ok": True,
  1163	                "route": "respond",
  1164	                "graph_unchanged": False,
  1165	                "no_candidate_reason": "no_changes",
  1166	                "outcome": {"kind": "noop"},
  1167	            }
  1168	        ),
  1169	        encoding="utf-8",
  1170	    )
  1171	
  1172	    verdict = guard_output_dir(
  1173	        output_dir,
  1174	        scenario={
  1175	            "id": "landed-count-noop-check",
  1176	            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
  1177	        },
  1178	    )
  1179	
  1180	    assert verdict["live_agentic_success"] is False
  1181	    error_checks = {
  1182	        issue["check"]
  1183	        for issue in verdict["assessment"]["issues"]
  1184	        if issue["severity"] == "error"
  1185	    }
  1186	    assert "route_graph_consistency" in error_checks
  1187	    assert "no_candidate_reason" in error_checks
  1188	    assert "outcome_kind" in error_checks
  1189	    assert "landed_operation_count" not in error_checks
  1190	
  1191	
  1192	def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
  1193	    output_dir = tmp_path / "shared-linked-source-effective-change"
  1194	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
  1195	    _write_successful_candidate(output_dir)
   519	# (scenario_id, response) — prose excerpts are grounded in the persisted
   520	# response.json artifacts of the recorded matcher-only failures.
   521	_MATCHER_ONLY_COUNTEREXAMPLES: tuple[tuple[str, dict[str, object]], ...] = (
   522	    (
   523	        "3d-generates-a-3d-mesh-from",
   524	        {
   525	            "message": (
   526	                "Done — I tuned the mesh-generation path to reduce floating bits and noise. "
   527	                "Concretely, `KSampler` steps went from 20 to 50 so the sampler converges "
   528	                "further before `VAEDecodeHunyuan3D` extracts the mesh; node connections and "
   529	                "other widgets are unchanged (structure validated)."
   530	            ),
   531	            "graph_unchanged": False,
   532	            "outcome": {"kind": "candidate"},
   533	            "change_details": {"landed_operation_count": 1},
   534	            "gates": _ALL_GATES_PASS,
   535	        },
   536	    ),
   537	    (
   538	        "audio-acestep-audio-generation-workflow-2a31ec",
   539	        {
   540	            "message": (
   541	                "The AceStepSFTGenerate node now uses acestep-sft-v2.safetensors as its base "
   542	                "model checkpoint (widget_0), replacing acestep-v15.safetensors. The rest of "
   543	                "the SFT chain (audio input, prompt, LoRA, and save) is preserved unchanged."
   544	            ),
   545	            "graph_unchanged": False,
   546	            "outcome": {"kind": "candidate"},
   547	            "change_details": {"landed_operation_count": 1},
   548	            "gates": _ALL_GATES_PASS,
   549	        },
   550	    ),
   551	    (
   552	        "image-sd3-image-generation-with-controlnet-19d221",
   553	        {
   554	            "message": (
   555	                "I lowered the ControlNet influence to give your text prompt the upper hand: "
   556	                "the `strength` widget on `ACN_AdvancedControlNetApply` (node 60) is now 0.5, "
   557	                "down from 0.6, while the tile ControlNet loader and its start/end percent "
   558	                "(0 / 0.75) stay unchanged."
   559	            ),
   560	            "graph_unchanged": False,
   561	            "outcome": {"kind": "candidate"},
   562	            "change_details": {"landed_operation_count": 1},
   563	            "gates": _ALL_GATES_PASS,
   564	        },
   565	    ),
   566	    (
   567	        "video-generates-a-video-from-a",
   568	        {
   569	            "message": (
   570	                "Done — I set the video output to 24 fps by updating the `frame_rate` widget "
   571	                "on VHS_VideoCombine from 15 to 24. No other nodes were touched; the "
   572	                "`Modelscopet2v` and `CR Prompt Text` nodes are unchanged."
   573	            ),
   574	            "graph_unchanged": False,
   575	            "outcome": {"kind": "candidate"},
   576	            "change_details": {"landed_operation_count": 1},
   577	            "gates": _ALL_GATES_PASS,
   578	        },
   579	    ),
   580	    (
   581	        "video-image-to-video-conversion-with-moonvalley-d7853c",
   582	        {
   583	            "message": (
   584	                "Updated MoonvalleyImg2VideoNode so the output videos are 5.0 seconds long: "
   585	                "frame count (widget_3) 7 -> 120, frame rate (widget_6) 100 -> 24 fps. "
   586	                "LoadImage and SaveVideo are unchanged and still connected as before."
   587	            ),
   588	            "graph_unchanged": False,
   589	            "outcome": {"kind": "candidate"},
   590	            "change_details": {"landed_operation_count": 2},
   591	            "gates": _ALL_GATES_PASS,
   592	        },
   593	    ),
   594	    (
   595	        "multi-ai-video-upscaling-with-detail-daemon-sampler-673197",
   596	        {
   597	            "message": (
   598	                "Here's what your graph (29 nodes) actually does, and where the color-shift "
   599	                "suspects live. Pipeline as connected: 1. Conditioning — CLIPLoader encodes "
   600	                "the prompt via CLIPTextEncode; 2. Sampling chain — UNETLoader feeds three "
   601	                "BetaSamplingScheduler nodes. Since the SeedVR2 nodes are disconnected here, "
   602	                "I'd verify whether the upscaler is being used."
   603	            ),
   604	            "graph_unchanged": True,
   605	            "outcome": {"kind": "noop"},
   606	            "change_details": {"landed_operation_count": 0},
   607	            "gates": _ALL_GATES_PASS,
   608	        },
   609	    ),
   610	    (
   611	        "multi-audio-to-image-mel-band-roformer-workflow-b22937",
   612	        {
   613	            "message": (
   614	                "This graph is an audio-enhancement pipeline: load a WAV, process it with a "
   615	                "Mel-band separation model, then upscale the result. The sampler applies "
   616	                "MelBandRoFormer to do the core audio processing. Portability note: the "
   617	                "model loader isn't connected to the data flow; no changes were made."
   618	            ),
   619	            "graph_unchanged": True,
   620	            "outcome": {"kind": "noop"},
   621	            "change_details": {"landed_operation_count": 0},
   622	            "gates": _ALL_GATES_PASS,
   623	        },
   624	    ),
   625	    (
   626	        "video-hunyuan-video-text-to-video-generation-265847",
   627	        {
   628	            "message": (
   629	                "This is a Hunyuan Video T2V workflow: UNETLoader -> ModelSamplingSD3 -> "
   630	                "SamplerCustomAdvanced with euler / 20 steps / denoise=1, starting from "
   631	                "EmptyHunyuanLatentVideo (73 frames). There is a VAEDecode (node 8) that is "
   632	                "not connected to the save node; the animated WEBP is saved from "
   633	                "VAEDecodeTiled at 24 fps."
   634	            ),
   635	            "graph_unchanged": True,
   636	            "outcome": {"kind": "noop"},
   637	            "change_details": {"landed_operation_count": 0},
   638	            "gates": _ALL_GATES_PASS,
   639	        },
   640	    ),
   641	    (
   642	        "video-video-output-workflow-f855de",
   643	        {
   644	            "message": (
   645	                "This graph makes a low-resolution image, upscales it, decodes latents, and "
   646	                "writes the video directly. Likely causes of blur: both upscale stages are "
   647	                "toggled off, so the saved frames are the tiny base resolution. Note the "
   648	                "detail-enhancement edits I have not applied."
   649	            ),
   650	            "graph_unchanged": True,
   651	            "outcome": {"kind": "noop"},
   652	            "change_details": {"landed_operation_count": 0},
   653	            "gates": _ALL_GATES_PASS,
   654	        },
   655	    ),
   656	)
   657	
   658	
   659	@pytest.mark.parametrize(
   660	    ("scenario_id", "response"),
   661	    _MATCHER_ONLY_COUNTEREXAMPLES,
   662	    ids=[scenario_id for scenario_id, _ in _MATCHER_ONLY_COUNTEREXAMPLES],
   663	)
   664	def test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating(
   665	    tmp_path: Path,
   666	    scenario_id: str,
   667	    response: dict[str, object],
   668	) -> None:
   669	    """The nine matcher-only scenarios now pass: prose never gates scoring."""
   670	    output_dir = tmp_path / scenario_id
   671	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   672	    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
   673	
   674	    expect_edit = bool(response.get("graph_unchanged") is False)
   675	    scenario = {
   676	        "id": scenario_id,
   677	        "assessment": {
   678	            "expect_graph_changed": expect_edit,
   679	            "skip_intent_judge": True,
   680	        },
   681	    }
   682	    verdict = guard_output_dir(output_dir, scenario=scenario)
   683	
   684	    assert verdict["live_agentic_success"] is True, verdict["assessment"]["issues"]
   685	    assert verdict["score_class"] == "pass"
   686	    assert verdict["assessment"]["passed"] is True
   687	    assert all(
   688	        issue["check"] != "message_artifact"
   689	        for issue in verdict["assessment"]["issues"]
   690	    ), "prose must never produce an error-severity issue"
   691	
   692	

exec
/bin/zsh -lc "rg -n 'class AgentTurnResult|def to_dict|route:' vibecomfy/executor/contracts.py | head -80
nl -ba vibecomfy/executor/contracts.py | sed -n '1,240p'
rg -n '\"route\"\\s*:\\s*\"(revise|adapt|reorganise|clarify|respond|inspect|research|requires_custom_nodes)\"' tests -g '*.json' -g '*.py' | head -120
rg -n 'Literal\\[.*revise|VALID.*ROUTE|ROUTES|requires_custom_nodes|reorganise' vibecomfy/executor tests/live_agentic_harness | head -160" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
316:    route: str,
329:    if not route:
470:    route: str = ""
542:        if self.route:
565:    def to_dict(self) -> dict[str, Any]:
576:        if self.route:
613:        route: str = "",
635:        route: str = "",
735:    def to_dict(self) -> dict[str, Any]:
874:    def to_dict(self) -> dict[str, Any]:
939:    def to_dict(self) -> dict[str, Any]:
1040:    def to_dict(self) -> dict[str, Any]:
1177:    def to_dict(self) -> dict[str, Any]:
1336:    def to_dict(self) -> dict[str, Any]:
1379:    def to_dict(self) -> dict[str, Any]:
1515:    def to_dict(self) -> dict[str, Any]:
1610:    def to_dict(self) -> dict[str, Any]:
1670:    def to_dict(self) -> dict[str, Any]:
1744:    def to_dict(self) -> dict[str, Any]:
1810:    def to_dict(self) -> dict[str, Any]:
1917:    def to_dict(self) -> dict[str, Any]:
1980:    def to_dict(self) -> dict[str, Any]:
2074:    def to_dict(self) -> dict[str, Any]:
2136:    def to_dict(self) -> dict[str, Any]:
2204:    def to_dict(self) -> dict[str, Any]:
2219:class AgentTurnResult:
2227:    route: str
2256:    def to_dict(self) -> dict[str, Any]:
2287:            if plan.route and plan.route != route:
2342:    route: str,
2412:    def to_dict(self) -> dict[str, Any]:
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
    36	
    37	_NODE_TYPE_MARKER_RE = re.compile(
    38	    r"(?:class(?:_type|\s+type)?|node(?:\s+of)?(?:\s+type)?|of\s+type)\s*[:=]?\s*"
    39	    r"([A-Za-z_][A-Za-z0-9_.:-]*)",
    40	    re.IGNORECASE,
    41	)
    42	_NODE_TYPE_VERB_RE = re.compile(
    43	    r"\b(?:add|insert|create|restore|replace|remove|change|edit)\s+"
    44	    r"(?:(?:an?|the|new|another|some|one)\s+)*"
    45	    r"([A-Za-z_][A-Za-z0-9_.:-]*)\b",
    46	    re.IGNORECASE,
    47	)
    48	_NON_NODE_TYPE_TOKENS = frozenset({
    49	    "a", "an", "the", "node", "nodes", "class", "type", "of", "to",
    50	    "with", "for", "from", "into", "on", "in", "and", "or", "value",
    51	    "setting", "settings", "field", "fields", "widget", "widgets", "new",
    52	})
    53	_UI_ONLY_ANNOTATION_CLASS_TYPES = frozenset({
    54	    "annotation",
    55	    "annotationnode",
    56	    "comment",
    57	    "commentnode",
    58	    "markdown",
    59	    "markdownnote",
    60	    "markdownnotenode",
    61	    "note",
    62	    "notenode",
    63	    "workflowcomment",
    64	    "workflowmarkdown",
    65	    "workflownote",
    66	})
    67	
    68	
    69	def is_ui_only_annotation_class_type(class_type: Any) -> bool:
    70	    """Return whether a class name denotes a known no-dataflow UI annotation.
    71	
    72	    Keep this deliberately conservative: reroutes, primitives, groups, and
    73	    other frontend components can participate in dataflow or component
    74	    expansion and therefore are not skipped merely because they are UI nodes.
    75	    """
    76	    normalized = re.sub(r"[^a-z0-9]", "", str(class_type or "").casefold())
    77	    return normalized in _UI_ONLY_ANNOTATION_CLASS_TYPES
    78	
    79	
    80	def parse_target_node_type(change_goal: str) -> str:
    81	    """Extract a likely ComfyUI class-type token from a change goal.
    82	
    83	    Classifier metadata is intentionally best-effort.  The parser only uses
    84	    explicit node/type markers or an edit verb followed by a token, and returns
    85	    an empty string when the sentence is too ambiguous to bind safely.
    86	    """
    87	    if not isinstance(change_goal, str) or not change_goal.strip():
    88	        return ""
    89	
    90	    candidates: list[str] = []
    91	    marker = _NODE_TYPE_MARKER_RE.search(change_goal)
    92	    if marker:
    93	        candidates.append(marker.group(1))
    94	    verb = _NODE_TYPE_VERB_RE.search(change_goal)
    95	    if verb:
    96	        candidates.append(verb.group(1))
    97	
    98	    for candidate in candidates:
    99	        token = candidate.strip(".,;()[]{}\"'")
   100	        if token and token.casefold() not in _NON_NODE_TYPE_TOKENS:
   101	            return token
   102	    return ""
   103	
   104	
   105	def _freeze_jsonish(value: Any) -> Any:
   106	    if isinstance(value, Mapping):
   107	        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
   108	    if isinstance(value, (list, tuple)):
   109	        return tuple(_freeze_jsonish(v) for v in value)
   110	    return value
   111	
   112	
   113	def _thaw_jsonish(value: Any) -> Any:
   114	    if isinstance(value, Mapping):
   115	        return {str(k): _thaw_jsonish(v) for k, v in value.items()}
   116	    if isinstance(value, tuple):
   117	        return [_thaw_jsonish(v) for v in value]
   118	    return value
   119	
   120	
   121	_ADAPTATION_PLAN_FOLLOWUPS: tuple[str, ...] = (
   122	    "apply_bound_current_graph_edit_if_schema_sufficient",
   123	    "build_execution_plan_with_required_nodes_and_rewires",
   124	    "typed_refusal_or_clarification_if_authoring_surface_missing",
   125	)
   126	
   127	
   128	def _adaptation_plan_field(value: Any, key: str, default: Any = None) -> Any:
   129	    if isinstance(value, Mapping):
   130	        return value.get(key, default)
   131	    return getattr(value, key, default)
   132	
   133	
   134	def adaptation_plan_actionability(value: Any) -> tuple[str, str]:
   135	    """Return ``("actionable", "")`` or ``("non_actionable", reason)``.
   136	
   137	    Validation status alone is not enough. A structurally failed plan with
   138	    concrete edit operations can still describe a current-graph direct edit,
   139	    while a passing or unevaluated plan with no candidate graph, nodes, rewires,
   140	    or edit ops is still only evidence.
   141	    """
   142	
   143	    if value is None:
   144	        return "non_actionable", "missing_plan"
   145	    if not isinstance(value, Mapping) and not any(
   146	        hasattr(value, key)
   147	        for key in (
   148	            "candidate_graph",
   149	            "required_new_nodes",
   150	            "required_rewires",
   151	            "edit_ops",
   152	            "structural_validation",
   153	            "semantic_validation",
   154	        )
   155	    ):
   156	        return "non_actionable", "invalid_plan_shape"
   157	
   158	    explicit = _adaptation_plan_field(value, "actionability")
   159	    if explicit == "non_actionable":
   160	        reason = _adaptation_plan_field(value, "non_actionable_reason") or "explicitly_non_actionable"
   161	        return "non_actionable", str(reason)
   162	
   163	    candidate_graph = _adaptation_plan_field(value, "candidate_graph")
   164	    required_new_nodes = _adaptation_plan_field(value, "required_new_nodes") or ()
   165	    required_rewires = _adaptation_plan_field(value, "required_rewires") or ()
   166	    edit_ops = _adaptation_plan_field(value, "edit_ops") or ()
   167	    if candidate_graph or required_new_nodes or required_rewires or edit_ops:
   168	        return "actionable", ""
   169	
   170	    structural = _adaptation_plan_field(value, "structural_validation")
   171	    semantic = _adaptation_plan_field(value, "semantic_validation")
   172	    if structural == "fail":
   173	        return "non_actionable", "structural_validation_failed_without_concrete_edits"
   174	    if semantic == "fail":
   175	        return "non_actionable", "semantic_validation_failed_without_concrete_edits"
   176	    return "non_actionable", "no_concrete_adaptation_edits"
   177	
   178	
   179	def is_actionable_adaptation_plan(value: Any) -> bool:
   180	    return adaptation_plan_actionability(value)[0] == "actionable"
   181	
   182	
   183	def adaptation_plan_actionability_payload(value: Any) -> dict[str, Any]:
   184	    actionability, reason = adaptation_plan_actionability(value)
   185	    payload: dict[str, Any] = {"actionability": actionability}
   186	    if actionability != "actionable":
   187	        payload["non_actionable_reason"] = reason
   188	        payload["allowed_followups"] = list(_ADAPTATION_PLAN_FOLLOWUPS)
   189	    return payload
   190	
   191	
   192	def _safe_exception_message(exc: BaseException) -> str:
   193	    message = " ".join(str(exc).split())
   194	    if not message:
   195	        return ""
   196	    message = re.sub(
   197	        r"https?://[^\s]+",
   198	        lambda match: _sanitize_url_for_warning(match.group(0)),
   199	        message,
   200	    )
   201	    if len(message) > _WARNING_DETAIL_MAX_MESSAGE:
   202	        return message[: _WARNING_DETAIL_MAX_MESSAGE - 3].rstrip() + "..."
   203	    return message
   204	
   205	
   206	def _sanitize_url_for_warning(raw_url: str) -> str:
   207	    try:
   208	        parsed = urlsplit(raw_url)
   209	    except ValueError:
   210	        return "<url>"
   211	    query_pairs = []
   212	    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
   213	        if key.lower() in _SENSITIVE_QUERY_KEYS:
   214	            query_pairs.append((key, "<redacted>"))
   215	        else:
   216	            query_pairs.append((key, value))
   217	    return urlunsplit((
   218	        parsed.scheme,
   219	        parsed.netloc,
   220	        parsed.path,
   221	        urlencode(query_pairs),
   222	        "",
   223	    ))
   224	
   225	
   226	def warning_detail_from_exception(exc: BaseException) -> dict[str, str]:
   227	    """Return a compact, JSON-safe exception detail for research warnings."""
   228	    return {
   229	        "type": type(exc).__name__,
   230	        "message": _safe_exception_message(exc),
   231	    }
   232	
   233	
   234	# ── classify decision ────────────────────────────────────────────────────────
   235	
   236	# Canonical route vocabulary (SD1).  Empty string means "no route specified —
   237	# derive from legacy booleans".
   238	_ALLOWED_ROUTES = frozenset({
   239	    "",
   240	    "clarify",
tests/test_headless_harness_scenarios_contract.py:160:        response = {"ok": True, "route": "inspect", "reply": "schema ok"}
tests/test_reorganise_skill.py:142:            "route": "reorganise",
tests/test_reorganise_skill.py:341:            "route": "reorganise",
tests/test_reorganise_skill.py:402:                "route": "reorganise",
tests/test_agent_executor_response.py:35:        "route": "clarify",
tests/test_agent_executor_response.py:52:        "route": "clarify",
tests/test_agent_executor_response.py:69:        "route": "requires_custom_nodes",
tests/test_agent_executor_response.py:106:        "route": "clarify",
tests/test_agent_executor_response.py:190:        "route": "clarify",
tests/test_agent_executor_response.py:208:        "route": "respond",
tests/test_authority_receipts.py:92:        "route": "reorganise",
tests/test_authority_receipts.py:126:        "route": "reorganise",
tests/structural_harness/actors.py:2248:                "route": "inspect",
tests/test_headless_agent_artifacts.py:64:            "route": "adapt",
tests/test_headless_agent_artifacts.py:164:        response={"ok": True, "route": "adapt"},
tests/test_headless_agent_artifacts.py:180:    (turn_dir / "response.json").write_text('{"ok": true, "route": "inspect"}\n', encoding="utf-8")
tests/test_headless_agent_artifacts.py:192:            "route": "inspect",
tests/test_executor_contracts.py:671:                classification={"route": "revise", "task": "edit_graph"},
tests/test_executor_contracts.py:1220:                "route": "research",
tests/test_executor_contracts.py:1289:            "route": "revise",
tests/test_executor_contracts.py:1318:            "route": "reorganise",
tests/test_executor_contracts.py:1372:            "route": "inspect",
tests/test_executor_contracts.py:1390:            "route": "adapt",
tests/test_executor_contracts.py:1425:            "route": "adapt",
tests/test_executor_contracts.py:1479:            "route": "clarify",
tests/test_demo_factory_multinode.py:399:            "route": "clarify",
tests/test_routes_session_sanitization.py:63:            mock_run.return_value = MagicMock(to_dict=lambda: {"ok": True, "route": "respond"})
tests/test_routes_session_sanitization.py:66:                mock_write.return_value = {"ok": True, "route": "respond"}
tests/test_routes_session_sanitization.py:164:            mock_run.return_value = MagicMock(to_dict=lambda: {"ok": True, "route": "respond"})
tests/test_routes_session_sanitization.py:167:                mock_write.return_value = {"ok": True, "route": "respond"}
tests/test_routes_session_sanitization.py:185:            mock_run.return_value = MagicMock(to_dict=lambda: {"ok": True, "route": "respond"})
tests/test_routes_session_sanitization.py:188:                mock_write.return_value = {"ok": True, "route": "respond"}
tests/test_routes_session_sanitization.py:209:            mock_run.return_value = MagicMock(to_dict=lambda: {"ok": True, "route": "respond"})
tests/test_routes_session_sanitization.py:212:                mock_write.return_value = {"ok": True, "route": "respond"}
tests/test_routes_session_sanitization.py:228:            mock_run.return_value = MagicMock(to_dict=lambda: {"ok": True, "route": "respond"})
tests/test_routes_session_sanitization.py:231:                mock_write.return_value = {"ok": True, "route": "respond"}
tests/test_routes_session_sanitization.py:278:        response = {"ok": True, "route": "clarify", "reply": "Clarification needed"}
tests/test_routes_session_sanitization.py:317:            response={"ok": True, "route": "respond", "message": "Explanation."},
tests/test_comfy_nodes_agent_backend_spine.py:10591:        "route": "revise",
tests/test_comfy_nodes_agent_backend_spine.py:10638:        "route": "revise",
tests/test_comfy_nodes_agent_backend_spine.py:10693:        "route": "revise",
tests/test_comfy_nodes_agent_backend_spine.py:10757:        "route": "clarify",
tests/test_comfy_nodes_agent_backend_spine.py:10820:        "route": "clarify",
tests/test_comfy_nodes_agent_backend_spine.py:10875:        "route": "inspect",
tests/test_comfy_nodes_agent_backend_spine.py:10921:        "route": "inspect",
tests/test_comfy_nodes_agent_backend_spine.py:10980:        "route": "respond",
tests/test_comfy_nodes_agent_backend_spine.py:11048:        "route": "research",
tests/test_comfy_nodes_agent_backend_spine.py:11439:        {"route": "respond", "query": "First question", "reply": "First answer."},
tests/test_comfy_nodes_agent_backend_spine.py:11440:        {"route": "inspect", "query": "Second question", "reply": "Second answer."},
tests/test_comfy_nodes_agent_backend_spine.py:11441:        {"route": "research", "query": "Third question", "reply": "Third answer.",
tests/test_comfy_nodes_agent_backend_spine.py:11498:        "route": "respond",
tests/test_comfy_nodes_agent_backend_spine.py:11514:        "route": "respond",
tests/test_comfy_nodes_agent_backend_spine.py:11570:        "route": "clarify",
tests/test_comfy_nodes_agent_backend_spine.py:11616:        "route": "clarify",
tests/test_comfy_nodes_agent_backend_spine.py:11733:        "route": "requires_custom_nodes",
tests/test_comfy_nodes_agent_backend_spine.py:11789:        "route": "requires_custom_nodes",
tests/test_agent_executor_durable.py:35:        "route": "revise",
tests/test_agent_executor_durable.py:68:        "route": "inspect",
tests/test_agent_executor_durable.py:155:        "route": "inspect",
tests/test_agent_executor_durable.py:206:        "route": "inspect",
tests/test_agent_executor_durable.py:274:        "route": "research",
tests/test_agent_executor_durable.py:344:        "route": "inspect",
tests/test_comfy_nodes_agent_edit.py:4225:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:4307:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:4397:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:4476:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:4561:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5237:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5239:                "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5315:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5317:                "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5379:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5459:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5547:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5674:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5676:                "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:5793:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:5795:                "route": "revise",
tests/test_comfy_nodes_agent_edit.py:6554:            "route": "research",
tests/test_comfy_nodes_agent_edit.py:6628:            "route": "research",
tests/test_comfy_nodes_agent_edit.py:8182:            "route": "research",
tests/test_comfy_nodes_agent_edit.py:11014:            return {"ok": True, "route": "respond", "reply": "ok"}
tests/test_comfy_nodes_agent_edit.py:11042:            return {"ok": True, "route": "respond", "reply": "ok"}
tests/test_comfy_nodes_agent_edit.py:11070:            return {"ok": True, "route": "respond", "reply": "ok"}
tests/test_comfy_nodes_agent_edit.py:11098:                "route": "clarify",
tests/test_comfy_nodes_agent_edit.py:11140:                "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:13794:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:13797:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:13908:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:13911:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14010:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14013:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14053:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14056:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14150:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14153:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14244:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14247:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14329:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14332:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14400:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14405:                "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14566:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14579:                "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14666:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:14669:            "executor_classification": {"route": "revise", "task": "edit_graph"},
tests/test_comfy_nodes_agent_edit.py:14711:            "route": "clarify",
tests/test_comfy_nodes_agent_edit.py:19354:            "route": "inspect",
tests/test_comfy_nodes_agent_edit.py:19392:            "route": "clarify",
tests/test_comfy_nodes_agent_edit.py:19437:            "route": "revise",
tests/test_comfy_nodes_agent_edit.py:19485:            "route": "adapt",
tests/test_comfy_nodes_agent_edit.py:19525:        "route": "revise",
tests/test_comfy_nodes_agent_edit.py:19579:        "route": "revise",
tests/test_comfy_nodes_agent_edit.py:19597:        "route": "revise",
tests/test_live_agentic_harness_guard_contract.py:174:                    "route": "adapt",
tests/test_live_agentic_harness_guard_contract.py:1008:                "route": "revise",
tests/test_live_agentic_harness_guard_contract.py:1081:                "route": "revise",
tests/test_live_agentic_harness_guard_contract.py:1120:                "route": "respond",
tests/test_live_agentic_harness_guard_contract.py:1163:                "route": "respond",
tests/test_agent_executor_routes.py:68:                "route": "inspect",
tests/live_agentic_harness/assessor.py:51:_EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise"})
tests/live_agentic_harness/assessor.py:52:_NON_EDIT_ROUTES = frozenset({
tests/live_agentic_harness/assessor.py:57:    "requires_custom_nodes",
tests/live_agentic_harness/assessor.py:268:    return _canonical_route(response) in _NON_EDIT_ROUTES
tests/live_agentic_harness/assessor.py:735:                and route in _NON_EDIT_ROUTES
tests/live_agentic_harness/assessor.py:758:            if not safe_refusal_accepted and outcome_kind in {"noop", "requires_custom_nodes"}:
tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:18:    "requires_custom_nodes": true,
vibecomfy/executor/prompts.py:71:    "- route=\"reorganise\": explicit canvas organisation/readability/layout "
vibecomfy/executor/prompts.py:73:    "reply=true, task=\"layout_reorganise\". This route may move, group, "
vibecomfy/executor/prompts.py:87:    "- Do not choose route=\"reorganise\" just because the canvas is messy, "
vibecomfy/executor/prompts.py:89:    "route=\"reorganise\" only when the user explicitly asks to organise, "
vibecomfy/executor/prompts.py:250:    "- Explicit organisational requests such as a /reorganise_comfy_workflow "
vibecomfy/executor/prompts.py:252:    "\"make this readable\" should use route=\"reorganise\" with "
vibecomfy/executor/prompts.py:253:    "task=\"layout_reorganise\". Do not use route=\"revise\" for layout-only "
vibecomfy/executor/prompts.py:277:    "- \"/reorganise_comfy_workflow\" -> route=\"reorganise\", "
vibecomfy/executor/prompts.py:278:    "task=\"layout_reorganise\".\n"
vibecomfy/executor/prompts.py:279:    "- \"organise this workflow\" -> route=\"reorganise\", "
vibecomfy/executor/prompts.py:280:    "task=\"layout_reorganise\".\n"
vibecomfy/executor/prompts.py:281:    "- \"clean up the canvas\" -> route=\"reorganise\", "
vibecomfy/executor/prompts.py:282:    "task=\"layout_reorganise\".\n"
vibecomfy/executor/prompts.py:283:    "- \"make this readable\" -> route=\"reorganise\", "
vibecomfy/executor/prompts.py:284:    "task=\"layout_reorganise\".\n"
vibecomfy/executor/prompts.py:325:    concrete functional edit to ``reorganise``.
vibecomfy/executor/prompts.py:468:        "functional edits to reorganise solely from this hint): "
vibecomfy/executor/prompts.py:550:    "the concrete graph edit; for route=\"reorganise\", describe the layout "
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json:23:    "requires_custom_nodes": true,
vibecomfy/executor/contracts.py:238:_ALLOWED_ROUTES = frozenset({
vibecomfy/executor/contracts.py:244:    "requires_custom_nodes",
vibecomfy/executor/contracts.py:247:    "reorganise",
vibecomfy/executor/contracts.py:259:    "layout_reorganise",
vibecomfy/executor/contracts.py:269:    "requires_custom_nodes": "return that the requested edit cannot be safely authored from current evidence without applying graph changes.",
vibecomfy/executor/contracts.py:272:    "reorganise": "reorganise the current canvas layout/readability without changing workflow semantics.",
vibecomfy/executor/contracts.py:275:_PUBLIC_ROUTES = frozenset({
vibecomfy/executor/contracts.py:277:    "requires_custom_nodes",
vibecomfy/executor/contracts.py:279:_APPLY_ELIGIBLE_ROUTES = frozenset({"revise", "adapt", "reorganise"})
vibecomfy/executor/contracts.py:303:    "layout_reorganise": "reorganise canvas layout/readability without changing workflow semantics.",
vibecomfy/executor/contracts.py:308:if set(_ROUTE_DESCRIPTIONS) != (_ALLOWED_ROUTES - {""}):
vibecomfy/executor/contracts.py:331:            "layout_reorganise",
vibecomfy/executor/contracts.py:332:            "reorganise_comfy_workflow",
vibecomfy/executor/contracts.py:334:            "/reorganise_comfy_workflow",
vibecomfy/executor/contracts.py:337:            return "reorganise"
vibecomfy/executor/contracts.py:340:    if route == "requires_custom_nodes":
vibecomfy/executor/contracts.py:358:    if route in _ALLOWED_ROUTES:
vibecomfy/executor/contracts.py:366:        "layout_reorganise": "reorganise",
vibecomfy/executor/contracts.py:367:        "layout_reorganize": "reorganise",
vibecomfy/executor/contracts.py:368:        "reorganise_workflow": "reorganise",
vibecomfy/executor/contracts.py:369:        "reorganize_workflow": "reorganise",
vibecomfy/executor/contracts.py:370:        "reorganise_comfy_workflow": "reorganise",
vibecomfy/executor/contracts.py:371:        "reorganize_comfy_workflow": "reorganise",
vibecomfy/executor/contracts.py:372:        "/reorganise_comfy_workflow": "reorganise",
vibecomfy/executor/contracts.py:373:        "/reorganize_comfy_workflow": "reorganise",
vibecomfy/executor/contracts.py:513:            "reorganise": (False, True),
vibecomfy/executor/contracts.py:523:        if self.route == "reorganise" and self.task != "layout_reorganise":
vibecomfy/executor/contracts.py:524:            object.__setattr__(self, "task", "layout_reorganise")
vibecomfy/executor/contracts.py:555:        if self.route == "reorganise":
vibecomfy/executor/contracts.py:556:            return "layout_reorganise"
vibecomfy/executor/contracts.py:2168:    if route in _PUBLIC_ROUTES:
vibecomfy/executor/contracts.py:2235:        route = self.route if self.route in _PUBLIC_ROUTES else "respond"
vibecomfy/executor/contracts.py:2254:        return self.route in _APPLY_ELIGIBLE_ROUTES and self.candidate is not None
vibecomfy/executor/contracts.py:2308:        if route in _APPLY_ELIGIBLE_ROUTES and result.graph is not None:
vibecomfy/executor/contracts.py:2346:    if route not in _APPLY_ELIGIBLE_ROUTES:
tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:12:      "requires_custom_nodes"
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:27:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-background-removal-and-grid-composition-54a681.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-model-load-edit-and-export-workflow-d66a66.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676.json:22:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-audio-processing-with-chatterbox-tts-and-vc-b55994.json:22:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:12:      "requires_custom_nodes"
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:26:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json:12:      "requires_custom_nodes"
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json:27:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-image-to-image-with-controlnet-and-dwpreproces-49d057.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-image-to-video-with-upscaling-and-color-matchi-359848.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json:23:    "requires_custom_nodes": true,
vibecomfy/executor/core.py:55:    _ALLOWED_ROUTES,
vibecomfy/executor/core.py:363:    "requires_custom_nodes": RouteBehavior(
vibecomfy/executor/core.py:364:        route="requires_custom_nodes",
vibecomfy/executor/core.py:390:    "reorganise": RouteBehavior(
vibecomfy/executor/core.py:391:        route="reorganise",
vibecomfy/executor/core.py:401:if set(_ROUTE_BEHAVIORS) != (_ALLOWED_ROUTES - {""}):
vibecomfy/executor/core.py:1619:    if outcome_kind in {"clarify", "requires_custom_nodes"}:
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-and-processing-workfl-1b1360.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-webp-and-png-output-bd3afb.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-flux-image-inpainting-and-compositing-with-con-00444a.json:23:    "requires_custom_nodes": true,
vibecomfy/executor/layout_hints.py:10:from vibecomfy.porting.reorganise.assess import (
vibecomfy/executor/layout_hints.py:25:from vibecomfy.porting.reorganise.orchestrate import assess_reorganise_workflow
vibecomfy/executor/layout_hints.py:26:from vibecomfy.porting.reorganise.plan_types import AssessmentReport
vibecomfy/executor/layout_hints.py:96:        result = assess_reorganise_workflow(graph)
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-workflow-2a31ec.json:22:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json:18:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:23:    "requires_custom_nodes": true,
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json:23:    "requires_custom_nodes": true,
vibecomfy/executor/execution_plan_builder.py:23:_NON_PLANNING_ROUTES = frozenset({"revise", "respond", "inspect", "research", "clarify"})
vibecomfy/executor/execution_plan_builder.py:1314:    if route in _NON_PLANNING_ROUTES:

exec
/bin/zsh -lc "nl -ba vibecomfy/executor/contracts.py | sed -n '234,290p;2200,2320p'
rg -n '_expects_graph_changed|expect_graph_changed' tests/live_agentic_harness/assessor.py tests/test_live_agentic_harness_guard_contract.py | head -80" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   234	# ── classify decision ────────────────────────────────────────────────────────
   235	
   236	# Canonical route vocabulary (SD1).  Empty string means "no route specified —
   237	# derive from legacy booleans".
   238	_ALLOWED_ROUTES = frozenset({
   239	    "",
   240	    "clarify",
   241	    "respond",
   242	    "inspect",
   243	    "research",
   244	    "requires_custom_nodes",
   245	    "revise",
   246	    "adapt",
   247	    "reorganise",
   248	})
   249	
   250	# Normalized task vocabulary carried alongside route.
   251	_ALLOWED_TASKS = frozenset({
   252	    "",
   253	    "edit_graph",
   254	    "inspect_graph",
   255	    "find_assets",
   256	    "diagnose",
   257	    "preview_subgraph",
   258	    "research_precedent",
   259	    "layout_reorganise",
   260	    "respond",
   261	    "research_nodes",
   262	})
   263	
   264	_ROUTE_DESCRIPTIONS: dict[str, str] = {
   265	    "clarify": "ask a clarifying question when load-bearing information is missing.",
   266	    "respond": "answer directly from existing context without research or editing.",
   267	    "inspect": "explain or analyze the current graph without outside research or editing.",
   268	    "research": "research workflows, nodes, or techniques, then answer without editing.",
   269	    "requires_custom_nodes": "return that the requested edit cannot be safely authored from current evidence without applying graph changes.",
   270	    "revise": "edit the current graph using local context only.",
   271	    "adapt": "research precedent or workflow patterns, then edit the graph.",
   272	    "reorganise": "reorganise the current canvas layout/readability without changing workflow semantics.",
   273	}
   274	
   275	_PUBLIC_ROUTES = frozenset({
   276	    *_ROUTE_DESCRIPTIONS,
   277	    "requires_custom_nodes",
   278	})
   279	_APPLY_ELIGIBLE_ROUTES = frozenset({"revise", "adapt", "reorganise"})
   280	_EVIDENCE_KEYS = frozenset({
   281	    "classification",
   282	    "graph_inspection",
   283	    "research",
   284	    "implementation",
   285	    "warnings",
   286	})
   287	_NO_CANDIDATE_REASONS = frozenset({
   288	    "route_not_applyable",
   289	    "no_graph",
   290	    "implementation_skipped",
  2200	            str(k): _freeze_jsonish(v) for k, v in self.implementation.items()
  2201	        }))
  2202	        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings))
  2203	
  2204	    def to_dict(self) -> dict[str, Any]:
  2205	        payload = {
  2206	            "classification": _thaw_jsonish(self.classification),
  2207	            "graph_inspection": _thaw_jsonish(self.graph_inspection),
  2208	            "research": _thaw_jsonish(self.research),
  2209	            "implementation": _thaw_jsonish(self.implementation),
  2210	            "warnings": list(self.warnings),
  2211	        }
  2212	        extra_keys = set(payload) - _EVIDENCE_KEYS
  2213	        if extra_keys:
  2214	            raise ValueError(f"Unexpected evidence keys: {sorted(extra_keys)}")
  2215	        return payload
  2216	
  2217	
  2218	@dataclass(frozen=True)
  2219	class AgentTurnResult:
  2220	    """Canonical public response envelope for one executor turn.
  2221	
  2222	    ``disposition`` is internal execution metadata. It is intentionally omitted
  2223	    from serialization so public ``route`` remains the only route vocabulary
  2224	    consumers see.
  2225	    """
  2226	
  2227	    route: str
  2228	    reply: str
  2229	    evidence: AgentEvidence = field(default_factory=AgentEvidence)
  2230	    candidate: dict[str, Any] | None = None
  2231	    no_candidate_reason: str | None = None
  2232	    disposition: str = ""
  2233	
  2234	    def __post_init__(self) -> None:
  2235	        route = self.route if self.route in _PUBLIC_ROUTES else "respond"
  2236	        object.__setattr__(self, "route", route)
  2237	
  2238	        candidate = self.candidate
  2239	        if candidate is not None:
  2240	            object.__setattr__(self, "candidate", MappingProxyType({
  2241	                str(k): _freeze_jsonish(v) for k, v in candidate.items()
  2242	            }))
  2243	            object.__setattr__(self, "no_candidate_reason", None)
  2244	        else:
  2245	            reason = self.no_candidate_reason or "no_changes"
  2246	            if reason not in _NO_CANDIDATE_REASONS:
  2247	                reason = "no_changes"
  2248	            object.__setattr__(self, "no_candidate_reason", reason)
  2249	
  2250	        object.__setattr__(self, "disposition", str(self.disposition or ""))
  2251	
  2252	    @property
  2253	    def apply_eligible(self) -> bool:
  2254	        return self.route in _APPLY_ELIGIBLE_ROUTES and self.candidate is not None
  2255	
  2256	    def to_dict(self) -> dict[str, Any]:
  2257	        return {
  2258	            "route": self.route,
  2259	            "reply": self.reply,
  2260	            "evidence": self.evidence.to_dict(),
  2261	            "candidate": _thaw_jsonish(self.candidate) if self.candidate is not None else None,
  2262	            "apply_eligible": self.apply_eligible,
  2263	            "no_candidate_reason": self.no_candidate_reason,
  2264	        }
  2265	
  2266	    @classmethod
  2267	    def from_executor_result(cls, result: "ExecutorResult") -> "AgentTurnResult":
  2268	        plan = result.report.plan
  2269	        reply = result.reply or result.failure_message or ""
  2270	        warnings: list[str] = []
  2271	
  2272	        if plan is None:
  2273	            # Failed classification has NO decision (G0): do not invent a
  2274	            # route/task/intent.  The classification evidence stays empty and
  2275	            # the envelope carries no disposition.
  2276	            classification: dict[str, Any] = {}
  2277	            route = ""
  2278	            disposition = ""
  2279	        else:
  2280	            route = _public_route_for_plan(plan)
  2281	            classification = {
  2282	                "route": route,
  2283	                "task": plan.effective_task,
  2284	                "intent": plan.intent,
  2285	                "plan_summary": plan.plan_summary,
  2286	            }
  2287	            if plan.route and plan.route != route:
  2288	                classification["disposition"] = plan.route
  2289	            disposition = plan.route or plan.effective_route
  2290	
  2291	        graph_inspection: dict[str, Any] = {}
  2292	        if route == "inspect":
  2293	            graph_inspection["used_for_reply"] = True
  2294	
  2295	        research: dict[str, Any] = {}
  2296	        if result.report.research is not None:
  2297	            research = result.report.research.to_dict()
  2298	            warnings.extend(result.report.research.warnings)
  2299	
  2300	        implementation: dict[str, Any] = {}
  2301	        if result.report.implementation is not None:
  2302	            implementation = result.report.implementation.to_dict()
  2303	
  2304	        if result.failure_message:
  2305	            warnings.append(result.failure_message)
  2306	
  2307	        candidate: dict[str, Any] | None = None
  2308	        if route in _APPLY_ELIGIBLE_ROUTES and result.graph is not None:
  2309	            candidate = {"graph": result.graph}
  2310	            # Attach durable metadata (SD2: applyable == durable).
  2311	            impl = result.report.implementation
  2312	            if impl is not None:
  2313	                sid = impl.durable_session_id
  2314	                tid = impl.durable_turn_id
  2315	                if sid is not None:
  2316	                    candidate["session_id"] = sid
  2317	                if tid is not None:
  2318	                    candidate["turn_id"] = tid
  2319	        reason = _derive_no_candidate_reason(
  2320	            route=route,
tests/test_live_agentic_harness_guard_contract.py:66:            "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:186:    scenario = {"id": "hotshot-failure", "assessment": {"expect_graph_changed": True}}
tests/test_live_agentic_harness_guard_contract.py:193:    assert assessment["expect_graph_changed"] is True
tests/test_live_agentic_harness_guard_contract.py:237:            "expect_graph_changed": False,
tests/test_live_agentic_harness_guard_contract.py:246:    assert assessment["expect_graph_changed"] is False
tests/test_live_agentic_harness_guard_contract.py:269:            "expect_graph_changed": False,
tests/test_live_agentic_harness_guard_contract.py:314:            "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:323:    assert assessment["expect_graph_changed"] is True
tests/test_live_agentic_harness_guard_contract.py:347:            "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:379:            "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:418:            "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:678:            "expect_graph_changed": expect_edit,
tests/test_live_agentic_harness_guard_contract.py:720:        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:762:            "expect_graph_changed": False,
tests/test_live_agentic_harness_guard_contract.py:847:        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:905:        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:943:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:981:                "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:1021:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1057:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1094:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1135:                "expect_graph_changed": True,
tests/test_live_agentic_harness_guard_contract.py:1176:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1256:        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
tests/test_live_agentic_harness_guard_contract.py:1296:        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
tests/live_agentic_harness/assessor.py:279:def _expects_graph_changed(
tests/live_agentic_harness/assessor.py:290:        if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
tests/live_agentic_harness/assessor.py:291:            return bool(assessment["expect_graph_changed"])
tests/live_agentic_harness/assessor.py:624:    * ``expect_graph_changed`` — whether the scenario expected an edit.
tests/live_agentic_harness/assessor.py:633:    expect_graph_changed = _expects_graph_changed(scenario, response)
tests/live_agentic_harness/assessor.py:642:            expect_graph_changed
tests/live_agentic_harness/assessor.py:678:        if expect_graph_changed:
tests/live_agentic_harness/assessor.py:813:            expect_graph_changed
tests/live_agentic_harness/assessor.py:919:        "expect_graph_changed": expect_graph_changed,

codex
The direct inspection now shows the key structural decisions are in the right places: the scorer reads the canonical route and raw `change_details.landed_operation_count`, while the narrator returns the selected message after a separately guarded artifact write. I’m moving to the exact focused test commands and diff hygiene check.
exec
/bin/zsh -lc 'git diff --check a890884f..16d80bbe' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc '.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc '.venv/bin/python -m pytest -q tests/test_edit_narrative.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 296ms:
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

 exited 1 in 303ms:
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
The diff hygiene check passed. Both pytest commands are blocked before collection because this read-only sandbox exposes no writable temporary directory (`FileNotFoundError` from Python `tempfile`); I won’t treat that infrastructure failure as a product-test failure. I’m compensating with line-level test inspection and checking commit-contained evidence and fixture enumeration.
exec
/bin/zsh -lc 'git log --oneline --decorate --no-merges a890884f..16d80bbe
git show --no-ext-diff --format=fuller --stat 16d80bbe
git show --no-ext-diff --format=fuller --stat a890884f..16d80bbe
for p in out/agentic output/agentic; do if [ -e "$p" ]; then ls -ld "$p"; else echo "ABSENT $p"; fi; done
.venv/bin/python -c '"'import ast, pathlib; paths=[\"tests/live_agentic_harness/assessor.py\",\"vibecomfy/comfy_nodes/agent/_frag_narrator.py\",\"tests/test_edit_narrative.py\",\"tests/test_live_agentic_assessor_score_honesty.py\",\"tests/test_live_agentic_harness_guard_contract.py\"]; [ast.parse(pathlib.Path(p).read_text(encoding=\"utf-8\"), filename=p) for p in paths]; print(\"AST parse OK:\", len(paths), \"files\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 182ms:
AST parse OK: 5 files

exec
/bin/zsh -lc "rg -n 'Never mention internal agent machinery|validation outcome truthfully|validation\\.passed below|_NARRATOR_SYSTEM_PROMPT' vibecomfy/comfy_nodes/agent -g '*.py'
rg -n '_frag_narrator|exec\\(|compile\\(' vibecomfy/comfy_nodes/agent/edit.py vibecomfy/comfy_nodes/agent/__init__.py pyproject.toml tests/conftest.py
sed -n '1,120p' vibecomfy/comfy_nodes/agent/edit.py
nl -ba vibecomfy/comfy_nodes/agent/edit_narrator.py | sed -n '232,265p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
vibecomfy/comfy_nodes/agent/_frag_narrator.py:245:_NARRATOR_SYSTEM_PROMPT = (
vibecomfy/comfy_nodes/agent/_frag_narrator.py:253:    "- Never mention internal agent machinery (gate names, scoring, batch REPL, "
vibecomfy/comfy_nodes/agent/_frag_narrator.py:254:    "field-level diffs). Describe the validation outcome truthfully — "
vibecomfy/comfy_nodes/agent/_frag_narrator.py:255:    "validation.passed below is user-facing and must be reported as-is.\n"
vibecomfy/comfy_nodes/agent/_frag_narrator.py:283:    from vibecomfy.comfy_nodes.agent.edit import (_NARRATOR_SYSTEM_PROMPT)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_narrator.py:296:        {"role": "system", "content": _NARRATOR_SYSTEM_PROMPT},
vibecomfy/comfy_nodes/agent/_frag_narrator.py:497:    "_NARRATOR_SYSTEM_PROMPT",
vibecomfy/comfy_nodes/agent/edit.py:166:        "_NARRATOR_SYSTEM_PROMPT",
vibecomfy/comfy_nodes/agent/edit.py:38:from ._frag_narrator import *  # noqa: F401,F403
from __future__ import annotations

from importlib import import_module

# T-037: the batch REPL loop now lives as real functions in edit_batch_repl.py,
# reached through the thin _stage_agent_batch_repl delegate defined below.
# Resolved here via import_module (never through a normal from-import) so there
# is no import cycle: edit_batch_repl imports only stdlib and builds its
# EditBatchReplDeps at call time from this assembled façade namespace
# (globals()).
_edit_batch_repl = import_module(f"{__package__ or 'vibecomfy.comfy_nodes.agent'}.edit_batch_repl")

# T-038/T-039: the foundation fragments (state/humanize/memory/reports/chat/
# session_bundle/ingest/research) and the orchestration fragments (revision,
# revision_stages, batch_loop, transform_stages, narrator, response_contract,
# orchestration, entrypoint) live as real modules imported here in dependency
# order. Each module's __all__ is exactly the name set its fragment contributed
# to this namespace under the old exec assembly, so `import *` reproduces the
# identical top-level attributes.
# T-040: these imports are now the ONLY source of façade names. The exec
# assembler and the fragment SOURCE strings are gone from the live path;
# __all__ below pins the frozen name surface (G0-T2 removed the 10
# deterministic-prose-gating names: the _NARRATIVE_* pattern constants,
# _validate_narrative_message, _guard_narrative_message, and
# _narrator_fast_path_applies).
from ._frag_state import *  # noqa: F401,F403
from ._frag_humanize import *  # noqa: F401,F403
from ._frag_batch_memory import *  # noqa: F401,F403
from ._frag_batch_reports import *  # noqa: F401,F403
from ._frag_chat import *  # noqa: F401,F403
from ._frag_session_bundle import *  # noqa: F401,F403
from ._frag_ingest import *  # noqa: F401,F403
from ._frag_research import *  # noqa: F401,F403
from ._frag_revision import *  # noqa: F401,F403
from ._frag_revision_stages import *  # noqa: F401,F403
from ._frag_batch_loop import *  # noqa: F401,F403
from ._frag_transform_stages import *  # noqa: F401,F403
from ._frag_narrator import *  # noqa: F401,F403
from ._frag_response_contract import *  # noqa: F401,F403
from ._frag_orchestration import *  # noqa: F401,F403
from ._frag_entrypoint import *  # noqa: F401,F403

# T-039 required_post_split contract: the frozen manifest names
# load_agent_generated_scratchpad as a top-level edit-module attr post-split
# (pre-split it exists only as a guarded local import inside
# _frag_transform_stages._stage_load_python). The lazy facade lives in the
# fragment module; it is re-exported here by name and kept OUT of __all__ so
# the frozen 472-name surface set stays byte-identical (the manifest records
# this name under required_post_split, not __all__).
from ._frag_transform_stages import load_agent_generated_scratchpad


def _stage_agent_batch_repl(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    """Batch REPL loop (T-037): thin delegate into edit_batch_repl.

    The loop body moved out of the stitched fragments into
    :mod:`vibecomfy.comfy_nodes.agent.edit_batch_repl`; this S3 stage keeps the
    original signature so orchestration and tests are unaffected. The extracted
    implementation builds its invocation-time :class:`EditBatchReplDeps` from
    this assembled namespace (``globals()``) at the top of each call.
    """
    return _edit_batch_repl._stage_agent_batch_repl(
        globals(),
        state,
        _context,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
        effort=effort,
        client_id=client_id,
        conversation_messages=conversation_messages,
    )


# Frozen ORACLE-1 cleanup surface (T-036, membership-only; order not
# contractual — a frozenset). Source of truth:
# tests/fixtures/agent_edit/cleanup_surface_manifest.json. Every name is a
# top-level attribute of this module, provided by the _frag_* re-exports above
# (or defined in place, as _stage_agent_batch_repl is); the surface test
# enforces set-equality with the manifest so drift fails loudly.
__all__ = frozenset(
    {
        "AgentEditState",
        "AgentError",
        "AgentTurnResult",
        "Any",
        "ApplyCandidate",
        "ApplyEligibility",
        "ArtifactRef",
        "BatchTurnResult",
        "Callable",
        "DEFAULT_CHAT_DISPLAY_MESSAGES",
        "DeepSeekClient",
        "ExecutionPlan",
        "FailureEnvelope",
        "FailureKind",
        "FieldChange",
        "LOGGER",
        "MalformedModelJSON",
        "Mapping",
        "MissingRequiredField",
        "NarrativeContext",
        "PLAN_STATE_NOT_REQUIRED",
        "PROMPT_MEMORY_MESSAGES",
        "Path",
        "PlanEvaluation",
        "ProviderError",
        "REVIEWABLE_CANDIDATE_STATES",
        "ReadinessReport",
        "RevisionEvidence",
nl: vibecomfy/comfy_nodes/agent/edit_narrator.py: No such file or directory

exec
/bin/zsh -lc ".venv/bin/python -B -c 'import vibecomfy.comfy_nodes.agent.edit as e; import vibecomfy.comfy_nodes.agent._frag_narrator as f; original=f._write_narrative_artifacts; e._write_narrative_artifacts=lambda *a,**k: (_ for _ in ()).throw(RuntimeError(\"boom\")); print(\"function_module\", e._narrate_final_message.__module__); print(\"facade_patch_reaches_fragment\", f._write_narrative_artifacts is e._write_narrative_artifacts); print(\"fragment_writer_unchanged\", f._write_narrative_artifacts is original)'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 7533ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/torch/library.py:361: UserWarning: Warning only once for all operators,  other operators may also be overridden.
  Overriding a previously registered kernel for the same operator and the same dispatch key
  operator: aten::mm(Tensor self, Tensor mat2) -> Tensor
    registered at /Users/runner/work/pytorch/pytorch/build/aten/src/ATen/RegisterSchema.cpp:6
  dispatch key: MPS
  previous kernel: registered at /Users/runner/work/pytorch/pytorch/aten/src/ATen/LegacyBatchingRegistrations.cpp:1076
       new kernel: registered at /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/fp4_fp8_for_torch_mps/ops.py:7 (Triggered internally at /Users/runner/work/pytorch/pytorch/aten/src/ATen/core/dispatch/OperatorEntry.cpp:215.)
  self.m.impl(
Could not locate ComfyUI root (no server.py + nodes.py found).
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/comfy/model_management.py:237: UserWarning: torch.cuda.current_device() did not return a device, returning a CPU torch device
  warnings.warn("torch.cuda.current_device() did not return a device, returning a CPU torch device")
[32m[INFO][0m Set vram state to: NORMAL_VRAM
objc[77841]: Class AVFFrameReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x1149e83a8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x1253b43a8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
objc[77841]: Class AVFAudioReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x1149e83f8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x1253b43f8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
[32m[INFO][0m PromptServer imported; registering VibeComfy routes.
[32m[INFO][0m vibecomfy agent routes module loaded and all routes registered.
[32m[INFO][0m VibeComfy routes registered successfully.
function_module vibecomfy.comfy_nodes.agent._frag_narrator
facade_patch_reaches_fragment False
fragment_writer_unchanged True

exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/_frag_narrator.py | sed -n '275,405p'
sed -n '1,50p' tests/test_edit_narrative.py
rg -n 'monkeypatch\\.setattr\\(\\s*\"vibecomfy\\.comfy_nodes\\.agent\\.edit\\._write_narrative_artifacts\"|_write_narrative_artifacts' tests -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   275	
   276	
   277	def _build_narrator_messages(
   278	    narrative_context: NarrativeContext,
   279	    *,
   280	    raw_executor_message: str = "",
   281	    fallback_message: str = "",
   282	) -> list[dict[str, str]]:
   283	    from vibecomfy.comfy_nodes.agent.edit import (_NARRATOR_SYSTEM_PROMPT)  # T-039 late import: host namespace lookup; resolved at call time
   284	    """Build the message list for the LLM narrator call."""
   285	    context_json = json.dumps(narrative_context.payload, indent=2, sort_keys=True)
   286	    user_content_parts: list[str] = [
   287	        "Turn narrative context (JSON):",
   288	        context_json,
   289	    ]
   290	    if raw_executor_message:
   291	        user_content_parts.append(f"\nRaw executor message: {raw_executor_message[:240]}")
   292	    if fallback_message:
   293	        user_content_parts.append(f"\nFallback message (use as reference): {fallback_message}")
   294	    user_content_parts.append("\nProduce the user-facing message as a JSON object.")
   295	    return [
   296	        {"role": "system", "content": _NARRATOR_SYSTEM_PROMPT},
   297	        {"role": "user", "content": "\n".join(user_content_parts)},
   298	    ]
   299	
   300	
   301	# ── Provider-backed LLM call ──────────────────────────────────────────────
   302	
   303	def _call_narrator_llm(
   304	    narrative_context: NarrativeContext,
   305	    messages: list[dict[str, str]],
   306	    *,
   307	    route: str,
   308	    model: str,
   309	) -> tuple[str, dict[str, Any]]:
   310	    from vibecomfy.comfy_nodes.agent.edit import (MalformedModelJSON, MissingRequiredField, ProviderError, _narrator_message_from_response, run_model_turn)  # T-039 late import: host namespace lookup; resolved at call time
   311	    """Call the LLM narrator through the provider and extract the message.
   312	
   313	    Returns ``(message, raw_response)``.  The *message* is extracted from
   314	    the JSON response; *raw_response* is the full dict for artifact recording.
   315	
   316	    Raises :class:`ProviderError`, :class:`AuthError`, :class:`MalformedModelJSON`,
   317	    or :class:`TimeoutError` on failure — callers must catch these.
   318	    """
   319	    try:
   320	        raw = run_model_turn(
   321	            task=narrative_context.task or "narrate turn outcome",
   322	            messages=messages,
   323	            route=route,
   324	            model=model,
   325	            response_contract="json",
   326	        )
   327	    except TimeoutError:
   328	        raise
   329	    except ImportError:
   330	        raise ProviderError("Narrator runtime unavailable (import error).")
   331	    except (ProviderError, MalformedModelJSON, MissingRequiredField):
   332	        raise
   333	    except Exception as exc:
   334	        raise ProviderError(f"Narrator LLM call failed: {exc}") from exc
   335	
   336	    if not isinstance(raw, dict):
   337	        raise MalformedModelJSON(
   338	            "Narrator response was not a JSON object.",
   339	            raw_response=str(raw)[:500],
   340	            parse_reason="non_dict_response",
   341	        )
   342	
   343	    # Use the canonical extraction helper from _frag_humanize which handles
   344	    # the 'json' wrapper key that run_model_turn returns.
   345	    message_raw = _narrator_message_from_response(raw)
   346	
   347	    return message_raw, raw
   348	
   349	
   350	# ── Main entrypoint (LLM narrator is the sole path) ───────────────────────
   351	
   352	def _narrate_final_message(
   353	    state: AgentEditState,
   354	    context: TurnContext,
   355	    *,
   356	    outcome: TurnOutcome | None = None,
   357	    failure: FailureEnvelope | None = None,
   358	    public_outcome: str | None = None,
   359	    apply_eligibility: ApplyEligibility | None = None,
   360	) -> str:
   361	    from vibecomfy.comfy_nodes.agent.edit import (LOGGER, MalformedModelJSON, ProviderError, _NARRATOR_DEFAULT_MODEL, _NARRATOR_DEFAULT_ROUTE, _assemble_narrative_context, _build_narrator_messages, _call_narrator_llm, _deterministic_narrative_fallback, _narrator_model, _narrator_route, _write_narrative_artifacts)  # T-039 late import: host namespace lookup; resolved at call time
   362	    """Produce the final user-facing message for a completed agent-edit turn.
   363	
   364	    The agent ALWAYS writes the message: the LLM narrator is invoked for every
   365	    outcome, and whatever message it produces is the final message — prose is
   366	    never gated or replaced by a deterministic substitute. The deterministic
   367	    fallback is used only when no agent message exists (provider failure,
   368	    timeout, or a response that did not yield a message).
   369	
   370	    The synthesis prompt feeds the agent the structured outcome
   371	    (``change.graph_unchanged``, ``outcome.kind``,
   372	    ``change.landed_operation_count``, ``validation.passed``) and requires the
   373	    narrative to describe exactly those facts.
   374	
   375	    Every path writes compact narrative_context.json and
   376	    narrative_validation.json artifacts; the LLM path additionally writes
   377	    narrator_request.json and narrator_response.json.  All artifact writes
   378	    are best-effort (failures logged and swallowed).
   379	    """
   380	    try:
   381	        # ── Assemble context ──────────────────────────────────────────
   382	        narrative_context = _assemble_narrative_context(
   383	            state,
   384	            context,
   385	            outcome=outcome,
   386	            failure=failure,
   387	            public_outcome=public_outcome,
   388	            apply_eligibility=apply_eligibility,
   389	        )
   390	
   391	        # ── LLM narrator path (sole path; SD1 fast-path removed) ──────
   392	        route = _narrator_route() or _NARRATOR_DEFAULT_ROUTE
   393	        model = _narrator_model() or _NARRATOR_DEFAULT_MODEL
   394	
   395	        # Pre-compute the deterministic fallback in case the LLM path
   396	        # produces no message at all.
   397	        fallback_message = _deterministic_narrative_fallback(
   398	            state,
   399	            outcome=outcome,
   400	            failure=failure,
   401	            narrative_context=narrative_context,
   402	        )
   403	
   404	        llm_request: list[dict[str, str]] | None = None
   405	        llm_response: dict[str, Any] | None = None
"""Unit tests for the post-validation narrative narrator.

Covers the _frag_narrator narrative synthesis (exported through the live
edit module) without invoking a real provider.
Tests exercise the fact-grounded prompt construction, deterministic fallback,
and the full _narrate_final_message entrypoint with mocked provider.
G0-T2: the agent ALWAYS writes the message — the LLM narrator runs for every
outcome and its message always ships; the deterministic fallback is used only
when no agent message exists (provider failure / timeout / malformed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from vibecomfy.comfy_nodes.agent.edit import (
    AgentEditState,
    NarrativeContext,
    _assemble_narrative_context,
    _build_narrator_messages,
    _call_narrator_llm,
    _deterministic_narrative_fallback,
    _narrate_final_message,
    _net_field_changes,
    _total_landed_edit_count,
    _write_narrative_artifacts,
)
from vibecomfy.comfy_nodes.agent.contracts import (
    ApplyEligibility,
    FailureEnvelope,
    FailureKind,
    TurnContext,
    TurnOutcome,
)
from vibecomfy.comfy_nodes.agent.provider import (
    MalformedModelJSON,
    MissingRequiredField,
    ProviderError,
)
from vibecomfy.porting.edit.types import FieldChange


def test_net_field_changes_collapses_revisions_and_drops_reverted_edits() -> None:
    changes = (
        FieldChange(uid="prompt", field_path="text", old="calm", new="energetic"),
tests/test_edit_narrative.py:31:    _write_narrative_artifacts,
tests/test_edit_narrative.py:408:        _write_narrative_artifacts(state, ctx, validation)
tests/test_edit_narrative.py:431:        _write_narrative_artifacts(
tests/test_edit_narrative.py:450:        _write_narrative_artifacts(state, ctx, validation)
tests/test_edit_narrative.py:922:        """G0R: a raise from _write_narrative_artifacts must not replace the
tests/test_edit_narrative.py:941:            "vibecomfy.comfy_nodes.agent.edit._write_narrative_artifacts",

Acceptance, exact diff, implementation, tests, and scope have been inspected. Focused pytest was attempted but cannot initialize without a writable temp directory in this read-only sandbox; diff check and AST parsing succeeded.
  ✓ Read G0R acceptance, original G0 failure, brief, and exact diff scope
  ✓ Inspect scorer guard, narrator behavior, prompt, and fixture coverage
  ✓ Run the permitted focused verification commands
  → Cross-check independent reviews and issue binary verdict
collab: Wait
exec
/bin/zsh -lc ".venv/bin/python -B - <<'PY'
import ast
from pathlib import Path
p=Path('tests/test_live_agentic_harness_guard_contract.py')
t=ast.parse(p.read_text())
for node in t.body:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == '_MATCHER_ONLY_COUNTEREXAMPLES':
        print('matcher_fixture_count', len(node.value.elts))
        break
else:
    raise SystemExit('fixture tuple not found')
PY
git diff --numstat a890884f..16d80bbe
if rg -n '\"unchanged\"\\s+in|in\\s+.*\\.lower\\(\\).*unchanged|message_artifact|_MESSAGE_|_NARRATIVE_' tests/live_agentic_harness/assessor.py; then true; else echo 'no executable matcher identifiers/patterns found'; fi" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 6ms:
no executable matcher identifiers/patterns found

exec
/bin/zsh -lc ".venv/bin/python -B -c 'import ast,pathlib; t=ast.parse(pathlib.Path(\"tests/test_live_agentic_harness_guard_contract.py\").read_text()); nodes=[n for n in t.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id==\"_MATCHER_ONLY_COUNTEREXAMPLES\"]; print(\"matcher_fixture_count\",len(nodes[0].value.elts))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
matcher_fixture_count 9

Independent reviews converged with the direct inspection. No substantive acceptance issue remains; the only verification gap is sandbox-blocked pytest execution, offset by executor evidence plus static/AST/diff checks.
  ✓ Read G0R acceptance, original G0 failure, brief, and exact diff scope
  ✓ Inspect scorer guard, narrator behavior, prompt, and fixture coverage
  ✓ Run the permitted focused verification commands
  ✓ Cross-check independent reviews and issue binary verdict
codex
G0R CHECKPOINT VERDICT: PASS — All four original G0 defects are closed; no G0R-scoped acceptance issue remains.

1. **Residual prose gate — PASS.** No executable `"unchanged"`, `message_artifact`, `_MESSAGE_`, or `_NARRATIVE_` scoring gate remains. [assessor.py:888](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:888) now checks only structured `implementation_result.ok`; remaining `"unchanged"` references are comments or structured `graph_unchanged` handling.

2. **Structural landed-count guard — PASS.** [assessor.py:696](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:696) reads `change_details.landed_operation_count` and requires an integer greater than zero, explicitly rejecting booleans. Missing details/count, zero, negative, string, float, and boolean controls are covered at [test_live_agentic_harness_guard_contract.py:871](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_guard_contract.py:871). Canonical-route exemptions use the response envelope rather than self-declared outcome/reason labels at [assessor.py:227](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:227). Grounded refusals remain exempt; dishonest non-edit routes claiming a changed graph fail `route_graph_consistency`.

3. **Narrator write failure — PASS.** Message selection occurs before the independently guarded artifact write at [_frag_narrator.py:439](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_narrator.py:439), and the selected message is returned at line 476. The regression patches the live façade writer to raise `RuntimeError` at [test_edit_narrative.py:937](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_edit_narrative.py:937) and asserts the exact narrator response survives at line 973. The late import at `_frag_narrator.py:361` makes that monkeypatch effective.

4. **Prompt contradiction — PASS.** [_frag_narrator.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_narrator.py:253) now excludes only internal machinery while explicitly requiring truthful validation reporting. The `validation.passed` requirements at lines 263–273 are consistent; no residual “never mention validation” instruction remains.

5. **Scope and criteria — PASS.** The diff contains only `.gitignore`’s `.venv` symlink rule, two G0R briefs, scorer/narrator changes, and their three focused test files. The rework tightens route-aware fail-closed behavior; no criterion was weakened and the tasklist-numbering change is absent. `out/agentic/` is absent, so historical re-binning is correctly unavailable rather than inferred.

6. **Verification — PASS with sandbox limitation.** `git diff --check a890884f..16d80bbe` passed, and all five changed Python files parse successfully. Both requested pytest commands were attempted but pytest could not initialize because the read-only sandbox provides no writable temporary directory. This is an infrastructure limitation, not a collected test failure. Executor evidence reports 20 guard/score tests and 38 narrative tests passing.

7. **Nine matcher counterexamples — PASS.** Static enumeration confirms exactly nine fixtures at [test_live_agentic_harness_guard_contract.py:521](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_guard_contract.py:521). Their parametrized test requires every case to pass and forbids any `message_artifact` issue at lines 659–690; executor evidence reports the slice green with zero matcher failures.
tokens used
192,193
G0R CHECKPOINT VERDICT: PASS — All four original G0 defects are closed; no G0R-scoped acceptance issue remains.

1. **Residual prose gate — PASS.** No executable `"unchanged"`, `message_artifact`, `_MESSAGE_`, or `_NARRATIVE_` scoring gate remains. [assessor.py:888](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:888) now checks only structured `implementation_result.ok`; remaining `"unchanged"` references are comments or structured `graph_unchanged` handling.

2. **Structural landed-count guard — PASS.** [assessor.py:696](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:696) reads `change_details.landed_operation_count` and requires an integer greater than zero, explicitly rejecting booleans. Missing details/count, zero, negative, string, float, and boolean controls are covered at [test_live_agentic_harness_guard_contract.py:871](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_guard_contract.py:871). Canonical-route exemptions use the response envelope rather than self-declared outcome/reason labels at [assessor.py:227](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:227). Grounded refusals remain exempt; dishonest non-edit routes claiming a changed graph fail `route_graph_consistency`.

3. **Narrator write failure — PASS.** Message selection occurs before the independently guarded artifact write at [_frag_narrator.py:439](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_narrator.py:439), and the selected message is returned at line 476. The regression patches the live façade writer to raise `RuntimeError` at [test_edit_narrative.py:937](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_edit_narrative.py:937) and asserts the exact narrator response survives at line 973. The late import at `_frag_narrator.py:361` makes that monkeypatch effective.

4. **Prompt contradiction — PASS.** [_frag_narrator.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_narrator.py:253) now excludes only internal machinery while explicitly requiring truthful validation reporting. The `validation.passed` requirements at lines 263–273 are consistent; no residual “never mention validation” instruction remains.

5. **Scope and criteria — PASS.** The diff contains only `.gitignore`’s `.venv` symlink rule, two G0R briefs, scorer/narrator changes, and their three focused test files. The rework tightens route-aware fail-closed behavior; no criterion was weakened and the tasklist-numbering change is absent. `out/agentic/` is absent, so historical re-binning is correctly unavailable rather than inferred.

6. **Verification — PASS with sandbox limitation.** `git diff --check a890884f..16d80bbe` passed, and all five changed Python files parse successfully. Both requested pytest commands were attempted but pytest could not initialize because the read-only sandbox provides no writable temporary directory. This is an infrastructure limitation, not a collected test failure. Executor evidence reports 20 guard/score tests and 38 narrative tests passing.

7. **Nine matcher counterexamples — PASS.** Static enumeration confirms exactly nine fixtures at [test_live_agentic_harness_guard_contract.py:521](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_guard_contract.py:521). Their parametrized test requires every case to pass and forbids any `message_artifact` issue at lines 659–690; executor evidence reports the slice green with zero matcher failures.
