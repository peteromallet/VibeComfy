# Loose Work Consolidation Plan - 2026-06-12

## Rationale

This plan exists because the loose-work survey found a stacked branch family, a dirty current checkout, and a dirty pinned worktree. A branch deletion table is not enough here: valuable work must be preserved, integrated in dependency order, tested, and only then should residue branches or worktrees be removed.

The target end-state is that every useful payload lands on `main` through a recoverable branch/PR, and everything deleted has positive evidence that it is redundant or already consumed.

## Current Ground Truth

- Default remote head: `origin/main`.
- Current checkout: `agent-edit-combo-enum-fix` at `edaa45d`, ahead of `origin/agent-edit-combo-enum-fix` by one commit, with dirty tracked edits and untracked docs.
- Local `main`: `d4c80b5`, behind `origin/main` (`3ed13eb`) by one merged fix commit.
- Same-origin worktrees:
  - `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` -> `agent-edit-combo-enum-fix`, dirty.
  - `/Users/peteromalley/Documents/.megaplan-worktrees/code-node-dynamic-io` -> `code-node-dynamic-io`, clean tracked, duplicated untracked docs.
  - `/Users/peteromalley/Documents/.megaplan-worktrees/agent-panel-welcome` -> `agent-panel-welcome`, dirty tracked and untracked.
  - `/Users/peteromalley/Documents/.megaplan-worktrees/structural-decomp` -> `main`, behind `origin/main`.
- Stashes: none.
- Open PRs: none.
- Codespaces: none returned.
- Cloud workspace: config exists, but provider reports app not running; do not deploy just to inspect.

## Branch Landscape

All three active feature branches share the same old base (`7cfeb71`) relative to `origin/main`. They are not merge-ready by ancestry because `origin/main` has moved through reorg milestones, but their unique patches are clear.

| Branch | Tip | Relationship | Unique payload |
|---|---:|---|---|
| `agent-edit-combo-enum-fix` | `edaa45d` | old-base branch; mostly superseded by `origin/main` reorg | its named behaviors are already present on `origin/main` under `vibecomfy/comfy_nodes/agent/*`; keep only as provenance until final cleanup |
| `code-node-dynamic-io` | `719bcdb` | stacked on `agent-edit-combo-enum-fix`, but top layer can land directly on `origin/main` | 4 additional code-node commits: dynamic IO, predicate fix, badge placement, execution-safety modes |
| `agent-panel-welcome` | `ce182e8` | old-base branch; committed UI layer superseded by newer overlay already on `origin/main` | dirty worktree needs dedup check; committed `ce182e8` should not be applied as-is |
| `structural-decomp` | `edaa45d` | duplicate pointer to `agent-edit-combo-enum-fix` | none |
| `epic/reorg/m0-tier1-low` | `cc66105` | PR #80 residue | consumed by merge commit `a2677c3` tree |
| `fix/m2-merge-regressions` | `141872e` | PR #83 residue | no diff vs `origin/main`; upstream already gone |
| `checkpoint/preserved-wip-20260609` | `33ca252` | preservation archive | archived exec-node panel WIP and prior cleanup planning docs |

## Everything Valuable -> Where It Lands

| Work | Current state | Lands as |
|---|---|---|
| Agent edit combo enum/output slot signatures | behavior present on `origin/main` after reorg | no landing needed unless final diff finds a missing test-only assertion |
| Agent edit issue-report zip and surfaced reasoning | behavior present on `origin/main`; old cherry-pick becomes empty after resolving stale JS/import paths | no landing needed |
| Object-info fail-closed and runtime-unavailable classification | behavior present on `origin/main`: `UnknownNodeSchemaError`, `require_class_output_count`, `AGENT_RUNTIME_UNAVAILABLE`, `agent/runtime.py`, `agent/worker.py` | no whole-commit landing; only preserve branch until cleanup approval |
| Current checkout dirty agent backend/runtime edits | old flat-path uncommitted work | likely superseded by `origin/main` `agent/` modules; do not apply raw |
| Code-node dynamic IO and safety modes | committed on `code-node-dynamic-io` | land the 4 top commits on `origin/main`, with mechanical path/test fixes |
| Agent panel welcome overlay | committed on `agent-panel-welcome` | skip as superseded by newer panel-scoped overlay already present on `origin/main` |
| Agent panel dirty provider/runtime/worker/JS work | uncommitted in `agent-panel-welcome` worktree | likely superseded/duplicated; only port if final diff proves unique behavior remains |
| Node-resolution docs/evidence bundle | untracked in multiple worktrees | land once if intended as repo evidence; otherwise archive once and remove duplicates |
| Research docs | untracked in current checkout and selected worktrees | land once if still useful; otherwise archive/remove duplicates after approval |

