Reading additional input from stdin...
2026-08-13T19:33:49.490266Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:33:49.490343Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:33:49.490357Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffc9d-ce2b-78f0-b101-6fa06ac47bbc
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 3 — review Batch D+E (IR-authoritative emission and groups + VibeEdge sole connectivity authority, [XHARD]).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: ec13a34e (Batch B). Batch D+E commit: 0d2bb176. Review `git diff ec13a34e..0d2bb176`. NOTE: the intervening 8a8300bb commit is the oracle-approved tasklist adjustment (docs only).

## Batch D+E tasks + acceptance gate (frozen tasklist.md, incl. your oracle-approved task 6)
Tasks 1-5: _resolve_furniture mode only via _get_node_mode(node) (single _ui fallback kept); remove groups param from emit_ui_json + all callers/tests; reconcile sidecar groups into wf.groups after _resolve_preserve_source; remap group membership during emission (aliases from node id/numeric source id/uid/_ui.id → id_remap LiteGraph ints; omit stale members); write_layout serializes wf.groups not metadata["groups"]. Task 6 (your addition): VibeEdge sole connectivity authority — migrate package-owned low-level link-pair-in-inputs construction to VibeEdge; from_api/from_ui as normalization boundaries (link pairs → edges, absent from node.inputs); fail closed on API-link-shaped values in node.inputs outside ingestion (decode/validate/serialize/compile); narrow predicate; collision tests.

## Host-verified evidence
- emit_ui_json signature (ui.py:2043-2051): NO groups parameter. rg 'groups=' across vibecomfy/ scripts/ *.py → zero emit calls with groups kwarg.
- commands/port/_export.py:482 calls emit_ui_json(workflow, schema_provider=..., force_drop_editor_only=..., **_emit_kwargs) — no groups.
- New D+E tests pass: 15 passed (mode_authority, group_members, furniture) + 17 passed (raw_api_link, edge_only, link, collision, envelope_decode_rejects, edge_only_connectivity) — 32 total green.
- Focused gate run: 371 passed / 13 failed / 6 skipped. Failure attribution (all verified by running at baselines):
  - 9 x test_offline_parity_gate_green_on_starter_set + test_corpus_roundtrip_parity_with_compile_api + test_offline_parity_never_imports_comfy — canonical_form mismatches (topology/widget_value A-vs-B diffs on ready_templates/sources/official/*.json). VERIFIED PRE-EXISTING: identical failure on main @ 0f515870 (pre-megado-run-2) and at 8a8300bb. Not introduced by D+E, A, or B.
  - 2 x corpus FileNotFoundError (90a1d5ff9044902e.json) — worktree has no gitignored external_workflows corpus; environmental, identical at HEAD.
  - 2 x TestCorpusWideInvariants timeouts — corpus-wide tests, environmental (no corpus in worktree).
- git diff --check clean. 16 files changed (9 code: _compile/_graph.py, _compile/_helpers.py, commands/port/_export.py, ingest/normalize.py, patches/ltx_lowvram.py, porting/emit/ui.py, porting/layout_store.py, runtime/eval/core.py, workflow.py; 7 tests).

## Your verdict
1. Verdict on Batch D+E: binary `PASS` or concrete issues (file:line). Confirm the acceptance gate — especially task 6 (collisions fail explicitly, canonical round trips unchanged) and tasks 1-5 (mode authority shared by compile+emit, groups remap, no kwarg).
2. Ruling on the 9 pre-existing parity-gate failures: they are a KNOWN pre-existing gap (red on main before run 2). Decide whether they block the release gate as-is or should be recorded as a pre-existing finding (recommend: record — they are outside this run's batches; the run's release gate should compare against the pre-existing baseline).
Do NOT edit anything. Read-only.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’ll use the `megaplan` review workflow and keep this strictly read-only. I’ll inspect the skill instructions first, then independently audit the commit diff, the acceptance points, and the claimed baseline failures.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megaplan/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
---
name: megaplan
description: AI agent harness for coordinating Claude and GPT to make and execute extremely robust plans.
---

# Megaplan

> **Before you invoke megaplan, run the `megaplan-prep` skill.** It's the front door for every run: it sizes the work (one plan vs. an epic), shapes the brief, and picks the profile (intelligence tier), robustness level, and thinking depth. Do not run `<launcher> init` without it.

**Scope:** This skill covers tooling — how to invoke and drive megaplan. For the decisions that come *before* invocation (scoping, brief, profile, robustness, depth), consult the **megaplan-prep** skill. If anything here contradicts megaplan-prep on decision-making content, megaplan-prep wins.

Route every step through the Arnold CLI's Megaplan subcommands. Never call agents directly.
Before the first CLI call, resolve a working launcher and reuse it for the whole run. Do not assume the removed `megaplan` entrypoint is on `PATH`; command presence alone is not enough. Prove the launcher works by successfully running a harmless CLI call with it first. In the instructions below, treat `<launcher>` as that verified command.
Launcher resolution order:
1. Try `python -m arnold_pipelines.megaplan config show`.
2. If that fails, try `./.venv/bin/python -m arnold_pipelines.megaplan config show`.
3. If that fails, try `uv run python -m arnold_pipelines.megaplan config show`.
4. If those fail, stop and report that the Arnold Megaplan module launcher is unavailable.
5. Do not use the removed `megaplan` module or console entrypoint; the repo-root `megaplan.py` file is a clean-break guard.
## Triage
Decision-making (scoping, profile, robustness, depth, brief structure) lives in the **megaplan-prep** skill — consult it before running `<launcher> init`. **Always run megaplan, even for tiny work** — `bare` robustness is the floor, never skip the harness. The few seconds of overhead pay back in the captured brief, plan, and outcome record.
## Modes
Megaplan has two output modes, picked with `--mode` at `init`:
- **`--mode code`** (default): the run produces a code diff. Execute workers emit per-task file changes. Use for features, refactors, bug fixes, migrations — anything whose deliverable is source code.
- **`--mode metaplan`** (alias: `--mode doc`): the run produces a single document artifact at `--output <relative/path>` (e.g. `docs/design.md`). The prep, execute, and review phases use authoring-specific prompts; the execute schema uses `sections_written` instead of file changes; auditing reasons about section delivery. Use for design docs, architecture specs, research notes, RFCs, proposals, post-mortems, migration plans — anything whose deliverable is prose, not code. This is the "design-first / preplan" workflow; `prep` is the visible repository-investigation *phase* inside every run (both modes have it), not a separate mode.

`--from-doc <relative/path>` works with either mode. The path must be relative to `--project-dir`, must stay inside that directory, and must point to an existing file. When present, `init` imports any `## Settled Decisions` section from that prior doc artifact and stores the source path for later planning and execution context.

All other flags (`--robustness`, `--auto-approve`, `--phase-model`, `--hermes`, subagent mode, overrides, step editing) behave identically in both modes. The workflow phases are the same: `prep → plan → critique → gate → revise → finalize → execute → review`.

A common pattern is two runs: first `--mode metaplan` to produce a rigorous design document, then `--mode code --from-doc docs/design.md` on a new idea that references that document to implement it.

**`--mode` and `--output` go together.** `init` rejects `--output` without `--mode metaplan` (error `invalid_args`), and rejects `--mode metaplan` without `--output`. Don't try to pass one without the other.
## Working tree default
Default to building on top of any existing uncommitted changes in the working tree, not stashing or resetting them. The plan author should treat the dirty tree as in-progress context the new work composes with. Only deviate when the existing changes directly contradict what the new plan needs to do — and then flag the conflict explicitly rather than silently overwriting.

## Start
Run `<launcher> config show` before `init`. If `raw_config.execution.auto_approve` is explicitly present, do not ask the execution-mode question and honor that configured override, including configured `false`. If that raw key is absent, ask execution mode (auto-approve or review) before `init`. In the same config check, respect `execution.robustness` as a settable override when it is configured; otherwise pick robustness yourself per the **megaplan-prep** skill.
```bash
<launcher> init --project-dir "$PROJECT_DIR" [--auto-approve] [--robustness bare|light|full|thorough|extreme] [--mode code|metaplan] [--output docs/foo.md] [--from-doc docs/prior.md] [--north-star path/to/NORTHSTAR.md] "$IDEA"
```
Legacy robustness names (`tiny|standard|robust|superrobust`) are still accepted on the CLI and in stored config — they map to `bare|full|thorough|extreme` respectively — but new plans should use the canonical names.
For metaplan-mode runs, pass `--mode metaplan --output <relative/path>` (the path is where the final document artifact is written, relative to the project dir). Everything else is identical to code mode.
Pass `--from-doc <relative/path>` when the new run should inherit decisions from a prior doc artifact. The path must be relative to the project dir, must exist as a file, and can be used with either `--mode code` or `--mode metaplan`. When the source doc contains a `## Settled Decisions` section, megaplan imports those decisions and automatically promotes them into success criteria for the new plan: `load_bearing: true` decisions become `must` criteria and `load_bearing: false` decisions become `info` criteria.

Pass `--north-star <path>` when the plan needs durable end-state intent beyond the local brief. `init` snapshots the UTF-8 markdown/text file into the plan under `anchors/north_star/plan.md`; later source edits do not affect the active plan. First iteration supports only the `north_star` anchor type. Decision-heavy prompts get full `## Anchor Context: North Star` blocks; review-family prompts get short `## Anchor Check: North Star` reminders; execution and feedback prompts get no anchor context.
## Settled Decisions Section Format
When authoring a doc artifact that makes design decisions, use either of these canonical markdown shapes (the parser accepts both):

Bold-dash inline shape (preferred for short decisions):
```md
## Settled Decisions

- **SD-001** \u2014 Keep the current storage model. _load_bearing: true_
  Rationale: External integrations depend on it.
- **SD-002** \u2014 Default model is claude-sonnet-4-6. _load_bearing: false_
  Rationale: Balance of speed and capability.
```

YAML-ish shape (preferred when decisions need more fields):
```md
## Settled Decisions
- id: SD-001
  load_bearing: true
  decision: Keep the current storage model
  rationale: External integrations depend on it.
```
Use one list item per decision. Keep the `SD-NNN` convention (`SD-` prefix plus a number), store `load_bearing` as `true` or `false`, and indent continuation lines by two spaces beneath the list-item marker.
Report the plan name, execution mode, robustness, mode (and `--output` path when metaplan mode), current state, and next step.
## Workflow
Run the loop in this order:
1. `prep`
2. `plan`
3. `critique`
4. `gate`
5. `revise` when gate recommends iteration
6. `finalize`
7. `execute`
8. `review`
Use `next_step` and `valid_next` for CLI routing. After `gate`, follow `orchestrator_guidance` instead of manually interpreting gate signals. When a response includes `next_step_runtime`, use its `duration_hint` and `recommended_next_check_seconds` to calibrate timing.
At `--robustness bare`, the loop is: `plan` → `finalize` → `execute`. There is no prep, no critique, no gate, and no review.
At `--robustness light`, the loop is: `plan` → `critique` → `revise` → `finalize` → `execute`. There is no prep, no gate, and no review.
At `--robustness full`, the loop is: `prep` → `plan` → `critique` → `gate` → ...
At `--robustness thorough`, the loop is also `prep` → `plan` → `critique` → `gate` → ... but uses 8 critique checks instead of 4 and enables parallel critique.
At `--robustness extreme`, the loop is the same as thorough but also enables parallel review.
## Step Rules
- `plan`: inspect the repository first; produce the plan plus `questions`, `assumptions`, and `success_criteria`. Each criterion is `{"criterion": "...", "priority": "must|should|info"}`. `must` = hard gate (reviewer blocks), `should` = quality target (reviewer flags but doesn't block), `info` = human reference (reviewer skips).
- `prep`: make repository investigation explicit before planning. Respect `skip: true` when the task is already concrete enough.
- `critique`: surface concrete flags with concern, evidence, category, and severity; reuse open flag IDs; call out scope creep. Also validate that success criteria priorities are well-calibrated — `must` criteria should be verifiable yes/no, subjective goals should be `should`.
- `gate`: read the response, warnings, and `orchestrator_guidance`. (Skipped at light robustness.)
- `revise`: show the delta, flags addressed, and flags remaining. At light robustness, routes to `finalize`; otherwise loops back through `critique` and `gate`.
- `review`: judge success against the success criteria and the user's intent, not plan elegance. Only block on `must` criteria failures. `should` failures are flagged but don't require rework. `info` criteria are waived.
## Gate Principle
The gate response tells the orchestrator what to do next. Follow `orchestrator_guidance` unless you have a concrete reason to disagree after investigating the repository or plan artifacts yourself.
Investigate before disagreeing: read the current plan and critique artifacts, check the project code to verify whether a flagged issue is real, or use `<launcher> status --plan <name>` / `<launcher> audit --plan <name>`.
If you disagree with the guidance, explain why briefly and use an override. Do not manually reinterpret score trajectory, flag quality, or loop state when the gate already did that work for you.
## Execute
- After a successful gate, run `<launcher> finalize` to produce the execution-ready briefing document.
- In auto-approve mode, run `<launcher> execute --confirm-destructive` after finalize.
- In review mode, pause at the finalize-to-execute checkpoint and wait for explicit approval before running:
```bash
<launcher> execute --confirm-destructive --user-approved
```
## Long-Running Execution
For plans with multiple batches, use per-batch mode to drive execution incrementally:
```bash
<launcher> execute --plan <name> --confirm-destructive --user-approved --batch 1
<launcher> execute --plan <name> --confirm-destructive --user-approved --batch 2
# ... continue until all batches complete
```
Between batches, poll progress:
```bash
<launcher> progress --plan <name>
```
Use `<launcher> status --plan <name>` for the full plan state, including active-step timing and any `next_step_runtime` guidance from the latest response.
Per-batch mode uses global batch numbering (1-indexed, computed from ALL tasks). Each `--batch N` call:
- Validates that batches 1..N-1 are complete
- Executes only batch N's tasks
- Writes `execution_batch_N.json` as evidence
- On the final batch, produces aggregate `execution.json` and transitions to `executed`
Timeout recovery: re-run the same `--batch N`. The harness checks prerequisite completion and merges only untracked tasks.
Note: `progress` shows completed state only (between-batch granularity). With per-batch mode, each batch is a separate CLI call, so the orchestrator has full visibility.
## Overrides
- `<launcher> override add-note --plan <name> --note "..."`
- `<launcher> override force-proceed --plan <name> --reason "..."`
- `<launcher> override replan --plan <name> --reason "..." [--note "..."]`
- `<launcher> override abort --plan <name> --reason "..."`
`force-proceed` is available from `critiqued` (routes to finalize, not execute). `replan` is available from `gated`, `finalized`, or `critiqued`. `add-note` is safe from any active state.
## Replan
Use `replan` when the orchestrator itself needs to edit the plan directly instead of asking the revise worker to do it.
```bash
<launcher> override replan --plan <name> --reason "expanding scope" --note "Also clean up the display layer"
```
After `replan`, read the returned plan file, edit it directly, then run `<launcher> critique`.
## Step Editing
Use `step` when you need to insert, remove, or reorder step sections (`## Step N:` or `### Step N:`) without hand-editing the markdown.
```bash
<launcher> step add --plan <name> --after S3 "Add regression coverage for the parser"
<launcher> step remove --plan <name> S4
<launcher> step move --plan <name> S4 --after S2
```
Each edit writes a new same-iteration plan artifact, preserves the latest plan meta questions/success criteria/assumptions, and resets the plan to `planned` so it re-enters critique.
## Sessions And Autonomy
- Agents default to persistent sessions.
- `--fresh`: start a new persistent session.
- `--ephemeral`: one-off call with no saved session.
- `--persist`: explicit persistent mode.
- Keep moving and show results at each step.
- Only pause at finalize to execute in review mode.
## Configuration
View current defaults with `<launcher> config show`. Override with `<launcher> config set <key> <value>`. Reset with `<launcher> config reset`.
When routing or behavior depends on config, check `<launcher> config show` and respect user overrides instead of assuming defaults.
Settable execution keys: `execution.auto_approve`, `execution.robustness`.
## Profiles
A profile is a named preset that maps each workflow phase to an agent/model spec. Pass `--profile <name>` to any command that accepts `--phase-model` (`init`, `loop-init`, `tiebreaker`, etc.) to apply the preset.
See **megaplan-prep** for profile selection. Inspect available profiles with `<launcher> config profiles list`.
Resolution order, later overrides earlier within the same name: built-in (`megaplan/profiles/*.toml`) → user (`~/.config/megaplan/profiles.toml`, or `$XDG_CONFIG_HOME/megaplan/profiles.toml`) → project (`<project_dir>/.megaplan/profiles.toml`).
Inspect with `<launcher> config profiles list` and `<launcher> config profiles show <name>`.
File format: TOML with a `[profiles.<name>]` table. Keys are phase names (`plan`, `prep`, `critique`, `revise`, `gate`, `finalize`, `execute`, `loop_plan`, `loop_execute`, `review`, `tiebreaker_researcher`, `tiebreaker_challenger`); values are agent specs like `"claude"`, `"codex"`, `"hermes:fireworks:accounts/fireworks/models/kimi-k2p6"`, `"hermes:glm-5.1"`. Example:
```toml
[profiles.my-mix]
plan     = "claude"
critique = "codex"
execute  = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
review   = "codex"
```
`--phase-model` overrides on the CLI stack on top of any profile.

### Fallback chains (v1)

Phase spec values can also be **TOML string arrays** to declare an ordered fallback chain. The first element is the selected spec; subsequent elements are only tried when the preceding spec fails with a retryable availability or infrastructure error and the next spec crosses a provider-family boundary. Example:

```toml
[profiles.safe-mix]
plan   = ["claude", "codex"]
review = ["codex:gpt-5.5", "claude:sonnet"]
```

**This is the only v1 entry point for fallback chains.** Comma-separated strings, CLI fallback-list flags, and YAML chain editing syntax are not supported in v1 and are deferred to later versions.

Internally, multi-spec phase values are persisted in `state.json` using the compact `__fallback_json__:<json-array>` encoding. This encoding is an implementation detail of the persistence bridge — you never write it by hand. The harness decodes it transparently; every downstream consumer sees the selected spec (first element) as the legacy scalar value.

**Fallback advancement rules (v1):**
- **Allowed:** Fallback advances to the next spec only on retryable **availability** or **infrastructure** failures (connection errors, timeouts, crashes, service unavailable, internal errors).
- **Blocked:** Fallback does **not** advance for malformed output, schema failures, test/evidence failures, blocked results, gate/review rejection, semantic failures, auth errors, quota exhaustion, rate limits, bad requests, unsupported models, or context-window errors.
- **Cross-provider requirement:** The next spec must belong to a different provider family than the failing spec (e.g., `claude` → `codex`, or `hermes:deepseek` → `hermes:fireworks`). Same-provider advancement is rejected.
- **execute / loop_execute:** Fallback chains are preserved in state but advancement beyond the first spec is **blocked** in v1 — the harness raises `ExecuteFallbackUnsafe` if a retryable failure would trigger a second attempt. This protects against duplicate side effects (file mutations, checkpoints, merges).

When an explicit fallback chain is configured for a phase, ambient runtime fallback (e.g., automatic provider retry) is **suppressed** — only the declared chain controls advancement.
## Bakeoff
See the **bakeoff** skill for methodology and the **megaplan-prep** skill for when bake-offs earn their cost. This section covers the CLI mechanics once you've decided to run one.

`<launcher> bakeoff run` runs the same idea through multiple profiles concurrently, each in its own git worktree, each driven autonomously by `<launcher> auto`. Use it when the user wants to compare profiles head-to-head on the same task (e.g., "run this with kimi and the default profile side-by-side").
Supports `--mode code` (default) and `--mode doc` / `--mode metaplan` (alias). For doc-mode bake-offs, `--output <relative/path>` is required and is threaded into each profile's `<launcher> init`; merge brings the chosen profile's doc artifact back to main instead of applying a code patch. Joke mode is not yet supported.
Requires a clean main worktree by default — pass `--allow-dirty` when there are unrelated uncommitted changes you want to keep on main. Those changes stay on main and are NOT copied into the worktrees, since worktrees branch off the current commit's SHA.
The idea must be a file (`--idea-file <path>`), not an inline string. Write the idea to a file first.
Bakeoff is inherently autonomous (it spawns `<launcher> auto`), so the execution-mode question doesn't apply to bakeoff runs. `--robustness` is forwarded to each profile's `init`. When a project-layer `.megaplan/profiles.toml` exists, it's automatically copied into each worktree so project-only profiles resolve.
Lifecycle:
- `<launcher> bakeoff run --idea-file <path> --profiles <p1> <p2> [--mode code|doc|metaplan] [--output <relative/path>] [--exp-id <id>] [--detach] [--robustness <level>] [--allow-dirty]` — kicks off N concurrent profile runs. Without `--detach` it streams a live status table every 5s and blocks until all profiles finish; with `--detach` it returns immediately and the user polls via `status`. `--output` is required with `--mode doc|metaplan` and rejected with `--mode code`.
- `<launcher> bakeoff status [--exp <id>]` — current state of each profile (running / completed / crashed).
- `<launcher> bakeoff tail [--exp <id>]` — tail the per-profile auto logs.
- `<launcher> bakeoff compare --exp <id> [--judge <model>]` — collect metrics across profiles; with `--judge`, an LLM judge ranks the outputs.
- `<launcher> bakeoff pick --exp <id> --profile <name> --rationale "..."` — record the human-selected winner.
- `<launcher> bakeoff merge --exp <id>` — merge the chosen profile's worktree back to main.
- `<launcher> bakeoff resume --exp <id>` — resume unfinished profile runs.
- `<launcher> bakeoff abandon --exp <id>` — discard worktrees but keep audit data.
## Cloud Mode
`<launcher> cloud` runs a plan inside a provider-managed container with a persistent workspace volume, so the run survives the user's terminal session. Suggest it for long-running plans that would outlast a local session, multi-repo work, or when the user wants an isolated persistent sandbox. The supported remote path is `provider: ssh` against the Hetzner agentbox; `provider: local` remains for local iteration and CI smoke tests.

Quick subcommand reference: `init`, `build`, `deploy`, `chain`, `status`, `attach`, `logs`, `exec`, `resume`, `down`, `destroy`. Typical flow: `<launcher> cloud init` → edit `cloud.yaml` → export secrets → `<launcher> cloud deploy` → `<launcher> cloud chain <chain.yaml>`.

For the full reference — `cloud.yaml` fields, the `extra_repos[]` + `chain_session` multi-tenancy model, the operator loop, and the gotchas that wedge fresh runs (committed `chain_state.json`, profile-alias gap, secret-upload behavior, "internal_error" masking credit failures) — see the **megaplan-cloud** skill. Read it before launching the first cloud chain in a new project; the gotchas section will save hours.
## Tickets
`<launcher> ticket new` creates a repo-scoped issue ticket. Use it when:
- During epic/plan work you notice an out-of-scope problem, bug, or rough edge
- A user explicitly asks you to capture something for later attention
- You want to log an observation that doesn't block the current task but should be tracked

The command prints only a ULID to stdout on success. Tickets live as `.megaplan/tickets/{ulid}-{slug}.md` files and are auto-discovered by the planner for future epics. Link them to epics with `<launcher> ticket link <ticket> <epic> --resolves` so they auto-address when the epic completes.

## Briefs
`<launcher> brief` creates canonical source artifacts for work you intend to run.
Use it when:
- You are turning an idea into a durable single-plan input
- You are scaffolding an epic's `chain.yaml` and milestone idea files
- You want the source document committed before `<launcher> init` snapshots it into plan state

Briefs live as committed files under `.megaplan/initiatives/{slug}/`. Single-plan
ideas live at `.megaplan/initiatives/{slug}/briefs/{slug}.md`; epics live at
`.megaplan/initiatives/{epic-slug}/chain.yaml` with milestone briefs under the
initiative's `briefs/` directory. This is ticket-like in storage and ergonomics, but not in lifecycle:
briefs feed `<launcher> init` / `<launcher> chain start`; tickets are open problem
notes that can be discovered, linked, and auto-addressed by epics.

Briefs and tickets share the local artifact substrate: common `.megaplan/<kind>/`
path handling, slug normalization, optional frontmatter parsing, keyword
filtering, and snippets. Use `<launcher> brief list`, `<launcher> brief show`, and
`<launcher> brief search` for the brief side of that common read surface.

For epics, `<launcher> brief epic` also scaffolds `NORTHSTAR.md` beside

codex
The Megaplan skill’s relevant rule here is to judge the batch against the frozen “must” criteria, not general plan elegance. I’m not invoking or mutating the run; I’m treating this as its read-only review checkpoint. First pass is commit scope and exact changed code/tests.
exec
/bin/zsh -lc 'git status --short && git log --oneline --decorate -5 && git diff --stat ec13a34e..0d2bb176 && git diff --check ec13a34e..0d2bb176 && git diff --name-status ec13a34e..0d2bb176' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 2 in 217ms:
0d2bb176 (HEAD -> elegance-run2) megado run2 Batch D+E: IR-authoritative emission — mode via node.mode only, groups kwarg removed + member-ID remap, wf.groups reconciled, VibeEdge sole connectivity authority
8a8300bb megado run2: oracle-approved plan adjustments — D+E#6 VibeEdge sole connectivity authority, K#4 collision-safe UID minting
ec13a34e megado run2 Batch B: remove convert_to_vibe_format — migrate 15 callers to named importers, guard test, scratchpad emits from_api
ae6f1e9a megado run2: record Batch A checkpoint PASS
2b60f74a megado run2 Batch A rework: b02-corpus-full expected count 2825 (oracle issue)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-2.md              | 11095 +++++++++++++++++++++++++++++
 .oracle/tasklist.md                      |    19 +
 tests/test_foundation_utils.py           |    15 +-
 tests/test_layout_store.py               |     7 +-
 tests/test_patches.py                    |     5 +-
 tests/test_porting_normalize_ingest.py   |     3 +-
 tests/test_porting_synthetic_fixtures.py |     4 +-
 tests/test_porting_ui_emitter.py         |   104 +-
 tests/test_schema_validate.py            |    29 +-
 tests/test_ui_layout.py                  |     5 +-
 tests/test_workflow_core.py              |   176 +-
 vibecomfy/_compile/_graph.py             |    27 +-
 vibecomfy/_compile/_helpers.py           |    10 +-
 vibecomfy/commands/port/_export.py       |     5 +-
 vibecomfy/ingest/normalize.py            |    29 +-
 vibecomfy/patches/ltx_lowvram.py         |    20 +-
 vibecomfy/porting/emit/ui.py             |   133 +-
 vibecomfy/porting/layout_store.py        |     8 +-
 vibecomfy/runtime/eval/core.py           |    12 +-
 vibecomfy/schema/validate.py             |     9 +-
 vibecomfy/workflow.py                    |    97 +-
 21 files changed, 11649 insertions(+), 163 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2.md:903: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:905: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:924: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:938: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:946: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:953: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:960: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:968: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:985: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:990: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:991: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:996: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1009: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1011: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1015: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1016: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1023: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1025: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1029: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1030: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1037: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1039: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1043: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1044: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1053: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1057: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1058: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1067: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1071: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1072: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1081: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1085: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1086: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1095: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1099: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1100: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1107: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1109: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1113: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1114: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1121: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1123: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1128: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1135: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1137: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1154: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1167: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1169: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1180: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1183: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1198: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1200: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1201: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1209: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1210: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1230: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1232: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1237: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1238: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1241: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1242: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1262: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1263: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1272: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1273: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1276: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1291: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1293: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1307: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1323: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1329: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1331: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1332: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1338: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1378: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1387: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1389: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1394: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1403: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1409: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1411: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1414: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1420: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1425: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1439: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1457: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1458: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1466: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1467: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1474: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1479: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1483: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1499: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1505: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1514: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1515: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1522: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1528: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1533: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1536: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1537: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1544: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1550: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1555: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1558: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1559: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1566: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1572: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1577: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1580: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1581: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1588: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1594: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1599: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1602: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1603: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1610: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1616: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1624: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1625: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1632: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1638: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1646: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1647: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1652: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1655: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1660: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1663: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1668: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1669: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1674: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1677: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1682: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1685: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1690: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1691: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1698: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1704: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1709: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1719: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1722: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1725: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1727: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1734: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1748: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1749: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1754: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1759: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1768: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1781: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1788: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1790: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1791: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1803: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1808: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1810: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1814: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1819: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1834: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1835: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1837: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1838: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1843: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1849: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1850: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1854: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1862: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1866: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1867: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1871: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1872: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1877: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1878: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1883: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1892: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1894: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1900: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1901: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1909: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1921: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1922: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1928: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1932: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1933: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1939: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1940: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1950: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1954: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1955: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1960: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1967: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1968: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1975: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1976: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1986: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1987: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1997: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:1998: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2016: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2017: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2027: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2028: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2056: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2059: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2069: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2071: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2075: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2083: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2085: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2091: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2094: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2102: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2103: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2109: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2113: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2114: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2120: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2124: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2125: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2133: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2135: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2136: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2142: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2153: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2157: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2158: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2173: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2175: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2178: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2179: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2184: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2185: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2189: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2193: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2194: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2198: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2201: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2202: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2206: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2210: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2211: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2215: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2218: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2219: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2223: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2225: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2226: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2231: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2234: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2237: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2242: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2245: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2248: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2253: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2256: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2264: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2267: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2269: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2270: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2275: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2278: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2281: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2282: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2287: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2295: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2298: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2306: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2308: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2313: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2314: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2318: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2322: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2328: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2329: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2337: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2339: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2349: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2355: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2356: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2360: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2365: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2367: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2371: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2376: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2378: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2381: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2390: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2396: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2398: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2403: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2404: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2408: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2409: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2413: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2414: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2416: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2431: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2441: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2446: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2447: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2454: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2482: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2483: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2492: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2493: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2500: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2501: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2515: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2522: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2524: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2530: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2533: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2540: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2544: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2551: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2552: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2554: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2561: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2563: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2565: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2571: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2577: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2583: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2589: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2595: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2596: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2606: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2614: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2622: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2623: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2633: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2639: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2645: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2646: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2651: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2664: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2666: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2671: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2688: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2689: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2702: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2703: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2725: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2729: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2747: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2750: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2761: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2769: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2773: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2783: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2795: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2802: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2803: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2808: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2812: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2818: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2820: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2822: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2823: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2829: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2842: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2845: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2853: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2859: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2862: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2864: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2869: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2872: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2875: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2878: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2881: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2884: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2885: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2890: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2896: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2897: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2903: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2906: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2911: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2919: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2922: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2927: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2932: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2933: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2939: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2944: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2952: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2955: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2978: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2982: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2986: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2989: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2992: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:2998: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3011: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3015: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3025: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3034: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3036: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3060: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3063: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3071: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3078: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3082: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3083: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3089: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3093: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3094: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3100: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3104: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3105: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3111: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3115: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3116: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3123: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3126: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3127: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3133: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3135: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3137: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3138: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3144: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3146: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3148: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3149: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3155: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3157: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3159: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3160: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3170: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3171: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3178: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3181: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3182: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3189: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3193: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3194: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3200: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3201: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3203: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3204: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3210: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3212: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3220: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3221: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3231: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3242: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3259: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3260: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3267: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3280: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3281: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3294: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3295: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3306: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3309: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3316: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3317: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3335: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3336: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3353: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3354: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3375: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3376: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3400: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3402: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3416: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3418: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3425: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3428: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3434: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3436: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3452: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3454: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3462: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3468: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3469: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3478: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3479: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3483: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3506: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3509: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3513: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3515: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3523: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3546: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3549: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3566: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3567: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3572: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3573: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3605: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3606: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3627: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3628: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3639: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3647: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3657: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3658: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3662: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3663: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3681: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3687: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3702: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3710: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3719: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3722: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3748: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3749: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3754: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3777: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3781: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3793: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3802: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3823: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3842: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3847: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3883: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3897: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3898: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3942: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3945: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3952: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3963: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3967: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:3986: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4000: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4008: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4015: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4045: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4051: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4068: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4069: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4076: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4077: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4079: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4080: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:4117: trailing whitespace.
+   719	
.oracle/checkins/batch-2.md:4124: trailing whitespace.
+   726	
.oracle/checkins/batch-2.md:4126: trailing whitespace.
+   728	
.oracle/checkins/batch-2.md:4128: trailing whitespace.
+   730	
.oracle/checkins/batch-2.md:4129: trailing whitespace.
+   731	
.oracle/checkins/batch-2.md:4132: trailing whitespace.
+   734	
.oracle/checkins/batch-2.md:4138: trailing whitespace.
+   740	
.oracle/checkins/batch-2.md:4139: trailing whitespace.
+   741	
.oracle/checkins/batch-2.md:4167: trailing whitespace.
+   769	
.oracle/checkins/batch-2.md:4168: trailing whitespace.
+   770	
.oracle/checkins/batch-2.md:4184: trailing whitespace.
+   786	
.oracle/checkins/batch-2.md:4185: trailing whitespace.
+   787	
.oracle/checkins/batch-2.md:4192: trailing whitespace.
+   794	
.oracle/checkins/batch-2.md:4193: trailing whitespace.
+   795	
.oracle/checkins/batch-2.md:4227: trailing whitespace.
+   829	
.oracle/checkins/batch-2.md:4228: trailing whitespace.
+   830	
.oracle/checkins/batch-2.md:4287: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:4291: trailing whitespace.
+     6	
.oracle/checkins/batch-2.md:4292: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:4299: trailing whitespace.
+    14	
.oracle/checkins/batch-2.md:4300: trailing whitespace.
+    15	
.oracle/checkins/batch-2.md:4311: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:4313: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:4315: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:4317: trailing whitespace.
++    15	
.oracle/checkins/batch-2.md:4319: trailing whitespace.
++    31	
.oracle/checkins/batch-2.md:4321: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:4323: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:4325: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:4327: trailing whitespace.
++    43	
.oracle/checkins/batch-2.md:4329: trailing whitespace.
++    45	
.oracle/checkins/batch-2.md:4331: trailing whitespace.
++    53	
.oracle/checkins/batch-2.md:4333: trailing whitespace.
++    58	
.oracle/checkins/batch-2.md:4335: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:4337: trailing whitespace.
++    65	
.oracle/checkins/batch-2.md:4339: trailing whitespace.
++    66	
.oracle/checkins/batch-2.md:4341: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:4343: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:4345: trailing whitespace.
++    83	
.oracle/checkins/batch-2.md:4347: trailing whitespace.
++    84	
.oracle/checkins/batch-2.md:4349: trailing whitespace.
++    88	
.oracle/checkins/batch-2.md:4351: trailing whitespace.
++    89	
.oracle/checkins/batch-2.md:4353: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:4355: trailing whitespace.
++    98	
.oracle/checkins/batch-2.md:4357: trailing whitespace.
++   110	
.oracle/checkins/batch-2.md:4359: trailing whitespace.
++   111	
.oracle/checkins/batch-2.md:4361: trailing whitespace.
++   116	
.oracle/checkins/batch-2.md:4363: trailing whitespace.
++   117	
.oracle/checkins/batch-2.md:4365: trailing whitespace.
++   135	
.oracle/checkins/batch-2.md:4367: trailing whitespace.
++   136	
.oracle/checkins/batch-2.md:4369: trailing whitespace.
++   149	
.oracle/checkins/batch-2.md:4371: trailing whitespace.
++   150	
.oracle/checkins/batch-2.md:4373: trailing whitespace.
++   163	
.oracle/checkins/batch-2.md:4375: trailing whitespace.
++   164	
.oracle/checkins/batch-2.md:4377: trailing whitespace.
++   173	
.oracle/checkins/batch-2.md:4379: trailing whitespace.
++   174	
.oracle/checkins/batch-2.md:4381: trailing whitespace.
++   180	
.oracle/checkins/batch-2.md:4383: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:4385: trailing whitespace.
++   191	
.oracle/checkins/batch-2.md:4387: trailing whitespace.
++   192	
.oracle/checkins/batch-2.md:4389: trailing whitespace.
++   198	
.oracle/checkins/batch-2.md:4391: trailing whitespace.
++   199	
.oracle/checkins/batch-2.md:4393: trailing whitespace.
++   206	
.oracle/checkins/batch-2.md:4395: trailing whitespace.
++   207	
.oracle/checkins/batch-2.md:4397: trailing whitespace.
++   223	
.oracle/checkins/batch-2.md:4399: trailing whitespace.
++   224	
.oracle/checkins/batch-2.md:4401: trailing whitespace.
++   228	
.oracle/checkins/batch-2.md:4403: trailing whitespace.
++   229	
.oracle/checkins/batch-2.md:4405: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:4407: trailing whitespace.
++   233	
.oracle/checkins/batch-2.md:4409: trailing whitespace.
++   237	
.oracle/checkins/batch-2.md:4411: trailing whitespace.
++   238	
.oracle/checkins/batch-2.md:4413: trailing whitespace.
++   242	
.oracle/checkins/batch-2.md:4415: trailing whitespace.
++   243	
.oracle/checkins/batch-2.md:4417: trailing whitespace.
++   250	
.oracle/checkins/batch-2.md:4419: trailing whitespace.
++   251	
.oracle/checkins/batch-2.md:4421: trailing whitespace.
++   254	
.oracle/checkins/batch-2.md:4423: trailing whitespace.
++   271	
.oracle/checkins/batch-2.md:4425: trailing whitespace.
++   275	
.oracle/checkins/batch-2.md:4427: trailing whitespace.
++   278	
.oracle/checkins/batch-2.md:4429: trailing whitespace.
++   288	
.oracle/checkins/batch-2.md:4431: trailing whitespace.
++   307	
.oracle/checkins/batch-2.md:4433: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:4435: trailing whitespace.
++   324	
.oracle/checkins/batch-2.md:4437: trailing whitespace.
++   336	
.oracle/checkins/batch-2.md:4439: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:4441: trailing whitespace.
++     8	
.oracle/checkins/batch-2.md:4443: trailing whitespace.
++    10	
.oracle/checkins/batch-2.md:4445: trailing whitespace.
++    21	
.oracle/checkins/batch-2.md:4447: trailing whitespace.
++    24	
.oracle/checkins/batch-2.md:4449: trailing whitespace.
++    25	
.oracle/checkins/batch-2.md:4451: trailing whitespace.
++    28	
.oracle/checkins/batch-2.md:4453: trailing whitespace.
++    29	
.oracle/checkins/batch-2.md:4455: trailing whitespace.
++    55	
.oracle/checkins/batch-2.md:4457: trailing whitespace.
++    56	
.oracle/checkins/batch-2.md:4459: trailing whitespace.
++    61	
.oracle/checkins/batch-2.md:4461: trailing whitespace.
++    62	
.oracle/checkins/batch-2.md:4463: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:4465: trailing whitespace.
++    72	
.oracle/checkins/batch-2.md:4467: trailing whitespace.
++    79	
.oracle/checkins/batch-2.md:4469: trailing whitespace.
++    80	
.oracle/checkins/batch-2.md:4471: trailing whitespace.
++    94	
.oracle/checkins/batch-2.md:4473: trailing whitespace.
++    95	
.oracle/checkins/batch-2.md:4475: trailing whitespace.
++   102	
.oracle/checkins/batch-2.md:4477: trailing whitespace.
++   104	
.oracle/checkins/batch-2.md:4479: trailing whitespace.
++   111	
.oracle/checkins/batch-2.md:4481: trailing whitespace.
++   113	
.oracle/checkins/batch-2.md:4483: trailing whitespace.
++   119	
.oracle/checkins/batch-2.md:4485: trailing whitespace.
++   128	
.oracle/checkins/batch-2.md:4487: trailing whitespace.
++   140	
.oracle/checkins/batch-2.md:4489: trailing whitespace.
++   162	
.oracle/checkins/batch-2.md:4491: trailing whitespace.
++   171	
.oracle/checkins/batch-2.md:4493: trailing whitespace.
++   201	
.oracle/checkins/batch-2.md:4495: trailing whitespace.
++   202	
.oracle/checkins/batch-2.md:4497: trailing whitespace.
++   214	
.oracle/checkins/batch-2.md:4499: trailing whitespace.
++   215	
.oracle/checkins/batch-2.md:4501: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:4503: trailing whitespace.
++   245	
.oracle/checkins/batch-2.md:4505: trailing whitespace.
++   248	
.oracle/checkins/batch-2.md:4507: trailing whitespace.
++   266	
.oracle/checkins/batch-2.md:4509: trailing whitespace.
++   313	
.oracle/checkins/batch-2.md:4511: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:4513: trailing whitespace.
++   335	
.oracle/checkins/batch-2.md:4515: trailing whitespace.
++   339	
.oracle/checkins/batch-2.md:4517: trailing whitespace.
++   360	
.oracle/checkins/batch-2.md:4519: trailing whitespace.
++   361	
.oracle/checkins/batch-2.md:4521: trailing whitespace.
++   385	
.oracle/checkins/batch-2.md:4523: trailing whitespace.
++   386	
.oracle/checkins/batch-2.md:4529: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4531: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4533: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4535: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4537: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4543: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4547: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4549: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4551: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4553: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4555: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4557: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4559: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4561: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4563: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4565: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4567: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4569: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4571: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4573: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4575: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4577: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4579: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4581: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4583: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4585: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4587: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4589: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4591: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4593: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4595: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4597: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4599: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4601: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4603: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:4605: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:4607: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:4609: trailing whitespace.
++    15	
.oracle/checkins/batch-2.md:4611: trailing whitespace.
++    31	
.oracle/checkins/batch-2.md:4613: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:4615: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:4617: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:4619: trailing whitespace.
++    43	
.oracle/checkins/batch-2.md:4621: trailing whitespace.
++    45	
.oracle/checkins/batch-2.md:4623: trailing whitespace.
++    53	
.oracle/checkins/batch-2.md:4625: trailing whitespace.
++    58	
.oracle/checkins/batch-2.md:4627: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:4629: trailing whitespace.
++    65	
.oracle/checkins/batch-2.md:4631: trailing whitespace.
++    66	
.oracle/checkins/batch-2.md:4633: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:4635: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:4637: trailing whitespace.
++    83	
.oracle/checkins/batch-2.md:4639: trailing whitespace.
++    84	
.oracle/checkins/batch-2.md:4641: trailing whitespace.
++    88	
.oracle/checkins/batch-2.md:4643: trailing whitespace.
++    89	
.oracle/checkins/batch-2.md:4645: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:4647: trailing whitespace.
++    98	
.oracle/checkins/batch-2.md:4649: trailing whitespace.
++   110	
.oracle/checkins/batch-2.md:4651: trailing whitespace.
++   111	
.oracle/checkins/batch-2.md:4653: trailing whitespace.
++   116	
.oracle/checkins/batch-2.md:4655: trailing whitespace.
++   117	
.oracle/checkins/batch-2.md:4657: trailing whitespace.
++   135	
.oracle/checkins/batch-2.md:4659: trailing whitespace.
++   136	
.oracle/checkins/batch-2.md:4661: trailing whitespace.
++   149	
.oracle/checkins/batch-2.md:4663: trailing whitespace.
++   150	
.oracle/checkins/batch-2.md:4665: trailing whitespace.
++   163	
.oracle/checkins/batch-2.md:4667: trailing whitespace.
++   164	
.oracle/checkins/batch-2.md:4669: trailing whitespace.
++   173	
.oracle/checkins/batch-2.md:4671: trailing whitespace.
++   174	
.oracle/checkins/batch-2.md:4673: trailing whitespace.
++   180	
.oracle/checkins/batch-2.md:4675: trailing whitespace.
++   180	
.oracle/checkins/batch-2.md:4677: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:4679: trailing whitespace.
++   191	
.oracle/checkins/batch-2.md:4681: trailing whitespace.
++   192	
.oracle/checkins/batch-2.md:4683: trailing whitespace.
++   198	
.oracle/checkins/batch-2.md:4685: trailing whitespace.
++   199	
.oracle/checkins/batch-2.md:4687: trailing whitespace.
++   206	
.oracle/checkins/batch-2.md:4689: trailing whitespace.
++   207	
.oracle/checkins/batch-2.md:4691: trailing whitespace.
++   223	
.oracle/checkins/batch-2.md:4693: trailing whitespace.
++   224	
.oracle/checkins/batch-2.md:4695: trailing whitespace.
++   228	
.oracle/checkins/batch-2.md:4697: trailing whitespace.
++   229	
.oracle/checkins/batch-2.md:4699: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:4701: trailing whitespace.
++   233	
.oracle/checkins/batch-2.md:4703: trailing whitespace.
++   237	
.oracle/checkins/batch-2.md:4705: trailing whitespace.
++   238	
.oracle/checkins/batch-2.md:4707: trailing whitespace.
++   242	
.oracle/checkins/batch-2.md:4709: trailing whitespace.
++   243	
.oracle/checkins/batch-2.md:4711: trailing whitespace.
++   250	
.oracle/checkins/batch-2.md:4713: trailing whitespace.
++   251	
.oracle/checkins/batch-2.md:4715: trailing whitespace.
++   254	
.oracle/checkins/batch-2.md:4717: trailing whitespace.
++   271	
.oracle/checkins/batch-2.md:4719: trailing whitespace.
++   275	
.oracle/checkins/batch-2.md:4721: trailing whitespace.
++   278	
.oracle/checkins/batch-2.md:4723: trailing whitespace.
++   288	
.oracle/checkins/batch-2.md:4725: trailing whitespace.
++   307	
.oracle/checkins/batch-2.md:4727: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:4729: trailing whitespace.
++   324	
.oracle/checkins/batch-2.md:4731: trailing whitespace.
++   336	
.oracle/checkins/batch-2.md:4733: trailing whitespace.
++   347	
.oracle/checkins/batch-2.md:4735: trailing whitespace.
++   352	
.oracle/checkins/batch-2.md:4737: trailing whitespace.
++   374	
.oracle/checkins/batch-2.md:4739: trailing whitespace.
++   388	
.oracle/checkins/batch-2.md:4741: trailing whitespace.
++   423	
.oracle/checkins/batch-2.md:4743: trailing whitespace.
++   436	
.oracle/checkins/batch-2.md:4745: trailing whitespace.
++   462	
.oracle/checkins/batch-2.md:4747: trailing whitespace.
++   477	
.oracle/checkins/batch-2.md:4749: trailing whitespace.
++   479	
.oracle/checkins/batch-2.md:4751: trailing whitespace.
++   480	
.oracle/checkins/batch-2.md:4753: trailing whitespace.
++   486	
.oracle/checkins/batch-2.md:4755: trailing whitespace.
++   487	
.oracle/checkins/batch-2.md:4757: trailing whitespace.
++   491	
.oracle/checkins/batch-2.md:4759: trailing whitespace.
++   492	
.oracle/checkins/batch-2.md:4761: trailing whitespace.
++   507	
.oracle/checkins/batch-2.md:4763: trailing whitespace.
++   508	
.oracle/checkins/batch-2.md:4765: trailing whitespace.
++   511	
.oracle/checkins/batch-2.md:4767: trailing whitespace.
++   531	
.oracle/checkins/batch-2.md:4769: trailing whitespace.
++   532	
.oracle/checkins/batch-2.md:4771: trailing whitespace.
++   539	
.oracle/checkins/batch-2.md:4773: trailing whitespace.
++   584	
.oracle/checkins/batch-2.md:4775: trailing whitespace.
++   601	
.oracle/checkins/batch-2.md:4777: trailing whitespace.
++   613	
.oracle/checkins/batch-2.md:4779: trailing whitespace.
++   614	
.oracle/checkins/batch-2.md:4781: trailing whitespace.
++   627	
.oracle/checkins/batch-2.md:4783: trailing whitespace.
++   628	
.oracle/checkins/batch-2.md:4785: trailing whitespace.
++   632	
.oracle/checkins/batch-2.md:4787: trailing whitespace.
++   633	
.oracle/checkins/batch-2.md:4789: trailing whitespace.
++   647	
.oracle/checkins/batch-2.md:4791: trailing whitespace.
++   654	
.oracle/checkins/batch-2.md:4793: trailing whitespace.
++   655	
.oracle/checkins/batch-2.md:4795: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4797: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4799: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4801: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4803: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4805: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4807: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4809: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4811: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4813: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4815: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4817: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4819: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4821: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4823: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4825: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4827: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4829: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4831: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4833: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4835: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4837: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4839: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4841: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4843: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4845: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4847: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4849: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4851: trailing whitespace.
++   174	
.oracle/checkins/batch-2.md:4853: trailing whitespace.
++   177	
.oracle/checkins/batch-2.md:4855: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:4857: trailing whitespace.
++   185	
.oracle/checkins/batch-2.md:4859: trailing whitespace.
++   193	
.oracle/checkins/batch-2.md:4861: trailing whitespace.
++   196	
.oracle/checkins/batch-2.md:4863: trailing whitespace.
++   140	
.oracle/checkins/batch-2.md:4865: trailing whitespace.
++   162	
.oracle/checkins/batch-2.md:4867: trailing whitespace.
++   171	
.oracle/checkins/batch-2.md:4869: trailing whitespace.
++   201	
.oracle/checkins/batch-2.md:4871: trailing whitespace.
++   202	
.oracle/checkins/batch-2.md:4873: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:4875: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:4877: trailing whitespace.
++    77	
.oracle/checkins/batch-2.md:4879: trailing whitespace.
++    78	
.oracle/checkins/batch-2.md:4881: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:4883: trailing whitespace.
++    98	
.oracle/checkins/batch-2.md:4885: trailing whitespace.
++   104	
.oracle/checkins/batch-2.md:4887: trailing whitespace.
++   105	
.oracle/checkins/batch-2.md:4889: trailing whitespace.
++   113	
.oracle/checkins/batch-2.md:4891: trailing whitespace.
++   114	
.oracle/checkins/batch-2.md:4893: trailing whitespace.
++   127	
.oracle/checkins/batch-2.md:4895: trailing whitespace.
++   128	
.oracle/checkins/batch-2.md:4897: trailing whitespace.
++   142	
.oracle/checkins/batch-2.md:4899: trailing whitespace.
++   143	
.oracle/checkins/batch-2.md:4901: trailing whitespace.
++   161	
.oracle/checkins/batch-2.md:4903: trailing whitespace.
++   173	
.oracle/checkins/batch-2.md:4905: trailing whitespace.
++   176	
.oracle/checkins/batch-2.md:4907: trailing whitespace.
++   177	
.oracle/checkins/batch-2.md:4909: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:4911: trailing whitespace.
++   182	
.oracle/checkins/batch-2.md:4919: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4929: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4937: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4939: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4941: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4943: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4945: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4951: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4955: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:4957: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:4959: trailing whitespace.
++     8	
.oracle/checkins/batch-2.md:4961: trailing whitespace.
++    10	
.oracle/checkins/batch-2.md:4963: trailing whitespace.
++    21	
.oracle/checkins/batch-2.md:4965: trailing whitespace.
++    24	
.oracle/checkins/batch-2.md:4967: trailing whitespace.
++    25	
.oracle/checkins/batch-2.md:4969: trailing whitespace.
++    28	
.oracle/checkins/batch-2.md:4971: trailing whitespace.
++    29	
.oracle/checkins/batch-2.md:4973: trailing whitespace.
++    55	
.oracle/checkins/batch-2.md:4975: trailing whitespace.
++    56	
.oracle/checkins/batch-2.md:4977: trailing whitespace.
++    61	
.oracle/checkins/batch-2.md:4979: trailing whitespace.
++    62	
.oracle/checkins/batch-2.md:4981: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:4983: trailing whitespace.
++    72	
.oracle/checkins/batch-2.md:4985: trailing whitespace.
++    79	
.oracle/checkins/batch-2.md:4987: trailing whitespace.
++    80	
.oracle/checkins/batch-2.md:4989: trailing whitespace.
++    94	
.oracle/checkins/batch-2.md:4991: trailing whitespace.
++    95	
.oracle/checkins/batch-2.md:4993: trailing whitespace.
++   102	
.oracle/checkins/batch-2.md:4995: trailing whitespace.
++   104	
.oracle/checkins/batch-2.md:4997: trailing whitespace.
++   111	
.oracle/checkins/batch-2.md:4999: trailing whitespace.
++   113	
.oracle/checkins/batch-2.md:5001: trailing whitespace.
++   119	
.oracle/checkins/batch-2.md:5003: trailing whitespace.
++   128	
.oracle/checkins/batch-2.md:5005: trailing whitespace.
++   140	
.oracle/checkins/batch-2.md:5007: trailing whitespace.
++   162	
.oracle/checkins/batch-2.md:5009: trailing whitespace.
++   171	
.oracle/checkins/batch-2.md:5011: trailing whitespace.
++   201	
.oracle/checkins/batch-2.md:5013: trailing whitespace.
++   202	
.oracle/checkins/batch-2.md:5015: trailing whitespace.
++   214	
.oracle/checkins/batch-2.md:5017: trailing whitespace.
++   215	
.oracle/checkins/batch-2.md:5019: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:5021: trailing whitespace.
++   245	
.oracle/checkins/batch-2.md:5023: trailing whitespace.
++   248	
.oracle/checkins/batch-2.md:5025: trailing whitespace.
++   266	
.oracle/checkins/batch-2.md:5027: trailing whitespace.
++   313	
.oracle/checkins/batch-2.md:5029: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:5031: trailing whitespace.
++   335	
.oracle/checkins/batch-2.md:5033: trailing whitespace.
++   339	
.oracle/checkins/batch-2.md:5035: trailing whitespace.
++   360	
.oracle/checkins/batch-2.md:5037: trailing whitespace.
++   361	
.oracle/checkins/batch-2.md:5039: trailing whitespace.
++   385	
.oracle/checkins/batch-2.md:5041: trailing whitespace.
++   386	
.oracle/checkins/batch-2.md:5043: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:5045: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:5047: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:5049: trailing whitespace.
++    14	
.oracle/checkins/batch-2.md:5051: trailing whitespace.
++    21	
.oracle/checkins/batch-2.md:5053: trailing whitespace.
++    23	
.oracle/checkins/batch-2.md:5055: trailing whitespace.
++    27	
.oracle/checkins/batch-2.md:5057: trailing whitespace.
++    28	
.oracle/checkins/batch-2.md:5059: trailing whitespace.
++    30	
.oracle/checkins/batch-2.md:5061: trailing whitespace.
++    31	
.oracle/checkins/batch-2.md:5063: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:5065: trailing whitespace.
++    36	
.oracle/checkins/batch-2.md:5067: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:5069: trailing whitespace.
++    41	
.oracle/checkins/batch-2.md:5071: trailing whitespace.
++    62	
.oracle/checkins/batch-2.md:5073: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:5075: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:5077: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:5079: trailing whitespace.
++    77	
.oracle/checkins/batch-2.md:5081: trailing whitespace.
++    78	
.oracle/checkins/batch-2.md:5083: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:5085: trailing whitespace.
++    98	
.oracle/checkins/batch-2.md:5087: trailing whitespace.
++   104	
.oracle/checkins/batch-2.md:5089: trailing whitespace.
++   105	
.oracle/checkins/batch-2.md:5091: trailing whitespace.
++   113	
.oracle/checkins/batch-2.md:5093: trailing whitespace.
++   114	
.oracle/checkins/batch-2.md:5095: trailing whitespace.
++   127	
.oracle/checkins/batch-2.md:5097: trailing whitespace.
++   128	
.oracle/checkins/batch-2.md:5099: trailing whitespace.
++   142	
.oracle/checkins/batch-2.md:5101: trailing whitespace.
++   143	
.oracle/checkins/batch-2.md:5103: trailing whitespace.
++   161	
.oracle/checkins/batch-2.md:5105: trailing whitespace.
++   173	
.oracle/checkins/batch-2.md:5107: trailing whitespace.
++   176	
.oracle/checkins/batch-2.md:5109: trailing whitespace.
++   177	
.oracle/checkins/batch-2.md:5111: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:5113: trailing whitespace.
++   182	
.oracle/checkins/batch-2.md:5115: trailing whitespace.
++   204	
.oracle/checkins/batch-2.md:5117: trailing whitespace.
++   205	
.oracle/checkins/batch-2.md:5119: trailing whitespace.
++   208	
.oracle/checkins/batch-2.md:5121: trailing whitespace.
++   319	
.oracle/checkins/batch-2.md:5123: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:5125: trailing whitespace.
++   326	
.oracle/checkins/batch-2.md:5127: trailing whitespace.
++   334	
.oracle/checkins/batch-2.md:5129: trailing whitespace.
++   338	
.oracle/checkins/batch-2.md:5131: trailing whitespace.
++   341	
.oracle/checkins/batch-2.md:5133: trailing whitespace.
++   344	
.oracle/checkins/batch-2.md:5135: trailing whitespace.
++   345	
.oracle/checkins/batch-2.md:5137: trailing whitespace.
++   348	
.oracle/checkins/batch-2.md:5139: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:5141: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:5143: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:5145: trailing whitespace.
++    15	
.oracle/checkins/batch-2.md:5147: trailing whitespace.
++    31	
.oracle/checkins/batch-2.md:5149: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:5151: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:5153: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:5155: trailing whitespace.
++    43	
.oracle/checkins/batch-2.md:5157: trailing whitespace.
++    45	
.oracle/checkins/batch-2.md:5159: trailing whitespace.
++    53	
.oracle/checkins/batch-2.md:5161: trailing whitespace.
++    58	
.oracle/checkins/batch-2.md:5163: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:5165: trailing whitespace.
++    65	
.oracle/checkins/batch-2.md:5167: trailing whitespace.
++    66	
.oracle/checkins/batch-2.md:5169: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:5171: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:5173: trailing whitespace.
++    83	
.oracle/checkins/batch-2.md:5175: trailing whitespace.
++    84	
.oracle/checkins/batch-2.md:5177: trailing whitespace.
++    88	
.oracle/checkins/batch-2.md:5179: trailing whitespace.
++    89	
.oracle/checkins/batch-2.md:5181: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:5183: trailing whitespace.
++    98	
.oracle/checkins/batch-2.md:5185: trailing whitespace.
++   110	
.oracle/checkins/batch-2.md:5187: trailing whitespace.
++   111	
.oracle/checkins/batch-2.md:5189: trailing whitespace.
++   116	
.oracle/checkins/batch-2.md:5191: trailing whitespace.
++   117	
.oracle/checkins/batch-2.md:5193: trailing whitespace.
++   135	
.oracle/checkins/batch-2.md:5195: trailing whitespace.
++   136	
.oracle/checkins/batch-2.md:5197: trailing whitespace.
++   149	
.oracle/checkins/batch-2.md:5199: trailing whitespace.
++   150	
.oracle/checkins/batch-2.md:5201: trailing whitespace.
++   163	
.oracle/checkins/batch-2.md:5203: trailing whitespace.
++   164	
.oracle/checkins/batch-2.md:5205: trailing whitespace.
++   173	
.oracle/checkins/batch-2.md:5207: trailing whitespace.
++   174	
.oracle/checkins/batch-2.md:5209: trailing whitespace.
++   180	
.oracle/checkins/batch-2.md:5211: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:5213: trailing whitespace.
++   191	
.oracle/checkins/batch-2.md:5215: trailing whitespace.
++   192	
.oracle/checkins/batch-2.md:5217: trailing whitespace.
++   198	
.oracle/checkins/batch-2.md:5219: trailing whitespace.
++   199	
.oracle/checkins/batch-2.md:5221: trailing whitespace.
++   206	
.oracle/checkins/batch-2.md:5223: trailing whitespace.
++   207	
.oracle/checkins/batch-2.md:5225: trailing whitespace.
++   223	
.oracle/checkins/batch-2.md:5227: trailing whitespace.
++   224	
.oracle/checkins/batch-2.md:5229: trailing whitespace.
++   228	
.oracle/checkins/batch-2.md:5231: trailing whitespace.
++   229	
.oracle/checkins/batch-2.md:5233: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:5235: trailing whitespace.
++   233	
.oracle/checkins/batch-2.md:5237: trailing whitespace.
++   237	
.oracle/checkins/batch-2.md:5239: trailing whitespace.
++   238	
.oracle/checkins/batch-2.md:5241: trailing whitespace.
++   242	
.oracle/checkins/batch-2.md:5243: trailing whitespace.
++   243	
.oracle/checkins/batch-2.md:5245: trailing whitespace.
++   250	
.oracle/checkins/batch-2.md:5247: trailing whitespace.
++   251	
.oracle/checkins/batch-2.md:5249: trailing whitespace.
++   254	
.oracle/checkins/batch-2.md:5251: trailing whitespace.
++   271	
.oracle/checkins/batch-2.md:5253: trailing whitespace.
++   275	
.oracle/checkins/batch-2.md:5255: trailing whitespace.
++   278	
.oracle/checkins/batch-2.md:5257: trailing whitespace.
++   288	
.oracle/checkins/batch-2.md:5259: trailing whitespace.
++   307	
.oracle/checkins/batch-2.md:5261: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:5263: trailing whitespace.
++   324	
.oracle/checkins/batch-2.md:5265: trailing whitespace.
++   336	
.oracle/checkins/batch-2.md:5267: trailing whitespace.
++   347	
.oracle/checkins/batch-2.md:5269: trailing whitespace.
++   352	
.oracle/checkins/batch-2.md:5271: trailing whitespace.
++   374	
.oracle/checkins/batch-2.md:5273: trailing whitespace.
++   388	
.oracle/checkins/batch-2.md:5275: trailing whitespace.
++   423	
.oracle/checkins/batch-2.md:5277: trailing whitespace.
++   436	
.oracle/checkins/batch-2.md:5279: trailing whitespace.
++   462	
.oracle/checkins/batch-2.md:5281: trailing whitespace.
++   477	
.oracle/checkins/batch-2.md:5283: trailing whitespace.
++   479	
.oracle/checkins/batch-2.md:5285: trailing whitespace.
++   480	
.oracle/checkins/batch-2.md:5287: trailing whitespace.
++   486	
.oracle/checkins/batch-2.md:5289: trailing whitespace.
++   487	
.oracle/checkins/batch-2.md:5291: trailing whitespace.
++   491	
.oracle/checkins/batch-2.md:5293: trailing whitespace.
++   492	
.oracle/checkins/batch-2.md:5295: trailing whitespace.
++   507	
.oracle/checkins/batch-2.md:5297: trailing whitespace.
++   508	
.oracle/checkins/batch-2.md:5299: trailing whitespace.
++   511	
.oracle/checkins/batch-2.md:5301: trailing whitespace.
++   531	
.oracle/checkins/batch-2.md:5303: trailing whitespace.
++   532	
.oracle/checkins/batch-2.md:5305: trailing whitespace.
++   539	
.oracle/checkins/batch-2.md:5307: trailing whitespace.
++   584	
.oracle/checkins/batch-2.md:5309: trailing whitespace.
++   601	
.oracle/checkins/batch-2.md:5311: trailing whitespace.
++   613	
.oracle/checkins/batch-2.md:5313: trailing whitespace.
++   614	
.oracle/checkins/batch-2.md:5315: trailing whitespace.
++   627	
.oracle/checkins/batch-2.md:5317: trailing whitespace.
++   628	
.oracle/checkins/batch-2.md:5319: trailing whitespace.
++   632	
.oracle/checkins/batch-2.md:5321: trailing whitespace.
++   633	
.oracle/checkins/batch-2.md:5323: trailing whitespace.
++   647	
.oracle/checkins/batch-2.md:5325: trailing whitespace.
++   654	
.oracle/checkins/batch-2.md:5327: trailing whitespace.
++   655	
.oracle/checkins/batch-2.md:5329: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:5331: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:5333: trailing whitespace.
++     9	
.oracle/checkins/batch-2.md:5335: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:5337: trailing whitespace.
++    15	
.oracle/checkins/batch-2.md:5339: trailing whitespace.
++    20	
.oracle/checkins/batch-2.md:5341: trailing whitespace.
++    21	
.oracle/checkins/batch-2.md:5343: trailing whitespace.
++    24	
.oracle/checkins/batch-2.md:5345: trailing whitespace.
++    25	
.oracle/checkins/batch-2.md:5347: trailing whitespace.
++    30	
.oracle/checkins/batch-2.md:5349: trailing whitespace.
++    38	
.oracle/checkins/batch-2.md:5351: trailing whitespace.
++    43	
.oracle/checkins/batch-2.md:5353: trailing whitespace.
++    44	
.oracle/checkins/batch-2.md:5355: trailing whitespace.
++    49	
.oracle/checkins/batch-2.md:5357: trailing whitespace.
++    50	
.oracle/checkins/batch-2.md:5359: trailing whitespace.
++    54	
.oracle/checkins/batch-2.md:5361: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:5363: trailing whitespace.
++    11	
.oracle/checkins/batch-2.md:5365: trailing whitespace.
++    16	
.oracle/checkins/batch-2.md:5367: trailing whitespace.
++    18	
.oracle/checkins/batch-2.md:5369: trailing whitespace.
++    22	
.oracle/checkins/batch-2.md:5371: trailing whitespace.
++    23	
.oracle/checkins/batch-2.md:5373: trailing whitespace.
++    36	
.oracle/checkins/batch-2.md:5375: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:5377: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:5379: trailing whitespace.
++    56	
.oracle/checkins/batch-2.md:5381: trailing whitespace.
++    57	
.oracle/checkins/batch-2.md:5383: trailing whitespace.
++    60	
.oracle/checkins/batch-2.md:5385: trailing whitespace.
++    61	
.oracle/checkins/batch-2.md:5387: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:5389: trailing whitespace.
++    64	
.oracle/checkins/batch-2.md:5391: trailing whitespace.
++    68	
.oracle/checkins/batch-2.md:5393: trailing whitespace.
++    69	
.oracle/checkins/batch-2.md:5395: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:5397: trailing whitespace.
++    72	
.oracle/checkins/batch-2.md:5399: trailing whitespace.
++    76	
.oracle/checkins/batch-2.md:5401: trailing whitespace.
++    77	
.oracle/checkins/batch-2.md:5403: trailing whitespace.
++    79	
.oracle/checkins/batch-2.md:5405: trailing whitespace.
++    80	
.oracle/checkins/batch-2.md:5407: trailing whitespace.
++    84	
.oracle/checkins/batch-2.md:5409: trailing whitespace.
++    85	
.oracle/checkins/batch-2.md:5411: trailing whitespace.
++   100	
.oracle/checkins/batch-2.md:5413: trailing whitespace.
++   106	
.oracle/checkins/batch-2.md:5415: trailing whitespace.
++   107	
.oracle/checkins/batch-2.md:5417: trailing whitespace.
++   153	
.oracle/checkins/batch-2.md:5419: trailing whitespace.
++   162	
.oracle/checkins/batch-2.md:5421: trailing whitespace.
++   213	
.oracle/checkins/batch-2.md:5423: trailing whitespace.
++   219	
.oracle/checkins/batch-2.md:5425: trailing whitespace.
++   220	
.oracle/checkins/batch-2.md:5427: trailing whitespace.
++   222	
.oracle/checkins/batch-2.md:5429: trailing whitespace.
++   223	
.oracle/checkins/batch-2.md:5431: trailing whitespace.
++   229	
.oracle/checkins/batch-2.md:5433: trailing whitespace.
++   230	
.oracle/checkins/batch-2.md:5435: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:5437: trailing whitespace.
++   233	
.oracle/checkins/batch-2.md:5439: trailing whitespace.
++   242	
.oracle/checkins/batch-2.md:5441: trailing whitespace.
++   243	
.oracle/checkins/batch-2.md:5443: trailing whitespace.
++   245	
.oracle/checkins/batch-2.md:5445: trailing whitespace.
++   246	
.oracle/checkins/batch-2.md:5447: trailing whitespace.
++   249	
.oracle/checkins/batch-2.md:5449: trailing whitespace.
++   256	
.oracle/checkins/batch-2.md:5451: trailing whitespace.
++   259	
.oracle/checkins/batch-2.md:5453: trailing whitespace.
++   264	
.oracle/checkins/batch-2.md:5455: trailing whitespace.
++   265	
.oracle/checkins/batch-2.md:5457: trailing whitespace.
++   269	
.oracle/checkins/batch-2.md:5459: trailing whitespace.
++   270	
.oracle/checkins/batch-2.md:5461: trailing whitespace.
++   274	
.oracle/checkins/batch-2.md:5463: trailing whitespace.
++   278	
.oracle/checkins/batch-2.md:5465: trailing whitespace.
++   279	
.oracle/checkins/batch-2.md:5467: trailing whitespace.
++   285	
.oracle/checkins/batch-2.md:5469: trailing whitespace.
++   292	
.oracle/checkins/batch-2.md:5471: trailing whitespace.
++   293	
.oracle/checkins/batch-2.md:5473: trailing whitespace.
++   297	
.oracle/checkins/batch-2.md:5475: trailing whitespace.
++   303	
.oracle/checkins/batch-2.md:5477: trailing whitespace.
++   309	
.oracle/checkins/batch-2.md:5479: trailing whitespace.
++   310	
.oracle/checkins/batch-2.md:5481: trailing whitespace.
++   316	
.oracle/checkins/batch-2.md:5483: trailing whitespace.
++   329	
.oracle/checkins/batch-2.md:5485: trailing whitespace.
++   330	
.oracle/checkins/batch-2.md:5487: trailing whitespace.
++   335	
.oracle/checkins/batch-2.md:5489: trailing whitespace.
++   341	
.oracle/checkins/batch-2.md:5491: trailing whitespace.
++   342	
.oracle/checkins/batch-2.md:5493: trailing whitespace.
++   344	
.oracle/checkins/batch-2.md:5495: trailing whitespace.
++   345	
.oracle/checkins/batch-2.md:5497: trailing whitespace.
++   352	
.oracle/checkins/batch-2.md:5499: trailing whitespace.
++   353	
.oracle/checkins/batch-2.md:5501: trailing whitespace.
++   356	
.oracle/checkins/batch-2.md:5503: trailing whitespace.
++   357	
.oracle/checkins/batch-2.md:5505: trailing whitespace.
++   380	
.oracle/checkins/batch-2.md:5507: trailing whitespace.
++   381	
.oracle/checkins/batch-2.md:5509: trailing whitespace.
++   391	
.oracle/checkins/batch-2.md:5511: trailing whitespace.
++   392	
.oracle/checkins/batch-2.md:5513: trailing whitespace.
++   400	
.oracle/checkins/batch-2.md:5515: trailing whitespace.
++   401	
.oracle/checkins/batch-2.md:5517: trailing whitespace.
++   407	
.oracle/checkins/batch-2.md:5519: trailing whitespace.
++   408	
.oracle/checkins/batch-2.md:5521: trailing whitespace.
++   417	
.oracle/checkins/batch-2.md:5523: trailing whitespace.
++   418	
.oracle/checkins/batch-2.md:5525: trailing whitespace.
++   421	
.oracle/checkins/batch-2.md:5527: trailing whitespace.
++   428	
.oracle/checkins/batch-2.md:5529: trailing whitespace.
++   432	
.oracle/checkins/batch-2.md:5531: trailing whitespace.
++   434	
.oracle/checkins/batch-2.md:5533: trailing whitespace.
++   440	
.oracle/checkins/batch-2.md:5535: trailing whitespace.
++   441	
.oracle/checkins/batch-2.md:5537: trailing whitespace.
++   445	
.oracle/checkins/batch-2.md:5539: trailing whitespace.
++   451	
.oracle/checkins/batch-2.md:5541: trailing whitespace.
++   452	
.oracle/checkins/batch-2.md:5543: trailing whitespace.
++   455	
.oracle/checkins/batch-2.md:5545: trailing whitespace.
++   463	
.oracle/checkins/batch-2.md:5547: trailing whitespace.
++   468	
.oracle/checkins/batch-2.md:5549: trailing whitespace.
++   471	
.oracle/checkins/batch-2.md:5551: trailing whitespace.
++   472	
.oracle/checkins/batch-2.md:5553: trailing whitespace.
++   475	
.oracle/checkins/batch-2.md:5555: trailing whitespace.
++   481	
.oracle/checkins/batch-2.md:5557: trailing whitespace.
++   488	
.oracle/checkins/batch-2.md:5559: trailing whitespace.
++   494	
.oracle/checkins/batch-2.md:5561: trailing whitespace.
++   495	
.oracle/checkins/batch-2.md:5563: trailing whitespace.
++   498	
.oracle/checkins/batch-2.md:5565: trailing whitespace.
++   506	
.oracle/checkins/batch-2.md:5567: trailing whitespace.
++   517	
.oracle/checkins/batch-2.md:5569: trailing whitespace.
++   532	
.oracle/checkins/batch-2.md:5571: trailing whitespace.
++   533	
.oracle/checkins/batch-2.md:5573: trailing whitespace.
++   536	
.oracle/checkins/batch-2.md:5575: trailing whitespace.
++   543	
.oracle/checkins/batch-2.md:5577: trailing whitespace.
++   547	
.oracle/checkins/batch-2.md:5579: trailing whitespace.
++   554	
.oracle/checkins/batch-2.md:5581: trailing whitespace.
++   557	
.oracle/checkins/batch-2.md:5583: trailing whitespace.
++   558	
.oracle/checkins/batch-2.md:5585: trailing whitespace.
++   562	
.oracle/checkins/batch-2.md:5587: trailing whitespace.
++   565	
.oracle/checkins/batch-2.md:5589: trailing whitespace.
++   576	
.oracle/checkins/batch-2.md:5591: trailing whitespace.
++   584	
.oracle/checkins/batch-2.md:5593: trailing whitespace.
++   587	
.oracle/checkins/batch-2.md:5595: trailing whitespace.
++   588	
.oracle/checkins/batch-2.md:5597: trailing whitespace.
++   592	
.oracle/checkins/batch-2.md:5599: trailing whitespace.
++   595	
.oracle/checkins/batch-2.md:5601: trailing whitespace.
++   606	
.oracle/checkins/batch-2.md:5603: trailing whitespace.
++   615	
.oracle/checkins/batch-2.md:5605: trailing whitespace.
++   619	
.oracle/checkins/batch-2.md:5607: trailing whitespace.
++   620	
.oracle/checkins/batch-2.md:5609: trailing whitespace.
++   624	
.oracle/checkins/batch-2.md:5611: trailing whitespace.
++   629	
.oracle/checkins/batch-2.md:5613: trailing whitespace.
++   630	
.oracle/checkins/batch-2.md:5615: trailing whitespace.
++   633	
.oracle/checkins/batch-2.md:5617: trailing whitespace.
++   634	
.oracle/checkins/batch-2.md:5619: trailing whitespace.
++   655	
.oracle/checkins/batch-2.md:5621: trailing whitespace.
++   656	
.oracle/checkins/batch-2.md:5623: trailing whitespace.
++   661	
.oracle/checkins/batch-2.md:5625: trailing whitespace.
++   663	
.oracle/checkins/batch-2.md:5627: trailing whitespace.
++   672	
.oracle/checkins/batch-2.md:5629: trailing whitespace.
++   676	
.oracle/checkins/batch-2.md:5631: trailing whitespace.
++   679	
.oracle/checkins/batch-2.md:5633: trailing whitespace.
++   682	
.oracle/checkins/batch-2.md:5635: trailing whitespace.
++   694	
.oracle/checkins/batch-2.md:5637: trailing whitespace.
++   706	
.oracle/checkins/batch-2.md:5639: trailing whitespace.
++   707	
.oracle/checkins/batch-2.md:5641: trailing whitespace.
++   711	
.oracle/checkins/batch-2.md:5643: trailing whitespace.
++   714	
.oracle/checkins/batch-2.md:5645: trailing whitespace.
++   720	
.oracle/checkins/batch-2.md:5647: trailing whitespace.
++   721	
.oracle/checkins/batch-2.md:5649: trailing whitespace.
++   724	
.oracle/checkins/batch-2.md:5651: trailing whitespace.
++   731	
.oracle/checkins/batch-2.md:5653: trailing whitespace.
++   733	
.oracle/checkins/batch-2.md:5655: trailing whitespace.
++   738	
.oracle/checkins/batch-2.md:5657: trailing whitespace.
++   744	
.oracle/checkins/batch-2.md:5659: trailing whitespace.
++   745	
.oracle/checkins/batch-2.md:5661: trailing whitespace.
++   749	
.oracle/checkins/batch-2.md:5663: trailing whitespace.
++   752	
.oracle/checkins/batch-2.md:5665: trailing whitespace.
++   758	
.oracle/checkins/batch-2.md:5667: trailing whitespace.
++   760	
.oracle/checkins/batch-2.md:5669: trailing whitespace.
++   762	
.oracle/checkins/batch-2.md:5671: trailing whitespace.
++   763	
.oracle/checkins/batch-2.md:5673: trailing whitespace.
++   767	
.oracle/checkins/batch-2.md:5675: trailing whitespace.
++   772	
.oracle/checkins/batch-2.md:5677: trailing whitespace.
++   777	
.oracle/checkins/batch-2.md:5679: trailing whitespace.
++   782	
.oracle/checkins/batch-2.md:5681: trailing whitespace.
++   787	
.oracle/checkins/batch-2.md:5683: trailing whitespace.
++   792	
.oracle/checkins/batch-2.md:5685: trailing whitespace.
++   793	
.oracle/checkins/batch-2.md:5687: trailing whitespace.
++   797	
.oracle/checkins/batch-2.md:5689: trailing whitespace.
++   804	
.oracle/checkins/batch-2.md:5691: trailing whitespace.
++   811	
.oracle/checkins/batch-2.md:5693: trailing whitespace.
++   818	
.oracle/checkins/batch-2.md:5695: trailing whitespace.
++   819	
.oracle/checkins/batch-2.md:5697: trailing whitespace.
++   823	
.oracle/checkins/batch-2.md:5699: trailing whitespace.
++   829	
.oracle/checkins/batch-2.md:5701: trailing whitespace.
++   834	
.oracle/checkins/batch-2.md:5703: trailing whitespace.
++   839	
.oracle/checkins/batch-2.md:5705: trailing whitespace.
++   840	
.oracle/checkins/batch-2.md:5707: trailing whitespace.
++   844	
.oracle/checkins/batch-2.md:5709: trailing whitespace.
++   845	
.oracle/checkins/batch-2.md:5711: trailing whitespace.
++   849	
.oracle/checkins/batch-2.md:5713: trailing whitespace.
++   861	
.oracle/checkins/batch-2.md:5715: trailing whitespace.
++   867	
.oracle/checkins/batch-2.md:5717: trailing whitespace.
++   881	
.oracle/checkins/batch-2.md:5719: trailing whitespace.
++   882	
.oracle/checkins/batch-2.md:5721: trailing whitespace.
++   886	
.oracle/checkins/batch-2.md:5723: trailing whitespace.
++   932	
.oracle/checkins/batch-2.md:5725: trailing whitespace.
++   948	
.oracle/checkins/batch-2.md:5727: trailing whitespace.
++   949	
.oracle/checkins/batch-2.md:5729: trailing whitespace.
++   953	
.oracle/checkins/batch-2.md:5731: trailing whitespace.
++   973	
.oracle/checkins/batch-2.md:5733: trailing whitespace.
++   985	
.oracle/checkins/batch-2.md:5735: trailing whitespace.
++   990	
.oracle/checkins/batch-2.md:5737: trailing whitespace.
++   995	
.oracle/checkins/batch-2.md:5739: trailing whitespace.
++  1000	
.oracle/checkins/batch-2.md:5741: trailing whitespace.
++  1004	
.oracle/checkins/batch-2.md:5743: trailing whitespace.
++  1005	
.oracle/checkins/batch-2.md:5745: trailing whitespace.
++  1009	
.oracle/checkins/batch-2.md:5747: trailing whitespace.
++  1010	
.oracle/checkins/batch-2.md:5749: trailing whitespace.
++  1015	
.oracle/checkins/batch-2.md:5751: trailing whitespace.
++  1028	
.oracle/checkins/batch-2.md:5753: trailing whitespace.
++  1029	
.oracle/checkins/batch-2.md:5755: trailing whitespace.
++  1042	
.oracle/checkins/batch-2.md:5757: trailing whitespace.
++  1043	
.oracle/checkins/batch-2.md:5759: trailing whitespace.
++  1051	
.oracle/checkins/batch-2.md:5761: trailing whitespace.
++  1052	
.oracle/checkins/batch-2.md:5763: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:5765: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:5767: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:5769: trailing whitespace.
++    15	
.oracle/checkins/batch-2.md:5771: trailing whitespace.
++    31	
.oracle/checkins/batch-2.md:5773: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:5775: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:5777: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:5779: trailing whitespace.
++    43	
.oracle/checkins/batch-2.md:5781: trailing whitespace.
++    45	
.oracle/checkins/batch-2.md:5783: trailing whitespace.
++    53	
.oracle/checkins/batch-2.md:5785: trailing whitespace.
++    58	
.oracle/checkins/batch-2.md:5787: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:5789: trailing whitespace.
++    65	
.oracle/checkins/batch-2.md:5791: trailing whitespace.
++    66	
.oracle/checkins/batch-2.md:5793: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:5795: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:5797: trailing whitespace.
++    83	
.oracle/checkins/batch-2.md:5799: trailing whitespace.
++    84	
.oracle/checkins/batch-2.md:5801: trailing whitespace.
++    88	
.oracle/checkins/batch-2.md:5803: trailing whitespace.
++    89	
.oracle/checkins/batch-2.md:5805: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:5807: trailing whitespace.
++    98	
.oracle/checkins/batch-2.md:5809: trailing whitespace.
++   110	
.oracle/checkins/batch-2.md:5811: trailing whitespace.
++   111	
.oracle/checkins/batch-2.md:5813: trailing whitespace.
++   116	
.oracle/checkins/batch-2.md:5815: trailing whitespace.
++   117	
.oracle/checkins/batch-2.md:5817: trailing whitespace.
++   135	
.oracle/checkins/batch-2.md:5819: trailing whitespace.
++   136	
.oracle/checkins/batch-2.md:5821: trailing whitespace.
++   149	
.oracle/checkins/batch-2.md:5823: trailing whitespace.
++   150	
.oracle/checkins/batch-2.md:5825: trailing whitespace.
++   163	
.oracle/checkins/batch-2.md:5827: trailing whitespace.
++   164	
.oracle/checkins/batch-2.md:5829: trailing whitespace.
++   173	
.oracle/checkins/batch-2.md:5831: trailing whitespace.
++   174	
.oracle/checkins/batch-2.md:5833: trailing whitespace.
++   180	
.oracle/checkins/batch-2.md:5835: trailing whitespace.
++   181	
.oracle/checkins/batch-2.md:5837: trailing whitespace.
++   191	
.oracle/checkins/batch-2.md:5839: trailing whitespace.
++   192	
.oracle/checkins/batch-2.md:5841: trailing whitespace.
++   198	
.oracle/checkins/batch-2.md:5843: trailing whitespace.
++   199	
.oracle/checkins/batch-2.md:5845: trailing whitespace.
++   206	
.oracle/checkins/batch-2.md:5847: trailing whitespace.
++   207	
.oracle/checkins/batch-2.md:5849: trailing whitespace.
++   223	
.oracle/checkins/batch-2.md:5851: trailing whitespace.
++   224	
.oracle/checkins/batch-2.md:5853: trailing whitespace.
++   228	
.oracle/checkins/batch-2.md:5855: trailing whitespace.
++   229	
.oracle/checkins/batch-2.md:5857: trailing whitespace.
++   232	
.oracle/checkins/batch-2.md:5859: trailing whitespace.
++   233	
.oracle/checkins/batch-2.md:5861: trailing whitespace.
++   237	
.oracle/checkins/batch-2.md:5863: trailing whitespace.
++   238	
.oracle/checkins/batch-2.md:5865: trailing whitespace.
++   531	
.oracle/checkins/batch-2.md:5867: trailing whitespace.
++   532	
.oracle/checkins/batch-2.md:5869: trailing whitespace.
++   539	
.oracle/checkins/batch-2.md:5871: trailing whitespace.
++   584	
.oracle/checkins/batch-2.md:5873: trailing whitespace.
++   601	
.oracle/checkins/batch-2.md:5875: trailing whitespace.
++   613	
.oracle/checkins/batch-2.md:5877: trailing whitespace.
++   614	
.oracle/checkins/batch-2.md:5879: trailing whitespace.
++   627	
.oracle/checkins/batch-2.md:5881: trailing whitespace.
++   628	
.oracle/checkins/batch-2.md:5883: trailing whitespace.
++   632	
.oracle/checkins/batch-2.md:5885: trailing whitespace.
++   633	
.oracle/checkins/batch-2.md:5887: trailing whitespace.
++   647	
.oracle/checkins/batch-2.md:5889: trailing whitespace.
++   654	
.oracle/checkins/batch-2.md:5891: trailing whitespace.
++   655	
.oracle/checkins/batch-2.md:5893: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5895: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5897: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5899: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5901: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5903: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5905: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5907: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5909: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5911: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5913: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5915: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5917: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5919: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5921: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5923: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5925: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5927: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5929: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5931: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5933: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5935: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5937: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5939: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5941: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5943: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5945: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5947: trailing whitespace.
++   242	
.oracle/checkins/batch-2.md:5949: trailing whitespace.
++   243	
.oracle/checkins/batch-2.md:5951: trailing whitespace.
++   250	
.oracle/checkins/batch-2.md:5953: trailing whitespace.
++   251	
.oracle/checkins/batch-2.md:5955: trailing whitespace.
++   254	
.oracle/checkins/batch-2.md:5957: trailing whitespace.
++   271	
.oracle/checkins/batch-2.md:5959: trailing whitespace.
++   275	
.oracle/checkins/batch-2.md:5961: trailing whitespace.
++   278	
.oracle/checkins/batch-2.md:5963: trailing whitespace.
++   288	
.oracle/checkins/batch-2.md:5965: trailing whitespace.
++   307	
.oracle/checkins/batch-2.md:5967: trailing whitespace.
++   320	
.oracle/checkins/batch-2.md:5969: trailing whitespace.
++   324	
.oracle/checkins/batch-2.md:5971: trailing whitespace.
++   336	
.oracle/checkins/batch-2.md:5973: trailing whitespace.
++   347	
.oracle/checkins/batch-2.md:5975: trailing whitespace.
++   352	
.oracle/checkins/batch-2.md:5977: trailing whitespace.
++   374	
.oracle/checkins/batch-2.md:5979: trailing whitespace.
++   388	
.oracle/checkins/batch-2.md:5981: trailing whitespace.
++   423	
.oracle/checkins/batch-2.md:5983: trailing whitespace.
++   436	
.oracle/checkins/batch-2.md:5985: trailing whitespace.
++   462	
.oracle/checkins/batch-2.md:5987: trailing whitespace.
++   477	
.oracle/checkins/batch-2.md:5989: trailing whitespace.
++   479	
.oracle/checkins/batch-2.md:5991: trailing whitespace.
++   480	
.oracle/checkins/batch-2.md:5993: trailing whitespace.
++   486	
.oracle/checkins/batch-2.md:5995: trailing whitespace.
++   487	
.oracle/checkins/batch-2.md:5997: trailing whitespace.
++   491	
.oracle/checkins/batch-2.md:5999: trailing whitespace.
++   492	
.oracle/checkins/batch-2.md:6001: trailing whitespace.
++   507	
.oracle/checkins/batch-2.md:6003: trailing whitespace.
++   508	
.oracle/checkins/batch-2.md:6005: trailing whitespace.
++   511	
.oracle/checkins/batch-2.md:6013: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:6023: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:6027: trailing whitespace.
++   280	
.oracle/checkins/batch-2.md:6029: trailing whitespace.
++   283	
.oracle/checkins/batch-2.md:6031: trailing whitespace.
++   300	
.oracle/checkins/batch-2.md:6033: trailing whitespace.
++   311	
.oracle/checkins/batch-2.md:6035: trailing whitespace.
++   317	
.oracle/checkins/batch-2.md:6037: trailing whitespace.
++   326	
.oracle/checkins/batch-2.md:6039: trailing whitespace.
++   365	
.oracle/checkins/batch-2.md:6041: trailing whitespace.
++   370	
.oracle/checkins/batch-2.md:6043: trailing whitespace.
++   392	
.oracle/checkins/batch-2.md:6045: trailing whitespace.
++   404	
.oracle/checkins/batch-2.md:6047: trailing whitespace.
++   423	
.oracle/checkins/batch-2.md:6049: trailing whitespace.
++   451	
.oracle/checkins/batch-2.md:6051: trailing whitespace.
++   465	
.oracle/checkins/batch-2.md:6053: trailing whitespace.
++   469	
.oracle/checkins/batch-2.md:6055: trailing whitespace.
++   472	
.oracle/checkins/batch-2.md:6057: trailing whitespace.
++   481	
.oracle/checkins/batch-2.md:6059: trailing whitespace.
++   492	
.oracle/checkins/batch-2.md:6061: trailing whitespace.
++   496	
.oracle/checkins/batch-2.md:6063: trailing whitespace.
++   241	
.oracle/checkins/batch-2.md:6065: trailing whitespace.
++   252	
.oracle/checkins/batch-2.md:6067: trailing whitespace.
++   255	
.oracle/checkins/batch-2.md:6069: trailing whitespace.
++   264	
.oracle/checkins/batch-2.md:6071: trailing whitespace.
++   268	
.oracle/checkins/batch-2.md:6073: trailing whitespace.
++   275	
.oracle/checkins/batch-2.md:6075: trailing whitespace.
++   277	
.oracle/checkins/batch-2.md:6077: trailing whitespace.
++   280	
.oracle/checkins/batch-2.md:6079: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:6081: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:6083: trailing whitespace.
++    79	
.oracle/checkins/batch-2.md:6085: trailing whitespace.
++    80	
.oracle/checkins/batch-2.md:6087: trailing whitespace.
++    92	
.oracle/checkins/batch-2.md:6089: trailing whitespace.
++    97	
.oracle/checkins/batch-2.md:6091: trailing whitespace.
++    99	
.oracle/checkins/batch-2.md:6093: trailing whitespace.
++   100	
.oracle/checkins/batch-2.md:6095: trailing whitespace.
++   107	
.oracle/checkins/batch-2.md:6097: trailing whitespace.
++   108	
.oracle/checkins/batch-2.md:6708: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:6710: trailing whitespace.
++     7	
.oracle/checkins/batch-2.md:6712: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:6714: trailing whitespace.
++    15	
.oracle/checkins/batch-2.md:6716: trailing whitespace.
++    31	
.oracle/checkins/batch-2.md:6718: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:6720: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:6722: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:6724: trailing whitespace.
++    43	
.oracle/checkins/batch-2.md:6726: trailing whitespace.
++    45	
.oracle/checkins/batch-2.md:6728: trailing whitespace.
++    53	
.oracle/checkins/batch-2.md:6730: trailing whitespace.
++    58	
.oracle/checkins/batch-2.md:6732: trailing whitespace.
++    63	
.oracle/checkins/batch-2.md:6734: trailing whitespace.
++    65	
.oracle/checkins/batch-2.md:6736: trailing whitespace.
++    66	
.oracle/checkins/batch-2.md:6738: trailing whitespace.
++    70	
.oracle/checkins/batch-2.md:6740: trailing whitespace.
++    71	
.oracle/checkins/batch-2.md:6742: trailing whitespace.
++    83	
.oracle/checkins/batch-2.md:6744: trailing whitespace.
++    84	
.oracle/checkins/batch-2.md:7278: trailing whitespace.
+    80	
.oracle/checkins/batch-2.md:7290: trailing whitespace.
+    92	
.oracle/checkins/batch-2.md:7295: trailing whitespace.
+    97	
.oracle/checkins/batch-2.md:7297: trailing whitespace.
+    99	
.oracle/checkins/batch-2.md:7298: trailing whitespace.
+   100	
.oracle/checkins/batch-2.md:7305: trailing whitespace.
+   107	
.oracle/checkins/batch-2.md:7306: trailing whitespace.
+   108	
.oracle/checkins/batch-2.md:7319: trailing whitespace.
+   121	
.oracle/checkins/batch-2.md:7323: trailing whitespace.
+   125	
.oracle/checkins/batch-2.md:7327: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:7328: trailing whitespace.
+   130	
.oracle/checkins/batch-2.md:7338: trailing whitespace.
+   140	
.oracle/checkins/batch-2.md:7339: trailing whitespace.
+   141	
.oracle/checkins/batch-2.md:7346: trailing whitespace.
+   148	
.oracle/checkins/batch-2.md:7347: trailing whitespace.
+   149	
.oracle/checkins/batch-2.md:7352: trailing whitespace.
+   154	
.oracle/checkins/batch-2.md:7353: trailing whitespace.
+   155	
.oracle/checkins/batch-2.md:7356: trailing whitespace.
+   158	
.oracle/checkins/batch-2.md:7368: trailing whitespace.
+   170	
.oracle/checkins/batch-2.md:7369: trailing whitespace.
+   171	
.oracle/checkins/batch-2.md:7384: trailing whitespace.
+   275	
.oracle/checkins/batch-2.md:7386: trailing whitespace.
+   277	
.oracle/checkins/batch-2.md:7389: trailing whitespace.
+   280	
.oracle/checkins/batch-2.md:7392: trailing whitespace.
+   283	
.oracle/checkins/batch-2.md:7409: trailing whitespace.
+   300	
.oracle/checkins/batch-2.md:7420: trailing whitespace.
+   311	
.oracle/checkins/batch-2.md:7426: trailing whitespace.
+   317	
.oracle/checkins/batch-2.md:7435: trailing whitespace.
+   326	
.oracle/checkins/batch-2.md:7474: trailing whitespace.
+   365	
.oracle/checkins/batch-2.md:7479: trailing whitespace.
+   370	
.oracle/checkins/batch-2.md:7501: trailing whitespace.
+   392	
.oracle/checkins/batch-2.md:7513: trailing whitespace.
+   404	
.oracle/checkins/batch-2.md:7532: trailing whitespace.
+   423	
.oracle/checkins/batch-2.md:7560: trailing whitespace.
+   451	
.oracle/checkins/batch-2.md:7574: trailing whitespace.
+   465	
.oracle/checkins/batch-2.md:7578: trailing whitespace.
+   469	
.oracle/checkins/batch-2.md:7581: trailing whitespace.
+   472	
.oracle/checkins/batch-2.md:7590: trailing whitespace.
+   481	
.oracle/checkins/batch-2.md:7601: trailing whitespace.
+   492	
.oracle/checkins/batch-2.md:7605: trailing whitespace.
+   496	
.oracle/checkins/batch-2.md:7622: trailing whitespace.
+   513	
.oracle/checkins/batch-2.md:7624: trailing whitespace.
+   515	
.oracle/checkins/batch-2.md:7647: trailing whitespace.
+   538	
.oracle/checkins/batch-2.md:7659: trailing whitespace.
+   550	
.oracle/checkins/batch-2.md:7665: trailing whitespace.
+   556	
.oracle/checkins/batch-2.md:7677: trailing whitespace.
+   568	
.oracle/checkins/batch-2.md:7693: trailing whitespace.
+   584	
.oracle/checkins/batch-2.md:7705: trailing whitespace.
+   596	
.oracle/checkins/batch-2.md:7713: trailing whitespace.
+   604	
.oracle/checkins/batch-2.md:7729: trailing whitespace.
+   620	
.oracle/checkins/batch-2.md:7740: trailing whitespace.
+   631	
.oracle/checkins/batch-2.md:7743: trailing whitespace.
+   634	
.oracle/checkins/batch-2.md:7763: trailing whitespace.
+   733	
.oracle/checkins/batch-2.md:7789: trailing whitespace.
+   759	
.oracle/checkins/batch-2.md:7794: trailing whitespace.
+   764	
.oracle/checkins/batch-2.md:7798: trailing whitespace.
+   768	
.oracle/checkins/batch-2.md:7814: trailing whitespace.
+   784	
.oracle/checkins/batch-2.md:7817: trailing whitespace.
+   787	
.oracle/checkins/batch-2.md:7824: trailing whitespace.
+   794	
.oracle/checkins/batch-2.md:7826: trailing whitespace.
+   796	
.oracle/checkins/batch-2.md:7833: trailing whitespace.
+   803	
.oracle/checkins/batch-2.md:7843: trailing whitespace.
+   813	
.oracle/checkins/batch-2.md:7850: trailing whitespace.
+   820	
.oracle/checkins/batch-2.md:7853: trailing whitespace.
+   823	
.oracle/checkins/batch-2.md:7856: trailing whitespace.
+   826	
.oracle/checkins/batch-2.md:7870: trailing whitespace.
+   840	
.oracle/checkins/batch-2.md:7877: trailing whitespace.
+   847	
.oracle/checkins/batch-2.md:7887: trailing whitespace.
+   857	
.oracle/checkins/batch-2.md:7906: trailing whitespace.
+   995	
.oracle/checkins/batch-2.md:7907: trailing whitespace.
+   996	
.oracle/checkins/batch-2.md:7918: trailing whitespace.
+  1007	
.oracle/checkins/batch-2.md:7919: trailing whitespace.
+  1008	
.oracle/checkins/batch-2.md:7930: trailing whitespace.
+  1019	
.oracle/checkins/batch-2.md:7931: trailing whitespace.
+  1020	
.oracle/checkins/batch-2.md:7938: trailing whitespace.
+  1027	
.oracle/checkins/batch-2.md:7942: trailing whitespace.
+  1031	
.oracle/checkins/batch-2.md:7943: trailing whitespace.
+  1032	
.oracle/checkins/batch-2.md:7954: trailing whitespace.
+  1043	
.oracle/checkins/batch-2.md:7955: trailing whitespace.
+  1044	
.oracle/checkins/batch-2.md:7960: trailing whitespace.
+  1049	
.oracle/checkins/batch-2.md:7961: trailing whitespace.
+  1050	
.oracle/checkins/batch-2.md:7965: trailing whitespace.
+  1054	
.oracle/checkins/batch-2.md:7966: trailing whitespace.
+  1055	
.oracle/checkins/batch-2.md:7997: trailing whitespace.
+  1066	
.oracle/checkins/batch-2.md:7998: trailing whitespace.
+  1067	
.oracle/checkins/batch-2.md:8001: trailing whitespace.
+  1070	
.oracle/checkins/batch-2.md:8002: trailing whitespace.
+  1071	
.oracle/checkins/batch-2.md:8009: trailing whitespace.
+  1078	
.oracle/checkins/batch-2.md:8010: trailing whitespace.
+  1079	
.oracle/checkins/batch-2.md:8014: trailing whitespace.
+  1083	
.oracle/checkins/batch-2.md:8018: trailing whitespace.
+  1087	
.oracle/checkins/batch-2.md:8019: trailing whitespace.
+  1088	
.oracle/checkins/batch-2.md:8038: trailing whitespace.
+  1107	
.oracle/checkins/batch-2.md:8039: trailing whitespace.
+  1108	
.oracle/checkins/batch-2.md:8081: trailing whitespace.
+  1150	
.oracle/checkins/batch-2.md:8082: trailing whitespace.
+  1151	
.oracle/checkins/batch-2.md:8085: trailing whitespace.
+  1154	
.oracle/checkins/batch-2.md:8086: trailing whitespace.
+  1155	
.oracle/checkins/batch-2.md:8089: trailing whitespace.
+  1158	
.oracle/checkins/batch-2.md:8103: trailing whitespace.
+  1172	
.oracle/checkins/batch-2.md:8104: trailing whitespace.
+  1173	
.oracle/checkins/batch-2.md:8109: trailing whitespace.
+  1178	
.oracle/checkins/batch-2.md:8122: trailing whitespace.
+  1191	
.oracle/checkins/batch-2.md:8123: trailing whitespace.
+  1192	
.oracle/checkins/batch-2.md:8130: trailing whitespace.
+  1199	
.oracle/checkins/batch-2.md:8137: trailing whitespace.
+  1206	
.oracle/checkins/batch-2.md:8142: trailing whitespace.
+  1211	
.oracle/checkins/batch-2.md:8146: trailing whitespace.
+  1215	
.oracle/checkins/batch-2.md:8163: trailing whitespace.
+  1232	
.oracle/checkins/batch-2.md:8181: trailing whitespace.
+  1250	
.oracle/checkins/batch-2.md:8182: trailing whitespace.
+  1251	
.oracle/checkins/batch-2.md:8192: trailing whitespace.
+  1261	
.oracle/checkins/batch-2.md:8193: trailing whitespace.
+  1262	
.oracle/checkins/batch-2.md:8212: trailing whitespace.
+  1753	
.oracle/checkins/batch-2.md:8213: trailing whitespace.
+  1754	
.oracle/checkins/batch-2.md:8232: trailing whitespace.
+  1773	
.oracle/checkins/batch-2.md:8233: trailing whitespace.
+  1774	
.oracle/checkins/batch-2.md:8241: trailing whitespace.
+  1782	
.oracle/checkins/batch-2.md:8248: trailing whitespace.
+  1789	
.oracle/checkins/batch-2.md:8256: trailing whitespace.
+  1797	
.oracle/checkins/batch-2.md:8257: trailing whitespace.
+  1798	
.oracle/checkins/batch-2.md:8260: trailing whitespace.
+  1801	
.oracle/checkins/batch-2.md:8266: trailing whitespace.
+  1807	
.oracle/checkins/batch-2.md:8267: trailing whitespace.
+  1808	
.oracle/checkins/batch-2.md:8271: trailing whitespace.
+  1812	
.oracle/checkins/batch-2.md:8274: trailing whitespace.
+  1815	
.oracle/checkins/batch-2.md:8275: trailing whitespace.
+  1816	
.oracle/checkins/batch-2.md:8300: trailing whitespace.
+   733	
.oracle/checkins/batch-2.md:8326: trailing whitespace.
+   759	
.oracle/checkins/batch-2.md:8331: trailing whitespace.
+   764	
.oracle/checkins/batch-2.md:8335: trailing whitespace.
+   768	
.oracle/checkins/batch-2.md:8351: trailing whitespace.
+   784	
.oracle/checkins/batch-2.md:8354: trailing whitespace.
+   787	
.oracle/checkins/batch-2.md:8361: trailing whitespace.
+   794	
.oracle/checkins/batch-2.md:8363: trailing whitespace.
+   796	
.oracle/checkins/batch-2.md:8370: trailing whitespace.
+   803	
.oracle/checkins/batch-2.md:8380: trailing whitespace.
+   813	
.oracle/checkins/batch-2.md:8387: trailing whitespace.
+   820	
.oracle/checkins/batch-2.md:8390: trailing whitespace.
+   823	
.oracle/checkins/batch-2.md:8393: trailing whitespace.
+   826	
.oracle/checkins/batch-2.md:8407: trailing whitespace.
+   840	
.oracle/checkins/batch-2.md:8414: trailing whitespace.
+   847	
.oracle/checkins/batch-2.md:8461: trailing whitespace.
+   995	
.oracle/checkins/batch-2.md:8462: trailing whitespace.
+   996	
.oracle/checkins/batch-2.md:8473: trailing whitespace.
+  1007	
.oracle/checkins/batch-2.md:8474: trailing whitespace.
+  1008	
.oracle/checkins/batch-2.md:8485: trailing whitespace.
+  1019	
.oracle/checkins/batch-2.md:8486: trailing whitespace.
+  1020	
.oracle/checkins/batch-2.md:8493: trailing whitespace.
+  1027	
.oracle/checkins/batch-2.md:8497: trailing whitespace.
+  1031	
.oracle/checkins/batch-2.md:8498: trailing whitespace.
+  1032	
.oracle/checkins/batch-2.md:8509: trailing whitespace.
+  1043	
.oracle/checkins/batch-2.md:8510: trailing whitespace.
+  1044	
.oracle/checkins/batch-2.md:8515: trailing whitespace.
+  1049	
.oracle/checkins/batch-2.md:8516: trailing whitespace.
+  1050	
.oracle/checkins/batch-2.md:8520: trailing whitespace.
+  1054	
.oracle/checkins/batch-2.md:8521: trailing whitespace.
+  1055	
.oracle/checkins/batch-2.md:8522: trailing whitespace.
+  1270	
.oracle/checkins/batch-2.md:8577: trailing whitespace.
+  1325	
.oracle/checkins/batch-2.md:8578: trailing whitespace.
+  1326	
.oracle/checkins/batch-2.md:8590: trailing whitespace.
+  1338	
.oracle/checkins/batch-2.md:8591: trailing whitespace.
+  1339	
.oracle/checkins/batch-2.md:8627: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:8630: trailing whitespace.
+   190	
.oracle/checkins/batch-2.md:8646: trailing whitespace.
+   206	
.oracle/checkins/batch-2.md:8649: trailing whitespace.
+   209	
.oracle/checkins/batch-2.md:8654: trailing whitespace.
+   214	
.oracle/checkins/batch-2.md:8657: trailing whitespace.
+   217	
.oracle/checkins/batch-2.md:8662: trailing whitespace.
+   222	
.oracle/checkins/batch-2.md:8666: trailing whitespace.
+   226	
.oracle/checkins/batch-2.md:8669: trailing whitespace.
+   229	
.oracle/checkins/batch-2.md:8672: trailing whitespace.
+   232	
.oracle/checkins/batch-2.md:8675: trailing whitespace.
+   235	
.oracle/checkins/batch-2.md:8678: trailing whitespace.
+   238	
.oracle/checkins/batch-2.md:8681: trailing whitespace.
+   241	
.oracle/checkins/batch-2.md:8692: trailing whitespace.
+   252	
.oracle/checkins/batch-2.md:8695: trailing whitespace.
+   255	
.oracle/checkins/batch-2.md:8704: trailing whitespace.
+   264	
.oracle/checkins/batch-2.md:8708: trailing whitespace.
+   268	
.oracle/checkins/batch-2.md:8715: trailing whitespace.
+   430	
.oracle/checkins/batch-2.md:8716: trailing whitespace.
+   431	
.oracle/checkins/batch-2.md:8719: trailing whitespace.
+   434	
.oracle/checkins/batch-2.md:8726: trailing whitespace.
+   441	
.oracle/checkins/batch-2.md:8734: trailing whitespace.
+   449	
.oracle/checkins/batch-2.md:8743: trailing whitespace.
+   458	
.oracle/checkins/batch-2.md:8763: trailing whitespace.
+   478	
.oracle/checkins/batch-2.md:8767: trailing whitespace.
+   482	
.oracle/checkins/batch-2.md:8788: trailing whitespace.
+   503	
.oracle/checkins/batch-2.md:8792: trailing whitespace.
+   507	
.oracle/checkins/batch-2.md:8796: trailing whitespace.
+   511	
.oracle/checkins/batch-2.md:8798: trailing whitespace.
+   513	
.oracle/checkins/batch-2.md:8807: trailing whitespace.
+   522	
.oracle/checkins/batch-2.md:8892: trailing whitespace.
+   607	
.oracle/checkins/batch-2.md:8919: trailing whitespace.
+   634	
.oracle/checkins/batch-2.md:8970: trailing whitespace.
+   685	
.oracle/checkins/batch-2.md:8992: trailing whitespace.
+    37	
.oracle/checkins/batch-2.md:9002: trailing whitespace.
+    47	
.oracle/checkins/batch-2.md:9013: trailing whitespace.
+    58	
.oracle/checkins/batch-2.md:9015: trailing whitespace.
+    60	
.oracle/checkins/batch-2.md:9020: trailing whitespace.
+    65	
.oracle/checkins/batch-2.md:9024: trailing whitespace.
+    69	
.oracle/checkins/batch-2.md:9025: trailing whitespace.
+    70	
.oracle/checkins/batch-2.md:9051: trailing whitespace.
+   345	
.oracle/checkins/batch-2.md:9053: trailing whitespace.
+   347	
.oracle/checkins/batch-2.md:9060: trailing whitespace.
+   354	
.oracle/checkins/batch-2.md:9062: trailing whitespace.
+   940	
.oracle/checkins/batch-2.md:9070: trailing whitespace.
+   948	
.oracle/checkins/batch-2.md:9071: trailing whitespace.
+   949	
.oracle/checkins/batch-2.md:9086: trailing whitespace.
+   964	
.oracle/checkins/batch-2.md:9087: trailing whitespace.
+   965	
.oracle/checkins/batch-2.md:9177: trailing whitespace.
+   719	
.oracle/checkins/batch-2.md:9184: trailing whitespace.
+   726	
.oracle/checkins/batch-2.md:9186: trailing whitespace.
+   728	
.oracle/checkins/batch-2.md:9188: trailing whitespace.
+   730	
.oracle/checkins/batch-2.md:9189: trailing whitespace.
+   731	
.oracle/checkins/batch-2.md:9192: trailing whitespace.
+   734	
.oracle/checkins/batch-2.md:9198: trailing whitespace.
+   740	
.oracle/checkins/batch-2.md:9199: trailing whitespace.
+   741	
.oracle/checkins/batch-2.md:9227: trailing whitespace.
+   769	
.oracle/checkins/batch-2.md:9228: trailing whitespace.
+   770	
.oracle/checkins/batch-2.md:9244: trailing whitespace.
+   786	
.oracle/checkins/batch-2.md:9245: trailing whitespace.
+   787	
.oracle/checkins/batch-2.md:9252: trailing whitespace.
+   794	
.oracle/checkins/batch-2.md:9253: trailing whitespace.
+   795	
.oracle/checkins/batch-2.md:9287: trailing whitespace.
+   829	
.oracle/checkins/batch-2.md:9288: trailing whitespace.
+   830	
.oracle/checkins/batch-2.md:9320: trailing whitespace.
+   830	
.oracle/checkins/batch-2.md:9441: trailing whitespace.
+   951	
.oracle/checkins/batch-2.md:9457: trailing whitespace.
+   967	
.oracle/checkins/batch-2.md:9459: trailing whitespace.
+   969	
.oracle/checkins/batch-2.md:9464: trailing whitespace.
+   974	
.oracle/checkins/batch-2.md:9471: trailing whitespace.
+   981	
.oracle/checkins/batch-2.md:9472: trailing whitespace.
+   982	
.oracle/checkins/batch-2.md:9475: trailing whitespace.
+   985	
.oracle/checkins/batch-2.md:9476: trailing whitespace.
+   986	
.oracle/checkins/batch-2.md:9479: trailing whitespace.
+   989	
.oracle/checkins/batch-2.md:9488: trailing whitespace.
+   998	
.oracle/checkins/batch-2.md:9489: trailing whitespace.
+   999	
.oracle/checkins/batch-2.md:9508: trailing whitespace.
+  1018	
.oracle/checkins/batch-2.md:9509: trailing whitespace.
+  1019	
.oracle/checkins/batch-2.md:9533: trailing whitespace.
+  1043	
.oracle/checkins/batch-2.md:9534: trailing whitespace.
+  1044	
.oracle/checkins/batch-2.md:9614: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:9616: trailing whitespace.
+     4	
.oracle/checkins/batch-2.md:9617: trailing whitespace.
+     5	
.oracle/checkins/batch-2.md:9619: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:9620: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:9631: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:9637: trailing whitespace.
+    25	
.oracle/checkins/batch-2.md:9641: trailing whitespace.
+    29	
.oracle/checkins/batch-2.md:9650: trailing whitespace.
+    38	
.oracle/checkins/batch-2.md:9651: trailing whitespace.
+    39	
.oracle/checkins/batch-2.md:9654: trailing whitespace.
+    42	
.oracle/checkins/batch-2.md:9660: trailing whitespace.
+    48	
.oracle/checkins/batch-2.md:9661: trailing whitespace.
+    49	
.oracle/checkins/batch-2.md:9665: trailing whitespace.
+    53	
.oracle/checkins/batch-2.md:9666: trailing whitespace.
+    54	
.oracle/checkins/batch-2.md:9673: trailing whitespace.
+    50	
.oracle/checkins/batch-2.md:9674: trailing whitespace.
+    51	
.oracle/checkins/batch-2.md:9677: trailing whitespace.
+    54	
.oracle/checkins/batch-2.md:9704: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:9710: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:9712: trailing whitespace.
+     4	
.oracle/checkins/batch-2.md:9715: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:9720: trailing whitespace.
+    12	
.oracle/checkins/batch-2.md:9721: trailing whitespace.
+    13	
.oracle/checkins/batch-2.md:9724: trailing whitespace.
+    16	
.oracle/checkins/batch-2.md:9731: trailing whitespace.
+    23	
.oracle/checkins/batch-2.md:9734: trailing whitespace.
+    26	
.oracle/checkins/batch-2.md:9739: trailing whitespace.
+    31	
.oracle/checkins/batch-2.md:9752: trailing whitespace.
+    44	
.oracle/checkins/batch-2.md:9787: trailing whitespace.
+    79	
.oracle/checkins/batch-2.md:9805: trailing whitespace.
+    97	
.oracle/checkins/batch-2.md:9812: trailing whitespace.
+   104	
.oracle/checkins/batch-2.md:9815: trailing whitespace.
+   107	
.oracle/checkins/batch-2.md:9825: trailing whitespace.
+   117	
.oracle/checkins/batch-2.md:9832: trailing whitespace.
+   124	
.oracle/checkins/batch-2.md:9893: trailing whitespace.
+   383	
.oracle/checkins/batch-2.md:9894: trailing whitespace.
+   384	
.oracle/checkins/batch-2.md:9903: trailing whitespace.
+   393	
.oracle/checkins/batch-2.md:9904: trailing whitespace.
+   394	
.oracle/checkins/batch-2.md:9912: trailing whitespace.
+   402	
.oracle/checkins/batch-2.md:9913: trailing whitespace.
+   403	
.oracle/checkins/batch-2.md:9916: trailing whitespace.
+   406	
.oracle/checkins/batch-2.md:9926: trailing whitespace.
+   416	
.oracle/checkins/batch-2.md:9927: trailing whitespace.
+   417	
.oracle/checkins/batch-2.md:9940: trailing whitespace.
+   430	
.oracle/checkins/batch-2.md:10067: trailing whitespace.
+  1670	
.oracle/checkins/batch-2.md:10068: trailing whitespace.
+  1671	
.oracle/checkins/batch-2.md:10077: trailing whitespace.
+  1680	
.oracle/checkins/batch-2.md:10078: trailing whitespace.
+  1681	
.oracle/checkins/batch-2.md:10087: trailing whitespace.
+  1690	
.oracle/checkins/batch-2.md:10088: trailing whitespace.
+  1691	
.oracle/checkins/batch-2.md:10096: trailing whitespace.
+  1699	
.oracle/checkins/batch-2.md:10097: trailing whitespace.
+  1700	
.oracle/checkins/batch-2.md:10107: trailing whitespace.
+  1710	
.oracle/checkins/batch-2.md:10108: trailing whitespace.
+  1711	
.oracle/checkins/batch-2.md:10121: trailing whitespace.
+  1724	
.oracle/checkins/batch-2.md:10122: trailing whitespace.
+  1725	
.oracle/checkins/batch-2.md:10150: trailing whitespace.
+  1753	
.oracle/checkins/batch-2.md:10151: trailing whitespace.
+  1754	
.oracle/checkins/batch-2.md:10170: trailing whitespace.
+  1773	
.oracle/checkins/batch-2.md:10171: trailing whitespace.
+  1774	
.oracle/checkins/batch-2.md:10179: trailing whitespace.
+  1782	
.oracle/checkins/batch-2.md:10186: trailing whitespace.
+  1789	
.oracle/checkins/batch-2.md:10194: trailing whitespace.
+  1797	
.oracle/checkins/batch-2.md:10195: trailing whitespace.
+  1798	
.oracle/checkins/batch-2.md:10208: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10210: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10215: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10216: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10228: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10229: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10233: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10234: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10236: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10237: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10267: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10280: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10281: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10285: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10290: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10291: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10297: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10300: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10306: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10313: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10314: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10333: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10334: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10345: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10346: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10355: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10356: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10363: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10364: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10374: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10375: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10378: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10385: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10392: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10394: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10402: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10403: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10408: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10411: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10421: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10422: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10426: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10430: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10437: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10438: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10441: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10445: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10448: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10455: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10457: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10459: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10460: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10464: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10470: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10476: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10482: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10488: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10494: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10495: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10499: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10507: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10515: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10523: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10524: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10528: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10535: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10541: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10547: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10548: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10552: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10553: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10557: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10570: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10579: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10580: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10585: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10599: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10600: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10610: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10611: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10624: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10625: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10647: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10649: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10679: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10681: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10688: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10691: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10697: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10698: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10703: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10716: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10717: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10730: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10731: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10763: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10764: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10785: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10786: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10797: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10805: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10815: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10816: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10819: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10825: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:10826: trailing whitespace.
+ 

2026-08-13T19:34:18.105577Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:18.105895Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:18.105929Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:23.377305Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:23.377622Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:23.377677Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:28.146603Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:28.148604Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T19:34:28.148636Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc 'git show --stat --oneline --summary 0d2bb176 && git diff --check 8a8300bb..0d2bb176 && git diff --name-status 8a8300bb..0d2bb176' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 258ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
0d2bb176 megado run2 Batch D+E: IR-authoritative emission — mode via node.mode only, groups kwarg removed + member-ID remap, wf.groups reconciled, VibeEdge sole connectivity authority
 tests/test_foundation_utils.py           |  15 ++-
 tests/test_layout_store.py               |   7 +-
 tests/test_patches.py                    |   5 +-
 tests/test_porting_normalize_ingest.py   |   3 +-
 tests/test_porting_synthetic_fixtures.py |   4 +-
 tests/test_porting_ui_emitter.py         | 104 +++++++++++++++---
 tests/test_schema_validate.py            |  29 +++--
 tests/test_ui_layout.py                  |   5 +-
 tests/test_workflow_core.py              | 176 ++++++++++++++++++++++++++++---
 vibecomfy/_compile/_graph.py             |  27 +++--
 vibecomfy/_compile/_helpers.py           |  10 +-
 vibecomfy/commands/port/_export.py       |   5 +-
 vibecomfy/ingest/normalize.py            |  29 +++--
 vibecomfy/patches/ltx_lowvram.py         |  20 +++-
 vibecomfy/porting/emit/ui.py             | 133 ++++++++++++++---------
 vibecomfy/porting/layout_store.py        |   8 +-
 vibecomfy/runtime/eval/core.py           |  12 +--
 vibecomfy/schema/validate.py             |   9 +-
 vibecomfy/workflow.py                    |  97 +++++++++++++++--
 19 files changed, 535 insertions(+), 163 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	tests/test_foundation_utils.py
M	tests/test_layout_store.py
M	tests/test_patches.py
M	tests/test_porting_normalize_ingest.py
M	tests/test_porting_synthetic_fixtures.py
M	tests/test_porting_ui_emitter.py
M	tests/test_schema_validate.py
M	tests/test_ui_layout.py
M	tests/test_workflow_core.py
M	vibecomfy/_compile/_graph.py
M	vibecomfy/_compile/_helpers.py
M	vibecomfy/commands/port/_export.py
M	vibecomfy/ingest/normalize.py
M	vibecomfy/patches/ltx_lowvram.py
M	vibecomfy/porting/emit/ui.py
M	vibecomfy/porting/layout_store.py
M	vibecomfy/runtime/eval/core.py
M	vibecomfy/schema/validate.py
M	vibecomfy/workflow.py

exec
/bin/zsh -lc "git show 8a8300bb:.oracle/tasklist.md | rg -n -C 5 'Batch D|VibeEdge|Task 6|groups|furniture'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 259ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8-   - Fail closed if the directory is absent or contains zero envelopes.
9-   - Process `*.json` except `*.layout.json`; reject sidecars if explicitly supplied.
10-   - Decode only with `from_envelope()`, serialize only with `to_envelope()` and `sort_keys=True`.
11-   - Stage every output before any replacement.
12-   - Allow exactly:
13:     - add `groups: []` where absent;
14-     - remove `compiled_api`;
15-     - add integer first-class `node.mode`.
16-   - Preserve all metadata and `_ui` content exactly, including legacy mode copies.
17-   - Emit a machine-readable per-file delta report; support check-only and explicit write modes.
18-
--
25-3. Harden `check_b02_rich_preservation.py`.
26-
27-   - Require an explicit corpus directory and fail on missing/empty input.
28-   - Read first-class mode first with legacy fallback.
29-   - Use `from_envelope()` for corpus envelopes and `from_api()` for normalized API dictionaries.
30:   - Put groups on `wf.groups`; stop passing `groups=`.
31-   - Report checked/skipped counts, including two skipped sidecars.
32-
33-4. Re-anchor corpus tests around derived execution state.
34-
35-   - Remove `compiled_api` assumptions.
--
92-
93-   - `_named_import()` remains for raw dictionaries of unknown shape.
94-   - Ready-ID and `.py` paths continue bypassing it.
95-   - `workbench.py` is not a dispatcher caller and receives no migration edit.
96-
97:4. Update live comments/docs and mechanically migrate affected tests. Re-anchor equivalence tests on IDs, UIDs, classes, modes, groups, edges, and compiled output.
98-
99-Acceptance gate:
100-
101-- `rg 'convert_to_vibe_format' --glob '*.py'` finds only an intentional negative guard.
102-- `vibecomfy.ingest` exposes `from_envelope`, `from_ui`, and `from_api`, not the removed dispatcher.
103-- `_named_import()` still handles ambiguous raw JSON/image-loader inputs.
104-- Generated scratchpad code imports and calls `from_api()`.
105-- Offline routes remain offline.
106-- Focused ingest, loader, security, ready-template, scratchpad, porting, and B02 tests pass.
107-
108:## Batch D+E — IR-authoritative emission and groups `[XHARD]`
109-
110-Tasks:
111-
112:1. Make `_resolve_furniture()` obtain mode only through `_get_node_mode(node)`.
113-
114-   - Sidecars and top-level metadata retain authority for flags, colors, properties, title, and geometry—not mode.
115-   - Keep the single legacy `_ui.mode` fallback inside `_get_node_mode()`.
116-
117:2. Remove the `groups` parameter from `emit_ui_json()` and all seven callers/tests.
118-
119:3. Reconcile groups into the IR immediately after `_resolve_preserve_source()`.
120-
121:   - If the selected preserve store contains groups, deep-copy them into `workflow.groups`.
122:   - Otherwise retain the groups already present on the workflow.
123-   - Preserve existing fresh/sidecar/`--from`/breadcrumb precedence.
124-
125-4. Remap group membership during emission.
126-
127-   - Build aliases from workflow node ID, numeric source ID, `node.uid`, and captured `_ui.id`.
128-   - Map known group members to final LiteGraph integers through `id_remap`.
129-   - Preserve member order and group metadata.
130-   - Deterministically omit stale/unresolved members rather than emitting dangling IDs.
131:   - Merge IR groups before engine-generated groups and retain title deduplication.
132-
133:5. Make `write_layout()` serialize `wf.groups`, not `wf.metadata["groups"]`.
134-
135:6. Make `VibeEdge` the sole IR representation and authority for connectivity. *(oracle-approved addition, checkpoint 2)*
136-
137:   - Migrate all package-owned low-level construction that stores Comfy API link pairs in `VibeNode.inputs` to construct `VibeEdge` objects instead; update affected tests and fixtures.
138-   - Keep `from_api()` and `from_ui()` as normalization boundaries: incoming API link pairs become edges and are absent from `node.inputs`.
139-   - Outside those ingestion boundaries, fail closed with a targeted error when an API-link-shaped value remains in `VibeNode.inputs` during envelope decode, validation, serialization, or compilation. Compilation must not mutate the IR or silently choose between embedded-input and edge authority.
140-   - Use the canonical API-link predicate narrowly so ordinary two-element literal lists are not rejected.
141-   - Test raw-link-only inputs and raw-link-plus-edge collisions with both identical and conflicting sources, plus unchanged compiled output for canonical edge-only workflows.
142-
--
144-
145-- Compile and emit agree for modes 0/2/4 despite conflicting sidecar or metadata values.
146-- Raw source-ID and UID-based group members both emit as correct LiteGraph integers.
147-- No emitted group contains dangling/string membership for emitted nodes.
148-- Sidecar-only, `--from`, conflict, breadcrumb, `--fresh`, removed-node, and nonnumeric-node-ID cases pass.
149:- `port convert` writes reconciled groups onto `wf.groups`.
150:- No `emit_ui_json(..., groups=...)` calls or signature remain.
151-- No package-owned low-level `VibeNode` construction stores API link pairs in `inputs`, and no serialized envelope contains them.
152-- Raw-link/edge collisions fail explicitly rather than compiling with implicit edge-wins precedence.
153-- Canonical `from_api()`/`from_ui()` ingestion and edge-only compile round trips remain unchanged.
154-- Focused port, emitter, layout, CLI, and B02 tests pass.
155-
--
237-- `make ci`
238-- `make full-pytest`
239-- `git diff --check`
240-- Static guards for:
241-  - removed dispatcher;
242:  - removed `groups=` emitter surface;
243-  - sidecar/metadata mode authority in emission;
244-  - remaining geometry descents outside approved ingest/hash fallbacks.
245-- Verify manifest and Hivemind were not mutated.
246-- Final oracle review of the complete branch diff plus the external-corpus report.
247-
248:Explicitly deferred: manifest repair, Hivemind payload refresh/upsert, tracking the 466 MB corpus, id-map redesign, typed groups/metadata, mode enum/sentinel redesign, slots, JS consumers, and full compile/emit unification.
249-
250-**New exploration areas:** none.
251-tokens used
252-52,078
253-# Revised frozen plan

exec
/bin/zsh -lc 'git diff --unified=80 8a8300bb..0d2bb176 -- vibecomfy/_compile/_graph.py vibecomfy/_compile/_helpers.py vibecomfy/workflow.py vibecomfy/schema/validate.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/_compile/_graph.py b/vibecomfy/_compile/_graph.py
index b2b8603a..ef3e7c07 100644
--- a/vibecomfy/_compile/_graph.py
+++ b/vibecomfy/_compile/_graph.py
@@ -1,55 +1,70 @@
 from __future__ import annotations
 
 from typing import Any
 
 
 UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})
 
 
 def is_api_link(
     value: Any,
     *,
     allow_tuple: bool = False,
     require_string_node_id: bool = False,
     require_numeric_node_id: bool = True,
     allow_compound_node_id: bool = False,
     require_int_slot: bool = False,
 ) -> bool:
     """Return whether ``value`` is a ComfyUI API link pair.
 
-    The defaults match the most common legacy helper in this repo: a list pair
-    whose source id is digit-shaped after ``str(...)`` coercion. Flags let
-    stricter call sites preserve their existing list/tuple, source-id, and slot
-    rules explicitly.
+    The defaults retain the legacy configurable helper contract.  IR authority
+    boundaries must use :func:`is_canonical_api_link`, whose stricter shape
+    keeps ordinary two-item literal lists out of connectivity logic.
     """
 
     allowed_types = (list, tuple) if allow_tuple else (list,)
     if not (isinstance(value, allowed_types) and len(value) == 2):
         return False
 
     source_id, slot = value
     if require_string_node_id and not isinstance(source_id, str):
         return False
     if require_numeric_node_id and not _is_numeric_node_id(source_id, allow_compound=allow_compound_node_id):
         return False
-    if require_int_slot and not isinstance(slot, int):
+    if require_int_slot and (isinstance(slot, bool) or not isinstance(slot, int)):
         return False
     return True
 
 
+def is_canonical_api_link(value: Any) -> bool:
+    """Return whether *value* has the canonical stored Comfy API link shape."""
+    return is_api_link(
+        value,
+        allow_tuple=False,
+        require_string_node_id=True,
+        require_numeric_node_id=True,
+        require_int_slot=True,
+    )
+
+
 def node_id_sort_key(node_id: Any, *, allow_compound: bool = False) -> tuple[Any, ...]:
     """Sort node ids numerically when possible, with a stable text fallback."""
 
     text = str(node_id)
     parts = text.split(":") if allow_compound else [text]
     if all(part.isdigit() for part in parts):
         return tuple(int(part) for part in parts)
     return (1 << 31, text)
 
 
 def _is_numeric_node_id(node_id: Any, *, allow_compound: bool) -> bool:
     parts = str(node_id).split(":") if allow_compound else [str(node_id)]
     return all(part.isdigit() for part in parts)
 
 
-__all__ = ["UI_ONLY_CLASS_TYPES", "is_api_link", "node_id_sort_key"]
+__all__ = [
+    "UI_ONLY_CLASS_TYPES",
+    "is_api_link",
+    "is_canonical_api_link",
+    "node_id_sort_key",
+]
diff --git a/vibecomfy/_compile/_helpers.py b/vibecomfy/_compile/_helpers.py
index 4db577e3..528a18bb 100644
--- a/vibecomfy/_compile/_helpers.py
+++ b/vibecomfy/_compile/_helpers.py
@@ -1,85 +1,87 @@
 from __future__ import annotations
 
 from dataclasses import dataclass, field
 from typing import Any, Mapping, Sequence
 
+from vibecomfy._compile._graph import is_api_link
+
 
 UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})
 BROADCAST_HELPER_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode"})
 # Conversion-only: stripped only by the resolver inside port_convert_workflow, never silently
 # dropped by generic compile paths (is_helper_class_type / _is_ui_only_node do NOT consult this set).
 PASSTHROUGH_HELPER_CLASS_TYPES: frozenset[str] = frozenset({"Reroute", "PrimitiveNode"})
 # Conversion-only: stripped only by the resolver inside port_convert_workflow, never silently
 # dropped by generic compile paths (is_helper_class_type / _is_ui_only_node do NOT consult this set).
 VALUE_HELPER_CLASS_TYPES: frozenset[str] = frozenset(
     {"PrimitiveBoolean", "PrimitiveInt", "PrimitiveFloat", "PrimitiveString", "PrimitiveStringMultiline"}
 )
 HELPER_CLASS_TYPES: frozenset[str] = UI_ONLY_CLASS_TYPES | BROADCAST_HELPER_CLASS_TYPES
 RESOLVABLE_HELPER_CLASS_TYPES: frozenset[str] = (
     BROADCAST_HELPER_CLASS_TYPES | PASSTHROUGH_HELPER_CLASS_TYPES | VALUE_HELPER_CLASS_TYPES
 )
 
 
 @dataclass(frozen=True, slots=True)
 class HelperDiagnostic:
     code: str
     message: str
     severity: str = "warning"
     node_id: str | None = None
     class_type: str | None = None
     detail: dict[str, Any] = field(default_factory=dict)
 
 
 def is_ui_only_class_type(class_type: str) -> bool:
     return class_type in UI_ONLY_CLASS_TYPES
 
 
 def is_broadcast_helper_class_type(class_type: str) -> bool:
     return class_type in BROADCAST_HELPER_CLASS_TYPES
 
 
 def is_passthrough_helper_class_type(class_type: str) -> bool:
     return class_type in PASSTHROUGH_HELPER_CLASS_TYPES
 
 
 def is_value_helper_class_type(class_type: str) -> bool:
     return class_type in VALUE_HELPER_CLASS_TYPES
 
 
 def is_helper_class_type(class_type: str) -> bool:
     return class_type in HELPER_CLASS_TYPES
 
 
 def helper_stripped_nodes(nodes: Mapping[str, Any]) -> dict[str, Any]:
     return {
         str(node_id): node
         for node_id, node in nodes.items()
         if not is_helper_class_type(_node_class_type(node))
     }
 
 
 def helper_stripped_class_types(nodes: Mapping[str, Any]) -> list[str]:
     return sorted({_node_class_type(node) for node in helper_stripped_nodes(nodes).values()})
 
 
 def collect_helper_diagnostics(nodes: Mapping[str, Any], edges: Sequence[Any]) -> list[HelperDiagnostic]:
     broadcast_sources = collect_broadcast_sources(nodes, edges)
     diagnostics: list[HelperDiagnostic] = []
     for node_id, node in _sorted_nodes(nodes):
         class_type = _node_class_type(node)
         if class_type in UI_ONLY_CLASS_TYPES:
             diagnostics.append(
                 HelperDiagnostic(
                     code="ui_only_node_stripped",
                     message=f"{class_type} node {node_id} is UI-only and will be omitted from runtime prompts.",
                     severity="info",
                     node_id=str(node_id),
                     class_type=class_type,
                 )
             )
             continue
         if class_type in PASSTHROUGH_HELPER_CLASS_TYPES:
             diagnostics.append(
                 HelperDiagnostic(
                     code="passthrough_helper_source_presence",
                     message=(
@@ -118,168 +120,160 @@ def collect_helper_diagnostics(nodes: Mapping[str, Any], edges: Sequence[Any]) -
                     class_type=class_type,
                 )
             )
             continue
         if name in broadcast_sources:
             diagnostics.append(
                 HelperDiagnostic(
                     code="helper_broadcast_resolved",
                     message=f"{class_type} node {node_id} broadcast {name!r} resolves to a runtime link.",
                     severity="info",
                     node_id=str(node_id),
                     class_type=class_type,
                     detail={"broadcast": name, "source": broadcast_sources[name]},
                 )
             )
             continue
         diagnostics.append(
             HelperDiagnostic(
                 code="helper_broadcast_unresolved",
                 message=f"{class_type} node {node_id} references unresolved broadcast {name!r}.",
                 node_id=str(node_id),
                 class_type=class_type,
                 detail={"broadcast": name},
             )
         )
     return diagnostics
 
 
 def collect_broadcast_sources(nodes: Mapping[str, Any], edges: Sequence[Any]) -> dict[str, list[Any]]:
     sources: dict[str, list[Any]] = {}
     edge_sources_by_target: dict[str, list[Any]] = {}
     for edge in edges:
         target_node = nodes.get(str(_edge_attr(edge, "to_node")))
         if target_node is None or _node_class_type(target_node) != "SetNode":
             continue
         if _edge_attr(edge, "to_input") == "widget_0":
             continue
         from_output = _edge_attr(edge, "from_output")
         try:
             output_slot = int(from_output)
         except (TypeError, ValueError):
             output_slot = 0
         edge_sources_by_target[str(_edge_attr(edge, "to_node"))] = [str(_edge_attr(edge, "from_node")), output_slot]
 
     for node_id, node in nodes.items():
         if _node_class_type(node) != "SetNode":
             continue
         name = broadcast_name(node)
         if not name:
             continue
         direct_source = first_link_input(_compile_helper_inputs(node))
         if direct_source is not None:
             sources[name] = direct_source
         elif str(node_id) in edge_sources_by_target:
             sources[name] = edge_sources_by_target[str(node_id)]
     return sources
 
 
 def broadcast_name(node: Any) -> str | None:
     inputs = _node_inputs(node)
     widgets = _node_widgets(node)
     name = inputs.get("widget_0", widgets.get("widget_0"))
     # Fall back to ``name`` — the emitter writes SetNode/GetNode channel names
     # as ``name=`` kwargs (e.g. ``_node(wf, 'SetNode', ..., name='LATENT')``).
     if name is None:
         name = inputs.get("name")
     if name is None:
         return None
     return str(name)
 
 
 def first_link_input(inputs: Mapping[str, Any]) -> list[Any] | None:
     for key, value in inputs.items():
         if key == "widget_0":
             continue
         if is_api_link(value):
             return [str(value[0]), int(value[1])]
     return None
 
 
-def is_api_link(value: Any) -> bool:
-    if not isinstance(value, list) or len(value) != 2:
-        return False
-    if isinstance(value[1], bool) or not isinstance(value[1], int):
-        return False
-    return True
-
-
 def _compile_helper_inputs(node: Any) -> dict[str, Any]:
     inputs = dict(_node_widgets(node))
     inputs.update(_node_inputs(node))
     return inputs
 
 
 def _sorted_nodes(nodes: Mapping[str, Any]) -> list[tuple[str, Any]]:
     return sorted(nodes.items(), key=lambda item: _node_sort_key(item[0]))
 
 
 def _node_sort_key(node_id: Any) -> tuple[int, str]:
     try:
         return (int(node_id), str(node_id))
     except (TypeError, ValueError):
         return (10**12, str(node_id))
 
 
 def _node_class_type(node: Any) -> str:
     class_type = getattr(node, "class_type", None)
     if isinstance(class_type, str):
         return class_type
     if isinstance(node, Mapping):
         for key in ("class_type", "type"):
             value = node.get(key)
             if isinstance(value, str):
                 return value
     return ""
 
 
 def _node_inputs(node: Any) -> Mapping[str, Any]:
     inputs = getattr(node, "inputs", None)
     if isinstance(inputs, Mapping):
         return inputs
     if isinstance(node, Mapping):
         value = node.get("inputs")
         if isinstance(value, Mapping):
             return value
     return {}
 
 
 def _node_widgets(node: Any) -> Mapping[str, Any]:
     widgets = getattr(node, "widgets", None)
     if isinstance(widgets, Mapping):
         return widgets
     if isinstance(node, Mapping):
         value = node.get("widgets")
         if isinstance(value, Mapping):
             return value
     return {}
 
 
 def _edge_attr(edge: Any, name: str) -> Any:
     if isinstance(edge, Mapping):
         return edge.get(name)
     return getattr(edge, name)
 
 
 __all__ = [
     "BROADCAST_HELPER_CLASS_TYPES",
     "HELPER_CLASS_TYPES",
     "HelperDiagnostic",
     "PASSTHROUGH_HELPER_CLASS_TYPES",
     "RESOLVABLE_HELPER_CLASS_TYPES",
     "UI_ONLY_CLASS_TYPES",
     "VALUE_HELPER_CLASS_TYPES",
     "_compile_helper_inputs",
     "_edge_attr",
     "_node_class_type",
     "_node_inputs",
     "_node_sort_key",
     "_node_widgets",
     "_sorted_nodes",
     "broadcast_name",
     "collect_broadcast_sources",
     "collect_helper_diagnostics",
     "first_link_input",
     "helper_stripped_class_types",
     "helper_stripped_nodes",
     "is_api_link",
     "is_broadcast_helper_class_type",
diff --git a/vibecomfy/schema/validate.py b/vibecomfy/schema/validate.py
index 7a23807d..d7702865 100644
--- a/vibecomfy/schema/validate.py
+++ b/vibecomfy/schema/validate.py
@@ -1,86 +1,88 @@
 from __future__ import annotations
 
 import copy
 import re
 from typing import Any
 
+from vibecomfy._compile._graph import is_canonical_api_link
+
 from vibecomfy.metadata import MODEL_FILE_EXTENSIONS
 from vibecomfy.model_assets import _subdir_for_model_reference
 from vibecomfy.schema.provider import SchemaProvider, schema_for, schema_registry_empty
 from vibecomfy.workflow import ValidationIssue, VibeWorkflow
 
 
 def format_issue(issue: Any) -> str:
     detail = issue.detail or {}
     location = " ".join(
         f"{key}={detail[key]}" for key in ("node_id", "class_type", "input") if key in detail
     )
     return f"[{issue.code}] {location}: {issue.message}".strip()
 
 
 def validation_errors_payload(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
     """Group concrete validation errors by node for agent feedback payloads."""
     grouped: dict[tuple[str | None, str | None], dict[str, Any]] = {}
     for issue in issues:
         if issue.severity != "error":
             continue
         detail = issue.detail or {}
         node_id = detail.get("node_id") or detail.get("to_node") or detail.get("from_node")
         class_type = detail.get("class_type") or detail.get("to_class_type") or detail.get("from_class_type")
         key = (
             str(node_id) if node_id is not None else None,
             str(class_type) if class_type is not None else None,
         )
         entry = grouped.setdefault(
             key,
             {
                 "node_id": key[0],
                 "class_type": key[1],
                 "errors": [],
             },
         )
         entry["errors"].append(
             {
                 "code": issue.code,
                 "message": issue.message,
                 "input": detail.get("input") or detail.get("to_input"),
                 "detail": dict(detail),
             }
         )
     return list(grouped.values())
 
 
 #: Known-lying custom-node schemas that may suppress only ``unknown_input`` and
 #: ``value_*`` validation issues. Every entry must be cross-referenced from
 #: ``docs/node_pack_reconciliation.md`` with its contract/root-cause note.
 #:
 #: Classes listed here have stub object_info cache entries that only define
 #: category/description but lack full input schemas; they were added to satisfy
 #: ``unknown_class_type`` gating without triggering ``unknown_input`` cascade
 #: errors on every workflow input. When a real runpod snapshot is available for
 #: the pack, remove the stub file and the entry here.
 SCHEMA_VALIDATION_SKIP_CLASSES: dict[str, str] = {
     # ComfyUI-Florence2 — stub schema; real schema from runpod snapshot pending
     "DownloadAndLoadFlorence2Model": "stub schema - see docs/node_pack_reconciliation.md",
     "Florence2Run": "stub schema - see docs/node_pack_reconciliation.md",
     # ComfyUI-GIMM-VFI — stub schema; real schema from runpod snapshot pending
     "DownloadAndLoadGIMMVFIModel": "stub schema - see docs/node_pack_reconciliation.md",
     "GIMMVFI_interpolate": "stub schema - see docs/node_pack_reconciliation.md",
     # ComfyUI-MelBandRoformer — stub schema; real schema from runpod snapshot pending
     "MelBandRoFormerModelLoader": "stub schema - see docs/node_pack_reconciliation.md",
     "MelBandRoFormerSampler": "stub schema - see docs/node_pack_reconciliation.md",
     # ComfyUI-Custom-Scripts — stub schema; real schema from runpod snapshot pending
     "ShowText|pysssss": "stub schema - see docs/node_pack_reconciliation.md",
     "MathExpression|pysssss": "stub schema - see docs/node_pack_reconciliation.md",
     # comfyui_controlnet_aux — stub schema; real schema from runpod snapshot pending
     "DWPreprocessor": "stub schema - see docs/node_pack_reconciliation.md",
     "CannyEdgePreprocessor": "stub schema - see docs/node_pack_reconciliation.md",
     "DepthAnythingPreprocessor": "stub schema - see docs/node_pack_reconciliation.md",
     # ComfyUI-DepthAnythingV2 — stub entries added; real schema from runpod snapshot pending
     "VideoDepthAnythingProcess": "stub schema - see docs/node_pack_reconciliation.md",
     "LoadVideoDepthAnythingModel": "stub schema - see docs/node_pack_reconciliation.md",
     "VideoDepthAnythingOutput": "stub schema - see docs/node_pack_reconciliation.md",
     # ComfyUI-WanVideoWrapper — WanVideoModelLoader schema snapshot predates vace_model input
     # vace_model was added in a newer WanVideoWrapper version; snapshot needs refresh
     "WanVideoModelLoader": "snapshot predates vace_model input - see docs/node_pack_reconciliation.md",
     # ComfyUI-WanVideoWrapper — VACE model enum only captures one HiddenSwitch-local file
@@ -635,166 +637,161 @@ def _normalize_type(value: Any) -> str | None:
 
 def socket_types_compatible(output_type: Any, input_type: Any) -> bool:
     """Return whether a Comfy output socket type can connect to an input type."""
 
     normalized_output = _normalize_type(output_type)
     normalized_input = _normalize_type(input_type)
     if normalized_output is None or normalized_input is None:
         return True
     if normalized_output == normalized_input:
         return True
     if normalized_output in {"*", "ANY"} or normalized_input in {"*", "ANY"}:
         return True
     return False
 
 
 def _primitive_expected_type(value: Any) -> str | None:
     normalized = _normalize_type(value)
     if normalized in {"INT", "INTEGER"}:
         return "INT"
     if normalized in {"FLOAT", "DOUBLE"}:
         return "FLOAT"
     if normalized in {"BOOL", "BOOLEAN"}:
         return "BOOLEAN"
     if normalized in {"STR", "STRING"}:
         return "STRING"
     return None
 
 
 def _matches_primitive_type(value: Any, expected_type: str) -> bool:
     if expected_type == "INT":
         return _is_int_literal(value)
     if expected_type == "FLOAT":
         return _is_float_literal(value)
     if expected_type == "BOOLEAN":
         return _is_boolean_literal(value)
     if expected_type == "STRING":
         return isinstance(value, str)
     return True
 
 
 def _is_int_literal(value: Any) -> bool:
     if isinstance(value, bool):
         return False
     if isinstance(value, int):
         return True
     if isinstance(value, str):
         text = value.strip()
         if not text:
             return False
         try:
             int(text, 10)
         except ValueError:
             return False
         return True
     return False
 
 
 def _is_float_literal(value: Any) -> bool:
     if isinstance(value, bool):
         return False
     if isinstance(value, (int, float)):
         return True
     if isinstance(value, str):
         try:
             float(value)
         except ValueError:
             return False
         return True
     return False
 
 
 def _is_boolean_literal(value: Any) -> bool:
     if isinstance(value, bool):
         return True
     if isinstance(value, str):
         return value.strip().lower() in {"true", "false"}
     return False
 
 
 def _is_api_link(value: Any) -> bool:
-    return (
-        isinstance(value, (list, tuple))
-        and len(value) == 2
-        and isinstance(value[0], str)
-        and isinstance(value[1], int)
-    )
+    return is_canonical_api_link(value)
 
 
 def _truncate(value: Any, n: int = 120) -> str:
     text = repr(value)
     if len(text) <= n:
         return text
     return text[: max(0, n - 3)] + "..."
 
 
 _NO_MATCH = object()
 
 
 def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
     if value in choices:
         return _NO_MATCH
     if not isinstance(value, str):
         return _NO_MATCH
     normalized_value = _portable_choice_key(value)
     basename_value = normalized_value.rsplit("/", 1)[-1]
     matches = [
         choice
         for choice in choices
         if isinstance(choice, str)
         and (
             _portable_choice_key(choice) == normalized_value
             or _portable_choice_key(choice).rsplit("/", 1)[-1] == basename_value
         )
     ]
     return matches[0] if len(matches) == 1 else _NO_MATCH
 
 
 def _portable_choice_key(value: str) -> str:
     return value.replace("\\", "/").strip()
 
 
 def _issue_suppressed(class_type: str, code: str) -> bool:
     if class_type not in SCHEMA_VALIDATION_SKIP_CLASSES:
         return False
     return code == "unknown_input" or code.startswith("value_")
 
 
 def _is_dynamic_file_choice(class_type: str, input_name: str) -> bool:
     """Return whether a Comfy enum is a runtime file picker, not a semantic enum.
 
     Object-info choices for these inputs reflect files present in the active
     input directory when object_info was fetched. Task scratchpads often copy
     images/videos immediately before queueing, so treating stale file-picker
     choices as hard schema errors rejects valid runs. Model/checkpoint enums are
     intentionally not listed here.
     """
 
     return (class_type, input_name) in {
         ("LoadImage", "image"),
         ("LoadVideo", "video"),
         ("LoadVideo", "file"),
         ("VHS_LoadVideo", "video"),
         ("VHS_LoadVideo", "file"),
     }
 
 
 def _schema_accepts_dict(spec: Any) -> bool:
     typ = getattr(spec, "type", None)
     if typ is None:
         return False
     return str(typ).strip().upper() in {"DICT", "JSON", "*"}
 
 
 def advisory_validation_for_precedent(
     issues: list[Any],
     *,
     route: str | None = None,
 ) -> list[dict[str, Any]]:
     """Build advisory task-satisfaction entries from validation issues.
 
     When *route* is precedent_research, every validation issue is recast
     as an advisory task-satisfaction entry with satisfaction="advisory"
     so the precedent-adaptation path can surface schema concerns without
     blocking Apply or Queue.
 
     When *route* is anything else, returns an empty list (issues remain
diff --git a/vibecomfy/workflow.py b/vibecomfy/workflow.py
index 07e24332..6731c6e2 100644
--- a/vibecomfy/workflow.py
+++ b/vibecomfy/workflow.py
@@ -1,91 +1,92 @@
 from __future__ import annotations
 
 import copy
 import dataclasses
 from dataclasses import dataclass, field, replace
 import warnings
 from typing import TYPE_CHECKING, Any
 
 from vibecomfy._compile import _resolve as helper_resolve
 from vibecomfy._compile import _widgets as widget_aliases
 from vibecomfy._compile import _helpers as workflow_helpers
+from vibecomfy._compile._graph import is_canonical_api_link
 from vibecomfy.errors import VibeComfyError
 from vibecomfy.handles import Handle
 
 if TYPE_CHECKING:
     from vibecomfy.schema.provider import SchemaProvider
 
 
 # ComfyUI-specific validation policy lives in the neutral contracts layer.
 # Re-exported here so existing `from vibecomfy.workflow import OPAQUE_COMPONENT_CLASS_RE`
 # imports keep working.
 from vibecomfy.contracts.validation import (  # noqa: E402
     OPAQUE_COMPONENT_CLASS_RE,
     comfyui_node_issue_specs,
 )
 
 # WorkflowSummary is the typed contract for LLM-generated summaries stored
 # under ``workflow.metadata['summary']``.  Re-exported so consumers can
 # import from ``vibecomfy.workflow`` without reaching into contracts.
 from vibecomfy.contracts.summary import WorkflowSummary  # noqa: E402
 
 
 # Stored-envelope format version. The IR is the schema source: writers stamp
 # this via ``VibeWorkflow.to_envelope()`` rather than a script-local constant.
 FORMAT_VERSION = "1.0"
 VIBECOMFY_FORMAT_VERSION = FORMAT_VERSION
 
 
 def _to_plain(obj: Any) -> Any:
     """Lossless walk of public dataclass fields (skip private ``_`` names)."""
     if dataclasses.is_dataclass(obj):
         result: dict[str, Any] = {}
         for field_info in dataclasses.fields(obj):
             if field_info.name.startswith("_"):
                 continue
             result[field_info.name] = _to_plain(getattr(obj, field_info.name))
         return result
     if isinstance(obj, dict):
         return {str(key): _to_plain(value) for key, value in obj.items()}
     if isinstance(obj, (list, tuple)):
         return [_to_plain(value) for value in obj]
     return obj
 
 
 @dataclass(slots=True)
 class WorkflowSource:
     id: str
     path: str | None = None
     source_type: str = "unknown"
     provenance: dict[str, Any] = field(default_factory=dict)
 
 
 @dataclass(slots=True)
 class WorkflowRequirements:
     models: list[str] = field(default_factory=list)
     custom_nodes: list[str] = field(default_factory=list)
     missing_models: list[str] = field(default_factory=list)
     missing_nodes: list[str] = field(default_factory=list)
     unsupported: list[str] = field(default_factory=list)
 
 
 @dataclass(slots=True)
 class RawWidgetPayload:
     values: Any
     shape: str
     source: str
     has_dict_rows: bool
     length: int
 
 
 @dataclass(slots=True)
 class VibeNode:
     id: str
     class_type: str
     pack: str | None = None
     inputs: dict[str, Any] = field(default_factory=dict)
     widgets: dict[str, Any] = field(default_factory=dict)
     metadata: dict[str, Any] = field(default_factory=dict)
     uid: str = ""
     raw_widgets: RawWidgetPayload | None = None
     mode: int = 0
@@ -181,160 +182,161 @@ class VibeWorkflow:
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
         if token is not None:
             reset_workflow(token)
             self._workflow_context_token = None
 
     def confirm_node(self, node_id: str) -> "VibeWorkflow":
         """Promote ``untrusted_source`` provenance on ``node_id`` → ``user_confirmed``.
 
         Idempotent on already-trusted nodes. Raises ``KeyError`` if ``node_id``
         is unknown so callers cannot silently confirm a non-existent node.
         """
         from vibecomfy.security import provenance as _prov
 
         node = self.nodes[node_id]
         _prov.confirm(node)
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
+        _raise_embedded_api_links(self, surface="envelope serialization")
         plain = _to_plain(self)
         plain["vibecomfy_format_version"] = FORMAT_VERSION
         return plain
 
     @classmethod
     def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
         """Fail-closed decoder for a serialized vibe envelope.
 
         Rich ``nodes`` + ``edges`` are the only structural authority.
         ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
         no partial graph is returned. Implementation is the existing ingest
         decoder — this method does not relax it.
         """
         from vibecomfy.ingest.normalize import _decode_serialized_vibe
 
         return _decode_serialized_vibe(raw)
 
     def clone(self) -> "VibeWorkflow":
         return self.copy()
 
     def finalize_metadata(self) -> "VibeWorkflow":
         from vibecomfy.metadata import OUTPUT_NODE_NAMES, _infer_requirements, _register_common_inputs
 
         manual_inputs = {
             name: replace(vibe_input)
             for name, vibe_input in self.inputs.items()
             if name in self._manual_input_names and self._input_target_exists(vibe_input)
         }
         self._manual_input_names.intersection_update(manual_inputs)
         self.inputs.clear()
         self.outputs.clear()
         for node_id, node in self.nodes.items():
             _register_common_inputs(self, node_id, node)
             if node.class_type in OUTPUT_NODE_NAMES:
                 self.outputs.append(VibeOutput(node_id=node_id, output_type=node.class_type))
         self.inputs.update(manual_inputs)
         self.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
         self.requirements = _infer_requirements(self)
         return self
 
     def finalize(
         self,
         public_inputs: dict[str, Any],
         *,
         metadata: dict[str, Any] | None = None,
         output_node: Any = None,
         output_kind: str | None = None,
         **bind_kwargs: Any,
     ) -> "VibeWorkflow":
         """Finalize ready-template public inputs and output binding.
 
         ``metadata`` is optional for the v2.5 method form; when omitted, the
         workflow's current metadata is used. The legacy free function remains
         available in ``vibecomfy.templates.finalize``.
         """
         from vibecomfy.templates import _finalize_impl
 
         return _finalize_impl(
             self,
             public_inputs,
             dict(self.metadata if metadata is None else metadata),
             output_node=output_node,
             output_kind=output_kind,
             **bind_kwargs,
         )
 
     def register_input(
         self,
         name: str,
         node_id: str,
         field: str,
         value: Any = None,
         *,
         type: str | None = None,
         default: Any = None,
         required: bool = False,
         range: Any = None,
         aliases: list[str] | tuple[str, ...] | None = None,
         media_semantics: str | None = None,
         media: str | None = None,
@@ -617,198 +619,210 @@ class VibeWorkflow:
         if output_type is None or input_type is None:
             return
         from vibecomfy.schema import socket_types_compatible
 
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
+        embedded_links = _embedded_api_link_details(self)
+        for detail in embedded_links:
+            issues.append(
+                ValidationIssue(
+                    "embedded_api_link",
+                    _embedded_api_link_message(detail, surface="validation"),
+                    severity="error",
+                    detail=detail,
+                )
+            )
         api: dict[str, Any] | None = None
-        try:
-            api = self.compile(backend="api")
-        except Exception as exc:
-            detail: dict[str, Any] = {}
-            if isinstance(exc, WorkflowCompileError):
-                detail = {"compile_code": exc.code, **exc.detail}
-            issues.append(ValidationIssue("api_compile_failed", str(exc), severity="error", detail=detail))
+        if not embedded_links:
+            try:
+                api = self.compile(backend="api")
+            except Exception as exc:
+                detail: dict[str, Any] = {}
+                if isinstance(exc, WorkflowCompileError):
+                    detail = {"compile_code": exc.code, **exc.detail}
+                issues.append(ValidationIssue("api_compile_failed", str(exc), severity="error", detail=detail))
         if schema_provider is not None:
             from vibecomfy.schema.validate import validate_against_schema, validate_api_link_shapes
 
             issues.extend(validate_against_schema(self, schema_provider))
             if api is not None:
                 issues.extend(validate_api_link_shapes(api, schema_provider))
         return ValidationReport(ok=not any(issue.severity == "error" for issue in issues), issues=issues)
 
     def runtime_nodes(self) -> dict[str, VibeNode]:
         return workflow_helpers.helper_stripped_nodes(self.nodes)
 
     def runtime_class_types(self) -> list[str]:
         return workflow_helpers.helper_stripped_class_types(self.nodes)
 
     def helper_diagnostics(self) -> list[ValidationIssue]:
         return [
             ValidationIssue(
                 diagnostic.code,
                 diagnostic.message,
                 severity=diagnostic.severity,
                 detail={
                     **diagnostic.detail,
                     "node_id": diagnostic.node_id,
                     "class_type": diagnostic.class_type,
                 },
             )
             for diagnostic in workflow_helpers.collect_helper_diagnostics(self.nodes, self.edges)
         ]
 
     def compile(self, backend: str = "api") -> dict[str, Any]:
+        _raise_embedded_api_links(self, surface=f"{backend} compilation")
         if backend == "graphbuilder":
             return self._compile_graphbuilder()
         if backend != "api":
             raise ValueError(f"Unknown compile backend: {backend}")
         dropped_ids, bypassed_ids = _compute_dropped_bypassed_ids(self.nodes)
         resolved_edges = _resolve_bypass_edges(self.edges, dropped_ids, bypassed_ids)
         broadcast_sources = workflow_helpers.collect_broadcast_sources(self.nodes, resolved_edges)
         api: dict[str, Any] = {}
         for node_id, node in self.nodes.items():
             if _is_compile_stripped_node(node):
                 continue
             if str(node_id) in dropped_ids:
                 continue
             inputs = _rewrite_broadcast_links(_compile_node_inputs(node), self.nodes, broadcast_sources)
             inputs.update(_compile_intent_runtime_inputs(node))
             api[str(node_id)] = {"class_type": node.class_type, "inputs": inputs}
         edge_inputs = _compile_resolved_edge_inputs(
             self.nodes, resolved_edges, broadcast_sources, dropped_ids=dropped_ids
         )
         for target_node_id, inputs in edge_inputs.items():
             if target_node_id not in api:
                 continue
             api[target_node_id]["inputs"].update(inputs)
         return api
 
     def export_to_json(self, *, format: str = "api") -> dict[str, Any]:
         if format != "api":
             raise ValueError(f"Unsupported workflow JSON export format: {format!r}")
         return self.compile("api")
 
     def id_map(self) -> dict[str, str]:
         """Map variable name (as used in build()) to assigned node id."""
         return dict(self._id_map)
 
     def _set_id_map(self, mapping: dict[str, Any]) -> "VibeWorkflow":
         """Store codemod-emitted variable-name mappings and return ``self``."""
         resolved: dict[str, str] = {}
         metadata_id_map = self.metadata.get("id_map")
         metadata_id_map = metadata_id_map if isinstance(metadata_id_map, dict) else {}
         for name, node_id in mapping.items():
             key = str(name)
             value = str(node_id)
             if value in self.nodes:
                 resolved[key] = value
                 continue
             metadata_value = metadata_id_map.get(value)
             resolved[key] = str(metadata_value) if metadata_value is not None else value
         self._id_map = resolved
         return self
 
     def lookup_id(self, node_id: str) -> dict[str, Any]:
         """Return a rich info dict for the node identified by *node_id*.
 
         Raises ``KeyError`` when *node_id* is absent from the workflow —
         callers asked for a concrete node id.
         """
         nid = str(node_id)
         if nid not in self.nodes:
             raise KeyError(nid)
 
         node = self.nodes[nid]
 
         # --- variable_name: reverse lookup from _id_map --------------------
         variable_name: str | None = None
         for name, mapped_id in self._id_map.items():
             if mapped_id == nid:
                 variable_name = name
                 break
 
         # --- source_path ---------------------------------------------------
         provenance = node.metadata.get("provenance")
         source_path: str | None = None
         if isinstance(provenance, dict):
             sp = provenance.get("source_path")
             if isinstance(sp, str) and sp:
                 source_path = sp
         if source_path is None:
             source_path = self.source.path
 
         # --- source_line (SD4: null for generated-template nodes) ----------
@@ -965,160 +979,225 @@ class _NodeBuilder:
                     node_id=self.node.id,
                     output_slot=index,
                     output_type=_node_output_type(self.node, index),
                     name=str(name) if isinstance(name, str) and name else None,
                 )
             return
         yield self.out(0)
 
 
 def _node_output_type(node: VibeNode | None, output_slot: int | str) -> str | None:
     if node is None:
         return None
     output_types = node.metadata.get("output_types")
     try:
         index = int(str(output_slot))
     except (TypeError, ValueError):
         index = None
     if isinstance(output_types, (list, tuple)) and index is not None and 0 <= index < len(output_types):
         value = output_types[index]
         return str(value) if value is not None else None
     schema = _schema_for_node(node)
     outputs = getattr(schema, "outputs", None) or []
     if index is not None and 0 <= index < len(outputs):
         value = getattr(outputs[index], "type", None)
         return str(value) if value is not None else None
     for output in outputs:
         if getattr(output, "name", None) == output_slot:
             value = getattr(output, "type", None)
             return str(value) if value is not None else None
     return None
 
 
 def _node_output_names(node: VibeNode) -> list[str | None]:
     output_names = node.metadata.get("output_names")
     if isinstance(output_names, (list, tuple)) and output_names:
         return [str(name) if name is not None else None for name in output_names]
     schema = _schema_for_node(node)
     outputs = getattr(schema, "outputs", None) or []
     return [
         str(getattr(output, "name", "")) if getattr(output, "name", None) else None
         for output in outputs
     ]
 
 
 def _node_input_type(node: VibeNode | None, input_name: str) -> str | None:
     if node is None:
         return None
     schema = _schema_for_node(node)
     inputs = getattr(schema, "inputs", {}) or {}
     spec = inputs.get(input_name)
     if spec is None:
         return None
     value = getattr(spec, "type", None)
     return str(value) if value is not None else None
 
 
 def _schema_for_node(node: VibeNode) -> object | None:
     schema = node.metadata.get("schema")
     if schema is not None:
         return schema
     try:
         from vibecomfy.schema import get_authoring_schema_provider
 
         return get_authoring_schema_provider().get_schema(node.class_type)
     except Exception:
         return None
 
 
 def _compile_node_inputs(node: VibeNode) -> dict[str, Any]:
     inputs = dict(node.widgets)
     inputs.update(node.inputs)
     _apply_positional_widget_aliases(inputs, node)
     _drop_unused_positional_aliases(inputs)
     return {
         key: value
         for key, value in inputs.items()
         if not _is_ui_only_prompt_input(key, value)
     }
 
 
+def _embedded_api_link_details(workflow: VibeWorkflow) -> list[dict[str, Any]]:
+    """Describe canonical API links illegally embedded in IR node inputs."""
+    details: list[dict[str, Any]] = []
+    edges_by_target: dict[tuple[str, str], list[list[Any]]] = {}
+    for edge in workflow.edges:
+        key = (str(edge.to_node), str(edge.to_input))
+        try:
+            output_slot: Any = int(edge.from_output)
+        except (TypeError, ValueError):
+            output_slot = str(edge.from_output)
+        edges_by_target.setdefault(key, []).append([str(edge.from_node), output_slot])
+
+    for node_id, node in workflow.nodes.items():
+        for input_name, value in node.inputs.items():
+            if not is_canonical_api_link(value):
+                continue
+            embedded_source = [str(value[0]), int(value[1])]
+            edge_sources = edges_by_target.get((str(node_id), str(input_name)), [])
+            if not edge_sources:
+                collision = "none"
+            elif all(source == embedded_source for source in edge_sources):
+                collision = "identical"
+            else:
+                collision = "conflicting"
+            details.append(
+                {
+                    "node_id": str(node_id),
+                    "input_name": str(input_name),
+                    "embedded_source": embedded_source,
+                    "edge_sources": edge_sources,
+                    "edge_collision": collision,
+                }
+            )
+    return details
+
+
+def _embedded_api_link_message(detail: dict[str, Any], *, surface: str) -> str:
+    collision = detail["edge_collision"]
+    collision_text = ""
+    if collision != "none":
+        collision_text = f"; the socket also has {collision} VibeEdge connectivity"
+    return (
+        f"{surface} rejected node {detail['node_id']!r} input "
+        f"{detail['input_name']!r}: embedded Comfy API link "
+        f"{detail['embedded_source']!r}{collision_text}. "
+        "VibeEdge is the sole IR connectivity authority."
+    )
+
+
+def _raise_embedded_api_links(workflow: VibeWorkflow, *, surface: str) -> None:
+    details = _embedded_api_link_details(workflow)
+    if not details:
+        return
+    detail = details[0]
+    raise WorkflowCompileError(
+        "embedded_api_link",
+        _embedded_api_link_message(detail, surface=surface),
+        detail=detail,
+        next_action=(
+            "Normalize raw workflows with from_api()/from_ui(), or replace the embedded "
+            "pair with a VibeEdge before continuing."
+        ),
+    )
+
+
 def _normalize_input_aliases(aliases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
     if aliases is None:
         return ()
     return tuple(str(alias) for alias in aliases)
 
 
 def _format_available_names(names: Any) -> str:
     values = sorted(str(name) for name in names)
     return ", ".join(repr(value) for value in values) if values else "<none>"
 
 
 def _is_ui_only_prompt_input(key: str, value: Any) -> bool:
     if value is None:
         return True
     if key == "control_after_generate":
         return True
     if key == "add_noise_to_samples" and value == "":
         return True
     if key in {"videopreview", "preview", "preview_image"} and isinstance(value, dict):
         return True
     return False
 
 
 def _is_ui_only_node(node: VibeNode) -> bool:
     return workflow_helpers.is_helper_class_type(node.class_type)
 
 
 def _is_compile_stripped_node(node: VibeNode) -> bool:
     if _is_ui_only_node(node):
         return True
     if not _is_intent_node_class_type(node.class_type):
         return False
     return not _is_runtime_backed_code_intent_node(node)
 
 
 def _is_intent_node_class_type(class_type: str) -> bool:
     try:
         from vibecomfy.contracts.intent_nodes import is_intent_class_type
 
         return is_intent_class_type(class_type)
     except Exception:
         return class_type in {"vibecomfy.code", "vibecomfy.loop"}
 
 
 def _is_runtime_backed_code_intent_node(node: VibeNode) -> bool:
     try:
         from vibecomfy.contracts.intent_nodes import (
             KIND_TO_CLASS_TYPE,
             intent_node_payload_from_metadata,
             validate_runtime_code_contract,
         )
     except Exception:
         return False
     if node.class_type != KIND_TO_CLASS_TYPE["code"]:
         return False
     payload = intent_node_payload_from_metadata(node.metadata)
     runtime_result = validate_runtime_code_contract(
         class_type=node.class_type,
         payload=payload,
         require_runtime=True,
     )
     return runtime_result.ok
 
 
 def _compile_intent_runtime_inputs(node: VibeNode) -> dict[str, Any]:
     try:
         from vibecomfy.contracts.intent_nodes import (
             KIND_TO_CLASS_TYPE,
             intent_node_payload_from_metadata,
             validate_intent_node_contract,
             validate_runtime_code_contract,
         )
     except Exception:
         return {}
     if node.class_type != KIND_TO_CLASS_TYPE["code"]:
         return {}
     payload = intent_node_payload_from_metadata(node.metadata)
     runtime_result = validate_runtime_code_contract(
         class_type=node.class_type,
         payload=payload,
@@ -1376,111 +1455,107 @@ def _resolve_compiled_source_ref(
                 detail={
                     "source_node_id": str(source_node_id),
                     "source_output": str(source_output),
                     "target_node_id": target_node_id,
                     "target_input": target_input,
                 },
                 next_action="Use an explicit numeric output slot before compiling.",
             ) from exc
         return [str(source_node_id), output_slot]
 
     if source_node.class_type in {"Note", "MarkdownNote"}:
         raise WorkflowCompileError(
             "helper_edge_unresolved",
             (
                 f"{source_node.class_type} node {source_node_id!r} is compile-stripped "
                 f"but feeds runtime input {target_node_id!r}.{target_input!r}."
             ),
             detail={
                 "helper_node_id": str(source_node_id),
                 "class_type": source_node.class_type,
                 "target_node_id": target_node_id,
                 "target_input": target_input,
             },
             next_action="Remove the UI-only helper edge or reconnect the input to a runtime node.",
         )
 
     if source_node_id in visited:
         raise WorkflowCompileError(
             "helper_edge_cycle",
             (
                 f"Helper edge cycle while resolving {source_node_id!r} for "
                 f"{target_node_id!r}.{target_input!r}."
             ),
             detail={
                 "helper_node_id": str(source_node_id),
                 "target_node_id": target_node_id,
                 "target_input": target_input,
                 "visited": sorted(visited),
             },
             next_action="Break the SetNode/GetNode broadcast cycle before compiling.",
         )
     visited.add(source_node_id)
 
     name = workflow_helpers.broadcast_name(source_node)
     if not name or name not in broadcast_sources:
         raise WorkflowCompileError(
             "helper_edge_unresolved",
             (
                 f"{source_node.class_type} node {source_node_id!r} feeding "
                 f"{target_node_id!r}.{target_input!r} has no resolved broadcast source."
             ),
             detail={
                 "helper_node_id": str(source_node_id),
                 "class_type": source_node.class_type,
                 "broadcast": name,
                 "target_node_id": target_node_id,
                 "target_input": target_input,
             },
             next_action="Add a matching SetNode source or reconnect the input to a runtime node.",
         )
     source = broadcast_sources[name]
     return _resolve_compiled_source_ref(
         str(source[0]),
         source[1],
         nodes,
         broadcast_sources,
         visited=visited,
         target_node_id=target_node_id,
         target_input=target_input,
     )
 
 
 def _resolve_link_value(
     value: Any,
     nodes: dict[str, VibeNode],
     broadcast_sources: dict[str, list[Any]],
 ) -> Any:
     return helper_resolve.resolve_compile_link_value(value, nodes, broadcast_sources)
 
 
-def _is_api_link(value: Any) -> bool:
-    return workflow_helpers.is_api_link(value)
-
-
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

exec
/bin/zsh -lc "rg -n \"is_canonical_api_link|_embedded_api_link|from_dict|to_dict|from_envelope|def compile|def validate\" vibecomfy/workflow.py vibecomfy/schema/validate.py vibecomfy/porting/emit/ui.py vibecomfy/ingest/normalize.py && nl -ba vibecomfy/workflow.py | sed -n '1,430p' && nl -ba vibecomfy/workflow.py | sed -n '780,920p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/workflow.py:12:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/workflow.py:262:        _raise_embedded_api_links(self, surface="envelope serialization")
vibecomfy/workflow.py:268:    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
vibecomfy/workflow.py:678:    def validate(self, schema_provider: SchemaProvider | None = None) -> ValidationReport:
vibecomfy/workflow.py:699:        embedded_links = _embedded_api_link_details(self)
vibecomfy/workflow.py:704:                    _embedded_api_link_message(detail, surface="validation"),
vibecomfy/workflow.py:747:    def compile(self, backend: str = "api") -> dict[str, Any]:
vibecomfy/workflow.py:748:        _raise_embedded_api_links(self, surface=f"{backend} compilation")
vibecomfy/workflow.py:926:def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
vibecomfy/workflow.py:929:    Module-level alias of :meth:`VibeWorkflow.from_envelope`.
vibecomfy/workflow.py:931:    return VibeWorkflow.from_envelope(raw)
vibecomfy/workflow.py:1059:def _embedded_api_link_details(workflow: VibeWorkflow) -> list[dict[str, Any]]:
vibecomfy/workflow.py:1073:            if not is_canonical_api_link(value):
vibecomfy/workflow.py:1095:def _embedded_api_link_message(detail: dict[str, Any], *, surface: str) -> str:
vibecomfy/workflow.py:1108:def _raise_embedded_api_links(workflow: VibeWorkflow, *, surface: str) -> None:
vibecomfy/workflow.py:1109:    details = _embedded_api_link_details(workflow)
vibecomfy/workflow.py:1115:        _embedded_api_link_message(detail, surface=surface),
vibecomfy/schema/validate.py:7:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/schema/validate.py:100:def validate_against_schema(workflow: VibeWorkflow, provider: SchemaProvider) -> list[ValidationIssue]:
vibecomfy/schema/validate.py:114:def validate_api_against_schema(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
vibecomfy/schema/validate.py:405:def validate_api_link_shapes(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
vibecomfy/schema/validate.py:717:    return is_canonical_api_link(value)
vibecomfy/ingest/normalize.py:9:from vibecomfy._compile._graph import is_canonical_api_link
vibecomfy/ingest/normalize.py:35:    _embedded_api_link_details,
vibecomfy/ingest/normalize.py:36:    _embedded_api_link_message,
vibecomfy/ingest/normalize.py:46:    Callers that know their input should use :func:`from_envelope`,
vibecomfy/ingest/normalize.py:96:        workflow = VibeWorkflow.from_envelope(raw)
vibecomfy/ingest/normalize.py:435:    """Implementation of :meth:`VibeWorkflow.from_envelope`.
vibecomfy/ingest/normalize.py:437:    Do not call this from new code — use ``VibeWorkflow.from_envelope`` (or
vibecomfy/ingest/normalize.py:438:    the module-level ``from_envelope``).  The decoder is fail-closed and
vibecomfy/ingest/normalize.py:638:    embedded_links = _embedded_api_link_details(workflow)
vibecomfy/ingest/normalize.py:642:            + _embedded_api_link_message(
vibecomfy/ingest/normalize.py:743:def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
vibecomfy/ingest/normalize.py:748:    :meth:`VibeWorkflow.from_envelope`.
vibecomfy/ingest/normalize.py:750:    return VibeWorkflow.from_envelope(raw)
vibecomfy/ingest/normalize.py:818:        return from_envelope(raw)
vibecomfy/ingest/normalize.py:868:            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
vibecomfy/ingest/normalize.py:964:            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
     1	from __future__ import annotations
     2	
     3	import copy
     4	import dataclasses
     5	from dataclasses import dataclass, field, replace
     6	import warnings
     7	from typing import TYPE_CHECKING, Any
     8	
     9	from vibecomfy._compile import _resolve as helper_resolve
    10	from vibecomfy._compile import _widgets as widget_aliases
    11	from vibecomfy._compile import _helpers as workflow_helpers
    12	from vibecomfy._compile._graph import is_canonical_api_link
    13	from vibecomfy.errors import VibeComfyError
    14	from vibecomfy.handles import Handle
    15	
    16	if TYPE_CHECKING:
    17	    from vibecomfy.schema.provider import SchemaProvider
    18	
    19	
    20	# ComfyUI-specific validation policy lives in the neutral contracts layer.
    21	# Re-exported here so existing `from vibecomfy.workflow import OPAQUE_COMPONENT_CLASS_RE`
    22	# imports keep working.
    23	from vibecomfy.contracts.validation import (  # noqa: E402
    24	    OPAQUE_COMPONENT_CLASS_RE,
    25	    comfyui_node_issue_specs,
    26	)
    27	
    28	# WorkflowSummary is the typed contract for LLM-generated summaries stored
    29	# under ``workflow.metadata['summary']``.  Re-exported so consumers can
    30	# import from ``vibecomfy.workflow`` without reaching into contracts.
    31	from vibecomfy.contracts.summary import WorkflowSummary  # noqa: E402
    32	
    33	
    34	# Stored-envelope format version. The IR is the schema source: writers stamp
    35	# this via ``VibeWorkflow.to_envelope()`` rather than a script-local constant.
    36	FORMAT_VERSION = "1.0"
    37	VIBECOMFY_FORMAT_VERSION = FORMAT_VERSION
    38	
    39	
    40	def _to_plain(obj: Any) -> Any:
    41	    """Lossless walk of public dataclass fields (skip private ``_`` names)."""
    42	    if dataclasses.is_dataclass(obj):
    43	        result: dict[str, Any] = {}
    44	        for field_info in dataclasses.fields(obj):
    45	            if field_info.name.startswith("_"):
    46	                continue
    47	            result[field_info.name] = _to_plain(getattr(obj, field_info.name))
    48	        return result
    49	    if isinstance(obj, dict):
    50	        return {str(key): _to_plain(value) for key, value in obj.items()}
    51	    if isinstance(obj, (list, tuple)):
    52	        return [_to_plain(value) for value in obj]
    53	    return obj
    54	
    55	
    56	@dataclass(slots=True)
    57	class WorkflowSource:
    58	    id: str
    59	    path: str | None = None
    60	    source_type: str = "unknown"
    61	    provenance: dict[str, Any] = field(default_factory=dict)
    62	
    63	
    64	@dataclass(slots=True)
    65	class WorkflowRequirements:
    66	    models: list[str] = field(default_factory=list)
    67	    custom_nodes: list[str] = field(default_factory=list)
    68	    missing_models: list[str] = field(default_factory=list)
    69	    missing_nodes: list[str] = field(default_factory=list)
    70	    unsupported: list[str] = field(default_factory=list)
    71	
    72	
    73	@dataclass(slots=True)
    74	class RawWidgetPayload:
    75	    values: Any
    76	    shape: str
    77	    source: str
    78	    has_dict_rows: bool
    79	    length: int
    80	
    81	
    82	@dataclass(slots=True)
    83	class VibeNode:
    84	    id: str
    85	    class_type: str
    86	    pack: str | None = None
    87	    inputs: dict[str, Any] = field(default_factory=dict)
    88	    widgets: dict[str, Any] = field(default_factory=dict)
    89	    metadata: dict[str, Any] = field(default_factory=dict)
    90	    uid: str = ""
    91	    raw_widgets: RawWidgetPayload | None = None
    92	    mode: int = 0
    93	
    94	    @property
    95	    def provenance(self) -> str:
    96	        """Read-through to the S4 provenance tag; fail-closed on missing/None."""
    97	        from vibecomfy.security import provenance as _prov
    98	
    99	        return _prov.read(self)
   100	
   101	
   102	@dataclass(slots=True)
   103	class VibeEdge:
   104	    from_node: str
   105	    from_output: str
   106	    to_node: str
   107	    to_input: str
   108	
   109	
   110	@dataclass(slots=True)
   111	class VibeInput:
   112	    name: str
   113	    node_id: str
   114	    field: str
   115	    value: Any = None
   116	    type: str | None = None
   117	    default: Any = None
   118	    required: bool = False
   119	    range: Any = None
   120	    aliases: tuple[str, ...] = field(default_factory=tuple)
   121	    media_semantics: str | None = None
   122	
   123	    @property
   124	    def media(self) -> str | None:
   125	        return self.media_semantics
   126	
   127	    @media.setter
   128	    def media(self, value: str | None) -> None:
   129	        self.media_semantics = value
   130	
   131	
   132	@dataclass(slots=True)
   133	class VibeOutput:
   134	    node_id: str
   135	    output_type: str
   136	    name: str | None = None
   137	    artifact_kind: str | None = None
   138	    mime_type: str | None = None
   139	    filename_prefix: str | None = None
   140	    expected_cardinality: str | int | None = None
   141	
   142	
   143	@dataclass(slots=True)
   144	class ValidationIssue:
   145	    code: str
   146	    message: str
   147	    severity: str = "error"
   148	    detail: dict[str, Any] = field(default_factory=dict)
   149	
   150	
   151	@dataclass(slots=True)
   152	class ValidationReport:
   153	    ok: bool
   154	    issues: list[ValidationIssue] = field(default_factory=list)
   155	
   156	
   157	class WorkflowCompileError(VibeComfyError):
   158	    """Compile-time graph assembly failure with a stable machine-readable code."""
   159	
   160	    def __init__(
   161	        self,
   162	        code: str,
   163	        message: str,
   164	        *,
   165	        detail: dict[str, Any] | None = None,
   166	        next_action: str | None = None,
   167	    ) -> None:
   168	        self.code = code
   169	        self.detail = detail or {}
   170	        super().__init__(f"{code}: {message}", next_action=next_action)
   171	
   172	
   173	@dataclass
   174	class VibeWorkflow:
   175	    id: str
   176	    source: WorkflowSource
   177	    nodes: dict[str, VibeNode] = field(default_factory=dict)
   178	    edges: list[VibeEdge] = field(default_factory=list)
   179	    inputs: dict[str, VibeInput] = field(default_factory=dict)
   180	    outputs: list[VibeOutput] = field(default_factory=list)
   181	    requirements: WorkflowRequirements = field(default_factory=WorkflowRequirements)
   182	    metadata: dict[str, Any] = field(default_factory=dict)
   183	    strict_types: bool = False
   184	    groups: list[dict[str, Any]] = field(default_factory=list)
   185	    _id_map: dict[str, str] = field(default_factory=dict, init=False, repr=False)
   186	    _manual_input_names: set[str] = field(default_factory=set, init=False, repr=False)
   187	    _uid_counter: int = field(default=0, init=False, repr=False)
   188	
   189	    def __enter__(self) -> "VibeWorkflow":
   190	        from vibecomfy.workflow_context import active_workflow, bind_workflow
   191	
   192	        # If ``new_workflow()`` already eagerly bound this workflow (the post-
   193	        # revert default for emitted templates), reuse that binding rather than
   194	        # raising — the ``with`` form is purely scoping sugar in that case.
   195	        if (
   196	            getattr(self, "_workflow_context_token", None) is not None
   197	            and active_workflow() is self
   198	        ):
   199	            return self
   200	        if getattr(self, "_workflow_context_token", None) is not None:
   201	            raise RuntimeError(
   202	                "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
   203	                "block is still active."
   204	            )
   205	        self._workflow_context_token = bind_workflow(self)
   206	        return self
   207	
   208	    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
   209	        from vibecomfy.workflow_context import reset_workflow
   210	
   211	        token = getattr(self, "_workflow_context_token", None)
   212	        if token is not None:
   213	            reset_workflow(token)
   214	            self._workflow_context_token = None
   215	
   216	    def confirm_node(self, node_id: str) -> "VibeWorkflow":
   217	        """Promote ``untrusted_source`` provenance on ``node_id`` → ``user_confirmed``.
   218	
   219	        Idempotent on already-trusted nodes. Raises ``KeyError`` if ``node_id``
   220	        is unknown so callers cannot silently confirm a non-existent node.
   221	        """
   222	        from vibecomfy.security import provenance as _prov
   223	
   224	        node = self.nodes[node_id]
   225	        _prov.confirm(node)
   226	        return self
   227	
   228	    def set_prompt(self, value: str) -> "VibeWorkflow":
   229	        return self.set_input("prompt", value)
   230	
   231	    def set_seed(self, value: int) -> "VibeWorkflow":
   232	        return self.set_input("seed", int(value))
   233	
   234	    def set_steps(self, value: int) -> "VibeWorkflow":
   235	        return self.set_input("steps", int(value))
   236	
   237	    def set_model(self, value: str) -> "VibeWorkflow":
   238	        return self.set_input("model", value)
   239	
   240	    def copy(self) -> "VibeWorkflow":
   241	        """Derived, complete deep copy.
   242	
   243	        The dataclass walk (``copy.deepcopy``) copies every public field —
   244	        including ``groups`` and per-node ``mode`` — plus the private
   245	        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``),
   246	        so adding a field to the dataclass needs no ``copy()`` edit.  The
   247	        clone is not bound to any workflow context.
   248	        """
   249	        cloned = copy.deepcopy(self)
   250	        if hasattr(cloned, "_workflow_context_token"):
   251	            del cloned._workflow_context_token
   252	        return cloned
   253	
   254	    def to_envelope(self) -> dict[str, Any]:
   255	        """Serialize this IR as the stored vibe envelope.
   256	
   257	        Public dataclass fields plus ``vibecomfy_format_version``. No
   258	        ``compiled_api`` — ``compile("api")`` is a function, not stored data.
   259	        Transport stamps such as ``workflow_id`` are applied by callers after
   260	        this, not here.
   261	        """
   262	        _raise_embedded_api_links(self, surface="envelope serialization")
   263	        plain = _to_plain(self)
   264	        plain["vibecomfy_format_version"] = FORMAT_VERSION
   265	        return plain
   266	
   267	    @classmethod
   268	    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
   269	        """Fail-closed decoder for a serialized vibe envelope.
   270	
   271	        Rich ``nodes`` + ``edges`` are the only structural authority.
   272	        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
   273	        no partial graph is returned. Implementation is the existing ingest
   274	        decoder — this method does not relax it.
   275	        """
   276	        from vibecomfy.ingest.normalize import _decode_serialized_vibe
   277	
   278	        return _decode_serialized_vibe(raw)
   279	
   280	    def clone(self) -> "VibeWorkflow":
   281	        return self.copy()
   282	
   283	    def finalize_metadata(self) -> "VibeWorkflow":
   284	        from vibecomfy.metadata import OUTPUT_NODE_NAMES, _infer_requirements, _register_common_inputs
   285	
   286	        manual_inputs = {
   287	            name: replace(vibe_input)
   288	            for name, vibe_input in self.inputs.items()
   289	            if name in self._manual_input_names and self._input_target_exists(vibe_input)
   290	        }
   291	        self._manual_input_names.intersection_update(manual_inputs)
   292	        self.inputs.clear()
   293	        self.outputs.clear()
   294	        for node_id, node in self.nodes.items():
   295	            _register_common_inputs(self, node_id, node)
   296	            if node.class_type in OUTPUT_NODE_NAMES:
   297	                self.outputs.append(VibeOutput(node_id=node_id, output_type=node.class_type))
   298	        self.inputs.update(manual_inputs)
   299	        self.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
   300	        self.requirements = _infer_requirements(self)
   301	        return self
   302	
   303	    def finalize(
   304	        self,
   305	        public_inputs: dict[str, Any],
   306	        *,
   307	        metadata: dict[str, Any] | None = None,
   308	        output_node: Any = None,
   309	        output_kind: str | None = None,
   310	        **bind_kwargs: Any,
   311	    ) -> "VibeWorkflow":
   312	        """Finalize ready-template public inputs and output binding.
   313	
   314	        ``metadata`` is optional for the v2.5 method form; when omitted, the
   315	        workflow's current metadata is used. The legacy free function remains
   316	        available in ``vibecomfy.templates.finalize``.
   317	        """
   318	        from vibecomfy.templates import _finalize_impl
   319	
   320	        return _finalize_impl(
   321	            self,
   322	            public_inputs,
   323	            dict(self.metadata if metadata is None else metadata),
   324	            output_node=output_node,
   325	            output_kind=output_kind,
   326	            **bind_kwargs,
   327	        )
   328	
   329	    def register_input(
   330	        self,
   331	        name: str,
   332	        node_id: str,
   333	        field: str,
   334	        value: Any = None,
   335	        *,
   336	        type: str | None = None,
   337	        default: Any = None,
   338	        required: bool = False,
   339	        range: Any = None,
   340	        aliases: list[str] | tuple[str, ...] | None = None,
   341	        media_semantics: str | None = None,
   342	        media: str | None = None,
   343	    ) -> "VibeWorkflow":
   344	        if media_semantics is not None and media is not None and media_semantics != media:
   345	            raise ValueError(
   346	                f"register_input({name!r}): media_semantics and legacy media "
   347	                "must match when both are provided"
   348	            )
   349	        resolved_media_semantics = media_semantics if media_semantics is not None else media
   350	        alias_tuple = _normalize_input_aliases(aliases)
   351	        self._validate_input_aliases(name, alias_tuple)
   352	        self._validate_input_target(name, node_id, field)
   353	        self.inputs[name] = VibeInput(
   354	            name=name,
   355	            node_id=str(node_id),
   356	            field=field,
   357	            value=value,
   358	            type=type,
   359	            default=value if default is None else default,
   360	            required=required,
   361	            range=range,
   362	            aliases=alias_tuple,
   363	            media_semantics=resolved_media_semantics,
   364	        )
   365	        self._manual_input_names.add(name)
   366	        return self
   367	
   368	    def set_input(self, name: str, value: Any) -> "VibeWorkflow":
   369	        target = self._resolve_input(name)
   370	        if target is None:
   371	            raise ValueError(self._unknown_input_message(name))
   372	
   373	        node = self.nodes.get(target.node_id)
   374	        if node is None:
   375	            raise ValueError(
   376	                f"set_input({name!r}) cannot update public input {target.name!r}: "
   377	                f"target node {target.node_id!r} is missing from workflow {self.id!r}. "
   378	                f"Registered target: {target.node_id}.{target.field}."
   379	            )
   380	        if target.field in node.inputs:
   381	            node.inputs[target.field] = value
   382	        elif target.field in node.widgets:
   383	            node.widgets[target.field] = value
   384	        else:
   385	            available = _format_available_names([*node.inputs.keys(), *node.widgets.keys()])
   386	            raise ValueError(
   387	                f"set_input({name!r}) cannot update public input {target.name!r}: "
   388	                f"target field {target.field!r} is missing from node {target.node_id!r} "
   389	                f"({node.class_type}) in workflow {self.id!r}. "
   390	                f"Available fields on node {target.node_id!r}: {available}."
   391	            )
   392	        target.value = value
   393	        return self
   394	
   395	    def _resolve_input(self, name: str) -> VibeInput | None:
   396	        if name in self.inputs:
   397	            return self.inputs[name]
   398	        matches = [item for item in self.inputs.values() if name in item.aliases]
   399	        if len(matches) > 1:
   400	            matched_names = _format_available_names(item.name for item in matches)
   401	            raise ValueError(
   402	                f"Input alias {name!r} is ambiguous in workflow {self.id!r}; "
   403	                f"it matches public inputs: {matched_names}."
   404	            )
   405	        return matches[0] if matches else None
   406	
   407	    def _unknown_input_message(self, name: str) -> str:
   408	        available_names = _format_available_names(self.inputs.keys())
   409	        aliases = {
   410	            alias: item.name
   411	            for item in self.inputs.values()
   412	            for alias in item.aliases
   413	        }
   414	        if aliases:
   415	            alias_text = ", ".join(
   416	                f"{alias!r} -> {primary!r}" for alias, primary in sorted(aliases.items())
   417	            )
   418	        else:
   419	            alias_text = "<none>"
   420	        return (
   421	            f"set_input({name!r}) has no registered public input or alias in "
   422	            f"workflow {self.id!r}. Available public inputs: {available_names}. "
   423	            f"Available aliases: {alias_text}. Register the input before calling set_input()."
   424	        )
   425	
   426	    def _validate_input_aliases(self, name: str, aliases: tuple[str, ...]) -> None:
   427	        if len(set(aliases)) != len(aliases):
   428	            raise ValueError(f"register_input({name!r}): duplicate aliases are not allowed")
   429	        if name in aliases:
   430	            raise ValueError(f"register_input({name!r}): alias cannot equal its primary input name")
   780	        """Map variable name (as used in build()) to assigned node id."""
   781	        return dict(self._id_map)
   782	
   783	    def _set_id_map(self, mapping: dict[str, Any]) -> "VibeWorkflow":
   784	        """Store codemod-emitted variable-name mappings and return ``self``."""
   785	        resolved: dict[str, str] = {}
   786	        metadata_id_map = self.metadata.get("id_map")
   787	        metadata_id_map = metadata_id_map if isinstance(metadata_id_map, dict) else {}
   788	        for name, node_id in mapping.items():
   789	            key = str(name)
   790	            value = str(node_id)
   791	            if value in self.nodes:
   792	                resolved[key] = value
   793	                continue
   794	            metadata_value = metadata_id_map.get(value)
   795	            resolved[key] = str(metadata_value) if metadata_value is not None else value
   796	        self._id_map = resolved
   797	        return self
   798	
   799	    def lookup_id(self, node_id: str) -> dict[str, Any]:
   800	        """Return a rich info dict for the node identified by *node_id*.
   801	
   802	        Raises ``KeyError`` when *node_id* is absent from the workflow —
   803	        callers asked for a concrete node id.
   804	        """
   805	        nid = str(node_id)
   806	        if nid not in self.nodes:
   807	            raise KeyError(nid)
   808	
   809	        node = self.nodes[nid]
   810	
   811	        # --- variable_name: reverse lookup from _id_map --------------------
   812	        variable_name: str | None = None
   813	        for name, mapped_id in self._id_map.items():
   814	            if mapped_id == nid:
   815	                variable_name = name
   816	                break
   817	
   818	        # --- source_path ---------------------------------------------------
   819	        provenance = node.metadata.get("provenance")
   820	        source_path: str | None = None
   821	        if isinstance(provenance, dict):
   822	            sp = provenance.get("source_path")
   823	            if isinstance(sp, str) and sp:
   824	                source_path = sp
   825	        if source_path is None:
   826	            source_path = self.source.path
   827	
   828	        # --- source_line (SD4: null for generated-template nodes) ----------
   829	        source_line: int | None = None
   830	        if isinstance(provenance, dict):
   831	            sl = provenance.get("source_line")
   832	            if isinstance(sl, int) and sl >= 1:
   833	                source_line = sl
   834	
   835	        # --- inputs ---------------------------------------------------------
   836	        input_names: list[str] = list(node.inputs.keys())
   837	
   838	        # --- widgets --------------------------------------------------------
   839	        widgets: dict[str, Any] = dict(node.widgets)
   840	
   841	        # --- public_bindings ------------------------------------------------
   842	        public_bindings: list[dict[str, Any]] = [
   843	            {
   844	                "name": vibe_input.name,
   845	                "field": vibe_input.field,
   846	                "value": vibe_input.value,
   847	                "type": vibe_input.type,
   848	                "default": vibe_input.default,
   849	                "required": vibe_input.required,
   850	            }
   851	            for vibe_input in self.inputs.values()
   852	            if str(vibe_input.node_id) == nid
   853	        ]
   854	
   855	        # --- outputs --------------------------------------------------------
   856	        output_type_names: list[str] = [
   857	            output.output_type
   858	            for output in self.outputs
   859	            if str(output.node_id) == nid
   860	        ]
   861	
   862	        # --- model_assets ---------------------------------------------------
   863	        model_assets: list[dict[str, Any]] = []
   864	        try:
   865	            from vibecomfy.model_assets import (
   866	                _asset_for_reference,
   867	                _referenced_model_values,
   868	                _unresolved_asset_for_reference,
   869	            )
   870	            from vibecomfy.registry.models_loader import load_registry
   871	
   872	            registry = load_registry()
   873	            all_refs = _referenced_model_values(self)
   874	            for ref in all_refs:
   875	                if ref.get("node_id") != nid:
   876	                    continue
   877	                asset = _asset_for_reference(ref, registry=registry)
   878	                if asset is not None:
   879	                    model_assets.append(asset)
   880	                else:
   881	                    model_assets.append(_unresolved_asset_for_reference(ref))
   882	        except Exception:
   883	            # resolve_referenced_assets may fail when registry is unavailable;
   884	            # degrade gracefully and return whatever we can.
   885	            pass
   886	
   887	        return {
   888	            "variable_name": variable_name,
   889	            "class_type": node.class_type,
   890	            "source_path": source_path,
   891	            "source_line": source_line,
   892	            "inputs": input_names,
   893	            "widgets": widgets,
   894	            "public_bindings": public_bindings,
   895	            "outputs": output_type_names,
   896	            "model_assets": model_assets,
   897	        }
   898	
   899	    def _compile_graphbuilder(self) -> dict[str, Any]:
   900	        try:
   901	            from comfy_execution.graph_utils import GraphBuilder
   902	        except ImportError as exc:
   903	            raise RuntimeError("GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.") from exc
   904	
   905	        broadcast_sources = workflow_helpers.collect_broadcast_sources(self.nodes, self.edges)
   906	        edge_inputs = _compile_resolved_edge_inputs(self.nodes, self.edges, broadcast_sources)
   907	
   908	        builder = GraphBuilder(prefix="")
   909	        for node_id, node in self.nodes.items():
   910	            if _is_compile_stripped_node(node):
   911	                continue
   912	            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), self.nodes, broadcast_sources)
   913	            inputs.update(_compile_intent_runtime_inputs(node))
   914	            inputs.update(edge_inputs.get(str(node_id), {}))
   915	            builder.node(node.class_type, id=str(node_id), **inputs)
   916	        return builder.finalize()
   917	
   918	    def _next_node_id(self) -> str:
   919	        numeric = {int(node_id) for node_id in self.nodes if str(node_id).isdigit() and int(node_id) > 0}
   920	        candidate = 1

exec
/bin/zsh -lc "git diff --unified=70 8a8300bb..0d2bb176 -- vibecomfy/ingest/normalize.py && nl -ba vibecomfy/ingest/normalize.py | sed -n '410,675p' && nl -ba vibecomfy/ingest/normalize.py | sed -n '830,990p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/ingest/normalize.py b/vibecomfy/ingest/normalize.py
index 760d2ee4..1dddec49 100644
--- a/vibecomfy/ingest/normalize.py
+++ b/vibecomfy/ingest/normalize.py
@@ -1,104 +1,106 @@
 from __future__ import annotations
 
 from copy import deepcopy
 from pathlib import Path
 from typing import Any
 
 import warnings
 
-from vibecomfy._compile._graph import is_api_link
+from vibecomfy._compile._graph import is_canonical_api_link
 from vibecomfy.comfy_backend import check_comfy_compatibility, require_comfy_compatibility
 # vibecomfy.exec class type: mirrored as a literal to avoid a module-level import of
 # vibecomfy.comfy_nodes.exec_node, which would re-execute comfy_nodes/__init__ (route
 # registration side-effect) at boot and pull torch eagerly. Mirrors
 # vibecomfy.comfy_nodes.exec_node.EXEC_CLASS_TYPE (see agent_session.py for the same pattern).
 EXEC_CLASS_TYPE = "vibecomfy.exec"
 from vibecomfy.metadata import (
     OUTPUT_NODE_NAMES,
     _infer_requirements,
     _register_common_inputs,
 )
 from vibecomfy.identity.uid import make_uid, mint_local_uid
 from vibecomfy.porting.widgets.aliases import widget_names_for_class, widget_names_from_schema
 from vibecomfy.schema import OutputSpec, SchemaProvider, schema_for
 from vibecomfy.security.gate import untrusted_scope
 from vibecomfy.security.provenance import PROVENANCE_KEY
 from vibecomfy.workflow import (
     RawWidgetPayload,
     VibeEdge,
     VibeInput,
     VibeNode,
     VibeOutput,
     VibeWorkflow,
     WorkflowRequirements,
     WorkflowSource,
+    _embedded_api_link_details,
+    _embedded_api_link_message,
 )
 
 EXEC_SOURCE_MAX_BYTES = 48 * 1024
 EXEC_SOURCE_MAX_TOTAL_BYTES = 768 * 1024
 
 
 def detect_workflow_shape(raw: dict[str, Any]) -> str:
     """Private dispatcher helper. Not part of the public ingest API.
 
     Callers that know their input should use :func:`from_envelope`,
     :func:`from_ui`, or :func:`from_api`. This remains for
     :func:`normalize_to_api` and a few internal tags that still need a shape
     label.
     """
     if "prompt" in raw and isinstance(raw["prompt"], dict):
         return detect_workflow_shape(raw["prompt"])
     # ``compiled_api`` is optional execution evidence.  A versioned rich
     # envelope remains a Vibe envelope even when that evidence is absent or
     # malformed; structural shape is established by the rich nodes mapping.
     if isinstance(raw.get("nodes"), dict) and (
         "vibecomfy_format_version" in raw
         or isinstance(raw.get("compiled_api"), dict)
     ):
         return "vibe"
     if isinstance(raw.get("nodes"), list):
         return "ui"
     if raw == {}:
         return "api"
     if raw and all(isinstance(value, dict) and "class_type" in value for value in raw.values()):
         return "api"
     return "unknown"
 
 
 def normalize_to_api(
     raw: dict[str, Any],
     *,
     schema_provider: SchemaProvider | None = None,
     use_comfy_converter: bool = True,
     comfy_converter_strict: bool = True,
 ) -> dict[str, Any]:
     """Convert a raw workflow dict (UI or API shape) to ComfyUI API format.
 
     By default this prefers the live ComfyUI converter and raises if
     ``convert_ui_to_api`` fails. Pass ``comfy_converter_strict=False`` to keep the
     legacy lenient fallback path when the converter is importable but errors. Pass
     ``use_comfy_converter=False`` for explicit offline normalization that never
     imports or calls the ComfyUI converter; in that mode
     ``comfy_converter_strict`` is ignored.
     """
     shape = detect_workflow_shape(raw)
     if shape == "api":
         api = raw.get("prompt", raw)
         _enforce_exec_source_limits(api, surface="api")
         return api
     if shape == "vibe":
         # The rich envelope (nodes mapping + edges list) is the only structural
         # authority. ``compiled_api`` is stale execution evidence and must never
         # decide which rich nodes exist — the API view is derived by decoding
         # the envelope into a VibeWorkflow and compiling it fresh.
         workflow = VibeWorkflow.from_envelope(raw)
         api = workflow.compile("api")
         _merge_vibe_node_widget_evidence(raw, api)
         _enforce_exec_source_limits(api, surface="vibe.compiled_api")
         return api
     if shape != "ui":
         raise ValueError(f"Unsupported workflow shape: {shape}")
     return _ui_graph_to_api(
         raw,
         schema_provider=schema_provider,
         use_comfy_converter=use_comfy_converter,
@@ -566,140 +568,149 @@ def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
                     f"node {node_id!r}: raw_widgets.shape must be a nonblank string"
                 )
             if not isinstance(source_name, str) or not source_name.strip():
                 raise ValueError(
                     f"node {node_id!r}: raw_widgets.source must be a nonblank string"
                 )
             if not isinstance(has_dict_rows, bool):
                 raise ValueError(
                     f"node {node_id!r}: raw_widgets.has_dict_rows must be a boolean"
                 )
             raw_widget_payload = RawWidgetPayload(
                 values=deepcopy(raw_widgets["values"]),
                 shape=shape,
                 source=source_name,
                 has_dict_rows=has_dict_rows,
                 length=length,
             )
         node_metadata = deepcopy(entry["metadata"])
         # S4 capability fence: ingest is the external-JSON boundary, so every
         # decoded node is tagged untrusted_source. Unconditional set — never
         # `setdefault` — so hostile JSON cannot pre-declare itself trusted.
         node_metadata[PROVENANCE_KEY] = "untrusted_source"
         # Mode is first-class: prefer the serialized node-level ``mode`` field
         # (written by to_envelope's dataclass walk), falling back to the legacy
         # ``_ui.mode`` / ``metadata["mode"]`` locations for old envelopes.
         # ``_ui`` stays verbatim so the emitter's furniture keeps re-emitting it.
         entry_mode = entry.get("mode")
         node_mode = (
             entry_mode if isinstance(entry_mode, int) else _node_mode_from_metadata(node_metadata)
         )
         workflow.nodes[node_id] = VibeNode(
             id=node_id,
             class_type=class_type,
             pack=pack,
             inputs=deepcopy(entry["inputs"]),
             widgets=deepcopy(entry["widgets"]),
             metadata=node_metadata,
             uid=uid,
             raw_widgets=raw_widget_payload,
             mode=node_mode,
         )
 
     # ── edges ──────────────────────────────────────────────────────────────
     edges_raw = raw.get("edges")
     if not isinstance(edges_raw, list):
         raise ValueError("serialized vibe envelope 'edges' must be a list")
     for index, edge in enumerate(edges_raw):
         if not isinstance(edge, dict):
             raise ValueError(
                 f"edge {index}: edge entries must be mappings, got {type(edge).__name__}"
             )
         for field_name in ("from_node", "from_output", "to_node", "to_input"):
             value = edge.get(field_name)
             if not isinstance(value, str) or not value.strip():
                 raise ValueError(f"edge {index}: {field_name} must be a nonblank string")
         if edge["from_node"] not in workflow.nodes or edge["to_node"] not in workflow.nodes:
             raise ValueError(
                 f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
                 "must exist in nodes"
             )
         workflow.edges.append(
             VibeEdge(
                 from_node=edge["from_node"],
                 from_output=edge["from_output"],
                 to_node=edge["to_node"],
                 to_input=edge["to_input"],
             )
         )
 
     # ── top-level inputs / outputs ─────────────────────────────────────────
+    embedded_links = _embedded_api_link_details(workflow)
+    if embedded_links:
+        raise ValueError(
+            "embedded_api_link: "
+            + _embedded_api_link_message(
+                embedded_links[0], surface="serialized vibe envelope decode"
+            )
+        )
+
     inputs_raw = raw.get("inputs")
     if not isinstance(inputs_raw, dict):
         raise ValueError("serialized vibe envelope 'inputs' must be a mapping")
     for name, entry in inputs_raw.items():
         if not isinstance(entry, dict):
             raise ValueError(
                 f"input {name!r}: input entries must be mappings, got {type(entry).__name__}"
             )
         input_name = entry.get("name")
         node_id = entry.get("node_id")
         field = entry.get("field")
         if not isinstance(input_name, str) or not input_name.strip():
             raise ValueError(f"input {name!r}: name must be a nonblank string")
         if str(name) != input_name:
             raise ValueError(
                 f"input mapping key {name!r} must equal input.name {input_name!r}"
             )
         if not isinstance(node_id, str) or not node_id.strip():
             raise ValueError(f"input {name!r}: node_id must be a nonblank string")
         if node_id not in workflow.nodes:
             raise ValueError(f"input {name!r}: node_id {node_id!r} must exist in nodes")
         if not isinstance(field, str) or not field.strip():
             raise ValueError(f"input {name!r}: field must be a nonblank string")
         required = entry.get("required", False)
         if not isinstance(required, bool):
             raise ValueError(f"input {name!r}: required must be a boolean")
         aliases = entry.get("aliases", ())
         if not isinstance(aliases, (list, tuple)) or not all(
             isinstance(alias, str) for alias in aliases
         ):
             raise ValueError(f"input {name!r}: aliases must be a list of strings")
         media_semantics = entry.get("media_semantics")
         if media_semantics is not None and not isinstance(media_semantics, str):
             raise ValueError(f"input {name!r}: media_semantics must be a string or null")
         input_type = entry.get("type")
         if input_type is not None and not isinstance(input_type, str):
             raise ValueError(f"input {name!r}: type must be a string or null")
         workflow.inputs[str(input_name)] = VibeInput(
             name=str(input_name),
             node_id=str(node_id),
             field=str(field),
             value=deepcopy(entry.get("value")),
             type=input_type,
             default=deepcopy(entry.get("default")),
             required=required,
             range=deepcopy(entry.get("range")),
             aliases=tuple(aliases),
             media_semantics=media_semantics,
         )
 
     outputs_raw = raw.get("outputs")
     if not isinstance(outputs_raw, list):
         raise ValueError("serialized vibe envelope 'outputs' must be a list")
     for index, entry in enumerate(outputs_raw):
         if not isinstance(entry, dict):
             raise ValueError(
                 f"output {index}: output entries must be mappings, got {type(entry).__name__}"
             )
         node_id = entry.get("node_id")
         output_type = entry.get("output_type")
         if not isinstance(node_id, str) or not node_id.strip():
             raise ValueError(f"output {index}: node_id must be a nonblank string")
         if node_id not in workflow.nodes:
             raise ValueError(
                 f"output {index}: node_id {node_id!r} must exist in nodes"
             )
         if not isinstance(output_type, str) or not output_type.strip():
             raise ValueError(f"output {index}: output_type must be a nonblank string")
         for field_name in ("name", "artifact_kind", "mime_type", "filename_prefix"):
             value = entry.get(field_name)
@@ -787,249 +798,237 @@ def from_api(
 
 def _is_vibe_envelope(raw: dict[str, Any]) -> bool:
     """True when *raw* is a versioned (or compiled_api-bearing) rich envelope."""
     return isinstance(raw.get("nodes"), dict) and (
         "vibecomfy_format_version" in raw
         or isinstance(raw.get("compiled_api"), dict)
     )
 
 
 def _named_import(
     raw: dict[str, Any],
     *,
     source_path: str | None = None,
     workflow_id: str | None = None,
     schema_provider: SchemaProvider | None = None,
     use_comfy_converter: bool = True,
     comfy_converter_strict: bool = True,
 ) -> VibeWorkflow:
     """Happy-path import: envelope, then UI, then API. Never ``compile()`` to reach IR."""
     if _is_vibe_envelope(raw):
         return from_envelope(raw)
     if isinstance(raw.get("nodes"), list):
         return from_ui(
             raw,
             source_path=source_path,
             workflow_id=workflow_id,
             schema_provider=schema_provider,
             use_comfy_converter=use_comfy_converter,
             comfy_converter_strict=comfy_converter_strict,
         )
     api = normalize_to_api(
         raw,
         schema_provider=schema_provider,
         use_comfy_converter=use_comfy_converter,
         comfy_converter_strict=comfy_converter_strict,
     )
     return from_api(
         api,
         source_path=source_path,
         workflow_id=workflow_id,
         schema_provider=schema_provider,
     )
 
 
 def _from_api_impl(
     api_workflow: dict[str, Any],
     *,
     source_path: str | None = None,
     workflow_id: str | None = None,
     schema_provider: SchemaProvider | None = None,
 ) -> VibeWorkflow:
     """Ingest a Comfy prompt dict. Caller holds :func:`untrusted_scope`."""
     _enforce_exec_source_limits(api_workflow, surface="api.ingest")
     source = WorkflowSource(
         id=workflow_id or (Path(source_path).stem if source_path else "workflow"),
         path=source_path,
         source_type="api",
     )
     workflow = VibeWorkflow(id=source.id, source=source)
     for node_id, node in api_workflow.items():
         if not isinstance(node, dict):
             continue
         raw_inputs = dict(node.get("inputs", {}))
         input_provenance = node.get("_input_provenance")
         if not isinstance(input_provenance, dict):
             input_provenance = {}
         inputs: dict[str, Any] = {}
         widgets: dict[str, Any] = {}
         class_type = str(node.get("class_type", "Unknown"))
         for key, value in raw_inputs.items():
-            if input_provenance.get(key) != "widget" and is_api_link(
-                value,
-                allow_tuple=False,
-                require_string_node_id=False,
-                require_numeric_node_id=True,
-                require_int_slot=False,
-            ):
+            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
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
-            if input_provenance.get(name) != "widget" and is_api_link(
-                value,
-                allow_tuple=False,
-                require_string_node_id=False,
-                require_numeric_node_id=True,
-                require_int_slot=False,
-            ):
+            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
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
 
 
 def _is_exec_widget_key(class_type: str, key: str) -> bool:
     return class_type == EXEC_CLASS_TYPE and key in {"source", "io"}
 
 
 def _normalize_exec_io_metadata(io_value: Any) -> dict[str, list[list[str | None]]] | None:
     from vibecomfy.comfy_nodes.exec_node import ExecNodeContractError, parse_io
 
     try:
         io_spec = parse_io(io_value)
     except ExecNodeContractError:
         return None
     normalized: dict[str, list[list[str | None]]] = {"inputs": [], "outputs": []}
     for field in ("inputs", "outputs"):
         normalized[field] = [[name, type_name] for name, type_name in io_spec.get(field, ())]
     return normalized
 
 
 def _rebuild_exec_reload_metadata(metadata: dict[str, Any], io_value: Any) -> None:
     ui = metadata.get("_ui")
     if not isinstance(ui, dict):
         ui = {}
         metadata["_ui"] = ui
     properties = ui.get("properties")
     if not isinstance(properties, dict):
         properties = {}
         ui["properties"] = properties
     vibecomfy = properties.get("vibecomfy")
     if not isinstance(vibecomfy, dict):
         vibecomfy = {}
         properties["vibecomfy"] = vibecomfy
     normalized_io = _normalize_exec_io_metadata(io_value)
     if normalized_io is None:
         vibecomfy.pop("io", None)
     else:
         vibecomfy["io"] = normalized_io
 
 
 def _enforce_exec_source_limits(api_workflow: dict[str, Any], *, surface: str) -> None:
     total_bytes = 0
     for node_id, node in api_workflow.items():
         if not isinstance(node, dict):
             continue
         if str(node.get("class_type", "")) != EXEC_CLASS_TYPE:
             continue
         inputs = node.get("inputs")
         if not isinstance(inputs, dict):
             continue
         source = inputs.get("source")
         if not isinstance(source, str):
             continue
         source_bytes = len(source.encode("utf-8"))
         if source_bytes > EXEC_SOURCE_MAX_BYTES:
             raise ValueError(
   410	    must be a list of group objects (LiteGraph ``{title, bounding, ...}``
   411	    dicts).  Old envelopes without the key decode to an empty list.
   412	    """
   413	    if value is None:
   414	        return []
   415	    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
   416	        raise ValueError("serialized vibe envelope 'groups' must be a list of group objects")
   417	    return deepcopy(value)
   418	
   419	
   420	def _node_mode_from_metadata(metadata: dict[str, Any]) -> int:
   421	    """First-class mode value for a node: ``_ui.mode`` then legacy
   422	    ``metadata["mode"]``, else 0.  Only ints are accepted."""
   423	    ui = metadata.get("_ui")
   424	    if isinstance(ui, dict):
   425	        ui_mode = ui.get("mode", 0)
   426	        if isinstance(ui_mode, int):
   427	            return ui_mode
   428	    meta_mode = metadata.get("mode")
   429	    if isinstance(meta_mode, int):
   430	        return meta_mode
   431	    return 0
   432	
   433	
   434	def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
   435	    """Implementation of :meth:`VibeWorkflow.from_envelope`.
   436	
   437	    Do not call this from new code — use ``VibeWorkflow.from_envelope`` (or
   438	    the module-level ``from_envelope``).  The decoder is fail-closed and
   439	    unrelaxed: the rich top-level ``nodes`` mapping and ``edges`` list are
   440	    the ONLY structural authority; ``compiled_api`` is never consulted for
   441	    which nodes exist.  Any malformed or mixed entry raises ``ValueError``
   442	    and no partial graph is ever returned.
   443	
   444	    Every field is deep-copied.  Node ``metadata`` is preserved verbatim
   445	    (including ``metadata._ui``) except that ``metadata[PROVENANCE_KEY]`` is
   446	    unconditionally enforced to ``"untrusted_source"`` at this external JSON
   447	    boundary, and stable node ``uid`` values are preserved exactly.
   448	    """
   449	    if not isinstance(raw, dict):
   450	        raise ValueError("serialized vibe envelope must be a JSON object")
   451	
   452	    nodes_raw = raw.get("nodes")
   453	    if not isinstance(nodes_raw, dict):
   454	        raise ValueError("serialized vibe envelope 'nodes' must be a mapping of node objects")
   455	    for key, entry in nodes_raw.items():
   456	        if not isinstance(entry, dict):
   457	            raise ValueError(
   458	                f"node {key!r}: node entries must be mappings, got {type(entry).__name__}"
   459	            )
   460	
   461	    # ── top-level envelope fields ──────────────────────────────────────────
   462	    source_raw = raw.get("source")
   463	    if not isinstance(source_raw, dict):
   464	        raise ValueError("serialized vibe envelope 'source' must be a mapping")
   465	    source_id = source_raw.get("id")
   466	    if not isinstance(source_id, str) or not source_id.strip():
   467	        raise ValueError("source.id must be a nonblank string")
   468	    source_path = source_raw.get("path")
   469	    if source_path is not None and not isinstance(source_path, str):
   470	        raise ValueError("source.path must be a string or null")
   471	    source_provenance = source_raw.get("provenance")
   472	    if source_provenance is not None and not isinstance(source_provenance, dict):
   473	        raise ValueError("source.provenance must be a mapping or null")
   474	    source = WorkflowSource(
   475	        id=source_id,
   476	        path=source_path,
   477	        source_type=str(source_raw.get("source_type", "unknown")),
   478	        provenance=deepcopy(source_provenance) if isinstance(source_provenance, dict) else {},
   479	    )
   480	
   481	    workflow_id = raw.get("id")
   482	    if not isinstance(workflow_id, str) or not workflow_id.strip():
   483	        workflow_id = source_id
   484	
   485	    requirements_raw = raw.get("requirements")
   486	    if not isinstance(requirements_raw, dict):
   487	        raise ValueError("serialized vibe envelope 'requirements' must be a mapping")
   488	    requirements = WorkflowRequirements(
   489	        models=_vibe_string_list(
   490	            requirements_raw.get("models"), "requirements.models"
   491	        ),
   492	        custom_nodes=_vibe_string_list(
   493	            requirements_raw.get("custom_nodes"), "requirements.custom_nodes"
   494	        ),
   495	        missing_models=_vibe_string_list(
   496	            requirements_raw.get("missing_models"), "requirements.missing_models"
   497	        ),
   498	        missing_nodes=_vibe_string_list(
   499	            requirements_raw.get("missing_nodes"), "requirements.missing_nodes"
   500	        ),
   501	        unsupported=_vibe_string_list(
   502	            requirements_raw.get("unsupported"), "requirements.unsupported"
   503	        ),
   504	    )
   505	
   506	    metadata_raw = raw.get("metadata")
   507	    if metadata_raw is not None and not isinstance(metadata_raw, dict):
   508	        raise ValueError("serialized vibe envelope 'metadata' must be a mapping or null")
   509	
   510	    strict_types = raw.get("strict_types", False)
   511	    if not isinstance(strict_types, bool):
   512	        raise ValueError("strict_types must be a boolean")
   513	
   514	    groups = _vibe_groups(raw.get("groups"))
   515	
   516	    workflow = VibeWorkflow(
   517	        id=workflow_id,
   518	        source=source,
   519	        requirements=requirements,
   520	        metadata=deepcopy(metadata_raw) if isinstance(metadata_raw, dict) else {},
   521	        strict_types=strict_types,
   522	        groups=groups,
   523	    )
   524	
   525	    # ── nodes ──────────────────────────────────────────────────────────────
   526	    for key, entry in nodes_raw.items():
   527	        node_id = entry.get("id")
   528	        if not isinstance(node_id, str) or not node_id.strip():
   529	            raise ValueError(f"node {key!r}: id must be a nonblank string")
   530	        if str(key) != node_id:
   531	            raise ValueError(f"node mapping key {key!r} must equal node.id {node_id!r}")
   532	        class_type = entry.get("class_type")
   533	        if not isinstance(class_type, str) or not class_type.strip():
   534	            raise ValueError(f"node {node_id!r}: class_type must be a nonblank string")
   535	        uid = entry.get("uid")
   536	        if not isinstance(uid, str) or not uid.strip():
   537	            raise ValueError(f"node {node_id!r}: uid must be a nonblank string")
   538	        pack = entry.get("pack")
   539	        if pack is not None and not isinstance(pack, str):
   540	            raise ValueError(f"node {node_id!r}: pack must be a string or null")
   541	        for field_name in ("inputs", "widgets", "metadata"):
   542	            value = entry.get(field_name)
   543	            if not isinstance(value, dict):
   544	                raise ValueError(f"node {node_id!r}: {field_name} must be a mapping")
   545	        raw_widgets = entry.get("raw_widgets")
   546	        raw_widget_payload: RawWidgetPayload | None = None
   547	        if raw_widgets is not None:
   548	            if not isinstance(raw_widgets, dict) or not {
   549	                "values",
   550	                "shape",
   551	                "source",
   552	                "has_dict_rows",
   553	                "length",
   554	            } <= set(raw_widgets):
   555	                raise ValueError(
   556	                    f"node {node_id!r}: raw_widgets must be a RawWidgetPayload mapping or null"
   557	                )
   558	            length = raw_widgets["length"]
   559	            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
   560	                raise ValueError(
   561	                    f"node {node_id!r}: raw_widgets.length must be a nonnegative integer"
   562	                )
   563	            shape = raw_widgets["shape"]
   564	            source_name = raw_widgets["source"]
   565	            has_dict_rows = raw_widgets["has_dict_rows"]
   566	            if not isinstance(shape, str) or not shape.strip():
   567	                raise ValueError(
   568	                    f"node {node_id!r}: raw_widgets.shape must be a nonblank string"
   569	                )
   570	            if not isinstance(source_name, str) or not source_name.strip():
   571	                raise ValueError(
   572	                    f"node {node_id!r}: raw_widgets.source must be a nonblank string"
   573	                )
   574	            if not isinstance(has_dict_rows, bool):
   575	                raise ValueError(
   576	                    f"node {node_id!r}: raw_widgets.has_dict_rows must be a boolean"
   577	                )
   578	            raw_widget_payload = RawWidgetPayload(
   579	                values=deepcopy(raw_widgets["values"]),
   580	                shape=shape,
   581	                source=source_name,
   582	                has_dict_rows=has_dict_rows,
   583	                length=length,
   584	            )
   585	        node_metadata = deepcopy(entry["metadata"])
   586	        # S4 capability fence: ingest is the external-JSON boundary, so every
   587	        # decoded node is tagged untrusted_source. Unconditional set — never
   588	        # `setdefault` — so hostile JSON cannot pre-declare itself trusted.
   589	        node_metadata[PROVENANCE_KEY] = "untrusted_source"
   590	        # Mode is first-class: prefer the serialized node-level ``mode`` field
   591	        # (written by to_envelope's dataclass walk), falling back to the legacy
   592	        # ``_ui.mode`` / ``metadata["mode"]`` locations for old envelopes.
   593	        # ``_ui`` stays verbatim so the emitter's furniture keeps re-emitting it.
   594	        entry_mode = entry.get("mode")
   595	        node_mode = (
   596	            entry_mode if isinstance(entry_mode, int) else _node_mode_from_metadata(node_metadata)
   597	        )
   598	        workflow.nodes[node_id] = VibeNode(
   599	            id=node_id,
   600	            class_type=class_type,
   601	            pack=pack,
   602	            inputs=deepcopy(entry["inputs"]),
   603	            widgets=deepcopy(entry["widgets"]),
   604	            metadata=node_metadata,
   605	            uid=uid,
   606	            raw_widgets=raw_widget_payload,
   607	            mode=node_mode,
   608	        )
   609	
   610	    # ── edges ──────────────────────────────────────────────────────────────
   611	    edges_raw = raw.get("edges")
   612	    if not isinstance(edges_raw, list):
   613	        raise ValueError("serialized vibe envelope 'edges' must be a list")
   614	    for index, edge in enumerate(edges_raw):
   615	        if not isinstance(edge, dict):
   616	            raise ValueError(
   617	                f"edge {index}: edge entries must be mappings, got {type(edge).__name__}"
   618	            )
   619	        for field_name in ("from_node", "from_output", "to_node", "to_input"):
   620	            value = edge.get(field_name)
   621	            if not isinstance(value, str) or not value.strip():
   622	                raise ValueError(f"edge {index}: {field_name} must be a nonblank string")
   623	        if edge["from_node"] not in workflow.nodes or edge["to_node"] not in workflow.nodes:
   624	            raise ValueError(
   625	                f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
   626	                "must exist in nodes"
   627	            )
   628	        workflow.edges.append(
   629	            VibeEdge(
   630	                from_node=edge["from_node"],
   631	                from_output=edge["from_output"],
   632	                to_node=edge["to_node"],
   633	                to_input=edge["to_input"],
   634	            )
   635	        )
   636	
   637	    # ── top-level inputs / outputs ─────────────────────────────────────────
   638	    embedded_links = _embedded_api_link_details(workflow)
   639	    if embedded_links:
   640	        raise ValueError(
   641	            "embedded_api_link: "
   642	            + _embedded_api_link_message(
   643	                embedded_links[0], surface="serialized vibe envelope decode"
   644	            )
   645	        )
   646	
   647	    inputs_raw = raw.get("inputs")
   648	    if not isinstance(inputs_raw, dict):
   649	        raise ValueError("serialized vibe envelope 'inputs' must be a mapping")
   650	    for name, entry in inputs_raw.items():
   651	        if not isinstance(entry, dict):
   652	            raise ValueError(
   653	                f"input {name!r}: input entries must be mappings, got {type(entry).__name__}"
   654	            )
   655	        input_name = entry.get("name")
   656	        node_id = entry.get("node_id")
   657	        field = entry.get("field")
   658	        if not isinstance(input_name, str) or not input_name.strip():
   659	            raise ValueError(f"input {name!r}: name must be a nonblank string")
   660	        if str(name) != input_name:
   661	            raise ValueError(
   662	                f"input mapping key {name!r} must equal input.name {input_name!r}"
   663	            )
   664	        if not isinstance(node_id, str) or not node_id.strip():
   665	            raise ValueError(f"input {name!r}: node_id must be a nonblank string")
   666	        if node_id not in workflow.nodes:
   667	            raise ValueError(f"input {name!r}: node_id {node_id!r} must exist in nodes")
   668	        if not isinstance(field, str) or not field.strip():
   669	            raise ValueError(f"input {name!r}: field must be a nonblank string")
   670	        required = entry.get("required", False)
   671	        if not isinstance(required, bool):
   672	            raise ValueError(f"input {name!r}: required must be a boolean")
   673	        aliases = entry.get("aliases", ())
   674	        if not isinstance(aliases, (list, tuple)) or not all(
   675	            isinstance(alias, str) for alias in aliases
   830	        schema_provider=schema_provider,
   831	        use_comfy_converter=use_comfy_converter,
   832	        comfy_converter_strict=comfy_converter_strict,
   833	    )
   834	    return from_api(
   835	        api,
   836	        source_path=source_path,
   837	        workflow_id=workflow_id,
   838	        schema_provider=schema_provider,
   839	    )
   840	
   841	
   842	def _from_api_impl(
   843	    api_workflow: dict[str, Any],
   844	    *,
   845	    source_path: str | None = None,
   846	    workflow_id: str | None = None,
   847	    schema_provider: SchemaProvider | None = None,
   848	) -> VibeWorkflow:
   849	    """Ingest a Comfy prompt dict. Caller holds :func:`untrusted_scope`."""
   850	    _enforce_exec_source_limits(api_workflow, surface="api.ingest")
   851	    source = WorkflowSource(
   852	        id=workflow_id or (Path(source_path).stem if source_path else "workflow"),
   853	        path=source_path,
   854	        source_type="api",
   855	    )
   856	    workflow = VibeWorkflow(id=source.id, source=source)
   857	    for node_id, node in api_workflow.items():
   858	        if not isinstance(node, dict):
   859	            continue
   860	        raw_inputs = dict(node.get("inputs", {}))
   861	        input_provenance = node.get("_input_provenance")
   862	        if not isinstance(input_provenance, dict):
   863	            input_provenance = {}
   864	        inputs: dict[str, Any] = {}
   865	        widgets: dict[str, Any] = {}
   866	        class_type = str(node.get("class_type", "Unknown"))
   867	        for key, value in raw_inputs.items():
   868	            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
   869	                continue
   870	            if key.startswith("widget_") or _is_exec_widget_key(class_type, key):
   871	                widgets[key] = value
   872	            else:
   873	                inputs[key] = value
   874	        raw_widgets = _coerce_raw_widget_payload(
   875	            node.get("_raw_widgets", node.get("raw_widgets"))
   876	        )
   877	        if raw_widgets is None:
   878	            raw_ui = node.get("_ui")
   879	            if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
   880	                raw_widgets = _coerce_raw_widget_payload(
   881	                    _raw_widget_payload_dict(raw_ui["widgets_values"], source="ui.widgets_values")
   882	                )
   883	        metadata = {
   884	            key: value
   885	            for key, value in node.items()
   886	            if key
   887	            not in {
   888	                "class_type",
   889	                "inputs",
   890	                "_raw_widgets",
   891	                "raw_widgets",
   892	                "_input_provenance",
   893	            }
   894	        }
   895	        # ── retain control_after_generate (UI-only) into metadata ──
   896	        # Captured here, before the compile-time `_is_ui_only_prompt_input` filter
   897	        # (workflow.py:471) drops it from the compiled API dict, so the emitter can
   898	        # re-render it. Metadata-only: it never re-enters `inputs`/`widgets`, so
   899	        # `compile("api")` stays byte-for-byte identical. Never guessed — when no
   900	        # recognized control token is present, metadata stays unset and the emitter
   901	        # emits the documented `fixed` default itself.
   902	        control_value = _capture_control_after_generate(node, class_type)
   903	        if control_value is not None:
   904	            metadata.setdefault("control_after_generate", control_value)
   905	        # ── retain flags/color/bgcolor from _ui into top-level metadata ──
   906	        # Both paths: pure-Python path stores the full raw node in _ui (line 99);
   907	        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
   908	        # Captured as metadata DATA only — never enters inputs/widgets (K3 invariant).
   909	        # mode is first-class on VibeNode (the compile mute/bypass signal): the
   910	        # field is populated below from `_ui.mode` (fallback metadata["mode"]) and
   911	        # `_ui.mode` is LEFT IN PLACE so emit_ui_json's furniture keeps re-emitting
   912	        # it.  No duplicate metadata["mode"] is written on new ingests.
   913	        _ui_raw = metadata.get("_ui")
   914	        if isinstance(_ui_raw, dict):
   915	            # The _ui dict may alias the input API node's _ui (pure-Python path);
   916	            # deepcopy so the caller's node dict is never corrupted.
   917	            # Only assign when a real _ui was present — do not invent {}.
   918	            _ui_node = deepcopy(_ui_raw)
   919	            metadata["_ui"] = _ui_node
   920	            for _vis_field in ("flags", "color", "bgcolor"):
   921	                if _vis_field in _ui_node:
   922	                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
   923	        # ── enrich node metadata from schema ──
   924	        output_names = _schema_output_names(schema_provider, class_type)
   925	        if output_names:
   926	            metadata.setdefault("output_names", output_names)
   927	        output_types = _schema_output_types(schema_provider, class_type)
   928	        if output_types:
   929	            metadata.setdefault("output_types", output_types)
   930	        input_aliases = _schema_input_aliases(schema_provider, class_type)
   931	        if input_aliases:
   932	            metadata.setdefault("input_aliases", input_aliases)
   933	        schema_source = _schema_source_provenance(schema_provider, class_type)
   934	        if schema_source is not None:
   935	            metadata.setdefault("schema_source", schema_source)
   936	        if class_type == EXEC_CLASS_TYPE:
   937	            _rebuild_exec_reload_metadata(metadata, widgets.get("io"))
   938	        # S4 capability fence: ingest is the external-JSON boundary, so every
   939	        # ingested node is tagged untrusted_source. Unconditional set — never
   940	        # `setdefault` — so a hostile JSON cannot pre-declare itself trusted.
   941	        metadata[PROVENANCE_KEY] = "untrusted_source"
   942	        workflow.nodes[str(node_id)] = VibeNode(
   943	            id=str(node_id),
   944	            class_type=class_type,
   945	            inputs=inputs,
   946	            widgets=widgets,
   947	            metadata=metadata,
   948	            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
   949	            raw_widgets=raw_widgets,
   950	            mode=_node_mode_from_metadata(metadata),
   951	        )
   952	        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
   953	        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
   954	            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
   955	    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
   956	
   957	    for node_id, node in api_workflow.items():
   958	        if not isinstance(node, dict):
   959	            continue
   960	        input_provenance = node.get("_input_provenance")
   961	        if not isinstance(input_provenance, dict):
   962	            input_provenance = {}
   963	        for name, value in dict(node.get("inputs", {})).items():
   964	            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
   965	                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))
   966	
   967	    workflow.requirements = _infer_requirements(workflow)
   968	
   969	    # Stash an ingest-time snapshot immediately after uid minting and edge setup.
   970	    # Captured once here so downstream delta computation can detect edits.
   971	    from vibecomfy.ingest.snapshot import capture_ingest_snapshot  # local to avoid circular at module level
   972	    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(api_workflow, workflow)
   973	
   974	    # ``workflow.metadata`` is ``dict[str, Any]`` and transparently accepts
   975	    # any extra keys.  In particular, ``summary`` (a ``WorkflowSummary`` dict)
   976	    # may be present when re-ingesting a corpus JSON that was enriched with
   977	    # LLM-generated summaries.  It is left untouched here — no validation,
   978	    # no stripping — so it survives round-trips through this pipeline intact.
   979	    return workflow
   980	
   981	
   982	def _is_exec_widget_key(class_type: str, key: str) -> bool:
   983	    return class_type == EXEC_CLASS_TYPE and key in {"source", "io"}
   984	
   985	
   986	def _normalize_exec_io_metadata(io_value: Any) -> dict[str, list[list[str | None]]] | None:
   987	    from vibecomfy.comfy_nodes.exec_node import ExecNodeContractError, parse_io
   988	
   989	    try:
   990	        io_spec = parse_io(io_value)

exec
/bin/zsh -lc "rg -n \"VibeNode\\(\" vibecomfy --glob '*.py' && rg -n \"inputs\\s*=\\s*\\{["'^'"\\n]*\\[["'^'"\\]]+,["'^'"\\]]+\\]\" vibecomfy --glob '*.py' || true && rg -n \"\\[[\\\"'][0-9]+[\\\"']\\s*,\\s*[0-9]+\\]\" vibecomfy --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 73ms:
vibecomfy/workflow.py:544:        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
vibecomfy/porting/readability_inventory.py:265:    # Also look for VibeNode('<uuid>', ...) patterns
vibecomfy/porting/emit/ui.py:1349:    node = VibeNode(
vibecomfy/porting/reorganise/graph_facts.py:905:        wf.nodes[node_id] = VibeNode(
vibecomfy/ingest/normalize.py:598:        workflow.nodes[node_id] = VibeNode(
vibecomfy/ingest/normalize.py:942:        workflow.nodes[str(node_id)] = VibeNode(
vibecomfy/porting/edit/_resolve.py:1281:        return estimate_node_size(VibeNode(id="__batch__", class_type=class_type, uid="__batch__"), schema)[0]
vibecomfy/runtime/eval/core.py:248:    preview_node = VibeNode(
vibecomfy/runtime/eval/core.py:300:    decode_node = VibeNode(
vibecomfy/runtime/eval/core.py:315:    preview_node = VibeNode(

exec
/bin/zsh -lc "rg -n \"\\.inputs\\[["'^]]+'"\\]\\s*=|inputs\\.update\\(|inputs\\s*=.*\\[\" vibecomfy --glob '*.py' | head -300" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/demo_factory/run_campaign.py:621:    inputs = target.get("inputs") or []
vibecomfy/intent/_fixture.py:94:            inputs = node.get("inputs", [])
vibecomfy/intent/_fixture.py:95:            widget_inputs = [i for i in inputs if i.get("widget") and i.get("link") is None]
vibecomfy/intent/render_diff.py:71:        node.inputs[seed_field] = seed
vibecomfy/intent/render_diff.py:73:            node.inputs[control_field] = "fixed"
vibecomfy/executor/graph_facts.py:605:        literal_inputs = [
vibecomfy/porting/lowering.py:543:            cloned.inputs[target.target_field] = iteration_value
vibecomfy/porting/emit/node_kwargs.py:169:                    node.inputs[new] = node.inputs.pop(old)
vibecomfy/porting/emit/node_kwargs.py:174:                    node.inputs[key] = value
vibecomfy/porting/layout/reconcile.py:509:    raw_inputs = ui.get("inputs") or []
vibecomfy/comfy_nodes/agent/_frag_research.py:67:                parts.append("inputs=(" + "; ".join(slot_info[:6]) + ")")
vibecomfy/porting/emit/emit_ready.py:1530:                    node.inputs[new] = node.inputs.pop(old)
vibecomfy/porting/emit/emit_ready.py:1535:                    node.inputs[key] = value
vibecomfy/porting/emit/emit_ready.py:1732:                builder.node.inputs[key] = value
vibecomfy/porting/emit/emit_subgraph.py:219:        min_inputs = len(ordered[0][1].get("inputs") or ())
vibecomfy/porting/emit/emit_subgraph.py:340:                    nodes[str(node_id)].inputs[str(key)] = ["-10", len(input_ports) - 1]
vibecomfy/workflow.py:298:        self.inputs.update(manual_inputs)
vibecomfy/workflow.py:353:        self.inputs[name] = VibeInput(
vibecomfy/workflow.py:381:            node.inputs[target.field] = value
vibecomfy/workflow.py:568:                node.inputs[key] = value
vibecomfy/workflow.py:763:            inputs.update(_compile_intent_runtime_inputs(node))
vibecomfy/workflow.py:913:            inputs.update(_compile_intent_runtime_inputs(node))
vibecomfy/workflow.py:914:            inputs.update(edge_inputs.get(str(node_id), {}))
vibecomfy/workflow.py:1049:    inputs.update(node.inputs)
vibecomfy/commands/port/_widgets.py:61:            inputs = ", ".join(node["unresolved_inputs"])
vibecomfy/registry/ready_template.py:265:                builder.node.inputs[key] = value
vibecomfy/ingest/normalize.py:602:            inputs=deepcopy(entry["inputs"]),
vibecomfy/ingest/normalize.py:684:        workflow.inputs[str(input_name)] = VibeInput(
vibecomfy/registry/static_contract.py:528:            keyword_inputs.update({str(key): value for key, value in extras.items()})
vibecomfy/patches/save_prefix.py:19:                node.inputs["filename_prefix"] = value
vibecomfy/patches/ltx_lowvram.py:156:            node.inputs[key] = value
vibecomfy/patches/ltx_lowvram.py:198:        node.inputs["skip_blocks"] = node.inputs.pop("widget_0", node.widgets.pop("widget_0", "28"))
vibecomfy/patches/ltx_lowvram.py:211:    node.inputs.update(values)
vibecomfy/patches/gguf_unet.py:25:                node.inputs["unet_name"] = GGUF_MODEL
vibecomfy/patches/gguf_unet.py:33:                node.inputs["vae_name"] = "flux2-vae.safetensors"
vibecomfy/porting/emit/ui.py:1757:    raw_inputs = node_dict.get("inputs") or []
vibecomfy/identity/scope.py:47:        inputs = [
vibecomfy/porting/edit/apply_links.py:294:        inputs = []
vibecomfy/porting/reorganise/graph_facts.py:954:        inputs.update({str(key): value for key, value in raw_inputs.items()})
vibecomfy/porting/edit/_describe.py:581:        inputs = node.get("inputs") or []
vibecomfy/porting/edit/_describe.py:749:        inputs = node.get("inputs") or []
vibecomfy/_compile/_resolve.py:346:    node.inputs[field_name] = literal
vibecomfy/templates.py:366:            wf.inputs[alias] = VibeInput(
vibecomfy/schema/provider.py:164:        inputs.update({f"in_{index}": InputSpec("*", required=False) for index in range(EXEC_SLOT_COUNT)})
vibecomfy/metadata.py:77:            workflow.inputs["prompt"] = VibeInput("prompt", node_id, field, value)
vibecomfy/metadata.py:84:            workflow.inputs["seed"] = VibeInput("seed", node_id, field, value)
vibecomfy/metadata.py:92:            workflow.inputs["steps"] = VibeInput("steps", node_id, field, value)
vibecomfy/metadata.py:94:            workflow.inputs["model"] = VibeInput("model", node_id, field, value)
vibecomfy/_compile/_helpers.py:202:    inputs.update(_node_inputs(node))

codex
One important discrepancy surfaced immediately: the supplied “16 files / diff clean” summary describes only part of the commit. The actual Batch D+E commit changes 19 files (10 code, 9 tests); its own diff is clean, while the broader `ec13a34e..0d2bb176` range includes the approved documentation/check-in material and is not clean because of pre-existing whitespace in that generated check-in. I’m separating those scopes and checking whether the extra code changes are required by task 6.
exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/emit_subgraph.py | sed -n '300,365p' && git blame -L 330,348 -- vibecomfy/porting/emit/emit_subgraph.py && rg -n \"emit_subgraph|_extract|subgraph\" tests --glob '*.py' | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 428ms:
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 330)                         used_input_names,
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 331)                     )
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 332)                     input_ports.append(
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 333)                         _SubgraphPort(
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 334)                             input_name,
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 335)                             None,
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 336)                             source_name=str(key),
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 337)                             external_ref=(from_node, from_slot),
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 338)                         )
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 339)                     )
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 340)                     nodes[str(node_id)].inputs[str(key)] = ["-10", len(input_ports) - 1]
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 341)                     input_refs[(str(node_id), str(key))] = input_name
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 342)                     continue
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 343)                 edge = _Edge(from_node, str(from_slot), str(node_id), str(key))
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 344)                 edges_in.setdefault(str(node_id), []).append(edge)
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 345) 
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 346)     inputs = tuple(input_ports)
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 347) 
19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 348)     return_refs: list[tuple[str, int]] = []
tests/test_runtime_run.py:869:def test_compile_eval_subgraph_image_preview():
tests/test_runtime_run.py:871:    from vibecomfy.runtime.eval import compile_eval_subgraph
tests/test_runtime_run.py:877:    result = compile_eval_subgraph(wf, "1")
tests/test_runtime_run.py:887:def test_compile_eval_subgraph_latent_with_vae_from_checkpoint():
tests/test_runtime_run.py:889:    from vibecomfy.runtime.eval import compile_eval_subgraph
tests/test_runtime_run.py:895:    result = compile_eval_subgraph(wf, "2")
tests/test_runtime_run.py:908:def test_compile_eval_subgraph_latent_without_vae():
tests/test_runtime_run.py:910:    from vibecomfy.runtime.eval import compile_eval_subgraph
tests/test_runtime_run.py:916:    result = compile_eval_subgraph(wf, "1")
tests/test_runtime_run.py:925:def test_compile_eval_subgraph_non_visualizable():
tests/test_runtime_run.py:927:    from vibecomfy.runtime.eval import compile_eval_subgraph
tests/test_runtime_run.py:932:    result = compile_eval_subgraph(wf, "1")
tests/test_runtime_run.py:939:def test_compile_eval_subgraph_absent_node():
tests/test_runtime_run.py:941:    from vibecomfy.runtime.eval import compile_eval_subgraph
tests/test_runtime_run.py:947:        compile_eval_subgraph(wf, "999")
tests/test_model_assets.py:16:def test_extract_from_raw_workflow_normalises_model_metadata() -> None:
tests/test_model_assets.py:86:def test_extract_from_raw_workflow_recurses_nested_subgraphs() -> None:
tests/test_model_assets.py:89:            "subgraphs": [
tests/test_model_assets.py:106:                        "subgraphs": [
tests/test_model_assets.py:136:def test_extract_from_raw_workflow_returns_empty_for_api_shaped_workflow() -> None:
tests/test_model_assets.py:397:def test_real_wan_t2v_extracts_three_assets() -> None:
tests/test_model_assets.py:408:def test_real_flux2_subgraph_extracts_pre_policy_assets() -> None:
tests/test_ui_layout.py:278:        # Simulate scoped uids (as from subgraph inner nodes).
tests/test_ui_layout.py:279:        n1 = _make_node("3", "subgraph#inner_3")
tests/test_ui_layout.py:280:        n2 = _make_node("7", "subgraph#inner_7")
tests/test_ui_layout.py:287:        assert layers["subgraph#inner_3"] == 0
tests/test_ui_layout.py:288:        assert layers["subgraph#inner_7"] == 1
tests/test_ui_layout.py:435:# T5 — build_subgraph_groups tests
tests/test_ui_layout.py:440:    """Group title matches the subgraph definition name."""
tests/test_ui_layout.py:442:    def test_subgraph_box_title_matches_definition_name(self):
tests/test_ui_layout.py:443:        from vibecomfy.porting.layout.groups import build_subgraph_groups
tests/test_ui_layout.py:448:                "subgraphs": [
tests/test_ui_layout.py:466:        groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)
tests/test_ui_layout.py:474:    def test_subgraph_box_bounds_enclose_all_member_nodes(self):
tests/test_ui_layout.py:475:        from vibecomfy.porting.layout.groups import build_subgraph_groups
tests/test_ui_layout.py:480:                "subgraphs": [
tests/test_ui_layout.py:502:        groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)
tests/test_ui_layout.py:519:    """No subgraphs in metadata → empty group list."""
tests/test_ui_layout.py:521:    def test_no_subgraphs_returns_empty_group_list(self):
tests/test_ui_layout.py:522:        from vibecomfy.porting.layout.groups import build_subgraph_groups
tests/test_ui_layout.py:526:        groups = build_subgraph_groups(wf, positions={}, sizes={})
tests/test_ui_layout.py:531:        groups = build_subgraph_groups(wf, positions={}, sizes={})
tests/test_ui_layout.py:534:        # Definitions with no subgraphs.
tests/test_ui_layout.py:536:        groups = build_subgraph_groups(wf, positions={}, sizes={})
tests/test_ui_layout.py:543:    def test_subgraph_partial_match_logs_debug_and_uses_subset_bounds(self, caplog):
tests/test_ui_layout.py:544:        from vibecomfy.porting.layout.groups import build_subgraph_groups
tests/test_ui_layout.py:549:                "subgraphs": [
tests/test_ui_layout.py:573:            groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)
tests/test_ui_layout.py:598:    """Same subgraph name → same colour regardless of ordering or workflow."""
tests/test_ui_layout.py:600:    def test_same_subgraph_name_gets_same_color(self):
tests/test_ui_layout.py:601:        from vibecomfy.porting.layout.groups import build_subgraph_groups
tests/test_ui_layout.py:603:        def _make_wf_with_subgraph(name: str):
tests/test_ui_layout.py:607:                    "subgraphs": [
tests/test_ui_layout.py:627:        wf_a = _make_wf_with_subgraph("MySubgraph")
tests/test_ui_layout.py:628:        wf_b = _make_wf_with_subgraph("MySubgraph")
tests/test_ui_layout.py:629:        groups_a = build_subgraph_groups(wf_a, positions=positions, sizes=sizes)
tests/test_ui_layout.py:630:        groups_b = build_subgraph_groups(wf_b, positions=positions, sizes=sizes)
tests/test_ui_layout.py:632:            "Same subgraph name must produce the same colour across workflows"
tests/test_ui_layout.py:635:    def test_different_subgraph_names_may_differ(self):
tests/test_ui_layout.py:636:        from vibecomfy.porting.layout.groups import build_subgraph_groups
tests/test_ui_layout.py:638:        def _make_wf_with_subgraph(name: str):
tests/test_ui_layout.py:642:                    "subgraphs": [
tests/test_ui_layout.py:661:        wf_a = _make_wf_with_subgraph("AlphaSubgraph")
tests/test_ui_layout.py:662:        wf_b = _make_wf_with_subgraph("BetaSubgraph")
tests/test_ui_layout.py:663:        groups_a = build_subgraph_groups(wf_a, positions=positions, sizes=sizes)
tests/test_ui_layout.py:664:        groups_b = build_subgraph_groups(wf_b, positions=positions, sizes=sizes)
tests/test_ui_layout.py:672:    def test_known_role_subgraph_gets_mapped_color(self):
tests/test_ui_layout.py:675:            _role_color_for_subgraph,
tests/test_ui_layout.py:679:        colour = _role_color_for_subgraph("UUID-abc-123-def")
tests/test_ui_layout.py:681:            f"UUID subgraph should get teal (#3f7e7e), got {colour}"
tests/test_ui_layout.py:684:    def test_vhs_subgraph_gets_plum(self):
tests/test_ui_layout.py:686:            _role_color_for_subgraph,
tests/test_ui_layout.py:690:        colour = _role_color_for_subgraph("VHS_VideoCombine")
tests/test_ui_layout.py:692:            f"VHS subgraph should get plum (#7e3f7e), got {colour}"
tests/test_ui_layout.py:1490:    """T8: emit_ui_json groups array includes engine-generated subgraph groups."""
tests/test_ui_layout.py:1492:    def test_emit_ui_json_groups_include_subgraphs(self):
tests/test_ui_layout.py:1493:        """When the workflow has subgraph definitions, emitted groups contain subgraph boxes."""
tests/test_ui_layout.py:1497:        wf = VibeWorkflow("subgraph_test", WorkflowSource("subgraph_test"))
tests/test_ui_layout.py:1502:        # Attach subgraph definition whose inner nodes match the flat nodes above.
tests/test_ui_layout.py:1505:                "subgraphs": [
tests/test_ui_layout.py:1539:                "subgraphs": [
tests/test_ui_layout.py:1603:        # Attach a subgraph so engine_groups is non-empty (exercises group merge path).
tests/test_ui_layout.py:1606:                "subgraphs": [
tests/test_graph_inspection.py:291:    def test_single_node_extracts_id_and_class_type(self, single_node_graph: dict) -> None:
tests/test_graph_inspection.py:298:    def test_single_node_extracts_widgets(self, single_node_graph: dict) -> None:
tests/test_graph_inspection.py:307:    def test_node_title_extracted(self, graph_with_title: dict) -> None:
tests/test_graph_inspection.py:316:    def test_vibe_graph_dict_nodes_extracts_widgets_and_edges(
tests/test_graph_inspection.py:444:    def test_output_slots_extracted(self, graph_with_outputs: dict) -> None:
tests/test_graph_inspection.py:464:    def test_list_edges_extracted(self, two_node_graph_list_links: dict) -> None:
tests/test_graph_inspection.py:472:    def test_dict_edges_extracted(self, two_node_graph_dict_links: dict) -> None:
tests/test_scope.py:9:    sanitize_subgraph_name,
tests/test_scope.py:74:def test_sanitize_subgraph_name():
tests/test_scope.py:75:    assert sanitize_subgraph_name("a/b#c") == "a_b_c"
tests/test_porting_assets.py:82:def test_python_metadata_extractor_resolves_literal_module_constants(tmp_path: Path) -> None:
tests/test_porting_assets.py:101:def test_legacy_raw_workflow_extractor_still_returns_only_url_bearing_assets() -> None:
tests/test_reorganise_validate.py:47:def _subgraph_ui() -> dict:
tests/test_reorganise_validate.py:52:            "subgraphs": [
tests/test_reorganise_validate.py:417:    facts = extract_graph_facts(_subgraph_ui())
tests/test_reorganise_validate.py:468:    assert _codes(orphan_inner_report) == ["subgraph_boundary_violation"]
tests/test_cli_analyze.py:25:    assert "uuid_subgraph_instances" in payload

exec
/bin/zsh -lc "sed -n '1,100p' vibecomfy/porting/emit/emit_subgraph.py && rg -n \"class _Node|_Node =|NamedTuple.*_Node\" vibecomfy/porting/emit/emit_subgraph.py && rg -n \"inputs\\[.*\\]\\s*=\\s*\\[|inputs=.*\\[["'^]]+,'"\\s*["'^]]+'"\\]\" vibecomfy --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 26ms:
"""emit_subgraph.py — subgraph definition, naming, and emission helpers.

This module is carved from :mod:`vibecomfy.porting.emitter` as part of the
M2 structural-decomposition epic (Step 5).

All names exported here remain importable from ``vibecomfy.porting.emitter``
via explicit re-exports so that existing callers are unaffected.
"""

from __future__ import annotations

import hashlib
import json
import keyword as _keyword
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.emit.emit_constants import (
    UI_ONLY_CLASS_TYPES,
    _translate_widget_for_key,
    _ui_widget_aliases,
)
from vibecomfy.porting.emit.emit_kwargs import (
    _apply_locked_variable_names,
    _assignment_target,
    _compute_output_variable_names,
    _compute_variable_names,
    _edge_ref_expr,
    _edges_in_with_subgraph_external_refs,
    _first_output_var,
    _format_metadata_dict,
    _format_value,
    _is_any_link,
    _is_link,
    _live_output_slots_for_function,
    _node_kwargs,
    _node_output_names,
    _safe_output_name,
    _safe_var,
    _topological_node_order,
    _ui_output_names,
)
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA

if TYPE_CHECKING:
    from vibecomfy.porting.emitter import EmissionDiagnostic

logger = logging.getLogger(__name__)

READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND = "subgraph_input_unbound"

__all__ = [
    "_SubgraphPort",
    "_SubgraphDef",
    "slugify_subgraph_name",
    "_slugify_identifier",
    "_safe_kwarg_name",
    "_subgraph_input_kwarg_name",
    "_unique_port_name",
    "_subgraph_definitions_from_raw",
    "_disambiguated_subgraph_slugs",
    "_build_subgraph_def",
    "subgraph_source_hash",
    "_subgraph_default_args",
    "_widget_default_for_target",
    "_apply_subgraph_names_to_prepared",
    "_subgraph_result_base",
    "_unique_var",
    "COMFY_TYPE_TO_PY_HINT",
    "_emit_subgraph_functions",
    "_subgraph_topological_order",
    "_short_subgraph_id_prefix",
    "_subgraph_emitted_node_id",
    "_subgraph_node_id_required",
    "_subgraph_signature",
    "_subgraph_docstring",
    "_emit_subgraph_call_statement",
    "_subgraph_call_kwargs",
    "_subgraph_instance_port_candidate_names",
    "_subgraph_instance_widget_values",
    "_positional_ui_widget_names",
    "_ui_widget_values_by_name",
    "_subgraph_return_expr",
]


@dataclass(frozen=True, slots=True)
class _SubgraphPort:
    name: str
    type: str | None = None
    source_name: str | None = None
    external_ref: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class _SubgraphDef:

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/emit_subgraph.py | sed -n '90,150p' && rg -n \"_Node\" vibecomfy/porting/emit/emit_subgraph.py | head -20 && rg -n \"inputs\\[["'^]]+'"\\]\\s*=\\s*\\[["'^]]+,'"\\s*["'^]]+'"\\]\" vibecomfy --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 231ms:
    90	
    91	@dataclass(frozen=True, slots=True)
    92	class _SubgraphPort:
    93	    name: str
    94	    type: str | None = None
    95	    source_name: str | None = None
    96	    external_ref: tuple[str, int] | None = None
    97	
    98	
    99	@dataclass(frozen=True, slots=True)
   100	class _SubgraphDef:
   101	    id: str
   102	    raw_name: str
   103	    slug: str
   104	    inputs: tuple[_SubgraphPort, ...]
   105	    outputs: tuple[_SubgraphPort, ...]
   106	    nodes: dict[str, Any]
   107	    edges_in: dict[str, list[Any]]
   108	    input_refs: dict[tuple[str, str], str]
   109	    default_args: dict[str, Any]
   110	    return_refs: tuple[tuple[str, int], ...]
   111	    source_hash: str
   112	    source_path: str | None = None
   113	def slugify_subgraph_name(name: str, fallback_uuid: str) -> str:
   114	    if not name:
   115	        return f"subgraph_{fallback_uuid[:8].lower()}"
   116	    name = re.sub(r"(?<=[A-Za-z])\.(?=\d)", "", name)
   117	    slug = name.lower()
   118	    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
   119	    slug = re.sub(r"_+", "_", slug).strip("_")
   120	    if not slug or slug[0].isdigit():
   121	        slug = f"subgraph_{slug}" if slug else f"subgraph_{fallback_uuid[:8].lower()}"
   122	    if _keyword.iskeyword(slug):
   123	        slug = f"{slug}_"
   124	    return slug
   125	
   126	
   127	_GENERIC_SUBGRAPH_LABELS: frozenset[str] = frozenset(
   128	    {
   129	        "arg",
   130	        "argument",
   131	        "input",
   132	        "inputs",
   133	        "output",
   134	        "outputs",
   135	        "parameter",
   136	        "param",
   137	        "value",
   138	    }
   139	)
   140	
   141	
   142	def _slugify_identifier(value: str) -> str:
   143	    candidate = str(value or "").lower()
   144	    candidate = re.sub(r"[^a-z0-9_]+", "_", candidate)
   145	    candidate = re.sub(r"_+", "_", candidate).strip("_")
   146	    if _keyword.iskeyword(candidate):
   147	        candidate = f"{candidate}_"
   148	    return candidate
   149	
   150	
237:    from vibecomfy.workflow import VibeEdge as _Edge, VibeNode as _Node
305:        nodes[str(node_id)] = _Node(
vibecomfy/testing/canonical.py:163:                new_inputs[key] = [labels.get(src, src), slot]
vibecomfy/porting/emit/emit_subgraph.py:340:                    nodes[str(node_id)].inputs[str(key)] = ["-10", len(input_ports) - 1]

exec
/bin/zsh -lc 'git diff --unified=90 8a8300bb..0d2bb176 -- vibecomfy/porting/emit/ui.py vibecomfy/commands/port/_export.py vibecomfy/porting/layout_store.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/commands/port/_export.py b/vibecomfy/commands/port/_export.py
index a56f9d60..524fd4e0 100644
--- a/vibecomfy/commands/port/_export.py
+++ b/vibecomfy/commands/port/_export.py
@@ -1,96 +1,97 @@
 from __future__ import annotations
 
 import argparse
 import dataclasses
 import json
 import sys
+from copy import deepcopy
 from pathlib import Path
 from typing import Any
 
 from vibecomfy.commands._diagnostics import Diagnostic, diagnostics_to_json, diagnostics_to_text
 from vibecomfy.porting.layout_store import read_store, store_from_ui_json, write_store
 from vibecomfy.porting.latency import FALLBACK_LATENCY_BUDGET_MS
 from vibecomfy.porting.emit.ui import default_output_path
 
 
 def _print_change_report(
     report: Any,
     *,
     json_mode: bool = False,
     prior_store_existed: bool | None = None,
 ) -> None:
     """Print a ChangeReport to stderr (text) or stdout (JSON)."""
     from dataclasses import asdict  # noqa: PLC0415
     if json_mode:
         print(json.dumps({"change_report": asdict(report)}, indent=2, sort_keys=True))
     else:
         ce = report.content_edits
         ids = report.identity_stabilization
         lines = ["[change-report]"]
         lines.append(
             f"  content: preserved={len(ce.preserved)} edited={len(ce.edited)}"
             f" new={len(ce.new_auto_placed)} removed={len(ce.removed)}"
             f" virtual_wires_degraded={len(ce.virtual_wires_degraded)}"
         )
         # removed_named entries (uid + class_type per removed node)
         removed_named = getattr(ce, "removed_named", None) or []
         if removed_named:
             lines.append(f"  removed_named: {len(removed_named)} entry/ies")
             for rn in removed_named:
                 lines.append(f"    uid={rn['uid']} class={rn.get('class_type', 'unknown')}")
         # stripped_helpers count
         stripped = getattr(ce, "stripped_helpers", None) or []
         if stripped:
             lines.append(f"  stripped_helpers: {len(stripped)}")
         # no prior layout found marker — fires on a genuine fresh layout:
         # prior store absent, nodes were placed, and no named removals or stripped helpers.
         if (
             prior_store_existed is False
             and ce.new_auto_placed
             and not removed_named
             and not stripped
         ):
             lines.append("  no prior layout found — fresh layout applied")
         if ids.bridge_minted:
             lines.append(f"  identity: bridge_minted={len(ids.bridge_minted)}")
         if ids.unmatched_legacy:
             lines.append(f"  identity: unmatched_legacy={len(ids.unmatched_legacy)}")
         if ids.definition_relayout:
             lines.append(f"  identity: definition_relayout={ids.definition_relayout}")
         print("\n".join(lines), file=sys.stderr)
 
 
 def _print_from_overrides(
     overrides: dict[str, Any],
     *,
     json_mode: bool = False,
 ) -> None:
     """Print ``--from`` overrides (conflict resolution) to stderr or stdout.
 
     Called when both a sidecar and ``--from`` exist and ``--from`` entries
     override specific UIDs.  The sidecar is the base; ``--from`` provides
     explicit per-uid overrides.
     """
     if json_mode:
         print(json.dumps({"from_overrides": sorted(overrides.keys())}, indent=2, sort_keys=True))
     else:
         lines = [f"[from-overrides] {len(overrides)} uid(s) overridden from --from:"]
         for uid in sorted(overrides):
             lines.append(f"  {uid}")
         print("\n".join(lines), file=sys.stderr)
 
 
 def _print_recovery_report(
     recovery_report: list[dict[str, Any]],
     *,
     json_mode: bool = False,
 ) -> None:
     """Print a structured recovery report to stderr (text) or stdout (JSON).
 
     The recovery report is populated by ``emit_ui_json`` only on the non-strict
     warn-and-emit path.  It records per-node provenance for schema-less nodes,
     low-confidence widget-schema-fallback nodes, and any widget-length-check
     warnings encountered during emission.
 
     Precedence note: ``--strict`` fails *before* the report is populated
     (``emit_ui_json`` raises ``ValueError``) — the except-arm in
@@ -356,208 +357,208 @@ def _resolve_preserve_source(
             merged["entries"] = merged_entries
             return merged, str(py_path), overrides, from_ui_payload
         else:
             # No differences — sidecar is authoritative
             return sidecar_store, str(py_path), None, None
 
     # 3. --from <path> only
     if from_path:
         store = store_from_ui_json(from_path)
         return store, str(from_path), None, _read_ui_payload(from_path)
 
     # 4. Sidecar only
     if sidecar_store:
         return sidecar_store, str(py_path), None, None
 
     # 5. Breadcrumb auto-discovery: look for a prior emitted UI JSON at the
     #    default output path and check its extra.vibecomfy.prior_path.
     candidate_path = default_output_path(workflow, source_template=py_path.stem)
     if candidate_path.exists():
         try:
             candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
             extra_vc = candidate.get("extra", {}).get("vibecomfy", {})
             breadcrumb_prior = extra_vc.get("prior_path")
             if breadcrumb_prior and Path(breadcrumb_prior).resolve() == py_path.resolve():
                 store = store_from_ui_json(candidate_path)
                 return store, str(candidate_path), None, candidate
         except (json.JSONDecodeError, OSError):
             pass
 
     # 6. No source → fresh
     return None, None, None, None
 
 
 def _read_ui_payload(path: str | Path) -> dict[str, Any] | None:
     try:
         candidate = json.loads(Path(path).read_text(encoding="utf-8"))
     except (json.JSONDecodeError, OSError, TypeError):
         return None
     if isinstance(candidate, dict) and isinstance(candidate.get("nodes"), list):
         return candidate
     return None
 
 
 def _cmd_port_export(args: argparse.Namespace) -> int:
     from vibecomfy.commands import port as _port
 
     if args.to == "json":
         try:
             schema_provider = _port._build_authoring_provider(args)
             workflow = _port.load_workflow_reference(
                 args.workflow,
                 schema_provider=schema_provider,
                 allow_scratchpad=True,
                 ready=getattr(args, "ready", False),
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
+            if store is not None and "groups" in store:
+                workflow.groups = deepcopy(store["groups"])
 
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
-            sidecar_groups = store.get("groups") if store else None
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
-                groups=sidecar_groups,
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
                         schema_provider=schema_provider,
                         force_drop_editor_only=True,
                         **_emit_kwargs,
                     )
                 else:
                     raise
             if args.out:
                 out_path = Path(args.out)
             else:
                 out_path = default_output_path(workflow, source_template=py_path.stem)
             change_report_path = Path(
                 getattr(args, "change_report_out", "") or _default_change_report_path(out_path)
             )
             include_virtual_wires = not getattr(args, "no_virtual_wires", False)
             reroute_uids = (
                 frozenset()
                 if getattr(args, "fresh", False) or not include_virtual_wires
                 else _reroute_uids_for_workflow(workflow)
             )
             felt_report = (
                 _port.evaluate_felt_delta(
                     store,
                     ui_payload,
                     change_report_out[0],
                     reroute_uids=reroute_uids,
                 )
                 if change_report_out
                 else None
             )
             artifact_payload = (
                 _artifact_payload(change_report=change_report_out[0], felt_report=felt_report)
                 if change_report_out and felt_report is not None
                 else None
             )
 
             dry_run = getattr(args, "dry_run", False)
             if dry_run:
                 print(f"[dry-run] would write to {out_path}", file=sys.stderr)
                 if artifact_payload is not None:
                     print(f"[dry-run] would write to {change_report_path}", file=sys.stderr)
             else:
                 if artifact_payload is not None:
                     change_report_path.parent.mkdir(parents=True, exist_ok=True)
                     change_report_path.write_text(
                         json.dumps(artifact_payload, indent=2, sort_keys=True),
                         encoding="utf-8",
                     )
                 if felt_report is not None and not felt_report.ok and not felt_report.skipped_snapshot_absent:
                     _print_felt_violation_summary(felt_report, artifact_path=change_report_path)
                     return 5
                 out_path.parent.mkdir(parents=True, exist_ok=True)
                 out_path.write_text(json.dumps(ui_payload, indent=2, sort_keys=True), encoding="utf-8")
                 print(f"wrote {out_path}")
             if dry_run and felt_report is not None and not felt_report.ok and not felt_report.skipped_snapshot_absent:
                 _print_felt_violation_summary(felt_report, artifact_path=change_report_path)
                 return 5
 
             # Emit layout sidecar alongside the UI JSON (best-effort).
             # Build the store from the freshly-emitted ui_payload (which carries
             # correct positions in properties['vibecomfy_uid']).  Do NOT call
             # write_layout(py_path, workflow) here: a workflow loaded from a .py
             # file has no _ui metadata so write_layout would overwrite the valid
             # convert-time sidecar with empty entries.
             if not dry_run:
                 try:
                     write_store(py_path, store_from_ui_json(ui_payload))
                 except Exception as exc:  # noqa: BLE001 - main UI JSON remains authoritative
                     sidecar_path = py_path.with_suffix(".layout.json")
                     sidecar_diagnostic = Diagnostic(
                         code="sidecar_write_failed",
                         message=(
                             f"UI JSON export succeeded, but layout sidecar {sidecar_path} "
                             f"could not be written: {type(exc).__name__}: {exc}"
diff --git a/vibecomfy/porting/emit/ui.py b/vibecomfy/porting/emit/ui.py
index 92a8de5e..922d1c14 100644
--- a/vibecomfy/porting/emit/ui.py
+++ b/vibecomfy/porting/emit/ui.py
@@ -1,565 +1,604 @@
 """Emit a VibeWorkflow IR back to a litegraph (ComfyUI editor) JSON envelope.
 
 This is the inverse direction of ingest: ``from_ui`` reads litegraph
 JSON into the ``VibeWorkflow`` IR; :func:`emit_ui_json` renders an IR back out to the
 litegraph shape that the ComfyUI web editor loads. It is a NEW standalone function and
 deliberately NOT a ``VibeWorkflow.compile`` backend — ``compile("api")`` must stay
 byte-for-byte identical and only ever produces the runtime API dict.
 
 Identity preservation is **best-effort**, not lossless:
 
 - ``properties["vibecomfy_uid"]`` is the stable identity key for nodes that carry a uid
   (source-derived nodes ingested from litegraph JSON). Use this for round-trip lookup.
 - ``properties["vibecomfy_id"]`` is a display-only forward label (the emitter's
   variable / role name, ``{class_type}_{order}``). It renumbers on edits and must NEVER
   be used as a match key. Always present as a fallback when uid is absent.
 - ``properties["Node name for S&R"]`` is the litegraph node type, as the editor expects.
 - ``properties["ir_node_id"]`` is **no longer emitted** (demoted in M5). Any stale
   ``ir_node_id`` value from a captured properties blob is scrubbed before emission.
 
 Node ids in the litegraph envelope are integers (the editor format requires it): digit
 VibeNode ids keep their numeric value (``"98"`` → ``98``); non-digit ids are assigned
 fresh integers above the highest digit id. Parity is unaffected because the normalizer
 ``str()``-coerces every node id on read-back. The top-level ``links[]`` are 6-element
 arrays ``[link_id, from_node, from_slot, to_node, to_slot, type]`` over those integer
 ids; ``definitions.subgraphs[].links[]`` (emitted only when the IR carries definitions)
 use the litegraph OBJECT shape. ``SetNode``/``GetNode`` broadcast helpers are resolved
 into direct links via :func:`collect_broadcast_sources` and omitted from ``nodes``.
 
 No promise of lossless preservation is made. The envelope is byte-deterministic for a
 given IR: same IR in → same JSON out. All node geometry is stubbed and isolated in the
 single :func:`_stub_layout` helper, which M2 will replace with real layout; this module
 carries no layout-quality logic of its own.
 
 ``widgets_values`` emission rule (verified empirically against the Comfy oracle)
 -------------------------------------------------------------------------------
 ComfyUI's ``convert_ui_to_api`` reads ``widgets_values`` *positionally* against the
 raw object-info widget order, including ``None``-named UI-only slots such as
 KSampler's ``control_after_generate`` position. Therefore the emitted array is laid
 out against that raw order: named positions take the node's current value, ``None``
 positions preserve the captured source value when available, and seed control slots
 fall back to the documented ``"fixed"`` value. Trailing ``None`` is trimmed.
 
 The retained ``VibeNode.metadata["control_after_generate"]`` — or the documented
 ``"fixed"`` default when absent — is recorded in the recovery report under
 ``control_after_generate`` with a ``control_after_generate_defaulted`` flag.
 
 Input-slot ``widget`` objects: only inputs that are actually LINKED get an entry in the
 node ``inputs`` array; an entry whose name is a widget-type input additionally carries
 ``"widget": {"name": <name>}`` (a widget converted to a link). Unlinked widget-type
 inputs get NO input-slot entry — they live in ``widgets_values``.
 """
 
 from __future__ import annotations
 
 import hashlib
 import json
 import re
 import uuid
 import warnings
 from collections import defaultdict
 from copy import deepcopy
 from pathlib import Path
 from collections.abc import Mapping
 from dataclasses import dataclass
 from typing import Any
 
 from vibecomfy._compile._helpers import (
     broadcast_name,
     collect_broadcast_sources,
     is_broadcast_helper_class_type,
 )
 from vibecomfy.contracts.intent_nodes import (
     CLASS_TYPE_TO_KIND,
     KIND_TO_CLASS_TYPE,
     is_intent_class_type,
     intent_node_payload_from_metadata,
     validate_intent_node_contract,
     validate_runtime_code_contract,
 )
 from vibecomfy.identity.uid import mint_local_uid
 from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
 from vibecomfy.porting.widgets.aliases import widget_names_for_class, widget_names_from_schema
-from vibecomfy.workflow import VibeEdge, VibeNode
+from vibecomfy.workflow import VibeEdge, VibeNode, _get_node_mode
 
 # Documented default control_after_generate mode when none is retained in metadata.
 _CONTROL_AFTER_GENERATE_DEFAULT = "fixed"
 
 # Stable namespace so a given workflow id always yields the same envelope id.
 _ENVELOPE_ID_NAMESPACE = uuid.UUID("6f1d2c3a-4b5e-4a6c-8d9e-0f1a2b3c4d5e")
 
 # Litegraph editor format version this emitter targets.
 _LITEGRAPH_VERSION = 1.0
 
 # Layout-schema version stamped into the breadcrumb (extra.vibecomfy.layout_version).
 # M2 replaces _stub_layout with real layout and will bump this. M3 preserve-mode keys
 # off the breadcrumb, so the version travels with the file.
 _LAYOUT_VERSION = "m4"
 
 # Default directory and subdirectory for emitted UI exports.
 _DEFAULT_OUT_DIR = "out"
 _UI_EXPORT_SUBDIR = "ui_export"
 
 # Deterministic grid geometry constants used only by ``_stub_layout``.
 _STUB_COLUMN_WIDTH = 400
 _STUB_ROW_HEIGHT = 200
 _STUB_COLUMNS = 4
 _STUB_NODE_SIZE = [320, 180]
 
 # M2 canonicalization precision (2 decimal places) for all emitted coordinates.
 # Every pos/size/group-bounding value is rounded through this precision so two
 # machines emit byte-identical JSON regardless of CWD, env, or float quirks.
 _M2_PRECISION = 2
 
 # Fixed default canvas drag/scale state for ``extra.ds`` when
 # ``include_main_positions=True`` and no sidecar ``extra`` provides overrides.
 _DEFAULT_DS = {"scale": 1.0, "offset": [0.0, 0.0]}
 
 
 def _intent_recovery_fields(node: Any) -> dict[str, Any]:
     class_type = str(getattr(node, "class_type", ""))
     payload = intent_node_payload_from_metadata(getattr(node, "metadata", None))
     intent_result = validate_intent_node_contract(
         node_id=str(getattr(node, "id", "")),
         class_type=class_type,
         metadata=getattr(node, "metadata", None),
     )
     runtime_result = validate_runtime_code_contract(
         class_type=class_type,
         payload=payload,
         require_runtime=True,
     )
     runtime_backed = (
         class_type == KIND_TO_CLASS_TYPE["code"]
         and intent_result.ok
         and runtime_result.ok
     )
     return {
         "uid": getattr(node, "uid", None) or intent_result.vibecomfy_uid,
         "kind": intent_result.kind or CLASS_TYPE_TO_KIND.get(class_type),
         "lowered": False,
         "runtime_backed": runtime_backed,
         "runtime_contract_valid": runtime_result.ok,
         "intent_contract_valid": intent_result.ok,
         "contract_problem_codes": [
             problem.code for problem in (*intent_result.problems, *runtime_result.problems)
         ],
     }
 
 # Confidence threshold at or below which a node is considered low-confidence.
 # widget_schema_fallback tier uses confidence=0.3; strict=True rejects it.
 _LOW_CONFIDENCE_THRESHOLD = 0.3
 _STATIC_WIDGET_OVERFLOW_TOLERANCE = 4
 _STATIC_RAW_WIDGET_SLACK_CLASSES = frozenset(
     {"CheckpointLoaderSimple", "KSampler", "KSamplerAdvanced"}
 )
 _PRIMITIVE_CONTROL_WIDGET_CLASSES = frozenset(
     {"PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt"}
 )
 
 
 @dataclass(frozen=True, slots=True)
 class WidgetShapeEvidence:
     node_id: str
     class_type: str
     schema_less: bool
     confidence: float | None
     raw_widget_count: int | None
     candidate_widget_count: int
     schema_widget_count: int | None
     compacted_widget_names: tuple[str, ...]
     raw_widget_shape: str | None
     has_dict_rows: bool
     overflow: bool
     provider: str | None
     explicit_widget_overflow: bool = False
     raw_widget_length_recovered: bool = False
     value_domain: str = "compact"
 
 
 def _canonicalize_coord(value: float) -> float:
     """Round a coordinate value to M2 precision (2 decimal places).
 
     Every pos/size/group-bounding value emitted by this module passes through this
     helper so two machines produce byte-identical JSON regardless of CWD, env,
     or minor float-representation differences.
     """
     return round(value, _M2_PRECISION)
 
 
 def _canonicalize_group_geometry(groups: list[dict[str, Any]]) -> None:
     """Canonicalize ``bounding`` arrays in-place for every group in ``groups``.
 
     Each group's ``bounding`` is ``[x, y, width, height]`` — all four values are
     rounded to M2 precision.  Groups without a valid ``bounding`` are left alone.
     This guarantees byte-identical group geometry across machines when
     ``include_main_positions=True``.
     """
     for g in groups:
         bbox = g.get("bounding")
         if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
             g["bounding"] = [
                 _canonicalize_coord(float(bbox[0])),
                 _canonicalize_coord(float(bbox[1])),
                 _canonicalize_coord(float(bbox[2])),
                 _canonicalize_coord(float(bbox[3])),
             ]
 
 
 def _stub_layout(order: int) -> dict[str, list[float]]:
     """Return deterministic placeholder geometry for the ``order``-th emitted node.
 
     ALL layout decisions live here. The grid is a pure function of emission order, so
     the same IR always produces identical positions. M2 replaces this helper with real
     layout; nothing elsewhere in the emitter reasons about geometry.
     """
     col = order % _STUB_COLUMNS
     row = order // _STUB_COLUMNS
     return {
         "pos": [
             _canonicalize_coord(float(col * _STUB_COLUMN_WIDTH)),
             _canonicalize_coord(float(row * _STUB_ROW_HEIGHT)),
         ],
         "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
     }
 
 
 def _extract_geometry(layout_entry: dict | None) -> dict[str, list[float]] | None:
     """Extract {pos, size} from a layout-store entry, or None.
 
     This isolates the pos/size geometry chain from the furniture resolver so the
     two paths never accidentally couple.  A layout entry that is ``None`` or
     lacks a valid ``pos`` returns ``None``, letting the caller fall through to
     ``_captured_geometry`` or ``_stub_layout``.
     """
     if not isinstance(layout_entry, dict):
         return None
     pos = layout_entry.get("pos")
     size = layout_entry.get("size")
     if not isinstance(pos, (list, tuple)) or len(pos) < 2:
         return None
     if not isinstance(size, (list, tuple)) or len(size) < 2:
         return None
     return {
         "pos": [_canonicalize_coord(float(pos[0])), _canonicalize_coord(float(pos[1]))],
         "size": [_canonicalize_coord(float(size[0])), _canonicalize_coord(float(size[1]))],
     }
 
 
 def _resolve_furniture(
     node: Any,
     layout_entry: dict | None,
 ) -> dict[str, Any]:
-    """Resolve furniture (flags, color, bgcolor, mode, properties, title) from sidecar or metadata.
+    """Resolve display furniture while taking mode only from the IR node.
 
     This is a SEPARATE path from the pos/size geometry chain
     (:func:`_captured_geometry`).  Precedence:
 
-    1. Sidecar entry (``layout_entry``) — the authoritative source when a
-       ``.layout.json`` sidecar exists.
-    2. ``node.metadata['_ui']`` — the raw litegraph node dict captured during
-       ingest (the direct-ingest / comfy-gate fallback).
-    3. Legacy ``node.metadata['mode']`` copy, then the first-class
-       ``node.mode`` field (the same authority compile reads).
-    4. Fixed defaults (``flags={}``, ``mode=0``, ``color=None``, ``bgcolor=None``,
+    1. Sidecar entry (``layout_entry``) for flags, colors, properties, and title.
+    2. ``node.metadata['_ui']`` for those same fields when no sidecar exists.
+    3. :func:`vibecomfy.workflow._get_node_mode` for mode.  This is the exact
+       authority used by compilation, including its single legacy ``_ui.mode``
+       fallback.
+    4. Fixed defaults (``flags={}``, ``color=None``, ``bgcolor=None``,
        ``properties={}``, ``title=None``).
 
     Returns a dict with keys ``flags``, ``color``, ``bgcolor``, ``mode``,
     ``properties``, ``title``.
     """
     # Source 1: sidecar entry (authoritative)
     if layout_entry:
         flags = layout_entry.get("flags")
         color = layout_entry.get("color")
         bgcolor = layout_entry.get("bgcolor")
-        mode = layout_entry.get("mode")
         properties = layout_entry.get("properties")
         title = layout_entry.get("title")
     else:
         # Source 2: node.metadata['_ui'] (direct-ingest fallback)
         _ui = getattr(node, "metadata", {}).get("_ui")
         if isinstance(_ui, dict):
             flags = _ui.get("flags")
             color = _ui.get("color")
             bgcolor = _ui.get("bgcolor")
-            mode = _ui.get("mode")
             properties = _ui.get("properties")
             title = _ui.get("title")
         else:
             flags = None
             color = None
             bgcolor = None
-            mode = None
             properties = None
             title = None
 
-    # Source 2.5: legacy ingest furniture fallback.  Old envelopes may carry a
-    # top-level metadata["mode"] copy; re-emit it.  Only an int is accepted —
-    # sidecar (source 1) still wins over this fallback.
-    if mode is None:
-        _meta_mode = getattr(node, "metadata", {}).get("mode")
-        if isinstance(_meta_mode, int):
-            mode = _meta_mode
-
-    # Source 2.75: the first-class VibeNode.mode field (the same authority
-    # compile's _get_node_mode reads).  Ingest and envelope decode populate it
-    # from _ui.mode and leave _ui.mode in place, so sources 2/2.5 normally win;
-    # this only fires for hand-built nodes that set the field directly.
-    if mode is None:
-        _field_mode = getattr(node, "mode", 0)
-        if isinstance(_field_mode, int):
-            mode = _field_mode
-
     # Source 3: fixed defaults
     if not isinstance(flags, dict):
         flags = {}
-    if mode is None or not isinstance(mode, int):
-        mode = 0
     if not isinstance(properties, dict):
         properties = {}
     # title stays None for absent/default — the caller decides whether to emit it
 
     return {
         "flags": flags,
         "color": color,
         "bgcolor": bgcolor,
-        "mode": mode,
+        "mode": _get_node_mode(node),
         "properties": properties,
         "title": title,
     }
 
 
 def _captured_geometry(node: Any) -> dict[str, list[float]] | None:
     """Return {pos, size} from ``node.metadata['_ui']``, or None when absent.
 
     The ``None`` fallthrough is intentional: callers should chain through to
     ``_stub_layout`` when no captured geometry exists (e.g. programmatic nodes
     or workflows loaded from a .py file without a sidecar).
     """
     _ui = getattr(node, "metadata", {}).get("_ui")
     if not isinstance(_ui, dict):
         return None
     pos = _ui.get("pos")
     size = _ui.get("size")
     if not isinstance(pos, (list, tuple)) or len(pos) < 2:
         return None
     if not isinstance(size, (list, tuple)) or len(size) < 2:
         return None
     return {
         "pos": [_canonicalize_coord(float(pos[0])), _canonicalize_coord(float(pos[1]))],
         "size": [_canonicalize_coord(float(size[0])), _canonicalize_coord(float(size[1]))],
     }
 
 
 def _envelope_id(wf: Any) -> str:
     """Deterministic envelope id derived from the workflow id."""
     return str(uuid.uuid5(_ENVELOPE_ID_NAMESPACE, str(getattr(wf, "id", "workflow"))))
 
 
 def _source_template_name(wf: Any) -> str | None:
     """Best-effort source-template name for the breadcrumb / output path.
 
     Prefers an explicit source id, then the source file stem.  The ingest default
     id ``"workflow"`` (and an empty value) is treated as *unnamed* so the IR-hash
     fallback path takes over.  Returns ``None`` when no real name is available.
     """
     source = getattr(wf, "source", None)
     candidate = getattr(source, "id", None) if source is not None else None
     if isinstance(candidate, str) and candidate and candidate != "workflow":
         return candidate
     path = getattr(source, "path", None) if source is not None else None
     if isinstance(path, str) and path:
         stem = Path(path).stem
         if stem:
             return stem
     wf_id = getattr(wf, "id", None)
     if isinstance(wf_id, str) and wf_id and wf_id != "workflow":
         return wf_id
     return None
 
 
 def _source_prior_path(wf: Any) -> str | None:
     """The originating file path (M3 preserve-mode reads extra.vibecomfy.prior_path)."""
     source = getattr(wf, "source", None)
     path = getattr(source, "path", None) if source is not None else None
     return path if isinstance(path, str) and path else None
 
 
 def _ir_hash(wf: Any) -> str:
     """Stable short hash of the IR structure, for naming unnamed sources.
 
     Hashes a canonical, order-independent projection of nodes (id + class_type)
     and edges so the same IR always yields the same name and the path is never
     empty or raising.
     """
     nodes = sorted((nid, node.class_type) for nid, node in wf.nodes.items())
     edges = sorted(
         (e.from_node, e.from_output, e.to_node, e.to_input) for e in wf.edges
     )
     payload = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True)
     return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
 
 
 def _breadcrumb(wf: Any, source_template: str | None, prior_path: str | None) -> dict[str, Any]:
     """Build the ``extra.vibecomfy`` breadcrumb stamped on the envelope/subgraphs."""
     return {
         "layout_version": _LAYOUT_VERSION,
         "source_template": source_template if source_template is not None else _source_template_name(wf),
         "prior_path": prior_path if prior_path is not None else _source_prior_path(wf),
     }
 
 
 def default_output_path(
     wf: Any,
     *,
     out: str | None = None,
     source_template: str | None = None,
     out_dir: str = _DEFAULT_OUT_DIR,
 ) -> Path:
     """Deterministic output path for an emitted UI export.
 
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
         used.add(nxt)
         nxt += 1
     return remap
 
 
+def _remap_ir_groups(
+    wf: Any,
+    order_list: list[str],
+    id_remap: Mapping[str, int],
+) -> list[dict[str, Any]]:
+    """Deep-copy IR groups and resolve live members to LiteGraph integer ids.
+
+    Group membership may have been captured at different boundaries, so each
+    live node contributes aliases for its workflow mapping key, ``node.id``,
+    stable uid, and captured ``_ui.id``.  Numeric aliases accept either their
+    integer or decimal-string form.  Ambiguous aliases and stale members are
+    omitted instead of emitting a dangling reference.
+    """
+    candidates: dict[tuple[str, Any], set[int]] = defaultdict(set)
+
+    def add_alias(value: Any, emitted_id: int) -> None:
+        if isinstance(value, bool):
+            return
+        if isinstance(value, int):
+            candidates[("int", value)].add(emitted_id)
+            candidates[("str", str(value))].add(emitted_id)
+        elif isinstance(value, str) and value:
+            candidates[("str", value)].add(emitted_id)
+            if value.isdigit():
+                candidates[("int", int(value))].add(emitted_id)
+
+    for workflow_node_id in order_list:
+        node = wf.nodes[workflow_node_id]
+        emitted_id = id_remap[workflow_node_id]
+        add_alias(workflow_node_id, emitted_id)
+        add_alias(getattr(node, "id", None), emitted_id)
+        add_alias(getattr(node, "uid", None), emitted_id)
+        raw_ui = getattr(node, "metadata", {}).get("_ui")
+        if isinstance(raw_ui, dict):
+            add_alias(raw_ui.get("id"), emitted_id)
+
+    aliases = {key: next(iter(ids)) for key, ids in candidates.items() if len(ids) == 1}
+    remapped: list[dict[str, Any]] = []
+    for raw_group in deepcopy(getattr(wf, "groups", [])):
+        group = dict(raw_group)
+        members = group.get("nodes")
+        if isinstance(members, list):
+            resolved: list[int] = []
+            for member in members:
+                if isinstance(member, bool):
+                    continue
+                key = (
+                    ("int", member)
+                    if isinstance(member, int)
+                    else ("str", member)
+                    if isinstance(member, str)
+                    else None
+                )
+                if key is not None and key in aliases:
+                    resolved.append(aliases[key])
+            group["nodes"] = resolved
+        elif "nodes" in group:
+            group["nodes"] = []
+        remapped.append(group)
+    return remapped
+
+
 # ── Virtual-wire classification ────────────────────────────────────────────
 # Get/Set broadcast wires + Reroute passthrough are the virtual-wire nodes
 # whose stable channel name (not the edge) is the routing key.
 _VIRTUAL_WIRE_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})
 
 
 def _resolve_broadcast_edges(
     wf: Any,
 ) -> tuple[list[Any], set[str], set[str]]:
     """Resolve SetNode/GetNode broadcast indirection into direct edges.
 
     Reuses :func:`collect_broadcast_sources` (porting/helpers.py) — the broadcast
     resolution is NOT reimplemented here.  A ``SetNode`` captures the value on its input
     under a broadcast name; each ``GetNode`` re-emits that name to one or more consumers
     (one source → many links).  For the litegraph envelope we drop the helper nodes and
     rewire every ``GetNode``-origin edge to the captured real source, so a fan-out of N
     consumers becomes N direct links.  Edges feeding a helper are dropped; an unresolved
     ``GetNode`` reference drops its dangling edges.
 
     Returns ``(effective_edges, broadcast_helper_ids, orphaned_get_ids)`` where
     *orphaned_get_ids* are GetNode IDs whose broadcast name could not be resolved
     to a SetNode source (used for the recovery report in display mode).  When the
     IR carries no broadcast helpers (the common case) the original edge list is
     returned unchanged, so emission stays byte-identical.
     """
     helper_ids = {
         node_id
         for node_id, node in wf.nodes.items()
         if is_broadcast_helper_class_type(node.class_type)
     }
     if not helper_ids:
         return list(wf.edges), helper_ids, set()
 
     sources = collect_broadcast_sources(wf.nodes, wf.edges)
     get_source: dict[str, tuple[str, str]] = {}
     orphaned: set[str] = set()
     for node_id in helper_ids:
         node = wf.nodes[node_id]
         if node.class_type != "GetNode":
             continue
         name = broadcast_name(node)
         src = sources.get(name) if name else None
         if src is not None:
             get_source[node_id] = (str(src[0]), str(src[1]))
         else:
             orphaned.add(node_id)
 
     effective: list[Any] = []
     for edge in wf.edges:
         if edge.to_node in helper_ids:
             continue  # edge into a SetNode/GetNode helper — not a runtime link
         if edge.from_node in helper_ids:
             redirect = get_source.get(edge.from_node)
             if redirect is None:
                 continue  # unresolved broadcast — drop the dangling edge
             effective.append(VibeEdge(redirect[0], redirect[1], edge.to_node, edge.to_input))
         else:
             effective.append(edge)
     return effective, helper_ids, orphaned
 
 
 def _resolve_reroute_edges(
     edges: list[Any],
     nodes: dict[str, Any],
 ) -> list[Any]:
     """Passthrough Reroute nodes: A→Reroute→B becomes A→B (transitive chains).
 
     Returns a new edge list where every edge that originates from a Reroute is
     rewritten to originate from the terminal non-Reroute source, and edges into
     Reroutes are dropped.  When no Reroute nodes exist the list is returned
     unchanged.
     """
     reroute_ids = {nid for nid, n in nodes.items() if n.class_type == "Reroute"}
     if not reroute_ids:
         return list(edges)
 
     # Build inbound map: reroute_id → [(from_node, from_output), ...]
     inbound: dict[str, list[tuple[str, str]]] = {}
     for edge in edges:
         if edge.to_node in reroute_ids:
             inbound.setdefault(edge.to_node, []).append(
                 (edge.from_node, edge.from_output)
             )
 
     # Recursive terminal-source lookup (follows Reroute chains transitively)
     def _terminal(nid: str, visited: frozenset[str]) -> tuple[str, str] | None:
         if nid in visited:
             return None
         ins = inbound.get(nid, [])
         if not ins:
@@ -1927,221 +1966,215 @@ def derive_widget_shape_evidence(
                 except ValueError:
                     continue
         if widget_idxs:
             programmatic_widget_count = max(widget_idxs) + 1
     primitive_control_widget = (
         node.class_type in _PRIMITIVE_CONTROL_WIDGET_CLASSES
         and schema_widget_count == 1
         and candidate_widget_count == 2
         and programmatic_widget_count == 2
         and raw_widget_count is None
         and isinstance(node_widgets, dict)
         and node_widgets.get("widget_1") in {"fixed", "randomize", "increment", "decrement"}
     )
     overflow = False
     explicit_widget_overflow = False
     if schema_widget_count is not None and not provenance["schema_less"]:
         if has_dict_rows:
             overflow = largest_observed_count > schema_widget_count
         elif primitive_control_widget:
             overflow = False
         elif (
             node.class_type in _STATIC_RAW_WIDGET_SLACK_CLASSES
             and candidate_widget_count <= schema_widget_count + _STATIC_WIDGET_OVERFLOW_TOLERANCE
             and (
                 raw_widget_count is not None
                 or programmatic_widget_count <= schema_widget_count
             )
             and (
                 raw_widget_count is None
                 or programmatic_widget_count <= raw_widget_count
             )
         ):
             overflow = False
         elif (
             programmatic_widget_count > schema_widget_count
             and not (raw_widget_count is not None and programmatic_widget_count <= raw_widget_count)
         ):
             overflow = True
             explicit_widget_overflow = True
         else:
             overflow = largest_observed_count > schema_widget_count
             explicit_widget_overflow = (
                 programmatic_widget_count > schema_widget_count
                 and not (
                     raw_widget_count is not None
                     and programmatic_widget_count <= raw_widget_count
                 )
             )
 
     raw_widget_length_recovered = False
     raw_widgets = getattr(node, "raw_widgets", None)
     if raw_widgets is not None and getattr(raw_widgets, "length", None) is None:
         raw_widget_length_recovered = raw_widget_count is not None
 
     return WidgetShapeEvidence(
         node_id=str(node.id),
         class_type=str(node.class_type),
         schema_less=bool(provenance["schema_less"]),
         confidence=provenance.get("confidence"),
         raw_widget_count=raw_widget_count,
         candidate_widget_count=candidate_widget_count,
         schema_widget_count=schema_widget_count,
         compacted_widget_names=tuple(
             name
             for index, name in enumerate(widget_names)
             if name is not None and name != f"widget_{index}"
         ),
         raw_widget_shape=raw_widget_shape,
         has_dict_rows=has_dict_rows,
         overflow=overflow,
         provider=provenance.get("provider"),
         explicit_widget_overflow=explicit_widget_overflow,
         raw_widget_length_recovered=raw_widget_length_recovered,
         value_domain=value_domain,
     )
 
 
 def emit_ui_json(
     wf: Any,
     *,
     schema_provider: Any = None,
     prior_store: Mapping[str, Any] | None = None,
     layout: Any = None,
     anchors: dict[str, Any] | None = None,
     strict: bool = False,
     recovery_report: list[dict[str, Any]] | None = None,
     source_template: str | None = None,
     prior_path: str | None = None,
     include_main_positions: bool = False,
     include_virtual_wires: bool = True,
-    groups: list[dict[str, Any]] | None = None,
     extra: dict[str, Any] | None = None,
     definitions: dict[str, Any] | None = None,
     change_report_out: list | None = None,
     guard_original_ui: Mapping[str, Any] | None = None,
     guard_resolved_ops: Any = None,
     prior_ui_payload: Mapping[str, Any] | None = None,
     force_drop_editor_only: bool = False,
 ) -> dict[str, Any]:
     """Render ``wf`` (a ``VibeWorkflow``) to a litegraph JSON envelope.
 
     Args:
         wf: The IR workflow to emit.
         schema_provider: Schema source used for slot/type resolution.  Consulted
             via ``get_schema(class_type)`` for each node.  Pass ``None`` to skip
             schema resolution (all edges emit with slot 0 and empty type).
         prior_store: Full prior-store envelope (``{entries, groups, extra,
             definitions, virtual_wires}``) from a previously written sidecar.
             ``entries`` (keyed by node uid) feeds the legacy
             ``_resolve_furniture`` precedence chain and is passed as ``pinned``
             to the layout engine.  The full envelope is also handed to
             :func:`reconcile` once at the top of the function; the resulting
             ``ReconcileResult`` is exposed to the per-node loop as a local
             (``reconcile_result``) for later steps (Step 9b+).
         anchors: New-node placement hints ``{new_uid: anchor_uid, ...}``.
             Routed to :func:`~vibecomfy.porting.layout.placement.place_constrained`
             in the engine (Phase 8) as a dedicated kwarg.  Passing ``None`` or
             ``{}`` leaves existing behavior unchanged.
         strict: When ``True``, raises ``ValueError`` if any node has a schema-less
             class type (``get_schema() == None``) or a low-confidence schema
             (``confidence <= 0.3``, i.e. the ``widget_schema_fallback`` tier).
         recovery_report: Optional mutable list.  If provided, one provenance dict
             is appended per node with keys ``node_id``, ``class_type``,
             ``provider``, ``confidence``, ``schema_less``.  This is the
             **authoritative** record of which schema tier supplied each node's
             output/input resolution.
-        groups: Optional graph-level groups list.  Overrides the IR's own
-            ``wf.groups`` (first-class on ``VibeWorkflow``, populated by the
-            envelope/UI importers).  When omitted, ``wf.groups`` is emitted as
-            the top-level ``groups`` array (``[]`` when unset).  Pass an
-            explicit list (e.g. from a ``.layout.json`` sidecar) to override.
         extra: Optional ``extra`` dict (canvas drag/scale state under ``extra.ds``).
             When provided, merged with the ``vibecomfy`` breadcrumb; otherwise
             only the breadcrumb is emitted.
         definitions: Optional subgraph definitions blob.  When provided from a
             sidecar envelope, used directly instead of re-emitting from IR
             metadata via ``_emit_definitions``.  The caller is responsible for
             passing definitions as they appear in the sidecar's envelope.
         prior_ui_payload: Optional full raw LiteGraph UI JSON used only as raw
             node evidence for future dynamic widget pin/refuse decisions.
             ``prior_store`` remains furniture-only and is not treated as a raw
             node payload source.
 
     Returns:
         A litegraph envelope dict: ``version``, deterministic ``id``,
         ``last_node_id``, ``last_link_id``, ``groups``, ``nodes``, and ``links``.
         Every node carries stamped ``properties`` and stub geometry.  Node outputs
         include ``slot_index``, ``name``, ``type``, and ``links`` (``null`` for
         unwired outputs).  The global ``links`` list holds 6-element arrays
         ``[link_id, from_node, from_slot, to_node, to_slot, type]``.
     """
     # T9a: prior_store is the full envelope ({entries, groups, extra, definitions,
     # virtual_wires}); reconcile() is called once at top and the result exposed to
     # the per-node loop as a local. The legacy ``_resolve_furniture`` chain still
     # reads from ``layout`` (= prior_store['entries']) for this batch — Step 9b
     # will replace that precedence chain with ``reconcile_result.matched``.
     from vibecomfy.porting.layout.reconcile import reconcile as _reconcile  # noqa: PLC0415
     _prior_store: dict[str, Any] = dict(prior_store) if prior_store else {}
     raw_ui_node_map = extract_raw_ui_node_map(prior_ui_payload)
     # Back-compat: callers that still pass the flat ``layout=`` kwarg are wrapped
     # into a minimal envelope so reconcile() sees the entries. Step 9b retires
     # ``layout`` entirely once all call sites migrate to prior_store.
     if layout is not None and not _prior_store:
         _prior_store = {"entries": dict(layout) if isinstance(layout, dict) else {}}
     reconcile_result = _reconcile(wf, _prior_store)
     layout = _prior_store.get("entries", {}) or {}
     anchors = anchors or {}
 
     # ── Editor-ahead detection (T3) ───────────────────────────────────────────
     # When guard_original_ui is supplied, detect editor-only uids early (before
     # expensive emission) and raise EditorAheadError so the caller can abort.
     # An editor-only uid is in the prior store, absent from the IR, and NOT in
     # the VibeComfy-authored set.
     #
     # Authored-uid heuristic: if the prior-store breadcrumb's prior_path matches
     # the current workflow's source path, all prior-store uids were authored by a
     # previous VibeComfy emit of this file → treat them all as authored.
     # If no breadcrumb or path mismatch → authored set is EMPTY so every
     # prior-only uid is conservatively flagged as editor-added.
     if guard_original_ui is not None:
         _prior_store_uids: set[str] = set(_prior_store.get("entries", {}).keys())
         _ir_uids: set[str] = set(wf.nodes.keys())
         _prior_breadcrumb: dict = (_prior_store.get("extra") or {}).get("vibecomfy") or {}
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
@@ -2339,188 +2372,188 @@ def emit_ui_json(
         )
         verdict = _decide_widget_shape(
             evidence,
             raw_widget_payloads={node_id: getattr(node, "raw_widgets", None)},
             raw_payloads={node_id: raw_ui_node} if raw_ui_node is not None else {},
             layout_entries={node_id: layout_entry} if layout_entry is not None else {},
             field_deltas={node_id: field_delta} if field_delta else {},
             link_deltas={node_id: link_delta} if link_delta else {},
             identity_matched=identity_matched,
             allow_schema_default_regenerate=allow_schema_defaults,
             is_new_node=(
                 (node.uid or node_id) in new_node_keys
                 and getattr(node, "raw_widgets", None) is None
                 and raw_ui_node is None
             ),
         )
         widget_shape_verdicts[node_id] = verdict
         widget_shape_default_values[node_id] = (
             _schema_default_widget_values_for_node(node, schema)
             if getattr(verdict, "use_schema_defaults", False)
             else None
         )
 
     refused_verdicts = [
         verdict
         for verdict in widget_shape_verdicts.values()
         if verdict.refuse
     ]
     if refused_verdicts:
         if recovery_report is not None:
             for node_id in order_list:
                 recovery_report.append(
                     _build_recovery_entry(
                         node_prov[node_id],
                         widget_shape_verdicts[node_id],
                         has_raw_ui_payload=widget_shape_raw_payloads[node_id] is not None,
                     )
                 )
         raise _refused_widget_shape(refused_verdicts)
 
     # Sort edges deterministically (from_node asc, from_output, to_node, to_input)
     sorted_edges = sorted(
         display_edges,
         key=lambda e: (e.from_node.zfill(20), e.from_output, e.to_node.zfill(20), e.to_input),
     )
 
     # Assign deterministic link IDs (1-indexed)
     EdgeKey = tuple[str, str, str, str]
     link_id_map: dict[EdgeKey, int] = {
         (e.from_node, e.from_output, e.to_node, e.to_input): idx
         for idx, e in enumerate(sorted_edges, start=1)
     }
     last_link_id = len(sorted_edges)
 
     # Edge lookup by node
     edges_from: dict[str, list[Any]] = defaultdict(list)
     edges_to: dict[str, list[Any]] = defaultdict(list)
     for edge in sorted_edges:
         edges_from[edge.from_node].append(edge)
         edges_to[edge.to_node].append(edge)
 
     # Build nodes
     nodes: list[dict[str, Any]] = []
     last_node_id = max(id_remap.values()) if id_remap else 0
 
     for order, node_id in enumerate(order_list):
         node = wf.nodes[node_id]
         key = _node_key(node_id)
         verdict = widget_shape_verdicts[node_id]
         if verdict.pin_opaque and _exec_io_for_node(node) is None:
             incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
             for edge in edges_to[node_id]:
                 lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
                 incoming_link_ids_by_input[edge.to_input].append(lid)
             outgoing_link_ids_by_slot: dict[int, list[int]] = defaultdict(list)
             for edge in edges_from[node_id]:
                 slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
                 lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
                 outgoing_link_ids_by_slot[slot].append(lid)
             pinned = _raw_ui_payload_for_pin(
                 verdict.raw_ui_node or {},
                 node_id=node_id,
                 class_type=node.class_type,
                 canonical_uid=node.uid,
                 litegraph_node_id=id_remap[node_id],
                 order=order,
                 incoming_link_ids_by_input=incoming_link_ids_by_input,
                 outgoing_link_ids_by_slot=outgoing_link_ids_by_slot,
             )
             # The pinned raw copy comes from raw UI evidence and may lack mode;
-            # stamp the resolved furniture mode (sidecar > _ui.mode >
-            # metadata.mode > node.mode field > 0) onto the emitted node.
+            # stamp the same IR-authoritative mode used by compilation.
             pinned["mode"] = _resolve_furniture(node, matched_entries.get(key))["mode"]
             nodes.append(pinned)
             continue
         matched_entry = matched_entries.get(key)
         # T9b: reconcile-driven merge.
-        #   matched → verbatim pos/size/mode/flags/color/properties/group/title from the entry.
+        #   matched → verbatim pos/size/flags/color/properties/group/title from the entry;
+        #             mode remains IR-authoritative.
         #   else    → engine_positions (already incorporates anchors / pinning), else _stub.
         if matched_entry is not None:
             geometry = (
                 _extract_geometry(matched_entry)
                 or engine_positions.get(node.uid)
                 or _stub_layout(order)
             )
             furniture = _resolve_furniture(node, matched_entry)
         else:
             # Unmatched (new / unmatched_legacy / removed-then-readded).
             # The captured _ui inline on the node (direct-ingest fallback) is the
             # source of truth when present; the engine owns geometry only when
             # no captured _ui exists (programmatic / scratchpad path).
             geometry = (
                 _captured_geometry(node)
                 or engine_positions.get(node.uid)
                 or _stub_layout(order)
             )
             furniture = _resolve_furniture(node, None)
         schema = schema_cache.get(node.class_type)
         schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else []
         exec_io = _exec_io_for_node(node)
 
         # --- outputs list ---
         outputs: list[dict[str, Any]] = []
         # Build a set of (from_output_val) → links for this node from edges
         output_links_by_slot: dict[int, list[int]] = defaultdict(list)
         for edge in edges_from[node_id]:
             slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
             eid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
             output_links_by_slot[slot].append(eid)
 
         if exec_io is not None:
             outputs = _exec_dynamic_outputs(exec_io, output_links_by_slot)
         elif schema_outputs:
             for slot_idx, out_spec in enumerate(schema_outputs):
                 link_list = sorted(output_links_by_slot.get(slot_idx, []))
                 outputs.append({
                     "name": out_spec.name or f"output_{slot_idx}",
                     "type": out_spec.type or "",
                     "links": link_list if link_list else None,
                     "slot_index": slot_idx,
                 })
         elif edges_from[node_id]:
             # Schema-less best-effort: emit one output entry per distinct from_output value,
             # ordered by numeric slot if numeric or by appearance order otherwise.
             seen: dict[str, int] = {}
             for edge in edges_from[node_id]:
                 fo = edge.from_output
                 if fo not in seen:
                     seen[fo] = int(fo) if fo.isdigit() else len(seen)
 
             for fo, slot_idx in sorted(seen.items(), key=lambda kv: kv[1]):
                 link_list = sorted(output_links_by_slot.get(slot_idx, []))
                 outputs.append({
                     "name": fo if not fo.isdigit() else f"output_{slot_idx}",
                     "type": fo.upper() if not fo.isdigit() else "",
                     "links": link_list if link_list else None,
                     "slot_index": slot_idx,
                 })
             # Record schema-less diagnostic in recovery_report (populated below)
             if recovery_report is not None:
                 pass  # appended after the loop; diagnostic is in the provenance entry
 
         # --- widget metadata for this class ---
         widget_names = _widget_names_for_emission(
             node.class_type,
             schema,
             node=node,
             schema_provider=schema_provider,
         )
         widget_name_set = {name for name in widget_names if name is not None}
         full_committed = widget_names_for_class(node.class_type)
         if full_committed is not None:
             widget_name_set.update(n for n in full_committed if n is not None)
 
         # --- inputs list (physical ComfyUI socket order) ---
         # Only LINKED inputs get an input-slot entry; a linked input whose name is a
         # widget-type input additionally carries widget:{name:...} (widget→link).
         incoming_sorted = _ordered_incoming_edges(edges_to[node_id], schema)
         incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
         for edge in incoming_sorted:
             lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
             incoming_link_ids_by_input[edge.to_input].append(lid)
         inputs: list[dict[str, Any]] = []
         if exec_io is not None:
             inputs = _exec_dynamic_inputs(exec_io, incoming_link_ids_by_input)
         else:
             for edge in incoming_sorted:
                 from_class = wf.nodes[edge.from_node].class_type if edge.from_node in wf.nodes else ""
@@ -2576,193 +2609,189 @@ def emit_ui_json(
             incoming_sorted = _ordered_incoming_edges(edges_to[edge.to_node], target_schema)
             to_slot = next(
                 (
                     i
                     for i, e in enumerate(incoming_sorted)
                     if e.to_input == edge.to_input
                     and e.from_node == edge.from_node
                     and e.from_output == edge.from_output
                 ),
                 0,
             )
         if (
             to_exec_io is not None
             and 0 <= to_slot < len(to_exec_io["inputs"])
             and (not socket_type or socket_type in {"*", "UNKNOWN"})
         ):
             socket_type = to_exec_io["inputs"][to_slot][1]
         lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
         links.append(
             [lid, id_remap[edge.from_node], from_slot, id_remap[edge.to_node], to_slot, socket_type or ""]
         )
 
     links.sort(key=lambda lnk: lnk[0])
 
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
 
-    # --- groups: merge caller-passed groups with engine-generated subgraph groups ---
-    #   Order: caller-passed groups first, then engine_groups (suppressing duplicates
-    #   whose ``title`` matches a caller-passed group title).  All groups are
+    # --- groups: merge remapped IR groups with engine-generated subgraph groups ---
+    #   Order: IR groups first, then engine_groups (suppressing duplicates whose
+    #   ``title`` matches an IR group title).  All groups are
     #   canonicalized when ``include_main_positions=True``.
-    #   groups= is an override: when omitted, the IR's own ``wf.groups`` is used
-    #   (deep-copied so geometry canonicalization can never mutate the IR).
-    caller_groups: list[dict[str, Any]] = (
-        list(groups) if groups is not None else deepcopy(getattr(wf, "groups", []))
-    )
-    caller_titles: set[str] = {g.get("title", "") for g in caller_groups if g.get("title")}
-    emitted_groups: list[dict[str, Any]] = list(caller_groups)
+    ir_groups = _remap_ir_groups(wf, order_list, id_remap)
+    ir_titles: set[str] = {g.get("title", "") for g in ir_groups if g.get("title")}
+    emitted_groups: list[dict[str, Any]] = list(ir_groups)
     for eg in engine_groups:
-        if eg.get("title", "") not in caller_titles:
+        if eg.get("title", "") not in ir_titles:
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
     if include_main_positions and "state" not in envelope:
         envelope["state"] = {
             "lastNodeId": last_node_id,
             "lastLinkId": last_link_id,
             "lastRerouteId": 0,
         }
 
     # M5 Step 16: refusal-spine on APPLIED re-emit. When the caller supplies the
     # pre-edit UI JSON as guard_original_ui, run convert_ui_to_api over both
     # original and candidate (this envelope) and refuse if any uid-matched,
     # snapshot-present node diverges outside snapshot_delta. RefusedEmit bubbles
     # up so the caller can abort the write.
     if guard_original_ui is not None:
         from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
         from vibecomfy.porting.refuse import guard_emit as _guard_emit  # noqa: PLC0415
 
         _snap = (wf.metadata or {}).get("_ingest_snapshot", {})
         _delta = compute_field_delta(_snap, wf) if _snap else {}
         _guard_emit(guard_original_ui, envelope, _delta, resolved_ops=guard_resolved_ops)
 
     return envelope
 
 
 def offline_emitter_normalizer_self_consistency_check(
     wf: Any,
     *,
     schema_provider: Any = None,
 ) -> tuple[bool, list[str]]:
     """Self-consistency check: emitter and normalizer agree on the same IR.
 
     Proves that ``emit_ui_json`` and ``_normalize_ui_to_api`` are inverses of
     each other on the given workflow — NOT that the result is correct relative
     to ComfyUI's own output.  After compile('api') drops muted/bypassed nodes,
     the compare is against the potentially-smaller compiled graph.
 
     This NEVER imports ComfyUI — it calls the pure-Python ``_normalize_ui_to_api``
     fallback directly rather than ``normalize_to_api`` (which would try the comfy
     converter).  Returns ``(equivalent, diffs)``.
     """
     from vibecomfy.ingest.normalize import _normalize_ui_to_api
     from vibecomfy.porting.parity import compile_equivalent
 
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         ui = emit_ui_json(wf, schema_provider=schema_provider)
     api = wf.compile("api")
     normalized = _normalize_ui_to_api(ui, schema_provider=schema_provider)
     return compile_equivalent(normalized, api)
 
 
 def _node_schema_for_structural(
     class_type: str,
     schema_provider: Any,
     cache: dict[str, Any],
 ) -> Any:
     if class_type not in cache:
         cache[class_type] = (
             schema_provider.get_schema(class_type) if schema_provider is not None else None
diff --git a/vibecomfy/porting/layout_store.py b/vibecomfy/porting/layout_store.py
index 841f09be..ff96b2fd 100644
--- a/vibecomfy/porting/layout_store.py
+++ b/vibecomfy/porting/layout_store.py
@@ -1,311 +1,313 @@
 """Sidecar layout store. M2 envelope (Step 5a) supersedes the frozen M1.5 schema.
 
 The M1.5 sidecar was a flat ``{"layout_version": 1, "nodes": {uid: {pos, size}}}``.
 M2 replaces it with a versioned envelope that round-trips the full editor state
 needed to reconstruct a workflow losslessly:
 
     {
       "store_version": 2,
       "vibecomfy_version": "<str>",
       "schema_hash": "<blake2b of the entry/section key shape>",
       "entries": {                       # per-uid node geometry + verbatim blob
         "<uid>": {
           "pos": [x, y],                 # canonicalized via snap_pos (T3)
           "size": [w, h],
           "flags": {...},
           "color": "<str|null>",
           "bgcolor": "<str|null>",
           "properties": {...}            # verbatim
         }
       },
       "groups": [...],                   # graph-level
       "extra": {"ds": {...}},            # canvas drag/scale state under extra.ds
       "lastRerouteId": <int|null>,
       "definitions": {...},              # subgraph inner-node ids/pos
       "virtual_wires": {                 # Get/Set/Reroute virtual edges
         "<uid>": {"type": <str>, "channel": <str>, "endpoints": [...]}
       }
     }
 
 The sidecar lives alongside the converted .py file with the suffix
 ``.layout.json`` (e.g. ``flat.py`` -> ``flat.layout.json``).
 
 Graceful-absence behaviors from M1.5 are preserved: ``write_layout`` skips nodes
 with an empty uid or with no captured ``pos``; ``read_layout`` returns ``{}`` for
 an absent or unreadable sidecar.
 """
 from __future__ import annotations
 
 import hashlib
 import json
+from copy import deepcopy
 from pathlib import Path
 from typing import TYPE_CHECKING, Any, Iterable
 
 from vibecomfy.porting.canonical_coords import snap_pos, snap_size
 from vibecomfy.identity.scope import compose_scope_path, sg_key
 from vibecomfy.identity.uid import make_uid, mint_local_uid
 
 if TYPE_CHECKING:
     from vibecomfy.workflow import VibeWorkflow
 
 STORE_VERSION = 2
 
 # Stable description of the envelope shape; hashed into ``schema_hash`` so a
 # reader can detect a schema drift independent of the version integer.
 _ENTRY_KEYS = ("pos", "size", "flags", "color", "bgcolor", "mode", "properties")
 _SECTION_KEYS = (
     "entries",
     "groups",
     "extra",
     "lastRerouteId",
     "definitions",
     "virtual_wires",
 )
 
 
 def _schema_hash() -> str:
     payload = json.dumps(
         {"entry_keys": list(_ENTRY_KEYS), "section_keys": list(_SECTION_KEYS)},
         sort_keys=True,
     ).encode("utf-8")
     return hashlib.blake2b(payload, digest_size=8).hexdigest()
 
 
 def sidecar_path_for(py_path: Path) -> Path:
     """Return the sidecar layout path for a given .py file path.
 
     flat.py -> flat.layout.json
     """
     return py_path.with_suffix(".layout.json")
 
 
 def _vibecomfy_version() -> str:
     try:
         from importlib.metadata import PackageNotFoundError, version
 
         try:
             return version("vibecomfy")
         except PackageNotFoundError:
             return "0"
     except Exception:
         return "0"
 
 
 def _build_entry(ui: dict) -> dict[str, Any]:
     """Build a per-uid entry from a node's captured ``_ui`` blob.
 
     ``pos`` is canonicalized (T3) so repeated round-trips are idempotent and
     bit-stable. ``size`` is canonicalized when present.
     """
     entry: dict[str, Any] = {"pos": snap_pos(ui["pos"])}
     size = ui.get("size")
     entry["size"] = snap_size(size) if size is not None else None
     entry["flags"] = ui.get("flags")
     entry["color"] = ui.get("color")
     entry["bgcolor"] = ui.get("bgcolor")
     mode = ui.get("mode")
     entry["mode"] = mode if isinstance(mode, int) else 0
     properties = ui.get("properties")
     entry["properties"] = properties if isinstance(properties, dict) else {}
     return entry
 
 
 def _iter_subgraph_defs(definitions: Any) -> Iterable[dict]:
     """Yield individual subgraph definition dicts from a ``definitions`` blob.
 
     Tolerant of the shapes ComfyUI emits: ``{"subgraphs": [...]}``, a plain
     ``{uuid: def}`` mapping, a single def dict (has its own ``nodes``), or a
     bare list of defs.
     """
     if isinstance(definitions, dict):
         subgraphs = definitions.get("subgraphs")
         if isinstance(subgraphs, list):
             for sg in subgraphs:
                 if isinstance(sg, dict):
                     yield sg
             return
         if isinstance(definitions.get("nodes"), list):
             yield definitions
             return
         for sg in definitions.values():
             if isinstance(sg, dict):
                 yield sg
         return
     if isinstance(definitions, list):
         for sg in definitions:
             if isinstance(sg, dict):
                 yield sg
 
 
 def _assemble_definition_entries(
     definitions: Any, scope_chain: tuple[str, ...]
 ) -> dict[str, dict]:
     """Mint scoped uids over the subgraph-inner skeleton and build geometry entries.
 
     For each subgraph definition we derive an ``sg_key`` (T8), extend the scope
     chain, and key every inner node by ``make_uid(scope_path, local_uid)`` where
     ``local_uid`` resolves ``properties['vibecomfy_uid']`` via ``mint_local_uid``
     (falling back to the inner integer id). Recurses into nested definitions so
     the scope_path is the full chain of sg_keys (SD1). A raw litegraph inner node
     already exposes the same pos/size/flags/color/bgcolor/properties keys that
     ``_build_entry`` reads.
     """
     entries: dict[str, dict] = {}
     for sg_def in _iter_subgraph_defs(definitions):
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
-    Graph-level sections are read from ``wf.metadata`` when present and otherwise
-    serialized as empty/absent. Returns the sidecar path written.
+    Groups are serialized from the first-class ``wf.groups`` field.  Other
+    graph-level sections are read from ``wf.metadata`` when present and
+    otherwise serialized as empty/absent. Returns the sidecar path written.
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
     definitions = meta.get("definitions")
     if definitions:
         entries.update(_assemble_definition_entries(definitions, ()))
 
     def _section(key: str, default: Any) -> Any:
         # Prefer an explicit _layout section, then a top-level metadata key.
         if key in layout_meta:
             return layout_meta[key]
         if key in meta:
             return meta[key]
         return default
 
     extra = _section("extra", None)
     if not isinstance(extra, dict):
         extra = {}
     if "ds" not in extra:
         ds = _section("ds", None)
         if ds is not None:
             extra = {**extra, "ds": ds}
 
     envelope = {
         "store_version": STORE_VERSION,
         "vibecomfy_version": _vibecomfy_version(),
         "schema_hash": _schema_hash(),
         "entries": entries,
-        "groups": _section("groups", []) or [],
+        "groups": deepcopy(wf.groups),
         "extra": extra,
         "lastRerouteId": _section("lastRerouteId", None),
         "definitions": _section("definitions", {}) or {},
         "virtual_wires": _section("virtual_wires", {}) or {},
     }
 
     # gc the .py sidecar (T7, default-on): prune any per-uid entry / virtual wire
     # whose uid is not part of the live set (surviving node entries + captured
     # furniture). A fresh build keys only live geometry, so this is a no-op in the
     # common path but enforces the contract that the sidecar never carries dead
     # geometry for a uid that no longer exists.
     live_uids = set(envelope["entries"]) | set(envelope["virtual_wires"])
     gc(envelope, live_uids)
 
     sidecar = sidecar_path_for(py_path)
     sidecar.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
     return sidecar
 
 
 def write_store(py_path: Path, store_envelope: dict[str, Any]) -> Path:
     """Write a pre-built store envelope to the sidecar alongside ``py_path``.
 
     Use this when the envelope was built from an already-emitted UI JSON
     (e.g. via ``store_from_ui_json``) rather than from a live ``VibeWorkflow``.
     Skips writing if ``store_envelope`` contains no entries (prevents silently
     overwriting a valid sidecar with an empty one).  Returns the sidecar path.
     """
     if not store_envelope.get("entries"):
         return sidecar_path_for(py_path)
     sidecar = sidecar_path_for(py_path)
     sidecar.write_text(json.dumps(store_envelope, indent=2), encoding="utf-8")
     return sidecar
 
 
 def migrate_store(data: dict[str, Any]) -> dict[str, Any]:
     """Upgrade a legacy v1 flat layout schema to the current M2 envelope.
 
     The frozen M1.5 sidecar was a flat
     ``{"layout_version": 1, "nodes": {uid: {pos, size, ...}}}``. This lifts each
     v1 node into a per-uid envelope ``entry`` (preserving pos/size, canonicalized
     via T3 snapping, plus any flags/color/bgcolor/properties present). Data that
     is already a v2 envelope — or an unrecognized shape — is returned unchanged
     (no-op), so the function is safe to invoke unconditionally on load.
     """
     if not isinstance(data, dict):
         return data
     if data.get("store_version") == STORE_VERSION:
         return data
     if data.get("layout_version") != 1:
         return data
 
     nodes = data.get("nodes")
     entries: dict[str, dict] = {}
     if isinstance(nodes, dict):
         for uid, node in nodes.items():
             if not isinstance(node, dict):
                 continue
             pos = node.get("pos")
             size = node.get("size")
             properties = node.get("properties")
             mode = node.get("mode")
             entries[str(uid)] = {
                 "pos": snap_pos(pos) if pos is not None else None,
                 "size": snap_size(size) if size is not None else None,
                 "flags": node.get("flags"),
                 "color": node.get("color"),
                 "bgcolor": node.get("bgcolor"),
                 "mode": mode if isinstance(mode, int) else 0,
                 "properties": properties if isinstance(properties, dict) else {},
             }
 
     return {
         "store_version": STORE_VERSION,
         "vibecomfy_version": _vibecomfy_version(),
         "schema_hash": _schema_hash(),
         "entries": entries,
         "groups": [],
         "extra": {},
         "lastRerouteId": None,
         "definitions": {},
         "virtual_wires": {},
     }
 
 
 def gc(data: dict[str, Any], live_uids: Iterable[str]) -> dict[str, Any]:
     """Prune per-uid sections to the set of currently live uids.
 
     Entries (and the uid-keyed ``virtual_wires`` section) whose uid is no longer
     present in ``live_uids`` are dropped; live entries are retained verbatim.
     Default-on for the ``.py`` sidecar so a converted module never accumulates

exec
/bin/zsh -lc "rg -n \"def _get_node_mode|def _resolve_furniture|def _remap_ir_groups|def emit_ui_json|def _allocate_node_ids|id_remap\" vibecomfy/porting/emit/ui.py vibecomfy/workflow.py && nl -ba vibecomfy/porting/emit/ui.py | sed -n '380,520p' && nl -ba vibecomfy/porting/emit/ui.py | sed -n '1340,1455p' && nl -ba vibecomfy/porting/emit/ui.py | sed -n '1980,2085p' && nl -ba vibecomfy/porting/emit/ui.py | sed -n '2360,2445p' && nl -ba vibecomfy/workflow.py | sed -n '1470,1535p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/porting/emit/ui.py:249:def _resolve_furniture(
vibecomfy/porting/emit/ui.py:425:def _build_id_remap(order_list: list[str]) -> dict[str, int]:
vibecomfy/porting/emit/ui.py:453:def _remap_ir_groups(
vibecomfy/porting/emit/ui.py:456:    id_remap: Mapping[str, int],
vibecomfy/porting/emit/ui.py:481:        emitted_id = id_remap[workflow_node_id]
vibecomfy/porting/emit/ui.py:2043:def emit_ui_json(
vibecomfy/porting/emit/ui.py:2219:    id_remap = _build_id_remap(order_list)
vibecomfy/porting/emit/ui.py:2435:    last_node_id = max(id_remap.values()) if id_remap else 0
vibecomfy/porting/emit/ui.py:2456:                litegraph_node_id=id_remap[node_id],
vibecomfy/porting/emit/ui.py:2574:                litegraph_node_id=id_remap[node_id],
vibecomfy/porting/emit/ui.py:2628:            [lid, id_remap[edge.from_node], from_slot, id_remap[edge.to_node], to_slot, socket_type or ""]
vibecomfy/porting/emit/ui.py:2703:    ir_groups = _remap_ir_groups(wf, order_list, id_remap)
vibecomfy/workflow.py:1235:def _get_node_mode(node: VibeNode) -> int:
   380	def _breadcrumb(wf: Any, source_template: str | None, prior_path: str | None) -> dict[str, Any]:
   381	    """Build the ``extra.vibecomfy`` breadcrumb stamped on the envelope/subgraphs."""
   382	    return {
   383	        "layout_version": _LAYOUT_VERSION,
   384	        "source_template": source_template if source_template is not None else _source_template_name(wf),
   385	        "prior_path": prior_path if prior_path is not None else _source_prior_path(wf),
   386	    }
   387	
   388	
   389	def default_output_path(
   390	    wf: Any,
   391	    *,
   392	    out: str | None = None,
   393	    source_template: str | None = None,
   394	    out_dir: str = _DEFAULT_OUT_DIR,
   395	) -> Path:
   396	    """Deterministic output path for an emitted UI export.
   397	
   398	    ``--out`` (the ``out`` argument) overrides everything.  Otherwise the path is
   399	    ``<out_dir>/ui_export/<source_template>.json`` when a source-template name is
   400	    available, falling back to ``<out_dir>/ui_export/<ir-hash>.json`` for unnamed
   401	    (programmatic) sources.  The fallback hash guarantees the path is never empty
   402	    and never raises.
   403	    """
   404	    if out:
   405	        return Path(out)
   406	    name = source_template if source_template is not None else _source_template_name(wf)
   407	    if name:
   408	        safe = re.sub(r"[^A-Za-z0-9._/-]", "_", name)
   409	        # Collapse path-traversal and leading separators so the name stays under out_dir.
   410	        safe = safe.replace("..", "_").lstrip("/") or _ir_hash(wf)
   411	    else:
   412	        safe = _ir_hash(wf)
   413	    return Path(out_dir) / _UI_EXPORT_SUBDIR / f"{safe}.json"
   414	
   415	
   416	def _emission_order(wf: Any) -> list[str]:
   417	    """Deterministic node emission order: numeric ids ascending, then lexical."""
   418	
   419	    def key(node_id: str) -> tuple[int, str]:
   420	        return (int(node_id), node_id) if node_id.isdigit() else (1 << 30, node_id)
   421	
   422	    return sorted(wf.nodes.keys(), key=key)
   423	
   424	
   425	def _build_id_remap(order_list: list[str]) -> dict[str, int]:
   426	    """Map string VibeNode ids → litegraph integer node ids.
   427	
   428	    Digit ids keep their numeric value (so source-derived ``"98"`` stays ``98`` and the
   429	    envelope matches the litegraph reference field-for-field).  Non-digit ids (e.g.
   430	    typed-wrapper labels) are assigned fresh integers above the highest digit id, never
   431	    colliding with a preserved value.  This mapping only governs the litegraph ``id`` field
   432	    and the node-id slots inside ``links[]``.
   433	    """
   434	    remap: dict[str, int] = {}
   435	    used: set[int] = set()
   436	    for node_id in order_list:
   437	        if node_id.isdigit():
   438	            value = int(node_id)
   439	            remap[node_id] = value
   440	            used.add(value)
   441	    nxt = (max(used) + 1) if used else 1
   442	    for node_id in order_list:
   443	        if node_id in remap:
   444	            continue
   445	        while nxt in used:
   446	            nxt += 1
   447	        remap[node_id] = nxt
   448	        used.add(nxt)
   449	        nxt += 1
   450	    return remap
   451	
   452	
   453	def _remap_ir_groups(
   454	    wf: Any,
   455	    order_list: list[str],
   456	    id_remap: Mapping[str, int],
   457	) -> list[dict[str, Any]]:
   458	    """Deep-copy IR groups and resolve live members to LiteGraph integer ids.
   459	
   460	    Group membership may have been captured at different boundaries, so each
   461	    live node contributes aliases for its workflow mapping key, ``node.id``,
   462	    stable uid, and captured ``_ui.id``.  Numeric aliases accept either their
   463	    integer or decimal-string form.  Ambiguous aliases and stale members are
   464	    omitted instead of emitting a dangling reference.
   465	    """
   466	    candidates: dict[tuple[str, Any], set[int]] = defaultdict(set)
   467	
   468	    def add_alias(value: Any, emitted_id: int) -> None:
   469	        if isinstance(value, bool):
   470	            return
   471	        if isinstance(value, int):
   472	            candidates[("int", value)].add(emitted_id)
   473	            candidates[("str", str(value))].add(emitted_id)
   474	        elif isinstance(value, str) and value:
   475	            candidates[("str", value)].add(emitted_id)
   476	            if value.isdigit():
   477	                candidates[("int", int(value))].add(emitted_id)
   478	
   479	    for workflow_node_id in order_list:
   480	        node = wf.nodes[workflow_node_id]
   481	        emitted_id = id_remap[workflow_node_id]
   482	        add_alias(workflow_node_id, emitted_id)
   483	        add_alias(getattr(node, "id", None), emitted_id)
   484	        add_alias(getattr(node, "uid", None), emitted_id)
   485	        raw_ui = getattr(node, "metadata", {}).get("_ui")
   486	        if isinstance(raw_ui, dict):
   487	            add_alias(raw_ui.get("id"), emitted_id)
   488	
   489	    aliases = {key: next(iter(ids)) for key, ids in candidates.items() if len(ids) == 1}
   490	    remapped: list[dict[str, Any]] = []
   491	    for raw_group in deepcopy(getattr(wf, "groups", [])):
   492	        group = dict(raw_group)
   493	        members = group.get("nodes")
   494	        if isinstance(members, list):
   495	            resolved: list[int] = []
   496	            for member in members:
   497	                if isinstance(member, bool):
   498	                    continue
   499	                key = (
   500	                    ("int", member)
   501	                    if isinstance(member, int)
   502	                    else ("str", member)
   503	                    if isinstance(member, str)
   504	                    else None
   505	                )
   506	                if key is not None and key in aliases:
   507	                    resolved.append(aliases[key])
   508	            group["nodes"] = resolved
   509	        elif "nodes" in group:
   510	            group["nodes"] = []
   511	        remapped.append(group)
   512	    return remapped
   513	
   514	
   515	# ── Virtual-wire classification ────────────────────────────────────────────
   516	# Get/Set broadcast wires + Reroute passthrough are the virtual-wire nodes
   517	# whose stable channel name (not the edge) is the routing key.
   518	_VIRTUAL_WIRE_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})
   519	
   520	
  1340	            if default is not None:
  1341	                merged_fields[name] = deepcopy(default)
  1342	    merged_fields.update(dict(fields))
  1343	
  1344	    metadata: dict[str, Any] = {}
  1345	    retained_control = merged_fields.pop("control_after_generate", None)
  1346	    if isinstance(retained_control, str):
  1347	        metadata["control_after_generate"] = retained_control
  1348	
  1349	    node = VibeNode(
  1350	        id=str(node_id),
  1351	        class_type=class_type,
  1352	        inputs=merged_fields,
  1353	        metadata=metadata,
  1354	        uid=uid,
  1355	    )
  1356	    geometry = {
  1357	        "pos": [
  1358	            _canonicalize_coord(float(pos[0])),
  1359	            _canonicalize_coord(float(pos[1])),
  1360	        ],
  1361	        "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
  1362	    }
  1363	    furniture = _resolve_furniture(node, None)
  1364	    inputs: list[dict[str, Any]] = []
  1365	    outputs: list[dict[str, Any]] = _schema_outputs_for_unwired_node(schema)
  1366	    if class_type == "vibecomfy.exec":
  1367	        exec_io = _exec_io_for_node(node)
  1368	        if exec_io is not None:
  1369	            inputs = _exec_dynamic_inputs(exec_io, {})
  1370	            outputs = _exec_dynamic_outputs(exec_io, {})
  1371	    return _emit_litegraph_node_dict(
  1372	        node,
  1373	        litegraph_node_id=int(node_id),
  1374	        order=0,
  1375	        geometry=geometry,
  1376	        furniture=furniture,
  1377	        inputs=inputs,
  1378	        outputs=outputs,
  1379	        schema=schema,
  1380	        include_main_positions=False,
  1381	    )
  1382	
  1383	
  1384	def _schema_for_provider(schema_provider: Any | None, class_type: str) -> Any | None:
  1385	    if schema_provider is None:
  1386	        return None
  1387	    getter = getattr(schema_provider, "get_schema", None) or getattr(schema_provider, "get", None)
  1388	    if not callable(getter):
  1389	        return None
  1390	    return getter(class_type)
  1391	
  1392	
  1393	def _raw_widget_shape_from_value(values: Any) -> tuple[int, str, bool]:
  1394	    if values is None:
  1395	        return 0, "none", False
  1396	    if isinstance(values, dict):
  1397	        return len(values), "dict", True
  1398	    if isinstance(values, list):
  1399	        return len(values), "list", any(isinstance(item, dict) for item in values)
  1400	    return 1, "scalar", False
  1401	
  1402	
  1403	def _raw_widget_shape_from_node(node: Any) -> tuple[int | None, str | None, bool]:
  1404	    raw_widgets = getattr(node, "raw_widgets", None)
  1405	    if raw_widgets is not None:
  1406	        length = getattr(raw_widgets, "length", None)
  1407	        shape = getattr(raw_widgets, "shape", None)
  1408	        has_dict_rows = bool(getattr(raw_widgets, "has_dict_rows", False))
  1409	        if length is None:
  1410	            length, recovered_shape, recovered_has_dict_rows = _raw_widget_shape_from_value(
  1411	                getattr(raw_widgets, "values", None)
  1412	            )
  1413	            if shape is None:
  1414	                shape = recovered_shape
  1415	            has_dict_rows = has_dict_rows or recovered_has_dict_rows
  1416	        return (
  1417	            int(length) if length is not None else None,
  1418	            str(shape or "unknown"),
  1419	            has_dict_rows,
  1420	        )
  1421	
  1422	    raw_ui = getattr(node, "metadata", {}).get("_ui")
  1423	    if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
  1424	        count, shape, has_dict_rows = _raw_widget_shape_from_value(raw_ui.get("widgets_values"))
  1425	        return count, shape, has_dict_rows
  1426	
  1427	    return None, None, False
  1428	
  1429	
  1430	def extract_raw_ui_node_map(
  1431	    ui_payload: Mapping[str, Any] | None,
  1432	) -> dict[str, dict[str, Any]]:
  1433	    """Return full raw LiteGraph node payloads keyed by stable lookup ids.
  1434	
  1435	    This is deliberately separate from ``prior_store``.  The layout store is a
  1436	    furniture/identity envelope built by :func:`store_from_ui_json`; it must not
  1437	    become evidence that a dynamic widget node can be preserved opaque.  Pinning
  1438	    decisions need the original full node dict from an actual UI JSON payload.
  1439	    """
  1440	    if not isinstance(ui_payload, Mapping):
  1441	        return {}
  1442	    nodes = ui_payload.get("nodes")
  1443	    if not isinstance(nodes, list):
  1444	        return {}
  1445	
  1446	    out: dict[str, dict[str, Any]] = {}
  1447	    for raw_node in nodes:
  1448	        if not isinstance(raw_node, dict):
  1449	            continue
  1450	        node_copy = dict(raw_node)
  1451	        node_id = raw_node.get("id")
  1452	        if node_id is not None:
  1453	            out[str(node_id)] = node_copy
  1454	        props = raw_node.get("properties")
  1455	        if isinstance(props, Mapping):
  1980	    explicit_widget_overflow = False
  1981	    if schema_widget_count is not None and not provenance["schema_less"]:
  1982	        if has_dict_rows:
  1983	            overflow = largest_observed_count > schema_widget_count
  1984	        elif primitive_control_widget:
  1985	            overflow = False
  1986	        elif (
  1987	            node.class_type in _STATIC_RAW_WIDGET_SLACK_CLASSES
  1988	            and candidate_widget_count <= schema_widget_count + _STATIC_WIDGET_OVERFLOW_TOLERANCE
  1989	            and (
  1990	                raw_widget_count is not None
  1991	                or programmatic_widget_count <= schema_widget_count
  1992	            )
  1993	            and (
  1994	                raw_widget_count is None
  1995	                or programmatic_widget_count <= raw_widget_count
  1996	            )
  1997	        ):
  1998	            overflow = False
  1999	        elif (
  2000	            programmatic_widget_count > schema_widget_count
  2001	            and not (raw_widget_count is not None and programmatic_widget_count <= raw_widget_count)
  2002	        ):
  2003	            overflow = True
  2004	            explicit_widget_overflow = True
  2005	        else:
  2006	            overflow = largest_observed_count > schema_widget_count
  2007	            explicit_widget_overflow = (
  2008	                programmatic_widget_count > schema_widget_count
  2009	                and not (
  2010	                    raw_widget_count is not None
  2011	                    and programmatic_widget_count <= raw_widget_count
  2012	                )
  2013	            )
  2014	
  2015	    raw_widget_length_recovered = False
  2016	    raw_widgets = getattr(node, "raw_widgets", None)
  2017	    if raw_widgets is not None and getattr(raw_widgets, "length", None) is None:
  2018	        raw_widget_length_recovered = raw_widget_count is not None
  2019	
  2020	    return WidgetShapeEvidence(
  2021	        node_id=str(node.id),
  2022	        class_type=str(node.class_type),
  2023	        schema_less=bool(provenance["schema_less"]),
  2024	        confidence=provenance.get("confidence"),
  2025	        raw_widget_count=raw_widget_count,
  2026	        candidate_widget_count=candidate_widget_count,
  2027	        schema_widget_count=schema_widget_count,
  2028	        compacted_widget_names=tuple(
  2029	            name
  2030	            for index, name in enumerate(widget_names)
  2031	            if name is not None and name != f"widget_{index}"
  2032	        ),
  2033	        raw_widget_shape=raw_widget_shape,
  2034	        has_dict_rows=has_dict_rows,
  2035	        overflow=overflow,
  2036	        provider=provenance.get("provider"),
  2037	        explicit_widget_overflow=explicit_widget_overflow,
  2038	        raw_widget_length_recovered=raw_widget_length_recovered,
  2039	        value_domain=value_domain,
  2040	    )
  2041	
  2042	
  2043	def emit_ui_json(
  2044	    wf: Any,
  2045	    *,
  2046	    schema_provider: Any = None,
  2047	    prior_store: Mapping[str, Any] | None = None,
  2048	    layout: Any = None,
  2049	    anchors: dict[str, Any] | None = None,
  2050	    strict: bool = False,
  2051	    recovery_report: list[dict[str, Any]] | None = None,
  2052	    source_template: str | None = None,
  2053	    prior_path: str | None = None,
  2054	    include_main_positions: bool = False,
  2055	    include_virtual_wires: bool = True,
  2056	    extra: dict[str, Any] | None = None,
  2057	    definitions: dict[str, Any] | None = None,
  2058	    change_report_out: list | None = None,
  2059	    guard_original_ui: Mapping[str, Any] | None = None,
  2060	    guard_resolved_ops: Any = None,
  2061	    prior_ui_payload: Mapping[str, Any] | None = None,
  2062	    force_drop_editor_only: bool = False,
  2063	) -> dict[str, Any]:
  2064	    """Render ``wf`` (a ``VibeWorkflow``) to a litegraph JSON envelope.
  2065	
  2066	    Args:
  2067	        wf: The IR workflow to emit.
  2068	        schema_provider: Schema source used for slot/type resolution.  Consulted
  2069	            via ``get_schema(class_type)`` for each node.  Pass ``None`` to skip
  2070	            schema resolution (all edges emit with slot 0 and empty type).
  2071	        prior_store: Full prior-store envelope (``{entries, groups, extra,
  2072	            definitions, virtual_wires}``) from a previously written sidecar.
  2073	            ``entries`` (keyed by node uid) feeds the legacy
  2074	            ``_resolve_furniture`` precedence chain and is passed as ``pinned``
  2075	            to the layout engine.  The full envelope is also handed to
  2076	            :func:`reconcile` once at the top of the function; the resulting
  2077	            ``ReconcileResult`` is exposed to the per-node loop as a local
  2078	            (``reconcile_result``) for later steps (Step 9b+).
  2079	        anchors: New-node placement hints ``{new_uid: anchor_uid, ...}``.
  2080	            Routed to :func:`~vibecomfy.porting.layout.placement.place_constrained`
  2081	            in the engine (Phase 8) as a dedicated kwarg.  Passing ``None`` or
  2082	            ``{}`` leaves existing behavior unchanged.
  2083	        strict: When ``True``, raises ``ValueError`` if any node has a schema-less
  2084	            class type (``get_schema() == None``) or a low-confidence schema
  2085	            (``confidence <= 0.3``, i.e. the ``widget_schema_fallback`` tier).
  2360	        layout_entry = _layout_entry_for_widget_shape(node_id, node, matched_entries)
  2361	        allow_schema_defaults = (
  2362	            raw_ui_node is None
  2363	            and not identity_matched
  2364	            and schema is not None
  2365	            and not prov["schema_less"]
  2366	            and prov.get("provider") == "object_info_index"
  2367	            and expected_widget_count is not None
  2368	            and expected_widget_count > 1
  2369	            and (prov.get("confidence") is None or prov["confidence"] > _LOW_CONFIDENCE_THRESHOLD)
  2370	            and not evidence.has_dict_rows
  2371	            and _has_schema_default_regeneration_basis(node, schema, schema_provider)
  2372	        )
  2373	        verdict = _decide_widget_shape(
  2374	            evidence,
  2375	            raw_widget_payloads={node_id: getattr(node, "raw_widgets", None)},
  2376	            raw_payloads={node_id: raw_ui_node} if raw_ui_node is not None else {},
  2377	            layout_entries={node_id: layout_entry} if layout_entry is not None else {},
  2378	            field_deltas={node_id: field_delta} if field_delta else {},
  2379	            link_deltas={node_id: link_delta} if link_delta else {},
  2380	            identity_matched=identity_matched,
  2381	            allow_schema_default_regenerate=allow_schema_defaults,
  2382	            is_new_node=(
  2383	                (node.uid or node_id) in new_node_keys
  2384	                and getattr(node, "raw_widgets", None) is None
  2385	                and raw_ui_node is None
  2386	            ),
  2387	        )
  2388	        widget_shape_verdicts[node_id] = verdict
  2389	        widget_shape_default_values[node_id] = (
  2390	            _schema_default_widget_values_for_node(node, schema)
  2391	            if getattr(verdict, "use_schema_defaults", False)
  2392	            else None
  2393	        )
  2394	
  2395	    refused_verdicts = [
  2396	        verdict
  2397	        for verdict in widget_shape_verdicts.values()
  2398	        if verdict.refuse
  2399	    ]
  2400	    if refused_verdicts:
  2401	        if recovery_report is not None:
  2402	            for node_id in order_list:
  2403	                recovery_report.append(
  2404	                    _build_recovery_entry(
  2405	                        node_prov[node_id],
  2406	                        widget_shape_verdicts[node_id],
  2407	                        has_raw_ui_payload=widget_shape_raw_payloads[node_id] is not None,
  2408	                    )
  2409	                )
  2410	        raise _refused_widget_shape(refused_verdicts)
  2411	
  2412	    # Sort edges deterministically (from_node asc, from_output, to_node, to_input)
  2413	    sorted_edges = sorted(
  2414	        display_edges,
  2415	        key=lambda e: (e.from_node.zfill(20), e.from_output, e.to_node.zfill(20), e.to_input),
  2416	    )
  2417	
  2418	    # Assign deterministic link IDs (1-indexed)
  2419	    EdgeKey = tuple[str, str, str, str]
  2420	    link_id_map: dict[EdgeKey, int] = {
  2421	        (e.from_node, e.from_output, e.to_node, e.to_input): idx
  2422	        for idx, e in enumerate(sorted_edges, start=1)
  2423	    }
  2424	    last_link_id = len(sorted_edges)
  2425	
  2426	    # Edge lookup by node
  2427	    edges_from: dict[str, list[Any]] = defaultdict(list)
  2428	    edges_to: dict[str, list[Any]] = defaultdict(list)
  2429	    for edge in sorted_edges:
  2430	        edges_from[edge.from_node].append(edge)
  2431	        edges_to[edge.to_node].append(edge)
  2432	
  2433	    # Build nodes
  2434	    nodes: list[dict[str, Any]] = []
  2435	    last_node_id = max(id_remap.values()) if id_remap else 0
  2436	
  2437	    for order, node_id in enumerate(order_list):
  2438	        node = wf.nodes[node_id]
  2439	        key = _node_key(node_id)
  2440	        verdict = widget_shape_verdicts[node_id]
  2441	        if verdict.pin_opaque and _exec_io_for_node(node) is None:
  2442	            incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
  2443	            for edge in edges_to[node_id]:
  2444	                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
  2445	                incoming_link_ids_by_input[edge.to_input].append(lid)
  1470	                f"but feeds runtime input {target_node_id!r}.{target_input!r}."
  1471	            ),
  1472	            detail={
  1473	                "helper_node_id": str(source_node_id),
  1474	                "class_type": source_node.class_type,
  1475	                "target_node_id": target_node_id,
  1476	                "target_input": target_input,
  1477	            },
  1478	            next_action="Remove the UI-only helper edge or reconnect the input to a runtime node.",
  1479	        )
  1480	
  1481	    if source_node_id in visited:
  1482	        raise WorkflowCompileError(
  1483	            "helper_edge_cycle",
  1484	            (
  1485	                f"Helper edge cycle while resolving {source_node_id!r} for "
  1486	                f"{target_node_id!r}.{target_input!r}."
  1487	            ),
  1488	            detail={
  1489	                "helper_node_id": str(source_node_id),
  1490	                "target_node_id": target_node_id,
  1491	                "target_input": target_input,
  1492	                "visited": sorted(visited),
  1493	            },
  1494	            next_action="Break the SetNode/GetNode broadcast cycle before compiling.",
  1495	        )
  1496	    visited.add(source_node_id)
  1497	
  1498	    name = workflow_helpers.broadcast_name(source_node)
  1499	    if not name or name not in broadcast_sources:
  1500	        raise WorkflowCompileError(
  1501	            "helper_edge_unresolved",
  1502	            (
  1503	                f"{source_node.class_type} node {source_node_id!r} feeding "
  1504	                f"{target_node_id!r}.{target_input!r} has no resolved broadcast source."
  1505	            ),
  1506	            detail={
  1507	                "helper_node_id": str(source_node_id),
  1508	                "class_type": source_node.class_type,
  1509	                "broadcast": name,
  1510	                "target_node_id": target_node_id,
  1511	                "target_input": target_input,
  1512	            },
  1513	            next_action="Add a matching SetNode source or reconnect the input to a runtime node.",
  1514	        )
  1515	    source = broadcast_sources[name]
  1516	    return _resolve_compiled_source_ref(
  1517	        str(source[0]),
  1518	        source[1],
  1519	        nodes,
  1520	        broadcast_sources,
  1521	        visited=visited,
  1522	        target_node_id=target_node_id,
  1523	        target_input=target_input,
  1524	    )
  1525	
  1526	
  1527	def _resolve_link_value(
  1528	    value: Any,
  1529	    nodes: dict[str, VibeNode],
  1530	    broadcast_sources: dict[str, list[Any]],
  1531	) -> Any:
  1532	    return helper_resolve.resolve_compile_link_value(value, nodes, broadcast_sources)
  1533	
  1534	
  1535	def _apply_positional_widget_aliases(inputs: dict[str, Any], node: VibeNode) -> None:

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/ui.py | sed -n '225,290p' && nl -ba vibecomfy/workflow.py | sed -n '1200,1260p' && rg -n \"_get_node_mode\\(\" vibecomfy --glob '*.py' && rg -n \"\\.mode|get\\([\\\"']mode[\\\"']|\\[[\\\"']mode[\\\"']\\]\" vibecomfy/porting/emit/ui.py vibecomfy/workflow.py | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 34ms:
vibecomfy/workflow.py:1235:def _get_node_mode(node: VibeNode) -> int:
vibecomfy/workflow.py:1264:        mode = _get_node_mode(node)
vibecomfy/porting/emit/ui.py:303:        "mode": _get_node_mode(node),
vibecomfy/workflow.py:865:            from vibecomfy.model_assets import (
vibecomfy/workflow.py:870:            from vibecomfy.registry.models_loader import load_registry
vibecomfy/workflow.py:1231:_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
vibecomfy/workflow.py:1232:_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)
vibecomfy/workflow.py:1236:    """Read the litegraph mode (0/2/4); ``node.mode`` is the authority.
vibecomfy/workflow.py:1239:    ``metadata["_ui"]["mode"]``; it is consulted only when the field is unset
vibecomfy/workflow.py:1243:    mode = node.mode
vibecomfy/workflow.py:1249:    legacy = ui.get("mode", 0)
vibecomfy/porting/emit/ui.py:261:       authority used by compilation, including its single legacy ``_ui.mode``
vibecomfy/porting/emit/ui.py:1298:        "mode": furniture["mode"],
vibecomfy/porting/emit/ui.py:2463:            pinned["mode"] = _resolve_furniture(node, matched_entries.get(key))["mode"]

exec
/bin/zsh -lc "nl -ba vibecomfy/commands/port/_export.py | sed -n '285,380p' && rg -n \"emit_ui_json\\(\" vibecomfy scripts tests --glob '*.py' | wc -l && rg -n -U \"emit_ui_json\\([\\s\\S]{0,500}?groups\\s*=\" vibecomfy scripts tests --glob '*.py' || true && rg -n \"groups\\s*=\" vibecomfy scripts --glob '*.py' | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 39ms:
tests/test_porting_ui_emitter.py:2149:    result = emit_ui_json(wf, layout={"uid-bm": layout_entry})
tests/test_porting_ui_emitter.py:2150:    assert result["nodes"][0]["mode"] == 0
tests/test_porting_ui_emitter.py:2151:
tests/test_porting_ui_emitter.py:2152:    # string mode
tests/test_porting_ui_emitter.py:2153:    layout_entry["mode"] = "muted"
tests/test_porting_ui_emitter.py:2154:    result2 = emit_ui_json(wf, layout={"uid-bm": layout_entry})
tests/test_porting_ui_emitter.py:2155:    assert result2["nodes"][0]["mode"] == 0
tests/test_porting_ui_emitter.py:2156:
tests/test_porting_ui_emitter.py:2157:
tests/test_porting_ui_emitter.py:2158:def test_furniture_groups_from_ir() -> None:
tests/test_porting_ui_emitter.py:2159:    """The first-class IR groups field populates the top-level groups array."""
tests/test_porting_ui_emitter.py:2160:    wf = _wf("gtest")
tests/test_porting_ui_emitter.py:2161:    wf.nodes["1"] = VibeNode("1", "N1")
tests/test_porting_ui_emitter.py:2162:
tests/test_porting_ui_emitter.py:2163:    groups = [
tests/test_porting_ui_emitter.py:2168:    result = emit_ui_json(wf)
tests/test_porting_ui_emitter.py:2169:    assert result["groups"] == groups
tests/test_porting_ui_emitter.py:2170:
tests/test_porting_ui_emitter.py:2171:    # Default: empty list
tests/test_porting_ui_emitter.py:2172:    wf.groups = []
tests/test_porting_ui_emitter.py:2744:        result = emit_ui_json(
tests/test_porting_ui_emitter.py:2745:            wf, layout={"uid-lt": layout_entry}, include_main_positions=False,
tests/test_porting_ui_emitter.py:2746:        )
tests/test_porting_ui_emitter.py:2747:
tests/test_porting_ui_emitter.py:2748:    n1 = next(n for n in result["nodes"] if n["id"] == 1)
tests/test_porting_ui_emitter.py:2749:    assert "title" not in n1, "lean default must NOT emit title"
tests/test_porting_ui_emitter.py:2750:
tests/test_porting_ui_emitter.py:2751:
tests/test_porting_ui_emitter.py:2752:def test_canonicalize_group_geometry() -> None:
tests/test_porting_ui_emitter.py:2753:    """Group bounding boxes are canonicalized to M2 precision when
tests/test_porting_ui_emitter.py:2754:    include_main_positions=True."""
tests/test_porting_ui_emitter.py:2755:    from vibecomfy.porting.emit.ui import _canonicalize_group_geometry
tests/test_porting_ui_emitter.py:2756:
tests/test_porting_ui_emitter.py:2757:    groups = [
scripts/check_b02_rich_preservation.py:277:    ir1.groups = deepcopy(raw.get("groups") or [])
scripts/check_b02_rich_preservation.py:313:        ir2.groups = deepcopy(canonical.get("groups") or [])
scripts/check_b02_rich_preservation.py:425:    rich_groups = raw.get("groups") or []
scripts/check_b02_rich_preservation.py:426:    canonical_groups = canonical.get("groups") or []
scripts/check_b02_rich_preservation.py:427:    reemit_groups = reemit.get("groups") or []
vibecomfy/porting/layout_store.py:428:    raw_groups = ui.get("groups") or []
vibecomfy/porting/lowering.py:1180:            emit_native_groups=emit_native_groups,
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:190:    groups = graph.get("groups", [])
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:196:    result_groups = []
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:391:    groups = graph.get("groups")
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:423:    groups = [
vibecomfy/porting/layout/engine.py:313:    groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)
vibecomfy/porting/layout/engine.py:316:    return LayoutResult(positions=positions, groups=groups)
vibecomfy/commands/port/_export.py:448:                workflow.groups = deepcopy(store["groups"])
vibecomfy/ingest/normalize.py:514:    groups = _vibe_groups(raw.get("groups"))
vibecomfy/ingest/normalize.py:522:        groups=groups,
vibecomfy/ingest/normalize.py:778:    workflow.groups = _vibe_groups(raw.get("groups"))
vibecomfy/comfy_nodes/agent/layout_reorganisation.py:298:        touched_groups=_touched_group_count(before_facts, after_facts),
vibecomfy/comfy_nodes/agent/layout_reorganisation.py:300:        added_boxes_outside_groups=_added_boxes_outside_groups(after_facts, added_refs),
vibecomfy/comfy_nodes/agent/layout_reorganisation.py:463:        groups = groups_by_scope.get(furniture.ref.scope_path, [])
vibecomfy/schema/provider.py:1072:    input_groups = info.get("input")
vibecomfy/schema/provider.py:1074:        input_groups = info.get("inputs", {})
vibecomfy/porting/emit/emit_ready.py:688:    section_groups = _build_section_groups(workflow_nodes, edges_in)
vibecomfy/porting/emit/emit_ready.py:798:            section_groups=section_groups,
vibecomfy/porting/emit/emit_ready.py:972:        section_groups = {}
vibecomfy/porting/emit/emit_subgraph.py:544:                section_groups={},
vibecomfy/porting/reorganise/visualize.py:23:    groups = [group for group in ui_json.get("groups", []) if isinstance(group, Mapping)]
vibecomfy/porting/emit/ui.py:2703:    ir_groups = _remap_ir_groups(wf, order_list, id_remap)
vibecomfy/porting/reorganise/projection.py:297:        groups = scope_furniture.groups if scope_furniture is not None else ()
vibecomfy/porting/reorganise/projection.py:298:        shown_groups = tuple(groups[: opts.max_group_facts_per_scope])
vibecomfy/porting/reorganise/graph_facts.py:709:        raw_groups = graph.get("groups")
vibecomfy/porting/reorganise/graph_facts.py:710:        groups = raw_groups if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (str, bytes)) else []
vibecomfy/porting/reorganise/graph_facts.py:732:                groups=tuple(group_facts),
vibecomfy/porting/reorganise/compile.py:1519:    scored_groups = tuple(_scored_existing_groups(facts, classification))
vibecomfy/porting/reorganise/compile.py:4604:    groups = tuple(_sidecar_group(group) for group in sorted(group_layouts, key=lambda item: (item.scope_path, item.id)))
vibecomfy/porting/reorganise/compile.py:4615:        groups=groups,
vibecomfy/porting/reorganise/compile.py:5772:    current_groups = sidecar.get("groups") if isinstance(sidecar.get("groups"), Sequence) and not isinstance(sidecar.get("groups"), (str, bytes)) else ()
vibecomfy/porting/reorganise/compile.py:6311:    shifted_groups = _compiled_group_layouts(sections, shifted_nodes, facts, spacing, options)
vibecomfy/porting/edit/apply_place.py:181:    groups = scope_graph.get("groups")
vibecomfy/porting/edit/apply_place.py:225:    groups = scope_graph.get("groups")
vibecomfy/porting/edit/apply_place.py:243:    groups = scope_graph.get("groups")
vibecomfy/porting/edit/apply_place.py:253:    groups = scope_graph.get("groups")
vibecomfy/porting/edit/_resolve.py:290:        input_groups = info.get("input")
vibecomfy/porting/reorganise/orchestrate.py:804:    groups = find_second_stage_planning_groups(plan=plan, facts=facts, options=opts)
vibecomfy/porting/reorganise/orchestrate.py:1551:    raw_groups = patch.get("groups")

exec
/bin/zsh -lc 'git diff --unified=60 8a8300bb..0d2bb176 -- tests/test_workflow_core.py tests/test_schema_validate.py tests/test_foundation_utils.py tests/test_patches.py tests/test_porting_normalize_ingest.py tests/test_porting_synthetic_fixtures.py tests/test_porting_ui_emitter.py tests/test_layout_store.py tests/test_ui_layout.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 103ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/test_foundation_utils.py b/tests/test_foundation_utils.py
index 152fcaf4..3f87094d 100644
--- a/tests/test_foundation_utils.py
+++ b/tests/test_foundation_utils.py
@@ -1,81 +1,94 @@
 from __future__ import annotations
 
 import subprocess
 from pathlib import Path
 from typing import Sequence
 
 from vibecomfy._git_utils import git_head, git_stdout, git_stdout_result
-from vibecomfy._compile._graph import UI_ONLY_CLASS_TYPES, is_api_link, node_id_sort_key
+from vibecomfy._compile._graph import (
+    UI_ONLY_CLASS_TYPES,
+    is_api_link,
+    is_canonical_api_link,
+    node_id_sort_key,
+)
 from vibecomfy.commands._diagnostics import Diagnostic, diagnostic_to_json, diagnostic_to_text
 
 
 def test_ui_only_class_types_matches_legacy_strip_set() -> None:
     assert UI_ONLY_CLASS_TYPES == frozenset({"Note", "MarkdownNote"})
 
 
 def test_is_api_link_accepts_legacy_numeric_and_string_list_links() -> None:
     assert is_api_link([1, 0])
     assert is_api_link(["1", 0])
     assert is_api_link(["1", "slot"])
 
 
+def test_canonical_api_link_requires_json_string_id_and_integer_slot() -> None:
+    assert is_canonical_api_link(["1", 0])
+    assert not is_canonical_api_link([1, 0])
+    assert not is_canonical_api_link(["1", "0"])
+    assert not is_canonical_api_link(["1", False])
+    assert not is_canonical_api_link([640, 480])
+
+
 def test_is_api_link_rejects_bad_shapes() -> None:
     assert not is_api_link(None)
     assert not is_api_link({"node": "1", "slot": 0})
     assert not is_api_link(["1"])
     assert not is_api_link(["1", 0, "extra"])
     assert not is_api_link(["abc", 0])
     assert not is_api_link(["", 0])
 
 
 def test_is_api_link_can_allow_tuple_links() -> None:
     assert not is_api_link(("1", 0))
     assert is_api_link(("1", 0), allow_tuple=True)
 
 
 def test_is_api_link_can_preserve_schema_style_string_source_ids() -> None:
     assert is_api_link(
         ("source_node", 0),
         allow_tuple=True,
         require_string_node_id=True,
         require_numeric_node_id=False,
         require_int_slot=True,
     )
 
 
 def test_is_api_link_strict_string_node_id_rejects_numeric_source_ids() -> None:
     assert not is_api_link([1, 0], require_string_node_id=True)
     assert is_api_link(["1", 0], require_string_node_id=True)
 
 
 def test_is_api_link_strict_int_slot_rejects_non_int_slots() -> None:
     assert not is_api_link(["1", "0"], require_int_slot=True)
     assert is_api_link(["1", 0], require_int_slot=True)
 
 
 def test_is_api_link_can_allow_compound_numeric_node_ids() -> None:
     assert not is_api_link(["76:67", 0])
     assert is_api_link(["76:67", 0], allow_compound_node_id=True, require_int_slot=True)
     assert not is_api_link(["76:abc", 0], allow_compound_node_id=True)
 
 
 def test_is_api_link_tool_mode_is_string_source_strict_with_compound_ids() -> None:
     tool_mode = {
         "allow_tuple": False,
         "require_string_node_id": True,
         "require_numeric_node_id": True,
         "allow_compound_node_id": True,
         "require_int_slot": True,
     }
 
     assert not is_api_link([1, 0], **tool_mode)
     assert is_api_link(["1", 0], **tool_mode)
     assert is_api_link(["76:67", 0], **tool_mode)
     assert not is_api_link(["76:67", "0"], **tool_mode)
 
 
 def test_workflow_helpers_is_api_link_narrowing_rejects_string_and_float_slots() -> None:
     # The old body used int(value[1]) coercion, accepting "3" and 3.5.
     # The new body uses isinstance(slot, int) via require_int_slot=True, narrowing both to False.
     # first_link_input and resolve_compile_link_value only see real compiled API links
     # where slots are always ints, so the narrowing is safe.
diff --git a/tests/test_layout_store.py b/tests/test_layout_store.py
index 21d86036..e98e63b9 100644
--- a/tests/test_layout_store.py
+++ b/tests/test_layout_store.py
@@ -62,122 +62,123 @@ def test_sidecar_path_naming(tmp_path: Path):
 
 # ---------------------------------------------------------------------------
 # write → read round-trip
 # ---------------------------------------------------------------------------
 
 
 def test_write_read_round_trip(tmp_path: Path):
     py_path = tmp_path / "flat.py"
     wf = _wf()
     wf.nodes["1"] = _node("1", uid="1", pos=[0, 120], size=[315, 98])
     wf.nodes["2"] = _node("2", uid="2", pos=[430, 10], size=[430, 160])
 
     written = write_layout(py_path, wf)
     assert written == sidecar_path_for(py_path)
     assert written.exists()
 
     layout = read_layout(py_path)
     assert layout["1"]["pos"] == [0, 120]
     assert layout["1"]["size"] == [315, 98]
     assert layout["2"]["pos"] == [430, 10]
     assert layout["2"]["size"] == [430, 160]
 
 
 def test_sidecar_schema_version(tmp_path: Path):
     """M1.5 schema-version assertion updated (authorized by SD3): envelope v2."""
     py_path = tmp_path / "flat.py"
     wf = _wf()
     wf.nodes["1"] = _node("1", uid="1", pos=[0, 0], size=[100, 100])
     write_layout(py_path, wf)
 
     raw = json.loads(sidecar_path_for(py_path).read_text())
     assert raw["store_version"] == STORE_VERSION == 2
     assert "layout_version" not in raw
     # Envelope sections present.
     for key in ("entries", "groups", "extra", "lastRerouteId", "definitions", "virtual_wires"):
         assert key in raw
     assert "vibecomfy_version" in raw
     assert "schema_hash" in raw
 
 
 def test_envelope_full_round_trip(tmp_path: Path):
     """Full envelope round-trips per-uid blob + graph-level sections."""
     py_path = tmp_path / "flat.py"
     wf = _wf()
     n = VibeNode(
         "1",
         "SaveImage",
         metadata={
             "_ui": {
                 "pos": [10, 20],
                 "size": [300, 100],
                 "flags": {"collapsed": True},
                 "color": "#223",
                 "bgcolor": "#000",
                 "properties": {"vibecomfy_uid": "abc", "extra": 1},
             }
         },
     )
     n.uid = "1"
     wf.nodes["1"] = n
+    wf.groups = [{"title": "g1", "bounding": [0, 0, 50, 50]}]
     wf.metadata["_layout"] = {
-        "groups": [{"title": "g1", "bounding": [0, 0, 50, 50]}],
+        "groups": [{"title": "stale-metadata-group"}],
         "extra": {"ds": {"scale": 1.5, "offset": [3, 4]}},
         "lastRerouteId": 7,
         "definitions": {"sub": {"nodes": []}},
         "virtual_wires": {"u9": {"type": "GetNode", "channel": "LATENT", "endpoints": ["a", "b"]}},
     }
 
     write_layout(py_path, wf)
     store = read_store(py_path)
 
     entry = store["entries"]["1"]
     assert entry["pos"] == [10, 20]
     assert entry["size"] == [300, 100]
     assert entry["flags"] == {"collapsed": True}
     assert entry["color"] == "#223"
     assert entry["bgcolor"] == "#000"
     assert entry["properties"] == {"vibecomfy_uid": "abc", "extra": 1}
 
     assert store["groups"] == [{"title": "g1", "bounding": [0, 0, 50, 50]}]
     assert store["extra"]["ds"] == {"scale": 1.5, "offset": [3, 4]}
     assert store["lastRerouteId"] == 7
     assert store["definitions"] == {"sub": {"nodes": []}}
     assert store["virtual_wires"]["u9"]["channel"] == "LATENT"
 
 
 def test_pos_canonicalized_on_write(tmp_path: Path):
     """Fractional pos/size are snapped to whole pixels (T3 round-half-even)."""
     py_path = tmp_path / "flat.py"
     wf = _wf()
     wf.nodes["1"] = _node("1", uid="1", pos=[0.5, 1.5], size=[2.5, 100.4])
     write_layout(py_path, wf)
 
     entry = read_layout(py_path)["1"]
     assert entry["pos"] == [0, 2]  # 0.5->0, 1.5->2 (banker's rounding)
     assert entry["size"] == [2, 100]
 
 
 def test_envelope_graceful_absent_sections(tmp_path: Path):
     """When metadata has no _layout sections, envelope still serializes defaults."""
     py_path = tmp_path / "flat.py"
     wf = _wf()
     wf.nodes["1"] = _node("1", uid="1", pos=[0, 0], size=[10, 10])
     write_layout(py_path, wf)
 
     store = read_store(py_path)
     assert store["groups"] == []
     assert store["extra"] == {}
     assert store["lastRerouteId"] is None
     assert store["definitions"] == {}
     assert store["virtual_wires"] == {}
 
 
 # ---------------------------------------------------------------------------
 # Skip conditions
 # ---------------------------------------------------------------------------
 
 
 def test_skip_empty_uid(tmp_path: Path):
     """Nodes with empty uid are not written to the sidecar."""
     py_path = tmp_path / "flat.py"
     wf = _wf()
@@ -571,122 +572,122 @@ def test_inner_definition_entries_keyed_by_scoped_uid(tmp_path: Path):
     assert "1" in store["entries"]
 
 
 def test_inner_definition_uses_vibecomfy_uid_property(tmp_path: Path):
     """An inner node carrying properties['vibecomfy_uid'] is keyed by that uid."""
     from vibecomfy.identity.scope import compose_scope_path, sg_key
     from vibecomfy.identity.uid import make_uid
 
     inner = {
         "id": 7,
         "type": "KSampler",
         "pos": [0, 0],
         "properties": {"vibecomfy_uid": "carried-uid"},
     }
     definition = _sg_def("Upscale", [inner])
 
     wf = _wf()
     wf.metadata["definitions"] = {"subgraphs": [definition]}
 
     py_path = tmp_path / "flat.py"
     write_layout(py_path, wf)
     store = read_store(py_path)
 
     scope_path = compose_scope_path((sg_key(definition),))
     assert make_uid(scope_path, "carried-uid") in store["entries"]
 
 
 def test_inner_definition_clones_share_definition_no_crash(tmp_path: Path):
     """Two definitions with colliding inner ids yield distinct scoped uids."""
     d1 = _sg_def("A", [{"id": 1, "type": "KSampler", "pos": [0, 0]}])
     d2 = _sg_def(
         "B", [{"id": 1, "type": "VAEDecode", "pos": [5, 5]}]
     )  # same inner id, different topology
 
     wf = _wf()
     wf.metadata["definitions"] = {"subgraphs": [d1, d2]}
 
     py_path = tmp_path / "flat.py"
     write_layout(py_path, wf)
     store = read_store(py_path)
 
     # Distinct scope_paths -> distinct uids despite the colliding inner id 1.
     assert len(store["entries"]) == 2
 
 
 # ---------------------------------------------------------------------------
 # T12: Capture-verification tests — corpus spot-checks
 # ---------------------------------------------------------------------------
 
 
 def _load_with_furniture(corpus_path: str, tmp_path: Path, tmp_suffix: str = "wf") -> tuple:
     """Load a corpus JSON, populate graph-level furniture from raw_workflow, write layout.
 
     Returns (wf, store, entries) for assertion.
     """
     from vibecomfy.porting.workbench import load_port_source
 
     source = load_port_source(corpus_path)
     wf = source.workflow
     raw = source.raw_workflow or {}
-    # Populate graph-level sections into metadata so write_layout can read them.
-    wf.metadata["groups"] = raw.get("groups", [])
+    # Groups are first-class IR state; other graph-level sections use metadata.
+    wf.groups = raw.get("groups", [])
     wf.metadata["extra"] = raw.get("extra", {})
     if "lastRerouteId" in raw:
         wf.metadata["lastRerouteId"] = raw["lastRerouteId"]
 
     py_path = tmp_path / f"{tmp_suffix}.py"
     write_layout(py_path, wf)
     store = read_store(py_path)
     return wf, store, store["entries"]
 
 
 def test_corpus_vace_cnr_id_ver_properties_survive(tmp_path: Path):
     """wan13b_vace.json: cnr_id/ver properties, pos/size, flags survive ingest→store (C9)."""
     wf, store, entries = _load_with_furniture(
         "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json",
         tmp_path,
         "vace",
     )
 
     # At least all nodes with _ui.pos have entries.
     assert len(entries) > 0
 
     # Node carrying cnr_id + ver (full properties blob).
     cnr_entry = next(
         (e for e in entries.values() if e.get("properties", {}).get("cnr_id")),
         None,
     )
     assert cnr_entry is not None, "No entry with cnr_id found"
     assert cnr_entry["properties"]["cnr_id"] == "ComfyUI-WanVideoWrapper"
     assert cnr_entry["properties"]["ver"]  # non-empty hash string
     assert cnr_entry["pos"] is not None
     assert cnr_entry["size"] is not None
 
     # Node with only partial properties (previousName, no cnr_id) — unknown key survives.
     partial_entry = next(
         (
             e
             for e in entries.values()
             if e.get("properties")
             and "previousName" in e["properties"]
             and "cnr_id" not in e["properties"]
         ),
         None,
     )
     assert partial_entry is not None, "No partial-props entry found"
     # 'previousName' is an unknown/extra key — must survive verbatim.
     assert "previousName" in partial_entry["properties"]
 
     # flags survive (GetNode 124 is collapsed).
     uid_124 = "124"
     if uid_124 in entries:
         assert entries[uid_124]["flags"] == {"collapsed": True}
 
     # color/bgcolor survive.
     colored = next(
         (e for e in entries.values() if e.get("color")),
         None,
     )
     assert colored is not None, "No entry with color found"
     assert colored.get("bgcolor")
 
diff --git a/tests/test_patches.py b/tests/test_patches.py
index 5eb90dd6..5f48ced3 100644
--- a/tests/test_patches.py
+++ b/tests/test_patches.py
@@ -1,76 +1,76 @@
 from __future__ import annotations
 
 import inspect
 import os
 import subprocess
 import sys
 from pathlib import Path
 
 import pytest
 
 from vibecomfy.patches.registry import find_applicable, register, registered_patches
 from vibecomfy.patches.ltx_lowvram import COMFY_CONFIGURATION, FP8_CHECKPOINT, SOURCE_CHECKPOINT, patch as ltx_lowvram
 from vibecomfy.patches.requirements import ensure_custom_nodes
 from vibecomfy.patches.seed import seed
 from vibecomfy.patches.types import Patch
-from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
+from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
 
 
 def test_patch_contract_documents_decoration_not_handle_construction() -> None:
     contract = inspect.getdoc(Patch) or ""
 
     assert "decoration of an existing workflow graph" in contract
     assert "Construction APIs" in contract
     assert "return public handles belong in blocks or ready workflows" in contract
     assert "public result is always the same" in contract
     assert "must not introduce a new handle-producing API" in contract
     assert "conservative, side-effect-free predicate" in contract
     assert "idempotent" in contract
     assert "fail clearly" in contract
     assert "silently leaving the graph unchanged" in contract
 
 
 def test_builtin_patches_remain_discoverable_from_registry() -> None:
     builtin_names = {patch.name for patch in registered_patches(include_builtins=True)}
 
     assert {"controlnet", "gguf_unet", "ltx_lowvram"} <= builtin_names
 
 
 def test_patch_package_import_does_not_register_builtins() -> None:
     script = """
 import vibecomfy.patches
 from vibecomfy.patches.registry import _PATCHES, bootstrap_builtin_patches, registered_patches
 
 print(",".join(sorted(_PATCHES)))
 print(",".join(sorted(patch.name for patch in bootstrap_builtin_patches())))
 print(",".join(sorted(_PATCHES)))
 print(",".join(sorted(patch.name for patch in registered_patches())))
 """
     env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
     result = subprocess.run(
         [sys.executable, "-c", script],
         check=True,
         cwd=Path.cwd(),
         env=env,
         capture_output=True,
         text=True,
     )
 
     before_bootstrap, builtin_names, after_bootstrap, registered_names = result.stdout.splitlines()
     assert before_bootstrap == ""
     assert builtin_names == "controlnet,gguf_unet,ltx_lowvram"
     assert after_bootstrap == ""
     assert registered_names == builtin_names
 
 
 def test_find_applicable_uses_builtin_tuple_and_external_registry() -> None:
     workflow = VibeWorkflow("patch-registry-test", WorkflowSource("patch-registry-test"))
     external = Patch("external", lambda candidate: candidate is workflow, lambda candidate: candidate, lambda _: "test")
 
     register(external)
 
     assert external in registered_patches(include_builtins=False)
     assert external in find_applicable(workflow)
 
 
 def test_patch_apply_preserves_return_value_and_compiled_api_for_metadata_only_patch() -> None:
@@ -104,134 +104,137 @@ def test_patch_apply_preserves_return_value_and_compiled_api_for_metadata_only_p
 
 def test_seed_patch_records_value_change_without_topology_change() -> None:
     workflow = VibeWorkflow("seed-only", WorkflowSource("seed-only"))
     workflow.nodes["sampler"] = VibeNode("sampler", "KSampler", inputs={"seed": 1, "steps": 4})
     before = workflow.compile("api")
 
     patched = seed(99)
     result = patched.apply(workflow)
 
     assert result is workflow
     assert workflow.compile("api") == {
         **before,
         "sampler": {
             **before["sampler"],
             "inputs": {
                 **before["sampler"]["inputs"],
                 "seed": 99,
             },
         },
     }
     assert workflow.metadata["patch_applications"] == [
         {
             "name": "seed:99",
             "layer": "patch",
             "called": True,
             "topology_changed": False,
             "nodes_added": [],
             "introduced_edges": [],
             "rewritten_edges": [],
             "value_changed": True,
         }
     ]
 
 
 def test_ensure_custom_nodes_appends_without_duplicates() -> None:
     workflow = VibeWorkflow("requirements-test", WorkflowSource("requirements-test"))
     workflow.requirements.custom_nodes.append("Existing")
 
     ensure_custom_nodes(workflow, ("Existing", "New"))
     ensure_custom_nodes(workflow, ("New",))
 
     assert workflow.requirements.custom_nodes == ["Existing", "New"]
 
 
 def test_ltx_lowvram_rewrites_supported_graph() -> None:
     positive = _supported_ltx_workflow()
     positive.metadata["ready_template"] = "video/ltx2_3_t2v"
 
     assert ltx_lowvram.applies_to(positive)
 
     ltx_lowvram.apply(positive)
 
     assert positive.metadata["comfy_configuration"] == COMFY_CONFIGURATION
     assert positive.metadata["smoke_resolution"] == "384x256x9_frames"
     assert positive.metadata["external_python_marker"] == "external_python:video/ltx2_3_t2v"
     assert positive.nodes["4010"].class_type == "LTXVAudioVAELoader"
     assert positive.nodes["4010"].inputs == {"ckpt_name": FP8_CHECKPOINT}
     assert positive.nodes["4010"].widgets == {}
     assert positive.nodes["3940"].class_type == "LowVRAMCheckpointLoader"
     assert positive.nodes["3940"].inputs["ckpt_name"] == FP8_CHECKPOINT
+    assert "dependencies" not in positive.nodes["3940"].inputs
+    assert VibeEdge("4960", "0", "3940", "dependencies") in positive.edges
     assert "ComfyUI-LTXVideo" in positive.requirements.custom_nodes
     assert "ComfyUI-KJNodes" in positive.requirements.custom_nodes
 
 
 def test_ltx_lowvram_accepts_already_applied_supported_graph_idempotently() -> None:
     workflow = _supported_ltx_workflow()
     ltx_lowvram.apply(workflow)
     first_api = workflow.compile("api")
 
     assert not ltx_lowvram.applies_to(workflow)
 
     ltx_lowvram.apply(workflow)
 
     assert workflow.compile("api") == first_api
     assert workflow.requirements.custom_nodes.count("ComfyUI-LTXVideo") == 1
     assert workflow.requirements.custom_nodes.count("ComfyUI-KJNodes") == 1
 
 
 def test_ltx_lowvram_rejects_non_ltx_and_unsupported_ltx_like_graphs() -> None:
     negative = VibeWorkflow("plain", WorkflowSource("plain"))
     negative.add_node("SaveImage", images="placeholder")
 
     assert not ltx_lowvram.applies_to(negative)
     with pytest.raises(ValueError, match="ltx_lowvram only supports LTX 2.3 workflows"):
         ltx_lowvram.apply(negative)
 
     unsupported = VibeWorkflow("ltx-like", WorkflowSource("ltx-like"))
     unsupported.add_node("LTXVLoader")
     unsupported.nodes["4010"] = VibeNode(id="4010", class_type="LTXVAudioVAELoader", inputs={"ckpt_name": "other.safetensors"})
     unsupported.nodes["3940"] = VibeNode(id="3940", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": SOURCE_CHECKPOINT})
 
     assert not ltx_lowvram.applies_to(unsupported)
     with pytest.raises(ValueError, match="ltx_lowvram only supports LTX 2.3 workflows"):
         ltx_lowvram.apply(unsupported)
 
 
 def test_ltx_lowvram_generated_ready_template_applies_before_metadata_policy() -> None:
     from ready_templates.video.ltx2_3_t2v import build
 
     workflow = build()
 
     assert workflow.metadata["ready_template"] == "video/ltx2_3_t2v"
     assert workflow.nodes["4010"].class_type == "LTXVAudioVAELoader"
     assert workflow.nodes["3940"].class_type == "LowVRAMCheckpointLoader"
     assert workflow.nodes["4010"].inputs["ckpt_name"] == FP8_CHECKPOINT
     assert workflow.nodes["3940"].inputs["ckpt_name"] == FP8_CHECKPOINT
     api = workflow.compile("api")
     assert api["3059"]["inputs"]["batch_size"] == 1
     assert api["3980"]["inputs"]["batch_size"] == 1
     assert api["4981"]["inputs"]["longer_size"] == 384
     assert api["4981"]["inputs"]["resize_type.longer_size"] == 384
     assert api["4966"]["inputs"]["max_shift"] == 2.05
     assert api["4966"]["inputs"]["base_shift"] == 0.95
     assert api["4966"]["inputs"]["stretch"] is True
     assert api["4966"]["inputs"]["terminal"] == 0.1
     assert api["4963"]["inputs"]["cross_attn"] is True
     assert api["4964"]["inputs"]["modality"] == "VIDEO"
     assert api["4808"]["inputs"]["skip_blocks"] == "28"
     assert api["4982"]["inputs"]["last_frame_fix"] is False
     assert api["4983"]["inputs"]["last_frame_fix"] is False
     assert "audio" not in api["4819"]["inputs"]
     assert "audio" not in api["4849"]["inputs"]
     assert api["4823"]["inputs"]["format"] == "auto"
     assert api["4823"]["inputs"]["codec"] == "auto"
     assert api["4852"]["inputs"]["format"] == "auto"
     assert api["4852"]["inputs"]["codec"] == "auto"
 
 
 def _supported_ltx_workflow() -> VibeWorkflow:
     workflow = VibeWorkflow("ltx", WorkflowSource("ltx"))
     workflow.add_node("LTXVScheduler")
+    workflow.nodes["4960"] = VibeNode(id="4960", class_type="LTXAVTextEncoderLoader")
     workflow.nodes["4010"] = VibeNode(id="4010", class_type="LTXVAudioVAELoader", inputs={"ckpt_name": SOURCE_CHECKPOINT})
     workflow.nodes["3940"] = VibeNode(id="3940", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": SOURCE_CHECKPOINT})
     return workflow
diff --git a/tests/test_porting_normalize_ingest.py b/tests/test_porting_normalize_ingest.py
index 02f79d2b..007aa6eb 100644
--- a/tests/test_porting_normalize_ingest.py
+++ b/tests/test_porting_normalize_ingest.py
@@ -699,121 +699,122 @@ def test_vibe_rich_ingest_preserves_90a1d5() -> None:
     by_id = {str(node["id"]): node for node in normalized["nodes"]}
     assert set(by_id) == set(raw["nodes"])
     for nid, rich in raw["nodes"].items():
         ui_node = by_id[nid]
         assert ui_node["type"] == rich["class_type"]
         assert ui_node["mode"] == rich["metadata"]["_ui"]["mode"]
         assert (ui_node.get("properties") or {})["vibecomfy_uid"] == rich["uid"]
 
 
 def test_vibe_rich_ingest_ignores_optional_compiled_api_evidence() -> None:
     """Rich structure remains authoritative without stored execution evidence or with bad evidence."""
     raw = _load_90a1d5()
 
     assert "compiled_api" not in raw
     assert len(from_envelope(raw).nodes) == 15
 
     malformed_evidence = deepcopy(raw)
     malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}
     workflow = from_envelope(malformed_evidence)
     assert len(workflow.nodes) == 15
     assert workflow.nodes["10"].class_type == "TripoRefineNode"
 
 
 def test_public_loaders_preserve_rich_envelope_90a1d5() -> None:
     """load_workflow_any / load_port_source decode envelopes losslessly (P1).
 
     Public loaders must return the full 15-node IR, not the 2-node compile
     view: they decode the envelope directly instead of compile-then-reingest.
     The execution view (compile("api")) is unchanged at 2 nodes.
     """
     from vibecomfy.cli_loader import load_workflow_any
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
     wf2 = from_api(api2)
     assert len(wf2.nodes) == 15 and len(wf2.edges) == 10
 
-    ui2 = emit_ui_json(wf2, schema_provider=None, groups=deepcopy(ui1.get("groups")))
+    wf2.groups = deepcopy(ui1.get("groups"))
+    ui2 = emit_ui_json(wf2, schema_provider=None)
 
     assert _ui_projection(ui1) == _ui_projection(ui2)
 
 
 def test_vibe_rich_ingest_rejects_malformed_mixed_entries() -> None:
     """Malformed/mixed rich entries raise ValueError; no partial graph is returned."""
     raw = _load_90a1d5()
 
     mixed_nodes = deepcopy(raw)
     mixed_nodes["nodes"]["999"] = "not-a-node"
     with pytest.raises(ValueError, match="must be mappings"):
         from_envelope(mixed_nodes)
 
     key_mismatch = deepcopy(raw)
     key_mismatch["nodes"]["10"]["id"] = "11"
     with pytest.raises(ValueError, match="must equal node.id"):
         from_envelope(key_mismatch)
 
     blank_uid = deepcopy(raw)
     blank_uid["nodes"]["10"]["uid"] = "  "
     with pytest.raises(ValueError, match="uid must be a nonblank string"):
         from_envelope(blank_uid)
 
     negative_length = deepcopy(raw)
     negative_length["nodes"]["10"]["raw_widgets"]["length"] = -1
     with pytest.raises(ValueError, match="nonnegative integer"):
         from_envelope(negative_length)
 
     non_mapping_edges = deepcopy(raw)
     non_mapping_edges["edges"] = ["not-an-edge"]
     with pytest.raises(ValueError, match="must be mappings"):
         from_envelope(non_mapping_edges)
 
 
 def test_vibe_rich_ingest_rejects_dangling_endpoint_edges() -> None:
     """Edges referencing endpoint node ids absent from nodes raise ValueError."""
     raw = _load_90a1d5()
 
     dangling_from = deepcopy(raw)
     dangling_from["edges"] = [
         {"from_node": "999", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
     ]
     with pytest.raises(ValueError, match="must exist in nodes"):
         from_envelope(dangling_from)
 
     dangling_to = deepcopy(raw)
     dangling_to["edges"] = [
         {"from_node": "3", "from_output": "0", "to_node": "424242", "to_input": "model_file"}
     ]
     with pytest.raises(ValueError, match="must exist in nodes"):
         from_envelope(dangling_to)
 
     blank_endpoint = deepcopy(raw)
     blank_endpoint["edges"] = [
         {"from_node": "", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
     ]
     with pytest.raises(ValueError, match="from_node must be a nonblank string"):
         from_envelope(blank_endpoint)
 
 
diff --git a/tests/test_porting_synthetic_fixtures.py b/tests/test_porting_synthetic_fixtures.py
index 44017fe6..a68f0d98 100644
--- a/tests/test_porting_synthetic_fixtures.py
+++ b/tests/test_porting_synthetic_fixtures.py
@@ -103,187 +103,187 @@ def _make_virtual_wire_wf() -> tuple[VibeWorkflow, int]:
     wf.nodes["11"] = _virtual_node("11", "GetNode", channel="LATENT", pos=[700, 0], size=[200, 58])
     wf.nodes["12"] = _virtual_node("12", "SetNode", channel="IMAGE", pos=[400, 100], size=[200, 58])
     wf.nodes["13"] = _virtual_node("13", "Reroute", pos=[600, 100], size=[75, 26])
     return wf, 4  # 4 virtual-wire nodes
 
 
 # ---------------------------------------------------------------------------
 # T15.1: Virtual-wire round-trip on synthetic fixture
 # ---------------------------------------------------------------------------
 
 
 def test_virtual_wire_round_trip_synthetic(tmp_path: Path):
     """Synthetic fixture: virtual-wire count in == count in store (round-trip parity)."""
     from vibecomfy.porting.convert import _capture_virtual_wires
 
     wf, count_virtual = _make_virtual_wire_wf()
 
     # Capture virtual wires (simulating pre-resolution capture in port_convert_workflow).
     vw = _capture_virtual_wires(wf)
     wf.metadata["virtual_wires"] = vw
 
     py_path = tmp_path / "vw_synthetic.py"
     write_layout(py_path, wf)
     store = read_store(py_path)
 
     # Count in (pre-capture) == count out (store virtual_wires).
     assert len(store["virtual_wires"]) == count_virtual
     # Each entry has a type field.
     for uid, wire in store["virtual_wires"].items():
         assert "type" in wire
         assert wire["type"] in ("SetNode", "GetNode", "Reroute")
     # Entries also contain the virtual-wire node geometry.
     for uid in store["virtual_wires"]:
         assert uid in store["entries"]
         assert store["entries"][uid]["pos"] is not None
 
 
 # ---------------------------------------------------------------------------
 # T15.2: Virtual-wire round-trip on wan13b_vace.json (C8)
 # ---------------------------------------------------------------------------
 
 
 def test_virtual_wire_round_trip_vace_corpus(tmp_path: Path):
     """C8 — wan13b_vace.json: virtual-wire count in == count in store (round-trip parity)."""
     from vibecomfy.porting.convert import _capture_virtual_wires
     from vibecomfy.porting.workbench import load_port_source
 
     corpus_path = "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
     source = load_port_source(corpus_path)
     wf = source.workflow
 
     # Count the virtual-wire nodes before capture (they will be deleted by resolver).
     _VW_TYPES = {"GetNode", "SetNode", "Reroute"}
     vw_count_before = sum(1 for n in wf.nodes.values() if n.class_type in _VW_TYPES)
     assert vw_count_before > 0, "wan13b_vace.json must have Get/Set/Reroute nodes"
 
     # Capture virtual wires (pre-resolution snapshot).
     vw = _capture_virtual_wires(wf)
     wf.metadata["virtual_wires"] = vw
     raw = source.raw_workflow or {}
-    wf.metadata["groups"] = raw.get("groups", [])
+    wf.groups = raw.get("groups", [])
     wf.metadata["extra"] = raw.get("extra", {})
 
     py_path = tmp_path / "vace.py"
     write_layout(py_path, wf)
     store = read_store(py_path)
 
     # count in == count out
     assert len(store["virtual_wires"]) == vw_count_before, (
         f"Expected {vw_count_before} virtual wires; got {len(store['virtual_wires'])}"
     )
 
 
 # ---------------------------------------------------------------------------
 # T15.3: Scoped-path identity prevents inner-id collision across cloned instances
 # ---------------------------------------------------------------------------
 
 
 def test_scoped_identity_prevents_inner_id_collision(tmp_path: Path):
     """Two cloned subgraph definitions with colliding inner ids yield distinct uids."""
     from vibecomfy.identity.scope import compose_scope_path, sg_key
     from vibecomfy.identity.uid import make_uid
 
     # Two definitions with the SAME inner node id (1) but different topologies.
     def_a = {
         "name": "A",
         "nodes": [{"id": 1, "type": "KSampler", "pos": [0, 0]}],
         "links": [],
     }
     def_b = {
         "name": "B",
         "nodes": [{"id": 1, "type": "VAEDecode", "pos": [5, 5]}],
         "links": [],
     }
 
     wf = _wf("cloned-sg")
     wf.metadata["definitions"] = {"subgraphs": [def_a, def_b]}
 
     py_path = tmp_path / "cloned.py"
     write_layout(py_path, wf)
     store = read_store(py_path)
 
     # Two distinct scope_paths → two distinct uids, despite colliding inner id 1.
     uid_a = make_uid(compose_scope_path((sg_key(def_a),)), "1")
     uid_b = make_uid(compose_scope_path((sg_key(def_b),)), "1")
     assert uid_a != uid_b, "Distinct topologies must yield distinct uids"
     assert uid_a in store["entries"]
     assert uid_b in store["entries"]
     assert len(store["entries"]) == 2
 
 
 # ---------------------------------------------------------------------------
 # T15.4: Coordinate canonicalization — no float drift across repeated writes
 # ---------------------------------------------------------------------------
 
 
 def test_coord_canonicalization_no_float_drift(tmp_path: Path):
     """The same IR written twice yields bit-identical stored coords (no float drift)."""
     from vibecomfy.porting.workbench import load_port_source
     import json
 
     source = load_port_source(
         "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
     )
     wf = source.workflow
     raw = source.raw_workflow or {}
-    wf.metadata["groups"] = raw.get("groups", [])
+    wf.groups = raw.get("groups", [])
     wf.metadata["extra"] = raw.get("extra", {})
 
     py_path_1 = tmp_path / "first.py"
     py_path_2 = tmp_path / "second.py"
     write_layout(py_path_1, wf)
     write_layout(py_path_2, wf)
 
     store_1 = read_store(py_path_1)
     store_2 = read_store(py_path_2)
 
     # Every entry's pos must be bit-identical between the two writes.
     assert set(store_1["entries"]) == set(store_2["entries"])
     for uid in store_1["entries"]:
         pos_1 = store_1["entries"][uid]["pos"]
         pos_2 = store_2["entries"][uid]["pos"]
         assert pos_1 == pos_2, f"Float drift detected for uid {uid}: {pos_1} vs {pos_2}"
         size_1 = store_1["entries"][uid]["size"]
         size_2 = store_2["entries"][uid]["size"]
         assert size_1 == size_2, f"Float drift in size for uid {uid}: {size_1} vs {size_2}"
 
     # Entries must round-trip through json.dumps/loads unchanged.
     raw_json = json.dumps(store_1["entries"])
     reloaded = json.loads(raw_json)
     for uid, entry in reloaded.items():
         assert entry["pos"] == store_1["entries"][uid]["pos"]
 
 
 # ---------------------------------------------------------------------------
 # T15.5: Agent-edit safety — add/delete/add yields no uid collision, no stale pos
 # ---------------------------------------------------------------------------
 
 
 def test_agent_edit_safety_add_delete_add(tmp_path: Path):
     """add → delete → add cycle: no uid collision, no stale-position inheritance."""
     wf = _wf("edit-safety")
 
     # Step 1: add node A.
     wf.nodes["1"] = _node_with_ui("1", "KSampler", pos=[0, 0], size=[300, 100])
     py_path = tmp_path / "edit.py"
     write_layout(py_path, wf)
     store_after_add = read_store(py_path)
     uid_a = wf.nodes["1"].uid
 
     # Step 2: delete node A.
     del wf.nodes["1"]
     write_layout(py_path, wf)
     store_after_delete = read_store(py_path)
     assert uid_a not in store_after_delete["entries"], "Deleted node must not remain in store"
 
     # Step 3: add a NEW node at a different position using the same integer id slot.
     new_node = _node_with_ui("1", "VAEDecode", pos=[500, 500], size=[200, 80])
     wf.nodes["1"] = new_node
     write_layout(py_path, wf)
     store_after_readd = read_store(py_path)
 
     uid_b = new_node.uid
     # Both nodes got a uid (they share the int slot but the uid is distinct only if
     # the uid was minted differently; here uid defaults to node_id "1" in our helper,
     # so we test that the NEW geometry was written and the OLD pos was not inherited).
     assert uid_b in store_after_readd["entries"]
diff --git a/tests/test_porting_ui_emitter.py b/tests/test_porting_ui_emitter.py
index 3d248478..c7cc6368 100644
--- a/tests/test_porting_ui_emitter.py
+++ b/tests/test_porting_ui_emitter.py
@@ -2001,326 +2001,394 @@ def test_previously_flagged_files_pin_or_refuse_without_safe_overflow() -> None:
         report: list[dict] = []
         try:
             with warnings.catch_warnings():
                 warnings.simplefilter("ignore")
                 emit_ui_json(
                     wf,
                     strict=False,
                     prior_store=None,
                     prior_ui_payload=raw,
                     recovery_report=report,
                 )
         except RefusedEmit as exc:
             assert exc.diff, f"{result_entry['path']}: refusal must carry typed details"
             assert all(
                 detail.get("axis") == "widget_shape"
                 for detail in exc.diff.values()
             ), f"{result_entry['path']}: unexpected refusal diff {exc.diff}"
         except Exception as exc:
             raise AssertionError(
                 f"Previously-flagged file {result_entry['path']} raised {type(exc).__name__}: {exc}"
             ) from exc
         else:
             assert report, f"{result_entry['path']}: recovery_report must be populated"
             unsafe_overflow = [
                 item
                 for item in report
                 if item.get("widget_shape_verdict") == "safe_to_regenerate"
                 and "overflow" in str(item.get("widget_length_check", ""))
             ]
             assert not unsafe_overflow, (
                 f"{result_entry['path']}: overflow entries cannot be safe_to_regenerate"
             )
 
 
 def test_widget_order_matches_object_info_for_covered_class() -> None:
     """For a class present in the object_info cache, the raw widget order
     (nulls included) is authoritative for COUNT."""
     from vibecomfy.porting.emit.ui import _raw_widget_order_from_provider
     from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
 
     provider = ObjectInfoIndexSchemaProvider(
         root="vibecomfy/porting/cache/object_info"
     )
     raw_order = _raw_widget_order_from_provider("KSampler", provider)
     assert raw_order is not None, "KSampler should be in the object_info cache"
     # Raw order from the cache: [null, "seed", null, "steps", "cfg", "sampler_name", "scheduler", null, null, null, "denoise"]
     assert raw_order[0] is None, f"Expected first slot to be None (control_after_generate), got: {raw_order[0]}"
     assert raw_order[1] == "seed"
     assert raw_order[6] == "scheduler", f"Expected slot 6 to be scheduler, got: {raw_order[6]}"
     assert raw_order[9] is None, f"Expected slot 9 to be None (UI-only), got: {raw_order[9]}"
     assert raw_order[10] == "denoise"
     assert len(raw_order) == 11, f"Expected 11 raw slots for KSampler, got: {len(raw_order)}"
 
 
 # ---------------------------------------------------------------------------
 # T5: Furniture resolver (flags / color / bgcolor / mode / properties)
 # ---------------------------------------------------------------------------
 
 
 def test_furniture_from_sidecar_entry_roundtrip() -> None:
-    """Sidecar path: a layout entry with groups/colors/collapsed/mode is emitted faithfully."""
+    """Sidecar furniture is preserved while mode remains IR-authoritative."""
     wf = _wf("sidecar-test")
-    node = VibeNode("1", "SidecarNode")
+    node = VibeNode("1", "SidecarNode", mode=2)
     node.uid = "uid-aa"
     wf.nodes["1"] = node
 
     # Simulate a full sidecar entry as returned by read_store()["entries"]
     layout_entry = {
         "pos": [200.0, 300.0],
         "size": [400.0, 200.0],
         "flags": {"collapsed": True},
         "color": "#332",
         "bgcolor": "#553",
-        "mode": 2,
+        "mode": 4,
         "properties": {"Node name for S&R": "SidecarNode", "custom": "val"},
     }
     result = emit_ui_json(wf, layout={"uid-aa": layout_entry})
     emitted = result["nodes"][0]
 
     assert emitted["flags"] == {"collapsed": True}
     assert emitted["color"] == "#332"
     assert emitted["bgcolor"] == "#553"
     assert emitted["mode"] == 2
     # Sidecar properties are the base; IR-built overlay wins for vibecomfy keys.
     assert emitted["properties"]["custom"] == "val"
     assert emitted["properties"]["Node name for S&R"] == "SidecarNode"
     assert emitted["properties"]["vibecomfy_uid"] == "uid-aa"
     assert "vibecomfy_id" in emitted["properties"]
     assert "ir_node_id" not in emitted["properties"]
 
 
 def test_furniture_from_metadata_ui_fallback() -> None:
     """Direct-ingest fallback: node.metadata['_ui'] supplies furniture when no sidecar exists."""
     wf = _wf("ingest-test")
     node = VibeNode("1", "HasUI")
     node.uid = "uid-ingest"
     node.metadata["_ui"] = {
         "pos": [100, 150],
         "size": [300, 250],
         "flags": {"collapsed": False},
         "color": "#123",
         "bgcolor": "#456",
         "mode": 4,
         "properties": {"original": "yes"},
     }
     wf.nodes["1"] = node
 
     result = emit_ui_json(wf)  # no layout= param → falls through to _ui
     emitted = result["nodes"][0]
 
     assert emitted["flags"] == {"collapsed": False}
     assert emitted["color"] == "#123"
     assert emitted["bgcolor"] == "#456"
     assert emitted["mode"] == 4
     assert emitted["properties"]["original"] == "yes"
     assert emitted["properties"]["vibecomfy_uid"] == "uid-ingest"
 
 
 def test_furniture_absent_fields_fallback_to_defaults() -> None:
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
-    """Non-int mode values (None, string, float) are defaulted to 0."""
+    """Non-int sidecar mode values cannot override the IR's mode authority."""
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
 
 
-def test_furniture_groups_from_param() -> None:
-    """groups= param populates the top-level groups array."""
+def test_furniture_groups_from_ir() -> None:
+    """The first-class IR groups field populates the top-level groups array."""
     wf = _wf("gtest")
     wf.nodes["1"] = VibeNode("1", "N1")
 
     groups = [
         {"title": "Group A", "bounding": [0, 0, 400, 300], "color": "#3f3"},
         {"title": "Group B", "bounding": [500, 0, 400, 300], "color": "#33f"},
     ]
-    result = emit_ui_json(wf, groups=groups)
+    wf.groups = groups
+    result = emit_ui_json(wf)
     assert result["groups"] == groups
 
     # Default: empty list
+    wf.groups = []
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
     assert emitted["color"] == "#sc", "sidecar color should win"
     assert emitted["bgcolor"] == "#scbg", "sidecar bgcolor should win"
-    assert emitted["mode"] == 2, "sidecar mode should win"
+    assert emitted["mode"] == 4, "IR/_ui mode authority should beat sidecar mode"
     assert emitted["properties"]["from"] == "sidecar", "sidecar properties should win"
 
 
+@pytest.mark.parametrize(
+    ("mode", "sidecar_mode", "metadata_mode", "compiled"),
+    [(0, 2, 4, True), (2, 4, 0, False), (4, 0, 2, False)],
+)
+def test_emit_and_compile_share_mode_authority_despite_conflicts(
+    mode: int,
+    sidecar_mode: int,
+    metadata_mode: int,
+    compiled: bool,
+) -> None:
+    wf = _wf(f"mode-authority-{mode}")
+    node = VibeNode(
+        "1",
+        "LoadImage",
+        uid="uid-mode",
+        mode=mode,
+        metadata={"mode": metadata_mode},
+    )
+    wf.nodes["1"] = node
+    layout_entry = {
+        "pos": [0, 0],
+        "size": [100, 100],
+        "mode": sidecar_mode,
+    }
+
+    emitted = emit_ui_json(wf, layout={"uid-mode": layout_entry})
+
+    assert emitted["nodes"][0]["mode"] == mode
+    assert ("1" in wf.compile("api")) is compiled
+
+
+def test_ir_group_members_remap_all_live_aliases_and_omit_stale_members() -> None:
+    wf = _wf("group-members")
+    wf.nodes["author_a"] = VibeNode(
+        "41",
+        "NodeA",
+        uid="uid-a",
+        metadata={"_ui": {"id": 141}},
+    )
+    wf.nodes["author_b"] = VibeNode(
+        "author_b",
+        "NodeB",
+        uid="uid-b",
+        metadata={"_ui": {"id": "142"}},
+    )
+    wf.groups = [
+        {
+            "title": "Aliases",
+            "color": "#123456",
+            "nodes": ["author_a", 41, "uid-a", 141, "uid-b", "142", "stale", 999],
+        }
+    ]
+
+    emitted = emit_ui_json(wf)
+
+    assert emitted["groups"] == [
+        {
+            "title": "Aliases",
+            "color": "#123456",
+            "nodes": [1, 1, 1, 1, 2, 2],
+        }
+    ]
+    assert wf.groups[0]["nodes"][-2:] == ["stale", 999], "emission must not mutate IR"
+
+
 # ---------------------------------------------------------------------------
 # T10 — Mode emit for bypass/mute display (Step 8)
 # ---------------------------------------------------------------------------
 
 
 def test_node_captured_with_mode_4_reemits_mode_4() -> None:
     """T10: A node captured with mode 4 (bypassed) re-emits mode 4.
 
     This is the canonical round-trip: capture mode 4 in metadata['_ui'],
     emit through emit_ui_json, and confirm the emitted node carries mode: 4.
     """
     wf = _wf("mode4-roundtrip")
     node = VibeNode("1", "LoadImage")
     node.uid = "uid-mode4"
     node.metadata["_ui"] = {
         "pos": [100.0, 200.0],
         "size": [300.0, 250.0],
         "flags": {},
         "color": "#abc",
         "bgcolor": None,
         "mode": 4,
         "properties": {},
     }
     wf.nodes["1"] = node
 
     provider = _Provider({
         "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
     })
     result = emit_ui_json(wf, schema_provider=provider)
     emitted = result["nodes"][0]
 
     assert emitted["mode"] == 4, f"bypassed node must re-emit mode 4, got {emitted['mode']}"
     # Verify the node is otherwise intact
     assert emitted["type"] == "LoadImage"
     assert emitted["id"] == 1
 
 
 def test_node_captured_with_mode_2_reemits_mode_2() -> None:
     """T10: A node captured with mode 2 (muted) re-emits mode 2.
 
-    Captures mode 2 via the sidecar (layout=) path and confirms it
-    survives the full emit round-trip.
+    Captures mode 2 on the IR node and confirms a conflicting sidecar cannot
+    override it during the full emit round-trip.
     """
     wf = _wf("mode2-roundtrip")
     node = VibeNode("1", "SaveImage")
     node.uid = "uid-mode2"
+    node.mode = 2
     wf.nodes["1"] = node
 
     sidecar_entry = {
         "pos": [50.0, 60.0],
         "size": [400.0, 200.0],
         "flags": {},
         "color": None,
         "bgcolor": None,
-        "mode": 2,
+        "mode": 4,
         "properties": {},
     }
 
     provider = _Provider({
         "SaveImage": _schema("SaveImage", []),
     })
     result = emit_ui_json(wf, layout={"uid-mode2": sidecar_entry}, schema_provider=provider)
     emitted = result["nodes"][0]
 
     assert emitted["mode"] == 2, f"muted node must re-emit mode 2, got {emitted['mode']}"
     assert emitted["type"] == "SaveImage"
 
 
 def test_mode_emit_reflects_display_state() -> None:
     """T10: emit_ui_json re-emits the captured mode field in each node dict.
 
     Creates three identical workflows whose only difference is the captured
     mode (0=normal, 2=muted, 4=bypassed) and verifies that emit_ui_json
     re-emits the correct mode value.  compile('api') behavior for mode!=0
     is tested separately in test_compile_* (T11).
     """
     def _build_wf(mode_val: int) -> VibeWorkflow:
         wf = _wf(f"mode-emit-{mode_val}")
         li = VibeNode("1", "LoadImage")
         li.uid = "uid-li"
         li.metadata["_ui"] = {
             "pos": [10.0, 20.0], "size": [300.0, 200.0],
             "flags": {}, "color": None, "bgcolor": None,
             "mode": mode_val, "properties": {},
         }
         wf.nodes["1"] = li
 
         si = VibeNode("2", "SaveImage")
         si.uid = "uid-si"
         si.metadata["_ui"] = {
             "pos": [400.0, 20.0], "size": [300.0, 200.0],
             "flags": {}, "color": None, "bgcolor": None,
             "mode": mode_val, "properties": {},
         }
         wf.nodes["2"] = si
 
         wf.edges.append(VibeEdge("1", "0", "2", "images"))
         return wf
 
     provider = _Provider({
         "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
         "SaveImage": _schema("SaveImage", []),
     })
 
     wf0 = _build_wf(0)
     wf2 = _build_wf(2)
     wf4 = _build_wf(4)
 
     emit0 = emit_ui_json(wf0, schema_provider=provider)
     emit2 = emit_ui_json(wf2, schema_provider=provider)
     emit4 = emit_ui_json(wf4, schema_provider=provider)
 
     nodes0 = {n["id"]: n["mode"] for n in emit0["nodes"]}
     nodes2 = {n["id"]: n["mode"] for n in emit2["nodes"]}
     nodes4 = {n["id"]: n["mode"] for n in emit4["nodes"]}
@@ -2660,121 +2728,122 @@ def test_main_positions_node_title_from_metadata_ui() -> None:
 
 
 def test_main_positions_lean_omits_title() -> None:
     """When include_main_positions=False, node title is NOT emitted even when present."""
     wf = _wf("lean_title")
     wf.nodes["1"] = VibeNode(
         "1", "MyNode", uid="uid-lt",
         metadata={"_ui": {"pos": [10, 20], "size": [100, 80], "title": "ShouldHide"}},
     )
     wf.nodes["2"] = VibeNode("2", "SaveImage")
     wf.connect("1.0", "2.images")
 
     layout_entry = {"pos": [10, 20], "size": [100, 80], "title": "SidecarTitle"}
 
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         result = emit_ui_json(
             wf, layout={"uid-lt": layout_entry}, include_main_positions=False,
         )
 
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
-        result = emit_ui_json(wf, groups=groups, include_main_positions=True)
+        wf.groups = groups
+        result = emit_ui_json(wf, include_main_positions=True)
 
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
 
 
 def test_schema_version_1_0_roundtrip() -> None:
     """Step 13a (T17): Bump _LITEGRAPH_VERSION 0.4 → 1.0.
 
     Q2 guard: a version-1.0 emitted file re-ingests/normalizes cleanly,
     confirming the structural read path is version-agnostic.
     """
     from vibecomfy.ingest.normalize import _normalize_ui_to_api
     from vibecomfy.porting.emit.ui import _LITEGRAPH_VERSION as _VER
     from vibecomfy.porting.parity import compile_equivalent
 
     assert _VER == 1.0, f"_LITEGRAPH_VERSION should be 1.0, got {_VER}"
 
     wf = _wf("t17_rt")
     wf.nodes["1"] = VibeNode("1", "LoadImage", uid="load1")
     wf.nodes["2"] = VibeNode("2", "SaveImage", uid="save1")
     wf.nodes["3"] = VibeNode("3", "VAEDecode", uid="vae1")
     wf.connect("1.0", "3.pixels")
     wf.connect("3.0", "2.images")
 
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         ui = emit_ui_json(wf)
 
     # The envelope must carry version 1.0
     assert ui["version"] == 1.0, f"expected version 1.0, got {ui['version']!r}"
 
     # Re-ingest/re-normalize should work cleanly (version-agnostic read)
     api = wf.compile("api")
@@ -2919,156 +2988,157 @@ def test_pin_opaque_blank_uid_refuses_instead_of_emitting() -> None:
 
 
 # ---------------------------------------------------------------------------
 # T9a — reconcile() called with the full envelope (not just flat entries)
 # ---------------------------------------------------------------------------
 
 
 def test_reconcile_called_with_full_envelope(monkeypatch) -> None:
     """emit_ui_json must hand the FULL prior-store envelope (entries + groups +
     extra + definitions + virtual_wires) to reconcile(), not just flat entries.
 
     Spies on vibecomfy.porting.layout.reconcile.reconcile and asserts the call.
     """
     from vibecomfy.porting.layout import reconcile as reconcile_mod
 
     captured: dict[str, object] = {}
     real_reconcile = reconcile_mod.reconcile
 
     def spy(current_wf, prior_store):
         captured["wf"] = current_wf
         captured["prior_store"] = prior_store
         return real_reconcile(current_wf, prior_store)
 
     monkeypatch.setattr(reconcile_mod, "reconcile", spy)
 
     wf = _wf()
     wf.nodes["1"] = VibeNode("1", "LoadImage")
     wf.nodes["2"] = VibeNode("2", "SaveImage")
     wf.connect("1.0", "2.images")
 
     envelope = {
         "entries": {"some-uid": {"pos": [10.0, 20.0], "size": [200.0, 100.0]}},
         "groups": [{"title": "G", "bounding": [0, 0, 100, 100]}],
         "extra": {"ds": {"scale": 1.0}},
         "definitions": {"subgraph-uuid:abc": {"inner_entries": {}}},
         "virtual_wires": [{"source": "a", "target": "b"}],
     }
 
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         emit_ui_json(wf, prior_store=envelope)
 
     assert "prior_store" in captured, "reconcile() was not called"
     passed = captured["prior_store"]
     assert isinstance(passed, dict)
     # Every envelope key must reach reconcile() — proves we pass the FULL
     # envelope, not just flat entries.
     for key in ("entries", "groups", "extra", "definitions", "virtual_wires"):
         assert key in passed, f"reconcile() did not receive '{key}': {sorted(passed)}"
     assert passed["entries"] == envelope["entries"]
     assert passed["groups"] == envelope["groups"]
     assert passed["virtual_wires"] == envelope["virtual_wires"]
 
 
 # ---------------------------------------------------------------------------
 # T9b — reconcile-driven merge: matched verbatim, new anchored, unmatched engine
 # ---------------------------------------------------------------------------
 
 
 def test_preserve_merge_matched_verbatim_new_anchored() -> None:
-    """A uid-matched node carries pos/size/mode/flags/color/properties verbatim
-    from the prior_store entry; a new (uidless) wired neighbor is anchored to
-    the matched node via computed_anchors and placed by the layout engine.
+    """A matched node carries sidecar geometry/furniture except IR-owned mode.
+
+    A new (uidless) wired neighbor is anchored to the matched node via
+    computed_anchors and placed by the layout engine.
     """
     wf = _wf()
     a = VibeNode("1", "LoadImage")
     a.uid = "uid-a"
     b = VibeNode("2", "SaveImage")  # uidless → "new"
     wf.nodes["1"] = a
     wf.nodes["2"] = b
     wf.connect("1.0", "2.images")
 
     envelope = {
         "entries": {
             "uid-a": {
                 "pos": [123.0, 456.0],
                 "size": [222.0, 111.0],
                 "mode": 2,
                 "flags": {"collapsed": True},
                 "color": "#abc",
                 "bgcolor": "#def",
                 "properties": {"cnr_id": "verbatim"},
                 "title": "Carried",
             }
         }
     }
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         result = emit_ui_json(wf, prior_store=envelope, include_main_positions=True)
 
     by_uid = {n["properties"].get("vibecomfy_uid"): n for n in result["nodes"]}
     matched_node = by_uid["uid-a"]
-    # Verbatim pos/size/mode/flags from the prior_store entry.
+    # Geometry and display furniture come from the prior store; mode does not.
     assert matched_node["pos"] == [123.0, 456.0]
     assert matched_node["size"] == [222.0, 111.0]
-    assert matched_node["mode"] == 2
+    assert matched_node["mode"] == 0
     assert matched_node["flags"] == {"collapsed": True}
     assert matched_node["color"] == "#abc"
     assert matched_node["bgcolor"] == "#def"
     # Properties carried verbatim; IR identity keys overlaid on top.
     assert matched_node["properties"]["cnr_id"] == "verbatim"
     assert matched_node["properties"]["vibecomfy_uid"] == "uid-a"
     # title emitted only with include_main_positions=True
     assert matched_node["title"] == "Carried"
 
     # The new (uidless) node is NOT positioned at the matched node's pos
     # (i.e. didn't accidentally inherit it) and was placed by the engine.
     new_node = next(n for n in result["nodes"] if n["type"] == "SaveImage")
     assert new_node["pos"] != [123.0, 456.0]
     assert isinstance(new_node["pos"], list) and len(new_node["pos"]) == 2
 
 
 def test_unmatched_legacy_routed_through_engine() -> None:
     """When prior_store has entries no current node matches (unmatched_legacy /
     removed-then-readded), those positions are NOT applied to the current
     nodes — current nodes route through the layout engine without anchors.
     """
     wf = _wf()
     n = VibeNode("1", "LoadImage")
     n.uid = "current-uid"
     wf.nodes["1"] = n
 
     envelope = {
         "entries": {
             # Wholly unrelated uid → unmatched_legacy / removed.
             "ghost-uid": {"pos": [9999.0, 8888.0], "size": [50.0, 50.0]},
         }
     }
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         result = emit_ui_json(wf, prior_store=envelope)
 
     emitted = result["nodes"][0]
     # The current node does not adopt the ghost-uid coordinates.
     assert emitted["pos"] != [9999.0, 8888.0]
     # No vibecomfy_uid stamp from the ghost entry leaks in.
     assert emitted["properties"]["vibecomfy_uid"] == "current-uid"
 
 
 def test_uidless_workflow_degrades_to_fresh_layout() -> None:
     """A workflow with no uids and an empty prior_store has nothing matched.
     All nodes route through the layout engine (fresh layout).
     """
     wf = _wf()
     wf.nodes["1"] = VibeNode("1", "LoadImage")
     wf.nodes["2"] = VibeNode("2", "SaveImage")
     wf.connect("1.0", "2.images")
 
     with warnings.catch_warnings():
         warnings.simplefilter("ignore")
         result = emit_ui_json(wf, prior_store=None)
 
     # Sanity: both nodes emitted with engine-supplied (non-stub) positions.
     assert len(result["nodes"]) == 2
     for emitted in result["nodes"]:
         assert isinstance(emitted["pos"], list) and len(emitted["pos"]) == 2
diff --git a/tests/test_schema_validate.py b/tests/test_schema_validate.py
index 178e509f..7278ff33 100644
--- a/tests/test_schema_validate.py
+++ b/tests/test_schema_validate.py
@@ -1,75 +1,75 @@
 from __future__ import annotations
 
 import json
 from pathlib import Path
 
 import pytest
 
 from vibecomfy.ingest.normalize import from_api
 from vibecomfy.schema import InputSpec, LocalSchemaProvider, NodeSchema
 from vibecomfy.schema.validate import (
     SCHEMA_VALIDATION_SKIP_CLASSES,
     sanitize_api_against_schema,
     validate_api_against_schema,
 )
-from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
+from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
 
 
 class FakeSchemaProvider:
     def __init__(self, schemas: dict[str, NodeSchema]) -> None:
         self._schemas = schemas
 
     def get_schema(self, class_type: str) -> NodeSchema | None:
         return self._schemas.get(class_type)
 
     def schemas(self) -> dict[str, NodeSchema]:
         return self._schemas
 
 
 def _workflow(*nodes: VibeNode) -> VibeWorkflow:
     workflow = VibeWorkflow("schema-validate-test", WorkflowSource("schema-validate-test"))
     workflow.nodes = {node.id: node for node in nodes}
     return workflow
 
 
 def _schema(class_type: str, inputs: dict[str, InputSpec]) -> NodeSchema:
     return NodeSchema(class_type=class_type, pack=None, inputs=inputs, outputs=[])
 
 
 def _codes(workflow: VibeWorkflow, provider: FakeSchemaProvider) -> list[str]:
     return [issue.code for issue in workflow.validate(schema_provider=provider).issues]
 
 
 def test_missing_required_input_emits_error() -> None:
     provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", {"text": InputSpec("STRING", required=True)})})
     report = _workflow(VibeNode("1", "PromptNode")).validate(schema_provider=provider)
 
     assert not report.ok
     assert report.issues[0].code == "missing_required_input"
     assert report.issues[0].detail == {"node_id": "1", "class_type": "PromptNode", "input": "text"}
 
 
 def test_unknown_input_emits_error() -> None:
     provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", {"text": InputSpec("STRING")})})
     report = _workflow(VibeNode("1", "PromptNode", inputs={"extra": "value"})).validate(schema_provider=provider)
 
     assert not report.ok
     assert report.issues[0].code == "unknown_input"
     assert report.issues[0].detail == {"node_id": "1", "class_type": "PromptNode", "input": "extra"}
 
 
 def test_value_out_of_range_emits_error() -> None:
     provider = FakeSchemaProvider({"AceNode": _schema("AceNode", {"bpm": InputSpec("INT", min=10)})})
     report = _workflow(VibeNode("1", "AceNode", inputs={"bpm": 2})).validate(schema_provider=provider)
 
     assert not report.ok
     issue = report.issues[0]
     assert issue.code == "value_out_of_range"
     assert issue.detail["node_id"] == "1"
     assert issue.detail["class_type"] == "AceNode"
     assert issue.detail["input"] == "bpm"
     assert issue.detail["value"] == "2"
     assert issue.detail["min"] == 10
     assert issue.detail["max"] is None
 
 
@@ -123,269 +123,286 @@ def test_sanitize_api_strips_unknown_runtime_inputs_and_coerces_portable_choices
             "LoadImage": _schema("LoadImage", {"image": InputSpec("STRING")}),
         }
     )
     api = {
         "1": {
             "class_type": "WanVideoLoraSelect",
             "inputs": {
                 "lora": "WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                 "strength": 1.0,
                 "widget_0": "ui copy",
             },
         },
         "2": {"class_type": "LoadImage", "inputs": {"image": "start.png", "widget_0": "start.png"}},
     }
 
     sanitized = sanitize_api_against_schema(api, provider)
 
     assert sanitized["1"]["inputs"] == {
         "lora": "WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
         "strength": 1.0,
     }
     assert sanitized["2"]["inputs"] == {"image": "start.png"}
     assert api["1"]["inputs"]["widget_0"] == "ui copy"
 
 
 def test_sanitize_preserves_ltx_dynamic_image_slots() -> None:
     provider = FakeSchemaProvider(
         {
             "LTXVImgToVideoInplaceKJ": _schema(
                 "LTXVImgToVideoInplaceKJ",
                 {"num_images": InputSpec("INT"), "latent": InputSpec("LATENT"), "vae": InputSpec("VAE")},
             )
         }
     )
     api = {
         "210": {
             "class_type": "LTXVImgToVideoInplaceKJ",
             "inputs": {
                 "num_images": "2",
                 "num_images.image_1": ["1", 0],
                 "num_images.index_1": 0,
                 "num_images.strength_1": 1.0,
                 "num_images.image_2": ["2", 0],
                 "num_images.index_2": -1,
                 "num_images.strength_2": 1.0,
                 "widget_0": "ui alias",
             },
         }
     }
 
     sanitized = sanitize_api_against_schema(api, provider)
 
     assert "widget_0" not in sanitized["210"]["inputs"]
     assert sanitized["210"]["inputs"]["num_images.strength_1"] == 1.0
     assert sanitized["210"]["inputs"]["num_images.strength_2"] == 1.0
 
 
 def test_ltx_dynamic_image_slots_validate_required_fields() -> None:
     provider = FakeSchemaProvider(
         {
+            "ImageSource": _schema("ImageSource", {}),
             "LTXVImgToVideoInplaceKJ": _schema(
                 "LTXVImgToVideoInplaceKJ",
                 {"num_images": InputSpec("INT"), "latent": InputSpec("LATENT"), "vae": InputSpec("VAE")},
             )
         }
     )
     workflow = _workflow(
+        VibeNode("1", "ImageSource"),
+        VibeNode("2", "ImageSource"),
         VibeNode(
             "210",
             "LTXVImgToVideoInplaceKJ",
             inputs={
                 "num_images": "2",
-                "num_images.image_1": ["1", 0],
                 "num_images.index_1": 0,
                 "num_images.strength_1": 1.0,
-                "num_images.image_2": ["2", 0],
                 "num_images.index_2": -1,
             },
         )
     )
+    workflow.edges.extend(
+        [
+            VibeEdge("1", "0", "210", "num_images.image_1"),
+            VibeEdge("2", "0", "210", "num_images.image_2"),
+        ]
+    )
 
     report = workflow.validate(schema_provider=provider)
 
     assert not report.ok
     assert [(issue.code, issue.detail["input"]) for issue in report.issues] == [
         ("missing_dynamic_input", "num_images.strength_2")
     ]
 
 
 def test_sanitize_preserves_simple_calculator_autogrow_variables() -> None:
     provider = FakeSchemaProvider(
         {
             "SimpleCalculatorKJ": _schema(
                 "SimpleCalculatorKJ",
                 {"expression": InputSpec("STRING"), "variables": InputSpec("COMFY_AUTOGROW_V3")},
             )
         }
     )
     api = {
         "2077": {
             "class_type": "SimpleCalculatorKJ",
             "inputs": {
                 "expression": "a",
                 "variables": "a,b",
                 "a": ["2078", 0],
                 "b": ["2076", 0],
                 "widget_0": "ui alias",
             },
         }
     }
 
     sanitized = sanitize_api_against_schema(api, provider)
 
     assert sanitized["2077"]["inputs"] == {
         "expression": "a",
         "variables": "a,b",
         "a": ["2078", 0],
         "b": ["2076", 0],
     }
 
 
 def test_simple_calculator_autogrow_variables_validate_required_fields() -> None:
     provider = FakeSchemaProvider(
         {
+            "ValueSource": _schema("ValueSource", {}),
             "SimpleCalculatorKJ": _schema(
                 "SimpleCalculatorKJ",
                 {"expression": InputSpec("STRING"), "variables": InputSpec("COMFY_AUTOGROW_V3")},
             )
         }
     )
     workflow = _workflow(
-        VibeNode("2077", "SimpleCalculatorKJ", inputs={"expression": "a", "variables": "a,b", "a": ["2078", 0]})
+        VibeNode("2077", "SimpleCalculatorKJ", inputs={"expression": "a", "variables": "a,b"}),
+        VibeNode("2078", "ValueSource"),
     )
+    workflow.edges.append(VibeEdge("2078", "0", "2077", "a"))
 
     report = workflow.validate(schema_provider=provider)
 
     assert not report.ok
     assert [(issue.code, issue.detail["input"]) for issue in report.issues] == [("missing_dynamic_input", "b")]
 
 
 def test_sanitize_and_validate_preserve_linked_fixed_slot_inputs_not_in_local_schema() -> None:
     provider = FakeSchemaProvider(
         {
             "FixedSlotConsumer": _schema("FixedSlotConsumer", {"declared": InputSpec("STRING")}),
         }
     )
     api = {
         "2": {
             "class_type": "FixedSlotConsumer",
             "inputs": {
                 "declared": "ok",
                 "in_0": ["1", 0],
                 "extra_literal": "drop-me",
             },
         }
     }
 
     sanitized = sanitize_api_against_schema(api, provider)
     issues = validate_api_against_schema(sanitized, provider)
 
     assert sanitized["2"]["inputs"] == {
         "declared": "ok",
         "in_0": ["1", 0],
     }
     assert all(
         not (issue.code == "unknown_input" and issue.detail.get("input") == "in_0")
         for issue in issues
     )
 
 
 def test_invalid_link_shape_emits_error_for_dict_shaped_link() -> None:
     provider = FakeSchemaProvider({"Sink": _schema("Sink", {"latent": InputSpec("LATENT")})})
     report = _workflow(VibeNode("1", "Sink", inputs={"latent": {"link": 1, "node": "2"}})).validate(
         schema_provider=provider
     )
 
     assert not report.ok
     issue = report.issues[0]
     assert issue.code == "invalid_link_shape"
     assert issue.detail["node_id"] == "1"
     assert issue.detail["class_type"] == "Sink"
     assert issue.detail["input"] == "latent"
     assert issue.detail["value_repr"] == "{'link': 1, 'node': '2'}"
 
 
 def test_skip_list_suppresses_unknown_and_value_issues_only() -> None:
     SCHEMA_VALIDATION_SKIP_CLASSES["LyingNode"] = "test-only"
     try:
         provider = FakeSchemaProvider(
             {
                 "LyingNode": _schema(
                     "LyingNode",
                     {
                         "required": InputSpec("STRING", required=True),
                         "mode": InputSpec("STRING", choices=["a"]),
                     },
                 )
             }
         )
         workflow = _workflow(VibeNode("1", "LyingNode", inputs={"mode": "b", "extra": "value"}))
 
         assert _codes(workflow, provider) == ["missing_required_input"]
     finally:
         SCHEMA_VALIDATION_SKIP_CLASSES.pop("LyingNode", None)
 
 
 def test_range_enum_skipped_when_value_is_api_link() -> None:
-    provider = FakeSchemaProvider({"ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("INT", min=10, choices=[10])})})
-    report = _workflow(VibeNode("1", "ChoiceNode", inputs={"mode": ["3", 0]})).validate(schema_provider=provider)
+    provider = FakeSchemaProvider(
+        {
+            "ChoiceNode": _schema("ChoiceNode", {"mode": InputSpec("INT", min=10, choices=[10])}),
+            "ValueSource": _schema("ValueSource", {}),
+        }
+    )
+    workflow = _workflow(VibeNode("1", "ChoiceNode"), VibeNode("3", "ValueSource"))
+    workflow.edges.append(VibeEdge("3", "0", "1", "mode"))
+    report = workflow.validate(schema_provider=provider)
 
     assert report.ok
     assert report.issues == []
 
 
 # Schema regression-guard contract — see .megaplan/plans/brief-a-internal-testing-20260516-0048/ (T7).
 @pytest.mark.parametrize("snapshot", sorted(Path("tests/snapshots").glob("*.api.json")))
 def test_snapshot_api_workflows_validate_against_permissive_local_schema(snapshot: Path, tmp_path: Path) -> None:
     api = json.loads(snapshot.read_text(encoding="utf-8"))
     rows: dict[str, dict] = {}
     for node in api.values():
         if not isinstance(node, dict):
             continue
         class_type = str(node.get("class_type", "Unknown"))
         row = rows.setdefault(class_type, {"class_type": class_type, "inputs": {}})
         for name in (node.get("inputs") or {}):
             row["inputs"][name] = "*"
     index_path = tmp_path / "node_index.json"
     index_path.write_text(json.dumps(list(rows.values())), encoding="utf-8")
     provider = LocalSchemaProvider(index_path)
     workflow = from_api(api, workflow_id=snapshot.stem, schema_provider=provider)
 
     report = workflow.validate(schema_provider=provider)
 
     assert report.ok, [f"{issue.code}: {issue.message}" for issue in report.issues]
 
 # ── T16: advisory_validation_for_precedent tests ────────────────────────────
 
 
 def test_advisory_validation_for_precedent_returns_empty_for_none_route() -> None:
     """Returns empty list when route is None."""
     from vibecomfy.schema.validate import advisory_validation_for_precedent
     issues = [type("Issue", (), {"code": "missing_required_input", "message": "missing text"})()]
     result = advisory_validation_for_precedent(issues, route=None)
     assert result == []
 
 
 def test_advisory_validation_for_precedent_returns_empty_for_direct_edit() -> None:
     """Returns empty list when route is direct_edit (structural gate applies)."""
     from vibecomfy.schema.validate import advisory_validation_for_precedent
     issues = [type("Issue", (), {"code": "missing_required_input", "message": "missing text"})()]
     result = advisory_validation_for_precedent(issues, route="direct_edit")
     assert result == []
 
 
 def test_advisory_validation_for_precedent_returns_empty_for_inspect_only() -> None:
     """Returns empty list when route is inspect_only."""
     from vibecomfy.schema.validate import advisory_validation_for_precedent
     issues = [type("Issue", (), {"code": "unsatisfied_input", "message": "input missing"})()]
     result = advisory_validation_for_precedent(issues, route="inspect_only")
     assert result == []
 
 
 def test_advisory_validation_for_precedent_returns_empty_for_clarify() -> None:
     """Returns empty list when route is clarify."""
     from vibecomfy.schema.validate import advisory_validation_for_precedent
     issues = [type("Issue", (), {"code": "schema_gap", "message": "unknown node"})()]
     result = advisory_validation_for_precedent(issues, route="clarify")
     assert result == []
 
diff --git a/tests/test_ui_layout.py b/tests/test_ui_layout.py
index d0b1ed46..a73fb7bd 100644
--- a/tests/test_ui_layout.py
+++ b/tests/test_ui_layout.py
@@ -1492,127 +1492,128 @@ class TestEmitUiJsonGroupsIncludeSubgraphs:
     def test_emit_ui_json_groups_include_subgraphs(self):
         """When the workflow has subgraph definitions, emitted groups contain subgraph boxes."""
         from vibecomfy.workflow import VibeWorkflow, WorkflowSource
         from vibecomfy.porting.emit.ui import emit_ui_json
 
         wf = VibeWorkflow("subgraph_test", WorkflowSource("subgraph_test"))
         wf.add_node("TypeA", "1", uid="inner_1")
         wf.add_node("TypeB", "2", uid="inner_2")
         wf.connect("1.0", "2.x")
 
         # Attach subgraph definition whose inner nodes match the flat nodes above.
         wf.metadata = {
             "definitions": {
                 "subgraphs": [
                     {
                         "id": "sg-1",
                         "name": "MySubgraphBox",
                         "nodes": [
                             {"id": 10, "properties": {"vibecomfy_uid": "inner_1"}},
                             {"id": 11, "properties": {"vibecomfy_uid": "inner_2"}},
                         ],
                     }
                 ]
             }
         }
 
         result = emit_ui_json(wf)
 
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
 
-        caller_groups = [
+        ir_groups = [
             {"title": "CallerGroup", "bounding": [0, 0, 100, 100], "color": "#ffffff"},
             # Same title as engine group → should be suppressed from engine merge
             {"title": "EngineGroup", "bounding": [200, 200, 50, 50], "color": "#cccccc"},
         ]
 
-        result = emit_ui_json(wf, groups=caller_groups)
+        wf.groups = ir_groups
+        result = emit_ui_json(wf)
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
         wf.add_node("TypeA", "1", uid="ba")
         wf.add_node("TypeB", "2", uid="bb")
         wf.add_node("TypeC", "3", uid="bc")
         wf.connect("1.0", "2.x")
         wf.connect("2.0", "3.y")
 
         # Attach a subgraph so engine_groups is non-empty (exercises group merge path).
         wf.metadata = {
             "definitions": {
                 "subgraphs": [
                     {
                         "id": "sg-byte",
                         "name": "ByteGroup",
                         "nodes": [
                             {"id": 10, "properties": {"vibecomfy_uid": "ba"}},
                             {"id": 11, "properties": {"vibecomfy_uid": "bb"}},
                             {"id": 12, "properties": {"vibecomfy_uid": "bc"}},
                         ],
                     }
                 ]
             }
         }
 
diff --git a/tests/test_workflow_core.py b/tests/test_workflow_core.py
index 9c577ce7..4b4402a1 100644
--- a/tests/test_workflow_core.py
+++ b/tests/test_workflow_core.py
@@ -1,126 +1,243 @@
 from __future__ import annotations
 
 import builtins
 import importlib.util
 import json
 import sys
 import types
 import warnings
 from pathlib import Path
 
 import pytest
 
 from vibecomfy.ingest.index import index_workflows
 from vibecomfy.ingest.normalize import (
     from_api,
     from_envelope,
     from_ui,
     normalize_to_api,
 )
 from vibecomfy.registry.library import load_workflow_reference, workflow_from_id
 from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
 from vibecomfy.handles import Handle
 from vibecomfy.workflow import (
     VibeEdge,
     VibeInput,
     VibeNode,
     VibeOutput,
     VibeWorkflow,
     WorkflowCompileError,
     WorkflowRequirements,
     WorkflowSource,
 )
 import vibecomfy.workflow as workflow_module
 
 
 class _FakeSchemaProvider:
     def __init__(self, schemas: dict[str, NodeSchema]) -> None:
         self._schemas = schemas
 
     def get_schema(self, class_type: str) -> NodeSchema | None:
         return self._schemas.get(class_type)
 
 
 def test_api_workflow_converts_to_vibe_workflow() -> None:
     raw = {
         "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
         "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
         "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
     }
 
     workflow = from_api(raw, workflow_id="sample")
 
     assert workflow.id == "sample"
+    assert "positive" not in workflow.nodes["2"].inputs
+    assert "images" not in workflow.nodes["3"].inputs
+    assert workflow.edges == [
+        VibeEdge("1", "0", "2", "positive"),
+        VibeEdge("2", "0", "3", "images"),
+    ]
     assert workflow.validate().ok
     assert "prompt" in workflow.inputs
     workflow.set_prompt("new").set_seed(42).set_steps(8)
     api = workflow.compile()
     assert api["1"]["inputs"]["text"] == "new"
     assert api["2"]["inputs"]["seed"] == 42
     assert api["2"]["inputs"]["steps"] == 8
     assert api["2"]["inputs"]["positive"] == ["1", 0]
     assert workflow.export_to_json(format="api") == api
     with pytest.raises(ValueError, match="Unsupported workflow JSON export format"):
         workflow.export_to_json(format="ui")
 
 
+def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
+    workflow = VibeWorkflow("edge-only", WorkflowSource("edge-only"))
+    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
+    workflow.nodes["2"] = VibeNode(
+        "2",
+        "Sink",
+        inputs={
+            "literal_pair": [640, 480],
+            "label_pair": ["alpha", 0],
+            "boolean_pair": ["1", False],
+        },
+        uid="uid-2",
+    )
+    workflow.edges.append(VibeEdge("1", "0", "2", "image"))
+    before = workflow.copy()
+
+    expected = {
+        "1": {"class_type": "Source", "inputs": {}},
+        "2": {
+            "class_type": "Sink",
+            "inputs": {
+                "literal_pair": [640, 480],
+                "label_pair": ["alpha", 0],
+                "boolean_pair": ["1", False],
+                "image": ["1", 0],
+            },
+        },
+    }
+    assert workflow.compile("api") == expected
+    assert workflow == before
+
+    envelope = workflow.to_envelope()
+    assert envelope["nodes"]["2"]["inputs"] == {
+        "literal_pair": [640, 480],
+        "label_pair": ["alpha", 0],
+        "boolean_pair": ["1", False],
+    }
+    restored = from_envelope(envelope)
+    assert restored.compile("api") == expected
+
+
+def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
+    literals = {
+        "dimensions": [640, 480],
+        "label_and_index": ["alpha", 0],
+        "boolean_slot": ["1", False],
+    }
+
+    workflow = from_api({"1": {"class_type": "LiteralNode", "inputs": literals}})
+
+    assert workflow.nodes["1"].inputs == literals
+    assert workflow.edges == []
+    assert workflow.compile("api")["1"]["inputs"] == literals
+
+
+def test_raw_api_link_input_fails_validation_serialization_and_compile() -> None:
+    workflow = VibeWorkflow("raw-link", WorkflowSource("raw-link"))
+    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
+    workflow.nodes["2"] = VibeNode(
+        "2", "Sink", inputs={"image": ["1", 0]}, uid="uid-2"
+    )
+
+    report = workflow.validate()
+    assert not report.ok
+    issue = next(issue for issue in report.issues if issue.code == "embedded_api_link")
+    assert issue.detail["edge_collision"] == "none"
+
+    for operation in (workflow.to_envelope, lambda: workflow.compile("api")):
+        with pytest.raises(WorkflowCompileError) as exc_info:
+            operation()
+        assert exc_info.value.code == "embedded_api_link"
+        assert exc_info.value.detail["edge_collision"] == "none"
+
+
+@pytest.mark.parametrize(
+    ("edge", "expected_collision"),
+    [
+        (VibeEdge("1", "0", "2", "image"), "identical"),
+        (VibeEdge("3", "1", "2", "image"), "conflicting"),
+    ],
+)
+def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
+    edge: VibeEdge, expected_collision: str
+) -> None:
+    workflow = VibeWorkflow("collision", WorkflowSource("collision"))
+    workflow.nodes["1"] = VibeNode("1", "Source")
+    workflow.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
+    workflow.nodes["3"] = VibeNode("3", "OtherSource")
+    workflow.edges.append(edge)
+    before = workflow.copy()
+
+    with pytest.raises(WorkflowCompileError) as exc_info:
+        workflow.compile("api")
+
+    assert exc_info.value.code == "embedded_api_link"
+    assert exc_info.value.detail["edge_collision"] == expected_collision
+    assert workflow == before
+
+
+def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
+    workflow = VibeWorkflow("decode", WorkflowSource("decode"))
+    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
+    workflow.nodes["2"] = VibeNode("2", "Sink", uid="uid-2")
+    workflow.edges.append(VibeEdge("1", "0", "2", "image"))
+    envelope = workflow.to_envelope()
+    envelope["nodes"]["2"]["inputs"]["image"] = ["1", 0]
+
+    with pytest.raises(ValueError, match="embedded_api_link.*identical VibeEdge"):
+        from_envelope(envelope)
+
+
 def test_export_to_json_api_is_compile_api_for_ready_template() -> None:
     from vibecomfy import load_workflow_any
 
     workflow = load_workflow_any("image/z_image")
 
     assert workflow.export_to_json(format="api") == workflow.compile("api")
 
 
 def test_handle_is_generic_for_static_tools() -> None:
     assert Handle[str] is not None
 
 
 def test_node_builder_handles_include_schema_output_type() -> None:
     workflow = VibeWorkflow("typed", WorkflowSource("typed"))
 
     image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
     latent = workflow.node("EmptyLatentImage", width=8, height=8, batch_size=1)
 
     assert image.out(0).output_type == "IMAGE"
     assert latent.out(0).output_type == "LATENT"
 
 
 def test_strict_types_warns_for_known_incompatible_connections_only() -> None:
     workflow = VibeWorkflow("typed", WorkflowSource("typed"), strict_types=True)
     image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
     latent = workflow.node("EmptyLatentImage", width=8, height=8, batch_size=1)
     sampler = workflow.node("KSampler")
     unknown = workflow.node("UnknownNode")
 
     with pytest.warns(RuntimeWarning, match="IMAGE.*LATENT"):
         workflow.connect(image.out(0), f"{sampler.id}.latent_image")
 
     with warnings.catch_warnings(record=True) as captured:
         warnings.simplefilter("always")
         workflow.connect(latent.out(0), f"{sampler.id}.latent_image")
         workflow.connect(unknown.out(0), f"{sampler.id}.latent_image")
 
     assert captured == []
 
 
 def test_api_workflow_import_preserves_schema_output_names() -> None:
     provider = _FakeSchemaProvider(
         {
             "GuideNode": NodeSchema(
                 class_type="GuideNode",
                 pack=None,
                 inputs={},
                 outputs=[
                     OutputSpec("CONDITIONING", "positive"),
                     OutputSpec("CONDITIONING", "negative"),
                     OutputSpec("LATENT", "latent"),
                 ],
             ),
             "SinkNode": NodeSchema(
                 class_type="SinkNode",
                 pack=None,
                 inputs={"latent": InputSpec("LATENT")},
                 outputs=[],
             ),
         }
@@ -196,547 +313,564 @@ def test_set_input_rejects_unknown_name_without_unbound_metadata_write() -> None
     message = str(exc_info.value)
     assert "no registered public input or alias" in message
     assert "Available public inputs: 'filename_prefix'" in message
     assert "'prefix' -> 'filename_prefix'" in message
     assert "unbound_inputs" not in workflow.metadata
     assert workflow.nodes["1"].inputs["filename_prefix"] == "old"
 
 
 def test_set_input_rejects_unknown_alias() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
     workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])
 
     with pytest.raises(ValueError, match="Available aliases: 'prefix' -> 'filename_prefix'"):
         workflow.set_input("file_prefix", "new")
 
 
 def test_set_input_rejects_stale_missing_target_node() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
     workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])
     workflow.nodes.pop("1")
 
     with pytest.raises(ValueError) as exc_info:
         workflow.set_input("prefix", "new")
 
     message = str(exc_info.value)
     assert "target node '1' is missing" in message
     assert "Registered target: 1.filename_prefix" in message
     assert "unbound_inputs" not in workflow.metadata
 
 
 def test_set_input_rejects_stale_missing_target_field() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode(
         "1",
         "SaveImage",
         inputs={"filename_prefix": "old", "other": "old"},
         widgets={"preview": True},
     )
     workflow.register_input("filename_prefix", "1", "filename_prefix", "old")
     workflow.nodes["1"].inputs.pop("filename_prefix")
 
     with pytest.raises(ValueError) as exc_info:
         workflow.set_input("filename_prefix", "new")
 
     message = str(exc_info.value)
     assert "target field 'filename_prefix' is missing" in message
     assert "node '1' (SaveImage)" in message
     assert "Available fields on node '1': 'other', 'preview'" in message
     assert "unbound_inputs" not in workflow.metadata
 
 
 def test_set_input_rejects_stale_missing_target_field_after_node_replacement() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
     workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])
     workflow.nodes["1"] = VibeNode(
         "1",
         "PreviewImage",
-        inputs={"images": ["2", 0]},
+        inputs={"images": "placeholder"},
         widgets={"preview": False},
     )
 
     with pytest.raises(ValueError) as exc_info:
         workflow.set_input("prefix", "new")
 
     message = str(exc_info.value)
     assert "target field 'filename_prefix' is missing" in message
     assert "node '1' (PreviewImage)" in message
     assert "Available fields on node '1': 'images', 'preview'" in message
 
 
 def test_set_input_rejects_ambiguous_alias_with_matching_public_inputs() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "one"})
     workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "two"})
     workflow.register_input("first", "1", "filename_prefix", "one", aliases=["prefix"])
     workflow.inputs["second"] = VibeInput(
         name="second",
         node_id="2",
         field="filename_prefix",
         value="two",
         aliases=("prefix",),
     )
 
     with pytest.raises(ValueError) as exc_info:
         workflow.set_input("prefix", "new")
 
     message = str(exc_info.value)
     assert "alias 'prefix' is ambiguous" in message
     assert "first" in message
     assert "second" in message
 
 
 def test_set_input_updates_primary_name_when_aliases_exist() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
     workflow.register_input("filename_prefix", "1", "filename_prefix", "old", aliases=["prefix"])
 
     workflow.set_input("filename_prefix", "new")
 
     assert workflow.inputs["filename_prefix"].value == "new"
     assert workflow.nodes["1"].inputs["filename_prefix"] == "new"
     assert workflow.compile("api")["1"]["inputs"]["filename_prefix"] == "new"
 
 
 def test_register_input_rejects_bad_target() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "old"})
 
     with pytest.raises(ValueError, match="does not exist"):
         workflow.register_input("missing", "404", "filename_prefix", "old")
 
     with pytest.raises(ValueError, match="not found"):
         workflow.register_input("bad_field", "1", "missing", "old")
 
 
 def test_register_input_rejects_alias_collisions() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"filename_prefix": "one"})
     workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "two"})
     workflow.register_input("first", "1", "filename_prefix", "one", aliases=["prefix"])
 
     with pytest.raises(ValueError, match="existing alias"):
         workflow.register_input("second", "2", "filename_prefix", "two", aliases=["prefix"])
     with pytest.raises(ValueError, match="existing primary input"):
         workflow.register_input("second", "2", "filename_prefix", "two", aliases=["first"])
     with pytest.raises(ValueError, match="existing alias"):
         workflow.register_input("prefix", "2", "filename_prefix", "two")
 
 
 def test_workflow_copy_deep_copies_mutable_state_and_preserves_original() -> None:
     workflow = VibeWorkflow("original", WorkflowSource("original", provenance={"origin": ["unit"]}))
     workflow.nodes["1"] = VibeNode(
         "1",
         "SourceNode",
         inputs={"seed": {"value": 1}},
         widgets={"steps": [4]},
         metadata={"tags": ["source"]},
         uid="uid-1",
     )
     workflow.nodes["2"] = VibeNode(
         "2",
         "SaveImage",
-        inputs={"images": ["1", 0], "filename_prefix": "orig"},
+        inputs={"filename_prefix": "orig"},
         metadata={"tags": ["sink"]},
         uid="uid-2",
     )
     workflow.edges.append(VibeEdge("1", "0", "2", "images"))
     workflow.register_input(
         "seed",
         "1",
         "seed",
         value={"current": 1},
         default={"original": 1},
         aliases=["seed_alias"],
         range={"min": 0},
     )
     workflow.outputs.append(
         VibeOutput(
             node_id="2",
             output_type="IMAGE",
             name="preview",
             expected_cardinality={"count": 1},
         )
     )
     workflow.requirements = WorkflowRequirements(
         models=["base"],
         custom_nodes=["pack-a"],
         missing_models=["missing-a"],
         missing_nodes=["missing-node"],
         unsupported=["unsupported-a"],
     )
     workflow.metadata = {
         "flags": ["original"],
         "nested": {"keep": True},
         "id_map": {"seed_node": "1"},
     }
     workflow._set_id_map({"seed_node": "1"})
     workflow._manual_input_names.add("seed")
     workflow._uid_counter = 7
 
     cloned = workflow.copy()
 
     assert cloned is not workflow
     assert cloned.clone() is not cloned
     assert cloned.source is not workflow.source
     assert cloned.nodes["1"] is not workflow.nodes["1"]
     assert cloned.inputs["seed"] is not workflow.inputs["seed"]
     assert cloned.outputs[0] is not workflow.outputs[0]
     assert cloned.requirements is not workflow.requirements
     assert cloned.metadata is not workflow.metadata
     assert cloned.edges[0] is not workflow.edges[0]
     assert cloned.id_map() == {"seed_node": "1"}
     assert cloned._manual_input_names == {"seed"}
     assert cloned._uid_counter == 7
 
     cloned.nodes["1"].inputs["seed"]["value"] = 99
     cloned.nodes["1"].widgets["steps"].append(8)
     cloned.nodes["1"].metadata["tags"].append("clone")
     cloned.inputs["seed"].value["current"] = 99
     cloned.inputs["seed"].default["original"] = 99
     cloned.inputs["seed"].range["min"] = -1
     cloned.outputs[0].expected_cardinality["count"] = 2
     cloned.requirements.models.append("clone-model")
     cloned.metadata["flags"].append("clone")
     cloned.metadata["nested"]["keep"] = False
     cloned._id_map["seed_node"] = "2"
     cloned._manual_input_names.add("extra")
     cloned._uid_counter = 100
     cloned.source.provenance["origin"].append("clone")
     cloned.edges[0].from_node = "9"
 
     assert workflow.nodes["1"].inputs["seed"] == {"value": 1}
     assert workflow.nodes["1"].widgets["steps"] == [4]
     assert workflow.nodes["1"].metadata["tags"] == ["source"]
     assert workflow.inputs["seed"].value == {"current": 1}
     assert workflow.inputs["seed"].default == {"original": 1}
     assert workflow.inputs["seed"].range == {"min": 0}
     assert workflow.outputs[0].expected_cardinality == {"count": 1}
     assert workflow.requirements.models == ["base"]
     assert workflow.metadata["flags"] == ["original"]
     assert workflow.metadata["nested"] == {"keep": True}
     assert workflow.id_map() == {"seed_node": "1"}
     assert workflow._manual_input_names == {"seed"}
     assert workflow._uid_counter == 7
     assert workflow.source.provenance == {"origin": ["unit"]}
     assert workflow.edges[0].from_node == "1"
 
 
 def test_copy_is_derived_and_preserves_mode_and_groups_deeply() -> None:
     """P10: copy() is derived — mode/groups ride along without a hand-list edit,
     and the copy is deep (mutating the clone never touches the original)."""
     workflow = VibeWorkflow("derived", WorkflowSource("derived"))
     workflow.nodes["1"] = VibeNode(
         "1", "KSampler", inputs={"seed": 1}, uid="uid-1", mode=4
     )
     workflow.nodes["2"] = VibeNode(
-        "2", "SaveImage", inputs={"images": ["1", 0]}, uid="uid-2", mode=0
+        "2", "SaveImage", uid="uid-2", mode=0
     )
+    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
     workflow.groups = [
         {"title": "input-group", "nodes": [1, 2], "color": "#3f789e"},
     ]
 
     cloned = workflow.copy()
 
     assert cloned.nodes["1"].mode == 4
     assert cloned.nodes["2"].mode == 0
     assert cloned.groups == workflow.groups
 
     # Deep: mutating the clone's mode/groups leaves the original untouched.
     cloned.nodes["1"].mode = 0
     cloned.groups[0]["color"] = "#000000"
     cloned.groups.append({"title": "extra"})
     assert workflow.nodes["1"].mode == 4
     assert workflow.groups == [
         {"title": "input-group", "nodes": [1, 2], "color": "#3f789e"}
     ]
 
 
 def test_node_mode_and_groups_survive_envelope_round_trip() -> None:
     """P10: node.mode and workflow.groups are serialized by to_envelope and
     restored by from_envelope (dataclass walk — no hand-listed fields)."""
     from vibecomfy.ingest.normalize import from_envelope
 
     wf = VibeWorkflow("roundtrip", WorkflowSource("roundtrip"))
     wf.nodes["1"] = VibeNode(
         "1", "LoadImage", inputs={"image": "a.png"}, uid="uid-1", mode=4
     )
     wf.nodes["2"] = VibeNode(
-        "2", "PreviewImage", inputs={"images": ["1", 0]}, uid="uid-2", mode=2
+        "2", "PreviewImage", uid="uid-2", mode=2
     )
+    wf.edges.append(VibeEdge("1", "0", "2", "images"))
     wf.groups = [
         {"title": "g1", "nodes": [1, 2], "color": "#112233"},
         {"title": "g2", "bounding": [0, 0, 100, 100]},
     ]
 
     envelope = wf.to_envelope()
     assert envelope["groups"] == wf.groups
     assert envelope["nodes"]["1"]["mode"] == 4
     assert envelope["nodes"]["2"]["mode"] == 2
 
     restored = from_envelope(envelope)
     assert restored.nodes["1"].mode == 4
     assert restored.nodes["2"].mode == 2
     assert restored.groups == wf.groups
 
 
 def test_90a1d5_mode_distribution_and_compile_survive_p10() -> None:
     """P10 gate: the 90a1d5 envelope decodes 15 nodes with mode dist {4:9, 0:6};
     compile still emits 2 (bypass rewiring)."""
     from collections import Counter
 
     from vibecomfy.ingest.normalize import from_envelope
 
     envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
     envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
     wf = from_envelope(envelope)
 
     assert len(wf.nodes) == 15
     assert dict(Counter(node.mode for node in wf.nodes.values())) == {4: 9, 0: 6}
     assert len(wf.compile("api")) == 2
 
 
 def test_ui_workflow_normalizes_to_api() -> None:
     raw = {
         "nodes": [
             {"id": 1, "type": "CLIPTextEncode", "widgets_values": ["hello"], "inputs": []},
             {"id": 2, "type": "SaveImage", "inputs": [{"name": "images", "link": 1}]},
         ],
         "links": [[1, 1, 0, 2, 0, "IMAGE"]],
     }
 
     api = normalize_to_api(raw)
     assert api["1"]["class_type"] == "CLIPTextEncode"
     assert api["2"]["inputs"]["images"] == ["1", 0]
     via_named = from_ui(raw)
     assert set(via_named.nodes) == {"1", "2"}
     assert [node.class_type for node in via_named.nodes.values()] == [
         "CLIPTextEncode",
         "SaveImage",
     ]
+    assert "images" not in via_named.nodes["2"].inputs
+    assert via_named.edges == [VibeEdge("1", "0", "2", "images")]
 
 
 def test_empty_workflow_shapes_are_valid_authoring_inputs() -> None:
     assert normalize_to_api({}) == {}
     assert normalize_to_api({"nodes": [], "links": []}) == {}
     assert from_api({}).nodes == {}
     assert from_ui({"nodes": [], "links": []}).nodes == {}
 
 
 @pytest.mark.skipif(
     importlib.util.find_spec("comfy_execution") is None,
     reason="GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.",
 )
 def test_graphbuilder_backend_matches_api_backend() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SourceNode", inputs={"value": 1})
     workflow.nodes["2"] = VibeNode("2", "SinkNode", inputs={})
     workflow.connect("1.0", "2.input")
 
     assert workflow.compile("graphbuilder") == workflow.compile("api")
 
 
 def test_node_builder_named_outputs_use_registered_output_names() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     source = workflow.node("Source")
     source.node.metadata["output_names"] = ["positive", "negative", "latent"]
     sink = workflow.node("Sink", positive=source.out("positive"), latent=source.out("latent"))
 
     api = workflow.compile("api")
 
     assert api[sink.id]["inputs"]["positive"] == [source.id, 0]
     assert api[sink.id]["inputs"]["latent"] == [source.id, 2]
     assert source.out("latent").name == "latent"
 
 
 def test_explicit_inputs_override_imported_widget_values_at_compile_time() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode(
         "1",
         "LoadImage",
         inputs={"widget_0": "scratchpad.png", "image": "scratchpad.png"},
         widgets={"widget_0": "imported.png"},
     )
 
     api = workflow.compile("api")
 
     assert "widget_0" not in api["1"]["inputs"]
     assert api["1"]["inputs"]["image"] == "scratchpad.png"
 
 
 def test_compile_drops_video_preview_ui_payloads() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
+    workflow.nodes["2"] = VibeNode("2", "Source")
     workflow.nodes["1"] = VibeNode(
         "1",
         "VHS_VideoCombine",
         inputs={
-            "images": ["2", 0],
             "videopreview": {
                 "hidden": False,
                 "params": {"filename": "preview.mp4"},
                 "paused": False,
             },
         },
     )
+    workflow.edges.append(VibeEdge("2", "0", "1", "images"))
 
     api = workflow.compile("api")
 
     assert "videopreview" not in api["1"]["inputs"]
     assert api["1"]["inputs"]["images"] == ["2", 0]
 
 
 def test_compile_drops_null_prompt_inputs() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
+    workflow.nodes["2"] = VibeNode("2", "Source")
+    workflow.nodes["3"] = VibeNode("3", "Source")
     workflow.nodes["1"] = VibeNode(
         "1",
         "ImageConcatMulti",
         inputs={
-            "image_1": ["2", 0],
-            "image_2": ["3", 0],
             "widget_3": None,
         },
     )
+    workflow.edges.extend(
+        [
+            VibeEdge("2", "0", "1", "image_1"),
+            VibeEdge("3", "0", "1", "image_2"),
+        ]
+    )
 
     api = workflow.compile("api")
 
     assert "widget_3" not in api["1"]["inputs"]
     assert api["1"]["inputs"]["image_1"] == ["2", 0]
 
 
 def test_compile_drops_note_nodes_from_api_prompt() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor-only note"})
-    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"images": ["3", 0]})
+    workflow.nodes["2"] = VibeNode("2", "SaveImage")
+    workflow.nodes["3"] = VibeNode("3", "Source")
+    workflow.edges.append(VibeEdge("3", "0", "2", "images"))
 
     api = workflow.compile("api")
 
     assert "1" not in api
     assert api["2"]["class_type"] == "SaveImage"
 
 
 def test_compile_drops_markdown_note_nodes_from_api_prompt() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "editor-only note"})
-    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={"images": ["3", 0]})
+    workflow.nodes["2"] = VibeNode("2", "SaveImage")
+    workflow.nodes["3"] = VibeNode("3", "Source")
+    workflow.edges.append(VibeEdge("3", "0", "2", "images"))
 
     api = workflow.compile("api")
 
     assert "1" not in api
     assert api["2"]["class_type"] == "SaveImage"
 
 
 def test_validate_rejects_opaque_component_class_types() -> None:
     workflow = VibeWorkflow(id="test", source=WorkflowSource(id="test"))
     workflow.nodes["1"] = VibeNode(
         "1",
         "19e3f7e8-881c-4a61-a360-1c463734043a",
     )
 
     report = workflow.validate()
 
     assert report.ok
     assert [issue.code for issue in report.issues] == ["opaque_component_class_type"]
     assert [issue.severity for issue in report.issues] == ["warning"]
 
 
 def test_validate_rejects_kj_loader_for_ltx_audio_vae() -> None:
     workflow = VibeWorkflow("ltx-audio", WorkflowSource("ltx-audio"))
     workflow.nodes["175"] = VibeNode(
         "175",
         "VAELoaderKJ",
         inputs={"vae_name": "LTX23_audio_vae_bf16.safetensors"},
     )
 
     report = workflow.validate()
 
     assert not report.ok
     assert [issue.code for issue in report.issues] == ["ltx_audio_vae_wrong_loader"]
 
 
 def test_compile_rewrites_set_get_nodes_to_direct_links() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
     workflow.nodes["2"] = VibeNode(
         "2",
         "SetNode",
-        inputs={"IMAGE": ["1", 0], "widget_0": "reference_image"},
+        inputs={"widget_0": "reference_image"},
     )
     workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
     workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
+    workflow.connect("1.0", "2.IMAGE")
     workflow.connect("3.0", "4.images")
 
     api = workflow.compile("api")
 
     assert set(api) == {"1", "4"}
     assert api["4"]["inputs"]["images"] == ["1", 0]
 
 
 def test_compile_rewrites_edge_fed_set_get_nodes_to_direct_links() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
     workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "reference_image"})
     workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "reference_image"})
-    workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={"images": ["3", 0]})
+    workflow.nodes["4"] = VibeNode("4", "SaveImage")
     workflow.connect("1.0", "2.IMAGE")
+    workflow.connect("3.0", "4.images")
 
     api = workflow.compile("api")
 
     assert set(api) == {"1", "4"}
     assert api["4"]["inputs"]["images"] == ["1", 0]
 
 
 def test_compile_rewrites_set_get_source_through_bypassed_nodes() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
     bypassed = VibeNode("2", "ImageFilter", inputs={})
     bypassed.metadata["_ui"] = {"mode": 4}
     workflow.nodes["2"] = bypassed
     workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"})
     workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"})
     workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={})
     workflow.connect("1.0", "2.image")
     workflow.connect("2.0", "3.IMAGE")
     workflow.connect("4.0", "5.images")
 
     api = workflow.compile("api")
 
     assert set(api) == {"1", "5"}
     assert api["5"]["inputs"]["images"] == ["1", 0]
 
 
 @pytest.mark.parametrize(
     ("path", "target_node_id", "target_input", "expected_source"),
     [
         (
             Path("/tmp/runexx-ltx23/LTX-2.3_-_I2V_T2V_Basic_for_checkpoint_models.json"),
             "103",
             "model",
             ["337", 0],
         ),
         (
             Path("/tmp/runexx-ltx23/LTX-2.3_-_I2V_multi-subject-reference_Licon-MSR-lora.json"),
             "10",
             "model",
             ["59", 0],
         ),
     ],
 )
 def test_compile_original_runexx_ui_with_bypassed_set_get_sources(
     path: Path,
     target_node_id: str,
     target_input: str,
     expected_source: list[object],
 ) -> None:
     if not path.exists():
         pytest.skip(f"RuneXX regression fixture not present: {path}")
 
     from vibecomfy import load_workflow_any
 
     workflow = load_workflow_any(path)
 
     api = workflow.compile("api")
 
     assert api[target_node_id]["inputs"][target_input] == expected_source
 
@@ -820,262 +954,266 @@ def test_compile_raises_stable_code_for_helper_edge_cycles() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SetNode", inputs={"widget_0": "first"})
     workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "second"})
     workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "first"})
     workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
     workflow.connect("2.0", "1.IMAGE")
     workflow.connect("1.0", "2.IMAGE")
     workflow.connect("3.0", "4.images")
 
     with pytest.raises(WorkflowCompileError) as exc_info:
         workflow.compile("api")
 
     assert exc_info.value.code == "helper_edge_cycle"
     assert exc_info.value.detail["target_node_id"] == "4"
     assert exc_info.value.detail["target_input"] == "images"
 
 
 def test_compile_raises_stable_code_for_missing_edge_endpoint() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={})
     workflow.edges.append(VibeEdge("missing", "0", "1", "images"))
 
     with pytest.raises(WorkflowCompileError) as exc_info:
         workflow.compile("api")
 
     assert exc_info.value.code == "compiled_edge_missing_endpoint"
     assert exc_info.value.detail["source_node_id"] == "missing"
 
 
 def test_compile_ignores_stripped_intent_edge_when_target_has_literal_input() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "vibecomfy.loop")
     workflow.nodes["2"] = VibeNode("2", "CLIPTextEncode", inputs={"text": "literal fallback"})
     workflow.connect("1.0", "2.text")
 
     assert workflow.compile("api") == {
         "2": {
             "class_type": "CLIPTextEncode",
             "inputs": {"text": "literal fallback"},
         }
     }
 
 
 def test_compile_raises_for_stripped_intent_edge_without_target_literal_input() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "vibecomfy.loop")
     workflow.nodes["2"] = VibeNode("2", "CLIPTextEncode", inputs={})
     workflow.connect("1.0", "2.text")
 
     with pytest.raises(WorkflowCompileError) as exc_info:
         workflow.compile("api")
 
     assert exc_info.value.code == "compiled_edge_missing_endpoint"
     assert exc_info.value.detail["source_node_id"] == "1"
     assert exc_info.value.detail["target_node_id"] == "2"
     assert exc_info.value.detail["target_input"] == "text"
 
 
 def test_compile_keeps_non_intent_vibecomfy_nodes_in_api_output() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
-    workflow.nodes["1"] = VibeNode("1", "vibecomfy.exec", inputs={"in_0": ["9", 0], "source": "return 1"})
+    workflow.nodes["1"] = VibeNode("1", "vibecomfy.exec", inputs={"source": "return 1"})
     workflow.nodes["2"] = VibeNode("2", "vibecomfy.loop")
+    workflow.nodes["9"] = VibeNode("9", "Source")
+    workflow.edges.append(VibeEdge("9", "0", "1", "in_0"))
 
     compiled = workflow.compile("api")
 
     assert compiled["1"] == {
         "class_type": "vibecomfy.exec",
         "inputs": {"in_0": ["9", 0], "source": "return 1"},
     }
     assert "2" not in compiled
 
 
 def test_intent_classification_fallback_only_matches_known_vibecomfy_intents(
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     original_import = builtins.__import__
 
     def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
         if name == "vibecomfy.contracts.intent_nodes":
             raise ImportError("test fallback")
         return original_import(name, globals, locals, fromlist, level)
 
     monkeypatch.setattr(builtins, "__import__", fake_import)
 
     assert workflow_module._is_intent_node_class_type("vibecomfy.code") is True
     assert workflow_module._is_intent_node_class_type("vibecomfy.loop") is True
     assert workflow_module._is_intent_node_class_type("vibecomfy.exec") is False
 
 
 def test_validate_records_api_compile_failures_without_schema_provider() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={})
     workflow.edges.append(VibeEdge("missing", "0", "1", "images"))
 
     report = workflow.validate(schema_provider=None)
 
     compile_issues = [issue for issue in report.issues if issue.code == "api_compile_failed"]
     assert not report.ok
     assert len(compile_issues) == 1
     assert compile_issues[0].severity == "error"
     assert compile_issues[0].detail["compile_code"] == "compiled_edge_missing_endpoint"
     assert compile_issues[0].detail["source_node_id"] == "missing"
 
 
 def test_validate_keeps_schema_checks_conditional(monkeypatch: pytest.MonkeyPatch) -> None:
     from vibecomfy.schema import validate as schema_validate
 
     calls: list[str] = []
 
     def fake_validate_against_schema(workflow, schema_provider):
         calls.append("schema")
         return []
 
     def fake_validate_api_link_shapes(api, schema_provider):
         calls.append("links")
         return []
 
     monkeypatch.setattr(schema_validate, "validate_against_schema", fake_validate_against_schema)
     monkeypatch.setattr(schema_validate, "validate_api_link_shapes", fake_validate_api_link_shapes)
 
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
     workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={})
     workflow.connect("1.0", "2.images")
 
     assert workflow.validate(schema_provider=None).ok
     assert calls == []
 
     provider = _FakeSchemaProvider({})
     assert workflow.validate(schema_provider=provider).ok
     assert calls == ["schema", "links"]
 
 
 def test_runtime_views_strip_helper_nodes_without_changing_compile_rewrite() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "editor-only note"})
     workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "reference.png"})
     workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "reference_image"})
     workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "reference_image"})
-    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={"images": ["4", 0]})
+    workflow.nodes["5"] = VibeNode("5", "SaveImage")
     workflow.connect("2.0", "3.IMAGE")
+    workflow.connect("4.0", "5.images")
 
     api = workflow.compile("api")
     diagnostics = workflow.helper_diagnostics()
 
     assert sorted(workflow.runtime_nodes()) == ["2", "5"]
     assert workflow.runtime_class_types() == ["LoadImage", "SaveImage"]
     assert set(api) == {"2", "5"}
     assert api["5"]["inputs"]["images"] == ["2", 0]
     assert [(issue.code, issue.severity) for issue in diagnostics] == [
         ("ui_only_node_stripped", "info"),
         ("helper_broadcast_resolved", "info"),
         ("helper_broadcast_resolved", "info"),
     ]
 
 
 def test_compile_strips_only_ui_and_broadcast_helpers_not_conversion_helpers() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor note"})
     workflow.nodes["2"] = VibeNode("2", "MarkdownNote", inputs={"widget_0": "editor note"})
     workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "bus"})
     workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "bus"})
     workflow.nodes["5"] = VibeNode("5", "Reroute", inputs={})
     workflow.nodes["6"] = VibeNode("6", "PrimitiveNode", inputs={"value": 7})
     workflow.nodes["7"] = VibeNode("7", "PrimitiveInt", inputs={"value": 8})
 
     api = workflow.compile("api")
 
     assert set(api) == {"5", "6", "7"}
     assert api["5"]["class_type"] == "Reroute"
     assert api["6"]["class_type"] == "PrimitiveNode"
     assert api["7"]["class_type"] == "PrimitiveInt"
 
 
 def test_compile_resolves_supported_note_markdown_set_get_helper_chain() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
     workflow.nodes["2"] = VibeNode("2", "Note", inputs={"widget_0": "editor note"})
     workflow.nodes["3"] = VibeNode("3", "MarkdownNote", inputs={"widget_0": "## doc"})
     workflow.nodes["4"] = VibeNode("4", "SetNode", inputs={"widget_0": "bus"})
     workflow.nodes["5"] = VibeNode("5", "GetNode", inputs={"widget_0": "bus"})
     workflow.nodes["6"] = VibeNode("6", "SaveImage", inputs={})
     workflow.connect("1.0", "4.IMAGE")
     workflow.connect("5.0", "6.images")
 
     api = workflow.compile("api")
     report = workflow.validate(schema_provider=None)
 
     assert set(api) == {"1", "6"}
     assert api["6"]["inputs"]["images"] == ["1", 0]
     assert report.ok
     assert not [issue for issue in report.issues if issue.code == "api_compile_failed"]
 
 
 def test_compile_strips_standalone_helpers_silently() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "loose note"})
     workflow.nodes["2"] = VibeNode("2", "MarkdownNote", inputs={"widget_0": "## loose doc"})
     workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "loose_bus"})
     workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "loose_bus"})
     workflow.nodes["5"] = VibeNode("5", "LoadImage", inputs={"image": "reference.png"})
-    workflow.nodes["6"] = VibeNode("6", "SaveImage", inputs={"images": ["5", 0]})
+    workflow.nodes["6"] = VibeNode("6", "SaveImage")
+    workflow.connect("5.0", "6.images")
 
     api = workflow.compile("api")
     report = workflow.validate(schema_provider=None)
 
     assert set(api) == {"5", "6"}
     assert api["6"]["inputs"]["images"] == ["5", 0]
     assert report.ok
     assert not [issue for issue in report.issues if issue.code == "api_compile_failed"]
 
 
 def test_compile_raises_for_unrewirable_helper_path_through_ui_only_source() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "Note", inputs={"widget_0": "editor note"})
     workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "bus"})
     workflow.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "bus"})
     workflow.nodes["4"] = VibeNode("4", "SaveImage", inputs={})
     workflow.connect("1.0", "2.IMAGE")
     workflow.connect("3.0", "4.images")
 
     with pytest.raises(WorkflowCompileError) as exc_info:
         workflow.compile("api")
 
     assert exc_info.value.code == "helper_edge_unresolved"
     assert exc_info.value.detail["helper_node_id"] == "1"
     assert exc_info.value.detail["class_type"] == "Note"
     assert exc_info.value.detail["target_node_id"] == "4"
     assert exc_info.value.detail["target_input"] == "images"
 
 
 def test_compile_raises_when_traced_helper_source_missing_from_compiled_api() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "SetNode", inputs={"widget_0": "bus"})
     workflow.nodes["2"] = VibeNode("2", "GetNode", inputs={"widget_0": "bus"})
     workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={})
     workflow.edges.append(VibeEdge("missing", "0", "1", "IMAGE"))
     workflow.connect("2.0", "3.images")
 
     with pytest.raises(WorkflowCompileError) as exc_info:
         workflow.compile("api")
 
     assert exc_info.value.code == "compiled_edge_missing_endpoint"
     assert exc_info.value.detail["source_node_id"] == "missing"
     assert exc_info.value.detail["target_node_id"] == "3"
     assert exc_info.value.detail["target_input"] == "images"
 
 
 def test_compile_backend_parity_for_helper_edge_target_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
     graph_utils = types.ModuleType("comfy_execution.graph_utils")
 
     class FakeGraphBuilder:
         def __init__(self, prefix: str = "") -> None:
             self.prefix = prefix
             self.nodes: dict[str, dict[str, object]] = {}
 
         def node(self, class_type: str, id: str, **inputs: object) -> None:
             self.nodes[str(id)] = {"class_type": class_type, "inputs": inputs}
 
         def finalize(self) -> dict[str, dict[str, object]]:
             return self.nodes
 
@@ -1154,138 +1292,144 @@ def test_compile_rewrites_set_node_passthrough_outputs_to_direct_links() -> None
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "reference.png"})
     workflow.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "reference_image"})
     workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={})
     workflow.connect("1.0", "2.IMAGE")
     workflow.connect("2.0", "3.images")
 
     api = workflow.compile("api")
 
     assert set(api) == {"1", "3"}
     assert api["3"]["inputs"]["images"] == ["1", 0]
 
 
 def test_compile_adds_named_inputs_for_known_custom_node_widgets() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode(
         "1",
         "WanVideoImageToVideoEncode",
         inputs={
             "widget_0": 832,
             "widget_1": 480,
             "widget_2": 81,
             "widget_3": 0,
             "widget_4": 1,
             "widget_5": 1,
             "widget_6": True,
         },
     )
     workflow.nodes["2"] = VibeNode("2", "INTConstant", inputs={"widget_0": 6})
     workflow.nodes["3"] = VibeNode(
         "3",
         "WanVideoLoraSelect",
         inputs={
             "widget_0": "WanVideo\\Lightx2v\\example.safetensors",
             "widget_1": 1.0,
             "widget_2": False,
             "widget_3": False,
         },
     )
 
     api = workflow.compile("api")
 
     assert api["1"]["inputs"]["width"] == 832
     assert api["1"]["inputs"]["height"] == 480
     assert api["1"]["inputs"]["num_frames"] == 81
     assert api["1"]["inputs"]["noise_aug_strength"] == 0
     assert api["1"]["inputs"]["start_latent_strength"] == 1
     assert api["1"]["inputs"]["end_latent_strength"] == 1
     assert api["1"]["inputs"]["force_offload"] is True
     assert api["2"]["inputs"]["value"] == 6
     assert api["3"]["inputs"]["lora"] == "WanVideo\\Lightx2v\\example.safetensors"
     assert api["3"]["inputs"]["strength"] == 1.0
 
 
 def test_wan_video_sampler_aliases_skip_seed_control_widget() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode(
         "1",
         "WanVideoSampler",
         inputs={
-            "model": ["2", 0],
-            "image_embeds": ["3", 0],
             "widget_0": 6,
             "widget_1": 1,
             "widget_2": 8,
             "widget_3": 43,
             "widget_4": "fixed",
             "widget_5": True,
             "widget_6": "dpm++_sde",
             "widget_7": 0,
             "widget_8": 1,
             "widget_9": False,
             "widget_10": "comfy",
             "widget_11": 0,
             "widget_12": 10,
             "widget_13": "",
         },
     )
+    workflow.nodes["2"] = VibeNode("2", "ModelSource")
+    workflow.nodes["3"] = VibeNode("3", "ImageEmbedsSource")
+    workflow.edges.extend(
+        [
+            VibeEdge("2", "0", "1", "model"),
+            VibeEdge("3", "0", "1", "image_embeds"),
+        ]
+    )
 
     api = workflow.compile("api")
 
     assert api["1"]["inputs"]["seed"] == 43
     assert api["1"]["inputs"]["force_offload"] is True
     assert api["1"]["inputs"]["scheduler"] == "dpm++_sde"
     assert api["1"]["inputs"]["batched_cfg"] is False
     assert api["1"]["inputs"]["rope_function"] == "comfy"
     assert api["1"]["inputs"]["start_step"] == 0
     assert api["1"]["inputs"]["end_step"] == 10
     assert "add_noise_to_samples" not in api["1"]["inputs"]
 
 
 def test_compile_adds_named_inputs_for_wan_animate_helper_widgets() -> None:
     workflow = VibeWorkflow("test", WorkflowSource("test"))
     workflow.nodes["1"] = VibeNode(
         "1",
         "WanVideoAnimateEmbeds",
         inputs={
             "widget_0": 832,
             "widget_1": 480,
             "widget_2": 49,
             "widget_3": True,
             "widget_4": 77,
             "widget_5": "disabled",
             "widget_6": 1,
             "widget_7": 1,
             "widget_8": False,
         },
     )
     workflow.nodes["2"] = VibeNode(
         "2",
         "GrowMaskWithBlur",
         inputs={
             "widget_0": 10,
             "widget_1": 0,
             "widget_2": True,
             "widget_3": False,
             "widget_4": 0,
             "widget_5": 1,
             "widget_6": 1,
             "widget_7": False,
         },
     )
     workflow.nodes["3"] = VibeNode("3", "ImageConcatMulti", inputs={"widget_0": 4, "widget_1": "down", "widget_2": True, "widget_3": None})
     workflow.nodes["4"] = VibeNode("4", "BlockifyMask", inputs={"widget_0": 32})
     workflow.nodes["5"] = VibeNode("5", "DrawMaskOnImage", inputs={"widget_0": "0, 0, 0"})
 
     api = workflow.compile("api")
 
     assert api["1"]["inputs"]["width"] == 832
     assert api["1"]["inputs"]["height"] == 480
     assert api["1"]["inputs"]["num_frames"] == 49
     assert api["1"]["inputs"]["force_offload"] is True
     assert api["1"]["inputs"]["frame_window_size"] == 77
     assert api["1"]["inputs"]["colormatch"] == "disabled"
     assert api["1"]["inputs"]["face_strength"] == 1
     assert api["1"]["inputs"]["pose_strength"] == 1
     assert "unused_8" not in api["1"]["inputs"]
     assert api["2"]["inputs"]["expand"] == 10

exec
/bin/zsh -lc 'rg -n "embedded_api_link|raw_link|edge_only|collision|canonical.*round|literal.*list|mode_authority|group_member|source.*UID|uid.*group" tests/test_workflow_core.py tests/test_schema_validate.py tests/test_porting_ui_emitter.py tests/test_ui_layout.py tests/test_porting_normalize_ingest.py tests/test_foundation_utils.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 21ms:
tests/test_ui_layout.py:98:    def test_sizing_returns_canonicalized_ints_via_round(self):
tests/test_ui_layout.py:183:    """Parallel sampler nodes land in the same layer, no collisions."""
tests/test_ui_layout.py:185:    def test_layers_handle_parallel_samplers_no_collisions(self):
tests/test_ui_layout.py:357:        # Both coords should be canonicalized (2-decimal rounded floats).
tests/test_ui_layout.py:1153:    def test_engine_barycenter_no_sub_lane_collisions(self):
tests/test_workflow_core.py:73:def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
tests/test_workflow_core.py:114:def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
tests/test_workflow_core.py:137:    issue = next(issue for issue in report.issues if issue.code == "embedded_api_link")
tests/test_workflow_core.py:138:    assert issue.detail["edge_collision"] == "none"
tests/test_workflow_core.py:143:        assert exc_info.value.code == "embedded_api_link"
tests/test_workflow_core.py:144:        assert exc_info.value.detail["edge_collision"] == "none"
tests/test_workflow_core.py:148:    ("edge", "expected_collision"),
tests/test_workflow_core.py:154:def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
tests/test_workflow_core.py:155:    edge: VibeEdge, expected_collision: str
tests/test_workflow_core.py:157:    workflow = VibeWorkflow("collision", WorkflowSource("collision"))
tests/test_workflow_core.py:167:    assert exc_info.value.code == "embedded_api_link"
tests/test_workflow_core.py:168:    assert exc_info.value.detail["edge_collision"] == expected_collision
tests/test_workflow_core.py:172:def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
tests/test_workflow_core.py:180:    with pytest.raises(ValueError, match="embedded_api_link.*identical VibeEdge"):
tests/test_workflow_core.py:431:def test_register_input_rejects_alias_collisions() -> None:
tests/test_porting_ui_emitter.py:2218:def test_emit_and_compile_share_mode_authority_despite_conflicts(
tests/test_porting_ui_emitter.py:2245:def test_ir_group_members_remap_all_live_aliases_and_omit_stale_members() -> None:
tests/test_porting_ui_emitter.py:2287:    This is the canonical round-trip: capture mode 4 in metadata['_ui'],

exec
/bin/zsh -lc "nl -ba tests/test_workflow_core.py | sed -n '45,200p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '2180,2325p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '2325,2375p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
    45	    raw = {
    46	        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
    47	        "2": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 4, "positive": ["1", 0]}},
    48	        "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0]}},
    49	    }
    50	
    51	    workflow = from_api(raw, workflow_id="sample")
    52	
    53	    assert workflow.id == "sample"
    54	    assert "positive" not in workflow.nodes["2"].inputs
    55	    assert "images" not in workflow.nodes["3"].inputs
    56	    assert workflow.edges == [
    57	        VibeEdge("1", "0", "2", "positive"),
    58	        VibeEdge("2", "0", "3", "images"),
    59	    ]
    60	    assert workflow.validate().ok
    61	    assert "prompt" in workflow.inputs
    62	    workflow.set_prompt("new").set_seed(42).set_steps(8)
    63	    api = workflow.compile()
    64	    assert api["1"]["inputs"]["text"] == "new"
    65	    assert api["2"]["inputs"]["seed"] == 42
    66	    assert api["2"]["inputs"]["steps"] == 8
    67	    assert api["2"]["inputs"]["positive"] == ["1", 0]
    68	    assert workflow.export_to_json(format="api") == api
    69	    with pytest.raises(ValueError, match="Unsupported workflow JSON export format"):
    70	        workflow.export_to_json(format="ui")
    71	
    72	
    73	def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
    74	    workflow = VibeWorkflow("edge-only", WorkflowSource("edge-only"))
    75	    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
    76	    workflow.nodes["2"] = VibeNode(
    77	        "2",
    78	        "Sink",
    79	        inputs={
    80	            "literal_pair": [640, 480],
    81	            "label_pair": ["alpha", 0],
    82	            "boolean_pair": ["1", False],
    83	        },
    84	        uid="uid-2",
    85	    )
    86	    workflow.edges.append(VibeEdge("1", "0", "2", "image"))
    87	    before = workflow.copy()
    88	
    89	    expected = {
    90	        "1": {"class_type": "Source", "inputs": {}},
    91	        "2": {
    92	            "class_type": "Sink",
    93	            "inputs": {
    94	                "literal_pair": [640, 480],
    95	                "label_pair": ["alpha", 0],
    96	                "boolean_pair": ["1", False],
    97	                "image": ["1", 0],
    98	            },
    99	        },
   100	    }
   101	    assert workflow.compile("api") == expected
   102	    assert workflow == before
   103	
   104	    envelope = workflow.to_envelope()
   105	    assert envelope["nodes"]["2"]["inputs"] == {
   106	        "literal_pair": [640, 480],
   107	        "label_pair": ["alpha", 0],
   108	        "boolean_pair": ["1", False],
   109	    }
   110	    restored = from_envelope(envelope)
   111	    assert restored.compile("api") == expected
   112	
   113	
   114	def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
   115	    literals = {
   116	        "dimensions": [640, 480],
   117	        "label_and_index": ["alpha", 0],
   118	        "boolean_slot": ["1", False],
   119	    }
   120	
   121	    workflow = from_api({"1": {"class_type": "LiteralNode", "inputs": literals}})
   122	
   123	    assert workflow.nodes["1"].inputs == literals
   124	    assert workflow.edges == []
   125	    assert workflow.compile("api")["1"]["inputs"] == literals
   126	
   127	
   128	def test_raw_api_link_input_fails_validation_serialization_and_compile() -> None:
   129	    workflow = VibeWorkflow("raw-link", WorkflowSource("raw-link"))
   130	    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
   131	    workflow.nodes["2"] = VibeNode(
   132	        "2", "Sink", inputs={"image": ["1", 0]}, uid="uid-2"
   133	    )
   134	
   135	    report = workflow.validate()
   136	    assert not report.ok
   137	    issue = next(issue for issue in report.issues if issue.code == "embedded_api_link")
   138	    assert issue.detail["edge_collision"] == "none"
   139	
   140	    for operation in (workflow.to_envelope, lambda: workflow.compile("api")):
   141	        with pytest.raises(WorkflowCompileError) as exc_info:
   142	            operation()
   143	        assert exc_info.value.code == "embedded_api_link"
   144	        assert exc_info.value.detail["edge_collision"] == "none"
   145	
   146	
   147	@pytest.mark.parametrize(
   148	    ("edge", "expected_collision"),
   149	    [
   150	        (VibeEdge("1", "0", "2", "image"), "identical"),
   151	        (VibeEdge("3", "1", "2", "image"), "conflicting"),
   152	    ],
   153	)
   154	def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
   155	    edge: VibeEdge, expected_collision: str
   156	) -> None:
   157	    workflow = VibeWorkflow("collision", WorkflowSource("collision"))
   158	    workflow.nodes["1"] = VibeNode("1", "Source")
   159	    workflow.nodes["2"] = VibeNode("2", "Sink", inputs={"image": ["1", 0]})
   160	    workflow.nodes["3"] = VibeNode("3", "OtherSource")
   161	    workflow.edges.append(edge)
   162	    before = workflow.copy()
   163	
   164	    with pytest.raises(WorkflowCompileError) as exc_info:
   165	        workflow.compile("api")
   166	
   167	    assert exc_info.value.code == "embedded_api_link"
   168	    assert exc_info.value.detail["edge_collision"] == expected_collision
   169	    assert workflow == before
   170	
   171	
   172	def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
   173	    workflow = VibeWorkflow("decode", WorkflowSource("decode"))
   174	    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
   175	    workflow.nodes["2"] = VibeNode("2", "Sink", uid="uid-2")
   176	    workflow.edges.append(VibeEdge("1", "0", "2", "image"))
   177	    envelope = workflow.to_envelope()
   178	    envelope["nodes"]["2"]["inputs"]["image"] = ["1", 0]
   179	
   180	    with pytest.raises(ValueError, match="embedded_api_link.*identical VibeEdge"):
   181	        from_envelope(envelope)
   182	
   183	
   184	def test_export_to_json_api_is_compile_api_for_ready_template() -> None:
   185	    from vibecomfy import load_workflow_any
   186	
   187	    workflow = load_workflow_any("image/z_image")
   188	
   189	    assert workflow.export_to_json(format="api") == workflow.compile("api")
   190	
   191	
   192	def test_handle_is_generic_for_static_tools() -> None:
   193	    assert Handle[str] is not None
   194	
   195	
   196	def test_node_builder_handles_include_schema_output_type() -> None:
   197	    workflow = VibeWorkflow("typed", WorkflowSource("typed"))
   198	
   199	    image = workflow.node("EmptyImage", width=8, height=8, batch_size=1, color=0)
   200	    latent = workflow.node("EmptyLatentImage", width=8, height=8, batch_size=1)
  2180	    node = VibeNode("1", "Conflict")
  2181	    node.uid = "uid-conflict"
  2182	    # metadata['_ui'] says mode=4, color='#ui'
  2183	    node.metadata["_ui"] = {
  2184	        "pos": [10, 20],
  2185	        "size": [30, 40],
  2186	        "flags": {"collapsed": False},
  2187	        "color": "#ui",
  2188	        "bgcolor": "#uibg",
  2189	        "mode": 4,
  2190	        "properties": {"from": "ui"},
  2191	    }
  2192	    wf.nodes["1"] = node
  2193	
  2194	    # Sidecar says mode=2, color='#sc'
  2195	    sidecar_entry = {
  2196	        "pos": [50, 60],
  2197	        "size": [70, 80],
  2198	        "flags": {"collapsed": True},
  2199	        "color": "#sc",
  2200	        "bgcolor": "#scbg",
  2201	        "mode": 2,
  2202	        "properties": {"from": "sidecar"},
  2203	    }
  2204	    result = emit_ui_json(wf, layout={"uid-conflict": sidecar_entry})
  2205	    emitted = result["nodes"][0]
  2206	
  2207	    assert emitted["flags"] == {"collapsed": True}, "sidecar flags should win"
  2208	    assert emitted["color"] == "#sc", "sidecar color should win"
  2209	    assert emitted["bgcolor"] == "#scbg", "sidecar bgcolor should win"
  2210	    assert emitted["mode"] == 4, "IR/_ui mode authority should beat sidecar mode"
  2211	    assert emitted["properties"]["from"] == "sidecar", "sidecar properties should win"
  2212	
  2213	
  2214	@pytest.mark.parametrize(
  2215	    ("mode", "sidecar_mode", "metadata_mode", "compiled"),
  2216	    [(0, 2, 4, True), (2, 4, 0, False), (4, 0, 2, False)],
  2217	)
  2218	def test_emit_and_compile_share_mode_authority_despite_conflicts(
  2219	    mode: int,
  2220	    sidecar_mode: int,
  2221	    metadata_mode: int,
  2222	    compiled: bool,
  2223	) -> None:
  2224	    wf = _wf(f"mode-authority-{mode}")
  2225	    node = VibeNode(
  2226	        "1",
  2227	        "LoadImage",
  2228	        uid="uid-mode",
  2229	        mode=mode,
  2230	        metadata={"mode": metadata_mode},
  2231	    )
  2232	    wf.nodes["1"] = node
  2233	    layout_entry = {
  2234	        "pos": [0, 0],
  2235	        "size": [100, 100],
  2236	        "mode": sidecar_mode,
  2237	    }
  2238	
  2239	    emitted = emit_ui_json(wf, layout={"uid-mode": layout_entry})
  2240	
  2241	    assert emitted["nodes"][0]["mode"] == mode
  2242	    assert ("1" in wf.compile("api")) is compiled
  2243	
  2244	
  2245	def test_ir_group_members_remap_all_live_aliases_and_omit_stale_members() -> None:
  2246	    wf = _wf("group-members")
  2247	    wf.nodes["author_a"] = VibeNode(
  2248	        "41",
  2249	        "NodeA",
  2250	        uid="uid-a",
  2251	        metadata={"_ui": {"id": 141}},
  2252	    )
  2253	    wf.nodes["author_b"] = VibeNode(
  2254	        "author_b",
  2255	        "NodeB",
  2256	        uid="uid-b",
  2257	        metadata={"_ui": {"id": "142"}},
  2258	    )
  2259	    wf.groups = [
  2260	        {
  2261	            "title": "Aliases",
  2262	            "color": "#123456",
  2263	            "nodes": ["author_a", 41, "uid-a", 141, "uid-b", "142", "stale", 999],
  2264	        }
  2265	    ]
  2266	
  2267	    emitted = emit_ui_json(wf)
  2268	
  2269	    assert emitted["groups"] == [
  2270	        {
  2271	            "title": "Aliases",
  2272	            "color": "#123456",
  2273	            "nodes": [1, 1, 1, 1, 2, 2],
  2274	        }
  2275	    ]
  2276	    assert wf.groups[0]["nodes"][-2:] == ["stale", 999], "emission must not mutate IR"
  2277	
  2278	
  2279	# ---------------------------------------------------------------------------
  2280	# T10 — Mode emit for bypass/mute display (Step 8)
  2281	# ---------------------------------------------------------------------------
  2282	
  2283	
  2284	def test_node_captured_with_mode_4_reemits_mode_4() -> None:
  2285	    """T10: A node captured with mode 4 (bypassed) re-emits mode 4.
  2286	
  2287	    This is the canonical round-trip: capture mode 4 in metadata['_ui'],
  2288	    emit through emit_ui_json, and confirm the emitted node carries mode: 4.
  2289	    """
  2290	    wf = _wf("mode4-roundtrip")
  2291	    node = VibeNode("1", "LoadImage")
  2292	    node.uid = "uid-mode4"
  2293	    node.metadata["_ui"] = {
  2294	        "pos": [100.0, 200.0],
  2295	        "size": [300.0, 250.0],
  2296	        "flags": {},
  2297	        "color": "#abc",
  2298	        "bgcolor": None,
  2299	        "mode": 4,
  2300	        "properties": {},
  2301	    }
  2302	    wf.nodes["1"] = node
  2303	
  2304	    provider = _Provider({
  2305	        "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
  2306	    })
  2307	    result = emit_ui_json(wf, schema_provider=provider)
  2308	    emitted = result["nodes"][0]
  2309	
  2310	    assert emitted["mode"] == 4, f"bypassed node must re-emit mode 4, got {emitted['mode']}"
  2311	    # Verify the node is otherwise intact
  2312	    assert emitted["type"] == "LoadImage"
  2313	    assert emitted["id"] == 1
  2314	
  2315	
  2316	def test_node_captured_with_mode_2_reemits_mode_2() -> None:
  2317	    """T10: A node captured with mode 2 (muted) re-emits mode 2.
  2318	
  2319	    Captures mode 2 on the IR node and confirms a conflicting sidecar cannot
  2320	    override it during the full emit round-trip.
  2321	    """
  2322	    wf = _wf("mode2-roundtrip")
  2323	    node = VibeNode("1", "SaveImage")
  2324	    node.uid = "uid-mode2"
  2325	    node.mode = 2
  2325	    node.mode = 2
  2326	    wf.nodes["1"] = node
  2327	
  2328	    sidecar_entry = {
  2329	        "pos": [50.0, 60.0],
  2330	        "size": [400.0, 200.0],
  2331	        "flags": {},
  2332	        "color": None,
  2333	        "bgcolor": None,
  2334	        "mode": 4,
  2335	        "properties": {},
  2336	    }
  2337	
  2338	    provider = _Provider({
  2339	        "SaveImage": _schema("SaveImage", []),
  2340	    })
  2341	    result = emit_ui_json(wf, layout={"uid-mode2": sidecar_entry}, schema_provider=provider)
  2342	    emitted = result["nodes"][0]
  2343	
  2344	    assert emitted["mode"] == 2, f"muted node must re-emit mode 2, got {emitted['mode']}"
  2345	    assert emitted["type"] == "SaveImage"
  2346	
  2347	
  2348	def test_mode_emit_reflects_display_state() -> None:
  2349	    """T10: emit_ui_json re-emits the captured mode field in each node dict.
  2350	
  2351	    Creates three identical workflows whose only difference is the captured
  2352	    mode (0=normal, 2=muted, 4=bypassed) and verifies that emit_ui_json
  2353	    re-emits the correct mode value.  compile('api') behavior for mode!=0
  2354	    is tested separately in test_compile_* (T11).
  2355	    """
  2356	    def _build_wf(mode_val: int) -> VibeWorkflow:
  2357	        wf = _wf(f"mode-emit-{mode_val}")
  2358	        li = VibeNode("1", "LoadImage")
  2359	        li.uid = "uid-li"
  2360	        li.metadata["_ui"] = {
  2361	            "pos": [10.0, 20.0], "size": [300.0, 200.0],
  2362	            "flags": {}, "color": None, "bgcolor": None,
  2363	            "mode": mode_val, "properties": {},
  2364	        }
  2365	        wf.nodes["1"] = li
  2366	
  2367	        si = VibeNode("2", "SaveImage")
  2368	        si.uid = "uid-si"
  2369	        si.metadata["_ui"] = {
  2370	            "pos": [400.0, 20.0], "size": [300.0, 200.0],
  2371	            "flags": {}, "color": None, "bgcolor": None,
  2372	            "mode": mode_val, "properties": {},
  2373	        }
  2374	        wf.nodes["2"] = si
  2375	

exec
/bin/zsh -lc "git diff --unified=70 8a8300bb..0d2bb176 -- vibecomfy/patches/ltx_lowvram.py vibecomfy/runtime/eval/core.py && rg -n \"\\[["'^]]+,'"\\s*["'^]]+'"\\]\" vibecomfy/patches/ltx_lowvram.py vibecomfy/runtime/eval/core.py | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/patches/ltx_lowvram.py b/vibecomfy/patches/ltx_lowvram.py
index b3639df1..f25f9afa 100644
--- a/vibecomfy/patches/ltx_lowvram.py
+++ b/vibecomfy/patches/ltx_lowvram.py
@@ -1,127 +1,143 @@
 from __future__ import annotations
 
 from vibecomfy.patches.requirements import ensure_custom_nodes
 from vibecomfy.patches.types import Patch
-from vibecomfy.workflow import VibeWorkflow
+from vibecomfy.workflow import VibeEdge, VibeWorkflow
 
 
 FP8_CHECKPOINT = "ltx-2.3-22b-dev-fp8.safetensors"
 SOURCE_CHECKPOINT = "ltx-2.3-22b-dev.safetensors"
 AUDIO_LOADER_ID = "4010"
 CHECKPOINT_LOADER_ID = "3940"
 CLOWN_SAMPLER_CLASS = "ClownSampler_Beta"
 PORTABLE_SAMPLER = "euler_ancestral_cfg_pp"
 
 COMFY_CONFIGURATION = {
     "reserve_vram": 12,
     "cache_none": True,
     "fp8_e4m3fn_text_enc": True,
 }
 
 
 def applies_to(workflow: VibeWorkflow) -> bool:
     return _is_supported_rewrite_target(workflow)
 
 
 def apply(workflow: VibeWorkflow) -> VibeWorkflow:
     if not _is_supported_target(workflow):
         raise ValueError(
             "ltx_lowvram only supports LTX 2.3 workflows with node 3940 as a "
             "CheckpointLoaderSimple/LowVRAMCheckpointLoader and node 4010 as "
             "an LTXVAudioVAELoader."
         )
 
     image_to_video = workflow.metadata.get("capability") == "image_to_video"
     if "3159" in workflow.nodes:
         image_to_video = True
 
     _update_node(workflow, "3059", inputs={"width": 384, "height": 256}, widgets={"widget_0": 384, "widget_1": 256, "widget_2": 9})
     _update_node(workflow, "4979", widgets={"widget_0": 9})
     _update_node(workflow, "4978", widgets={"widget_0": 8})
     _update_node(workflow, "1241", widgets={"widget_0": 8})
     _update_node(workflow, "3980", widgets={"widget_0": 9, "widget_1": 8})
     _update_node(workflow, "4977", widgets={"widget_0": not image_to_video})
     _update_node(workflow, "2004", widgets={"widget_0": "egyptian_queen.png" if image_to_video else "example.png"})
     _update_node(workflow, "4981", widgets={"widget_1": 384})
     _replace_clown_samplers(workflow)
 
     if AUDIO_LOADER_ID in workflow.nodes:
         node = workflow.nodes[AUDIO_LOADER_ID]
         node.class_type = "LTXVAudioVAELoader"
         node.inputs = {"ckpt_name": FP8_CHECKPOINT}
         node.widgets = {}
     if CHECKPOINT_LOADER_ID in workflow.nodes:
         node = workflow.nodes[CHECKPOINT_LOADER_ID]
         node.class_type = "LowVRAMCheckpointLoader"
-        node.inputs = {"ckpt_name": FP8_CHECKPOINT, "dependencies": ["4960", 0]}
+        node.inputs = {"ckpt_name": FP8_CHECKPOINT}
         node.widgets = {}
+        workflow.edges = [
+            edge
+            for edge in workflow.edges
+            if not (
+                str(edge.to_node) == CHECKPOINT_LOADER_ID
+                and edge.to_input == "dependencies"
+            )
+        ]
+        workflow.edges.append(
+            VibeEdge(
+                from_node="4960",
+                from_output="0",
+                to_node=CHECKPOINT_LOADER_ID,
+                to_input="dependencies",
+            )
+        )
 
     _ensure_current_ltx_schema_defaults(workflow)
 
     workflow.metadata["smoke_resolution"] = "384x256x9_frames"
     workflow.metadata["comfy_configuration"] = dict(COMFY_CONFIGURATION)
     if ready_template := workflow.metadata.get("ready_template"):
         workflow.metadata["external_python_marker"] = f"external_python:{ready_template}"
 
     workflow.finalize_metadata()
     ensure_custom_nodes(workflow, ("ComfyUI-LTXVideo", "ComfyUI-KJNodes"))
     return workflow
 
 
 def rationale(workflow: VibeWorkflow) -> str:
     return (
         "LTXVideo nodes detected; reduces VRAM by using the fp8 checkpoint, "
         "low-VRAM model loader, portable sampler, and 384x256x9 smoke settings."
     )
 
 
 def _is_supported_target(workflow: VibeWorkflow) -> bool:
     return _is_supported_rewrite_target(workflow) or _is_supported_applied_target(workflow)
 
 
 def _is_supported_rewrite_target(workflow: VibeWorkflow) -> bool:
     audio_loader = workflow.nodes.get(AUDIO_LOADER_ID)
     checkpoint_loader = workflow.nodes.get(CHECKPOINT_LOADER_ID)
     if audio_loader is None or checkpoint_loader is None:
         return False
 
     return _is_supported_audio_loader(audio_loader) and _is_supported_checkpoint_loader(checkpoint_loader)
 
 
 def _is_supported_applied_target(workflow: VibeWorkflow) -> bool:
     audio_loader = workflow.nodes.get(AUDIO_LOADER_ID)
     checkpoint_loader = workflow.nodes.get(CHECKPOINT_LOADER_ID)
     if audio_loader is None or checkpoint_loader is None:
         return False
 
     return _is_supported_audio_loader(audio_loader) and _is_lowvram_checkpoint_loader(checkpoint_loader)
 
 
 def _is_supported_audio_loader(node) -> bool:
     if node.class_type != "LTXVAudioVAELoader":
         return False
     return _is_ltx_2_3_checkpoint(_node_checkpoint_name(node))
 
 
 def _is_supported_checkpoint_loader(node) -> bool:
     if node.class_type != "CheckpointLoaderSimple":
         return False
     return _is_ltx_2_3_checkpoint(_node_checkpoint_name(node))
 
 
 def _is_lowvram_checkpoint_loader(node) -> bool:
     if node.class_type != "LowVRAMCheckpointLoader":
         return False
     return _is_ltx_2_3_checkpoint(_node_checkpoint_name(node))
 
 
 def _node_checkpoint_name(node) -> object:
     return node.inputs.get("ckpt_name") or node.inputs.get("ckpt_name.string") or node.widgets.get("widget_0")
 
 
 def _is_ltx_2_3_checkpoint(value: object) -> bool:
     return isinstance(value, str) and value in {SOURCE_CHECKPOINT, FP8_CHECKPOINT}
 
 
 def _update_node(
     workflow: VibeWorkflow,
diff --git a/vibecomfy/runtime/eval/core.py b/vibecomfy/runtime/eval/core.py
index 01bc6303..21fd8bf5 100644
--- a/vibecomfy/runtime/eval/core.py
+++ b/vibecomfy/runtime/eval/core.py
@@ -181,214 +181,208 @@ def _find_upstream_vae(
             continue
         node = workflow.nodes[uid]
         if node.class_type in VAE_EMITTER_CLASSES:
             depth = depths.get(uid, 1 << 30)
             vae_candidates.append((depth, uid))
 
     vae_candidates.sort()
     return vae_candidates[0][1] if vae_candidates else None
 
 
 def _upstream_depths(
     workflow: VibeWorkflow,
     node_id: str,
 ) -> dict[str, int]:
     """BFS depth of each node from *node_id* (following edges in reverse)."""
     from collections import deque
 
     reverse: dict[str, set[str]] = {}
     for edge in workflow.edges:
         reverse.setdefault(edge.to_node, set()).add(edge.from_node)
 
     depths: dict[str, int] = {str(node_id): 0}
     queue: deque[str] = deque([str(node_id)])
     visited: set[str] = {str(node_id)}
 
     while queue:
         current = queue.popleft()
         current_depth = depths[current]
         for upstream_node in reverse.get(current, ()):
             if upstream_node not in visited:
                 visited.add(upstream_node)
                 depths[upstream_node] = current_depth + 1
                 queue.append(upstream_node)
 
     return depths
 
 
 # ---------------------------------------------------------------------------
 # Subgraph builders
 # ---------------------------------------------------------------------------
 
 
 def _build_preview_subgraph(
     workflow: VibeWorkflow,
     target_node_id: str,
     preview: Any,  # PreviewInjection
     selected_ids: set[str],
     *,
     backend: str = "api",
 ) -> dict[str, Any]:
     """Build a subgraph API dict with a preview node injected."""
     nid = str(target_node_id)
 
     # Build temporary subgraph workflow
     sub_nodes: dict[str, VibeNode] = {}
     for node_id in selected_ids:
         if node_id in workflow.nodes:
             sub_nodes[node_id] = workflow.nodes[node_id]
 
     # Filter edges to only those where both endpoints are in selected_ids
     sub_edges: list[VibeEdge] = []
     for edge in workflow.edges:
         if edge.from_node in selected_ids and edge.to_node in selected_ids:
             sub_edges.append(edge)
 
     # Add preview node
     preview_id = f"{nid}_preview"
     preview_node = VibeNode(
         id=preview_id,
         class_type=preview.class_type,
-        inputs=(
-            {preview.output_input_slot: [nid, 0]}
-            | (preview.extra_inputs or {})
-        ),
+        inputs=dict(preview.extra_inputs or {}),
     )
     sub_nodes[preview_id] = preview_node
     sub_edges.append(
         VibeEdge(
             from_node=nid,
             from_output="0",
             to_node=preview_id,
             to_input=preview.output_input_slot,
         )
     )
 
     # Build temporary VibeWorkflow and compile
     temp_wf = VibeWorkflow(
         id=f"{workflow.id}_eval_{nid}",
         source=workflow.source,
         nodes=sub_nodes,
         edges=sub_edges,
     )
     return temp_wf.compile(backend=backend)
 
 
 def _build_latent_preview_subgraph(
     workflow: VibeWorkflow,
     target_node_id: str,
     vae_node_id: str,
     selected_ids: set[str],
     *,
     backend: str = "api",
 ) -> dict[str, Any]:
     """Build a subgraph with VAEDecode → PreviewImage for LATENT output."""
     nid = str(target_node_id)
 
     all_ids = selected_ids.copy()
 
     # Build temporary subgraph workflow
     sub_nodes: dict[str, VibeNode] = {}
     for node_id in all_ids:
         if node_id in workflow.nodes:
             sub_nodes[node_id] = workflow.nodes[node_id]
 
     # Filter edges
     sub_edges: list[VibeEdge] = []
     for edge in workflow.edges:
         if edge.from_node in all_ids and edge.to_node in all_ids:
             sub_edges.append(edge)
 
     # Add VAEDecode node
     decode_id = f"{nid}_vaedecode"
     decode_node = VibeNode(
         id=decode_id,
         class_type="VAEDecode",
-        inputs={
-            "samples": [nid, 0],
-            "vae": [vae_node_id, 0],
-        },
+        inputs={},
     )
     sub_nodes[decode_id] = decode_node
     sub_edges.append(
         VibeEdge(from_node=nid, from_output="0", to_node=decode_id, to_input="samples")
     )
     sub_edges.append(
         VibeEdge(from_node=vae_node_id, from_output="0", to_node=decode_id, to_input="vae")
     )
 
     # Add PreviewImage node after VAEDecode
     preview_id = f"{nid}_preview"
     preview_node = VibeNode(
         id=preview_id,
         class_type="PreviewImage",
-        inputs={"images": [decode_id, 0]},
+        inputs={},
     )
     sub_nodes[preview_id] = preview_node
     sub_edges.append(
         VibeEdge(from_node=decode_id, from_output="0", to_node=preview_id, to_input="images")
     )
 
     # Build temporary VibeWorkflow and compile
     temp_wf = VibeWorkflow(
         id=f"{workflow.id}_eval_{nid}",
         source=workflow.source,
         nodes=sub_nodes,
         edges=sub_edges,
     )
     return temp_wf.compile(backend=backend)
 
 
 def _latent_metadata_fallback(
     workflow: VibeWorkflow,
     target_node_id: str,
     target_node: VibeNode,
 ) -> dict[str, Any]:
     """Return metadata dict for LATENT without discoverable upstream VAE."""
     return {
         "type": "LATENT",
         "shape": _infer_latent_shape(workflow, target_node_id, target_node),
         "node_id": str(target_node_id),
         "class_type": target_node.class_type,
         "previewable": False,
         "plan_only": True,
     }
 
 
 def _non_visualizable_metadata(
     target_node: VibeNode,
     node_id: str,
 ) -> dict[str, Any]:
     """Return metadata dict for non-visualizable outputs."""
     return {
         "type": target_node.class_type,
         "node_id": str(node_id),
         "class_type": target_node.class_type,
         "previewable": False,
     }
 
 
 # ---------------------------------------------------------------------------
 # Helpers
 # ---------------------------------------------------------------------------
 
 
 def _infer_latent_shape(
     workflow: VibeWorkflow,
     target_node_id: str,
     target_node: VibeNode,
 ) -> dict[str, Any] | None:
     """Try to infer latent shape from node inputs."""
     # Look for width/height inputs on the target node or its upstream
     shape: dict[str, Any] = {}
     for key in ("width", "height", "latent_width", "latent_height", "batch_size"):
         if key in target_node.inputs:
             shape[key] = target_node.inputs[key]
 
     if not shape:
         # Try upstream empty latent node
         from vibecomfy.analysis.graph import upstream
 
         for uid in upstream(workflow, target_node_id):
             if uid not in workflow.nodes:
                 continue
             node = workflow.nodes[uid]
vibecomfy/runtime/eval/core.py:33:) -> dict[str, Any]:
vibecomfy/runtime/eval/core.py:175:    vae_candidates: list[tuple[int, str]] = []
vibecomfy/runtime/eval/core.py:194:) -> dict[str, int]:
vibecomfy/runtime/eval/core.py:198:    reverse: dict[str, set[str]] = {}
vibecomfy/runtime/eval/core.py:202:    depths: dict[str, int] = {str(node_id): 0}
vibecomfy/runtime/eval/core.py:230:) -> dict[str, Any]:
vibecomfy/runtime/eval/core.py:235:    sub_nodes: dict[str, VibeNode] = {}
vibecomfy/runtime/eval/core.py:280:) -> dict[str, Any]:
vibecomfy/runtime/eval/core.py:287:    sub_nodes: dict[str, VibeNode] = {}
vibecomfy/runtime/eval/core.py:339:) -> dict[str, Any]:
vibecomfy/runtime/eval/core.py:354:) -> dict[str, Any]:
vibecomfy/runtime/eval/core.py:373:) -> dict[str, Any] | None:
vibecomfy/runtime/eval/core.py:376:    shape: dict[str, Any] = {}
vibecomfy/patches/ltx_lowvram.py:214:def _drop_inputs(workflow: VibeWorkflow, node_id: str, keys: tuple[str, ...]) -> None:
vibecomfy/patches/ltx_lowvram.py:231:__all__ = ["COMFY_CONFIGURATION", "applies_to", "apply", "patch", "rationale"]

exec
/bin/zsh -lc "git diff --unified=0 8a8300bb..0d2bb176 -- tests | rg '"'^'"\\+\\s*def test'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
+def test_canonical_api_link_requires_json_string_id_and_integer_slot() -> None:
+def test_furniture_groups_from_ir() -> None:
+def test_emit_and_compile_share_mode_authority_despite_conflicts(
+def test_ir_group_members_remap_all_live_aliases_and_omit_stale_members() -> None:
+def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
+def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
+def test_raw_api_link_input_fails_validation_serialization_and_compile() -> None:
+def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
+def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:

codex
The core task-6 paths do reject canonical embedded links during validation, envelope serialization/decoding, and both compile backends, with collision classification and no mutation. I’m now running the changed test files without pytest cache writes, while separately tracing every remaining package-owned `VibeNode.inputs` link-pair construction; that static search has found one suspicious subgraph path not covered by the supplied evidence.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_foundation_utils.py tests/test_layout_store.py tests/test_patches.py tests/test_porting_normalize_ingest.py tests/test_porting_synthetic_fixtures.py tests/test_porting_ui_emitter.py tests/test_schema_validate.py tests/test_ui_layout.py tests/test_workflow_core.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 3963ms:
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
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2']

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_from_api_normalizes_links_into_edges tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 4 in 10538ms:

no tests ran in 6.00s
ERROR: not found: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_workflow_core.py::test_from_api_normalizes_links_into_edges
(no match in any of [<Module test_workflow_core.py>])


exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_workflow_mutation_and_export_round_trip tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 4 in 8738ms:

no tests ran in 3.88s
ERROR: not found: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_workflow_core.py::test_workflow_mutation_and_export_round_trip
(no match in any of [<Module test_workflow_core.py>])


exec
/bin/zsh -lc "rg -n '"'^def test_'"' tests/test_workflow_core.py | head -12" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 110ms:
44:def test_api_workflow_converts_to_vibe_workflow() -> None:
73:def test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips() -> None:
114:def test_from_api_preserves_noncanonical_two_item_literal_lists() -> None:
128:def test_raw_api_link_input_fails_validation_serialization_and_compile() -> None:
154:def test_raw_api_link_edge_collisions_fail_explicitly_without_mutation(
172:def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
184:def test_export_to_json_api_is_compile_api_for_ready_template() -> None:
192:def test_handle_is_generic_for_static_tools() -> None:
196:def test_node_builder_handles_include_schema_output_type() -> None:
206:def test_strict_types_warns_for_known_incompatible_connections_only() -> None:
224:def test_api_workflow_import_preserves_schema_output_names() -> None:
260:def test_prompt_override_does_not_bind_conditioning_inputs() -> None:

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_foundation_utils.py::test_canonical_api_link_requires_json_string_id_and_integer_slot tests/test_workflow_core.py::test_api_workflow_converts_to_vibe_workflow tests/test_workflow_core.py::test_edge_only_connectivity_compiles_without_mutating_ir_and_round_trips tests/test_workflow_core.py::test_from_api_preserves_noncanonical_two_item_literal_lists tests/test_workflow_core.py::test_raw_api_link_input_fails_validation_serialization_and_compile tests/test_workflow_core.py::test_raw_api_link_edge_collisions_fail_explicitly_without_mutation tests/test_workflow_core.py::test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 19191ms:
.OMP: Warning #179: Function Can't set size of /tmp file failed:
...........
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts[0-2-4-True]
tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts[2-4-0-False]
tests/test_porting_ui_emitter.py::test_emit_and_compile_share_mode_authority_despite_conflicts[4-0-2-False]
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:2239: UserWarning: emit_ui_json: schema-less node 1(LoadImage); emitting best-effort slots. Pass strict=True to hard-fail.
    emitted = emit_ui_json(wf, layout={"uid-mode": layout_entry})

tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:2267: UserWarning: emit_ui_json: schema-less node author_a(NodeA); emitting best-effort slots. Pass strict=True to hard-fail.
    emitted = emit_ui_json(wf)

tests/test_porting_ui_emitter.py::test_ir_group_members_remap_all_live_aliases_and_omit_stale_members
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_ui_emitter.py:2267: UserWarning: emit_ui_json: schema-less node author_b(NodeB); emitting best-effort slots. Pass strict=True to hard-fail.
    emitted = emit_ui_json(wf)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 6 warnings in 8.08s

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/emit_subgraph.py | sed -n '220,305p' && rg -n \"_build_subgraph_def\\(\" tests vibecomfy --glob '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 38ms:
tests/test_porting_edit_session.py:1073:        subgraph = _build_subgraph_def(raw_subgraph, slug="scoped", source_path=None)

exec
/bin/zsh -lc "nl -ba tests/test_porting_edit_session.py | sed -n '1010,1105p' && rg -n '\"-10\"|target_id.*-10|origin_id.*-10' tests --glob '*.py' | head -100" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
  1010	
  1011	        wf = self._tiny_uid_workflow()
  1012	        diagnostics = []
  1013	        source = emit_scratchpad_python(
  1014	            wf,
  1015	            diagnostics=diagnostics,
  1016	            variable_name_locks={
  1017	                "uid-loader": "same_name",
  1018	                "uid-sampler": "same_name",
  1019	            },
  1020	            prune_dead_branches=False,
  1021	        )
  1022	
  1023	        assert "same_name = _node" not in source
  1024	        assert any(diag.code == READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION for diag in diagnostics)
  1025	
  1026	    def test_strict_missing_locked_uid_reports_later_render_diagnostic(self) -> None:
  1027	        from vibecomfy.porting.emitter import (
  1028	            READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
  1029	            emit_scratchpad_python,
  1030	        )
  1031	
  1032	        diagnostics = []
  1033	        emit_scratchpad_python(
  1034	            self._tiny_uid_workflow(),
  1035	            diagnostics=diagnostics,
  1036	            variable_name_locks={"missing-uid": "old_name"},
  1037	            strict_variable_name_locks=True,
  1038	            prune_dead_branches=False,
  1039	        )
  1040	
  1041	        missing = [diag for diag in diagnostics if diag.code == READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING]
  1042	        assert len(missing) == 1
  1043	        assert missing[0].severity == "error"
  1044	        assert missing[0].detail["uid"] == "missing-uid"
  1045	
  1046	    def test_subgraph_internal_locked_names_use_scope_qualified_uid(self) -> None:
  1047	        from vibecomfy.porting.emitter import _build_subgraph_def, _emit_subgraph_functions
  1048	        from vibecomfy.identity.uid import make_uid
  1049	
  1050	        raw_subgraph = {
  1051	            "id": "sg-alpha",
  1052	            "name": "Scoped",
  1053	            "nodes": [
  1054	                {
  1055	                    "id": 1,
  1056	                    "type": "TotallyCustomNode",
  1057	                    "properties": {"vibecomfy_uid": "inner-loader"},
  1058	                    "widgets_values": [],
  1059	                },
  1060	            ],
  1061	            "links": [
  1062	                {
  1063	                    "id": 1,
  1064	                    "origin_id": 1,
  1065	                    "origin_slot": 0,
  1066	                    "target_id": -20,
  1067	                    "target_slot": 0,
  1068	                }
  1069	            ],
  1070	            "inputs": [],
  1071	            "outputs": [{"name": "MODEL", "type": "MODEL"}],
  1072	        }
  1073	        subgraph = _build_subgraph_def(raw_subgraph, slug="scoped", source_path=None)
  1074	        diagnostics = []
  1075	        source = "\n".join(
  1076	            _emit_subgraph_functions(
  1077	                {"subgraph_definitions": {"sg-alpha": subgraph}},
  1078	                diagnostics=diagnostics,
  1079	                constant_map={},
  1080	                variable_name_locks={make_uid("sg-alpha", "inner-loader"): "locked_inner_loader"},
  1081	            )
  1082	        )
  1083	
  1084	        assert "locked_inner_loader = raw_call('TotallyCustomNode'" in source
  1085	        assert not [diag for diag in diagnostics if diag.code.startswith("locked_variable_")]
  1086	
  1087	
  1088	# =====================================================================
  1089	# M1 T6 — emit_available_node_signatures and format_signature_rows
  1090	# =====================================================================
  1091	
  1092	
  1093	class TestAvailableNodeSignatures:
  1094	    """Tests for emit_available_node_signatures(...) and format_signature_rows(...)."""
  1095	
  1096	    @staticmethod
  1097	    def _fake_provider(
  1098	        schemas_dict: dict[str, Any] | None = None,
  1099	    ) -> Any:
  1100	        """Build a fake schema provider with .schemas() and .get_schema()."""
  1101	        from vibecomfy.schema import NodeSchema
  1102	
  1103	        if schemas_dict is None:
  1104	            schemas_dict = {}
  1105	
tests/test_subgraph_emission_contract.py:49:                        {"id": 1, "origin_id": -10, "origin_slot": 0, "target_id": 10, "target_slot": 0, "type": "BOOLEAN"},
tests/fixtures/node_resolution/ideogram4_t2i.expected_emit.py:12:    definitions={'subgraphs': [{'id': '83e6e004-48ea-408e-9024-eb49c3d7dc14', 'version': 1, 'state': {'lastGroupId': 9, 'lastNodeId': 176, 'lastLinkId': 252, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': 'Text to Image (Ideogram v4)', 'inputNode': {'id': -10, 'bounding': [3490, 920, 154.921875, 228]}, 'outputNode': {'id': -20, 'bounding': [6850, 936, 128, 68]}, 'inputs': [{'id': '4bc742d1-7b4b-452c-90d9-0d76ebcdae76', 'name': 'text', 'type': 'STRING', 'linkIds': [152], 'label': 'prompt', 'pos': [3620.921875, 944]}, {'id': '8d4038eb-73c7-45e9-bba1-f068f55e8d32', 'name': 'value', 'type': 'INT', 'linkIds': [153], 'label': 'width', 'pos': [3620.921875, 964]}, {'id': '281550e6-6acf-4cbe-aec1-9eb803b4dec1', 'name': 'value_1', 'type': 'INT', 'linkIds': [154], 'label': 'height', 'pos': [3620.921875, 984]}, {'id': 'fae56884-2f1a-470b-a25f-40e7a87ef69d', 'name': 'noise_seed', 'type': 'INT', 'linkIds': [155], 'pos': [3620.921875, 1004]}, {'id': '3497309c-a7d7-4e28-9330-142c15881632', 'name': 'unet_name', 'type': 'COMBO', 'linkIds': [156], 'pos': [3620.921875, 1024]}, {'id': 'e87126db-7147-465e-b129-370ed2c6cc22', 'name': 'clip_name', 'type': 'COMBO', 'linkIds': [157], 'pos': [3620.921875, 1044]}, {'id': 'a1e6c080-b11b-4d5c-a3a8-fcf4df654cf7', 'name': 'vae_name', 'type': 'COMBO', 'linkIds': [158], 'pos': [3620.921875, 1064]}, {'id': 'b0d16516-95de-44d9-bea8-3cd2e7c78e9a', 'name': 'unet_name_1', 'type': 'COMBO', 'linkIds': [216], 'label': 'unconditional_unet', 'pos': [3620.921875, 1084]}, {'id': '249fd825-e6b3-489d-a341-6d8050500f5e', 'name': 'choice', 'type': 'COMBO', 'linkIds': [219], 'label': 'mode', 'pos': [3620.921875, 1104]}], 'outputs': [{'id': 'b81e4f60-e543-4f02-875b-b0f1bdc274f2', 'name': 'IMAGE', 'type': 'IMAGE', 'linkIds': [25], 'localized_name': 'IMAGE', 'pos': [6874, 960]}], 'widgets': [], 'nodes': [{'id': 9, 'type': 'VAELoader', 'pos': [4730, 1220], 'size': [470, 110], 'flags': {}, 'order': 1, 'mode': 0, 'inputs': [{'localized_name': 'vae_name', 'name': 'vae_name', 'type': 'COMBO', 'widget': {'name': 'vae_name'}, 'link': 158}], 'outputs': [{'localized_name': 'VAE', 'name': 'VAE', 'type': 'VAE', 'links': [17]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'VAELoader', 'models': [{'name': 'flux2-vae.safetensors', 'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors', 'directory': 'vae'}]}, 'widgets_values': ['flux2-vae.safetensors']}, {'id': 10, 'type': 'ConditioningZeroOut', 'pos': [5450, 960], 'size': [250, 80], 'flags': {'collapsed': False}, 'order': 2, 'mode': 0, 'inputs': [{'localized_name': 'conditioning', 'name': 'conditioning', 'type': 'CONDITIONING', 'link': 8}], 'outputs': [{'localized_name': 'CONDITIONING', 'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [214]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.9.1', 'Node name for S&R': 'ConditioningZeroOut'}, 'widgets_values': []}, {'id': 11, 'type': 'EmptyFlux2LatentImage', 'pos': [5330, 1180], 'size': [270, 170], 'flags': {}, 'order': 3, 'mode': 0, 'inputs': [{'localized_name': 'width', 'name': 'width', 'type': 'INT', 'widget': {'name': 'width'}, 'link': 33}, {'localized_name': 'height', 'name': 'height', 'type': 'INT', 'widget': {'name': 'height'}, 'link': 36}], 'outputs': [{'localized_name': 'LATENT', 'name': 'LATENT', 'type': 'LATENT', 'links': [15]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'EmptyFlux2LatentImage'}, 'widgets_values': [1024, 1024, 1]}, {'id': 12, 'type': 'SamplerCustomAdvanced', 'pos': [6160, 500], 'size': [290, 170], 'flags': {}, 'order': 4, 'mode': 0, 'inputs': [{'localized_name': 'noise', 'name': 'noise', 'type': 'NOISE', 'link': 11}, {'localized_name': 'guider', 'name': 'guider', 'type': 'GUIDER', 'link': 215}, {'localized_name': 'sampler', 'name': 'sampler', 'type': 'SAMPLER', 'link': 13}, {'localized_name': 'sigmas', 'name': 'sigmas', 'type': 'SIGMAS', 'link': 14}, {'localized_name': 'latent_image', 'name': 'latent_image', 'type': 'LATENT', 'link': 15}], 'outputs': [{'localized_name': 'output', 'name': 'output', 'type': 'LATENT', 'links': [16]}, {'localized_name': 'denoised_output', 'name': 'denoised_output', 'type': 'LATENT', 'links': []}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'SamplerCustomAdvanced'}, 'widgets_values': []}, {'id': 13, 'type': 'VAEDecode', 'pos': [6560, 500], 'size': [230, 100], 'flags': {}, 'order': 5, 'mode': 0, 'inputs': [{'localized_name': 'samples', 'name': 'samples', 'type': 'LATENT', 'link': 16}, {'localized_name': 'vae', 'name': 'vae', 'type': 'VAE', 'link': 17}], 'outputs': [{'localized_name': 'IMAGE', 'name': 'IMAGE', 'type': 'IMAGE', 'slot_index': 0, 'links': [25]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'VAEDecode'}, 'widgets_values': []}, {'id': 16, 'type': 'KSamplerSelect', 'pos': [5790, 1100], 'size': [270, 110], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [{'localized_name': 'SAMPLER', 'name': 'SAMPLER', 'type': 'SAMPLER', 'links': [13]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'KSamplerSelect'}, 'widgets_values': ['euler']}, {'id': 17, 'type': 'Ideogram4Scheduler', 'pos': [5790, 1260], 'size': [270, 240], 'flags': {}, 'order': 7, 'mode': 0, 'inputs': [{'localized_name': 'steps', 'name': 'steps', 'type': 'INT', 'widget': {'name': 'steps'}, 'link': 207}, {'localized_name': 'width', 'name': 'width', 'type': 'INT', 'widget': {'name': 'width'}, 'link': 34}, {'localized_name': 'height', 'name': 'height', 'type': 'INT', 'widget': {'name': 'height'}, 'link': 37}, {'localized_name': 'mu', 'name': 'mu', 'type': 'FLOAT', 'widget': {'name': 'mu'}, 'link': 208}, {'localized_name': 'std', 'name': 'std', 'type': 'FLOAT', 'widget': {'name': 'std'}, 'link': 209}], 'outputs': [{'localized_name': 'SIGMAS', 'name': 'SIGMAS', 'type': 'SIGMAS', 'links': [14]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'Ideogram4Scheduler'}, 'widgets_values': [20, 1024, 1024, 0.5, 1.75]}, {'id': 18, 'type': 'RandomNoise', 'pos': [5780, 490], 'size': [270, 110], 'flags': {}, 'order': 8, 'mode': 0, 'inputs': [{'localized_name': 'noise_seed', 'name': 'noise_seed', 'type': 'INT', 'widget': {'name': 'noise_seed'}, 'link': 155}], 'outputs': [{'localized_name': 'NOISE', 'name': 'NOISE', 'type': 'NOISE', 'links': [11]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'RandomNoise'}, 'widgets_values': [885894517601261, 'randomize']}, {'id': 23, 'type': 'UNETLoader', 'pos': [4720, 520], 'size': [470, 170], 'flags': {}, 'order': 9, 'mode': 0, 'showAdvanced': True, 'inputs': [{'localized_name': 'unet_name', 'name': 'unet_name', 'type': 'COMBO', 'widget': {'name': 'unet_name'}, 'link': 156}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [222]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'UNETLoader', 'models': [{'name': 'ideogram4_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/diffusion_models/ideogram4_fp8_scaled.safetensors', 'directory': 'diffusion_models'}]}, 'widgets_values': ['ideogram4_fp8_scaled.safetensors', 'default']}, {'id': 24, 'type': 'CLIPTextEncode', 'pos': [5270, 500], 'size': [430, 420], 'flags': {}, 'order': 10, 'mode': 0, 'inputs': [{'localized_name': 'clip', 'name': 'clip', 'type': 'CLIP', 'link': 24}, {'localized_name': 'text', 'name': 'text', 'type': 'STRING', 'widget': {'name': 'text'}, 'link': 152}], 'outputs': [{'localized_name': 'CONDITIONING', 'name': 'CONDITIONING', 'type': 'CONDITIONING', 'slot_index': 0, 'links': [8, 213]}], 'title': 'CLIP Text Encode (Positive Prompt)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'CLIPTextEncode'}, 'widgets_values': ['{\n    "high_level_description": "A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling \'COMFY\'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying an effortless, cozy vibe.",\n    "style_description": {\n        "aesthetics": "Retro magazine cutout style, mixed-media digital collage, high-contrast streetwear graphic, featuring rough ripped paper edges and distressed grunge textures.",\n        "lighting": "High-contrast flash mixed with harsh midday sunlight on the skater cutout, contrasting with flat, bright graphic lighting on the 3D typography.",\n        "photo": "Vintage grainy 35mm film with distressed halftone scan textures and subtle light leaks.",\n        "medium": "Mixed-media digital collage",\n        "color_palette": ["#1E73BE", "#FDFDFD", "#C82A2A", "#657C9C", "#EFEFEF"]\n    },\n    "compositional_deconstruction": {\n        "background": "A vibrant, clear blue sky layered with a vintage grainy film texture and subtle halftone dot patterns, transitioning down to an implied pale gray concrete ramp at the very bottom edge.",\n        "elements": [\n            {\n                "type": "obj",\n                "bbox": [128, 149, 354, 810],\n                "desc": "Massive 3D puffy, inflatable white typography spelling \'COMFY\'. The letters stretch across the upper half of the canvas, acting as a surreal, soft cloud-like backdrop.",\n                "color_palette": ["#FDFDFD", "#E0E0E0", "#D3DBE2"]\n            },\n            {\n                "type": "obj",\n                "bbox": [459, 37, 727, 264],\n                "desc": "A cluster of oversized, distressed red stamped circles and dots, applied loosely to the midground like a grunge ink stamp, partially obscuring the bottom left of the text.",\n                "color_palette": ["#C82A2A", "#A11D1D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [23, 366, 153, 666],\n                "desc": "A vertically oriented, torn paper side banner pinned to the left edge. The rough-edged paper displays the bold, stamped text \'STAY COZY\' in high-contrast black ink.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [287, 210, 756, 819],\n                "desc": "A sharp photographic cutout of a skateboarder mid-air in a relaxed pose. He wears loose-fitting washed denim jeans and a plain white tee, appearing to effortlessly float above the concrete ramp. A distinct white cutout border surrounds his silhouette.",\n                "color_palette": ["#FDFDFD", "#657C9C", "#2B2B2B", "#DCA57D"]\n            },\n            {\n                "type": "obj",\n                "bbox": [773, 39, 973, 187],\n                "desc": "A surreal, miniature floating skateboard cutout, positioned playfully in the upper right sky as if defying gravity.",\n                "color_palette": ["#D2A679", "#2B2B2B", "#C82A2A"]\n            },\n            {\n                "type": "obj",\n                "bbox": [105, 830, 905, 980],\n                "desc": "A wide, horizontal strip of heavily textured torn paper spanning the lower third of the composition. It features the bold typographic phrase \'BEYOND THE COMFORT ZONE\' intermixed with \'EFFORTLESS RIDE\' alongside ripped edges that reveal the background.",\n                "color_palette": ["#EFEFEF", "#1A1A1A", "#999999"]\n            }\n        ]\n    }\n}']}, {'id': 14, 'type': 'CLIPLoader', 'pos': [4730, 990], 'size': [470, 170], 'flags': {}, 'order': 6, 'mode': 0, 'inputs': [{'localized_name': 'clip_name', 'name': 'clip_name', 'type': 'COMBO', 'widget': {'name': 'clip_name'}, 'link': 157}], 'outputs': [{'localized_name': 'CLIP', 'name': 'CLIP', 'type': 'CLIP', 'links': [24]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'CLIPLoader', 'models': [{'name': 'qwen3vl_8b_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Qwen3-VL/resolve/main/text_encoders/qwen3vl_8b_fp8_scaled.safetensors', 'directory': 'text_encoders'}]}, 'widgets_values': ['qwen3vl_8b_fp8_scaled.safetensors', 'ideogram4', 'default']}, {'id': 27, 'type': 'PrimitiveInt', 'pos': [4240, 1610], 'size': [270, 110], 'flags': {}, 'order': 11, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'INT', 'widget': {'name': 'value'}, 'link': 153}], 'outputs': [{'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [32]}], 'title': 'Int (Width)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveInt'}, 'widgets_values': [1024, 'fixed']}, {'id': 28, 'type': 'PrimitiveInt', 'pos': [4250, 1800], 'size': [270, 110], 'flags': {}, 'order': 12, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'INT', 'widget': {'name': 'value'}, 'link': 154}], 'outputs': [{'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [35]}], 'title': 'Int (Height)', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveInt'}, 'widgets_values': [1024, 'fixed']}, {'id': 31, 'type': 'ComfyMathExpression', 'pos': [5340, 1400], 'size': [230, 80], 'flags': {'collapsed': True}, 'order': 13, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 32}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [33, 34]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 32, 'type': 'ComfyMathExpression', 'pos': [5350, 1470], 'size': [230, 80], 'flags': {'collapsed': True}, 'order': 14, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 35}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [36, 37]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 144, 'type': 'ComfyNumberConvert', 'pos': [5920, 1870], 'size': [230, 100], 'flags': {}, 'order': 15, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 195}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': [208]}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 145, 'type': 'JsonExtractString', 'pos': [5450, 1870], 'size': [400, 200], 'flags': {}, 'order': 16, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 196}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [195]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'mu']}, {'id': 146, 'type': 'ComfyNumberConvert', 'pos': [5930, 2110], 'size': [230, 100], 'flags': {}, 'order': 17, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 197}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': [209]}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 147, 'type': 'JsonExtractString', 'pos': [5010, 1630], 'size': [410, 470], 'flags': {}, 'order': 18, 'mode': 0, 'inputs': [{'localized_name': 'key', 'name': 'key', 'type': 'STRING', 'widget': {'name': 'key'}, 'link': 218}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [199]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['{\n  "Quality": {\n    "num_steps": 48,\n    "mu": 0.0,\n    "std": 1.5,\n    "preset_id": "V4_QUALITY_48"\n  },\n  "Default": {\n    "num_steps": 20,\n    "mu": 0.0,\n    "std": 1.75,\n    "preset_id": "V4_DEFAULT_20"\n  },\n  "Turbo": {\n    "num_steps": 12,\n    "mu": 0.5,\n    "std": 1.75,\n    "preset_id": "V4_TURBO_12"\n  }\n}', 'Default']}, {'id': 148, 'type': 'StringReplace', 'pos': [5050, 2150], 'size': [230, 40], 'flags': {'collapsed': True}, 'order': 19, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 199}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [196, 200, 201]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', "'", '"']}, {'id': 149, 'type': 'JsonExtractString', 'pos': [5460, 1610], 'size': [400, 200], 'flags': {}, 'order': 20, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 200}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [202]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'num_steps']}, {'id': 150, 'type': 'JsonExtractString', 'pos': [5450, 2110], 'size': [400, 200], 'flags': {}, 'order': 21, 'mode': 0, 'inputs': [{'localized_name': 'json_string', 'name': 'json_string', 'type': 'STRING', 'widget': {'name': 'json_string'}, 'link': 201}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [197]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'JsonExtractString'}, 'widgets_values': ['', 'std']}, {'id': 151, 'type': 'ComfyNumberConvert', 'pos': [5920, 1620], 'size': [230, 100], 'flags': {}, 'order': 22, 'mode': 0, 'inputs': [{'label': 'value', 'localized_name': 'value', 'name': 'value', 'type': 'INT,FLOAT,STRING,BOOLEAN', 'link': 202}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': []}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [207]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyNumberConvert'}, 'widgets_values': []}, {'id': 154, 'type': 'UNETLoader', 'pos': [4730, 740], 'size': [470, 170], 'flags': {}, 'order': 23, 'mode': 0, 'showAdvanced': True, 'inputs': [{'localized_name': 'unet_name', 'name': 'unet_name', 'type': 'COMBO', 'widget': {'name': 'unet_name'}, 'link': 216}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [211]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.8.2', 'Node name for S&R': 'UNETLoader', 'models': [{'name': 'ideogram4_unconditional_fp8_scaled.safetensors', 'url': 'https://huggingface.co/Comfy-Org/Ideogram-4/resolve/main/diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors', 'directory': 'diffusion_models'}]}, 'widgets_values': ['ideogram4_unconditional_fp8_scaled.safetensors', 'default']}, {'id': 155, 'type': 'DualModelGuider', 'pos': [5790, 870], 'size': [270, 180], 'flags': {}, 'order': 24, 'mode': 0, 'inputs': [{'localized_name': 'model', 'name': 'model', 'type': 'MODEL', 'link': 223}, {'localized_name': 'positive', 'name': 'positive', 'type': 'CONDITIONING', 'link': 213}, {'localized_name': 'model_negative', 'name': 'model_negative', 'shape': 7, 'type': 'MODEL', 'link': 211}, {'localized_name': 'negative', 'name': 'negative', 'shape': 7, 'type': 'CONDITIONING', 'link': 214}], 'outputs': [{'localized_name': 'GUIDER', 'name': 'GUIDER', 'type': 'GUIDER', 'links': [215]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'DualModelGuider'}, 'widgets_values': [7]}, {'id': 156, 'type': 'CustomCombo', 'pos': [4720, 1630], 'size': [270, 280], 'flags': {}, 'order': 25, 'mode': 0, 'inputs': [{'localized_name': 'choice', 'name': 'choice', 'type': 'COMBO', 'widget': {'name': 'choice'}, 'link': 219}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [218]}, {'localized_name': 'INDEX', 'name': 'INDEX', 'type': 'INT', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'CustomCombo'}, 'widgets_values': ['Default', 1, 'Quality', 'Default', 'Turbo', '']}, {'id': 157, 'type': 'CFGOverride', 'pos': [5790, 650], 'size': [260, 170], 'flags': {}, 'order': 26, 'mode': 0, 'inputs': [{'localized_name': 'model', 'name': 'model', 'type': 'MODEL', 'link': 222}], 'outputs': [{'localized_name': 'MODEL', 'name': 'MODEL', 'type': 'MODEL', 'links': [223]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'CFGOverride'}, 'widgets_values': [3, 0.7, 1]}], 'groups': [{'id': 1, 'title': 'Models', 'bounding': [4700, 420, 530, 1100], 'color': '#3f789e', 'flags': {}}, {'id': 2, 'title': 'Latent Size', 'bounding': [5260, 1080, 450, 440], 'color': '#3f789e', 'flags': {}}, {'id': 3, 'title': 'Sampling', 'bounding': [5740, 420, 780, 1100], 'color': '#3f789e', 'flags': {}}, {'id': 4, 'title': 'Prompt', 'bounding': [5260, 420, 450, 640], 'color': '#3f789e', 'flags': {}}, {'id': 5, 'title': 'Image Size', 'bounding': [4130, 1540, 530, 420], 'color': '#3f789e', 'flags': {}}, {'id': 9, 'title': 'Preset', 'bounding': [4700, 1540, 1820, 780], 'color': '#3f789e', 'flags': {}}], 'links': [{'id': 8, 'origin_id': 24, 'origin_slot': 0, 'target_id': 10, 'target_slot': 0, 'type': 'CONDITIONING'}, {'id': 33, 'origin_id': 31, 'origin_slot': 1, 'target_id': 11, 'target_slot': 0, 'type': 'INT'}, {'id': 36, 'origin_id': 32, 'origin_slot': 1, 'target_id': 11, 'target_slot': 1, 'type': 'INT'}, {'id': 11, 'origin_id': 18, 'origin_slot': 0, 'target_id': 12, 'target_slot': 0, 'type': 'NOISE'}, {'id': 13, 'origin_id': 16, 'origin_slot': 0, 'target_id': 12, 'target_slot': 2, 'type': 'SAMPLER'}, {'id': 14, 'origin_id': 17, 'origin_slot': 0, 'target_id': 12, 'target_slot': 3, 'type': 'SIGMAS'}, {'id': 15, 'origin_id': 11, 'origin_slot': 0, 'target_id': 12, 'target_slot': 4, 'type': 'LATENT'}, {'id': 16, 'origin_id': 12, 'origin_slot': 0, 'target_id': 13, 'target_slot': 0, 'type': 'LATENT'}, {'id': 17, 'origin_id': 9, 'origin_slot': 0, 'target_id': 13, 'target_slot': 1, 'type': 'VAE'}, {'id': 34, 'origin_id': 31, 'origin_slot': 1, 'target_id': 17, 'target_slot': 1, 'type': 'INT'}, {'id': 37, 'origin_id': 32, 'origin_slot': 1, 'target_id': 17, 'target_slot': 2, 'type': 'INT'}, {'id': 24, 'origin_id': 14, 'origin_slot': 0, 'target_id': 24, 'target_slot': 0, 'type': 'CLIP'}, {'id': 32, 'origin_id': 27, 'origin_slot': 0, 'target_id': 31, 'target_slot': 0, 'type': 'INT'}, {'id': 35, 'origin_id': 28, 'origin_slot': 0, 'target_id': 32, 'target_slot': 0, 'type': 'INT'}, {'id': 25, 'origin_id': 13, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'IMAGE'}, {'id': 152, 'origin_id': -10, 'origin_slot': 0, 'target_id': 24, 'target_slot': 1, 'type': 'STRING'}, {'id': 153, 'origin_id': -10, 'origin_slot': 1, 'target_id': 27, 'target_slot': 0, 'type': 'INT'}, {'id': 154, 'origin_id': -10, 'origin_slot': 2, 'target_id': 28, 'target_slot': 0, 'type': 'INT'}, {'id': 155, 'origin_id': -10, 'origin_slot': 3, 'target_id': 18, 'target_slot': 0, 'type': 'INT'}, {'id': 156, 'origin_id': -10, 'origin_slot': 4, 'target_id': 23, 'target_slot': 0, 'type': 'COMBO'}, {'id': 157, 'origin_id': -10, 'origin_slot': 5, 'target_id': 14, 'target_slot': 0, 'type': 'COMBO'}, {'id': 158, 'origin_id': -10, 'origin_slot': 6, 'target_id': 9, 'target_slot': 0, 'type': 'COMBO'}, {'id': 195, 'origin_id': 145, 'origin_slot': 0, 'target_id': 144, 'target_slot': 0, 'type': 'STRING'}, {'id': 196, 'origin_id': 148, 'origin_slot': 0, 'target_id': 145, 'target_slot': 0, 'type': 'STRING'}, {'id': 197, 'origin_id': 150, 'origin_slot': 0, 'target_id': 146, 'target_slot': 0, 'type': 'STRING'}, {'id': 199, 'origin_id': 147, 'origin_slot': 0, 'target_id': 148, 'target_slot': 0, 'type': 'STRING'}, {'id': 200, 'origin_id': 148, 'origin_slot': 0, 'target_id': 149, 'target_slot': 0, 'type': 'STRING'}, {'id': 201, 'origin_id': 148, 'origin_slot': 0, 'target_id': 150, 'target_slot': 0, 'type': 'STRING'}, {'id': 202, 'origin_id': 149, 'origin_slot': 0, 'target_id': 151, 'target_slot': 0, 'type': 'STRING'}, {'id': 207, 'origin_id': 151, 'origin_slot': 1, 'target_id': 17, 'target_slot': 0, 'type': 'INT'}, {'id': 208, 'origin_id': 144, 'origin_slot': 0, 'target_id': 17, 'target_slot': 3, 'type': 'FLOAT'}, {'id': 209, 'origin_id': 146, 'origin_slot': 0, 'target_id': 17, 'target_slot': 4, 'type': 'FLOAT'}, {'id': 211, 'origin_id': 154, 'origin_slot': 0, 'target_id': 155, 'target_slot': 2, 'type': 'MODEL'}, {'id': 213, 'origin_id': 24, 'origin_slot': 0, 'target_id': 155, 'target_slot': 1, 'type': 'CONDITIONING'}, {'id': 214, 'origin_id': 10, 'origin_slot': 0, 'target_id': 155, 'target_slot': 3, 'type': 'CONDITIONING'}, {'id': 215, 'origin_id': 155, 'origin_slot': 0, 'target_id': 12, 'target_slot': 1, 'type': 'GUIDER'}, {'id': 216, 'origin_id': -10, 'origin_slot': 7, 'target_id': 154, 'target_slot': 0, 'type': 'COMBO'}, {'id': 218, 'origin_id': 156, 'origin_slot': 0, 'target_id': 147, 'target_slot': 0, 'type': 'STRING'}, {'id': 219, 'origin_id': -10, 'origin_slot': 8, 'target_id': 156, 'target_slot': 0, 'type': 'COMBO'}, {'id': 222, 'origin_id': 23, 'origin_slot': 0, 'target_id': 157, 'target_slot': 0, 'type': 'MODEL'}, {'id': 223, 'origin_id': 157, 'origin_slot': 0, 'target_id': 155, 'target_slot': 0, 'type': 'MODEL'}], 'extra': {}}, {'id': 'f5f04613-ee09-4cd9-9ada-a880360891d4', 'version': 1, 'state': {'lastGroupId': 9, 'lastNodeId': 176, 'lastLinkId': 252, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': 'Ideogram4 Caption Prompt Template', 'inputNode': {'id': -10, 'bounding': [4830, 2840, 128, 108]}, 'outputNode': {'id': -20, 'bounding': [6270, 2700, 128, 68]}, 'inputs': [{'id': 'b96a4263-d942-4b93-9225-03d8aff697ed', 'name': 'value', 'type': 'STRING', 'linkIds': [180], 'label': 'user_prompt', 'pos': [4934, 2864]}, {'id': '1292f2e8-bc8b-4896-956a-77cbfe7f7482', 'name': 'source', 'type': '*', 'linkIds': [234], 'label': 'width', 'pos': [4934, 2884]}, {'id': '52396a95-c41b-4e06-94be-b6000d977bec', 'name': 'source_1', 'type': '*', 'linkIds': [236], 'label': 'height', 'pos': [4934, 2904]}], 'outputs': [{'id': '6527ba64-e7bb-474f-b015-bd6931e990ca', 'name': 'STRING', 'type': 'STRING', 'linkIds': [247], 'pos': [6294, 2724]}], 'widgets': [], 'nodes': [{'id': 114, 'type': 'PrimitiveStringMultiline', 'pos': [5070, 2580], 'size': [430, 520], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [228]}], 'title': 'System Prompt', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveStringMultiline'}, 'widgets_values': ['[META]\nfrozen: false\ndescription: Slim single-shot magic prompt — splatter planning + v15 output discipline, deduped for faster inference. Thinking off.\nthinking_mode: disabled\n\n[SYSTEM]\nYou convert a natural-language user idea into a structured JSON caption an image renderer can consume. You receive the user idea plus a target aspect ratio, and you emit one JSON object.\n\n## OUTPUT CONTRACT — exactly three top-level keys, in this order:\n\n```json\n{"aspect_ratio":"W:H","high_level_description":"...","compositional_deconstruction":{"background":"...","elements":[ ... ]}}\n```\n\n- Emit a SINGLE-LINE MINIFIED JSON object — no markdown fences, no commentary, no other top-level keys.\n- Preserve non-ASCII characters as-is (CJK, Cyrillic, Devanagari, Arabic, accented Latin). Never escape with `\\uNNNN`, transliterate, or replace `café` with `cafe`.\n- Use SINGLE quotes for embedded text references in prose fields (`\'Joe\'s Diner\'`, not `\\"Joe\'s Diner\\"`). The `text` field of text elements is the exception — that field holds the user\'s verbatim characters, may use any characters, and follows QUOTED SPAN FIDELITY below.\n\n### `aspect_ratio` (first field, always required)\n\nA string in `W:H` form with positive integers (`1:1`, `16:9`, `9:16`, `4:5`, `3:1`, `2:3`, etc.).\n- If the user message gives a concrete `W:H`, echo it verbatim.\n- If the user message says `auto`, pick a concrete ratio that matches the medium and composition (panoramic subjects → wide ratios like `16:9` or `3:1`; portrait subjects → tall like `9:16` or `4:5`; designed artifacts → format conventions like `2:3` book cover, `3:4` poster; ambiguous → `1:1`). NEVER emit the literal string `auto`.\n- The aspect ratio you commit to drives every bbox decision. Pick it first.\n\n### `high_level_description` — observational summary (50-word hard cap)\n\n- ONE long sentence preferred, never more than two.\n- Reads like a short natural-language prompt, not an analysis. Starts immediately with the subject — no "this image shows", "depicts", "captures".\n- Identifies subject(s), medium, and overall composition. Names recognized pop-culture entities by full name (`Nike Air Jordan 1`, `Eiffel Tower`, `Mario (Nintendo character)`).\n- Don\'t enumerate granular features (every color, every grid dimension, every typography choice). That detail belongs in element descs or `background`.\n- `various`, `multiple`, general categories ARE appropriate here. Specificity rule (below) applies to element descs and `background`, NOT this field.\n- For transparent backgrounds, include the literal phrase `on a transparent background`.\n\nGOOD: `A full-action shot of a male soccer player in a red kit and black Adidas cleats kicking a soccer ball on a green turf field, with a blurred crowd in the stadium background.`\nBAD (over-specifies): `A male soccer player captured mid-kick on a bright green grass pitch, right leg fully extended through the follow-through at the precise moment his black-and-white studded boot makes contact with a white-and-black size-5 ball...`\n\n## ELEMENTS — what they are, what they\'re not\n\nEach element is one of:\n```\n{"type":"obj","bbox":[y1,x1,y2,x2],"desc":"..."}\n{"type":"text","bbox":[y1,x1,y2,x2],"text":"LINE ONE\\nLINE TWO","desc":"..."}\n```\n\n`bbox` is optional per-element (see BBOX section below).\n\n### SINGLE SUBJECT = SINGLE ELEMENT\n\nA coherent subject — one animal, person, vehicle, building, plant, instrument, machine — is exactly ONE `obj` element. Anatomical and structural parts are descriptive attributes inside that element\'s `desc`, NOT separate elements.\n\nFORBIDDEN: a bee split into 8 elements (thorax/abdomen/wings/eyes/legs/...); a car split into 6 (body/wheels/windshield/...); a person split into 7 (head/torso/each limb/...); a building split into 5 (foundation/walls/windows/roof/door); a flower split into 3 (petals/stem/leaves).\n\nWhen MULTIPLE distinct subjects appear (a person AND a dog; two bees; three runners), use MULTIPLE elements — one per subject.\n\n**Test:** part-of-one-thing → goes in that thing\'s desc. Separate thing → its own element.\n\n**Transparent enclosure + featured contents = ONE element.** Display cases, snow globes, terrariums, aquariums, specimen jars, bell jars, vitrines containing a featured subject: name the enclosure + contents as a single unified desc.\n\n**Configured parts + revealed interior = ONE element.** A car with an open door, a machine with raised hood, a building with drawn curtains: the open state and any revealed interior are attributes of the single subject\'s desc, not separate elements.\n\n### Element desc — what to write (30–60 words, 60-word HARD CAP)\n\nIdentity first, then major attributes briefly, then one distinguishing detail if relevant. Each desc is a standalone catalog entry — open with the subject\'s identity, not a referring phrase like "the X" that assumes the reader has seen the scene.\n\nGOOD (introduces from scratch):\n- `Woman walking on the platform, medium size. Shoulder-length dark wavy hair, medium skin tone, light blue button-down shirt and grey trousers. Small bag slung over the right shoulder.`\n- `Circular concrete tunnel entrance with glowing blue ring lights along the interior. Train tracks lead directly into the dark opening.`\n\n**Major attributes — always name:**\n- People: skin tone, hair (color + style), each visible garment with color, expression/gaze, pose, distinguishing feature (mole, glasses, jewelry, held prop).\n- Objects: shape, material, color, distinctive parts (handle, label, logo, marking).\n- Scenes/structures: type, primary material, color, distinctive structural elements.\n\n**Skip (eat word budget for marginal benefit):**\n- Surface-finish micro-prose (`finely granular matte texture with subtle sheen along the elytral ridges`). Pick one short descriptor (matte/glossy/metallic/textured) or omit.\n- Pose mechanics per-limb. Pick ONE summary action phrase plus the major attributes.\n- Camera/shadow/lighting micro-detail per element. Belongs in `background`.\n- Fabric weave, skin texture nuances, micro-anatomy.\n\n### Element desc — what NOT to include\n\n**No shadows.** Cast shadows, drop shadows, ground shadows, contact shadows, ambient occlusion — describe in `background` only when scene-wide, otherwise omit (the renderer infers them). Forbidden: `casts a thin hard shadow to the lower right`, `with a soft drop shadow beneath`.\n\n**No camera or render language.** Depth of field, focus, sharpness, bokeh, exposure, motion blur, lens flare, chromatic aberration, film grain — render properties belong in `high_level_description` or `background` as natural prose ONLY when the user prompt explicitly named them. NEVER inside an obj desc.\n  - EXCEPTION — viewpoint/angle (`from a low-angle perspective`, `bird\'s-eye view`, `eye-level`) IS allowed in obj descs when the prompt calls for it. Place once, usually in the focal subject\'s desc or background.\n\n**No describing impressions instead of physical reality.** Avoid `luminous`, `radiant`, `vibrant`, `lush`, `dynamic`, `glowing` (metaphorically), `gorgeous`, `stunning`, `breathtaking`, `mesmerizing`. Use observable properties: `cheekbone catches a small highlight`, not `luminous complexion`.\n\n**No scene-context repetition per-element.** Lighting direction, ambient surface, mounting context, weather → describe ONCE in `background`. Each element\'s desc focuses on what\'s UNIQUE to that element.\n\n### Anchor placements to named references\n\nSpecify body parts, surfaces, spatial landmarks.\n- CORRECT: `applied to the forehead near the hairline above the left eyebrow`.\n- INCORRECT: `pressed against the skin`.\n- CORRECT: `resting on the lower-right corner of the table directly in front of the laptop`.\n- INCORRECT: `sitting on the surface`.\n\n## BACKGROUND — what goes here, what doesn\'t (CRITICAL)\n\n`background` describes the scene SHELL: walls and finishes, floor/ground and surface state, ceiling and architectural fixtures, windows as architecture, atmospheric context (sky, clouds, fog, dust, mist), scene-wide ambient lighting, distant out-of-focus context (horizon, blurred crowds, distant scenery).\n\n### No double-counting\n\nAnything described in `background` CANNOT also appear as an obj element. Each scene component lives in EXACTLY ONE field. Decide once and commit. Before emitting an obj element, scan `background` — if the component is named there, omit the obj element.\n\n### ALWAYS-BACKGROUND — these live in `background` only, never as obj elements:\n\n- sky, clouds, atmospheric color\n- horizon\n- distant mountains, hills, tree lines\n- atmospheric weather (fog, haze, mist, smoke)\n- distant cityscape or stadium architecture\n- distant blurred or simplified crowds\n- the floor / ground / turf / paving surface the scene sits on\n- ambient walls or studio backdrop behind focal subjects\n\nYou cannot split these by region. `sky upper-left portion`, `sky behind the fortress`, `sky upper two-thirds` are the SAME component — describe in `background` once. Same for crowd, ground, horizon.\n\nIf you want technique-level detail on an atmospheric component (watercolor wet-on-wet sky blooms, fog with directional density variation), put that detail in `background`. The `background` field is allowed to be long.\n\n### Ground/floor/pavement is ALWAYS background — zero tolerance\n\nThe surface the scene sits on — floor, ground, turf, grass, dirt, sand, asphalt, pavement, road, sidewalk, deck, water surface, snow, tile floor, hardwood, marble — lives in `background` only. This holds REGARDLESS of how the input formats it: if the prompt lists `Wet rain-slicked pavement below` as a foreground bullet, RE-CLASSIFY it into background.\n\n**Surface character that belongs in background, not as a separate obj:** wet / rain-slicked / mud-streaked / dusty / cracked / polished / weathered surface state; reflective neon pools, fragmented color reflections, puddles, wet patches, mud patches, ice patches, frost, snow on the floor, water pooled on the ground, oil slicks, footprints, tire tracks; surface material (asphalt, cobblestone, hardwood, tile, marble, packed dirt); texture words for the floor (glassy, mirror-like, matte, polished, rough).\n\n**Puddles, reflections, wet patches are part of the ground surface** — never separate obj elements, regardless of whether they reflect the hero\'s silhouette or carry visible content.\n\n**Failure mode this prevents:** when a standing hero is the focal element and the floor is also emitted as an obj at the bottom of the frame, the renderer treats the floor obj as a 2D frame band rather than a perspectival receding plane, and clips the hero\'s legs into it — figure rendered half-in-the-ground with feet/calves buried.\n\n**Discrete objects ON the floor are still elements:** broken glass shards, crushed cans, scattered debris, leaves, rocks, dropped tools, brick fragments, foreground litter remain obj elements. The rule applies to the SURFACE itself and any state of that surface (wet, frozen, muddy, puddled), never to solid objects resting on it.\n\n### Background is the shell only — no individually-placeable things\n\nFurniture, vehicles, equipment, people, animals, decor (artwork, signs, plants in pots, stacks of books), free-standing lamps → obj elements, never `background`.\n\n### Shell-affixed prominent objects → DUAL MENTION\n\nSome objects are simultaneously part of the shell AND focal elements that define the room\'s identity: a chalkboard covering the back wall of a classroom, a fireplace built into a living-room wall, a large mounted TV, a stage proscenium, a built-in altar, a built-in bookshelf, a large fixed reception desk, a fixed sign/banner.\n\nFor these, MANDATORY all three steps:\n1. **MENTION in `background`** as part of the shell — anchors the object to the wall.\n2. **EMIT as an obj element** with the qualifier `"the primary background element"` (or similar) at the start of its desc. The obj carries the detail (material, content, frame, mounting).\n3. **PLACE FIRST in the elements list** so painter\'s-algorithm draws it behind foreground items.\n\nSkipping step 1 (the most common failure) makes the renderer float the object in mid-room or render it in front of foreground subjects.\n\nThis is an EXCEPTION to the shell rule\'s "no individually placeable things". Applies ONLY to objects that genuinely define the room\'s architectural identity. Free-standing items (chairs, table lamps, plants in pots, framed pictures on a wall) get the normal treatment: elements only, no background mention.\n\n### Recession/arrangement is not architecture\n\nDo not smuggle furniture or people into `background` by describing them as a receding arrangement. Forbidden background phrasings: `rows of desks recede toward the back`, `a grid of desks fills the room`, `students seated at the desks`, `chairs arranged in front of the podium`, `the room is filled with people`, `cars parked along the street`, `customers seated at the tables`. The arrangement IS the foreground content — emit elements.\n\n### No medium/post-processing effects in background\n\n`background` describes WHAT is in the scene, not HOW it was made. Forbidden in `background` — even when the prompt names the effect (route those to HLD instead):\n- Film grain, Kodak/Portra/Tri-X grain, ISO noise\n- Lens flare, chromatic aberration, vignetting, bokeh quality\n- Color cast / film-stock shift (warm shift, cool shift)\n- Paper texture, paper grain, canvas texture\n- Brushstroke texture, palette-knife texture\n- Halftone dots, screen-print texture, risograph texture\n\n**Test:** read `background` aloud. If you can picture the EMPTY room from the description — no furniture, no people, no equipment, no wall decor — you\'re in the shell. If anything disappears when you remove the room\'s contents, the background has leaked.\n\n## BBOX STRATEGY\n\nINCLUDE bboxes on elements where precise positioning matters — portrait subjects, products on a surface, logos, signs on a wall, distinct individually-placeable objects.\n\nOMIT bboxes on elements that represent dense or hard-to-enumerate visuals — crowds, fields of wildflowers, scattered particles, starry skies. Per-element judgment.\n\n### Coordinate system\n\nCoordinates are normalized to the target image shape: `x` runs left→right along full width (0 = left edge, 1000 = right), `y` runs top→bottom along full height (0 = top, 1000 = bottom). Top-left origin. Format `[y1, x1, y2, x2]` with `y1 < y2`, `x1 < x2`.\n\n### Shape warning (common failure)\n\nBbox values are normalized to 0–1000 in BOTH axes. A square `[0, 0, 500, 500]` is square only on a square frame; on 16:9 it becomes a wide rectangle, on 9:16 a tall rectangle. Most bbox failures (extra subjects, duplicates, mis-scaled objects) come from this mismatch.\n\nFor round objects or square on-screen regions, scale spans so `(x2-x1)/(y2-y1) ≈ W/H`. For single-subject prompts on wide frames, prefer narrower x-spans. For multi-subject prompts, give each a tight bbox so no one bbox dominates and invites a duplicate.\n\n## SPECIFICITY — commit to one value\n\nThis JSON feeds a diffusion model. Leave nothing for the model to invent or choose.\n\n**Banned hedge phrasings** (in elements and background): `things like`, `such as`, `e.g.`, `for example`, `or similar`, `various`, `could include`, `might be`, `some kind of`, `style of`. Replace with concrete nouns, counts, colors, materials, poses.\n\n**Banned alternative listings for one property:** `pale institutional off-white or pale green`, `oak or walnut`, `cream or ivory`, `late afternoon or early evening`, `italic serif or italic sans-serif`, `bold or semibold`. Pick ONE and commit. `or` is reserved for the loader\'s exclusive-choice idiom (`\'YES\' or \'NO\'`), not captioner hedging.\n\n**Typography specifically:** name ONE typeface category (serif OR sans-serif OR display OR script OR monospace), ONE weight (bold/regular/light/medium), ONE style (italic OR upright). Never two joined by `or`.\n\n**Banned "implied/suggested" hedges:** `a desk corner implied`, `a chair suggested beneath the figure`, `a building hinted at`, `a shadow that reads as a person`. If it\'s in the scene, paint it concretely. If it isn\'t, leave it out. Forbidden words: `implied, suggested, hinted, barely visible, possibly, perhaps, maybe, might be, could be, reads as, almost`.\n\n**Exhaustive content preservation.** When the user provides enumerable content — schedules, itineraries, lists, menu items, steps, names, times — every item must appear in the output. Use as many text elements as needed; never sacrifice completeness for layout.\n\n**Named prompt elements MUST appear.** Every explicitly-named visual unit in the user prompt MUST appear as its own element:\n- Input `text:` sections — every entry becomes its own text element, verbatim. Zero tolerance: 3 entries in input → ≥3 text elements in output. Empty `text: []` is the only case where text elements may be omitted on that basis.\n- Quoted strings (single or double quotes) — each is its own text element.\n- Speech bubbles / dialogue callouts / thought bubbles / captions — each gets a text element for the quoted string AND an obj element for the bubble/balloon/container.\n- Named decorative elements (`small medical cross icon top-left`, `airplane arc trajectory`, `flame-lick flourish at the tail`) — each gets its own obj.\n- Named badges / chips / CTAs / strips — each gets its own obj (and text if it carries a quoted string).\n- Named accents / graphic devices (`hairline rule`, `dot grid`, `accent line`, `divider`) — each gets its own obj UNLESS it\'s a scene-wide overlay belonging in `background`.\n\n**Test before emitting:** count named visual units in the user prompt; element list must contain at least that many.\n\n**No placeholder enumeration.** When the imagined image contains a sequentially-numbered, alphabetically-labeled, or otherwise individually-identified set (stones numbered 1–50, parking spaces A1–A20, place cards `1st`–`12th`, a periodic table of 118 elements, a calendar grid of 31 dates, a 22-name team roster), EACH item is its own element. No `etc.`, no `and so on`, no `6 through 49`, no single obj grouping all into one cluster. List ALL of them.\n\nThe "dense unenumerable group" exception (crowd of thousands, field of wildflowers, starry sky) does NOT apply to enumerable sets — if items are sequentially identified, they\'re enumerable BY DEFINITION.\n\n**Don\'t invent visual concepts the user didn\'t ask for.** Forbidden without explicit user request: `glitch art`, `wireframe overlay`, `mesh that fragments the body`, `digital artifacts`, `dissolved`, `decompose`. If the prompt asks for a cinematic photo of a journalist, render a cinematic photo of a journalist — not a glitch-art composite.\n\n## PLANNING — turn the user idea into elements\n\n### 1. Pick a medium\n\n`photograph | illustration | 3D render | graphic design` — applies as natural-language framing inside HLD/background, NOT as a structured slot.\n\nDecision: **DESIGNED artifact vs CAPTURED / DRAWN / RENDERED moment.**\n- **graphic design** — poster, book cover, album cover, magazine cover, flyer, banner, social post, sticker, logo, wordmark, packaging, app icon, UI mockup, infographic, menu, greeting card, ticket, signage. If a human designer would sit at a desk to make it.\n- **photograph** — portrait, landscape, lifestyle, street, sport, wildlife, food, product, fashion editorial (when described as a photograph). Default for ambiguous everyday scenes.\n- **illustration** — cartoon, anime, manga, comic, watercolor, oil painting, ink, vector, pixel art, children\'s book illustration, named studios (Ghibli, KyoAni, Pixar 2D).\n- **3D render** — CGI, octane/unreal/blender, hyperrealistic product render, arch viz, isometric low-poly, voxel, named 3D studios.\n\nSilent / ambiguous → photograph (default). The subject\'s reality status does NOT override this default — wizards, dragons, aliens, robots in a photograph are valid; the brief must explicitly ASK for illustration / painting / render to get one.\n\nImperative verbs at the start ("Illustrate a…", "Paint a…", "Draw a…", "Render a…") are NOT medium signals — they mean "depict / show". Default to photograph unless an explicit medium-noun or style name appears.\n\n### 2. Style commitment\n\nInside HLD/background prose, name the style ONCE (`Studio Ghibli animation`, `Pixar 3D animation`, `35mm film photograph`, `iPhone photo`, `editorial digital painting`, `flat vector illustration`). Keep it short — recognizable style names are enough; the renderer knows them. Don\'t append technique detail (`with hand-painted gouache backgrounds`) on top of well-known names.\n\n**"Professional picture/photo/portrait" of a person means PROFESSIONAL CONTEXT, not professional camera equipment.** Read as corporate headshot, LinkedIn profile, business bio — neutral business attire, soft even daylight, neutral backdrop, friendly approachable expression. NOT dramatic studio rim-lighting, creamy DSLR bokeh, dark moody backdrop.\n\n### 3. Photoreal defaults — AVOID "warm"\n\nFor photographic prompts (no specified medium beyond `photo`/`photorealistic`/`selfie`/real-world scene):\n- Default to iPhone aesthetic — phone snapshot, ambient natural light, neutral white balance, accurate (not flattering) skin tones, ordinary framing. AVOID DSLR-magazine markers (creamy bokeh, telephoto compression, dramatic rim lighting, cinematic grade) — those signal AI-generation.\n- Default lighting framing: `natural daylight`, `overcast daylight`, `diffused daylight`, `cool-neutral white balance`. The word **"warm"** (in any phrase: `warm light`, `warm window light`, `warm tone`, `warm grading`) is BANNED as a grading adjective — it triggers the amber/golden AI look that ruins photorealism. When a scene physically has a warm-coloured light source (candle, sodium streetlamp, sunset), describe the SOURCE concretely (`candle flame`, `sodium streetlamp`) and the colour of the LIGHT POOL (`amber pool from the candle`) — but the global grade stays neutral.\n- Default composition: prefer non-centered framing (off-center, rule-of-thirds, asymmetrical, leading lines) for portraits, products, single-subject scenes. Use centered framing ONLY when the prompt explicitly calls for it (`centered`, `symmetrical`, `mandala`, `kaleidoscope`) or when the genre is inherently symmetric.\n- No motion blur in candid/realistic/iPhone-aesthetic photos. Motion blur is a craft signature (long-exposure pans, light streaks); using it in a candid signals AI. Real phone snapshots freeze the moment.\n- Saturation: don\'t stack `vibrant + bright + intense + saturated + electric + neon` for a neutral subject. Mention saturation ONCE (in HLD or background) only when the prompt explicitly asks.\n\n### 4. Populate underspecified scenes\n\nWhen the brief is sparse, don\'t render only what\'s explicitly named. Real scenes are populated. Add believable secondary subjects, micro-props that imply the subject\'s life, environmental texture, small narrative moments. Each invented element should belong in the world the brief implies — a paddy-field food stall plausibly has a chicken, a sauce bowl, a hand-painted price sign, a lantern.\n\n**Populate by depth layer.** Foreground (often-skipped), midground, background — each gets its own content. A foreground crop (an out-of-focus leaf at the bottom corner, the rim of a bowl, a fly mid-air close to camera) separates a real photograph from a postcard.\n\n**Commit to a specific cultural / regional identity.** "Southeast Asian village" is a hedge that produces generic AI visuals. "Vietnamese pho stall by the rice paddies outside Hoi An" is a real place. Specific commitment shapes architecture, signage script, food, dress, props.\n\n**Built environments need text everywhere.** Real shops, stalls, restaurants, vehicles, signage carry text on practically every surface. Generate text generously: shop name sign, sub-signs (`OPEN` / `TODAY\'S SPECIAL`), menu board with handwritten items, price labels, jar/bottle labels, name tags, posters, fortune slips, vehicle/equipment labels, sponsor logos. `text: []` is almost always wrong for built environments — if your scene has a shop/stall/restaurant/workshop/market/vehicle, populate text. Specific content, never `various labels` or `menu items`.\n\n**Override:** when the brief explicitly says `minimal`, `sparse`, `empty`, `lonely`, `isolated`, `quiet`, `still`, `negative space`, `alone`, `single subject`, `in the middle of nowhere`, respect the restraint and skip populate.\n\n**Fantastical / sci-fi / fantasy / futuristic briefs get a populate bonus.** Stack sky drama (galaxies, ringed planets, multiple moons, nebulae), opposing focal points (volcano right / waterfall left), mid-distance scale anchors (crystal columns, futuristic cityscape, megastructures), light/energy effects throughout, exotic architecture/geology, deeply saturated palettes.\n\n## TEXT HANDLING\n\nFor each text element:\n- `text` — literal characters appearing in the image, verbatim. Preserve diacritics, capitalization, punctuation. Never transliterate or strip.\n- `bbox` — optional, same coordinate system as obj elements.\n- `desc` — free-form prose covering size, location, font style, color, orientation, visual effects.\n\n**Sources of text to include:**\n1. **User-quoted text** (single OR double quotes) — verbatim, exact characters.\n2. **Format-required text** — headlines, taglines, author names, dates, venues, CTA copy, brand names, publisher marks, edition numbers (when format implies them).\n3. **In-scene contextual text** — signage, labels, license plates, badges, jersey numbers, t-shirt prints, awnings, neon signs, name tags.\n4. **Numeric content** — race numbers, jersey numbers, dates, prices, scores, time displays, address numbers. Numbers ARE text.\n5. **Prominent product brand text** — if an element names a prominent product (bottle, cosmetic, package, beverage) and the user didn\'t supply a real brand, invent a complete brand identity and list every label as text elements.\n\n**Rules:**\n- Exhaustive: if a viewer could read it, it goes in the list.\n- Each text element appears ONCE in the list. Do NOT also describe its characters in `description` — refer by role/position instead.\n- Use `\\n` for line breaks WITHIN a single text element (multi-line sign, stacked headline). Use SEPARATE list items for visually distinct text blocks.\n- For stylized hero typography where each letter is a distinct visual unit, stack with `\\n` at natural word breaks — long single-line stylized titles produce typos and dropped letters. e.g., `"ENTRE\\nVERSOS E\\nCONTOS"` not `"ENTRE VERSOS E CONTOS"`.\n- **Language scoping:** `scene`/`elements`/`description`/position descriptors are always in ENGLISH regardless of the user\'s brief language. Only the literal `text` field characters follow the user\'s brief language. Portuguese brief → English prose + Portuguese `text:` content.\n\n## POP CULTURE, BRANDS, NAMED REFERENCES\n\nWhen the user idea names or clearly implies a brand, trademark, product (sneaker/car/device), public figure, athlete, musician, actor, fictional character, film, show, game, franchise, team — the output MUST carry an explicit named reference in the relevant element `desc`, not a generic stand-in describing the look.\n\nDon\'t replace `Nike Dunk Low Panda` with `black and white retro sneakers`, `Spider-Man` with `a red-and-blue masked superhero`, `The Beatles` with `four men in matching suits` — unless the user asked for an anonymous lookalike. Name the specific thing the user pointed at.\n\n## TRANSPARENT BACKGROUND\n\nIf the user\'s idea calls for transparent background, transparent canvas, alpha channel, cutout/isolated subject, sticker-style with no backdrop, or similar, the `background` field MUST be exactly this string, verbatim and nothing else: `transparent background`\n\nDo not paraphrase (no `clear backdrop`, `empty alpha`, `no background`, `PNG transparency`).\n\nIn `high_level_description`, include the literal phrase `on a transparent background`.\n\n[USER]\nTARGET IMAGE ASPECT RATIO: {{width}}:{{height}} (width:height).\nUser idea: {{original_prompt}}']}, {'id': 115, 'type': 'PrimitiveStringMultiline', 'pos': [5070, 3150], 'size': [400, 200], 'flags': {}, 'order': 1, 'mode': 0, 'inputs': [{'localized_name': 'value', 'name': 'value', 'type': 'STRING', 'widget': {'name': 'value'}, 'link': 180}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [238]}], 'title': 'User Prompt', 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'PrimitiveStringMultiline'}, 'widgets_values': ["A surreal streetwear mixed-media collage poster featuring a relaxed skateboarder mid-air against a vibrant blue sky, backed by giant puffy 3D letters spelling 'COMFY'. The composition blends retro magazine cutout aesthetics with grunge elements like torn paper banners and distressed red stamps, conveying "]}, {'id': 163, 'type': 'StringReplace', 'pos': [5580, 2540], 'size': [400, 280], 'flags': {}, 'order': 2, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 228}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 238}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [239]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{original_prompt}}', '']}, {'id': 164, 'type': 'PreviewAny', 'pos': [5420, 3420], 'size': [230, 180], 'flags': {}, 'order': 3, 'mode': 0, 'inputs': [{'localized_name': 'source', 'name': 'source', 'type': '*', 'link': 235}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [240]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'PreviewAny'}, 'widgets_values': [None, None, None]}, {'id': 165, 'type': 'PreviewAny', 'pos': [5400, 3680], 'size': [230, 180], 'flags': {}, 'order': 4, 'mode': 0, 'inputs': [{'localized_name': 'source', 'name': 'source', 'type': '*', 'link': 237}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [242]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'PreviewAny'}, 'widgets_values': [None, None, None]}, {'id': 166, 'type': 'ComfyMathExpression', 'pos': [5100, 3420], 'size': [230, 190], 'flags': {'collapsed': False}, 'order': 5, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 234}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [235]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 167, 'type': 'ComfyMathExpression', 'pos': [5110, 3670], 'size': [230, 190], 'flags': {'collapsed': False}, 'order': 6, 'mode': 0, 'inputs': [{'label': 'a', 'localized_name': 'values.a', 'name': 'values.a', 'type': 'FLOAT,INT,BOOLEAN', 'link': 236}, {'label': 'b', 'localized_name': 'values.b', 'name': 'values.b', 'shape': 7, 'type': 'FLOAT,INT,BOOLEAN', 'link': None}], 'outputs': [{'localized_name': 'FLOAT', 'name': 'FLOAT', 'type': 'FLOAT', 'links': None}, {'localized_name': 'INT', 'name': 'INT', 'type': 'INT', 'links': [237]}, {'localized_name': 'BOOL', 'name': 'BOOL', 'type': 'BOOLEAN', 'links': None}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.23.0', 'Node name for S&R': 'ComfyMathExpression'}, 'widgets_values': ['max(((a + 15) // 16) * 16, 256)']}, {'id': 169, 'type': 'StringReplace', 'pos': [5710, 3250], 'size': [400, 280], 'flags': {}, 'order': 7, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 239}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 240}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [241]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{width}}', '']}, {'id': 170, 'type': 'StringReplace', 'pos': [5690, 3670], 'size': [400, 280], 'flags': {}, 'order': 8, 'mode': 0, 'inputs': [{'localized_name': 'string', 'name': 'string', 'type': 'STRING', 'widget': {'name': 'string'}, 'link': 241}, {'localized_name': 'replace', 'name': 'replace', 'type': 'STRING', 'widget': {'name': 'replace'}, 'link': 242}], 'outputs': [{'localized_name': 'STRING', 'name': 'STRING', 'type': 'STRING', 'links': [247]}], 'properties': {'enableTabs': False, 'tabWidth': 65, 'tabXOffset': 10, 'hasSecondTab': False, 'secondTabText': 'Send Back', 'secondTabOffset': 80, 'secondTabWidth': 65, 'cnr_id': 'comfy-core', 'ver': '0.24.0', 'Node name for S&R': 'StringReplace'}, 'widgets_values': ['', '{{height}}', '']}], 'groups': [], 'links': [{'id': 180, 'origin_id': -10, 'origin_slot': 0, 'target_id': 115, 'target_slot': 0, 'type': 'STRING'}, {'id': 228, 'origin_id': 114, 'origin_slot': 0, 'target_id': 163, 'target_slot': 0, 'type': 'STRING'}, {'id': 234, 'origin_id': -10, 'origin_slot': 1, 'target_id': 166, 'target_slot': 0, 'type': 'FLOAT,INT,BOOLEAN'}, {'id': 235, 'origin_id': 166, 'origin_slot': 1, 'target_id': 164, 'target_slot': 0, 'type': 'INT'}, {'id': 236, 'origin_id': -10, 'origin_slot': 2, 'target_id': 167, 'target_slot': 0, 'type': 'FLOAT,INT,BOOLEAN'}, {'id': 237, 'origin_id': 167, 'origin_slot': 1, 'target_id': 165, 'target_slot': 0, 'type': 'INT'}, {'id': 238, 'origin_id': 115, 'origin_slot': 0, 'target_id': 163, 'target_slot': 1, 'type': 'STRING'}, {'id': 239, 'origin_id': 163, 'origin_slot': 0, 'target_id': 169, 'target_slot': 0, 'type': 'STRING'}, {'id': 240, 'origin_id': 164, 'origin_slot': 0, 'target_id': 169, 'target_slot': 1, 'type': 'STRING'}, {'id': 241, 'origin_id': 169, 'origin_slot': 0, 'target_id': 170, 'target_slot': 0, 'type': 'STRING'}, {'id': 242, 'origin_id': 165, 'origin_slot': 0, 'target_id': 170, 'target_slot': 1, 'type': 'STRING'}, {'id': 247, 'origin_id': 170, 'origin_slot': 0, 'target_id': -20, 'target_slot': 0, 'type': 'STRING'}], 'extra': {}}]},

exec
/bin/zsh -lc "sed -n '1,140p' tests/test_subgraph_emission_contract.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 179ms:
from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.ingest.normalize import from_api, normalize_to_api
from vibecomfy.porting.emitter import emit_ready_template_python
from vibecomfy.commands.validate import _subgraph_freshness_diagnostics
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_materialized_subgraph_contract_includes_call_site_and_source_hash() -> None:
    path = "ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json"
    text = _emit_ready_from_ui_json(path, "edit/flux2_klein_9b_image_edit_base")

    assert "def image_edit_flux2_klein_9b(" in text
    assert "edited = image_edit_flux2_klein_9b(" in text
    assert "raw_call('7b34ab90" not in text
    assert "# vibecomfy source hash: sha256:" in text


def test_subgraph_freshness_detects_hash_drift(tmp_path: Path) -> None:
    path = "ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json"
    text = _emit_ready_from_ui_json(path, "edit/flux2_klein_9b_image_edit_base")
    template = tmp_path / "template.py"
    template.write_text(text.replace("# vibecomfy source hash: sha256:", "# vibecomfy source hash: sha256:" + "0" * 64 + "X", 1), encoding="utf-8")

    diagnostics = _subgraph_freshness_diagnostics(template)

    assert diagnostics
    assert "source hash changed" in diagnostics[0]


def test_subgraph_blank_labeled_input_matches_normalized_call_site_edge() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 1})
    workflow.nodes["2"] = VibeNode("2", "sg-enable", metadata={"_ui": {"inputs": [{"name": "", "label": "Enable", "link": 99}]}})
    workflow.edges.append(VibeEdge("1", "0", "2", "_un99"))
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-enable",
                    "name": "Prompt Enhancer",
                    "inputs": [{"name": "", "label": "Enable", "type": "BOOLEAN", "linkIds": [1]}],
                    "outputs": [{"name": "out", "type": "BOOLEAN"}],
                    "nodes": [{"id": 10, "type": "LazySwitchKJ", "inputs": [{"name": "switch", "link": 1}], "outputs": [{"name": "out"}]}],
                    "links": [
                        {"id": 1, "origin_id": -10, "origin_slot": 0, "target_id": 10, "target_slot": 0, "type": "BOOLEAN"},
                        {"id": 2, "origin_id": 10, "origin_slot": 0, "target_id": -20, "target_slot": 0, "type": "BOOLEAN"},
                    ],
                }
            ]
        }
    }

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test"},
        ready_requirements={},
        template_id="video/test",
        raw_workflow=raw,
    )

    assert "def prompt_enhancer(\n    *,\n    enable" in text
    assert "enable=intconstant" in text
    assert "enable=None" not in text


def test_subgraph_external_input_edge_becomes_function_parameter() -> None:
    workflow = VibeWorkflow("sample", WorkflowSource("sample"))
    workflow.nodes["1"] = VibeNode("1", "INTConstant", inputs={"value": 7})
    workflow.nodes["2"] = VibeNode("2", "sg-total")
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-total",
                    "name": "Total duration",
                    "inputs": [],
                    "outputs": [{"name": "FLOAT", "type": "FLOAT"}],
                    "nodes": [
                        {
                            "id": 20,
                            "type": "SimpleCalculatorKJ",
                            "inputs": [{"name": "variables.a", "link": 1}],
                            "outputs": [{"name": "FLOAT"}, {"name": "INT"}, {"name": "BOOLEAN"}],
                            "widgets_values": ["a + 1"],
                        }
                    ],
                    "links": [
                        {"id": 1, "origin_id": 1, "origin_slot": 0, "target_id": 20, "target_slot": 0, "type": "FLOAT"},
                        {"id": 2, "origin_id": 20, "origin_slot": 0, "target_id": -20, "target_slot": 0, "type": "FLOAT"},
                    ],
                }
            ]
        }
    }

    text = emit_ready_template_python(
        workflow,
        ready_metadata={"ready_template": "video/test"},
        ready_requirements={},
        template_id="video/test",
        raw_workflow=raw,
    )

    assert "def total_duration(\n    *,\n    variables_a" in text
    assert "'variables.a': variables_a" in text
    assert "variables_a=intconstant" in text


def _emit_ready_from_ui_json(path: str, template_id: str) -> str:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    api = normalize_to_api(raw, use_comfy_converter=False)
    workflow = from_api(api, source_path=path, workflow_id=Path(path).stem)
    return emit_ready_template_python(
        workflow,
        ready_metadata={
            "ready_template": template_id,
            "capability": "image_edit",
            "provenance": {"source_workflow": path},
        },
        ready_requirements={"models": [], "custom_nodes": []},
        template_id=template_id,
        raw_workflow=raw,
    )

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from vibecomfy.porting.emit.emit_subgraph import _build_subgraph_def; raw={\"id\":\"sg\",\"name\":\"S\",\"inputs\":[{\"name\":\"enable\",\"type\":\"BOOLEAN\"}],\"outputs\":[],\"nodes\":[{\"id\":10,\"type\":\"LazySwitchKJ\",\"inputs\":[{\"name\":\"switch\",\"link\":1}],\"outputs\":[],\"widgets_values\":[]}],\"links\":[{\"id\":1,\"origin_id\":-10,\"origin_slot\":0,\"target_id\":10,\"target_slot\":0,\"type\":\"BOOLEAN\"}]}; d=_build_subgraph_def(raw,slug=\"s\",source_path=None); print(d.nodes[\"10\"].inputs); print(type(d.nodes[\"10\"]).__name__)'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 1488ms:
{'switch': ['-10', 0]}
VibeNode

codex
The focused executable checks now pass locally: 12/12 selected task-6/mode/group cases (the parametrized cases account for the count). The remaining concern is reproducible: `_build_subgraph_def()` returns a real `VibeNode` whose `inputs` contains `{'switch': ['-10', 0]}` for a subgraph boundary connection. Because `-10` is excluded by the new canonical predicate, none of the new fail-closed guards sees it. I’m checking whether this is an intentional non-IR exception in the frozen contract or a genuine missed migration; the tasklist’s exact “no package-owned low-level VibeNode construction” wording currently points to the latter.
exec
/bin/zsh -lc 'rg -n "test_offline_parity_gate_green_on_starter_set|test_corpus_roundtrip_parity_with_compile_api|test_offline_parity_never_imports_comfy" tests && git diff --name-only 0f515870..8a8300bb -- tests | sort && git diff --name-only 8a8300bb..0d2bb176 -- tests | sort' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 181ms:
tests/quarantine/emitter_parity_surface.txt:15:tests/test_porting_ui_emitter.py::test_corpus_roundtrip_parity_with_compile_api
tests/quarantine/emitter_parity_surface.txt:17:tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json]
tests/quarantine/emitter_parity_surface.txt:18:tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/edit/qwen_image_edit.json]
tests/quarantine/emitter_parity_surface.txt:19:tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/image/flux2_klein_4b_t2i.json]
tests/quarantine/emitter_parity_surface.txt:20:tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/image/z_image.json]
tests/quarantine/emitter_parity_surface.txt:21:tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/video/wan_i2v.json]
tests/quarantine/emitter_parity_surface.txt:22:tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/video/wan_t2v.json]
tests/quarantine/emitter_parity_surface.txt:23:tests/test_porting_ui_emitter.py::test_offline_parity_never_imports_comfy
tests/test_porting_ui_emitter.py:500:def test_corpus_roundtrip_parity_with_compile_api() -> None:
tests/test_porting_ui_emitter.py:891:def test_offline_parity_gate_green_on_starter_set(path: str) -> None:
tests/test_porting_ui_emitter.py:904:def test_offline_parity_never_imports_comfy() -> None:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
tests/edgecases/test_backward_compat.py
tests/edgecases/test_concurrency.py
tests/edgecases/test_determinism.py
tests/edgecases/test_json_formats.py
tests/edgecases/test_model_assets.py
tests/edgecases/test_multi_output.py
tests/edgecases/test_pack_drift.py
tests/edgecases/test_runtime_failures.py
tests/edgecases/test_subgraph_corners.py
tests/edgecases/test_type_system.py
tests/fixtures/b02_corpus_mini/001cd1f527f7f288.layout.json
tests/fixtures/b02_corpus_mini/42188130f0d8021b.json
tests/fixtures/b02_corpus_mini/90a1d5ff9044902e.json
tests/fixtures/b02_corpus_mini/bbb556b30438a62c.json
tests/live_agentic_harness/intent_judge.py
tests/parity/test_independent_readback.py
tests/security/test_agent_context_boundary.py
tests/security/test_ingest_provenance.py
tests/security/test_integration.py
tests/test_agent_edit_safety.py
tests/test_b02_rich_preservation.py
tests/test_codemod_hypothesis.py
tests/test_comfy_roundtrip_route.py
tests/test_compile_invariance.py
tests/test_demo_factory_structural_baseline.py
tests/test_emitted_artifacts_open.py
tests/test_exec_normalize.py
tests/test_finalize_metadata.py
tests/test_ingest_external_workflows.py
tests/test_ingest_snapshot.py
tests/test_intent_nodes.py
tests/test_layer4_smoke.py
tests/test_layout_delta.py
tests/test_metadata_registration.py
tests/test_porting_edit_session.py
tests/test_porting_emitter.py
tests/test_porting_normalize_ingest.py
tests/test_porting_ui_emitter.py
tests/test_position_fidelity.py
tests/test_ready_templates.py
tests/test_reconcile.py
tests/test_run_command.py
tests/test_schema.py
tests/test_schema_validate.py
tests/test_subgraph_emission_contract.py
tests/test_ui_emitter_parity.py
tests/test_ui_emitter_widget_shape_verdict.py
tests/test_walking_skeleton.py
tests/test_workflow_core.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
tests/test_foundation_utils.py
tests/test_layout_store.py
tests/test_patches.py
tests/test_porting_normalize_ingest.py
tests/test_porting_synthetic_fixtures.py
tests/test_porting_ui_emitter.py
tests/test_schema_validate.py
tests/test_ui_layout.py
tests/test_workflow_core.py

exec
/bin/zsh -lc "nl -ba tests/quarantine/emitter_parity_surface.txt | sed -n '1,30p' && nl -ba tests/conftest.py | sed -n '350,455p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '480,525p' && nl -ba tests/test_porting_ui_emitter.py | sed -n '870,925p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
     1	# owner: emitter-parity-surface
     2	# reason: pre-existing emitter, parity, snapshot, and workflow-lens failures from the legacy baseline
     3	# audit: migrated from tests/known_failures.txt during sprint-3 diagnostics T7
     4	
     5	tests/parity/test_independent_readback.py::test_independent_readback_corpus
     6	tests/test_api_surface.py::test_public_module_all_snapshots_are_intentional
     7	tests/test_porting_emitter.py::test_emit_ready_template_python_has_ready_metadata_contract
     8	tests/test_porting_emitter.py::test_generated_template_not_formatted_missing_section_comments
     9	tests/test_porting_emitter.py::test_ready_template_build_spacing_for_multiline_and_packed_simple_calls
    10	tests/test_porting_emitter.py::test_ready_template_emits_unpacking_for_typed_multi_output_node
    11	tests/test_porting_emitter.py::test_ready_template_keeps_dead_multi_output_node_as_bare_call
    12	tests/test_porting_emitter.py::test_ready_template_replaces_dead_unpacked_outputs_with_underscore
    13	tests/test_porting_emitter.py::test_ready_template_unpacked_output_names_use_collision_suffix
    14	tests/test_porting_normalize_ingest.py::test_compile_api_byte_identical_with_and_without_mode
    15	tests/test_porting_ui_emitter.py::test_corpus_roundtrip_parity_with_compile_api
    16	tests/test_porting_ui_emitter.py::test_ksampler_none_widget_alignment_roundtrips
    17	tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json]
    18	tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/edit/qwen_image_edit.json]
    19	tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/image/flux2_klein_4b_t2i.json]
    20	tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/image/z_image.json]
    21	tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/video/wan_i2v.json]
    22	tests/test_porting_ui_emitter.py::test_offline_parity_gate_green_on_starter_set[ready_templates/sources/official/video/wan_t2v.json]
    23	tests/test_porting_ui_emitter.py::test_offline_parity_never_imports_comfy
    24	tests/test_ready_templates.py::test_ltx_lightricks_first_last_parity_exposes_worker_patch_points
    25	tests/test_ready_templates.py::test_snapshotted_ready_template_graph_matches_pre_refactor_api[edit/flux2_klein_4b_image_edit_distilled]
    26	tests/test_ready_templates.py::test_snapshotted_ready_template_graph_matches_pre_refactor_api[edit/qwen_image_edit]
    27	tests/test_ready_templates.py::test_snapshotted_ready_template_graph_matches_pre_refactor_api[image/flux2_klein_4b_t2i]
    28	tests/test_ready_templates.py::test_snapshotted_ready_template_graph_matches_pre_refactor_api[image/flux2_klein_9b_gguf_t2i]
    29	tests/test_ready_templates.py::test_snapshotted_ready_template_graph_matches_pre_refactor_api[image/z_image]
    30	tests/test_ready_templates.py::test_snapshotted_ready_template_graph_matches_pre_refactor_api[video/ltx2_3_i2v]
   350	        )
   351	        return
   352	    flaky_marker = pytest.mark.flaky(reruns=1, reruns_delay=10)
   353	    for item in items:
   354	        if "runpod" in item.keywords or "runpod_full" in item.keywords:
   355	            item.add_marker(flaky_marker)
   356	
   357	
   358	def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config) -> None:
   359	    """Exit non-zero only when there are NEW failures not in scoped quarantine files.
   360	
   361	    Tests that are already in the by-design-red baseline are silently accepted.
   362	    A rising set (test IDs not in the baseline) is the real regression signal.
   363	
   364	    When ``--known-failures-audit`` is passed, also report STALE entries in
   365	    ``tests/quarantine/*.txt`` that no longer map to any collected test ID.
   366	    """
   367	    try:
   368	        quarantine = _load_quarantine_index()
   369	    except ValueError as exc:
   370	        terminalreporter.write_sep("=", "QUARANTINE CONFIG ERROR", red=True)
   371	        terminalreporter.write_line(str(exc), red=True)
   372	        terminalreporter._session.exitstatus = 1  # type: ignore[attr-defined]
   373	        return
   374	
   375	    # --- Stale-failures audit (independent of exit status) ---
   376	    if config.getoption("--known-failures-audit", default=False):
   377	        if quarantine:
   378	            collected_ids = {item.nodeid for item in terminalreporter.stats.get("passed", [])}
   379	            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("failed", []))
   380	            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("skipped", []))
   381	            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("xfailed", []))
   382	            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("xpassed", []))
   383	            # Also try to get the full collected set from the session
   384	            session = terminalreporter._session  # type: ignore[attr-defined]
   385	            if hasattr(session, "items"):
   386	                collected_ids.update(item.nodeid for item in session.items)
   387	            stale = sorted(set(quarantine) - collected_ids)
   388	            if stale:
   389	                terminalreporter.write_sep("=", "STALE FAILURES / QUARANTINES (not collected)", yellow=True)
   390	                for nodeid in stale:
   391	                    entry = quarantine[nodeid]
   392	                    terminalreporter.write_line(
   393	                        f"  STALE: {nodeid} [{entry.display_path}; owner={entry.owner}]",
   394	                        yellow=True,
   395	                    )
   396	                terminalreporter.write_line(
   397	                    f"{len(stale)} stale quarantine entry(s) — remove or update the owning file.",
   398	                    yellow=True,
   399	                )
   400	            else:
   401	                terminalreporter.write_line(
   402	                    f"quarantine audit: all {len(quarantine)} entry(s) map to collected tests.",
   403	                    green=True,
   404	                )
   405	
   406	    # --- New-failures gate ---
   407	    stats = terminalreporter.stats
   408	    failed_items = stats.get("failed", [])
   409	    if not failed_items:
   410	        return
   411	
   412	    new_failures = [
   413	        rep.nodeid for rep in failed_items if rep.nodeid not in quarantine
   414	    ]
   415	    tolerated_failures = [
   416	        rep.nodeid for rep in failed_items if rep.nodeid in quarantine
   417	    ]
   418	
   419	    if tolerated_failures:
   420	        terminalreporter.write_sep("=", "TOLERATED QUARANTINED FAILURES", yellow=True)
   421	        for nodeid in sorted(tolerated_failures):
   422	            entry = quarantine[nodeid]
   423	            terminalreporter.write_line(
   424	                f"  TOLERATED FAIL: {nodeid} [{entry.display_path}; owner={entry.owner}]",
   425	                yellow=True,
   426	            )
   427	
   428	    if new_failures:
   429	        terminalreporter.write_sep("=", "NEW FAILURES (not quarantined)", red=True)
   430	        for nodeid in sorted(new_failures):
   431	            terminalreporter.write_line(f"  NEW FAIL: {nodeid}", red=True)
   432	        terminalreporter.write_line(
   433	            f"{len(new_failures)} new failure(s) detected — add a scoped tests/quarantine/*.txt entry only if intentional.",
   434	            red=True,
   435	        )
   436	        # Force a non-zero exit even if pytest would otherwise consider only known failures
   437	        terminalreporter._session.exitstatus = 1  # type: ignore[attr-defined]
   438	    else:
   439	        known_count = len(failed_items)
   440	        terminalreporter.write_line(
   441	            f"All {known_count} failure(s) are quarantined baseline failures. No regressions.",
   442	            green=True,
   443	        )
   444	        # Reset exit status so CI gates pass when failures are all known-baseline.
   445	        terminalreporter._session.exitstatus = 0  # type: ignore[attr-defined]
   480	    wf.edges.append(VibeEdge("1", "0", "2", "text"))
   481	    with warnings.catch_warnings():
   482	        warnings.simplefilter("ignore")
   483	        node = next(n for n in emit_ui_json(wf)["nodes"] if n["id"] == 2)
   484	    slot = node["inputs"][0]
   485	    assert slot["name"] == "text"
   486	    assert slot["widget"] == {"name": "text"}
   487	    assert node["widgets_values"] == []  # linked widget removed from array
   488	
   489	
   490	def test_schema_less_node_skips_length_check() -> None:
   491	    wf = _wf()
   492	    wf.nodes["1"] = VibeNode("1", "TotallyUnknownNode", widgets={"widget_0": 5})
   493	    report: list[dict] = []
   494	    with warnings.catch_warnings():
   495	        warnings.simplefilter("ignore")
   496	        emit_ui_json(wf, recovery_report=report)
   497	    assert "skipped" in report[0]["widget_length_check"]
   498	
   499	
   500	def test_corpus_roundtrip_parity_with_compile_api() -> None:
   501	    """The parity oracle: _normalize_ui_to_api(emit_ui_json(wf)) is compile_equivalent
   502	    to wf.compile('api') for every UI-shaped official corpus workflow."""
   503	    import glob
   504	
   505	    from vibecomfy.ingest.normalize import _normalize_ui_to_api, from_ui
   506	    from vibecomfy.porting.parity import compile_equivalent
   507	
   508	    paths = sorted(glob.glob("ready_templates/sources/official/**/*.json", recursive=True))
   509	    checked = 0
   510	    for path in paths:
   511	        with open(path) as handle:
   512	            raw = json.load(handle)
   513	        if not isinstance(raw.get("nodes"), list):
   514	            continue
   515	        wf = from_ui(raw)
   516	        with warnings.catch_warnings():
   517	            warnings.simplefilter("ignore")
   518	            ui = emit_ui_json(wf)
   519	        api = wf.compile("api")
   520	        equal, diffs = compile_equivalent(_normalize_ui_to_api(ui), api)
   521	        assert equal, f"{path}: {diffs[:5]}"
   522	        checked += 1
   523	    assert checked > 0
   524	
   525	
   870	# ---------------------------------------------------------------------------
   871	# T8 — offline parity gate + structural validation
   872	# ---------------------------------------------------------------------------
   873	
   874	_STARTER_SET = [
   875	    "ready_templates/sources/official/image/z_image.json",
   876	    "ready_templates/sources/official/image/flux2_klein_4b_t2i.json",
   877	    "ready_templates/sources/official/video/wan_t2v.json",
   878	    "ready_templates/sources/official/video/wan_i2v.json",
   879	    "ready_templates/sources/official/edit/qwen_image_edit.json",
   880	    "ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json",
   881	]
   882	
   883	
   884	def _local_provider():
   885	    from vibecomfy.schema import get_schema_provider
   886	
   887	    return get_schema_provider("local")
   888	
   889	
   890	@pytest.mark.parametrize("path", _STARTER_SET)
   891	def test_offline_parity_gate_green_on_starter_set(path: str) -> None:
   892	    """compile_equivalent(_normalize_ui_to_api(emit_ui_json(wf)), compile('api')) — never
   893	    imports ComfyUI — is green for a >=5 starter set spanning image/video/edit."""
   894	    from vibecomfy.ingest.normalize import from_ui
   895	    from vibecomfy.porting.emit.ui import offline_emitter_normalizer_self_consistency_check
   896	
   897	    with open(path) as handle:
   898	        raw = json.load(handle)
   899	    wf = from_ui(raw)
   900	    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
   901	    assert ok, f"{path}: {diffs[:5]}"
   902	
   903	
   904	def test_offline_parity_never_imports_comfy() -> None:
   905	    """The offline gate must not import ComfyUI. Build the IR first (ingest itself may
   906	    probe comfy with an ImportError fallback), then poison ``comfy`` imports *only*
   907	    around offline_emitter_normalizer_self_consistency_check and assert it still runs green."""
   908	    import builtins
   909	
   910	    from vibecomfy.ingest.normalize import from_ui
   911	    from vibecomfy.porting.emit.ui import offline_emitter_normalizer_self_consistency_check
   912	
   913	    with open("ready_templates/sources/official/video/wan_t2v.json") as handle:
   914	        raw = json.load(handle)
   915	    wf = from_ui(raw)
   916	    provider = _local_provider()
   917	
   918	    real_import = builtins.__import__
   919	
   920	    def _poisoned(name, *args, **kwargs):
   921	        if name == "comfy" or name.startswith("comfy."):
   922	            raise AssertionError(f"offline parity gate imported ComfyUI module {name!r}")
   923	        return real_import(name, *args, **kwargs)
   924	
   925	    builtins.__import__ = _poisoned

exec
/bin/zsh -lc "rg -n \"input_refs|edges_in\" vibecomfy/porting/emit/emit_subgraph.py | head -80 && nl -ba vibecomfy/porting/emit/emit_subgraph.py | sed -n '500,575p' && nl -ba vibecomfy/porting/emit/emit_subgraph.py | sed -n '650,750p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 17ms:
   650	    subgraph: _SubgraphDef,
   651	    edges_in: dict[str, list[Any]],
   652	    var_names: dict[str, str],
   653	    output_var_names: dict[str, dict[int, str]],
   654	    workflow_nodes: dict[str, Any],
   655	    *,
   656	    body_indent: str,
   657	    continuation_indent: str,
   658	    diagnostics: list[EmissionDiagnostic] | None,
   659	) -> list[str]:
   660	    live_output_slots = _live_output_slots_for_function(
   661	        workflow_nodes,
   662	        edges_in,
   663	        output_var_names,
   664	    )
   665	    assignment_target = _assignment_target(
   666	        var_names[str(node.id)],
   667	        output_var_names.get(str(node.id)),
   668	        live_slots=live_output_slots.get(str(node.id)),
   669	    )
   670	    kwargs = _subgraph_call_kwargs(
   671	        node,
   672	        subgraph,
   673	        edges_in,
   674	        var_names,
   675	        output_var_names,
   676	        workflow_nodes,
   677	        diagnostics=diagnostics,
   678	    )
   679	    kwarg_lines = [f"{key}={expr}" for key, expr in kwargs]
   680	    call_expr = f"{subgraph.slug}({', '.join(kwarg_lines)})"
   681	    single_line = (
   682	        f"{body_indent}{assignment_target} = {call_expr}"
   683	        if assignment_target is not None
   684	        else f"{body_indent}{call_expr}"
   685	    )
   686	    if len(kwargs) > 3 or len(single_line) > 88:
   687	        head = f"{body_indent}{subgraph.slug}(" if assignment_target is None else f"{body_indent}{assignment_target} = {subgraph.slug}("
   688	        lines = [head]
   689	        for key, expr in kwargs:
   690	            lines.append(f"{continuation_indent}{key}={expr},")
   691	        lines.append(f"{body_indent})")
   692	        return lines
   693	    return [single_line]
   694	def _subgraph_call_kwargs(
   695	    node: Any,
   696	    subgraph: _SubgraphDef,
   697	    edges_in: dict[str, list[Any]],
   698	    var_names: dict[str, str],
   699	    output_var_names: dict[str, dict[int, str]],
   700	    workflow_nodes: dict[str, Any],
   701	    *,
   702	    diagnostics: list[EmissionDiagnostic] | None,
   703	) -> list[tuple[str, str]]:
   704	    incoming: dict[str, tuple[str, int]] = {}
   705	    for edge in edges_in.get(str(node.id), []):
   706	        incoming[str(edge.to_input)] = (str(edge.from_node), int(edge.from_output))
   707	    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
   708	        if _is_link(value):
   709	            incoming.setdefault(str(key), (str(value[0]), int(value[1])))
   710	
   711	    static = {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}
   712	    widget_values = _subgraph_instance_widget_values(node)
   713	    port_candidate_names = _subgraph_instance_port_candidate_names(node, subgraph)
   714	    kwargs: list[tuple[str, str]] = []
   715	    for index, port in enumerate(subgraph.inputs):
   716	        if port.external_ref is not None:
   717	            src, slot = port.external_ref
   718	            kwargs.append(
   719	                (
   720	                    port.name,
   721	                    _edge_ref_expr(
   722	                        workflow_nodes,
   723	                        var_names,
   724	                        output_var_names,
   725	                        src,
   726	                        slot,
   727	                        bare_single_output_refs=True,
   728	                        diagnostics=diagnostics,
   729	                        target_node=node,
   730	                        target_input=port.name,
   731	                    ),
   732	                )
   733	            )
   734	            continue
   735	        candidate_names = port_candidate_names.get(index, (port.name, port.source_name or port.name))
   736	        incoming_name = next((name for name in candidate_names if name in incoming), None)
   737	        widget_name = next((name for name in candidate_names if name in widget_values), None)
   738	        static_name = next((name for name in candidate_names if name in static), None)
   739	        default_name = next((name for name in candidate_names if name in subgraph.default_args), None)
   740	        if incoming_name is not None:
   741	            src, slot = incoming[incoming_name]
   742	            kwargs.append(
   743	                (
   744	                    port.name,
   745	                    _edge_ref_expr(
   746	                        workflow_nodes,
   747	                        var_names,
   748	                        output_var_names,
   749	                        src,
   750	                        slot,

exec
/bin/zsh -lc "rg -n \"external_refs\" vibecomfy/porting/emit -g '*.py' && nl -ba vibecomfy/porting/emitter.py | sed -n '1640,1775p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/porting/emit/emit_subgraph.py:32:    _edges_in_with_subgraph_external_refs,
vibecomfy/porting/emit/emit_subgraph.py:549:                external_refs=subgraph.input_refs,
vibecomfy/porting/emit/emit_prepare.py:33:    _edges_in_with_subgraph_external_refs,
vibecomfy/porting/emit/emit_prepare.py:306:    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
vibecomfy/porting/emit/emit_ready.py:80:    _edges_in_with_subgraph_external_refs,
vibecomfy/porting/emit/emit_ready.py:682:    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
vibecomfy/porting/emit/emit_ready.py:954:    external_refs: dict[tuple[str, str], str] | None = None,
vibecomfy/porting/emit/emit_ready.py:965:    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
vibecomfy/porting/emit/emit_ready.py:1107:            external_refs=external_refs,
vibecomfy/porting/emit/emit_kwargs.py:57:    "_edges_in_with_subgraph_external_refs",
vibecomfy/porting/emit/emit_kwargs.py:615:def _edges_in_with_subgraph_external_refs(
vibecomfy/porting/emit/emit_kwargs.py:1133:    external_refs: dict[tuple[str, str], str] | None = None,
vibecomfy/porting/emit/emit_kwargs.py:1162:    if external_refs is None:
vibecomfy/porting/emit/emit_kwargs.py:1163:        external_refs = {}
vibecomfy/porting/emit/emit_kwargs.py:1184:                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
vibecomfy/porting/emit/emit_kwargs.py:1197:                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/emit_kwargs.py | sed -n '1125,1215p' && nl -ba vibecomfy/porting/emit/emit_ready.py | sed -n '940,985p' && nl -ba vibecomfy/porting/emit/emit_ready.py | sed -n '1085,1120p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
  1125	    diagnostics: "list[Any] | None" = None,
  1126	    constant_map: dict[tuple[str, str], str] | None = None,
  1127	    use_ui_widget_aliases: bool = False,
  1128	    strip_schema_defaults: bool = False,
  1129	    omit_single_output_metadata: bool = False,
  1130	    bare_single_output_refs: bool = False,
  1131	    emit_reserved_keyword_args: bool = False,
  1132	    preserve_fields: set[str] | None = None,
  1133	    external_refs: dict[tuple[str, str], str] | None = None,
  1134	) -> list[tuple[str, str]]:
  1135	    # Lazy imports to avoid circular dependency
  1136	    from vibecomfy.porting.emitter import (  # noqa: PLC0415
  1137	        RESERVED_WRAPPER_INPUT_NAMES,
  1138	        _ui_widget_aliases,
  1139	        READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
  1140	        EmissionDiagnostic,
  1141	    )
  1142	
  1143	    cls = node.class_type
  1144	    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
  1145	    schema_set = set(schema)
  1146	
  1147	    # Per-node widget alias metadata populated by the schema provider during
  1148	    # from_api.  Prefer this over the static WIDGET_SCHEMA so
  1149	    # that schema-source evidence wins - the static table is only a fallback.
  1150	    node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
  1151	    input_aliases: list[str | None] | None = None
  1152	    compact_names = compact_widget_names_for_node(node, cls).names
  1153	    if compact_names:
  1154	        input_aliases = list(compact_names)
  1155	    elif use_ui_widget_aliases:
  1156	        input_aliases = _ui_widget_aliases(node)
  1157	
  1158	    if constant_map is None:
  1159	        constant_map = {}
  1160	    if preserve_fields is None:
  1161	        preserve_fields = set()
  1162	    if external_refs is None:
  1163	        external_refs = {}
  1164	
  1165	    incoming: dict[str, tuple[str, int]] = {}
  1166	    incoming_exprs: dict[str, str] = {}
  1167	    for edge in edges_in.get(node.id, []):
  1168	        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))
  1169	
  1170	    def _translate_widget(key: str, value: Any = None) -> str | None:
  1171	        if key.startswith("unused_widget_"):
  1172	            return None
  1173	        if cls == "Power Lora Loader (rgthree)":
  1174	            return _translate_power_lora_loader_widget(key, value)
  1175	        if not key.startswith("widget_"):
  1176	            return key
  1177	        return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name
  1178	
  1179	    raw_inputs: dict[str, Any] = {}
  1180	    for key, value in node.inputs.items():
  1181	        if _is_any_link(value) and str(value[0]) == "-10":
  1182	            translated_link = _translate_widget(key, value)
  1183	            if translated_link is not None:
  1184	                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
  1185	                if expr is not None:
  1186	                    incoming_exprs[translated_link] = expr
  1187	        elif _is_link(value):
  1188	            translated_link = _translate_widget(key, value)
  1189	            if translated_link is not None:
  1190	                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
  1191	        else:
  1192	            raw_inputs[key] = value
  1193	    for key, value in node.widgets.items():
  1194	        if _is_any_link(value) and str(value[0]) == "-10":
  1195	            translated_link = _translate_widget(key, value)
  1196	            if translated_link is not None:
  1197	                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
  1198	                if expr is not None:
  1199	                    incoming_exprs[translated_link] = expr
  1200	        elif _is_link(value):
  1201	            translated_link = _translate_widget(key, value)
  1202	            if translated_link is not None:
  1203	                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
  1204	        elif key not in raw_inputs:
  1205	            raw_inputs[key] = value
  1206	
  1207	    static_inputs: dict[str, Any] = {}
  1208	    for key, value in raw_inputs.items():
  1209	        translated = _translate_widget(key, value)
  1210	        if translated is None:
  1211	            continue
  1212	        value = _resolve_graph_field_get_string(value, workflow_nodes)
  1213	        if translated != key and translated not in raw_inputs and translated not in static_inputs:
  1214	            if translated not in incoming and translated not in incoming_exprs:
  1215	                static_inputs[translated] = value
   940	    source_path_expr: str,
   941	    source_type: str,
   942	    source_provenance: dict[str, Any] | None,
   943	    registered_inputs: dict[str, tuple[str, str]] | None,
   944	    public_inputs: list[_PublicInputSpec] | None,
   945	    tail_lines: list[str],
   946	    diagnostics: list[Any] | None = None,
   947	    use_shared_helpers: bool = False,
   948	    constant_map: dict[tuple[str, str], str] | None = None,
   949	    section_groups: dict[str, list[str]] | None = None,
   950	    function_name: str = "build",
   951	    function_signature: str | None = None,
   952	    function_docstring: list[str] | None = None,
   953	    return_refs: tuple[tuple[str, int], ...] = (),
   954	    external_refs: dict[tuple[str, str], str] | None = None,
   955	    node_id_prefix: str | None = None,
   956	    required_ids: set[str] | None = None,
   957	) -> list[str]:
   958	    from vibecomfy.porting.emitter import (  # noqa: PLC0415
   959	        EmissionDiagnostic,
   960	        READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
   961	        READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
   962	    )
   963	    workflow_nodes = prepared["nodes"]
   964	    edges_in = prepared["edges_in"]
   965	    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
   966	    var_names = prepared["var_names"]
   967	    output_var_names = prepared.get("output_var_names", {}) if use_shared_helpers else {}
   968	
   969	    if constant_map is None:
   970	        constant_map = {}
   971	    if section_groups is None:
   972	        section_groups = {}
   973	    var_to_nid = {var: nid for nid, var in var_names.items()}
   974	    for output_nid, slot_vars in output_var_names.items():
   975	        for output_var in slot_vars.values():
   976	            var_to_nid[str(output_var)] = str(output_nid)
   977	    live_output_slots = _live_output_slots_for_function(
   978	        workflow_nodes,
   979	        ordering_edges_in,
   980	        output_var_names,
   981	        return_refs=return_refs,
   982	        tail_lines=tail_lines,
   983	    )
   984	    public_preserve_fields: dict[str, set[str]] = {}
   985	    for spec in public_inputs or []:
  1085	            out_lines.append(f"{body_indent}# {section}")
  1086	            emitted_sections.add(section)
  1087	
  1088	        wrapper_module = _wrapper_module_for_class(str(node.class_type)) if use_shared_helpers else None
  1089	        preserve_fields = {
  1090	            field
  1091	            for old_id, field in (registered_inputs or {}).values()
  1092	            if old_id == nid
  1093	        }
  1094	        preserve_fields.update(public_preserve_fields.get(nid, set()))
  1095	        kwargs = _node_kwargs(
  1096	            node, edges_in, var_names,
  1097	            workflow_nodes=workflow_nodes,
  1098	            output_var_names=output_var_names,
  1099	            diagnostics=diagnostics,
  1100	            constant_map=constant_map,
  1101	            use_ui_widget_aliases=use_shared_helpers,
  1102	            strip_schema_defaults=use_shared_helpers,
  1103	            omit_single_output_metadata=use_shared_helpers,
  1104	            bare_single_output_refs=use_shared_helpers,
  1105	            emit_reserved_keyword_args=wrapper_module is not None,
  1106	            preserve_fields=preserve_fields,
  1107	            external_refs=external_refs,
  1108	        )
  1109	
  1110	        if use_shared_helpers:
  1111	            subgraph = (prepared.get("subgraph_definitions") or {}).get(str(node.class_type))
  1112	            if subgraph is not None:
  1113	                stmt_lines = _emit_subgraph_call_statement(
  1114	                    node,
  1115	                    subgraph,
  1116	                    edges_in,
  1117	                    var_names,
  1118	                    output_var_names,
  1119	                    workflow_nodes,
  1120	                    body_indent=body_indent,

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/ui.py | sed -n '2170,2240p' && rg -n \"order_list =\" vibecomfy/porting/emit/ui.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
  2170	
  2171	    # Build ChangeReport if the caller requested it via change_report_out.
  2172	    _change_report_ref: list = []  # mutable container so we can set stripped_helpers later
  2173	    if change_report_out is not None:
  2174	        from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
  2175	        from vibecomfy.porting.layout.reconcile import build_change_report  # noqa: PLC0415
  2176	        _snapshot = (wf.metadata or {}).get("_ingest_snapshot", {})
  2177	        _field_delta = compute_field_delta(_snapshot, wf) if _snapshot else {}
  2178	        _report = build_change_report(
  2179	            reconcile_result,
  2180	            _field_delta,
  2181	            prior_store_entries=_prior_store.get("entries"),
  2182	        )
  2183	        change_report_out.append(_report)
  2184	        _change_report_ref.append(_report)
  2185	
  2186	    # ── Resolve broadcast helpers (SetNode / GetNode) into direct edges ────
  2187	    # effective_edges: direct links for the EXECUTION (flat) graph
  2188	    # broadcast_ids: SetNode/GetNode node ids to drop from flat graph
  2189	    # orphaned_get_ids: GetNode ids whose broadcast name has no SetNode source
  2190	    effective_edges, broadcast_ids, orphaned_get_ids = _resolve_broadcast_edges(wf)
  2191	
  2192	    # Collect the full set of virtual-wire node ids (broadcast + Reroute)
  2193	    reroute_ids = {
  2194	        node_id
  2195	        for node_id, node in wf.nodes.items()
  2196	        if node.class_type == "Reroute"
  2197	    }
  2198	    virtual_wire_ids: set[str] = broadcast_ids | reroute_ids
  2199	
  2200	    # Populate stripped_helpers on the change report (now that virtual_wire_ids is computed).
  2201	    if _change_report_ref:
  2202	        _change_report_ref[0].content_edits.stripped_helpers = sorted(virtual_wire_ids) if virtual_wire_ids else []
  2203	
  2204	    # ── Choose edge list and node filter based on virtual-wire toggle ───────
  2205	    if include_virtual_wires:
  2206	        # DISPLAY mode: keep all nodes, use ALL original edges (helpers visible)
  2207	        order_list = _emission_order(wf)
  2208	        display_edges = list(wf.edges)
  2209	    else:
  2210	        # EXECUTION (flat) mode: drop virtual-wire nodes, resolve edges
  2211	        order_list = [
  2212	            nid for nid in _emission_order(wf) if nid not in virtual_wire_ids
  2213	        ]
  2214	        # First resolve broadcast indirection, then passthrough Reroutes
  2215	        flat_edges = _resolve_reroute_edges(effective_edges, wf.nodes)
  2216	        display_edges = flat_edges
  2217	
  2218	    # Remap string node ids → litegraph integer ids (digit ids preserve their value).
  2219	    id_remap = _build_id_remap(order_list)
  2220	
  2221	    # Build schema cache (one get_schema call per unique class_type)
  2222	    schema_cache: dict[str, Any] = {}
  2223	    if schema_provider is not None:
  2224	        for node_id in order_list:
  2225	            ct = wf.nodes[node_id].class_type
  2226	            if ct not in schema_cache:
  2227	                schema_cache[ct] = schema_provider.get_schema(ct)
  2228	
  2229	    # ── Layout engine: compute fresh positions for every node ───────────────
  2230	    # T9b: reconcile-driven merge.
  2231	    #   pinned   = {uid: {pos,size} for uid in reconcile_result.matched}
  2232	    #              → engine never re-positions matched nodes.
  2233	    #   anchors  = caller-supplied anchors ∪ computed_anchors, where
  2234	    #              computed_anchors[new_uid] = nearest_wired_neighbor_uid(new_node, matched).
  2235	    #              unmatched_legacy / removed-then-readded nodes (i.e. nodes whose
  2236	    #              key is neither matched nor in reconcile_result.new but were once
  2237	    #              in the store) route through the engine WITHOUT anchors.
  2238	    from vibecomfy.porting.layout import layout as _compute_layout  # noqa: PLC0415
  2239	    from vibecomfy.porting.layout.reconcile import (  # noqa: PLC0415
  2240	        nearest_wired_neighbor_uid as _nearest_wired_neighbor_uid,
2207:        order_list = _emission_order(wf)
2211:        order_list = [

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import warnings; from vibecomfy.workflow import VibeWorkflow,WorkflowSource,VibeNode; from vibecomfy.porting.emit.ui import emit_ui_json; w=VibeWorkflow(\"x\",WorkflowSource(\"x\")); w.nodes[\"1\"]=VibeNode(\"1\",\"Source\"); w.nodes[\"2\"]=VibeNode(\"2\",\"Sink\",inputs={\"image\":[\"1\",0]}); warnings.simplefilter(\"ignore\"); u=emit_ui_json(w); print(u[\"links\"]); print([n for n in u[\"nodes\"] if n[\"id\"]==2][0].get(\"widgets_values\"))'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 4179ms:
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 
[]
[]

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -s -p no:cacheprovider tests/test_subgraph_emission_contract.py::test_subgraph_blank_labeled_input_matches_normalized_call_site_edge tests/test_subgraph_emission_contract.py::test_subgraph_external_input_edge_becomes_function_parameter' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 18611ms:
.OMP: Warning #179: Function Can't set size of /tmp file failed:
.
=============================== warnings summary ===============================
../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2 passed, 1 warning in 5.93s

codex
## Verdict: FAIL

Tasks 1–5 pass, but Task 6 has two concrete blockers.

1. [emit_subgraph.py:292](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/emit_subgraph.py:292) and [emit_subgraph.py:340](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/emit_subgraph.py:340) still store connectivity pairs in real `VibeNode.inputs`.

   `_build_subgraph_def()` preserves and manufactures `["-10", slot]` boundary links. I reproduced a returned `VibeNode` containing `{'switch': ['-10', 0]}`. The narrow canonical predicate excludes negative `-10`, so all new invariant guards miss this connectivity representation. This directly violates “all package-owned low-level construction” and “VibeEdge sole connectivity authority.”

2. [ui.py:2043](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/ui.py:2043) does not fail closed during UI serialization.

   Given `VibeNode(inputs={"image": ["1", 0]})` without an edge, `emit_ui_json()` succeeds and emits `links=[]`, silently erasing the illegal embedded connectivity. Task 6 explicitly requires fail-closed behavior outside ingestion during serialization. The emitter needs the same invariant preflight, with raw-link and collision tests.

Task-6 functionality that does pass:

- `from_api()` normalizes canonical pairs into `VibeEdge` and removes them from `node.inputs`.
- Validation, envelope decoding/serialization, and compilation reject embedded canonical links.
- Identical and conflicting raw-link/edge collisions fail explicitly during compilation.
- Edge-only compilation is non-mutating.
- Canonical API/envelope round trips and narrow literal-list behavior pass.

I independently ran 12 focused connectivity/mode/group cases successfully, plus two existing subgraph-emission tests. Those tests currently do not enforce the missed subgraph invariant.

## Tasks 1–5: PASS

- Compile and emit share `_get_node_mode()`, with only the retained `_ui.mode` fallback.
- No `groups` emitter parameter or call remains.
- Selected preserve-store groups are deep-copied into `workflow.groups`.
- Group aliases remap through final LiteGraph integers; stale and ambiguous members are omitted without mutating the IR.
- IR groups precede engine groups with title deduplication.
- `write_layout()` serializes `wf.groups`.

## Parity ruling

Record the identified parity failures as a known pre-existing gap. They do not block this run’s release gate provided the gate is baseline-relative: no new, unquarantined, or worsened failures versus `0f515870`.

The repository already labels these node IDs as legacy-baseline failures and explicitly makes CI fail only for new failures.

One bookkeeping correction: I cannot ratify the count “9” as written. The three named families collect eight test items total, and direct baseline/HEAD checks show three failing items among them—two starter parameters plus the corpus test. Exact node IDs are needed for any additional six claimed failures. This does not change the pre-existing attribution of the observed failures.

Also, `8a8300bb..0d2bb176` is diff-check clean; the requested broader `ec13a34e..0d2bb176` range is not, due to trailing whitespace in the approved generated check-in document. No files were edited.
tokens used
305,009
## Verdict: FAIL

Tasks 1–5 pass, but Task 6 has two concrete blockers.

1. [emit_subgraph.py:292](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/emit_subgraph.py:292) and [emit_subgraph.py:340](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/emit_subgraph.py:340) still store connectivity pairs in real `VibeNode.inputs`.

   `_build_subgraph_def()` preserves and manufactures `["-10", slot]` boundary links. I reproduced a returned `VibeNode` containing `{'switch': ['-10', 0]}`. The narrow canonical predicate excludes negative `-10`, so all new invariant guards miss this connectivity representation. This directly violates “all package-owned low-level construction” and “VibeEdge sole connectivity authority.”

2. [ui.py:2043](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/ui.py:2043) does not fail closed during UI serialization.

   Given `VibeNode(inputs={"image": ["1", 0]})` without an edge, `emit_ui_json()` succeeds and emits `links=[]`, silently erasing the illegal embedded connectivity. Task 6 explicitly requires fail-closed behavior outside ingestion during serialization. The emitter needs the same invariant preflight, with raw-link and collision tests.

Task-6 functionality that does pass:

- `from_api()` normalizes canonical pairs into `VibeEdge` and removes them from `node.inputs`.
- Validation, envelope decoding/serialization, and compilation reject embedded canonical links.
- Identical and conflicting raw-link/edge collisions fail explicitly during compilation.
- Edge-only compilation is non-mutating.
- Canonical API/envelope round trips and narrow literal-list behavior pass.

I independently ran 12 focused connectivity/mode/group cases successfully, plus two existing subgraph-emission tests. Those tests currently do not enforce the missed subgraph invariant.

## Tasks 1–5: PASS

- Compile and emit share `_get_node_mode()`, with only the retained `_ui.mode` fallback.
- No `groups` emitter parameter or call remains.
- Selected preserve-store groups are deep-copied into `workflow.groups`.
- Group aliases remap through final LiteGraph integers; stale and ambiguous members are omitted without mutating the IR.
- IR groups precede engine groups with title deduplication.
- `write_layout()` serializes `wf.groups`.

## Parity ruling

Record the identified parity failures as a known pre-existing gap. They do not block this run’s release gate provided the gate is baseline-relative: no new, unquarantined, or worsened failures versus `0f515870`.

The repository already labels these node IDs as legacy-baseline failures and explicitly makes CI fail only for new failures.

One bookkeeping correction: I cannot ratify the count “9” as written. The three named families collect eight test items total, and direct baseline/HEAD checks show three failing items among them—two starter parameters plus the corpus test. Exact node IDs are needed for any additional six claimed failures. This does not change the pre-existing attribution of the observed failures.

Also, `8a8300bb..0d2bb176` is diff-check clean; the requested broader `ec13a34e..0d2bb176` range is not, due to trailing whitespace in the approved generated check-in document. No files were edited.
6e97450a PASS — Batch D+E (emit authority, groups, VibeEdge) after rework
