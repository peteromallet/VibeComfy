# EXECUTION GOAL — run the VibeComfy cleanup T-001…T-069 end-to-end

Status: ready to launch. This is the operator goal for a coordinating agent. It specifies WHO does WHAT, WHEN, and HOW, using two agent tiers: **DeepSeek Flash workers** (actual implementation, in subagents) and **Codex GPT-5.6-Sol oracles** (high-reasoning sense-checkers). The coordinating agent does NOT implement — it dispatches, sequences, gates, and logs.

## Mission

Execute the full task list in `docs/megaplan_chains/technical_debt_cleanup/EXECUTION.md` (T-001…T-069, ORACLE-1…10) on a cleanup branch until the Definition of Done holds:

- All T-001…T-069 and ORACLE-1…10 report `PASS`.
- `make check` and full pytest exit 0 (only the T-001-recorded quarantined baseline tolerated).
- Both package formats (wheel + sdist) exclude `web_dist`; deletion negative-proofs pass; generated node shims and the three golden fixtures are intact; edit/session/runtime/frontend surfaces match the pinned manifests.
- The execution log and `desloppify status` show every scoped category closed.

## Source of truth

- Task list, lanes, oracles, worker protocol, DoD: `docs/megaplan_chains/technical_debt_cleanup/EXECUTION.md`.
- Ground-truth resolutions (why tasks are shaped this way): `docs/megaplan_chains/technical_debt_cleanup/resolutions-digest.md`.
- 28-area investigation: `docs/megaplan_chains/technical_debt_cleanup/area-digest.md`.
- Baseline manifests are created by T-001…T-006 and frozen thereafter.

## Agent topology

| Role | Agent | Model | Does |
|---|---|---|---|
| **Orchestrator** | the coordinating agent (this session) | deepseek-v4-flash | owns the queue, dependency/lane sequencing, dispatch, oracle invocation, execution log, escalation. Never edits code itself. |
| **Workers** | subagents via the task tool (`agent: task`) | DeepSeek Flash | implement exactly ONE task (or a tightly coupled pair) per dispatch, per the worker protocol. |
| **Oracles** | Codex subagents (`codex exec --sandbox read-only -m gpt-5.6-sol`) | GPT-5.6-Sol, max reasoning (config default) | after each batch, verify against the frozen manifests/owners, run the ORACLE-n commands, emit `PASS\|FAIL\|BLOCKED` with evidence. Also used for adversarial review of any risky diff before landing. |

## Execution loop (per oracle batch)

1. **Gate**: do not start batch N until ORACLE-(N-1) is `PASS` (ORACLE-0 = the T-001 baseline).
2. **Dispatch**: fan out the batch's tasks to DeepSeek Flash workers. Within a batch:
   - tasks with different lanes run **in parallel** (one worker per task);
   - `SPINE` tasks run **serially** (one worker owns the spine; no two spine tasks concurrently);
   - a task runs only after its dependencies (`d:`) are `PASS`.
   - Cap the fan-out at 32 concurrent workers.
