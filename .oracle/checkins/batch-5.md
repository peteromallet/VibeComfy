Reading additional input from stdin...
2026-08-13T20:40:02.555805Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T20:40:02.555846Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T20:40:02.555853Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffcda-71d8-7112-a62e-164f2a3c24b9
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 5 — review Batch K (Declare the workflow context token + collision-safe UID minting).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 2ddd1f06 (Batch C). Batch K commit: 06d94e4a530e67ac72fd805c20b302b83666e963. Review `git diff 2ddd1f06..HEAD` (ignore the 11c788bf checkpoint-record commit's .oracle whitespace).

## Batch K tasks + acceptance gate (frozen tasklist.md incl. your oracle-approved task 4)
(1) _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False). (2) Replace token getattr/hasattr/creation/deletion with direct access. (3) copy() deepcopy memo mapping active contextvars.Token to None — every clone unbound. (4) Collision-safe unseeded UID minting: reconcile _uid_counter with existing flat n<positive-integer> auto-minted uids, choose next unoccupied n<N>; preserve imported uids verbatim; monotonic; no parallel registry / no id: redesign.

Gate: bound+unbound copies token None; constructor/repr/equality/envelope omit field; enter/exit/eager reuse/finalize/nesting rejection/exception cleanup/async isolation pass; no token leak into serialization; after decoding envelope with uid=n1 (incl. sparse n1/n5/n100), new nodes get distinct uids beyond imported auto-minted range; repeated mints+copies monotonic; nonmatching imported uids unchanged.

## Host-verified evidence
- Agent (Flash) verification: 679 passed / 2 failed / 2 skipped; 2 failures = FileNotFoundError external_workflows/corpus/90a1d5ff9044902e.json (environmental missing corpus, identical at pristine HEAD 11c788bf); test_templates_module 5 failures pre-exist at baseline. git diff --check clean. Only vibecomfy/workflow.py changed.
- Acceptance claimed met: token field declared; __enter__/__exit__ direct access; copy() memo pre-seeds {id(token): None}; _mint_uid calls _reconcile_uid_counter() before unseeded mints (raises counter to largest existing n<N>, never lowers); imported uids preserved (42, id:abc, explicit-uid, n7 unchanged); sparse n1/n5/n100 case mints beyond.

## Your verdict
Binary PASS or concrete issues (file:line). Verify the diff + the two acceptance surfaces. Do NOT edit. Read-only.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megaplan` skill because this is an explicit Megado oracle checkpoint; I’ll follow its review/gating instructions and remain read-only.
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

exec
/bin/zsh -lc "sed -n '241,520p' /Users/peteromalley/.codex/skills/megaplan/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
`chain.yaml` and declares it through `anchors.north_star`. Edit it before
`chain start`. Chain runs require this top-level North Star by default. Use it
for the durable destination and milestone briefs for local scope. Opt out only
with `--no-require-anchor --missing-anchor-ack "<reason>"` or matching
`driver.require_anchor: false` plus `driver.missing_anchor_ack` in the spec.

`<launcher> init --idea-file <path>` reads the file and snapshots its text; it does
not move arbitrary files into the retired `.megaplan/briefs/` tree. If the idea file is a markdown
artifact with YAML frontmatter, `init` snapshots only the markdown body. Use
`<launcher> brief new --init` to create the canonical source file first and then
initialize from it.

Inspect captured anchors with:

```bash
<launcher> anchors show --plan <name> [--json]
```

## Feedback
See **megaplan-prep** for when to add the feedback phase (`--with-feedback`). This section covers the CLI mechanics once you've decided to use it.

`<launcher> feedback --plan <name>` scaffolds a `feedback.md` file in the plan directory and opens it in `$EDITOR` (or `$VISUAL`). The file has one section per workflow stage — `prep`, `plan`, `critique`, `revise`, `gate`, `tiebreaker`, `finalize`, `execute`, `review` — plus an `Overall` section. Each section has a `rating:` (integer 0–10) and a free-form `comment:` field; leave any field blank to skip it.

This is **user feedback**, owned by the human after a run finishes — megaplan only scaffolds the template and parses it back on load, it never overwrites edits. Old plans without a `feedback.md` simply have no feedback attached; running `<launcher> feedback --plan <name>` on an older plan scaffolds the template on demand (backwards compatible).

Use `<launcher> feedback show --plan <name>` to print the parsed summary, and `--no-edit` to just scaffold the template and print the path without launching an editor. Parsed feedback is exposed on the in-memory `Plan` record as `Plan.feedback` (a dict shaped `{"overall": {...}, "stages": {stage: {...}}}`), so downstream tooling can read it the same way as any other artifact. When `--actor`/`MEGAPLAN_ACTOR_ID` is set, parsed feedback is also written to the `plans.feedback` jsonb column so the DB and file backends stay in sync.

### Filling feedback with subagents
Recommended process when an agent (rather than the human) is producing the initial assessment:

1. **Scaffold**: run `<launcher> feedback --plan <name> --no-edit` to create the empty `feedback.md`. Note the plan directory it prints — that is where the per-stage artifacts live (`plan_v*.md`, `critique*.json`, `gate.json`, `tiebreaker_*.json`, `finalize.json`, `execution*.json`, `review.json`, etc.).
2. **Per-stage assessment**: dispatch one read-only subagent per stage that actually ran (skip stages with no artifacts). Brief each subagent narrowly — give it the plan idea, the stage name, and the artifact filenames for that stage only. Ask it to return a 0–10 rating plus a 1–3 sentence comment grounded in what the artifacts show (what worked, what was weak, what was missed). Run these in parallel; they have no dependencies on each other.
3. **Synthesize Overall**: after the per-stage results come back, *you* (the orchestrating agent, not a subagent) read the per-stage ratings and comments together with the final outcome (`final.md`, `review.json`, any `latest_failure`) and decide an Overall rating and comment. The Overall is a judgment call about whether the run delivered the goal, not an average of stage ratings.
4. **Write**: edit `feedback.md` with the ratings and comments. Leave a stage blank if it didn't run or you can't form a defensible opinion — empty is better than guessed. Run `<launcher> feedback show --plan <name>` to confirm the parser picked everything up.

Keep comments grounded in specific artifact evidence ("critique flagged X but reviewer didn't catch the regression in Y") rather than vibes. The point of feedback is signal for future runs, not a participation score.

### Searching feedback across plans
`<launcher> feedback search` queries every plan with non-empty feedback across both backends — local `feedback.md` files in this project tree plus, when an actor is configured, the `plans.feedback` jsonb column in the DB. Duplicates between backends are de-duped by (plan name, project_dir). Use this to answer "which profile actually scored well on this repo?" or "where did the executor get a 6 or below?". Filters:
- `--profile <substr>` — substring match on the plan's profile (e.g. `--profile claude` matches `all-claude`, `claude-led`, etc.).
- `--repo <substr>` — substring match on the plan's `project_dir` / repo path.
- `--min-rating N` / `--max-rating N` — bounds on the Overall rating.
- `--stage <name>` — only plans that recorded a rating for that stage (`plan`, `critique`, `execute`, …).
- `--has-comment` — only plans whose Overall comment is non-empty.
- `--all` — scan every megaplan project root on this machine, not just the current tree.
- `--json` — emit raw rows instead of a table.

Default output is a compact table (plan, profile, overall rating, backend, repo, plus the first line of the Overall comment). Combine with `<launcher> feedback show --plan <name>` to drill into a specific match.
## Observability
Plans started after this layer landed write an append-only `events.ndjson` event journal to their plan dir. Four CLI surfaces read from it; reach for them whenever a run is in flight or you need to reconstruct what happened. See the **megaplan-observe** skill for the full failure-mode catalog and worked invocation chains.

- `<launcher> introspect --plan <name>` — single structured-JSON snapshot. Always check this first when something looks stuck; the `active_phase.liveness` enum (`progressing | quiet | stalled | timeout-imminent`) and `block_details.recoverable_via` together tell you whether to wait, intervene, or override. Also surfaces `outstanding_flags_count`, useful when a plan is sitting on unresolved critique signals.
- `<launcher> trace --plan <name> [--follow] [--format json|pretty|narrative] [--phase <p>] [--since <duration>]` — stream events. `narrative` format is the agent-facing affordance; `--follow` tails as the plan progresses; `--phase` and `--since` filter. Prints `trace: no events.ndjson for plan <name>` cleanly when a plan predates the journal.
- `<launcher> doctor [--plan <name> | --repo]` — diagnostic. `--repo` catches rubric/binary drift (skill profile names vs `profiles list`) and editable-install dirtiness *before* `<launcher> init`, so reach for it after a branch switch / pull / fresh checkout. `--plan` reports lock, phase liveness, LLM liveness, cost-vs-cap, orphan subprocesses, and outstanding flags.
- `<launcher> record-tag --plan <name> --tag <name> --note "..."` — annotate a moment in the journal so later trace/introspect calls can find it. All three args are required.

Stale-timestamp inference, opaque blocked state, and "model thinking vs TCP wedged" are the three confusions this layer is designed to kill — if you find yourself running `lsof`, `ps`, or doing manual `ls -lat` time math on a plan dir, you should be running `introspect` or `trace` instead.
## Commands
```bash
<launcher> status --plan <name>
<launcher> progress --plan <name>
<launcher> audit --plan <name>
<launcher> list
<launcher> prep --plan <name>
<launcher> plan --plan <name>
<launcher> critique --plan <name>
<launcher> revise --plan <name>
<launcher> gate --plan <name>
<launcher> finalize --plan <name>
<launcher> execute --plan <name> --confirm-destructive [--batch N]
<launcher> review --plan <name>
<launcher> step add --plan <name> [--after S<N>] "description"
<launcher> step remove --plan <name> S<N>
<launcher> step move --plan <name> S<N> --after S<M>
<launcher> override add-note --plan <name> --note "..."
<launcher> override force-proceed --plan <name> --reason "..."
<launcher> override replan --plan <name> --reason "..." [--note "..."]
<launcher> override abort --plan <name> --reason "..."
<launcher> config show
<launcher> config set <key> <value>
<launcher> config reset
<launcher> config profiles list
<launcher> config profiles show <name>
<launcher> bakeoff run --idea-file <path> --profiles <p1> <p2> [--mode code|doc|metaplan] [--output <relative/path>] [--exp-id <id>] [--detach] [--robustness <level>] [--allow-dirty]
<launcher> bakeoff status [--exp <id>]
<launcher> bakeoff tail [--exp <id>]
<launcher> bakeoff compare --exp <id> [--judge <model>]
<launcher> bakeoff pick --exp <id> --profile <name> --rationale "..."
<launcher> bakeoff merge --exp <id>
<launcher> bakeoff resume --exp <id>
<launcher> bakeoff abandon --exp <id>
<launcher> brief new <slug> [-b <body> | --from <path> | -] [--force] [--init]
<launcher> brief epic <slug> --milestone LABEL=TITLE [--base-branch <branch>] [--force]
<launcher> brief list [--json]
<launcher> brief show <id-or-path> [--json]
<launcher> brief search [KW ...] [--all] [--sort path|title|length] [--desc] [--limit N] [--json]
<launcher> ticket new "title" -b "body"
<launcher> ticket list [--status <s>] [--tags <t>] [--json]
<launcher> ticket show <id> [--json]
<launcher> ticket edit <id> [--title <t>] [--body <b>] [--status <s>]
<launcher> ticket link <ticket> <epic> [--resolves]
<launcher> ticket unlink <ticket> <epic>
<launcher> ticket addressed <id> [--note <n>]
<launcher> ticket dismiss <id> --reason "..."
<launcher> ticket reopen <id>
<launcher> feedback show --plan <name> [--no-edit]
<launcher> feedback search [--profile <s>] [--repo <s>] [--min-rating N] [--max-rating N] [--stage <name>] [--has-comment] [--all] [--json]
<launcher> introspect --plan <name> [--json]
<launcher> trace --plan <name> [--follow] [--format json|pretty|narrative] [--phase <p>] [--since <duration>]
<launcher> doctor [--plan <name> | --repo]
<launcher> record-tag --plan <name> --tag <name> --note "..."
```


<!-- Source of truth for Codex-specific subagent orchestration. Appended only to the Codex skill via bundled_global_file('codex_skill.md'). -->
## Subagent Mode
This appendix is Codex-specific. It adds only the orchestration delta for Codex. The base skill remains the workflow source of truth.

### Activation
- Default to subagent unless an inline override is explicit for this run or `megaplan config show` reports `"orchestration": {"mode": "inline"}`.
- Prefer subagent for long multi-phase runs where keeping the outer conversation clean matters.
- Prefer inline for small edits, quick clarifications, or when the user wants to watch each phase in the main thread.

### Tool Mapping
- `spawn_agent`: launch the autonomous megaplan runner.
- `wait_agent`: wait for either a breakpoint or completion.
- `resume_agent`: reopen the orchestrator after a breakpoint.
- `send_input`: resume after a breakpoint, or interrupt a still-running agent when the user needs an immediate change.
- `close_agent`: hard-stop a stuck orchestrator before relaunching.

### Launch
When subagent mode is active, the outer skill becomes a launcher plus breakpoint relay. Start a Codex subagent with:
- `agent_type`: `default`
- `model`: prefer `gpt-5.4` when available
- `reasoning_effort`: `high`
- `fork_context`: `false` unless the current thread contains important constraints that are not restated in the prompt
- `message`: fill the template below with `{IDEA}`, `{PROJECT_DIR}`, `{AUTO_APPROVE}`, `{AUTO_APPROVE_FLAG}`, and `{ROBUSTNESS_FLAG}`
- Expand `{AUTO_APPROVE_FLAG}` to an empty string when `raw_config.execution.auto_approve` is explicitly set; otherwise expand it to `--auto-approve` for auto-approve runs and an empty string for review runs.
- Expand `{ROBUSTNESS_FLAG}` to an empty string when `raw_config.execution.robustness` is explicitly set; otherwise expand it to `--robustness {ROBUSTNESS}`.
- After editing this source file, rerun `megaplan setup --force` so installed `SKILL.md` files pick up the refreshed appendix.

### Outer Skill Rules
- Decide inline vs subagent before starting the workflow.
- Launch once, remember the spawned agent id, then `wait_agent` for a final message that starts with either `BREAKPOINT:` or `COMPLETE:`.
- Parse only the explicit first header line when deciding whether the stop was intentional.
- If a breakpoint arrives, relay it to the user, collect the answer, then `resume_agent` and `send_input` to the same agent.
- If the user adds context while the subagent is running, default to `megaplan override add-note --plan <name> --note "..."` and let the next phase boundary pick it up.
- If the user needs an immediate redirect, add the note first, then `send_input` with `interrupt: true` telling the orchestrator to rerun `megaplan status`, read all notes, and continue from the current state.
- If the orchestrator is stuck, `close_agent`, add a note, and relaunch a new subagent with a resume prompt on the same plan.

### Agent Prompt Template
```text
You are the autonomous megaplan runner for this single run.

Project: {PROJECT_DIR}
Idea: {IDEA}
Execution mode: {AUTO_APPROVE}

Operate through the `megaplan` CLI only. Do not call workers or agents directly.
Use the same verified `<launcher>` for every CLI call in this run. Verify it with a successful harmless CLI call first; command presence alone is not enough.

Startup:
1. Run `<launcher> init --project-dir "{PROJECT_DIR}" {AUTO_APPROVE_FLAG} {ROBUSTNESS_FLAG} "{IDEA}"`.
2. Capture the returned plan name.
3. Output `PLAN_NAME: <name>` on its own line before any `BREAKPOINT:` or `COMPLETE:`.
4. Run `<launcher> status --plan <name>`.
5. If `status` reports anchors, run `<launcher> anchors show --plan <name>` once and treat the captured North Star as durable alignment context.

Routing:
- Use `next_step` and `valid_next` from `<launcher> status --plan <name>` for every move.
- Trust CLI state over memory.
- If `notes_count > 0`, read the full `notes` array before acting.
- After each step, read `next_step_runtime.duration_hint` and `next_step_runtime.recommended_next_check_seconds` when present to calibrate the next status check.
- For `bare`: `plan -> finalize -> execute`.
- For `light`: `plan -> critique -> revise -> finalize -> execute`.
- For `full` (legacy: `standard`), `thorough` (legacy: `robust`), or `extreme` (legacy: `superrobust`): follow the base skill workflow, including `prep`, `gate`, `review`, and any revise/rework loops.
- Build on top of uncommitted changes in the working tree by default; only override if they directly contradict the plan.
- After `gate`, follow `orchestrator_guidance` unless repository evidence proves it wrong.

Breakpoints:
- Stop only for `GATE_ESCALATE`, `GATE_BLOCKED`, `EXECUTE_APPROVAL`, `PHASE_ESCALATE`, or `EXECUTE_ESCALATE`.
- Format every breakpoint exactly as:
  `BREAKPOINT: <type>`
  `Plan: <name>`
  `State: <state>`
  `Summary: <short reason>`
  `Context: <artifacts, warnings, or the exact user decision needed>`

Safeguards:
- Retry a non-execute phase once with `--fresh` before escalating.
- If `execute` makes no forward progress for 3 attempts, stop with `BREAKPOINT: EXECUTE_ESCALATE`.
- Treat `review` returning `needs_rework` as a normal branch, not a breakpoint.

Completion:
- When the run finishes, return exactly:
  `COMPLETE: megaplan run finished`
  `Plan: <name>`
  `Final state: <state>`
  `Summary: <outcome>`
  `Artifacts: <key files or reports>`
  `Follow-up: <only if something remains>`
