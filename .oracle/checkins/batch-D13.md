Reading additional input from stdin...
2026-08-13T13:19:17.750769Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:19:17.752167Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:19:17.752178Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb46-e483-77c1-bfc9-2f5d76a43e4e
--------
user
# MEGADO CHECKPOINT — Batch D13 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the D13 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**D13 [HARD] — Corpus integrity, satisfiability, and semantic rubrics.** Tasks + acceptance from `.oracle/tasklist.md` (D13 section). Diff to review: `git diff 0f015101..5aa73c53` (B01 PASS SHA → D13 commit). Executor: GPT-5.6 Sol (workspace-write).

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
8. Scope: only D13 files; `git diff --check 0f015101..5aa73c53` clean.
9. Run the focused slice yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks).

## Output

First line: `D13 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–9) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit MEGADO oracle checkpoint. I’ll keep the review read-only, independently verify the diff and tests, and report against all nine focus areas.
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
The skill’s normal oracle flow delegates verification through an outbound-network executor, but this checkpoint is explicitly read-only and the environment disallows network/escalation. I’m therefore performing the gate directly and will not alter the worktree. I’m starting with the frozen D13 acceptance text, commit identity, and exact changed-file scope.
exec
/bin/zsh -lc 'git diff --check 0f015101..5aa73c53' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git diff --stat 0f015101..5aa73c53 && git diff --name-status 0f015101..5aa73c53' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git status --short --branch && git rev-parse --abbrev-ref HEAD && git rev-parse 0f015101 && git rev-parse 5aa73c53' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "awk 'BEGIN{p=0} /"'^## D13|''^### D13|''^D13 /{p=1} p{print} p && /''^## D14|''^### D14|''^D14 /{exit}'"' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
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

 succeeded in 141ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

 succeeded in 158ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .gitignore                                         |    1 +
 .oracle/briefs/batch-D13-rework.md                 |   33 +
 .oracle/briefs/batch-D13.md                        |   32 +
 .oracle/checkins/batch-D13.md                      | 9835 ++++++++++++++++++++
 tests/live_agentic_harness/README.md               |    6 +
 tests/live_agentic_harness/REVISIONS.md            |   22 +
 tests/live_agentic_harness/assessor.py             |  114 +-
 tests/live_agentic_harness/intent_judge.py         |  163 +-
 tests/live_agentic_harness/runner.py               |   23 +-
 tests/live_agentic_harness/scenario_manifest.json  | 1299 +++
 tests/live_agentic_harness/scenario_manifest.py    |  261 +
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
 tests/test_live_agentic_harness_corpus_manifest.py |  148 +
 tests/test_live_agentic_harness_guard_contract.py  |  270 +
 ...test_live_agentic_harness_runner_persistence.py |    3 +
 ...est_live_agentic_intent_judge_schema_context.py |   51 +
 tests/test_live_agentic_runner_persistence.py      |    9 +
 vibecomfy/intent/prompts/refusal_judge.prompt.md   |   43 +
 57 files changed, 13309 insertions(+), 56 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	.gitignore
A	.oracle/briefs/batch-D13-rework.md
A	.oracle/briefs/batch-D13.md
A	.oracle/checkins/batch-D13.md
M	tests/live_agentic_harness/README.md
A	tests/live_agentic_harness/REVISIONS.md
M	tests/live_agentic_harness/assessor.py
M	tests/live_agentic_harness/intent_judge.py
M	tests/live_agentic_harness/runner.py
A	tests/live_agentic_harness/scenario_manifest.json
A	tests/live_agentic_harness/scenario_manifest.py
M	tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json
M	tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json
M	tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json
M	tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
M	tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json
M	tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json
M	tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json
M	tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json
M	tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json
M	tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json
M	tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
M	tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
M	tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json
M	tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json
M	tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json
M	tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json
M	tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json
M	tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json
M	tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json
M	tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json
M	tests/live_agentic_harness/scenarios/speed-distillation-research.json
M	tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
M	tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json
M	tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json
M	tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json
M	tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
M	tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
M	tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json
M	tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json
M	tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
M	tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json
M	tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
M	tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json
M	tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json
M	tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
M	tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
M	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json
M	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json
M	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
M	tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
A	tests/test_live_agentic_harness_corpus_manifest.py
M	tests/test_live_agentic_harness_guard_contract.py
A	tests/test_live_agentic_harness_runner_persistence.py
M	tests/test_live_agentic_intent_judge_schema_context.py
M	tests/test_live_agentic_runner_persistence.py
A	vibecomfy/intent/prompts/refusal_judge.prompt.md

 succeeded in 224ms:
## oracle-run
 M .oracle/checkins/batch-D13.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
oracle-run
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
0f015101e98d9292e07d2e0777ed01d6d41ee373
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
5aa73c5397f2e6e5a35e7f7878d1a00e4a5275e4

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/scenario_manifest.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'git diff --unified=80 0f015101..5aa73c53 -- tests/live_agentic_harness/runner.py tests/live_agentic_harness/assessor.py tests/live_agentic_harness/intent_judge.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/assessor.py b/tests/live_agentic_harness/assessor.py
index 42388790..8a50ef27 100644
--- a/tests/live_agentic_harness/assessor.py
+++ b/tests/live_agentic_harness/assessor.py
@@ -1,109 +1,109 @@
 """Deep assessment of live agentic run artifacts.

 The live agentic harness already verifies flow metadata (real dispatcher,
 agentic model behavior, status == success).  This module inspects the actual
 run artifacts to catch failures that metadata alone cannot:

 * response.ok == false or response.error set
 * readiness blockers
 * graph unchanged when an edit was expected
 * hard diagnostics (severity == error) from agent-edit turns
 * upstream dependency failures such as Hivemind HTTP 500
 * implementation_result.ok == false
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

-from .intent_judge import judge_edit_intent
+from .intent_judge import judge_edit_intent, judge_grounded_refusal

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

 # Canonical public route vocabulary (mirrors vibecomfy.executor.contracts).
 # Edit routes may land graph changes; non-edit routes never do.  Exemption
 # from the landed-count guard is decided from the envelope's canonical route,
 # never from the agent's self-declared outcome/reason labels.
 _EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise"})
 _NON_EDIT_ROUTES = frozenset({
     "clarify",
     "respond",
     "inspect",
     "research",
     "requires_custom_nodes",
 })


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
     stage at all; that missing stage should not be scored the same as a
     concrete queue blocker.
     """
     if not _has_successful_candidate(response):
         return False
     gates = response.get("gates")
     if not isinstance(gates, Mapping) or gates.get("queue_validate_ok") is not False:
         return False
     debug = response.get("debug")
     if not isinstance(debug, Mapping):
@@ -732,194 +732,242 @@ def assess_live_output_dir(
             if (
                 not safe_refusal_accepted
                 and response.get("graph_unchanged") is False
                 and route in _NON_EDIT_ROUTES
             ):
                 issues.append(
                     {
                         "check": "route_graph_consistency",
                         "severity": "error",
                         "detail": (
                             f"Non-edit route {route!r} claimed graph_unchanged=false; "
                             "a non-edit route cannot change the graph."
                         ),
                     }
                 )

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
                         "detail": f"Expected edit but gates failed: {', '.join(sorted(false_gates))}.",
                     }
                 )

             if not safe_refusal_accepted:
                 issues.extend(_assess_effective_edit_targets(output_dir, response, scenario))
         elif expected_outcome_kinds:
             outcome = response.get("outcome") or {}
             outcome_kind = outcome.get("kind")
             if outcome_kind not in expected_outcome_kinds:
                 issues.append(
                     {
                         "check": "outcome_kind",
                         "severity": "error",
                         "detail": (
                             f"Expected outcome.kind in {sorted(expected_outcome_kinds)!r} "
                             f"but got {outcome_kind!r}."
                         ),
                     }
                 )

         # LLM intent judge: score the candidate edit against the query when the
         # scenario expects a graph change.  This runs by default; set
         # ``assessment.skip_intent_judge: true`` in the scenario to disable it.
+        # A DESIRED edit must never pass on an allowlisted refusal label
+        # without an active grounded-refusal judge: the judge runs and must
+        # confirm the refusal is grounded (supported blocker, no representable
+        # edit, specific next action, no fabricated inability), and it FAILS
+        # CLOSED when the judge is unavailable.  graph_unchanged=false plus a
+        # refusal label is never a safe refusal (safe_refusal_accepted requires
+        # graph_unchanged=true), so it is still scored by the structural guards
+        # and — for desired scenarios — fails closed without a judge verdict.
+        # Non-desired edit-or-refuse scenarios keep the historical bypass.
         if (
             expect_graph_changed
-            and not safe_refusal_accepted
             and not scenario.get("assessment", {}).get("skip_intent_judge")
         ):
-            verdict = judge_edit_intent(output_dir, scenario)
-            if verdict.get("pass_") is False:
-                issues.append(
-                    {
-                        "check": "intent_judge",
-                        "severity": "error",
-                        "detail": (
-                            f"LLM intent judge failed: {verdict.get('rationale', 'no rationale')} "
-                            f"criteria={verdict.get('criteria')}"
-                        ),
-                    }
-                )
-            elif verdict.get("pass_") is True:
-                issues.append(
-                    {
-                        "check": "intent_judge",
-                        "severity": "info",
-                        "detail": (
-                            f"LLM intent judge passed: {verdict.get('rationale', 'no rationale')} "
-                            f"criteria={verdict.get('criteria')}"
-                        ),
-                    }
-                )
-            else:
-                issues.append(
-                    {
-                        "check": "intent_judge",
-                        "severity": "warning",
-                        "detail": f"LLM intent judge could not run: {verdict.get('error')}",
-                    }
-                )
+            if safe_refusal_accepted and scenario.get("desired"):
+                verdict = judge_grounded_refusal(output_dir, scenario)
+                if verdict.get("pass_") is False:
+                    issues.append(
+                        {
+                            "check": "grounded_refusal",
+                            "severity": "error",
+                            "detail": (
+                                f"Refusal not grounded: {verdict.get('rationale', 'no rationale')} "
+                                f"criteria={verdict.get('criteria')}"
+                            ),
+                        }
+                    )
+                elif verdict.get("pass_") is True:
+                    issues.append(
+                        {
+                            "check": "grounded_refusal",
+                            "severity": "info",
+                            "detail": (
+                                f"Grounded refusal confirmed: {verdict.get('rationale', 'no rationale')} "
+                                f"criteria={verdict.get('criteria')}"
+                            ),
+                        }
+                    )
+                else:
+                    issues.append(
+                        {
+                            "check": "grounded_refusal",
+                            # A desired block is an active acceptance rubric;
+                            # an absent grounded-refusal judge fails closed.
+                            "severity": "error",
+                            "detail": (
+                                "Grounded-refusal judge could not run: "
+                                f"{verdict.get('error')}"
+                            ),
+                        }
+                    )
+            elif not safe_refusal_accepted:
+                verdict = judge_edit_intent(output_dir, scenario)
+                if verdict.get("pass_") is False:
+                    issues.append(
+                        {
+                            "check": "intent_judge",
+                            "severity": "error",
+                            "detail": (
+                                f"LLM intent judge failed: {verdict.get('rationale', 'no rationale')} "
+                                f"criteria={verdict.get('criteria')}"
+                            ),
+                        }
+                    )
+                elif verdict.get("pass_") is True:
+                    issues.append(
+                        {
+                            "check": "intent_judge",
+                            "severity": "info",
+                            "detail": (
+                                f"LLM intent judge passed: {verdict.get('rationale', 'no rationale')} "
+                                f"criteria={verdict.get('criteria')}"
+                            ),
+                        }
+                    )
+                else:
+                    issues.append(
+                        {
+                            "check": "intent_judge",
+                            # A desired block is an active acceptance rubric, not
+                            # optional context. Fail closed if its judge is absent.
+                            "severity": "error" if scenario.get("desired") else "warning",
+                            "detail": f"LLM intent judge could not run: {verdict.get('error')}",
+                        }
+                    )

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
         # G0R: the residual "unchanged" substring gate over the
         # implementation_result message is removed — prose never gates
         # scoring.  Only the structured ok flag is authoritative.
         if impl_result.get("ok") is False:
             issues.append(
                 {
                     "check": "implementation_result_ok",
                     "severity": "error",
                     "detail": (
                         "implementation_result.ok is False: "
                         f"{impl_result.get('error') or impl_result.get('message', '')}"
                     ),
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
diff --git a/tests/live_agentic_harness/intent_judge.py b/tests/live_agentic_harness/intent_judge.py
index b935d2d4..af63a507 100644
--- a/tests/live_agentic_harness/intent_judge.py
+++ b/tests/live_agentic_harness/intent_judge.py
@@ -1,147 +1,199 @@
 """LLM intent judge for live agentic harness artifacts.

 Provides a DeepSeek-backed text judge that scores a candidate workflow edit
 against the scenario's natural-language intent.  The judge is intentionally
 separate from the deterministic assessor so it can be enabled/disabled without
 changing the core pass/fail logic.
 """

 from __future__ import annotations

 import json
 import os
 from pathlib import Path
 from typing import Any, Mapping

 from vibecomfy.comfy_nodes.agent.provider import run_model_turn

 _PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "text_judge.prompt.md"
+_REFUSAL_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "refusal_judge.prompt.md"


 def _load_prompt() -> str:
     if _PROMPT_PATH.is_file():
         return _PROMPT_PATH.read_text(encoding="utf-8")
     # Fallback rubric if the canonical prompt is missing.
     return (
         "You are a precise evaluator for ComfyUI workflow edits. Given a natural-language\n"
         "intent and a structural diff between a pre-edit and post-edit workflow IR, you\n"
         "must determine whether the edit correctly implements the intent.\n\n"
         "Evaluate the edit against exactly four binary criteria:\n"
         "- correct_node_targeted\n"
         "- correct_parameter_changed\n"
         "- value_semantically_matches_intent\n"
         "- no_orphaned_wiring\n\n"
         "Respond with a JSON object and nothing else:\n"
         '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
         '"correct_parameter_changed": true | false, "value_semantically_matches_intent": true | false, '
         '"no_orphaned_wiring": true | false}, "rationale": "<one or two sentences>"}\n'
         "`pass_` must be true if and only if all four criteria are true."
     )


-def _parse_verdict(raw: str) -> dict[str, Any]:
-    """Parse the judge's JSON response into a normalized dict."""
-    text = raw.strip()
-    # Some models wrap JSON in markdown fences; strip them.
+def _load_refusal_prompt() -> str:
+    if _REFUSAL_PROMPT_PATH.is_file():
+        return _REFUSAL_PROMPT_PATH.read_text(encoding="utf-8")
+    # Fallback rubric if the canonical prompt is missing.
+    return (
+        "You are a precise evaluator for ComfyUI workflow edits. A model was asked\n"
+        "to perform an edit but refused and left the workflow graph unchanged, citing\n"
+        "a reason. You must determine whether that refusal is GROUNDED (the model\n"
+        "could not honestly satisfy the intent) or fabricated/unsupported (the model\n"
+        "dodged an edit it could have made).\n\n"
+        "Evaluate the refusal against exactly four binary criteria:\n"
+        "- supported_blocker: the refusal cites a real, supported blocker (for\n"
+        "  example, a node class genuinely absent from the installed schema, or a\n"
+        "  genuine ambiguity in the request) rather than a made-up constraint.\n"
+        "- no_representable_edit: no representable edit to the given workflow could\n"
+        "  satisfy the intent, so refusing was the only honest option.\n"
+        "- specific_next_action: the refusal states a concrete next action that\n"
+        "  would unblock the edit (for example, installing a named custom node, or\n"
+        "  answering a named clarifying question).\n"
+        "- no_fabricated_inability: the refusal does not falsely claim an inability\n"
+        "  (for example, claiming a node is unavailable when the schema contains it,\n"
+        "  or claiming the request is ambiguous when it is concrete).\n\n"
+        "Respond with a JSON object and nothing else:\n"
+        '{"pass_": true | false, "criteria": {"supported_blocker": true | false, '
+        '"no_representable_edit": true | false, "specific_next_action": true | false, '
+        '"no_fabricated_inability": true | false}, "rationale": "<one or two sentences>"}\n'
+        "`pass_` must be true if and only if all four criteria are true."
+    )
+
+
+def _strip_code_fences(text: str) -> str:
+    """Strip markdown fences some models wrap JSON responses in."""
+    text = text.strip()
     if text.startswith("```"):
         lines = text.splitlines()
         if lines[0].startswith("```"):
             lines = lines[1:]
         if lines and lines[-1].startswith("```"):
             lines = lines[:-1]
         text = "\n".join(lines).strip()
-    parsed = json.loads(text)
+    return text
+
+
+def _parse_verdict(raw: str) -> dict[str, Any]:
+    """Parse the judge's JSON response into a normalized dict."""
+    parsed = json.loads(_strip_code_fences(raw))
     criteria = parsed.get("criteria") or {}
     normalized_criteria = {
         "correct_node_targeted": bool(criteria.get("correct_node_targeted")),
         "correct_parameter_changed": bool(criteria.get("correct_parameter_changed")),
         "value_semantically_matches_intent": bool(criteria.get("value_semantically_matches_intent")),
         "no_orphaned_wiring": bool(criteria.get("no_orphaned_wiring")),
     }
     return {
         "pass_": bool(parsed.get("pass_")),
         "criteria": normalized_criteria,
         "rationale": str(parsed.get("rationale", "")),
     }


