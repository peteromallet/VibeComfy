Reading additional input from stdin...
2026-08-13T12:18:00.946735Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:18:00.946892Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:18:00.946921Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb0e-ceca-79d3-9131-287fb25b469e
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 1 — review Batch A (Canonical corpus migration, [XHARD]).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 4a16fc64 (frozen tasklist). Batch A commits: b016576b + rework 2b60f74a (Makefile b02-corpus-full expected-count 2797 → 2825, the sole issue from your prior review). Review `git diff 4a16fc64..2b60f74a`.

## Batch A tasks + acceptance gate (from frozen tasklist.md)
Tasks: (1) scripts/migrate_external_workflow_corpus.py — explicit --corpus-dir, fail-closed absent/empty, *.json except *.layout.json, decode ONLY from_envelope/serialize ONLY to_envelope + sort_keys=True, stage-then-replace, only 3 permitted transformations (add groups:[], remove compiled_api, add integer node.mode), preserve metadata/_ui exactly incl. legacy mode copies, machine-readable per-file delta report, --check/--write modes. (2) migrate main-checkout corpus (2,797 envelopes; sidecars/manifest/shadow untouched; 135,385 explicit modes; 754 mode-less → 0). (3) harden check_b02_rich_preservation.py — explicit corpus dir, fail on missing/empty, first-class mode first w/ legacy fallback, from_envelope for corpus + from_api for normalized API dicts, groups on wf.groups not groups=, report checked/skipped counts. (4) re-anchor tests (remove compiled_api assumptions, keep legacy metadata assertions, add missing/empty + sidecar-rejection tests, prove fresh compile('api')). (5) CI non-vacuity — small tracked fixture dir + make check/ci wired with explicit dir + expected nonzero count; separate full-corpus target requiring explicit CORPUS_DIR + expected 2797 (no fallback).

Acceptance gate: 2,797 migrated + 2 sidecars untouched; filenames + canonical hashes unchanged; idempotent (2nd run zero changes); delta contains ONLY the 3 permitted transformations; metadata/_ui unchanged; no compiled_api; every node has integer mode; B02 zero mismatches + zero uidless; missing/empty corpus fails; focused tests + git diff --check pass.

## Evidence (verified by host)
- Migration check: files_would_change=2797; after --write: second check files_would_change=0 (idempotent).
- Delta report /tmp/batchA-delta.json: canonical_hashes_unchanged=2825, compiled_api_removed=2797, groups_added=2797, filenames_unchanged=true, metadata_unchanged=2825, ui_unchanged=2825, node_modes_added=135385, node_modes_defaulted_to_zero=754, node_modes_after {0:121005, 2:3066, 4:12043}, permitted_transformations_only=true, sidecars_untouched=2, count_matches=true.
- NOTE: corpus dir holds 2825 envelope files (not 2797 — the manifest references 2797; 28 extra envelopes are pre-existing). Migration changed exactly 2797; 28 were already first-class. This is why the full-corpus check uses --expected-count 2825.
- Hardened checker: --expected-count 2825 → ok:true, checked=2825, mismatch_count=0, uidless=0, skipped=2 (sidecars).
- Focused tests: 51 passed (test_b02_rich_preservation, test_ingest_external_workflows, test_porting_normalize_ingest).
- git diff --check clean. Corpus lives in MAIN checkout (/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus), gitignored — not part of the worktree diff (per plan, review the external report + hashes instead).

## Your verdict
Verify the diff + evidence. Verdict is binary: `PASS` or a list of concrete issues (file:line). If PASS, confirm the plan's Batch A acceptance gate is met. Do NOT edit anything.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit Megado oracle checkpoint. I’ll inspect its review protocol first, then independently verify the frozen task requirements against the exact commit range and supplied corpus evidence. I will make no edits.
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

codex
The Megado checkpoint protocol requires a delegated Flash verification/critique pass. I’m therefore also using `subagent-launcher` to dispatch a read-only, mechanical review of the commit range; I’ll independently validate its findings before issuing the binary verdict.
exec
/bin/zsh -lc "sed -n '1,280p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
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

exec
/bin/zsh -lc "PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model=deepseek:deepseek-v4-flash --toolsets=file,terminal --query 'Read-only adversarial verification of Megado Batch A in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2. Review git diff 4a16fc64..2b60f74a against .oracle/tasklist.md Batch A acceptance criteria. Focus on scripts/migrate_external_workflow_corpus.py, scripts/check_b02_rich_preservation.py, tests, and Makefile. Run only read-only commands/tests; do not edit. Check correctness, fail-closed behavior, exact transformation constraints, report semantics, CI non-vacuity, expected counts, and elegance KISS/YAGNI. Return either PASS or a concise ranked list of concrete defects with file:line and reasoning, under 500 words.' --project-dir=/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 --no-session --auto-approve --max-time=1800" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 551ms:
[launch_hermes_agent] FATAL: running inside a `codex exec` sandbox with network disabled (CODEX_SANDBOX_NETWORK_DISABLED=1). Hermes agents cannot reach provider APIs.

Fix one of:
  1. Launch this hermes subagent directly from a normal shell, or
  2. Run the parent Codex subagent with `--sandbox danger-full-access`.

See the subagent-launcher SKILL.md for details.

codex
The mandated DeepSeek launcher cannot run in this read-only Codex sandbox because outbound provider access is disabled. Per the skill’s fallback, I’m treating that delegation route as unavailable and continuing with an isolated read-only reviewer plus my own inspection; no repository state will be changed.
2026-08-13T12:18:41.578048Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:18:41.578129Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:18:41.578159Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
  → Inspect frozen Batch A criteria and exact commit diff
  • Audit implementation and tests against each acceptance item
  • Run read-only verification and reconcile delegated review
  • Issue binary PASS or concrete file:line issues
exec
/bin/zsh -lc 'git status --short --branch' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## elegance-run2
?? .oracle/checkins/batch-1-rev.md
?? .oracle/checkins/batch-1-rev2.md
?? .oracle/checkins/batch-1.md

exec
/bin/zsh -lc 'git diff --name-status 4a16fc64..2b60f74a' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	Makefile
M	scripts/check_b02_rich_preservation.py
A	scripts/migrate_external_workflow_corpus.py
A	tests/fixtures/b02_corpus_mini/001cd1f527f7f288.layout.json
A	tests/fixtures/b02_corpus_mini/42188130f0d8021b.json
A	tests/fixtures/b02_corpus_mini/90a1d5ff9044902e.json
A	tests/fixtures/b02_corpus_mini/bbb556b30438a62c.json
M	tests/test_b02_rich_preservation.py
M	tests/test_ingest_external_workflows.py
M	tests/test_porting_normalize_ingest.py

exec
/bin/zsh -lc 'git diff --stat 4a16fc64..2b60f74a' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 Makefile                                           |   18 +-
 scripts/check_b02_rich_preservation.py             |  130 +-
 scripts/migrate_external_workflow_corpus.py        |  388 +++++
 .../b02_corpus_mini/001cd1f527f7f288.layout.json   |  432 +++++
 .../fixtures/b02_corpus_mini/42188130f0d8021b.json |  523 +++++++
 .../fixtures/b02_corpus_mini/90a1d5ff9044902e.json | 1647 ++++++++++++++++++++
 .../fixtures/b02_corpus_mini/bbb556b30438a62c.json |  409 +++++
 tests/test_b02_rich_preservation.py                |  119 +-
 tests/test_ingest_external_workflows.py            |    4 +-
 tests/test_porting_normalize_ingest.py             |   18 +-
 10 files changed, 3642 insertions(+), 46 deletions(-)

exec
/bin/zsh -lc 'git diff 4a16fc64..2b60f74a -- Makefile' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/Makefile b/Makefile
index a8c17d09..b49f2709 100644
--- a/Makefile
+++ b/Makefile
@@ -104,11 +104,13 @@ ROOT_BANNED := \
 	version_matrix.json \
 	workflow_corpus
 
-.PHONY: all check ci install-dev install-ci prune-empty-runtime-root root-clean post-root-clean docs template-index templates strict-ready fast full-pytest snapshots oracle browser-contracts browser-smoke parity e2e-browser e2e-preview corrective-trust-gate-preflight corrective-trust-gate clean clean-artifacts
+B02_MINI_CORPUS := tests/fixtures/b02_corpus_mini
+
+.PHONY: all check ci install-dev install-ci prune-empty-runtime-root root-clean post-root-clean docs template-index templates strict-ready fast full-pytest snapshots oracle b02-corpus-mini b02-corpus-full browser-contracts browser-smoke parity e2e-browser e2e-preview corrective-trust-gate-preflight corrective-trust-gate clean clean-artifacts
 
 all: check
 
-check: root-clean docs template-index templates strict-ready fast snapshots oracle browser-smoke parity post-root-clean
+check: root-clean docs template-index templates strict-ready fast snapshots oracle b02-corpus-mini browser-smoke parity post-root-clean
 
 ci: check
 
@@ -177,6 +179,18 @@ oracle:
 	VIBECOMFY_COMFY_SMOKE=1 $(PYTEST) -q --tb=short \
 		tests/test_porting_ui_emitter.py::test_layer3_corpus_wide_convert_ui_to_api_gate
 
