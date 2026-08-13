Reading additional input from stdin...
2026-08-13T10:49:23.355492Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:49:23.356509Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T10:49:23.356517Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffabd-adcd-77c2-8e7d-19ec11b5fe6b
--------
user
You are GPT-5.6 Sol (high reasoning). Phase 3 of megado run 2 — REVISE-UNTIL-STABLE.

Plan under revision: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/.oracle/plan.md (your own Phase-1 plan: 5 batches A/B/D+E/C/K + release gate, 8 explore areas, 7 open questions).
All 8 exploration areas are now explored; findings: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/.oracle/findings/area-1..8 (read them all — they are short).

Your instruction: Update the plan given these findings. Bias toward ELEGANCE AND SIMPLICITY — cut scope that isn't pulling its weight. List any NEW areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

Findings that MATERIALLY affect the plan (verify in the files):
1. Corpus ownership (area-1): worktree has NO corpus (gitignored, main-only, 466MB). check_b02 VACUOUSLY PASSES on empty dir. Regeneration must target main's corpus explicitly (REPO_ROOT-relative scripts write to the worktree's OWN fresh dir if run there). CI assertion needs explicit corpus-dir arg or hydration artifact; never allow skip.
2. Delta contract (area-2): exact per-file delta verified = + groups:[], − compiled_api, + mode per node, metadata unchanged, sort_keys keeps files alphabetical. Regeneration TODAY writes first-class mode with no Batch-B dependency. *.layout.json sidecars are NOT envelopes (reject).
3. Manifest (area-3): 355b418f missing = pre-existing drift; ingest is append-only preserve-mode, no --dry-run; check_b02 ignores manifest; upload reads/writes manifest.
4. Hivemind (area-4): uploader is INSERT-ONLY skip-by-default; regenerated payloads will NOT refresh Hivemind rows (external_id = canonical hash). No update path exists. Options: accept stale rows (summaries unaffected) or add upsert (scope question).
5. Groups (area-5): emit NEVER remaps group member ids; wf.groups carries raw source ids; emitted node ids are LiteGraph ints; coherence today depends on callers passing groups= in the right ID space. Dropping the groups= kwarg (Batch D+E) REQUIRES a member-id remap in emit, or port-export loses group membership. 7 groups= call sites: only _export.py is production; 6 are tests/check_b02.
6. Geometry (area-6): BOTH VibeNode.pos AND VibeNode.size needed (list[float]|None, 2 finite coords each); pos alone insufficient — emit._captured_geometry gates on size len>=2. No descent wants bounding box. Ingest never synthesizes geometry (absent stays absent).
7. Loader (area-7): _named_import MUST stay (raw dicts of unknown shape; extension can't disambiguate). .py/ready-id bypass it.
8. Migration map (area-8): 15 call sites, 3 buckets + 1 ambiguous (_frag_ingest:89-90 else-branch → split on _is_vibe_envelope: from_envelope if envelope else from_api). CORRECTIONS: workbench is NOT a convert caller; scratchpad_loader is a CODE EMITTER (rewrite emitted string + import); tools/format_as_python.py + tools/convert_ready_templates.py ARE callers (your plan's "~11" list had workbench but missed the tools).

Open questions from Phase 1 with exploration answers:
- Q1 corpus location → answered: regeneration runs in/against MAIN checkout's corpus (explicit --corpus-dir); check_b02/CI assertion need explicit corpus-dir arg (never vacuously pass — add a fail-closed guard when dir absent).
- Q2 groups:[] delta → allowed (single-writer doctrine).
- Q3 hivemind update → NO update path exists; decide: accept stale rows (recommended, summaries unaffected) vs add upsert (cuts scope).
- Q4 missing manifest file → pre-existing drift; optionally add manifest↔corpus consistency check to the migrate script (flag rows whose corpus_path is absent).
- Q5 drop groups= → means the emit parameter too; member-id remap REQUIRED (see finding 5).
- Q6 geometry type → pos AND size, separate 2-vectors.
- Q7 K-minor bound copy → yes: current deepcopy cannot copy a bound contextvars.Token; fix local to token declaration/copy contract.

Output the REVISED plan (full, concrete, frozen-shape: batches with tasks + acceptance gates + [XHARD] tags + checkpoint structure) incorporating all corrections, OR `STABLE` if nothing material changed. Terse.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is its revise-until-stable phase. I’ll read its full instructions, then the current plan and all eight finding areas before producing the frozen revised plan.
exec
/bin/zsh -lc "sed -n '1,260p' /Users/peteromalley/.codex/skills/megado/SKILL.md && find .oracle/findings -maxdepth 2 -type f -print | sort && sed -n '1,320p' .oracle/plan.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
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
| **Planner / Oracle** | GPT-5.6 Sol (oracle may also be **Grok 4.6** via the grok CLI) | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` · oracle: `grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high --permission-mode plan` | read-only for planning/review; `workspace-write` when it implements |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Hard-task executor** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | `workspace-write` |

The whole pipeline runs on two workhorse models — **DeepSeek V4 Flash** (cheap, fast, coding-tuned — exploration and normal execution) and **GPT-5.6 Sol** (frontier planning, revision, hard tasks) — with **Grok 4.6** via the grok CLI as an alternative oracle for checkpoint review. Escalate exploration to DeepSeek V4 Pro only on evidence that Flash's findings are thin.

One orchestrator (the host agent) drives all phases and holds the artifacts; each subagent gets a self-contained brief and returns only its conclusion.

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

`[XHARD]` tasks go to GPT-5.6 Sol instead:

```bash
timeout 1800 codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/hard-task-brief.md)" </dev/null
```

(Use `--sandbox danger-full-access` only when the Codex agent must itself orchestrate hermes subagents — those need outbound network.)

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

The check-in brief carries: the batch's tasks + acceptance criteria from `tasklist.md`, and the diff since the last checkpoint (`git diff <last-checkpoint-sha>..HEAD` — commit after each batch so the oracle sees a clean delta). Verdict is binary: `PASS` or a list of issues.

**3. Rework loop.** On issues, send them back to the executor (Flash for normal, GPT-5.6 Sol for XHARD), re-run, re-review — until the oracle passes. **Do not start batch N+1 until batch N passes.**

## Phase 6 — Completion

1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
3. `open` the worktree / project for the user, and report phase-by-phase evidence.

## Gotchas

- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
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
# [XHARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high
# checkpoint (oracle: GPT-5.6 Sol or Grok 4.6): codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/checkin-brief.md)" </dev/null
#   or: grok --prompt-file /tmp/checkin-brief.md -m grok-4.6 --reasoning-effort high --permission-mode plan

# Phase 6 — commit, push, open
git add -A && git commit -m "megado: <project>" && git push && open .
```
.oracle/findings/ExploreDualContract.txt
.oracle/findings/ExploreEnvelopeApi.txt
.oracle/findings/ExploreIrClone.txt
.oracle/findings/ExploreShapeDetector.txt
.oracle/findings/ExploreStaleComments.txt
.oracle/findings/area-1-corpus.md
.oracle/findings/area-2-delta.md
.oracle/findings/area-3-manifest.md
.oracle/findings/area-4-hivemind.md
.oracle/findings/area-5-groups.md
.oracle/findings/area-6-geometry.md
.oracle/findings/area-7-loader.md
.oracle/findings/area-8-migration-map.md
Execution protocol: complete each batch, run its gates, commit only its scope, submit the full checkpoint diff to the oracle, and rework until `PASS`. Do not start the next batch early.

### Batch A — Canonical corpus regeneration `[XHARD]`

Depends on resolving corpus ownership in Open Question 1.

Tasks:

1. Add a durable corpus migrate/check command, e.g. `scripts/migrate_external_workflow_corpus.py`.

   - Process only versioned envelopes; skip the two `*.layout.json` sidecars.
   - Decode fail-closed through `VibeWorkflow.from_envelope()`.
   - Resolve mode as first-class → `_ui.mode` → `metadata.mode` → `0`.
   - Write `node.mode`, remove both legacy mode copies, remove `compiled_api`, serialize only through `to_envelope()`.
   - Stage all output before replacement; emit a machine-readable delta report.
   - Permit only `compiled_api` deletion, first-class mode addition, legacy-mode deletion, and—recommended—`groups: []` addition. The latter follows automatically from the dataclass writer ([workflow.py:172](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:172), [workflow.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:253)).

2. Regenerate all 2,797 envelope files under `external_workflows/corpus/*.json`.

   - Preserve file count and filenames.
   - Make all 135,385 node modes explicit; the 754 formerly mode-less nodes become `mode: 0`.
   - Leave `_ui` intact except for deleting `_ui.mode`.
   - Do not perform a geometry regeneration here.

3. Update the preservation checker.

   - `scripts/check_b02_rich_preservation.py`: project first-class `entry.mode` first, retain legacy fallback for old/synthetic fixtures, replace dispatcher calls with `from_envelope`/`from_api`, and emit through `wf.groups` rather than `groups=` ([checker:89](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/scripts/check_b02_rich_preservation.py:89), [checker:262](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/scripts/check_b02_rich_preservation.py:262)).

4. Re-anchor corpus tests:

   - `tests/test_b02_rich_preservation.py`
   - `tests/test_porting_normalize_ingest.py`
   - `tests/test_ingest_external_workflows.py`
   - `tests/test_workflow_core.py`

   Remove `compiled_api` preconditions and metadata-mode assertions; prove the two-node execution view is freshly derived by `compile("api")` ([test_porting_normalize_ingest.py:657](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_normalize_ingest.py:657)).

5. Add the fast structural invariant to `Makefile`’s maintained `check` path; CI already runs `make ci` ([ci.yml:44](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/.github/workflows/ci.yml:44), [Makefile:111](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:111)).

   - If CI must hydrate the corpus, also touch `.github/workflows/ci.yml`.
   - If the corpus becomes tracked, touch `.gitignore`, `.gitattributes` if required, and add `external_workflows` to `ROOT_ALLOWLIST` ([.gitignore:26](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/.gitignore:26), [Makefile:62](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:62)).

6. Run the Hivemind upload only after resolving the update semantics in Open Question 3. No uploader code change is otherwise required: dispatch already uses `from_envelope` ([upload_external_workflows_to_hivemind.py:339](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/scripts/upload_external_workflows_to_hivemind.py:339)).

Acceptance:

- Exactly 2,797 envelopes and unchanged filenames.
- Every envelope decodes and round-trips idempotently.
- Filename equals `canonical_form(compile("api"))` hash prefix; canonical form considers only execution fields ([canonical.py:65](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/testing/canonical.py:65)).
- No envelope contains `compiled_api`, `metadata.mode`, or `_ui.mode`.
- Every node has integer first-class `mode`.
- B02 checker reports zero mismatches/UID-less emissions.
- `git diff --check`, focused corpus tests, and `make ci` pass.

### Batch B — Remove `convert_to_vibe_format` `[XHARD]`

Keep private `_named_import` for genuinely polymorphic file/PNG loaders; delete only the judged public dispatcher.

Production/tooling files:

- Delete dispatcher: `vibecomfy/ingest/normalize.py`.
- Remove public import/export: `vibecomfy/ingest/__init__.py`.
- API → `from_api`:  
  `scripts/ingest_external_workflows.py`, `tools/convert_ready_templates.py`, `tools/format_as_python.py`, `vibecomfy/registry/ready_template.py`, `vibecomfy/scratchpad_loader.py`, API route in `vibecomfy/comfy_nodes/agent/routes.py`.
- UI → `from_ui`:  
  `vibecomfy/demo_factory/fixer.py`, round-trip route in `vibecomfy/comfy_nodes/agent/routes.py`, `vibecomfy/porting/edit/_gates.py`.
- Explicit envelope/API branch:  
  `vibecomfy/comfy_nodes/agent/_frag_ingest.py`, `vibecomfy/comfy_nodes/agent/graph_normalization.py`.
- Checker: `scripts/check_b02_rich_preservation.py`.
- Rename stale comments and recognize `from_api` wrappers:  
  `vibecomfy/porting/emit/ui.py`, `emit_kwargs.py`, `node_kwargs.py`, `vibecomfy/registry/ready.py`.
- Update live—not historical—docs:  
  `docs/agent-edit/session-contract.md`, `docs/runtime/incompatibilities.md`, `docs/security/agent_data_boundary.md`, `docs/security/capability_taxonomy.md`, `docs/text-to-graph/mvp.md`.

Tests requiring call/import migration:

- `tests/edgecases/`: `test_backward_compat.py`, `test_concurrency.py`, `test_determinism.py`, `test_json_formats.py`, `test_model_assets.py`, `test_multi_output.py`, `test_pack_drift.py`, `test_runtime_failures.py`, `test_subgraph_corners.py`, `test_type_system.py`.
- `tests/security/`: `test_agent_context_boundary.py`, `test_ingest_provenance.py`, `test_integration.py`.
- `tests/parity/test_independent_readback.py`
- `tests/live_agentic_harness/intent_judge.py`
- `tests/test_agent_edit_safety.py`
- `tests/test_codemod_hypothesis.py`
- `tests/test_comfy_roundtrip_route.py`
- `tests/test_compile_invariance.py`
- `tests/test_demo_factory_structural_baseline.py`
- `tests/test_emitted_artifacts_open.py`
- `tests/test_exec_normalize.py`
- `tests/test_finalize_metadata.py`
- `tests/test_ingest_external_workflows.py`
- `tests/test_ingest_snapshot.py`
- `tests/test_intent_nodes.py`
- `tests/test_layer4_smoke.py`
- `tests/test_layout_delta.py`
- `tests/test_metadata_registration.py`
- `tests/test_porting_edit_session.py`
- `tests/test_porting_emitter.py`
- `tests/test_porting_normalize_ingest.py`
- `tests/test_porting_ui_emitter.py`
- `tests/test_position_fidelity.py`
- `tests/test_ready_templates.py`
- `tests/test_reconcile.py`
- `tests/test_run_command.py`
- `tests/test_schema.py`
- `tests/test_schema_validate.py`
- `tests/test_subgraph_emission_contract.py`
- `tests/test_ui_emitter_parity.py`
- `tests/test_ui_emitter_widget_shape_verdict.py`
- `tests/test_walking_skeleton.py`
- `tests/test_workflow_core.py`

Re-anchor equivalence tests on fixture invariants—IDs, classes, UIDs, modes, groups, edges, and compiled view—not on the deleted dispatcher. Add the public-surface guard beside the existing detector guard ([test_workflow_core.py:1769](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_workflow_core.py:1769)).

Acceptance:

- `rg 'convert_to_vibe_format' --glob '*.py'` finds only the intentional negative guard, if any.
- `vibecomfy.ingest` exposes `from_envelope`, `from_ui`, and `from_api`, but not the dispatcher.
- Offline paths remain offline; no new live-ComfyUI dependency.
- Generated scratchpad and subprocess source use `from_api`.
- Focused ingest, security, ready-template, scratchpad, porting, and B02 gates pass.

### Batch D+E — Emit/port consumes IR authority `[XHARD]`

Files:

- `vibecomfy/porting/emit/ui.py`
- `vibecomfy/commands/port/_export.py`
- `vibecomfy/porting/layout_store.py`
- `scripts/check_b02_rich_preservation.py`
- Tests: `test_porting_ui_emitter.py`, `test_cli_port.py`, `test_ui_emitter_prior_payload.py`, `test_layout_store.py`, `test_porting_synthetic_fixtures.py`, `test_porting_normalize_ingest.py`, `test_ui_layout.py`.

Tasks:

- Make `_resolve_furniture()` obtain mode exclusively through `_get_node_mode(node)`. Sidecar and metadata retain authority only for flags, colors, properties, and title ([ui.py:249](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/ui.py:249), [workflow.py:1156](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:1156)).
- Remove `emit_ui_json(groups=...)`; emission starts from a deep copy of `wf.groups`.
- Reconcile the selected preserve store’s groups into `workflow.groups` immediately after `_resolve_preserve_source()`, then remove `groups=sidecar_groups` from export ([port/_export.py:445](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/commands/port/_export.py:445)).
- Make `write_layout()` read first-class `wf.groups`, not `wf.metadata["groups"]` ([layout_store.py:171](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/layout_store.py:171)).
- Preserve current source precedence: fresh → sidecar plus `--from` entry overrides → `--from` → sidecar → breadcrumb.

Acceptance:

- Conflicting sidecar, `_ui`, metadata, and field modes cannot make compile and emit disagree.
- Modes 0/2/4 work with the single legacy `_ui` fallback.
- Sidecar geometry/furniture other than mode remains unchanged.
- Sidecar-only, `--from`, conflict, breadcrumb, and `--fresh` group cases pass.
- `port convert` writes `wf.groups`.
- No live `emit_ui_json(..., groups=...)` calls remain.
- Focused port/UI/layout tests and B02 pass.

### Batch C — First-class geometry `[XHARD]`

Frozen simplification: do not perform a second corpus regeneration. Old envelopes populate first-class geometry during decode from `_ui`.

Files:

- Model/ingest: `vibecomfy/workflow.py`, `vibecomfy/ingest/normalize.py`.
- Consumers: `vibecomfy/porting/layout_store.py`, `vibecomfy/porting/lowering.py`, `vibecomfy/porting/convert.py`, `vibecomfy/porting/layout/reconcile.py`, `vibecomfy/porting/emit/ui.py`.
- Tests:  
  `test_workflow_core.py`, `test_porting_normalize_ingest.py`, `test_layout_store.py`, `tests/intent/test_static_lowering.py`, `test_porting_convert.py`, `test_porting_synthetic_fixtures.py`, `test_virtual_wire_round_trip.py`, `test_reconcile.py`, `test_porting_ui_emitter.py`, `test_porting_ui_materialize.py`, `test_position_fidelity.py`, `test_compile_invariance.py`, `tests/live_agentic_harness/source_layouts.py`.

Tasks:

- Add optional `VibeNode.pos` and `VibeNode.size`, default `None`.
- Populate them from UI/API `_ui` during ingest; envelope decode prefers node-level values and falls back to legacy `_ui`.
- Replace geometry descents in layout-store writing, lowering clones, virtual-wire capture, reconcile position matching, and UI emission.
- Explicitly copy `mode`, `pos`, and `size` in lowering’s manual node constructor.
- Do not alter `layout/reconcile.py:505`: that `_ui` access hashes subgraph properties/input schema, not geometry ([reconcile.py:498](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/layout/reconcile.py:498)).

Acceptance:

- UI ingest through live and offline converters yields identical geometry.
- Old/new envelopes round-trip; first-class values win conflicts.
- Copy is deep; compile output is geometry-invariant.
- Lowering clone offsets/sizes, virtual-wire capture, nearest-node reconcile, sidecar serialization, and emitted coordinate canonicalization remain stable.
- Focused suite, B02, `make ci`, and full pytest pass.

### Batch K — Declare workflow context token

Files:

- `vibecomfy/workflow.py`
- `vibecomfy/templates.py`
- `tests/test_workflow_core.py`
- `tests/test_templates_module.py`
- `tests/test_workflow_context.py`

Tasks:

- Add `_workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`.
- Replace token-related `getattr`/`hasattr`, dynamic creation, and deletion with direct access/assignment.
- Ensure `copy()` always produces `_workflow_context_token is None`; use a deepcopy memo for an actively bound `contextvars.Token`.
- Prove the field is absent from constructor, repr, equality, and envelope.

Acceptance:

- Context enter/exit, eager binding/finalize, nesting, exception cleanup, and async isolation remain green.
- Bound and unbound workflow copies succeed and are unbound.
- No token leaks into `to_envelope()`.

### Final release gate

- Corpus invariant command and full B02 checker.
- `make ci`
- `make full-pytest`
- `git diff --check`
- Static searches for deleted dispatcher, legacy corpus mode stores, and `groups=` emission overrides.
- Final oracle review of the complete diff against the explicit defer/leave-alone list.

Explicitly untouched: id-map authority, requirements/diagnostics split, typed metadata/groups, mode enum, slots, JS consumers, full compile/emit unification.

## 2. Additional areas to explore for full clarity

1. **Corpus ownership and hydration.** The worktree has no `external_workflows/`; the populated sibling checkout has the 2,797 envelopes, while the path is ignored in clean clones. Establish whether the PR tracks ~466 MB, force-adds a data artifact, or hydrates a pinned corpus in CI.

2. **Regeneration delta contract.** A plain `from_envelope().to_envelope()` also adds `groups: []` to every old envelope. Recommended: allow it as canonical schema completion; suppressing it would make the migration bypass the sole writer.

3. **Manifest consistency.** The sibling manifest contains 2,798 rows but references missing `corpus/355b418f7449ba25.json`. Determine whether to reconstruct it from shadow data or record it as pre-existing drift.

4. **Hivemind update semantics.** Default upload skips existing rows, so “run upload” would not refresh regenerated payloads. Prove one-row update/upsert behavior with `--only` and `--verify` before the full operation.

5. **Group member reconciliation.** `store_from_ui_json()` converts group member IDs to UIDs ([layout_store.py:425](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/layout_store.py:425)); emission must decide whether to map those back to emitted LiteGraph IDs or omit nonstandard membership.

6. **Geometry validation.** Decide whether first-class `pos`/`size` accept only two finite numeric values and fail closed on malformed versioned envelopes. Recommended: strict for envelopes, tolerant absence for UI/API ingest.

7. **Generic loader boundary.** Retain `_named_import`: file, PNG, and registry loaders genuinely accept multiple formats ([workbench.py:716](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/workbench.py:716)). Duplicating its shape branches would reduce elegance.

8. **Ready-template producers.** The brief omitted `tools/format_as_python.py` and `tools/convert_ready_templates.py`; both own API-shaped paths and belong in Batch B. No ready-template source or index regeneration is otherwise justified.

## 3. Open questions / potential issues

1. **Where will the corpus live for review and CI?** This blocks Batch A. Recommended: a pinned hydration artifact if the 466 MB corpus is intentionally excluded from Git; never allow the CI assertion to skip when absent.

2. **Is `groups: []` an allowed corpus delta?** Recommended: yes, because suppressing it contradicts the “single writer” design.

3. **How are existing Hivemind resources updated?** `--skip-existing` prevents refresh; disabling it may duplicate rows unless `add_resource` is an upsert.

4. **Should the missing manifest corpus file be repaired?** Recommended: isolate it from the schema migration unless its shadow source deterministically reconstructs the same canonical hash.

5. **Does dropping `groups=` mean the emitter parameter itself, or only the command call?** The frozen tasklist interprets the verdict as deleting the override entirely; five additional callers/tests must therefore migrate to `wf.groups`.

6. **What is the exact geometry type?** Recommended: `list[float] | None`, normalized to two finite coordinates while preserving `None` for absent evidence.

7. **Should K-minor fix copying a bound workflow?** Recommended: yes. Current `deepcopy` cannot copy a bound `contextvars.Token`, and the fix is local to the token declaration/copy contract.

exec
/bin/zsh -lc 'for f in .oracle/findings/area-{1,2,3,4,5,6,7,8}-*.md; do echo "===== $f"; sed -n '"'1,260p' \""'$f"; done' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
===== .oracle/findings/area-1-corpus.md
# Area 1 — Corpus ownership
- Worktree has NO external_workflows/ (not symlinked). Corpus lives only in main checkout: 1.0G total, corpus/ 466M (2799 *.json + 2 *.layout.json sidecars), manifest.json 9.9MB/2798 rows. Fully gitignored (line 26) in both checkouts; git ls-files shows only 4 tracked files (2 scripts + 2 tests).
- Scripts resolve REPO_ROOT=Path(__file__).resolve().parents[1]: ingest/upload write in place under REPO_ROOT/external_workflows (worktree run creates a FRESH empty corpus there, does NOT touch main's); check_b02 default 'external_workflows/corpus' is CWD-relative and READ-ONLY.
- check_b02 VACUOUSLY PASSES on empty/missing dir (ok=True, workflows=0). test_b02_rich_preservation.py calls check_corpus() with default path, no env skip — would silently pass in the worktree.
- Regeneration must run against the main checkout's corpus (explicit --corpus-dir / run in main), and CI assertion needs a pinned hydration artifact (or explicit corpus-dir arg); never allow the assertion to skip when absent.
- Ingest is idempotent by canonical hash; filenames canonical_hash[:16].json.
===== .oracle/findings/area-2-delta.md
# Area 2 — Regeneration delta (empirically verified on 3 envelopes)
- Exact per-file roundtrip delta: + top-level groups:[] (VibeWorkflow.groups default_factory=list, serialized by _to_plain); − compiled_api (not a dataclass field, never serialized); + top-level mode on EVERY node (value = _ui.mode then metadata.mode else 0); metadata/_ui keys+values UNCHANGED; all other fields identical.
- On-disk files stay alphabetically sorted: ingest writes json.dumps(sort_keys=True) — roundtrip+rewrite keeps them sorted.
- Regenerating TODAY (before Batch B) already writes first-class mode: _from_api_impl sets VibeNode.mode=_node_mode_from_metadata(metadata) and to_envelope serializes it — NO Batch B dependency.
- ingest_external_workflows.py:255 feeds normalized Comfy API dict into convert_to_vibe_format(api_workflow, source_path, workflow_id) → _from_api_impl → VibeWorkflow → to_envelope persisted.
- Risks: compiled_api silently dropped on regenerated files (IR unaffected — from_envelope ignores it — but raw-JSON consumers break); every node gains mode → large diff noise (~2800 files); non-sort_keys rewrite would reorder files.
- The *.layout.json files are layout-store format, NOT envelopes (no 'nodes' key) — from_envelope rejects them; skip in regen.
===== .oracle/findings/area-3-manifest.md
# Area 3 — Manifest consistency
- Manifest: external_workflows/manifest.json (DEFAULT_MANIFEST ingest_external_workflows.py:35). Top-level keys: version, created_at, updated_at, source, sources, discovered_by, summary, summary_enrichment, origin_backfill, upload_summary, workflows. 2798 rows; row schema: canonical_workflow_hash, workflow_id, corpus_path, shadow_path, primary_source, alternate_sources, status, summary, hivemind_upload.
- corpus/355b418f7449ba25.json is ABSENT from the corpus dir (2799 files, none match); manifest still references it (status ok, hivemind preflight exists=true, resource_id 516); .shadow/summary-briefs/355b418f7449ba25.md exists.
- ingest loads existing manifest, dedupes by canonical_workflow_hash, APPENDS only unseen hashes, sorts + rewrites whole file (378-392, 444-468). NEVER deletes rows or corpus files. NO --dry-run flag (flags: scan-json, source, discovered-by/at, out-dir, shadow-dir, manifest, limit, skip-errors).
- check_b02 does NOT read the manifest (iterates corpus/*.json, skips .layout.json sidecars). upload_external_workflows_to_hivemind DOES read/write manifest (enriches summaries, appends hivemind_upload; dry-run updates in memory only).
- Verdict: 355b418f missing is PRE-EXISTING DRIFT, untouched by regen. Regeneration is preserve-mode (append-only). Suggested: consistency check flagging manifest rows with absent corpus_path; optionally re-ingest from shadow to restore, or mark status missing.
===== .oracle/findings/area-4-hivemind.md
# Area 4 — Hivemind update semantics
- Uploader is INSERT-ONLY, SKIP-BY-DEFAULT: --skip-existing default True; preflights external_resources by source+external_id (GET) before POST; external_id = vibecomfy:external_workflow:<canonical_workflow_hash>. add_resource INSERTs into external_resources (contribute-resource edge fn). NO update/upsert path anywhere (upload_external_workflows_to_hivemind.py, upload_ready_templates_to_hivemind.py, hivemind_workflow_semantics.py).
- --verify is read-only; --only is a substring filter. Tests prove one-row skip + insert.
- Implication: after corpus regeneration, re-running the uploader SKIPS every existing row — regenerated payloads (mode first-class, no compiled_api) do NOT reach Hivemind. Options: (a) accept Hivemind keeps old payloads (summaries unchanged — summarize reads requirements, not mode), (b) add an update/upsert path (out of scope for this run unless judged needed).
===== .oracle/findings/area-5-groups.md
# Area 5 — Group member-ID reconciliation
- emit_ui_json (ui.py:2666-2681): caller_groups = list(groups) if given else deepcopy(wf.groups); emitted_groups = caller_groups + engine_groups. NO member-id remapping; emitted node id = id_remap[node_id] (LiteGraph ints).
- layout_store.store_from_ui_json REKEYS group member int LiteGraph ids → UIDs on ingest (:429-439; test confirms [1,2]->['uid-1','uid-2']).
- wf.groups members are RAW SOURCE ids (LiteGraph ints from source UI; _vibe_groups deep-copies verbatim, normalize.py:404-415). Coherence today depends entirely on callers supplying groups= in the target ID space.
- 7 groups= call sites beyond _export.py: test_porting_normalize_ingest.py:759; test_porting_ui_emitter.py:2167,2720; test_ui_layout.py:1558; check_b02:267,298 (via _emit wrapper :230-235). Production caller: only commands/port/_export.py:460-476 (groups=sidecar_groups from store.get('groups')).
- build_subgraph_groups (layout/groups.py:60-114) produces engine groups WITHOUT 'nodes' member list (title/bounding/color only; matches by properties.vibecomfy_uid).
- Dropping the groups= kwarg (Batch D+E) REQUIRES a member-id remap: map wf.groups member ids (raw source ints or UIDs) → emitted LiteGraph int ids inside emit, else port-export loses group membership coherence.
===== .oracle/findings/area-6-geometry.md
# Area 6 — Geometry validation + minting
- All 6 descents read _ui['pos'] as 2-element [x,y]; _ui['size'] as separate 2-element [w,h]. NONE wants bounding [x,y,w,h].
- Descents: (1) layout_store.write_layout — pos REQUIRED (skip if None), size optional; (2) lowering._clone_node — pos[0],pos[1] for stride, copies size if present; (3) reconcile._pos_from_node — pos-only euclidean match; reconcile:505 hash IGNORES geometry; (4) convert._capture_virtual_wires — opaque pos+size passthrough (may be None); (5) emit._captured_geometry — REQUIRES BOTH pos AND size as len>=2 lists (canonicalized), returns None→_stub_layout if either missing; (6) ingest carries/slims verbatim.
- Ingest never synthesizes geometry: pure path _ui = full raw litegraph node (normalize.py:210); comfy-converter path mints slim {id,pos,size,properties,widgets_values} via _merge_slim_ui (343-356); _from_api_impl deep-copies _ui into VibeNode.metadata (946-984). Absent source geometry stays absent.
- ANSWER to Codex Q6: pos ALONE (list[float]|None, two finite coords) covers descents 1,2,3,4,6 but NOT 5 (which gates on size len>=2). Need BOTH VibeNode.pos AND VibeNode.size (list[float]|None, two finite coords each), minted/validated together. Separate 2-vectors; no bounding box.
===== .oracle/findings/area-7-loader.md
# Area 7 — Generic loader boundary
- All three loaders ingest RAW DICTS of unknown shape and route JSON/PNG/WEBP through _named_import (envelope→UI→API sniff, never compile): cli_loader.load_workflow_any (ready-id / .py scratchpad / .json→_named_import; NO .png/.webp — image raises FileNotFoundError); library.workflow_from_file (.json→_named_import) + workflow_from_id (indexed corpus→_named_import); workbench.load_port_source (ready-id / .py / .png+.webp→_load_workflow_from_image→_named_import / .json→_named_import; most format-rich).
- Extension alone cannot disambiguate shape (JSON can be envelope OR api dict OR ui litegraph). _named_import MUST be retained as happy-path dispatcher for every loader consuming a raw dict. .py (scratchpad) + ready-id paths legitimately bypass it (not raw dicts).
- Verdict: Codex's recommendation confirmed — keep _named_import.
===== .oracle/findings/area-8-migration-map.md
# Area 8 — Exhaustive convert_to_vibe_format migration map (15 call sites)
Bucket API dict → from_api (11): registry/ready_template.py:22 (build_api_ready_workflow); tools/format_as_python.py:436 (dict(module.API_WORKFLOW)) + :454 (normalize_to_api(ui,use_comfy_converter=False)); tools/convert_ready_templates.py:428 (normalize_to_api(raw,use_comfy_converter=False)); porting/edit/_gates.py:166 (normalize_to_api(ui,False)); comfy_nodes/agent/routes.py:229 (dict(api_graph)); scratchpad_loader.py:16,92 (CODE EMITTER — rewrites emitted template string + import, not just the call); scripts/ingest_external_workflows.py:255 (identity['api_workflow']); scripts/check_b02_rich_preservation.py:297 (normalize_to_api(canonical,False)).
Bucket UI list-nodes → from_ui (2): comfy_nodes/agent/routes.py:110 (payload['graph'], test fixture flat.json is litegraph); demo_factory/fixer.py:46 (ui_graph litegraph).
Bucket vibe envelope → from_envelope (2): comfy_nodes/agent/graph_normalization.py:56 (rich envelope, nodes is Mapping); scripts/check_b02_rich_preservation.py:262 (corpus serialized-vibe envelopes).
AMBIGUOUS (1): comfy_nodes/agent/_frag_ingest.py:89-90 else-branch (nodes not a list) — API dict OR vibe envelope; split on _is_vibe_envelope: from_envelope if _is_vibe_envelope(raw) else from_api.
CORRECTIONS to plan.md: workbench.py is NOT a convert_to_vibe_format caller (uses detect_workflow_shape :822 for provenance tagging only). scratchpad_loader is a code emitter. tools/format_as_python.py + tools/convert_ready_templates.py ARE callers (plan missed them; verdict's '11' list included workbench but not the tools).

codex
The main revisions are now clear: preserve legacy metadata byte-for-byte during corpus regeneration, drop the Hivemind refresh/upsert work, and add an emitter-side group-member remap. I’m checking the emitter’s actual ID maps so that acceptance criteria specify the remap precisely rather than hand-waving it.
exec
/bin/zsh -lc "sed -n '2600,2710p' vibecomfy/porting/emit/ui.py; sed -n '410,490p' vibecomfy/commands/port/_export.py; sed -n '390,460p' vibecomfy/porting/layout_store.py; sed -n '130,210p' vibecomfy/workflow.py; sed -n '1120,1185p' vibecomfy/workflow.py; sed -n '1,130p' vibecomfy/porting/layout/groups.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
    # Populate recovery_report
    if recovery_report is not None:
        for node_id in order_list:
            entry = _build_recovery_entry(
                node_prov[node_id],
                widget_shape_verdicts[node_id],
                has_raw_ui_payload=widget_shape_raw_payloads[node_id] is not None,
            )
            node = wf.nodes.get(node_id)
            if node is not None and is_intent_class_type(node.class_type):
                entry.update(_intent_recovery_fields(node))
            recovery_report.append(entry)

        # ── Orphaned virtual-wire routes (display mode) ─────────────────
        if include_virtual_wires and orphaned_get_ids:
            for gid in sorted(orphaned_get_ids):
                node = wf.nodes.get(gid)
                name = broadcast_name(node) if node else None
                recovery_report.append({
                    "node_id": gid,
                    "class_type": "GetNode",
                    "provider": None,
                    "confidence": None,
                    "schema_less": False,
                    "diagnostic": (
                        f"orphaned virtual-wire: GetNode {gid} "
                        f"(broadcast name={name!r}) has no matching SetNode source — "
                        "emitted as visible node with dangling links in display graph"
                    ),
                    "orphaned_route": True,
                    "broadcast_name": name,
                    "widget_shape_verdict": "not_applicable",
                })

        # ── Stripped virtual-wire helpers summary (T7) ───────────────────
        # Always append this entry (zero-count or non-zero) so JSON-mode
        # consumers can detect the emit-mode. Text mode prints only when N > 0.
        recovery_report.append({
            "stripped_helpers": sorted(virtual_wire_ids),
            "count": len(virtual_wire_ids),
            "widget_shape_verdict": "not_applicable",
        })

    # Warn for schema-less nodes when not strict
    if not strict:
        for node_id in order_list:
            p = node_prov[node_id]
            if p["schema_less"]:
                warnings.warn(
                    f"emit_ui_json: schema-less node {node_id}({p['class_type']}); "
                    "emitting best-effort slots. Pass strict=True to hard-fail.",
                    stacklevel=2,
                )

    breadcrumb = _breadcrumb(wf, source_template, prior_path)

    # --- extra: merge caller-provided extra (e.g. sidecar ds) with vibecomfy breadcrumb ---
    merged_extra: dict[str, Any] = dict(extra) if extra else {}
    merged_extra["vibecomfy"] = dict(breadcrumb)

    # When include_main_positions=True, ensure extra.ds (canvas drag/scale state) is
    # present, falling back to a fixed machine-independent default.  The lean default
    # (include_main_positions=False) omits ds entirely.
    if include_main_positions and "ds" not in merged_extra:
        merged_extra["ds"] = dict(_DEFAULT_DS)

    # --- groups: merge caller-passed groups with engine-generated subgraph groups ---
    #   Order: caller-passed groups first, then engine_groups (suppressing duplicates
    #   whose ``title`` matches a caller-passed group title).  All groups are
    #   canonicalized when ``include_main_positions=True``.
    #   groups= is an override: when omitted, the IR's own ``wf.groups`` is used
    #   (deep-copied so geometry canonicalization can never mutate the IR).
    caller_groups: list[dict[str, Any]] = (
        list(groups) if groups is not None else deepcopy(getattr(wf, "groups", []))
    )
    caller_titles: set[str] = {g.get("title", "") for g in caller_groups if g.get("title")}
    emitted_groups: list[dict[str, Any]] = list(caller_groups)
    for eg in engine_groups:
        if eg.get("title", "") not in caller_titles:
            emitted_groups.append(eg)
    if include_main_positions and emitted_groups:
        _canonicalize_group_geometry(emitted_groups)

    envelope: dict[str, Any] = {
        "id": _envelope_id(wf),
        "version": _LITEGRAPH_VERSION,
        "last_node_id": last_node_id,
        "last_link_id": last_link_id,
        "groups": emitted_groups,
        "nodes": nodes,
        "links": links,
        "extra": merged_extra,
    }

    # Subgraph definitions: caller-provided `definitions` (from sidecar envelope)
    # takes precedence over re-emitting from IR metadata.
    effective_defs = definitions if definitions else _emit_definitions(wf)
    if effective_defs is not None:
        for sg in effective_defs.get("subgraphs", []):
            sg_extra = dict(sg.get("extra") or {})
            sg_extra["vibecomfy"] = dict(breadcrumb)
            sg["extra"] = sg_extra
        envelope["definitions"] = effective_defs
        envelope["state"] = {
            "lastNodeId": last_node_id,
            "lastLinkId": last_link_id,
            "lastRerouteId": 0,
        }

    # When include_main_positions=True, always emit state counters even if there
    # are no definitions (the lean default ties state to definitions presence).
            )
            payload = {
                "status": "ok",
                "workflow": args.workflow,
                "format": "api",
                "api": workflow.export_to_json(format="api"),
            }
        except Exception as exc:
            print(f"port export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload["api"], indent=2, sort_keys=True))
        return 0

    if args.to == "ui":
        recovery_report: list[dict[str, Any]] = []
        change_report_out: list = []
        try:
            schema_provider = _port._build_conversion_provider(args)
            workflow = _port.load_workflow_reference(
                args.workflow,
                schema_provider=schema_provider,
                allow_scratchpad=True,
                ready=getattr(args, "ready", False),
            )
            # Prefer the real on-disk .py path from the loaded workflow so the
            # layout-store sidecar is written next to the actual template file.
            _src = getattr(workflow, "source", None)
            _src_path = getattr(_src, "path", None) if _src else None
            if _src_path and Path(_src_path).suffix == ".py" and Path(_src_path).exists():
                py_path = Path(_src_path)
            else:
                py_path = Path(args.workflow)
            store, prior_path_str, from_overrides, prior_ui_payload = _resolve_preserve_source(args, py_path, workflow)

            # M5 Step 16: when the preserve source is a UI JSON on disk (--from
            # or breadcrumb auto-discovery), load it as the guard's "original"
            # so refuse.guard_emit can refuse a corrupted re-emit.
            guard_original_ui: dict[str, Any] | None = None
            if prior_path_str and prior_path_str != str(py_path):
                try:
                    _prior_text = Path(prior_path_str).read_text(encoding="utf-8")
                    _candidate = json.loads(_prior_text)
                    if isinstance(_candidate, dict) and isinstance(_candidate.get("nodes"), list):
                        guard_original_ui = _candidate
                except Exception:
                    guard_original_ui = None

            # Extract sidecar sections for explicit kwargs (for callers that pre-resolved them)
            sidecar_groups = store.get("groups") if store else None
            sidecar_extra = store.get("extra") if store else None
            sidecar_definitions = store.get("definitions") if store else None
            _force_drop = bool(getattr(args, "force_drop", False))
            # Wrap emit_ui_json so we can retry with --force-drop on EditorAheadError.
            _emit_kwargs: dict[str, Any] = dict(
                prior_store=store,
                prior_path=prior_path_str,
                strict=getattr(args, "strict", False),
                include_main_positions=getattr(args, "main_positions", False),
                include_virtual_wires=not getattr(args, "no_virtual_wires", False),
                recovery_report=recovery_report,
                groups=sidecar_groups,
                extra=sidecar_extra,
                definitions=sidecar_definitions,
                change_report_out=change_report_out,
                guard_original_ui=guard_original_ui,
                prior_ui_payload=prior_ui_payload,
            )
            try:
                ui_payload = _port.emit_ui_json(
                    workflow,
                    schema_provider=schema_provider,
                    force_drop_editor_only=False,
                    **_emit_kwargs,
                )
            except Exception as _emit_exc:
                if type(_emit_exc).__name__ == "EditorAheadError" and _force_drop:
                    ui_payload = _port.emit_ui_json(
                        workflow,
        ui: dict[str, Any] = json.loads(raw)
    else:
        ui = ui_json_or_path

    # ── Pass 1: node entries ──────────────────────────────────────────────────
    entries: dict[str, dict] = {}
    unkeyed: list[str] = []          # lit_ids of uidless nodes
    lit_to_uid: dict[str, str] = {}  # lit_id (str) -> vibecomfy_uid

    for node in ui.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        lit_id = str(node.get("id", ""))
        props = node.get("properties") or {}
        uid = props.get("vibecomfy_uid", "")
        if uid:
            lit_to_uid[lit_id] = uid
            entries[uid] = _build_entry(node)
        else:
            unkeyed.append(lit_id)

    # ── Pass 2: re-key endpoint integers in groups, virtual_wires, definitions ─
    unkeyed_endpoints: list[Any] = []

    def _rekey(ref: Any) -> Any:
        """Resolve a litegraph integer endpoint to its uid, or flag unresolved."""
        if isinstance(ref, int):
            key = str(ref)
            uid = lit_to_uid.get(key)
            if uid:
                return uid
            unkeyed_endpoints.append(ref)
            return ref
        return ref

    # groups — each group may carry a ``nodes`` list of integer node ids
    raw_groups = ui.get("groups") or []
    groups: list[Any] = []
    for grp in raw_groups:
        if not isinstance(grp, dict):
            groups.append(grp)
            continue
        grp_copy = dict(grp)
        if isinstance(grp_copy.get("nodes"), list):
            grp_copy["nodes"] = [_rekey(n) for n in grp_copy["nodes"]]
        groups.append(grp_copy)

    # extra — carry forward as-is but re-key virtual_wires endpoints
    raw_extra = ui.get("extra")
    extra: dict[str, Any] = dict(raw_extra) if isinstance(raw_extra, dict) else {}

    raw_vw = extra.pop("virtual_wires", None) or {}
    virtual_wires: dict[str, Any] = {}
    for vw_key, vw_val in (raw_vw.items() if isinstance(raw_vw, dict) else []):
        if not isinstance(vw_val, dict):
            virtual_wires[vw_key] = vw_val
            continue
        vw_copy = dict(vw_val)
        if isinstance(vw_copy.get("endpoints"), list):
            vw_copy["endpoints"] = [_rekey(ep) for ep in vw_copy["endpoints"]]
        virtual_wires[vw_key] = vw_copy

    if unkeyed_endpoints:
        extra["unkeyed_endpoints"] = unkeyed_endpoints

    # definitions — re-key any integer node ids within subgraph definitions
    raw_defs = ui.get("definitions") or {}

    def _rekey_definitions(defs: Any) -> Any:
        if isinstance(defs, dict):
            return {k: _rekey_definitions(v) for k, v in defs.items()}

@dataclass(slots=True)
class VibeOutput:
    node_id: str
    output_type: str
    name: str | None = None
    artifact_kind: str | None = None
    mime_type: str | None = None
    filename_prefix: str | None = None
    expected_cardinality: str | int | None = None


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)


class WorkflowCompileError(VibeComfyError):
    """Compile-time graph assembly failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        next_action: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail or {}
        super().__init__(f"{code}: {message}", next_action=next_action)


@dataclass
class VibeWorkflow:
    id: str
    source: WorkflowSource
    nodes: dict[str, VibeNode] = field(default_factory=dict)
    edges: list[VibeEdge] = field(default_factory=list)
    inputs: dict[str, VibeInput] = field(default_factory=dict)
    outputs: list[VibeOutput] = field(default_factory=list)
    requirements: WorkflowRequirements = field(default_factory=WorkflowRequirements)
    metadata: dict[str, Any] = field(default_factory=dict)
    strict_types: bool = False
    groups: list[dict[str, Any]] = field(default_factory=list)
    _id_map: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _manual_input_names: set[str] = field(default_factory=set, init=False, repr=False)
    _uid_counter: int = field(default=0, init=False, repr=False)

    def __enter__(self) -> "VibeWorkflow":
        from vibecomfy.workflow_context import active_workflow, bind_workflow

        # If ``new_workflow()`` already eagerly bound this workflow (the post-
        # revert default for emitted templates), reuse that binding rather than
        # raising — the ``with`` form is purely scoping sugar in that case.
        if (
            getattr(self, "_workflow_context_token", None) is not None
            and active_workflow() is self
        ):
            return self
        if getattr(self, "_workflow_context_token", None) is not None:
            raise RuntimeError(
                "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
                "block is still active."
            )
        self._workflow_context_token = bind_workflow(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        from vibecomfy.workflow_context import reset_workflow

        token = getattr(self, "_workflow_context_token", None)
        return {}
    payload = intent_node_payload_from_metadata(node.metadata)
    runtime_result = validate_runtime_code_contract(
        class_type=node.class_type,
        payload=payload,
        require_runtime=True,
    )
    if not runtime_result.ok or payload is None or runtime_result.normalized is None:
        return {}
    intent_result = validate_intent_node_contract(
        node_id=node.id,
        class_type=node.class_type,
        metadata=node.metadata,
    )
    intent = payload.get("intent")
    intent = intent if isinstance(intent, dict) else {}
    compiled: dict[str, Any] = {
        "runtime_backed": True,
        **runtime_result.normalized.as_dict(),
        "vibecomfy_uid": node.uid or intent_result.vibecomfy_uid,
        "kind": payload.get("kind"),
        "io": payload.get("io"),
    }
    source = intent.get("source")
    spec = intent.get("spec")
    if isinstance(source, str):
        compiled["source"] = source
    if isinstance(spec, str):
        compiled["spec"] = spec
    return compiled


_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)


def _get_node_mode(node: VibeNode) -> int:
    """Read the litegraph mode (0/2/4); ``node.mode`` is the authority.

    Legacy fallback: hand-built nodes that predate the field signal mode via
    ``metadata["_ui"]["mode"]``; it is consulted only when the field is unset
    (0).  Ingest and envelope decode always populate the field, so production
    graphs read the field.
    """
    mode = node.mode
    if isinstance(mode, int) and mode:
        return mode
    ui = node.metadata.get("_ui")
    if not isinstance(ui, dict):
        return 0
    legacy = ui.get("mode", 0)
    return legacy if isinstance(legacy, int) else 0


def _compute_dropped_bypassed_ids(
    nodes: dict[str, VibeNode],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return (dropped_ids, bypassed_ids) for compile(api) mode filtering.

    dropped_ids: node ids with mode 2 (muted) or mode 4 (bypassed) — excluded from output.
    bypassed_ids: subset of dropped_ids with mode 4 — edges are rewired around them.
    """
    dropped: set[str] = set()
    bypassed: set[str] = set()
    for node_id, node in nodes.items():
        mode = _get_node_mode(node)
"""Subgraph bounding-box groups for the fresh-layout engine.

Phase 2 Step 5: :func:`build_subgraph_groups` reads subgraph definitions from
``wf.metadata['definitions']['subgraphs']`` and produces a list of group dicts
with titled boxes, colours from a fixed palette, and canonicalized bounding
values.  Partial inner-uid matches are debug-logged; fully unmatched subgraphs
are skipped.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

from vibecomfy.porting.emit.ui import _canonicalize_coord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Padding added to each side of the bounding box (pixels).
_GROUP_PAD_PX = 24

# Role-color palette: named roles get consistent colors across workflows.
# Subgraph names without a named role fall through to a deterministic hash-
# based selection from the extended fallback palette.
_ROLE_COLOR_MAP: dict[str, str] = {
    # UUID subgraphs — teal
    "uuid": "#3f7e7e",
    # Video combine / output subgraphs — plum
    "vhs": "#7e3f7e",
    "videocombine": "#7e3f7e",
    # Audio subgraphs — olive
    "audio": "#7e7e3f",
    # Image-processing subgraphs — navy
    "image": "#3f3f7e",
    # Misc / generic subgraphs — rust
    "default": "#7e3f3f",
}

# Fallback palette for hash-based assignment when no named role matches.
_FALLBACK_PALETTE: tuple[str, ...] = (
    "#3f7e7e",
    "#7e3f7e",
    "#7e7e3f",
    "#3f3f7e",
    "#7e3f3f",
    "#5f9f9f",
    "#9f5f9f",
    "#9f9f5f",
    "#5f5f9f",
    "#9f5f5f",
    "#4f8f8f",
    "#8f4f8f",
)


def _role_color_for_subgraph(name: str) -> str:
    """Return a consistent colour for *name* based on its role.

    If *name* matches a known role key (case-insensitive substring match
    against ``_ROLE_COLOR_MAP``), the mapped colour is returned.  Otherwise
    a deterministic hash of *name* modulo ``len(_FALLBACK_PALETTE)`` is used
    so the same name always maps to the same colour across workflows.
    """
    name_lower = name.lower()
    for role_key, colour in _ROLE_COLOR_MAP.items():
        if role_key in name_lower:
            return colour
    # Deterministic hash fallback. Use a stable digest, NOT builtin hash() —
    # hash() is PYTHONHASHSEED-randomized per process, so it would pick a different
    # colour for the same name across runs (despite the docstring's promise), which
    # also defeats the byte-identical agent-edit guard. blake2b is process-stable.
    h = int.from_bytes(hashlib.blake2b(name.encode("utf-8"), digest_size=4).digest(), "big")
    return _FALLBACK_PALETTE[h % len(_FALLBACK_PALETTE)]


def build_subgraph_groups(
    wf: Any,
    *,
    positions: dict[str, dict[str, Any]],
    sizes: dict[str, tuple[int, int]],
) -> list[dict[str, Any]]:
    """Return a list of group-dicts for materializable subgraph bounding boxes.

    Parameters
    ----------
    wf:
        Workflow object with ``wf.metadata['definitions']['subgraphs']``.
    positions:
        ``{uid: {pos: [x, y]}, ...}`` of already-computed node positions.
    sizes:
        ``{uid: (w, h)}`` of already-computed node sizes.

    Returns
    -------
    A list of group dicts, each with keys ``title``, ``bounding``, and ``color``.
    Empty list when no subgraphs are present or no nodes matched.
    """
    metadata = getattr(wf, "metadata", None)
    if not isinstance(metadata, dict):
        return []

    definitions = metadata.get("definitions")
    if not isinstance(definitions, dict):
        return []

    raw_subgraphs = definitions.get("subgraphs")
    if not raw_subgraphs:
        return []

    # Accept both dict-of-subgraphs and list-of-subgraphs shapes.
    if isinstance(raw_subgraphs, dict):
        subgraph_items: list[dict[str, Any]] = [
            item for item in raw_subgraphs.values() if isinstance(item, dict)
        ]
    elif isinstance(raw_subgraphs, list):
        subgraph_items = [
            item for item in raw_subgraphs if isinstance(item, dict)
        ]
    else:
        return []

    groups: list[dict[str, Any]] = []

    for i, subgraph in enumerate(subgraph_items):
        # ── Identify subgraph name (title) ───────────────────────────

exec
/bin/zsh -lc "rg -n \"id_remap|vibecomfy_uid|node\\.uid\" vibecomfy/porting/emit/ui.py | head -80; sed -n '2110,2245p' vibecomfy/porting/emit/ui.py; rg -n \"def copy|deepcopy\" vibecomfy/workflow.py | head -30; sed -n '620,710p' vibecomfy/workflow.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
11:- ``properties["vibecomfy_uid"]`` is the stable identity key for nodes that carry a uid
138:        "uid": getattr(node, "uid", None) or intent_result.vibecomfy_uid,
448:def _build_id_remap(order_list: list[str]) -> dict[str, int]:
608:    Step 6 (T8): Every inner subgraph node has ``properties['vibecomfy_uid']`` stamped
631:        # ── T8: stamp vibecomfy_uid on every inner subgraph node ──
640:                    if "vibecomfy_uid" not in props:
644:                        props["vibecomfy_uid"] = local_uid
1225:    if node.uid:
1226:        properties["vibecomfy_uid"] = node.uid
1417:            uid = props.get("vibecomfy_uid")
1863:    properties["vibecomfy_uid"] = canonical_uid
2186:    id_remap = _build_id_remap(order_list)
2350:                (node.uid or node_id) in new_node_keys
2402:    last_node_id = max(id_remap.values()) if id_remap else 0
2422:                canonical_uid=node.uid,
2423:                litegraph_node_id=id_remap[node_id],
2441:                or engine_positions.get(node.uid)
2452:                or engine_positions.get(node.uid)
2541:                litegraph_node_id=id_remap[node_id],
2595:            [lid, id_remap[edge.from_node], from_slot, id_remap[edge.to_node], to_slot, socket_type or ""]
        _bc_prior_path = _prior_breadcrumb.get("prior_path")
        _wf_source_path = _source_prior_path(wf)
        if (
            _bc_prior_path is not None
            and _wf_source_path is not None
            and _bc_prior_path == _wf_source_path
        ):
            _vibecomfy_authored: set[str] = set(_prior_store_uids)
        else:
            _vibecomfy_authored = set()
        _editor_only: set[str] = _prior_store_uids - _ir_uids - _vibecomfy_authored
        if _editor_only:
            _entries = _prior_store.get("entries", {})
            if force_drop_editor_only:
                # Suppress the editor-ahead error: fold editor-only uids into
                # reconcile_result.removed so build_change_report can populate
                # removed_named with class_type information.
                _sorted_editor_only = sorted(_editor_only)
                reconcile_result.removed.extend(_sorted_editor_only)
            else:
                from vibecomfy.porting.refuse import EditorAheadError as _EditorAheadError  # noqa: PLC0415
                raise _EditorAheadError(
                    [
                        {"uid": u, "class_type": _entries.get(u, {}).get("class_type", "")}
                        for u in sorted(_editor_only)
                    ]
                )

    # Build ChangeReport if the caller requested it via change_report_out.
    _change_report_ref: list = []  # mutable container so we can set stripped_helpers later
    if change_report_out is not None:
        from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
        from vibecomfy.porting.layout.reconcile import build_change_report  # noqa: PLC0415
        _snapshot = (wf.metadata or {}).get("_ingest_snapshot", {})
        _field_delta = compute_field_delta(_snapshot, wf) if _snapshot else {}
        _report = build_change_report(
            reconcile_result,
            _field_delta,
            prior_store_entries=_prior_store.get("entries"),
        )
        change_report_out.append(_report)
        _change_report_ref.append(_report)

    # ── Resolve broadcast helpers (SetNode / GetNode) into direct edges ────
    # effective_edges: direct links for the EXECUTION (flat) graph
    # broadcast_ids: SetNode/GetNode node ids to drop from flat graph
    # orphaned_get_ids: GetNode ids whose broadcast name has no SetNode source
    effective_edges, broadcast_ids, orphaned_get_ids = _resolve_broadcast_edges(wf)

    # Collect the full set of virtual-wire node ids (broadcast + Reroute)
    reroute_ids = {
        node_id
        for node_id, node in wf.nodes.items()
        if node.class_type == "Reroute"
    }
    virtual_wire_ids: set[str] = broadcast_ids | reroute_ids

    # Populate stripped_helpers on the change report (now that virtual_wire_ids is computed).
    if _change_report_ref:
        _change_report_ref[0].content_edits.stripped_helpers = sorted(virtual_wire_ids) if virtual_wire_ids else []

    # ── Choose edge list and node filter based on virtual-wire toggle ───────
    if include_virtual_wires:
        # DISPLAY mode: keep all nodes, use ALL original edges (helpers visible)
        order_list = _emission_order(wf)
        display_edges = list(wf.edges)
    else:
        # EXECUTION (flat) mode: drop virtual-wire nodes, resolve edges
        order_list = [
            nid for nid in _emission_order(wf) if nid not in virtual_wire_ids
        ]
        # First resolve broadcast indirection, then passthrough Reroutes
        flat_edges = _resolve_reroute_edges(effective_edges, wf.nodes)
        display_edges = flat_edges

    # Remap string node ids → litegraph integer ids (digit ids preserve their value).
    id_remap = _build_id_remap(order_list)

    # Build schema cache (one get_schema call per unique class_type)
    schema_cache: dict[str, Any] = {}
    if schema_provider is not None:
        for node_id in order_list:
            ct = wf.nodes[node_id].class_type
            if ct not in schema_cache:
                schema_cache[ct] = schema_provider.get_schema(ct)

    # ── Layout engine: compute fresh positions for every node ───────────────
    # T9b: reconcile-driven merge.
    #   pinned   = {uid: {pos,size} for uid in reconcile_result.matched}
    #              → engine never re-positions matched nodes.
    #   anchors  = caller-supplied anchors ∪ computed_anchors, where
    #              computed_anchors[new_uid] = nearest_wired_neighbor_uid(new_node, matched).
    #              unmatched_legacy / removed-then-readded nodes (i.e. nodes whose
    #              key is neither matched nor in reconcile_result.new but were once
    #              in the store) route through the engine WITHOUT anchors.
    from vibecomfy.porting.layout import layout as _compute_layout  # noqa: PLC0415
    from vibecomfy.porting.layout.reconcile import (  # noqa: PLC0415
        nearest_wired_neighbor_uid as _nearest_wired_neighbor_uid,
    )

    matched_entries: dict[str, dict[str, Any]] = reconcile_result.matched

    def _node_key(node_id: str) -> str:
        n = wf.nodes.get(node_id)
        return (n.uid or node_id) if n is not None else node_id

    pinned_for_engine: dict[str, dict[str, Any]] = {}
    for uid_key, m_entry in matched_entries.items():
        if isinstance(m_entry, dict) and "pos" in m_entry and "size" in m_entry:
            pinned_for_engine[uid_key] = {"pos": m_entry["pos"], "size": m_entry["size"]}

    computed_anchors: dict[str, Any] = {}
    new_keys_set: set[str] = set(reconcile_result.new)
    for node_id in order_list:
        key = _node_key(node_id)
        if key not in new_keys_set:
            continue
        anchor = _nearest_wired_neighbor_uid(node_id, wf, matched_entries)
        if anchor is not None:
            computed_anchors[key] = anchor

    effective_anchors: dict[str, Any] = dict(anchors) if anchors else {}
    for k, v in computed_anchors.items():
        effective_anchors.setdefault(k, v)

    _engine_result = _compute_layout(
        wf,
        schema_provider=schema_provider,
        schema_cache=schema_cache,
        pinned=pinned_for_engine,
        anchors=effective_anchors,
    )
    engine_positions: dict[str, Any] = _engine_result.positions
    engine_groups: list[dict[str, Any]] = _engine_result.groups  # used in T8 group merge

    # Per-node provenance (keyed by node_id)
239:    def copy(self) -> "VibeWorkflow":
242:        The dataclass walk (``copy.deepcopy``) copies every public field —
248:        cloned = copy.deepcopy(self)

        if socket_types_compatible(output_type, input_type):
            return
        warnings.warn(
            (
                f"Strict type warning: connecting {from_node}.{from_output} ({output_type}) "
                f"to {to_node}.{to_input} ({input_type}) may be incompatible."
            ),
            RuntimeWarning,
            stacklevel=3,
        )

    def disconnect(self, to_ref: str) -> bool:
        """Remove the edge whose target matches ``to_ref`` (``"node_id.input_name"``).

        Returns True if an edge was removed, False otherwise.
        """
        to_node, to_input = self._parse_target_ref(to_ref, operation="disconnect")
        for index, edge in enumerate(self.edges):
            if edge.to_node == to_node and edge.to_input == to_input:
                del self.edges[index]
                return True
        return False

    def remove_node(self, node_id: str) -> "VibeWorkflow":
        """Remove a node and all edges attached to it."""
        node_id = str(node_id)
        self.nodes.pop(node_id, None)
        self.edges = [
            edge
            for edge in self.edges
            if str(edge.from_node) != node_id and str(edge.to_node) != node_id
        ]
        self.inputs = {
            name: target
            for name, target in self.inputs.items()
            if str(target.node_id) != node_id
        }
        self.outputs = [
            output
            for output in self.outputs
            if str(output.node_id) != node_id
        ]
        return self

    def replace_edge(self, to_ref: str, new_from_ref: str | Handle) -> "VibeWorkflow":
        """Redirect the edge feeding ``to_ref`` so it now originates from ``new_from_ref``.

        Disconnects the existing edge (if any) and connects the new source. Returns
        ``self`` for chaining.
        """
        self._parse_target_ref(to_ref, operation="replace_edge")
        self._parse_source_ref(new_from_ref, operation="replace_edge")
        self.disconnect(to_ref)
        return self.connect(new_from_ref, to_ref)

    def validate(self, schema_provider: SchemaProvider | None = None) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not self.nodes:
            issues.append(ValidationIssue("empty_workflow", "Workflow contains no nodes."))
        for spec in comfyui_node_issue_specs(
            (node_id, node.class_type, node.inputs, node.metadata)
            for node_id, node in self.nodes.items()
        ):
            issues.append(
                ValidationIssue(
                    spec.code,
                    spec.message,
                    severity=spec.severity,
                    detail=spec.detail,
                )
            )
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_source", f"Missing source node {edge.from_node}."))
            if edge.to_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_target", f"Missing target node {edge.to_node}."))
        api: dict[str, Any] | None = None
        try:
            api = self.compile(backend="api")
        except Exception as exc:
            detail: dict[str, Any] = {}
            if isinstance(exc, WorkflowCompileError):
                detail = {"compile_code": exc.code, **exc.detail}
            issues.append(ValidationIssue("api_compile_failed", str(exc), severity="error", detail=detail))
        if schema_provider is not None:
            from vibecomfy.schema.validate import validate_against_schema, validate_api_link_shapes

            issues.extend(validate_against_schema(self, schema_provider))
            if api is not None:
                issues.extend(validate_api_link_shapes(api, schema_provider))

exec
/bin/zsh -lc "sed -n '420,470p' vibecomfy/porting/emit/ui.py; sed -n '225,270p' vibecomfy/workflow.py; sed -n '155,195p' vibecomfy/porting/layout_store.py; sed -n '900,1020p' vibecomfy/ingest/normalize.py; sed -n '70,120p' vibecomfy/comfy_nodes/agent/_frag_ingest.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:

    ``--out`` (the ``out`` argument) overrides everything.  Otherwise the path is
    ``<out_dir>/ui_export/<source_template>.json`` when a source-template name is
    available, falling back to ``<out_dir>/ui_export/<ir-hash>.json`` for unnamed
    (programmatic) sources.  The fallback hash guarantees the path is never empty
    and never raises.
    """
    if out:
        return Path(out)
    name = source_template if source_template is not None else _source_template_name(wf)
    if name:
        safe = re.sub(r"[^A-Za-z0-9._/-]", "_", name)
        # Collapse path-traversal and leading separators so the name stays under out_dir.
        safe = safe.replace("..", "_").lstrip("/") or _ir_hash(wf)
    else:
        safe = _ir_hash(wf)
    return Path(out_dir) / _UI_EXPORT_SUBDIR / f"{safe}.json"


def _emission_order(wf: Any) -> list[str]:
    """Deterministic node emission order: numeric ids ascending, then lexical."""

    def key(node_id: str) -> tuple[int, str]:
        return (int(node_id), node_id) if node_id.isdigit() else (1 << 30, node_id)

    return sorted(wf.nodes.keys(), key=key)


def _build_id_remap(order_list: list[str]) -> dict[str, int]:
    """Map string VibeNode ids → litegraph integer node ids.

    Digit ids keep their numeric value (so source-derived ``"98"`` stays ``98`` and the
    envelope matches the litegraph reference field-for-field).  Non-digit ids (e.g.
    typed-wrapper labels) are assigned fresh integers above the highest digit id, never
    colliding with a preserved value.  This mapping only governs the litegraph ``id`` field
    and the node-id slots inside ``links[]``.
    """
    remap: dict[str, int] = {}
    used: set[int] = set()
    for node_id in order_list:
        if node_id.isdigit():
            value = int(node_id)
            remap[node_id] = value
            used.add(value)
    nxt = (max(used) + 1) if used else 1
    for node_id in order_list:
        if node_id in remap:
            continue
        while nxt in used:
            nxt += 1
        remap[node_id] = nxt
        return self

    def set_prompt(self, value: str) -> "VibeWorkflow":
        return self.set_input("prompt", value)

    def set_seed(self, value: int) -> "VibeWorkflow":
        return self.set_input("seed", int(value))

    def set_steps(self, value: int) -> "VibeWorkflow":
        return self.set_input("steps", int(value))

    def set_model(self, value: str) -> "VibeWorkflow":
        return self.set_input("model", value)

    def copy(self) -> "VibeWorkflow":
        """Derived, complete deep copy.

        The dataclass walk (``copy.deepcopy``) copies every public field —
        including ``groups`` and per-node ``mode`` — plus the private
        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``),
        so adding a field to the dataclass needs no ``copy()`` edit.  The
        clone is not bound to any workflow context.
        """
        cloned = copy.deepcopy(self)
        if hasattr(cloned, "_workflow_context_token"):
            del cloned._workflow_context_token
        return cloned

    def to_envelope(self) -> dict[str, Any]:
        """Serialize this IR as the stored vibe envelope.

        Public dataclass fields plus ``vibecomfy_format_version``. No
        ``compiled_api`` — ``compile("api")`` is a function, not stored data.
        Transport stamps such as ``workflow_id`` are applied by callers after
        this, not here.
        """
        plain = _to_plain(self)
        plain["vibecomfy_format_version"] = FORMAT_VERSION
        return plain

    @classmethod
    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
        """Fail-closed decoder for a serialized vibe envelope.

        Rich ``nodes`` + ``edges`` are the only structural authority.
        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
        chain = (*scope_chain, sg_key(sg_def))
        scope_path = compose_scope_path(chain)
        for node in sg_def.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if node.get("pos") is None:
                continue
            local_uid = mint_local_uid(node, str(node.get("id")))
            uid = make_uid(scope_path, local_uid)
            entries[uid] = _build_entry(node)
        nested = sg_def.get("definitions")
        if nested:
            entries.update(_assemble_definition_entries(nested, chain))
    return entries


def write_layout(py_path: Path, wf: VibeWorkflow) -> Path:
    """Serialize the full M2 layout envelope for ``wf`` to the sidecar file.

    Per-uid node geometry is captured from each node's ``metadata['_ui']``.
    Nodes with an empty uid or no captured ``pos`` are skipped (M1.5 behavior).
    Graph-level sections are read from ``wf.metadata`` when present and otherwise
    serialized as empty/absent. Returns the sidecar path written.
    """
    entries: dict[str, dict] = {}
    for node in wf.nodes.values():
        uid = node.uid
        if not uid:
            continue
        ui = node.metadata.get("_ui")
        if not isinstance(ui, dict):
            continue
        if ui.get("pos") is None:
            continue
        entries[uid] = _build_entry(ui)

    meta = getattr(wf, "metadata", {}) or {}
    layout_meta = meta.get("_layout") if isinstance(meta.get("_layout"), dict) else {}

    # Subgraph-inner nodes: mint scoped uids over the captured definitions
    # skeleton (T10 furniture) and add their geometry entries keyed by uid (SD1).
                require_int_slot=False,
            ):
                continue
            if key.startswith("widget_") or _is_exec_widget_key(class_type, key):
                widgets[key] = value
            else:
                inputs[key] = value
        raw_widgets = _coerce_raw_widget_payload(
            node.get("_raw_widgets", node.get("raw_widgets"))
        )
        if raw_widgets is None:
            raw_ui = node.get("_ui")
            if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
                raw_widgets = _coerce_raw_widget_payload(
                    _raw_widget_payload_dict(raw_ui["widgets_values"], source="ui.widgets_values")
                )
        metadata = {
            key: value
            for key, value in node.items()
            if key
            not in {
                "class_type",
                "inputs",
                "_raw_widgets",
                "raw_widgets",
                "_input_provenance",
            }
        }
        # ── retain control_after_generate (UI-only) into metadata ──
        # Captured here, before the compile-time `_is_ui_only_prompt_input` filter
        # (workflow.py:471) drops it from the compiled API dict, so the emitter can
        # re-render it. Metadata-only: it never re-enters `inputs`/`widgets`, so
        # `compile("api")` stays byte-for-byte identical. Never guessed — when no
        # recognized control token is present, metadata stays unset and the emitter
        # emits the documented `fixed` default itself.
        control_value = _capture_control_after_generate(node, class_type)
        if control_value is not None:
            metadata.setdefault("control_after_generate", control_value)
        # ── retain flags/color/bgcolor from _ui into top-level metadata ──
        # Both paths: pure-Python path stores the full raw node in _ui (line 99);
        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
        # Captured as metadata DATA only — never enters inputs/widgets (K3 invariant).
        # mode is first-class on VibeNode (the compile mute/bypass signal): the
        # field is populated below from `_ui.mode` (fallback metadata["mode"]) and
        # `_ui.mode` is LEFT IN PLACE so emit_ui_json's furniture keeps re-emitting
        # it.  No duplicate metadata["mode"] is written on new ingests.
        _ui_raw = metadata.get("_ui")
        if isinstance(_ui_raw, dict):
            # The _ui dict may alias the input API node's _ui (pure-Python path);
            # deepcopy so the caller's node dict is never corrupted.
            # Only assign when a real _ui was present — do not invent {}.
            _ui_node = deepcopy(_ui_raw)
            metadata["_ui"] = _ui_node
            for _vis_field in ("flags", "color", "bgcolor"):
                if _vis_field in _ui_node:
                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
        # ── enrich node metadata from schema ──
        output_names = _schema_output_names(schema_provider, class_type)
        if output_names:
            metadata.setdefault("output_names", output_names)
        output_types = _schema_output_types(schema_provider, class_type)
        if output_types:
            metadata.setdefault("output_types", output_types)
        input_aliases = _schema_input_aliases(schema_provider, class_type)
        if input_aliases:
            metadata.setdefault("input_aliases", input_aliases)
        schema_source = _schema_source_provenance(schema_provider, class_type)
        if schema_source is not None:
            metadata.setdefault("schema_source", schema_source)
        if class_type == EXEC_CLASS_TYPE:
            _rebuild_exec_reload_metadata(metadata, widgets.get("io"))
        # S4 capability fence: ingest is the external-JSON boundary, so every
        # ingested node is tagged untrusted_source. Unconditional set — never
        # `setdefault` — so a hostile JSON cannot pre-declare itself trusted.
        metadata[PROVENANCE_KEY] = "untrusted_source"
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_id),
            class_type=class_type,
            inputs=inputs,
            widgets=widgets,
            metadata=metadata,
            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
            raw_widgets=raw_widgets,
            mode=_node_mode_from_metadata(metadata),
        )
        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))

    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        input_provenance = node.get("_input_provenance")
        if not isinstance(input_provenance, dict):
            input_provenance = {}
        for name, value in dict(node.get("inputs", {})).items():
            if input_provenance.get(name) != "widget" and is_api_link(
                value,
                allow_tuple=False,
                require_string_node_id=False,
                require_numeric_node_id=True,
                require_int_slot=False,
            ):
                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))

    workflow.requirements = _infer_requirements(workflow)

    # Stash an ingest-time snapshot immediately after uid minting and edge setup.
    # Captured once here so downstream delta computation can detect edits.
    from vibecomfy.ingest.snapshot import capture_ingest_snapshot  # local to avoid circular at module level
    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(api_workflow, workflow)

    # ``workflow.metadata`` is ``dict[str, Any]`` and transparently accepts
    # any extra keys.  In particular, ``summary`` (a ``WorkflowSummary`` dict)
    # may be present when re-ingesting a corpus JSON that was enriched with
    # LLM-generated summaries.  It is left untouched here — no validation,
    # no stripping — so it survives round-trips through this pipeline intact.
    return workflow


    return {
        "code": "stale_state_mismatch",
        "severity": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "message": "Submitted graph no longer matches the current baseline.",
        "detail": dict(gate_evidence),
        "rebaseline_recovery": recovery,
    }


def _stage_ingest(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.ingest.normalize import convert_to_vibe_format, from_ui
    from vibecomfy.porting.layout_store import store_from_ui_json

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)
    if isinstance(state.graph.get("nodes"), list):
        state.workflow = from_ui(state.graph, schema_provider=state.schema_provider)
    else:
        state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
    state.prior_store = store_from_ui_json(state.graph)
    # Phase 1 (concrete-tree migration, docs/agent-edit/concrete-tree.md): give the
    # user's original graph stable identity so the delta-scope guard (guard_emit)
    # engages on the FIRST edit. Stamp a COPY — never mutate state.graph, which is
    # hashed/echoed/audited. The candidate inherits the same uids (verified: uid ==
    # node id, preserved across the scratchpad round-trip), so the guard scope
    # becomes non-empty.
    #
    # Gated OFF by default: with the guard engaged but the candidate still produced
    # by the LOSSY regeneration path (Phase 2 not yet landed), guard_emit correctly
    # refuses candidates that diverge from the original outside the intended delta.
    # Enabling identity is therefore only safe once Phase 2 (verbatim-preserve)
    # makes the candidate faithful. Toggle with VIBECOMFY_AGENT_EDIT_IDENTITY=1.
    if os.getenv("VIBECOMFY_AGENT_EDIT_IDENTITY") == "1":
        from copy import deepcopy as _deepcopy
        guard_original = _deepcopy(state.graph)
        _stamp_identity_on_original(guard_original, state.workflow)
        state.guard_original_ui = guard_original
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]

exec
/bin/zsh -lc "sed -n '2120,2205p' tests/test_porting_ui_emitter.py; sed -n '2680,2750p' tests/test_porting_ui_emitter.py; sed -n '1520,1595p' tests/test_ui_layout.py; sed -n '730,780p' tests/test_porting_normalize_ingest.py; rg -n 'unkeyed_endpoints|group.*nodes|\"nodes\": \\[' tests/test_cli_port.py tests/test_layout_store.py tests/test_porting_ui_emitter.py | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
    """When both sidecar and _ui are absent, emit fixed defaults (flags={}, mode=0, no color/bgcolor)."""
    wf = _wf("minimal")
    node = VibeNode("1", "Plain")
    # No _ui metadata, no uid
    wf.nodes["1"] = node

    result = emit_ui_json(wf)
    emitted = result["nodes"][0]

    assert emitted["flags"] == {}
    assert emitted["mode"] == 0
    assert "color" not in emitted, "color should be absent when None"
    assert "bgcolor" not in emitted, "bgcolor should be absent when None"


def test_furniture_mode_defaults_to_zero_for_non_int() -> None:
    """Non-int mode values (None, string, float) are defaulted to 0."""
    wf = _wf("bad-mode")
    node = VibeNode("1", "BadMode")
    node.uid = "uid-bm"
    wf.nodes["1"] = node

    # layout entry with a non-int mode
    layout_entry = {
        "pos": [0, 0],
        "size": [100, 100],
        "flags": {},
        "mode": None,  # None → 0
    }
    result = emit_ui_json(wf, layout={"uid-bm": layout_entry})
    assert result["nodes"][0]["mode"] == 0

    # string mode
    layout_entry["mode"] = "muted"
    result2 = emit_ui_json(wf, layout={"uid-bm": layout_entry})
    assert result2["nodes"][0]["mode"] == 0


def test_furniture_groups_from_param() -> None:
    """groups= param populates the top-level groups array."""
    wf = _wf("gtest")
    wf.nodes["1"] = VibeNode("1", "N1")

    groups = [
        {"title": "Group A", "bounding": [0, 0, 400, 300], "color": "#3f3"},
        {"title": "Group B", "bounding": [500, 0, 400, 300], "color": "#33f"},
    ]
    result = emit_ui_json(wf, groups=groups)
    assert result["groups"] == groups

    # Default: empty list
    result2 = emit_ui_json(wf)
    assert result2["groups"] == []


def test_furniture_sidecar_takes_precedence_over_metadata_ui() -> None:
    """When BOTH a sidecar entry and node.metadata['_ui'] exist, the sidecar wins."""
    wf = _wf("precedence")
    node = VibeNode("1", "Conflict")
    node.uid = "uid-conflict"
    # metadata['_ui'] says mode=4, color='#ui'
    node.metadata["_ui"] = {
        "pos": [10, 20],
        "size": [30, 40],
        "flags": {"collapsed": False},
        "color": "#ui",
        "bgcolor": "#uibg",
        "mode": 4,
        "properties": {"from": "ui"},
    }
    wf.nodes["1"] = node

    # Sidecar says mode=2, color='#sc'
    sidecar_entry = {
        "pos": [50, 60],
        "size": [70, 80],
        "flags": {"collapsed": True},
        "color": "#sc",
        "bgcolor": "#scbg",
        "mode": 2,
        "properties": {"from": "sidecar"},
    }
    result = emit_ui_json(wf, layout={"uid-conflict": sidecar_entry})
    emitted = result["nodes"][0]

    assert emitted["flags"] == {"collapsed": True}, "sidecar flags should win"
    n1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert "title" not in n1, "lean default must NOT emit title"


def test_canonicalize_group_geometry() -> None:
    """Group bounding boxes are canonicalized to M2 precision when
    include_main_positions=True."""
    from vibecomfy.porting.emit.ui import _canonicalize_group_geometry

    groups = [
        {
            "title": "Group A",
            "bounding": [100.123456, 200.654321, 300.999999, 400.000001],
        },
        {
            "title": "Group B",
            # No bounding → left alone
        },
    ]
    _canonicalize_group_geometry(groups)
    assert groups[0]["bounding"] == [100.12, 200.65, 301.0, 400.0], (
        f"bounding not M2-canonicalized: {groups[0]['bounding']}"
    )
    # Group B should be unchanged (no bounding key or not a 4-element list)
    assert "bounding" not in groups[1]


def test_main_positions_groups_with_canonicalized_geometry() -> None:
    """Full emit with include_main_positions=True canonicalizes group geometry."""
    wf = _wf("group_geom")
    wf.nodes["1"] = VibeNode("1", "G1")
    wf.nodes["2"] = VibeNode("2", "G2")
    wf.connect("1.0", "2.images")

    groups = [
        {"title": "Group X", "bounding": [10.556, 20.444, 300.001, 400.999]},
    ]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, groups=groups, include_main_positions=True)

    assert len(result["groups"]) == 1
    assert result["groups"][0]["bounding"] == [10.56, 20.44, 300.0, 401.0], (
        f"group bounding not canonicalized: {result['groups'][0]['bounding']}"
    )


def test_main_positions_extra_ds_from_sidecar() -> None:
    """When a sidecar extra provides ds, it MUST be used verbatim (not overridden)
    when include_main_positions=True."""
    wf = _wf("ds_sidecar")
    wf.nodes["1"] = VibeNode("1", "N")
    wf.nodes["2"] = VibeNode("2", "M")
    wf.connect("1.0", "2.images")

    sidecar_ds = {"scale": 0.5, "offset": [42.0, 99.0]}
    sidecar_extra = {"ds": sidecar_ds}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, extra=sidecar_extra, include_main_positions=True)

    assert result["extra"]["ds"] == sidecar_ds, (
        f"sidecar ds must be preserved: {result['extra']['ds']}"
    )


# ---------------------------------------------------------------------------
# T17 — schema version 1.0 round-trip guard (Q2)
# ---------------------------------------------------------------------------
        groups = result.get("groups", [])
        assert len(groups) >= 1, f"Expected at least 1 group, got {len(groups)}: {groups}"
        titles = [g.get("title") for g in groups]
        assert "MySubgraphBox" in titles, (
            f"Subgraph group 'MySubgraphBox' missing from groups: {titles}"
        )

    def test_emit_ui_json_caller_groups_take_priority_over_engine_groups(self):
        """Caller-passed groups appear before engine groups, and duplicate titles are suppressed."""
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("priority_test", WorkflowSource("priority_test"))
        wf.add_node("TypeA", "1", uid="p1")
        wf.add_node("TypeB", "2", uid="p2")
        wf.connect("1.0", "2.x")

        wf.metadata = {
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg-p",
                        "name": "EngineGroup",
                        "nodes": [
                            {"id": 10, "properties": {"vibecomfy_uid": "p1"}},
                            {"id": 11, "properties": {"vibecomfy_uid": "p2"}},
                        ],
                    }
                ]
            }
        }

        caller_groups = [
            {"title": "CallerGroup", "bounding": [0, 0, 100, 100], "color": "#ffffff"},
            # Same title as engine group → should be suppressed from engine merge
            {"title": "EngineGroup", "bounding": [200, 200, 50, 50], "color": "#cccccc"},
        ]

        result = emit_ui_json(wf, groups=caller_groups)
        groups = result.get("groups", [])

        # Caller groups must appear first.
        assert len(groups) >= 2, f"Expected at least 2 groups, got {len(groups)}: {groups}"
        assert groups[0]["title"] == "CallerGroup", (
            f"First group should be 'CallerGroup', got {groups[0].get('title')}"
        )
        assert groups[1]["title"] == "EngineGroup", (
            f"Second group should be caller's 'EngineGroup', got {groups[1].get('title')}"
        )

        # Engine group with same title must NOT appear (deduplicated).
        engine_titles = [g["title"] for g in groups[2:]] if len(groups) > 2 else []
        assert "EngineGroup" not in engine_titles, (
            f"Engine group 'EngineGroup' should be deduplicated: {groups}"
        )

        # Caller's EngineGroup should retain its custom bounding (not overwritten by engine).
        # groups[0] = CallerGroup [0, 0, 100, 100]; groups[1] = EngineGroup [200, 200, 50, 50]
        assert groups[0]["bounding"] == [0.0, 0.0, 100.0, 100.0], (
            f"CallerGroup bounding should be preserved: {groups[0]['bounding']}"
        )
        assert groups[1]["bounding"] == [200.0, 200.0, 50.0, 50.0], (
            f"EngineGroup caller bounding should be preserved: {groups[1]['bounding']}"
        )


class TestEmitUiJsonByteIdentical:
    """T8: two emit_ui_json calls on the same workflow produce byte-identical JSON."""

    def test_emit_ui_json_byte_identical_two_calls(self):
        """json.dumps(emit_ui_json(wf), sort_keys=True) twice → identical."""
        import json
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource
        from vibecomfy.porting.emit.ui import emit_ui_json

        wf = VibeWorkflow("byte_id_test", WorkflowSource("byte_id_test"))
    from vibecomfy.porting.workbench import load_port_source

    corpus = str(_CORPUS_90A1D5)

    wf = load_workflow_any(corpus)
    assert len(wf.nodes) == 15
    assert wf.nodes["10"].class_type == "TripoRefineNode"
    assert len(wf.compile("api")) == 2

    loaded = load_port_source(corpus)
    assert len(loaded.workflow.nodes) == 15
    assert loaded.workflow.nodes["10"].class_type == "TripoRefineNode"
    assert len(loaded.workflow.compile("api")) == 2
    assert loaded.source_kind in {"indexed_json", "raw_json"}


def test_vibe_rich_ingest_is_idempotent() -> None:
    """rich->UI and UI->IR->UI produce identical projections (nodes, edges, widgets, groups)."""
    raw = _load_90a1d5()

    ui1 = normalize_agent_edit_graph(raw)  # rich -> UI
    assert len(ui1["nodes"]) == 15 and len(ui1["links"]) == 10

    # UI -> IR via the deterministic offline normalizer (the comfy converter
    # intentionally drops mode-4 bypassed nodes — ComfyUI semantics, unchanged).
    api2 = normalize_to_api(ui1, use_comfy_converter=False)
    wf2 = convert_to_vibe_format(api2)
    assert len(wf2.nodes) == 15 and len(wf2.edges) == 10

    ui2 = emit_ui_json(wf2, schema_provider=None, groups=deepcopy(ui1.get("groups")))

    assert _ui_projection(ui1) == _ui_projection(ui2)


def test_vibe_rich_ingest_rejects_malformed_mixed_entries() -> None:
    """Malformed/mixed rich entries raise ValueError; no partial graph is returned."""
    raw = _load_90a1d5()

    mixed_nodes = deepcopy(raw)
    mixed_nodes["nodes"]["999"] = "not-a-node"
    with pytest.raises(ValueError, match="must be mappings"):
        convert_to_vibe_format(mixed_nodes)

    key_mismatch = deepcopy(raw)
    key_mismatch["nodes"]["10"]["id"] = "11"
    with pytest.raises(ValueError, match="must equal node.id"):
        convert_to_vibe_format(key_mismatch)

    blank_uid = deepcopy(raw)
    blank_uid["nodes"]["10"]["uid"] = "  "
    with pytest.raises(ValueError, match="uid must be a nonblank string"):
tests/test_porting_ui_emitter.py:838:                "nodes": [],
tests/test_porting_ui_emitter.py:956:        "nodes": [{"id": 1, "type": "LoadImage", "inputs": [], "outputs": [{"slot_index": 0}], "widgets_values": []}],
tests/test_porting_ui_emitter.py:968:        "nodes": [
tests/test_porting_ui_emitter.py:984:        "nodes": [
tests/test_porting_ui_emitter.py:1559:        "subgraphs": [{"id": "sg-uuid", "name": "Sub", "nodes": [], "links": []}]
tests/test_layout_store.py:126:        "definitions": {"sub": {"nodes": []}},
tests/test_layout_store.py:144:    assert store["definitions"] == {"sub": {"nodes": []}}
tests/test_cli_port.py:177:        "nodes": [
tests/test_cli_port.py:249:            "nodes": [
tests/test_cli_port.py:535:                "nodes": [
tests/test_cli_port.py:566:            "nodes": [
tests/test_cli_port.py:1148:                "nodes": [
tests/test_cli_port.py:1210:                "nodes": [

codex
# Revised frozen plan

Execution order: **A → B → D+E → C → K → release gate**. Do not begin a batch until its checkpoint passes.

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