```

codex
The skill’s execution workflow is not applicable here because the Megado run already exists and you asked only for an oracle review. I’ll inspect the specified commit range, implementation invariants, and focused tests without invoking or mutating the run.
exec
/bin/zsh -lc 'git status --short --branch && git log --oneline --decorate -8 && git diff --stat 2ddd1f06..HEAD && git diff --check 2ddd1f06..HEAD && git diff 2ddd1f06..HEAD -- vibecomfy/workflow.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## elegance-run2
?? .oracle/checkins/batch-5.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
06d94e4a (HEAD -> elegance-run2) megado run2 Batch K: declare _workflow_context_token, direct field access, copy memo for bound workflows, collision-safe unseeded UID minting
11c788bf megado run2: record Batch C checkpoint PASS
2ddd1f06 megado run2 Batch C: first-class VibeNode.pos/.size — mint at ingest, decode precedence, 6 descents replaced, stub-layout preserved
5795812e megado run2: record Batch D+E checkpoint PASS
6e97450a megado run2 Batch D+E rework (oracle issues): subgraph boundary links to VibeEdge, emit fails closed on embedded links
0d2bb176 megado run2 Batch D+E: IR-authoritative emission — mode via node.mode only, groups kwarg removed + member-ID remap, wf.groups reconciled, VibeEdge sole connectivity authority
8a8300bb megado run2: oracle-approved plan adjustments — D+E#6 VibeEdge sole connectivity authority, K#4 collision-safe UID minting
ec13a34e megado run2 Batch B: remove convert_to_vibe_format — migrate 15 callers to named importers, guard test, scratchpad emits from_api
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-4.md | 10633 ++++++++++++++++++++++++++++++++++++++++++
 vibecomfy/workflow.py       |    49 +-
 2 files changed, 10668 insertions(+), 14 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-4.md:171: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:173: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:175: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:177: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:179: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:181: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:183: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:185: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:187: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:189: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:191: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:193: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:195: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:197: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:199: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:201: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:203: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:205: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:207: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:209: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:211: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:213: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:215: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:217: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:219: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:221: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:223: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:225: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:227: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:229: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:231: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:233: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:235: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:237: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:239: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:241: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:243: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:245: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:247: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:249: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:251: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:253: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:255: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:257: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:259: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:261: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:263: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:265: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:267: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:269: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:271: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:273: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:275: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:277: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:279: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:281: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:283: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:285: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:287: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:289: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:291: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:293: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:295: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:297: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:299: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:301: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:303: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:305: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:307: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:309: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:311: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:313: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:315: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:317: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:319: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:321: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:323: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:325: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:327: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:329: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:331: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:333: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:335: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:337: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:339: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:341: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:343: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:345: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:347: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:349: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:351: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:353: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:355: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:357: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:359: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:361: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:363: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:365: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:367: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:369: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:371: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:373: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:375: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:377: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:379: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:381: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:383: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:385: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:387: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:389: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:391: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:393: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:395: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:397: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:399: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:401: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:403: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:405: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:407: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:409: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:411: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:413: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:415: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:417: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:419: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:421: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:423: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:425: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:427: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:429: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:431: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:433: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:435: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:437: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:439: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:441: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:443: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:445: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:447: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:449: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:451: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:453: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:455: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:457: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:459: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:461: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:463: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:465: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:467: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:469: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:471: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:473: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:475: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:477: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:479: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:481: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:483: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:485: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:487: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:489: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:491: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:493: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:495: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:497: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:499: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:501: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:503: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:505: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:507: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:509: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:511: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:513: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:515: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:517: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:519: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:521: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:523: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:525: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:527: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:529: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:531: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:533: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:535: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:537: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:539: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:541: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:543: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:545: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:547: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:549: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:551: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:553: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:555: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:557: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:559: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:561: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:563: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:565: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:567: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:569: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:571: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:573: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:575: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:577: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:579: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:581: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:583: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:585: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:587: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:589: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:591: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:593: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:595: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:597: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:599: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:601: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:603: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:605: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:607: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:609: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:611: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:613: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:615: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:617: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:619: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:621: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:623: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:625: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:627: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:629: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:631: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:633: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:635: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:637: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:639: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:641: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:643: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:645: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:647: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:649: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:651: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:653: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:655: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:657: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:659: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:661: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:663: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:665: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:667: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:669: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:671: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:673: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:675: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:677: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:679: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:681: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:683: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:685: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:687: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:689: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:691: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:693: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:695: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:697: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:699: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:701: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:703: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:705: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:707: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:709: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:711: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:713: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:715: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:717: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:719: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:721: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:723: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:725: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:727: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:729: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:731: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:733: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:735: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:737: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:739: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:741: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:743: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:745: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:747: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:749: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:751: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:753: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:755: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:757: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:759: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:761: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:763: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:765: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:767: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:769: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:771: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:773: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:775: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:777: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:779: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:781: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:783: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:785: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:787: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:789: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:791: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:793: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:795: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:797: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:799: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:801: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:803: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:805: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:807: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:809: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:811: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:813: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:815: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:817: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:819: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:821: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:823: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:825: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:827: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:829: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:831: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:833: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:835: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:837: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:839: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:841: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:843: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:845: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:847: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:849: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:851: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:853: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:855: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:857: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:859: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:861: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:863: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:865: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:867: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:869: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:871: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:873: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:875: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:877: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:879: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:881: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:883: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:885: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:887: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:889: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:891: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:893: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:895: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:897: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:899: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:901: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:903: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:905: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:907: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:909: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:911: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:913: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:915: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:917: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:919: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:921: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:923: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:925: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:927: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:929: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:931: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:933: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:935: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:937: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:939: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:941: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:943: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:945: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:947: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:949: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:951: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:953: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:955: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:957: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:959: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:961: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:963: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:965: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:967: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:969: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:971: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:973: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:975: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:977: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:979: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:981: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:983: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:985: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:987: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:989: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:991: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:993: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:995: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:997: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:999: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1001: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1003: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1005: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1007: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1009: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1011: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1013: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1015: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1017: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1019: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1021: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1023: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1025: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1027: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1029: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1031: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1033: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1035: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1037: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1039: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1041: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1043: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1045: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1047: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1049: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1051: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1053: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1055: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1057: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1059: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1061: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1063: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1065: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1067: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1069: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1071: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1073: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1075: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1077: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1079: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1081: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1083: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1085: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1087: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1089: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1091: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1093: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1095: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1097: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1099: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1101: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1103: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1105: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1107: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1109: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1111: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1113: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1115: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1117: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1119: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1121: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1123: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1125: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1127: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1129: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1131: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1133: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1135: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1137: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1139: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1141: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1143: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1145: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1147: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1149: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1151: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1153: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1155: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1157: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1159: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1161: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1163: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1165: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1167: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1169: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1171: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1173: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1175: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1177: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1179: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1181: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1183: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1185: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1187: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1189: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1191: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1193: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1195: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1197: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1199: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1201: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1203: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1205: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1207: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1209: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1211: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1213: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1215: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1217: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1219: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1221: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1223: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1225: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1227: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1229: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1231: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1233: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1235: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1237: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1239: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1241: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1243: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:1245: trailing whitespace.
++++   719	
.oracle/checkins/batch-4.md:1247: trailing whitespace.
++++   726	
.oracle/checkins/batch-4.md:1249: trailing whitespace.
++++   728	
.oracle/checkins/batch-4.md:1251: trailing whitespace.
++++   730	
.oracle/checkins/batch-4.md:1253: trailing whitespace.
++++   731	
.oracle/checkins/batch-4.md:1255: trailing whitespace.
++++   734	
.oracle/checkins/batch-4.md:1257: trailing whitespace.
++++   740	
.oracle/checkins/batch-4.md:1259: trailing whitespace.
++++   741	
.oracle/checkins/batch-4.md:1261: trailing whitespace.
++++   769	
.oracle/checkins/batch-4.md:1263: trailing whitespace.
++++   770	
.oracle/checkins/batch-4.md:1265: trailing whitespace.
++++   786	
.oracle/checkins/batch-4.md:1267: trailing whitespace.
++++   787	
.oracle/checkins/batch-4.md:1269: trailing whitespace.
++++   794	
.oracle/checkins/batch-4.md:1271: trailing whitespace.
++++   795	
.oracle/checkins/batch-4.md:1273: trailing whitespace.
++++   829	
.oracle/checkins/batch-4.md:1275: trailing whitespace.
++++   830	
.oracle/checkins/batch-4.md:1277: trailing whitespace.
++++     2	
.oracle/checkins/batch-4.md:1279: trailing whitespace.
++++     6	
.oracle/checkins/batch-4.md:1281: trailing whitespace.
++++     7	
.oracle/checkins/batch-4.md:1283: trailing whitespace.
++++    14	
.oracle/checkins/batch-4.md:1285: trailing whitespace.
++++    15	
.oracle/checkins/batch-4.md:1287: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:1289: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:1291: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:1293: trailing whitespace.
+++++    15	
.oracle/checkins/batch-4.md:1295: trailing whitespace.
+++++    31	
.oracle/checkins/batch-4.md:1297: trailing whitespace.
+++++    35	
.oracle/checkins/batch-4.md:1299: trailing whitespace.
+++++    37	
.oracle/checkins/batch-4.md:1301: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:1303: trailing whitespace.
+++++    43	
.oracle/checkins/batch-4.md:1305: trailing whitespace.
+++++    45	
.oracle/checkins/batch-4.md:1307: trailing whitespace.
+++++    53	
.oracle/checkins/batch-4.md:1309: trailing whitespace.
+++++    58	
.oracle/checkins/batch-4.md:1311: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:1313: trailing whitespace.
+++++    65	
.oracle/checkins/batch-4.md:1315: trailing whitespace.
+++++    66	
.oracle/checkins/batch-4.md:1317: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:1319: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:1321: trailing whitespace.
+++++    83	
.oracle/checkins/batch-4.md:1323: trailing whitespace.
+++++    84	
.oracle/checkins/batch-4.md:1325: trailing whitespace.
+++++    88	
.oracle/checkins/batch-4.md:1327: trailing whitespace.
+++++    89	
.oracle/checkins/batch-4.md:1329: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:1331: trailing whitespace.
+++++    98	
.oracle/checkins/batch-4.md:1333: trailing whitespace.
+++++   110	
.oracle/checkins/batch-4.md:1335: trailing whitespace.
+++++   111	
.oracle/checkins/batch-4.md:1337: trailing whitespace.
+++++   116	
.oracle/checkins/batch-4.md:1339: trailing whitespace.
+++++   117	
.oracle/checkins/batch-4.md:1341: trailing whitespace.
+++++   135	
.oracle/checkins/batch-4.md:1343: trailing whitespace.
+++++   136	
.oracle/checkins/batch-4.md:1345: trailing whitespace.
+++++   149	
.oracle/checkins/batch-4.md:1347: trailing whitespace.
+++++   150	
.oracle/checkins/batch-4.md:1349: trailing whitespace.
+++++   163	
.oracle/checkins/batch-4.md:1351: trailing whitespace.
+++++   164	
.oracle/checkins/batch-4.md:1353: trailing whitespace.
+++++   173	
.oracle/checkins/batch-4.md:1355: trailing whitespace.
+++++   174	
.oracle/checkins/batch-4.md:1357: trailing whitespace.
+++++   180	
.oracle/checkins/batch-4.md:1359: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:1361: trailing whitespace.
+++++   191	
.oracle/checkins/batch-4.md:1363: trailing whitespace.
+++++   192	
.oracle/checkins/batch-4.md:1365: trailing whitespace.
+++++   198	
.oracle/checkins/batch-4.md:1367: trailing whitespace.
+++++   199	
.oracle/checkins/batch-4.md:1369: trailing whitespace.
+++++   206	
.oracle/checkins/batch-4.md:1371: trailing whitespace.
+++++   207	
.oracle/checkins/batch-4.md:1373: trailing whitespace.
+++++   223	
.oracle/checkins/batch-4.md:1375: trailing whitespace.
+++++   224	
.oracle/checkins/batch-4.md:1377: trailing whitespace.
+++++   228	
.oracle/checkins/batch-4.md:1379: trailing whitespace.
+++++   229	
.oracle/checkins/batch-4.md:1381: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:1383: trailing whitespace.
+++++   233	
.oracle/checkins/batch-4.md:1385: trailing whitespace.
+++++   237	
.oracle/checkins/batch-4.md:1387: trailing whitespace.
+++++   238	
.oracle/checkins/batch-4.md:1389: trailing whitespace.
+++++   242	
.oracle/checkins/batch-4.md:1391: trailing whitespace.
+++++   243	
.oracle/checkins/batch-4.md:1393: trailing whitespace.
+++++   250	
.oracle/checkins/batch-4.md:1395: trailing whitespace.
+++++   251	
.oracle/checkins/batch-4.md:1397: trailing whitespace.
+++++   254	
.oracle/checkins/batch-4.md:1399: trailing whitespace.
+++++   271	
.oracle/checkins/batch-4.md:1401: trailing whitespace.
+++++   275	
.oracle/checkins/batch-4.md:1403: trailing whitespace.
+++++   278	
.oracle/checkins/batch-4.md:1405: trailing whitespace.
+++++   288	
.oracle/checkins/batch-4.md:1407: trailing whitespace.
+++++   307	
.oracle/checkins/batch-4.md:1409: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:1411: trailing whitespace.
+++++   324	
.oracle/checkins/batch-4.md:1413: trailing whitespace.
+++++   336	
.oracle/checkins/batch-4.md:1415: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:1417: trailing whitespace.
+++++     8	
.oracle/checkins/batch-4.md:1419: trailing whitespace.
+++++    10	
.oracle/checkins/batch-4.md:1421: trailing whitespace.
+++++    21	
.oracle/checkins/batch-4.md:1423: trailing whitespace.
+++++    24	
.oracle/checkins/batch-4.md:1425: trailing whitespace.
+++++    25	
.oracle/checkins/batch-4.md:1427: trailing whitespace.
+++++    28	
.oracle/checkins/batch-4.md:1429: trailing whitespace.
+++++    29	
.oracle/checkins/batch-4.md:1431: trailing whitespace.
+++++    55	
.oracle/checkins/batch-4.md:1433: trailing whitespace.
+++++    56	
.oracle/checkins/batch-4.md:1435: trailing whitespace.
+++++    61	
.oracle/checkins/batch-4.md:1437: trailing whitespace.
+++++    62	
.oracle/checkins/batch-4.md:1439: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:1441: trailing whitespace.
+++++    72	
.oracle/checkins/batch-4.md:1443: trailing whitespace.
+++++    79	
.oracle/checkins/batch-4.md:1445: trailing whitespace.
+++++    80	
.oracle/checkins/batch-4.md:1447: trailing whitespace.
+++++    94	
.oracle/checkins/batch-4.md:1449: trailing whitespace.
+++++    95	
.oracle/checkins/batch-4.md:1451: trailing whitespace.
+++++   102	
.oracle/checkins/batch-4.md:1453: trailing whitespace.
+++++   104	
.oracle/checkins/batch-4.md:1455: trailing whitespace.
+++++   111	
.oracle/checkins/batch-4.md:1457: trailing whitespace.
+++++   113	
.oracle/checkins/batch-4.md:1459: trailing whitespace.
+++++   119	
.oracle/checkins/batch-4.md:1461: trailing whitespace.
+++++   128	
.oracle/checkins/batch-4.md:1463: trailing whitespace.
+++++   140	
.oracle/checkins/batch-4.md:1465: trailing whitespace.
+++++   162	
.oracle/checkins/batch-4.md:1467: trailing whitespace.
+++++   171	
.oracle/checkins/batch-4.md:1469: trailing whitespace.
+++++   201	
.oracle/checkins/batch-4.md:1471: trailing whitespace.
+++++   202	
.oracle/checkins/batch-4.md:1473: trailing whitespace.
+++++   214	
.oracle/checkins/batch-4.md:1475: trailing whitespace.
+++++   215	
.oracle/checkins/batch-4.md:1477: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:1479: trailing whitespace.
+++++   245	
.oracle/checkins/batch-4.md:1481: trailing whitespace.
+++++   248	
.oracle/checkins/batch-4.md:1483: trailing whitespace.
+++++   266	
.oracle/checkins/batch-4.md:1485: trailing whitespace.
+++++   313	
.oracle/checkins/batch-4.md:1487: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:1489: trailing whitespace.
+++++   335	
.oracle/checkins/batch-4.md:1491: trailing whitespace.
+++++   339	
.oracle/checkins/batch-4.md:1493: trailing whitespace.
+++++   360	
.oracle/checkins/batch-4.md:1495: trailing whitespace.
+++++   361	
.oracle/checkins/batch-4.md:1497: trailing whitespace.
+++++   385	
.oracle/checkins/batch-4.md:1499: trailing whitespace.
+++++   386	
.oracle/checkins/batch-4.md:1501: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1503: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1505: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1507: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1509: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1511: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1513: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1515: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1517: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1519: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1521: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1523: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1525: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1527: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1529: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1531: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1533: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1535: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1537: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1539: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1541: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1543: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1545: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1547: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1549: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1551: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1553: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1555: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1557: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1559: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1561: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1563: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1565: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1567: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1569: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:1571: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:1573: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:1575: trailing whitespace.
+++++    15	
.oracle/checkins/batch-4.md:1577: trailing whitespace.
+++++    31	
.oracle/checkins/batch-4.md:1579: trailing whitespace.
+++++    35	
.oracle/checkins/batch-4.md:1581: trailing whitespace.
+++++    37	
.oracle/checkins/batch-4.md:1583: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:1585: trailing whitespace.
+++++    43	
.oracle/checkins/batch-4.md:1587: trailing whitespace.
+++++    45	
.oracle/checkins/batch-4.md:1589: trailing whitespace.
+++++    53	
.oracle/checkins/batch-4.md:1591: trailing whitespace.
+++++    58	
.oracle/checkins/batch-4.md:1593: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:1595: trailing whitespace.
+++++    65	
.oracle/checkins/batch-4.md:1597: trailing whitespace.
+++++    66	
.oracle/checkins/batch-4.md:1599: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:1601: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:1603: trailing whitespace.
+++++    83	
.oracle/checkins/batch-4.md:1605: trailing whitespace.
+++++    84	
.oracle/checkins/batch-4.md:1607: trailing whitespace.
+++++    88	
.oracle/checkins/batch-4.md:1609: trailing whitespace.
+++++    89	
.oracle/checkins/batch-4.md:1611: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:1613: trailing whitespace.
+++++    98	
.oracle/checkins/batch-4.md:1615: trailing whitespace.
+++++   110	
.oracle/checkins/batch-4.md:1617: trailing whitespace.
+++++   111	
.oracle/checkins/batch-4.md:1619: trailing whitespace.
+++++   116	
.oracle/checkins/batch-4.md:1621: trailing whitespace.
+++++   117	
.oracle/checkins/batch-4.md:1623: trailing whitespace.
+++++   135	
.oracle/checkins/batch-4.md:1625: trailing whitespace.
+++++   136	
.oracle/checkins/batch-4.md:1627: trailing whitespace.
+++++   149	
.oracle/checkins/batch-4.md:1629: trailing whitespace.
+++++   150	
.oracle/checkins/batch-4.md:1631: trailing whitespace.
+++++   163	
.oracle/checkins/batch-4.md:1633: trailing whitespace.
+++++   164	
.oracle/checkins/batch-4.md:1635: trailing whitespace.
+++++   173	
.oracle/checkins/batch-4.md:1637: trailing whitespace.
+++++   174	
.oracle/checkins/batch-4.md:1639: trailing whitespace.
+++++   180	
.oracle/checkins/batch-4.md:1641: trailing whitespace.
+++++   180	
.oracle/checkins/batch-4.md:1643: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:1645: trailing whitespace.
+++++   191	
.oracle/checkins/batch-4.md:1647: trailing whitespace.
+++++   192	
.oracle/checkins/batch-4.md:1649: trailing whitespace.
+++++   198	
.oracle/checkins/batch-4.md:1651: trailing whitespace.
+++++   199	
.oracle/checkins/batch-4.md:1653: trailing whitespace.
+++++   206	
.oracle/checkins/batch-4.md:1655: trailing whitespace.
+++++   207	
.oracle/checkins/batch-4.md:1657: trailing whitespace.
+++++   223	
.oracle/checkins/batch-4.md:1659: trailing whitespace.
+++++   224	
.oracle/checkins/batch-4.md:1661: trailing whitespace.
+++++   228	
.oracle/checkins/batch-4.md:1663: trailing whitespace.
+++++   229	
.oracle/checkins/batch-4.md:1665: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:1667: trailing whitespace.
+++++   233	
.oracle/checkins/batch-4.md:1669: trailing whitespace.
+++++   237	
.oracle/checkins/batch-4.md:1671: trailing whitespace.
+++++   238	
.oracle/checkins/batch-4.md:1673: trailing whitespace.
+++++   242	
.oracle/checkins/batch-4.md:1675: trailing whitespace.
+++++   243	
.oracle/checkins/batch-4.md:1677: trailing whitespace.
+++++   250	
.oracle/checkins/batch-4.md:1679: trailing whitespace.
+++++   251	
.oracle/checkins/batch-4.md:1681: trailing whitespace.
+++++   254	
.oracle/checkins/batch-4.md:1683: trailing whitespace.
+++++   271	
.oracle/checkins/batch-4.md:1685: trailing whitespace.
+++++   275	
.oracle/checkins/batch-4.md:1687: trailing whitespace.
+++++   278	
.oracle/checkins/batch-4.md:1689: trailing whitespace.
+++++   288	
.oracle/checkins/batch-4.md:1691: trailing whitespace.
+++++   307	
.oracle/checkins/batch-4.md:1693: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:1695: trailing whitespace.
+++++   324	
.oracle/checkins/batch-4.md:1697: trailing whitespace.
+++++   336	
.oracle/checkins/batch-4.md:1699: trailing whitespace.
+++++   347	
.oracle/checkins/batch-4.md:1701: trailing whitespace.
+++++   352	
.oracle/checkins/batch-4.md:1703: trailing whitespace.
+++++   374	
.oracle/checkins/batch-4.md:1705: trailing whitespace.
+++++   388	
.oracle/checkins/batch-4.md:1707: trailing whitespace.
+++++   423	
.oracle/checkins/batch-4.md:1709: trailing whitespace.
+++++   436	
.oracle/checkins/batch-4.md:1711: trailing whitespace.
+++++   462	
.oracle/checkins/batch-4.md:1713: trailing whitespace.
+++++   477	
.oracle/checkins/batch-4.md:1715: trailing whitespace.
+++++   479	
.oracle/checkins/batch-4.md:1717: trailing whitespace.
+++++   480	
.oracle/checkins/batch-4.md:1719: trailing whitespace.
+++++   486	
.oracle/checkins/batch-4.md:1721: trailing whitespace.
+++++   487	
.oracle/checkins/batch-4.md:1723: trailing whitespace.
+++++   491	
.oracle/checkins/batch-4.md:1725: trailing whitespace.
+++++   492	
.oracle/checkins/batch-4.md:1727: trailing whitespace.
+++++   507	
.oracle/checkins/batch-4.md:1729: trailing whitespace.
+++++   508	
.oracle/checkins/batch-4.md:1731: trailing whitespace.
+++++   511	
.oracle/checkins/batch-4.md:1733: trailing whitespace.
+++++   531	
.oracle/checkins/batch-4.md:1735: trailing whitespace.
+++++   532	
.oracle/checkins/batch-4.md:1737: trailing whitespace.
+++++   539	
.oracle/checkins/batch-4.md:1739: trailing whitespace.
+++++   584	
.oracle/checkins/batch-4.md:1741: trailing whitespace.
+++++   601	
.oracle/checkins/batch-4.md:1743: trailing whitespace.
+++++   613	
.oracle/checkins/batch-4.md:1745: trailing whitespace.
+++++   614	
.oracle/checkins/batch-4.md:1747: trailing whitespace.
+++++   627	
.oracle/checkins/batch-4.md:1749: trailing whitespace.
+++++   628	
.oracle/checkins/batch-4.md:1751: trailing whitespace.
+++++   632	
.oracle/checkins/batch-4.md:1753: trailing whitespace.
+++++   633	
.oracle/checkins/batch-4.md:1755: trailing whitespace.
+++++   647	
.oracle/checkins/batch-4.md:1757: trailing whitespace.
+++++   654	
.oracle/checkins/batch-4.md:1759: trailing whitespace.
+++++   655	
.oracle/checkins/batch-4.md:1761: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1763: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1765: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1767: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1769: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1771: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1773: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1775: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1777: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1779: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1781: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1783: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1785: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1787: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1789: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1791: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1793: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1795: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1797: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1799: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1801: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1803: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1805: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1807: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1809: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1811: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1813: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1815: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1817: trailing whitespace.
+++++   174	
.oracle/checkins/batch-4.md:1819: trailing whitespace.
+++++   177	
.oracle/checkins/batch-4.md:1821: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:1823: trailing whitespace.
+++++   185	
.oracle/checkins/batch-4.md:1825: trailing whitespace.
+++++   193	
.oracle/checkins/batch-4.md:1827: trailing whitespace.
+++++   196	
.oracle/checkins/batch-4.md:1829: trailing whitespace.
+++++   140	
.oracle/checkins/batch-4.md:1831: trailing whitespace.
+++++   162	
.oracle/checkins/batch-4.md:1833: trailing whitespace.
+++++   171	
.oracle/checkins/batch-4.md:1835: trailing whitespace.
+++++   201	
.oracle/checkins/batch-4.md:1837: trailing whitespace.
+++++   202	
.oracle/checkins/batch-4.md:1839: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:1841: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:1843: trailing whitespace.
+++++    77	
.oracle/checkins/batch-4.md:1845: trailing whitespace.
+++++    78	
.oracle/checkins/batch-4.md:1847: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:1849: trailing whitespace.
+++++    98	
.oracle/checkins/batch-4.md:1851: trailing whitespace.
+++++   104	
.oracle/checkins/batch-4.md:1853: trailing whitespace.
+++++   105	
.oracle/checkins/batch-4.md:1855: trailing whitespace.
+++++   113	
.oracle/checkins/batch-4.md:1857: trailing whitespace.
+++++   114	
.oracle/checkins/batch-4.md:1859: trailing whitespace.
+++++   127	
.oracle/checkins/batch-4.md:1861: trailing whitespace.
+++++   128	
.oracle/checkins/batch-4.md:1863: trailing whitespace.
+++++   142	
.oracle/checkins/batch-4.md:1865: trailing whitespace.
+++++   143	
.oracle/checkins/batch-4.md:1867: trailing whitespace.
+++++   161	
.oracle/checkins/batch-4.md:1869: trailing whitespace.
+++++   173	
.oracle/checkins/batch-4.md:1871: trailing whitespace.
+++++   176	
.oracle/checkins/batch-4.md:1873: trailing whitespace.
+++++   177	
.oracle/checkins/batch-4.md:1875: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:1877: trailing whitespace.
+++++   182	
.oracle/checkins/batch-4.md:1879: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1881: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1883: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1885: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1887: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1889: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1891: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1893: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1895: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:1897: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:1899: trailing whitespace.
+++++     8	
.oracle/checkins/batch-4.md:1901: trailing whitespace.
+++++    10	
.oracle/checkins/batch-4.md:1903: trailing whitespace.
+++++    21	
.oracle/checkins/batch-4.md:1905: trailing whitespace.
+++++    24	
.oracle/checkins/batch-4.md:1907: trailing whitespace.
+++++    25	
.oracle/checkins/batch-4.md:1909: trailing whitespace.
+++++    28	
.oracle/checkins/batch-4.md:1911: trailing whitespace.
+++++    29	
.oracle/checkins/batch-4.md:1913: trailing whitespace.
+++++    55	
.oracle/checkins/batch-4.md:1915: trailing whitespace.
+++++    56	
.oracle/checkins/batch-4.md:1917: trailing whitespace.
+++++    61	
.oracle/checkins/batch-4.md:1919: trailing whitespace.
+++++    62	
.oracle/checkins/batch-4.md:1921: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:1923: trailing whitespace.
+++++    72	
.oracle/checkins/batch-4.md:1925: trailing whitespace.
+++++    79	
.oracle/checkins/batch-4.md:1927: trailing whitespace.
+++++    80	
.oracle/checkins/batch-4.md:1929: trailing whitespace.
+++++    94	
.oracle/checkins/batch-4.md:1931: trailing whitespace.
+++++    95	
.oracle/checkins/batch-4.md:1933: trailing whitespace.
+++++   102	
.oracle/checkins/batch-4.md:1935: trailing whitespace.
+++++   104	
.oracle/checkins/batch-4.md:1937: trailing whitespace.
+++++   111	
.oracle/checkins/batch-4.md:1939: trailing whitespace.
+++++   113	
.oracle/checkins/batch-4.md:1941: trailing whitespace.
+++++   119	
.oracle/checkins/batch-4.md:1943: trailing whitespace.
+++++   128	
.oracle/checkins/batch-4.md:1945: trailing whitespace.
+++++   140	
.oracle/checkins/batch-4.md:1947: trailing whitespace.
+++++   162	
.oracle/checkins/batch-4.md:1949: trailing whitespace.
+++++   171	
.oracle/checkins/batch-4.md:1951: trailing whitespace.
+++++   201	
.oracle/checkins/batch-4.md:1953: trailing whitespace.
+++++   202	
.oracle/checkins/batch-4.md:1955: trailing whitespace.
+++++   214	
.oracle/checkins/batch-4.md:1957: trailing whitespace.
+++++   215	
.oracle/checkins/batch-4.md:1959: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:1961: trailing whitespace.
+++++   245	
.oracle/checkins/batch-4.md:1963: trailing whitespace.
+++++   248	
.oracle/checkins/batch-4.md:1965: trailing whitespace.
+++++   266	
.oracle/checkins/batch-4.md:1967: trailing whitespace.
+++++   313	
.oracle/checkins/batch-4.md:1969: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:1971: trailing whitespace.
+++++   335	
.oracle/checkins/batch-4.md:1973: trailing whitespace.
+++++   339	
.oracle/checkins/batch-4.md:1975: trailing whitespace.
+++++   360	
.oracle/checkins/batch-4.md:1977: trailing whitespace.
+++++   361	
.oracle/checkins/batch-4.md:1979: trailing whitespace.
+++++   385	
.oracle/checkins/batch-4.md:1981: trailing whitespace.
+++++   386	
.oracle/checkins/batch-4.md:1983: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:1985: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:1987: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:1989: trailing whitespace.
+++++    14	
.oracle/checkins/batch-4.md:1991: trailing whitespace.
+++++    21	
.oracle/checkins/batch-4.md:1993: trailing whitespace.
+++++    23	
.oracle/checkins/batch-4.md:1995: trailing whitespace.
+++++    27	
.oracle/checkins/batch-4.md:1997: trailing whitespace.
+++++    28	
.oracle/checkins/batch-4.md:1999: trailing whitespace.
+++++    30	
.oracle/checkins/batch-4.md:2001: trailing whitespace.
+++++    31	
.oracle/checkins/batch-4.md:2003: trailing whitespace.
+++++    35	
.oracle/checkins/batch-4.md:2005: trailing whitespace.
+++++    36	
.oracle/checkins/batch-4.md:2007: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:2009: trailing whitespace.
+++++    41	
.oracle/checkins/batch-4.md:2011: trailing whitespace.
+++++    62	
.oracle/checkins/batch-4.md:2013: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:2015: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:2017: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:2019: trailing whitespace.
+++++    77	
.oracle/checkins/batch-4.md:2021: trailing whitespace.
+++++    78	
.oracle/checkins/batch-4.md:2023: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:2025: trailing whitespace.
+++++    98	
.oracle/checkins/batch-4.md:2027: trailing whitespace.
+++++   104	
.oracle/checkins/batch-4.md:2029: trailing whitespace.
+++++   105	
.oracle/checkins/batch-4.md:2031: trailing whitespace.
+++++   113	
.oracle/checkins/batch-4.md:2033: trailing whitespace.
+++++   114	
.oracle/checkins/batch-4.md:2035: trailing whitespace.
+++++   127	
.oracle/checkins/batch-4.md:2037: trailing whitespace.
+++++   128	
.oracle/checkins/batch-4.md:2039: trailing whitespace.
+++++   142	
.oracle/checkins/batch-4.md:2041: trailing whitespace.
+++++   143	
.oracle/checkins/batch-4.md:2043: trailing whitespace.
+++++   161	
.oracle/checkins/batch-4.md:2045: trailing whitespace.
+++++   173	
.oracle/checkins/batch-4.md:2047: trailing whitespace.
+++++   176	
.oracle/checkins/batch-4.md:2049: trailing whitespace.
+++++   177	
.oracle/checkins/batch-4.md:2051: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:2053: trailing whitespace.
+++++   182	
.oracle/checkins/batch-4.md:2055: trailing whitespace.
+++++   204	
.oracle/checkins/batch-4.md:2057: trailing whitespace.
+++++   205	
.oracle/checkins/batch-4.md:2059: trailing whitespace.
+++++   208	
.oracle/checkins/batch-4.md:2061: trailing whitespace.
+++++   319	
.oracle/checkins/batch-4.md:2063: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:2065: trailing whitespace.
+++++   326	
.oracle/checkins/batch-4.md:2067: trailing whitespace.
+++++   334	
.oracle/checkins/batch-4.md:2069: trailing whitespace.
+++++   338	
.oracle/checkins/batch-4.md:2071: trailing whitespace.
+++++   341	
.oracle/checkins/batch-4.md:2073: trailing whitespace.
+++++   344	
.oracle/checkins/batch-4.md:2075: trailing whitespace.
+++++   345	
.oracle/checkins/batch-4.md:2077: trailing whitespace.
+++++   348	
.oracle/checkins/batch-4.md:2079: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:2081: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:2083: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:2085: trailing whitespace.
+++++    15	
.oracle/checkins/batch-4.md:2087: trailing whitespace.
+++++    31	
.oracle/checkins/batch-4.md:2089: trailing whitespace.
+++++    35	
.oracle/checkins/batch-4.md:2091: trailing whitespace.
+++++    37	
.oracle/checkins/batch-4.md:2093: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:2095: trailing whitespace.
+++++    43	
.oracle/checkins/batch-4.md:2097: trailing whitespace.
+++++    45	
.oracle/checkins/batch-4.md:2099: trailing whitespace.
+++++    53	
.oracle/checkins/batch-4.md:2101: trailing whitespace.
+++++    58	
.oracle/checkins/batch-4.md:2103: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:2105: trailing whitespace.
+++++    65	
.oracle/checkins/batch-4.md:2107: trailing whitespace.
+++++    66	
.oracle/checkins/batch-4.md:2109: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:2111: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:2113: trailing whitespace.
+++++    83	
.oracle/checkins/batch-4.md:2115: trailing whitespace.
+++++    84	
.oracle/checkins/batch-4.md:2117: trailing whitespace.
+++++    88	
.oracle/checkins/batch-4.md:2119: trailing whitespace.
+++++    89	
.oracle/checkins/batch-4.md:2121: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:2123: trailing whitespace.
+++++    98	
.oracle/checkins/batch-4.md:2125: trailing whitespace.
+++++   110	
.oracle/checkins/batch-4.md:2127: trailing whitespace.
+++++   111	
.oracle/checkins/batch-4.md:2129: trailing whitespace.
+++++   116	
.oracle/checkins/batch-4.md:2131: trailing whitespace.
+++++   117	
.oracle/checkins/batch-4.md:2133: trailing whitespace.
+++++   135	
.oracle/checkins/batch-4.md:2135: trailing whitespace.
+++++   136	
.oracle/checkins/batch-4.md:2137: trailing whitespace.
+++++   149	
.oracle/checkins/batch-4.md:2139: trailing whitespace.
+++++   150	
.oracle/checkins/batch-4.md:2141: trailing whitespace.
+++++   163	
.oracle/checkins/batch-4.md:2143: trailing whitespace.
+++++   164	
.oracle/checkins/batch-4.md:2145: trailing whitespace.
+++++   173	
.oracle/checkins/batch-4.md:2147: trailing whitespace.
+++++   174	
.oracle/checkins/batch-4.md:2149: trailing whitespace.
+++++   180	
.oracle/checkins/batch-4.md:2151: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:2153: trailing whitespace.
+++++   191	
.oracle/checkins/batch-4.md:2155: trailing whitespace.
+++++   192	
.oracle/checkins/batch-4.md:2157: trailing whitespace.
+++++   198	
.oracle/checkins/batch-4.md:2159: trailing whitespace.
+++++   199	
.oracle/checkins/batch-4.md:2161: trailing whitespace.
+++++   206	
.oracle/checkins/batch-4.md:2163: trailing whitespace.
+++++   207	
.oracle/checkins/batch-4.md:2165: trailing whitespace.
+++++   223	
.oracle/checkins/batch-4.md:2167: trailing whitespace.
+++++   224	
.oracle/checkins/batch-4.md:2169: trailing whitespace.
+++++   228	
.oracle/checkins/batch-4.md:2171: trailing whitespace.
+++++   229	
.oracle/checkins/batch-4.md:2173: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:2175: trailing whitespace.
+++++   233	
.oracle/checkins/batch-4.md:2177: trailing whitespace.
+++++   237	
.oracle/checkins/batch-4.md:2179: trailing whitespace.
+++++   238	
.oracle/checkins/batch-4.md:2181: trailing whitespace.
+++++   242	
.oracle/checkins/batch-4.md:2183: trailing whitespace.
+++++   243	
.oracle/checkins/batch-4.md:2185: trailing whitespace.
+++++   250	
.oracle/checkins/batch-4.md:2187: trailing whitespace.
+++++   251	
.oracle/checkins/batch-4.md:2189: trailing whitespace.
+++++   254	
.oracle/checkins/batch-4.md:2191: trailing whitespace.
+++++   271	
.oracle/checkins/batch-4.md:2193: trailing whitespace.
+++++   275	
.oracle/checkins/batch-4.md:2195: trailing whitespace.
+++++   278	
.oracle/checkins/batch-4.md:2197: trailing whitespace.
+++++   288	
.oracle/checkins/batch-4.md:2199: trailing whitespace.
+++++   307	
.oracle/checkins/batch-4.md:2201: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:2203: trailing whitespace.
+++++   324	
.oracle/checkins/batch-4.md:2205: trailing whitespace.
+++++   336	
.oracle/checkins/batch-4.md:2207: trailing whitespace.
+++++   347	
.oracle/checkins/batch-4.md:2209: trailing whitespace.
+++++   352	
.oracle/checkins/batch-4.md:2211: trailing whitespace.
+++++   374	
.oracle/checkins/batch-4.md:2213: trailing whitespace.
+++++   388	
.oracle/checkins/batch-4.md:2215: trailing whitespace.
+++++   423	
.oracle/checkins/batch-4.md:2217: trailing whitespace.
+++++   436	
.oracle/checkins/batch-4.md:2219: trailing whitespace.
+++++   462	
.oracle/checkins/batch-4.md:2221: trailing whitespace.
+++++   477	
.oracle/checkins/batch-4.md:2223: trailing whitespace.
+++++   479	
.oracle/checkins/batch-4.md:2225: trailing whitespace.
+++++   480	
.oracle/checkins/batch-4.md:2227: trailing whitespace.
+++++   486	
.oracle/checkins/batch-4.md:2229: trailing whitespace.
+++++   487	
.oracle/checkins/batch-4.md:2231: trailing whitespace.
+++++   491	
.oracle/checkins/batch-4.md:2233: trailing whitespace.
+++++   492	
.oracle/checkins/batch-4.md:2235: trailing whitespace.
+++++   507	
.oracle/checkins/batch-4.md:2237: trailing whitespace.
+++++   508	
.oracle/checkins/batch-4.md:2239: trailing whitespace.
+++++   511	
.oracle/checkins/batch-4.md:2241: trailing whitespace.
+++++   531	
.oracle/checkins/batch-4.md:2243: trailing whitespace.
+++++   532	
.oracle/checkins/batch-4.md:2245: trailing whitespace.
+++++   539	
.oracle/checkins/batch-4.md:2247: trailing whitespace.
+++++   584	
.oracle/checkins/batch-4.md:2249: trailing whitespace.
+++++   601	
.oracle/checkins/batch-4.md:2251: trailing whitespace.
+++++   613	
.oracle/checkins/batch-4.md:2253: trailing whitespace.
+++++   614	
.oracle/checkins/batch-4.md:2255: trailing whitespace.
+++++   627	
.oracle/checkins/batch-4.md:2257: trailing whitespace.
+++++   628	
.oracle/checkins/batch-4.md:2259: trailing whitespace.
+++++   632	
.oracle/checkins/batch-4.md:2261: trailing whitespace.
+++++   633	
.oracle/checkins/batch-4.md:2263: trailing whitespace.
+++++   647	
.oracle/checkins/batch-4.md:2265: trailing whitespace.
+++++   654	
.oracle/checkins/batch-4.md:2267: trailing whitespace.
+++++   655	
.oracle/checkins/batch-4.md:2269: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:2271: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:2273: trailing whitespace.
+++++     9	
.oracle/checkins/batch-4.md:2275: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:2277: trailing whitespace.
+++++    15	
.oracle/checkins/batch-4.md:2279: trailing whitespace.
+++++    20	
.oracle/checkins/batch-4.md:2281: trailing whitespace.
+++++    21	
.oracle/checkins/batch-4.md:2283: trailing whitespace.
+++++    24	
.oracle/checkins/batch-4.md:2285: trailing whitespace.
+++++    25	
.oracle/checkins/batch-4.md:2287: trailing whitespace.
+++++    30	
.oracle/checkins/batch-4.md:2289: trailing whitespace.
+++++    38	
.oracle/checkins/batch-4.md:2291: trailing whitespace.
+++++    43	
.oracle/checkins/batch-4.md:2293: trailing whitespace.
+++++    44	
.oracle/checkins/batch-4.md:2295: trailing whitespace.
+++++    49	
.oracle/checkins/batch-4.md:2297: trailing whitespace.
+++++    50	
.oracle/checkins/batch-4.md:2299: trailing whitespace.
+++++    54	
.oracle/checkins/batch-4.md:2301: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:2303: trailing whitespace.
+++++    11	
.oracle/checkins/batch-4.md:2305: trailing whitespace.
+++++    16	
.oracle/checkins/batch-4.md:2307: trailing whitespace.
+++++    18	
.oracle/checkins/batch-4.md:2309: trailing whitespace.
+++++    22	
.oracle/checkins/batch-4.md:2311: trailing whitespace.
+++++    23	
.oracle/checkins/batch-4.md:2313: trailing whitespace.
+++++    36	
.oracle/checkins/batch-4.md:2315: trailing whitespace.
+++++    37	
.oracle/checkins/batch-4.md:2317: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:2319: trailing whitespace.
+++++    56	
.oracle/checkins/batch-4.md:2321: trailing whitespace.
+++++    57	
.oracle/checkins/batch-4.md:2323: trailing whitespace.
+++++    60	
.oracle/checkins/batch-4.md:2325: trailing whitespace.
+++++    61	
.oracle/checkins/batch-4.md:2327: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:2329: trailing whitespace.
+++++    64	
.oracle/checkins/batch-4.md:2331: trailing whitespace.
+++++    68	
.oracle/checkins/batch-4.md:2333: trailing whitespace.
+++++    69	
.oracle/checkins/batch-4.md:2335: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:2337: trailing whitespace.
+++++    72	
.oracle/checkins/batch-4.md:2339: trailing whitespace.
+++++    76	
.oracle/checkins/batch-4.md:2341: trailing whitespace.
+++++    77	
.oracle/checkins/batch-4.md:2343: trailing whitespace.
+++++    79	
.oracle/checkins/batch-4.md:2345: trailing whitespace.
+++++    80	
.oracle/checkins/batch-4.md:2347: trailing whitespace.
+++++    84	
.oracle/checkins/batch-4.md:2349: trailing whitespace.
+++++    85	
.oracle/checkins/batch-4.md:2351: trailing whitespace.
+++++   100	
.oracle/checkins/batch-4.md:2353: trailing whitespace.
+++++   106	
.oracle/checkins/batch-4.md:2355: trailing whitespace.
+++++   107	
.oracle/checkins/batch-4.md:2357: trailing whitespace.
+++++   153	
.oracle/checkins/batch-4.md:2359: trailing whitespace.
+++++   162	
.oracle/checkins/batch-4.md:2361: trailing whitespace.
+++++   213	
.oracle/checkins/batch-4.md:2363: trailing whitespace.
+++++   219	
.oracle/checkins/batch-4.md:2365: trailing whitespace.
+++++   220	
.oracle/checkins/batch-4.md:2367: trailing whitespace.
+++++   222	
.oracle/checkins/batch-4.md:2369: trailing whitespace.
+++++   223	
.oracle/checkins/batch-4.md:2371: trailing whitespace.
+++++   229	
.oracle/checkins/batch-4.md:2373: trailing whitespace.
+++++   230	
.oracle/checkins/batch-4.md:2375: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:2377: trailing whitespace.
+++++   233	
.oracle/checkins/batch-4.md:2379: trailing whitespace.
+++++   242	
.oracle/checkins/batch-4.md:2381: trailing whitespace.
+++++   243	
.oracle/checkins/batch-4.md:2383: trailing whitespace.
+++++   245	
.oracle/checkins/batch-4.md:2385: trailing whitespace.
+++++   246	
.oracle/checkins/batch-4.md:2387: trailing whitespace.
+++++   249	
.oracle/checkins/batch-4.md:2389: trailing whitespace.
+++++   256	
.oracle/checkins/batch-4.md:2391: trailing whitespace.
+++++   259	
.oracle/checkins/batch-4.md:2393: trailing whitespace.
+++++   264	
.oracle/checkins/batch-4.md:2395: trailing whitespace.
+++++   265	
.oracle/checkins/batch-4.md:2397: trailing whitespace.
+++++   269	
.oracle/checkins/batch-4.md:2399: trailing whitespace.
+++++   270	
.oracle/checkins/batch-4.md:2401: trailing whitespace.
+++++   274	
.oracle/checkins/batch-4.md:2403: trailing whitespace.
+++++   278	
.oracle/checkins/batch-4.md:2405: trailing whitespace.
+++++   279	
.oracle/checkins/batch-4.md:2407: trailing whitespace.
+++++   285	
.oracle/checkins/batch-4.md:2409: trailing whitespace.
+++++   292	
.oracle/checkins/batch-4.md:2411: trailing whitespace.
+++++   293	
.oracle/checkins/batch-4.md:2413: trailing whitespace.
+++++   297	
.oracle/checkins/batch-4.md:2415: trailing whitespace.
+++++   303	
.oracle/checkins/batch-4.md:2417: trailing whitespace.
+++++   309	
.oracle/checkins/batch-4.md:2419: trailing whitespace.
+++++   310	
.oracle/checkins/batch-4.md:2421: trailing whitespace.
+++++   316	
.oracle/checkins/batch-4.md:2423: trailing whitespace.
+++++   329	
.oracle/checkins/batch-4.md:2425: trailing whitespace.
+++++   330	
.oracle/checkins/batch-4.md:2427: trailing whitespace.
+++++   335	
.oracle/checkins/batch-4.md:2429: trailing whitespace.
+++++   341	
.oracle/checkins/batch-4.md:2431: trailing whitespace.
+++++   342	
.oracle/checkins/batch-4.md:2433: trailing whitespace.
+++++   344	
.oracle/checkins/batch-4.md:2435: trailing whitespace.
+++++   345	
.oracle/checkins/batch-4.md:2437: trailing whitespace.
+++++   352	
.oracle/checkins/batch-4.md:2439: trailing whitespace.
+++++   353	
.oracle/checkins/batch-4.md:2441: trailing whitespace.
+++++   356	
.oracle/checkins/batch-4.md:2443: trailing whitespace.
+++++   357	
.oracle/checkins/batch-4.md:2445: trailing whitespace.
+++++   380	
.oracle/checkins/batch-4.md:2447: trailing whitespace.
+++++   381	
.oracle/checkins/batch-4.md:2449: trailing whitespace.
+++++   391	
.oracle/checkins/batch-4.md:2451: trailing whitespace.
+++++   392	
.oracle/checkins/batch-4.md:2453: trailing whitespace.
+++++   400	
.oracle/checkins/batch-4.md:2455: trailing whitespace.
+++++   401	
.oracle/checkins/batch-4.md:2457: trailing whitespace.
+++++   407	
.oracle/checkins/batch-4.md:2459: trailing whitespace.
+++++   408	
.oracle/checkins/batch-4.md:2461: trailing whitespace.
+++++   417	
.oracle/checkins/batch-4.md:2463: trailing whitespace.
+++++   418	
.oracle/checkins/batch-4.md:2465: trailing whitespace.
+++++   421	
.oracle/checkins/batch-4.md:2467: trailing whitespace.
+++++   428	
.oracle/checkins/batch-4.md:2469: trailing whitespace.
+++++   432	
.oracle/checkins/batch-4.md:2471: trailing whitespace.
+++++   434	
.oracle/checkins/batch-4.md:2473: trailing whitespace.
+++++   440	
.oracle/checkins/batch-4.md:2475: trailing whitespace.
+++++   441	
.oracle/checkins/batch-4.md:2477: trailing whitespace.
+++++   445	
.oracle/checkins/batch-4.md:2479: trailing whitespace.
+++++   451	
.oracle/checkins/batch-4.md:2481: trailing whitespace.
+++++   452	
.oracle/checkins/batch-4.md:2483: trailing whitespace.
+++++   455	
.oracle/checkins/batch-4.md:2485: trailing whitespace.
+++++   463	
.oracle/checkins/batch-4.md:2487: trailing whitespace.
+++++   468	
.oracle/checkins/batch-4.md:2489: trailing whitespace.
+++++   471	
.oracle/checkins/batch-4.md:2491: trailing whitespace.
+++++   472	
.oracle/checkins/batch-4.md:2493: trailing whitespace.
+++++   475	
.oracle/checkins/batch-4.md:2495: trailing whitespace.
+++++   481	
.oracle/checkins/batch-4.md:2497: trailing whitespace.
+++++   488	
.oracle/checkins/batch-4.md:2499: trailing whitespace.
+++++   494	
.oracle/checkins/batch-4.md:2501: trailing whitespace.
+++++   495	
.oracle/checkins/batch-4.md:2503: trailing whitespace.
+++++   498	
.oracle/checkins/batch-4.md:2505: trailing whitespace.
+++++   506	
.oracle/checkins/batch-4.md:2507: trailing whitespace.
+++++   517	
.oracle/checkins/batch-4.md:2509: trailing whitespace.
+++++   532	
.oracle/checkins/batch-4.md:2511: trailing whitespace.
+++++   533	
.oracle/checkins/batch-4.md:2513: trailing whitespace.
+++++   536	
.oracle/checkins/batch-4.md:2515: trailing whitespace.
+++++   543	
.oracle/checkins/batch-4.md:2517: trailing whitespace.
+++++   547	
.oracle/checkins/batch-4.md:2519: trailing whitespace.
+++++   554	
.oracle/checkins/batch-4.md:2521: trailing whitespace.
+++++   557	
.oracle/checkins/batch-4.md:2523: trailing whitespace.
+++++   558	
.oracle/checkins/batch-4.md:2525: trailing whitespace.
+++++   562	
.oracle/checkins/batch-4.md:2527: trailing whitespace.
+++++   565	
.oracle/checkins/batch-4.md:2529: trailing whitespace.
+++++   576	
.oracle/checkins/batch-4.md:2531: trailing whitespace.
+++++   584	
.oracle/checkins/batch-4.md:2533: trailing whitespace.
+++++   587	
.oracle/checkins/batch-4.md:2535: trailing whitespace.
+++++   588	
.oracle/checkins/batch-4.md:2537: trailing whitespace.
+++++   592	
.oracle/checkins/batch-4.md:2539: trailing whitespace.
+++++   595	
.oracle/checkins/batch-4.md:2541: trailing whitespace.
+++++   606	
.oracle/checkins/batch-4.md:2543: trailing whitespace.
+++++   615	
.oracle/checkins/batch-4.md:2545: trailing whitespace.
+++++   619	
.oracle/checkins/batch-4.md:2547: trailing whitespace.
+++++   620	
.oracle/checkins/batch-4.md:2549: trailing whitespace.
+++++   624	
.oracle/checkins/batch-4.md:2551: trailing whitespace.
+++++   629	
.oracle/checkins/batch-4.md:2553: trailing whitespace.
+++++   630	
.oracle/checkins/batch-4.md:2555: trailing whitespace.
+++++   633	
.oracle/checkins/batch-4.md:2557: trailing whitespace.
+++++   634	
.oracle/checkins/batch-4.md:2559: trailing whitespace.
+++++   655	
.oracle/checkins/batch-4.md:2561: trailing whitespace.
+++++   656	
.oracle/checkins/batch-4.md:2563: trailing whitespace.
+++++   661	
.oracle/checkins/batch-4.md:2565: trailing whitespace.
+++++   663	
.oracle/checkins/batch-4.md:2567: trailing whitespace.
+++++   672	
.oracle/checkins/batch-4.md:2569: trailing whitespace.
+++++   676	
.oracle/checkins/batch-4.md:2571: trailing whitespace.
+++++   679	
.oracle/checkins/batch-4.md:2573: trailing whitespace.
+++++   682	
.oracle/checkins/batch-4.md:2575: trailing whitespace.
+++++   694	
.oracle/checkins/batch-4.md:2577: trailing whitespace.
+++++   706	
.oracle/checkins/batch-4.md:2579: trailing whitespace.
+++++   707	
.oracle/checkins/batch-4.md:2581: trailing whitespace.
+++++   711	
.oracle/checkins/batch-4.md:2583: trailing whitespace.
+++++   714	
.oracle/checkins/batch-4.md:2585: trailing whitespace.
+++++   720	
.oracle/checkins/batch-4.md:2587: trailing whitespace.
+++++   721	
.oracle/checkins/batch-4.md:2589: trailing whitespace.
+++++   724	
.oracle/checkins/batch-4.md:2591: trailing whitespace.
+++++   731	
.oracle/checkins/batch-4.md:2593: trailing whitespace.
+++++   733	
.oracle/checkins/batch-4.md:2595: trailing whitespace.
+++++   738	
.oracle/checkins/batch-4.md:2597: trailing whitespace.
+++++   744	
.oracle/checkins/batch-4.md:2599: trailing whitespace.
+++++   745	
.oracle/checkins/batch-4.md:2601: trailing whitespace.
+++++   749	
.oracle/checkins/batch-4.md:2603: trailing whitespace.
+++++   752	
.oracle/checkins/batch-4.md:2605: trailing whitespace.
+++++   758	
.oracle/checkins/batch-4.md:2607: trailing whitespace.
+++++   760	
.oracle/checkins/batch-4.md:2609: trailing whitespace.
+++++   762	
.oracle/checkins/batch-4.md:2611: trailing whitespace.
+++++   763	
.oracle/checkins/batch-4.md:2613: trailing whitespace.
+++++   767	
.oracle/checkins/batch-4.md:2615: trailing whitespace.
+++++   772	
.oracle/checkins/batch-4.md:2617: trailing whitespace.
+++++   777	
.oracle/checkins/batch-4.md:2619: trailing whitespace.
+++++   782	
.oracle/checkins/batch-4.md:2621: trailing whitespace.
+++++   787	
.oracle/checkins/batch-4.md:2623: trailing whitespace.
+++++   792	
.oracle/checkins/batch-4.md:2625: trailing whitespace.
+++++   793	
.oracle/checkins/batch-4.md:2627: trailing whitespace.
+++++   797	
.oracle/checkins/batch-4.md:2629: trailing whitespace.
+++++   804	
.oracle/checkins/batch-4.md:2631: trailing whitespace.
+++++   811	
.oracle/checkins/batch-4.md:2633: trailing whitespace.
+++++   818	
.oracle/checkins/batch-4.md:2635: trailing whitespace.
+++++   819	
.oracle/checkins/batch-4.md:2637: trailing whitespace.
+++++   823	
.oracle/checkins/batch-4.md:2639: trailing whitespace.
+++++   829	
.oracle/checkins/batch-4.md:2641: trailing whitespace.
+++++   834	
.oracle/checkins/batch-4.md:2643: trailing whitespace.
+++++   839	
.oracle/checkins/batch-4.md:2645: trailing whitespace.
+++++   840	
.oracle/checkins/batch-4.md:2647: trailing whitespace.
+++++   844	
.oracle/checkins/batch-4.md:2649: trailing whitespace.
+++++   845	
.oracle/checkins/batch-4.md:2651: trailing whitespace.
+++++   849	
.oracle/checkins/batch-4.md:2653: trailing whitespace.
+++++   861	
.oracle/checkins/batch-4.md:2655: trailing whitespace.
+++++   867	
.oracle/checkins/batch-4.md:2657: trailing whitespace.
+++++   881	
.oracle/checkins/batch-4.md:2659: trailing whitespace.
+++++   882	
.oracle/checkins/batch-4.md:2661: trailing whitespace.
+++++   886	
.oracle/checkins/batch-4.md:2663: trailing whitespace.
+++++   932	
.oracle/checkins/batch-4.md:2665: trailing whitespace.
+++++   948	
.oracle/checkins/batch-4.md:2667: trailing whitespace.
+++++   949	
.oracle/checkins/batch-4.md:2669: trailing whitespace.
+++++   953	
.oracle/checkins/batch-4.md:2671: trailing whitespace.
+++++   973	
.oracle/checkins/batch-4.md:2673: trailing whitespace.
+++++   985	
.oracle/checkins/batch-4.md:2675: trailing whitespace.
+++++   990	
.oracle/checkins/batch-4.md:2677: trailing whitespace.
+++++   995	
.oracle/checkins/batch-4.md:2679: trailing whitespace.
+++++  1000	
.oracle/checkins/batch-4.md:2681: trailing whitespace.
+++++  1004	
.oracle/checkins/batch-4.md:2683: trailing whitespace.
+++++  1005	
.oracle/checkins/batch-4.md:2685: trailing whitespace.
+++++  1009	
.oracle/checkins/batch-4.md:2687: trailing whitespace.
+++++  1010	
.oracle/checkins/batch-4.md:2689: trailing whitespace.
+++++  1015	
.oracle/checkins/batch-4.md:2691: trailing whitespace.
+++++  1028	
.oracle/checkins/batch-4.md:2693: trailing whitespace.
+++++  1029	
.oracle/checkins/batch-4.md:2695: trailing whitespace.
+++++  1042	
.oracle/checkins/batch-4.md:2697: trailing whitespace.
+++++  1043	
.oracle/checkins/batch-4.md:2699: trailing whitespace.
+++++  1051	
.oracle/checkins/batch-4.md:2701: trailing whitespace.
+++++  1052	
.oracle/checkins/batch-4.md:2703: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:2705: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:2707: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:2709: trailing whitespace.
+++++    15	
.oracle/checkins/batch-4.md:2711: trailing whitespace.
+++++    31	
.oracle/checkins/batch-4.md:2713: trailing whitespace.
+++++    35	
.oracle/checkins/batch-4.md:2715: trailing whitespace.
+++++    37	
.oracle/checkins/batch-4.md:2717: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:2719: trailing whitespace.
+++++    43	
.oracle/checkins/batch-4.md:2721: trailing whitespace.
+++++    45	
.oracle/checkins/batch-4.md:2723: trailing whitespace.
+++++    53	
.oracle/checkins/batch-4.md:2725: trailing whitespace.
+++++    58	
.oracle/checkins/batch-4.md:2727: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:2729: trailing whitespace.
+++++    65	
.oracle/checkins/batch-4.md:2731: trailing whitespace.
+++++    66	
.oracle/checkins/batch-4.md:2733: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:2735: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:2737: trailing whitespace.
+++++    83	
.oracle/checkins/batch-4.md:2739: trailing whitespace.
+++++    84	
.oracle/checkins/batch-4.md:2741: trailing whitespace.
+++++    88	
.oracle/checkins/batch-4.md:2743: trailing whitespace.
+++++    89	
.oracle/checkins/batch-4.md:2745: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:2747: trailing whitespace.
+++++    98	
.oracle/checkins/batch-4.md:2749: trailing whitespace.
+++++   110	
.oracle/checkins/batch-4.md:2751: trailing whitespace.
+++++   111	
.oracle/checkins/batch-4.md:2753: trailing whitespace.
+++++   116	
.oracle/checkins/batch-4.md:2755: trailing whitespace.
+++++   117	
.oracle/checkins/batch-4.md:2757: trailing whitespace.
+++++   135	
.oracle/checkins/batch-4.md:2759: trailing whitespace.
+++++   136	
.oracle/checkins/batch-4.md:2761: trailing whitespace.
+++++   149	
.oracle/checkins/batch-4.md:2763: trailing whitespace.
+++++   150	
.oracle/checkins/batch-4.md:2765: trailing whitespace.
+++++   163	
.oracle/checkins/batch-4.md:2767: trailing whitespace.
+++++   164	
.oracle/checkins/batch-4.md:2769: trailing whitespace.
+++++   173	
.oracle/checkins/batch-4.md:2771: trailing whitespace.
+++++   174	
.oracle/checkins/batch-4.md:2773: trailing whitespace.
+++++   180	
.oracle/checkins/batch-4.md:2775: trailing whitespace.
+++++   181	
.oracle/checkins/batch-4.md:2777: trailing whitespace.
+++++   191	
.oracle/checkins/batch-4.md:2779: trailing whitespace.
+++++   192	
.oracle/checkins/batch-4.md:2781: trailing whitespace.
+++++   198	
.oracle/checkins/batch-4.md:2783: trailing whitespace.
+++++   199	
.oracle/checkins/batch-4.md:2785: trailing whitespace.
+++++   206	
.oracle/checkins/batch-4.md:2787: trailing whitespace.
+++++   207	
.oracle/checkins/batch-4.md:2789: trailing whitespace.
+++++   223	
.oracle/checkins/batch-4.md:2791: trailing whitespace.
+++++   224	
.oracle/checkins/batch-4.md:2793: trailing whitespace.
+++++   228	
.oracle/checkins/batch-4.md:2795: trailing whitespace.
+++++   229	
.oracle/checkins/batch-4.md:2797: trailing whitespace.
+++++   232	
.oracle/checkins/batch-4.md:2799: trailing whitespace.
+++++   233	
.oracle/checkins/batch-4.md:2801: trailing whitespace.
+++++   237	
.oracle/checkins/batch-4.md:2803: trailing whitespace.
+++++   238	
.oracle/checkins/batch-4.md:2805: trailing whitespace.
+++++   531	
.oracle/checkins/batch-4.md:2807: trailing whitespace.
+++++   532	
.oracle/checkins/batch-4.md:2809: trailing whitespace.
+++++   539	
.oracle/checkins/batch-4.md:2811: trailing whitespace.
+++++   584	
.oracle/checkins/batch-4.md:2813: trailing whitespace.
+++++   601	
.oracle/checkins/batch-4.md:2815: trailing whitespace.
+++++   613	
.oracle/checkins/batch-4.md:2817: trailing whitespace.
+++++   614	
.oracle/checkins/batch-4.md:2819: trailing whitespace.
+++++   627	
.oracle/checkins/batch-4.md:2821: trailing whitespace.
+++++   628	
.oracle/checkins/batch-4.md:2823: trailing whitespace.
+++++   632	
.oracle/checkins/batch-4.md:2825: trailing whitespace.
+++++   633	
.oracle/checkins/batch-4.md:2827: trailing whitespace.
+++++   647	
.oracle/checkins/batch-4.md:2829: trailing whitespace.
+++++   654	
.oracle/checkins/batch-4.md:2831: trailing whitespace.
+++++   655	
.oracle/checkins/batch-4.md:2833: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2835: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2837: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2839: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2841: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2843: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2845: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2847: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2849: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2851: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2853: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2855: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2857: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2859: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2861: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2863: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2865: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2867: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2869: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2871: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2873: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2875: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2877: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2879: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2881: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2883: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2885: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2887: trailing whitespace.
+++++   242	
.oracle/checkins/batch-4.md:2889: trailing whitespace.
+++++   243	
.oracle/checkins/batch-4.md:2891: trailing whitespace.
+++++   250	
.oracle/checkins/batch-4.md:2893: trailing whitespace.
+++++   251	
.oracle/checkins/batch-4.md:2895: trailing whitespace.
+++++   254	
.oracle/checkins/batch-4.md:2897: trailing whitespace.
+++++   271	
.oracle/checkins/batch-4.md:2899: trailing whitespace.
+++++   275	
.oracle/checkins/batch-4.md:2901: trailing whitespace.
+++++   278	
.oracle/checkins/batch-4.md:2903: trailing whitespace.
+++++   288	
.oracle/checkins/batch-4.md:2905: trailing whitespace.
+++++   307	
.oracle/checkins/batch-4.md:2907: trailing whitespace.
+++++   320	
.oracle/checkins/batch-4.md:2909: trailing whitespace.
+++++   324	
.oracle/checkins/batch-4.md:2911: trailing whitespace.
+++++   336	
.oracle/checkins/batch-4.md:2913: trailing whitespace.
+++++   347	
.oracle/checkins/batch-4.md:2915: trailing whitespace.
+++++   352	
.oracle/checkins/batch-4.md:2917: trailing whitespace.
+++++   374	
.oracle/checkins/batch-4.md:2919: trailing whitespace.
+++++   388	
.oracle/checkins/batch-4.md:2921: trailing whitespace.
+++++   423	
.oracle/checkins/batch-4.md:2923: trailing whitespace.
+++++   436	
.oracle/checkins/batch-4.md:2925: trailing whitespace.
+++++   462	
.oracle/checkins/batch-4.md:2927: trailing whitespace.
+++++   477	
.oracle/checkins/batch-4.md:2929: trailing whitespace.
+++++   479	
.oracle/checkins/batch-4.md:2931: trailing whitespace.
+++++   480	
.oracle/checkins/batch-4.md:2933: trailing whitespace.
+++++   486	
.oracle/checkins/batch-4.md:2935: trailing whitespace.
+++++   487	
.oracle/checkins/batch-4.md:2937: trailing whitespace.
+++++   491	
.oracle/checkins/batch-4.md:2939: trailing whitespace.
+++++   492	
.oracle/checkins/batch-4.md:2941: trailing whitespace.
+++++   507	
.oracle/checkins/batch-4.md:2943: trailing whitespace.
+++++   508	
.oracle/checkins/batch-4.md:2945: trailing whitespace.
+++++   511	
.oracle/checkins/batch-4.md:2947: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2949: trailing whitespace.
+++++ 
.oracle/checkins/batch-4.md:2951: trailing whitespace.
+++++   280	
.oracle/checkins/batch-4.md:2953: trailing whitespace.
+++++   283	
.oracle/checkins/batch-4.md:2955: trailing whitespace.
+++++   300	
.oracle/checkins/batch-4.md:2957: trailing whitespace.
+++++   311	
.oracle/checkins/batch-4.md:2959: trailing whitespace.
+++++   317	
.oracle/checkins/batch-4.md:2961: trailing whitespace.
+++++   326	
.oracle/checkins/batch-4.md:2963: trailing whitespace.
+++++   365	
.oracle/checkins/batch-4.md:2965: trailing whitespace.
+++++   370	
.oracle/checkins/batch-4.md:2967: trailing whitespace.
+++++   392	
.oracle/checkins/batch-4.md:2969: trailing whitespace.
+++++   404	
.oracle/checkins/batch-4.md:2971: trailing whitespace.
+++++   423	
.oracle/checkins/batch-4.md:2973: trailing whitespace.
+++++   451	
.oracle/checkins/batch-4.md:2975: trailing whitespace.
+++++   465	
.oracle/checkins/batch-4.md:2977: trailing whitespace.
+++++   469	
.oracle/checkins/batch-4.md:2979: trailing whitespace.
+++++   472	
.oracle/checkins/batch-4.md:2981: trailing whitespace.
+++++   481	
.oracle/checkins/batch-4.md:2983: trailing whitespace.
+++++   492	
.oracle/checkins/batch-4.md:2985: trailing whitespace.
+++++   496	
.oracle/checkins/batch-4.md:2987: trailing whitespace.
+++++   241	
.oracle/checkins/batch-4.md:2989: trailing whitespace.
+++++   252	
.oracle/checkins/batch-4.md:2991: trailing whitespace.
+++++   255	
.oracle/checkins/batch-4.md:2993: trailing whitespace.
+++++   264	
.oracle/checkins/batch-4.md:2995: trailing whitespace.
+++++   268	
.oracle/checkins/batch-4.md:2997: trailing whitespace.
+++++   275	
.oracle/checkins/batch-4.md:2999: trailing whitespace.
+++++   277	
.oracle/checkins/batch-4.md:3001: trailing whitespace.
+++++   280	
.oracle/checkins/batch-4.md:3003: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:3005: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:3007: trailing whitespace.
+++++    79	
.oracle/checkins/batch-4.md:3009: trailing whitespace.
+++++    80	
.oracle/checkins/batch-4.md:3011: trailing whitespace.
+++++    92	
.oracle/checkins/batch-4.md:3013: trailing whitespace.
+++++    97	
.oracle/checkins/batch-4.md:3015: trailing whitespace.
+++++    99	
.oracle/checkins/batch-4.md:3017: trailing whitespace.
+++++   100	
.oracle/checkins/batch-4.md:3019: trailing whitespace.
+++++   107	
.oracle/checkins/batch-4.md:3021: trailing whitespace.
+++++   108	
.oracle/checkins/batch-4.md:3023: trailing whitespace.
+++++     2	
.oracle/checkins/batch-4.md:3025: trailing whitespace.
+++++     7	
.oracle/checkins/batch-4.md:3027: trailing whitespace.
+++++    12	
.oracle/checkins/batch-4.md:3029: trailing whitespace.
+++++    15	
.oracle/checkins/batch-4.md:3031: trailing whitespace.
+++++    31	
.oracle/checkins/batch-4.md:3033: trailing whitespace.
+++++    35	
.oracle/checkins/batch-4.md:3035: trailing whitespace.
+++++    37	
.oracle/checkins/batch-4.md:3037: trailing whitespace.
+++++    40	
.oracle/checkins/batch-4.md:3039: trailing whitespace.
+++++    43	
.oracle/checkins/batch-4.md:3041: trailing whitespace.
+++++    45	
.oracle/checkins/batch-4.md:3043: trailing whitespace.
+++++    53	
.oracle/checkins/batch-4.md:3045: trailing whitespace.
+++++    58	
.oracle/checkins/batch-4.md:3047: trailing whitespace.
+++++    63	
.oracle/checkins/batch-4.md:3049: trailing whitespace.
+++++    65	
.oracle/checkins/batch-4.md:3051: trailing whitespace.
+++++    66	
.oracle/checkins/batch-4.md:3053: trailing whitespace.
+++++    70	
.oracle/checkins/batch-4.md:3055: trailing whitespace.
+++++    71	
.oracle/checkins/batch-4.md:3057: trailing whitespace.
+++++    83	
.oracle/checkins/batch-4.md:3059: trailing whitespace.
+++++    84	
.oracle/checkins/batch-4.md:3061: trailing whitespace.
++++    80	
.oracle/checkins/batch-4.md:3063: trailing whitespace.
++++    92	
.oracle/checkins/batch-4.md:3065: trailing whitespace.
++++    97	
.oracle/checkins/batch-4.md:3067: trailing whitespace.
++++    99	
.oracle/checkins/batch-4.md:3069: trailing whitespace.
++++   100	
.oracle/checkins/batch-4.md:3071: trailing whitespace.
++++   107	
.oracle/checkins/batch-4.md:3073: trailing whitespace.
++++   108	
.oracle/checkins/batch-4.md:3075: trailing whitespace.
++++   121	
.oracle/checkins/batch-4.md:3077: trailing whitespace.
++++   125	
.oracle/checkins/batch-4.md:3079: trailing whitespace.
++++   129	
.oracle/checkins/batch-4.md:3081: trailing whitespace.
++++   130	
.oracle/checkins/batch-4.md:3083: trailing whitespace.
++++   140	
.oracle/checkins/batch-4.md:3085: trailing whitespace.
++++   141	
.oracle/checkins/batch-4.md:3087: trailing whitespace.
++++   148	
.oracle/checkins/batch-4.md:3089: trailing whitespace.
++++   149	
.oracle/checkins/batch-4.md:3091: trailing whitespace.
++++   154	
.oracle/checkins/batch-4.md:3093: trailing whitespace.
++++   155	
.oracle/checkins/batch-4.md:3095: trailing whitespace.
++++   158	
.oracle/checkins/batch-4.md:3097: trailing whitespace.
++++   170	
.oracle/checkins/batch-4.md:3099: trailing whitespace.
++++   171	
.oracle/checkins/batch-4.md:3101: trailing whitespace.
++++   275	
.oracle/checkins/batch-4.md:3103: trailing whitespace.
++++   277	
.oracle/checkins/batch-4.md:3105: trailing whitespace.
++++   280	
.oracle/checkins/batch-4.md:3107: trailing whitespace.
++++   283	
.oracle/checkins/batch-4.md:3109: trailing whitespace.
++++   300	
.oracle/checkins/batch-4.md:3111: trailing whitespace.
++++   311	
.oracle/checkins/batch-4.md:3113: trailing whitespace.
++++   317	
.oracle/checkins/batch-4.md:3115: trailing whitespace.
++++   326	
.oracle/checkins/batch-4.md:3117: trailing whitespace.
++++   365	
.oracle/checkins/batch-4.md:3119: trailing whitespace.
++++   370	
.oracle/checkins/batch-4.md:3121: trailing whitespace.
++++   392	
.oracle/checkins/batch-4.md:3123: trailing whitespace.
++++   404	
.oracle/checkins/batch-4.md:3125: trailing whitespace.
++++   423	
.oracle/checkins/batch-4.md:3127: trailing whitespace.
++++   451	
.oracle/checkins/batch-4.md:3129: trailing whitespace.
++++   465	
.oracle/checkins/batch-4.md:3131: trailing whitespace.
++++   469	
.oracle/checkins/batch-4.md:3133: trailing whitespace.
++++   472	
.oracle/checkins/batch-4.md:3135: trailing whitespace.
++++   481	
.oracle/checkins/batch-4.md:3137: trailing whitespace.
++++   492	
.oracle/checkins/batch-4.md:3139: trailing whitespace.
++++   496	
.oracle/checkins/batch-4.md:3141: trailing whitespace.
++++   513	
.oracle/checkins/batch-4.md:3143: trailing whitespace.
++++   515	
.oracle/checkins/batch-4.md:3145: trailing whitespace.
++++   538	
.oracle/checkins/batch-4.md:3147: trailing whitespace.
++++   550	
.oracle/checkins/batch-4.md:3149: trailing whitespace.
++++   556	
.oracle/checkins/batch-4.md:3151: trailing whitespace.
++++   568	
.oracle/checkins/batch-4.md:3153: trailing whitespace.
++++   584	
.oracle/checkins/batch-4.md:3155: trailing whitespace.
++++   596	
.oracle/checkins/batch-4.md:3157: trailing whitespace.
++++   604	
.oracle/checkins/batch-4.md:3159: trailing whitespace.
++++   620	
.oracle/checkins/batch-4.md:3161: trailing whitespace.
++++   631	
.oracle/checkins/batch-4.md:3163: trailing whitespace.
++++   634	
.oracle/checkins/batch-4.md:3165: trailing whitespace.
++++   733	
.oracle/checkins/batch-4.md:3167: trailing whitespace.
++++   759	
.oracle/checkins/batch-4.md:3169: trailing whitespace.
++++   764	
.oracle/checkins/batch-4.md:3171: trailing whitespace.
++++   768	
.oracle/checkins/batch-4.md:3173: trailing whitespace.
++++   784	
.oracle/checkins/batch-4.md:3175: trailing whitespace.
++++   787	
.oracle/checkins/batch-4.md:3177: trailing whitespace.
++++   794	
.oracle/checkins/batch-4.md:3179: trailing whitespace.
++++   796	
.oracle/checkins/batch-4.md:3181: trailing whitespace.
++++   803	
.oracle/checkins/batch-4.md:3183: trailing whitespace.
++++   813	
.oracle/checkins/batch-4.md:3185: trailing whitespace.
++++   820	
.oracle/checkins/batch-4.md:3187: trailing whitespace.
++++   823	
.oracle/checkins/batch-4.md:3189: trailing whitespace.
++++   826	
.oracle/checkins/batch-4.md:3191: trailing whitespace.
++++   840	
.oracle/checkins/batch-4.md:3193: trailing whitespace.
++++   847	
.oracle/checkins/batch-4.md:3195: trailing whitespace.
++++   857	
.oracle/checkins/batch-4.md:3197: trailing whitespace.
++++   995	
.oracle/checkins/batch-4.md:3199: trailing whitespace.
++++   996	
.oracle/checkins/batch-4.md:3201: trailing whitespace.
++++  1007	
.oracle/checkins/batch-4.md:3203: trailing whitespace.
++++  1008	
.oracle/checkins/batch-4.md:3205: trailing whitespace.
++++  1019	
.oracle/checkins/batch-4.md:3207: trailing whitespace.
++++  1020	
.oracle/checkins/batch-4.md:3209: trailing whitespace.
++++  1027	
.oracle/checkins/batch-4.md:3211: trailing whitespace.
++++  1031	
.oracle/checkins/batch-4.md:3213: trailing whitespace.
++++  1032	
.oracle/checkins/batch-4.md:3215: trailing whitespace.
++++  1043	
.oracle/checkins/batch-4.md:3217: trailing whitespace.
++++  1044	
.oracle/checkins/batch-4.md:3219: trailing whitespace.
++++  1049	
.oracle/checkins/batch-4.md:3221: trailing whitespace.
++++  1050	
.oracle/checkins/batch-4.md:3223: trailing whitespace.
++++  1054	
.oracle/checkins/batch-4.md:3225: trailing whitespace.
++++  1055	
.oracle/checkins/batch-4.md:3227: trailing whitespace.
++++  1066	
.oracle/checkins/batch-4.md:3229: trailing whitespace.
++++  1067	
.oracle/checkins/batch-4.md:3231: trailing whitespace.
++++  1070	
.oracle/checkins/batch-4.md:3233: trailing whitespace.
++++  1071	
.oracle/checkins/batch-4.md:3235: trailing whitespace.
++++  1078	
.oracle/checkins/batch-4.md:3237: trailing whitespace.
++++  1079	
.oracle/checkins/batch-4.md:3239: trailing whitespace.
++++  1083	
.oracle/checkins/batch-4.md:3241: trailing whitespace.
++++  1087	
.oracle/checkins/batch-4.md:3243: trailing whitespace.
++++  1088	
.oracle/checkins/batch-4.md:3245: trailing whitespace.
++++  1107	
.oracle/checkins/batch-4.md:3247: trailing whitespace.
++++  1108	
.oracle/checkins/batch-4.md:3249: trailing whitespace.
++++  1150	
.oracle/checkins/batch-4.md:3251: trailing whitespace.
++++  1151	
.oracle/checkins/batch-4.md:3253: trailing whitespace.
++++  1154	
.oracle/checkins/batch-4.md:3255: trailing whitespace.
++++  1155	
.oracle/checkins/batch-4.md:3257: trailing whitespace.
++++  1158	
.oracle/checkins/batch-4.md:3259: trailing whitespace.
++++  1172	
.oracle/checkins/batch-4.md:3261: trailing whitespace.
++++  1173	
.oracle/checkins/batch-4.md:3263: trailing whitespace.
++++  1178	
.oracle/checkins/batch-4.md:3265: trailing whitespace.
++++  1191	
.oracle/checkins/batch-4.md:3267: trailing whitespace.
++++  1192	
.oracle/checkins/batch-4.md:3269: trailing whitespace.
++++  1199	
.oracle/checkins/batch-4.md:3271: trailing whitespace.
++++  1206	
.oracle/checkins/batch-4.md:3273: trailing whitespace.
++++  1211	
.oracle/checkins/batch-4.md:3275: trailing whitespace.
++++  1215	
.oracle/checkins/batch-4.md:3277: trailing whitespace.
++++  1232	
.oracle/checkins/batch-4.md:3279: trailing whitespace.
++++  1250	
.oracle/checkins/batch-4.md:3281: trailing whitespace.
++++  1251	
.oracle/checkins/batch-4.md:3283: trailing whitespace.
++++  1261	
.oracle/checkins/batch-4.md:3285: trailing whitespace.
++++  1262	
.oracle/checkins/batch-4.md:3287: trailing whitespace.
++++  1753	
.oracle/checkins/batch-4.md:3289: trailing whitespace.
++++  1754	
.oracle/checkins/batch-4.md:3291: trailing whitespace.
++++  1773	
.oracle/checkins/batch-4.md:3293: trailing whitespace.
++++  1774	
.oracle/checkins/batch-4.md:3295: trailing whitespace.
++++  1782	
.oracle/checkins/batch-4.md:3297: trailing whitespace.
++++  1789	
.oracle/checkins/batch-4.md:3299: trailing whitespace.
++++  1797	
.oracle/checkins/batch-4.md:3301: trailing whitespace.
++++  1798	
.oracle/checkins/batch-4.md:3303: trailing whitespace.
++++  1801	
.oracle/checkins/batch-4.md:3305: trailing whitespace.
++++  1807	
.oracle/checkins/batch-4.md:3307: trailing whitespace.
++++  1808	
.oracle/checkins/batch-4.md:3309: trailing whitespace.
++++  1812	
.oracle/checkins/batch-4.md:3311: trailing whitespace.
++++  1815	
.oracle/checkins/batch-4.md:3313: trailing whitespace.
++++  1816	
.oracle/checkins/batch-4.md:3315: trailing whitespace.
++++   733	
.oracle/checkins/batch-4.md:3317: trailing whitespace.
++++   759	
.oracle/checkins/batch-4.md:3319: trailing whitespace.
++++   764	
.oracle/checkins/batch-4.md:3321: trailing whitespace.
++++   768	
.oracle/checkins/batch-4.md:3323: trailing whitespace.
++++   784	
.oracle/checkins/batch-4.md:3325: trailing whitespace.
++++   787	
.oracle/checkins/batch-4.md:3327: trailing whitespace.
++++   794	
.oracle/checkins/batch-4.md:3329: trailing whitespace.
++++   796	
.oracle/checkins/batch-4.md:3331: trailing whitespace.
++++   803	
.oracle/checkins/batch-4.md:3333: trailing whitespace.
++++   813	
.oracle/checkins/batch-4.md:3335: trailing whitespace.
++++   820	
.oracle/checkins/batch-4.md:3337: trailing whitespace.
++++   823	
.oracle/checkins/batch-4.md:3339: trailing whitespace.
++++   826	
.oracle/checkins/batch-4.md:3341: trailing whitespace.
++++   840	
.oracle/checkins/batch-4.md:3343: trailing whitespace.
++++   847	
.oracle/checkins/batch-4.md:3345: trailing whitespace.
++++   995	
.oracle/checkins/batch-4.md:3347: trailing whitespace.
++++   996	
.oracle/checkins/batch-4.md:3349: trailing whitespace.
++++  1007	
.oracle/checkins/batch-4.md:3351: trailing whitespace.
++++  1008	
.oracle/checkins/batch-4.md:3353: trailing whitespace.
++++  1019	
.oracle/checkins/batch-4.md:3355: trailing whitespace.
++++  1020	
.oracle/checkins/batch-4.md:3357: trailing whitespace.
++++  1027	
.oracle/checkins/batch-4.md:3359: trailing whitespace.
++++  1031	
.oracle/checkins/batch-4.md:3361: trailing whitespace.
++++  1032	
.oracle/checkins/batch-4.md:3363: trailing whitespace.
++++  1043	
.oracle/checkins/batch-4.md:3365: trailing whitespace.
++++  1044	
.oracle/checkins/batch-4.md:3367: trailing whitespace.
++++  1049	
.oracle/checkins/batch-4.md:3369: trailing whitespace.
++++  1050	
.oracle/checkins/batch-4.md:3371: trailing whitespace.
++++  1054	
.oracle/checkins/batch-4.md:3373: trailing whitespace.
++++  1055	
.oracle/checkins/batch-4.md:3375: trailing whitespace.
++++  1270	
.oracle/checkins/batch-4.md:3377: trailing whitespace.
++++  1325	
.oracle/checkins/batch-4.md:3379: trailing whitespace.
++++  1326	
.oracle/checkins/batch-4.md:3381: trailing whitespace.
++++  1338	
.oracle/checkins/batch-4.md:3383: trailing whitespace.
++++  1339	
.oracle/checkins/batch-4.md:3385: trailing whitespace.
++++   187	
.oracle/checkins/batch-4.md:3387: trailing whitespace.
++++   190	
.oracle/checkins/batch-4.md:3389: trailing whitespace.
++++   206	
.oracle/checkins/batch-4.md:3391: trailing whitespace.
++++   209	
.oracle/checkins/batch-4.md:3393: trailing whitespace.
++++   214	
.oracle/checkins/batch-4.md:3395: trailing whitespace.
++++   217	
.oracle/checkins/batch-4.md:3397: trailing whitespace.
++++   222	
.oracle/checkins/batch-4.md:3399: trailing whitespace.
++++   226	
.oracle/checkins/batch-4.md:3401: trailing whitespace.
++++   229	
.oracle/checkins/batch-4.md:3403: trailing whitespace.
++++   232	
.oracle/checkins/batch-4.md:3405: trailing whitespace.
++++   235	
.oracle/checkins/batch-4.md:3407: trailing whitespace.
++++   238	
.oracle/checkins/batch-4.md:3409: trailing whitespace.
++++   241	
.oracle/checkins/batch-4.md:3411: trailing whitespace.
++++   252	
.oracle/checkins/batch-4.md:3413: trailing whitespace.
++++   255	
.oracle/checkins/batch-4.md:3415: trailing whitespace.
++++   264	
.oracle/checkins/batch-4.md:3417: trailing whitespace.
++++   268	
.oracle/checkins/batch-4.md:3419: trailing whitespace.
++++   430	
.oracle/checkins/batch-4.md:3421: trailing whitespace.
++++   431	
.oracle/checkins/batch-4.md:3423: trailing whitespace.
++++   434	
.oracle/checkins/batch-4.md:3425: trailing whitespace.
++++   441	
.oracle/checkins/batch-4.md:3427: trailing whitespace.
++++   449	
.oracle/checkins/batch-4.md:3429: trailing whitespace.
++++   458	
.oracle/checkins/batch-4.md:3431: trailing whitespace.
++++   478	
.oracle/checkins/batch-4.md:3433: trailing whitespace.
++++   482	
.oracle/checkins/batch-4.md:3435: trailing whitespace.
++++   503	
.oracle/checkins/batch-4.md:3437: trailing whitespace.
++++   507	
.oracle/checkins/batch-4.md:3439: trailing whitespace.
++++   511	
.oracle/checkins/batch-4.md:3441: trailing whitespace.
++++   513	
.oracle/checkins/batch-4.md:3443: trailing whitespace.
++++   522	
.oracle/checkins/batch-4.md:3445: trailing whitespace.
++++   607	
.oracle/checkins/batch-4.md:3447: trailing whitespace.
++++   634	
.oracle/checkins/batch-4.md:3449: trailing whitespace.
++++   685	
.oracle/checkins/batch-4.md:3451: trailing whitespace.
++++    37	
.oracle/checkins/batch-4.md:3453: trailing whitespace.
++++    47	
.oracle/checkins/batch-4.md:3455: trailing whitespace.
++++    58	
.oracle/checkins/batch-4.md:3457: trailing whitespace.
++++    60	
.oracle/checkins/batch-4.md:3459: trailing whitespace.
++++    65	
.oracle/checkins/batch-4.md:3461: trailing whitespace.
++++    69	
.oracle/checkins/batch-4.md:3463: trailing whitespace.
++++    70	
.oracle/checkins/batch-4.md:3465: trailing whitespace.
++++   345	
.oracle/checkins/batch-4.md:3467: trailing whitespace.
++++   347	
.oracle/checkins/batch-4.md:3469: trailing whitespace.
++++   354	
.oracle/checkins/batch-4.md:3471: trailing whitespace.
++++   940	
.oracle/checkins/batch-4.md:3473: trailing whitespace.
++++   948	
.oracle/checkins/batch-4.md:3475: trailing whitespace.
++++   949	
.oracle/checkins/batch-4.md:3477: trailing whitespace.
++++   964	
.oracle/checkins/batch-4.md:3479: trailing whitespace.
++++   965	
.oracle/checkins/batch-4.md:3481: trailing whitespace.
++++   719	
.oracle/checkins/batch-4.md:3483: trailing whitespace.
++++   726	
.oracle/checkins/batch-4.md:3485: trailing whitespace.
++++   728	
.oracle/checkins/batch-4.md:3487: trailing whitespace.
++++   730	
.oracle/checkins/batch-4.md:3489: trailing whitespace.
++++   731	
.oracle/checkins/batch-4.md:3491: trailing whitespace.
++++   734	
.oracle/checkins/batch-4.md:3493: trailing whitespace.
++++   740	
.oracle/checkins/batch-4.md:3495: trailing whitespace.
++++   741	
.oracle/checkins/batch-4.md:3497: trailing whitespace.
++++   769	
.oracle/checkins/batch-4.md:3499: trailing whitespace.
++++   770	
.oracle/checkins/batch-4.md:3501: trailing whitespace.
++++   786	
.oracle/checkins/batch-4.md:3503: trailing whitespace.
++++   787	
.oracle/checkins/batch-4.md:3505: trailing whitespace.
++++   794	
.oracle/checkins/batch-4.md:3507: trailing whitespace.
++++   795	
.oracle/checkins/batch-4.md:3509: trailing whitespace.
++++   829	
.oracle/checkins/batch-4.md:3511: trailing whitespace.
++++   830	
.oracle/checkins/batch-4.md:3513: trailing whitespace.
++++   830	
.oracle/checkins/batch-4.md:3515: trailing whitespace.
++++   951	
.oracle/checkins/batch-4.md:3517: trailing whitespace.
++++   967	
.oracle/checkins/batch-4.md:3519: trailing whitespace.
++++   969	
.oracle/checkins/batch-4.md:3521: trailing whitespace.
++++   974	
.oracle/checkins/batch-4.md:3523: trailing whitespace.
++++   981	
.oracle/checkins/batch-4.md:3525: trailing whitespace.
++++   982	
.oracle/checkins/batch-4.md:3527: trailing whitespace.
++++   985	
.oracle/checkins/batch-4.md:3529: trailing whitespace.
++++   986	
.oracle/checkins/batch-4.md:3531: trailing whitespace.
++++   989	
.oracle/checkins/batch-4.md:3533: trailing whitespace.
++++   998	
.oracle/checkins/batch-4.md:3535: trailing whitespace.
++++   999	
.oracle/checkins/batch-4.md:3537: trailing whitespace.
++++  1018	
.oracle/checkins/batch-4.md:3539: trailing whitespace.
++++  1019	
.oracle/checkins/batch-4.md:3541: trailing whitespace.
++++  1043	
.oracle/checkins/batch-4.md:3543: trailing whitespace.
++++  1044	
.oracle/checkins/batch-4.md:3545: trailing whitespace.
++++     2	
.oracle/checkins/batch-4.md:3547: trailing whitespace.
++++     4	
.oracle/checkins/batch-4.md:3549: trailing whitespace.
++++     5	
.oracle/checkins/batch-4.md:3551: trailing whitespace.
++++     7	
.oracle/checkins/batch-4.md:3553: trailing whitespace.
++++     8	
.oracle/checkins/batch-4.md:3555: trailing whitespace.
++++    19	
.oracle/checkins/batch-4.md:3557: trailing whitespace.
++++    25	
.oracle/checkins/batch-4.md:3559: trailing whitespace.
++++    29	
.oracle/checkins/batch-4.md:3561: trailing whitespace.
++++    38	
.oracle/checkins/batch-4.md:3563: trailing whitespace.
++++    39	
.oracle/checkins/batch-4.md:3565: trailing whitespace.
++++    42	
.oracle/checkins/batch-4.md:3567: trailing whitespace.
++++    48	
.oracle/checkins/batch-4.md:3569: trailing whitespace.
++++    49	
.oracle/checkins/batch-4.md:3571: trailing whitespace.
++++    53	
.oracle/checkins/batch-4.md:3573: trailing whitespace.
++++    54	
.oracle/checkins/batch-4.md:3575: trailing whitespace.
++++    50	
.oracle/checkins/batch-4.md:3577: trailing whitespace.
++++    51	
.oracle/checkins/batch-4.md:3579: trailing whitespace.
++++    54	
.oracle/checkins/batch-4.md:3581: trailing whitespace.
++++    81	
.oracle/checkins/batch-4.md:3583: trailing whitespace.
++++     2	
.oracle/checkins/batch-4.md:3585: trailing whitespace.
++++     4	
.oracle/checkins/batch-4.md:3587: trailing whitespace.
++++     7	
.oracle/checkins/batch-4.md:3589: trailing whitespace.
++++    12	
.oracle/checkins/batch-4.md:3591: trailing whitespace.
++++    13	
.oracle/checkins/batch-4.md:3593: trailing whitespace.
++++    16	
.oracle/checkins/batch-4.md:3595: trailing whitespace.
++++    23	
.oracle/checkins/batch-4.md:3597: trailing whitespace.
++++    26	
.oracle/checkins/batch-4.md:3599: trailing whitespace.
++++    31	
.oracle/checkins/batch-4.md:3601: trailing whitespace.
++++    44	
.oracle/checkins/batch-4.md:3603: trailing whitespace.
++++    79	
.oracle/checkins/batch-4.md:3605: trailing whitespace.
++++    97	
.oracle/checkins/batch-4.md:3607: trailing whitespace.
++++   104	
.oracle/checkins/batch-4.md:3609: trailing whitespace.
++++   107	
.oracle/checkins/batch-4.md:3611: trailing whitespace.
++++   117	
.oracle/checkins/batch-4.md:3613: trailing whitespace.
++++   124	
.oracle/checkins/batch-4.md:3615: trailing whitespace.
++++   383	
.oracle/checkins/batch-4.md:3617: trailing whitespace.
++++   384	
.oracle/checkins/batch-4.md:3619: trailing whitespace.
++++   393	
.oracle/checkins/batch-4.md:3621: trailing whitespace.
++++   394	
.oracle/checkins/batch-4.md:3623: trailing whitespace.
++++   402	
.oracle/checkins/batch-4.md:3625: trailing whitespace.
++++   403	
.oracle/checkins/batch-4.md:3627: trailing whitespace.
++++   406	
.oracle/checkins/batch-4.md:3629: trailing whitespace.
++++   416	
.oracle/checkins/batch-4.md:3631: trailing whitespace.
++++   417	
.oracle/checkins/batch-4.md:3633: trailing whitespace.
++++   430	
.oracle/checkins/batch-4.md:3635: trailing whitespace.
++++  1670	
.oracle/checkins/batch-4.md:3637: trailing whitespace.
++++  1671	
.oracle/checkins/batch-4.md:3639: trailing whitespace.
++++  1680	
.oracle/checkins/batch-4.md:3641: trailing whitespace.
++++  1681	
.oracle/checkins/batch-4.md:3643: trailing whitespace.
++++  1690	
.oracle/checkins/batch-4.md:3645: trailing whitespace.
++++  1691	
.oracle/checkins/batch-4.md:3647: trailing whitespace.
++++  1699	
.oracle/checkins/batch-4.md:3649: trailing whitespace.
++++  1700	
.oracle/checkins/batch-4.md:3651: trailing whitespace.
++++  1710	
.oracle/checkins/batch-4.md:3653: trailing whitespace.
++++  1711	
.oracle/checkins/batch-4.md:3655: trailing whitespace.
++++  1724	
.oracle/checkins/batch-4.md:3657: trailing whitespace.
++++  1725	
.oracle/checkins/batch-4.md:3659: trailing whitespace.
++++  1753	
.oracle/checkins/batch-4.md:3661: trailing whitespace.
++++  1754	
.oracle/checkins/batch-4.md:3663: trailing whitespace.
++++  1773	
.oracle/checkins/batch-4.md:3665: trailing whitespace.
++++  1774	
.oracle/checkins/batch-4.md:3667: trailing whitespace.
++++  1782	
.oracle/checkins/batch-4.md:3669: trailing whitespace.
++++  1789	
.oracle/checkins/batch-4.md:3671: trailing whitespace.
++++  1797	
.oracle/checkins/batch-4.md:3673: trailing whitespace.
++++  1798	
.oracle/checkins/batch-4.md:3675: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3677: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3679: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3681: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3683: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3685: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3687: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3689: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3691: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3693: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3695: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3697: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3699: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3701: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3703: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3705: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3707: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3709: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3711: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3713: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3715: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3717: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3719: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3721: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3723: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3725: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3727: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3729: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3731: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3733: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3735: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3737: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3739: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3741: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3743: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3745: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3747: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3749: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3751: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3753: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3755: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3757: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3759: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3761: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3763: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3765: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3767: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3769: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3771: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3773: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3775: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3777: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3779: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3781: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3783: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3785: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3787: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3789: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3791: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3793: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3795: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3797: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3799: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3801: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3803: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3805: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3807: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3809: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3811: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3813: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3815: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3817: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3819: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3821: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3823: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3825: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3827: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3829: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3831: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3833: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3835: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3837: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3839: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3841: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3843: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3845: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3847: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3849: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3851: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3853: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3855: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3857: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3859: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3861: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3863: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3865: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3867: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3869: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3871: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3873: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3875: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3877: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3879: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3881: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3883: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3885: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:3887: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3889: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3891: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3893: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3895: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3897: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3899: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3901: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3903: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3905: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3907: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3909: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3911: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3913: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3915: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3917: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3919: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3921: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3923: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3925: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3927: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3929: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3931: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3933: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3935: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3937: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3939: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3941: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3943: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3945: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3947: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3949: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3951: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3953: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3955: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3957: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3959: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3961: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3963: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3965: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3967: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3969: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3971: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3973: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3975: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3977: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3979: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3981: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3983: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3985: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3987: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3989: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3991: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3993: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3995: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3997: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:3999: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4001: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4003: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4005: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4007: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4009: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4011: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4013: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4015: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4017: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4019: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4021: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4023: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4025: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4027: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4029: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4031: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4033: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4035: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4037: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4039: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4041: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4043: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4045: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4047: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4049: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4051: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4053: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4055: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4057: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4059: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4061: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4063: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4065: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4067: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4069: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4071: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4073: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4075: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4077: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4079: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4081: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4083: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4085: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4087: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4089: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4091: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4093: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4095: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4097: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4099: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4101: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4103: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4105: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4107: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4109: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4111: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4113: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4115: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4117: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4119: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4121: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4123: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4125: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4127: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4129: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4131: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4133: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4135: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4137: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4139: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4141: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4143: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4145: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4147: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4149: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4151: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4153: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4155: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4157: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4159: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4161: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4163: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4165: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4167: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4169: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4171: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4173: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4175: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4177: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4179: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4181: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4183: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4185: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4187: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4189: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4191: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4193: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4195: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4197: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4199: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4201: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4203: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4205: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4207: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4209: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4211: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4213: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4215: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4217: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4219: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4221: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4223: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4225: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4227: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4229: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4231: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4233: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4235: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4237: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4239: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4241: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4243: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4245: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4247: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4249: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4251: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4253: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4255: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4257: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4259: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4261: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4263: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4265: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4267: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4269: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4271: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4273: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4275: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4277: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4279: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4281: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4283: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4285: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4287: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4289: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4291: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4293: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4295: trailing whitespace.
+++     2	
.oracle/checkins/batch-4.md:4297: trailing whitespace.
+++     8	
.oracle/checkins/batch-4.md:4299: trailing whitespace.
+++    15	
.oracle/checkins/batch-4.md:4301: trailing whitespace.
+++    18	
.oracle/checkins/batch-4.md:4303: trailing whitespace.
+++    19	
.oracle/checkins/batch-4.md:4305: trailing whitespace.
+++    27	
.oracle/checkins/batch-4.md:4307: trailing whitespace.
+++    32	
.oracle/checkins/batch-4.md:4309: trailing whitespace.
+++    33	
.oracle/checkins/batch-4.md:4311: trailing whitespace.
+++    38	
.oracle/checkins/batch-4.md:4313: trailing whitespace.
+++    39	
.oracle/checkins/batch-4.md:4315: trailing whitespace.
+++    54	
.oracle/checkins/batch-4.md:4317: trailing whitespace.
+++    55	
.oracle/checkins/batch-4.md:4319: trailing whitespace.
+++    62	
.oracle/checkins/batch-4.md:4321: trailing whitespace.
+++    63	
.oracle/checkins/batch-4.md:4323: trailing whitespace.
+++    71	
.oracle/checkins/batch-4.md:4325: trailing whitespace.
+++    72	
.oracle/checkins/batch-4.md:4327: trailing whitespace.
+++    80	
.oracle/checkins/batch-4.md:4329: trailing whitespace.
+++    81	
.oracle/checkins/batch-4.md:4331: trailing whitespace.
+++    93	
.oracle/checkins/batch-4.md:4333: trailing whitespace.
+++    98	
.oracle/checkins/batch-4.md:4335: trailing whitespace.
+++   100	
.oracle/checkins/batch-4.md:4337: trailing whitespace.
+++   101	
.oracle/checkins/batch-4.md:4339: trailing whitespace.
+++   108	
.oracle/checkins/batch-4.md:4341: trailing whitespace.
+++   109	
.oracle/checkins/batch-4.md:4343: trailing whitespace.
+++   122	
.oracle/checkins/batch-4.md:4345: trailing whitespace.
+++   126	
.oracle/checkins/batch-4.md:4347: trailing whitespace.
+++   130	
.oracle/checkins/batch-4.md:4349: trailing whitespace.
+++   131	
.oracle/checkins/batch-4.md:4351: trailing whitespace.
+++   141	
.oracle/checkins/batch-4.md:4353: trailing whitespace.
+++   142	
.oracle/checkins/batch-4.md:4355: trailing whitespace.
+++   149	
.oracle/checkins/batch-4.md:4357: trailing whitespace.
+++   150	
.oracle/checkins/batch-4.md:4359: trailing whitespace.
+++   155	
.oracle/checkins/batch-4.md:4361: trailing whitespace.
+++   156	
.oracle/checkins/batch-4.md:4363: trailing whitespace.
+++   159	
.oracle/checkins/batch-4.md:4365: trailing whitespace.
+++   171	
.oracle/checkins/batch-4.md:4367: trailing whitespace.
+++   172	
.oracle/checkins/batch-4.md:4369: trailing whitespace.
+++   188	
.oracle/checkins/batch-4.md:4371: trailing whitespace.
+++   191	
.oracle/checkins/batch-4.md:4373: trailing whitespace.
+++   207	
.oracle/checkins/batch-4.md:4375: trailing whitespace.
+++   210	
.oracle/checkins/batch-4.md:4377: trailing whitespace.
+++   215	
.oracle/checkins/batch-4.md:4379: trailing whitespace.
+++   218	
.oracle/checkins/batch-4.md:4381: trailing whitespace.
+++   223	
.oracle/checkins/batch-4.md:4383: trailing whitespace.
+++   227	
.oracle/checkins/batch-4.md:4385: trailing whitespace.
+++   230	
.oracle/checkins/batch-4.md:4387: trailing whitespace.
+++   233	
.oracle/checkins/batch-4.md:4389: trailing whitespace.
+++   236	
.oracle/checkins/batch-4.md:4391: trailing whitespace.
+++   239	
.oracle/checkins/batch-4.md:4393: trailing whitespace.
+++   242	
.oracle/checkins/batch-4.md:4395: trailing whitespace.
+++   253	
.oracle/checkins/batch-4.md:4397: trailing whitespace.
+++   256	
.oracle/checkins/batch-4.md:4399: trailing whitespace.
+++   266	
.oracle/checkins/batch-4.md:4401: trailing whitespace.
+++   270	
.oracle/checkins/batch-4.md:4403: trailing whitespace.
+++   277	
.oracle/checkins/batch-4.md:4405: trailing whitespace.
+++   279	
.oracle/checkins/batch-4.md:4407: trailing whitespace.
+++   282	
.oracle/checkins/batch-4.md:4409: trailing whitespace.
+++   285	
.oracle/checkins/batch-4.md:4411: trailing whitespace.
+++   302	
.oracle/checkins/batch-4.md:4413: trailing whitespace.
+++   313	
.oracle/checkins/batch-4.md:4415: trailing whitespace.
+++   319	
.oracle/checkins/batch-4.md:4417: trailing whitespace.
+++   328	
.oracle/checkins/batch-4.md:4419: trailing whitespace.
+++   367	
.oracle/checkins/batch-4.md:4421: trailing whitespace.
+++   372	
.oracle/checkins/batch-4.md:4423: trailing whitespace.
+++   394	
.oracle/checkins/batch-4.md:4425: trailing whitespace.
+++   406	
.oracle/checkins/batch-4.md:4427: trailing whitespace.
+++   425	
.oracle/checkins/batch-4.md:4429: trailing whitespace.
+++   782	
.oracle/checkins/batch-4.md:4431: trailing whitespace.
+++   798	
.oracle/checkins/batch-4.md:4433: trailing whitespace.
+++   801	
.oracle/checkins/batch-4.md:4435: trailing whitespace.
+++   808	
.oracle/checkins/batch-4.md:4437: trailing whitespace.
+++   810	
.oracle/checkins/batch-4.md:4439: trailing whitespace.
+++   817	
.oracle/checkins/batch-4.md:4441: trailing whitespace.
+++   827	
.oracle/checkins/batch-4.md:4443: trailing whitespace.
+++   834	
.oracle/checkins/batch-4.md:4445: trailing whitespace.
+++   837	
.oracle/checkins/batch-4.md:4447: trailing whitespace.
+++   840	
.oracle/checkins/batch-4.md:4449: trailing whitespace.
+++   854	
.oracle/checkins/batch-4.md:4451: trailing whitespace.
+++   861	
.oracle/checkins/batch-4.md:4453: trailing whitespace.
+++   871	
.oracle/checkins/batch-4.md:4455: trailing whitespace.
+++   886	
.oracle/checkins/batch-4.md:4457: trailing whitespace.
+++   898	
.oracle/checkins/batch-4.md:4459: trailing whitespace.
+++   904	
.oracle/checkins/batch-4.md:4461: trailing whitespace.
+++   907	
.oracle/checkins/batch-4.md:4463: trailing whitespace.
+++   917	
.oracle/checkins/batch-4.md:4465: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4467: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4469: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4471: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4473: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4475: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4477: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4479: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4481: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4483: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4485: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4487: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4489: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4491: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4493: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4495: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4497: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4499: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4501: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4503: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4505: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4507: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4509: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4511: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4513: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4515: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4517: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4519: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4521: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4523: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4525: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4527: trailing whitespace.
+++   418	
.oracle/checkins/batch-4.md:4529: trailing whitespace.
+++   419	
.oracle/checkins/batch-4.md:4531: trailing whitespace.
+++   432	
.oracle/checkins/batch-4.md:4533: trailing whitespace.
+++   433	
.oracle/checkins/batch-4.md:4535: trailing whitespace.
+++   436	
.oracle/checkins/batch-4.md:4537: trailing whitespace.
+++   443	
.oracle/checkins/batch-4.md:4539: trailing whitespace.
+++   451	
.oracle/checkins/batch-4.md:4541: trailing whitespace.
+++   460	
.oracle/checkins/batch-4.md:4543: trailing whitespace.
+++   480	
.oracle/checkins/batch-4.md:4545: trailing whitespace.
+++   484	
.oracle/checkins/batch-4.md:4547: trailing whitespace.
+++   505	
.oracle/checkins/batch-4.md:4549: trailing whitespace.
+++   509	
.oracle/checkins/batch-4.md:4551: trailing whitespace.
+++   513	
.oracle/checkins/batch-4.md:4553: trailing whitespace.
+++   515	
.oracle/checkins/batch-4.md:4555: trailing whitespace.
+++   524	
.oracle/checkins/batch-4.md:4557: trailing whitespace.
+++   609	
.oracle/checkins/batch-4.md:4559: trailing whitespace.
+++   636	
.oracle/checkins/batch-4.md:4561: trailing whitespace.
+++   646	
.oracle/checkins/batch-4.md:4563: trailing whitespace.
+++   840	
.oracle/checkins/batch-4.md:4565: trailing whitespace.
+++   841	
.oracle/checkins/batch-4.md:4567: trailing whitespace.
+++   956	
.oracle/checkins/batch-4.md:4569: trailing whitespace.
+++   966	
.oracle/checkins/batch-4.md:4571: trailing whitespace.
+++   968	
.oracle/checkins/batch-4.md:4573: trailing whitespace.
+++   973	
.oracle/checkins/batch-4.md:4575: trailing whitespace.
+++   980	
.oracle/checkins/batch-4.md:4577: trailing whitespace.
+++   981	
.oracle/checkins/batch-4.md:4579: trailing whitespace.
+++   984	
.oracle/checkins/batch-4.md:4581: trailing whitespace.
+++   985	
.oracle/checkins/batch-4.md:4583: trailing whitespace.
+++   988	
.oracle/checkins/batch-4.md:4585: trailing whitespace.
+++19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 345) 
.oracle/checkins/batch-4.md:4587: trailing whitespace.
+++19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 347) 
.oracle/checkins/batch-4.md:4589: trailing whitespace.
+++    90	
.oracle/checkins/batch-4.md:4591: trailing whitespace.
+++    97	
.oracle/checkins/batch-4.md:4593: trailing whitespace.
+++    98	
.oracle/checkins/batch-4.md:4595: trailing whitespace.
+++   125	
.oracle/checkins/batch-4.md:4597: trailing whitespace.
+++   126	
.oracle/checkins/batch-4.md:4599: trailing whitespace.
+++   140	
.oracle/checkins/batch-4.md:4601: trailing whitespace.
+++   141	
.oracle/checkins/batch-4.md:4603: trailing whitespace.
+++   149	
.oracle/checkins/batch-4.md:4605: trailing whitespace.
+++   150	
.oracle/checkins/batch-4.md:4607: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4609: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4611: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4613: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4615: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4617: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4619: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4621: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4623: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4625: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4627: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4629: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4631: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4633: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4635: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4637: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4639: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4641: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4643: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4645: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4647: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4649: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4651: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4653: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4655: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4657: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4659: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4661: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4663: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4665: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4667: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4669: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4671: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4673: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4675: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4677: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4679: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4681: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4683: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4685: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4687: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4689: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4691: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4693: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4695: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4697: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4699: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4701: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4703: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4705: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4707: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4709: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4711: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4713: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4715: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4717: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4719: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4721: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4723: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4725: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4727: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4729: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4731: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4733: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4735: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4737: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4739: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4741: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4743: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4745: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4747: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4749: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4751: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4753: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4755: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4757: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4759: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4761: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4763: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4765: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4767: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4769: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4771: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4773: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4775: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4777: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4779: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4781: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4783: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4785: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4787: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4789: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4791: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4793: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4795: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4797: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4799: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4801: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4803: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4805: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4807: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4809: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4811: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4813: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4815: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4817: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4819: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4821: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4823: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4825: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4827: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4829: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4831: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4833: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4835: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4837: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4839: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4841: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4843: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4845: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4847: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4849: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4851: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4853: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4855: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4857: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4859: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4861: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4863: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4865: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4867: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4869: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4871: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4873: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4875: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4877: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4879: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4881: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4883: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4885: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4887: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4889: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4891: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4893: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4895: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4897: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4899: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4901: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4903: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4905: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4907: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4909: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4911: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4913: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4915: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4917: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4919: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4921: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4923: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4925: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4927: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4929: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4931: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4933: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4935: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4937: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4939: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4941: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4943: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4945: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4947: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4949: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4951: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4953: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4955: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4957: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4959: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4961: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4963: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4965: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4967: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4969: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4971: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4973: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4975: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4977: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4979: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4981: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4983: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4985: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4987: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4989: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4991: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4993: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:4995: trailing whitespace.
+++   387	
.oracle/checkins/batch-4.md:4997: trailing whitespace.
+++   388	
.oracle/checkins/batch-4.md:4999: trailing whitespace.
+++   397	
.oracle/checkins/batch-4.md:5001: trailing whitespace.
+++   414	
.oracle/checkins/batch-4.md:5003: trailing whitespace.
+++   415	
.oracle/checkins/batch-4.md:5005: trailing whitespace.
+++   418	
.oracle/checkins/batch-4.md:5007: trailing whitespace.
+++   421	
.oracle/checkins/batch-4.md:5009: trailing whitespace.
+++   423	
.oracle/checkins/batch-4.md:5011: trailing whitespace.
+++   424	
.oracle/checkins/batch-4.md:5013: trailing whitespace.
+++   427	
.oracle/checkins/batch-4.md:5015: trailing whitespace.
+++   451	
.oracle/checkins/batch-4.md:5017: trailing whitespace.
+++   452	
.oracle/checkins/batch-4.md:5019: trailing whitespace.
+++   459	
.oracle/checkins/batch-4.md:5021: trailing whitespace.
+++   467	
.oracle/checkins/batch-4.md:5023: trailing whitespace.
+++   478	
.oracle/checkins/batch-4.md:5025: trailing whitespace.
+++   488	
.oracle/checkins/batch-4.md:5027: trailing whitespace.
+++   513	
.oracle/checkins/batch-4.md:5029: trailing whitespace.
+++   514	
.oracle/checkins/batch-4.md:5031: trailing whitespace.
+++   519	
.oracle/checkins/batch-4.md:5033: trailing whitespace.
+++   520	
.oracle/checkins/batch-4.md:5035: trailing whitespace.
+++  1343	
.oracle/checkins/batch-4.md:5037: trailing whitespace.
+++  1348	
.oracle/checkins/batch-4.md:5039: trailing whitespace.
+++  1382	
.oracle/checkins/batch-4.md:5041: trailing whitespace.
+++  1383	
.oracle/checkins/batch-4.md:5043: trailing whitespace.
+++  1391	
.oracle/checkins/batch-4.md:5045: trailing whitespace.
+++  1392	
.oracle/checkins/batch-4.md:5047: trailing whitespace.
+++  1401	
.oracle/checkins/batch-4.md:5049: trailing whitespace.
+++  1402	
.oracle/checkins/batch-4.md:5051: trailing whitespace.
+++  1421	
.oracle/checkins/batch-4.md:5053: trailing whitespace.
+++  1426	
.oracle/checkins/batch-4.md:5055: trailing whitespace.
+++  1428	
.oracle/checkins/batch-4.md:5057: trailing whitespace.
+++  1429	
.oracle/checkins/batch-4.md:5059: trailing whitespace.
+++  1434	
.oracle/checkins/batch-4.md:5061: trailing whitespace.
+++  1445	
.oracle/checkins/batch-4.md:5063: trailing whitespace.
+++  2014	
.oracle/checkins/batch-4.md:5065: trailing whitespace.
+++  2019	
.oracle/checkins/batch-4.md:5067: trailing whitespace.
+++  2041	
.oracle/checkins/batch-4.md:5069: trailing whitespace.
+++  2042	
.oracle/checkins/batch-4.md:5071: trailing whitespace.
+++  2065	
.oracle/checkins/batch-4.md:5073: trailing whitespace.
+++  2394	
.oracle/checkins/batch-4.md:5075: trailing whitespace.
+++  2411	
.oracle/checkins/batch-4.md:5077: trailing whitespace.
+++  2417	
.oracle/checkins/batch-4.md:5079: trailing whitespace.
+++  2425	
.oracle/checkins/batch-4.md:5081: trailing whitespace.
+++  2432	
.oracle/checkins/batch-4.md:5083: trailing whitespace.
+++  2436	
.oracle/checkins/batch-4.md:5085: trailing whitespace.
+++  1480	
.oracle/checkins/batch-4.md:5087: trailing whitespace.
+++  1497	
.oracle/checkins/batch-4.md:5089: trailing whitespace.
+++  1525	
.oracle/checkins/batch-4.md:5091: trailing whitespace.
+++  1526	
.oracle/checkins/batch-4.md:5093: trailing whitespace.
+++  1533	
.oracle/checkins/batch-4.md:5095: trailing whitespace.
+++  1534	
.oracle/checkins/batch-4.md:5097: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5099: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5101: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5103: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5105: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5107: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5109: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5111: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5113: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5115: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5117: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5119: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5121: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5123: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5125: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5127: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5129: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5131: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5133: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5135: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5137: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5139: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5141: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5143: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5145: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5147: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5149: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5151: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5153: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5155: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5157: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5159: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5161: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5163: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5165: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5167: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5169: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5171: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5173: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5175: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5177: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5179: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5181: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5183: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5185: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5187: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5189: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5191: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5193: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5195: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5197: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5199: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5201: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5203: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5205: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5207: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5209: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5211: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5213: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5215: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5217: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5219: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5221: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5223: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5225: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5227: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5229: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5231: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5233: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5235: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5237: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5239: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5241: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5243: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5245: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5247: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5249: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5251: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5253: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5255: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5257: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5259: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5261: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5263: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5265: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5267: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5269: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5271: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5273: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5275: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5277: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5279: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5281: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5283: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5285: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5287: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5289: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5291: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5293: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5295: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5297: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5299: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5301: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5303: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5305: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5307: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5309: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5311: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5313: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5315: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5317: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5319: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5321: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5323: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5325: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5327: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5329: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5331: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5333: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5335: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5337: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5339: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5341: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5343: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5345: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5347: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5349: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5351: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5353: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5355: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5357: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5359: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5361: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5363: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5365: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5367: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5369: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5371: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5373: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5375: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5377: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5379: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5381: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5383: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5385: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5387: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5389: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5391: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5393: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5395: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5397: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5399: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5401: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5403: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5405: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5407: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5409: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5411: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5413: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5415: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5417: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5419: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5421: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5423: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5425: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5427: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5429: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5431: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5433: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5435: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5437: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5439: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5441: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5443: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5445: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5447: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5449: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5451: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5453: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5455: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5457: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5459: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5461: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5463: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5465: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5467: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5469: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5471: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5473: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5475: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5477: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5479: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5481: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5483: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5485: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5487: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5489: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5491: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5493: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5495: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5497: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5499: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5501: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5503: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5505: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5507: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5509: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5511: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5513: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5515: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5517: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5519: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5521: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5523: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5525: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5527: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5529: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5531: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5533: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5535: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5537: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5539: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5541: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5543: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5545: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5547: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5549: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5551: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5553: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5555: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5557: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5559: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5561: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5563: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5565: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5567: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5569: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5571: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5573: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5575: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5577: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5579: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5581: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5583: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5585: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5587: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5589: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5591: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5593: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5595: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5597: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5599: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5601: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5603: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5605: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5607: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5609: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5611: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5613: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5615: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5617: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5619: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5621: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5623: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5625: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5627: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5629: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5631: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5633: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5635: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5637: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5639: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5641: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5643: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5645: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5647: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5649: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5651: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5653: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5655: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5657: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5659: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5661: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5663: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5665: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5667: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5669: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5671: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5673: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5675: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5677: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5679: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5681: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5683: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5685: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5687: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5689: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5691: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5693: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5695: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5697: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5699: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5701: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5703: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5705: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5707: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5709: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5711: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5713: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5715: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5717: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5719: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5721: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5723: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5725: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5727: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5729: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5731: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5733: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5735: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5737: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5739: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5741: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5743: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5745: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5747: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5749: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5751: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5753: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5755: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5757: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5759: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5761: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5763: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5765: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5767: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5769: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5771: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5773: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5775: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5777: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5779: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5781: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5783: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5785: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5787: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5789: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5791: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5793: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5795: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5797: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5799: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5801: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5803: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5805: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5807: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5809: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5811: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5813: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5815: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5817: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5819: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5821: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5823: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5825: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5827: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5829: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5831: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5833: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5835: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5837: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5839: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5841: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5843: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5845: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5847: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5849: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5851: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5853: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5855: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5857: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5859: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5861: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5863: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5865: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5867: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5869: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5871: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5873: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5875: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5877: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5879: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5881: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5883: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5885: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5887: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5889: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5891: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5893: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5895: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5897: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5899: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5901: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5903: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5905: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5907: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5909: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5911: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5913: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5915: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5917: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5919: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5921: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5923: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5925: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5927: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5929: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5931: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5933: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5935: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5937: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5939: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5941: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5943: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5945: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5947: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5949: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5951: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5953: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5955: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5957: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5959: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5961: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5963: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5965: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5967: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5969: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5971: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5973: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5975: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5977: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5979: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5981: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5983: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5985: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5987: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5989: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5991: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5993: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5995: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5997: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:5999: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6001: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6003: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6005: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6007: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6009: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6011: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6013: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6015: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6017: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6019: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6021: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6023: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6025: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6027: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6029: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6031: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6033: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6035: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6037: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6039: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6041: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6043: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6045: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6047: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6049: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6051: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6053: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6055: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6057: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6059: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6061: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6063: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6065: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6067: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6069: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6071: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6073: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6075: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6077: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6079: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6081: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6083: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6085: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6087: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6089: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6091: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6093: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6095: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6097: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6099: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6101: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6103: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6105: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6107: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6109: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6111: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6113: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6115: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6117: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6119: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6121: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6123: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6125: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6127: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6129: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6131: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6133: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6135: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6137: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6139: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6141: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6143: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6145: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6147: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6149: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6151: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6153: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6155: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6157: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6159: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6161: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6163: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6165: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6167: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6169: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6171: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6173: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6175: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6177: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6179: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6181: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6183: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6185: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6187: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6189: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6191: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6193: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6195: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6197: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6199: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6201: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6203: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6205: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6207: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6209: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6211: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6213: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6215: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6217: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6219: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6221: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6223: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6225: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6227: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6229: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6231: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6233: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6235: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6237: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6239: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6241: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6243: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6245: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6247: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6249: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6251: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6253: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6255: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6257: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6259: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6261: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6263: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6265: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6267: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6269: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6271: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6273: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6275: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6277: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6279: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6281: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6283: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6285: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6287: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6289: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6291: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6293: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6295: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6297: trailing whitespace.
+++    50	
.oracle/checkins/batch-4.md:6299: trailing whitespace.
+++    52	
.oracle/checkins/batch-4.md:6301: trailing whitespace.
+++    71	
.oracle/checkins/batch-4.md:6303: trailing whitespace.
+++    72	
.oracle/checkins/batch-4.md:6305: trailing whitespace.
+++    88	
.oracle/checkins/batch-4.md:6307: trailing whitespace.
+++   103	
.oracle/checkins/batch-4.md:6309: trailing whitespace.
+++   112	
.oracle/checkins/batch-4.md:6311: trailing whitespace.
+++   113	
.oracle/checkins/batch-4.md:6313: trailing whitespace.
+++   120	
.oracle/checkins/batch-4.md:6315: trailing whitespace.
+++   122	
.oracle/checkins/batch-4.md:6317: trailing whitespace.
+++   126	
.oracle/checkins/batch-4.md:6319: trailing whitespace.
+++   127	
.oracle/checkins/batch-4.md:6321: trailing whitespace.
+++   134	
.oracle/checkins/batch-4.md:6323: trailing whitespace.
+++   139	
.oracle/checkins/batch-4.md:6325: trailing whitespace.
+++   145	
.oracle/checkins/batch-4.md:6327: trailing whitespace.
+++   146	
.oracle/checkins/batch-4.md:6329: trailing whitespace.
+++   163	
.oracle/checkins/batch-4.md:6331: trailing whitespace.
+++   166	
.oracle/checkins/batch-4.md:6333: trailing whitespace.
+++   170	
.oracle/checkins/batch-4.md:6335: trailing whitespace.
+++   171	
.oracle/checkins/batch-4.md:6337: trailing whitespace.
+++   179	
.oracle/checkins/batch-4.md:6339: trailing whitespace.
+++   182	
.oracle/checkins/batch-4.md:6341: trailing whitespace.
+++   183	
.oracle/checkins/batch-4.md:6343: trailing whitespace.
+++   186	
.oracle/checkins/batch-4.md:6345: trailing whitespace.
+++   188	
.oracle/checkins/batch-4.md:6347: trailing whitespace.
+++   190	
.oracle/checkins/batch-4.md:6349: trailing whitespace.
+++   191	
.oracle/checkins/batch-4.md:6351: trailing whitespace.
+++   194	
.oracle/checkins/batch-4.md:6353: trailing whitespace.
+++   195	
.oracle/checkins/batch-4.md:6355: trailing whitespace.
+++   198	
.oracle/checkins/batch-4.md:6357: trailing whitespace.
+++  2193	
.oracle/checkins/batch-4.md:6359: trailing whitespace.
+++  2206	
.oracle/checkins/batch-4.md:6361: trailing whitespace.
+++  2212	
.oracle/checkins/batch-4.md:6363: trailing whitespace.
+++  2213	
.oracle/checkins/batch-4.md:6365: trailing whitespace.
+++  2238	
.oracle/checkins/batch-4.md:6367: trailing whitespace.
+++  2240	
.oracle/checkins/batch-4.md:6369: trailing whitespace.
+++  2243	
.oracle/checkins/batch-4.md:6371: trailing whitespace.
+++  2244	
.oracle/checkins/batch-4.md:6373: trailing whitespace.
+++  2266	
.oracle/checkins/batch-4.md:6375: trailing whitespace.
+++  2268	
.oracle/checkins/batch-4.md:6377: trailing whitespace.
+++  2277	
.oracle/checkins/batch-4.md:6379: trailing whitespace.
+++  2278	
.oracle/checkins/batch-4.md:6381: trailing whitespace.
+++  2282	
.oracle/checkins/batch-4.md:6383: trailing whitespace.
+++  2283	
.oracle/checkins/batch-4.md:6385: trailing whitespace.
+++  2286	
.oracle/checkins/batch-4.md:6387: trailing whitespace.
+++  2303	
.oracle/checkins/batch-4.md:6389: trailing whitespace.
+++  2309	
.oracle/checkins/batch-4.md:6391: trailing whitespace.
+++  2314	
.oracle/checkins/batch-4.md:6393: trailing whitespace.
+++  2315	
.oracle/checkins/batch-4.md:6395: trailing whitespace.
+++  2318	
.oracle/checkins/batch-4.md:6397: trailing whitespace.
+++  2327	
.oracle/checkins/batch-4.md:6399: trailing whitespace.
+++  2337	
.oracle/checkins/batch-4.md:6401: trailing whitespace.
+++  2343	
.oracle/checkins/batch-4.md:6403: trailing whitespace.
+++  2346	
.oracle/checkins/batch-4.md:6405: trailing whitespace.
+++  2347	
.oracle/checkins/batch-4.md:6407: trailing whitespace.
+++  2350	
.oracle/checkins/batch-4.md:6409: trailing whitespace.
+++  2366	
.oracle/checkins/batch-4.md:6411: trailing whitespace.
+++  2375	
.oracle/checkins/batch-4.md:6413: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6415: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6417: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6419: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6421: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6423: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6425: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6427: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6429: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6431: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6433: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6435: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6437: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6439: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6441: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6443: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6445: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6447: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6449: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6451: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6453: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6455: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6457: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6459: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6461: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6463: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6465: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6467: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6469: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6471: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6473: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6475: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6477: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6479: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6481: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6483: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6485: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6487: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6489: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6491: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6493: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6495: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6497: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6499: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6501: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6503: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6505: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6507: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6509: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6511: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6513: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6515: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6517: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6519: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6521: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6523: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6525: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6527: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6529: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6531: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6533: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6535: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6537: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6539: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6541: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6543: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6545: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6547: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6549: trailing whitespace.
+++ 
.oracle/checkins/batch-4.md:6551: trailing whitespace.
+++  1010	
.oracle/checkins/batch-4.md:6553: trailing whitespace.
+++  1022	
.oracle/checkins/batch-4.md:6555: trailing whitespace.
+++  1025	
.oracle/checkins/batch-4.md:6557: trailing whitespace.
+++  1031	
.oracle/checkins/batch-4.md:6559: trailing whitespace.
+++  1040	
.oracle/checkins/batch-4.md:6561: trailing whitespace.
+++  1045	
.oracle/checkins/batch-4.md:6563: trailing whitespace.
+++  1049	
.oracle/checkins/batch-4.md:6565: trailing whitespace.
+++  1083	
.oracle/checkins/batch-4.md:6567: trailing whitespace.
+++  1086	
.oracle/checkins/batch-4.md:6569: trailing whitespace.
+++  1087	
.oracle/checkins/batch-4.md:6571: trailing whitespace.
+++  1091	
.oracle/checkins/batch-4.md:6573: trailing whitespace.
+++  1092	
.oracle/checkins/batch-4.md:6575: trailing whitespace.
+++  1095	
.oracle/checkins/batch-4.md:6577: trailing whitespace.
+++  1102	
.oracle/checkins/batch-4.md:6579: trailing whitespace.
+++  1105	
.oracle/checkins/batch-4.md:6581: trailing whitespace.
+++     4	
.oracle/checkins/batch-4.md:6583: trailing whitespace.
+++   356	
.oracle/checkins/batch-4.md:6585: trailing whitespace.
+++   357	
.oracle/checkins/batch-4.md:6587: trailing whitespace.
+++   360	
.oracle/checkins/batch-4.md:6589: trailing whitespace.
+++   363	
.oracle/checkins/batch-4.md:6591: trailing whitespace.
+++   374	
.oracle/checkins/batch-4.md:6593: trailing whitespace.
+++   405	
.oracle/checkins/batch-4.md:6595: trailing whitespace.
+++   411	
.oracle/checkins/batch-4.md:6597: trailing whitespace.
+++   418	
.oracle/checkins/batch-4.md:6599: trailing whitespace.
+++   427	
.oracle/checkins/batch-4.md:6601: trailing whitespace.
+++   488	
.oracle/checkins/batch-4.md:6603: trailing whitespace.
+++   489	
.oracle/checkins/batch-4.md:6605: trailing whitespace.
+++   498	
.oracle/checkins/batch-4.md:6607: trailing whitespace.
+++   499	
.oracle/checkins/batch-4.md:6609: trailing whitespace.
+++   504	
.oracle/checkins/batch-4.md:6611: trailing whitespace.
+++   507	
.oracle/checkins/batch-4.md:6613: trailing whitespace.
+++   524	
.oracle/checkins/batch-4.md:6615: trailing whitespace.
+++   525	
.oracle/checkins/batch-4.md:6617: trailing whitespace.
+++   873	
.oracle/checkins/batch-4.md:6619: trailing whitespace.
+++   882	
.oracle/checkins/batch-4.md:6621: trailing whitespace.
+++   883	
.oracle/checkins/batch-4.md:6623: trailing whitespace.
+++   886	
.oracle/checkins/batch-4.md:6625: trailing whitespace.
+++   888	
.oracle/checkins/batch-4.md:6627: trailing whitespace.
+++   889	
.oracle/checkins/batch-4.md:6629: trailing whitespace.
+++   896	
.oracle/checkins/batch-4.md:6631: trailing whitespace.
+++   902	
.oracle/checkins/batch-4.md:6633: trailing whitespace.
+++   903	
.oracle/checkins/batch-4.md:6635: trailing whitespace.
+++   909	
.oracle/checkins/batch-4.md:6637: trailing whitespace.
+++   912	
.oracle/checkins/batch-4.md:6639: trailing whitespace.
+++   917	
.oracle/checkins/batch-4.md:6641: trailing whitespace.
+++   919	
.oracle/checkins/batch-4.md:6643: trailing whitespace.
+++   924	
.oracle/checkins/batch-4.md:6645: trailing whitespace.
+++   710	
.oracle/checkins/batch-4.md:6647: trailing whitespace.
+++  1142	
.oracle/checkins/batch-4.md:6649: trailing whitespace.
+++  1146	
.oracle/checkins/batch-4.md:6651: trailing whitespace.
+++  1157	
.oracle/checkins/batch-4.md:6653: trailing whitespace.
+++  1164	
.oracle/checkins/batch-4.md:6655: trailing whitespace.
+++  1169	
.oracle/checkins/batch-4.md:6657: trailing whitespace.
+++  1178	
.oracle/checkins/batch-4.md:6659: trailing whitespace.
+++  1206	
.oracle/checkins/batch-4.md:6661: trailing whitespace.
+++   968	
.oracle/checkins/batch-4.md:6663: trailing whitespace.
+++  1087	
.oracle/checkins/batch-4.md:6665: trailing whitespace.
+++  1109	
.oracle/checkins/batch-4.md:6667: trailing whitespace.
+++  2170	
.oracle/checkins/batch-4.md:6669: trailing whitespace.
+++  2185	
.oracle/checkins/batch-4.md:6671: trailing whitespace.
+++  2191	
.oracle/checkins/batch-4.md:6673: trailing whitespace.
+++  2199	
.oracle/checkins/batch-4.md:6675: trailing whitespace.
+++  2203	
.oracle/checkins/batch-4.md:6677: trailing whitespace.
+++  2217	
.oracle/checkins/batch-4.md:6679: trailing whitespace.
+++  2220	
.oracle/checkins/batch-4.md:6681: trailing whitespace.
+++  2228	
.oracle/checkins/batch-4.md:6683: trailing whitespace.
+++compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 
.oracle/checkins/batch-4.md:6685: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6687: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6689: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6691: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6693: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6695: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6697: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6699: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6701: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6703: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6705: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6707: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6709: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6711: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6713: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6715: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6717: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6719: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6721: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6723: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6725: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6727: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6729: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6731: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6733: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6735: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6737: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6739: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6741: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6743: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6745: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6747: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6749: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6751: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6753: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6755: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6757: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6759: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6761: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6763: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6765: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6767: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6769: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6771: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6773: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6775: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6777: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6779: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6781: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6783: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6785: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6787: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6789: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6791: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6793: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6795: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6797: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6799: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6801: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6803: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6805: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6807: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6809: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6811: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6813: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6815: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6817: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6819: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6821: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6823: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6825: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6827: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6829: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6831: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6833: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6835: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6837: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6839: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6841: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6843: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6845: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6847: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6849: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6851: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6853: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6855: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6857: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6859: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6861: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6863: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6865: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6867: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6869: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6871: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6873: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6875: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6877: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6879: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6881: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6883: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6885: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6887: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6889: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6891: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6893: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6895: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6897: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6899: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6901: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6903: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6905: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6907: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6909: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6911: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6913: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6915: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6917: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6919: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6921: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6923: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6925: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6927: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6929: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6931: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6933: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6935: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6937: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6939: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6941: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6943: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6945: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6947: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6949: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6951: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6953: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6955: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6957: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6959: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6961: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6963: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6965: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6967: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6969: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6971: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6973: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6975: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6977: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6979: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6981: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6983: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6985: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6987: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6989: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6991: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6993: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6995: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6997: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:6999: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7001: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7003: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7005: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7007: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7009: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7011: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7013: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7015: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7017: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7019: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7021: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7023: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7025: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7027: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7029: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7031: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7033: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7035: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7037: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7039: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7041: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7043: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7045: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7047: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7049: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7051: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7053: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7055: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7057: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7059: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7061: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7063: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7065: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7067: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7069: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7071: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7073: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7075: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7077: trailing whitespace.
++ 
.oracle/checkins/batch-4.md:7079: trailing whitespace.
++   135	
.oracle/checkins/batch-4.md:7081: trailing whitespace.
++   138	
.oracle/checkins/batch-4.md:7083: trailing whitespace.
++   143	
.oracle/checkins/batch-4.md:7085: trailing whitespace.
++   144	
.oracle/checkins/batch-4.md:7087: trailing whitespace.
++   149	
.oracle/checkins/batch-4.md:7089: trailing whitespace.
++   152	
.oracle/checkins/batch-4.md:7091: trailing whitespace.
++   155	
.oracle/checkins/batch-4.md:7093: trailing whitespace.
++   156	
.oracle/checkins/batch-4.md:7095: trailing whitespace.
++   160	
.oracle/checkins/batch-4.md:7097: trailing whitespace.
++   163	
.oracle/checkins/batch-4.md:7099: trailing whitespace.
++   166	
.oracle/checkins/batch-4.md:7101: trailing whitespace.
++   167	
.oracle/checkins/batch-4.md:7103: trailing whitespace.
++   183	
.oracle/checkins/batch-4.md:7105: trailing whitespace.
++   186	
.oracle/checkins/batch-4.md:7107: trailing whitespace.
++   189	
.oracle/checkins/batch-4.md:7109: trailing whitespace.
++   190	
.oracle/checkins/batch-4.md:7111: trailing whitespace.
++   196	
.oracle/checkins/batch-4.md:7113: trailing whitespace.
++   198	
.oracle/checkins/batch-4.md:7115: trailing whitespace.
++   202	
.oracle/checkins/batch-4.md:7117: trailing whitespace.
++   203	
.oracle/checkins/batch-4.md:7119: trailing whitespace.
++   253	
.oracle/checkins/batch-4.md:7121: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:7123: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:7125: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:7127: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:7129: trailing whitespace.
++++ 
.oracle/checkins/batch-4.md:7197: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7199: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7283: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7285: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7303: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7308: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7311: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7312: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7355: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7372: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7404: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7405: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7409: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7441: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7442: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7459: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7481: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7490: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7519: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7542: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7545: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7546: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7591: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:7647: trailing whitespace.
+   710	
.oracle/checkins/batch-4.md:7650: trailing whitespace.
+   713	
.oracle/checkins/batch-4.md:7658: trailing whitespace.
+   721	
.oracle/checkins/batch-4.md:7717: trailing whitespace.
+   405	
.oracle/checkins/batch-4.md:7718: trailing whitespace.
+   406	
.oracle/checkins/batch-4.md:7721: trailing whitespace.
+   409	
.oracle/checkins/batch-4.md:7731: trailing whitespace.
+   419	
.oracle/checkins/batch-4.md:7732: trailing whitespace.
+   420	
.oracle/checkins/batch-4.md:7745: trailing whitespace.
+   433	
.oracle/checkins/batch-4.md:7746: trailing whitespace.
+   434	
.oracle/checkins/batch-4.md:7758: trailing whitespace.
+   446	
.oracle/checkins/batch-4.md:7759: trailing whitespace.
+   447	
.oracle/checkins/batch-4.md:7774: trailing whitespace.
+   462	
.oracle/checkins/batch-4.md:7785: trailing whitespace.
+   473	
.oracle/checkins/batch-4.md:7786: trailing whitespace.
+   474	
.oracle/checkins/batch-4.md:7789: trailing whitespace.
+   477	
.oracle/checkins/batch-4.md:7796: trailing whitespace.
+   484	
.oracle/checkins/batch-4.md:7804: trailing whitespace.
+   492	
.oracle/checkins/batch-4.md:7813: trailing whitespace.
+   501	
.oracle/checkins/batch-4.md:7833: trailing whitespace.
+   521	
.oracle/checkins/batch-4.md:7837: trailing whitespace.
+   525	
.oracle/checkins/batch-4.md:7858: trailing whitespace.
+   546	
.oracle/checkins/batch-4.md:7862: trailing whitespace.
+   550	
.oracle/checkins/batch-4.md:7866: trailing whitespace.
+   554	
.oracle/checkins/batch-4.md:7868: trailing whitespace.
+   556	
.oracle/checkins/batch-4.md:7877: trailing whitespace.
+   565	
.oracle/checkins/batch-4.md:7966: trailing whitespace.
+   654	
.oracle/checkins/batch-4.md:7998: trailing whitespace.
+   825	
.oracle/checkins/batch-4.md:7999: trailing whitespace.
+   826	
.oracle/checkins/batch-4.md:8015: trailing whitespace.
+   842	
.oracle/checkins/batch-4.md:8016: trailing whitespace.
+   843	
.oracle/checkins/batch-4.md:8023: trailing whitespace.
+   850	
.oracle/checkins/batch-4.md:8024: trailing whitespace.
+   851	
.oracle/checkins/batch-4.md:8058: trailing whitespace.
+   885	
.oracle/checkins/batch-4.md:8059: trailing whitespace.
+   886	
.oracle/checkins/batch-4.md:8176: trailing whitespace.
+  1003	
.oracle/checkins/batch-4.md:8186: trailing whitespace.
+  1013	
.oracle/checkins/batch-4.md:8188: trailing whitespace.
+  1015	
.oracle/checkins/batch-4.md:8193: trailing whitespace.
+  1020	
.oracle/checkins/batch-4.md:8331: trailing whitespace.
+   264	
.oracle/checkins/batch-4.md:8341: trailing whitespace.
+   274	
.oracle/checkins/batch-4.md:8342: trailing whitespace.
+   275	
.oracle/checkins/batch-4.md:8346: trailing whitespace.
+   279	
.oracle/checkins/batch-4.md:8347: trailing whitespace.
+   280	
.oracle/checkins/batch-4.md:8355: trailing whitespace.
+   288	
.oracle/checkins/batch-4.md:8356: trailing whitespace.
+   289	
.oracle/checkins/batch-4.md:8361: trailing whitespace.
+   294	
.oracle/checkins/batch-4.md:8362: trailing whitespace.
+   295	
.oracle/checkins/batch-4.md:8369: trailing whitespace.
+   302	
.oracle/checkins/batch-4.md:8370: trailing whitespace.
+   303	
.oracle/checkins/batch-4.md:8373: trailing whitespace.
+   306	
.oracle/checkins/batch-4.md:8378: trailing whitespace.
+   485	
.oracle/checkins/batch-4.md:8379: trailing whitespace.
+   486	
.oracle/checkins/batch-4.md:8383: trailing whitespace.
+   490	
.oracle/checkins/batch-4.md:8384: trailing whitespace.
+   491	
.oracle/checkins/batch-4.md:8388: trailing whitespace.
+   495	
.oracle/checkins/batch-4.md:8389: trailing whitespace.
+   496	
.oracle/checkins/batch-4.md:8392: trailing whitespace.
+   499	
.oracle/checkins/batch-4.md:8409: trailing whitespace.
+   516	
.oracle/checkins/batch-4.md:8410: trailing whitespace.
+   517	
.oracle/checkins/batch-4.md:8434: trailing whitespace.
+   170	
.oracle/checkins/batch-4.md:8435: trailing whitespace.
+   171	
.oracle/checkins/batch-4.md:8438: trailing whitespace.
+   174	
.oracle/checkins/batch-4.md:8455: trailing whitespace.
+   191	
.oracle/checkins/batch-4.md:8458: trailing whitespace.
+   194	
.oracle/checkins/batch-4.md:8464: trailing whitespace.
+   200	
.oracle/checkins/batch-4.md:8472: trailing whitespace.
+   208	
.oracle/checkins/batch-4.md:8501: trailing whitespace.
+   351	
.oracle/checkins/batch-4.md:8515: trailing whitespace.
+   365	
.oracle/checkins/batch-4.md:8531: trailing whitespace.
+   381	
.oracle/checkins/batch-4.md:8532: trailing whitespace.
+   382	
.oracle/checkins/batch-4.md:8537: trailing whitespace.
+   387	
.oracle/checkins/batch-4.md:8538: trailing whitespace.
+   388	
.oracle/checkins/batch-4.md:8548: trailing whitespace.
+   162	
.oracle/checkins/batch-4.md:8549: trailing whitespace.
+   163	
.oracle/checkins/batch-4.md:8552: trailing whitespace.
+   166	
.oracle/checkins/batch-4.md:8562: trailing whitespace.
+   176	
.oracle/checkins/batch-4.md:8588: trailing whitespace.
+   202	
.oracle/checkins/batch-4.md:8589: trailing whitespace.
+   203	
.oracle/checkins/batch-4.md:8595: trailing whitespace.
+   298	
.oracle/checkins/batch-4.md:8604: trailing whitespace.
+   307	
.oracle/checkins/batch-4.md:8605: trailing whitespace.
+   308	
.oracle/checkins/batch-4.md:8608: trailing whitespace.
+   311	
.oracle/checkins/batch-4.md:8623: trailing whitespace.
+   326	
.oracle/checkins/batch-4.md:8624: trailing whitespace.
+   327	
.oracle/checkins/batch-4.md:8628: trailing whitespace.
+   331	
.oracle/checkins/batch-4.md:8629: trailing whitespace.
+   332	
.oracle/checkins/batch-4.md:8632: trailing whitespace.
+   335	
.oracle/checkins/batch-4.md:8657: trailing whitespace.
+   225	
.oracle/checkins/batch-4.md:8658: trailing whitespace.
+   226	
.oracle/checkins/batch-4.md:8661: trailing whitespace.
+   229	
.oracle/checkins/batch-4.md:8679: trailing whitespace.
+   247	
.oracle/checkins/batch-4.md:8680: trailing whitespace.
+   248	
.oracle/checkins/batch-4.md:8686: trailing whitespace.
+   254	
.oracle/checkins/batch-4.md:8689: trailing whitespace.
+   257	
.oracle/checkins/batch-4.md:8697: trailing whitespace.
+   265	
.oracle/checkins/batch-4.md:8723: trailing whitespace.
+   291	
.oracle/checkins/batch-4.md:8728: trailing whitespace.
+  1083	
.oracle/checkins/batch-4.md:8732: trailing whitespace.
+  1087	
.oracle/checkins/batch-4.md:8733: trailing whitespace.
+  1088	
.oracle/checkins/batch-4.md:8752: trailing whitespace.
+  1107	
.oracle/checkins/batch-4.md:8753: trailing whitespace.
+  1108	
.oracle/checkins/batch-4.md:8765: trailing whitespace.
+  1120	
.oracle/checkins/batch-4.md:8766: trailing whitespace.
+  1121	
.oracle/checkins/batch-4.md:8783: trailing whitespace.
+  1282	
.oracle/checkins/batch-4.md:8784: trailing whitespace.
+  1283	
.oracle/checkins/batch-4.md:8787: trailing whitespace.
+  1286	
.oracle/checkins/batch-4.md:8788: trailing whitespace.
+  1287	
.oracle/checkins/batch-4.md:8791: trailing whitespace.
+  1290	
.oracle/checkins/batch-4.md:8805: trailing whitespace.
+  1304	
.oracle/checkins/batch-4.md:8806: trailing whitespace.
+  1305	
.oracle/checkins/batch-4.md:8811: trailing whitespace.
+  1310	
.oracle/checkins/batch-4.md:8828: trailing whitespace.
+   246	
.oracle/checkins/batch-4.md:8829: trailing whitespace.
+   247	
.oracle/checkins/batch-4.md:8832: trailing whitespace.
+   250	
.oracle/checkins/batch-4.md:8866: trailing whitespace.
+   284	
.oracle/checkins/batch-4.md:8867: trailing whitespace.
+   285	
.oracle/checkins/batch-4.md:8882: trailing whitespace.
+   300	
.oracle/checkins/batch-4.md:8883: trailing whitespace.
+   301	
.oracle/checkins/batch-4.md:8886: trailing whitespace.
+   304	
.oracle/checkins/batch-4.md:8899: trailing whitespace.
+   317	
.oracle/checkins/batch-4.md:8914: trailing whitespace.
+   332	
.oracle/checkins/batch-4.md:8968: trailing whitespace.
+   386	
.oracle/checkins/batch-4.md:8969: trailing whitespace.
+   387	
.oracle/checkins/batch-4.md:8973: trailing whitespace.
+  1028	
.oracle/checkins/batch-4.md:8976: trailing whitespace.
+  1031	
.oracle/checkins/batch-4.md:8977: trailing whitespace.
+  1032	
.oracle/checkins/batch-4.md:8980: trailing whitespace.
+  1035	
.oracle/checkins/batch-4.md:8989: trailing whitespace.
+  1044	
.oracle/checkins/batch-4.md:8990: trailing whitespace.
+  1045	
.oracle/checkins/batch-4.md:9016: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9017: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9047: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9057: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9064: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9071: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9074: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9075: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9086: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9089: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9099: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9119: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9130: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9131: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9150: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9151: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9190: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9191: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9195: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9196: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9262: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9275: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9284: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9291: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9292: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9318: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9322: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9326: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9331: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9336: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9350: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9363: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9366: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9373: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9379: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9467: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9475: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9476: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:9663: trailing whitespace.
+   681	
.oracle/checkins/batch-4.md:9673: trailing whitespace.
+   691	
.oracle/checkins/batch-4.md:9723: trailing whitespace.
+   741	
.oracle/checkins/batch-4.md:9757: trailing whitespace.
+   775	
.oracle/checkins/batch-4.md:9764: trailing whitespace.
+   782	
.oracle/checkins/batch-4.md:9766: trailing whitespace.
+   784	
.oracle/checkins/batch-4.md:9768: trailing whitespace.
+   786	
.oracle/checkins/batch-4.md:9769: trailing whitespace.
+   787	
.oracle/checkins/batch-4.md:9772: trailing whitespace.
+   790	
.oracle/checkins/batch-4.md:9778: trailing whitespace.
+   796	
.oracle/checkins/batch-4.md:9779: trailing whitespace.
+   797	
.oracle/checkins/batch-4.md:9807: trailing whitespace.
+   825	
.oracle/checkins/batch-4.md:9854: trailing whitespace.
+    69	
.oracle/checkins/batch-4.md:9855: trailing whitespace.
+    70	
.oracle/checkins/batch-4.md:9864: trailing whitespace.
+    79	
.oracle/checkins/batch-4.md:9895: trailing whitespace.
+   110	
.oracle/checkins/batch-4.md:9896: trailing whitespace.
+   111	
.oracle/checkins/batch-4.md:9939: trailing whitespace.
+   154	
.oracle/checkins/batch-4.md:9941: trailing whitespace.
+   156	
.oracle/checkins/batch-4.md:9942: trailing whitespace.
+   157	
.oracle/checkins/batch-4.md:9952: trailing whitespace.
+   167	
.oracle/checkins/batch-4.md:9978: trailing whitespace.
+  1327	
.oracle/checkins/batch-4.md:9991: trailing whitespace.
+  1340	
.oracle/checkins/batch-4.md:9996: trailing whitespace.
+  1345	
.oracle/checkins/batch-4.md:10032: trailing whitespace.
+   885	
.oracle/checkins/batch-4.md:10033: trailing whitespace.
+   886	
.oracle/checkins/batch-4.md:10059: trailing whitespace.
+   912	
.oracle/checkins/batch-4.md:10086: trailing whitespace.
+   167	
.oracle/checkins/batch-4.md:10140: trailing whitespace.
+   221	
.oracle/checkins/batch-4.md:10141: trailing whitespace.
+   222	
.oracle/checkins/batch-4.md:10379: trailing whitespace.
+    81	
.oracle/checkins/batch-4.md:10380: trailing whitespace.
+    82	
.oracle/checkins/batch-4.md:10384: trailing whitespace.
+    86	
.oracle/checkins/batch-4.md:10391: trailing whitespace.
+    93	
.oracle/checkins/batch-4.md:10392: trailing whitespace.
+    94	
.oracle/checkins/batch-4.md:10395: trailing whitespace.
+    97	
.oracle/checkins/batch-4.md:10410: trailing whitespace.
+   112	
.oracle/checkins/batch-4.md:10411: trailing whitespace.
+   113	
.oracle/checkins/batch-4.md:10414: trailing whitespace.
+   116	
.oracle/checkins/batch-4.md:10432: trailing whitespace.
+   273	
.oracle/checkins/batch-4.md:10452: trailing whitespace.
+   293	
.oracle/checkins/batch-4.md:10505: trailing whitespace.
+  2490	
.oracle/checkins/batch-4.md:10514: trailing whitespace.
+  2499	
.oracle/checkins/batch-4.md:10526: trailing whitespace.
+   415	
.oracle/checkins/batch-4.md:10539: trailing whitespace.
+   428	
.oracle/checkins/batch-4.md:10561: trailing whitespace.
+   450	
.oracle/checkins/batch-4.md:10564: trailing whitespace.
+   453	
.oracle/checkins/batch-4.md:10568: trailing whitespace.
+   457	
.oracle/checkins/batch-4.md:10574: trailing whitespace.
+   463	
.oracle/checkins/batch-4.md:10580: trailing whitespace.
+   469	
.oracle/checkins/batch-4.md:10586: trailing whitespace.
+   475	

exec
/bin/zsh -lc 'git show --format=fuller --stat 06d94e4a && git show --format= --find-renames 06d94e4a -- vibecomfy/workflow.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 06d94e4a530e67ac72fd805c20b302b83666e963
Author:     POM <peter@omalley.io>
AuthorDate: Thu Aug 13 22:39:56 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Thu Aug 13 22:39:56 2026 +0200

    megado run2 Batch K: declare _workflow_context_token, direct field access, copy memo for bound workflows, collision-safe unseeded UID minting

 vibecomfy/workflow.py | 49 +++++++++++++++++++++++++++++++++++--------------
 1 file changed, 35 insertions(+), 14 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/vibecomfy/workflow.py b/vibecomfy/workflow.py
index 5075fc4a..ffba2b5b 100644
--- a/vibecomfy/workflow.py
+++ b/vibecomfy/workflow.py
@@ -223,6 +223,7 @@ class VibeWorkflow:
     _id_map: dict[str, str] = field(default_factory=dict, init=False, repr=False)
     _manual_input_names: set[str] = field(default_factory=set, init=False, repr=False)
     _uid_counter: int = field(default=0, init=False, repr=False)
+    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)
 
     def __enter__(self) -> "VibeWorkflow":
         from vibecomfy.workflow_context import active_workflow, bind_workflow
@@ -230,12 +231,9 @@ class VibeWorkflow:
         # If ``new_workflow()`` already eagerly bound this workflow (the post-
         # revert default for emitted templates), reuse that binding rather than
         # raising — the ``with`` form is purely scoping sugar in that case.
-        if (
-            getattr(self, "_workflow_context_token", None) is not None
-            and active_workflow() is self
-        ):
+        if self._workflow_context_token is not None and active_workflow() is self:
             return self
-        if getattr(self, "_workflow_context_token", None) is not None:
+        if self._workflow_context_token is not None:
             raise RuntimeError(
                 "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
                 "block is still active."
@@ -246,7 +244,7 @@ class VibeWorkflow:
     def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
         from vibecomfy.workflow_context import reset_workflow
 
-        token = getattr(self, "_workflow_context_token", None)
+        token = self._workflow_context_token
         if token is not None:
             reset_workflow(token)
             self._workflow_context_token = None
@@ -280,14 +278,13 @@ class VibeWorkflow:
 
         The dataclass walk (``copy.deepcopy``) copies every public field —
         including ``groups`` and per-node ``mode`` — plus the private
-        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``),
-        so adding a field to the dataclass needs no ``copy()`` edit.  The
-        clone is not bound to any workflow context.
+        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``).
+        A bound workflow's live ``contextvars.Token`` cannot be meaningfully
+        deep-copied, so the deepcopy memo maps it to ``None`` up front; every
+        clone is therefore unbound (``_workflow_context_token is None``).
         """
-        cloned = copy.deepcopy(self)
-        if hasattr(cloned, "_workflow_context_token"):
-            del cloned._workflow_context_token
-        return cloned
+        memo = {id(self._workflow_context_token): None}
+        return copy.deepcopy(self, memo=memo)
 
     def to_envelope(self) -> dict[str, Any]:
         """Serialize this IR as the stored vibe envelope.
@@ -518,13 +515,37 @@ class VibeWorkflow:
 
         Counter always increments regardless of whether a seed is provided.
         When seed is given it becomes the local uid component (extrinsic identity).
-        When omitted, the counter value provides authored creation-order identity.
+        When omitted, the counter value provides authored creation-order identity;
+        before minting, the counter is reconciled with any pre-existing flat
+        auto-minted ``n<positive-integer>`` uids (e.g. imported via envelope
+        decode) so the minted uid never collides with one already present.
+        The counter only ever moves forward (monotonic).
         """
         from vibecomfy.identity.uid import make_uid
+        if seed is None:
+            self._reconcile_uid_counter()
         self._uid_counter += 1
         local = seed if seed is not None else f"n{self._uid_counter}"
         return make_uid("", local)
 
+    def _reconcile_uid_counter(self) -> None:
+        """Raise ``_uid_counter`` above any existing flat auto-minted ``n<N>`` uids.
+
+        Envelope decode preserves imported uids verbatim while
+        ``_uid_counter`` starts at zero, so an unseeded mint would otherwise
+        collide with an imported ``n<positive-integer>`` (e.g. ``n1``). Scan
+        existing node uids matching the auto-mint shape and move the counter
+        forward to the largest N found. Imported uids are never rewritten and
+        the counter never decreases (monotonic).
+        """
+        highest = 0
+        for node in self.nodes.values():
+            digits = node.uid[1:] if node.uid.startswith("n") else ""
+            if digits.isdecimal() and int(digits) > 0:
+                highest = max(highest, int(digits))
+        if highest >= self._uid_counter:
+            self._uid_counter = highest
+
     def add_node(
         self,
         class_type: str,

exec
/bin/zsh -lc "nl -ba vibecomfy/workflow.py | sed -n '1,360p'; nl -ba vibecomfy/workflow.py | sed -n '470,620p'; rg -n \"_workflow_context_token|_uid_counter|_mint_uid|uid=\" vibecomfy tests | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	import copy
     4	import dataclasses
     5	from dataclasses import dataclass, field, replace
     6	import math
     7	import warnings
     8	from typing import TYPE_CHECKING, Any
     9	
    10	from vibecomfy._compile import _resolve as helper_resolve
    11	from vibecomfy._compile import _widgets as widget_aliases
    12	from vibecomfy._compile import _helpers as workflow_helpers
    13	from vibecomfy._compile._graph import is_canonical_api_link
    14	from vibecomfy.errors import VibeComfyError
    15	from vibecomfy.handles import Handle
    16	
    17	if TYPE_CHECKING:
    18	    from vibecomfy.schema.provider import SchemaProvider
    19	
    20	
    21	# ComfyUI-specific validation policy lives in the neutral contracts layer.
    22	# Re-exported here so existing `from vibecomfy.workflow import OPAQUE_COMPONENT_CLASS_RE`
    23	# imports keep working.
    24	from vibecomfy.contracts.validation import (  # noqa: E402
    25	    OPAQUE_COMPONENT_CLASS_RE,
    26	    comfyui_node_issue_specs,
    27	)
    28	
    29	# WorkflowSummary is the typed contract for LLM-generated summaries stored
    30	# under ``workflow.metadata['summary']``.  Re-exported so consumers can
    31	# import from ``vibecomfy.workflow`` without reaching into contracts.
    32	from vibecomfy.contracts.summary import WorkflowSummary  # noqa: E402
    33	
    34	
    35	# Stored-envelope format version. The IR is the schema source: writers stamp
    36	# this via ``VibeWorkflow.to_envelope()`` rather than a script-local constant.
    37	FORMAT_VERSION = "1.0"
    38	VIBECOMFY_FORMAT_VERSION = FORMAT_VERSION
    39	
    40	
    41	def _to_plain(obj: Any) -> Any:
    42	    """Lossless walk of public dataclass fields (skip private ``_`` names)."""
    43	    if dataclasses.is_dataclass(obj):
    44	        result: dict[str, Any] = {}
    45	        for field_info in dataclasses.fields(obj):
    46	            if field_info.name.startswith("_"):
    47	                continue
    48	            result[field_info.name] = _to_plain(getattr(obj, field_info.name))
    49	        return result
    50	    if isinstance(obj, dict):
    51	        return {str(key): _to_plain(value) for key, value in obj.items()}
    52	    if isinstance(obj, (list, tuple)):
    53	        return [_to_plain(value) for value in obj]
    54	    return obj
    55	
    56	
    57	def _geometry_error(value: Any) -> str | None:
    58	    """Return why a first-class geometry value is invalid, if it is invalid."""
    59	    if value is None:
    60	        return None
    61	    if not isinstance(value, list) or len(value) != 2:
    62	        return "must be a list containing exactly two coordinates"
    63	    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
    64	        return "coordinates must be numeric (not booleans)"
    65	    try:
    66	        finite = all(math.isfinite(float(coord)) for coord in value)
    67	    except (OverflowError, TypeError, ValueError):
    68	        finite = False
    69	    if not finite:
    70	        return "coordinates must be finite"
    71	    return None
    72	
    73	
    74	def _invalid_geometry_details(workflow: "VibeWorkflow") -> list[dict[str, Any]]:
    75	    details: list[dict[str, Any]] = []
    76	    for node_id, node in workflow.nodes.items():
    77	        for field_name in ("pos", "size"):
    78	            value = getattr(node, field_name)
    79	            error = _geometry_error(value)
    80	            if error is not None:
    81	                details.append(
    82	                    {
    83	                        "node_id": str(node_id),
    84	                        "field": field_name,
    85	                        "value": value,
    86	                        "reason": error,
    87	                    }
    88	                )
    89	    return details
    90	
    91	
    92	@dataclass(slots=True)
    93	class WorkflowSource:
    94	    id: str
    95	    path: str | None = None
    96	    source_type: str = "unknown"
    97	    provenance: dict[str, Any] = field(default_factory=dict)
    98	
    99	
   100	@dataclass(slots=True)
   101	class WorkflowRequirements:
   102	    models: list[str] = field(default_factory=list)
   103	    custom_nodes: list[str] = field(default_factory=list)
   104	    missing_models: list[str] = field(default_factory=list)
   105	    missing_nodes: list[str] = field(default_factory=list)
   106	    unsupported: list[str] = field(default_factory=list)
   107	
   108	
   109	@dataclass(slots=True)
   110	class RawWidgetPayload:
   111	    values: Any
   112	    shape: str
   113	    source: str
   114	    has_dict_rows: bool
   115	    length: int
   116	
   117	
   118	@dataclass(slots=True)
   119	class VibeNode:
   120	    id: str
   121	    class_type: str
   122	    pack: str | None = None
   123	    inputs: dict[str, Any] = field(default_factory=dict)
   124	    widgets: dict[str, Any] = field(default_factory=dict)
   125	    metadata: dict[str, Any] = field(default_factory=dict)
   126	    uid: str = ""
   127	    raw_widgets: RawWidgetPayload | None = None
   128	    mode: int = 0
   129	    pos: list[float] | None = None
   130	    size: list[float] | None = None
   131	
   132	    @property
   133	    def provenance(self) -> str:
   134	        """Read-through to the S4 provenance tag; fail-closed on missing/None."""
   135	        from vibecomfy.security import provenance as _prov
   136	
   137	        return _prov.read(self)
   138	
   139	
   140	@dataclass(slots=True)
   141	class VibeEdge:
   142	    from_node: str
   143	    from_output: str
   144	    to_node: str
   145	    to_input: str
   146	
   147	
   148	@dataclass(slots=True)
   149	class VibeInput:
   150	    name: str
   151	    node_id: str
   152	    field: str
   153	    value: Any = None
   154	    type: str | None = None
   155	    default: Any = None
   156	    required: bool = False
   157	    range: Any = None
   158	    aliases: tuple[str, ...] = field(default_factory=tuple)
   159	    media_semantics: str | None = None
   160	
   161	    @property
   162	    def media(self) -> str | None:
   163	        return self.media_semantics
   164	
   165	    @media.setter
   166	    def media(self, value: str | None) -> None:
   167	        self.media_semantics = value
   168	
   169	
   170	@dataclass(slots=True)
   171	class VibeOutput:
   172	    node_id: str
   173	    output_type: str
   174	    name: str | None = None
   175	    artifact_kind: str | None = None
   176	    mime_type: str | None = None
   177	    filename_prefix: str | None = None
   178	    expected_cardinality: str | int | None = None
   179	
   180	
   181	@dataclass(slots=True)
   182	class ValidationIssue:
   183	    code: str
   184	    message: str
   185	    severity: str = "error"
   186	    detail: dict[str, Any] = field(default_factory=dict)
   187	
   188	
   189	@dataclass(slots=True)
   190	class ValidationReport:
   191	    ok: bool
   192	    issues: list[ValidationIssue] = field(default_factory=list)
   193	
   194	
   195	class WorkflowCompileError(VibeComfyError):
   196	    """Compile-time graph assembly failure with a stable machine-readable code."""
   197	
   198	    def __init__(
   199	        self,
   200	        code: str,
   201	        message: str,
   202	        *,
   203	        detail: dict[str, Any] | None = None,
   204	        next_action: str | None = None,
   205	    ) -> None:
   206	        self.code = code
   207	        self.detail = detail or {}
   208	        super().__init__(f"{code}: {message}", next_action=next_action)
   209	
   210	
   211	@dataclass
   212	class VibeWorkflow:
   213	    id: str
   214	    source: WorkflowSource
   215	    nodes: dict[str, VibeNode] = field(default_factory=dict)
   216	    edges: list[VibeEdge] = field(default_factory=list)
   217	    inputs: dict[str, VibeInput] = field(default_factory=dict)
   218	    outputs: list[VibeOutput] = field(default_factory=list)
   219	    requirements: WorkflowRequirements = field(default_factory=WorkflowRequirements)
   220	    metadata: dict[str, Any] = field(default_factory=dict)
   221	    strict_types: bool = False
   222	    groups: list[dict[str, Any]] = field(default_factory=list)
   223	    _id_map: dict[str, str] = field(default_factory=dict, init=False, repr=False)
   224	    _manual_input_names: set[str] = field(default_factory=set, init=False, repr=False)
   225	    _uid_counter: int = field(default=0, init=False, repr=False)
   226	    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)
   227	
   228	    def __enter__(self) -> "VibeWorkflow":
   229	        from vibecomfy.workflow_context import active_workflow, bind_workflow
   230	
   231	        # If ``new_workflow()`` already eagerly bound this workflow (the post-
   232	        # revert default for emitted templates), reuse that binding rather than
   233	        # raising — the ``with`` form is purely scoping sugar in that case.
   234	        if self._workflow_context_token is not None and active_workflow() is self:
   235	            return self
   236	        if self._workflow_context_token is not None:
   237	            raise RuntimeError(
   238	                "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
   239	                "block is still active."
   240	            )
   241	        self._workflow_context_token = bind_workflow(self)
   242	        return self
   243	
   244	    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
   245	        from vibecomfy.workflow_context import reset_workflow
   246	
   247	        token = self._workflow_context_token
   248	        if token is not None:
   249	            reset_workflow(token)
   250	            self._workflow_context_token = None
   251	
   252	    def confirm_node(self, node_id: str) -> "VibeWorkflow":
   253	        """Promote ``untrusted_source`` provenance on ``node_id`` → ``user_confirmed``.
   254	
   255	        Idempotent on already-trusted nodes. Raises ``KeyError`` if ``node_id``
   256	        is unknown so callers cannot silently confirm a non-existent node.
   257	        """
   258	        from vibecomfy.security import provenance as _prov
   259	
   260	        node = self.nodes[node_id]
   261	        _prov.confirm(node)
   262	        return self
   263	
   264	    def set_prompt(self, value: str) -> "VibeWorkflow":
   265	        return self.set_input("prompt", value)
   266	
   267	    def set_seed(self, value: int) -> "VibeWorkflow":
   268	        return self.set_input("seed", int(value))
   269	
   270	    def set_steps(self, value: int) -> "VibeWorkflow":
   271	        return self.set_input("steps", int(value))
   272	
   273	    def set_model(self, value: str) -> "VibeWorkflow":
   274	        return self.set_input("model", value)
   275	
   276	    def copy(self) -> "VibeWorkflow":
   277	        """Derived, complete deep copy.
   278	
   279	        The dataclass walk (``copy.deepcopy``) copies every public field —
   280	        including ``groups`` and per-node ``mode`` — plus the private
   281	        bookkeeping (``_id_map``, ``_manual_input_names``, ``_uid_counter``).
   282	        A bound workflow's live ``contextvars.Token`` cannot be meaningfully
   283	        deep-copied, so the deepcopy memo maps it to ``None`` up front; every
   284	        clone is therefore unbound (``_workflow_context_token is None``).
   285	        """
   286	        memo = {id(self._workflow_context_token): None}
   287	        return copy.deepcopy(self, memo=memo)
   288	
   289	    def to_envelope(self) -> dict[str, Any]:
   290	        """Serialize this IR as the stored vibe envelope.
   291	
   292	        Public dataclass fields plus ``vibecomfy_format_version``. No
   293	        ``compiled_api`` — ``compile("api")`` is a function, not stored data.
   294	        Transport stamps such as ``workflow_id`` are applied by callers after
   295	        this, not here.
   296	        """
   297	        _raise_embedded_api_links(self, surface="envelope serialization")
   298	        invalid_geometry = _invalid_geometry_details(self)
   299	        if invalid_geometry:
   300	            detail = invalid_geometry[0]
   301	            raise ValueError(
   302	                f"node {detail['node_id']!r}: {detail['field']} {detail['reason']}"
   303	            )
   304	        plain = _to_plain(self)
   305	        plain["vibecomfy_format_version"] = FORMAT_VERSION
   306	        return plain
   307	
   308	    @classmethod
   309	    def from_envelope(cls, raw: dict[str, Any]) -> "VibeWorkflow":
   310	        """Fail-closed decoder for a serialized vibe envelope.
   311	
   312	        Rich ``nodes`` + ``edges`` are the only structural authority.
   313	        ``compiled_api`` is ignored. Malformed input raises ``ValueError``;
   314	        no partial graph is returned. Implementation is the existing ingest
   315	        decoder — this method does not relax it.
   316	        """
   317	        from vibecomfy.ingest.normalize import _decode_serialized_vibe
   318	
   319	        return _decode_serialized_vibe(raw)
   320	
   321	    def clone(self) -> "VibeWorkflow":
   322	        return self.copy()
   323	
   324	    def finalize_metadata(self) -> "VibeWorkflow":
   325	        from vibecomfy.metadata import OUTPUT_NODE_NAMES, _infer_requirements, _register_common_inputs
   326	
   327	        manual_inputs = {
   328	            name: replace(vibe_input)
   329	            for name, vibe_input in self.inputs.items()
   330	            if name in self._manual_input_names and self._input_target_exists(vibe_input)
   331	        }
   332	        self._manual_input_names.intersection_update(manual_inputs)
   333	        self.inputs.clear()
   334	        self.outputs.clear()
   335	        for node_id, node in self.nodes.items():
   336	            _register_common_inputs(self, node_id, node)
   337	            if node.class_type in OUTPUT_NODE_NAMES:
   338	                self.outputs.append(VibeOutput(node_id=node_id, output_type=node.class_type))
   339	        self.inputs.update(manual_inputs)
   340	        self.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
   341	        self.requirements = _infer_requirements(self)
   342	        return self
   343	
   344	    def finalize(
   345	        self,
   346	        public_inputs: dict[str, Any],
   347	        *,
   348	        metadata: dict[str, Any] | None = None,
   349	        output_node: Any = None,
   350	        output_kind: str | None = None,
   351	        **bind_kwargs: Any,
   352	    ) -> "VibeWorkflow":
   353	        """Finalize ready-template public inputs and output binding.
   354	
   355	        ``metadata`` is optional for the v2.5 method form; when omitted, the
   356	        workflow's current metadata is used. The legacy free function remains
   357	        available in ``vibecomfy.templates.finalize``.
   358	        """
   359	        from vibecomfy.templates import _finalize_impl
   360	
   470	        if name in aliases:
   471	            raise ValueError(f"register_input({name!r}): alias cannot equal its primary input name")
   472	        existing_primary_names = {existing_name for existing_name in self.inputs if existing_name != name}
   473	        if name in {
   474	            alias
   475	            for existing_name, item in self.inputs.items()
   476	            if existing_name != name
   477	            for alias in item.aliases
   478	        }:
   479	            raise ValueError(f"register_input({name!r}): primary input name conflicts with an existing alias")
   480	        primary_conflicts = existing_primary_names.intersection(aliases)
   481	        if primary_conflicts:
   482	            conflict = sorted(primary_conflicts)[0]
   483	            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing primary input")
   484	        existing_aliases = {
   485	            alias
   486	            for existing_name, item in self.inputs.items()
   487	            if existing_name != name
   488	            for alias in item.aliases
   489	        }
   490	        alias_conflicts = existing_aliases.intersection(aliases)
   491	        if alias_conflicts:
   492	            conflict = sorted(alias_conflicts)[0]
   493	            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing alias")
   494	
   495	    def _validate_input_target(self, name: str, node_id: str, field: str) -> None:
   496	        node_key = str(node_id)
   497	        if node_key not in self.nodes:
   498	            raise ValueError(
   499	                f"register_input({name!r}): target node {node_key!r} does not exist "
   500	                f"in workflow {self.id!r}"
   501	            )
   502	        node = self.nodes[node_key]
   503	        if field not in node.inputs and field not in node.widgets:
   504	            raise ValueError(
   505	                f"register_input({name!r}): field {field!r} not found in "
   506	                f"node {node_key!r} ({node.class_type}) inputs or widgets"
   507	            )
   508	
   509	    def _input_target_exists(self, vibe_input: VibeInput) -> bool:
   510	        node = self.nodes.get(vibe_input.node_id)
   511	        return node is not None and (vibe_input.field in node.inputs or vibe_input.field in node.widgets)
   512	
   513	    def _mint_uid(self, seed: str | None = None) -> str:
   514	        """Mint a never-reused uid using the monotonic counter.
   515	
   516	        Counter always increments regardless of whether a seed is provided.
   517	        When seed is given it becomes the local uid component (extrinsic identity).
   518	        When omitted, the counter value provides authored creation-order identity;
   519	        before minting, the counter is reconciled with any pre-existing flat
   520	        auto-minted ``n<positive-integer>`` uids (e.g. imported via envelope
   521	        decode) so the minted uid never collides with one already present.
   522	        The counter only ever moves forward (monotonic).
   523	        """
   524	        from vibecomfy.identity.uid import make_uid
   525	        if seed is None:
   526	            self._reconcile_uid_counter()
   527	        self._uid_counter += 1
   528	        local = seed if seed is not None else f"n{self._uid_counter}"
   529	        return make_uid("", local)
   530	
   531	    def _reconcile_uid_counter(self) -> None:
   532	        """Raise ``_uid_counter`` above any existing flat auto-minted ``n<N>`` uids.
   533	
   534	        Envelope decode preserves imported uids verbatim while
   535	        ``_uid_counter`` starts at zero, so an unseeded mint would otherwise
   536	        collide with an imported ``n<positive-integer>`` (e.g. ``n1``). Scan
   537	        existing node uids matching the auto-mint shape and move the counter
   538	        forward to the largest N found. Imported uids are never rewritten and
   539	        the counter never decreases (monotonic).
   540	        """
   541	        highest = 0
   542	        for node in self.nodes.values():
   543	            digits = node.uid[1:] if node.uid.startswith("n") else ""
   544	            if digits.isdecimal() and int(digits) > 0:
   545	                highest = max(highest, int(digits))
   546	        if highest >= self._uid_counter:
   547	            self._uid_counter = highest
   548	
   549	    def add_node(
   550	        self,
   551	        class_type: str,
   552	        _id: str | None = None,
   553	        *,
   554	        uid: str | None = None,
   555	        _provenance: "Provenance | None" = None,
   556	        **inputs: Any,
   557	    ) -> VibeNode:
   558	        """Add a node to the workflow.
   559	
   560	        ``uid`` is keyword-only and sets node.uid verbatim when provided.
   561	        Extrinsic-seed minting via _mint_uid belongs in node()/raw_call callers,
   562	        not here, so add_node stays uid-neutral by default.
   563	
   564	        ``_provenance`` is a reserved keyword-only parameter declared BEFORE
   565	        ``**inputs`` so callers cannot accidentally bind it from an inputs
   566	        dict. When ``None`` it falls back to the ``requesting_provenance``
   567	        ContextVar (default ``"agent_authored"``); ingest enters
   568	        ``untrusted_scope()`` to flip it. The resulting tag is written into
   569	        ``node.metadata[PROVENANCE_KEY]`` and is never copied into
   570	        ``node.inputs``. ``_provenance`` is a reserved kwarg name and must not
   571	        be used as a ComfyUI input field.
   572	        """
   573	        from vibecomfy.security.capabilities import capabilities_for, is_side_effecting
   574	        from vibecomfy.security.gate import (
   575	            current_gate_context,
   576	            requesting_provenance,
   577	            require_confirmation,
   578	        )
   579	        from vibecomfy.security.provenance import PROVENANCE_KEY, tag as _tag_provenance
   580	
   581	        effective = _provenance if _provenance is not None else requesting_provenance.get()
   582	
   583	        # ── S4 capability fence ─────────────────────────────────────────────
   584	        # Edit-time confused-deputy gate. Only the IR write path is gated; the
   585	        # compile path at ``_compile_graphbuilder`` below (GraphBuilder.node
   586	        # from ``comfy_execution.graph_utils``) is INTENTIONALLY NOT gated —
   587	        # gating happens at edit-time, not at compile-time. By the time a
   588	        # workflow compiles, every node has already passed this gate (or was
   589	        # tagged trusted by its authoring path).
   590	        if is_side_effecting(class_type):
   591	            caps = capabilities_for(class_type)
   592	            risky = {
   593	                k: v
   594	                for k, v in inputs.items()
   595	                if not isinstance(v, Handle) and k != "_provenance"
   596	            }
   597	            require_confirmation(
   598	                operation="add_node",
   599	                class_type=class_type,
   600	                provenance=effective,
   601	                capabilities=caps,
   602	                details={"params": risky},
   603	                ctx=current_gate_context(),
   604	            )
   605	
   606	        node_id = str(_id) if _id is not None else self._next_node_id()
   607	        if node_id in self.nodes:
   608	            raise ValueError(f"Node id {node_id!r} already exists in workflow {self.id!r}")
   609	        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
   610	        if uid is not None:
   611	            node.uid = uid
   612	        _tag_provenance(node, effective)
   613	        # Defensive: ensure the reserved kwarg never leaked into inputs.
   614	        node.inputs.pop("_provenance", None)
   615	        self.nodes[node_id] = node
   616	        return node
   617	
   618	    def node(self, class_type: str, **kwargs: Any) -> "_NodeBuilder":
   619	        pass_raw = bool(kwargs.pop("pass_raw", False))
   620	        explicit_id = kwargs.pop("_id", None)
tests/test_ui_layout.py:157:    return _FakeNode(id=id_, uid=uid or id_)
tests/test_ui_layout.py:786:                f"expected sub_lane {idx} for uid={uid}, got {lanes[uid][1]}"
tests/test_ui_layout.py:816:            nodes[nid] = _FakeNode(id=nid, uid=uid, class_type=class_type)
tests/test_ui_layout.py:988:            nodes[str(nid)] = _FakeNode(id=str(nid), uid=uid, class_type="SomeNode")
tests/test_ui_layout.py:1049:            "1": _FakeNode(id="1", uid="u1", class_type="TypeA"),
tests/test_ui_layout.py:1050:            "2": _FakeNode(id="2", uid="u2", class_type="TypeB"),
tests/test_ui_layout.py:1051:            "3": _FakeNode(id="3", uid="u3", class_type="TypeA"),
tests/test_ui_layout.py:1088:            "1": _FakeNode(id="1", uid="x1", class_type="UnknownWidgetX99"),
tests/test_ui_layout.py:1089:            "2": _FakeNode(id="2", uid="x2", class_type="UnknownWidgetY88"),
tests/test_ui_layout.py:1206:        # Layer 0: root (class_type="Ctrl", uid="root")
tests/test_ui_layout.py:1207:        # Layer 1: src_a (class_type="Alpha", uid="src_a"), src_b (class_type="Alpha", uid="src_b")
tests/test_ui_layout.py:1212:        # Layer 2: node_x (class_type="Beta", uid="node_x"), node_y (class_type="Beta", uid="node_y")
tests/test_ui_layout.py:1315:        # Layer 0: src (uid="src")
tests/test_ui_layout.py:1316:        # Layer 1: pos_node (uid="positive", class_type="LoadImage")
tests/test_ui_layout.py:1317:        #          neg_node (uid="negative", class_type="SaveImage")
tests/test_ui_layout.py:1408:        wf.add_node("TypeA", "1", uid="u1")
tests/test_ui_layout.py:1409:        wf.add_node("TypeB", "2", uid="u2")
tests/test_ui_layout.py:1410:        wf.add_node("TypeC", "3", uid="u3")
tests/test_ui_layout.py:1411:        wf.add_node("TypeD", "4", uid="u4")
tests/test_ui_layout.py:1412:        wf.add_node("TypeE", "5", uid="u5")
tests/test_ui_layout.py:1434:        wf.add_node("TypeA", "1", uid="a1")
tests/test_ui_layout.py:1435:        wf.add_node("TypeB", "2", uid="a2")
tests/test_ui_layout.py:1455:        wf.add_node("TypeA", "1", uid="na")
tests/test_ui_layout.py:1456:        wf.add_node("TypeB", "2", uid="nb")
tests/test_ui_layout.py:1498:        wf.add_node("TypeA", "1", uid="inner_1")
tests/test_ui_layout.py:1499:        wf.add_node("TypeB", "2", uid="inner_2")
tests/test_ui_layout.py:1533:        wf.add_node("TypeA", "1", uid="p1")
tests/test_ui_layout.py:1534:        wf.add_node("TypeB", "2", uid="p2")
tests/test_ui_layout.py:1597:        wf.add_node("TypeA", "1", uid="ba")
tests/test_ui_layout.py:1598:        wf.add_node("TypeB", "2", uid="bb")
tests/test_ui_layout.py:1599:        wf.add_node("TypeC", "3", uid="bc")
tests/test_ui_layout.py:1640:        wf.add_node("TypeA", "1", uid="va")
tests/test_ui_layout.py:1738:                            f"{tid}: {cls_i}(uid={uid_i}) [{ix1},{iy1},{ix2},{iy2}]"
tests/test_ui_layout.py:1739:                            f" overlaps {cls_j}(uid={uid_j}) [{jx1},{jy1},{jx2},{jy2}]"
tests/test_ui_layout.py:1982:                new_uid=new_uid,
tests/test_ui_layout.py:1983:                anchor_uid=anchor_uid,
tests/test_felt_fidelity_gate.py:39:def _ui_node(id_=1, pos=(100, 200), size=(200, 100), uid=None, vid=None, mode=0) -> dict:
tests/test_felt_fidelity_gate.py:91:    emitted = _emitted_ui([_ui_node(1, pos=(108, 200), uid=uid)])
tests/test_felt_fidelity_gate.py:120:        _ui_node(1, pos=(0, 0), uid="other-node"),
tests/test_felt_fidelity_gate.py:155:        _ui_node(1, pos=(500, 500), uid=uid),
tests/test_felt_fidelity_gate.py:156:        _ui_node(2, pos=(200, 200), uid=preserved_uid),
tests/test_felt_fidelity_gate.py:174:        _ui_node(1, pos=(50, 50), uid=preserved_uid),
tests/test_felt_fidelity_gate.py:175:        _ui_node(2, pos=(999, 999), uid=new_uid),
tests/test_felt_fidelity_gate.py:204:    emitted_05 = _emitted_ui([_ui_node(1, pos=(100.5, 200), uid=uid)])
tests/test_felt_fidelity_gate.py:210:    emitted_2 = _emitted_ui([_ui_node(1, pos=(102, 200), uid=uid)])
tests/test_felt_fidelity_gate.py:225:    emitted = _emitted_ui([_ui_node(1, pos=(999, 999), uid=uid)])
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:20:    cliploader = _node(wf, 'CLIPLoader', '1', _uid='n1',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:25:    vaeloader = _node(wf, 'VAELoader', '2', _uid='n2',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:29:    unetloader = _node(wf, 'UNETLoader', '3', _uid='n3',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:33:    emptysd3latentimage = _node(wf, 'EmptySD3LatentImage', '4', _uid='n4',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:38:    positive = _node(wf, 'CLIPTextEncode', '5', _uid='n5',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:43:    modelsamplingauraflow = _node(wf, 'ModelSamplingAuraFlow', '6', _uid='n6',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:48:    negative = _node(wf, 'CLIPTextEncode', '7', _uid='n7',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:53:    ksampler = _node(wf, 'KSampler', '8', _uid='n8',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:64:    vaedecode = _node(wf, 'VAEDecode', '11', _uid='n9',
tests/characterization/goldens/emitter/z_image.scratchpad.py.golden:69:    saveimage = _node(wf, 'SaveImage', '9', _uid='n10',
vibecomfy/porting/resolution.py:123:        uid=uid,
vibecomfy/porting/resolution.py:316:        uid=uid,
vibecomfy/porting/resolution.py:357:            uid=uid_str,
vibecomfy/porting/resolution.py:374:            NodeTarget(scope_path=target.scope_path, uid=result.value), []
vibecomfy/porting/resolution.py:391:                uid=result.value,
vibecomfy/porting/resolution.py:411:                uid=result.value,
vibecomfy/porting/resolution.py:431:                uid=result.value,
vibecomfy/porting/resolution.py:454:                scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:461:                scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:469:                scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:486:                scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:513:                            scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:529:            scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:546:                scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:555:                scope_path=scope_path, uid=uid,
vibecomfy/porting/resolution.py:583:                scope_path=ref.scope_path, uid=resolved_uid,
vibecomfy/porting/resolution.py:593:                scope_path=ref.scope_path, uid=resolved_uid,
vibecomfy/porting/resolution.py:605:                    scope_path=ref.scope_path, uid=resolved_uid,
vibecomfy/porting/resolution.py:634:                        uid=resolved_uid,
vibecomfy/porting/resolution.py:666:                                uid=resolved_uid,
vibecomfy/porting/resolution.py:683:                    scope_path=ref.scope_path, uid=resolved_uid,
vibecomfy/porting/resolution.py:693:                uid=resolved_uid,
vibecomfy/porting/resolution.py:727:                scope_path=ref.scope_path, uid=resolved_uid,
vibecomfy/porting/resolution.py:748:                scope_path=ref.scope_path, uid=resolved_uid,
vibecomfy/porting/resolution.py:765:                uid=resolved_uid,
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:20:    unetloader = _node(wf, 'UNETLoader', '37', _uid='n1',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:24:    cliploader = _node(wf, 'CLIPLoader', '38', _uid='n2',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:29:    vaeloader = _node(wf, 'VAELoader', '39', _uid='n3',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:33:    emptyhunyuanlatentvideo = _node(wf, 'EmptyHunyuanLatentVideo', '40', _uid='n4',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:39:    positive = _node(wf, 'CLIPTextEncode', '6', _uid='n5',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:44:    negative = _node(wf, 'CLIPTextEncode', '7', _uid='n6',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:49:    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '48', _uid='n7',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:54:    ksampler = _node(wf, 'KSampler', '3', _uid='n8',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:65:    vaedecode = _node(wf, 'VAEDecode', '8', _uid='n9',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:70:    createvideo = _node(wf, 'CreateVideo', '49', _uid='n10',
tests/characterization/goldens/emitter/wan_t2v.scratchpad.py.golden:75:    savevideo = _node(wf, 'SaveVideo', '50', _uid='n11',
tests/test_comfy_nodes_agent_contracts.py:222:    change = ContractFieldChange(uid="n1", field_path="widgets.seed", old=1, new=2)
tests/test_comfy_nodes_agent_contracts.py:610:                uid="node-7",
tests/test_comfy_nodes_agent_contracts.py:655:                FieldChange(uid="n1", field_path="widgets.seed", old=1, new=2),
tests/test_comfy_nodes_agent_contracts.py:2209:                (FieldChange(uid="n1", field_path="x", old=1, new=2),)
tests/test_comfy_nodes_agent_contracts.py:2661:    changes = (FieldChange(uid="1", field_path="widgets_values[0]", old=None, new=25),)
tests/test_comfy_nodes_agent_contracts.py:2678:    changes = (FieldChange(uid="n1", field_path="seed", old=42, new=43),)
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:48:    unetloader = UNETLoader(_id='37', unet_name=UNET_NAME, _uid='n1')
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:54:        _uid='n2',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:57:    vaeloader = VAELoader(_id='39', vae_name=VAE_NAME, _uid='n3')
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:65:        _uid='n4',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:73:        _uid='n5',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:80:        _uid='n6',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:87:        _uid='n7',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:100:        _uid='n8',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:108:        _uid='n9',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:115:        _uid='n10',
tests/characterization/goldens/emitter/wan_t2v.ready.py.golden:119:    savevideo = SaveVideo(_id='50', video=createvideo, _uid='n11')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:59:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#61',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:65:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#68',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:71:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#69',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:76:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#70',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:82:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#71',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:87:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#72',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:92:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#73',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:98:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#62',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:104:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#66',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:110:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#67',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:116:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#74',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:124:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#63',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:133:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#64',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:139:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#65',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:163:        _uid='a67caa28-5f85-4917-8396-36004960dd30#61',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:169:        _uid='a67caa28-5f85-4917-8396-36004960dd30#68',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:175:        _uid='a67caa28-5f85-4917-8396-36004960dd30#69',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:180:        _uid='a67caa28-5f85-4917-8396-36004960dd30#70',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:186:        _uid='a67caa28-5f85-4917-8396-36004960dd30#71',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:191:        _uid='a67caa28-5f85-4917-8396-36004960dd30#72',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:197:        _uid='a67caa28-5f85-4917-8396-36004960dd30#73',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:204:        _uid='a67caa28-5f85-4917-8396-36004960dd30#62',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:210:        _uid='a67caa28-5f85-4917-8396-36004960dd30#66',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:216:        _uid='a67caa28-5f85-4917-8396-36004960dd30#74',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:221:        _uid='a67caa28-5f85-4917-8396-36004960dd30#76',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:229:        _uid='a67caa28-5f85-4917-8396-36004960dd30#63',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:238:        _uid='a67caa28-5f85-4917-8396-36004960dd30#64',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:244:        _uid='a67caa28-5f85-4917-8396-36004960dd30#65',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:254:    ksamplerselect = KSamplerSelect(_id='1', sampler_name=EULER, _uid='n1')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:255:    flux2scheduler = Flux2Scheduler(_id='2', _uid='n2')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:256:    emptyflux2latentimage = EmptyFlux2LatentImage(_id='3', _uid='n3')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:259:    unetloader = UNETLoader(_id='4', unet_name=UNET_NAME, _uid='n4')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:265:        _uid='n5',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:268:    vaeloader = VAELoader(_id='6', vae_name=VAE_NAME, _uid='n6')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:269:    randomnoise = RandomNoise(_id='7', control_after_generate=RANDOMIZE, _uid='n7')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:270:    ksamplerselect_2 = KSamplerSelect(_id='13', sampler_name=EULER, _uid='n13')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:271:    flux2scheduler_2 = Flux2Scheduler(_id='14', steps=4, _uid='n14')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:272:    emptyflux2latentimage_2 = EmptyFlux2LatentImage(_id='15', _uid='n15')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:273:    unetloader_2 = UNETLoader(_id='16', unet_name=UNET_NAME_2, _uid='n16')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:279:        _uid='n17',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:282:    vaeloader_2 = VAELoader(_id='18', vae_name=VAE_NAME, _uid='n18')
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:288:        _uid='n19',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:296:        _uid='n8',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:303:        _uid='n20',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:310:        _uid='n9',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:319:        _uid='n10',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:325:        _uid='n21',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:335:        _uid='n11',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:344:        _uid='n22',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:352:        _uid='n12',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:362:        _uid='n23',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:370:        _uid='n25',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:377:        _uid='n24',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.ready.py.golden:384:        _uid='n26',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:20:    ksamplerselect = _node(wf, 'KSamplerSelect', '1', _uid='n1',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:24:    flux2scheduler = _node(wf, 'Flux2Scheduler', '2', _uid='n2',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:27:    emptyflux2latentimage = _node(wf, 'EmptyFlux2LatentImage', '3', _uid='n3',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:30:    unetloader = _node(wf, 'UNETLoader', '4', _uid='n4',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:34:    cliploader = _node(wf, 'CLIPLoader', '5', _uid='n5',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:39:    vaeloader = _node(wf, 'VAELoader', '6', _uid='n6',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:43:    randomnoise = _node(wf, 'RandomNoise', '7', _uid='n7',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:47:    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '13', _uid='n13',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:51:    flux2scheduler_2 = _node(wf, 'Flux2Scheduler', '14', _uid='n14',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:55:    emptyflux2latentimage_2 = _node(wf, 'EmptyFlux2LatentImage', '15', _uid='n15',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:58:    unetloader_2 = _node(wf, 'UNETLoader', '16', _uid='n16',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:62:    cliploader_2 = _node(wf, 'CLIPLoader', '17', _uid='n17',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:67:    vaeloader_2 = _node(wf, 'VAELoader', '18', _uid='n18',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:71:    randomnoise_2 = _node(wf, 'RandomNoise', '19', _uid='n19',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:76:    negative = _node(wf, 'CLIPTextEncode', '8', _uid='n8',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:81:    positive = _node(wf, 'CLIPTextEncode', '20', _uid='n20',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:86:    positive_2 = _node(wf, 'CLIPTextEncode', '26', _uid='n9',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:91:    cfgguider = _node(wf, 'CFGGuider', '10', _uid='n10',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:98:    conditioningzeroout = _node(wf, 'ConditioningZeroOut', '21', _uid='n21',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:102:    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '11', _uid='n11',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:110:    cfgguider_2 = _node(wf, 'CFGGuider', '22', _uid='n22',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:117:    vaedecode = _node(wf, 'VAEDecode', '12', _uid='n12',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:122:    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '23', _uid='n23',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:130:    saveimage = _node(wf, 'SaveImage', '9', _uid='n25',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:134:    vaedecode_2 = _node(wf, 'VAEDecode', '24', _uid='n24',
tests/characterization/goldens/emitter/flux2_klein_4b_t2i.scratchpad.py.golden:139:    saveimage_2 = _node(wf, 'SaveImage', '78', _uid='n26',
tests/characterization/goldens/emitter/empty_image_red.scratchpad.py.golden:20:    emptyimage = _node(wf, 'EmptyImage', '1', _uid='n1',
tests/characterization/goldens/emitter/empty_image_red.scratchpad.py.golden:27:    saveimage = _node(wf, 'SaveImage', '2', _uid='n2',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:20:    loadimage = _node(wf, 'LoadImage', '2004', _uid='n1',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:25:    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '3059', _uid='n2',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:35:    ltxvaudiovaeloader = _node(wf, 'LTXVAudioVAELoader', '4010', _uid='n4',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:39:    randomnoise = _node(wf, 'RandomNoise', '4814', _uid='n5',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:44:    ksamplerselect = _node(wf, 'KSamplerSelect', '4831', _uid='n6',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:48:    randomnoise_2 = _node(wf, 'RandomNoise', '4832', _uid='n7',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:53:    ltxavtextencoderloader = _node(wf, 'LTXAVTextEncoderLoader', '4960', _uid='n8',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:59:    guiderparameters = _node(wf, 'GuiderParameters', '4963', _uid='n9',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:70:    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '4967', _uid='n10',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:73:    manualsigmas = _node(wf, 'ManualSigmas', '4971', _uid='n11',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:77:    ltxfloattoint = _node(wf, 'LTXFloatToInt', '4985', _uid='n12',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:82:    cliptextencode = _node(wf, 'CLIPTextEncode', '2483', _uid='n13',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:87:    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '2612', _uid='n14',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:92:    lowvramcheckpointloader = _node(wf, 'LowVRAMCheckpointLoader', '3940', _uid='n3',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:97:    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '3980', _uid='n15',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:106:    guiderparameters_2 = _node(wf, 'GuiderParameters', '4964', _uid='n17',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:118:    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '4981', _uid='n19',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:127:    ltxvconditioning = _node(wf, 'LTXVConditioning', '1241', _uid='n20',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:134:    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '3336', _uid='n21',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:139:    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '4922', _uid='n16',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:145:    loraloadermodelonly_2 = _node(wf, 'LoraLoaderModelOnly', '4968', _uid='n18',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:151:    ltxvimgtovideoconditiononly = _node(wf, 'LTXVImgToVideoConditionOnly', '3159', _uid='n22',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:159:    multimodalguider = _node(wf, 'MultimodalGuider', '4808', _uid='n23',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:167:    cfgguider = _node(wf, 'CFGGuider', '4828', _uid='n24',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:174:    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '4528', _uid='n25',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:179:    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '4829', _uid='n26',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:187:    ltxvscheduler = _node(wf, 'LTXVScheduler', '4966', _uid='n27',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:196:    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '4802', _uid='n28',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:204:    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '4845', _uid='n29',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:208:    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '4824', _uid='n30',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:212:    ltxvtiledvaedecode = _node(wf, 'LTXVTiledVAEDecode', '4982', _uid='n32',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:221:    createvideo_2 = _node(wf, 'CreateVideo', '4849', _uid='n34',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:226:    ltxvtiledvaedecode_2 = _node(wf, 'LTXVTiledVAEDecode', '4983', _uid='n35',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:235:    createvideo = _node(wf, 'CreateVideo', '4819', _uid='n36',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:240:    savevideo_2 = _node(wf, 'SaveVideo', '4852', _uid='n37',
tests/characterization/goldens/emitter/ltx2_3_t2v.scratchpad.py.golden:246:    savevideo = _node(wf, 'SaveVideo', '4823', _uid='n38',
tests/test_porting_ui_emitter.py:1848:            f"Node {lite_id} vibecomfy_uid={props['vibecomfy_uid']!r} != litegraph id {lite_id}"
tests/test_porting_ui_emitter.py:2389:        uid="uid-mode",
tests/test_porting_ui_emitter.py:2411:        uid="uid-a",
tests/test_porting_ui_emitter.py:2417:        uid="uid-b",
tests/test_porting_ui_emitter.py:2855:    wf.nodes["1"] = VibeNode("1", "MyNode", uid="uid-tt")
tests/test_porting_ui_emitter.py:2897:        "1", "MyNode", uid="uid-lt",
tests/test_porting_ui_emitter.py:2998:    wf.nodes["1"] = VibeNode("1", "LoadImage", uid="load1")
tests/test_porting_ui_emitter.py:2999:    wf.nodes["2"] = VibeNode("2", "SaveImage", uid="save1")
tests/test_porting_ui_emitter.py:3000:    wf.nodes["3"] = VibeNode("3", "VAEDecode", uid="vae1")
tests/test_porting_ui_emitter.py:3099:        uid=uid,
tests/test_porting_ui_emitter.py:3140:        wf.nodes["7"] = _pin_opaque_dynamic_node(uid=blank_uid)
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:62:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#61',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:67:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#70',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:73:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#71',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:78:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#72',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:84:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#73',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:90:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#80',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:96:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#74',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:101:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#99',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:107:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#122',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:114:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#62',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:120:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#66',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:125:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#82',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:131:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#123',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:137:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#121',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:145:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#63',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:154:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#64',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:160:        _uid='7b34ab90-36f9-45ba-a665-71d418f0df18#65',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:183:        _uid='27eacb9f-0da2-421d-a0bf-b4b4e5fe5709#116',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:189:        _uid='27eacb9f-0da2-421d-a0bf-b4b4e5fe5709#115',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:195:        _uid='27eacb9f-0da2-421d-a0bf-b4b4e5fe5709#117',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:218:        _uid='93041a64-452a-477a-9447-40330b7c1136#119',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:224:        _uid='93041a64-452a-477a-9447-40330b7c1136#118',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:230:        _uid='93041a64-452a-477a-9447-40330b7c1136#120',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:255:        _uid='65c22b29-59aa-496b-89c6-55a603658670#85',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:260:        _uid='65c22b29-59aa-496b-89c6-55a603658670#101',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:266:        _uid='65c22b29-59aa-496b-89c6-55a603658670#106',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:271:        _uid='65c22b29-59aa-496b-89c6-55a603658670#107',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:277:        _uid='65c22b29-59aa-496b-89c6-55a603658670#108',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:282:        _uid='65c22b29-59aa-496b-89c6-55a603658670#110',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:288:        _uid='65c22b29-59aa-496b-89c6-55a603658670#111',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:294:        _uid='65c22b29-59aa-496b-89c6-55a603658670#109',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:299:        _uid='65c22b29-59aa-496b-89c6-55a603658670#114',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:304:        _uid='65c22b29-59aa-496b-89c6-55a603658670#86',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:311:        _uid='65c22b29-59aa-496b-89c6-55a603658670#102',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:317:        _uid='65c22b29-59aa-496b-89c6-55a603658670#113',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:339:        _uid='65c22b29-59aa-496b-89c6-55a603658670#103',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:348:        _uid='65c22b29-59aa-496b-89c6-55a603658670#104',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:354:        _uid='65c22b29-59aa-496b-89c6-55a603658670#105',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:364:    ksamplerselect = KSamplerSelect(_id='1', sampler_name=EULER, _uid='n3')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:367:    unetloader = UNETLoader(_id='2', unet_name=UNET_NAME, _uid='n4')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:373:        _uid='n5',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:376:    vaeloader = VAELoader(_id='4', vae_name=VAE_NAME, _uid='n6')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:382:        _uid='n7',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:385:    ksamplerselect_2 = KSamplerSelect(_id='19', sampler_name=EULER, _uid='n21')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:391:        _uid='n22',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:394:    unetloader_2 = UNETLoader(_id='21', unet_name=UNET_NAME, _uid='n23')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:400:        _uid='n24',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:403:    vaeloader_2 = VAELoader(_id='23', vae_name=VAE_NAME, _uid='n25')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:406:    image, _ = LoadImage(_id='76', image='handbag_white.png', _uid='n1')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:407:    image_2, _ = LoadImage(_id='81', image='comfy_logo_blue.png', _uid='n2')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:413:        _uid='n8',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:421:        _uid='n9',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:428:        _uid='n20',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:435:        _uid='n26',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:442:        _uid='n27',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:445:    width, height, _ = GetImageSize(_id='8', image=imagescaletototalpixels, _uid='n10')
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:450:        _uid='n14',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:456:        _uid='n28',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:462:        _uid='n29',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:469:        _uid='n32',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:476:        _uid='n35',
tests/characterization/goldens/emitter/flux2_klein_4b_image_edit_distilled.ready.py.golden:483:        _uid='n11',

exec
/bin/zsh -lc "rg -n \"_workflow_context_token\" . --glob '"'!'"\\.oracle/**' --glob '"'!*.md'"'; sed -n '513,610p' vibecomfy/workflow.py; rg -n \"def _decode_serialized_vibe|VibeNode\\(\" vibecomfy/ingest/normalize.py | head -n 40; sed -n '560,700p' vibecomfy/ingest/normalize.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
./tools/check_canonical_parity.py:217:    token = getattr(workflow, "_workflow_context_token", None) if workflow is not None else None
./tools/check_canonical_parity.py:224:    workflow._workflow_context_token = None
./tests/test_templates_module.py:225:        wf._workflow_context_token = None
./tests/test_templates_module.py:241:        wf._workflow_context_token = None
./tests/test_templates_module.py:255:        outer._workflow_context_token = None
./tests/test_templates_module.py:270:        wf._workflow_context_token = None
./tests/test_templates_module.py:284:            wf._workflow_context_token = None
./vibecomfy/workflow.py:226:    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)
./vibecomfy/workflow.py:234:        if self._workflow_context_token is not None and active_workflow() is self:
./vibecomfy/workflow.py:236:        if self._workflow_context_token is not None:
./vibecomfy/workflow.py:241:        self._workflow_context_token = bind_workflow(self)
./vibecomfy/workflow.py:247:        token = self._workflow_context_token
./vibecomfy/workflow.py:250:            self._workflow_context_token = None
./vibecomfy/workflow.py:284:        clone is therefore unbound (``_workflow_context_token is None``).
./vibecomfy/workflow.py:286:        memo = {id(self._workflow_context_token): None}
./vibecomfy/templates.py:106:    if getattr(wf, "_workflow_context_token", None) is None:
./vibecomfy/templates.py:120:            existing_token = getattr(existing, "_workflow_context_token", None)
./vibecomfy/templates.py:126:        wf._workflow_context_token = bind_workflow(wf)
./vibecomfy/templates.py:561:    token = getattr(wf, "_workflow_context_token", None)
./vibecomfy/templates.py:569:        wf._workflow_context_token = None
    def _mint_uid(self, seed: str | None = None) -> str:
        """Mint a never-reused uid using the monotonic counter.

        Counter always increments regardless of whether a seed is provided.
        When seed is given it becomes the local uid component (extrinsic identity).
        When omitted, the counter value provides authored creation-order identity;
        before minting, the counter is reconciled with any pre-existing flat
        auto-minted ``n<positive-integer>`` uids (e.g. imported via envelope
        decode) so the minted uid never collides with one already present.
        The counter only ever moves forward (monotonic).
        """
        from vibecomfy.identity.uid import make_uid
        if seed is None:
            self._reconcile_uid_counter()
        self._uid_counter += 1
        local = seed if seed is not None else f"n{self._uid_counter}"
        return make_uid("", local)

    def _reconcile_uid_counter(self) -> None:
        """Raise ``_uid_counter`` above any existing flat auto-minted ``n<N>`` uids.

        Envelope decode preserves imported uids verbatim while
        ``_uid_counter`` starts at zero, so an unseeded mint would otherwise
        collide with an imported ``n<positive-integer>`` (e.g. ``n1``). Scan
        existing node uids matching the auto-mint shape and move the counter
        forward to the largest N found. Imported uids are never rewritten and
        the counter never decreases (monotonic).
        """
        highest = 0
        for node in self.nodes.values():
            digits = node.uid[1:] if node.uid.startswith("n") else ""
            if digits.isdecimal() and int(digits) > 0:
                highest = max(highest, int(digits))
        if highest >= self._uid_counter:
            self._uid_counter = highest

    def add_node(
        self,
        class_type: str,
        _id: str | None = None,
        *,
        uid: str | None = None,
        _provenance: "Provenance | None" = None,
        **inputs: Any,
    ) -> VibeNode:
        """Add a node to the workflow.

        ``uid`` is keyword-only and sets node.uid verbatim when provided.
        Extrinsic-seed minting via _mint_uid belongs in node()/raw_call callers,
        not here, so add_node stays uid-neutral by default.

        ``_provenance`` is a reserved keyword-only parameter declared BEFORE
        ``**inputs`` so callers cannot accidentally bind it from an inputs
        dict. When ``None`` it falls back to the ``requesting_provenance``
        ContextVar (default ``"agent_authored"``); ingest enters
        ``untrusted_scope()`` to flip it. The resulting tag is written into
        ``node.metadata[PROVENANCE_KEY]`` and is never copied into
        ``node.inputs``. ``_provenance`` is a reserved kwarg name and must not
        be used as a ComfyUI input field.
        """
        from vibecomfy.security.capabilities import capabilities_for, is_side_effecting
        from vibecomfy.security.gate import (
            current_gate_context,
            requesting_provenance,
            require_confirmation,
        )
        from vibecomfy.security.provenance import PROVENANCE_KEY, tag as _tag_provenance

        effective = _provenance if _provenance is not None else requesting_provenance.get()

        # ── S4 capability fence ─────────────────────────────────────────────
        # Edit-time confused-deputy gate. Only the IR write path is gated; the
        # compile path at ``_compile_graphbuilder`` below (GraphBuilder.node
        # from ``comfy_execution.graph_utils``) is INTENTIONALLY NOT gated —
        # gating happens at edit-time, not at compile-time. By the time a
        # workflow compiles, every node has already passed this gate (or was
        # tagged trusted by its authoring path).
        if is_side_effecting(class_type):
            caps = capabilities_for(class_type)
            risky = {
                k: v
                for k, v in inputs.items()
                if not isinstance(v, Handle) and k != "_provenance"
            }
            require_confirmation(
                operation="add_node",
                class_type=class_type,
                provenance=effective,
                capabilities=caps,
                details={"params": risky},
                ctx=current_gate_context(),
            )

        node_id = str(_id) if _id is not None else self._next_node_id()
        if node_id in self.nodes:
            raise ValueError(f"Node id {node_id!r} already exists in workflow {self.id!r}")
        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
        if uid is not None:
475:def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
641:        workflow.nodes[node_id] = VibeNode(
987:        workflow.nodes[str(node_id)] = VibeNode(
        requirements=requirements,
        metadata=deepcopy(metadata_raw) if isinstance(metadata_raw, dict) else {},
        strict_types=strict_types,
        groups=groups,
    )

    # ── nodes ──────────────────────────────────────────────────────────────
    for key, entry in nodes_raw.items():
        node_id = entry.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"node {key!r}: id must be a nonblank string")
        if str(key) != node_id:
            raise ValueError(f"node mapping key {key!r} must equal node.id {node_id!r}")
        class_type = entry.get("class_type")
        if not isinstance(class_type, str) or not class_type.strip():
            raise ValueError(f"node {node_id!r}: class_type must be a nonblank string")
        uid = entry.get("uid")
        if not isinstance(uid, str) or not uid.strip():
            raise ValueError(f"node {node_id!r}: uid must be a nonblank string")
        pack = entry.get("pack")
        if pack is not None and not isinstance(pack, str):
            raise ValueError(f"node {node_id!r}: pack must be a string or null")
        for field_name in ("inputs", "widgets", "metadata"):
            value = entry.get(field_name)
            if not isinstance(value, dict):
                raise ValueError(f"node {node_id!r}: {field_name} must be a mapping")
        raw_widgets = entry.get("raw_widgets")
        raw_widget_payload: RawWidgetPayload | None = None
        if raw_widgets is not None:
            if not isinstance(raw_widgets, dict) or not {
                "values",
                "shape",
                "source",
                "has_dict_rows",
                "length",
            } <= set(raw_widgets):
                raise ValueError(
                    f"node {node_id!r}: raw_widgets must be a RawWidgetPayload mapping or null"
                )
            length = raw_widgets["length"]
            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.length must be a nonnegative integer"
                )
            shape = raw_widgets["shape"]
            source_name = raw_widgets["source"]
            has_dict_rows = raw_widgets["has_dict_rows"]
            if not isinstance(shape, str) or not shape.strip():
                raise ValueError(
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
        node_pos = _decode_envelope_geometry(entry, node_metadata, "pos", node_id)
        node_size = _decode_envelope_geometry(entry, node_metadata, "size", node_id)
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
            pos=node_pos,
            size=node_size,
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
    embedded_links = _embedded_api_link_details(workflow)
    if embedded_links:
        raise ValueError(
            "embedded_api_link: "
            + _embedded_api_link_message(
                embedded_links[0], surface="serialized vibe envelope decode"
            )
        )

    inputs_raw = raw.get("inputs")
    if not isinstance(inputs_raw, dict):
        raise ValueError("serialized vibe envelope 'inputs' must be a mapping")
    for name, entry in inputs_raw.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"input {name!r}: input entries must be mappings, got {type(entry).__name__}"
            )
        input_name = entry.get("name")

codex
The core diff is small, but one task-level concern is emerging: token access was made direct in `VibeWorkflow`, while production lifecycle code in `templates.py` still uses `getattr`. I’m checking the frozen task wording and whether this is a true gate violation or deliberately scoped to the class methods.
exec
/bin/zsh -lc "rg -n \"Batch K|workflow_context_token|collision-safe|direct access|task 4|_reconcile_uid_counter\" .megaplan .oracle tasklist.md . 2>/dev/null --glob 'tasklist.md' --glob '*.md' --glob '*.json' | head -n 240" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
.oracle/tasklist.md:195:## Batch K — Declare the workflow context token
.oracle/tasklist.md:201:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/tasklist.md:207:4. Make unseeded counter-generated UID minting collision-safe for deserialized or otherwise pre-populated workflows. *(oracle-approved addition, checkpoint 2)*
.oracle/plan.md:184:## Batch K — Declare the workflow context token
.oracle/plan.md:190:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/plan-rev1.md:424:### Batch K — Declare workflow context token
.oracle/plan-rev1.md:436:- Add `_workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`.
.oracle/plan-rev1.md:437:- Replace token-related `getattr`/`hasattr`, dynamic creation, and deletion with direct access/assignment.
.oracle/plan-rev1.md:438:- Ensure `copy()` always produces `_workflow_context_token is None`; use a deepcopy memo for an actively bound `contextvars.Token`.
.oracle/plan-rev1.md:882:            getattr(self, "_workflow_context_token", None) is not None
.oracle/plan-rev1.md:886:        if getattr(self, "_workflow_context_token", None) is not None:
.oracle/plan-rev1.md:891:        self._workflow_context_token = bind_workflow(self)
.oracle/plan-rev1.md:897:        token = getattr(self, "_workflow_context_token", None)
.oracle/plan-rev1.md:1427:        if hasattr(cloned, "_workflow_context_token"):
.oracle/plan-rev1.md:1428:            del cloned._workflow_context_token
.oracle/plan-rev1.md:2152:## Batch K — Declare the workflow context token
.oracle/plan-rev1.md:2158:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/plan-rev1.md:2389:## Batch K — Declare the workflow context token
.oracle/plan-rev1.md:2395:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/plan-rev1-clean.md:184:## Batch K — Declare the workflow context token
.oracle/plan-rev1-clean.md:190:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/plan-rev1-clean.md:421:## Batch K — Declare the workflow context token
.oracle/plan-rev1-clean.md:427:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/plan-clean.md:176:### Batch K — Declare workflow context token
.oracle/plan-clean.md:188:- Add `_workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`.
.oracle/plan-clean.md:189:- Replace token-related `getattr`/`hasattr`, dynamic creation, and deletion with direct access/assignment.
.oracle/plan-clean.md:190:- Ensure `copy()` always produces `_workflow_context_token is None`; use a deepcopy memo for an actively bound `contextvars.Token`.
.oracle/checkins/batch-2.md:38:2. **Modify Batch K — UID minting collision-safe after envelope decoding.** Claimed reproduction: decode a workflow containing uid="n1", then wf.node(...) mints n1 again (uid_counter unaware of decoded uids). Currently Batch K covers only the _workflow_context_token declaration + copy() memo.
.oracle/checkins/batch-2.md:42:2. Ruling on the two adjustment proposals: approve/reject/modify, and if approved, the exact task wording to add to tasklist.md Batch D+E and Batch K.
.oracle/checkins/batch-2.md:468:/bin/zsh -lc "PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model='deepseek:deepseek-v4-flash' --toolsets='file,web,terminal' --project-dir='/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2' --query='Read-only adversarial oracle verification. Do not modify files. Review git diff 2b60f74a..ec13a34e for Batch B removal of public convert_to_vibe_format dispatcher. Acceptance: remove it from ingest/normalize.py and ingest/__init__.py; migrate callers correctly among from_api/from_ui/from_envelope including _frag_ingest split on _is_vibe_envelope and scratchpad generated code; keep _named_import and workbench boundaries unchanged; update tests to structural equivalence; only negative guard Python hit; exports correct; offline routes remain offline; diff check clean. Inspect actual files and git history. Also assess two proposed future plan additions for necessity and minimal precise scope: (1) Batch D+E canonicalize raw API link pairs into VibeEdge or explicitly normalize/reject link-shaped node.inputs, testing edge/input collisions; (2) Batch K ensure UID minting after envelope decoding cannot collide with decoded UIDs such as n1. Return a firm concise report with file:line evidence, concrete Batch B issues or PASS recommendation, and approve/reject/modify each proposal. Favor KISS/YAGNI and flag overengineering.'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
.oracle/checkins/batch-2.md:685:## Batch K — Declare the workflow context token
.oracle/checkins/batch-2.md:691:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/checkins/batch-2.md:6874:.oracle/checkins/batch-2.md:38:2. **Modify Batch K — UID minting collision-safe after envelope decoding.** Claimed reproduction: decode a workflow containing uid="n1", then wf.node(...) mints n1 again (uid_counter unaware of decoded uids). Currently Batch K covers only the _workflow_context_token declaration + copy() memo.
.oracle/checkins/batch-2.md:6875:.oracle/checkins/batch-2.md:468:/bin/zsh -lc "PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model='deepseek:deepseek-v4-flash' --toolsets='file,web,terminal' --project-dir='/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2' --query='Read-only adversarial oracle verification. Do not modify files. Review git diff 2b60f74a..ec13a34e for Batch B removal of public convert_to_vibe_format dispatcher. Acceptance: remove it from ingest/normalize.py and ingest/__init__.py; migrate callers correctly among from_api/from_ui/from_envelope including _frag_ingest split on _is_vibe_envelope and scratchpad generated code; keep _named_import and workbench boundaries unchanged; update tests to structural equivalence; only negative guard Python hit; exports correct; offline routes remain offline; diff check clean. Inspect actual files and git history. Also assess two proposed future plan additions for necessity and minimal precise scope: (1) Batch D+E canonicalize raw API link pairs into VibeEdge or explicitly normalize/reject link-shaped node.inputs, testing edge/input collisions; (2) Batch K ensure UID minting after envelope decoding cannot collide with decoded UIDs such as n1. Return a firm concise report with file:line evidence, concrete Batch B issues or PASS recommendation, and approve/reject/modify each proposal. Favor KISS/YAGNI and flag overengineering.'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
.oracle/checkins/batch-2.md:8635:   195	            getattr(self, "_workflow_context_token", None) is not None
.oracle/checkins/batch-2.md:8639:   199	        if getattr(self, "_workflow_context_token", None) is not None:
.oracle/checkins/batch-2.md:8644:   204	        self._workflow_context_token = bind_workflow(self)
.oracle/checkins/batch-2.md:8650:   210	        token = getattr(self, "_workflow_context_token", None)
.oracle/checkins/batch-2.md:8653:   213	            self._workflow_context_token = None
.oracle/checkins/batch-2.md:8689:   249	        if hasattr(cloned, "_workflow_context_token"):
.oracle/checkins/batch-2.md:8690:   250	            del cloned._workflow_context_token
.oracle/checkins/batch-2.md:9309:.oracle/checkins/batch-2.md:38:2. **Modify Batch K — UID minting collision-safe after envelope decoding.** Claimed reproduction: decode a workflow containing uid="n1", then wf.node(...) mints n1 again (uid_counter unaware of decoded uids). Currently Batch K covers only the _workflow_context_token declaration + copy() memo.
.oracle/checkins/batch-2.md:9310:.oracle/checkins/batch-2.md:468:/bin/zsh -lc "PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model='deepseek:deepseek-v4-flash' --toolsets='file,web,terminal' --project-dir='/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2' --query='Read-only adversarial oracle verification. Do not modify files. Review git diff 2b60f74a..ec13a34e for Batch B removal of public convert_to_vibe_format dispatcher. Acceptance: remove it from ingest/normalize.py and ingest/__init__.py; migrate callers correctly among from_api/from_ui/from_envelope including _frag_ingest split on _is_vibe_envelope and scratchpad generated code; keep _named_import and workbench boundaries unchanged; update tests to structural equivalence; only negative guard Python hit; exports correct; offline routes remain offline; diff check clean. Inspect actual files and git history. Also assess two proposed future plan additions for necessity and minimal precise scope: (1) Batch D+E canonicalize raw API link pairs into VibeEdge or explicitly normalize/reject link-shaped node.inputs, testing edge/input collisions; (2) Batch K ensure UID minting after envelope decoding cannot collide with decoded UIDs such as n1. Return a firm concise report with file:line evidence, concrete Batch B issues or PASS recommendation, and approve/reject/modify each proposal. Favor KISS/YAGNI and flag overengineering.'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
.oracle/checkins/batch-2.md:9312:.oracle/checkins/batch-2.md:6874:.oracle/checkins/batch-2.md:38:2. **Modify Batch K — UID minting collision-safe after envelope decoding.** Claimed reproduction: decode a workflow containing uid="n1", then wf.node(...) mints n1 again (uid_counter unaware of decoded uids). Currently Batch K covers only the _workflow_context_token declaration + copy() memo.
.oracle/checkins/batch-2.md:9313:.oracle/checkins/batch-2.md:6875:.oracle/checkins/batch-2.md:468:/bin/zsh -lc "PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model='deepseek:deepseek-v4-flash' --toolsets='file,web,terminal' --project-dir='/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2' --query='Read-only adversarial oracle verification. Do not modify files. Review git diff 2b60f74a..ec13a34e for Batch B removal of public convert_to_vibe_format dispatcher. Acceptance: remove it from ingest/normalize.py and ingest/__init__.py; migrate callers correctly among from_api/from_ui/from_envelope including _frag_ingest split on _is_vibe_envelope and scratchpad generated code; keep _named_import and workbench boundaries unchanged; update tests to structural equivalence; only negative guard Python hit; exports correct; offline routes remain offline; diff check clean. Inspect actual files and git history. Also assess two proposed future plan additions for necessity and minimal precise scope: (1) Batch D+E canonicalize raw API link pairs into VibeEdge or explicitly normalize/reject link-shaped node.inputs, testing edge/input collisions; (2) Batch K ensure UID minting after envelope decoding cannot collide with decoded UIDs such as n1. Return a firm concise report with file:line evidence, concrete Batch B issues or PASS recommendation, and approve/reject/modify each proposal. Favor KISS/YAGNI and flag overengineering.'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
.oracle/checkins/batch-2.md:11022:### 2. Batch K collision-safe UID minting: MODIFY AND APPROVE
.oracle/checkins/batch-2.md:11028:> 4. Make unseeded counter-generated UID minting collision-safe for deserialized or otherwise pre-populated workflows.
.oracle/checkins/batch-2.md:11079:### 2. Batch K collision-safe UID minting: MODIFY AND APPROVE
.oracle/checkins/batch-2.md:11085:> 4. Make unseeded counter-generated UID minting collision-safe for deserialized or otherwise pre-populated workflows.
.oracle/checkins/batch-1-rev2.md:747:## Batch K — Declare the workflow context token
.oracle/checkins/batch-1-rev2.md:753:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
.oracle/checkins/batch-1-rev2.md:5556:   249	        if hasattr(cloned, "_workflow_context_token"):
.oracle/checkins/batch-1-rev2.md:5557:   250	            del cloned._workflow_context_token
.oracle/checkins/batch-5.md:17:You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 5 — review Batch K (Declare the workflow context token + collision-safe UID minting).
.oracle/checkins/batch-5.md:19:Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 2ddd1f06 (Batch C). Batch K commit: 06d94e4a530e67ac72fd805c20b302b83666e963. Review `git diff 2ddd1f06..HEAD` (ignore the 11c788bf checkpoint-record commit's .oracle whitespace).
.oracle/checkins/batch-5.md:21:## Batch K tasks + acceptance gate (frozen tasklist.md incl. your oracle-approved task 4)
.oracle/checkins/batch-5.md:22:(1) _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False). (2) Replace token getattr/hasattr/creation/deletion with direct access. (3) copy() deepcopy memo mapping active contextvars.Token to None — every clone unbound. (4) Collision-safe unseeded UID minting: reconcile _uid_counter with existing flat n<positive-integer> auto-minted uids, choose next unoccupied n<N>; preserve imported uids verbatim; monotonic; no parallel registry / no id: redesign.
.oracle/checkins/batch-5.md:28:- Acceptance claimed met: token field declared; __enter__/__exit__ direct access; copy() memo pre-seeds {id(token): None}; _mint_uid calls _reconcile_uid_counter() before unseeded mints (raises counter to largest existing n<N>, never lowers); imported uids preserved (42, id:abc, explicit-uid, n7 unchanged); sparse n1/n5/n100 case mints beyond.
.oracle/checkins/batch-5.md:494:06d94e4a (HEAD -> elegance-run2) megado run2 Batch K: declare _workflow_context_token, direct field access, copy memo for bound workflows, collision-safe unseeded UID minting
.oracle/checkins/batch-5.md:500:8a8300bb megado run2: oracle-approved plan adjustments — D+E#6 VibeEdge sole connectivity authority, K#4 collision-safe UID minting
.oracle/checkins/batch-5.md:7962:    megado run2 Batch K: declare _workflow_context_token, direct field access, copy memo for bound workflows, collision-safe unseeded UID minting
.oracle/checkins/batch-5.md:7975:+    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)
.oracle/checkins/batch-5.md:7984:-            getattr(self, "_workflow_context_token", None) is not None
.oracle/checkins/batch-5.md:7987:+        if self._workflow_context_token is not None and active_workflow() is self:
.oracle/checkins/batch-5.md:7989:-        if getattr(self, "_workflow_context_token", None) is not None:
.oracle/checkins/batch-5.md:7990:+        if self._workflow_context_token is not None:
.oracle/checkins/batch-5.md:7998:-        token = getattr(self, "_workflow_context_token", None)
.oracle/checkins/batch-5.md:7999:+        token = self._workflow_context_token
.oracle/checkins/batch-5.md:8002:             self._workflow_context_token = None
.oracle/checkins/batch-5.md:8013:+        clone is therefore unbound (``_workflow_context_token is None``).
.oracle/checkins/batch-5.md:8016:-        if hasattr(cloned, "_workflow_context_token"):
.oracle/checkins/batch-5.md:8017:-            del cloned._workflow_context_token
.oracle/checkins/batch-5.md:8019:+        memo = {id(self._workflow_context_token): None}
.oracle/checkins/batch-5.md:8037:+            self._reconcile_uid_counter()
.oracle/checkins/batch-5.md:8042:+    def _reconcile_uid_counter(self) -> None:
.oracle/checkins/batch-5.md:8065:/bin/zsh -lc "nl -ba vibecomfy/workflow.py | sed -n '1,360p'; nl -ba vibecomfy/workflow.py | sed -n '470,620p'; rg -n \"_workflow_context_token|_uid_counter|_mint_uid|uid=\" vibecomfy tests | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
.oracle/checkins/batch-5.md:8292:   226	    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)
.oracle/checkins/batch-5.md:8300:   234	        if self._workflow_context_token is not None and active_workflow() is self:
.oracle/checkins/batch-5.md:8302:   236	        if self._workflow_context_token is not None:
.oracle/checkins/batch-5.md:8307:   241	        self._workflow_context_token = bind_workflow(self)
.oracle/checkins/batch-5.md:8313:   247	        token = self._workflow_context_token
.oracle/checkins/batch-5.md:8316:   250	            self._workflow_context_token = None
.oracle/checkins/batch-5.md:8350:   284	        clone is therefore unbound (``_workflow_context_token is None``).
.oracle/checkins/batch-5.md:8352:   286	        memo = {id(self._workflow_context_token): None}
.oracle/checkins/batch-5.md:8483:   526	            self._reconcile_uid_counter()
.oracle/checkins/batch-5.md:8488:   531	    def _reconcile_uid_counter(self) -> None:
.oracle/checkins/batch-5.md:8880:/bin/zsh -lc "rg -n \"_workflow_context_token\" . --glob '"'!'"\\.oracle/**' --glob '"'!*.md'"'; sed -n '513,610p' vibecomfy/workflow.py; rg -n \"def _decode_serialized_vibe|VibeNode\\(\" vibecomfy/ingest/normalize.py | head -n 40; sed -n '560,700p' vibecomfy/ingest/normalize.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
.oracle/checkins/batch-5.md:8882:./tools/check_canonical_parity.py:217:    token = getattr(workflow, "_workflow_context_token", None) if workflow is not None else None
.oracle/checkins/batch-5.md:8883:./tools/check_canonical_parity.py:224:    workflow._workflow_context_token = None
.oracle/checkins/batch-5.md:8884:./tests/test_templates_module.py:225:        wf._workflow_context_token = None
.oracle/checkins/batch-5.md:8885:./tests/test_templates_module.py:241:        wf._workflow_context_token = None
.oracle/checkins/batch-5.md:8886:./tests/test_templates_module.py:255:        outer._workflow_context_token = None
.oracle/checkins/batch-5.md:8887:./tests/test_templates_module.py:270:        wf._workflow_context_token = None
.oracle/checkins/batch-5.md:8888:./tests/test_templates_module.py:284:            wf._workflow_context_token = None
.oracle/checkins/batch-5.md:8889:./vibecomfy/workflow.py:226:    _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)
.oracle/checkins/batch-5.md:8890:./vibecomfy/workflow.py:234:        if self._workflow_context_token is not None and active_workflow() is self:
.oracle/checkins/batch-5.md:8891:./vibecomfy/workflow.py:236:        if self._workflow_context_token is not None:
.oracle/checkins/batch-5.md:8892:./vibecomfy/workflow.py:241:        self._workflow_context_token = bind_workflow(self)
.oracle/checkins/batch-5.md:8893:./vibecomfy/workflow.py:247:        token = self._workflow_context_token
.oracle/checkins/batch-5.md:8894:./vibecomfy/workflow.py:250:            self._workflow_context_token = None
.oracle/checkins/batch-5.md:8895:./vibecomfy/workflow.py:284:        clone is therefore unbound (``_workflow_context_token is None``).
.oracle/checkins/batch-5.md:8896:./vibecomfy/workflow.py:286:        memo = {id(self._workflow_context_token): None}
.oracle/checkins/batch-5.md:8897:./vibecomfy/templates.py:106:    if getattr(wf, "_workflow_context_token", None) is None:
.oracle/checkins/batch-5.md:8898:./vibecomfy/templates.py:120:            existing_token = getattr(existing, "_workflow_context_token", None)
.oracle/checkins/batch-5.md:8899:./vibecomfy/templates.py:126:        wf._workflow_context_token = bind_workflow(wf)
.oracle/checkins/batch-5.md:8900:./vibecomfy/templates.py:561:    token = getattr(wf, "_workflow_context_token", None)
.oracle/checkins/batch-5.md:8901:./vibecomfy/templates.py:569:        wf._workflow_context_token = None
.oracle/checkins/batch-5.md:8915:            self._reconcile_uid_counter()
.oracle/checkins/batch-5.md:8920:    def _reconcile_uid_counter(self) -> None:
.oracle/checkins/batch-3.md:291:8a8300bb megado run2: oracle-approved plan adjustments — D+E#6 VibeEdge sole connectivity authority, K#4 collision-safe UID minting
.oracle/checkins/batch-3.md:4922:             getattr(self, "_workflow_context_token", None) is not None
.oracle/checkins/batch-3.md:4926:         if getattr(self, "_workflow_context_token", None) is not None:
.oracle/checkins/batch-3.md:4931:         self._workflow_context_token = bind_workflow(self)
.oracle/checkins/batch-3.md:4937:         token = getattr(self, "_workflow_context_token", None)
.oracle/checkins/batch-3.md:4940:             self._workflow_context_token = None
.oracle/checkins/batch-3.md:4976:         if hasattr(cloned, "_workflow_context_token"):
.oracle/checkins/batch-3.md:4977:             del cloned._workflow_context_token
.oracle/checkins/batch-3.md:5862:   196	            getattr(self, "_workflow_context_token", None) is not None
.oracle/checkins/batch-3.md:5866:   200	        if getattr(self, "_workflow_context_token", None) is not None:
.oracle/checkins/batch-3.md:5871:   205	        self._workflow_context_token = bind_workflow(self)
.oracle/checkins/batch-3.md:5877:   211	        token = getattr(self, "_workflow_context_token", None)
.oracle/checkins/batch-3.md:5880:   214	            self._workflow_context_token = None
.oracle/checkins/batch-3.md:5916:   250	        if hasattr(cloned, "_workflow_context_token"):
.oracle/checkins/batch-3.md:5917:   251	            del cloned._workflow_context_token
.oracle/checkins/batch-1-rev.md:408:## Batch K — Declare the workflow context token
.oracle/checkins/batch-1-rev.md:414:   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`
./docs/architecture/python_on_the_graph.md:569:- **[verified] Plugin surface not collision-safe / not deterministic.** Block & patch registries