+def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
+    """Parse the grounded-refusal judge's JSON response into a normalized dict."""
+    parsed = json.loads(_strip_code_fences(raw))
+    criteria = parsed.get("criteria") or {}
+    normalized_criteria = {
+        "supported_blocker": bool(criteria.get("supported_blocker")),
+        "no_representable_edit": bool(criteria.get("no_representable_edit")),
+        "specific_next_action": bool(criteria.get("specific_next_action")),
+        "no_fabricated_inability": bool(criteria.get("no_fabricated_inability")),
+    }
+    return {
+        "pass_": bool(parsed.get("pass_")),
+        "criteria": normalized_criteria,
+        "rationale": str(parsed.get("rationale", "")),
+    }
+
+
 def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
     path = output_dir / "implementation_payload.json"
     if not path.is_file():
         return None
     try:
         data = json.loads(path.read_text(encoding="utf-8"))
     except (OSError, json.JSONDecodeError):
         return None
     return data if isinstance(data, dict) else None


 def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
     if not isinstance(payload, Mapping):
         return None
     graph = payload.get("graph")
     if not isinstance(graph, Mapping):
         return None
     compiled_api = graph.get("compiled_api")
     if not isinstance(compiled_api, Mapping):
         # Sidecar-less envelope: the execution view is derived by compiling the
         # IR (compile("api") is a function, not stored data). Only a graph the
         # decoder accepts yields context; anything else stays context-free.
         try:
             from vibecomfy.ingest.normalize import convert_to_vibe_format

             compiled_api = convert_to_vibe_format(dict(graph)).compile("api")
         except Exception:
             return None
     context: dict[str, Any] = {"compiled_api": compiled_api}
     metadata = graph.get("metadata")
     if isinstance(metadata, Mapping):
         widget_index = metadata.get("widget_index") or metadata.get("object_info_index")
         if isinstance(widget_index, Mapping):
             context["widget_index"] = widget_index
     return context


 def _ui_nodes_by_id(ui: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
     nodes = ui.get("nodes")
     if not isinstance(nodes, list):
         return {}
     result: dict[str, Mapping[str, Any]] = {}
     for node in nodes:
         if not isinstance(node, Mapping):
             continue
         node_id = node.get("id")
         if node_id is not None:
             result[str(node_id)] = node
     return result


 def _ui_links_by_id(ui: Mapping[str, Any]) -> dict[Any, Any]:
     links = ui.get("links")
     if not isinstance(links, list):
         return {}
     result: dict[Any, Any] = {}
     for link in links:
         if isinstance(link, list) and link:
             result[link[0]] = link
         elif isinstance(link, Mapping) and "id" in link:
             result[link.get("id")] = link
     return result


 def _link_source(link: Any) -> dict[str, Any] | None:
     if isinstance(link, list) and len(link) >= 3:
         return {"node_id": str(link[1]), "slot": link[2]}
     if isinstance(link, Mapping):
         source_id = link.get("origin_id", link.get("source_id", link.get("from_node")))
         source_slot = link.get("origin_slot", link.get("source_slot", link.get("from_slot")))
         if source_id is not None:
             return {"node_id": str(source_id), "slot": source_slot}
     return None


 def _linked_inputs_for_node(
     node: Mapping[str, Any],
     *,
     links_by_id: Mapping[Any, Any],
     nodes_by_id: Mapping[str, Mapping[str, Any]],
@@ -296,80 +348,181 @@ def judge_edit_intent(
     except (OSError, json.JSONDecodeError) as exc:
         return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}

     system_prompt = _load_prompt()
     implementation_payload = _load_implementation_payload(output_dir)
     schema_context = _schema_context_from_payload(implementation_payload) or {}
     dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
     if dataflow_context:
         schema_context["dataflow_context"] = dataflow_context
     if schema_context:
         system_prompt = (
             system_prompt.rstrip()
             + "\n\n## Schema and widget evidence\n"
             "When schema_context is provided, use it to map opaque widget_N fields "
             "to semantic input names. Treat literal widget values as static node "
             "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
             "widget's meaning from index order when compiled_api names are available. "
             "If a static widget containing stale or fabricated text is removed while "
             "the relevant linked dynamic input path remains connected, do not treat "
             "that removal as deleting the dynamic dataflow."
         )
     # Optional non-prescriptive "desired outcome" rubric from the scenario. When
     # present, it grounds the judge on what a GOOD result achieves (the outcome +
     # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
     # alternative approaches that reach the same outcome count as correct.
     desired = scenario.get("desired")
     if desired:
         system_prompt = (
             system_prompt.rstrip()
             + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
             "The scenario author described what a GOOD result looks like below. Use it to "
             "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
             "This is NOT a recipe of exact nodes/params to use — any sound approach that "
             "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
             "it fully wired/complete (no dangling or broken connections, existing pipeline "
             "not broken), and is the approach a sensible one?\n\n"
             f"Desired outcome: {desired.get('outcome', '')}\n"
             f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
             f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
         )
     payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
     if desired:
         payload["desired_outcome"] = desired
     if schema_context:
         payload["schema_context"] = schema_context
     user_content = json.dumps(payload, indent=2)

     try:
         response = run_model_turn(
             "evaluate workflow edit against intent",
             messages=[
                 {"role": "system", "content": system_prompt},
                 {"role": "user", "content": user_content},
             ],
             route=route,
             model=model,
             response_contract="json",
         )
     except Exception as exc:  # noqa: BLE001
         return {"pass_": None, "error": f"model call failed: {exc}"}

     raw = response.get("content") or ""
     if not raw:
         return {"pass_": None, "error": "model returned empty content"}

     try:
         verdict = _parse_verdict(raw)
     except (json.JSONDecodeError, KeyError, TypeError) as exc:
         return {
             "pass_": None,
             "error": f"could not parse judge response: {exc}",
             "raw": raw[:500],
         }

     verdict["metadata"] = {
         "route": route,
         "model": model,
         "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
     }
     return verdict
+
+
+def judge_grounded_refusal(
+    output_dir: Path | str,
+    scenario: Mapping[str, Any],
+    *,
+    route: str = "deepseek",
+    model: str = "deepseek-v4-pro",
+) -> dict[str, Any]:
+    """Run the DeepSeek grounded-refusal judge for a desired edit scenario.
+
+    A desired edit may pass on an allowlisted refusal label ONLY when this judge
+    confirms the refusal is grounded: the cited blocker is real and supported,
+    no representable edit could satisfy the intent, the refusal states a
+    specific next action, and it does not fabricate an inability.
+
+    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
+    If required artifacts are missing or the model call fails, ``pass_`` is None
+    and ``error`` describes why — callers MUST fail closed on that outcome.
+    """
+    output_dir = Path(output_dir)
+    query = str(scenario.get("query", "")).strip()
+    if not query:
+        return {"pass_": None, "error": "scenario has no query"}
+
+    # The refusal envelope is read from the run's response.json: outcome kind,
+    # message, gates, route, evidence.  Only the structured envelope is scored;
+    # prose never gates.
+    response_path = output_dir / "response.json"
+    refusal: dict[str, Any] = {}
+    if response_path.is_file():
+        try:
+            response = json.loads(response_path.read_text(encoding="utf-8"))
+        except (OSError, json.JSONDecodeError):
+            response = None
+        if isinstance(response, Mapping):
+            refusal = {
+                "outcome": response.get("outcome"),
+                "message": response.get("message"),
+                "no_candidate_reason": response.get("no_candidate_reason"),
+                "route": response.get("route"),
+                "gates": response.get("gates"),
+                "evidence": response.get("evidence"),
+                "graph_unchanged": response.get("graph_unchanged"),
+            }
+    if not isinstance(refusal.get("outcome"), Mapping):
+        return {"pass_": None, "error": "response.json is missing a refusal outcome"}
+
+    system_prompt = _load_refusal_prompt()
+    implementation_payload = _load_implementation_payload(output_dir)
+    schema_context = _schema_context_from_payload(implementation_payload) or {}
+    if schema_context:
+        system_prompt = (
+            system_prompt.rstrip()
+            + "\n\n## Schema evidence\n"
+            "When schema_context is provided, use it to verify whether a cited "
+            "blocker is real. A 'requires_custom_nodes' refusal is fabricated if "
+            "the needed node class actually exists in compiled_api. Do not guess "
+            "from node names when compiled_api is available."
+        )
+    desired = scenario.get("desired")
+    payload: dict[str, Any] = {"nl_intent": query, "refusal": refusal}
+    if desired:
+        payload["desired_outcome"] = desired
+    if schema_context:
+        payload["schema_context"] = schema_context
+    user_content = json.dumps(payload, indent=2)
+
+    try:
+        response = run_model_turn(
+            "evaluate whether a workflow-edit refusal is grounded",
+            messages=[
+                {"role": "system", "content": system_prompt},
+                {"role": "user", "content": user_content},
+            ],
+            route=route,
+            model=model,
+            response_contract="json",
+        )
+    except Exception as exc:  # noqa: BLE001
+        return {"pass_": None, "error": f"model call failed: {exc}"}
+
+    raw = response.get("content") or ""
+    if not raw:
+        return {"pass_": None, "error": "model returned empty content"}
+
+    try:
+        verdict = _parse_refusal_verdict(raw)
+    except (json.JSONDecodeError, KeyError, TypeError) as exc:
+        return {
+            "pass_": None,
+            "error": f"could not parse judge response: {exc}",
+            "raw": raw[:500],
+        }
+
+    verdict["metadata"] = {
+        "route": route,
+        "model": model,
+        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
+    }
+    return verdict
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index 94672531..29bac47f 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -1,126 +1,131 @@
 """Live agentic harness runner for VibeComfy headless scenarios.

 Scenarios run CONCURRENTLY — each in its own subprocess (process isolation +
 kill-on-timeout via ``subprocess.run``), bounded by ``--max-workers``. Modeled
 on the subagent-launcher fanout: one process per task, a bounded pool, a
 per-task timeout. ``--single`` is the per-scenario subprocess entry point.
 """

 from __future__ import annotations

 import argparse
 import json
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
+from .scenario_manifest import discover_manifest_scenarios

 DEFAULT_MAX_WORKERS = 12
 DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
 DEFAULT_PROGRESS_EVERY = 10
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
     return s if len(s) <= 400 else s[-400:]


 def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
     path.parent.mkdir(parents=True, exist_ok=True)
     tmp = path.with_suffix(path.suffix + ".tmp")
     tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
     tmp.replace(path)


 def _scenario_expect_graph_changed(scenario: dict[str, Any] | None) -> bool:
     assessment = scenario.get("assessment") if isinstance(scenario, dict) else None
     if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
         return bool(assessment["expect_graph_changed"])
     return False


 def _synthetic_guard(
     detail: str,
     *,
     failure_class: str = "runner_error",
     expect_graph_changed: bool = False,
 ) -> dict[str, Any]:
     """A failing guard for scenarios that errored/timed out in the runner itself."""
     return {
         "live_agentic_success": False,
         "metadata_success": False,
         "failure_class": failure_class,
         "score_class": "infra_blocked" if failure_class.startswith("infra_") else "product_fail",
         "assessment": {
             "passed": False,
             "expect_graph_changed": expect_graph_changed,
             "issue_count": 1,
             "error_count": 1,
             "issues": [
                 {
                     "check": "runner",
                     "severity": "error",
                     "detail": detail,
                     "failure_class": failure_class,
                 }
             ],
         },
     }


 def _failure_summary(
     scenario_id: str,
     output_base: Any,
     tag: str,
     detail: str,
     *,
     failure_class: str = "runner_error",
     attempt: int | None = None,
     expect_graph_changed: bool = False,
     stdout_tail: str | None = None,
     stderr_tail: str | None = None,
     elapsed_s: float | None = None,
 ) -> dict[str, Any]:
@@ -410,166 +415,167 @@ def _analysis_index_path_for_summary(run_summary_path: Path) -> Path:


 def _run_failure_analysis_from_summary(
     run_summary_path: Path,
     *,
     scenarios_dir: Path,
     analyze_failures_enabled: bool,
     prepare_only: bool,
     recommend_fixes: bool,
     analysis_model: str,
     analysis_max_workers: int,
     analysis_timeout: int,
     resume_failure_analysis: bool,
     recommendations_model: str,
     recommendations_timeout: int,
 ) -> dict[str, Any]:
     result: dict[str, Any] = {
         "run_summary_path": str(run_summary_path),
         "analysis_index_path": None,
         "recommendations_path": None,
     }
     index_path = _analysis_index_path_for_summary(run_summary_path)
     should_prepare = prepare_only or analyze_failures_enabled or (recommend_fixes and not index_path.exists())
     if should_prepare:
         if analyze_failures_enabled:
             index = analyze_failures(
                 run_summary_path,
                 scenarios_dir=scenarios_dir,
                 model=analysis_model,
                 max_workers=analysis_max_workers,
                 timeout_s=analysis_timeout,
                 resume=resume_failure_analysis,
             )
         else:
             index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)
         result["analysis_index_path"] = str(index_path)
         result["failed_count"] = index.get("failed_count", 0)
     elif index_path.exists():
         result["analysis_index_path"] = str(index_path)
     if recommend_fixes:
         meta = recommendations_for_run(
             run_summary_path,
             model=recommendations_model,
             timeout_s=recommendations_timeout,
         )
         result["recommendations_path"] = meta["output_path"]
         result["recommendations_returncode"] = meta["returncode"]
     return result


 def run_single(scenario_path: str, tag: str, output_base: Any, out_file: Path | None) -> dict[str, Any]:
     """Run ONE scenario in-process; write its summary JSON to *out_file* if given.

     This is the entry point invoked by the per-scenario subprocess in parallel mode.
     """
     from .adapter import run_headless_scenario
     from .guard import guard_output_dir

     path = Path(scenario_path)
     scenario = _load_scenario(path)
     scenario.setdefault("id", path.stem)
     summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
     summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
     _classify_retryable_infra_summary(summary)
     _persist_scenario_summary(summary, output_base, tag)
     if out_file is not None:
         out_file.parent.mkdir(parents=True, exist_ok=True)
         out_file.write_text(json.dumps(summary, default=str), encoding="utf-8")
     return summary


 def run_tag(
     tag: str,
     *,
     scenarios_dir: Path | None = None,
     output_base: Path | str | None = None,
     max_workers: int = DEFAULT_MAX_WORKERS,
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
     tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
     try:
         def record_result(idx: int, summary: dict[str, Any]) -> None:
             results[idx] = summary
             results[idx].setdefault("scenario_id", paths[idx].stem)
             _persist_scenario_summary(results[idx], output_base, tag)
             with lock:
                 completed = sum(1 for r in results if r)
                 run_summary = _persist_run_summary(
                     tag,
                     results,
                     output_base,
                     total_scenarios=len(paths),
                     complete=False,
                 )
                 if progress_every > 0 and (
                     completed == len(paths) or completed % progress_every == 0
                 ):
                     print(
                         "[agentic-progress] "
                         f"tag={tag} completed={completed}/{len(paths)} "
                         f"passed={run_summary['passed']} failed={run_summary['failed']} "
                         f"pending={run_summary['pending']}",
                         file=sys.stderr,
                         flush=True,
                     )

         def worker(idx: int, path: Path) -> None:
             sid = path.stem
             scenario_for_synthetic = _load_scenario(path)
             expect_graph_changed = _scenario_expect_graph_changed(scenario_for_synthetic)
             attempts: list[dict[str, Any]] = []
             with sem:
                 max_attempts = 1 + max(0, infra_retries)
                 final_summary: dict[str, Any] | None = None
                 for attempt in range(1, max_attempts + 1):
                     attempt_run_tag = _attempt_tag(tag, sid, attempt)
                     out_file = tmpdir / f"{idx:03d}-{attempt}.json"
                     cmd = [
                         sys.executable, "-m", "tests.live_agentic_harness.runner",
                         "--single", str(path), "--tag", attempt_run_tag,
                         "--single-out", str(out_file),
                     ]
                     if output_base is not None:
                         cmd += ["--output-base", str(output_base)]
                     started = time.monotonic()
                     try:
                         proc = subprocess.run(
                             cmd, cwd=str(REPO), capture_output=True, text=True,
                             timeout=per_scenario_timeout,
                         )
                         elapsed_s = time.monotonic() - started
                         if out_file.exists():
                             final_summary = json.loads(out_file.read_text(encoding="utf-8"))
                             final_summary["attempt"] = attempt
                             final_summary["elapsed_s"] = elapsed_s
                             final_summary["agent_exercised"] = True
                         else:
                             tail = _trim((proc.stderr or ""))
                             final_summary = _failure_summary(
                                 sid,
                                 output_base,
                                 attempt_run_tag,
                                 f"runner produced no summary (rc={proc.returncode}); {tail}",
                                 failure_class="infra_no_summary",
                                 attempt=attempt,
                                 expect_graph_changed=expect_graph_changed,
                                 stdout_tail=_trim(proc.stdout or ""),
                                 stderr_tail=tail,
                                 elapsed_s=elapsed_s,
                             )
                     except subprocess.TimeoutExpired as exc:
                         elapsed_s = time.monotonic() - started
                         final_summary = _failure_summary(
                             sid,
                             output_base,
                             attempt_run_tag,
@@ -595,278 +601,287 @@ def run_tag(
                         )

                     retryable_infra = _is_retryable_infra_summary(final_summary)
                     attempts.append(_attempt_record(final_summary, attempt=attempt))
                     if not retryable_infra:
                         break

                 if final_summary is None:
                     final_summary = _failure_summary(
                         sid,
                         output_base,
                         _attempt_tag(tag, sid, 1),
                         "runner produced no attempt result",
                         failure_class="infra_runner_exception",
                         attempt=1,
                         expect_graph_changed=expect_graph_changed,
                     )
                     attempts.append(_attempt_record(final_summary, attempt=1))

                 final_summary["attempts"] = attempts
                 final_summary["attempt_count"] = len(attempts)
                 final_summary["final_attempt"] = attempts[-1]["attempt"]
                 final_summary["raw_first_attempt_success"] = attempts[0].get("live_agentic_success") is True
                 final_summary["final_success"] = final_summary["guard"].get("live_agentic_success") is True
                 final_summary.setdefault(
                     "failure_class",
                     attempts[-1].get("failure_class") or "product_or_assessment_failure",
                 )
                 final_summary.setdefault(
                     "score_class",
                     attempts[-1].get("score_class") or (
                         "pass"
                         if final_summary["guard"].get("live_agentic_success") is True
                         else "product_fail"
                     ),
                 )
                 record_result(idx, final_summary)
                 _persist_canonical_scenario_summary(
                     final_summary,
                     output_base,
                     tag,
                     sid,
                 )

         threads = [
             threading.Thread(target=worker, args=(i, p), daemon=True)
             for i, p in enumerate(paths)
         ]
         for t in threads:
             t.start()
         for t in threads:
             t.join()
     finally:
         for f in tmpdir.glob("*.json"):
             try:
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
     )


 def _build_parser() -> argparse.ArgumentParser:
     parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
     parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
     parser.add_argument(
         "--scenarios-dir",
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
         out_file = Path(args.single_out) if args.single_out else None
         ob = Path(args.output_base) if args.output_base else None
         summary = run_single(args.single, args.tag, ob, out_file)
         # Compact one-line stdout for liveness; the real payload is in --single-out.
         print(json.dumps({"scenario_id": summary.get("scenario_id"),
                           "ok": summary["guard"]["live_agentic_success"]}))
         return 0 if summary["guard"]["live_agentic_success"] else 1

     output_base = Path(args.output_base) if args.output_base else None
     summary = run_tag(
         args.tag,
         scenarios_dir=scenarios_dir,
         output_base=output_base,
         max_workers=args.max_workers,
         per_scenario_timeout=args.per_scenario_timeout,
         progress_every=args.progress_every,
         infra_retries=args.infra_retries,
+        manifest_path=Path(args.manifest) if args.manifest else None,
     )
     if args.prepare_failure_analysis or args.analyze_failures or args.recommend_fixes:
         run_summary_path = _run_dir_for(output_base, summary["tag"]) / "run_summary.json"
         analysis = _run_failure_analysis_from_summary(
             run_summary_path,
             scenarios_dir=scenarios_dir,
             analyze_failures_enabled=args.analyze_failures,
             prepare_only=args.prepare_failure_analysis,
             recommend_fixes=args.recommend_fixes,
             analysis_model=args.analysis_model,
             analysis_max_workers=args.analysis_max_workers,
             analysis_timeout=args.analysis_timeout,
             resume_failure_analysis=not args.restart_failure_analysis,
             recommendations_model=args.recommendations_model,
             recommendations_timeout=args.recommendations_timeout,
         )
         summary["failure_analysis"] = analysis

     if args.json:
         print(json.dumps(summary, indent=2, default=str))
     else:
         print(f"tag: {summary['tag']}")
         print(f"scenarios: {summary['scenario_count']}")
         print(f"score: {summary['passed']}/{summary['scenario_count']}")
         print(
             f"raw_first_attempt_score: "
             f"{summary['raw_first_attempt_passed']}/{summary['scenario_count']}"
         )
         print(f"infra_failures: {summary['infra_failures']}")
         print(f"product_or_assessment_failures: {summary['product_or_assessment_failures']}")
         print(f"overall_success: {summary['overall_success']}")
         for s in summary["scenarios"]:
             assessment = s["guard"].get("assessment", {})
             errors = assessment.get("error_count", 0)
             print(
                 f"  {s['scenario_id']}: {s['status']} "
                 f"(live_agentic_success={s['guard']['live_agentic_success']}, "
                 f"assessment_errors={errors})"
             )

     return 0 if summary["overall_success"] or summary["scenario_count"] == 0 else 1


 if __name__ == "__main__":
     raise SystemExit(main())

exec
/bin/zsh -lc "nl -ba tests/test_live_agentic_harness_corpus_manifest.py | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
     1	from __future__ import annotations
     2
     3	import json
     4	from pathlib import Path
     5
     6	import pytest
     7
     8	from tests.live_agentic_harness.scenario_manifest import (
     9	    DEFAULT_MANIFEST_PATH,
    10	    DEFAULT_SCENARIOS_DIR,
    11	    ScenarioManifestError,
    12	    discover_manifest_scenarios,
    13	    sha256_file,
    14	    write_manifest,
    15	)
    16	from tests.live_agentic_harness.runner import run_tag
    17
    18
    19	CORRECTED_EDITS = {
    20	    "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
    21	    "video-image-to-video-conversion-with-moonvalley-d7853c",
    22	    "multi-3d-preview-and-image-output-workflow-d93baf",
    23	}
    24
    25
    26	def _scenario(path: Path) -> dict:
    27	    return json.loads(path.read_text(encoding="utf-8"))
    28
    29
    30	def test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios() -> None:
    31	    paths = discover_manifest_scenarios()
    32	    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    33	    entries = manifest["entries"]
    34
    35	    assert len(paths) == manifest["scenario_count"] == len(entries) == 100
    36	    assert len({entry["id"] for entry in entries}) == 100
    37	    assert len({entry["path"] for entry in entries}) == 100
    38	    assert all(entry["id"] == Path(entry["path"]).stem for entry in entries)
    39	    assert all(entry["inclusion_status"] == "included" for entry in entries)
    40	    assert {entry["revision_status"] for entry in entries} == {"matched", "revised"}
    41	    assert {entry["id"] for entry in entries if entry["revision_status"] == "revised"} == CORRECTED_EDITS
    42
    43	    source_entries = [entry for entry in entries if entry["source_workflow"]]
    44	    assert len(source_entries) == 98
    45	    for entry in source_entries:
    46	        source = entry["source_workflow"]
    47	        source_path = Path(__file__).parents[1] / source["path"]
    48	        assert source_path.is_file()
    49	        assert source["sha256"] == sha256_file(source_path)
    50
    51
    52	def test_d13_no_change_reconciliation_and_rubric_contract() -> None:
    53	    scenarios = [_scenario(path) for path in discover_manifest_scenarios()]
    54	    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
    55	    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
    56	    corrected = [s for s in scenarios if s["id"] in CORRECTED_EDITS]
    57
    58	    assert len(semantic) == 35
    59	    assert len(controls) == 2
    60	    assert len(corrected) == 3
    61	    assert len(semantic) + len(controls) + len(corrected) == 40
    62	    assert {s["_tags"]["query_type"] for s in semantic} == {"research", "explain", "diagnose"}
    63	    assert all(s["assessment"]["expect_graph_changed"] is False for s in semantic + controls)
    64	    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
    65	    assert all(s["assessment"]["expect_graph_changed"] is True and s["apply"] is True for s in corrected)
    66
    67	    for scenario in semantic:
    68	        rubric = scenario["answer_rubric"]
    69	        assert rubric["judge"] == "semantic_answer"
    70	        assert rubric["workflow_path"] == scenario["workflow_path"]
    71	        assert rubric["required_node_evidence"]
    72	        assert len(rubric["expected_criteria"]) >= 4
    73	        assert "grounded" in rubric["pass_condition"]
    74	        assert len(rubric["fail_conditions"]) == 5
    75
    76	    desired_edits = [s for s in scenarios if s.get("desired")]
    77	    assert desired_edits
    78	    for scenario in desired_edits:
    79	        assessment = scenario["assessment"]
    80	        # A desired edit is an active acceptance rubric: it must expect a graph
    81	        # change and must never be configured so a refusal can skip the judge.
    82	        assert assessment["expect_graph_changed"] is True, scenario["id"]
    83	        # skip_intent_judge would let an allowlisted refusal bypass ALL judging
    84	        # (both the edit-intent judge and the grounded-refusal gate) — invalid.
    85	        assert assessment.get("skip_intent_judge") is not True, (
    86	            f"{scenario['id']}: skip_intent_judge would let a refusal skip the judge"
    87	        )
    88
    89
    90	def test_runner_rejects_unmanifested_descriptor_before_execution(tmp_path: Path) -> None:
    91	    scenarios_dir = tmp_path / "scenarios"
    92	    scenarios_dir.mkdir()
    93	    (scenarios_dir / "one.json").write_text(
    94	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
    95	    )
    96	    write_manifest(scenarios_dir)
    97	    (scenarios_dir / "stray.json").write_text(
    98	        json.dumps({"id": "stray", "query": "stray"}), encoding="utf-8"
    99	    )
   100	    with pytest.raises(ScenarioManifestError, match="unmanifested"):
   101	        run_tag("stray-preflight", scenarios_dir=scenarios_dir, output_base=tmp_path / "out")
   102
   103
   104	def test_manifest_discovery_rejects_changed_or_missing_descriptor(tmp_path: Path) -> None:
   105	    scenarios_dir = tmp_path / "scenarios"
   106	    scenarios_dir.mkdir()
   107	    descriptor = scenarios_dir / "one.json"
   108	    descriptor.write_text(json.dumps({"id": "one", "query": "one"}), encoding="utf-8")
   109	    write_manifest(scenarios_dir)
   110	    descriptor.write_text(json.dumps({"id": "one", "query": "changed"}), encoding="utf-8")
   111	    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
   112	        discover_manifest_scenarios(scenarios_dir)
   113
   114	    descriptor.unlink()
   115	    with pytest.raises(ScenarioManifestError, match="missing"):
   116	        discover_manifest_scenarios(scenarios_dir)
   117
   118
   119	def test_manifest_discovery_rejects_duplicate_id_and_path(tmp_path: Path) -> None:
   120	    scenarios_dir = tmp_path / "scenarios"
   121	    scenarios_dir.mkdir()
   122	    (scenarios_dir / "one.json").write_text(
   123	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
   124	    )
   125	    manifest_path = write_manifest(scenarios_dir)
   126	    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   127	    manifest["entries"].append(dict(manifest["entries"][0]))
   128	    manifest["scenario_count"] = 2
   129	    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
   130	    with pytest.raises(ScenarioManifestError, match="duplicate scenario id"):
   131	        discover_manifest_scenarios(scenarios_dir)
   132
   133
   134	def test_manifest_discovery_rejects_duplicate_path_with_distinct_id(tmp_path: Path) -> None:
   135	    scenarios_dir = tmp_path / "scenarios"
   136	    scenarios_dir.mkdir()
   137	    (scenarios_dir / "one.json").write_text(
   138	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
   139	    )
   140	    manifest_path = write_manifest(scenarios_dir)
   141	    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   142	    duplicate = dict(manifest["entries"][0])
   143	    duplicate["id"] = "two"
   144	    manifest["entries"].append(duplicate)
   145	    manifest["scenario_count"] = 2
   146	    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
   147	    with pytest.raises(ScenarioManifestError, match="duplicate scenario path"):
   148	        discover_manifest_scenarios(scenarios_dir)

exec
/bin/zsh -lc "sed -n '1,100p' tests/live_agentic_harness/scenario_manifest.json && tail -80 tests/live_agentic_harness/scenario_manifest.json" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 51ms:
{
  "schema_version": 1,
  "scenario_root": "tests/live_agentic_harness/scenarios",
  "scenario_count": 100,
  "entries": [
    {
      "id": "3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json",
      "descriptor_sha256": "f2d7ac44c1d69ddbc3da300e0700868a9107e64c2ce5b75a405d92080b761f46",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "c24aa2ac329006f2",
        "path": "external_workflows/corpus/c24aa2ac329006f2.json",
        "sha256": "3c605c00652907736c02e5c4bfff6fa17c9edbfd06024be972b004dc2332f180"
      }
    },
    {
      "id": "3d-3d-model-generation-and-preview-workflow-cc0df7",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json",
      "descriptor_sha256": "cace0fcd18209e4aa4197e4f4571bb4de4d15bc8f1b9148edf5b63e2906cbb43",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "cc0df70583f28c98",
        "path": "external_workflows/corpus/cc0df70583f28c98.json",
        "sha256": "f59807058734a50e245e4d97446e42d378a6589457f9359a05f9b5da09400583"
      }
    },
    {
      "id": "3d-3d-model-generation-and-retargeting-workflow-f65774",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json",
      "descriptor_sha256": "56ec24c8f324bb7d0f94befd5e3392d6f90d850e3556a25e970f54754adff64d",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "f657743bc2a3db17",
        "path": "external_workflows/corpus/f657743bc2a3db17.json",
        "sha256": "4874162874ab6ddce8b7a248382e5ee20a392158f423c14f8ce1fffd4f21833e"
      }
    },
    {
      "id": "3d-3d-model-generation-and-rigging-from-image-352066",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json",
      "descriptor_sha256": "d071f50f251ca718363ae04177d35f66ad1e26b305be7b7dd220ed10f62b6dee",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "352066ccef9dbe37",
        "path": "external_workflows/corpus/352066ccef9dbe37.json",
        "sha256": "cb759b44eeef9b28df2ed3f0d0e835ce3d2d35770930a7d0a95cbaccb80b68f3"
      }
    },
    {
      "id": "3d-3d-model-generation-and-rigging-workflow-90a1d5",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json",
      "descriptor_sha256": "7555873253d66728e17ec5180d8d61063e9aa25d4704c5e63101fecd0541ad94",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "90a1d5ff9044902e",
        "path": "external_workflows/corpus/90a1d5ff9044902e.json",
        "sha256": "3f7fe8c665328f4ffa8db8f851da2081f288c9e2d107fd697c89de8655cf5f63"
      }
    },
    {
      "id": "3d-3d-model-load-edit-and-export-workflow-d66a66",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-model-load-edit-and-export-workflow-d66a66.json",
      "descriptor_sha256": "5fe9bba69049a4849346c505321eac3e7a4c44b212b67d8e940de12f92874bbe",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "d66a660d74cbc9ec",
        "path": "external_workflows/corpus/d66a660d74cbc9ec.json",
        "sha256": "6855d89472a70305bedfdcdd14b1caaf4287afe333cd1e4f6c5a409d2b77b44c"
      }
    },
    {
      "id": "3d-3d-shape-generation-and-export-workflow-8800a9",
      "path": "tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json",
      "descriptor_sha256": "4c8dfefcdd372108a83b88fd5b855c557f3fc3ef436e40cb92418e02a4b3a6c0",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "8800a945cff8d090",
        "path": "external_workflows/corpus/8800a945cff8d090.json",
        "sha256": "134ec19b6bd7158373e968face34c9bd2390c8e1011d40c92fc077e6a08f7658"
      }
    },
    {
      "id": "3d-converts-image-to-3d-model",
      "path": "tests/live_agentic_harness/scenarios/3d-converts-image-to-3d-model.json",
      "descriptor_sha256": "5f131e3f6743491dc8ce59b63d5e52d50091d8f4bf7c199f76b130ada6f2214c",
    {
      "id": "video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9",
      "path": "tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json",
      "descriptor_sha256": "24fdb142ea8caebfd3f286f0aedb54122f4b7804a727381a3d1f0335a063e311",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "semantic_product",
      "source_workflow": {
        "id": "374aa988d0a133be",
        "path": "external_workflows/corpus/374aa988d0a133be.json",
        "sha256": "9c5506586ffe421d7036c393ece06f5d54136505115187a259bc9d64f1c6f49c"
      }
    },
    {
      "id": "video-wan2-2-text-to-video-with-dual-unet-and-model-03fced",
      "path": "tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json",
      "descriptor_sha256": "f4b4d6aadc320f1e02d88c0c33fdaf05ba3f146e63ebf9c13780569d081cca87",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "edit",
      "source_workflow": {
        "id": "03fcedf997c13003",
        "path": "external_workflows/corpus/03fcedf997c13003.json",
        "sha256": "59dd2c79a049f5cc7c822e01265c9874f7215565f71e7eda403426c23bac774a"
      }
    },
    {
      "id": "video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3",
      "path": "tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json",
      "descriptor_sha256": "b39a28160c01c811f0ef1f70811960ee4b6a4b45b2c8cbed619375f59e3addac",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "semantic_product",
      "source_workflow": {
        "id": "7c8bb3b65e8084ae",
        "path": "external_workflows/corpus/7c8bb3b65e8084ae.json",
        "sha256": "93eb79de70cc379a83d40bcb131b6e9d8c9b1133de89e961b325ab5c7078ee83"
      }
    },
    {
      "id": "video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a",
      "path": "tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json",
      "descriptor_sha256": "637dfff0f769548b04e2b699b7f9e54aa1f156b9a6142e82bcc3b9ef76619c52",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "semantic_product",
      "source_workflow": {
        "id": "62682a77ae33b43a",
        "path": "external_workflows/corpus/62682a77ae33b43a.json",
        "sha256": "a518f843af614e923733dbee9e3cd7d346fb1d220bc1404abb9c5cc640545969"
      }
    },
    {
      "id": "video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9",
      "path": "tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json",
      "descriptor_sha256": "60430aa6027ef838aa9c4815a09ab297d65c90db428875360186e34c9c47e856",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "semantic_product",
      "source_workflow": {
        "id": "82ffb9156459a82e",
        "path": "external_workflows/corpus/82ffb9156459a82e.json",
        "sha256": "b1234ae980088293b2e8cfa294548b7fcae8e13f286e4cd5f1f87833d976c1a4"
      }
    },
    {
      "id": "video-wanvideo-text-to-video-generation-71f825",
      "path": "tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json",
      "descriptor_sha256": "df4959641e24bfcd7b62ad558dc4cede081febf7e14f44475fd3a70855f60d31",
      "inclusion_status": "included",
      "revision_status": "matched",
      "scenario_kind": "semantic_product",
      "source_workflow": {
        "id": "71f825e4550c95b7",
        "path": "external_workflows/corpus/71f825e4550c95b7.json",
        "sha256": "87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3"
      }
    }
  ]
}

 succeeded in 105ms:
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