3. **Collect**: each worker returns `T-NNN PASS|FAIL|BLOCKED — changed: <files>; verify: <cmd>; result: <exit + output>; acceptance: <met/failed>`.
4. **Review risky diffs**: before ORACLE, have a Codex-sol read-only review of the batch's diff if it touches the exec-assembler, session.py, runtime spawn, deep_plain, or the frontend carve (T-035…T-062). Fix findings by re-dispatch before the oracle.
5. **Oracle**: run the ORACLE-N briefing as a Codex subagent (gpt-5.6-sol, read-only) with the exact commands from EXECUTION.md (plus the frozen manifests and the batch's changed-file scope). Oracle returns one line per checkpoint: `PASS|FAIL|BLOCKED — observed: <cmd/output>; scope: <files>`.
6. **Record**: append task results + oracle verdict to `docs/megaplan_chains/technical_debt_cleanup/execution-log.md`; update `.desloppify/` debt state (per T-068).
7. **Commit**: one commit per logical task/pair on the cleanup branch (never main). Commit message: `cleanup(T-NNN): <title>`.

## Worker dispatch brief (given to every DeepSeek Flash worker)

```
You are executing cleanup task T-NNN from docs/megaplan_chains/technical_debt_cleanup/EXECUTION.md.
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch: cleanup/technical-debt).
Read the task line. It specifies: files (F:), the change, the verification command (V:), risk/size, dependencies, lane, oracle.
Protocol (strict):
1. Read every file in F: before editing. If the task requires a file not listed, STOP and report BLOCKED — do not improvise.
2. Edit ONLY the files in F:. No scope cleanup, no lint/format sweeps, no broad gate runs, no generated-file hand-edits, no dependency changes.
3. Run exactly V: (use .venv/bin/python for pytest, node --test for browser tests, make for make targets).
4. Run git diff --check. Keep the change minimal and coherent.
5. Do NOT modify frozen manifests (tests/fixtures/agent_edit/cleanup_surface_manifest.json etc.) to make a refactor pass. If a task's change legitimately alters a pinned surface, report BLOCKED with the exact delta for orchestrator/plan-owner approval.
6. Do NOT add quarantine entries, skips, waivers, or dependency loosening.
7. Report exactly: "T-NNN PASS|FAIL|BLOCKED — changed: <files>; verify: <exact command>; result: <exit code + concise output>; acceptance: <met or failed reason>".
On FAIL: preserve evidence and stop; do not repair adjacent code. The orchestrator re-dispatches or escalates.
```

## Oracle dispatch brief (given to every Codex-sol subagent)

```
You are the oracle for cleanup checkpoint ORACLE-N (docs/megaplan_chains/technical_debt_cleanup/EXECUTION.md).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (cleanup/technical-debt branch).
Read-only. Your briefing: the batch's task ids + the frozen contracts that must survive (from tests/fixtures/agent_edit/cleanup_surface_manifest.json, /tmp/cleanup-ownership.md, and the resolutions in docs/megaplan_chains/technical_debt_cleanup/resolutions-digest.md) + the batch's changed-file scope.
Verify, with the EXACT commands listed for ORACLE-N in EXECUTION.md:
- behavioral equivalence (targeted pytest/node per the batch);
- no second canonical implementation introduced (the owner ledger's canonical owners must remain unique);
- public/private symbol surfaces preserved (edit 472-name set, session 23/31/23 lists, monkeypatch seams);
- generated files regenerated whole, never hand-edited; goldens unchanged;
- import/CLI/reflection/exec compatibility; guarded NODE_CLASS_MAPPINGS imports still lazy;
- changed-file scope matches the tasks (nothing outside);
- make check (+ full pytest at the batch boundary) exit 0 with only quarantined-baseline tolerated.
Emit exactly one line: "PASS|FAIL|BLOCKED — observed: <command/result>; scope: <files>". On FAIL, list the specific violations with file:line evidence. Be adversarial; try to break the batch's claims.
```

## Sequencing rules

- **Parallel lanes**: L1–L13 tasks in the same batch run concurrently (e.g., ORACLE-3 batch: L4 make/package tasks ∥ L5 demo CLI ∥ L6 route tests; ORACLE-5 batch: L8 clone migration ∥ L9 codegen).
- **SPINE**: one worker at a time; SPINE never runs in parallel with another SPINE task. SPINE tasks (T-035…T-055, T-057…T-065) are the exec-split → session-extraction → runtime → frontend-carve order; their internal dependencies are explicit in `d:`.
- **Resource note**: T-016 (declare pytest-xdist) must land before any `full-pytest`/`-n 8` gate is treated as canonical; until then full-pytest runs are ad-hoc.
- **Branch discipline**: all work on `cleanup/technical-debt`; merge to main only at the end (after T-069 + ORACLE-10), via the normal review path.

## Escalation rules

- Worker `FAIL` → re-dispatch once with the failure evidence; if it fails again, escalate to a Codex-sol adversarial review of the task, then re-dispatch with its fix, or mark BLOCKED and stop that lane.
- Worker `BLOCKED` (unexpected file / frozen-surface change / missing prerequisite) → orchestrator investigates; if it's a legitimate surface change, stop and ask the plan owner (user) for approval; otherwise unblock and re-dispatch.
- Oracle `FAIL` → return the batch to the workers with the oracle's violation list; repeat until oracle `PASS` (max 3 rounds, then stop and report to the plan owner).
- Oracle `BLOCKED` → same as worker BLOCKED.
- Any deviation from the weak-worker protocol (scope creep, waivers, quarantine additions, generated-file hand-edits) is an immediate stop-and-report.

## Definition of done (for this goal)

- `cleanup/technical-debt` merged to `main`; every task and oracle verdict recorded in `execution-log.md` as `PASS`.
- `make check`, full pytest, `node --test tests/browser/*.mjs`, `make docs`, `desloppify scan/status` all green per ORACLE-10.
- Debt-map categories (deletion, duplication, staleness, coupling, CLI, packaging) closed; no hidden waivers.
- Final report: per-batch oracle log + changed-file inventory + before/after gate evidence.