exec
/bin/zsh -lc "sed -n '184,224p' .oracle/tasklist.md; sed -n '168,205p' .oracle/plan-clean.md; sed -n '11010,11045p' .oracle/checkins/batch-2.md; git diff --check 2ddd1f06..HEAD -- vibecomfy/workflow.py; git diff --name-status 2ddd1f06..HEAD -- . ':(exclude).oracle/**'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
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

4. Make unseeded counter-generated UID minting collision-safe for deserialized or otherwise pre-populated workflows. *(oracle-approved addition, checkpoint 2)*

   - Before an unseeded mint, reconcile `_uid_counter` with existing flat auto-minted `n<positive-integer>` UIDs and choose the next unoccupied `n<N>`.
   - Preserve imported UIDs verbatim and keep the counter monotonic.
   - Do not introduce a parallel UID registry or expand this task into seeded `id:...` identity redesign or global duplicate-import validation.

Acceptance gate:

- Bound and unbound copies succeed and have token `None`.
- Constructor, repr, equality, and envelope omit the field.
- Enter/exit, eager binding, finalize, nesting rejection, exception cleanup, and async isolation pass.
- No context token leaks into serialization.
- After decoding an envelope containing `uid="n1"`, including a sparse higher `n<N>` case, newly added nodes receive distinct UIDs beyond the imported auto-minted range.
- Repeated mints and copies remain monotonic; nonmatching imported UIDs remain unchanged.

