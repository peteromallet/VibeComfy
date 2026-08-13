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
exec
/bin/zsh -lc "git show 4a16fc64:.oracle/tasklist.md | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
/bin/zsh -lc 'git status --short --branch && git rev-parse HEAD && git branch --show-current && git diff --stat 4a16fc64..b016576b && git diff --name-status 4a16fc64..b016576b' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git diff --check 4a16fc64..b016576b && git log --oneline --decorate -5 b016576b' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
b016576b megado run2 Batch A: canonical corpus migration (XHARD) — migrate script, hardened checker, re-anchored tests, CI fixture
4a16fc64 megado run2: frozen plan + tasklist (A→B→D+E→C→K) + exploration findings
0f515870 (origin/main) megado: elegant VibeWorkflow declaration — P0-P10 (lossless envelope, to_envelope/from_envelope, named importers, first-class mode/groups, ir/ + dead snapshots deleted)
dbbe7aa5 (elegance-transform) megado P10: first-class VibeNode.mode + VibeWorkflow.groups + derived copy()
594a25a8 megado P6: named graph importers (from_envelope/from_ui/from_api); detect_workflow_shape private; edit_ingest uses nodes-is-list

 succeeded in 62ms:
2b60f74aa52a6cefb40dffd01475c0a6781154c8
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
elegance-run2
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
/bin/zsh -lc "git show b016576b:scripts/migrate_external_workflow_corpus.py | nl -ba | sed -n '1,460p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git show b016576b:scripts/check_b02_rich_preservation.py | nl -ba | sed -n '1,340p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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

 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
