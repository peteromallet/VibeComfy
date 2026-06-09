# Loose-work consolidation plan (2026-06-09)

Goal: land every piece of useful loose work onto **one** branch
(`consolidate/loose-work-20260609`, branched from `origin/main` @ `1cea104`),
then retire everything that is merged/dead. Driven by a read-only DeepSeek
fan-out (6 agents) whose verdicts were Claude-sense-checked against direct git.

## Protected — never touched
- Repo-root checkout (`reigh-workspace/vibecomfy`, branch `agent-edit-combo-enum-fix`): user's in-progress object_info fail-closed work (14 dirty files).
- `agent-edit-chat-platform` / `epic/agent-edit-chat/m4-chat-ui`: LIVE run (9 procs). It is actively rewriting `vibecomfy_roundtrip.js` (7,104 lines on m4 vs 10,276 on main) and `panel_*.js`.
- `local-library-config`: in-flight sprint.
- `/private/tmp/vc-exec-main`: exec-node test server (:8201).

## KEEP-AND-LAND (onto the consolidation branch)
| # | Source | What | Stakes | Merge notes |
|---|--------|------|--------|-------------|
| L1 | `e752578` (node-resolution wt) | known_failures.txt allowlist for talking_avatar + `docs/structural_issues.md` root-cause note | low | cherry-pick; may touch known_failures.txt also touched by cleanup |
| L2 | `epic/node-resolution/m1-acceptance-completion` `916409d` | un-skip 5 sprint_a acceptance scenarios + `compute_schema_hash` identity test (test-only, +113/−10) | med | 3-way merge of `test_node_resolution_acceptance.py` vs m3's sprint_c additions; MUST verify un-skipped tests pass on main |
| L3 | `codebase-cleanup-20260609` (vibecomfy-cleanup wt) | whole 10-wave cleanup, net −5,886 lines (dead code, shims, dedup, port.py god-file split, runtime spawn unification) + 3 planning docs | HIGH | merge whole; overlaps m3 in `porting/object_info/consume.py`,`convert.py`,`emitter.py` — verify with real trial merge + full suite |
| L4 | `sisypy-suite` wt | `3b967fb` doctor/i2v fix + uncommitted agentic harness (`agentic/` ~6,700 lines net-new, `origin.py`, `test_agentic_*`, chain-id/origin-stamp integration) | med-high | DROP `evidence/` (generated) + untracked `recipes/*` (100% already on main); reconcile session.py/video.py (91 commits behind) |

## LEAVE ALONE (live-run territory or rare-incomplete exception)
- agent-edit-chat m3 fix `7a16c41` (vibecomfy_roundtrip.js rehydration): NOT on main, NOT on live m4 — but the file is being wholesale-rewritten by the live run. Landing it would collide. **Live run's territory; leave.**
- `vibecomfy-exec-node` worktree dirty JS (`panel_composer.js`, `panel_thread.js`, `vibecomfy_roundtrip.js` +603/−534 vs main, `astrid_logo.png`): unique uncommitted UI work, but same files the live run owns and likely superseded. **Preserve to `checkpoint/exec-node-panel-wip` (no land), then it's safe to remove the worktree.** Drop the PNG.
- `symbolic-public-inputs` `9f68adc`: 79-file WIP snapshot, "WIP: preserve". Rare KEEP-IF-INCOMPLETE — leave the branch as-is, do not land or delete.

## DELETE (merged / squash-residue / cherry+0 — verified)
Worktree branches (cherry+0 or squash-merged): `agent-edit-native`, `agent-edit-preview-fidelity`, `agent-edit-turn-progress`, `diff-preview`, `feat/agent-edit-batch-default`, `feat/vibecomfy-debug-cli`, `agent-edit-statematch-verified`, `fix/primitivefloat-resolver`, `integration/agent-edit-overhaul`, `feat/agent-edit-lean-catalog`, `agent-edit-delta-lint` (#64), `vibecomfy-exec-node` (#65, after JS preserved), `epic/agent-edit-hardening/m3-module-split` (#62), `epic/agent-edit-structural/m2-render-architecture` (#59), and the two source branches after L3/L4 land: `codebase-cleanup-20260609`, `sisypy-suite`, plus `epic/node-resolution/m3-faithful-pinning` (#70 merged) and `epic/node-resolution/m1-acceptance-completion` (after L2 lands).

Local-only branches (merged/superseded): `node-resolution-epic`, `vibecomfy-exec-boot-hotfix` (#66), `epic/node-resolution/spec`, `epic/node-resolution/m1-correctness-spine`, `archive/agent-edit-message-synth-wip`, `epic/agent-edit-chat/m0-prelaunch-cleanup`, `epic/agent-edit-chat/m1-edit-state-authority`, `epic/agent-edit-chat/m2-typed-contracts`, `epic/agent-edit-chat/m3-conversation-slice` (after confirming its only unique content is the live-run-owned `7a16c41`), `agent-edit-hardening`, `agent-edit-structural`, `epic/agent-edit-hardening/m1-typed-response-contract`, `epic/agent-edit-hardening/m2-scoped-apply`, `epic/agent-edit-structural/m1-client-lifecycle-contract`.

Stashes: `stash@{0}` (agentic-port WIP) and `stash@{1}` (desloppify WIP) — both DROP (stale, base branches gone, superseded). Per separate confirmation before dropping.

## Execution order (preserve → integrate → test → delete)
1. L1 cherry-pick (trivial).
2. L2 acceptance gate — 3-way merge test file, run `pytest -m sprint_a` + node_resolution tests.
3. L3 cleanup whole-merge — resolve consume.py/convert.py overlap, run full fast-suite vs known_failures baseline.
4. L4 sisypy — fix commit + harness commit (drop evidence/recipes), reconcile session.py/video.py, run agentic + ops tests.
5. Full `pytest` gate: no NEW failures vs the `tests/known_failures.txt` baseline.
6. Push, open PR → main, CI green (test job), merge.
7. Preserve exec-node JS to checkpoint; remove all merged/dead worktrees; delete merged/dead branches (local+remote); drop stashes.
8. Re-verify: `git worktree list`, `git branch`, clean.

## Notes / contradictions surfaced
- `vibecomfy_roundtrip.js` is a 3-way contention hotspot (main / live-m4 / exec-node-dirty); resolved by leaving all roundtrip.js work to the live run.
- Cleanup (L3) heavily edits `consume.py`, which the user's repo-root dirty work ALSO edits; the user will reconcile their uncommitted work against the landed cleanup.
- DeepSeek for mechanical steps; Claude for the L3 m3-overlap conflict resolution and the L4 session.py/video.py reconciliation.