## Checkpoint structure

After each batch:
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
>    - Migrate all package-owned low-level construction that stores Comfy API link pairs in `VibeNode.inputs` to construct `VibeEdge` objects instead; update affected tests and fixtures.
>    - Keep `from_api()` and `from_ui()` as normalization boundaries: incoming API link pairs become edges and are absent from `node.inputs`.
>    - Outside those ingestion boundaries, fail closed with a targeted error when an API-link-shaped value remains in `VibeNode.inputs` during envelope decode, validation, serialization, or compilation. Compilation must not mutate the IR or silently choose between embedded-input and edge authority.
>    - Use the canonical API-link predicate narrowly so ordinary two-element literal lists are not rejected.
>    - Test raw-link-only inputs and raw-link-plus-edge collisions with both identical and conflicting sources, plus unchanged compiled output for canonical edge-only workflows.

Add to its acceptance gate:

> - No package-owned low-level `VibeNode` construction stores API link pairs in `inputs`, and no serialized envelope contains them.
> - Raw-link/edge collisions fail explicitly rather than compiling with implicit edge-wins precedence.
> - Canonical `from_api()`/`from_ui()` ingestion and edge-only compile round trips remain unchanged.

### 2. Batch K collision-safe UID minting: MODIFY AND APPROVE

The defect reproduces: envelope decoding preserves `uid="n1"` while leaving `_uid_counter` at zero; the next unseeded `node()` also mints `n1`. The relevant paths are [normalize.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/ingest/normalize.py:514) and [workflow.py](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:470).