exec
/bin/zsh -lc 'rg -n "discover_manifest|manifest_path|answer_rubric|semantic_answer|health_control|excluded_from_semantic|desired|skip_intent_judge|judge_unavailable|intent_judge|grounded_refusal|refusal" tests/live_agentic_harness/{runner.py,assessor.py,intent_judge.py} tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'for f in tests/live_agentic_harness/scenarios/*485ff2.json tests/live_agentic_harness/scenarios/*d7853c.json tests/live_agentic_harness/scenarios/*d93baf.json; do echo "FILE $f"; git diff --unified=40 0f015101..5aa73c53 -- "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/REVISIONS.md && nl -ba tests/live_agentic_harness/README.md | sed -n '1,240p' && nl -ba .gitignore | tail -30" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 24ms:
    50	this.env
    51	_debug_*.py
    52	_fix_t6.py
    53	_regen_templates.py
    54	finalize.json
    55	install.log
    56	.hypothesis/
    57	.tmp/
    58	node_modules/
    59	*.pid
    60	*.zip
    61	comfyui_*.png
    62	comfyui_screenshot*.png
    63	comfyui_panel_open*.png
    64	agent_edit_e2e.mjs
    65	local_env.sh
    66
    67	# e2e test tier — isolated dependency management
    68	tests/e2e/node_modules/
    69	tests/e2e/playwright-report/
    70	tests/e2e/test-results/
    71	test-results/
    72
    73	# Generated cache-busted web assets
    74	vibecomfy/comfy_nodes/web_dist/
    75
    76	# Live agentic watchdog run artifacts (logs, backups, baselines, codex outputs)
    77	.watchdog-runs/
    78	.venv
    79	external_workflows

exec
/bin/zsh -lc 'git show --format=fuller --stat --oneline 5aa73c53 && git diff --numstat 0f015101..5aa73c53 | tail -10' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 233ms:
FILE tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json b/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
index b61b9bfb..bc4fc210 100644
--- a/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
+++ b/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
@@ -1,37 +1,40 @@
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
     "query_type": "edit",
     "abstraction": "low",
     "complexity": "low",
     "manifest_complexity": 2,
     "task_type": "inpainting",
     "requires_custom_nodes": true,
     "techniques": [
       "video-inpainting",
       "spline-editing",
       "cut-and-drag",
       "image-inpainting",
       "video-combine"
     ],
     "source_workflow_id": "485ff2fa6dcc1917",
     "source": "external_workflows/corpus",
     "staged": true,
     "authored_by": "deepseek-v4-pro",
     "author_rationale": "This targets a specific technique in the spline-cut-and-drag pipeline (inpainting blend) and tests whether the agent can distinguish it from generic model settings."
+  },
+  "classification": {
+    "kind": "edit"
   }
 }
FILE tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json b/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
index 129cfe8b..99562d06 100644
--- a/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
+++ b/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
@@ -1,36 +1,39 @@
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
     "modality": "video",
     "query_type": "edit",
     "abstraction": "low",
     "complexity": "low",
     "manifest_complexity": 1,
     "task_type": "other",
     "requires_custom_nodes": true,
     "techniques": [
       "image-to-video",
       "moonvalley",
       "video-generation",
       "custom-node"
     ],
     "source_workflow_id": "d7853cd7421f9ebc",
     "source": "external_workflows/corpus",
     "staged": true,
     "authored_by": "deepseek-v4-flash",
     "author_rationale": "A simple, concrete parameter edit that requires reasoning about frame count vs. fps to hit a target duration."
+  },
+  "classification": {
+    "kind": "edit"
   }
 }
FILE tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json b/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
index f56d2f9d..3af2ad55 100644
--- a/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
+++ b/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
@@ -1,37 +1,40 @@
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
     "query_type": "edit",
     "abstraction": "low",
     "complexity": "low",
     "manifest_complexity": 2,
     "task_type": "other",
     "requires_custom_nodes": true,
     "techniques": [
       "3d",
       "glb",
       "image-loading",
       "preview",
       "save"
     ],
     "source_workflow_id": "d93baf73c8a43f57",
     "source": "external_workflows/corpus",
     "staged": true,
     "authored_by": "deepseek-v4-pro",
     "author_rationale": "Specific, simple edit that tests parameter change without breaking the 3D pipeline."
+  },
+  "classification": {
+    "kind": "edit"
   }
 }

 succeeded in 437ms:
tests/test_live_agentic_intent_judge_schema_context.py:6:from tests.live_agentic_harness.intent_judge import judge_edit_intent
tests/test_live_agentic_intent_judge_schema_context.py:9:def test_intent_judge_includes_scenario_desired_rubric(
tests/test_live_agentic_intent_judge_schema_context.py:33:                    "rationale": "desired outcome satisfied",
tests/test_live_agentic_intent_judge_schema_context.py:39:        "tests.live_agentic_harness.intent_judge.run_model_turn",
tests/test_live_agentic_intent_judge_schema_context.py:42:    desired = {
tests/test_live_agentic_intent_judge_schema_context.py:49:        {"query": "set seed to 42", "desired": desired},
tests/test_live_agentic_intent_judge_schema_context.py:55:    assert "Scenario-specific desired outcome" in messages[0]["content"]
tests/test_live_agentic_intent_judge_schema_context.py:57:    assert payload["desired_outcome"] == desired
tests/test_live_agentic_intent_judge_schema_context.py:60:def test_intent_judge_includes_compiled_api_schema_context(
tests/test_live_agentic_intent_judge_schema_context.py:119:        "tests.live_agentic_harness.intent_judge.run_model_turn",
tests/test_live_agentic_intent_judge_schema_context.py:136:def test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input(
tests/test_live_agentic_intent_judge_schema_context.py:209:        "tests.live_agentic_harness.intent_judge.run_model_turn",
tests/test_live_agentic_intent_judge_schema_context.py:231:def test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope(
tests/test_live_agentic_intent_judge_schema_context.py:313:        "tests.live_agentic_harness.intent_judge.run_model_turn",
tests/live_agentic_harness/assessor.py:29:from .intent_judge import judge_edit_intent, judge_grounded_refusal
tests/live_agentic_harness/assessor.py:320:def _allowed_safe_refusal_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
tests/live_agentic_harness/assessor.py:321:    """Return no-edit outcome kinds accepted as safe refusals for edit scenarios."""
tests/live_agentic_harness/assessor.py:327:    raw = assessment.get("allow_safe_refusal_outcome_kinds")
tests/live_agentic_harness/assessor.py:329:        raw = assessment.get("allow_safe_refusal_outcome_kind")
tests/live_agentic_harness/assessor.py:635:    allowed_safe_refusal_outcome_kinds = _allowed_safe_refusal_outcome_kinds(scenario)
tests/live_agentic_harness/assessor.py:636:    safe_refusal_accepted = False
tests/live_agentic_harness/assessor.py:641:        safe_refusal_accepted = (
tests/live_agentic_harness/assessor.py:645:            and outcome_kind in allowed_safe_refusal_outcome_kinds
tests/live_agentic_harness/assessor.py:679:            if safe_refusal_accepted:
tests/live_agentic_harness/assessor.py:682:                        "check": "safe_refusal",
tests/live_agentic_harness/assessor.py:684:                        "detail": f"Accepted safe refusal outcome.kind={outcome_kind!r}.",
tests/live_agentic_harness/assessor.py:699:            # zero counts fail closed.  Accepted grounded refusals
tests/live_agentic_harness/assessor.py:700:            # (safe_refusal_accepted) and canonical non-edit routes are
tests/live_agentic_harness/assessor.py:704:                not safe_refusal_accepted
tests/live_agentic_harness/assessor.py:729:            # unchanged (or the refusal is authorized above); an edit-route
tests/live_agentic_harness/assessor.py:733:                not safe_refusal_accepted
tests/live_agentic_harness/assessor.py:749:            if not safe_refusal_accepted and no_reason in {"no_changes", "no_candidate"}:
tests/live_agentic_harness/assessor.py:758:            if not safe_refusal_accepted and outcome_kind in {"noop", "requires_custom_nodes"}:
tests/live_agentic_harness/assessor.py:783:            if false_gates and not safe_refusal_accepted:
tests/live_agentic_harness/assessor.py:792:            if not safe_refusal_accepted:
tests/live_agentic_harness/assessor.py:811:        # ``assessment.skip_intent_judge: true`` in the scenario to disable it.
tests/live_agentic_harness/assessor.py:812:        # A DESIRED edit must never pass on an allowlisted refusal label
tests/live_agentic_harness/assessor.py:813:        # without an active grounded-refusal judge: the judge runs and must
tests/live_agentic_harness/assessor.py:814:        # confirm the refusal is grounded (supported blocker, no representable
tests/live_agentic_harness/assessor.py:817:        # refusal label is never a safe refusal (safe_refusal_accepted requires
tests/live_agentic_harness/assessor.py:819:        # and — for desired scenarios — fails closed without a judge verdict.
tests/live_agentic_harness/assessor.py:820:        # Non-desired edit-or-refuse scenarios keep the historical bypass.
tests/live_agentic_harness/assessor.py:823:            and not scenario.get("assessment", {}).get("skip_intent_judge")
tests/live_agentic_harness/assessor.py:825:            if safe_refusal_accepted and scenario.get("desired"):
tests/live_agentic_harness/assessor.py:826:                verdict = judge_grounded_refusal(output_dir, scenario)
tests/live_agentic_harness/assessor.py:830:                            "check": "grounded_refusal",
tests/live_agentic_harness/assessor.py:841:                            "check": "grounded_refusal",
tests/live_agentic_harness/assessor.py:844:                                f"Grounded refusal confirmed: {verdict.get('rationale', 'no rationale')} "
tests/live_agentic_harness/assessor.py:852:                            "check": "grounded_refusal",
tests/live_agentic_harness/assessor.py:853:                            # A desired block is an active acceptance rubric;
tests/live_agentic_harness/assessor.py:854:                            # an absent grounded-refusal judge fails closed.
tests/live_agentic_harness/assessor.py:857:                                "Grounded-refusal judge could not run: "
tests/live_agentic_harness/assessor.py:862:            elif not safe_refusal_accepted:
tests/live_agentic_harness/assessor.py:867:                            "check": "intent_judge",
tests/live_agentic_harness/assessor.py:878:                            "check": "intent_judge",
tests/live_agentic_harness/assessor.py:889:                            "check": "intent_judge",
tests/live_agentic_harness/assessor.py:890:                            # A desired block is an active acceptance rubric, not
tests/live_agentic_harness/assessor.py:892:                            "severity": "error" if scenario.get("desired") else "warning",
tests/live_agentic_harness/assessor.py:969:        "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
tests/live_agentic_harness/intent_judge.py:19:_REFUSAL_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "refusal_judge.prompt.md"
tests/live_agentic_harness/intent_judge.py:43:def _load_refusal_prompt() -> str:
tests/live_agentic_harness/intent_judge.py:50:        "a reason. You must determine whether that refusal is GROUNDED (the model\n"
tests/live_agentic_harness/intent_judge.py:53:        "Evaluate the refusal against exactly four binary criteria:\n"
tests/live_agentic_harness/intent_judge.py:54:        "- supported_blocker: the refusal cites a real, supported blocker (for\n"
tests/live_agentic_harness/intent_judge.py:59:        "- specific_next_action: the refusal states a concrete next action that\n"
tests/live_agentic_harness/intent_judge.py:62:        "- no_fabricated_inability: the refusal does not falsely claim an inability\n"
tests/live_agentic_harness/intent_judge.py:103:def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
tests/live_agentic_harness/intent_judge.py:104:    """Parse the grounded-refusal judge's JSON response into a normalized dict."""
tests/live_agentic_harness/intent_judge.py:369:    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
tests/live_agentic_harness/intent_judge.py:373:    desired = scenario.get("desired")
tests/live_agentic_harness/intent_judge.py:374:    if desired:
tests/live_agentic_harness/intent_judge.py:377:            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
tests/live_agentic_harness/intent_judge.py:379:            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
tests/live_agentic_harness/intent_judge.py:384:            f"Desired outcome: {desired.get('outcome', '')}\n"
tests/live_agentic_harness/intent_judge.py:385:            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
tests/live_agentic_harness/intent_judge.py:386:            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
tests/live_agentic_harness/intent_judge.py:389:    if desired:
tests/live_agentic_harness/intent_judge.py:390:        payload["desired_outcome"] = desired
tests/live_agentic_harness/intent_judge.py:430:def judge_grounded_refusal(
tests/live_agentic_harness/intent_judge.py:437:    """Run the DeepSeek grounded-refusal judge for a desired edit scenario.
tests/live_agentic_harness/intent_judge.py:439:    A desired edit may pass on an allowlisted refusal label ONLY when this judge
tests/live_agentic_harness/intent_judge.py:440:    confirms the refusal is grounded: the cited blocker is real and supported,
tests/live_agentic_harness/intent_judge.py:441:    no representable edit could satisfy the intent, the refusal states a
tests/live_agentic_harness/intent_judge.py:453:    # The refusal envelope is read from the run's response.json: outcome kind,
tests/live_agentic_harness/intent_judge.py:457:    refusal: dict[str, Any] = {}
tests/live_agentic_harness/intent_judge.py:464:            refusal = {
tests/live_agentic_harness/intent_judge.py:473:    if not isinstance(refusal.get("outcome"), Mapping):
tests/live_agentic_harness/intent_judge.py:474:        return {"pass_": None, "error": "response.json is missing a refusal outcome"}
tests/live_agentic_harness/intent_judge.py:476:    system_prompt = _load_refusal_prompt()
tests/live_agentic_harness/intent_judge.py:484:            "blocker is real. A 'requires_custom_nodes' refusal is fabricated if "
tests/live_agentic_harness/intent_judge.py:488:    desired = scenario.get("desired")
tests/live_agentic_harness/intent_judge.py:489:    payload: dict[str, Any] = {"nl_intent": query, "refusal": refusal}
tests/live_agentic_harness/intent_judge.py:490:    if desired:
tests/live_agentic_harness/intent_judge.py:491:        payload["desired_outcome"] = desired
tests/live_agentic_harness/intent_judge.py:498:            "evaluate whether a workflow-edit refusal is grounded",
tests/live_agentic_harness/intent_judge.py:515:        verdict = _parse_refusal_verdict(raw)
tests/live_agentic_harness/runner.py:36:from .scenario_manifest import discover_manifest_scenarios
tests/live_agentic_harness/runner.py:47:    manifest_path: Path | None = None,
tests/live_agentic_harness/runner.py:51:    return discover_manifest_scenarios(scenarios_dir, manifest_path=manifest_path)
tests/live_agentic_harness/runner.py:495:    manifest_path: Path | None = None,
tests/live_agentic_harness/runner.py:501:    paths = _scenario_paths(scenarios_dir, manifest_path=manifest_path)
tests/live_agentic_harness/runner.py:842:        manifest_path=Path(args.manifest) if args.manifest else None,
tests/test_live_agentic_harness_guard_contract.py:69:def _write_safe_refusal_response(
tests/test_live_agentic_harness_guard_contract.py:96:def _desired_edit_scenario(scenario_id: str, kind: str = "requires_custom_nodes") -> dict:
tests/test_live_agentic_harness_guard_contract.py:102:            "allow_safe_refusal_outcome_kinds": ["clarify", kind],
tests/test_live_agentic_harness_guard_contract.py:104:        "desired": {
tests/test_live_agentic_harness_guard_contract.py:112:def _grounded_refusal_verdict(*, grounded: bool) -> dict:
tests/test_live_agentic_harness_guard_contract.py:123:            "blocker is real and the refusal names a concrete next action"
tests/test_live_agentic_harness_guard_contract.py:135:            "skip_intent_judge": True,
tests/test_live_agentic_harness_guard_contract.py:272:def test_agentic_guard_allows_explicit_safe_refusal_scenarios(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:273:    output_dir = tmp_path / "safe-refusal"
tests/test_live_agentic_harness_guard_contract.py:303:        "id": "safe-refusal",
tests/test_live_agentic_harness_guard_contract.py:318:def test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:319:    output_dir = tmp_path / "wrong-refusal"
tests/test_live_agentic_harness_guard_contract.py:335:        "id": "wrong-refusal",
tests/test_live_agentic_harness_guard_contract.py:349:def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:383:            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
tests/test_live_agentic_harness_guard_contract.py:392:    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
tests/test_live_agentic_harness_guard_contract.py:393:    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}
tests/test_live_agentic_harness_guard_contract.py:396:def test_desired_edit_rejects_safe_refusal_when_grounded_judge_unavailable(
tests/test_live_agentic_harness_guard_contract.py:400:    """D13 finding 5, fail-closed: a desired edit may not pass on an
tests/test_live_agentic_harness_guard_contract.py:401:    allowlisted refusal label when the grounded-refusal judge cannot run."""
tests/test_live_agentic_harness_guard_contract.py:402:    output_dir = tmp_path / "desired-refusal-judge-unavailable"
tests/test_live_agentic_harness_guard_contract.py:404:    _write_safe_refusal_response(output_dir)
tests/test_live_agentic_harness_guard_contract.py:409:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
tests/test_live_agentic_harness_guard_contract.py:415:        scenario=_desired_edit_scenario("desired-refusal-judge-unavailable"),
tests/test_live_agentic_harness_guard_contract.py:420:        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
tests/test_live_agentic_harness_guard_contract.py:425:def test_desired_edit_rejects_fabricated_safe_refusal(
tests/test_live_agentic_harness_guard_contract.py:429:    """D13 finding 5: a fabricated/unsupported requires_custom_nodes refusal
tests/test_live_agentic_harness_guard_contract.py:430:    (judge: not grounded) must fail a desired edit."""
tests/test_live_agentic_harness_guard_contract.py:431:    output_dir = tmp_path / "desired-refusal-fabricated"
tests/test_live_agentic_harness_guard_contract.py:433:    _write_safe_refusal_response(output_dir)
tests/test_live_agentic_harness_guard_contract.py:438:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
tests/test_live_agentic_harness_guard_contract.py:439:        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=False),
tests/test_live_agentic_harness_guard_contract.py:444:        scenario=_desired_edit_scenario("desired-refusal-fabricated"),
tests/test_live_agentic_harness_guard_contract.py:449:        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
tests/test_live_agentic_harness_guard_contract.py:454:def test_desired_edit_accepts_grounded_safe_refusal(
tests/test_live_agentic_harness_guard_contract.py:458:    """D13 finding 5, positive control: a genuine grounded refusal (judge:
tests/test_live_agentic_harness_guard_contract.py:459:    grounded) may still pass a desired edit."""
tests/test_live_agentic_harness_guard_contract.py:460:    output_dir = tmp_path / "desired-refusal-grounded"
tests/test_live_agentic_harness_guard_contract.py:462:    _write_safe_refusal_response(output_dir)
tests/test_live_agentic_harness_guard_contract.py:467:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
tests/test_live_agentic_harness_guard_contract.py:468:        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
tests/test_live_agentic_harness_guard_contract.py:473:        scenario=_desired_edit_scenario("desired-refusal-grounded"),
tests/test_live_agentic_harness_guard_contract.py:480:        issue["check"] == "grounded_refusal" and issue["severity"] == "info"
tests/test_live_agentic_harness_guard_contract.py:485:def test_desired_edit_refusal_label_with_graph_change_fails_closed_without_verdict(
tests/test_live_agentic_harness_guard_contract.py:489:    """D13 finding 5: graph_unchanged=false plus a refusal label is never a
tests/test_live_agentic_harness_guard_contract.py:490:    safe refusal; without any grounded judge verdict a desired edit fails
tests/test_live_agentic_harness_guard_contract.py:492:    output_dir = tmp_path / "desired-refusal-graph-changed"
tests/test_live_agentic_harness_guard_contract.py:494:    _write_safe_refusal_response(output_dir, graph_unchanged=False)
tests/test_live_agentic_harness_guard_contract.py:499:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
tests/test_live_agentic_harness_guard_contract.py:509:        scenario=_desired_edit_scenario("desired-refusal-graph-changed"),
tests/test_live_agentic_harness_guard_contract.py:518:    assert "intent_judge" in error_checks, verdict["assessment"]["issues"]
tests/test_live_agentic_harness_guard_contract.py:542:            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
tests/test_live_agentic_harness_guard_contract.py:593:def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
tests/test_live_agentic_harness_guard_contract.py:597:    output_dir = tmp_path / "desired-judge-unavailable"
tests/test_live_agentic_harness_guard_contract.py:611:            "id": "desired-judge-unavailable",
tests/test_live_agentic_harness_guard_contract.py:614:            "desired": {
tests/test_live_agentic_harness_guard_contract.py:624:        issue["check"] == "intent_judge" and issue["severity"] == "error"
tests/test_live_agentic_harness_guard_contract.py:650:            "skip_intent_judge": True,
tests/test_live_agentic_harness_guard_contract.py:689:            "skip_intent_judge": True,
tests/test_live_agentic_harness_guard_contract.py:949:            "skip_intent_judge": True,
tests/test_live_agentic_harness_guard_contract.py:990:        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1117:        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1135:# zero counts fail closed; accepted grounded refusals and canonical
tests/test_live_agentic_harness_guard_contract.py:1175:        "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1213:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1226:def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
tests/test_live_agentic_harness_guard_contract.py:1229:    """G0R: an accepted grounded refusal (graph_unchanged=true, allowed
tests/test_live_agentic_harness_guard_contract.py:1231:    output_dir = tmp_path / "landed-count-refusal-exempt"
tests/test_live_agentic_harness_guard_contract.py:1249:            "id": "landed-count-refusal-exempt",
tests/test_live_agentic_harness_guard_contract.py:1252:                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
tests/test_live_agentic_harness_guard_contract.py:1259:    assert {issue["check"] for issue in verdict["assessment"]["issues"]} == {"safe_refusal"}
tests/test_live_agentic_harness_guard_contract.py:1291:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1327:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1364:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1381:    graph_unchanged=true and an authorized refusal outcome kind is still
tests/test_live_agentic_harness_guard_contract.py:1406:                "allow_safe_refusal_outcome_kinds": ["respond", "clarify"],
tests/test_live_agentic_harness_guard_contract.py:1407:                "skip_intent_judge": True,
tests/test_live_agentic_harness_guard_contract.py:1415:    assert "safe_refusal" in checks
tests/test_live_agentic_harness_guard_contract.py:1446:            "assessment": {"expect_graph_changed": True, "skip_intent_judge": True},
tests/test_live_agentic_harness_guard_contract.py:1526:        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
tests/test_live_agentic_harness_guard_contract.py:1566:        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},

 succeeded in 386ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
5aa73c53 megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green
 .oracle/briefs/batch-D13-rework.md                 |   33 +
 .oracle/checkins/batch-D13.md                      | 9835 ++++++++++++++++++++
 tests/live_agentic_harness/assessor.py             |  116 +-
 tests/live_agentic_harness/intent_judge.py         |  163 +-
 tests/test_live_agentic_harness_corpus_manifest.py |   12 +-
 tests/test_live_agentic_harness_guard_contract.py  |  187 +
 vibecomfy/intent/prompts/refusal_judge.prompt.md   |   43 +
 7 files changed, 10347 insertions(+), 42 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
30	0	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json
29	0	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json
29	0	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
30	0	tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
148	0	tests/test_live_agentic_harness_corpus_manifest.py
270	0	tests/test_live_agentic_harness_guard_contract.py
3	0	tests/test_live_agentic_harness_runner_persistence.py
51	0	tests/test_live_agentic_intent_judge_schema_context.py
9	0	tests/test_live_agentic_runner_persistence.py
43	0	vibecomfy/intent/prompts/refusal_judge.prompt.md

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '1,150p'; nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '330,540p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
     1	"""LLM intent judge for live agentic harness artifacts.
     2
     3	Provides a DeepSeek-backed text judge that scores a candidate workflow edit
     4	against the scenario's natural-language intent.  The judge is intentionally
     5	separate from the deterministic assessor so it can be enabled/disabled without
     6	changing the core pass/fail logic.
     7	"""
     8
     9	from __future__ import annotations
    10
    11	import json
    12	import os
    13	from pathlib import Path
    14	from typing import Any, Mapping
    15
    16	from vibecomfy.comfy_nodes.agent.provider import run_model_turn
    17
    18	_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "text_judge.prompt.md"
    19	_REFUSAL_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "refusal_judge.prompt.md"
    20
    21
    22	def _load_prompt() -> str:
    23	    if _PROMPT_PATH.is_file():
    24	        return _PROMPT_PATH.read_text(encoding="utf-8")
    25	    # Fallback rubric if the canonical prompt is missing.
    26	    return (
    27	        "You are a precise evaluator for ComfyUI workflow edits. Given a natural-language\n"
    28	        "intent and a structural diff between a pre-edit and post-edit workflow IR, you\n"
    29	        "must determine whether the edit correctly implements the intent.\n\n"
    30	        "Evaluate the edit against exactly four binary criteria:\n"
    31	        "- correct_node_targeted\n"
    32	        "- correct_parameter_changed\n"
    33	        "- value_semantically_matches_intent\n"
    34	        "- no_orphaned_wiring\n\n"
    35	        "Respond with a JSON object and nothing else:\n"
    36	        '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
    37	        '"correct_parameter_changed": true | false, "value_semantically_matches_intent": true | false, '
    38	        '"no_orphaned_wiring": true | false}, "rationale": "<one or two sentences>"}\n'
    39	        "`pass_` must be true if and only if all four criteria are true."
    40	    )
    41
    42
    43	def _load_refusal_prompt() -> str:
    44	    if _REFUSAL_PROMPT_PATH.is_file():
    45	        return _REFUSAL_PROMPT_PATH.read_text(encoding="utf-8")
    46	    # Fallback rubric if the canonical prompt is missing.
    47	    return (
    48	        "You are a precise evaluator for ComfyUI workflow edits. A model was asked\n"
    49	        "to perform an edit but refused and left the workflow graph unchanged, citing\n"
    50	        "a reason. You must determine whether that refusal is GROUNDED (the model\n"
    51	        "could not honestly satisfy the intent) or fabricated/unsupported (the model\n"
    52	        "dodged an edit it could have made).\n\n"
    53	        "Evaluate the refusal against exactly four binary criteria:\n"
    54	        "- supported_blocker: the refusal cites a real, supported blocker (for\n"
    55	        "  example, a node class genuinely absent from the installed schema, or a\n"
    56	        "  genuine ambiguity in the request) rather than a made-up constraint.\n"
    57	        "- no_representable_edit: no representable edit to the given workflow could\n"
    58	        "  satisfy the intent, so refusing was the only honest option.\n"
    59	        "- specific_next_action: the refusal states a concrete next action that\n"
    60	        "  would unblock the edit (for example, installing a named custom node, or\n"
    61	        "  answering a named clarifying question).\n"
    62	        "- no_fabricated_inability: the refusal does not falsely claim an inability\n"
    63	        "  (for example, claiming a node is unavailable when the schema contains it,\n"
    64	        "  or claiming the request is ambiguous when it is concrete).\n\n"
    65	        "Respond with a JSON object and nothing else:\n"
    66	        '{"pass_": true | false, "criteria": {"supported_blocker": true | false, '
    67	        '"no_representable_edit": true | false, "specific_next_action": true | false, '
    68	        '"no_fabricated_inability": true | false}, "rationale": "<one or two sentences>"}\n'
    69	        "`pass_` must be true if and only if all four criteria are true."
    70	    )
    71
    72
    73	def _strip_code_fences(text: str) -> str:
    74	    """Strip markdown fences some models wrap JSON responses in."""
    75	    text = text.strip()
    76	    if text.startswith("```"):
    77	        lines = text.splitlines()
    78	        if lines[0].startswith("```"):
    79	            lines = lines[1:]
    80	        if lines and lines[-1].startswith("```"):
    81	            lines = lines[:-1]
    82	        text = "\n".join(lines).strip()
    83	    return text
    84
    85
    86	def _parse_verdict(raw: str) -> dict[str, Any]:
    87	    """Parse the judge's JSON response into a normalized dict."""
    88	    parsed = json.loads(_strip_code_fences(raw))
    89	    criteria = parsed.get("criteria") or {}
    90	    normalized_criteria = {
    91	        "correct_node_targeted": bool(criteria.get("correct_node_targeted")),
    92	        "correct_parameter_changed": bool(criteria.get("correct_parameter_changed")),
    93	        "value_semantically_matches_intent": bool(criteria.get("value_semantically_matches_intent")),
    94	        "no_orphaned_wiring": bool(criteria.get("no_orphaned_wiring")),
    95	    }
    96	    return {
    97	        "pass_": bool(parsed.get("pass_")),
    98	        "criteria": normalized_criteria,
    99	        "rationale": str(parsed.get("rationale", "")),
   100	    }
   101
   102
   103	def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
   104	    """Parse the grounded-refusal judge's JSON response into a normalized dict."""
   105	    parsed = json.loads(_strip_code_fences(raw))
   106	    criteria = parsed.get("criteria") or {}
   107	    normalized_criteria = {
   108	        "supported_blocker": bool(criteria.get("supported_blocker")),
   109	        "no_representable_edit": bool(criteria.get("no_representable_edit")),
   110	        "specific_next_action": bool(criteria.get("specific_next_action")),
   111	        "no_fabricated_inability": bool(criteria.get("no_fabricated_inability")),
   112	    }
   113	    return {
   114	        "pass_": bool(parsed.get("pass_")),
   115	        "criteria": normalized_criteria,
   116	        "rationale": str(parsed.get("rationale", "")),
   117	    }
   118
   119
   120	def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
   121	    path = output_dir / "implementation_payload.json"
   122	    if not path.is_file():
   123	        return None
   124	    try:
   125	        data = json.loads(path.read_text(encoding="utf-8"))
   126	    except (OSError, json.JSONDecodeError):
   127	        return None
   128	    return data if isinstance(data, dict) else None
   129
   130
   131	def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
   132	    if not isinstance(payload, Mapping):
   133	        return None
   134	    graph = payload.get("graph")
   135	    if not isinstance(graph, Mapping):
   136	        return None
   137	    compiled_api = graph.get("compiled_api")
   138	    if not isinstance(compiled_api, Mapping):
   139	        # Sidecar-less envelope: the execution view is derived by compiling the
   140	        # IR (compile("api") is a function, not stored data). Only a graph the
   141	        # decoder accepts yields context; anything else stays context-free.
   142	        try:
   143	            from vibecomfy.ingest.normalize import convert_to_vibe_format
   144
   145	            compiled_api = convert_to_vibe_format(dict(graph)).compile("api")
   146	        except Exception:
   147	            return None
   148	    context: dict[str, Any] = {"compiled_api": compiled_api}
   149	    metadata = graph.get("metadata")
   150	    if isinstance(metadata, Mapping):
   330	        except (OSError, json.JSONDecodeError):
   331	            pass
   332
   333	    # Fallback to common in-directory locations if response artifacts are absent.
   334	    if original_ui_path is None:
   335	        original_ui_path = output_dir / "original.ui.json"
   336	    if candidate_ui_path is None:
   337	        candidate_ui_path = output_dir / "candidate.ui.json"
   338
   339	    if not original_ui_path.is_file() or not candidate_ui_path.is_file():
   340	        return {
   341	            "pass_": None,
   342	            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
   343	        }
   344
   345	    try:
   346	        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
   347	        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
   348	    except (OSError, json.JSONDecodeError) as exc:
   349	        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}
   350
   351	    system_prompt = _load_prompt()
   352	    implementation_payload = _load_implementation_payload(output_dir)
   353	    schema_context = _schema_context_from_payload(implementation_payload) or {}
   354	    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
   355	    if dataflow_context:
   356	        schema_context["dataflow_context"] = dataflow_context
   357	    if schema_context:
   358	        system_prompt = (
   359	            system_prompt.rstrip()
   360	            + "\n\n## Schema and widget evidence\n"
   361	            "When schema_context is provided, use it to map opaque widget_N fields "
   362	            "to semantic input names. Treat literal widget values as static node "
   363	            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
   364	            "widget's meaning from index order when compiled_api names are available. "
   365	            "If a static widget containing stale or fabricated text is removed while "
   366	            "the relevant linked dynamic input path remains connected, do not treat "
   367	            "that removal as deleting the dynamic dataflow."
   368	        )
   369	    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
   370	    # present, it grounds the judge on what a GOOD result achieves (the outcome +
   371	    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
   372	    # alternative approaches that reach the same outcome count as correct.
   373	    desired = scenario.get("desired")
   374	    if desired:
   375	        system_prompt = (
   376	            system_prompt.rstrip()
   377	            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
   378	            "The scenario author described what a GOOD result looks like below. Use it to "
   379	            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
   380	            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
   381	            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
   382	            "it fully wired/complete (no dangling or broken connections, existing pipeline "
   383	            "not broken), and is the approach a sensible one?\n\n"
   384	            f"Desired outcome: {desired.get('outcome', '')}\n"
   385	            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
   386	            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
   387	        )
   388	    payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
   389	    if desired:
   390	        payload["desired_outcome"] = desired
   391	    if schema_context:
   392	        payload["schema_context"] = schema_context
   393	    user_content = json.dumps(payload, indent=2)
   394
   395	    try:
   396	        response = run_model_turn(
   397	            "evaluate workflow edit against intent",
   398	            messages=[
   399	                {"role": "system", "content": system_prompt},
   400	                {"role": "user", "content": user_content},
   401	            ],
   402	            route=route,
   403	            model=model,
   404	            response_contract="json",
   405	        )
   406	    except Exception as exc:  # noqa: BLE001
   407	        return {"pass_": None, "error": f"model call failed: {exc}"}
   408
   409	    raw = response.get("content") or ""
   410	    if not raw:
   411	        return {"pass_": None, "error": "model returned empty content"}
   412
   413	    try:
   414	        verdict = _parse_verdict(raw)
   415	    except (json.JSONDecodeError, KeyError, TypeError) as exc:
   416	        return {
   417	            "pass_": None,
   418	            "error": f"could not parse judge response: {exc}",
   419	            "raw": raw[:500],
   420	        }
   421
   422	    verdict["metadata"] = {
   423	        "route": route,
   424	        "model": model,
   425	        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
   426	    }
   427	    return verdict
   428
   429
   430	def judge_grounded_refusal(
   431	    output_dir: Path | str,
   432	    scenario: Mapping[str, Any],
   433	    *,
   434	    route: str = "deepseek",
   435	    model: str = "deepseek-v4-pro",
   436	) -> dict[str, Any]:
   437	    """Run the DeepSeek grounded-refusal judge for a desired edit scenario.
   438
   439	    A desired edit may pass on an allowlisted refusal label ONLY when this judge
   440	    confirms the refusal is grounded: the cited blocker is real and supported,
   441	    no representable edit could satisfy the intent, the refusal states a
   442	    specific next action, and it does not fabricate an inability.
   443
   444	    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
   445	    If required artifacts are missing or the model call fails, ``pass_`` is None
   446	    and ``error`` describes why — callers MUST fail closed on that outcome.
   447	    """
   448	    output_dir = Path(output_dir)
   449	    query = str(scenario.get("query", "")).strip()
   450	    if not query:
   451	        return {"pass_": None, "error": "scenario has no query"}
   452
   453	    # The refusal envelope is read from the run's response.json: outcome kind,
   454	    # message, gates, route, evidence.  Only the structured envelope is scored;
   455	    # prose never gates.
   456	    response_path = output_dir / "response.json"
   457	    refusal: dict[str, Any] = {}
   458	    if response_path.is_file():
   459	        try:
   460	            response = json.loads(response_path.read_text(encoding="utf-8"))
   461	        except (OSError, json.JSONDecodeError):
   462	            response = None
   463	        if isinstance(response, Mapping):
   464	            refusal = {
   465	                "outcome": response.get("outcome"),
   466	                "message": response.get("message"),
   467	                "no_candidate_reason": response.get("no_candidate_reason"),
   468	                "route": response.get("route"),
   469	                "gates": response.get("gates"),
   470	                "evidence": response.get("evidence"),
   471	                "graph_unchanged": response.get("graph_unchanged"),
   472	            }
   473	    if not isinstance(refusal.get("outcome"), Mapping):
   474	        return {"pass_": None, "error": "response.json is missing a refusal outcome"}
   475
   476	    system_prompt = _load_refusal_prompt()
   477	    implementation_payload = _load_implementation_payload(output_dir)
   478	    schema_context = _schema_context_from_payload(implementation_payload) or {}
   479	    if schema_context:
   480	        system_prompt = (
   481	            system_prompt.rstrip()
   482	            + "\n\n## Schema evidence\n"
   483	            "When schema_context is provided, use it to verify whether a cited "
   484	            "blocker is real. A 'requires_custom_nodes' refusal is fabricated if "
   485	            "the needed node class actually exists in compiled_api. Do not guess "
   486	            "from node names when compiled_api is available."
   487	        )
   488	    desired = scenario.get("desired")
   489	    payload: dict[str, Any] = {"nl_intent": query, "refusal": refusal}
   490	    if desired:
   491	        payload["desired_outcome"] = desired
   492	    if schema_context:
   493	        payload["schema_context"] = schema_context
   494	    user_content = json.dumps(payload, indent=2)
   495
   496	    try:
   497	        response = run_model_turn(
   498	            "evaluate whether a workflow-edit refusal is grounded",
   499	            messages=[
   500	                {"role": "system", "content": system_prompt},
   501	                {"role": "user", "content": user_content},
   502	            ],
   503	            route=route,
   504	            model=model,
   505	            response_contract="json",
   506	        )
   507	    except Exception as exc:  # noqa: BLE001
   508	        return {"pass_": None, "error": f"model call failed: {exc}"}
   509
   510	    raw = response.get("content") or ""
   511	    if not raw:
   512	        return {"pass_": None, "error": "model returned empty content"}
   513
   514	    try:
   515	        verdict = _parse_refusal_verdict(raw)
   516	    except (json.JSONDecodeError, KeyError, TypeError) as exc:
   517	        return {
   518	            "pass_": None,
   519	            "error": f"could not parse judge response: {exc}",
   520	            "raw": raw[:500],
   521	        }
   522
   523	    verdict["metadata"] = {
   524	        "route": route,
   525	        "model": model,
   526	        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
   527	    }
   528	    return verdict

exec
/bin/zsh -lc 'git log --oneline --decorate --reverse 0f015101..5aa73c53' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
b39f0c91 megado D13: authoritative 100-scenario manifest (SHA-256), manifest-driven runner discovery, 3 mislabeled edits corrected, 35 semantic rubrics, 2 health controls, REVISIONS.md — 71 focused tests green
5aa73c53 (HEAD -> oracle-run) megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green

exec
/bin/zsh -lc "nl -ba tests/test_live_agentic_harness_guard_contract.py | sed -n '380,640p'; nl -ba tests/test_live_agentic_harness_corpus_manifest.py | sed -n '85,220p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   380	        "id": "edit-or-refuse",
   381	        "assessment": {
   382	            "expect_graph_changed": True,
   383	            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
   384	        },
   385	    }
   386	    verdict = guard_output_dir(output_dir, scenario=scenario)
   387
   388	    assert verdict["live_agentic_success"] is True
   389	    assessment = verdict["assessment"]
   390	    assert assessment["passed"] is True
   391	    assert assessment["expect_graph_changed"] is True
   392	    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
   393	    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}
   394
   395
   396	def test_desired_edit_rejects_safe_refusal_when_grounded_judge_unavailable(
   397	    tmp_path: Path,
   398	    monkeypatch,
   399	) -> None:  # noqa: ANN001
   400	    """D13 finding 5, fail-closed: a desired edit may not pass on an
   401	    allowlisted refusal label when the grounded-refusal judge cannot run."""
   402	    output_dir = tmp_path / "desired-refusal-judge-unavailable"
   403	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   404	    _write_safe_refusal_response(output_dir)
   405	    (output_dir / "implementation_result.json").write_text(
   406	        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
   407	    )
   408	    monkeypatch.setattr(
   409	        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
   410	        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
   411	    )
   412
   413	    verdict = guard_output_dir(
   414	        output_dir,
   415	        scenario=_desired_edit_scenario("desired-refusal-judge-unavailable"),
   416	    )
   417
   418	    assert verdict["live_agentic_success"] is False
   419	    assert any(
   420	        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
   421	        for issue in verdict["assessment"]["issues"]
   422	    )
   423
   424
   425	def test_desired_edit_rejects_fabricated_safe_refusal(
   426	    tmp_path: Path,
   427	    monkeypatch,
   428	) -> None:  # noqa: ANN001
   429	    """D13 finding 5: a fabricated/unsupported requires_custom_nodes refusal
   430	    (judge: not grounded) must fail a desired edit."""
   431	    output_dir = tmp_path / "desired-refusal-fabricated"
   432	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   433	    _write_safe_refusal_response(output_dir)
   434	    (output_dir / "implementation_result.json").write_text(
   435	        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
   436	    )
   437	    monkeypatch.setattr(
   438	        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
   439	        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=False),
   440	    )
   441
   442	    verdict = guard_output_dir(
   443	        output_dir,
   444	        scenario=_desired_edit_scenario("desired-refusal-fabricated"),
   445	    )
   446
   447	    assert verdict["live_agentic_success"] is False
   448	    assert any(
   449	        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
   450	        for issue in verdict["assessment"]["issues"]
   451	    )
   452
   453
   454	def test_desired_edit_accepts_grounded_safe_refusal(
   455	    tmp_path: Path,
   456	    monkeypatch,
   457	) -> None:  # noqa: ANN001
   458	    """D13 finding 5, positive control: a genuine grounded refusal (judge:
   459	    grounded) may still pass a desired edit."""
   460	    output_dir = tmp_path / "desired-refusal-grounded"
   461	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   462	    _write_safe_refusal_response(output_dir)
   463	    (output_dir / "implementation_result.json").write_text(
   464	        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
   465	    )
   466	    monkeypatch.setattr(
   467	        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
   468	        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
   469	    )
   470
   471	    verdict = guard_output_dir(
   472	        output_dir,
   473	        scenario=_desired_edit_scenario("desired-refusal-grounded"),
   474	    )
   475
   476	    assert verdict["live_agentic_success"] is True
   477	    assessment = verdict["assessment"]
   478	    assert assessment["passed"] is True
   479	    assert any(
   480	        issue["check"] == "grounded_refusal" and issue["severity"] == "info"
   481	        for issue in assessment["issues"]
   482	    )
   483
   484
   485	def test_desired_edit_refusal_label_with_graph_change_fails_closed_without_verdict(
   486	    tmp_path: Path,
   487	    monkeypatch,
   488	) -> None:  # noqa: ANN001
   489	    """D13 finding 5: graph_unchanged=false plus a refusal label is never a
   490	    safe refusal; without any grounded judge verdict a desired edit fails
   491	    closed (structural guards + fail-closed intent judge)."""
   492	    output_dir = tmp_path / "desired-refusal-graph-changed"
   493	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   494	    _write_safe_refusal_response(output_dir, graph_unchanged=False)
   495	    (output_dir / "implementation_result.json").write_text(
   496	        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
   497	    )
   498	    monkeypatch.setattr(
   499	        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
   500	        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
   501	    )
   502	    monkeypatch.setattr(
   503	        "tests.live_agentic_harness.assessor.judge_edit_intent",
   504	        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
   505	    )
   506
   507	    verdict = guard_output_dir(
   508	        output_dir,
   509	        scenario=_desired_edit_scenario("desired-refusal-graph-changed"),
   510	    )
   511
   512	    assert verdict["live_agentic_success"] is False
   513	    error_checks = {
   514	        issue["check"]
   515	        for issue in verdict["assessment"]["issues"]
   516	        if issue["severity"] == "error"
   517	    }
   518	    assert "intent_judge" in error_checks, verdict["assessment"]["issues"]
   519	    assert {"outcome_kind", "landed_operation_count", "gates"} <= error_checks
   520
   521
   522	def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_path: Path) -> None:
   523	    output_dir = tmp_path / "edit-or-refuse-noop"
   524	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   525	    (output_dir / "response.json").write_text(
   526	        json.dumps(
   527	            {
   528	                "ok": True,
   529	                "graph_unchanged": True,
   530	                "no_candidate_reason": "no_changes",
   531	                "outcome": {"kind": "noop"},
   532	                "message": "No changes.",
   533	            }
   534	        ),
   535	        encoding="utf-8",
   536	    )
   537
   538	    scenario = {
   539	        "id": "edit-or-refuse-noop",
   540	        "assessment": {
   541	            "expect_graph_changed": True,
   542	            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
   543	        },
   544	    }
   545	    verdict = guard_output_dir(output_dir, scenario=scenario)
   546
   547	    assert verdict["live_agentic_success"] is False
   548	    checks = {issue["check"] for issue in verdict["assessment"]["issues"] if issue["severity"] == "error"}
   549	    assert "graph_changed" in checks
   550	    assert "no_candidate_reason" in checks
   551
   552
   553	@pytest.mark.parametrize("scenario_id", _CORRECTED_D13_EDIT_IDS)
   554	def test_corrected_d13_edits_cannot_pass_as_noops(
   555	    tmp_path: Path,
   556	    scenario_id: str,
   557	) -> None:
   558	    output_dir = tmp_path / scenario_id
   559	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   560	    (output_dir / "response.json").write_text(
   561	        json.dumps(
   562	            {
   563	                "ok": True,
   564	                "graph_unchanged": True,
   565	                "no_candidate_reason": "no_changes",
   566	                "outcome": {"kind": "noop"},
   567	                "message": "No changes.",
   568	            }
   569	        ),
   570	        encoding="utf-8",
   571	    )
   572	    scenario_path = (
   573	        Path(__file__).parent
   574	        / "live_agentic_harness"
   575	        / "scenarios"
   576	        / f"{scenario_id}.json"
   577	    )
   578	    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
   579
   580	    verdict = guard_output_dir(output_dir, scenario=scenario)
   581
   582	    assert verdict["live_agentic_success"] is False
   583	    checks = {
   584	        issue["check"]
   585	        for issue in verdict["assessment"]["issues"]
   586	        if issue["severity"] == "error"
   587	    }
   588	    assert "graph_changed" in checks
   589	    assert "no_candidate_reason" in checks
   590	    assert "outcome_kind" in checks
   591
   592
   593	def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
   594	    tmp_path: Path,
   595	    monkeypatch,
   596	) -> None:  # noqa: ANN001
   597	    output_dir = tmp_path / "desired-judge-unavailable"
   598	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   599	    _write_successful_candidate(output_dir)
   600	    (output_dir / "implementation_result.json").write_text(
   601	        json.dumps({"status": "success"}), encoding="utf-8"
   602	    )
   603	    monkeypatch.setattr(
   604	        "tests.live_agentic_harness.assessor.judge_edit_intent",
   605	        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
   606	    )
   607
   608	    verdict = guard_output_dir(
   609	        output_dir,
   610	        scenario={
   611	            "id": "desired-judge-unavailable",
   612	            "query": "set seed to 42",
   613	            "assessment": {"expect_graph_changed": True},
   614	            "desired": {
   615	                "outcome": "seed is 42",
   616	                "quality": "only the intended seed changes",
   617	                "alternatives_ok": False,
   618	            },
   619	        },
   620	    )
   621
   622	    assert verdict["live_agentic_success"] is False
   623	    assert any(
   624	        issue["check"] == "intent_judge" and issue["severity"] == "error"
   625	        for issue in verdict["assessment"]["issues"]
   626	    )
   627
   628
   629	def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
   630	    output_dir = tmp_path / "oversized-model-request"
   631	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   632	    (output_dir / "response.json").write_text(
   633	        json.dumps(
   634	            {
   635	                "ok": True,
   636	                "graph_unchanged": False,
   637	                "outcome": {"kind": "candidate"},
   638	                "candidate": {"nodes": [{"id": 1}]},
   639	                "change_details": {"landed_operation_count": 1},
   640	            }
    85	        assert assessment.get("skip_intent_judge") is not True, (
    86	            f"{scenario['id']}: skip_intent_judge would let a refusal skip the judge"
    87	        )
    88
    89
    90	def test_runner_rejects_unmanifested_descriptor_before_execution(tmp_path: Path) -> None:
    91	    scenarios_dir = tmp_path / "scenarios"
    92	    scenarios_dir.mkdir()
    93	    (scenarios_dir / "one.json").write_text(
    94	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
    95	    )
    96	    write_manifest(scenarios_dir)
    97	    (scenarios_dir / "stray.json").write_text(
    98	        json.dumps({"id": "stray", "query": "stray"}), encoding="utf-8"
    99	    )
   100	    with pytest.raises(ScenarioManifestError, match="unmanifested"):
   101	        run_tag("stray-preflight", scenarios_dir=scenarios_dir, output_base=tmp_path / "out")
   102
   103
   104	def test_manifest_discovery_rejects_changed_or_missing_descriptor(tmp_path: Path) -> None:
   105	    scenarios_dir = tmp_path / "scenarios"
   106	    scenarios_dir.mkdir()
   107	    descriptor = scenarios_dir / "one.json"
   108	    descriptor.write_text(json.dumps({"id": "one", "query": "one"}), encoding="utf-8")
   109	    write_manifest(scenarios_dir)
   110	    descriptor.write_text(json.dumps({"id": "one", "query": "changed"}), encoding="utf-8")
   111	    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
   112	        discover_manifest_scenarios(scenarios_dir)
   113
   114	    descriptor.unlink()
   115	    with pytest.raises(ScenarioManifestError, match="missing"):
   116	        discover_manifest_scenarios(scenarios_dir)
   117
   118
   119	def test_manifest_discovery_rejects_duplicate_id_and_path(tmp_path: Path) -> None:
   120	    scenarios_dir = tmp_path / "scenarios"
   121	    scenarios_dir.mkdir()
   122	    (scenarios_dir / "one.json").write_text(
   123	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
   124	    )
   125	    manifest_path = write_manifest(scenarios_dir)
   126	    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   127	    manifest["entries"].append(dict(manifest["entries"][0]))
   128	    manifest["scenario_count"] = 2
   129	    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
   130	    with pytest.raises(ScenarioManifestError, match="duplicate scenario id"):
   131	        discover_manifest_scenarios(scenarios_dir)
   132
   133
   134	def test_manifest_discovery_rejects_duplicate_path_with_distinct_id(tmp_path: Path) -> None:
   135	    scenarios_dir = tmp_path / "scenarios"
   136	    scenarios_dir.mkdir()
   137	    (scenarios_dir / "one.json").write_text(
   138	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
   139	    )
   140	    manifest_path = write_manifest(scenarios_dir)
   141	    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   142	    duplicate = dict(manifest["entries"][0])
   143	    duplicate["id"] = "two"
   144	    manifest["entries"].append(duplicate)
   145	    manifest["scenario_count"] = 2
   146	    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
   147	    with pytest.raises(ScenarioManifestError, match="duplicate scenario path"):
   148	        discover_manifest_scenarios(scenarios_dir)

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '600,930p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 5ms:
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
   812	        # A DESIRED edit must never pass on an allowlisted refusal label
   813	        # without an active grounded-refusal judge: the judge runs and must
   814	        # confirm the refusal is grounded (supported blocker, no representable
   815	        # edit, specific next action, no fabricated inability), and it FAILS
   816	        # CLOSED when the judge is unavailable.  graph_unchanged=false plus a
   817	        # refusal label is never a safe refusal (safe_refusal_accepted requires
   818	        # graph_unchanged=true), so it is still scored by the structural guards
   819	        # and — for desired scenarios — fails closed without a judge verdict.
   820	        # Non-desired edit-or-refuse scenarios keep the historical bypass.
   821	        if (
   822	            expect_graph_changed
   823	            and not scenario.get("assessment", {}).get("skip_intent_judge")
   824	        ):
   825	            if safe_refusal_accepted and scenario.get("desired"):
   826	                verdict = judge_grounded_refusal(output_dir, scenario)
   827	                if verdict.get("pass_") is False:
   828	                    issues.append(
   829	                        {
   830	                            "check": "grounded_refusal",
   831	                            "severity": "error",
   832	                            "detail": (
   833	                                f"Refusal not grounded: {verdict.get('rationale', 'no rationale')} "
   834	                                f"criteria={verdict.get('criteria')}"
   835	                            ),
   836	                        }
   837	                    )
   838	                elif verdict.get("pass_") is True:
   839	                    issues.append(
   840	                        {
   841	                            "check": "grounded_refusal",
   842	                            "severity": "info",
   843	                            "detail": (
   844	                                f"Grounded refusal confirmed: {verdict.get('rationale', 'no rationale')} "
   845	                                f"criteria={verdict.get('criteria')}"
   846	                            ),
   847	                        }
   848	                    )
   849	                else:
   850	                    issues.append(
   851	                        {
   852	                            "check": "grounded_refusal",
   853	                            # A desired block is an active acceptance rubric;
   854	                            # an absent grounded-refusal judge fails closed.
   855	                            "severity": "error",
   856	                            "detail": (
   857	                                "Grounded-refusal judge could not run: "
   858	                                f"{verdict.get('error')}"
   859	                            ),
   860	                        }
   861	                    )
   862	            elif not safe_refusal_accepted:
   863	                verdict = judge_edit_intent(output_dir, scenario)
   864	                if verdict.get("pass_") is False:
   865	                    issues.append(
   866	                        {
   867	                            "check": "intent_judge",
   868	                            "severity": "error",
   869	                            "detail": (
   870	                                f"LLM intent judge failed: {verdict.get('rationale', 'no rationale')} "
   871	                                f"criteria={verdict.get('criteria')}"
   872	                            ),
   873	                        }
   874	                    )
   875	                elif verdict.get("pass_") is True:
   876	                    issues.append(
   877	                        {
   878	                            "check": "intent_judge",
   879	                            "severity": "info",
   880	                            "detail": (
   881	                                f"LLM intent judge passed: {verdict.get('rationale', 'no rationale')} "
   882	                                f"criteria={verdict.get('criteria')}"
   883	                            ),
   884	                        }
   885	                    )
   886	                else:
   887	                    issues.append(
   888	                        {
   889	                            "check": "intent_judge",
   890	                            # A desired block is an active acceptance rubric, not
   891	                            # optional context. Fail closed if its judge is absent.
   892	                            "severity": "error" if scenario.get("desired") else "warning",
   893	                            "detail": f"LLM intent judge could not run: {verdict.get('error')}",
   894	                        }
   895	                    )
   896
   897	        # Any hard diagnostic anywhere in the response envelope.
   898	        for msg in _collect_hard_diagnostics(response):
   899	            issues.append(
   900	                {
   901	                    "check": "hard_diagnostic",
   902	                    "severity": "error",
   903	                    "detail": msg,
   904	                }
   905	            )
   906
   907	        # G0-T2: the deterministic message-artifact prose matcher is removed.
   908	        # Scoring is structured-only — prose never gates a scenario. The
   909	        # agent's message always ships as written; the structured
   910	        # cross-checks (graph_changed, outcome_kind, gates, landed counts,
   911	        # effective edits) above remain fully authoritative.
   912
   913	        # Critical upstream failures (Hivemind 500, etc.). When a successful
   914	        # candidate exists, a recovered research-side upstream error should stay
   915	        # visible but not invalidate an otherwise valid edit.
   916	        upstream_severity = "warning" if _has_successful_candidate(response) else "error"
   917	        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
   918	            issues.append(
   919	                {
   920	                    "check": "upstream_failure",
   921	                    "severity": upstream_severity,
   922	                    "detail": msg,
   923	                }
   924	            )
   925
   926	        # Capacity/soft warnings: surfaced, but not counted as errors.
   927	        for msg in _collect_pattern_matches(response, _SOFT_WARNING_PATTERNS):
   928	            issues.append(
   929	                {
   930	                    "check": "soft_warning",

codex
The manifest’s core rejection path is present and directly tested. I’ve also confirmed the three corrected descriptors now demand real edits. Next I’m checking the harder semantic claims: whether all 35 rubrics are genuinely workflow-grounded, whether all retained `desired` scenarios are judge-active, and whether every manifest/source hash resolves—not merely whether schema-shape tests pass.
exec
/bin/zsh -lc 'python -c $'"'import json,hashlib,pathlib,collections\\nroot=pathlib.Path(\".\").resolve()\\nm=json.loads((root/\"tests/live_agentic_harness/scenario_manifest.json\").read_text())\\nsc=[];bad_desc=[];bad_src=[];missing=[]\\nfor e in m[\"entries\"]:\\n p=root/e[\"path\"];s=json.loads(p.read_text());sc.append((e,s,p));h=hashlib.sha256(p.read_bytes()).hexdigest()\\n if h"'!=e["descriptor_sha256"]:bad_desc.append((e["id"],h,e["descriptor_sha256"]))'"\\n src=e.get(\"source_workflow\")\\n if src:\\n  sp=root/src[\"path\"]\\n  if not sp.is_file():missing.append((e[\"id\"],str(sp)))\\n  else:\\n   sh=hashlib.sha256(sp.read_bytes()).hexdigest()\\n   if sh"'!=src["sha256"]:bad_src.append((e["id"],sh,src["sha256"]))'"\\nprint(\"manifest_count\",m[\"scenario_count\"],\"entries\",len(m[\"entries\"]))\\nprint(\"unique_ids\",len({e[\"id\"] for e in m[\"entries\"]}),\"unique_paths\",len({e[\"path\"] for e in m[\"entries\"]}),\"stem_matches\",sum(e[\"id\"]==pathlib.Path(e[\"path\"]).stem for e in m[\"entries\"]))\\nprint(\"statuses\",collections.Counter(e[\"inclusion_status\"] for e in m[\"entries\"]))\\nprint(\"revisions\",collections.Counter(e[\"revision_status\"] for e in m[\"entries\"]))\\nprint(\"manifest_kinds\",collections.Counter(e[\"scenario_kind\"] for e in m[\"entries\"]))\\nprint(\"classifications\",collections.Counter((s.get(\"classification\") or {}).get(\"kind\",\"<none>\") for _,s,_ in sc))\\nprint(\"query_types\",collections.Counter((s.get(\"_tags\") or {}).get(\"query_type\") for _,s,_ in sc))\\nprint(\"desired_count\",sum(bool(s.get(\"desired\")) for _,s,_ in sc))\\nprint(\"desired_skips\",[(e[\"id\"],s.get(\"assessment\")) for e,s,_ in sc if s.get(\"desired\") and (s.get(\"assessment\") or {}).get(\"skip_intent_judge\") is True])\\nprint(\"desired_not_expect_change\",[(e[\"id\"],s.get(\"assessment\")) for e,s,_ in sc if s.get(\"desired\") and (s.get(\"assessment\") or {}).get(\"expect_graph_changed\") is not True])\\nprint(\"descriptor_hash_mismatches\",len(bad_desc),bad_desc[:3])\\nprint(\"source_missing\",len(missing),missing[:3])\\nprint(\"source_hash_mismatches\",len(bad_src),bad_src[:3])\\nprint(\"source_count\",sum(bool(e.get(\"source_workflow\")) for e in m[\"entries\"]))\\nprint(\"scenario_files\",len(list((root/\"tests/live_agentic_harness/scenarios\").glob(\"*.json\"))))\\nprint(\"corpus_jsons\",len(list((root/\"external_workflows\").rglob(\"*.json\"))),\"symlink\",(root/\"external_workflows\").is_symlink(),\"target\",(root/\"external_workflows\").resolve())\\nprint(\"revised_ids\",[e[\"id\"] for e in m[\"entries\"] if e[\"revision_status\"]==\"revised\"])'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 1666ms:
manifest_count 100 entries 100
unique_ids 100 unique_paths 100 stem_matches 100
statuses Counter({'included': 100})
revisions Counter({'matched': 97, 'revised': 3})
manifest_kinds Counter({'edit': 63, 'semantic_product': 35, 'health_control': 2})
classifications Counter({'<none>': 60, 'semantic_product': 35, 'edit': 3, 'health_control': 2})
query_types Counter({'edit': 26, None: 23, 'big_adjustment': 16, 'research': 12, 'diagnose': 12, 'explain': 11})
desired_count 42
desired_skips []
desired_not_expect_change []
descriptor_hash_mismatches 0 []
source_missing 0 []
source_hash_mismatches 0 []
source_count 98
scenario_files 100
corpus_jsons 9251 symlink True target /Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows
revised_ids ['multi-3d-preview-and-image-output-workflow-d93baf', 'video-image-to-video-conversion-with-moonvalley-d7853c', 'video-video-inpainting-with-spline-based-cut-and-dra-485ff2']

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\"tests/live_agentic_harness/scenarios\")\\nfor p in sorted(root.glob(\"*.json\")):\\n s=json.loads(p.read_text())\\n if (s.get(\"classification\") or {}).get(\"kind\")==\"semantic_product\":\\n  r=s[\"answer_rubric\"]\\n  print(\"ID\",s[\"id\"]);print(\"Q\",s[\"query\"]);print(\"EVID\",json.dumps(r.get(\"required_node_evidence\"),sort_keys=True));print(\"CRIT\",json.dumps(r.get(\"expected_criteria\"),sort_keys=True));print(\"PASS\",r.get(\"pass_condition\"));print(\"FAIL\",json.dumps(r.get(\"fail_conditions\")));print()'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 864ms:
ID audio-acestep-audio-generation-with-detail-daemon-f0859f
Q The DetailDaemon sampler is used for enhancing audio detail. How does it work compared to standard audio diffusion samplers, and what settings would you recommend for generating a cinematic soundscape?
EVID ["DetailDaemonSamplerNode", "KSampler", "SamplerCustom", "BasicScheduler"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Explain how DetailDaemon changes the sampling/detail path versus the standard KSampler path, and give cinematic-soundscape settings with trade-offs rather than unsupported magic values.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-animatediff-image-to-video-with-latent-composi-17dc9b
Q How does the latent compositing approach here compare to using an init image directly in the video latent space? Which gives better temporal coherence?
EVID ["LatentComposite", "VAEEncode", "EmptyLatentImage", "AnimateDiffLoaderV1", "KSampler"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Compare the graph's encoded-image LatentComposite path with direct init-image conditioning, including where each anchors structure and the likely temporal-coherence trade-off.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-dual-checkpoint-xl-image-generation-with-refin-c9df19
Q I'm running this dual-checkpoint XL pipeline with juggernautXL as the base and sd_xl_refiner as the refiner. Are there any newer, better refiner models I should consider, and what are the tradeoffs between using a dedicated refiner vs. a single high-quality XL checkpoint that handles fine details natively? I'm particularly interested in how the LoRA timing (before or after the refiner) affects flexibility.
EVID ["CheckpointLoaderSimple", "KSamplerAdvanced", "Power Lora Loader (rgthree)", "VAEDecode"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Describe the base/refiner handoff visible in the two-checkpoint/two-sampler graph, compare current refiner or single-checkpoint options, and address whether LoRA is applied before or after the handoff.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-gemini-prompt-splitter-and-text-display-workfl-caae97
Q This workflow uses Gemini to process and split prompts. I'd like to compare Gemini to Claude for generating complex, multi-part image prompts. What are the trade-offs in terms of output quality, prompt structure, rate limits, and cost? Just research, don't modify the workflow.
EVID ["GeminiNode", "VRGDG_PromptSplitter_General", "StringConcatenate", "ShowText|pysssss"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Compare Gemini and Claude for this multi-part prompt-generation role across output structure/quality, rate limits, and cost, while clearly separating graph facts from time-sensitive provider facts.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-image-processing-with-sharpening-film-grain-an-9aa0f1
Q What alternative sharpening methods could replace the high pass filter in this workflow, and what are the tradeoffs in terms of edge halos vs. natural detail enhancement?
EVID ["Image High Pass Filter", "VividSharpenV2", "Image Filter Adjustments", "ImageBlend", "BetterFilmGrain"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Name viable replacements for the current high-pass branch and compare halo risk, local contrast, noise amplification, masking, and blend-strength control in this graph.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-image-to-image-with-ipadapter-and-controlnet-1999a9
Q How can I balance the influence between the IPAdapter style reference and the Canny edge ControlNet strength to preserve more of the original image structure while still applying the desired style? What parameters control this interplay?
EVID ["IPAdapterApply", "Canny", "ControlNetApply", "ControlNetLoader", "KSampler"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Identify the concrete IPAdapter and Canny/ControlNet influence controls, explain their interaction, and recommend a tuning order that preserves structure without eliminating style transfer.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-llava-image-captioning-and-keyword-extraction-d38dc8
Q What alternative image captioning models could I replace LLaVA with to produce longer, more detailed prompts? Are there any that also extract keywords directly, or should I keep separate steps?
EVID ["LLavaPromptGenerator", "LLavaSamplerSimple", "KeywordExtraction", "JsonToText", "Suggester"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Compare named captioning alternatives for longer detailed prompts and decide, with trade-offs, whether keyword extraction can be combined or should remain the graph's separate step.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID image-qwen-image-inpainting-with-controlnet-09fc64
Q For this Qwen Image inpainting workflow, I frequently get color mismatches between the inpainted area and the original image. Before editing anything, research the best techniques to improve color consistency specifically for ControlNet-based inpainting with Qwen-Image-Lightning. Also explore if there's a better method for mask feathering or blending that could reduce the mismatch.
EVID ["ControlNetInpaintingAliMamaApply", "ImagePadForOutpaint", "VAEEncode", "KSampler", "VAEDecode"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Recommend Qwen-Image-Lightning/ControlNet color-consistency and mask-edge techniques that map to this encode/control/sample/decode pipeline, including feathering or compositing checks and relevant trade-offs.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-3d-gaussian-splatting-from-video-with-hunyuan-432652
Q The 3D reconstruction has noticeable geometry flickering across frames, likely from inconsistent depth maps. Can you investigate this video-to-3D Gaussian Splatting pipeline and suggest alternative depth estimation approaches or stabilization techniques that could reduce temporal jitter in the output point cloud?
EVID ["PreprocessImagesForHWM", "HWMInference", "VisualizeDepth", "Save3DGaussians", "SavePointCloud"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Tie temporal geometry jitter to the workflow's preprocessing/depth-inference path and compare concrete temporally stable depth, camera, filtering, or point-cloud stabilization strategies.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-ai-video-upscaling-with-detail-daemon-sampler-673197
Q I'm using the Detail Daemon Sampler with beta scheduling to upscale a low-res video. The output has strong color shifting compared to the input, and details look smeared rather than enhanced. I've tried different SeedVR2 checkpoints but the issue persists. Where should I look?
EVID ["SeedVR2VideoUpscaler", "DetailDaemonSamplerNode", "BetaSamplingScheduler", "Sigmas Rescale", "VAEDecode"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Prioritize plausible causes of both color shift and smeared detail in the SeedVR2/detail-daemon/sigma/VAE chain, and give discriminating checks before recommending parameter changes.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-animated-image-to-video-with-svd-and-lora-4ed6d9
Q Walk me through the entire pipeline of this workflow from loading the input image to generating the WEBP video. I want to understand why there are two KSampler stages and how the SVD model conditions the generated frames. Also explain how the LoRA augmentation fits in.
EVID ["ImageOnlyCheckpointLoader", "SVD_img2vid_Conditioning", "LoraLoader", "KSampler", "SaveAnimatedWEBP"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace the actual image-to-SVD-conditioning-to-sampling-to-WEBP flow, distinguish the two KSampler stages, and state where the LoRA-modified model enters.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-animatediff-video-generation-with-controlnet-a7e2af
Q My current workflow uses a standard UNet-based Stable Diffusion checkpoint with AnimateDiff. What would be the trade-offs if I switched to a DiT-based model (e.g., SD3 or PixArt) for better motion consistency and temporal coherence? Specifically, how would ControlNet integration differ, and what performance or quality changes should I expect?
EVID ["CheckpointLoaderSimple", "ADE_AnimateDiffLoaderWithContext", "ControlNetLoaderAdvanced", "ControlNetApplyAdvanced", "KSampler"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Compare the current UNet/AnimateDiff/ControlNet integration with a DiT migration, covering model/control compatibility, motion coherence, compute, and likely graph changes without pretending it is a drop-in swap.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-audio-to-image-mel-band-roformer-workflow-b22937
Q Can you explain step-by-step what this audio-to-image workflow does, how the MelBandRoFormer model fits in, and why it both saves an MP3 and outputs a preview image?
EVID ["LoadAudio", "MelBandRoFormerModelLoader", "MelBandRoFormerSampler", "SaveAudioMP3", "PreviewImage"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace the audio through MelBandRoFormer and explain separately why an MP3 is saved and why an image preview is produced, based on the actual output branches.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-flux2-image-and-video-generation-with-outpaint-435de2
Q The outpainted borders look noticeably brighter than the original image, even after color matching is applied. Why is the color matching node not aligning the luminance, and which specific node or setting is likely causing this mismatch?
EVID ["ImagePadForOutpaint", "DrawMaskOnImage", "ReferenceLatent", "VAEDecode", "ColorMatch", "ImageCompare"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Locate ColorMatch relative to generation/decoding/compositing, identify a graph-supported luminance mismatch mechanism, and propose checks that distinguish bad reference/mask/range settings from a broken color-match node.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-svd-image-to-video-with-animation-builder-99e2a9
Q The generated video has severe flickering and jittery motion, with frames occasionally going black. What in the workflow could be causing this?
EVID ["SVD_img2vid_Conditioning", "KSampler", "Animation Builder (mtb)", "Get Batch From History (mtb)", "Export With Ffmpeg (mtb)"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Rank workflow-specific causes for flicker, jitter, and black frames across conditioning, sampling, batch-history selection, animation assembly, and export, with a test that isolates each leading cause.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-svd-image-to-video-with-sdxl-conditioning-389d90
Q Can you explain how each stage of this workflow contributes to generating the final WEBP video, particularly the role of the CLIP text conditioning and how the SVD model uses the input image and text prompt together to determine motion?
EVID ["CheckpointLoaderSimple", "CLIPTextEncode", "ImageOnlyCheckpointLoader", "SVD_img2vid_Conditioning", "KSampler", "SaveAnimatedWEBP"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace every major stage to the WEBP output and accurately distinguish SDXL text conditioning from SVD's image/motion conditioning instead of claiming unsupported direct text control of SVD.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14
Q Explain how the Wan2.2 Lightning model and LoRA adapters work together in this workflow. What is the purpose of having two LoRA strength settings?
EVID ["DiffusionModelLoaderKJ", "LoraLoaderModelOnly", "ModelSamplingSD3", "KSamplerAdvanced", "EmptyHunyuanLatentVideo"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Explain how the Lightning model patch and LoRA loaders feed sampling, and disambiguate the two strength controls by identifying what each applies to in this graph.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6
Q The generated video has a visible, frame‑varying flicker in the film grain overlay, giving it a disjointed look. Which part of the post‑processing stack is introducing this temporal inconsistency?
EVID ["VAEDecode", "FastUnsharpSharpen", "FastFilmGrain", "SaveImage", "Image Comparer (rgthree)"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Identify the frame-varying grain source in the post-process branch, explain why independent/random per-frame grain flickers, and distinguish it from sharpening or model-sampling artifacts.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-animatediff-video-to-video-with-controlnet-and-3c978e
Q I'm trying to understand how this AnimateDiff video-to-video workflow keeps motion coherent across frames. Walk me through the pipeline end-to-end, focusing on where the ControlNets, LoRAs, and KSampler interact to preserve temporal consistency.
EVID ["VHS_LoadVideo", "VAEEncode", "ControlNetLoaderAdvanced", "ControlNetApply", "LoraLoader", "ADE_AnimateDiffLoaderWithContext", "KSampler", "VHS_VideoCombine"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Walk the connected video-to-latent, ControlNet/LoRA/AnimateDiff model-conditioning, KSampler, decode, and combine path and explain which mechanisms preserve spatial versus temporal consistency.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-animatediff-video-with-controlnet-and-depth-89b02a
Q What alternatives to Depth-Anything could I use as the depth estimator for better temporal consistency in my AnimateDiff video pipeline, and how would replacing it affect the ControlNet guidance?
EVID ["DownloadAndLoadDepthAnythingV2Model", "DepthAnything_V2", "ControlNetLoader", "ACN_AdvancedControlNetApply_v2", "ADE_UseEvolvedSampling"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Compare named depth estimators or temporal-depth strategies and explain how their output normalization/stability must match the existing ControlNet guidance path.", "Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-animatediff-video-with-ipadapter-and-controlne-4eebf3
Q The output video has a persistent tiling grid pattern visible in uniform areas like sky or walls, as if the IPAdapter style is being applied in blocks rather than smoothly. Which node and setting is the likely culprit?
EVID ["IPAdapterTiled", "IPAdapterUnifiedLoader", "ImageResize+", "ACN_AdvancedControlNetApply", "SamplerCustom"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Test the tiling hypothesis against IPAdapterTiled and its tile/weight/application settings, explain the grid mechanism, and distinguish it from resize, ControlNet, VAE, or codec artifacts.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-hunyuan-video-text-to-video-generation-265847
Q The generated animated WEBP has severe flickering between frames, especially in high-motion areas, but the first frame looks fine. What in the workflow could be causing this temporal inconsistency?
EVID ["EmptyHunyuanLatentVideo", "BasicScheduler", "SamplerCustomAdvanced", "VAEDecodeTiled", "SaveAnimatedWEBP"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Prioritize causes that can affect later/high-motion frames while sparing the first, grounding the diagnosis in latent length/schedule/sampling/tiled decode/WEBP settings and proposing isolating checks.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-hunyuanvideo-image-to-video-generation-with-en-ff076a
Q The generated video doesn't resemble my input image at all — the first frame is completely different, and the video looks like random noise. I suspect the image encoding or conditioning is broken.
EVID ["LoadImageFromUrl", "ImageResizeKJ", "HyVideoI2VEncode", "HyVideoEncode", "SetLatentNoiseMask", "HyVideoSampler", "HyVideoDecode"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace the image-conditioning and latent/noise-mask path, identify concrete disconnections or incompatible encoding/settings that could discard the first frame, and give ordered verification steps.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-image-to-video-with-svd-and-webp-output-1882aa
Q Walk me through this workflow: how does it turn a static image into a moving video and save it as WebP? I'm especially curious how the Stable Video Diffusion conditioning and linear CFG guidance are set up.
EVID ["LoadImage", "ImageOnlyCheckpointLoader", "SVD_img2vid_Conditioning", "VideoLinearCFGGuidance", "KSampler", "VAEDecode", "SaveAnimatedWEBP"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace the static image through SVD conditioning, CFG-guided sampling, decode, and WebP save, explaining the distinct roles and the motion-related SVD controls.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-inpaint-and-video-composition-with-spline-path-0c2716
Q What role does the spline editor play in this inpainting-and-compositing workflow? Explain how the path controls the inpainting mask over time and how the final video frames are assembled from the processed results.
EVID ["SplineEditor", "CutAndDragOnPath", "INPAINT_LoadInpaintModel", "INPAINT_InpaintWithModel", "VHS_MergeImages", "VHS_VideoCombine"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Explain how spline coordinates drive the moving mask/cut path, how inpainting consumes image and mask, and how merge/combine nodes assemble the final frames without inventing absent tracking stages.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-ltx-video-with-audio-and-inpainting-b3ba8a
Q The inpainted region looks sharp-edged and doesn't blend smoothly with the rest of the video, and the colors in that region are completely off (grayish). What's going wrong?
EVID ["ImageToMask", "GrowMaskWithBlur", "InvertMask", "LatentInpaintTTM", "LTXVImgToVideoInplace", "ImageBlend", "VAEDecodeTiled"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Connect sharp edges to the mask grow/blur/invert route and gray color to latent/encode/decode/blend compatibility, then give checks that separately isolate mask geometry and color-space/latent issues.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-seedvr2-video-upscaling-workflow-052e59
Q Walk me through what each major stage does: how the video frames are loaded, what the VAE and DiT models contribute, and how the final upscaled video is assembled. I want to understand the full pipeline.
EVID ["LoadVideo", "GetVideoComponents", "SeedVR2LoadDiTModel", "SeedVR2LoadVAEModel", "SeedVR2VideoUpscaler", "CreateVideo", "SaveVideo"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace video loading/component extraction through the SeedVR2 DiT and VAE upscaler to video creation/save, accurately separating model restoration from VAE encoding/decoding and container assembly.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-video-loading-and-saving-workflow-1c7ad8
Q This workflow loads a video and an image, applies boolean logic, and saves three separate video outputs. Explain what each boolean operation is doing and how the three resulting videos differ from one another.
EVID ["LoadVideo", "LoadImage", "PrimitiveBoolean", "SaveVideo", "2dc75cab-e957-4437-a5bb-2afb0ea00516", "3ad0b41c-8c47-4e10-a53e-ed340cc26b5f", "b83ac947-e174-4a8e-b0c1-f7c3b8f00419"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Use the three custom-node connections and shared boolean inputs to explain each operation/output distinctly; unknown UUID node semantics must be derived from metadata/connections or stated as uncertain, not guessed.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-video-output-workflow-f855de
Q The final output video is unacceptably blurry and shows heavy banding in dark areas, even though no explicit blur or compression step is visible in the node graph. I need you to inspect the custom nodes and connections to identify what's causing this loss of detail.
EVID ["SaveVideo", "1cef296e-0f57-4f74-9e5e-7fe2b9097bcf", "61c3c7e8-7a92-4f27-8c3f-82eb62976f7b", "94adb7a7-527b-4ea8-92e0-9ab2ca8387c4"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Inspect the opaque custom-node metadata/settings and connections before naming a culprit for blur/banding; distinguish processing/range/bit-depth loss from SaveVideo codec settings and flag any unresolved UUID semantics.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-wan-video-generation-with-vace-and-multi-outpu-d1caec
Q The video output has severe temporal flickering and only the first image in my batch produces a coherent result — the rest are pure noise. What's causing this?
EVID ["ImageBatch", "ImageBatchMulti", "GetImageRangeFromBatch", "ReverseImageBatch", "WanVaceToVideo", "TrimVideoLatent", "KSamplerAdvanced"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Explain why only the first batch item might be coherent by tracing batch slicing/order into VACE conditioning and latent length/masks, and separate that from global sampling causes of temporal flicker.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9
Q The high-noise LoRA variant produces outputs that look identical to the low-noise variant — no difference in motion or texture. Also, the video appears to have incorrect brightness/contrast, as if the latent scaling is off.
EVID ["UnetLoaderGGUF", "LoraLoaderModelOnly", "KSamplerAdvanced", "Frames Concat Latent", "LatentLoaderAdvanced", "SetLatentNoiseMask", "VAEDecode"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Verify whether the high/low LoRA branches actually reach distinct model/sampling paths and diagnose brightness through latent concat/load/noise-mask/decode scaling, with tests for bypassed or identical inputs.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3
Q Explain how this workflow uses the high and low noise variants of Wan2.2 differently. I'm confused about why there are two separate generation paths and how their outputs are combined or selected.
EVID ["UNETLoader", "ModelSamplingSD3", "KSamplerAdvanced", "EmptyHunyuanLatentVideo", "VAEDecode", "SaveAnimatedWEBP", "SaveWEBM"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Describe the two loaded model/sampling paths from high-noise to low-noise stages and state whether the graph chains, combines, or merely exposes alternatives, based on actual edges rather than the title.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a
Q Can you explain the dual-UNet staging in this Wan2.2 pipeline? Specifically, how do the high-noise and low-noise models divide the sampling work, and where does the LoRA get applied to improve output quality?
EVID ["UNETLoader", "LoraLoaderModelOnly", "ModelSamplingSD3", "KSamplerAdvanced", "CreateVideo", "SaveVideo"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Explain the sigma/noise-range handoff between the two UNet sampler stages and identify exactly where each LoRA-modified model is applied before decode/output.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9
Q The animation looks great for the first 16 frames, but then the motion becomes erratic and the subject’s appearance shifts noticeably. What could be causing this degradation?
EVID ["UNETLoader", "LoraLoader", "SwarmKSampler", "SwarmTrimFrames", "LatentUpscaleBy", "SwarmSaveAnimationWS"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Tie degradation after frame 16 to explicit frame-window/trim/upscale or staged-sampling settings where supported, and give checks that distinguish context-boundary drift from LoRA/model or save artifacts.", "Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

ID video-wanvideo-text-to-video-generation-71f825
Q How does the WanVideo text-to-video pipeline turn a prompt into a video clip? Walk me through the flow from the T5 and CLIP encoders through sampling to the final output, and explain how the model learns to generate motion across frames.
EVID ["LoadWanVideoT5TextEncoder", "LoadWanVideoClipTextEncoder", "WanVideoTextEncode", "WanVideoModelLoader", "WanVideoSampler", "WanVideoDecode", "VHS_VideoCombine"]
CRIT ["Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone.", "Trace T5 and CLIP inputs through WanVideo text encoding, model sampling, VAE decode, and combine, accurately explaining conditioning and latent temporal generation without claiming the encoders themselves generate motion.", "Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names.", "Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification."]
PASS Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]


exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\".\")\\nfor sid in [\"485ff2fa6dcc1917\",\"d7853cd7421f9ebc\",\"d93baf73c8a43f57\"]:\\n p=root/\"external_workflows/corpus\"/(sid+\".json\");w=json.loads(p.read_text());print(\"WORKFLOW\",sid,\"keys\",list(w)[:12])\\n nodes=w.get(\"nodes\") or []\\n for n in nodes:\\n  blob=json.dumps(n,ensure_ascii=False)\\n  if any(x in blob for x in [\"INPAINT_InpaintWithModel\",\"Moonvalley\",\"SaveGLB\",\"534667941392889\",\"3d/ComfyUI\"]):print(json.dumps(n,ensure_ascii=False,indent=2))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\".\")\\nmp=json.loads((root/\"tests/live_agentic_harness/scenario_manifest.json\").read_text())\\nbad=[]\\nfor e in mp[\"entries\"]:\\n p=root/e[\"path\"];s=json.loads(p.read_text())\\n if (s.get(\"classification\") or {}).get(\"kind\")"'!="semantic_product":continue'"\\n wf=json.loads((root/e[\"source_workflow\"][\"path\"]).read_text());blob=json.dumps(wf,ensure_ascii=False)\\n for ev in s[\"answer_rubric\"][\"required_node_evidence\"]:\\n  if str(ev) not in blob:bad.append((e[\"id\"],ev))\\nprint(\"required_evidence_missing_from_source_blob\",len(bad));print(*bad,sep=\"\\\\n\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
exec
/bin/zsh -lc 'for f in tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json tests/live_agentic_harness/scenarios/speed-distillation-research.json; do echo "FILE $f"; nl -ba "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
FILE tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json
     1	{
     2	  "id": "live-graph-explanation-smoke",
     3	  "brief": "briefs/live-graph-explanation-smoke.md",
     4	  "query": "Explain what this graph does. If anything important is missing, ask one clarifying question; otherwise inspect the workflow and answer directly.",
     5	  "graph": {
     6	    "1": {
     7	      "class_type": "CheckpointLoaderSimple",
     8	      "inputs": {
     9	        "ckpt_name": "sd15.safetensors"
    10	      }
    11	    },
    12	    "2": {
    13	      "class_type": "CLIPTextEncode",
    14	      "inputs": {
    15	        "clip": [
    16	          "1",
    17	          1
    18	        ],
    19	        "text": "a quiet studio portrait"
    20	      }
    21	    },
    22	    "3": {
    23	      "class_type": "KSampler",
    24	      "inputs": {
    25	        "cfg": 7.0,
    26	        "model": [
    27	          "1",
    28	          0
    29	        ],
    30	        "positive": [
    31	          "2",
    32	          0
    33	        ],
    34	        "steps": 20
    35	      }
    36	    }
    37	  },
    38	  "assessment": {
    39	    "expect_graph_changed": false
    40	  },
    41	  "classification": {
    42	    "kind": "health_control",
    43	    "excluded_from_semantic_product_rates": true,
    44	    "purpose": "Smoke-test that an inline graph can be inspected and answered without requiring a product-quality semantic score."
    45	  }
    46	}
FILE tests/live_agentic_harness/scenarios/speed-distillation-research.json
     1	{
     2	  "id": "speed-distillation-research",
     3	  "query": "This video workflow is too slow. Is there a distilled or faster way to run it without changing the creative intent?",
     4	  "assessment": {
     5	    "expect_graph_changed": false
     6	  },
     7	  "classification": {
     8	    "kind": "health_control",
     9	    "excluded_from_semantic_product_rates": true,
    10	    "purpose": "Exercise the research route without a source graph; this is transport/routing health, not semantic product quality."
    11	  }
    12	}

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib,collections\\nroot=pathlib.Path(\"tests/live_agentic_harness/scenarios\")\\nsems=[]\\nfor p in sorted(root.glob(\"*.json\")):\\n s=json.loads(p.read_text())\\n if (s.get(\"classification\") or {}).get(\"kind\")==\"semantic_product\":sems.append(s)\\nprint(\"rubric_key_shapes\",collections.Counter(tuple(sorted(s[\"answer_rubric\"])) for s in sems))\\nprint(\"workflow_path_mismatch\",[s[\"id\"] for s in sems if s[\"answer_rubric\"].get(\"workflow_path\")"'!=s.get("workflow_path")])'"\\nprint(\"bad_pass\",[s[\"id\"] for s in sems if s[\"answer_rubric\"].get(\"pass_condition\")"'!="Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion."])'"\\nprint(\"fail_sets\",collections.Counter(tuple(s[\"answer_rubric\"].get(\"fail_conditions\",[])) for s in sems))\\nprint(\"criteria_lengths\",collections.Counter(len(s[\"answer_rubric\"].get(\"expected_criteria\",[])) for s in sems))\\nprint(\"judge\",collections.Counter(s[\"answer_rubric\"].get(\"judge\") for s in sems))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 695ms:
rubric_key_shapes Counter({('expected_criteria', 'fail_conditions', 'judge', 'pass_condition', 'required_node_evidence', 'workflow_path'): 35})
workflow_path_mismatch []
bad_pass []
fail_sets Counter({('hallucinated nodes, settings, connections, model behavior, citations, or provider facts', 'technically wrong or materially misleading claims', 'irrelevant or generic advice that does not address this workflow and question', 'vacuous node-name listing without causal explanation, comparison, or diagnosis', 'empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer'): 35})
criteria_lengths Counter({4: 35})
judge Counter({'semantic_answer': 35})

 succeeded in 783ms:
WORKFLOW 485ff2fa6dcc1917 keys ['edges', 'groups', 'id', 'inputs', 'metadata', 'nodes', 'outputs', 'requirements', 'source', 'strict_types', 'vibecomfy_format_version']
WORKFLOW d7853cd7421f9ebc keys ['edges', 'groups', 'id', 'inputs', 'metadata', 'nodes', 'outputs', 'requirements', 'source', 'strict_types', 'vibecomfy_format_version']
WORKFLOW d93baf73c8a43f57 keys ['edges', 'groups', 'id', 'inputs', 'metadata', 'nodes', 'outputs', 'requirements', 'source', 'strict_types', 'vibecomfy_format_version']

 succeeded in 944ms:
required_evidence_missing_from_source_blob 0


exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\"external_workflows/corpus\")\\nfor sid in [\"485ff2fa6dcc1917\",\"d7853cd7421f9ebc\",\"d93baf73c8a43f57\"]:\\n w=json.loads((root/(sid+\".json\")).read_text());print(\"WORKFLOW\",sid)\\n for n in w[\"nodes\"]:\\n  print(n.get(\"uid\"),n.get(\"class_type\"),n.get(\"title\"),json.dumps(n.get(\"widgets_values\")),json.dumps(n.get(\"properties\")))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 971ms:
WORKFLOW 485ff2fa6dcc1917
Traceback (most recent call last):
  File "<string>", line 6, in <module>
AttributeError: 'str' object has no attribute 'get'

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nfor sid in [\"485ff2fa6dcc1917\",\"d7853cd7421f9ebc\",\"d93baf73c8a43f57\"]:\\n w=json.loads((pathlib.Path(\"external_workflows/corpus\")/(sid+\".json\")).read_text());print(sid,type(w[\"nodes\"]),list(w[\"nodes\"])[:5]);print(json.dumps(w[\"nodes\"],ensure_ascii=False)[:2500])'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 582ms:
485ff2fa6dcc1917 <class 'dict'> ['10', '11', '12', '16', '17']
{"10": {"class_type": "CutAndDragOnPath", "id": "10", "inputs": {}, "metadata": {"_ui": {"flags": {}, "id": 10, "inputs": [{"link": 22, "name": "image", "type": "IMAGE"}, {"link": 10, "name": "mask", "type": "MASK"}, {"link": 14, "name": "coordinates", "type": "STRING", "widget": {"name": "coordinates"}}, {"link": 24, "name": "bg_image", "shape": 7, "type": "IMAGE"}], "mode": 0, "order": 4, "outputs": [{"links": [17], "name": "image", "slot_index": 0, "type": "IMAGE"}, {"links": [], "name": "mask", "slot_index": 1, "type": "MASK"}], "pos": [8.958178520202637, 395.44854736328125], "properties": {"Node name for S&R": "CutAndDragOnPath"}, "size": [315, 166], "type": "CutAndDragOnPath", "widgets_values": ["", 1024, 768, false]}, "flags": {}, "mode": 0, "provenance": "untrusted_source"}, "mode": 0, "pack": null, "raw_widgets": {"has_dict_rows": false, "length": 4, "shape": "list", "source": "ui.widgets_values", "values": ["", 1024, 768, false]}, "uid": "10", "widgets": {"widget_0": "", "widget_1": 1024, "widget_2": 768, "widget_3": false}}, "11": {"class_type": "LoadImage", "id": "11", "inputs": {"image": "clipspace/clipspace-mask-6709059.199999999.png [input]", "unused_widget_1": "image"}, "metadata": {"_ui": {"flags": {}, "id": 11, "inputs": [], "mode": 0, "order": 1, "outputs": [{"links": [12, 19, 22], "name": "IMAGE", "slot_index": 0, "type": "IMAGE"}, {"links": [10, 20], "name": "MASK", "slot_index": 1, "type": "MASK"}], "pos": [-620.6697998046875, 302.7655029296875], "properties": {"Node name for S&R": "LoadImage"}, "size": [315, 314], "type": "LoadImage", "widgets_values": ["clipspace/clipspace-mask-6709059.199999999.png [input]", "image"]}, "flags": {}, "mode": 0, "provenance": "untrusted_source"}, "mode": 0, "pack": null, "raw_widgets": {"has_dict_rows": false, "length": 2, "shape": "list", "source": "ui.widgets_values", "values": ["clipspace/clipspace-mask-6709059.199999999.png [input]", "image"]}, "uid": "11", "widgets": {}}, "12": {"class_type": "SplineEditor", "id": "12", "inputs": {}, "metadata": {"_ui": {"flags": {}, "id": 12, "inputs": [{"link": 12, "name": "bg_image", "shape": 7, "type": "IMAGE"}], "mode": 0, "order": 2, "outputs": [{"links": null, "name": "mask", "type": "MASK"}, {"links": [14], "name": "coord_str", "slot_index": 1, "type": "STRING"}, {"links": [], "name": "float", "slot_index": 2, "type": "FLOAT"}, {"links": null, "name": "count", "type": "INT"}, {"links": null, "name": "normalized_str", "type": "STRING"}], "pos": [-688.39111
d7853cd7421f9ebc <class 'dict'> ['27', '29', '30', '34']
{"27": {"class_type": "SaveVideo", "id": "27", "inputs": {"codec": "auto", "filename_prefix": "video/ComfyUI", "format": "auto"}, "metadata": {"_ui": {"flags": {}, "id": 27, "inputs": [{"link": 35, "name": "video", "type": "VIDEO"}], "mode": 0, "order": 3, "outputs": [], "pos": [1190, 620], "properties": {"Node name for S&R": "SaveVideo"}, "size": [531.188232421875, 398.43743896484375], "type": "SaveVideo", "widgets_values": ["video/ComfyUI", "auto", "auto"]}, "flags": {}, "mode": 0, "provenance": "untrusted_source"}, "mode": 0, "pack": null, "raw_widgets": {"has_dict_rows": false, "length": 3, "shape": "list", "source": "ui.widgets_values", "values": ["video/ComfyUI", "auto", "auto"]}, "uid": "27", "widgets": {}}, "29": {"class_type": "LoadImage", "id": "29", "inputs": {"image": "api_moonvalley_image_to_video_input_image.jpg", "unused_widget_1": "image"}, "metadata": {"_ui": {"flags": {}, "id": 29, "inputs": [], "mode": 0, "order": 1, "outputs": [{"links": [36], "name": "IMAGE", "type": "IMAGE"}, {"links": null, "name": "MASK", "type": "MASK"}], "pos": [320, 620], "properties": {"Node name for S&R": "LoadImage"}, "size": [430, 390], "type": "LoadImage", "widgets_values": ["api_moonvalley_image_to_video_input_image.jpg", "image"]}, "flags": {}, "mode": 0, "provenance": "untrusted_source"}, "mode": 0, "pack": null, "raw_widgets": {"has_dict_rows": false, "length": 2, "shape": "list", "source": "ui.widgets_values", "values": ["api_moonvalley_image_to_video_input_image.jpg", "image"]}, "uid": "29", "widgets": {}}, "30": {"class_type": "MarkdownNote", "id": "30", "inputs": {"unused_widget_0": "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"}, "metadata": {"_ui": {"bgcolor": "#000", "colo
d93baf73c8a43f57 <class 'dict'> ['21', '46', '47', '50', '52']
{"21": {"class_type": "SaveGLB", "id": "21", "inputs": {}, "metadata": {"_ui": {"flags": {}, "id": 21, "inputs": [{"link": 92, "name": "mesh", "type": "MESH,FILE_3D_GLB,FILE_3D_GLTF,FILE_3D_OBJ,FILE_3D_FBX,FILE_3D_STL,FILE_3D_USDZ,FILE_3D"}], "mode": 0, "order": 5, "outputs": [], "pos": [-1891.1849394490798, 5054.079271096964], "properties": {"Camera Config": {"cameraType": "perspective", "fov": 35, "state": {"cameraType": "perspective", "position": {"x": 6.786724982855805, "y": 1.9262054236803827, "z": 4.315390609507273}, "target": {"x": 0.5610696024689849, "y": 1.8227901315768118, "z": -0.15103066686464472}, "zoom": 1}}, "Light Config": {"hdri": {"enabled": false, "hdriPath": "", "intensity": 1, "showAsBackground": false}, "intensity": 2.4000000000000004}, "Model Config": {"gizmo": {"enabled": false, "mode": "translate", "position": {"x": 0.3622254788581172, "y": 1.8487530247818735, "z": 3.580411492082191}, "rotation": {"x": 0, "y": 0, "z": 0}, "scale": {"x": 2.687608243041624, "y": 2.687608243041624, "z": 2.687608243041624}}, "materialMode": "original", "showSkeleton": false, "upDirection": "original"}, "Node name for S&R": "SaveGLB", "Scene Config": {"backgroundColor": "#8e9ea9", "backgroundImage": "", "backgroundRenderMode": "tiled", "showGrid": false}, "cnr_id": "comfy-core", "enableTabs": false, "hasSecondTab": false, "secondTabOffset": 80, "secondTabText": "Send Back", "secondTabWidth": 65, "tabWidth": 65, "tabXOffset": 10, "ue_properties": {"input_ue_unconnectable": {}, "version": "7.8", "widget_ue_connectable": {}}, "ver": "0.21.1"}, "size": [782.0843697681353, 601.1357657565522], "type": "SaveGLB", "widgets_values": ["3d/ComfyUI", ""]}, "flags": {}, "mode": 0, "provenance": "untrusted_source"}, "mode": 0, "pack": null, "raw_widgets": {"has_dict_rows": false, "length": 2, "shape": "list", "source": "ui.widgets_values", "values": ["3d/ComfyUI", ""]}, "uid": "21", "widgets": {"widget_0": "3d/ComfyUI", "widget_1": ""}}, "46": {"class_type": "PreviewImage", "id": "46", "inputs": {}, "metadata": {"_ui": {"flags": {}, "id": 46, "inputs": [{"link": 88, "name": "images", "type": "IMAGE"}], "mode": 0, "order": 6, "outputs": [], "pos": [-2950, 5000], "properties": {"Node name for S&R": "PreviewImage (normal_opengl)", "cnr_id": "comfy-core", "enableTabs": false, "hasSecondTab": false, "secondTabOffset": 80, "secondTabText": "Send Back", "secondTabWidth": 65, "tabWidth": 65, "tabXOffset": 10, "ue_properties": {"input_ue_unconnectable": {}, "version": "7.8",

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\"external_workflows/corpus\")\\nfor sid,classes in [(\"485ff2fa6dcc1917\",{\"INPAINT_InpaintWithModel\"}),(\"d7853cd7421f9ebc\",set()),(\"d93baf73c8a43f57\",{\"SaveGLB\",\"PreviewImage\"})]:\\n w=json.loads((root/(sid+\".json\")).read_text());print(\"WORKFLOW\",sid)\\n for uid,n in w[\"nodes\"].items():\\n  if n.get(\"class_type\") in classes or sid.startswith(\"d785\"):\\n   print(uid,n.get(\"class_type\"),\"inputs\",json.dumps(n.get(\"inputs\"),ensure_ascii=False),\"widgets\",json.dumps(n.get(\"widgets\"),ensure_ascii=False),\"raw\",json.dumps(n.get(\"raw_widgets\"),ensure_ascii=False))\\n print(\"edges\",json.dumps(w[\"edges\"],ensure_ascii=False))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 462ms:
WORKFLOW 485ff2fa6dcc1917
18 INPAINT_InpaintWithModel inputs {} widgets {"widget_0": 534667941392889, "widget_1": "fixed"} raw {"has_dict_rows": false, "length": 2, "shape": "list", "source": "ui.widgets_values", "values": [534667941392889, "fixed"]}
edges [{"from_node": "11", "from_output": "0", "to_input": "bg_image", "to_node": "12"}, {"from_node": "17", "from_output": "0", "to_input": "inpaint_model", "to_node": "18"}, {"from_node": "11", "from_output": "0", "to_input": "image", "to_node": "18"}, {"from_node": "11", "from_output": "1", "to_input": "mask", "to_node": "18"}, {"from_node": "11", "from_output": "0", "to_input": "image", "to_node": "10"}, {"from_node": "11", "from_output": "1", "to_input": "mask", "to_node": "10"}, {"from_node": "12", "from_output": "1", "to_input": "coordinates", "to_node": "10"}, {"from_node": "18", "from_output": "0", "to_input": "bg_image", "to_node": "10"}, {"from_node": "10", "from_output": "0", "to_input": "images", "to_node": "16"}]
WORKFLOW d7853cd7421f9ebc
27 SaveVideo inputs {"codec": "auto", "filename_prefix": "video/ComfyUI", "format": "auto"} widgets {} raw {"has_dict_rows": false, "length": 3, "shape": "list", "source": "ui.widgets_values", "values": ["video/ComfyUI", "auto", "auto"]}
29 LoadImage inputs {"image": "api_moonvalley_image_to_video_input_image.jpg", "unused_widget_1": "image"} widgets {} raw {"has_dict_rows": false, "length": 2, "shape": "list", "source": "ui.widgets_values", "values": ["api_moonvalley_image_to_video_input_image.jpg", "image"]}
30 MarkdownNote inputs {"unused_widget_0": "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"} widgets {} raw {"has_dict_rows": false, "length": 1, "shape": "list", "source": "ui.widgets_values", "values": ["## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"]}
34 MoonvalleyImg2VideoNode inputs {} widgets {"widget_0": "A bedroom is transformed into a surreal underwater dreamscape, completely submerged in deep turquoise water where caustic light patterns ripple and dance across the walls, floor, and ceiling. In the center of this submerged room, a ballerina gracefully holds a pose en pointe, her form silhouetted against the ethereal blue glow. She moves with impossible slowness, transitioning between ballet positions as her sheer white dress billows around her in the gentle, silent currents. Tiny bubbles occasionally escape her lips, rising towards the undulating surface above, which serves as the room's only light source. The scene is both beautiful and unsettling, a silent performance in a liquid world where reality is suspended. Background: The ceiling is the agitated surface of the water, with ethereal beams of light filtering down and constantly shifting. A bed sits against the back wall, its form partially obscured by the moving shadows and light. Middleground: A silhouetted ballerina stands as the focal point, her arms outstretched in a graceful ballet pose. Her diaphanous dress flows weightlessly around her, moved by invisible underwater currents as she performs her silent dance. Foreground: The floor is covered in a moving tapestry of bright caustic reflections from the water's surface above. The ballerina's shadow and reflection are cast upon the floor, distorting and swaying with the light.", "widget_1": "low-poly, flat shader, bad rigging, stiff animation, uncanny eyes, low-quality textures, looping glitch, cheap effect, overbloom, bloom spam, default lighting, game asset, stiff face, ugly specular, AI artifacts", "widget_2": "16:9 (1920 x 1080)", "widget_3": 7, "widget_4": 2328774152, "widget_5": "randomize", "widget_6": 100} raw {"has_dict_rows": false, "length": 7, "shape": "list", "source": "ui.widgets_values", "values": ["A bedroom is transformed into a surreal underwater dreamscape, completely submerged in deep turquoise water where caustic light patterns ripple and dance across the walls, floor, and ceiling. In the center of this submerged room, a ballerina gracefully holds a pose en pointe, her form silhouetted against the ethereal blue glow. She moves with impossible slowness, transitioning between ballet positions as her sheer white dress billows around her in the gentle, silent currents. Tiny bubbles occasionally escape her lips, rising towards the undulating surface above, which serves as the room's only light source. The scene is both beautiful and unsettling, a silent performance in a liquid world where reality is suspended. Background: The ceiling is the agitated surface of the water, with ethereal beams of light filtering down and constantly shifting. A bed sits against the back wall, its form partially obscured by the moving shadows and light. Middleground: A silhouetted ballerina stands as the focal point, her arms outstretched in a graceful ballet pose. Her diaphanous dress flows weightlessly around her, moved by invisible underwater currents as she performs her silent dance. Foreground: The floor is covered in a moving tapestry of bright caustic reflections from the water's surface above. The ballerina's shadow and reflection are cast upon the floor, distorting and swaying with the light.", "low-poly, flat shader, bad rigging, stiff animation, uncanny eyes, low-quality textures, looping glitch, cheap effect, overbloom, bloom spam, default lighting, game asset, stiff face, ugly specular, AI artifacts", "16:9 (1920 x 1080)", 7, 2328774152, "randomize", 100]}
edges [{"from_node": "34", "from_output": "0", "to_input": "video", "to_node": "27"}, {"from_node": "29", "from_output": "0", "to_input": "image", "to_node": "34"}]
WORKFLOW d93baf73c8a43f57
21 SaveGLB inputs {} widgets {"widget_0": "3d/ComfyUI", "widget_1": ""} raw {"has_dict_rows": false, "length": 2, "shape": "list", "source": "ui.widgets_values", "values": ["3d/ComfyUI", ""]}
46 PreviewImage inputs {} widgets {} raw {"has_dict_rows": false, "length": 0, "shape": "list", "source": "ui.widgets_values", "values": []}
47 PreviewImage inputs {} widgets {} raw {"has_dict_rows": false, "length": 0, "shape": "list", "source": "ui.widgets_values", "values": []}
edges [{"from_node": "67", "from_output": "1", "to_input": "images", "to_node": "46"}, {"from_node": "67", "from_output": "2", "to_input": "images", "to_node": "47"}, {"from_node": "9", "from_output": "0", "to_input": "source_image", "to_node": "67"}, {"from_node": "67", "from_output": "0", "to_input": "mesh", "to_node": "21"}]

exec
/bin/zsh -lc "rg -n \"semantic_product|health_control|excluded_from_semantic_product_rates|scenario_kind|revision_status|answer_rubric\" . --glob '"'!tests/live_agentic_harness/scenario_manifest.json'"' --glob '"'!tests/live_agentic_harness/scenarios/*.json'"' --glob '"'!.oracle/checkins/*'"'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 144ms:
./tests/live_agentic_harness/REVISIONS.md:5:as `revision_status: revised|matched`.
./tests/live_agentic_harness/scenario_manifest.py:96:        scenario_kind = "edit"
./tests/live_agentic_harness/scenario_manifest.py:97:        if (scenario.get("classification") or {}).get("kind") == "health_control":
./tests/live_agentic_harness/scenario_manifest.py:98:            scenario_kind = "health_control"
./tests/live_agentic_harness/scenario_manifest.py:99:        elif scenario.get("answer_rubric"):
./tests/live_agentic_harness/scenario_manifest.py:100:            scenario_kind = "semantic_product"
./tests/live_agentic_harness/scenario_manifest.py:107:                "revision_status": "revised" if scenario_id in revised_ids else "matched",
./tests/live_agentic_harness/scenario_manifest.py:108:                "scenario_kind": scenario_kind,
./tests/test_live_agentic_harness_corpus_manifest.py:40:    assert {entry["revision_status"] for entry in entries} == {"matched", "revised"}
./tests/test_live_agentic_harness_corpus_manifest.py:41:    assert {entry["id"] for entry in entries if entry["revision_status"] == "revised"} == CORRECTED_EDITS
./tests/test_live_agentic_harness_corpus_manifest.py:54:    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
./tests/test_live_agentic_harness_corpus_manifest.py:55:    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
./tests/test_live_agentic_harness_corpus_manifest.py:64:    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
./tests/test_live_agentic_harness_corpus_manifest.py:68:        rubric = scenario["answer_rubric"]

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -p no:rerunfailures -q tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 3810ms:
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
The full pytest slice cannot initialize because this read-only sandbox exposes no writable temporary directory (failure occurs before test collection, even with cache/rerun plugins disabled). I’m continuing with read-only executable checks and will run the no-temp corpus tests with capture disabled, then separate this environment limitation from the code verdict.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 pytest -s -p no:cacheprovider -p no:rerunfailures -q tests/test_live_agentic_harness_corpus_manifest.py -k 'authoritative_manifest_selects_and_hashes_exactly_100_scenarios or d13_no_change_reconciliation_and_rubric_contract'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 6593ms:
.OMP: Warning #179: Function Can't set size of /tmp file failed:
.
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2 passed, 4 deselected, 1 warning in 2.87s

exec
/bin/zsh -lc "rg -n '"'^def test_'"' tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
tests/test_live_agentic_intent_judge_schema_context.py:9:def test_intent_judge_includes_scenario_desired_rubric(
tests/test_live_agentic_intent_judge_schema_context.py:60:def test_intent_judge_includes_compiled_api_schema_context(
tests/test_live_agentic_intent_judge_schema_context.py:136:def test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input(
tests/test_live_agentic_intent_judge_schema_context.py:231:def test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope(
tests/test_structural_harness_runner.py:15:def test_runner_help_exposes_repo_local_options(capsys: pytest.CaptureFixture[str]) -> None:
tests/test_structural_harness_runner.py:31:def test_main_forwards_actor_tag_defaults_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
tests/test_structural_harness_runner.py:73:def test_run_chaining_family_adapts_to_reports_dir_api_shape(monkeypatch: pytest.MonkeyPatch) -> None:
tests/test_structural_harness_runner.py:125:def test_structural_runner_rejects_live_agent_actors() -> None:
tests/test_structural_harness_runner.py:130:def test_structural_runner_rejects_live_mode() -> None:
tests/test_structural_harness_runner.py:143:def test_assessor_parse_failure_is_retried_once() -> None:
tests/test_structural_harness_runner.py:161:def test_assessor_parse_failure_retry_is_bounded() -> None:
tests/test_structural_harness_runner.py:177:def test_assessor_rubric_failure_is_not_retried() -> None:
tests/test_live_agentic_harness_guard_contract.py:187:def test_agentic_guard_rejects_fake_dispatchers(tmp_path: Path, dispatcher: str) -> None:
tests/test_live_agentic_harness_guard_contract.py:196:def test_agentic_guard_rejects_non_agentic_model_behavior(
tests/test_live_agentic_harness_guard_contract.py:207:def test_agentic_guard_allows_blocked_real_agentic_artifacts(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:218:def test_agentic_guard_catches_unchanged_graph_and_upstream_errors(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:272:def test_agentic_guard_allows_explicit_safe_refusal_scenarios(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:318:def test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:349:def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:396:def test_desired_edit_rejects_safe_refusal_when_grounded_judge_unavailable(
tests/test_live_agentic_harness_guard_contract.py:425:def test_desired_edit_rejects_fabricated_safe_refusal(
tests/test_live_agentic_harness_guard_contract.py:454:def test_desired_edit_accepts_grounded_safe_refusal(
tests/test_live_agentic_harness_guard_contract.py:485:def test_desired_edit_refusal_label_with_graph_change_fails_closed_without_verdict(
tests/test_live_agentic_harness_guard_contract.py:522:def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:554:def test_corrected_d13_edits_cannot_pass_as_noops(
tests/test_live_agentic_harness_guard_contract.py:593:def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
tests/test_live_agentic_harness_guard_contract.py:629:def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:665:def test_agentic_guard_rejects_forbidden_model_request_substrings(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:704:def test_agentic_guard_rejects_static_widget_edit_overridden_by_link(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:725:def test_agentic_guard_rejects_no_effective_value_change_for_claimed_target(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:746:def test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:934:def test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating(
tests/test_live_agentic_harness_guard_contract.py:963:def test_agentic_guard_false_landed_claim_still_fails_via_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1004:def test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1048:def test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check(
tests/test_live_agentic_harness_guard_contract.py:1080:def test_agentic_guard_false_validation_success_claim_still_fails_via_gates(
tests/test_live_agentic_harness_guard_contract.py:1153:def test_agentic_guard_expected_edit_requires_positive_landed_count(
tests/test_live_agentic_harness_guard_contract.py:1188:def test_agentic_guard_expected_edit_with_positive_landed_count_passes(
tests/test_live_agentic_harness_guard_contract.py:1226:def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
tests/test_live_agentic_harness_guard_contract.py:1267:def test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1304:def test_agentic_guard_rejects_route_not_applyable_without_landed_count(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1340:def test_agentic_guard_rejects_failure_outcome_without_landed_count(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1377:def test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph(
tests/test_live_agentic_harness_guard_contract.py:1420:def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1462:def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1483:def test_agentic_guard_allows_shared_linked_source_edit_when_declared(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1501:def test_agentic_guard_treats_skipped_queue_validation_as_warning(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1538:def test_agentic_guard_product_fails_real_queue_validation_failure(tmp_path: Path) -> None:
tests/test_live_agentic_runner_persistence.py:55:def test_persists_per_scenario_and_incremental_run_summary(tmp_path: Path) -> None:
tests/test_live_agentic_runner_persistence.py:82:def test_final_summary_replaces_partial_summary(tmp_path: Path) -> None:
tests/test_live_agentic_runner_persistence.py:94:def test_runner_does_not_retry_outer_timeout(
tests/test_live_agentic_runner_persistence.py:146:def test_runner_types_provider_capacity_without_retry(
tests/test_live_agentic_runner_persistence.py:226:def test_runner_retries_only_typed_empty_zero_token_attempt(
tests/test_live_agentic_runner_persistence.py:268:def test_runner_keeps_malformed_nonempty_as_product_failure(
tests/test_live_agentic_runner_persistence.py:308:def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
tests/test_live_agentic_runner_persistence.py:361:def test_runner_does_not_classify_soft_search_429_as_infra(
tests/test_live_agentic_runner_persistence.py:429:def test_runner_timeout_preserves_scenario_graph_change_expectation(
tests/test_live_agentic_runner_persistence.py:469:def test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed() -> None:
tests/test_live_agentic_runner_persistence.py:494:def test_retryability_is_derived_from_canonical_typed_evidence() -> None:
tests/test_live_agentic_runner_persistence.py:530:def test_persisted_agentic_summary_redacts_json_quoted_secrets(

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -s -p no:cacheprovider -p no:rerunfailures -q tests/test_structural_harness_runner.py tests/test_live_agentic_runner_persistence.py::test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed tests/test_live_agentic_runner_persistence.py::test_retryability_is_derived_from_canonical_typed_evidence' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 16262ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
..........
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
10 passed, 1 warning in 11.72s

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib,collections\\nroot=pathlib.Path(\"tests/live_agentic_harness/scenarios\")\\nrows=[]\\nfor p in sorted(root.glob(\"*.json\")):\\n s=json.loads(p.read_text())\\n if s.get(\"desired\"):\\n  a=s.get(\"assessment\") or {};rows.append((s[\"id\"],bool(a.get(\"allow_safe_refusal_outcome_kinds\") or a.get(\"allow_safe_refusal_outcome_kind\")),a.get(\"expect_graph_changed\"),a.get(\"skip_intent_judge\")))\\nprint(\"desired\",len(rows),\"refusal-enabled\",sum(x[1] for x in rows),\"normal-edit\",sum(not x[1] for x in rows));print(\"bad\",[x for x in rows if x[2] is not True or x[3] is True])\\nprint(\"refusal-enabled IDs\");print(*[x[0] for x in rows if x[1]],sep=\"\\\\n\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 600ms:
desired 42 refusal-enabled 3 normal-edit 39
bad []
refusal-enabled IDs
3d-3d-shape-generation-and-export-workflow-8800a9
audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf
image-face-detection-and-cropping-workflow-949658

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\".\");m=json.loads((root/\"tests/live_agentic_harness/scenario_manifest.json\").read_text());bad=[]\\nfor e in m[\"entries\"]:\\n s=json.loads((root/e[\"path\"]).read_text())\\n if (s.get(\"classification\") or {}).get(\"kind\")"'!="semantic_product":continue'"\\n wf=json.loads((root/e[\"source_workflow\"][\"path\"]).read_text());nodes=wf.get(\"nodes\") or {};vals=nodes.values() if isinstance(nodes,dict) else nodes\\n classes={str(n.get(\"class_type\") or n.get(\"type\") or \"\") for n in vals if isinstance(n,dict)};uids={str(n.get(\"uid\") or n.get(\"id\") or \"\") for n in vals if isinstance(n,dict)}\\n for ev in s[\"answer_rubric\"][\"required_node_evidence\"]:\\n  if str(ev) not in classes|uids:bad.append((e[\"id\"],ev))\\nprint(\"required_evidence_not_exact_class_or_uid\",len(bad));print(*bad,sep=\"\\\\n\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 752ms:
required_evidence_not_exact_class_or_uid 0


exec
/bin/zsh -lc 'rg -n "D13 CHECKPOINT VERDICT|VERDICT:|''^## Issue|''^### Issue|FAIL|rework" .oracle/checkins/batch-D13.md | tail -80' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
46:First line: `D13 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
47:Then per-focus findings (1–9) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
65:- **Oracle** — GPT-5.6 Sol or Grok 4.6 (grok CLI): gates every batch; rework until it passes.
547: .oracle/briefs/batch-D13-rework.md                 |   33 +
606:A	.oracle/briefs/batch-D13-rework.md
718: _UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
878:+        # edit, specific next action, no fabricated inability), and it FAILS
1012:         for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
3039:5aa73c53 megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green
3040: .oracle/briefs/batch-D13-rework.md                 |   33 +
3418:5aa73c53 (HEAD -> oracle-run) megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green
3967:   815	        # edit, specific next action, no fabricated inability), and it FAILS
4069:   917	        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
4108:/bin/zsh -lc 'python -c $'"'import json,pathlib\\nroot=pathlib.Path(\"tests/live_agentic_harness/scenarios\")\\nfor p in sorted(root.glob(\"*.json\")):\\n s=json.loads(p.read_text())\\n if (s.get(\"classification\") or {}).get(\"kind\")==\"semantic_product\":\\n  r=s[\"answer_rubric\"]\\n  print(\"ID\",s[\"id\"]);print(\"Q\",s[\"query\"]);print(\"EVID\",json.dumps(r.get(\"required_node_evidence\"),sort_keys=True));print(\"CRIT\",json.dumps(r.get(\"expected_criteria\"),sort_keys=True));print(\"PASS\",r.get(\"pass_condition\"));print(\"FAIL\",json.dumps(r.get(\"fail_conditions\")));print()'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
4115:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4122:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4129:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4136:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4143:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4150:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4157:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4164:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4171:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4178:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4185:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4192:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4199:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4206:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4213:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4220:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4227:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4234:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4241:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4248:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4255:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4262:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4269:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4276:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4283:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4290:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4297:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4304:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4311:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4318:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4325:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4332:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4339:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4346:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]
4353:FAIL ["hallucinated nodes, settings, connections, model behavior, citations, or provider facts", "technically wrong or materially misleading claims", "irrelevant or generic advice that does not address this workflow and question", "vacuous node-name listing without causal explanation, comparison, or diagnosis", "empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer"]

exec
/bin/zsh -lc 'python -c $'"'import subprocess,json,pathlib\\nbase=\"0f015101\";head=\"5aa73c53\";prefix=\"tests/live_agentic_harness/scenarios/\"\\ndef files(rev):return [x for x in subprocess.check_output([\"git\",\"ls-tree\",\"-r\",\"--name-only\",rev,prefix],text=True).splitlines() if x.endswith(\".json\")]\\nbf,hf=files(base),files(head);print(\"base/head counts\",len(bf),len(hf));print(\"added\",sorted(set(hf)-set(bf)));print(\"removed\",sorted(set(bf)-set(hf)))\\nq=[];wf=[];ids=[]\\nfor p in sorted(set(bf)&set(hf)):\\n a=json.loads(subprocess.check_output([\"git\",\"show\",f\"{base}:{p}\"]));b=json.loads(subprocess.check_output([\"git\",\"show\",f\"{head}:{p}\"]))\\n if a.get(\"query\")"'!=b.get("query"):q.append((pathlib.Path(p).stem,a.get("query"),b.get("query")))'"\\n if a.get(\"workflow_path\")"'!=b.get("workflow_path"):wf.append((p,a.get("workflow_path"),b.get("workflow_path")))'"\\n if a.get(\"id\")"'!=b.get("id"):ids.append((p,a.get("id"),b.get("id")))'"\\nprint(\"query_changes\",len(q));print(*[x[0] for x in q],sep=\"\\\\n\");print(\"workflow_path_changes\",wf);print(\"id_changes\",ids)'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 9791ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
base/head counts 100 100
added []
removed []
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
query_changes 3
multi-3d-preview-and-image-output-workflow-d93baf
video-image-to-video-conversion-with-moonvalley-d7853c
video-video-inpainting-with-spline-based-cut-and-dra-485ff2
workflow_path_changes []
id_changes []

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '930,1010p'; nl -ba tests/live_agentic_harness/runner.py | sed -n '1,70p'; nl -ba tests/live_agentic_harness/runner.py | sed -n '475,515p'; nl -ba tests/live_agentic_harness/scenario_manifest.py | sed -n '134,265p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   930	                    "check": "soft_warning",
   931	                    "severity": "warning",
   932	                    "detail": msg,
   933	                }
   934	            )
   935
   936	    if impl_result is not None:
   937	        # G0R: the residual "unchanged" substring gate over the
   938	        # implementation_result message is removed — prose never gates
   939	        # scoring.  Only the structured ok flag is authoritative.
   940	        if impl_result.get("ok") is False:
   941	            issues.append(
   942	                {
   943	                    "check": "implementation_result_ok",
   944	                    "severity": "error",
   945	                    "detail": (
   946	                        "implementation_result.ok is False: "
   947	                        f"{impl_result.get('error') or impl_result.get('message', '')}"
   948	                    ),
   949	                }
   950	            )
   951
   952	    issues.extend(_assess_model_request_artifact(output_dir, scenario))
   953
   954	    # Deduplicate while preserving order.
   955	    seen: set[tuple[str, str, str]] = set()
   956	    deduped: list[dict[str, Any]] = []
   957	    for issue in issues:
   958	        key = (issue["check"], issue["severity"], issue["detail"])
   959	        if key in seen:
   960	            continue
   961	        seen.add(key)
   962	        deduped.append(issue)
   963
   964	    errors = [issue for issue in deduped if issue["severity"] == "error"]
   965	    return {
   966	        "passed": len(errors) == 0,
   967	        "expect_graph_changed": expect_graph_changed,
   968	        "expected_outcome_kinds": sorted(expected_outcome_kinds),
   969	        "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
   970	        "issue_count": len(deduped),
   971	        "error_count": len(errors),
   972	        "issues": deduped,
   973	    }
     1	"""Live agentic harness runner for VibeComfy headless scenarios.
     2
     3	Scenarios run CONCURRENTLY — each in its own subprocess (process isolation +
     4	kill-on-timeout via ``subprocess.run``), bounded by ``--max-workers``. Modeled
     5	on the subagent-launcher fanout: one process per task, a bounded pool, a
     6	per-task timeout. ``--single`` is the per-scenario subprocess entry point.
     7	"""
     8
     9	from __future__ import annotations
    10
    11	import argparse
    12	import json
    13	import subprocess
    14	import sys
    15	import tempfile
    16	import threading
    17	import time
    18	from pathlib import Path
    19	from typing import Any, Mapping
    20
    21	from vibecomfy.agent.deepseek_usage import (
    22	    add_deepseek_usage,
    23	    coerce_deepseek_usage,
    24	    combine_deepseek_cost_bases,
    25	)
    26
    27	from .failure_analysis import (
    28	    DEFAULT_AGENT_TIMEOUT_S,
    29	    DEFAULT_ANALYSIS_MODEL,
    30	    DEFAULT_ANALYSIS_WORKERS,
    31	    DEFAULT_RECOMMENDATIONS_MODEL,
    32	    analyze_failures,
    33	    prepare_failure_analysis,
    34	    recommendations_for_run,
    35	)
    36	from .scenario_manifest import discover_manifest_scenarios
    37
    38	DEFAULT_MAX_WORKERS = 12
    39	DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
    40	DEFAULT_PROGRESS_EVERY = 10
    41	DEFAULT_INFRA_RETRIES = 1
    42	REPO = Path(__file__).resolve().parents[2]
    43
    44	def _scenario_paths(
    45	    scenarios_dir: Path,
    46	    *,
    47	    manifest_path: Path | None = None,
    48	) -> list[Path]:
    49	    if not scenarios_dir.is_dir():
    50	        raise FileNotFoundError(f"scenario directory is missing: {scenarios_dir}")
    51	    return discover_manifest_scenarios(scenarios_dir, manifest_path=manifest_path)
    52
    53
    54	def _load_scenario(path: Path) -> dict[str, Any]:
    55	    if path.suffix == ".json":
    56	        return json.loads(path.read_text(encoding="utf-8"))
    57	    import yaml
    58
    59	    return yaml.safe_load(path.read_text(encoding="utf-8"))
    60
    61
    62	def _output_dir_for(output_base: Any, tag: str, scenario_id: str) -> Path:
    63	    base = Path(output_base) if output_base else Path("out/agentic")
    64	    return Path(base) / tag / scenario_id
    65
    66
    67	def _run_dir_for(output_base: Any, tag: str) -> Path:
    68	    base = Path(output_base) if output_base else Path("out/agentic")
    69	    return Path(base) / tag
    70
   475	    scenario.setdefault("id", path.stem)
   476	    summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
   477	    summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
   478	    _classify_retryable_infra_summary(summary)
   479	    _persist_scenario_summary(summary, output_base, tag)
   480	    if out_file is not None:
   481	        out_file.parent.mkdir(parents=True, exist_ok=True)
   482	        out_file.write_text(json.dumps(summary, default=str), encoding="utf-8")
   483	    return summary
   484
   485
   486	def run_tag(
   487	    tag: str,
   488	    *,
   489	    scenarios_dir: Path | None = None,
   490	    output_base: Path | str | None = None,
   491	    max_workers: int = DEFAULT_MAX_WORKERS,
   492	    per_scenario_timeout: int = DEFAULT_PER_SCENARIO_TIMEOUT,
   493	    progress_every: int = DEFAULT_PROGRESS_EVERY,
   494	    infra_retries: int = DEFAULT_INFRA_RETRIES,
   495	    manifest_path: Path | None = None,
   496	) -> dict[str, Any]:
   497	    """Run every scenario under *scenarios_dir* CONCURRENTLY — each in its own
   498	    subprocess (process-isolated + kill-on-timeout), bounded by *max_workers*."""
   499	    if scenarios_dir is None:
   500	        scenarios_dir = Path(__file__).with_name("scenarios")
   501	    paths = _scenario_paths(scenarios_dir, manifest_path=manifest_path)
   502	    results: list[dict[str, Any] | None] = [None] * len(paths)
   503	    sem = threading.Semaphore(max(1, max_workers))
   504	    lock = threading.Lock()
   505	    tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
   506	    try:
   507	        def record_result(idx: int, summary: dict[str, Any]) -> None:
   508	            results[idx] = summary
   509	            results[idx].setdefault("scenario_id", paths[idx].stem)
   510	            _persist_scenario_summary(results[idx], output_base, tag)
   511	            with lock:
   512	                completed = sum(1 for r in results if r)
   513	                run_summary = _persist_run_summary(
   514	                    tag,
   515	                    results,
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

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/runner.py | sed -n '515,650p'; git diff --unified=20 0f015101..5aa73c53 -- tests/live_agentic_harness/runner.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 5ms:
diff --git a/tests/live_agentic_harness/runner.py b/tests/live_agentic_harness/runner.py
index 94672531..29bac47f 100644
--- a/tests/live_agentic_harness/runner.py
+++ b/tests/live_agentic_harness/runner.py
@@ -16,51 +16,56 @@ import tempfile
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
+from .scenario_manifest import discover_manifest_scenarios

 DEFAULT_MAX_WORKERS = 12
 DEFAULT_PER_SCENARIO_TIMEOUT = 1200  # seconds; kills a wedged/over-slow scenario
 DEFAULT_PROGRESS_EVERY = 10
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


@@ -470,46 +475,47 @@ def run_single(scenario_path: str, tag: str, output_base: Any, out_file: Path |
     scenario.setdefault("id", path.stem)
     summary = run_headless_scenario(scenario, output_base=output_base, tag=tag)
     summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
     _classify_retryable_infra_summary(summary)
     _persist_scenario_summary(summary, output_base, tag)
     if out_file is not None:
         out_file.parent.mkdir(parents=True, exist_ok=True)
         out_file.write_text(json.dumps(summary, default=str), encoding="utf-8")
     return summary


 def run_tag(
     tag: str,
     *,
     scenarios_dir: Path | None = None,
     output_base: Path | str | None = None,
     max_workers: int = DEFAULT_MAX_WORKERS,
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
     tmpdir = Path(tempfile.mkdtemp(prefix="vibecomfy-runner-"))
     try:
         def record_result(idx: int, summary: dict[str, Any]) -> None:
             results[idx] = summary
             results[idx].setdefault("scenario_id", paths[idx].stem)
             _persist_scenario_summary(results[idx], output_base, tag)
             with lock:
                 completed = sum(1 for r in results if r)
                 run_summary = _persist_run_summary(
                     tag,
                     results,
                     output_base,
                     total_scenarios=len(paths),
                     complete=False,
                 )
                 if progress_every > 0 and (
                     completed == len(paths) or completed % progress_every == 0
@@ -655,40 +661,48 @@ def run_tag(
         except Exception:  # noqa: BLE001
             pass

     return _persist_run_summary(
         tag,
         results,
         output_base,
         total_scenarios=len(paths),
         complete=True,
     )


 def _build_parser() -> argparse.ArgumentParser:
     parser = argparse.ArgumentParser(prog="python -m tests.live_agentic_harness.runner")
     parser.add_argument("--tag", default=None, help="Run tag (used in evidence path).")
     parser.add_argument(
         "--scenarios-dir",
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
@@ -808,40 +822,41 @@ def main(argv: list[str] | None = None) -> int:
         parser.error("--tag is required unless --analyze-existing-summary is used")

     if args.single:
         out_file = Path(args.single_out) if args.single_out else None
         ob = Path(args.output_base) if args.output_base else None
         summary = run_single(args.single, args.tag, ob, out_file)
         # Compact one-line stdout for liveness; the real payload is in --single-out.
         print(json.dumps({"scenario_id": summary.get("scenario_id"),
                           "ok": summary["guard"]["live_agentic_success"]}))
         return 0 if summary["guard"]["live_agentic_success"] else 1

     output_base = Path(args.output_base) if args.output_base else None
     summary = run_tag(
         args.tag,
         scenarios_dir=scenarios_dir,
         output_base=output_base,
         max_workers=args.max_workers,
         per_scenario_timeout=args.per_scenario_timeout,
         progress_every=args.progress_every,
         infra_retries=args.infra_retries,
+        manifest_path=Path(args.manifest) if args.manifest else None,
     )
     if args.prepare_failure_analysis or args.analyze_failures or args.recommend_fixes:
         run_summary_path = _run_dir_for(output_base, summary["tag"]) / "run_summary.json"
         analysis = _run_failure_analysis_from_summary(
             run_summary_path,
             scenarios_dir=scenarios_dir,
             analyze_failures_enabled=args.analyze_failures,
             prepare_only=args.prepare_failure_analysis,
             recommend_fixes=args.recommend_fixes,
             analysis_model=args.analysis_model,
             analysis_max_workers=args.analysis_max_workers,
             analysis_timeout=args.analysis_timeout,
             resume_failure_analysis=not args.restart_failure_analysis,
             recommendations_model=args.recommendations_model,
             recommendations_timeout=args.recommendations_timeout,
         )
         summary["failure_analysis"] = analysis

     if args.json:
         print(json.dumps(summary, indent=2, default=str))

exec
/bin/zsh -lc 'python -c $'"'import json,pathlib,hashlib\\nroot=pathlib.Path(\".\");m=json.loads((root/\"tests/live_agentic_harness/scenario_manifest.json\").read_text());pick=[m[\"entries\"][0],m[\"entries\"][49],m[\"entries\"][-1]]\\nfor e in pick:\\n p=root/e[\"path\"];src=e.get(\"source_workflow\");print(e[\"id\"],\"descriptor\",hashlib.sha256(p.read_bytes()).hexdigest(),\"manifest\",e[\"descriptor_sha256\"]);\\n if src:\\n  sp=root/src[\"path\"];print(\" source\",src[\"id\"],hashlib.sha256(sp.read_bytes()).hexdigest(),\"manifest\",src[\"sha256\"])'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 907ms:
3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2 descriptor f2d7ac44c1d69ddbc3da300e0700868a9107e64c2ce5b75a405d92080b761f46 manifest f2d7ac44c1d69ddbc3da300e0700868a9107e64c2ce5b75a405d92080b761f46
 source c24aa2ac329006f2 3c605c00652907736c02e5c4bfff6fa17c9edbfd06024be972b004dc2332f180 manifest 3c605c00652907736c02e5c4bfff6fa17c9edbfd06024be972b004dc2332f180
multi-ai-video-upscaling-with-detail-daemon-sampler-673197 descriptor 2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457 manifest 2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457
 source 673197a9269d00f8 d15ba9e1d9385ec8ebcbe3ba82d1e9a85af103821b369af3f45170ac8c037f1b manifest d15ba9e1d9385ec8ebcbe3ba82d1e9a85af103821b369af3f45170ac8c037f1b
video-wanvideo-text-to-video-generation-71f825 descriptor df4959641e24bfcd7b62ad558dc4cede081febf7e14f44475fd3a70855f60d31 manifest df4959641e24bfcd7b62ad558dc4cede081febf7e14f44475fd3a70855f60d31
 source 71f825e4550c95b7 87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3 manifest 87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3

exec
/bin/zsh -lc 'for f in tests/live_agentic_harness/scenarios/*485ff2.json tests/live_agentic_harness/scenarios/*d7853c.json tests/live_agentic_harness/scenarios/*d93baf.json; do nl -ba "$f" | sed -n '"'1,22p'; done; rg -n '\"id\": \"(3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2|multi-ai-video-upscaling-with-detail-daemon-sampler-673197|video-wanvideo-text-to-video-generation-71f825)\"' tests/live_agentic_harness/scenario_manifest.json" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 62ms:
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
7:      "id": "3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2",
640:      "id": "multi-ai-video-upscaling-with-detail-daemon-sampler-673197",
1286:      "id": "video-wanvideo-text-to-video-generation-71f825",

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '85,140p'; nl -ba vibecomfy/intent/prompts/refusal_judge.prompt.md | sed -n '1,100p'; nl -ba tests/test_live_agentic_harness_corpus_manifest.py | sed -n '25,155p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
    85
    86	def _parse_verdict(raw: str) -> dict[str, Any]:
    87	    """Parse the judge's JSON response into a normalized dict."""
    88	    parsed = json.loads(_strip_code_fences(raw))
    89	    criteria = parsed.get("criteria") or {}
    90	    normalized_criteria = {
    91	        "correct_node_targeted": bool(criteria.get("correct_node_targeted")),
    92	        "correct_parameter_changed": bool(criteria.get("correct_parameter_changed")),
    93	        "value_semantically_matches_intent": bool(criteria.get("value_semantically_matches_intent")),
    94	        "no_orphaned_wiring": bool(criteria.get("no_orphaned_wiring")),
    95	    }
    96	    return {
    97	        "pass_": bool(parsed.get("pass_")),
    98	        "criteria": normalized_criteria,
    99	        "rationale": str(parsed.get("rationale", "")),
   100	    }
   101
   102
   103	def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
   104	    """Parse the grounded-refusal judge's JSON response into a normalized dict."""
   105	    parsed = json.loads(_strip_code_fences(raw))
   106	    criteria = parsed.get("criteria") or {}
   107	    normalized_criteria = {
   108	        "supported_blocker": bool(criteria.get("supported_blocker")),
   109	        "no_representable_edit": bool(criteria.get("no_representable_edit")),
   110	        "specific_next_action": bool(criteria.get("specific_next_action")),
   111	        "no_fabricated_inability": bool(criteria.get("no_fabricated_inability")),
   112	    }
   113	    return {
   114	        "pass_": bool(parsed.get("pass_")),
   115	        "criteria": normalized_criteria,
   116	        "rationale": str(parsed.get("rationale", "")),
   117	    }
   118
   119
   120	def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
   121	    path = output_dir / "implementation_payload.json"
   122	    if not path.is_file():
   123	        return None
   124	    try:
   125	        data = json.loads(path.read_text(encoding="utf-8"))
   126	    except (OSError, json.JSONDecodeError):
   127	        return None
   128	    return data if isinstance(data, dict) else None
   129
   130
   131	def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
   132	    if not isinstance(payload, Mapping):
   133	        return None
   134	    graph = payload.get("graph")
   135	    if not isinstance(graph, Mapping):
   136	        return None
   137	    compiled_api = graph.get("compiled_api")
   138	    if not isinstance(compiled_api, Mapping):
   139	        # Sidecar-less envelope: the execution view is derived by compiling the
   140	        # IR (compile("api") is a function, not stored data). Only a graph the
     1	You are a precise evaluator for ComfyUI workflow edits. A model was asked
     2	to perform an edit but refused and left the workflow graph unchanged, citing
     3	a reason. You must determine whether that refusal is GROUNDED (the model
     4	could not honestly satisfy the intent) or fabricated/unsupported (the model
     5	dodged an edit it could have made).
     6
     7	Evaluate the refusal against exactly four binary criteria:
     8
     9	**R1 — supported_blocker**: The refusal cites a real, supported blocker
    10	rather than a made-up constraint. For example, a `requires_custom_nodes`
    11	refusal is supported only when the node class the edit would need is
    12	genuinely absent from the installed schema; a `clarify` refusal is supported
    13	only when the request has a genuine ambiguity that prevents a correct edit.
    14
    15	**R2 — no_representable_edit**: No representable edit to the given workflow
    16	could satisfy the intent, so refusing was the only honest option. If a
    17	parameter change, node replacement, or node addition on the existing graph
    18	could have satisfied the request, this criterion fails.
    19
    20	**R3 — specific_next_action**: The refusal states a concrete next action that
    21	would unblock the edit (for example, installing a named custom node, or
    22	answering a named clarifying question). A refusal that just says "cannot do
    23	this" without any path forward fails this criterion.
    24
    25	**R4 — no_fabricated_inability**: The refusal does not falsely claim an
    26	inability. Claiming a node class is unavailable when the schema contains it,
    27	or claiming the request is ambiguous when it is concrete, is a fabricated
    28	inability and fails this criterion.
    29
    30	Respond with a JSON object and nothing else:
    31	{
    32	  "pass_": true | false,
    33	  "criteria": {
    34	    "supported_blocker": true | false,
    35	    "no_representable_edit": true | false,
    36	    "specific_next_action": true | false,
    37	    "no_fabricated_inability": true | false
    38	  },
    39	  "rationale": "<one or two sentences citing the specific refusal evidence for any failing criterion>"
    40	}
    41
    42	`pass_` must be true if and only if all four criteria are true.
    43	Do not add any text before or after the JSON object.
    25
    26	def _scenario(path: Path) -> dict:
    27	    return json.loads(path.read_text(encoding="utf-8"))
    28
    29
    30	def test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios() -> None:
    31	    paths = discover_manifest_scenarios()
    32	    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    33	    entries = manifest["entries"]
    34
    35	    assert len(paths) == manifest["scenario_count"] == len(entries) == 100
    36	    assert len({entry["id"] for entry in entries}) == 100
    37	    assert len({entry["path"] for entry in entries}) == 100
    38	    assert all(entry["id"] == Path(entry["path"]).stem for entry in entries)
    39	    assert all(entry["inclusion_status"] == "included" for entry in entries)
    40	    assert {entry["revision_status"] for entry in entries} == {"matched", "revised"}
    41	    assert {entry["id"] for entry in entries if entry["revision_status"] == "revised"} == CORRECTED_EDITS
    42
    43	    source_entries = [entry for entry in entries if entry["source_workflow"]]
    44	    assert len(source_entries) == 98
    45	    for entry in source_entries:
    46	        source = entry["source_workflow"]
    47	        source_path = Path(__file__).parents[1] / source["path"]
    48	        assert source_path.is_file()
    49	        assert source["sha256"] == sha256_file(source_path)
    50
    51
    52	def test_d13_no_change_reconciliation_and_rubric_contract() -> None:
    53	    scenarios = [_scenario(path) for path in discover_manifest_scenarios()]
    54	    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
    55	    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
    56	    corrected = [s for s in scenarios if s["id"] in CORRECTED_EDITS]
    57
    58	    assert len(semantic) == 35
    59	    assert len(controls) == 2
    60	    assert len(corrected) == 3
    61	    assert len(semantic) + len(controls) + len(corrected) == 40
    62	    assert {s["_tags"]["query_type"] for s in semantic} == {"research", "explain", "diagnose"}
    63	    assert all(s["assessment"]["expect_graph_changed"] is False for s in semantic + controls)
    64	    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
    65	    assert all(s["assessment"]["expect_graph_changed"] is True and s["apply"] is True for s in corrected)
    66
    67	    for scenario in semantic:
    68	        rubric = scenario["answer_rubric"]
    69	        assert rubric["judge"] == "semantic_answer"
    70	        assert rubric["workflow_path"] == scenario["workflow_path"]
    71	        assert rubric["required_node_evidence"]
    72	        assert len(rubric["expected_criteria"]) >= 4
    73	        assert "grounded" in rubric["pass_condition"]
    74	        assert len(rubric["fail_conditions"]) == 5
    75
    76	    desired_edits = [s for s in scenarios if s.get("desired")]
    77	    assert desired_edits
    78	    for scenario in desired_edits:
    79	        assessment = scenario["assessment"]
    80	        # A desired edit is an active acceptance rubric: it must expect a graph
    81	        # change and must never be configured so a refusal can skip the judge.
    82	        assert assessment["expect_graph_changed"] is True, scenario["id"]
    83	        # skip_intent_judge would let an allowlisted refusal bypass ALL judging
    84	        # (both the edit-intent judge and the grounded-refusal gate) — invalid.
    85	        assert assessment.get("skip_intent_judge") is not True, (
    86	            f"{scenario['id']}: skip_intent_judge would let a refusal skip the judge"
    87	        )
    88
    89
    90	def test_runner_rejects_unmanifested_descriptor_before_execution(tmp_path: Path) -> None:
    91	    scenarios_dir = tmp_path / "scenarios"
    92	    scenarios_dir.mkdir()
    93	    (scenarios_dir / "one.json").write_text(
    94	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
    95	    )
    96	    write_manifest(scenarios_dir)
    97	    (scenarios_dir / "stray.json").write_text(
    98	        json.dumps({"id": "stray", "query": "stray"}), encoding="utf-8"
    99	    )
   100	    with pytest.raises(ScenarioManifestError, match="unmanifested"):
   101	        run_tag("stray-preflight", scenarios_dir=scenarios_dir, output_base=tmp_path / "out")
   102
   103
   104	def test_manifest_discovery_rejects_changed_or_missing_descriptor(tmp_path: Path) -> None:
   105	    scenarios_dir = tmp_path / "scenarios"
   106	    scenarios_dir.mkdir()
   107	    descriptor = scenarios_dir / "one.json"
   108	    descriptor.write_text(json.dumps({"id": "one", "query": "one"}), encoding="utf-8")
   109	    write_manifest(scenarios_dir)
   110	    descriptor.write_text(json.dumps({"id": "one", "query": "changed"}), encoding="utf-8")
   111	    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
   112	        discover_manifest_scenarios(scenarios_dir)
   113
   114	    descriptor.unlink()
   115	    with pytest.raises(ScenarioManifestError, match="missing"):
   116	        discover_manifest_scenarios(scenarios_dir)
   117
   118
   119	def test_manifest_discovery_rejects_duplicate_id_and_path(tmp_path: Path) -> None:
   120	    scenarios_dir = tmp_path / "scenarios"
   121	    scenarios_dir.mkdir()
   122	    (scenarios_dir / "one.json").write_text(
   123	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
   124	    )
   125	    manifest_path = write_manifest(scenarios_dir)
   126	    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   127	    manifest["entries"].append(dict(manifest["entries"][0]))
   128	    manifest["scenario_count"] = 2
   129	    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
   130	    with pytest.raises(ScenarioManifestError, match="duplicate scenario id"):
   131	        discover_manifest_scenarios(scenarios_dir)
   132
   133
   134	def test_manifest_discovery_rejects_duplicate_path_with_distinct_id(tmp_path: Path) -> None:
   135	    scenarios_dir = tmp_path / "scenarios"
   136	    scenarios_dir.mkdir()
   137	    (scenarios_dir / "one.json").write_text(
   138	        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
   139	    )
   140	    manifest_path = write_manifest(scenarios_dir)
   141	    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
   142	    duplicate = dict(manifest["entries"][0])
   143	    duplicate["id"] = "two"
   144	    manifest["entries"].append(duplicate)
   145	    manifest["scenario_count"] = 2
   146	    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
   147	    with pytest.raises(ScenarioManifestError, match="duplicate scenario path"):
   148	        discover_manifest_scenarios(scenarios_dir)

exec
/bin/zsh -lc "nl -ba .oracle/briefs/batch-D13-rework.md | sed -n '1,180p'; nl -ba .oracle/briefs/batch-D13.md | sed -n '1,180p'; git show b39f0c91:.oracle/checkins/batch-D13.md 2>/dev/null | tail -120" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
     1	# MEGADO D13 REWORK (oracle finding 5) — desired-edit refusal judge bypass
     2
     3	Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. D13 is in the tree at `b39f0c91` — fix on top, do not revert.
     4
     5	## The issue (D13 oracle FAIL, finding 5)
     6
     7	Three retained `desired` edits can pass via an unjudged, ungrounded refusal:
     8
     9	- `tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:8-18`
    10	- `tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:8-17`
    11	- `tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json:8-18`
    12
    13	Mechanism: `tests/live_agentic_harness/assessor.py:641-646` accepts the outcome label (allowlisted safe refusal, e.g. `clarify`/`requires_custom_nodes`), after which `:812-817` SKIPS the `judge_edit_intent()` call for the scenario. No evidence establishes the refusal is grounded. The regression at `tests/test_live_agentic_harness_guard_contract.py:288-332` explicitly permits this path with only prose and failed edit gates.
    14
    15	## What to change
    16
    17	1. **`assessor.py:641-646` + `:812-817`**: a `desired` scenario must NOT bypass all judging merely through an allowlisted refusal label. Either:
    18	   - (a) require an ACTIVE grounded-refusal judge for those scenarios (judge must run and confirm the refusal is grounded: supported blocker, no representable edit, specific next action, no fabricated inability), failing closed when the judge is unavailable; or
    19	   - (b) remove the refusal bypass for `desired` scenarios entirely.
    20	   Pick the option that keeps genuine grounded refusals passable but makes fabricated/unsupported refusals fail. `graph_unchanged=false` + refusal label + no grounded judge verdict must fail closed.
    21	2. **`tests/test_live_agentic_harness_guard_contract.py:288-332`**: add coverage proving an unsupported or fabricated `clarify`/`requires_custom_nodes` refusal cannot pass (for a desired edit).
    22	3. **`tests/test_live_agentic_harness_corpus_manifest.py:76-79`**: extend the desired-edit corpus assertion to detect judge-bypassing refusal configurations (any desired scenario whose configuration would let a refusal skip the judge must fail validation).
    23
    24	## Verification (run, retain output)
    25
    26	```bash
    27	.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_harness_runner_persistence.py
    28	```
    29
    30	Expected exit 0. The three scenarios' configurations must still be manifest-valid (they stay desired edits; the judge path now gates refusals).
    31
    32	## Report
    33	Return: exact changes (files + line refs), which option you picked, fixture names, pytest output. Do NOT commit.
     1	# MEGADO BATCH D13 [HARD] — Corpus integrity, satisfiability, and semantic rubrics
     2
     3	Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — you are the executor (GPT-5.6 Sol, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only. `external_workflows/` is symlinked into the worktree (2827 corpus JSONs).
     4
     5	## Context
     6	The 100-scenario corpus at tests/live_agentic_harness/scenarios/ has integrity issues: 40 scenarios are `expect_graph_changed:false`, of which 3 are MISLABELED EDITS (query_type:edit, apply:true, a desired block, but expect_graph_changed:false) that can no-op and still pass; the remaining 37 query non-edits have NO answer-quality judge/rubric; 2 are health controls. The runner discovers scenarios by unrestricted glob — stray files can silently change the lane. The final B09 measurement needs a stable, hashed scenario manifest and source-workflow hashes.
     7
     8	## Tasks (from .oracle/tasklist.md D13)
     9
    10	1. **Check in an authoritative manifest** for the current 100 scenarios: stable ID, path, descriptor SHA-256, inclusion status, source-workflow ID and hash where applicable.
    11	2. **Make runner discovery consume the manifest** rather than an unrestricted glob. Reject missing, changed, duplicate, or unmanifested files.
    12	3. **Audit scenario/query/schema/operation/rubric coherence**, prioritizing all anomalous or revised cases.
    13	4. **Correct the three mislabeled edits** (query_type:edit, apply:true, desired block, expect_graph_changed:false):
    14	   - `video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json`
    15	   - `video-image-to-video-conversion-with-moonvalley-d7853c.json`
    16	   - `multi-3d-preview-and-image-output-workflow-d93baf.json`
    17	   Set edit/change expectations truthfully if satisfiable; otherwise rewrite or replace while preserving coverage; NEVER let them pass as no-ops.
    18	5. **Classify the remaining 37 query non-edits**: 35 semantic product scenarios get explicit expected-answer criteria (rubric: grounded, relevant, correct → pass; hallucinated/wrong/irrelevant/vacuous/empty-but-valid → fail); `live-graph-explanation-smoke` and `speed-distillation-research` become explicit health controls.
    19	6. **Ensure every retained edit `desired` block feeds an active judge** (the edit-intent judge must consume the desired block).
    20	7. **Record every rewrite/replacement** and preserve matched-versus-revised reporting (e.g. a REVISIONS.md or manifest field).
    21	8. **Provision + hash source workflows**: hash the source-workflow JSONs from external_workflows/corpus/ referenced by the scenarios; resolve every workflow_path.
    22
    23	## Verification (run, retain output)
    24	- The manifest selects exactly 100 unique ID/stem-matched scenarios; runner rejects a stray/unmanifested file.
    25	- The 40 no-change-routed cases reconcile as 35 semantic non-edits + 2 health controls + 3 corrected edits.
    26	- The 3 corrected edits cannot pass without a judged graph change or legitimate grounded refusal.
    27	- All 35 semantic non-edits have evidence-backed rubrics.
    28	- Source-workflow hashes resolve (no missing workflow_path).
    29	- Run: `.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py` (expect green; the rerunfailures plugin binds a socket and cannot run here).
    30
    31	## Report
    32	Return: manifest location + shape, runner discovery change, the 3 corrected scenarios (before/after), the rubric format for the 35, the health-control marking, rewrite/replacement record, source-hash coverage, pytest output. Do NOT commit.

exec
/bin/zsh -lc "rg -n \"implementation_payload|model_request\" tests/live_agentic_harness/assessor.py | head -60; nl -ba tests/live_agentic_harness/assessor.py | sed -n '330,470p'; nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '120,330p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
358:def _model_request_text(output_dir: Path) -> str | None:
359:    """Return copied model_request.json text when the headless run produced it."""
360:    path = output_dir / "model_request.json"
369:def _assess_model_request_artifact(
377:    * ``assessment.max_model_request_bytes`` — fail when copied
378:      ``model_request.json`` is larger than this many bytes.
379:    * ``assessment.forbid_model_request_substrings`` — fail when any listed
380:      substring appears in copied ``model_request.json``.
383:    max_bytes = assessment.get("max_model_request_bytes")
384:    forbidden_raw = assessment.get("forbid_model_request_substrings")
390:    path = output_dir / "model_request.json"
394:                "check": "model_request_artifact",
396:                "detail": "Scenario requires model_request.json checks, but the artifact is missing.",
406:                    "check": "model_request_size",
409:                        f"model_request.json is {actual_size} bytes; "
416:        text = _model_request_text(output_dir)
420:                    "check": "model_request_artifact",
422:                    "detail": "model_request.json could not be read.",
439:                            "check": "model_request_forbidden_substring",
442:                                "model_request.json contains forbidden substring "
952:    issues.extend(_assess_model_request_artifact(output_dir, scenario))
   330	    if isinstance(raw, str):
   331	        return {raw}
   332	    if isinstance(raw, list):
   333	        return {item for item in raw if isinstance(item, str)}
   334	    return set()
   335
   336
   337	def _assessment_config(scenario: Mapping[str, Any] | None) -> Mapping[str, Any]:
   338	    """Return the scenario assessment config, if present."""
   339	    if scenario is None:
   340	        return {}
   341	    assessment = scenario.get("assessment")
   342	    return assessment if isinstance(assessment, Mapping) else {}
   343
   344
   345	def _effective_edit_targets(scenario: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
   346	    """Return explicit effective-value targets required by the scenario."""
   347	    assessment = _assessment_config(scenario)
   348	    raw = assessment.get("effective_edit_targets")
   349	    if raw is None:
   350	        raw = assessment.get("effective_targets")
   351	    if isinstance(raw, Mapping):
   352	        return [raw]
   353	    if isinstance(raw, list):
   354	        return [item for item in raw if isinstance(item, Mapping)]
   355	    return []
   356
   357
   358	def _model_request_text(output_dir: Path) -> str | None:
   359	    """Return copied model_request.json text when the headless run produced it."""
   360	    path = output_dir / "model_request.json"
   361	    if not path.is_file():
   362	        return None
   363	    try:
   364	        return path.read_text(encoding="utf-8")
   365	    except OSError:
   366	        return None
   367
   368
   369	def _assess_model_request_artifact(
   370	    output_dir: Path,
   371	    scenario: Mapping[str, Any] | None,
   372	) -> list[dict[str, Any]]:
   373	    """Apply optional prompt-size/content guardrails from scenario assessment.
   374
   375	    Supported scenario fields:
   376
   377	    * ``assessment.max_model_request_bytes`` — fail when copied
   378	      ``model_request.json`` is larger than this many bytes.
   379	    * ``assessment.forbid_model_request_substrings`` — fail when any listed
   380	      substring appears in copied ``model_request.json``.
   381	    """
   382	    assessment = _assessment_config(scenario)
   383	    max_bytes = assessment.get("max_model_request_bytes")
   384	    forbidden_raw = assessment.get("forbid_model_request_substrings")
   385	    has_size_check = isinstance(max_bytes, int) and not isinstance(max_bytes, bool)
   386	    forbidden = [item for item in forbidden_raw or [] if isinstance(item, str)]
   387	    if not has_size_check and not forbidden:
   388	        return []
   389
   390	    path = output_dir / "model_request.json"
   391	    if not path.is_file():
   392	        return [
   393	            {
   394	                "check": "model_request_artifact",
   395	                "severity": "error",
   396	                "detail": "Scenario requires model_request.json checks, but the artifact is missing.",
   397	            }
   398	        ]
   399
   400	    issues: list[dict[str, Any]] = []
   401	    if has_size_check:
   402	        actual_size = path.stat().st_size
   403	        if actual_size > max_bytes:
   404	            issues.append(
   405	                {
   406	                    "check": "model_request_size",
   407	                    "severity": "error",
   408	                    "detail": (
   409	                        f"model_request.json is {actual_size} bytes; "
   410	                        f"limit is {max_bytes} bytes."
   411	                    ),
   412	                }
   413	            )
   414
   415	    if forbidden:
   416	        text = _model_request_text(output_dir)
   417	        if text is None:
   418	            issues.append(
   419	                {
   420	                    "check": "model_request_artifact",
   421	                    "severity": "error",
   422	                    "detail": "model_request.json could not be read.",
   423	                }
   424	            )
   425	        else:
   426	            decoded: Any = None
   427	            try:
   428	                decoded = json.loads(text)
   429	            except json.JSONDecodeError:
   430	                decoded = None
   431	            for substring in forbidden:
   432	                found_in_decoded_string = any(
   433	                    isinstance(node, str) and substring in node
   434	                    for node in _walk(decoded)
   435	                )
   436	                if substring in text or found_in_decoded_string:
   437	                    issues.append(
   438	                        {
   439	                            "check": "model_request_forbidden_substring",
   440	                            "severity": "error",
   441	                            "detail": (
   442	                                "model_request.json contains forbidden substring "
   443	                                f"{substring!r}."
   444	                            ),
   445	                        }
   446	                    )
   447	    return issues
   448
   449
   450	def _ui_artifact_path(
   451	    output_dir: Path,
   452	    response: Mapping[str, Any],
   453	    artifact_name: str,
   454	    fallback_name: str,
   455	) -> Path:
   456	    artifacts = response.get("artifacts")
   457	    if isinstance(artifacts, Mapping) and isinstance(artifacts.get(artifact_name), str):
   458	        return Path(artifacts[artifact_name])
   459	    return output_dir / fallback_name
   460
   461
   462	def _load_ui_artifact(
   463	    output_dir: Path,
   464	    response: Mapping[str, Any],
   465	    artifact_name: str,
   466	    fallback_name: str,
   467	) -> Mapping[str, Any] | None:
   468	    path = _ui_artifact_path(output_dir, response, artifact_name, fallback_name)
   469	    loaded = _load_json(path)
   470	    return loaded if isinstance(loaded, Mapping) else None
   120	def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
   121	    path = output_dir / "implementation_payload.json"
   122	    if not path.is_file():
   123	        return None
   124	    try:
   125	        data = json.loads(path.read_text(encoding="utf-8"))
   126	    except (OSError, json.JSONDecodeError):
   127	        return None
   128	    return data if isinstance(data, dict) else None
   129
   130
   131	def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
   132	    if not isinstance(payload, Mapping):
   133	        return None
   134	    graph = payload.get("graph")
   135	    if not isinstance(graph, Mapping):
   136	        return None
   137	    compiled_api = graph.get("compiled_api")
   138	    if not isinstance(compiled_api, Mapping):
   139	        # Sidecar-less envelope: the execution view is derived by compiling the
   140	        # IR (compile("api") is a function, not stored data). Only a graph the
   141	        # decoder accepts yields context; anything else stays context-free.
   142	        try:
   143	            from vibecomfy.ingest.normalize import convert_to_vibe_format
   144
   145	            compiled_api = convert_to_vibe_format(dict(graph)).compile("api")
   146	        except Exception:
   147	            return None
   148	    context: dict[str, Any] = {"compiled_api": compiled_api}
   149	    metadata = graph.get("metadata")
   150	    if isinstance(metadata, Mapping):
   151	        widget_index = metadata.get("widget_index") or metadata.get("object_info_index")
   152	        if isinstance(widget_index, Mapping):
   153	            context["widget_index"] = widget_index
   154	    return context
   155
   156
   157	def _ui_nodes_by_id(ui: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
   158	    nodes = ui.get("nodes")
   159	    if not isinstance(nodes, list):
   160	        return {}
   161	    result: dict[str, Mapping[str, Any]] = {}
   162	    for node in nodes:
   163	        if not isinstance(node, Mapping):
   164	            continue
   165	        node_id = node.get("id")
   166	        if node_id is not None:
   167	            result[str(node_id)] = node
   168	    return result
   169
   170
   171	def _ui_links_by_id(ui: Mapping[str, Any]) -> dict[Any, Any]:
   172	    links = ui.get("links")
   173	    if not isinstance(links, list):
   174	        return {}
   175	    result: dict[Any, Any] = {}
   176	    for link in links:
   177	        if isinstance(link, list) and link:
   178	            result[link[0]] = link
   179	        elif isinstance(link, Mapping) and "id" in link:
   180	            result[link.get("id")] = link
   181	    return result
   182
   183
   184	def _link_source(link: Any) -> dict[str, Any] | None:
   185	    if isinstance(link, list) and len(link) >= 3:
   186	        return {"node_id": str(link[1]), "slot": link[2]}
   187	    if isinstance(link, Mapping):
   188	        source_id = link.get("origin_id", link.get("source_id", link.get("from_node")))
   189	        source_slot = link.get("origin_slot", link.get("source_slot", link.get("from_slot")))
   190	        if source_id is not None:
   191	            return {"node_id": str(source_id), "slot": source_slot}
   192	    return None
   193
   194
   195	def _linked_inputs_for_node(
   196	    node: Mapping[str, Any],
   197	    *,
   198	    links_by_id: Mapping[Any, Any],
   199	    nodes_by_id: Mapping[str, Mapping[str, Any]],
   200	) -> list[dict[str, Any]]:
   201	    inputs = node.get("inputs")
   202	    if not isinstance(inputs, list):
   203	        return []
   204	    linked_inputs: list[dict[str, Any]] = []
   205	    for index, input_item in enumerate(inputs):
   206	        if not isinstance(input_item, Mapping):
   207	            continue
   208	        link_id = input_item.get("link")
   209	        if link_id is None:
   210	            continue
   211	        source = _link_source(links_by_id.get(link_id))
   212	        source_node = nodes_by_id.get(source["node_id"]) if source is not None else None
   213	        linked_inputs.append(
   214	            {
   215	                "input_index": index,
   216	                "name": input_item.get("name"),
   217	                "type": input_item.get("type"),
   218	                "link": link_id,
   219	                "source": {
   220	                    **(source or {}),
   221	                    "class_type": source_node.get("type") if isinstance(source_node, Mapping) else None,
   222	                },
   223	            }
   224	        )
   225	    return linked_inputs
   226
   227
   228	def _static_widget_dataflow_context(
   229	    pre_ir: Mapping[str, Any],
   230	    post_ir: Mapping[str, Any],
   231	) -> dict[str, Any] | None:
   232	    pre_nodes = _ui_nodes_by_id(pre_ir)
   233	    post_nodes = _ui_nodes_by_id(post_ir)
   234	    pre_links = _ui_links_by_id(pre_ir)
   235	    post_links = _ui_links_by_id(post_ir)
   236	    widget_deltas: list[dict[str, Any]] = []
   237	    static_removals_with_preserved_dynamic_inputs: list[dict[str, Any]] = []
   238
   239	    for node_id, pre_node in sorted(pre_nodes.items()):
   240	        post_node = post_nodes.get(node_id)
   241	        if post_node is None:
   242	            continue
   243	        pre_widgets = pre_node.get("widgets_values")
   244	        post_widgets = post_node.get("widgets_values")
   245	        if not isinstance(pre_widgets, list) or not isinstance(post_widgets, list):
   246	            continue
   247	        linked_inputs_pre = _linked_inputs_for_node(
   248	            pre_node,
   249	            links_by_id=pre_links,
   250	            nodes_by_id=pre_nodes,
   251	        )
   252	        linked_inputs_post = _linked_inputs_for_node(
   253	            post_node,
   254	            links_by_id=post_links,
   255	            nodes_by_id=post_nodes,
   256	        )
   257	        linked_signature_pre = {
   258	            (item.get("name"), item.get("link"), item.get("source", {}).get("node_id"))
   259	            for item in linked_inputs_pre
   260	        }
   261	        linked_signature_post = {
   262	            (item.get("name"), item.get("link"), item.get("source", {}).get("node_id"))
   263	            for item in linked_inputs_post
   264	        }
   265	        preserved_dynamic_inputs = bool(linked_signature_pre & linked_signature_post)
   266	        for index in range(max(len(pre_widgets), len(post_widgets))):
   267	            old = pre_widgets[index] if index < len(pre_widgets) else None
   268	            new = post_widgets[index] if index < len(post_widgets) else None
   269	            if old == new:
   270	                continue
   271	            delta = {
   272	                "node_id": node_id,
   273	                "class_type": post_node.get("type") or pre_node.get("type"),
   274	                "widget_index": index,
   275	                "old": old,
   276	                "new": new,
   277	                "kind": "static_widget_delta",
   278	                "linked_inputs_pre": linked_inputs_pre,
   279	                "linked_inputs_post": linked_inputs_post,
   280	                "preserved_dynamic_inputs": preserved_dynamic_inputs,
   281	            }
   282	            widget_deltas.append(delta)
   283	            if isinstance(old, str) and old.strip() and (new is None or (isinstance(new, str) and not new.strip())):
   284	                if preserved_dynamic_inputs:
   285	                    static_removals_with_preserved_dynamic_inputs.append(delta)
   286
   287	    if not widget_deltas:
   288	        return None
   289	    return {
   290	        "widget_deltas": widget_deltas,
   291	        "static_widget_removals_with_preserved_dynamic_inputs": static_removals_with_preserved_dynamic_inputs,
   292	        "note": (
   293	            "widgets_values are static node configuration. Linked inputs are dynamic dataflow. "
   294	            "A static text widget removal can be correct when linked dynamic inputs remain connected."
   295	        ),
   296	    }
   297
   298
   299	def judge_edit_intent(
   300	    output_dir: Path | str,
   301	    scenario: Mapping[str, Any],
   302	    *,
   303	    route: str = "deepseek",
   304	    model: str = "deepseek-v4-pro",
   305	) -> dict[str, Any]:
   306	    """Run the DeepSeek text judge on the candidate edit in *output_dir*.
   307
   308	    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
   309	    If required artifacts are missing or the model call fails, ``pass_`` is None
   310	    and ``error`` describes why.
   311	    """
   312	    output_dir = Path(output_dir)
   313	    query = str(scenario.get("query", "")).strip()
   314	    if not query:
   315	        return {"pass_": None, "error": "scenario has no query"}
   316
   317	    # The durable turn writes UI artifacts under out/editor_sessions; the response
   318	    # JSON carries the exact paths in its artifacts block.
   319	    response_path = output_dir / "response.json"
   320	    original_ui_path: Path | None = None
   321	    candidate_ui_path: Path | None = None
   322	    if response_path.is_file():
   323	        try:
   324	            response = json.loads(response_path.read_text(encoding="utf-8"))
   325	            artifacts = response.get("artifacts", {}) or {}
   326	            if isinstance(artifacts.get("original_ui"), str):
   327	                original_ui_path = Path(artifacts["original_ui"])
   328	            if isinstance(artifacts.get("candidate_ui"), str):
   329	                candidate_ui_path = Path(artifacts["candidate_ui"])
   330	        except (OSError, json.JSONDecodeError):

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from tests.live_agentic_harness.intent_judge import _parse_refusal_verdict; import json; cases=[{\"pass_\":True,\"criteria\":{\"supported_blocker\":False,\"no_representable_edit\":False,\"specific_next_action\":False,\"no_fabricated_inability\":False},\"rationale\":\"not grounded\"},{\"pass_\":\"false\",\"criteria\":{\"supported_blocker\":\"false\",\"no_representable_edit\":\"false\",\"specific_next_action\":\"false\",\"no_fabricated_inability\":\"false\"},\"rationale\":\"malformed\"}]; [print(_parse_refusal_verdict(json.dumps(x))) for x in cases]'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 2600ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
Could not locate ComfyUI root (no server.py + nodes.py found).
Could not register VibeComfy agent routes (No module named 'comfy'); the ComfyUI server may not be available. POST /vibecomfy/agent-edit and /vibecomfy/agent/status will not be served.
{'pass_': True, 'criteria': {'supported_blocker': False, 'no_representable_edit': False, 'specific_next_action': False, 'no_fabricated_inability': False}, 'rationale': 'not grounded'}
{'pass_': True, 'criteria': {'supported_blocker': True, 'no_representable_edit': True, 'specific_next_action': True, 'no_fabricated_inability': True}, 'rationale': 'malformed'}

exec
/bin/zsh -lc "rg -n \"parse_refusal|criteria.*supported_blocker|pass_.*criteria|inconsistent|malformed.*refusal\" tests tests/live_agentic_harness --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 47ms:
tests/live_agentic_harness/intent_judge.py:36:        '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
tests/live_agentic_harness/intent_judge.py:39:        "`pass_` must be true if and only if all four criteria are true."
tests/live_agentic_harness/intent_judge.py:66:        '{"pass_": true | false, "criteria": {"supported_blocker": true | false, '
tests/live_agentic_harness/intent_judge.py:69:        "`pass_` must be true if and only if all four criteria are true."
tests/live_agentic_harness/intent_judge.py:103:def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
tests/live_agentic_harness/intent_judge.py:108:        "supported_blocker": bool(criteria.get("supported_blocker")),
tests/live_agentic_harness/intent_judge.py:308:    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
tests/live_agentic_harness/intent_judge.py:444:    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
tests/live_agentic_harness/intent_judge.py:515:        verdict = _parse_refusal_verdict(raw)
tests/intent/test_static_lowering.py:1008:def test_lower_workflow_fails_atomically_on_inconsistent_seed_source_values() -> None:
tests/intent/test_static_lowering.py:1025:    assert [diag.code for diag in result.diagnostics] == ["inconsistent_seed_source_values"]
tests/intent/test_static_lowering.py:1029:def test_lower_workflow_fails_atomically_on_inconsistent_prompt_source_values() -> None:
tests/intent/test_static_lowering.py:1044:    assert [diag.code for diag in result.diagnostics] == ["inconsistent_text_source_values"]
tests/intent/test_judge_text_offline.py:106:def test_judge_text_pass_iff_all_criteria_true():
tests/intent/test_judge_text_offline.py:107:    """pass_ must be the AND of all criteria, regardless of the raw JSON field."""
tests/intent/test_panel_aggregation.py:23:    return JudgeVerdict(pass_=pass_, criteria=criteria, rationale="stub")
tests/intent/smoke/test_judge_calibration.py:56:        f"  text: pass_={text_v.pass_}, criteria={text_v.criteria}, rationale={text_v.rationale!r}\n"
tests/intent/smoke/test_judge_calibration.py:57:        f"  vision: pass_={vision_v.pass_}, criteria={vision_v.criteria}"
tests/test_emitter_object_info_validation.py:329:    internally inconsistent.
tests/test_emitter_object_info_validation.py:457:    #     internally inconsistent cache that Layer 2 MUST catch. ---

exec
/bin/zsh -lc "nl -ba tests/intent/test_judge_text_offline.py | sed -n '80,125p'; rg -n \"def .*parse.*verdict|all\\(.*criteria|pass_.*all\" vibecomfy/intent -g '*.py' | head -40" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 58ms:
vibecomfy/intent/judge.py:95:    pass_ = all(criteria.values())
vibecomfy/intent/judge.py:176:    pass_ = all(criteria.values())

exec
/bin/zsh -lc 'for f in tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json; do echo FILE:$f; nl -ba "$f" | sed -n '"'1,24p'; done" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
FILE:tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json
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
FILE:tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json
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
FILE:tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json
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

exec
/bin/zsh -lc 'rg -n "implementation_payload.json|implementation_payload" tests/live_agentic_harness vibecomfy | head -100' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 9ms:
tests/live_agentic_harness/failure_analysis.py:121:        "implementation_payload.json",
tests/live_agentic_harness/intent_judge.py:120:def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
tests/live_agentic_harness/intent_judge.py:121:    path = output_dir / "implementation_payload.json"
tests/live_agentic_harness/intent_judge.py:352:    implementation_payload = _load_implementation_payload(output_dir)
tests/live_agentic_harness/intent_judge.py:353:    schema_context = _schema_context_from_payload(implementation_payload) or {}
tests/live_agentic_harness/intent_judge.py:477:    implementation_payload = _load_implementation_payload(output_dir)
tests/live_agentic_harness/intent_judge.py:478:    schema_context = _schema_context_from_payload(implementation_payload) or {}
vibecomfy/demo_factory/case.py:94:    implementation_payload = _read_attempt_json(
vibecomfy/demo_factory/case.py:96:        "implementation_payload.json",
vibecomfy/demo_factory/case.py:149:    payloads = (request_payload, implementation_payload)
vibecomfy/demo_factory/fixer.py:86:    "implementation_payload.json",
vibecomfy/demo_factory/fixer.py:107:    ``implementation_payload.json`` holds the INPUT graph, not the repair, so it
vibecomfy/agent/artifacts.py:232:def _implementation_payload_from_report(
vibecomfy/agent/artifacts.py:451:            implementation_payload = _implementation_payload_from_report(
vibecomfy/agent/artifacts.py:457:                output_dir / "implementation_payload.json",
vibecomfy/agent/artifacts.py:458:                _redact(implementation_payload),
vibecomfy/agent/artifacts.py:460:            _append_manifest(manifest, "implementation_payload.json")

exec
/bin/zsh -lc "nl -ba vibecomfy/agent/artifacts.py | sed -n '420,470p'; nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '340,405p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 131ms:
   420	        "dry_run": bool(request.get("dry_run", False)),
   421	        "apply": bool(request.get("apply", False)),
   422	        "network": bool(request.get("network", True)),
   423	        "readiness": dict(readiness) if readiness else {},
   424	    }
   425	    _safe_write(output_dir / "flow_metadata.json", _redact(flow_metadata))
   426	    _append_manifest(manifest, "flow_metadata.json")
   427
   428	    report = _executor_report(result)
   429	    model_attempts = report.get("model_attempts")
   430	    if isinstance(model_attempts, (list, tuple)) and model_attempts:
   431	        _safe_write(
   432	            output_dir / "model_attempts.json",
   433	            {"attempts": _redact(model_attempts)},
   434	        )
   435	        _append_manifest(manifest, "model_attempts.json")
   436	    classification = report.get("plan")
   437	    if isinstance(classification, Mapping):
   438	        classification_payload = _redact(classification)
   439	        _safe_write(output_dir / "classification.json", classification_payload)
   440	        _append_manifest(manifest, "classification.json")
   441
   442	        research = report.get("research")
   443	        research_payload: dict[str, Any] | None = None
   444	        if isinstance(research, Mapping):
   445	            research_payload = _redact(research)
   446	            _safe_write(output_dir / "research.json", research_payload)
   447	            _append_manifest(manifest, "research.json")
   448
   449	        implementation = report.get("implementation")
   450	        if isinstance(implementation, Mapping):
   451	            implementation_payload = _implementation_payload_from_report(
   452	                request=request,
   453	                classification=classification_payload,
   454	                research=research_payload,
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
   340	        return {
   341	            "pass_": None,
   342	            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
   343	        }
   344
   345	    try:
   346	        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
   347	        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
   348	    except (OSError, json.JSONDecodeError) as exc:
   349	        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}
   350
   351	    system_prompt = _load_prompt()
   352	    implementation_payload = _load_implementation_payload(output_dir)
   353	    schema_context = _schema_context_from_payload(implementation_payload) or {}
   354	    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
   355	    if dataflow_context:
   356	        schema_context["dataflow_context"] = dataflow_context
   357	    if schema_context:
   358	        system_prompt = (
   359	            system_prompt.rstrip()
   360	            + "\n\n## Schema and widget evidence\n"
   361	            "When schema_context is provided, use it to map opaque widget_N fields "
   362	            "to semantic input names. Treat literal widget values as static node "
   363	            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
   364	            "widget's meaning from index order when compiled_api names are available. "
   365	            "If a static widget containing stale or fabricated text is removed while "
   366	            "the relevant linked dynamic input path remains connected, do not treat "
   367	            "that removal as deleting the dynamic dataflow."
   368	        )
   369	    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
   370	    # present, it grounds the judge on what a GOOD result achieves (the outcome +
   371	    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
   372	    # alternative approaches that reach the same outcome count as correct.
   373	    desired = scenario.get("desired")
   374	    if desired:
   375	        system_prompt = (
   376	            system_prompt.rstrip()
   377	            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
   378	            "The scenario author described what a GOOD result looks like below. Use it to "
   379	            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
   380	            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
   381	            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
   382	            "it fully wired/complete (no dangling or broken connections, existing pipeline "
   383	            "not broken), and is the approach a sensible one?\n\n"
   384	            f"Desired outcome: {desired.get('outcome', '')}\n"
   385	            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
   386	            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
   387	        )
   388	    payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
   389	    if desired:
   390	        payload["desired_outcome"] = desired
   391	    if schema_context:
   392	        payload["schema_context"] = schema_context
   393	    user_content = json.dumps(payload, indent=2)
   394
   395	    try:
   396	        response = run_model_turn(
   397	            "evaluate workflow edit against intent",
   398	            messages=[
   399	                {"role": "system", "content": system_prompt},
   400	                {"role": "user", "content": user_content},
   401	            ],
   402	            route=route,
   403	            model=model,
   404	            response_contract="json",
   405	        )

exec
/bin/zsh -lc "find external_workflows/corpus -maxdepth 1 -type f -name '*.json' | wc -l; git diff --name-only 0f015101..5aa73c53 | wc -l; git diff --numstat 0f015101..5aa73c53 | awk '{a+="'$1; d+=$2} END{print a,d}'"'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 104ms:
      57
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
13309 56

codex
D13 CHECKPOINT VERDICT: FAIL — Corpus integrity is sound, but malformed or contradictory judge verdicts can pass desired edits/refusals instead of failing closed.

1. **Manifest — PASS.** The manifest contains exactly 100 entries: 100 unique IDs, 100 unique paths, 100 ID/stem matches, all included; split is 63 edits, 35 semantic products, and 2 health controls. All 100 descriptor hashes and all 98 applicable source-workflow hashes independently matched. Spot-checks at entries [7](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.json:7), [640](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.json:640), and [1286](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.json:1286) matched byte-for-byte.

2. **Runner discovery — PASS.** `run_tag()` obtains paths exclusively through manifest discovery at [runner.py:44](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:44) and [runner.py:501](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:501). Missing, changed, duplicate ID/path, ID/stem mismatch, source mismatch, and unmanifested files are rejected at [scenario_manifest.py:161](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:161). Corresponding tests begin at [test_live_agentic_harness_corpus_manifest.py:90](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:90).

3. **Corrected edits — descriptor work PASS; gate affected by issue below.** All three now use satisfiable source-backed changes and require `apply: true` plus `expect_graph_changed: true`:

   - Seed `534667941392889 → 42`: [485ff2 scenario:3](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:3)
   - Moonvalley steps `100 → 80`: [d7853c scenario:3](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:3)
   - SaveGLB prefix `3d/ComfyUI → 3d/moge-top-down`: [d93baf scenario:3](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:3)

   Source inspection confirmed each old value and protected wiring. Explicit no-op regressions cover all three at [test_live_agentic_harness_guard_contract.py:553](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_guard_contract.py:553).

4. **Semantic rubrics/controls — PASS.** Exactly 35 scenarios have `semantic_answer` rubrics, four expected criteria, workflow paths, and nonempty exact node-class/UID evidence. Every required evidence token matched an actual source-workflow node. All share the required grounded/relevant/correct pass condition and five hallucinated/wrong/irrelevant/vacuous/empty fail conditions. The two controls carry `excluded_from_semantic_product_rates: true`; contract assertions are at [test_live_agentic_harness_corpus_manifest.py:52](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:52).

5. **Desired judges — FAIL.** All 42 retained `desired` scenarios expect a graph change and none sets `skip_intent_judge`; normal edits and allowlisted refusals reach active judges at [assessor.py:821](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:821), and unavailable judges become errors. However, the verdict parsers do not enforce their own “pass iff all criteria pass” contract; see blocking issue below.

6. **Revisions — PASS.** Base and head each contain the same 100 scenario files: none added, removed, renamed, or source-path changed. Exactly the three declared queries changed. The manifest records 97 matched and 3 revised, while [REVISIONS.md:7](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/REVISIONS.md:7) records before/after intent and retained coverage.

7. **Source workflows — PASS.** `external_workflows/` resolves to the provisioned corpus, with 2,827 JSONs directly under `corpus/`. All 98 referenced `workflow_path` values exist and all hashes match. Loader enforcement is at [scenario_manifest.py:211](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:211).

8. **Scope/whitespace — PASS with evidence discrepancy.** `git diff --check 0f015101..5aa73c53` is clean. Changed files are D13 scenarios, manifest/runner/judges/tests/docs, corpus provisioning ignore, and D13 oracle artifacts. The actual range is **57 files, +13,309/−56**, not the supplied 47 files, +1,210/−19; most excess is the committed 9,835-line D13 check-in transcript.

9. **Tests — PARTIALLY REPRODUCED.** The full slice could not initialize because the read-only sandbox has no writable temporary directory. With capture/cache disabled, runnable subsets passed:

   - Corpus integrity/rubric tests: **2 passed**
   - Structural runner plus two no-temp persistence tests: **10 passed**

   This limitation occurred before collection and is not itself a product failure.

## Blocking issue

- [intent_judge.py:86](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/intent_judge.py:86) and [intent_judge.py:103](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/intent_judge.py:103): both parsers trust the model’s `pass_` field and coerce arbitrary values with `bool()`. Consequently:

  - `pass_=true` with all criteria false remains a pass.
  - JSON strings such as `"false"` become Python `True`, including every criterion.

  I reproduced both cases directly. The assessor then accepts `pass_ is True` at [assessor.py:838](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:838) and [assessor.py:875](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:875). This can admit a fabricated refusal or incorrect desired edit despite failing criteria.

  **Rework:** require actual JSON booleans, reject missing/malformed criteria, and derive `pass_ = all(criteria.values())` rather than trusting the returned aggregate. Apply this to both edit and refusal parsers and add contradictory-boolean plus string-typed regressions. The canonical implementation already demonstrates the intended invariant at [vibecomfy/intent/judge.py:95](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/intent/judge.py:95) with regression coverage at [test_judge_text_offline.py:106](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/intent/test_judge_text_offline.py:106).
tokens used
162,564
D13 CHECKPOINT VERDICT: FAIL — Corpus integrity is sound, but malformed or contradictory judge verdicts can pass desired edits/refusals instead of failing closed.

1. **Manifest — PASS.** The manifest contains exactly 100 entries: 100 unique IDs, 100 unique paths, 100 ID/stem matches, all included; split is 63 edits, 35 semantic products, and 2 health controls. All 100 descriptor hashes and all 98 applicable source-workflow hashes independently matched. Spot-checks at entries [7](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.json:7), [640](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.json:640), and [1286](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.json:1286) matched byte-for-byte.

2. **Runner discovery — PASS.** `run_tag()` obtains paths exclusively through manifest discovery at [runner.py:44](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:44) and [runner.py:501](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:501). Missing, changed, duplicate ID/path, ID/stem mismatch, source mismatch, and unmanifested files are rejected at [scenario_manifest.py:161](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:161). Corresponding tests begin at [test_live_agentic_harness_corpus_manifest.py:90](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:90).

3. **Corrected edits — descriptor work PASS; gate affected by issue below.** All three now use satisfiable source-backed changes and require `apply: true` plus `expect_graph_changed: true`:

   - Seed `534667941392889 → 42`: [485ff2 scenario:3](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:3)
   - Moonvalley steps `100 → 80`: [d7853c scenario:3](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:3)
   - SaveGLB prefix `3d/ComfyUI → 3d/moge-top-down`: [d93baf scenario:3](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:3)

   Source inspection confirmed each old value and protected wiring. Explicit no-op regressions cover all three at [test_live_agentic_harness_guard_contract.py:553](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_guard_contract.py:553).

4. **Semantic rubrics/controls — PASS.** Exactly 35 scenarios have `semantic_answer` rubrics, four expected criteria, workflow paths, and nonempty exact node-class/UID evidence. Every required evidence token matched an actual source-workflow node. All share the required grounded/relevant/correct pass condition and five hallucinated/wrong/irrelevant/vacuous/empty fail conditions. The two controls carry `excluded_from_semantic_product_rates: true`; contract assertions are at [test_live_agentic_harness_corpus_manifest.py:52](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:52).

5. **Desired judges — FAIL.** All 42 retained `desired` scenarios expect a graph change and none sets `skip_intent_judge`; normal edits and allowlisted refusals reach active judges at [assessor.py:821](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:821), and unavailable judges become errors. However, the verdict parsers do not enforce their own “pass iff all criteria pass” contract; see blocking issue below.

6. **Revisions — PASS.** Base and head each contain the same 100 scenario files: none added, removed, renamed, or source-path changed. Exactly the three declared queries changed. The manifest records 97 matched and 3 revised, while [REVISIONS.md:7](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/REVISIONS.md:7) records before/after intent and retained coverage.

7. **Source workflows — PASS.** `external_workflows/` resolves to the provisioned corpus, with 2,827 JSONs directly under `corpus/`. All 98 referenced `workflow_path` values exist and all hashes match. Loader enforcement is at [scenario_manifest.py:211](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:211).

8. **Scope/whitespace — PASS with evidence discrepancy.** `git diff --check 0f015101..5aa73c53` is clean. Changed files are D13 scenarios, manifest/runner/judges/tests/docs, corpus provisioning ignore, and D13 oracle artifacts. The actual range is **57 files, +13,309/−56**, not the supplied 47 files, +1,210/−19; most excess is the committed 9,835-line D13 check-in transcript.

9. **Tests — PARTIALLY REPRODUCED.** The full slice could not initialize because the read-only sandbox has no writable temporary directory. With capture/cache disabled, runnable subsets passed:

   - Corpus integrity/rubric tests: **2 passed**
   - Structural runner plus two no-temp persistence tests: **10 passed**

   This limitation occurred before collection and is not itself a product failure.

## Blocking issue

- [intent_judge.py:86](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/intent_judge.py:86) and [intent_judge.py:103](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/intent_judge.py:103): both parsers trust the model’s `pass_` field and coerce arbitrary values with `bool()`. Consequently:

  - `pass_=true` with all criteria false remains a pass.
  - JSON strings such as `"false"` become Python `True`, including every criterion.

  I reproduced both cases directly. The assessor then accepts `pass_ is True` at [assessor.py:838](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:838) and [assessor.py:875](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:875). This can admit a fabricated refusal or incorrect desired edit despite failing criteria.

  **Rework:** require actual JSON booleans, reject missing/malformed criteria, and derive `pass_ = all(criteria.values())` rather than trusting the returned aggregate. Apply this to both edit and refusal parsers and add contradictory-boolean plus string-typed regressions. The canonical implementation already demonstrates the intended invariant at [vibecomfy/intent/judge.py:95](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/intent/judge.py:95) with regression coverage at [test_judge_text_offline.py:106](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/intent/test_judge_text_offline.py:106).