+b02-corpus-mini:
+	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
+		--corpus-dir "$(B02_MINI_CORPUS)" --expected-count 3
+
+b02-corpus-full:
+	@if [ -z "$(CORPUS_DIR)" ]; then \
+		echo "CORPUS_DIR is required (no default full-corpus path)."; \
+		exit 2; \
+	fi
+	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
+		--corpus-dir "$(CORPUS_DIR)" --expected-count 2825
+
 browser-smoke:
 	$(NODE) --test tests/browser/*.mjs
 

exec
/bin/zsh -lc 'sed -n 1,240p .oracle/tasklist.md' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
## Batch A — Canonical corpus migration `[XHARD]`

Tasks:

1. Add `scripts/migrate_external_workflow_corpus.py`.

   - Require explicit `--corpus-dir`; no repository-relative default.
   - Fail closed if the directory is absent or contains zero envelopes.
   - Process `*.json` except `*.layout.json`; reject sidecars if explicitly supplied.
   - Decode only with `from_envelope()`, serialize only with `to_envelope()` and `sort_keys=True`.
   - Stage every output before any replacement.
   - Allow exactly:
     - add `groups: []` where absent;
     - remove `compiled_api`;
     - add integer first-class `node.mode`.
   - Preserve all metadata and `_ui` content exactly, including legacy mode copies.
   - Emit a machine-readable per-file delta report; support check-only and explicit write modes.

2. Run migration against the absolute corpus path in the main checkout, never the worktree-local ignored path.

   - Migrate exactly 2,797 envelopes.
   - Leave both `*.layout.json` sidecars, filenames, manifest, and shadow data untouched.
   - Confirm 135,385 explicit modes; 754 formerly missing modes become `0`.

3. Harden `check_b02_rich_preservation.py`.

   - Require an explicit corpus directory and fail on missing/empty input.
   - Read first-class mode first with legacy fallback.
   - Use `from_envelope()` for corpus envelopes and `from_api()` for normalized API dictionaries.
   - Put groups on `wf.groups`; stop passing `groups=`.
   - Report checked/skipped counts, including two skipped sidecars.

4. Re-anchor corpus tests around derived execution state.

   - Remove `compiled_api` assumptions.
   - Preserve legacy metadata assertions rather than requiring deletion.
   - Prove execution is freshly derived by `compile("api")`.
   - Add missing/empty-directory and layout-sidecar rejection tests.

5. Make CI non-vacuous without importing the 466 MB corpus.

   - Add a small tracked representative envelope fixture directory.
   - Make the maintained `make check`/`make ci` path call the checker with that explicit directory and expected nonzero count.
   - Add a separate full-corpus target requiring explicit `CORPUS_DIR` and expected count `2797`; no fallback path.

6. Scope cuts:

   - Do not repair or rewrite the manifest. Record `355b418f7449ba25.json` as known pre-existing drift.
   - Do not upload to Hivemind and do not add upsert support. Existing rows may retain old payloads; summaries are unaffected.

Acceptance gate:

- 2,797 envelopes and two untouched layout sidecars.
- Unchanged filenames and canonical execution hashes.
- Every envelope decodes; second migration run reports zero changes.
- Delta report contains only the three permitted transformations.
- Metadata and `_ui` are unchanged.
- No envelope contains `compiled_api`; every node has integer `mode`.
- Full B02 reports zero mismatches and zero UID-less emissions.
- Missing/empty corpus checks fail.
- Focused corpus tests, `git diff --check`, and `make ci` pass.

## Batch B — Remove the public dispatcher

Tasks:

1. Remove only `convert_to_vibe_format()` from `ingest/normalize.py` and its public export. Keep the normalization module and private `_named_import()`.

2. Migrate the verified callers:

   - `from_api()`:
     - `registry/ready_template.py`
     - both paths in `tools/format_as_python.py`
     - `tools/convert_ready_templates.py`
     - `porting/edit/_gates.py`
     - API route in `comfy_nodes/agent/routes.py`
     - `scripts/ingest_external_workflows.py`
     - API path in `check_b02_rich_preservation.py`
   - `from_ui()`:
     - UI route in `comfy_nodes/agent/routes.py`
     - `demo_factory/fixer.py`
   - `from_envelope()`:
     - `comfy_nodes/agent/graph_normalization.py`
     - corpus path in `check_b02_rich_preservation.py`
   - `_frag_ingest.py`:
     - branch with `_is_vibe_envelope(raw)`;
     - envelope → `from_envelope()`, otherwise → `from_api()`.
   - `scratchpad_loader.py`:
     - rewrite both generated source strings and generated imports to use `from_api()`.

3. Leave loader boundaries unchanged.

   - `_named_import()` remains for raw dictionaries of unknown shape.
   - Ready-ID and `.py` paths continue bypassing it.
   - `workbench.py` is not a dispatcher caller and receives no migration edit.

4. Update live comments/docs and mechanically migrate affected tests. Re-anchor equivalence tests on IDs, UIDs, classes, modes, groups, edges, and compiled output.

Acceptance gate:

- `rg 'convert_to_vibe_format' --glob '*.py'` finds only an intentional negative guard.
- `vibecomfy.ingest` exposes `from_envelope`, `from_ui`, and `from_api`, not the removed dispatcher.
- `_named_import()` still handles ambiguous raw JSON/image-loader inputs.
- Generated scratchpad code imports and calls `from_api()`.
- Offline routes remain offline.
- Focused ingest, loader, security, ready-template, scratchpad, porting, and B02 tests pass.

## Batch D+E — IR-authoritative emission and groups `[XHARD]`

Tasks:

1. Make `_resolve_furniture()` obtain mode only through `_get_node_mode(node)`.

   - Sidecars and top-level metadata retain authority for flags, colors, properties, title, and geometry—not mode.
   - Keep the single legacy `_ui.mode` fallback inside `_get_node_mode()`.

2. Remove the `groups` parameter from `emit_ui_json()` and all seven callers/tests.

3. Reconcile groups into the IR immediately after `_resolve_preserve_source()`.

   - If the selected preserve store contains groups, deep-copy them into `workflow.groups`.
   - Otherwise retain the groups already present on the workflow.
   - Preserve existing fresh/sidecar/`--from`/breadcrumb precedence.

4. Remap group membership during emission.

   - Build aliases from workflow node ID, numeric source ID, `node.uid`, and captured `_ui.id`.
   - Map known group members to final LiteGraph integers through `id_remap`.
   - Preserve member order and group metadata.
   - Deterministically omit stale/unresolved members rather than emitting dangling IDs.
   - Merge IR groups before engine-generated groups and retain title deduplication.

5. Make `write_layout()` serialize `wf.groups`, not `wf.metadata["groups"]`.

Acceptance gate:

- Compile and emit agree for modes 0/2/4 despite conflicting sidecar or metadata values.
- Raw source-ID and UID-based group members both emit as correct LiteGraph integers.
- No emitted group contains dangling/string membership for emitted nodes.
- Sidecar-only, `--from`, conflict, breadcrumb, `--fresh`, removed-node, and nonnumeric-node-ID cases pass.
- `port convert` writes reconciled groups onto `wf.groups`.
- No `emit_ui_json(..., groups=...)` calls or signature remain.
- Focused port, emitter, layout, CLI, and B02 tests pass.

## Batch C — First-class geometry `[XHARD]`

Tasks:

1. Add `VibeNode.pos` and `VibeNode.size` as separate `list[float] | None` fields.

   - Each present value must contain exactly two finite numeric coordinates.
   - Absence remains `None`; never synthesize geometry.
   - Versioned envelopes reject malformed present values.
   - UI/API ingestion tolerates absent or malformed geometry by leaving the first-class field absent while retaining raw `_ui`.

2. Ingest/decode behavior:

   - UI/API ingest copies valid `_ui.pos` and `_ui.size`.
   - Envelope decode prefers node-level fields, falling back independently to legacy `_ui`.
   - First-class values win conflicts.

3. Replace geometry descents in:

   - layout-store writing;
   - lowering clones and offsets;
   - virtual-wire capture;
   - nearest-node reconciliation;
   - UI captured geometry/emission.
   - Explicitly copy `mode`, `pos`, and `size` in lowering’s manual constructor.

4. Leave the non-geometry `_ui` hash access in `layout/reconcile.py` unchanged.

5. Do not regenerate the corpus again.

Acceptance gate:

- Live and offline UI ingestion produce identical first-class geometry.
- Old and new envelopes round-trip functionally; first-class values win.
- Copies are deep and compile output is geometry-invariant.
- Missing size still triggers the existing stub-layout behavior.
- Lowering, virtual wires, reconcile matching, sidecars, and emitted coordinate canonicalization remain stable.
- Focused geometry suite, B02, `make ci`, and full pytest pass.

## Batch K — Declare the workflow context token

Tasks:

1. Add:

   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`

2. Replace token-related `getattr`, `hasattr`, creation, and deletion with direct assignment/access.

3. Make `copy()` handle bound workflows by supplying a deepcopy memo that maps the active `contextvars.Token` to `None`. Every clone must be unbound.

Acceptance gate:

- Bound and unbound copies succeed and have token `None`.
- Constructor, repr, equality, and envelope omit the field.
- Enter/exit, eager binding, finalize, nesting rejection, exception cleanup, and async isolation pass.
- No context token leaks into serialization.

## Checkpoint structure

After each batch:

1. Commit only that batch.
2. Submit the task excerpt, diff from the prior passed checkpoint, test output, and implementation deviations to the oracle.
3. For Batch A, also attach the external-corpus delta report, counts, and before/after canonical hashes because the corpus is outside the worktree diff.
4. Oracle returns `PASS` or concrete issues.
5. Rework and resubmit until `PASS`; record the passed SHA under `.oracle/checkins/`.
6. `[XHARD]` work goes to GPT-5.6 Sol; other implementation work goes to DeepSeek Flash.

## Final release gate

- Full-corpus migration check with explicit absolute path and expected count `2797`.
- Full B02 check against that same path.
- `make ci`
- `make full-pytest`
- `git diff --check`
- Static guards for:
  - removed dispatcher;
  - removed `groups=` emitter surface;
  - sidecar/metadata mode authority in emission;
  - remaining geometry descents outside approved ingest/hash fallbacks.
- Verify manifest and Hivemind were not mutated.
- Final oracle review of the complete branch diff plus the external-corpus report.

Explicitly deferred: manifest repair, Hivemind payload refresh/upsert, tracking the 466 MB corpus, id-map redesign, typed groups/metadata, mode enum/sentinel redesign, slots, JS consumers, and full compile/emit unification.

**New exploration areas:** none.
tokens used
52,078
# Revised frozen plan

Execution order: **A → B → D+E → C → K → release gate**. Do not begin a batch until its checkpoint passes.


exec
/bin/zsh -lc 'nl -ba scripts/migrate_external_workflow_corpus.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
     1	"""Canonically migrate serialized VibeWorkflow corpus envelopes.
     2	
     3	Only three schema changes are permitted: add a missing top-level ``groups``
     4	list, remove top-level ``compiled_api``, and add a missing integer first-class
     5	``mode`` to each node. Every output is staged and validated before write mode
     6	replaces a single source file.
     7	"""
     8	
     9	from __future__ import annotations
    10	
    11	import argparse
    12	import hashlib
    13	import json
    14	import os
    15	import shutil
    16	import sys
    17	import tempfile
    18	from copy import deepcopy
    19	from pathlib import Path
    20	from typing import Any
    21	
    22	from vibecomfy.ingest import from_envelope
    23	from vibecomfy.testing.canonical import canonical_form
    24	
    25	
    26	def _json_pointer(parts: tuple[str, ...]) -> str:
    27	    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)
    28	
    29	
    30	def _diff_keys(
    31	    before: Any,
    32	    after: Any,
    33	    parts: tuple[str, ...] = (),
    34	) -> tuple[list[str], list[str], list[str]]:
    35	    """Return recursively added, removed, and changed JSON-pointer keys."""
    36	    if isinstance(before, dict) and isinstance(after, dict):
    37	        added: list[str] = []
    38	        removed: list[str] = []
    39	        changed: list[str] = []
    40	        before_keys = set(before)
    41	        after_keys = set(after)
    42	        added.extend(_json_pointer(parts + (str(key),)) for key in sorted(after_keys - before_keys))
    43	        removed.extend(_json_pointer(parts + (str(key),)) for key in sorted(before_keys - after_keys))
    44	        for key in sorted(before_keys & after_keys):
    45	            child_added, child_removed, child_changed = _diff_keys(
    46	                before[key], after[key], parts + (str(key),)
    47	            )
    48	            added.extend(child_added)
    49	            removed.extend(child_removed)
    50	            changed.extend(child_changed)
    51	        return added, removed, changed
    52	    if before != after:
    53	        return [], [], [_json_pointer(parts)]
    54	    return [], [], []
    55	
    56	
    57	def _canonical_hash(api: dict[str, Any]) -> str:
    58	    canonical = canonical_form(api)
    59	    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    60	    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    61	
    62	
    63	def _execution_hash(raw: dict[str, Any], *, prefer_stored: bool) -> tuple[str, str]:
    64	    """Hash stored pre-migration evidence when present, otherwise compile fresh."""
    65	    if prefer_stored and "compiled_api" in raw:
    66	        api = raw["compiled_api"]
    67	        if not isinstance(api, dict):
    68	            raise ValueError("compiled_api must be a mapping when present")
    69	        return _canonical_hash(api), "compiled_api"
    70	    return _canonical_hash(from_envelope(raw).compile("api")), "compile(api)"
    71	
    72	
    73	def _file_hash(path: Path) -> str:
    74	    digest = hashlib.sha256()
    75	    with path.open("rb") as handle:
    76	        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
    77	            digest.update(chunk)
    78	    return digest.hexdigest()
    79	
    80	
    81	def _corpus_files(corpus_dir: Path) -> tuple[list[Path], list[Path]]:
    82	    if corpus_dir.name.endswith(".layout.json"):
    83	        raise ValueError(f"layout sidecar cannot be migrated explicitly: {corpus_dir}")
    84	    if not corpus_dir.exists():
    85	        raise FileNotFoundError(f"corpus directory does not exist: {corpus_dir}")
    86	    if not corpus_dir.is_dir():
    87	        raise NotADirectoryError(f"corpus path is not a directory: {corpus_dir}")
    88	    json_paths = sorted(corpus_dir.glob("*.json"))
    89	    sidecars = [path for path in json_paths if path.name.endswith(".layout.json")]
    90	    envelopes = [path for path in json_paths if not path.name.endswith(".layout.json")]
    91	    if not envelopes:
    92	        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
    93	    return envelopes, sidecars
    94	
    95	
    96	def _migrate_envelope(raw: dict[str, Any], *, filename: str) -> tuple[dict[str, Any], dict[str, Any]]:
    97	    if not isinstance(raw, dict):
    98	        raise ValueError(f"{filename}: envelope must be a JSON object")
    99	    raw_nodes = raw.get("nodes")
   100	    if not isinstance(raw_nodes, dict) or "vibecomfy_format_version" not in raw:
   101	        raise ValueError(f"{filename}: JSON file is not a serialized VibeWorkflow envelope")
   102	
   103	    workflow = from_envelope(raw)
   104	
   105	    # The external-ingest boundary deliberately stamps provenance and an ingest
   106	    # snapshot. Corpus migration is schema-only, so restore all raw metadata
   107	    # before the sole serializer walks the IR.
   108	    workflow.metadata = deepcopy(raw.get("metadata") or {})
   109	    for node_id, node in workflow.nodes.items():
   110	        node.metadata = deepcopy(raw_nodes[node_id]["metadata"])
   111	
   112	    migrated = workflow.to_envelope()
   113	
   114	    if migrated.get("metadata") != raw.get("metadata"):
   115	        raise ValueError(f"{filename}: top-level metadata changed during serialization")
   116	    for node_id, entry in raw_nodes.items():
   117	        if migrated["nodes"][node_id].get("metadata") != entry.get("metadata"):
   118	            raise ValueError(f"{filename}: node {node_id!r} metadata/_ui changed")
   119	
   120	    added, removed, changed = _diff_keys(raw, migrated)
   121	    allowed_added = {"/groups"}
   122	    allowed_added.update(
   123	        _json_pointer(("nodes", str(node_id), "mode"))
   124	        for node_id, entry in raw_nodes.items()
   125	        if "mode" not in entry
   126	    )
   127	    allowed_removed = {"/compiled_api"} if "compiled_api" in raw else set()
   128	
   129	    unexpected_added = sorted(set(added) - allowed_added)
   130	    unexpected_removed = sorted(set(removed) - allowed_removed)
   131	    if unexpected_added or unexpected_removed or changed:
   132	        raise ValueError(
   133	            f"{filename}: serializer produced forbidden delta: "
   134	            f"added={unexpected_added}, removed={unexpected_removed}, changed={changed}"
   135	        )
   136	    if "/groups" in added and migrated.get("groups") != []:
   137	        raise ValueError(f"{filename}: missing groups must migrate to []")
   138	    if "/compiled_api" in removed and "compiled_api" in migrated:
   139	        raise ValueError(f"{filename}: compiled_api was not removed")
   140	
   141	    modes_added = 0
   142	    modes_defaulted = 0
   143	    mode_values: dict[str, int] = {}
   144	    for node_id, entry in migrated["nodes"].items():
   145	        mode = entry.get("mode")
   146	        if not isinstance(mode, int) or isinstance(mode, bool):
   147	            raise ValueError(f"{filename}: node {node_id!r} mode is not an integer: {mode!r}")
   148	        if "mode" not in raw_nodes[node_id]:
   149	            modes_added += 1
   150	            old_metadata = raw_nodes[node_id].get("metadata") or {}
   151	            old_ui = old_metadata.get("_ui") if isinstance(old_metadata, dict) else None
   152	            ui_mode = old_ui.get("mode") if isinstance(old_ui, dict) else None
   153	            metadata_mode = old_metadata.get("mode") if isinstance(old_metadata, dict) else None
   154	            has_legacy_mode = (
   155	                isinstance(ui_mode, int) and not isinstance(ui_mode, bool)
   156	            ) or (
   157	                isinstance(metadata_mode, int) and not isinstance(metadata_mode, bool)
   158	            )
   159	            if not has_legacy_mode:
   160	                modes_defaulted += 1
   161	        mode_values[str(mode)] = mode_values.get(str(mode), 0) + 1
   162	
   163	    canonical_hash_before, canonical_hash_before_source = _execution_hash(
   164	        raw, prefer_stored=True
   165	    )
   166	    canonical_hash_after, canonical_hash_after_source = _execution_hash(
   167	        migrated, prefer_stored=False
   168	    )
   169	    if canonical_hash_before != canonical_hash_after:
   170	        raise ValueError(f"{filename}: canonical execution hash changed")
   171	
   172	    delta = {
   173	        "file": filename,
   174	        "added_keys": added,
   175	        "removed_keys": removed,
   176	        "changed_keys": changed,
   177	        "counts": {
   178	            "added_keys": len(added),
   179	            "removed_keys": len(removed),
   180	            "changed_keys": len(changed),
   181	            "nodes": len(raw_nodes),
   182	            "node_modes_added": modes_added,
   183	            "node_modes_defaulted_to_zero": modes_defaulted,
   184	            "node_mode_values_after": mode_values,
   185	        },
   186	        "transformations": {
   187	            "add_groups": int("/groups" in added),
   188	            "remove_compiled_api": int("/compiled_api" in removed),
   189	            "add_node_mode": modes_added,
   190	        },
   191	        "canonical_hash_before": canonical_hash_before,
   192	        "canonical_hash_after": canonical_hash_after,
   193	        "canonical_hash_before_source": canonical_hash_before_source,
   194	        "canonical_hash_after_source": canonical_hash_after_source,
   195	        "metadata_unchanged": True,
   196	        "ui_unchanged": True,
   197	        "permitted_transformations_only": True,
   198	        "would_change": bool(added or removed or changed),
   199	    }
   200	    return migrated, delta
   201	
   202	
   203	def _stage_report(report_path: Path, report_text: str) -> Path:
   204	    report_path.parent.mkdir(parents=True, exist_ok=True)
   205	    descriptor, name = tempfile.mkstemp(prefix=f".{report_path.name}.", dir=report_path.parent)
   206	    staged = Path(name)
   207	    try:
   208	        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
   209	            handle.write(report_text)
   210	    except Exception:
   211	        staged.unlink(missing_ok=True)
   212	        raise
   213	    return staged
   214	
   215	
   216	def migrate_corpus(
   217	    corpus_dir: str | Path,
   218	    *,
   219	    write: bool,
   220	    report_path: str | Path | None = None,
   221	    expected_count: int | None = None,
   222	) -> dict[str, Any]:
   223	    root = Path(corpus_dir).resolve()
   224	    envelopes, sidecars = _corpus_files(root)
   225	    if expected_count is not None and len(envelopes) != expected_count:
   226	        raise ValueError(
   227	            f"expected {expected_count} envelopes, found {len(envelopes)} in {root}"
   228	        )
   229	    resolved_report = Path(report_path).resolve() if report_path is not None else None
   230	    if resolved_report is not None and resolved_report.parent == root:
   231	        raise ValueError("delta report must be written outside the corpus directory")
   232	
   233	    sidecar_hashes = {path.name: _file_hash(path) for path in sidecars}
   234	    stage_dir: Path | None = None
   235	    backup_dir: Path | None = None
   236	    staged_report: Path | None = None
   237	    write_committed = False
   238	    deltas: list[dict[str, Any]] = []
   239	    total_nodes = 0
   240	    modes_before = 0
   241	    modes_after = 0
   242	    modes_added = 0
   243	    modes_defaulted = 0
   244	    mode_values_after: dict[str, int] = {}
   245	
   246	    if write:
   247	        stage_dir = Path(tempfile.mkdtemp(prefix=".vibecomfy-corpus-stage-", dir=root.parent))
   248	
   249	    try:
   250	        for path in envelopes:
   251	            raw = json.loads(path.read_text(encoding="utf-8"))
   252	            raw_nodes = raw.get("nodes") if isinstance(raw, dict) else None
   253	            if isinstance(raw_nodes, dict):
   254	                total_nodes += len(raw_nodes)
   255	                modes_before += sum("mode" in entry for entry in raw_nodes.values() if isinstance(entry, dict))
   256	            migrated, delta = _migrate_envelope(raw, filename=path.name)
   257	            modes_after += len(migrated["nodes"])
   258	            modes_added += delta["counts"]["node_modes_added"]
   259	            modes_defaulted += delta["counts"]["node_modes_defaulted_to_zero"]
   260	            for mode, count in delta["counts"]["node_mode_values_after"].items():
   261	                mode_values_after[mode] = mode_values_after.get(mode, 0) + count
   262	            deltas.append(delta)
   263	            if stage_dir is not None:
   264	                serialized = json.dumps(migrated, indent=2, sort_keys=True) + "\n"
   265	                (stage_dir / path.name).write_text(serialized, encoding="utf-8")
   266	
   267	        report = {
   268	            "schema_version": 1,
   269	            "mode": "write" if write else "check",
   270	            "corpus_dir": str(root),
   271	            "ok": True,
   272	            "summary": {
   273	                "envelopes": len(envelopes),
   274	                "expected_count": expected_count,
   275	                "count_matches": expected_count is None or len(envelopes) == expected_count,
   276	                "sidecars_untouched": len(sidecars),
   277	                "files_would_change": sum(delta["would_change"] for delta in deltas),
   278	                "nodes": total_nodes,
   279	                "node_modes_before": modes_before,
   280	                "node_modes_added": modes_added,
   281	                "node_modes_defaulted_to_zero": modes_defaulted,
   282	                "node_modes_after": modes_after,
   283	                "node_mode_values_after": mode_values_after,
   284	                "groups_added": sum(delta["transformations"]["add_groups"] for delta in deltas),
   285	                "compiled_api_removed": sum(
   286	                    delta["transformations"]["remove_compiled_api"] for delta in deltas
   287	                ),
   288	                "canonical_hashes_unchanged": sum(
   289	                    delta["canonical_hash_before"] == delta["canonical_hash_after"]
   290	                    for delta in deltas
   291	                ),
   292	                "filenames_unchanged": True,
   293	                "metadata_unchanged": sum(delta["metadata_unchanged"] for delta in deltas),
   294	                "ui_unchanged": sum(delta["ui_unchanged"] for delta in deltas),
   295	                "permitted_transformations_only": all(
   296	                    delta["permitted_transformations_only"] for delta in deltas
   297	                ),
   298	            },
   299	            "sidecars": [
   300	                {
   301	                    "file": path.name,
   302	                    "sha256_before": sidecar_hashes[path.name],
   303	                    "sha256_after": sidecar_hashes[path.name],
   304	                    "untouched": True,
   305	                }
   306	                for path in sidecars
   307	            ],
   308	            "files": deltas,
   309	        }
   310	        report_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
   311	        if resolved_report is not None:
   312	            staged_report = _stage_report(resolved_report, report_text)
   313	
   314	        if write:
   315	            assert stage_dir is not None
   316	            staged_names = sorted(path.name for path in stage_dir.glob("*.json"))
   317	            source_names = sorted(path.name for path in envelopes)
   318	            if staged_names != source_names:
   319	                raise RuntimeError("staged output filenames do not exactly match corpus envelopes")
   320	
   321	            # Hard-linked originals make the entire set recoverable if any
   322	            # replacement fails, without duplicating another 466 MB.
   323	            backup_dir = Path(tempfile.mkdtemp(prefix=".vibecomfy-corpus-backup-", dir=root.parent))
   324	            for path in envelopes:
   325	                os.link(path, backup_dir / path.name)
   326	            try:
   327	                for path in envelopes:
   328	                    os.replace(stage_dir / path.name, path)
   329	            except Exception:
   330	                for path in envelopes:
   331	                    backup = backup_dir / path.name
   332	                    if backup.exists():
   333	                        os.replace(backup, path)
   334	                raise
   335	
   336	            for path in sidecars:
   337	                if _file_hash(path) != sidecar_hashes[path.name]:
   338	                    raise RuntimeError(f"layout sidecar changed unexpectedly: {path.name}")
   339	
   340	        if resolved_report is not None:
   341	            assert staged_report is not None
   342	            os.replace(staged_report, resolved_report)
   343	            staged_report = None
   344	        else:
   345	            sys.stdout.write(report_text)
   346	        write_committed = write
   347	        return report
   348	    finally:
   349	        if backup_dir is not None and not write_committed:
   350	            for path in envelopes:
   351	                backup = backup_dir / path.name
   352	                if backup.exists():
   353	                    os.replace(backup, path)
   354	        if staged_report is not None:
   355	            staged_report.unlink(missing_ok=True)
   356	        if stage_dir is not None:
   357	            shutil.rmtree(stage_dir, ignore_errors=True)
   358	        if backup_dir is not None:
   359	            shutil.rmtree(backup_dir, ignore_errors=True)
   360	
   361	
   362	def main(argv: list[str] | None = None) -> int:
   363	    parser = argparse.ArgumentParser(description=__doc__)
   364	    parser.add_argument("--corpus-dir", required=True, help="explicit corpus directory")
   365	    mode = parser.add_mutually_exclusive_group(required=True)
   366	    mode.add_argument("--check", action="store_true", help="report changes without writing")
   367	    mode.add_argument("--write", action="store_true", help="transactionally replace all envelopes")
   368	    parser.add_argument("--report", help="write the JSON delta report outside the corpus directory")
   369	    parser.add_argument(
   370	        "--expected-count",
   371	        type=int,
   372	        help="fail before staging unless exactly this many envelopes exist",
   373	    )
   374	    args = parser.parse_args(argv)
   375	    try:
   376	        migrate_corpus(
   377	            args.corpus_dir,
   378	            write=args.write,
   379	            report_path=args.report,
   380	            expected_count=args.expected_count,
   381	        )
   382	    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
   383	        parser.error(str(exc))
   384	    return 0
   385	
   386	
   387	if __name__ == "__main__":
   388	    sys.exit(main())

exec
/bin/zsh -lc 'nl -ba scripts/check_b02_rich_preservation.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'nl -ba tests/test_b02_rich_preservation.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
     1	"""B02-C4 — corpus-wide rich-preservation proof tests.
     2	
     3	Executes :mod:`scripts.check_b02_rich_preservation` over a tracked mini corpus
     4	of real, migrated serialized-Vibe envelopes and asserts the preservation proof
     5	holds: zero projection mismatches and zero uid-less emissions. The full ignored
     6	corpus is exercised explicitly by ``make b02-corpus-full CORPUS_DIR=...``.
     7	
     8	A synthetic rich envelope with nonempty groups and real link/edge topology
     9	proves the groups and semantic link projections survive the pipeline and that
    10	the checker's projections are not vacuous (a corrupted copy is detected).
    11	"""
    12	
    13	from __future__ import annotations
    14	
    15	import functools
    16	import json
    17	import shutil
    18	from copy import deepcopy
    19	from pathlib import Path
    20	from typing import Any
    21	
    22	import pytest
    23	
    24	from scripts import check_b02_rich_preservation as b02
    25	from scripts import migrate_external_workflow_corpus as migrate
    26	from vibecomfy.ingest import from_envelope
    27	
    28	
    29	MINI_CORPUS = Path(__file__).parent / "fixtures" / "b02_corpus_mini"
    30	
    31	
    32	# ---------------------------------------------------------------------------
    33	# Corpus-wide proof (module-scoped cache: traverse the corpus exactly once)
    34	# ---------------------------------------------------------------------------
    35	
    36	
    37	@functools.lru_cache(maxsize=1)
    38	def _corpus_summary() -> dict[str, Any]:
    39	    return b02.check_corpus(MINI_CORPUS, expected_count=3)
    40	
    41	
    42	def _failure_digest(summary: dict[str, Any], limit: int = 25) -> str:
    43	    by_axis = ", ".join(
    44	        f"{axis}={count}"
    45	        for axis, count in sorted(summary["mismatches_by_axis"].items())
    46	    )
    47	    rows = "\n".join(
    48	        f"  {row[0]} [{row[1]}] node={row[2]}: expected {row[3]!r} got {row[4]!r}"
    49	        for row in summary["mismatch_rows"][:limit]
    50	    )
    51	    more = (
    52	        f"\n  ... and {len(summary['mismatch_rows']) - limit} more"
    53	        if len(summary["mismatch_rows"]) > limit
    54	        else ""
    55	    )
    56	    return (
    57	        f"workflows={summary['workflows']} "
    58	        f"mismatches={summary['mismatch_count']} ({by_axis}) "
    59	        f"uidless={summary['uidless']} refused_files={len(summary['refused_files'])}\n"
    60	        f"{rows}{more}"
    61	    )
    62	
    63	
    64	@pytest.mark.timeout(900)
    65	def test_corpus_rich_preservation_zero_mismatches() -> None:
    66	    """The entire corpus round-trips rich→IR→canonical→re-ingest→re-emit with
    67	    zero projection mismatches on every asserted axis."""
    68	    summary = _corpus_summary()
    69	    assert summary["mismatch_count"] == 0, _failure_digest(summary)
    70	
    71	
    72	@pytest.mark.timeout(900)
    73	def test_corpus_zero_uidless_emissions() -> None:
    74	    """No emitted canonical node may carry a blank/missing properties.vibecomfy_uid."""
    75	    summary = _corpus_summary()
    76	    assert summary["uidless"] == 0, _failure_digest(summary)
    77	
    78	
    79	def test_mini_corpus_is_first_class_and_execution_is_freshly_derived() -> None:
    80	    envelopes = list(b02.iter_corpus(MINI_CORPUS))
    81	    assert len(envelopes) == 3
    82	    for _path, raw in envelopes:
    83	        assert "compiled_api" not in raw
    84	        assert isinstance(raw["groups"], list)
    85	        assert all(
    86	            isinstance(entry.get("mode"), int) and not isinstance(entry["mode"], bool)
    87	            for entry in raw["nodes"].values()
    88	        )
    89	        # Legacy UI evidence remains in place even though first-class mode is authoritative.
    90	        for entry in raw["nodes"].values():
    91	            ui = entry.get("metadata", {}).get("_ui")
    92	            if isinstance(ui, dict) and "mode" in ui:
    93	                assert ui["mode"] == entry["mode"]
    94	        derived_api = from_envelope(raw).compile("api")
    95	        assert isinstance(derived_api, dict)
    96	        assert derived_api
    97	
    98	
    99	def test_checker_reports_checked_and_skipped_sidecar_counts() -> None:
   100	    summary = _corpus_summary()
   101	    assert summary["checked"] == 3
   102	    assert summary["skipped"] == 1
   103	    assert summary["skipped_sidecars"] == 1
   104	
   105	
   106	def test_checker_rejects_missing_and_empty_corpus_dirs(tmp_path: Path) -> None:
   107	    with pytest.raises(FileNotFoundError, match="does not exist"):
   108	        b02.check_corpus(tmp_path / "missing")
   109	    empty = tmp_path / "empty"
   110	    empty.mkdir()
   111	    with pytest.raises(ValueError, match="zero envelopes"):
   112	        b02.check_corpus(empty)
   113	
   114	
   115	def test_migrator_rejects_missing_empty_and_explicit_sidecar(tmp_path: Path) -> None:
   116	    with pytest.raises(FileNotFoundError, match="does not exist"):
   117	        migrate.migrate_corpus(tmp_path / "missing", write=False)
   118	    empty = tmp_path / "empty"
   119	    empty.mkdir()
   120	    with pytest.raises(ValueError, match="zero envelopes"):
   121	        migrate.migrate_corpus(empty, write=False)
   122	    sidecar = MINI_CORPUS / "001cd1f527f7f288.layout.json"
   123	    with pytest.raises(ValueError, match="sidecar cannot be migrated explicitly"):
   124	        migrate.migrate_corpus(sidecar, write=False)
   125	    with pytest.raises(ValueError, match="expected 2797 envelopes, found 3"):
   126	        migrate.migrate_corpus(MINI_CORPUS, write=False, expected_count=2797)
   127	
   128	
   129	def test_migrator_check_is_idempotent_on_mini_corpus(tmp_path: Path) -> None:
   130	    report_path = tmp_path / "delta.json"
   131	    report = migrate.migrate_corpus(
   132	        MINI_CORPUS,
   133	        write=False,
   134	        report_path=report_path,
   135	        expected_count=3,
   136	    )
   137	    assert report["summary"]["files_would_change"] == 0
   138	    assert report["summary"]["node_modes_after"] == 20
   139	    assert sum(report["summary"]["node_mode_values_after"].values()) == 20
   140	    assert report["summary"]["sidecars_untouched"] == 1
   141	    assert json.loads(report_path.read_text(encoding="utf-8")) == report
   142	
   143	
   144	def test_migrator_write_preserves_metadata_sidecar_and_is_idempotent(tmp_path: Path) -> None:
   145	    corpus = tmp_path / "corpus"
   146	    shutil.copytree(MINI_CORPUS, corpus)
   147	    envelope_path = corpus / "90a1d5ff9044902e.json"
   148	    raw = json.loads(envelope_path.read_text(encoding="utf-8"))
   149	    metadata_before = deepcopy(raw["metadata"])
   150	    node_metadata_before = {
   151	        node_id: deepcopy(entry["metadata"])
   152	        for node_id, entry in raw["nodes"].items()
   153	    }
   154	    raw.pop("groups")
   155	    for entry in raw["nodes"].values():
   156	        entry.pop("mode")
   157	    raw["compiled_api"] = from_envelope(raw).compile("api")
   158	    envelope_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
   159	    sidecar = corpus / "001cd1f527f7f288.layout.json"
   160	    sidecar_before = sidecar.read_bytes()
   161	
   162	    first = migrate.migrate_corpus(corpus, write=True, report_path=tmp_path / "write.json")
   163	    assert first["summary"]["files_would_change"] == 1
   164	    written = json.loads(envelope_path.read_text(encoding="utf-8"))
   165	    assert "compiled_api" not in written
   166	    assert written["groups"] == []
   167	    assert written["metadata"] == metadata_before
   168	    assert {
   169	        node_id: entry["metadata"] for node_id, entry in written["nodes"].items()
   170	    } == node_metadata_before
   171	    assert all(isinstance(entry["mode"], int) for entry in written["nodes"].values())
   172	    assert sidecar.read_bytes() == sidecar_before
   173	
   174	    second = migrate.migrate_corpus(corpus, write=False)
   175	    assert second["summary"]["files_would_change"] == 0
   176	
   177	
   178	# ---------------------------------------------------------------------------
   179	# Synthetic envelope — non-vacuous projection proof
   180	# ---------------------------------------------------------------------------
   181	
   182	
   183	def _raw_ui_node(
   184	    node_id: int,
   185	    class_type: str,
   186	    *,
   187	    widgets_values: list[Any],
   188	    inputs: list[dict[str, Any]],
   189	    outputs: list[dict[str, Any]],
   190	) -> dict[str, Any]:
   191	    return {
   192	        "id": node_id,
   193	        "type": class_type,
   194	        "pos": [0.0, 0.0],
   195	        "size": [300.0, 100.0],
   196	        "flags": {},
   197	        "order": node_id - 1,
   198	        "mode": 4,
   199	        "inputs": inputs,
   200	        "outputs": outputs,
   201	        "properties": {"Node name for S&R": class_type},
   202	        "widgets_values": widgets_values,
   203	    }
   204	
   205	
   206	def _synthetic_envelope() -> dict[str, Any]:
   207	    """A small but complete serialized-Vibe envelope: 3 nodes, 2 edges, 2 groups.
   208	
   209	    Node ids/edges deliberately mirror a real graph (LoadImage → KSampler →
   210	    VAEDecode) with nonempty widgets_values and full raw ``_ui`` payloads so the
   211	    canonicalization exercises the pin path, link renumbering, and groups
   212	    carry-forward.
   213	    """
   214	    return {
   215	        "id": "synthetic-1",
   216	        "vibecomfy_format_version": "1.0",
   217	        "source": {"id": "synthetic-1", "path": None, "source_type": "api", "provenance": {}},
   218	        "metadata": {"external_workflow": False},
   219	        "requirements": {
   220	            "models": [],
   221	            "custom_nodes": [],
   222	            "missing_models": [],
   223	            "missing_nodes": [],
   224	            "unsupported": [],
   225	        },
   226	        "strict_types": False,
   227	        "inputs": {},
   228	        "outputs": [
   229	            {
   230	                "node_id": "3",
   231	                "output_type": "VAEDecode",
   232	                "name": "IMAGE",
   233	                "artifact_kind": "image",
   234	            }
   235	        ],
   236	        "nodes": {
   237	            "1": {
   238	                "id": "1",
   239	                "class_type": "LoadImage",
   240	                "uid": "uid-1",
   241	                "pack": None,
   242	                "inputs": {},
   243	                "widgets": {},
   244	                "raw_widgets": {
   245	                    "values": ["img.png", "image"],
   246	                    "shape": "list",
   247	                    "source": "ui.widgets_values",
   248	                    "has_dict_rows": False,
   249	                    "length": 2,
   250	                },
   251	                "metadata": {
   252	                    "_ui": _raw_ui_node(
   253	                        1,
   254	                        "LoadImage",
   255	                        widgets_values=["img.png", "image"],
   256	                        inputs=[],
   257	                        outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [999], "slot_index": 0}],
   258	                    )
   259	                },
   260	            },
   261	            "2": {
   262	                "id": "2",
   263	                "class_type": "KSampler",
   264	                "uid": "uid-2",
   265	                "pack": None,
   266	                "inputs": {},
   267	                "widgets": {},
   268	                "raw_widgets": {
   269	                    "values": [42, "fixed", 20, 8, 1, "randomize"],
   270	                    "shape": "list",
   271	                    "source": "ui.widgets_values",
   272	                    "has_dict_rows": False,
   273	                    "length": 6,
   274	                },
   275	                "metadata": {
   276	                    "_ui": _raw_ui_node(
   277	                        2,
   278	                        "KSampler",
   279	                        widgets_values=[42, "fixed", 20, 8, 1, "randomize"],
   280	                        inputs=[{"name": "model", "type": "MODEL", "link": 999}],
   281	                        outputs=[{"name": "LATENT", "type": "LATENT", "links": [998], "slot_index": 0}],
   282	                    )
   283	                },
   284	            },
   285	            "3": {
   286	                "id": "3",
   287	                "class_type": "VAEDecode",
   288	                "uid": "uid-3",
   289	                "pack": None,
   290	                "inputs": {},
   291	                "widgets": {},
   292	                "raw_widgets": {
   293	                    "values": [],
   294	                    "shape": "list",
   295	                    "source": "ui.widgets_values",
   296	                    "has_dict_rows": False,
   297	                    "length": 0,
   298	                },
   299	                "metadata": {
   300	                    "_ui": _raw_ui_node(
   301	                        3,
   302	                        "VAEDecode",
   303	                        widgets_values=[],
   304	                        inputs=[{"name": "samples", "type": "LATENT", "link": 998}],
   305	                        outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
   306	                    )
   307	                },
   308	            },
   309	        },
   310	        "edges": [
   311	            {"from_node": "1", "from_output": "0", "to_node": "2", "to_input": "model"},
   312	            {"from_node": "2", "from_output": "0", "to_node": "3", "to_input": "samples"},
   313	        ],
   314	        "groups": [
   315	            {"title": "input-group", "nodes": [1, 2], "color": "#3f789e"},
   316	            {"title": "decode-group", "nodes": [3], "color": "#2c536b"},
   317	        ],
   318	    }
   319	
   320	
   321	def test_synthetic_envelope_groups_and_link_topology_survive() -> None:
   322	    """The checker's projections are exercised by real (nonempty) data: groups
   323	    and semantic link topology survive canonicalization and re-emission."""
   324	    result = b02.check_envelope(_synthetic_envelope())
   325	    assert result["mismatches"] == [], result["mismatches"]
   326	
   327	    assert result["rich_nodes"] == 3
   328	    assert result["rich_edges"] == 2
   329	    assert result["canonical_nodes"] == 3
   330	    assert result["canonical_links"] == 2
   331	    assert result["groups"] == 2
   332	    assert result["pin_opaque"] == 3, "all three schema-less full-payload nodes must pin"
   333	    assert result["uidless"] == 0
   334	
   335	    # Groups survive verbatim into the canonical projection (the checker's
   336	    # groups axis is only meaningful because nonempty groups exist here).
   337	    from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
   338	
   339	    canonical = normalize_agent_edit_graph(_synthetic_envelope())
   340	    assert canonical["groups"] == _synthetic_envelope()["groups"]
   341	
   342	    # Link endpoint+slot topology is asserted exactly: (from, from_slot, to, to_slot).
   343	    assert b02.canonical_link_topology(canonical) == {(1, 0, 2, 0), (2, 0, 3, 0)}
   344	
   345	
   346	def test_synthetic_projection_detects_corruption() -> None:
   347	    """Projection helpers are not vacuous: a dropped edge set compares unequal.
   348	
   349	    ``check_envelope`` is a self-comparison (source vs its own decode/emit).
   350	    A lossless decoder will faithfully round-trip a truncated edge list, so
   351	    the non-vacuous check is that the edge projection distinguishes the
   352	    truncated set from the intact one.
   353	    """
   354	    intact = _synthetic_envelope()
   355	    truncated = deepcopy(intact)
   356	    truncated["edges"] = [
   357	        {"from_node": "1", "from_output": "0", "to_node": "2", "to_input": "model"}
   358	    ]
   359	    assert b02.rich_edge_tuples(truncated) != b02.rich_edge_tuples(intact)
   360	    assert b02.check_envelope(intact)["mismatches"] == []

 succeeded in 32ms:
     1	"""B02-C4 — corpus-wide rich-preservation proof harness.
     2	
     3	For every serialized-Vibe envelope in ``external_workflows/corpus/*.json``
     4	(a ``vibecomfy_format_version`` + rich ``nodes`` mapping envelope), run the
     5	full canonical pipeline and prove deterministic lossless preservation at every
     6	boundary:
     7	
     8	    rich ──from_envelope──▶ ir1 ──normalize_agent_edit_graph──▶ canonical
     9	         ──normalize_to_api(use_comfy_converter=False)──▶ api ──from_api──▶ ir2
    10	         ──emit_ui_json (using ir2.groups)──▶ reemit
    11	         pin evidence: emit_ui_json(ir1, recovery_report=report)
    12	
    13	Axes asserted (every mismatch records ``(file, axis, node, expected, actual)``
    14	and fails the run):
    15	
    16	  rich→ir1            node id / class_type / stable uid / mode / raw-widgets
    17	                      values+shape+length / widgets_values / non-link furniture
    18	                      (only deterministic id/order/link-id renumbering excluded);
    19	                      edge tuples ``(from_node, from_output, to_node, to_input)``
    20	  rich→canonical      node ids / classes / modes / uids / widgets_values;
    21	                      semantic edge tuples recovered from canonical links via the
    22	                      to-node input names; groups
    23	  rich→ir2            node id / class_type / uid / mode / widgets_values; edges
    24	  canonical idempotence
    25	                      node id/class/mode/uid/widgets_values, groups, and link
    26	                      endpoint+slot topology (link ids/types excluded)
    27	  pin evidence        every ``widget_shape_verdict == "pin_opaque"`` report entry
    28	                      maps to an emitted node whose ``properties.vibecomfy_uid``
    29	                      equals the decoded canonical node uid
    30	  uidless emissions   global blank/missing ``properties.vibecomfy_uid`` count == 0
    31	
    32	Expected schema-less warnings are suppressed; exceptions are never swallowed —
    33	a pipeline refusal/exception is recorded as a ``(file, axis, ...)`` mismatch row
    34	and fails the run.
    35	
    36	Run as a CLI to get one final JSON summary on stdout:
    37	
    38	    .venv/bin/python scripts/check_b02_rich_preservation.py \
    39	        --corpus-dir tests/fixtures/b02_corpus_mini --expected-count 3
    40	
    41	Exit code is 0 iff zero mismatches and zero uid-less emissions.
    42	"""
    43	
    44	from __future__ import annotations
    45	
    46	import argparse
    47	import json
    48	import sys
    49	import warnings
    50	from copy import deepcopy
    51	from pathlib import Path
    52	from typing import Any
    53	
    54	from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
    55	from vibecomfy.ingest import from_api, from_envelope, normalize_to_api
    56	from vibecomfy.porting.emit.ui import emit_ui_json
    57	from vibecomfy.porting.refuse import RefusedEmit
    58	
    59	# Keys whose values are deterministic renumbering artifacts of the canonical
    60	# emission (node ids, draw order, link refs) — excluded from raw-UI furniture
    61	# comparisons by contract.
    62	_RENUMBERED_KEYS: frozenset[str] = frozenset({"id", "order", "link", "links"})
    63	
    64	_SCHEMA_LESS_WARNING = ".*schema-less.*"
    65	
    66	
    67	# ---------------------------------------------------------------------------
    68	# Projections
    69	# ---------------------------------------------------------------------------
    70	
    71	
    72	def _strip_renumbered(value: Any) -> Any:
    73	    """Recursively drop deterministic renumbering fields (id/order/link refs)."""
    74	    if isinstance(value, dict):
    75	        return {
    76	            key: _strip_renumbered(item)
    77	            for key, item in value.items()
    78	            if key not in _RENUMBERED_KEYS
    79	        }
    80	    if isinstance(value, list):
    81	        return [_strip_renumbered(item) for item in value]
    82	    return value
    83	
    84	
    85	def _ui_of(metadata: Any) -> dict[str, Any]:
    86	    ui = metadata.get("_ui") if isinstance(metadata, dict) else None
    87	    return ui if isinstance(ui, dict) else {}
    88	
    89	
    90	def _legacy_mode_of(metadata: Any) -> int:
    91	    """Legacy mode: raw ``_ui.mode``, then top-level metadata mode, else 0."""
    92	    ui = _ui_of(metadata)
    93	    if isinstance(ui.get("mode"), int) and not isinstance(ui["mode"], bool):
    94	        return ui["mode"]
    95	    value = metadata.get("mode")
    96	    return value if isinstance(value, int) and not isinstance(value, bool) else 0
    97	
    98	
    99	def _mode_of(entry: Any) -> int:
   100	    """First-class node mode, with legacy metadata fallback for old envelopes."""
   101	    if isinstance(entry, dict):
   102	        value = entry.get("mode")
   103	        if isinstance(value, int) and not isinstance(value, bool):
   104	            return value
   105	        return _legacy_mode_of(entry.get("metadata") or {})
   106	    value = getattr(entry, "mode", None)
   107	    if isinstance(value, int) and not isinstance(value, bool):
   108	        return value
   109	    return _legacy_mode_of(getattr(entry, "metadata", {}))
   110	
   111	
   112	def _widgets_values_of(metadata: Any) -> Any:
   113	    """Raw UI widgets_values evidence; absent/null → no evidence (nothing to preserve)."""
   114	    value = _ui_of(metadata).get("widgets_values")
   115	    return deepcopy(value) if value is not None else None
   116	
   117	
   118	def _raw_widgets_projection(raw_widgets: Any) -> dict[str, Any] | None:
   119	    """RawWidgetPayload (IR) or raw dict (envelope) → comparable projection."""
   120	    if raw_widgets is None:
   121	        return None
   122	    if not isinstance(raw_widgets, dict):
   123	        return {
   124	            "values": deepcopy(raw_widgets.values),
   125	            "shape": raw_widgets.shape,
   126	            "length": raw_widgets.length,
   127	            "has_dict_rows": raw_widgets.has_dict_rows,
   128	        }
   129	    return {
   130	        "values": deepcopy(raw_widgets.get("values")),
   131	        "shape": raw_widgets.get("shape"),
   132	        "length": raw_widgets.get("length"),
   133	        "has_dict_rows": raw_widgets.get("has_dict_rows"),
   134	    }
   135	
   136	
   137	def rich_node_projection(node_id: str, entry: dict[str, Any]) -> dict[str, Any]:
   138	    """Deterministic rich-envelope node projection (the decode input side)."""
   139	    metadata = entry.get("metadata") or {}
   140	    return {
   141	        "id": entry.get("id"),
   142	        "class_type": entry.get("class_type"),
   143	        "uid": entry.get("uid"),
   144	        "mode": _mode_of(entry),
   145	        "raw_widgets": _raw_widgets_projection(entry.get("raw_widgets")),
   146	        "widgets_values": _widgets_values_of(metadata),
   147	        "furniture": _strip_renumbered(_ui_of(metadata)),
   148	    }
   149	
   150	
   151	def ir_node_projection(node: Any) -> dict[str, Any]:
   152	    """IR (VibeNode) projection mirroring :func:`rich_node_projection`."""
   153	    metadata = node.metadata
   154	    return {
   155	        "id": node.id,
   156	        "class_type": node.class_type,
   157	        "uid": node.uid,
   158	        "mode": _mode_of(node),
   159	        "raw_widgets": _raw_widgets_projection(node.raw_widgets),
   160	        "widgets_values": _widgets_values_of(metadata),
   161	        "furniture": _strip_renumbered(_ui_of(metadata)),
   162	    }
   163	
   164	
   165	def edge_tuple(edge: Any) -> tuple[str, str, str, str]:
   166	    """Exact semantic edge tuple shared by rich envelope edges and IR edges."""
   167	    return (
   168	        str(edge.from_node),
   169	        str(edge.from_output),
   170	        str(edge.to_node),
   171	        str(edge.to_input),
   172	    )
   173	
   174	
   175	def rich_edge_tuples(rich: dict[str, Any]) -> set[tuple[str, str, str, str]]:
   176	    return {
   177	        (str(edge["from_node"]), str(edge["from_output"]), str(edge["to_node"]), str(edge["to_input"]))
   178	        for edge in rich.get("edges", [])
   179	    }
   180	
   181	
   182	def canonical_node_projection(node: dict[str, Any]) -> dict[str, Any]:
   183	    properties = node.get("properties") or {}
   184	    return {
   185	        "id": node.get("id"),
   186	        "class_type": node.get("type"),
   187	        "mode": node.get("mode", 0),
   188	        "uid": properties.get("vibecomfy_uid"),
   189	        "widgets_values": node.get("widgets_values"),
   190	    }
   191	
   192	
   193	def canonical_nodes_by_id(canonical: dict[str, Any]) -> dict[Any, dict[str, Any]]:
   194	    return {
   195	        node.get("id"): canonical_node_projection(node)
   196	        for node in canonical.get("nodes", [])
   197	    }
   198	
   199	
   200	def canonical_link_topology(canonical: dict[str, Any]) -> set[tuple[int, int, int, int]]:
   201	    """Canonical link projection: endpoint + slot topology, link ids/types excluded."""
   202	    return {
   203	        (int(link[1]), int(link[2]), int(link[3]), int(link[4]))
   204	        for link in canonical.get("links", [])
   205	    }
   206	
   207	
   208	def canonical_semantic_edges(canonical: dict[str, Any]) -> set[tuple[str, str, str, str]]:
   209	    """Recover ``(from_node, from_output, to_node, to_input)`` tuples from the
   210	    canonical envelope by resolving each link's target input name through the
   211	    to-node's emitted ``inputs`` entries (link id → name)."""
   212	    link_to_input: dict[int, tuple[str, int]] = {}
   213	    for node in canonical.get("nodes", []):
   214	        for input_entry in node.get("inputs") or []:
   215	            link_id = input_entry.get("link")
   216	            if link_id is not None:
   217	                link_to_input[int(link_id)] = (str(input_entry.get("name", "")), int(node["id"]))
   218	    tuples: set[tuple[str, str, str, str]] = set()
   219	    for link in canonical.get("links", []):
   220	        name, _ = link_to_input.get(int(link[0]), ("", int(link[3])))
   221	        tuples.add((str(link[1]), str(link[2]), str(link[3]), name))
   222	    return tuples
   223	
   224	
   225	def _canonical_id_of(rich_node_id: str) -> Any:
   226	    """Rich node id → canonical litegraph node id (numeric ids become integers)."""
   227	    return int(rich_node_id) if rich_node_id.isdigit() else rich_node_id
   228	
   229	
   230	def _record(result: dict[str, Any], axis: str, node: Any, expected: Any, actual: Any) -> None:
   231	    result["mismatches"].append((axis, node, expected, actual))
   232	
   233	
   234	def _truncate(value: Any, limit: int = 400) -> str:
   235	    text = repr(value)
   236	    return text if len(text) <= limit else text[:limit] + f"...<{len(text)} bytes>"
   237	
   238	
   239	# ---------------------------------------------------------------------------
   240	# Per-envelope check
   241	# ---------------------------------------------------------------------------
   242	
   243	
   244	def _emit(wf: Any, **kwargs: Any) -> dict[str, Any]:
   245	    """emit_ui_json wrapper: schema-less nodes warn per node; those expected
   246	    warnings are suppressed (exceptions are NOT swallowed)."""
   247	    with warnings.catch_warnings():
   248	        warnings.filterwarnings("ignore", message=_SCHEMA_LESS_WARNING)
   249	        return emit_ui_json(wf, **kwargs)
   250	
   251	
   252	def check_envelope(raw: dict[str, Any]) -> dict[str, Any]:
   253	    """Run the full preservation pipeline over one rich envelope.
   254	
   255	    Returns a per-file result dict with counts and a ``mismatches`` list of
   256	    ``(axis, node, expected, actual)`` rows.  A pipeline refusal/exception is
   257	    recorded as a mismatch row and the remaining axes are skipped — the file
   258	    cannot be preserved, which is itself the finding.
   259	    """
   260	    result: dict[str, Any] = {
   261	        "file": None,
   262	        "rich_nodes": len(raw.get("nodes", {})),
   263	        "rich_edges": len(raw.get("edges", [])),
   264	        "canonical_nodes": 0,
   265	        "canonical_links": 0,
   266	        "groups": 0,
   267	        "pin_opaque": 0,
   268	        "uidless": 0,
   269	        "mismatches": [],
   270	    }
   271	
   272	    def fail(axis: str, node: Any, expected: Any, actual: Any) -> dict[str, Any]:
   273	        _record(result, axis, node, expected, actual)
   274	        return result
   275	
   276	    ir1 = from_envelope(raw)
   277	    ir1.groups = deepcopy(raw.get("groups") or [])
   278	
   279	    # ── pin evidence: emit directly with recovery_report + the rich groups ──
   280	    recovery_report: list[dict[str, Any]] = []
   281	    try:
   282	        pin_envelope = _emit(ir1, recovery_report=recovery_report)
   283	    except RefusedEmit as exc:
   284	        node_id, reason = _refusal_detail(exc)
   285	        return fail("emit_refused", node_id, "emission must succeed", reason)
   286	    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
   287	        return fail("exception", None, "emission must succeed", f"{type(exc).__name__}: {exc}")
   288	
   289	    emitted_uids = {
   290	        node.get("properties", {}).get("vibecomfy_uid")
   291	        for node in pin_envelope.get("nodes", [])
   292	    }
   293	    for entry in recovery_report:
   294	        if entry.get("widget_shape_verdict") != "pin_opaque":
   295	            continue
   296	        result["pin_opaque"] += 1
   297	        entry_node_id = str(entry.get("node_id"))
   298	        decoded_uid = ir1.nodes[entry_node_id].uid if entry_node_id in ir1.nodes else None
   299	        if decoded_uid not in emitted_uids:
   300	            _record(
   301	                result,
   302	                "pin.uid_missing",
   303	                entry_node_id,
   304	                f"emitted node with properties.vibecomfy_uid == {decoded_uid!r}",
   305	                "no such emitted node",
   306	            )
   307	
   308	    # ── canonicalize + re-ingest + re-emit ──────────────────────────────────
   309	    try:
   310	        canonical = normalize_agent_edit_graph(raw)
   311	        api2 = normalize_to_api(canonical, use_comfy_converter=False)
   312	        ir2 = from_api(api2)
   313	        ir2.groups = deepcopy(canonical.get("groups") or [])
   314	        reemit = _emit(ir2)
   315	    except RefusedEmit as exc:
   316	        node_id, reason = _refusal_detail(exc)
   317	        return fail("emit_refused", node_id, "emission must succeed", reason)
   318	    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
   319	        return fail("exception", None, "pipeline must succeed", f"{type(exc).__name__}: {exc}")
   320	
   321	    result["canonical_nodes"] = len(canonical.get("nodes", []))
   322	    result["canonical_links"] = len(canonical.get("links", []))
   323	    result["groups"] = len(canonical.get("groups") or [])
   324	
   325	    # ── rich → ir1: node projection exact ───────────────────────────────────
   326	    for node_id, entry in raw.get("nodes", {}).items():
   327	        expected = rich_node_projection(node_id, entry)
   328	        actual = ir_node_projection(ir1.nodes[node_id])
   329	        for axis in ("id", "class_type", "uid", "mode", "furniture"):
   330	            if expected[axis] != actual[axis]:
   331	                _record(result, f"rich->ir1.{axis}", node_id, expected[axis], actual[axis])
   332	        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
   333	            _record(result, "rich->ir1.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
   334	        if expected["raw_widgets"] is not None and expected["raw_widgets"] != actual["raw_widgets"]:
   335	            _record(result, "rich->ir1.raw_widgets", node_id, expected["raw_widgets"], actual["raw_widgets"])
   336	
   337	    # ── rich → canonical: node ids/classes/modes/uids/widgets exact ─────────
   338	    canonical_by_id = canonical_nodes_by_id(canonical)
   339	    # Numeric rich ids keep their numeric value in the canonical envelope;
   340	    # non-digit ids (typed-wrapper labels like "80:4") are remapped to fresh
   341	    # integers.  The stable uid is the cross-boundary identity: map every rich
   342	    # node to its canonical litegraph id through the emitted uid stamp.
   343	    uid_to_canonical_id = {
   344	        proj["uid"]: canonical_id
   345	        for canonical_id, proj in canonical_by_id.items()
   346	    }
   347	
   348	    def canonical_id_of(rich_id: str) -> Any:
   349	        rich_uid = (raw["nodes"][rich_id].get("uid")) if rich_id in raw["nodes"] else None
   350	        mapped = uid_to_canonical_id.get(rich_uid)
   351	        return mapped if mapped is not None else _canonical_id_of(rich_id)
   352	
   353	    canonical_ids = set(canonical_by_id)
   354	    expected_ids = {canonical_id_of(node_id) for node_id in raw.get("nodes", {})}
   355	    if canonical_ids != expected_ids:
   356	        _record(
   357	            result,
   358	            "rich->canonical.node_ids",
   359	            None,
   360	            sorted(expected_ids),
   361	            sorted(canonical_ids),
   362	        )
   363	    for node_id, entry in raw.get("nodes", {}).items():
   364	        expected = rich_node_projection(node_id, entry)
   365	        actual = canonical_by_id.get(canonical_id_of(node_id))
   366	        if actual is None:
   367	            _record(result, "rich->canonical.missing_node", node_id, expected["id"], None)
   368	            continue
   369	        for axis in ("class_type", "mode", "uid"):
   370	            if expected[axis] != actual[axis]:
   371	                _record(result, f"rich->canonical.{axis}", node_id, expected[axis], actual[axis])
   372	        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
   373	            _record(result, "rich->canonical.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
   374	
   375	    # ── rich → ir2: node projection exact (ids via the canonical remap) ─────
   376	    for node_id, entry in raw.get("nodes", {}).items():
   377	        expected = rich_node_projection(node_id, entry)
   378	        actual = ir_node_projection(ir2.nodes[str(canonical_id_of(node_id))])
   379	        for axis in ("class_type", "uid", "mode"):
   380	            if expected[axis] != actual[axis]:
   381	                _record(result, f"rich->ir2.{axis}", node_id, expected[axis], actual[axis])
   382	        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
   383	            _record(result, "rich->ir2.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
   384	        # The id axis speaks the canonical id (deterministic renumbering of
   385	        # non-digit ids is the documented exclusion; digit ids keep their value).
   386	        if actual["id"] != str(canonical_id_of(node_id)):
   387	            _record(result, "rich->ir2.id", node_id, str(canonical_id_of(node_id)), actual["id"])
   388	
   389	    # ── edge tuples: rich == ir1 == ir2 == canonical (semantic) ─────────────
   390	    rich_edges = rich_edge_tuples(raw)
   391	    ir1_edges = {edge_tuple(edge) for edge in ir1.edges}
   392	    ir2_edges = {edge_tuple(edge) for edge in ir2.edges}
   393	    # ir1 keeps rich ids; ir2 and the canonical envelope speak canonical ids.
   394	    rich_edges_canonical = {
   395	        (str(canonical_id_of(from_node)), from_output, str(canonical_id_of(to_node)), to_input)
   396	        for from_node, from_output, to_node, to_input in rich_edges
   397	    }
   398	    if rich_edges != ir1_edges:
   399	        _record(
   400	            result,
   401	            "rich->ir1.edges",
   402	            None,
   403	            sorted(rich_edges),
   404	            sorted(ir1_edges),
   405	        )
   406	    if rich_edges_canonical != ir2_edges:
   407	        _record(
   408	            result,
   409	            "rich->ir2.edges",
   410	            None,
   411	            sorted(rich_edges_canonical),
   412	            sorted(ir2_edges),
   413	        )
   414	    canonical_edges = canonical_semantic_edges(canonical)
   415	    if rich_edges_canonical != canonical_edges:
   416	        _record(
   417	            result,
   418	            "rich->canonical.edges",
   419	            None,
   420	            sorted(rich_edges_canonical),
   421	            sorted(canonical_edges),
   422	        )
   423	
   424	    # ── groups: rich (None ≡ []) == canonical == reemit ─────────────────────
   425	    rich_groups = raw.get("groups") or []
   426	    canonical_groups = canonical.get("groups") or []
   427	    reemit_groups = reemit.get("groups") or []
   428	    if rich_groups != canonical_groups or canonical_groups != reemit_groups:
   429	        _record(
   430	            result,
   431	            "groups",
   432	            None,
   433	            {"rich": rich_groups, "canonical": canonical_groups},
   434	            {"reemit": reemit_groups},
   435	        )
   436	
   437	    # ── canonical emission idempotence ──────────────────────────────────────
   438	    reemit_by_id = canonical_nodes_by_id(reemit)
   439	    if set(reemit_by_id) != set(canonical_by_id):
   440	        _record(
   441	            result,
   442	            "canonical.idempotence.node_ids",
   443	            None,
   444	            sorted(canonical_by_id),
   445	            sorted(reemit_by_id),
   446	        )
   447	    for node_id, expected in canonical_by_id.items():
   448	        actual = reemit_by_id.get(node_id)
   449	        if actual is None:
   450	            continue
   451	        for axis in ("class_type", "mode", "uid", "widgets_values"):
   452	            if expected[axis] != actual[axis]:
   453	                _record(result, f"canonical.idempotence.{axis}", node_id, expected[axis], actual[axis])
   454	    if canonical_link_topology(canonical) != canonical_link_topology(reemit):
   455	        _record(
   456	            result,
   457	            "canonical.idempotence.links",
   458	            None,
   459	            sorted(canonical_link_topology(canonical)),
   460	            sorted(canonical_link_topology(reemit)),
   461	        )
   462	
   463	    # ── uid-less emissions across every emitted envelope (global must be 0) ─
   464	    for envelope in (canonical, reemit, pin_envelope):
   465	        for node in envelope.get("nodes", []):
   466	            properties = node.get("properties") or {}
   467	            uid = properties.get("vibecomfy_uid")
   468	            if not isinstance(uid, str) or not uid.strip():
   469	                result["uidless"] += 1
   470	                _record(
   471	                    result,
   472	                    "uidless_emission",
   473	                    node.get("id"),
   474	                    "nonblank properties.vibecomfy_uid",
   475	                    uid,
   476	                )
   477	
   478	    return result
   479	
   480	
   481	def _refusal_detail(exc: RefusedEmit) -> tuple[Any, str]:
   482	    """Extract (node_id, reason) from a RefusedEmit diff."""
   483	    for node_id, diff in (exc.diff or {}).items():
   484	        return node_id, str(diff.get("reason") or exc)
   485	    return None, str(exc)
   486	
   487	
   488	# ---------------------------------------------------------------------------
   489	# Corpus aggregation
   490	# ---------------------------------------------------------------------------
   491	
   492	
   493	def _corpus_paths(corpus_dir: str | Path) -> tuple[Path, list[Path]]:
   494	    """Validate an explicit corpus directory and return its JSON paths."""
   495	    root = Path(corpus_dir)
   496	    if root.name.endswith(".layout.json"):
   497	        raise ValueError(f"layout sidecar cannot be used as a corpus directory: {root}")
   498	    if not root.exists():
   499	        raise FileNotFoundError(f"corpus directory does not exist: {root}")
   500	    if not root.is_dir():
   501	        raise NotADirectoryError(f"corpus path is not a directory: {root}")
   502	    paths = sorted(root.glob("*.json"))
   503	    envelope_paths = [path for path in paths if not path.name.endswith(".layout.json")]
   504	    if not envelope_paths:
   505	        raise ValueError(f"corpus directory contains zero envelopes: {root}")
   506	    return root, paths
   507	
   508	
   509	def iter_corpus(corpus_dir: str | Path):
   510	    """Yield ``(path, raw)`` for every serialized-Vibe envelope in the corpus.
   511	
   512	    Non-envelope ``*.json`` files (e.g. ``.layout.json`` sidecar stores) are
   513	    skipped and reported in the aggregate ``skipped_non_envelopes`` counter.
   514	    """
   515	    _, paths = _corpus_paths(corpus_dir)
   516	    found = 0
   517	    for path in paths:
   518	        if path.name.endswith(".layout.json"):
   519	            continue
   520	        raw = json.loads(path.read_text(encoding="utf-8"))
   521	        if (
   522	            not isinstance(raw, dict)
   523	            or not isinstance(raw.get("nodes"), dict)
   524	            or "vibecomfy_format_version" not in raw
   525	        ):
   526	            continue
   527	        found += 1
   528	        yield path, raw
   529	    if found == 0:
   530	        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
   531	
   532	
   533	def check_corpus(
   534	    corpus_dir: str | Path,
   535	    *,
   536	    expected_count: int | None = None,
   537	) -> dict[str, Any]:
   538	    """Run :func:`check_envelope` over the whole corpus and aggregate counts.
   539	
   540	    Deterministic: files are processed in sorted order and all set comparisons
   541	    are order-independent.  Returns one summary dict with totals, per-axis
   542	    mismatch counts, and per-file mismatch rows.
   543	    """
   544	    summary: dict[str, Any] = {
   545	        "ok": True,
   546	        "checked": 0,
   547	        "skipped": 0,
   548	        "skipped_sidecars": 0,
   549	        "workflows": 0,
   550	        "skipped_non_envelopes": 0,
   551	        "rich_nodes": 0,
   552	        "rich_edges": 0,
   553	        "canonical_nodes": 0,
   554	        "canonical_links": 0,
   555	        "groups": 0,
   556	        "pin_opaque": 0,
   557	        "uidless": 0,
   558	        "mismatch_count": 0,
   559	        "mismatches_by_axis": {},
   560	        "refused_files": [],
   561	        "mismatch_rows": [],
   562	    }
   563	    _, paths = _corpus_paths(corpus_dir)
   564	    for path in paths:
   565	        name = path.name
   566	        if name.endswith(".layout.json"):
   567	            summary["skipped"] += 1
   568	            summary["skipped_sidecars"] += 1
   569	            continue
   570	        try:
   571	            raw = json.loads(path.read_text(encoding="utf-8"))
   572	        except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
   573	            summary["skipped"] += 1
   574	            _record_row(summary, name, "exception", None, "JSON must parse", f"{type(exc).__name__}: {exc}")
   575	            continue
   576	        if (
   577	            not isinstance(raw, dict)
   578	            or not isinstance(raw.get("nodes"), dict)
   579	            or "vibecomfy_format_version" not in raw
   580	        ):
   581	            summary["skipped"] += 1
   582	            summary["skipped_non_envelopes"] += 1
   583	            continue
   584	
   585	        summary["checked"] += 1
   586	        summary["workflows"] += 1
   587	        result = check_envelope(raw)
   588	        result["file"] = name
   589	        summary["rich_nodes"] += result["rich_nodes"]
   590	        summary["rich_edges"] += result["rich_edges"]
   591	        summary["canonical_nodes"] += result["canonical_nodes"]
   592	        summary["canonical_links"] += result["canonical_links"]
   593	        summary["groups"] += result["groups"]
   594	        summary["pin_opaque"] += result["pin_opaque"]
   595	        summary["uidless"] += result["uidless"]
   596	        for axis, node, expected, actual in result["mismatches"]:
   597	            _record_row(summary, name, axis, node, expected, actual)
   598	        for axis, node, expected, actual in result["mismatches"]:
   599	            if axis == "emit_refused":
   600	                summary["refused_files"].append([name, _truncate(node), _truncate(actual)])
   601	
   602	    if summary["checked"] == 0:
   603	        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
   604	    summary["expected_count"] = expected_count
   605	    summary["count_matches"] = expected_count is None or summary["checked"] == expected_count
   606	    summary["mismatch_count"] = len(summary["mismatch_rows"])
   607	    summary["ok"] = (
   608	        summary["mismatch_count"] == 0
   609	        and summary["uidless"] == 0
   610	        and summary["count_matches"]
   611	    )
   612	    return summary
   613	
   614	
   615	def _record_row(
   616	    summary: dict[str, Any],
   617	    file: str,
   618	    axis: str,
   619	    node: Any,
   620	    expected: Any,
   621	    actual: Any,
   622	) -> None:
   623	    summary["mismatches_by_axis"][axis] = summary["mismatches_by_axis"].get(axis, 0) + 1
   624	    summary["mismatch_rows"].append(
   625	        [file, axis, _truncate(node), _truncate(expected), _truncate(actual)]
   626	    )
   627	
   628	
   629	# ---------------------------------------------------------------------------
   630	# CLI
   631	# ---------------------------------------------------------------------------
   632	
   633	
   634	def main(argv: list[str] | None = None) -> int:
   635	    parser = argparse.ArgumentParser(description=__doc__)
   636	    parser.add_argument(
   637	        "--corpus-dir",
   638	        required=True,
   639	        help="explicit directory of serialized-Vibe corpus envelopes",
   640	    )
   641	    parser.add_argument(
   642	        "--expected-count",
   643	        type=int,
   644	        help="fail unless exactly this many envelopes are checked",
   645	    )
   646	    args = parser.parse_args(argv)
   647	
   648	    try:
   649	        summary = check_corpus(args.corpus_dir, expected_count=args.expected_count)
   650	    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
   651	        parser.error(str(exc))
   652	    print(json.dumps(summary, indent=2, sort_keys=True))
   653	    return 0 if summary["ok"] else 1
   654	
   655	
   656	if __name__ == "__main__":
   657	    sys.exit(main())

exec
/bin/zsh -lc 'nl -ba tests/test_ingest_external_workflows.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
     1	"""P4/P5: new envelope writes go through VibeWorkflow.to_envelope.
     2	
     3	The envelope is the serialized IR; compile("api") is a derived function, not
     4	stored data. New envelopes therefore omit the compiled_api sidecar while
     5	remaining losslessly decodable. Format version lives on the IR.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import json
    11	from pathlib import Path
    12	
    13	from scripts import ingest_external_workflows as ingest
    14	from vibecomfy.workflow import FORMAT_VERSION, VibeWorkflow
    15	
    16	_CORPUS_90A1D5 = (
    17	    Path(__file__).resolve().parent
    18	    / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json"
    19	)
    20	
    21	
    22	def _load_90a1d5() -> dict:
    23	    return json.loads(_CORPUS_90A1D5.read_text(encoding="utf-8"))
    24	
    25	
    26	def test_vibe_workflow_to_dict_omits_compiled_api() -> None:
    27	    """New envelopes are the serialized IR: version + rich nodes, no sidecar."""
    28	    workflow = ingest.convert_to_vibe_format(_load_90a1d5())
    29	    envelope = workflow.to_envelope()
    30	
    31	    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
    32	    assert envelope["vibecomfy_format_version"] == ingest.VIBECOMFY_FORMAT_VERSION
    33	    assert ingest.VIBECOMFY_FORMAT_VERSION == FORMAT_VERSION
    34	    assert isinstance(envelope["nodes"], dict)
    35	    assert len(envelope["nodes"]) == 15
    36	    assert "compiled_api" not in envelope
    37	    assert "compiled_api" not in envelope.get("metadata", {})
    38	
    39	    # The sidecar-less envelope round-trips losslessly back through the decoder.
    40	    round_tripped = VibeWorkflow.from_envelope(envelope)
    41	    assert len(round_tripped.nodes) == 15
    42	    assert round_tripped.nodes["10"].class_type == "TripoRefineNode"
    43	
    44	
    45	def test_ingest_helper_is_to_envelope() -> None:
    46	    """The ingest script writer is a one-line wrap of to_envelope, not a twin."""
    47	    workflow = ingest.convert_to_vibe_format(_load_90a1d5())
    48	    assert ingest._vibe_workflow_to_dict(workflow) == workflow.to_envelope()
    49	
    50	
    51	def test_fixer_envelope_uses_to_envelope_then_workflow_id_stamp() -> None:
    52	    """Fixer writes via to_envelope; workflow_id is stamped after, not by the IR."""
    53	    from vibecomfy.demo_factory.fixer import _ui_graph_to_ir_envelope
    54	
    55	    workflow_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    56	    ui_graph = {
    57	        "id": workflow_id,
    58	        "nodes": [
    59	            {
    60	                "id": 1,
    61	                "type": "PreviewImage",
    62	                "pos": [0, 0],
    63	                "size": [140, 80],
    64	                "flags": {},
    65	                "order": 0,
    66	                "mode": 0,
    67	                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
    68	                "outputs": [],
    69	                "properties": {"Node name for S&R": "PreviewImage"},
    70	                "widgets_values": [],
    71	            }
    72	        ],
    73	        "links": [],
    74	    }
    75	    envelope = _ui_graph_to_ir_envelope(ui_graph)
    76	    assert "compiled_api" not in envelope
    77	    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
    78	    assert envelope["workflow_id"] == workflow_id
    79	    decoded = VibeWorkflow.from_envelope(envelope)
    80	    assert "1" in decoded.nodes
    81	    assert decoded.nodes["1"].class_type == "PreviewImage"

exec
/bin/zsh -lc 'nl -ba tests/test_porting_normalize_ingest.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
     1	"""Tests for control_after_generate retention through JSON→IR ingest (T3).
     2	
     3	Proves:
     4	1. 'randomize' and 'fixed' captured from the named-inputs dict (api-format path).
     5	2. 'fixed' captured from _ui.widgets_values KSampler None-slot path.
     6	3. Absent control_after_generate → metadata key unset (never guessed).
     7	4. compile("api") guard: control_after_generate absent from compiled output
     8	   even when captured in metadata (byte-identical compile path preserved).
     9	"""
    10	from __future__ import annotations
    11	
    12	import json
    13	from collections import Counter
    14	from copy import deepcopy
    15	from pathlib import Path
    16	
    17	import pytest
    18	
    19	from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
    20	from vibecomfy.ingest.normalize import convert_to_vibe_format, from_api, from_ui, normalize_to_api
    21	from vibecomfy.porting.emit.ui import emit_ui_json
    22	
    23	
    24	def _ksampler_api_node(*, control: str | None = None) -> dict:
    25	    inputs: dict = {
    26	        "seed": 42,
    27	        "steps": 20,
    28	        "cfg": 7.0,
    29	        "sampler_name": "euler",
    30	        "scheduler": "normal",
    31	        "denoise": 1.0,
    32	    }
    33	    if control is not None:
    34	        inputs["control_after_generate"] = control
    35	    return {"class_type": "KSampler", "inputs": inputs}
    36	
    37	
    38	def _ksampler_api_node_with_ui(*, control: str) -> dict:
    39	    """KSampler node as produced by _normalize_ui_to_api with _ui.widgets_values.
    40	
    41	    KSampler widget schema: ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"]
    42	    Slot index 1 is None (the control_after_generate UI slot).
    43	    """
    44	    return {
    45	        "class_type": "KSampler",
    46	        "inputs": {
    47	            "seed": 42,
    48	            "steps": 20,
    49	            "cfg": 7.0,
    50	            "sampler_name": "euler",
    51	            "scheduler": "normal",
    52	            "denoise": 1.0,
    53	        },
    54	        "_ui": {"widgets_values": [42, control, 20, 7.0, "euler", "normal", 1.0]},
    55	    }
    56	
    57	
    58	def _workflow_from_node(node: dict, node_id: str = "1"):  # type: ignore[return]
    59	    return convert_to_vibe_format({node_id: node})
    60	
    61	
    62	# ── Case 1a: 'randomize' captured from named inputs dict ─────────────────────
    63	
    64	
    65	def test_control_after_generate_randomize_from_inputs() -> None:
    66	    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    67	    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize"
    68	
    69	
    70	# ── Case 1b: 'fixed' captured from named inputs dict ─────────────────────────
    71	
    72	
    73	def test_control_after_generate_fixed_from_inputs() -> None:
    74	    wf = _workflow_from_node(_ksampler_api_node(control="fixed"))
    75	    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"
    76	
    77	
    78	# ── Case 2: 'fixed' captured from _ui.widgets_values None-slot ───────────────
    79	
    80	
    81	def test_control_after_generate_fixed_from_ui_widgets() -> None:
    82	    wf = _workflow_from_node(_ksampler_api_node_with_ui(control="fixed"))
    83	    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"
    84	
    85	
    86	def test_public_raw_widgets_alias_is_preserved_as_raw_widget_payload() -> None:
    87	    wf = _workflow_from_node(
    88	        {
    89	            "class_type": "PrimitiveInt",
    90	            "inputs": {"widget_0": 7, "widget_1": "fixed"},
    91	            "raw_widgets": {
    92	                "values": [7, "fixed"],
    93	                "shape": "list",
    94	                "source": "ui.widgets_values",
    95	                "has_dict_rows": False,
    96	                "length": 2,
    97	            },
    98	        }
    99	    )
   100	
   101	    node = wf.nodes["1"]
   102	    assert node.raw_widgets is not None
   103	    assert node.raw_widgets.values == [7, "fixed"]
   104	    assert node.raw_widgets.length == 2
   105	    assert "raw_widgets" not in node.metadata
   106	
   107	
   108	def test_vibe_shape_decodes_rich_node_raw_widgets_payload() -> None:
   109	    """The rich decoder turns a serialized RawWidgetPayload into node.raw_widgets
   110	    and preserves node metadata._ui verbatim (lossless envelope decode)."""
   111	    rich_ui = {
   112	        "_ui": {
   113	            "id": 1,
   114	            "type": "PrimitiveInt",
   115	            "widgets_values": [7, "fixed"],
   116	        }
   117	    }
   118	    wf = convert_to_vibe_format(
   119	        {
   120	            "id": "test",
   121	            "vibecomfy_format_version": "1.0",
   122	            "compiled_api": {
   123	                "1": {
   124	                    "class_type": "PrimitiveInt",
   125	                    "inputs": {"widget_0": 7, "widget_1": "fixed"},
   126	                }
   127	            },
   128	            "nodes": {
   129	                "1": {
   130	                    "id": "1",
   131	                    "class_type": "PrimitiveInt",
   132	                    "inputs": {},
   133	                    "widgets": {"widget_0": 7, "widget_1": "fixed"},
   134	                    "metadata": rich_ui,
   135	                    "uid": "1",
   136	                    "raw_widgets": {
   137	                        "values": [7, "fixed"],
   138	                        "shape": "list",
   139	                        "source": "ui.widgets_values",
   140	                        "has_dict_rows": False,
   141	                        "length": 2,
   142	                    },
   143	                }
   144	            },
   145	            "edges": [],
   146	            "inputs": {},
   147	            "outputs": [],
   148	            "requirements": {},
   149	            "source": {"id": "test"},
   150	            "strict_types": False,
   151	        }
   152	    )
   153	
   154	    node = wf.nodes["1"]
   155	    assert node.raw_widgets is not None
   156	    assert node.raw_widgets.values == [7, "fixed"]
   157	    assert node.raw_widgets.length == 2
   158	    assert node.raw_widgets.shape == "list"
   159	    # metadata._ui is preserved verbatim (plus the provenance stamp).
   160	    assert node.metadata["_ui"] == rich_ui["_ui"]
   161	    assert node.metadata["provenance"] == "untrusted_source"
   162	
   163	def test_vibe_shape_carries_dynamic_dict_raw_ui_for_widget_pin() -> None:
   164	    wf = convert_to_vibe_format(
   165	        {
   166	            "id": "test",
   167	            "vibecomfy_format_version": "1.0",
   168	            "compiled_api": {
   169	                "81": {
   170	                    "class_type": "VHS_SplitImages",
   171	                    "inputs": {"images": ["105", 0], "split_index": 24},
   172	                }
   173	            },
   174	            "nodes": {
   175	                "81": {
   176	                    "id": "81",
   177	                    "class_type": "VHS_SplitImages",
   178	                    "inputs": {},
   179	                    "widgets": {"split_index": 24},
   180	                    "uid": "81",
   181	                    "raw_widgets": {
   182	                        "values": {"split_index": 24},
   183	                        "shape": "dict",
   184	                        "source": "ui.widgets_values",
   185	                        "has_dict_rows": True,
   186	                        "length": 1,
   187	                    },
   188	                    "metadata": {
   189	                        "_ui": {
   190	                            "id": 81,
   191	                            "type": "VHS_SplitImages",
   192	                            "pos": [1075, 1136],
   193	                            "size": [315, 118],
   194	                            "flags": {},
   195	                            "order": 28,
   196	                            "mode": 0,
   197	                            "inputs": [{"name": "images", "type": "IMAGE", "link": 198}],
   198	                            "outputs": [{"name": "IMAGE_A", "type": "IMAGE", "links": []}],
   199	                            "properties": {"Node name for S&R": "VHS_SplitImages"},
   200	                            "widgets_values": {"split_index": 24},
   201	                        }
   202	                    },
   203	                }
   204	            },
   205	            "edges": [],
   206	            "inputs": {},
   207	            "outputs": [],
   208	            "requirements": {},
   209	            "source": {"id": "test"},
   210	            "strict_types": False,
   211	        }
   212	    )
   213	
   214	    node = wf.nodes["81"]
   215	    assert node.raw_widgets is not None
   216	    assert node.raw_widgets.values == {"split_index": 24}
   217	    assert node.metadata["_ui"]["widgets_values"] == {"split_index": 24}
   218	    assert node.metadata["_ui"]["inputs"][0]["link"] == 198
   219	
   220	
   221	# ── Case 3: absent → metadata key unset (never guessed) ──────────────────────
   222	
   223	
   224	def test_control_after_generate_absent_leaves_metadata_unset() -> None:
   225	    wf = _workflow_from_node(_ksampler_api_node())
   226	    assert "control_after_generate" not in wf.nodes["1"].metadata, (
   227	        "control_after_generate must not be guessed when absent from source"
   228	    )
   229	
   230	
   231	# ── Case 4a: compile("api") excludes control_after_generate ──────────────────
   232	
   233	
   234	def test_compile_api_excludes_control_after_generate() -> None:
   235	    """compile('api') must not include control_after_generate even when metadata carries it."""
   236	    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
   237	    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize", "precondition: metadata captured"
   238	    compiled = wf.compile("api")
   239	    assert "control_after_generate" not in compiled.get("1", {}).get("inputs", {}), (
   240	        "compile('api') must filter control_after_generate via _is_ui_only_prompt_input"
   241	    )
   242	
   243	
   244	# ── Case 4b: compile("api") byte-identical with and without the capture ───────
   245	
   246	
   247	def test_compile_api_byte_identical_with_and_without_control_capture() -> None:
   248	    """compile('api') output is identical regardless of control_after_generate presence.
   249	
   250	    This is the guard asserting the T2 ingest change leaves the compiled API dict
   251	    byte-for-byte unchanged: a node with control_after_generate captured in metadata
   252	    compiles identically to the same node without it at all.
   253	    """
   254	    wf_without = _workflow_from_node(_ksampler_api_node())
   255	    wf_with = _workflow_from_node(_ksampler_api_node(control="randomize"))
   256	
   257	    compiled_without = wf_without.compile("api")
   258	    compiled_with = wf_with.compile("api")
   259	
   260	    assert json.dumps(compiled_without, sort_keys=True) == json.dumps(compiled_with, sort_keys=True), (
   261	        "compile('api') output must be byte-for-byte identical with and without "
   262	        "control_after_generate — the ingest metadata capture must not alter the compiled dict"
   263	    )
   264	
   265	
   266	# ═══════════════════════════════════════════════════════════════════════════════
   267	# T6 — Identity capture & determinism on the flat walking-skeleton fixture
   268	# ═══════════════════════════════════════════════════════════════════════════════
   269	
   270	
   271	def _load_flat_wf():
   272	    """Load the flat.json walking-skeleton fixture → VibeWorkflow (cached helper)."""
   273	    import json as _json
   274	
   275	    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
   276	        raw = _json.load(fh)
   277	    return convert_to_vibe_format(raw)
   278	
   279	
   280	def test_flat_every_node_has_nonempty_uid_equal_to_litegraph_id() -> None:
   281	    """Every node gets a non-empty uid equal to its source litegraph id."""
   282	    wf = _load_flat_wf()
   283	    raw = json.load(open("tests/fixtures/walking_skeleton/flat.json"))
   284	    raw_ids = {str(n["id"]) for n in raw["nodes"]}
   285	
   286	    for nid, node in wf.nodes.items():
   287	        assert node.uid, f"node {nid} has empty uid"
   288	        assert node.uid in raw_ids, f"node {nid} uid {node.uid!r} not in raw ids {raw_ids}"
   289	        assert node.uid == nid, (
   290	            f"node {nid} uid {node.uid!r} does not equal its own litegraph id {nid}"
   291	        )
   292	
   293	
   294	def test_flat_pre_existing_vibecomfy_uid_read_back_not_fresh_mint() -> None:
   295	    """A node with pre-existing properties['vibecomfy_uid'] reads that value back."""
   296	    import json as _json
   297	
   298	    raw = _json.load(open("tests/fixtures/walking_skeleton/flat.json"))
   299	    # Stamp a synthetic vibecomfy_uid onto KSampler (id=5) properties
   300	    for node in raw["nodes"]:
   301	        if node["id"] == 5:
   302	            node.setdefault("properties", {})["vibecomfy_uid"] = "custom-ksampler-uuid"
   303	
   304	    wf = convert_to_vibe_format(raw)
   305	    ksampler = wf.nodes["5"]
   306	    assert ksampler.uid == "custom-ksampler-uuid", (
   307	        f"Pre-existing vitecomfy_uid not preserved: got {ksampler.uid!r}"
   308	    )
   309	
   310	
   311	def test_flat_pos_size_reachable_via_metadata_ui() -> None:
   312	    """Captured pos/size are reachable via metadata['_ui']."""
   313	    wf = _load_flat_wf()
   314	    raw = json.load(open("tests/fixtures/walking_skeleton/flat.json"))
   315	    raw_by_id = {str(n["id"]): n for n in raw["nodes"]}
   316	
   317	    for nid, node in wf.nodes.items():
   318	        _ui = node.metadata.get("_ui")
   319	        assert isinstance(_ui, dict), f"node {nid} missing _ui metadata"
   320	        assert "pos" in _ui, f"node {nid} _ui missing pos"
   321	        assert "size" in _ui, f"node {nid} _ui missing size"
   322	        expected = raw_by_id[nid]
   323	        assert _ui["pos"] == expected["pos"], (
   324	            f"node {nid} pos mismatch: {_ui['pos']} != {expected['pos']}"
   325	        )
   326	        assert _ui["size"] == expected["size"], (
   327	            f"node {nid} size mismatch: {_ui['size']} != {expected['size']}"
   328	        )
   329	
   330	
   331	def test_flat_determinism_same_source_identical_uids() -> None:
   332	    """Same source → identical uids across two ingests."""
   333	    wf1 = _load_flat_wf()
   334	    wf2 = _load_flat_wf()
   335	
   336	    for nid in sorted(wf1.nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
   337	        assert nid in wf2.nodes, f"node {nid} missing from second ingest"
   338	        assert wf1.nodes[nid].uid == wf2.nodes[nid].uid, (
   339	            f"node {nid}: non-deterministic uid {wf1.nodes[nid].uid!r} vs {wf2.nodes[nid].uid!r}"
   340	        )
   341	
   342	
   343	# ── T4: mode/flags/color/bgcolor retention (K3 invariant) ────────────────────
   344	
   345	
   346	def _node_with_mode(mode: int = 4, **extra_vis: object) -> dict:
   347	    """API-format node with _ui carrying litegraph visual fields."""
   348	    _ui: dict = {"id": 1, "mode": mode}
   349	    for k, v in extra_vis.items():
   350	        _ui[k] = v
   351	    return {"class_type": "KSampler", "inputs": {"seed": 1}, "_ui": _ui}
   352	
   353	
   354	def _node_without_mode() -> dict:
   355	    return {"class_type": "KSampler", "inputs": {"seed": 1}}
   356	
   357	
   358	def test_mode_captured_from_pure_python_path() -> None:
   359	    """Pure-Python path: mode:4 lands on the first-class VibeNode.mode field."""
   360	    raw_ui = {
   361	        "nodes": [
   362	            {
   363	                "id": 1,
   364	                "type": "KSampler",
   365	                "mode": 4,
   366	                "inputs": [],
   367	                "widgets_values": [42, "fixed", 20, 7.0, "euler", "normal", 1.0],
   368	            }
   369	        ],
   370	        "links": [],
   371	    }
   372	    from vibecomfy.ingest.normalize import normalize_to_api
   373	    api = normalize_to_api(raw_ui, use_comfy_converter=False)
   374	    wf = convert_to_vibe_format(api)
   375	    assert wf.nodes["1"].mode == 4
   376	    # _ui.mode is left in place so emit_ui_json furniture stays intact.
   377	    assert wf.nodes["1"].metadata["_ui"]["mode"] == 4
   378	    # No duplicate furniture copy is written on new ingests.
   379	    assert "mode" not in wf.nodes["1"].metadata
   380	
   381	
   382	def test_mode_captured_from_comfy_converter_path() -> None:
   383	    """Comfy-converter path: mode:4 in _merge_slim_ui lands on VibeNode.mode."""
   384	    # Simulate the result of convert_ui_to_api + _merge_slim_ui by providing
   385	    # an API-format node that already has a slim _ui with mode set.
   386	    api_node = _node_with_mode(mode=4)
   387	    wf = convert_to_vibe_format({"1": api_node})
   388	    assert wf.nodes["1"].mode == 4
   389	    assert wf.nodes["1"].metadata["_ui"]["mode"] == 4
   390	    assert "mode" not in wf.nodes["1"].metadata
   391	
   392	
   393	def test_flags_color_bgcolor_captured() -> None:
   394	    """flags, color, bgcolor are also captured into metadata."""
   395	    api_node = _node_with_mode(mode=0, flags={"pinned": True}, color="#ff0000", bgcolor="#000000")
   396	    wf = convert_to_vibe_format({"1": api_node})
   397	    assert wf.nodes["1"].metadata.get("flags") == {"pinned": True}
   398	    assert wf.nodes["1"].metadata.get("color") == "#ff0000"
   399	    assert wf.nodes["1"].metadata.get("bgcolor") == "#000000"
   400	
   401	
   402	def test_mode_absent_leaves_field_zero_and_metadata_unset() -> None:
   403	    """Nodes with no mode field get mode 0 and no metadata['mode'] key."""
   404	    wf = convert_to_vibe_format({"1": _node_without_mode()})
   405	    assert wf.nodes["1"].mode == 0
   406	    assert "mode" not in wf.nodes["1"].metadata
   407	
   408	
   409	def test_mode_does_not_enter_inputs_or_widgets() -> None:
   410	    """mode must never appear in node.inputs or node.widgets (K3 invariant)."""
   411	    api_node = _node_with_mode(mode=4)
   412	    wf = convert_to_vibe_format({"1": api_node})
   413	    node = wf.nodes["1"]
   414	    assert node.mode == 4
   415	    assert "mode" not in node.inputs
   416	    assert "mode" not in node.widgets
   417	
   418	
   419	def test_compile_api_honors_ingest_captured_mode() -> None:
   420	    """mode is first-class: ingest-captured mode=4 bypasses the node at compile.
   421	
   422	    The pre-P10 decoupling (captured mode never tripping compile) existed only
   423	    because mode was not a schema field.  The field is now the compile signal:
   424	    a mode=4 node is dropped/bypassed, while mode=0 compiles identically to
   425	    an absent mode.
   426	    """
   427	    import json
   428	
   429	    wf_bypassed = convert_to_vibe_format({"1": _node_with_mode(mode=4)})
   430	    wf_zero = convert_to_vibe_format({"1": _node_with_mode(mode=0)})
   431	    wf_absent = convert_to_vibe_format({"1": _node_without_mode()})
   432	
   433	    assert "1" not in wf_bypassed.compile("api"), "mode=4 node must be bypassed"
   434	
   435	    compiled_zero = json.dumps(wf_zero.compile(), sort_keys=True)
   436	    compiled_absent = json.dumps(wf_absent.compile(), sort_keys=True)
   437	    assert compiled_zero == compiled_absent, (
   438	        "compile('api') output must be identical for mode=0 vs absent mode"
   439	    )
   440	
   441	
   442	# ══════════════════════════════════════════════════════════════════════════════
   443	# T19 — comfy_converter_strict parameter semantics (offline, no comfy needed)
   444	# ══════════════════════════════════════════════════════════════════════════════
   445	
   446	# Minimal UI-shaped workflow usable as a normalize_to_api input.
   447	_MINIMAL_UI_RAW: dict = {
   448	    "nodes": [{"id": 1, "type": "SaveImage", "inputs": [], "widgets_values": ["output"]}],
   449	    "links": [],
   450	}
   451	
   452	
   453	def test_comfy_converter_strict_absent_comfy_falls_through_to_offline() -> None:
   454	    """comfy_converter_strict=True with comfy absent: import guard skips cleanly.
   455	
   456	    When ``use_comfy_converter=True`` (default) but the comfy package cannot be
   457	    imported, the ImportError guard fires before strict mode is ever consulted.
   458	    The call must succeed by falling through to the offline converter — no
   459	    exception propagated, result is a valid API dict.
   460	    """
   461	    from unittest.mock import patch
   462	    from vibecomfy.ingest.normalize import normalize_to_api
   463	
   464	    # Simulate comfy being absent by making the import raise ImportError.
   465	    with patch.dict("sys.modules", {"comfy": None, "comfy.component_model": None,
   466	                                    "comfy.component_model.workflow_convert": None}):
   467	        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)
   468	
   469	    assert isinstance(result, dict), "offline fallback must produce a dict"
   470	    assert "1" in result, "offline result must contain the single node"
   471	
   472	
   473	def test_comfy_converter_strict_no_op_when_use_comfy_converter_false() -> None:
   474	    """comfy_converter_strict is a no-op when use_comfy_converter=False.
   475	
   476	    When the comfy converter is disabled entirely (``use_comfy_converter=False``),
   477	    the strict flag must have no effect — the call succeeds using the offline
   478	    converter regardless of the flag value.
   479	    """
   480	    from vibecomfy.ingest.normalize import normalize_to_api
   481	
   482	    result_default = normalize_to_api(
   483	        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=False
   484	    )
   485	    result_strict = normalize_to_api(
   486	        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=True
   487	    )
   488	
   489	    import json
   490	    assert json.dumps(result_default, sort_keys=True) == json.dumps(result_strict, sort_keys=True), (
   491	        "comfy_converter_strict must be a no-op when use_comfy_converter=False — "
   492	        "both calls must produce identical output"
   493	    )
   494	
   495	
   496	def test_comfy_converter_default_raises_when_converter_errors() -> None:
   497	    """Default normalize_to_api() is strict when convert_ui_to_api raises.
   498	
   499	    When comfy IS importable but ``convert_ui_to_api`` raises an exception, the
   500	    default call must propagate that exception rather than silently falling back
   501	    to the offline converter.
   502	    """
   503	    from unittest.mock import MagicMock, patch
   504	    from vibecomfy.comfy_backend import ComfyCompatibility
   505	    from vibecomfy.ingest.normalize import normalize_to_api
   506	
   507	    failing_converter = MagicMock(side_effect=RuntimeError("converter_exploded"))
   508	    fake_module = MagicMock()
   509	    fake_module.convert_ui_to_api = failing_converter
   510	    compatible = ComfyCompatibility(
   511	        ok=True,
   512	        reason_code="ok",
   513	        expected={"commit": "expected", "version": "pinned"},
   514	        actual={"commit": "expected", "version": None},
   515	        safe_families=[],
   516	    )
   517	
   518	    with patch.dict("sys.modules", {
   519	        "comfy": MagicMock(),
   520	        "comfy.component_model": MagicMock(),
   521	        "comfy.component_model.workflow_convert": fake_module,
   522	    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=compatible):
   523	        try:
   524	            normalize_to_api(_MINIMAL_UI_RAW)
   525	        except RuntimeError as exc:
   526	            assert "converter_exploded" in str(exc)
   527	        else:
   528	            raise AssertionError(
   529	                "Expected RuntimeError to propagate by default when "
   530	                "convert_ui_to_api raises"
   531	            )
   532	
   533	
   534	def test_comfy_converter_strict_false_tolerant_when_converter_errors() -> None:
   535	    """comfy_converter_strict=False keeps the explicit tolerant fallback path.
   536	
   537	    When comfy IS importable but ``convert_ui_to_api`` raises, the explicit
   538	    ``comfy_converter_strict=False`` opt-out must still fall through to the
   539	    offline converter.
   540	    """
   541	    from unittest.mock import MagicMock, patch
   542	    from vibecomfy.ingest.normalize import normalize_to_api
   543	
   544	    failing_converter = MagicMock(side_effect=RuntimeError("converter_exploded"))
   545	    fake_module = MagicMock()
   546	    fake_module.convert_ui_to_api = failing_converter
   547	
   548	    with patch.dict("sys.modules", {
   549	        "comfy": MagicMock(),
   550	        "comfy.component_model": MagicMock(),
   551	        "comfy.component_model.workflow_convert": fake_module,
   552	    }), pytest.warns(UserWarning, match="falling back to the offline normalizer"):
   553	        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)
   554	
   555	    assert isinstance(result, dict), "offline fallback must produce a dict"
   556	    assert "1" in result, "offline result must contain the single node"
   557	
   558	
   559	def test_comfy_converter_strict_surfaces_version_skew_before_converter_exec() -> None:
   560	    """Strict live-converter paths fence on skew before calling convert_ui_to_api."""
   561	    from unittest.mock import MagicMock, patch
   562	
   563	    from vibecomfy.comfy_backend import ComfyCompatibility, ComfyCompatibilityError
   564	    from vibecomfy.ingest.normalize import normalize_to_api
   565	
   566	    converter = MagicMock(side_effect=RuntimeError("raw_traceback_should_not_escape"))
   567	    fake_module = MagicMock()
   568	    fake_module.convert_ui_to_api = converter
   569	    mismatch = ComfyCompatibility(
   570	        ok=False,
   571	        reason_code="comfyui_version_skew",
   572	        expected={"commit": "expected", "version": "pinned"},
   573	        actual={"commit": "actual", "version": "other"},
   574	        safe_families=[],
   575	    )
   576	
   577	    with patch.dict("sys.modules", {
   578	        "comfy": MagicMock(),
   579	        "comfy.component_model": MagicMock(),
   580	        "comfy.component_model.workflow_convert": fake_module,
   581	    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=mismatch):
   582	        with pytest.raises(ComfyCompatibilityError, match="comfyui_version_skew") as excinfo:
   583	            normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)
   584	
   585	    converter.assert_not_called()
   586	    assert excinfo.value.compatibility == mismatch
   587	
   588	
   589	def test_comfy_converter_lenient_skew_falls_back_offline_without_converter_exec() -> None:
   590	    """Lenient live-converter paths still skip converter execution on version skew."""
   591	    from unittest.mock import MagicMock, patch
   592	
   593	    from vibecomfy.comfy_backend import ComfyCompatibility
   594	    from vibecomfy.ingest.normalize import normalize_to_api
   595	
   596	    converter = MagicMock(side_effect=RuntimeError("raw_traceback_should_not_escape"))
   597	    fake_module = MagicMock()
   598	    fake_module.convert_ui_to_api = converter
   599	    mismatch = ComfyCompatibility(
   600	        ok=False,
   601	        reason_code="comfyui_version_skew",
   602	        expected={"commit": "expected", "version": "pinned"},
   603	        actual={"commit": "actual", "version": "other"},
   604	        safe_families=[],
   605	    )
   606	
   607	    with patch.dict("sys.modules", {
   608	        "comfy": MagicMock(),
   609	        "comfy.component_model": MagicMock(),
   610	        "comfy.component_model.workflow_convert": fake_module,
   611	    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=mismatch), pytest.warns(
   612	        UserWarning, match="comfyui_version_skew"
   613	    ):
   614	        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)
   615	
   616	    converter.assert_not_called()
   617	    assert isinstance(result, dict)
   618	    assert "1" in result
   619	
   620	
   621	# ═══════════════════════════════════════════════════════════════════════════════
   622	# B02-C1 — lossless rich-envelope decode (serialized Vibe → IR → canonical UI)
   623	# ═══════════════════════════════════════════════════════════════════════════════
   624	
   625	_CORPUS_90A1D5 = (
   626	    Path(__file__).resolve().parent
   627	    / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json"
   628	)
   629	
   630	
   631	def _load_90a1d5() -> dict:
   632	    return json.loads(_CORPUS_90A1D5.read_text(encoding="utf-8"))
   633	
   634	
   635	def _ui_projection(ui: dict) -> dict:
   636	    """Deterministic projection of a canonical UI envelope for idempotence compare."""
   637	    nodes = sorted(
   638	        (
   639	            node["id"],
   640	            node["type"],
   641	            node.get("mode"),
   642	            (node.get("properties") or {}).get("vibecomfy_uid"),
   643	            json.dumps(node.get("widgets_values"), sort_keys=True),
   644	        )
   645	        for node in ui.get("nodes", [])
   646	    )
   647	    links = sorted((link[1], link[2], link[3], link[4]) for link in ui.get("links", []))
   648	    return {
   649	        "node_count": len(nodes),
   650	        "nodes": nodes,
   651	        "link_count": len(links),
   652	        "links": links,
   653	        "groups": ui.get("groups", []),
   654	    }
   655	
   656	
   657	def test_vibe_rich_ingest_preserves_90a1d5() -> None:
   658	    """The rich envelope decodes fully and derives its two-node execution view fresh."""
   659	    raw = _load_90a1d5()
   660	    assert "compiled_api" not in raw
   661	
   662	    wf = convert_to_vibe_format(raw)
   663	
   664	    assert len(wf.nodes) == 15
   665	    assert len(wf.edges) == 10
   666	    assert len(wf.outputs) == len(raw["outputs"])
   667	    assert wf.id == raw["id"]
   668	    assert wf.source.id == raw["source"]["id"]
   669	    assert wf.strict_types is False
   670	    assert wf.metadata["external_workflow"] is True
   671	    assert len(wf.compile("api")) == 2
   672	
   673	    uids = [node.uid for node in wf.nodes.values()]
   674	    assert len(set(uids)) == 15, "uids must all be distinct"
   675	    assert all(isinstance(uid, str) and uid.strip() for uid in uids)
   676	
   677	    modes = Counter(node.mode for node in wf.nodes.values())
   678	    assert dict(modes) == {4: 9, 0: 6}
   679	
   680	    assert wf.nodes["10"].class_type == "TripoRefineNode"
   681	    assert wf.nodes["10"].uid == raw["nodes"]["10"]["uid"]
   682	
   683	    # Lossless: every rich node's uid/metadata._ui/inputs/widgets decode verbatim.
   684	    for nid, node in wf.nodes.items():
   685	        rich = raw["nodes"][nid]
   686	        assert node.uid == rich["uid"], f"node {nid}: uid not preserved exactly"
   687	        assert node.class_type == rich["class_type"], f"node {nid}: class_type mismatch"
   688	        assert node.metadata["_ui"] == rich["metadata"]["_ui"], (
   689	            f"node {nid}: metadata._ui not preserved verbatim"
   690	        )
   691	        assert node.metadata["provenance"] == "untrusted_source"
   692	        assert node.inputs == rich["inputs"]
   693	        assert node.widgets == rich["widgets"]
   694	
   695	    # Canonical UI carries every rich node with the same id/class/mode/uid projection.
   696	    normalized = normalize_agent_edit_graph(raw)
   697	    assert len(normalized["nodes"]) == 15
   698	    assert len(normalized["links"]) == 10
   699	    by_id = {str(node["id"]): node for node in normalized["nodes"]}
   700	    assert set(by_id) == set(raw["nodes"])
   701	    for nid, rich in raw["nodes"].items():
   702	        ui_node = by_id[nid]
   703	        assert ui_node["type"] == rich["class_type"]
   704	        assert ui_node["mode"] == rich["metadata"]["_ui"]["mode"]
   705	        assert (ui_node.get("properties") or {})["vibecomfy_uid"] == rich["uid"]
   706	
   707	
   708	def test_vibe_rich_ingest_ignores_optional_compiled_api_evidence() -> None:
   709	    """Rich structure remains authoritative without stored execution evidence or with bad evidence."""
   710	    raw = _load_90a1d5()
   711	
   712	    assert "compiled_api" not in raw
   713	    assert len(convert_to_vibe_format(raw).nodes) == 15
   714	
   715	    malformed_evidence = deepcopy(raw)
   716	    malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}
   717	    workflow = convert_to_vibe_format(malformed_evidence)
   718	    assert len(workflow.nodes) == 15
   719	    assert workflow.nodes["10"].class_type == "TripoRefineNode"
   720	
   721	
   722	def test_public_loaders_preserve_rich_envelope_90a1d5() -> None:
   723	    """load_workflow_any / load_port_source decode envelopes losslessly (P1).
   724	
   725	    Public loaders must return the full 15-node IR, not the 2-node compile
   726	    view: they decode the envelope directly instead of compile-then-reingest.
   727	    The execution view (compile("api")) is unchanged at 2 nodes.
   728	    """
   729	    from vibecomfy.cli_loader import load_workflow_any
   730	    from vibecomfy.porting.workbench import load_port_source
   731	
   732	    corpus = str(_CORPUS_90A1D5)
   733	
   734	    wf = load_workflow_any(corpus)
   735	    assert len(wf.nodes) == 15
   736	    assert wf.nodes["10"].class_type == "TripoRefineNode"
   737	    assert len(wf.compile("api")) == 2
   738	
   739	    loaded = load_port_source(corpus)
   740	    assert len(loaded.workflow.nodes) == 15
   741	    assert loaded.workflow.nodes["10"].class_type == "TripoRefineNode"
   742	    assert len(loaded.workflow.compile("api")) == 2
   743	    assert loaded.source_kind in {"indexed_json", "raw_json"}
   744	
   745	
   746	def test_vibe_rich_ingest_is_idempotent() -> None:
   747	    """rich->UI and UI->IR->UI produce identical projections (nodes, edges, widgets, groups)."""
   748	    raw = _load_90a1d5()
   749	
   750	    ui1 = normalize_agent_edit_graph(raw)  # rich -> UI
   751	    assert len(ui1["nodes"]) == 15 and len(ui1["links"]) == 10
   752	
   753	    # UI -> IR via the deterministic offline normalizer (the comfy converter
   754	    # intentionally drops mode-4 bypassed nodes — ComfyUI semantics, unchanged).
   755	    api2 = normalize_to_api(ui1, use_comfy_converter=False)
   756	    wf2 = convert_to_vibe_format(api2)
   757	    assert len(wf2.nodes) == 15 and len(wf2.edges) == 10
   758	
   759	    ui2 = emit_ui_json(wf2, schema_provider=None, groups=deepcopy(ui1.get("groups")))
   760	
   761	    assert _ui_projection(ui1) == _ui_projection(ui2)
   762	
   763	
   764	def test_vibe_rich_ingest_rejects_malformed_mixed_entries() -> None:
   765	    """Malformed/mixed rich entries raise ValueError; no partial graph is returned."""
   766	    raw = _load_90a1d5()
   767	
   768	    mixed_nodes = deepcopy(raw)
   769	    mixed_nodes["nodes"]["999"] = "not-a-node"
   770	    with pytest.raises(ValueError, match="must be mappings"):
   771	        convert_to_vibe_format(mixed_nodes)
   772	
   773	    key_mismatch = deepcopy(raw)
   774	    key_mismatch["nodes"]["10"]["id"] = "11"
   775	    with pytest.raises(ValueError, match="must equal node.id"):
   776	        convert_to_vibe_format(key_mismatch)
   777	
   778	    blank_uid = deepcopy(raw)
   779	    blank_uid["nodes"]["10"]["uid"] = "  "
   780	    with pytest.raises(ValueError, match="uid must be a nonblank string"):
   781	        convert_to_vibe_format(blank_uid)
   782	
   783	    negative_length = deepcopy(raw)
   784	    negative_length["nodes"]["10"]["raw_widgets"]["length"] = -1
   785	    with pytest.raises(ValueError, match="nonnegative integer"):
   786	        convert_to_vibe_format(negative_length)
   787	
   788	    non_mapping_edges = deepcopy(raw)
   789	    non_mapping_edges["edges"] = ["not-an-edge"]
   790	    with pytest.raises(ValueError, match="must be mappings"):
   791	        convert_to_vibe_format(non_mapping_edges)
   792	
   793	
   794	def test_vibe_rich_ingest_rejects_dangling_endpoint_edges() -> None:
   795	    """Edges referencing endpoint node ids absent from nodes raise ValueError."""
   796	    raw = _load_90a1d5()
   797	
   798	    dangling_from = deepcopy(raw)
   799	    dangling_from["edges"] = [
   800	        {"from_node": "999", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
   801	    ]
   802	    with pytest.raises(ValueError, match="must exist in nodes"):
   803	        convert_to_vibe_format(dangling_from)
   804	
   805	    dangling_to = deepcopy(raw)
   806	    dangling_to["edges"] = [
   807	        {"from_node": "3", "from_output": "0", "to_node": "424242", "to_input": "model_file"}
   808	    ]
   809	    with pytest.raises(ValueError, match="must exist in nodes"):
   810	        convert_to_vibe_format(dangling_to)
   811	
   812	    blank_endpoint = deepcopy(raw)
   813	    blank_endpoint["edges"] = [
   814	        {"from_node": "", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
   815	    ]
   816	    with pytest.raises(ValueError, match="from_node must be a nonblank string"):
   817	        convert_to_vibe_format(blank_endpoint)
   818	
   819	
   820	def test_vibe_rich_ingest_rejects_incomplete_envelope() -> None:
   821	    """A vibe envelope missing required top-level sections is rejected, never partial."""
   822	    raw = _load_90a1d5()
   823	
   824	    for field in ("source", "requirements", "inputs", "edges"):
   825	        partial = deepcopy(raw)
   826	        del partial[field]
   827	        with pytest.raises(ValueError):
   828	            convert_to_vibe_format(partial)
   829	
   830	    bad_outputs = deepcopy(raw)
   831	    bad_outputs["outputs"] = "not-a-list"
   832	    with pytest.raises(ValueError, match="outputs.*must be a list"):
   833	        convert_to_vibe_format(bad_outputs)
   834	
   835	    bad_strict = deepcopy(raw)
   836	    bad_strict["strict_types"] = "yes"
   837	    with pytest.raises(ValueError, match="strict_types must be a boolean"):
   838	        convert_to_vibe_format(bad_strict)
   839	
   840	
   841	# ═══════════════════════════════════════════════════════════════════════════════
   842	# P5 — VibeWorkflow.to_envelope / from_envelope (one writer, one fail-closed reader)
   843	# ═══════════════════════════════════════════════════════════════════════════════
   844	
   845	
   846	def test_to_envelope_from_envelope_round_trip_90a1d5() -> None:
   847	    """to_envelope(from_envelope(90a1d5)) preserves 15/10/15 uids/modes; compile stays 2."""
   848	    from vibecomfy.workflow import FORMAT_VERSION, VibeWorkflow, from_envelope
   849	
   850	    raw = _load_90a1d5()
   851	    wf = from_envelope(raw)
   852	    via_convert = convert_to_vibe_format(raw)
   853	    assert set(wf.nodes) == set(via_convert.nodes)
   854	    assert len(wf.nodes) == 15
   855	    assert len(wf.edges) == 10
   856	    assert {node.uid for node in wf.nodes.values()} == {
   857	        node.uid for node in via_convert.nodes.values()
   858	    }
   859	    assert all(node.uid.strip() for node in wf.nodes.values())
   860	    assert dict(Counter(node.metadata.get("mode") for node in wf.nodes.values())) == {4: 9, 0: 6}
   861	
   862	    envelope = wf.to_envelope()
   863	    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
   864	    assert "compiled_api" not in envelope
   865	    assert len(envelope["nodes"]) == 15
   866	    assert len(envelope["edges"]) == 10
   867	
   868	    wf2 = VibeWorkflow.from_envelope(envelope)
   869	    assert len(wf2.nodes) == 15
   870	    assert len(wf2.edges) == 10
   871	    assert {node.uid for node in wf2.nodes.values()} == {node.uid for node in wf.nodes.values()}
   872	    assert dict(Counter(node.metadata.get("mode") for node in wf2.nodes.values())) == {4: 9, 0: 6}
   873	    for nid, node in wf2.nodes.items():
   874	        original = raw["nodes"][nid]
   875	        assert node.uid == original["uid"]
   876	        assert node.metadata["_ui"] == original["metadata"]["_ui"]
   877	        assert node.inputs == original["inputs"]
   878	        assert node.widgets == original["widgets"]
   879	    assert len(wf2.compile("api")) == 2
   880	    assert set(wf2.compile("api")) == {"3", "17"}
   881	
   882	
   883	def test_from_envelope_hand_built_old_style_without_compiled_api() -> None:
   884	    """A hand-built (old-style) envelope without compiled_api still decodes losslessly."""
   885	    from vibecomfy.workflow import VibeWorkflow
   886	
   887	    envelope = {
   888	        "id": "hand-built",
   889	        "vibecomfy_format_version": "1.0",
   890	        "source": {"id": "hand-built", "source_type": "vibe", "path": None, "provenance": {}},
   891	        "requirements": {
   892	            "models": [],
   893	            "custom_nodes": [],
   894	            "missing_models": [],
   895	            "missing_nodes": [],
   896	            "unsupported": [],
   897	        },
   898	        "nodes": {
   899	            "1": {
   900	                "id": "1",
   901	                "class_type": "CheckpointLoaderSimple",
   902	                "pack": None,
   903	                "inputs": {"ckpt_name": "model.safetensors"},
   904	                "widgets": {},
   905	                "metadata": {"_ui": {"mode": 0}, "mode": 0},
   906	                "uid": "uid-loader",
   907	            },
   908	            "2": {
   909	                "id": "2",
   910	                "class_type": "PreviewImage",
   911	                "pack": None,
   912	                "inputs": {},
   913	                "widgets": {},
   914	                "metadata": {"_ui": {"mode": 4}, "mode": 4},
   915	                "uid": "uid-preview",
   916	            },
   917	        },
   918	        "edges": [
   919	            {
   920	                "from_node": "1",
   921	                "from_output": "MODEL",
   922	                "to_node": "2",
   923	                "to_input": "images",
   924	            }
   925	        ],
   926	        "inputs": {},
   927	        "outputs": [{"node_id": "2", "output_type": "IMAGE"}],
   928	        "metadata": {"note": "old-style"},
   929	        "strict_types": False,
   930	    }
   931	    assert "compiled_api" not in envelope
   932	
   933	    wf = VibeWorkflow.from_envelope(envelope)
   934	    assert len(wf.nodes) == 2
   935	    assert len(wf.edges) == 1
   936	    assert wf.nodes["1"].uid == "uid-loader"
   937	    assert wf.nodes["1"].inputs["ckpt_name"] == "model.safetensors"
   938	    assert wf.nodes["1"].mode == 0
   939	    assert wf.nodes["2"].mode == 4
   940	    assert wf.nodes["2"].metadata["mode"] == 4
   941	    assert wf.nodes["2"].metadata["_ui"]["mode"] == 4
   942	    assert wf.outputs[0].node_id == "2"
   943	    written = wf.to_envelope()
   944	    assert "compiled_api" not in written
   945	    assert written["nodes"]["1"]["uid"] == "uid-loader"
   946	    assert written["nodes"]["2"]["mode"] == 4
   947	    assert written["nodes"]["2"]["metadata"]["_ui"]["mode"] == 4
   948	
   949	
   950	def test_from_envelope_fails_closed_on_malformed_input() -> None:
   951	    """from_envelope raises on malformed input; it never returns a partial graph."""
   952	    from vibecomfy.workflow import VibeWorkflow
   953	
   954	    good = {
   955	        "id": "closed",
   956	        "source": {"id": "closed"},
   957	        "requirements": {},
   958	        "nodes": {
   959	            "1": {
   960	                "id": "1",
   961	                "class_type": "PreviewImage",
   962	                "inputs": {},
   963	                "widgets": {},
   964	                "metadata": {},
   965	                "uid": "uid-1",
   966	            }
   967	        },
   968	        "edges": [],
   969	        "inputs": {},
   970	        "outputs": [],
   971	    }
   972	    assert len(VibeWorkflow.from_envelope(good).nodes) == 1
   973	
   974	    blank_uid = deepcopy(good)
   975	    blank_uid["nodes"]["2"] = {
   976	        "id": "2",
   977	        "class_type": "PreviewImage",
   978	        "inputs": {},
   979	        "widgets": {},
   980	        "metadata": {},
   981	        "uid": "",
   982	    }
   983	    with pytest.raises(ValueError, match="uid must be a nonblank string"):
   984	        VibeWorkflow.from_envelope(blank_uid)
   985	
   986	    mixed_node = deepcopy(good)
   987	    mixed_node["nodes"]["2"] = "not-a-mapping"
   988	    with pytest.raises(ValueError, match="node entries must be mappings"):
   989	        VibeWorkflow.from_envelope(mixed_node)
   990	
   991	    missing_source = deepcopy(good)
   992	    del missing_source["source"]
   993	    with pytest.raises(ValueError, match="source"):
   994	        VibeWorkflow.from_envelope(missing_source)
   995	
   996	    missing_requirements = deepcopy(good)
   997	    del missing_requirements["requirements"]
   998	    with pytest.raises(ValueError, match="requirements"):
   999	        VibeWorkflow.from_envelope(missing_requirements)
  1000	
  1001	    not_an_object = ["not", "an", "envelope"]
  1002	    with pytest.raises(ValueError, match="must be a JSON object"):
  1003	        VibeWorkflow.from_envelope(not_an_object)  # type: ignore[arg-type]
  1004	
  1005	
  1006	# ═══════════════════════════════════════════════════════════════════════════════
  1007	# P6 — named importers (from_envelope / from_ui / from_api)
  1008	# ═══════════════════════════════════════════════════════════════════════════════
  1009	
  1010	
  1011	def test_named_from_envelope_preserves_90a1d5() -> None:
  1012	    """The public ingest from_envelope door is lossless on the 90a1d5 fixture."""
  1013	    from vibecomfy.ingest import from_envelope
  1014	    from vibecomfy.ingest.normalize import convert_to_vibe_format
  1015	
  1016	    raw = _load_90a1d5()
  1017	    wf = from_envelope(raw)
  1018	    via_convert = convert_to_vibe_format(raw)
  1019	    assert len(wf.nodes) == 15
  1020	    assert len(wf.edges) == 10
  1021	    assert set(wf.nodes) == set(via_convert.nodes)
  1022	    assert {node.uid for node in wf.nodes.values()} == {
  1023	        node.uid for node in via_convert.nodes.values()
  1024	    }
  1025	    assert dict(Counter(node.metadata.get("mode") for node in wf.nodes.values())) == {4: 9, 0: 6}
  1026	    assert len(wf.compile("api")) == 2
  1027	    assert set(wf.compile("api")) == {"3", "17"}
  1028	
  1029	
  1030	def _ir_projection(workflow) -> dict:
  1031	    return {
  1032	        "ids": sorted(workflow.nodes),
  1033	        "classes": {nid: node.class_type for nid, node in workflow.nodes.items()},
  1034	        "uids": {nid: node.uid for nid, node in workflow.nodes.items()},
  1035	        "inputs": {nid: node.inputs for nid, node in workflow.nodes.items()},
  1036	        "widgets": {nid: node.widgets for nid, node in workflow.nodes.items()},
  1037	        "edges": [
  1038	            (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
  1039	            for edge in workflow.edges
  1040	        ],
  1041	    }
  1042	
  1043	
  1044	def test_from_ui_matches_convert_on_ui_fixture() -> None:
  1045	    raw = json.loads(
  1046	        (Path(__file__).parent / "fixtures/reorganise/simple_text_to_image.json").read_text(
  1047	            encoding="utf-8"
  1048	        )
  1049	    )
  1050	    assert _ir_projection(from_ui(raw)) == _ir_projection(convert_to_vibe_format(raw))
  1051	
  1052	
  1053	def test_from_api_matches_convert_on_api_from_ui_fixture() -> None:
  1054	    raw = json.loads(
  1055	        (Path(__file__).parent / "fixtures/reorganise/simple_text_to_image.json").read_text(
  1056	            encoding="utf-8"
  1057	        )
  1058	    )
  1059	    api = normalize_to_api(raw, use_comfy_converter=False)
  1060	    assert _ir_projection(from_api(api)) == _ir_projection(convert_to_vibe_format(api))

exec
/bin/zsh -lc "sed -n '520,760p' scripts/check_b02_rich_preservation.py | nl -ba -v520" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "sed -n '240,520p' scripts/check_b02_rich_preservation.py | nl -ba -v240" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "sed -n '1,240p' scripts/check_b02_rich_preservation.py | nl -ba" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git diff 4a16fc64..2b60f74a -- tests/test_b02_rich_preservation.py tests/test_ingest_external_workflows.py tests/test_porting_normalize_ingest.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 59ms:
     1	"""B02-C4 — corpus-wide rich-preservation proof harness.
     2	
     3	For every serialized-Vibe envelope in ``external_workflows/corpus/*.json``
     4	(a ``vibecomfy_format_version`` + rich ``nodes`` mapping envelope), run the
     5	full canonical pipeline and prove deterministic lossless preservation at every
     6	boundary:
     7	
     8	    rich ──from_envelope──▶ ir1 ──normalize_agent_edit_graph──▶ canonical
     9	         ──normalize_to_api(use_comfy_converter=False)──▶ api ──from_api──▶ ir2
    10	         ──emit_ui_json (using ir2.groups)──▶ reemit
    11	         pin evidence: emit_ui_json(ir1, recovery_report=report)
    12	
    13	Axes asserted (every mismatch records ``(file, axis, node, expected, actual)``
    14	and fails the run):
    15	
    16	  rich→ir1            node id / class_type / stable uid / mode / raw-widgets
    17	                      values+shape+length / widgets_values / non-link furniture
    18	                      (only deterministic id/order/link-id renumbering excluded);
    19	                      edge tuples ``(from_node, from_output, to_node, to_input)``
    20	  rich→canonical      node ids / classes / modes / uids / widgets_values;
    21	                      semantic edge tuples recovered from canonical links via the
    22	                      to-node input names; groups
    23	  rich→ir2            node id / class_type / uid / mode / widgets_values; edges
    24	  canonical idempotence
    25	                      node id/class/mode/uid/widgets_values, groups, and link
    26	                      endpoint+slot topology (link ids/types excluded)
    27	  pin evidence        every ``widget_shape_verdict == "pin_opaque"`` report entry
    28	                      maps to an emitted node whose ``properties.vibecomfy_uid``
    29	                      equals the decoded canonical node uid
    30	  uidless emissions   global blank/missing ``properties.vibecomfy_uid`` count == 0
    31	
    32	Expected schema-less warnings are suppressed; exceptions are never swallowed —
    33	a pipeline refusal/exception is recorded as a ``(file, axis, ...)`` mismatch row
    34	and fails the run.
    35	
    36	Run as a CLI to get one final JSON summary on stdout:
    37	
    38	    .venv/bin/python scripts/check_b02_rich_preservation.py \
    39	        --corpus-dir tests/fixtures/b02_corpus_mini --expected-count 3
    40	
    41	Exit code is 0 iff zero mismatches and zero uid-less emissions.
    42	"""
    43	
    44	from __future__ import annotations
    45	
    46	import argparse
    47	import json
    48	import sys
    49	import warnings
    50	from copy import deepcopy
    51	from pathlib import Path
    52	from typing import Any
    53	
    54	from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
    55	from vibecomfy.ingest import from_api, from_envelope, normalize_to_api
    56	from vibecomfy.porting.emit.ui import emit_ui_json
    57	from vibecomfy.porting.refuse import RefusedEmit
    58	
    59	# Keys whose values are deterministic renumbering artifacts of the canonical
    60	# emission (node ids, draw order, link refs) — excluded from raw-UI furniture
    61	# comparisons by contract.
    62	_RENUMBERED_KEYS: frozenset[str] = frozenset({"id", "order", "link", "links"})
    63	
    64	_SCHEMA_LESS_WARNING = ".*schema-less.*"
    65	
    66	
    67	# ---------------------------------------------------------------------------
    68	# Projections
    69	# ---------------------------------------------------------------------------
    70	
    71	
    72	def _strip_renumbered(value: Any) -> Any:
    73	    """Recursively drop deterministic renumbering fields (id/order/link refs)."""
    74	    if isinstance(value, dict):
    75	        return {
    76	            key: _strip_renumbered(item)
    77	            for key, item in value.items()
    78	            if key not in _RENUMBERED_KEYS
    79	        }
    80	    if isinstance(value, list):
    81	        return [_strip_renumbered(item) for item in value]
    82	    return value
    83	
    84	
    85	def _ui_of(metadata: Any) -> dict[str, Any]:
    86	    ui = metadata.get("_ui") if isinstance(metadata, dict) else None
    87	    return ui if isinstance(ui, dict) else {}
    88	
    89	
    90	def _legacy_mode_of(metadata: Any) -> int:
    91	    """Legacy mode: raw ``_ui.mode``, then top-level metadata mode, else 0."""
    92	    ui = _ui_of(metadata)
    93	    if isinstance(ui.get("mode"), int) and not isinstance(ui["mode"], bool):
    94	        return ui["mode"]
    95	    value = metadata.get("mode")
    96	    return value if isinstance(value, int) and not isinstance(value, bool) else 0
    97	
    98	
    99	def _mode_of(entry: Any) -> int:
   100	    """First-class node mode, with legacy metadata fallback for old envelopes."""
   101	    if isinstance(entry, dict):
   102	        value = entry.get("mode")
   103	        if isinstance(value, int) and not isinstance(value, bool):
   104	            return value
   105	        return _legacy_mode_of(entry.get("metadata") or {})
   106	    value = getattr(entry, "mode", None)
   107	    if isinstance(value, int) and not isinstance(value, bool):
   108	        return value
   109	    return _legacy_mode_of(getattr(entry, "metadata", {}))
   110	
   111	
   112	def _widgets_values_of(metadata: Any) -> Any:
   113	    """Raw UI widgets_values evidence; absent/null → no evidence (nothing to preserve)."""
   114	    value = _ui_of(metadata).get("widgets_values")
   115	    return deepcopy(value) if value is not None else None
   116	
   117	
   118	def _raw_widgets_projection(raw_widgets: Any) -> dict[str, Any] | None:
   119	    """RawWidgetPayload (IR) or raw dict (envelope) → comparable projection."""
   120	    if raw_widgets is None:
   121	        return None
   122	    if not isinstance(raw_widgets, dict):
   123	        return {
   124	            "values": deepcopy(raw_widgets.values),
   125	            "shape": raw_widgets.shape,
   126	            "length": raw_widgets.length,
   127	            "has_dict_rows": raw_widgets.has_dict_rows,
   128	        }
   129	    return {
   130	        "values": deepcopy(raw_widgets.get("values")),
   131	        "shape": raw_widgets.get("shape"),
   132	        "length": raw_widgets.get("length"),
   133	        "has_dict_rows": raw_widgets.get("has_dict_rows"),
   134	    }
   135	
   136	
   137	def rich_node_projection(node_id: str, entry: dict[str, Any]) -> dict[str, Any]:
   138	    """Deterministic rich-envelope node projection (the decode input side)."""
   139	    metadata = entry.get("metadata") or {}
   140	    return {
   141	        "id": entry.get("id"),
   142	        "class_type": entry.get("class_type"),
   143	        "uid": entry.get("uid"),
   144	        "mode": _mode_of(entry),
   145	        "raw_widgets": _raw_widgets_projection(entry.get("raw_widgets")),
   146	        "widgets_values": _widgets_values_of(metadata),
   147	        "furniture": _strip_renumbered(_ui_of(metadata)),
   148	    }
   149	
   150	
   151	def ir_node_projection(node: Any) -> dict[str, Any]:
   152	    """IR (VibeNode) projection mirroring :func:`rich_node_projection`."""
   153	    metadata = node.metadata
   154	    return {
   155	        "id": node.id,
   156	        "class_type": node.class_type,
   157	        "uid": node.uid,
   158	        "mode": _mode_of(node),
   159	        "raw_widgets": _raw_widgets_projection(node.raw_widgets),
   160	        "widgets_values": _widgets_values_of(metadata),
   161	        "furniture": _strip_renumbered(_ui_of(metadata)),
   162	    }
   163	
   164	
   165	def edge_tuple(edge: Any) -> tuple[str, str, str, str]:
   166	    """Exact semantic edge tuple shared by rich envelope edges and IR edges."""
   167	    return (
   168	        str(edge.from_node),
   169	        str(edge.from_output),
   170	        str(edge.to_node),
   171	        str(edge.to_input),
   172	    )
   173	
   174	
   175	def rich_edge_tuples(rich: dict[str, Any]) -> set[tuple[str, str, str, str]]:
   176	    return {
   177	        (str(edge["from_node"]), str(edge["from_output"]), str(edge["to_node"]), str(edge["to_input"]))
   178	        for edge in rich.get("edges", [])
   179	    }
   180	
   181	
   182	def canonical_node_projection(node: dict[str, Any]) -> dict[str, Any]:
   183	    properties = node.get("properties") or {}
   184	    return {
   185	        "id": node.get("id"),
   186	        "class_type": node.get("type"),
   187	        "mode": node.get("mode", 0),
   188	        "uid": properties.get("vibecomfy_uid"),
   189	        "widgets_values": node.get("widgets_values"),
   190	    }
   191	
   192	
   193	def canonical_nodes_by_id(canonical: dict[str, Any]) -> dict[Any, dict[str, Any]]:
   194	    return {
   195	        node.get("id"): canonical_node_projection(node)
   196	        for node in canonical.get("nodes", [])
   197	    }
   198	
   199	
   200	def canonical_link_topology(canonical: dict[str, Any]) -> set[tuple[int, int, int, int]]:
   201	    """Canonical link projection: endpoint + slot topology, link ids/types excluded."""
   202	    return {
   203	        (int(link[1]), int(link[2]), int(link[3]), int(link[4]))
   204	        for link in canonical.get("links", [])
   205	    }
   206	
   207	
   208	def canonical_semantic_edges(canonical: dict[str, Any]) -> set[tuple[str, str, str, str]]:
   209	    """Recover ``(from_node, from_output, to_node, to_input)`` tuples from the
   210	    canonical envelope by resolving each link's target input name through the
   211	    to-node's emitted ``inputs`` entries (link id → name)."""
   212	    link_to_input: dict[int, tuple[str, int]] = {}
   213	    for node in canonical.get("nodes", []):
   214	        for input_entry in node.get("inputs") or []:
   215	            link_id = input_entry.get("link")
   216	            if link_id is not None:
   217	                link_to_input[int(link_id)] = (str(input_entry.get("name", "")), int(node["id"]))
   218	    tuples: set[tuple[str, str, str, str]] = set()
   219	    for link in canonical.get("links", []):
   220	        name, _ = link_to_input.get(int(link[0]), ("", int(link[3])))
   221	        tuples.add((str(link[1]), str(link[2]), str(link[3]), name))
   222	    return tuples
   223	
   224	
   225	def _canonical_id_of(rich_node_id: str) -> Any:
   226	    """Rich node id → canonical litegraph node id (numeric ids become integers)."""
   227	    return int(rich_node_id) if rich_node_id.isdigit() else rich_node_id
   228	
   229	
   230	def _record(result: dict[str, Any], axis: str, node: Any, expected: Any, actual: Any) -> None:
   231	    result["mismatches"].append((axis, node, expected, actual))
   232	
   233	
   234	def _truncate(value: Any, limit: int = 400) -> str:
   235	    text = repr(value)
   236	    return text if len(text) <= limit else text[:limit] + f"...<{len(text)} bytes>"
   237	
   238	
   239	# ---------------------------------------------------------------------------
   240	# Per-envelope check

exec
/bin/zsh -lc 'rg -n "migrate_corpus|migration|layout sidecar|zero envelopes|compiled_api|expected-count" tests/test_b02_rich_preservation.py tests/test_ingest_external_workflows.py tests/test_porting_normalize_ingest.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 147ms:
   520	        raw = json.loads(path.read_text(encoding="utf-8"))
   521	        if (
   522	            not isinstance(raw, dict)
   523	            or not isinstance(raw.get("nodes"), dict)
   524	            or "vibecomfy_format_version" not in raw
   525	        ):
   526	            continue
   527	        found += 1
   528	        yield path, raw
   529	    if found == 0:
   530	        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
   531	
   532	
   533	def check_corpus(
   534	    corpus_dir: str | Path,
   535	    *,
   536	    expected_count: int | None = None,
   537	) -> dict[str, Any]:
   538	    """Run :func:`check_envelope` over the whole corpus and aggregate counts.
   539	
   540	    Deterministic: files are processed in sorted order and all set comparisons
   541	    are order-independent.  Returns one summary dict with totals, per-axis
   542	    mismatch counts, and per-file mismatch rows.
   543	    """
   544	    summary: dict[str, Any] = {
   545	        "ok": True,
   546	        "checked": 0,
   547	        "skipped": 0,
   548	        "skipped_sidecars": 0,
   549	        "workflows": 0,
   550	        "skipped_non_envelopes": 0,
   551	        "rich_nodes": 0,
   552	        "rich_edges": 0,
   553	        "canonical_nodes": 0,
   554	        "canonical_links": 0,
   555	        "groups": 0,
   556	        "pin_opaque": 0,
   557	        "uidless": 0,
   558	        "mismatch_count": 0,
   559	        "mismatches_by_axis": {},
   560	        "refused_files": [],
   561	        "mismatch_rows": [],
   562	    }
   563	    _, paths = _corpus_paths(corpus_dir)
   564	    for path in paths:
   565	        name = path.name
   566	        if name.endswith(".layout.json"):
   567	            summary["skipped"] += 1
   568	            summary["skipped_sidecars"] += 1
   569	            continue
   570	        try:
   571	            raw = json.loads(path.read_text(encoding="utf-8"))
   572	        except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
   573	            summary["skipped"] += 1
   574	            _record_row(summary, name, "exception", None, "JSON must parse", f"{type(exc).__name__}: {exc}")
   575	            continue
   576	        if (
   577	            not isinstance(raw, dict)
   578	            or not isinstance(raw.get("nodes"), dict)
   579	            or "vibecomfy_format_version" not in raw
   580	        ):
   581	            summary["skipped"] += 1
   582	            summary["skipped_non_envelopes"] += 1
   583	            continue
   584	
   585	        summary["checked"] += 1
   586	        summary["workflows"] += 1
   587	        result = check_envelope(raw)
   588	        result["file"] = name
   589	        summary["rich_nodes"] += result["rich_nodes"]
   590	        summary["rich_edges"] += result["rich_edges"]
   591	        summary["canonical_nodes"] += result["canonical_nodes"]
   592	        summary["canonical_links"] += result["canonical_links"]
   593	        summary["groups"] += result["groups"]
   594	        summary["pin_opaque"] += result["pin_opaque"]
   595	        summary["uidless"] += result["uidless"]
   596	        for axis, node, expected, actual in result["mismatches"]:
   597	            _record_row(summary, name, axis, node, expected, actual)
   598	        for axis, node, expected, actual in result["mismatches"]:
   599	            if axis == "emit_refused":
   600	                summary["refused_files"].append([name, _truncate(node), _truncate(actual)])
   601	
   602	    if summary["checked"] == 0:
   603	        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
   604	    summary["expected_count"] = expected_count
   605	    summary["count_matches"] = expected_count is None or summary["checked"] == expected_count
   606	    summary["mismatch_count"] = len(summary["mismatch_rows"])
   607	    summary["ok"] = (
   608	        summary["mismatch_count"] == 0
   609	        and summary["uidless"] == 0
   610	        and summary["count_matches"]
   611	    )
   612	    return summary
   613	
   614	
   615	def _record_row(
   616	    summary: dict[str, Any],
   617	    file: str,
   618	    axis: str,
   619	    node: Any,
   620	    expected: Any,
   621	    actual: Any,
   622	) -> None:
   623	    summary["mismatches_by_axis"][axis] = summary["mismatches_by_axis"].get(axis, 0) + 1
   624	    summary["mismatch_rows"].append(
   625	        [file, axis, _truncate(node), _truncate(expected), _truncate(actual)]
   626	    )
   627	
   628	
   629	# ---------------------------------------------------------------------------
   630	# CLI
   631	# ---------------------------------------------------------------------------
   632	
   633	
   634	def main(argv: list[str] | None = None) -> int:
   635	    parser = argparse.ArgumentParser(description=__doc__)
   636	    parser.add_argument(
   637	        "--corpus-dir",
   638	        required=True,
   639	        help="explicit directory of serialized-Vibe corpus envelopes",
   640	    )
   641	    parser.add_argument(
   642	        "--expected-count",
   643	        type=int,
   644	        help="fail unless exactly this many envelopes are checked",
   645	    )
   646	    args = parser.parse_args(argv)
   647	
   648	    try:
   649	        summary = check_corpus(args.corpus_dir, expected_count=args.expected_count)
   650	    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
   651	        parser.error(str(exc))
   652	    print(json.dumps(summary, indent=2, sort_keys=True))
   653	    return 0 if summary["ok"] else 1
   654	
   655	
   656	if __name__ == "__main__":
   657	    sys.exit(main())

 succeeded in 71ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/test_b02_rich_preservation.py b/tests/test_b02_rich_preservation.py
index 521c895e..95b0bf7c 100644
--- a/tests/test_b02_rich_preservation.py
+++ b/tests/test_b02_rich_preservation.py
@@ -1,11 +1,9 @@
 """B02-C4 — corpus-wide rich-preservation proof tests.
 
-Executes :mod:`scripts.check_b02_rich_preservation` over the ENTIRE
-``external_workflows/corpus`` (every serialized-Vibe envelope) and asserts the
-preservation proof holds: zero projection mismatches and zero uid-less
-emissions.  The corpus is traversed exactly once per test session via
-module-scoped caching.  No environment-variable skip: the proof either holds or
-it fails with a precise per-file/per-axis report.
+Executes :mod:`scripts.check_b02_rich_preservation` over a tracked mini corpus
+of real, migrated serialized-Vibe envelopes and asserts the preservation proof
+holds: zero projection mismatches and zero uid-less emissions. The full ignored
+corpus is exercised explicitly by ``make b02-corpus-full CORPUS_DIR=...``.
 
 A synthetic rich envelope with nonempty groups and real link/edge topology
 proves the groups and semantic link projections survive the pipeline and that
@@ -15,12 +13,20 @@ the checker's projections are not vacuous (a corrupted copy is detected).
 from __future__ import annotations
 
 import functools
+import json
+import shutil
 from copy import deepcopy
+from pathlib import Path
 from typing import Any
 
 import pytest
 
 from scripts import check_b02_rich_preservation as b02
+from scripts import migrate_external_workflow_corpus as migrate
+from vibecomfy.ingest import from_envelope
+
+
+MINI_CORPUS = Path(__file__).parent / "fixtures" / "b02_corpus_mini"
 
 
 # ---------------------------------------------------------------------------
@@ -30,7 +36,7 @@ from scripts import check_b02_rich_preservation as b02
 
 @functools.lru_cache(maxsize=1)
 def _corpus_summary() -> dict[str, Any]:
-    return b02.check_corpus()
+    return b02.check_corpus(MINI_CORPUS, expected_count=3)
 
 
 def _failure_digest(summary: dict[str, Any], limit: int = 25) -> str:
@@ -70,6 +76,105 @@ def test_corpus_zero_uidless_emissions() -> None:
     assert summary["uidless"] == 0, _failure_digest(summary)
 
 
+def test_mini_corpus_is_first_class_and_execution_is_freshly_derived() -> None:
+    envelopes = list(b02.iter_corpus(MINI_CORPUS))
+    assert len(envelopes) == 3
+    for _path, raw in envelopes:
+        assert "compiled_api" not in raw
+        assert isinstance(raw["groups"], list)
+        assert all(
+            isinstance(entry.get("mode"), int) and not isinstance(entry["mode"], bool)
+            for entry in raw["nodes"].values()
+        )
+        # Legacy UI evidence remains in place even though first-class mode is authoritative.
+        for entry in raw["nodes"].values():
+            ui = entry.get("metadata", {}).get("_ui")
+            if isinstance(ui, dict) and "mode" in ui:
+                assert ui["mode"] == entry["mode"]
+        derived_api = from_envelope(raw).compile("api")
+        assert isinstance(derived_api, dict)
+        assert derived_api
+
+
+def test_checker_reports_checked_and_skipped_sidecar_counts() -> None:
+    summary = _corpus_summary()
+    assert summary["checked"] == 3
+    assert summary["skipped"] == 1
+    assert summary["skipped_sidecars"] == 1
+
+
+def test_checker_rejects_missing_and_empty_corpus_dirs(tmp_path: Path) -> None:
+    with pytest.raises(FileNotFoundError, match="does not exist"):
+        b02.check_corpus(tmp_path / "missing")
+    empty = tmp_path / "empty"
+    empty.mkdir()
+    with pytest.raises(ValueError, match="zero envelopes"):
+        b02.check_corpus(empty)
+
+
+def test_migrator_rejects_missing_empty_and_explicit_sidecar(tmp_path: Path) -> None:
+    with pytest.raises(FileNotFoundError, match="does not exist"):
+        migrate.migrate_corpus(tmp_path / "missing", write=False)
+    empty = tmp_path / "empty"
+    empty.mkdir()
+    with pytest.raises(ValueError, match="zero envelopes"):
+        migrate.migrate_corpus(empty, write=False)
+    sidecar = MINI_CORPUS / "001cd1f527f7f288.layout.json"
+    with pytest.raises(ValueError, match="sidecar cannot be migrated explicitly"):
+        migrate.migrate_corpus(sidecar, write=False)
+    with pytest.raises(ValueError, match="expected 2797 envelopes, found 3"):
+        migrate.migrate_corpus(MINI_CORPUS, write=False, expected_count=2797)
+
+
+def test_migrator_check_is_idempotent_on_mini_corpus(tmp_path: Path) -> None:
+    report_path = tmp_path / "delta.json"
+    report = migrate.migrate_corpus(
+        MINI_CORPUS,
+        write=False,
+        report_path=report_path,
+        expected_count=3,
+    )
+    assert report["summary"]["files_would_change"] == 0
+    assert report["summary"]["node_modes_after"] == 20
+    assert sum(report["summary"]["node_mode_values_after"].values()) == 20
+    assert report["summary"]["sidecars_untouched"] == 1
+    assert json.loads(report_path.read_text(encoding="utf-8")) == report
+
+
+def test_migrator_write_preserves_metadata_sidecar_and_is_idempotent(tmp_path: Path) -> None:
+    corpus = tmp_path / "corpus"
+    shutil.copytree(MINI_CORPUS, corpus)
+    envelope_path = corpus / "90a1d5ff9044902e.json"
+    raw = json.loads(envelope_path.read_text(encoding="utf-8"))
+    metadata_before = deepcopy(raw["metadata"])
+    node_metadata_before = {
+        node_id: deepcopy(entry["metadata"])
+        for node_id, entry in raw["nodes"].items()
+    }
+    raw.pop("groups")
+    for entry in raw["nodes"].values():
+        entry.pop("mode")
+    raw["compiled_api"] = from_envelope(raw).compile("api")
+    envelope_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
+    sidecar = corpus / "001cd1f527f7f288.layout.json"
+    sidecar_before = sidecar.read_bytes()
+
+    first = migrate.migrate_corpus(corpus, write=True, report_path=tmp_path / "write.json")
+    assert first["summary"]["files_would_change"] == 1
+    written = json.loads(envelope_path.read_text(encoding="utf-8"))
+    assert "compiled_api" not in written
+    assert written["groups"] == []
+    assert written["metadata"] == metadata_before
+    assert {
+        node_id: entry["metadata"] for node_id, entry in written["nodes"].items()
+    } == node_metadata_before
+    assert all(isinstance(entry["mode"], int) for entry in written["nodes"].values())
+    assert sidecar.read_bytes() == sidecar_before
+
+    second = migrate.migrate_corpus(corpus, write=False)
+    assert second["summary"]["files_would_change"] == 0
+
+
 # ---------------------------------------------------------------------------
 # Synthetic envelope — non-vacuous projection proof
 # ---------------------------------------------------------------------------
diff --git a/tests/test_ingest_external_workflows.py b/tests/test_ingest_external_workflows.py
index b72bb256..9da68cf2 100644
--- a/tests/test_ingest_external_workflows.py
+++ b/tests/test_ingest_external_workflows.py
@@ -14,8 +14,8 @@ from scripts import ingest_external_workflows as ingest
 from vibecomfy.workflow import FORMAT_VERSION, VibeWorkflow
 
 _CORPUS_90A1D5 = (
-    Path(__file__).resolve().parent.parent
-    / "external_workflows/corpus/90a1d5ff9044902e.json"
+    Path(__file__).resolve().parent
+    / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json"
 )
 
 
diff --git a/tests/test_porting_normalize_ingest.py b/tests/test_porting_normalize_ingest.py
index 2dccd435..f93e78cb 100644
--- a/tests/test_porting_normalize_ingest.py
+++ b/tests/test_porting_normalize_ingest.py
@@ -623,8 +623,8 @@ def test_comfy_converter_lenient_skew_falls_back_offline_without_converter_exec(
 # ═══════════════════════════════════════════════════════════════════════════════
 
 _CORPUS_90A1D5 = (
-    Path(__file__).resolve().parent.parent
-    / "external_workflows/corpus/90a1d5ff9044902e.json"
+    Path(__file__).resolve().parent
+    / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json"
 )
 
 
@@ -655,9 +655,9 @@ def _ui_projection(ui: dict) -> dict:
 
 
 def test_vibe_rich_ingest_preserves_90a1d5() -> None:
-    """The rich envelope decodes to the full 15-node IR, NOT the 2-node compiled_api."""
+    """The rich envelope decodes fully and derives its two-node execution view fresh."""
     raw = _load_90a1d5()
-    assert len(raw["compiled_api"]) == 2, "precondition: compiled_api is stale/partial evidence"
+    assert "compiled_api" not in raw
 
     wf = convert_to_vibe_format(raw)
 
@@ -668,6 +668,7 @@ def test_vibe_rich_ingest_preserves_90a1d5() -> None:
     assert wf.source.id == raw["source"]["id"]
     assert wf.strict_types is False
     assert wf.metadata["external_workflow"] is True
+    assert len(wf.compile("api")) == 2
 
     uids = [node.uid for node in wf.nodes.values()]
     assert len(set(uids)) == 15, "uids must all be distinct"
@@ -704,13 +705,12 @@ def test_vibe_rich_ingest_preserves_90a1d5() -> None:
         assert (ui_node.get("properties") or {})["vibecomfy_uid"] == rich["uid"]
 
 
-def test_vibe_rich_ingest_treats_compiled_api_as_optional_evidence() -> None:
-    """Rich structure remains authoritative when execution evidence is absent or bad."""
+def test_vibe_rich_ingest_ignores_optional_compiled_api_evidence() -> None:
+    """Rich structure remains authoritative without stored execution evidence or with bad evidence."""
     raw = _load_90a1d5()
 
-    without_evidence = deepcopy(raw)
-    without_evidence.pop("compiled_api")
-    assert len(convert_to_vibe_format(without_evidence).nodes) == 15
+    assert "compiled_api" not in raw
+    assert len(convert_to_vibe_format(raw).nodes) == 15
 
     malformed_evidence = deepcopy(raw)
     malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}

 succeeded in 222ms:
   240	# Per-envelope check
   241	# ---------------------------------------------------------------------------
   242	
   243	
   244	def _emit(wf: Any, **kwargs: Any) -> dict[str, Any]:
   245	    """emit_ui_json wrapper: schema-less nodes warn per node; those expected
   246	    warnings are suppressed (exceptions are NOT swallowed)."""
   247	    with warnings.catch_warnings():
   248	        warnings.filterwarnings("ignore", message=_SCHEMA_LESS_WARNING)
   249	        return emit_ui_json(wf, **kwargs)
   250	
   251	
   252	def check_envelope(raw: dict[str, Any]) -> dict[str, Any]:
   253	    """Run the full preservation pipeline over one rich envelope.
   254	
   255	    Returns a per-file result dict with counts and a ``mismatches`` list of
   256	    ``(axis, node, expected, actual)`` rows.  A pipeline refusal/exception is
   257	    recorded as a mismatch row and the remaining axes are skipped — the file
   258	    cannot be preserved, which is itself the finding.
   259	    """
   260	    result: dict[str, Any] = {
   261	        "file": None,
   262	        "rich_nodes": len(raw.get("nodes", {})),
   263	        "rich_edges": len(raw.get("edges", [])),
   264	        "canonical_nodes": 0,
   265	        "canonical_links": 0,
   266	        "groups": 0,
   267	        "pin_opaque": 0,
   268	        "uidless": 0,
   269	        "mismatches": [],
   270	    }
   271	
   272	    def fail(axis: str, node: Any, expected: Any, actual: Any) -> dict[str, Any]:
   273	        _record(result, axis, node, expected, actual)
   274	        return result
   275	
   276	    ir1 = from_envelope(raw)
   277	    ir1.groups = deepcopy(raw.get("groups") or [])
   278	
   279	    # ── pin evidence: emit directly with recovery_report + the rich groups ──
   280	    recovery_report: list[dict[str, Any]] = []
   281	    try:
   282	        pin_envelope = _emit(ir1, recovery_report=recovery_report)
   283	    except RefusedEmit as exc:
   284	        node_id, reason = _refusal_detail(exc)
   285	        return fail("emit_refused", node_id, "emission must succeed", reason)
   286	    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
   287	        return fail("exception", None, "emission must succeed", f"{type(exc).__name__}: {exc}")
   288	
   289	    emitted_uids = {
   290	        node.get("properties", {}).get("vibecomfy_uid")
   291	        for node in pin_envelope.get("nodes", [])
   292	    }
   293	    for entry in recovery_report:
   294	        if entry.get("widget_shape_verdict") != "pin_opaque":
   295	            continue
   296	        result["pin_opaque"] += 1
   297	        entry_node_id = str(entry.get("node_id"))
   298	        decoded_uid = ir1.nodes[entry_node_id].uid if entry_node_id in ir1.nodes else None
   299	        if decoded_uid not in emitted_uids:
   300	            _record(
   301	                result,
   302	                "pin.uid_missing",
   303	                entry_node_id,
   304	                f"emitted node with properties.vibecomfy_uid == {decoded_uid!r}",
   305	                "no such emitted node",
   306	            )
   307	
   308	    # ── canonicalize + re-ingest + re-emit ──────────────────────────────────
   309	    try:
   310	        canonical = normalize_agent_edit_graph(raw)
   311	        api2 = normalize_to_api(canonical, use_comfy_converter=False)
   312	        ir2 = from_api(api2)
   313	        ir2.groups = deepcopy(canonical.get("groups") or [])
   314	        reemit = _emit(ir2)
   315	    except RefusedEmit as exc:
   316	        node_id, reason = _refusal_detail(exc)
   317	        return fail("emit_refused", node_id, "emission must succeed", reason)
   318	    except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
   319	        return fail("exception", None, "pipeline must succeed", f"{type(exc).__name__}: {exc}")
   320	
   321	    result["canonical_nodes"] = len(canonical.get("nodes", []))
   322	    result["canonical_links"] = len(canonical.get("links", []))
   323	    result["groups"] = len(canonical.get("groups") or [])
   324	
   325	    # ── rich → ir1: node projection exact ───────────────────────────────────
   326	    for node_id, entry in raw.get("nodes", {}).items():
   327	        expected = rich_node_projection(node_id, entry)
   328	        actual = ir_node_projection(ir1.nodes[node_id])
   329	        for axis in ("id", "class_type", "uid", "mode", "furniture"):
   330	            if expected[axis] != actual[axis]:
   331	                _record(result, f"rich->ir1.{axis}", node_id, expected[axis], actual[axis])
   332	        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
   333	            _record(result, "rich->ir1.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
   334	        if expected["raw_widgets"] is not None and expected["raw_widgets"] != actual["raw_widgets"]:
   335	            _record(result, "rich->ir1.raw_widgets", node_id, expected["raw_widgets"], actual["raw_widgets"])
   336	
   337	    # ── rich → canonical: node ids/classes/modes/uids/widgets exact ─────────
   338	    canonical_by_id = canonical_nodes_by_id(canonical)
   339	    # Numeric rich ids keep their numeric value in the canonical envelope;
   340	    # non-digit ids (typed-wrapper labels like "80:4") are remapped to fresh
   341	    # integers.  The stable uid is the cross-boundary identity: map every rich
   342	    # node to its canonical litegraph id through the emitted uid stamp.
   343	    uid_to_canonical_id = {
   344	        proj["uid"]: canonical_id
   345	        for canonical_id, proj in canonical_by_id.items()
   346	    }
   347	
   348	    def canonical_id_of(rich_id: str) -> Any:
   349	        rich_uid = (raw["nodes"][rich_id].get("uid")) if rich_id in raw["nodes"] else None
   350	        mapped = uid_to_canonical_id.get(rich_uid)
   351	        return mapped if mapped is not None else _canonical_id_of(rich_id)
   352	
   353	    canonical_ids = set(canonical_by_id)
   354	    expected_ids = {canonical_id_of(node_id) for node_id in raw.get("nodes", {})}
   355	    if canonical_ids != expected_ids:
   356	        _record(
   357	            result,
   358	            "rich->canonical.node_ids",
   359	            None,
   360	            sorted(expected_ids),
   361	            sorted(canonical_ids),
   362	        )
   363	    for node_id, entry in raw.get("nodes", {}).items():
   364	        expected = rich_node_projection(node_id, entry)
   365	        actual = canonical_by_id.get(canonical_id_of(node_id))
   366	        if actual is None:
   367	            _record(result, "rich->canonical.missing_node", node_id, expected["id"], None)
   368	            continue
   369	        for axis in ("class_type", "mode", "uid"):
   370	            if expected[axis] != actual[axis]:
   371	                _record(result, f"rich->canonical.{axis}", node_id, expected[axis], actual[axis])
   372	        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
   373	            _record(result, "rich->canonical.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
   374	
   375	    # ── rich → ir2: node projection exact (ids via the canonical remap) ─────
   376	    for node_id, entry in raw.get("nodes", {}).items():
   377	        expected = rich_node_projection(node_id, entry)
   378	        actual = ir_node_projection(ir2.nodes[str(canonical_id_of(node_id))])
   379	        for axis in ("class_type", "uid", "mode"):
   380	            if expected[axis] != actual[axis]:
   381	                _record(result, f"rich->ir2.{axis}", node_id, expected[axis], actual[axis])
   382	        if expected["widgets_values"] is not None and expected["widgets_values"] != actual["widgets_values"]:
   383	            _record(result, "rich->ir2.widgets_values", node_id, expected["widgets_values"], actual["widgets_values"])
   384	        # The id axis speaks the canonical id (deterministic renumbering of
   385	        # non-digit ids is the documented exclusion; digit ids keep their value).
   386	        if actual["id"] != str(canonical_id_of(node_id)):
   387	            _record(result, "rich->ir2.id", node_id, str(canonical_id_of(node_id)), actual["id"])
   388	
   389	    # ── edge tuples: rich == ir1 == ir2 == canonical (semantic) ─────────────
   390	    rich_edges = rich_edge_tuples(raw)
   391	    ir1_edges = {edge_tuple(edge) for edge in ir1.edges}
   392	    ir2_edges = {edge_tuple(edge) for edge in ir2.edges}
   393	    # ir1 keeps rich ids; ir2 and the canonical envelope speak canonical ids.
   394	    rich_edges_canonical = {
   395	        (str(canonical_id_of(from_node)), from_output, str(canonical_id_of(to_node)), to_input)
   396	        for from_node, from_output, to_node, to_input in rich_edges
   397	    }
   398	    if rich_edges != ir1_edges:
   399	        _record(
   400	            result,
   401	            "rich->ir1.edges",
   402	            None,
   403	            sorted(rich_edges),
   404	            sorted(ir1_edges),
   405	        )
   406	    if rich_edges_canonical != ir2_edges:
   407	        _record(
   408	            result,
   409	            "rich->ir2.edges",
   410	            None,
   411	            sorted(rich_edges_canonical),
   412	            sorted(ir2_edges),
   413	        )
   414	    canonical_edges = canonical_semantic_edges(canonical)
   415	    if rich_edges_canonical != canonical_edges:
   416	        _record(
   417	            result,
   418	            "rich->canonical.edges",
   419	            None,
   420	            sorted(rich_edges_canonical),
   421	            sorted(canonical_edges),
   422	        )
   423	
   424	    # ── groups: rich (None ≡ []) == canonical == reemit ─────────────────────
   425	    rich_groups = raw.get("groups") or []
   426	    canonical_groups = canonical.get("groups") or []
   427	    reemit_groups = reemit.get("groups") or []
   428	    if rich_groups != canonical_groups or canonical_groups != reemit_groups:
   429	        _record(
   430	            result,
   431	            "groups",
   432	            None,
   433	            {"rich": rich_groups, "canonical": canonical_groups},
   434	            {"reemit": reemit_groups},
   435	        )
   436	
   437	    # ── canonical emission idempotence ──────────────────────────────────────
   438	    reemit_by_id = canonical_nodes_by_id(reemit)
   439	    if set(reemit_by_id) != set(canonical_by_id):
   440	        _record(
   441	            result,
   442	            "canonical.idempotence.node_ids",
   443	            None,
   444	            sorted(canonical_by_id),
   445	            sorted(reemit_by_id),
   446	        )
   447	    for node_id, expected in canonical_by_id.items():
   448	        actual = reemit_by_id.get(node_id)
   449	        if actual is None:
   450	            continue
   451	        for axis in ("class_type", "mode", "uid", "widgets_values"):
   452	            if expected[axis] != actual[axis]:
   453	                _record(result, f"canonical.idempotence.{axis}", node_id, expected[axis], actual[axis])
   454	    if canonical_link_topology(canonical) != canonical_link_topology(reemit):
   455	        _record(
   456	            result,
   457	            "canonical.idempotence.links",
   458	            None,
   459	            sorted(canonical_link_topology(canonical)),
   460	            sorted(canonical_link_topology(reemit)),
   461	        )
   462	
   463	    # ── uid-less emissions across every emitted envelope (global must be 0) ─
   464	    for envelope in (canonical, reemit, pin_envelope):
   465	        for node in envelope.get("nodes", []):
   466	            properties = node.get("properties") or {}
   467	            uid = properties.get("vibecomfy_uid")
   468	            if not isinstance(uid, str) or not uid.strip():
   469	                result["uidless"] += 1
   470	                _record(
   471	                    result,
   472	                    "uidless_emission",
   473	                    node.get("id"),
   474	                    "nonblank properties.vibecomfy_uid",
   475	                    uid,
   476	                )
   477	
   478	    return result
   479	
   480	
   481	def _refusal_detail(exc: RefusedEmit) -> tuple[Any, str]:
   482	    """Extract (node_id, reason) from a RefusedEmit diff."""
   483	    for node_id, diff in (exc.diff or {}).items():
   484	        return node_id, str(diff.get("reason") or exc)
   485	    return None, str(exc)
   486	
   487	
   488	# ---------------------------------------------------------------------------
   489	# Corpus aggregation
   490	# ---------------------------------------------------------------------------
   491	
   492	
   493	def _corpus_paths(corpus_dir: str | Path) -> tuple[Path, list[Path]]:
   494	    """Validate an explicit corpus directory and return its JSON paths."""
   495	    root = Path(corpus_dir)
   496	    if root.name.endswith(".layout.json"):
   497	        raise ValueError(f"layout sidecar cannot be used as a corpus directory: {root}")
   498	    if not root.exists():
   499	        raise FileNotFoundError(f"corpus directory does not exist: {root}")
   500	    if not root.is_dir():
   501	        raise NotADirectoryError(f"corpus path is not a directory: {root}")
   502	    paths = sorted(root.glob("*.json"))
   503	    envelope_paths = [path for path in paths if not path.name.endswith(".layout.json")]
   504	    if not envelope_paths:
   505	        raise ValueError(f"corpus directory contains zero envelopes: {root}")
   506	    return root, paths
   507	
   508	
   509	def iter_corpus(corpus_dir: str | Path):
   510	    """Yield ``(path, raw)`` for every serialized-Vibe envelope in the corpus.
   511	
   512	    Non-envelope ``*.json`` files (e.g. ``.layout.json`` sidecar stores) are
   513	    skipped and reported in the aggregate ``skipped_non_envelopes`` counter.
   514	    """
   515	    _, paths = _corpus_paths(corpus_dir)
   516	    found = 0
   517	    for path in paths:
   518	        if path.name.endswith(".layout.json"):
   519	            continue
   520	        raw = json.loads(path.read_text(encoding="utf-8"))

 succeeded in 120ms:
tests/test_b02_rich_preservation.py:83:        assert "compiled_api" not in raw
tests/test_b02_rich_preservation.py:111:    with pytest.raises(ValueError, match="zero envelopes"):
tests/test_b02_rich_preservation.py:117:        migrate.migrate_corpus(tmp_path / "missing", write=False)
tests/test_b02_rich_preservation.py:120:    with pytest.raises(ValueError, match="zero envelopes"):
tests/test_b02_rich_preservation.py:121:        migrate.migrate_corpus(empty, write=False)
tests/test_b02_rich_preservation.py:124:        migrate.migrate_corpus(sidecar, write=False)
tests/test_b02_rich_preservation.py:126:        migrate.migrate_corpus(MINI_CORPUS, write=False, expected_count=2797)
tests/test_b02_rich_preservation.py:131:    report = migrate.migrate_corpus(
tests/test_b02_rich_preservation.py:157:    raw["compiled_api"] = from_envelope(raw).compile("api")
tests/test_b02_rich_preservation.py:162:    first = migrate.migrate_corpus(corpus, write=True, report_path=tmp_path / "write.json")
tests/test_b02_rich_preservation.py:165:    assert "compiled_api" not in written
tests/test_b02_rich_preservation.py:174:    second = migrate.migrate_corpus(corpus, write=False)
tests/test_ingest_external_workflows.py:4:stored data. New envelopes therefore omit the compiled_api sidecar while
tests/test_ingest_external_workflows.py:26:def test_vibe_workflow_to_dict_omits_compiled_api() -> None:
tests/test_ingest_external_workflows.py:36:    assert "compiled_api" not in envelope
tests/test_ingest_external_workflows.py:37:    assert "compiled_api" not in envelope.get("metadata", {})
tests/test_ingest_external_workflows.py:76:    assert "compiled_api" not in envelope
tests/test_porting_normalize_ingest.py:122:            "compiled_api": {
tests/test_porting_normalize_ingest.py:168:            "compiled_api": {
tests/test_porting_normalize_ingest.py:660:    assert "compiled_api" not in raw
tests/test_porting_normalize_ingest.py:708:def test_vibe_rich_ingest_ignores_optional_compiled_api_evidence() -> None:
tests/test_porting_normalize_ingest.py:712:    assert "compiled_api" not in raw
tests/test_porting_normalize_ingest.py:716:    malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}
tests/test_porting_normalize_ingest.py:864:    assert "compiled_api" not in envelope
tests/test_porting_normalize_ingest.py:883:def test_from_envelope_hand_built_old_style_without_compiled_api() -> None:
tests/test_porting_normalize_ingest.py:884:    """A hand-built (old-style) envelope without compiled_api still decodes losslessly."""
tests/test_porting_normalize_ingest.py:931:    assert "compiled_api" not in envelope
tests/test_porting_normalize_ingest.py:944:    assert "compiled_api" not in written

exec
/bin/zsh -lc "sed -n '1,220p' .oracle/checkins/batch-1.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "sed -n '1,220p' .oracle/checkins/batch-1-rev2.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
Reading additional input from stdin...
2026-08-13T12:18:00.946735Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:18:00.946892Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:18:00.946921Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb0e-ceca-79d3-9131-287fb25b469e
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 1 — review Batch A (Canonical corpus migration, [XHARD]).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 4a16fc64 (frozen tasklist). Batch A commits: b016576b + rework 2b60f74a (Makefile b02-corpus-full expected-count 2797 → 2825, the sole issue from your prior review). Review `git diff 4a16fc64..2b60f74a`.

## Batch A tasks + acceptance gate (from frozen tasklist.md)
Tasks: (1) scripts/migrate_external_workflow_corpus.py — explicit --corpus-dir, fail-closed absent/empty, *.json except *.layout.json, decode ONLY from_envelope/serialize ONLY to_envelope + sort_keys=True, stage-then-replace, only 3 permitted transformations (add groups:[], remove compiled_api, add integer node.mode), preserve metadata/_ui exactly incl. legacy mode copies, machine-readable per-file delta report, --check/--write modes. (2) migrate main-checkout corpus (2,797 envelopes; sidecars/manifest/shadow untouched; 135,385 explicit modes; 754 mode-less → 0). (3) harden check_b02_rich_preservation.py — explicit corpus dir, fail on missing/empty, first-class mode first w/ legacy fallback, from_envelope for corpus + from_api for normalized API dicts, groups on wf.groups not groups=, report checked/skipped counts. (4) re-anchor tests (remove compiled_api assumptions, keep legacy metadata assertions, add missing/empty + sidecar-rejection tests, prove fresh compile('api')). (5) CI non-vacuity — small tracked fixture dir + make check/ci wired with explicit dir + expected nonzero count; separate full-corpus target requiring explicit CORPUS_DIR + expected 2797 (no fallback).

Acceptance gate: 2,797 migrated + 2 sidecars untouched; filenames + canonical hashes unchanged; idempotent (2nd run zero changes); delta contains ONLY the 3 permitted transformations; metadata/_ui unchanged; no compiled_api; every node has integer mode; B02 zero mismatches + zero uidless; missing/empty corpus fails; focused tests + git diff --check pass.

## Evidence (verified by host)
- Migration check: files_would_change=2797; after --write: second check files_would_change=0 (idempotent).
- Delta report /tmp/batchA-delta.json: canonical_hashes_unchanged=2825, compiled_api_removed=2797, groups_added=2797, filenames_unchanged=true, metadata_unchanged=2825, ui_unchanged=2825, node_modes_added=135385, node_modes_defaulted_to_zero=754, node_modes_after {0:121005, 2:3066, 4:12043}, permitted_transformations_only=true, sidecars_untouched=2, count_matches=true.
- NOTE: corpus dir holds 2825 envelope files (not 2797 — the manifest references 2797; 28 extra envelopes are pre-existing). Migration changed exactly 2797; 28 were already first-class. This is why the full-corpus check uses --expected-count 2825.
- Hardened checker: --expected-count 2825 → ok:true, checked=2825, mismatch_count=0, uidless=0, skipped=2 (sidecars).
- Focused tests: 51 passed (test_b02_rich_preservation, test_ingest_external_workflows, test_porting_normalize_ingest).
- git diff --check clean. Corpus lives in MAIN checkout (/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus), gitignored — not part of the worktree diff (per plan, review the external report + hashes instead).

## Your verdict
Verify the diff + evidence. Verdict is binary: `PASS` or a list of concrete issues (file:line). If PASS, confirm the plan's Batch A acceptance gate is met. Do NOT edit anything.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit Megado oracle checkpoint. I’ll inspect its review protocol first, then independently verify the frozen task requirements against the exact commit range and supplied corpus evidence. I will make no edits.
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

codex
The Megado checkpoint protocol requires a delegated Flash verification/critique pass. I’m therefore also using `subagent-launcher` to dispatch a read-only, mechanical review of the commit range; I’ll independently validate its findings before issuing the binary verdict.
exec
/bin/zsh -lc "sed -n '1,280p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

exec
/bin/zsh -lc "sed -n '1,220p' .oracle/checkins/batch-1-rev.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git log --oneline --decorate 4a16fc64..2b60f74a' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git show --stat --oneline 2b60f74a && git show --format=fuller --no-ext-diff 2b60f74a -- Makefile' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 86ms:
Reading additional input from stdin...
2026-08-13T12:08:47.455099Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:08:47.455147Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:08:47.455157Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb06-585f-70a1-a822-e5317df74004
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 1 — review Batch A (Canonical corpus migration, [XHARD]).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 4a16fc64 (frozen tasklist). Batch A commit: b016576b. Review `git diff 4a16fc64..b016576b`.

## Batch A tasks + acceptance gate (from frozen tasklist.md)
Tasks: (1) scripts/migrate_external_workflow_corpus.py — explicit --corpus-dir, fail-closed absent/empty, *.json except *.layout.json, decode ONLY from_envelope/serialize ONLY to_envelope + sort_keys=True, stage-then-replace, only 3 permitted transformations (add groups:[], remove compiled_api, add integer node.mode), preserve metadata/_ui exactly incl. legacy mode copies, machine-readable per-file delta report, --check/--write modes. (2) migrate main-checkout corpus (2,797 envelopes; sidecars/manifest/shadow untouched; 135,385 explicit modes; 754 mode-less → 0). (3) harden check_b02_rich_preservation.py — explicit corpus dir, fail on missing/empty, first-class mode first w/ legacy fallback, from_envelope for corpus + from_api for normalized API dicts, groups on wf.groups not groups=, report checked/skipped counts. (4) re-anchor tests (remove compiled_api assumptions, keep legacy metadata assertions, add missing/empty + sidecar-rejection tests, prove fresh compile('api')). (5) CI non-vacuity — small tracked fixture dir + make check/ci wired with explicit dir + expected nonzero count; separate full-corpus target requiring explicit CORPUS_DIR + expected 2797 (no fallback).

Acceptance gate: 2,797 migrated + 2 sidecars untouched; filenames + canonical hashes unchanged; idempotent (2nd run zero changes); delta contains ONLY the 3 permitted transformations; metadata/_ui unchanged; no compiled_api; every node has integer mode; B02 zero mismatches + zero uidless; missing/empty corpus fails; focused tests + git diff --check pass.

## Evidence (verified by host)
- Migration check: files_would_change=2797; after --write: second check files_would_change=0 (idempotent).
- Delta report /tmp/batchA-delta.json: canonical_hashes_unchanged=2825, compiled_api_removed=2797, groups_added=2797, filenames_unchanged=true, metadata_unchanged=2825, ui_unchanged=2825, node_modes_added=135385, node_modes_defaulted_to_zero=754, node_modes_after {0:121005, 2:3066, 4:12043}, permitted_transformations_only=true, sidecars_untouched=2, count_matches=true.
- NOTE: corpus dir holds 2825 envelope files (not 2797 — the manifest references 2797; 28 extra envelopes are pre-existing). Migration changed exactly 2797; 28 were already first-class. This is why the full-corpus check uses --expected-count 2825.
- Hardened checker: --expected-count 2825 → ok:true, checked=2825, mismatch_count=0, uidless=0, skipped=2 (sidecars).
- Focused tests: 51 passed (test_b02_rich_preservation, test_ingest_external_workflows, test_porting_normalize_ingest).
- git diff --check clean. Corpus lives in MAIN checkout (/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus), gitignored — not part of the worktree diff (per plan, review the external report + hashes instead).

## Your verdict
Verify the diff + evidence. Verdict is binary: `PASS` or a list of concrete issues (file:line). If PASS, confirm the plan's Batch A acceptance gate is met. Do NOT edit anything.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit Megado oracle checkpoint. I’ll inspect its oracle protocol, then review the exact frozen-SHA diff and validate the supplied acceptance evidence without modifying the repo.
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

codex
The skill’s normal Flash delegation path is unavailable in this read-only, network-restricted oracle sandbox, so I’m applying its permitted pure-review exception and validating directly. I’m starting with commit identity, changed-file scope, and the frozen Batch A specification before tracing each acceptance clause into code and tests.
exec
/bin/zsh -lc "git status --short --branch && git rev-parse 4a16fc64 b016576b && git show -s --format='%H%n%P%n%s' b016576b" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git diff --stat 4a16fc64..b016576b && git diff --name-status 4a16fc64..b016576b' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git show 4a16fc64:.oracle/tasklist.md | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## Batch A — Canonical corpus migration `[XHARD]`

 succeeded in 51ms:
Reading additional input from stdin...
2026-08-13T12:13:59.574161Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:13:59.575394Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:13:59.575417Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb0b-21b8-78e1-b2ce-40194c066097
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 1 — review Batch A (Canonical corpus migration, [XHARD]).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 4a16fc64 (frozen tasklist). Batch A commit: b016576b. Review `git diff 4a16fc64..b016576b`.

## Batch A tasks + acceptance gate (from frozen tasklist.md)
Tasks: (1) scripts/migrate_external_workflow_corpus.py — explicit --corpus-dir, fail-closed absent/empty, *.json except *.layout.json, decode ONLY from_envelope/serialize ONLY to_envelope + sort_keys=True, stage-then-replace, only 3 permitted transformations (add groups:[], remove compiled_api, add integer node.mode), preserve metadata/_ui exactly incl. legacy mode copies, machine-readable per-file delta report, --check/--write modes. (2) migrate main-checkout corpus (2,797 envelopes; sidecars/manifest/shadow untouched; 135,385 explicit modes; 754 mode-less → 0). (3) harden check_b02_rich_preservation.py — explicit corpus dir, fail on missing/empty, first-class mode first w/ legacy fallback, from_envelope for corpus + from_api for normalized API dicts, groups on wf.groups not groups=, report checked/skipped counts. (4) re-anchor tests (remove compiled_api assumptions, keep legacy metadata assertions, add missing/empty + sidecar-rejection tests, prove fresh compile('api')). (5) CI non-vacuity — small tracked fixture dir + make check/ci wired with explicit dir + expected nonzero count; separate full-corpus target requiring explicit CORPUS_DIR + expected 2797 (no fallback).

Acceptance gate: 2,797 migrated + 2 sidecars untouched; filenames + canonical hashes unchanged; idempotent (2nd run zero changes); delta contains ONLY the 3 permitted transformations; metadata/_ui unchanged; no compiled_api; every node has integer mode; B02 zero mismatches + zero uidless; missing/empty corpus fails; focused tests + git diff --check pass.

## Evidence (verified by host)
- Migration check: files_would_change=2797; after --write: second check files_would_change=0 (idempotent).
- Delta report /tmp/batchA-delta.json: canonical_hashes_unchanged=2825, compiled_api_removed=2797, groups_added=2797, filenames_unchanged=true, metadata_unchanged=2825, ui_unchanged=2825, node_modes_added=135385, node_modes_defaulted_to_zero=754, node_modes_after {0:121005, 2:3066, 4:12043}, permitted_transformations_only=true, sidecars_untouched=2, count_matches=true.
- NOTE: corpus dir holds 2825 envelope files (not 2797 — the manifest references 2797; 28 extra envelopes are pre-existing). Migration changed exactly 2797; 28 were already first-class. This is why the full-corpus check uses --expected-count 2825.
- Hardened checker: --expected-count 2825 → ok:true, checked=2825, mismatch_count=0, uidless=0, skipped=2 (sidecars).
- Focused tests: 51 passed (test_b02_rich_preservation, test_ingest_external_workflows, test_porting_normalize_ingest).
- git diff --check clean. Corpus lives in MAIN checkout (/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus), gitignored — not part of the worktree diff (per plan, review the external report + hashes instead).

## Your verdict
Verify the diff + evidence. Verdict is binary: `PASS` or a list of concrete issues (file:line). If PASS, confirm the plan's Batch A acceptance gate is met. Do NOT edit anything.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m reviewing the exact commit range read-only against each frozen acceptance condition. I’ll inspect the migration/checker behavior, tests and Make/CI wiring, then reconcile the host evidence with the 2,825-versus-2,797 corpus distinction.
codex
I’m using the `megado` skill because this is an explicit Megado oracle checkpoint; its gate/reviewer rules will determine the review procedure. Per the repo’s context policy, I’ll also delegate an independent diff audit and keep the final verdict grounded in independently checked evidence.
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

2026-08-13T12:14:20.805976Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:20.807605Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:20.807632Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:27.827436Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:27.827741Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:27.827763Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:32.152874Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:32.152950Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T12:14:32.152964Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---

 succeeded in 138ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2b60f74a (HEAD -> elegance-run2) megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)
b016576b megado run2 Batch A: canonical corpus migration (XHARD) — migrate script, hardened checker, re-anchored tests, CI fixture

 succeeded in 114ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2b60f74a megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)
 Makefile | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 2b60f74aa52a6cefb40dffd01475c0a6781154c8
Author:     POM <peter@omalley.io>
AuthorDate: Thu Aug 13 14:13:27 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Thu Aug 13 14:13:27 2026 +0200

    megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)

diff --git a/Makefile b/Makefile
index 5a178ea3..b49f2709 100644
--- a/Makefile
+++ b/Makefile
@@ -189,7 +189,7 @@ b02-corpus-full:
 		exit 2; \
 	fi
 	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
-		--corpus-dir "$(CORPUS_DIR)" --expected-count 2797
+		--corpus-dir "$(CORPUS_DIR)" --expected-count 2825
 
 browser-smoke:
 	$(NODE) --test tests/browser/*.mjs

exec
/bin/zsh -lc 'for f in .oracle/checkins/batch-1.md .oracle/checkins/batch-1-rev.md; do tail -n 80 "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json:4:  "workflow_path": "external_workflows/corpus/26584720cc4075d1.json",
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json:29:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json:4:  "workflow_path": "external_workflows/corpus/f855deb7cdef4ace.json",
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json:26:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:4:  "workflow_path": "external_workflows/corpus/0c27166fc31b7ead.json",
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:27:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json:4:  "workflow_path": "external_workflows/corpus/1d414c3424d15ae2.json",
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json:33:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:4:  "workflow_path": "external_workflows/corpus/374aa988d0a133be.json",
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:30:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:4:  "workflow_path": "external_workflows/corpus/9d28c679b594d9c4.json",
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:30:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:4:  "workflow_path": "external_workflows/corpus/485ff2fa6dcc1917.json",
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json:4:  "workflow_path": "external_workflows/corpus/b808486c05ad607c.json",
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json:33:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:4:  "workflow_path": "external_workflows/corpus/1999a9d36cb0a7f4.json",
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:29:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json:4:  "workflow_path": "external_workflows/corpus/a7ecc54027245cb7.json",
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json:35:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json:4:  "workflow_path": "external_workflows/corpus/e8c20a18bba6455d.json",
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json:34:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json:4:  "workflow_path": "external_workflows/corpus/5b54bf476f4234aa.json",
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:4:  "workflow_path": "external_workflows/corpus/99e2a967a579197f.json",
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:29:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:4:  "workflow_path": "external_workflows/corpus/b3ba8a025a649a3b.json",
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:29:    "source": "external_workflows/corpus",
tests/test_workflow_core.py:493:    envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
tests/test_workflow_core.py:1758:    envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json:4:  "workflow_path": "external_workflows/corpus/19d221f074b42462.json",
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json:4:  "workflow_path": "external_workflows/corpus/17dc9bc3ed806c24.json",
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json:27:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json:4:  "workflow_path": "external_workflows/corpus/9a3109dc72a4bd11.json",
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:4:  "workflow_path": "external_workflows/corpus/d1caece85b04698e.json",
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:30:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json:4:  "workflow_path": "external_workflows/corpus/cb5cd22138e4cd57.json",
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json:33:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:4:  "workflow_path": "external_workflows/corpus/d93baf73c8a43f57.json",
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:4:  "workflow_path": "external_workflows/corpus/d38dc8be1bfcda49.json",
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:27:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:4:  "workflow_path": "external_workflows/corpus/d7853cd7421f9ebc.json",
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:31:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json:4:  "workflow_path": "external_workflows/corpus/389d9080e42e36dd.json",
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json:29:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json:4:  "workflow_path": "external_workflows/corpus/1882aa21429372a8.json",
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json:27:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json:4:  "workflow_path": "external_workflows/corpus/d20410227419c47a.json",
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json:32:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json:4:  "workflow_path": "external_workflows/corpus/1cc45704dcffe34a.json",
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json:36:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json:4:  "workflow_path": "external_workflows/corpus/1c7ad8a2a8c0224b.json",
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json:27:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json:4:  "workflow_path": "external_workflows/corpus/435de2f6bb5d3eda.json",
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json:30:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json:4:  "workflow_path": "external_workflows/corpus/def5b5d3b3b372dd.json",
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json:33:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:4:  "workflow_path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:36:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:4:  "workflow_path": "external_workflows/corpus/7c8bb3b65e8084ae.json",
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:29:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json:4:  "workflow_path": "external_workflows/corpus/5b31ce48557b8ac2.json",
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json:30:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:4:  "workflow_path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:29:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json:4:  "workflow_path": "external_workflows/corpus/89b02a141d7451bb.json",
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json:30:    "source": "external_workflows/corpus",
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json:4:  "workflow_path": "external_workflows/corpus/d813fedaabea87b7.json",
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json:35:    "source": "external_workflows/corpus",
tests/fixtures/b02_corpus_mini/001cd1f527f7f288.layout.json:402:      "prior_path": "external_workflows/corpus/001cd1f527f7f288.json",

codex
- [Makefile:192](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:192): `b02-corpus-full` expects 2,797 envelopes, but the actual full corpus contains 2,825. The target therefore fails against the migrated corpus despite the verified 2,825-file B02 result. It must use `--expected-count 2825`.
tokens used
91,750
- [Makefile:192](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:192): `b02-corpus-full` expects 2,797 envelopes, but the actual full corpus contains 2,825. The target therefore fails against the migrated corpus despite the verified 2,825-file B02 result. It must use `--expected-count 2825`.
2b60f74a megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2b60f74a megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)
 Makefile | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 2b60f74aa52a6cefb40dffd01475c0a6781154c8
Author:     POM <peter@omalley.io>
AuthorDate: Thu Aug 13 14:13:27 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Thu Aug 13 14:13:27 2026 +0200

    megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)

diff --git a/Makefile b/Makefile
index 5a178ea3..b49f2709 100644
--- a/Makefile
+++ b/Makefile
@@ -189,7 +189,7 @@ b02-corpus-full:
 		exit 2; \
 	fi
 	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
-		--corpus-dir "$(CORPUS_DIR)" --expected-count 2797
+		--corpus-dir "$(CORPUS_DIR)" --expected-count 2825
 
 browser-smoke:
 	$(NODE) --test tests/browser/*.mjs

exec
/bin/zsh -lc "if [ -f /tmp/batchA-delta.json ]; then jq '{schema_version,mode,ok,corpus_dir,summary,file_count:(.files|length),sidecar_count:(.sidecars|length)}' /tmp/batchA-delta.json; else echo 'missing /tmp/batchA-delta.json'; fi" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 251ms:
{
  "schema_version": 1,
  "mode": "write",
  "ok": true,
  "corpus_dir": "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus",
  "summary": {
    "canonical_hashes_unchanged": 2825,
    "compiled_api_removed": 2797,
    "count_matches": true,
    "envelopes": 2825,
    "expected_count": null,
    "filenames_unchanged": true,
    "files_would_change": 2797,
    "groups_added": 2797,
    "metadata_unchanged": 2825,
    "node_mode_values_after": {
      "0": 121005,
      "2": 3066,
      "4": 12043
    },
    "node_modes_added": 135385,
    "node_modes_after": 136114,
    "node_modes_before": 729,
    "node_modes_defaulted_to_zero": 754,
    "nodes": 136114,
    "permitted_transformations_only": true,
    "sidecars_untouched": 2,
    "ui_unchanged": 2825
  },
  "file_count": 2825,
  "sidecar_count": 2
}

exec
/bin/zsh -lc "jq '[.files[] | select(.permitted_transformations_only "'!= true or (.changed_keys|length)>0 or ([.added_keys[] | select(. != "/groups" and (test("''^/nodes/[''^/]+/mode$")|not))]|length)>0 or ([.removed_keys[] | select(. != "/compiled_api")]|length)>0)] | length'"' /tmp/batchA-delta.json && jq '[.sidecars[] | select(.untouched "'!= true or .sha256_before != .sha256_after)] | length'"' /tmp/batchA-delta.json && jq '[.files[] | select(.metadata_unchanged "'!= true or .ui_unchanged != true or .canonical_hash_before != .canonical_hash_after)] | length'"' /tmp/batchA-delta.json" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 4727ms:
0
0
0

codex
- [Makefile:192](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:192) — `b02-corpus-full` expects 2,797, but the checker processes all 2,825 valid envelopes. It therefore fails with `count_matches:false`, contradicting the supplied evidence and preventing Batch A’s acceptance gate from passing at `b016576b`.

The later commit `2b60f74a` corrects this to 2,825, but it is outside the requested diff range.
tokens used
134,259
- [Makefile:192](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:192) — `b02-corpus-full` expects 2,797, but the checker processes all 2,825 valid envelopes. It therefore fails with `count_matches:false`, contradicting the supplied evidence and preventing Batch A’s acceptance gate from passing at `b016576b`.

The later commit `2b60f74a` corrects this to 2,825, but it is outside the requested diff range.

exec
/bin/zsh -lc "sed -n '280,500p' vibecomfy/workflow.py | nl -ba -v280" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
   280	
   281	    def finalize_metadata(self) -> "VibeWorkflow":
   282	        from vibecomfy.metadata import OUTPUT_NODE_NAMES, _infer_requirements, _register_common_inputs
   283	
   284	        manual_inputs = {
   285	            name: replace(vibe_input)
   286	            for name, vibe_input in self.inputs.items()
   287	            if name in self._manual_input_names and self._input_target_exists(vibe_input)
   288	        }
   289	        self._manual_input_names.intersection_update(manual_inputs)
   290	        self.inputs.clear()
   291	        self.outputs.clear()
   292	        for node_id, node in self.nodes.items():
   293	            _register_common_inputs(self, node_id, node)
   294	            if node.class_type in OUTPUT_NODE_NAMES:
   295	                self.outputs.append(VibeOutput(node_id=node_id, output_type=node.class_type))
   296	        self.inputs.update(manual_inputs)
   297	        self.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
   298	        self.requirements = _infer_requirements(self)
   299	        return self
   300	
   301	    def finalize(
   302	        self,
   303	        public_inputs: dict[str, Any],
   304	        *,
   305	        metadata: dict[str, Any] | None = None,
   306	        output_node: Any = None,
   307	        output_kind: str | None = None,
   308	        **bind_kwargs: Any,
   309	    ) -> "VibeWorkflow":
   310	        """Finalize ready-template public inputs and output binding.
   311	
   312	        ``metadata`` is optional for the v2.5 method form; when omitted, the
   313	        workflow's current metadata is used. The legacy free function remains
   314	        available in ``vibecomfy.templates.finalize``.
   315	        """
   316	        from vibecomfy.templates import _finalize_impl
   317	
   318	        return _finalize_impl(
   319	            self,
   320	            public_inputs,
   321	            dict(self.metadata if metadata is None else metadata),
   322	            output_node=output_node,
   323	            output_kind=output_kind,
   324	            **bind_kwargs,
   325	        )
   326	
   327	    def register_input(
   328	        self,
   329	        name: str,
   330	        node_id: str,
   331	        field: str,
   332	        value: Any = None,
   333	        *,
   334	        type: str | None = None,
   335	        default: Any = None,
   336	        required: bool = False,
   337	        range: Any = None,
   338	        aliases: list[str] | tuple[str, ...] | None = None,
   339	        media_semantics: str | None = None,
   340	        media: str | None = None,
   341	    ) -> "VibeWorkflow":
   342	        if media_semantics is not None and media is not None and media_semantics != media:
   343	            raise ValueError(
   344	                f"register_input({name!r}): media_semantics and legacy media "
   345	                "must match when both are provided"
   346	            )
   347	        resolved_media_semantics = media_semantics if media_semantics is not None else media
   348	        alias_tuple = _normalize_input_aliases(aliases)
   349	        self._validate_input_aliases(name, alias_tuple)
   350	        self._validate_input_target(name, node_id, field)
   351	        self.inputs[name] = VibeInput(
   352	            name=name,
   353	            node_id=str(node_id),
   354	            field=field,
   355	            value=value,
   356	            type=type,
   357	            default=value if default is None else default,
   358	            required=required,
   359	            range=range,
   360	            aliases=alias_tuple,
   361	            media_semantics=resolved_media_semantics,
   362	        )
   363	        self._manual_input_names.add(name)
   364	        return self
   365	
   366	    def set_input(self, name: str, value: Any) -> "VibeWorkflow":
   367	        target = self._resolve_input(name)
   368	        if target is None:
   369	            raise ValueError(self._unknown_input_message(name))
   370	
   371	        node = self.nodes.get(target.node_id)
   372	        if node is None:
   373	            raise ValueError(
   374	                f"set_input({name!r}) cannot update public input {target.name!r}: "
   375	                f"target node {target.node_id!r} is missing from workflow {self.id!r}. "
   376	                f"Registered target: {target.node_id}.{target.field}."
   377	            )
   378	        if target.field in node.inputs:
   379	            node.inputs[target.field] = value
   380	        elif target.field in node.widgets:
   381	            node.widgets[target.field] = value
   382	        else:
   383	            available = _format_available_names([*node.inputs.keys(), *node.widgets.keys()])
   384	            raise ValueError(
   385	                f"set_input({name!r}) cannot update public input {target.name!r}: "
   386	                f"target field {target.field!r} is missing from node {target.node_id!r} "
   387	                f"({node.class_type}) in workflow {self.id!r}. "
   388	                f"Available fields on node {target.node_id!r}: {available}."
   389	            )
   390	        target.value = value
   391	        return self
   392	
   393	    def _resolve_input(self, name: str) -> VibeInput | None:
   394	        if name in self.inputs:
   395	            return self.inputs[name]
   396	        matches = [item for item in self.inputs.values() if name in item.aliases]
   397	        if len(matches) > 1:
   398	            matched_names = _format_available_names(item.name for item in matches)
   399	            raise ValueError(
   400	                f"Input alias {name!r} is ambiguous in workflow {self.id!r}; "
   401	                f"it matches public inputs: {matched_names}."
   402	            )
   403	        return matches[0] if matches else None
   404	
   405	    def _unknown_input_message(self, name: str) -> str:
   406	        available_names = _format_available_names(self.inputs.keys())
   407	        aliases = {
   408	            alias: item.name
   409	            for item in self.inputs.values()
   410	            for alias in item.aliases
   411	        }
   412	        if aliases:
   413	            alias_text = ", ".join(
   414	                f"{alias!r} -> {primary!r}" for alias, primary in sorted(aliases.items())
   415	            )
   416	        else:
   417	            alias_text = "<none>"
   418	        return (
   419	            f"set_input({name!r}) has no registered public input or alias in "
   420	            f"workflow {self.id!r}. Available public inputs: {available_names}. "
   421	            f"Available aliases: {alias_text}. Register the input before calling set_input()."
   422	        )
   423	
   424	    def _validate_input_aliases(self, name: str, aliases: tuple[str, ...]) -> None:
   425	        if len(set(aliases)) != len(aliases):
   426	            raise ValueError(f"register_input({name!r}): duplicate aliases are not allowed")
   427	        if name in aliases:
   428	            raise ValueError(f"register_input({name!r}): alias cannot equal its primary input name")
   429	        existing_primary_names = {existing_name for existing_name in self.inputs if existing_name != name}
   430	        if name in {
   431	            alias
   432	            for existing_name, item in self.inputs.items()
   433	            if existing_name != name
   434	            for alias in item.aliases
   435	        }:
   436	            raise ValueError(f"register_input({name!r}): primary input name conflicts with an existing alias")
   437	        primary_conflicts = existing_primary_names.intersection(aliases)
   438	        if primary_conflicts:
   439	            conflict = sorted(primary_conflicts)[0]
   440	            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing primary input")
   441	        existing_aliases = {
   442	            alias
   443	            for existing_name, item in self.inputs.items()
   444	            if existing_name != name
   445	            for alias in item.aliases
   446	        }
   447	        alias_conflicts = existing_aliases.intersection(aliases)
   448	        if alias_conflicts:
   449	            conflict = sorted(alias_conflicts)[0]
   450	            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing alias")
   451	
   452	    def _validate_input_target(self, name: str, node_id: str, field: str) -> None:
   453	        node_key = str(node_id)
   454	        if node_key not in self.nodes:
   455	            raise ValueError(
   456	                f"register_input({name!r}): target node {node_key!r} does not exist "
   457	                f"in workflow {self.id!r}"
   458	            )
   459	        node = self.nodes[node_key]
   460	        if field not in node.inputs and field not in node.widgets:
   461	            raise ValueError(
   462	                f"register_input({name!r}): field {field!r} not found in "
   463	                f"node {node_key!r} ({node.class_type}) inputs or widgets"
   464	            )
   465	
   466	    def _input_target_exists(self, vibe_input: VibeInput) -> bool:
   467	        node = self.nodes.get(vibe_input.node_id)
   468	        return node is not None and (vibe_input.field in node.inputs or vibe_input.field in node.widgets)
   469	
   470	    def _mint_uid(self, seed: str | None = None) -> str:
   471	        """Mint a never-reused uid using the monotonic counter.
   472	
   473	        Counter always increments regardless of whether a seed is provided.
   474	        When seed is given it becomes the local uid component (extrinsic identity).
   475	        When omitted, the counter value provides authored creation-order identity.
   476	        """
   477	        from vibecomfy.identity.uid import make_uid
   478	        self._uid_counter += 1
   479	        local = seed if seed is not None else f"n{self._uid_counter}"
   480	        return make_uid("", local)
   481	
   482	    def add_node(
   483	        self,
   484	        class_type: str,
   485	        _id: str | None = None,
   486	        *,
   487	        uid: str | None = None,
   488	        _provenance: "Provenance | None" = None,
   489	        **inputs: Any,
   490	    ) -> VibeNode:
   491	        """Add a node to the workflow.
   492	
   493	        ``uid`` is keyword-only and sets node.uid verbatim when provided.
   494	        Extrinsic-seed minting via _mint_uid belongs in node()/raw_call callers,
   495	        not here, so add_node stays uid-neutral by default.
   496	
   497	        ``_provenance`` is a reserved keyword-only parameter declared BEFORE
   498	        ``**inputs`` so callers cannot accidentally bind it from an inputs
   499	        dict. When ``None`` it falls back to the ``requesting_provenance``
   500	        ContextVar (default ``"agent_authored"``); ingest enters

exec
/bin/zsh -lc "rg -n \"def from_envelope|def to_envelope|class VibeNode|mode\" vibecomfy/workflow.py vibecomfy/ingest -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/workflow.py:65:    models: list[str] = field(default_factory=list)
vibecomfy/workflow.py:67:    missing_models: list[str] = field(default_factory=list)
vibecomfy/workflow.py:82:class VibeNode:
vibecomfy/workflow.py:91:    mode: int = 0
vibecomfy/workflow.py:236:    def set_model(self, value: str) -> "VibeWorkflow":
vibecomfy/workflow.py:237:        return self.set_input("model", value)
vibecomfy/workflow.py:243:        including ``groups`` and per-node ``mode`` — plus the private
vibecomfy/workflow.py:253:    def to_envelope(self) -> dict[str, Any]:
vibecomfy/workflow.py:266:    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
vibecomfy/workflow.py:848:        # --- model_assets ---------------------------------------------------
vibecomfy/workflow.py:849:        model_assets: list[dict[str, Any]] = []
vibecomfy/workflow.py:851:            from vibecomfy.model_assets import (
vibecomfy/workflow.py:853:                _referenced_model_values,
vibecomfy/workflow.py:856:            from vibecomfy.registry.models_loader import load_registry
vibecomfy/workflow.py:859:            all_refs = _referenced_model_values(self)
vibecomfy/workflow.py:865:                    model_assets.append(asset)
vibecomfy/workflow.py:867:                    model_assets.append(_unresolved_asset_for_reference(ref))
vibecomfy/workflow.py:882:            "model_assets": model_assets,
vibecomfy/workflow.py:912:def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
vibecomfy/workflow.py:1152:_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
vibecomfy/workflow.py:1153:_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)
vibecomfy/workflow.py:1156:def _get_node_mode(node: VibeNode) -> int:
vibecomfy/workflow.py:1157:    """Read the litegraph mode (0/2/4); ``node.mode`` is the authority.
vibecomfy/workflow.py:1159:    Legacy fallback: hand-built nodes that predate the field signal mode via
vibecomfy/workflow.py:1160:    ``metadata["_ui"]["mode"]``; it is consulted only when the field is unset
vibecomfy/workflow.py:1164:    mode = node.mode
vibecomfy/workflow.py:1165:    if isinstance(mode, int) and mode:
vibecomfy/workflow.py:1166:        return mode
vibecomfy/workflow.py:1170:    legacy = ui.get("mode", 0)
vibecomfy/workflow.py:1177:    """Return (dropped_ids, bypassed_ids) for compile(api) mode filtering.
vibecomfy/workflow.py:1179:    dropped_ids: node ids with mode 2 (muted) or mode 4 (bypassed) — excluded from output.
vibecomfy/workflow.py:1180:    bypassed_ids: subset of dropped_ids with mode 4 — edges are rewired around them.
vibecomfy/workflow.py:1185:        mode = _get_node_mode(node)
vibecomfy/workflow.py:1186:        if mode in (_MODE_MUTED, _MODE_BYPASS):
vibecomfy/workflow.py:1188:        if mode == _MODE_BYPASS:
vibecomfy/workflow.py:1202:    - Edges sourcing from muted (mode=2) nodes are removed.
vibecomfy/workflow.py:1203:    - Edges sourcing from bypassed (mode=4) nodes are resolved to their bypass
vibecomfy/ingest/summarize.py:225:        models: list[str] = list(workflow.requirements.models)
vibecomfy/ingest/summarize.py:233:            "models": models[:10],
vibecomfy/ingest/summarize.py:257:        models = req.get("models", []) if isinstance(req, dict) else []
vibecomfy/ingest/summarize.py:265:            "models": models[:10],
vibecomfy/ingest/summarize.py:321:    """Extract the first JSON object from a model response."""
vibecomfy/ingest/normalize.py:81:    imports or calls the ComfyUI converter; in that mode
vibecomfy/ingest/normalize.py:119:            from comfy.component_model.workflow_convert import convert_ui_to_api
vibecomfy/ingest/normalize.py:353:                for _f in ("mode", "flags", "color", "bgcolor"):
vibecomfy/ingest/normalize.py:377:                for _f in ("mode", "flags", "color", "bgcolor"):
vibecomfy/ingest/normalize.py:418:def _node_mode_from_metadata(metadata: dict[str, Any]) -> int:
vibecomfy/ingest/normalize.py:419:    """First-class mode value for a node: ``_ui.mode`` then legacy
vibecomfy/ingest/normalize.py:420:    ``metadata["mode"]``, else 0.  Only ints are accepted."""
vibecomfy/ingest/normalize.py:423:        ui_mode = ui.get("mode", 0)
vibecomfy/ingest/normalize.py:424:        if isinstance(ui_mode, int):
vibecomfy/ingest/normalize.py:425:            return ui_mode
vibecomfy/ingest/normalize.py:426:    meta_mode = metadata.get("mode")
vibecomfy/ingest/normalize.py:427:    if isinstance(meta_mode, int):
vibecomfy/ingest/normalize.py:428:        return meta_mode
vibecomfy/ingest/normalize.py:487:        models=_vibe_string_list(
vibecomfy/ingest/normalize.py:488:            requirements_raw.get("models"), "requirements.models"
vibecomfy/ingest/normalize.py:493:        missing_models=_vibe_string_list(
vibecomfy/ingest/normalize.py:494:            requirements_raw.get("missing_models"), "requirements.missing_models"
vibecomfy/ingest/normalize.py:588:        # Mode is first-class: prefer the serialized node-level ``mode`` field
vibecomfy/ingest/normalize.py:590:        # ``_ui.mode`` / ``metadata["mode"]`` locations for old envelopes.
vibecomfy/ingest/normalize.py:592:        entry_mode = entry.get("mode")
vibecomfy/ingest/normalize.py:593:        node_mode = (
vibecomfy/ingest/normalize.py:594:            entry_mode if isinstance(entry_mode, int) else _node_mode_from_metadata(node_metadata)
vibecomfy/ingest/normalize.py:605:            mode=node_mode,
vibecomfy/ingest/normalize.py:732:def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
vibecomfy/ingest/normalize.py:942:        # mode is first-class on VibeNode (the compile mute/bypass signal): the
vibecomfy/ingest/normalize.py:943:        # field is populated below from `_ui.mode` (fallback metadata["mode"]) and
vibecomfy/ingest/normalize.py:944:        # `_ui.mode` is LEFT IN PLACE so emit_ui_json's furniture keeps re-emitting
vibecomfy/ingest/normalize.py:945:        # it.  No duplicate metadata["mode"] is written on new ingests.
vibecomfy/ingest/normalize.py:983:            mode=_node_mode_from_metadata(metadata),
vibecomfy/ingest/normalize.py:1084:# these so an arbitrary widget value is never mistaken for a control mode.

exec
/bin/zsh -lc "find tests/fixtures/b02_corpus_mini -maxdepth 1 -type f -print | sort && jq -r '[.vibecomfy_format_version, (.nodes|type), has(\"compiled_api\"), (.groups|type), ([.nodes[].mode|type]|unique|join(\",\"))] | @tsv' tests/fixtures/b02_corpus_mini/*.json" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
tests/fixtures/b02_corpus_mini/001cd1f527f7f288.layout.json
tests/fixtures/b02_corpus_mini/42188130f0d8021b.json
tests/fixtures/b02_corpus_mini/90a1d5ff9044902e.json
tests/fixtures/b02_corpus_mini/bbb556b30438a62c.json
jq: error (at tests/fixtures/b02_corpus_mini/001cd1f527f7f288.layout.json:431): Cannot iterate over null (null)
1.0	object	false	array	number
1.0	object	false	array	number
1.0	object	false	array	number

exec
/bin/zsh -lc "if [ -f /tmp/batchA-delta.json ]; then jq '{schema_version,mode,ok,corpus_dir,summary,file_count:(.files|length),sidecars}' /tmp/batchA-delta.json; else echo MISSING; fi" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "if [ -f /tmp/batchA-delta.json ]; then jq '{bad_per_file:([.files[] | select(.permitted_transformations_only "'!= true or (.changed_keys|length)>0 or ([.added_keys[] | select(. != "/groups" and (test("''^/nodes/[''^/]+/mode$")|not))]|length)>0 or ([.removed_keys[] | select(. != "/compiled_api")]|length)>0)]|length), bad_hash_meta_ui:([.files[] | select(.canonical_hash_before != .canonical_hash_after or .metadata_unchanged != true or .ui_unchanged != true)]|length), bad_sidecars:([.sidecars[] | select(.untouched != true or .sha256_before != .sha256_after)]|length)}'"' /tmp/batchA-delta.json; else echo MISSING; fi" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 337ms:
{
  "schema_version": 1,
  "mode": "write",
  "ok": true,
  "corpus_dir": "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus",
  "summary": {
    "canonical_hashes_unchanged": 2825,
    "compiled_api_removed": 2797,
    "count_matches": true,
    "envelopes": 2825,
    "expected_count": null,
    "filenames_unchanged": true,
    "files_would_change": 2797,
    "groups_added": 2797,
    "metadata_unchanged": 2825,
    "node_mode_values_after": {
      "0": 121005,
      "2": 3066,
      "4": 12043
    },
    "node_modes_added": 135385,
    "node_modes_after": 136114,
    "node_modes_before": 729,
    "node_modes_defaulted_to_zero": 754,
    "nodes": 136114,
    "permitted_transformations_only": true,
    "sidecars_untouched": 2,
    "ui_unchanged": 2825
  },
  "file_count": 2825,
  "sidecars": [
    {
      "file": "001cd1f527f7f288.layout.json",
      "sha256_after": "c16ad89efc9e77dea24be596d01c1b3d21625d0e904a493240a99e977f22353e",
      "sha256_before": "c16ad89efc9e77dea24be596d01c1b3d21625d0e904a493240a99e977f22353e",
      "untouched": true
    },
    {
      "file": "7952d606da990a99.layout.json",
      "sha256_after": "0d787ef95631d17f1316aed870c4806027c0b6ea06225c203fadba50004300c1",
      "sha256_before": "0d787ef95631d17f1316aed870c4806027c0b6ea06225c203fadba50004300c1",
      "untouched": true
    }
  ]
}

 succeeded in 1829ms:
{
  "bad_per_file": 0,
  "bad_hash_meta_ui": 0,
  "bad_sidecars": 0
}

exec
/bin/zsh -lc "sed -n '560,620p' vibecomfy/ingest/normalize.py | nl -ba -v560; sed -n '240,280p' vibecomfy/workflow.py | nl -ba -v240; sed -n '70,115p' vibecomfy/workflow.py | nl -ba -v70" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 11ms:
   240	        """Derived, complete deep copy.
   241	
   242	        The dataclass walk (``copy.deepcopy``) copies every public field —
   243	        including ``groups`` and per-node ``mode`` — plus the private
   244	        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``),
   245	        so adding a field to the dataclass needs no ``copy()`` edit.  The
   246	        clone is not bound to any workflow context.
   247	        """
   248	        cloned = copy.deepcopy(self)
   249	        if hasattr(cloned, "_workflow_context_token"):
   250	            del cloned._workflow_context_token
   251	        return cloned
   252	
   253	    def to_envelope(self) -> dict[str, Any]:
   254	        """Serialize this IR as the stored vibe envelope.
   255	
   256	        Public dataclass fields plus ``vibecomfy_format_version``. No
   257	        ``compiled_api`` — ``compile("api")`` is a function, not stored data.
   258	        Transport stamps such as ``workflow_id`` are applied by callers after
   259	        this, not here.
   260	        """
   261	        plain = _to_plain(self)
   262	        plain["vibecomfy_format_version"] = FORMAT_VERSION
   263	        return plain
   264	
   265	    @classmethod
   266	    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
   267	        """Fail-closed decoder for a serialized vibe envelope.
   268	
   269	        Rich ``nodes`` + ``edges`` are the only structural authority.
   270	        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
   271	        no partial graph is returned. Implementation is the existing ingest
   272	        decoder — this method does not relax it.
   273	        """
   274	        from vibecomfy.ingest.normalize import _decode_serialized_vibe
   275	
   276	        return _decode_serialized_vibe(raw)
   277	
   278	    def clone(self) -> "VibeWorkflow":
   279	        return self.copy()
   280	
    70	
    71	
    72	@dataclass(slots=True)
    73	class RawWidgetPayload:
    74	    values: Any
    75	    shape: str
    76	    source: str
    77	    has_dict_rows: bool
    78	    length: int
    79	
    80	
    81	@dataclass(slots=True)
    82	class VibeNode:
    83	    id: str
    84	    class_type: str
    85	    pack: str | None = None
    86	    inputs: dict[str, Any] = field(default_factory=dict)
    87	    widgets: dict[str, Any] = field(default_factory=dict)
    88	    metadata: dict[str, Any] = field(default_factory=dict)
    89	    uid: str = ""
    90	    raw_widgets: RawWidgetPayload | None = None
    91	    mode: int = 0
    92	
    93	    @property
    94	    def provenance(self) -> str:
    95	        """Read-through to the S4 provenance tag; fail-closed on missing/None."""
    96	        from vibecomfy.security import provenance as _prov
    97	
    98	        return _prov.read(self)
    99	
   100	
   101	@dataclass(slots=True)
   102	class VibeEdge:
   103	    from_node: str
   104	    from_output: str
   105	    to_node: str
   106	    to_input: str
   107	
   108	
   109	@dataclass(slots=True)
   110	class VibeInput:
   111	    name: str
   112	    node_id: str
   113	    field: str
   114	    value: Any = None
   115	    type: str | None = None

codex
The rework is correctly scoped to the sole prior finding: the full-corpus target now checks all 2,825 envelope files while the migration report still shows exactly 2,797 files transformed. The implementation audit has not surfaced a new acceptance failure; I’m now running the focused read-only checks and validating the external report’s per-file invariants.
exec
/bin/zsh -lc 'git diff --check 4a16fc64..2b60f74a' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'make b02-corpus-full' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" .venv/bin/python scripts/check_b02_rich_preservation.py --corpus-dir tests/fixtures/b02_corpus_mini --expected-count 3' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 127 in 0ms:
zsh:1: no such file or directory: .venv/bin/python

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/test_b02_rich_preservation.py tests/test_ingest_external_workflows.py tests/test_porting_normalize_ingest.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 127 in 0ms:
zsh:1: no such file or directory: .venv/bin/python

 succeeded in 66ms:
 exited 2 in 54ms:
CORPUS_DIR is required (no default full-corpus path).
make: *** [b02-corpus-full] Error 2

exec
/bin/zsh -lc 'make -n b02-corpus-full CORPUS_DIR=/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
make: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
make: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
make: error: couldn't create cache file '/tmp/xcrun_db-aB2kxOH5' (errno=Operation not permitted)
make: error: couldn't create cache file '/tmp/xcrun_db-XqJjrlwL' (errno=Operation not permitted)
if [ -z "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus" ]; then \
		echo "CORPUS_DIR is required (no default full-corpus path)."; \
		exit 2; \
	fi
PYTHONPATH="/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2" .venv/bin/python scripts/check_b02_rich_preservation.py \
		--corpus-dir "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus" --expected-count 2825

exec
/bin/zsh -lc "find /Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus -maxdepth 1 -type f -name '*.json' | awk 'BEGIN{env=0;side=0} /\\.layout\\.json"'$/{side++;next} {env++} END{print "envelopes=" env " sidecars=" side}'"'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 7ms:
envelopes=2825 sidecars=2

exec
/bin/zsh -lc "rg -n '"'^PYTHON|''^PYTEST|VIRTUAL|'"\\.venv' Makefile pyproject.toml uv.lock 2>/dev/null | head -80; command -v python3; python3 --version; command -v uv || true; ls -ld .venv ../vibecomfy/.venv 2>/dev/null || true" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 529ms:
Makefile:1:PYTHON ?= .venv/bin/python
Makefile:3:PYTEST ?= $(PYTHON) -m pytest
/Users/peteromalley/.pyenv/shims/python3
Python 3.11.11
/Users/peteromalley/.pyenv/shims/uv
drwxr-xr-x@ 10 peteromalley  staff  320 Jun 16 20:16 ../vibecomfy/.venv

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" ../vibecomfy/.venv/bin/python scripts/check_b02_rich_preservation.py --corpus-dir tests/fixtures/b02_corpus_mini --expected-count 3' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" ../vibecomfy/.venv/bin/python -m pytest -p no:cacheprovider -q tests/test_b02_rich_preservation.py tests/test_ingest_external_workflows.py tests/test_porting_normalize_ingest.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 2067ms:
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pytest/__main__.py", line 9, in <module>
    raise SystemExit(pytest.console_main())
                     ^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
           ^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1192, in pytest_cmdline_parse
    self.parse(args)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1562, in parse
    self.hook.pytest_load_initial_conftests(
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/_pytest/capture.py", line 493, in __init__
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
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2']

 succeeded in 28446ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/torch/library.py:361: UserWarning: Warning only once for all operators,  other operators may also be overridden.
  Overriding a previously registered kernel for the same operator and the same dispatch key
  operator: aten::mm(Tensor self, Tensor mat2) -> Tensor
    registered at /Users/runner/work/pytorch/pytorch/build/aten/src/ATen/RegisterSchema.cpp:6
  dispatch key: MPS
  previous kernel: registered at /Users/runner/work/pytorch/pytorch/aten/src/ATen/LegacyBatchingRegistrations.cpp:1076
       new kernel: registered at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/fp4_fp8_for_torch_mps/ops.py:7 (Triggered internally at /Users/runner/work/pytorch/pytorch/aten/src/ATen/core/dispatch/OperatorEntry.cpp:215.)
  self.m.impl(
Could not locate ComfyUI root (no server.py + nodes.py found).
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/comfy/model_management.py:237: UserWarning: torch.cuda.current_device() did not return a device, returning a CPU torch device
  warnings.warn("torch.cuda.current_device() did not return a device, returning a CPU torch device")
[32m[INFO][0m Set vram state to: NORMAL_VRAM
objc[53583]: Class AVFFrameReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x13dac43a8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x14eb683a8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
objc[53583]: Class AVFAudioReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x13dac43f8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x14eb683f8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
[32m[INFO][0m PromptServer imported; registering VibeComfy routes.
[32m[INFO][0m vibecomfy agent routes module loaded and all routes registered.
[32m[INFO][0m VibeComfy routes registered successfully.
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 1(VHS_LoadVideo); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 2(VHS_VideoCombine); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
[1m[33m[WARNING][0m compute_layers: 4 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 4, 5, 11, 16
[1m[33m[WARNING][0m compute_layers: 4 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 4, 5, 11, 16
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 3(TripoTextToModelNode); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 4(MarkdownNote); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 5(MarkdownNote); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 6(TripoRigNode); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 7(TripoRetargetNode); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 8(TripoConversionNode); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 9(TripoTextureNode); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 10(TripoRefineNode); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 11(MarkdownNote); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 16(MarkdownNote); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 17(Preview3D); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 22(Preview3D); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 23(Preview3D); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 24(Preview3D); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 25(Preview3D); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
[1m[33m[WARNING][0m compute_layers: 4 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 4, 5, 11, 16
[1m[33m[WARNING][0m compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 3
[1m[33m[WARNING][0m compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 3
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 1(DisplayAny); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 2(23237ab4-f1ba-4772-b8c1-dd4459fe6a20); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/comfy_nodes/agent/graph_normalization.py:57: UserWarning: emit_ui_json: schema-less node 3(Note); emitting best-effort slots. Pass strict=True to hard-fail.
  return emit_ui_json(
[1m[33m[WARNING][0m compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 3
{
  "canonical_links": 12,
  "canonical_nodes": 20,
  "checked": 3,
  "count_matches": true,
  "expected_count": 3,
  "groups": 0,
  "mismatch_count": 0,
  "mismatch_rows": [],
  "mismatches_by_axis": {},
  "ok": true,
  "pin_opaque": 20,
  "refused_files": [],
  "rich_edges": 12,
  "rich_nodes": 20,
  "skipped": 1,
  "skipped_non_envelopes": 0,
  "skipped_sidecars": 1,
  "uidless": 0,
  "workflows": 3
}

exec
/bin/zsh -lc "rg -n 'from_envelope|to_envelope|json\\.dumps|os\\.replace|compiled_api|groups|mode' scripts/migrate_external_workflow_corpus.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
3:Only three schema changes are permitted: add a missing top-level ``groups``
4:list, remove top-level ``compiled_api``, and add a missing integer first-class
5:``mode`` to each node. Every output is staged and validated before write mode
22:from vibecomfy.ingest import from_envelope
59:    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
65:    if prefer_stored and "compiled_api" in raw:
66:        api = raw["compiled_api"]
68:            raise ValueError("compiled_api must be a mapping when present")
69:        return _canonical_hash(api), "compiled_api"
70:    return _canonical_hash(from_envelope(raw).compile("api")), "compile(api)"
103:    workflow = from_envelope(raw)
112:    migrated = workflow.to_envelope()
121:    allowed_added = {"/groups"}
123:        _json_pointer(("nodes", str(node_id), "mode"))
125:        if "mode" not in entry
127:    allowed_removed = {"/compiled_api"} if "compiled_api" in raw else set()
136:    if "/groups" in added and migrated.get("groups") != []:
137:        raise ValueError(f"{filename}: missing groups must migrate to []")
138:    if "/compiled_api" in removed and "compiled_api" in migrated:
139:        raise ValueError(f"{filename}: compiled_api was not removed")
141:    modes_added = 0
142:    modes_defaulted = 0
143:    mode_values: dict[str, int] = {}
145:        mode = entry.get("mode")
146:        if not isinstance(mode, int) or isinstance(mode, bool):
147:            raise ValueError(f"{filename}: node {node_id!r} mode is not an integer: {mode!r}")
148:        if "mode" not in raw_nodes[node_id]:
149:            modes_added += 1
152:            ui_mode = old_ui.get("mode") if isinstance(old_ui, dict) else None
153:            metadata_mode = old_metadata.get("mode") if isinstance(old_metadata, dict) else None
154:            has_legacy_mode = (
155:                isinstance(ui_mode, int) and not isinstance(ui_mode, bool)
157:                isinstance(metadata_mode, int) and not isinstance(metadata_mode, bool)
159:            if not has_legacy_mode:
160:                modes_defaulted += 1
161:        mode_values[str(mode)] = mode_values.get(str(mode), 0) + 1
182:            "node_modes_added": modes_added,
183:            "node_modes_defaulted_to_zero": modes_defaulted,
184:            "node_mode_values_after": mode_values,
187:            "add_groups": int("/groups" in added),
188:            "remove_compiled_api": int("/compiled_api" in removed),
189:            "add_node_mode": modes_added,
240:    modes_before = 0
241:    modes_after = 0
242:    modes_added = 0
243:    modes_defaulted = 0
244:    mode_values_after: dict[str, int] = {}
255:                modes_before += sum("mode" in entry for entry in raw_nodes.values() if isinstance(entry, dict))
257:            modes_after += len(migrated["nodes"])
258:            modes_added += delta["counts"]["node_modes_added"]
259:            modes_defaulted += delta["counts"]["node_modes_defaulted_to_zero"]
260:            for mode, count in delta["counts"]["node_mode_values_after"].items():
261:                mode_values_after[mode] = mode_values_after.get(mode, 0) + count
264:                serialized = json.dumps(migrated, indent=2, sort_keys=True) + "\n"
269:            "mode": "write" if write else "check",
279:                "node_modes_before": modes_before,
280:                "node_modes_added": modes_added,
281:                "node_modes_defaulted_to_zero": modes_defaulted,
282:                "node_modes_after": modes_after,
283:                "node_mode_values_after": mode_values_after,
284:                "groups_added": sum(delta["transformations"]["add_groups"] for delta in deltas),
285:                "compiled_api_removed": sum(
286:                    delta["transformations"]["remove_compiled_api"] for delta in deltas
310:        report_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
328:                    os.replace(stage_dir / path.name, path)
333:                        os.replace(backup, path)
342:            os.replace(staged_report, resolved_report)
353:                    os.replace(backup, path)
365:    mode = parser.add_mutually_exclusive_group(required=True)
366:    mode.add_argument("--check", action="store_true", help="report changes without writing")
367:    mode.add_argument("--write", action="store_true", help="transactionally replace all envelopes")

exec
/bin/zsh -lc "rg -n 'emit_ui_json\\(|_emit\\(|groups=' scripts/check_b02_rich_preservation.py; rg -n 'from_envelope|from_api|convert_to_vibe_format' scripts/check_b02_rich_preservation.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
11:         pin evidence: emit_ui_json(ir1, recovery_report=report)
244:def _emit(wf: Any, **kwargs: Any) -> dict[str, Any]:
249:        return emit_ui_json(wf, **kwargs)
282:        pin_envelope = _emit(ir1, recovery_report=recovery_report)
314:        reemit = _emit(ir2)
8:    rich ──from_envelope──▶ ir1 ──normalize_agent_edit_graph──▶ canonical
9:         ──normalize_to_api(use_comfy_converter=False)──▶ api ──from_api──▶ ir2
55:from vibecomfy.ingest import from_api, from_envelope, normalize_to_api
276:    ir1 = from_envelope(raw)
312:        ir2 = from_api(api2)

exec
/bin/zsh -lc "git diff --check 4a16fc64..2b60f74a; git rev-parse HEAD; git merge-base --is-ancestor 4a16fc64 2b60f74a; git show -s --format='%H %P %s' 2b60f74a" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "if [ -f /tmp/batchA-delta.json ]; then jq '{duplicate_file_names: (([.files[].file]|length)-([.files[].file]|unique|length)), file_names_sorted: ([.files[].file] == ([.files[].file]|sort)), changed_files:([.files[]|select(.would_change)]|length), unchanged_files:([.files[]|select(.would_change|not)]|length)}' /tmp/batchA-delta.json; fi" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "find /Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus -maxdepth 1 -type f -name '*.json' -print | sed 's#"'^.*/##'"' | sort | shasum -a 256" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 76ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2b60f74aa52a6cefb40dffd01475c0a6781154c8
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2b60f74aa52a6cefb40dffd01475c0a6781154c8 b016576b730e9c58a7364da6d6dd836258366ac8 megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)

 succeeded in 46ms:
