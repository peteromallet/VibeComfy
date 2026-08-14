Reading additional input from stdin...
2026-08-13T14:28:17.005589Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:17.007302Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:17.007317Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb86-08c7-7c82-b512-d525d336ab98
--------
user
# MEGADO CHECKPOINT — Batch B04 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the B04 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**B04 — Real-schema authority.** Tasks + acceptance from `.oracle/tasklist.md` (B04 section). Diff to review: `git diff f2661b01..ff6ae9c8` (D13 PASS SHA → B04 commit). Executor: DeepSeek V4 Flash.

## Executor evidence

- New helper `with_provisional_gap_filler(authoritative, provisional)` in `vibecomfy/schema/provider.py` (+ re-export in `schema/__init__.py`, + snapshot update in `test_api_surface.py`).
- All 7 construction sites now real-first through the helper: `_frag_research.py` (:821, :874, :922), `_frag_response_contract.py:793` (cross-turn — no longer poisons session), `_frag_batch_loop.py:910`, `edit_batch_repl.py:1116`.
- Focused tests: 45 passed (`tests/test_comfy_nodes_agent_edit.py` + backend_spine, -k schema/precedence/provisional/real_schema/widget/cross_turn).
- Broader slice: 62 passed / 1 failed / 1 skipped — the 1 failure is `test_api_surface.py::test_public_module_all_snapshots_are_intentional`, which is in the PRE-EXISTING quarantine baseline `tests/quarantine/emitter_parity_surface.txt` (owner emitter-parity-surface, reason: legacy baseline failures). Verified: that snapshot delta concerns `RawWidgetPayload`/`WorkflowSource` in the workflow lens, predates B04, and `vibecomfy/workflow.py` is untouched by this range.

## Review focus (adversarial)

1. The helper composes real-first (CompositeSchemaProvider(authoritative, provisional)) — verify get_schema first-match + schemas() reverse-merge semantics still make the FIRST provider dominant at every site.
2. ALL SEVEN sites (grep `CompositeSchemaProvider` and `with_provisional_gap_filler` across vibecomfy/): no provisional-first construction remains anywhere; no helper factory can reintroduce wrong precedence.
3. Cross-turn: `_frag_response_contract.py:793` previously poisoned session AND state — confirm the fix composes `(session.schema_provider, provisional)` and the cross-turn regression exists + passes.
4. Widget/choice shadowing: provisional `widget_N` names and empty choices cannot shadow real semantic names/choices (fixture).
5. Enum: invalid values rejected before mutation for add and set (existing mechanism tests still green); missing local asset filenames remain warning-only.
6. Scope: only B04 files; `git diff --check f2661b01..ff6ae9c8` clean.
7. Run the focused slice yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks; skip the quarantined surface test).

## Output

First line: `B04 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–7) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit MEGADO oracle checkpoint. I’ll follow its gate discipline, inspect the exact commit range and B04 acceptance criteria, then run the permitted focused tests without modifying the worktree.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 102ms:
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
The MEGADO checkpoint discipline calls for independent verification passes, so I’m splitting the read-only audit into two parallel reviews: provider precedence/site coverage, and regression/scope/test evidence. I’ll independently inspect the acceptance criteria and reconcile both reviews before issuing the binary gate.
2026-08-13T14:28:42.142558Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:42.142717Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:42.142749Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:46.596252Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:46.596730Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T14:28:46.596995Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "rg -n -A80 -B8 '"'^## B04|''^### B04|B04 —|B04 -'"' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git status --short --branch && git log --oneline --decorate -8' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git diff --stat f2661b01..ff6ae9c8 && git diff --name-status f2661b01..ff6ae9c8 && git diff --check f2661b01..ff6ae9c8' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "rg -n 'CompositeSchemaProvider|with_provisional_gap_filler' vibecomfy tests" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 170ms:
128-- Source-workflow hashes resolve before D13 passes.
129-
130-### Oracle checkpoint
131-
132-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
133-
134----
135-
136:## B04 — Real-schema authority
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
178-   - normalize reroutes to terminal endpoints;
179-   - normalize loop-cloned UIDs to their canonical consumer UID.
180-3. Feed the canonical before/after sets into the pin fence.
181-4. Refuse when semantic sets genuinely differ or endpoint resolution is ambiguous/unresolved.
182-5. Preserve canonical before/after sets in diagnostics.
183-6. Do not revive dead link-count refusal strings or construct a second topology abstraction.
184-
185-### Acceptance
186-
187-- Multiplicity-only Set/Get expansion passes.
188-- Equivalent reroute, loop-clone, link-renumbering, and nested lowering passes.
189-- Added, removed, repointed, orphaned, or output-port-changed consumers refuse.
190-- Unresolved/cyclic paths terminate deterministically and fail closed.
191-- Multi-output identity is preserved.
192-- B02 preservation tests remain green.
193-
194-### Oracle checkpoint
195-
196-Require both false-positive and true-topology-change fixtures to pass before B05-lite.
197-
198----
199-
200-## B05-lite — Journaled unexpected-exception rollback `[HARD]`
201-
202-### Tasks
203-
204-1. Create a loop-entry rollback journal covering:
205-   - existing mutable session snapshot;
206-   - `value_default_context`;
207-   - UI payload, batch accumulators, budget, and exit fields;
208-   - exact bytes-or-absence of rendered Python, candidate UI, model request/response, and messages artifacts.
209-2. Cover the full mutating path through apply, render, `done()`, and final evidence promotion with one exception boundary.
210-3. On unexpected exception:
211-   - restore session state;
212-   - restore files byte-for-byte;
213-   - truncate appended state;
214-   - close the allocated durable turn as aborted;
215-   - re-raise.
216-4. Persist a separate bounded typed abort diagnostic after restoration.

 succeeded in 131ms:
## oracle-run
?? .oracle/checkins/batch-B04.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
ff6ae9c8 (HEAD -> oracle-run) megado B04: with_provisional_gap_filler helper — all 7 schema sites real-first incl. _frag_response_contract (cross-turn) + _frag_batch_loop; seven-site precedence test; 45 focused tests green
f2661b01 megado: record D13 oracle PASS (ea421528)
ea421528 megado D13 rework2: judge verdicts derived from criteria, never model self-declared pass_ — string-typed booleans/contradictory verdicts fail closed; 78 focused tests green
5aa73c53 megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green
b39f0c91 megado D13: authoritative 100-scenario manifest (SHA-256), manifest-driven runner discovery, 3 mislabeled edits corrected, 35 semantic rubrics, 2 health controls, REVISIONS.md — 71 focused tests green
0f015101 megado: record B01 oracle PASS (0b265092)
0b265092 megado B01 rework3: redact JSON-quoted sensitive fields (api_key/authorization/token) in failure previews; malformed-JSON safe; durable model_attempts.json regression — 380 focused tests green
1bd1b04b megado B01 rework2: harness retry derived from canonical typed evidence (conflicting-flags regression); artifact sanitization covers every string leaf incl. ordinary content/url fields — 35 focused tests green

 succeeded in 208ms:
tests/test_comfy_nodes_agent_edit.py:20018:# CompositeSchemaProvider.get_schema is first-match-wins and schemas() merges
tests/test_comfy_nodes_agent_edit.py:20117:def test_schema_precedence_helper_with_provisional_gap_filler_both_views() -> None:
tests/test_comfy_nodes_agent_edit.py:20119:    from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
tests/test_comfy_nodes_agent_edit.py:20125:    composite = with_provisional_gap_filler(real, provisional)
tests/test_comfy_nodes_agent_edit.py:20249:    from vibecomfy.schema import CompositeSchemaProvider
tests/test_comfy_nodes_agent_edit.py:20297:    assert isinstance(provider, CompositeSchemaProvider)
tests/test_comfy_nodes_agent_edit.py:20324:        CompositeSchemaProvider,
tests/test_comfy_nodes_agent_edit.py:20326:        with_provisional_gap_filler,
tests/test_comfy_nodes_agent_edit.py:20335:        with_provisional_gap_filler(real, provisional),
tests/test_comfy_nodes_agent_edit.py:20457:    assert isinstance(baseline, CompositeSchemaProvider)
tests/test_schema.py:20:    CompositeSchemaProvider,
tests/test_schema.py:92:    provider = CompositeSchemaProvider(
tests/test_api_surface.py:29:        "NodeCallValidationReport", "CompositeSchemaProvider", "ConversionSchemaProvider",
tests/test_api_surface.py:34:        "validate_node_call", "with_provisional_gap_filler",
vibecomfy/comfy_nodes/agent/_frag_research.py:811:            from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_research.py:821:                state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
vibecomfy/comfy_nodes/agent/_frag_research.py:838:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_research.py:874:    state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
vibecomfy/comfy_nodes/agent/_frag_research.py:886:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_research.py:922:    state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:782:    from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793:    enriched = with_provisional_gap_filler(session.schema_provider, provisional)
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:411:        CompositeSchemaProvider,
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:434:    return CompositeSchemaProvider(*providers)
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:899:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:910:        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1104:        CompositeSchemaProvider, ProvisionalRegistrySchemaProvider = _import_from("vibecomfy.schema", "CompositeSchemaProvider"), _import_from("vibecomfy.schema", "ProvisionalRegistrySchemaProvider")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1105:        with_provisional_gap_filler = _import_from("vibecomfy.schema", "with_provisional_gap_filler")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1116:        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
vibecomfy/schema/__init__.py:7:    CompositeSchemaProvider,
vibecomfy/schema/__init__.py:26:    with_provisional_gap_filler,
vibecomfy/schema/__init__.py:35:    "CompositeSchemaProvider",
vibecomfy/schema/__init__.py:56:    "with_provisional_gap_filler",
vibecomfy/schema/provider.py:496:class CompositeSchemaProvider:
vibecomfy/schema/provider.py:519:def with_provisional_gap_filler(
vibecomfy/schema/provider.py:522:) -> CompositeSchemaProvider:
vibecomfy/schema/provider.py:525:    ``CompositeSchemaProvider.get_schema`` is first-match-wins and
vibecomfy/schema/provider.py:533:    return CompositeSchemaProvider(authoritative, provisional)
vibecomfy/schema/provider.py:1050:) -> RuntimeSchemaProvider | LocalSchemaProvider | AuthoringSchemaProvider | CompositeSchemaProvider:

 succeeded in 324ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/briefs/batch-B04.md                        |  42 ++
 tests/test_api_surface.py                          |   2 +-
 tests/test_comfy_nodes_agent_edit.py               | 511 +++++++++++++++++++++
 vibecomfy/comfy_nodes/agent/_frag_batch_loop.py    |   4 +-
 vibecomfy/comfy_nodes/agent/_frag_research.py      |  12 +-
 .../comfy_nodes/agent/_frag_response_contract.py   |   4 +-
 vibecomfy/comfy_nodes/agent/edit_batch_repl.py     |   3 +-
 vibecomfy/schema/__init__.py                       |   2 +
 vibecomfy/schema/provider.py                       |  17 +
 9 files changed, 585 insertions(+), 12 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/briefs/batch-B04.md
M	tests/test_api_surface.py
M	tests/test_comfy_nodes_agent_edit.py
M	vibecomfy/comfy_nodes/agent/_frag_batch_loop.py
M	vibecomfy/comfy_nodes/agent/_frag_research.py
M	vibecomfy/comfy_nodes/agent/_frag_response_contract.py
M	vibecomfy/comfy_nodes/agent/edit_batch_repl.py
M	vibecomfy/schema/__init__.py
M	vibecomfy/schema/provider.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc 'git diff --find-renames --find-copies --unified=80 f2661b01..ff6ae9c8 -- vibecomfy/schema/provider.py vibecomfy/schema/__init__.py vibecomfy/comfy_nodes/agent/_frag_research.py vibecomfy/comfy_nodes/agent/_frag_response_contract.py vibecomfy/comfy_nodes/agent/_frag_batch_loop.py vibecomfy/comfy_nodes/agent/edit_batch_repl.py tests/test_api_surface.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "nl -ba vibecomfy/schema/provider.py | sed -n '470,550p;1020,1075p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "nl -ba vibecomfy/comfy_nodes/agent/_frag_orchestration.py | sed -n '385,450p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "sed -n '1,240p' .oracle/briefs/batch-B04.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 290ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/test_api_surface.py b/tests/test_api_surface.py
index d0540f23..ab1f19fc 100644
--- a/tests/test_api_surface.py
+++ b/tests/test_api_surface.py
@@ -1,55 +1,55 @@
 from __future__ import annotations

 import importlib


 PUBLIC_EXPORT_SNAPSHOTS = {
     "vibecomfy": [
         "Artifact", "Image", "Video", "Audio", "Latent", "Mask", "Handle",
         "VibeWorkflow", "RawWidgetPayload", "VibeNode", "VibeEdge", "VibeInput", "VibeOutput",
         "WorkflowRequirements", "WorkflowSource", "ValidationIssue", "ValidationReport",
         "workflow_from_file", "workflow_from_id", "workflow_from_template", "workflow_from_ready",
         "ready_template_ids", "load_workflow_any", "load_workflow_json", "load_template",
         "find_repo_root", "ensure_plugins_loaded", "image", "video", "blocks", "patches",
         "router", "run", "run_sync", "run_embedded", "run_embedded_sync",
     ],
     "vibecomfy.workflow": [
         "OPAQUE_COMPONENT_CLASS_RE", "ValidationIssue", "ValidationReport", "VibeEdge",
         "VibeInput", "VibeNode", "VibeOutput", "VibeWorkflow", "WorkflowRequirements",
         "WorkflowSource",
     ],
     "vibecomfy.handles": ["Handle"],
     "vibecomfy.errors": [
         "ContextVarBindingError", "ConversionParityError", "DriftError", "ModelAssetError",
         "QueueError", "RuntimeNodeError", "SchemaValidationError", "SubgraphFreshnessError",
         "VibeComfyError",
     ],
     "vibecomfy.schema": [
         "AuthoringSchemaProvider", "InputSpec", "NodeCallValidationIssue",
         "NodeCallValidationReport", "CompositeSchemaProvider", "ConversionSchemaProvider",
         "LocalSchemaProvider", "NodeSchema", "ObjectInfoSchemaProvider", "OutputSpec",
         "RuntimeSchemaProvider", "SchemaIndexError", "SchemaProvider", "SchemaSourceInfo",
         "SourceSchemaProvider", "get_authoring_schema_provider", "get_schema_provider",
         "schema_for", "schema_registry_empty", "schemas_for", "socket_types_compatible",
-        "validate_node_call",
+        "validate_node_call", "with_provisional_gap_filler",
     ],
     "vibecomfy.artifacts": ["Artifact", "ArtifactKind", "Image", "Video", "Audio", "Latent", "Mask"],
     "vibecomfy.templates": [
         "InputSpec", "ModelAsset", "ReadyMetadata", "_at", "_current_workflow_or_raise",
         "_derive_output_kind", "finalize", "finalize_ready", "new_workflow", "node",
         "template_input", "template_output",
     ],
 }


 def test_public_module_all_snapshots_are_intentional() -> None:
     for module_name, expected in PUBLIC_EXPORT_SNAPSHOTS.items():
         module = importlib.import_module(module_name)
         assert list(module.__all__) == expected


 def test_method_level_apis_are_not_module_export_snapshots() -> None:
     from vibecomfy.workflow import VibeWorkflow

     assert "export_to_json" not in PUBLIC_EXPORT_SNAPSHOTS["vibecomfy.workflow"]
     assert hasattr(VibeWorkflow, "export_to_json")
diff --git a/vibecomfy/comfy_nodes/agent/_frag_batch_loop.py b/vibecomfy/comfy_nodes/agent/_frag_batch_loop.py
index bd3c8066..ebac902a 100644
--- a/vibecomfy/comfy_nodes/agent/_frag_batch_loop.py
+++ b/vibecomfy/comfy_nodes/agent/_frag_batch_loop.py
@@ -819,128 +819,128 @@ def _actionable_plan_dependency_status(
                         _resolver_candidate_supports_class(candidate, class_type)
                         or (
                             source in {"comfy-registry", "comfy_registry"}
                             and not registry_resolution_is_ambiguous
                         )
                     )
                 ):
                     if _candidate_stable_key(candidate) not in {
                         _candidate_stable_key(existing) for existing in candidates
                     }:
                         candidates.append(candidate)
         except Exception as exc:  # noqa: BLE001 - unresolved is the safe result
             warnings.append(f"{type(exc).__name__}: {exc}")

         record: dict[str, Any] = {
             "class_type": class_type,
             "availability": (
                 "registry_resolvable" if candidates else "unresolved"
             ),
         }
         if candidates:
             record["resolver_candidates"] = candidates
         if attempted:
             record["source_tiers_attempted"] = list(dict.fromkeys(attempted))
         if warnings:
             record["warnings"] = list(dict.fromkeys(warnings))
         dependencies.append(record)
     return tuple(dependencies)


 def _retry_after_dependency_preflight_failure(
     state: AgentEditState,
     unresolved_runtime_classes: tuple[str, ...],
 ) -> None:
     """Reject one poisoned synthesis while preserving evidence for a retry.

     The batch author still receives the inquiry, current graph, and retrieved
     precedent slices, but the unresolved candidate graph is removed so it
     cannot abort or prescribe the next attempt.
     """
     notes = (
         dict(state.execution_protocol_notes)
         if isinstance(state.execution_protocol_notes, Mapping)
         else {}
     )
     notes.pop("adaptation_plan", None)
     notes["adaptation_plan_actionability"] = {
         "actionability": "non_actionable",
         "non_actionable_reason": "dependency_preflight_failed_retry_synthesis",
     }
     notes["synthesis_retry"] = {
         "trigger": "dependency_preflight_failed",
         "rejected_class_types": list(unresolved_runtime_classes),
         "strategy": "choose another retrieved precedent or bounded direct edit",
     }
     state.execution_protocol_notes = notes
     state.executor_adaptation_plan = None


 def _hydrate_actionable_registry_dependencies(state: AgentEditState) -> None:
     from vibecomfy.comfy_nodes.agent.edit import (LOGGER, _candidate_stable_key)  # T-039 late import: host namespace lookup; resolved at call time
     candidates: list[dict[str, Any]] = []
     for dependency in state.runtime_dependencies:
         if dependency.get("availability") != "registry_resolvable":
             continue
         raw_candidates = dependency.get("resolver_candidates")
         if isinstance(raw_candidates, list):
             candidates.extend(
                 dict(candidate)
                 for candidate in raw_candidates
                 if isinstance(candidate, Mapping)
             )
     new_candidates = [
         candidate
         for candidate in candidates
         if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
     ]
     if not new_candidates:
         return
     try:
-        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
+        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler

         provisional = ProvisionalRegistrySchemaProvider(new_candidates)
         if not provisional.schemas():
             return
         state.provisional_registry_candidate_hashes = frozenset(
             {
                 *state.provisional_registry_candidate_hashes,
                 *(_candidate_stable_key(candidate) for candidate in new_candidates),
             }
         )
-        state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
+        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
     except Exception as exc:  # noqa: BLE001 - workflow evidence may still hydrate it
         LOGGER.debug("planned registry dependency hydration unavailable: %s", exc)


 __all__ = (
     "_BATCH_PROTOCOL_RETRY_PROMPT",
     "_MANIFEST_COMPACTOR_MAX_ANCHORS",
     "_MANIFEST_COMPACTOR_MAX_EDGES",
     "_MANIFEST_COMPACTOR_MAX_NODES",
     "_MAX_EXECUTION_PROTOCOL_LIST_ITEMS",
     "_MAX_EXECUTION_PROTOCOL_SOURCES",
     "_MAX_EXECUTION_PROTOCOL_STRING",
     "_actionable_plan_dependency_status",
     "_actionable_plan_required_new_classes",
     "_actionable_plan_ui_only_classes",
     "_active_manifest_from_plan",
     "_batch_protocol_parse_reason",
     "_batch_protocol_retry_messages",
     "_compact_execution_protocol_notes_for_prompt",
     "_compact_protocol_jsonish",
     "_compact_protocol_list",
     "_compact_protocol_string",
     "_compact_research_source_for_prompt",
     "_copy_compact_protocol_fields",
     "_dependency_graph_class_types",
     "_evaluate_execution_plan_after_candidate_update",
     "_execution_plan_done_refusal_hint",
     "_execution_plan_status_for_prompt",
     "_hydrate_actionable_registry_dependencies",
     "_is_ui_only_annotation_class_type",
     "_malformed_model_json_detail",
     "_manifest_compact_payload",
     "_manifest_is_complete",
     "_manifest_required_new_classes",
     "_retry_after_dependency_preflight_failure",
 )
diff --git a/vibecomfy/comfy_nodes/agent/_frag_research.py b/vibecomfy/comfy_nodes/agent/_frag_research.py
index 95d22eb1..40cfa22e 100644
--- a/vibecomfy/comfy_nodes/agent/_frag_research.py
+++ b/vibecomfy/comfy_nodes/agent/_frag_research.py
@@ -731,272 +731,272 @@ def _workflow_class_types_from_research_context(
                     "_" in class_type
                     or class_type.startswith(("ADE", "VHS", "IPAdapter", "ACN"))
                     or " " in class_type
                 ):
                     continue
             elif state.schema_provider.get_schema(class_type) is None and not (
                 "_" in class_type
                 or class_type.startswith(("ADE", "VHS", "IPAdapter", "ACN"))
                 or " " in class_type
             ):
                 # For prompt focus we want already-known core classes too, but
                 # unknown plain names from workflow metadata are usually labels
                 # or weak aliases rather than authorable node types.
                 continue
             classes.append(class_type)
             if len(classes) >= max_classes:
                 return tuple(classes)
     return tuple(classes)


 def _workflow_schema_candidates_from_research_context(
     state: AgentEditState,
 ) -> tuple[dict[str, Any], ...]:
     candidates: list[dict[str, Any]] = []
     seen: set[str] = set()
     for source in _iter_research_precedent_sources(state):
         workflow_schema = source.get("workflow_schema")
         if not isinstance(workflow_schema, Mapping) or not workflow_schema:
             continue
         source_kind = str(source.get("source") or "")
         pack = str(source.get("pack") or "")
         if "workflow" not in source_kind and pack != "workflow":
             continue
         key = json.dumps(
             {
                 "url": source.get("url") or source.get("source_workflow_path") or "",
                 "classes": sorted(str(class_type) for class_type in workflow_schema),
             },
             sort_keys=True,
         )
         if key in seen:
             continue
         seen.add(key)
         candidates.append(
             {
                 "pack": {
                     "name": source.get("class_type") or source.get("name") or "workflow_json",
                     "slug": source.get("pack") or "workflow_json",
                     "source": source.get("source") or "external_workflow",
                     "url": source.get("url") or source.get("source_workflow_path") or "",
                 },
                 "provisional_schema": {
                     "version": "workflow-json",
                     "schema": {"nodes": workflow_schema},
                     "runnable": False,
                 },
                 "expected_classes": sorted(str(class_type) for class_type in workflow_schema),
                 "validation_mode": "workflow_json_provisional",
                 "warnings": [
                     "Schema derived from workflow JSON; runtime node pack may need installation."
                 ],
                 "stable_install_hash": f"workflow-json:{key}",
             }
         )
     return tuple(candidates)


 def _hydrate_research_precedent_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
     """Compile workflow-observed missing node classes into authoring capabilities.

     Adapt-route prefetch provides workflow evidence before the batch agent runs.
     Exact workflow JSON schemas are allowed as provisional authoring schemas;
     registry/Manager resolution is an additional source of stronger evidence,
     not a prerequisite for placing a reviewable candidate node.
     """
     from vibecomfy.comfy_nodes.agent.edit import _candidate_stable_key  # T-038 late import: exec'd-host fragment; resolved at call time
     missing_classes = _workflow_class_types_from_research_context(state)
     workflow_candidates = _workflow_schema_candidates_from_research_context(state)
     if workflow_candidates:
         try:
-            from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
+            from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler

             provisional = ProvisionalRegistrySchemaProvider(workflow_candidates)
             if provisional.schemas():
                 state.provisional_registry_candidate_hashes = frozenset(
                     {
                         *state.provisional_registry_candidate_hashes,
                         *(_candidate_stable_key(candidate) for candidate in workflow_candidates),
                     }
                 )
-                state.schema_provider = CompositeSchemaProvider(state.schema_provider, provisional)
+                state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
         except Exception as exc:  # noqa: BLE001 - keep registry fallback below available
             LOGGER.debug("workflow schema provisional hydration unavailable: %s", exc)

     if not missing_classes:
         return workflow_candidates

     unresolved_missing_classes = tuple(
         class_type
         for class_type in missing_classes
         if state.schema_provider.get_schema(class_type) is None
     )
     if not unresolved_missing_classes:
         return workflow_candidates

     try:
         from vibecomfy.registry.pack_resolver import resolve_missing_nodes
-        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
+        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
     except Exception as exc:  # noqa: BLE001 - registry hydration is best-effort
         LOGGER.debug("research precedent schema hydration unavailable: %s", exc)
         return workflow_candidates

     candidates: list[dict[str, Any]] = []
     for class_type in unresolved_missing_classes:
         try:
             resolution = resolve_missing_nodes(class_type, query_intent="class_name")
         except Exception as exc:  # noqa: BLE001 - keep context-only behavior on lookup failure
             LOGGER.debug("research precedent schema hydration failed for %s: %s", class_type, exc)
             continue
         for raw_candidate in getattr(resolution, "candidates", ()) or ():
             candidate = _candidate_dict(raw_candidate)
             if candidate is None:
                 continue
             if not _resolver_candidate_supports_class(candidate, class_type):
                 continue
             candidates.append(candidate)

     new_candidates = [
         candidate
         for candidate in candidates
         if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
     ]
     if not new_candidates:
         return workflow_candidates
     provisional = ProvisionalRegistrySchemaProvider(new_candidates)
     if not provisional.schemas():
         return ()
     state.provisional_registry_candidate_hashes = frozenset(
         {
             *state.provisional_registry_candidate_hashes,
             *(_candidate_stable_key(candidate) for candidate in new_candidates),
         }
     )
-    state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
+    state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
     return (*workflow_candidates, *new_candidates)


 def _hydrate_current_graph_unknown_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
     from vibecomfy.comfy_nodes.agent.edit import _candidate_stable_key  # T-038 late import: exec'd-host fragment; resolved at call time
     missing_classes = _graph_class_types_missing_from_schema(state.graph, state.schema_provider)
     if not missing_classes:
         return ()

     try:
         from vibecomfy.registry.pack_resolver import resolve_missing_nodes
-        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
+        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
     except Exception as exc:  # noqa: BLE001 - registry hydration is best-effort
         LOGGER.debug("registry schema hydration unavailable: %s", exc)
         return ()

     candidates: list[dict[str, Any]] = []
     for class_type in missing_classes:
         try:
             resolution = resolve_missing_nodes(class_type, query_intent="class_name")
         except Exception as exc:  # noqa: BLE001 - keep existing blocker on lookup failure
             LOGGER.debug("registry schema hydration failed for %s: %s", class_type, exc)
             continue
         for raw_candidate in getattr(resolution, "candidates", ()) or ():
             candidate = _candidate_dict(raw_candidate)
             if candidate is None:
                 continue
             if not _resolver_candidate_supports_class(candidate, class_type):
                 continue
             candidates.append(candidate)

     new_candidates = [
         candidate
         for candidate in candidates
         if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
     ]
     if not new_candidates:
         return ()
     provisional = ProvisionalRegistrySchemaProvider(new_candidates)
     if not provisional.schemas():
         return ()
     state.provisional_registry_candidate_hashes = frozenset(
         {
             *state.provisional_registry_candidate_hashes,
             *(_candidate_stable_key(candidate) for candidate in new_candidates),
         }
     )
-    state.schema_provider = CompositeSchemaProvider(state.schema_provider, provisional)
+    state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
     return tuple(new_candidates)


 def _revision_no_candidate_reason(evidence: RevisionEvidence) -> str | None:
     if evidence.safe_candidate_possible:
         return None
     if evidence.topology.missing_graph:
         return "no_graph"
     return "no_changes"


 def _executor_classification_text(state: AgentEditState) -> str:
     classification = state.request_payload.get("executor_classification")
     if isinstance(classification, Mapping):
         return " ".join(
             str(classification.get(key) or "")
             for key in ("plan_summary", "intent", "route", "task")
         )
     return ""


 def _effective_implementation_task(state: AgentEditState) -> str:
     # Carry intent/route/task into the editor's task, but NOT plan_summary: the
     # classifier's one-sentence plan commits to a semantic solution/placement,
     # and on ambiguous requests it commits wrongly (e.g. "add ImageScale after
     # VAEDecode"). Let the editor decide placement from the raw graph + request.
     # The guard in _runtime_code_additive_request still reads the full
     # classification text via _executor_classification_text, so this only
     # changes what the editor SEES, not the safety predicates.
     classification = state.request_payload.get("executor_classification")
     context = ""
     if isinstance(classification, Mapping):
         context = " ".join(
             str(classification.get(key) or "")
             for key in ("intent", "route", "task")
         ).strip()
     if not context:
         return state.task
     return (
         f"{state.task}\n\n"
         "Resolved executor context:\n"
         f"{context}"
     )


 def _runtime_code_additive_request(state: AgentEditState) -> bool:
     classification_text = _executor_classification_text(state)
     task = (
         f"{state.task} {state.request_payload.get('query') or ''} "
         f"{classification_text}"
     ).lower()
     explicit_frame_extraction = (
         ("extract" in task and "frame" in task)
         or ("first frame" in task and ("save" in task or "png" in task or "image" in task))
     )
     return (
         (
             "code node" in task
             or "runtime code" in task
             or "vibecomfy.exec" in task
             or "imagecode" in task
             or ("pil" in task and "transformation" in task)
             or explicit_frame_extraction
         )
         and ("pil" in task or "image" in task or "frame" in task or "process" in task)
     )


 def _executor_requested_implementation(state: AgentEditState) -> bool:
     classification = state.request_payload.get("executor_classification")
     if isinstance(classification, Mapping) and "implement" in classification:
         return bool(classification.get("implement"))
     return _canonical_agent_edit_route(state.route) in {"revise", "adapt", "dev"}


 def _state_runtime_execution_requested(state: AgentEditState) -> bool:
     runtime = state.request_payload.get("runtime")
     return isinstance(runtime, Mapping) and bool(runtime.get("execution_requested"))


diff --git a/vibecomfy/comfy_nodes/agent/_frag_response_contract.py b/vibecomfy/comfy_nodes/agent/_frag_response_contract.py
index 935194ec..00cb6243 100644
--- a/vibecomfy/comfy_nodes/agent/_frag_response_contract.py
+++ b/vibecomfy/comfy_nodes/agent/_frag_response_contract.py
@@ -702,172 +702,172 @@ def _resolver_candidates_from_batch_turns(state: AgentEditState) -> list[dict[st
             continue
         statements = turn.get("statements")
         if not isinstance(statements, list):
             continue
         for statement in statements:
             if not isinstance(statement, Mapping):
                 continue
             detail = statement.get("detail")
             if not isinstance(detail, Mapping):
                 continue
             for key_name in ("resolver_candidates", "workflow_schema_candidates"):
                 raw_candidates = detail.get(key_name)
                 if not isinstance(raw_candidates, list):
                     continue
                 for raw_candidate in raw_candidates:
                     if not isinstance(raw_candidate, Mapping):
                         continue
                     candidate = dict(raw_candidate)
                     key = (
                         str(candidate.get("stable_install_hash") or "")
                         or json.dumps(candidate, sort_keys=True, default=str)
                     )
                     if key in seen:
                         continue
                     seen.add(key)
                     candidates.append(candidate)
     return candidates


 def _resolver_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
     candidates: list[dict[str, Any]] = []
     for statement in getattr(batch_result, "statements", ()) or ():
         detail = getattr(statement, "detail", None)
         if not isinstance(detail, Mapping):
             continue
         for key_name in ("resolver_candidates", "workflow_schema_candidates"):
             raw_candidates = detail.get(key_name)
             if not isinstance(raw_candidates, list):
                 continue
             for raw_candidate in raw_candidates:
                 if isinstance(raw_candidate, Mapping):
                     candidates.append(dict(raw_candidate))
     return candidates


 def _workflow_schema_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
     candidates: list[dict[str, Any]] = []
     for statement in getattr(batch_result, "statements", ()) or ():
         detail = getattr(statement, "detail", None)
         if not isinstance(detail, Mapping):
             continue
         raw_candidates = detail.get("workflow_schema_candidates")
         if not isinstance(raw_candidates, list):
             continue
         for raw_candidate in raw_candidates:
             if isinstance(raw_candidate, Mapping):
                 candidates.append(dict(raw_candidate))
     return candidates


 def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
     return (
         str(candidate.get("stable_install_hash") or "")
         or json.dumps(dict(candidate), sort_keys=True, default=str)
     )


 def _enrich_schema_provider_from_resolver_candidates(
     state: AgentEditState,
     session: Any,
     candidates: list[dict[str, Any]],
 ) -> None:
     from vibecomfy.comfy_nodes.agent.edit import (_candidate_stable_key)  # T-039 late import: host namespace lookup; resolved at call time
     new_candidates = [
         candidate
         for candidate in candidates
         if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
     ]
     if not new_candidates:
         return
-    from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
+    from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler

     provisional = ProvisionalRegistrySchemaProvider(new_candidates)
     if not provisional.schemas():
         return
     state.provisional_registry_candidate_hashes = frozenset(
         {
             *state.provisional_registry_candidate_hashes,
             *(_candidate_stable_key(candidate) for candidate in new_candidates),
         }
     )
-    enriched = CompositeSchemaProvider(provisional, session.schema_provider)
+    enriched = with_provisional_gap_filler(session.schema_provider, provisional)
     session.schema_provider = enriched
     state.schema_provider = enriched


 def _legacy_failure_response(
     state: AgentEditState,
     context: TurnContext,
     *,
     failure: AgentError,
 ) -> dict[str, Any]:
     from vibecomfy.comfy_nodes.agent.edit import (FailureKind, TurnOutcome, _stage_audit, build_legacy_agent_edit_v1, derive_apply_eligibility, derive_gates, product_failure_envelope_fields)  # T-039 late import: host namespace lookup; resolved at call time
     derive_gates(
         context,
         baseline_graph_hash=state.baseline_graph_hash,
         client_graph_hash=state.submit_structural_graph_hash,
     )
     failure = dataclasses.replace(
         failure,
         canvas_apply_allowed=context.canvas_apply_allowed,
         queue_allowed=context.queue_allowed,
     )
     try:
         audit_ref = _stage_audit(state, context, failure=failure)
         failure = dataclasses.replace(failure, audit_ref=audit_ref)
     except Exception as audit_exc:
         failure = dataclasses.replace(failure, audit_error=str(audit_exc))
     response = failure.to_dict()
     if failure.kind is FailureKind.STALE_STATE_MISMATCH:
         eligibility = derive_apply_eligibility(
             context,
             live_structural_graph_hash=state.baseline_graph_hash,
             submit_structural_graph_hash=state.submit_structural_graph_hash,
         )
     else:
         eligibility = derive_apply_eligibility(context, has_candidate=False)
     response.update(
         {
             "eligibility": eligibility.to_dict(),
             "canvas_apply_allowed": context.canvas_apply_allowed,
             "queue_allowed": context.queue_allowed,
         }
     )
     response = build_legacy_agent_edit_v1(response)
     response.update(product_failure_envelope_fields(failure))
     failure_context = response.get("agent_failure_context")
     issues = failure_context.get("issues") if isinstance(failure_context, Mapping) else None
     if isinstance(issues, list):
         for issue in issues:
             if not isinstance(issue, Mapping):
                 continue
             recovery = issue.get("rebaseline_recovery")
             if isinstance(recovery, Mapping):
                 response["rebaseline_recovery"] = dict(recovery)
                 break
     response["internal_outcome"] = TurnOutcome.from_failure(failure).to_dict()
     return response


 def _build_batch_repl_failure_response(
     state: AgentEditState,
     context: TurnContext,
     *,
     failure: AgentError,
 ) -> dict[str, Any]:
     from vibecomfy.comfy_nodes.agent.edit import (LOGGER, _build_compatibility_response_fields, _fallback_narrative_message, _legacy_failure_response, _legacy_narrative_debug_status, _narrate_final_message, _narrative_debug_fields, _prepare_narrative_artifact_paths, _record_narrative_artifacts, _response_apply_eligibility, _response_artifacts_with_execution_plan, _session_artifact_response_fields)  # T-039 late import: host namespace lookup; resolved at call time
     response = _legacy_failure_response(state, context, failure=failure)
     compatibility_fields = _build_compatibility_response_fields(state)
     response.update(compatibility_fields)
     response.update(_session_artifact_response_fields(state))
     response["eligibility"] = response["apply_eligibility"]
     apply_eligibility = _response_apply_eligibility(response.get("apply_eligibility"))
     public_outcome_kind = (
         response["outcome"].get("kind")
         if isinstance(response.get("outcome"), Mapping)
         else None
     )
     _prepare_narrative_artifact_paths(state)
     try:
         message = _narrate_final_message(
             state,
diff --git a/vibecomfy/comfy_nodes/agent/edit_batch_repl.py b/vibecomfy/comfy_nodes/agent/edit_batch_repl.py
index 7c87fd99..a99eb1a5 100644
--- a/vibecomfy/comfy_nodes/agent/edit_batch_repl.py
+++ b/vibecomfy/comfy_nodes/agent/edit_batch_repl.py
@@ -1025,171 +1025,172 @@ def _actionable_plan_dependency_status(deps,
                         deps._resolver_candidate_supports_class(candidate, class_type)
                         or (
                             source in {"comfy-registry", "comfy_registry"}
                             and not registry_resolution_is_ambiguous
                         )
                     )
                 ):
                     if deps._candidate_stable_key(candidate) not in {
                         deps._candidate_stable_key(existing) for existing in candidates
                     }:
                         candidates.append(candidate)
         except Exception as exc:  # noqa: BLE001 - unresolved is the safe result
             warnings.append(f"{type(exc).__name__}: {exc}")

         record: dict[str, Any] = {
             "class_type": class_type,
             "availability": (
                 "registry_resolvable" if candidates else "unresolved"
             ),
         }
         if candidates:
             record["resolver_candidates"] = candidates
         if attempted:
             record["source_tiers_attempted"] = list(dict.fromkeys(attempted))
         if warnings:
             record["warnings"] = list(dict.fromkeys(warnings))
         dependencies.append(record)
     return tuple(dependencies)


 def _retry_after_dependency_preflight_failure(
     state: AgentEditState,
     unresolved_runtime_classes: tuple[str, ...],
 ) -> None:
     """Reject one poisoned synthesis while preserving evidence for a retry.

     The batch author still receives the inquiry, current graph, and retrieved
     precedent slices, but the unresolved candidate graph is removed so it
     cannot abort or prescribe the next attempt.
     """
     notes = (
         dict(state.execution_protocol_notes)
         if isinstance(state.execution_protocol_notes, Mapping)
         else {}
     )
     notes.pop("adaptation_plan", None)
     notes["adaptation_plan_actionability"] = {
         "actionability": "non_actionable",
         "non_actionable_reason": "dependency_preflight_failed_retry_synthesis",
     }
     notes["synthesis_retry"] = {
         "trigger": "dependency_preflight_failed",
         "rejected_class_types": list(unresolved_runtime_classes),
         "strategy": "choose another retrieved precedent or bounded direct edit",
     }
     state.execution_protocol_notes = notes
     state.executor_adaptation_plan = None


 def _hydrate_actionable_registry_dependencies(deps, state: AgentEditState) -> None:
     candidates: list[dict[str, Any]] = []
     for dependency in state.runtime_dependencies:
         if dependency.get("availability") != "registry_resolvable":
             continue
         raw_candidates = dependency.get("resolver_candidates")
         if isinstance(raw_candidates, list):
             candidates.extend(
                 dict(candidate)
                 for candidate in raw_candidates
                 if isinstance(candidate, Mapping)
             )
     new_candidates = [
         candidate
         for candidate in candidates
         if deps._candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
     ]
     if not new_candidates:
         return
     try:
         CompositeSchemaProvider, ProvisionalRegistrySchemaProvider = _import_from("vibecomfy.schema", "CompositeSchemaProvider"), _import_from("vibecomfy.schema", "ProvisionalRegistrySchemaProvider")
+        with_provisional_gap_filler = _import_from("vibecomfy.schema", "with_provisional_gap_filler")

         provisional = ProvisionalRegistrySchemaProvider(new_candidates)
         if not provisional.schemas():
             return
         state.provisional_registry_candidate_hashes = frozenset(
             {
                 *state.provisional_registry_candidate_hashes,
                 *(deps._candidate_stable_key(candidate) for candidate in new_candidates),
             }
         )
-        state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
+        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
     except Exception as exc:  # noqa: BLE001 - workflow evidence may still hydrate it
         deps.LOGGER.debug("planned registry dependency hydration unavailable: %s", exc)


 def _stage_agent_batch_repl(globals_dict: Mapping[str, Any],
     state: AgentEditState,
     _context: TurnContext,
     *,
     deepseek_client: DeepSeekClient | None = None,
     route: str | None = None,
     model: str | None = None,
     effort: str | None = None,
     client_id: str | None = None,
     conversation_messages: list[dict[str, Any]] | None = None,
 ) -> deps.StageResult:
     deps = build_edit_batch_repl_deps(globals_dict)
     edit_session_module = importlib.import_module("vibecomfy.porting.edit.session")
     ValueDefaultContext = _import_from("vibecomfy.porting.edit.apply_types", "ValueDefaultContext")

     start = time.monotonic()
     prepared_ui = state.guard_original_ui or state.graph
     state.runtime_dependencies = _actionable_plan_dependency_status(deps, state)
     unresolved_runtime_classes = tuple(
         str(dependency.get("class_type"))
         for dependency in state.runtime_dependencies
         if dependency.get("availability") == "unresolved"
     )
     if unresolved_runtime_classes:
         # Hard-block: planned runtime classes with neither a live schema nor an
         # exact registry candidate cannot be authored against.  Stop BEFORE the
         # model is called and surface a clarification (HEAD contract).  Do NOT
         # fall through to authoring and do NOT retry by discarding the plan —
         # there is nothing to retry with.  (W-07's dependency_preflight.json
         # diagnostic is preserved as a write-only artifact alongside the
         # clarification artifacts.)
         missing_text = ", ".join(unresolved_runtime_classes)
         message = (
             "This edit requires custom-node classes that could not be found in "
             f"the live ComfyUI runtime or Comfy Registry: {missing_text}. "
             "Install or identify the providing custom-node pack, restart ComfyUI, "
             "and then retry this edit."
         )
         deps.write_json_artifact(
             state.turn_dir / "dependency_preflight.json",
             {
                 "ignored_ui_annotation_classes": list(
                     _actionable_plan_ui_only_classes(
                         state.execution_protocol_notes.get("adaptation_plan")
                         if isinstance(state.execution_protocol_notes, Mapping)
                         else None
                     )
                     if isinstance(state.execution_protocol_notes, Mapping)
                     else ()
                 ),
                 "unresolved_runtime_classes": list(unresolved_runtime_classes),
                 "runtime_dependencies": list(state.runtime_dependencies),
                 "retrying_synthesis": False,
             },
         )
         state.batch_exit_mode = deps._BATCH_EXIT_PURE_CLARIFY
         state.batch_final_summary = "Stopped before authoring because dependencies are unresolved."
         state.user_message = message
         state.report = {
             "clarification_required": True,
             "graph_unchanged": True,
             "queue_blockers": [],
             "authoring_blocker": {
                 "reason": "unresolved_runtime_classes",
                 "missing_runtime_classes": list(unresolved_runtime_classes),
                 "runtime_dependencies": list(state.runtime_dependencies),
                 "message": message,
             },
         }
         state.python_before = ""
         state.python_after = ""
         state.before_py_path.write_text("", encoding="utf-8")
         state.after_py_path.write_text("", encoding="utf-8")
         deps.write_json_artifact(state.model_request_path, {"turns": []})
         deps.write_json_artifact(
             state.model_response_path,
diff --git a/vibecomfy/schema/__init__.py b/vibecomfy/schema/__init__.py
index c4cbd428..c94d6bf7 100644
--- a/vibecomfy/schema/__init__.py
+++ b/vibecomfy/schema/__init__.py
@@ -1,55 +1,57 @@
 from __future__ import annotations

 from .call_validation import NodeCallValidationIssue, NodeCallValidationReport, validate_node_call
 from .provider import (
     AuthoringSchemaProvider,
     InputSpec,
     CompositeSchemaProvider,
     ConversionSchemaProvider,
     LocalSchemaProvider,
     NodeSchema,
     ObjectInfoSchemaProvider,
     OutputSpec,
     ProvisionalRegistrySchemaProvider,
     RuntimeSchemaProvider,
     SchemaIndexError,
     SchemaProvider,
     SchemaSourceInfo,
     SourceScanWarning,
     SourceSchemaProvider,
     get_authoring_schema_provider,
     get_schema_provider,
     is_workflow_stub_schema,
     schema_for,
     schema_registry_empty,
     schemas_for,
+    with_provisional_gap_filler,
 )
 from .validate import socket_types_compatible

 __all__ = [
     "AuthoringSchemaProvider",
     "InputSpec",
     "NodeCallValidationIssue",
     "NodeCallValidationReport",
     "CompositeSchemaProvider",
     "ConversionSchemaProvider",
     "LocalSchemaProvider",
     "NodeSchema",
     "ObjectInfoSchemaProvider",
     "OutputSpec",
     "ProvisionalRegistrySchemaProvider",
     "RuntimeSchemaProvider",
     "SchemaIndexError",
     "SchemaProvider",
     "SchemaSourceInfo",
     "SourceScanWarning",
     "SourceSchemaProvider",
     "get_authoring_schema_provider",
     "get_schema_provider",
     "is_workflow_stub_schema",
     "schema_for",
     "schema_registry_empty",
     "schemas_for",
     "socket_types_compatible",
     "validate_node_call",
+    "with_provisional_gap_filler",
 ]
diff --git a/vibecomfy/schema/provider.py b/vibecomfy/schema/provider.py
index d89a77d6..bc71f3cd 100644
--- a/vibecomfy/schema/provider.py
+++ b/vibecomfy/schema/provider.py
@@ -439,160 +439,177 @@ class ObjectInfoIndexSchemaProvider:
                 str(key): str(value)
                 for key, value in data.items()
                 if isinstance(key, str) and isinstance(value, str)
                 and not str(value).lower().endswith("@stub.json")
             }
         return self._index

     def raw_widget_order(self, class_type: str) -> list[str | None] | None:
         """Return the raw ``object_info_widget_order`` including ``None``/null entries.

         Returns ``None`` when the class is not found in the cache.
         This is the authoritative slot-count source (nulls denote UI-only slots);
         the compacted null-free list is for widget VALUES emission only.
         """
         filename = self._load_index().get(class_type)
         if not filename:
             return None
         data = self._file_cache.get(filename)
         if data is None:
             data = load_object_info_cache(self.root / filename) or {}
             self._file_cache[filename] = data
         info = data.get(class_type)
         if not isinstance(info, dict):
             return None
         from vibecomfy.porting.object_info.consume import (  # noqa: PLC0415
             reconciled_object_info_widget_order,
         )

         raw_order = reconciled_object_info_widget_order(info)
         return raw_order if raw_order else None

     def _load_schema(self, class_type: str) -> NodeSchema | None:
         filename = self._load_index().get(class_type)
         if not filename:
             return None
         data = self._file_cache.get(filename)
         if data is None:
             data = load_object_info_cache(self.root / filename) or {}
             self._file_cache[filename] = data
         info = data.get(class_type)
         if not isinstance(info, dict):
             return None
         schema = _schema_from_object_info(class_type, info)
         return NodeSchema(
             class_type=schema.class_type,
             pack=schema.pack,
             inputs=schema.inputs,
             outputs=schema.outputs,
             source_provider="object_info_index",
             source_cache_path=str(self.root / filename),
             source_package=schema.pack,
             source_version=str(info.get("pack_version"))
             if isinstance(info.get("pack_version"), str)
             else None,
         )


 class CompositeSchemaProvider:
     def __init__(self, *providers: SchemaProvider) -> None:
         self.providers = providers

     def get(self, class_type: str) -> NodeSchema | None:
         return self.get_schema(class_type)

     def get_schema(self, class_type: str) -> NodeSchema | None:
         for provider in self.providers:
             schema = provider.get_schema(class_type)
             if schema is not None:
                 return schema
         return None

     def schemas(self) -> dict[str, NodeSchema]:
         merged: dict[str, NodeSchema] = {}
         for provider in reversed(self.providers):
             schemas = schemas_for(provider)
             if schemas is not None:
                 merged.update({str(key): value for key, value in schemas.items() if isinstance(value, NodeSchema)})
         return merged


+def with_provisional_gap_filler(
+    authoritative: SchemaProvider,
+    provisional: SchemaProvider,
+) -> CompositeSchemaProvider:
+    """Compose real/runtime schemas first; provisional fills only gaps.
+
+    ``CompositeSchemaProvider.get_schema`` is first-match-wins and
+    ``schemas()`` merges providers in reverse order, so the FIRST provider
+    dominates both views. Provisional registry/workflow-JSON schemas are weaker
+    evidence than real/runtime object-info schemas: they must never shadow a
+    real schema (semantic names/choices), only answer classes the
+    authoritative provider cannot. Every agent hydration site composes through
+    this helper so the ordering invariant lives in exactly one place.
+    """
+    return CompositeSchemaProvider(authoritative, provisional)
+
+
 class ProvisionalRegistrySchemaProvider:
     """Evidence-backed schemas for missing custom nodes discovered by registry research.

     These schemas are not runtime proof that a node is installed. They only let
     the editor represent a missing custom node class in a candidate graph when a
     registry/manager lookup supplied either a concrete object_info-like schema
     or trusted class-map evidence for that exact class. Weak class-name
     extraction from GitHub/web search remains install guidance, not an
     authoring schema.
     """

     def __init__(self, candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
         self._schemas = _provisional_schemas_from_candidates(candidates)

     def get(self, class_type: str) -> NodeSchema | None:
         return self.get_schema(class_type)

     def get_schema(self, class_type: str) -> NodeSchema | None:
         return self._schemas.get(class_type)

     def schemas(self) -> dict[str, NodeSchema]:
         return dict(self._schemas)


 class AuthoringSchemaProvider:
     """Offline schema provider for schema-only authoring and CLI inspection.

     Unlike ``ConversionSchemaProvider``, this provider intentionally prefers the
     committed structured object_info cache before local/generated
     ``node_index.json`` so schema-only commands are not shadowed by stale local
     indexes.
     """

     def __init__(
         self,
         *,
         object_info_index_root: str | Path | None = None,
         object_info_cache_path: str | Path | None = None,
         object_info_cache_dir: str | Path = "out/cache",
         source_roots: list[str | Path] | None = None,
         node_index_path: str | Path = "node_index.json",
         on_demand_schemas: bool | None = None,
     ) -> None:
         self.object_info_index_root = Path(object_info_index_root) if object_info_index_root is not None else _default_object_info_index_root()
         self.object_info_cache_path = Path(object_info_cache_path) if object_info_cache_path is not None else None
         self.object_info_cache_dir = Path(object_info_cache_dir)
         self.node_index_path = Path(node_index_path)
         self.on_demand_schemas = on_demand_schemas
         self._providers: tuple[SchemaProvider, ...] = self._build_providers(source_roots=source_roots, on_demand_schemas=on_demand_schemas)

     def get(self, class_type: str) -> NodeSchema | None:
         return self.get_schema(class_type)

     def get_schema(self, class_type: str) -> NodeSchema | None:
         builtin = _builtin_schema(class_type)
         if builtin is not None:
             return builtin
         for provider in self._providers:
             try:
                 schema = provider.get_schema(class_type)
             except SchemaIndexError:
                 continue
             if schema is not None:
                 return schema
         return None

     def schemas(self) -> dict[str, NodeSchema]:
         merged: dict[str, NodeSchema] = {}
         for provider in reversed(self._providers):
             schemas = schemas_for(provider)
             if schemas is not None:
                 merged.update({str(key): value for key, value in schemas.items() if isinstance(value, NodeSchema)})
         return merged

     def _build_providers(self, *, source_roots: list[str | Path] | None, on_demand_schemas: bool | None = None) -> tuple[SchemaProvider, ...]:
         providers: list[SchemaProvider] = []
         if self.object_info_cache_path is not None:
             providers.append(ObjectInfoSchemaProvider(self.object_info_cache_path))
         providers.append(ObjectInfoIndexSchemaProvider(self.object_info_index_root))
         if self.object_info_cache_path is None:

 succeeded in 254ms:
   470	    def _load_schema(self, class_type: str) -> NodeSchema | None:
   471	        filename = self._load_index().get(class_type)
   472	        if not filename:
   473	            return None
   474	        data = self._file_cache.get(filename)
   475	        if data is None:
   476	            data = load_object_info_cache(self.root / filename) or {}
   477	            self._file_cache[filename] = data
   478	        info = data.get(class_type)
   479	        if not isinstance(info, dict):
   480	            return None
   481	        schema = _schema_from_object_info(class_type, info)
   482	        return NodeSchema(
   483	            class_type=schema.class_type,
   484	            pack=schema.pack,
   485	            inputs=schema.inputs,
   486	            outputs=schema.outputs,
   487	            source_provider="object_info_index",
   488	            source_cache_path=str(self.root / filename),
   489	            source_package=schema.pack,
   490	            source_version=str(info.get("pack_version"))
   491	            if isinstance(info.get("pack_version"), str)
   492	            else None,
   493	        )
   494
   495
   496	class CompositeSchemaProvider:
   497	    def __init__(self, *providers: SchemaProvider) -> None:
   498	        self.providers = providers
   499
   500	    def get(self, class_type: str) -> NodeSchema | None:
   501	        return self.get_schema(class_type)
   502
   503	    def get_schema(self, class_type: str) -> NodeSchema | None:
   504	        for provider in self.providers:
   505	            schema = provider.get_schema(class_type)
   506	            if schema is not None:
   507	                return schema
   508	        return None
   509
   510	    def schemas(self) -> dict[str, NodeSchema]:
   511	        merged: dict[str, NodeSchema] = {}
   512	        for provider in reversed(self.providers):
   513	            schemas = schemas_for(provider)
   514	            if schemas is not None:
   515	                merged.update({str(key): value for key, value in schemas.items() if isinstance(value, NodeSchema)})
   516	        return merged
   517
   518
   519	def with_provisional_gap_filler(
   520	    authoritative: SchemaProvider,
   521	    provisional: SchemaProvider,
   522	) -> CompositeSchemaProvider:
   523	    """Compose real/runtime schemas first; provisional fills only gaps.
   524
   525	    ``CompositeSchemaProvider.get_schema`` is first-match-wins and
   526	    ``schemas()`` merges providers in reverse order, so the FIRST provider
   527	    dominates both views. Provisional registry/workflow-JSON schemas are weaker
   528	    evidence than real/runtime object-info schemas: they must never shadow a
   529	    real schema (semantic names/choices), only answer classes the
   530	    authoritative provider cannot. Every agent hydration site composes through
   531	    this helper so the ordering invariant lives in exactly one place.
   532	    """
   533	    return CompositeSchemaProvider(authoritative, provisional)
   534
   535
   536	class ProvisionalRegistrySchemaProvider:
   537	    """Evidence-backed schemas for missing custom nodes discovered by registry research.
   538
   539	    These schemas are not runtime proof that a node is installed. They only let
   540	    the editor represent a missing custom node class in a candidate graph when a
   541	    registry/manager lookup supplied either a concrete object_info-like schema
   542	    or trusted class-map evidence for that exact class. Weak class-name
   543	    extraction from GitHub/web search remains install guidance, not an
   544	    authoring schema.
   545	    """
   546
   547	    def __init__(self, candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> None:
   548	        self._schemas = _provisional_schemas_from_candidates(candidates)
   549
   550	    def get(self, class_type: str) -> NodeSchema | None:
  1020	            cached,
  1021	            expected=self._cache_validation_expected(),
  1022	            policy="strict",
  1023	            cache_path=self.cache_path,
  1024	        )
  1025	        if result.ok:
  1026	            return cached if isinstance(cached, dict) else None
  1027	        if cached is not None:
  1028	            _logger.warning(
  1029	                "rejected runtime object_info cache: path=%s reason=%s expected=%s actual=%s",
  1030	                self.cache_path,
  1031	                result.reason,
  1032	                result.expected,
  1033	                result.actual,
  1034	            )
  1035	        return None
  1036
  1037	    def _cache_validation_expected(self) -> dict[str, Any]:
  1038	        return {"runtime_fingerprint": runtime_fingerprint(self.server_url)}
  1039
  1040	    def _set_object_info(self, data: dict[str, Any]) -> None:
  1041	        if self._object_info != data:
  1042	            self._schemas = None
  1043	        self._object_info = data
  1044
  1045
  1046	def get_schema_provider(
  1047	    prefer: Literal["runtime", "local", "authoring", "auto"] = "auto",
  1048	    *,
  1049	    server_url: str | None = None,
  1050	) -> RuntimeSchemaProvider | LocalSchemaProvider | AuthoringSchemaProvider | CompositeSchemaProvider:
  1051	    if prefer == "runtime":
  1052	        return RuntimeSchemaProvider(server_url=server_url)
  1053	    if prefer == "local":
  1054	        return LocalSchemaProvider()
  1055	    if prefer == "authoring":
  1056	        return get_authoring_schema_provider()
  1057	    if prefer != "auto":
  1058	        raise ValueError(f"Unknown schema provider preference: {prefer}")
  1059	    if server_url:
  1060	        return RuntimeSchemaProvider(server_url=server_url)
  1061	    if Path("node_index.json").exists():
  1062	        return LocalSchemaProvider()
  1063	    if has_comfyui_runtime():
  1064	        return RuntimeSchemaProvider(server_url=server_url)
  1065	    return LocalSchemaProvider()
  1066
  1067
  1068	def get_authoring_schema_provider(
  1069	    *,
  1070	    object_info_cache_path: str | Path | None = None,
  1071	    object_info_index_root: str | Path | None = None,
  1072	    node_index_path: str | Path = "node_index.json",
  1073	    on_demand_schemas: bool | None = None,
  1074	) -> AuthoringSchemaProvider:
  1075	    return AuthoringSchemaProvider(

 succeeded in 254ms:
   385
   386	    try:
   387	        if not (_RUNTIME_OBJECT_INFO_PATH and Path(_RUNTIME_OBJECT_INFO_PATH[0]).is_file()):
   388	            data = _build_object_info_in_process()
   389	            if data:
   390	                import tempfile
   391
   392	                fd, path = tempfile.mkstemp(prefix="vibecomfy_object_info_", suffix=".json")
   393	                with os.fdopen(fd, "w", encoding="utf-8") as fh:
   394	                    json.dump(data, fh)
   395	                _RUNTIME_OBJECT_INFO_PATH[:] = [path]
   396	        if _RUNTIME_OBJECT_INFO_PATH:
   397	            from vibecomfy.schema.provider import ObjectInfoSchemaProvider
   398
   399	            return ObjectInfoSchemaProvider(_RUNTIME_OBJECT_INFO_PATH[0])
   400	    except Exception:
   401	        pass
   402	    # Headless fallback (no comfy imported in-process): resolve every INSTALLED
   403	    # node by querying a separately-running ComfyUI's live /object_info, then the
   404	    # shipped corpus, then the offline authoring chain. RuntimeSchemaProvider with
   405	    # an explicit server_url only does a GET (no spawn); a cheap socket probe guards
   406	    # an absent server so the edit turn never hangs. The in-process path above
   407	    # already covers the live-product case, where an HTTP self-request would deadlock.
   408	    import socket
   409	    from urllib.parse import urlparse
   410	    from vibecomfy.schema.provider import (
   411	        CompositeSchemaProvider,
   412	        RuntimeSchemaProvider,
   413	    )
   414
   415	    server_url = os.environ.get("VIBECOMFY_COMFYUI_URL")
   416	    reachable = False
   417	    if server_url:
   418	        try:
   419	            parsed = urlparse(server_url)
   420	            with socket.create_connection(
   421	                (parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=0.5
   422	            ):
   423	                reachable = True
   424	        except OSError:
   425	            reachable = False
   426	    providers: list[Any] = []
   427	    if reachable:
   428	        providers.append(RuntimeSchemaProvider(server_url=server_url))
   429	    # AuthoringSchemaProvider already consults the shipped corpus (ObjectInfoIndex),
   430	    # source parser, and local index, plus the on-demand resolver (default ON; the
   431	    # request's on_demand_schemas flag or VIBECOMFY_ON_DEMAND_SCHEMAS="0" can opt out)
   432	    # — so it stands in for the entire offline + on-demand tail.
   433	    providers.append(get_authoring_schema_provider(on_demand_schemas=on_demand_schemas))
   434	    return CompositeSchemaProvider(*providers)
   435
   436
   437	__all__ = (
   438	    "_RUNTIME_OBJECT_INFO_PATH",
   439	    "_batch_repl_candidate_needs_queue_validate",
   440	    "_build_object_info_in_process",
   441	    "_classify_stage_failure",
   442	    "_default_runtime_schema_provider",
   443	    "_is_provider_exception",
   444	    "_run_batch_repl_product_path",
   445	    "_run_batch_repl_queue_validate_if_needed",
   446	    "_run_delta_dev_path",
   447	    "_run_full_dev_path",
   448	    "_run_stage",
   449	    "_stage_batch_repl_queue_validate",
   450	)

 succeeded in 242ms:
# MEGADO BATCH B04 — Real-schema authority (Flash executor)

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only.

## Context
G0-R1 already swapped `_frag_research.py:821` to real-first. Exploration found 7 total construction sites; 4 are provisional-first and must be fixed (the oracle-verified list):

1. `vibecomfy/comfy_nodes/agent/_frag_research.py:874` — `(provisional, state)` ✗
2. `vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793` — `(provisional, session.schema_provider)` ✗ **poisons session AND state across turns**
3. `vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:910` — `(provisional, state)` ✗
4. `vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1115` — ✗ (remaining site)

Real-first invariant: `CompositeSchemaProvider.get_schema` is first-match-wins and `schemas()` merges `reversed(providers)` — the FIRST provider dominates both views, so real-first is required at every site.

## Tasks (from .oracle/tasklist.md B04)

1. Introduce ONE small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
2. Migrate all four provisional-first sites to real-first.
3. Assert precedence across ALL SEVEN construction sites for both `get_schema()` and merged `schemas()` (test).
4. Add a cross-turn regression for `_frag_response_contract.py:793` (currently poisons session + state — verify it no longer does).
5. Retain mechanism-level enum regressions for add and set (existing tests). Do NOT add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.

## Key files
- vibecomfy/comfy_nodes/agent/_frag_research.py, _frag_response_contract.py, _frag_batch_loop.py, edit_batch_repl.py, _frag_entrypoint.py (baseline), routes.py
- vibecomfy/comfy_nodes/agent/projection_registry_v1.py (get_schema/schemas semantics)
- tests: focused agent tests + test_executor_contracts.py

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py -k 'schema or precedence or provisional or real_schema or widget'
```
Plus run the full targeted files: `.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py` (expected exit 0; the rerunfailures plugin binds a socket and cannot run here).

## Acceptance
- All seven sites real-first.
- Session schema authority real-first across turns.
- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
- Invalid enum values rejected before mutation for add and set.
- Missing local asset filenames remain warning-only.

## Report
Return: helper name/location, per-site changes (file:line), the seven-site precedence test, cross-turn regression proof, enum regression results, pytest output. Do NOT commit.

exec
/bin/zsh -lc "rg -n 'ProvisionalRegistrySchemaProvider|CompositeSchemaProvider\\(' vibecomfy --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "rg -n '"'^def test_.*(schema|precedence|provisional|real_schema|widget|enum|choice|asset|cross_turn)'"' tests/test_comfy_nodes_agent_edit.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_porting_edit_apply.py tests/test_porting_edit_apply_values.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "nl -ba tests/test_comfy_nodes_agent_edit.py | sed -n '19970,20520p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "git grep -n -E 'ProvisionalRegistrySchemaProvider|CompositeSchemaProvider\\(' f2661b01 -- 'vibecomfy/**/*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
 19970	                    "widget_2": ["MASK"],
 19971	                    "widget_3": ["INT"],
 19972	                    "widget_4": ["INT"],
 19973	                    "widget_5": ["BOOLEAN"],
 19974	                }
 19975	            },
 19976	            "output": [["IMAGE", "IMAGE"]],
 19977	        },
 19978	        "ADE_MissingNode": {
 19979	            "input": {"required": {"widget_0": ["MODEL"]}},
 19980	            "output": [["MODEL", "MODEL"]],
 19981	        },
 19982	    }
 19983	    source = {
 19984	        "source": "external_workflow",
 19985	        "pack": "workflow",
 19986	        "url": "https://example.test/485ff2fa6dcc1917.json",
 19987	        "workflow_schema": workflow_schema,
 19988	    }
 19989
 19990	    state = _make_state(
 19991	        schema_provider=real_provider,
 19992	        executor_research_sources=(source,),
 19993	    )
 19994	    candidates = _hydrate_research_precedent_node_schemas(state)
 19995
 19996	    # Shadowing class: real named schema must win, never widget_N names.
 19997	    resolved = state.schema_provider.get_schema("CutAndDragOnPath")
 19998	    assert resolved is not None
 19999	    assert resolved.source_provider == "object_info"
 20000	    assert "inpaint" in resolved.inputs
 20001	    assert "frame_width" in resolved.inputs
 20002	    assert "frame_height" in resolved.inputs
 20003	    assert "image" in resolved.inputs
 20004	    assert not any(name.startswith("widget_") for name in resolved.inputs), (
 20005	        f"real schema shadowed by provisional widget_N inputs: {sorted(resolved.inputs)}"
 20006	    )
 20007
 20008	    # Missing class: provisional still fills the gap.
 20009	    missing_resolved = state.schema_provider.get_schema("ADE_MissingNode")
 20010	    assert missing_resolved is not None
 20011	    assert missing_resolved.source_provider == "workflow_json_provisional"
 20012
 20013	    # Hydration still surfaces the workflow candidates as reviewable evidence.
 20014	    assert any("CutAndDragOnPath" in cand.get("expected_classes", ()) for cand in candidates)
 20015
 20016
 20017	# ── B04: real-schema authority — real-first at every construction site ───────
 20018	# CompositeSchemaProvider.get_schema is first-match-wins and schemas() merges
 20019	# reversed(providers), so the FIRST provider dominates BOTH views. Every site
 20020	# that composes real/runtime schemas with provisional registry/workflow-JSON
 20021	# schemas must keep real first; provisional may only fill classes the real
 20022	# provider cannot answer.
 20023
 20024	_SHADOW = "ShadowNode"
 20025	# Underscore-bearing class so the workflow/registry hydration filters treat it
 20026	# as a plausible custom node (custom_only requires "_" in the class name).
 20027	_GAP = "GapNode_KJ"
 20028
 20029
 20030	def _b04_real_shadow_schema() -> NodeSchema:
 20031	    return NodeSchema(
 20032	        class_type=_SHADOW,
 20033	        pack="ComfyUI-KJNodes",
 20034	        inputs={
 20035	            "image": InputSpec("IMAGE", required=True),
 20036	            "frame_width": InputSpec("INT", required=True),
 20037	            "mode": InputSpec("STRING", choices=["real_a", "real_b"], required=True),
 20038	        },
 20039	        outputs=[OutputSpec("IMAGE", "IMAGE")],
 20040	        source_provider="object_info",
 20041	        confidence=1.0,
 20042	    )
 20043
 20044
 20045	def _b04_gap_schema() -> NodeSchema:
 20046	    return NodeSchema(
 20047	        class_type=_GAP,
 20048	        pack=None,
 20049	        inputs={"model": InputSpec("MODEL", required=True)},
 20050	        outputs=[OutputSpec("MODEL", "MODEL")],
 20051	        source_provider="object_info",
 20052	        confidence=1.0,
 20053	    )
 20054
 20055
 20056	def _b04_weaker_shadow_schema() -> NodeSchema:
 20057	    """Same class as the real schema but with widget_N names/empty choices."""
 20058	    return NodeSchema(
 20059	        class_type=_SHADOW,
 20060	        pack=None,
 20061	        inputs={"widget_0": InputSpec("STRING", choices=[])},
 20062	        outputs=[],
 20063	        source_provider="object_info",
 20064	        confidence=0.5,
 20065	    )
 20066
 20067
 20068	def _b04_provisional_node(class_type: str, index: int) -> dict[str, Any]:
 20069	    return {
 20070	        "input": {"required": {f"widget_{index}": ["STRING", {"choices": []}]}},
 20071	        "output": [["IMAGE", "IMAGE"]],
 20072	    }
 20073
 20074
 20075	def _b04_provisional_candidate(
 20076	    *class_types: str,
 20077	    validation_mode: str = "registry",
 20078	) -> dict[str, Any]:
 20079	    """Resolver-candidate dict shape consumed by ProvisionalRegistrySchemaProvider.
 20080
 20081	    Carries only positional widget_N names and empty choices — exactly the weak
 20082	    evidence that must never shadow a real semantic schema.
 20083	    """
 20084	    nodes = {
 20085	        class_type: _b04_provisional_node(class_type, index)
 20086	        for index, class_type in enumerate(class_types)
 20087	    }
 20088	    candidate: dict[str, Any] = {
 20089	        "stable_install_hash": f"b04:{','.join(class_types)}",
 20090	        "provisional_schema": {"schema": {"nodes": nodes}, "version": "1.0.0"},
 20091	        "expected_classes": list(class_types),
 20092	    }
 20093	    if validation_mode == "workflow":
 20094	        candidate["validation_mode"] = "workflow_json_provisional"
 20095	    return candidate
 20096
 20097
 20098	def _assert_b04_real_first(provider: Any, *, gap_source: str) -> None:
 20099	    """Both get_schema() and merged schemas() must prefer the real schema."""
 20100	    resolved = provider.get_schema(_SHADOW)
 20101	    assert resolved is not None
 20102	    assert resolved.source_provider == "object_info"
 20103	    assert "frame_width" in resolved.inputs
 20104	    assert "mode" in resolved.inputs
 20105	    assert list(resolved.inputs["mode"].choices or []) == ["real_a", "real_b"]
 20106	    assert not any(name.startswith("widget_") for name in resolved.inputs), (
 20107	        f"real schema shadowed by provisional widget_N inputs: {sorted(resolved.inputs)}"
 20108	    )
 20109	    merged = provider.schemas()
 20110	    assert merged[_SHADOW] is resolved, "merged schemas() view lost real-first precedence"
 20111	    gap = provider.get_schema(_GAP)
 20112	    assert gap is not None
 20113	    assert gap.source_provider == gap_source, f"expected provisional gap fill, got {gap.source_provider}"
 20114	    assert merged[_GAP] is gap, "merged schemas() view lost the provisional gap fill"
 20115
 20116
 20117	def test_schema_precedence_helper_with_provisional_gap_filler_both_views() -> None:
 20118	    """The one shared helper composes real first for get_schema() and schemas()."""
 20119	    from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
 20120
 20121	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20122	    provisional = ProvisionalRegistrySchemaProvider(
 20123	        [_b04_provisional_candidate(_SHADOW, _GAP)]
 20124	    )
 20125	    composite = with_provisional_gap_filler(real, provisional)
 20126	    assert isinstance(composite.providers[0], _Provider)
 20127	    assert isinstance(composite.providers[1], ProvisionalRegistrySchemaProvider)
 20128	    _assert_b04_real_first(composite, gap_source="comfy_registry_provisional")
 20129
 20130
 20131	def test_schema_precedence_research_workflow_hydration_real_first() -> None:
 20132	    """Site _frag_research.py:821 — workflow-JSON provisional cannot shadow real."""
 20133	    from vibecomfy.comfy_nodes.agent.edit import _hydrate_research_precedent_node_schemas
 20134
 20135	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20136	    workflow_schema = {
 20137	        _SHADOW: _b04_provisional_node(_SHADOW, 0),
 20138	        _GAP: _b04_provisional_node(_GAP, 1),
 20139	    }
 20140	    source = {
 20141	        "source": "external_workflow",
 20142	        "pack": "workflow",
 20143	        "url": "https://example.test/b04-workflow.json",
 20144	        "workflow_schema": workflow_schema,
 20145	    }
 20146	    state = _make_state(schema_provider=real, executor_research_sources=(source,))
 20147	    _hydrate_research_precedent_node_schemas(state)
 20148	    _assert_b04_real_first(state.schema_provider, gap_source="workflow_json_provisional")
 20149
 20150
 20151	def test_schema_precedence_research_registry_hydration_real_first(
 20152	    monkeypatch: pytest.MonkeyPatch,
 20153	) -> None:
 20154	    """Site _frag_research.py:874 — registry provisional cannot shadow real."""
 20155	    from vibecomfy.comfy_nodes.agent.edit import _hydrate_research_precedent_node_schemas
 20156	    from vibecomfy.registry import pack_resolver
 20157
 20158	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20159	    candidate = _b04_provisional_candidate(_GAP, _SHADOW)
 20160	    monkeypatch.setattr(
 20161	        pack_resolver,
 20162	        "resolve_missing_nodes",
 20163	        lambda query, **kwargs: types.SimpleNamespace(candidates=[candidate]),
 20164	    )
 20165	    source = {
 20166	        "source": "external_workflow",
 20167	        "pack": "workflow",
 20168	        "url": "https://example.test/b04-registry.json",
 20169	        # class evidence only: drives the registry fallback, not :821's workflow path
 20170	        "workflow_schema_classes": [_GAP],
 20171	    }
 20172	    state = _make_state(schema_provider=real, executor_research_sources=(source,))
 20173	    _hydrate_research_precedent_node_schemas(state)
 20174	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20175
 20176
 20177	def test_schema_precedence_current_graph_unknown_hydration_real_first(
 20178	    monkeypatch: pytest.MonkeyPatch,
 20179	) -> None:
 20180	    """Site _frag_research.py:922 — graph-driven provisional cannot shadow real."""
 20181	    from vibecomfy.comfy_nodes.agent.edit import _hydrate_current_graph_unknown_node_schemas
 20182	    from vibecomfy.registry import pack_resolver
 20183
 20184	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20185	    candidate = _b04_provisional_candidate(_GAP, _SHADOW)
 20186	    monkeypatch.setattr(
 20187	        pack_resolver,
 20188	        "resolve_missing_nodes",
 20189	        lambda query, **kwargs: types.SimpleNamespace(candidates=[candidate]),
 20190	    )
 20191	    state = _make_state(
 20192	        schema_provider=real,
 20193	        graph={"nodes": [{"id": 1, "class_type": _GAP}]},
 20194	    )
 20195	    _hydrate_current_graph_unknown_node_schemas(state)
 20196	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20197
 20198
 20199	def test_schema_precedence_batch_loop_registry_hydration_real_first() -> None:
 20200	    """Site _frag_batch_loop.py:910 — planned-dependency provisional cannot shadow real."""
 20201	    from vibecomfy.comfy_nodes.agent.edit import _hydrate_actionable_registry_dependencies
 20202
 20203	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20204	    candidate = _b04_provisional_candidate(_GAP, _SHADOW)
 20205	    state = _make_state(
 20206	        schema_provider=real,
 20207	        runtime_dependencies=(
 20208	            {
 20209	                "availability": "registry_resolvable",
 20210	                "resolver_candidates": [candidate],
 20211	            },
 20212	        ),
 20213	    )
 20214	    _hydrate_actionable_registry_dependencies(state)
 20215	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20216
 20217
 20218	def test_schema_precedence_batch_repl_registry_hydration_real_first() -> None:
 20219	    """Site edit_batch_repl.py:1115 — REPL planned-dependency provisional cannot shadow real."""
 20220	    import logging
 20221
 20222	    from vibecomfy.comfy_nodes.agent import edit_batch_repl
 20223	    from vibecomfy.comfy_nodes.agent.edit import _candidate_stable_key
 20224
 20225	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20226	    candidate = _b04_provisional_candidate(_GAP, _SHADOW)
 20227	    state = _make_state(
 20228	        schema_provider=real,
 20229	        runtime_dependencies=(
 20230	            {
 20231	                "availability": "registry_resolvable",
 20232	                "resolver_candidates": [candidate],
 20233	            },
 20234	        ),
 20235	    )
 20236	    deps = types.SimpleNamespace(
 20237	        LOGGER=logging.getLogger("b04_repl_test"),
 20238	        _candidate_stable_key=_candidate_stable_key,
 20239	    )
 20240	    edit_batch_repl._hydrate_actionable_registry_dependencies(deps, state)
 20241	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20242
 20243
 20244	def test_schema_precedence_baseline_runtime_provider_real_first(
 20245	    monkeypatch: pytest.MonkeyPatch,
 20246	) -> None:
 20247	    """Site _frag_orchestration.py:434 — baseline [Runtime, Authoring] stays real-first."""
 20248	    from vibecomfy.comfy_nodes.agent.edit import _default_runtime_schema_provider
 20249	    from vibecomfy.schema import CompositeSchemaProvider
 20250
 20251	    runtime_schema = _b04_real_shadow_schema()
 20252
 20253	    class _FakeRuntimeProvider:
 20254	        def __init__(self, *, server_url: str | None = None) -> None:
 20255	            self.server_url = server_url
 20256	            self._schemas = {_SHADOW: runtime_schema}
 20257
 20258	        def get_schema(self, class_type: str) -> NodeSchema | None:
 20259	            return self._schemas.get(class_type)
 20260
 20261	        def schemas(self) -> dict[str, NodeSchema]:
 20262	            return dict(self._schemas)
 20263
 20264	    class _FakeConn:
 20265	        def __enter__(self) -> "_FakeConn":
 20266	            return self
 20267
 20268	        def __exit__(self, *args: Any) -> None:
 20269	            return None
 20270
 20271	    authoring = _Provider(
 20272	        {
 20273	            _SHADOW: _b04_weaker_shadow_schema(),
 20274	            _GAP: _b04_gap_schema(),
 20275	        }
 20276	    )
 20277	    monkeypatch.setattr(
 20278	        "vibecomfy.comfy_nodes.agent.edit._build_object_info_in_process",
 20279	        lambda: None,
 20280	    )
 20281	    monkeypatch.setattr(
 20282	        "vibecomfy.comfy_nodes.agent._frag_orchestration._RUNTIME_OBJECT_INFO_PATH",
 20283	        [],
 20284	    )
 20285	    monkeypatch.setenv("VIBECOMFY_COMFYUI_URL", "http://127.0.0.1:9")
 20286	    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: _FakeConn())
 20287	    monkeypatch.setattr(
 20288	        "vibecomfy.schema.provider.RuntimeSchemaProvider",
 20289	        _FakeRuntimeProvider,
 20290	    )
 20291	    monkeypatch.setattr(
 20292	        "vibecomfy.schema.get_authoring_schema_provider",
 20293	        lambda **kwargs: authoring,
 20294	    )
 20295
 20296	    provider = _default_runtime_schema_provider(on_demand_schemas=False)
 20297	    assert isinstance(provider, CompositeSchemaProvider)
 20298	    assert isinstance(provider.providers[0], _FakeRuntimeProvider), (
 20299	        "baseline runtime provider must stay first"
 20300	    )
 20301	    assert provider.providers[0].server_url == "http://127.0.0.1:9"
 20302	    resolved = provider.get_schema(_SHADOW)
 20303	    assert resolved is runtime_schema
 20304	    assert provider.schemas()[_SHADOW] is runtime_schema
 20305	    assert provider.get_schema(_GAP) is authoring._schemas[_GAP]
 20306	    assert provider.schemas()[_GAP] is authoring._schemas[_GAP]
 20307
 20308
 20309	def test_schema_precedence_across_all_seven_construction_sites(
 20310	    monkeypatch: pytest.MonkeyPatch,
 20311	) -> None:
 20312	    """Every construction site keeps real-first for get_schema() AND schemas()."""
 20313	    from vibecomfy.comfy_nodes.agent import edit_batch_repl
 20314	    from vibecomfy.comfy_nodes.agent.edit import (
 20315	        _candidate_stable_key as _stable_key,
 20316	        _default_runtime_schema_provider,
 20317	        _enrich_schema_provider_from_resolver_candidates,
 20318	        _hydrate_actionable_registry_dependencies,
 20319	        _hydrate_current_graph_unknown_node_schemas,
 20320	        _hydrate_research_precedent_node_schemas,
 20321	    )
 20322	    from vibecomfy.registry import pack_resolver
 20323	    from vibecomfy.schema import (
 20324	        CompositeSchemaProvider,
 20325	        ProvisionalRegistrySchemaProvider,
 20326	        with_provisional_gap_filler,
 20327	    )
 20328
 20329	    # Site 1 — helper (vibecomfy/schema/provider.py)
 20330	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20331	    provisional = ProvisionalRegistrySchemaProvider(
 20332	        [_b04_provisional_candidate(_SHADOW, _GAP)]
 20333	    )
 20334	    _assert_b04_real_first(
 20335	        with_provisional_gap_filler(real, provisional),
 20336	        gap_source="comfy_registry_provisional",
 20337	    )
 20338
 20339	    # Site 2 — _frag_research.py:821 (workflow-JSON path)
 20340	    workflow_source = {
 20341	        "source": "external_workflow",
 20342	        "pack": "workflow",
 20343	        "url": "https://example.test/b04-seven.json",
 20344	        "workflow_schema": {
 20345	            _SHADOW: _b04_provisional_node(_SHADOW, 0),
 20346	            _GAP: _b04_provisional_node(_GAP, 1),
 20347	        },
 20348	    }
 20349	    state = _make_state(
 20350	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()}),
 20351	        executor_research_sources=(workflow_source,),
 20352	    )
 20353	    _hydrate_research_precedent_node_schemas(state)
 20354	    _assert_b04_real_first(state.schema_provider, gap_source="workflow_json_provisional")
 20355
 20356	    # Site 3 — _frag_research.py:874 (registry path, class-evidence source)
 20357	    candidate = _b04_provisional_candidate(_GAP, _SHADOW)
 20358	    monkeypatch.setattr(
 20359	        pack_resolver,
 20360	        "resolve_missing_nodes",
 20361	        lambda query, **kwargs: types.SimpleNamespace(candidates=[candidate]),
 20362	    )
 20363	    state = _make_state(
 20364	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()}),
 20365	        executor_research_sources=(
 20366	            {
 20367	                "source": "external_workflow",
 20368	                "pack": "workflow",
 20369	                "url": "https://example.test/b04-seven-registry.json",
 20370	                "workflow_schema_classes": [_GAP],
 20371	            },
 20372	        ),
 20373	    )
 20374	    _hydrate_research_precedent_node_schemas(state)
 20375	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20376
 20377	    # Site 4 — _frag_research.py:922 (current-graph unknown nodes)
 20378	    state = _make_state(
 20379	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()}),
 20380	        graph={"nodes": [{"id": 1, "class_type": _GAP}]},
 20381	    )
 20382	    _hydrate_current_graph_unknown_node_schemas(state)
 20383	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20384
 20385	    # Site 5 — _frag_batch_loop.py:910 (planned registry dependencies)
 20386	    state = _make_state(
 20387	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()}),
 20388	        runtime_dependencies=(
 20389	            {"availability": "registry_resolvable", "resolver_candidates": [candidate]},
 20390	        ),
 20391	    )
 20392	    _hydrate_actionable_registry_dependencies(state)
 20393	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20394
 20395	    # Site 6 — edit_batch_repl.py:1115 (REPL planned registry dependencies)
 20396	    import logging
 20397
 20398	    state = _make_state(
 20399	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()}),
 20400	        runtime_dependencies=(
 20401	            {"availability": "registry_resolvable", "resolver_candidates": [candidate]},
 20402	        ),
 20403	    )
 20404	    deps = types.SimpleNamespace(
 20405	        LOGGER=logging.getLogger("b04_seven_test"),
 20406	        _candidate_stable_key=_stable_key,
 20407	    )
 20408	    edit_batch_repl._hydrate_actionable_registry_dependencies(deps, state)
 20409	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20410
 20411	    # Site 7 — _frag_orchestration.py:434 (baseline runtime + authoring)
 20412	    runtime_schema = _b04_real_shadow_schema()
 20413
 20414	    class _FakeRuntimeProvider:
 20415	        def __init__(self, *, server_url: str | None = None) -> None:
 20416	            self.server_url = server_url
 20417	            self._schemas = {_SHADOW: runtime_schema}
 20418
 20419	        def get_schema(self, class_type: str) -> NodeSchema | None:
 20420	            return self._schemas.get(class_type)
 20421
 20422	        def schemas(self) -> dict[str, NodeSchema]:
 20423	            return dict(self._schemas)
 20424
 20425	    class _FakeConn:
 20426	        def __enter__(self) -> "_FakeConn":
 20427	            return self
 20428
 20429	        def __exit__(self, *args: Any) -> None:
 20430	            return None
 20431
 20432	    authoring = _Provider(
 20433	        {
 20434	            _SHADOW: _b04_weaker_shadow_schema(),
 20435	            _GAP: _b04_gap_schema(),
 20436	        }
 20437	    )
 20438	    monkeypatch.setattr(
 20439	        "vibecomfy.comfy_nodes.agent.edit._build_object_info_in_process",
 20440	        lambda: None,
 20441	    )
 20442	    monkeypatch.setattr(
 20443	        "vibecomfy.comfy_nodes.agent._frag_orchestration._RUNTIME_OBJECT_INFO_PATH",
 20444	        [],
 20445	    )
 20446	    monkeypatch.setenv("VIBECOMFY_COMFYUI_URL", "http://127.0.0.1:9")
 20447	    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: _FakeConn())
 20448	    monkeypatch.setattr(
 20449	        "vibecomfy.schema.provider.RuntimeSchemaProvider",
 20450	        _FakeRuntimeProvider,
 20451	    )
 20452	    monkeypatch.setattr(
 20453	        "vibecomfy.schema.get_authoring_schema_provider",
 20454	        lambda **kwargs: authoring,
 20455	    )
 20456	    baseline = _default_runtime_schema_provider(on_demand_schemas=False)
 20457	    assert isinstance(baseline, CompositeSchemaProvider)
 20458	    assert isinstance(baseline.providers[0], _FakeRuntimeProvider)
 20459	    assert baseline.get_schema(_SHADOW) is runtime_schema
 20460	    assert baseline.schemas()[_SHADOW] is runtime_schema
 20461	    assert baseline.get_schema(_GAP) is authoring._schemas[_GAP]
 20462	    assert baseline.schemas()[_GAP] is authoring._schemas[_GAP]
 20463
 20464	    # Cross-turn authority: :793 enrichment must not poison session or state.
 20465	    session = types.SimpleNamespace(
 20466	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()})
 20467	    )
 20468	    state = _make_state(schema_provider=session.schema_provider)
 20469	    _enrich_schema_provider_from_resolver_candidates(
 20470	        state,
 20471	        session,
 20472	        [_b04_provisional_candidate(_GAP, _SHADOW)],
 20473	    )
 20474	    _assert_b04_real_first(session.schema_provider, gap_source="comfy_registry_provisional")
 20475	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20476	    assert state.schema_provider is session.schema_provider
 20477
 20478
 20479	def test_schema_enrichment_cross_turn_keeps_real_first(
 20480	    monkeypatch: pytest.MonkeyPatch,
 20481	) -> None:
 20482	    """Session + state authority stays real-first across turns (regression for :793).
 20483
 20484	    Before B04, _enrich_schema_provider_from_resolver_candidates composed
 20485	    (provisional, session.schema_provider): the provisional provider became the
 20486	    FIRST provider on BOTH session and durable state, so every later turn —
 20487	    including a fresh EditSession built from state.schema_provider — resolved
 20488	    overlapping classes through weak widget_N schemas.
 20489	    """
 20490	    from vibecomfy.comfy_nodes.agent.edit import _enrich_schema_provider_from_resolver_candidates
 20491	    from vibecomfy.porting.edit.session import EditSession
 20492
 20493	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20494	    session = types.SimpleNamespace(schema_provider=real)
 20495	    state = _make_state(schema_provider=real)
 20496
 20497	    # Turn 1: enrichment with a provisional carrying the shadow class + a gap class.
 20498	    _enrich_schema_provider_from_resolver_candidates(
 20499	        state,
 20500	        session,
 20501	        [_b04_provisional_candidate(_GAP, _SHADOW)],
 20502	    )
 20503	    _assert_b04_real_first(session.schema_provider, gap_source="comfy_registry_provisional")
 20504	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20505
 20506	    # Turn 2: the durable state provider feeds a brand-new session (the batch-REPL
 20507	    # construction path) — authority must remain real-first, not drift provisional.
 20508	    turn2_session = EditSession(
 20509	        {"nodes": [], "links": []},
 20510	        schema_provider=state.schema_provider,
 20511	    )
 20512	    _assert_b04_real_first(turn2_session.schema_provider, gap_source="comfy_registry_provisional")
 20513
 20514	    # Turn 2 enrichment with NEW candidates (fresh stable hash) must not rotate
 20515	    # the earlier provisional ahead of the real provider either.
 20516	    second_candidate = _b04_provisional_candidate(_GAP)
 20517	    second_candidate["stable_install_hash"] = "b04:turn2:GapNode"
 20518	    _enrich_schema_provider_from_resolver_candidates(
 20519	        state,
 20520	        turn2_session,

 succeeded in 116ms:
tests/test_porting_edit_apply_values.py:37:def test_validate_asset_enum_accepts_missing_local_asset_with_warning(
tests/test_porting_edit_apply_values.py:57:def test_validate_constrained_enum_still_rejects_unknown_value(
tests/test_porting_edit_apply_values.py:70:def test_validate_asset_enum_does_not_accept_non_string_value() -> None:
tests/test_porting_edit_apply_values.py:79:def test_apply_values_add_node_keeps_missing_asset_filename_and_warning() -> None:
tests/test_comfy_nodes_agent_edit.py:112:def test_schema_less_preexisting_node_rewire_preserves_queue_safety() -> None:
tests/test_comfy_nodes_agent_edit.py:2947:def test_default_runtime_schema_provider_falls_back_to_authoring_object_info(
tests/test_comfy_nodes_agent_edit.py:3168:def test_batch_repl_search_exact_miss_explains_local_schema_lookup() -> None:
tests/test_comfy_nodes_agent_edit.py:3399:def test_batch_repl_web_workflow_json_prompts_exact_schema_followup(
tests/test_comfy_nodes_agent_edit.py:3439:def test_batch_repl_research_memory_keeps_workflow_evidence_across_turns() -> None:
tests/test_comfy_nodes_agent_edit.py:4019:def test_missing_custom_node_clarify_does_not_force_registry_after_schema_miss() -> None:
tests/test_comfy_nodes_agent_edit.py:4088:def test_workflow_schema_clarify_does_not_force_uninstalled_provisional_nodes() -> None:
tests/test_comfy_nodes_agent_edit.py:4144:def test_workflow_schema_clarify_rejects_asking_for_present_workflow_signatures() -> None:
tests/test_comfy_nodes_agent_edit.py:4293:def test_selected_precedent_workflow_schema_class_is_authorable_provisionally(
tests/test_comfy_nodes_agent_edit.py:4588:def test_registry_evidence_only_candidate_is_resolvable_without_live_schema(
tests/test_comfy_nodes_agent_edit.py:4915:def test_handle_agent_edit_batch_repl_adds_workflow_json_provisional_node(
tests/test_comfy_nodes_agent_edit.py:5124:def test_handle_agent_edit_batch_repl_adds_registry_provisional_missing_node(
tests/test_comfy_nodes_agent_edit.py:5266:def test_adapt_prefetch_compiles_workflow_classes_into_schema_backed_capabilities(
tests/test_comfy_nodes_agent_edit.py:5536:def test_adapt_prompt_marks_unhydrated_workflow_schema_classes_observed_only(
tests/test_comfy_nodes_agent_edit.py:5858:def test_batch_repl_search_exact_miss_explains_local_schema_lookup() -> None:
tests/test_comfy_nodes_agent_edit.py:5988:def test_batch_budget_failure_kind_prefers_schema_gap_then_unrepresentable_then_model_mistake() -> None:
tests/test_comfy_nodes_agent_edit.py:6864:def test_handle_agent_edit_batch_repl_unresolved_schema_capability_does_not_emit_noop_message(
tests/test_comfy_nodes_agent_edit.py:8318:def test_handle_agent_edit_batch_repl_edit_clarify_with_unresolved_schema_capability_downgrades(
tests/test_comfy_nodes_agent_edit.py:12928:def test_repair_field_changes_uses_named_widget_old_value_for_ksampler_steps() -> None:
tests/test_comfy_nodes_agent_edit.py:13124:def test_humanized_edit_message_describes_added_nodes_not_internal_widget_uid() -> None:
tests/test_comfy_nodes_agent_edit.py:14079:def test_handle_agent_edit_revise_ignores_preexisting_assets_and_unknown_nodes_for_local_edit(
tests/test_comfy_nodes_agent_edit.py:16759:def test_format_batch_report_includes_enum_choices_in_detail() -> None:
tests/test_comfy_nodes_agent_edit.py:18166:def test_route_blocks_apply_asset_lookup() -> None:
tests/test_comfy_nodes_agent_edit.py:19930:def test_research_precedent_provisional_workflow_schema_does_not_shadow_real_schema() -> None:
tests/test_comfy_nodes_agent_edit.py:20117:def test_schema_precedence_helper_with_provisional_gap_filler_both_views() -> None:
tests/test_comfy_nodes_agent_edit.py:20131:def test_schema_precedence_research_workflow_hydration_real_first() -> None:
tests/test_comfy_nodes_agent_edit.py:20151:def test_schema_precedence_research_registry_hydration_real_first(
tests/test_comfy_nodes_agent_edit.py:20177:def test_schema_precedence_current_graph_unknown_hydration_real_first(
tests/test_comfy_nodes_agent_edit.py:20199:def test_schema_precedence_batch_loop_registry_hydration_real_first() -> None:
tests/test_comfy_nodes_agent_edit.py:20218:def test_schema_precedence_batch_repl_registry_hydration_real_first() -> None:
tests/test_comfy_nodes_agent_edit.py:20244:def test_schema_precedence_baseline_runtime_provider_real_first(
tests/test_comfy_nodes_agent_edit.py:20309:def test_schema_precedence_across_all_seven_construction_sites(
tests/test_comfy_nodes_agent_edit.py:20479:def test_schema_enrichment_cross_turn_keeps_real_first(
tests/test_porting_edit_apply.py:299:def test_resolve_delta_rejects_invalid_enum_without_mutating_original() -> None:
tests/test_porting_edit_apply.py:415:def test_resolve_delta_accepts_ksampler_widget_fields_but_not_socket_literals() -> None:
tests/test_porting_edit_apply.py:464:def test_resolve_delta_accepts_loadimage_semantic_alias_with_widget_only_schema() -> None:
tests/test_porting_edit_apply.py:510:def test_resolve_delta_accepts_object_info_semantic_alias_for_existing_widget_field() -> None:
tests/test_porting_edit_apply.py:622:def test_resolve_delta_unknown_ksampler_set_node_field_exposes_compact_names_and_omits_widget_N() -> None:
tests/test_porting_edit_apply.py:730:def test_resolve_delta_unknown_ksampler_add_node_field_omits_covered_widget_N() -> None:
tests/test_porting_edit_apply.py:929:def test_apply_delta_sets_unlinked_widget_value_and_preserves_unrelated_nodes() -> None:
tests/test_porting_edit_apply.py:957:def test_apply_delta_sets_ksampler_control_after_generate_ui_widget() -> None:
tests/test_porting_edit_apply.py:996:def test_apply_delta_maps_legacy_unused_widget_alias_to_control_after_generate() -> None:
tests/test_porting_edit_apply.py:1397:def test_apply_delta_auto_unlinks_schema_less_linked_widget_and_records_diagnostics() -> None:
tests/test_porting_edit_apply.py:1468:def test_apply_delta_sets_schema_less_dict_widget_without_changing_other_nodes() -> None:
tests/test_porting_edit_apply.py:1534:def test_apply_delta_unlinks_widget_input_and_sets_dict_widget_value() -> None:
tests/test_porting_edit_apply.py:1602:def test_resolve_delta_rejects_unknown_dict_widget_field() -> None:
tests/test_porting_edit_apply.py:1836:def test_apply_delta_reorders_unlinked_widget_values_only() -> None:
tests/test_porting_edit_apply.py:1881:def test_resolve_delta_rejects_linked_widget_reorder() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:144:def test_workflow_class_types_can_include_known_schema_for_prompt_focus() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:2405:def test_validate_stage_flags_invalid_model_picker_values_when_schema_choices_exist() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:2762:def test_queue_recovery_report_enriches_emit_schema_less_entries_for_preexisting_safe_nodes() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:2855:def test_queue_stage_tolerates_preexisting_schema_less_nodes_after_recovery_enrichment() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:2948:def test_queue_recovery_allows_schema_less_transitive_reroute_with_schema_less_intermediate() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:3047:def test_queue_diagnostics_detect_intent_nodes_before_generic_schema_confidence_checks() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:3226:def test_runtime_backed_code_fixture_is_queueable_after_compile_schema_and_recovery() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:3261:def test_runtime_backed_code_fixture_blocks_pre_queue_when_contract_or_schema_is_not_proven(
tests/test_comfy_nodes_agent_backend_spine.py:3485:def test_queue_diagnostics_schema_less_only_blocks_queue_when_canvas_passes() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:3701:def test_queue_diagnostics_unresolved_model_widget_blocks_queue_when_canvas_passes() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:7129:def test_read_field_value_covers_widgets_widgets_values_inputs_outputs_and_top_level() -> None:
tests/test_comfy_nodes_agent_backend_spine.py:9500:def test_exec_structural_hash_ignores_duplicate_io_widget_after_roundtrip() -> None:

 succeeded in 151ms:
vibecomfy/comfy_nodes/agent/_frag_research.py:811:            from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_research.py:813:            provisional = ProvisionalRegistrySchemaProvider(workflow_candidates)
vibecomfy/comfy_nodes/agent/_frag_research.py:838:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_research.py:865:    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
vibecomfy/comfy_nodes/agent/_frag_research.py:886:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_research.py:913:    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:782:    from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_response_contract.py:784:    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
vibecomfy/schema/__init__.py:13:    ProvisionalRegistrySchemaProvider,
vibecomfy/schema/__init__.py:41:    "ProvisionalRegistrySchemaProvider",
vibecomfy/schema/provider.py:533:    return CompositeSchemaProvider(authoritative, provisional)
vibecomfy/schema/provider.py:536:class ProvisionalRegistrySchemaProvider:
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1104:        CompositeSchemaProvider, ProvisionalRegistrySchemaProvider = _import_from("vibecomfy.schema", "CompositeSchemaProvider"), _import_from("vibecomfy.schema", "ProvisionalRegistrySchemaProvider")
vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1107:        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:899:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:901:        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
vibecomfy/comfy_nodes/agent/_frag_orchestration.py:434:    return CompositeSchemaProvider(*providers)

 succeeded in 436ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
f2661b01:vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:899:        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
f2661b01:vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:901:        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:910:        state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_orchestration.py:434:    return CompositeSchemaProvider(*providers)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:811:            from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:813:            provisional = ProvisionalRegistrySchemaProvider(workflow_candidates)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:821:                state.schema_provider = CompositeSchemaProvider(state.schema_provider, provisional)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:838:        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:865:    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:874:    state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:886:        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:913:    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_research.py:922:    state.schema_provider = CompositeSchemaProvider(state.schema_provider, provisional)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_response_contract.py:782:    from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
f2661b01:vibecomfy/comfy_nodes/agent/_frag_response_contract.py:784:    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
f2661b01:vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793:    enriched = CompositeSchemaProvider(provisional, session.schema_provider)
f2661b01:vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1104:        CompositeSchemaProvider, ProvisionalRegistrySchemaProvider = _import_from("vibecomfy.schema", "CompositeSchemaProvider"), _import_from("vibecomfy.schema", "ProvisionalRegistrySchemaProvider")
f2661b01:vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1106:        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
f2661b01:vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1115:        state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
f2661b01:vibecomfy/schema/__init__.py:13:    ProvisionalRegistrySchemaProvider,
f2661b01:vibecomfy/schema/__init__.py:40:    "ProvisionalRegistrySchemaProvider",
f2661b01:vibecomfy/schema/provider.py:519:class ProvisionalRegistrySchemaProvider:

exec
/bin/zsh -lc "nl -ba tests/test_comfy_nodes_agent_edit.py | sed -n '20464,20560p'; nl -ba vibecomfy/comfy_nodes/agent/_frag_response_contract.py | sed -n '750,815p'; nl -ba vibecomfy/comfy_nodes/agent/edit_batch_repl.py | sed -n '1088,1125p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 89ms:
 20464	    # Cross-turn authority: :793 enrichment must not poison session or state.
 20465	    session = types.SimpleNamespace(
 20466	        schema_provider=_Provider({_SHADOW: _b04_real_shadow_schema()})
 20467	    )
 20468	    state = _make_state(schema_provider=session.schema_provider)
 20469	    _enrich_schema_provider_from_resolver_candidates(
 20470	        state,
 20471	        session,
 20472	        [_b04_provisional_candidate(_GAP, _SHADOW)],
 20473	    )
 20474	    _assert_b04_real_first(session.schema_provider, gap_source="comfy_registry_provisional")
 20475	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20476	    assert state.schema_provider is session.schema_provider
 20477
 20478
 20479	def test_schema_enrichment_cross_turn_keeps_real_first(
 20480	    monkeypatch: pytest.MonkeyPatch,
 20481	) -> None:
 20482	    """Session + state authority stays real-first across turns (regression for :793).
 20483
 20484	    Before B04, _enrich_schema_provider_from_resolver_candidates composed
 20485	    (provisional, session.schema_provider): the provisional provider became the
 20486	    FIRST provider on BOTH session and durable state, so every later turn —
 20487	    including a fresh EditSession built from state.schema_provider — resolved
 20488	    overlapping classes through weak widget_N schemas.
 20489	    """
 20490	    from vibecomfy.comfy_nodes.agent.edit import _enrich_schema_provider_from_resolver_candidates
 20491	    from vibecomfy.porting.edit.session import EditSession
 20492
 20493	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
 20494	    session = types.SimpleNamespace(schema_provider=real)
 20495	    state = _make_state(schema_provider=real)
 20496
 20497	    # Turn 1: enrichment with a provisional carrying the shadow class + a gap class.
 20498	    _enrich_schema_provider_from_resolver_candidates(
 20499	        state,
 20500	        session,
 20501	        [_b04_provisional_candidate(_GAP, _SHADOW)],
 20502	    )
 20503	    _assert_b04_real_first(session.schema_provider, gap_source="comfy_registry_provisional")
 20504	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20505
 20506	    # Turn 2: the durable state provider feeds a brand-new session (the batch-REPL
 20507	    # construction path) — authority must remain real-first, not drift provisional.
 20508	    turn2_session = EditSession(
 20509	        {"nodes": [], "links": []},
 20510	        schema_provider=state.schema_provider,
 20511	    )
 20512	    _assert_b04_real_first(turn2_session.schema_provider, gap_source="comfy_registry_provisional")
 20513
 20514	    # Turn 2 enrichment with NEW candidates (fresh stable hash) must not rotate
 20515	    # the earlier provisional ahead of the real provider either.
 20516	    second_candidate = _b04_provisional_candidate(_GAP)
 20517	    second_candidate["stable_install_hash"] = "b04:turn2:GapNode"
 20518	    _enrich_schema_provider_from_resolver_candidates(
 20519	        state,
 20520	        turn2_session,
 20521	        [second_candidate],
 20522	    )
 20523	    _assert_b04_real_first(turn2_session.schema_provider, gap_source="comfy_registry_provisional")
 20524	    _assert_b04_real_first(state.schema_provider, gap_source="comfy_registry_provisional")
 20525	    assert state.schema_provider is turn2_session.schema_provider
   750	        detail = getattr(statement, "detail", None)
   751	        if not isinstance(detail, Mapping):
   752	            continue
   753	        raw_candidates = detail.get("workflow_schema_candidates")
   754	        if not isinstance(raw_candidates, list):
   755	            continue
   756	        for raw_candidate in raw_candidates:
   757	            if isinstance(raw_candidate, Mapping):
   758	                candidates.append(dict(raw_candidate))
   759	    return candidates
   760
   761
   762	def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
   763	    return (
   764	        str(candidate.get("stable_install_hash") or "")
   765	        or json.dumps(dict(candidate), sort_keys=True, default=str)
   766	    )
   767
   768
   769	def _enrich_schema_provider_from_resolver_candidates(
   770	    state: AgentEditState,
   771	    session: Any,
   772	    candidates: list[dict[str, Any]],
   773	) -> None:
   774	    from vibecomfy.comfy_nodes.agent.edit import (_candidate_stable_key)  # T-039 late import: host namespace lookup; resolved at call time
   775	    new_candidates = [
   776	        candidate
   777	        for candidate in candidates
   778	        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
   779	    ]
   780	    if not new_candidates:
   781	        return
   782	    from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
   783
   784	    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
   785	    if not provisional.schemas():
   786	        return
   787	    state.provisional_registry_candidate_hashes = frozenset(
   788	        {
   789	            *state.provisional_registry_candidate_hashes,
   790	            *(_candidate_stable_key(candidate) for candidate in new_candidates),
   791	        }
   792	    )
   793	    enriched = with_provisional_gap_filler(session.schema_provider, provisional)
   794	    session.schema_provider = enriched
   795	    state.schema_provider = enriched
   796
   797
   798	def _legacy_failure_response(
   799	    state: AgentEditState,
   800	    context: TurnContext,
   801	    *,
   802	    failure: AgentError,
   803	) -> dict[str, Any]:
   804	    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, TurnOutcome, _stage_audit, build_legacy_agent_edit_v1, derive_apply_eligibility, derive_gates, product_failure_envelope_fields)  # T-039 late import: host namespace lookup; resolved at call time
   805	    derive_gates(
   806	        context,
   807	        baseline_graph_hash=state.baseline_graph_hash,
   808	        client_graph_hash=state.submit_structural_graph_hash,
   809	    )
   810	    failure = dataclasses.replace(
   811	        failure,
   812	        canvas_apply_allowed=context.canvas_apply_allowed,
   813	        queue_allowed=context.queue_allowed,
   814	    )
   815	    try:
  1088	            continue
  1089	        raw_candidates = dependency.get("resolver_candidates")
  1090	        if isinstance(raw_candidates, list):
  1091	            candidates.extend(
  1092	                dict(candidate)
  1093	                for candidate in raw_candidates
  1094	                if isinstance(candidate, Mapping)
  1095	            )
  1096	    new_candidates = [
  1097	        candidate
  1098	        for candidate in candidates
  1099	        if deps._candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
  1100	    ]
  1101	    if not new_candidates:
  1102	        return
  1103	    try:
  1104	        CompositeSchemaProvider, ProvisionalRegistrySchemaProvider = _import_from("vibecomfy.schema", "CompositeSchemaProvider"), _import_from("vibecomfy.schema", "ProvisionalRegistrySchemaProvider")
  1105	        with_provisional_gap_filler = _import_from("vibecomfy.schema", "with_provisional_gap_filler")
  1106
  1107	        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
  1108	        if not provisional.schemas():
  1109	            return
  1110	        state.provisional_registry_candidate_hashes = frozenset(
  1111	            {
  1112	                *state.provisional_registry_candidate_hashes,
  1113	                *(deps._candidate_stable_key(candidate) for candidate in new_candidates),
  1114	            }
  1115	        )
  1116	        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
  1117	    except Exception as exc:  # noqa: BLE001 - workflow evidence may still hydrate it
  1118	        deps.LOGGER.debug("planned registry dependency hydration unavailable: %s", exc)
  1119
  1120
  1121	def _stage_agent_batch_repl(globals_dict: Mapping[str, Any],
  1122	    state: AgentEditState,
  1123	    _context: TurnContext,
  1124	    *,
  1125	    deepseek_client: DeepSeekClient | None = None,

codex
Static inspection confirms the core invariant is encoded as `CompositeSchemaProvider(authoritative, provisional)`, matching first-match lookup and reverse-order merge behavior. I also found the “seven sites” count includes the baseline runtime→authoring composite in `_frag_orchestration.py`; there are six provisional-enrichment paths (five production call sites plus the shared helper) and that seventh baseline construction. I’m now testing both the B04-focused slice and the existing enum/asset mechanisms.
exec
/bin/zsh -lc ".venv/bin/python -m pytest -p no:rerunfailures -q tests/test_comfy_nodes_agent_edit.py tests/test_comfy_nodes_agent_backend_spine.py -k 'schema or precedence or provisional or real_schema or widget or cross_turn'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 3659ms:
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
The first pytest attempt was blocked before collection because this read-only sandbox exposes no writable temporary directory; this is separate from the known socket-plugin issue. I’m retrying the B04 tests with capture and cache disabled, which can work if those cases do not require `tmp_path`.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -s -p no:cacheprovider -p no:rerunfailures -q tests/test_comfy_nodes_agent_edit.py -k 'schema_precedence or schema_enrichment_cross_turn or research_precedent_provisional_workflow_schema_does_not_shadow_real_schema'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "ps -ax -o pid=,ppid=,stat=,command= | rg 'pytest.*schema_precedence|python -m pytest'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 414ms:
zsh:1: operation not permitted: ps

exec
/bin/zsh -lc "nl -ba tests/test_porting_edit_apply_values.py | sed -n '1,130p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "nl -ba tests/test_porting_edit_apply.py | sed -n '260,340p;680,760p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "rg -n 'invalid enum|enum.*(add|set)|rejects.*enum|without_mutat|missing.*asset|warning' tests/test_porting_edit_apply*.py tests/test_comfy_nodes_agent_edit.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "rg -n 'validate_asset|choices|invalid.*enum|enum' vibecomfy/porting/edit -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 510ms:
     1	from types import SimpleNamespace
     2
     3	import pytest
     4
     5	from vibecomfy.porting.edit.apply import apply_delta
     6	from vibecomfy.porting.edit.apply_values import _validate_literal_value
     7	from vibecomfy.porting.edit.ops import parse_edit_delta
     8	from vibecomfy.schema import InputSpec, NodeSchema
     9
    10
    11	def _validate(value: object, spec: SimpleNamespace, *, input_name: str) -> list:
    12	    return _validate_literal_value(
    13	        value=value,
    14	        spec=spec,
    15	        class_type="TestNode",
    16	        input_name=input_name,
    17	        context="test",
    18	    )
    19
    20
    21	@pytest.mark.parametrize(
    22	    ("spec", "input_name", "value"),
    23	    [
    24	        (SimpleNamespace(choices=["installed.safetensors"], type="lora"), "lora", "missing"),
    25	        (
    26	            SimpleNamespace(choices=["models/installed.safetensors"], type="STRING"),
    27	            "choice",
    28	            "missing",
    29	        ),
    30	        (
    31	            SimpleNamespace(choices=["installed"], type="STRING"),
    32	            "choice",
    33	            "WanVid/notinstalled.safetensors",
    34	        ),
    35	    ],
    36	)
    37	def test_validate_asset_enum_accepts_missing_local_asset_with_warning(
    38	    spec: SimpleNamespace,
    39	    input_name: str,
    40	    value: str,
    41	) -> None:
    42	    issues = _validate(value, spec, input_name=input_name)
    43
    44	    assert [(issue.code, issue.severity) for issue in issues] == [
    45	        ("asset_not_installed", "warning")
    46	    ]
    47	    assert issues[0].detail["value"] == value
    48
    49
    50	@pytest.mark.parametrize(
    51	    ("input_name", "value"),
    52	    [
    53	        ("scheduler", "bogus_scheduler"),
    54	        ("model_type", "bogus_model_type"),
    55	    ],
    56	)
    57	def test_validate_constrained_enum_still_rejects_unknown_value(
    58	    input_name: str,
    59	    value: str,
    60	) -> None:
    61	    spec = SimpleNamespace(choices=["euler", "dpm++_2m"], type="STRING", min=None, max=None)
    62
    63	    issues = _validate(value, spec, input_name=input_name)
    64
    65	    assert [(issue.code, issue.severity) for issue in issues] == [
    66	        ("value_not_in_enum", "error")
    67	    ]
    68
    69
    70	def test_validate_asset_enum_does_not_accept_non_string_value() -> None:
    71	    spec = SimpleNamespace(choices=["installed.safetensors"], type="lora")
    72
    73	    issues = _validate(123, spec, input_name="lora")
    74
    75	    assert issues[0].code == "value_not_in_enum"
    76	    assert issues[0].severity == "error"
    77
    78
    79	def test_apply_values_add_node_keeps_missing_asset_filename_and_warning() -> None:
    80	    schema = NodeSchema(
    81	        class_type="WanVideoLoraSelect",
    82	        pack="test",
    83	        inputs={
    84	            "lora": InputSpec(
    85	                type="lora",
    86	                choices=["installed.safetensors"],
    87	            )
    88	        },
    89	        outputs=[],
    90	    )
    91	    provider = SimpleNamespace(get_schema=lambda class_type: schema if class_type == schema.class_type else None)
    92	    delta = parse_edit_delta(
    93	        [
    94	            {
    95	                "op": "add_node",
    96	                "scope_path": "",
    97	                "class_type": schema.class_type,
    98	                "fields": {"lora": "WanVid/notinstalled.safetensors"},
    99	                "inputs": {},
   100	            }
   101	        ]
   102	    )
   103
   104	    result = apply_delta(
   105	        {"last_node_id": 0, "last_link_id": 0, "nodes": [], "links": []},
   106	        delta,
   107	        schema_provider=provider,
   108	    )
   109
   110	    assert result.ok is True
   111	    assert result.candidate is not None
   112	    assert result.candidate["nodes"][0]["widgets_values"] == ["WanVid/notinstalled.safetensors"]
   113	    warning = next(issue for issue in result.diagnostics if issue.code == "asset_not_installed")
   114	    assert warning.severity == "warning"

 succeeded in 778ms:
   260
   261	def _normalized_root_nodes(ui: dict[str, object]) -> dict[int, dict[str, object]]:
   262	    normalized = normalize_ui_json(ui)
   263	    return {
   264	        int(node["id"]): node
   265	        for node in normalized.get("nodes", [])
   266	        if isinstance(node, dict) and isinstance(node.get("id"), int)
   267	    }
   268
   269
   270	def _grouped_fixture() -> dict[str, object]:
   271	    fixture = _fixture()
   272	    fixture["groups"] = [
   273	        {
   274	            "title": "Outputs",
   275	            "bounding": [1240.0, 160.0, 340.0, 220.0],
   276	            "color": "#333333",
   277	        }
   278	    ]
   279	    return fixture
   280
   281
   282	def _node_rect(node: dict[str, object]) -> tuple[float, float, float, float]:
   283	    pos = node.get("pos")
   284	    size = node.get("size")
   285	    assert isinstance(pos, list) and len(pos) >= 2
   286	    assert isinstance(size, list) and len(size) >= 2
   287	    return float(pos[0]), float(pos[1]), float(size[0]), float(size[1])
   288
   289
   290	def _overlaps(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
   291	    return not (
   292	        left[0] + left[2] <= right[0]
   293	        or right[0] + right[2] <= left[0]
   294	        or left[1] + left[3] <= right[1]
   295	        or right[1] + right[3] <= left[1]
   296	    )
   297
   298
   299	def test_resolve_delta_rejects_invalid_enum_without_mutating_original() -> None:
   300	    original = _fixture()
   301	    before = copy.deepcopy(original)
   302	    provider = _SchemaProvider()
   303	    delta = parse_edit_delta(
   304	        [
   305	            {
   306	                "op": "set_node_field",
   307	                "target": ["", "5", "sampler_name"],
   308	                "value": "not-a-real-sampler",
   309	            }
   310	        ]
   311	    )
   312
   313	    result = resolve_delta(original, delta, schema_provider=provider)
   314
   315	    assert result.ok is False
   316	    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
   317	    assert result.resolved_ops == ()
   318	    assert original == before
   319
   320
   321	def test_resolve_delta_rejects_known_incompatible_link_without_mutating_original() -> None:
   322	    original = _fixture()
   323	    before = copy.deepcopy(original)
   324	    provider = _SchemaProvider()
   325	    delta = parse_edit_delta(
   326	        [
   327	            {
   328	                "op": "upsert_link",
   329	                "from": ["", "1", "MODEL"],
   330	                "to": ["", "5", "latent_image"],
   331	            }
   332	        ]
   333	    )
   334
   335	    result = resolve_delta(original, delta, schema_provider=provider)
   336
   337	    assert result.ok is False
   338	    assert any(issue.code == "incompatible_socket_types" for issue in result.diagnostics)
   339	    assert result.resolved_ops == ()
   340	    assert original == before
   680
   681	def test_resolve_delta_unknown_ksampler_set_node_field_includes_relevant_aliases() -> None:
   682	    """Semantic aliases must describe the mapping for UI-only slots like
   683	    control_after_generate → widget_1, while self-mapping fields (seed→seed)
   684	    are correctly excluded."""
   685	    original = {
   686	        "last_node_id": 1,
   687	        "last_link_id": 0,
   688	        "nodes": [
   689	            {
   690	                "id": 1,
   691	                "type": "KSampler",
   692	                "pos": [0, 0],
   693	                "size": [315, 341],
   694	                "flags": {},
   695	                "order": 0,
   696	                "mode": 0,
   697	                "inputs": [],
   698	                "outputs": [{"name": "LATENT", "type": "LATENT", "links": None, "slot_index": 0}],
   699	                "properties": {"vibecomfy_uid": "ksampler"},
   700	                "widgets_values": [42, "fixed", 8, 1.0, "euler", "normal", 1.0],
   701	            }
   702	        ],
   703	        "links": [],
   704	    }
   705	    delta = parse_edit_delta(
   706	        [
   707	            {
   708	                "op": "set_node_field",
   709	                "target": ["", "ksampler", "bogus"],
   710	                "value": 1,
   711	            }
   712	        ]
   713	    )
   714
   715	    result = resolve_delta(original, delta, schema_provider=_SchemaProvider())
   716
   717	    assert result.ok is False
   718	    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_node_field")
   719	    semantic_aliases = issue.detail["semantic_aliases"]
   720
   721	    # control_after_generate → widget_1 must be present (UI-only slot).
   722	    assert "control_after_generate" in semantic_aliases
   723	    assert semantic_aliases["control_after_generate"] == "widget_1"
   724
   725	    # Self-mapping fields (seed→seed, steps→steps, …) must NOT leak into aliases.
   726	    for compact_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
   727	        assert compact_name not in semantic_aliases, f"{compact_name!r} should not appear in semantic_aliases"
   728
   729
   730	def test_resolve_delta_unknown_ksampler_add_node_field_omits_covered_widget_N() -> None:
   731	    """When add_node targets a KSampler with an unknown field, the class-level
   732	    diagnostics must omit widget_N slots that have compact semantic names."""
   733	    original = _fixture()
   734	    delta = parse_edit_delta(
   735	        [
   736	            {
   737	                "op": "add_node",
   738	                "scope_path": "",
   739	                "class_type": "KSampler",
   740	                "fields": {"seed": 7, "bogus_field": 999},
   741	                "inputs": {},
   742	            }
   743	        ]
   744	    )
   745
   746	    result = resolve_delta(original, delta, schema_provider=_SchemaProvider())
   747
   748	    assert result.ok is False
   749	    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_add_node_field")
   750	    valid_fields = issue.detail["valid_fields"]
   751
   752	    # Compact names must be in valid_fields.
   753	    for compact_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
   754	        assert compact_name in valid_fields, f"{compact_name!r} missing from valid_fields"
   755
   756	    # widget_N for slots that have known semantic names must be omitted.
   757	    for widget_n in ("widget_0", "widget_2", "widget_3", "widget_4", "widget_5", "widget_6"):
   758	        assert widget_n not in valid_fields, f"{widget_n!r} should be omitted but is present"
   759
   760

 succeeded in 837ms:
vibecomfy/porting/edit/lint.py:1246:    for i, op in enumerate(delta):
vibecomfy/porting/edit/lint.py:1271:    for i, op in enumerate(delta):
vibecomfy/porting/edit/_describe.py:100:        for idx, slot in enumerate(inputs_raw if isinstance(inputs_raw, list) else []):
vibecomfy/porting/edit/_describe.py:184:            When ``None``, enumerates every known schema.
vibecomfy/porting/edit/apply_slots.py:15:    for index, item in enumerate(slots):
vibecomfy/porting/edit/apply_slots.py:54:    for index, name in enumerate(resolution.names):
vibecomfy/porting/edit/apply_field_aliases.py:102:    for i, name in enumerate(compact_names):
vibecomfy/porting/edit/apply_field_aliases.py:154:        for i, name in enumerate(names):
vibecomfy/porting/edit/apply_field_aliases.py:238:    for order, node in enumerate(nodes):
vibecomfy/porting/edit/apply_field_aliases.py:249:        for output_index, output in enumerate(outputs):
vibecomfy/porting/edit/apply_field_aliases.py:275:    for index, name in enumerate(resolution.names):
vibecomfy/porting/edit/apply_field_aliases.py:292:        for index, name in enumerate(names):
vibecomfy/porting/edit/apply_mutate.py:363:        index_by_name = {name: index for index, name in enumerate(names)}
vibecomfy/porting/edit/apply_mutate.py:381:    index_by_name = {name: index for index, name in enumerate(names)}
vibecomfy/porting/edit/apply_mutate.py:383:    for index, output in enumerate(node_ref.node["outputs"]):
vibecomfy/porting/edit/normalize.py:30:enumerated in the **allow-list** (see :data:`NORMALIZE_ALLOW_LIST`).
vibecomfy/porting/edit/apply_types.py:322:        choices = list(getattr(spec, "choices", None) or ())
vibecomfy/porting/edit/apply_types.py:323:        if raw_value is None and choices:
vibecomfy/porting/edit/apply_types.py:324:            for choice in choices:
vibecomfy/porting/edit/apply_resolve_base.py:324:                "value_not_in_enum",
vibecomfy/porting/edit/apply_resolve_base.py:325:                f"set_node_field rejected {class_type}.{field_path}: value {op.value!r} is not in the declared enum.",
vibecomfy/porting/edit/apply_resolve_base.py:330:                    "choices": list(_CONTROL_AFTER_GENERATE_CHOICES),
vibecomfy/porting/edit/_ir_utils.py:40:    # Try to enumerate known class types from the schema provider.
vibecomfy/porting/edit/_ir_utils.py:49:        # Cannot enumerate — fall back to case-insensitive direct lookup.
vibecomfy/porting/edit/_ir_utils.py:215:        for index, output in enumerate(raw_outputs):
vibecomfy/porting/edit/_ir_utils.py:234:        for index, output in enumerate(schema_outputs):
vibecomfy/porting/edit/_ir_utils.py:245:    for index, output in enumerate(schema_outputs):
vibecomfy/porting/edit/apply_place.py:231:    for index, group in enumerate(groups):
vibecomfy/porting/edit/apply_place.py:246:    for index, group in enumerate(groups):
vibecomfy/porting/edit/_resolve.py:74:    for index, item in enumerate(raw_items):
vibecomfy/porting/edit/_resolve.py:165:    for index, (semantic_name, _socket_type) in enumerate(entries):
vibecomfy/porting/edit/_resolve.py:236:        for index, source in enumerate(selected_sources, start=1):
vibecomfy/porting/edit/_resolve.py:422:    return "\n\n" + "\n".join(f"{index}. {note}" for index, note in enumerate(notes, start=1))
vibecomfy/porting/edit/ops.py:89:                    "op": {"enum": list(CANONICAL_DELTA_OP_NAMES)}
vibecomfy/porting/edit/ops.py:441:    for index, item in enumerate(value):
vibecomfy/porting/edit/ops.py:552:    for index, item in enumerate(payload):
vibecomfy/porting/edit/_session_types.py:107:            for i, op in enumerate(self.landed_ops):
vibecomfy/porting/edit/projection.py:189:            choices = getattr(spec, "choices", None)
vibecomfy/porting/edit/projection.py:190:            if choices:
vibecomfy/porting/edit/projection.py:191:                spec_str += f" one_of={list(choices)[:6]}"
vibecomfy/porting/edit/projection.py:336:        for index, value in enumerate(widgets):
vibecomfy/porting/edit/projection.py:371:        choices = getattr(spec, "choices", None)
vibecomfy/porting/edit/projection.py:372:        if choices:
vibecomfy/porting/edit/projection.py:373:            preview = list(choices[:8]) if isinstance(choices, list) else list(choices)
vibecomfy/porting/edit/projection.py:374:            bits.append(f"choices={_format_value(preview)}")
vibecomfy/porting/edit/projection.py:380:    for index, output in enumerate(outputs):
vibecomfy/porting/edit/projection.py:393:    for index, slot in enumerate(slots):
vibecomfy/porting/edit/_diff.py:160:        landed_statement_indexes = [i for i, statement in enumerate(statement_results) if statement.landed]
vibecomfy/porting/edit/_diff.py:162:        for op_index, op in enumerate(landed_ops):
vibecomfy/porting/edit/ledger.py:71:    for index, definition in enumerate(subgraphs):
vibecomfy/porting/edit/apply_links.py:186:    for index, link in enumerate(list(links)):
vibecomfy/porting/edit/apply_links.py:393:    for index, node in enumerate(list(nodes)):
vibecomfy/porting/edit/apply_values.py:23:    choices = getattr(spec, "choices", None) or []
vibecomfy/porting/edit/apply_values.py:24:    if choices and value not in choices and _coerce_choice_value(value, choices) is _NO_MATCH:
vibecomfy/porting/edit/apply_values.py:29:            "choices": list(choices),
vibecomfy/porting/edit/apply_values.py:31:        if _is_asset_enum(value=value, spec=spec, input_name=input_name, choices=choices):
vibecomfy/porting/edit/apply_values.py:35:                    f"{context} accepted {class_type}.{input_name}: asset {value!r} is not in the declared local choices.",
vibecomfy/porting/edit/apply_values.py:43:                    "value_not_in_enum",
vibecomfy/porting/edit/apply_values.py:44:                    f"{context} rejected {class_type}.{input_name}: value {value!r} is not in the declared enum.",
vibecomfy/porting/edit/apply_values.py:145:def _is_asset_enum(*, value: Any, spec: InputSpec, input_name: str, choices: list[Any]) -> bool:
vibecomfy/porting/edit/apply_values.py:149:    # ComfyUI exposes installed asset files as enums. Treat an enum as an asset
vibecomfy/porting/edit/apply_values.py:150:    # selector when its field/type names identify an asset, its installed choices
vibecomfy/porting/edit/apply_values.py:160:    if any(isinstance(choice, str) and _looks_like_asset_reference(choice) for choice in choices):
vibecomfy/porting/edit/apply_values.py:179:def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
vibecomfy/porting/edit/apply_values.py:182:        for choice in choices:

 succeeded in 950ms:
tests/test_porting_edit_apply_values.py:37:def test_validate_asset_enum_accepts_missing_local_asset_with_warning(
tests/test_porting_edit_apply_values.py:45:        ("asset_not_installed", "warning")
tests/test_porting_edit_apply_values.py:79:def test_apply_values_add_node_keeps_missing_asset_filename_and_warning() -> None:
tests/test_porting_edit_apply_values.py:113:    warning = next(issue for issue in result.diagnostics if issue.code == "asset_not_installed")
tests/test_porting_edit_apply_values.py:114:    assert warning.severity == "warning"
tests/test_porting_edit_apply.py:299:def test_resolve_delta_rejects_invalid_enum_without_mutating_original() -> None:
tests/test_porting_edit_apply.py:321:def test_resolve_delta_rejects_known_incompatible_link_without_mutating_original() -> None:
tests/test_comfy_nodes_agent_edit.py:21:    _batch_warning_sentence,
tests/test_comfy_nodes_agent_edit.py:3321:            warnings=("local corpus unavailable",),
tests/test_comfy_nodes_agent_edit.py:3537:        "warnings": ["Some nodes may require custom packs"],
tests/test_comfy_nodes_agent_edit.py:3605:        "warnings": ["warning1", "warning2", "warning3"],
tests/test_comfy_nodes_agent_edit.py:3661:        "warnings": [],
tests/test_comfy_nodes_agent_edit.py:3736:        "warnings": ["global warning 1"],
tests/test_comfy_nodes_agent_edit.py:3755:    assert "global warning 1" not in result
tests/test_comfy_nodes_agent_edit.py:3771:        "warnings": [],
tests/test_comfy_nodes_agent_edit.py:3801:        "warnings": [],
tests/test_comfy_nodes_agent_edit.py:3867:        "warnings": [],
tests/test_comfy_nodes_agent_edit.py:3993:        "warnings": [],
tests/test_comfy_nodes_agent_edit.py:4609:            warnings=("Registry schema is not published.",),
tests/test_comfy_nodes_agent_edit.py:4656:            warnings=("Comfy Registry returned ambiguous candidates for 'Note'.",),
tests/test_comfy_nodes_agent_edit.py:5904:            warnings=("local corpus unavailable",),
tests/test_comfy_nodes_agent_edit.py:6658:            warnings=("precedent research: no workflow/template precedents found",),
tests/test_comfy_nodes_agent_edit.py:7514:def test_handle_agent_edit_hotshotxl_complete_plan_keeps_queue_warning(
tests/test_comfy_nodes_agent_edit.py:7543:            "session_id": "hotshotxl-complete-plan-queue-warning",
tests/test_comfy_nodes_agent_edit.py:7570:    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
tests/test_comfy_nodes_agent_edit.py:7571:    assert result["apply_eligibility"]["warnings"] == ["queue_blocked"]
tests/test_comfy_nodes_agent_edit.py:7585:        "hotshotxl-complete-plan-queue-warning",
tests/test_comfy_nodes_agent_edit.py:7595:    assert response_payload["apply_eligibility"]["reason"] == "queue_blocked_warning"
tests/test_comfy_nodes_agent_edit.py:7732:def test_batch_repl_response_passing_execution_plan_keeps_queue_warning_candidate(
tests/test_comfy_nodes_agent_edit.py:7777:    assert response["apply_eligibility"]["reason"] == "queue_blocked_warning"
tests/test_comfy_nodes_agent_edit.py:8148:    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
tests/test_comfy_nodes_agent_edit.py:8149:    assert result["apply_eligibility"]["warnings"] == ["queue_blocked"]
tests/test_comfy_nodes_agent_edit.py:9606:                        "warning_count": 0,
tests/test_comfy_nodes_agent_edit.py:9658:                "warning_count": 0,
tests/test_comfy_nodes_agent_edit.py:10755:    assert result["apply_eligibility"]["reason"] == "queue_blocked_warning"
tests/test_comfy_nodes_agent_edit.py:10756:    assert result["apply_eligibility"]["warnings"] == ["queue_blocked"]
tests/test_comfy_nodes_agent_edit.py:12848:    # in the failure path (where failure + _BATCH_EXIT_BUDGET combines lead + warning).
tests/test_comfy_nodes_agent_edit.py:12855:    """Partial success: some edits landed, failure set (with budget exit) — lead + warning."""
tests/test_comfy_nodes_agent_edit.py:12878:    """Partial success with failure but zero landed edits — just the warning."""
tests/test_comfy_nodes_agent_edit.py:13523:    """Edit+clarify combines lead + clarification warning."""
tests/test_comfy_nodes_agent_edit.py:15146:            "reason": "queue_blocked_warning",
tests/test_comfy_nodes_agent_edit.py:15148:            "warnings": ["queue_blocked"],
tests/test_comfy_nodes_agent_edit.py:16034:            "reason": "queue_blocked_warning",
tests/test_comfy_nodes_agent_edit.py:16036:            "warnings": ["queue_blocked"],
tests/test_comfy_nodes_agent_edit.py:16136:            "reason": "queue_blocked_warning",
tests/test_comfy_nodes_agent_edit.py:16138:            "warnings": ["queue_blocked"],
tests/test_comfy_nodes_agent_edit.py:17414:    """Actionable failed plans keep validation warnings; empty failed plans do not render."""
tests/test_comfy_nodes_agent_edit.py:19137:                "reason": "queue_blocked_warning",

exec
/bin/zsh -lc "rg -n 'value_not_in_enum|not-a-real-sampler|bogus_scheduler|bogus_model_type' tests --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 815ms:
tests/test_agent_edit_settings_contract.py:426:def test_batch_set_sampler_name_nonexistent_fails_with_value_not_in_enum() -> None:
tests/test_agent_edit_settings_contract.py:428:    ``value_not_in_enum`` and the diagnostic detail includes valid choices."""
tests/test_agent_edit_settings_contract.py:440:    assert "value_not_in_enum" in diag_codes
tests/test_agent_edit_settings_contract.py:442:    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
tests/test_agent_edit_settings_contract.py:465:    assert "value_not_in_enum" in report
tests/test_agent_edit_settings_contract.py:471:def test_batch_set_scheduler_nonexistent_fails_with_value_not_in_enum() -> None:
tests/test_agent_edit_settings_contract.py:479:    assert "value_not_in_enum" in diag_codes
tests/test_agent_edit_settings_contract.py:481:    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
tests/test_agent_edit_settings_contract.py:546:    assert "value_not_in_enum" in report
tests/test_schema_validate.py:76:def test_value_not_in_enum_emits_error() -> None:
tests/test_schema_validate.py:82:    assert issue.code == "value_not_in_enum"
tests/test_schema_validate.py:106:        ("value_not_in_enum", "UNETLoader", "unet_name")
tests/test_porting_edit_corpus.py:340:            "value_not_in_enum",
tests/test_porting_edit_corpus.py:388:    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
tests/test_schema.py:383:    assert by_code["value_not_in_enum"].detail["choices"] == ["a", "b"]
tests/test_comfy_nodes_agent_backend_spine.py:2425:    assert any(issue["code"] == "value_not_in_enum" for issue in diagnostics.issues)
tests/test_demo_factory_structural_baseline.py:250:        "value_not_in_enum",
tests/test_demo_factory_structural_baseline.py:267:        "value_not_in_enum",
tests/test_porting_edit_apply_values.py:53:        ("scheduler", "bogus_scheduler"),
tests/test_porting_edit_apply_values.py:54:        ("model_type", "bogus_model_type"),
tests/test_porting_edit_apply_values.py:66:        ("value_not_in_enum", "error")
tests/test_porting_edit_apply_values.py:75:    assert issues[0].code == "value_not_in_enum"
tests/test_cli_port.py:315:    assert {"missing_required_input", "unknown_input", "value_not_in_enum", "value_out_of_range", "primitive_type_mismatch"} <= codes
tests/test_cli_port.py:360:        ({"sampler_name": "not-a-sampler"}, "value_not_in_enum", "sampler_name"),
tests/test_porting_edit_apply.py:308:                "value": "not-a-real-sampler",
tests/test_porting_edit_apply.py:316:    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
tests/test_porting_edit_apply.py:1069:    issue = next(issue for issue in result.diagnostics if issue.code == "value_not_in_enum")
tests/test_comfy_nodes_agent_edit.py:16347:                                    "code": "value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py:16382:    assert diag["code"] == "value_not_in_enum"
tests/test_comfy_nodes_agent_edit.py:16766:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py:16786:    assert "value_not_in_enum" in report
tests/test_comfy_nodes_agent_edit.py:16841:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py:16907:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py:16918:    assert "value_not_in_enum" in report
tests/test_comfy_nodes_agent_edit.py:17004:        code="value_not_in_enum",

exec
/bin/zsh -lc "nl -ba tests/test_porting_edit_apply.py | sed -n '1010,1090p'; nl -ba tests/test_porting_edit_corpus.py | sed -n '310,405p'; nl -ba tests/test_agent_edit_settings_contract.py | sed -n '400,500p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 335ms:
  1010	                "outputs": [{"name": "LATENT", "type": "LATENT", "links": None, "slot_index": 0}],
  1011	                "properties": {"vibecomfy_uid": "ksampler"},
  1012	                "widgets_values": [42, "fixed", 8, 1, "euler", "normal", 1],
  1013	            }
  1014	        ],
  1015	        "links": [],
  1016	    }
  1017	    delta = parse_edit_delta(
  1018	        [
  1019	            {
  1020	                "op": "set_node_field",
  1021	                "target": ["", "ksampler", "unused_widget_1"],
  1022	                "value": "randomize",
  1023	            }
  1024	        ]
  1025	    )
  1026
  1027	    result = apply_delta(original, delta, schema_provider=_SchemaProvider())
  1028
  1029	    assert result.ok is True
  1030	    assert result.candidate is not None
  1031	    node = result.candidate["nodes"][0]
  1032	    assert node["widgets_values"] == [42, "randomize", 8, 1, "euler", "normal", 1]
  1033
  1034
  1035	def test_apply_delta_rejects_invalid_control_after_generate_value() -> None:
  1036	    original = {
  1037	        "last_node_id": 1,
  1038	        "last_link_id": 0,
  1039	        "nodes": [
  1040	            {
  1041	                "id": 1,
  1042	                "type": "KSampler",
  1043	                "pos": [0, 0],
  1044	                "size": [315, 341],
  1045	                "flags": {},
  1046	                "order": 0,
  1047	                "mode": 0,
  1048	                "inputs": [],
  1049	                "outputs": [{"name": "LATENT", "type": "LATENT", "links": None, "slot_index": 0}],
  1050	                "properties": {"vibecomfy_uid": "ksampler"},
  1051	                "widgets_values": [42, "fixed", 8, 1, "euler", "normal", 1],
  1052	            }
  1053	        ],
  1054	        "links": [],
  1055	    }
  1056	    delta = parse_edit_delta(
  1057	        [
  1058	            {
  1059	                "op": "set_node_field",
  1060	                "target": ["", "ksampler", "control_after_generate"],
  1061	                "value": "sometimes",
  1062	            }
  1063	        ]
  1064	    )
  1065
  1066	    result = apply_delta(original, delta, schema_provider=_SchemaProvider())
  1067
  1068	    assert result.ok is False
  1069	    issue = next(issue for issue in result.diagnostics if issue.code == "value_not_in_enum")
  1070	    assert issue.detail["choices"] == ["fixed", "randomize", "increment", "decrement"]
  1071
  1072
  1073	def test_apply_delta_adds_node_with_ledger_ids_and_collision_nudging() -> None:
  1074	    original = _fixture()
  1075	    provider = _SchemaProvider()
  1076	    delta = parse_edit_delta(
  1077	        [
  1078	            {
  1079	                "op": "add_node",
  1080	                "scope_path": "",
  1081	                "class_type": "SaveImage",
  1082	                "fields": {"filename_prefix": "agent-edit/new"},
  1083	                "inputs": {"images": ["", "6", "IMAGE"]},
  1084	                "anchor": {"relation": "right_of", "near": ["", "5"]},
  1085	            }
  1086	        ]
  1087	    )
  1088
  1089	    first = apply_delta(copy.deepcopy(original), delta, schema_provider=provider)
  1090	    second = apply_delta(copy.deepcopy(original), delta, schema_provider=provider)
   310	    original = _fixture("flat.json")
   311	    first_before = EditLedger.ingest(original).stamped_copy()
   312	    first_delta = parse_edit_delta(
   313	        [{"op": "set_node_field", "target": ["", "2", "text"], "value": "first edit"}]
   314	    )
   315
   316	    first = apply_delta(original, first_delta, schema_provider=_SchemaProvider())
   317
   318	    assert first.ok is True
   319	    assert first.candidate is not None
   320	    _assert_preserves_out_of_delta_nodes(first_before, first.candidate, touched={("", "2")})
   321
   322	    second_before = EditLedger.ingest(first.candidate).stamped_copy()
   323	    second_delta = parse_edit_delta(
   324	        [{"op": "set_node_field", "target": ["", "2", "text"], "value": "second edit"}]
   325	    )
   326
   327	    second = apply_delta(first.candidate, second_delta, schema_provider=_SchemaProvider())
   328
   329	    assert second.ok is True
   330	    assert second.candidate is not None
   331	    assert _node(second.candidate, 2)["widgets_values"] == ["second edit"]
   332	    _assert_preserves_out_of_delta_nodes(second_before, second.candidate, touched={("", "2")})
   333
   334
   335	@pytest.mark.parametrize(
   336	    ("raw_delta", "expected_code"),
   337	    [
   338	        (
   339	            [{"op": "set_node_field", "target": ["", "5", "sampler_name"], "value": "not-real"}],
   340	            "value_not_in_enum",
   341	        ),
   342	        (
   343	            [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 1000}],
   344	            "value_out_of_range",
   345	        ),
   346	        (
   347	            [{"op": "set_node_field", "target": ["", "5", "steps"], "value": "twenty"}],
   348	            "value_type_mismatch",
   349	        ),
   350	        (
   351	            [{"op": "upsert_link", "from": ["", "1", "MODEL"], "to": ["", "5", "latent_image"]}],
   352	            "incompatible_socket_types",
   353	        ),
   354	    ],
   355	)
   356	def test_edit_corpus_rejects_invalid_scripted_ops_atomically(
   357	    raw_delta: list[dict[str, Any]],
   358	    expected_code: str,
   359	) -> None:
   360	    original = _fixture("flat.json")
   361	    before = copy.deepcopy(original)
   362
   363	    result = apply_delta(original, parse_edit_delta(raw_delta), schema_provider=_SchemaProvider())
   364
   365	    assert result.ok is False
   366	    assert result.candidate is None
   367	    assert result.mutation_started is False
   368	    assert original == before
   369	    assert any(issue.code == expected_code for issue in result.diagnostics)
   370
   371
   372	def test_edit_corpus_later_rejection_keeps_earlier_successful_op_atomic() -> None:
   373	    original = _fixture("flat.json")
   374	    before = copy.deepcopy(original)
   375	    delta = parse_edit_delta(
   376	        [
   377	            {"op": "set_node_field", "target": ["", "2", "text"], "value": "should not apply"},
   378	            {"op": "set_node_field", "target": ["", "5", "sampler_name"], "value": "not-real"},
   379	        ]
   380	    )
   381
   382	    result = apply_delta(original, delta, schema_provider=_SchemaProvider())
   383
   384	    assert result.ok is False
   385	    assert result.candidate is None
   386	    assert result.mutation_started is False
   387	    assert original == before
   388	    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
   400	    """Setting ``scheduler='karras'`` (a valid enum choice) lands."""
   401	    session = _ks_edit_session()
   402	    result = session.apply_batch("ksampler.scheduler = 'karras'")
   403
   404	    assert result.ok is True
   405	    assert result.statements[0].landed is True
   406
   407	    node = session.working_ui["nodes"][0]
   408	    assert node["widgets_values"][5] == "karras"
   409
   410
   411	def test_batch_set_sampler_name_to_valid_enum() -> None:
   412	    """Setting ``sampler_name='dpmpp_2m'`` (a valid enum choice) lands."""
   413	    session = _ks_edit_session()
   414	    result = session.apply_batch("ksampler.sampler_name = 'dpmpp_2m'")
   415
   416	    assert result.ok is True
   417	    assert result.statements[0].landed is True
   418
   419	    node = session.working_ui["nodes"][0]
   420	    assert node["widgets_values"][4] == "dpmpp_2m"
   421
   422
   423	# ── failure paths — invalid enum value ───────────────────────────────────
   424
   425
   426	def test_batch_set_sampler_name_nonexistent_fails_with_value_not_in_enum() -> None:
   427	    """Setting ``sampler_name='nonexistent_sampler'`` fails with
   428	    ``value_not_in_enum`` and the diagnostic detail includes valid choices."""
   429	    session = _ks_edit_session()
   430	    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
   431
   432	    assert result.ok is False
   433	    assert len(result.statements) == 1
   434	    stmt = result.statements[0]
   435	    assert stmt.ok is False
   436	    assert stmt.landed is False
   437	    assert stmt.op_kind == "set_node_field"
   438
   439	    diag_codes = {d.code for d in stmt.diagnostics}
   440	    assert "value_not_in_enum" in diag_codes
   441
   442	    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
   443	    detail = enum_diag.detail
   444	    assert detail.get("class_type") == "KSampler"
   445	    assert detail.get("input") == "sampler_name"
   446	    assert detail.get("value") == "nonexistent_sampler"
   447	    assert isinstance(detail.get("choices"), list)
   448	    assert len(detail["choices"]) >= 4  # at least the 4 we configured
   449	    assert "euler" in detail["choices"]
   450	    assert "nonexistent_sampler" not in detail["choices"]
   451
   452	    # Graph should NOT be mutated
   453	    node = session.working_ui["nodes"][0]
   454	    assert node["widgets_values"][4] == "euler"
   455
   456
   457	def test_batch_set_sampler_name_nonexistent_text_report_includes_choices() -> None:
   458	    """The text report for an invalid enum edit includes the valid choices list."""
   459	    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
   460
   461	    session = _ks_edit_session()
   462	    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
   463	    report = _format_batch_report(result, consecutive_errors=1, budget_remaining=3)
   464
   465	    assert "value_not_in_enum" in report
   466	    assert "choices:" in report
   467	    assert "euler" in report
   468	    assert "nonexistent_sampler" in report
   469
   470
   471	def test_batch_set_scheduler_nonexistent_fails_with_value_not_in_enum() -> None:
   472	    """Setting ``scheduler='nonexistent_scheduler'`` fails with enum diagnostics."""
   473	    session = _ks_edit_session()
   474	    result = session.apply_batch("ksampler.scheduler = 'nonexistent_scheduler'")
   475
   476	    assert result.ok is False
   477	    stmt = result.statements[0]
   478	    diag_codes = {d.code for d in stmt.diagnostics}
   479	    assert "value_not_in_enum" in diag_codes
   480
   481	    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
   482	    assert enum_diag.detail.get("input") == "scheduler"
   483	    assert "normal" in enum_diag.detail["choices"]
   484
   485
   486	# ── failure paths — unknown field ────────────────────────────────────────
   487
   488
   489	def test_batch_set_nonexistent_attribute_sampler_fails_with_unknown_target_field() -> None:
   490	    """Setting ``ksampler.sampler = 'euler'`` (no such attribute) fails with
   491	    ``unknown_target_field`` and diagnostic detail names the field and
   492	    surfaces ``valid_fields`` containing compact KSampler fields."""
   493	    session = _ks_edit_session()
   494	    result = session.apply_batch("ksampler.sampler = 'euler'")
   495
   496	    assert result.ok is False
   497	    stmt = result.statements[0]
   498	    assert stmt.ok is False
   499	    assert stmt.landed is False
   500

 exited 1 in 173425ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
[32m[INFO][0m Set vram state to: NORMAL_VRAM
objc[32743]: Class AVFFrameReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x137fac3a8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x147fd83a8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
objc[32743]: Class AVFAudioReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x137fac3f8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x147fd83f8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
[32m[INFO][0m PromptServer imported; registering VibeComfy routes.
[32m[INFO][0m vibecomfy agent routes module loaded and all routes registered.
[32m[INFO][0m VibeComfy routes registered successfully.
..........
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1434
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: timeout

    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

.venv/lib/python3.11/site-packages/torch/library.py:361
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/torch/library.py:361: UserWarning: Warning only once for all operators,  other operators may also be overridden.
    Overriding a previously registered kernel for the same operator and the same dispatch key
    operator: aten::mm(Tensor self, Tensor mat2) -> Tensor
      registered at /Users/runner/work/pytorch/pytorch/build/aten/src/ATen/RegisterSchema.cpp:6
    dispatch key: MPS
    previous kernel: registered at /Users/runner/work/pytorch/pytorch/aten/src/ATen/LegacyBatchingRegistrations.cpp:1076
         new kernel: registered at /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/fp4_fp8_for_torch_mps/ops.py:7 (Triggered internally at /Users/runner/work/pytorch/pytorch/aten/src/ATen/core/dispatch/OperatorEntry.cpp:215.)
    self.m.impl(

.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32: DeprecationWarning: SelectableGroups dict interface is deprecated. Use select.
    return EntryPoints(ep for group_eps in eps.values() for ep in group_eps)

.venv/lib/python3.11/site-packages/comfy/model_management.py:237
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/comfy/model_management.py:237: UserWarning: torch.cuda.current_device() did not return a device, returning a CPU torch device
    warnings.warn("torch.cuda.current_device() did not return a device, returning a CPU torch device")

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

tests/test_comfy_nodes_agent_edit.py:390
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_comfy_nodes_agent_edit.py:390: UserWarning: emit_ui_json: schema-less node 2(SaveImage); emitting best-effort slots. Pass strict=True to hard-fail.
    graph = emit_ui_json(

tests/conftest.py:352
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/conftest.py:352: PytestUnknownMarkWarning: Unknown pytest.mark.flaky - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    flaky_marker = pytest.mark.flaky(reruns=1, reruns_delay=10)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
10 passed, 441 deselected, 8 warnings in 107.80s (0:01:47)
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pytest/__main__.py", line 9, in <module>
    raise SystemExit(pytest.console_main())
                     ^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
           ^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 199, in main
    ret: ExitCode | int = config.hook.pytest_cmdline_main(config=config)
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/main.py", line 360, in wrap_session
    config._ensure_unconfigure()
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1177, in _ensure_unconfigure
    self._cleanup_stack.close()
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/contextlib.py", line 609, in close
    self.__exit__(None, None, None)
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/contextlib.py", line 601, in __exit__
    raise exc_details[1]
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/contextlib.py", line 586, in __exit__
    if cb(*exc_details):
       ^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/contextlib.py", line 469, in _exit_wrapper
    callback(*args, **kwds)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/unraisableexception.py", line 94, in cleanup
    gc_collect_harder(gc_collect_iterations)
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/unraisableexception.py", line 33, in gc_collect_harder
    gc.collect()
KeyboardInterrupt
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

exec
/bin/zsh -lc "rg -n -i -C3 'add.{0,60}(enum|invalid)|invalid.{0,60}add|add_node.{0,100}value_not_in_enum' tests/test_comfy_nodes_agent_edit.py tests/test_agent_edit_settings_contract.py tests/test_porting_edit_apply.py tests/test_porting_edit_apply_values.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 404ms:
exec
/bin/zsh -lc "rg -n -C8 'not-real|nonexistent_sampler|bogus_scheduler|value_not_in_enum' tests --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 303ms:
tests/test_agent_edit_settings_contract.py-418-
tests/test_agent_edit_settings_contract.py-419-    node = session.working_ui["nodes"][0]
tests/test_agent_edit_settings_contract.py-420-    assert node["widgets_values"][4] == "dpmpp_2m"
tests/test_agent_edit_settings_contract.py-421-
tests/test_agent_edit_settings_contract.py-422-
tests/test_agent_edit_settings_contract.py-423-# ── failure paths — invalid enum value ───────────────────────────────────
tests/test_agent_edit_settings_contract.py-424-
tests/test_agent_edit_settings_contract.py-425-
tests/test_agent_edit_settings_contract.py:426:def test_batch_set_sampler_name_nonexistent_fails_with_value_not_in_enum() -> None:
tests/test_agent_edit_settings_contract.py:427:    """Setting ``sampler_name='nonexistent_sampler'`` fails with
tests/test_agent_edit_settings_contract.py:428:    ``value_not_in_enum`` and the diagnostic detail includes valid choices."""
tests/test_agent_edit_settings_contract.py-429-    session = _ks_edit_session()
tests/test_agent_edit_settings_contract.py:430:    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
tests/test_agent_edit_settings_contract.py-431-
tests/test_agent_edit_settings_contract.py-432-    assert result.ok is False
tests/test_agent_edit_settings_contract.py-433-    assert len(result.statements) == 1
tests/test_agent_edit_settings_contract.py-434-    stmt = result.statements[0]
tests/test_agent_edit_settings_contract.py-435-    assert stmt.ok is False
tests/test_agent_edit_settings_contract.py-436-    assert stmt.landed is False
tests/test_agent_edit_settings_contract.py-437-    assert stmt.op_kind == "set_node_field"
tests/test_agent_edit_settings_contract.py-438-
tests/test_agent_edit_settings_contract.py-439-    diag_codes = {d.code for d in stmt.diagnostics}
tests/test_agent_edit_settings_contract.py:440:    assert "value_not_in_enum" in diag_codes
tests/test_agent_edit_settings_contract.py-441-
tests/test_agent_edit_settings_contract.py:442:    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
tests/test_agent_edit_settings_contract.py-443-    detail = enum_diag.detail
tests/test_agent_edit_settings_contract.py-444-    assert detail.get("class_type") == "KSampler"
tests/test_agent_edit_settings_contract.py-445-    assert detail.get("input") == "sampler_name"
tests/test_agent_edit_settings_contract.py:446:    assert detail.get("value") == "nonexistent_sampler"
tests/test_agent_edit_settings_contract.py-447-    assert isinstance(detail.get("choices"), list)
tests/test_agent_edit_settings_contract.py-448-    assert len(detail["choices"]) >= 4  # at least the 4 we configured
tests/test_agent_edit_settings_contract.py-449-    assert "euler" in detail["choices"]
tests/test_agent_edit_settings_contract.py:450:    assert "nonexistent_sampler" not in detail["choices"]
tests/test_agent_edit_settings_contract.py-451-
tests/test_agent_edit_settings_contract.py-452-    # Graph should NOT be mutated
tests/test_agent_edit_settings_contract.py-453-    node = session.working_ui["nodes"][0]
tests/test_agent_edit_settings_contract.py-454-    assert node["widgets_values"][4] == "euler"
tests/test_agent_edit_settings_contract.py-455-
tests/test_agent_edit_settings_contract.py-456-
tests/test_agent_edit_settings_contract.py-457-def test_batch_set_sampler_name_nonexistent_text_report_includes_choices() -> None:
tests/test_agent_edit_settings_contract.py-458-    """The text report for an invalid enum edit includes the valid choices list."""
tests/test_agent_edit_settings_contract.py-459-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
tests/test_agent_edit_settings_contract.py-460-
tests/test_agent_edit_settings_contract.py-461-    session = _ks_edit_session()
tests/test_agent_edit_settings_contract.py:462:    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
tests/test_agent_edit_settings_contract.py-463-    report = _format_batch_report(result, consecutive_errors=1, budget_remaining=3)
tests/test_agent_edit_settings_contract.py-464-
tests/test_agent_edit_settings_contract.py:465:    assert "value_not_in_enum" in report
tests/test_agent_edit_settings_contract.py-466-    assert "choices:" in report
tests/test_agent_edit_settings_contract.py-467-    assert "euler" in report
tests/test_agent_edit_settings_contract.py:468:    assert "nonexistent_sampler" in report
tests/test_agent_edit_settings_contract.py-469-
tests/test_agent_edit_settings_contract.py-470-
tests/test_agent_edit_settings_contract.py:471:def test_batch_set_scheduler_nonexistent_fails_with_value_not_in_enum() -> None:
tests/test_agent_edit_settings_contract.py-472-    """Setting ``scheduler='nonexistent_scheduler'`` fails with enum diagnostics."""
tests/test_agent_edit_settings_contract.py-473-    session = _ks_edit_session()
tests/test_agent_edit_settings_contract.py-474-    result = session.apply_batch("ksampler.scheduler = 'nonexistent_scheduler'")
tests/test_agent_edit_settings_contract.py-475-
tests/test_agent_edit_settings_contract.py-476-    assert result.ok is False
tests/test_agent_edit_settings_contract.py-477-    stmt = result.statements[0]
tests/test_agent_edit_settings_contract.py-478-    diag_codes = {d.code for d in stmt.diagnostics}
tests/test_agent_edit_settings_contract.py:479:    assert "value_not_in_enum" in diag_codes
tests/test_agent_edit_settings_contract.py-480-
tests/test_agent_edit_settings_contract.py:481:    enum_diag = next(d for d in stmt.diagnostics if d.code == "value_not_in_enum")
tests/test_agent_edit_settings_contract.py-482-    assert enum_diag.detail.get("input") == "scheduler"
tests/test_agent_edit_settings_contract.py-483-    assert "normal" in enum_diag.detail["choices"]
tests/test_agent_edit_settings_contract.py-484-
tests/test_agent_edit_settings_contract.py-485-
tests/test_agent_edit_settings_contract.py-486-# ── failure paths — unknown field ────────────────────────────────────────
tests/test_agent_edit_settings_contract.py-487-
tests/test_agent_edit_settings_contract.py-488-
tests/test_agent_edit_settings_contract.py-489-def test_batch_set_nonexistent_attribute_sampler_fails_with_unknown_target_field() -> None:
--
tests/test_agent_edit_settings_contract.py-534-# ── batch report integration (structured diagnostics in text) ────────────
tests/test_agent_edit_settings_contract.py-535-
tests/test_agent_edit_settings_contract.py-536-
tests/test_agent_edit_settings_contract.py-537-def test_batch_report_for_enum_failure_has_detail_choices() -> None:
tests/test_agent_edit_settings_contract.py-538-    """``_format_batch_report`` includes ``choices`` detail for enum failure."""
tests/test_agent_edit_settings_contract.py-539-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
tests/test_agent_edit_settings_contract.py-540-
tests/test_agent_edit_settings_contract.py-541-    session = _ks_edit_session()
tests/test_agent_edit_settings_contract.py:542:    result = session.apply_batch("ksampler.sampler_name = 'nonexistent_sampler'")
tests/test_agent_edit_settings_contract.py-543-    report = _format_batch_report(result, consecutive_errors=0, budget_remaining=5)
tests/test_agent_edit_settings_contract.py-544-
tests/test_agent_edit_settings_contract.py-545-    # The report should contain both the diagnostic code and the choices
tests/test_agent_edit_settings_contract.py:546:    assert "value_not_in_enum" in report
tests/test_agent_edit_settings_contract.py-547-    assert "choices:" in report
tests/test_agent_edit_settings_contract.py-548-    assert "'euler'" in report
tests/test_agent_edit_settings_contract.py-549-
tests/test_agent_edit_settings_contract.py-550-
tests/test_agent_edit_settings_contract.py-551-def test_batch_report_for_unknown_field_has_diagnostic_code() -> None:
tests/test_agent_edit_settings_contract.py-552-    """``_format_batch_report`` includes ``unknown_target_field`` and
tests/test_agent_edit_settings_contract.py-553-    ``valid_fields`` for unknown field."""
tests/test_agent_edit_settings_contract.py-554-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
--
tests/test_agent_edit_settings_contract.py-590-    assert node["widgets_values"][3] == 7.5
tests/test_agent_edit_settings_contract.py-591-
tests/test_agent_edit_settings_contract.py-592-
tests/test_agent_edit_settings_contract.py-593-def test_batch_mixed_success_and_failure_rolls_back() -> None:
tests/test_agent_edit_settings_contract.py-594-    """When a later statement fails, earlier successful edits are rolled back."""
tests/test_agent_edit_settings_contract.py-595-    session = _ks_edit_session()
tests/test_agent_edit_settings_contract.py-596-    batch = (
tests/test_agent_edit_settings_contract.py-597-        "ksampler.steps = 30\n"
tests/test_agent_edit_settings_contract.py:598:        "ksampler.sampler_name = 'nonexistent_sampler'\n"
tests/test_agent_edit_settings_contract.py-599-        "ksampler.cfg = 7.5"
tests/test_agent_edit_settings_contract.py-600-    )
tests/test_agent_edit_settings_contract.py-601-    result = session.apply_batch(batch)
tests/test_agent_edit_settings_contract.py-602-
tests/test_agent_edit_settings_contract.py-603-    # The batch should fail overall
tests/test_agent_edit_settings_contract.py-604-    assert result.ok is False
tests/test_agent_edit_settings_contract.py-605-    # The graph should be unchanged from the original
tests/test_agent_edit_settings_contract.py-606-    node = session.working_ui["nodes"][0]
--
tests/test_schema_validate.py-68-    assert issue.detail["node_id"] == "1"
tests/test_schema_validate.py-69-    assert issue.detail["class_type"] == "AceNode"
tests/test_schema_validate.py-70-    assert issue.detail["input"] == "bpm"
tests/test_schema_validate.py-71-    assert issue.detail["value"] == "2"
tests/test_schema_validate.py-72-    assert issue.detail["min"] == 10
tests/test_schema_validate.py-73-    assert issue.detail["max"] is None
tests/test_schema_validate.py-74-
tests/test_schema_validate.py-75-
tests/test_schema_validate.py:76:def test_value_not_in_enum_emits_error() -> None:
tests/test_schema_validate.py-77-    provider = FakeSchemaProvider({"ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("STRING", choices=["a", "b"])})})
tests/test_schema_validate.py-78-    report = _workflow(VibeNode("1", "ChoiceNode", inputs={"mode": "c"})).validate(schema_provider=provider)
tests/test_schema_validate.py-79-
tests/test_schema_validate.py-80-    assert not report.ok
tests/test_schema_validate.py-81-    issue = report.issues[0]
tests/test_schema_validate.py:82:    assert issue.code == "value_not_in_enum"
tests/test_schema_validate.py-83-    assert issue.detail["node_id"] == "1"
tests/test_schema_validate.py-84-    assert issue.detail["class_type"] == "ChoiceNode"
tests/test_schema_validate.py-85-    assert issue.detail["input"] == "mode"
tests/test_schema_validate.py-86-    assert issue.detail["value"] == "'c'"
tests/test_schema_validate.py-87-    assert issue.detail["choices"] == ["a", "b"]
tests/test_schema_validate.py-88-
tests/test_schema_validate.py-89-
tests/test_schema_validate.py-90-def test_dynamic_file_picker_choices_do_not_reject_task_inputs() -> None:
--
tests/test_schema_validate.py-98-        VibeNode("1", "LoadImage", inputs={"image": "task-specific.png"}),
tests/test_schema_validate.py-99-        VibeNode("2", "UNETLoader", inputs={"unet_name": "missing-model.safetensors"}),
tests/test_schema_validate.py-100-    )
tests/test_schema_validate.py-101-
tests/test_schema_validate.py-102-    report = workflow.validate(schema_provider=provider)
tests/test_schema_validate.py-103-
tests/test_schema_validate.py-104-    assert not report.ok
tests/test_schema_validate.py-105-    assert [(issue.code, issue.detail["class_type"], issue.detail["input"]) for issue in report.issues] == [
tests/test_schema_validate.py:106:        ("value_not_in_enum", "UNETLoader", "unet_name")
tests/test_schema_validate.py-107-    ]
tests/test_schema_validate.py-108-
tests/test_schema_validate.py-109-
tests/test_schema_validate.py-110-def test_sanitize_api_strips_unknown_runtime_inputs_and_coerces_portable_choices() -> None:
tests/test_schema_validate.py-111-    provider = FakeSchemaProvider(
tests/test_schema_validate.py-112-        {
tests/test_schema_validate.py-113-            "WanVideoLoraSelect": _schema(
tests/test_schema_validate.py-114-                "WanVideoLoraSelect",
--
tests/test_comfy_nodes_agent_backend_spine.py-2417-                )
tests/test_comfy_nodes_agent_backend_spine.py-2418-            )
tests/test_comfy_nodes_agent_backend_spine.py-2419-        }
tests/test_comfy_nodes_agent_backend_spine.py-2420-    )
tests/test_comfy_nodes_agent_backend_spine.py-2421-
tests/test_comfy_nodes_agent_backend_spine.py-2422-    diagnostics = validate_stage_diagnostics(workflow, schema_provider=provider)
tests/test_comfy_nodes_agent_backend_spine.py-2423-
tests/test_comfy_nodes_agent_backend_spine.py-2424-    assert diagnostics.failure_kind is FailureKind.VALIDATION_ERROR
tests/test_comfy_nodes_agent_backend_spine.py:2425:    assert any(issue["code"] == "value_not_in_enum" for issue in diagnostics.issues)
tests/test_comfy_nodes_agent_backend_spine.py-2426-
tests/test_comfy_nodes_agent_backend_spine.py-2427-
tests/test_comfy_nodes_agent_backend_spine.py-2428-def test_validate_stage_leaves_helper_info_non_blocking() -> None:
tests/test_comfy_nodes_agent_backend_spine.py-2429-    workflow = VibeWorkflow("helper", WorkflowSource("helper"))
tests/test_comfy_nodes_agent_backend_spine.py-2430-    workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "note"})
tests/test_comfy_nodes_agent_backend_spine.py-2431-    workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "a.png"})
tests/test_comfy_nodes_agent_backend_spine.py-2432-    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "img", "IMAGE": ["2", 0]})
tests/test_comfy_nodes_agent_backend_spine.py-2433-    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "img"})
--
tests/test_porting_edit_apply_values.py-45-        ("asset_not_installed", "warning")
tests/test_porting_edit_apply_values.py-46-    ]
tests/test_porting_edit_apply_values.py-47-    assert issues[0].detail["value"] == value
tests/test_porting_edit_apply_values.py-48-
tests/test_porting_edit_apply_values.py-49-
tests/test_porting_edit_apply_values.py-50-@pytest.mark.parametrize(
tests/test_porting_edit_apply_values.py-51-    ("input_name", "value"),
tests/test_porting_edit_apply_values.py-52-    [
tests/test_porting_edit_apply_values.py:53:        ("scheduler", "bogus_scheduler"),
tests/test_porting_edit_apply_values.py-54-        ("model_type", "bogus_model_type"),
tests/test_porting_edit_apply_values.py-55-    ],
tests/test_porting_edit_apply_values.py-56-)
tests/test_porting_edit_apply_values.py-57-def test_validate_constrained_enum_still_rejects_unknown_value(
tests/test_porting_edit_apply_values.py-58-    input_name: str,
tests/test_porting_edit_apply_values.py-59-    value: str,
tests/test_porting_edit_apply_values.py-60-) -> None:
tests/test_porting_edit_apply_values.py-61-    spec = SimpleNamespace(choices=["euler", "dpm++_2m"], type="STRING", min=None, max=None)
tests/test_porting_edit_apply_values.py-62-
tests/test_porting_edit_apply_values.py-63-    issues = _validate(value, spec, input_name=input_name)
tests/test_porting_edit_apply_values.py-64-
tests/test_porting_edit_apply_values.py-65-    assert [(issue.code, issue.severity) for issue in issues] == [
tests/test_porting_edit_apply_values.py:66:        ("value_not_in_enum", "error")
tests/test_porting_edit_apply_values.py-67-    ]
tests/test_porting_edit_apply_values.py-68-
tests/test_porting_edit_apply_values.py-69-
tests/test_porting_edit_apply_values.py-70-def test_validate_asset_enum_does_not_accept_non_string_value() -> None:
tests/test_porting_edit_apply_values.py-71-    spec = SimpleNamespace(choices=["installed.safetensors"], type="lora")
tests/test_porting_edit_apply_values.py-72-
tests/test_porting_edit_apply_values.py-73-    issues = _validate(123, spec, input_name="lora")
tests/test_porting_edit_apply_values.py-74-
tests/test_porting_edit_apply_values.py:75:    assert issues[0].code == "value_not_in_enum"
tests/test_porting_edit_apply_values.py-76-    assert issues[0].severity == "error"
tests/test_porting_edit_apply_values.py-77-
tests/test_porting_edit_apply_values.py-78-
tests/test_porting_edit_apply_values.py-79-def test_apply_values_add_node_keeps_missing_asset_filename_and_warning() -> None:
tests/test_porting_edit_apply_values.py-80-    schema = NodeSchema(
tests/test_porting_edit_apply_values.py-81-        class_type="WanVideoLoraSelect",
tests/test_porting_edit_apply_values.py-82-        pack="test",
tests/test_porting_edit_apply_values.py-83-        inputs={
--
tests/test_schema.py-375-        {"mode": "c", "steps": 9, "enabled": "yes", "extra": True},
tests/test_schema.py-376-        provider,
tests/test_schema.py-377-    )
tests/test_schema.py-378-
tests/test_schema.py-379-    assert report.ok is False
tests/test_schema.py-380-    by_code = {issue.code: issue for issue in report.issues}
tests/test_schema.py-381-    assert by_code["missing_required_input"].input == "required_text"
tests/test_schema.py-382-    assert by_code["unknown_input"].input == "extra"
tests/test_schema.py:383:    assert by_code["value_not_in_enum"].detail["choices"] == ["a", "b"]
tests/test_schema.py-384-    assert by_code["value_out_of_range"].detail["max"] == 4
tests/test_schema.py-385-    assert by_code["primitive_type_mismatch"].detail["expected"] == "bool"
tests/test_schema.py-386-
tests/test_schema.py-387-
tests/test_schema.py-388-def _workflow(*nodes: VibeNode, edges: list[VibeEdge] | None = None) -> VibeWorkflow:
tests/test_schema.py-389-    workflow = VibeWorkflow("schema-test", WorkflowSource("schema-test"))
tests/test_schema.py-390-    workflow.nodes = {node.id: node for node in nodes}
tests/test_schema.py-391-    workflow.edges = edges or []
--
tests/test_porting_edit_corpus.py-331-    assert _node(second.candidate, 2)["widgets_values"] == ["second edit"]
tests/test_porting_edit_corpus.py-332-    _assert_preserves_out_of_delta_nodes(second_before, second.candidate, touched={("", "2")})
tests/test_porting_edit_corpus.py-333-
tests/test_porting_edit_corpus.py-334-
tests/test_porting_edit_corpus.py-335-@pytest.mark.parametrize(
tests/test_porting_edit_corpus.py-336-    ("raw_delta", "expected_code"),
tests/test_porting_edit_corpus.py-337-    [
tests/test_porting_edit_corpus.py-338-        (
tests/test_porting_edit_corpus.py:339:            [{"op": "set_node_field", "target": ["", "5", "sampler_name"], "value": "not-real"}],
tests/test_porting_edit_corpus.py:340:            "value_not_in_enum",
tests/test_porting_edit_corpus.py-341-        ),
tests/test_porting_edit_corpus.py-342-        (
tests/test_porting_edit_corpus.py-343-            [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 1000}],
tests/test_porting_edit_corpus.py-344-            "value_out_of_range",
tests/test_porting_edit_corpus.py-345-        ),
tests/test_porting_edit_corpus.py-346-        (
tests/test_porting_edit_corpus.py-347-            [{"op": "set_node_field", "target": ["", "5", "steps"], "value": "twenty"}],
tests/test_porting_edit_corpus.py-348-            "value_type_mismatch",
--
tests/test_porting_edit_corpus.py-370-
tests/test_porting_edit_corpus.py-371-
tests/test_porting_edit_corpus.py-372-def test_edit_corpus_later_rejection_keeps_earlier_successful_op_atomic() -> None:
tests/test_porting_edit_corpus.py-373-    original = _fixture("flat.json")
tests/test_porting_edit_corpus.py-374-    before = copy.deepcopy(original)
tests/test_porting_edit_corpus.py-375-    delta = parse_edit_delta(
tests/test_porting_edit_corpus.py-376-        [
tests/test_porting_edit_corpus.py-377-            {"op": "set_node_field", "target": ["", "2", "text"], "value": "should not apply"},
tests/test_porting_edit_corpus.py:378:            {"op": "set_node_field", "target": ["", "5", "sampler_name"], "value": "not-real"},
tests/test_porting_edit_corpus.py-379-        ]
tests/test_porting_edit_corpus.py-380-    )
tests/test_porting_edit_corpus.py-381-
tests/test_porting_edit_corpus.py-382-    result = apply_delta(original, delta, schema_provider=_SchemaProvider())
tests/test_porting_edit_corpus.py-383-
tests/test_porting_edit_corpus.py-384-    assert result.ok is False
tests/test_porting_edit_corpus.py-385-    assert result.candidate is None
tests/test_porting_edit_corpus.py-386-    assert result.mutation_started is False
tests/test_porting_edit_corpus.py-387-    assert original == before
tests/test_porting_edit_corpus.py:388:    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
--
tests/test_demo_factory_structural_baseline.py-242-        "credible_non_defaultable_required_input"
tests/test_demo_factory_structural_baseline.py-243-    )
tests/test_demo_factory_structural_baseline.py-244-
tests/test_demo_factory_structural_baseline.py-245-
tests/test_demo_factory_structural_baseline.py-246-def test_asset_enum_warns_but_semantic_enum_is_hard(
tests/test_demo_factory_structural_baseline.py-247-    monkeypatch: pytest.MonkeyPatch,
tests/test_demo_factory_structural_baseline.py-248-) -> None:
tests/test_demo_factory_structural_baseline.py-249-    asset = _diag(
tests/test_demo_factory_structural_baseline.py:250:        "value_not_in_enum",
tests/test_demo_factory_structural_baseline.py-251-        class_type="VAELoader",
tests/test_demo_factory_structural_baseline.py-252-        node_id="1",
tests/test_demo_factory_structural_baseline.py-253-        detail={
tests/test_demo_factory_structural_baseline.py-254-            "input": "vae_name",
tests/test_demo_factory_structural_baseline.py-255-            "value": "remote-only.safetensors",
tests/test_demo_factory_structural_baseline.py-256-            "choice_scope": "environment_asset",
tests/test_demo_factory_structural_baseline.py-257-        },
tests/test_demo_factory_structural_baseline.py-258-    )
tests/test_demo_factory_structural_baseline.py-259-    _report(monkeypatch, [asset])
tests/test_demo_factory_structural_baseline.py-260-    asset_result = structural_check_graph(_connected_graph())
tests/test_demo_factory_structural_baseline.py-261-    assert asset_result["passed"] is True
tests/test_demo_factory_structural_baseline.py-262-    assert asset_result["warnings"][0]["detail"]["structural_reason"] == (
tests/test_demo_factory_structural_baseline.py-263-        "environment_asset_inventory"
tests/test_demo_factory_structural_baseline.py-264-    )
tests/test_demo_factory_structural_baseline.py-265-
tests/test_demo_factory_structural_baseline.py-266-    semantic = _diag(
tests/test_demo_factory_structural_baseline.py:267:        "value_not_in_enum",
tests/test_demo_factory_structural_baseline.py-268-        class_type="KSampler",
tests/test_demo_factory_structural_baseline.py-269-        node_id="1",
tests/test_demo_factory_structural_baseline.py-270-        detail={
tests/test_demo_factory_structural_baseline.py-271-            "input": "sampler_name",
tests/test_demo_factory_structural_baseline.py-272-            "value": "definitely-not-a-sampler",
tests/test_demo_factory_structural_baseline.py-273-            "choice_scope": "semantic",
tests/test_demo_factory_structural_baseline.py-274-        },
tests/test_demo_factory_structural_baseline.py-275-    )
--
tests/test_cli_port.py-307-        )
tests/test_cli_port.py-308-    )
tests/test_cli_port.py-309-
tests/test_cli_port.py-310-    payload = json.loads(capsys.readouterr().out)
tests/test_cli_port.py-311-    codes = {issue["code"] for issue in payload["issues"]}
tests/test_cli_port.py-312-    assert code == 1
tests/test_cli_port.py-313-    assert payload["status"] == "error"
tests/test_cli_port.py-314-    assert payload["provider"] == "AuthoringSchemaProvider"
tests/test_cli_port.py:315:    assert {"missing_required_input", "unknown_input", "value_not_in_enum", "value_out_of_range", "primitive_type_mismatch"} <= codes
tests/test_cli_port.py-316-
tests/test_cli_port.py-317-
tests/test_cli_port.py-318-def test_port_validate_call_success_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
tests/test_cli_port.py-319-    code = _cmd_port_validate_call(
tests/test_cli_port.py-320-        argparse.Namespace(
tests/test_cli_port.py-321-            class_type="SaveImage",
tests/test_cli_port.py-322-            kwargs=json.dumps({"images": ["1", 0], "filename_prefix": "out/test"}),
tests/test_cli_port.py-323-            json=True,
--
tests/test_cli_port.py-352-    payload = json.loads(result.stdout)
tests/test_cli_port.py-353-    assert result.returncode == 1
tests/test_cli_port.py-354-    assert any(issue["code"] == "primitive_type_mismatch" for issue in payload["issues"])
tests/test_cli_port.py-355-
tests/test_cli_port.py-356-
tests/test_cli_port.py-357-@pytest.mark.parametrize(
tests/test_cli_port.py-358-    ("kwargs", "expected_code", "expected_input"),
tests/test_cli_port.py-359-    [
tests/test_cli_port.py:360:        ({"sampler_name": "not-a-sampler"}, "value_not_in_enum", "sampler_name"),
tests/test_cli_port.py-361-        ({}, "missing_required_input", "model"),
tests/test_cli_port.py-362-        ({"unknown_knob": 1}, "unknown_input", "unknown_knob"),
tests/test_cli_port.py-363-        ({"steps": 999999}, "value_out_of_range", "steps"),
tests/test_cli_port.py-364-        ({"seed": "12"}, "primitive_type_mismatch", "seed"),
tests/test_cli_port.py-365-    ],
tests/test_cli_port.py-366-)
tests/test_cli_port.py-367-def test_port_validate_call_subprocess_reports_stable_error_fields(
tests/test_cli_port.py-368-    kwargs: dict[str, object],
--
tests/test_comfy_nodes_agent_edit.py-16339-                            "turn_number": 0,
tests/test_comfy_nodes_agent_edit.py-16340-                            "batch_ok": False,
tests/test_comfy_nodes_agent_edit.py-16341-                            "message": "I'll load ae.safetensors and wire a VAEDecode.",
tests/test_comfy_nodes_agent_edit.py-16342-                            "batch": "vae = VAELoader(vae_name='ae.safetensors')",
tests/test_comfy_nodes_agent_edit.py-16343-                            "diff": "HUGE DIFF " * 1000,  # bulky → must be dropped
tests/test_comfy_nodes_agent_edit.py-16344-                            "statements": [{"x": 1}],  # bulky → must be dropped
tests/test_comfy_nodes_agent_edit.py-16345-                            "diagnostics": [
tests/test_comfy_nodes_agent_edit.py-16346-                                {
tests/test_comfy_nodes_agent_edit.py:16347:                                    "code": "value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py-16348-                                    "severity": "error",
tests/test_comfy_nodes_agent_edit.py-16349-                                    "message": "value 'ae.safetensors' is not in the declared enum.",
tests/test_comfy_nodes_agent_edit.py-16350-                                    "detail": {
tests/test_comfy_nodes_agent_edit.py-16351-                                        "input": "vae_name",
tests/test_comfy_nodes_agent_edit.py-16352-                                        "value": "ae.safetensors",
tests/test_comfy_nodes_agent_edit.py-16353-                                        "choices": ["pixel_space"],
tests/test_comfy_nodes_agent_edit.py-16354-                                    },
tests/test_comfy_nodes_agent_edit.py-16355-                                }
--
tests/test_comfy_nodes_agent_edit.py-16374-    assert step["batch_ok"] is False
tests/test_comfy_nodes_agent_edit.py-16375-    assert "ae.safetensors" in step["message"]
tests/test_comfy_nodes_agent_edit.py-16376-    assert "VAELoader" in step["batch"]
tests/test_comfy_nodes_agent_edit.py-16377-    # Bulky fields are trimmed out entirely.
tests/test_comfy_nodes_agent_edit.py-16378-    assert "diff" not in step
tests/test_comfy_nodes_agent_edit.py-16379-    assert "statements" not in step
tests/test_comfy_nodes_agent_edit.py-16380-    # The root-cause diagnostic and the valid enum choices survive.
tests/test_comfy_nodes_agent_edit.py-16381-    diag = step["diagnostics"][0]
tests/test_comfy_nodes_agent_edit.py:16382:    assert diag["code"] == "value_not_in_enum"
tests/test_comfy_nodes_agent_edit.py-16383-    assert diag["detail"]["choices"] == ["pixel_space"]
tests/test_comfy_nodes_agent_edit.py-16384-
tests/test_comfy_nodes_agent_edit.py-16385-
tests/test_comfy_nodes_agent_edit.py-16386-def test_read_session_bundle_bundles_text_and_binary_artifacts(tmp_path: Path) -> None:
tests/test_comfy_nodes_agent_edit.py-16387-    """read_session_bundle returns every artifact under a session dir.
tests/test_comfy_nodes_agent_edit.py-16388-
tests/test_comfy_nodes_agent_edit.py-16389-    This is an explicit raw debug/report retention surface, not a normal public
tests/test_comfy_nodes_agent_edit.py-16390-    renderer payload. It intentionally remains exempt from
--
tests/test_comfy_nodes_agent_edit.py-16758-
tests/test_comfy_nodes_agent_edit.py-16759-def test_format_batch_report_includes_enum_choices_in_detail() -> None:
tests/test_comfy_nodes_agent_edit.py-16760-    """Enum failure diagnostics include valid choices in text feedback."""
tests/test_comfy_nodes_agent_edit.py-16761-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
tests/test_comfy_nodes_agent_edit.py-16762-    from vibecomfy.porting.edit.session import BatchResult, StatementResult
tests/test_comfy_nodes_agent_edit.py-16763-    from vibecomfy.porting.edit._session_types import CompactDiagnostic
tests/test_comfy_nodes_agent_edit.py-16764-
tests/test_comfy_nodes_agent_edit.py-16765-    diag = CompactDiagnostic(
tests/test_comfy_nodes_agent_edit.py:16766:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py-16767-        message="value 'bad' is not in the declared enum.",
tests/test_comfy_nodes_agent_edit.py-16768-        severity="error",
tests/test_comfy_nodes_agent_edit.py-16769-        detail={"class_type": "KSampler", "input": "sampler_name", "value": "bad", "choices": ["euler", "heun", "dpmpp_2m"]},
tests/test_comfy_nodes_agent_edit.py-16770-    )
tests/test_comfy_nodes_agent_edit.py-16771-    br = BatchResult(
tests/test_comfy_nodes_agent_edit.py-16772-        ok=False,
tests/test_comfy_nodes_agent_edit.py-16773-        statements=(
tests/test_comfy_nodes_agent_edit.py-16774-            StatementResult(
--
tests/test_comfy_nodes_agent_edit.py-16778-                landed=False,
tests/test_comfy_nodes_agent_edit.py-16779-                op_kind="set_node_field",
tests/test_comfy_nodes_agent_edit.py-16780-                diagnostics=(diag,),
tests/test_comfy_nodes_agent_edit.py-16781-            ),
tests/test_comfy_nodes_agent_edit.py-16782-        ),
tests/test_comfy_nodes_agent_edit.py-16783-        diagnostics=(),
tests/test_comfy_nodes_agent_edit.py-16784-    )
tests/test_comfy_nodes_agent_edit.py-16785-    report = _format_batch_report(br, consecutive_errors=1, budget_remaining=3)
tests/test_comfy_nodes_agent_edit.py:16786:    assert "value_not_in_enum" in report
tests/test_comfy_nodes_agent_edit.py-16787-    assert "choices: [" in report
tests/test_comfy_nodes_agent_edit.py-16788-    assert "'euler'" in report
tests/test_comfy_nodes_agent_edit.py-16789-    assert "'heun'" in report
tests/test_comfy_nodes_agent_edit.py-16790-    assert "'dpmpp_2m'" in report
tests/test_comfy_nodes_agent_edit.py-16791-
tests/test_comfy_nodes_agent_edit.py-16792-
tests/test_comfy_nodes_agent_edit.py-16793-def test_format_batch_report_includes_valid_fields_for_unknown_field() -> None:
tests/test_comfy_nodes_agent_edit.py-16794-    """Unknown-field failure diagnostics include valid_fields in text feedback."""
--
tests/test_comfy_nodes_agent_edit.py-16833-def test_format_batch_report_detail_caps_long_lists() -> None:
tests/test_comfy_nodes_agent_edit.py-16834-    """Diagnostic detail lists are capped at _DETAIL_LIST_CAP entries."""
tests/test_comfy_nodes_agent_edit.py-16835-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
tests/test_comfy_nodes_agent_edit.py-16836-    from vibecomfy.porting.edit.session import BatchResult, StatementResult
tests/test_comfy_nodes_agent_edit.py-16837-    from vibecomfy.porting.edit._session_types import CompactDiagnostic
tests/test_comfy_nodes_agent_edit.py-16838-
tests/test_comfy_nodes_agent_edit.py-16839-    many_choices = [f"choice_{i}" for i in range(20)]
tests/test_comfy_nodes_agent_edit.py-16840-    diag = CompactDiagnostic(
tests/test_comfy_nodes_agent_edit.py:16841:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py-16842-        message="value 'x' is not in the declared enum.",
tests/test_comfy_nodes_agent_edit.py-16843-        severity="error",
tests/test_comfy_nodes_agent_edit.py-16844-        detail={"class_type": "Test", "input": "f", "value": "x", "choices": many_choices},
tests/test_comfy_nodes_agent_edit.py-16845-    )
tests/test_comfy_nodes_agent_edit.py-16846-    br = BatchResult(
tests/test_comfy_nodes_agent_edit.py-16847-        ok=False,
tests/test_comfy_nodes_agent_edit.py-16848-        statements=(
tests/test_comfy_nodes_agent_edit.py-16849-            StatementResult(
--
tests/test_comfy_nodes_agent_edit.py-16899-
tests/test_comfy_nodes_agent_edit.py-16900-def test_format_batch_report_batch_level_detail() -> None:
tests/test_comfy_nodes_agent_edit.py-16901-    """Batch-level diagnostics also include capped detail text."""
tests/test_comfy_nodes_agent_edit.py-16902-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
tests/test_comfy_nodes_agent_edit.py-16903-    from vibecomfy.porting.edit.session import BatchResult
tests/test_comfy_nodes_agent_edit.py-16904-    from vibecomfy.porting.edit._session_types import CompactDiagnostic
tests/test_comfy_nodes_agent_edit.py-16905-
tests/test_comfy_nodes_agent_edit.py-16906-    diag = CompactDiagnostic(
tests/test_comfy_nodes_agent_edit.py:16907:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py-16908-        message="value 'bad' is not in the declared enum.",
tests/test_comfy_nodes_agent_edit.py-16909-        severity="error",
tests/test_comfy_nodes_agent_edit.py-16910-        detail={"class_type": "Test", "input": "f", "value": "bad", "choices": ["a", "b", "c"]},
tests/test_comfy_nodes_agent_edit.py-16911-    )
tests/test_comfy_nodes_agent_edit.py-16912-    br = BatchResult(
tests/test_comfy_nodes_agent_edit.py-16913-        ok=False,
tests/test_comfy_nodes_agent_edit.py-16914-        statements=(),
tests/test_comfy_nodes_agent_edit.py-16915-        diagnostics=(diag,),
tests/test_comfy_nodes_agent_edit.py-16916-    )
tests/test_comfy_nodes_agent_edit.py-16917-    report = _format_batch_report(br, consecutive_errors=1, budget_remaining=3)
tests/test_comfy_nodes_agent_edit.py:16918:    assert "value_not_in_enum" in report
tests/test_comfy_nodes_agent_edit.py-16919-    assert "detail: " in report
tests/test_comfy_nodes_agent_edit.py-16920-    assert "choices: [" in report
tests/test_comfy_nodes_agent_edit.py-16921-
tests/test_comfy_nodes_agent_edit.py-16922-
tests/test_comfy_nodes_agent_edit.py-16923-def test_format_batch_report_detail_stable_ordering() -> None:
tests/test_comfy_nodes_agent_edit.py-16924-    """Detail keys are rendered in stable order regardless of dict insertion order."""
tests/test_comfy_nodes_agent_edit.py-16925-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report
tests/test_comfy_nodes_agent_edit.py-16926-    from vibecomfy.porting.edit.session import BatchResult, StatementResult
--
tests/test_comfy_nodes_agent_edit.py-16996-def test_format_batch_report_json_caps_detail_lists() -> None:
tests/test_comfy_nodes_agent_edit.py-16997-    """JSON report caps detail list values at _DETAIL_LIST_CAP."""
tests/test_comfy_nodes_agent_edit.py-16998-    from vibecomfy.comfy_nodes.agent.edit import _format_batch_report_json
tests/test_comfy_nodes_agent_edit.py-16999-    from vibecomfy.porting.edit.session import BatchResult
tests/test_comfy_nodes_agent_edit.py-17000-    from vibecomfy.porting.edit._session_types import CompactDiagnostic
tests/test_comfy_nodes_agent_edit.py-17001-
tests/test_comfy_nodes_agent_edit.py-17002-    many_choices = [f"choice_{i}" for i in range(15)]
tests/test_comfy_nodes_agent_edit.py-17003-    diag = CompactDiagnostic(
tests/test_comfy_nodes_agent_edit.py:17004:        code="value_not_in_enum",
tests/test_comfy_nodes_agent_edit.py-17005-        message="value 'x' is not in the declared enum.",
tests/test_comfy_nodes_agent_edit.py-17006-        severity="error",
tests/test_comfy_nodes_agent_edit.py-17007-        detail={"choices": many_choices},
tests/test_comfy_nodes_agent_edit.py-17008-    )
tests/test_comfy_nodes_agent_edit.py-17009-    br = BatchResult(
tests/test_comfy_nodes_agent_edit.py-17010-        ok=False,
tests/test_comfy_nodes_agent_edit.py-17011-        statements=(),
tests/test_comfy_nodes_agent_edit.py-17012-        diagnostics=(diag,),
--
tests/test_porting_edit_apply.py-308-                "value": "not-a-real-sampler",
tests/test_porting_edit_apply.py-309-            }
tests/test_porting_edit_apply.py-310-        ]
tests/test_porting_edit_apply.py-311-    )
tests/test_porting_edit_apply.py-312-
tests/test_porting_edit_apply.py-313-    result = resolve_delta(original, delta, schema_provider=provider)
tests/test_porting_edit_apply.py-314-
tests/test_porting_edit_apply.py-315-    assert result.ok is False
tests/test_porting_edit_apply.py:316:    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
tests/test_porting_edit_apply.py-317-    assert result.resolved_ops == ()
tests/test_porting_edit_apply.py-318-    assert original == before
tests/test_porting_edit_apply.py-319-
tests/test_porting_edit_apply.py-320-
tests/test_porting_edit_apply.py-321-def test_resolve_delta_rejects_known_incompatible_link_without_mutating_original() -> None:
tests/test_porting_edit_apply.py-322-    original = _fixture()
tests/test_porting_edit_apply.py-323-    before = copy.deepcopy(original)
tests/test_porting_edit_apply.py-324-    provider = _SchemaProvider()
--
tests/test_porting_edit_apply.py-1061-                "value": "sometimes",
tests/test_porting_edit_apply.py-1062-            }
tests/test_porting_edit_apply.py-1063-        ]
tests/test_porting_edit_apply.py-1064-    )
tests/test_porting_edit_apply.py-1065-
tests/test_porting_edit_apply.py-1066-    result = apply_delta(original, delta, schema_provider=_SchemaProvider())
tests/test_porting_edit_apply.py-1067-
tests/test_porting_edit_apply.py-1068-    assert result.ok is False
tests/test_porting_edit_apply.py:1069:    issue = next(issue for issue in result.diagnostics if issue.code == "value_not_in_enum")
tests/test_porting_edit_apply.py-1070-    assert issue.detail["choices"] == ["fixed", "randomize", "increment", "decrement"]
tests/test_porting_edit_apply.py-1071-
tests/test_porting_edit_apply.py-1072-
tests/test_porting_edit_apply.py-1073-def test_apply_delta_adds_node_with_ledger_ids_and_collision_nudging() -> None:
tests/test_porting_edit_apply.py-1074-    original = _fixture()
tests/test_porting_edit_apply.py-1075-    provider = _SchemaProvider()
tests/test_porting_edit_apply.py-1076-    delta = parse_edit_delta(
tests/test_porting_edit_apply.py-1077-        [

exec
/bin/zsh -lc "git diff --unified=12 f2661b01..ff6ae9c8 -- tests/test_comfy_nodes_agent_edit.py | rg -n -C12 'enum|invalid|mutation|add_node|set_node_field|asset'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 441ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
77-+
78-+def _b04_provisional_candidate(
79-+    *class_types: str,
80-+    validation_mode: str = "registry",
81-+) -> dict[str, Any]:
82-+    """Resolver-candidate dict shape consumed by ProvisionalRegistrySchemaProvider.
83-+
84-+    Carries only positional widget_N names and empty choices — exactly the weak
85-+    evidence that must never shadow a real semantic schema.
86-+    """
87-+    nodes = {
88-+        class_type: _b04_provisional_node(class_type, index)
89:+        for index, class_type in enumerate(class_types)
90-+    }
91-+    candidate: dict[str, Any] = {
92-+        "stable_install_hash": f"b04:{','.join(class_types)}",
93-+        "provisional_schema": {"schema": {"nodes": nodes}, "version": "1.0.0"},
94-+        "expected_classes": list(class_types),
95-+    }
96-+    if validation_mode == "workflow":
97-+        candidate["validation_mode"] = "workflow_json_provisional"
98-+    return candidate
99-+
100-+
101-+def _assert_b04_real_first(provider: Any, *, gap_source: str) -> None:

exec
/bin/zsh -lc "rg -n -C8 '\"fields\": \\{["'^'"\\n]*(sampler_name|scheduler|mode)|fields=\\{["'^'"\\n]*(sampler_name|scheduler|mode)' tests --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 597ms:
tests/test_porting_edit_apply.py-393-    before = copy.deepcopy(original)
tests/test_porting_edit_apply.py-394-    provider = _SchemaProvider()
tests/test_porting_edit_apply.py-395-    delta = parse_edit_delta(
tests/test_porting_edit_apply.py-396-        [
tests/test_porting_edit_apply.py-397-            {
tests/test_porting_edit_apply.py-398-                "op": "add_node",
tests/test_porting_edit_apply.py-399-                "scope_path": "",
tests/test_porting_edit_apply.py-400-                "class_type": "KSampler",
tests/test_porting_edit_apply.py:401:                "fields": {"denoise": 1.5, "sampler_name": "euler"},
tests/test_porting_edit_apply.py-402-                "inputs": {},
tests/test_porting_edit_apply.py-403-            }
tests/test_porting_edit_apply.py-404-        ]
tests/test_porting_edit_apply.py-405-    )
tests/test_porting_edit_apply.py-406-
tests/test_porting_edit_apply.py-407-    result = resolve_delta(original, delta, schema_provider=provider)
tests/test_porting_edit_apply.py-408-
tests/test_porting_edit_apply.py-409-    assert result.ok is False
--
tests/test_porting_edit_apply.py-434-        ]
tests/test_porting_edit_apply.py-435-    )
tests/test_porting_edit_apply.py-436-    invalid_delta = parse_edit_delta(
tests/test_porting_edit_apply.py-437-        [
tests/test_porting_edit_apply.py-438-            {
tests/test_porting_edit_apply.py-439-                "op": "add_node",
tests/test_porting_edit_apply.py-440-                "scope_path": "",
tests/test_porting_edit_apply.py-441-                "class_type": "KSampler",
tests/test_porting_edit_apply.py:442:                "fields": {"model": "checkpoint.safetensors", "seed": 7},
tests/test_porting_edit_apply.py-443-                "inputs": {},
tests/test_porting_edit_apply.py-444-            }
tests/test_porting_edit_apply.py-445-        ]
tests/test_porting_edit_apply.py-446-    )
tests/test_porting_edit_apply.py-447-
tests/test_porting_edit_apply.py-448-    valid = resolve_delta(copy.deepcopy(original), valid_delta, schema_provider=provider)
tests/test_porting_edit_apply.py-449-    invalid = resolve_delta(copy.deepcopy(original), invalid_delta, schema_provider=provider)
tests/test_porting_edit_apply.py-450-
--
tests/test_porting_edit_apply.py-488-    original = _fixture()
tests/test_porting_edit_apply.py-489-    provider = _WidgetOnlySchemaProvider()
tests/test_porting_edit_apply.py-490-    delta = parse_edit_delta(
tests/test_porting_edit_apply.py-491-        [
tests/test_porting_edit_apply.py-492-            {
tests/test_porting_edit_apply.py-493-                "op": "add_node",
tests/test_porting_edit_apply.py-494-                "scope_path": "",
tests/test_porting_edit_apply.py-495-                "class_type": "ImageBlend",
tests/test_porting_edit_apply.py:496:                "fields": {"blend_factor": 0.25, "blend_mode": "multiply"},
tests/test_porting_edit_apply.py-497-                "inputs": {},
tests/test_porting_edit_apply.py-498-            }
tests/test_porting_edit_apply.py-499-        ]
tests/test_porting_edit_apply.py-500-    )
tests/test_porting_edit_apply.py-501-
tests/test_porting_edit_apply.py-502-    result = apply_delta(original, delta, schema_provider=provider)
tests/test_porting_edit_apply.py-503-
tests/test_porting_edit_apply.py-504-    assert result.ok is True

exec
/bin/zsh -lc "nl -ba tests/test_porting_edit_apply.py | sed -n '370,425p'; rg -n 'def _resolve_add|add_node rejected|context=.*add|_validate_literal_value' vibecomfy/porting/edit -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 374ms:
   370	    provider = _SchemaProvider()
   371	    delta = parse_edit_delta(
   372	        [
   373	            {
   374	                "op": "add_node",
   375	                "scope_path": "",
   376	                "class_type": "TotallyUnknownNode",
   377	                "fields": {"filename_prefix": "out/run"},
   378	                "inputs": {},
   379	            }
   380	        ]
   381	    )
   382
   383	    result = resolve_delta(original, delta, schema_provider=provider)
   384
   385	    assert result.ok is False
   386	    assert any(issue.code == "unknown_add_node_class_type" for issue in result.diagnostics)
   387	    assert result.resolved_ops == ()
   388	    assert original == before
   389
   390
   391	def test_resolve_delta_rejects_add_node_out_of_range_field_before_any_mutation() -> None:
   392	    original = _fixture()
   393	    before = copy.deepcopy(original)
   394	    provider = _SchemaProvider()
   395	    delta = parse_edit_delta(
   396	        [
   397	            {
   398	                "op": "add_node",
   399	                "scope_path": "",
   400	                "class_type": "KSampler",
   401	                "fields": {"denoise": 1.5, "sampler_name": "euler"},
   402	                "inputs": {},
   403	            }
   404	        ]
   405	    )
   406
   407	    result = resolve_delta(original, delta, schema_provider=provider)
   408
   409	    assert result.ok is False
   410	    assert any(issue.code == "value_out_of_range" for issue in result.diagnostics)
   411	    assert result.resolved_ops == ()
   412	    assert original == before
   413
   414
   415	def test_resolve_delta_accepts_ksampler_widget_fields_but_not_socket_literals() -> None:
   416	    original = _fixture()
   417	    provider = _SchemaProvider()
   418	    valid_delta = parse_edit_delta(
   419	        [
   420	            {
   421	                "op": "add_node",
   422	                "scope_path": "",
   423	                "class_type": "KSampler",
   424	                "fields": {
   425	                    "seed": 7,
vibecomfy/porting/edit/_resolve.py:983:    def _resolve_add_node_statement(
vibecomfy/porting/edit/_resolve.py:1050:    def _resolve_add_node_call(
vibecomfy/porting/edit/apply_resolve_add.py:30:from vibecomfy.porting.edit.apply_values import _validate_literal_value
vibecomfy/porting/edit/apply_resolve_add.py:39:def _resolve_add_node(
vibecomfy/porting/edit/apply_resolve_add.py:199:            _validate_literal_value(
vibecomfy/porting/edit/apply_resolve_add.py:204:                context="add_node",
vibecomfy/porting/edit/apply_resolve_add.py:333:        validation_issues = _validate_literal_value(
vibecomfy/porting/edit/apply_resolve_add.py:571:def _resolve_add_node_anchor(
vibecomfy/porting/edit/apply.py:139:    _validate_literal_value,
vibecomfy/porting/edit/apply_values.py:12:def _validate_literal_value(
vibecomfy/porting/edit/apply_resolve_base.py:34:from vibecomfy.porting.edit.apply_values import _validate_literal_value
vibecomfy/porting/edit/apply_resolve_base.py:335:    value_issues = _validate_literal_value(
vibecomfy/porting/edit/apply_resolve_base.py:393:            old_value_issues = _validate_literal_value(

exec
/bin/zsh -lc "rg -n 'sampler_name|scheduler|choices=' tests/test_porting_edit_apply.py | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 348ms:
42:                    "sampler_name": InputSpec(type="STRING", choices=["euler", "heun"]),
43:                    "scheduler": InputSpec(type="STRING", choices=["normal", "karras"]),
112:                    "widget_1": InputSpec(type="STRING", choices=["normal", "multiply"]),
307:                "target": ["", "5", "sampler_name"],
401:                "fields": {"denoise": 1.5, "sampler_name": "euler"},
428:                    "sampler_name": "euler",
429:                    "scheduler": "normal",
669:    for compact_name in ("seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
726:    for compact_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
753:    for compact_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
789:    for name in ("seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
821:    for name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):

exec
/bin/zsh -lc "git log --all --oneline -S'value_not_in_enum' -- tests | head -30; git log --all --oneline --grep='schema authority\\|enum' -20" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 5051ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8ad7e9a2 consolidate: checkpoint agent-edit robustness v2 work onto main-track
ef52fc0c Agent-edit robustness: multi-node/debug/additive campaigns + failure analysis + splice-pipeline design
e3e46c0f sprint-2: megaplan milestone (#139)
390fbbf8 Fix agent edit randomize sampler control
9eb3d6be agent-edit: self-contained issue-report zip + surfaced agent reasoning
760de980 agent-edit-v2: faithful op-based graph editing (build complete)
859642cc s1-apply-safe-backend: megaplan milestone (#38)
d7932b01 Run pristine cleanup epic
bed1b3ab megaplan: v2-7-sprint-4-type-safety-20260521-2230 execute
03188158 Allow dynamic task file inputs in schema validation
b60bef0a feat: object_info pre-submit validator as a real gate
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
fa06a300 megado: consolidate quick wins into G0 gate (own checkpoint + STOP + flip verification); renumber B03..B11 -> B01..B08
6ac560fa docs: correct MalformedModelJSON enumeration (13 persisted)
fa385a07 docs: append scenario enumerations (54 failed, 9 matcher-only, 14 malformed)
b984cc74 fix(executor): drop unsupported adaptation_plan kwarg in reply fallback (#95)
5f10a77d M5: agentic-suite route-intent map and safety tests (#94)
d96fcde2 agent-edit: surface combo enum values + output slot names in signatures
9eb3d6be agent-edit: self-contained issue-report zip + surfaced agent reasoning
16db45f8 m1-edit-state-authority: megaplan milestone (#51)
75661639 agent-edit: fix StaleStateMismatch round-trip + self-healing baseline + complete-edit done-guard
4274eaa4 m5-preserve-roundtrip: megaplan milestone (#31)
6ae229a6 Document the wrapper codegen pipeline and add a demo script
5189128d Re-emit 5 runexx Family P templates through current emitter
b60bef0a feat: object_info pre-submit validator as a real gate

exec
/bin/zsh -lc "rg -n -C8 'enum regressions|Real-schema authority|widget_N|provisional-first' .oracle --glob '*.md' --glob '*.txt'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 995ms:
.oracle/plan.md-128-- Source-workflow hashes resolve before D13 passes.
.oracle/plan.md-129-
.oracle/plan.md-130-### Oracle checkpoint
.oracle/plan.md-131-
.oracle/plan.md-132-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
.oracle/plan.md-133-
.oracle/plan.md-134----
.oracle/plan.md-135-
.oracle/plan.md:136:## B04 — Real-schema authority
.oracle/plan.md-137-
.oracle/plan.md-138-### Tasks
.oracle/plan.md-139-
.oracle/plan.md-140-1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/plan.md:141:2. Migrate all four verified provisional-first sites:
.oracle/plan.md-142-   - `_frag_research.py:874`;
.oracle/plan.md-143-   - `_frag_response_contract.py:793`;
.oracle/plan.md-144-   - `_frag_batch_loop.py:910`;
.oracle/plan.md-145-   - `edit_batch_repl.py:1115`.
.oracle/plan.md-146-3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
.oracle/plan.md-147-4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
.oracle/plan.md:148:5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/plan.md-149-
.oracle/plan.md-150-### Acceptance
.oracle/plan.md-151-
.oracle/plan.md-152-- All seven sites are real-first.
.oracle/plan.md-153-- Session schema authority remains real-first across turns.
.oracle/plan.md:154:- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/plan.md-155-- Invalid enum values are rejected before mutation for add and set.
.oracle/plan.md-156-- Missing local asset filenames remain warning-only.
.oracle/plan.md-157-
.oracle/plan.md-158-### Oracle checkpoint
.oracle/plan.md-159-
.oracle/plan.md-160-Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.
.oracle/plan.md-161-
.oracle/plan.md-162----
--
.oracle/tasklist.md-128-- Source-workflow hashes resolve before D13 passes.
.oracle/tasklist.md-129-
.oracle/tasklist.md-130-### Oracle checkpoint
.oracle/tasklist.md-131-
.oracle/tasklist.md-132-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
.oracle/tasklist.md-133-
.oracle/tasklist.md-134----
.oracle/tasklist.md-135-
.oracle/tasklist.md:136:## B04 — Real-schema authority
.oracle/tasklist.md-137-
.oracle/tasklist.md-138-### Tasks
.oracle/tasklist.md-139-
.oracle/tasklist.md-140-1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/tasklist.md:141:2. Migrate all four verified provisional-first sites:
.oracle/tasklist.md-142-   - `_frag_research.py:874`;
.oracle/tasklist.md-143-   - `_frag_response_contract.py:793`;
.oracle/tasklist.md-144-   - `_frag_batch_loop.py:910`;
.oracle/tasklist.md-145-   - `edit_batch_repl.py:1115`.
.oracle/tasklist.md-146-3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
.oracle/tasklist.md-147-4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
.oracle/tasklist.md:148:5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/tasklist.md-149-
.oracle/tasklist.md-150-### Acceptance
.oracle/tasklist.md-151-
.oracle/tasklist.md-152-- All seven sites are real-first.
.oracle/tasklist.md-153-- Session schema authority remains real-first across turns.
.oracle/tasklist.md:154:- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/tasklist.md-155-- Invalid enum values are rejected before mutation for add and set.
.oracle/tasklist.md-156-- Missing local asset filenames remain warning-only.
.oracle/tasklist.md-157-
.oracle/tasklist.md-158-### Oracle checkpoint
.oracle/tasklist.md-159-
.oracle/tasklist.md-160-Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.
.oracle/tasklist.md-161-
.oracle/tasklist.md-162----
--
.oracle/briefs-legacy/batch-B04.md:1:# B04 — Real-schema authority and apply-time combo validation
.oracle/briefs-legacy/batch-B04.md-2-
.oracle/briefs-legacy/batch-B04.md-3-Executor: DeepSeek V4 Flash (normal executor).
.oracle/briefs-legacy/batch-B04.md-4-Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
.oracle/briefs-legacy/batch-B04.md-5-Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.
.oracle/briefs-legacy/batch-B04.md-6-
.oracle/briefs-legacy/batch-B04.md-7-## Tasks
.oracle/briefs-legacy/batch-B04.md-8-
.oracle/briefs-legacy/batch-B04.md-9-1. Put real schemas before provisional evidence everywhere.
--
.oracle/checkins/batch-D13.md-268-- Source-workflow hashes resolve before D13 passes.
.oracle/checkins/batch-D13.md-269-
.oracle/checkins/batch-D13.md-270-### Oracle checkpoint
.oracle/checkins/batch-D13.md-271-
.oracle/checkins/batch-D13.md-272-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
.oracle/checkins/batch-D13.md-273-
.oracle/checkins/batch-D13.md-274----
.oracle/checkins/batch-D13.md-275-
.oracle/checkins/batch-D13.md:276:## B04 — Real-schema authority
.oracle/checkins/batch-D13.md-277-
.oracle/checkins/batch-D13.md-278-### Tasks
.oracle/checkins/batch-D13.md-279-
.oracle/checkins/batch-D13.md-280-1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/checkins/batch-D13.md:281:2. Migrate all four verified provisional-first sites:
.oracle/checkins/batch-D13.md-282-   - `_frag_research.py:874`;
.oracle/checkins/batch-D13.md-283-   - `_frag_response_contract.py:793`;
.oracle/checkins/batch-D13.md-284-   - `_frag_batch_loop.py:910`;
.oracle/checkins/batch-D13.md-285-   - `edit_batch_repl.py:1115`.
.oracle/checkins/batch-D13.md-286-3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
.oracle/checkins/batch-D13.md-287-4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
.oracle/checkins/batch-D13.md:288:5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/checkins/batch-D13.md-289-
.oracle/checkins/batch-D13.md-290-### Acceptance
.oracle/checkins/batch-D13.md-291-
.oracle/checkins/batch-D13.md-292-- All seven sites are real-first.
.oracle/checkins/batch-D13.md-293-- Session schema authority remains real-first across turns.
.oracle/checkins/batch-D13.md:294:- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/checkins/batch-D13.md-295-- Invalid enum values are rejected before mutation for add and set.
.oracle/checkins/batch-D13.md-296-- Missing local asset filenames remain warning-only.
.oracle/checkins/batch-D13.md-297-
.oracle/checkins/batch-D13.md-298-### Oracle checkpoint
.oracle/checkins/batch-D13.md-299-
.oracle/checkins/batch-D13.md-300-Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.
.oracle/checkins/batch-D13.md-301-
.oracle/checkins/batch-D13.md-302----
--
.oracle/checkins/batch-D13.md-2613-   401	    schema_context = _schema_context_from_payload(implementation_payload) or {}
.oracle/checkins/batch-D13.md-2614-   402	    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
.oracle/checkins/batch-D13.md-2615-   403	    if dataflow_context:
.oracle/checkins/batch-D13.md-2616-   404	        schema_context["dataflow_context"] = dataflow_context
.oracle/checkins/batch-D13.md-2617-   405	    if schema_context:
.oracle/checkins/batch-D13.md-2618-   406	        system_prompt = (
.oracle/checkins/batch-D13.md-2619-   407	            system_prompt.rstrip()
.oracle/checkins/batch-D13.md-2620-   408	            + "\n\n## Schema and widget evidence\n"
.oracle/checkins/batch-D13.md:2621:   409	            "When schema_context is provided, use it to map opaque widget_N fields "
.oracle/checkins/batch-D13.md-2622-   410	            "to semantic input names. Treat literal widget values as static node "
.oracle/checkins/batch-D13.md-2623-   411	            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
.oracle/checkins/batch-D13.md-2624-   412	            "widget's meaning from index order when compiled_api names are available. "
.oracle/checkins/batch-D13.md-2625-   413	            "If a static widget containing stale or fabricated text is removed while "
.oracle/checkins/batch-D13.md-2626-   414	            "the relevant linked dynamic input path remains connected, do not treat "
.oracle/checkins/batch-D13.md-2627-   415	            "that removal as deleting the dynamic dataflow."
.oracle/checkins/batch-D13.md-2628-   416	        )
.oracle/checkins/batch-D13.md-2629-   417	    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
--
.oracle/checkins/G0.md-620-
.oracle/checkins/G0.md-621-### G0-T4 — Evidence plumbing at classify+reply (cheap half of plan item 11)
.oracle/checkins/G0.md-622-
.oracle/checkins/G0.md-623-- Touch: `vibecomfy/comfy_nodes/agent/worker.py`, `vibecomfy/comfy_nodes/agent/provider.py`, `vibecomfy/executor/core.py` (classify/reply paths).
.oracle/checkins/G0.md-624-- Persist bounded raw preview, `parse_reason`, finish reason, observed usage, model, phase, and endpoint — the same evidence batch-repl already preserves (`edit_batch_repl.py:254-262`, `1538/1553/1575/1582-1587/1607-1610`). Also stop writing the fake `respond_only` classification when classify raises.
.oracle/checkins/G0.md-625-
.oracle/checkins/G0.md-626-### G0-R1 — Rider: one-line schema-precedence swap (from plan item 7)
.oracle/checkins/G0.md-627-
.oracle/checkins/G0.md:628:- Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py:821` — `CompositeSchemaProvider(provisional, state.schema_provider)` → `CompositeSchemaProvider(state.schema_provider, provisional)` (real schema first; same invariant already at `:922`). Verify the 485ff2 CutAndDragOnPath case resolves to named fields, not `widget_N`.
.oracle/checkins/G0.md-629-
.oracle/checkins/G0.md-630-### G0 verification (all must pass)
.oracle/checkins/G0.md-631-
.oracle/checkins/G0.md-632-```bash
.oracle/checkins/G0.md-633-.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_structural_harness_runner.py
.oracle/checkins/G0.md-634-# harness mechanics + the 9 counterexamples + 4 structured controls + retry tests
.oracle/checkins/G0.md-635-.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_edit.py::test_agent_edit_batch_protocol_retry_executes_dataclasses_replace tests/test_comfy_nodes_agent_backend_spine.py::test_run_agent_turn_batch_retries_empty_content_once_then_succeeds
.oracle/checkins/G0.md-636-# regression lock
--
.oracle/checkins/G0.md-804-- Unresolved endpoints remain a typed refusal, not an assumed equivalence.
.oracle/checkins/G0.md-805-
.oracle/checkins/G0.md-806-### Formal checkpoint B03
.oracle/checkins/G0.md-807-
.oracle/checkins/G0.md-808-Review traversal termination, cycle handling, UID use, set equality, negative controls, and `git diff C04..C05`. Reject comparisons that still depend on raw link count or link ID. Verdict: `PASS` or issue list; rework B03 until `PASS`.
.oracle/checkins/G0.md-809-
.oracle/checkins/G0.md-810----
.oracle/checkins/G0.md-811-
.oracle/checkins/G0.md:812:## B04 — Real-schema authority and apply-time combo validation
.oracle/checkins/G0.md-813-
.oracle/checkins/G0.md-814-**Executor:** DeepSeek V4 Flash
.oracle/checkins/G0.md-815-**Plan item:** 7
.oracle/checkins/G0.md-816-
.oracle/checkins/G0.md-817-### Tasks
.oracle/checkins/G0.md-818-
.oracle/checkins/G0.md-819-1. Put real schemas before provisional evidence everywhere.
.oracle/checkins/G0.md-820-   - Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py`, `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, and focused agent tests.
--
.oracle/checkins/G0.md-1990-| # | Area | Verdict | Key finding |
.oracle/checkins/G0.md-1991-|---|---|---|---|
.oracle/checkins/G0.md-1992-| D1 | Stage-resolved model/transport provenance | CONFIRMED | Per-phase models profile-driven (flash classify/reply, **pro research/implement**) since 2026-06-18; `VIBECOMFY_OPENROUTER_MODEL` never reaches implement. **Transport changed: June native `api.deepseek.com` (105/105) → now OpenRouter (100%)** |
.oracle/checkins/G0.md-1993-| D2 | Counterfactual scoring | CONFIRMED | True current 49/100; true baseline 69/100; matcher = ~9-point tax; message_artifact added Jul 1 |
.oracle/checkins/G0.md-1994-| D3 | Malformed-response provenance | CONFIRMED | 14 MalformedModelJSON: 11 transport/empty (0 tokens) + 3 parser-contract (real tokens). Batch-repl preserves parse_reason/raw; classify/reply preserve nothing |
.oracle/checkins/G0.md-1995-| D4 | Baseline drift | CONFIRMED | **`edit_batch_repl.py:1577` `dataclasses.replace` without import → NameError on every sync retry (10 failures)** — introduced `11f4267e`, FIXED `c77fe228`. Request envelopes byte-identical June-vs-now; prompt bytes +27% (intentional) |
.oracle/checkins/G0.md-1996-| D5 | Canonicalization authority | CONFIRMED | c467f7d9 partial: executor_durable bypass + lossy converter (15→2 nodes) + pin_opaque uid-less emission; 64/85 submits serialized-Vibe, 18 carry muted rich nodes |
.oracle/checkins/G0.md-1997-| D6 | Retry reachability | CONFIRMED | 6 retry layers all scoped to transient/parse faults; deterministic contract rejections + batch exceptions escape all; B6 edit LANDED in-session then discarded at allocation |
.oracle/checkins/G0.md:1998:| D7 | Schema witness | PARTIAL | 3/4 unexpressible genuinely absent; **precedence bug CONFIRMED** `_frag_research.py:821` (provisional-first shadows real schema); combo-option validation NOT enforced at apply |
.oracle/checkins/G0.md-1999-| D8 | Refusal scoring | CONFIRMED | 11 refusal-failures: 4 matcher-FP; 7 true → 3 grounded / 3 ungrounded give-ups / 1 partial; safe-refusal mechanism works when wired (2 scenarios) |
.oracle/checkins/G0.md-2000-| D9 | Research starvation | REFUTED | 429s universal (100% in baseline too); research never starved (failed scenarios got MORE sources); not causal |
.oracle/checkins/G0.md-2001-| D10 | Pinned-node guard | CONFIRMED | Pre-editor false positive: Set/Get broadcast lowering expands 1 raw link → 4 lowered; pin guard compares cardinality not semantics; 44/131 corpus nodes exposed |
.oracle/checkins/G0.md-2002-
.oracle/checkins/G0.md-2003----
.oracle/checkins/G0.md-2004-
.oracle/checkins/G0.md-2005-## 4. Forward plan — 11 items (three lenses)
.oracle/checkins/G0.md-2006-
--
.oracle/checkins/G0.md-3907-    48
.oracle/checkins/G0.md-3908-    49	### G0-T4 — Evidence plumbing at classify+reply (cheap half of plan item 11)
.oracle/checkins/G0.md-3909-    50
.oracle/checkins/G0.md-3910-    51	- Touch: `vibecomfy/comfy_nodes/agent/worker.py`, `vibecomfy/comfy_nodes/agent/provider.py`, `vibecomfy/executor/core.py` (classify/reply paths).
.oracle/checkins/G0.md-3911-    52	- Persist bounded raw preview, `parse_reason`, finish reason, observed usage, model, phase, and endpoint — the same evidence batch-repl already preserves (`edit_batch_repl.py:254-262`, `1538/1553/1575/1582-1587/1607-1610`). Also stop writing the fake `respond_only` classification when classify raises.
.oracle/checkins/G0.md-3912-    53
.oracle/checkins/G0.md-3913-    54	### G0-R1 — Rider: one-line schema-precedence swap (from plan item 7)
.oracle/checkins/G0.md-3914-    55
.oracle/checkins/G0.md:3915:    56	- Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py:821` — `CompositeSchemaProvider(provisional, state.schema_provider)` → `CompositeSchemaProvider(state.schema_provider, provisional)` (real schema first; same invariant already at `:922`). Verify the 485ff2 CutAndDragOnPath case resolves to named fields, not `widget_N`.
.oracle/checkins/G0.md-3916-    57
.oracle/checkins/G0.md-3917-    58	### G0 verification (all must pass)
.oracle/checkins/G0.md-3918-    59
.oracle/checkins/G0.md-3919-    60	```bash
.oracle/checkins/G0.md-3920-    61	.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py tests/test_structural_harness_runner.py
.oracle/checkins/G0.md-3921-    62	# harness mechanics + the 9 counterexamples + 4 structured controls + retry tests
.oracle/checkins/G0.md-3922-    63	.venv/bin/python -m pytest -q tests/test_comfy_nodes_agent_edit.py::test_agent_edit_batch_protocol_retry_executes_dataclasses_replace tests/test_comfy_nodes_agent_backend_spine.py::test_run_agent_turn_batch_retries_empty_content_once_then_succeeds
.oracle/checkins/G0.md-3923-    64	# regression lock
--
.oracle/checkins/batch-B04.md-15---------
.oracle/checkins/batch-B04.md-16-user
.oracle/checkins/batch-B04.md-17-# MEGADO CHECKPOINT — Batch B04 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)
.oracle/checkins/batch-B04.md-18-
.oracle/checkins/batch-B04.md-19-You are the B04 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.
.oracle/checkins/batch-B04.md-20-
.oracle/checkins/batch-B04.md-21-## The batch
.oracle/checkins/batch-B04.md-22-
.oracle/checkins/batch-B04.md:23:**B04 — Real-schema authority.** Tasks + acceptance from `.oracle/tasklist.md` (B04 section). Diff to review: `git diff f2661b01..ff6ae9c8` (D13 PASS SHA → B04 commit). Executor: DeepSeek V4 Flash.
.oracle/checkins/batch-B04.md-24-
.oracle/checkins/batch-B04.md-25-## Executor evidence
.oracle/checkins/batch-B04.md-26-
.oracle/checkins/batch-B04.md-27-- New helper `with_provisional_gap_filler(authoritative, provisional)` in `vibecomfy/schema/provider.py` (+ re-export in `schema/__init__.py`, + snapshot update in `test_api_surface.py`).
.oracle/checkins/batch-B04.md-28-- All 7 construction sites now real-first through the helper: `_frag_research.py` (:821, :874, :922), `_frag_response_contract.py:793` (cross-turn — no longer poisons session), `_frag_batch_loop.py:910`, `edit_batch_repl.py:1116`.
.oracle/checkins/batch-B04.md-29-- Focused tests: 45 passed (`tests/test_comfy_nodes_agent_edit.py` + backend_spine, -k schema/precedence/provisional/real_schema/widget/cross_turn).
.oracle/checkins/batch-B04.md-30-- Broader slice: 62 passed / 1 failed / 1 skipped — the 1 failure is `test_api_surface.py::test_public_module_all_snapshots_are_intentional`, which is in the PRE-EXISTING quarantine baseline `tests/quarantine/emitter_parity_surface.txt` (owner emitter-parity-surface, reason: legacy baseline failures). Verified: that snapshot delta concerns `RawWidgetPayload`/`WorkflowSource` in the workflow lens, predates B04, and `vibecomfy/workflow.py` is untouched by this range.
.oracle/checkins/batch-B04.md-31-
.oracle/checkins/batch-B04.md-32-## Review focus (adversarial)
.oracle/checkins/batch-B04.md-33-
.oracle/checkins/batch-B04.md-34-1. The helper composes real-first (CompositeSchemaProvider(authoritative, provisional)) — verify get_schema first-match + schemas() reverse-merge semantics still make the FIRST provider dominant at every site.
.oracle/checkins/batch-B04.md:35:2. ALL SEVEN sites (grep `CompositeSchemaProvider` and `with_provisional_gap_filler` across vibecomfy/): no provisional-first construction remains anywhere; no helper factory can reintroduce wrong precedence.
.oracle/checkins/batch-B04.md-36-3. Cross-turn: `_frag_response_contract.py:793` previously poisoned session AND state — confirm the fix composes `(session.schema_provider, provisional)` and the cross-turn regression exists + passes.
.oracle/checkins/batch-B04.md:37:4. Widget/choice shadowing: provisional `widget_N` names and empty choices cannot shadow real semantic names/choices (fixture).
.oracle/checkins/batch-B04.md-38-5. Enum: invalid values rejected before mutation for add and set (existing mechanism tests still green); missing local asset filenames remain warning-only.
.oracle/checkins/batch-B04.md-39-6. Scope: only B04 files; `git diff --check f2661b01..ff6ae9c8` clean.
.oracle/checkins/batch-B04.md-40-7. Run the focused slice yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks; skip the quarantined surface test).
.oracle/checkins/batch-B04.md-41-
.oracle/checkins/batch-B04.md-42-## Output
.oracle/checkins/batch-B04.md-43-
.oracle/checkins/batch-B04.md-44-First line: `B04 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
.oracle/checkins/batch-B04.md-45-Then per-focus findings (1–7) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
--
.oracle/checkins/batch-B04.md-237-128-- Source-workflow hashes resolve before D13 passes.
.oracle/checkins/batch-B04.md-238-129-
.oracle/checkins/batch-B04.md-239-130-### Oracle checkpoint
.oracle/checkins/batch-B04.md-240-131-
.oracle/checkins/batch-B04.md-241-132-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
.oracle/checkins/batch-B04.md-242-133-
.oracle/checkins/batch-B04.md-243-134----
.oracle/checkins/batch-B04.md-244-135-
.oracle/checkins/batch-B04.md:245:136:## B04 — Real-schema authority
.oracle/checkins/batch-B04.md-246-137-
.oracle/checkins/batch-B04.md-247-138-### Tasks
.oracle/checkins/batch-B04.md-248-139-
.oracle/checkins/batch-B04.md-249-140-1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/checkins/batch-B04.md:250:141-2. Migrate all four verified provisional-first sites:
.oracle/checkins/batch-B04.md-251-142-   - `_frag_research.py:874`;
.oracle/checkins/batch-B04.md-252-143-   - `_frag_response_contract.py:793`;
.oracle/checkins/batch-B04.md-253-144-   - `_frag_batch_loop.py:910`;
.oracle/checkins/batch-B04.md-254-145-   - `edit_batch_repl.py:1115`.
.oracle/checkins/batch-B04.md-255-146-3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
.oracle/checkins/batch-B04.md-256-147-4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
.oracle/checkins/batch-B04.md:257:148-5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/checkins/batch-B04.md-258-149-
.oracle/checkins/batch-B04.md-259-150-### Acceptance
.oracle/checkins/batch-B04.md-260-151-
.oracle/checkins/batch-B04.md-261-152-- All seven sites are real-first.
.oracle/checkins/batch-B04.md-262-153-- Session schema authority remains real-first across turns.
.oracle/checkins/batch-B04.md:263:154-- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/checkins/batch-B04.md-264-155-- Invalid enum values are rejected before mutation for add and set.
.oracle/checkins/batch-B04.md-265-156-- Missing local asset filenames remain warning-only.
.oracle/checkins/batch-B04.md-266-157-
.oracle/checkins/batch-B04.md-267-158-### Oracle checkpoint
.oracle/checkins/batch-B04.md-268-159-
.oracle/checkins/batch-B04.md-269-160-Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.
.oracle/checkins/batch-B04.md-270-161-
.oracle/checkins/batch-B04.md-271-162----
--
.oracle/checkins/batch-B04.md-1696-   445	    "_run_batch_repl_queue_validate_if_needed",
.oracle/checkins/batch-B04.md-1697-   446	    "_run_delta_dev_path",
.oracle/checkins/batch-B04.md-1698-   447	    "_run_full_dev_path",
.oracle/checkins/batch-B04.md-1699-   448	    "_run_stage",
.oracle/checkins/batch-B04.md-1700-   449	    "_stage_batch_repl_queue_validate",
.oracle/checkins/batch-B04.md-1701-   450	)
.oracle/checkins/batch-B04.md-1702-
.oracle/checkins/batch-B04.md-1703- succeeded in 242ms:
.oracle/checkins/batch-B04.md:1704:# MEGADO BATCH B04 — Real-schema authority (Flash executor)
.oracle/checkins/batch-B04.md-1705-
.oracle/checkins/batch-B04.md-1706-Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only.
.oracle/checkins/batch-B04.md-1707-
.oracle/checkins/batch-B04.md-1708-## Context
.oracle/checkins/batch-B04.md:1709:G0-R1 already swapped `_frag_research.py:821` to real-first. Exploration found 7 total construction sites; 4 are provisional-first and must be fixed (the oracle-verified list):
.oracle/checkins/batch-B04.md-1710-
.oracle/checkins/batch-B04.md-1711-1. `vibecomfy/comfy_nodes/agent/_frag_research.py:874` — `(provisional, state)` ✗
.oracle/checkins/batch-B04.md-1712-2. `vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793` — `(provisional, session.schema_provider)` ✗ **poisons session AND state across turns**
.oracle/checkins/batch-B04.md-1713-3. `vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:910` — `(provisional, state)` ✗
.oracle/checkins/batch-B04.md-1714-4. `vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1115` — ✗ (remaining site)
.oracle/checkins/batch-B04.md-1715-
.oracle/checkins/batch-B04.md-1716-Real-first invariant: `CompositeSchemaProvider.get_schema` is first-match-wins and `schemas()` merges `reversed(providers)` — the FIRST provider dominates both views, so real-first is required at every site.
.oracle/checkins/batch-B04.md-1717-
.oracle/checkins/batch-B04.md-1718-## Tasks (from .oracle/tasklist.md B04)
.oracle/checkins/batch-B04.md-1719-
.oracle/checkins/batch-B04.md-1720-1. Introduce ONE small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/checkins/batch-B04.md:1721:2. Migrate all four provisional-first sites to real-first.
.oracle/checkins/batch-B04.md-1722-3. Assert precedence across ALL SEVEN construction sites for both `get_schema()` and merged `schemas()` (test).
.oracle/checkins/batch-B04.md-1723-4. Add a cross-turn regression for `_frag_response_contract.py:793` (currently poisons session + state — verify it no longer does).
.oracle/checkins/batch-B04.md:1724:5. Retain mechanism-level enum regressions for add and set (existing tests). Do NOT add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/checkins/batch-B04.md-1725-
.oracle/checkins/batch-B04.md-1726-## Key files
.oracle/checkins/batch-B04.md-1727-- vibecomfy/comfy_nodes/agent/_frag_research.py, _frag_response_contract.py, _frag_batch_loop.py, edit_batch_repl.py, _frag_entrypoint.py (baseline), routes.py
.oracle/checkins/batch-B04.md-1728-- vibecomfy/comfy_nodes/agent/projection_registry_v1.py (get_schema/schemas semantics)
.oracle/checkins/batch-B04.md-1729-- tests: focused agent tests + test_executor_contracts.py
.oracle/checkins/batch-B04.md-1730-
.oracle/checkins/batch-B04.md-1731-## Verification (run, retain output)
.oracle/checkins/batch-B04.md-1732-```bash
.oracle/checkins/batch-B04.md-1733-.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py -k 'schema or precedence or provisional or real_schema or widget'
.oracle/checkins/batch-B04.md-1734-```
.oracle/checkins/batch-B04.md-1735-Plus run the full targeted files: `.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py` (expected exit 0; the rerunfailures plugin binds a socket and cannot run here).
.oracle/checkins/batch-B04.md-1736-
.oracle/checkins/batch-B04.md-1737-## Acceptance
.oracle/checkins/batch-B04.md-1738-- All seven sites real-first.
.oracle/checkins/batch-B04.md-1739-- Session schema authority real-first across turns.
.oracle/checkins/batch-B04.md:1740:- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/checkins/batch-B04.md-1741-- Invalid enum values rejected before mutation for add and set.
.oracle/checkins/batch-B04.md-1742-- Missing local asset filenames remain warning-only.
.oracle/checkins/batch-B04.md-1743-
.oracle/checkins/batch-B04.md-1744-## Report
.oracle/checkins/batch-B04.md-1745-Return: helper name/location, per-site changes (file:line), the seven-site precedence test, cross-turn regression proof, enum regression results, pytest output. Do NOT commit.
.oracle/checkins/batch-B04.md-1746-
.oracle/checkins/batch-B04.md-1747-exec
.oracle/checkins/batch-B04.md-1748-/bin/zsh -lc "rg -n 'ProvisionalRegistrySchemaProvider|CompositeSchemaProvider\\(' vibecomfy --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
--
.oracle/checkins/batch-B04.md-1774- 19988	    }
.oracle/checkins/batch-B04.md-1775- 19989
.oracle/checkins/batch-B04.md-1776- 19990	    state = _make_state(
.oracle/checkins/batch-B04.md-1777- 19991	        schema_provider=real_provider,
.oracle/checkins/batch-B04.md-1778- 19992	        executor_research_sources=(source,),
.oracle/checkins/batch-B04.md-1779- 19993	    )
.oracle/checkins/batch-B04.md-1780- 19994	    candidates = _hydrate_research_precedent_node_schemas(state)
.oracle/checkins/batch-B04.md-1781- 19995
.oracle/checkins/batch-B04.md:1782: 19996	    # Shadowing class: real named schema must win, never widget_N names.
.oracle/checkins/batch-B04.md-1783- 19997	    resolved = state.schema_provider.get_schema("CutAndDragOnPath")
.oracle/checkins/batch-B04.md-1784- 19998	    assert resolved is not None
.oracle/checkins/batch-B04.md-1785- 19999	    assert resolved.source_provider == "object_info"
.oracle/checkins/batch-B04.md-1786- 20000	    assert "inpaint" in resolved.inputs
.oracle/checkins/batch-B04.md-1787- 20001	    assert "frame_width" in resolved.inputs
.oracle/checkins/batch-B04.md-1788- 20002	    assert "frame_height" in resolved.inputs
.oracle/checkins/batch-B04.md-1789- 20003	    assert "image" in resolved.inputs
.oracle/checkins/batch-B04.md-1790- 20004	    assert not any(name.startswith("widget_") for name in resolved.inputs), (
.oracle/checkins/batch-B04.md:1791: 20005	        f"real schema shadowed by provisional widget_N inputs: {sorted(resolved.inputs)}"
.oracle/checkins/batch-B04.md-1792- 20006	    )
.oracle/checkins/batch-B04.md-1793- 20007
.oracle/checkins/batch-B04.md-1794- 20008	    # Missing class: provisional still fills the gap.
.oracle/checkins/batch-B04.md-1795- 20009	    missing_resolved = state.schema_provider.get_schema("ADE_MissingNode")
.oracle/checkins/batch-B04.md-1796- 20010	    assert missing_resolved is not None
.oracle/checkins/batch-B04.md-1797- 20011	    assert missing_resolved.source_provider == "workflow_json_provisional"
.oracle/checkins/batch-B04.md-1798- 20012
.oracle/checkins/batch-B04.md-1799- 20013	    # Hydration still surfaces the workflow candidates as reviewable evidence.
--
.oracle/checkins/batch-B04.md-1835- 20049	        inputs={"model": InputSpec("MODEL", required=True)},
.oracle/checkins/batch-B04.md-1836- 20050	        outputs=[OutputSpec("MODEL", "MODEL")],
.oracle/checkins/batch-B04.md-1837- 20051	        source_provider="object_info",
.oracle/checkins/batch-B04.md-1838- 20052	        confidence=1.0,
.oracle/checkins/batch-B04.md-1839- 20053	    )
.oracle/checkins/batch-B04.md-1840- 20054
.oracle/checkins/batch-B04.md-1841- 20055
.oracle/checkins/batch-B04.md-1842- 20056	def _b04_weaker_shadow_schema() -> NodeSchema:
.oracle/checkins/batch-B04.md:1843: 20057	    """Same class as the real schema but with widget_N names/empty choices."""
.oracle/checkins/batch-B04.md-1844- 20058	    return NodeSchema(
.oracle/checkins/batch-B04.md-1845- 20059	        class_type=_SHADOW,
.oracle/checkins/batch-B04.md-1846- 20060	        pack=None,
.oracle/checkins/batch-B04.md-1847- 20061	        inputs={"widget_0": InputSpec("STRING", choices=[])},
.oracle/checkins/batch-B04.md-1848- 20062	        outputs=[],
.oracle/checkins/batch-B04.md-1849- 20063	        source_provider="object_info",
.oracle/checkins/batch-B04.md-1850- 20064	        confidence=0.5,
.oracle/checkins/batch-B04.md-1851- 20065	    )
--
.oracle/checkins/batch-B04.md-1859- 20073
.oracle/checkins/batch-B04.md-1860- 20074
.oracle/checkins/batch-B04.md-1861- 20075	def _b04_provisional_candidate(
.oracle/checkins/batch-B04.md-1862- 20076	    *class_types: str,
.oracle/checkins/batch-B04.md-1863- 20077	    validation_mode: str = "registry",
.oracle/checkins/batch-B04.md-1864- 20078	) -> dict[str, Any]:
.oracle/checkins/batch-B04.md-1865- 20079	    """Resolver-candidate dict shape consumed by ProvisionalRegistrySchemaProvider.
.oracle/checkins/batch-B04.md-1866- 20080
.oracle/checkins/batch-B04.md:1867: 20081	    Carries only positional widget_N names and empty choices — exactly the weak
.oracle/checkins/batch-B04.md-1868- 20082	    evidence that must never shadow a real semantic schema.
.oracle/checkins/batch-B04.md-1869- 20083	    """
.oracle/checkins/batch-B04.md-1870- 20084	    nodes = {
.oracle/checkins/batch-B04.md-1871- 20085	        class_type: _b04_provisional_node(class_type, index)
.oracle/checkins/batch-B04.md-1872- 20086	        for index, class_type in enumerate(class_types)
.oracle/checkins/batch-B04.md-1873- 20087	    }
.oracle/checkins/batch-B04.md-1874- 20088	    candidate: dict[str, Any] = {
.oracle/checkins/batch-B04.md-1875- 20089	        "stable_install_hash": f"b04:{','.join(class_types)}",
--
.oracle/checkins/batch-B04.md-1885- 20099	    """Both get_schema() and merged schemas() must prefer the real schema."""
.oracle/checkins/batch-B04.md-1886- 20100	    resolved = provider.get_schema(_SHADOW)
.oracle/checkins/batch-B04.md-1887- 20101	    assert resolved is not None
.oracle/checkins/batch-B04.md-1888- 20102	    assert resolved.source_provider == "object_info"
.oracle/checkins/batch-B04.md-1889- 20103	    assert "frame_width" in resolved.inputs
.oracle/checkins/batch-B04.md-1890- 20104	    assert "mode" in resolved.inputs
.oracle/checkins/batch-B04.md-1891- 20105	    assert list(resolved.inputs["mode"].choices or []) == ["real_a", "real_b"]
.oracle/checkins/batch-B04.md-1892- 20106	    assert not any(name.startswith("widget_") for name in resolved.inputs), (
.oracle/checkins/batch-B04.md:1893: 20107	        f"real schema shadowed by provisional widget_N inputs: {sorted(resolved.inputs)}"
.oracle/checkins/batch-B04.md-1894- 20108	    )
.oracle/checkins/batch-B04.md-1895- 20109	    merged = provider.schemas()
.oracle/checkins/batch-B04.md-1896- 20110	    assert merged[_SHADOW] is resolved, "merged schemas() view lost real-first precedence"
.oracle/checkins/batch-B04.md-1897- 20111	    gap = provider.get_schema(_GAP)
.oracle/checkins/batch-B04.md-1898- 20112	    assert gap is not None
.oracle/checkins/batch-B04.md-1899- 20113	    assert gap.source_provider == gap_source, f"expected provisional gap fill, got {gap.source_provider}"
.oracle/checkins/batch-B04.md-1900- 20114	    assert merged[_GAP] is gap, "merged schemas() view lost the provisional gap fill"
.oracle/checkins/batch-B04.md-1901- 20115
--
.oracle/checkins/batch-B04.md-2266- 20480	    monkeypatch: pytest.MonkeyPatch,
.oracle/checkins/batch-B04.md-2267- 20481	) -> None:
.oracle/checkins/batch-B04.md-2268- 20482	    """Session + state authority stays real-first across turns (regression for :793).
.oracle/checkins/batch-B04.md-2269- 20483
.oracle/checkins/batch-B04.md-2270- 20484	    Before B04, _enrich_schema_provider_from_resolver_candidates composed
.oracle/checkins/batch-B04.md-2271- 20485	    (provisional, session.schema_provider): the provisional provider became the
.oracle/checkins/batch-B04.md-2272- 20486	    FIRST provider on BOTH session and durable state, so every later turn —
.oracle/checkins/batch-B04.md-2273- 20487	    including a fresh EditSession built from state.schema_provider — resolved
.oracle/checkins/batch-B04.md:2274: 20488	    overlapping classes through weak widget_N schemas.
.oracle/checkins/batch-B04.md-2275- 20489	    """
.oracle/checkins/batch-B04.md-2276- 20490	    from vibecomfy.comfy_nodes.agent.edit import _enrich_schema_provider_from_resolver_candidates
.oracle/checkins/batch-B04.md-2277- 20491	    from vibecomfy.porting.edit.session import EditSession
.oracle/checkins/batch-B04.md-2278- 20492
.oracle/checkins/batch-B04.md-2279- 20493	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
.oracle/checkins/batch-B04.md-2280- 20494	    session = types.SimpleNamespace(schema_provider=real)
.oracle/checkins/batch-B04.md-2281- 20495	    state = _make_state(schema_provider=real)
.oracle/checkins/batch-B04.md-2282- 20496
--
.oracle/checkins/batch-B04.md-2342-tests/test_comfy_nodes_agent_edit.py:20218:def test_schema_precedence_batch_repl_registry_hydration_real_first() -> None:
.oracle/checkins/batch-B04.md-2343-tests/test_comfy_nodes_agent_edit.py:20244:def test_schema_precedence_baseline_runtime_provider_real_first(
.oracle/checkins/batch-B04.md-2344-tests/test_comfy_nodes_agent_edit.py:20309:def test_schema_precedence_across_all_seven_construction_sites(
.oracle/checkins/batch-B04.md-2345-tests/test_comfy_nodes_agent_edit.py:20479:def test_schema_enrichment_cross_turn_keeps_real_first(
.oracle/checkins/batch-B04.md-2346-tests/test_porting_edit_apply.py:299:def test_resolve_delta_rejects_invalid_enum_without_mutating_original() -> None:
.oracle/checkins/batch-B04.md-2347-tests/test_porting_edit_apply.py:415:def test_resolve_delta_accepts_ksampler_widget_fields_but_not_socket_literals() -> None:
.oracle/checkins/batch-B04.md-2348-tests/test_porting_edit_apply.py:464:def test_resolve_delta_accepts_loadimage_semantic_alias_with_widget_only_schema() -> None:
.oracle/checkins/batch-B04.md-2349-tests/test_porting_edit_apply.py:510:def test_resolve_delta_accepts_object_info_semantic_alias_for_existing_widget_field() -> None:
.oracle/checkins/batch-B04.md:2350:tests/test_porting_edit_apply.py:622:def test_resolve_delta_unknown_ksampler_set_node_field_exposes_compact_names_and_omits_widget_N() -> None:
.oracle/checkins/batch-B04.md:2351:tests/test_porting_edit_apply.py:730:def test_resolve_delta_unknown_ksampler_add_node_field_omits_covered_widget_N() -> None:
.oracle/checkins/batch-B04.md-2352-tests/test_porting_edit_apply.py:929:def test_apply_delta_sets_unlinked_widget_value_and_preserves_unrelated_nodes() -> None:
.oracle/checkins/batch-B04.md-2353-tests/test_porting_edit_apply.py:957:def test_apply_delta_sets_ksampler_control_after_generate_ui_widget() -> None:
.oracle/checkins/batch-B04.md-2354-tests/test_porting_edit_apply.py:996:def test_apply_delta_maps_legacy_unused_widget_alias_to_control_after_generate() -> None:
.oracle/checkins/batch-B04.md-2355-tests/test_porting_edit_apply.py:1397:def test_apply_delta_auto_unlinks_schema_less_linked_widget_and_records_diagnostics() -> None:
.oracle/checkins/batch-B04.md-2356-tests/test_porting_edit_apply.py:1468:def test_apply_delta_sets_schema_less_dict_widget_without_changing_other_nodes() -> None:
.oracle/checkins/batch-B04.md-2357-tests/test_porting_edit_apply.py:1534:def test_apply_delta_unlinks_widget_input_and_sets_dict_widget_value() -> None:
.oracle/checkins/batch-B04.md-2358-tests/test_porting_edit_apply.py:1602:def test_resolve_delta_rejects_unknown_dict_widget_field() -> None:
.oracle/checkins/batch-B04.md-2359-tests/test_porting_edit_apply.py:1836:def test_apply_delta_reorders_unlinked_widget_values_only() -> None:
--
.oracle/checkins/batch-B04.md-2437- 20480	    monkeypatch: pytest.MonkeyPatch,
.oracle/checkins/batch-B04.md-2438- 20481	) -> None:
.oracle/checkins/batch-B04.md-2439- 20482	    """Session + state authority stays real-first across turns (regression for :793).
.oracle/checkins/batch-B04.md-2440- 20483
.oracle/checkins/batch-B04.md-2441- 20484	    Before B04, _enrich_schema_provider_from_resolver_candidates composed
.oracle/checkins/batch-B04.md-2442- 20485	    (provisional, session.schema_provider): the provisional provider became the
.oracle/checkins/batch-B04.md-2443- 20486	    FIRST provider on BOTH session and durable state, so every later turn —
.oracle/checkins/batch-B04.md-2444- 20487	    including a fresh EditSession built from state.schema_provider — resolved
.oracle/checkins/batch-B04.md:2445: 20488	    overlapping classes through weak widget_N schemas.
.oracle/checkins/batch-B04.md-2446- 20489	    """
.oracle/checkins/batch-B04.md-2447- 20490	    from vibecomfy.comfy_nodes.agent.edit import _enrich_schema_provider_from_resolver_candidates
.oracle/checkins/batch-B04.md-2448- 20491	    from vibecomfy.porting.edit.session import EditSession
.oracle/checkins/batch-B04.md-2449- 20492
.oracle/checkins/batch-B04.md-2450- 20493	    real = _Provider({_SHADOW: _b04_real_shadow_schema()})
.oracle/checkins/batch-B04.md-2451- 20494	    session = types.SimpleNamespace(schema_provider=real)
.oracle/checkins/batch-B04.md-2452- 20495	    state = _make_state(schema_provider=real)
.oracle/checkins/batch-B04.md-2453- 20496
--
.oracle/checkins/batch-B04.md-2928-   722	    assert "control_after_generate" in semantic_aliases
.oracle/checkins/batch-B04.md-2929-   723	    assert semantic_aliases["control_after_generate"] == "widget_1"
.oracle/checkins/batch-B04.md-2930-   724
.oracle/checkins/batch-B04.md-2931-   725	    # Self-mapping fields (seed→seed, steps→steps, …) must NOT leak into aliases.
.oracle/checkins/batch-B04.md-2932-   726	    for compact_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
.oracle/checkins/batch-B04.md-2933-   727	        assert compact_name not in semantic_aliases, f"{compact_name!r} should not appear in semantic_aliases"
.oracle/checkins/batch-B04.md-2934-   728
.oracle/checkins/batch-B04.md-2935-   729
.oracle/checkins/batch-B04.md:2936:   730	def test_resolve_delta_unknown_ksampler_add_node_field_omits_covered_widget_N() -> None:
.oracle/checkins/batch-B04.md-2937-   731	    """When add_node targets a KSampler with an unknown field, the class-level
.oracle/checkins/batch-B04.md:2938:   732	    diagnostics must omit widget_N slots that have compact semantic names."""
.oracle/checkins/batch-B04.md-2939-   733	    original = _fixture()
.oracle/checkins/batch-B04.md-2940-   734	    delta = parse_edit_delta(
.oracle/checkins/batch-B04.md-2941-   735	        [
.oracle/checkins/batch-B04.md-2942-   736	            {
.oracle/checkins/batch-B04.md-2943-   737	                "op": "add_node",
.oracle/checkins/batch-B04.md-2944-   738	                "scope_path": "",
.oracle/checkins/batch-B04.md-2945-   739	                "class_type": "KSampler",
.oracle/checkins/batch-B04.md-2946-   740	                "fields": {"seed": 7, "bogus_field": 999},
--
.oracle/checkins/batch-B04.md-2954-   748	    assert result.ok is False
.oracle/checkins/batch-B04.md-2955-   749	    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_add_node_field")
.oracle/checkins/batch-B04.md-2956-   750	    valid_fields = issue.detail["valid_fields"]
.oracle/checkins/batch-B04.md-2957-   751
.oracle/checkins/batch-B04.md-2958-   752	    # Compact names must be in valid_fields.
.oracle/checkins/batch-B04.md-2959-   753	    for compact_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
.oracle/checkins/batch-B04.md-2960-   754	        assert compact_name in valid_fields, f"{compact_name!r} missing from valid_fields"
.oracle/checkins/batch-B04.md-2961-   755
.oracle/checkins/batch-B04.md:2962:   756	    # widget_N for slots that have known semantic names must be omitted.
.oracle/checkins/batch-B04.md-2963-   757	    for widget_n in ("widget_0", "widget_2", "widget_3", "widget_4", "widget_5", "widget_6"):
.oracle/checkins/batch-B04.md-2964-   758	        assert widget_n not in valid_fields, f"{widget_n!r} should be omitted but is present"
.oracle/checkins/batch-B04.md-2965-   759
.oracle/checkins/batch-B04.md-2966-   760
.oracle/checkins/batch-B04.md-2967-
.oracle/checkins/batch-B04.md-2968- succeeded in 837ms:
.oracle/checkins/batch-B04.md-2969-vibecomfy/porting/edit/lint.py:1246:    for i, op in enumerate(delta):
.oracle/checkins/batch-B04.md-2970-vibecomfy/porting/edit/lint.py:1271:    for i, op in enumerate(delta):
--
.oracle/checkins/batch-B04.md-4007-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-B04.md-4008-77-+
.oracle/checkins/batch-B04.md-4009-78-+def _b04_provisional_candidate(
.oracle/checkins/batch-B04.md-4010-79-+    *class_types: str,
.oracle/checkins/batch-B04.md-4011-80-+    validation_mode: str = "registry",
.oracle/checkins/batch-B04.md-4012-81-+) -> dict[str, Any]:
.oracle/checkins/batch-B04.md-4013-82-+    """Resolver-candidate dict shape consumed by ProvisionalRegistrySchemaProvider.
.oracle/checkins/batch-B04.md-4014-83-+
.oracle/checkins/batch-B04.md:4015:84-+    Carries only positional widget_N names and empty choices — exactly the weak
.oracle/checkins/batch-B04.md-4016-85-+    evidence that must never shadow a real semantic schema.
.oracle/checkins/batch-B04.md-4017-86-+    """
.oracle/checkins/batch-B04.md-4018-87-+    nodes = {
.oracle/checkins/batch-B04.md-4019-88-+        class_type: _b04_provisional_node(class_type, index)
.oracle/checkins/batch-B04.md-4020-89:+        for index, class_type in enumerate(class_types)
.oracle/checkins/batch-B04.md-4021-90-+    }
.oracle/checkins/batch-B04.md-4022-91-+    candidate: dict[str, Any] = {
.oracle/checkins/batch-B04.md-4023-92-+        "stable_install_hash": f"b04:{','.join(class_types)}",
--
.oracle/checkins/batch-B04.md-4203-16db45f8 m1-edit-state-authority: megaplan milestone (#51)
.oracle/checkins/batch-B04.md-4204-75661639 agent-edit: fix StaleStateMismatch round-trip + self-healing baseline + complete-edit done-guard
.oracle/checkins/batch-B04.md-4205-4274eaa4 m5-preserve-roundtrip: megaplan milestone (#31)
.oracle/checkins/batch-B04.md-4206-6ae229a6 Document the wrapper codegen pipeline and add a demo script
.oracle/checkins/batch-B04.md-4207-5189128d Re-emit 5 runexx Family P templates through current emitter
.oracle/checkins/batch-B04.md-4208-b60bef0a feat: object_info pre-submit validator as a real gate
.oracle/checkins/batch-B04.md-4209-
.oracle/checkins/batch-B04.md-4210-exec
.oracle/checkins/batch-B04.md:4211:/bin/zsh -lc "rg -n -C8 'enum regressions|Real-schema authority|widget_N|provisional-first' .oracle --glob '*.md' --glob '*.txt'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
--
.oracle/briefs/batch-B04.md:1:# MEGADO BATCH B04 — Real-schema authority (Flash executor)
.oracle/briefs/batch-B04.md-2-
.oracle/briefs/batch-B04.md-3-Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only.
.oracle/briefs/batch-B04.md-4-
.oracle/briefs/batch-B04.md-5-## Context
.oracle/briefs/batch-B04.md:6:G0-R1 already swapped `_frag_research.py:821` to real-first. Exploration found 7 total construction sites; 4 are provisional-first and must be fixed (the oracle-verified list):
.oracle/briefs/batch-B04.md-7-
.oracle/briefs/batch-B04.md-8-1. `vibecomfy/comfy_nodes/agent/_frag_research.py:874` — `(provisional, state)` ✗
.oracle/briefs/batch-B04.md-9-2. `vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793` — `(provisional, session.schema_provider)` ✗ **poisons session AND state across turns**
.oracle/briefs/batch-B04.md-10-3. `vibecomfy/comfy_nodes/agent/_frag_batch_loop.py:910` — `(provisional, state)` ✗
.oracle/briefs/batch-B04.md-11-4. `vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1115` — ✗ (remaining site)
.oracle/briefs/batch-B04.md-12-
.oracle/briefs/batch-B04.md-13-Real-first invariant: `CompositeSchemaProvider.get_schema` is first-match-wins and `schemas()` merges `reversed(providers)` — the FIRST provider dominates both views, so real-first is required at every site.
.oracle/briefs/batch-B04.md-14-
.oracle/briefs/batch-B04.md-15-## Tasks (from .oracle/tasklist.md B04)
.oracle/briefs/batch-B04.md-16-
.oracle/briefs/batch-B04.md-17-1. Introduce ONE small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/briefs/batch-B04.md:18:2. Migrate all four provisional-first sites to real-first.
.oracle/briefs/batch-B04.md-19-3. Assert precedence across ALL SEVEN construction sites for both `get_schema()` and merged `schemas()` (test).
.oracle/briefs/batch-B04.md-20-4. Add a cross-turn regression for `_frag_response_contract.py:793` (currently poisons session + state — verify it no longer does).
.oracle/briefs/batch-B04.md:21:5. Retain mechanism-level enum regressions for add and set (existing tests). Do NOT add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/briefs/batch-B04.md-22-
.oracle/briefs/batch-B04.md-23-## Key files
.oracle/briefs/batch-B04.md-24-- vibecomfy/comfy_nodes/agent/_frag_research.py, _frag_response_contract.py, _frag_batch_loop.py, edit_batch_repl.py, _frag_entrypoint.py (baseline), routes.py
.oracle/briefs/batch-B04.md-25-- vibecomfy/comfy_nodes/agent/projection_registry_v1.py (get_schema/schemas semantics)
.oracle/briefs/batch-B04.md-26-- tests: focused agent tests + test_executor_contracts.py
.oracle/briefs/batch-B04.md-27-
.oracle/briefs/batch-B04.md-28-## Verification (run, retain output)
.oracle/briefs/batch-B04.md-29-```bash
.oracle/briefs/batch-B04.md-30-.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py -k 'schema or precedence or provisional or real_schema or widget'
.oracle/briefs/batch-B04.md-31-```
.oracle/briefs/batch-B04.md-32-Plus run the full targeted files: `.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py` (expected exit 0; the rerunfailures plugin binds a socket and cannot run here).
.oracle/briefs/batch-B04.md-33-
.oracle/briefs/batch-B04.md-34-## Acceptance
.oracle/briefs/batch-B04.md-35-- All seven sites real-first.
.oracle/briefs/batch-B04.md-36-- Session schema authority real-first across turns.
.oracle/briefs/batch-B04.md:37:- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/briefs/batch-B04.md-38-- Invalid enum values rejected before mutation for add and set.
.oracle/briefs/batch-B04.md-39-- Missing local asset filenames remain warning-only.
.oracle/briefs/batch-B04.md-40-
.oracle/briefs/batch-B04.md-41-## Report
.oracle/briefs/batch-B04.md-42-Return: helper name/location, per-site changes (file:line), the seven-site precedence test, cross-turn regression proof, enum regression results, pytest output. Do NOT commit.
--
.oracle/findings/area-04-schema-provider.txt-5-Precedence: `CompositeSchemaProvider.get_schema` = first-match-wins; `schemas()` merges `reversed(providers)`, so the **first** provider also dominates the merged dict — real-first is the invariant for both views.
.oracle/findings/area-04-schema-provider.txt-6-
.oracle/findings/area-04-schema-provider.txt-7-Baseline is real: `_frag_entrypoint.py:65` (`_default_runtime_schema_provider`), `routes.py:107/230` (`get_schema_provider("local")`). Wrong precedence enters only via the sites below.
.oracle/findings/area-04-schema-provider.txt-8-
.oracle/findings/area-04-schema-provider.txt-9-**Sites (7)** — argument order:
.oracle/findings/area-04-schema-provider.txt-10-1. `_frag_orchestration.py:434` — `(*providers)` = [Runtime, Authoring] — all real ✓
.oracle/findings/area-04-schema-provider.txt-11-2. `_frag_research.py:821` — `(state, provisional)` real-first ✓ (structurally; poisoned if 874 ran earlier)
.oracle/findings/area-04-schema-provider.txt-12-3. `_frag_research.py:922` — `(state, provisional)` real-first ✓ (same caveat)
.oracle/findings/area-04-schema-provider.txt:13:4. `_frag_research.py:874` — `(provisional, state)` ✗ provisional-first (known)
.oracle/findings/area-04-schema-provider.txt-14-5. `_frag_response_contract.py:793` — `(provisional, session.schema_provider)` ✗ **new**; sets both session AND state → poisons session across turns
.oracle/findings/area-04-schema-provider.txt-15-6. `_frag_batch_loop.py:910` — `(provisional, state)` ✗ **new**
.oracle/findings/area-04-schema-provider.txt-16-7. `edit_batch_repl.py:1115` — `(provisional, state)` ✗ known (`_hydrate_actionable_registry_dependencies`)
.oracle/findings/area-04-schema-provider.txt-17-
.oracle/findings/area-04-schema-provider.txt-18-Helper factories (`get_schema_provider`, `get_authoring_schema_provider`, `_default_runtime_schema_provider`) never inject provisional — safe. No shared "wrap-with-provisional" helper exists; each bug site hand-rolls the ordering, which is why it drifts.
.oracle/findings/area-04-schema-provider.txt-19-
.oracle/findings/area-04-schema-provider.txt-20-**Enum/combo at apply — both paths safe:**
.oracle/findings/area-04-schema-provider.txt-21-- Set (`apply_resolve_base.py:184`): `control_after_generate` check (:321) + `_validate_literal_value` (:335) run **before** any mutation; errors → `(None, issues)`.
.oracle/findings/area-04-schema-provider.txt-22-- Add (`apply_resolve_add.py:39`): per-field validation (:199), blocks on error (:209) before `ResolvedAddNodeSpec` builds.
.oracle/findings/area-04-schema-provider.txt:23:- Caveat: `_validate_literal_value` returns `[]` when `spec is None` (apply_values.py:20) — so a provisional-first schema with empty `choices` makes `value_not_in_enum` vacuous. `_coerce_choice_value` and asset-enum warning are soft escapes.
.oracle/findings/area-04-schema-provider.txt-24-
.oracle/findings/area-04-schema-provider.txt-25-**Widget-name derivation:** `contracts.py:2527` → compile-time `WIDGET_SCHEMA` table (aliases.py:129) — provider-independent; fallback only via `apply_positional_widget_aliases`. Low risk.
.oracle/findings/area-04-schema-provider.txt-26-
.oracle/findings/area-04-schema-provider.txt-27-**Unknowns:** intra-turn order of 874 vs 821/922; session persistence across turns (amplifies :793).
.oracle/findings/area-04-schema-provider.txt-28-
.oracle/findings/area-04-schema-provider.txt-29-**Ranked findings:** (1) 793 session-poison, (2) 874, (3) 910, (4) 1115, (5) 821/922 conditional.
.oracle/findings/area-04-schema-provider.txt-30-
.oracle/findings/area-04-schema-provider.txt-31-**Suggested approach:** introduce one factory `prepend_provisional(provider, candidates)` enforcing real-first, migrate all 4 bug sites, assert order in tests.
--
.oracle/checkins/batch-B01.md-659-128-- Source-workflow hashes resolve before D13 passes.
.oracle/checkins/batch-B01.md-660-129-
.oracle/checkins/batch-B01.md-661-130-### Oracle checkpoint
.oracle/checkins/batch-B01.md-662-131-
.oracle/checkins/batch-B01.md-663-132-Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.
.oracle/checkins/batch-B01.md-664-133-
.oracle/checkins/batch-B01.md-665-134----
.oracle/checkins/batch-B01.md-666-135-
.oracle/checkins/batch-B01.md:667:136-## B04 — Real-schema authority
.oracle/checkins/batch-B01.md-668-137-
.oracle/checkins/batch-B01.md-669-138-### Tasks
.oracle/checkins/batch-B01.md-670-139-
.oracle/checkins/batch-B01.md-671-140-1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
.oracle/checkins/batch-B01.md:672:141-2. Migrate all four verified provisional-first sites:
.oracle/checkins/batch-B01.md-673-142-   - `_frag_research.py:874`;
.oracle/checkins/batch-B01.md-674-143-   - `_frag_response_contract.py:793`;
.oracle/checkins/batch-B01.md-675-144-   - `_frag_batch_loop.py:910`;
.oracle/checkins/batch-B01.md-676-145-   - `edit_batch_repl.py:1115`.
.oracle/checkins/batch-B01.md-677-146-3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
.oracle/checkins/batch-B01.md-678-147-4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
.oracle/checkins/batch-B01.md:679:148-5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.
.oracle/checkins/batch-B01.md-680-149-
.oracle/checkins/batch-B01.md-681-150-### Acceptance
.oracle/checkins/batch-B01.md-682-151-
.oracle/checkins/batch-B01.md-683-152-- All seven sites are real-first.
.oracle/checkins/batch-B01.md-684-153-- Session schema authority remains real-first across turns.
.oracle/checkins/batch-B01.md:685:154-- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
.oracle/checkins/batch-B01.md-686-155-- Invalid enum values are rejected before mutation for add and set.
.oracle/checkins/batch-B01.md-687-156-- Missing local asset filenames remain warning-only.
.oracle/checkins/batch-B01.md-688-157-
.oracle/checkins/batch-B01.md-689-158-### Oracle checkpoint
.oracle/checkins/batch-B01.md-690-159-
.oracle/checkins/batch-B01.md-691-160-Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.
.oracle/checkins/batch-B01.md-692-161-
.oracle/checkins/batch-B01.md-693-162----
--
.oracle/checkins/batch-B01.md-1978-./vibecomfy/commands/_agent_edit_debug.py:291:                              capture_output=True, text=True, timeout=5).stdout.strip()
.oracle/checkins/batch-B01.md-1979-./vibecomfy/commands/_agent_edit_debug.py:303:            with httpx.Client(timeout=5.0) as client:
.oracle/checkins/batch-B01.md-1980-./vibecomfy/commands/_agent_edit_debug.py:307:        with urllib.request.urlopen(url, timeout=5) as f:
.oracle/checkins/batch-B01.md-1981-./vibecomfy/comfy_nodes/web/canonical_delta.js:24:export const DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta";
.oracle/checkins/batch-B01.md-1982-./vibecomfy/comfy_nodes/web/canonical_delta.js:334:      code: "canonical_envelope_malformed_ops",
.oracle/checkins/batch-B01.md-1983-./vibecomfy/comfy_nodes/agent/routes.py:805:    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - local ComfyUI endpoint.
.oracle/checkins/batch-B01.md-1984-./tests/test_agent_edit_settings_contract.py:97:    assert seed.kind in ("int", "unknown")  # schema may or may not resolve
.oracle/checkins/batch-B01.md-1985-./tests/test_agent_edit_settings_contract.py:184:def test_node_settings_for_unknown_class_type() -> None:
.oracle/checkins/batch-B01.md:1986:./tests/test_agent_edit_settings_contract.py:185:    """An unknown class type returns widget_N fallback names."""
.oracle/checkins/batch-B01.md-1987-./tests/test_agent_edit_settings_contract.py:226:    # Slot 0 might be widget_0 (unknown), slot 1 might be control_after_generate
.oracle/checkins/batch-B01.md-1988-./tests/test_agent_edit_settings_contract.py:486:# ── failure paths — unknown field ────────────────────────────────────────
.oracle/checkins/batch-B01.md-1989-./tests/test_agent_edit_settings_contract.py:489:def test_batch_set_nonexistent_attribute_sampler_fails_with_unknown_target_field() -> None:
.oracle/checkins/batch-B01.md-1990-./tests/test_agent_edit_settings_contract.py:491:    ``unknown_target_field`` and diagnostic detail names the field and
.oracle/checkins/batch-B01.md-1991-./tests/test_agent_edit_settings_contract.py:502:    assert "unknown_target_field" in diag_codes
.oracle/checkins/batch-B01.md-1992-./tests/test_agent_edit_settings_contract.py:504:    field_diag = next(d for d in stmt.diagnostics if d.code == "unknown_target_field")
.oracle/checkins/batch-B01.md-1993-./tests/test_agent_edit_settings_contract.py:523:    """The text report for an unknown field edit mentions the rejected field name."""
.oracle/checkins/batch-B01.md-1994-./tests/test_agent_edit_settings_contract.py:530:    assert "unknown_target_field" in report
--
.oracle/checkins/batch-B01.md-2836-./vibecomfy/comfy_nodes/agent/_artifact_store.py:328:        raise ValueError(f"unknown transaction event type: {event_type!r}")
.oracle/checkins/batch-B01.md-2837-./tests/smoke/_runpod_helpers.py:74:            f"unknown gpu_type for budget cap: {gpu_type!r}; add it to HOURLY_USD with the runpod.io price."
.oracle/checkins/batch-B01.md-2838-./tests/smoke/_runpod_helpers.py:212:        code, stdout, stderr = await pod.exec_ssh(install_cmd, timeout=1800)
.oracle/checkins/batch-B01.md-2839-./tests/smoke/_runpod_helpers.py:226:    pod, template_ids: tuple[str, ...] | list[str], *, timeout: int = 1200
.oracle/checkins/batch-B01.md-2840-./tests/smoke/_runpod_helpers.py:287:    code, stdout, stderr = await pod.exec_ssh(cmd, timeout=timeout)
.oracle/checkins/batch-B01.md-2841-./tests/smoke/_runpod_helpers.py:303:    4090 launches when capacity is thin. Retry covers transient capacity windows.
.oracle/checkins/batch-B01.md-2842-./tests/smoke/_runpod_helpers.py:313:                # 30s, 60s, 90s, ... — RunPod capacity windows recover on tens-of-seconds.
.oracle/checkins/batch-B01.md-2843-./tests/test_agent_edit_parameter_tweak_fallback.py:209:def test_unknown_node_still_falls_back_to_widget_n() -> None:
.oracle/checkins/batch-B01.md:2844:./tests/test_agent_edit_parameter_tweak_fallback.py:231:    # The fallback should produce widget_N names for unknown nodes
.oracle/checkins/batch-B01.md-2845-./tests/test_reorganise_orchestrate.py:474:                    "id": "unknown",
.oracle/checkins/batch-B01.md-2846-./tests/test_porting_ui_emitter.py:1042:    # Capture comfy warnings about unknown nodes via logger
.oracle/checkins/batch-B01.md-2847-./tests/test_porting_ui_emitter.py:1044:    unknown_records: list[logging.LogRecord] = []
.oracle/checkins/batch-B01.md-2848-./tests/test_porting_ui_emitter.py:1049:                unknown_records.append(record)
.oracle/checkins/batch-B01.md-2849-./tests/test_porting_ui_emitter.py:1064:    assert len(unknown_records) == 0, (
.oracle/checkins/batch-B01.md-2850-./tests/test_porting_ui_emitter.py:1065:        f"convert_ui_to_api reported {len(unknown_records)} unknown node(s): "
.oracle/checkins/batch-B01.md-2851-./tests/test_porting_ui_emitter.py:1066:        f"{[r.getMessage() for r in unknown_records]}"
.oracle/checkins/batch-B01.md-2852-./tests/smoke/test_p1_runpod.py:38:        await pod.wait_ready(timeout=600)
--
.oracle/checkins/batch-B01.md-4662-./tests/test_porting_edit_apply.py:343:def test_resolve_delta_allows_unknown_target_socket_as_wildcard() -> None:
.oracle/checkins/batch-B01.md-4663-./tests/test_porting_edit_apply.py:367:def test_resolve_delta_rejects_unknown_add_node_class_before_any_mutation() -> None:
.oracle/checkins/batch-B01.md-4664-./tests/test_porting_edit_apply.py:386:    assert any(issue.code == "unknown_add_node_class_type" for issue in result.diagnostics)
.oracle/checkins/batch-B01.md-4665-./tests/test_porting_edit_apply.py:452:    assert not any(issue.code == "unknown_add_node_field" for issue in valid.diagnostics)
.oracle/checkins/batch-B01.md-4666-./tests/test_porting_edit_apply.py:549:def test_resolve_delta_unknown_add_node_field_lists_valid_fields_and_aliases() -> None:
.oracle/checkins/batch-B01.md-4667-./tests/test_porting_edit_apply.py:567:    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_add_node_field")
.oracle/checkins/batch-B01.md-4668-./tests/test_porting_edit_apply.py:576:def test_resolve_delta_unknown_set_node_field_lists_valid_fields_and_aliases() -> None:
.oracle/checkins/batch-B01.md-4669-./tests/test_porting_edit_apply.py:611:    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_node_field")
.oracle/checkins/batch-B01.md:4670:./tests/test_porting_edit_apply.py:622:def test_resolve_delta_unknown_ksampler_set_node_field_exposes_compact_names_and_omits_widget_N() -> None:
.oracle/checkins/batch-B01.md-4671-./tests/test_porting_edit_apply.py:623:    """When an unknown field is targeted on a KSampler node, valid_fields must
.oracle/checkins/batch-B01.md-4672-./tests/test_porting_edit_apply.py:664:    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_node_field")
.oracle/checkins/batch-B01.md-4673-./tests/test_porting_edit_apply.py:681:def test_resolve_delta_unknown_ksampler_set_node_field_includes_relevant_aliases() -> None:
.oracle/checkins/batch-B01.md-4674-./tests/test_porting_edit_apply.py:718:    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_node_field")
.oracle/checkins/batch-B01.md:4675:./tests/test_porting_edit_apply.py:730:def test_resolve_delta_unknown_ksampler_add_node_field_omits_covered_widget_N() -> None:
.oracle/checkins/batch-B01.md-4676-./tests/test_porting_edit_apply.py:731:    """When add_node targets a KSampler with an unknown field, the class-level
.oracle/checkins/batch-B01.md-4677-./tests/test_porting_edit_apply.py:749:    issue = next(issue for issue in result.diagnostics if issue.code == "unknown_add_node_field")
.oracle/checkins/batch-B01.md-4678-./tests/test_porting_edit_apply.py:883:    assert any(issue.code == "unknown_link_id" for issue in result.diagnostics)
.oracle/checkins/batch-B01.md-4679-./tests/test_porting_edit_apply.py:926:    assert any(issue.code == "unknown_add_node_class_type" for issue in result.diagnostics)
.oracle/checkins/batch-B01.md-4680-./tests/test_porting_edit_apply.py:1163:def test_apply_delta_keeps_unknown_intra_delta_node_target_as_clean_failure() -> None:
.oracle/checkins/batch-B01.md-4681-./tests/test_porting_edit_apply.py:1190:    assert any(issue.code == "unknown_node_target" and issue.detail.get("uid") == "n2" for issue in result.diagnostics)
.oracle/checkins/batch-B01.md-4682-./tests/test_porting_edit_apply.py:1375:def test_resolve_delta_rejects_unknown_add_node_group_anchor() -> None:
.oracle/checkins/batch-B01.md-4683-./tests/test_porting_edit_apply.py:1394:    assert any(issue.code == "unknown_group_anchor" for issue in result.diagnostics)
--
.oracle/briefs/area-04-schema-provider.md-1-Explore area: Schema-provider ownership — audit all provider construction sites.
.oracle/briefs/area-04-schema-provider.md-2-
.oracle/briefs/area-04-schema-provider.md:3:Context: B04 needs real schemas authoritative over provisional evidence. Four provisional-first sites are known (_frag_research.py:821, :874, edit_batch_repl.py:1115 + widget-name derivation); the plan must know ALL construction sites of CompositeSchemaProvider and similar providers, including future helper factories.
.oracle/briefs/area-04-schema-provider.md-4-
.oracle/briefs/area-04-schema-provider.md:5:Task: find every construction/ordering site of schema providers (search for CompositeSchemaProvider, ProvisionalSchemaProvider, schema_provider, provisional across vibecomfy/ and tests/), and report for each: file:line, argument order (real-first vs provisional-first), whether the invariant holds, and any helper factory that could reintroduce wrong precedence. Also check enum/combo validation at apply (porting/edit/apply_values.py, apply_resolve_*.py): is value_not_in_enum enforced before candidate mutation on both add and set paths? Verified facts, unknowns, risks, suggested approach. Ranked findings, <300 words.

exec
/bin/zsh -lc "sed -n '1,220p' .oracle/briefs-legacy/batch-B04.md; sed -n '812,870p' .oracle/checkins/G0.md; sed -n '1,100p' .oracle/findings/area-04-schema-provider.txt" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 738ms:
# B04 — Real-schema authority and apply-time combo validation

Executor: DeepSeek V4 Flash (normal executor).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. Put real schemas before provisional evidence everywhere.
   - Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py`, `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, and focused agent tests.
   - Change all applicable `CompositeSchemaProvider` construction so an existing live/real schema wins and provisional workflow/registry evidence fills only missing classes/fields. The `_frag_research.py:821` one-line swap already landed in G0 (rider); B04 covers the remaining inconsistent sites at `_frag_research.py:874` and `edit_batch_repl.py:1115` plus widget-name derivation.
   - Derive widget/input names presented to the batch editor from the winning real schema.

2. Enforce semantic combo membership before candidate mutation.
   - Touch as required: `vibecomfy/porting/edit/apply_values.py`, `vibecomfy/porting/edit/apply_resolve_base.py`, `vibecomfy/porting/edit/apply_resolve_add.py`, `tests/test_porting_edit_apply_values.py`, and focused end-to-end edit tests.
   - Ensure both add-node values and set-field values use the same validation. Invalid semantic choices are blocking `value_not_in_enum` issues and never reach a candidate. Retain the deliberate warning behavior for missing local asset filenames; do not turn asset inventory into a semantic enum.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_edit_apply_values.py \
  tests/test_porting_edit_apply.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  tests/test_comfy_nodes_agent_edit.py \
  -k 'real_schema_precedes_provisional or real_schema_widget_names_drive_batch_catalog or invalid_combo_rejected_before_candidate or asset_enum_accepts_missing_local_asset'
```

```bash
.venv/bin/python -m pytest -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py
```

## Acceptance criteria

- A conflicting provisional schema cannot shadow a real schema at any hydration site.
- Batch-visible widget names and choices come from the winning real schema.
- Invalid semantic combo values fail before graph mutation for both add and set paths; no candidate artifact contains the invalid value.
- Valid/coercible choices still land, and missing local model/asset filenames retain their existing warning-only policy.

## Report
"B04 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
## B04 — Real-schema authority and apply-time combo validation

**Executor:** DeepSeek V4 Flash
**Plan item:** 7

### Tasks

1. Put real schemas before provisional evidence everywhere.
   - Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py`, `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, and focused agent tests.
   - Change all applicable `CompositeSchemaProvider` construction so an existing live/real schema wins and provisional workflow/registry evidence fills only missing classes/fields. The `_frag_research.py:821` one-line swap already landed in **B02 (rider)**; B04 covers the remaining inconsistent sites at `_frag_research.py:874` and `edit_batch_repl.py:1115` plus widget-name derivation.
   - Derive widget/input names presented to the batch editor from the winning real schema.

2. Enforce semantic combo membership before candidate mutation.
   - Touch as required: `vibecomfy/porting/edit/apply_values.py`, `vibecomfy/porting/edit/apply_resolve_base.py`, `vibecomfy/porting/edit/apply_resolve_add.py`, `tests/test_porting_edit_apply_values.py`, and focused end-to-end edit tests.
   - Ensure both add-node values and set-field values use the same validation. Invalid semantic choices are blocking `value_not_in_enum` issues and never reach a candidate. Retain the deliberate warning behavior for missing local asset filenames; do not turn asset inventory into a semantic enum.

### Verification

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_edit_apply_values.py \
  tests/test_porting_edit_apply.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  tests/test_comfy_nodes_agent_edit.py \
  -k 'real_schema_precedes_provisional or real_schema_widget_names_drive_batch_catalog or invalid_combo_rejected_before_candidate or asset_enum_accepts_missing_local_asset'
```

Expected: all selected tests pass; invalid add and set controls yield blocking `value_not_in_enum`, while the missing-asset control remains a warning.

```bash
.venv/bin/python -m pytest -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py
```

Expected: exit 0.

### Acceptance criteria

- A conflicting provisional schema cannot shadow a real schema at any hydration site.
- Batch-visible widget names and choices come from the winning real schema.
- Invalid semantic combo values fail before graph mutation for both add and set paths; no candidate artifact contains the invalid value.
- Valid/coercible choices still land, and missing local model/asset filenames retain their existing warning-only policy.

### Formal checkpoint B04

Review provider ordering at every construction site, the add/set apply paths, asset-vs-semantic controls, and `git diff C05..C06`. Verdict: `PASS` or issue list; rework B04 until `PASS`.

---

## B05 — Transactional batch execution and bounded semantic repair

**Executor:** GPT-5.6 Sol
**Plan item:** 5

### Tasks

1. **[HARD] Make one model-authored batch an atomic transaction.**
   - Touch as required: `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, `vibecomfy/porting/edit/_parse_execute.py`, and focused tests in `tests/test_comfy_nodes_agent_edit.py` / `tests/test_comfy_nodes_agent_backend_spine.py`.
   - Snapshot the working IR/UI/rendered Python and relevant ledger before executing a batch. Any uncaught batch exception must restore the exact snapshot before another model turn or terminal response. Persist a bounded traceback and exception fingerprint without leaking secrets.

## Schema-provider ownership audit

**Verified facts**

Precedence: `CompositeSchemaProvider.get_schema` = first-match-wins; `schemas()` merges `reversed(providers)`, so the **first** provider also dominates the merged dict — real-first is the invariant for both views.

Baseline is real: `_frag_entrypoint.py:65` (`_default_runtime_schema_provider`), `routes.py:107/230` (`get_schema_provider("local")`). Wrong precedence enters only via the sites below.

**Sites (7)** — argument order:
1. `_frag_orchestration.py:434` — `(*providers)` = [Runtime, Authoring] — all real ✓
2. `_frag_research.py:821` — `(state, provisional)` real-first ✓ (structurally; poisoned if 874 ran earlier)
3. `_frag_research.py:922` — `(state, provisional)` real-first ✓ (same caveat)
4. `_frag_research.py:874` — `(provisional, state)` ✗ provisional-first (known)
5. `_frag_response_contract.py:793` — `(provisional, session.schema_provider)` ✗ **new**; sets both session AND state → poisons session across turns
6. `_frag_batch_loop.py:910` — `(provisional, state)` ✗ **new**
7. `edit_batch_repl.py:1115` — `(provisional, state)` ✗ known (`_hydrate_actionable_registry_dependencies`)

Helper factories (`get_schema_provider`, `get_authoring_schema_provider`, `_default_runtime_schema_provider`) never inject provisional — safe. No shared "wrap-with-provisional" helper exists; each bug site hand-rolls the ordering, which is why it drifts.

**Enum/combo at apply — both paths safe:**
- Set (`apply_resolve_base.py:184`): `control_after_generate` check (:321) + `_validate_literal_value` (:335) run **before** any mutation; errors → `(None, issues)`.
- Add (`apply_resolve_add.py:39`): per-field validation (:199), blocks on error (:209) before `ResolvedAddNodeSpec` builds.
- Caveat: `_validate_literal_value` returns `[]` when `spec is None` (apply_values.py:20) — so a provisional-first schema with empty `choices` makes `value_not_in_enum` vacuous. `_coerce_choice_value` and asset-enum warning are soft escapes.

**Widget-name derivation:** `contracts.py:2527` → compile-time `WIDGET_SCHEMA` table (aliases.py:129) — provider-independent; fallback only via `apply_positional_widget_aliases`. Low risk.

**Unknowns:** intra-turn order of 874 vs 821/922; session persistence across turns (amplifies :793).

**Ranked findings:** (1) 793 session-poison, (2) 874, (3) 910, (4) 1115, (5) 821/922 conditional.

**Suggested approach:** introduce one factory `prepend_provisional(provider, candidates)` enforcing real-first, migrate all 4 bug sites, assert order in tests.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -s -p no:cacheprovider -p no:rerunfailures -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
2026-08-13T14:36:10.716554Z ERROR codex_core::tools::router: error=write_stdin failed: stdin is closed for this session; rerun exec_command with tty=true to keep stdin open
codex
The read-only workaround succeeded: the dedicated B04 precedence/cross-turn selection reports 10 passed, and the complete apply-mechanism files report 61 passed, 1 skipped. Both pytest processes printed final summaries but leave imported ComfyUI resources alive after teardown in this environment; that does not affect test outcomes. I’m running the executor’s exact 45-test filter now to independently confirm its count.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -s -p no:cacheprovider -p no:rerunfailures -q tests/test_comfy_nodes_agent_edit.py tests/test_comfy_nodes_agent_backend_spine.py -k 'schema or precedence or provisional or real_schema or widget or cross_turn'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 168516ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
[32m[INFO][0m Set vram state to: NORMAL_VRAM
objc[41654]: Class AVFFrameReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x123fc43a8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x134bec3a8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
objc[41654]: Class AVFAudioReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x123fc43f8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x134bec3f8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
[32m[INFO][0m PromptServer imported; registering VibeComfy routes.
[1m[33m[WARNING][0m Could not register VibeComfy agent routes (cannot import name 'parse_edit_delta' from partially initialized module 'vibecomfy.porting.edit.ops' (most likely due to a circular import) (/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/ops.py)); the ComfyUI server may not be available. POST /vibecomfy/agent-edit and /vibecomfy/agent/status will not be served.
..................................s...........................
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1434
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: timeout

    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

.venv/lib/python3.11/site-packages/torch/library.py:361
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/torch/library.py:361: UserWarning: Warning only once for all operators,  other operators may also be overridden.
    Overriding a previously registered kernel for the same operator and the same dispatch key
    operator: aten::mm(Tensor self, Tensor mat2) -> Tensor
      registered at /Users/runner/work/pytorch/pytorch/build/aten/src/ATen/RegisterSchema.cpp:6
    dispatch key: MPS
    previous kernel: registered at /Users/runner/work/pytorch/pytorch/aten/src/ATen/LegacyBatchingRegistrations.cpp:1076
         new kernel: registered at /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/fp4_fp8_for_torch_mps/ops.py:7 (Triggered internally at /Users/runner/work/pytorch/pytorch/aten/src/ATen/core/dispatch/OperatorEntry.cpp:215.)
    self.m.impl(

.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32: DeprecationWarning: SelectableGroups dict interface is deprecated. Use select.
    return EntryPoints(ep for group_eps in eps.values() for ep in group_eps)

.venv/lib/python3.11/site-packages/comfy/model_management.py:237
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/comfy/model_management.py:237: UserWarning: torch.cuda.current_device() did not return a device, returning a CPU torch device
    warnings.warn("torch.cuda.current_device() did not return a device, returning a CPU torch device")

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

tests/conftest.py:352
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/conftest.py:352: PytestUnknownMarkWarning: Unknown pytest.mark.flaky - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    flaky_marker = pytest.mark.flaky(reruns=1, reruns_delay=10)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
61 passed, 1 skipped, 7 warnings in 120.03s (0:02:00)
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

codex
The exact 45-test selection confirms 38 runnable tests passed; the remaining 7 errored only because they require `tmp_path`, which this enforced read-only sandbox cannot create. All B04-added precedence and cross-turn tests were among the 38 passes. I’m finishing with the quarantined API-snapshot provenance and an exact changed-file/scope audit.
exec
/bin/zsh -lc "rg -n -C3 'test_public_module_all_snapshots_are_intentional|test_api_surface|emitter-parity-surface|owner' tests/quarantine/emitter_parity_surface.txt .oracle 2>/dev/null | head -160" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "git log -1 --format='%h %ad %s' --date=iso -- tests/quarantine/emitter_parity_surface.txt; git blame -L 1,120 tests/quarantine/emitter_parity_surface.txt | rg 'test_api_surface|public_module|emitter-parity' | head -30" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git diff --numstat f2661b01..ff6ae9c8; git diff --name-only f2661b01..ff6ae9c8 -- vibecomfy/workflow.py; git diff --check f2661b01..ff6ae9c8; git status --short' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "nl -ba vibecomfy/schema/__init__.py | sed -n '1,75p'; nl -ba tests/test_api_surface.py | sed -n '1,48p'; rg -n '"'^__all__|RawWidgetPayload|WorkflowSource'"' vibecomfy/workflow.py | tail -30" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 351ms:
     1	from __future__ import annotations
     2
     3	from .call_validation import NodeCallValidationIssue, NodeCallValidationReport, validate_node_call
     4	from .provider import (
     5	    AuthoringSchemaProvider,
     6	    InputSpec,
     7	    CompositeSchemaProvider,
     8	    ConversionSchemaProvider,
     9	    LocalSchemaProvider,
    10	    NodeSchema,
    11	    ObjectInfoSchemaProvider,
    12	    OutputSpec,
    13	    ProvisionalRegistrySchemaProvider,
    14	    RuntimeSchemaProvider,
    15	    SchemaIndexError,
    16	    SchemaProvider,
    17	    SchemaSourceInfo,
    18	    SourceScanWarning,
    19	    SourceSchemaProvider,
    20	    get_authoring_schema_provider,
    21	    get_schema_provider,
    22	    is_workflow_stub_schema,
    23	    schema_for,
    24	    schema_registry_empty,
    25	    schemas_for,
    26	    with_provisional_gap_filler,
    27	)
    28	from .validate import socket_types_compatible
    29
    30	__all__ = [
    31	    "AuthoringSchemaProvider",
    32	    "InputSpec",
    33	    "NodeCallValidationIssue",
    34	    "NodeCallValidationReport",
    35	    "CompositeSchemaProvider",
    36	    "ConversionSchemaProvider",
    37	    "LocalSchemaProvider",
    38	    "NodeSchema",
    39	    "ObjectInfoSchemaProvider",
    40	    "OutputSpec",
    41	    "ProvisionalRegistrySchemaProvider",
    42	    "RuntimeSchemaProvider",
    43	    "SchemaIndexError",
    44	    "SchemaProvider",
    45	    "SchemaSourceInfo",
    46	    "SourceScanWarning",
    47	    "SourceSchemaProvider",
    48	    "get_authoring_schema_provider",
    49	    "get_schema_provider",
    50	    "is_workflow_stub_schema",
    51	    "schema_for",
    52	    "schema_registry_empty",
    53	    "schemas_for",
    54	    "socket_types_compatible",
    55	    "validate_node_call",
    56	    "with_provisional_gap_filler",
    57	]
     1	from __future__ import annotations
     2
     3	import importlib
     4
     5
     6	PUBLIC_EXPORT_SNAPSHOTS = {
     7	    "vibecomfy": [
     8	        "Artifact", "Image", "Video", "Audio", "Latent", "Mask", "Handle",
     9	        "VibeWorkflow", "RawWidgetPayload", "VibeNode", "VibeEdge", "VibeInput", "VibeOutput",
    10	        "WorkflowRequirements", "WorkflowSource", "ValidationIssue", "ValidationReport",
    11	        "workflow_from_file", "workflow_from_id", "workflow_from_template", "workflow_from_ready",
    12	        "ready_template_ids", "load_workflow_any", "load_workflow_json", "load_template",
    13	        "find_repo_root", "ensure_plugins_loaded", "image", "video", "blocks", "patches",
    14	        "router", "run", "run_sync", "run_embedded", "run_embedded_sync",
    15	    ],
    16	    "vibecomfy.workflow": [
    17	        "OPAQUE_COMPONENT_CLASS_RE", "ValidationIssue", "ValidationReport", "VibeEdge",
    18	        "VibeInput", "VibeNode", "VibeOutput", "VibeWorkflow", "WorkflowRequirements",
    19	        "WorkflowSource",
    20	    ],
    21	    "vibecomfy.handles": ["Handle"],
    22	    "vibecomfy.errors": [
    23	        "ContextVarBindingError", "ConversionParityError", "DriftError", "ModelAssetError",
    24	        "QueueError", "RuntimeNodeError", "SchemaValidationError", "SubgraphFreshnessError",
    25	        "VibeComfyError",
    26	    ],
    27	    "vibecomfy.schema": [
    28	        "AuthoringSchemaProvider", "InputSpec", "NodeCallValidationIssue",
    29	        "NodeCallValidationReport", "CompositeSchemaProvider", "ConversionSchemaProvider",
    30	        "LocalSchemaProvider", "NodeSchema", "ObjectInfoSchemaProvider", "OutputSpec",
    31	        "RuntimeSchemaProvider", "SchemaIndexError", "SchemaProvider", "SchemaSourceInfo",
    32	        "SourceSchemaProvider", "get_authoring_schema_provider", "get_schema_provider",
    33	        "schema_for", "schema_registry_empty", "schemas_for", "socket_types_compatible",
    34	        "validate_node_call", "with_provisional_gap_filler",
    35	    ],
    36	    "vibecomfy.artifacts": ["Artifact", "ArtifactKind", "Image", "Video", "Audio", "Latent", "Mask"],
    37	    "vibecomfy.templates": [
    38	        "InputSpec", "ModelAsset", "ReadyMetadata", "_at", "_current_workflow_or_raise",
    39	        "_derive_output_kind", "finalize", "finalize_ready", "new_workflow", "node",
    40	        "template_input", "template_output",
    41	    ],
    42	}
    43
    44
    45	def test_public_module_all_snapshots_are_intentional() -> None:
    46	    for module_name, expected in PUBLIC_EXPORT_SNAPSHOTS.items():
    47	        module = importlib.import_module(module_name)
    48	        assert list(module.__all__) == expected
56:class WorkflowSource:
73:class RawWidgetPayload:
90:    raw_widgets: RawWidgetPayload | None = None
175:    source: WorkflowSource
1474:__all__ = [
1476:    "RawWidgetPayload",
1485:    "WorkflowSource",

 succeeded in 457ms:
tests/quarantine/emitter_parity_surface.txt:1:# owner: emitter-parity-surface
tests/quarantine/emitter_parity_surface.txt-2-# reason: pre-existing emitter, parity, snapshot, and workflow-lens failures from the legacy baseline
tests/quarantine/emitter_parity_surface.txt-3-# audit: migrated from tests/known_failures.txt during sprint-3 diagnostics T7
tests/quarantine/emitter_parity_surface.txt-4-
tests/quarantine/emitter_parity_surface.txt-5-tests/parity/test_independent_readback.py::test_independent_readback_corpus
tests/quarantine/emitter_parity_surface.txt:6:tests/test_api_surface.py::test_public_module_all_snapshots_are_intentional
tests/quarantine/emitter_parity_surface.txt-7-tests/test_porting_emitter.py::test_emit_ready_template_python_has_ready_metadata_contract
tests/quarantine/emitter_parity_surface.txt-8-tests/test_porting_emitter.py::test_generated_template_not_formatted_missing_section_comments
tests/quarantine/emitter_parity_surface.txt-9-tests/test_porting_emitter.py::test_ready_template_build_spacing_for_multiline_and_packed_simple_calls
--
.oracle/tasklist.md-341-   - source-workflow per-file hashes and `primary_source`;
.oracle/tasklist.md-342-   - one aggregate corpus digest;
.oracle/tasklist.md-343-   - commit and configuration digests.
.oracle/tasklist.md:344:3. Extend the B02 preservation summary or make B09 preflight the sole corpus-hash owner. Do not maintain two hash systems.
.oracle/tasklist.md-345-4. Embed commit, selection, configuration, and corpus digests in `run_summary.json`.
.oracle/tasklist.md-346-5. Cite report evidence by stable scenario ID and SHA, never checkout-relative artifact paths.
.oracle/tasklist.md-347-6. Run deterministic gates:
--
.oracle/findings/area-04-schema-provider.txt:1:## Schema-provider ownership audit
.oracle/findings/area-04-schema-provider.txt-2-
.oracle/findings/area-04-schema-provider.txt-3-**Verified facts**
.oracle/findings/area-04-schema-provider.txt-4-
--
.oracle/briefs/area-04-schema-provider.md:1:Explore area: Schema-provider ownership — audit all provider construction sites.
.oracle/briefs/area-04-schema-provider.md-2-
.oracle/briefs/area-04-schema-provider.md-3-Context: B04 needs real schemas authoritative over provisional evidence. Four provisional-first sites are known (_frag_research.py:821, :874, edit_batch_repl.py:1115 + widget-name derivation); the plan must know ALL construction sites of CompositeSchemaProvider and similar providers, including future helper factories.
.oracle/briefs/area-04-schema-provider.md-4-
--
.oracle/checkins/batch-B04.md-24-
.oracle/checkins/batch-B04.md-25-## Executor evidence
.oracle/checkins/batch-B04.md-26-
.oracle/checkins/batch-B04.md:27:- New helper `with_provisional_gap_filler(authoritative, provisional)` in `vibecomfy/schema/provider.py` (+ re-export in `schema/__init__.py`, + snapshot update in `test_api_surface.py`).
.oracle/checkins/batch-B04.md-28-- All 7 construction sites now real-first through the helper: `_frag_research.py` (:821, :874, :922), `_frag_response_contract.py:793` (cross-turn — no longer poisons session), `_frag_batch_loop.py:910`, `edit_batch_repl.py:1116`.
.oracle/checkins/batch-B04.md-29-- Focused tests: 45 passed (`tests/test_comfy_nodes_agent_edit.py` + backend_spine, -k schema/precedence/provisional/real_schema/widget/cross_turn).
.oracle/checkins/batch-B04.md:30:- Broader slice: 62 passed / 1 failed / 1 skipped — the 1 failure is `test_api_surface.py::test_public_module_all_snapshots_are_intentional`, which is in the PRE-EXISTING quarantine baseline `tests/quarantine/emitter_parity_surface.txt` (owner emitter-parity-surface, reason: legacy baseline failures). Verified: that snapshot delta concerns `RawWidgetPayload`/`WorkflowSource` in the workflow lens, predates B04, and `vibecomfy/workflow.py` is untouched by this range.
.oracle/checkins/batch-B04.md-31-
.oracle/checkins/batch-B04.md-32-## Review focus (adversarial)
.oracle/checkins/batch-B04.md-33-
--
.oracle/checkins/batch-B04.md-350-tests/test_comfy_nodes_agent_edit.py:20457:    assert isinstance(baseline, CompositeSchemaProvider)
.oracle/checkins/batch-B04.md-351-tests/test_schema.py:20:    CompositeSchemaProvider,
.oracle/checkins/batch-B04.md-352-tests/test_schema.py:92:    provider = CompositeSchemaProvider(
.oracle/checkins/batch-B04.md:353:tests/test_api_surface.py:29:        "NodeCallValidationReport", "CompositeSchemaProvider", "ConversionSchemaProvider",
.oracle/checkins/batch-B04.md:354:tests/test_api_surface.py:34:        "validate_node_call", "with_provisional_gap_filler",
.oracle/checkins/batch-B04.md-355-vibecomfy/comfy_nodes/agent/_frag_research.py:811:            from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
.oracle/checkins/batch-B04.md-356-vibecomfy/comfy_nodes/agent/_frag_research.py:821:                state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
.oracle/checkins/batch-B04.md-357-vibecomfy/comfy_nodes/agent/_frag_research.py:838:        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler
--
.oracle/checkins/batch-B04.md-381- succeeded in 324ms:
.oracle/checkins/batch-B04.md-382-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-B04.md-383- .oracle/briefs/batch-B04.md                        |  42 ++
.oracle/checkins/batch-B04.md:384: tests/test_api_surface.py                          |   2 +-
.oracle/checkins/batch-B04.md-385- tests/test_comfy_nodes_agent_edit.py               | 511 +++++++++++++++++++++
.oracle/checkins/batch-B04.md-386- vibecomfy/comfy_nodes/agent/_frag_batch_loop.py    |   4 +-
.oracle/checkins/batch-B04.md-387- vibecomfy/comfy_nodes/agent/_frag_research.py      |  12 +-
--
.oracle/checkins/batch-B04.md-392- 9 files changed, 585 insertions(+), 12 deletions(-)
.oracle/checkins/batch-B04.md-393-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-B04.md-394-A	.oracle/briefs/batch-B04.md
.oracle/checkins/batch-B04.md:395:M	tests/test_api_surface.py
.oracle/checkins/batch-B04.md-396-M	tests/test_comfy_nodes_agent_edit.py
.oracle/checkins/batch-B04.md-397-M	vibecomfy/comfy_nodes/agent/_frag_batch_loop.py
.oracle/checkins/batch-B04.md-398-M	vibecomfy/comfy_nodes/agent/_frag_research.py
--
.oracle/checkins/batch-B04.md-403-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-B04.md-404-
.oracle/checkins/batch-B04.md-405-exec
.oracle/checkins/batch-B04.md:406:/bin/zsh -lc 'git diff --find-renames --find-copies --unified=80 f2661b01..ff6ae9c8 -- vibecomfy/schema/provider.py vibecomfy/schema/__init__.py vibecomfy/comfy_nodes/agent/_frag_research.py vibecomfy/comfy_nodes/agent/_frag_response_contract.py vibecomfy/comfy_nodes/agent/_frag_batch_loop.py vibecomfy/comfy_nodes/agent/edit_batch_repl.py tests/test_api_surface.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-407-exec
.oracle/checkins/batch-B04.md-408-/bin/zsh -lc "nl -ba vibecomfy/schema/provider.py | sed -n '470,550p;1020,1075p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-409-exec
--
.oracle/checkins/batch-B04.md-412-/bin/zsh -lc "sed -n '1,240p' .oracle/briefs/batch-B04.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-413- succeeded in 290ms:
.oracle/checkins/batch-B04.md-414-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-B04.md:415:diff --git a/tests/test_api_surface.py b/tests/test_api_surface.py
.oracle/checkins/batch-B04.md-416-index d0540f23..ab1f19fc 100644
.oracle/checkins/batch-B04.md:417:--- a/tests/test_api_surface.py
.oracle/checkins/batch-B04.md:418:+++ b/tests/test_api_surface.py
.oracle/checkins/batch-B04.md-419-@@ -1,55 +1,55 @@
.oracle/checkins/batch-B04.md-420- from __future__ import annotations
.oracle/checkins/batch-B04.md-421-
--
.oracle/checkins/batch-B04.md-462- }
.oracle/checkins/batch-B04.md-463-
.oracle/checkins/batch-B04.md-464-
.oracle/checkins/batch-B04.md:465: def test_public_module_all_snapshots_are_intentional() -> None:
.oracle/checkins/batch-B04.md-466-     for module_name, expected in PUBLIC_EXPORT_SNAPSHOTS.items():
.oracle/checkins/batch-B04.md-467-         module = importlib.import_module(module_name)
.oracle/checkins/batch-B04.md-468-         assert list(module.__all__) == expected
--
.oracle/checkins/batch-B04.md-4430-.oracle/checkins/batch-B04.md-24-
.oracle/checkins/batch-B04.md-4431-.oracle/checkins/batch-B04.md-25-## Executor evidence
.oracle/checkins/batch-B04.md-4432-.oracle/checkins/batch-B04.md-26-
.oracle/checkins/batch-B04.md:4433:.oracle/checkins/batch-B04.md-27-- New helper `with_provisional_gap_filler(authoritative, provisional)` in `vibecomfy/schema/provider.py` (+ re-export in `schema/__init__.py`, + snapshot update in `test_api_surface.py`).
.oracle/checkins/batch-B04.md-4434-.oracle/checkins/batch-B04.md-28-- All 7 construction sites now real-first through the helper: `_frag_research.py` (:821, :874, :922), `_frag_response_contract.py:793` (cross-turn — no longer poisons session), `_frag_batch_loop.py:910`, `edit_batch_repl.py:1116`.
.oracle/checkins/batch-B04.md-4435-.oracle/checkins/batch-B04.md-29-- Focused tests: 45 passed (`tests/test_comfy_nodes_agent_edit.py` + backend_spine, -k schema/precedence/provisional/real_schema/widget/cross_turn).
.oracle/checkins/batch-B04.md:4436:.oracle/checkins/batch-B04.md-30-- Broader slice: 62 passed / 1 failed / 1 skipped — the 1 failure is `test_api_surface.py::test_public_module_all_snapshots_are_intentional`, which is in the PRE-EXISTING quarantine baseline `tests/quarantine/emitter_parity_surface.txt` (owner emitter-parity-surface, reason: legacy baseline failures). Verified: that snapshot delta concerns `RawWidgetPayload`/`WorkflowSource` in the workflow lens, predates B04, and `vibecomfy/workflow.py` is untouched by this range.
.oracle/checkins/batch-B04.md-4437-.oracle/checkins/batch-B04.md-31-
.oracle/checkins/batch-B04.md-4438-.oracle/checkins/batch-B04.md-32-## Review focus (adversarial)
.oracle/checkins/batch-B04.md-4439-.oracle/checkins/batch-B04.md-33-
--
.oracle/checkins/batch-B04.md-4908-.oracle/checkins/batch-B01.md-4682-./tests/test_porting_edit_apply.py:1375:def test_resolve_delta_rejects_unknown_add_node_group_anchor() -> None:
.oracle/checkins/batch-B04.md-4909-.oracle/checkins/batch-B01.md-4683-./tests/test_porting_edit_apply.py:1394:    assert any(issue.code == "unknown_group_anchor" for issue in result.diagnostics)
.oracle/checkins/batch-B04.md-4910---
.oracle/checkins/batch-B04.md:4911:.oracle/briefs/area-04-schema-provider.md-1-Explore area: Schema-provider ownership — audit all provider construction sites.
.oracle/checkins/batch-B04.md-4912-.oracle/briefs/area-04-schema-provider.md-2-
.oracle/checkins/batch-B04.md-4913-.oracle/briefs/area-04-schema-provider.md:3:Context: B04 needs real schemas authoritative over provisional evidence. Four provisional-first sites are known (_frag_research.py:821, :874, edit_batch_repl.py:1115 + widget-name derivation); the plan must know ALL construction sites of CompositeSchemaProvider and similar providers, including future helper factories.
.oracle/checkins/batch-B04.md-4914-.oracle/briefs/area-04-schema-provider.md-4-
--
.oracle/checkins/batch-B04.md-5017-   - Touch as required: `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, `vibecomfy/porting/edit/_parse_execute.py`, and focused tests in `tests/test_comfy_nodes_agent_edit.py` / `tests/test_comfy_nodes_agent_backend_spine.py`.
.oracle/checkins/batch-B04.md-5018-   - Snapshot the working IR/UI/rendered Python and relevant ledger before executing a batch. Any uncaught batch exception must restore the exact snapshot before another model turn or terminal response. Persist a bounded traceback and exception fingerprint without leaking secrets.
.oracle/checkins/batch-B04.md-5019-
.oracle/checkins/batch-B04.md:5020:## Schema-provider ownership audit
.oracle/checkins/batch-B04.md-5021-
.oracle/checkins/batch-B04.md-5022-**Verified facts**
.oracle/checkins/batch-B04.md-5023-
--
.oracle/checkins/batch-B04.md-5104-codex
.oracle/checkins/batch-B04.md-5105-The exact 45-test selection confirms 38 runnable tests passed; the remaining 7 errored only because they require `tmp_path`, which this enforced read-only sandbox cannot create. All B04-added precedence and cross-turn tests were among the 38 passes. I’m finishing with the quarantined API-snapshot provenance and an exact changed-file/scope audit.
.oracle/checkins/batch-B04.md-5106-exec
.oracle/checkins/batch-B04.md:5107:/bin/zsh -lc "rg -n -C3 'test_public_module_all_snapshots_are_intentional|test_api_surface|emitter-parity-surface|owner' tests/quarantine/emitter_parity_surface.txt .oracle 2>/dev/null | head -160" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-5108-exec
.oracle/checkins/batch-B04.md:5109:/bin/zsh -lc "git log -1 --format='%h %ad %s' --date=iso -- tests/quarantine/emitter_parity_surface.txt; git blame -L 1,120 tests/quarantine/emitter_parity_surface.txt | rg 'test_api_surface|public_module|emitter-parity' | head -30" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-5110-exec
.oracle/checkins/batch-B04.md-5111-/bin/zsh -lc 'git diff --numstat f2661b01..ff6ae9c8; git diff --name-only f2661b01..ff6ae9c8 -- vibecomfy/workflow.py; git diff --check f2661b01..ff6ae9c8; git status --short' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-5112-exec
.oracle/checkins/batch-B04.md:5113:/bin/zsh -lc "nl -ba vibecomfy/schema/__init__.py | sed -n '1,75p'; nl -ba tests/test_api_surface.py | sed -n '1,48p'; rg -n '"'^__all__|RawWidgetPayload|WorkflowSource'"' vibecomfy/workflow.py | tail -30" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
.oracle/checkins/batch-B04.md-5114- succeeded in 351ms:
.oracle/checkins/batch-B04.md-5115-     1	from __future__ import annotations
.oracle/checkins/batch-B04.md-5116-     2
--
.oracle/checkins/batch-B04.md-5213-    42	}
.oracle/checkins/batch-B04.md-5214-    43
.oracle/checkins/batch-B04.md-5215-    44
.oracle/checkins/batch-B04.md:5216:    45	def test_public_module_all_snapshots_are_intentional() -> None:
.oracle/checkins/batch-B04.md-5217-    46	    for module_name, expected in PUBLIC_EXPORT_SNAPSHOTS.items():
.oracle/checkins/batch-B04.md-5218-    47	        module = importlib.import_module(module_name)
.oracle/checkins/batch-B04.md-5219-    48	        assert list(module.__all__) == expected
--
.oracle/plan.md-341-   - source-workflow per-file hashes and `primary_source`;
.oracle/plan.md-342-   - one aggregate corpus digest;
.oracle/plan.md-343-   - commit and configuration digests.
.oracle/plan.md:344:3. Extend the B02 preservation summary or make B09 preflight the sole corpus-hash owner. Do not maintain two hash systems.
.oracle/plan.md-345-4. Embed commit, selection, configuration, and corpus digests in `run_summary.json`.
.oracle/plan.md-346-5. Cite report evidence by stable scenario ID and SHA, never checkout-relative artifact paths.
.oracle/plan.md-347-6. Run deterministic gates:
--
.oracle/checkins/batch-D13.md-481-   - source-workflow per-file hashes and `primary_source`;
.oracle/checkins/batch-D13.md-482-   - one aggregate corpus digest;
.oracle/checkins/batch-D13.md-483-   - commit and configuration digests.
.oracle/checkins/batch-D13.md:484:3. Extend the B02 preservation summary or make B09 preflight the sole corpus-hash owner. Do not maintain two hash systems.
.oracle/checkins/batch-D13.md-485-4. Embed commit, selection, configuration, and corpus digests in `run_summary.json`.
.oracle/checkins/batch-D13.md-486-5. Cite report evidence by stable scenario ID and SHA, never checkout-relative artifact paths.
.oracle/checkins/batch-D13.md-487-6. Run deterministic gates:
--
.oracle/checkins/batch-B01.md-3094-./tests/test_comfy_nodes_agent_backend_spine.py:7522:    assert plan["diagnostics"][1]["op"] == "unknown_future_op"
.oracle/checkins/batch-B01.md-3095-./tests/test_comfy_nodes_agent_backend_spine.py:8207:    #    V2 turn into "unknown" state).  Also delete the turn's structural
.oracle/checkins/batch-B01.md-3096-./tests/test_comfy_nodes_agent_backend_spine.py:8383:    #    pending V2 turn into "unknown" state.  Delete the turn's structural
.oracle/checkins/batch-B01.md:3097:./tests/test_comfy_nodes_agent_backend_spine.py:9725:def test_session_lock_live_owner_timeout(tmp_path: Path, monkeypatch) -> None:

 succeeded in 995ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
42	0	.oracle/briefs/batch-B04.md
1	1	tests/test_api_surface.py
511	0	tests/test_comfy_nodes_agent_edit.py
2	2	vibecomfy/comfy_nodes/agent/_frag_batch_loop.py
6	6	vibecomfy/comfy_nodes/agent/_frag_research.py
2	2	vibecomfy/comfy_nodes/agent/_frag_response_contract.py
2	1	vibecomfy/comfy_nodes/agent/edit_batch_repl.py
2	0	vibecomfy/schema/__init__.py
17	0	vibecomfy/schema/provider.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-B04.md

 succeeded in 1693ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
1b71a167 2026-06-21 03:01:48 +0200 fix(sprint-3): harden git_utils mock tolerance, relax port stderr assertion, scope offline failures into quarantine
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
ea4243aab (POM 2026-06-21 02:05:56 +0200   1) # owner: emitter-parity-surface
ea4243aab (POM 2026-06-21 02:05:56 +0200   6) tests/test_api_surface.py::test_public_module_all_snapshots_are_intentional

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/edit/apply_values.py | sed -n '1,62p;135,190p'; nl -ba vibecomfy/porting/edit/apply_resolve_add.py | sed -n '165,225p;305,355p'; nl -ba vibecomfy/porting/edit/apply_resolve_base.py | sed -n '300,355p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 258ms:
     1	from __future__ import annotations
     2
     3	import re
     4	from typing import Any
     5
     6	from vibecomfy.porting.edit.apply_types import _issue
     7	from vibecomfy.porting.report import PortIssue
     8	from vibecomfy.porting.resolution import _normalize_type
     9	from vibecomfy.schema import InputSpec
    10
    11
    12	def _validate_literal_value(
    13	    *,
    14	    value: Any,
    15	    spec: InputSpec | None,
    16	    class_type: str,
    17	    input_name: str,
    18	    context: str,
    19	) -> list[PortIssue]:
    20	    if spec is None:
    21	        return []
    22	    issues: list[PortIssue] = []
    23	    choices = getattr(spec, "choices", None) or []
    24	    if choices and value not in choices and _coerce_choice_value(value, choices) is _NO_MATCH:
    25	        detail = {
    26	            "class_type": class_type,
    27	            "input": input_name,
    28	            "value": value,
    29	            "choices": list(choices),
    30	        }
    31	        if _is_asset_enum(value=value, spec=spec, input_name=input_name, choices=choices):
    32	            issues.append(
    33	                _issue(
    34	                    "asset_not_installed",
    35	                    f"{context} accepted {class_type}.{input_name}: asset {value!r} is not in the declared local choices.",
    36	                    severity="warning",
    37	                    detail=detail,
    38	                )
    39	            )
    40	        else:
    41	            issues.append(
    42	                _issue(
    43	                    "value_not_in_enum",
    44	                    f"{context} rejected {class_type}.{input_name}: value {value!r} is not in the declared enum.",
    45	                    detail=detail,
    46	                )
    47	            )
    48	    min_value = getattr(spec, "min", None)
    49	    max_value = getattr(spec, "max", None)
    50	    if min_value is not None or max_value is not None:
    51	        numeric = _as_number(value)
    52	        if numeric is not None and (
    53	            (min_value is not None and numeric < float(min_value))
    54	            or (max_value is not None and numeric > float(max_value))
    55	        ):
    56	            issues.append(
    57	                _issue(
    58	                    "value_out_of_range",
    59	                    f"{context} rejected {class_type}.{input_name}: value {value!r} is outside the declared range.",
    60	                    detail={
    61	                        "class_type": class_type,
    62	                        "input": input_name,
   135	    ".bin",
   136	    ".ckpt",
   137	    ".gguf",
   138	    ".pt",
   139	    ".safetensors",
   140	    ".sft",
   141	)
   142	_CONSTRAINED_FIELD_SUFFIXES = frozenset({"format", "method", "mode", "option", "preset", "type"})
   143
   144
   145	def _is_asset_enum(*, value: Any, spec: InputSpec, input_name: str, choices: list[Any]) -> bool:
   146	    if not isinstance(value, str):
   147	        return False
   148
   149	    # ComfyUI exposes installed asset files as enums. Treat an enum as an asset
   150	    # selector when its field/type names identify an asset, its installed choices
   151	    # look path-shaped, or (conservatively for unknown schemas) the proposed string
   152	    # itself is unmistakably a file/path reference.
   153	    field_identifier = _normalized_identifier(input_name)
   154	    field_name_signals_asset = any(word in field_identifier for word in _ASSET_FIELD_WORDS) and not any(
   155	        field_identifier.endswith(suffix) for suffix in _CONSTRAINED_FIELD_SUFFIXES
   156	    )
   157	    type_identifier = _normalized_identifier(str(getattr(spec, "type", "") or ""))
   158	    if field_name_signals_asset or any(word in type_identifier for word in _ASSET_FIELD_WORDS):
   159	        return True
   160	    if any(isinstance(choice, str) and _looks_like_asset_reference(choice) for choice in choices):
   161	        return True
   162	    return _looks_like_asset_reference(value)
   163
   164
   165	def _normalized_identifier(value: str) -> str:
   166	    return re.sub(r"[^a-z0-9]+", "", value.lower())
   167
   168
   169	def _looks_like_asset_reference(value: str) -> bool:
   170	    normalized = value.strip().replace("\\", "/").lower()
   171	    path_without_query = normalized.split("?", 1)[0].split("#", 1)[0]
   172	    return (
   173	        "/" in normalized
   174	        or normalized.startswith(("http://", "https://"))
   175	        or path_without_query.endswith(_ASSET_EXTENSIONS)
   176	    )
   177
   178
   179	def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
   180	    if isinstance(value, str):
   181	        normalized = value.replace("\\", "/")
   182	        for choice in choices:
   183	            if isinstance(choice, str) and choice.replace("\\", "/") == normalized:
   184	                return choice
   185	    return _NO_MATCH
   165	            )
   166	            hint = format_valid_field_hint(field_detail)
   167	            message = f"{op.class_type} does not declare field {field_name!r}."
   168	            if hint:
   169	                message = f"{message} {hint}"
   170	            issues.append(
   171	                _issue(
   172	                    "unknown_add_node_field",
   173	                    message,
   174	                    detail={
   175	                        "scope_path": op.scope_path,
   176	                        "class_type": op.class_type,
   177	                        "field": field_name,
   178	                        **field_detail,
   179	                    },
   180	                )
   181	            )
   182	            continue
   183	        if input_spec_is_socket_only(spec):
   184	            hint, hint_detail = socket_source_hint(scope.graph, getattr(spec, "type", None))
   185	            issues.append(
   186	                _issue(
   187	                    "socket_input_not_literal_widget",
   188	                    f"{op.class_type}.{field_name} is an input socket, not a widget. {hint}",
   189	                    detail={
   190	                        "scope_path": op.scope_path,
   191	                        "class_type": op.class_type,
   192	                        "field": field_name,
   193	                        **hint_detail,
   194	                    },
   195	                )
   196	            )
   197	            continue
   198	        issues.extend(
   199	            _validate_literal_value(
   200	                value=value,
   201	                spec=spec,
   202	                class_type=op.class_type,
   203	                input_name=field_name,
   204	                context="add_node",
   205	            )
   206	        )
   207	    # Block only on errors; carry warnings (e.g. missing required input) forward so the
   208	    # node is still added and the gap surfaces as a non-blocking queue-validate warning.
   209	    if any(issue.severity == "error" for issue in issues):
   210	        return None, issues
   211
   212	    resolved_inputs: dict[str, ResolvedLinkEndpoint] = {}
   213	    resolved_input_specs: dict[str, InputSpec] = {}
   214	    for input_name, source in op.inputs.items():
   215	        if source.scope_path != op.scope_path:
   216	            return None, [
   217	                _issue(
   218	                    "cross_scope_link_unsupported",
   219	                    "add_node input endpoints must resolve within the same scope.",
   220	                    detail={
   221	                        "from_scope_path": source.scope_path,
   222	                        "to_scope_path": op.scope_path,
   223	                        "to_class_type": op.class_type,
   224	                        "to_input": input_name,
   225	                    },
   305	            value_default_receipts=value_default_receipts,
   306	            value_default_fields=value_default_fields,
   307	            anchor_near=anchor_near,
   308	            anchor_between=anchor_between,
   309	            anchor_group_index=anchor_group_index,
   310	            anchor_group_title=anchor_group_title,
   311	        ),
   312	        list(issues),
   313	    )
   314
   315
   316	def _values_equal(left: Any, right: Any) -> bool:
   317	    try:
   318	        return bool(left == right)
   319	    except Exception:
   320	        return repr(left) == repr(right)
   321
   322
   323	def _unique_schema_valid_prior(
   324	    *,
   325	    class_type: str,
   326	    input_name: str,
   327	    spec: InputSpec,
   328	    context: ValueDefaultContext,
   329	) -> tuple[ValueDefaultBinding | None, str]:
   330	    valid: list[ValueDefaultBinding] = []
   331	    refused_invalid = False
   332	    for binding in context.selected_bindings(class_type, input_name):
   333	        validation_issues = _validate_literal_value(
   334	            value=binding.thawed_value(),
   335	            spec=spec,
   336	            class_type=class_type,
   337	            input_name=input_name,
   338	            context="value_default_prior",
   339	        )
   340	        if validation_issues:
   341	            refused_invalid = True
   342	            continue
   343	        valid.append(binding)
   344	    if not valid:
   345	        return None, "invalid_source_prior" if refused_invalid else "no_eligible_source_prior"
   346	    first_value = valid[0].thawed_value()
   347	    if any(not _values_equal(first_value, binding.thawed_value()) for binding in valid[1:]):
   348	        return None, "conflicting_source_priors"
   349	    return valid[0], "unique_schema_valid_source_prior"
   350
   351
   352	def _bind_value_defaults(
   353	    op: AddNodeOp,
   354	    *,
   355	    schema_inputs: Mapping[str, InputSpec],
   300	                        "field_path": field_path,
   301	                        "requested_field_path": op.target.field_path,
   302	                        "class_type": class_type,
   303	                        **hint_detail,
   304	                    },
   305	                )
   306	            ]
   307	        return None, [
   308	            _issue(
   309	                "non_widget_field_not_editable",
   310	                f"{class_type}.{op.target.field_path} is not editable through set_node_field because it has no widget-backed literal surface.",
   311	                detail={
   312	                    "scope_path": op.target.scope_path,
   313	                    "uid": op.target.uid,
   314	                    "field_path": field_path,
   315	                    "requested_field_path": op.target.field_path,
   316	                    "class_type": class_type,
   317	                },
   318	            )
   319	        ]
   320
   321	    if field_path == "control_after_generate" and op.value not in _CONTROL_AFTER_GENERATE_CHOICES:
   322	        return None, [
   323	            _issue(
   324	                "value_not_in_enum",
   325	                f"set_node_field rejected {class_type}.{field_path}: value {op.value!r} is not in the declared enum.",
   326	                detail={
   327	                    "class_type": class_type,
   328	                    "input": field_path,
   329	                    "value": op.value,
   330	                    "choices": list(_CONTROL_AFTER_GENERATE_CHOICES),
   331	                },
   332	            )
   333	        ]
   334
   335	    value_issues = _validate_literal_value(
   336	        value=op.value,
   337	        spec=schema_input,
   338	        class_type=class_type,
   339	        input_name=field_path,
   340	        context="set_node_field",
   341	    )
   342	    if value_issues:
   343	        return None, value_issues
   344
   345	    value_default_receipt = None
   346	    node_properties = node.get("properties")
   347	    protected_uid = (
   348	        str(node_properties.get("vibecomfy_uid"))
   349	        if isinstance(node_properties, Mapping)
   350	        and isinstance(node_properties.get("vibecomfy_uid"), str)
   351	        else target.uid
   352	    )
   353	    if (
   354	        value_default_context is not None
   355	        and value_default_context.active

 exited 1 in 210114ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
[32m[INFO][0m Set vram state to: NORMAL_VRAM
objc[47970]: Class AVFFrameReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x12785c3a8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x166e4c3a8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
objc[47970]: Class AVFAudioReceiver is implemented in both /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/cv2/.dylibs/libavdevice.61.3.100.dylib (0x12785c3f8) and /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/lib/python3.11/site-packages/av/.dylibs/libavdevice.62.3.102.dylib (0x166e4c3f8). This may cause spurious casting failures and mysterious crashes. One of the duplicates must be removed or renamed.
[32m[INFO][0m PromptServer imported; registering VibeComfy routes.
[32m[INFO][0m vibecomfy agent routes module loaded and all routes registered.
[32m[INFO][0m VibeComfy routes registered successfully.
........E.EEEE.EE...................[1m[33m[WARNING][0m compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0:
.........
==================================== ERRORS ====================================
_ ERROR at setup of test_selected_precedent_workflow_schema_class_is_authorable_provisionally _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_selected_precedent_workflow_schema_class_is_authorable_provisionally>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_handle_agent_edit_batch_repl_adds_workflow_json_provisional_node _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_handle_agent_edit_batch_repl_adds_workflow_json_provisional_node>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_handle_agent_edit_batch_repl_adds_registry_provisional_missing_node _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_handle_agent_edit_batch_repl_adds_registry_provisional_missing_node>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_adapt_prefetch_compiles_workflow_classes_into_schema_backed_capabilities _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_adapt_prefetch_compiles_workflow_classes_into_schema_backed_capabilities>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_adapt_prompt_marks_unhydrated_workflow_schema_classes_observed_only _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_adapt_prompt_marks_unhydrated_workflow_schema_classes_observed_only>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_handle_agent_edit_batch_repl_unresolved_schema_capability_does_not_emit_noop_message _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_handle_agent_edit_batch_repl_unresolved_schema_capability_does_not_emit_noop_message>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
_ ERROR at setup of test_handle_agent_edit_batch_repl_edit_clarify_with_unresolved_schema_capability_downgrades _

fixturedef = <FixtureDef argname='tmp_path' scope='function' baseid=''>
request = <SubRequest 'tmp_path' for <Function test_handle_agent_edit_batch_repl_edit_clarify_with_unresolved_schema_capability_downgrades>>

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

../vibecomfy/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:730:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:309: in _gettempdir
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

../../../.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/lib/python3.11/tempfile.py:224: FileNotFoundError
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1434
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: timeout

    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

.venv/lib/python3.11/site-packages/torch/library.py:361
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/torch/library.py:361: UserWarning: Warning only once for all operators,  other operators may also be overridden.
    Overriding a previously registered kernel for the same operator and the same dispatch key
    operator: aten::mm(Tensor self, Tensor mat2) -> Tensor
      registered at /Users/runner/work/pytorch/pytorch/build/aten/src/ATen/RegisterSchema.cpp:6
    dispatch key: MPS
    previous kernel: registered at /Users/runner/work/pytorch/pytorch/aten/src/ATen/LegacyBatchingRegistrations.cpp:1076
         new kernel: registered at /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/fp4_fp8_for_torch_mps/ops.py:7 (Triggered internally at /Users/runner/work/pytorch/pytorch/aten/src/ATen/core/dispatch/OperatorEntry.cpp:215.)
    self.m.impl(

.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/opentelemetry/util/_importlib_metadata.py:32: DeprecationWarning: SelectableGroups dict interface is deprecated. Use select.
    return EntryPoints(ep for group_eps in eps.values() for ep in group_eps)

.venv/lib/python3.11/site-packages/comfy/model_management.py:237
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/lib/python3.11/site-packages/comfy/model_management.py:237: UserWarning: torch.cuda.current_device() did not return a device, returning a CPU torch device
    warnings.warn("torch.cuda.current_device() did not return a device, returning a CPU torch device")

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

tests/test_comfy_nodes_agent_edit.py:390
tests/test_comfy_nodes_agent_edit.py::test_batch_repl_search_exact_miss_explains_local_schema_lookup
tests/test_comfy_nodes_agent_edit.py::test_batch_repl_web_workflow_json_prompts_exact_schema_followup
tests/test_comfy_nodes_agent_edit.py::test_registry_evidence_only_candidate_is_resolvable_without_live_schema
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_comfy_nodes_agent_edit.py:390: UserWarning: emit_ui_json: schema-less node 2(SaveImage); emitting best-effort slots. Pass strict=True to hard-fail.
    graph = emit_ui_json(

tests/conftest.py:352
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/conftest.py:352: PytestUnknownMarkWarning: Unknown pytest.mark.flaky - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    flaky_marker = pytest.mark.flaky(reruns=1, reruns_delay=10)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/test_comfy_nodes_agent_edit.py::test_selected_precedent_workflow_schema_class_is_authorable_provisionally - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_adds_workflow_json_provisional_node - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_adds_registry_provisional_missing_node - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_comfy_nodes_agent_edit.py::test_adapt_prefetch_compiles_workflow_classes_into_schema_backed_capabilities - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_comfy_nodes_agent_edit.py::test_adapt_prompt_marks_unhydrated_workflow_schema_classes_observed_only - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_unresolved_schema_capability_does_not_emit_noop_message - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
ERROR tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_edit_clarify_with_unresolved_schema_capability_downgrades - FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle']
38 passed, 699 deselected, 11 warnings, 7 errors in 155.52s (0:02:35)
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

exec
/bin/zsh -lc "nl -ba vibecomfy/workflow.py | sed -n '1468,1494p'; git show f2661b01:vibecomfy/workflow.py | tail -28; git show f2661b01:tests/test_api_surface.py | sed -n '12,36p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 220ms:
  1468	def _drop_unused_positional_aliases(inputs: dict[str, Any]) -> None:
  1469	    for key in list(inputs):
  1470	        if key.startswith("unused_"):
  1471	            inputs.pop(key, None)
  1472
  1473
  1474	__all__ = [
  1475	    "OPAQUE_COMPONENT_CLASS_RE",
  1476	    "RawWidgetPayload",
  1477	    "ValidationIssue",
  1478	    "ValidationReport",
  1479	    "VibeEdge",
  1480	    "VibeInput",
  1481	    "VibeNode",
  1482	    "VibeOutput",
  1483	    "VibeWorkflow",
  1484	    "WorkflowRequirements",
  1485	    "WorkflowSource",
  1486	]
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

def _apply_positional_widget_aliases(inputs: dict[str, Any], node: VibeNode) -> None:
    widget_aliases.apply_positional_widget_aliases(
        inputs,
        node.class_type,
        input_aliases=node.metadata.get("input_aliases"),
    )


def _drop_unused_positional_aliases(inputs: dict[str, Any]) -> None:
    for key in list(inputs):
        if key.startswith("unused_"):
            inputs.pop(key, None)


__all__ = [
    "OPAQUE_COMPONENT_CLASS_RE",
    "RawWidgetPayload",
    "ValidationIssue",
    "ValidationReport",
    "VibeEdge",
    "VibeInput",
    "VibeNode",
    "VibeOutput",
    "VibeWorkflow",
    "WorkflowRequirements",
    "WorkflowSource",
]
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
        "ready_template_ids", "load_workflow_any", "load_workflow_json", "load_template",
        "find_repo_root", "ensure_plugins_loaded", "image", "video", "blocks", "patches",
        "router", "run", "run_sync", "run_embedded", "run_embedded_sync",
    ],
    "vibecomfy.workflow": [
        "OPAQUE_COMPONENT_CLASS_RE", "ValidationIssue", "ValidationReport", "VibeEdge",
        "VibeInput", "VibeNode", "VibeOutput", "VibeWorkflow", "WorkflowRequirements",
        "WorkflowSource",
    ],
    "vibecomfy.handles": ["Handle"],
    "vibecomfy.errors": [
        "ContextVarBindingError", "ConversionParityError", "DriftError", "ModelAssetError",
        "QueueError", "RuntimeNodeError", "SchemaValidationError", "SubgraphFreshnessError",
        "VibeComfyError",
    ],
    "vibecomfy.schema": [
        "AuthoringSchemaProvider", "InputSpec", "NodeCallValidationIssue",
        "NodeCallValidationReport", "CompositeSchemaProvider", "ConversionSchemaProvider",
        "LocalSchemaProvider", "NodeSchema", "ObjectInfoSchemaProvider", "OutputSpec",
        "RuntimeSchemaProvider", "SchemaIndexError", "SchemaProvider", "SchemaSourceInfo",
        "SourceSchemaProvider", "get_authoring_schema_provider", "get_schema_provider",
        "schema_for", "schema_registry_empty", "schemas_for", "socket_types_compatible",
        "validate_node_call",
    ],
    "vibecomfy.artifacts": ["Artifact", "ArtifactKind", "Image", "Video", "Audio", "Latent", "Mask"],

exec
/bin/zsh -lc 'git blame -L 1474,1488 vibecomfy/workflow.py; git blame -L 14,21 tests/test_api_surface.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 949ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1474) __all__ = [
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1475)     "OPAQUE_COMPONENT_CLASS_RE",
92dfdb8e1 (POM 2026-05-31 06:37:37 +0200 1476)     "RawWidgetPayload",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1477)     "ValidationIssue",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1478)     "ValidationReport",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1479)     "VibeEdge",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1480)     "VibeInput",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1481)     "VibeNode",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1482)     "VibeOutput",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1483)     "VibeWorkflow",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1484)     "WorkflowRequirements",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1485)     "WorkflowSource",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 1486) ]
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
c328242b0 (POM 2026-06-09 20:45:20 +0200 14)         "router", "run", "run_sync", "run_embedded", "run_embedded_sync",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 15)     ],
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 16)     "vibecomfy.workflow": [
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 17)         "OPAQUE_COMPONENT_CLASS_RE", "ValidationIssue", "ValidationReport", "VibeEdge",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 18)         "VibeInput", "VibeNode", "VibeOutput", "VibeWorkflow", "WorkflowRequirements",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 19)         "WorkflowSource",
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 20)     ],
bed1b3ab4 (POM 2026-05-21 23:55:52 +0200 21)     "vibecomfy.handles": ["Handle"],

collab: Wait
collab: Wait
collab: Wait
codex
B04 CHECKPOINT VERDICT: PASS — Real schemas remain authoritative across all construction and cross-turn paths; enum/asset behavior and scope checks satisfy B04.

1. Provider precedence: PASS. [`CompositeSchemaProvider`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/schema/provider.py:496) searches providers in order for `get_schema()` and reverse-merges `schemas()`, making provider 0 dominant in both views. [`with_provisional_gap_filler()`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/schema/provider.py:519) correctly constructs `(authoritative, provisional)`.

2. All seven sites: PASS. The six provisional hydration paths use the helper real-first: `_frag_research.py:821,874,922`, `_frag_response_contract.py:793`, `_frag_batch_loop.py:910`, and `edit_batch_repl.py:1116`. The seventh site, [`_frag_orchestration.py:426`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_orchestration.py:426), is the baseline runtime→authoring composite and remains real-first. Exhaustive search found no provisional-first construction or unsafe factory.

3. Cross-turn authority: PASS. [`_frag_response_contract.py:793`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793) wraps `session.schema_provider` as authoritative, then assigns the same composite to session and state. The regression at [`test_comfy_nodes_agent_edit.py:20479`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_comfy_nodes_agent_edit.py:20479) verifies a fresh second-turn `EditSession` and repeated enrichment remain real-first.

4. Widget/choice shadowing: PASS. The fixture at [`test_comfy_nodes_agent_edit.py:20030`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_comfy_nodes_agent_edit.py:20030) contrasts real semantic inputs and choices with provisional `widget_0`/empty choices. The shared assertion verifies both lookup APIs retain real names/choices while provisional-only classes still fill gaps.

5. Enum and asset behavior: PASS. Add validates before producing a resolved node at [`apply_resolve_add.py:198`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_resolve_add.py:198); set validates before mutation at [`apply_resolve_base.py:335`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_resolve_base.py:335). Invalid enums return `value_not_in_enum`, no candidate/mutation, while missing asset filenames remain `asset_not_installed` warnings under [`test_porting_edit_apply_values.py:37`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_porting_edit_apply_values.py:37).

6. Scope and hygiene: PASS. The range contains only the B04 brief, focused tests, four agent files, and two schema files. `vibecomfy/workflow.py` is untouched. `git diff --check f2661b01..ff6ae9c8` is clean. The API-snapshot failure is explicitly pre-existing in [`emitter_parity_surface.txt:1`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/quarantine/emitter_parity_surface.txt:1); B04’s snapshot change only adds the new helper export. Nonblocking cleanup only: `edit_batch_repl.py:1104` retains an unused `CompositeSchemaProvider` binding.

7. Independent verification: PASS within sandbox limits.

   - B04 precedence/cross-turn selection: **10 passed**.
   - Apply mechanism files: **61 passed, 1 skipped**.
   - Exact broad filter: **38 passed, 7 setup errors**; every error was solely `tmp_path` failing because the enforced read-only sandbox has no writable temporary directory. All B04-added tests passed. This is consistent with the executor’s writable-environment result of **45 passed**.

No blocking issues.
tokens used
275,392
B04 CHECKPOINT VERDICT: PASS — Real schemas remain authoritative across all construction and cross-turn paths; enum/asset behavior and scope checks satisfy B04.

1. Provider precedence: PASS. [`CompositeSchemaProvider`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/schema/provider.py:496) searches providers in order for `get_schema()` and reverse-merges `schemas()`, making provider 0 dominant in both views. [`with_provisional_gap_filler()`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/schema/provider.py:519) correctly constructs `(authoritative, provisional)`.

2. All seven sites: PASS. The six provisional hydration paths use the helper real-first: `_frag_research.py:821,874,922`, `_frag_response_contract.py:793`, `_frag_batch_loop.py:910`, and `edit_batch_repl.py:1116`. The seventh site, [`_frag_orchestration.py:426`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_orchestration.py:426), is the baseline runtime→authoring composite and remains real-first. Exhaustive search found no provisional-first construction or unsafe factory.

3. Cross-turn authority: PASS. [`_frag_response_contract.py:793`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_response_contract.py:793) wraps `session.schema_provider` as authoritative, then assigns the same composite to session and state. The regression at [`test_comfy_nodes_agent_edit.py:20479`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_comfy_nodes_agent_edit.py:20479) verifies a fresh second-turn `EditSession` and repeated enrichment remain real-first.

4. Widget/choice shadowing: PASS. The fixture at [`test_comfy_nodes_agent_edit.py:20030`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_comfy_nodes_agent_edit.py:20030) contrasts real semantic inputs and choices with provisional `widget_0`/empty choices. The shared assertion verifies both lookup APIs retain real names/choices while provisional-only classes still fill gaps.

5. Enum and asset behavior: PASS. Add validates before producing a resolved node at [`apply_resolve_add.py:198`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_resolve_add.py:198); set validates before mutation at [`apply_resolve_base.py:335`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_resolve_base.py:335). Invalid enums return `value_not_in_enum`, no candidate/mutation, while missing asset filenames remain `asset_not_installed` warnings under [`test_porting_edit_apply_values.py:37`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_porting_edit_apply_values.py:37).

6. Scope and hygiene: PASS. The range contains only the B04 brief, focused tests, four agent files, and two schema files. `vibecomfy/workflow.py` is untouched. `git diff --check f2661b01..ff6ae9c8` is clean. The API-snapshot failure is explicitly pre-existing in [`emitter_parity_surface.txt:1`](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/quarantine/emitter_parity_surface.txt:1); B04’s snapshot change only adds the new helper export. Nonblocking cleanup only: `edit_batch_repl.py:1104` retains an unused `CompositeSchemaProvider` binding.

7. Independent verification: PASS within sandbox limits.

   - B04 precedence/cross-turn selection: **10 passed**.
   - Apply mechanism files: **61 passed, 1 skipped**.
   - Exact broad filter: **38 passed, 7 setup errors**; every error was solely `tmp_path` failing because the enforced read-only sandbox has no writable temporary directory. All B04-added tests passed. This is consistent with the executor’s writable-environment result of **45 passed**.

No blocking issues.