## Everything Else -> Delete

| Work | Delete route | Positive evidence |
|---|---|---|
| `structural-decomp` local branch | delete local branch after active work is preserved | points to exactly `edaa45d`, same as `agent-edit-combo-enum-fix`; no upstream; no unique commit |
| `fix/m2-merge-regressions` local branch | delete local branch | `git diff --stat origin/main fix/m2-merge-regressions` is empty; remote is already gone |
| `epic/reorg/m0-tier1-low` local and remote branches | delete local and `origin/epic/reorg/m0-tier1-low` | `git diff --stat a2677c3 epic/reorg/m0-tier1-low` is empty; PR #80 merge consumed branch tree |
| `agent-edit-combo-enum-fix` local/remote branches | delete after code-node layer and docs decisions are preserved | DeepSeek and throwaway integration show the meaningful payload is already in `origin/main` under the reorged module layout |
| `agent-panel-welcome` local branch/worktree | remove after confirming dirty payload is represented or intentionally discarded | committed overlay is superseded; dirty shared backend files duplicate current checkout; only `.auto-drive.log` and maybe old JS diff remain as provenance |
| duplicate untracked docs in secondary worktrees | remove only after one source is landed or archived | path sets duplicate the current checkout/code-node worktree payload except `.auto-drive.log` |
| `.auto-drive.log` in `agent-panel-welcome` | delete or archive as provenance | log artifact, not source; only after user approval |

## Strategy

1. Do not whole-branch merge any old-base branch. The reorg moved flat `vibecomfy/comfy_nodes/*.py` modules into `vibecomfy/comfy_nodes/agent/*.py`, so whole merges and raw dirty patches resurrect obsolete paths.
2. Land `code-node-dynamic-io` top-layer commits only (`b6aa3a0`, `e2a188e`, `0934856`, `719bcdb`) onto `origin/main`.
3. Apply required mechanical fixes while landing code-node:
   - In `vibecomfy/comfy_nodes/__init__.py`, preserve dynamic-IO logic but import runtime helpers from `vibecomfy.comfy_nodes.agent.runtime_code`.
   - In `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`, keep both provider-persistence helpers and default execution-mode helpers.
   - In code-node tests, update legacy imports from `vibecomfy.comfy_nodes.runtime_code` / `agent_provider` / `agent_edit` to the current `vibecomfy.comfy_nodes.agent.*` paths.
   - Update the prompt assertion from "Use `vibecomfy.code` only for inspectable typed logic" to the new execution-mode wording.
4. Skip `agent-panel-welcome` committed overlay (`ce182e8`) as superseded. The current code already has the stronger panel-scoped overlay, logo, single-select cards, key field, countdown, and Change Engine path.
5. Treat current checkout dirty edits and `agent-panel-welcome` dirty edits as old-layout residue until a final semantic diff proves otherwise.
6. Run focused tests:
   - `pytest tests/test_comfy_nodes_agent_backend_spine.py`
   - `pytest tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_edit.py`
   - `pytest tests/test_comfy_nodes.py tests/test_runtime_code_modes.py tests/test_contracts_reexport.py` for code-node layer
7. Do not delete or remove worktrees until the code-node landing branch is pushed and the docs/provenance decision is approved.

## Known Risk And Current Hypotheses

| Risk | Current hypothesis | Verification |
|---|---|---|
| Whole-branch merge conflicts | resolved: do not whole-branch merge old-base branches | DeepSeek found modify/delete conflicts on reorged files; throwaway cherry-picks confirmed path drift |
| Current checkout dirty edits overlap `agent-panel-welcome` dirty edits | resolved: 4 of 5 dirty files are duplicated between current checkout and panel worktree; do not apply twice | DeepSeek diffed shared dirty files; raw patch check failed against current layout |
| `agent-panel-welcome` tests mismatch implementation | obsolete under current `origin/main` layout; current runtime already uses `codex_auth_present`/CLI checks | focused agent suite has no new regressions after code-node layer |
| Untracked docs intent | unknown: looks like real node-resolution evidence, not build junk | inspect and decide land-vs-archive |
| `checkpoint/preserved-wip-20260609` relevance | likely should remain until this stack lands | revisit after consolidation branch is pushed |

## Throwaway Integration Results

Test worktree: `/tmp/vibecomfy-consolidation-test-20260612`, created from `origin/main`.

Findings:

- `agent-edit` commit `11db3a8` became empty after resolving stale import/JS conflicts, because the issue-report/reasoning payload is already present on `origin/main`.
- `agent-edit` commit `edaa45d` should not be cherry-picked whole: it conflicts with deleted old flat paths, but its actual behaviors are already present on `origin/main` in `vibecomfy/comfy_nodes/agent/*` and `vibecomfy/porting/object_info/*`.
- Code-node top commits are viable on `origin/main` with mechanical module-layout fixes.
- `agent-panel-welcome` commit `ce182e8` should be skipped as superseded by the newer overlay already on `origin/main`.
- Dirty panel/current backend patches do not apply raw and should not be treated as new landing work without a final semantic diff.

Verification:

- `pytest tests/test_comfy_nodes.py tests/test_runtime_code_modes.py tests/test_contracts_reexport.py`: `42 passed`.
- `pytest tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_contracts.py tests/test_comfy_nodes_agent_edit.py`: no new regressions; `424 passed`, one `known_failures.txt` baseline failure in `test_agent_edit_submit_after_accept_still_blocks_real_structural_divergence`.

## Final PR Outcome

Landing branch: `land/code-node-dynamic-io-20260612`.

PR: https://github.com/peteromallet/VibeComfy/pull/84

Final head: `7960738`.

Additional merge-blocker repairs made on the landing branch:

- Restored canonical parity for generated video templates by updating stale `ComfyMathExpression` unpacking, adding a curated `LTXVAddGuideMulti` output fallback, and making the parity checker reset leaked workflow context after a skipped template.
- Added missing snapshot stem mappings for `empty_image_red` and `empty_image_red_smoke_required`.

Final local verification:

- `uv run --frozen python -m tools.check_canonical_parity --all`: `canonical parity passed: 64 templates`.
- `uv run --frozen pytest tests/test_v26_canonical_parity.py tests/test_comfy_nodes.py tests/test_runtime_code_modes.py tests/test_contracts_reexport.py`: `47 passed`.
- `uv run --frozen python scripts/regenerate_snapshots.py --check`: all snapshot stems unchanged.
- CI fast-suite file list without local coverage plugin: one known `known_failures.txt` baseline failure, no new regressions.

Final GitHub checks on `7960738`:

- `ci / test`: success.
- `canonical-parity`: success.
- `Strict-ready gates`: success.

No cleanup deletions have been performed yet; residue branch/worktree deletion still requires explicit approval.

## DeepSeek / Subagent Provenance

Initial read-only Codex subagent outputs:

- `/tmp/vibecomfy-loose-branches-20260612-124908/results/01-agent-code-stack.txt`
- `/tmp/vibecomfy-loose-branches-20260612-124908/results/02-panel-welcome-dirty-worktree.txt`
- `/tmp/vibecomfy-loose-branches-20260612-124908/results/03-reorg-merged-residue.txt`

DeepSeek cross-check:

- `/tmp/vibecomfy-loose-branches-20260612-124908/results/04-deepseek-strategy-crosscheck.txt`

DeepSeek corrected the first draft in two important ways:

- Do not merge old-base branches wholesale; the reorg moved flat files into `agent/` modules.
- Do not apply both current dirty edits and agent-panel dirty edits; four shared files are duplicated, and only the panel JS/log/provenance needs separate consideration.

## Execution Order

1. Create a real landing branch from `origin/main`, e.g. `land/code-node-dynamic-io-20260612`.
2. Cherry-pick only code-node top commits: `b6aa3a0 e2a188e 0934856 719bcdb`.
3. Apply the same mechanical fixes proven in the throwaway branch.
4. Run the code-node focused tests and agent focused tests above.
5. Push/open PR.
6. After PR/landing approval, delete residue branches/worktrees in low-blast-radius order:
   - `fix/m2-merge-regressions`
   - `epic/reorg/m0-tier1-low` local and remote
   - `structural-decomp`
   - `agent-edit-combo-enum-fix`
   - `agent-panel-welcome` worktree/branch after docs/log decision
   - `code-node-dynamic-io` worktree/branch after PR merge

## Confidence

High confidence:

- `structural-decomp`, `fix/m2-merge-regressions`, and `epic/reorg/m0-tier1-low` are cleanup candidates.
- `agent-edit-combo-enum-fix` is not a landing branch anymore; it is old-base provenance whose behavior is already on `origin/main`.
- `code-node-dynamic-io` top commits are the real landing work and are viable on `origin/main`.
- `agent-panel-welcome` committed overlay is superseded by `origin/main`; dirty payload is mostly duplicate/old-layout residue.

Not yet fully proven:

- Whether the node-resolution docs should be committed as repo evidence or archived outside the main tree.
- Whether `.auto-drive.log` should be archived as provenance before removing `agent-panel-welcome`.