/bin/zsh -lc 'git diff 4a16fc64..b016576b -- Makefile tests/test_b02_rich_preservation.py tests/test_ingest_external_workflows.py tests/test_porting_normalize_ingest.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/Makefile b/Makefile
index a8c17d09..5a178ea3 100644
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
+		--corpus-dir "$(CORPUS_DIR)" --expected-count 2797
+
 browser-smoke:
 	$(NODE) --test tests/browser/*.mjs
 
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

exec
/bin/zsh -lc "git show b016576b:scripts/check_b02_rich_preservation.py | nl -ba | sed -n '1,180p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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

exec
/bin/zsh -lc "git show b016576b:scripts/check_b02_rich_preservation.py | nl -ba | sed -n '180,430p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
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

exec
/bin/zsh -lc "git show b016576b:scripts/check_b02_rich_preservation.py | nl -ba | sed -n '430,760p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
/bin/zsh -lc 'git diff 4a16fc64..b016576b -- scripts/check_b02_rich_preservation.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/scripts/check_b02_rich_preservation.py b/scripts/check_b02_rich_preservation.py
index 29f1ec9a..e0d39d2c 100644
--- a/scripts/check_b02_rich_preservation.py
+++ b/scripts/check_b02_rich_preservation.py
@@ -5,10 +5,10 @@ For every serialized-Vibe envelope in ``external_workflows/corpus/*.json``
 full canonical pipeline and prove deterministic lossless preservation at every
 boundary:
 
-    rich ──convert_to_vibe_format──▶ ir1 ──normalize_agent_edit_graph──▶ canonical
-         ──normalize_to_api(use_comfy_converter=False)──▶ api ──convert_to_vibe_format──▶ ir2
-         ──emit_ui_json(groups=canonical groups)──▶ reemit
-         pin evidence: emit_ui_json(ir1, recovery_report=report, groups=rich groups)
+    rich ──from_envelope──▶ ir1 ──normalize_agent_edit_graph──▶ canonical
+         ──normalize_to_api(use_comfy_converter=False)──▶ api ──from_api──▶ ir2
+         ──emit_ui_json (using ir2.groups)──▶ reemit
+         pin evidence: emit_ui_json(ir1, recovery_report=report)
 
 Axes asserted (every mismatch records ``(file, axis, node, expected, actual)``
 and fails the run):
@@ -35,7 +35,8 @@ and fails the run.
 
 Run as a CLI to get one final JSON summary on stdout:
 
-    .venv/bin/python scripts/check_b02_rich_preservation.py
+    .venv/bin/python scripts/check_b02_rich_preservation.py \
+        --corpus-dir tests/fixtures/b02_corpus_mini --expected-count 3
 
 Exit code is 0 iff zero mismatches and zero uid-less emissions.
 """
@@ -51,7 +52,7 @@ from pathlib import Path
 from typing import Any
 
 from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
-from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
+from vibecomfy.ingest import from_api, from_envelope, normalize_to_api
 from vibecomfy.porting.emit.ui import emit_ui_json
 from vibecomfy.porting.refuse import RefusedEmit
 
@@ -60,7 +61,7 @@ from vibecomfy.porting.refuse import RefusedEmit
 # comparisons by contract.
 _RENUMBERED_KEYS: frozenset[str] = frozenset({"id", "order", "link", "links"})
 
-_SCHEMA_LESS_WARNING = "schema-less"
+_SCHEMA_LESS_WARNING = ".*schema-less.*"
 
 
 # ---------------------------------------------------------------------------
@@ -86,13 +87,26 @@ def _ui_of(metadata: Any) -> dict[str, Any]:
     return ui if isinstance(ui, dict) else {}
 
 
-def _mode_of(metadata: Any) -> int:
-    """Node mode: raw ``_ui.mode`` when present, else top-level metadata mode, else 0."""
+def _legacy_mode_of(metadata: Any) -> int:
+    """Legacy mode: raw ``_ui.mode``, then top-level metadata mode, else 0."""
     ui = _ui_of(metadata)
-    if "mode" in ui:
+    if isinstance(ui.get("mode"), int) and not isinstance(ui["mode"], bool):
         return ui["mode"]
     value = metadata.get("mode")
-    return value if isinstance(value, int) else 0
+    return value if isinstance(value, int) and not isinstance(value, bool) else 0
+
+
+def _mode_of(entry: Any) -> int:
+    """First-class node mode, with legacy metadata fallback for old envelopes."""
+    if isinstance(entry, dict):
+        value = entry.get("mode")
+        if isinstance(value, int) and not isinstance(value, bool):
+            return value
+        return _legacy_mode_of(entry.get("metadata") or {})
+    value = getattr(entry, "mode", None)
+    if isinstance(value, int) and not isinstance(value, bool):
+        return value
+    return _legacy_mode_of(getattr(entry, "metadata", {}))
 
 
 def _widgets_values_of(metadata: Any) -> Any:
@@ -127,7 +141,7 @@ def rich_node_projection(node_id: str, entry: dict[str, Any]) -> dict[str, Any]:
         "id": entry.get("id"),
         "class_type": entry.get("class_type"),
         "uid": entry.get("uid"),
-        "mode": _mode_of(metadata),
+        "mode": _mode_of(entry),
         "raw_widgets": _raw_widgets_projection(entry.get("raw_widgets")),
         "widgets_values": _widgets_values_of(metadata),
         "furniture": _strip_renumbered(_ui_of(metadata)),
@@ -141,7 +155,7 @@ def ir_node_projection(node: Any) -> dict[str, Any]:
         "id": node.id,
         "class_type": node.class_type,
         "uid": node.uid,
-        "mode": _mode_of(metadata),
+        "mode": _mode_of(node),
         "raw_widgets": _raw_widgets_projection(node.raw_widgets),
         "widgets_values": _widgets_values_of(metadata),
         "furniture": _strip_renumbered(_ui_of(metadata)),
@@ -259,12 +273,13 @@ def check_envelope(raw: dict[str, Any]) -> dict[str, Any]:
         _record(result, axis, node, expected, actual)
         return result
 
-    ir1 = convert_to_vibe_format(raw)
+    ir1 = from_envelope(raw)
+    ir1.groups = deepcopy(raw.get("groups") or [])
 
     # ── pin evidence: emit directly with recovery_report + the rich groups ──
     recovery_report: list[dict[str, Any]] = []
     try:
-        pin_envelope = _emit(ir1, recovery_report=recovery_report, groups=raw.get("groups"))
+        pin_envelope = _emit(ir1, recovery_report=recovery_report)
     except RefusedEmit as exc:
         node_id, reason = _refusal_detail(exc)
         return fail("emit_refused", node_id, "emission must succeed", reason)
@@ -294,8 +309,9 @@ def check_envelope(raw: dict[str, Any]) -> dict[str, Any]:
     try:
         canonical = normalize_agent_edit_graph(raw)
         api2 = normalize_to_api(canonical, use_comfy_converter=False)
-        ir2 = convert_to_vibe_format(api2)
-        reemit = _emit(ir2, groups=canonical.get("groups"))
+        ir2 = from_api(api2)
+        ir2.groups = deepcopy(canonical.get("groups") or [])
+        reemit = _emit(ir2)
     except RefusedEmit as exc:
         node_id, reason = _refusal_detail(exc)
         return fail("emit_refused", node_id, "emission must succeed", reason)
@@ -474,20 +490,51 @@ def _refusal_detail(exc: RefusedEmit) -> tuple[Any, str]:
 # ---------------------------------------------------------------------------
 
 
+def _corpus_paths(corpus_dir: str | Path) -> tuple[Path, list[Path]]:
+    """Validate an explicit corpus directory and return its JSON paths."""
+    root = Path(corpus_dir)
+    if root.name.endswith(".layout.json"):
+        raise ValueError(f"layout sidecar cannot be used as a corpus directory: {root}")
+    if not root.exists():
+        raise FileNotFoundError(f"corpus directory does not exist: {root}")
+    if not root.is_dir():
+        raise NotADirectoryError(f"corpus path is not a directory: {root}")
+    paths = sorted(root.glob("*.json"))
+    envelope_paths = [path for path in paths if not path.name.endswith(".layout.json")]
+    if not envelope_paths:
+        raise ValueError(f"corpus directory contains zero envelopes: {root}")
+    return root, paths
+
+
 def iter_corpus(corpus_dir: str | Path):
     """Yield ``(path, raw)`` for every serialized-Vibe envelope in the corpus.
 
     Non-envelope ``*.json`` files (e.g. ``.layout.json`` sidecar stores) are
     skipped and reported in the aggregate ``skipped_non_envelopes`` counter.
     """
-    for path in sorted(Path(corpus_dir).glob("*.json")):
+    _, paths = _corpus_paths(corpus_dir)
+    found = 0
+    for path in paths:
+        if path.name.endswith(".layout.json"):
+            continue
         raw = json.loads(path.read_text(encoding="utf-8"))
-        if not isinstance(raw.get("nodes"), dict) or "vibecomfy_format_version" not in raw:
+        if (
+            not isinstance(raw, dict)
+            or not isinstance(raw.get("nodes"), dict)
+            or "vibecomfy_format_version" not in raw
+        ):
             continue
+        found += 1
         yield path, raw
+    if found == 0:
+        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
 
 
-def check_corpus(corpus_dir: str | Path = "external_workflows/corpus") -> dict[str, Any]:
+def check_corpus(
+    corpus_dir: str | Path,
+    *,
+    expected_count: int | None = None,
+) -> dict[str, Any]:
     """Run :func:`check_envelope` over the whole corpus and aggregate counts.
 
     Deterministic: files are processed in sorted order and all set comparisons
@@ -496,6 +543,9 @@ def check_corpus(corpus_dir: str | Path = "external_workflows/corpus") -> dict[s
     """
     summary: dict[str, Any] = {
         "ok": True,
+        "checked": 0,
+        "skipped": 0,
+        "skipped_sidecars": 0,
         "workflows": 0,
         "skipped_non_envelopes": 0,
         "rich_nodes": 0,
@@ -510,17 +560,29 @@ def check_corpus(corpus_dir: str | Path = "external_workflows/corpus") -> dict[s
         "refused_files": [],
         "mismatch_rows": [],
     }
-    for path in sorted(Path(corpus_dir).glob("*.json")):
+    _, paths = _corpus_paths(corpus_dir)
+    for path in paths:
         name = path.name
+        if name.endswith(".layout.json"):
+            summary["skipped"] += 1
+            summary["skipped_sidecars"] += 1
+            continue
         try:
             raw = json.loads(path.read_text(encoding="utf-8"))
         except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
+            summary["skipped"] += 1
             _record_row(summary, name, "exception", None, "JSON must parse", f"{type(exc).__name__}: {exc}")
             continue
-        if not isinstance(raw.get("nodes"), dict) or "vibecomfy_format_version" not in raw:
+        if (
+            not isinstance(raw, dict)
+            or not isinstance(raw.get("nodes"), dict)
+            or "vibecomfy_format_version" not in raw
+        ):
+            summary["skipped"] += 1
             summary["skipped_non_envelopes"] += 1
             continue
 
+        summary["checked"] += 1
         summary["workflows"] += 1
         result = check_envelope(raw)
         result["file"] = name
@@ -537,8 +599,16 @@ def check_corpus(corpus_dir: str | Path = "external_workflows/corpus") -> dict[s
             if axis == "emit_refused":
                 summary["refused_files"].append([name, _truncate(node), _truncate(actual)])
 
+    if summary["checked"] == 0:
+        raise ValueError(f"corpus directory contains zero envelopes: {corpus_dir}")
+    summary["expected_count"] = expected_count
+    summary["count_matches"] = expected_count is None or summary["checked"] == expected_count
     summary["mismatch_count"] = len(summary["mismatch_rows"])
-    summary["ok"] = summary["mismatch_count"] == 0 and summary["uidless"] == 0
+    summary["ok"] = (
+        summary["mismatch_count"] == 0
+        and summary["uidless"] == 0
+        and summary["count_matches"]
+    )
     return summary
 
 
@@ -565,12 +635,20 @@ def main(argv: list[str] | None = None) -> int:
     parser = argparse.ArgumentParser(description=__doc__)
     parser.add_argument(
         "--corpus-dir",
-        default="external_workflows/corpus",
-        help="directory of serialized-Vibe corpus envelopes (default: %(default)s)",
+        required=True,
+        help="explicit directory of serialized-Vibe corpus envelopes",
+    )
+    parser.add_argument(
+        "--expected-count",
+        type=int,
+        help="fail unless exactly this many envelopes are checked",
     )
     args = parser.parse_args(argv)
 
-    summary = check_corpus(args.corpus_dir)
+    try:
+        summary = check_corpus(args.corpus_dir, expected_count=args.expected_count)
+    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
+        parser.error(str(exc))
     print(json.dumps(summary, indent=2, sort_keys=True))
     return 0 if summary["ok"] else 1
 

codex
The first concrete discrepancy is in the committed full-corpus target: the reviewed commit still expects 2,797 checked envelopes, while the supplied corpus evidence establishes 2,825 actual envelopes and explicitly says the target uses 2,825. I’m continuing the audit for any additional independent gate failures before issuing the binary verdict.
exec
/bin/zsh -lc 'git diff --numstat 4a16fc64..b016576b -- tests/fixtures/b02_corpus_mini && for f in $(git diff --name-only 4a16fc64..b016576b -- tests/fixtures/b02_corpus_mini); do git show b016576b:$f | python -m json.tool >/dev/null || exit 1; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git show b016576b:scripts/migrate_external_workflow_corpus.py | nl -ba | sed -n '130,205p' && git show b016576b:tests/test_b02_rich_preservation.py | nl -ba | sed -n '70,195p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git show --format=fuller --stat b016576b && git diff-tree --no-commit-id --name-only -r b016576b | rg -n 'manifest|shadow|external_workflows' || true" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git show b016576b:Makefile | nl -ba | sed -n '172,198p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 39ms:
   172	full-pytest:
   173		PYTHONHASHSEED=0 $(PYTEST) -n 8 -q -p no:cacheprovider
   174	
   175	snapshots:
   176		$(PYTHON) -m tools.regenerate_snapshots --check
   177	
   178	oracle:
   179		VIBECOMFY_COMFY_SMOKE=1 $(PYTEST) -q --tb=short \
   180			tests/test_porting_ui_emitter.py::test_layer3_corpus_wide_convert_ui_to_api_gate
   181	
   182	b02-corpus-mini:
   183		PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
   184			--corpus-dir "$(B02_MINI_CORPUS)" --expected-count 3
   185	
   186	b02-corpus-full:
   187		@if [ -z "$(CORPUS_DIR)" ]; then \
   188			echo "CORPUS_DIR is required (no default full-corpus path)."; \
   189			exit 2; \
   190		fi
   191		PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
   192			--corpus-dir "$(CORPUS_DIR)" --expected-count 2797
   193	
   194	browser-smoke:
   195		$(NODE) --test tests/browser/*.mjs
   196	
   197	# Standalone subset of browser-smoke; pure Node/browser-contract coverage without Playwright or ComfyUI prerequisites (browser-smoke already runs all tests/browser/*.mjs).
   198	browser-contracts:

 succeeded in 84ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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

 succeeded in 127ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit b016576b730e9c58a7364da6d6dd836258366ac8
Author:     POM <peter@omalley.io>
AuthorDate: Thu Aug 13 14:08:14 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Thu Aug 13 14:08:14 2026 +0200

    megado run2 Batch A: canonical corpus migration (XHARD) — migrate script, hardened checker, re-anchored tests, CI fixture

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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
9:tests/test_ingest_external_workflows.py

 succeeded in 2644ms:
432	0	tests/fixtures/b02_corpus_mini/001cd1f527f7f288.layout.json
523	0	tests/fixtures/b02_corpus_mini/42188130f0d8021b.json
1647	0	tests/fixtures/b02_corpus_mini/90a1d5ff9044902e.json
409	0	tests/fixtures/b02_corpus_mini/bbb556b30438a62c.json
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc "git grep -n \"def from_envelope\\|def to_envelope\\|def _get_node_mode\\|mode=\" b016576b -- vibecomfy | head -200" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git grep -n \"compiled_api\\|node_modes_defaulted_to_zero\\|expected-count 2797\\|expected-count 2825\" b016576b -- ':"'!tests/fixtures/**'"'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git diff b016576b..2b60f74 -- Makefile scripts/migrate_external_workflow_corpus.py scripts/check_b02_rich_preservation.py tests/test_b02_rich_preservation.py | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 76ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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

 succeeded in 1452ms:
b016576b:vibecomfy/comfy_nodes/agent/_frag_chat.py:137:            compatibility_mode=True,
b016576b:vibecomfy/comfy_nodes/agent/_frag_chat.py:156:            compatibility_mode=True,
b016576b:vibecomfy/comfy_nodes/agent/_frag_ingest.py:272:    messages = build_messages(task=state.task, python_source=state.python_before, execution_mode="sandboxed_loose")
b016576b:vibecomfy/comfy_nodes/agent/contracts.py:1617:                compatibility_mode=compatibility_mode,
b016576b:vibecomfy/comfy_nodes/agent/contracts.py:1668:            compatibility_mode=compatibility_mode,
b016576b:vibecomfy/comfy_nodes/agent/contracts.py:1766:            compatibility_mode=compatibility_mode,
b016576b:vibecomfy/comfy_nodes/agent/contracts.py:1776:            compatibility_mode=compatibility_mode,
b016576b:vibecomfy/comfy_nodes/agent/layout_reorganisation.py:168:        return ReorganiseAutoConfig(mode=_DEFAULT_MODE, raw_value=raw)
b016576b:vibecomfy/comfy_nodes/agent/layout_reorganisation.py:173:            mode=normalized,  # type: ignore[arg-type]
b016576b:vibecomfy/comfy_nodes/agent/layout_reorganisation.py:178:        mode="off",
b016576b:vibecomfy/comfy_nodes/agent/layout_reorganisation.py:263:        mode=config.mode,
b016576b:vibecomfy/comfy_nodes/agent/provider.py:1063:    messages = build_messages(task=task, python_source=python_source, execution_mode="sandboxed_loose")
b016576b:vibecomfy/comfy_nodes/agent/runtime.py:452:        quiet_mode=True,
b016576b:vibecomfy/comfy_nodes/agent/runtime_code.py:569:        compile(ast.parse(payload["source"], mode="eval"), "<runtime_code_expression>", "eval"),
b016576b:vibecomfy/comfy_nodes/agent/runtime_code.py:615:            result = _run_sandboxed(payload, mode="sandboxed_strict")
b016576b:vibecomfy/comfy_nodes/agent/runtime_code.py:617:            result = _run_sandboxed(payload, mode="sandboxed_loose")
b016576b:vibecomfy/comfy_nodes/agent/worker.py:212:        mode="default",
b016576b:vibecomfy/comfy_nodes/agent/worker.py:349:                api_mode=api_mode,
b016576b:vibecomfy/commands/port/_check.py:45:        mode=port_mode,
b016576b:vibecomfy/commands/port/_convert.py:61:            mode=port_mode,
b016576b:vibecomfy/commands/port/_export.py:592:                    json_mode=bool(getattr(args, "json", False)),
b016576b:vibecomfy/commands/port/_export.py:598:                _print_from_overrides(from_overrides, json_mode=bool(getattr(args, "json", False)))
b016576b:vibecomfy/commands/port/_export.py:602:                _print_recovery_report(recovery_report, json_mode=bool(getattr(args, "json", False)))
b016576b:vibecomfy/commands/port/_export.py:614:                    _print_recovery_report(recovery_report, json_mode=bool(getattr(args, "json", False)))
b016576b:vibecomfy/commands/port/_export.py:615:                _emit_refused_emit(exc, json_mode=bool(getattr(args, "json", False)))
b016576b:vibecomfy/commands/port/_repair.py:15:            mode=args.mode,
b016576b:vibecomfy/commands/port/_shared.py:114:        output_mode=operation,
b016576b:vibecomfy/commands/run.py:241:            mode="explicit_remote_server_unverified",
b016576b:vibecomfy/commands/run.py:252:        mode="attached_local_session_verified",
b016576b:vibecomfy/contracts/intent_nodes.py:695:            mode=resolved_mode,
b016576b:vibecomfy/contracts/intent_nodes.py:736:            execution_mode=execution_mode or RUNTIME_CODE_EXECUTION_MODE,
b016576b:vibecomfy/contracts/intent_nodes.py:801:            mode=mode,
b016576b:vibecomfy/contracts/intent_nodes.py:833:        mode=RUNTIME_CODE_EXECUTION_MODE,
b016576b:vibecomfy/contracts/intent_nodes.py:847:        tree = ast.parse(source, filename="<runtime_code_expression>", mode="eval")
b016576b:vibecomfy/contracts/intent_nodes.py:850:            ast.parse(source, filename="<runtime_code_expression>", mode="exec")
b016576b:vibecomfy/contracts/intent_nodes.py:886:        tree = ast.parse(source, filename="<runtime_code_source>", mode="exec")
b016576b:vibecomfy/contracts/intent_nodes.py:901:        mode=mode,
b016576b:vibecomfy/contracts/intent_nodes.py:910:        ast.parse(source, filename="<runtime_code_source>", mode="exec")
b016576b:vibecomfy/demo_factory/oracle.py:149:                    mode=self._additive_mode(),
b016576b:vibecomfy/demo_factory/oracle.py:247:            additive_mode=self._additive_mode(),
b016576b:vibecomfy/demo_factory/oracle.py:270:            additive_mode=self._additive_mode(),
b016576b:vibecomfy/demo_factory/oracle.py:328:            golden_grade = grade_additive_witness(self.golden, locus, mode=mode)
b016576b:vibecomfy/demo_factory/oracle.py:329:            candidate_grade = grade_additive_witness(candidate, locus, mode=mode)
b016576b:vibecomfy/demo_factory/predicates.py:450:    grade = grade_additive_witness(graph, locus, mode=mode)
b016576b:vibecomfy/demo_factory/predicates.py:618:            if _find_additive_witness(graph, item, mode=additive_mode) is None:
b016576b:vibecomfy/demo_factory/predicates.py:625:            if _find_additive_witness(graph, item, mode=additive_mode) is not None:
b016576b:vibecomfy/ingest/normalize.py:605:            mode=node_mode,
b016576b:vibecomfy/ingest/normalize.py:732:def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
b016576b:vibecomfy/ingest/normalize.py:983:            mode=_node_mode_from_metadata(metadata),
b016576b:vibecomfy/porting/convert.py:340:            output_mode="scratchpad",
b016576b:vibecomfy/porting/convert.py:362:            output_mode="ready_template",
b016576b:vibecomfy/porting/convert.py:417:    result = PortConvertResult(mode=mode, text=text, ready_id=ready_id)
b016576b:vibecomfy/porting/convert.py:988:        mode="w",
b016576b:vibecomfy/porting/edit/_describe.py:54:        mode_label = MODE_LABELS.get(node_mode, f"mode={node_mode}")
b016576b:vibecomfy/porting/edit/_describe.py:151:            mode=node_mode,
b016576b:vibecomfy/porting/edit/_diff.py:142:        old_label = MODE_LABELS.get(old_mode, f"mode={old_mode}")
b016576b:vibecomfy/porting/edit/_diff.py:143:        new_label = MODE_LABELS.get(op.mode, f"mode={op.mode}")
b016576b:vibecomfy/porting/edit/_diff.py:291:        return f"set_mode  uid={op.target.uid!r} → mode={op.mode}"
b016576b:vibecomfy/porting/edit/_parse.py:64:        module = ast.parse(code, mode="exec")
b016576b:vibecomfy/porting/edit/_parse_execute.py:420:            return SetModeOp(op="set_mode", target=node_target, mode=mode_value), ()
b016576b:vibecomfy/porting/edit/lint.py:1189:    return SetModeOp(op="set_mode", target=target, mode=op.mode), None, "passed"
b016576b:vibecomfy/porting/edit/ops.py:542:            mode=mode,  # type: ignore[arg-type]
b016576b:vibecomfy/porting/edit/projection.py:64:        sparse_budget_mode=False,
b016576b:vibecomfy/porting/edit/projection.py:76:            sparse_budget_mode=True,
b016576b:vibecomfy/porting/edit/projection.py:271:    mode_text = MODE_LABELS.get(mode, f"mode={mode}")
b016576b:vibecomfy/porting/edit/projection.py:277:        f"mode={json.dumps(mode, ensure_ascii=True)} ({mode_text}; informational)"
b016576b:vibecomfy/porting/emit/ui.py:264:    4. Fixed defaults (``flags={}``, ``mode=0``, ``color=None``, ``bgcolor=None``,
b016576b:vibecomfy/porting/manual_repair.py:134:            mode=mode,
b016576b:vibecomfy/porting/manual_repair.py:145:        mode=mode,
b016576b:vibecomfy/porting/reorganise/graph_facts.py:490:                mode=node.get("mode"),
b016576b:vibecomfy/porting/workbench.py:132:        output_mode="analysis",
b016576b:vibecomfy/porting/workbench.py:145:    report.diagnostics.extend(_materialization_diagnostics(workflow, resolved_mode=resolved_mode))
b016576b:vibecomfy/porting/workbench.py:227:                mode=resolved_mode,
b016576b:vibecomfy/porting/workbench.py:288:    """Resolve ``mode=\"auto\"`` to the concrete analysis mode.
b016576b:vibecomfy/registry/ready.py:197:        source_mode=source_mode,
b016576b:vibecomfy/runtime/model_policy.py:63:                mode="explicit_remote_server_shared_root",
b016576b:vibecomfy/runtime/model_policy.py:68:        return ModelPreflightPolicy(mode=mode, ensure_models=False, local_models_root=local_root, shared_models_root=shared)
b016576b:vibecomfy/runtime/model_policy.py:69:    return ModelPreflightPolicy(mode=mode, ensure_models=ensure_models, local_models_root=local_root, shared_models_root=shared)
b016576b:vibecomfy/runtime/run.py:71:        mode="managed_local_server" if server_url is None else "explicit_remote_server_unverified",
b016576b:vibecomfy/runtime/session.py:297:            policy = resolve_model_preflight_policy(mode="embedded", ensure_models=True)
b016576b:vibecomfy/runtime/session.py:503:            mode="managed_local_server",
b016576b:vibecomfy/testing/smoke_fixtures.py:180:    container = av.open(str(out_path), mode="w")
b016576b:vibecomfy/workflow.py:253:    def to_envelope(self) -> dict[str, Any]:
b016576b:vibecomfy/workflow.py:266:    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
b016576b:vibecomfy/workflow.py:912:def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
b016576b:vibecomfy/workflow.py:1156:def _get_node_mode(node: VibeNode) -> int:
b016576b:vibecomfy/workflow.py:1202:    - Edges sourcing from muted (mode=2) nodes are removed.
b016576b:vibecomfy/workflow.py:1203:    - Edges sourcing from bypassed (mode=4) nodes are resolved to their bypass

 succeeded in 3947ms:
b016576b:.oracle/checkins/G0.md:728:   - For serialized Vibe envelopes, treat rich `nodes` and `edges` as structural authority. Decode them into the lossless `VibeWorkflow` editable representation, preserving node identity, stable UID, inputs/widgets/raw widget evidence, mode, metadata/UI evidence, and all edges. Treat `compiled_api` only as derived execution evidence; it must not decide which rich nodes survive.
b016576b:.oracle/checkins/G0.md:761:- The `external_workflows/corpus/90a1d5ff9044902e.json` repro preserves exactly 15 rich nodes, 10 rich edges, all 15 distinct UIDs, and the mode distribution (9 mode-4, 6 mode-0); `TripoRefineNode` survives even though `compiled_api` contains only 2 nodes.
b016576b:.oracle/checkins/G0.md:2013:3. **One lossless canonical graph representation** — replace lossy `compiled_api` round-trip (`graph_normalization.py:34`, `ingest/normalize.py:69-73,378-383`) with a rich-envelope decoder (rich `nodes` authoritative; `compiled_api` execution-evidence only); close `executor_durable.py` bypass; pin_opaque emission must carry `properties.vibecomfy_uid` (`ui.py:1800`). *Scout confirmed: NO lossless rich→canonical path exists today; only the browser UI list-nodes path is lossless; the missing piece is a `rich` ingest branch (~50-line decoder reusing `_normalize_ui_to_api`).*
b016576b:.oracle/checkins/G0.md:2045:- **Serialized Vibe envelope** — rich `nodes` mapping IS lossless (all VibeNodes, uids, `metadata._ui`) but **nothing consumes it for structure**; re-ingest reads only `compiled_api` (`normalize.py:70`); rich nodes feed widget-evidence merge only (`normalize.py:205-241`, guarded to compiled survivors at `:213-215`).
b016576b:.oracle/checkins/G0.md:2046:- **VibeWorkflow IR (in-memory Python)** — lossless itself; only ever built FROM lossy compiled_api when input is a vibe envelope.
b016576b:.oracle/checkins/G0.md:5309:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:5476:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:5639:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:5802:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:5965:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:6134:                  "evidence/stage1/compiled_api.json",
b016576b:.oracle/checkins/G0.md:6136:                  "evidence/stage2/compiled_api.json",
b016576b:.oracle/checkins/G0.md:7106:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:7424:                  "evidence/stage1/compiled_api.json",
b016576b:.oracle/checkins/G0.md:7426:                  "evidence/stage2/compiled_api.json",
b016576b:.oracle/checkins/G0.md:7745:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:7908:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:8076:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:8247:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:8412:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:9061:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:9382:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:9547:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:9710:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:9875:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:10038:                  "evidence/compiled_api.json",
b016576b:.oracle/checkins/G0.md:10201:                  "evidence/compiled_api.json",
b016576b:.oracle/findings/area-2-delta.md:2:- Exact per-file roundtrip delta: + top-level groups:[] (VibeWorkflow.groups default_factory=list, serialized by _to_plain); − compiled_api (not a dataclass field, never serialized); + top-level mode on EVERY node (value = _ui.mode then metadata.mode else 0); metadata/_ui keys+values UNCHANGED; all other fields identical.
b016576b:.oracle/findings/area-2-delta.md:6:- Risks: compiled_api silently dropped on regenerated files (IR unaffected — from_envelope ignores it — but raw-JSON consumers break); every node gains mode → large diff noise (~2800 files); non-sort_keys rewrite would reorder files.
b016576b:.oracle/findings/area-4-hivemind.md:4:- Implication: after corpus regeneration, re-running the uploader SKIPS every existing row — regenerated payloads (mode first-class, no compiled_api) do NOT reach Hivemind. Options: (a) accept Hivemind keeps old payloads (summaries unchanged — summarize reads requirements, not mode), (b) add an update/upsert path (out of scope for this run unless judged needed).
b016576b:.oracle/plan-clean.md:14:   - Write `node.mode`, remove both legacy mode copies, remove `compiled_api`, serialize only through `to_envelope()`.
b016576b:.oracle/plan-clean.md:16:   - Permit only `compiled_api` deletion, first-class mode addition, legacy-mode deletion, and—recommended—`groups: []` addition. The latter follows automatically from the dataclass writer ([workflow.py:172](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:172), [workflow.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:253)).
b016576b:.oracle/plan-clean.md:36:   Remove `compiled_api` preconditions and metadata-mode assertions; prove the two-node execution view is freshly derived by `compile("api")` ([test_porting_normalize_ingest.py:657](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_normalize_ingest.py:657)).
b016576b:.oracle/plan-clean.md:50:- No envelope contains `compiled_api`, `metadata.mode`, or `_ui.mode`.
b016576b:.oracle/plan-rev1-clean.md:14:     - remove `compiled_api`;
b016576b:.oracle/plan-rev1-clean.md:35:   - Remove `compiled_api` assumptions.
b016576b:.oracle/plan-rev1-clean.md:58:- No envelope contains `compiled_api`; every node has integer `mode`.
b016576b:.oracle/plan-rev1-clean.md:251:     - remove `compiled_api`;
b016576b:.oracle/plan-rev1-clean.md:272:   - Remove `compiled_api` assumptions.
b016576b:.oracle/plan-rev1-clean.md:295:- No envelope contains `compiled_api`; every node has integer `mode`.
b016576b:.oracle/plan-rev1.md:26:2. Delta contract (area-2): exact per-file delta verified = + groups:[], − compiled_api, + mode per node, metadata unchanged, sort_keys keeps files alphabetical. Regeneration TODAY writes first-class mode with no Batch-B dependency. *.layout.json sidecars are NOT envelopes (reject).
b016576b:.oracle/plan-rev1.md:262:   - Write `node.mode`, remove both legacy mode copies, remove `compiled_api`, serialize only through `to_envelope()`.
b016576b:.oracle/plan-rev1.md:264:   - Permit only `compiled_api` deletion, first-class mode addition, legacy-mode deletion, and—recommended—`groups: []` addition. The latter follows automatically from the dataclass writer ([workflow.py:172](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:172), [workflow.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:253)).
b016576b:.oracle/plan-rev1.md:284:   Remove `compiled_api` preconditions and metadata-mode assertions; prove the two-node execution view is freshly derived by `compile("api")` ([test_porting_normalize_ingest.py:657](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_normalize_ingest.py:657)).
b016576b:.oracle/plan-rev1.md:298:- No envelope contains `compiled_api`, `metadata.mode`, or `_ui.mode`.
b016576b:.oracle/plan-rev1.md:504:- Exact per-file roundtrip delta: + top-level groups:[] (VibeWorkflow.groups default_factory=list, serialized by _to_plain); − compiled_api (not a dataclass field, never serialized); + top-level mode on EVERY node (value = _ui.mode then metadata.mode else 0); metadata/_ui keys+values UNCHANGED; all other fields identical.
b016576b:.oracle/plan-rev1.md:508:- Risks: compiled_api silently dropped on regenerated files (IR unaffected — from_envelope ignores it — but raw-JSON consumers break); every node gains mode → large diff noise (~2800 files); non-sort_keys rewrite would reorder files.
b016576b:.oracle/plan-rev1.md:521:- Implication: after corpus regeneration, re-running the uploader SKIPS every existing row — regenerated payloads (mode first-class, no compiled_api) do NOT reach Hivemind. Options: (a) accept Hivemind keeps old payloads (summaries unchanged — summarize reads requirements, not mode), (b) add an update/upsert path (out of scope for this run unless judged needed).
b016576b:.oracle/plan-rev1.md:1435:        ``compiled_api`` — ``compile("api")`` is a function, not stored data.
b016576b:.oracle/plan-rev1.md:1448:        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
b016576b:.oracle/plan-rev1.md:1982:     - remove `compiled_api`;
b016576b:.oracle/plan-rev1.md:2003:   - Remove `compiled_api` assumptions.
b016576b:.oracle/plan-rev1.md:2026:- No envelope contains `compiled_api`; every node has integer `mode`.
b016576b:.oracle/plan-rev1.md:2219:     - remove `compiled_api`;
b016576b:.oracle/plan-rev1.md:2240:   - Remove `compiled_api` assumptions.
b016576b:.oracle/plan-rev1.md:2263:- No envelope contains `compiled_api`; every node has integer `mode`.
b016576b:.oracle/plan.md:14:     - remove `compiled_api`;
b016576b:.oracle/plan.md:35:   - Remove `compiled_api` assumptions.
b016576b:.oracle/plan.md:58:- No envelope contains `compiled_api`; every node has integer `mode`.
b016576b:.oracle/tasklist.md:14:     - remove `compiled_api`;
b016576b:.oracle/tasklist.md:35:   - Remove `compiled_api` assumptions.
b016576b:.oracle/tasklist.md:58:- No envelope contains `compiled_api`; every node has integer `mode`.
b016576b:Makefile:192:		--corpus-dir "$(CORPUS_DIR)" --expected-count 2797
b016576b:docs/agent-skill/REFERENCE.md:129:Agentic evidence packs use frozen artifacts such as `compiled_api.json`, `metadata.json`, `actions.jsonl`, `response.json`, and `implementation_result.json`. They prove what happened; narrative files such as `report.md` are not proof.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:21:| **Wave 0.4 is almost only `intent_judge`.** | `_frag_batch_memory` and `research.py:_graph_node_class_types` are already rich-nodes-first. They never consult `compiled_api` on a real envelope. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:38:The short answer: **the center of gravity is right, the envelope is still ugly.** `VibeWorkflow` (`vibecomfy/workflow.py`) is the in-memory IR. `_decode_serialized_vibe` already treats the rich `nodes` mapping as the only structural authority. `compile("api")` is already a pure function of the IR. What is not elegant is everything around that: a persisted `compiled_api` twin, an 18-line shape detector that still treats vibe as a peer of UI/API, public loaders that compile-then-reingest (undoing the lossless decode), a half-extracted `vibecomfy/ir/` clone that has already drifted, and a family of dual-defined contracts that are not one problem.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:52:### 1.1 Dual envelope — rich `nodes` + persisted `compiled_api`
b016576b:docs/architecture/canonical-graph-elegance-plan.md:56:- `scripts/ingest_external_workflows.py:82-103` walks `dataclasses.fields` via `_to_plain`, then stamps `vibecomfy_format_version = "1.0"` (`:39`) and `compiled_api = workflow.compile("api")`. **This walk is already lossless for public IR fields. It is the seed of `to_envelope()`.**
b016576b:docs/architecture/canonical-graph-elegance-plan.md:57:- `vibecomfy/demo_factory/fixer.py:68-132` hand-builds the same envelope field-by-field, including `compiled_api` (`:71`) and a hardcoded `"1.0"` (`:80`). It also stamps a non-IR `workflow_id` (`:70`). **This is a twin that will drift the moment Wave 2 adds `mode` / `groups`.** Docstring `:27-40` still describes the `compiled_api` envelope.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:58:- `VibeWorkflow` itself (`vibecomfy/workflow.py:148-161`) does **not** carry `compiled_api`. There is no `to_envelope()` / `from_envelope()`.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:60:The decoder already got this right. `_decode_serialized_vibe` (`normalize.py:382-389`) treats rich `nodes` + `edges` as the only structural authority. It is fail-closed: blank `uid` raises (`:479-481`); `source.id` must be nonblank (`:413-414`); every node `inputs`/`widgets`/`metadata` must be a mapping; provenance is forced to `untrusted_source` (`:529-533`). `compile()` (`workflow.py:738-762`) is a pure function of the IR: it never reads an envelope field named `compiled_api`. `normalize_to_api` on a vibe envelope decodes then recompiles (`normalize.py:82-91`).
b016576b:docs/architecture/canonical-graph-elegance-plan.md:62:**The 90a1d5 smoking gun, verified 2026-08-12.** `external_workflows/corpus/90a1d5ff9044902e.json` stores 2 `compiled_api` nodes (`17`, `3`) and 15 rich nodes (9 `mode=4` bypassed, 4 `MarkdownNote` helpers, 2 executable). Tests at `tests/test_porting_normalize_ingest.py:642-704` lock the decoder to the 15-node IR even when `compiled_api` is missing or malformed.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:64:One nuance: for *this* file, `compiled_api` is not drifted relative to `compile()`. Recompiling the 15-node IR today still yields exactly `{'3', '17'}`. The stored twin is a correct *lossy* snapshot, not a stale one. That does not make it an authority. It makes it a cache of a function. The optional-evidence test (`:692-704`) is the real invariant: delete or corrupt `compiled_api` and the graph is unchanged.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:70:| Live `_frag_batch_memory.py:678-679` (imported via `edit.py:28`) | Falls back to `compiled_api` only when `nodes` is neither `Mapping` nor `list`. A rich envelope's `nodes` **is** a dict, so the sidecar is never touched. | No |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:72:| `executor/research.py:5056-5079` `_graph_node_class_types` | Prefers UI list (`:5058-5060`), then rich mapping (`:5061-5067`), then `compiled_api` / graph last. Rich envelope returns from the mapping branch. | No |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:73:| `executor/research.py:787-789` hivemind rank | `+30` when `gates.has_compiled_api` is True. Semantics source: `hivemind_workflow_semantics.py:150,169`. | Rank only: sidecar-less uploads lose exactly 30 points |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:74:| `tests/live_agentic_harness/intent_judge.py:85-88` | Builds schema context **only** from `graph.get("compiled_api")`. | **Yes — the only real break.** Sidecar-less envelope → no schema context. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:87:2. `nodes` is a dict **and** (`vibecomfy_format_version` present **or** `compiled_api` is a dict) → `"vibe"`.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:133:| `detect_workflow_shape` | vibe = nodes-dict + (version **or** compiled_api-dict); api = *all* values have `class_type` | Official |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:137:| Hivemind upload (`upload_external_workflows_to_hivemind.py:343`) | truthy `vibecomfy_format_version` + nodes-dict | Does not require `compiled_api`; then uses the private constructor |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:203:**Frontend never consumes `compiled_api`.** Confirmed: zero hits under `vibecomfy/comfy_nodes/web/`. The panel consumes LiteGraph list-nodes via `vibecomfy_roundtrip.js`, projects via `projectGraphV1` (`projection_registry_v1.js:423`), applies deltas via `comfy_adapter.js`.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:277:| Leftover `compiled_api` readers | Only `intent_judge.py:85-88` actually breaks. Rank gate `:787-789` loses +30. `_frag_batch_memory.py:678-679` fallback is dead on rich envelopes. `edit_batch_memory.py` does not ship. | Debt. Fix the judge; switch the rank; optional one-liners for the rest. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:298:- Stop *writing* `compiled_api`.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:304:**Can ride with B02:** stale docs/comments; leftover `compiled_api` *readers* (judge recompute; rank switch); stop *requiring* `compiled_api` on newly written envelopes; public loader fix (behavior-affecting, but it is B02's authority lane leaking).
b016576b:docs/architecture/canonical-graph-elegance-plan.md:313:- ~2.8k corpus envelopes (`external_workflows/corpus/*.json`: 2799 files, 2797 carry both `compiled_api` and `vibecomfy_format_version`). Leave them. The ~8936 JSON files under `external_workflows/` include 6129 `.shadow` UI/API originals, which are not sidecar envelopes. The decoder already ignores the sidecar for structure.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:370:        No compiled_api. Transport stamps (workflow_id) are applied by callers after this, not here."""
b016576b:docs/architecture/canonical-graph-elegance-plan.md:383:Envelope keys = public dataclass fields + `vibecomfy_format_version`. That is the stored IR schema. `compiled_api` is absent on new writes. Old corpus files may still carry it; `from_envelope` ignores it.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:454:3. No `compiled_api` in the browser today; none tomorrow.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:539:| **Change** | **Required:** `intent_judge._schema_context_from_payload` (`:85-88`): if `compiled_api` is missing, `convert_to_vibe_format(graph).compile("api")` and keep the payload key `schema_context["compiled_api"]` as the *execution view*, not as "I read a sidecar." Add a sidecar-less fixture to `tests/test_live_agentic_intent_judge_schema_context.py`. **Optional one-liners, same PR if cheap:** `_frag_batch_memory.py:678-679` — delete the `compiled_api` fallback; return `[]` when `nodes` is neither Mapping nor list. `research.py:5056` — when `nodes` is absent, treat `graph` itself as the API dict. **Do not touch `edit_batch_memory.py`.** |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:541:| **Breaks** | Judge test currently asserts `payload["schema_context"]["compiled_api"]` — keep the *key*, change the *source*. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:546:#### Step 0.5 — Stop writing `compiled_api` on new envelopes
b016576b:docs/architecture/canonical-graph-elegance-plan.md:552:| **Change** | `ingest_external_workflows._vibe_workflow_to_dict` and `fixer._ui_graph_to_ir_envelope` stop stamping `compiled_api`. Keep `vibecomfy_format_version`. Reword fixer docstring `:27-40` if not done in 0.1. Hivemind upload: if the sidecar is absent, do not list `"compiled_api"` as a representation; compute `compile("api")` at upload/rank time if identity or class-multiset needs it. Change the hivemind rank gate from `has_compiled_api` to `has_rich_nodes` (or "compiles") in the same PR so new uploads do not drop 30 points. Update `hivemind_workflow_semantics.py:150,169`, `research.py:787-789`, `tests/test_upload_external_workflows_to_hivemind.py:74-104`, **and** `tests/test_executor_research.py:260-272, 885-886, 3706-3708`. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:554:| **Breaks** | Tests that require `payload["compiled_api"]` or `has_compiled_api`. Old corpus files still have the sidecar; do not rewrite them. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:555:| **Gate** | New ingest fixture has version + rich `nodes`, no `compiled_api`. `convert_to_vibe_format` still returns 15 nodes. Hivemind rank for a sidecar-less envelope is not 30 points worse than today's sidecar-full one. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:571:| **Change** | `VibeWorkflow.to_envelope` **is** ingest `_to_plain` (`ingest_external_workflows.py:85-98`) plus `vibecomfy_format_version`. No `compiled_api`. `VibeWorkflow.from_envelope` **is** `_decode_serialized_vibe` moved onto the class (or a one-line wrap — do not rewrite the decoder, do not relax it). Ingest script and fixer call them. **Delete** hivemind `_vibe_workflow_from_dict`. Format version constant lives in `workflow.py`. Fixer keeps `_ensure_workflow_uuid` *after* `to_envelope`. If a corpus row fails fail-closed (blank uid, missing `source` / `requirements`), write a **repair-then-decode** helper that fills blanks and then calls `from_envelope`. Do not keep a third constructor. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:573:| **Breaks** | Hivemind Python emission on envelopes that today's lenient constructor accepted and `from_envelope` will reject (blank uid is the obvious case). That is the point of closing the hole — gate it with a corpus sample, not a hope. Envelope bytes for public fields stay the same minus absent `compiled_api` (already done in 0.5). |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:612:| **Change** | Delete the fifteen `edit_*.py` files that are only `SOURCE = r'''...'''` snapshots (this includes `edit_batch_memory.py` and its dead `compiled_api` fallback). Move the additive-bypass test (`test_comfy_nodes_agent_edit.py:19610`) onto `_frag_orchestration` / `_frag_research`. Leave `edit_batch_repl.py` (it is live). |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:683:| Overnight corpus rewrite dropping `compiled_api` | 9k files, no reader benefit (decoder already ignores it). Lazy-compat is cheaper. |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:706:- **The envelope is the serialized IR.** Opening a corpus JSON, you see `nodes` / `edges` / `inputs` / `outputs` / `source` / `requirements` / `metadata` / `groups`. You do not see a second graph called `compiled_api`.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:707:- **`compile()` is a function, not a stored twin.** Grep for `["compiled_api"] = workflow.compile` is empty. Queue, hivemind identity, and the judge call `compile()` at the boundary.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:804:| Envelope `compiled_api` | always written | not written; ignored on read |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:807:| `has_compiled_api` rank gate | +30 | `has_rich_nodes` / compiles |
b016576b:docs/architecture/canonical-graph-elegance-plan.md:833:No `compiled_api`. Old files may still have it; `from_envelope` never consults it for structure (already true of `_decode_serialized_vibe`).
b016576b:docs/architecture/canonical-graph-elegance-plan.md:870:### E. Keep writing `compiled_api` as a cache, mark it `derived: true`
b016576b:docs/architecture/canonical-graph-elegance-plan.md:873:- **Against:** We already have a cache-invalidation bug in the *concept* — the field name does not say "derived," and leftover readers treat it as data. A `derived` bit is a third thing to teach. Recompute is cheap (90a1d5 compile is 15 nodes). **Rejected.** If a future profiler shows hivemind upload compile is hot, add an explicit `execution_cache` with a hash of the IR, not a peer named `compiled_api`.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:898:- **Threat: a hostile envelope with a lying `compiled_api`.** Already mitigated for structure. After Wave 0, the judge stops depending on it. After Wave 0.5, new writers stop offering the lie.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:907:- **Hivemind:** replace `has_compiled_api` in promotion gates with `compile_ok` / `rich_node_count`. Keep the existing parseable-workflow +40 (`research.py:784-786`).
b016576b:docs/architecture/canonical-graph-elegance-plan.md:908:- **No new alerts** for missing `compiled_api`. Absence is the target.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:943:5. **When, if ever, to strip `compiled_api` from corpus files.** Recommendation: never as a project. If a future ingest re-run rewrites a file for another reason, omit the sidecar then.
b016576b:docs/architecture/canonical-graph-elegance-plan.md:978:- Rank tests that pin `has_compiled_api`: [`tests/test_upload_external_workflows_to_hivemind.py`](../../tests/test_upload_external_workflows_to_hivemind.py) `:74-104`, [`tests/test_executor_research.py`](../../tests/test_executor_research.py) `:260-272,885-886,3706-3708`
b016576b:docs/architecture/canonical-graph-elegance-plan.md:997:| P4 | `fix: stop writing compiled_api on new envelopes` | ingest script, fixer (+ docstring `:27-40`), hivemind upload + semantics, `research.py:787` rank, upload tests **and** `test_executor_research.py` | P3 | Flash | New writes omit the sidecar. Rank uses rich nodes / compile-ok. No corpus rewrite. |
b016576b:docs/failure-analysis/agentic-pipeline-complete-picture-2026-08-12.md:14:- **Class B — Format/contract gaps**: lossy `compiled_api` round-trip drops muted/bypassed nodes (15 rich → 2 nodes on workflow `90a1d5`, TripoRefineNode lost); `executor_durable` bypasses normalization; `pin_opaque` emission skips `properties.vibecomfy_uid`.
b016576b:docs/failure-analysis/agentic-pipeline-complete-picture-2026-08-12.md:54:**Plan item 3** (Class B). Goal: one lossless canonical representation — the `VibeWorkflow` IR built from the envelope's rich `nodes` is the authority; `compiled_api` demoted to a derived execution view; UI JSON stays the JS boundary; close the `executor_durable` bypass; pinned-opaque emission always carries `properties.vibecomfy_uid`.
b016576b:docs/failure-analysis/agentic-pipeline-improvement-2026-08.md:82:3. **One lossless canonical graph representation** — LANDED (B02 + Wave 0; see `docs/architecture/canonical-graph-elegance-plan.md`): rich-envelope decoder (`_decode_serialized_vibe`, `normalize.py:382-395`) makes rich `nodes` authoritative; `compiled_api` is execution evidence only; `executor_durable.py` bypass closed; pin_opaque emission carries `properties.vibecomfy_uid` (`ui.py:1800`); public loaders decode envelopes losslessly.
b016576b:docs/failure-analysis/agentic-pipeline-improvement-2026-08.md:114:- **Serialized Vibe envelope** — rich `nodes` mapping IS lossless (all VibeNodes, uids, `metadata._ui`) and **is now the structural authority** (`_decode_serialized_vibe`, `normalize.py:382-395`); the decoder ignores `compiled_api`; rich nodes still feed widget-evidence merge (`normalize.py:205-241`).
b016576b:docs/failure-analysis/agentic-pipeline-improvement-2026-08.md:115:- **VibeWorkflow IR (in-memory Python)** — lossless itself; only ever built FROM lossy compiled_api when input is a vibe envelope.
b016576b:docs/failure-analysis/current-research-prompts-8683c491-hotshotxl.md:106:    "has_compiled_api": true,
b016576b:docs/failure-analysis/v2/multinode-campaign-design.md:13:`_golden_for`. The two corpus cases were inspected in `compiled_api`; each
b016576b:docs/failure-analysis/v2/multinode-campaign-design.md:146:**Verification note.** I inspected the artifact's `compiled_api` and exact edge
b016576b:docs/failure-analysis/v2/multinode-campaign-design.md:397:**Verification note.** I inspected the artifact's `compiled_api`, including the
b016576b:docs/templates/readable_ready_template_cleanup_plan.md:802:- `public_input_does_not_change_compiled_api`;
b016576b:docs/vibeworkflow.md:22:VibeWorkflow -> envelope   (VibeWorkflow.to_envelope; no compiled_api)
b016576b:docs/vibeworkflow.md:29:is a function, not stored data: old corpus files may carry a `compiled_api`
b016576b:docs/watchdog-babysitting-loop.md:124:`2026-06-28 ~12:00 CEST — GOAL COMPLETE — 100-TEST SCORE: 32/100 (orig 23=10/23 unchanged, new 77=22/77). Deployed 6 fixes (all compile) but they DIDN'T move the score: guard_emit was correct but NOT WIRED (edit.py::_stage_emit missing guard_resolved_ops), validation helper unwired, prompt rules insufficient, + 77 new scenarios exposed 2 new false-blocks. HIGH-THINKING CLUSTERING of 68 failures → 6 clusters; per-cluster codex investigators confirmed root causes + fixes: (1) research-route 10 — core.py research needs_implement=False + research prefetch; (2) UnsupportedNonDAG 22 — ingest/normalize.py recognize VibeComfy compiled_api envelope + narrow classify_failure [BIGGEST]; (3) genuine-hard 23 — _build_adaptation_plan deferred; need adapt plan→execute layer ('topology transplant compiler'); (4) destroy-editor-state 7 — WIRE guard_resolved_ops in edit.py::_stage_emit (activates deployed fix); (5) schema/IR 4 — wire validation_errors_payload into implementation_result.json + schema-source; (6) semantic 2 — enrich widget metadata (directionality) + hard preflight gate. CROSS-CUTTING: ~45/68 failures are FALSE-BLOCKS (pipeline rejecting valid edits), only 23 genuine-hard. Recommended order: wire guard_emit (7) → fix ingest envelope (22) → fix research route (10) → wire validation (4) → widget semantics (2) → adapt-compiler (23). Projected: fixes 1-4 → ~70+/100. Goal closed.`
b016576b:scripts/hivemind_workflow_semantics.py:91:    compiled_api = _as_dict(payload.get("compiled_api"))
b016576b:scripts/hivemind_workflow_semantics.py:94:    if compiled_api:
b016576b:scripts/hivemind_workflow_semantics.py:95:        derived_from.append("compiled_api")
b016576b:scripts/hivemind_workflow_semantics.py:104:        extract_node_class_multiset(compiled_api),
b016576b:scripts/hivemind_workflow_semantics.py:119:        + _extract_model_strings(compiled_api)
b016576b:scripts/migrate_external_workflow_corpus.py:4:list, remove top-level ``compiled_api``, and add a missing integer first-class
b016576b:scripts/migrate_external_workflow_corpus.py:65:    if prefer_stored and "compiled_api" in raw:
b016576b:scripts/migrate_external_workflow_corpus.py:66:        api = raw["compiled_api"]
b016576b:scripts/migrate_external_workflow_corpus.py:68:            raise ValueError("compiled_api must be a mapping when present")
b016576b:scripts/migrate_external_workflow_corpus.py:69:        return _canonical_hash(api), "compiled_api"
b016576b:scripts/migrate_external_workflow_corpus.py:127:    allowed_removed = {"/compiled_api"} if "compiled_api" in raw else set()
b016576b:scripts/migrate_external_workflow_corpus.py:138:    if "/compiled_api" in removed and "compiled_api" in migrated:
b016576b:scripts/migrate_external_workflow_corpus.py:139:        raise ValueError(f"{filename}: compiled_api was not removed")
b016576b:scripts/migrate_external_workflow_corpus.py:183:            "node_modes_defaulted_to_zero": modes_defaulted,
b016576b:scripts/migrate_external_workflow_corpus.py:188:            "remove_compiled_api": int("/compiled_api" in removed),
b016576b:scripts/migrate_external_workflow_corpus.py:259:            modes_defaulted += delta["counts"]["node_modes_defaulted_to_zero"]
b016576b:scripts/migrate_external_workflow_corpus.py:281:                "node_modes_defaulted_to_zero": modes_defaulted,
b016576b:scripts/migrate_external_workflow_corpus.py:285:                "compiled_api_removed": sum(
b016576b:scripts/migrate_external_workflow_corpus.py:286:                    delta["transformations"]["remove_compiled_api"] for delta in deltas
b016576b:scripts/upload_external_workflows_to_hivemind.py:383:    compiled_api = workflow_json.get("compiled_api") if isinstance(workflow_json, dict) else None
b016576b:scripts/upload_external_workflows_to_hivemind.py:385:    if compiled_api is not None:
b016576b:scripts/upload_external_workflows_to_hivemind.py:386:        representations.append("compiled_api")
b016576b:scripts/upload_external_workflows_to_hivemind.py:391:        "compiled_api": compiled_api,
b016576b:scripts/upload_external_workflows_to_hivemind.py:418:        "COMPILED_API = WORKFLOW_JSON.get('compiled_api')\n\n"
b016576b:scripts/upload_external_workflows_to_hivemind.py:638:        "compiled_api": workflow_payload["compiled_api"],
b016576b:tests/live_agentic_harness/intent_judge.py:85:    compiled_api = graph.get("compiled_api")
b016576b:tests/live_agentic_harness/intent_judge.py:86:    if not isinstance(compiled_api, Mapping):
b016576b:tests/live_agentic_harness/intent_judge.py:93:            compiled_api = convert_to_vibe_format(dict(graph)).compile("api")
b016576b:tests/live_agentic_harness/intent_judge.py:96:    context: dict[str, Any] = {"compiled_api": compiled_api}
b016576b:tests/live_agentic_harness/intent_judge.py:312:            "widget's meaning from index order when compiled_api names are available. "
b016576b:tests/structural_harness/README.md:136:| Missing compiled API | Remove `stage1/compiled_api.json` but keep a glowing `report.md` | Fail (AUTHORED) | ✅ |
b016576b:tests/structural_harness/actors.py:54:    compiled_api_path: str
b016576b:tests/structural_harness/actors.py:62:    compiled_api_path: str
b016576b:tests/structural_harness/actors.py:108:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors.py:169:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors.py:264:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors.py:475:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors.py:530:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors.py:587:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors.py:784:    compiled_api = workflow.compile("api")
b016576b:tests/structural_harness/actors.py:788:        api_dict=compiled_api,
b016576b:tests/structural_harness/actors.py:794:    compiled_api_path = artifact_dir / "compiled_api.json"
b016576b:tests/structural_harness/actors.py:796:    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
b016576b:tests/structural_harness/actors.py:804:        compiled_api_path=str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:820:    compiled_api = workflow.compile("api")
b016576b:tests/structural_harness/actors.py:825:        api_dict=compiled_api,
b016576b:tests/structural_harness/actors.py:831:    compiled_api_path = root / "compiled_api.json"
b016576b:tests/structural_harness/actors.py:833:    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
b016576b:tests/structural_harness/actors.py:837:        compiled_api_path=str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:857:    (compiled_api.json, metadata.json, outputs, actions.jsonl) so that
b016576b:tests/structural_harness/actors.py:1654:    compiled_api = _ui_graph_to_compiled_api(final_graph)
b016576b:tests/structural_harness/actors.py:1655:    compiled_api_path = root / "compiled_api.json"
b016576b:tests/structural_harness/actors.py:1656:    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
b016576b:tests/structural_harness/actors.py:1710:                    "compiled_api": str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:1769:        "compiled_api_path": str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:1949:    compiled_api = _ui_graph_to_compiled_api(final_graph)
b016576b:tests/structural_harness/actors.py:1950:    compiled_api_path = root / "compiled_api.json"
b016576b:tests/structural_harness/actors.py:1951:    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
b016576b:tests/structural_harness/actors.py:2062:                    "compiled_api": str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:2132:        "compiled_api_path": str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:2143:def _ui_graph_to_compiled_api(graph: dict[str, Any]) -> dict[str, Any]:
b016576b:tests/structural_harness/actors.py:2530:    compiled_api = _ui_graph_to_compiled_api(executor_result.graph or {})
b016576b:tests/structural_harness/actors.py:2531:    compiled_api_path = root / "compiled_api.json"
b016576b:tests/structural_harness/actors.py:2532:    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
b016576b:tests/structural_harness/actors.py:2555:                    "compiled_api": str(compiled_api_path),
b016576b:tests/structural_harness/actors.py:2634:        "compiled_api_path": str(compiled_api_path),
b016576b:tests/structural_harness/actors_m4/ltx_firstlast_disable_resize_rewire.py:104:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m4/ltx_i2v_swap_tiled_vae_decode.py:116:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m4/wan22_i2v_second_pass_refine.py:16:so the enforced compiled_api.json edge-reference checks pass.
b016576b:tests/structural_harness/actors_m4/wan22_i2v_second_pass_refine.py:128:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m4/wan22_stack_highlow_noise_lora.py:96:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m4/wan_t2v_append_frame_interpolation.py:99:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m4/wan_t2v_splice_modelpatch_before_loras.py:97:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m5/diagnose_broken_graph.py:124:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m5/readiness_go_no_go.py:159:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m5/trace_resolution_source.py:128:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/actors_m5/verify_edit_scoped.py:143:        "compiled_api_path": evidence.compiled_api_path,
b016576b:tests/structural_harness/adapter.py:111:_ASSESSOR_REQUIRED_ONLY_NAMES = {"actions.jsonl", "compiled_api.json", "metadata.json"}
b016576b:tests/structural_harness/adapter.py:669:        if path.name == "compiled_api.json" and isinstance(payload, dict):
b016576b:tests/structural_harness/adapter.py:678:            index = self._compiled_api_structural_index(payload)
b016576b:tests/structural_harness/adapter.py:692:    def _compiled_api_structural_index(payload: dict[str, Any]) -> str:
b016576b:tests/structural_harness/scenarios/add-depth-controlnet-image.yaml:16:    - "compiled_api.json contains a ControlNetLoader node and at least two ControlNetApplyAdvanced nodes."
b016576b:tests/structural_harness/scenarios/add-depth-controlnet-image.yaml:17:    - "compiled_api.json contains a KSampler whose inputs.positive and inputs.negative reference ControlNetApplyAdvanced nodes rather than the original CLIPTextEncode nodes."
b016576b:tests/structural_harness/scenarios/add-depth-controlnet-image.yaml:27:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/add-save-node-finalize.yaml:16:    - "compiled_api.json contains a SaveImage node."
b016576b:tests/structural_harness/scenarios/add-save-node-finalize.yaml:23:    - "compiled_api.json also contains a CheckpointLoaderSimple node feeding the finalized workflow."
b016576b:tests/structural_harness/scenarios/add-save-node-finalize.yaml:26:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/audio_song_escape_hatch_positive.yaml:15:    - "compiled_api.json exists and contains audio workflow nodes from the ace_step_1_5_t2a_song template."
b016576b:tests/structural_harness/scenarios/audio_song_escape_hatch_positive.yaml:24:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/audio_t2a_unwired_limit.yaml:19:    - "evidence/compiled_api.json does NOT exist, evidence/candidate_graph.json does NOT exist, and evidence/candidate.json does NOT exist (the unwired verb must not produce an apply-eligible graph)."
b016576b:tests/structural_harness/scenarios/audio_t2a_unwired_limit.yaml:21:    - "No compiled_api.json exists (agent did not attempt to compile the unwired verb)."
b016576b:tests/structural_harness/scenarios/chaining_positive.yaml:14:    - "Stage 2 compiled_api.json contains at least one LoadImage node whose inputs.image field references the stage 1 output image path (as observed in compiled_api.<node_id>.inputs.image)."
b016576b:tests/structural_harness/scenarios/chaining_positive.yaml:27:    - evidence/stage1/compiled_api.json
b016576b:tests/structural_harness/scenarios/chaining_positive.yaml:29:    - evidence/stage2/compiled_api.json
b016576b:tests/structural_harness/scenarios/controlnet-video-noop.yaml:16:    - "compiled_api.json contains no ControlNetLoader or ControlNetApplyAdvanced nodes."
b016576b:tests/structural_harness/scenarios/controlnet-video-noop.yaml:21:    - "compiled_api.json remains a simple video graph with LoadImage and SaveVideo nodes only."
b016576b:tests/structural_harness/scenarios/controlnet-video-noop.yaml:26:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/diagnose-broken-graph.yaml:18:    - "Load and parse fault_report.json. Let N be the string value of broken_input_node_id and F be the string value of broken_input_field. Verify that in compiled_api.json, node N exists, its class_type is CreateVideo, and it has an input named F that is not connected to any upstream node output."
b016576b:tests/structural_harness/scenarios/diagnose-broken-graph.yaml:30:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/embedded-run-no-gpu.yaml:17:    - "evidence/run_result.json does NOT exist, evidence/candidate_graph.json does NOT exist, evidence/candidate.json does NOT exist, and evidence/compiled_api.json does NOT exist."
b016576b:tests/structural_harness/scenarios/generate_image_canonical_op.yaml:15:    - "compiled_api.json contains an image generation workflow with at least one node referencing a t2i-style prompt input."
b016576b:tests/structural_harness/scenarios/generate_image_canonical_op.yaml:24:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/hotshot-16-frames-agent-edit.yaml:19:    - "Fulfillment: Did the full executor pipeline actually switch the workflow toward generating 16 frames with Hotshot? The candidate graph (candidate.ui.json / graph_summary.json / compiled_api.json) should include Hotshot/AnimateDiff custom nodes (ADE_AnimateDiffLoaderWithContext and ADE_UseEvolvedSampling) and should not have replaced the user's Hotshot request with unrelated installed nodes."
b016576b:tests/structural_harness/scenarios/hotshot-16-frames-agent-edit.yaml:21:    - "Wiring plausibility: Are the added nodes placed and wired in a way that could plausibly inject Hotshot/AnimateDiff motion into the existing sampler path, or is the edit structurally incomplete? (Use graph_summary.json and compiled_api.json; UI graphs use the 'type' field for node class names.)"
b016576b:tests/structural_harness/scenarios/hotshot-16-frames-agent-edit.yaml:36:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/image_edit_unwired_limit.yaml:19:    - "evidence/compiled_api.json does NOT exist, evidence/candidate_graph.json does NOT exist, and evidence/candidate.json does NOT exist (the unwired verb must not produce an apply-eligible graph)."
b016576b:tests/structural_harness/scenarios/image_edit_unwired_limit.yaml:21:    - "No compiled_api.json exists (agent did not attempt to compile the unwired verb)."
b016576b:tests/structural_harness/scenarios/image_to_video_chain_recovery.yaml:23:    - "Stage 2 compiled_api.json contains at least one LoadImage node whose inputs.image field references the recovered stage 1 output image path (as observed in compiled_api.<node_id>.inputs.image)."
b016576b:tests/structural_harness/scenarios/image_to_video_chain_recovery.yaml:31:    - evidence/stage1/compiled_api.json
b016576b:tests/structural_harness/scenarios/image_to_video_chain_recovery.yaml:33:    - evidence/stage2/compiled_api.json
b016576b:tests/structural_harness/scenarios/impossible_8k_free_tier_video.yaml:20:    - "evidence/compiled_api.json does NOT exist, evidence/candidate_graph.json does NOT exist, and evidence/candidate.json does NOT exist (the impossible request must not produce an apply-eligible graph)."
b016576b:tests/structural_harness/scenarios/impossible_8k_free_tier_video.yaml:22:    - "No compiled_api.json exists (agent refused to build the impossible request)."
b016576b:tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml:11:    - "compiled_api.json contains no node whose class_type is ResizeImagesByLongerEdge reading images from the ImageResizeKJv2 node (node 48) on the last-frame path; the disabled resize node 49 is absent from the compiled graph."
b016576b:tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml:12:    - "compiled_api.json: the former resize consumer ResizeImageMaskNode (node 2) has inputs.input referencing [\"48\", 0] (the resize's former source) and NOT the removed resize node 49."
b016576b:tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml:13:    - "compiled_api.json: the former resize consumer LTXVAddGuide (node 2152) has inputs.image referencing [\"48\", 0] and NOT the removed resize node 49."
b016576b:tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml:14:    - "compiled_api.json contains no edge reference whose source node id is 49 anywhere in any node's inputs (no dangling reference to the removed resize node)."
b016576b:tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml:20:    - "Telemetry: the run reaches finalize_metadata and emits compiled_api.json + metadata.json without a queue-blocking dangling-input error."
b016576b:tests/structural_harness/scenarios/ltx-firstlast-disable-resize-rewire.yaml:23:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/ltx-i2v-audio-research-execute.yaml:16:    - "compiled_api.json contains an audio input or audio-related node: LoadAudio, LTXVAudioVAEEncode, or RuneXXCustomAudioLipsync."
b016576b:tests/structural_harness/scenarios/ltx-i2v-audio-research-execute.yaml:23:    - "Evidence includes executor_result.json, executor_report.json, research_result.json, research_summary.json, implementation_result.json, implementation_payload.json, compiled_api.json, candidate.ui.json, graph_summary.json, messages.jsonl, metadata.json, and actions.jsonl."
b016576b:tests/structural_harness/scenarios/ltx-i2v-audio-research-execute.yaml:35:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/ltx-i2v-swap-tiled-vae-decode.yaml:11:    - "compiled_api.json contains NO node whose class_type is LTXVTiledVAEDecode."
b016576b:tests/structural_harness/scenarios/ltx-i2v-swap-tiled-vae-decode.yaml:12:    - "compiled_api.json contains at least one VAEDecode node, and a VAEDecode node's inputs.samples references the same upstream latent the removed tiled decoder consumed (the SamplerCustomAdvanced/LTXVSeparateAVLatent latent at ['4824', 0]), NOT a fresh EmptyLTXVLatentVideo node."
b016576b:tests/structural_harness/scenarios/ltx-i2v-swap-tiled-vae-decode.yaml:13:    - "compiled_api.json: the CreateVideo node 4819 inputs.images references a VAEDecode node output (the new standard decode), and that VAEDecode's inputs.vae references the shared checkpoint vae at ['3940', 2]."
b016576b:tests/structural_harness/scenarios/ltx-i2v-swap-tiled-vae-decode.yaml:14:    - "compiled_api.json: the declared output SaveVideo node 4823 inputs.video still references CreateVideo 4819, and every node input edge reference points to a node that exists (no dangling required inputs)."
b016576b:tests/structural_harness/scenarios/ltx-i2v-swap-tiled-vae-decode.yaml:23:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/readiness-go-no-go.yaml:32:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/run_wan_t2v_ready_cli.yaml:16:    - "compiled_api.json exists and contains WanVideo-related workflow nodes."
b016576b:tests/structural_harness/scenarios/run_wan_t2v_ready_cli.yaml:24:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/trace-resolution-source.yaml:16:    - "Load and parse resolution_source.json. Load compiled_api.json. Verify that parsed node_id matches the id of the EmptyHunyuanLatentVideo node in the compiled graph (the node whose class_type defines the latent video dimensions)."
b016576b:tests/structural_harness/scenarios/trace-resolution-source.yaml:17:    - "Verify that parsed width and height equal the corresponding input values on that EmptyHunyuanLatentVideo node in compiled_api.json."
b016576b:tests/structural_harness/scenarios/trace-resolution-source.yaml:27:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/verify-edit-scoped.yaml:19:    - "Load and parse scoped_diff.json. Verify that the single entry in changed_paths, when split on '.', yields a node id that corresponds to a KSampler node in compiled_api.json, followed by 'inputs', followed by 'seed'."
b016576b:tests/structural_harness/scenarios/verify-edit-scoped.yaml:30:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/wan-t2v-append-frame-interpolation.yaml:16:    - "compiled_api.json contains a vibecomfy.placeholder.frame_interpolation node whose inputs.images references the VAEDecode output [\"8\", 0]."
b016576b:tests/structural_harness/scenarios/wan-t2v-append-frame-interpolation.yaml:17:    - "compiled_api.json contains the CreateVideo node 49 whose inputs.images references the vibecomfy.placeholder.frame_interpolation node (NOT the raw VAEDecode [\"8\", 0])."
b016576b:tests/structural_harness/scenarios/wan-t2v-append-frame-interpolation.yaml:18:    - "compiled_api.json contains the SaveVideo node 50 whose inputs.video references CreateVideo [\"49\", 0], so the interpolated frames reach the save path."
b016576b:tests/structural_harness/scenarios/wan-t2v-append-frame-interpolation.yaml:19:    - "compiled_api.json shows the frame_interpolation node does NOT consume any LATENT output (its images input does not reference the KSampler node 3); interpolation runs on decoded images, not latents."
b016576b:tests/structural_harness/scenarios/wan-t2v-append-frame-interpolation.yaml:27:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/wan-t2v-splice-modelpatch-before-loras.yaml:11:    - "compiled_api.json contains a WanVideoTorchCompileSettings node whose inputs.model edge reference points at the base WanVideoModelLoader node (node 22 output, i.e. [\"22\", 0])."
b016576b:tests/structural_harness/scenarios/wan-t2v-splice-modelpatch-before-loras.yaml:12:    - "compiled_api.json shows the WanVideoSetLoRAs node (node 58) inputs.model references the WanVideoTorchCompileSettings node's output, NOT the base WanVideoModelLoader (node 22) and NOT any downstream node — proving the optimization is spliced UPSTREAM of the loras."
b016576b:tests/structural_harness/scenarios/wan-t2v-splice-modelpatch-before-loras.yaml:13:    - "compiled_api.json shows the WanVideoSampler node (node 27) inputs.model still references the post-lora model chain via WanVideoSetBlockSwap (node 56), whose inputs.model references WanVideoSetLoRAs (node 58) — the sampler keeps receiving the fully combined model+lora model."
b016576b:tests/structural_harness/scenarios/wan-t2v-splice-modelpatch-before-loras.yaml:14:    - "compiled_api.json contains exactly one WanVideoTorchCompileSettings node (the optimization was spliced in, not duplicated or left between loras and sampler)."
b016576b:tests/structural_harness/scenarios/wan-t2v-splice-modelpatch-before-loras.yaml:22:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/wan22-i2v-second-pass-refine.yaml:16:    - "compiled_api.json contains at least two KSamplerAdvanced nodes (the base pass plus the added refine pass) and exactly one LatentUpscale node."
b016576b:tests/structural_harness/scenarios/wan22-i2v-second-pass-refine.yaml:17:    - "compiled_api.json: the LatentUpscale node's inputs.samples references the base KSamplerAdvanced's LATENT output (its source node's class_type is KSamplerAdvanced), NOT an EmptyLatent/WanImageToVideo latent."
b016576b:tests/structural_harness/scenarios/wan22-i2v-second-pass-refine.yaml:18:    - "compiled_api.json: the refine KSamplerAdvanced's inputs.latent_image references the LatentUpscale node's output (the source node's class_type is LatentUpscale), NOT an Empty*Latent or WanImageToVideo node."
b016576b:tests/structural_harness/scenarios/wan22-i2v-second-pass-refine.yaml:19:    - "compiled_api.json: the VAEDecode node's inputs.samples references the refine KSamplerAdvanced (the sampler that consumes the upscaled latent), NOT the base KSamplerAdvanced."
b016576b:tests/structural_harness/scenarios/wan22-i2v-second-pass-refine.yaml:28:    - evidence/compiled_api.json
b016576b:tests/structural_harness/scenarios/wan22-stack-highlow-noise-lora.yaml:16:    - "compiled_api.json contains at least four WanVideoLoraSelect nodes (the two pre-existing per-path heads plus one newly stacked LoRA select for each noise path)."
b016576b:tests/structural_harness/scenarios/wan22-stack-highlow-noise-lora.yaml:17:    - "compiled_api.json node '6' (the high-noise LoRA head feeding WanVideoSetLoRAs '21') has inputs.prev_lora referencing a WanVideoLoraSelect node, NOT null/absent, so a stacked LoRA is chained into the high-noise path."
b016576b:tests/structural_harness/scenarios/wan22-stack-highlow-noise-lora.yaml:18:    - "compiled_api.json node '11' (the low-noise LoRA head feeding WanVideoSetLoRAs '20') has inputs.prev_lora referencing a WanVideoLoraSelect node, NOT null/absent, so a stacked LoRA is chained into the low-noise path."
b016576b:tests/structural_harness/scenarios/wan22-stack-highlow-noise-lora.yaml:19:    - "compiled_api.json WanVideoSampler '23' inputs.model resolves (via WanVideoSetLoRAs '21' -> WanVideoSetBlockSwap '16') back to the high-noise WanVideoModelLoader, and WanVideoSampler '24' inputs.model resolves (via WanVideoSetLoRAs '20' -> WanVideoSetBlockSwap '17') back to the low-noise WanVideoModelLoader, so each stacked LoRA reaches its own sampler."
b016576b:tests/structural_harness/scenarios/wan22-stack-highlow-noise-lora.yaml:27:    - evidence/compiled_api.json
b016576b:tests/test_agent_executor_durable.py:115:        "compiled_api": {
b016576b:tests/test_b02_rich_preservation.py:83:        assert "compiled_api" not in raw
b016576b:tests/test_b02_rich_preservation.py:157:    raw["compiled_api"] = from_envelope(raw).compile("api")
b016576b:tests/test_b02_rich_preservation.py:165:    assert "compiled_api" not in written
b016576b:tests/test_ingest_external_workflows.py:4:stored data. New envelopes therefore omit the compiled_api sidecar while
b016576b:tests/test_ingest_external_workflows.py:26:def test_vibe_workflow_to_dict_omits_compiled_api() -> None:
b016576b:tests/test_ingest_external_workflows.py:36:    assert "compiled_api" not in envelope
b016576b:tests/test_ingest_external_workflows.py:37:    assert "compiled_api" not in envelope.get("metadata", {})
b016576b:tests/test_ingest_external_workflows.py:76:    assert "compiled_api" not in envelope
b016576b:tests/test_live_agentic_intent_judge_schema_context.py:9:def test_intent_judge_includes_compiled_api_schema_context(
b016576b:tests/test_live_agentic_intent_judge_schema_context.py:32:                    "compiled_api": {
b016576b:tests/test_live_agentic_intent_judge_schema_context.py:81:    assert payload["schema_context"]["compiled_api"]["3"]["inputs"]["temperature"] == 0.8
b016576b:tests/test_live_agentic_intent_judge_schema_context.py:184:    """A rich envelope without compiled_api still yields schema context (P3).
b016576b:tests/test_live_agentic_intent_judge_schema_context.py:275:    compiled = payload["schema_context"]["compiled_api"]
b016576b:tests/test_m1_contracts.py:179:        "compiled_api": {
b016576b:tests/test_m1_contracts.py:215:        "compiled_api": {},
b016576b:tests/test_patches.py:76:def test_patch_apply_preserves_return_value_and_compiled_api_for_metadata_only_patch() -> None:
b016576b:tests/test_porting_normalize_ingest.py:122:            "compiled_api": {
b016576b:tests/test_porting_normalize_ingest.py:168:            "compiled_api": {
b016576b:tests/test_porting_normalize_ingest.py:660:    assert "compiled_api" not in raw
b016576b:tests/test_porting_normalize_ingest.py:708:def test_vibe_rich_ingest_ignores_optional_compiled_api_evidence() -> None:
b016576b:tests/test_porting_normalize_ingest.py:712:    assert "compiled_api" not in raw
b016576b:tests/test_porting_normalize_ingest.py:716:    malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}
b016576b:tests/test_porting_normalize_ingest.py:864:    assert "compiled_api" not in envelope
b016576b:tests/test_porting_normalize_ingest.py:883:def test_from_envelope_hand_built_old_style_without_compiled_api() -> None:
b016576b:tests/test_porting_normalize_ingest.py:884:    """A hand-built (old-style) envelope without compiled_api still decodes losslessly."""
b016576b:tests/test_porting_normalize_ingest.py:931:    assert "compiled_api" not in envelope
b016576b:tests/test_porting_normalize_ingest.py:944:    assert "compiled_api" not in written
b016576b:tests/test_structural_evidence_builders.py:44:    stage2_api = json.loads((report_dir / "stage2" / "compiled_api.json").read_text(encoding="utf-8"))
b016576b:tests/test_structural_evidence_builders.py:265:    stage2_api = json.loads((report_dir / "stage2" / "compiled_api.json").read_text(encoding="utf-8"))
b016576b:tests/test_structural_evidence_builders.py:338:    assert not (report_dir / "compiled_api.json").exists()
b016576b:tests/test_structural_evidence_builders.py:372:    assert "evidence/stage1/compiled_api.json" in required
b016576b:tests/test_structural_evidence_builders.py:374:    assert "evidence/stage2/compiled_api.json" in required
b016576b:tests/test_structural_evidence_builders.py:387:        "Missing enforced check for LoadImage.image binding in stage2 compiled_api.json"
b016576b:tests/test_structural_evidence_builders.py:427:            # rel_path looks like "evidence/stage1/compiled_api.json"
b016576b:tests/test_structural_evidence_builders.py:435:        stage2_api = json.loads((report_dir / "stage2" / "compiled_api.json").read_text(encoding="utf-8"))
b016576b:tests/test_structural_evidence_builders.py:579:def _compiled_api(report_dir: Path) -> dict[str, dict[str, object]]:
b016576b:tests/test_structural_evidence_builders.py:580:    return json.loads((report_dir / "compiled_api.json").read_text(encoding="utf-8"))
b016576b:tests/test_structural_evidence_builders.py:636:        ["evidence/compiled_api.json", "evidence/metadata.json", "evidence/actions.jsonl"],
b016576b:tests/test_structural_evidence_builders.py:644:            "evidence/compiled_api.json",
b016576b:tests/test_structural_evidence_builders.py:655:        ["evidence/compiled_api.json", "evidence/metadata.json", "evidence/actions.jsonl"],
b016576b:tests/test_structural_evidence_builders.py:718:# ── Negative / refusal M2 builders (forbidden-call absence, no compiled_api) ─
b016576b:tests/test_structural_evidence_builders.py:737:def test_m2_negative_builder_writes_forbidden_call_absence_and_no_compiled_api(
b016576b:tests/test_structural_evidence_builders.py:745:    produce compiled_api.json or fake output artifacts."""
b016576b:tests/test_structural_evidence_builders.py:779:    # NO compiled_api.json — builder must NOT attempt to compile the unwired verb
b016576b:tests/test_structural_evidence_builders.py:780:    assert not (report_dir / "compiled_api.json").is_file(), (
b016576b:tests/test_structural_evidence_builders.py:781:        f"[{slug}] must NOT produce compiled_api.json for an unwired verb"
b016576b:tests/test_structural_evidence_builders.py:809:def test_m2_refusal_builder_writes_limits_and_refusal_action_no_compiled_api(
b016576b:tests/test_structural_evidence_builders.py:816:    template defaults, a refusal action, and NO compiled_api.json."""
b016576b:tests/test_structural_evidence_builders.py:848:    # NO compiled_api.json (refused to build)
b016576b:tests/test_structural_evidence_builders.py:849:    assert not (report_dir / "compiled_api.json").is_file(), (
b016576b:tests/test_structural_evidence_builders.py:850:        f"[{slug}] must NOT produce compiled_api.json for a refused request"
b016576b:tests/test_structural_evidence_builders.py:948:    compiled_api = _compiled_api(report_dir)
b016576b:tests/test_structural_evidence_builders.py:953:        node for node in compiled_api.values() if isinstance(node, dict) and node.get("class_type") == "KSampler"
b016576b:tests/test_structural_evidence_builders.py:976:    compiled_api = _compiled_api(report_dir)
b016576b:tests/test_structural_evidence_builders.py:980:    class_types = {node["class_type"] for node in compiled_api.values() if isinstance(node, dict)}
b016576b:tests/test_structural_evidence_builders.py:996:    compiled_api = _compiled_api(report_dir)
b016576b:tests/test_structural_evidence_builders.py:1000:    class_types = {node["class_type"] for node in compiled_api.values() if isinstance(node, dict)}
b016576b:tests/test_structural_evidence_builders.py:1102:        "compiled_api.json", "implementation_payload.json",
b016576b:tests/test_structural_evidence_builders.py:1182:    compiled_api = json.loads((report_dir / "compiled_api.json").read_text(encoding="utf-8"))
b016576b:tests/test_structural_evidence_builders.py:1185:        for node in compiled_api.values()
b016576b:tests/test_structural_evidence_builders.py:1188:    assert class_types, "compiled_api.json must have nodes"
b016576b:tests/test_structural_evidence_builders.py:1191:        f"compiled_api.json must include a save/output node type; got {class_types}"
b016576b:tests/test_structural_golden_m4.py:10:  * the builder runs without error and emits compiled_api.json + metadata.json +
b016576b:tests/test_structural_golden_m4.py:12:  * compiled_api.json parses to a non-empty node graph,
b016576b:tests/test_structural_golden_m4.py:56:    for key in ("compiled_api_path", "metadata_path", "actions_path"):
b016576b:tests/test_structural_golden_m4.py:61:    # 2. compiled_api.json parses to a non-empty node graph.
b016576b:tests/test_structural_golden_m4.py:62:    compiled = json.loads(Path(manifest["compiled_api_path"]).read_text(encoding="utf-8"))
b016576b:tests/test_structural_golden_m4.py:63:    assert isinstance(compiled, dict) and compiled, f"{name}: empty compiled_api"
b016576b:tests/test_structural_golden_m4.py:70:    assert class_types, f"{name}: no class_type nodes in compiled_api"
b016576b:tests/test_structural_golden_m5.py:10:  * investigate scenarios (4): compiled_api.json parses to a non-empty node
b016576b:tests/test_structural_golden_m5.py:54:# compiled_api.json + metadata.json.
b016576b:tests/test_structural_golden_m5.py:127:    is_investigate = "compiled_api_path" in manifest
b016576b:tests/test_structural_golden_m5.py:187:    """Investigate-tier builders: compiled_api + metadata must exist and parse."""
b016576b:tests/test_structural_golden_m5.py:188:    # compiled_api.json
b016576b:tests/test_structural_golden_m5.py:190:        ("compiled_api_path", "compiled_api.json"),
b016576b:tests/test_structural_golden_m5.py:198:        Path(manifest["compiled_api_path"]).read_text(encoding="utf-8"),
b016576b:tests/test_structural_golden_m5.py:200:    assert isinstance(compiled, dict) and compiled, f"{name}: empty compiled_api"
b016576b:tests/test_structural_golden_m5.py:208:    assert class_types, f"{name}: no class_type nodes in compiled_api"
b016576b:tests/test_structural_harness_adapter.py:98:        "evidence/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:119:    compiled_api = json.loads((evidence_dir / "compiled_api.json").read_text(encoding="utf-8"))
b016576b:tests/test_structural_harness_adapter.py:120:    class_types = {node.get("class_type") for node in compiled_api.values() if isinstance(node, dict)}
b016576b:tests/test_structural_harness_adapter.py:132:    assert "F compiled_api.json" in tree_after
b016576b:tests/test_structural_harness_adapter.py:137:    assert "Project Evidence File: compiled_api.json" in capture_notes
b016576b:tests/test_structural_harness_adapter.py:146:    assert "Project Evidence File: compiled_api.json" in assessor_input
b016576b:tests/test_structural_harness_adapter.py:152:    assert manifest["files"]["compiled_api.json"] == "compiled_api.json"
b016576b:tests/test_structural_harness_adapter.py:166:        "evidence/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:186:        (frozen_root / "compiled_api.json").write_text(
b016576b:tests/test_structural_harness_adapter.py:415:        "evidence/stage1/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:416:        "evidence/stage2/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:451:        "evidence/stage1/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:453:        "evidence/stage2/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:467:        "stage1/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:469:        "stage2/compiled_api.json",
b016576b:tests/test_structural_harness_adapter.py:557:def test_missing_compiled_api_fails_despite_plausible_report(
b016576b:tests/test_structural_harness_adapter.py:575:    # Remove a critical evidence file: stage1/compiled_api.json
b016576b:tests/test_structural_harness_adapter.py:577:    (frozen / "stage1" / "compiled_api.json").unlink()
b016576b:tests/test_structural_harness_adapter.py:581:        if "stage1/compiled_api.json" not in k
b016576b:tests/test_structural_harness_adapter.py:588:        f"Expected AUTHORED when compiled_api.json is missing, got {proof_level.value!r}."
b016576b:tests/test_structural_harness_adapter.py:932:    like compiled_api.json, metadata.json, actions.jsonl, etc.
b016576b:tests/test_upload_external_workflows_to_hivemind.py:74:def test_envelope_carries_workflow_json_compiled_api_and_python(monkeypatch, tmp_path) -> None:
b016576b:tests/test_upload_external_workflows_to_hivemind.py:82:        "compiled_api": {"1": {"class_type": "LoadCheckpoint", "inputs": {}}},
b016576b:tests/test_upload_external_workflows_to_hivemind.py:97:    assert metadata["representations"] == ["vibecomfy_json", "compiled_api", "scratchpad_python"]
b016576b:tests/test_upload_external_workflows_to_hivemind.py:104:    assert payload["compiled_api"] == workflow_json["compiled_api"]
b016576b:tests/test_upload_external_workflows_to_hivemind.py:189:    """A new envelope without compiled_api still ranks rich: has_rich_nodes gate (P4)."""
b016576b:tests/test_upload_external_workflows_to_hivemind.py:213:    # No sidecar → no compiled_api representation; the rich-nodes gate stays on
b016576b:tests/test_upload_external_workflows_to_hivemind.py:223:    assert "has_compiled_api" not in metadata["workflow_semantics"]["promotion_gates"]
b016576b:tests/test_upload_external_workflows_to_hivemind.py:225:    assert payload["compiled_api"] is None
b016576b:tests/test_workflow_core.py:1052:def test_compile_raises_when_traced_helper_source_missing_from_compiled_api() -> None:
b016576b:tools/convert_ready_templates.py:317:    """Process one template. Returns (row, emitted_text or None, original_compiled_api)."""
b016576b:vibecomfy/comfy_nodes/agent/_frag_batch_memory.py:680:        # authority; there is no compiled_api twin to fall back to.
b016576b:vibecomfy/comfy_nodes/agent/graph_normalization.py:28:    ``nodes`` mapping is the sole structural authority (``compiled_api`` is
b016576b:vibecomfy/comfy_nodes/agent/graph_normalization.py:44:    # The rich ``nodes`` mapping is the sole structural authority. ``compiled_api``
b016576b:vibecomfy/commands/test.py:32:def _build_compiled_api(workflow_path: Path) -> dict[str, Any]:
b016576b:vibecomfy/commands/test.py:74:        api = _build_compiled_api(path)
b016576b:vibecomfy/commands/test.py:112:        api = _build_compiled_api(path)
b016576b:vibecomfy/commands/test.py:166:                api = _build_compiled_api(template_path)
b016576b:vibecomfy/commands/test.py:195:                api = _build_compiled_api(recipe)
b016576b:vibecomfy/demo_factory/fixer.py:34:    no ``compiled_api`` twin is written. ``workflow_id`` is a transport stamp
b016576b:vibecomfy/executor/research.py:5053:    descend into ``compiled_api`` (when present) or treat the graph itself as
b016576b:vibecomfy/executor/research.py:5058:    api_graph = graph.get("compiled_api") if isinstance(graph.get("compiled_api"), dict) else graph
b016576b:vibecomfy/ingest/normalize.py:51:    # ``compiled_api`` is optional execution evidence.  A versioned rich
b016576b:vibecomfy/ingest/normalize.py:56:        or isinstance(raw.get("compiled_api"), dict)
b016576b:vibecomfy/ingest/normalize.py:91:        # authority. ``compiled_api`` is stale execution evidence and must never
b016576b:vibecomfy/ingest/normalize.py:97:        _enforce_exec_source_limits(api, surface="vibe.compiled_api")
b016576b:vibecomfy/ingest/normalize.py:438:    the ONLY structural authority; ``compiled_api`` is never consulted for
b016576b:vibecomfy/ingest/normalize.py:736:    authority. ``compiled_api`` is ignored. Same decoder as
b016576b:vibecomfy/ingest/normalize.py:789:    """True when *raw* is a versioned (or compiled_api-bearing) rich envelope."""
b016576b:vibecomfy/ingest/normalize.py:792:        or isinstance(raw.get("compiled_api"), dict)
b016576b:vibecomfy/workflow.py:257:        ``compiled_api`` — ``compile("api")`` is a function, not stored data.
b016576b:vibecomfy/workflow.py:270:        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;

exec
/bin/zsh -lc 'git log --oneline --reverse b016576b..HEAD && git show --stat --oneline 2b60f74 && git show --format=fuller --no-ext-diff 2b60f74 -- Makefile' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
