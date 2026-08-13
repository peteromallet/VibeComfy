Reading additional input from stdin...
2026-08-13T13:37:22.460712Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:37:22.461979Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T13:37:22.461994Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffb57-7689-7882-9735-19e9b17fce72
--------
user
# MEGADO CHECKPOINT — Batch D13 (oracle: GPT-5.6 Sol, high reasoning, READ-ONLY)

You are the D13 oracle gate for the megado run on the VibeComfy agent-edit pipeline in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Read-only review; do NOT modify files.

## The batch

**D13 [HARD] — Corpus integrity, satisfiability, and semantic rubrics.** Tasks + acceptance from `.oracle/tasklist.md` (D13 section). Diff to review: `git diff 0f015101..ea421528` (B01 PASS SHA → D13 commit). Executor: GPT-5.6 Sol (workspace-write).

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
8. Scope: only D13 files; `git diff --check 0f015101..ea421528` clean.
9. Run the focused slice yourself where sandbox permits (`-p no:rerunfailures` if the socket plugin blocks).

## Output

First line: `D13 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
Then per-focus findings (1–9) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit MEGADO oracle checkpoint. I’ll follow its gate protocol, inspect the full D13 diff and acceptance criteria, then run only read-only validation/tests.
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
The skill allows a pure, non-delegating oracle review in a read-only sandbox, which matches this checkpoint; I won’t dispatch or mutate anything. I’m starting from the frozen D13 acceptance text and the exact two-commit delta, then I’ll independently verify corpus invariants and focused tests.
  → Read D13 acceptance criteria and inventory the exact commit delta
  • Audit manifest integrity, runner rejection paths, corrected edits, rubrics, judge behavior, revisions, and source hashes
  • Run diff hygiene and focused test slices permitted by the read-only sandbox
  • Issue binary D13 verdict with per-focus evidence and precise rework if needed
exec
/bin/zsh -lc "git status --short --branch && git rev-parse --show-toplevel && git branch --show-current && git log -1 --oneline ea421528 && sed -n '/"'^## D13/,/''^## D14/p'"' .oracle/tasklist.md && git diff --stat 0f015101..ea421528 && git diff --name-status 0f015101..ea421528" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 191ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
oracle-run
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
ea421528 megado D13 rework2: judge verdicts derived from criteria, never model self-declared pass_ — string-typed booleans/contradictory verdicts fail closed; 78 focused tests green
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .gitignore                                         |    1 +
 .oracle/briefs/batch-D13-rework.md                 |   33 +
 .oracle/briefs/batch-D13-rework2.md                |   38 +
 .oracle/briefs/batch-D13.md                        |   32 +
 .oracle/checkins/batch-D13.md                      | 6510 ++++++++++++++++++++
 tests/live_agentic_harness/README.md               |    6 +
 tests/live_agentic_harness/REVISIONS.md            |   22 +
 tests/live_agentic_harness/assessor.py             |  114 +-
 tests/live_agentic_harness/intent_judge.py         |  229 +-
 tests/live_agentic_harness/runner.py               |   23 +-
 tests/live_agentic_harness/scenario_manifest.json  | 1299 ++++
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
 tests/test_live_agentic_harness_guard_contract.py  |  357 ++
 ...test_live_agentic_harness_runner_persistence.py |    3 +
 ...est_live_agentic_intent_judge_schema_context.py |  245 +-
 tests/test_live_agentic_runner_persistence.py      |    9 +
 vibecomfy/intent/prompts/refusal_judge.prompt.md   |   43 +
 58 files changed, 10359 insertions(+), 66 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	.gitignore
A	.oracle/briefs/batch-D13-rework.md
A	.oracle/briefs/batch-D13-rework2.md
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

codex
The exact delta is larger than the executor summary: 58 files and 10,359 insertions because it includes D13 briefs/check-in artifacts and additional judge changes. The checkout also has a pre-existing modification to `.oracle/checkins/batch-D13.md`; I’m treating that as user-owned and reviewing the committed endpoint objects via `git show`/the stated range, not the working-copy edit.
Acceptance criteria and exact delta are now inventoried. The committed range includes 58 files (including D13 oracle artifacts), so the audit will distinguish product/test changes from checkpoint byproducts and ignore the dirty working-copy check-in file.
  ✓ Read D13 acceptance criteria and inventory the exact commit delta
  → Audit manifest integrity, runner rejection paths, corrected edits, rubrics, judge behavior, revisions, and source hashes
  • Run diff hygiene and focused test slices permitted by the read-only sandbox
  • Issue binary D13 verdict with per-focus evidence and precise rework if needed
exec
/bin/zsh -lc 'git diff --unified=80 0f015101..ea421528 -- tests/live_agentic_harness/scenario_manifest.py tests/live_agentic_harness/runner.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 14ms:
       raise ScenarioManifestError(
+                f"scenario descriptor must contain an object for {scenario_id}"
+            )
+        if scenario.get("id") != scenario_id:
+            raise ScenarioManifestError(
+                f"descriptor id mismatch for {scenario_id}: got {scenario.get('id')!r}"
+            )
+        workflow_path = scenario.get("workflow_path")
+        source = entry.get("source_workflow")
+        if workflow_path:
+            if not isinstance(source, Mapping):
+                raise ScenarioManifestError(f"source workflow metadata missing for {scenario_id}")
+            source_path = repo / str(source.get("path") or "")
+            expected_source_path = Path(str(workflow_path))
+            if not expected_source_path.is_absolute():
+                expected_source_path = repo / expected_source_path
+            if source_path.resolve() != expected_source_path.resolve():
+                raise ScenarioManifestError(f"source workflow path mismatch for {scenario_id}")
+            if not source_path.is_file():
+                raise ScenarioManifestError(f"source workflow is missing for {scenario_id}: {source_path}")
+            expected_source_id = str(
+                (scenario.get("_tags") or {}).get("source_workflow_id") or source_path.stem
+            )
+            if source.get("id") != expected_source_id:
+                raise ScenarioManifestError(f"source workflow id mismatch for {scenario_id}")
+            actual_source_hash = sha256_file(source_path)
+            if actual_source_hash != source.get("sha256"):
+                raise ScenarioManifestError(
+                    f"source workflow hash mismatch for {scenario_id}: "
+                    f"expected {source.get('sha256')}, got {actual_source_hash}"
+                )
+        elif source is not None:
+            raise ScenarioManifestError(f"unexpected source workflow metadata for {scenario_id}")
+        if inclusion_status == "included":
+            selected.append(path)
+
+    declared_count = manifest.get("scenario_count")
+    if declared_count != len(selected):
+        raise ScenarioManifestError(
+            f"scenario_count mismatch: expected {declared_count}, selected {len(selected)}"
+        )
+    discovered = {
+        _repo_relative(path, repo=repo)
+        for path in scenarios_dir.iterdir()
+        if path.suffix in DESCRIPTOR_SUFFIXES
+    }
+    unmanifested = sorted(discovered - seen_paths)
+    if unmanifested:
+        raise ScenarioManifestError(
+            "unmanifested scenario descriptor(s): " + ", ".join(unmanifested)
+        )
+    missing_from_directory = sorted(seen_paths - discovered)
+    if missing_from_directory:
+        raise ScenarioManifestError(
+            "manifested scenario descriptor(s) missing from directory: "
+            + ", ".join(missing_from_directory)
+        )
+    return selected
diff --git a/tests/test_live_agentic_harness_corpus_manifest.py b/tests/test_live_agentic_harness_corpus_manifest.py
new file mode 100644
index 00000000..ab67a520
--- /dev/null
+++ b/tests/test_live_agentic_harness_corpus_manifest.py
@@ -0,0 +1,148 @@
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
+    for scenario in desired_edits:
+        assessment = scenario["assessment"]
+        # A desired edit is an active acceptance rubric: it must expect a graph
+        # change and must never be configured so a refusal can skip the judge.
+        assert assessment["expect_graph_changed"] is True, scenario["id"]
+        # skip_intent_judge would let an allowlisted refusal bypass ALL judging
+        # (both the edit-intent judge and the grounded-refusal gate) — invalid.
+        assert assessment.get("skip_intent_judge") is not True, (
+            f"{scenario['id']}: skip_intent_judge would let a refusal skip the judge"
+        )
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
diff --git a/tests/test_live_agentic_harness_runner_persistence.py b/tests/test_live_agentic_harness_runner_persistence.py
new file mode 100644
index 00000000..6be670da
--- /dev/null
+++ b/tests/test_live_agentic_harness_runner_persistence.py
@@ -0,0 +1,3 @@
+"""Compatibility path retained for the D13 verification command."""
+
+from tests.test_live_agentic_runner_persistence import *  # noqa: F403
diff --git a/tests/test_live_agentic_runner_persistence.py b/tests/test_live_agentic_runner_persistence.py
index 59bb17ef..44a1cb62 100644
--- a/tests/test_live_agentic_runner_persistence.py
+++ b/tests/test_live_agentic_runner_persistence.py
@@ -1,574 +1,583 @@
 from __future__ import annotations

 import json
 import subprocess
 from pathlib import Path

 import pytest

 from tests.live_agentic_harness.runner import (
     _is_retryable_infra_summary,
     _persist_run_summary,
     _persist_scenario_summary,
     _provider_infra_failure_class,
     run_tag,
 )
+from tests.live_agentic_harness.scenario_manifest import write_manifest
 from vibecomfy.executor.contracts import coerce_model_attempts


 def _summary(tmp_path: Path, scenario_id: str, *, ok: bool) -> dict:
     output_dir = tmp_path / "tag" / scenario_id
     return {
         "scenario_id": scenario_id,
         "status": "success" if ok else "error",
         "output_dir": str(output_dir),
         "guard": {"live_agentic_success": ok},
         "deepseek_usage": {},
         "deepseek_est_cost_usd": 0.0,
         "deepseek_cost_basis": "not_available",
         "model_attempts": [],
     }


 def _failed_attempt(failure_type: str, *, completion_tokens: int = 0) -> dict:
     return {
         "phase": "classify",
         "attempt": 1,
         "outcome": "failure",
         "failure_type": failure_type,
         "requested_model": "requested",
         "resolved_model": "resolved",
         "adapter": "hermes",
         "provider": "openrouter",
         "transport": "openrouter",
         "endpoint": "https://openrouter.ai/api/v1",
         "finish_reason": "unknown",
         "token_usage": {
             "prompt_tokens": 10,
             "completion_tokens": completion_tokens,
             "total_tokens": 10 + completion_tokens,
         },
     }


 def test_persists_per_scenario_and_incremental_run_summary(tmp_path: Path) -> None:
     passing = _summary(tmp_path, "passing", ok=True)
     failing = _summary(tmp_path, "failing", ok=False)

     _persist_scenario_summary(passing, tmp_path, "tag")
     _persist_scenario_summary(failing, tmp_path, "tag")
     partial = _persist_run_summary(
         "tag",
         [passing, failing, None],
         tmp_path,
         total_scenarios=3,
         complete=False,
     )

     assert partial["passed"] == 1
     assert partial["failed"] == 1
     assert partial["pending"] == 1
     assert partial["complete"] is False
     assert (tmp_path / "tag" / "passing" / "agentic_summary.json").exists()
     assert (tmp_path / "tag" / "failing" / "agentic_summary.json").exists()
     assert (tmp_path / "tag" / "run_summary.partial.json").exists()

     persisted = json.loads((tmp_path / "tag" / "run_summary.partial.json").read_text())
     assert persisted["passed"] == 1
     assert persisted["failed"] == 1


 def test_final_summary_replaces_partial_summary(tmp_path: Path) -> None:
     passing = _summary(tmp_path, "passing", ok=True)

     _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=False)
     final = _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=True)

     assert final["complete"] is True
     assert final["overall_success"] is True
     assert (tmp_path / "tag" / "run_summary.json").exists()
     assert not (tmp_path / "tag" / "run_summary.partial.json").exists()


 def test_runner_does_not_retry_outer_timeout(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "retry-me.json"
     scenario_path.write_text(json.dumps({"id": "retry-me", "query": "do it"}), encoding="utf-8")

     calls = 0

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
         nonlocal calls
         calls += 1
         if calls == 1:
             raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         output_dir = tmp_path / "out" / tag / "retry-me"
         payload = _summary(tmp_path / "out" / tag, "retry-me", ok=True)
         payload["output_dir"] = str(output_dir)
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         per_scenario_timeout=1,
         infra_retries=1,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert calls == 1
     assert summary["passed"] == 0
     assert summary["raw_first_attempt_passed"] == 0
     assert scenario["attempt_count"] == 1
     assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
     assert scenario["attempts"][0]["score_class"] == "infra_blocked"
     assert scenario["attempts"][0]["retryable_infra"] is False
     assert scenario["attempts"][0]["agent_exercised"] is False
     assert scenario["attempts"][0]["elapsed_s"] is not None
     assert (
         tmp_path / "out" / "tag" / "retry-me" / "agentic_summary.json"
     ).exists()


 def test_runner_types_provider_capacity_without_retry(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "provider-capacity.json"
     scenario_path.write_text(
         json.dumps({"id": "provider-capacity", "query": "do it"}),
         encoding="utf-8",
     )

     calls = 0

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
         nonlocal calls
         calls += 1
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         output_dir = tmp_path / "out" / tag / "provider-capacity"
         if calls == 1:
             payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
             payload.update(
                 {
                     "status": "executor_failure",
                     "error": (
                         "OpenRouter rejected the request because the account does "
                         "not have enough credits for the requested token budget."
                     ),
                     "output_dir": str(output_dir),
                     "model_attempts": [_failed_attempt("provider_failure")],
                     "guard": {
                         "live_agentic_success": False,
                         "score_class": "product_fail",
                         "assessment": {
                             "passed": False,
                             "issues": [
                                 {
                                     "check": "response_ok",
                                     "severity": "error",
                                     "detail": (
                                         "response.ok is False: OpenRouter rejected "
                                         "the request because the account does not "
                                         "have enough credits for the requested token budget."
                                     ),
                                 }
                             ],
                         },
                     },
                 }
             )
         else:
             payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
             payload["output_dir"] = str(output_dir)
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         per_scenario_timeout=1,
         infra_retries=1,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert calls == 1
     assert summary["passed"] == 0
     assert summary["raw_first_attempt_passed"] == 0
     assert scenario["attempt_count"] == 1
     assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
     assert scenario["attempts"][0]["score_class"] == "infra_blocked"
     assert scenario["attempts"][0]["retryable_infra"] is False


 def test_runner_retries_only_typed_empty_zero_token_attempt(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "typed-empty.json"
     scenario_path.write_text(json.dumps({"id": "typed-empty", "query": "do it"}), encoding="utf-8")
     calls = 0

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
         nonlocal calls
         calls += 1
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         payload = _summary(tmp_path / "out" / tag, "typed-empty", ok=calls > 1)
         payload["output_dir"] = str(tmp_path / "out" / tag / "typed-empty")
         if calls == 1:
             payload["error"] = "arbitrary wording that must not drive classification"
             payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         infra_retries=1,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert calls == 2
     assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
     assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
     assert scenario["attempts"][1]["live_agentic_success"] is True


 def test_runner_keeps_malformed_nonempty_as_product_failure(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "malformed.json"
     scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
     calls = 0

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
         nonlocal calls
         calls += 1
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
         payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
         payload["error"] = "OpenRouter rejected / HTTP 429 wording is irrelevant"
         payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         infra_retries=1,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert calls == 1
     assert scenario["score_class"] == "product_fail"
     assert scenario.get("retryable_infra") is not True


 def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "provider-down.json"
     scenario_path.write_text(json.dumps({"id": "provider-down", "query": "do it"}), encoding="utf-8")

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         output_dir = tmp_path / "out" / tag / "provider-down"
         payload = _summary(tmp_path / "out" / tag, "provider-down", ok=False)
         payload.update(
             {
                 "status": "executor_failure",
                 "error": "HTTP Error 429: Too Many Requests",
                 "output_dir": str(output_dir),
                 "model_attempts": [_failed_attempt("provider_failure")],
                 "guard": {
                     "live_agentic_success": False,
                     "score_class": "product_fail",
                     "assessment": {"passed": False, "issues": []},
                 },
             }
         )
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         per_scenario_timeout=1,
         infra_retries=1,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert scenario["attempt_count"] == 1
     assert scenario["failure_class"] == "infra_provider_capacity"
     assert scenario["score_class"] == "infra_blocked"
     assert summary["passed"] == 0
     assert summary["infra_failures"] == 1
     assert summary["product_or_assessment_failures"] == 0
     assert summary["score_classes"] == {"infra_blocked": 1}


 def test_runner_does_not_classify_soft_search_429_as_infra(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "soft-search-warning.json"
     scenario_path.write_text(
         json.dumps({"id": "soft-search-warning", "query": "do it"}),
         encoding="utf-8",
     )

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         output_dir = tmp_path / "out" / tag / "soft-search-warning"
         payload = _summary(tmp_path / "out" / tag, "soft-search-warning", ok=False)
         payload.update(
             {
                 "status": "success",
                 "error": None,
                 "output_dir": str(output_dir),
                 "guard": {
                     "live_agentic_success": False,
                     "score_class": "product_fail",
                     "assessment": {
                         "passed": False,
                         "issues": [
                             {
                                 "check": "graph_changed",
                                 "severity": "error",
                                 "detail": "Expected graph change but response.graph_unchanged is True.",
                             },
                             {
                                 "check": "soft_warning",
                                 "severity": "warning",
                                 "detail": "web search: brave search HTTP error: HTTP Error 429: Too Many Requests",
                             },
                         ],
                     },
                 },
             }
         )
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         per_scenario_timeout=1,
         infra_retries=1,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert scenario["attempt_count"] == 1
     assert scenario["failure_class"] == "product_or_assessment_failure"
     assert scenario["score_class"] == "product_fail"
     assert scenario.get("retryable_infra") is not True
     assert summary["infra_failures"] == 0
     assert summary["product_or_assessment_failures"] == 1


 def test_runner_timeout_preserves_scenario_graph_change_expectation(
     tmp_path: Path,
     monkeypatch,
 ) -> None:  # noqa: ANN001
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "diagnose.json"
     scenario_path.write_text(
         json.dumps(
             {
                 "id": "diagnose",
                 "query": "explain the graph",
                 "assessment": {"expect_graph_changed": False},
             }
         ),
         encoding="utf-8",
     )

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
         raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     summary = run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         per_scenario_timeout=1,
         infra_retries=0,
         progress_every=0,
     )

     scenario = summary["scenarios"][0]
     assert scenario["guard"]["assessment"]["expect_graph_changed"] is False
     assert scenario["failure_class"] == "infra_timeout"
     assert summary["infra_failures"] == 1


 def test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed() -> None:
     """Oracle finding 4: persisted failure_class/retryable_infra must never drive retry.

     Canonical ``malformed_json`` evidence with zero tokens is NOT retryable even
     when the summary inherited ``failure_class=infra_empty_response`` and
     ``retryable_infra=True`` from an earlier attempt.
     """
     summary = _summary(Path("/tmp"), "conflicting-flags", ok=False)
     summary["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=0)]
     summary["failure_class"] = "infra_empty_response"
     summary["retryable_infra"] = True
     summary["score_class"] = "infra_blocked"
     summary["guard"]["failure_class"] = "infra_empty_response"
     summary["guard"]["score_class"] = "infra_blocked"

     assert _provider_infra_failure_class(summary) is None
     assert _is_retryable_infra_summary(summary) is False
     # The inherited markers were cleared, never trusted.
     assert summary.get("failure_class") is None
     assert summary.get("retryable_infra") is False
     assert summary.get("score_class") is None
     assert summary["guard"].get("failure_class") is None
     assert summary["guard"].get("score_class") is None


 def test_retryability_is_derived_from_canonical_typed_evidence() -> None:
     """Canonical empty_response + observed zero tokens is retryable regardless of flags."""
     summary = _summary(Path("/tmp"), "canonical-empty", ok=False)
     summary["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
     summary["failure_class"] = "product_or_assessment_failure"  # stale conflicting flag
     summary["retryable_infra"] = False  # stale conflicting flag

     assert _provider_infra_failure_class(summary) == "infra_empty_response"
     assert _is_retryable_infra_summary(summary) is True
     assert summary["failure_class"] == "infra_empty_response"
     assert summary["retryable_infra"] is True


 @pytest.fixture
 def leaky_canonical_attempt() -> dict:
     """Canonical failed attempt whose preview embeds oracle finding 5 JSON secrets.

     The canonical shape is exactly what the executor emits (``coerce_model_attempts``
     applies ``ModelAttemptEvidence`` redaction), so a persisted agentic summary must
     never reintroduce the raw secrets.
     """
     attempts = coerce_model_attempts(
         (
             {
                 **_failed_attempt("provider_failure"),
                 "raw_response_preview": (
                     '{"api_key":"sk-secret",'
                     '"authorization":"Basic dXNlcjpwYXNz",'
                     '"token":"tok-secret"}'
                 ),
             },
         )
     )
     return attempts[0]


 def test_persisted_agentic_summary_redacts_json_quoted_secrets(
     tmp_path: Path,
     monkeypatch,
     leaky_canonical_attempt: dict,
 ) -> None:  # noqa: ANN001
     """Oracle finding 5 durable: agentic_summary.json keeps JSON-quoted secrets out."""
     scenarios_dir = tmp_path / "scenarios"
     scenarios_dir.mkdir()
     scenario_path = scenarios_dir / "json-quoted-secrets.json"
     scenario_path.write_text(
         json.dumps({"id": "json-quoted-secrets", "query": "do it"}),
         encoding="utf-8",
     )

     def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
         out_file = Path(cmd[cmd.index("--single-out") + 1])
         tag = cmd[cmd.index("--tag") + 1]
         payload = _summary(tmp_path / "out" / tag, "json-quoted-secrets", ok=False)
         payload["output_dir"] = str(tmp_path / "out" / tag / "json-quoted-secrets")
         payload["error"] = "provider rejected"
         payload["model_attempts"] = [leaky_canonical_attempt]
         out_file.write_text(json.dumps(payload), encoding="utf-8")
         return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

+    write_manifest(scenarios_dir)
     monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

     run_tag(
         "tag",
         scenarios_dir=scenarios_dir,
         output_base=tmp_path / "out",
         max_workers=1,
         per_scenario_timeout=1,
         infra_retries=0,
         progress_every=0,
     )

     persisted_path = (
         tmp_path / "out" / "tag" / "json-quoted-secrets" / "agentic_summary.json"
     )
     assert persisted_path.exists()
     persisted = persisted_path.read_text(encoding="utf-8")
     assert "sk-secret" not in persisted
     assert "Basic dXNlcjpwYXNz" not in persisted
     assert "tok-secret" not in persisted
     summary = json.loads(persisted)
     # model_attempts is persisted both top-level and inside the attempt record;
     # every occurrence must carry the fully redacted preview.
     for attempt in [summary["model_attempts"][0], summary["attempts"][0]["model_attempts"][0]]:
         preview = attempt["raw_response_preview"]
         assert preview.count("<redacted>") == 3
         assert "sk-secret" not in preview
         assert "Basic dXNlcjpwYXNz" not in preview
         assert "tok-secret" not in preview

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/scenario_manifest.py | sed -n '1,320p'
nl -ba tests/test_live_agentic_harness_corpus_manifest.py | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
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
/bin/zsh -lc "ls -ld external_workflows && find tests/live_agentic_harness/scenarios -maxdepth 1 -type f \\( -name '*.json' -o -name '*.yaml' -o -name '*.yml' \\) | wc -l && jq '{schema_version,scenario_root,scenario_count,entries:(.entries|length),included:([.entries[]|select(.inclusion_status==\"included\")]|length),unique_ids:([.entries[].id]|unique|length),unique_paths:([.entries[].path]|unique|length),kinds:([.entries[].scenario_kind]|group_by(.)|map({key:.[0],value:length})|from_entries),revisions:([.entries[].revision_status]|group_by(.)|map({key:.[0],value:length})|from_entries),sources:([.entries[]|select(.source_workflow "'!= null)]|length)}'"' tests/live_agentic_harness/scenario_manifest.json && jq -r '.entries[0,49,99] | [.id,.path,.descriptor_sha256,(.source_workflow.id // \"-\"),(.source_workflow.path // \"-\"),(.source_workflow.sha256 // \"-\")] | @tsv' tests/live_agentic_harness/scenario_manifest.json" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
lrwxr-xr-x  1 peteromalley  staff  74 Aug 13 14:41 external_workflows -> /Users/peteromalley/Documents/reigh-workspace/vibecomfy/external_workflows
     100
{
  "schema_version": 1,
  "scenario_root": "tests/live_agentic_harness/scenarios",
  "scenario_count": 100,
  "entries": 100,
  "included": 100,
  "unique_ids": 100,
  "unique_paths": 100,
  "kinds": {
    "edit": 63,
    "health_control": 2,
    "semantic_product": 35
  },
  "revisions": {
    "matched": 97,
    "revised": 3
  },
  "sources": 98
}
3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2	tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json	f2d7ac44c1d69ddbc3da300e0700868a9107e64c2ce5b75a405d92080b761f46	c24aa2ac329006f2	external_workflows/corpus/c24aa2ac329006f2.json	3c605c00652907736c02e5c4bfff6fa17c9edbfd06024be972b004dc2332f180
multi-ai-video-upscaling-with-detail-daemon-sampler-673197	tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json	2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457	673197a9269d00f8	external_workflows/corpus/673197a9269d00f8.json	d15ba9e1d9385ec8ebcbe3ba82d1e9a85af103821b369af3f45170ac8c037f1b
video-wanvideo-text-to-video-generation-71f825	tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json	df4959641e24bfcd7b62ad558dc4cede081febf7e14f44475fd3a70855f60d31	71f825e4550c95b7	external_workflows/corpus/71f825e4550c95b7.json	87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3

exec
/bin/zsh -lc 'for p in tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json external_workflows/corpus/c24aa2ac329006f2.json external_workflows/corpus/673197a9269d00f8.json external_workflows/corpus/71f825e4550c95b7.json; do shasum -a 256 "$p"; done
PYTHONDONTWRITEBYTECODE=1 python - <<'"'PY'
import hashlib,json
from pathlib import Path
root=Path('.')
m=json.loads((root/'tests/live_agentic_harness/scenario_manifest.json').read_text())
errs=[]
for e in m['entries']:
 p=root/e['path']
 h=hashlib.sha256(p.read_bytes()).hexdigest()
 if h "'!= e['"'descriptor_sha256']: errs.append(('descriptor',e['id'],h,e['descriptor_sha256']))
 s=e.get('source_workflow')
 if s:
  sp=root/s['path']
  if not sp.is_file(): errs.append(('missing-source',e['id'],str(sp)))
  else:
   sh=hashlib.sha256(sp.read_bytes()).hexdigest()
   if sh "'!= s['"'sha256']: errs.append(('source',e['id'],sh,s['sha256']))
print({'entries':len(m['entries']),'full_hash_mismatches':len(errs),'errors':errs[:5]})
PY" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 248ms:
2ca7950b93535364cb63947b4d658ec35eb0fbd9d3113da74e480be28c40b457  tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
df4959641e24bfcd7b62ad558dc4cede081febf7e14f44475fd3a70855f60d31  tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
3c605c00652907736c02e5c4bfff6fa17c9edbfd06024be972b004dc2332f180  external_workflows/corpus/c24aa2ac329006f2.json
d15ba9e1d9385ec8ebcbe3ba82d1e9a85af103821b369af3f45170ac8c037f1b  external_workflows/corpus/673197a9269d00f8.json
87bcefccfcba650f83aa8568f6572b623151ccd4e296a44d442048f2f737bef3  external_workflows/corpus/71f825e4550c95b7.json
zsh:2: can't create temp file for here document: operation not permitted

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import hashlib,json
from pathlib import Path
root=Path(\".\")
m=json.loads((root/\"tests/live_agentic_harness/scenario_manifest.json\").read_text())
errs=[]
for e in m[\"entries\"]:
 p=root/e[\"path\"]
 h=hashlib.sha256(p.read_bytes()).hexdigest()
 if h "'!= e["descriptor_sha256"]: errs.append(("descriptor",e["id"],h,e["descriptor_sha256"]))
 s=e.get("source_workflow")
 if s:
  sp=root/s["path"]
  if not sp.is_file(): errs.append(("missing-source",e["id"],str(sp)))
  elif hashlib.sha256(sp.read_bytes()).hexdigest() != s["sha256"]: errs.append(("source",e["id"]))
print({"entries":len(m["entries"]),"full_hash_mismatches":len(errs),"errors":errs[:5]})
'"' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 1265ms:
{'entries': 100, 'full_hash_mismatches': 0, 'errors': []}

exec
/bin/zsh -lc 'git diff --unified=80 0f015101..ea421528 -- tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 26ms:
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

exec
/bin/zsh -lc "rg -n 'INPAINT_InpaintWithModel|534667941392889|SaveGLB|3d/ComfyUI|Moonvalley|MoonValley|100|prompt adherence' external_workflows/corpus/485ff2fa6dcc1917.json external_workflows/corpus/d7853cd7421f9ebc.json external_workflows/corpus/d93baf73c8a43f57.json | head -80" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
external_workflows/corpus/d93baf73c8a43f57.json:34:        "class_type": "SaveGLB",
external_workflows/corpus/d93baf73c8a43f57.json:49:            "'3d/ComfyUI'"
external_workflows/corpus/d93baf73c8a43f57.json:211:        "SaveGLB": 1
external_workflows/corpus/d93baf73c8a43f57.json:253:      "class_type": "SaveGLB",
external_workflows/corpus/d93baf73c8a43f57.json:326:            "Node name for S&R": "SaveGLB",
external_workflows/corpus/d93baf73c8a43f57.json:352:          "type": "SaveGLB",
external_workflows/corpus/d93baf73c8a43f57.json:354:            "3d/ComfyUI",
external_workflows/corpus/d93baf73c8a43f57.json:370:          "3d/ComfyUI",
external_workflows/corpus/d93baf73c8a43f57.json:376:        "widget_0": "3d/ComfyUI",
external_workflows/corpus/d93baf73c8a43f57.json:524:            6028.071510079876
external_workflows/corpus/d93baf73c8a43f57.json:968:        "SaveGLB": 1
external_workflows/corpus/d7853cd7421f9ebc.json:81:            "'## Moonvalley Template Docs\\n\\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\\n\\n## API Node Docs\\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\\n## FAQ about login issues\\n\\nTo use the API, you must be in a secure network environment:\\n\\n- Allows access from `127.0.0.1` or `localhost`.\\n\\n- Use our API Node in website services starting with `https`\\n\\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\\n\\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\\n\\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)'"
external_workflows/corpus/d7853cd7421f9ebc.json:86:        "class_type": "MoonvalleyImg2VideoNode",
external_workflows/corpus/d7853cd7421f9ebc.json:133:            "100"
external_workflows/corpus/d7853cd7421f9ebc.json:143:      "commit_message": "Remove Moonvalley templates (#834)\n\nCo-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>\nCo-authored-by: GitHub Action <action@github.com>",
external_workflows/corpus/d7853cd7421f9ebc.json:155:        "MoonvalleyImg2VideoNode": 1,
external_workflows/corpus/d7853cd7421f9ebc.json:177:      "description": "Loads an image and generates a video using the Moonvalley Img2Video custom node, then saves the output video.",
external_workflows/corpus/d7853cd7421f9ebc.json:194:      "title": "Image to Video Conversion with Moonvalley"
external_workflows/corpus/d7853cd7421f9ebc.json:326:        "unused_widget_0": "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"
external_workflows/corpus/d7853cd7421f9ebc.json:350:            "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"
external_workflows/corpus/d7853cd7421f9ebc.json:367:          "## Moonvalley Template Docs\n\n[Moonvalley video generation](https://docs.comfy.org/tutorials/partner-nodes/moonvalley/moonvalley-video-generation)\n\n## API Node Docs\n[API Node](https://docs.comfy.org/tutorials/partner-nodes/overview)\n## FAQ about login issues\n\nTo use the API, you must be in a secure network environment:\n\n- Allows access from `127.0.0.1` or `localhost`.\n\n- Use our API Node in website services starting with `https`\n\n- Ensure normal connectivity to our API services (VPN may be needed in some regions).\n\n- Make sure you are logged in in the settings and that your account still has enough credits to cover the consumption of API calls.\n\n- On non-whitelisted sites or local area networks (LANs), please try to [log in using an API Key](https://docs.comfy.org/interface/user#logging-in-with-an-api-key)"
external_workflows/corpus/d7853cd7421f9ebc.json:374:      "class_type": "MoonvalleyImg2VideoNode",
external_workflows/corpus/d7853cd7421f9ebc.json:406:            "Node name for S&R": "MoonvalleyImg2VideoNode"
external_workflows/corpus/d7853cd7421f9ebc.json:412:          "type": "MoonvalleyImg2VideoNode",
external_workflows/corpus/d7853cd7421f9ebc.json:420:            100
external_workflows/corpus/d7853cd7421f9ebc.json:443:          100
external_workflows/corpus/d7853cd7421f9ebc.json:454:        "widget_6": 100
external_workflows/corpus/d7853cd7421f9ebc.json:483:      "commit_message": "Remove Moonvalley templates (#834)\n\nCo-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>\nCo-authored-by: GitHub Action <action@github.com>",
external_workflows/corpus/d7853cd7421f9ebc.json:495:        "MoonvalleyImg2VideoNode": 1,
external_workflows/corpus/485ff2fa6dcc1917.json:341:        "class_type": "INPAINT_InpaintWithModel",
external_workflows/corpus/485ff2fa6dcc1917.json:378:            "534667941392889"
external_workflows/corpus/485ff2fa6dcc1917.json:406:        "INPAINT_InpaintWithModel": 1,
external_workflows/corpus/485ff2fa6dcc1917.json:676:                "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"
external_workflows/corpus/485ff2fa6dcc1917.json:958:      "class_type": "INPAINT_InpaintWithModel",
external_workflows/corpus/485ff2fa6dcc1917.json:1005:            "Node name for S&R": "INPAINT_InpaintWithModel"
external_workflows/corpus/485ff2fa6dcc1917.json:1011:          "type": "INPAINT_InpaintWithModel",
external_workflows/corpus/485ff2fa6dcc1917.json:1013:            534667941392889,
external_workflows/corpus/485ff2fa6dcc1917.json:1029:          534667941392889,
external_workflows/corpus/485ff2fa6dcc1917.json:1035:        "widget_0": 534667941392889,
external_workflows/corpus/485ff2fa6dcc1917.json:1079:        "INPAINT_InpaintWithModel": 1,

exec
/bin/zsh -lc "jq -c '.. | objects | select(.class_type? == \"INPAINT_InpaintWithModel\" or .type? == \"INPAINT_InpaintWithModel\") | {class_type,type,inputs,widgets_values,properties}' external_workflows/corpus/485ff2fa6dcc1917.json | head -8
jq -c '.. | objects | select(.class_type? == \"MoonvalleyImg2VideoNode\" or .type? == \"MoonvalleyImg2VideoNode\") | {class_type,type,inputs,widgets_values,properties}' external_workflows/corpus/d7853cd7421f9ebc.json | head -8
jq -c '.. | objects | select(.class_type? == \"SaveGLB\" or .type? == \"SaveGLB\") | {class_type,type,inputs,widgets_values,properties}' external_workflows/corpus/d93baf73c8a43f57.json | head -8" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
{"class_type":"INPAINT_InpaintWithModel","type":null,"inputs":null,"widgets_values":null,"properties":null}
{"class_type":"INPAINT_InpaintWithModel","type":null,"inputs":{},"widgets_values":null,"properties":null}
{"class_type":null,"type":"INPAINT_InpaintWithModel","inputs":[{"link":18,"name":"inpaint_model","type":"INPAINT_MODEL"},{"link":19,"name":"image","type":"IMAGE"},{"link":20,"name":"mask","type":"MASK"},{"link":null,"name":"optional_upscale_model","shape":7,"type":"UPSCALE_MODEL"}],"widgets_values":[534667941392889,"fixed"],"properties":{"Node name for S&R":"INPAINT_InpaintWithModel"}}
{"class_type":"MoonvalleyImg2VideoNode","type":null,"inputs":null,"widgets_values":null,"properties":null}
{"class_type":"MoonvalleyImg2VideoNode","type":null,"inputs":{},"widgets_values":null,"properties":null}
{"class_type":null,"type":"MoonvalleyImg2VideoNode","inputs":[{"link":36,"name":"image","type":"IMAGE"}],"widgets_values":["A bedroom is transformed into a surreal underwater dreamscape, completely submerged in deep turquoise water where caustic light patterns ripple and dance across the walls, floor, and ceiling. In the center of this submerged room, a ballerina gracefully holds a pose en pointe, her form silhouetted against the ethereal blue glow. She moves with impossible slowness, transitioning between ballet positions as her sheer white dress billows around her in the gentle, silent currents. Tiny bubbles occasionally escape her lips, rising towards the undulating surface above, which serves as the room's only light source. The scene is both beautiful and unsettling, a silent performance in a liquid world where reality is suspended. Background: The ceiling is the agitated surface of the water, with ethereal beams of light filtering down and constantly shifting. A bed sits against the back wall, its form partially obscured by the moving shadows and light. Middleground: A silhouetted ballerina stands as the focal point, her arms outstretched in a graceful ballet pose. Her diaphanous dress flows weightlessly around her, moved by invisible underwater currents as she performs her silent dance. Foreground: The floor is covered in a moving tapestry of bright caustic reflections from the water's surface above. The ballerina's shadow and reflection are cast upon the floor, distorting and swaying with the light.","low-poly, flat shader, bad rigging, stiff animation, uncanny eyes, low-quality textures, looping glitch, cheap effect, overbloom, bloom spam, default lighting, game asset, stiff face, ugly specular, AI artifacts","16:9 (1920 x 1080)",7,2328774152,"randomize",100],"properties":{"Node name for S&R":"MoonvalleyImg2VideoNode"}}
{"class_type":"SaveGLB","type":null,"inputs":null,"widgets_values":null,"properties":null}
{"class_type":"SaveGLB","type":null,"inputs":{},"widgets_values":null,"properties":null}
{"class_type":null,"type":"SaveGLB","inputs":[{"link":92,"name":"mesh","type":"MESH,FILE_3D_GLB,FILE_3D_GLTF,FILE_3D_OBJ,FILE_3D_FBX,FILE_3D_STL,FILE_3D_USDZ,FILE_3D"}],"widgets_values":["3d/ComfyUI",""],"properties":{"Camera Config":{"cameraType":"perspective","fov":35,"state":{"cameraType":"perspective","position":{"x":6.786724982855805,"y":1.9262054236803827,"z":4.315390609507273},"target":{"x":0.5610696024689849,"y":1.8227901315768118,"z":-0.15103066686464472},"zoom":1}},"Light Config":{"hdri":{"enabled":false,"hdriPath":"","intensity":1,"showAsBackground":false},"intensity":2.4000000000000004},"Model Config":{"gizmo":{"enabled":false,"mode":"translate","position":{"x":0.3622254788581172,"y":1.8487530247818735,"z":3.580411492082191},"rotation":{"x":0,"y":0,"z":0},"scale":{"x":2.687608243041624,"y":2.687608243041624,"z":2.687608243041624}},"materialMode":"original","showSkeleton":false,"upDirection":"original"},"Node name for S&R":"SaveGLB","Scene Config":{"backgroundColor":"#8e9ea9","backgroundImage":"","backgroundRenderMode":"tiled","showGrid":false},"cnr_id":"comfy-core","enableTabs":false,"hasSecondTab":false,"secondTabOffset":80,"secondTabText":"Send Back","secondTabWidth":65,"tabWidth":65,"tabXOffset":10,"ue_properties":{"input_ue_unconnectable":{},"version":"7.8","widget_ue_connectable":{}},"ver":"0.21.1"}}

exec
/bin/zsh -lc 'rg -n "desired|intent_judge|judge|unavailable|graph_changed|refusal|skip_intent|pass_|verdict|semantic_answer" tests/live_agentic_harness/assessor.py tests/live_agentic_harness/intent_judge.py tests/live_agentic_harness/guard.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_intent_judge_schema_context.py vibecomfy/intent/prompts/refusal_judge.prompt.md | head -260' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 1ms:
exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '620,895p'
nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '100,180p'
nl -ba tests/live_agentic_harness/intent_judge.py | sed -n '340,585p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
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
   100
   101	def _strict_boolean(value: Any) -> bool | None:
   102	    """Return *value* iff it is an explicit JSON boolean (Python ``bool``).
   103
   104	    JSON ``true``/``false`` decode to Python ``bool``.  Anything else —
   105	    including the strings ``"true"``/``"false"`` — is malformed and returns
   106	    None so callers fail closed instead of coercing with ``bool()``.
   107	    """
   108	    if type(value) is bool:
   109	        return value
   110	    return None
   111
   112
   113	def _derive_verdict(parsed: Any, criterion_keys: tuple[str, ...]) -> dict[str, Any]:
   114	    """Normalize a parsed judge response, deriving ``pass_`` from the criteria.
   115
   116	    The model's self-declared ``pass_`` is never trusted: the verdict is True
   117	    only when the response is a JSON object whose ``pass_`` is an explicit
   118	    boolean and every required criterion is an explicit ``true`` boolean.  Any
   119	    criterion that is false, missing, or not a strict boolean (including the
   120	    strings ``"false"``/``"true"``), any non-boolean or absent ``pass_``, and
   121	    any non-object response fail the verdict closed — malformed output is a
   122	    fail, never a pass.  Only genuinely unparsable JSON (json.loads raising
   123	    in the caller) stays undetermined (``pass_`` None).
   124	    """
   125	    if not isinstance(parsed, dict):
   126	        return {"pass_": False, "criteria": {}, "rationale": ""}
   127	    self_declared = _strict_boolean(parsed.get("pass_"))
   128	    criteria_raw = parsed.get("criteria")
   129	    criteria: dict[str, Any] = {}
   130	    if isinstance(criteria_raw, dict):
   131	        for key in criterion_keys:
   132	            value = _strict_boolean(criteria_raw.get(key))
   133	            if value is not None:
   134	                criteria[key] = value
   135	    all_criteria_pass = all(criteria.get(key) is True for key in criterion_keys)
   136	    return {
   137	        "pass_": self_declared is not None and all_criteria_pass,
   138	        "criteria": criteria,
   139	        "rationale": str(parsed.get("rationale", "")),
   140	    }
   141
   142
   143	def _parse_verdict(raw: str) -> dict[str, Any]:
   144	    """Parse the judge's JSON response into a normalized dict.
   145
   146	    ``pass_`` is derived from the criteria (fail closed), never from the
   147	    model's self-declared ``pass_``: it is True iff every required criterion
   148	    is an explicit JSON boolean ``true`` and ``pass_`` itself is an explicit
   149	    boolean.  String-typed booleans, missing criteria, false criteria, and
   150	    contradictory self-declarations all fail closed.
   151	    """
   152	    parsed = json.loads(_strip_code_fences(raw))
   153	    return _derive_verdict(parsed, _EDIT_CRITERION_KEYS)
   154
   155
   156	def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
   157	    """Parse the grounded-refusal judge's JSON response into a normalized dict.
   158
   159	    Same fail-closed contract as :func:`_parse_verdict`: the verdict is
   160	    derived from the four refusal criteria (supported blocker, no
   161	    representable edit, specific next action, no fabricated inability), not
   162	    from the model's self-declared ``pass_``.
   163	    """
   164	    parsed = json.loads(_strip_code_fences(raw))
   165	    return _derive_verdict(parsed, _REFUSAL_CRITERION_KEYS)
   166
   167
   168	def _load_implementation_payload(output_dir: Path) -> dict[str, Any] | None:
   169	    path = output_dir / "implementation_payload.json"
   170	    if not path.is_file():
   171	        return None
   172	    try:
   173	        data = json.loads(path.read_text(encoding="utf-8"))
   174	    except (OSError, json.JSONDecodeError):
   175	        return None
   176	    return data if isinstance(data, dict) else None
   177
   178
   179	def _schema_context_from_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
   180	    if not isinstance(payload, Mapping):
   340	        "note": (
   341	            "widgets_values are static node configuration. Linked inputs are dynamic dataflow. "
   342	            "A static text widget removal can be correct when linked dynamic inputs remain connected."
   343	        ),
   344	    }
   345
   346
   347	def judge_edit_intent(
   348	    output_dir: Path | str,
   349	    scenario: Mapping[str, Any],
   350	    *,
   351	    route: str = "deepseek",
   352	    model: str = "deepseek-v4-pro",
   353	) -> dict[str, Any]:
   354	    """Run the DeepSeek text judge on the candidate edit in *output_dir*.
   355
   356	    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
   357	    If required artifacts are missing or the model call fails, ``pass_`` is None
   358	    and ``error`` describes why.
   359	    """
   360	    output_dir = Path(output_dir)
   361	    query = str(scenario.get("query", "")).strip()
   362	    if not query:
   363	        return {"pass_": None, "error": "scenario has no query"}
   364
   365	    # The durable turn writes UI artifacts under out/editor_sessions; the response
   366	    # JSON carries the exact paths in its artifacts block.
   367	    response_path = output_dir / "response.json"
   368	    original_ui_path: Path | None = None
   369	    candidate_ui_path: Path | None = None
   370	    if response_path.is_file():
   371	        try:
   372	            response = json.loads(response_path.read_text(encoding="utf-8"))
   373	            artifacts = response.get("artifacts", {}) or {}
   374	            if isinstance(artifacts.get("original_ui"), str):
   375	                original_ui_path = Path(artifacts["original_ui"])
   376	            if isinstance(artifacts.get("candidate_ui"), str):
   377	                candidate_ui_path = Path(artifacts["candidate_ui"])
   378	        except (OSError, json.JSONDecodeError):
   379	            pass
   380
   381	    # Fallback to common in-directory locations if response artifacts are absent.
   382	    if original_ui_path is None:
   383	        original_ui_path = output_dir / "original.ui.json"
   384	    if candidate_ui_path is None:
   385	        candidate_ui_path = output_dir / "candidate.ui.json"
   386
   387	    if not original_ui_path.is_file() or not candidate_ui_path.is_file():
   388	        return {
   389	            "pass_": None,
   390	            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
   391	        }
   392
   393	    try:
   394	        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
   395	        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
   396	    except (OSError, json.JSONDecodeError) as exc:
   397	        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}
   398
   399	    system_prompt = _load_prompt()
   400	    implementation_payload = _load_implementation_payload(output_dir)
   401	    schema_context = _schema_context_from_payload(implementation_payload) or {}
   402	    dataflow_context = _static_widget_dataflow_context(pre_ir, post_ir)
   403	    if dataflow_context:
   404	        schema_context["dataflow_context"] = dataflow_context
   405	    if schema_context:
   406	        system_prompt = (
   407	            system_prompt.rstrip()
   408	            + "\n\n## Schema and widget evidence\n"
   409	            "When schema_context is provided, use it to map opaque widget_N fields "
   410	            "to semantic input names. Treat literal widget values as static node "
   411	            "configuration, and linked inputs/edges as dynamic dataflow. Do not guess a "
   412	            "widget's meaning from index order when compiled_api names are available. "
   413	            "If a static widget containing stale or fabricated text is removed while "
   414	            "the relevant linked dynamic input path remains connected, do not treat "
   415	            "that removal as deleting the dynamic dataflow."
   416	        )
   417	    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
   418	    # present, it grounds the judge on what a GOOD result achieves (the outcome +
   419	    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
   420	    # alternative approaches that reach the same outcome count as correct.
   421	    desired = scenario.get("desired")
   422	    if desired:
   423	        system_prompt = (
   424	            system_prompt.rstrip()
   425	            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
   426	            "The scenario author described what a GOOD result looks like below. Use it to "
   427	            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
   428	            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
   429	            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
   430	            "it fully wired/complete (no dangling or broken connections, existing pipeline "
   431	            "not broken), and is the approach a sensible one?\n\n"
   432	            f"Desired outcome: {desired.get('outcome', '')}\n"
   433	            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
   434	            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
   435	        )
   436	    payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
   437	    if desired:
   438	        payload["desired_outcome"] = desired
   439	    if schema_context:
   440	        payload["schema_context"] = schema_context
   441	    user_content = json.dumps(payload, indent=2)
   442
   443	    try:
   444	        response = run_model_turn(
   445	            "evaluate workflow edit against intent",
   446	            messages=[
   447	                {"role": "system", "content": system_prompt},
   448	                {"role": "user", "content": user_content},
   449	            ],
   450	            route=route,
   451	            model=model,
   452	            response_contract="json",
   453	        )
   454	    except Exception as exc:  # noqa: BLE001
   455	        return {"pass_": None, "error": f"model call failed: {exc}"}
   456
   457	    raw = response.get("content") or ""
   458	    if not raw:
   459	        return {"pass_": None, "error": "model returned empty content"}
   460
   461	    try:
   462	        verdict = _parse_verdict(raw)
   463	    except (json.JSONDecodeError, KeyError, TypeError) as exc:
   464	        return {
   465	            "pass_": None,
   466	            "error": f"could not parse judge response: {exc}",
   467	            "raw": raw[:500],
   468	        }
   469
   470	    verdict["metadata"] = {
   471	        "route": route,
   472	        "model": model,
   473	        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
   474	    }
   475	    return verdict
   476
   477
   478	def judge_grounded_refusal(
   479	    output_dir: Path | str,
   480	    scenario: Mapping[str, Any],
   481	    *,
   482	    route: str = "deepseek",
   483	    model: str = "deepseek-v4-pro",
   484	) -> dict[str, Any]:
   485	    """Run the DeepSeek grounded-refusal judge for a desired edit scenario.
   486
   487	    A desired edit may pass on an allowlisted refusal label ONLY when this judge
   488	    confirms the refusal is grounded: the cited blocker is real and supported,
   489	    no representable edit could satisfy the intent, the refusal states a
   490	    specific next action, and it does not fabricate an inability.
   491
   492	    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
   493	    If required artifacts are missing or the model call fails, ``pass_`` is None
   494	    and ``error`` describes why — callers MUST fail closed on that outcome.
   495	    """
   496	    output_dir = Path(output_dir)
   497	    query = str(scenario.get("query", "")).strip()
   498	    if not query:
   499	        return {"pass_": None, "error": "scenario has no query"}
   500
   501	    # The refusal envelope is read from the run's response.json: outcome kind,
   502	    # message, gates, route, evidence.  Only the structured envelope is scored;
   503	    # prose never gates.
   504	    response_path = output_dir / "response.json"
   505	    refusal: dict[str, Any] = {}
   506	    if response_path.is_file():
   507	        try:
   508	            response = json.loads(response_path.read_text(encoding="utf-8"))
   509	        except (OSError, json.JSONDecodeError):
   510	            response = None
   511	        if isinstance(response, Mapping):
   512	            refusal = {
   513	                "outcome": response.get("outcome"),
   514	                "message": response.get("message"),
   515	                "no_candidate_reason": response.get("no_candidate_reason"),
   516	                "route": response.get("route"),
   517	                "gates": response.get("gates"),
   518	                "evidence": response.get("evidence"),
   519	                "graph_unchanged": response.get("graph_unchanged"),
   520	            }
   521	    if not isinstance(refusal.get("outcome"), Mapping):
   522	        return {"pass_": None, "error": "response.json is missing a refusal outcome"}
   523
   524	    system_prompt = _load_refusal_prompt()
   525	    implementation_payload = _load_implementation_payload(output_dir)
   526	    schema_context = _schema_context_from_payload(implementation_payload) or {}
   527	    if schema_context:
   528	        system_prompt = (
   529	            system_prompt.rstrip()
   530	            + "\n\n## Schema evidence\n"
   531	            "When schema_context is provided, use it to verify whether a cited "
   532	            "blocker is real. A 'requires_custom_nodes' refusal is fabricated if "
   533	            "the needed node class actually exists in compiled_api. Do not guess "
   534	            "from node names when compiled_api is available."
   535	        )
   536	    desired = scenario.get("desired")
   537	    payload: dict[str, Any] = {"nl_intent": query, "refusal": refusal}
   538	    if desired:
   539	        payload["desired_outcome"] = desired
   540	    if schema_context:
   541	        payload["schema_context"] = schema_context
   542	    user_content = json.dumps(payload, indent=2)
   543
   544	    try:
   545	        response = run_model_turn(
   546	            "evaluate whether a workflow-edit refusal is grounded",
   547	            messages=[
   548	                {"role": "system", "content": system_prompt},
   549	                {"role": "user", "content": user_content},
   550	            ],
   551	            route=route,
   552	            model=model,
   553	            response_contract="json",
   554	        )
   555	    except Exception as exc:  # noqa: BLE001
   556	        return {"pass_": None, "error": f"model call failed: {exc}"}
   557
   558	    raw = response.get("content") or ""
   559	    if not raw:
   560	        return {"pass_": None, "error": "model returned empty content"}
   561
   562	    try:
   563	        verdict = _parse_refusal_verdict(raw)
   564	    except (json.JSONDecodeError, KeyError, TypeError) as exc:
   565	        return {
   566	            "pass_": None,
   567	            "error": f"could not parse judge response: {exc}",
   568	            "raw": raw[:500],
   569	        }
   570
   571	    verdict["metadata"] = {
   572	        "route": route,
   573	        "model": model,
   574	        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
   575	    }
   576	    return verdict

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/assessor.py | sed -n '270,350p'
rg -n 'allow_safe_refusal|skip_intent_judge' tests/live_agentic_harness/scenarios tests/live_agentic_harness/scenario_manifest.json" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 96ms:
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
   286	    agent's own classification/plan from the response.
   287	    """
   288	    if scenario is not None:
   289	        assessment = scenario.get("assessment")
   290	        if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
   291	            return bool(assessment["expect_graph_changed"])
   292
   293	    if response is None:
   294	        return False
   295
   296	    plan = response.get("report", {}).get("executor", {}).get("plan") or {}
   297	    if plan.get("implement") is True and plan.get("route") in {"adapt", "revise"}:
   298	        return True
   299
   300	    return False
   301
   302
   303	def _expected_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
   304	    """Return explicitly accepted public outcome kinds for this scenario."""
   305	    if scenario is None:
   306	        return set()
   307	    assessment = scenario.get("assessment")
   308	    if not isinstance(assessment, Mapping):
   309	        return set()
   310	    raw = assessment.get("expected_outcome_kinds")
   311	    if raw is None:
   312	        raw = assessment.get("expected_outcome_kind")
   313	    if isinstance(raw, str):
   314	        return {raw}
   315	    if isinstance(raw, list):
   316	        return {item for item in raw if isinstance(item, str)}
   317	    return set()
   318
   319
   320	def _allowed_safe_refusal_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
   321	    """Return no-edit outcome kinds accepted as safe refusals for edit scenarios."""
   322	    if scenario is None:
   323	        return set()
   324	    assessment = scenario.get("assessment")
   325	    if not isinstance(assessment, Mapping):
   326	        return set()
   327	    raw = assessment.get("allow_safe_refusal_outcome_kinds")
   328	    if raw is None:
   329	        raw = assessment.get("allow_safe_refusal_outcome_kind")
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
tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json:10:    "allow_safe_refusal_outcome_kinds": [
tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json:10:    "allow_safe_refusal_outcome_kinds": [
tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json:10:    "allow_safe_refusal_outcome_kinds": [

exec
/bin/zsh -lc 'rg -n "desired.*judge|judge.*unavailable|fails_closed|grounded_refusal|safe_refusal" tests/test_live_agentic_harness_guard_contract.py | tail -100' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
69:def _write_safe_refusal_response(
102:            "allow_safe_refusal_outcome_kinds": ["clarify", kind],
112:def _grounded_refusal_verdict(*, grounded: bool) -> dict:
272:def test_agentic_guard_allows_explicit_safe_refusal_scenarios(tmp_path: Path) -> None:
318:def test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios(tmp_path: Path) -> None:
349:def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
383:            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
392:    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
393:    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}
396:def test_desired_edit_rejects_safe_refusal_when_grounded_judge_unavailable(
402:    output_dir = tmp_path / "desired-refusal-judge-unavailable"
404:    _write_safe_refusal_response(output_dir)
409:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
410:        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
415:        scenario=_desired_edit_scenario("desired-refusal-judge-unavailable"),
420:        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
425:def test_desired_edit_rejects_fabricated_safe_refusal(
433:    _write_safe_refusal_response(output_dir)
438:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
439:        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=False),
449:        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
454:def test_desired_edit_accepts_grounded_safe_refusal(
462:    _write_safe_refusal_response(output_dir)
467:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
468:        lambda *args, **kwargs: _grounded_refusal_verdict(grounded=True),
480:        issue["check"] == "grounded_refusal" and issue["severity"] == "info"
485:def test_desired_edit_refusal_label_with_graph_change_fails_closed_without_verdict(
494:    _write_safe_refusal_response(output_dir, graph_unchanged=False)
499:        "tests.live_agentic_harness.assessor.judge_grounded_refusal",
500:        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
504:        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
542:            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
593:def test_desired_edit_fails_closed_when_intent_judge_is_unavailable(
597:    output_dir = tmp_path / "desired-judge-unavailable"
605:        lambda *args, **kwargs: {"pass_": None, "error": "judge unavailable"},
611:            "id": "desired-judge-unavailable",
629:def test_desired_edit_fails_closed_on_fabricated_intent_judge_pass(
673:def test_desired_edit_fails_closed_on_fabricated_grounded_refusal_pass(
678:    (assessor.py grounded_refusal branch).  A fabricated pass_=true with a
682:    _write_safe_refusal_response(output_dir)
711:        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
1313:def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
1339:                "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
1346:    assert {issue["check"] for issue in verdict["assessment"]["issues"]} == {"safe_refusal"}
1493:                "allow_safe_refusal_outcome_kinds": ["respond", "clarify"],
1502:    assert "safe_refusal" in checks

exec
/bin/zsh -lc "nl -ba tests/test_live_agentic_harness_guard_contract.py | sed -n '360,730p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
   360	                    "ir_validate_ok": False,
   361	                    "lower_ok": False,
   362	                    "python_load_ok": False,
   363	                    "queue_validate_ok": False,
   364	                    "state_match_ok": True,
   365	                    "ui_emit_ok": False,
   366	                    "ui_fidelity_ok": False,
   367	                    "ui_load_safe_ok": False,
   368	                },
   369	                "message": "No schema-backed replacement node was found.",
   370	            }
   371	        ),
   372	        encoding="utf-8",
   373	    )
   374	    (output_dir / "implementation_result.json").write_text(
   375	        json.dumps({"message": "The graph is unchanged."}),
   376	        encoding="utf-8",
   377	    )
   378
   379	    scenario = {
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
   629	def test_desired_edit_fails_closed_on_fabricated_intent_judge_pass(
   630	    tmp_path: Path,
   631	    monkeypatch,
   632	) -> None:
   633	    """D13 rework: the assessor consumes the DERIVED intent-judge verdict
   634	    (assessor.py intent_judge branch).  A fabricated pass_=true with a false
   635	    criterion must fail the desired edit instead of passing it."""
   636	    output_dir = tmp_path / "desired-fabricated-intent-pass"
   637	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   638	    _write_successful_candidate(output_dir)
   639	    _write_ui_pair(output_dir, {"nodes": []}, {"nodes": [{"id": 1}]})
   640	    (output_dir / "implementation_result.json").write_text(
   641	        json.dumps({"status": "success"}), encoding="utf-8"
   642	    )
   643	    monkeypatch.setattr(
   644	        "tests.live_agentic_harness.intent_judge.run_model_turn",
   645	        lambda *args, **kwargs: {
   646	            "content": json.dumps(
   647	                {
   648	                    "pass_": True,
   649	                    "criteria": {
   650	                        "correct_node_targeted": True,
   651	                        "correct_parameter_changed": False,
   652	                        "value_semantically_matches_intent": True,
   653	                        "no_orphaned_wiring": True,
   654	                    },
   655	                    "rationale": "fabricated pass",
   656	                }
   657	            )
   658	        },
   659	    )
   660
   661	    verdict = guard_output_dir(
   662	        output_dir,
   663	        scenario=_desired_edit_scenario("desired-fabricated-intent-pass"),
   664	    )
   665
   666	    assert verdict["live_agentic_success"] is False
   667	    assert any(
   668	        issue["check"] == "intent_judge" and issue["severity"] == "error"
   669	        for issue in verdict["assessment"]["issues"]
   670	    )
   671
   672
   673	def test_desired_edit_fails_closed_on_fabricated_grounded_refusal_pass(
   674	    tmp_path: Path,
   675	    monkeypatch,
   676	) -> None:
   677	    """D13 rework: the assessor consumes the DERIVED grounded-refusal verdict
   678	    (assessor.py grounded_refusal branch).  A fabricated pass_=true with a
   679	    false criterion must fail the desired edit instead of passing it."""
   680	    output_dir = tmp_path / "desired-fabricated-refusal-pass"
   681	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   682	    _write_safe_refusal_response(output_dir)
   683	    (output_dir / "implementation_result.json").write_text(
   684	        json.dumps({"message": "The graph is unchanged."}), encoding="utf-8"
   685	    )
   686	    monkeypatch.setattr(
   687	        "tests.live_agentic_harness.intent_judge.run_model_turn",
   688	        lambda *args, **kwargs: {
   689	            "content": json.dumps(
   690	                {
   691	                    "pass_": True,
   692	                    "criteria": {
   693	                        "supported_blocker": True,
   694	                        "no_representable_edit": True,
   695	                        "specific_next_action": True,
   696	                        "no_fabricated_inability": False,
   697	                    },
   698	                    "rationale": "fabricated grounded refusal",
   699	                }
   700	            )
   701	        },
   702	    )
   703
   704	    verdict = guard_output_dir(
   705	        output_dir,
   706	        scenario=_desired_edit_scenario("desired-fabricated-refusal-pass"),
   707	    )
   708
   709	    assert verdict["live_agentic_success"] is False
   710	    assert any(
   711	        issue["check"] == "grounded_refusal" and issue["severity"] == "error"
   712	        for issue in verdict["assessment"]["issues"]
   713	    )
   714
   715
   716	def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
   717	    output_dir = tmp_path / "oversized-model-request"
   718	    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
   719	    (output_dir / "response.json").write_text(
   720	        json.dumps(
   721	            {
   722	                "ok": True,
   723	                "graph_unchanged": False,
   724	                "outcome": {"kind": "candidate"},
   725	                "candidate": {"nodes": [{"id": 1}]},
   726	                "change_details": {"landed_operation_count": 1},
   727	            }
   728	        ),
   729	        encoding="utf-8",
   730	    )

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json
from pathlib import Path
m=json.loads(Path(\"tests/live_agentic_harness/scenario_manifest.json\").read_text())
ss=[json.loads(Path(e[\"path\"]).read_text()) for e in m[\"entries\"] if e[\"inclusion_status\"]==\"included\"]
d=[s for s in ss if s.get(\"desired\")]
print({\"selected\":len(ss),\"desired\":len(d),\"desired_expect_change\":sum(s.get(\"assessment\",{}).get(\"expect_graph_changed\") is True for s in d),\"desired_skip_judge\":sum(s.get(\"assessment\",{}).get(\"skip_intent_judge\") is True for s in d),\"desired_safe_refusal\":sum(bool(s.get(\"assessment\",{}).get(\"allow_safe_refusal_outcome_kinds\") or s.get(\"assessment\",{}).get(\"allow_safe_refusal_outcome_kind\")) for s in d)})
print(\"bad desired:\",[s[\"id\"] for s in d if s.get(\"assessment\",{}).get(\"expect_graph_changed\") is not True or s.get(\"assessment\",{}).get(\"skip_intent_judge\") is True])
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 728ms:
{'selected': 100, 'desired': 42, 'desired_expect_change': 42, 'desired_skip_judge': 0, 'desired_safe_refusal': 3}
bad desired: []

codex
Manifest and source preflight currently hold: all 100 descriptor hashes and all 98 referenced source-workflow hashes match independently, including three manual spot checks. The corrected edits also target concrete existing fields (seed/fixed control, Moonvalley steps, SaveGLB prefix), so I’m now testing whether the semantic rubrics and judge paths are genuinely discriminating rather than merely present.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json
from pathlib import Path
m=json.loads(Path(\"tests/live_agentic_harness/scenario_manifest.json\").read_text())
for e in m[\"entries\"]:
 s=json.loads(Path(e[\"path\"]).read_text())
 if (s.get(\"classification\") or {}).get(\"kind\")==\"semantic_product\":
  r=s.get(\"answer_rubric\",{})
  print(\"\\n\"+s[\"id\"])
  print(\"  criteria:\",\" | \".join(r.get(\"expected_criteria\",[])))
  print(\"  evidence:\",json.dumps(r.get(\"required_node_evidence\"),sort_keys=True))
  print(\"  pass:\",r.get(\"pass_condition\"))
  print(\"  fail:\",\" | \".join(r.get(\"fail_conditions\",[])))
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 682ms:

audio-acestep-audio-generation-with-detail-daemon-f0859f
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Explain how DetailDaemon changes the sampling/detail path versus the standard KSampler path, and give cinematic-soundscape settings with trade-offs rather than unsupported magic values. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["DetailDaemonSamplerNode", "KSampler", "SamplerCustom", "BasicScheduler"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-animatediff-image-to-video-with-latent-composi-17dc9b
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Compare the graph's encoded-image LatentComposite path with direct init-image conditioning, including where each anchors structure and the likely temporal-coherence trade-off. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LatentComposite", "VAEEncode", "EmptyLatentImage", "AnimateDiffLoaderV1", "KSampler"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-dual-checkpoint-xl-image-generation-with-refin-c9df19
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Describe the base/refiner handoff visible in the two-checkpoint/two-sampler graph, compare current refiner or single-checkpoint options, and address whether LoRA is applied before or after the handoff. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["CheckpointLoaderSimple", "KSamplerAdvanced", "Power Lora Loader (rgthree)", "VAEDecode"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-gemini-prompt-splitter-and-text-display-workfl-caae97
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Compare Gemini and Claude for this multi-part prompt-generation role across output structure/quality, rate limits, and cost, while clearly separating graph facts from time-sensitive provider facts. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["GeminiNode", "VRGDG_PromptSplitter_General", "StringConcatenate", "ShowText|pysssss"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-image-processing-with-sharpening-film-grain-an-9aa0f1
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Name viable replacements for the current high-pass branch and compare halo risk, local contrast, noise amplification, masking, and blend-strength control in this graph. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["Image High Pass Filter", "VividSharpenV2", "Image Filter Adjustments", "ImageBlend", "BetterFilmGrain"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-image-to-image-with-ipadapter-and-controlnet-1999a9
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Identify the concrete IPAdapter and Canny/ControlNet influence controls, explain their interaction, and recommend a tuning order that preserves structure without eliminating style transfer. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["IPAdapterApply", "Canny", "ControlNetApply", "ControlNetLoader", "KSampler"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-llava-image-captioning-and-keyword-extraction-d38dc8
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Compare named captioning alternatives for longer detailed prompts and decide, with trade-offs, whether keyword extraction can be combined or should remain the graph's separate step. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LLavaPromptGenerator", "LLavaSamplerSimple", "KeywordExtraction", "JsonToText", "Suggester"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

image-qwen-image-inpainting-with-controlnet-09fc64
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Recommend Qwen-Image-Lightning/ControlNet color-consistency and mask-edge techniques that map to this encode/control/sample/decode pipeline, including feathering or compositing checks and relevant trade-offs. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["ControlNetInpaintingAliMamaApply", "ImagePadForOutpaint", "VAEEncode", "KSampler", "VAEDecode"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-3d-gaussian-splatting-from-video-with-hunyuan-432652
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Tie temporal geometry jitter to the workflow's preprocessing/depth-inference path and compare concrete temporally stable depth, camera, filtering, or point-cloud stabilization strategies. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["PreprocessImagesForHWM", "HWMInference", "VisualizeDepth", "Save3DGaussians", "SavePointCloud"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-ai-video-upscaling-with-detail-daemon-sampler-673197
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Prioritize plausible causes of both color shift and smeared detail in the SeedVR2/detail-daemon/sigma/VAE chain, and give discriminating checks before recommending parameter changes. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["SeedVR2VideoUpscaler", "DetailDaemonSamplerNode", "BetaSamplingScheduler", "Sigmas Rescale", "VAEDecode"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-animated-image-to-video-with-svd-and-lora-4ed6d9
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace the actual image-to-SVD-conditioning-to-sampling-to-WEBP flow, distinguish the two KSampler stages, and state where the LoRA-modified model enters. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["ImageOnlyCheckpointLoader", "SVD_img2vid_Conditioning", "LoraLoader", "KSampler", "SaveAnimatedWEBP"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-animatediff-video-generation-with-controlnet-a7e2af
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Compare the current UNet/AnimateDiff/ControlNet integration with a DiT migration, covering model/control compatibility, motion coherence, compute, and likely graph changes without pretending it is a drop-in swap. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["CheckpointLoaderSimple", "ADE_AnimateDiffLoaderWithContext", "ControlNetLoaderAdvanced", "ControlNetApplyAdvanced", "KSampler"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-audio-to-image-mel-band-roformer-workflow-b22937
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace the audio through MelBandRoFormer and explain separately why an MP3 is saved and why an image preview is produced, based on the actual output branches. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LoadAudio", "MelBandRoFormerModelLoader", "MelBandRoFormerSampler", "SaveAudioMP3", "PreviewImage"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-flux2-image-and-video-generation-with-outpaint-435de2
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Locate ColorMatch relative to generation/decoding/compositing, identify a graph-supported luminance mismatch mechanism, and propose checks that distinguish bad reference/mask/range settings from a broken color-match node. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["ImagePadForOutpaint", "DrawMaskOnImage", "ReferenceLatent", "VAEDecode", "ColorMatch", "ImageCompare"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-svd-image-to-video-with-animation-builder-99e2a9
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Rank workflow-specific causes for flicker, jitter, and black frames across conditioning, sampling, batch-history selection, animation assembly, and export, with a test that isolates each leading cause. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["SVD_img2vid_Conditioning", "KSampler", "Animation Builder (mtb)", "Get Batch From History (mtb)", "Export With Ffmpeg (mtb)"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-svd-image-to-video-with-sdxl-conditioning-389d90
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace every major stage to the WEBP output and accurately distinguish SDXL text conditioning from SVD's image/motion conditioning instead of claiming unsupported direct text control of SVD. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["CheckpointLoaderSimple", "CLIPTextEncode", "ImageOnlyCheckpointLoader", "SVD_img2vid_Conditioning", "KSampler", "SaveAnimatedWEBP"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Explain how the Lightning model patch and LoRA loaders feed sampling, and disambiguate the two strength controls by identifying what each applies to in this graph. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["DiffusionModelLoaderKJ", "LoraLoaderModelOnly", "ModelSamplingSD3", "KSamplerAdvanced", "EmptyHunyuanLatentVideo"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Identify the frame-varying grain source in the post-process branch, explain why independent/random per-frame grain flickers, and distinguish it from sharpening or model-sampling artifacts. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["VAEDecode", "FastUnsharpSharpen", "FastFilmGrain", "SaveImage", "Image Comparer (rgthree)"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-animatediff-video-to-video-with-controlnet-and-3c978e
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Walk the connected video-to-latent, ControlNet/LoRA/AnimateDiff model-conditioning, KSampler, decode, and combine path and explain which mechanisms preserve spatial versus temporal consistency. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["VHS_LoadVideo", "VAEEncode", "ControlNetLoaderAdvanced", "ControlNetApply", "LoraLoader", "ADE_AnimateDiffLoaderWithContext", "KSampler", "VHS_VideoCombine"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-animatediff-video-with-controlnet-and-depth-89b02a
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Compare named depth estimators or temporal-depth strategies and explain how their output normalization/stability must match the existing ControlNet guidance path. | Compare concrete alternatives and trade-offs, give a usable recommendation, and clearly distinguish inspected workflow evidence from external or time-sensitive claims. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["DownloadAndLoadDepthAnythingV2Model", "DepthAnything_V2", "ControlNetLoader", "ACN_AdvancedControlNetApply_v2", "ADE_UseEvolvedSampling"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-animatediff-video-with-ipadapter-and-controlne-4eebf3
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Test the tiling hypothesis against IPAdapterTiled and its tile/weight/application settings, explain the grid mechanism, and distinguish it from resize, ControlNet, VAE, or codec artifacts. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["IPAdapterTiled", "IPAdapterUnifiedLoader", "ImageResize+", "ACN_AdvancedControlNetApply", "SamplerCustom"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-hunyuan-video-text-to-video-generation-265847
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Prioritize causes that can affect later/high-motion frames while sparing the first, grounding the diagnosis in latent length/schedule/sampling/tiled decode/WEBP settings and proposing isolating checks. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["EmptyHunyuanLatentVideo", "BasicScheduler", "SamplerCustomAdvanced", "VAEDecodeTiled", "SaveAnimatedWEBP"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-hunyuanvideo-image-to-video-generation-with-en-ff076a
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace the image-conditioning and latent/noise-mask path, identify concrete disconnections or incompatible encoding/settings that could discard the first frame, and give ordered verification steps. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LoadImageFromUrl", "ImageResizeKJ", "HyVideoI2VEncode", "HyVideoEncode", "SetLatentNoiseMask", "HyVideoSampler", "HyVideoDecode"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-image-to-video-with-svd-and-webp-output-1882aa
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace the static image through SVD conditioning, CFG-guided sampling, decode, and WebP save, explaining the distinct roles and the motion-related SVD controls. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LoadImage", "ImageOnlyCheckpointLoader", "SVD_img2vid_Conditioning", "VideoLinearCFGGuidance", "KSampler", "VAEDecode", "SaveAnimatedWEBP"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-inpaint-and-video-composition-with-spline-path-0c2716
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Explain how spline coordinates drive the moving mask/cut path, how inpainting consumes image and mask, and how merge/combine nodes assemble the final frames without inventing absent tracking stages. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["SplineEditor", "CutAndDragOnPath", "INPAINT_LoadInpaintModel", "INPAINT_InpaintWithModel", "VHS_MergeImages", "VHS_VideoCombine"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-ltx-video-with-audio-and-inpainting-b3ba8a
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Connect sharp edges to the mask grow/blur/invert route and gray color to latent/encode/decode/blend compatibility, then give checks that separately isolate mask geometry and color-space/latent issues. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["ImageToMask", "GrowMaskWithBlur", "InvertMask", "LatentInpaintTTM", "LTXVImgToVideoInplace", "ImageBlend", "VAEDecodeTiled"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-seedvr2-video-upscaling-workflow-052e59
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace video loading/component extraction through the SeedVR2 DiT and VAE upscaler to video creation/save, accurately separating model restoration from VAE encoding/decoding and container assembly. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LoadVideo", "GetVideoComponents", "SeedVR2LoadDiTModel", "SeedVR2LoadVAEModel", "SeedVR2VideoUpscaler", "CreateVideo", "SaveVideo"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-video-loading-and-saving-workflow-1c7ad8
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Use the three custom-node connections and shared boolean inputs to explain each operation/output distinctly; unknown UUID node semantics must be derived from metadata/connections or stated as uncertain, not guessed. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LoadVideo", "LoadImage", "PrimitiveBoolean", "SaveVideo", "2dc75cab-e957-4437-a5bb-2afb0ea00516", "3ad0b41c-8c47-4e10-a53e-ed340cc26b5f", "b83ac947-e174-4a8e-b0c1-f7c3b8f00419"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-video-output-workflow-f855de
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Inspect the opaque custom-node metadata/settings and connections before naming a culprit for blur/banding; distinguish processing/range/bit-depth loss from SaveVideo codec settings and flag any unresolved UUID semantics. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["SaveVideo", "1cef296e-0f57-4f74-9e5e-7fe2b9097bcf", "61c3c7e8-7a92-4f27-8c3f-82eb62976f7b", "94adb7a7-527b-4ea8-92e0-9ab2ca8387c4"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-wan-video-generation-with-vace-and-multi-outpu-d1caec
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Explain why only the first batch item might be coherent by tracing batch slicing/order into VACE conditioning and latent length/masks, and separate that from global sampling causes of temporal flicker. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["ImageBatch", "ImageBatchMulti", "GetImageRangeFromBatch", "ReverseImageBatch", "WanVaceToVideo", "TrimVideoLatent", "KSamplerAdvanced"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Verify whether the high/low LoRA branches actually reach distinct model/sampling paths and diagnose brightness through latent concat/load/noise-mask/decode scaling, with tests for bypassed or identical inputs. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["UnetLoaderGGUF", "LoraLoaderModelOnly", "KSamplerAdvanced", "Frames Concat Latent", "LatentLoaderAdvanced", "SetLatentNoiseMask", "VAEDecode"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Describe the two loaded model/sampling paths from high-noise to low-noise stages and state whether the graph chains, combines, or merely exposes alternatives, based on actual edges rather than the title. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["UNETLoader", "ModelSamplingSD3", "KSamplerAdvanced", "EmptyHunyuanLatentVideo", "VAEDecode", "SaveAnimatedWEBP", "SaveWEBM"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Explain the sigma/noise-range handoff between the two UNet sampler stages and identify exactly where each LoRA-modified model is applied before decode/output. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["UNETLoader", "LoraLoaderModelOnly", "ModelSamplingSD3", "KSamplerAdvanced", "CreateVideo", "SaveVideo"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Tie degradation after frame 16 to explicit frame-window/trim/upscale or staged-sampling settings where supported, and give checks that distinguish context-boundary drift from LoRA/model or save artifacts. | Give a prioritized, causal diagnosis tied to concrete settings or connections, plus discriminating checks or remedies and explicit uncertainty where evidence is incomplete. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["UNETLoader", "LoraLoader", "SwarmKSampler", "SwarmTrimFrames", "LatentUpscaleBy", "SwarmSaveAnimationWS"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

video-wanvideo-text-to-video-generation-71f825
  criteria: Ground substantive claims in the inspected workflow, naming relevant nodes, settings, or connections from the required evidence; do not infer behavior from the scenario title alone. | Trace T5 and CLIP inputs through WanVideo text encoding, model sampling, VAE decode, and combine, accurately explaining conditioning and latent temporal generation without claiming the encoders themselves generate motion. | Give a coherent end-to-end explanation of the connected stages and their distinct causal roles; do not merely list node names. | Answer the user's actual question directly, with enough specific technical content to be useful and no workflow modification.
  evidence: ["LoadWanVideoT5TextEncoder", "LoadWanVideoClipTextEncoder", "WanVideoTextEncode", "WanVideoModelLoader", "WanVideoSampler", "WanVideoDecode", "VHS_VideoCombine"]
  pass: Pass only when the answer is grounded, relevant, technically correct, and satisfies every expected criterion.
  fail: hallucinated nodes, settings, connections, model behavior, citations, or provider facts | technically wrong or materially misleading claims | irrelevant or generic advice that does not address this workflow and question | vacuous node-name listing without causal explanation, comparison, or diagnosis | empty, whitespace-only, refusal-only, or structurally valid but substantively empty answer

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json
from pathlib import Path
m=json.loads(Path(\"tests/live_agentic_harness/scenario_manifest.json\").read_text())
missing=[]
for e in m[\"entries\"]:
 s=json.loads(Path(e[\"path\"]).read_text())
 if (s.get(\"classification\") or {}).get(\"kind\") "'!= "semantic_product": continue
 w=json.loads(Path(s["workflow_path"]).read_text())
 vals=set()
 def walk(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in {"type","class_type","title"} and isinstance(v,str): vals.add(v)
    walk(v)
  elif isinstance(x,list):
   for v in x: walk(v)
 walk(w)
 for req in s["answer_rubric"]["required_node_evidence"]:
  alts=req.split("|")
  if not any(a in vals for a in alts): missing.append((s["id"],req,sorted(v for v in vals if any(a.lower() in v.lower() or v.lower() in a.lower() for a in alts))[:5]))
print({"semantic":35,"required_evidence_items":sum(len(json.loads(Path(e["path"]).read_text()).get("answer_rubric",{}).get("required_node_evidence",[])) for e in m["entries"]),"missing_exact_or_alternative":len(missing)})
for x in missing: print(x)
'"' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 754ms:
{'semantic': 35, 'required_evidence_items': 197, 'missing_exact_or_alternative': 1}
('image-gemini-prompt-splitter-and-text-display-workfl-caae97', 'ShowText|pysssss', ['ShowText|pysssss'])

exec
/bin/zsh -lc 'for f in tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json tests/live_agentic_harness/scenarios/speed-distillation-research.json; do echo "$f"; jq . "$f"; done
rg -n "excluded_from_semantic_product_rates|semantic_product|health_control" tests/live_agentic_harness tests/test_live_agentic* | head -200' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 57ms:
{
  "id": "live-graph-explanation-smoke",
  "brief": "briefs/live-graph-explanation-smoke.md",
  "query": "Explain what this graph does. If anything important is missing, ask one clarifying question; otherwise inspect the workflow and answer directly.",
  "graph": {
    "1": {
      "class_type": "CheckpointLoaderSimple",
      "inputs": {
        "ckpt_name": "sd15.safetensors"
      }
    },
    "2": {
      "class_type": "CLIPTextEncode",
      "inputs": {
        "clip": [
          "1",
          1
        ],
        "text": "a quiet studio portrait"
      }
    },
    "3": {
      "class_type": "KSampler",
      "inputs": {
        "cfg": 7.0,
        "model": [
          "1",
          0
        ],
        "positive": [
          "2",
          0
        ],
        "steps": 20
      }
    }
  },
  "assessment": {
    "expect_graph_changed": false
  },
  "classification": {
    "kind": "health_control",
    "excluded_from_semantic_product_rates": true,
    "purpose": "Smoke-test that an inline graph can be inspected and answered without requiring a product-quality semantic score."
  }
}
tests/live_agentic_harness/scenarios/speed-distillation-research.json
{
  "id": "speed-distillation-research",
  "query": "This video workflow is too slow. Is there a distilled or faster way to run it without changing the creative intent?",
  "assessment": {
    "expect_graph_changed": false
  },
  "classification": {
    "kind": "health_control",
    "excluded_from_semantic_product_rates": true,
    "purpose": "Exercise the research route without a source graph; this is transport/routing health, not semantic product quality."
  }
}
tests/test_live_agentic_harness_corpus_manifest.py:54:    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
tests/test_live_agentic_harness_corpus_manifest.py:55:    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
tests/test_live_agentic_harness_corpus_manifest.py:64:    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
tests/live_agentic_harness/scenario_manifest.py:97:        if (scenario.get("classification") or {}).get("kind") == "health_control":
tests/live_agentic_harness/scenario_manifest.py:98:            scenario_kind = "health_control"
tests/live_agentic_harness/scenario_manifest.py:100:            scenario_kind = "semantic_product"
tests/live_agentic_harness/scenario_manifest.json:142:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:272:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:337:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:376:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:428:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:454:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:519:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:532:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:610:      "scenario_kind": "health_control",
tests/live_agentic_harness/scenario_manifest.json:619:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:645:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:658:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:684:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:697:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:736:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:814:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:827:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:892:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:905:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:931:      "scenario_kind": "health_control",
tests/live_agentic_harness/scenario_manifest.json:940:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:953:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:966:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1005:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1018:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1044:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1057:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1083:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1096:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1174:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1187:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1213:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1226:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1252:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1265:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1278:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenario_manifest.json:1291:      "scenario_kind": "semantic_product",
tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json:34:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json:32:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json:34:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/speed-distillation-research.json:8:    "kind": "health_control",
tests/live_agentic_harness/scenarios/speed-distillation-research.json:9:    "excluded_from_semantic_product_rates": true,
tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json:42:    "kind": "health_control",
tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json:43:    "excluded_from_semantic_product_rates": true,
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json:33:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json:35:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json:36:    "kind": "semantic_product"
tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json:33:    "kind": "semantic_product"

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/REVISIONS.md
nl -ba tests/live_agentic_harness/README.md | sed -n '1,220p'
git diff --unified=50 0f015101..ea421528 -- tests/live_agentic_harness/REVISIONS.md tests/live_agentic_harness/README.md .gitignore" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 37ms:
diff --git a/.gitignore b/.gitignore
index c3dd200c..8659492c 100644
--- a/.gitignore
+++ b/.gitignore
@@ -29,50 +29,51 @@ temp/

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
 .venv
+external_workflows
diff --git a/tests/live_agentic_harness/README.md b/tests/live_agentic_harness/README.md
index f1a222b4..fe42cf50 100644
--- a/tests/live_agentic_harness/README.md
+++ b/tests/live_agentic_harness/README.md
@@ -1,49 +1,55 @@
 # Live Agentic Tests

 This directory is for **live agentic tests only**: real executor paths with
 real model/provider calls.

 A test belongs here only when the subject-under-test is a real model or agent
 using production-like tools, and the evidence comes from the actual run. Fake or
 faking actors, deterministic builders, scripted `messages.jsonl`, and structural
 contract scenarios do not belong here.

+The selected live lane is fixed by `scenario_manifest.json`. Before starting
+scenario subprocesses, the runner validates descriptor IDs/paths/hashes,
+source-workflow IDs/paths/hashes, and exact directory membership. A missing,
+changed, duplicate, or stray descriptor fails preflight. `--manifest` can select
+another equally strict manifest for an explicit scenario directory.
+
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
diff --git a/tests/live_agentic_harness/REVISIONS.md b/tests/live_agentic_harness/REVISIONS.md
new file mode 100644
index 00000000..85f615d3
--- /dev/null
+++ b/tests/live_agentic_harness/REVISIONS.md
@@ -0,0 +1,22 @@
+# Live-agentic corpus revisions
+
+This log distinguishes query/coverage revisions from descriptors whose original
+scenario intent remains matched. `scenario_manifest.json` records the same split
+as `revision_status: revised|matched`.
+
+## D13
+
+Three edit descriptors were revised because their original requests targeted
+controls that the referenced source workflow does not expose. No scenario was
+replaced and all three retain their original source workflow and modality.
+
+| Scenario | Before | After | Coverage retained |
+| --- | --- | --- | --- |
+| `video-video-inpainting-with-spline-based-cut-and-dra-485ff2` | Set nonexistent inpaint denoising strength to `0.6`; expected no graph change. | Set `INPAINT_InpaintWithModel` seed from `534667941392889` to `42`, keep control fixed; graph change and desired-outcome judge required. | Low-level video-inpainting parameter edit without disturbing spline/composite stages. |
+| `video-image-to-video-conversion-with-moonvalley-d7853c` | Change frame count/FPS for five seconds, though Moonvalley exposes neither; expected no graph change. | Change Moonvalley generation steps from `100` to `80`, preserve prompt adherence `7`; graph change and desired-outcome judge required. | Low-level Moonvalley generation parameter edit and downstream video-save integrity. |
+| `multi-3d-preview-and-image-output-workflow-d93baf` | Make a normal-map `PreviewImage` top-down as though it were a camera-controlled 3D preview; expected no graph change. | Change `SaveGLB` filename prefix from `3d/ComfyUI` to `3d/moge-top-down`, preserving mesh and both normal-preview branches; graph change and desired-outcome judge required. | Low-level 3D output parameter edit and multi-branch integrity. |
+
+The 35 research/explain/diagnose descriptors received semantic answer rubrics
+without changing their original queries or source workflows, so they remain
+`matched`. The two non-product smoke scenarios were marked as health controls;
+that classification change is not a query rewrite.

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json,subprocess
from pathlib import Path
scdir=Path(\"tests/live_agentic_harness/scenarios\")
now={p.name:json.loads(p.read_text()) for p in scdir.glob(\"*.json\")}
base_names=subprocess.check_output([\"git\",\"ls-tree\",\"-r\",\"--name-only\",\"0f015101\",\"tests/live_agentic_harness/scenarios\"],text=True).splitlines()
base={}
for n in base_names:
 if n.endswith(\".json\"):
  base[Path(n).name]=json.loads(subprocess.check_output([\"git\",\"show\",f\"0f015101:{n}\"],text=True))
print({\"base\":len(base),\"now\":len(now),\"added\":sorted(set(now)-set(base)),\"removed\":sorted(set(base)-set(now))})
for field in (\"id\",\"query\",\"workflow_path\"):
 changed=sorted(k for k in set(base)&set(now) if base[k].get(field)"'!=now[k].get(field))
 print(field,"changed",len(changed),changed)
mods=sorted(k for k in set(base)&set(now) if base[k]!=now[k])
print("modified descriptors",len(mods))
'"' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 4909ms:
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
{'base': 100, 'now': 100, 'added': [], 'removed': []}
id changed 0 []
query changed 3 ['multi-3d-preview-and-image-output-workflow-d93baf.json', 'video-image-to-video-conversion-with-moonvalley-d7853c.json', 'video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json']
workflow_path changed 0 []
modified descriptors 40

exec
/bin/zsh -lc "git log --oneline --reverse 0f015101..ea421528 && git diff --check 0f015101..ea421528 && git diff --numstat 0f015101..ea421528 -- ':"'!.oracle/checkins/batch-D13.md'"' ':"'!.oracle/briefs/**'"'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 273ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
b39f0c91 megado D13: authoritative 100-scenario manifest (SHA-256), manifest-driven runner discovery, 3 mislabeled edits corrected, 35 semantic rubrics, 2 health controls, REVISIONS.md — 71 focused tests green
5aa73c53 megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green
ea421528 megado D13 rework2: judge verdicts derived from criteria, never model self-declared pass_ — string-typed booleans/contradictory verdicts fail closed; 78 focused tests green
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
1	0	.gitignore
6	0	tests/live_agentic_harness/README.md
22	0	tests/live_agentic_harness/REVISIONS.md
81	33	tests/live_agentic_harness/assessor.py
215	14	tests/live_agentic_harness/intent_judge.py
19	4	tests/live_agentic_harness/runner.py
1299	0	tests/live_agentic_harness/scenario_manifest.json
261	0	tests/live_agentic_harness/scenario_manifest.py
27	0	tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json
28	0	tests/live_agentic_harness/scenarios/image-animatediff-image-to-video-with-latent-composi-17dc9b.json
27	0	tests/live_agentic_harness/scenarios/image-dual-checkpoint-xl-image-generation-with-refin-c9df19.json
27	0	tests/live_agentic_harness/scenarios/image-gemini-prompt-splitter-and-text-display-workfl-caae97.json
28	0	tests/live_agentic_harness/scenarios/image-image-processing-with-sharpening-film-grain-an-9aa0f1.json
28	0	tests/live_agentic_harness/scenarios/image-image-to-image-with-ipadapter-and-controlnet-1999a9.json
28	0	tests/live_agentic_harness/scenarios/image-llava-image-captioning-and-keyword-extraction-d38dc8.json
28	0	tests/live_agentic_harness/scenarios/image-qwen-image-inpainting-with-controlnet-09fc64.json
8	0	tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json
28	0	tests/live_agentic_harness/scenarios/multi-3d-gaussian-splatting-from-video-with-hunyuan-432652.json
8	5	tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json
28	0	tests/live_agentic_harness/scenarios/multi-ai-video-upscaling-with-detail-daemon-sampler-673197.json
28	0	tests/live_agentic_harness/scenarios/multi-animated-image-to-video-with-svd-and-lora-4ed6d9.json
28	0	tests/live_agentic_harness/scenarios/multi-animatediff-video-generation-with-controlnet-a7e2af.json
28	0	tests/live_agentic_harness/scenarios/multi-audio-to-image-mel-band-roformer-workflow-b22937.json
29	0	tests/live_agentic_harness/scenarios/multi-flux2-image-and-video-generation-with-outpaint-435de2.json
28	0	tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-animation-builder-99e2a9.json
29	0	tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-sdxl-conditioning-389d90.json
28	0	tests/live_agentic_harness/scenarios/multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14.json
28	0	tests/live_agentic_harness/scenarios/multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6.json
5	0	tests/live_agentic_harness/scenarios/speed-distillation-research.json
31	0	tests/live_agentic_harness/scenarios/video-animatediff-video-to-video-with-controlnet-and-3c978e.json
28	0	tests/live_agentic_harness/scenarios/video-animatediff-video-with-controlnet-and-depth-89b02a.json
28	0	tests/live_agentic_harness/scenarios/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json
28	0	tests/live_agentic_harness/scenarios/video-hunyuan-video-text-to-video-generation-265847.json
30	0	tests/live_agentic_harness/scenarios/video-hunyuanvideo-image-to-video-generation-with-en-ff076a.json
7	4	tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json
30	0	tests/live_agentic_harness/scenarios/video-image-to-video-with-svd-and-webp-output-1882aa.json
29	0	tests/live_agentic_harness/scenarios/video-inpaint-and-video-composition-with-spline-path-0c2716.json
30	0	tests/live_agentic_harness/scenarios/video-ltx-video-with-audio-and-inpainting-b3ba8a.json
30	0	tests/live_agentic_harness/scenarios/video-seedvr2-video-upscaling-workflow-052e59.json
8	5	tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json
30	0	tests/live_agentic_harness/scenarios/video-video-loading-and-saving-workflow-1c7ad8.json
27	0	tests/live_agentic_harness/scenarios/video-video-output-workflow-f855de.json
30	0	tests/live_agentic_harness/scenarios/video-wan-video-generation-with-vace-and-multi-outpu-d1caec.json
30	0	tests/live_agentic_harness/scenarios/video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9.json
30	0	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3.json
29	0	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a.json
29	0	tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9.json
30	0	tests/live_agentic_harness/scenarios/video-wanvideo-text-to-video-generation-71f825.json
148	0	tests/test_live_agentic_harness_corpus_manifest.py
357	0	tests/test_live_agentic_harness_guard_contract.py
3	0	tests/test_live_agentic_harness_runner_persistence.py
244	1	tests/test_live_agentic_intent_judge_schema_context.py
9	0	tests/test_live_agentic_runner_persistence.py
43	0	vibecomfy/intent/prompts/refusal_judge.prompt.md

exec
/bin/zsh -lc "rg --files tests | rg 'runner_persistence|structural_harness_runner|guard_contract|corpus_manifest|intent_judge_schema_context'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
tests/test_live_agentic_intent_judge_schema_context.py
tests/test_structural_harness_runner.py
tests/test_live_agentic_harness_guard_contract.py
tests/test_live_agentic_harness_runner_persistence.py
tests/test_live_agentic_harness_corpus_manifest.py
tests/test_live_agentic_runner_persistence.py

codex
The semantic rubric audit is substantive: 35/35 include workflow-specific node evidence, a tailored expected-answer criterion, an explicit grounded/relevant/correct pass condition, and the five required failure modes. All 197 cited evidence items resolve in their source workflows. The two controls are separately typed and explicitly excluded; the three edit rewrites are the only query changes across the 100-file corpus. I’m moving to the requested test slice and hygiene checks.
  ✓ Read D13 acceptance criteria and inventory the exact commit delta
  ✓ Audit manifest integrity, runner rejection paths, corrected edits, rubrics, judge behavior, revisions, and source hashes
  → Run diff hygiene and focused test slices permitted by the read-only sandbox
  • Issue binary D13 verdict with per-focus evidence and precise rework if needed
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:rerunfailures -p no:cacheprovider tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_intent_judge_schema_context.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 exited 1 in 2549ms:
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
The full pytest slice cannot start in this read-only sandbox: pytest has no writable temporary directory (even capture setup fails), so this is an environment limitation rather than a test failure. I’ll still run the pure, no-temp D13 tests with capture disabled, then supplement them with direct read-only invariant checks.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:rerunfailures -p no:cacheprovider tests/test_live_agentic_harness_corpus_manifest.py::test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios tests/test_live_agentic_harness_corpus_manifest.py::test_d13_no_change_reconciliation_and_rubric_contract tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_string_false_pass_with_all_criteria_true_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_pass_true_with_false_criterion_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_string_typed_criteria_booleans_are_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_pass_true_with_missing_criteria_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_missing_pass_field_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_genuine_all_true_is_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_refusal_verdict_genuine_all_true_is_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_refusal_verdict_string_false_pass_with_all_criteria_true_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_refusal_verdict_pass_true_with_false_criterion_is_not_pass' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 6579ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
...........
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
11 passed, 1 warning in 3.02s

exec
/bin/zsh -lc "rg -n '"'^def test_'"' tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_intent_judge_schema_context.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
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
tests/test_live_agentic_intent_judge_schema_context.py:44:def test_parse_verdict_string_false_pass_with_all_criteria_true_is_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:54:def test_parse_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:65:def test_parse_verdict_string_typed_criteria_booleans_are_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:83:def test_parse_verdict_pass_true_with_missing_criteria_is_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:94:def test_parse_verdict_missing_pass_field_is_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:103:def test_parse_verdict_genuine_all_true_is_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:112:def test_parse_refusal_verdict_genuine_all_true_is_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:121:def test_parse_refusal_verdict_string_false_pass_with_all_criteria_true_is_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:129:def test_parse_refusal_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
tests/test_live_agentic_intent_judge_schema_context.py:140:def test_intent_judge_surfaces_derived_fail_for_fabricated_pass(
tests/test_live_agentic_intent_judge_schema_context.py:169:def test_grounded_refusal_judge_surfaces_derived_fail_for_fabricated_pass(
tests/test_live_agentic_intent_judge_schema_context.py:201:def test_intent_judge_includes_scenario_desired_rubric(
tests/test_live_agentic_intent_judge_schema_context.py:252:def test_intent_judge_includes_compiled_api_schema_context(
tests/test_live_agentic_intent_judge_schema_context.py:328:def test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input(
tests/test_live_agentic_intent_judge_schema_context.py:423:def test_intent_judge_recomputes_schema_context_for_sidecar_less_envelope(
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
tests/test_live_agentic_harness_guard_contract.py:629:def test_desired_edit_fails_closed_on_fabricated_intent_judge_pass(
tests/test_live_agentic_harness_guard_contract.py:673:def test_desired_edit_fails_closed_on_fabricated_grounded_refusal_pass(
tests/test_live_agentic_harness_guard_contract.py:716:def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:752:def test_agentic_guard_rejects_forbidden_model_request_substrings(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:791:def test_agentic_guard_rejects_static_widget_edit_overridden_by_link(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:812:def test_agentic_guard_rejects_no_effective_value_change_for_claimed_target(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:833:def test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1021:def test_agentic_guard_matcher_only_scenarios_pass_without_prose_gating(
tests/test_live_agentic_harness_guard_contract.py:1050:def test_agentic_guard_false_landed_claim_still_fails_via_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1091:def test_agentic_guard_false_unchanged_claim_still_fails_via_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1135:def test_agentic_guard_false_connection_claim_still_fails_via_effective_edit_check(
tests/test_live_agentic_harness_guard_contract.py:1167:def test_agentic_guard_false_validation_success_claim_still_fails_via_gates(
tests/test_live_agentic_harness_guard_contract.py:1240:def test_agentic_guard_expected_edit_requires_positive_landed_count(
tests/test_live_agentic_harness_guard_contract.py:1275:def test_agentic_guard_expected_edit_with_positive_landed_count_passes(
tests/test_live_agentic_harness_guard_contract.py:1313:def test_agentic_guard_exempts_grounded_refusal_from_landed_count(
tests/test_live_agentic_harness_guard_contract.py:1354:def test_agentic_guard_rejects_edit_route_self_relabeled_as_clarify(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1391:def test_agentic_guard_rejects_route_not_applyable_without_landed_count(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1427:def test_agentic_guard_rejects_failure_outcome_without_landed_count(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1464:def test_agentic_guard_exempts_genuine_non_edit_route_with_unchanged_graph(
tests/test_live_agentic_harness_guard_contract.py:1507:def test_agentic_guard_non_edit_route_still_scored_by_own_structured_checks(
tests/test_live_agentic_harness_guard_contract.py:1549:def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1570:def test_agentic_guard_allows_shared_linked_source_edit_when_declared(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1588:def test_agentic_guard_treats_skipped_queue_validation_as_warning(tmp_path: Path) -> None:
tests/test_live_agentic_harness_guard_contract.py:1625:def test_agentic_guard_product_fails_real_queue_validation_failure(tmp_path: Path) -> None:
tests/test_structural_harness_runner.py:15:def test_runner_help_exposes_repo_local_options(capsys: pytest.CaptureFixture[str]) -> None:
tests/test_structural_harness_runner.py:31:def test_main_forwards_actor_tag_defaults_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
tests/test_structural_harness_runner.py:73:def test_run_chaining_family_adapts_to_reports_dir_api_shape(monkeypatch: pytest.MonkeyPatch) -> None:
tests/test_structural_harness_runner.py:125:def test_structural_runner_rejects_live_agent_actors() -> None:
tests/test_structural_harness_runner.py:130:def test_structural_runner_rejects_live_mode() -> None:
tests/test_structural_harness_runner.py:143:def test_assessor_parse_failure_is_retried_once() -> None:
tests/test_structural_harness_runner.py:161:def test_assessor_parse_failure_retry_is_bounded() -> None:
tests/test_structural_harness_runner.py:177:def test_assessor_rubric_failure_is_not_retried() -> None:
tests/test_live_agentic_harness_corpus_manifest.py:30:def test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios() -> None:
tests/test_live_agentic_harness_corpus_manifest.py:52:def test_d13_no_change_reconciliation_and_rubric_contract() -> None:
tests/test_live_agentic_harness_corpus_manifest.py:90:def test_runner_rejects_unmanifested_descriptor_before_execution(tmp_path: Path) -> None:
tests/test_live_agentic_harness_corpus_manifest.py:104:def test_manifest_discovery_rejects_changed_or_missing_descriptor(tmp_path: Path) -> None:
tests/test_live_agentic_harness_corpus_manifest.py:119:def test_manifest_discovery_rejects_duplicate_id_and_path(tmp_path: Path) -> None:
tests/test_live_agentic_harness_corpus_manifest.py:134:def test_manifest_discovery_rejects_duplicate_path_with_distinct_id(tmp_path: Path) -> None:

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:rerunfailures -p no:cacheprovider tests/test_structural_harness_runner.py tests/test_live_agentic_runner_persistence.py::test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed tests/test_live_agentic_runner_persistence.py::test_retryability_is_derived_from_canonical_typed_evidence' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 11176ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
..........
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
10 passed, 1 warning in 8.15s

exec
/bin/zsh -lc "git diff --unified=30 0f015101..ea421528 -- tests/live_agentic_harness/assessor.py tests/live_agentic_harness/intent_judge.py vibecomfy/intent/prompts/refusal_judge.prompt.md | sed -n '1,1200p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/live_agentic_harness/assessor.py b/tests/live_agentic_harness/assessor.py
index 42388790..8a50ef27 100644
--- a/tests/live_agentic_harness/assessor.py
+++ b/tests/live_agentic_harness/assessor.py
@@ -1,59 +1,59 @@
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

@@ -782,96 +782,144 @@ def assess_live_output_dir(
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

diff --git a/tests/live_agentic_harness/intent_judge.py b/tests/live_agentic_harness/intent_judge.py
index b935d2d4..23b361f1 100644
--- a/tests/live_agentic_harness/intent_judge.py
+++ b/tests/live_agentic_harness/intent_judge.py
@@ -1,97 +1,197 @@
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
-    criteria = parsed.get("criteria") or {}
-    normalized_criteria = {
-        "correct_node_targeted": bool(criteria.get("correct_node_targeted")),
-        "correct_parameter_changed": bool(criteria.get("correct_parameter_changed")),
-        "value_semantically_matches_intent": bool(criteria.get("value_semantically_matches_intent")),
-        "no_orphaned_wiring": bool(criteria.get("no_orphaned_wiring")),
-    }
+    return text
+
+
+_EDIT_CRITERION_KEYS = (
+    "correct_node_targeted",
+    "correct_parameter_changed",
+    "value_semantically_matches_intent",
+    "no_orphaned_wiring",
+)
+
+_REFUSAL_CRITERION_KEYS = (
+    "supported_blocker",
+    "no_representable_edit",
+    "specific_next_action",
+    "no_fabricated_inability",
+)
+
+
+def _strict_boolean(value: Any) -> bool | None:
+    """Return *value* iff it is an explicit JSON boolean (Python ``bool``).
+
+    JSON ``true``/``false`` decode to Python ``bool``.  Anything else —
+    including the strings ``"true"``/``"false"`` — is malformed and returns
+    None so callers fail closed instead of coercing with ``bool()``.
+    """
+    if type(value) is bool:
+        return value
+    return None
+
+
+def _derive_verdict(parsed: Any, criterion_keys: tuple[str, ...]) -> dict[str, Any]:
+    """Normalize a parsed judge response, deriving ``pass_`` from the criteria.
+
+    The model's self-declared ``pass_`` is never trusted: the verdict is True
+    only when the response is a JSON object whose ``pass_`` is an explicit
+    boolean and every required criterion is an explicit ``true`` boolean.  Any
+    criterion that is false, missing, or not a strict boolean (including the
+    strings ``"false"``/``"true"``), any non-boolean or absent ``pass_``, and
+    any non-object response fail the verdict closed — malformed output is a
+    fail, never a pass.  Only genuinely unparsable JSON (json.loads raising
+    in the caller) stays undetermined (``pass_`` None).
+    """
+    if not isinstance(parsed, dict):
+        return {"pass_": False, "criteria": {}, "rationale": ""}
+    self_declared = _strict_boolean(parsed.get("pass_"))
+    criteria_raw = parsed.get("criteria")
+    criteria: dict[str, Any] = {}
+    if isinstance(criteria_raw, dict):
+        for key in criterion_keys:
+            value = _strict_boolean(criteria_raw.get(key))
+            if value is not None:
+                criteria[key] = value
+    all_criteria_pass = all(criteria.get(key) is True for key in criterion_keys)
     return {
-        "pass_": bool(parsed.get("pass_")),
-        "criteria": normalized_criteria,
+        "pass_": self_declared is not None and all_criteria_pass,
+        "criteria": criteria,
         "rationale": str(parsed.get("rationale", "")),
     }


+def _parse_verdict(raw: str) -> dict[str, Any]:
+    """Parse the judge's JSON response into a normalized dict.
+
+    ``pass_`` is derived from the criteria (fail closed), never from the
+    model's self-declared ``pass_``: it is True iff every required criterion
+    is an explicit JSON boolean ``true`` and ``pass_`` itself is an explicit
+    boolean.  String-typed booleans, missing criteria, false criteria, and
+    contradictory self-declarations all fail closed.
+    """
+    parsed = json.loads(_strip_code_fences(raw))
+    return _derive_verdict(parsed, _EDIT_CRITERION_KEYS)
+
+
+def _parse_refusal_verdict(raw: str) -> dict[str, Any]:
+    """Parse the grounded-refusal judge's JSON response into a normalized dict.
+
+    Same fail-closed contract as :func:`_parse_verdict`: the verdict is
+    derived from the four refusal criteria (supported blocker, no
+    representable edit, specific next action, no fabricated inability), not
+    from the model's self-declared ``pass_``.
+    """
+    parsed = json.loads(_strip_code_fences(raw))
+    return _derive_verdict(parsed, _REFUSAL_CRITERION_KEYS)
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
@@ -346,30 +446,131 @@ def judge_edit_intent(
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
diff --git a/vibecomfy/intent/prompts/refusal_judge.prompt.md b/vibecomfy/intent/prompts/refusal_judge.prompt.md
new file mode 100644
index 00000000..0f4983ee
--- /dev/null
+++ b/vibecomfy/intent/prompts/refusal_judge.prompt.md
@@ -0,0 +1,43 @@
+You are a precise evaluator for ComfyUI workflow edits. A model was asked
+to perform an edit but refused and left the workflow graph unchanged, citing
+a reason. You must determine whether that refusal is GROUNDED (the model
+could not honestly satisfy the intent) or fabricated/unsupported (the model
+dodged an edit it could have made).
+
+Evaluate the refusal against exactly four binary criteria:
+
+**R1 — supported_blocker**: The refusal cites a real, supported blocker
+rather than a made-up constraint. For example, a `requires_custom_nodes`
+refusal is supported only when the node class the edit would need is
+genuinely absent from the installed schema; a `clarify` refusal is supported
+only when the request has a genuine ambiguity that prevents a correct edit.
+
+**R2 — no_representable_edit**: No representable edit to the given workflow
+could satisfy the intent, so refusing was the only honest option. If a
+parameter change, node replacement, or node addition on the existing graph
+could have satisfied the request, this criterion fails.
+
+**R3 — specific_next_action**: The refusal states a concrete next action that
+would unblock the edit (for example, installing a named custom node, or
+answering a named clarifying question). A refusal that just says "cannot do
+this" without any path forward fails this criterion.
+
+**R4 — no_fabricated_inability**: The refusal does not falsely claim an
+inability. Claiming a node class is unavailable when the schema contains it,
+or claiming the request is ambiguous when it is concrete, is a fabricated
+inability and fails this criterion.
+
+Respond with a JSON object and nothing else:
+{
+  "pass_": true | false,
+  "criteria": {
+    "supported_blocker": true | false,
+    "no_representable_edit": true | false,
+    "specific_next_action": true | false,
+    "no_fabricated_inability": true | false
+  },
+  "rationale": "<one or two sentences citing the specific refusal evidence for any failing criterion>"
+}
+
+`pass_` must be true if and only if all four criteria are true.
+Do not add any text before or after the JSON object.

exec
/bin/zsh -lc 'rg -n "CHECKPOINT VERDICT|FAIL|Issue|Finding|pass_.*false|contradict|rework" .oracle/checkins/batch-D13.md | head -160' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 0ms:
46:First line: `D13 CHECKPOINT VERDICT: PASS|FAIL — <one line>`.
47:Then per-focus findings (1–9) with evidence, and an issue list if FAIL (file:line + rework). Be adversarial but fair.
65:- **Oracle** — GPT-5.6 Sol or Grok 4.6 (grok CLI): gates every batch; rework until it passes.
227:  • Issue binary D13 verdict with per-focus evidence and precise rework if needed
236:ea421528 megado D13 rework2: judge verdicts derived from criteria, never model self-declared pass_ — string-typed booleans/contradictory verdicts fail closed; 78 focused tests green
546: .oracle/briefs/batch-D13-rework.md                 |   33 +
547: .oracle/briefs/batch-D13-rework2.md                |   38 +
606:A	.oracle/briefs/batch-D13-rework.md
607:A	.oracle/briefs/batch-D13-rework2.md
670:  • Issue binary D13 verdict with per-focus evidence and precise rework if needed
2390:   815	        # edit, specific next action, no fabricated inability), and it FAILS
2521:   150	    contradictory self-declarations all fail closed.
3205:   633	    """D13 rework: the assessor consumes the DERIVED intent-judge verdict
3206:   634	    (assessor.py intent_judge branch).  A fabricated pass_=true with a false
3249:   677	    """D13 rework: the assessor consumes the DERIVED grounded-refusal verdict
4003:5aa73c53 megado D13 rework: desired-edit refusal cannot bypass judge — grounded-refusal gate required, fabricated clarify/requires_custom_nodes fail closed; manifest detects judge-bypass configs — 73 focused tests green
4004:ea421528 megado D13 rework2: judge verdicts derived from criteria, never model self-declared pass_ — string-typed booleans/contradictory verdicts fail closed; 78 focused tests green
4077:  • Issue binary D13 verdict with per-focus evidence and precise rework if needed
4160:/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:rerunfailures -p no:cacheprovider tests/test_live_agentic_harness_corpus_manifest.py::test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios tests/test_live_agentic_harness_corpus_manifest.py::test_d13_no_change_reconciliation_and_rubric_contract tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_string_false_pass_with_all_criteria_true_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_pass_true_with_false_criterion_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_string_typed_criteria_booleans_are_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_pass_true_with_missing_criteria_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_missing_pass_field_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_verdict_genuine_all_true_is_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_refusal_verdict_genuine_all_true_is_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_refusal_verdict_string_false_pass_with_all_criteria_true_is_not_pass tests/test_live_agentic_intent_judge_schema_context.py::test_parse_refusal_verdict_pass_true_with_false_criterion_is_not_pass' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
4188:tests/test_live_agentic_intent_judge_schema_context.py:54:def test_parse_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
4195:tests/test_live_agentic_intent_judge_schema_context.py:129:def test_parse_refusal_verdict_pass_true_with_false_criterion_is_not_pass() -> None:
4311: _UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
4371:+        # edit, specific next action, no fabricated inability), and it FAILS
4505:         for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
4554:         '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
4588:+        '{"pass_": true | false, "criteria": {"supported_blocker": true | false, '
4682:+    contradictory self-declarations all fail closed.
4899:+  "pass_": true | false,

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json
from tests.live_agentic_harness.intent_judge import _parse_verdict,_parse_refusal_verdict
edit={\"pass_\":False,\"criteria\":{\"correct_node_targeted\":True,\"correct_parameter_changed\":True,\"value_semantically_matches_intent\":True,\"no_orphaned_wiring\":True},\"rationale\":\"contradiction\"}
ref={\"pass_\":False,\"criteria\":{\"supported_blocker\":True,\"no_representable_edit\":True,\"specific_next_action\":True,\"no_fabricated_inability\":True},\"rationale\":\"contradiction\"}
print(\"edit contradictory false/all-true =>\",_parse_verdict(json.dumps(edit)))
print(\"refusal contradictory false/all-true =>\",_parse_refusal_verdict(json.dumps(ref)))
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 2131ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
Could not locate ComfyUI root (no server.py + nodes.py found).
Could not register VibeComfy agent routes (No module named 'comfy'); the ComfyUI server may not be available. POST /vibecomfy/agent-edit and /vibecomfy/agent/status will not be served.
edit contradictory false/all-true => {'pass_': True, 'criteria': {'correct_node_targeted': True, 'correct_parameter_changed': True, 'value_semantically_matches_intent': True, 'no_orphaned_wiring': True}, 'rationale': 'contradiction'}
refusal contradictory false/all-true => {'pass_': True, 'criteria': {'supported_blocker': True, 'no_representable_edit': True, 'specific_next_action': True, 'no_fabricated_inability': True}, 'rationale': 'contradiction'}

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/runner.py | sed -n '25,58p'
nl -ba tests/live_agentic_harness/runner.py | sed -n '760,850p'
nl -ba tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json | sed -n '1,45p'
nl -ba tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json | sed -n '1,45p'
nl -ba tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json | sed -n '1,45p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 56ms:
   760	    parser.add_argument(
   761	        "--analysis-timeout",
   762	        type=int,
   763	        default=DEFAULT_AGENT_TIMEOUT_S,
   764	        help=f"Seconds before killing one failure diagnosis agent (default {DEFAULT_AGENT_TIMEOUT_S}).",
   765	    )
   766	    parser.add_argument(
   767	        "--restart-failure-analysis",
   768	        action="store_true",
   769	        help="Rerun every failed-scenario diagnosis, including ones already marked done.",
   770	    )
   771	    parser.add_argument(
   772	        "--recommend-fixes",
   773	        action="store_true",
   774	        help="Use Codex/GPT-5.5 to synthesize all failure diagnoses into ranked fix recommendations.",
   775	    )
   776	    parser.add_argument(
   777	        "--recommendations-model",
   778	        default=DEFAULT_RECOMMENDATIONS_MODEL,
   779	        help=f"Model for aggregate fix recommendations (default {DEFAULT_RECOMMENDATIONS_MODEL}).",
   780	    )
   781	    parser.add_argument(
   782	        "--recommendations-timeout",
   783	        type=int,
   784	        default=DEFAULT_AGENT_TIMEOUT_S,
   785	        help=f"Seconds before killing aggregate recommendations (default {DEFAULT_AGENT_TIMEOUT_S}).",
   786	    )
   787	    parser.add_argument(
   788	        "--analyze-existing-summary",
   789	        default=None,
   790	        help=(
   791	            "Analyze an existing run_summary.json or redirected summary JSON instead of running scenarios."
   792	        ),
   793	    )
   794	    return parser
   795
   796
   797	def main(argv: list[str] | None = None) -> int:
   798	    parser = _build_parser()
   799	    args = parser.parse_args(argv)
   800
   801	    scenarios_dir = Path(args.scenarios_dir) if args.scenarios_dir else Path(__file__).with_name("scenarios")
   802
   803	    if args.analyze_existing_summary:
   804	        analysis = _run_failure_analysis_from_summary(
   805	            Path(args.analyze_existing_summary),
   806	            scenarios_dir=scenarios_dir,
   807	            analyze_failures_enabled=args.analyze_failures,
   808	            prepare_only=args.prepare_failure_analysis
   809	            or not (args.analyze_failures or args.recommend_fixes),
   810	            recommend_fixes=args.recommend_fixes,
   811	            analysis_model=args.analysis_model,
   812	            analysis_max_workers=args.analysis_max_workers,
   813	            analysis_timeout=args.analysis_timeout,
   814	            resume_failure_analysis=not args.restart_failure_analysis,
   815	            recommendations_model=args.recommendations_model,
   816	            recommendations_timeout=args.recommendations_timeout,
   817	        )
   818	        print(json.dumps({"failure_analysis": analysis}, indent=2, default=str))
   819	        return 0
   820
   821	    if not args.tag:
   822	        parser.error("--tag is required unless --analyze-existing-summary is used")
   823
   824	    if args.single:
   825	        out_file = Path(args.single_out) if args.single_out else None
   826	        ob = Path(args.output_base) if args.output_base else None
   827	        summary = run_single(args.single, args.tag, ob, out_file)
   828	        # Compact one-line stdout for liveness; the real payload is in --single-out.
   829	        print(json.dumps({"scenario_id": summary.get("scenario_id"),
   830	                          "ok": summary["guard"]["live_agentic_success"]}))
   831	        return 0 if summary["guard"]["live_agentic_success"] else 1
   832
   833	    output_base = Path(args.output_base) if args.output_base else None
   834	    summary = run_tag(
   835	        args.tag,
   836	        scenarios_dir=scenarios_dir,
   837	        output_base=output_base,
   838	        max_workers=args.max_workers,
   839	        per_scenario_timeout=args.per_scenario_timeout,
   840	        progress_every=args.progress_every,
   841	        infra_retries=args.infra_retries,
   842	        manifest_path=Path(args.manifest) if args.manifest else None,
   843	    )
   844	    if args.prepare_failure_analysis or args.analyze_failures or args.recommend_fixes:
   845	        run_summary_path = _run_dir_for(output_base, summary["tag"]) / "run_summary.json"
   846	        analysis = _run_failure_analysis_from_summary(
   847	            run_summary_path,
   848	            scenarios_dir=scenarios_dir,
   849	            analyze_failures_enabled=args.analyze_failures,
   850	            prepare_only=args.prepare_failure_analysis,
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
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 pytest --collect-only -q -s -p no:rerunfailures -p no:cacheprovider tests/test_live_agentic_harness_runner_persistence.py tests/test_live_agentic_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_harness_corpus_manifest.py tests/test_live_agentic_intent_judge_schema_context.py | tail -5
PYTHONDONTWRITEBYTECODE=1 python -c '
import ast,subprocess
files=[p for p in subprocess.check_output([\"git\",\"diff\",\"--name-only\",\"0f015101..ea421528\"],text=True).splitlines() if p.endswith(\".py\")]
for p in files: ast.parse(open(p,encoding=\"utf-8\").read(),filename=p)
print(f\"AST parsed {len(files)} changed Python files\")
' " in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 5038ms:
OMP: Warning #179: Function Can't set size of /tmp file failed:
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
110 tests collected in 2.19s
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
AST parsed 9 changed Python files

exec
/bin/zsh -lc "nl -ba tests/live_agentic_harness/scenarios/audio-acestep-audio-generation-with-detail-daemon-f0859f.json | sed -n '1,70p'
nl -ba tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json | sed -n '35,52p'
nl -ba tests/live_agentic_harness/scenarios/speed-distillation-research.json | sed -n '1,20p'
nl -ba tests/test_live_agentic_harness_corpus_manifest.py | sed -n '30,150p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
 succeeded in 1ms:
All nine focus areas are audited. Independent hash checks are clean, the committed diff is hygienic and D13-scoped, 21 no-temp tests passed, and the remaining temp-writing portion of the focused slice is blocked solely by the read-only sandbox having no writable temporary directory.
  ✓ Read D13 acceptance criteria and inventory the exact commit delta
  ✓ Audit manifest integrity, runner rejection paths, corrected edits, rubrics, judge behavior, revisions, and source hashes
  ✓ Run diff hygiene and focused test slices permitted by the read-only sandbox
  ✓ Issue binary D13 verdict with per-focus evidence and precise rework if needed
codex
D13 CHECKPOINT VERDICT: PASS — The committed corpus is pinned, satisfiable, manifest-driven, and fail-closed for desired edits.

1. Manifest integrity: PASS. The manifest selects exactly 100 included scenarios with 100 unique, stem-matched IDs and paths; classifications are 63 edits, 35 semantic products, and 2 health controls. Revision split is 97 matched/3 revised, with 98 source workflows. Independent recomputation found zero descriptor or source hash mismatches. Three manual descriptor/source spot checks also matched. See [scenario_manifest.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:134) and [manifest tests](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:30).

2. Runner discovery: PASS. `_scenario_paths()` delegates to manifest discovery before execution in [runner.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:44). Validation rejects duplicate IDs/paths, missing or changed descriptors, ID/stem mismatches, source mismatches, and unmanifested files in [scenario_manifest.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:161). Explicit rejection tests cover all requested cases in [test_live_agentic_harness_corpus_manifest.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:90).

3. Corrected edits: PASS. All three now set `apply: true`, expect graph changes, and carry concrete `desired` rubrics:

   - `485ff2`: nonexistent denoise request → seed `534667941392889` to `42`, retaining fixed control.
   - `d7853c`: nonexistent duration controls → Moonvalley steps `100` to `80`, preserving adherence `7`.
   - `d93baf`: nonexistent preview camera control → SaveGLB prefix change.

   The target values exist in their source workflows, and parameterized guard tests prove the scenarios cannot pass as no-ops. See the three descriptors beginning at [485ff2](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:2), [d7853c](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:2), and [d93baf](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:2).

4. Semantic rubrics and controls: PASS. All 35 semantic non-edits have workflow-specific evidence, at least four expected criteria, grounded/relevant/correct pass language, and explicit hallucinated/wrong/irrelevant/vacuous/empty failure conditions. All 197 required evidence references resolve in their source workflows. Both controls are typed `health_control` and explicitly excluded from semantic-product rates; see [live smoke](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json:41) and [speed research](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/speed-distillation-research.json:7).

5. Active desired-edit judges: PASS. All 42 selected scenarios containing `desired` expect a graph change; none sets `skip_intent_judge`. Changed candidates feed `judge_edit_intent`; allowlisted unchanged refusals feed `judge_grounded_refusal`. Missing, failed, empty, or unparsable judge results become error-level findings for desired edits in [assessor.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:809). Tests cover judge outage, fabricated passes/refusals, grounded refusal, and no-op rejection.

6. Revision accounting: PASS. [REVISIONS.md](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/REVISIONS.md:7) records the before/after intent and retained coverage for exactly three revised scenarios. Independent base-versus-head comparison found no added or removed descriptors, no ID changes, no source-path changes, and only those three query changes.

7. Source-workflow resolution: PASS. `external_workflows` resolves to the provisioned 2,827-file corpus. All 98 applicable `workflow_path` values exist, and every manifest source ID/path/SHA-256 validates. The two health controls are the only scenarios without source workflows.

8. Scope and hygiene: PASS. The exact range contains 58 files rather than the stale 47-file executor summary because it includes D13 briefs/check-in artifacts and both rework commits. Every changed file is attributable to D13 corpus, discovery, judging, documentation, or regression coverage. `git diff --check 0f015101..ea421528` is clean. The working-copy modification to `.oracle/checkins/batch-D13.md` was outside the committed comparison; review used the stated commit objects.

9. Tests: PASS within sandbox limits. The full focused invocation with `-p no:rerunfailures` could not initialize because the read-only sandbox exposes no writable temporary directory. With capture disabled, 21 applicable no-temp tests passed: 11 manifest/judge tests and 10 structural/runner tests. The complete six-file slice collected successfully as 110 tests, and all nine changed Python files parsed successfully. No test produced a product failure.
tokens used
169,435
D13 CHECKPOINT VERDICT: PASS — The committed corpus is pinned, satisfiable, manifest-driven, and fail-closed for desired edits.

1. Manifest integrity: PASS. The manifest selects exactly 100 included scenarios with 100 unique, stem-matched IDs and paths; classifications are 63 edits, 35 semantic products, and 2 health controls. Revision split is 97 matched/3 revised, with 98 source workflows. Independent recomputation found zero descriptor or source hash mismatches. Three manual descriptor/source spot checks also matched. See [scenario_manifest.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:134) and [manifest tests](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:30).

2. Runner discovery: PASS. `_scenario_paths()` delegates to manifest discovery before execution in [runner.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:44). Validation rejects duplicate IDs/paths, missing or changed descriptors, ID/stem mismatches, source mismatches, and unmanifested files in [scenario_manifest.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:161). Explicit rejection tests cover all requested cases in [test_live_agentic_harness_corpus_manifest.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/test_live_agentic_harness_corpus_manifest.py:90).

3. Corrected edits: PASS. All three now set `apply: true`, expect graph changes, and carry concrete `desired` rubrics:

   - `485ff2`: nonexistent denoise request → seed `534667941392889` to `42`, retaining fixed control.
   - `d7853c`: nonexistent duration controls → Moonvalley steps `100` to `80`, preserving adherence `7`.
   - `d93baf`: nonexistent preview camera control → SaveGLB prefix change.

   The target values exist in their source workflows, and parameterized guard tests prove the scenarios cannot pass as no-ops. See the three descriptors beginning at [485ff2](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json:2), [d7853c](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/video-image-to-video-conversion-with-moonvalley-d7853c.json:2), and [d93baf](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/multi-3d-preview-and-image-output-workflow-d93baf.json:2).

4. Semantic rubrics and controls: PASS. All 35 semantic non-edits have workflow-specific evidence, at least four expected criteria, grounded/relevant/correct pass language, and explicit hallucinated/wrong/irrelevant/vacuous/empty failure conditions. All 197 required evidence references resolve in their source workflows. Both controls are typed `health_control` and explicitly excluded from semantic-product rates; see [live smoke](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/live-graph-explanation-smoke.json:41) and [speed research](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenarios/speed-distillation-research.json:7).

5. Active desired-edit judges: PASS. All 42 selected scenarios containing `desired` expect a graph change; none sets `skip_intent_judge`. Changed candidates feed `judge_edit_intent`; allowlisted unchanged refusals feed `judge_grounded_refusal`. Missing, failed, empty, or unparsable judge results become error-level findings for desired edits in [assessor.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:809). Tests cover judge outage, fabricated passes/refusals, grounded refusal, and no-op rejection.

6. Revision accounting: PASS. [REVISIONS.md](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/REVISIONS.md:7) records the before/after intent and retained coverage for exactly three revised scenarios. Independent base-versus-head comparison found no added or removed descriptors, no ID changes, no source-path changes, and only those three query changes.

7. Source-workflow resolution: PASS. `external_workflows` resolves to the provisioned 2,827-file corpus. All 98 applicable `workflow_path` values exist, and every manifest source ID/path/SHA-256 validates. The two health controls are the only scenarios without source workflows.

8. Scope and hygiene: PASS. The exact range contains 58 files rather than the stale 47-file executor summary because it includes D13 briefs/check-in artifacts and both rework commits. Every changed file is attributable to D13 corpus, discovery, judging, documentation, or regression coverage. `git diff --check 0f015101..ea421528` is clean. The working-copy modification to `.oracle/checkins/batch-D13.md` was outside the committed comparison; review used the stated commit objects.

9. Tests: PASS within sandbox limits. The full focused invocation with `-p no:rerunfailures` could not initialize because the read-only sandbox exposes no writable temporary directory. With capture disabled, 21 applicable no-temp tests passed: 11 manifest/judge tests and 10 structural/runner tests. The complete six-file slice collected successfully as 110 tests, and all nine changed Python files parsed successfully. No test produced a product failure.