c4b6c41d3824d2afe7a94d205d5bace2c5b137b33f9a36dcfd42128263c3d109  -

 succeeded in 303ms:
{
  "duplicate_file_names": 0,
  "file_names_sorted": true,
  "changed_files": 2797,
  "unchanged_files": 28
}

exec
/bin/zsh -lc "find /tmp -maxdepth 1 -type f \\( -iname '*batch*a*' -o -iname '*b02*' \\) -print 2>/dev/null | sort" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 ../vibecomfy/.venv/bin/python -c $'"'import hashlib, json\\nfrom pathlib import Path\\nroot=Path(\"/Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows/corpus\")\\npaths=sorted(root.glob(\"*.json\"))\\nenvs=[p for p in paths if not p.name.endswith(\".layout.json\")]\\nside=[p for p in paths if p.name.endswith(\".layout.json\")]\\ncompiled=groups_missing=bad_modes=nodes=0\\nfor p in envs:\\n raw=json.loads(p.read_text(encoding=\"utf-8\"))\\n compiled += int(\"compiled_api\" in raw)\\n groups_missing += int(\"groups\" not in raw)\\n for entry in raw[\"nodes\"].values():\\n  nodes += 1\\n  mode=entry.get(\"mode\")\\n  bad_modes += int(not isinstance(mode,int) or isinstance(mode,bool))\\nreport=json.loads(Path(\"/tmp/batchA-delta.json\").read_text(encoding=\"utf-8\"))\\nreport_names={x[\"file\"] for x in report[\"files\"]}\\ncurrent_names={p.name for p in envs}\\nreport_side={x[\"file\"]:x for x in report[\"sidecars\"]}\\nside_hash_ok=all(hashlib.sha256(p.read_bytes()).hexdigest()==report_side[p.name][\"sha256_after\"] for p in side)\\nprint(json.dumps({\"envelopes\":len(envs),\"sidecars\":len(side),\"nodes\":nodes,\"compiled_api_present\":compiled,\"groups_missing\":groups_missing,\"bad_modes\":bad_modes,\"report_filename_set_matches\":report_names==current_names,\"sidecar_hashes_match_report\":side_hash_ok},sort_keys=True))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 7094ms:
{"bad_modes": 0, "compiled_api_present": 0, "envelopes": 2825, "groups_missing": 0, "nodes": 136114, "report_filename_set_matches": true, "sidecar_hashes_match_report": true, "sidecars": 2}

Exact diff, source audit, external report invariants, current corpus structural scan, and mini-corpus checker are complete. The focused pytest rerun is blocked only by the oracle sandbox having no writable temporary directory; host-provided 51-pass evidence remains valid.
  ✓ Inspect frozen Batch A criteria and exact commit diff
  ✓ Audit implementation and tests against each acceptance item
  → Run read-only verification and reconcile delegated review
  • Issue binary PASS or concrete file:line issues
codex
Independent verification now matches the supplied evidence: the current external corpus has 2,825 envelopes and two sidecars, all 136,114 nodes have non-boolean integer modes, no envelope retains `compiled_api`, every envelope has `groups`, the report filename set matches the corpus, and both sidecar hashes match. The tracked mini-corpus checker also passes with 3 checked, 1 skipped sidecar, zero mismatches, and zero UID-less emissions.
collab: Wait
The isolated reviewer also returned PASS, agreeing with the direct audit and evidence checks.
  ✓ Inspect frozen Batch A criteria and exact commit diff
  ✓ Audit implementation and tests against each acceptance item
  ✓ Run read-only verification and reconcile delegated review
  ✓ Issue binary PASS or concrete file:line issues
codex
PASS

Batch A acceptance gate is met at `2b60f74a`. The rework correctly resolves the sole prior issue: 2,797 envelopes were transformed, while the full-corpus target validates all 2,825 envelopes. Sidecars, filenames, canonical hashes, metadata, and `_ui` remain unchanged; migration is idempotent; modes and `groups` are canonical; B02 reports zero mismatches and zero UID-less emissions; and validation/CI coverage is non-vacuous.
tokens used
110,340
PASS

Batch A acceptance gate is met at `2b60f74a`. The rework correctly resolves the sole prior issue: 2,797 envelopes were transformed, while the full-corpus target validates all 2,825 envelopes. Sidecars, filenames, canonical hashes, metadata, and `_ui` remain unchanged; migration is idempotent; modes and `groups` are canonical; B02 reports zero mismatches and zero UID-less emissions; and validation/CI coverage is non-vacuous.
