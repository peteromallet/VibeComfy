Reading additional input from stdin...
2026-08-17T21:30:07.574018Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-17T21:30:07.575088Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-17T21:30:07.575093Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /private/tmp/vc-twostep
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 01a011a1-bc55-7863-ab78-af8a81d759bd
--------
user
You are GPT-5.6 Sol (high reasoning), planning a megado run for VibeComfy.

PROJECT: Implement a `two_step` pipeline mode for the VibeComfy agent executor: classify → execute, as a toggle alongside the existing full pipeline.

REPO/WORKTREE: /private/tmp/vc-twostep (branch two-step-megado, based on ir-everywhere @ c8407a8e). The codebase already has: `vibecomfy/executor/core.py` with `run_executor()` (line ~1699), `_run_classify()` (line ~703), `_ROUTE_BEHAVIORS`; `vibecomfy/porting/render.py` (render(wf, lens)); `vibecomfy/porting/edit/` with `session.py` (EditSession), `_interpret.py`, `grammar.py`, `editable_surface.py`, `ops.py`, `_parse_execute.py`; `vibecomfy/executor/` tool modules (hivemind_tools.py, lookup_tools.py, edit_suggestion_tools.py, layout_hints.py, web_tools.py, tool_specs.py, tool_contracts.py, evidence_pack.py, agent_research_stage.py, stage_contracts.py, contracts.py, profiles.py, prompts.py, graph_inspection.py, graph_facts.py).

THE DESIGN (authoritative; implement this exactly): /Users/peteromalley/Documents/vibecomfy-ir-everywhere/.oracle/two-step-mode-design.md — read it fully. Key points:
- `PipelineMode = Literal["full", "two_step"]`, optional `ExecutorRequest.pipeline_mode`, resolution order: request → env `VIBECOMFY_EXECUTOR_PIPELINE_MODE` → "full". Seam: `core.py::run_executor` after `_run_classify`, branch to new `executor/two_step.py::_run_two_step`.
- Two orchestrator stages: classify → execute. Inside execute, ONE bounded agent session with tool continuations (NOT a literal single provider response — that's explicitly the "attractive but bad" version).
- THREAD CONTINUITY is the defining behavior: follow-ups in the same chat window reuse the SAME execute session (accumulated Δs/observations/replies); only a new window starts fresh. Session keyed to chat-window/session id. Budgets are per-session cumulative with per-message slices.
- Execute system prompt: route/plan/query, current workflow render (lenses), RESEARCH (hivemind_search/get + registry + web last resort, evidence IDs, research_attempt derived), PRECEDENT TRANSLATION (immutable surface/topology lens), EDITING (Python batch surface only, one atomic batch, CAS preflight, one replacement allowed, zero-Δ on reject), REPLY (grounded in accepted Δ), SELF-CHECK + final contract (claim_refs: delta_ids ⊆ accepted Δ, lens_fact_ids ⊆ reply_lens, evidence_ids ⊆ tool ledger).
- Route surfaces/budgets table: clarify/respond (none tools, 2k, 30s), inspect (node_schema, 4k, 60s), research (hivemind+registry+schema+ready templates+web, 8k, 180s), requires_custom_nodes (registry+schema, 4k, 90s), revise (schema+templates+suggestions+layout+Python, 8k, 180s), adapt (all ten + Python, 12k, 240s), reorganise (layout+Python, 6k, 120s).
- `TwoStepRoutePolicy` keyed by canonical `_ROUTE_BEHAVIORS`, assert exact route coverage. Tools registered once; advertise least-privilege subset per route.
- Profiles: optional `execute` agent spec (profiles.py + profile_data/); typed profile error if a two-step profile lacks it; no implicit reuse of `implement`. Record resolved mode in Report + profiler; `execute` phase event, full-mode events byte-compatible.
- Research/one-shot application contract: no full IR to agent; fetched precedent = surface+topology render + evidence ID; one atomic batch; claim-ref validation.
- Validation: mode precedence, invalid values, classify_only, answer_only, missing execute specs, route coverage, tool denial, budget exhaustion, event/report compat, prompt goldens; thread-continuity tests (5 sub-cases); IR law suites on both modes; differential run (locked classifications) over simple edits + 57-case ledger; shadow rollout staged (respond/inspect → revise/reorganise → bounded research; adapt opt-in).

Also note the user's requirement: the prompt must clearly tell the agent the stages it goes through and the tools available for each (research → change → submit), and which tools are available.

DELIVERABLE: a complete megado plan with batches. Each batch: tasks (file-level, concrete), acceptance gate (verifiable commands/tests), [XHARD] tags on genuinely hard tasks (thread-continuity session identity, differential test harness, prompt design). Also: a list of additional areas to explore for full clarity, and open questions. Bias toward elegance — cut scope that isn't pulling its weight. The overall shape: B01 mode plumbing + toggle, B02 route policy + tool gating, B03 execute prompt + session/thread continuity, B04 reply/claim-ref contract + atomic batch, B05 profiles/report/events, B06 tests (unit + thread + differential), B07 scenario test run wiring (50 scenarios) + comparison harness. Adjust as you see fit.

Be concrete: exact files, exact functions, exact test files. Output the plan.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is specifically a batch plan for a megado run. I’ll first absorb its planning contract and the authoritative design, then ground every batch against the actual repository and test layout; I’ll delegate a bounded repository survey so the main thread stays lean.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && wc -l /Users/peteromalley/Documents/vibecomfy-ir-everywhere/.oracle/two-step-mode-design.md && sed -n '1,260p' /Users/peteromalley/Documents/vibecomfy-ir-everywhere/.oracle/two-step-mode-design.md" in /private/tmp/vc-twostep
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

> **Keep in sync with `microdo`.** These two skills share the delegation mandate, the roles table, invocation flags, and gotchas. If you edit this skill, apply the same change to `microdo/SKILL.md` — and vice versa. Keep the shared blocks identical.

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
     156 /Users/peteromalley/Documents/vibecomfy-ir-everywhere/.oracle/two-step-mode-design.md
# Two-step pipeline mode: classify → execute

## Decision

Add a parallel `two_step` orchestration path after classification. It reuses the same `VibeWorkflow`, renderer, tool registry, interpreter, canonical Δ, emit, and response envelope as the full pipeline. It does not replace or fork any graph authority. **Its defining behavior is thread continuity: every follow-up in the same chat window continues the SAME execute-agent session (accumulating Δs, observations, and replies); only a new chat window starts a fresh session.**

“One execute call” means one call to a bounded **agent session**. Tool use necessarily causes provider continuations: the model cannot search, observe results, apply an edit, observe accepted Δ, and then describe it in one raw inference response. If the requirement is literally two provider responses total, edit routes cannot safely produce model-written post-edit prose; they would need deterministic slot-filled narration. This design chooses the useful and honest boundary: two orchestrator stages, with a bounded tool loop inside execute.

## Toggle and orchestration seam

Introduce `PipelineMode = Literal["full", "two_step"]` and optional `ExecutorRequest.pipeline_mode`. Resolve it once as:

1. validated per-request `pipeline_mode`;
2. `VIBECOMFY_EXECUTOR_PIPELINE_MODE`;
3. `full`.

An invalid request value is a request error; an invalid environment value fails configuration loading. Do not infer mode from route, profile, `apply`, or `interaction_mode`, and do not silently fall back between modes. `classify_only` still exits immediately after classify. The existing `answer_only` rewrite still runs before dispatch and therefore forbids edits in either mode.

The exact seam is `core.py::run_executor`, after successful `_run_classify`, clarification-context persistence, `classify_only`, and the `answer_only` rewrite:

```python
mode = resolve_pipeline_mode(request)
if mode is PipelineMode.TWO_STEP:
    return _run_two_step(request, plan, retained_workflow, ...)
# existing research → implement → reply path remains unchanged
```

Put the new implementation in `executor/two_step.py`. A `TwoStepRoutePolicy` map, keyed by the existing canonical `_ROUTE_BEHAVIORS`, owns tool allow-lists and budgets; assert exact route coverage. Do not add mode conditionals to each full-pipeline phase.

Profiles gain an optional `execute` agent spec. The four full-pipeline specs remain required; built-in profiles define `execute`. A selected two-step profile without it fails with a typed profile error—there is no implicit reuse of `implement`, which could silently choose the wrong model. Record resolved mode in `Report` and profiler data; add an `execute` phase event while leaving full-mode events byte-compatible.

## Thread and session continuity (two-step semantics)

The defining behavior of two-step mode is that **the conversation is a single persistent thread** — every follow-up the user sends in the same chat window is dispatched to the SAME execute-agent session, not a fresh conversation. The agent accumulates the thread's context (its own prior tool observations, accepted Δs, lens facts, and replies) and builds on it turn over turn. It is the same identity, same session, same workflow authority — not a new agent per message.

- **Same-thread follow-ups reuse the session.** A user message in the same window continues the existing execute session: it re-runs the classifier for route/plan (routes may legitimately change mid-thread — e.g. "now also make it 512×512"), then dispatches to the same session with the accumulated context plus the new request. No new conversation, no context reset, no re-ingest of the workflow from scratch beyond the retained IR.
- **Only a NEW chat window starts a new session.** Opening a new window (or explicitly starting a new conversation) is the only trigger for a fresh session: fresh classify, fresh execute session, workflow re-attached from the current canvas state. The session id is the thread's identity; the harness must key it to the chat-window/session id, never mint a new one per turn.
- **Contrast with full-pipeline mode.** Full mode may treat each turn as an independent pipeline invocation (research → implement → reply per turn, handoffs rebuilt from artifacts). Two-step mode is explicitly stateful across turns within a thread: the agent's session history IS the thread memory. This is what makes low-latency iterative editing (tweak → look → tweak) natural in two-step — and it is the responsibility of the harness to guarantee session continuity, not something the agent improvises.
- **Budgets span the session, not the message.** Tool/token/wall-clock budgets are per-session cumulative with a per-message slice, so a long thread cannot silently accumulate unbounded spend. The typed per-message budgets from the route table still gate each turn; the session budget is the ceiling.
- **The prompt must state the thread rule explicitly** (the execute system prompt below gains): "You are the same agent across this conversation. Follow-ups in this window continue your session; treat prior accepted Δs, your observations, and your replies as your own history. Only a new chat window starts a fresh session." The self-check contract then validates that a follow-up's claims are grounded in the thread's accumulated accepted Δs, not just the current turn's.

## Execute prompt (system text)

The runtime fills bracketed fields and includes only the route-allowed catalog.

```text
You are VibeComfy's execute agent. Complete the locked route in this one
bounded session. Do not reclassify it.

THREAD CONTINUITY
You are the same agent across this conversation window. Follow-ups in this
chat continue YOUR session: prior accepted Deltas, your tool observations,
and your replies are your own history. Build on them. Only a new chat window
starts a fresh session with a fresh workflow re-attach. Do not restart,
re-ingest, or re-ask what the thread already established.

ROUTE AND INPUT
Route: [route]. Plan: [plan_summary]. User request: [query].
Baseline revision: [revision/hash]. The attached workflow authority is the
VibeWorkflow IR. Raw ComfyUI JSON is never evidence and must never be emitted.

CURRENT WORKFLOW
[render(wf, route lenses): census/reference map plus the necessary surface
and computed topology facts]
Names are deterministic bindings. Literal fields and sockets are different
channels. Treat computed lens facts as authoritative; do not infer omitted
topology.

RESEARCH
Search Hivemind with short capability/model/node phrases, adding source filters
instead of alias-heavy OR queries. Search results are leads, not evidence.
Fetch every materially relied-on record with hivemind_get and cite its returned
evidence ID. Use registry_lookup for pack ownership. Use web_search only for a
specific unresolved question after local/Hivemind evidence is empty, and say
what remained unresolved. Never manufacture consensus. The runtime derives
research_attempt as never, empty, thin, or grounded from the tool ledger.

PRECEDENT TRANSLATION
A fetched workflow precedent is rendered through its named ingest door as a
Python surface/topology lens. Read it as an immutable source pattern: extract
relevant classes, named connections, parameter relationships, and constraints.
Do not copy its bindings/uids, merge its IR, or mutate it. Author any change
fresh against the current workflow's typed library and cite the precedent ID.

EDITING
Use only the advertised Python edit surface: named literal assignment,
dst.input = src.OUTPUT, dst.input = None, node construction, del node, and
supported mode assignment. Never use positional widget/slot indexes, imports,
exec, or raw JSON. Put the complete intended edit in one atomic python batch.
The host preflights the batch, enforces the baseline/CAS guard, types and bounds,
then interprets it immutably. On rejection you may submit one complete
replacement batch; after success no further edit is allowed. Do not claim a
change until the tool returns accepted Delta and post-edit lenses.

REPLY
Answer the user directly. For edits, state only changes present in accepted
Delta; distinguish rejected or unverified work. Ground graph claims in returned
surface/topology fact IDs and research claims in ledger evidence IDs. If no
claim can be verified, fail closed: say what could not be verified and do not
produce a candidate.

SELF-CHECK AND FINAL CONTRACT
Before finalizing, check route completion, accepted Delta against the request,
channel/target correctness, topology after the edit, evidence citations, and
remaining uncertainty. In a follow-up turn, ground claims in the thread's
ACCUMULATED accepted Deltas — not only this turn's. Return:
{reply, outcome, claim_refs:{delta_ids,lens_fact_ids,evidence_ids},
 self_assessment:{request_satisfied,checks,unverified,repair_used}}.
Self-assessment is evidence for an independent judge, never authority. Every
reference must exist in the runtime-provided accepted Delta, reply lens, or
tool ledger. A missing reference makes the response invalid.
```

## Route surfaces and budgets

All ten tools remain registered once; execute advertises a least-privilege subset. The Python surface is the existing edit channel, not an eleventh/new agent tool. Output tokens are aggregate across the execute session's continuations.

| Route | Advertised tools | Effort / aggregate output / hard limits |
|---|---|---|
| `clarify`, `respond` | none | low / 2k / 30 s |
| `inspect` | `node_schema` | low / 4k / 2 calls / 60 s |
| `research` | `hivemind_search/get`, `registry_lookup`, `node_schema`, `ready_template_list/load`, policy-enabled `web_search` | medium / 8k / search 3, get 4, registry 1, web 1, local lookups 3 / 180 s |
| `requires_custom_nodes` | `registry_lookup`, `node_schema` | medium / 4k / 3 calls / 90 s |
| `revise` | `node_schema`, `ready_template_list/load`, `rank_edit_targets`, `suggest_seed_nodes`, `layout_hints`, Python surface | medium / 8k / six advisory calls total, apply 1 + replacement 1 / 180 s |
| `adapt` | all ten plus Python surface | high / 12k / research caps above, six advisory calls, apply 1 + replacement 1 / 240 s |
| `reorganise` | `layout_hints`, Python surface | medium / 6k / layout 2, apply 1 + replacement 1 / 120 s |

`web_search` remains disabled unless existing policy enables it. Token, tool, apply, and wall-clock budgets are enforced by the host, not merely stated in the prompt.

## Research and one-shot application contract

Never give the agent a full internal IR or raw record. A fetched workflow gets the same grounded `surface + topology` renderer used for the target, plus source metadata and evidence ID. For an oversized precedent, render a deterministic relevant subgraph with explicit omitted counts; forbid global topology claims rather than silently truncating them. The precedent remains a separate immutable `VibeWorkflow`; only the agent's newly authored batch can affect the target.

Do not introduce a second `declared_targets` representation. The parsed Python batch already declares targets. The host preflights the whole batch into canonical ops, verifies the request baseline and CAS expectations for every op, then calls pure `interpret(pre, batch)`. Two-step policy is atomic: any parse, resolution, CAS, channel, bound, or done-gate failure rejects the whole batch and yields zero Δ. The agent may use the typed diagnostics for one **model-authored replacement** within the same execute session. Calling that deterministic would be false; it consumes the session budget. A second failure returns no candidate.

On success, the Python tool returns accepted Δ and `render(post, surface + diff(Δ) + topology)`. Only then does the agent compose its final reply. The host validates `delta_ids ⊆ accepted Δ`, `lens_fact_ids ⊆ reply_lens`, and `evidence_ids ⊆ tool ledger`; change claims with zero Δ are invalid. The existing judge, when run, receives its strict lens subset plus `self_assessment`, but grades independently. Self-assessment is useful for disagreement telemetry, never a success gate.

## Tradeoffs and selection

| | Two-step | Full pipeline |
|---|---|---|
| Stronger | Lower latency/cost; no lossy research→implement→reply handoffs; one agent retains intent and evidence; **same-thread session continuity makes iterative editing (tweak → look → tweak) natural — the agent remembers its own Δs and observations across follow-ups** | Independent stages/judge; deeper research refinement; repeated edit feedback and recovery; smaller per-stage contexts |
| Weaker | Context/tool overload; correlated self-review; one bad batch can exhaust the edit; budget exhaustion can strand research; more prompt-policy surface | More calls, latency, handoff contracts, and opportunities for summaries to lose nuance |
| Prefer for | respond, inspect, bounded research, simple named-field/wire revisions, deterministic-layout reorganise | precedent-heavy adapt, unknown/custom schemas, multi-node structural edits, ambiguous targets, long or conflicting research |

The attractive but bad version is a literal single inference that emits batch and success prose together. It must predict CAS, minted bindings, validation, and accepted Δ; a rollback then leaves a confident reply describing a phantom edit. That directly violates Δ/reply symmetry. The bounded post-apply continuation is not optional for model-written edit replies.

## Validation and rollout

1. Unit-test mode precedence, invalid values, `classify_only`, `answer_only`, missing `execute` specs, exact route-policy coverage, tool denial, budget exhaustion, event/report compatibility, and prompt section goldens.
2. **Thread-continuity tests** (the two-step defining behavior): (a) two follow-ups in the same session id reuse the SAME execute session — no new session minted, accumulated Δs visible to the agent, a follow-up claim grounded in turn-1's accepted Δ passes; (b) a NEW chat-window id starts a fresh session — prior Δs NOT visible, workflow re-attached, agent must re-establish context; (c) route change mid-thread (e.g. edit → then "now explain it") re-runs classify but keeps the same session; (d) a follow-up that references a turn-1 edit without it being in the accumulated Δ fails the claim-ref check; (e) session budgets are cumulative with per-message slices.
3. Reuse all five IR law suites on both modes. Inject stale baselines, unknown schemas, socket/literal mismatches, bad mixed batches, done-gate failure, research timeout/empty, forged evidence IDs, and false topology/change claims. Assert atomic zero-Δ failure and no candidate.
4. Differentially run both modes with locked identical classifications over simple field edits, rewires, add/remove, inspect, research, adapt, reorganise, and the 57-case ledger. Compare `pi_edit(post)`, canonical Δ replay, judge outcome, evidence correctness, latency/cost, and failure family—not prose equality.
5. Shadow two-step behind the default-off toggle. Roll out `respond/inspect`, then simple `revise/reorganise`, then bounded `research`; keep `adapt` opt-in until its per-family judge pass rate is non-inferior. Track batch rejection, replacement use, full-mode escalation, self-check↔judge disagreement, unsupported claims, latency, cost, and thread-session reuse rate (asserting follow-ups hit the same session).

Shipping two-step before the IR-everywhere end-state is a non-starter: it recreates raw/truncated-view and positional-edit failures. Shipping it after the IR but before the full pipeline is possible, but loses the differential reference and tends to make the union tool prompt and self-check the de facto contracts; later stage separation must then recover independent gates and evidence handoffs. Shipping full first is safer: it proves the shared substrate and laws, supplies parity baselines, and makes two-step genuinely additive. Shipping full first does not block two-step; only profile schema, optional report fields, and the post-classify branch are new.

2026-08-17T21:30:24.047992Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-17T21:30:24.048161Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-17T21:30:24.048174Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short --branch && rg --files vibecomfy/executor vibecomfy/porting tests | sed -n '1,260p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## two-step-megado
tests/test_executor_hivemind_tools.py
vibecomfy/executor/profiles.py
vibecomfy/porting/lint.py
tests/test_agent_edit_settings_contract.py
tests/test_runtime_run.py
tests/test_structural_harness_runner.py
tests/test_finalize_metadata.py
tests/test_emitted_no_helpers.py
tests/test_porting_provenance.py
tests/test_execution_plan_contracts.py
vibecomfy/executor/graph_inspection.py
vibecomfy/executor/evidence_pack.py
vibecomfy/executor/agent_research_stage.py
vibecomfy/executor/profiler.py
vibecomfy/executor/graph_facts.py
vibecomfy/executor/hivemind_clients.py
vibecomfy/executor/provenance.py
vibecomfy/porting/widgets/schema.py
vibecomfy/porting/widgets/compact_resolver.py
vibecomfy/porting/widgets/aliases.py
vibecomfy/porting/widgets/settings_contract.py
vibecomfy/porting/widgets/__init__.py
vibecomfy/porting/report.py
vibecomfy/executor/profile_data/openrouter.toml
vibecomfy/executor/profile_data/openai.toml
vibecomfy/executor/profile_data/anthropic.toml
vibecomfy/executor/profile_data/__init__.py
vibecomfy/executor/profile_data/default.toml
vibecomfy/executor/profile_data/opensource.toml
vibecomfy/executor/revision_evidence.py
vibecomfy/executor/contracts.py
vibecomfy/executor/edit_suggestion_tools.py
vibecomfy/executor/hivemind_tools.py
tests/pi_transition/structural/__init__.py
tests/pi_transition/pi_worker.py
vibecomfy/porting/object_info/consume.py
vibecomfy/porting/object_info/__init__.py
vibecomfy/porting/object_info/core_regen.py
vibecomfy/porting/object_info/serialize.py
vibecomfy/porting/emitter.py
vibecomfy/porting/resolution.py
vibecomfy/porting/manual_repair.py
vibecomfy/porting/provenance.py
vibecomfy/porting/strict_ready.py
tests/pi_transition/fixtures/manifest.json
vibecomfy/executor/schemas/tool_result.schema.json
vibecomfy/executor/schemas/needs_input.schema.json
vibecomfy/executor/schemas/evidence_pack.schema.json
vibecomfy/executor/schemas/stage_package.schema.json
vibecomfy/executor/prompts.py
vibecomfy/executor/core.py
vibecomfy/executor/__init__.py
vibecomfy/executor/agent_backend.py
vibecomfy/executor/layout_hints.py
vibecomfy/executor/tool_contracts.py
vibecomfy/executor/lookup_tools.py
vibecomfy/executor/web_tools.py
vibecomfy/executor/tool_specs.py
vibecomfy/executor/stage_contracts.py
tests/test_nodes_index.py
tests/conftest.py
tests/test_cookbook_imports.py
tests/test_utils.py
tests/pi_transition/bakeoff/test_pi_bakeoff.py
tests/pi_transition/bakeoff/__init__.py
vibecomfy/porting/emit/emit_constants.py
vibecomfy/porting/emit/emit_kwargs.py
vibecomfy/porting/emit/identity.py
vibecomfy/porting/emit/subgraph.py
vibecomfy/porting/emit/node_kwargs.py
vibecomfy/porting/emit/public_inputs.py
vibecomfy/porting/emit/emit_agent_edit.py
vibecomfy/porting/emit/entrypoints.py
vibecomfy/porting/emit/signatures.py
vibecomfy/porting/emit/wrappers.py
vibecomfy/porting/emit/emit_prepare.py
vibecomfy/porting/emit/formatting.py
vibecomfy/porting/emit/__init__.py
vibecomfy/porting/emit/emit_ready.py
vibecomfy/porting/emit/emit_subgraph.py
vibecomfy/porting/emit/ui.py
vibecomfy/porting/emit/naming.py
vibecomfy/porting/emit/models.py
vibecomfy/porting/emit/valueclassify.py
tests/quarantine/structural_harness_surface.txt
tests/quarantine/comfy_nodes_hivemind_surface.txt
tests/quarantine/agent_cli_surface.txt
tests/quarantine/intent_surface.txt
tests/quarantine/runtime_embedded_surface.txt
tests/quarantine/comfy_roundtrip_surface.txt
tests/quarantine/pi_transition.txt
tests/quarantine/ready_templates_surface.txt
tests/quarantine/node_resolution_surface.txt
tests/quarantine/emitter_parity_surface.txt
tests/quarantine/core_api_surface.txt
tests/quarantine/schema_oracle_surface.txt
tests/quarantine/characterization_surface.txt
tests/quarantine/comfy_nodes_agent_surface.txt
tests/test_reorganise_orchestrate.py
tests/test_strict_ready.py
tests/test_live_agentic_runner_persistence.py
tests/test_agent_contract_codegen.py
tests/test_release_guard_four_category.py
tests/test_live_agentic_watchdog.py
tests/test_felt_fidelity_gate.py
tests/test_provenance.py
tests/test_porting_normalize_ingest.py
tests/test_authority_receipts.py
tests/test_snapshot_api_workflows.py
tests/test_porting_workbench.py
tests/test_schema_validate.py
tests/test_comfy_nodes_browser.py
tests/test_diagnostics.py
tests/test_models_registry_node_packs.py
tests/test_enrich_workflow_summaries.py
tests/test_porting_object_info.py
tests/test_agent_edit_parameter_tweak_fallback.py
tests/test_demo_factory_creative.py
tests/test_layout_operation_v1.py
tests/test_pack_resolver.py
tests/smoke/test_layer2_runpod_dropped.py
tests/smoke/test_layer2_runpod_ops.py
tests/smoke/test_layer2_runpod_matrix.py
tests/smoke/__init__.py
tests/smoke/_runpod_helpers.py
tests/smoke/test_p1_runpod.py
tests/smoke/test_z_image_only.py
tests/test_upload_external_workflows_to_hivemind.py
tests/test_b02_rich_preservation.py
tests/test_ui_layout.py
tests/test_widget_shape_evidence.py
tests/test_porting_report.py
tests/test_cli_analyze.py
tests/test_comfy_nodes_agent_transaction_storage.py
vibecomfy/porting/reorganise/report.py
vibecomfy/porting/reorganise/projection.py
vibecomfy/porting/reorganise/graph_facts.py
vibecomfy/porting/reorganise/parse.py
vibecomfy/porting/reorganise/compile.py
vibecomfy/porting/reorganise/validate.py
vibecomfy/porting/reorganise/assess.py
vibecomfy/porting/reorganise/plan_types.py
vibecomfy/porting/reorganise/orchestrate.py
vibecomfy/porting/reorganise/visualize.py
vibecomfy/porting/reorganise/__init__.py
vibecomfy/porting/reorganise/classify.py
vibecomfy/porting/reorganise/diagnostics.py
vibecomfy/porting/widget_shape_fence.py
vibecomfy/porting/assets.py
vibecomfy/porting/endpoint_invariant.py
tests/analysis/test_workflow_summary.py
tests/analysis/__init__.py
tests/test_virtual_wire_round_trip.py
tests/test_agent_route_families.py
tests/test_porting_ui_emitter.py
tests/test_structural_harness_contract.py
vibecomfy/porting/edit/lint.py
vibecomfy/porting/edit/apply_field_aliases.py
vibecomfy/porting/edit/_render.py
vibecomfy/porting/edit/_parse.py
vibecomfy/porting/edit/apply_gate.py
vibecomfy/porting/edit/validate.py
vibecomfy/porting/edit/ops.py
vibecomfy/porting/edit/_parse_execute.py
vibecomfy/porting/edit/grammar.py
tests/pi_transition/system/test_pi_edge_cases.py
tests/pi_transition/system/__init__.py
tests/pi_transition/TEST_PLAN.md
tests/pi_transition/__init__.py
tests/test_position_fidelity.py
tests/test_agent_executor_response.py
tests/test_memory_profile.py
tests/test_runtime_model_policy.py
tests/test_runtime_session_validation.py
tests/test_porting_edit_session_harness.py
tests/test_agent_runtime_adapter.py
tests/pi_transition/integration/__init__.py
tests/pi_transition/integration/test_pi_worker_fixtures.py
tests/pi_transition/harness.py
tests/test_testing_snapshot.py
tests/test_cli_misc.py
tests/test_wrapper_codegen.py
tests/test_runtime_eval_absence.py
tests/test_headless_agent_artifacts.py
tests/test_porting_emitter.py
tests/test_runtime_session_config.py
tests/test_live_agentic_source_layouts.py
tests/test_compact_widget_resolver.py
tests/test_fixture_provider.py
tests/test_v24_surface_coverage.py
tests/test_contracts_reexport.py
tests/test_quarantine_policy.py
tests/test_success_rate_cli.py
tests/test_comfy_nodes_agent_backend_spine.py
tests/test_templates_module.py
tests/test_execution_plan_runtime.py
tests/test_structural_golden_m4.py
tests/test_run_command.py
tests/test_porting_emit_signatures.py
tests/test_authority_replay_sequential.py
tests/test_live_agentic_assessor_score_honesty.py
tests/test_cache_busting.py
tests/test_layout_store.py
tests/test_doctor_lockfile.py
tests/test_runtime_session_run_untracked.py
tests/test_wrapper_discovery.py
tests/test_mutation_materialization_v1.py
tests/test_routes_session_sanitization.py
tests/test_reconcile.py
tests/test_agent_edit_artifact_replay.py
tests/known_failures.txt
tests/test_helper_resolve.py
tests/test_porting_edit_session.py
tests/test_blocks.py
tests/test_runtime_execution.py
tests/test_testing_canonical.py
tests/test_plugin_discovery.py
tests/test_headless_agent_cli.py
tests/test_executor_lookup_tools.py
tests/test_structural_golden_m5.py
tests/test_ui_emitter_widget_shape_verdict.py
tests/test_reorganise_assess.py
tests/test_store_from_ui_json.py
tests/test_live_agentic_failure_analysis.py
tests/test_origin_stamping.py
tests/test_comfy_nodes_live_smoke.py
tests/test_router.py
tests/test_headless_harness_contract.py
tests/test_porting_convert.py
tests/test_preserve_convergence.py
tests/test_executor_stage_contracts.py
tests/test_edit_batch_repl_dependencies.py
tests/test_executor_hivemind_messages.py
vibecomfy/porting/edit/schemas/v2/obligation_ledger.schema.json
vibecomfy/porting/edit/schemas/v2/add_node.schema.json
vibecomfy/porting/edit/schemas/v2/set_mode.schema.json
vibecomfy/porting/edit/schemas/v2/delta_envelope.schema.json
vibecomfy/porting/edit/schemas/v2/README.md
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json
vibecomfy/porting/edit/schemas/v2/upsert_link.schema.json
tests/property/test_emitter_fuzz.py
vibecomfy/porting/edit/schemas/v2/set_node_field.schema.json
tests/property/__init__.py
vibecomfy/porting/edit/schemas/v2/remove_node.schema.json
vibecomfy/porting/edit/schemas/v2/remove_link.schema.json
tests/test_walking_skeleton.py
tests/test_errors.py
tests/test_agent_edit_compatibility_ledger.py
tests/test_structural_harness_adapter.py
tests/test_reorganise_existing_groups.py
tests/test_comfy_nodes_agent_session.py
tests/test_reorganise_skill.py
vibecomfy/porting/edit/value_defaults.py
vibecomfy/porting/edit/_interpret.py
vibecomfy/porting/edit/types.py
vibecomfy/porting/edit/_session_types.py
vibecomfy/porting/edit/__init__.py
vibecomfy/porting/edit/session.py
vibecomfy/porting/edit/constants.py
vibecomfy/porting/edit/_diff.py

exec
/bin/zsh -lc "rg -n \"class ExecutorRequest|def run_executor|def _run_classify|_ROUTE_BEHAVIORS|class Report|phase|profile|implement|class EditSession|def render\\(|session_id|conversation|thread|57|scenario\" vibecomfy/executor vibecomfy/porting tests/test_agent_executor_response.py tests/test_executor_stage_contracts.py tests/test_porting_edit_session.py tests/test_agent_edit_compatibility_ledger.py tests/test_live_agentic_runner_persistence.py | sed -n '1,320p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
tests/test_live_agentic_runner_persistence.py:12:    _persist_scenario_summary,
tests/test_live_agentic_runner_persistence.py:16:from tests.live_agentic_harness.scenario_manifest import write_manifest
tests/test_live_agentic_runner_persistence.py:20:def _summary(tmp_path: Path, scenario_id: str, *, ok: bool) -> dict:
tests/test_live_agentic_runner_persistence.py:21:    output_dir = tmp_path / "tag" / scenario_id
tests/test_live_agentic_runner_persistence.py:23:        "scenario_id": scenario_id,
tests/test_live_agentic_runner_persistence.py:36:        "phase": "classify",
tests/test_live_agentic_runner_persistence.py:55:def test_persists_per_scenario_and_incremental_run_summary(tmp_path: Path) -> None:
tests/test_live_agentic_runner_persistence.py:59:    _persist_scenario_summary(passing, tmp_path, "tag")
tests/test_live_agentic_runner_persistence.py:60:    _persist_scenario_summary(failing, tmp_path, "tag")
tests/test_live_agentic_runner_persistence.py:65:        total_scenarios=3,
tests/test_live_agentic_runner_persistence.py:85:    _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=False)
tests/test_live_agentic_runner_persistence.py:86:    final = _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=True)
tests/test_live_agentic_runner_persistence.py:98:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:99:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:100:    scenario_path = scenarios_dir / "retry-me.json"
tests/test_live_agentic_runner_persistence.py:101:    scenario_path.write_text(json.dumps({"id": "retry-me", "query": "do it"}), encoding="utf-8")
tests/test_live_agentic_runner_persistence.py:119:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:120:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:124:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:127:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:132:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:136:    assert scenario["attempt_count"] == 2
tests/test_live_agentic_runner_persistence.py:137:    assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
tests/test_live_agentic_runner_persistence.py:138:    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
tests/test_live_agentic_runner_persistence.py:139:    assert scenario["attempts"][0]["retryable_infra"] is True
tests/test_live_agentic_runner_persistence.py:140:    assert scenario["attempts"][0]["agent_exercised"] is False
tests/test_live_agentic_runner_persistence.py:141:    assert scenario["attempts"][0]["model_attempts"] == []
tests/test_live_agentic_runner_persistence.py:142:    assert scenario["attempts"][0]["killed_before_first_attempt"] is True
tests/test_live_agentic_runner_persistence.py:143:    assert scenario["attempts"][0]["elapsed_s"] is not None
tests/test_live_agentic_runner_persistence.py:144:    assert scenario["final_attempt"] == 2
tests/test_live_agentic_runner_persistence.py:168:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:169:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:170:    scenario_path = scenarios_dir / "provider-capacity.json"
tests/test_live_agentic_runner_persistence.py:171:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:221:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:222:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:226:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:229:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:234:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:238:    assert scenario["attempt_count"] == 1
tests/test_live_agentic_runner_persistence.py:239:    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
tests/test_live_agentic_runner_persistence.py:240:    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
tests/test_live_agentic_runner_persistence.py:241:    assert scenario["attempts"][0]["retryable_infra"] is False
tests/test_live_agentic_runner_persistence.py:248:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:249:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:250:    scenario_path = scenarios_dir / "typed-empty.json"
tests/test_live_agentic_runner_persistence.py:251:    scenario_path.write_text(json.dumps({"id": "typed-empty", "query": "do it"}), encoding="utf-8")
tests/test_live_agentic_runner_persistence.py:267:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:268:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:272:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:279:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:281:    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:282:    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
tests/test_live_agentic_runner_persistence.py:283:    assert scenario["attempts"][1]["live_agentic_success"] is True
tests/test_live_agentic_runner_persistence.py:290:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:291:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:292:    scenario_path = scenarios_dir / "malformed.json"
tests/test_live_agentic_runner_persistence.py:293:    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
tests/test_live_agentic_runner_persistence.py:308:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:309:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:313:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:320:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:322:    assert scenario["score_class"] == "product_fail"
tests/test_live_agentic_runner_persistence.py:323:    assert scenario.get("retryable_infra") is not True
tests/test_live_agentic_runner_persistence.py:330:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:331:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:332:    scenario_path = scenarios_dir / "provider-down.json"
tests/test_live_agentic_runner_persistence.py:333:    scenario_path.write_text(json.dumps({"id": "provider-down", "query": "do it"}), encoding="utf-8")
tests/test_live_agentic_runner_persistence.py:356:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:357:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:361:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:364:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:369:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:370:    assert scenario["attempt_count"] == 1
tests/test_live_agentic_runner_persistence.py:371:    assert scenario["failure_class"] == "infra_provider_capacity"
tests/test_live_agentic_runner_persistence.py:372:    assert scenario["score_class"] == "infra_blocked"
tests/test_live_agentic_runner_persistence.py:383:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:384:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:385:    scenario_path = scenarios_dir / "soft-search-warning.json"
tests/test_live_agentic_runner_persistence.py:386:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:425:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:426:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:430:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:433:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:438:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:439:    assert scenario["attempt_count"] == 1
tests/test_live_agentic_runner_persistence.py:440:    assert scenario["failure_class"] == "product_or_assessment_failure"
tests/test_live_agentic_runner_persistence.py:441:    assert scenario["score_class"] == "product_fail"
tests/test_live_agentic_runner_persistence.py:442:    assert scenario.get("retryable_infra") is not True
tests/test_live_agentic_runner_persistence.py:447:def test_runner_timeout_preserves_scenario_graph_change_expectation(
tests/test_live_agentic_runner_persistence.py:451:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:452:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:453:    scenario_path = scenarios_dir / "diagnose.json"
tests/test_live_agentic_runner_persistence.py:454:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:468:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:469:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:473:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:476:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:481:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:482:    assert scenario["guard"]["assessment"]["expect_graph_changed"] is False
tests/test_live_agentic_runner_persistence.py:483:    assert scenario["failure_class"] == "infra_timeout"
tests/test_live_agentic_runner_persistence.py:563:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:564:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:565:    scenario_path = scenarios_dir / "json-quoted-secrets.json"
tests/test_live_agentic_runner_persistence.py:566:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:581:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:582:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:586:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:589:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:622:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:623:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:624:    scenario_path = scenarios_dir / "transport.json"
tests/test_live_agentic_runner_persistence.py:625:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:645:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:646:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:650:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:653:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:670:    assert summary["scenarios"][0]["transport"] == "native"
tests/test_live_agentic_runner_persistence.py:685:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:686:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:687:    scenario_path = scenarios_dir / "no-transport.json"
tests/test_live_agentic_runner_persistence.py:688:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:707:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:708:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:712:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:715:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:729:    assert summary["scenarios"][0]["transport"] == "openrouter"
tests/test_live_agentic_runner_persistence.py:742:    scenarios_dir = tmp_path / "scenarios"
tests/test_live_agentic_runner_persistence.py:743:    scenarios_dir.mkdir()
tests/test_live_agentic_runner_persistence.py:744:    scenario_path = scenarios_dir / "observed-transport.json"
tests/test_live_agentic_runner_persistence.py:745:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:770:    write_manifest(scenarios_dir)
tests/test_live_agentic_runner_persistence.py:771:    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)
tests/test_live_agentic_runner_persistence.py:775:        scenarios_dir=scenarios_dir,
tests/test_live_agentic_runner_persistence.py:778:        per_scenario_timeout=1,
tests/test_live_agentic_runner_persistence.py:784:    scenario = summary["scenarios"][0]
tests/test_live_agentic_runner_persistence.py:787:    observed = scenario["attempts"][0]["model_attempts"][0]
tests/test_live_agentic_runner_persistence.py:791:    assert scenario["failure_class"] == "infra_empty_response"
tests/test_live_agentic_runner_persistence.py:793:    assert scenario["transport"] == "native"
tests/test_live_agentic_runner_persistence.py:794:    assert observed["transport"] == scenario["transport"]
tests/test_live_agentic_runner_persistence.py:803:    scenario_path = tmp_path / "single.json"
tests/test_live_agentic_runner_persistence.py:804:    scenario_path.write_text(
tests/test_live_agentic_runner_persistence.py:810:    def fake_headless(scenario, *, output_base, tag, transport=None):  # noqa: ANN001, ANN202, ARG001
tests/test_live_agentic_runner_persistence.py:813:            "scenario_id": "single",
tests/test_live_agentic_runner_persistence.py:821:    def fake_guard(output_dir, *, scenario=None):  # noqa: ANN001, ANN202, ARG001
tests/test_live_agentic_runner_persistence.py:829:        "tests.live_agentic_harness.adapter.run_headless_scenario", fake_headless
tests/test_live_agentic_runner_persistence.py:834:        str(scenario_path), "tag", tmp_path / "out", None, transport="openrouter"
tests/test_agent_edit_compatibility_ledger.py:85:    "panel_thread.js",
tests/test_executor_stage_contracts.py:136:    """C01/F01: the research stage hands the implement phase a StagePackage
tests/test_executor_stage_contracts.py:138:    typed envelope the executor now constructs at the research→implement
vibecomfy/porting/lint.py:82:# -- Rule implementations ----------------------------------------------------
vibecomfy/executor/profiles.py:3:Loads per-phase agent specs from Arnold-owned TOML profiles.  Each profile
vibecomfy/executor/profiles.py:4:maps the canonical stages (``classify``, ``research``, ``implement``,
vibecomfy/executor/profiles.py:8:The primary source is ``arnold.pipelines.vibecomfy_executor.profiles``
vibecomfy/executor/profiles.py:10:the profile directory via ``set_profile_override_dir()``.
vibecomfy/executor/profiles.py:28:DECLARED_STAGES: frozenset[str] = frozenset({"classify", "research", "implement", "reply"})
vibecomfy/executor/profiles.py:38:    """Resolved agent specification for a single executor phase.
vibecomfy/executor/profiles.py:56:# Module-level override: when set to a non-None Path, profile loading uses
vibecomfy/executor/profiles.py:58:# package.  Call ``set_profile_override_dir(None)`` to restore the default.
vibecomfy/executor/profiles.py:59:_profile_override_dir: Path | None = None
vibecomfy/executor/profiles.py:62:def set_profile_override_dir(path: Path | str | None) -> None:
vibecomfy/executor/profiles.py:63:    """Override the directory from which profile TOMLs are loaded.
vibecomfy/executor/profiles.py:68:    global _profile_override_dir
vibecomfy/executor/profiles.py:70:        _profile_override_dir = None
vibecomfy/executor/profiles.py:72:        _profile_override_dir = Path(path)
vibecomfy/executor/profiles.py:75:# ── profile directory resolution ─────────────────────────────────────────────
vibecomfy/executor/profiles.py:78:def _profile_dir() -> Path:
vibecomfy/executor/profiles.py:79:    """Return the resolved profile directory.
vibecomfy/executor/profiles.py:81:    Uses the test override when set; otherwise loads the profile TOMLs
vibecomfy/executor/profiles.py:82:    shipped inside ``vibecomfy.executor.profile_data`` so that external
vibecomfy/executor/profiles.py:85:    if _profile_override_dir is not None:
vibecomfy/executor/profiles.py:86:        return _profile_override_dir
vibecomfy/executor/profiles.py:91:    pkg_files = resources.files("vibecomfy.executor.profile_data")
vibecomfy/executor/profiles.py:95:            "Cannot locate executor profile directory. "
vibecomfy/executor/profiles.py:97:            "set_profile_override_dir() to point to a local profile directory."
vibecomfy/executor/profiles.py:210:def load_profile(name: str) -> dict[str, AgentSpecShape]:
vibecomfy/executor/profiles.py:211:    """Load a single named profile.
vibecomfy/executor/profiles.py:213:    Reads ``{name}.toml`` from the profile directory and parses each
vibecomfy/executor/profiles.py:217:    ``"implement"``, ``"reply"``) to its resolved spec.
vibecomfy/executor/profiles.py:219:    toml_path = _profile_dir() / f"{name}.toml"
vibecomfy/executor/profiles.py:225:    # Allow profiles to nest their stages under a top-level key.  Two common
vibecomfy/executor/profiles.py:228:    #   2. Stages under [profiles.{name}] (Arnold-style packaging).
vibecomfy/executor/profiles.py:229:    #   3. Stages under a single wrapper key such as [default] or [profile].
vibecomfy/executor/profiles.py:232:        # Convention 2: {profiles = {name = {classify = ...}}}
vibecomfy/executor/profiles.py:234:            "profiles" in raw
vibecomfy/executor/profiles.py:235:            and isinstance(raw["profiles"], dict)
vibecomfy/executor/profiles.py:236:            and isinstance(raw["profiles"].get(name), dict)
vibecomfy/executor/profiles.py:238:            raw = raw["profiles"][name]
vibecomfy/executor/profiles.py:253:def load_all_profiles() -> dict[str, dict[str, AgentSpecShape]]:
vibecomfy/executor/profiles.py:254:    """Load every ``*.toml`` profile from the profile directory.
vibecomfy/executor/profiles.py:256:    Returns a mapping from profile name (stem) to its resolved stage map.
vibecomfy/executor/profiles.py:258:    profiles: dict[str, dict[str, AgentSpecShape]] = {}
vibecomfy/executor/profiles.py:259:    for toml_path in sorted(_profile_dir().glob("*.toml")):
vibecomfy/executor/profiles.py:261:        profiles[name] = load_profile(name)
vibecomfy/executor/profiles.py:262:    return profiles
vibecomfy/executor/profiles.py:268:    "load_all_profiles",
vibecomfy/executor/profiles.py:269:    "load_profile",
vibecomfy/executor/profiles.py:270:    "set_profile_override_dir",
tests/test_porting_edit_session.py:4:implementation. Loads raw LiteGraph UI JSON fixtures, converts them through
tests/test_porting_edit_session.py:12:All tests in this module are expected to FAIL until EditSession is implemented.
tests/test_porting_edit_session.py:134:    they prove the contract exists before the implementation.
tests/test_porting_edit_session.py:141:        raise NotImplementedError("EditSession not yet implemented (M1 Step 8)")
tests/test_porting_edit_session.py:143:    def render(self) -> str:
tests/test_porting_edit_session.py:145:        raise NotImplementedError("EditSession.render not yet implemented")
tests/test_porting_edit_session.py:149:        raise NotImplementedError("EditSession.apply_batch not yet implemented")
tests/test_porting_edit_session.py:153:        raise NotImplementedError("EditSession.done not yet implemented")
tests/test_porting_edit_session.py:246:        This test MUST fail until EditSession.render is implemented with
tests/test_porting_edit_session.py:262:        with name-lock enforcement are implemented.
tests/test_porting_edit_session.py:312:        # This test must fail until the slot codec is implemented.
tests/test_porting_edit_session.py:321:                "slot_codec not yet implemented — "
tests/test_porting_edit_session.py:336:                "slot_codec not yet implemented — "
tests/test_porting_edit_session.py:356:                "slot_codec not yet implemented — "
tests/test_porting_edit_session.py:1810:        # _safe_output_name are implementation details of the emitter
vibecomfy/porting/rules_registry.py:322:            "for the canonical implementation."
vibecomfy/executor/agent_research_stage.py:1:"""C1 agent-owned research stage — one genuine tool-calling agent phase.
vibecomfy/executor/agent_research_stage.py:3:Runs the research phase for ``research`` / ``adapt`` routes as a single
vibecomfy/executor/agent_research_stage.py:8:records typed evidence, and enforces the phase allowlist + effort budgets.
vibecomfy/executor/agent_research_stage.py:10:is the only handoff into the implement phase.
vibecomfy/executor/agent_research_stage.py:14:      research-phase tool catalog, and a compact bounded digest of tool
vibecomfy/executor/agent_research_stage.py:20:    * Tool calls outside the research-phase allowlist
vibecomfy/executor/agent_research_stage.py:190:    The attempt is a Python-side statement about what the research phase
vibecomfy/executor/agent_research_stage.py:228:# Research-phase tool allowlist (C01): the agent may only call these tools.
vibecomfy/executor/agent_research_stage.py:230:# executor research phase is Hivemind-first.
vibecomfy/executor/agent_research_stage.py:377:    research phase never poisons the pipeline.
vibecomfy/executor/agent_research_stage.py:466:# The agent decision request carries ONLY the question + the research-phase
vibecomfy/executor/agent_research_stage.py:523:    research-phase tool catalog, the call/finish action contract, the
vibecomfy/executor/agent_research_stage.py:533:        f"Available tools (research phase only):\n{catalog}\n"
vibecomfy/executor/agent_research_stage.py:564:        "question. The implement agent (or the user, on research routes) "
vibecomfy/executor/agent_research_stage.py:719:        profiling_context={"backend_phase": "research_stage"},
vibecomfy/executor/agent_research_stage.py:726:    """Bind the provider decision turn to the resolved research profile spec."""
vibecomfy/executor/agent_research_stage.py:908:    research-phase allowlist plus I01 budgets (3 searches / 6 fetches /
vibecomfy/executor/agent_research_stage.py:933:    module-level tool implementations / provider decision turn, resolved at
vibecomfy/executor/agent_research_stage.py:1107:                warnings.append("research stage phase deadline exceeded; stopped early")
vibecomfy/executor/agent_research_stage.py:1221:                    "research stage phase deadline exceeded after the decision "
vibecomfy/executor/agent_research_stage.py:1233:                        f"tool {tool!r} is not in the research phase allowlist; "
vibecomfy/executor/agent_research_stage.py:1345:                    "research stage phase deadline exceeded after the tool "
vibecomfy/executor/agent_research_stage.py:1392:            # can fail closed instead of implementing from nothing.
vibecomfy/executor/profiler.py:14:    os.getenv("VIBECOMFY_PROFILER_LOG_PATH", "/tmp/vibecomfy_executor_profiler.log")
vibecomfy/executor/profiler.py:22:def new_profile_id(prefix: str = "prof") -> str:
vibecomfy/executor/profiler.py:59:def profiler_log(
vibecomfy/executor/profiler.py:68:    logger.log(level, "vibecomfy.profiler %s", line)
vibecomfy/executor/profiler.py:92:        profiler_log(
vibecomfy/executor/profiler.py:105:        profiler_log(
vibecomfy/executor/profiler.py:132:def profiler_span(
vibecomfy/porting/object_info/core_regen.py:94:    import threading
vibecomfy/porting/object_info/core_regen.py:141:    thread = threading.Thread(target=main.main, kwargs={"listen": "127.0.0.1", "port": port}, daemon=True)
vibecomfy/porting/object_info/core_regen.py:142:    thread.start()
vibecomfy/executor/hivemind_clients.py:1:"""Hivemind transport for the executor research phase (A01).
vibecomfy/executor/hivemind_clients.py:65:# timeout (HTTP 500 with Postgres SQLSTATE 57014).
vibecomfy/executor/hivemind_clients.py:158:# REC-A: Postgres statement-timeout (SQLSTATE 57014) surfaces as HTTP 500 with
vibecomfy/executor/hivemind_clients.py:159:# a body like ``{"code":"57014",...,"message":"canceling statement due to
vibecomfy/executor/hivemind_clients.py:163:# soft miss.  A persistent 57014 is still a soft miss
vibecomfy/executor/hivemind_clients.py:213:      SQLSTATE 57014 (statement timeout) after the retry budget was spent;
vibecomfy/executor/hivemind_clients.py:238:    """True when an HTTP error body carries Postgres SQLSTATE 57014.
vibecomfy/executor/hivemind_clients.py:241:    Postgres error as ``{"code":"57014","message":"canceling statement due
vibecomfy/executor/hivemind_clients.py:246:    return '"57014"' in body or "canceling statement due to statement timeout" in body
vibecomfy/executor/hivemind_clients.py:262:    57014) is retried ONCE with a short backoff — the query is valid, the
vibecomfy/executor/hivemind_clients.py:263:    backend just hit its statement budget.  A persistent 57014 still raises,
vibecomfy/executor/hivemind_clients.py:409:    """Phrase-first ilike with no leading wildcard (RC1 57014 degrade).
vibecomfy/executor/hivemind_clients.py:1051:                                    "message": "hivemind_query_degraded_after_57014",
vibecomfy/porting/render.py:175:def render(
vibecomfy/executor/profile_data/openrouter.toml:1:# Explicit OpenRouter profile for vibecomfy-executor.
vibecomfy/executor/profile_data/openrouter.toml:6:[profiles.openrouter]
vibecomfy/executor/profile_data/openrouter.toml:9:implement  = "openrouter:openrouter:deepseek/deepseek-v4-pro"
vibecomfy/porting/resolution.py:3:Provides the NodeBackend protocol, the LintIndexBackend implementation,
vibecomfy/porting/resolution.py:135:    """Backend for node lookups — implemented by LintIndexBackend."""
vibecomfy/executor/profile_data/openai.toml:1:# OpenAI Codex profile for vibecomfy-executor.
vibecomfy/executor/profile_data/openai.toml:6:[profiles.openai]
vibecomfy/executor/profile_data/openai.toml:9:implement  = "codex:gpt-5.6-sol:medium"
vibecomfy/executor/profile_data/anthropic.toml:1:# Anthropic Claude profile for vibecomfy-executor.
vibecomfy/executor/profile_data/anthropic.toml:4:# Classify / reply use Haiku, research uses Sonnet, and implement uses Opus.
vibecomfy/executor/profile_data/anthropic.toml:5:[profiles.anthropic]
vibecomfy/executor/profile_data/anthropic.toml:8:implement  = "claude:claude-opus-4-7:high"
vibecomfy/executor/profile_data/__init__.py:1:"""Executor profile TOMLs shipped with VibeComfy.
vibecomfy/executor/profile_data/__init__.py:3:These profiles are duplicated from ``arnold.pipelines.vibecomfy_executor.profiles``
vibecomfy/executor/profile_data/__init__.py:5:that contains the pipeline-local profile package.
vibecomfy/executor/profile_data/default.toml:1:# Pipeline-local profile for vibecomfy-executor.
vibecomfy/executor/profile_data/default.toml:4:# ctx.profile and constructs the matching AIAgent for the stage.
vibecomfy/executor/profile_data/default.toml:6:[profiles.default]
vibecomfy/executor/profile_data/default.toml:9:implement  = "hermes:openrouter:deepseek/deepseek-v4-pro"
vibecomfy/porting/layout/engine.py:4:primitives into a :class:`LayoutResult` in ten ordered phases:
vibecomfy/porting/layout/engine.py:114:    # id→uid translation (used in in-degree computation and later phases).
vibecomfy/executor/profile_data/opensource.toml:1:# Open-source / OpenRouter profile for vibecomfy-executor.
vibecomfy/executor/profile_data/opensource.toml:4:# Classify uses DeepSeek V4 Flash; research / implement use Kimi K2.7 Code;
vibecomfy/executor/profile_data/opensource.toml:6:[profiles.opensource]
vibecomfy/executor/profile_data/opensource.toml:9:implement  = "hermes:openrouter:moonshotai/kimi-k2.7-code"
vibecomfy/porting/emit/emit_constants.py:1002:        metadata.setdefault("comfy_configuration", {"memory_profile": 3, "fp8_e4m3fn_text_enc": True})
vibecomfy/executor/contracts.py:4:implement → reply pipeline.  Every contract is a frozen dataclass with a
vibecomfy/executor/contracts.py:195:    phase: str = _MODEL_ATTEMPT_UNKNOWN
vibecomfy/executor/contracts.py:216:        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
vibecomfy/executor/contracts.py:241:            phase=value.get("phase", _MODEL_ATTEMPT_UNKNOWN),
vibecomfy/executor/contracts.py:258:            "phase": self.phase,
vibecomfy/executor/contracts.py:536:    "implementation",
vibecomfy/executor/contracts.py:542:    "implementation_skipped",
vibecomfy/executor/contracts.py:543:    "implementation_failed",
vibecomfy/executor/contracts.py:571:    implement: bool,
vibecomfy/executor/contracts.py:593:        if implement or intent == "edit" or task in {"edit_graph", "research_precedent"}:
vibecomfy/executor/contracts.py:636:        if research and implement:
vibecomfy/executor/contracts.py:638:        elif implement:
vibecomfy/executor/contracts.py:694:    ``research`` and ``implement`` are booleans that drive whether those phases
vibecomfy/executor/contracts.py:699:    ``route`` is the authoritative phase-routing label.  When the classifier
vibecomfy/executor/contracts.py:701:    normalized route from the legacy ``research`` / ``implement`` / ``intent``
vibecomfy/executor/contracts.py:710:    that downstream phases may use to select models or token budgets.
vibecomfy/executor/contracts.py:715:    implement: bool = False
vibecomfy/executor/contracts.py:749:            implement=self.implement,
vibecomfy/executor/contracts.py:768:            expected_research, expected_implement = route_booleans[self.route]
vibecomfy/executor/contracts.py:770:            object.__setattr__(self, "implement", expected_implement)
vibecomfy/executor/contracts.py:798:            implement=self.implement,
vibecomfy/executor/contracts.py:811:            implement=self.implement,
vibecomfy/executor/contracts.py:820:            "implement": self.implement,
vibecomfy/executor/contracts.py:871:            implement=False,
vibecomfy/executor/contracts.py:893:            implement=True,
vibecomfy/executor/contracts.py:906:def _derive_route(*, research: bool, implement: bool, intent: str) -> str:
vibecomfy/executor/contracts.py:910:    * revise → implement without research
vibecomfy/executor/contracts.py:911:    * adapt → research + implement (legacy booleans are unambiguous here)
vibecomfy/executor/contracts.py:912:    * research → research without implementation and research intent
vibecomfy/executor/contracts.py:913:    * inspect → explain_graph intent without implementation
vibecomfy/executor/contracts.py:914:    * respond → respond intent without research or implementation
vibecomfy/executor/contracts.py:915:    * clarify → neither research nor implementation when intent is ambiguous
vibecomfy/executor/contracts.py:917:    if implement and research:

exec
/bin/zsh -lc 'rg -n "''^(class ExecutorRequest|class ExecutorResponse|class Report|def _run_classify|def run_executor|_ROUTE_BEHAVIORS|def _run_|@dataclass)" vibecomfy/executor/core.py vibecomfy/executor/contracts.py vibecomfy/executor/profiles.py vibecomfy/executor/agent_backend.py vibecomfy/porting/edit/session.py vibecomfy/porting/render.py
sed -n '"'1,220p' vibecomfy/executor/core.py
sed -n '650,820p' vibecomfy/executor/core.py
sed -n '1640,1910p' vibecomfy/executor/core.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
vibecomfy/executor/profiles.py:36:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:186:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:687:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:955:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:956:class ExecutorRequest:
vibecomfy/executor/contracts.py:1135:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1154:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1166:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1188:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1194:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1208:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1367:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1431:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1490:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1571:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1635:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1745:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1834:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1835:class Report:
vibecomfy/executor/contracts.py:1938:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:1977:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:2155:@dataclass(frozen=True)
vibecomfy/executor/contracts.py:2357:@dataclass(frozen=True)
vibecomfy/executor/core.py:137:@dataclass(frozen=True)
vibecomfy/executor/core.py:148:_ROUTE_BEHAVIORS = MappingProxyType({
vibecomfy/executor/core.py:703:def _run_classify(
vibecomfy/executor/core.py:812:def _run_research(*args: Any, **kwargs: Any) -> Any:
vibecomfy/executor/core.py:833:@dataclass(frozen=True)
vibecomfy/executor/core.py:1054:def _run_agent_owned_research(
vibecomfy/executor/core.py:1141:def _run_implement(
vibecomfy/executor/core.py:1464:def _run_reply(
vibecomfy/executor/core.py:1699:def run_executor(
"""Executor orchestration: classify → research → implement → reply.

Implements the full executor pipeline (SD1).  Every request flows through
classify (always calls the model backend), then optionally research and/or
implement, then always reply via the model backend.

Failures are converted through the existing failure-envelope classification
machinery (``classify_failure`` / ``failure_envelope`` from the agent
contracts module) — raw exceptions never leak out of this module.
"""

from __future__ import annotations

import logging
import os
import threading
import time
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
    begin_model_attempt_capture,
    end_deepseek_usage_capture,
    end_model_attempt_capture,
    snapshot_deepseek_usage_capture,
    snapshot_model_attempt_capture,
)
from vibecomfy.agent.deepseek_usage import estimate_deepseek_cost_usd
from vibecomfy.executor.profiler import (
    new_profile_id,
    profiler_log,
    profiler_span,
    short_text,
)

from .agent_backend import run_classify_turn, run_reply_turn
from .agent_research_stage import (
    RESEARCH_ATTEMPT_EMPTY,
    RESEARCH_ATTEMPT_GROUNDED,
    RESEARCH_ATTEMPT_NEVER,
    RESEARCH_ATTEMPT_THIN,
    AgentResearchTrace,
    build_research_brief,
    derive_research_attempt,
    form_research_question,
    run_agent_research_stage,
)
from .evidence_pack import EvidenceLedger, EvidenceLedgerEntry, EvidencePack
from .stage_contracts import StageDiagnostic, StagePackage
from .tool_contracts import ToolStatus
from .prompts import build_classify_messages
from .contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    _ALLOWED_ROUTES,
    coerce_model_attempts,
    warning_detail_from_exception,
)
from .profiles import (
    AgentSpecShape,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

# Interval between ``vibecomfy.executor.phase`` ``status="working"`` heartbeat
# events emitted while the implement phase is running.
_IMPLEMENT_HEARTBEAT_INTERVAL_SECONDS = 15.0


def _spec_fields(spec: AgentSpecShape | None) -> dict[str, Any]:
    if spec is None:
        return {}
    return {"route": spec.agent, "model": spec.model, "effort": spec.effort}


def _model_attempts_from_exception(exc: BaseException) -> tuple[dict[str, Any], ...]:
    """Return the first canonical attempt sequence found in an exception chain."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        attempts = coerce_model_attempts(getattr(current, "model_attempts", None))
        if attempts:
            return attempts
        worker_result = getattr(current, "worker_result", None)
        if isinstance(worker_result, Mapping):
            attempts = coerce_model_attempts(worker_result.get("model_attempts"))
            if attempts:
                return attempts
        current = current.__cause__
    return ()


def _enrich_failure_envelope(
    failure: Any,
    exc: BaseException,
) -> Any:
    """Attach only canonical model-attempt evidence to a failure envelope."""
    attempts = _model_attempts_from_exception(exc)
    if not attempts:
        return failure
    context = dict(failure.agent_failure_context or {})
    context["model_attempts"] = list(attempts)
    return replace(failure, agent_failure_context=context)


def _failure_model_attempts(failure: Any) -> tuple[dict[str, Any], ...]:
    """Read canonical attempts previously attached to a failure envelope."""
    context = getattr(failure, "agent_failure_context", None)
    if not isinstance(context, Mapping):
        return ()
    return coerce_model_attempts(context.get("model_attempts"))


# ── route-aware behavior helpers (SD2) ───────────────────────────────────────


@dataclass(frozen=True)
class RouteBehavior:
    route: str
    needs_research: bool
    needs_implement: bool
    plan_summary: str
    clears_result_graph: bool
    reply_uses_graph_inspection: bool
    can_produce_candidate: bool


_ROUTE_BEHAVIORS = MappingProxyType({
    "clarify": RouteBehavior(
        route="clarify",
        needs_research=False,
        needs_implement=False,
        plan_summary="Ask a clarifying question before proceeding.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "respond": RouteBehavior(
        route="respond",
        needs_research=False,
        needs_implement=False,
        plan_summary="Answer directly from existing context without research or editing.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "inspect": RouteBehavior(
        route="inspect",
        needs_research=False,
        needs_implement=False,
        plan_summary="Inspect the graph without editing or outside research.",
        clears_result_graph=True,
        reply_uses_graph_inspection=True,
        can_produce_candidate=False,
    ),
    "research": RouteBehavior(
        route="research",
        needs_research=True,
        needs_implement=False,
        plan_summary="Research workflows, nodes, or techniques, then answer without editing.",
        clears_result_graph=True,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "requires_custom_nodes": RouteBehavior(
        route="requires_custom_nodes",
        needs_research=False,
        needs_implement=False,
        plan_summary="Report that the requested edit cannot be safely authored from the current evidence.",
        clears_result_graph=True,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "revise": RouteBehavior(
        route="revise",
        needs_research=False,
        needs_implement=True,
        plan_summary="Revise the current graph without research.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=True,
    ),
    "adapt": RouteBehavior(
        route="adapt",
        needs_research=True,
        needs_implement=True,
        plan_summary="Research workflow precedents, then adapt them to the current graph.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=True,
    ),
    "reorganise": RouteBehavior(
        route="reorganise",
        needs_research=False,
        needs_implement=True,
        plan_summary="Reorganise the current canvas layout without changing workflow semantics.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=True,
    ),
    """
    name = profile_name or "default"
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Executor profile '{name}' not found."
        ) from None
    except Exception as exc:
        raise ValueError(
            f"Failed to load executor profile '{name}': {exc}"
        ) from exc

    spec = profile.get(stage)
    if spec is None:
        raise ValueError(
            f"Profile '{name}' is missing the '{stage}' stage."
        )
    return spec


# ── classify phase ───────────────────────────────────────────────────────────


def _classify_stage_message(message: str) -> str:
    """Classify-stage failures are not workflow-validation errors (RC7)."""
    if "edited workflow has validation errors" in (message or ""):
        return (
            "Classification failed: the classifier reply was missing required "
            "fields or was not valid JSON. The graph is unchanged."
        )
    return message


_CLASSIFY_JSON_NUDGE = (
    "Your previous reply was missing required fields or was not valid JSON. "
    "Return the exact JSON object required by the classify schema and nothing else."
)


def _classify_parse_is_retryable(exc: BaseException) -> bool:
    """True for classify malformed_json / missing_required_fields only."""
    if isinstance(exc, (MalformedModelJSON, MissingRequiredField)):
        return True
    from vibecomfy.executor.agent_backend import _downstream_failure_type

    raw = getattr(exc, "raw_response_preview", None)
    return _downstream_failure_type(raw if isinstance(raw, str) else None) in {
        "malformed_json",
        "missing_required_fields",
    }


def _run_classify(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    session_context: dict[str, Any] | None = None,
) -> ClassifyDecision:
    """Run the classify model turn.

    Always calls the model (SD1).  Converts provider exceptions through
    ``classify_failure`` so raw exceptions never leak.
    """
    try:
        # Build enriched messages when session context carries actual data
        # for reference resolution (M3).  Otherwise, let run_classify_turn
        # build them from the default parameters.
        # Batch 12 (Law 4): classify sees ONLY the census lens — the compact
        # node/class census + reference map (derived from the IR via the
        # renderer).  No widgets, no edges, no raw-JSON sidecar.
        graph_summary = _render_census_text(request.graph)
        classify_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "effort": spec.effort,
            "has_graph": request.graph is not None,
            "graph_summary": graph_summary,
        }
        # Pre-build messages whenever we have session context beyond the
        # bare query.  The census lens already carries the node reference
        # map, so no separate raw-JSON walk is needed for reference
        # resolution on first-turn or follow-up graph edits.
        if isinstance(session_context, dict) and (
            session_context.get("recent_messages")
            or session_context.get("prior_clarification")
            or session_context.get("latest_candidate")
            or session_context.get("prior_route")
        ):
            classify_kwargs["messages"] = build_classify_messages(
                request.query,
                has_graph=request.graph is not None,
                graph_summary=graph_summary,
                session_context=session_context,
            )

        try:
            return run_classify_turn(request.query, **classify_kwargs)
        except (ProviderError, AuthError, TimeoutError) as first_exc:
            if not _classify_parse_is_retryable(first_exc):
                raise
        except Exception as first_exc:
            if isinstance(first_exc, _ExecutorPhaseError) or not _classify_parse_is_retryable(
                first_exc
            ):
                raise
        retry_kwargs = dict(classify_kwargs)
        base_messages = retry_kwargs.get("messages")
        if not isinstance(base_messages, list):
            base_messages = build_classify_messages(
                request.query,
                has_graph=request.graph is not None,
                graph_summary=graph_summary,
                session_context=session_context if isinstance(session_context, dict) else None,
            )
        retry_kwargs["messages"] = [
            *base_messages,
            {"role": "user", "content": _CLASSIFY_JSON_NUDGE},
        ]
        return run_classify_turn(request.query, **retry_kwargs)
    except _ExecutorPhaseError:
        raise
    except (ProviderError, AuthError, MalformedModelJSON,
            MissingRequiredField, TimeoutError) as exc:
        # Map provider-level errors through the failure envelope machinery.
        failure = classify_failure("agent_response", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=_classify_stage_message(failure.user_facing_message),
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc
    except Exception as exc:
        failure = classify_failure("classify", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=_classify_stage_message(failure.user_facing_message),
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc


# ── research phase ───────────────────────────────────────────────────────────


def run_research_phase(*args: Any, **kwargs: Any) -> Any:
    """Legacy automatic research engine — REMOVED by the agent-judgment rework.

    Kept only so tests can prove the active path never calls it
    (``mock.assert_not_called()``). Any live call raises: research is
    agent-owned (C01); the prefetch is gone.
    """
    raise RuntimeError(
        "legacy automatic research engine removed (C01); research is agent-owned — "
        "use run_agent_research_stage via _run_agent_owned_research"
    )


def _run_research(*args: Any, **kwargs: Any) -> Any:
    """Legacy executor research phase — removed (C01); see ``run_research_phase``."""
    return run_research_phase(*args, **kwargs)


def _default_hivemind_client(*args: Any, **kwargs: Any) -> Any:
    """Legacy default Hivemind client — removed (C01); research is agent-owned."""
    raise RuntimeError(
        "legacy _default_hivemind_client removed (C01); hivemind access is via "
    """Best-effort websocket send for executor lifecycle events."""
    try:
        from server import PromptServer  # noqa: PLC0415
    except ImportError:
        return
    try:
        if hasattr(PromptServer.instance, "send_sync") and callable(
            PromptServer.instance.send_sync
        ):
            PromptServer.instance.send_sync(event, payload, sid=client_id)
        elif hasattr(PromptServer.instance, "send_json") and callable(
            PromptServer.instance.send_json
        ):
            PromptServer.instance.send_json(event, payload, sid=client_id)
    except Exception:
        LOGGER.debug(
            "executor websocket send for event %r to client %r failed",
            event,
            client_id,
            exc_info=True,
        )


def _emit_executor_phase_event(
    request: ExecutorRequest,
    *,
    executor_id: str,
    phase: str,
    status: str,
    plan: ClassifyDecision | None = None,
    client_id: str | None = None,
) -> None:
    if not client_id:
        return
    payload = {
        "executor_id": executor_id,
        "phase": phase,
        "status": status,
        "session_id": request.session_id,
        "profile": request.profile or "default",
        "has_graph": request.graph is not None,
        "query_preview": short_text(request.query),
        "emitted_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
    if phase == "classify" and plan is not None:
        payload["plan_summary"] = _classification_plan_summary(plan)
        payload["intent"] = plan.intent
        payload["route"] = plan.effective_route
        payload["task"] = plan.effective_task
    _ws_send("vibecomfy.executor.phase", payload, client_id=client_id)


def _classification_plan_summary(plan: ClassifyDecision) -> str:
    summary = plan.plan_summary.strip()
    if summary:
        return summary
    return _route_behavior(plan).plan_summary


def run_executor(
    request: ExecutorRequest,
    *,
    client_id: str | None = None,
    classify_only: bool = False,
    additive: bool = False,
) -> ExecutorResult:
    """Execute the full classify → research → implement → reply pipeline.

    Parameters
    ----------
    request:
        The parsed executor request (query + optional graph/profile/etc.).
    classify_only:
        When True, run only the classify phase and return a diagnostic result
        without invoking research, implement, or reply model calls.  This is
        the honest dry-run seam: ``live=false`` is a product flag, but
        ``classify_only`` guarantees no subsequent phases run.
    additive:
        Headless-only caller hint that this is an additive restore (the caller
        removed a feature and now asks to re-add it).  Forwarded into the
        implement payload so the revise pipeline can relax ONLY the pre-edit
        "input graph has dangling/absent endpoints -> refuse to compound"
        precondition.  All post-edit validation and gates remain enforced.

    Returns
    -------
    ExecutorResult
        Always returns a result — failures are captured in the result
        shape, never raised as raw exceptions.
    """
    plan: ClassifyDecision | None = None
    research_result: AgentResearchResult | None = None
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
    attempt_token = begin_model_attempt_capture()

    def _build_report(
        *,
        plan: ClassifyDecision | None = None,
        research: AgentResearchResult | None = None,
        implementation: ImplementationResult | None = None,
        classification_status: str = "",
        fallback_model_attempts: tuple[dict[str, Any], ...] = (),
    ) -> Report:
        usage, cache_breakout_complete = snapshot_deepseek_usage_capture()
        model_attempts = snapshot_model_attempt_capture()
        if not model_attempts:
            model_attempts = coerce_model_attempts(fallback_model_attempts)
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
            model_attempts=model_attempts,
        )

    def _finish(result: ExecutorResult) -> ExecutorResult:
        end_deepseek_usage_capture(usage_token)
        end_model_attempt_capture(attempt_token)
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

    # ── Build session context (M3) ──────────────────────────────────────
    session_context: dict[str, Any] | None = None
    if request.session_id:
        session_context = _build_session_context(request)

    # ── Phase 1: classify (always via model) ─────────────────────────────
    try:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="classify",
            status="start",
            client_id=client_id,
        )
        with profiler_span(
            LOGGER,
            "executor.phase",
            **request_fields,
            phase="classify",
            **_spec_fields(classify_spec),
        ) as span:
            plan = _run_classify(
                request,
                classify_spec,
                session_context=session_context,
            )
            span.update(
                plan_research=plan.research,
                plan_implement=plan.implement,
                plan_reply=plan.reply,
                plan_route=plan.effective_route,
                plan_task=plan.effective_task,
            )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="classify",
            status="progress",
            plan=plan,
            client_id=client_id,
        )
        # The typed classifier output is authoritative for ambiguity.  Code
        # records clarify context but never rewrites the selected route.
        if plan.effective_route == "clarify":
            _save_clarification_context(
                request,
                plan,
                blocked_route=None,
                blocked_task=None,
            )
    except _ExecutorPhaseError as exc:
        # The classify phase raised — the report must NOT claim a model
        # decision (respond_only) that never happened. Record
        # classification_status=failed and leave the plan None so artifacts
        # reflect reality: failed classification carries no invented
        # route/task/intent.
        report = _build_report(
            classification_status="failed",
            fallback_model_attempts=exc.model_attempts,
        )
        return _finish(ExecutorResult.failure(
            kind=exc.failure_kind,
            stage=exc.stage,
            message=str(exc),
            report=report,
        ))

    # ── Classify-only dry-run exit ─────────────────────────────────────────
    if classify_only:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="research",
            status="skipped",
            client_id=client_id,
        )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="implement",
            status="skipped",
            client_id=client_id,
        )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="reply",
            status="skipped",
            client_id=client_id,
        )
        profiler_log(
            LOGGER,
            "executor.result",
            **request_fields,
            has_research=False,
            has_implementation=False,
            result_has_graph=False,
            reply_preview="",
            reason="classify_only",
        )
        report = _build_report(plan=plan)
        route = _canonical_route_for_plan(plan)
        task = plan.effective_task
        parts = [f"[dry-run] classified route: {route}"]
        if task:
            parts.append(f"task: {task}")
        if plan.plan_summary:
            parts.append(f"summary: {plan.plan_summary}")
        return _finish(ExecutorResult.success(
            report=report,
            graph=None,
            reply="\n".join(parts),
        ))

exec
/bin/zsh -lc "sed -n '1910,2240p' vibecomfy/executor/core.py
sed -n '930,1040p' vibecomfy/executor/contracts.py
sed -n '1820,1955p' vibecomfy/executor/contracts.py
sed -n '1,290p' vibecomfy/executor/profiles.py
sed -n '1,260p' vibecomfy/executor/agent_backend.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
        ))

    # ── Answer-only interaction enforcement (PR-B) ────────────────────────
    # interaction_mode="answer_only" is the explicit request/scenario contract
    # for diagnosis/advice turns: no graph edit may be produced, whatever the
    # classifier decided.  It is never inferred from apply=false — that flag
    # only declares whether a candidate is applied, not whether editing is
    # permitted.  Edit-capable routes are downgraded to agent-owned research
    # + semantic reply so the user still gets a grounded answer.
    if request.interaction_mode == "answer_only":
        plan = _answer_only_plan(plan)
        LOGGER.info(
            "executor: answer_only interaction → route=%s task=%s implement=%s",
            plan.effective_route,
            plan.effective_task,
            plan.implement,
        )

    # ── Phase 2: research (standalone replies only) ──────────────────────
    if _canonical_route_for_plan(plan) in {"research", "adapt"}:
        try:
            research_spec = _resolve_spec(request.profile, "research")
        except Exception as exc:
            failure = classify_failure("profile", exc)
            return _finish(ExecutorResult.failure(
                kind=failure.kind.value,
                stage="profile",
                message=failure.user_facing_message,
                report=_build_report(plan=plan),
            ))
        else:
            _emit_executor_phase_event(
                request,
                executor_id=executor_id,
                phase="research",
                status="start",
                client_id=client_id,
            )
            with profiler_span(
                LOGGER,
                "executor.phase",
                **request_fields,
                phase="research",
                **_spec_fields(research_spec),
            ) as span:
                research_result = _run_agent_owned_research(
                    request,
                    research_spec,
                    plan=plan,
                )
                span.update(
                    research_status=research_result.trace.status,
                    research_verdict=research_result.trace.final_verdict,
                    ledger_entries=len(research_result.ledger.entries),
                    summary_preview=short_text(research_result.summary),
                )
    else:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="research",
            status="skipped",
            client_id=client_id,
        )
        profiler_log(
            LOGGER,
            "executor.phase.skipped",
            **request_fields,
            phase="research",
            reason="plan_disabled",
        )

    # ── Phase 3: implement (optional) ────────────────────────────────────
    if _should_implement(plan):
        try:
            implement_spec = _resolve_spec(request.profile, "implement")
        except Exception as exc:
            # Profile missing implement spec → failure.
            failure = classify_failure("profile", exc)
            report = _build_report(plan=plan, research=research_result)
            return _finish(ExecutorResult.failure(
                kind=failure.kind.value,
                stage="profile",
                message=failure.user_facing_message,
                report=report,
            ))

        try:
            _emit_executor_phase_event(
                request,
                executor_id=executor_id,
                phase="implement",
                status="start",
                client_id=client_id,
            )
            with profiler_span(
                LOGGER,
                "executor.phase",
                **request_fields,
                phase="implement",
                **_spec_fields(implement_spec),
            ) as span:
                # Keep the panel alive during long model-backed implement turns:
                # a daemon thread re-emits phase="implement" status="working" every
                # ~15s until _run_implement returns. send_sync is thread-safe.
                heartbeat_stop = threading.Event()

                def _implement_heartbeat() -> None:
                    while not heartbeat_stop.wait(_IMPLEMENT_HEARTBEAT_INTERVAL_SECONDS):
                        _emit_executor_phase_event(
                            request,
                            executor_id=executor_id,
                            phase="implement",
                            status="working",
                            client_id=client_id,
                        )

                heartbeat_thread = threading.Thread(
                    target=_implement_heartbeat,
                    name="vibecomfy-executor-implement-heartbeat",
                    daemon=True,
                )
                try:
                    heartbeat_thread.start()
                    implementation_result = _run_implement(
                        request,
                        implement_spec,
                        plan=plan,
                        research_result=research_result,
                        client_id=client_id,
                        additive=additive,
                    )
                finally:
                    heartbeat_stop.set()
                    heartbeat_thread.join(timeout=2.0)
                span.update(
                    graph_returned=implementation_result.graph is not None,
                    message_preview=short_text(implementation_result.message),
                )
        except _ExecutorPhaseError as exc:
            failure_payload: dict[str, Any] = {
                "failure_kind": exc.failure_kind,
                "stage": exc.stage,
                "message": str(exc),
            }
            diagnostics_payload: dict[str, Any] | None = None
            envelope = exc.failure_envelope
            if envelope is not None:
                context_payload = getattr(envelope, "agent_failure_context", None)
                if isinstance(context_payload, Mapping):
                    failure_payload["agent_failure_context"] = context_payload
                    diagnostics_payload = {
                        key: value
                        for key, value in context_payload.items()
                        if key in {"issues", "diagnostics", "validation_errors"}
                    }
                    failure_payload.update(diagnostics_payload)
            report = _build_report(
                plan=plan,
                research=research_result,
                implementation=ImplementationResult(
                    message=str(exc),
                    diagnostics=diagnostics_payload,
                    failure=failure_payload,
                ),
            )
            return _finish(ExecutorResult.failure(
                kind=exc.failure_kind,
                stage=exc.stage,
                message=str(exc),
                report=report,
            ))

        route_behavior = _route_behavior(plan)
        if (
            route_behavior.can_produce_candidate
            and implementation_result.graph is not None
        ):
            effective_graph = implementation_result.graph
            result_graph = implementation_result.graph
        elif (
            _implementation_result_is_terminal_no_candidate(implementation_result)
            and _canonical_route_for_plan(plan) != "research"
        ):
            report = _build_report(
                plan=plan,
                research=research_result,
                implementation=implementation_result,
            )
            reply_text = implementation_result.message
            profiler_log(
                LOGGER,
                "executor.result",
                **request_fields,
                has_research=research_result is not None,
                has_implementation=True,
                result_has_graph=False,
                reply_preview=short_text(reply_text),
                reason="terminal_no_candidate",
            )
            return _finish(ExecutorResult.success(
                report=report,
                graph=None,
                reply=reply_text,
            ))
    else:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="implement",
            status="skipped",
            client_id=client_id,
        )
        profiler_log(
            LOGGER,
            "executor.phase.skipped",
            **request_fields,
            phase="implement",
            reason="plan_disabled",
        )

    # ── Phase 4: reply (always via model) ────────────────────────────────
    route_behavior = _route_behavior(plan)
    try:
        reply_spec = _resolve_spec(request.profile, "reply")
    except Exception as exc:
        failure = classify_failure("profile", exc)
        report = _build_report(
            plan=plan,
            research=research_result,
            implementation=implementation_result,
        )
        return _finish(ExecutorResult.failure(
            kind=failure.kind.value,
            stage="profile",
            message=failure.user_facing_message,
            report=report,
        ))
    try:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="reply",
            status="start",
            client_id=client_id,
        )
        with profiler_span(
            LOGGER,
            "executor.phase",
            **request_fields,
            phase="reply",
            **_spec_fields(reply_spec),
        ) as span:
            reply_text = _run_reply(
                request,
                reply_spec,
                plan=plan,
                effective_graph=effective_graph,
                research_result=research_result,
                implementation_result=implementation_result,
                graph_inspection=_render_graph_text(effective_graph)
                if route_behavior.reply_uses_graph_inspection
                else None,
            )
            span.update(reply_preview=short_text(reply_text))
    except _ExecutorPhaseError as exc:
        # Preserve durable candidate when reply narration fails.
        # Narration failure is presentation-only (SD1): the durable
        # edit work (candidate, gates, proofs, receipts, eligibility)
        # must not be discarded when only the reply surface fails.
        if (
            implementation_result is not None
            and implementation_result.durable_response is not None
            and result_graph is not None
        ):
            LOGGER.warning(
                "Reply narration failed after durable edit succeeded "
                "(stage=%s, kind=%s); preserving implementation with "
                "deterministic fallback narration.",
                exc.stage,
                exc.failure_kind,
            )
            report = _build_report(
                plan=plan,
                research=research_result,
                implementation=implementation_result,
                fallback_model_attempts=exc.model_attempts,
            )
            fallback_reply = (
                implementation_result.message
                or "Edit completed. The candidate is ready to review."
            )
            return _finish(ExecutorResult.success(
                report=report,
                graph=result_graph,
                reply=fallback_reply,
            ))

        report = _build_report(
            plan=plan,
            research=research_result,
            implementation=implementation_result,
            fallback_model_attempts=exc.model_attempts,
        )
        return _finish(ExecutorResult.failure(
            kind=exc.failure_kind,
            stage=exc.stage,
            message=str(exc),
            report=report,
        ))

    # ── Guard: inspect must never return an edited graph ─────────────────
    if route_behavior.clears_result_graph:
        result_graph = None

    # ── Assemble success result ──────────────────────────────────────────
    report = _build_report(
        plan=plan,
        research=research_result,
        implementation=implementation_result,
    )
    profiler_log(
        LOGGER,
        "executor.result",
        **request_fields,
        has_research=research_result is not None,
        has_implementation=implementation_result is not None,
        result_has_graph=result_graph is not None,
        reply_preview=short_text(reply_text),
    )
    return _finish(ExecutorResult.success(


def _derive_task(*, research: bool, implement: bool, intent: str) -> str:
    """Derive a normalized task label from legacy fields.

    Returns ``""`` when the mapping is ambiguous.
    """
    if implement and research:
        return "research_precedent"
    if implement and not research:
        return "edit_graph"
    if research and not implement:
        return "research_nodes"
    if not research and not implement:
        if intent == "explain_graph":
            return "inspect_graph"
        if intent == "respond":
            return "respond"
        return "respond"
    return ""


# ── request ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecutorRequest:
    """Public input shape for ``POST /vibecomfy/agent-executor``.

    ``query`` is the only required field.  ``graph`` is the optional current
    canvas (the executor forwards it to ``handle_agent_edit`` through a
    ``{task, query, graph, session_id}`` payload when an implementation turn is
    indicated).
    """

    query: str
    graph: dict[str, Any] | None = None
    workflow_id: str | None = None
    session_id: str | None = None
    profile: str | None = None
    idempotency_key: str | None = None
    client_graph_hash: str | None = None
    client_structural_graph_hash: str | None = None
    client_live_canvas_token: str | None = None
    expected_baseline_graph_hash: str | None = None
    expected_baseline_graph_hash_present: bool = False
    # Frontend "Author Uninstalled Node Packs" setting (default ON at the provider).
    # None = unset → provider applies its env/default. Threaded through so the
    # user-facing toggle actually controls on-demand schema resolution.
    on_demand_schemas: bool | None = None
    # Explicit interaction contract for diagnosis/advice turns.  "answer_only"
    # declares that this interaction must never produce a graph edit — the
    # executor routes to deterministic research + semantic reply regardless of
    # what the classifier decided.  It is deliberately NOT inferred from
    # ``apply``: that flag only says whether a candidate is applied, not
    # whether editing is permitted.  None = ordinary interaction.
    interaction_mode: str | None = None
    # Batch-REPL per-request turn budget (PR-D).  Integer 1..MAX_BATCHES_LIMIT;
    # None = default (DEFAULT_MAX_BATCHES).  Forwarded into the implement
    # payload as ``max_batches`` and enforced again at the edit entrypoint.
    max_batches: int | None = None

    def __post_init__(self) -> None:
        # Preserve the distinction between an explicit null from a current
        # pristine client and omission by a legacy client.
        if self.expected_baseline_graph_hash is not None:
            object.__setattr__(self, "expected_baseline_graph_hash_present", True)
        if self.max_batches is not None:
            object.__setattr__(
                self,
                "max_batches",
                coerce_max_batches(self.max_batches, field_name="max_batches"),
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": self.query}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.workflow_id is not None:
            payload["workflow_id"] = self.workflow_id
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.profile is not None:
            payload["profile"] = self.profile
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        if self.client_graph_hash is not None:
            payload["client_graph_hash"] = self.client_graph_hash
        if self.client_structural_graph_hash is not None:
            payload["client_structural_graph_hash"] = self.client_structural_graph_hash
        if self.client_live_canvas_token is not None:
            payload["client_live_canvas_token"] = self.client_live_canvas_token
        if self.expected_baseline_graph_hash_present:
            payload["expected_baseline_graph_hash"] = self.expected_baseline_graph_hash
        if self.on_demand_schemas is not None:
            payload["on_demand_schemas"] = self.on_demand_schemas
        if self.interaction_mode is not None:
            payload["interaction_mode"] = self.interaction_mode
        if self.max_batches is not None:
            payload["max_batches"] = self.max_batches
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExecutorRequest":
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("ExecutorRequest requires a non-empty string `query`.")
        graph = payload.get("graph")
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("ExecutorRequest `graph` must be a dict or null.")
        workflow_id = payload.get("workflow_id")
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

    ``research`` carries the H01 :class:`~vibecomfy.executor.core.AgentResearchResult`
    (F01 evidence pack + C5 decision memo).  Legacy research-result payloads
    (``precedent_packet`` / ``adaptation_plan`` / ``precedent_slices``) were
    removed by the agent-judgment rework (D02) and are rejected explicitly
    instead of being silently rewritten.
    """

    plan: ClassifyDecision | None = None
    research: "AgentResearchResult | None" = None
    implementation: ImplementationResult | None = None
    deepseek_usage: dict[str, Any] = field(default_factory=dict)
    deepseek_est_cost_usd: float | None = None
    deepseek_cost_basis: str | None = None
    # Truthful classification lifecycle signal: "failed" means classify raised
    # (the plan is then None — no invented respond_only placeholder). Empty
    # string means the signal was not recorded (legacy paths).
    classification_status: str = ""
    # Canonical per-call evidence for every successful and failed model attempt
    # observed across classify, implement/batch, and reply.
    model_attempts: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.research is not None and not callable(getattr(self.research, "to_dict", None)):
            raise TypeError(
                "Report.research must be an AgentResearchResult (or None). "
                "Legacy research-result payloads were removed (D02); serialize "
                "the F01 evidence pack / C5 decision memo instead. "
                f"got {type(self.research).__name__}"
            )
        object.__setattr__(
            self,
            "deepseek_usage",
            MappingProxyType({
                str(k): _freeze_jsonish(v)
                for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
            }),
        )
        object.__setattr__(
            self,
            "model_attempts",
            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
        )

    @property
    def model_response(self) -> dict[str, Any] | None:
        """Compatibility view derived solely from canonical ``model_attempts``."""
        if not self.model_attempts:
            return None
        return {
            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
        }

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
        inner["model_attempts"] = [
            _thaw_jsonish(item) for item in self.model_attempts
        ]
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
"""Profile loading and resolution for the embedded VibeComfy executor.

Loads per-phase agent specs from Arnold-owned TOML profiles.  Each profile
maps the canonical stages (``classify``, ``research``, ``implement``,
``reply``) to an :class:`AgentSpecShape` with ``agent``, ``model``, and
``effort`` fields.

The primary source is ``arnold.pipelines.vibecomfy_executor.profiles``
loaded via ``importlib.resources``.  For testing, callers can override
the profile directory via ``set_profile_override_dir()``.

Spec-to-provider mapping (executed by ``agent_backend.py``, not here):
``AgentSpecShape.agent`` → VibeComfy provider ``route`` kwarg,
``AgentSpecShape.model`` → VibeComfy provider ``model`` kwarg,
``effort`` → may be ignored if the provider function does not accept it.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ── canonical stages ─────────────────────────────────────────────────────────

DECLARED_STAGES: frozenset[str] = frozenset({"classify", "research", "implement", "reply"})
_KNOWN_AGENTS: frozenset[str] = frozenset(
    {"hermes", "openrouter", "codex", "claude", "shannon"}
)

# ── AgentSpecShape ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentSpecShape:
    """Resolved agent specification for a single executor phase.

    ``agent`` maps to the VibeComfy provider ``route`` kwarg.
    ``model`` maps to the VibeComfy provider ``model`` kwarg.
    ``effort`` is a coarse hint (``"low"`` / ``"medium"`` / ``"high"``).
    """

    agent: str
    model: str
    effort: str = "low"

    def __post_init__(self) -> None:
        if self.effort not in ("low", "medium", "high"):
            object.__setattr__(self, "effort", "low")


# ── test path override ───────────────────────────────────────────────────────

# Module-level override: when set to a non-None Path, profile loading uses
# this directory instead of attempting importlib.resources on the Arnold
# package.  Call ``set_profile_override_dir(None)`` to restore the default.
_profile_override_dir: Path | None = None


def set_profile_override_dir(path: Path | str | None) -> None:
    """Override the directory from which profile TOMLs are loaded.

    Set to a :class:`Path` to load from a local directory (useful for testing).
    Set to ``None`` to restore the default Arnold package-resource behaviour.
    """
    global _profile_override_dir
    if path is None:
        _profile_override_dir = None
    else:
        _profile_override_dir = Path(path)


# ── profile directory resolution ─────────────────────────────────────────────


def _profile_dir() -> Path:
    """Return the resolved profile directory.

    Uses the test override when set; otherwise loads the profile TOMLs
    shipped inside ``vibecomfy.executor.profile_data`` so that external
    installs work without an Arnold checkout.
    """
    if _profile_override_dir is not None:
        return _profile_override_dir

    # Import here so the file is still importable even when Arnold is absent.
    from importlib import resources

    pkg_files = resources.files("vibecomfy.executor.profile_data")
    path = Path(str(pkg_files))
    if not path.is_dir() or not any(path.glob("*.toml")):
        raise FileNotFoundError(
            "Cannot locate executor profile directory. "
            "Install VibeComfy with the [agent] extra, or call "
            "set_profile_override_dir() to point to a local profile directory."
        )
    return path


# ── validation ───────────────────────────────────────────────────────────────


_EFFORT_TOKENS: frozenset[str] = frozenset({"low", "medium", "high"})


def _validate_stages(stage_map: dict[str, Any]) -> None:
    """Ensure *stage_map* contains exactly the declared stages."""
    stages = frozenset(stage_map.keys())
    missing = DECLARED_STAGES - stages
    extra = stages - DECLARED_STAGES
    if missing:
        raise ValueError(
            f"Profile is missing required stages: {sorted(missing)}"
        )
    if extra:
        raise ValueError(
            f"Profile contains unknown stages: {sorted(extra)}"
        )


def _parse_compact_spec(spec: str, *, stage: str) -> AgentSpecShape:
    """Parse a compact ``agent:model[:effort]`` string spec.

    Model identifiers may themselves contain colons (e.g.
    ``"hermes:openrouter:deepseek/deepseek-v4-pro"``), so effort is only extracted
    when the final colon-separated segment is a known effort token.
    """
    candidate = spec.strip()
    parts = candidate.split(":")
    if any(part == "" for part in parts):
        raise ValueError(
            f"Stage '{stage}' compact spec {spec!r} contains an empty segment."
        )

    agent = parts[0]
    if agent not in _KNOWN_AGENTS:
        raise ValueError(
            f"Stage '{stage}' agent '{agent}' is not a known agent. "
            f"Known agents: {sorted(_KNOWN_AGENTS)}"
        )

    if len(parts) == 1:
        raise ValueError(
            f"Stage '{stage}' compact spec {spec!r} must include a model."
        )

    if parts[-1] in _EFFORT_TOKENS and len(parts) >= 3:
        effort = parts[-1]
        model = ":".join(parts[1:-1])
    else:
        effort = "low"
        model = ":".join(parts[1:])

    if not model.strip():
        raise ValueError(
            f"Stage '{stage}' compact spec {spec!r} has an empty model."
        )

    return AgentSpecShape(agent=agent, model=model, effort=effort)


def _parse_spec(raw: Any, *, stage: str) -> AgentSpecShape:
    """Parse a single stage spec into an :class:`AgentSpecShape`.

    Accepts either the compact string form ``agent:model[:effort]`` or the
    legacy dict form with ``agent``, ``model`` and optional ``effort`` keys.
    """
    if isinstance(raw, str):
        return _parse_compact_spec(raw, stage=stage)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Stage '{stage}' spec must be a string or dict, got {type(raw).__name__}."
        )

    # --- agent ---
    agent = raw.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        raise ValueError(
            f"Stage '{stage}' must specify a non-empty string 'agent'."
        )
    agent = agent.strip()
    if agent not in _KNOWN_AGENTS:
        raise ValueError(
            f"Stage '{stage}' agent '{agent}' is not a known agent. "
            f"Known agents: {sorted(_KNOWN_AGENTS)}"
        )

    # --- model ---
    model = raw.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            f"Stage '{stage}' must specify a non-empty string 'model'."
        )
    model = model.strip()

    # --- effort ---
    effort = raw.get("effort", "low")
    if not isinstance(effort, str) or effort not in _EFFORT_TOKENS:
        effort = "low"

    return AgentSpecShape(agent=agent, model=model, effort=effort)


# ── public API ───────────────────────────────────────────────────────────────


def load_profile(name: str) -> dict[str, AgentSpecShape]:
    """Load a single named profile.

    Reads ``{name}.toml`` from the profile directory and parses each
    declared stage into an :class:`AgentSpecShape`.

    Returns a mapping from stage name (``"classify"``, ``"research"``,
    ``"implement"``, ``"reply"``) to its resolved spec.
    """
    toml_path = _profile_dir() / f"{name}.toml"
    if not toml_path.is_file():
        raise FileNotFoundError(f"Profile '{name}' not found at {toml_path}")

    raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    # Allow profiles to nest their stages under a top-level key.  Two common
    # conventions exist in the wild:
    #   1. Stages directly at top level.
    #   2. Stages under [profiles.{name}] (Arnold-style packaging).
    #   3. Stages under a single wrapper key such as [default] or [profile].
    has_stages_directly = bool(DECLARED_STAGES & frozenset(raw.keys()))
    if not has_stages_directly:
        # Convention 2: {profiles = {name = {classify = ...}}}
        if (
            "profiles" in raw
            and isinstance(raw["profiles"], dict)
            and isinstance(raw["profiles"].get(name), dict)
        ):
            raw = raw["profiles"][name]
        else:
            # Convention 3: single wrapper key containing the stage dict.
            for value in raw.values():
                if isinstance(value, dict) and DECLARED_STAGES & frozenset(value.keys()):
                    raw = value
                    break

    _validate_stages(raw)

    return {
        stage: _parse_spec(raw[stage], stage=stage) for stage in DECLARED_STAGES
    }


def load_all_profiles() -> dict[str, dict[str, AgentSpecShape]]:
    """Load every ``*.toml`` profile from the profile directory.

    Returns a mapping from profile name (stem) to its resolved stage map.
    """
    profiles: dict[str, dict[str, AgentSpecShape]] = {}
    for toml_path in sorted(_profile_dir().glob("*.toml")):
        name = toml_path.stem
        profiles[name] = load_profile(name)
    return profiles


__all__ = [
    "AgentSpecShape",
    "DECLARED_STAGES",
    "load_all_profiles",
    "load_profile",
    "set_profile_override_dir",
]
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
import json
from typing import Any

from vibecomfy.executor.profiler import new_profile_id, profiler_span, short_text

from .prompts import (
    build_classify_messages,
    build_reply_messages,
    parse_classify_response,
    parse_reply_response,
)
from .contracts import (
    ClassifyDecision,
    ModelAttemptEvidence,
    coerce_model_attempts,
    redact_model_preview,
)

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
    return redact_model_preview(text, limit=limit)


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
        if result is not None and getattr(exc, "model_attempts", None) is None:
            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
        if raw is not None and getattr(exc, "raw_response_preview", None) is None:
            exc.raw_response_preview = _preview_raw(raw)  # type: ignore[attr-defined]
        for name, value in (("model", model), ("phase", phase)):
            if getattr(exc, name, None) is None:
                setattr(exc, name, value)
        if getattr(exc, "requested_model", None) is None:
            exc.requested_model = model  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - evidence attachment is best-effort
        pass


def _downstream_failure_type(raw: str | None) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "empty_response"
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```")
        stripped = stripped.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return "malformed_json" if "{" in stripped else "non_json_content"
    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"


def _record_result_attempts(result: dict[str, Any]) -> None:
    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts

    record_model_attempts(result.get("model_attempts"))


def _mark_last_attempt_failed(
    result: dict[str, Any], *, raw: str | None, failure_type: str
) -> None:
    attempts = list(coerce_model_attempts(result.get("model_attempts")))
    if not attempts:
        return
    latest = dict(attempts[-1])
    latest.update({
        "outcome": "failure",
        "failure_type": failure_type,
        "raw_response_preview": raw,
    })
    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
    attempts[-1] = revised
    result["model_attempts"] = attempts
    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt

    replace_last_model_attempt(revised)


def run_classify_turn(
    query: str,
    *,
    route: str,
    model: str,
    effort: str | None = None,
    has_graph: bool = False,
    graph_summary: str | None = None,
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
        The user's natural-language request.
    route:
        Provider route name (resolved from the profile's ``agent`` field).
    model:
        Model identifier (resolved from the profile's ``model`` field).
    has_graph:
        Whether a ComfyUI canvas graph is attached to the request.
    graph_summary:
        Optional compact summary of the attached graph (≤ 200 chars).
    messages:
        Optional pre-built messages list.  When provided, skips the default
        message building and uses this list directly.
    """
    if messages is None:
        messages = build_classify_messages(
            query,
            has_graph=has_graph,
            graph_summary=graph_summary,
        )
    model_turn_id = new_profile_id("model")
    with profiler_span(
        LOGGER,
        "executor.model_turn",
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
            _mark_last_attempt_failed(
                result,
                raw=raw,
                failure_type=_downstream_failure_type(raw),
            )
            _attach_model_turn_evidence(
                exc,
                result,
                model=model,
                phase="classify",
                raw=raw,
            )
            raise
        _record_result_attempts(result)
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
    research_memo: dict[str, Any] | None = None,
    research_ledger: dict[str, Any] | None = None,
    research_summary: str | None = None,
    research_sources: tuple[dict[str, Any], ...] | None = None,
    research_warnings: tuple[str, ...] | None = None,
    research_precedent_slices: tuple[dict[str, Any], ...] | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
    graph_inspection: str | None = None,
    adaptation_plan: dict[str, Any] | None = None,
    effective_route: str | None = None,
    effective_task: str | None = None,
    candidate_present: bool = False,
    interaction_mode: str | None = None,
    research_attempt: str | None = None,
) -> str:
    """Run a single reply model turn through the provider seam.

    Builds reply-specific messages via :func:`build_reply_messages`,
    dispatches through :func:`run_model_turn` with
    ``response_contract="text"`` (the reply phase accepts plain prose; a
    ``{"reply": ...}`` JSON object is still parsed for backward
    compatibility), and parses the result with
    :func:`parse_reply_response`.

    Parameters
    ----------
    query:

codex
The main seam is confirmed: the full path is centralized after classify and `answer_only`, while profiles currently require exactly four stages. I’m now tracing the actual provider/session and edit transaction primitives so the plan does not invent a parallel state store or a second edit language.
exec
/bin/zsh -lc "rg --files tests/live_agentic_harness tests | rg 'scenario|ledger|law|executor|profile|prompt|diff|comparison|session' | sed -n '1,320p'
rg -n \"class .*Session|session_id|conversation_id|thread_id|run_model_turn|continu|tool_calls|tool loop|while .*tool|apply_batch|def done|accepted.*delta|delta_id|claim_ref|reply_lens|tool ledger\" vibecomfy/comfy_nodes/agent vibecomfy/executor vibecomfy/porting/edit tests | sed -n '1,420p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
tests/test_agent_obligation_ledger.py
tests/test_demo_scenarios_routes.py
tests/test_executor_layout_hints.py
tests/test_session_cli.py
tests/test_headless_harness_scenarios_contract.py
tests/test_runtime_session_run_untracked.py
tests/test_routes_session_sanitization.py
tests/test_porting_edit_session.py
tests/test_executor_lookup_tools.py
tests/test_executor_stage_contracts.py
tests/test_executor_hivemind_messages.py
tests/test_agent_executor_response.py
tests/test_memory_profile.py
tests/test_runtime_session_validation.py
tests/test_porting_edit_session_harness.py
tests/live_agentic_harness/scenfails41/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails41/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails41/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails41/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenario_manifest.json
tests/live_agentic_harness/scenfails41/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails41/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails41/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails41/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenario_manifest.json
tests/test_agent_edit_compatibility_ledger.py
tests/test_comfy_nodes_agent_session.py
tests/live_agentic_harness/scenfails32/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails32/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails32/image-animatediff-video-generation-with-vae-d20410.json
tests/test_executor_hivemind_tools.py
tests/structural_harness/scenarios/two-stage-chain-both-ran.yaml
tests/structural_harness/scenarios/audio_song_escape_hatch_positive.yaml
tests/structural_harness/scenarios/embedded-run-no-gpu.yaml
tests/structural_harness/scenarios/invalid-emitted-socket.yaml
tests/structural_harness/scenarios/empty-graph-authoring.yaml
tests/structural_harness/scenarios/hivemind-rate-limiting.yaml
tests/structural_harness/scenarios/add-save-node-finalize.yaml
tests/structural_harness/scenarios/run_wan_t2v_ready_cli.yaml
tests/structural_harness/scenarios/hotshot-16-frames-agent-edit.yaml
tests/structural_harness/scenarios/image_edit_unwired_limit.yaml
tests/structural_harness/scenarios/image_to_video_chain_recovery.yaml
tests/structural_harness/scenarios/route-intent-map.yaml
tests/structural_harness/scenarios/revise-without-forced-research.yaml
tests/structural_harness/scenarios/headless-ambiguity-needs_input.yaml
tests/structural_harness/scenarios/explain-simple-workflow.yaml
tests/structural_harness/scenarios/audio_t2a_unwired_limit.yaml
tests/structural_harness/scenarios/schema-drift-approved-normalization.yaml
tests/structural_harness/scenarios/ltx-i2v-swap-tiled-vae-decode.yaml
tests/structural_harness/scenarios/impossible_8k_free_tier_video.yaml
tests/structural_harness/scenarios/chaining_positive.yaml
tests/structural_harness/scenarios/ltx-i2v-audio-research-execute.yaml
tests/structural_harness/scenarios/wan-t2v-append-frame-interpolation.yaml
tests/structural_harness/scenarios/add-depth-controlnet-image.yaml
tests/structural_harness/scenarios/wan-t2v-splice-modelpatch-before-loras.yaml
tests/structural_harness/scenarios/server-runtime-dead-url.yaml
tests/structural_harness/scenarios/verify-edit-scoped.yaml
tests/structural_harness/scenarios/distilled-faster-research-route.yaml
tests/structural_harness/scenarios/runpod-list-before-terminate.yaml
tests/structural_harness/scenarios/wan22-stack-highlow-noise-lora.yaml
tests/structural_harness/scenarios/readiness-go-no-go.yaml
tests/structural_harness/scenarios/reorganise-large-messy-ltx-workflow.yaml
tests/structural_harness/scenarios/research-only-decision-memo.yaml
tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml
tests/structural_harness/scenarios/controlnet-video-noop.yaml
tests/structural_harness/scenarios/diagnose-broken-graph.yaml
tests/test_executor_contracts.py
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json
tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json
tests/live_agentic_harness/scenarios/image-generates-a-2x2-seed-variation.json
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json
tests/live_agentic_harness/scenarios/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json
tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json
tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json
tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json
tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676.json
tests/live_agentic_harness/scenarios/audio-tts-narration-using-indextts-2.json
tests/structural_harness/scenarios/queue-refusal-valid-runtime-probe.yaml
tests/structural_harness/scenarios/generate_image_canonical_op.yaml
tests/structural_harness/scenarios/explore-hotshot-xl-workflow.yaml
tests/structural_harness/scenarios/reorganise-large-messy-batch.yaml
tests/structural_harness/scenarios/trace-resolution-source.yaml
tests/structural_harness/scenarios/fork_z_image_copy_to_recipe.yaml
tests/structural_harness/scenarios/wan22-i2v-second-pass-refine.yaml
tests/live_agentic_harness/scenarios/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json
tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json
tests/live_agentic_harness/scenarios/image-background-removal-and-grid-composition-54a681.json
tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
tests/live_agentic_harness/scenarios/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with-2.json
tests/live_agentic_harness/scenarios/3d-3d-model-load-edit-and-export-workflow-d66a66.json
tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json
tests/live_agentic_harness/scenarios/multi-crops-face-previews-it-sets.json
tests/live_agentic_harness/scenarios/audio-audio-processing-with-chatterbox-tts-and-vc-b55994.json
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json
tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json
tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json
tests/live_agentic_harness/scenarios/multi-image-to-video-with-upscaling-and-color-matchi-359848.json
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json
tests/live_agentic_harness/scenarios/image-two-stage-qwen-image-generation.json
tests/live_agentic_harness/scenarios/video-video-generation-from-resized-image.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
tests/live_agentic_harness/scenarios/image-flux-image-inpainting-and-compositing-with-con-00444a.json
tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json
tests/live_agentic_harness/scenarios/image-image-editing-with-qwen-image.json
tests/live_agentic_harness/scenarios/multi-video-based-character-replacement-using.json
tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json
tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json
tests/live_agentic_harness/scenarios/speed-distillation-research.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json
tests/live_agentic_harness/scenarios/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json
tests/live_agentic_harness/scenarios/image-style-transfer-using-ip-adapter.json
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenarios/3d-generates-a-3d-mesh-from.json
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json
tests/live_agentic_harness/scenarios/multi-wan-vace-video-retargeting-driven.json
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json
tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json
tests/live_agentic_harness/scenarios/3d-converts-image-to-3d-model.json
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
tests/live_agentic_harness/scenarios/video-generates-a-video-from-a.json
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json
tests/live_agentic_harness/scenarios/audio-transcribes-audio-appends-text-regenerates.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-workflow-2a31ec.json
tests/live_agentic_harness/scenarios/multi-image-to-video-with-llm.json
tests/live_agentic_harness/scenarios/video-video-frame-by-frame-style.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-and-processing-workfl-1b1360.json
tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json
tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json
tests/live_agentic_harness/scenarios/image-sdxl-txt2img-cat-in-spacesuit.json
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json
tests/live_agentic_harness/scenarios/video-ltx-video-upscaling-and-enhancement.json
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-webp-and-png-output-bd3afb.json
tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-controlnet-and-dwpreproces-49d057.json
tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json
tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json
tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json
tests/live_agentic_harness/scenarios/image-generates-a-2x2-seed-variation.json
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json
tests/live_agentic_harness/scenarios/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json
tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json
tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json
tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json
tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676.json
tests/live_agentic_harness/scenarios/audio-tts-narration-using-indextts-2.json
tests/live_agentic_harness/scenarios/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json
tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json
tests/live_agentic_harness/scenarios/image-background-removal-and-grid-composition-54a681.json
tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
tests/live_agentic_harness/scenarios/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with-2.json
tests/live_agentic_harness/scenarios/3d-3d-model-load-edit-and-export-workflow-d66a66.json
tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json
tests/live_agentic_harness/scenarios/multi-crops-face-previews-it-sets.json
tests/live_agentic_harness/scenarios/audio-audio-processing-with-chatterbox-tts-and-vc-b55994.json
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json
tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json
tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json
tests/live_agentic_harness/scenarios/multi-image-to-video-with-upscaling-and-color-matchi-359848.json
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json
tests/live_agentic_harness/scenarios/image-two-stage-qwen-image-generation.json
tests/live_agentic_harness/scenarios/video-video-generation-from-resized-image.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
tests/live_agentic_harness/scenarios/image-flux-image-inpainting-and-compositing-with-con-00444a.json
tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json
tests/live_agentic_harness/scenarios/image-image-editing-with-qwen-image.json
tests/live_agentic_harness/scenarios/multi-video-based-character-replacement-using.json
tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json
tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json
tests/live_agentic_harness/scenarios/speed-distillation-research.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json
tests/live_agentic_harness/scenarios/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json
tests/live_agentic_harness/scenarios/image-style-transfer-using-ip-adapter.json
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenarios/3d-generates-a-3d-mesh-from.json
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json
tests/live_agentic_harness/scenarios/multi-wan-vace-video-retargeting-driven.json
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json
tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json
tests/live_agentic_harness/scenarios/3d-converts-image-to-3d-model.json
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
tests/live_agentic_harness/scenarios/video-generates-a-video-from-a.json
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json
tests/live_agentic_harness/scenarios/audio-transcribes-audio-appends-text-regenerates.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-workflow-2a31ec.json
tests/live_agentic_harness/scenarios/multi-image-to-video-with-llm.json
tests/live_agentic_harness/scenarios/video-video-frame-by-frame-style.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-and-processing-workfl-1b1360.json
tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json
tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json
tests/live_agentic_harness/scenarios/image-sdxl-txt2img-cat-in-spacesuit.json
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json
tests/live_agentic_harness/scenarios/video-ltx-video-upscaling-and-enhancement.json
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-webp-and-png-output-bd3afb.json
tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-controlnet-and-dwpreproces-49d057.json
tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json
tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json
tests/live_agentic_harness/scen19/image-animatediff-video-from-images-with.json
tests/test_build_demo_scenario_assets.py
tests/_runtime_session_helpers.py
tests/live_agentic_harness/scenario_manifest.py
tests/live_agentic_harness/scenfails57/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
tests/live_agentic_harness/scenfails57/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails57/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails57/multi-animatediff-video-generation-with-controlnet-a7e2af.json
tests/live_agentic_harness/scenfails57/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails57/video-animatediff-video-with-controlnet-and-depth-89b02a.json
tests/live_agentic_harness/scenfails57/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenfails57/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
tests/live_agentic_harness/scenario_manifest.py
tests/browser/scoped_session_persistence.test.mjs
tests/browser/preview_diff_core.test.mjs
tests/test_executor_classify_only.py
tests/live_agentic_harness/scenfails32/image-animatediff-video-generation-with-vae-d20410.json
tests/test_executor_web_tools.py
tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails32/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails32/image-image-comparison-and-enhancement-with-florence-007018.json
tests/test_executor_edit_suggestion_tools.py
tests/test_agent_executor_routes.py
tests/test_profile_smoke_report.py
tests/test_ir_laws.py
tests/test_executor_flows.py
tests/test_runtime_session_server.py
tests/test_runtime_session_embedded.py
tests/live_agentic_harness/scen19/image-animatediff-video-from-images-with.json
tests/test_executor_profiles.py
tests/test_agent_executor_durable.py
tests/test_runtime_session_config.py
tests/live_agentic_harness/scenfails57/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
tests/live_agentic_harness/scenfails57/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails57/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails57/multi-animatediff-video-generation-with-controlnet-a7e2af.json
tests/live_agentic_harness/scenfails57/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails57/video-animatediff-video-with-controlnet-and-depth-89b02a.json
tests/live_agentic_harness/scenfails57/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenfails57/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
tests/intent/test_render_diff_structural.py
vibecomfy/executor/graph_inspection.py:262:                continue
vibecomfy/executor/graph_inspection.py:391:            continue
vibecomfy/executor/graph_inspection.py:433:            continue
vibecomfy/executor/graph_inspection.py:458:            continue
vibecomfy/executor/graph_inspection.py:466:            continue
vibecomfy/executor/graph_inspection.py:472:                continue
vibecomfy/porting/edit/lint.py:672:            continue
vibecomfy/porting/edit/lint.py:1114:                    continue
vibecomfy/porting/edit/lint.py:1237:            continue
vibecomfy/porting/edit/lint.py:1281:            continue
vibecomfy/comfy_nodes/agent/routes.py:57:    normalize_session_id,
vibecomfy/comfy_nodes/agent/routes.py:327:            continue
vibecomfy/comfy_nodes/agent/routes.py:330:            continue
vibecomfy/comfy_nodes/agent/routes.py:382:            "session_id": response.get("session_id") or f"demo-{scenario_id}",
vibecomfy/comfy_nodes/agent/routes.py:425:        session_id = response_json.get("session_id") or f"demo-{scenario_id}"
vibecomfy/comfy_nodes/agent/routes.py:435:        session_id = f"demo-{scenario_id}"
vibecomfy/comfy_nodes/agent/routes.py:451:        "session_id": session_id,
vibecomfy/comfy_nodes/agent/routes.py:591:            continue
vibecomfy/comfy_nodes/agent/routes.py:607:            continue
vibecomfy/comfy_nodes/agent/routes.py:641:    session_id = response_json.get("session_id") or f"replay-{run_id}-{test_id}"
vibecomfy/comfy_nodes/agent/routes.py:658:        "session_id": session_id if isinstance(session_id, str) else f"replay-{run_id}-{test_id}",
vibecomfy/comfy_nodes/agent/routes.py:778:            continue
vibecomfy/comfy_nodes/agent/routes.py:1103:    # ── T2: Normalise session_id before it reaches ExecutorRequest ────────
vibecomfy/comfy_nodes/agent/routes.py:1104:    # ExecutorRequest.from_payload() accepts a raw session_id string, but the
vibecomfy/comfy_nodes/agent/routes.py:1108:    raw_session_id = safe_payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1109:    if isinstance(raw_session_id, str):
vibecomfy/comfy_nodes/agent/routes.py:1110:        safe_payload["session_id"] = normalize_session_id(raw_session_id)
vibecomfy/comfy_nodes/agent/routes.py:1111:    elif "session_id" in safe_payload:
vibecomfy/comfy_nodes/agent/routes.py:1113:        del safe_payload["session_id"]
vibecomfy/comfy_nodes/agent/routes.py:1190:    raw_session_id = payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1192:    # ── T2: Normalise session_id before it reaches read_session_chat.
vibecomfy/comfy_nodes/agent/routes.py:1193:    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else None
vibecomfy/comfy_nodes/agent/routes.py:1197:            session_id,
vibecomfy/comfy_nodes/agent/routes.py:1329:def _audit_path_for_action(session_root: Path, session_id: str, turn_id: str, action: str) -> Path:
vibecomfy/comfy_nodes/agent/routes.py:1330:    return session_dir_for(session_root, session_id) / "turns" / turn_id / f"{action}_audit" / "audit.json"
vibecomfy/comfy_nodes/agent/routes.py:1340:    session_id = response.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1342:    if not isinstance(session_id, str) or not isinstance(turn_id, str):
vibecomfy/comfy_nodes/agent/routes.py:1344:    audit_path = _audit_path_for_action(session_root, session_id, turn_id, action)
vibecomfy/comfy_nodes/agent/routes.py:1349:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:1390:    raw_session_id = payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1391:    # ── T2: Normalise session_id through the authoritative normaliser before
vibecomfy/comfy_nodes/agent/routes.py:1393:    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else ""
vibecomfy/comfy_nodes/agent/routes.py:1398:            session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:1407:            response_writer=_json_response_writer(root / session_id / "turns" / safe_turn_id / "accept_response.json")
vibecomfy/comfy_nodes/agent/routes.py:1408:            if session_id
vibecomfy/comfy_nodes/agent/routes.py:1457:    raw_session_id = payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1458:    # ── T2: Normalise session_id through the authoritative normaliser before
vibecomfy/comfy_nodes/agent/routes.py:1460:    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else ""
vibecomfy/comfy_nodes/agent/routes.py:1474:            session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:1482:                root / session_id / "turns" / safe_turn_id / reject_response_name
vibecomfy/comfy_nodes/agent/routes.py:1484:            if session_id
vibecomfy/comfy_nodes/agent/routes.py:1522:    raw_session_id = payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1523:    # ── T2: Normalise session_id before it reaches durable rebaseline_session.
vibecomfy/comfy_nodes/agent/routes.py:1524:    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else ""
vibecomfy/comfy_nodes/agent/routes.py:1528:            session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:1558:    raw_session_id = payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1559:    if not isinstance(raw_session_id, str) or not raw_session_id.strip():
vibecomfy/comfy_nodes/agent/routes.py:1565:                agent_failure_context={"explanation": "session_id is required."},
vibecomfy/comfy_nodes/agent/routes.py:1588:    # ── T2: Normalise session_id and turn_id before path construction.
vibecomfy/comfy_nodes/agent/routes.py:1589:    session_id = normalize_session_id(raw_session_id)
vibecomfy/comfy_nodes/agent/routes.py:1591:    audit_path = _audit_path_for_action(_session_root_path(session_root), session_id, turn_id, action)
vibecomfy/comfy_nodes/agent/routes.py:1600:            "Content-Disposition": f'attachment; filename="{session_id}-{turn_id}-{action}_audit.json"',
vibecomfy/comfy_nodes/agent/routes.py:1751:        raw_session_id = safe_payload.get("session_id")
vibecomfy/comfy_nodes/agent/routes.py:1753:        if isinstance(raw_session_id, str):
vibecomfy/comfy_nodes/agent/routes.py:1754:            safe_payload["session_id"] = normalize_session_id(raw_session_id)
vibecomfy/comfy_nodes/agent/routes.py:1757:        if isinstance(safe_payload.get("session_id"), str) and isinstance(safe_payload.get("turn_id"), str):
vibecomfy/comfy_nodes/agent/routes.py:1758:            safe_payload["response_id"] = f"{safe_payload['session_id']}/{safe_payload['turn_id']}"
vibecomfy/comfy_nodes/agent/routes.py:1802:        normalize_session_id as _safe_session_id,
vibecomfy/comfy_nodes/agent/routes.py:1823:    def _session_id_from_query(request) -> str:  # type: ignore[no-untyped-def]
vibecomfy/comfy_nodes/agent/routes.py:1824:        return _safe_session_id(request.query.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:1925:        session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:1933:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:1964:        session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:1972:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:1995:        session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:2003:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:2026:        session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:2034:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:2057:        session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:2063:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:2104:        session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/routes.py:2109:                session_id=session_id,
vibecomfy/comfy_nodes/agent/routes.py:2125:        session_id = _session_id_from_query(request)
vibecomfy/comfy_nodes/agent/routes.py:2131:                session_id,
vibecomfy/comfy_nodes/agent/routes.py:2144:        session_id = _session_id_from_query(request)
vibecomfy/comfy_nodes/agent/routes.py:2149:                session_id,
vibecomfy/comfy_nodes/agent/routes.py:2161:        session_id = _session_id_from_query(request)
vibecomfy/comfy_nodes/agent/routes.py:2166:                session_id,
vibecomfy/porting/edit/apply_field_aliases.py:124:            continue  # already present via schema_inputs
vibecomfy/porting/edit/apply_field_aliases.py:127:            continue  # covered by a compact semantic name
vibecomfy/porting/edit/apply_field_aliases.py:138:                continue
vibecomfy/porting/edit/apply_field_aliases.py:174:            continue  # already present via schema_inputs
vibecomfy/porting/edit/apply_field_aliases.py:177:            continue  # covered by a semantic name
vibecomfy/porting/edit/apply_field_aliases.py:186:                continue
vibecomfy/porting/edit/apply_field_aliases.py:241:            continue
vibecomfy/porting/edit/apply_field_aliases.py:243:            continue
vibecomfy/porting/edit/apply_field_aliases.py:246:            continue
vibecomfy/porting/edit/apply_field_aliases.py:249:            continue
vibecomfy/porting/edit/apply_field_aliases.py:252:                continue
vibecomfy/porting/edit/apply_field_aliases.py:255:                continue
vibecomfy/porting/edit/apply_field_aliases.py:261:                continue
vibecomfy/porting/edit/apply_field_aliases.py:278:            continue
vibecomfy/porting/edit/apply_field_aliases.py:295:                continue
vibecomfy/porting/edit/apply_field_aliases.py:381:            continue
vibecomfy/executor/agent_research_stage.py:112:# from the research tool ledger (never model judgment).  The four states are
vibecomfy/executor/agent_research_stage.py:188:    """Derive the typed ``ResearchAttempt`` from the research tool ledger.
vibecomfy/executor/agent_research_stage.py:206:    tool_calls_made = sum(
vibecomfy/executor/agent_research_stage.py:209:    if tool_calls_made == 0:
vibecomfy/executor/agent_research_stage.py:599:    tool_calls: Sequence[Mapping[str, Any]],
vibecomfy/executor/agent_research_stage.py:632:    for call in tool_calls:
vibecomfy/executor/agent_research_stage.py:649:                continue
vibecomfy/executor/agent_research_stage.py:700:    ``provider.run_model_turn`` with ``response_contract="json"``, and parses
vibecomfy/executor/agent_research_stage.py:710:    from vibecomfy.comfy_nodes.agent.provider import run_model_turn  # noqa: PLC0415
vibecomfy/executor/agent_research_stage.py:712:    result = run_model_turn(
vibecomfy/executor/agent_research_stage.py:752:    tool_calls: tuple[dict[str, Any], ...]
vibecomfy/executor/agent_research_stage.py:760:            "tool_calls": [dict(call) for call in self.tool_calls],
vibecomfy/executor/agent_research_stage.py:772:    research tool ledger, never model judgment.
vibecomfy/executor/agent_research_stage.py:841:class _StageToolSession:
vibecomfy/executor/agent_research_stage.py:955:    tool_calls_made = 0
vibecomfy/executor/agent_research_stage.py:985:        nonlocal tool_calls_made
vibecomfy/executor/agent_research_stage.py:986:        tool_calls_made += 1
vibecomfy/executor/agent_research_stage.py:1011:                tool_calls=(digest,),
vibecomfy/executor/agent_research_stage.py:1042:                tool_calls=(digest,),
vibecomfy/executor/agent_research_stage.py:1077:                tool_calls=(digest,),
vibecomfy/executor/agent_research_stage.py:1112:                tool_calls=tool_call_digests,
vibecomfy/executor/agent_research_stage.py:1152:                if not citable_citations and tool_calls_made == 0:
vibecomfy/executor/agent_research_stage.py:1164:                    continue
vibecomfy/executor/agent_research_stage.py:1200:                        tool_calls=(),
vibecomfy/executor/agent_research_stage.py:1237:                continue
vibecomfy/executor/agent_research_stage.py:1241:                    continue
vibecomfy/executor/agent_research_stage.py:1246:                    continue
vibecomfy/executor/agent_research_stage.py:1251:                    continue
vibecomfy/executor/agent_research_stage.py:1352:            and tool_calls_made == 0
vibecomfy/executor/profiler.py:41:            continue
tests/test_agent_edit_settings_contract.py:350:    result = session.apply_batch("ksampler.control_after_generate = 'randomize'")
tests/test_agent_edit_settings_contract.py:366:    result = session.apply_batch("ksampler.steps = 30")
tests/test_agent_edit_settings_contract.py:378:    result = session.apply_batch("ksampler.cfg = 7.5")
tests/test_agent_edit_settings_contract.py:390:    result = session.apply_batch("ksampler.seed = 42")
tests/test_agent_edit_settings_contract.py:402:    result = session.apply_batch("ksampler.scheduler = 'karras'")
tests/test_agent_edit_settings_contract.py:414:    result = session.apply_batch("ksampler.sampler_name = 'dpmpp_2m'")
tests/test_agent_edit_settings_contract.py:430:    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
tests/test_agent_edit_settings_contract.py:462:    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
tests/test_agent_edit_settings_contract.py:474:    result = session.apply_batch("ksampler.scheduler = 'nonexistent_scheduler'")
tests/test_agent_edit_settings_contract.py:494:    result = session.apply_batch("ksampler.sampler = 'euler'")
tests/test_agent_edit_settings_contract.py:527:    result = session.apply_batch("ksampler.sampler = 'euler'")
tests/test_agent_edit_settings_contract.py:542:    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
tests/test_agent_edit_settings_contract.py:557:    result = session.apply_batch("ksampler.sampler = 'euler'")
tests/test_agent_edit_settings_contract.py:569:    result = session.apply_batch("ksampler.steps = 30")
tests/test_agent_edit_settings_contract.py:581:    result = session.apply_batch(batch)
tests/test_agent_edit_settings_contract.py:601:    result = session.apply_batch(batch)
tests/test_agent_edit_settings_contract.py:615:    result = session.apply_batch("ksampler.denoise = 0.5")
vibecomfy/porting/edit/_parse.py:162:            continue
vibecomfy/porting/edit/_parse.py:418:            continue
vibecomfy/porting/edit/_parse.py:427:            continue
vibecomfy/porting/edit/_parse.py:523:                continue
vibecomfy/porting/edit/_parse.py:525:            continue
vibecomfy/porting/edit/_parse.py:530:            continue
vibecomfy/porting/edit/_parse.py:535:                continue
vibecomfy/porting/edit/_parse.py:537:            continue
vibecomfy/porting/edit/_parse.py:543:            continue
vibecomfy/porting/edit/_parse.py:562:            continue
vibecomfy/porting/edit/_parse.py:572:            continue
vibecomfy/porting/edit/_parse.py:577:            continue
vibecomfy/executor/graph_facts.py:260:            continue
vibecomfy/executor/graph_facts.py:264:                continue
vibecomfy/executor/graph_facts.py:413:            continue
vibecomfy/executor/graph_facts.py:455:            continue
vibecomfy/executor/graph_facts.py:482:            continue
tests/test_ui_layout.py:1709:                continue
tests/test_ui_layout.py:1715:                continue
tests/test_ui_layout.py:1774:                continue
tests/test_ui_layout.py:1781:                continue
tests/test_agent_research_shadow.py:284:        assert trace.iterations[0].tool_calls[0]["tool"] == "hivemind_search"
tests/test_agent_research_shadow.py:286:        assert trace.iterations[1].tool_calls[0]["tool"] == "hivemind_get"
tests/test_agent_research_shadow.py:338:            if it.tool_calls and it.tool_calls[0]["tool"] == "hivemind_search"
tests/test_agent_research_shadow.py:339:            and it.tool_calls[0]["status"] == "ok"
tests/test_agent_research_shadow.py:344:            if it.tool_calls and it.tool_calls[0]["status"] == "refused"
tests/test_agent_research_shadow.py:532:        failure — and the loop continues to a finish."""
tests/test_agent_research_shadow.py:612:        stage, and the loop continues to a finish."""
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:80:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:306:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:317:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:363:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:383:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:387:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:390:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:396:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:399:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:460:                        continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:481:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:483:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:487:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:506:                        continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:552:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:571:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:575:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:596:                continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:684:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:688:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:705:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:711:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:725:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:833:    session_id: str,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:842:            continue
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:845:                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:847:                    session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:856:            continue
vibecomfy/porting/edit/apply_gate.py:57:    ``landed_ops`` is the accepted batch (preferred Δ).  ``delta`` is used
vibecomfy/porting/edit/apply_gate.py:148:            continue
vibecomfy/porting/edit/apply_gate.py:160:            continue
vibecomfy/porting/edit/apply_gate.py:252:            continue
vibecomfy/porting/edit/apply_gate.py:254:            continue
vibecomfy/porting/edit/apply_gate.py:259:                    continue
vibecomfy/porting/edit/apply_gate.py:261:                    continue
vibecomfy/porting/edit/apply_gate.py:297:                continue
vibecomfy/porting/edit/apply_gate.py:315:            continue
vibecomfy/executor/hivemind_clients.py:289:                continue
vibecomfy/executor/hivemind_clients.py:373:                continue
vibecomfy/executor/hivemind_clients.py:376:                continue
vibecomfy/executor/hivemind_clients.py:534:            continue
vibecomfy/executor/hivemind_clients.py:542:            continue
vibecomfy/executor/hivemind_clients.py:576:            continue
vibecomfy/executor/hivemind_clients.py:609:                continue
vibecomfy/executor/hivemind_clients.py:652:            continue
vibecomfy/executor/hivemind_clients.py:1020:            continue
vibecomfy/executor/hivemind_clients.py:1064:                continue
vibecomfy/executor/hivemind_clients.py:1067:                continue
vibecomfy/executor/hivemind_clients.py:1071:                continue
vibecomfy/executor/hivemind_clients.py:1086:            continue
vibecomfy/executor/hivemind_clients.py:1088:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:45:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:234:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:238:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:260:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:264:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:402:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:421:                continue
vibecomfy/comfy_nodes/agent/_frag_research.py:430:                    continue
vibecomfy/comfy_nodes/agent/_frag_research.py:439:                continue
vibecomfy/comfy_nodes/agent/_frag_research.py:454:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:458:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:467:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:544:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:548:                continue
vibecomfy/comfy_nodes/agent/_frag_research.py:550:                continue
vibecomfy/comfy_nodes/agent/_frag_research.py:592:            continue
vibecomfy/comfy_nodes/agent/_frag_research.py:596:                continue
vibecomfy/comfy_nodes/agent/_frag_research.py:598:                continue
tests/test_porting_normalize_ingest.py:1264:    _stage_ingest_v2(state, TurnContext(session_id="b3-a", turn_id="t1"))
tests/test_porting_normalize_ingest.py:1286:    context = TurnContext(session_id="b3-b", turn_id="t1")
tests/test_porting_normalize_ingest.py:1294:    result2 = _stage_ingest_v2(state, TurnContext(session_id="b3-b", turn_id="t2"))
tests/test_porting_normalize_ingest.py:1299:    _stage_ingest(state2, TurnContext(session_id="b3-b", turn_id="t3"))
vibecomfy/executor/provenance.py:75:            continue
vibecomfy/executor/provenance.py:78:            continue
vibecomfy/executor/provenance.py:218:            continue
tests/test_authority_receipts.py:104:        session_id="layout-session",
tests/test_authority_receipts.py:138:        session_id="layout-session",
tests/test_authority_receipts.py:156:        session_id="schema-session",
tests/test_authority_receipts.py:202:        session_id="session-exact",
tests/test_authority_receipts.py:219:    assert raw["accepted_batch_digest"] == raw["cumulative_delta_hash"]
tests/test_authority_receipts.py:233:        session_id="strict-receipt",
vibecomfy/porting/edit/_parse_execute.py:22:    def apply_batch(self, code: str) -> BatchResult:
vibecomfy/porting/edit/_parse_execute.py:49:                raise RuntimeError("EditSession.apply_batch requires a retained IR")
vibecomfy/porting/edit/_parse_execute.py:199:                continue
vibecomfy/porting/edit/_parse_execute.py:202:                continue
vibecomfy/porting/edit/_parse_execute.py:208:                continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:20:    _accepted_batch_delta_ops,
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:22:    derived_accepted_delta_envelope,
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:87:    ops = _accepted_batch_delta_ops(state)
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:90:    return derived_accepted_delta_envelope(
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:638:        text = "What detail should I use before continuing?"
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:648:                continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:683:            continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:686:            continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:689:                continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:692:                continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:696:                    continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:699:                        continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:706:                        continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:717:            continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:721:                continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:733:            continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:736:            continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:825:                continue
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:1245:    if response["accepted_batch"] or delta_evidence_envelope is not None:
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:1262:                    claim_keys = _accepted_delta_claim_keys(response)
tests/conftest.py:20:        continue
tests/conftest.py:23:        continue
tests/conftest.py:75:            continue
tests/conftest.py:84:            continue
tests/conftest.py:115:            continue
tests/conftest.py:248:            continue
vibecomfy/porting/edit/grammar.py:407:            continue
vibecomfy/porting/edit/grammar.py:416:            continue
vibecomfy/porting/edit/grammar.py:450:            continue
vibecomfy/porting/edit/grammar.py:475:            continue
vibecomfy/executor/revision_evidence.py:79:            continue
vibecomfy/executor/revision_evidence.py:180:                continue
vibecomfy/executor/revision_evidence.py:218:                continue
vibecomfy/executor/revision_evidence.py:223:                    continue
vibecomfy/executor/revision_evidence.py:534:            continue
vibecomfy/executor/revision_evidence.py:537:            continue
vibecomfy/executor/revision_evidence.py:576:            continue
vibecomfy/executor/revision_evidence.py:630:            continue
vibecomfy/executor/revision_evidence.py:632:            continue
vibecomfy/executor/revision_evidence.py:640:            continue
vibecomfy/executor/revision_evidence.py:655:            continue
vibecomfy/executor/revision_evidence.py:660:            continue
vibecomfy/executor/revision_evidence.py:668:                continue
vibecomfy/executor/revision_evidence.py:965:                continue
vibecomfy/executor/revision_evidence.py:1140:                continue
vibecomfy/executor/revision_evidence.py:1282:                    continue
vibecomfy/executor/revision_evidence.py:1350:                        continue
vibecomfy/executor/contracts.py:961:    ``{task, query, graph, session_id}`` payload when an implementation turn is
vibecomfy/executor/contracts.py:968:    session_id: str | None = None
vibecomfy/executor/contracts.py:1010:        if self.session_id is not None:
vibecomfy/executor/contracts.py:1011:            payload["session_id"] = self.session_id
vibecomfy/executor/contracts.py:1065:        session_id = payload.get("session_id")
vibecomfy/executor/contracts.py:1066:        if session_id is not None and not isinstance(session_id, str):
vibecomfy/executor/contracts.py:1067:            raise ValueError("ExecutorRequest `session_id` must be a string or null.")
vibecomfy/executor/contracts.py:1068:        if session_id is not None:
vibecomfy/executor/contracts.py:1069:            from vibecomfy.comfy_nodes.agent.session import normalize_session_id  # noqa: PLC0415
vibecomfy/executor/contracts.py:1071:            session_id = normalize_session_id(session_id)
vibecomfy/executor/contracts.py:1112:            session_id=session_id,
vibecomfy/executor/contracts.py:1753:    ``handle_agent_edit`` (SD1).  It preserves ``session_id``, ``turn_id``,
vibecomfy/executor/contracts.py:1796:    def durable_session_id(self) -> str | None:
vibecomfy/executor/contracts.py:1797:        """Return the session_id from the durable response, if present."""
vibecomfy/executor/contracts.py:1801:        sid = dr.get("session_id")
vibecomfy/executor/contracts.py:2077:                sid = impl.durable_session_id
vibecomfy/executor/contracts.py:2080:                    candidate["session_id"] = sid
vibecomfy/executor/contracts.py:2131:    "session_id",
vibecomfy/executor/contracts.py:2191:        # response (SD1, SD2) so downstream consumers see session_id,
vibecomfy/executor/contracts.py:2255:            continue
vibecomfy/executor/contracts.py:2309:                continue
vibecomfy/executor/contracts.py:2313:                continue
vibecomfy/executor/contracts.py:2316:                continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:138:            continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:310:            continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:358:            continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:402:                continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:577:                continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:601:            continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:616:                continue
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:961:    for key in ("transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash"): issued_identity_v1(raw.get(key), key)
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:973:        raise ContractError("operation must not persist ops; accepted_batch is the durable Δ", "durable_delta_ops_copy")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:976:        raise ContractError("Operation must reference accepted_batch by digest", "invalid_delta_contract")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:979:        from vibecomfy.comfy_nodes.agent._frag_state import derived_accepted_delta_envelope
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:982:        expected = content_hash(derived_accepted_delta_envelope({"accepted_batch": accepted_batch}))
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:1070:        for key in ("transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash", "workflow_id", "scope", "operation", "operation_family", "precondition", "postcondition", "rollback_projection", "restoration_strategy", "authority_receipt_contract_version", "authority_receipt_delta_schema", "authority_receipt_digest"):
tests/test_schema_validate.py:604:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:62:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:129:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:134:                    continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:145:                    continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:277:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:486:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:489:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:569:            continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:575:                continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:657:                continue
vibecomfy/comfy_nodes/agent/_frag_batch_reports.py:660:                continue
vibecomfy/executor/edit_suggestion_tools.py:373:                continue
vibecomfy/executor/edit_suggestion_tools.py:375:                continue
vibecomfy/executor/edit_suggestion_tools.py:671:            continue
vibecomfy/executor/edit_suggestion_tools.py:674:            continue
vibecomfy/executor/edit_suggestion_tools.py:779:            continue
vibecomfy/executor/edit_suggestion_tools.py:918:            continue
vibecomfy/executor/edit_suggestion_tools.py:921:            continue
vibecomfy/executor/edit_suggestion_tools.py:923:            continue
tests/smoke/test_layer2_runpod_dropped.py:121:                continue
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:59:    from vibecomfy.comfy_nodes.agent.edit import (AgentEditState, FailureKind, PROMPT_MEMORY_MESSAGES, StageResult, _SESSION_ROOT, _StageBlocked, _agent_edit_contract, _build_batch_repl_response, _canonical_agent_edit_route, _conversation_with_candidate_reference, _default_runtime_schema_provider, _failure_response, _hydrate_execution_plan_from_protocol_notes, _product_failure_response, _record, _run_batch_repl_product_path, _safe_session_id, _stage_audit, _validated_agent_edit_response, _write_turn_chat_artifact, _write_unknown_transition_audits, allocate_turn, classify_failure, failure_envelope, initialize_gates, read_session_chat, record_idempotent_response, write_allocation_failure_audit)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:130:    session_id = _safe_session_id(payload.get("session_id"))
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:133:        session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:154:                session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:171:        session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:314:            session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:340:            chat = read_session_chat(root, session_id, max_messages=PROMPT_MEMORY_MESSAGES)
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:382:            session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:460:        session_id=session_id,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:532:            continue
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:574:        "session_id": context.session_id,
tests/test_agent_route_families.py:140:            continue
tests/test_agent_route_families.py:142:            continue
tests/test_agent_route_families.py:145:                continue
tests/test_agent_route_families.py:184:            continue
tests/test_agent_route_families.py:196:            continue
vibecomfy/executor/hivemind_tools.py:329:            continue
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:11:    "session_id",
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:33:    "session_id": {
tests/pi_transition/TEST_PLAN.md:159:  continue to produce their compile-only evidence packs. The Pi worker is
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:577:            continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:640:                continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:694:            continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:773:            continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1484:            batch_result = session.apply_batch(editable_batch)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1558:                        continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1998:                continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2058:                        continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2116:                    continue
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2167:                    continue
vibecomfy/executor/prompts.py:308:    "- \"Pick some please\" after a clarification -> continue with a reasonable "
vibecomfy/executor/prompts.py:359:                    continue
vibecomfy/executor/prompts.py:362:                    continue
vibecomfy/executor/prompts.py:365:                    continue
vibecomfy/executor/prompts.py:407:                        continue
vibecomfy/executor/prompts.py:598:            "research tool ledger — what research actually did, not a "
vibecomfy/executor/prompts.py:935:            continue
tests/test_porting_ui_emitter.py:657:            continue
tests/test_porting_ui_emitter.py:711:            continue
tests/test_porting_ui_emitter.py:721:            continue
tests/test_porting_ui_emitter.py:806:            continue
tests/test_porting_ui_emitter.py:822:            continue
tests/test_porting_ui_emitter.py:826:            continue
tests/test_porting_ui_emitter.py:836:            continue
tests/test_porting_ui_emitter.py:1366:                continue
tests/test_porting_ui_emitter.py:1394:                continue
tests/test_porting_ui_emitter.py:1403:                continue
tests/test_porting_ui_emitter.py:1417:                continue
tests/test_porting_ui_emitter.py:1429:                continue
tests/test_porting_ui_emitter.py:1445:                continue

exec
/bin/zsh -lc "find tests/live_agentic_harness -maxdepth 2 -type f | sort | sed -n '1,220p'
rg -n \"argparse|add_argument|def main|50|scenario_manifest|run_headless|pytest\" tests/live_agentic_harness pyproject.toml Makefile README.md | sed -n '1,320p'
rg -n \"compatibility.*57|57.*case|LEDGER|parametrize|cases\" tests/test_agent_edit_compatibility_ledger.py | sed -n '1,220p'
sed -n '1,220p' tests/live_agentic_harness/README.md 2>/dev/null || true
sed -n '1,220p' tests/test_agent_edit_compatibility_ledger.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
tests/live_agentic_harness/README.md
tests/live_agentic_harness/REVISIONS.md
tests/live_agentic_harness/__init__.py
tests/live_agentic_harness/adapter.py
tests/live_agentic_harness/assessor.py
tests/live_agentic_harness/briefs/live-graph-explanation-smoke.md
tests/live_agentic_harness/failure_analysis.py
tests/live_agentic_harness/fixtures/__init__.py
tests/live_agentic_harness/fixtures/harness_child.py
tests/live_agentic_harness/guard.py
tests/live_agentic_harness/intent_judge.py
tests/live_agentic_harness/research_assessment.py
tests/live_agentic_harness/runner.py
tests/live_agentic_harness/scen19/3d-converts-image-to-3d-model.json
tests/live_agentic_harness/scen19/3d-generates-a-3d-mesh-from.json
tests/live_agentic_harness/scen19/audio-transcribes-audio-appends-text-regenerates.json
tests/live_agentic_harness/scen19/audio-tts-narration-using-indextts-2.json
tests/live_agentic_harness/scen19/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scen19/image-generates-a-2x2-seed-variation.json
tests/live_agentic_harness/scen19/image-image-editing-with-qwen-image.json
tests/live_agentic_harness/scen19/image-sdxl-txt2img-cat-in-spacesuit.json
tests/live_agentic_harness/scen19/image-style-transfer-using-ip-adapter.json
tests/live_agentic_harness/scen19/image-two-stage-qwen-image-generation.json
tests/live_agentic_harness/scen19/multi-crops-face-previews-it-sets.json
tests/live_agentic_harness/scen19/multi-image-to-video-generation-with-2.json
tests/live_agentic_harness/scen19/multi-image-to-video-generation-with.json
tests/live_agentic_harness/scen19/multi-image-to-video-with-llm.json
tests/live_agentic_harness/scen19/multi-video-based-character-replacement-using.json
tests/live_agentic_harness/scen19/video-generates-a-video-from-a.json
tests/live_agentic_harness/scen19/video-ltx-video-upscaling-and-enhancement.json
tests/live_agentic_harness/scen19/video-video-frame-by-frame-style.json
tests/live_agentic_harness/scen19/video-video-generation-from-resized-image.json
tests/live_agentic_harness/scen19_manifest.json
tests/live_agentic_harness/scenario_manifest.json
tests/live_agentic_harness/scenario_manifest.py
tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json
tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json
tests/live_agentic_harness/scenarios/3d-3d-model-load-edit-and-export-workflow-d66a66.json
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json
tests/live_agentic_harness/scenarios/3d-converts-image-to-3d-model.json
tests/live_agentic_harness/scenarios/3d-generates-a-3d-mesh-from.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-and-processing-workfl-1b1360.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-ksampler-e8c20a.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-workflow-2a31ec.json
tests/live_agentic_harness/scenarios/audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676.json
tests/live_agentic_harness/scenarios/audio-audio-processing-with-chatterbox-tts-and-vc-b55994.json
tests/live_agentic_harness/scenarios/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json
tests/live_agentic_harness/scenarios/audio-transcribes-audio-appends-text-regenerates.json
tests/live_agentic_harness/scenarios/audio-tts-narration-using-indextts-2.json
tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json
tests/live_agentic_harness/scenarios/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenarios/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json
tests/live_agentic_harness/scenarios/image-background-removal-and-grid-composition-54a681.json
tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json
tests/live_agentic_harness/scenarios/image-flux-image-inpainting-and-compositing-with-con-00444a.json
tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
tests/live_agentic_harness/scenarios/image-generates-a-2x2-seed-variation.json
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenarios/image-image-editing-with-qwen-image.json
tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-controlnet-and-dwpreproces-49d057.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json
tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json
tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json
tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json
tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json
tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json
tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json
tests/live_agentic_harness/scenarios/image-sdxl-txt2img-cat-in-spacesuit.json
tests/live_agentic_harness/scenarios/image-style-transfer-using-ip-adapter.json
tests/live_agentic_harness/scenarios/image-two-stage-qwen-image-generation.json
tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json
tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json
tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json
tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json
tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json
tests/live_agentic_harness/scenarios/multi-crops-face-previews-it-sets.json
tests/live_agentic_harness/scenarios/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json
tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json
tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with-2.json
tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with.json
tests/live_agentic_harness/scenarios/multi-image-to-video-with-llm.json
tests/live_agentic_harness/scenarios/multi-image-to-video-with-upscaling-and-color-matchi-359848.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-webp-and-png-output-bd3afb.json
tests/live_agentic_harness/scenarios/multi-video-based-character-replacement-using.json
tests/live_agentic_harness/scenarios/multi-wan-vace-video-retargeting-driven.json
tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json
tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json
tests/live_agentic_harness/scenarios/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json
tests/live_agentic_harness/scenarios/speed-distillation-research.json
tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json
tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json
tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json
tests/live_agentic_harness/scenarios/video-generates-a-video-from-a.json
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json
tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json
tests/live_agentic_harness/scenarios/video-ltx-video-upscaling-and-enhancement.json
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json
tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json
tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json
tests/live_agentic_harness/scenarios/video-video-frame-by-frame-style.json
tests/live_agentic_harness/scenarios/video-video-generation-from-resized-image.json
tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json
tests/live_agentic_harness/scenarios/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
tests/live_agentic_harness/scenfails32/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json
tests/live_agentic_harness/scenfails32/3d-3d-model-generation-and-preview-workflow-cc0df7.json
tests/live_agentic_harness/scenfails32/3d-3d-model-generation-and-retargeting-workflow-f65774.json
tests/live_agentic_harness/scenfails32/3d-3d-model-generation-and-rigging-from-image-352066.json
tests/live_agentic_harness/scenfails32/3d-3d-model-generation-and-rigging-workflow-90a1d5.json
tests/live_agentic_harness/scenfails32/3d-3d-shape-generation-and-export-workflow-8800a9.json
tests/live_agentic_harness/scenfails32/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json
tests/live_agentic_harness/scenfails32/hotshot-16-frames-agent-edit.json
tests/live_agentic_harness/scenfails32/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenfails32/image-face-detection-and-cropping-workflow-949658.json
tests/live_agentic_harness/scenfails32/image-flux-image-inpainting-and-compositing-with-con-00444a.json
tests/live_agentic_harness/scenfails32/image-generates-a-2x2-seed-variation.json
tests/live_agentic_harness/scenfails32/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails32/image-kolors-image-generation-with-segs-detailer-and-d813fe.json
tests/live_agentic_harness/scenfails32/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json
tests/live_agentic_harness/scenfails32/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails32/multi-crops-face-previews-it-sets.json
tests/live_agentic_harness/scenfails32/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails32/multi-image-to-video-generation-with-2.json
tests/live_agentic_harness/scenfails32/multi-image-to-video-with-upscaling-and-color-matchi-359848.json
tests/live_agentic_harness/scenfails32/multi-wan-vace-video-retargeting-driven.json
tests/live_agentic_harness/scenfails32/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json
tests/live_agentic_harness/scenfails32/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json
tests/live_agentic_harness/scenfails32/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
tests/live_agentic_harness/scenfails32/video-image-to-video-with-svd-and-webp-output-1882aa.json
tests/live_agentic_harness/scenfails32/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
tests/live_agentic_harness/scenfails32/video-svd-image-to-video-generation-fc240f.json
tests/live_agentic_harness/scenfails32/video-video-combine-with-image-loading-5b31ce.json
tests/live_agentic_harness/scenfails32/video-video-frame-by-frame-style.json
tests/live_agentic_harness/scenfails32/video-video-generation-from-resized-image.json
tests/live_agentic_harness/scenfails32/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
tests/live_agentic_harness/scenfails32/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json
tests/live_agentic_harness/scenfails32/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
tests/live_agentic_harness/scenfails32/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
tests/live_agentic_harness/scenfails32_manifest.json
tests/live_agentic_harness/scenfails41/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json
tests/live_agentic_harness/scenfails41/3d-3d-model-generation-and-preview-workflow-cc0df7.json
tests/live_agentic_harness/scenfails41/3d-3d-model-generation-and-retargeting-workflow-f65774.json
tests/live_agentic_harness/scenfails41/3d-3d-model-generation-and-rigging-from-image-352066.json
tests/live_agentic_harness/scenfails41/3d-3d-model-generation-and-rigging-workflow-90a1d5.json
tests/live_agentic_harness/scenfails41/3d-3d-shape-generation-and-export-workflow-8800a9.json
tests/live_agentic_harness/scenfails41/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json
tests/live_agentic_harness/scenfails41/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json
tests/live_agentic_harness/scenfails41/hotshot-16-frames-agent-edit.json
tests/live_agentic_harness/scenfails41/image-animatediff-video-from-images-with.json
tests/live_agentic_harness/scenfails41/image-animatediff-video-generation-with-vae-d20410.json
tests/live_agentic_harness/scenfails41/image-face-detection-and-cropping-workflow-949658.json
tests/live_agentic_harness/scenfails41/image-flux-image-inpainting-and-compositing-with-con-00444a.json
tests/live_agentic_harness/scenfails41/image-generates-a-2x2-seed-variation.json
tests/live_agentic_harness/scenfails41/image-image-comparison-and-enhancement-with-florence-007018.json
tests/live_agentic_harness/scenfails41/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json
tests/live_agentic_harness/scenfails41/image-kolors-image-generation-with-segs-detailer-and-d813fe.json
tests/live_agentic_harness/scenfails41/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json
tests/live_agentic_harness/scenfails41/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json
tests/live_agentic_harness/scenfails41/multi-crops-face-previews-it-sets.json
tests/live_agentic_harness/scenfails41/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json
tests/live_agentic_harness/scenfails41/multi-image-to-video-generation-with-2.json
tests/live_agentic_harness/scenfails41/multi-image-to-video-with-upscaling-and-color-matchi-359848.json
tests/live_agentic_harness/scenfails41/multi-wan-vace-video-retargeting-driven.json
tests/live_agentic_harness/scenfails41/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json
tests/live_agentic_harness/scenfails41/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json
tests/live_agentic_harness/scenfails41/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json
tests/live_agentic_harness/scenfails41/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
tests/live_agentic_harness/scenfails41/video-image-to-video-with-svd-and-webp-output-1882aa.json
tests/live_agentic_harness/scenfails41/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
tests/live_agentic_harness/scenfails41/video-seedvr2-video-upscaling-workflow-052e59.json
tests/live_agentic_harness/scenfails41/video-svd-image-to-video-generation-fc240f.json
tests/live_agentic_harness/scenfails41/video-video-combine-with-image-loading-5b31ce.json
tests/live_agentic_harness/scenfails41/video-video-frame-by-frame-style.json
tests/live_agentic_harness/scenfails41/video-video-generation-from-resized-image.json
tests/live_agentic_harness/scenfails41/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
tests/live_agentic_harness/scenfails41/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json
tests/live_agentic_harness/scenfails41/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
tests/live_agentic_harness/scenfails41/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
tests/live_agentic_harness/scenfails41/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
tests/live_agentic_harness/scenfails41_manifest.json
tests/live_agentic_harness/scenfails57/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json
tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-preview-workflow-cc0df7.json
tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-retargeting-workflow-f65774.json
tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-rigging-from-image-352066.json
tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-rigging-workflow-90a1d5.json
tests/live_agentic_harness/scenfails57/3d-3d-shape-generation-and-export-workflow-8800a9.json
tests/live_agentic_harness/scenfails57/audio-acestep-audio-generation-with-detail-daemon-f0859f.json
pyproject.toml:22:  "pytest>=7",
pyproject.toml:23:  "pytest-asyncio>=0.23",
pyproject.toml:24:  "pytest-cov>=4",
pyproject.toml:25:  "pytest-rerunfailures>=14",
pyproject.toml:26:  "pytest-xdist>=3.6",
pyproject.toml:100:[tool.pytest.ini_options]
pyproject.toml:108:  "intent_ci: marks fast, deterministic intent-oracle CI gate tests (invoke with `pytest -m intent_ci tests/intent`).",
pyproject.toml:133:[project.entry-points.pytest11]
pyproject.toml:134:vibecomfy = "vibecomfy.testing._pytest_plugin"
Makefile:3:PYTEST ?= $(PYTHON) -m pytest
Makefile:107:.PHONY: all check ci install-dev install-ci prune-empty-runtime-root root-clean post-root-clean docs template-index templates strict-ready fast full-pytest snapshots oracle b02-corpus-mini b02-corpus-full browser-contracts browser-smoke parity e2e-browser e2e-preview corrective-trust-gate-preflight corrective-trust-gate ir-boundary clean clean-artifacts
Makefile:169:# pyproject [tool.pytest.ini_options] addopts) parallelized across 8 xdist workers.
Makefile:170:full-pytest:
Makefile:233:	rm -rf .coverage coverage.xml .pytest_cache .hypothesis out temp test-results
README.md:3:<img src="docs/assets/mascot/mascot.png" align="left" width="150px">
tests/live_agentic_harness/REVISIONS.md:4:scenario intent remains matched. `scenario_manifest.json` records the same split
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:2:  "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:4:  "workflow_path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:35:    "source_workflow_id": "506ebdde037e22d8",
tests/live_agentic_harness/README.md:11:The selected live lane is fixed by `scenario_manifest.json`. Before starting
tests/live_agentic_harness/scenario_manifest.py:17:DEFAULT_MANIFEST_PATH = Path(__file__).with_name("scenario_manifest.json")
tests/live_agentic_harness/scenario_manifest.py:36:    return scenarios_dir.parent / "scenario_manifest.json"
tests/live_agentic_harness/intent_judge.py:1032:            "raw": raw[:500],
tests/live_agentic_harness/intent_judge.py:1145:            "raw": raw[:500],
tests/live_agentic_harness/intent_judge.py:1243:            "raw": raw[:500],
tests/live_agentic_harness/scenfails41_manifest.json:29:    "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenfails41_manifest.json:35:   "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
tests/live_agentic_harness/scenfails41_manifest.json:48:   "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
tests/live_agentic_harness/scenfails41_manifest.json:107:    "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenfails41_manifest.json:185:    "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenfails41_manifest.json:198:    "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenfails41_manifest.json:204:   "descriptor_sha256": "12229915b1fc6a91fa40dbd8217de299577e02974cae4550af8f090cfa52797c",
tests/live_agentic_harness/scenfails41_manifest.json:224:    "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenfails41_manifest.json:243:   "descriptor_sha256": "2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457",
tests/live_agentic_harness/scenfails41_manifest.json:254:   "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails41_manifest.json:255:   "path": "tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json",
tests/live_agentic_harness/scenfails41_manifest.json:261:    "id": "506ebdde037e22d8",
tests/live_agentic_harness/scenfails41_manifest.json:262:    "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails41_manifest.json:295:   "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scenfails41_manifest.json:302:    "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenfails41_manifest.json:367:    "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenfails41_manifest.json:373:   "descriptor_sha256": "60a19bcef50943ef4134e0282d1d14a312df987354e5e3a03c0f380854d942e0",
tests/live_agentic_harness/scenfails41_manifest.json:386:   "descriptor_sha256": "d52d2cf1efae560d5cb49cd507321c8ae20290ecb723ad06b5674d6914bf59a1",
tests/live_agentic_harness/scenfails41_manifest.json:406:    "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenfails41_manifest.json:523:    "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenfails57_manifest.json:29:        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenfails57_manifest.json:35:      "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
tests/live_agentic_harness/scenfails57_manifest.json:48:      "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
tests/live_agentic_harness/scenfails57_manifest.json:120:        "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenfails57_manifest.json:172:        "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scenfails57_manifest.json:211:        "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scenfails57_manifest.json:224:        "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenfails57_manifest.json:237:        "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenfails57_manifest.json:256:      "descriptor_sha256": "12229915b1fc6a91fa40dbd8217de299577e02974cae4550af8f090cfa52797c",
tests/live_agentic_harness/scenfails57_manifest.json:276:        "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenfails57_manifest.json:330:      "descriptor_sha256": "2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457",
tests/live_agentic_harness/scenfails57_manifest.json:341:      "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails57_manifest.json:342:      "path": "tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json",
tests/live_agentic_harness/scenfails57_manifest.json:348:        "id": "506ebdde037e22d8",
tests/live_agentic_harness/scenfails57_manifest.json:349:        "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails57_manifest.json:363:        "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scenfails57_manifest.json:408:      "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scenfails57_manifest.json:415:        "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenfails57_manifest.json:493:        "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenfails57_manifest.json:525:      "descriptor_sha256": "60a19bcef50943ef4134e0282d1d14a312df987354e5e3a03c0f380854d942e0",
tests/live_agentic_harness/scenfails57_manifest.json:538:      "descriptor_sha256": "d52d2cf1efae560d5cb49cd507321c8ae20290ecb723ad06b5674d6914bf59a1",
tests/live_agentic_harness/scenfails57_manifest.json:571:        "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenfails57_manifest.json:668:      "descriptor_sha256": "c18f241b403ed7d3c533330a9f4851f6e0870bb450c9d6edda713db827785be0",
tests/live_agentic_harness/scenfails57_manifest.json:714:        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenfails57_manifest.json:738:        "id": "71f825e4550c95b7",
tests/live_agentic_harness/scenfails57_manifest.json:739:        "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenfails57_manifest.json:740:        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
tests/live_agentic_harness/assessor.py:11:* upstream dependency failures such as Hivemind HTTP 500
tests/live_agentic_harness/assessor.py:46:    re.compile(r"Hivemind HTTP error.*500", re.IGNORECASE),
tests/live_agentic_harness/assessor.py:47:    re.compile(r"HTTP Error 500", re.IGNORECASE),
tests/live_agentic_harness/assessor.py:954:        # Critical upstream failures (Hivemind 500, etc.). Infra is not a
tests/live_agentic_harness/scen19_manifest.json:9:   "descriptor_sha256": "5f131e3f6743491dc8ce59b63d5e52d50091d8f4bf7c199f76b130ada6f2214c",
tests/live_agentic_harness/scen19_manifest.json:22:   "descriptor_sha256": "78500beb98600be76f05723fee97c4acb2894a7b7d71b6217fc176fc04cd461f",
tests/live_agentic_harness/scen19_manifest.json:48:   "descriptor_sha256": "4e55deceb5b3cb551aea17a49436b5749ee5a9ef0c8109239503c7297cf242ff",
tests/live_agentic_harness/scen19_manifest.json:81:    "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scen19_manifest.json:100:   "descriptor_sha256": "04bf444c3c44edc850a0a4c9a19a3664b31fd0d8ff4cff13826befd4f8d06080",
tests/live_agentic_harness/scen19_manifest.json:152:   "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scen19_manifest.json:159:    "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scen19_manifest.json:172:    "sha256": "f344d3cb450634d608fb63fb8296e1b6cb49f84481e2adc534be7d198d7fac72"
tests/live_agentic_harness/scen19_manifest.json:185:    "sha256": "287ee5ba6b895449763a1f6589d6d5b66fa225844ace8892e957c62d07504d22"
tests/live_agentic_harness/scen19_manifest.json:204:   "descriptor_sha256": "521376ee3a0b3c568644df355f791036ca6a034c6e9b0f4f4e78450c1953928d",
tests/live_agentic_harness/scen19_manifest.json:209:    "id": "59502aed6ad75d87",
tests/live_agentic_harness/scen19_manifest.json:210:    "path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scen19_manifest.json:307:    "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scen19_manifest.json:372:    "sha256": "cf18d35e10586b45a798da007c09965f0abd89a5339a1d15507605c651fcdc22"
tests/live_agentic_harness/scen19_manifest.json:382:    "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scen19_manifest.json:427:    "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scen19_manifest.json:442:    "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scen19_manifest.json:447:    "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scen19_manifest.json:452:    "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scen19_manifest.json:467:    "sha256": "08cee15268021cccedfae4b5cf7c9c689a135fb20cf83861a72d433471250b1d"
tests/live_agentic_harness/scen19_manifest.json:487:    "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scen19_manifest.json:547:    "sha256": "c148b3b74fb11eb408e6cfb2150189075d1b122b64eb6a341775267404c62af9"
tests/live_agentic_harness/scen19_manifest.json:549:   "multi-animatediff-video-face-swapping-with-deflicker-506ebd": {
tests/live_agentic_harness/scen19_manifest.json:550:    "source_workflow_id": "506ebdde037e22d8",
tests/live_agentic_harness/scen19_manifest.json:551:    "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scen19_manifest.json:557:    "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scen19_manifest.json:587:    "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scen19_manifest.json:592:    "sha256": "f344d3cb450634d608fb63fb8296e1b6cb49f84481e2adc534be7d198d7fac72"
tests/live_agentic_harness/scen19_manifest.json:597:    "sha256": "287ee5ba6b895449763a1f6589d6d5b66fa225844ace8892e957c62d07504d22"
tests/live_agentic_harness/scen19_manifest.json:612:    "sha256": "b3356f4640f638998d1eae50dd2ac775342c649d6d3a77940b93d6c72b762189"
tests/live_agentic_harness/scen19_manifest.json:647:    "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scen19_manifest.json:670:    "source_workflow_id": "59502aed6ad75d87",
tests/live_agentic_harness/scen19_manifest.json:671:    "path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scen19_manifest.json:687:    "sha256": "0cf39ff1502b0029829a20c609b8a0caee6bfd45ee9472e327bdfdb95acf827c"
tests/live_agentic_harness/scen19_manifest.json:707:    "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scen19_manifest.json:762:    "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scen19_manifest.json:785:    "source_workflow_id": "71f825e4550c95b7",
tests/live_agentic_harness/scen19_manifest.json:786:    "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scen19_manifest.json:787:    "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
tests/live_agentic_harness/adapter.py:4:``vibecomfy.agent.service.run_headless`` directly.  External callers (e.g.
tests/live_agentic_harness/adapter.py:135:def run_headless_scenario(
tests/live_agentic_harness/adapter.py:169:    from vibecomfy.agent.service import run_headless
tests/live_agentic_harness/adapter.py:203:    result = run_headless(request, entrypoint="live_agentic_harness")
tests/live_agentic_harness/scenario_manifest.json:29:        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenario_manifest.json:35:      "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
tests/live_agentic_harness/scenario_manifest.json:48:      "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
tests/live_agentic_harness/scenario_manifest.json:74:      "descriptor_sha256": "5fe9bba69049a4849346c505321eac3e7a4c44b212b67d8e940de12f92874bbe",
tests/live_agentic_harness/scenario_manifest.json:100:      "descriptor_sha256": "5f131e3f6743491dc8ce59b63d5e52d50091d8f4bf7c199f76b130ada6f2214c",
tests/live_agentic_harness/scenario_manifest.json:113:      "descriptor_sha256": "78500beb98600be76f05723fee97c4acb2894a7b7d71b6217fc176fc04cd461f",
tests/live_agentic_harness/scenario_manifest.json:165:      "descriptor_sha256": "f48a0350bc94e328d3aaf0d81cd8eb67fa0a95c458c61b215ea844b4e802b248",
tests/live_agentic_harness/scenario_manifest.json:191:      "descriptor_sha256": "aa3859ee4661d125044bdb9d1ba907ed3944c1e28010cacbd0826ed0baea1de4",
tests/live_agentic_harness/scenario_manifest.json:198:        "sha256": "cf18d35e10586b45a798da007c09965f0abd89a5339a1d15507605c651fcdc22"
tests/live_agentic_harness/scenario_manifest.json:224:        "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenario_manifest.json:243:      "descriptor_sha256": "4e55deceb5b3cb551aea17a49436b5749ee5a9ef0c8109239503c7297cf242ff",
tests/live_agentic_harness/scenario_manifest.json:341:        "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scenario_manifest.json:380:        "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scenario_manifest.json:393:        "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenario_manifest.json:406:        "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenario_manifest.json:445:        "sha256": "08cee15268021cccedfae4b5cf7c9c689a135fb20cf83861a72d433471250b1d"
tests/live_agentic_harness/scenario_manifest.json:451:      "descriptor_sha256": "12229915b1fc6a91fa40dbd8217de299577e02974cae4550af8f090cfa52797c",
tests/live_agentic_harness/scenario_manifest.json:497:        "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenario_manifest.json:555:      "descriptor_sha256": "04bf444c3c44edc850a0a4c9a19a3664b31fd0d8ff4cff13826befd4f8d06080",
tests/live_agentic_harness/scenario_manifest.json:642:      "descriptor_sha256": "2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457",
tests/live_agentic_harness/scenario_manifest.json:655:      "descriptor_sha256": "8f389a659ed1fcb982bd5512485075017864c4a5332e9dc23c29d7d7c88e6eab",
tests/live_agentic_harness/scenario_manifest.json:662:        "sha256": "c148b3b74fb11eb408e6cfb2150189075d1b122b64eb6a341775267404c62af9"
tests/live_agentic_harness/scenario_manifest.json:666:      "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenario_manifest.json:667:      "path": "tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json",
tests/live_agentic_harness/scenario_manifest.json:673:        "id": "506ebdde037e22d8",
tests/live_agentic_harness/scenario_manifest.json:674:        "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenario_manifest.json:688:        "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scenario_manifest.json:759:      "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scenario_manifest.json:766:        "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenario_manifest.json:779:        "sha256": "f344d3cb450634d608fb63fb8296e1b6cb49f84481e2adc534be7d198d7fac72"
tests/live_agentic_harness/scenario_manifest.json:792:        "sha256": "287ee5ba6b895449763a1f6589d6d5b66fa225844ace8892e957c62d07504d22"
tests/live_agentic_harness/scenario_manifest.json:824:      "descriptor_sha256": "9ae4a4234122da3701b9f19c218ee9f2b2d705f87cc506a2f3a8ed57f6218979",
tests/live_agentic_harness/scenario_manifest.json:831:        "sha256": "b3356f4640f638998d1eae50dd2ac775342c649d6d3a77940b93d6c72b762189"
tests/live_agentic_harness/scenario_manifest.json:837:      "descriptor_sha256": "e014838aa1dca64cd50ac288895928d490e197d5902c6dd37176981bb8e4466d",
tests/live_agentic_harness/scenario_manifest.json:922:        "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenario_manifest.json:928:      "descriptor_sha256": "5cd0755b3e83818619ba7e8dd40d360a2e419254b6f5394fd50eaca0de4dca80",
tests/live_agentic_harness/scenario_manifest.json:989:      "descriptor_sha256": "521376ee3a0b3c568644df355f791036ca6a034c6e9b0f4f4e78450c1953928d",
tests/live_agentic_harness/scenario_manifest.json:994:        "id": "59502aed6ad75d87",
tests/live_agentic_harness/scenario_manifest.json:995:        "path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scenario_manifest.json:1015:      "descriptor_sha256": "60a19bcef50943ef4134e0282d1d14a312df987354e5e3a03c0f380854d942e0",
tests/live_agentic_harness/scenario_manifest.json:1035:        "sha256": "0cf39ff1502b0029829a20c609b8a0caee6bfd45ee9472e327bdfdb95acf827c"
tests/live_agentic_harness/scenario_manifest.json:1041:      "descriptor_sha256": "d52d2cf1efae560d5cb49cd507321c8ae20290ecb723ad06b5674d6914bf59a1",
tests/live_agentic_harness/scenario_manifest.json:1087:        "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenario_manifest.json:1184:      "descriptor_sha256": "c18f241b403ed7d3c533330a9f4851f6e0870bb450c9d6edda713db827785be0",
tests/live_agentic_harness/scenario_manifest.json:1230:        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenario_manifest.json:1293:        "id": "71f825e4550c95b7",
tests/live_agentic_harness/scenario_manifest.json:1294:        "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenario_manifest.json:1295:        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
tests/live_agentic_harness/scenario_manifest.json:1311:        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenario_manifest.json:1376:        "sha256": "cf18d35e10586b45a798da007c09965f0abd89a5339a1d15507605c651fcdc22"
tests/live_agentic_harness/scenario_manifest.json:1386:        "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenario_manifest.json:1431:        "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scenario_manifest.json:1446:        "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scenario_manifest.json:1451:        "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenario_manifest.json:1456:        "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenario_manifest.json:1471:        "sha256": "08cee15268021cccedfae4b5cf7c9c689a135fb20cf83861a72d433471250b1d"
tests/live_agentic_harness/scenario_manifest.json:1491:        "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenario_manifest.json:1551:        "sha256": "c148b3b74fb11eb408e6cfb2150189075d1b122b64eb6a341775267404c62af9"
tests/live_agentic_harness/scenario_manifest.json:1553:      "multi-animatediff-video-face-swapping-with-deflicker-506ebd": {
tests/live_agentic_harness/scenario_manifest.json:1554:        "source_workflow_id": "506ebdde037e22d8",
tests/live_agentic_harness/scenario_manifest.json:1555:        "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenario_manifest.json:1561:        "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scenario_manifest.json:1591:        "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenario_manifest.json:1596:        "sha256": "f344d3cb450634d608fb63fb8296e1b6cb49f84481e2adc534be7d198d7fac72"
tests/live_agentic_harness/scenario_manifest.json:1601:        "sha256": "287ee5ba6b895449763a1f6589d6d5b66fa225844ace8892e957c62d07504d22"
tests/live_agentic_harness/scenario_manifest.json:1616:        "sha256": "b3356f4640f638998d1eae50dd2ac775342c649d6d3a77940b93d6c72b762189"
tests/live_agentic_harness/scenario_manifest.json:1651:        "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenario_manifest.json:1674:        "source_workflow_id": "59502aed6ad75d87",
tests/live_agentic_harness/scenario_manifest.json:1675:        "path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scenario_manifest.json:1691:        "sha256": "0cf39ff1502b0029829a20c609b8a0caee6bfd45ee9472e327bdfdb95acf827c"
tests/live_agentic_harness/scenario_manifest.json:1711:        "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenario_manifest.json:1766:        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenario_manifest.json:1789:        "source_workflow_id": "71f825e4550c95b7",
tests/live_agentic_harness/scenario_manifest.json:1790:        "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenario_manifest.json:1791:        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
tests/live_agentic_harness/scenario_manifest.json:1828:    "basis": "tests/live_agentic_harness/scenario_manifest.json (D13 authority)",
tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:2:  "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:4:  "workflow_path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:35:    "source_workflow_id": "506ebdde037e22d8",
tests/live_agentic_harness/fixtures/harness_child.py:21:import argparse
tests/live_agentic_harness/fixtures/harness_child.py:57:def main() -> int:
tests/live_agentic_harness/fixtures/harness_child.py:58:    parser = argparse.ArgumentParser(description=__doc__)
tests/live_agentic_harness/fixtures/harness_child.py:59:    parser.add_argument("--single-out", required=True)
tests/live_agentic_harness/fixtures/harness_child.py:60:    parser.add_argument("--scenario-id", default="fixture")
tests/live_agentic_harness/fixtures/harness_child.py:61:    parser.add_argument("--write-summary", action="store_true")
tests/live_agentic_harness/fixtures/harness_child.py:62:    parser.add_argument("--hold-stdio", action="store_true")
tests/live_agentic_harness/fixtures/harness_child.py:63:    parser.add_argument("--hang-after-summary", action="store_true")
tests/live_agentic_harness/runner.py:22:import argparse
tests/live_agentic_harness/runner.py:49:from .scenario_manifest import discover_manifest_scenarios
tests/live_agentic_harness/runner.py:661:    from .adapter import run_headless_scenario
tests/live_agentic_harness/runner.py:667:    summary = run_headless_scenario(
tests/live_agentic_harness/runner.py:931:def _build_parser() -> argparse.ArgumentParser:
tests/live_agentic_harness/runner.py:932:    parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
tests/live_agentic_harness/runner.py:933:    parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
tests/live_agentic_harness/runner.py:934:    parser.add_argument(
tests/live_agentic_harness/runner.py:939:    parser.add_argument(
tests/live_agentic_harness/runner.py:943:            "Authoritative scenario manifest (default: scenario_manifest.json "
tests/live_agentic_harness/runner.py:947:    parser.add_argument(
tests/live_agentic_harness/runner.py:952:    parser.add_argument(
tests/live_agentic_harness/runner.py:957:    parser.add_argument(
tests/live_agentic_harness/runner.py:962:    parser.add_argument(
tests/live_agentic_harness/runner.py:967:    parser.add_argument(
tests/live_agentic_harness/runner.py:973:    parser.add_argument(
tests/live_agentic_harness/runner.py:979:    parser.add_argument(
tests/live_agentic_harness/runner.py:988:    parser.add_argument(
tests/live_agentic_harness/runner.py:1001:    parser.add_argument(
tests/live_agentic_harness/runner.py:1010:    parser.add_argument(
tests/live_agentic_harness/runner.py:1015:    parser.add_argument(
tests/live_agentic_harness/runner.py:1020:    parser.add_argument(
tests/live_agentic_harness/runner.py:1025:    parser.add_argument(
tests/live_agentic_harness/runner.py:1031:    parser.add_argument(
tests/live_agentic_harness/runner.py:1037:    parser.add_argument(
tests/live_agentic_harness/runner.py:1042:    parser.add_argument(
tests/live_agentic_harness/runner.py:1047:    parser.add_argument(
tests/live_agentic_harness/runner.py:1052:    parser.add_argument(
tests/live_agentic_harness/runner.py:1058:    parser.add_argument(
tests/live_agentic_harness/runner.py:1068:def main(argv: list[str] | None = None) -> int:
tests/live_agentic_harness/scenfails32_manifest.json:29:    "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenfails32_manifest.json:35:   "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
tests/live_agentic_harness/scenfails32_manifest.json:48:   "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
tests/live_agentic_harness/scenfails32_manifest.json:159:    "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenfails32_manifest.json:172:    "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenfails32_manifest.json:185:    "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenfails32_manifest.json:204:   "descriptor_sha256": "2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457",
tests/live_agentic_harness/scenfails32_manifest.json:215:   "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails32_manifest.json:216:   "path": "tests/live_agentic_harness/scenfails32/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json",
tests/live_agentic_harness/scenfails32_manifest.json:222:    "id": "506ebdde037e22d8",
tests/live_agentic_harness/scenfails32_manifest.json:223:    "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails32_manifest.json:256:   "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scenfails32_manifest.json:263:    "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenfails32_manifest.json:315:    "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenfails32_manifest.json:321:   "descriptor_sha256": "60a19bcef50943ef4134e0282d1d14a312df987354e5e3a03c0f380854d942e0",
tests/live_agentic_harness/scenfails32_manifest.json:334:   "descriptor_sha256": "d52d2cf1efae560d5cb49cd507321c8ae20290ecb723ad06b5674d6914bf59a1",
tests/live_agentic_harness/scenfails32_manifest.json:354:    "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenfails32_manifest.json:458:    "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/research_assessment.py:66:``pytest tests/live_agentic_harness/research_assessment.py``).
tests/live_agentic_harness/research_assessment.py:466:#   .venv/bin/python -m pytest tests/live_agentic_harness/research_assessment.py
tests/live_agentic_harness/scen19/video-generates-a-video-from-a.json:4:  "workflow_path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scenfails57/video-wanvideo-text-to-video-generation-71f825.json:4:  "workflow_path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenfails57/video-wanvideo-text-to-video-generation-71f825.json:28:    "source_workflow_id": "71f825e4550c95b7",
tests/live_agentic_harness/scenfails57/video-wanvideo-text-to-video-generation-71f825.json:39:    "workflow_path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:4:  "workflow_path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:28:    "source_workflow_id": "71f825e4550c95b7",
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:39:    "workflow_path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenarios/video-generates-a-video-from-a.json:4:  "workflow_path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:2:  "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:4:  "workflow_path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:35:    "source_workflow_id": "506ebdde037e22d8",
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:2:  "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:4:  "workflow_path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:35:    "source_workflow_id": "506ebdde037e22d8",
21:LEDGER_PATH = ROOT / "tests/fixtures/agent_edit/compatibility_ledger.md"
22:ARCHITECTURE_LEDGER_PATH = ROOT / "docs/architecture/compatibility-ledger.md"
153:    text = LEDGER_PATH.read_text(encoding="utf-8")
164:        "fixture": LEDGER_PATH.read_text(encoding="utf-8"),
165:        "architecture": ARCHITECTURE_LEDGER_PATH.read_text(encoding="utf-8"),
174:    text = LEDGER_PATH.read_text(encoding="utf-8")
246:    architecture_text = ARCHITECTURE_LEDGER_PATH.read_text(encoding="utf-8")
# Live Agentic Tests

This directory is for **live agentic tests only**: real executor paths with
real model/provider calls.

A test belongs here only when the subject-under-test is a real model or agent
using production-like tools, and the evidence comes from the actual run. Fake or
faking actors, deterministic builders, scripted `messages.jsonl`, and structural
contract scenarios do not belong here.

The selected live lane is fixed by `scenario_manifest.json`. Before starting
scenario subprocesses, the runner validates descriptor IDs/paths/hashes,
source-workflow IDs/paths/hashes, and exact directory membership. A missing,
changed, duplicate, or stray descriptor fails preflight. `--manifest` can select
another equally strict manifest for an explicit scenario directory.

Deterministic real-workflow agentic scenarios live in
`tests/structural_harness/` as **structural agentic tests**:

```bash
python -m tests.structural_harness.runner --mode structural --actor fake --tag run
```

## Operator Commands

Run all live-headless scenarios in this directory:

```bash
python -m tests.live_agentic_harness.runner --tag live-headless-smoke --json
```

Run against an explicit scenario directory and output root:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-smoke \
  --scenarios-dir tests/live_agentic_harness/scenarios \
  --output-base out/agentic \
  --json
```

Each scenario writes artifacts under `out/agentic/<tag>/<scenario_id>/` and is
then checked by `tests.live_agentic_harness.guard.guard_output_dir`. A live success
requires `flow_kind=live_agentic_headless`, `live=true`, `status=success`,
`dispatcher=real`, and `model_behavior=agentic`. Fake/faking dispatchers and
non-agentic model behavior are rejected for live-headless artifacts.

Blocked provider readiness is a valid harness outcome but not a live success.
It should produce `status=blocked_prerequisite` in `flow_metadata.json` and a
nonzero runner exit when any scenario is blocked.

For the full boundary matrix, `live=false` versus `dry_run` semantics, dry-run
CLI invocation, blocked-prerequisite smoke checks, browser e2e commands, and
subprocess integration contract, see
`../../docs/testing/headless-agentic-harnesses.md`.
"""Guards for the agent-edit legacy alias compatibility ledger."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
    Path("vibecomfy/comfy_nodes/agent"),
    Path("vibecomfy/comfy_nodes/web"),
    Path("tests/fixtures/payload_contracts"),
    Path("tests/fixtures/e2e_sessions"),
    Path("tests/characterization"),
)

TEXT_SUFFIXES = {".js", ".mjs", ".py", ".json", ".md", ".txt"}

LEDGER_PATH = ROOT / "tests/fixtures/agent_edit/compatibility_ledger.md"
ARCHITECTURE_LEDGER_PATH = ROOT / "docs/architecture/compatibility-ledger.md"

ALIAS_PATTERNS = {
    "queue_allowed": re.compile(r"\bqueue_allowed\b"),
    "candidate_graph": re.compile(r"\bcandidate_graph\b"),
}

# 2026-06-24 M2 alias-token inventory across SCAN_ROOTS before tightening:
# queue_allowed: 16 files / ~169 hits; candidate_graph: 11 files / ~56 hits;
# candidate_graph_hash: 9 files / ~93 hits. Only queue_allowed and
# candidate_graph are compatibility-specific and bounded enough for explicit
# scanner allowlists. candidate_graph_hash is canonical; apply_eligible and
# apply_eligibility are broader apply-eligibility behavior surfaces, so keep
# those covered by adapter/contract behavior tests instead of broad regex
# scanner allowlists.
ALLOWED_ALIAS_FILES = {
    "queue_allowed": {
        "tests/fixtures/payload_contracts/agent_edit_accept_response.json",
        "tests/fixtures/payload_contracts/agent_edit_rebaseline_response.json",
        "tests/fixtures/payload_contracts/chat_rehydrate_response.json",
        "vibecomfy/comfy_nodes/agent/_frag_chat.py",
        "vibecomfy/comfy_nodes/agent/_frag_humanize.py",
        "vibecomfy/comfy_nodes/agent/_frag_response_contract.py",
        "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py",
        "vibecomfy/comfy_nodes/agent/audit.py",
        "vibecomfy/comfy_nodes/agent/authority_receipts.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/executor_response.py",
        "vibecomfy/comfy_nodes/agent/executor_durable.py",
        "vibecomfy/comfy_nodes/agent/gates.py",
        "vibecomfy/comfy_nodes/agent/reorganise.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/panel_overlay.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
    "candidate_graph": {
        "vibecomfy/comfy_nodes/agent/_frag_batch_loop.py",
        "vibecomfy/comfy_nodes/agent/_frag_research.py",
        "vibecomfy/comfy_nodes/agent/_frag_response_contract.py",
        "vibecomfy/comfy_nodes/agent/_frag_revision_stages.py",
        "vibecomfy/comfy_nodes/agent/_turn_state_machine.py",
        "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py",
        "vibecomfy/comfy_nodes/agent/candidate_transaction.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit.py",
        "vibecomfy/comfy_nodes/agent/edit_batch_repl.py",
        "vibecomfy/comfy_nodes/agent/execution_plan_runtime.py",
        "vibecomfy/comfy_nodes/agent/executor_response.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract.js",
        "vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js",
        "vibecomfy/comfy_nodes/web/agent_status_poller.js",
        "vibecomfy/comfy_nodes/web/agentic_replay.js",
        "vibecomfy/comfy_nodes/web/preview_picker.js",
        "vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js",
    },
}

PROHIBITED_ALLOWLIST_FRAGMENTS = (
    "panel_thread.js",
    "agent_edit_lifecycle_transcript",
    "transcript",
    "detail_selector",
    "bubble_detail",
    "model_provider",
    "provider_model",
)

FIXTURE_TOKEN_CLASSIFICATION_ANCHORS = {
    "_CLARIFY_FORBIDDEN_KEYS": (
        "### Clarify/noop forbidden-key guards",
        "retained legacy alias",
        "_CLARIFY_FORBIDDEN_KEYS`; it aliases `_NON_APPLYABLE_FORBIDDEN_KEYS`",
    ),
    "_CLARIFY_FORBIDDEN_RESPONSE_KEYS": (
        "### Edit-layer clarify-response sanitizer",
        "owned by response assembly",
        "keep it separate from the route-layer guard",
    ),
    "_strip_clarify_forbidden_response_fields": (
        "### Edit-layer clarify-response sanitizer",
        "_sanitize_pure_clarify_response",
        "may have added candidate/apply aliases",
    ),
    "apply_eligible": (
        "### `apply_eligible`",
        "Canonical executor/apply authorization bit",
        "N/A for the canonical authorization field",
    ),
    "candidate_graph_hash": (
        "### Graph hash fields",
        "active/session/diagnostic fields, not removable legacy aliases",
        "not removable legacy aliases",
    ),
    "client_graph_hash": (
        "### Graph hash fields",
        "active/session/diagnostic fields, not removable legacy aliases",
        "not removable legacy aliases",
    ),
    "graph": (
        "### `candidate_graph` / `graph` legacy candidate aliases",
        "top-level `candidate_graph` or `graph` alias",
        "status/debug, or compatibility display inputs",
    ),
    "action_client_graph_hash": (
        "### `submitted_client_graph_hash` / `action_client_graph_hash`",
        "Session migration/action-validation fields",
        "records `action_client_graph_hash`",
    ),
    "submitted_client_graph_hash": (
        "### `submitted_client_graph_hash` / `action_client_graph_hash`",
        "Session migration/action-validation fields",
        "Session allocation stores `submitted_client_graph_hash`",
    ),
}


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        for path in (ROOT / scan_root).rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return sorted(files)


def _ledger_scannable_backend_aliases() -> set[str]:
    text = LEDGER_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"Deliberately scannable bounded backend aliases:\s*(?P<aliases>.+)",
        text,
    )
    assert match, "Compatibility ledger must list deliberately scannable backend aliases."
    return set(re.findall(r"`([^`]+)`", match.group("aliases")))


def _read_ledgers() -> dict[str, str]:
    return {
        "fixture": LEDGER_PATH.read_text(encoding="utf-8"),
        "architecture": ARCHITECTURE_LEDGER_PATH.read_text(encoding="utf-8"),
    }


def _normalized_ledgers() -> dict[str, str]:
    return {name: re.sub(r"\s+", " ", text) for name, text in _read_ledgers().items()}


def _fixture_retained_alias_tokens_by_row() -> dict[str, str]:
    text = LEDGER_PATH.read_text(encoding="utf-8")
    header = "| Alias or shape | Owner | Allowed files | Fixture coverage | Deletion trigger |"
    in_table = False
    tokens_by_row: dict[str, str] = {}

    for line in text.splitlines():
        if line == header:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue
        for token in re.findall(r"`([^`]+)`", cells[0]):
            assert token not in tokens_by_row, f"duplicate fixture ledger table token: {token}"
            tokens_by_row[token] = cells[0]

    assert tokens_by_row, "Fixture compatibility ledger retained-alias table has no tokens."
    return tokens_by_row


def test_agent_edit_legacy_aliases_stay_inside_compatibility_ledger_allowlist() -> None:
    violations: list[str] = []

    for path in _iter_text_files():
        rel_path = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for alias_name, pattern in ALIAS_PATTERNS.items():
            if rel_path in ALLOWED_ALIAS_FILES[alias_name]:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    violations.append(f"{alias_name}: {rel_path}:{line_number}: {line.strip()}")

    assert not violations, (
        "Legacy agent-edit aliases must stay within tests/fixtures/agent_edit/"
        "compatibility_ledger.md allowlists:\n" + "\n".join(violations)
    )


def test_ledger_listed_scannable_backend_aliases_have_scanner_patterns() -> None:
    scannable_aliases = _ledger_scannable_backend_aliases()

    assert scannable_aliases == {

exec
/bin/zsh -lc "python - <<'PY'
import json
from pathlib import Path
for p in sorted(Path('tests/live_agentic_harness').glob('*manifest.json')):
 d=json.loads(p.read_text())
 if isinstance(d,dict):
  xs=d.get('scenarios',d.get('entries',[]))
  print(p, len(xs) if isinstance(xs,list) else type(xs).__name__, list(d)[:8])
print('scenarios dir',len(list(Path('tests/live_agentic_harness/scenarios').glob('*.json'))))
print('scenfails57 dir',len(list(Path('tests/live_agentic_harness/scenfails57').glob('*.json'))))
PY
sed -n '900,1095p' tests/live_agentic_harness/runner.py
sed -n '1,220p' tests/live_agentic_harness/scenario_manifest.py
sed -n '1,250p' vibecomfy/comfy_nodes/agent/session.py
sed -n '1,120p' vibecomfy/porting/edit/_parse_execute.py
sed -n '1,250p' vibecomfy/porting/edit/session.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
zsh:1: can't create temp file for here document: operation not permitted

        threads = [
            threading.Thread(target=worker, args=(i, p), daemon=True)
            for i, p in enumerate(paths)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        for f in tmpdir.iterdir():
            try:
                if f.is_file():
                    f.unlink()
            except Exception:  # noqa: BLE001
                pass
        try:
            tmpdir.rmdir()
        except Exception:  # noqa: BLE001
            pass

    return _persist_run_summary(
        tag,
        results,
        output_base,
        total_scenarios=len(paths),
        complete=True,
        transport=transport,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
    parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
    parser.add_argument(
        "--scenarios-dir",
        default=None,
        help="Directory containing scenario YAML/JSON files.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Authoritative scenario manifest (default: scenario_manifest.json "
            "beside the scenarios directory)."
        ),
    )
    parser.add_argument(
        "--output-base",
        default=None,
        help="Base evidence directory (default: out/agentic).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary instead of a short report.",
    )
    parser.add_argument(
        "--single",
        default=None,
        help="Run a SINGLE scenario file (subprocess entry point for parallel mode).",
    )
    parser.add_argument(
        "--single-out",
        default=None,
        help="Path to write the single-scenario summary JSON (used with --single).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"max concurrent scenarios (default {DEFAULT_MAX_WORKERS}).",
    )
    parser.add_argument(
        "--per-scenario-timeout",
        type=int,
        default=DEFAULT_PER_SCENARIO_TIMEOUT,
        help=f"per-scenario seconds before kill (default {DEFAULT_PER_SCENARIO_TIMEOUT}).",
    )
    parser.add_argument(
        "--infra-retries",
        type=int,
        default=DEFAULT_INFRA_RETRIES,
        help=(
            "retry subprocess-level infrastructure failures this many times "
            f"(default {DEFAULT_INFRA_RETRIES}; semantic guard failures are not retried)"
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("openrouter", "native"),
        default=None,
        help=(
            "Explicit model-call transport for every profile phase "
            "(classify/research/implement/reply). When set, ambient "
            "credentials/base URLs can never select the transport; the child "
            "environment is pinned and this flag is forwarded to every "
            "subprocess. Default: the canonical product route (openrouter), "
            "pinned — never an ambient credential."
        ),
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help=(
            "emit and persist aggregate progress every N completed scenarios "
            f"(default {DEFAULT_PROGRESS_EVERY}; 0 disables stderr progress)"
        ),
    )
    parser.add_argument(
        "--prepare-failure-analysis",
        action="store_true",
        help="Write per-failed-scenario analysis briefs and index without calling subagents.",
    )
    parser.add_argument(
        "--analyze-failures",
        action="store_true",
        help="After the run, launch one DeepSeek/Hermes diagnosis subagent per failed scenario.",
    )
    parser.add_argument(
        "--analysis-model",
        default=DEFAULT_ANALYSIS_MODEL,
        help=f"Model for per-failure diagnosis agents (default {DEFAULT_ANALYSIS_MODEL}).",
    )
    parser.add_argument(
        "--analysis-max-workers",
        type=int,
        default=DEFAULT_ANALYSIS_WORKERS,
        help=f"Maximum concurrent failure diagnosis agents (default {DEFAULT_ANALYSIS_WORKERS}).",
    )
    parser.add_argument(
        "--analysis-timeout",
        type=int,
        default=DEFAULT_AGENT_TIMEOUT_S,
        help=f"Seconds before killing one failure diagnosis agent (default {DEFAULT_AGENT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--restart-failure-analysis",
        action="store_true",
        help="Rerun every failed-scenario diagnosis, including ones already marked done.",
    )
    parser.add_argument(
        "--recommend-fixes",
        action="store_true",
        help="Use Codex/GPT-5.5 to synthesize all failure diagnoses into ranked fix recommendations.",
    )
    parser.add_argument(
        "--recommendations-model",
        default=DEFAULT_RECOMMENDATIONS_MODEL,
        help=f"Model for aggregate fix recommendations (default {DEFAULT_RECOMMENDATIONS_MODEL}).",
    )
    parser.add_argument(
        "--recommendations-timeout",
        type=int,
        default=DEFAULT_AGENT_TIMEOUT_S,
        help=f"Seconds before killing aggregate recommendations (default {DEFAULT_AGENT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--analyze-existing-summary",
        default=None,
        help=(
            "Analyze an existing run_summary.json or redirected summary JSON instead of running scenarios."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else Path(__file__).with_name("scenarios")

    if args.analyze_existing_summary:
        analysis = _run_failure_analysis_from_summary(
            Path(args.analyze_existing_summary),
            scenarios_dir=scenarios_dir,
            analyze_failures_enabled=args.analyze_failures,
            prepare_only=args.prepare_failure_analysis
            or not (args.analyze_failures or args.recommend_fixes),
            recommend_fixes=args.recommend_fixes,
            analysis_model=args.analysis_model,
            analysis_max_workers=args.analysis_max_workers,
            analysis_timeout=args.analysis_timeout,
            resume_failure_analysis=not args.restart_failure_analysis,
            recommendations_model=args.recommendations_model,
            recommendations_timeout=args.recommendations_timeout,
        )
        print(json.dumps({"failure_analysis": analysis}, indent=2, default=str))
        return 0

    if not args.tag:
        parser.error("--tag is required unless --analyze-existing-summary is used")

    if args.single:
"""Authoritative scenario-manifest generation and validation.

The live lane is descriptor-addressed: the manifest fixes both the selected
scenario set and every scenario/source-workflow byte stream before model calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIOS_DIR = Path(__file__).with_name("scenarios")
DEFAULT_MANIFEST_PATH = Path(__file__).with_name("scenario_manifest.json")
DESCRIPTOR_SUFFIXES = {".json", ".yaml", ".yml"}


class ScenarioManifestError(ValueError):
    """Raised when the selected live-agentic corpus differs from its manifest."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path_for(scenarios_dir: Path) -> Path:
    if scenarios_dir.resolve() == DEFAULT_SCENARIOS_DIR.resolve():
        return DEFAULT_MANIFEST_PATH
    return scenarios_dir.parent / "scenario_manifest.json"


def _repo_relative(path: Path, *, repo: Path) -> str:
    try:
        # Keep the checkout-relative symlink spelling (not the symlink target),
        # because external_workflows/ is intentionally mounted into worktrees.
        return path.absolute().relative_to(repo.absolute()).as_posix()
    except ValueError as exc:
        raise ScenarioManifestError(f"manifest path escapes repository root: {path}") from exc


def _effective_repo(scenarios_dir: Path, repo: Path) -> Path:
    """Use the real repo for lane data and a temp parent for isolated tests."""
    try:
        scenarios_dir.absolute().relative_to(repo.absolute())
    except ValueError:
        return scenarios_dir.parent
    return repo


def build_manifest(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    *,
    repo: Path = REPO,
    revised_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic manifest for descriptor files already on disk."""
    repo = _effective_repo(scenarios_dir, repo)
    revised_ids = revised_ids or set()
    entries: list[dict[str, Any]] = []
    for path in sorted(
        item for item in scenarios_dir.iterdir() if item.suffix in DESCRIPTOR_SUFFIXES
    ):
        if path.suffix != ".json":
            raise ScenarioManifestError(f"authoritative scenarios must be JSON: {path}")
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(scenario, Mapping):
            raise ScenarioManifestError(f"scenario descriptor must contain an object: {path}")
        scenario_id = str(scenario.get("id") or "")
        if not scenario_id or scenario_id != path.stem:
            raise ScenarioManifestError(
                f"scenario id/stem mismatch: id={scenario_id!r}, path={path}"
            )
        workflow_path = scenario.get("workflow_path")
        source_workflow: dict[str, str] | None = None
        if workflow_path:
            source_path = Path(str(workflow_path))
            if not source_path.is_absolute():
                source_path = repo / source_path
            if not source_path.is_file():
                raise ScenarioManifestError(
                    f"scenario {scenario_id!r} workflow_path does not resolve: {workflow_path}"
                )
            source_id = str((scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem)
            source_workflow = {
                "id": source_id,
                "path": _repo_relative(source_path, repo=repo),
                "sha256": sha256_file(source_path),
            }
        scenario_kind = "edit"
        if (scenario.get("classification") or {}).get("kind") == "health_control":
            scenario_kind = "health_control"
        elif scenario.get("answer_rubric"):
            scenario_kind = "semantic_product"
        entries.append(
            {
                "id": scenario_id,
                "path": _repo_relative(path, repo=repo),
                "descriptor_sha256": sha256_file(path),
                "inclusion_status": "included",
                "revision_status": "revised" if scenario_id in revised_ids else "matched",
                "scenario_kind": scenario_kind,
                "source_workflow": source_workflow,
            }
        )
    return {
        "schema_version": 1,
        "scenario_root": _repo_relative(scenarios_dir, repo=repo),
        "scenario_count": len(entries),
        "entries": entries,
    }


def write_manifest(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    *,
    manifest_path: Path | None = None,
    repo: Path = REPO,
    revised_ids: set[str] | None = None,
) -> Path:
    """Write a deterministic manifest. Used by corpus maintenance and tests."""
    target = manifest_path or manifest_path_for(scenarios_dir)
    payload = build_manifest(scenarios_dir, repo=repo, revised_ids=revised_ids)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def discover_manifest_scenarios(
    scenarios_dir: Path = DEFAULT_SCENARIOS_DIR,
    *,
    manifest_path: Path | None = None,
    repo: Path = REPO,
) -> list[Path]:
    """Validate the complete manifest contract and return included paths in order."""
    repo = _effective_repo(scenarios_dir, repo)
    manifest_path = manifest_path or manifest_path_for(scenarios_dir)
    if not manifest_path.is_file():
        raise ScenarioManifestError(f"scenario manifest is missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioManifestError(f"scenario manifest is unreadable: {exc}") from exc
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != 1:
        raise ScenarioManifestError("scenario manifest schema_version must be 1")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ScenarioManifestError("scenario manifest entries must be a list")

    expected_root = _repo_relative(scenarios_dir, repo=repo)
    if manifest.get("scenario_root") != expected_root:
        raise ScenarioManifestError(
            f"scenario_root mismatch: expected {expected_root!r}, got {manifest.get('scenario_root')!r}"
        )

    selected: list[Path] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ScenarioManifestError(f"manifest entry {index} must be an object")
        inclusion_status = entry.get("inclusion_status")
        if inclusion_status not in {"included", "excluded"}:
            raise ScenarioManifestError(
                f"manifest entry {index} has invalid inclusion_status: {inclusion_status!r}"
            )
        scenario_id = str(entry.get("id") or "")
        rel_path = str(entry.get("path") or "")
        if not scenario_id or scenario_id in seen_ids:
            raise ScenarioManifestError(f"missing or duplicate scenario id: {scenario_id!r}")
        if not rel_path or rel_path in seen_paths:
            raise ScenarioManifestError(f"missing or duplicate scenario path: {rel_path!r}")
        seen_ids.add(scenario_id)
        seen_paths.add(rel_path)
        path = repo / rel_path
        try:
            path.resolve().relative_to(scenarios_dir.resolve())
        except ValueError as exc:
            raise ScenarioManifestError(f"scenario path is outside scenario_root: {rel_path}") from exc
        if not path.is_file():
            raise ScenarioManifestError(f"manifested scenario is missing: {rel_path}")
        if path.stem != scenario_id:
            raise ScenarioManifestError(
                f"manifest id/path-stem mismatch: id={scenario_id!r}, path={rel_path!r}"
            )
        actual_descriptor_hash = sha256_file(path)
        if actual_descriptor_hash != entry.get("descriptor_sha256"):
            raise ScenarioManifestError(
                f"scenario descriptor hash mismatch for {scenario_id}: "
                f"expected {entry.get('descriptor_sha256')}, got {actual_descriptor_hash}"
            )
        try:
            scenario = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenarioManifestError(
                f"scenario descriptor is unreadable for {scenario_id}: {exc}"
            ) from exc
        if not isinstance(scenario, Mapping):
            raise ScenarioManifestError(
                f"scenario descriptor must contain an object for {scenario_id}"
            )
        if scenario.get("id") != scenario_id:
            raise ScenarioManifestError(
                f"descriptor id mismatch for {scenario_id}: got {scenario.get('id')!r}"
            )
        workflow_path = scenario.get("workflow_path")
        source = entry.get("source_workflow")
        if workflow_path:
            if not isinstance(source, Mapping):
                raise ScenarioManifestError(f"source workflow metadata missing for {scenario_id}")
            source_path = repo / str(source.get("path") or "")
            expected_source_path = Path(str(workflow_path))
            if not expected_source_path.is_absolute():
                expected_source_path = repo / expected_source_path
            if source_path.resolve() != expected_source_path.resolve():
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import socket
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterator, Literal

from .contracts import DiagnosticRecord, FailureEnvelope, FailureKind, TurnContext, failure_envelope
from .candidate_transaction import (
    CANDIDATE_TRANSACTION_V2,
    CANDIDATE_TRANSACTION_FILENAME,
    LAYOUT_VERIFICATION_CONTRACT_VERSION,
    LAYOUT_VERIFICATION_PROJECTION,
    build_candidate_transaction,
    canonical_transaction_state,
    classify_legacy_migration_v1,
    project_transaction_state,
    validate_candidate_transaction,
)
from .projection_registry_v1 import (
    ContractError,
    browser_layout_scope_issues_v1 as _registry_browser_layout_scope_issues,
    build_layout_graph_projection as _registry_layout_graph_projection,
    build_structural_graph_projection as _registry_structural_graph_projection,
    canonical_json_bytes_v1 as _registry_canonical_json_bytes,
    layout_graph_hash_compat as _registry_layout_graph_hash,
    projection_reference_v1,
    structural_graph_hash_compat as _registry_structural_graph_hash,
    workflow_identity_v1,
)
from .mutation_materialization_v1 import build_mutation_materialization_v1
from .layout_operation_v1 import build_layout_operation_envelope
from vibecomfy.porting.edit.ops import parse_edit_delta

_LOGGER = logging.getLogger(__name__)

STATE_FILE_NAME = "session_state.json"
LOCK_FILE_NAME = ".session_state.lock"
STATE_SCHEMA_VERSION = 1
# Bumped whenever `structural_graph_projection` changes shape. A baseline hash
# stored by an older version is recomputed from the on-disk accepted graph on
# read, so a projection change never strands an open session on a stale baseline
# it can no longer match (the StaleStateMismatch-on-every-submit failure mode).
STRUCTURAL_PROJECTION_VERSION = 3
DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_LEASE_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.025

# ── Phase 4 transactional storage constants (T19) ───────────────────────────
# Authoritative per-turn artifacts live under
# ``turns/<turn_id>/transactions/<plan_hash>/``.  The append-only
# ``lifecycle_events.jsonl`` is the single source of truth; the ``*.json``
# receipt snapshots are derived for fast reload, and the
# ``session_state.json`` index entries are a discoverable cache that can always
# be rebuilt from the artifacts (see ``recover_transaction_index``).
TRANSACTIONS_DIR_NAME = "transactions"
TRANSACTION_LIFECYCLE_LOG_NAME = "lifecycle_events.jsonl"
TRANSACTION_PREPARED_RECEIPT_NAME = "prepared.json"
TRANSACTION_VERIFIED_RECEIPT_NAME = "canvas_verified.json"
TRANSACTION_FINALIZED_RECEIPT_NAME = "finalized.json"
TRANSACTION_ROLLBACK_RECEIPT_NAME = "rollback.json"
# Event-type → receipt snapshot filename (the snapshot is derived from the event).
TRANSACTION_RECEIPT_BY_EVENT: Mapping[str, str] = MappingProxyType(
    {
        "prepared": TRANSACTION_PREPARED_RECEIPT_NAME,
        "finalized": TRANSACTION_FINALIZED_RECEIPT_NAME,
        "canvas_verified": TRANSACTION_VERIFIED_RECEIPT_NAME,
        "rollback_complete": TRANSACTION_ROLLBACK_RECEIPT_NAME,
        # Read-only historical adapter.
        "rolled_back": TRANSACTION_ROLLBACK_RECEIPT_NAME,
    }
)
# Lifecycle phases that resolve a transaction (no longer merely "prepared").
_TRANSACTION_RESOLVED_PHASES: frozenset[str] = frozenset(
    {
        "finalized",
        "rollback_complete",
        "discarded",
        "superseded",
        # Read-only historical adapter.
        "rolled_back",
        "cancelled",
    }
)

def _process_alive(pid: int) -> bool:
    """Return ``True`` when a process with *pid* exists on this host."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    else:
        return True


OperationScope = Literal["edit", "accept", "reject", "rebaseline"]
# ── TurnState lifecycle ──────────────────────────────────────────────────
# V1 historical states (read-only migration; never authored for new turns):
#   candidate, accepted, rejected, unknown, no_candidate
#
# V2 lifecycle states (authored for turns with agent_edit_protocol >= v2_delta):
#   submitted         – turn allocated, no candidate yet
#   candidate_ready   – candidate computed and persisted, ready for review
#   review_bound      – candidate has been reviewed / previewed by browser
#   prepared          – prepare route completed (CAS without baseline advance)
#   canvas_verified   – browser verified post-apply canvas hash matches plan hash
#   finalized         – finalize route succeeded; baseline advanced
#   rollback_complete – rollback confirmed and baseline restored
#   discarded         – unprepared candidate explicitly rejected by the user
#
# Valid V2 forward transitions (every state reachable from submitted):
#   submitted       → candidate_ready
#   candidate_ready → review_bound
#   review_bound    → prepared
#   prepared        → canvas_verified  | rollback_complete
#   canvas_verified → finalized        | rollback_complete
#   finalized       → (terminal)
#   rollback_complete → (terminal)
#   candidate_ready / review_bound → discarded (terminal, baseline unchanged)
# V2 turns can also transition to unknown (superseded) from any pre-finalized state.
TurnState = Literal[
    # V1 historical (read-only migration)
    "candidate",
    "accepted",
    "rejected",
    "unknown",
    "no_candidate",
    # V2 lifecycle
    "submitted",
    "candidate_ready",
    "review_bound",
    "prepared",
    "canvas_verified",
    "finalized",
    "rollback_complete",
    "discarded",
    "recoverable_error",
    "superseded",
]

# V2 states that are terminal / should not be mutated further by accept/reject.
_V2_TERMINAL_STATES: frozenset[TurnState] = frozenset(
    {"finalized", "rollback_complete", "discarded", "superseded"}
)

# V2 states that are pre-finalize / still mutable.
_V2_PRE_FINALIZE_STATES: frozenset[TurnState] = frozenset({
    "submitted",
    "candidate_ready",
    "review_bound",
    "prepared",
    "canvas_verified",
    "recoverable_error",
})

# Durable states whose turn still owns a candidate that the browser must be
# able to rehydrate.  Keep this separate from ``_V2_PRE_FINALIZE_STATES``:
# ``submitted`` has no candidate yet, while the legacy ``candidate`` state is
# still a reviewable persisted state during the V1 migration window.
REVIEWABLE_CANDIDATE_STATES: frozenset[TurnState] = frozenset({
    "candidate",
    "candidate_ready",
    "review_bound",
    "prepared",
    "canvas_verified",
    "recoverable_error",
})

# Historical V1 states that may appear in persisted state files.
_V1_HISTORICAL_STATES: frozenset[TurnState] = frozenset({
    "candidate",
    "accepted",
    "rejected",
    "unknown",
    "no_candidate",
})
# Event-type → V2 TurnState it represents (the latest event of a transaction
# pins the turn's authoritative lifecycle state after recovery).
_TRANSACTION_EVENT_TO_TURN_STATE: Mapping[str, TurnState] = MappingProxyType(
    {
        "prepared": "prepared",
        "finalized": "finalized",
        "rolled_back": "rollback_complete",
        "rollback_complete": "rollback_complete",
        "discarded": "discarded",
        "cancelled": "superseded",
        "superseded": "superseded",
        "canvas_verified": "canvas_verified",
    }
)
BaselineSource = Literal["none", "turn", "rebaseline", "legacy"]
RebaselineReason = Literal["undo", "stale_state_recovery", "continue_from_canvas"]
REBASELINE_REASONS: tuple[RebaselineReason, ...] = (
    "undo",
    "stale_state_recovery",
    "continue_from_canvas",
)


@dataclass(frozen=True)
class IdempotencyReplay:
    response: dict[str, Any]
    record: dict[str, Any]


@dataclass(frozen=True)
class IdempotencyConflict:
    failure: FailureEnvelope
    record: dict[str, Any]


@dataclass(frozen=True)
class TurnAllocation:
    context: TurnContext
    session_dir: Path
    turn_dir: Path
    state: dict[str, Any]
    request_hash: str
    unknown_transitions: tuple[dict[str, Any], ...] = ()
    idempotency_record_key: str | None = None
    replay: IdempotencyReplay | None = None
    conflict: IdempotencyConflict | None = None


@dataclass(frozen=True)
class ExpectedBaseline:
    reliable: bool
    graph_hash: str | None
    hash_kind: str | None
    source: str | None
    reason: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class RebaselineReplay:
from __future__ import annotations

import ast
from typing import Any

from vibecomfy.porting.edit.ops import EditOp
from vibecomfy.porting.edit._session_types import (
    BatchResult,
    CompactDiagnostic,
    StatementResult,
    _ExpandedStatement,
    _diag,
)
from vibecomfy.porting.edit._parse import (
    _parse_and_validate_batch,
)
from vibecomfy.porting.edit._ir_utils import _uids_for_op


class _ParseExecuteMixin:

    def apply_batch(self, code: str) -> BatchResult:
        """Apply one Python batch through ``interpret(pre, batch)``.

        Mutation authority is the immutable interpreter.  The retained IR
        is the only session graph.  Query statements (search / python /
        tools) are overlaid after interpret so the agent still sees typed
        catalog results.
        """
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
        from vibecomfy.porting.edit._interpret import interpret

        parsed = _parse_and_validate_batch(
            code,
            max_batch_bytes=self.max_batch_bytes,
            max_statements=self.max_statements,
            max_expanded_statements=self.max_expanded_statements,
            max_for_iterations=self.max_for_iterations,
        )
        if parsed.diagnostics:
            return BatchResult(
                ok=False,
                statements=parsed.statements,
                diagnostics=parsed.diagnostics,
            )
        snapshot = self._snapshot_mutable_state()
        try:
            if self.workflow is None:
                raise RuntimeError("EditSession.apply_batch requires a retained IR")
            pre_ir = _cow_workflow_copy(self.workflow)
            cas_old = self._cas_snapshot(pre_ir)
            interpreted = interpret(
                pre_ir,
                code,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
                cas_old=cas_old,
                name_hints=self._transient_name_index,
            )
            statement_results = [
                self._statement_result_from_outcome(outcome)
                for outcome in interpreted.statements
            ]
            statement_results = self._overlay_query_results(
                parsed.expanded, statement_results
            )
            apply_gate_eligible = True
            if interpreted.ok and interpreted.landed_ops:
                from vibecomfy.porting.edit.apply_gate import verify_apply

                gate = verify_apply(
                    pre_ir,
                    interpreted.workflow,
                    delta=code,
                    landed_ops=interpreted.landed_ops,
                    schema_provider=self.schema_provider,
                )
                apply_gate_eligible = gate.apply_eligible
                if not gate.ok:
                    rejected = tuple(
                        StatementResult(
                            statement_index=item.statement_index,
                            source=item.source,
                            ok=False,
                            landed=False,
                            op_kind=item.op_kind,
                            diagnostics=item.diagnostics + gate.diagnostics,
                            detail=dict(item.detail),
                            touched_uids=item.touched_uids,
                            dependency_cause=item.dependency_cause,
                            teaching_hint=item.teaching_hint,
                            status="rejected",
                            reason=gate.reason or "apply_gate_rejected",
                        )
                        if item.landed
                        else item
                        for item in statement_results
                    )
                    return BatchResult(
                        ok=False,
                        statements=rejected,
                        diagnostics=interpreted.diagnostics + gate.diagnostics,
                        landed_ops=(),
                        apply_eligible=False,
                    )
            if interpreted.landed_ops:
                self.workflow = interpreted.workflow
                if getattr(self, "history", None) is None:
                    self.history = []
                # The accepted batch IS the Δ.  Each history entry records
                # (wf_i, source, landed_ops) — the Python-surface source AND
                # the typed ops the grammar yields are the same batch value.
                self.history.append(
                    (pre_ir, code, tuple(interpreted.landed_ops))
                )
                self.landed_ops.extend(interpreted.landed_ops)
                self.resolved_ops = []
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping


class _ImmutableList(list):
    """List that compares like a list but rejects mutation."""

    def _frozen(self, *_args: Any, **_kwargs: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")

    __setitem__ = _frozen  # type: ignore[assignment]
    __delitem__ = _frozen  # type: ignore[assignment]
    append = _frozen  # type: ignore[assignment]
    extend = _frozen  # type: ignore[assignment]
    insert = _frozen  # type: ignore[assignment]
    pop = _frozen  # type: ignore[assignment]
    remove = _frozen  # type: ignore[assignment]
    clear = _frozen  # type: ignore[assignment]
    sort = _frozen  # type: ignore[assignment]
    reverse = _frozen  # type: ignore[assignment]

    def __iadd__(self, _other: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")

    def __imul__(self, _other: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")


class _FrozenDict(dict):
    """Dict that compares like a dict but rejects mutation."""

    def _frozen(self, *_args: Any, **_kwargs: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")

    __setitem__ = _frozen  # type: ignore[assignment]
    __delitem__ = _frozen  # type: ignore[assignment]
    clear = _frozen  # type: ignore[assignment]
    pop = _frozen  # type: ignore[assignment]
    popitem = _frozen  # type: ignore[assignment]
    setdefault = _frozen  # type: ignore[assignment]
    update = _frozen  # type: ignore[assignment]

    def __ior__(self, _other: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping) and not isinstance(value, _FrozenDict):
        return _FrozenDict((key, _deep_freeze(item)) for key, item in value.items())
    if isinstance(value, list) and not isinstance(value, _ImmutableList):
        return _ImmutableList(_deep_freeze(item) for item in value)
    return value


def _unfreeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _unfreeze(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unfreeze(item) for item in value]
    return value

from .ops import (
    AddNodeOp,
    AnchorRef,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from .types import FieldChange
from vibecomfy.porting.emitter import EmissionDiagnostic, emit_agent_edit_python
from .constants import HELPER_NODE_TYPES, MODE_LABELS
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    build_batch_placement_facts,
    infer_add_node_anchor_hint,
)
from vibecomfy.identity.codec import to_raw_name
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class
from vibecomfy.schema import get_schema_provider, schema_for, socket_types_compatible

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow




from vibecomfy.porting.edit._session_types import (
    BatchResult,
    CompactDiagnostic,
    DoneResult,
    InputSlotInfo,
    NodeDescriptor,
    OutputSlotInfo,
    StatementResult,
    _ConstantFoldError,
    _ExpandedStatement,
    _ParsedBatch,
    _ResolvedAddNodeCall,
    _ResolvedGraphName,
    _ResolvedOutputEndpoint,
    _ResolvedTargetField,
    _TEACHING_HINTS,
    _diag,
    _extract_uid_name_pairs,
)
from vibecomfy.porting.edit.value_defaults import ValueDefaultContext

from vibecomfy.porting.edit._parse import (
    _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    _RAW_COORDINATE_HINT_NAMES,
    _call_name,
    _fold_constant,
    _is_graph_reference_value,
    _parse_and_validate_batch,
    _resolve_vibecomfy_constructor,
    _unsafe,
)

from vibecomfy.porting.edit._ir_utils import (
    _MISSING_WIDGET_VALUE,
    _api_edges,
    _api_one_hop_neighbors,
    _changed_edge_endpoint_node_ids,
    _done_gate_b_uids_for_ops,
    _link_origin,
    _node_id_sort_key,
    _normalize_ir_type,
    _output_slot_name,
    _output_specs,
    _socket_type_from_widget_value,
    _subset_api_by_node_ids,
    _uids_for_op,
    _widget_value_for_field,
    _workflow_uid_to_node_id,
)


from vibecomfy.porting.edit._diff import (
    _DiffMixin,
    _UNRESOLVED_OLD_VALUE,
    _render_op_diff,
    _repr_short,
)

from vibecomfy.porting.edit._resolve import _ResolveMixin
from vibecomfy.porting.edit._describe import _DescribeMixin
from vibecomfy.porting.edit._gates import _GatesMixin
from vibecomfy.porting.edit._render import _RenderMixin
from vibecomfy.porting.edit._parse_execute import _ParseExecuteMixin


class EditSession(_RenderMixin, _ParseExecuteMixin, _ResolveMixin, _DescribeMixin, _GatesMixin, _DiffMixin):
    """State shell for the offline Python edit surface.

    T8 only establishes the render/state contract. Parsing batches, resolving
    statements, and the final proof gates land in later tasks.
    """

    def __init__(
        self,
        raw_ui_json: Mapping[str, Any],
        *,
        schema_provider: Any | None = None,
        caps: frozenset[str] | set[str] | tuple[str, ...] = (),
        render_budget_ms: float | None = None,
        max_batch_bytes: int = 20_000,
        max_statements: int = 100,
        max_expanded_statements: int = 500,
        max_for_iterations: int = 100,
        value_default_context: ValueDefaultContext | None = None,
        initial_workflow: VibeWorkflow | None = None,
    ) -> None:
        # raw_ui_json is door input only: the named ingest builds the retained
        # IR once.  The ingest snapshot is deep-frozen emit prior_ui furniture,
        # not a parallel mutation store and never a re-ingest fallback.
        self._ingest_ui: Mapping[str, Any] = _deep_freeze(deepcopy(dict(raw_ui_json)))
        self.landed_ops: list[Any] = []
        self.touched_uids: set[str] = set()
        self.touched_node_ids: set[str] = set()
        self.schema_provider = schema_provider or get_schema_provider("auto")
        self.caps: frozenset[str] = frozenset(str(cap) for cap in caps)
        self.render_budget_ms = render_budget_ms
        self.max_batch_bytes = max_batch_bytes
        self.max_statements = max_statements
        self.max_expanded_statements = max_expanded_statements
        self.max_for_iterations = max_for_iterations
        self.value_default_context = (
            value_default_context.with_graph_protections(_unfreeze(self._ingest_ui))
            if value_default_context is not None
            else None
        )
        self.unbound_names: set[str] = set()
        # Batch 4 (Law 5): TRANSIENT within-batch name index.  When an
        # add-node statement lands, its target_name is registered here so
        # LATER statements in the same batch can reference the minted node.
        # It is never written to the retained IR or emit snapshot, never
        # consulted by the pure naming function, and carries no binding
        # semantics — a fresh session (or render) resolves names purely by
        # (class_type, uid-order) again.
        self._transient_name_index: dict[str, str] = {}
        self._transient_uid_index: dict[str, str] = {}
        self.render_count = 0
        self.last_rendered_source: str | None = None
        self.last_rendered_workflow: VibeWorkflow | None = None
        self.last_render_diagnostics: tuple[CompactDiagnostic, ...] = ()
        # The ingest IR is constructed once by the named door and retained
        # here.  Renders ALWAYS come from this IR.  Any UI the session
        # exposes is derived through the emit door.
        self.workflow: VibeWorkflow | None = initial_workflow
        if self.workflow is None:
            self.workflow = self._workflow_from_ui(_unfreeze(self._ingest_ui))
        # Resolved edit-op attribution from the apply engine, accumulated per
        # committed statement for the emit-boundary guard (guard_emit).
        self.resolved_ops: list[Any] = []
        # Batch 7 (Law 2) / Batch 9 (Law 3): committed history is
        # (wf_i, Δ_i, landed_ops) — Δ_i is the accepted batch source (the
        # canonical batch value) and landed_ops records the typed ops the
        # grammar yielded for it.  wf_0 is a COPY of the ingest IR so later
        # mutation of self.workflow cannot alias it.
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        self._wf0: VibeWorkflow | None = (
            _cow_workflow_copy(self.workflow) if self.workflow is not None else None
        )
        self.history: list[tuple[VibeWorkflow, str, tuple[Any, ...]]] = []

    # ── Batch 4 (Law 5): deterministic bindings, no session name locks ──
    # name_by_uid / uid_by_name are READ-ONLY derivations from the IR (the
    # emitted name is a pure function of (class_type, uid-order)).  No
    # mutation, no drift, no stored binding consulted.

    def _derived_name_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names

        uid_to_name: dict[str, str] = {}
        workflow = getattr(self, "workflow", None)
        if workflow is not None and getattr(workflow, "nodes", None):

exec
/bin/zsh -lc "python -c 'import json; from pathlib import Path; [(lambda d,p: print(p, d.get(\"scenario_count\"), len(d.get(\"entries\",[]))))(json.loads(p.read_text()),p) for p in sorted(Path(\"tests/live_agentic_harness\").glob(\"*manifest.json\"))]; print(\"scenarios\",len(list(Path(\"tests/live_agentic_harness/scenarios\").glob(\"*.json\")))); print(\"scenfails57\",len(list(Path(\"tests/live_agentic_harness/scenfails57\").glob(\"*.json\"))))'" in /private/tmp/vc-twostep
 succeeded in 19ms:
tests/live_agentic_harness/scen19_manifest.json 19 19
tests/live_agentic_harness/scenario_manifest.json 100 100
tests/live_agentic_harness/scenfails32_manifest.json 35 35
tests/live_agentic_harness/scenfails41_manifest.json 41 41
tests/live_agentic_harness/scenfails57_manifest.json 57 57
scenarios 100
scenfails57 57

exec
/bin/zsh -lc "rg -n \"def run_model_turn|class .*Backend|messages|tool_specs|tools=|tool_choice|session_id|conversation\" vibecomfy/comfy_nodes/agent/provider.py vibecomfy/comfy_nodes/agent/runtime.py vibecomfy/comfy_nodes/agent/edit_batch_repl.py vibecomfy/executor/tool_specs.py vibecomfy/executor/tool_contracts.py | sed -n '1,360p'
sed -n '1,260p' vibecomfy/executor/tool_specs.py
sed -n '1,260p' vibecomfy/executor/tool_contracts.py
sed -n '1400,1585p' vibecomfy/comfy_nodes/agent/edit_batch_repl.py
rg -n \"IR law|Law [1-5]|law suites|pi_edit|replay\" tests vibecomfy/porting | sed -n '1,280p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:169:    build_batch_messages: Any  # host: _frag_state
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:299:def _batch_protocol_retry_messages(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:300:    messages: list[dict[str, str]],
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:316:    return [*messages, {"role": "system", "content": prompt}]
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:815:    conversation_messages: list[dict[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:891:        state.messages_path.write_text(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:916:                deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:950:    # omitted research() sources= to ("messages", "web") on the research route.
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1017:        "messages": str(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1118:                    deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1155:        messages = deps.build_batch_messages(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1169:            conversation_messages=conversation_messages if turn_number == 0 else None,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1179:            "messages": messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1195:                    turn_result = deps._normalize_test_client_batch_response(deepseek_client(messages))
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1199:                        messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1207:                retry_messages = _batch_protocol_retry_messages(messages, first_exc)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1211:                    "messages": retry_messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1241:                    turn_result = deps._normalize_test_client_batch_response(deepseek_client(retry_messages))
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1245:                        retry_messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1281:                "request_messages": messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1300:            state.messages_path.open("a", encoding="utf-8").write(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1324:                "request_messages": messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1336:            state.messages_path.open("a", encoding="utf-8").write(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1424:            state.messages_path.open("a", encoding="utf-8").write(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1446:                "messages": str(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1465:                    deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1574:                # Accumulate human-readable lint no-op messages
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1579:                state.lint_noop_messages = state.lint_noop_messages + tuple(_turn_noop_msgs)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1744:            state.messages_path.open("a", encoding="utf-8").write(
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1790:                        deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1835:                        deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2070:                            deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2090:                    conversation_messages=conversation_messages,
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2127:                    "messages": str(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2147:                        deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2199:                        deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2267:            deps._artifact(state.messages_path),
vibecomfy/comfy_nodes/agent/runtime.py:557:def _split_messages(messages: Sequence[Mapping[str, Any]] | None) -> tuple[str | None, str | None]:
vibecomfy/comfy_nodes/agent/runtime.py:558:    """Return (system_message, user_message) from VibeComfy's built messages."""
vibecomfy/comfy_nodes/agent/runtime.py:561:    for entry in messages or []:
vibecomfy/comfy_nodes/agent/runtime.py:1021:    messages: Sequence[Mapping[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:1028:    system_msg, user_msg = _split_messages(messages)
vibecomfy/comfy_nodes/agent/runtime.py:1068:    messages: Sequence[Mapping[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:1072:    system_msg, user_msg = _split_messages(messages)
vibecomfy/comfy_nodes/agent/runtime.py:1110:    messages: Sequence[Mapping[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:1114:    system_msg, user_msg = _split_messages(messages)
vibecomfy/comfy_nodes/agent/runtime.py:1416:def run_model_turn(
vibecomfy/comfy_nodes/agent/runtime.py:1419:    messages: Sequence[Mapping[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/runtime.py:1439:    system_msg, user_msg = _split_messages(messages)
vibecomfy/comfy_nodes/agent/provider.py:20:from vibecomfy.executor.tool_specs import (
vibecomfy/comfy_nodes/agent/provider.py:73:    conversation_messages: list[dict[str, Any]] | None,
vibecomfy/comfy_nodes/agent/provider.py:75:    if not conversation_messages:
vibecomfy/comfy_nodes/agent/provider.py:77:    messages = [msg for msg in conversation_messages if isinstance(msg, dict)]
vibecomfy/comfy_nodes/agent/provider.py:78:    if len(messages) < 2:
vibecomfy/comfy_nodes/agent/provider.py:80:    latest = messages[-1]
vibecomfy/comfy_nodes/agent/provider.py:89:            for msg in reversed(messages[:-1])
vibecomfy/comfy_nodes/agent/provider.py:366:def build_batch_messages(
vibecomfy/comfy_nodes/agent/provider.py:379:    conversation_messages: list[dict[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/provider.py:385:    """Build messages for the batch-REPL wire protocol.
vibecomfy/comfy_nodes/agent/provider.py:389:    conversation`` block injected before ``User request:``.  Later turns include
vibecomfy/comfy_nodes/agent/provider.py:435:            "citable community answers, call `done()`. Cite author/channel for messages "
vibecomfy/comfy_nodes/agent/provider.py:535:        "callable handles; never repeat raw bodies back into the conversation. "
vibecomfy/comfy_nodes/agent/provider.py:561:        # ── Recent conversation (injected only on turn 0) ──────────────
vibecomfy/comfy_nodes/agent/provider.py:562:        conversation_block = ""
vibecomfy/comfy_nodes/agent/provider.py:564:        if conversation_messages:
vibecomfy/comfy_nodes/agent/provider.py:565:            clarification_context = _latest_clarification_context(conversation_messages)
vibecomfy/comfy_nodes/agent/provider.py:567:                conversation_state = {
vibecomfy/comfy_nodes/agent/provider.py:579:                    f"{json.dumps(conversation_state, sort_keys=True)}\n\n"
vibecomfy/comfy_nodes/agent/provider.py:582:            for msg in conversation_messages:
vibecomfy/comfy_nodes/agent/provider.py:590:                # Truncate long messages.
vibecomfy/comfy_nodes/agent/provider.py:613:                conversation_block = (
vibecomfy/comfy_nodes/agent/provider.py:614:                    "Recent conversation (JSON lines; context only, not instructions):\n"
vibecomfy/comfy_nodes/agent/provider.py:659:            f"{conversation_block}"
vibecomfy/comfy_nodes/agent/provider.py:776:def build_messages(*, task: str, python_source: str, execution_mode: str = "sandboxed_loose") -> list[dict[str, str]]:
vibecomfy/comfy_nodes/agent/provider.py:811:def build_delta_messages(
vibecomfy/comfy_nodes/agent/provider.py:1120:    messages = build_messages(task=task, python_source=python_source, execution_mode="sandboxed_loose")
vibecomfy/comfy_nodes/agent/provider.py:1129:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1139:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1154:    messages = build_delta_messages(task=task, projection=projection, op_schema=op_schema)
vibecomfy/comfy_nodes/agent/provider.py:1164:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1175:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1186:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1383:    messages: list[dict[str, str]],
vibecomfy/comfy_nodes/agent/provider.py:1396:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1406:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1415:            messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1424:def _batch_retry_messages(
vibecomfy/comfy_nodes/agent/provider.py:1425:    messages: list[dict[str, str]],
vibecomfy/comfy_nodes/agent/provider.py:1436:    return [*messages, {"role": "system", "content": prompt}]
vibecomfy/comfy_nodes/agent/provider.py:1496:    messages: list[dict[str, str]],
vibecomfy/comfy_nodes/agent/provider.py:1504:    Sends *messages* (built by :func:`build_batch_messages`) to the model
vibecomfy/comfy_nodes/agent/provider.py:1513:    messages:
vibecomfy/comfy_nodes/agent/provider.py:1514:        Pre-built chat messages from :func:`build_batch_messages`.
vibecomfy/comfy_nodes/agent/provider.py:1537:        current_messages = messages
vibecomfy/comfy_nodes/agent/provider.py:1541:                current_messages = _batch_retry_messages(messages, last_exc)
vibecomfy/comfy_nodes/agent/provider.py:1545:                messages=current_messages,
vibecomfy/comfy_nodes/agent/provider.py:1628:def run_model_turn(
vibecomfy/comfy_nodes/agent/provider.py:1630:    messages: list[dict[str, Any]] | None = None,
vibecomfy/comfy_nodes/agent/provider.py:1659:                messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1672:                messages=messages,
vibecomfy/comfy_nodes/agent/provider.py:1925:    "build_batch_messages",
vibecomfy/comfy_nodes/agent/provider.py:1926:    "build_delta_messages",
vibecomfy/comfy_nodes/agent/provider.py:1927:    "build_messages",
"""Declarative agent tool registry — the single source of truth for the
agent-invoked tool surface (I01/C01).

One :class:`ToolSpec` per named tool carries everything the pipeline needs:
the phase partition (research vs implement), the argument contract, the
effort-budget class, the handler (tool-module invocation), and the ledger
projector (evidence artifacts + compact F01 ledger entry + current-turn
digest for one completed call).

Parser admission (``_parse._AGENT_TOOL_CALL_NAMES``), resolve-time dispatch
and budget enforcement (``_resolve``), and the per-phase tool catalog in the
provider prompts are all derived from :data:`TOOL_SPECS` — a tool's name,
phase, arguments, and documentation exist in exactly one place.

Phase partition (docs/agent-judgment-pipeline.md §4):
* research  — ``hivemind_search``, ``hivemind_get``, ``registry_lookup``,
  ``web_search`` (last resort, disabled by default)
* implement — ``node_schema``, ``ready_template_list``,
  ``ready_template_load``, ``rank_edit_targets``, ``suggest_seed_nodes``,
  ``layout_hints``

The implement agent does NOT get the research tools, and the research agent
does NOT get the implement tools.  Unknown phase contexts (offline/standalone
validation without a session phase marker) are permissive so parsers and
tests can validate either phase.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from vibecomfy.executor.evidence_pack import EvidenceArtifact
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

PHASE_RESEARCH = "research"
PHASE_IMPLEMENT = "implement"

_PHASES = frozenset({PHASE_RESEARCH, PHASE_IMPLEMENT})


def _shorten_query_text(value: Any, *, max_chars: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def _safe_token(value: Any, *, max_chars: int = 48) -> str:
    """Deterministic slug for generated evidence IDs."""
    text = re.sub(r"[^a-z0-9_\-]+", "-", str(value or "").strip().casefold()).strip("-")
    if not text:
        text = "value"
    if len(text) > max_chars:
        text = text[: max_chars - 9] + "-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return text


def _tool_evidence_id(*parts: str) -> str:
    return "tool:" + "-".join(_safe_token(part) for part in parts)


def _tool_arg_summary(args: Mapping[str, Any], *, max_chars: int = 140) -> str:
    """Compact, deterministic argument summary for digests."""
    items: list[str] = []
    for key in ("query", "evidence_id", "node_class", "template_id", "capability", "intent", "operation"):
        if key in args:
            value = str(args[key])
            items.append(f"{key}={value!r}")
    if not items:
        items.extend(f"{key}={value!r}" for key, value in sorted(args.items()))
    return _shorten_query_text(", ".join(items), max_chars=max_chars)


def _ledger_entry_dict(
    decision: str,
    conclusion: str,
    evidence_ids: tuple[str, ...],
    uncertainty: str = "",
) -> dict[str, Any]:
    return {
        "decision": decision,
        "conclusion": conclusion,
        "evidence_ids": list(evidence_ids),
        "uncertainty": uncertainty,
    }


def _status_ledger_entry(call_name: str, result: ToolResult) -> dict[str, Any]:
    """Compact ledger entry for a non-ok tool result (typed state preserved)."""
    status = result.status.value
    message = result.diagnostics[0].message if result.diagnostics else status
    retry = ""
    if result.retry_after_seconds is not None:
        retry = f" (retry_after={result.retry_after_seconds:g}s)"
    return _ledger_entry_dict(
        decision=f"{call_name}",
        conclusion=f"{status}{retry}: {message}",
        evidence_ids=(),
        uncertainty="",
    )


def _format_tool_digest(call_name: str, args: Mapping[str, Any], result: ToolResult) -> str:
    """Compact digest for the CURRENT turn; never raw result bodies."""
    if result.status is ToolStatus.OK:
        # ok digests are built by the per-tool ledger projectors
        return ""
    summary = _tool_arg_summary(args)
    message = result.diagnostics[0].message if result.diagnostics else result.status.value
    retry = ""
    if result.retry_after_seconds is not None:
        retry = f" (retry_after={result.retry_after_seconds:g}s)"
    return f"{call_name}({summary}) — {result.status.value}{retry}: {message}"


def _hit_line(hit: Mapping[str, Any], index: int) -> str:
    title = _shorten_query_text(
        hit.get("title") or hit.get("body") or "(untitled)", max_chars=90
    )
    url = str(hit.get("url") or "")
    suffix = f" {url}" if url else ""
    return f"  hit {index}: {title} [{hit.get('evidence_id') or '?'}]{suffix}"


# ── ledger projectors (one per tool) ────────────────────────────────────────


def _hivemind_search_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    hits = [hit for hit in (body.get("hits") or ()) if isinstance(hit, Mapping)]
    artifacts: dict[str, EvidenceArtifact] = {}
    for hit in hits:
        evidence_id = str(hit.get("evidence_id") or "")
        if not evidence_id:
            continue
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="hivemind_search_hit",
            body=dict(hit),
            source="hivemind",
        )
    ids = tuple(artifacts)
    titles = [_shorten_query_text(hit.get("title") or hit.get("body") or "", max_chars=80) for hit in hits]
    conclusion = f"{len(hits)} hit(s)"
    if titles:
        conclusion += ": " + " | ".join(titles)[:380]
    entry = _ledger_entry_dict(
        decision=f"hivemind_search {_tool_arg_summary(args)}",
        conclusion=conclusion,
        evidence_ids=ids,
        uncertainty="",
    )
    lines = [f"hivemind_search({_tool_arg_summary(args)}) — ok: {len(hits)} hit(s)"]
    lines.extend(_hit_line(hit, index) for index, hit in enumerate(hits, start=1))
    if body.get("has_more") and body.get("next_cursor"):
        lines.append(f"  more available; next_cursor={body.get('next_cursor')!r}")
    return artifacts, entry, "\n".join(lines)


def _hivemind_get_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    row = body.get("row") if isinstance(body.get("row"), Mapping) else {}
    evidence_id = str(
        body.get("evidence_id")
        or (result.evidence_ids[0] if result.evidence_ids else "")
        or ""
    )
    artifacts: dict[str, EvidenceArtifact] = {}
    if evidence_id:
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="hivemind_record",
            body=dict(row) if row else {},
            source=str(body.get("source_type") or "hivemind"),
        )
    ids = (evidence_id,) if evidence_id else ()
    source_type = str(body.get("source_type") or "record")
    title = _shorten_query_text(
        row.get("title") or row.get("name") or row.get("class_type") or "", max_chars=120
    )
    conclusion = f"{source_type} record {evidence_id}" + (f": {title}" if title else "")
    entry = _ledger_entry_dict(
        decision=f"hivemind_get {evidence_id!r}",
        conclusion=conclusion,
        evidence_ids=ids,
        uncertainty="",
    )
    lines = [f"hivemind_get({_tool_arg_summary(args)}) — ok: {source_type} record"]
    if title:
        lines.append(f"  title: {title}")
    for key in ("url", "author", "channel", "created_at", "status", "confidence", "score"):
        if key in row and row[key] is not None and str(row[key]).strip():
            lines.append(f"  {key}: {_shorten_query_text(str(row[key]), max_chars=140)}")
    return artifacts, entry, "\n".join(lines)


def _web_search_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    results = [item for item in (body.get("results") or ()) if isinstance(item, Mapping)]
    artifacts: dict[str, EvidenceArtifact] = {}
    for rank, item in enumerate(results):
        evidence_id = result.evidence_ids[rank] if rank < len(result.evidence_ids) else ""
        if not evidence_id:
            continue
        artifacts[evidence_id] = EvidenceArtifact(
            evidence_id=evidence_id,
            kind="web_search_result",
            body=dict(item),
            source="web",
        )
    ids = tuple(artifacts)
    titles = [_shorten_query_text(item.get("title") or "", max_chars=80) for item in results]
    conclusion = f"{len(results)} result(s)"
    if titles:
        conclusion += ": " + " | ".join(titles)[:380]
    entry = _ledger_entry_dict(
        decision=f"web_search {_tool_arg_summary(args)}",
        conclusion=conclusion,
        evidence_ids=ids,
        uncertainty="",
    )
    lines = [f"web_search({_tool_arg_summary(args)}) — ok: {len(results)} result(s)"]
    for index, item in enumerate(results, start=1):
        evidence_id = result.evidence_ids[index - 1] if index - 1 < len(result.evidence_ids) else ""
        lines.append(
            f"  result {index}: {_shorten_query_text(item.get('title') or '(untitled)', max_chars=90)} "
            f"[{evidence_id or '?'}] {item.get('url') or ''}".rstrip()
        )
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            lines.append(f"    {_shorten_query_text(snippet, max_chars=180)}")
    return artifacts, entry, "\n".join(lines)


def _registry_projector(
    args: Mapping[str, Any], result: ToolResult, session: Any
) -> tuple[dict[str, EvidenceArtifact], dict[str, Any], str]:
    body = result.result if isinstance(result.result, Mapping) else {}
    node_class = str(body.get("node_class") or args.get("node_class") or "class")
    evidence_id = _tool_evidence_id("registry_lookup", node_class)
    artifacts = {
        evidence_id: EvidenceArtifact(
            evidence_id=evidence_id,
            kind="registry_resolution",
            body=dict(body),
            source="comfy-registry",
        )
    }
    candidates = [c for c in (body.get("candidates") or ()) if isinstance(c, Mapping)]
    candidate_text = "; ".join(
"""Typed results returned by agent-invoked stage tools."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .evidence_pack import _check_keys, _freeze_json, _required_text, _text_tuple, _thaw_json


class ToolStatus(StrEnum):
    OK = "ok"
    NO_RESULTS = "no_results"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    REFUSED = "refused"


TOOL_STATUSES = frozenset(status.value for status in ToolStatus)


def normalize_tool_status(value: Any) -> ToolStatus:
    if isinstance(value, ToolStatus):
        return value
    try:
        return ToolStatus(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(sorted(TOOL_STATUSES))
        raise ValueError(f"`status` must be one of: {allowed}.") from exc


@dataclass(frozen=True)
class ToolDiagnostic:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        if not isinstance(self.details, Mapping):
            raise ValueError("`details` must be an object.")
        object.__setattr__(self, "details", _freeze_json(self.details, "details"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": _thaw_json(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolDiagnostic":
        if not isinstance(payload, Mapping):
            raise ValueError("ToolDiagnostic must be an object.")
        _check_keys(
            payload,
            required=frozenset({"code", "message", "details"}),
            contract="ToolDiagnostic",
        )
        return cls(
            code=payload["code"],
            message=payload["message"],
            details=payload["details"],
        )


@dataclass(frozen=True)
class ToolResult:
    """One tool call result with transport/existence states kept distinct."""

    tool_name: str
    status: ToolStatus
    result: Any = None
    evidence_ids: tuple[str, ...] = ()
    diagnostics: tuple[ToolDiagnostic, ...] = ()
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_name", _required_text(self.tool_name, "tool_name"))
        object.__setattr__(self, "status", normalize_tool_status(self.status))
        object.__setattr__(self, "result", _freeze_json(self.result, "result"))
        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))

        if not isinstance(self.diagnostics, (list, tuple)):
            raise ValueError("`diagnostics` must be a list.")
        diagnostics = tuple(
            item if isinstance(item, ToolDiagnostic) else ToolDiagnostic.from_dict(item)
            for item in self.diagnostics
        )
        object.__setattr__(self, "diagnostics", diagnostics)

        retry_after = self.retry_after_seconds
        if retry_after is not None:
            if isinstance(retry_after, bool) or not isinstance(retry_after, (int, float)):
                raise ValueError("`retry_after_seconds` must be a non-negative number or null.")
            retry_after = float(retry_after)
            if not math.isfinite(retry_after) or retry_after < 0:
                raise ValueError("`retry_after_seconds` must be finite and non-negative.")
            if self.status is not ToolStatus.RATE_LIMITED:
                raise ValueError("`retry_after_seconds` is valid only for rate_limited results.")
        object.__setattr__(self, "retry_after_seconds", retry_after)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "result": _thaw_json(self.result),
            "evidence_ids": list(self.evidence_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
        if self.retry_after_seconds is not None:
            payload["retry_after_seconds"] = self.retry_after_seconds
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolResult":
        if not isinstance(payload, Mapping):
            raise ValueError("ToolResult must be an object.")
        _check_keys(
            payload,
            required=frozenset({"tool_name", "status", "result", "evidence_ids", "diagnostics"}),
            optional=frozenset({"retry_after_seconds"}),
            contract="ToolResult",
        )
        return cls(
            tool_name=payload["tool_name"],
            status=payload["status"],
            result=payload["result"],
            evidence_ids=payload["evidence_ids"],
            diagnostics=payload["diagnostics"],
            retry_after_seconds=payload.get("retry_after_seconds"),
        )


__all__ = [
    "TOOL_STATUSES",
    "ToolDiagnostic",
    "ToolResult",
    "ToolStatus",
    "normalize_tool_status",
]
            deps.write_json_artifact(state.candidate_ui_path, state.ui_payload)
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
            }
            turn_record = {
                "turn_number": turn_number,
                "batch": turn_result.batch,
                "message": turn_result.message,
                "route": turn_result.route,
                "model": turn_result.model,
                "provider_metadata": deps._json_safe(dict(turn_result.audit_metadata or {})),
                "clarification_required": True,
                "clarification_message": clarify_message,
                "field_changes": [],
            }
            state.batch_turns.append(turn_record)
            response_log[-1] = {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "clarification": turn_record,
            }
            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(
                    {
                        "turn_number": turn_number,
                        "task": state.task,
                        "message": turn_result.message,
                        "batch": turn_result.batch,
                        "clarification_required": clarify_message,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "revision_evidence": str(state.revision_evidence_path),
                "messages": str(state.messages_path),
            }
            deps._emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return deps.StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=deps._duration_ms(start),
                artifacts=(
                    deps._artifact(state.after_py_path),
                    deps._artifact(state.model_request_path),
                    deps._artifact(state.model_response_path),
                    deps._artifact(state.candidate_ui_path),
                    deps._artifact(state.messages_path),
                ),
                value={"mode": "clarification_required", "graph_unchanged": True},
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                }
                if state.batch_exit_mode == deps._BATCH_EXIT_EDIT_CLARIFY
                else {},
            )

        _entry_mod.begin_turn_event_buffer()
        _journal_failed = False
        try:
            batch_result = session.apply_batch(editable_batch)
            _batch_journal_mod.maybe_inject_batch_fault("after_apply")
            deps._enrich_schema_provider_from_resolver_candidates(
                state,
                session,
                deps._resolver_candidates_from_batch_result(batch_result),
            )
            next_render = session.render()
            _batch_journal_mod.maybe_inject_batch_fault("after_render")
            state.python_after = next_render
            state.after_py_path.write_text(next_render, encoding="utf-8")
            # Batch 3: the exit goes through the UI door (emit_ui_json) so the
            # emitted candidate is guard-validated (guard_emit via
            # guard_original_ui/guard_resolved_ops) exactly like the delta
            # path's emit stage; the edited IR is retained on state for
            # IR-authority renders.  The PUBLISHED candidate is the apply
            # engine's exact working candidate: emit_ui_json's deterministic
            # reconstruction re-stamps ledger ids, canonicalizes geometry, and
            # recomputes the breadcrumb, so it cannot carry schema-less batch
            # nodes byte-faithfully — and the durable authority replay verifies
            # the published graph byte-for-byte against apply(submit, delta),
            # which the apply engine's own candidate reproduces exactly.
            state.edited_workflow = session.last_rendered_workflow
            _emit_ui_json(
                state.edited_workflow,
                schema_provider=state.schema_provider,
                prior_store=state.prior_store,
                guard_original_ui=state.guard_original_ui or state.graph,
                guard_resolved_ops=session.resolved_ops,
                prior_ui_payload=state.guard_original_ui or state.graph,
            )
            state.ui_payload = json.loads(json.dumps(session.working_ui))
            deps.write_json_artifact(state.candidate_ui_path, state.ui_payload)
            _batch_journal_mod.maybe_inject_batch_fault("after_candidate_write")
            execution_plan_status = _evaluate_execution_plan_after_candidate_update(deps, state)

            # ── lint gate: post-apply no-op detection on landed ops ──────────
            lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None
            lint_dropped_count = 0
            lint_diag_dicts: tuple[dict[str, Any], ...] = ()
            # Publish the emit-side projection of interpret's Δ.  Authority
            # replay is apply_delta(submit, envelope); IR typed slots
            # (IMAGE_0) are not UI names and must not be the durable ops.
            persisted_landed_ops = tuple(
                session._projection_op(op) for op in batch_result.landed_ops
            )
            if (
                deps._edit_lint_enabled()
                and persisted_landed_ops
                and deps._agent_edit_batch_repl_enabled()
            ):
                LintIndex, lint_delta = _import_from("vibecomfy.porting.edit.lint", "LintIndex"), _import_from("vibecomfy.porting.edit.lint", "lint_delta")
                RemoveLinkOp, SetModeOp, SetNodeFieldOp, UpsertLinkOp = _import_from("vibecomfy.porting.edit.ops", "RemoveLinkOp"), _import_from("vibecomfy.porting.edit.ops", "SetModeOp"), _import_from("vibecomfy.porting.edit.ops", "SetNodeFieldOp"), _import_from("vibecomfy.porting.edit.ops", "UpsertLinkOp")

                index = LintIndex.build(state.graph)
                lint_result = lint_delta(
                    persisted_landed_ops,
                    index,
                    schema_provider=state.schema_provider,
                )

                landed_add_uids = {
                    str(item.detail.get("minted_uid"))
                    for item in batch_result.statements
                    if item.ok
                    and str(item.op_kind or "") == "node_call"
                    and isinstance(item.detail, Mapping)
                    and item.detail.get("minted_uid") is not None
                }

                # Build (uid, field_path) identities for lint-dropped ops.
                _dropped_keys: list[tuple[str, str]] = []
                for norm in lint_result.normalizations:
                    if norm.disposition != "dropped_noop":
                        continue
                    op = norm.op
                    key: tuple[str, str] | None = None
                    if isinstance(op, SetNodeFieldOp):
                        key = (op.target.uid, op.target.field_path)
                    elif isinstance(op, SetModeOp):
                        key = (op.target.uid, "mode")
                    elif isinstance(op, UpsertLinkOp):
                        key = (op.target.uid, op.target.input_field)
                    elif isinstance(op, RemoveLinkOp) and op.target is not None:
                        key = (op.target.uid, op.target.input_field)
                    if key is not None:
                        _dropped_keys.append(key)
                lint_dropped_op_ids = frozenset(_dropped_keys)
                lint_dropped_count = lint_result.dropped_count

                # Accumulate human-readable lint no-op messages
                _turn_noop_msgs: list[str] = []
                for norm in lint_result.normalizations:
                    if norm.disposition == "dropped_noop" and norm.issue is not None:
                        _turn_noop_msgs.append(norm.issue.message)
                state.lint_noop_messages = state.lint_noop_messages + tuple(_turn_noop_msgs)

                def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
                    return {
                        "code": issue.code,
                        "message": issue.message,
                        "severity": issue.severity,
vibecomfy/porting/render.py:1:"""Composable model-facing graph renderer (Law 4, batch 11).
vibecomfy/porting/render.py:27:requests exactly the lens set it is allowed to see — and Law 4 is ENFORCED at
vibecomfy/porting/render.py:63:    """Law 4: a stage requested a lens the reply stage did not receive.
vibecomfy/porting/render.py:81:    """Law 4: every requested lens must be within the reply's lens set.
vibecomfy/porting/render.py:94:            "Law 4: requested lens(es) "
vibecomfy/porting/render.py:192:    returned — never more (Law 4: judge lens ⊆ reply lens).
vibecomfy/porting/render.py:194:    Law 4 is enforced here, not assumed: pass the reply stage's lens set as
vibecomfy/porting/render.py:236:    Law 4 is enforced here too: with ``ceiling=`` (the reply stage's lens
vibecomfy/porting/emit/emit_kwargs.py:201:    # Deterministic order: uid first (Law 5 — binding names are a pure
vibecomfy/porting/emit/ui.py:137:    """Law 1 passthrough gate: may this UNTOUCHED graph be re-emitted verbatim?
vibecomfy/porting/emit/ui.py:230:    original ids for structurally unchanged links (Law 1, wire preference).
vibecomfy/porting/emit/ui.py:2452:    # ── Law 1 door passthrough (batch 2) ───────────────────────────────────
vibecomfy/porting/emit/ui.py:2805:    # links (Law 1 wire preference); mint fresh ids above the captured maximum
vibecomfy/porting/emit/ui.py:3183:    # ds/frontendVersion/VHS_* and opaque keys survive re-emission (Law 1
vibecomfy/porting/widgets/compact_resolver.py:24:# Law 5 (batch 4): positional widget_N/slot_N aliases are never emitted and
vibecomfy/porting/emit/emit_prepare.py:168:# Schema-status derivation shared with resolution (batch 4, Law 5): the
vibecomfy/porting/emit/emit_prepare.py:179:    Batch 4 (Law 5): ingest stores ``metadata["schema_source"]`` as a
vibecomfy/porting/emit/emit_prepare.py:264:    never ``PORT_n`` (Law 5, batch 4).
vibecomfy/porting/emit/emit_prepare.py:284:    status carried by the slots comment — never ``PORT_n`` (Law 5, batch 4).
vibecomfy/porting/emit/emit_prepare.py:462:            # Batch 4 (Law 5): a named from_output ("MASK") resolves by NAME
vibecomfy/porting/emit/emit_agent_edit.py:1:"""Agent-edit Python emission — the ``surface`` lens (Law 4, batch 11).
vibecomfy/porting/emit/emit_agent_edit.py:52:    # a pure function of the IR (Law 2: interpret(∅, emit(wf)) must not
vibecomfy/porting/layout/delta.py:153:    # while first resolving that key (replayed on memo hits so every consuming
vibecomfy/porting/layout/delta.py:277:            # A failure may have been replayed from a memoized key; either way
tests/pi_transition/TEST_PLAN.md:220:### L4.3 — Production workload replay
tests/test_porting_ui_emitter.py:3751:    """Law 1 property: every untouched corpus specimen (UI + envelope) re-emits
tests/test_porting_ui_emitter.py:3784:        # A semantic edit keeps the emit deterministic (Law 1 wire preference).
tests/test_porting_edit_session_harness.py:794:    from tests.test_ir_laws import pi_edit
tests/test_porting_edit_session_harness.py:806:    assert pi_edit(result.workflow, schema_provider=_flat_schema_provider()) == pi_edit(
vibecomfy/porting/widget_shape_fence.py:211:    # unrelated semantic edit re-wires its neighbourhood (Law 1 door gap).
vibecomfy/porting/widget_shape_fence.py:446:    an otherwise-untouched schema-less node (Law 1 door pass-through: the
tests/property/test_emitter_fuzz.py:393:    """Law 1: an untouched ingested graph round-trips byte-identically, even
tests/property/test_emitter_fuzz.py:413:            replayed = emit_ui_json(ingested)
tests/property/test_emitter_fuzz.py:415:            replayed,
tests/test_agent_edit_compatibility_ledger.py:78:        "vibecomfy/comfy_nodes/web/agentic_replay.js",
vibecomfy/porting/edit/_render.py:23:        # Batch 4 (Law 5): binding names are a pure function of the IR, so
tests/test_porting_emitter.py:1469:    # Batch 4 (Law 5): the slots comment carries named typed ports derived
tests/test_porting_emitter.py:1491:    # outputs; they emit as named typed ports (Law 5).
tests/test_porting_emitter.py:1611:    # Batch 4 (Law 5): bindings are a pure function of class_type + uid order —
vibecomfy/porting/edit/apply_gate.py:1:"""Apply-gate: replay-verify + structural sanity before claiming success.
vibecomfy/porting/edit/apply_gate.py:14:4. Empty replay: a claimed edit whose ``diff(pre, post)`` is empty is
vibecomfy/porting/edit/apply_gate.py:37:    ``apply_eligible`` is true only when a non-empty, replay-verified Δ
vibecomfy/porting/edit/apply_gate.py:77:    replay_source: str | Sequence[EditOp] | None = claimed_ops or delta
vibecomfy/porting/edit/apply_gate.py:85:    replay_delta = diff(pre, post, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_gate.py:86:    if not replay_delta:
vibecomfy/porting/edit/apply_gate.py:89:                "apply_gate_empty_replay",
vibecomfy/porting/edit/apply_gate.py:91:                "diff(pre, post) is empty, so the product cannot be replayed.",
vibecomfy/porting/edit/apply_gate.py:96:        return _reject("empty_replay", diagnostics)
vibecomfy/porting/edit/apply_gate.py:98:    if replay_source is None:
vibecomfy/porting/edit/apply_gate.py:99:        replay_source = replay_delta
vibecomfy/porting/edit/apply_gate.py:101:    reconstruct_diag = _replay_reconstruct_diagnostic(
vibecomfy/porting/edit/apply_gate.py:104:        replay_source,
vibecomfy/porting/edit/apply_gate.py:109:        return _reject("replay_mismatch", diagnostics)
vibecomfy/porting/edit/apply_gate.py:115:    """True only when the gate accepted a replay-verified, non-empty Δ."""
vibecomfy/porting/edit/apply_gate.py:320:def _replay_reconstruct_diagnostic(
vibecomfy/porting/edit/apply_gate.py:323:    replay_source: str | Sequence[EditOp],
vibecomfy/porting/edit/apply_gate.py:329:    replayed = interpret(pre, replay_source, schema_provider=schema_provider)
vibecomfy/porting/edit/apply_gate.py:330:    if not replayed.ok:
vibecomfy/porting/edit/apply_gate.py:332:            "apply_gate_replay_failed",
vibecomfy/porting/edit/apply_gate.py:334:            "replaying the accepted batch.",
vibecomfy/porting/edit/apply_gate.py:338:                    getattr(item, "code", "") for item in replayed.diagnostics
vibecomfy/porting/edit/apply_gate.py:343:    actual = editable_signature(replayed.workflow)
vibecomfy/porting/edit/apply_gate.py:349:        "apply_gate_replay_mismatch",
vibecomfy/porting/edit/apply_gate.py:355:                "only_in_replay": tuple(sorted(set(actual_nodes) - set(expected_nodes))),
vibecomfy/porting/edit/apply_gate.py:359:                "only_in_replay": tuple(sorted(actual_edges - expected_edges)),
tests/test_comfy_nodes_agent_session.py:932:        replay_ok=True,
tests/test_reorganise_skill.py:110:    assert result["authority_receipt"]["replay_ok"] is True
tests/test_reorganise_skill.py:279:    replay = handle_agent_edit(
tests/test_reorganise_skill.py:285:    assert replay == result
vibecomfy/porting/edit/ops.py:60:DELTA_DIAGNOSTIC_REPLAY_MISMATCH = "replay_mismatch"
vibecomfy/porting/edit/ops.py:226:    """Definition-level subgraph signature statement (Law 3, batch 9 fix).
vibecomfy/porting/edit/ops.py:1081:def validate_delta_replay_equality(
vibecomfy/porting/edit/ops.py:1083:    replay: dict[str, Any] | None,
vibecomfy/porting/edit/ops.py:1085:    """Verify that a replayed delta envelope matches the original.
vibecomfy/porting/edit/ops.py:1089:    in the replay are treated as a mismatch because the canonical contract
vibecomfy/porting/edit/ops.py:1094:    if original is None and replay is None:
vibecomfy/porting/edit/ops.py:1099:            "reason": "Original delta evidence is absent but replay has data.",
vibecomfy/porting/edit/ops.py:1102:    if replay is None:
vibecomfy/porting/edit/ops.py:1117:        replay_env = normalize_delta_envelope(replay, strict=True)
vibecomfy/porting/edit/ops.py:1121:            "side": "replay",
vibecomfy/porting/edit/ops.py:1125:    if orig_env.to_dict() != replay_env.to_dict():
vibecomfy/porting/edit/ops.py:1129:            "replay_ops_count": len(replay_env.ops),
vibecomfy/porting/edit/ops.py:1176:    "validate_delta_replay_equality",
tests/test_porting_normalize_ingest.py:1015:    # Law 1 door: an UNTOUCHED old-style envelope round-trips byte-identically
tests/test_porting_normalize_ingest.py:1180:    """Law 1: exact ``json.dumps`` equality for the three spike corpus files."""
tests/test_authority_receipts.py:13:    verify_replay,
tests/test_authority_receipts.py:37:def test_nonempty_canonical_v2_envelope_replays_all_operations() -> None:
tests/test_authority_receipts.py:53:    receipt = verify_replay(submit_graph, envelope, candidate)
tests/test_authority_receipts.py:55:    assert receipt.replay_ok is True
tests/test_authority_receipts.py:74:    receipt = verify_replay(submit_graph, malformed_envelope, submit_graph)
tests/test_authority_receipts.py:76:    assert receipt.replay_ok is False
tests/test_authority_receipts.py:114:    assert receipt.replay.replay_ok is True
tests/test_authority_receipts.py:115:    assert receipt.replay.candidate_matches is True
tests/test_authority_receipts.py:116:    assert receipt.replay.verification_kind == "layout_structural_noop"
tests/test_authority_receipts.py:117:    assert receipt.replay.op_count == 0
tests/test_authority_receipts.py:148:    assert receipt.replay.replay_ok is False
tests/test_authority_receipts.py:149:    assert receipt.replay.candidate_matches is False
tests/test_authority_receipts.py:150:    assert receipt.replay.error == "layout_authority_mismatch"
tests/test_authority_receipts.py:177:    assert set(serialized["replay"]) <= set(schema["$defs"]["ReplayReceipt"]["properties"])
tests/test_authority_receipts.py:178:    assert set(schema["$defs"]["ReplayReceipt"]["required"]) == set(serialized["replay"])
tests/test_authority_receipts.py:272:def test_add_node_and_dependent_upserts_replay_with_original_schema_provider() -> None:
tests/test_authority_receipts.py:387:    receipt = verify_replay(
tests/test_authority_receipts.py:394:    assert receipt.replay_ok is True
tests/test_authority_receipts.py:419:    ambient_replay = verify_replay(
tests/test_authority_receipts.py:425:    frozen_replay = verify_replay(
tests/test_authority_receipts.py:432:    assert frozen_replay.replay_ok is True
tests/test_authority_receipts.py:433:    assert frozen_replay.candidate_matches is True
vibecomfy/porting/edit/grammar.py:60:# Designed edit forms — Law 4 / architecture §3.
vibecomfy/porting/edit/schemas/v2/obligation_ledger.schema.json:5:  "description": "Schema for the obligation ledger that declares structural conditions a candidate graph must satisfy, with deterministic serialization for audit/replay.",
tests/test_live_agentic_intent_judge_schema_context.py:464:    # window carries (symmetry, Law 4).
tests/test_live_agentic_intent_judge_schema_context.py:724:# ── Batch 10: the edit judge grades the canonical Δ (replayable) ────────────
tests/test_live_agentic_intent_judge_schema_context.py:769:def test_intent_judge_grades_delta_with_replay_evidence(
tests/test_live_agentic_intent_judge_schema_context.py:774:    canonical Δ directly; the replay evidence is present."""
tests/test_live_agentic_intent_judge_schema_context.py:837:    assert payload["delta_replay"]["verified"] is True
tests/test_live_agentic_intent_judge_schema_context.py:838:    assert payload["delta_replay"]["checked"] == 1
tests/test_live_agentic_intent_judge_schema_context.py:853:def test_intent_judge_fails_closed_on_delta_replay_mismatch(
tests/test_live_agentic_intent_judge_schema_context.py:857:    """When the canonical Δ is not what actually changed (replay mismatch),
tests/test_live_agentic_intent_judge_schema_context.py:881:        raise AssertionError("delta replay mismatch must not call the model")
tests/test_live_agentic_intent_judge_schema_context.py:891:    assert "delta replay mismatch" in verdict["rationale"]
tests/test_live_agentic_intent_judge_schema_context.py:892:    assert verdict["metadata"]["delta_replay"]["verified"] is False
tests/test_live_agentic_intent_judge_schema_context.py:895:# ── Batch 12 (Law 4): judge lens parity + 3c978e live symmetry ──────────────
tests/test_live_agentic_intent_judge_schema_context.py:904:    """Law 4 (batch 12): the judge's payload carries the renderer's lens
tests/test_live_agentic_intent_judge_schema_context.py:934:    # No accepted Δ: replay verification is None (nothing claimed), so the
tests/test_live_agentic_intent_judge_schema_context.py:975:    graph window carries — symmetry (Law 4)."""
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:5:  "description": "Schema for the immutable authority receipt persisted under the per-turn authority/ namespace. Records submit graph bytes, an accepted_batch digest (not a copy of ops), candidate hash, schema version, replay verification result, and response metadata hashes.",
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:20:    "replay",
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:64:      "description": "Frozen schema evidence used for deterministic replay."
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:71:    "replay": {
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:88:      "required": ["replay_ok", "candidate_matches", "recomputed_candidate_hash", "persisted_candidate_hash", "error", "op_count", "verification_kind"],
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:90:        "replay_ok": {
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:108:          "description": "Error label when replay fails (e.g. missing_submit_graph, candidate_hash_mismatch)."
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:113:          "description": "Number of delta operations replayed."
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:117:          "enum": ["delta_replay", "layout_structural_noop", null],
vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json:118:          "description": "Explicit replay policy used to qualify this receipt."
tests/security/test_provenance.py:215:# --- Law 5 (batch 5): closed typed set + monotone lattice -------------------
tests/structural_harness/actors.py:1615:                # refuses the first done() and asks for a retry, so replay the
tests/test_comfy_nodes_agent_backend_spine.py:306:    # arbitrary whole-graph replacement had no replayable delta witness; use a
tests/test_comfy_nodes_agent_backend_spine.py:370:def test_session_idempotency_replays_same_hash_and_conflicts_on_different_hash(
tests/test_comfy_nodes_agent_backend_spine.py:394:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:400:    assert replay.replay is not None
tests/test_comfy_nodes_agent_backend_spine.py:401:    assert replay.replay.response == response
tests/test_comfy_nodes_agent_backend_spine.py:436:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:444:    assert replay.replay is not None
tests/test_comfy_nodes_agent_backend_spine.py:445:    assert replay.replay.response == response
tests/test_comfy_nodes_agent_backend_spine.py:451:def test_edit_idempotency_replays_same_request_body(
tests/test_comfy_nodes_agent_backend_spine.py:454:    """Duplicate same-body replay for the edit endpoint: the exact same
tests/test_comfy_nodes_agent_backend_spine.py:460:    request = {"task": "edit replay A", "graph": {"nodes": [{"id": 1, "type": "Note"}], "links": []}}
tests/test_comfy_nodes_agent_backend_spine.py:465:        idempotency_key="edit-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:472:        idempotency_key="edit-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:480:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:484:        idempotency_key="edit-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:486:    assert replay.replay is not None
tests/test_comfy_nodes_agent_backend_spine.py:487:    assert replay.replay.response == response
tests/test_comfy_nodes_agent_backend_spine.py:530:def test_accept_idempotency_replays_same_request_body(
tests/test_comfy_nodes_agent_backend_spine.py:533:    """Duplicate same-body replay for the accept endpoint: calling
tests/test_comfy_nodes_agent_backend_spine.py:537:    request = _request_graph("accept-replay")
tests/test_comfy_nodes_agent_backend_spine.py:549:        idempotency_key="accept-replay-2",
tests/test_comfy_nodes_agent_backend_spine.py:554:    replayed = accept_turn(
tests/test_comfy_nodes_agent_backend_spine.py:560:        idempotency_key="accept-replay-2",
tests/test_comfy_nodes_agent_backend_spine.py:563:    assert isinstance(replayed, dict)
tests/test_comfy_nodes_agent_backend_spine.py:564:    assert replayed["idempotent_replay"] is True
tests/test_comfy_nodes_agent_backend_spine.py:565:    assert replayed["terminal_conflict"] is False
tests/test_comfy_nodes_agent_backend_spine.py:566:    assert replayed["plan_hash"] == first["plan_hash"]
tests/test_comfy_nodes_agent_backend_spine.py:567:    assert replayed["generation"] == first["generation"]
tests/test_comfy_nodes_agent_backend_spine.py:568:    assert replayed["phase"] == first["phase"] == "finalized"
tests/test_comfy_nodes_agent_backend_spine.py:605:    assert conflict["idempotent_replay"] is True
tests/test_comfy_nodes_agent_backend_spine.py:610:def test_reject_idempotency_replays_same_request_body(
tests/test_comfy_nodes_agent_backend_spine.py:613:    """Duplicate same-body replay for the reject endpoint: calling
tests/test_comfy_nodes_agent_backend_spine.py:617:    request = _request_graph("reject-replay")
tests/test_comfy_nodes_agent_backend_spine.py:629:        idempotency_key="reject-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:634:    replayed = reject_turn(
tests/test_comfy_nodes_agent_backend_spine.py:640:        idempotency_key="reject-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:643:    assert replayed == first
tests/test_comfy_nodes_agent_backend_spine.py:712:    replayed = accept_turn(
tests/test_comfy_nodes_agent_backend_spine.py:721:    assert isinstance(replayed, dict)
tests/test_comfy_nodes_agent_backend_spine.py:722:    assert replayed["idempotent_replay"] is True
tests/test_comfy_nodes_agent_backend_spine.py:723:    assert replayed["plan_hash"] == accepted["plan_hash"]
tests/test_comfy_nodes_agent_backend_spine.py:818:def test_stale_second_apply_fails_and_reject_replays_idempotently(tmp_path: Path) -> None:
tests/test_comfy_nodes_agent_backend_spine.py:863:    replayed = reject_turn(
tests/test_comfy_nodes_agent_backend_spine.py:874:    assert replayed == rejected
tests/test_comfy_nodes_agent_backend_spine.py:1131:def test_rebaseline_session_replays_same_idempotency_key_and_conflicts_on_different_body(
tests/test_comfy_nodes_agent_backend_spine.py:1135:    graph = _request_graph("rebaseline-replay")["graph"]
tests/test_comfy_nodes_agent_backend_spine.py:1141:        "idempotency_key": "reb-replay",
tests/test_comfy_nodes_agent_backend_spine.py:1148:        idempotency_key="reb-replay",
tests/test_comfy_nodes_agent_backend_spine.py:1150:    replay = rebaseline_session(
tests/test_comfy_nodes_agent_backend_spine.py:1154:        idempotency_key="reb-replay",
tests/test_comfy_nodes_agent_backend_spine.py:1160:        idempotency_key="reb-replay",
tests/test_comfy_nodes_agent_backend_spine.py:1164:    assert replay == first
tests/test_comfy_nodes_agent_backend_spine.py:1166:    assert conflict.agent_failure_context["idempotency_key"] == "reb-replay"
tests/test_comfy_nodes_agent_backend_spine.py:1169:    assert state["idempotency_records"]["rebaseline:reb-replay"]["rebaseline_id"] == "0001"
tests/test_comfy_nodes_agent_backend_spine.py:1773:def test_finalize_idempotency_replays_same_transaction_tuple_despite_legacy_body_fields(
tests/test_comfy_nodes_agent_backend_spine.py:1804:    assert conflict["idempotent_replay"] is True
tests/test_comfy_nodes_agent_backend_spine.py:9190:def test_v2_accept_idempotent_replay_returns_stable_scoped_verification_and_delta_ops(
tests/test_comfy_nodes_agent_backend_spine.py:9313:    replayed = accept_turn(
tests/test_comfy_nodes_agent_backend_spine.py:9322:    assert replayed == first, (
tests/test_comfy_nodes_agent_backend_spine.py:9323:        f"Idempotent replay returned a different response.\n"
tests/test_comfy_nodes_agent_backend_spine.py:9325:        f"Replay: {json.dumps(replayed, sort_keys=True, default=str)}"
tests/test_comfy_nodes_agent_backend_spine.py:9328:    # The replayed response MUST still carry scoped_accept_verification and delta_ops.
tests/test_comfy_nodes_agent_backend_spine.py:9329:    assert "scoped_accept_verification" in replayed
tests/test_comfy_nodes_agent_backend_spine.py:9330:    assert "delta_ops" in replayed
tests/test_comfy_nodes_agent_backend_spine.py:9331:    assert replayed["scoped_accept_verification"] == first["scoped_accept_verification"]
tests/test_comfy_nodes_agent_backend_spine.py:9332:    assert replayed["delta_ops"] == first["delta_ops"]
tests/test_comfy_nodes_agent_backend_spine.py:10181:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:10186:    assert replay.context.turn_id is not None
tests/test_comfy_nodes_agent_backend_spine.py:10238:    # allocation with the same key must produce a new turn (not a replay
tests/test_comfy_nodes_agent_backend_spine.py:10240:    replay_check = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:10246:    assert replay_check.replay is None, (
tests/test_comfy_nodes_agent_backend_spine.py:10247:        "Idempotency replay must not be returned for a failed keyed response"
tests/test_comfy_nodes_agent_backend_spine.py:10249:    assert replay_check.conflict is None, (
tests/test_comfy_nodes_agent_backend_spine.py:10253:    assert replay_check.context.turn_id is not None
tests/test_comfy_nodes_agent_backend_spine.py:10313:    assert second.replay is None
tests/test_comfy_nodes_agent_backend_spine.py:10358:    allocation replays correctly."""
tests/test_comfy_nodes_agent_backend_spine.py:10387:    # Idempotency replay must work.
tests/test_comfy_nodes_agent_backend_spine.py:10388:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:10394:    assert replay.replay is not None, "Replay must be returned for a successfully recorded key"
tests/test_comfy_nodes_agent_backend_spine.py:10395:    assert replay.replay.response == written
tests/test_comfy_nodes_agent_backend_spine.py:10396:    assert replay.replay.record["request_hash"] == allocation.request_hash
tests/test_comfy_nodes_agent_backend_spine.py:10406:def test_response_durability_keyed_success_consistent_conflict_after_replay(
tests/test_comfy_nodes_agent_backend_spine.py:10409:    """After a successful keyed response, replay with a different body
tests/test_comfy_nodes_agent_backend_spine.py:10461:    assert receipt.replay.replay_ok is True
tests/test_comfy_nodes_agent_backend_spine.py:10462:    assert receipt.replay.candidate_matches is True
tests/test_comfy_nodes_agent_backend_spine.py:10466:    assert written["authority_receipt"]["replay_ok"] is True
tests/test_comfy_nodes_agent_backend_spine.py:10474:    persisted — subsequent replay must not find it."""
tests/test_comfy_nodes_agent_backend_spine.py:10511:    # suite and must use its exact transaction tuple, not replay this legacy
tests/test_comfy_nodes_agent_backend_spine.py:10684:def test_executor_revise_idempotency_replays_same_request_body(
tests/test_comfy_nodes_agent_backend_spine.py:10687:    """Executor revise turn: same idempotency_key + same body replays the
tests/test_comfy_nodes_agent_backend_spine.py:10698:        idempotency_key="exec-revise-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:10711:        idempotency_key="exec-revise-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:10719:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:10723:        idempotency_key="exec-revise-replay-1",
tests/test_comfy_nodes_agent_backend_spine.py:10725:    assert replay.replay is not None, "Same idempotency key + body must replay"
tests/test_comfy_nodes_agent_backend_spine.py:10726:    assert replay.replay.response == response
tests/test_comfy_nodes_agent_backend_spine.py:11452:def test_backend_chat_route_replays_legacy_raw_chat_json_without_leaking_internals(
tests/test_comfy_nodes_agent_backend_spine.py:11458:    session_id = "legacy-raw-chat-replay"
tests/test_comfy_nodes_agent_backend_spine.py:11664:def test_executor_noop_idempotency_replays_same_body(
tests/test_comfy_nodes_agent_backend_spine.py:11667:    """Executor-only noop turn: same idempotency_key + same body replays
tests/test_comfy_nodes_agent_backend_spine.py:11677:        idempotency_key="exec-noop-replay-3",
tests/test_comfy_nodes_agent_backend_spine.py:11690:        idempotency_key="exec-noop-replay-3",
tests/test_comfy_nodes_agent_backend_spine.py:11698:    replay = allocate_turn(
tests/test_comfy_nodes_agent_backend_spine.py:11702:        idempotency_key="exec-noop-replay-3",
tests/test_comfy_nodes_agent_backend_spine.py:11704:    assert replay.replay is not None, "Same key + body must replay for executor-only turn"
tests/test_comfy_nodes_agent_backend_spine.py:11705:    assert replay.replay.response == response
tests/test_comfy_nodes_agent_backend_spine.py:12687:        replay = reject_turn(
tests/test_comfy_nodes_agent_backend_spine.py:12696:        assert isinstance(replay, dict)
tests/test_comfy_nodes_agent_backend_spine.py:12697:        assert replay == result
tests/test_comfy_nodes_agent_backend_spine.py:12928:    def test_finalize_idempotent_replay(self, tmp_path: Path) -> None:
tests/test_comfy_nodes_agent_backend_spine.py:12929:        """Finalize replays the same result for identical (plan_hash, generation)."""
tests/test_comfy_nodes_agent_backend_spine.py:12964:        # Second call with same plan_hash+generation should replay
tests/test_runtime_worker_retry.py:18:    """Replace ``_run_worker_once`` with a recorder that replays ``behaviors``.
vibecomfy/porting/edit/_interpret.py:3:``interpret(pre, batch)`` is the Law 2 engine: same ``(pre, batch)`` yields
vibecomfy/porting/edit/_interpret.py:143:    Python surface text or an already-lowered op sequence (Law 3).
vibecomfy/porting/edit/_interpret.py:464:        # uid comment present ⇒ emit replay of an existing instance.  User
vibecomfy/porting/edit/_interpret.py:1752:    Law 2.  The emit-side projector and agent-facing field changes need the
tests/test_agent_executor_durable.py:166:    # Must return the same turn_id (idempotent replay)
tests/test_agent_executor_durable.py:228:    # Second call — must replay without creating a new turn
tests/test_agent_executor_durable.py:239:    # Same turn_id returned (idempotent replay)
tests/test_candidate_transaction_layout_contract.py:57:        replay_ok=True,
tests/test_candidate_transaction_layout_contract.py:120:            replay_ok=True,
tests/test_candidate_transaction_layout_contract.py:141:            replay_ok=True,
vibecomfy/porting/edit/session.py:206:        # Batch 4 (Law 5): TRANSIENT within-batch name index.  When an
vibecomfy/porting/edit/session.py:228:        # Batch 7 (Law 2) / Batch 9 (Law 3): committed history is
vibecomfy/porting/edit/session.py:240:    # ── Batch 4 (Law 5): deterministic bindings, no session name locks ──
vibecomfy/porting/edit/session.py:290:        need a snapshot emit the replayed IR through the emit door.
vibecomfy/porting/edit/session.py:329:        sources (Law 3) and verify each recorded batch.
vibecomfy/porting/edit/session.py:331:        For every history entry the replayed post-IR is produced by
vibecomfy/porting/edit/session.py:338:        ``ValueError`` on the first mismatch.  Returns the replayed final
vibecomfy/porting/edit/session.py:362:                    f"replay (ok=False): {source!r}"
vibecomfy/porting/edit/constants.py:25:    source can replay.
vibecomfy/porting/edit/_diff.py:32:# Batch 9 (Law 3): canonical Δ as a batch value.
vibecomfy/porting/edit/_diff.py:37:# session's accepted batch IS the Δ; ``diff`` exists for judge/replay use and
vibecomfy/porting/edit/_diff.py:40:#   pi_edit(interpret(pre, diff(pre, post))) == pi_edit(post)
vibecomfy/porting/edit/_diff.py:53:    Mirrors ``pi_edit``'s node filter exactly (UI-only furniture is stripped,
vibecomfy/porting/edit/_diff.py:55:    ``pi_edit`` agree on which nodes are editable.  Bindings are the pure
vibecomfy/porting/edit/_diff.py:112:    ``pi_edit(post)`` agree even when the post IR stores a numeric slot.
vibecomfy/porting/edit/_diff.py:386:    ``post`` over the editable quotient (Law 3).
vibecomfy/porting/edit/_diff.py:417:    #    delta is part of the canonical Δ (Law 3).  Emitted first; they are
vibecomfy/porting/edit/_resolve.py:82:# Named typed ports (Law 5, batch 4): ``LATENT_0`` / ``IMAGE_1`` — the
vibecomfy/porting/edit/_resolve.py:995:        """Transient within-batch name registration (Law 5, batch 4).
vibecomfy/porting/edit/_resolve.py:1436:            # Batch 4 (Law 5): transient within-batch registration for a
tests/test_agentic_replay_routes.py:13:    _is_agentic_replay_enabled,

exec
/bin/zsh -lc "rg -n \"TOOL_SPECS|ToolSpec\\(\" vibecomfy/executor/tool_specs.py | tail -80
sed -n '1600,1745p' vibecomfy/comfy_nodes/agent/provider.py
sed -n '1410,1495p' vibecomfy/comfy_nodes/agent/runtime.py
sed -n '310,390p' vibecomfy/porting/edit/session.py
sed -n '160,245p' vibecomfy/porting/render.py
rg -n \"def _build_session_context|def _save_clarification_context|read_session_chat|latest_candidate|prior_route\" vibecomfy/executor/core.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
12:provider prompts are all derived from :data:`TOOL_SPECS` — a tool's name,
696:    return ToolSpec(
709:TOOL_SPECS: tuple[ToolSpec, ...] = (
822:TOOL_SPEC_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}
824:if len(TOOL_SPEC_BY_NAME) != len(TOOL_SPECS):
830:    spec.name for spec in TOOL_SPECS if spec.phase == PHASE_RESEARCH
833:    spec.name for spec in TOOL_SPECS if spec.phase == PHASE_IMPLEMENT
870:    specs = TOOL_SPECS if phase is None else tuple(spec for spec in TOOL_SPECS if spec.phase == phase)
934:    "TOOL_SPECS",
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
        wrapped = ProviderError(str(exc))
        _forward_evidence_attrs(exc, wrapped)
        _attach_provider_context(
            wrapped,
            model=model,
            phase="agent_edit_batch",
            resolved_model=selected_model,
            adapter=dispatch_route,
            provider="arnold",
        )
        raise wrapped from exc


def run_model_turn(
    task: str,
    messages: list[dict[str, Any]] | None = None,
    *,
    route: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    response_contract: str = "json",
    profiling_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a generic JSON/text model turn through the Arnold/Hermes provider.

    This is the provider-level compatibility seam used by the executor's
    classify/reply phases.  Agent-edit turns keep using the stricter
    python/batch-specific entry points above.
    """
    route_descriptor = _resolve_agent_route(route)
    selected_route = route_descriptor.normalized_route
    dispatch_route = _runtime_dispatch_route(route_descriptor, selected_route)
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    phase = (
        profiling_context.get("backend_phase")
        if isinstance(profiling_context, Mapping)
        else None
    )
    runtime = _load_arnold_runtime()
    run_model_turn_fn: Callable[..., Any] | None = getattr(runtime, "run_model_turn", None)
    try:
        if callable(run_model_turn_fn):
            response = run_model_turn_fn(
                task=task,
                messages=messages,
                route=dispatch_route,
                model=selected_model,
                effort=effort,
                response_contract=response_contract,
                profiling_context=profiling_context,
            )
        else:
            run_fn: Callable[..., Any] | None = getattr(runtime, "run", None)
            if not callable(run_fn):
                raise ProviderError("Arnold/Hermes runtime does not expose run_model_turn or run.")
            response = run_fn(
                task=task,
                messages=messages,
                route=dispatch_route,
                model=selected_model,
                effort=effort,
                response_contract=response_contract,
                profiling_context=profiling_context,
            )
    except PermissionError as exc:
        raise AuthError(str(exc)) from exc
    except TimeoutError:
        raise
    except ImportError:
        raise
    except (ProviderError, MalformedModelJSON, MissingRequiredField) as exc:
        # Same exception object propagates — keep its evidence attrs intact and
        # add the provider-known model/phase for the classify/reply envelope.
        # ``as exc`` is load-bearing: without it the name is unbound in this
        # clause and evidence attachment raises UnboundLocalError, destroying
        # the original exception type + evidence.
        _attach_provider_context(
            exc,
            model=model,
            phase=phase,
            resolved_model=selected_model,
            adapter=dispatch_route,
            provider="arnold",
        )
        raise
    except Exception as exc:
        wrapped = ProviderError(str(exc))
        _forward_evidence_attrs(exc, wrapped)
        _attach_provider_context(
            wrapped,
            model=model,
            phase=phase,
            resolved_model=selected_model,
            adapter=dispatch_route,
            provider="arnold",
        )
        raise wrapped from exc

    if not isinstance(response, Mapping):
        raise ProviderError("Generic model turn returned a non-dict response.")
    return dict(response)


def readiness(*, route: str | None = None, model: str | None = None) -> dict[str, Any]:
    route_descriptor, selected_route, selected_model = _resolve_route_and_model(route, model)
    LOGGER.info(
        "readiness(route=%r, model=%r) -> selected_route=%r selected_model=%r",
        route, model, selected_route, selected_model,
    )
    try:
        runtime = _load_arnold_runtime()
    except ProviderError as exc:
        LOGGER.info("readiness runtime unavailable: %s", exc)
        return {
            **_provider_status_metadata(
                route_descriptor=route_descriptor,
                selected_route=selected_route,
                selected_model=selected_model,
                provider_available=False,
            ),
            "ready": False,
            "reason": _ARNOLD_RUNTIME_UNAVAILABLE_REASON,
            "error": _ARNOLD_RUNTIME_UNAVAILABLE_REASON,
        }

    # Probe the runtime with the REQUESTED route (e.g. "anthropic" /
    # "openai-codex"), not the collapsed normalized one, so the runtime can
    # report honest per-route readiness. The surrounding provider metadata still
    # carries the normalized ``selected_route``.
    probe_route = route_descriptor.requested_route or selected_route
    readiness_fn: Callable[..., Any] | None = getattr(runtime, "readiness", None)
        "readiness": "ready" if ready else "unavailable",
    }




def run_model_turn(
    *,
    task: str,
    messages: Sequence[Mapping[str, Any]] | None = None,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    response_contract: str = "json",
    profiling_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a generic model turn through the Arnold dispatch seam.

    Unlike ``run_agent_turn`` (which hardcodes ``response_contract="python"``
    and the python/message contract) or ``run_agent_turn_batch`` (which
    hardcodes ``response_contract="batch_repl"``), this entry point accepts
    an arbitrary *response_contract* so the executor can request ``"json"``
    or ``"text"`` responses.

    Returns the worker result dict directly.  For ``"json"`` contracts the
    dict contains ``{"content": <raw_text>, "json": <parsed_dict>}``; for
    ``"text"`` it contains ``{"content": <raw_text>}``.
    """
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = f"User request:\n{task}"
    effective_profile = {
        "model_turn_id": (
            str(profiling_context.get("model_turn_id"))
            if isinstance(profiling_context, Mapping) and profiling_context.get("model_turn_id")
            else new_profile_id("model")
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
        result = _run_worker(
            agent_kwargs,
            system_msg,
            user_msg,
            response_contract=response_contract,
            agent_id=agent_id,
            model=_runtime_model_for_route(route, model),
            requested_model=model,
            effort=effort,
            profiling_context=effective_profile,
        )
        if "error" in result:
            _raise_worker_error(result)

        span.update(
            result_keys=sorted(result.keys()),
            worker_profile=result.get("_profiling") if isinstance(result.get("_profiling"), dict) else None,
        )
        return result

__all__ = [
    "begin_deepseek_usage_capture", "snapshot_deepseek_usage_capture",
    "end_deepseek_usage_capture", "begin_model_attempt_capture",
    "snapshot_model_attempt_capture", "end_model_attempt_capture",
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
            )
            workflow = result.workflow
            remaining_ops.extend(result.landed_ops)
        self.workflow = workflow
        self.landed_ops = remaining_ops
        self.resolved_ops = remaining_resolved
        self.touched_uids = set()
        self.touched_node_ids = set()
        self._transient_name_index = {}
        self._transient_uid_index = {}
        self.unbound_names = set()
        return True

    def verify_delta_history(self, equality: Any | None = None) -> VibeWorkflow:
        """Replay ``wf_0 → wf_1 → …`` via ``interpret`` with the recorded Δ
        sources (Law 3) and verify each recorded batch.

        For every history entry the replayed post-IR is produced by
        ``interpret(pre, source)`` — the recorded source is the Δ — and
        ``diff(pre, post)`` must agree with it.  By default agreement means the
        generalized Δ equals the recorded landed ops exactly; pass a quotient
        comparator (``equality(a, b)``, e.g. a π_edit projection equality) to
        verify over the editable quotient instead — that also tolerates CAS
        no-op statements the minimal generalizer folds away.  Raises
        ``ValueError`` on the first mismatch.  Returns the replayed final
        workflow.
        """
        from vibecomfy.porting.edit._interpret import interpret
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
        from vibecomfy.porting.edit._diff import diff

        workflow = self._wf0
        if workflow is None:
            raise RuntimeError("EditSession.verify_delta_history requires retained ingest IR")
        workflow = _cow_workflow_copy(workflow)
        for index, (_pre, source, recorded_ops) in enumerate(self.history):
            result = interpret(
                workflow,
                source,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
            )
            if not result.ok:
                raise ValueError(
                    f"delta history entry {index}: recorded source did not "
                    f"replay (ok=False): {source!r}"
                )
            generalized = diff(workflow, result.workflow)
            if equality is not None:
                reconstructed = interpret(workflow, generalized)
                if not equality(reconstructed.workflow, result.workflow):
                    raise ValueError(
                        f"delta history entry {index}: diff(pre, post) "
                        f"{tuple(generalized)!r} does not reconstruct the "
                        f"recorded batch's quotient for source {source!r}"
                    )
            elif tuple(generalized) != tuple(recorded_ops):
                raise ValueError(
                    f"delta history entry {index}: diff(pre, post) "
                    f"{tuple(generalized)!r} does not match the recorded batch "
                    f"{tuple(recorded_ops)!r} for source {source!r}"
                )
            workflow = result.workflow
        return workflow

    def _cas_snapshot(self, workflow: VibeWorkflow | None) -> dict[tuple[str, str], Any]:
        snapshot: dict[tuple[str, str], Any] = {}
        if workflow is None:
            return snapshot
        for node in workflow.nodes.values():
            uid = str(getattr(node, "uid", "") or "")
            if not uid:
                continue
            for name, value in {**node.inputs, **node.widgets}.items():
    else:
        items = (delta,)
    if items and all(isinstance(item, Mapping) for item in items):
        from vibecomfy.porting.edit.ops import parse_edit_delta

        try:
            return parse_edit_delta(list(items))
        except Exception:
            return items
    return items


# ── public API ────────────────────────────────────────────────────────────────


def render(
    wf: VibeWorkflow | Mapping[str, Any],
    lens: str | None = None,
    *,
    lenses: Iterable[str] | None = None,
    delta: Any = (),
    ceiling: Iterable[str] | None = None,
) -> str | tuple[tuple[str, str, str, str], ...] | dict[str, Any]:
    """Render *wf* through exactly the requested lens (set).

    Single-lens form (``lens=``) returns the lens value directly — a
    deterministic string for ``census``/``surface``/``diff`` and the
    structured tuple of edge facts for ``topology``.

    Lens-set form (``lenses=``) returns a dict keyed by lens name with the
    same per-lens values.  When ``topology`` is requested the dict also
    carries ``topology_source: "computed"``.  A lens requested is a lens
    returned — never more (Law 4: judge lens ⊆ reply lens).

    Law 4 is enforced here, not assumed: pass the reply stage's lens set as
    ``ceiling=`` and any requested lens outside it raises
    :class:`LensSubsetViolation` — the judge cannot request a lens the reply
    didn't get; the reply's lens set is the ceiling.
    """
    if lens is not None and lenses is not None:
        raise TypeError("render() accepts lens= or lenses=, not both.")
    if lens is None and lenses is None:
        raise TypeError("render() requires one of lens= or lenses=.")
    workflow = _coerce_workflow(wf)
    batch = _normalise_delta(delta)

    if lens is not None:
        _require_lens(lens)
        _enforce_ceiling((lens,), ceiling)
        return _render_lens_value(workflow, lens, batch)

    names = tuple(lenses or ())
    for name in names:
        _require_lens(name)
    _enforce_ceiling(names, ceiling)
    result: dict[str, Any] = {}
    for name in names:
        result[name] = _render_lens_value(workflow, name, batch)
    if LENS_TOPOLOGY in result:
        result[_TOPOLOGY_SOURCE_KEY] = _TOPOLOGY_SOURCE_COMPUTED
    return result


def render_text(
    wf: VibeWorkflow | Mapping[str, Any] | None,
    lenses: Iterable[str] = (LENS_SURFACE, LENS_TOPOLOGY),
    *,
    delta: Any = (),
    ceiling: Iterable[str] | None = None,
) -> str | None:
    """Render the model-facing text for the requested lens set.

    This is the single entry point stages consume for graph text.  The
    topology contribution is the COMPLETE computed view (every node, every
    edge, computed index) — no truncation.  Returns ``None`` for no graph.

    Law 4 is enforced here too: with ``ceiling=`` (the reply stage's lens
    set), any requested lens outside it raises
    :class:`LensSubsetViolation`.
    """
    if wf is None:
        return None
    workflow = _coerce_workflow(wf)
    batch = _normalise_delta(delta)
    names = tuple(lenses)
    for name in names:
370:def _build_session_context(request: ExecutorRequest) -> dict[str, Any] | None:
401:        chat = agent_edit.read_session_chat(
437:                # read_session_chat already caps at max_messages, but
445:            latest_candidate = chat.get("latest_candidate")
446:            if isinstance(latest_candidate, dict):
447:                context["latest_candidate"] = latest_candidate
504:            prior_route = state.get("blocked_route") or state.get("prior_route")
505:            if isinstance(prior_route, str) and prior_route.strip():
506:                route_text = prior_route.strip()
507:                context["prior_route"] = route_text
526:def _save_clarification_context(
545:        "prior_route": plan.effective_route,
736:            or session_context.get("latest_candidate")
737:            or session_context.get("prior_route")

exec
/bin/zsh -lc "sed -n '650,860p' vibecomfy/executor/tool_specs.py
sed -n '340,565p' vibecomfy/executor/core.py
sed -n '1040,1135p' vibecomfy/executor/contracts.py
sed -n '1830,1915p' vibecomfy/executor/contracts.py
rg -n \"Report\\(|to_dict\\(self\\).*Report|class ExecutorResult|report.to_dict|model_attempts\" vibecomfy/executor/contracts.py | sed -n '1,180p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
    ``handler(session, args, budget_payload)`` invokes the tool module and
    returns a typed :class:`ToolResult`.  ``projector(args, result, session)``
    maps one completed call to ``(evidence_artifacts, ledger_entry, digest)``
    — the only channel by which tool output crosses turns.
    """

    name: str
    phase: str
    description: str
    handler: Callable[[Any, Mapping[str, Any], Any], ToolResult] = field(repr=False)
    projector: Callable[
        [Mapping[str, Any], ToolResult, Any],
        tuple[dict[str, EvidenceArtifact], dict[str, Any], str],
    ] = field(repr=False)
    positional_names: tuple[str, ...] = ()
    keywords: frozenset[str] = frozenset()
    required: tuple[str, ...] = ()
    budget_class: str | None = None

    def __post_init__(self) -> None:
        if self.phase not in _PHASES:
            raise ValueError(f"ToolSpec {self.name!r}: unknown phase {self.phase!r}.")
        if self.name not in self.keywords and not self.positional_names:
            raise ValueError(f"ToolSpec {self.name!r}: no callable argument surface.")

    def catalog_line(self) -> str:
        """One compact prompt-doc line for this tool."""
        positional = ", ".join(self.positional_names) or "…"
        return f"- `{self.name}({positional})` — {self.description}"


def _tool_spec(
    *,
    name: str,
    phase: str,
    description: str,
    positional_names: tuple[str, ...],
    keywords: tuple[str, ...],
    required: tuple[str, ...] = (),
    budget_class: str | None = None,
    handler: Callable[[Any, Mapping[str, Any], Any], ToolResult],
    projector: Callable[
        [Mapping[str, Any], ToolResult, Any],
        tuple[dict[str, EvidenceArtifact], dict[str, Any], str],
    ],
) -> ToolSpec:
    return ToolSpec(
        name=name,
        phase=phase,
        description=description,
        positional_names=positional_names,
        keywords=frozenset(keywords),
        required=required,
        budget_class=budget_class,
        handler=handler,
        projector=projector,
    )


TOOL_SPECS: tuple[ToolSpec, ...] = (
    _tool_spec(
        name="hivemind_search",
        phase=PHASE_RESEARCH,
        description=(
            "search the Hivemind corpus (Discord community, external resources, "
            "curated distillations) for workflow precedents and community knowledge"
        ),
        positional_names=("query",),
        keywords=("query", "filters", "cursor", "limit", "timeout"),
        required=("query",),
        budget_class="search",
        handler=_hivemind_search_handler,
        projector=_hivemind_search_projector,
    ),
    _tool_spec(
        name="hivemind_get",
        phase=PHASE_RESEARCH,
        description="resolve one returned evidence ID to its full Hivemind record",
        positional_names=("evidence_id",),
        keywords=("evidence_id", "timeout"),
        required=("evidence_id",),
        budget_class="fetch",
        handler=_hivemind_get_handler,
        projector=_hivemind_get_projector,
    ),
    _tool_spec(
        name="registry_lookup",
        phase=PHASE_RESEARCH,
        description="find which node pack owns a node class (Comfy registry; exactly one batch per session)",
        positional_names=("node_class",),
        keywords=("node_class",),
        required=("node_class",),
        budget_class="registry",
        handler=_registry_lookup_handler,
        projector=_registry_projector,
    ),
    _tool_spec(
        name="web_search",
        phase=PHASE_RESEARCH,
        description=(
            "last-resort public web search; disabled unless explicitly enabled"
        ),
        positional_names=("query",),
        keywords=("query", "unresolved_question", "timeout"),
        required=("query",),
        budget_class="search",
        handler=_web_search_handler,
        projector=_web_search_projector,
    ),
    _tool_spec(
        name="node_schema",
        phase=PHASE_IMPLEMENT,
        description="read the runtime/local schema of one node class (availability, inputs, outputs)",
        positional_names=("node_class",),
        keywords=("node_class",),
        required=("node_class",),
        budget_class="fetch",
        handler=_node_schema_handler,
        projector=_node_schema_projector,
    ),
    _tool_spec(
        name="ready_template_list",
        phase=PHASE_IMPLEMENT,
        description="list ready workflow templates by capability (direct-load asset inventory; NOT research evidence)",
        positional_names=("capability",),
        keywords=("capability", "include_dynamic"),
        handler=_ready_template_list_handler,
        projector=_ready_template_list_projector,
    ),
    _tool_spec(
        name="ready_template_load",
        phase=PHASE_IMPLEMENT,
        description="load one ready template by id (direct-load shipping asset; NOT research evidence)",
        positional_names=("template_id",),
        keywords=("template_id", "include_dynamic", "include_content"),
        required=("template_id",),
        budget_class="fetch",
        handler=_ready_template_load_handler,
        projector=_ready_template_load_projector,
    ),
    _tool_spec(
        name="rank_edit_targets",
        phase=PHASE_IMPLEMENT,
        description="rank candidate edit targets in the current graph for an intent (advisory, explicit call only)",
        positional_names=("intent",),
        keywords=("intent", "max_targets"),
        required=("intent",),
        handler=_rank_edit_targets_handler,
        projector=_rank_edit_targets_projector,
    ),
    _tool_spec(
        name="suggest_seed_nodes",
        phase=PHASE_IMPLEMENT,
        description="suggest starting node classes for authoring (empty-graph case; visible alternatives)",
        positional_names=("intent", "constraints"),
        keywords=("intent", "constraints", "max_suggestions"),
        required=("intent",),
        handler=_suggest_seed_nodes_handler,
        projector=_suggest_seed_nodes_projector,
    ),
    _tool_spec(
        name="layout_hints",
        phase=PHASE_IMPLEMENT,
        description="suggest placement positions/groups for a node insertion (advisory)",
        positional_names=("operation", "anchors"),
        keywords=("operation", "anchors"),
        required=("operation",),
        handler=_layout_hints_handler,
        projector=_layout_hints_projector,
    ),
)

TOOL_SPEC_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}

if len(TOOL_SPEC_BY_NAME) != len(TOOL_SPECS):
    raise ValueError("ToolSpec registry contains duplicate tool names.")

AGENT_TOOL_CALL_NAMES: frozenset[str] = frozenset(TOOL_SPEC_BY_NAME)

RESEARCH_PHASE_TOOLS: frozenset[str] = frozenset(
    spec.name for spec in TOOL_SPECS if spec.phase == PHASE_RESEARCH
)
IMPLEMENT_PHASE_TOOLS: frozenset[str] = frozenset(
    spec.name for spec in TOOL_SPECS if spec.phase == PHASE_IMPLEMENT
)

# The two phase sets must be a clean partition of every registered tool: a
# tool is research or implement, never both, never neither.
if RESEARCH_PHASE_TOOLS | IMPLEMENT_PHASE_TOOLS != AGENT_TOOL_CALL_NAMES:
    raise ValueError("Tool phase partition does not cover every registered tool.")
if RESEARCH_PHASE_TOOLS & IMPLEMENT_PHASE_TOOLS:
    raise ValueError("Tool phase partition overlaps.")


def phase_for_tool(name: str) -> str:
    try:
        return TOOL_SPEC_BY_NAME[name].phase
    except KeyError:
        raise ValueError(f"Unknown agent tool {name!r}.") from None


def phase_allows(phase: str | None, name: str) -> bool:
    """True when *name* may be called in *phase*.

    ``None`` (unknown/offline phase context) is permissive so standalone
    parsers and offline validation can check either phase; the live batch
    REPL always carries an explicit phase marker.
    """
    if phase is None:
        return name in TOOL_SPEC_BY_NAME
    return phase_for_tool(name) == phase

    return render_text(graph, lenses=_CLASSIFY_LENSES)


def _accepted_delta_ops(
    implementation_result: ImplementationResult | None,
) -> tuple[dict[str, Any], ...]:
    """Return the accepted Δ ops from the implement phase's durable response.

    The canonical Δ is ``accepted_batch`` (batch 10): the accepted edit
    statements that landed, each carrying its typed ``op``.  No other
    representation (``batch_turns[].delta_ops_envelope`` / ``delta_ops``,
    the top-level ``delta_ops_envelope`` / ``delta_ops``) is consulted —
    one source.  Pure structured extraction — prose is never used.
    """
    if implementation_result is None:
        return ()
    durable = implementation_result.durable_response
    if not isinstance(durable, Mapping):
        return ()
    accepted = durable.get("accepted_batch")
    if not isinstance(accepted, list):
        return ()
    ops = [
        dict(item["op"]) for item in accepted
        if isinstance(item, Mapping) and isinstance(item.get("op"), Mapping)
    ]
    return tuple(ops)


def _build_session_context(request: ExecutorRequest) -> dict[str, Any] | None:
    """Build session context for reference resolution in the classify phase.

    Loads the last ``PROMPT_MEMORY_MESSAGES`` (5) durable chat messages in
    chronological order from persisted turn artifacts.  The backend-owned
    durable session store is the **only** source of prompt history — frontend
    ``recent_messages`` are never consulted as primary state (SD1: durable ==
    canonical).

    Also loads prior clarification context, latest candidate, and blocked
    route/task from session state so downstream classify logic can resolve
    follow-up references.

    Defensively tolerates malformed historical chat artifacts (non-dict
    messages, missing ``role`` / ``text`` keys, corrupt chat.json) by
    skipping unrecoverable entries rather than raising.

    Returns ``None`` when no session context is available (no session_id,
    store unavailable, etc.).
    """
    if not request.session_id:
        return None

    context: dict[str, Any] = {}
    chat_prior_clarification = False

    # ── Durable chat messages (backend-owned, SD1) ────────────────────────
    try:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        prompt_memory = getattr(agent_edit, "PROMPT_MEMORY_MESSAGES", 5)
        chat = agent_edit.read_session_chat(
            getattr(agent_edit, "_SESSION_ROOT"),
            request.session_id,
            max_messages=prompt_memory,
        )
        if isinstance(chat, dict):
            raw_messages = chat.get("messages")
            if isinstance(raw_messages, list):
                # Defensively filter: keep only well-formed dicts with both
                # ``role`` and ``text``.  Malformed entries are silently
                # skipped so a single corrupt turn artifact cannot poison the
                # entire prompt context.
                durable_messages: list[dict[str, Any]] = []
                for msg in raw_messages:
                    if not isinstance(msg, dict):
                        continue
                    role = msg.get("role")
                    text = msg.get("text")
                    if not isinstance(role, str) or not role.strip():
                        continue
                    if not isinstance(text, str):
                        continue
                    # Normalise: store minimal fields consumed by prompt
                    # construction and classifier reference resolution.
                    entry: dict[str, Any] = {"role": role.strip(), "text": text}
                    turn_id = msg.get("turn_id")
                    if isinstance(turn_id, str) and turn_id.strip():
                        entry["turn_id"] = turn_id.strip()
                    outcome = msg.get("outcome")
                    if isinstance(outcome, dict):
                        entry["outcome"] = outcome
                    change_details = msg.get("change_details")
                    if isinstance(change_details, dict):
                        entry["change_details"] = change_details
                    durable_messages.append(entry)

                # read_session_chat already caps at max_messages, but
                # enforce the hard cap here as a defensive second gate.
                if len(durable_messages) > prompt_memory:
                    durable_messages = durable_messages[-prompt_memory:]

                if durable_messages:
                    context["recent_messages"] = durable_messages

            latest_candidate = chat.get("latest_candidate")
            if isinstance(latest_candidate, dict):
                context["latest_candidate"] = latest_candidate

            # Extract prior clarification from the most recent agent message
            # whose outcome kind is ``clarify``.  Scan raw_messages (which may
            # include entries skipped by the durable filter above).
            latest_agent = next(
                (
                    msg for msg in reversed(raw_messages if isinstance(raw_messages, list) else [])
                    if isinstance(msg, dict)
                    and msg.get("role") == "agent"
                    and isinstance(msg.get("outcome"), dict)
                    and msg["outcome"].get("kind") == "clarify"
                ),
                None,
            )
            if latest_agent is not None:
                outcome = latest_agent.get("outcome")
                question = (
                    outcome.get("question")
                    if isinstance(outcome, dict)
                    and isinstance(outcome.get("question"), str)
                    else latest_agent.get("text")
                )
                prior: dict[str, Any] = {}
                if isinstance(question, str) and question.strip():
                    prior["clarification_question"] = question.strip()
                options = (
                    outcome.get("options")
                    if isinstance(outcome, dict)
                    and isinstance(outcome.get("options"), list)
                    else None
                )
                if options:
                    prior["clarification_options"] = [
                        str(opt) for opt in options if str(opt).strip()
                    ]
                if prior:
                    context["prior_clarification"] = prior
                    chat_prior_clarification = True

        from vibecomfy.comfy_nodes.agent.session import (
            read_state,
            session_dir_for,
        )

        state = read_state(session_dir_for(getattr(agent_edit, "_SESSION_ROOT"), request.session_id))
        if isinstance(state, dict):
            # Carry forward prior clarification context if present.  Durable
            # chat is newer/more specific than session_state, so don't let a
            # stale saved clarification overwrite the latest chat turn.
            prior_clarification = state.get("prior_clarification")
            if isinstance(prior_clarification, dict) and not chat_prior_clarification:
                context["prior_clarification"] = prior_clarification

            # Carry forward blocked route/task for continuation. Prefer the
            # intended blocked route over the public clarify route when both
            # are present.
            prior_route = state.get("blocked_route") or state.get("prior_route")
            if isinstance(prior_route, str) and prior_route.strip():
                route_text = prior_route.strip()
                context["prior_route"] = route_text
                if isinstance(state.get("blocked_route"), str) and state["blocked_route"].strip():
                    context["blocked_route"] = route_text
                prior_task = state.get("blocked_task") or state.get("prior_task")
                if isinstance(prior_task, str) and prior_task.strip():
                    task_text = prior_task.strip()
                    context["prior_task"] = task_text
                    if isinstance(state.get("blocked_task"), str) and state["blocked_task"].strip():
                        context["blocked_task"] = task_text
    except Exception:
        LOGGER.debug(
            "session_context: could not load session state for %r",
            request.session_id,
            exc_info=True,
        )

    return context if context else None


def _save_clarification_context(
    request: ExecutorRequest,
    plan: ClassifyDecision,
    *,
    blocked_route: str | None = None,
    blocked_task: str | None = None,
) -> None:
    """Persist clarification artifacts to the session for follow-up resolution.

    Best-effort: failures are logged and never propagate.
    """
    if not request.session_id:
        return

    clarification_context: dict[str, Any] = {
        "prior_clarification": {
            "clarification_question": plan.clarification_question or plan.plan_summary,
            "clarification_options": list(plan.clarification_options),
        },
        "prior_route": plan.effective_route,
        "prior_task": plan.effective_task,
    }
    if isinstance(blocked_route, str) and blocked_route.strip():
        clarification_context["blocked_route"] = blocked_route.strip()
    if isinstance(blocked_task, str) and blocked_task.strip():
        clarification_context["blocked_task"] = blocked_task.strip()

    try:
        from vibecomfy.comfy_nodes.agent.session import (
            read_state,
            session_dir_for,
            write_state_atomic,
        )

        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        sdir = session_dir_for(getattr(agent_edit, "_SESSION_ROOT"), request.session_id)
        if sdir is not None:
            # Merge with existing state to preserve messages.
            existing: dict[str, Any] = read_state(sdir)
        workflow_id = payload.get("workflow_id")
        if workflow_id is not None and not isinstance(workflow_id, str):
            raise ValueError("ExecutorRequest `workflow_id` must be a string or null.")
        graph_workflow_id = graph.get("id") if isinstance(graph, dict) else None
        if workflow_id is None and isinstance(graph_workflow_id, str):
            # Older already-loaded browser modules did not send the new
            # top-level fence. Canonicalize the identity at ingress from the
            # same serialized graph instead of failing after model execution.
            workflow_id = graph_workflow_id
        if workflow_id is not None:
            from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (  # noqa: PLC0415
                ContractError,
                workflow_identity_v1,
            )

            try:
                workflow_identity_v1(workflow_id)
                if isinstance(graph_workflow_id, str):
                    workflow_identity_v1(graph_workflow_id)
            except ContractError as exc:
                raise ValueError(str(exc)) from exc
            if isinstance(graph_workflow_id, str) and graph_workflow_id != workflow_id:
                raise ValueError(
                    "ExecutorRequest `workflow_id` must match the attached graph `id`."
                )
        session_id = payload.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("ExecutorRequest `session_id` must be a string or null.")
        if session_id is not None:
            from vibecomfy.comfy_nodes.agent.session import normalize_session_id  # noqa: PLC0415

            session_id = normalize_session_id(session_id)
        profile = payload.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise ValueError("ExecutorRequest `profile` must be a string or null.")
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise ValueError("ExecutorRequest `idempotency_key` must be a string or null.")
        client_graph_hash = payload.get("client_graph_hash")
        if client_graph_hash is not None and not isinstance(client_graph_hash, str):
            raise ValueError("ExecutorRequest `client_graph_hash` must be a string or null.")
        client_structural_graph_hash = payload.get("client_structural_graph_hash")
        if client_structural_graph_hash is not None and not isinstance(
            client_structural_graph_hash, str
        ):
            raise ValueError(
                "ExecutorRequest `client_structural_graph_hash` must be a string or null."
            )
        client_live_canvas_token = payload.get("client_live_canvas_token")
        if client_live_canvas_token is not None and not isinstance(client_live_canvas_token, str):
            raise ValueError("ExecutorRequest `client_live_canvas_token` must be a string or null.")
        expected_baseline_graph_hash = payload.get("expected_baseline_graph_hash")
        expected_baseline_graph_hash_present = "expected_baseline_graph_hash" in payload
        on_demand_schemas = payload.get("on_demand_schemas")
        if not isinstance(on_demand_schemas, bool):
            on_demand_schemas = None
        interaction_mode = payload.get("interaction_mode")
        if interaction_mode is not None and not isinstance(interaction_mode, str):
            raise ValueError(
                "ExecutorRequest `interaction_mode` must be a string or null."
            )
        max_batches = coerce_max_batches(payload.get("max_batches"), field_name="max_batches")
        if expected_baseline_graph_hash is not None and not isinstance(
            expected_baseline_graph_hash, str
        ):
            raise ValueError(
                "ExecutorRequest `expected_baseline_graph_hash` must be a string or null."
            )
        return cls(
            query=query.strip(),
            graph=graph,
            workflow_id=workflow_id,
            session_id=session_id,
            profile=profile,
            idempotency_key=idempotency_key,
            client_graph_hash=client_graph_hash,
            client_structural_graph_hash=client_structural_graph_hash,
            client_live_canvas_token=client_live_canvas_token,
            expected_baseline_graph_hash=expected_baseline_graph_hash,
            expected_baseline_graph_hash_present=expected_baseline_graph_hash_present,
            on_demand_schemas=on_demand_schemas,
            interaction_mode=interaction_mode,
            max_batches=max_batches,
        )





# ── topology manifest (W-02) ──────────────────────────────────────────────────

class ManifestOversized(ValueError):
    """Raised when a manifest exceeds its size bounds (never silently truncate)."""


@dataclass(frozen=True)

# ── report (nested executor metadata) ────────────────────────────────────────


@dataclass(frozen=True)
class Report:
    """Executor metadata nested under ``report`` in the final envelope.

    Every phase's output is captured here so the envelope stays a stable
    ``{message, outcome, candidate, eligibility, report}`` shape without
    new top-level fields.

    ``research`` carries the H01 :class:`~vibecomfy.executor.core.AgentResearchResult`
    (F01 evidence pack + C5 decision memo).  Legacy research-result payloads
    (``precedent_packet`` / ``adaptation_plan`` / ``precedent_slices``) were
    removed by the agent-judgment rework (D02) and are rejected explicitly
    instead of being silently rewritten.
    """

    plan: ClassifyDecision | None = None
    research: "AgentResearchResult | None" = None
    implementation: ImplementationResult | None = None
    deepseek_usage: dict[str, Any] = field(default_factory=dict)
    deepseek_est_cost_usd: float | None = None
    deepseek_cost_basis: str | None = None
    # Truthful classification lifecycle signal: "failed" means classify raised
    # (the plan is then None — no invented respond_only placeholder). Empty
    # string means the signal was not recorded (legacy paths).
    classification_status: str = ""
    # Canonical per-call evidence for every successful and failed model attempt
    # observed across classify, implement/batch, and reply.
    model_attempts: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.research is not None and not callable(getattr(self.research, "to_dict", None)):
            raise TypeError(
                "Report.research must be an AgentResearchResult (or None). "
                "Legacy research-result payloads were removed (D02); serialize "
                "the F01 evidence pack / C5 decision memo instead. "
                f"got {type(self.research).__name__}"
            )
        object.__setattr__(
            self,
            "deepseek_usage",
            MappingProxyType({
                str(k): _freeze_jsonish(v)
                for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
            }),
        )
        object.__setattr__(
            self,
            "model_attempts",
            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
        )

    @property
    def model_response(self) -> dict[str, Any] | None:
        """Compatibility view derived solely from canonical ``model_attempts``."""
        if not self.model_attempts:
            return None
        return {
            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
        }

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
276:def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
1699:            readiness = ReadinessReport()
1861:    model_attempts: tuple[dict[str, Any], ...] = ()
1881:            "model_attempts",
1882:            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
1887:        """Compatibility view derived solely from canonical ``model_attempts``."""
1888:        if not self.model_attempts:
1891:            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
1916:        inner["model_attempts"] = [
1917:            _thaw_jsonish(item) for item in self.model_attempts
2156:class ExecutorResult:
2179:            "report": self.report.to_dict(),
2183:        payload["model_attempts"] = [
2184:            _thaw_jsonish(item) for item in self.report.model_attempts
2222:        return cls(ok=True, report=report or Report(), graph=graph, reply=reply)
2235:            report=report or Report(),
2454:    "coerce_model_attempts",

exec
/bin/zsh -lc "rg -n \"load_profile|DECLARED_STAGES|profile_data|missing.*stage|profile\" tests | rg \"executor|profile\" | sed -n '1,240p'
rg -n \"_ROUTE_BEHAVIORS|effective_route|route coverage|tool denial|budget|prompt\" tests/test_executor_* tests/test_agent_executor_response.py tests/test_porting_edit_session_harness.py tests/test_edit_batch_repl_dependencies.py | sed -n '1,300p'
rg --files tests | rg 'law|ir_|porting_(edit|render)|executor' | sort" in /private/tmp/vc-twostep
 succeeded in 0ms:
tests/test_runtime_run.py:133:        "memory_profile": 5,
tests/test_runtime_run.py:164:    assert config.memory_profile == 5
tests/test_runtime_run.py:177:    workflow.metadata["comfy_configuration"] = {"memory_profile": 5}
tests/test_runtime_run.py:677:def test_cmd_run_memory_profile_overrides_embedded_config(
tests/test_runtime_run.py:682:        "memory_profile": 4,
tests/test_runtime_run.py:695:        memory_profile=5,
tests/test_runtime_run.py:725:    assert embedded_configs[0].memory_profile == 5
tests/test_runtime_run.py:732:def test_cmd_run_memory_profile_overrides_new_managed_server_config(
tests/test_runtime_run.py:737:        "memory_profile": 4,
tests/test_runtime_run.py:750:        memory_profile=5,
tests/test_runtime_run.py:780:    assert server_configs[0].memory_profile == 5
tests/test_runtime_run.py:786:def test_cmd_run_memory_profile_rejects_explicit_external_server(
tests/test_runtime_run.py:798:        memory_profile=5,
tests/test_runtime_run.py:811:def test_cmd_run_memory_profile_rejects_active_session(
tests/test_runtime_run.py:823:        memory_profile=5,
tests/test_memory_profile.py:5:from vibecomfy.memory_profile import (
tests/test_memory_profile.py:7:    apply_memory_profile_overrides,
tests/test_memory_profile.py:8:    memory_profile_telemetry,
tests/test_memory_profile.py:9:    parse_memory_profile,
tests/test_memory_profile.py:10:    serialize_memory_profile,
tests/test_memory_profile.py:11:    session_overrides_for_memory_profile,
tests/test_memory_profile.py:16:def test_memory_profiles_parse_integer_values_and_expose_labels() -> None:
tests/test_memory_profile.py:26:        profile = parse_memory_profile(value)
tests/test_memory_profile.py:27:        assert profile.serialize() == value
tests/test_memory_profile.py:28:        assert serialize_memory_profile(profile) == value
tests/test_memory_profile.py:29:        assert profile.label == label
tests/test_memory_profile.py:33:def test_memory_profile_rejects_non_integer_or_out_of_range_values(value: object) -> None:
tests/test_memory_profile.py:35:        parse_memory_profile(value)  # type: ignore[arg-type]
tests/test_memory_profile.py:38:def test_memory_profile_session_overrides_match_sprint_1_mapping() -> None:
tests/test_memory_profile.py:39:    assert session_overrides_for_memory_profile(1) == {"vram_policy": "high", "cache_policy": "smart"}
tests/test_memory_profile.py:40:    assert session_overrides_for_memory_profile(2) == {"vram_policy": "high", "cache_policy": "lru:32"}
tests/test_memory_profile.py:41:    assert session_overrides_for_memory_profile(3) == {"vram_policy": "normal", "cache_policy": "smart"}
tests/test_memory_profile.py:42:    assert session_overrides_for_memory_profile(4) == {
tests/test_memory_profile.py:47:    assert session_overrides_for_memory_profile(5) == {
tests/test_memory_profile.py:55:def test_memory_profile_telemetry_uses_public_label() -> None:
tests/test_memory_profile.py:56:    assert memory_profile_telemetry(4) == {
tests/test_memory_profile.py:57:        "memory_profile": 4,
tests/test_memory_profile.py:58:        "memory_profile_label": "Very Low VRAM",
tests/test_memory_profile.py:62:def test_apply_memory_profile_overrides_with_profile_precedence_is_non_mutating() -> None:
tests/test_memory_profile.py:65:    resolved = apply_memory_profile_overrides(config, MemoryProfile.MINIMUM, precedence="profile")
tests/test_memory_profile.py:76:def test_apply_memory_profile_overrides_with_config_precedence_preserves_explicit_fields() -> None:
tests/test_memory_profile.py:79:    resolved = apply_memory_profile_overrides(config, MemoryProfile.MINIMUM, precedence="config")
tests/test_memory_profile.py:89:def test_apply_memory_profile_overrides_with_config_precedence_fills_default_fields() -> None:
tests/test_memory_profile.py:92:    resolved = apply_memory_profile_overrides(config, 4, precedence="config")
tests/test_session_cli.py:15:from vibecomfy.memory_profile import MemoryProfile
tests/test_session_cli.py:90:        memory_profile=None,
tests/test_session_cli.py:123:def test_session_cli_start_persists_memory_profiles(
tests/test_session_cli.py:133:    for profile in range(1, 6):
tests/test_session_cli.py:135:            id=f"profile-{profile}",
tests/test_session_cli.py:136:            port=8200 + profile,
tests/test_session_cli.py:142:            memory_profile=profile,
tests/test_session_cli.py:147:            (tmp_path / f"out/sessions/profile-{profile}/config.json").read_text(encoding="utf-8")
tests/test_session_cli.py:149:        assert config["memory_profile"] == profile
tests/test_session_cli.py:150:        assert config["port"] == 8200 + profile
tests/test_session_cli.py:152:        assert effective.memory_profile == profile
tests/test_session_cli.py:153:        for key, value in MemoryProfile(profile).to_session_overrides().items():
tests/test_session_cli.py:157:def test_session_cli_start_without_memory_profile_leaves_config_unchanged(
tests/test_session_cli.py:174:        memory_profile=None,
tests/test_session_cli.py:180:    assert "memory_profile" not in config
tests/test_session_cli.py:223:        memory_profile=None,
tests/test_session_cli.py:438:        "memory_profile": 3,
tests/test_session_cli.py:459:        memory_profile=MemoryProfile.LOW_VRAM,
tests/test_executor_contracts.py:96:        assert req.profile is None
tests/test_executor_contracts.py:111:            profile="default",
tests/test_executor_contracts.py:121:        assert req.profile == "default"
tests/test_executor_contracts.py:155:            profile="default",
tests/test_executor_contracts.py:167:        assert d["profile"] == "default"
tests/test_executor_contracts.py:185:            "profile": "default",
tests/test_executor_contracts.py:609:            requested_model="profile-alias",
tests/test_executor_contracts.py:620:        assert payload["requested_model"] == "profile-alias"
tests/test_release_guard_four_category.py:409:            profile="unit-test",
tests/test_headless_agent_cli.py:21:def test_cli_blocked_on_missing_profile(tmp_path: Path) -> None:
tests/test_headless_agent_cli.py:32:            "--profile",
tests/test_headless_agent_cli.py:33:            "__missing_profile_for_test__",
tests/test_headless_agent_cli.py:105:            "--profile",
tests/test_headless_agent_cli.py:123:    assert request.profile == "default"
tests/test_agent_runtime_adapter.py:991:    profile phase (classify/research/implement/reply).  The ambient OpenRouter
tests/pi_transition/TEST_PLAN.md:11:**Risk profile:** Protocol drift (response contract shapes), credential routing regressions,
tests/test_megaplan_chain_spec.py:18:    assert {milestone["profile"] for milestone in milestones} == {"all-codex"}
tests/test_megaplan_chain_spec.py:26:    assert "profile: all-codex" in readme
tests/test_demo_factory_multinode.py:156:            profile="unit-test",
tests/test_agent_research_shadow.py:35:from vibecomfy.executor.profiles import AgentSpecShape, set_profile_override_dir
tests/test_agent_research_shadow.py:64:def profile_dir(tmp_path: Path) -> Path:
tests/test_agent_research_shadow.py:65:    dir_path = tmp_path / "profiles"
tests/test_agent_research_shadow.py:70:    set_profile_override_dir(dir_path)
tests/test_agent_research_shadow.py:72:    set_profile_override_dir(None)
tests/test_agent_research_shadow.py:242:        self, profile_dir: Path
tests/test_agent_research_shadow.py:307:        self, profile_dir: Path
tests/test_agent_research_shadow.py:352:    def test_deadline_exhaustion_is_exhausted_not_ok(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:382:        self, profile_dir: Path
tests/test_agent_research_shadow.py:429:    def test_phase_allowlist_refuses_implement_tools(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:471:    def test_registry_lookup_is_agent_callable(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:529:    def test_missing_required_query_is_typed_invalid_request(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:561:    def test_declared_search_args_reach_the_handler(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:609:    def test_malformed_limit_is_typed_invalid_request(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:648:        self, profile_dir: Path
tests/test_agent_research_shadow.py:701:        self, profile_dir: Path, monkeypatch: pytest.MonkeyPatch
tests/test_agent_research_shadow.py:753:            profile="default",
tests/test_agent_research_shadow.py:782:    def test_finish_before_any_tool_call_is_finish_premature_refinement(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:841:    def test_repeated_premature_finishes_stay_bounded_and_exhausted(self, profile_dir: Path) -> None:
tests/test_agent_research_shadow.py:880:    def test_adapt_zero_tool_loop_executes_fallback_search(self, profile_dir: Path) -> None:
tests/test_runtime_session_config.py:13:from vibecomfy.memory_profile import MemoryProfile
tests/test_runtime_session_config.py:23:    apply_memory_profile_override,
tests/test_runtime_session_config.py:247:def test_session_config_memory_profile_overlay_uses_normal_precedence() -> None:
tests/test_runtime_session_config.py:250:            "memory_profile": 5,
tests/test_runtime_session_config.py:257:    assert config.memory_profile is MemoryProfile.MINIMUM
tests/test_runtime_session_config.py:264:def test_session_config_memory_profile_overlay_respects_raw_hiddenswitch_precedence() -> None:
tests/test_runtime_session_config.py:267:            "memory_profile": 1,
tests/test_runtime_session_config.py:274:    assert config.memory_profile is MemoryProfile.LOW_RAM
tests/test_runtime_session_config.py:281:def test_session_config_memory_profile_rejects_invalid_values(value: object) -> None:
tests/test_runtime_session_config.py:283:        SessionConfig.from_dict({"memory_profile": value})
tests/test_runtime_session_config.py:286:def test_from_workflow_metadata_applies_memory_profile_before_explicit_fields() -> None:
tests/test_runtime_session_config.py:289:        "memory_profile": 4,
tests/test_runtime_session_config.py:296:    assert config.memory_profile is MemoryProfile.VERY_LOW_VRAM
tests/test_runtime_session_config.py:302:def test_explicit_memory_profile_override_wins_after_workflow_metadata_resolution() -> None:
tests/test_runtime_session_config.py:305:        "memory_profile": 4,
tests/test_runtime_session_config.py:311:    resolved = apply_memory_profile_override(config, 5)
tests/test_runtime_session_config.py:313:    assert config.memory_profile is MemoryProfile.VERY_LOW_VRAM
tests/test_runtime_session_config.py:316:    assert resolved.memory_profile is MemoryProfile.MINIMUM
tests/test_runtime_session_config.py:322:        "memory_profile": 4,
tests/test_runtime_session_config.py:328:def test_memory_profiles_round_trip_to_embedded_config_and_server_argv(fake_comfy) -> None:
tests/test_runtime_session_config.py:337:    for value, profile_expected in expected.items():
tests/test_runtime_session_config.py:338:        config = SessionConfig.from_dict({"memory_profile": value, "port": 8200})
tests/test_runtime_session_config.py:342:        assert config.memory_profile == value
tests/test_runtime_session_config.py:344:        assert getattr(embedded, profile_expected["vram"].removeprefix("--")) is True
tests/test_runtime_session_config.py:345:        assert profile_expected["vram"] in argv
tests/test_runtime_session_config.py:348:        cache = profile_expected["cache"]
tests/test_runtime_session_config.py:361:        if profile_expected["reserve"] is None:
tests/test_runtime_session_config.py:365:            assert argv[argv.index("--reserve-vram") + 1] == profile_expected["reserve"]
tests/test_runtime_session_config.py:366:            assert embedded.reserve_vram == float(profile_expected["reserve"])
tests/test_runtime_session_config.py:368:        if profile_expected["disable"]:
tests/test_runtime_session_config.py:376:def test_sage_attention_profile_maps_to_embedded_config_and_server_argv(
tests/test_runtime_session_config.py:423:def test_run_metadata_includes_memory_profile_telemetry_when_configured() -> None:
tests/test_runtime_session_config.py:431:        config=SessionConfig.from_dict({"memory_profile": 3}),
tests/test_runtime_session_config.py:435:    assert metadata["memory_profile"] == 3
tests/test_runtime_session_config.py:436:    assert metadata["memory_profile_label"] == "Low VRAM"
tests/test_runtime_session_config.py:440:def test_run_metadata_omits_memory_profile_telemetry_when_unset() -> None:
tests/test_runtime_session_config.py:451:    assert "memory_profile" not in metadata
tests/test_runtime_session_config.py:452:    assert "memory_profile_label" not in metadata
tests/structural_harness/actors_agent_judgment.py:205:        profile="default",
tests/structural_harness/actors_agent_judgment.py:393:        profile="default",
tests/structural_harness/actors_agent_judgment.py:635:        profile="default",
tests/structural_harness/actors_agent_judgment.py:1014:        profile="default",
tests/structural_harness/actors_agent_judgment.py:1020:        profile="default",
tests/structural_harness/actors_agent_judgment.py:1210:        profile="default",
tests/structural_harness/actors_agent_judgment.py:1403:        profile="default",
tests/structural_harness/actors_agent_judgment.py:1623:        profile="default",
tests/structural_harness/actors_agent_judgment.py:1629:        profile="default",
tests/test_run_command.py:29:        memory_profile=None,
tests/structural_harness/actors.py:1105:        profile="default",
tests/structural_harness/actors.py:1230:                "profile": request.profile,
tests/structural_harness/actors.py:1300:        profile="default",
tests/structural_harness/actors.py:1430:                "profile": request.profile,
tests/structural_harness/actors.py:1499:        profile="default",
tests/structural_harness/actors.py:1859:        profile="default",
tests/structural_harness/actors.py:2229:        profile="default",
tests/structural_harness/actors.py:2333:                "profile": request.profile,
tests/structural_harness/actors.py:2424:        profile="default",
tests/live_agentic_harness/scenario_manifest.json:1843:    "profile": "default",
tests/live_agentic_harness/runner.py:700:    survives subprocess isolation into every profile phase.  ``None`` resolves
tests/live_agentic_harness/runner.py:993:            "Explicit model-call transport for every profile phase "
tests/structural_harness/actors_m5/route_intent_map.py:116:            profile="default",
tests/test_comfy_nodes_agent_edit.py:8934:def test_agent_executor_route_maps_codex_selection_to_openai_profile(
tests/test_comfy_nodes_agent_edit.py:8946:        captured["profile"] = request.profile
tests/test_comfy_nodes_agent_edit.py:8959:    assert captured["profile"] == "openai"
tests/test_comfy_nodes_agent_edit.py:8962:def test_agent_executor_route_maps_openrouter_selection_to_openrouter_profile(
tests/test_comfy_nodes_agent_edit.py:8974:        captured["profile"] = request.profile
tests/test_comfy_nodes_agent_edit.py:8987:    assert captured["profile"] == "openrouter"
tests/test_comfy_nodes_agent_edit.py:8990:def test_agent_executor_openrouter_route_overrides_conflicting_client_profile(
tests/test_comfy_nodes_agent_edit.py:9002:        captured["profile"] = request.profile
tests/test_comfy_nodes_agent_edit.py:9011:        "profile": "openai",
tests/test_comfy_nodes_agent_edit.py:9015:    assert captured["profile"] == "openrouter"
tests/test_additive_witness_oracle.py:44:        profile_name: str,
tests/test_additive_witness_oracle.py:396:        profile_name: str,
tests/test_additive_witness_oracle.py:399:        captured["profile"] = profile_name
tests/test_additive_witness_oracle.py:424:    assert judge_gate.detail["profile"] == "judge-test"
tests/test_additive_witness_oracle.py:457:        profile_name: str,
tests/test_additive_witness_oracle.py:515:        profile_name: str,
tests/test_additive_witness_oracle.py:551:        profile_name: str,
tests/test_headless_harness_contract.py:24:from vibecomfy.executor.profiles import set_profile_override_dir
tests/test_headless_harness_contract.py:72:def profile_dir(tmp_path: Path) -> Generator[Path, None, None]:
tests/test_headless_harness_contract.py:73:    dir_path = tmp_path / "profiles"
tests/test_headless_harness_contract.py:75:    set_profile_override_dir(dir_path)
tests/test_headless_harness_contract.py:77:    set_profile_override_dir(None)
tests/test_headless_harness_contract.py:171:    profile_dir: Path,
tests/test_headless_harness_contract.py:215:        profile="default",
tests/test_headless_harness_contract.py:258:    profile_dir: Path,
tests/test_headless_harness_contract.py:350:        profile="default",
tests/test_headless_harness_contract.py:391:    profile_dir: Path,
tests/test_profile_smoke_report.py:8:from tools.profile_smoke_report import (
tests/test_profile_smoke_report.py:9:    build_profile_smoke_report,
tests/test_profile_smoke_report.py:12:    validate_profile_smoke_report,
tests/test_profile_smoke_report.py:16:FIXTURE_DIR = Path(__file__).parent / "fixtures" / "profile_smokes"
tests/test_profile_smoke_report.py:19:@pytest.mark.parametrize("profile", [1, 3])
tests/test_profile_smoke_report.py:20:def test_committed_profile_smoke_fixtures_match_schema(profile: int) -> None:
tests/test_profile_smoke_report.py:21:    data = load_json_file(FIXTURE_DIR / f"profile-{profile}.json")
tests/test_profile_smoke_report.py:23:    validate_profile_smoke_report(data)
tests/test_profile_smoke_report.py:25:    assert data["profile"] == profile
tests/test_profile_smoke_report.py:29:    ("profile", "label"),
tests/test_profile_smoke_report.py:35:def test_build_profile_smoke_report_from_run_artifacts(
tests/test_profile_smoke_report.py:37:    profile: int,
tests/test_profile_smoke_report.py:45:                "run_id": f"profile-{profile}-run",
tests/test_profile_smoke_report.py:48:                "memory_profile": profile,
tests/test_profile_smoke_report.py:49:                "memory_profile_label": label,
tests/test_profile_smoke_report.py:78:    output = tmp_path / f"profile-{profile}.json"
tests/test_profile_smoke_report.py:79:    report = build_profile_smoke_report(
tests/test_profile_smoke_report.py:80:        profile=profile,
tests/test_profile_smoke_report.py:83:        command=f"vibecomfy run video/wan_t2v --ready --runtime embedded --memory-profile {profile}",
tests/test_profile_smoke_report.py:90:    validate_profile_smoke_report(load_json_file(output))
tests/test_profile_smoke_report.py:91:    assert report["profile"] == profile
tests/test_profile_smoke_report.py:92:    assert report["profile_label"] == label
tests/test_profile_smoke_report.py:102:def test_build_profile_smoke_report_rejects_profile_mismatch(tmp_path: Path) -> None:
tests/test_profile_smoke_report.py:108:                "run_id": "profile-1-run",
tests/test_profile_smoke_report.py:111:                "memory_profile": 3,
tests/test_profile_smoke_report.py:112:                "memory_profile_label": "Low VRAM",
tests/test_profile_smoke_report.py:135:    with pytest.raises(ValueError, match="memory_profile must be 1"):
tests/test_profile_smoke_report.py:136:        build_profile_smoke_report(profile=1, run_dir=run_dir)
tests/test_profile_smoke_report.py:139:def test_profile_smoke_report_cli_writes_schema_artifact(tmp_path: Path) -> None:
tests/test_profile_smoke_report.py:145:                "run_id": "profile-1-run",
tests/test_profile_smoke_report.py:148:                "memory_profile": 1,
tests/test_profile_smoke_report.py:149:                "memory_profile_label": "Low RAM",
tests/test_profile_smoke_report.py:171:    output = tmp_path / "profile-1.json"
tests/test_profile_smoke_report.py:175:            "--profile",
tests/test_profile_smoke_report.py:184:            "vibecomfy run video/wan_t2v --ready --runtime embedded --memory-profile 1",
tests/test_profile_smoke_report.py:191:    validate_profile_smoke_report(load_json_file(output))
tests/test_profile_smoke_report.py:194:def test_profile_smoke_report_requires_numeric_vram_sample() -> None:
tests/test_profile_smoke_report.py:195:    data = load_json_file(FIXTURE_DIR / "profile-1.json")
tests/test_profile_smoke_report.py:204:        validate_profile_smoke_report(data)
tests/test_executor_classify_only.py:55:    def _resolve_spec(_profile: str | None, stage: str) -> object:
tests/test_runpod_matrix.py:17:    resolve_attention_profile,
tests/test_runpod_matrix.py:32:def test_attention_profile_defaults_to_portable_sdpa() -> None:
tests/test_runpod_matrix.py:33:    assert resolve_attention_profile(None) == "portable"
tests/test_runpod_matrix.py:34:    assert resolve_attention_profile("default") == "portable"
tests/test_runpod_matrix.py:35:    assert resolve_attention_profile("optimized") == "sage"
tests/test_runpod_matrix.py:38:def test_wanvideo_wrapper_patch_downgrades_sageattn_for_portable_profile() -> None:
tests/test_runpod_matrix.py:51:    assert patch_workflow_api("wanvideo_wrapper_example", api, attention_profile="portable")
tests/test_runpod_matrix.py:60:def test_wanvideo_wrapper_patch_preserves_sageattn_for_sage_profile() -> None:
tests/test_runpod_matrix.py:71:    assert patch_workflow_api("wanvideo_wrapper_example", api, attention_profile="sage")
tests/test_ready_templates.py:494:    assert workflow.metadata["comfy_configuration"] == {"memory_profile": 3, "fp8_e4m3fn_text_enc": True}
tests/test_ready_templates.py:1139:@pytest.mark.parametrize("memory_profile", [1, 2, 3, 4, 5])
tests/test_porting_edit_session_harness.py:288:def test_case_a_set_node_field_prompt(flat_ui: dict[str, Any]) -> None:
tests/test_porting_edit_session_harness.py:289:    """Case (a): Set a prompt text on the positive CLIPTextEncode node."""
tests/test_porting_edit_session_harness.py:297:    code = 'cliptextencode.text = "a faithful edited prompt"'
tests/test_porting_edit_session_harness.py:305:            assert node["widgets_values"] == ["a faithful edited prompt"]
tests/test_executor_contracts.py:1:"""Unit tests for executor contracts and prompt parsing.
tests/test_executor_contracts.py:46:    format_route_options_for_prompt,
tests/test_executor_contracts.py:50:from vibecomfy.executor.prompts import (
tests/test_executor_contracts.py:306:    def test_effective_route_property(self) -> None:
tests/test_executor_contracts.py:307:        """effective_route derives correctly from legacy booleans when route is empty."""
tests/test_executor_contracts.py:309:        assert ClassifyDecision(research=False, implement=True).effective_route == "revise"
tests/test_executor_contracts.py:311:        assert ClassifyDecision(research=True, implement=False).effective_route == "research"
tests/test_executor_contracts.py:313:        assert ClassifyDecision(research=False, implement=False).effective_route == "respond"
tests/test_executor_contracts.py:319:        ).effective_route == "inspect"
tests/test_executor_contracts.py:321:        assert ClassifyDecision(research=True, implement=True).effective_route == "adapt"
tests/test_executor_contracts.py:323:    def test_effective_route_explicit_wins(self) -> None:
tests/test_executor_contracts.py:330:        assert d.effective_route == "adapt"
tests/test_executor_contracts.py:362:        assert d.effective_route == "clarify"
tests/test_executor_contracts.py:401:        assert decision.effective_route == expected_route
tests/test_executor_contracts.py:425:        assert d.effective_route == "inspect"
tests/test_executor_contracts.py:443:        assert d.effective_route == "inspect"
tests/test_executor_contracts.py:501:        assert d.effective_route == "reorganise"
tests/test_executor_contracts.py:627:            "prompt_tokens": "unknown",
tests/test_executor_contracts.py:1095:    def test_system_prompt_biases_ambiguous_edits_to_clarify(self) -> None:
tests/test_executor_contracts.py:1101:    def test_system_prompt_never_clarifies_when_node_is_named(self) -> None:
tests/test_executor_contracts.py:1111:    def test_system_prompt_no_longer_advertises_set_title_edit_op(self) -> None:
tests/test_executor_contracts.py:1119:    def test_system_prompt_pins_outside_patterns_to_adapt_and_local_edits_elsewhere(self) -> None:
tests/test_executor_contracts.py:1142:    def test_implement_prompt_acts_on_graph_local_evidence_when_research_fails(self) -> None:
tests/test_executor_contracts.py:1239:    def test_research_implementation_prompt_requests_concise_rationale(self) -> None:
tests/test_executor_contracts.py:1251:    def test_reply_prompt_uses_plain_prose_with_json_compat(self) -> None:
tests/test_executor_contracts.py:1261:    def test_inspect_reply_prompt_encourages_readable_structure(self) -> None:
tests/test_executor_contracts.py:1374:    def test_reply_prompt_requires_traced_link_citations_for_connectivity(self) -> None:
tests/test_executor_contracts.py:1393:    def test_reply_prompt_requires_exact_widget_key_value_citations(self) -> None:
tests/test_executor_contracts.py:1408:    def test_reply_prompt_forbids_unknowable_refusals_with_ir_evidence(self) -> None:
tests/test_executor_contracts.py:1422:    def test_reply_prompt_handles_zero_on_topic_research_evidence(self) -> None:
tests/test_executor_contracts.py:1503:        assert d.effective_route == "research"
tests/test_executor_contracts.py:1562:        assert d.effective_route == "revise"
tests/test_executor_contracts.py:1610:        assert d.effective_route == "revise"
tests/test_executor_contracts.py:1627:        assert d.effective_route == "clarify"
tests/test_executor_contracts.py:1644:        assert d.effective_route == "inspect"
tests/test_executor_contracts.py:1665:        # effective_route uses explicit route
tests/test_executor_contracts.py:1666:        assert d.effective_route == "adapt"
tests/test_executor_contracts.py:1698:        assert decision.effective_route == "adapt"
tests/test_executor_contracts.py:1707:            ("set the prompt to a neon city", "revise", False, True, "edit_graph", "revise"),
tests/test_executor_contracts.py:1734:        assert decision.effective_route == expected_route
tests/test_executor_contracts.py:1735:        assert decision.effective_route != "adapt"
tests/test_executor_contracts.py:1752:        assert d.effective_route == "clarify"
tests/test_executor_contracts.py:1769:        assert d.effective_route == "revise"
tests/test_executor_contracts.py:2023:        assert parsed.effective_route == "revise"
tests/test_executor_classify_only.py:43:    assert result.report.plan.effective_route == "adapt"
tests/test_executor_classify_only.py:69:    assert result.report.plan.effective_route == "adapt"
tests/test_executor_lookup_tools.py:218:def test_registry_lookup_budget_is_one_per_stage() -> None:
tests/test_executor_lookup_tools.py:219:    budget = RegistryLookupBudget()
tests/test_executor_lookup_tools.py:226:    first = registry_lookup("SomeNodeKJ", resolver=resolver, budget=budget)
tests/test_executor_lookup_tools.py:227:    second = registry_lookup("SomeNodeKJ", resolver=resolver, budget=budget)
tests/test_executor_lookup_tools.py:231:    assert second.diagnostics[0].code == "registry_budget_exhausted"
tests/test_executor_lookup_tools.py:236:def test_registry_lookup_budget_defaults_to_one() -> None:
tests/test_executor_lookup_tools.py:238:    budget = RegistryLookupBudget()
tests/test_executor_lookup_tools.py:239:    assert budget.consume() is True
tests/test_executor_lookup_tools.py:240:    assert budget.consume() is False
tests/test_executor_lookup_tools.py:241:    assert budget.exhausted is True
tests/test_executor_lookup_tools.py:276:            warnings=("registry sub-budget exceeded during ComfyUI-Manager lookup; partial evidence.",),
tests/test_executor_layout_hints.py:17:from vibecomfy.executor import prompts as executor_prompts
tests/test_executor_layout_hints.py:516:        executor_prompts.build_classify_messages(
tests/test_executor_layout_hints.py:548:        "from vibecomfy.executor import prompts\n"
tests/test_executor_flows.py:48:from vibecomfy.executor.prompts import build_classify_messages
tests/test_executor_flows.py:584:    return "This workflow loads a checkpoint, encodes prompts, samples a latent, decodes it, and saves the image."
tests/test_executor_flows.py:815:        assert result.report.plan.effective_route == "research"
tests/test_executor_flows.py:843:            query="compare Gemini and Claude for prompt splitting",
tests/test_executor_flows.py:852:        assert result.report.plan.effective_route == "research"
tests/test_executor_flows.py:859:    def test_answer_only_reply_prompt_carries_explicit_note(self) -> None:
tests/test_executor_flows.py:861:        from vibecomfy.executor.prompts import build_reply_messages
tests/test_executor_flows.py:1067:        assert result.report.plan.effective_route == "revise"
tests/test_executor_flows.py:1073:        classify_prompt = classify_kwargs["messages"][1]["content"]
tests/test_executor_flows.py:1074:        assert "Prior clarification question:" in classify_prompt
tests/test_executor_flows.py:1075:        assert "Load external audio or keep the current text-to-audio setup?" in classify_prompt
tests/test_executor_flows.py:1433:        assert result.report.plan.effective_route == "inspect"
tests/test_executor_flows.py:1696:                "prompt_tokens": 4,
tests/test_executor_flows.py:2458:    Emulates a model that follows the reply prompt: if the prompt still
tests/test_executor_flows.py:2466:    prompt_text = "\n".join(
tests/test_executor_flows.py:2469:    if "return this bounded content" in prompt_text:
tests/test_executor_flows.py:2471:    if "synthesis produced no conclusion" in prompt_text:
tests/test_executor_flows.py:2621:def test_research_reply_prompt_has_no_c5_return_instruction() -> None:
tests/test_executor_flows.py:2622:    """Batch 14: the research reply prompt no longer tells the model to RELAY
tests/test_executor_flows.py:2625:    from vibecomfy.executor.prompts import build_reply_messages
tests/test_executor_flows.py:2648:        effective_route="research",
tests/test_executor_flows.py:2653:    # The C5-return relay contract is deleted from the reply prompt.
tests/test_executor_flows.py:2711:    assert inspect_result.report.plan.effective_route == "inspect"
tests/test_executor_flows.py:2732:    assert respond_result.report.plan.effective_route == "respond"
tests/test_executor_flows.py:2891:        assert result.report.plan.effective_route == "respond"
tests/test_executor_flows.py:2949:        assert result.report.plan.effective_route == "revise"
tests/test_executor_flows.py:3034:        assert result.report.plan.effective_route == "inspect"
tests/test_executor_flows.py:3088:        assert result.report.plan.effective_route == "clarify"
tests/test_executor_flows.py:3147:        assert result.report.plan.effective_route == "adapt"
tests/test_executor_flows.py:4151:    def test_classifier_prompt_owns_former_preclassify_judgment(self) -> None:
tests/test_executor_flows.py:4172:    def test_classifier_prompt_preserves_user_named_external_technologies(self) -> None:
tests/test_executor_flows.py:4221:    def test_prompt_memory_includes_last_five_durable_messages_in_order(
tests/test_executor_flows.py:4226:        """Seed session with >5 durable chat messages, verify executor prompt
tests/test_executor_flows.py:4230:        inspects the backend-built prompt/context directly through
tests/test_executor_flows.py:4234:        from vibecomfy.executor.prompts import build_classify_messages
tests/test_executor_flows.py:4236:        session_id = "prompt-memory-test"
tests/test_executor_flows.py:4300:        # ── verify the classifier prompt includes the messages ──────────
tests/test_executor_flows.py:4314:            f"Current query {current_query!r} not found in classify prompt"
tests/test_executor_flows.py:4322:                f"Expected recent message {expected!r} not found in classify prompt"
tests/test_executor_flows.py:4326:                f"previous message in classify prompt"
tests/test_executor_flows.py:4366:        assert result.report.plan.effective_route == expected_route
tests/test_executor_flows.py:4409:    def test_current_graph_prompt_change_routes_to_revise(
tests/test_executor_flows.py:4429:            query="change the positive prompt to 'a red rose'",
tests/test_executor_flows.py:4505:        assert result.report.plan.effective_route == "research"
tests/test_executor_flows.py:5130:# ── Batch 12 (Law 4): stage lens wiring + reply-prompt goldens ──────────────
tests/test_executor_flows.py:5242:    """Reply-prompt golden: the reply's graph context is the composable
tests/test_executor_flows.py:5257:    # The reply prompt embeds the renderer output verbatim behind the
tests/test_executor_flows.py:5259:    from vibecomfy.executor.prompts import build_reply_messages
tests/fixtures/payload_contracts/agent_executor_clarify_response.json
tests/fixtures/payload_contracts/agent_executor_failure_response.json
tests/fixtures/payload_contracts/agent_executor_request.json
tests/fixtures/payload_contracts/agent_executor_success_response.json
tests/fixtures/payload_contracts/websocket_executor_phase_classify.json
tests/fixtures/payload_contracts/websocket_executor_phase_implement.json
tests/fixtures/payload_contracts/websocket_executor_phase_reply.json
tests/fixtures/payload_contracts/websocket_executor_phase_research.json
tests/test_agent_executor_durable.py
tests/test_agent_executor_response.py
tests/test_agent_executor_routes.py
tests/test_executor_classify_only.py
tests/test_executor_contracts.py
tests/test_executor_edit_suggestion_tools.py
tests/test_executor_flows.py
tests/test_executor_hivemind_messages.py
tests/test_executor_hivemind_tools.py
tests/test_executor_layout_hints.py
tests/test_executor_lookup_tools.py
tests/test_executor_profiles.py
tests/test_executor_stage_contracts.py
tests/test_executor_web_tools.py
tests/test_ir_boundary_kpi.py
tests/test_ir_laws.py
tests/test_porting_edit_apply.py
tests/test_porting_edit_apply_values.py
tests/test_porting_edit_corpus.py
tests/test_porting_edit_delta_contract.py
tests/test_porting_edit_lint.py
tests/test_porting_edit_ops.py
tests/test_porting_edit_resolve.py
tests/test_porting_edit_session.py
tests/test_porting_edit_session_harness.py

exec
/bin/zsh -lc "sed -n '1,280p' tests/test_executor_profiles.py
sed -n '1,260p' tests/test_ir_laws.py
sed -n '1,220p' tests/test_executor_classify_only.py
sed -n '1,220p' tests/test_agent_runtime_adapter.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
"""Unit tests for profile loading and resolution.

Exercises ``vibecomfy/executor/profiles.py``: profile TOML parsing, stage
validation, agent validation, effort normalization, test path override,
and the four canonical profiles (``default``, ``openai``, ``anthropic``,
``opensource``).
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from typing import Generator

import pytest

from vibecomfy.executor.profiles import (
    DECLARED_STAGES,
    AgentSpecShape,
    load_all_profiles,
    load_profile,
    set_profile_override_dir,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_toml(dir_path: Path, name: str, content: str) -> Path:
    """Write a TOML profile file into *dir_path* and return its path."""
    file_path = dir_path / f"{name}.toml"
    file_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return file_path


_BASE_PROFILE = """
[classify]
agent = "hermes"
model = "openrouter:deepseek/deepseek-v4-flash"
effort = "low"

[research]
agent = "hermes"
model = "openrouter:deepseek/deepseek-v4-pro"
effort = "medium"

[implement]
agent = "codex"
model = "gpt-5.4"
effort = "high"

[reply]
agent = "hermes"
model = "openrouter:deepseek/deepseek-v4-pro"
effort = "low"
"""


@pytest.fixture
def profile_dir() -> Generator[Path, None, None]:
    """Temporary directory populated with the four canonical profiles."""
    with tempfile.TemporaryDirectory() as tmp:
        dir_path = Path(tmp)
        _write_toml(dir_path, "default", _BASE_PROFILE)
        _write_toml(dir_path, "openai", _BASE_PROFILE.replace('"codex"', '"codex"').replace('"gpt-5.4"', '"gpt-5.5"'))
        _write_toml(dir_path, "anthropic", _BASE_PROFILE.replace('"codex"', '"claude"').replace('"gpt-5.4"', '"claude-sonnet-4-5"'))
        _write_toml(dir_path, "opensource", _BASE_PROFILE.replace('"codex"', '"shannon"').replace('"gpt-5.4"', '"openrouter/hermes-3-70b"'))
        set_profile_override_dir(dir_path)
        yield dir_path
        set_profile_override_dir(None)


def _stage_names(profile: dict[str, AgentSpecShape]) -> set[str]:
    return set(profile.keys())


# ── canonical stages ─────────────────────────────────────────────────────────


def test_declared_stages_are_exactly_the_four_phases() -> None:
    """The module-level constant must contain exactly our four phases."""
    assert DECLARED_STAGES == {"classify", "research", "implement", "reply"}


# ── AgentSpecShape ───────────────────────────────────────────────────────────


def test_agent_spec_shape_defaults() -> None:
    spec = AgentSpecShape(agent="hermes", model="deepseek-v4")
    assert spec.agent == "hermes"
    assert spec.model == "deepseek-v4"
    assert spec.effort == "low"


def test_agent_spec_shape_explicit_effort() -> None:
    spec = AgentSpecShape(agent="codex", model="gpt-5.4", effort="high")
    assert spec.effort == "high"


def test_agent_spec_shape_invalid_effort_clamps_to_low() -> None:
    spec = AgentSpecShape(agent="hermes", model="d", effort="extreme")
    assert spec.effort == "low"


# ── profile loading (happy path) ─────────────────────────────────────────────


class TestLoadProfile:
    """Tests for ``load_profile()`` with valid fixture profiles."""

    def test_load_default_profile(self, profile_dir: Path) -> None:
        profile = load_profile("default")
        assert _stage_names(profile) == DECLARED_STAGES

        classify = profile["classify"]
        assert classify.agent == "hermes"
        assert classify.model == "openrouter:deepseek/deepseek-v4-flash"
        assert classify.effort == "low"

        research = profile["research"]
        assert research.agent == "hermes"
        assert research.model == "openrouter:deepseek/deepseek-v4-pro"
        assert research.effort == "medium"

        implement = profile["implement"]
        assert implement.agent == "codex"
        assert implement.model == "gpt-5.4"
        assert implement.effort == "high"

        reply = profile["reply"]
        assert reply.agent == "hermes"
        assert reply.model == "openrouter:deepseek/deepseek-v4-pro"
        assert reply.effort == "low"

    def test_load_openai_profile(self, profile_dir: Path) -> None:
        profile = load_profile("openai")
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "codex"
        assert profile["implement"].model == "gpt-5.5"

    def test_load_anthropic_profile(self, profile_dir: Path) -> None:
        profile = load_profile("anthropic")
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "claude"
        assert profile["implement"].model == "claude-sonnet-4-5"

    def test_load_opensource_profile(self, profile_dir: Path) -> None:
        profile = load_profile("opensource")
        assert profile["classify"].agent == "hermes"
        assert profile["implement"].agent == "shannon"
        assert profile["implement"].model == "openrouter/hermes-3-70b"


def test_packaged_openai_profile_uses_luna_adjudicator_and_sol_workers() -> None:
    """Guard the shipped profile, not the synthetic profile fixture above."""
    set_profile_override_dir(None)
    profile = load_profile("openai")

    assert profile["classify"] == AgentSpecShape(
        agent="codex", model="gpt-5.6-luna", effort="medium"
    )
    for stage in ("research", "implement", "reply"):
        assert profile[stage] == AgentSpecShape(
            agent="codex", model="gpt-5.6-sol", effort="medium"
        )


def test_packaged_openrouter_profile_preserves_explicit_provider_route() -> None:
    set_profile_override_dir(None)
    profile = load_profile("openrouter")

    assert profile["classify"] == AgentSpecShape(
        agent="openrouter",
        model="openrouter:deepseek/deepseek-v4-flash",
        effort="low",
    )
    assert profile["implement"] == AgentSpecShape(
        agent="openrouter",
        model="openrouter:deepseek/deepseek-v4-pro",
        effort="low",
    )

    def test_all_profiles_have_exactly_four_stages(self, profile_dir: Path) -> None:
        for name in ("default", "openai", "anthropic", "opensource"):
            profile = load_profile(name)
            assert _stage_names(profile) == DECLARED_STAGES, f"{name} has {_stage_names(profile)}"

    def test_all_profiles_have_valid_effort_values(self, profile_dir: Path) -> None:
        for name in ("default", "openai", "anthropic", "opensource"):
            profile = load_profile(name)
            for stage, spec in profile.items():
                assert spec.effort in ("low", "medium", "high"), (
                    f"{name}/{stage} effort={spec.effort!r}"
                )


# ── load_all_profiles ────────────────────────────────────────────────────────


class TestLoadAllProfiles:
    """Tests for ``load_all_profiles()``."""

    def test_loads_all_four_canonical_profiles(self, profile_dir: Path) -> None:
        all_profiles = load_all_profiles()
        assert set(all_profiles.keys()) == {"default", "openai", "anthropic", "opensource"}

    def test_every_profile_maps_all_stages(self, profile_dir: Path) -> None:
        all_profiles = load_all_profiles()
        for name, profile in all_profiles.items():
            assert _stage_names(profile) == DECLARED_STAGES, (
                f"{name} missing stages: {DECLARED_STAGES - _stage_names(profile)}"
            )


# ── validation (error paths) ─────────────────────────────────────────────────


class TestValidationErrors:
    """Tests for profile validation error paths."""

    def test_missing_stage_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_missing",
            """
            [classify]
            agent = "hermes"
            model = "d"
            [research]
            agent = "hermes"
            model = "d"
            [implement]
            agent = "hermes"
            model = "d"
            # reply missing
            """,
        )
        with pytest.raises(ValueError, match="missing required stages"):
            load_profile("bad_missing")

    def test_extra_stage_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_extra",
            _BASE_PROFILE
            + """
            [extra_stage]
            agent = "hermes"
            model = "d"
            """,
        )
        with pytest.raises(ValueError, match="unknown stages"):
            load_profile("bad_extra")

    def test_unknown_agent_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_agent",
            _BASE_PROFILE.replace('"hermes"', '"gpt-5-robot"'),
        )
        with pytest.raises(ValueError, match="not a known agent"):
            load_profile("bad_agent")

    def test_missing_model_field_raises(self, profile_dir: Path) -> None:
        _write_toml(
            profile_dir,
            "bad_no_model",
            """
            [classify]
            agent = "hermes"

            [research]
            agent = "hermes"
            model = "d"

            [implement]
            agent = "hermes"
            model = "d"

"""Executable laws for the VibeWorkflow IR-everywhere migration.

The law owners intentionally remain ``xfail(strict=False)`` until their named
batches land.  Passing tests in this module freeze the quotient, spike corpus,
and provisional failure ledger so later batches cannot weaken the contracts.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.ingest.normalize import from_envelope, from_ui
from vibecomfy.intent._ledger import (
    CLASS_D_HARD_FLOOR_IDS,
    EXIT_FAILURE_LEDGER,
    FailureLedgerRow,
    LEDGER_ID_COUNT,
    LEDGER_UNRECOVERABLE_COUNT,
    _EXIT_STATUSES,
    assert_ledger_integrity,
    ledger_scenario_ids,
)
from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import get_schema_provider, schema_for
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeInput, VibeNode, VibeWorkflow, WorkflowSource, mode_to_litegraph


REPO_ROOT = Path(__file__).parents[1]
SPIKE_CORPUS = (
    (
        "vibe_envelope",
        REPO_ROOT / "tests/fixtures/b02_corpus_mini/90a1d5ff9044902e.json",
        "3f7fe8c665328f4ffa8db8f851da2081f288c9e2d107fd697c89de8655cf5f63",
    ),
    (
        "raw_ui_definitions",
        REPO_ROOT / "tests/fixtures/agent_edit/subgraphed_wan_i2v.json",
        "063620c1a3828ce7a065c852ffcc50d238b15e25ebdbaef40f72d4fe36405236",
    ),
    (
        "raw_ui_unknown_schema",
        REPO_ROOT
        / "ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json",
        "16f5c40d768c2ce719add73e74317ff17f2f2c59f987b031fa295f48f27d0f0f",
    ),
)

# One ledger: vibecomfy.intent._ledger (re-exported from intent._fixture).
PROVISIONAL_FAILURE_LEDGER = EXIT_FAILURE_LEDGER

_UID_COMMENT = re.compile(r"\buid:([^\s]+)")
_PROVISIONAL_SCHEMA_SOURCES = frozenset(
    {"comfy_registry_provisional", "workflow_json_provisional"}
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Canonical bytes used by the door law (order retained, whitespace fixed).

    Non-finite floats (NaN/Infinity) are serialized deterministically (the
    JSON spec's ``NaN``/``Infinity`` tokens) rather than raising, so a fixture
    or edit that introduces them never makes the door law flaky.
    """
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _binding_by_uid(workflow: VibeWorkflow) -> dict[str, str]:
    """Read deterministic emitted bindings from the Python surface itself.

    Falls back to the emitter's own IR-derived naming when the specimen cannot
    be emitted (e.g. unresolved value helpers), so the projection stays total
    without requiring emission to succeed.
    """
    try:
        source = emit_agent_edit_python(workflow)
    except Exception:
        return _bindings_from_ir(workflow)
    lines = source.splitlines()
    bindings: dict[str, str] = {}
    for statement in ast.parse(source).body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        segment = "\n".join(lines[statement.lineno - 1 : statement.end_lineno])
        match = _UID_COMMENT.search(segment)
        if match is not None:
            bindings[match.group(1)] = target.id
    return bindings


def _bindings_from_ir(workflow: VibeWorkflow) -> dict[str, str]:
    """Derive the emitter's deterministic bindings directly from the IR.

    Mirrors ``_prepare_workflow_for_emit``'s node filter (UI-only furniture is
    stripped, virtual wires are kept, unresolvable helpers are excluded) and
    then applies the emitter's own ``_compute_variable_names``, so the names
    match what emission would assign without requiring emission to succeed.
    """
    from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES, UI_ONLY_CLASS_TYPES
    from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names
    from vibecomfy.porting.emit.emit_prepare import _VIRTUAL_WIRE_EMITTER_CLASS_TYPES

    nodes = {
        str(node_id): node
        for node_id, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES
        and not (
            node.class_type in RESOLVABLE_HELPER_CLASS_TYPES
            and node.class_type not in _VIRTUAL_WIRE_EMITTER_CLASS_TYPES
        )
    }
    edges = [
        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        for edge in workflow.edges
        if str(edge.from_node) in nodes and str(edge.to_node) in nodes
    ]
    names = _compute_variable_names(nodes, edges)
    return {
        str(node.uid): names[str(node_id)]
        for node_id, node in nodes.items()
        if node.uid is not None and str(node.uid) and str(node_id) in names
    }


def _schema_status(schema_provider: Any, class_type: str) -> str:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return "unknown"
    source = str(getattr(schema, "source_provider", "") or "")
    ignored = {str(item) for item in (getattr(schema, "ignored_evidence", ()) or ())}
    if source in _PROVISIONAL_SCHEMA_SOURCES or "not_runtime_validated" in ignored:
        return "provisional"
    return "known"


def _graph_interfaces(
    workflow: VibeWorkflow,
    binding_by_node: Mapping[str, str],
) -> tuple[Any, ...]:
    # Graph-level VibeInput/VibeOutput registrations are ingest heuristics
    # (prompt/seed/model, sink nodes).  The designed grammar does not emit
    # them, so they are door-owned and excluded from π_edit.  Subgraph
    # signatures remain: they are the Python ``def`` surface when definitions
    # are retained on the IR.
    _ = binding_by_node
    public_inputs: tuple[Any, ...] = ()
    public_outputs: tuple[Any, ...] = ()
    definitions = workflow.metadata.get("definitions")
    subgraphs: list[tuple[Any, ...]] = []
    if isinstance(definitions, Mapping):
        from vibecomfy.porting.emit.emit_subgraph import _subgraph_definitions_from_raw

        emitted_subgraphs = _subgraph_definitions_from_raw(
            {"definitions": dict(definitions)},
            source_path=None,
        )
        for subgraph in emitted_subgraphs.values():
            subgraphs.append(
                (
                    subgraph.slug,
                    tuple((port.name, port.type) for port in subgraph.inputs),
                    tuple((port.name, port.type) for port in subgraph.outputs),
                )
            )
    return public_inputs, public_outputs, tuple(sorted(subgraphs))


def pi_edit(
    workflow: VibeWorkflow,
    *,
    schema_provider: Any | None = None,
) -> tuple[Any, ...]:
    """The exact editable quotient from ``.oracle/plan.md``.

    Included: deterministic emitted binding; class and normalized mode; named
    literal fields AND positional widget values (widget_N) with their
    channel/value/schema status; named connections; grammar-visible subgraph
    interfaces when present; and the stable uid needed to resolve a binding.
    Canvas/wire furniture, raw ids, link bookkeeping, opaque UI, provenance,
    editor state, and Note/MarkdownNote furniture are absent.  Nodes without
    an emitted binding (and edges touching them) are furniture.
    """
    from vibecomfy.porting.emit.emit_prepare import _agent_edit_output_aliases

    provider = schema_provider or get_schema_provider("local")
    binding_by_uid = _binding_by_uid(workflow)
    binding_by_node = {
        str(node_id): binding_by_uid[str(node.uid)]
        for node_id, node in workflow.nodes.items()
        if str(node.uid) in binding_by_uid
    }
    nodes = []
    for node_id, node in workflow.nodes.items():
        binding = binding_by_node.get(str(node_id))
        if binding is None:
            continue
        status = _schema_status(provider, str(node.class_type))
        fields = tuple(
            sorted(
                [
                    ("input", str(name), _freeze(value), status)
                    for name, value in node.inputs.items()
                ]
                + [
                    ("widget", str(name), _freeze(value), status)
                    for name, value in node.widgets.items()
                ]
            )
        )
        nodes.append(
            (
                binding,
                str(node.uid),
                str(node.class_type),
                mode_to_litegraph(node.mode),
                fields,
            )
        )
    connections = []
    for edge in workflow.edges:
        from_binding = binding_by_node.get(str(edge.from_node))
        to_binding = binding_by_node.get(str(edge.to_node))
        if from_binding is None or to_binding is None:
            continue
        from_output = str(edge.from_output)
        if from_output.isdigit():
            from_output = _agent_edit_output_aliases(
                workflow.nodes[str(edge.from_node)]
            ).get(int(from_output), from_output)
            if from_output.isdigit():
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
from vibecomfy.executor.core import run_executor


def test_classify_only_skips_research_implement_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ClassifyDecision.edit(route="adapt", plan_summary="test summary")
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )
    reply_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_reply",
        lambda *args, **kwargs: reply_calls.append(args) or "should not run",
    )
    research_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_research",
        lambda *args, **kwargs: research_calls.append(args) or None,
    )
    implement_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_implement",
        lambda *args, **kwargs: implement_calls.append(args) or None,
    )

    request = ExecutorRequest(query="add a brightness node")
    result = run_executor(request, classify_only=True)

    assert result.ok is True
    assert result.reply is not None
    assert "dry-run" in result.reply
    assert "adapt" in result.reply
    assert result.report.plan.effective_route == "adapt"
    assert result.graph is None
    assert not research_calls
    assert not implement_calls
    assert not reply_calls


def test_classify_only_does_not_resolve_post_classify_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ClassifyDecision.edit(route="adapt", plan_summary="test summary")

    def _resolve_spec(_profile: str | None, stage: str) -> object:
        if stage != "classify":
            raise AssertionError(f"unexpected {stage} spec resolution")
        return SimpleNamespace(agent="test", model="test-model", effort="high")

    monkeypatch.setattr("vibecomfy.executor.core._resolve_spec", _resolve_spec)
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )

    result = run_executor(ExecutorRequest(query="add a brightness node"), classify_only=True)

    assert result.ok is True
    assert result.report.plan.effective_route == "adapt"


def test_classify_only_failure_captured_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor.core import _ExecutorPhaseError

    def _raise(*args, **kwargs):
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind="model_error",
            message="model refused",
        )

    monkeypatch.setattr("vibecomfy.executor.core._run_classify", _raise)

    request = ExecutorRequest(query="do something")
    result = run_executor(request, classify_only=True)

    assert result.ok is False
    assert result.failure_stage == "classify"
    assert "model refused" in (result.failure_message or "")


def test_full_run_does_not_skip_phases_when_classify_only_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ClassifyDecision.respond_only(route="respond")
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )
    reply_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_reply",
        lambda *args, **kwargs: reply_calls.append(args) or "reply text",
    )

    request = ExecutorRequest(query="hello")
    result = run_executor(request, classify_only=False)

    assert result.ok is True
    assert result.reply == "reply text"
    assert len(reply_calls) == 1
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest

from vibecomfy.comfy_nodes.agent import runtime
from vibecomfy.comfy_nodes.agent import provider as agent_provider
from vibecomfy.comfy_nodes.agent import worker
from vibecomfy.executor.agent_backend import run_classify_turn, run_reply_turn


def test_turn_timeout_raises_for_large_serialized_graphs() -> None:
    small = runtime._turn_timeout_seconds("tiny", stage="classify")
    large = runtime._turn_timeout_seconds("x" * 60_000, stage="reply")
    implement = runtime._turn_timeout_seconds("tiny", stage="implement")
    batch = runtime._turn_timeout_seconds("tiny", stage="batch")
    assert small == runtime._TURN_TIMEOUT_SECONDS
    assert large == min(
        max(runtime._TURN_TIMEOUT_SECONDS, runtime._LARGE_GRAPH_TURN_TIMEOUT_SECONDS),
        runtime._TURN_TIMEOUT_HARD_CAP_SECONDS,
    )
    assert implement == large
    assert batch == large
    assert large >= 480


def test_openrouter_agent_kwargs_use_openrouter_model_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes",
        route="openrouter",
        model="openrouter:deepseek/deepseek-v4-pro",
    )

    assert kwargs["provider"] == "openrouter"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["model"] == "deepseek/deepseek-v4-pro"
    assert kwargs["max_tokens"] == 4096
    # Cluster B: bounded, configurable per-turn iteration budget (default 2).
    assert kwargs["max_iterations"] == 2


def test_explicit_openrouter_route_cannot_be_hijacked_by_generic_endpoint_or_key_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("VIBECOMFY_HERMES_API_KEY", "generic-provider-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "native-deepseek-key")
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-v1-openrouter-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes",
        route="openrouter",
        model="openrouter:deepseek/deepseek-v4-pro",
    )

    assert kwargs["provider"] == "openrouter"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["api_key"] == "sk-or-v1-openrouter-key"
    assert kwargs["model"] == "deepseek/deepseek-v4-pro"


def test_provider_preserves_openrouter_route_at_runtime_boundary() -> None:
    descriptor = agent_provider._resolve_agent_route("openrouter")
    assert agent_provider._runtime_dispatch_route(
        descriptor, descriptor.normalized_route
    ) == "openrouter"


def test_unsupported_route_plumbs_unknown_provenance_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = agent_provider._resolve_agent_route("unsupported-route")
    assert descriptor.requested_route == "unsupported-route"
    assert descriptor.normalized_route == "unknown"
    assert agent_provider._runtime_dispatch_route(descriptor, descriptor.normalized_route) == "unknown"
    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: runtime)

    with pytest.raises(ImportError) as raised:
        agent_provider.run_model_turn(
            "test unsupported route",
            [{"role": "user", "content": "test unsupported route"}],
            route="unsupported-route",
            model="agent-edit",
            response_contract="text",
            profiling_context={"backend_phase": "classify"},
        )

    worker_result = raised.value.worker_result  # type: ignore[attr-defined]
    attempt = worker_result["model_attempts"][0]
    assert attempt["requested_model"] == "agent-edit"
    assert attempt["resolved_model"] == "unknown"
    assert attempt["adapter"] == "unknown"
    assert attempt["provider"] == "unknown"
    assert attempt["transport"] == "unknown"
    assert attempt["endpoint"] == "unknown"
    readiness = runtime.readiness(route="unsupported-route", model="agent-edit")
    assert readiness["route"] == "unknown"
    assert readiness["model"] == "unknown"


def test_agent_edit_contract_model_uses_openrouter_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    kwargs = runtime._build_agent_kwargs(
        "hermes",
        route="openrouter",
        model="agent-edit",
    )

    assert kwargs["provider"] == "openrouter"
    assert kwargs["model"] == "deepseek/deepseek-v4-pro"


def test_openrouter_readiness_does_not_report_contract_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    readiness = runtime.readiness(route="openrouter", model="agent-edit")

    assert readiness["ready"] is True
    assert readiness["route"] == "openrouter"
    assert readiness["model"] == "deepseek/deepseek-v4-pro"


def test_hermes_route_readiness_maps_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "test-key")

    readiness = runtime.readiness(route="hermes", model="agent-edit")

    assert readiness["ready"] is True
    assert readiness["route"] == "openrouter"
    assert readiness["model"] == "deepseek/deepseek-v4-pro"


def test_normalize_route_maps_hermes_to_openrouter() -> None:
    assert runtime._normalize_route("hermes") == "openrouter"
    assert runtime._requested_route("hermes") == "openrouter"


def test_provider_status_preserves_runtime_model_over_contract_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Runtime:
        @staticmethod
        def readiness(*, route: str, model: str | None = None) -> dict[str, object]:
            assert model == "agent-edit"
            return {
                "ready": True,
                "route": "openrouter",
                "model": "deepseek/deepseek-v4-pro",
                "reason": "ready",
            }

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)
    monkeypatch.setattr(agent_provider, "_openrouter_key_present", lambda: True)

    status = agent_provider.readiness(route="auto")

    assert status["ready"] is True
    assert status["route"] == "openrouter"
    assert status["model"] == "deepseek/deepseek-v4-pro"


def test_resolve_openrouter_key_prefers_openrouter_shaped_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_2", raising=False)
    monkeypatch.setattr(
        runtime,
        "_read_env_file_entries",
        lambda path=runtime._HERMES_ENV_PATH: [
            ("OPENROUTER_API_KEY", "sk-or-v1-valid-openrouter-key"),
            ("OPENROUTER_API_KEY", "sk-stale-direct-key"),
        ],
    )

    assert runtime._resolve_openrouter_key() == "sk-or-v1-valid-openrouter-key"


def test_run_worker_mirrors_openrouter_key_into_backend_env_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "_resolve_openrouter_key", lambda: "sk-or-v1-test-key")
    captured_env: dict[str, str] = {}

    def fake_subprocess(command, **kwargs):
        captured_env.update(kwargs["env"])
        with open(command[3], "w", encoding="utf-8") as fh:
            json.dump({"content": "hello"}, fh)
        return (0, "", "")

    monkeypatch.setattr(runtime, "_run_worker_subprocess", fake_subprocess)

    result = runtime._run_worker(
        {"api_key": "sk-or-v1-test-key"},
        "system",
        "user",
        response_contract="batch_repl",
        agent_id="hermes",
    )

    assert result["content"] == "hello"
    assert captured_env["OPENROUTER_API_KEY"] == "sk-or-v1-test-key"
    assert captured_env["OPENAI_API_KEY"] == "sk-or-v1-test-key"
    assert captured_env["HERMES_API_KEY"] == "sk-or-v1-test-key"


exec
/bin/zsh -lc "sed -n '540,590p' vibecomfy/comfy_nodes/agent/runtime.py
sed -n '1360,1455p' vibecomfy/comfy_nodes/agent/runtime.py
rg -n \"def _run_worker|agent_kwargs|session\" vibecomfy/comfy_nodes/agent/runtime.py | sed -n '1,180p'
rg -n \"messages_path|session_dir_for|write.*chat|read_session_chat|append.*chat\" vibecomfy/comfy_nodes/agent/session.py vibecomfy/comfy_nodes/agent/_frag_chat.py vibecomfy/comfy_nodes/agent/_frag_entrypoint.py | sed -n '1,260p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
    # _resolve_openrouter_key() force-prefers any sk-or-* entry it finds there.
    if _is_native_deepseek_endpoint() and os.getenv("DEEPSEEK_API_KEY"):
        return os.getenv("DEEPSEEK_API_KEY")
    return _resolve_openrouter_key()


def _has_arnold_credential() -> bool:
    return bool(
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_TOKEN")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        or Path("~/.claude/.credentials.json").expanduser().exists()
        or Path("~/.hermes/.anthropic_oauth.json").expanduser().exists()
    )


def _split_messages(messages: Sequence[Mapping[str, Any]] | None) -> tuple[str | None, str | None]:
    """Return (system_message, user_message) from VibeComfy's built messages."""
    system_msg: str | None = None
    user_msg: str | None = None
    for entry in messages or []:
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        if role == "system" and system_msg is None:
            system_msg = content
        elif role == "user":
            user_msg = content
    return system_msg, user_msg


def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | None = None) -> dict[str, Any]:
    """AIAgent constructor kwargs for a single, tool-free completion.

    Keyed off the resolved *dispatch agent id* (not the panel route). ``hermes``
    is always configured for OpenRouter, including the legacy ``deepseek`` route
    alias. For ``codex`` / ``claude`` the worker dispatches through the default
    dispatcher and ignores ``agent_kwargs``, so we pass only the tool-free
    single-shot flags.
    """
    common: dict[str, Any] = dict(
        max_iterations=_AGENT_MAX_ITERATIONS,
        enabled_toolsets=[],          # no tools: one-shot completion
        save_trajectories=False,      # no trajectory files on disk
        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
        skip_memory=True,             # don't load/write the memory store
        quiet_mode=True,
    )
    if agent_id == "hermes":
                    f"claude CLI {'on PATH' if have_claude else 'not on PATH'}, "
                    f"bun {'on PATH' if have_bun else 'not on PATH'}."
                )
            ),
        }

    # Bare/legacy ``arnold`` (or anything else) with no OpenRouter key: fall through
    # to the best available registered+ready backend (prefer OpenRouter). For
    # ``auto`` with no OpenRouter key, that is whatever else is wired; today only
    # hermes is guaranteed, so report not-ready honestly.
    if requested in {"", "auto", "arnold"}:
        if _adapter_registered("hermes") and _resolve_openrouter_key():
            key = _resolve_openrouter_key()
            return {
                "ready": True,
                "backend": backend,
                "route": "openrouter",
                "model": _default_model_for_route("openrouter", model),
                "base_url": _OPENROUTER_BASE_URL,
                "openrouter_key_present": bool(key),
                "reason": "OpenRouter key resolved; ready to run agent-edit turns.",
            }
    return {
        "ready": False,
        "backend": backend,
        "route": (
            "unknown"
            if requested and _normalize_route(requested) == "unknown"
            else requested or "arnold"
        ),
        "model": _default_model_for_route(_normalize_route(route), model),
        "reason": (
            "No agent adapter is wired for this route yet; only the openrouter "
            "route reaches a registered backend."
        ),
    }


def get_agent_status(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Compatibility wrapper around readiness().

    Prefer readiness(); this legacy shape remains for callers that still expect
    status-like fields.
    """
    payload = readiness(route=route, model=model)
    ready = bool(payload.get("ready"))
    return {
        **payload,
        "ok": ready,
        "detail": str(payload.get("reason") or ""),
        "readiness": "ready" if ready else "unavailable",
    }




def run_model_turn(
    *,
    task: str,
    messages: Sequence[Mapping[str, Any]] | None = None,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    response_contract: str = "json",
    profiling_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a generic model turn through the Arnold dispatch seam.

    Unlike ``run_agent_turn`` (which hardcodes ``response_contract="python"``
    and the python/message contract) or ``run_agent_turn_batch`` (which
    hardcodes ``response_contract="batch_repl"``), this entry point accepts
    an arbitrary *response_contract* so the executor can request ``"json"``
    or ``"text"`` responses.

    Returns the worker result dict directly.  For ``"json"`` contracts the
    dict contains ``{"content": <raw_text>, "json": <parsed_dict>}``; for
    ``"text"`` it contains ``{"content": <raw_text>}``.
    """
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = f"User request:\n{task}"
    effective_profile = {
        "model_turn_id": (
            str(profiling_context.get("model_turn_id"))
            if isinstance(profiling_context, Mapping) and profiling_context.get("model_turn_id")
            else new_profile_id("model")
        ),
        "route": route,
        "model": model,
        "response_contract": response_contract,
        **(dict(profiling_context or {})),
    }

    with profiler_span(
        LOGGER,
573:def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | None = None) -> dict[str, Any]:
579:    dispatcher and ignores ``agent_kwargs``, so we pass only the tool-free
627:    *, agent_id: str, agent_kwargs: Mapping[str, Any]
629:    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
643:    agent_kwargs: Mapping[str, Any],
651:        agent_id=agent_id, agent_kwargs=agent_kwargs
659:        resolved_model=resolved_model or agent_kwargs.get("model"),
715:    The worker is spawned with ``start_new_session=True``, so it is a session
744:def _run_worker_subprocess(
770:            start_new_session=True,
788:def _run_worker(
789:    agent_kwargs: dict[str, Any],
814:                agent_kwargs,
826:                agent_kwargs=agent_kwargs,
892:def _run_worker_once(
893:    agent_kwargs: dict[str, Any],
922:                    "agent_kwargs": agent_kwargs,
934:        hermes_key = agent_kwargs.get("api_key") or _resolve_openrouter_key()
1043:    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
1045:        agent_kwargs,
1087:    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
1089:        agent_kwargs,
1125:    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
1127:        agent_kwargs,
1471:        agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
1473:            agent_kwargs,
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:59:    from vibecomfy.comfy_nodes.agent.edit import (AgentEditState, FailureKind, PROMPT_MEMORY_MESSAGES, StageResult, _SESSION_ROOT, _StageBlocked, _agent_edit_contract, _build_batch_repl_response, _canonical_agent_edit_route, _conversation_with_candidate_reference, _default_runtime_schema_provider, _failure_response, _hydrate_execution_plan_from_protocol_notes, _product_failure_response, _record, _run_batch_repl_product_path, _safe_session_id, _stage_audit, _validated_agent_edit_response, _write_turn_chat_artifact, _write_unknown_transition_audits, allocate_turn, classify_failure, failure_envelope, initialize_gates, read_session_chat, record_idempotent_response, write_allocation_failure_audit)  # T-039 late import: host namespace lookup; resolved at call time
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:233:        messages_path=turn_dir / "messages.jsonl",
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:311:        _write_turn_chat_artifact(state, context, response, contract)
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:340:            chat = read_session_chat(root, session_id, max_messages=PROMPT_MEMORY_MESSAGES)
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:379:        _write_turn_chat_artifact(state, context, response, contract)
vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:457:    _write_turn_chat_artifact(state, context, response, contract)
vibecomfy/comfy_nodes/agent/session.py:315:        # that sanitise once and look up later (e.g. read_session_chat).
vibecomfy/comfy_nodes/agent/session.py:324:    This is the authoritative entry-point used by ``session_dir_for`` and
vibecomfy/comfy_nodes/agent/session.py:331:def session_dir_for(root: Path, session_id: str) -> Path:
vibecomfy/comfy_nodes/agent/session.py:1996:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:2252:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:2725:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:3012:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:3602:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:4132:            session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:4166:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:4233:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:4378:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:4563:        state = read_state(session_dir_for(session_root, session_id))
vibecomfy/comfy_nodes/agent/session.py:4639:    session_dir = session_dir_for(session_root, session_id)
vibecomfy/comfy_nodes/agent/session.py:4849:    "session_dir_for",
vibecomfy/comfy_nodes/agent/_frag_chat.py:16:from vibecomfy.comfy_nodes.agent.session import REVIEWABLE_CANDIDATE_STATES, _transaction_receipts_for_turn, load_candidate_transaction_with_migration, project_transaction_state, read_state, session_dir_for
vibecomfy/comfy_nodes/agent/_frag_chat.py:28:def _write_turn_chat_artifact(
vibecomfy/comfy_nodes/agent/_frag_chat.py:34:    """Best-effort write of ``chat.json`` for an allocated, completed edit turn.
vibecomfy/comfy_nodes/agent/_frag_chat.py:631:def read_session_chat(
vibecomfy/comfy_nodes/agent/_frag_chat.py:649:    session_dir = session_dir_for(session_root, safe_id)
vibecomfy/comfy_nodes/agent/_frag_chat.py:839:     "_stamped_turn_response_outcome", "_trim_chat_text", "_write_turn_chat_artifact",
vibecomfy/comfy_nodes/agent/_frag_chat.py:840:     "read_session_chat",

exec
/bin/zsh -lc 'rg -n "''^class .*Session|''^@dataclass|def invoke|TOOL_SPEC_BY_NAME|handler'"\\(\" vibecomfy/executor/agent_research_stage.py | sed -n '1,260p'
sed -n '780,1040p' vibecomfy/executor/agent_research_stage.py
rg -n \"class .*Budget|ToolBudget|budget_class|consume\" vibecomfy/executor/agent_research_stage.py vibecomfy/porting/edit/session.py vibecomfy/porting/edit/_resolve.py | sed -n '1,280p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
66:    TOOL_SPEC_BY_NAME,
746:@dataclass(frozen=True)
766:@dataclass(frozen=True)
841:class _StageToolSession:
880:    spec = TOOL_SPEC_BY_NAME[tool]
1260:            spec = TOOL_SPEC_BY_NAME[tool]
1362:            spec = TOOL_SPEC_BY_NAME[HIVE_MIND_SEARCH_TOOL]
    citations: tuple[str, ...]
    uncertainty: str
    status: str  # "ok" | "exhausted" | "failed" | "skipped"
    elapsed_seconds: float
    attempt: str = RESEARCH_ATTEMPT_NEVER
    warnings: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "route": self.route,
            "question": self.question,
            "iterations": [item.to_dict() for item in self.iterations],
            "final_verdict": self.final_verdict,
            "summary": self.summary,
            "citations": list(self.citations),
            "uncertainty": self.uncertainty,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "attempt": self.attempt,
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.error is not None:
            payload["error"] = self.error
        return payload


# ── the C1 tool-calling loop ─────────────────────────────────────────────────


def _tool_call_digest(
    *,
    tool: str,
    result: ToolResult,
    query: str = "",
    conclusion: str = "",
    evidence_ids: Sequence[str] = (),
) -> dict[str, Any]:
    # The digest shows the RECORDED artifact ids (what the agent can cite),
    # not ``result.evidence_ids`` — for ``hivemind_get`` the recorded id is
    # the namespaced ``hivemind_get:...`` artifact id, so digest ids and
    # artifact ids always agree (P1-b parity).
    return {
        "tool": tool,
        "status": result.status.value,
        "query": query,
        "evidence_ids": list(evidence_ids),
        "conclusion": conclusion,
    }


def _get_record_evidence_id(result: ToolResult, requested_id: str) -> str | None:
    """Evidence ID for a fetched record — namespaced so search-hit ids never collide."""
    if result.status is not ToolStatus.OK:
        return None
    if not requested_id.startswith(_HIVEMIND_EVIDENCE_ID_PREFIX):
        return None
    return f"hivemind_get:{requested_id.removeprefix(_HIVEMIND_EVIDENCE_ID_PREFIX)}"


class _StageToolSession:
    """Per-stage session namespace handed to the registry handlers.

    Carries the injected fakes (``search_fn`` / ``get_fn``) and the
    ``cache_root`` the tool modules need; the registry handlers read these
    attributes so the stage and the batch resolver share ONE dispatch path.
    """

    __slots__ = ("search_fn", "get_fn", "cache_root")

    def __init__(
        self,
        *,
        search_fn: Callable[..., ToolResult] | None,
        get_fn: Callable[..., ToolResult] | None,
        cache_root: Any,
    ) -> None:
        self.search_fn = search_fn
        self.get_fn = get_fn
        self.cache_root = cache_root


def _default_tool_fn(
    tool: str,
    args: Mapping[str, Any],
    *,
    search_fn: Callable[..., ToolResult] | None = None,
    get_fn: Callable[..., ToolResult] | None = None,
    cache_root: Any = None,
) -> ToolResult:
    """Execute one agent-chosen research tool call through the ToolSpec registry.

    The AGENT chooses the tool and arguments; Python only executes.  The
    allowlist and budgets were already enforced by the loop.  Dispatch and
    argument validation live in the registry: the registered handler receives
    the agent's declared arguments (filters/cursor/limit/timeout included) and
    a missing required argument or malformed value is a typed
    ``invalid_request`` — never a raise, never a dropped argument.
    """
    spec = TOOL_SPEC_BY_NAME[tool]
    session = _StageToolSession(
        search_fn=search_fn,
        get_fn=get_fn,
        cache_root=cache_root,
    )
    return invoke_tool(spec, session, args, None)


def run_agent_research_stage(
    *,
    route: str,
    question: str,
    spec: Any | None = None,
    search_fn: Callable[..., ToolResult] | None = None,
    get_fn: Callable[..., ToolResult] | None = None,
    judge_fn: Callable[..., dict[str, Any]] | None = None,
    tool_fn: Callable[..., ToolResult] | None = None,
    now_fn: Callable[[], float] | None = None,
    deadline_seconds: float = TOOL_PHASE_DEADLINE_SECONDS,
    max_turns: int = _MAX_TURNS,
    cache_root: Any = None,
    research_brief: str = "",
) -> tuple[AgentResearchTrace, EvidencePack]:
    """Run the C1 agent-owned tool-calling research loop.

    The AGENT chooses every tool call and decides when to finish; Python
    executes the chosen calls, records typed evidence, and enforces the
    research-phase allowlist plus I01 budgets (3 searches / 6 fetches /
    1 registry lookup / wall-clock ``deadline_seconds`` / ``max_turns``).
    RC2 exception: on ``route="adapt"``, if the agent still made zero
    evidence tool calls when the loop ends, Python executes one
    ``hivemind_search`` from the research question so ``research_attempt``
    is not stuck at ``never``.

    Per turn the agent returns one decision (via ``judge_fn``):
    ``{"action": "call", "tool", "args"}`` to gather more evidence or
    ``{"action": "finish", "conclusion", "evidence_ids", "uncertainty"}`` to
    stop.  A tool call outside the allowlist or a budget-exhausted call is a
    typed refusal recorded in the ledger; the agent sees it in the next
    digest and may finish or refine.

    ``research_brief`` (optional) is the full classifier brief assembled by
    :func:`build_research_brief`; it is embedded in every decision-turn
    message so the agent works from ALL search directions, graph context,
    source preferences, and the avoid-list — not just the narrow question.
    Each turn's digest also shows remaining calls, turns, and time so the
    agent can wind down to a finish.  The wall-clock deadline is enforced
    before the provider call, after the provider call (before executing a
    chosen tool), and after tool execution — slow provider/tool calls cannot
    silently overrun the budget.

    ``search_fn`` / ``get_fn`` / ``tool_fn`` / ``judge_fn`` default to the
    module-level tool implementations / provider decision turn, resolved at
    call time so tests and callers may inject fakes.  Never raises: failures
    are captured in the returned trace (``status="failed"`` / ``"exhausted"``)
    and the evidence pack recorded so far.
    """
    now = now_fn or time.monotonic
    if tool_fn is None:
        tool_fn = lambda tool, args, **kwargs: _default_tool_fn(  # noqa: E731
            tool, args, search_fn=search_fn, get_fn=get_fn, cache_root=cache_root
        )
    if judge_fn is None:
        judge_fn = _default_judge_fn(spec)
    started = now()
    deadline = started + max(0.0, float(deadline_seconds))

    artifacts: dict[str, EvidenceArtifact] = {}
    ledger_entries: list[EvidenceLedgerEntry] = []
    warnings: list[str] = []
    iterations: list[AgentResearchIteration] = []
    tool_call_digests: list[dict[str, Any]] = []
    # P1-c: count EXECUTED agent-chosen tool calls (not refusal/premature
    # digest entries) so a finish with zero research activity is detectable.
    tool_calls_made = 0
    searches_left = TOOL_SEARCH_BUDGET
    fetches_left = TOOL_FETCH_BUDGET
    registry_left = TOOL_REGISTRY_BUDGET

    final_verdict = "refine"
    final_summary = ""
    final_uncertainty = ""
    final_citations: tuple[str, ...] = ()
    status = "ok"
    error: str | None = None

    def _add_artifact(artifact: EvidenceArtifact) -> None:
        # Keep-first on id collisions across turns (deterministic).
        if artifact.evidence_id not in artifacts:
            artifacts[artifact.evidence_id] = artifact

    def _add_entry(entry: EvidenceLedgerEntry) -> None:
        ledger_entries.append(entry)

    def _record_call(
        tool: str,
        result: ToolResult,
        *,
        query: str,
        decision: str,
        conclusion: str,
        artifacts_to_add: Sequence[EvidenceArtifact] = (),
        evidence_ids: Sequence[str] = (),
    ) -> None:
        nonlocal tool_calls_made
        tool_calls_made += 1
        for artifact in artifacts_to_add:
            _add_artifact(artifact)
        _add_entry(
            EvidenceLedgerEntry(
                decision=decision,
                conclusion=conclusion,
                evidence_ids=tuple(evidence_ids),
                uncertainty=(
                    "" if result.status is ToolStatus.OK else conclusion
                ),
            )
        )
        digest = _tool_call_digest(
            tool=tool,
            result=result,
            query=query,
            conclusion=conclusion,
            evidence_ids=evidence_ids,
        )
        tool_call_digests.append(digest)
        iterations.append(
            AgentResearchIteration(
                iteration=len(iterations) + 1,
                question=current_question,
                tool_calls=(digest,),
                synthesis={},
                verdict="refine",
            )
        )

    def _refusal_call(tool: str, query: str, message: str) -> None:
        # A refusal is itself an agent-visible decision: it enters the digest
        # (so the agent can adapt), the ledger (typed, preserved), and the
        # trace (one iteration per turn — keeps the loop bounded).
        _add_entry(
            EvidenceLedgerEntry(
                decision=tool,
                conclusion=message,
                evidence_ids=(),
                uncertainty=message,
            )
        )
        warnings.append(message)
        digest = {
            "tool": tool,
            "status": ToolStatus.REFUSED.value,
            "query": query,
            "evidence_ids": [],
            "conclusion": message,
        }
        tool_call_digests.append(digest)
        iterations.append(
            AgentResearchIteration(
                iteration=len(iterations) + 1,
vibecomfy/executor/agent_research_stage.py:98:# Ledger entry decisions (stable identifiers consumed by the stage trace and
vibecomfy/executor/agent_research_stage.py:309:    is not currently consumed.
vibecomfy/executor/agent_research_stage.py:524:    downstream consumer of the synthesis, and the per-turn budget display;
vibecomfy/executor/agent_research_stage.py:534:        "Who consumes your result:\n"
vibecomfy/porting/edit/_resolve.py:246:# ``spec.budget_class`` ("search"/"fetch"/"registry"/None) the effort pool.
vibecomfy/porting/edit/_resolve.py:407:def _consume_tool_budget(
vibecomfy/porting/edit/_resolve.py:413:    A non-None ``refusal_code`` refuses the call (typed) and consumes nothing.
vibecomfy/porting/edit/_resolve.py:415:    (already consumed here); None for every other tool.
vibecomfy/porting/edit/_resolve.py:419:    budget_class = spec.budget_class
vibecomfy/porting/edit/_resolve.py:420:    if budget_class is None:
vibecomfy/porting/edit/_resolve.py:422:    if budget_class == "search":
vibecomfy/porting/edit/_resolve.py:427:    if budget_class == "fetch":
vibecomfy/porting/edit/_resolve.py:693:            # detail for consumers that pinned the legacy refusal shape.
vibecomfy/porting/edit/_resolve.py:897:        refusal_code, budget_payload = _consume_tool_budget(spec, surface)

exec
/bin/zsh -lc "sed -n '1,320p' vibecomfy/executor/graph_facts.py
sed -n '1,280p' vibecomfy/executor/graph_inspection.py
rg -n \"fact_id|lens_fact|trace_id|evidence_id\" vibecomfy/executor vibecomfy/porting/render.py | sed -n '1,320p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
from __future__ import annotations

from vibecomfy.ingest.normalize import door_get_links, door_get_nodes, door_get_widgets_values
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from vibecomfy.porting.widgets.compact_resolver import (
    compact_widget_names_for_node,
    missing_widget_value_sentinel,
    widget_index_for_field,
    widget_value_for_field,
)


NodeId = int | str

_MISSING_WIDGET_VALUE = missing_widget_value_sentinel()
_PRIMITIVE_SOURCE_CLASSES = frozenset(
    {
        "PrimitiveBoolean",
        "PrimitiveFloat",
        "PrimitiveInt",
        "PrimitiveNode",
        "PrimitiveString",
        "PrimitiveStringMultiline",
    }
)
_PASSTHROUGH_SOURCE_CLASSES = frozenset({"Reroute"})


@dataclass(frozen=True, slots=True)
class GraphFieldTarget:
    node_id: NodeId
    field_name: str | None = None
    widget_index: int | None = None

    def __post_init__(self) -> None:
        if self.field_name is None and self.widget_index is None:
            raise ValueError("GraphFieldTarget requires field_name or widget_index")


@dataclass(frozen=True, slots=True)
class LinkedSourceFact:
    node_id: NodeId
    class_type: str | None
    output_slot: int
    field_name: str | None = None
    widget_index: int | None = None
    value: Any = None
    value_known: bool = False
    value_source: str = "unknown"
    outgoing_link_count: int = 0


@dataclass(frozen=True, slots=True)
class EffectiveFieldFact:
    node_id: NodeId
    class_type: str | None
    field_name: str
    widget_index: int | None
    widget_name_source: str | None
    raw_value: Any = None
    raw_value_known: bool = False
    effective_value: Any = None
    effective_value_known: bool = False
    overridden: bool = False
    inert_static_edit: bool = False
    link_id: int | None = None
    source: LinkedSourceFact | None = None


@dataclass(frozen=True, slots=True)
class EffectiveValueChange:
    target: GraphFieldTarget
    before: EffectiveFieldFact
    after: EffectiveFieldFact
    raw_changed: bool | None
    effective_changed: bool | None


@dataclass(frozen=True, slots=True)
class _Edge:
    link_id: int | None
    origin_node: NodeId
    origin_slot: int
    target_node: NodeId
    target_slot: int | None = None
    target_input: str | None = None


@dataclass(frozen=True, slots=True)
class _GraphView:
    nodes_by_id: dict[str, Mapping[str, Any]]
    node_ids_by_key: dict[str, NodeId]
    edges: tuple[_Edge, ...]


def widget_field_name_for_index(
    graph: Mapping[str, Any],
    node_id: NodeId,
    widget_index: int,
    *,
    schema_provider: Any | None = None,
) -> str | None:
    """Return the semantic field name for a compact widget index."""

    view = _graph_view(graph)
    node = _node_for_id(view, node_id)
    if node is None:
        return None
    resolution = compact_widget_names_for_node(node, schema_provider=schema_provider)
    if 0 <= widget_index < len(resolution.names):
        return resolution.names[widget_index]
    return None


def inspect_effective_field(
    graph: Mapping[str, Any],
    target: GraphFieldTarget,
    *,
    schema_provider: Any | None = None,
) -> EffectiveFieldFact:
    """Inspect the raw and effective value for a widget-backed graph field."""

    view = _graph_view(graph)
    node = _node_for_id(view, target.node_id)
    if node is None:
        raise KeyError(f"Unknown node id {target.node_id!r}")

    actual_node_id = _actual_node_id(view, target.node_id)
    class_type = _class_type(node)
    field_name, widget_index, widget_name_source = _resolve_target_field(
        node,
        target,
        schema_provider=schema_provider,
    )
    raw_value, raw_known = _raw_value_for_field(
        node,
        field_name,
        widget_index,
        schema_provider=schema_provider,
    )
    link = _incoming_link_for_field(view, node, actual_node_id, field_name, widget_index)
    if link is None:
        return EffectiveFieldFact(
            node_id=actual_node_id,
            class_type=class_type,
            field_name=field_name,
            widget_index=widget_index,
            widget_name_source=widget_name_source,
            raw_value=raw_value,
            raw_value_known=raw_known,
            effective_value=raw_value,
            effective_value_known=raw_known,
        )

    source = _linked_source_fact(view, link, schema_provider=schema_provider)
    return EffectiveFieldFact(
        node_id=actual_node_id,
        class_type=class_type,
        field_name=field_name,
        widget_index=widget_index,
        widget_name_source=widget_name_source,
        raw_value=raw_value,
        raw_value_known=raw_known,
        effective_value=source.value if source.value_known else None,
        effective_value_known=source.value_known,
        overridden=True,
        inert_static_edit=True,
        link_id=link.link_id,
        source=source,
    )


def compare_effective_field(
    before_graph: Mapping[str, Any],
    after_graph: Mapping[str, Any],
    target: GraphFieldTarget,
    *,
    schema_provider: Any | None = None,
) -> EffectiveValueChange:
    """Compare raw and effective values for the same target in two graphs."""

    before = inspect_effective_field(before_graph, target, schema_provider=schema_provider)
    after = inspect_effective_field(after_graph, target, schema_provider=schema_provider)
    return EffectiveValueChange(
        target=target,
        before=before,
        after=after,
        raw_changed=_known_change(before.raw_value_known, before.raw_value, after.raw_value_known, after.raw_value),
        effective_changed=_known_change(
            before.effective_value_known,
            before.effective_value,
            after.effective_value_known,
            after.effective_value,
        ),
    )


def _graph_view(graph: Mapping[str, Any]) -> _GraphView:
    nodes_by_id: dict[str, Mapping[str, Any]] = {}
    node_ids_by_key: dict[str, NodeId] = {}
    for fallback_id, node in _iter_nodes(graph):
        node_id = _node_id(node, fallback_id)
        key = str(node_id)
        nodes_by_id[key] = node
        node_ids_by_key[key] = node_id

    return _GraphView(
        nodes_by_id=nodes_by_id,
        node_ids_by_key=node_ids_by_key,
        edges=tuple(_iter_edges(graph)),
    )


def _iter_nodes(graph: Mapping[str, Any]) -> list[tuple[NodeId, Mapping[str, Any]]]:
    nodes = door_get_nodes(graph)
    if isinstance(nodes, list):
        return [
            (index, node)
            for index, node in enumerate(nodes)
            if isinstance(node, Mapping)
        ]
    if isinstance(nodes, Mapping):
        return [
            (node_id, node)
            for node_id, node in nodes.items()
            if isinstance(node, Mapping)
        ]
    if all(isinstance(value, Mapping) for value in graph.values()):
        return [
            (node_id, node)
            for node_id, node in graph.items()
            if isinstance(node, Mapping) and ("class_type" in node or "inputs" in node)
        ]
    return []


def _iter_edges(graph: Mapping[str, Any]) -> list[_Edge]:
    edges: list[_Edge] = []

    links = door_get_links(graph)
    if isinstance(links, list):
        for index, link in enumerate(links):
            edge = _edge_from_link(link, index)
            if edge is not None:
                edges.append(edge)

    raw_edges = graph.get("edges")
    if isinstance(raw_edges, list):
        for index, edge in enumerate(raw_edges):
            parsed = _edge_from_vibe_edge(edge, index)
            if parsed is not None:
                edges.append(parsed)

    for target_id, node in _iter_nodes(graph):
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for input_name, value in inputs.items():
            api_link = _api_link_value(value)
            if api_link is None:
                continue
            source_id, output_slot = api_link
            edges.append(
                _Edge(
                    link_id=None,
                    origin_node=source_id,
                    origin_slot=output_slot,
                    target_node=_node_id(node, target_id),
                    target_input=str(input_name),
                )
            )
    return edges


def _edge_from_link(link: Any, index: int) -> _Edge | None:
    if isinstance(link, (list, tuple)):
        if len(link) < 5:
            return None
        return _Edge(
            link_id=_coerce_int(link[0], default=index),
            origin_node=link[1],
            origin_slot=_coerce_int(link[2], default=0),
            target_node=link[3],
            target_slot=_coerce_int(link[4], default=0),
        )
    if not isinstance(link, Mapping):
        return None
    origin = link.get("origin_id", link.get("from_node"))
    target = link.get("target_id", link.get("to_node"))
    if origin is None or target is None:
        return None
    target_input = link.get("to_input")
    return _Edge(
        link_id=_coerce_optional_int(link.get("id", link.get("link_id"))),
        origin_node=origin,
        origin_slot=_coerce_int(link.get("origin_slot", link.get("from_output")), default=0),
        target_node=target,
        target_slot=_coerce_optional_int(link.get("target_slot")),
        target_input=str(target_input) if target_input is not None else None,
    )


def _edge_from_vibe_edge(edge: Any, index: int) -> _Edge | None:
    if not isinstance(edge, Mapping):
        return None
    origin = edge.get("from_node", edge.get("origin_id"))
    target = edge.get("to_node", edge.get("target_id"))
    if origin is None or target is None:
        return None
    target_input = edge.get("to_input")
    return _Edge(
        link_id=_coerce_optional_int(edge.get("id", edge.get("link_id"))) or index,
        origin_node=origin,
        origin_slot=_coerce_int(edge.get("from_output", edge.get("origin_slot")), default=0),
        target_node=target,
        target_slot=_coerce_optional_int(edge.get("target_slot")),
        target_input=str(target_input) if target_input is not None else None,
"""Deterministic graph-inspection evidence extraction.

Product-path inspection projects from the IR (:class:`VibeWorkflow`).
Raw LiteGraph / envelope dicts enter only through the named ingest
doors (``from_ui`` / ``from_envelope`` / ``from_api``) and are then
read as ``wf.nodes``, ``wf.edges``, and ``wf.widgets``.

Every public function is pure: it never mutates the workflow or the
raw dict.  Failures during ingest yield empty evidence so callers can
treat inspection as best-effort.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeNode, VibeWorkflow


# ── typed evidence structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class WidgetEvidence:
    """One widget value extracted from a node's ``widgets_values`` list."""

    index: int
    value: Any
    name: str | None = None


@dataclass(frozen=True)
class SlotEvidence:
    """One input or output slot on a node."""

    name: str
    slot_type: str  # "input" | "output"
    link_id: int | None = None  # set for input slots connected to a link


@dataclass(frozen=True)
class NodeEvidence:
    """Structured evidence for one node in a ComfyUI graph."""

    node_id: int | str
    class_type: str
    title: str | None = None
    widgets: tuple[WidgetEvidence, ...] = ()
    input_slots: tuple[SlotEvidence, ...] = ()
    output_slots: tuple[SlotEvidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "widgets", tuple(self.widgets))
        object.__setattr__(self, "input_slots", tuple(self.input_slots))
        object.__setattr__(self, "output_slots", tuple(self.output_slots))


@dataclass(frozen=True)
class EdgeEvidence:
    """One link / edge in a ComfyUI graph."""

    link_id: int
    origin_node: int | str
    origin_slot: int
    target_node: int | str
    target_slot: int
    link_type: str | None = None


@dataclass(frozen=True)
class GraphEvidence:
    """Complete structured evidence extracted from a ComfyUI graph dict."""

    node_count: int
    nodes: tuple[NodeEvidence, ...] = ()
    edges: tuple[EdgeEvidence, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))


# ── link normalisation ───────────────────────────────────────────────────────


def _normalise_link(link: dict | list, index: int = 0) -> EdgeEvidence:
    """Convert a single link element to a uniform :class:`EdgeEvidence`.

    ComfyUI represents links in two shapes:

    **List shape** (positional)::

        [link_id, origin_node, origin_slot, target_node, target_slot, link_type]

    **Dict shape** (named)::

        {
            "id": …,
            "origin_id": …,   "origin_slot": …,
            "target_id": …,   "target_slot": …,
            "type": …,
        }

    Returns an :class:`EdgeEvidence` with deterministic field extraction for
    either shape.
    """
    if isinstance(link, list):
        lid = int(link[0]) if len(link) > 0 else index
        src_node = link[1] if len(link) > 1 else 0
        src_slot = int(link[2]) if len(link) > 2 else 0
        tgt_node = link[3] if len(link) > 3 else 0
        tgt_slot = int(link[4]) if len(link) > 4 else 0
        ltype: str | None = str(link[5]) if len(link) > 5 and link[5] is not None else None
        return EdgeEvidence(
            link_id=lid,
            origin_node=src_node,
            origin_slot=src_slot,
            target_node=tgt_node,
            target_slot=tgt_slot,
            link_type=ltype,
        )
    # dict shape
    lid = int(link.get("id", link.get("link_id", index)))
    return EdgeEvidence(
        link_id=lid,
        origin_node=link.get("origin_id", 0),
        origin_slot=int(link.get("origin_slot", 0)),
        target_node=link.get("target_id", 0),
        target_slot=int(link.get("target_slot", 0)),
        link_type=link.get("type"),
    )


def normalise_links(links: list) -> tuple[EdgeEvidence, ...]:
    """Normalise a list of link elements into a tuple of :class:`EdgeEvidence`.

    Accepts a list of either list-shaped or dict-shaped link elements and
    returns a deterministic, typed tuple suitable for evidence consumers.
    """
    return tuple(_normalise_link(link, idx) for idx, link in enumerate(links))


# ── node extraction ──────────────────────────────────────────────────────────


def _sort_widget_name(name: str) -> tuple[int, Any]:
    if name.startswith("widget_"):
        suffix = name.split("_", 1)[1]
        if suffix.isdigit():
            return (0, int(suffix))
    return (1, name)


def _evidence_id(value: Any) -> int | str:
    """Prefer an int node id when the IR id is a digit string."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value)
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return value if isinstance(value, str) else text


def _slot_index(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _node_title(node: VibeNode) -> str | None:
    metadata = node.metadata
    if not isinstance(metadata, dict):
        return None
    raw_ui = metadata.get("_ui")
    if not isinstance(raw_ui, dict):
        return None
    title = raw_ui.get("title")
    if isinstance(title, str) and title.strip():
        return title
    return None


def _declared_output_names(node: VibeNode) -> tuple[str, ...]:
    metadata = node.metadata
    if not isinstance(metadata, dict):
        return ()
    names: list[str] = []
    seen: set[str] = set()

    def _add(name: Any) -> None:
        text = str(name)
        if not text or text in seen:
            return
        seen.add(text)
        names.append(text)

    declared = metadata.get("output_names")
    if isinstance(declared, (list, tuple)):
        for name in declared:
            _add(name)
    raw_ui = metadata.get("_ui")
    if isinstance(raw_ui, dict):
        outputs = raw_ui.get("outputs")
        if isinstance(outputs, list):
            for item in outputs:
                if isinstance(item, dict):
                    _add(item.get("name"))
                elif isinstance(item, str):
                    _add(item)
    return tuple(names)


def _schema_widget_names_for_node(node: VibeNode) -> tuple[str, ...]:
    """Schema field names for this instance, positional-index aligned (RC8-A)."""
    try:
        from vibecomfy.porting.widgets.schema import effective_widget_names_for_class

        names = effective_widget_names_for_class(
            str(node.class_type),
            allow_object_info_fallback=True,
        )
        return tuple(str(name) for name in names if name)
    except Exception:
        return ()


def _widgets_from_ir(node: VibeNode) -> tuple[WidgetEvidence, ...]:
    raw = node.raw_widgets
    values = getattr(raw, "values", None)
    schema_names = _schema_widget_names_for_node(node)
    if isinstance(values, list):
        return tuple(
            WidgetEvidence(
                index=index,
                name=schema_names[index] if index < len(schema_names) else None,
                value=value,
            )
            for index, value in enumerate(values)
        )

    named: list[WidgetEvidence] = []
    widgets = node.widgets
    if isinstance(widgets, dict) and widgets:
        for offset, name in enumerate(sorted((str(key) for key in widgets), key=_sort_widget_name)):
            named.append(WidgetEvidence(index=offset, name=name, value=widgets[name]))
    inputs = node.inputs
    if isinstance(inputs, dict):
        base = len(named)
        for offset, name in enumerate(sorted(str(key) for key in inputs)):
            value = inputs[name]
            if isinstance(value, (dict, list, tuple)):
                continue
            named.append(WidgetEvidence(index=base + offset, name=str(name), value=value))
    return tuple(named)


def _node_from_ir(
    node: VibeNode,
    incoming: dict[str, dict[str, int]],
    outgoing: dict[str, set[str]],
) -> NodeEvidence:
    node_key = str(node.id)
    incoming_for_node = incoming.get(node_key, {})
    input_slots = tuple(
        SlotEvidence(name=name, slot_type="input", link_id=link_id)
        for name, link_id in sorted(incoming_for_node.items())
    )
    output_names = list(_declared_output_names(node))
    seen = set(output_names)
    for name in sorted(outgoing.get(node_key, set())):
vibecomfy/executor/hivemind_clients.py:696:def _evidence_id(table: str, row: Mapping[str, Any]) -> str | None:
vibecomfy/executor/hivemind_clients.py:719:def _parse_evidence_id(evidence_id: str) -> tuple[str, str] | None:
vibecomfy/executor/hivemind_clients.py:721:    if not isinstance(evidence_id, str):
vibecomfy/executor/hivemind_clients.py:723:    parts = evidence_id.split(":", 2)
vibecomfy/executor/hivemind_clients.py:915:        return _evidence_id(str(row.get("_hivemind_table") or ""), row) or ""
vibecomfy/executor/hivemind_clients.py:959:        "evidence_id": _evidence_id(table, row),
vibecomfy/executor/hivemind_clients.py:1070:            if _evidence_id(table, row) is None:
vibecomfy/executor/hivemind_clients.py:1084:        evidence_id = _evidence_id(str(row.get("_hivemind_table") or ""), row)
vibecomfy/executor/hivemind_clients.py:1085:        if evidence_id is None:
vibecomfy/executor/hivemind_clients.py:1087:        if evidence_id in seen:
vibecomfy/executor/hivemind_clients.py:1089:        seen.add(evidence_id)
vibecomfy/executor/agent_research_stage.py:162:    if entry.evidence_ids:
vibecomfy/executor/agent_research_stage.py:170:def _is_fetched_citation(evidence_id: str) -> bool:
vibecomfy/executor/agent_research_stage.py:178:    return str(evidence_id).startswith("hivemind_get:") or str(
vibecomfy/executor/agent_research_stage.py:179:        evidence_id
vibecomfy/executor/agent_research_stage.py:212:        evidence_id: artifact
vibecomfy/executor/agent_research_stage.py:213:        for evidence_id, artifact in artifacts_map.items()
vibecomfy/executor/agent_research_stage.py:214:        if evidence_id != _QUESTION_ARTIFACT_ID
vibecomfy/executor/agent_research_stage.py:219:        evidence_id
vibecomfy/executor/agent_research_stage.py:222:        for evidence_id in entry.evidence_ids
vibecomfy/executor/agent_research_stage.py:224:    if any(_is_fetched_citation(evidence_id) for evidence_id in cited):
vibecomfy/executor/agent_research_stage.py:370:        {"action": "finish", "conclusion": str, "evidence_ids": [str, ...],
vibecomfy/executor/agent_research_stage.py:422:    raw_ids = parsed.get("evidence_ids")
vibecomfy/executor/agent_research_stage.py:426:        raise ValueError("agent research decision: evidence_ids must be a list")
vibecomfy/executor/agent_research_stage.py:427:    evidence_ids: list[str] = []
vibecomfy/executor/agent_research_stage.py:430:            evidence_ids.append(item.strip())
vibecomfy/executor/agent_research_stage.py:445:        "evidence_ids": evidence_ids,
vibecomfy/executor/agent_research_stage.py:571:        '{"action": "finish", "conclusion": string, "evidence_ids": [string, ...], '
vibecomfy/executor/agent_research_stage.py:636:        ids = [str(item) for item in (call.get("evidence_ids") or ())]
vibecomfy/executor/agent_research_stage.py:646:        for evidence_id in ids:
vibecomfy/executor/agent_research_stage.py:647:            artifact = artifacts.get(evidence_id)
vibecomfy/executor/agent_research_stage.py:651:            title = _bounded(body.get("title") or body.get("name") or body.get("evidence_id") or evidence_id, 90)
vibecomfy/executor/agent_research_stage.py:675:            line = f"    [{evidence_id}] {title}"
vibecomfy/executor/agent_research_stage.py:817:    evidence_ids: Sequence[str] = (),
vibecomfy/executor/agent_research_stage.py:820:    # not ``result.evidence_ids`` — for ``hivemind_get`` the recorded id is
vibecomfy/executor/agent_research_stage.py:827:        "evidence_ids": list(evidence_ids),
vibecomfy/executor/agent_research_stage.py:832:def _get_record_evidence_id(result: ToolResult, requested_id: str) -> str | None:
vibecomfy/executor/agent_research_stage.py:917:    ``{"action": "finish", "conclusion", "evidence_ids", "uncertainty"}`` to
vibecomfy/executor/agent_research_stage.py:969:        if artifact.evidence_id not in artifacts:
vibecomfy/executor/agent_research_stage.py:970:            artifacts[artifact.evidence_id] = artifact
vibecomfy/executor/agent_research_stage.py:983:        evidence_ids: Sequence[str] = (),
vibecomfy/executor/agent_research_stage.py:993:                evidence_ids=tuple(evidence_ids),
vibecomfy/executor/agent_research_stage.py:1004:            evidence_ids=evidence_ids,
vibecomfy/executor/agent_research_stage.py:1025:                evidence_ids=(),
vibecomfy/executor/agent_research_stage.py:1034:            "evidence_ids": [],
vibecomfy/executor/agent_research_stage.py:1060:                evidence_ids=(),
vibecomfy/executor/agent_research_stage.py:1069:            "evidence_ids": [],
vibecomfy/executor/agent_research_stage.py:1088:                evidence_id=_QUESTION_ARTIFACT_ID,
vibecomfy/executor/agent_research_stage.py:1098:                evidence_ids=(_QUESTION_ARTIFACT_ID,),
vibecomfy/executor/agent_research_stage.py:1132:                # rejects duplicate evidence_ids, and a duplicated citation
vibecomfy/executor/agent_research_stage.py:1136:                        evidence_id
vibecomfy/executor/agent_research_stage.py:1137:                        for evidence_id in (decision.get("evidence_ids") or ())
vibecomfy/executor/agent_research_stage.py:1138:                        if evidence_id in artifacts
vibecomfy/executor/agent_research_stage.py:1176:                        evidence_ids=cited,
vibecomfy/executor/agent_research_stage.py:1187:                        evidence_ids=cited,
vibecomfy/executor/agent_research_stage.py:1203:                            "evidence_ids": list(cited),
vibecomfy/executor/agent_research_stage.py:1279:                    evidence_ids=tuple(entry["evidence_ids"]),
vibecomfy/executor/agent_research_stage.py:1282:                requested_id = str(args.get("evidence_id") or "")
vibecomfy/executor/agent_research_stage.py:1283:                get_evidence_id = _get_record_evidence_id(result, requested_id)
vibecomfy/executor/agent_research_stage.py:1298:                if get_evidence_id is not None:
vibecomfy/executor/agent_research_stage.py:1308:                                    dict(body), evidence_id=get_evidence_id
vibecomfy/executor/agent_research_stage.py:1315:                                evidence_id=get_evidence_id,
vibecomfy/executor/agent_research_stage.py:1328:                    evidence_ids=(get_evidence_id,) if get_evidence_id is not None else (),
vibecomfy/executor/agent_research_stage.py:1338:                    evidence_ids=tuple(entry["evidence_ids"]),
vibecomfy/executor/agent_research_stage.py:1380:                evidence_ids=tuple(entry["evidence_ids"]),
vibecomfy/executor/contracts.py:2370:    read and cited (by ``evidence_id``), never merged into the user's graph.
vibecomfy/executor/contracts.py:2374:    evidence_id: str
vibecomfy/executor/contracts.py:2388:        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
vibecomfy/executor/contracts.py:2389:            raise ValueError("`evidence_id` must be a non-empty string.")
vibecomfy/executor/contracts.py:2390:        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
vibecomfy/executor/contracts.py:2402:            "evidence_id": self.evidence_id,
vibecomfy/executor/contracts.py:2417:            evidence_id=payload.get("evidence_id", ""),
vibecomfy/executor/graph_inspection.py:157:def _evidence_id(value: Any) -> int | str:
vibecomfy/executor/graph_inspection.py:286:        node_id=_evidence_id(node.id),
vibecomfy/executor/graph_inspection.py:936:                origin_node=_evidence_id(edge.from_node),
vibecomfy/executor/graph_inspection.py:938:                target_node=_evidence_id(edge.to_node),
vibecomfy/executor/hivemind_tools.py:10:Every returned hit carries a stable, resolvable ``evidence_id`` of the form
vibecomfy/executor/hivemind_tools.py:39:    _parse_evidence_id,
vibecomfy/executor/hivemind_tools.py:348:    evidence_id: str,
vibecomfy/executor/hivemind_tools.py:374:                evidence_id=evidence_id,
vibecomfy/executor/hivemind_tools.py:383:            evidence_id=evidence_id,
vibecomfy/executor/hivemind_tools.py:413:                evidence_id=evidence_id,
vibecomfy/executor/hivemind_tools.py:420:            evidence_id=evidence_id,
vibecomfy/executor/hivemind_tools.py:426:        evidence_id=evidence_id,
vibecomfy/executor/hivemind_tools.py:472:    ``evidence_id`` resolvable via :func:`hivemind_get`.
vibecomfy/executor/hivemind_tools.py:586:        evidence_ids=tuple(hit["evidence_id"] for hit in hits),
vibecomfy/executor/hivemind_tools.py:592:    evidence_id: str,
vibecomfy/executor/hivemind_tools.py:602:    if not isinstance(evidence_id, str) or not evidence_id.strip():
vibecomfy/executor/hivemind_tools.py:605:            "evidence_id_required",
vibecomfy/executor/hivemind_tools.py:606:            "`evidence_id` must be a non-empty string.",
vibecomfy/executor/hivemind_tools.py:608:    evidence_id = evidence_id.strip()
vibecomfy/executor/hivemind_tools.py:609:    parsed = _parse_evidence_id(evidence_id)
vibecomfy/executor/hivemind_tools.py:613:            "invalid_evidence_id",
vibecomfy/executor/hivemind_tools.py:614:            "`evidence_id` must look like hivemind:<table>:<row_id> for a "
vibecomfy/executor/hivemind_tools.py:649:    record_view = serve_hivemind_record(row, evidence_id=evidence_id)
vibecomfy/executor/hivemind_tools.py:654:            "evidence_id": evidence_id,
vibecomfy/executor/hivemind_tools.py:660:        evidence_ids=(evidence_id,),
vibecomfy/executor/evidence_pack.py:5:and are resolved by ``evidence_id`` when a consumer needs to inspect them.
vibecomfy/executor/evidence_pack.py:119:    evidence_id: str
vibecomfy/executor/evidence_pack.py:126:        object.__setattr__(self, "evidence_id", _required_text(self.evidence_id, "evidence_id"))
vibecomfy/executor/evidence_pack.py:137:            "evidence_id": self.evidence_id,
vibecomfy/executor/evidence_pack.py:152:            required=frozenset({"evidence_id", "kind", "body", "metadata"}),
vibecomfy/executor/evidence_pack.py:157:            evidence_id=payload["evidence_id"],
vibecomfy/executor/evidence_pack.py:171:    evidence_ids: tuple[str, ...]
vibecomfy/executor/evidence_pack.py:187:            "evidence_ids",
vibecomfy/executor/evidence_pack.py:188:            _text_tuple(self.evidence_ids, "evidence_ids"),
vibecomfy/executor/evidence_pack.py:205:            "evidence_ids": list(self.evidence_ids),
vibecomfy/executor/evidence_pack.py:215:            required=frozenset({"decision", "conclusion", "evidence_ids", "uncertainty"}),
vibecomfy/executor/evidence_pack.py:221:            evidence_ids=payload["evidence_ids"],
vibecomfy/executor/evidence_pack.py:243:    def evidence_ids(self) -> tuple[str, ...]:
vibecomfy/executor/evidence_pack.py:245:            evidence_id
vibecomfy/executor/evidence_pack.py:247:            for evidence_id in entry.evidence_ids
vibecomfy/executor/evidence_pack.py:250:    def validate_references(self, available_evidence_ids: set[str] | frozenset[str]) -> None:
vibecomfy/executor/evidence_pack.py:251:        unresolved = sorted(set(self.evidence_ids) - set(available_evidence_ids))
vibecomfy/executor/evidence_pack.py:274:        raise ValueError("`artifacts` must be an object keyed by evidence_id.")
vibecomfy/executor/evidence_pack.py:277:        evidence_id = _required_text(raw_key, "artifacts key")
vibecomfy/executor/evidence_pack.py:283:        if artifact.evidence_id != evidence_id:
vibecomfy/executor/evidence_pack.py:285:                f"Artifact key {evidence_id!r} does not match its evidence_id "
vibecomfy/executor/evidence_pack.py:286:                f"{artifact.evidence_id!r}."
vibecomfy/executor/evidence_pack.py:288:        normalized[evidence_id] = artifact
vibecomfy/executor/evidence_pack.py:313:                evidence_id: artifact.to_dict()
vibecomfy/executor/evidence_pack.py:314:                for evidence_id, artifact in self.artifacts.items()
vibecomfy/executor/core.py:911:            evidence_ids=(),
vibecomfy/executor/core.py:930:        evidence_id
vibecomfy/executor/core.py:931:        for evidence_id in trace.citations
vibecomfy/executor/core.py:932:        if str(evidence_id).startswith("hivemind_get:")
vibecomfy/executor/core.py:1030:        str(evidence_id) != "research_question" for evidence_id in pack.artifacts
vibecomfy/executor/schemas/tool_result.schema.json:7:  "required": ["tool_name", "status", "result", "evidence_ids", "diagnostics"],
vibecomfy/executor/schemas/tool_result.schema.json:22:    "evidence_ids": {
vibecomfy/executor/tool_contracts.py:79:    evidence_ids: tuple[str, ...] = ()
vibecomfy/executor/tool_contracts.py:87:        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
vibecomfy/executor/tool_contracts.py:113:            "evidence_ids": list(self.evidence_ids),
vibecomfy/executor/tool_contracts.py:126:            required=frozenset({"tool_name", "status", "result", "evidence_ids", "diagnostics"}),
vibecomfy/executor/tool_contracts.py:134:            evidence_ids=payload["evidence_ids"],
vibecomfy/executor/schemas/stage_package.schema.json:61:      "required": ["evidence_id", "kind", "body", "metadata"],
vibecomfy/executor/schemas/stage_package.schema.json:63:        "evidence_id": {"type": "string", "minLength": 1},
vibecomfy/executor/schemas/stage_package.schema.json:84:      "required": ["decision", "conclusion", "evidence_ids", "uncertainty"],
vibecomfy/executor/schemas/stage_package.schema.json:88:        "evidence_ids": {
vibecomfy/executor/schemas/stage_package.schema.json:99:      "required": ["code", "message", "severity", "evidence_ids", "details"],
vibecomfy/executor/schemas/stage_package.schema.json:104:        "evidence_ids": {
vibecomfy/executor/schemas/stage_package.schema.json:119:        "evidence_ids",
vibecomfy/executor/schemas/stage_package.schema.json:131:        "evidence_ids": {
vibecomfy/executor/prompts.py:56:    '"evidence_ids", "options", and optional "bounded_assumption".\n'
vibecomfy/executor/schemas/needs_input.schema.json:11:    "evidence_ids",
vibecomfy/executor/schemas/needs_input.schema.json:23:    "evidence_ids": {
vibecomfy/executor/schemas/evidence_pack.schema.json:20:      "required": ["evidence_id", "kind", "body", "metadata"],
vibecomfy/executor/schemas/evidence_pack.schema.json:22:        "evidence_id": {"type": "string", "minLength": 1},
vibecomfy/executor/schemas/evidence_pack.schema.json:43:      "required": ["decision", "conclusion", "evidence_ids", "uncertainty"],
vibecomfy/executor/schemas/evidence_pack.schema.json:47:        "evidence_ids": {
vibecomfy/executor/stage_contracts.py:49:    evidence_ids: tuple[str, ...] = ()
vibecomfy/executor/stage_contracts.py:59:        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
vibecomfy/executor/stage_contracts.py:69:            "evidence_ids": list(self.evidence_ids),
vibecomfy/executor/stage_contracts.py:79:            required=frozenset({"code", "message", "severity", "evidence_ids", "details"}),
vibecomfy/executor/stage_contracts.py:86:            evidence_ids=payload["evidence_ids"],
vibecomfy/executor/stage_contracts.py:98:    evidence_ids: tuple[str, ...] = ()
vibecomfy/executor/stage_contracts.py:109:        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
vibecomfy/executor/stage_contracts.py:123:            "evidence_ids": list(self.evidence_ids),
vibecomfy/executor/stage_contracts.py:140:                "evidence_ids",
vibecomfy/executor/stage_contracts.py:154:            evidence_ids=payload.get("evidence_ids") or (),
vibecomfy/executor/stage_contracts.py:215:        referenced_ids = set(ledger.evidence_ids)
vibecomfy/executor/stage_contracts.py:217:            referenced_ids.update(diagnostic.evidence_ids)
vibecomfy/executor/stage_contracts.py:219:            referenced_ids.update(needs_input.evidence_ids)
vibecomfy/executor/stage_contracts.py:229:    def evidence_ids(self) -> tuple[str, ...]:
vibecomfy/executor/stage_contracts.py:237:                evidence_id: artifact.to_dict()
vibecomfy/executor/stage_contracts.py:238:                for evidence_id, artifact in self.artifacts.items()
vibecomfy/executor/web_tools.py:18:  ``evidence_ids``.
vibecomfy/executor/web_tools.py:31:artifacts behind the returned ``evidence_ids``.
vibecomfy/executor/web_tools.py:241:    evidence_ids: tuple[str, ...] = ()
vibecomfy/executor/web_tools.py:254:        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
vibecomfy/executor/web_tools.py:277:            "evidence_ids": list(self.evidence_ids),
vibecomfy/executor/web_tools.py:291:                {"tool_name", "query", "status", "unresolved_question", "evidence_ids"}
vibecomfy/executor/web_tools.py:301:            evidence_ids=payload["evidence_ids"],
vibecomfy/executor/web_tools.py:358:        """Evidence artifacts recorded behind the returned ``evidence_ids``."""
vibecomfy/executor/web_tools.py:362:    def evidence_ids(self) -> tuple[str, ...]:
vibecomfy/executor/web_tools.py:371:        evidence_ids: tuple[str, ...] = (),
vibecomfy/executor/web_tools.py:381:            evidence_ids=evidence_ids,
vibecomfy/executor/web_tools.py:437:            evidence_ids=evidence_ids,
vibecomfy/executor/web_tools.py:452:        return ``results`` and record ``evidence_ids`` referencing
vibecomfy/executor/web_tools.py:531:        evidence_ids = self._register_artifacts(query, results)
vibecomfy/executor/web_tools.py:536:            evidence_ids=evidence_ids,
vibecomfy/executor/web_tools.py:548:            evidence_ids=evidence_ids,
vibecomfy/executor/web_tools.py:559:        evidence_ids: list[str] = []
vibecomfy/executor/web_tools.py:561:            evidence_id = f"web:{digest}:{rank:02d}"
vibecomfy/executor/web_tools.py:563:                evidence_id=evidence_id,
vibecomfy/executor/web_tools.py:577:            self._artifacts[evidence_id] = artifact
vibecomfy/executor/web_tools.py:578:            evidence_ids.append(evidence_id)
vibecomfy/executor/web_tools.py:579:        return tuple(evidence_ids)
vibecomfy/executor/web_tools.py:598:    ``evidence_ids`` referencing raw results stored as
vibecomfy/executor/lookup_tools.py:116:        evidence_ids=(),
vibecomfy/executor/tool_specs.py:62:def _tool_evidence_id(*parts: str) -> str:
vibecomfy/executor/tool_specs.py:69:    for key in ("query", "evidence_id", "node_class", "template_id", "capability", "intent", "operation"):
vibecomfy/executor/tool_specs.py:81:    evidence_ids: tuple[str, ...],
vibecomfy/executor/tool_specs.py:87:        "evidence_ids": list(evidence_ids),
vibecomfy/executor/tool_specs.py:102:        evidence_ids=(),
vibecomfy/executor/tool_specs.py:126:    return f"  hit {index}: {title} [{hit.get('evidence_id') or '?'}]{suffix}"
vibecomfy/executor/tool_specs.py:139:        evidence_id = str(hit.get("evidence_id") or "")
vibecomfy/executor/tool_specs.py:140:        if not evidence_id:
vibecomfy/executor/tool_specs.py:142:        artifacts[evidence_id] = EvidenceArtifact(
vibecomfy/executor/tool_specs.py:143:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:156:        evidence_ids=ids,
vibecomfy/executor/tool_specs.py:171:    evidence_id = str(
vibecomfy/executor/tool_specs.py:172:        body.get("evidence_id")
vibecomfy/executor/tool_specs.py:173:        or (result.evidence_ids[0] if result.evidence_ids else "")
vibecomfy/executor/tool_specs.py:177:    if evidence_id:
vibecomfy/executor/tool_specs.py:178:        artifacts[evidence_id] = EvidenceArtifact(
vibecomfy/executor/tool_specs.py:179:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:184:    ids = (evidence_id,) if evidence_id else ()
vibecomfy/executor/tool_specs.py:189:    conclusion = f"{source_type} record {evidence_id}" + (f": {title}" if title else "")
vibecomfy/executor/tool_specs.py:191:        decision=f"hivemind_get {evidence_id!r}",
vibecomfy/executor/tool_specs.py:193:        evidence_ids=ids,
vibecomfy/executor/tool_specs.py:212:        evidence_id = result.evidence_ids[rank] if rank < len(result.evidence_ids) else ""
vibecomfy/executor/tool_specs.py:213:        if not evidence_id:
vibecomfy/executor/tool_specs.py:215:        artifacts[evidence_id] = EvidenceArtifact(
vibecomfy/executor/tool_specs.py:216:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:229:        evidence_ids=ids,
vibecomfy/executor/tool_specs.py:234:        evidence_id = result.evidence_ids[index - 1] if index - 1 < len(result.evidence_ids) else ""
vibecomfy/executor/tool_specs.py:237:            f"[{evidence_id or '?'}] {item.get('url') or ''}".rstrip()
vibecomfy/executor/tool_specs.py:250:    evidence_id = _tool_evidence_id("registry_lookup", node_class)
vibecomfy/executor/tool_specs.py:252:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:253:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:273:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:295:    evidence_id = _tool_evidence_id("node_schema", class_type)
vibecomfy/executor/tool_specs.py:297:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:298:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:316:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:332:    evidence_id = _tool_evidence_id("ready_template_list", filter_text or "all")
vibecomfy/executor/tool_specs.py:334:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:335:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:349:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:364:    evidence_id = _tool_evidence_id("ready_template_load", template_id)
vibecomfy/executor/tool_specs.py:366:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:367:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:379:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:391:        lines.append(f"  content excerpt (evidence_id {evidence_id}; full body not echoed):{truncated}\n{excerpt}")
vibecomfy/executor/tool_specs.py:400:    evidence_id = _tool_evidence_id("rank_edit_targets", intent)
vibecomfy/executor/tool_specs.py:402:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:403:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:417:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:434:    evidence_id = _tool_evidence_id("suggest_seed_nodes", intent)
vibecomfy/executor/tool_specs.py:436:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:437:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:451:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:468:    evidence_id = _tool_evidence_id("layout_hints", operation)
vibecomfy/executor/tool_specs.py:470:        evidence_id: EvidenceArtifact(
vibecomfy/executor/tool_specs.py:471:            evidence_id=evidence_id,
vibecomfy/executor/tool_specs.py:489:        evidence_ids=(evidence_id,),
vibecomfy/executor/tool_specs.py:537:        return get_fn(args["evidence_id"], timeout=args.get("timeout", 5.0))
vibecomfy/executor/tool_specs.py:539:        args["evidence_id"],
vibecomfy/executor/tool_specs.py:728:        positional_names=("evidence_id",),
vibecomfy/executor/tool_specs.py:729:        keywords=("evidence_id", "timeout"),
vibecomfy/executor/tool_specs.py:730:        required=("evidence_id",),
vibecomfy/executor/tool_specs.py:948:    "_tool_evidence_id",

exec
/bin/zsh -lc "sed -n '2320,2435p' vibecomfy/executor/contracts.py
rg -n \"PrecedentSlice|precedent.*render|surface.*topology|oversized|omitted\" vibecomfy/executor tests | sed -n '1,320p'
rg -n \"from_envelope|from_ui|named ingest|workflow.*record\" vibecomfy/executor/hivemind_tools.py vibecomfy/executor/hivemind_clients.py vibecomfy/executor/revision_evidence.py | sed -n '1,260p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
            )
    return violations


def _claim_operations(payload: Any) -> list[Any]:
    """Collect ``(uid, field_path)`` claim items from a payload mapping."""
    if not isinstance(payload, Mapping):
        return []
    operations = payload.get("operations")
    if isinstance(operations, list):
        return operations
    changes = payload.get("changes")
    if isinstance(changes, list):
        return changes
    return []


# ── Hivemind record views (batch 13: IR-shaped research records) ─────────────
#
# Typed classification of fetched Hivemind rows served to the research agent.
# A workflow record (a workflow JSON from the corpus) is normalized through
# the named ingest doors (from_ui / from_api / from_envelope per detected
# shape) and served as the IR surface lens; a non-workflow record (a message,
# a text post, a non-workflow JSON) is served as typed non-workflow evidence
# with its actual content; a workflow-shaped record that fails the named-door
# normalization is served as a typed malformed-record result with the error.
# The raw source row never rides in the view — it is retained only in the
# evidence artifact body (the raw body), never in model-facing content.

RECORD_TYPE_WORKFLOW = "workflow"
RECORD_TYPE_NON_WORKFLOW = "non_workflow"
RECORD_TYPE_MALFORMED = "malformed_record"
_RECORD_TYPES = frozenset(
    {RECORD_TYPE_WORKFLOW, RECORD_TYPE_NON_WORKFLOW, RECORD_TYPE_MALFORMED}
)


@dataclass(frozen=True)
class HivemindRecordView:
    """The typed, model-facing view of one fetched Hivemind record.

    Exactly one content field is populated per ``record_type``:

    * ``workflow`` — ``surface_lens`` carries ``render(wf, "surface")`` (the
      Python view) of the record normalized through the named ingest door;
      ``shape`` records the detected door shape (``ui`` / ``api`` / ``vibe``).
    * ``non_workflow`` — ``content`` carries the record's actual text/body.
    * ``malformed_record`` — ``error`` carries the normalization failure.

    The view is an immutable source pattern for the research agent: it is
    read and cited (by ``evidence_id``), never merged into the user's graph.
    """

    record_type: str
    evidence_id: str
    source_type: str = "hivemind"
    surface_lens: str | None = None
    content: str | None = None
    error: str | None = None
    shape: str | None = None

    def __post_init__(self) -> None:
        if self.record_type not in _RECORD_TYPES:
            raise ValueError(
                "`record_type` must be one of: "
                + ", ".join(sorted(_RECORD_TYPES))
                + f"; got {self.record_type!r}."
            )
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("`evidence_id` must be a non-empty string.")
        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
        if not isinstance(self.source_type, str) or not self.source_type.strip():
            raise ValueError("`source_type` must be a non-empty string.")
        object.__setattr__(self, "source_type", self.source_type.strip())
        for name in ("surface_lens", "content", "error", "shape"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"`{name}` must be a string or null.")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "record_type": self.record_type,
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
        }
        for name in ("surface_lens", "content", "error", "shape"):
            value = getattr(self, name)
            if value is not None:
                payload[name] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HivemindRecordView":
        if not isinstance(payload, Mapping):
            raise ValueError("HivemindRecordView must be an object.")
        return cls(
            record_type=payload.get("record_type", ""),
            evidence_id=payload.get("evidence_id", ""),
            source_type=payload.get("source_type", "hivemind"),
            surface_lens=payload.get("surface_lens"),
            content=payload.get("content"),
            error=payload.get("error"),
            shape=payload.get("shape"),
        )


__all__ = [
    "AgentEvidence",
    "AgentTurnResult",
    "ClassifyDecision",
    "ExecutorRequest",
    "ExecutorResult",
    "GraphFacts",
    "HivemindRecordView",
    "ImplementationResult",
    "ReadinessReport",
vibecomfy/executor/prompts.py:144:    "- Avoid is optional and should usually be omitted. Use it only to block generic searches such as "
vibecomfy/executor/core.py:297:#   * reply (inspect / respond with a graph) → surface + diff(Δ) + topology
vibecomfy/executor/core.py:303:_REPLY_LENSES: tuple[str, ...] = ("surface", "diff", "topology")
vibecomfy/executor/core.py:316:    ("surface", "diff", "topology"))`` — the complete Python-surface view,
vibecomfy/executor/core.py:320:    stage, which has no accepted Δ yet, requests surface+topology).  The
vibecomfy/executor/core.py:1204:    # the composable renderer's surface+topology view (COMPLETE — no
vibecomfy/executor/core.py:1210:        lenses=("surface", "topology"),
vibecomfy/executor/core.py:1486:    # surface + diff(Δ) + topology — the complete Python view, what changed
vibecomfy/executor/contracts.py:1981:    ``disposition`` is internal execution metadata. It is intentionally omitted
vibecomfy/executor/lookup_tools.py:73:# oversized template cannot blow out an agent context window.
tests/test_live_agentic_assessor_score_honesty.py:372:    oversized model_request.json containing a forbidden substring must NOT
tests/test_live_agentic_runner_persistence.py:677:def test_transport_omitted_resolves_to_openrouter_default_not_ambient_native(
tests/test_live_agentic_intent_judge_schema_context.py:905:    output — a STRICT SUBSET of the reply's lens set (surface+diff+topology)
tests/test_porting_ui_emitter.py:3125:    # Canonical uid stamped even though the captured payload omitted it
tests/test_porting_edit_resolve.py:7:- the refusal is identical whether ``sources=`` is omitted, empty, or
tests/test_porting_edit_resolve.py:133:    The statement fails closed identically whether sources= is omitted,
tests/test_porting_edit_resolve.py:163:    def test_resolve_omitted_sources_research_only_defaults_to_fail_closed(
tests/test_porting_edit_resolve.py:183:    def test_resolve_omitted_sources_adapt_defaults_to_fail_closed(self) -> None:
tests/test_porting_edit_resolve.py:189:    def test_resolve_omitted_sources_ignores_distilled_faster_brief_workflows(
tests/test_executor_contracts.py:135:        # Absent -> None (provider applies its default); omitted from to_dict.
tests/test_porting_edit_session.py:2034:    def test_apply_batch_rejects_unbounded_or_oversized_for(self) -> None:
tests/structural_harness/actors_reorganise.py:169:        "acceptably close: sensible stage groups, no oversized top-left slab, "
tests/test_agent_obligation_ledger.py:897:    def test_empty_evidence_omitted(self) -> None:
tests/test_headless_agent_artifacts.py:276:def test_malformed_json_artifact_body_is_omitted(tmp_path: Path) -> None:
tests/test_headless_agent_artifacts.py:302:def test_malformed_jsonl_artifact_body_is_omitted(tmp_path: Path) -> None:
tests/security/test_agent_generated_loader.py:110:def test_oversized_source_is_load_python_failure(monkeypatch: pytest.MonkeyPatch) -> None:
tests/test_m1_contracts.py:147:    omitted = json.loads(json.dumps(graph))
tests/test_m1_contracts.py:148:    omitted["nodes"][0].pop("widgets_values", None)
tests/test_m1_contracts.py:149:    variants.append(projection_reference_v1(omitted, "structural_v1")["digest"])
tests/test_generated_node_wrappers.py:43:def test_generated_wrapper_requires_context_when_workflow_omitted() -> None:
tests/test_generated_node_wrappers.py:59:def test_generated_wrapper_annotations_use_literal_and_omitted_sentinel() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:4893:def test_build_batch_messages_conversation_memory_omitted_on_later_turns() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:9544:    # omitted because ComfyUI may drop it after configure/decorate while the
tests/test_templates_module.py:708:    """T4(b): metadata output_prefix reaches finalized output when filename_prefix omitted."""
tests/live_agentic_harness/intent_judge.py:30:# the ceiling (surface + diff + topology); the judge requests a STRICT SUBSET
tests/live_agentic_harness/intent_judge.py:34:_REPLY_LENS_SET: tuple[str, ...] = ("surface", "diff", "topology")
tests/live_agentic_harness/intent_judge.py:721:    (``surface`` + ``diff`` + ``topology``) and the render boundary ENFORCES
tests/test_reorganise_projection.py:206:    assert "omitted: 5 canonical refs; see scope summaries below" in result.text
tests/test_reorganise_projection.py:207:    assert "omitted: 6 node furniture facts" in result.text
tests/test_reorganise_projection.py:208:    assert "omitted: 5 canonical refs in this scope" in result.text
tests/test_comfy_nodes_agent_hivemind_feedback.py:211:def test_submit_rejects_oversized_zip_before_transport() -> None:
tests/test_comfy_nodes_agent_edit.py:109:    assert "195 more node type names omitted" in formatted
tests/test_comfy_nodes_agent_edit.py:2700:    assert "if sources are omitted it searches internal workflows/templates only" not in system
tests/test_comfy_nodes_agent_edit.py:4822:    assert "workflow_schema_omitted" not in request_text
tests/test_comfy_nodes_agent_edit.py:4825:    assert "research_sources_omitted" not in request_text
tests/test_comfy_nodes_agent_edit.py:5776:    assert "If sources are omitted on this informational route" not in system_prompt
tests/test_comfy_nodes_agent_edit.py:12826:    oversized_result = routes._handle_agent_edit_chat(
tests/test_comfy_nodes_agent_edit.py:12835:    assert oversized_result["ok"] is True
tests/test_comfy_nodes_agent_edit.py:12836:    assert oversized_result["outcome"]["kind"] == "noop"
tests/test_comfy_nodes_agent_edit.py:12837:    assert len(oversized_result["messages"]) == 50
tests/test_comfy_nodes_agent_edit.py:15242:        assert "if sources are omitted" not in system
tests/test_comfy_nodes_agent_edit.py:15325:        assert "If sources are omitted on this informational route" not in system
tests/test_comfy_nodes_agent_edit.py:15441:    def test_precedent_adaptation_block_never_rendered(self) -> None:
tests/test_comfy_nodes_agent_edit.py:17098:            "omitted" in str(v) for v in manifest_nodes
tests/test_layout_delta.py:602:def test_added_node_is_snapshot_absent_and_omitted():
tests/test_layout_delta.py:612:    # New node is snapshot-absent → must be omitted
tests/test_layout_delta.py:616:def test_removed_node_omitted_from_delta():
tests/test_layout_delta.py:617:    """A node removed from the IR after snapshot is omitted from delta.
tests/test_layout_delta.py:635:def test_snapshot_absent_node_omitted_matches_add_semantics():
tests/test_coverage_policy.py:11:    omitted_paths = coverage_run.get("omit", [])
tests/test_coverage_policy.py:14:    assert "vibecomfy/comfy_nodes/*" not in omitted_paths
tests/test_live_agentic_harness_guard_contract.py:735:def test_agentic_guard_ignores_oversized_model_request(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:739:    output_dir = tmp_path / "oversized-model-request"
tests/test_live_agentic_harness_guard_contract.py:756:        "id": "oversized-model-request",
tests/browser/m1_contracts.test.mjs:124:test("zero-widget nodes normalize omitted, null, object, and array encodings", () => {
tests/test_executor_flows.py:5172:def test_batch12_classify_gets_census_only_and_reply_gets_surface_diff_topology(
tests/test_executor_flows.py:5178:    surface + diff(Δ) + topology (complete, with link ids) — never the
tests/test_executor_flows.py:5226:    # ── reply: surface + diff(Δ) + topology (complete, link ids) ──────────
tests/test_agent_tool_surface.py:835:        assert "if sources are omitted" not in system
tests/test_agent_tool_surface.py:899:    def test_evidence_ledger_block_omitted_when_empty(self) -> None:
tests/browser/active_row_rendering.test.mjs:973:      message: "LTX Video supports i2v with up to 768px resolution. PIL can be omitted.",
tests/test_intent_nodes.py:557:            id="oversized-source",
tests/test_intent_nodes.py:569:            id="oversized-spec",
tests/browser/harness.mjs:837:      // value even when the factory's minimal original shape omitted the key.
tests/test_ir_laws.py:1173:    reply_lenses = ("surface", "diff", "topology")
tests/test_ir_laws.py:1202:            lenses=("surface", "topology"),
tests/test_ir_laws.py:1272:    for lens in ("census", "surface", "topology", "diff"):
tests/test_ir_laws.py:1276:        lenses=("census", "surface", "diff", "topology"),
tests/browser/agent_edit_lifecycle.test.mjs:1223:    // requestScopeId intentionally omitted
tests/browser/agent_edit_lifecycle.test.mjs:1250:    // candidateSessionId intentionally omitted
tests/browser/agent_edit_lifecycle.test.mjs:2519:test("SYNC_BASELINE with omitted payload defaults to empty object and returns render:true", () => {
tests/browser/roundtrip_smoke.test.mjs:715:test("submitRating rejects oversized debug pack before posting rating payload", async () => {
tests/browser/roundtrip_smoke.test.mjs:3865:    // Deliberately no runtimeDependencies: legacy chat projections omitted it.
tests/browser/roundtrip_smoke.test.mjs:17574:test("VibeComfy comfy_adapter resolves semantic fields across auxiliary native widgets omitted from serialized inputs", async () => {
tests/fixtures/node_resolution/ideogram4_t2i.expected_emit.py:12:    definitions={'subgraphs': [{'id': '83e6e004-48ea-408e-9024-eb49c3d7dc14', 'version': 1, 'state': {'lastGroupId': 9, 'lastNodeId': 176, 'lastLinkId': 252, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': 'Text to Image (Ideogram v4)', 'inputNode': {'id': -10, 'bounding': [3490, 920, 154.921875, 228]}, 'outputNode': {'id': -20, 'bounding': [6850, 936, 128, 68]}, 'inputs': [{'id': '4bc742d1-7b4b-452c-90d9-0d76ebcdae76', 'name': 'text', 'type': 'STRING', 'linkIds': [152], 'label': 'prompt', 'pos': [3620.921875, 944]}, {'id': '8d4038eb-73c7-45e9-bba1-f068f55e8d32', 'name': 'value', 'type': 'INT', 'linkIds': [153], 'label': 'width', 'pos': [3620.921875, 964]}, {'id': '281550e6-6acf-4cbe-aec1-9eb803b4dec1', 'name': 'value_1', 'type': 'INT', 'linkIds': [154], 'label': 'height', 'pos': [3620.921875, 984]}, {'id': 'fae56884-2f1a-470b-a25f-40e7a87ef69d', 'name': 'noise_seed', 'type': 'INT', 'linkIds': [155], 'pos': [3620.921875, 1004]}, {'id': '3497309c-a7d7-4e28-9330-142c15881632', 'name': 'unet_name', 'type': 'COMBO', 'linkIds': [156], 'pos': [3620.921875, 1024]}, {'id': 'e87126db-7147-465e-b129-370ed2c6cc22', 'name': 'clip_name', 'type': 'COMBO', 'linkIds': [157], 'pos': [3620.921875, 1044]}, {'id': 'a1e6c080-b11b-4d5c-a3a8-fcf4df654cf7', 'name': 'vae_name', 'type': 'COMBO', 'linkIds': [158], 'pos': [3620.921875, 1064]}, {'id': 'b0d16516-95de-44d9-bea8-3cd2e7c78e9a', 'name': 'unet_name_1', 'type': 'COMBO', 'linkIds': [216], 'label': 'unconditional_unet', 'pos': [3620.921875, 1084]}, {'id': '249fd825-e6b3-489d-a341-6d8050500f5e', 'name': 'choice', 'type': 'COMBO', 'linkIds': [219], 'label': 'mode', 'pos': [3620.921875, 1104]}], 'outputs': [{'id': 'b81e4f60-e543-4f02-875b-b0f1bdc274f2', 'name': 'IMAGE', 'type': 'IMAGE', 'linkIds': [25], 'localized_name': 'IMAGE', 'pos': [6874, 960]}], 'widgets': [], 'nodes': [{'id': 9, 'type': 'VAELoader', 'pos': [4730, 1220], 'size': [470, 110], 'flags': {}, 'order': 1, 'mode': 0, 'inputs': [{'localized_name': 'vae_name', 'name': 'vae_name', 'type': 'COMBO', 'widget': {'name': 'vae_name'}, 'link': 158}], 'outputs': [{'localized_name': 'VAE', 'name': 'VAE', 'type': 'VAE', 'links': [17]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'VAELoader', 'models': [{'name': 'flux2-vae.safetensors', 'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors', 'directory': 'vae'}]}, 'widgets_values': ['flux2-vae.safetensors']}, {'id': 10, 'type': 'ConditioningZeroOut', 'pos': [5450, 960], 'size': [250, 80], 'flags': {'collapsed': False}, 'order': 2, 'mode': 0, 'inputs': [{'localized_name': 'conditioning', 'name': 'conditioning', 'type': 'CONDITIONING', 'link': 8}], 'outputs': [{'localized_name': 'CONDITIONING', 'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [214]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.9.1', 'Node name for S&R': 'ConditioningZeroOut'}, 'widgets_values': []}, {'id': 11, 'type': 'EmptyFlux2LatentImage', 'pos': [5330, 1180], 'size': [270, 170], 'flags': {}, 'order': 3, 'mode': 0, 'inputs': [{'localized_name': 'width', 'name': 'width', 'type': 'INT', 'widget': {'name': 'width'}, 'link': 33}, {'localized_name': 'height', 'name': 'height', 'type': 'INT', 'widget': {'name': 'height'}, 'link': 36}], 'outputs': [{'localized_name': 'LATENT', 'name': 'LATENT', 'type': 'LATENT', 'links': [15]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'EmptyFlux2LatentImage'}, 'widgets_values': [1024, 1024, 1]}, {'id': 12, 'type': 'SamplerCustomAdvanced', 'pos': [6160, 500], 'size': [290, 170], 'flags': {}, 'order': 4, 'mode': 0, 'inputs': [{'localized_name': 'noise', 'name': 'noise', 'type': 'NOISE', 'link': 11}, {'localized_name': 'guider', 'name': 'guider', 'type': 'GUIDER', 'link': 215}, {'localized_name': 'sampler', 'name': 'sampler', 'type': 'SAMPLER', 'link': 13}, {'localized_name': 'sigmas', 'name': 'sigmas', 'type': 'SIGMAS', 'link': 14}, {'localized_name': 'latent_image', 'name': 'latent_image', 'type': 'LATENT', 'link': 15}], 'outputs': [{'localized_name': 'output', 'name': 'output', 'type': 'LATENT', 'links': [16]}, {'localized_name': 'denoised_output', 'name': 'denoised_output', 'type': 'LATENT', 'links': []}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'SamplerCustomAdvanced'}, 'widgets_values': []}, {'id': 13, 'type': 'VAEDecode', 'pos': [6560, 500], 'size': [230, 100], 'flags': {}, 'order': 5, 'mode': 0, 'inputs': [{'localized_name': 'samples', 'name': 'samples', 'type': 'LATENT', 'link': 16}, {'localized_name': 'vae', 'name': 'vae', 'type': 'VAE', 'link': 17}], 'outputs': [{'localized_name': 'IMAGE', 'name': 'IMAGE', 'type': 'IMAGE', 'slot_index': 0, 'links': [25]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'VAEDecode'}, 'widgets_values': []}, {'id': 16, 'type': 'KSamplerSelect', 'pos': [5790, 1100], 'size': [270, 110], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [{'localized_name': 'SAMPLER', 'name': 'SAMPLER', 'type': 'SAMPLER', 'links': [13]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'KSamplerSelect'}, 'widgets_values': ['euler']}, {'id': 17, 'type': 'Ideogram4Scheduler', 'pos': [5790, 1260], 'size': [270, 240], 'flags': {}, 'order': 7, 'mode': 0, 'inputs': [{'localized_name': 'steps', 'name': 'steps', 'type': 'INT', 'widget': {'name': 'steps'}, 'link': 207}, {'localized_name': 'width', 'name': 'width', 'type': 'INT', 'widget': {'name': 'width'}, 'link': 34}, {'localized_name': 'height', 'name': 'height', 'type': 'INT', 'widget': {'name': 'height'}, 'link': 37}, {'localized_name': 'mu', 'name': 'mu', 'type': 'FLOAT', 'widget': {'name': 'mu'}, 'link': 208}, {'localized_name': 'std', 'name': 'std', 'type': 'FLOAT', 'widget': {'name': 'std'}, 'link': 209}], 'outputs': [{'localized_name': 'SIGMAS', 'name': 'SIGMAS', 'type': 'SIGMAS', 'links': [14]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'Ideogram4Scheduler'}, 'widgets_values': [20, 1024, 1024, 0.5, 1.75]}, {'id': 18, 'type': 'RandomNoise', 'pos': [5780, 490], 'size': [270, 110], 'flags': {}, 'order': 8, 'mode': 0, 'inputs': [{'localized_name': 'noise_seed', 'name': 'noise_seed', 'type': 'INT', 'widget': {'name': 'noise_seed'}, 'link': 155}], 'outputs': [{'localized_name': 'NOISE', 'name': 'NOISE', 'type': 'NOISE', 'links': [11]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'RandomNoise'}, 'widgets_values': [885894517601261, 'randomize']}, {'id': 23, 'type': 'UNETLoader', 'pos': [4720, 520], 'size': [470, 170], 'flags': {}, 'order': 9, 'mode': 0, 'showAdvanced': True, 'inputs': [{'localized_name': 'unet_name', 'name': 'unet_name', 'type': 'COMBO', 'widget': {'name': 'unet_name'}, 'link': 156}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [222]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'UNETLoader', 'models': [{'name': 'ideogram4_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/diffusion_models/ideogram4_fp8_scaled.safetensors', 'directory': 'diffusion_models'}]}, 'widgets_values': ['ideogram4_fp8_scaled.safetensors', 'default']}, {'id': 24, 'type': 'CLIPTextEncode', 'pos': [5270, 500], 'size': [430, 420], 'flags': {}, 'order': 10, 'mode': 0, 'inputs': [{'localized_name': 'clip', 'name': 'clip', 'type': 'CLIP', 'link': 24}, {'localized_name': 'text', 'name': 'text', 'type': 'STRING', 'widget': {'name': 'text'}, 'link': 152}], 'outputs': [{'localized_name': 'CONDITIONING', 'name': 'CONDITIONING', 'type': 'CONDITIONING', 'slot_index': 0, 'links': [8, 213]}], 'title': 'CLIP Text Encode (Positive Prompt)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'CLIPTextEncode'}, 'widgets_values': ['{\n    "high_level_description": "A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling \'COMFY\'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying an effortless, cozy vibe.",\n    "style_description": {\n        "aesthetics": "Retro magazine cutout style, mixed-media digital collage, high-contrast streetwear graphic, featuring rough ripped paper edges and distressed grunge textures.",\n        "lighting": "High-contrast flash mixed with harsh midday sunlight on the skater cutout, contrasting with flat, bright graphic lighting on the 3D typography.",\n        "photo": "Vintage grainy 35mm film with distressed halftone scan textures and subtle light leaks.",\n        "medium": "Mixed-media digital collage",\n        "color_palette": ["#1E73BE", "#FDFDFD", "#C82A2A", "#657C9C", "#EFEFEF"]\n    },\n    "compositional_deconstruction": {\n        "background": "A vibrant, clear blue sky layered with a vintage grainy film texture and subtle halftone dot patterns, transitioning down to an implied pale gray concrete ramp at the very bottom edge.",\n        "elements": [\n            {\n                "type": "obj",\n                "bbox": [128, 149, 354, 810],\n                "desc": "Massive 3D puffy, inflatable white typography spelling \'COMFY\'. The letters stretch across the upper half of the canvas, acting as a surreal, soft cloud-like backdrop.",\n                "color_palette": ["#FDFDFD", "#E0E0E0", "#D3DBE2"]\n            },\n            {\n                "type": "obj",\n                "bbox": [459, 37, 727, 264],\n                "desc": "A cluster of oversized, distressed red stamped circles and dots, applied loosely to the midground like a grunge ink stamp, partially obscuring the bottom left of the text.",\n                "color_palette": ["#C82A2A", "#A11D1D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [23, 366, 153, 666],\n                "desc": "A vertically oriented, torn paper side banner pinned to the left edge. The rough-edged paper displays the bold, stamped text \'STAY COZY\' in high-contrast black ink.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [287, 210, 756, 819],\n                "desc": "A sharp photographic cutout of a skateboarder mid-air in a relaxed pose. He wears loose-fitting washed denim jeans and a plain white tee, appearing to effortlessly float above the concrete ramp. A distinct white cutout border surrounds his silhouette.",\n                "color_palette": ["#FDFDFD", "#657C9C", "#2B2B2B", "#DCA57D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [773, 39, 973, 187],\n                "desc": "A surreal, miniature floating skateboard cutout, positioned playfully in the upper right sky as if defying gravity.",\n                "color_palette": ["#D2A679", "#2B2B2B", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [105, 830, 905, 980],\n                "desc": "A wide, horizontal strip of heavily textured torn paper spanning the lower third of the composition. It features the bold typographic phrase \'BEYOND THE COMFORT ZONE\' intermixed with \'EFFORTLESS RIDE\' alongside ripped edges that reveal the background.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#999999"]\n            }\n        ]\n    }\n}']}, {'id': 14, 'type': 'CLIPLoader', 'pos': [4730, 990], 'size': [470, 170], 'flags': {}, 'order': 6, 'mode': 0, 'inputs': [{'localized_name': 'clip_name', 'name': 'clip_name', 'type': 'COMBO', 'widget': {'name': 'clip_name'}, 'link': 157}], 'outputs': [{'localized_name': 'CLIP', 'name': 'CLIP', 'type': 'CLIP', 'links': [24]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'CLIPLoader', 'models': [{'name': 'qwen3vl_8b_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors', 'directory': 'text_encoders'}]}, 'widgets_values': ['qwen3vl_8b_fp8_scaled.safetensors', 'ideogram4', 'default']}, {'id': 27, 'type': 'PrimitiveInt', 'pos': [4240, 1610], 'size': [270, 110], 'flags': {}, 'order': 11, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'INT', 'widget': {'name': 'value'}, 'link': 153}], 'outputs': [{'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [32]}], 'title': 'Int (Width)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveInt'}, 'widgets_values': [1024, 'fixed']}, {'id': 28, 'type': 'PrimitiveInt', 'pos': [4250, 1800], 'size': [270, 110], 'flags': {}, 'order': 12, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'INT', 'widget': {'name': 'value'}, 'link': 154}], 'outputs': [{'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [35]}], 'title': 'Int (Height)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveInt'}, 'widgets_values': [1024, 'fixed']}, {'id': 31, 'type': 'ComfyMathExpression', 'pos': [5340, 1400], 'size': [230, 80], 'flags': {'collapsed': True}, 'order': 13, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 32}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [33, 34]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 32, 'type': 'ComfyMathExpression', 'pos': [5350, 1470], 'size': [230, 80], 'flags': {'collapsed': True}, 'order': 14, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 35}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [36, 37]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 144, 'type': 'ComfyNumberConvert', 'pos': [5920, 1870], 'size': [230, 100], 'flags': {}, 'order': 15, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 195}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': [208]}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 145, 'type': 'JsonExtractString', 'pos': [5450, 1870], 'size': [400, 200], 'flags': {}, 'order': 16, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 196}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [195]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'mu']}, {'id': 146, 'type': 'ComfyNumberConvert', 'pos': [5930, 2110], 'size': [230, 100], 'flags': {}, 'order': 17, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 197}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': [209]}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 147, 'type': 'JsonExtractString', 'pos': [5010, 1630], 'size': [410, 470], 'flags': {}, 'order': 18, 'mode': 0, 'inputs': [{'localized_name': 'key', 'name': 'key', 'type': 'STRING', 'widget': {'name': 'key'}, 'link': 218}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [199]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['{\n  "Quality": {\n    "num_steps": 48,\n    "mu": 0.0,\n    "std": 1.5,\n    "preset_id": "V4_QUALITY_48"\n  },\n  "Default": {\n    "num_steps": 20,\n    "mu": 0.0,\n    "std": 1.75,\n    "preset_id": "V4_DEFAULT_20"\n  },\n  "Turbo": {\n    "num_steps": 12,\n    "mu": 0.5,\n    "std": 1.75,\n    "preset_id": "V4_TURBO_12"\n  }\n}', 'Default']}, {'id': 148, 'type': 'StringReplace', 'pos': [5050, 2150], 'size': [230, 40], 'flags': {'collapsed': True}, 'order': 19, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 199}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [196, 200, 201]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', "'", '"']}, {'id': 149, 'type': 'JsonExtractString', 'pos': [5460, 1610], 'size': [400, 200], 'flags': {}, 'order': 20, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 200}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [202]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'num_steps']}, {'id': 150, 'type': 'JsonExtractString', 'pos': [5450, 2110], 'size': [400, 200], 'flags': {}, 'order': 21, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 201}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [197]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'std']}, {'id': 151, 'type': 'ComfyNumberConvert', 'pos': [5920, 1620], 'size': [230, 100], 'flags': {}, 'order': 22, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 202}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': []}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [207]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 154, 'type': 'UNETLoader', 'pos': [4730, 740], 'size': [470, 170], 'flags': {}, 'order': 23, 'mode': 0, 'showAdvanced': True, 'inputs': [{'localized_name': 'unet_name', 'name': 'unet_name', 'type': 'COMBO', 'widget': {'name': 'unet_name'}, 'link': 216}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [211]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'UNETLoader', 'models': [{'name': 'ideogram4_unconditional_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors', 'directory': 'diffusion_models'}]}, 'widgets_values': ['ideogram4_unconditional_fp8_scaled.safetensors', 'default']}, {'id': 155, 'type': 'DualModelGuider', 'pos': [5790, 870], 'size': [270, 180], 'flags': {}, 'order': 24, 'mode': 0, 'inputs': [{'localized_name': 'model', 'name': 'model', 'type': 'MODEL', 'link': 223}, {'localized_name': 'positive', 'name': 'positive', 'type': 'CONDITIONING', 'link': 213}, {'localized_name': 'model_negative', 'name': 'model_negative', 'shape': 7, 'type': 'MODEL', 'link': 211}, {'localized_name': 'negative', 'name': 'negative', 'shape': 7, 'type': 'CONDITIONING', 'link': 214}], 'outputs': [{'localized_name': 'GUIDER', 'name': 'GUIDER', 'type': 'GUIDER', 'links': [215]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'DualModelGuider'}, 'widgets_values': [7]}, {'id': 156, 'type': 'CustomCombo', 'pos': [4720, 1630], 'size': [270, 280], 'flags': {}, 'order': 25, 'mode': 0, 'inputs': [{'localized_name': 'choice', 'name': 'choice', 'type': 'COMBO', 'widget': {'name': 'choice'}, 'link': 219}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [218]}, {'localized_name': 'INDEX', 'name': 'INDEX', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'CustomCombo'}, 'widgets_values': ['Default', 1, 'Quality', 'Default', 'Turbo', '']}, {'id': 157, 'type': 'CFGOverride', 'pos': [5790, 650], 'size': [260, 170], 'flags': {}, 'order': 26, 'mode': 0, 'inputs': [{'localized_name': 'model', 'name': 'model', 'type': 'MODEL', 'link': 222}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [223]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'CFGOverride'}, 'widgets_values': [3, 0.7, 1]}], 'groups': [{'id': 1, 'title': 'Models', 'bounding': [4700, 420, 530, 1100], 'color': '#3f789e', 'flags': {}}, {'id': 2, 'title': 'Latent Size', 'bounding': [5260, 1080, 450, 440], 'color': '#3f789e', 'flags': {}}, {'id': 3, 'title': 'Sampling', 'bounding': [5740, 420, 780, 1100], 'color': '#3f789e', 'flags': {}}, {'id': 4, 'title': 'Prompt', 'bounding': [5260, 420, 450, 640], 'color': '#3f789e', 'flags': {}}, {'id': 5, 'title': 'Image Size', 'bounding': [4130, 1540, 530, 420], 'color': '#3f789e', 'flags': {}}, {'id': 9, 'title': 'Preset', 'bounding': [4700, 1540, 1820, 780], 'color': '#3f789e', 'flags': {}}], 'links': [{'id': 8, 'origin_id': 24, 'origin_slot': 0, 'target_id': 10, 'target_slot': 0, 'type': 'CONDITIONING'}, {'id': 33, 'origin_id': 31, 'origin_slot': 1, 'target_id': 11, 'target_slot': 0, 'type': 'INT'}, {'id': 36, 'origin_id': 32, 'origin_slot': 1, 'target_id': 11, 'target_slot': 1, 'type': 'INT'}, {'id': 11, 'origin_id': 18, 'origin_slot': 0, 'target_id': 12, 'target_slot': 0, 'type': 'NOISE'}, {'id': 13, 'origin_id': 16, 'origin_slot': 0, 'target_id': 12, 'target_slot': 2, 'type': 'SAMPLER'}, {'id': 14, 'origin_id': 17, 'origin_slot': 0, 'target_id': 12, 'target_slot': 3, 'type': 'SIGMAS'}, {'id': 15, 'origin_id': 11, 'origin_slot': 0, 'target_id': 12, 'target_slot': 4, 'type': 'LATENT'}, {'id': 16, 'origin_id': 12, 'origin_slot': 0, 'target_id': 13, 'target_slot': 0, 'type': 'LATENT'}, {'id': 17, 'origin_id': 9, 'origin_slot': 0, 'target_id': 13, 'target_slot': 1, 'type': 'VAE'}, {'id': 34, 'origin_id': 31, 'origin_slot': 1, 'target_id': 17, 'target_slot': 1, 'type': 'INT'}, {'id': 37, 'origin_id': 32, 'origin_slot': 1, 'target_id': 17, 'target_slot': 2, 'type': 'INT'}, {'id': 24, 'origin_id': 14, 'origin_slot': 0, 'target_id': 24, 'target_slot': 0, 'type': 'CLIP'}, {'id': 32, 'origin_id': 27, 'origin_slot': 0, 'target_id': 31, 'target_slot': 0, 'type': 'INT'}, {'id': 35, 'origin_id': 28, 'origin_slot': 0, 'target_id': 32, 'target_slot': 0, 'type': 'INT'}, {'id': 25, 'origin_id': 13, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'IMAGE'}, {'id': 152, 'origin_id': -10, 'origin_slot': 0, 'target_id': 24, 'target_slot': 1, 'type': 'STRING'}, {'id': 153, 'origin_id': -10, 'origin_slot': 1, 'target_id': 27, 'target_slot': 0, 'type': 'INT'}, {'id': 154, 'origin_id': -10, 'origin_slot': 2, 'target_id': 28, 'target_slot': 0, 'type': 'INT'}, {'id': 155, 'origin_id': -10, 'origin_slot': 3, 'target_id': 18, 'target_slot': 0, 'type': 'INT'}, {'id': 156, 'origin_id': -10, 'origin_slot': 4, 'target_id': 23, 'target_slot': 0, 'type': 'COMBO'}, {'id': 157, 'origin_id': -10, 'origin_slot': 5, 'target_id': 14, 'target_slot': 0, 'type': 'COMBO'}, {'id': 158, 'origin_id': -10, 'origin_slot': 6, 'target_id': 9, 'target_slot': 0, 'type': 'COMBO'}, {'id': 195, 'origin_id': 145, 'origin_slot': 0, 'target_id': 144, 'target_slot': 0, 'type': 'STRING'}, {'id': 196, 'origin_id': 148, 'origin_slot': 0, 'target_id': 145, 'target_slot': 0, 'type': 'STRING'}, {'id': 197, 'origin_id': 150, 'origin_slot': 0, 'target_id': 146, 'target_slot': 0, 'type': 'STRING'}, {'id': 199, 'origin_id': 147, 'origin_slot': 0, 'target_id': 148, 'target_slot': 0, 'type': 'STRING'}, {'id': 200, 'origin_id': 148, 'origin_slot': 0, 'target_id': 149, 'target_slot': 0, 'type': 'STRING'}, {'id': 201, 'origin_id': 148, 'origin_slot': 0, 'target_id': 150, 'target_slot': 0, 'type': 'STRING'}, {'id': 202, 'origin_id': 149, 'origin_slot': 0, 'target_id': 151, 'target_slot': 0, 'type': 'STRING'}, {'id': 207, 'origin_id': 151, 'origin_slot': 1, 'target_id': 17, 'target_slot': 0, 'type': 'INT'}, {'id': 208, 'origin_id': 144, 'origin_slot': 0, 'target_id': 17, 'target_slot': 3, 'type': 'FLOAT'}, {'id': 209, 'origin_id': 146, 'origin_slot': 0, 'target_id': 17, 'target_slot': 4, 'type': 'FLOAT'}, {'id': 211, 'origin_id': 154, 'origin_slot': 0, 'target_id': 155, 'target_slot': 2, 'type': 'MODEL'}, {'id': 213, 'origin_id': 24, 'origin_slot': 0, 'target_id': 155, 'target_slot': 1, 'type': 'CONDITIONING'}, {'id': 214, 'origin_id': 10, 'origin_slot': 0, 'target_id': 155, 'target_slot': 3, 'type': 'CONDITIONING'}, {'id': 215, 'origin_id': 155, 'origin_slot': 0, 'target_id': 12, 'target_slot': 1, 'type': 'GUIDER'}, {'id': 216, 'origin_id': -10, 'origin_slot': 7, 'target_id': 154, 'target_slot': 0, 'type': 'COMBO'}, {'id': 218, 'origin_id': 156, 'origin_slot': 0, 'target_id': 147, 'target_slot': 0, 'type': 'STRING'}, {'id': 219, 'origin_id': -10, 'origin_slot': 8, 'target_id': 156, 'target_slot': 0, 'type': 'COMBO'}, {'id': 222, 'origin_id': 23, 'origin_slot': 0, 'target_id': 157, 'target_slot': 0, 'type': 'MODEL'}, {'id': 223, 'origin_id': 157, 'origin_slot': 0, 'target_id': 155, 'target_slot': 0, 'type': 'MODEL'}], 'extra': {}}, {'id': 'f5f04613-ee09-4cd9-9ada-a880360891d4', 'version': 1, 'state': {'lastGroupId': 9, 'lastNodeId': 176, 'lastLinkId': 252, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': 'Ideogram4 Caption Prompt Template', 'inputNode': {'id': -10, 'bounding': [4830, 2840, 128, 108]}, 'outputNode': {'id': -20, 'bounding': [6270, 2700, 128, 68]}, 'inputs': [{'id': 'b96a4263-d942-4b93-9225-03d8aff697ed', 'name': 'value', 'type': 'STRING', 'linkIds': [180], 'label': 'user_prompt', 'pos': [4934, 2864]}, {'id': '1292f2e8-bc8b-4896-956a-77cbfe7f7482', 'name': 'source', 'type': '*', 'linkIds': [234], 'label': 'width', 'pos': [4934, 2884]}, {'id': '52396a95-c41b-4e06-94be-b6000d977bec', 'name': 'source_1', 'type': '*', 'linkIds': [236], 'label': 'height', 'pos': [4934, 2904]}], 'outputs': [{'id': '6527ba64-e7bb-474f-b015-bd6931e990ca', 'name': 'STRING', 'type': 'STRING', 'linkIds': [247], 'pos': [6294, 2724]}], 'widgets': [], 'nodes': [{'id': 114, 'type': 'PrimitiveStringMultiline', 'pos': [5070, 2580], 'size': [430, 520], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [228]}], 'title': 'System Prompt', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveStringMultiline'}, 'widgets_values': ['[META]\nfrozen: false\ndescription: Slim single-shot magic prompt — splatter planning + v15 output discipline, deduped for faster inference. Thinking off.\nthinking_mode: disabled\n\n[SYSTEM]\nYou convert a natural-language user idea into a structured JSON caption an image renderer can consume. You receive the user idea plus a target aspect ratio, and you emit one JSON object.\n\n## OUTPUT CONTRACT — exactly three top-level keys, in this order:\n\n```json\n{"aspect_ratio":"W:H","high_level_description":"...","compositional_deconstruction":{"background":"...","elements":[ ... ]}}\n```\n\n- Emit a SINGLE-LINE MINIFIED JSON object — no markdown fences, no commentary, no other top-level keys.\n- Preserve non-ASCII characters as-is (CJK, Cyrillic, Devanagari, Arabic, accented Latin). Never escape with `\\uNNNN`, transliterate, or replace `café` with `cafe`.\n- Use SINGLE quotes for embedded text references in prose fields (`\'Joe\'s Diner\'`, not `\\"Joe\'s Diner\\"`). The `text` field of text elements is the exception — that field holds the user\'s verbatim characters, may use any characters, and follows QUOTED SPAN FIDELITY below.\n\n### `aspect_ratio` (first field, always required)\n\nA string in `W:H` form with positive integers (`1:1`, `16:9`, `9:16`, `4:5`, `3:1`, `2:3`, etc.).\n- If the user message gives a concrete `W:H`, echo it verbatim.\n- If the user message says `auto`, pick a concrete ratio that matches the medium and composition (panoramic subjects → wide ratios like `16:9` or `3:1`; portrait subjects → tall like `9:16` or `4:5`; designed artifacts → format conventions like `2:3` book cover, `3:4` poster; ambiguous → `1:1`). NEVER emit the literal string `auto`.\n- The aspect ratio you commit to drives every bbox decision. Pick it first.\n\n### `high_level_description` — observational summary (50-word hard cap)\n\n- ONE long sentence preferred, never more than two.\n- Reads like a short natural-language prompt, not an analysis. Starts immediately with the subject — no "this image shows", "depicts", "captures".\n- Identifies subject(s), medium, and overall composition. Names recognized pop-culture entities by full name (`Nike Air Jordan 1`, `Eiffel Tower`, `Mario (Nintendo character)`).\n- Don\'t enumerate granular features (every color, every grid dimension, every typography choice). That detail belongs in element descs or `background`.\n- `various`, `multiple`, general categories ARE appropriate here. Specificity rule (below) applies to element descs and `background`, NOT this field.\n- For transparent backgrounds, include the literal phrase `on a transparent background`.\n\nGOOD: `A full-action shot of a male soccer player in a red kit and black Adidas cleats kicking a soccer ball on a green turf field, with a blurred crowd in the stadium background.`\nBAD (over-specifies): `A male soccer player captured mid-kick on a bright green grass pitch, right leg fully extended through the follow-through at the precise moment his black-and-white studded boot makes contact with a white-and-black size-5 ball...`\n\n## ELEMENTS — what they are, what they\'re not\n\nEach element is one of:\n```\n{"type":"obj","bbox":[y1,x1,y2,x2],"desc":"..."}\n{"type":"text","bbox":[y1,x1,y2,x2],"text":"LINE ONE\\nLINE TWO","desc":"..."}\n```\n\n`bbox` is optional per-element (see BBOX section below).\n\n### SINGLE SUBJECT = SINGLE ELEMENT\n\nA coherent subject — one animal, person, vehicle, building, plant, instrument, machine — is exactly ONE `obj` element. Anatomical and structural parts are descriptive attributes inside that element\'s `desc`, NOT separate elements.\n\nFORBIDDEN: a bee split into 8 elements (thorax/abdomen/wings/eyes/legs/...); a car split into 6 (body/wheels/windshield/...); a person split into 7 (head/torso/each limb/...); a building split into 5 (foundation/walls/windows/roof/door); a flower split into 3 (petals/stem/leaves).\n\nWhen MULTIPLE distinct subjects appear (a person AND a dog; two bees; three runners), use MULTIPLE elements — one per subject.\n\n**Test:** part-of-one-thing → goes in that thing\'s desc. Separate thing → its own element.\n\n**Transparent enclosure + featured contents = ONE element.** Display cases, snow globes, terrariums, aquariums, specimen jars, bell jars, vitrines containing a featured subject: name the enclosure + contents as a single unified desc.\n\n**Configured parts + revealed interior = ONE element.** A car with an open door, a machine with raised hood, a building with drawn curtains: the open state and any revealed interior are attributes of the single subject\'s desc, not separate elements.\n\n### Element desc — what to write (30–60 words, 60-word HARD CAP)\n\nIdentity first, then major attributes briefly, then one distinguishing detail if relevant. Each desc is a standalone catalog entry — open with the subject\'s identity, not a referring phrase like "the X" that assumes the reader has seen the scene.\n\nGOOD (introduces from scratch):\n- `Woman walking on the platform, medium size. Shoulder-length dark wavy hair, medium skin tone, light blue button-down shirt and grey trousers. Small bag slung over the right shoulder.`\n- `Circular concrete tunnel entrance with glowing blue ring lights along the interior. Train tracks lead directly into the dark opening.`\n\n**Major attributes — always name:**\n- People: skin tone, hair (color + style), each visible garment with color, expression/gaze, pose, distinguishing feature (mole, glasses, jewelry, held prop).\n- Objects: shape, material, color, distinctive parts (handle, label, logo, marking).\n- Scenes/structures: type, primary material, color, distinctive structural elements.\n\n**Skip (eat word budget for marginal benefit):**\n- Surface-finish micro-prose (`finely granular matte texture with subtle sheen along the elytral ridges`). Pick one short descriptor (matte/glossy/metallic/textured) or omit.\n- Pose mechanics per-limb. Pick ONE summary action phrase plus the major attributes.\n- Camera/shadow/lighting micro-detail per element. Belongs in `background`.\n- Fabric weave, skin texture nuances, micro-anatomy.\n\n### Element desc — what NOT to include\n\n**No shadows.** Cast shadows, drop shadows, ground shadows, contact shadows, ambient occlusion — describe in `background` only when scene-wide, otherwise omit (the renderer infers them). Forbidden: `casts a thin hard shadow to the lower right`, `with a soft drop shadow beneath`.\n\n**No camera or render language.** Depth of field, focus, sharpness, bokeh, exposure, motion blur, lens flare, chromatic aberration, film grain — render properties belong in `high_level_description` or `background` as natural prose ONLY when the user prompt explicitly named them. NEVER inside an obj desc.\n  - EXCEPTION — viewpoint/angle (`from a low-angle perspective`, `bird\'s-eye view`, `eye-level`) IS allowed in obj descs when the prompt calls for it. Place once, usually in the focal subject\'s desc or background.\n\n**No describing impressions instead of physical reality.** Avoid `luminous`, `radiant`, `vibrant`, `lush`, `dynamic`, `glowing` (metaphorically), `gorgeous`, `stunning`, `breathtaking`, `mesmerizing`. Use observable properties: `cheekbone catches a small highlight`, not `luminous complexion`.\n\n**No scene-context repetition per-element.** Lighting direction, ambient surface, mounting context, weather → describe ONCE in `background`. Each element\'s desc focuses on what\'s UNIQUE to that element.\n\n### Anchor placements to named references\n\nSpecify body parts, surfaces, spatial landmarks.\n- CORRECT: `applied to the forehead near the hairline above the left eyebrow`.\n- INCORRECT: `pressed against the skin`.\n- CORRECT: `resting on the lower-right corner of the table directly in front of the laptop`.\n- INCORRECT: `sitting on the surface`.\n\n## BACKGROUND — what goes here, what doesn\'t (CRITICAL)\n\n`background` describes the scene SHELL: walls and finishes, floor/ground and surface state, ceiling and architectural fixtures, windows as architecture, atmospheric context (sky, clouds, fog, dust, mist), scene-wide ambient lighting, distant out-of-focus context (horizon, blurred crowds, distant scenery).\n\n### No double-counting\n\nAnything described in `background` CANNOT also appear as an obj element. Each scene component lives in EXACTLY ONE field. Decide once and commit. Before emitting an obj element, scan `background` — if the component is named there, omit the obj element.\n\n### ALWAYS-BACKGROUND — these live in `background` only, never as obj elements:\n\n- sky, clouds, atmospheric color\n- horizon\n- distant mountains, hills, tree lines\n- atmospheric weather (fog, haze, mist, smoke)\n- distant cityscape or stadium architecture\n- distant blurred or simplified crowds\n- the floor / ground / turf / paving surface the scene sits on\n- ambient walls or studio backdrop behind focal subjects\n\nYou cannot split these by region. `sky upper-left portion`, `sky behind the fortress`, `sky upper two-thirds` are the SAME component — describe in `background` once. Same for crowd, ground, horizon.\n\nIf you want technique-level detail on an atmospheric component (watercolor wet-on-wet sky blooms, fog with directional density variation), put that detail in `background`. The `background` field is allowed to be long.\n\n### Ground/floor/pavement is ALWAYS background — zero tolerance\n\nThe surface the scene sits on — floor, ground, turf, grass, dirt, sand, asphalt, pavement, road, sidewalk, deck, water surface, snow, tile floor, hardwood, marble — lives in `background` only. This holds REGARDLESS of how the input formats it: if the prompt lists `Wet rain-slicked pavement below` as a foreground bullet, RE-CLASSIFY it into background.\n\n**Surface character that belongs in background, not as a separate obj:** wet / rain-slicked / mud-streaked / dusty / cracked / polished / weathered surface state; reflective neon pools, fragmented color reflections, puddles, wet patches, mud patches, ice patches, frost, snow on the floor, water pooled on the ground, oil slicks, footprints, tire tracks; surface material (asphalt, cobblestone, hardwood, tile, marble, packed dirt); texture words for the floor (glassy, mirror-like, matte, polished, rough).\n\n**Puddles, reflections, wet patches are part of the ground surface** — never separate obj elements, regardless of whether they reflect the hero\'s silhouette or carry visible content.\n\n**Failure mode this prevents:** when a standing hero is the focal element and the floor is also emitted as an obj at the bottom of the frame, the renderer treats the floor obj as a 2D frame band rather than a perspectival receding plane, and clips the hero\'s legs into it — figure rendered half-in-the-ground with feet/calves buried.\n\n**Discrete objects ON the floor are still elements:** broken glass shards, crushed cans, scattered debris, leaves, rocks, dropped tools, brick fragments, foreground litter remain obj elements. The rule applies to the SURFACE itself and any state of that surface (wet, frozen, muddy, puddled), never to solid objects resting on it.\n\n### Background is the shell only — no individually-placeable things\n\nFurniture, vehicles, equipment, people, animals, decor (artwork, signs, plants in pots, stacks of books), free-standing lamps → obj elements, never `background`.\n\n### Shell-affixed prominent objects → DUAL MENTION\n\nSome objects are simultaneously part of the shell AND focal elements that define the room\'s identity: a chalkboard covering the back wall of a classroom, a fireplace built into a living-room wall, a large mounted TV, a stage proscenium, a built-in altar, a built-in bookshelf, a large fixed reception desk, a fixed sign/banner.\n\nFor these, MANDATORY all three steps:\n1. **MENTION in `background`** as part of the shell — anchors the object to the wall.\n2. **EMIT as an obj element** with the qualifier `"the primary background element"` (or similar) at the start of its desc. The obj carries the detail (material, content, frame, mounting).\n3. **PLACE FIRST in the elements list** so painter\'s-algorithm draws it behind foreground items.\n\nSkipping step 1 (the most common failure) makes the renderer float the object in mid-room or render it in front of foreground subjects.\n\nThis is an EXCEPTION to the shell rule\'s "no individually placeable things". Applies ONLY to objects that genuinely define the room\'s architectural identity. Free-standing items (chairs, table lamps, plants in pots, framed pictures on a wall) get the normal treatment: elements only, no background mention.\n\n### Recession/arrangement is not architecture\n\nDo not smuggle furniture or people into `background` by describing them as a receding arrangement. Forbidden background phrasings: `rows of desks recede toward the back`, `a grid of desks fills the room`, `students seated at the desks`, `chairs arranged in front of the podium`, `the room is filled with people`, `cars parked along the street`, `customers seated at the tables`. The arrangement IS the foreground content — emit elements.\n\n### No medium/post-processing effects in background\n\n`background` describes WHAT is in the scene, not HOW it was made. Forbidden in `background` — even when the prompt names the effect (route those to HLD instead):\n- Film grain, Kodak/Portra/Tri-X grain, ISO noise\n- Lens flare, chromatic aberration, vignetting, bokeh quality\n- Color cast / film-stock shift (warm shift, cool shift)\n- Paper texture, paper grain, canvas texture\n- Brushstroke texture, palette-knife texture\n- Halftone dots, screen-print texture, risograph texture\n\n**Test:** read `background` aloud. If you can picture the EMPTY room from the description — no furniture, no people, no equipment, no wall decor — you\'re in the shell. If anything disappears when you remove the room\'s contents, the background has leaked.\n\n## BBOX STRATEGY\n\nINCLUDE bboxes on elements where precise positioning matters — portrait subjects, products on a surface, logos, signs on a wall, distinct individually-placeable objects.\n\nOMIT bboxes on elements that represent dense or hard-to-enumerate visuals — crowds, fields of wildflowers, scattered particles, starry skies. Per-element judgment.\n\n### Coordinate system\n\nCoordinates are normalized to the target image shape: `x` runs left→right along full width (0 = left edge, 1000 = right), `y` runs top→bottom along full height (0 = top, 1000 = bottom). Top-left origin. Format `[y1, x1, y2, x2]` with `y1 < y2`, `x1 < x2`.\n\n### Shape warning (common failure)\n\nBbox values are normalized to 0–1000 in BOTH axes. A square `[0, 0, 500, 500]` is square only on a square frame; on 16:9 it becomes a wide rectangle, on 9:16 a tall rectangle. Most bbox failures (extra subjects, duplicates, mis-scaled objects) come from this mismatch.\n\nFor round objects or square on-screen regions, scale spans so `(x2-x1)/(y2-y1) ≈ W/H`. For single-subject prompts on wide frames, prefer narrower x-spans. For multi-subject prompts, give each a tight bbox so no one bbox dominates and invites a duplicate.\n\n## SPECIFICITY — commit to one value\n\nThis JSON feeds a diffusion model. Leave nothing for the model to invent or choose.\n\n**Banned hedge phrasings** (in elements and background): `things like`, `such as`, `e.g.`, `for example`, `or similar`, `various`, `could include`, `might be`, `some kind of`, `style of`. Replace with concrete nouns, counts, colors, materials, poses.\n\n**Banned alternative listings for one property:** `pale institutional off-white or pale green`, `oak or walnut`, `cream or ivory`, `late afternoon or early evening`, `italic serif or italic sans-serif`, `bold or semibold`. Pick ONE and commit. `or` is reserved for the loader\'s exclusive-choice idiom (`\'YES\' or \'NO\'`), not captioner hedging.\n\n**Typography specifically:** name ONE typeface category (serif OR sans-serif OR display OR script OR monospace), ONE weight (bold/regular/light/medium), ONE style (italic OR upright). Never two joined by `or`.\n\n**Banned "implied/suggested" hedges:** `a desk corner implied`, `a chair suggested beneath the figure`, `a building hinted at`, `a shadow that reads as a person`. If it\'s in the scene, paint it concretely. If it isn\'t, leave it out. Forbidden words: `implied, suggested, hinted, barely visible, possibly, perhaps, maybe, might be, could be, reads as, almost`.\n\n**Exhaustive content preservation.** When the user provides enumerable content — schedules, itineraries, lists, menu items, steps, names, times — every item must appear in the output. Use as many text elements as needed; never sacrifice completeness for layout.\n\n**Named prompt elements MUST appear.** Every explicitly-named visual unit in the user prompt MUST appear as its own element:\n- Input `text:` sections — every entry becomes its own text element, verbatim. Zero tolerance: 3 entries in input → ≥3 text elements in output. Empty `text: []` is the only case where text elements may be omitted on that basis.\n- Quoted strings (single or double quotes) — each is its own text element.\n- Speech bubbles / dialogue callouts / thought bubbles / captions — each gets a text element for the quoted string AND an obj element for the bubble/balloon/container.\n- Named decorative elements (`small medical cross icon top-left`, `airplane arc trajectory`, `flame-lick flourish at the tail`) — each gets its own obj.\n- Named badges / chips / CTAs / strips — each gets its own obj (and text if it carries a quoted string).\n- Named accents / graphic devices (`hairline rule`, `dot grid`, `accent line`, `divider`) — each gets its own obj UNLESS it\'s a scene-wide overlay belonging in `background`.\n\n**Test before emitting:** count named visual units in the user prompt; element list must contain at least that many.\n\n**No placeholder enumeration.** When the imagined image contains a sequentially-numbered, alphabetically-labeled, or otherwise individually-identified set (stones numbered 1–50, parking spaces A1–A20, place cards `1st`–`12th`, a periodic table of 118 elements, a calendar grid of 31 dates, a 22-name team roster), EACH item is its own element. No `etc.`, no `and so on`, no `6 through 49`, no single obj grouping all into one cluster. List ALL of them.\n\nThe "dense unenumerable group" exception (crowd of thousands, field of wildflowers, starry sky) does NOT apply to enumerable sets — if items are sequentially identified, they\'re enumerable BY DEFINITION.\n\n**Don\'t invent visual concepts the user didn\'t ask for.** Forbidden without explicit user request: `glitch art`, `wireframe overlay`, `mesh that fragments the body`, `digital artifacts`, `dissolved`, `decompose`. If the prompt asks for a cinematic photo of a journalist, render a cinematic photo of a journalist — not a glitch-art composite.\n\n## PLANNING — turn the user idea into elements\n\n### 1. Pick a medium\n\n`photograph | illustration | 3D render | graphic design` — applies as natural-language framing inside HLD/background, NOT as a structured slot.\n\nDecision: **DESIGNED artifact vs CAPTURED / DRAWN / RENDERED moment.**\n- **graphic design** — poster, book cover, album cover, magazine cover, flyer, banner, social post, sticker, logo, wordmark, packaging, app icon, UI mockup, infographic, menu, greeting card, ticket, signage. If a human designer would sit at a desk to make it.\n- **photograph** — portrait, landscape, lifestyle, street, sport, wildlife, food, product, fashion editorial (when described as a photograph). Default for ambiguous everyday scenes.\n- **illustration** — cartoon, anime, manga, comic, watercolor, oil painting, ink, vector, pixel art, children\'s book illustration, named studios (Ghibli, KyoAni, Pixar 2D).\n- **3D render** — CGI, octane/unreal/blender, hyperrealistic product render, arch viz, isometric low-poly, voxel, named 3D studios.\n\nSilent / ambiguous → photograph (default). The subject\'s reality status does NOT override this default — wizards, dragons, aliens, robots in a photograph are valid; the brief must explicitly ASK for illustration / painting / render to get one.\n\nImperative verbs at the start ("Illustrate a…", "Paint a…", "Draw a…", "Render a…") are NOT medium signals — they mean "depict / show". Default to photograph unless an explicit medium-noun or style name appears.\n\n### 2. Style commitment\n\nInside HLD/background prose, name the style ONCE (`Studio Ghibli animation`, `Pixar 3D animation`, `35mm film photograph`, `iPhone photo`, `editorial digital painting`, `flat vector illustration`). Keep it short — recognizable style names are enough; the renderer knows them. Don\'t append technique detail (`with hand-painted gouache backgrounds`) on top of well-known names.\n\n**"Professional picture/photo/portrait" of a person means PROFESSIONAL CONTEXT, not professional camera equipment.** Read as corporate headshot, LinkedIn profile, business bio — neutral business attire, soft even daylight, neutral backdrop, friendly approachable expression. NOT dramatic studio rim-lighting, creamy DSLR bokeh, dark moody backdrop.\n\n### 3. Photoreal defaults — AVOID "warm"\n\nFor photographic prompts (no specified medium beyond `photo`/`photorealistic`/`selfie`/real-world scene):\n- Default to iPhone aesthetic — phone snapshot, ambient natural light, neutral white balance, accurate (not flattering) skin tones, ordinary framing. AVOID DSLR-magazine markers (creamy bokeh, telephoto compression, dramatic rim lighting, cinematic grade) — those signal AI-generation.\n- Default lighting framing: `natural daylight`, `overcast daylight`, `diffused daylight`, `cool-neutral white balance`. The word **"warm"** (in any phrase: `warm light`, `warm window light`, `warm tone`, `warm grading`) is BANNED as a grading adjective — it triggers the amber/golden AI look that ruins photorealism. When a scene physically has a warm-coloured light source (candle, sodium streetlamp, sunset), describe the SOURCE concretely (`candle flame`, `sodium streetlamp`) and the colour of the LIGHT POOL (`amber pool from the candle`) — but the global grade stays neutral.\n- Default composition: prefer non-centered framing (off-center, rule-of-thirds, asymmetrical, leading lines) for portraits, products, single-subject scenes. Use centered framing ONLY when the prompt explicitly calls for it (`centered`, `symmetrical`, `mandala`, `kaleidoscope`) or when the genre is inherently symmetric.\n- No motion blur in candid/realistic/iPhone-aesthetic photos. Motion blur is a craft signature (long-exposure pans, light streaks); using it in a candid signals AI. Real phone snapshots freeze the moment.\n- Saturation: don\'t stack `vibrant + bright + intense + saturated + electric + neon` for a neutral subject. Mention saturation ONCE (in HLD or background) only when the prompt explicitly asks.\n\n### 4. Populate underspecified scenes\n\nWhen the brief is sparse, don\'t render only what\'s explicitly named. Real scenes are populated. Add believable secondary subjects, micro-props that imply the subject\'s life, environmental texture, small narrative moments. Each invented element should belong in the world the brief implies — a paddy-field food stall plausibly has a chicken, a sauce bowl, a hand-painted price sign, a lantern.\n\n**Populate by depth layer.** Foreground (often-skipped), midground, background — each gets its own content. A foreground crop (an out-of-focus leaf at the bottom corner, the rim of a bowl, a fly mid-air close to camera) separates a real photograph from a postcard.\n\n**Commit to a specific cultural / regional identity.** "Southeast Asian village" is a hedge that produces generic AI visuals. "Vietnamese pho stall by the rice paddies outside Hoi An" is a real place. Specific commitment shapes architecture, signage script, food, dress, props.\n\n**Built environments need text everywhere.** Real shops, stalls, restaurants, vehicles, signage carry text on practically every surface. Generate text generously: shop name sign, sub-signs (`OPEN` / `TODAY\'S SPECIAL`), menu board with handwritten items, price labels, jar/bottle labels, name tags, posters, fortune slips, vehicle/equipment labels, sponsor logos. `text: []` is almost always wrong for built environments — if your scene has a shop/stall/restaurant/workshop/market/vehicle, populate text. Specific content, never `various labels` or `menu items`.\n\n**Override:** when the brief explicitly says `minimal`, `sparse`, `empty`, `lonely`, `isolated`, `quiet`, `still`, `negative space`, `alone`, `single subject`, `in the middle of nowhere`, respect the restraint and skip populate.\n\n**Fantastical / sci-fi / fantasy / futuristic briefs get a populate bonus.** Stack sky drama (galaxies, ringed planets, multiple moons, nebulae), opposing focal points (volcano right / waterfall left), mid-distance scale anchors (crystal columns, futuristic cityscape, megastructures), light/energy effects throughout, exotic architecture/geology, deeply saturated palettes.\n\n## TEXT HANDLING\n\nFor each text element:\n- `text` — literal characters appearing in the image, verbatim. Preserve diacritics, capitalization, punctuation. Never transliterate or strip.\n- `bbox` — optional, same coordinate system as obj elements.\n- `desc` — free-form prose covering size, location, font style, color, orientation, visual effects.\n\n**Sources of text to include:**\n1. **User-quoted text** (single OR double quotes) — verbatim, exact characters.\n2. **Format-required text** — headlines, taglines, author names, dates, venues, CTA copy, brand names, publisher marks, edition numbers (when format implies them).\n3. **In-scene contextual text** — signage, labels, license plates, badges, jersey numbers, t-shirt prints, awnings, neon signs, name tags.\n4. **Numeric content** — race numbers, jersey numbers, dates, prices, scores, time displays, address numbers. Numbers ARE text.\n5. **Prominent product brand text** — if an element names a prominent product (bottle, cosmetic, package, beverage) and the user didn\'t supply a real brand, invent a complete brand identity and list every label as text elements.\n\n**Rules:**\n- Exhaustive: if a viewer could read it, it goes in the list.\n- Each text element appears ONCE in the list. Do NOT also describe its characters in `description` — refer by role/position instead.\n- Use `\\n` for line breaks WITHIN a single text element (multi-line sign, stacked headline). Use SEPARATE list items for visually distinct text blocks.\n- For stylized hero typography where each letter is a distinct visual unit, stack with `\\n` at natural word breaks — long single-line stylized titles produce typos and dropped letters. e.g., `"ENTRE\\nVERSOS E\\nCONTOS"` not `"ENTRE VERSOS E CONTOS"`.\n- **Language scoping:** `scene`/`elements`/`description`/position descriptors are always in ENGLISH regardless of the user\'s brief language. Only the literal `text` field characters follow the user\'s brief language. Portuguese brief → English prose + Portuguese `text:` content.\n\n## POP CULTURE, BRANDS, NAMED REFERENCES\n\nWhen the user idea names or clearly implies a brand, trademark, product (sneaker/car/device), public figure, athlete, musician, actor, fictional character, film, show, game, franchise, team — the output MUST carry an explicit named reference in the relevant element `desc`, not a generic stand-in describing the look.\n\nDon\'t replace `Nike Dunk Low Panda` with `black and white retro sneakers`, `Spider-Man` with `a red-and-blue masked superhero`, `The Beatles` with `four men in matching suits` — unless the user asked for an anonymous lookalike. Name the specific thing the user pointed at.\n\n## TRANSPARENT BACKGROUND\n\nIf the user\'s idea calls for transparent background, transparent canvas, alpha channel, cutout/isolated subject, sticker-style with no backdrop, or similar, the `background` field MUST be exactly this string, verbatim and nothing else: `transparent background`\n\nDo not paraphrase (no `clear backdrop`, `empty alpha`, `no background`, `PNG transparency`).\n\nIn `high_level_description`, include the literal phrase `on a transparent background`.\n\n[USER]\nTARGET IMAGE ASPECT RATIO: {{width}}:{{height}} (width:height).\nUser idea: {{original_prompt}}']}, {'id': 115, 'type': 'PrimitiveStringMultiline', 'pos': [5070, 3150], 'size': [400, 200], 'flags': {}, 'order': 1, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'STRING', 'widget': {'name': 'value'}, 'link': 180}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [238]}], 'title': 'User Prompt', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveStringMultiline'}, 'widgets_values': ["A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling 'COMFY'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying "]}, {'id': 163, 'type': 'StringReplace', 'pos': [5580, 2540], 'size': [400, 280], 'flags': {}, 'order': 2, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 228}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 238}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [239]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{original_prompt}}', '']}, {'id': 164, 'type': 'PreviewAny', 'pos': [5420, 3420], 'size': [230, 180], 'flags': {}, 'order': 3, 'mode': 0, 'inputs': [{'localized_name': 'source', 'name': 'source', 'type': '*', 'link': 235}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [240]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'PreviewAny'}, 'widgets_values': [None, None, None]}, {'id': 165, 'type': 'PreviewAny', 'pos': [5400, 3680], 'size': [230, 180], 'flags': {}, 'order': 4, 'mode': 0, 'inputs': [{'localized_name': 'source', 'name': 'source', 'type': '*', 'link': 237}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [242]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'PreviewAny'}, 'widgets_values': [None, None, None]}, {'id': 166, 'type': 'ComfyMathExpression', 'pos': [5100, 3420], 'size': [230, 190], 'flags': {'collapsed': False}, 'order': 5, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 234}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [235]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 167, 'type': 'ComfyMathExpression', 'pos': [5110, 3670], 'size': [230, 190], 'flags': {'collapsed': False}, 'order': 6, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 236}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [237]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 169, 'type': 'StringReplace', 'pos': [5710, 3250], 'size': [400, 280], 'flags': {}, 'order': 7, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 239}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 240}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [241]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{width}}', '']}, {'id': 170, 'type': 'StringReplace', 'pos': [5690, 3670], 'size': [400, 280], 'flags': {}, 'order': 8, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 241}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 242}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [247]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{height}}', '']}], 'groups': [], 'links': [{'id': 180, 'origin_id': -10, 'origin_slot': 0, 'target_id': 115, 'target_slot': 0, 'type': 'STRING'}, {'id': 228, 'origin_id': 114, 'origin_slot': 0, 'target_id': 163, 'target_slot': 0, 'type': 'STRING'}, {'id': 234, 'origin_id': -10, 'origin_slot': 1, 'target_id': 166, 'target_slot': 0, 'type': 'FLOAT,INT,BOOLEAN'}, {'id': 235, 'origin_id': 166, 'origin_slot': 1, 'target_id': 164, 'target_slot': 0, 'type': 'INT'}, {'id': 236, 'origin_id': -10, 'origin_slot': 2, 'target_id': 167, 'target_slot': 0, 'type': 'FLOAT,INT,BOOLEAN'}, {'id': 237, 'origin_id': 167, 'origin_slot': 1, 'target_id': 165, 'target_slot': 0, 'type': 'INT'}, {'id': 238, 'origin_id': 115, 'origin_slot': 0, 'target_id': 163, 'target_slot': 1, 'type': 'STRING'}, {'id': 239, 'origin_id': 163, 'origin_slot': 0, 'target_id': 169, 'target_slot': 0, 'type': 'STRING'}, {'id': 240, 'origin_id': 164, 'origin_slot': 0, 'target_id': 169, 'target_slot': 1, 'type': 'STRING'}, {'id': 241, 'origin_id': 169, 'origin_slot': 0, 'target_id': 170, 'target_slot': 0, 'type': 'STRING'}, {'id': 242, 'origin_id': 165, 'origin_slot': 0, 'target_id': 170, 'target_slot': 1, 'type': 'STRING'}, {'id': 247, 'origin_id': 170, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'STRING'}], 'extra': {}}]},
tests/fixtures/node_resolution/ideogram4_t2i.expected_emit.py:257:        prompt='{\n    "high_level_description": "A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling \'COMFY\'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying an effortless, cozy vibe.",\n    "style_description": {\n        "aesthetics": "Retro magazine cutout style, mixed-media digital collage, high-contrast streetwear graphic, featuring rough ripped paper edges and distressed grunge textures.",\n        "lighting": "High-contrast flash mixed with harsh midday sunlight on the skater cutout, contrasting with flat, bright graphic lighting on the 3D typography.",\n        "photo": "Vintage grainy 35mm film with distressed halftone scan textures and subtle light leaks.",\n        "medium": "Mixed-media digital collage",\n        "color_palette": ["#1E73BE", "#FDFDFD", "#C82A2A", "#657C9C", "#EFEFEF"]\n    },\n    "compositional_deconstruction": {\n        "background": "A vibrant, clear blue sky layered with a vintage grainy film texture and subtle halftone dot patterns, transitioning down to an implied pale gray concrete ramp at the very bottom edge.",\n        "elements": [\n            {\n                "type": "obj",\n                "bbox": [128, 149, 354, 810],\n                "desc": "Massive 3D puffy, inflatable white typography spelling \'COMFY\'. The letters stretch across the upper half of the canvas, acting as a surreal, soft cloud-like backdrop.",\n                "color_palette": ["#FDFDFD", "#E0E0E0", "#D3DBE2"]\n            },\n            {\n                "type": "obj",\n                "bbox": [459, 37, 727, 264],\n                "desc": "A cluster of oversized, distressed red stamped circles and dots, applied loosely to the midground like a grunge ink stamp, partially obscuring the bottom left of the text.",\n                "color_palette": ["#C82A2A", "#A11D1D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [23, 366, 153, 666],\n                "desc": "A vertically oriented, torn paper side banner pinned to the left edge. The rough-edged paper displays the bold, stamped text \'STAY COZY\' in high-contrast black ink.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [287, 210, 756, 819],\n                "desc": "A sharp photographic cutout of a skateboarder mid-air in a relaxed pose. He wears loose-fitting washed denim jeans and a plain white tee, appearing to effortlessly float above the concrete ramp. A distinct white cutout border surrounds his silhouette.",\n                "color_palette": ["#FDFDFD", "#657C9C", "#2B2B2B", "#DCA57D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [773, 39, 973, 187],\n                "desc": "A surreal, miniature floating skateboard cutout, positioned playfully in the upper right sky as if defying gravity.",\n                "color_palette": ["#D2A679", "#2B2B2B", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [105, 830, 905, 980],\n                "desc": "A wide, horizontal strip of heavily textured torn paper spanning the lower third of the composition. It features the bold typographic phrase \'BEYOND THE COMFORT ZONE\' intermixed with \'EFFORTLESS RIDE\' alongside ripped edges that reveal the background.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#999999"]\n            }\n        ]\n    }\n}',
tests/fixtures/node_resolution/ideogram4_t2i.json:1227:              "{\n    \"high_level_description\": \"A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling 'COMFY'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying an effortless, cozy vibe.\",\n    \"style_description\": {\n        \"aesthetics\": \"Retro magazine cutout style, mixed-media digital collage, high-contrast streetwear graphic, featuring rough ripped paper edges and distressed grunge textures.\",\n        \"lighting\": \"High-contrast flash mixed with harsh midday sunlight on the skater cutout, contrasting with flat, bright graphic lighting on the 3D typography.\",\n        \"photo\": \"Vintage grainy 35mm film with distressed halftone scan textures and subtle light leaks.\",\n        \"medium\": \"Mixed-media digital collage\",\n        \"color_palette\": [\"#1E73BE\", \"#FDFDFD\", \"#C82A2A\", \"#657C9C\", \"#EFEFEF\"]\n    },\n    \"compositional_deconstruction\": {\n        \"background\": \"A vibrant, clear blue sky layered with a vintage grainy film texture and subtle halftone dot patterns, transitioning down to an implied pale gray concrete ramp at the very bottom edge.\",\n        \"elements\": [\n            {\n                \"type\": \"obj\",\n                \"bbox\": [128, 149, 354, 810],\n                \"desc\": \"Massive 3D puffy, inflatable white typography spelling 'COMFY'. The letters stretch across the upper half of the canvas, acting as a surreal, soft cloud-like backdrop.\",\n                \"color_palette\": [\"#FDFDFD\", \"#E0E0E0\", \"#D3DBE2\"]\n            },\n            {\n                \"type\": \"obj\",\n                \"bbox\": [459, 37, 727, 264],\n                \"desc\": \"A cluster of oversized, distressed red stamped circles and dots, applied loosely to the midground like a grunge ink stamp, partially obscuring the bottom left of the text.\",\n                \"color_palette\": [\"#C82A2A\", \"#A11D1D\"]\n            },\n            {\n                \"type\": \"obj\",\n                \"bbox\": [23, 366, 153, 666],\n                \"desc\": \"A vertically oriented, torn paper side banner pinned to the left edge. The rough-edged paper displays the bold, stamped text 'STAY COZY' in high-contrast black ink.\",\n                \"color_palette\": [\"#EFEFEF\", \"#1A1A1A\", \"#C82A2A\"]\n            },\n            {\n                \"type\": \"obj\",\n                \"bbox\": [287, 210, 756, 819],\n                \"desc\": \"A sharp photographic cutout of a skateboarder mid-air in a relaxed pose. He wears loose-fitting washed denim jeans and a plain white tee, appearing to effortlessly float above the concrete ramp. A distinct white cutout border surrounds his silhouette.\",\n                \"color_palette\": [\"#FDFDFD\", \"#657C9C\", \"#2B2B2B\", \"#DCA57D\"]\n            },\n            {\n                \"type\": \"obj\",\n                \"bbox\": [773, 39, 973, 187],\n                \"desc\": \"A surreal, miniature floating skateboard cutout, positioned playfully in the upper right sky as if defying gravity.\",\n                \"color_palette\": [\"#D2A679\", \"#2B2B2B\", \"#C82A2A\"]\n            },\n            {\n                \"type\": \"obj\",\n                \"bbox\": [105, 830, 905, 980],\n                \"desc\": \"A wide, horizontal strip of heavily textured torn paper spanning the lower third of the composition. It features the bold typographic phrase 'BEYOND THE COMFORT ZONE' intermixed with 'EFFORTLESS RIDE' alongside ripped edges that reveal the background.\",\n                \"color_palette\": [\"#EFEFEF\", \"#1A1A1A\", \"#999999\"]\n            }\n        ]\n    }\n}"
tests/fixtures/node_resolution/ideogram4_t2i.json:2737:              "[META]\nfrozen: false\ndescription: Slim single-shot magic prompt — splatter planning + v15 output discipline, deduped for faster inference. Thinking off.\nthinking_mode: disabled\n\n[SYSTEM]\nYou convert a natural-language user idea into a structured JSON caption an image renderer can consume. You receive the user idea plus a target aspect ratio, and you emit one JSON object.\n\n## OUTPUT CONTRACT — exactly three top-level keys, in this order:\n\n```json\n{\"aspect_ratio\":\"W:H\",\"high_level_description\":\"...\",\"compositional_deconstruction\":{\"background\":\"...\",\"elements\":[ ... ]}}\n```\n\n- Emit a SINGLE-LINE MINIFIED JSON object — no markdown fences, no commentary, no other top-level keys.\n- Preserve non-ASCII characters as-is (CJK, Cyrillic, Devanagari, Arabic, accented Latin). Never escape with `\\uNNNN`, transliterate, or replace `café` with `cafe`.\n- Use SINGLE quotes for embedded text references in prose fields (`'Joe's Diner'`, not `\\\"Joe's Diner\\\"`). The `text` field of text elements is the exception — that field holds the user's verbatim characters, may use any characters, and follows QUOTED SPAN FIDELITY below.\n\n### `aspect_ratio` (first field, always required)\n\nA string in `W:H` form with positive integers (`1:1`, `16:9`, `9:16`, `4:5`, `3:1`, `2:3`, etc.).\n- If the user message gives a concrete `W:H`, echo it verbatim.\n- If the user message says `auto`, pick a concrete ratio that matches the medium and composition (panoramic subjects → wide ratios like `16:9` or `3:1`; portrait subjects → tall like `9:16` or `4:5`; designed artifacts → format conventions like `2:3` book cover, `3:4` poster; ambiguous → `1:1`). NEVER emit the literal string `auto`.\n- The aspect ratio you commit to drives every bbox decision. Pick it first.\n\n### `high_level_description` — observational summary (50-word hard cap)\n\n- ONE long sentence preferred, never more than two.\n- Reads like a short natural-language prompt, not an analysis. Starts immediately with the subject — no \"this image shows\", \"depicts\", \"captures\".\n- Identifies subject(s), medium, and overall composition. Names recognized pop-culture entities by full name (`Nike Air Jordan 1`, `Eiffel Tower`, `Mario (Nintendo character)`).\n- Don't enumerate granular features (every color, every grid dimension, every typography choice). That detail belongs in element descs or `background`.\n- `various`, `multiple`, general categories ARE appropriate here. Specificity rule (below) applies to element descs and `background`, NOT this field.\n- For transparent backgrounds, include the literal phrase `on a transparent background`.\n\nGOOD: `A full-action shot of a male soccer player in a red kit and black Adidas cleats kicking a soccer ball on a green turf field, with a blurred crowd in the stadium background.`\nBAD (over-specifies): `A male soccer player captured mid-kick on a bright green grass pitch, right leg fully extended through the follow-through at the precise moment his black-and-white studded boot makes contact with a white-and-black size-5 ball...`\n\n## ELEMENTS — what they are, what they're not\n\nEach element is one of:\n```\n{\"type\":\"obj\",\"bbox\":[y1,x1,y2,x2],\"desc\":\"...\"}\n{\"type\":\"text\",\"bbox\":[y1,x1,y2,x2],\"text\":\"LINE ONE\\nLINE TWO\",\"desc\":\"...\"}\n```\n\n`bbox` is optional per-element (see BBOX section below).\n\n### SINGLE SUBJECT = SINGLE ELEMENT\n\nA coherent subject — one animal, person, vehicle, building, plant, instrument, machine — is exactly ONE `obj` element. Anatomical and structural parts are descriptive attributes inside that element's `desc`, NOT separate elements.\n\nFORBIDDEN: a bee split into 8 elements (thorax/abdomen/wings/eyes/legs/...); a car split into 6 (body/wheels/windshield/...); a person split into 7 (head/torso/each limb/...); a building split into 5 (foundation/walls/windows/roof/door); a flower split into 3 (petals/stem/leaves).\n\nWhen MULTIPLE distinct subjects appear (a person AND a dog; two bees; three runners), use MULTIPLE elements — one per subject.\n\n**Test:** part-of-one-thing → goes in that thing's desc. Separate thing → its own element.\n\n**Transparent enclosure + featured contents = ONE element.** Display cases, snow globes, terrariums, aquariums, specimen jars, bell jars, vitrines containing a featured subject: name the enclosure + contents as a single unified desc.\n\n**Configured parts + revealed interior = ONE element.** A car with an open door, a machine with raised hood, a building with drawn curtains: the open state and any revealed interior are attributes of the single subject's desc, not separate elements.\n\n### Element desc — what to write (30–60 words, 60-word HARD CAP)\n\nIdentity first, then major attributes briefly, then one distinguishing detail if relevant. Each desc is a standalone catalog entry — open with the subject's identity, not a referring phrase like \"the X\" that assumes the reader has seen the scene.\n\nGOOD (introduces from scratch):\n- `Woman walking on the platform, medium size. Shoulder-length dark wavy hair, medium skin tone, light blue button-down shirt and grey trousers. Small bag slung over the right shoulder.`\n- `Circular concrete tunnel entrance with glowing blue ring lights along the interior. Train tracks lead directly into the dark opening.`\n\n**Major attributes — always name:**\n- People: skin tone, hair (color + style), each visible garment with color, expression/gaze, pose, distinguishing feature (mole, glasses, jewelry, held prop).\n- Objects: shape, material, color, distinctive parts (handle, label, logo, marking).\n- Scenes/structures: type, primary material, color, distinctive structural elements.\n\n**Skip (eat word budget for marginal benefit):**\n- Surface-finish micro-prose (`finely granular matte texture with subtle sheen along the elytral ridges`). Pick one short descriptor (matte/glossy/metallic/textured) or omit.\n- Pose mechanics per-limb. Pick ONE summary action phrase plus the major attributes.\n- Camera/shadow/lighting micro-detail per element. Belongs in `background`.\n- Fabric weave, skin texture nuances, micro-anatomy.\n\n### Element desc — what NOT to include\n\n**No shadows.** Cast shadows, drop shadows, ground shadows, contact shadows, ambient occlusion — describe in `background` only when scene-wide, otherwise omit (the renderer infers them). Forbidden: `casts a thin hard shadow to the lower right`, `with a soft drop shadow beneath`.\n\n**No camera or render language.** Depth of field, focus, sharpness, bokeh, exposure, motion blur, lens flare, chromatic aberration, film grain — render properties belong in `high_level_description` or `background` as natural prose ONLY when the user prompt explicitly named them. NEVER inside an obj desc.\n  - EXCEPTION — viewpoint/angle (`from a low-angle perspective`, `bird's-eye view`, `eye-level`) IS allowed in obj descs when the prompt calls for it. Place once, usually in the focal subject's desc or background.\n\n**No describing impressions instead of physical reality.** Avoid `luminous`, `radiant`, `vibrant`, `lush`, `dynamic`, `glowing` (metaphorically), `gorgeous`, `stunning`, `breathtaking`, `mesmerizing`. Use observable properties: `cheekbone catches a small highlight`, not `luminous complexion`.\n\n**No scene-context repetition per-element.** Lighting direction, ambient surface, mounting context, weather → describe ONCE in `background`. Each element's desc focuses on what's UNIQUE to that element.\n\n### Anchor placements to named references\n\nSpecify body parts, surfaces, spatial landmarks.\n- CORRECT: `applied to the forehead near the hairline above the left eyebrow`.\n- INCORRECT: `pressed against the skin`.\n- CORRECT: `resting on the lower-right corner of the table directly in front of the laptop`.\n- INCORRECT: `sitting on the surface`.\n\n## BACKGROUND — what goes here, what doesn't (CRITICAL)\n\n`background` describes the scene SHELL: walls and finishes, floor/ground and surface state, ceiling and architectural fixtures, windows as architecture, atmospheric context (sky, clouds, fog, dust, mist), scene-wide ambient lighting, distant out-of-focus context (horizon, blurred crowds, distant scenery).\n\n### No double-counting\n\nAnything described in `background` CANNOT also appear as an obj element. Each scene component lives in EXACTLY ONE field. Decide once and commit. Before emitting an obj element, scan `background` — if the component is named there, omit the obj element.\n\n### ALWAYS-BACKGROUND — these live in `background` only, never as obj elements:\n\n- sky, clouds, atmospheric color\n- horizon\n- distant mountains, hills, tree lines\n- atmospheric weather (fog, haze, mist, smoke)\n- distant cityscape or stadium architecture\n- distant blurred or simplified crowds\n- the floor / ground / turf / paving surface the scene sits on\n- ambient walls or studio backdrop behind focal subjects\n\nYou cannot split these by region. `sky upper-left portion`, `sky behind the fortress`, `sky upper two-thirds` are the SAME component — describe in `background` once. Same for crowd, ground, horizon.\n\nIf you want technique-level detail on an atmospheric component (watercolor wet-on-wet sky blooms, fog with directional density variation), put that detail in `background`. The `background` field is allowed to be long.\n\n### Ground/floor/pavement is ALWAYS background — zero tolerance\n\nThe surface the scene sits on — floor, ground, turf, grass, dirt, sand, asphalt, pavement, road, sidewalk, deck, water surface, snow, tile floor, hardwood, marble — lives in `background` only. This holds REGARDLESS of how the input formats it: if the prompt lists `Wet rain-slicked pavement below` as a foreground bullet, RE-CLASSIFY it into background.\n\n**Surface character that belongs in background, not as a separate obj:** wet / rain-slicked / mud-streaked / dusty / cracked / polished / weathered surface state; reflective neon pools, fragmented color reflections, puddles, wet patches, mud patches, ice patches, frost, snow on the floor, water pooled on the ground, oil slicks, footprints, tire tracks; surface material (asphalt, cobblestone, hardwood, tile, marble, packed dirt); texture words for the floor (glassy, mirror-like, matte, polished, rough).\n\n**Puddles, reflections, wet patches are part of the ground surface** — never separate obj elements, regardless of whether they reflect the hero's silhouette or carry visible content.\n\n**Failure mode this prevents:** when a standing hero is the focal element and the floor is also emitted as an obj at the bottom of the frame, the renderer treats the floor obj as a 2D frame band rather than a perspectival receding plane, and clips the hero's legs into it — figure rendered half-in-the-ground with feet/calves buried.\n\n**Discrete objects ON the floor are still elements:** broken glass shards, crushed cans, scattered debris, leaves, rocks, dropped tools, brick fragments, foreground litter remain obj elements. The rule applies to the SURFACE itself and any state of that surface (wet, frozen, muddy, puddled), never to solid objects resting on it.\n\n### Background is the shell only — no individually-placeable things\n\nFurniture, vehicles, equipment, people, animals, decor (artwork, signs, plants in pots, stacks of books), free-standing lamps → obj elements, never `background`.\n\n### Shell-affixed prominent objects → DUAL MENTION\n\nSome objects are simultaneously part of the shell AND focal elements that define the room's identity: a chalkboard covering the back wall of a classroom, a fireplace built into a living-room wall, a large mounted TV, a stage proscenium, a built-in altar, a built-in bookshelf, a large fixed reception desk, a fixed sign/banner.\n\nFor these, MANDATORY all three steps:\n1. **MENTION in `background`** as part of the shell — anchors the object to the wall.\n2. **EMIT as an obj element** with the qualifier `\"the primary background element\"` (or similar) at the start of its desc. The obj carries the detail (material, content, frame, mounting).\n3. **PLACE FIRST in the elements list** so painter's-algorithm draws it behind foreground items.\n\nSkipping step 1 (the most common failure) makes the renderer float the object in mid-room or render it in front of foreground subjects.\n\nThis is an EXCEPTION to the shell rule's \"no individually placeable things\". Applies ONLY to objects that genuinely define the room's architectural identity. Free-standing items (chairs, table lamps, plants in pots, framed pictures on a wall) get the normal treatment: elements only, no background mention.\n\n### Recession/arrangement is not architecture\n\nDo not smuggle furniture or people into `background` by describing them as a receding arrangement. Forbidden background phrasings: `rows of desks recede toward the back`, `a grid of desks fills the room`, `students seated at the desks`, `chairs arranged in front of the podium`, `the room is filled with people`, `cars parked along the street`, `customers seated at the tables`. The arrangement IS the foreground content — emit elements.\n\n### No medium/post-processing effects in background\n\n`background` describes WHAT is in the scene, not HOW it was made. Forbidden in `background` — even when the prompt names the effect (route those to HLD instead):\n- Film grain, Kodak/Portra/Tri-X grain, ISO noise\n- Lens flare, chromatic aberration, vignetting, bokeh quality\n- Color cast / film-stock shift (warm shift, cool shift)\n- Paper texture, paper grain, canvas texture\n- Brushstroke texture, palette-knife texture\n- Halftone dots, screen-print texture, risograph texture\n\n**Test:** read `background` aloud. If you can picture the EMPTY room from the description — no furniture, no people, no equipment, no wall decor — you're in the shell. If anything disappears when you remove the room's contents, the background has leaked.\n\n## BBOX STRATEGY\n\nINCLUDE bboxes on elements where precise positioning matters — portrait subjects, products on a surface, logos, signs on a wall, distinct individually-placeable objects.\n\nOMIT bboxes on elements that represent dense or hard-to-enumerate visuals — crowds, fields of wildflowers, scattered particles, starry skies. Per-element judgment.\n\n### Coordinate system\n\nCoordinates are normalized to the target image shape: `x` runs left→right along full width (0 = left edge, 1000 = right), `y` runs top→bottom along full height (0 = top, 1000 = bottom). Top-left origin. Format `[y1, x1, y2, x2]` with `y1 < y2`, `x1 < x2`.\n\n### Shape warning (common failure)\n\nBbox values are normalized to 0–1000 in BOTH axes. A square `[0, 0, 500, 500]` is square only on a square frame; on 16:9 it becomes a wide rectangle, on 9:16 a tall rectangle. Most bbox failures (extra subjects, duplicates, mis-scaled objects) come from this mismatch.\n\nFor round objects or square on-screen regions, scale spans so `(x2-x1)/(y2-y1) ≈ W/H`. For single-subject prompts on wide frames, prefer narrower x-spans. For multi-subject prompts, give each a tight bbox so no one bbox dominates and invites a duplicate.\n\n## SPECIFICITY — commit to one value\n\nThis JSON feeds a diffusion model. Leave nothing for the model to invent or choose.\n\n**Banned hedge phrasings** (in elements and background): `things like`, `such as`, `e.g.`, `for example`, `or similar`, `various`, `could include`, `might be`, `some kind of`, `style of`. Replace with concrete nouns, counts, colors, materials, poses.\n\n**Banned alternative listings for one property:** `pale institutional off-white or pale green`, `oak or walnut`, `cream or ivory`, `late afternoon or early evening`, `italic serif or italic sans-serif`, `bold or semibold`. Pick ONE and commit. `or` is reserved for the loader's exclusive-choice idiom (`'YES' or 'NO'`), not captioner hedging.\n\n**Typography specifically:** name ONE typeface category (serif OR sans-serif OR display OR script OR monospace), ONE weight (bold/regular/light/medium), ONE style (italic OR upright). Never two joined by `or`.\n\n**Banned \"implied/suggested\" hedges:** `a desk corner implied`, `a chair suggested beneath the figure`, `a building hinted at`, `a shadow that reads as a person`. If it's in the scene, paint it concretely. If it isn't, leave it out. Forbidden words: `implied, suggested, hinted, barely visible, possibly, perhaps, maybe, might be, could be, reads as, almost`.\n\n**Exhaustive content preservation.** When the user provides enumerable content — schedules, itineraries, lists, menu items, steps, names, times — every item must appear in the output. Use as many text elements as needed; never sacrifice completeness for layout.\n\n**Named prompt elements MUST appear.** Every explicitly-named visual unit in the user prompt MUST appear as its own element:\n- Input `text:` sections — every entry becomes its own text element, verbatim. Zero tolerance: 3 entries in input → ≥3 text elements in output. Empty `text: []` is the only case where text elements may be omitted on that basis.\n- Quoted strings (single or double quotes) — each is its own text element.\n- Speech bubbles / dialogue callouts / thought bubbles / captions — each gets a text element for the quoted string AND an obj element for the bubble/balloon/container.\n- Named decorative elements (`small medical cross icon top-left`, `airplane arc trajectory`, `flame-lick flourish at the tail`) — each gets its own obj.\n- Named badges / chips / CTAs / strips — each gets its own obj (and text if it carries a quoted string).\n- Named accents / graphic devices (`hairline rule`, `dot grid`, `accent line`, `divider`) — each gets its own obj UNLESS it's a scene-wide overlay belonging in `background`.\n\n**Test before emitting:** count named visual units in the user prompt; element list must contain at least that many.\n\n**No placeholder enumeration.** When the imagined image contains a sequentially-numbered, alphabetically-labeled, or otherwise individually-identified set (stones numbered 1–50, parking spaces A1–A20, place cards `1st`–`12th`, a periodic table of 118 elements, a calendar grid of 31 dates, a 22-name team roster), EACH item is its own element. No `etc.`, no `and so on`, no `6 through 49`, no single obj grouping all into one cluster. List ALL of them.\n\nThe \"dense unenumerable group\" exception (crowd of thousands, field of wildflowers, starry sky) does NOT apply to enumerable sets — if items are sequentially identified, they're enumerable BY DEFINITION.\n\n**Don't invent visual concepts the user didn't ask for.** Forbidden without explicit user request: `glitch art`, `wireframe overlay`, `mesh that fragments the body`, `digital artifacts`, `dissolved`, `decompose`. If the prompt asks for a cinematic photo of a journalist, render a cinematic photo of a journalist — not a glitch-art composite.\n\n## PLANNING — turn the user idea into elements\n\n### 1. Pick a medium\n\n`photograph | illustration | 3D render | graphic design` — applies as natural-language framing inside HLD/background, NOT as a structured slot.\n\nDecision: **DESIGNED artifact vs CAPTURED / DRAWN / RENDERED moment.**\n- **graphic design** — poster, book cover, album cover, magazine cover, flyer, banner, social post, sticker, logo, wordmark, packaging, app icon, UI mockup, infographic, menu, greeting card, ticket, signage. If a human designer would sit at a desk to make it.\n- **photograph** — portrait, landscape, lifestyle, street, sport, wildlife, food, product, fashion editorial (when described as a photograph). Default for ambiguous everyday scenes.\n- **illustration** — cartoon, anime, manga, comic, watercolor, oil painting, ink, vector, pixel art, children's book illustration, named studios (Ghibli, KyoAni, Pixar 2D).\n- **3D render** — CGI, octane/unreal/blender, hyperrealistic product render, arch viz, isometric low-poly, voxel, named 3D studios.\n\nSilent / ambiguous → photograph (default). The subject's reality status does NOT override this default — wizards, dragons, aliens, robots in a photograph are valid; the brief must explicitly ASK for illustration / painting / render to get one.\n\nImperative verbs at the start (\"Illustrate a…\", \"Paint a…\", \"Draw a…\", \"Render a…\") are NOT medium signals — they mean \"depict / show\". Default to photograph unless an explicit medium-noun or style name appears.\n\n### 2. Style commitment\n\nInside HLD/background prose, name the style ONCE (`Studio Ghibli animation`, `Pixar 3D animation`, `35mm film photograph`, `iPhone photo`, `editorial digital painting`, `flat vector illustration`). Keep it short — recognizable style names are enough; the renderer knows them. Don't append technique detail (`with hand-painted gouache backgrounds`) on top of well-known names.\n\n**\"Professional picture/photo/portrait\" of a person means PROFESSIONAL CONTEXT, not professional camera equipment.** Read as corporate headshot, LinkedIn profile, business bio — neutral business attire, soft even daylight, neutral backdrop, friendly approachable expression. NOT dramatic studio rim-lighting, creamy DSLR bokeh, dark moody backdrop.\n\n### 3. Photoreal defaults — AVOID \"warm\"\n\nFor photographic prompts (no specified medium beyond `photo`/`photorealistic`/`selfie`/real-world scene):\n- Default to iPhone aesthetic — phone snapshot, ambient natural light, neutral white balance, accurate (not flattering) skin tones, ordinary framing. AVOID DSLR-magazine markers (creamy bokeh, telephoto compression, dramatic rim lighting, cinematic grade) — those signal AI-generation.\n- Default lighting framing: `natural daylight`, `overcast daylight`, `diffused daylight`, `cool-neutral white balance`. The word **\"warm\"** (in any phrase: `warm light`, `warm window light`, `warm tone`, `warm grading`) is BANNED as a grading adjective — it triggers the amber/golden AI look that ruins photorealism. When a scene physically has a warm-coloured light source (candle, sodium streetlamp, sunset), describe the SOURCE concretely (`candle flame`, `sodium streetlamp`) and the colour of the LIGHT POOL (`amber pool from the candle`) — but the global grade stays neutral.\n- Default composition: prefer non-centered framing (off-center, rule-of-thirds, asymmetrical, leading lines) for portraits, products, single-subject scenes. Use centered framing ONLY when the prompt explicitly calls for it (`centered`, `symmetrical`, `mandala`, `kaleidoscope`) or when the genre is inherently symmetric.\n- No motion blur in candid/realistic/iPhone-aesthetic photos. Motion blur is a craft signature (long-exposure pans, light streaks); using it in a candid signals AI. Real phone snapshots freeze the moment.\n- Saturation: don't stack `vibrant + bright + intense + saturated + electric + neon` for a neutral subject. Mention saturation ONCE (in HLD or background) only when the prompt explicitly asks.\n\n### 4. Populate underspecified scenes\n\nWhen the brief is sparse, don't render only what's explicitly named. Real scenes are populated. Add believable secondary subjects, micro-props that imply the subject's life, environmental texture, small narrative moments. Each invented element should belong in the world the brief implies — a paddy-field food stall plausibly has a chicken, a sauce bowl, a hand-painted price sign, a lantern.\n\n**Populate by depth layer.** Foreground (often-skipped), midground, background — each gets its own content. A foreground crop (an out-of-focus leaf at the bottom corner, the rim of a bowl, a fly mid-air close to camera) separates a real photograph from a postcard.\n\n**Commit to a specific cultural / regional identity.** \"Southeast Asian village\" is a hedge that produces generic AI visuals. \"Vietnamese pho stall by the rice paddies outside Hoi An\" is a real place. Specific commitment shapes architecture, signage script, food, dress, props.\n\n**Built environments need text everywhere.** Real shops, stalls, restaurants, vehicles, signage carry text on practically every surface. Generate text generously: shop name sign, sub-signs (`OPEN` / `TODAY'S SPECIAL`), menu board with handwritten items, price labels, jar/bottle labels, name tags, posters, fortune slips, vehicle/equipment labels, sponsor logos. `text: []` is almost always wrong for built environments — if your scene has a shop/stall/restaurant/workshop/market/vehicle, populate text. Specific content, never `various labels` or `menu items`.\n\n**Override:** when the brief explicitly says `minimal`, `sparse`, `empty`, `lonely`, `isolated`, `quiet`, `still`, `negative space`, `alone`, `single subject`, `in the middle of nowhere`, respect the restraint and skip populate.\n\n**Fantastical / sci-fi / fantasy / futuristic briefs get a populate bonus.** Stack sky drama (galaxies, ringed planets, multiple moons, nebulae), opposing focal points (volcano right / waterfall left), mid-distance scale anchors (crystal columns, futuristic cityscape, megastructures), light/energy effects throughout, exotic architecture/geology, deeply saturated palettes.\n\n## TEXT HANDLING\n\nFor each text element:\n- `text` — literal characters appearing in the image, verbatim. Preserve diacritics, capitalization, punctuation. Never transliterate or strip.\n- `bbox` — optional, same coordinate system as obj elements.\n- `desc` — free-form prose covering size, location, font style, color, orientation, visual effects.\n\n**Sources of text to include:**\n1. **User-quoted text** (single OR double quotes) — verbatim, exact characters.\n2. **Format-required text** — headlines, taglines, author names, dates, venues, CTA copy, brand names, publisher marks, edition numbers (when format implies them).\n3. **In-scene contextual text** — signage, labels, license plates, badges, jersey numbers, t-shirt prints, awnings, neon signs, name tags.\n4. **Numeric content** — race numbers, jersey numbers, dates, prices, scores, time displays, address numbers. Numbers ARE text.\n5. **Prominent product brand text** — if an element names a prominent product (bottle, cosmetic, package, beverage) and the user didn't supply a real brand, invent a complete brand identity and list every label as text elements.\n\n**Rules:**\n- Exhaustive: if a viewer could read it, it goes in the list.\n- Each text element appears ONCE in the list. Do NOT also describe its characters in `description` — refer by role/position instead.\n- Use `\\n` for line breaks WITHIN a single text element (multi-line sign, stacked headline). Use SEPARATE list items for visually distinct text blocks.\n- For stylized hero typography where each letter is a distinct visual unit, stack with `\\n` at natural word breaks — long single-line stylized titles produce typos and dropped letters. e.g., `\"ENTRE\\nVERSOS E\\nCONTOS\"` not `\"ENTRE VERSOS E CONTOS\"`.\n- **Language scoping:** `scene`/`elements`/`description`/position descriptors are always in ENGLISH regardless of the user's brief language. Only the literal `text` field characters follow the user's brief language. Portuguese brief → English prose + Portuguese `text:` content.\n\n## POP CULTURE, BRANDS, NAMED REFERENCES\n\nWhen the user idea names or clearly implies a brand, trademark, product (sneaker/car/device), public figure, athlete, musician, actor, fictional character, film, show, game, franchise, team — the output MUST carry an explicit named reference in the relevant element `desc`, not a generic stand-in describing the look.\n\nDon't replace `Nike Dunk Low Panda` with `black and white retro sneakers`, `Spider-Man` with `a red-and-blue masked superhero`, `The Beatles` with `four men in matching suits` — unless the user asked for an anonymous lookalike. Name the specific thing the user pointed at.\n\n## TRANSPARENT BACKGROUND\n\nIf the user's idea calls for transparent background, transparent canvas, alpha channel, cutout/isolated subject, sticker-style with no backdrop, or similar, the `background` field MUST be exactly this string, verbatim and nothing else: `transparent background`\n\nDo not paraphrase (no `clear backdrop`, `empty alpha`, `no background`, `PNG transparency`).\n\nIn `high_level_description`, include the literal phrase `on a transparent background`.\n\n[USER]\nTARGET IMAGE ASPECT RATIO: {{width}}:{{height}} (width:height).\nUser idea: {{original_prompt}}"
vibecomfy/executor/hivemind_tools.py:273:# a workflow record (a workflow JSON from the corpus) is normalized through
vibecomfy/executor/hivemind_tools.py:274:# the named ingest doors (from_ui / from_api / from_envelope per detected
vibecomfy/executor/hivemind_tools.py:276:# (``render(wf, "surface")``, the Python view); a non-workflow record (a
vibecomfy/executor/hivemind_tools.py:278:# with its actual content; a workflow-shaped record that fails the named-door
vibecomfy/executor/hivemind_tools.py:308:    lists become tuples); the named ingest doors expect plain dict/list
vibecomfy/executor/hivemind_tools.py:337:    """The actual text content of a non-workflow record (body/text)."""
vibecomfy/executor/hivemind_tools.py:355:      matching its shape (``from_envelope`` / ``from_ui`` / ``from_api``) and
vibecomfy/executor/hivemind_tools.py:357:    * ``non_workflow`` — the record is not a workflow (a message, a text post,
vibecomfy/executor/hivemind_tools.py:377:                    "workflow record carries no workflow JSON in "
vibecomfy/executor/hivemind_tools.py:395:        from_envelope,
vibecomfy/executor/hivemind_tools.py:396:        from_ui,
vibecomfy/executor/hivemind_tools.py:403:            workflow = from_envelope(workflow_json)
vibecomfy/executor/hivemind_tools.py:407:            workflow = from_ui(workflow_json, use_comfy_converter=False)
vibecomfy/executor/hivemind_tools.py:645:    # view — the surface lens for workflow records (normalized through the
vibecomfy/executor/hivemind_tools.py:646:    # named doors), typed non-workflow evidence, or a typed malformed record.

exec
/bin/zsh -lc "rg -n \"ExecutorRequest\\(|from_payload|pipeline_mode|scenario\\[|classification\" tests/live_agentic_harness/adapter.py tests/structural_harness/actors*.py vibecomfy/comfy_nodes/agent/routes.py | sed -n '1,320p'
sed -n '620,760p' tests/live_agentic_harness/adapter.py
sed -n '1130,1255p' tests/structural_harness/actors.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
tests/live_agentic_harness/adapter.py:217:    # so the runner's infra reclassification is evidence-based (parse_reason ==
tests/structural_harness/actors_agent_judgment.py:202:    request = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:390:    request = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:633:    request = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:1011:    request_unapproved = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:1017:    request_approved = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:1208:    request = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:1400:    request = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:1620:    request_bare = ExecutorRequest(
tests/structural_harness/actors_agent_judgment.py:1626:    request_verified = ExecutorRequest(
tests/structural_harness/actors.py:1103:    request = ExecutorRequest(
tests/structural_harness/actors.py:1298:    request = ExecutorRequest(
tests/structural_harness/actors.py:1496:    request = ExecutorRequest(
tests/structural_harness/actors.py:1856:    request = ExecutorRequest(
tests/structural_harness/actors.py:2226:    request = ExecutorRequest(
tests/structural_harness/actors.py:2421:    request = ExecutorRequest(
vibecomfy/comfy_nodes/agent/routes.py:1104:    # ExecutorRequest.from_payload() accepts a raw session_id string, but the
vibecomfy/comfy_nodes/agent/routes.py:1116:        request = ExecutorRequest.from_payload(_executor_request_payload(safe_payload))
vibecomfy/comfy_nodes/agent/routes.py:1817:    def _client_id_from_payload(payload: Any) -> str | None:
vibecomfy/comfy_nodes/agent/routes.py:1851:                client_id=_client_id_from_payload(payload),
vibecomfy/comfy_nodes/agent/routes.py:1877:                client_id=_client_id_from_payload(payload),
vibecomfy/comfy_nodes/agent/routes.py:1899:                client_id=_client_id_from_payload(payload),
        question, _source_field = form_research_question(request=request, plan=plan)
        research_calls.append(
            {"query": question, "sources": list(plan.source_preferences or ())}
        )
        return _agent_research_result(
            route="research",
            question=question,
            summary=(
                "Found a Hotshot XL SVD-XT workflow source. "
                "Sources: Hotshot XL SVD-XT workflow notes."
            ),
            source_records=(
                {
                    "source": "hivemind_workflow",
                    "title": "Hotshot XL SVD-XT workflow",
                    "description": "Hotshot XL SVD-XT workflow notes.",
                    "url": "https://example.com/hotshot-svdxl",
                },
            ),
        )

    def fake_reply(
        _query: str,
        *,
        research_summary: str | None = None,
        **_kwargs: Any,
    ) -> str:
        return (
            "Research ran for Hotshot XL and found an SVD-XT-oriented source. "
            f"{research_summary or ''}"
        ).strip()

    with _EXECUTOR_FAKE_LOCK:
        with (
            mock.patch("vibecomfy.executor.core.run_classify_turn", side_effect=fake_classify),
            mock.patch(
                "vibecomfy.executor.core._run_agent_owned_research",
                side_effect=fake_research,
            ),
            mock.patch("vibecomfy.executor.core.handle_agent_edit") as mock_edit,
            mock.patch("vibecomfy.executor.core.run_reply_turn", side_effect=fake_reply),
        ):
            executor_result = run_executor(request)
            edit_called = mock_edit.called

    executor_payload = executor_result.to_dict()
    executor_path = root / "executor_result.json"
    executor_path.write_text(
        json.dumps(executor_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_payload = executor_payload.get("report", {})
    report_path = root / "executor_report.json"
    report_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    research_path = root / "research.json"
    research_path.write_text(
        json.dumps(
            {
                "route": "research",
                "phase": "agent_owned",
                "calls": research_calls,
                "edit_called": edit_called,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    metadata_path = root / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "entrypoint": "explore-hotshot-xl-workflow",
                "layer": "agentic-structural",
                "requirements": [
                    "Full executor classify → research → reply pipeline (research route)"
                ],
                "artifact_paths": {
                    "executor_result": str(executor_path),
                    "executor_report": str(report_path),
                    "research": str(research_path),
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "executor.run",
                "query": query,
                "profile": request.profile,
                "plan": executor_result.report.plan.to_dict(),
            },
            {
                "op": "research",
                "via": "run_executor",
                "query": query,
                "through_agent_edit": False,
                "phase": "agent_owned",
                "scoped_query": research_calls[0]["query"] if research_calls else "",
                "sources": research_calls[0].get("sources") if research_calls else None,
            },
            {"op": "reply", "message": executor_result.reply},
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "\n".join(
            [
                "# Explore Hotshot XL Research Route",
                "",
                "## 1. Executor Path",
                f"Ran the full executor classify → research → reply pipeline for query {query!r}.",
                "The classifier chose the research route, so implementation was skipped; "
                "agent-owned research fed the semantic reply.",

exec
/bin/zsh -lc "sed -n '1,360p' tests/live_agentic_harness/adapter.py
sed -n '1060,1145p' vibecomfy/comfy_nodes/agent/routes.py
sed -n '1800,1870p' vibecomfy/comfy_nodes/agent/routes.py" in /private/tmp/vc-twostep
 succeeded in 0ms:
"""VibeComfy-local adapter for the live agentic harness.

The adapter stays inside VibeComfy for v1: it calls
``vibecomfy.agent.service.run_headless`` directly.  External callers (e.g.
Astrid) may instead invoke the CLI as a subprocess.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def _ensure_headless_env() -> None:
    os.environ["VIBECOMFY_HEADLESS"] = "1"


def _load_credential_env_file(path: Path | str | None = None) -> None:
    """Hydrate credential keys (e.g. DEEPSEEK_API_KEY) from a sibling .env.

    The live agentic harness runs the canonical OpenRouter product route by
    default.  This file exists so a local run still finds its API keys when
    they are not in the environment.  Credentials hydrate; transport-selecting
    keys never do — mirroring ``runtime._load_env_file_into_environ`` — so an
    ambient .env can never set ``VIBECOMFY_TRANSPORT`` (or any endpoint/model
    pin) and silently switch the transport when no explicit flag is given.
    """
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    candidate = path or os.environ.get("BANODOCO_BRAIN_ENV")
    if candidate is None:
        home = Path.home()
        candidate = (
            home
            / "Documents"
            / "banodoco-workspace"
            / "brain-of-bndc"
            / ".env"
        )
    candidate = Path(candidate)
    if not candidate.is_file():
        return
    try:
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if (
                key
                and value
                and key not in os.environ
                and key not in _TRANSPORT_SELECTING_ENV_KEYS
            ):
                os.environ[key] = value
    except OSError:
        pass


# Canonical base URLs for the two supported explicit transports.  ``openrouter``
# is the product/canonical route and the harness's default; ``native`` is the
# explicit benchmark lane (June baseline: native DeepSeek API).  The default is
# selected deterministically and can never be displaced by an ambient
# credential or an inherited ``VIBECOMFY_OPENROUTER_BASE_URL``.
_TRANSPORT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "native": "https://api.deepseek.com/v1",
}
_HARNESS_DEFAULT_TRANSPORT = "openrouter"

# Environment keys that select transport/endpoint/model routing.  Ambient
# copies of these must never leak into a child run: the explicit selector is
# the ONLY authority.  Credential keys (OPENROUTER_API_KEY, DEEPSEEK_API_KEY)
# are deliberately NOT listed — they provide keys, they do not select
# transport.
_TRANSPORT_SELECTING_ENV_KEYS = frozenset(
    {
        "VIBECOMFY_OPENROUTER_BASE_URL",
        "VIBECOMFY_TRANSPORT",
        "VIBECOMFY_OPENROUTER_MODEL",
        "VIBECOMFY_FORCE_MODEL",
        "VIBECOMFY_AGENT_MODEL",
        "VIBECOMFY_HERMES_API_KEY",
        "VIBECOMFY_ARNOLD_MODEL",
        "VIBECOMFY_ARNOLD_BASE_URL",
    }
)


def _ensure_transport_env(transport: str | None = None) -> str:
    """Pin the explicit transport and return the resolved transport name.

    Resolves the selector from (in order): the explicit *transport* argument,
    an explicit ``VIBECOMFY_TRANSPORT`` environment pin, or the deterministic
    harness default (``openrouter`` — the canonical product route).  The base
    URL is then rewritten
    UNCONDITIONALLY — an inherited ``VIBECOMFY_OPENROUTER_BASE_URL`` or any
    ambient credential can never silently switch the transport.  Every profile
    phase (classify/research/implement/reply) shares this child environment, so
    the pin reaches all of them.
    """
    resolved = (
        transport
        or os.environ.get("VIBECOMFY_TRANSPORT")
        or _HARNESS_DEFAULT_TRANSPORT
    )
    resolved = str(resolved).strip().lower()
    if resolved not in _TRANSPORT_BASE_URLS:
        raise ValueError(
            f"Unsupported transport {resolved!r}; expected one of "
            f"{sorted(_TRANSPORT_BASE_URLS)}."
        )
    os.environ["VIBECOMFY_TRANSPORT"] = resolved
    os.environ["VIBECOMFY_OPENROUTER_BASE_URL"] = _TRANSPORT_BASE_URLS[resolved]
    return resolved


def _load_workflow(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"Workflow file not found: {path}")
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must contain a JSON object: {path}")
    return data


def run_headless_scenario(
    scenario: Mapping[str, Any],
    *,
    output_base: Path | str | None = None,
    tag: str = "agentic-run",
    transport: str | None = None,
) -> dict[str, Any]:
    """Run a single agentic scenario through the headless service.

    Parameters
    ----------
    scenario:
        Must contain at least ``query``.  Optional keys: ``graph``,
        ``workflow_path``, ``profile``, ``session_id``, ``dry_run``,
        ``apply``, ``network``, ``timeout``.
    output_base:
        Base directory for evidence.  Defaults to ``out/agentic``.
    tag:
        Run tag used to build the evidence directory name.
    transport:
        Explicit transport selector: ``"openrouter"`` or ``"native"``.
        ``None`` resolves to the deterministic harness default and never to an
        ambient credential.

    Returns
    -------
    dict
        A summary suitable for ``summary.json``.
    """
    _ensure_headless_env()
    _load_credential_env_file()
    _ensure_transport_env(transport)

    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.agent.service import run_headless

    query = str(scenario.get("query", "")).strip()
    if not query:
        raise ValueError("Scenario must contain a non-empty 'query'.")

    base = Path(output_base) if output_base is not None else Path("out") / "agentic"
    scenario_id = str(scenario.get("id", "scenario"))
    output_dir = base / tag / scenario_id

    graph = scenario.get("graph")
    if graph is not None and not isinstance(graph, dict):
        raise ValueError("Scenario `graph` must be a JSON object when supplied.")
    if graph is not None and scenario.get("workflow_path") is not None:
        raise ValueError("Scenario accepts either `graph` or `workflow_path`, not both.")
    if graph is None:
        graph = _load_workflow(scenario.get("workflow_path"))

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
        interaction_mode=scenario.get("interaction_mode"),
        max_batches=scenario.get("max_batches"),
    )

    result = run_headless(request, entrypoint="live_agentic_harness")
    summary: dict[str, Any] = {
        "scenario_id": scenario_id,
        "status": result.status,
        "ok": result.ok,
        "output_dir": str(output_dir),
        "readiness": result.readiness,
        "error": result.error,
        "deepseek_usage": result.response.get("deepseek_usage", {}),
        "deepseek_est_cost_usd": result.response.get("deepseek_est_cost_usd"),
        "deepseek_cost_basis": result.response.get("deepseek_cost_basis"),
        "model_attempts": result.response.get("model_attempts", []),
    }
    # Persist the typed parse reason from the executor's model_response artifact
    # so the runner's infra reclassification is evidence-based (parse_reason ==
    # "empty" AND completion_tokens == 0), never phrase-matching alone.
    parse_reason = _extract_parse_reason(result.response)
    if parse_reason is not None:
        summary["parse_reason"] = parse_reason
    return summary


def _extract_parse_reason(response: Mapping[str, Any]) -> str | None:
    """Read ``parse_reason`` from the executor failure's model_response artifact.

    Shape: ``response.report.executor.model_response.turns[0].error.parse_reason``.
    Returns None when the attempt did not fail on a model response or the
    artifact is missing — absence is NOT evidence of an empty response.
    """
    report = response.get("report")
    if not isinstance(report, Mapping):
        return None
    executor = report.get("executor")
    if not isinstance(executor, Mapping):
        return None
    model_response = executor.get("model_response")
    if not isinstance(model_response, Mapping):
        return None
    turns = model_response.get("turns")
    if not isinstance(turns, (list, tuple)) or not turns:
        return None
    first = turns[0]
    if not isinstance(first, Mapping):
        return None
    error = first.get("error")
    if not isinstance(error, Mapping):
        return None
    value = error.get("parse_reason")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()
    request_payload = dict(payload)
    if "query" not in request_payload and isinstance(request_payload.get("task"), str):
        request_payload["query"] = request_payload["task"]
    route = str(request_payload.get("route") or "").strip().lower()
    route_profile = {
        "openai-codex": "openai",
        "codex": "openai",
        "openrouter": "openrouter",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "opensource": "opensource",
    }.get(route)
    if route_profile is not None:
        # A recognized provider route owns its executor profile.  Do not let a
        # stale or custom client claim OpenRouter while selecting another
        # provider's stages underneath it.
        request_payload["profile"] = route_profile
    elif "profile" not in request_payload:
        request_payload["profile"] = "default"
    return request_payload


def _handle_agent_executor_submit(
    payload: Any,
    *,
    client_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    from vibecomfy.executor.contracts import ExecutorRequest  # noqa: PLC0415
    from vibecomfy.executor.core import run_executor  # noqa: PLC0415

    if not isinstance(payload, dict):
        return (
            _failure_response(
                "agent_executor",
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "agent_executor",
                    agent_failure_context={"explanation": "Request body must be a JSON object."},
                ),
            ),
            400,
        )

    # ── T2: Normalise session_id before it reaches ExecutorRequest ────────
    # ExecutorRequest.from_payload() accepts a raw session_id string, but the
    # route layer must sanitise it first so that no path-component attack can
    # be embedded in a durable turn allocation or response-writer path downstream.
    safe_payload = dict(payload)
    raw_session_id = safe_payload.get("session_id")
    if isinstance(raw_session_id, str):
        safe_payload["session_id"] = normalize_session_id(raw_session_id)
    elif "session_id" in safe_payload:
        # Non-string sentinel values (null, numbers, etc.) → strip entirely.
        del safe_payload["session_id"]

    try:
        request = ExecutorRequest.from_payload(_executor_request_payload(safe_payload))
    except Exception as exc:
        return _failure_response("agent_executor", classify_failure("agent_executor", exc)), 400
    result = run_executor(request, client_id=client_id)
    response = _serialize_executor_result(result)
    # T7/T9: Durable turn writer for executor-only non-applyable turns
    # (clarify/inspect/respond/research).  When the executor skips implementation,
    # no durable response is produced by handle_agent_edit.  Allocate a lightweight
    # turn and write request/response/chat artifacts so the frontend can rehydrate
    # from canonical durable storage (SD1, SD2).
    response = _maybe_write_executor_only_durable_turn(
        response=response,
        result=result,
        payload=safe_payload,
        request=request,
    )
    status = 200 if response.get("ok") is not False else 500
    return response, status


def _maybe_write_executor_only_durable_turn(
    *,
    response: dict[str, Any],
    result: Any,
    payload: dict[str, Any],
    request: Any,
) -> dict[str, Any]:
    return maybe_write_executor_only_durable_turn(
        response=response,
        result=result,
        accept_turn,
        finalize_turn_transaction as _session_finalize_turn_transaction,
        normalize_session_id as _safe_session_id,
        prepare_turn_transaction as _session_prepare_turn_transaction,
        rebaseline_session,
        reconcile_turn_transactions as _session_reconcile_turn_transactions,
        rollback_turn_transaction as _session_rollback_turn_transaction,
    )
    from .contracts import (
        FailureKind as _FK,
        classify_failure as _classify_failure,
        ensure_agent_edit_response_contract as _ensure_contract,
        failure_envelope as _failure_envelope,
    )

    _SESSION_ROOT = _Path(_EDIT_SESSION_ROOT)

    def _client_id_from_payload(payload: Any) -> str | None:
        cid = payload.get("client_id") if isinstance(payload, dict) else None
        if isinstance(cid, str) and cid.strip():
            return cid
        return None

    def _session_id_from_query(request) -> str:  # type: ignore[no-untyped-def]
        return _safe_session_id(request.query.get("session_id"))

    def _json_error(message: str, stage: str = "agent_edit", status: int = 400):  # type: ignore[no-untyped-def]
        return _web.json_response(
            _ensure_contract(
                _failure_envelope(
                    _FK.MISSING_REQUIRED_FIELD,
                    stage,
                    agent_failure_context={"explanation": message},
                ).to_dict(),
                stage=stage,
            ),
            status=status,
        )

    @app.routes.post("/vibecomfy/agent-edit")
    async def _agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result, status = await asyncio.to_thread(
                _handle_agent_executor_submit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("run_executor returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result, status=status)

    @app.routes.post("/vibecomfy/agent-executor")
    async def _agent_executor_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_executor")

exec
/bin/zsh -lc "rg -n \"class HeadlessAgentRequest|ExecutorRequest\\(\" vibecomfy/agent/contracts.py vibecomfy/agent/service.py | sed -n '1,220p'
sed -n '1,190p' vibecomfy/agent/contracts.py
rg -n \"executor_request|pipeline|ExecutorRequest\" vibecomfy/agent/service.py | sed -n '1,220p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
vibecomfy/agent/contracts.py:62:class HeadlessAgentRequest:
vibecomfy/agent/contracts.py:177:        return ExecutorRequest(
"""Contracts for the headless VibeComfy agent CLI/API surface.

These types are intentionally separate from :class:`vibecomfy.executor.contracts.ExecutorRequest`
so that headless-only concerns (output directory, live/dry-run/apply flags, timeouts) do not
leak into the frozen HTTP executor contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.executor.stage_contracts import NeedsInput


def _require_optional_str(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"HeadlessAgentRequest `{field_name}` must be a string or null.")
    return value


def _parse_bool(value: Any, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"HeadlessAgentRequest `{field_name}` must be a boolean.")


def _parse_extra(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("HeadlessAgentRequest `extra` must be a mapping or null.")
    return dict(value)


def _load_workflow_graph(path: str | Path) -> dict[str, Any]:
    workflow_path = Path(path)
    if not workflow_path.is_file():
        raise ValueError(f"Workflow file not found: {workflow_path}")
    try:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Workflow file is not valid JSON: {workflow_path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must contain a JSON object: {workflow_path}")
    return data


@dataclass(frozen=True)
class HeadlessAgentRequest:
    """Headless request shape for ``python -m vibecomfy.agent``.

    ``query`` is the only required field.  The graph may be supplied as a dict
    or loaded from a JSON file by the CLI.  Provider/model routing is resolved
    from the executor profile, not from new fields on this contract.

    Flags
    -----
    * ``live=True`` allows real model calls (still gated by provider readiness).
    * ``dry_run=True`` forces classify-only execution: no research, implement,
      or reply phases run, but the classification decision is still produced
      by a model call unless the profile/classifier short-circuits.
    * ``apply=True`` marks the caller's intent to apply an edited graph when
      the executor produces a candidate.  It does not bypass eligibility gates.
    * ``network=True`` permits research phases to call external services.
    * ``timeout`` overrides the default per-turn timeout when supported.
    * ``additive=True`` marks the request as an additive restore (the caller
      intentionally removed a feature and now asks to re-add it).  This is an
      explicit signal to the revise pipeline: the only guard it relaxes is the
      pre-edit "input graph has dangling/absent endpoints -> refuse to compound"
      precondition, and only when the dangling/absent endpoints are exactly the
      gap the requested node would fill.  All post-edit IR-compile validation,
      the collateral fence, and every gate in ``gates.py`` remain enforced.
    """

    query: str
    graph: dict[str, Any] | None = None
    workflow_id: str | None = None
    session_id: str | None = None
    profile: str | None = None
    idempotency_key: str | None = None
    output_dir: Path | str | None = None
    live: bool = True
    dry_run: bool = False
    apply: bool = False
    network: bool = True
    timeout: float | None = None
    additive: bool = False
    # Explicit interaction contract for diagnosis/advice turns:
    # ``"answer_only"`` declares that this interaction must never produce a
    # graph edit (the executor routes to agent-owned research + semantic
    # reply regardless of classification).  Deliberately NOT inferred from
    # ``apply`` — that flag only says whether a candidate is applied, not
    # whether editing is permitted.  None = ordinary interaction.
    interaction_mode: str | None = None
    # Batch-REPL per-request turn budget (PR-D).  Integer 1..250; None =
    # default 50.  Forwarded through to_executor_request → implement payload.
    max_batches: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("HeadlessAgentRequest requires a non-empty string `query`.")
        graph = self.graph
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("HeadlessAgentRequest `graph` must be a dict or null.")
        if self.output_dir is not None and not isinstance(self.output_dir, (str, Path)):
            raise ValueError("HeadlessAgentRequest `output_dir` must be a string/Path or null.")
        if self.timeout is not None:
            try:
                timeout = float(self.timeout)
            except (TypeError, ValueError) as exc:
                raise ValueError("HeadlessAgentRequest `timeout` must be a number.") from exc
            if timeout <= 0:
                raise ValueError("HeadlessAgentRequest `timeout` must be greater than zero.")
            object.__setattr__(self, "timeout", timeout)
        object.__setattr__(self, "query", self.query.strip())
        object.__setattr__(self, "workflow_id", _require_optional_str(self.workflow_id, field_name="workflow_id"))
        object.__setattr__(self, "session_id", _require_optional_str(self.session_id, field_name="session_id"))
        object.__setattr__(self, "profile", _require_optional_str(self.profile, field_name="profile"))
        object.__setattr__(
            self,
            "idempotency_key",
            _require_optional_str(self.idempotency_key, field_name="idempotency_key"),
        )
        if not isinstance(self.live, bool):
            raise ValueError("HeadlessAgentRequest `live` must be a boolean.")
        if not isinstance(self.dry_run, bool):
            raise ValueError("HeadlessAgentRequest `dry_run` must be a boolean.")
        if not isinstance(self.apply, bool):
            raise ValueError("HeadlessAgentRequest `apply` must be a boolean.")
        if not isinstance(self.network, bool):
            raise ValueError("HeadlessAgentRequest `network` must be a boolean.")
        if not isinstance(self.additive, bool):
            raise ValueError("HeadlessAgentRequest `additive` must be a boolean.")
        if self.interaction_mode is not None and not isinstance(self.interaction_mode, str):
            raise ValueError(
                "HeadlessAgentRequest `interaction_mode` must be a string or null."
            )
        if self.max_batches is not None:
            from vibecomfy.executor.contracts import coerce_max_batches  # noqa: PLC0415

            object.__setattr__(
                self,
                "max_batches",
                coerce_max_batches(self.max_batches, field_name="max_batches"),
            )
        object.__setattr__(self, "extra", dict(self.extra or {}))

    @property
    def output_dir_path(self) -> Path | None:
        if self.output_dir is None:
            return None
        return Path(self.output_dir)

    def to_executor_request(self) -> Any:
        """Return a frozen :class:`ExecutorRequest` from this headless request."""
        from vibecomfy.executor.contracts import ExecutorRequest  # noqa: PLC0415
        from vibecomfy.comfy_nodes.agent.session import normalize_session_id  # noqa: PLC0415

        session_id = self.session_id
        if session_id is not None:
            session_id = normalize_session_id(session_id)

        return ExecutorRequest(
            query=self.query,
            graph=self.graph,
            workflow_id=self.workflow_id,
            session_id=session_id,
            profile=self.profile,
            idempotency_key=self.idempotency_key,
            interaction_mode=self.interaction_mode,
            max_batches=self.max_batches,
        )

    def resolve_provider_readiness_kwargs(self, *, stage: str = "classify") -> dict[str, str | None]:
        """Resolve provider readiness arguments from the configured executor profile."""
        from vibecomfy.executor.profiles import load_profile  # noqa: PLC0415
159:        executor_request = request.to_executor_request()
222:        executor_request,

exec
/bin/zsh -lc "sed -n '220,390p' tests/live_agentic_harness/scenario_manifest.py
rg -n \"scenfails57|scenario_count|50|comparison|differential|baseline\" tests/live_agentic_harness docs tools scripts | sed -n '1,360p'
find tests/live_agentic_harness/scenfails57 -maxdepth 1 -type f | wc -l" in /private/tmp/vc-twostep
 succeeded in 0ms:
            if source_path.resolve() != expected_source_path.resolve():
                raise ScenarioManifestError(f"source workflow path mismatch for {scenario_id}")
            if not source_path.is_file():
                raise ScenarioManifestError(f"source workflow is missing for {scenario_id}: {source_path}")
            expected_source_id = str(
                (scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem
            )
            if source.get("id") != expected_source_id:
                raise ScenarioManifestError(f"source workflow id mismatch for {scenario_id}")
            actual_source_hash = sha256_file(source_path)
            if actual_source_hash != source.get("sha256"):
                raise ScenarioManifestError(
                    f"source workflow hash mismatch for {scenario_id}: "
                    f"expected {source.get('sha256')}, got {actual_source_hash}"
                )
        elif source is not None:
            raise ScenarioManifestError(f"unexpected source workflow metadata for {scenario_id}")
        if inclusion_status == "included":
            selected.append(path)

    declared_count = manifest.get("scenario_count")
    if declared_count != len(selected):
        raise ScenarioManifestError(
            f"scenario_count mismatch: expected {declared_count}, selected {len(selected)}"
        )
    discovered = {
        _repo_relative(path, repo=repo)
        for path in scenarios_dir.iterdir()
        if path.suffix in DESCRIPTOR_SUFFIXES
    }
    unmanifested = sorted(discovered - seen_paths)
    if unmanifested:
        raise ScenarioManifestError(
            "unmanifested scenario descriptor(s): " + ", ".join(unmanifested)
        )
    missing_from_directory = sorted(seen_paths - discovered)
    if missing_from_directory:
        raise ScenarioManifestError(
            "manifested scenario descriptor(s) missing from directory: "
            + ", ".join(missing_from_directory)
        )
    return selected
tests/live_agentic_harness/scenfails41/video-seedvr2-video-upscaling-workflow-052e59.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tests/live_agentic_harness/scenfails41/image-image-comparison-and-enhancement-with-florence-007018.json:2:  "id": "image-image-comparison-and-enhancement-with-florence-007018",
tests/live_agentic_harness/scenfails41/image-image-comparison-and-enhancement-with-florence-007018.json:25:      "image-comparison",
tests/live_agentic_harness/scenfails41/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/enumerate_github_workflows.py:88:            if 500 <= error.code < 600:
scripts/enumerate_github_workflows.py:383:                if idx % 50 == 0:
tests/live_agentic_harness/scenfails41/video-image-to-video-with-svd-and-webp-output-1882aa.json:58:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/b07_transport_probe.py:115:        "scenario_count": len(entries),
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:2:  "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:4:  "workflow_path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails41/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json:35:    "source_workflow_id": "506ebdde037e22d8",
scripts/runpod_corpus_matrix.py:176:printf 'id\tmedia\tstatus\tbaseline_seconds\tconvert_seconds\tvalidate_seconds\tvibecomfy_seconds\tmedia_files\tbytes\tfailure\n' > out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:317:      # Comfy text/sampler nodes, so the baseline must run with its
scripts/runpod_corpus_matrix.py:345:        # HiddenSwitch baseline override only targets image text encoders, so
scripts/runpod_corpus_matrix.py:355:  baseline_log="out/corpus_matrix/logs/${{id}}.baseline.log"
scripts/runpod_corpus_matrix.py:356:  if run_with_media_watch "$baseline_log" "out/corpus_matrix/comfyui/$id" "$workflow_timeout" "$COMFY" run-workflow "$work_wf" --cwd . --input-directory input --output-directory "out/corpus_matrix/comfyui/$id" "${{workflow_override_args[@]}}" $comfy_extra_args --preview-method none --disable-progress; then
scripts/runpod_corpus_matrix.py:357:    baseline_seconds=$(( $(date +%s) - start ))
scripts/runpod_corpus_matrix.py:359:    baseline_seconds=$(( $(date +%s) - start ))
scripts/runpod_corpus_matrix.py:360:    baseline_media_files=$(count_media_files "out/corpus_matrix/comfyui/$id")
scripts/runpod_corpus_matrix.py:361:    if [ "$baseline_media_files" -gt 0 ]; then
scripts/runpod_corpus_matrix.py:362:      echo "baseline_nonzero_after_media id=$id files=$baseline_media_files" >> out/corpus_matrix/live.log
scripts/runpod_corpus_matrix.py:364:    failure=$(clean_failure "$baseline_log")
scripts/runpod_corpus_matrix.py:365:    echo -e "$id\\t$media\\tbaseline_failed\\t$baseline_seconds\\t0\\t0\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:379:    echo -e "$id\\t$media\\tconvert_failed\\t$baseline_seconds\\t$convert_seconds\\t0\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:396:    echo -e "$id\\t$media\\tvalidate_failed\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:413:    echo -e "$id\\t$media\\tvibecomfy_failed\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t$vibecomfy_seconds\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:421:    echo -e "$id\\t$media\\tno_new_vibecomfy_output\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t$vibecomfy_seconds\\t$media_files\\t$bytes\\tno new output file appeared under output/" >> out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:423:    echo -e "$id\\t$media\\tok\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t$vibecomfy_seconds\\t$media_files\\t$bytes\\t" >> out/corpus_matrix/results.tsv
scripts/runpod_corpus_matrix.py:447:printf 'id\tmedia\tstatus\tbaseline_seconds\tconvert_seconds\tvalidate_seconds\tvibecomfy_seconds\tmedia_files\tbytes\tfailure\n' > out/corpus_matrix/ready_results.tsv
scripts/runpod_corpus_matrix.py:824:    ], 500_000_000),
scripts/demo_wrapper_codegen.py:19:canonical comparison is wf.node() (with class_type as a string) vs the
tests/live_agentic_harness/scenfails41/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:61:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/build_eb45e_fixture.mjs:18:  "/Users/peteromalley/Documents/reigh-workspace/ComfyUI/out/editor_sessions/eb45e0ef50e146c6985417bf1449e96a/turns/0001";
scripts/build_eb45e_fixture.mjs:45:const sessionId = "eb45e0ef50e146c6985417bf1449e96a";
scripts/build_eb45e_fixture.mjs:111:      "/Users/peteromalley/Documents/reigh-workspace/ComfyUI/out/editor_sessions/eb45e0ef50e146c6985417bf1449e96a/turns/0001",
docs/vibecomfy_executor_embedded_plan.md:277:Direct search is deterministic, fast, and sufficient for most ComfyUI workflow questions. Agentic research can be added as a phase variant once the baseline works.
scripts/fireworks_null_strip_proxy.py:92:                self.send_response(502)
tests/live_agentic_harness/scenfails41/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tests/live_agentic_harness/scenfails41/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:60:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/live_agentic_watchdog.py:276:              scenario_count=summary.get("scenario_count"),
scripts/live_agentic_watchdog.py:416:                block.append(f"- response: {_trim(sig, 500)}".replace("\n", " "))
scripts/live_agentic_watchdog.py:553:    return _trim("## Turn " + chunks[-1].rstrip(), 1500)
scripts/live_agentic_watchdog.py:663:        log_event(logger, "codex_error", round=round_num, error=_trim(str(exc), 500))
scripts/live_agentic_watchdog.py:689:# Safety: round-start baseline, editable-surface gate, import check, git
scripts/live_agentic_watchdog.py:696:def capture_round_baseline() -> tuple[str, set[str]]:
scripts/live_agentic_watchdog.py:711:def changes_since(round_baseline: tuple[str, set[str]]) -> set[str]:
scripts/live_agentic_watchdog.py:714:    tree_sha, start_untracked = round_baseline
scripts/live_agentic_watchdog.py:728:def safety_gate(round_baseline: tuple[str, set[str]],
scripts/live_agentic_watchdog.py:732:    for p in sorted(changes_since(round_baseline)):
scripts/live_agentic_watchdog.py:746:def revert_round(round_baseline: tuple[str, set[str]]) -> None:
scripts/live_agentic_watchdog.py:749:    tree_sha, _start_untracked = round_baseline
scripts/live_agentic_watchdog.py:763:def git_commit(round_baseline: tuple[str, set[str]], allow_test_edits: bool,
scripts/live_agentic_watchdog.py:767:    changed = changes_since(round_baseline)
scripts/live_agentic_watchdog.py:784:        return "(no run-start baseline)"
scripts/live_agentic_watchdog.py:795:    brief: str, round_baseline: tuple[str, set[str]], args: argparse.Namespace,
scripts/live_agentic_watchdog.py:812:                revert_round(round_baseline)
scripts/live_agentic_watchdog.py:816:        ok, violations = safety_gate(round_baseline, args.allow_test_edits)
scripts/live_agentic_watchdog.py:824:            revert_round(round_baseline)
scripts/live_agentic_watchdog.py:849:    # 1. capture the round-start baseline (tree + untracked) for the safety gate / commit / revert
scripts/live_agentic_watchdog.py:850:    round_baseline = capture_round_baseline()
scripts/live_agentic_watchdog.py:864:            summary = {"tag": tag, "scenario_count": 0, "overall_success": False,
scripts/live_agentic_watchdog.py:891:        codex_record = repair_with_retry(brief, round_baseline,
scripts/live_agentic_watchdog.py:912:        sha = git_commit(round_baseline, args.allow_test_edits,
scripts/live_agentic_watchdog.py:1028:    # edits across all rounds (vs this baseline). Robust to Codex self-commits.
scripts/live_agentic_watchdog.py:1029:    run_start_commit = capture_round_baseline()[0]
scripts/runpod_model_matrix.py:56:printf 'source\tid\tstatus\tbaseline_seconds\tconvert_seconds\tvibecomfy_seconds\tmedia_files\tbytes\tfailure\n' > out/model_matrix/results.tsv
scripts/runpod_model_matrix.py:64:  baseline_log="out/model_matrix/${{id}}.baseline.log"
scripts/runpod_model_matrix.py:65:  if timeout 1800 comfyui run-workflow "$wf" --all --cwd . --input-directory input --output-directory "out/model_matrix/comfyui/$id" --steps 1 --seed 123 --prompt "a compact red cube on a neutral background" --disable-progress --novram >"$baseline_log" 2>&1; then
scripts/runpod_model_matrix.py:66:    baseline_seconds=$(( $(date +%s) - start ))
scripts/runpod_model_matrix.py:68:    baseline_seconds=$(( $(date +%s) - start ))
scripts/runpod_model_matrix.py:69:    failure=$(tail -40 "$baseline_log" | tr '\\t\\n' '  ' | cut -c1-600)
scripts/runpod_model_matrix.py:70:    echo -e "$source\\t$id\\tbaseline_failed\\t$baseline_seconds\\t0\\t0\\t0\\t0\\t$failure" >> out/model_matrix/results.tsv
scripts/runpod_model_matrix.py:81:    echo -e "$source\\t$id\\tconvert_failed\\t$baseline_seconds\\t$convert_seconds\\t0\\t0\\t0\\t$failure" >> out/model_matrix/results.tsv
scripts/runpod_model_matrix.py:92:    echo -e "$source\\t$id\\tvibecomfy_failed\\t$baseline_seconds\\t$convert_seconds\\t$vibecomfy_seconds\\t0\\t0\\t$failure" >> out/model_matrix/results.tsv
scripts/runpod_model_matrix.py:98:  echo -e "$source\\t$id\\tok\\t$baseline_seconds\\t$convert_seconds\\t$vibecomfy_seconds\\t$media_files\\t$bytes\\t" >> out/model_matrix/results.tsv
tests/live_agentic_harness/scenfails41/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json:58:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/upload_external_workflows_to_hivemind.py:460:            retryable = exc.code == 429 or 500 <= exc.code < 600
scripts/upload_external_workflows_to_hivemind.py:585:            retryable = exc.code == 429 or 500 <= exc.code < 600
scripts/check_b02_rich_preservation.py:61:# comparisons by contract.
scripts/check_b02_rich_preservation.py:540:    Deterministic: files are processed in sorted order and all set comparisons
docs/failure-analysis/pre_existing_bug.md:16:| `multi-animatediff-video-face-swapping-with-deflicker-506ebd` | **Failure:** `gates.queue_validate_ok: false` — the assessor flags this as an error because `expect_graph_changed: true` |
docs/failure-analysis/pre_existing_bug.md:28:For comparison, the iter5 run (57/100, before the regression):
docs/failure-analysis/pre_existing_bug.md:63:cp tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json "$TMP/"
tests/live_agentic_harness/scenfails41/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:58:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/scan_banodoco_discord_workflows.py:84:            if 500 <= error.code < 600:
scripts/scan_banodoco_discord_workflows.py:200:        if offset % 25000 == 0:
scripts/scan_banodoco_discord_workflows.py:480:            if index % 250 == 0:
tests/live_agentic_harness/scenfails41/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:61:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tools/check_strict_ready_templates.py:162:        comparison = compare_public_contracts(
tools/check_strict_ready_templates.py:172:                message=f"Could not build template for static contract comparison: {type(exc).__name__}: {exc}",
tools/check_strict_ready_templates.py:181:    for field, values in sorted(comparison.items()):
docs/failure-analysis/widget_name_resolution_phase3_impl.md:34:   (quarantined baseline failure — No regressions.)
scripts/b09_reducer.py:46:    "image-inpainting-with-differential-diffusion-and-rea-1d414c",  # INPAINT: no denoise field
tests/live_agentic_harness/scenfails41/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json:60:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tests/live_agentic_harness/scenario_manifest.json:4:  "scenario_count": 100,
tests/live_agentic_harness/scenario_manifest.json:29:        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenario_manifest.json:35:      "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
tests/live_agentic_harness/scenario_manifest.json:48:      "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
tests/live_agentic_harness/scenario_manifest.json:74:      "descriptor_sha256": "5fe9bba69049a4849346c505321eac3e7a4c44b212b67d8e940de12f92874bbe",
tests/live_agentic_harness/scenario_manifest.json:100:      "descriptor_sha256": "5f131e3f6743491dc8ce59b63d5e52d50091d8f4bf7c199f76b130ada6f2214c",
tests/live_agentic_harness/scenario_manifest.json:113:      "descriptor_sha256": "78500beb98600be76f05723fee97c4acb2894a7b7d71b6217fc176fc04cd461f",
tests/live_agentic_harness/scenario_manifest.json:165:      "descriptor_sha256": "f48a0350bc94e328d3aaf0d81cd8eb67fa0a95c458c61b215ea844b4e802b248",
tests/live_agentic_harness/scenario_manifest.json:191:      "descriptor_sha256": "aa3859ee4661d125044bdb9d1ba907ed3944c1e28010cacbd0826ed0baea1de4",
tests/live_agentic_harness/scenario_manifest.json:198:        "sha256": "cf18d35e10586b45a798da007c09965f0abd89a5339a1d15507605c651fcdc22"
tests/live_agentic_harness/scenario_manifest.json:224:        "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenario_manifest.json:243:      "descriptor_sha256": "4e55deceb5b3cb551aea17a49436b5749ee5a9ef0c8109239503c7297cf242ff",
tests/live_agentic_harness/scenario_manifest.json:341:        "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scenario_manifest.json:380:        "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scenario_manifest.json:393:        "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenario_manifest.json:397:      "id": "image-image-comparison-and-enhancement-with-florence-007018",
tests/live_agentic_harness/scenario_manifest.json:398:      "path": "tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json",
tests/live_agentic_harness/scenario_manifest.json:406:        "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenario_manifest.json:445:        "sha256": "08cee15268021cccedfae4b5cf7c9c689a135fb20cf83861a72d433471250b1d"
tests/live_agentic_harness/scenario_manifest.json:451:      "descriptor_sha256": "12229915b1fc6a91fa40dbd8217de299577e02974cae4550af8f090cfa52797c",
tests/live_agentic_harness/scenario_manifest.json:475:      "id": "image-inpainting-with-differential-diffusion-and-rea-1d414c",
tests/live_agentic_harness/scenario_manifest.json:476:      "path": "tests/live_agentic_harness/scenarios/image-inpainting-with-differential-diffusion-and-rea-1d414c.json",
tests/live_agentic_harness/scenario_manifest.json:497:        "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenario_manifest.json:555:      "descriptor_sha256": "04bf444c3c44edc850a0a4c9a19a3664b31fd0d8ff4cff13826befd4f8d06080",
tests/live_agentic_harness/scenario_manifest.json:642:      "descriptor_sha256": "2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457",
tests/live_agentic_harness/scenario_manifest.json:655:      "descriptor_sha256": "8f389a659ed1fcb982bd5512485075017864c4a5332e9dc23c29d7d7c88e6eab",
tests/live_agentic_harness/scenario_manifest.json:662:        "sha256": "c148b3b74fb11eb408e6cfb2150189075d1b122b64eb6a341775267404c62af9"
tests/live_agentic_harness/scenario_manifest.json:666:      "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenario_manifest.json:667:      "path": "tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json",
tests/live_agentic_harness/scenario_manifest.json:673:        "id": "506ebdde037e22d8",
tests/live_agentic_harness/scenario_manifest.json:674:        "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenario_manifest.json:688:        "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scenario_manifest.json:759:      "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scenario_manifest.json:766:        "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenario_manifest.json:779:        "sha256": "f344d3cb450634d608fb63fb8296e1b6cb49f84481e2adc534be7d198d7fac72"
tests/live_agentic_harness/scenario_manifest.json:792:        "sha256": "287ee5ba6b895449763a1f6589d6d5b66fa225844ace8892e957c62d07504d22"
tests/live_agentic_harness/scenario_manifest.json:824:      "descriptor_sha256": "9ae4a4234122da3701b9f19c218ee9f2b2d705f87cc506a2f3a8ed57f6218979",
tests/live_agentic_harness/scenario_manifest.json:831:        "sha256": "b3356f4640f638998d1eae50dd2ac775342c649d6d3a77940b93d6c72b762189"
tests/live_agentic_harness/scenario_manifest.json:837:      "descriptor_sha256": "e014838aa1dca64cd50ac288895928d490e197d5902c6dd37176981bb8e4466d",
tests/live_agentic_harness/scenario_manifest.json:922:        "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenario_manifest.json:928:      "descriptor_sha256": "5cd0755b3e83818619ba7e8dd40d360a2e419254b6f5394fd50eaca0de4dca80",
tests/live_agentic_harness/scenario_manifest.json:989:      "descriptor_sha256": "521376ee3a0b3c568644df355f791036ca6a034c6e9b0f4f4e78450c1953928d",
tests/live_agentic_harness/scenario_manifest.json:994:        "id": "59502aed6ad75d87",
tests/live_agentic_harness/scenario_manifest.json:995:        "path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scenario_manifest.json:1015:      "descriptor_sha256": "60a19bcef50943ef4134e0282d1d14a312df987354e5e3a03c0f380854d942e0",
tests/live_agentic_harness/scenario_manifest.json:1035:        "sha256": "0cf39ff1502b0029829a20c609b8a0caee6bfd45ee9472e327bdfdb95acf827c"
tests/live_agentic_harness/scenario_manifest.json:1041:      "descriptor_sha256": "d52d2cf1efae560d5cb49cd507321c8ae20290ecb723ad06b5674d6914bf59a1",
tests/live_agentic_harness/scenario_manifest.json:1087:        "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenario_manifest.json:1184:      "descriptor_sha256": "c18f241b403ed7d3c533330a9f4851f6e0870bb450c9d6edda713db827785be0",
tests/live_agentic_harness/scenario_manifest.json:1230:        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenario_manifest.json:1293:        "id": "71f825e4550c95b7",
tests/live_agentic_harness/scenario_manifest.json:1294:        "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenario_manifest.json:1295:        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
tests/live_agentic_harness/scenario_manifest.json:1311:        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenario_manifest.json:1376:        "sha256": "cf18d35e10586b45a798da007c09965f0abd89a5339a1d15507605c651fcdc22"
tests/live_agentic_harness/scenario_manifest.json:1386:        "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenario_manifest.json:1431:        "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scenario_manifest.json:1446:        "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scenario_manifest.json:1451:        "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenario_manifest.json:1453:      "image-image-comparison-and-enhancement-with-florence-007018": {
tests/live_agentic_harness/scenario_manifest.json:1456:        "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenario_manifest.json:1471:        "sha256": "08cee15268021cccedfae4b5cf7c9c689a135fb20cf83861a72d433471250b1d"
tests/live_agentic_harness/scenario_manifest.json:1483:      "image-inpainting-with-differential-diffusion-and-rea-1d414c": {
tests/live_agentic_harness/scenario_manifest.json:1491:        "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenario_manifest.json:1551:        "sha256": "c148b3b74fb11eb408e6cfb2150189075d1b122b64eb6a341775267404c62af9"
tests/live_agentic_harness/scenario_manifest.json:1553:      "multi-animatediff-video-face-swapping-with-deflicker-506ebd": {
tests/live_agentic_harness/scenario_manifest.json:1554:        "source_workflow_id": "506ebdde037e22d8",
tests/live_agentic_harness/scenario_manifest.json:1555:        "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenario_manifest.json:1561:        "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scenario_manifest.json:1591:        "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenario_manifest.json:1596:        "sha256": "f344d3cb450634d608fb63fb8296e1b6cb49f84481e2adc534be7d198d7fac72"
tests/live_agentic_harness/scenario_manifest.json:1601:        "sha256": "287ee5ba6b895449763a1f6589d6d5b66fa225844ace8892e957c62d07504d22"
tests/live_agentic_harness/scenario_manifest.json:1616:        "sha256": "b3356f4640f638998d1eae50dd2ac775342c649d6d3a77940b93d6c72b762189"
tests/live_agentic_harness/scenario_manifest.json:1651:        "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenario_manifest.json:1674:        "source_workflow_id": "59502aed6ad75d87",
tests/live_agentic_harness/scenario_manifest.json:1675:        "path": "tests/fixtures/live_agentic_corpus/59502aed6ad75d87.json",
tests/live_agentic_harness/scenario_manifest.json:1691:        "sha256": "0cf39ff1502b0029829a20c609b8a0caee6bfd45ee9472e327bdfdb95acf827c"
tests/live_agentic_harness/scenario_manifest.json:1711:        "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenario_manifest.json:1766:        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenario_manifest.json:1789:        "source_workflow_id": "71f825e4550c95b7",
tests/live_agentic_harness/scenario_manifest.json:1790:        "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenario_manifest.json:1791:        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
tests/live_agentic_harness/scenario_manifest.json:1807:      "scenario_count": 98,
docs/failure-analysis/cross_domain_over_rejection.md:28:For comparison, the iter5 run (57/100, before the regression):
scripts/agent-jury/schemas/verdict_schema.json:22:      "maxLength": 500,
scripts/agent-jury/schemas/verdict_schema.json:237:      "maxLength": 500,
scripts/b09_preflight.py:107:        "scenario_count": len(sources),
scripts/b09_preflight.py:141:    assert manifest["scenario_count"] == 100
scripts/b09_preflight.py:181:                "scenario_count": source_workflows["scenario_count"],
scripts/b09_preflight.py:203:            "scenario_count": 100,
scripts/b09_preflight.py:210:            "scenario_count": source_workflows["scenario_count"],
scripts/b09_preflight.py:226:                "out/agentic/ is absent -> no historical comparison, no "
tests/live_agentic_harness/scenfails57_manifest.json:3:  "scenario_root": "tests/live_agentic_harness/scenfails57",
tests/live_agentic_harness/scenfails57_manifest.json:4:  "scenario_count": 57,
tests/live_agentic_harness/scenfails57_manifest.json:8:      "path": "tests/live_agentic_harness/scenfails57/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json",
tests/live_agentic_harness/scenfails57_manifest.json:21:      "path": "tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-preview-workflow-cc0df7.json",
tests/live_agentic_harness/scenfails57_manifest.json:29:        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
tests/live_agentic_harness/scenfails57_manifest.json:34:      "path": "tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-retargeting-workflow-f65774.json",
tests/live_agentic_harness/scenfails57_manifest.json:35:      "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
tests/live_agentic_harness/scenfails57_manifest.json:47:      "path": "tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-rigging-from-image-352066.json",
tests/live_agentic_harness/scenfails57_manifest.json:48:      "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
tests/live_agentic_harness/scenfails57_manifest.json:60:      "path": "tests/live_agentic_harness/scenfails57/3d-3d-model-generation-and-rigging-workflow-90a1d5.json",
tests/live_agentic_harness/scenfails57_manifest.json:73:      "path": "tests/live_agentic_harness/scenfails57/3d-3d-shape-generation-and-export-workflow-8800a9.json",
tests/live_agentic_harness/scenfails57_manifest.json:86:      "path": "tests/live_agentic_harness/scenfails57/audio-acestep-audio-generation-with-detail-daemon-f0859f.json",
tests/live_agentic_harness/scenfails57_manifest.json:99:      "path": "tests/live_agentic_harness/scenfails57/audio-audio-processing-with-voice-tts-and-noise-remo-b80848.json",
tests/live_agentic_harness/scenfails57_manifest.json:112:      "path": "tests/live_agentic_harness/scenfails57/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json",
tests/live_agentic_harness/scenfails57_manifest.json:120:        "sha256": "50d0bae8056606a96cef8612a070d362eefefaf4863c1650a7ba073ae8cc3726"
tests/live_agentic_harness/scenfails57_manifest.json:125:      "path": "tests/live_agentic_harness/scenfails57/hotshot-16-frames-agent-edit.json",
tests/live_agentic_harness/scenfails57_manifest.json:138:      "path": "tests/live_agentic_harness/scenfails57/image-animatediff-video-from-images-with.json",
tests/live_agentic_harness/scenfails57_manifest.json:151:      "path": "tests/live_agentic_harness/scenfails57/image-animatediff-video-generation-with-vae-d20410.json",
tests/live_agentic_harness/scenfails57_manifest.json:164:      "path": "tests/live_agentic_harness/scenfails57/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json",
tests/live_agentic_harness/scenfails57_manifest.json:172:        "sha256": "205c6a0aa195069e3ee4add27e8625dee2894f6750a8ca38b95d25fbcd008865"
tests/live_agentic_harness/scenfails57_manifest.json:177:      "path": "tests/live_agentic_harness/scenfails57/image-face-detection-and-cropping-workflow-949658.json",
tests/live_agentic_harness/scenfails57_manifest.json:190:      "path": "tests/live_agentic_harness/scenfails57/image-flux-image-inpainting-and-compositing-with-con-00444a.json",
tests/live_agentic_harness/scenfails57_manifest.json:203:      "path": "tests/live_agentic_harness/scenfails57/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json",
tests/live_agentic_harness/scenfails57_manifest.json:211:        "sha256": "1639eab3d5038e907e2cc858031ddb436c056fb76974012fc0ce59940c475456"
tests/live_agentic_harness/scenfails57_manifest.json:216:      "path": "tests/live_agentic_harness/scenfails57/image-generates-a-2x2-seed-variation.json",
tests/live_agentic_harness/scenfails57_manifest.json:224:        "sha256": "fe550572488ea0190a95021290f93630055c0c1ebde95963bc4c15e9f4b83b01"
tests/live_agentic_harness/scenfails57_manifest.json:228:      "id": "image-image-comparison-and-enhancement-with-florence-007018",
tests/live_agentic_harness/scenfails57_manifest.json:229:      "path": "tests/live_agentic_harness/scenfails57/image-image-comparison-and-enhancement-with-florence-007018.json",
tests/live_agentic_harness/scenfails57_manifest.json:237:        "sha256": "11e3fb489c3cc8aee26f3d86e9d34cd6c59ad6affe650eb68a5389015104b2d4"
tests/live_agentic_harness/scenfails57_manifest.json:242:      "path": "tests/live_agentic_harness/scenfails57/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json",
tests/live_agentic_harness/scenfails57_manifest.json:255:      "path": "tests/live_agentic_harness/scenfails57/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json",
tests/live_agentic_harness/scenfails57_manifest.json:256:      "descriptor_sha256": "12229915b1fc6a91fa40dbd8217de299577e02974cae4550af8f090cfa52797c",
tests/live_agentic_harness/scenfails57_manifest.json:268:      "path": "tests/live_agentic_harness/scenfails57/image-kolors-image-generation-with-segs-detailer-and-d813fe.json",
tests/live_agentic_harness/scenfails57_manifest.json:276:        "sha256": "501fe619c5f4f686d93053390843ade4100e8c8b8b20556e68c35451a4afccc0"
tests/live_agentic_harness/scenfails57_manifest.json:281:      "path": "tests/live_agentic_harness/scenfails57/image-qwen-image-inpainting-with-controlnet-09fc64.json",
tests/live_agentic_harness/scenfails57_manifest.json:294:      "path": "tests/live_agentic_harness/scenfails57/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json",
tests/live_agentic_harness/scenfails57_manifest.json:307:      "path": "tests/live_agentic_harness/scenfails57/live-graph-explanation-smoke.json",
tests/live_agentic_harness/scenfails57_manifest.json:316:      "path": "tests/live_agentic_harness/scenfails57/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json",
tests/live_agentic_harness/scenfails57_manifest.json:329:      "path": "tests/live_agentic_harness/scenfails57/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json",
tests/live_agentic_harness/scenfails57_manifest.json:330:      "descriptor_sha256": "2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457",
tests/live_agentic_harness/scenfails57_manifest.json:341:      "id": "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
tests/live_agentic_harness/scenfails57_manifest.json:342:      "path": "tests/live_agentic_harness/scenfails57/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json",
tests/live_agentic_harness/scenfails57_manifest.json:348:        "id": "506ebdde037e22d8",
tests/live_agentic_harness/scenfails57_manifest.json:349:        "path": "external_workflows/corpus/506ebdde037e22d8.json",
tests/live_agentic_harness/scenfails57_manifest.json:355:      "path": "tests/live_agentic_harness/scenfails57/multi-animatediff-video-generation-with-controlnet-a7e2af.json",
tests/live_agentic_harness/scenfails57_manifest.json:363:        "sha256": "5d64cc12202fb36e3ca3b25b013712b78c1c08f077b18e450b8d31e6d670ec13"
tests/live_agentic_harness/scenfails57_manifest.json:368:      "path": "tests/live_agentic_harness/scenfails57/multi-crops-face-previews-it-sets.json",
tests/live_agentic_harness/scenfails57_manifest.json:381:      "path": "tests/live_agentic_harness/scenfails57/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json",
tests/live_agentic_harness/scenfails57_manifest.json:394:      "path": "tests/live_agentic_harness/scenfails57/multi-flux2-image-and-video-generation-with-outpaint-435de2.json",
tests/live_agentic_harness/scenfails57_manifest.json:407:      "path": "tests/live_agentic_harness/scenfails57/multi-image-to-video-generation-with-2.json",
tests/live_agentic_harness/scenfails57_manifest.json:408:      "descriptor_sha256": "cafe328c12d6ae6d74908354991a95c1da3fc5634149d5fa050a620d384b3819",
tests/live_agentic_harness/scenfails57_manifest.json:415:        "sha256": "a9d8ce67507977b3ceaeef81373cee4d77eb1f74693c1a1f15ee24a0e8591797"
tests/live_agentic_harness/scenfails57_manifest.json:420:      "path": "tests/live_agentic_harness/scenfails57/multi-image-to-video-with-upscaling-and-color-matchi-359848.json",
tests/live_agentic_harness/scenfails57_manifest.json:433:      "path": "tests/live_agentic_harness/scenfails57/multi-svd-image-to-video-with-animation-builder-99e2a9.json",
tests/live_agentic_harness/scenfails57_manifest.json:446:      "path": "tests/live_agentic_harness/scenfails57/multi-wan-vace-video-retargeting-driven.json",
tests/live_agentic_harness/scenfails57_manifest.json:459:      "path": "tests/live_agentic_harness/scenfails57/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json",
tests/live_agentic_harness/scenfails57_manifest.json:472:      "path": "tests/live_agentic_harness/scenfails57/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json",
tests/live_agentic_harness/scenfails57_manifest.json:485:      "path": "tests/live_agentic_harness/scenfails57/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json",
tests/live_agentic_harness/scenfails57_manifest.json:493:        "sha256": "b47c2b1f9b73a8c33e9e6fbd34857fea2359da47a3ee8542250e1bfeeaa51155"
tests/live_agentic_harness/scenfails57_manifest.json:498:      "path": "tests/live_agentic_harness/scenfails57/video-animatediff-video-to-video-with-controlnet-and-3c978e.json",
tests/live_agentic_harness/scenfails57_manifest.json:511:      "path": "tests/live_agentic_harness/scenfails57/video-animatediff-video-with-controlnet-and-depth-89b02a.json",
tests/live_agentic_harness/scenfails57_manifest.json:524:      "path": "tests/live_agentic_harness/scenfails57/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json",
tests/live_agentic_harness/scenfails57_manifest.json:525:      "descriptor_sha256": "60a19bcef50943ef4134e0282d1d14a312df987354e5e3a03c0f380854d942e0",
tests/live_agentic_harness/scenfails57_manifest.json:537:      "path": "tests/live_agentic_harness/scenfails57/video-image-to-video-with-svd-and-webp-output-1882aa.json",
tests/live_agentic_harness/scenfails57_manifest.json:538:      "descriptor_sha256": "d52d2cf1efae560d5cb49cd507321c8ae20290ecb723ad06b5674d6914bf59a1",
tests/live_agentic_harness/scenfails57_manifest.json:550:      "path": "tests/live_agentic_harness/scenfails57/video-inpaint-and-video-composition-with-spline-path-0c2716.json",
tests/live_agentic_harness/scenfails57_manifest.json:563:      "path": "tests/live_agentic_harness/scenfails57/video-ltx-video-with-audio-and-inpainting-b3ba8a.json",
tests/live_agentic_harness/scenfails57_manifest.json:571:        "sha256": "e5212e916469564f8e8ec57a52b5196f79eee9ac745013284377cc79cf9fc4b6"
tests/live_agentic_harness/scenfails57_manifest.json:576:      "path": "tests/live_agentic_harness/scenfails57/video-seedvr2-video-upscaling-workflow-052e59.json",
tests/live_agentic_harness/scenfails57_manifest.json:589:      "path": "tests/live_agentic_harness/scenfails57/video-svd-image-to-video-generation-fc240f.json",
tests/live_agentic_harness/scenfails57_manifest.json:602:      "path": "tests/live_agentic_harness/scenfails57/video-video-combine-with-image-loading-5b31ce.json",
tests/live_agentic_harness/scenfails57_manifest.json:615:      "path": "tests/live_agentic_harness/scenfails57/video-video-frame-by-frame-style.json",
tests/live_agentic_harness/scenfails57_manifest.json:628:      "path": "tests/live_agentic_harness/scenfails57/video-video-generation-from-resized-image.json",
tests/live_agentic_harness/scenfails57_manifest.json:641:      "path": "tests/live_agentic_harness/scenfails57/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json",
tests/live_agentic_harness/scenfails57_manifest.json:654:      "path": "tests/live_agentic_harness/scenfails57/video-video-loading-and-saving-workflow-1c7ad8.json",
tests/live_agentic_harness/scenfails57_manifest.json:667:      "path": "tests/live_agentic_harness/scenfails57/video-video-output-workflow-f855de.json",
tests/live_agentic_harness/scenfails57_manifest.json:668:      "descriptor_sha256": "c18f241b403ed7d3c533330a9f4851f6e0870bb450c9d6edda713db827785be0",
tests/live_agentic_harness/scenfails57_manifest.json:680:      "path": "tests/live_agentic_harness/scenfails57/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json",
tests/live_agentic_harness/scenfails57_manifest.json:693:      "path": "tests/live_agentic_harness/scenfails57/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json",
tests/live_agentic_harness/scenfails57_manifest.json:706:      "path": "tests/live_agentic_harness/scenfails57/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json",
tests/live_agentic_harness/scenfails57_manifest.json:714:        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
tests/live_agentic_harness/scenfails57_manifest.json:719:      "path": "tests/live_agentic_harness/scenfails57/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json",
tests/live_agentic_harness/scenfails57_manifest.json:732:      "path": "tests/live_agentic_harness/scenfails57/video-wanvideo-text-to-video-generation-71f825.json",
tests/live_agentic_harness/scenfails57_manifest.json:738:        "id": "71f825e4550c95b7",
tests/live_agentic_harness/scenfails57_manifest.json:739:        "path": "external_workflows/corpus/71f825e4550c95b7.json",
tests/live_agentic_harness/scenfails57_manifest.json:740:        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
scripts/enrich_workflow_summaries.py:26:    python scripts/enrich_workflow_summaries.py --limit 50
scripts/enrich_workflow_summaries.py:309:            retryable = exc.code == 429 or 500 <= exc.code < 600
tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json:61:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
docs/failure-analysis/widget_shape_guard.md:24:For comparison, the iter5 run (57/100, before the regression):
scripts/promote_demo_scenario.py:223:        case_id="3270acf50658",
tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
scripts/daily_agentic_workflow_scan.py:155:            "limit": "500",
scripts/daily_agentic_workflow_scan.py:413:    print(f"[upload] exit {upload.returncode}: {upload.stdout.strip()[-500:]}", file=sys.stderr)
docs/failure-analysis/variance.md:23:For comparison, the iter5 run (57/100, before the regression):
scripts/agent-jury/run_jury.sh:308:Keep it under 500 words. Use clear, direct language.
tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
docs/failure-analysis/PROPOSAL.md:11:| 03 | `audio_merge` | `baseline_rejected` | **INFRA** | Baseline failed on three IAMCCS “unknown class” errors before the agent ran; the campaign never enabled the resolver, so `baseline.py:93-94` never added `--resolve-on-demand`. | Enable on-demand schemas for campaign baseline, fixer, and candidate check; add a regression proving IAMCCS resolves through the public-source ladder. |
docs/failure-analysis/PROPOSAL.md:63:Make on-demand schema resolution the campaign default and propagate it to baseline, fixer authoring, and candidate `port check`; log which ladder rung/source resolved each missing class. Add an IAMCCS integration test and, if class-to-source discovery is the missing hop, fix that routing rather than declaring the class unsupported. Small-to-medium effort; **certain to remove case 03’s unknown-class baseline failure**, but the subsequent repair result is unproven.
docs/failure-analysis/PROPOSAL.md:83:3. **Enable and verify on-demand schemas end-to-end** — rerun 03. Impact: +1 runnable; likely repair opportunity. Confidence: certain on removing the baseline blocker, unknown on final oracle.
docs/failure-analysis/PROPOSAL.md:88:For the six currently runnable failures, this roadmap should move from zero passes to **four or five additional passes with high confidence**, with the sixth becoming a real test instead of an unknown-class baseline failure. The three invalid slots then need to earn their own results after re-pairing.
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json:2:  "id": "image-image-comparison-and-enhancement-with-florence-007018",
tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json:25:      "image-comparison",
tools/regenerate_snapshots.py:124:            comparisons: dict[str, tuple[str, str]] = {}
tools/regenerate_snapshots.py:129:                comparisons[suffix] = (committed, regenerated)
tools/regenerate_snapshots.py:136:                    print(_summarise(stem, ready_id, comparisons, updated=False))
tools/regenerate_snapshots.py:137:                    for suffix, (committed, regenerated) in comparisons.items():
tools/regenerate_snapshots.py:147:                    print(_summarise(stem, ready_id, comparisons, updated=False))
tools/regenerate_snapshots.py:152:                    print(_summarise(stem, ready_id, comparisons, updated=True))
tools/regenerate_snapshots.py:154:                    print(_summarise(stem, ready_id, comparisons, updated=False))
docs/failure-analysis/gen_hard_missing_precedents.md:28:For comparison, the iter5 run (57/100, before the regression):
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json:59:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tools/check_canonical_parity.py:1:"""Check ready-template canonical compile parity against one baseline file."""
tools/check_canonical_parity.py:21:DEFAULT_BASELINE = REPO_ROOT / "tests" / "fixtures" / "canonical_parity_baseline.json"
tools/check_canonical_parity.py:43:    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
tools/check_canonical_parity.py:45:    parser.add_argument("--update", action="store_true", help="Regenerate the canonical parity baseline.")
tools/check_canonical_parity.py:55:        payload = build_baseline(args.ready_root)
tools/check_canonical_parity.py:56:        args.baseline.parent.mkdir(parents=True, exist_ok=True)
tools/check_canonical_parity.py:57:        args.baseline.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
tools/check_canonical_parity.py:61:            "baseline": str(args.baseline),
tools/check_canonical_parity.py:67:    report = check_baseline(args.baseline, ready_root=args.ready_root)
tools/check_canonical_parity.py:72:def build_baseline(ready_root: Path = READY_ROOT) -> dict[str, Any]:
tools/check_canonical_parity.py:86:def check_baseline(baseline: Path = DEFAULT_BASELINE, *, ready_root: Path = READY_ROOT) -> dict[str, Any]:
tools/check_canonical_parity.py:87:    if not baseline.exists():
tools/check_canonical_parity.py:90:            "baseline": str(baseline),
tools/check_canonical_parity.py:91:            "errors": [f"missing baseline: {baseline}"],
tools/check_canonical_parity.py:97:    expected_payload = json.loads(baseline.read_text(encoding="utf-8"))
tools/check_canonical_parity.py:120:    errors.extend(f"new eligible template missing from baseline: {template_id}" for template_id in extra)
tools/check_canonical_parity.py:122:        f"baseline template no longer compiles: {item['id']}: {item['error']}"
tools/check_canonical_parity.py:132:        "baseline": str(baseline),
tools/check_canonical_parity.py:134:        "baseline_template_count": len(expected),
scripts/runpod_e2e_matrix.py:292:                proc.stderr.strip()[-500:] if proc.stderr.strip()
scripts/runpod_e2e_matrix.py:304:        entry["failure"] = traceback.format_exc()[-500:]
scripts/runpod_e2e_matrix.py:370:    """Load previous results.json if it exists for diff comparison."""
docs/failure-analysis/case-06-upscale.md:59:The `proof/baseline.json` confirms the **golden compiles clean** (output_reachable=true, 60 nodes, 83 links).
docs/failure-analysis/case-06-upscale.md:77:The on-demand schema resolver was **not engaged** for this node. Reason: `ResizeImageMaskNode` (id=3) was already in the broken graph, so the resolver had schema from the existing node. No `"unknown class"` or unresolved signals appear in any artifact. The baseline (`proof/baseline.json`) shows `"compile_error": "SOFT-PASS"` — the graph compiles structurally.
tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json:57:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
tools/generate_agent_contract_js.py:77:EXTENDED_CONSTANTS_BLOCK = "// \u2500\u2500 Completion proof states and domains (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/comfy_nodes/agent/completion_proofs.py\n\n/** Proof states: pass, fail, not_run, unknown.  Missing proof is never success. */\nexport const COMPLETION_PROOF_STATES = Object.freeze([\n  \"pass\",\n  \"fail\",\n  \"not_run\",\n  \"unknown\",\n]);\n\n/** Proof domains that each report an independent four-state result. */\nexport const COMPLETION_PROOF_DOMAINS = Object.freeze([\n  \"transformation_safety\",\n  \"graph_validity\",\n  \"task_satisfaction\",\n  \"runtime_readiness\",\n]);\n\n// \u2500\u2500 Obligation ledger vocabulary (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/comfy_nodes/agent/obligation_ledger.py\n\n/** Structural obligation kinds. */\nexport const OBLIGATION_KINDS = Object.freeze([\n  \"class_present\",\n  \"class_absent\",\n  \"value_match\",\n  \"edge_exists\",\n  \"terminal_output_domain\",\n  \"scope_preserved\",\n  \"obligation_declared\",\n]);\n\n/** Obligation evaluation statuses. */\nexport const OBLIGATION_STATUSES = Object.freeze([\n  \"satisfied\",\n  \"unsatisfied\",\n  \"unknown\",\n  \"not_evaluated\",\n  \"unsupported\",\n]);\n\n/** Obligation severities (criticality). */\nexport const OBLIGATION_SEVERITIES = Object.freeze([\n  \"required\",\n  \"recommended\",\n  \"optional\",\n]);\n\n// \u2500\u2500 Delta diagnostic codes (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/porting/edit/ops.py\n\nexport const DELTA_DIAGNOSTIC_CORRUPTED = \"corrupted_delta\";\nexport const DELTA_DIAGNOSTIC_TRUNCATED = \"truncated_delta\";\nexport const DELTA_DIAGNOSTIC_ABSENT = \"absent_delta\";\nexport const DELTA_DIAGNOSTIC_REPLAY_MISMATCH = \"replay_mismatch\";\n\n/** All delta diagnostic codes (including those from canonical_delta.js). */\nexport const DELTA_DIAGNOSTIC_CODES = Object.freeze([\n  \"malformed_delta\",\n  \"legacy_delta_shape\",\n  \"unsupported_scoped_apply\",\n  DELTA_DIAGNOSTIC_CORRUPTED,\n  DELTA_DIAGNOSTIC_TRUNCATED,\n  DELTA_DIAGNOSTIC_ABSENT,\n  DELTA_DIAGNOSTIC_REPLAY_MISMATCH,\n]);\n\n// \u2500\u2500 Plan obligation states (Python-sourced) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n// Source: vibecomfy/comfy_nodes/agent/obligation_ledger.py\n\nexport const PLAN_OBLIGATION_STATES = Object.freeze([\n  \"not_required\",\n  \"required_supported\",\n  \"required_unsupported\",\n]);"
tools/generate_agent_contract_js.py:79:HELPERS_BLOCK = "// \u2500\u2500 Proof state helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Check whether a value is a valid completion proof state.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidProofState(value) {\n  return COMPLETION_PROOF_STATES.includes(value);\n}\n\n/**\n * Check whether a value is a valid proof domain.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidProofDomain(value) {\n  return COMPLETION_PROOF_DOMAINS.includes(value);\n}\n\n// \u2500\u2500 Obligation ledger helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Check whether a value is a valid obligation kind.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidObligationKind(value) {\n  return OBLIGATION_KINDS.includes(value);\n}\n\n/**\n * Check whether a value is a valid obligation status.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidObligationStatus(value) {\n  return OBLIGATION_STATUSES.includes(value);\n}\n\n/**\n * Check whether a value is a valid obligation severity.\n * @param {*} value\n * @returns {boolean}\n */\nexport function isValidObligationSeverity(value) {\n  return OBLIGATION_SEVERITIES.includes(value);\n}\n\n// \u2500\u2500 Delta envelope reader \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Read the cumulative V2 delta envelope from a response.\n * Returns the canonical ``{schema_version, ops}`` envelope or null.\n *\n * @param {*} response - raw response object\n * @returns {object|null}\n */\nexport function readDeltaEnvelope(response) {\n  if (!isObject(response)) {\n    return null;\n  }\n  const accepted = response.accepted_batch;\n  if (!Array.isArray(accepted)) {\n    return null;\n  }\n  const ops = [];\n  for (const statement of accepted) {\n    if (!isObject(statement) || !isObject(statement.op)) {\n      continue;\n    }\n    ops.push(statement.op);\n  }\n  return {\n    schema_version: \"2.0.0\",\n    ops,\n  };\n}\n\n/**\n * Read the idempotency key from a response or its turn identity.\n * @param {*} response - raw response object\n * @returns {string|null}\n */\nexport function readIdempotencyKey(response) {\n  if (!isObject(response)) {\n    return null;\n  }\n  return asString(response.idempotency_key)\n    || asString(response.idempotencyKey)\n    || asString(response.candidate?.turn_identity?.idempotency_key)\n    || asString(response.candidate?.turnIdentity?.idempotencyKey)\n    || asString(response.debug?.turn_identity?.idempotency_key)\n    || asString(response.debug?.turnIdentity?.idempotencyKey)\n    || null;\n}\n\n// \u2500\u2500 Obligation ledger reader \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Read task satisfaction / obligation ledger entries from a response.\n * These mirror the Python-side task_satisfaction and obligation_ledger fields\n * that are serialized onto applyable and clarify responses.\n *\n * @param {*} response - raw response object\n * @returns {object|null} { task_satisfaction, obligation_ledger } or null\n */\nexport function readObligationArtifacts(response) {\n  if (!isObject(response)) {\n    return null;\n  }\n  const taskSatisfaction = Array.isArray(response.task_satisfaction)\n    ? response.task_satisfaction\n    : null;\n  const obligationLedger = isObject(response.obligation_ledger)\n    ? response.obligation_ledger\n    : null;\n  if (!taskSatisfaction && !obligationLedger) {\n    return null;\n  }\n  return {\n    task_satisfaction: taskSatisfaction,\n    obligation_ledger: obligationLedger,\n  };\n}\n\n// \u2500\u2500 Non-applyable clarify detection \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n/**\n * Detect whether a response represents a non-applyable clarify outcome.\n * Non-applyable clarify responses must carry clarification_required=true\n * and must NOT carry candidate, graph, apply_eligible, or eligibility fields\n * that could be mistaken for applyable content.\n *\n * @param {*} response - raw response object\n * @returns {boolean}\n */\nexport function isNonApplyableClarify(response) {\n  if (!isObject(response)) {\n    return false;\n  }\n  const outcomeKind = asString(response.outcome?.kind);\n  if (outcomeKind !== \"clarify\") {\n    return false;\n  }\n  // Non-applyable clarify must not carry candidate payloads.\n  if (isObject(response.candidate) || isObject(response.candidate_graph) || isObject(response.graph)) {\n    return false;\n  }\n  // Must carry clarification markers.\n  if (response.clarification_required !== true && response.clarificationRequired !== true) {\n    return false;\n  }\n  return true;\n}"
tools/generate_agent_contract_js.py:90:    # The search paths for extractRebaselineRecovery — these are the snake_case
tools/generate_agent_contract_js.py:91:    # dotted paths where a rebaseline_recovery object may nest inside a failure
tools/generate_agent_contract_js.py:173:// ── Rebaseline recovery (snake_case canonical) ──────────────────────────────
tools/generate_agent_contract_js.py:176: * Normalize a raw rebaseline-recovery object to the canonical snake_case shape.
tools/generate_agent_contract_js.py:182:export function normalizeRebaselineRecovery(recovery) {{
tools/generate_agent_contract_js.py:192: * Extract a rebaseline-recovery payload from a response object.
tools/generate_agent_contract_js.py:194: *   1. response.rebaseline_recovery (top-level)
tools/generate_agent_contract_js.py:195: *   2. response.agent_failure_context.issues[*].rebaseline_recovery
tools/generate_agent_contract_js.py:196: *   3. response.outcome.agent_failure_context.issues[*].rebaseline_recovery
tools/generate_agent_contract_js.py:197: *   4. response.debug.failure.agent_failure_context.issues[*].rebaseline_recovery
tools/generate_agent_contract_js.py:205:export function extractRebaselineRecovery(response) {{
tools/generate_agent_contract_js.py:206:  const topLevel = normalizeRebaselineRecovery(response?.rebaseline_recovery);
tools/generate_agent_contract_js.py:218:      const recovery = normalizeRebaselineRecovery(issue?.rebaseline_recovery);
tools/generate_agent_contract_js.py:260:        "last_known_baseline_graph_hash",
docs/failure-analysis/other.md:24:For comparison, the iter5 run (57/100, before the regression):
tools/format_as_python.py:4:    Lines ~1–550 below are a pre-existing standalone emitter implementation that
scripts/live_agentic_scenario_gen/_generator.py:239:        return "Raise the training steps to 1500 and set the learning rate to 1e-4."
docs/failure-analysis/widget_name_resolution_phase2_impl.md:143:All 1 failure(s) are quarantined baseline failures. No regressions.
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:57:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
docs/watchdog-babysitting-goal.md:69:  the allowlist + import check + baseline-diff, not approvals.
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:58:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
docs/watchdog-babysitting-loop.md:63:- **Cost/time runaway** → one turn wildly over baseline → investigate; if real,
docs/watchdog-babysitting-loop.md:112:`2026-06-28 ~04:57 CEST — run-20260628T022848 — HOURLY CHECK-IN — healthy. r1 suite DONE 5/23 (baseline; builds on old run r1-r3 commits — vs old run's r1=4). codex r1 turn mid-flight (started 02:56 UTC). No commits/rogue/grader edits yet. KEEP GOING; awaiting r1 commit to assess freedom-used + grader-safety. PENDING USER: per-scenario runner timeout to cut ~30m rounds → ~15m.`
docs/watchdog-babysitting-loop.md:113:`2026-06-28 ~05:08 CEST — run-20260628T022848 — R1 DONE ✅ BREAKTHROUGH — 5/23 baseline; codex USED THE NEW FREEDOM: edited runtime files edit.py (+82) + diagnostics.py (+5) — a STRUCTURAL fix to the queue-safety blocker (_stage_summarize_v2 schema_less_queue_blocker): pre-existing schema-less UI nodes no longer falsely block queue validation (fail-closed preserved for genuinely new nodes). This is the 'target-aware revision evidence' fix the old run could only write as a bigger-swing — codex implemented it directly. ANTI-GAMING CLEAN (pipeline-only; no grader/scenario/driver/docs; report says so). Safety gate PASSED, sha 214e65a7 recorded (new git commit model works — fixed old null-tracking). 11.7m codex turn (substantial). r2 = payoff test (falsely-queue-blocked scenarios should pass). Validates removing the allowlist.`
docs/release_notes/v2.8.0.md:120:| `_next_node_id()` uses lowest-unused-gap instead of max+1 | Snapshot-based test authors | Auto-generated node IDs may change when gaps exist; regenerate snapshots or accept baseline deltas |
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:56:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
docs/failure-analysis/widget_name_resolution_risks.md:141:- `_compile/_resolve.py` updates raw `_ui.widgets_values` after folding Primitive helper values by using its own `_widget_index_for_field`, which checks committed schema, `metadata.input_aliases`, then `_ui.inputs[].widget.name` at [line 350](../../vibecomfy/_compile/_resolve.py).
docs/structural_audit_2026-05.md:162:- **models.yaml is the weakest registry link:** all ~50 `node_pack` references use a naming scheme
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:60:      "vacuous node-name listing without causal explanation, comparison, or diagnosis",
docs/failure-analysis/gen_hard_missing_schemas.md:17:| `image-image-comparison-and-enhancement-with-florence-007018` | **Failure:** `failure_kind: SchemaGap` — the agent exhausted its budget (3 consecutive errors in 6 turns) because requir |
docs/failure-analysis/gen_hard_missing_schemas.md:26:For comparison, the iter5 run (57/100, before the regression):
docs/failure-analysis/gen_hard_missing_schemas.md:62:cp tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json "$TMP/"
docs/structural_issues.md:17:- `runtime_green`: baseline Comfy and VibeComfy both generated expected media on RunPod.
      57

exec
/bin/zsh -lc "python -c 'import json; from pathlib import Path; p=next(Path(\"tests/live_agentic_harness/scenarios\").glob(\"*.json\")); d=json.loads(p.read_text()); print(p); print(json.dumps(d,indent=2)[:2500])'
rg -n \"def from_dict\" vibecomfy/executor/contracts.py | head -20" in /private/tmp/vc-twostep
 succeeded in 0ms:
2412:    def from_dict(cls, payload: Mapping[str, Any]) -> "HivemindRecordView":

exec
/bin/zsh -lc "python -c 'from vibecomfy.intent._ledger import LEDGER_ID_COUNT,LEDGER_UNRECOVERABLE_COUNT; print(LEDGER_ID_COUNT,LEDGER_UNRECOVERABLE_COUNT)'
rg -n \"LEDGER_ID_COUNT|EXIT_FAILURE_LEDGER\" vibecomfy/intent/_ledger.py | sed -n '1,140p'" in /private/tmp/vc-twostep
 succeeded in 231ms:
57 0
61:LEDGER_ID_COUNT = 57
98:EXIT_FAILURE_LEDGER: tuple[FailureLedgerRow, ...] = (
296:        for row in EXIT_FAILURE_LEDGER
303:    if len(ids) != LEDGER_ID_COUNT:
304:        raise AssertionError(f"ledger has {len(ids)} ids, expected {LEDGER_ID_COUNT}")
309:        for row in EXIT_FAILURE_LEDGER
314:    for row in EXIT_FAILURE_LEDGER:

exec
/bin/zsh -lc "sed -n '1,360p' vibecomfy/intent/_ledger.py
rg -n \"def test_.*law|# .*Law\" tests/test_ir_laws.py | sed -n '1,260p'" in /private/tmp/vc-twostep
 succeeded in 0ms:
"""Single 57-failure owner ledger for the IR-everywhere sprint.

This is the only ledger.  ``tests/test_ir_laws.py`` and
``vibecomfy.intent._fixture`` both import it.  There is no second id set.

Reconstruction source
---------------------
The 57 unique scenario ids are the first-attempt failures of the host
recovery rerun:

    /Users/peteromalley/Documents/reigh-workspace/vibecomfy-recovery-run/out/agentic/recovery-rerun/run_summary.json

``failed`` / ``raw_first_attempt_failed`` = 57, ``raw_first_attempt_success``
is False on exactly those 57 unique ids.  All 57 ids are recoverable from
that artifact.

v1 (``ir-everywhere-57``) and v2 (``ir-everywhere-57-v2``) are INVALID
and must not be used for reconciliation: v1 imported the recovery-run
package via cwd-on-sys.path; v2 measured a dirty moving tree.

The only valid post-migration artifact is ``ir-everywhere-57-v3``, now
``complete: true`` with ``final_score: 16/57``.  Judge verdicts come from
each scenario's ``assessment.json`` ``passed`` field, not executor-level
``ok`` on the run_summary row.

A prior planning reconstruction (``.oracle/findings/failure-partition.txt``)
built 48 family-doc ids + 9 case-note ids.  That is a *different* 57
(partial overlap with this run).  This ledger does not mix the two sets
and does not invent the missing planning-partition ids.

Status rules
------------
- ``resolved`` requires the actual ids, the owning mechanism, and a v3
  judge pass (``assessment.json`` ``passed=true``).
- ``capability_floor`` is used only with named evidence (Class D hard floor
  or the variance family doc) that v3 still confirms as product_fail.
  ``cc0df7``, ``90a1d5``, and the variance id live only here.
  ``5b31ce`` is not a named floor.
- ``infra_out_of_scope`` is a v3 ``failure_class=infra_timeout`` /
  ``score_class=infra_blocked`` (8 ids).
- remaining v3 product_fail ids stay ``pending_live_rerun``.
"""

from __future__ import annotations

from dataclasses import dataclass


LEDGER_RECONSTRUCTION_SOURCE = (
    "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-recovery-run/"
    "out/agentic/recovery-rerun/run_summary.json"
)
V3_ARTIFACT = (
    "/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/"
    "out/agentic/ir-everywhere-57-v3/run_summary.json"
)
V3_ATTEMPTS = (
    "/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/"
    "out/agentic/ir-everywhere-57-v3/attempts"
)
LEDGER_ID_COUNT = 57
LEDGER_UNRECOVERABLE_COUNT = 0
CLASS_D_HARD_FLOOR_IDS = frozenset(
    {
        "3d-3d-model-generation-and-preview-workflow-cc0df7",
        "3d-3d-model-generation-and-rigging-workflow-90a1d5",
    }
)
_EXIT_STATUSES = frozenset(
    {"resolved", "capability_floor", "infra_out_of_scope", "pending_live_rerun"}
)
_V3_MECHANISM = "v3 live rerun on ir-everywhere branch"
_V3_PASS_EVIDENCE = (
    "v3 assessment.json passed=true for each id at "
    f"{V3_ATTEMPTS}/<id>/attempt_1/<id>/assessment.json; "
    f"{V3_ARTIFACT} complete=true, final_score=16/57."
)
_V3_INFRA_EVIDENCE = (
    "v3 assessment.json passed=false; run_summary failure_class=infra_timeout "
    f"/ score_class=infra_blocked (8 of 57). Artifact: {V3_ARTIFACT}."
)


@dataclass(frozen=True, slots=True)
class FailureLedgerRow:
    family: str
    owner: str
    scenario_ids: tuple[str, ...]
    status: str
    evidence: str
    mechanism: str = ""

    @property
    def count(self) -> int:
        return len(self.scenario_ids)


EXIT_FAILURE_LEDGER: tuple[FailureLedgerRow, ...] = (
    FailureLedgerRow(
        family="class_d_hard_floor",
        owner="capability floor; not a sprint phase",
        scenario_ids=(
            "3d-3d-model-generation-and-preview-workflow-cc0df7",
            "3d-3d-model-generation-and-rigging-workflow-90a1d5",
        ),
        status="capability_floor",
        evidence=(
            "scripts/b09_reducer.py CLASS_D_HARD_FLOOR: cc0df7 Rodin has no "
            "model selector; 90a1d5 TripoRig has no joint control.  v3 "
            "assessment.json passed=false, score_class=product_fail (not "
            "infra).  These ids are not resolved via Law 4 or interpret."
        ),
    ),
    FailureLedgerRow(
        family="semantic: variance",
        owner="phase 5",
        scenario_ids=("multi-wan-vace-video-retargeting-driven",),
        status="capability_floor",
        evidence=(
            "docs/failure-analysis/variance.md — model-variance capability "
            "floor.  v3 assessment.json passed=false, score_class=product_fail.  "
            "The Class D hard-floor ids live only in class_d_hard_floor."
        ),
    ),
    FailureLedgerRow(
        family="v3_live_pass",
        owner="v3 live rerun",
        scenario_ids=(
            "audio-acestep-audio-generation-with-detail-daemon-f0859f",
            "image-dual-checkpoint-xl-image-generation-with-refin-c9df19",
            "image-gemini-prompt-splitter-and-text-display-workfl-caae97",
            "image-image-processing-with-sharpening-film-grain-an-9aa0f1",
            "image-qwen-image-inpainting-with-controlnet-09fc64",
            "live-graph-explanation-smoke",
            "multi-3d-gaussian-splatting-from-video-with-hunyuan-432652",
            "multi-animatediff-video-generation-with-controlnet-a7e2af",
            "multi-flux2-image-and-video-generation-with-outpaint-435de2",
            "multi-svd-image-to-video-with-animation-builder-99e2a9",
            "video-animatediff-video-to-video-with-controlnet-and-3c978e",
            "video-animatediff-video-with-controlnet-and-depth-89b02a",
            "video-inpaint-and-video-composition-with-spline-path-0c2716",
            "video-video-loading-and-saving-workflow-1c7ad8",
            "video-video-output-workflow-f855de",
            "video-wanvideo-text-to-video-generation-71f825",
        ),
        status="resolved",
        evidence=_V3_PASS_EVIDENCE,
        mechanism=_V3_MECHANISM,
    ),
    FailureLedgerRow(
        family="infra",
        owner="out of scope: phase 7 is cut",
        scenario_ids=(
            "3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2",
            "image-generates-a-2x2-seed-variation",
            "image-kolors-image-generation-with-segs-detailer-and-d813fe",
            "image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5",
            "multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56",
            "video-hunyuanvideo-image-to-video-generation-with-en-ff076a",
            "video-ltx-video-with-audio-and-inpainting-b3ba8a",
            "video-seedvr2-video-upscaling-workflow-052e59",
        ),
        status="infra_out_of_scope",
        evidence=_V3_INFRA_EVIDENCE,
    ),
    FailureLedgerRow(
        family="semantic: gen_hard_missing_precedents",
        owner="phase 6",
        scenario_ids=(
            "multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/gen_hard_missing_precedents.md.  v3 "
            "assessment.json passed=false, score_class=product_fail."
        ),
        mechanism="ResearchAttempt never/empty/thin/grounded",
    ),
    FailureLedgerRow(
        family="semantic: gen_hard_missing_schemas",
        owner="phase 5",
        scenario_ids=(
            "3d-3d-shape-generation-and-export-workflow-8800a9",
            "audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf",
            "image-face-detection-and-cropping-workflow-949658",
            "image-image-comparison-and-enhancement-with-florence-007018",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/gen_hard_missing_schemas.md requires a schema "
            "source.  v3 assessment.json passed=false, score_class=product_fail.  "
            "cc0df7 is Class D and is not in this family."
        ),
        mechanism="render census/surface (Law 4)",
    ),
    FailureLedgerRow(
        family="edit: pre_existing_bug",
        owner="phase 3",
        scenario_ids=(
            "3d-3d-model-generation-and-rigging-from-image-352066",
            "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
            "multi-image-to-video-generation-with-2",
            "video-video-frame-by-frame-style",
            "video-video-generation-from-resized-image",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/pre_existing_bug.md.  v3 assessment.json "
            "passed=false, score_class=product_fail."
        ),
        mechanism="interpret + EditableSurface",
    ),
    FailureLedgerRow(
        family="edit: cross_domain_over_rejection",
        owner="phase 3",
        scenario_ids=(
            "hotshot-16-frames-agent-edit",
            "multi-deforum-stable-diffusion-animation-with-ip-ada-78afac",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/cross_domain_over_rejection.md.  v3 "
            "assessment.json passed=false, score_class=product_fail.  "
            "90a1d5 is Class D and is not in this family."
        ),
        mechanism="unknown-schema typed refusal on interpret",
    ),
    FailureLedgerRow(
        family="edit: widget_shape_guard",
        owner="phase 3",
        scenario_ids=(
            "multi-crops-face-previews-it-sets",
            "multi-image-to-video-with-upscaling-and-color-matchi-359848",
            "video-svd-image-to-video-generation-fc240f",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/widget_shape_guard.md.  v3 assessment.json "
            "passed=false, score_class=product_fail."
        ),
        mechanism="widget_shape_fence + interpret CAS",
    ),
    FailureLedgerRow(
        family="edit: revision_evidence_fix",
        owner="phase 4",
        scenario_ids=("video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20",),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/revision_evidence_fix.md.  v3 assessment.json "
            "passed=false, score_class=product_fail."
        ),
        mechanism="canonical Δ (Law 3)",
    ),
    FailureLedgerRow(
        family="other",
        owner="capability-floor candidate; reclassify with evidence",
        scenario_ids=("video-video-combine-with-image-loading-5b31ce",),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/other.md is an ambiguous bucket, not named "
            "Class-D or variance floor evidence.  v3 assessment.json "
            "passed=false, score_class=product_fail: research_attempt=never + "
            "agent refused, no edit (.oracle/findings/v3-batch-5.md)."
        ),
    ),
    FailureLedgerRow(
        family="recovery_rerun_unpartitioned",
        owner="host live rerun",
        scenario_ids=(
            "3d-3d-model-generation-and-retargeting-workflow-f65774",
            "audio-audio-processing-with-voice-tts-and-noise-remo-b80848",
            "image-animatediff-video-from-images-with",
            "image-animatediff-video-generation-with-vae-d20410",
            "image-flux-image-inpainting-and-compositing-with-con-00444a",
            "image-image-to-image-with-ipadapter-and-controlnet-1999a9",
            "multi-ai-video-upscaling-with-detail-daemon-sampler-673197",
            "multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6",
            "video-image-to-video-with-svd-and-webp-output-1882aa",
            "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
            "video-wan-video-generation-with-vace-and-multi-outpu-d1caec",
            "video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9",
            "video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9",
        ),
        status="pending_live_rerun",
        evidence=(
            "Present in the recovery-rerun 57; v3 assessment.json passed=false, "
            "score_class=product_fail.  Not a named Class-D or variance floor."
        ),
    ),
)


def ledger_scenario_ids() -> tuple[str, ...]:
    return tuple(
        scenario_id
        for row in EXIT_FAILURE_LEDGER
        for scenario_id in row.scenario_ids
    )


def assert_ledger_integrity() -> None:
    ids = ledger_scenario_ids()
    if len(ids) != LEDGER_ID_COUNT:
        raise AssertionError(f"ledger has {len(ids)} ids, expected {LEDGER_ID_COUNT}")
    if len(ids) != len(set(ids)):
        raise AssertionError("ledger scenario ids are not unique")
    if CLASS_D_HARD_FLOOR_IDS != frozenset(
        sid
        for row in EXIT_FAILURE_LEDGER
        if row.family == "class_d_hard_floor"
        for sid in row.scenario_ids
    ):
        raise AssertionError("Class D hard-floor ids are not isolated in class_d_hard_floor")
    for row in EXIT_FAILURE_LEDGER:
        if row.status not in _EXIT_STATUSES:
            raise AssertionError(f"{row.family}: invalid status {row.status!r}")
        if not row.scenario_ids or not row.evidence or not row.owner:
            raise AssertionError(f"{row.family}: missing ids/owner/evidence")
        if row.status == "resolved" and not row.mechanism:
            raise AssertionError(f"{row.family}: resolved without a mechanism")
        if row.status == "capability_floor" and not row.evidence:
            raise AssertionError(f"{row.family}: capability_floor without named evidence")
        if row.family != "class_d_hard_floor" and CLASS_D_HARD_FLOOR_IDS.intersection(row.scenario_ids):
            raise AssertionError(f"{row.family}: contains Class D hard-floor ids")
480:def test_law_1_door_fidelity(kind: str, path: Path) -> None:
634:def test_law_2_editable_isomorphism(kind: str, path: Path, _hash: str) -> None:
648:def test_law_2_unknown_schema_named_widget_channel() -> None:
675:def test_law_2_reserved_side_channel_does_not_collide() -> None:
776:def test_law_3_interface_op_does_not_permit_unrelated_state_drift() -> None:
990:def test_law_3_delta_replay_is_deterministic_and_minimal() -> None:
1012:def test_law_3_spike_corpus_diff_is_an_inverse_over_the_quotient(
1146:def test_law_4_topology_is_computed_from_ir_edges() -> None:
1158:def test_law_4_judge_lens_subset_is_enforced_at_render_boundary() -> None:
1217:# ── Law 4 (batch 11): composable renderer lens goldens ───────────────────────
1261:def test_law_4_render_lenses_are_deterministic_goldens() -> None:
1284:def test_law_4_census_lens_content() -> None:
1296:def test_law_4_surface_lens_content() -> None:
1315:def test_law_4_diff_lens_content() -> None:
1339:def test_law_4_topology_lens_has_no_truncation_cap() -> None:
1407:def test_law_4_3c978e_controlnet_chain_topology_complete() -> None:
1445:# Golden workflow fixture for Law 5: two VHS_LoadVideo nodes (deterministic
1507:def test_law_5_bindings_are_deterministic_across_ids_stages_and_turns() -> None:
1534:    # widget_N, PORT_n and the slot_N shim are all forbidden (Law 5, batch 4).
1560:# ── Law 5 (batch 5): provenance lattice + copy-on-write edits ───────────────
1585:def test_law_5_edits_are_copy_on_write_and_compose_provenance() -> None:
1701:def test_law_5_edits_never_downgrade_provenance(tag_value: str) -> None:
1723:def test_law_5_session_rebuild_is_copy_on_write_and_composes_provenance() -> None:
1778:def test_law_5_boundary_has_no_provisional_exceptions() -> None:
1796:def test_law_4_grammar_generates_allow_list_prompt_and_doc_table() -> None:
1830:def test_law_4_editable_surface_is_instance_hydrated() -> None:

2026-08-17T21:34:57.585456Z ERROR codex_core::tools::router: error=timeout_ms must be at least 10000
collab: Wait
codex
A key implementation constraint is now clear: the generic provider turn is intentionally tool-free and collapses chat messages, while the existing batch-REPL and `EditSession` already provide the continuation/transaction machinery. The plan will therefore extend that bounded continuation seam and persist one logical execute session per existing `session_id`; it will not pretend repeated stateless completions are thread continuity.
collab: Wait
codex
The repository survey confirms two planning-critical gaps: first-turn two-step requests can currently reach execution without a pre-established `session_id`, and accepted deltas/rendered lens facts do not yet have stable claim-reference IDs. I’m treating both as explicit host contracts—not prompt conventions—and keeping rollout control out of the product path unless the exploration phase finds an existing controller worth reusing.
codex
# Megado plan: VibeComfy `two_step` executor

Target: add `classify → execute` as an explicit, default-off pipeline mode while preserving the current full pipeline. The authoritative specification is [two-step-mode-design.md](/Users/peteromalley/Documents/vibecomfy-ir-everywhere/.oracle/two-step-mode-design.md).

Megado discipline: run the exploration briefs first, revise this plan until stable, freeze `.oracle/tasklist.md`, then execute one batch at a time. Commit and obtain an oracle `PASS` before starting the next batch.

## Non-negotiable invariants

- `PipelineMode = Literal["full", "two_step"]`.
- Resolution is request field → `VIBECOMFY_EXECUTOR_PIPELINE_MODE` → `"full"`.
- Branch only after classification, clarification persistence, `classify_only`, and `answer_only`.
- No automatic fallback between modes.
- Full-mode orchestration and websocket event payloads remain byte-compatible.
- Two-step means one host-managed execute session with bounded continuations, not one raw provider response.
- `session_id` is the chat-window identity. Never substitute `executor_id` or mint a new ID per message.
- The agent never receives raw ComfyUI JSON or full internal IR.
- All edits use the existing Python grammar and immutable interpreter.
- One atomic edit batch, with at most one complete replacement after rejection.
- Rejected batches produce zero Δ.
- No second target declaration or second delta representation.
- Claims are valid only through accepted Δ IDs, reply-lens fact IDs, and tool-ledger evidence IDs.
- The execute prompt explicitly presents `research → change → submit` and lists the exact tools available in each stage.
- Shadow rollout is operational; do not introduce an automatic route router or escalation framework.

## Pre-execution exploration

Dispatch these as parallel read-only Megado exploration briefs. Each finding should be under 300 words with file/line evidence, risks, and a recommended approach.

1. `provider-continuations.txt`
   - Trace `agent_backend.py`, provider/runtime workers, JSON response contracts, output-token controls, and model-attempt accounting.
   - Confirm the smallest provider-independent continuation mechanism.

2. `session-identity.txt`
   - Trace browser tab identity, first-turn `session_id`, durable session paths, locking, chat artifacts, process restart, and concurrent requests.
   - Decide how a retained execute session is reconstructed safely after restart.

3. `atomic-edit-cas.txt`
   - Trace `EditSession.apply_batch`, `interpret`, apply gates, request baseline hashes, structural hashes, accepted-batch serialization, and done gates.
   - Specify the exact preflight/CAS sequence.

4. `render-claim-ids.txt`
   - Trace `render`, topology facts, reply lenses, Hivemind workflow records, template loading, and oversized graph handling.
   - Propose deterministic delta/lens fact IDs without adding graph authority.

5. `profiles-events-report.txt`
   - Trace packaged and external profile ownership, profiler payloads, report fixtures, websocket phase fixtures, and downstream report consumers.

6. `differential-harness.txt`
   - Trace the live harness, intent judge, `pi_edit`, canonical replay, the 57-case owner ledger, and deterministic 50-case selection.
   - Specify test-only classification locking without a production bypass.

7. `budgets-policy.txt`
   - Trace current tool budgets, web-search policy, worker token limits, timeout enforcement, and usage capture.
   - Identify missing numeric cumulative-session ceilings.

After exploration, revise until `STABLE`, then freeze the batches below.

---

# B01 — Mode plumbing and dispatch toggle

## Tasks

1. Update [vibecomfy/executor/contracts.py](/private/tmp/vc-twostep/vibecomfy/executor/contracts.py):
   - Add `PipelineMode = Literal["full", "two_step"]`.
   - Add typed `PipelineModeRequestError` and `PipelineModeConfigurationError`.
   - Add `coerce_pipeline_mode()` and `resolve_pipeline_mode(request, environ=None)`.
   - Add optional `ExecutorRequest.pipeline_mode`.
   - Validate direct construction and `from_payload()`.
   - Preserve omission in `to_dict()` when unspecified.

2. Update [vibecomfy/agent/contracts.py](/private/tmp/vc-twostep/vibecomfy/agent/contracts.py):
   - Add optional `HeadlessAgentRequest.pipeline_mode`.
   - Carry it through parsing and `to_executor_request()`.

3. Update [vibecomfy/executor/core.py](/private/tmp/vc-twostep/vibecomfy/executor/core.py):
   - Resolve mode once for profiler/report use.
   - Preserve the existing classify and `answer_only` behavior.
   - Add the only orchestration branch immediately after the current `answer_only` block:
     ```python
     if pipeline_mode == "two_step":
         return _run_two_step(...)
     ```
   - Keep the existing research → implement → reply block structurally untouched.
   - For `classify_only`, full mode emits its existing skipped events; two-step emits only `execute: skipped`.

4. Add [vibecomfy/executor/two_step.py](/private/tmp/vc-twostep/vibecomfy/executor/two_step.py) with the typed entrypoint seam and a test-injectable outcome boundary. Real execution lands in B03–B04.

5. Add `tests/fixtures/payload_contracts/agent_executor_two_step_request.json`; do not rewrite the existing request fixture merely to include an optional field.

6. Add:
   - `tests/test_executor_pipeline_mode.py`
   - Mode round-trip cases to `tests/test_executor_contracts.py`
   - Branch/classify-only cases to `tests/test_executor_classify_only.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_pipeline_mode.py \
  tests/test_executor_contracts.py \
  tests/test_executor_classify_only.py \
  tests/test_executor_flows.py
```

Must prove:

- Request beats environment.
- Environment beats default.
- Invalid request value is a request error.
- Invalid environment value is a configuration error.
- Default is full.
- `classify_only` never resolves or invokes `execute`.
- `answer_only` reaches two-step only after its edit-forbidding rewrite.
- Full-mode phase calls and event payloads are unchanged.

---

# B02 — Route policy, tool gating, and host budgets

## Tasks

1. In `vibecomfy/executor/two_step.py`, add frozen types:
   - `TwoStepRoutePolicy`
   - `MessageBudget`
   - `SessionBudget`
   - `BudgetUsage`
   - `BudgetExceeded`

2. Define `TWO_STEP_ROUTE_POLICIES` with the authoritative route table:
   - `clarify`, `respond`: no tools; 2k; 30s.
   - `inspect`: `node_schema`; 4k; two calls; 60s.
   - `research`: Hivemind, registry, schema, templates, policy-enabled web; 8k; 180s.
   - `requires_custom_nodes`: registry and schema; 4k; 90s.
   - `revise`: schema, templates, suggestions, layout, Python; 8k; 180s.
   - `adapt`: all ten tools and Python; 12k; 240s.
   - `reorganise`: layout and Python; 6k; 120s.

3. Assert:
   ```python
   set(TWO_STEP_ROUTE_POLICIES) == set(_ROUTE_BEHAVIORS)
   ```
   Import `_ROUTE_BEHAVIORS` lazily to avoid moving or duplicating the full-mode route authority.

4. Reuse [tool_specs.py](/private/tmp/vc-twostep/vibecomfy/executor/tool_specs.py):
   - Keep exactly ten registered tools.
   - Use `tool_catalog_docs(..., allowed_names=...)` for advertisement.
   - Dispatch through the existing `ToolSpec` handlers/projectors.
   - Enforce the route allowlist before handler invocation or budget consumption.
   - Keep `web_search` disabled unless existing policy enables it.

5. Add hard budget checks before and after every model/tool call:
   - Per-message route slice.
   - Cumulative session ceiling.
   - Aggregate output tokens across continuations.
   - Per-tool/class call caps.
   - Apply/replacement counters.
   - Wall clock.

6. Extend optional parameters through:
   - `vibecomfy/comfy_nodes/agent/provider.py::run_model_turn`
   - `vibecomfy/comfy_nodes/agent/runtime.py::run_model_turn`
   - Worker construction
   so a continuation can receive the remaining output-token cap. `None` must preserve full-mode behavior.

7. Add:
   - `tests/test_executor_two_step_policy.py`
   - `tests/test_executor_two_step_tools.py`
   - Optional runtime-cap cases to `tests/test_agent_runtime_adapter.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py \
  tests/test_executor_hivemind_tools.py \
  tests/test_executor_lookup_tools.py \
  tests/test_executor_layout_hints.py \
  tests/test_agent_runtime_adapter.py
```

Must prove exact route coverage, exact advertised catalogs, denial before dispatch, disabled web policy, every budget family, aggregate-token exhaustion, and cumulative-session exhaustion.

---

# B03 — Execute prompt and thread-continuous session

## Tasks

1. `[XHARD]` Add [vibecomfy/executor/two_step_session.py](/private/tmp/vc-twostep/vibecomfy/executor/two_step_session.py):
   - Key identity directly by normalized chat-window `session_id`.
   - Persist a compact append-only execute transcript beneath the existing durable session directory.
   - Persist accepted Δ references, lens facts, evidence ledger, replies, route history, cumulative budget usage, and last retained workflow revision.
   - Serialize same-session messages with the existing session lock discipline.
   - Detect concurrent/stale message attempts before model work.
   - Cache the retained `EditSession` in process; reconstruct only through a named ingest door plus canonical accepted deltas after restart.
   - Never use an in-memory dictionary as the sole authority.

2. Establish first-turn identity before execution:
   - Browser submit flow must obtain/reuse its existing tab-scoped `session_id` before sending a two-step request.
   - Two-step HTTP/headless requests without a usable `session_id` fail as typed invalid requests.
   - Update `vibecomfy/comfy_nodes/web/agent_submit_flow.js` only as needed to reuse the existing tab-scoped allocator; do not add a settings UI.

3. `[XHARD]` Add `build_two_step_execute_messages()` to [prompts.py](/private/tmp/vc-twostep/vibecomfy/executor/prompts.py):
   - Include every authoritative design section.
   - Add an explicit `STAGES AND AVAILABLE TOOLS` section:
     1. `RESEARCH` — exact research tools available for this route.
     2. `CHANGE` — exact advisory/schema/layout tools plus whether Python editing is allowed.
     3. `SUBMIT` — no tools; final JSON contract only.
   - State that unavailable tools are denied by the host.
   - State the same-window continuity rule verbatim in substance.
   - For non-edit routes, explicitly say no change may be submitted.
   - Render only the route-allowed catalog.

4. `[XHARD]` Implement the bounded continuation loop:
   - Add `run_execute_turn()` to `vibecomfy/executor/agent_backend.py`.
   - Parse host actions: registered tool call, Python batch submission, or final contract.
   - Re-inject the compact accumulated transcript and the new message into every continuation.
   - Do not depend on provider-native memory.
   - Preserve one logical execute-session identity across messages and route changes.
   - Derive `research_attempt` from the session ledger.

5. Add prompt goldens:
   - `tests/fixtures/executor/two_step_prompt_clarify.txt`
   - `..._respond.txt`
   - `..._inspect.txt`
   - `..._research.txt`
   - `..._requires_custom_nodes.txt`
   - `..._revise.txt`
   - `..._adapt.txt`
   - `..._reorganise.txt`

6. Add:
   - `tests/test_executor_two_step_prompt.py`
   - Initial session tests in `tests/test_executor_two_step_continuity.py`
   - Browser identity coverage in the existing browser submit-flow suite

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_continuity.py \
  tests/test_routes_session_sanitization.py \
  tests/test_agent_executor_durable.py

npm test -- --runInBand
```

The gate must inspect every prompt golden and prove the visible sequence is `research → change → submit`, with exact tools and no union catalog leakage.

---

# B04 — Atomic edit, precedent projection, and claim references

## Tasks

1. In `two_step.py`, add the execute state machine:
   - Research/tool continuations may precede editing.
   - Exactly one complete Python batch may be accepted.
   - One complete replacement is allowed only after rejection.
   - After acceptance, further edit submissions are denied.
   - A second rejection returns no candidate.
   - Parse, resolution, CAS, channel, bounds, or done-gate failure returns zero Δ.

2. Reuse:
   - `EditSession.apply_batch()`
   - `interpret(pre, batch)`
   - `verify_apply()`
   - Existing emit and durable candidate machinery
   without changing general full-mode `max_batches` behavior.

3. Add request/session CAS preflight:
   - Compare the request baseline and current canvas projection with the retained session revision.
   - Validate every parsed operation’s CAS expectations before mutation.
   - Return typed stale-baseline diagnostics to the one replacement continuation.

4. Add `render_fact_pack()` to [vibecomfy/porting/render.py](/private/tmp/vc-twostep/vibecomfy/porting/render.py):
   - Derive stable fact IDs from canonical lens items.
   - Text lenses use canonical rendered lines; topology uses canonical tuples.
   - IDs reference facts but do not create another graph representation.
   - Preserve the Law 4 lens ceiling.

5. Extend `HivemindRecordView` and `serve_hivemind_record()`:
   - Workflow records expose immutable `surface + topology`.
   - Never expose raw workflow JSON to the model.
   - Oversized records use a deterministic relevant subgraph with explicit node/edge omitted counts and `global_topology_complete=false`.
   - Apply the same sanitization to workflow-valued ready-template observations.

6. Add typed final contracts in `executor/contracts.py`:
   - `TwoStepClaimRefs`
   - `TwoStepSelfAssessment`
   - `TwoStepFinal`
   - `TwoStepExecutionReport`

7. Implement `validate_two_step_final()`:
   - `delta_ids ⊆ accumulated accepted Δ ledger`
   - `lens_fact_ids ⊆ current reply-lens facts`
   - `evidence_ids ⊆ accumulated tool ledger`
   - Edit-success outcome requires nonempty accepted Δ.
   - Turn-1 Δ references are valid in later turns only when present in that session.
   - Forged or cross-session references fail closed.

8. Map accepted work into the existing `ImplementationResult`, durable candidate, and `ExecutorResult` envelope. Delta IDs are metadata pointing to canonical accepted-batch operations, not a new delta body.

9. Add:
   - `tests/test_executor_two_step_contracts.py`
   - `tests/test_executor_two_step_atomic.py`
   - `tests/test_executor_two_step_precedents.py`
   - Fact-ID cases to `tests/test_ir_laws.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_contracts.py \
  tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py \
  tests/test_porting_edit_session.py \
  tests/test_porting_edit_session_harness.py \
  tests/test_porting_edit_delta_contract.py \
  tests/test_ir_laws.py
```

Required fault injections:

- Stale baseline.
- Unknown schema.
- Socket/literal mismatch.
- Invalid mixed batch.
- Done-gate failure.
- First rejection then valid replacement.
- Two rejected submissions.
- Research timeout and empty result.
- Forged evidence ID.
- Forged lens fact ID.
- Cross-session delta ID.
- Claimed edit with zero accepted Δ.

---

# B05 — Profiles, report, profiler, and events

## Tasks

1. Update [profiles.py](/private/tmp/vc-twostep/vibecomfy/executor/profiles.py):
   - Keep `classify`, `research`, `implement`, and `reply` required.
   - Permit optional `execute`.
   - Reject every other extra stage.
   - Add typed `MissingProfileStageError`.
   - Resolve `execute` only for two-step.
   - Never fall back to `implement`.

2. Add explicit `execute` specs to:
   - `profile_data/default.toml`
   - `openai.toml`
   - `openrouter.toml`
   - `anthropic.toml`
   - `opensource.toml`

3. Update `Report`:
   - Serialize resolved `pipeline_mode` for both modes.
   - Add optional `execute` report only for two-step.
   - Include session identity, route, budget usage, tool/evidence IDs, accepted delta IDs, claim validation, replacement use, and self-assessment.
   - Keep the top-level executor envelope unchanged.

4. Update profiler data:
   - Add `pipeline_mode` to request/result records.
   - Add one `phase="execute"` span with continuation/tool/budget counters.
   - Preserve existing full-mode phase spans.

5. Update events:
   - Add `execute` start/working/completed/failed/skipped events for two-step.
   - Do not add `pipeline_mode` or other fields to existing full-mode websocket payloads.
   - Add `tests/fixtures/payload_contracts/websocket_executor_phase_execute.json`.
   - Preserve all existing event fixtures byte-for-byte.

6. Add/update:
   - `tests/test_executor_profiles.py`
   - `tests/test_executor_two_step_reporting.py`
   - Event cases in `tests/test_executor_flows.py`
   - Response fixture coverage in `tests/test_agent_executor_response.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_profiles.py \
  tests/test_executor_two_step_reporting.py \
  tests/test_executor_flows.py \
  tests/test_agent_executor_response.py \
  tests/test_agent_executor_durable.py
```

A fixture-level assertion must compare captured full-mode phase events against the pre-change JSON bytes.

---

# B06 — Unit, continuity, IR-law, and differential validation

## Tasks

1. Complete the five required thread-continuity cases in `tests/test_executor_two_step_continuity.py`:

   - Same session ID reuses one execute identity; turn-1 observations and accepted Δ are visible.
   - New chat-window ID starts fresh with no prior refs.
   - Route changes mid-thread after reclassification without replacing the execute session.
   - A follow-up claim referencing a missing turn-1 Δ fails.
   - Session budgets accumulate while every message receives only its route slice.

2. Add concurrency/recovery cases:
   - Two simultaneous messages for one session serialize or one fails stale.
   - Server restart reconstructs retained state through named ingest + canonical Δ replay.
   - Changed current canvas that does not match retained revision fails CAS.
   - Idempotent message replay does not duplicate tool calls or Δ.

3. Reuse all five IR laws against both modes:
   - Law 1: named-door workflow fidelity.
   - Law 2: editable interpretation.
   - Law 3: canonical Δ replay.
   - Law 4: lens boundaries and topology.
   - Law 5: deterministic bindings/provenance.
   Keep the existing lower-level law suite unchanged; add a mode-parameterized executor adapter around it.

4. `[XHARD]` Add:
   - `tests/executor_mode_harness.py`
   - `tests/test_executor_two_step_differential.py`

   The harness must:

   - Inject the same locked `ClassifyDecision` into both modes through a test-only seam.
   - Cover named-field edits, rewires, add/remove, inspect, research, adapt, and reorganise.
   - Compare `pi_edit(post)`, accepted Δ replay, judge outcome, evidence validity, failure family, latency, tokens, and cost.
   - Never compare prose equality.
   - Resolve and inventory all 57 IDs from `vibecomfy.intent._ledger`.
   - Refuse duplicate, missing, or unmanifested ledger IDs.

5. Add explicit full-path regressions for:
   - `classify_only`
   - `answer_only`
   - missing execute profile
   - route-policy coverage
   - tool denial
   - budget exhaustion
   - prompt sections
   - events/report compatibility

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_pipeline_mode.py \
  tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py \
  tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_contracts.py \
  tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py \
  tests/test_executor_two_step_continuity.py \
  tests/test_executor_two_step_reporting.py \
  tests/test_executor_two_step_differential.py \
  tests/test_executor_profiles.py \
  tests/test_executor_classify_only.py \
  tests/test_executor_flows.py \
  tests/test_ir_laws.py
```

Then:

```bash
PYTHONHASHSEED=0 python -m pytest -n 8 -q -p no:cacheprovider
```

No B06 oracle pass if any atomicity, reference-integrity, continuity, or full-mode compatibility test is quarantined or xfailed.

---

# B07 — Fifty-scenario lane and paired comparison harness

## Tasks

1. Extend the headless/live path:
   - `vibecomfy/agent/contracts.py`
   - `tests/live_agentic_harness/adapter.py`
   - `tests/live_agentic_harness/runner.py`
   - Add `--pipeline-mode {full,two_step}`.
   - Ensure every two-step scenario receives a stable per-window `session_id`.

2. Add `tests/live_agentic_harness/two_step_50_manifest.json`:
   - Reference all 100 canonical descriptors so strict directory validation remains intact.
   - Mark exactly 50 `included` and 50 `excluded`.
   - Stratify the included set by locked route, edit/non-edit behavior, media family, research need, graph size, and known failure family.
   - Do not select the first 50 alphabetically.
   - Pin descriptor and source hashes.

3. `[XHARD]` Add `tests/live_agentic_harness/compare_pipeline_modes.py`:
   - Classify each selected scenario once and persist `classification_lock.json`.
   - Run full and two-step with the identical decision.
   - Keep classification injection entirely test-only.
   - Use separate durable session roots per mode to avoid cross-contamination.
   - Produce per-scenario and aggregate JSON/Markdown.
   - Compare:
     - `pi_edit(post)`
     - canonical Δ replay
     - judge outcome
     - evidence/claim correctness
     - failure family
     - rejection/replacement use
     - unsupported claims
     - self-check/judge disagreement
     - latency, tokens, and cost
     - session-reuse rate

4. Add `tests/test_live_agentic_two_step_comparison.py`:
   - Manifest count/hash validation.
   - Lock completeness and route equality.
   - Pair completeness.
   - Comparator behavior without model calls.
   - Honest treatment of blocked provider/infra results.

5. Add a second comparator selection sourced from `ledger_scenario_ids()` for the complete 57-case ledger. This is separate from the fixed 50-case rollout lane.

6. Document commands and rollout order in `tests/live_agentic_harness/README.md`:
   - `respond/inspect`
   - simple `revise/reorganise`
   - bounded `research`
   - `adapt` opt-in only

## Acceptance gate

Deterministic wiring:

```bash
python -m pytest -q \
  tests/test_live_agentic_two_step_comparison.py \
  tests/test_live_agentic_harness_corpus_manifest.py \
  tests/test_live_agentic_runner_persistence.py
```

Validate the fixed lane without model calls:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json \
  --validate-only
```

Paired live run:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json \
  --tag two-step-50 \
  --capture-classifications \
  --max-workers 4 \
  --json
```

Complete 57-ledger differential:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --ledger ir-everywhere-57 \
  --tag two-step-ledger-57 \
  --capture-classifications \
  --max-workers 4 \
  --json
```

B07 passes only when:

- Both paired runs are complete.
- Every pair used the same locked classification.
- All Δ replays and claim-reference checks are valid.
- No full-mode compatibility regression appears.
- `respond/inspect` meet the initial non-inferiority gate.
- `adapt` results are reported but do not enable rollout automatically.

## Scope deliberately cut

- No new graph authority, edit DSL, or declared-target format.
- No native browser settings panel; request/env are the toggle.
- No automatic fallback or “escalate to full” behavior.
- No new tool registry.
- No provider-specific session implementation; continuity is host-owned and provider-independent.
- No model prose comparison in differential tests.
- No production rollout controller; rollout uses the fixed manifests and telemetry.

## Open questions to close during exploration

1. Cumulative session ceilings are unspecified.
   - Required decision: exact token, tool-call, wall-clock, accepted-batch, and lifetime limits.
   - Recommendation: explicit configuration values, not an implicit multiplier of the largest route slice.

2. Session lifetime and eviction are unspecified.
   - Recommendation: durable until the chat window is explicitly closed, with a conservative stale-session TTL used only for resource cleanup—not semantic reset.

3. Missing `session_id`.
   - Recommendation: browser establishes the tab-scoped ID before submission; custom/headless two-step callers without one receive a typed request error.

4. Oversized precedent bounds are unspecified.
   - Required decision: maximum rendered bytes/nodes/edges and deterministic relevance selector.
   - The implementation must expose omitted counts and forbid global claims.

5. Report compatibility.
   - Recommendation: serialize `pipeline_mode="full"` for full reports as the intentional additive schema change; keep full websocket events byte-identical.

6. External profile ownership.
   - Determine whether the packaged TOMLs are the sole shipping authority or must be mirrored into an Arnold package outside this worktree.

7. The 50-case mix.
   - Recommendation: select after classification-lock capture, with explicit route/family quotas committed into the manifest.

8. Multi-process server semantics.
   - Confirm whether the existing session lock is shared across all deployment workers. If not, B03 needs a process-safe lease or the runtime must pin a session to one worker.
tokens used
226,677
# Megado plan: VibeComfy `two_step` executor

Target: add `classify → execute` as an explicit, default-off pipeline mode while preserving the current full pipeline. The authoritative specification is [two-step-mode-design.md](/Users/peteromalley/Documents/vibecomfy-ir-everywhere/.oracle/two-step-mode-design.md).

Megado discipline: run the exploration briefs first, revise this plan until stable, freeze `.oracle/tasklist.md`, then execute one batch at a time. Commit and obtain an oracle `PASS` before starting the next batch.

## Non-negotiable invariants

- `PipelineMode = Literal["full", "two_step"]`.
- Resolution is request field → `VIBECOMFY_EXECUTOR_PIPELINE_MODE` → `"full"`.
- Branch only after classification, clarification persistence, `classify_only`, and `answer_only`.
- No automatic fallback between modes.
- Full-mode orchestration and websocket event payloads remain byte-compatible.
- Two-step means one host-managed execute session with bounded continuations, not one raw provider response.
- `session_id` is the chat-window identity. Never substitute `executor_id` or mint a new ID per message.
- The agent never receives raw ComfyUI JSON or full internal IR.
- All edits use the existing Python grammar and immutable interpreter.
- One atomic edit batch, with at most one complete replacement after rejection.
- Rejected batches produce zero Δ.
- No second target declaration or second delta representation.
- Claims are valid only through accepted Δ IDs, reply-lens fact IDs, and tool-ledger evidence IDs.
- The execute prompt explicitly presents `research → change → submit` and lists the exact tools available in each stage.
- Shadow rollout is operational; do not introduce an automatic route router or escalation framework.

## Pre-execution exploration

Dispatch these as parallel read-only Megado exploration briefs. Each finding should be under 300 words with file/line evidence, risks, and a recommended approach.

1. `provider-continuations.txt`
   - Trace `agent_backend.py`, provider/runtime workers, JSON response contracts, output-token controls, and model-attempt accounting.
   - Confirm the smallest provider-independent continuation mechanism.

2. `session-identity.txt`
   - Trace browser tab identity, first-turn `session_id`, durable session paths, locking, chat artifacts, process restart, and concurrent requests.
   - Decide how a retained execute session is reconstructed safely after restart.

3. `atomic-edit-cas.txt`
   - Trace `EditSession.apply_batch`, `interpret`, apply gates, request baseline hashes, structural hashes, accepted-batch serialization, and done gates.
   - Specify the exact preflight/CAS sequence.

4. `render-claim-ids.txt`
   - Trace `render`, topology facts, reply lenses, Hivemind workflow records, template loading, and oversized graph handling.
   - Propose deterministic delta/lens fact IDs without adding graph authority.

5. `profiles-events-report.txt`
   - Trace packaged and external profile ownership, profiler payloads, report fixtures, websocket phase fixtures, and downstream report consumers.

6. `differential-harness.txt`
   - Trace the live harness, intent judge, `pi_edit`, canonical replay, the 57-case owner ledger, and deterministic 50-case selection.
   - Specify test-only classification locking without a production bypass.

7. `budgets-policy.txt`
   - Trace current tool budgets, web-search policy, worker token limits, timeout enforcement, and usage capture.
   - Identify missing numeric cumulative-session ceilings.

After exploration, revise until `STABLE`, then freeze the batches below.

---

# B01 — Mode plumbing and dispatch toggle

## Tasks

1. Update [vibecomfy/executor/contracts.py](/private/tmp/vc-twostep/vibecomfy/executor/contracts.py):
   - Add `PipelineMode = Literal["full", "two_step"]`.
   - Add typed `PipelineModeRequestError` and `PipelineModeConfigurationError`.
   - Add `coerce_pipeline_mode()` and `resolve_pipeline_mode(request, environ=None)`.
   - Add optional `ExecutorRequest.pipeline_mode`.
   - Validate direct construction and `from_payload()`.
   - Preserve omission in `to_dict()` when unspecified.

2. Update [vibecomfy/agent/contracts.py](/private/tmp/vc-twostep/vibecomfy/agent/contracts.py):
   - Add optional `HeadlessAgentRequest.pipeline_mode`.
   - Carry it through parsing and `to_executor_request()`.

3. Update [vibecomfy/executor/core.py](/private/tmp/vc-twostep/vibecomfy/executor/core.py):
   - Resolve mode once for profiler/report use.
   - Preserve the existing classify and `answer_only` behavior.
   - Add the only orchestration branch immediately after the current `answer_only` block:
     ```python
     if pipeline_mode == "two_step":
         return _run_two_step(...)
     ```
   - Keep the existing research → implement → reply block structurally untouched.
   - For `classify_only`, full mode emits its existing skipped events; two-step emits only `execute: skipped`.

4. Add [vibecomfy/executor/two_step.py](/private/tmp/vc-twostep/vibecomfy/executor/two_step.py) with the typed entrypoint seam and a test-injectable outcome boundary. Real execution lands in B03–B04.

5. Add `tests/fixtures/payload_contracts/agent_executor_two_step_request.json`; do not rewrite the existing request fixture merely to include an optional field.

6. Add:
   - `tests/test_executor_pipeline_mode.py`
   - Mode round-trip cases to `tests/test_executor_contracts.py`
   - Branch/classify-only cases to `tests/test_executor_classify_only.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_pipeline_mode.py \
  tests/test_executor_contracts.py \
  tests/test_executor_classify_only.py \
  tests/test_executor_flows.py
```

Must prove:

- Request beats environment.
- Environment beats default.
- Invalid request value is a request error.
- Invalid environment value is a configuration error.
- Default is full.
- `classify_only` never resolves or invokes `execute`.
- `answer_only` reaches two-step only after its edit-forbidding rewrite.
- Full-mode phase calls and event payloads are unchanged.

---

# B02 — Route policy, tool gating, and host budgets

## Tasks

1. In `vibecomfy/executor/two_step.py`, add frozen types:
   - `TwoStepRoutePolicy`
   - `MessageBudget`
   - `SessionBudget`
   - `BudgetUsage`
   - `BudgetExceeded`

2. Define `TWO_STEP_ROUTE_POLICIES` with the authoritative route table:
   - `clarify`, `respond`: no tools; 2k; 30s.
   - `inspect`: `node_schema`; 4k; two calls; 60s.
   - `research`: Hivemind, registry, schema, templates, policy-enabled web; 8k; 180s.
   - `requires_custom_nodes`: registry and schema; 4k; 90s.
   - `revise`: schema, templates, suggestions, layout, Python; 8k; 180s.
   - `adapt`: all ten tools and Python; 12k; 240s.
   - `reorganise`: layout and Python; 6k; 120s.

3. Assert:
   ```python
   set(TWO_STEP_ROUTE_POLICIES) == set(_ROUTE_BEHAVIORS)
   ```
   Import `_ROUTE_BEHAVIORS` lazily to avoid moving or duplicating the full-mode route authority.

4. Reuse [tool_specs.py](/private/tmp/vc-twostep/vibecomfy/executor/tool_specs.py):
   - Keep exactly ten registered tools.
   - Use `tool_catalog_docs(..., allowed_names=...)` for advertisement.
   - Dispatch through the existing `ToolSpec` handlers/projectors.
   - Enforce the route allowlist before handler invocation or budget consumption.
   - Keep `web_search` disabled unless existing policy enables it.

5. Add hard budget checks before and after every model/tool call:
   - Per-message route slice.
   - Cumulative session ceiling.
   - Aggregate output tokens across continuations.
   - Per-tool/class call caps.
   - Apply/replacement counters.
   - Wall clock.

6. Extend optional parameters through:
   - `vibecomfy/comfy_nodes/agent/provider.py::run_model_turn`
   - `vibecomfy/comfy_nodes/agent/runtime.py::run_model_turn`
   - Worker construction
   so a continuation can receive the remaining output-token cap. `None` must preserve full-mode behavior.

7. Add:
   - `tests/test_executor_two_step_policy.py`
   - `tests/test_executor_two_step_tools.py`
   - Optional runtime-cap cases to `tests/test_agent_runtime_adapter.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py \
  tests/test_executor_hivemind_tools.py \
  tests/test_executor_lookup_tools.py \
  tests/test_executor_layout_hints.py \
  tests/test_agent_runtime_adapter.py
```

Must prove exact route coverage, exact advertised catalogs, denial before dispatch, disabled web policy, every budget family, aggregate-token exhaustion, and cumulative-session exhaustion.

---

# B03 — Execute prompt and thread-continuous session

## Tasks

1. `[XHARD]` Add [vibecomfy/executor/two_step_session.py](/private/tmp/vc-twostep/vibecomfy/executor/two_step_session.py):
   - Key identity directly by normalized chat-window `session_id`.
   - Persist a compact append-only execute transcript beneath the existing durable session directory.
   - Persist accepted Δ references, lens facts, evidence ledger, replies, route history, cumulative budget usage, and last retained workflow revision.
   - Serialize same-session messages with the existing session lock discipline.
   - Detect concurrent/stale message attempts before model work.
   - Cache the retained `EditSession` in process; reconstruct only through a named ingest door plus canonical accepted deltas after restart.
   - Never use an in-memory dictionary as the sole authority.

2. Establish first-turn identity before execution:
   - Browser submit flow must obtain/reuse its existing tab-scoped `session_id` before sending a two-step request.
   - Two-step HTTP/headless requests without a usable `session_id` fail as typed invalid requests.
   - Update `vibecomfy/comfy_nodes/web/agent_submit_flow.js` only as needed to reuse the existing tab-scoped allocator; do not add a settings UI.

3. `[XHARD]` Add `build_two_step_execute_messages()` to [prompts.py](/private/tmp/vc-twostep/vibecomfy/executor/prompts.py):
   - Include every authoritative design section.
   - Add an explicit `STAGES AND AVAILABLE TOOLS` section:
     1. `RESEARCH` — exact research tools available for this route.
     2. `CHANGE` — exact advisory/schema/layout tools plus whether Python editing is allowed.
     3. `SUBMIT` — no tools; final JSON contract only.
   - State that unavailable tools are denied by the host.
   - State the same-window continuity rule verbatim in substance.
   - For non-edit routes, explicitly say no change may be submitted.
   - Render only the route-allowed catalog.

4. `[XHARD]` Implement the bounded continuation loop:
   - Add `run_execute_turn()` to `vibecomfy/executor/agent_backend.py`.
   - Parse host actions: registered tool call, Python batch submission, or final contract.
   - Re-inject the compact accumulated transcript and the new message into every continuation.
   - Do not depend on provider-native memory.
   - Preserve one logical execute-session identity across messages and route changes.
   - Derive `research_attempt` from the session ledger.

5. Add prompt goldens:
   - `tests/fixtures/executor/two_step_prompt_clarify.txt`
   - `..._respond.txt`
   - `..._inspect.txt`
   - `..._research.txt`
   - `..._requires_custom_nodes.txt`
   - `..._revise.txt`
   - `..._adapt.txt`
   - `..._reorganise.txt`

6. Add:
   - `tests/test_executor_two_step_prompt.py`
   - Initial session tests in `tests/test_executor_two_step_continuity.py`
   - Browser identity coverage in the existing browser submit-flow suite

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_continuity.py \
  tests/test_routes_session_sanitization.py \
  tests/test_agent_executor_durable.py

npm test -- --runInBand
```

The gate must inspect every prompt golden and prove the visible sequence is `research → change → submit`, with exact tools and no union catalog leakage.

---

# B04 — Atomic edit, precedent projection, and claim references

## Tasks

1. In `two_step.py`, add the execute state machine:
   - Research/tool continuations may precede editing.
   - Exactly one complete Python batch may be accepted.
   - One complete replacement is allowed only after rejection.
   - After acceptance, further edit submissions are denied.
   - A second rejection returns no candidate.
   - Parse, resolution, CAS, channel, bounds, or done-gate failure returns zero Δ.

2. Reuse:
   - `EditSession.apply_batch()`
   - `interpret(pre, batch)`
   - `verify_apply()`
   - Existing emit and durable candidate machinery
   without changing general full-mode `max_batches` behavior.

3. Add request/session CAS preflight:
   - Compare the request baseline and current canvas projection with the retained session revision.
   - Validate every parsed operation’s CAS expectations before mutation.
   - Return typed stale-baseline diagnostics to the one replacement continuation.

4. Add `render_fact_pack()` to [vibecomfy/porting/render.py](/private/tmp/vc-twostep/vibecomfy/porting/render.py):
   - Derive stable fact IDs from canonical lens items.
   - Text lenses use canonical rendered lines; topology uses canonical tuples.
   - IDs reference facts but do not create another graph representation.
   - Preserve the Law 4 lens ceiling.

5. Extend `HivemindRecordView` and `serve_hivemind_record()`:
   - Workflow records expose immutable `surface + topology`.
   - Never expose raw workflow JSON to the model.
   - Oversized records use a deterministic relevant subgraph with explicit node/edge omitted counts and `global_topology_complete=false`.
   - Apply the same sanitization to workflow-valued ready-template observations.

6. Add typed final contracts in `executor/contracts.py`:
   - `TwoStepClaimRefs`
   - `TwoStepSelfAssessment`
   - `TwoStepFinal`
   - `TwoStepExecutionReport`

7. Implement `validate_two_step_final()`:
   - `delta_ids ⊆ accumulated accepted Δ ledger`
   - `lens_fact_ids ⊆ current reply-lens facts`
   - `evidence_ids ⊆ accumulated tool ledger`
   - Edit-success outcome requires nonempty accepted Δ.
   - Turn-1 Δ references are valid in later turns only when present in that session.
   - Forged or cross-session references fail closed.

8. Map accepted work into the existing `ImplementationResult`, durable candidate, and `ExecutorResult` envelope. Delta IDs are metadata pointing to canonical accepted-batch operations, not a new delta body.

9. Add:
   - `tests/test_executor_two_step_contracts.py`
   - `tests/test_executor_two_step_atomic.py`
   - `tests/test_executor_two_step_precedents.py`
   - Fact-ID cases to `tests/test_ir_laws.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_contracts.py \
  tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py \
  tests/test_porting_edit_session.py \
  tests/test_porting_edit_session_harness.py \
  tests/test_porting_edit_delta_contract.py \
  tests/test_ir_laws.py
```

Required fault injections:

- Stale baseline.
- Unknown schema.
- Socket/literal mismatch.
- Invalid mixed batch.
- Done-gate failure.
- First rejection then valid replacement.
- Two rejected submissions.
- Research timeout and empty result.
- Forged evidence ID.
- Forged lens fact ID.
- Cross-session delta ID.
- Claimed edit with zero accepted Δ.

---

# B05 — Profiles, report, profiler, and events

## Tasks

1. Update [profiles.py](/private/tmp/vc-twostep/vibecomfy/executor/profiles.py):
   - Keep `classify`, `research`, `implement`, and `reply` required.
   - Permit optional `execute`.
   - Reject every other extra stage.
   - Add typed `MissingProfileStageError`.
   - Resolve `execute` only for two-step.
   - Never fall back to `implement`.

2. Add explicit `execute` specs to:
   - `profile_data/default.toml`
   - `openai.toml`
   - `openrouter.toml`
   - `anthropic.toml`
   - `opensource.toml`

3. Update `Report`:
   - Serialize resolved `pipeline_mode` for both modes.
   - Add optional `execute` report only for two-step.
   - Include session identity, route, budget usage, tool/evidence IDs, accepted delta IDs, claim validation, replacement use, and self-assessment.
   - Keep the top-level executor envelope unchanged.

4. Update profiler data:
   - Add `pipeline_mode` to request/result records.
   - Add one `phase="execute"` span with continuation/tool/budget counters.
   - Preserve existing full-mode phase spans.

5. Update events:
   - Add `execute` start/working/completed/failed/skipped events for two-step.
   - Do not add `pipeline_mode` or other fields to existing full-mode websocket payloads.
   - Add `tests/fixtures/payload_contracts/websocket_executor_phase_execute.json`.
   - Preserve all existing event fixtures byte-for-byte.

6. Add/update:
   - `tests/test_executor_profiles.py`
   - `tests/test_executor_two_step_reporting.py`
   - Event cases in `tests/test_executor_flows.py`
   - Response fixture coverage in `tests/test_agent_executor_response.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_profiles.py \
  tests/test_executor_two_step_reporting.py \
  tests/test_executor_flows.py \
  tests/test_agent_executor_response.py \
  tests/test_agent_executor_durable.py
```

A fixture-level assertion must compare captured full-mode phase events against the pre-change JSON bytes.

---

# B06 — Unit, continuity, IR-law, and differential validation

## Tasks

1. Complete the five required thread-continuity cases in `tests/test_executor_two_step_continuity.py`:

   - Same session ID reuses one execute identity; turn-1 observations and accepted Δ are visible.
   - New chat-window ID starts fresh with no prior refs.
   - Route changes mid-thread after reclassification without replacing the execute session.
   - A follow-up claim referencing a missing turn-1 Δ fails.
   - Session budgets accumulate while every message receives only its route slice.

2. Add concurrency/recovery cases:
   - Two simultaneous messages for one session serialize or one fails stale.
   - Server restart reconstructs retained state through named ingest + canonical Δ replay.
   - Changed current canvas that does not match retained revision fails CAS.
   - Idempotent message replay does not duplicate tool calls or Δ.

3. Reuse all five IR laws against both modes:
   - Law 1: named-door workflow fidelity.
   - Law 2: editable interpretation.
   - Law 3: canonical Δ replay.
   - Law 4: lens boundaries and topology.
   - Law 5: deterministic bindings/provenance.
   Keep the existing lower-level law suite unchanged; add a mode-parameterized executor adapter around it.

4. `[XHARD]` Add:
   - `tests/executor_mode_harness.py`
   - `tests/test_executor_two_step_differential.py`

   The harness must:

   - Inject the same locked `ClassifyDecision` into both modes through a test-only seam.
   - Cover named-field edits, rewires, add/remove, inspect, research, adapt, and reorganise.
   - Compare `pi_edit(post)`, accepted Δ replay, judge outcome, evidence validity, failure family, latency, tokens, and cost.
   - Never compare prose equality.
   - Resolve and inventory all 57 IDs from `vibecomfy.intent._ledger`.
   - Refuse duplicate, missing, or unmanifested ledger IDs.

5. Add explicit full-path regressions for:
   - `classify_only`
   - `answer_only`
   - missing execute profile
   - route-policy coverage
   - tool denial
   - budget exhaustion
   - prompt sections
   - events/report compatibility

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_pipeline_mode.py \
  tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py \
  tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_contracts.py \
  tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py \
  tests/test_executor_two_step_continuity.py \
  tests/test_executor_two_step_reporting.py \
  tests/test_executor_two_step_differential.py \
  tests/test_executor_profiles.py \
  tests/test_executor_classify_only.py \
  tests/test_executor_flows.py \
  tests/test_ir_laws.py
```

Then:

```bash
PYTHONHASHSEED=0 python -m pytest -n 8 -q -p no:cacheprovider
```

No B06 oracle pass if any atomicity, reference-integrity, continuity, or full-mode compatibility test is quarantined or xfailed.

---

# B07 — Fifty-scenario lane and paired comparison harness

## Tasks

1. Extend the headless/live path:
   - `vibecomfy/agent/contracts.py`
   - `tests/live_agentic_harness/adapter.py`
   - `tests/live_agentic_harness/runner.py`
   - Add `--pipeline-mode {full,two_step}`.
   - Ensure every two-step scenario receives a stable per-window `session_id`.

2. Add `tests/live_agentic_harness/two_step_50_manifest.json`:
   - Reference all 100 canonical descriptors so strict directory validation remains intact.
   - Mark exactly 50 `included` and 50 `excluded`.
   - Stratify the included set by locked route, edit/non-edit behavior, media family, research need, graph size, and known failure family.
   - Do not select the first 50 alphabetically.
   - Pin descriptor and source hashes.

3. `[XHARD]` Add `tests/live_agentic_harness/compare_pipeline_modes.py`:
   - Classify each selected scenario once and persist `classification_lock.json`.
   - Run full and two-step with the identical decision.
   - Keep classification injection entirely test-only.
   - Use separate durable session roots per mode to avoid cross-contamination.
   - Produce per-scenario and aggregate JSON/Markdown.
   - Compare:
     - `pi_edit(post)`
     - canonical Δ replay
     - judge outcome
     - evidence/claim correctness
     - failure family
     - rejection/replacement use
     - unsupported claims
     - self-check/judge disagreement
     - latency, tokens, and cost
     - session-reuse rate

4. Add `tests/test_live_agentic_two_step_comparison.py`:
   - Manifest count/hash validation.
   - Lock completeness and route equality.
   - Pair completeness.
   - Comparator behavior without model calls.
   - Honest treatment of blocked provider/infra results.

5. Add a second comparator selection sourced from `ledger_scenario_ids()` for the complete 57-case ledger. This is separate from the fixed 50-case rollout lane.

6. Document commands and rollout order in `tests/live_agentic_harness/README.md`:
   - `respond/inspect`
   - simple `revise/reorganise`
   - bounded `research`
   - `adapt` opt-in only

## Acceptance gate

Deterministic wiring:

```bash
python -m pytest -q \
  tests/test_live_agentic_two_step_comparison.py \
  tests/test_live_agentic_harness_corpus_manifest.py \
  tests/test_live_agentic_runner_persistence.py
```

Validate the fixed lane without model calls:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json \
  --validate-only
```

Paired live run:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json \
  --tag two-step-50 \
  --capture-classifications \
  --max-workers 4 \
  --json
```

Complete 57-ledger differential:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --ledger ir-everywhere-57 \
  --tag two-step-ledger-57 \
  --capture-classifications \
  --max-workers 4 \
  --json
```

B07 passes only when:

- Both paired runs are complete.
- Every pair used the same locked classification.
- All Δ replays and claim-reference checks are valid.
- No full-mode compatibility regression appears.
- `respond/inspect` meet the initial non-inferiority gate.
- `adapt` results are reported but do not enable rollout automatically.

## Scope deliberately cut

- No new graph authority, edit DSL, or declared-target format.
- No native browser settings panel; request/env are the toggle.
- No automatic fallback or “escalate to full” behavior.
- No new tool registry.
- No provider-specific session implementation; continuity is host-owned and provider-independent.
- No model prose comparison in differential tests.
- No production rollout controller; rollout uses the fixed manifests and telemetry.

## Open questions to close during exploration

1. Cumulative session ceilings are unspecified.
   - Required decision: exact token, tool-call, wall-clock, accepted-batch, and lifetime limits.
   - Recommendation: explicit configuration values, not an implicit multiplier of the largest route slice.

2. Session lifetime and eviction are unspecified.
   - Recommendation: durable until the chat window is explicitly closed, with a conservative stale-session TTL used only for resource cleanup—not semantic reset.

3. Missing `session_id`.
   - Recommendation: browser establishes the tab-scoped ID before submission; custom/headless two-step callers without one receive a typed request error.

4. Oversized precedent bounds are unspecified.
   - Required decision: maximum rendered bytes/nodes/edges and deterministic relevance selector.
   - The implementation must expose omitted counts and forbid global claims.

5. Report compatibility.
   - Recommendation: serialize `pipeline_mode="full"` for full reports as the intentional additive schema change; keep full websocket events byte-identical.

6. External profile ownership.
   - Determine whether the packaged TOMLs are the sole shipping authority or must be mirrored into an Arnold package outside this worktree.

7. The 50-case mix.
   - Recommendation: select after classification-lock capture, with explicit route/family quotas committed into the manifest.

8. Multi-process server semantics.
   - Confirm whether the existing session lock is shared across all deployment workers. If not, B03 needs a process-safe lease or the runtime must pin a session to one worker.