Add:

> 4. Make unseeded counter-generated UID minting collision-safe for deserialized or otherwise pre-populated workflows.
>
>    - Before an unseeded mint, reconcile `_uid_counter` with existing flat auto-minted `n<positive-integer>` UIDs and choose the next unoccupied `n<N>`.
>    - Preserve imported UIDs verbatim and keep the counter monotonic.
>    - Do not introduce a parallel UID registry or expand this task into seeded `id:...` identity redesign or global duplicate-import validation.

Add to its acceptance gate:

> - After decoding an envelope containing `uid="n1"`, including a sparse higher `n<N>` case, newly added nodes receive distinct UIDs beyond the imported auto-minted range.
> - Repeated mints and copies remain monotonic; nonmatching imported UIDs remain unchanged.
tokens used
188,846
## Batch B verdict: PASS

The acceptance gate is satisfied:

- Dispatcher removed; only the intentional negative guard remains.
- Public ingest exports are `from_envelope`, `from_ui`, and `from_api`.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	vibecomfy/workflow.py

exec
/bin/zsh -lc "rg -n \"copy|context|token|eager|finalize|nest|async|exception|uid|envelope\" tests/test_workflow_core.py tests/test_templates_module.py tests/test_workflow_context.py | head -n 300; sed -n '80,145p' vibecomfy/templates.py; sed -n '535,580p' vibecomfy/templates.py; sed -n '190,235p' tools/check_canonical_parity.py" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
tests/test_workflow_context.py:3:"""Concurrency contract tests for workflow_context module.
tests/test_workflow_context.py:7:2. asyncio.gather isolates active workflows per task
tests/test_workflow_context.py:9:4. Post-exit: compile works, context-bound node() fails with remediation message
tests/test_workflow_context.py:10:5. _current_workflow_or_raise() outside context includes remediation message
tests/test_workflow_context.py:11:6. ContextVar survives await inside async build body
tests/test_workflow_context.py:17:import asyncio
tests/test_workflow_context.py:25:from vibecomfy.workflow_context import _current_workflow_or_raise, active_workflow
tests/test_workflow_context.py:28:_METADATA: dict[str, Any] = {"ready_template": "test/context"}
tests/test_workflow_context.py:32:# Contract 1: nested new_workflow(...) raises RuntimeError
tests/test_workflow_context.py:36:def test_nested_new_workflow_raises_runtime_error() -> None:
tests/test_workflow_context.py:38:    from workflow_context.bind_workflow."""
tests/test_workflow_context.py:41:        with pytest.raises(RuntimeError, match="Nested workflow contexts"):
tests/test_workflow_context.py:47:# Contract 2: asyncio.gather isolates active workflows per task
tests/test_workflow_context.py:51:@pytest.mark.asyncio
tests/test_workflow_context.py:52:async def test_asyncio_gather_isolates_workflows() -> None:
tests/test_workflow_context.py:53:    """Each asyncio task sees only its own workflow."""
tests/test_workflow_context.py:56:    async def build_in_context(task_id: int) -> tuple[int, str | None]:
tests/test_workflow_context.py:57:        metadata = {"ready_template": f"test/context-{task_id}"}
tests/test_workflow_context.py:67:    tasks = [build_in_context(i) for i in range(3)]
tests/test_workflow_context.py:68:    gathered = await asyncio.gather(*tasks)
tests/test_workflow_context.py:76:        assert f"context-{task_id}" in wf_id
tests/test_workflow_context.py:121:# Contract 4: post-exit compile works, context-bound node() fails
tests/test_workflow_context.py:126:    """After context exit, wf.compile('api') works but context-bound
tests/test_workflow_context.py:141:    # Active workflow should be None outside context
tests/test_workflow_context.py:154:# Contract 5: _current_workflow_or_raise() outside context includes
tests/test_workflow_context.py:159:def test_current_workflow_or_raise_outside_context_remediation_message() -> None:
tests/test_workflow_context.py:160:    """The error message from _current_workflow_or_raise() outside a context
tests/test_workflow_context.py:162:    # Ensure we are outside any context
tests/test_workflow_context.py:180:@pytest.mark.asyncio
tests/test_workflow_context.py:181:async def test_contextvar_survives_await() -> None:
tests/test_workflow_context.py:182:    """The ContextVar survives an await inside an async def using the context."""
tests/test_workflow_context.py:184:    async def async_operation() -> str:
tests/test_workflow_context.py:185:        # Simulate an async operation
tests/test_workflow_context.py:186:        await asyncio.sleep(0)
tests/test_workflow_context.py:189:    async def build_with_await() -> VibeWorkflow:
tests/test_workflow_context.py:190:        with new_workflow({"ready_template": "test/async-context"}) as wf:
tests/test_workflow_context.py:195:            # Await — context should survive
tests/test_workflow_context.py:196:            result = await async_operation()
tests/test_workflow_context.py:199:            # After await, context should still be bound
tests/test_workflow_context.py:204:            node_builder = templates_node("LoadImage", image="async-test.png")
tests/test_workflow_context.py:213:    # After context exit, verify context is unbound
tests/test_templates_module.py:3:import asyncio
tests/test_templates_module.py:10:from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, SymbolicNodeRef, _current_workflow_or_raise, _derive_output_kind, finalize, new_workflow, node
tests/test_templates_module.py:65:        return finalize(wf, public_inputs, {"ready_template": "image/legacy_ref"}, output_node=saved, output_type="SaveImage")
tests/test_templates_module.py:85:def test_id_map_returns_defensive_copy_from_set_id_map() -> None:
tests/test_templates_module.py:96:def test_finalize_resolves_symbolic_inputspec_from_build_locals() -> None:
tests/test_templates_module.py:110:        return finalize(wf, inputs, metadata, output_node=saved.node.id, output_kind="image", output_type="SaveImage")
tests/test_templates_module.py:119:def test_workflow_finalize_method_autodetects_single_terminal_output() -> None:
tests/test_templates_module.py:132:    result = wf.finalize(inputs, metadata=metadata, output_type="SaveImage", name="image")
tests/test_templates_module.py:139:def test_workflow_finalize_method_accepts_output_node_handle() -> None:
tests/test_templates_module.py:152:    wf.finalize(inputs, metadata=metadata, output_node=saved, output_type="SaveImage", name="image")
tests/test_templates_module.py:157:def test_finalize_prunes_auto_input_shadowed_by_explicit_public_input() -> None:
tests/test_templates_module.py:170:    wf.finalize(inputs, metadata=metadata, output_node=saved, output_type="SaveImage", name="image")
tests/test_templates_module.py:176:def test_workflow_finalize_method_rejects_ambiguous_terminal_outputs() -> None:
tests/test_templates_module.py:191:        wf.finalize(inputs, metadata=metadata, output_type="SaveImage")
tests/test_templates_module.py:211:    # Post-revert: new_workflow() eagerly binds the ContextVar so that the
tests/test_templates_module.py:214:    # ``wf.finalize(...)`` releases the binding.
tests/test_templates_module.py:221:        # Clean up so subsequent tests start with a clean context.
tests/test_templates_module.py:222:        from vibecomfy.workflow_context import _CURRENT_WORKFLOW
tests/test_templates_module.py:225:        wf._workflow_context_token = None
tests/test_templates_module.py:228:def test_workflow_context_propagates() -> None:
tests/test_templates_module.py:238:        from vibecomfy.workflow_context import _CURRENT_WORKFLOW
tests/test_templates_module.py:241:        wf._workflow_context_token = None
tests/test_templates_module.py:244:def test_nested_workflow_context_raises() -> None:
tests/test_templates_module.py:247:        with pytest.raises(RuntimeError, match="Nested workflow contexts not supported"):
tests/test_templates_module.py:249:            # held by the caller) raises bind_workflow's nested-contexts error.
tests/test_templates_module.py:252:        from vibecomfy.workflow_context import _CURRENT_WORKFLOW
tests/test_templates_module.py:255:        outer._workflow_context_token = None
tests/test_templates_module.py:258:def test_exception_in_workflow_context_unbinds() -> None:
tests/test_templates_module.py:267:        from vibecomfy.workflow_context import _CURRENT_WORKFLOW
tests/test_templates_module.py:270:        wf._workflow_context_token = None
tests/test_templates_module.py:273:def test_workflow_context_isolated_across_async_tasks() -> None:
tests/test_templates_module.py:274:    async def build(template_id: str) -> str:
tests/test_templates_module.py:278:                await asyncio.sleep(0)
tests/test_templates_module.py:281:            from vibecomfy.workflow_context import _CURRENT_WORKFLOW
tests/test_templates_module.py:284:            wf._workflow_context_token = None
tests/test_templates_module.py:286:    async def run_builds() -> list[str]:
tests/test_templates_module.py:287:        return list(await asyncio.gather(build("image/one"), build("image/two")))
tests/test_templates_module.py:289:    assert asyncio.run(run_builds()) == ["image/one", "image/two"]
tests/test_templates_module.py:380:    assert metadata["edit_guide"] == "Public inputs:\n- prompt: Prompt text.\n- image: Controls image."
tests/test_templates_module.py:386:def test_ready_metadata_build_appends_edit_guide_extra_and_warns_once_on_model_disagreement() -> None:
tests/test_templates_module.py:404:            edit_guide_extra="Use short prompts for smoke tests.",
tests/test_templates_module.py:416:    assert metadata["edit_guide"] == "Public inputs:\n- prompt: Text prompt.\nUse short prompts for smoke tests."
tests/test_templates_module.py:422:def test_finalize_preserves_source_requirements_and_image_output_contract() -> None:
tests/test_templates_module.py:445:    finalize(
tests/test_templates_module.py:486:def test_finalize_binds_output_contracts_across_artifact_kinds_without_output_kind(
tests/test_templates_module.py:504:    finalize(
tests/test_templates_module.py:540:def test_finalize_derives_model_requirements_from_metadata_when_requirements_empty() -> None:
tests/test_templates_module.py:559:    finalize(wf, inputs, metadata, output_node="2", output_type="SaveImage", requirements={})
tests/test_templates_module.py:564:def test_finalize_preserves_edit_style_image_input_defaults() -> None:
tests/test_templates_module.py:589:    finalize(
tests/test_templates_module.py:607:def test_finalize_allows_unrelated_auto_inputs_but_rejects_public_target_drift() -> None:
tests/test_templates_module.py:622:    finalize(wf, inputs, metadata, output_node="4", output_kind="image", output_type="SaveImage")
tests/test_templates_module.py:641:        finalize(
tests/test_templates_module.py:651:def test_finalize_merges_metadata_custom_nodes_into_wf_requirements() -> None:
tests/test_templates_module.py:666:    # Call finalize WITHOUT explicit requirements= — metadata requirements should flow through.
tests/test_templates_module.py:667:    finalize(wf, inputs, metadata, output_node="2", output_kind="image", output_type="SaveImage")
tests/test_templates_module.py:673:def test_finalize_unions_custom_nodes_from_both_sources() -> None:
tests/test_templates_module.py:688:    # Call finalize WITH explicit requirements that overlap.
tests/test_templates_module.py:689:    finalize(
tests/test_templates_module.py:707:def test_finalize_uses_metadata_output_prefix_as_filename_fallback() -> None:
tests/test_templates_module.py:708:    """T4(b): metadata output_prefix reaches finalized output when filename_prefix omitted."""
tests/test_templates_module.py:721:    # Call finalize WITHOUT filename_prefix — should fall back to metadata output_prefix.
tests/test_templates_module.py:722:    finalize(wf, inputs, metadata, output_node="2", output_kind="image", output_type="SaveImage")
tests/test_templates_module.py:728:def test_finalize_explicit_filename_prefix_overrides_metadata_output_prefix() -> None:
tests/test_templates_module.py:742:    finalize(
tests/test_templates_module.py:933:def test_canonical_finalize_does_not_warn() -> None:
tests/test_templates_module.py:934:    """T19: Canonical finalize() path suppresses PendingDeprecationWarning."""
tests/test_templates_module.py:949:        finalize(wf, inputs, metadata, output_node="2", output_kind="image", output_type="SaveImage")
tests/test_templates_module.py:973:def test_static_contract_extracts_public_outputs_from_finalize() -> None:
tests/test_templates_module.py:974:    """T5(b): static_contract derives public_outputs from finalize(..., output_node=...) call."""
tests/test_templates_module.py:981:    # Should find at least one output from finalize call
tests/test_templates_module.py:982:    finalize_outputs = [item for item in contract["public_outputs"] if item.get("source") == "finalize"]
tests/test_templates_module.py:983:    assert len(finalize_outputs) > 0, "No outputs extracted from finalize()"
tests/test_templates_module.py:984:    output = finalize_outputs[0]
tests/test_templates_module.py:989:def test_static_contract_extracts_public_outputs_from_workflow_finalize_method(tmp_path: Path) -> None:
tests/test_templates_module.py:1010:    return wf.finalize(PUBLIC_INPUTS, metadata=READY_METADATA, output_node=saved, output_type="SaveImage", name="image")
tests/test_templates_module.py:1018:    assert contract["public_outputs"][0]["source"] == "finalize"
tests/test_templates_module.py:1021:def test_static_contract_extracts_autodetected_workflow_finalize_output(tmp_path: Path) -> None:
tests/test_templates_module.py:1042:    return wf.finalize(PUBLIC_INPUTS, metadata=READY_METADATA, output_type="SaveImage", name="image")
tests/test_workflow_core.py:4:from copy import deepcopy
tests/test_workflow_core.py:17:    from_envelope,
tests/test_workflow_core.py:76:    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
tests/test_workflow_core.py:85:        uid="uid-2",
tests/test_workflow_core.py:88:    before = workflow.copy()
tests/test_workflow_core.py:105:    envelope = workflow.to_envelope()
tests/test_workflow_core.py:106:    assert envelope["nodes"]["2"]["inputs"] == {
tests/test_workflow_core.py:111:    restored = from_envelope(envelope)
tests/test_workflow_core.py:131:    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
tests/test_workflow_core.py:133:        "2", "Sink", inputs={"image": ["1", 0]}, uid="uid-2"
tests/test_workflow_core.py:141:    for operation in (workflow.to_envelope, lambda: workflow.compile("api")):
tests/test_workflow_core.py:163:    before = workflow.copy()
tests/test_workflow_core.py:173:def test_envelope_decode_rejects_embedded_api_links_even_with_matching_edge() -> None:
tests/test_workflow_core.py:175:    workflow.nodes["1"] = VibeNode("1", "Source", uid="uid-1")
tests/test_workflow_core.py:176:    workflow.nodes["2"] = VibeNode("2", "Sink", uid="uid-2")
tests/test_workflow_core.py:178:    envelope = workflow.to_envelope()
tests/test_workflow_core.py:179:    envelope["nodes"]["2"]["inputs"]["image"] = ["1", 0]
tests/test_workflow_core.py:182:        from_envelope(envelope)
tests/test_workflow_core.py:228:            "GuideNode": NodeSchema(
tests/test_workflow_core.py:229:                class_type="GuideNode",
tests/test_workflow_core.py:248:            "1": {"class_type": "GuideNode", "inputs": {}},
tests/test_workflow_core.py:256:    source = workflow.node("GuideNode")
tests/test_workflow_core.py:264:        "2": {"class_type": "CFGGuider", "inputs": {"positive": {"pooled": []}, "cfg": 5.0}},
tests/test_workflow_core.py:446:def test_workflow_copy_deep_copies_mutable_state_and_preserves_original() -> None:
tests/test_workflow_core.py:454:        uid="uid-1",
tests/test_workflow_core.py:461:        uid="uid-2",
tests/test_workflow_core.py:490:        "nested": {"keep": True},
tests/test_workflow_core.py:495:    workflow._uid_counter = 7
tests/test_workflow_core.py:497:    cloned = workflow.copy()
tests/test_workflow_core.py:510:    assert cloned._uid_counter == 7
tests/test_workflow_core.py:521:    cloned.metadata["nested"]["keep"] = False
tests/test_workflow_core.py:524:    cloned._uid_counter = 100
tests/test_workflow_core.py:537:    assert workflow.metadata["nested"] == {"keep": True}
tests/test_workflow_core.py:540:    assert workflow._uid_counter == 7
tests/test_workflow_core.py:545:def test_copy_is_derived_and_preserves_mode_and_groups_deeply() -> None:
tests/test_workflow_core.py:546:    """P10: copy() is derived — mode/groups ride along without a hand-list edit,
tests/test_workflow_core.py:547:    and the copy is deep (mutating the clone never touches the original)."""
tests/test_workflow_core.py:550:        "1", "KSampler", inputs={"seed": 1}, uid="uid-1", mode=4
tests/test_workflow_core.py:553:        "2", "SaveImage", uid="uid-2", mode=0
tests/test_workflow_core.py:560:    cloned = workflow.copy()
tests/test_workflow_core.py:576:def test_geometry_copy_and_compile_are_deep_and_execution_invariant() -> None:
tests/test_workflow_core.py:581:        uid="uid-1",
tests/test_workflow_core.py:587:    cloned = workflow.copy()
tests/test_workflow_core.py:596:def test_geometry_envelope_new_fields_win_and_legacy_fallback_is_independent() -> None:
tests/test_workflow_core.py:597:    workflow = VibeWorkflow("geometry-envelope", WorkflowSource("geometry-envelope"))
tests/test_workflow_core.py:601:        uid="uid-1",
tests/test_workflow_core.py:606:    envelope = workflow.to_envelope()
tests/test_workflow_core.py:607:    assert envelope["nodes"]["1"]["pos"] == [10.0, 20.0]
tests/test_workflow_core.py:608:    assert envelope["nodes"]["1"]["size"] == [300.0, 180.0]
tests/test_workflow_core.py:610:    restored = from_envelope(envelope)
tests/test_workflow_core.py:614:    old_mixed = deepcopy(envelope)
tests/test_workflow_core.py:621:    restored_old = from_envelope(old_mixed)
tests/test_workflow_core.py:625:    explicit_absence = deepcopy(old_mixed)
tests/test_workflow_core.py:627:    assert from_envelope(explicit_absence).nodes["1"].pos is None
tests/test_workflow_core.py:641:def test_versioned_envelope_rejects_malformed_present_geometry(
tests/test_workflow_core.py:645:    workflow.nodes["1"] = VibeNode("1", "SaveImage", uid="uid-1")
tests/test_workflow_core.py:646:    envelope = workflow.to_envelope()
tests/test_workflow_core.py:647:    envelope["nodes"]["1"][field_name] = value
tests/test_workflow_core.py:650:        from_envelope(envelope)
tests/test_workflow_core.py:653:def test_validation_and_envelope_writer_reject_invalid_programmatic_geometry() -> None:
tests/test_workflow_core.py:656:        "1", "SaveImage", uid="uid-1", pos=[1.0], size=[2.0, 3.0]
tests/test_workflow_core.py:662:        workflow.to_envelope()
tests/test_workflow_core.py:665:def test_node_mode_and_groups_survive_envelope_round_trip() -> None:
tests/test_workflow_core.py:666:    """P10: node.mode and workflow.groups are serialized by to_envelope and
tests/test_workflow_core.py:667:    restored by from_envelope (dataclass walk — no hand-listed fields)."""
tests/test_workflow_core.py:668:    from vibecomfy.ingest.normalize import from_envelope
tests/test_workflow_core.py:672:        "1", "LoadImage", inputs={"image": "a.png"}, uid="uid-1", mode=4
tests/test_workflow_core.py:675:        "2", "PreviewImage", uid="uid-2", mode=2
tests/test_workflow_core.py:683:    envelope = wf.to_envelope()
tests/test_workflow_core.py:684:    assert envelope["groups"] == wf.groups
tests/test_workflow_core.py:685:    assert envelope["nodes"]["1"]["mode"] == 4
tests/test_workflow_core.py:686:    assert envelope["nodes"]["2"]["mode"] == 2
tests/test_workflow_core.py:688:    restored = from_envelope(envelope)
tests/test_workflow_core.py:695:    """P10 gate: the 90a1d5 envelope decodes 15 nodes with mode dist {4:9, 0:6};
tests/test_workflow_core.py:699:    from vibecomfy.ingest.normalize import from_envelope
tests/test_workflow_core.py:701:    envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
tests/test_workflow_core.py:702:    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
tests/test_workflow_core.py:703:    wf = from_envelope(envelope)
tests/test_workflow_core.py:1022:        def finalize(self) -> dict[str, dict[str, object]]:
tests/test_workflow_core.py:1307:        def finalize(self) -> dict[str, dict[str, object]]:
tests/test_workflow_core.py:1869:# ── T2: Monotonic uid counter tests ──────────────────────────────────────────
tests/test_workflow_core.py:1876:def test_uid_counter_is_independent_of_next_node_id() -> None:
tests/test_workflow_core.py:1877:    """_uid_counter increments monotonically; _next_node_id gap-fills int ids."""
tests/test_workflow_core.py:1879:    # node() mints uid via counter
tests/test_workflow_core.py:1881:    assert wf._uid_counter == 1
tests/test_workflow_core.py:1883:    assert wf._uid_counter == 2
tests/test_workflow_core.py:1884:    # Both have distinct uids
tests/test_workflow_core.py:1885:    assert b1.node.uid != b2.node.uid
tests/test_workflow_core.py:1891:def test_add_delete_add_reuses_int_id_but_fresh_uid() -> None:
tests/test_workflow_core.py:1892:    """add→delete→add reuses the lowest gap int id but mints a fresh non-colliding uid."""
tests/test_workflow_core.py:1895:    uid_first = b1.node.uid
tests/test_workflow_core.py:1902:    # But uid must be fresh and non-colliding
tests/test_workflow_core.py:1903:    assert b2.node.uid != uid_first, "uid must not be reused after delete→add"
tests/test_workflow_core.py:1906:def test_uid_survives_finalize_metadata() -> None:
tests/test_workflow_core.py:1907:    """VibeNode.uid is preserved through finalize_metadata (not rebuilt)."""
tests/test_workflow_core.py:1910:    uid_before = b.node.uid
tests/test_workflow_core.py:1911:    assert uid_before  # must have been minted
tests/test_workflow_core.py:1912:    wf.finalize_metadata()
tests/test_workflow_core.py:1913:    assert wf.nodes[b.node.id].uid == uid_before
tests/test_workflow_core.py:1916:def test_add_node_uid_kwarg_sets_verbatim() -> None:
tests/test_workflow_core.py:1917:    """add_node(uid=...) sets node.uid verbatim without minting."""
tests/test_workflow_core.py:1919:    counter_before = wf._uid_counter
tests/test_workflow_core.py:1920:    node = wf.add_node("Foo", uid="explicit-uid-value")
tests/test_workflow_core.py:1921:    assert node.uid == "explicit-uid-value"
tests/test_workflow_core.py:1923:    assert wf._uid_counter == counter_before
tests/test_workflow_core.py:1926:def test_node_with_explicit_id_seeds_uid_from_id() -> None:
tests/test_workflow_core.py:1927:    """node(_id=...) seeds the uid from the explicit id, not the counter value alone."""
tests/test_workflow_core.py:1931:    # uid should encode the explicit id as seed
tests/test_workflow_core.py:1932:    assert "42" in b.node.uid
tests/test_workflow_core.py:1935:def test_uid_counter_monotonic_never_resets() -> None:
tests/test_workflow_core.py:1936:    """_uid_counter never decreases; deletion does not reset it."""
tests/test_workflow_core.py:1943:    assert wf._uid_counter == 3  # monotonically incremented, not reset
tests/test_workflow_core.py:1950:        "uids": {nid: node.uid for nid, node in workflow.nodes.items()},
tests/test_workflow_core.py:1975:        "uids": {"1": "1", "2": "2", "3": "3"},
tests/test_workflow_core.py:2002:        "uids": {"1": "1", "2": "2"},
tests/test_workflow_core.py:2010:    """from_ui / from_api / from_envelope decode fixtures with stable invariants."""
tests/test_workflow_core.py:2015:    assert all(node.uid for node in from_ui_wf.nodes.values())
tests/test_workflow_core.py:2024:    envelope_path = Path("external_workflows/corpus/90a1d5ff9044902e.json")
tests/test_workflow_core.py:2025:    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
tests/test_workflow_core.py:2026:    via_named = from_envelope(envelope)
tests/test_workflow_core.py:2027:    via_class = VibeWorkflow.from_envelope(envelope)
tests/test_workflow_core.py:2037:    assert "from_envelope" in ingest.__all__

    The returned workflow eagerly binds the ``workflow_context`` ContextVar so
    that subsequent ``node(...)`` / typed-wrapper calls at module body can
    discover the active workflow without an enclosing ``with`` block.
    ``finalize()`` releases the binding.  The workflow also supports use as a
    context manager (``with new_workflow(...) as wf:``) for callers that prefer
    explicit scoping.
    """
    raw_workflow_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    workflow_id = _category_qualified_template_id(raw_workflow_id, source_path)
    metadata = dict(metadata)
    metadata["ready_template"] = workflow_id
    metadata["workflow_template"] = workflow_id.rsplit("/", 1)[-1]
    provenance = metadata.get("provenance")
    wf = ready_workflow(
        workflow_id,
        source_path=source_path or __file__,
        provenance=provenance if isinstance(provenance, Mapping) else None,
    )
    wf.metadata.update(metadata)

    # Eagerly bind the ContextVar so that node()/typed-wrapper calls in the
    # caller's body can find the active workflow.  finalize() releases this
    # binding.  Skipping if the workflow is already bound (e.g. caller is using
    # ``with new_workflow(...) as wf:``); the ``with`` form will then re-bind a
    # fresh token in __enter__.
    if getattr(wf, "_workflow_context_token", None) is None:
        from vibecomfy.workflow_context import active_workflow, bind_workflow

        # Defensive: if a *different* previous workflow leaked its binding
        # (e.g. its build() raised before finalize() could release the token),
        # clear it so a brand-new template can be built.  Only do this when the
        # leaked workflow itself has no token attribute — a sign that its owner
        # has been garbage-collected and can never run __exit__.  Genuine nested
        # ``with new_workflow(...) as wf:`` blocks where the outer workflow is
        # still held by the caller will fall through to bind_workflow() and
        # raise ``Nested workflow contexts not supported``, preserving Block A's
        # contract.
        existing = active_workflow()
        if existing is not None and existing is not wf:
            existing_token = getattr(existing, "_workflow_context_token", None)
            if existing_token is None:
                from vibecomfy.workflow_context import _CURRENT_WORKFLOW

                _CURRENT_WORKFLOW.set(None)

        wf._workflow_context_token = bind_workflow(wf)

    return wf


def node(
    *args: Any,
    _id: str | None = None,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a ready-template node.

    v2.6.4 Fix 5: ``wf`` is now optional — reads from the ContextVar set by
    ``new_workflow(...)`` when omitted. This matches the typed-wrapper
    convention, so ``raw_call('<uuid>', '<id>', ...)`` works inside a
    ``with new_workflow(...) as wf:`` block without passing ``wf`` explicitly.

    Backward compat: legacy ``node(wf, class_type, source_id, ...)`` and the
    v2.5 id-free ``node(wf, class_type, ...)`` forms still work — the first
    """Backward-compatible free-function shim for ``VibeWorkflow.finalize``."""
    return wf.finalize(inputs, metadata=metadata, output_node=output_node, output_kind=output_kind, **bind_kwargs)


def _finalize_impl(
    wf: VibeWorkflow,
    inputs: dict[str, InputSpec],
    metadata: dict[str, Any],
    *,
    output_node: Any = None,
    output_kind: str | None = None,
    **bind_kwargs: Any,
) -> VibeWorkflow:
    """Finalize ready-template metadata, public inputs, and output binding.

    When ``output_kind`` is omitted, it is inferred best-effort from the
    output node class type, then from ``output_type`` if present. If
    ``output_node`` is omitted, a single terminal Save/Create/Preview node is
    selected; multiple candidates require an explicit output binding.
    """
    # Release the eager ContextVar binding that ``new_workflow()`` set, BEFORE
    # any work that might raise — otherwise an exec_failed/validate path leaves
    # the binding stuck across the next template's build() and the regen tool
    # cascades into ``ContextVarBindingError``.  ``new_workflow()`` exists to
    # let module-body node() calls discover the active workflow; by the time we
    # reach finalize, that purpose is served.
    token = getattr(wf, "_workflow_context_token", None)
    if token is not None:
        try:
            from vibecomfy.workflow_context import reset_workflow

            reset_workflow(token)
        except Exception:
            pass
        wf._workflow_context_token = None

    source_path = bind_kwargs.pop("source_path", None)
    requirements = bind_kwargs.pop("requirements", None)
    if source_path is None:
        source_path = wf.source.path or str(Path.cwd())

    # Merge metadata['requirements'] custom_nodes into explicit requirements.
    meta_reqs = metadata.get("requirements")
    if isinstance(meta_reqs, dict) and (meta_reqs.get("custom_nodes") or meta_reqs.get("custom_node_refs")):
        meta_normalized, _warnings = normalize_custom_node_requirements(meta_reqs)
        meta_custom = list(meta_normalized["custom_nodes"])
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return False
    return first_line.strip() == "# vibecomfy: manual"


def _compile_ready_template(path: Path, template_id: str) -> dict[str, Any]:
    module = types.ModuleType(f"vibecomfy_canonical_parity_{template_id.replace('/', '_')}")
    module.__file__ = str(path)
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102 - trusted repo ready-template code.
    build = getattr(module, "build", None)
    if build is None:
        raise ValueError(f"Ready template {template_id} must define build()")
    workflow = build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"Ready template {template_id} build() must return VibeWorkflow, got {type(workflow).__name__}")
    return workflow.compile("api")


def _reset_leaked_workflow_context() -> None:
    """Keep one failed template from poisoning later template imports."""
    try:
        from vibecomfy.workflow_context import active_workflow, reset_workflow
    except Exception:
        return
    workflow = active_workflow()
    token = getattr(workflow, "_workflow_context_token", None) if workflow is not None else None
    if token is None:
        return
    try:
        reset_workflow(token)
    except Exception:
        return
    workflow._workflow_context_token = None


def _canonical_sha256(form: dict[str, Any]) -> str:
    rendered = json.dumps(form, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _print_report(report: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=False))
        return

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' pytest -q tests/test_workflow_context.py tests/test_templates_module.py -k 'workflow_context or finalize or nested or exception or async' tests/test_workflow_core.py -k 'copy or uid_counter or add_delete_add or add_node_uid or node_with_explicit_id or envelope'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 435ms:
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

codex
The focused pytest command cannot start in this read-only sandbox because Python cannot create any temporary file; that is an environment limitation, not a code failure. I’m switching to assertion-only Python probes that avoid temp/cache writes, alongside static inspection.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import asyncio
import dataclasses
import inspect
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode
from vibecomfy.workflow_context import active_workflow
from vibecomfy.templates import new_workflow
field = {f.name: f for f in dataclasses.fields(VibeWorkflow)}[\"_workflow_context_token\"]
assert field.init is False and field.repr is False and field.compare is False
assert \"_workflow_context_token\" not in inspect.signature(VibeWorkflow).parameters
base = VibeWorkflow(\"w\", WorkflowSource(\"w\"))
assert base._workflow_context_token is None
assert \"_workflow_context_token\" not in repr(base)
assert \"_workflow_context_token\" not in base.to_envelope()
equal = VibeWorkflow(\"w\", WorkflowSource(\"w\"))
equal._workflow_context_token = object()
assert base == equal
assert base.copy()._workflow_context_token is None
with base:
    assert active_workflow() is base
    assert base.copy()._workflow_context_token is None
    assert active_workflow() is base
assert active_workflow() is None and base._workflow_context_token is None
try:
    with base:
        raise RuntimeError(\"probe\")
except RuntimeError:
    pass
assert active_workflow() is None and base._workflow_context_token is None
outer = VibeWorkflow(\"outer\", WorkflowSource(\"outer\"))
inner = VibeWorkflow(\"inner\", WorkflowSource(\"inner\"))
with outer:
    try:
        with inner:
            raise AssertionError(\"nested unexpectedly succeeded\")
    except RuntimeError as exc:
        assert \"Nested workflow contexts\" in str(exc)
    assert active_workflow() is outer
assert active_workflow() is None
async def task(i):
    wf = VibeWorkflow(f\"w{i}\", WorkflowSource(f\"w{i}\"))
    with wf:
        await asyncio.sleep(0)
        assert active_workflow() is wf
        return wf.id
async def main():
    return await asyncio.gather(task(1), task(2))
assert asyncio.run(main()) == [\"w1\", \"w2\"]
wf = new_workflow({\"ready_template\": \"oracle/token-probe\"})
assert active_workflow() is wf and wf._workflow_context_token is not None
try:
    wf.finalize({}, metadata={\"ready_template\": \"oracle/token-probe\"})
except Exception:
    pass
assert active_workflow() is None and wf._workflow_context_token is None
seed = VibeWorkflow(\"uids\", WorkflowSource(\"uids\"))
for node_id, uid in [(\"1\",\"n1\"),(\"2\",\"n5\"),(\"3\",\"n100\"),(\"4\",\"42\"),(\"5\",\"id:abc\"),(\"6\",\"explicit-uid\"),(\"7\",\"n7\")]:
    seed.nodes[node_id] = VibeNode(node_id, \"Probe\", uid=uid)
decoded = VibeWorkflow.from_envelope(seed.to_envelope())
original = {k: v.uid for k,v in decoded.nodes.items()}
a = decoded.node(\"Probe\").node.uid
b = decoded.node(\"Probe\").node.uid
assert (a,b) == (\"n101\",\"n102\"), (a,b)
assert decoded._uid_counter == 102
assert {k: decoded.nodes[k].uid for k in original} == original
clone = decoded.copy()
assert clone._workflow_context_token is None and clone._uid_counter == 102
c = clone.node(\"Probe\").node.uid
d = decoded.node(\"Probe\").node.uid
assert c == \"n103\" and d == \"n103\", (c,d)
assert clone._uid_counter == decoded._uid_counter == 103
print(\"oracle probes: PASS\")
'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 496ms:
oracle probes: PASS

exec
/bin/zsh -lc "rg -n \"n100|bound.*cop|copy.*bound|_workflow_context_token.*None|collision|sparse|imported.*uid|uid.*imported\" tests vibecomfy --glob '*.py'; git grep -n \"getattr(.*_workflow_context_token\\|hasattr(.*_workflow_context_token\\|del .*_workflow_context_token\" 06d94e4a -- vibecomfy tools tests" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 486ms:
06d94e4a:tools/check_canonical_parity.py:217:    token = getattr(workflow, "_workflow_context_token", None) if workflow is not None else None
06d94e4a:vibecomfy/templates.py:106:    if getattr(wf, "_workflow_context_token", None) is None:
06d94e4a:vibecomfy/templates.py:120:            existing_token = getattr(existing, "_workflow_context_token", None)
06d94e4a:vibecomfy/templates.py:561:    token = getattr(wf, "_workflow_context_token", None)

codex
FAIL

- [vibecomfy/templates.py:106](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/templates.py:106), [vibecomfy/templates.py:120](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/templates.py:120), and [vibecomfy/templates.py:561](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/templates.py:561) still use token-related `getattr(...)`. This violates frozen task 2, which requires direct access now that the field is declared. The Batch K plan explicitly included `vibecomfy/templates.py`.
- [tools/check_canonical_parity.py:217](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tools/check_canonical_parity.py:217) also retains token-related `getattr(...)`.

Everything else reviewed passes: field surface omissions, bound/unbound copying, lifecycle behavior, async isolation, exception cleanup, sparse `n1/n5/n100 → n101`, imported-UID preservation, copy monotonicity, and the production diff’s whitespace check. No edits made.
tokens used
86,729
FAIL

- [vibecomfy/templates.py:106](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/templates.py:106), [vibecomfy/templates.py:120](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/templates.py:120), and [vibecomfy/templates.py:561](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/templates.py:561) still use token-related `getattr(...)`. This violates frozen task 2, which requires direct access now that the field is declared. The Batch K plan explicitly included `vibecomfy/templates.py`.
- [tools/check_canonical_parity.py:217](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tools/check_canonical_parity.py:217) also retains token-related `getattr(...)`.

Everything else reviewed passes: field surface omissions, bound/unbound copying, lifecycle behavior, async isolation, exception cleanup, sparse `n1/n5/n100 → n101`, imported-UID preservation, copy monotonicity, and the production diff’s whitespace check. No edits made.
