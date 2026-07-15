# Loose-work consolidation — 2026-07-15

## Rationale

This plan closes the VibeComfy loose-work survey after confirming that the
Agent Edit Verifiable Transaction Spine is already delivered on `main` through
merged PRs #141, #142, and #143. The cloud checkout is clean at the same
`origin/main` tip. No topic branch or cloud workspace contains undelivered code.

## Valuable work and landing destination

| Work | Evidence | Destination |
| --- | --- | --- |
| Agent Edit Verifiable Transaction Spine | PRs #141–#143 merged; cloud checkout clean at `c54c530d` | Already on `main` |
| Per-workflow window chat recovery | Cloud archive showed eight dirty files; recovery commit `920c6e0d` changes the identical path set | Already on `main` |
| Stash recovery payload | Commit `d333c30c` recovered useful pieces; later transaction-spine work supersedes the remainder | Already on `main` |

## Proven cleanup candidates

| Item | Decision | Positive evidence |
| --- | --- | --- |
| `cleanup/lifecycle-clear` | Delete local branch | Ancestor of `origin/main`; zero unique commits |
| `cleanup/overlay-owner` | Delete local branch | Same tip and evidence |
| `cleanup/ownership-tests` | Delete local branch | Same tip and evidence |
| `cleanup/thread-owner-audit` | Delete local branch | Same tip and evidence |
| `fix/agent-edit-randomize-sampler-control` | Delete local branch | Ancestor of `origin/main`; zero unique commits |
| Remote corrective-1 branch | Delete remote branch | PR #140 squash-merged; patch delivered |
| Remote corrective-2 branch | Delete remote branch | Tip is an ancestor of `origin/main` |
| `stash@{0}` | Drop | Recovery commit and subsequent mainline supersession verified feature-by-feature |
| `tests/e2e/specs/tmp_text_overlay_inspect.spec.mjs` | Delete | Assertion-free temporary diagnostic |
| Stale `.git/REBASE_HEAD` | Delete | No rebase directory or active operation; reflog records completed rebase |
| Four prunable `/private/tmp` worktrees | Prune metadata | Worktree directories no longer exist |
| Completed Hetzner transaction-spine checkout | Remove checkout directory only | Clean, synchronized, chain reports all milestones complete; shared box/volume remains intact |

## Execution order

1. Fast-forward local `main` to `origin/main`.
2. Run focused transaction-spine/browser/backend tests and the practical repository gate.
3. Commit this consolidation record to `main` and push it.
4. Prune dead worktree metadata.
5. Delete the five proven local branches using safe deletion.
6. Delete the two proven residual GitHub branches.
7. Drop the superseded stash and remove the temporary diagnostic and stale rebase metadata.
8. Remove only the clean, completed VibeComfy transaction-spine checkout from the shared Hetzner volume.
9. Re-fetch and re-survey local refs, remote refs, worktrees, stashes, working tree, and the cloud path.

## Verification result

- Browser/agent-edit focused suite: **384 passed, 0 failed**.
- Focused Python transaction-spine suite: **442 passed, 24 failed**. All 24
  failures are confined to `tests/test_comfy_nodes_agent_backend_spine.py` on
  the already-merged `main` tip. The observed clusters are gate derivation
  without a plan, V2 accept calls returning `EditorAheadConflict`, and changed
  rollback-after-finalize idempotency. These are recorded as a delivery
  candidate; no cleanup operation modifies the implementation under test.

## Boundaries

- Do not destroy or stop the shared Hetzner box or volume; active Arnold work uses it.
- Do not touch Codespaces because the current GitHub token lacks the required scope.
- Other-repository work in reigh-app/reigh-workspace is outside this cleanup.

## Provenance

The survey used direct Git/GitHub/cloud evidence plus independent read-only
reviews under `/tmp/vibecomfy-loose-survey-results`. A focused stash audit and
an independent cloud-epic audit resolved the two ambiguous supersession calls.
