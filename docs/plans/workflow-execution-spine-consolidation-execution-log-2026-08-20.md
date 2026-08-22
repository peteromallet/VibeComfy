# Workflow execution-spine consolidation execution log

- **Goal:** Execute the workflow execution-spine consolidation from G0 through G7.
- **Plan:** `docs/plans/workflow-execution-spine-consolidation-plan-2026-08-20.md`
- **Execution venue:** `/workspace/vibecomfy-exec-spine-20260820/exec-spine`
- **Branch:** `fixer/workflow-execution-spine-consolidation`
- **Protected state:** base `5fc6be9d`; canonical six-entry manifest unchanged at SHA-256 `96b287c04718a59e09c4d8046ec4df9b7131644a709ee50eb8cb8a236086c323`; read-only r5 evidence preserved; structural-cleanup files and external worktrees untouched.

## Venue adaptation

The goal attachment names laptop launcher paths under `/Users/peteromalley/.codex/skills/subagent-launcher/`. This agentbox has the identical installed skill under `/root/.codex/skills/subagent-launcher/`; the receipt wrapper embeds the box paths. The venue re-ran T0.0 and T0.1 after the operator moved execution to the agentbox. Their receipts are preserved at `/workspace/vibecomfy-exec-spine-20260820/g0/t00-receipt.json` and `/workspace/vibecomfy-exec-spine-20260820/artifacts/t01-receipt.json`.

## G0 / T0.0 — Source custody and baseline

- **Disposition:** passed; bootstrap receipt, no commit or changed files.
- **Input/base SHA:** `5fc6be9dbe811df77e43d440ad087440e8bd57b5`.
- **Output SHA:** receipt `4da22c397e92276d230ec0ad33fbefe7d7f11b28268ebca4b85aff78d81534c0`.
- **Model route:** `codex:gpt-5.6-luna`.
- **Launcher command:** `/root/.pyenv/versions/3.11.11/bin/python3 /root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0-brief-t00.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`.
- **PID/timestamps/exit:** PID `1634`; `2026-08-20T19:01:34Z` → `2026-08-20T19:10:45Z`; exit `0`.
- **Brief/result digests:** brief `e6a773a5d4d702ab377271accb9f5323a5ef5697268b3f9a7db401caf157fdb8`; result `6b317cf7b7f6a583a897e8b71d8770dad0cba6807b2304c4f8b6d4585ba4308e`.
- **Tests/evidence:** six-entry validate-only exit `0`; T1.1 baseline exit `1` with six recorded pre-existing failures; T1.2 baseline exit `0`; evidence is the T0.0 receipt.
- **Residual risks:** container inventory was unavailable because Docker is not installed; protected checkout was observed dirty but untouched; T1.1 base failures remain intentionally pre-existing.
- **Next unblocked card:** T0.1.

## G0 / T0.1 — Freeze r5 regressions and final-five identity

- **Disposition:** passed; bootstrap receipt and commit `80e60329322b349448d194c73f0bcd02016befb8`.
- **Input/base SHA:** `5fc6be9dbe811df77e43d440ad087440e8bd57b5`.
- **Output SHA:** receipt `9edc6bb3e8fc6087fa1ee560eba24541629d5a0cf0b0e5583be829a76ca45834`; final-five manifest `857bf9cb2b1ce251f2952c2c576eaea3295175aa89bb0e0b39d414792324a733`.
- **Model route:** `codex:gpt-5.6-luna`.
- **Launcher command:** native metadata is recorded in the T0.1 receipt; no paid/live model call occurred.
- **PID/timestamps/exit:** receipt validation `2026-08-20T19:20:46Z`, focused tests `2026-08-20T19:20:56Z`, commit date `2026-08-20`; exit `0`.
- **Brief/result digests:** the T0.1 brief is `/workspace/vibecomfy-exec-spine-20260820/g0/t01-brief.md`; command output digests are `26bfc5c82bdaa129e3b2b7c7cba47831fb8c37bad0e1931a02c71a5af40e11` and `a6dd04167fa876d8912b4b9f730993f4aa6a30437faa0d13f43632ede23bd616` as recorded in the receipt.
- **Tests/evidence:** final-five validate-only passed with `model_calls: 0`; seven focused regression tests passed with one intentional xfail; fixture digests and changed-file allowance are in the receipt.
- **Residual risks:** mixed UI/API source-lineage regression remains intentionally frozen for T1.1; timeout and protocol enforcement belong to later cards.
- **Next unblocked card:** T0.3.

## G0 / T0.3 bootstrap

- **Disposition:** passed; native bootstrap receipt registered after implementation commit.
- **Input/base SHA:** `5fc6be9dbe811df77e43d440ad087440e8bd57b5`.
- **Output/commit:** receipt SHA-256 `b7040eccd04bd0b49af039dccfcb8b78853e610896d9895b6773d62949309ad7`; implementation commit `22d68c60c13cdf1def9d0476e2026e5c5627f971`.
- **Model route:** `codex:gpt-5.6-luna`; resolved `openai-codex/gpt-5.6-luna`.
- **Launcher command:** `/root/.pyenv/versions/3.11.11/bin/python3 /root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0-brief-t03.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`.
- **PID/timestamps/exit:** PID `3688`; `2026-08-20T19:35:25Z` → `2026-08-20T19:44:18Z`; exit `0`.
- **Brief/result digests:** brief `601b497710ee5b8fc3c866672c8052fde4aa09569307cb3679aa02057244aa45`; captured stdout result `a9cab249099eb7c9fd6a9a513e0468042ad7719e09f74890c2aa669f54d32c26`.
- **Tests/evidence:** focused wrapper/validator tests `14 passed, 1 warning`; seeded validator exit `0`; fake self-check valid exit `0` (`valid.stdout` SHA-256 `3d12a5d6d223f513dabfd3886003e73c15f3d4c4eecb339135fd8e83f36bc88a`), allowance violation exit `2` (`violation.stderr` SHA-256 `cddbcfdd1bc5025d0bbaceee853b4d6389cc8434b49383eccef4c2251432a679`), overlap rejection exit `2` (`overlap.stderr` SHA-256 `4846bb89082d563b6e3eb458f64a784230db730b4e141c8a5ad743e3b24370ef`).
- **Changed files:** wrapper, validator, focused tests, G0 manifest/shards/log, and bootstrap receipt; the base-to-head receipt enumerates the earlier T0.1 changes as inherited diff.
- **Residual risks:** no live model calls beyond this bootstrap; later cards must populate the manifest and run G0 review.
- **Next unblocked card:** `T0.2` — first wrapper-routed Grok XHARD-REVIEW.

## G0 / T0.4 — Operator-directed 50-scenario finale amendment (2026-08-20)

- **Disposition:** in progress; plan/goal/log amendment plus new final50
  manifest only. This entry records the operator override and the bounded
  T0.4 change; it does **not** claim implementation review, live completion,
  G7, merge, or promotion.
- **Operator directive (2026-08-20):** authoritative G7 finale is 50
  scenarios × 2 modes (staged + threaded) = 100 concurrent live legs;
  concurrency 10 = 10 waves; tag `final-50x2`; one authoritative G7.2 run.
  Authoritative G7 manifest:
  `tests/live_agentic_harness/threaded_comparison_manifest_final50.json`.
  Locked final5 remains the r5-comparable core (final50 entries 1–5) and is
  independently unchanged. Canonical six-entry manifest unchanged. No merge
  to `main`, no live promotion.
- **Prerequisite XHARD pre-code review:**
  `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/T0.4-plan-amendment-50-review-receipt.json`;
  wrapper exit `0`; result digest
  `d26b080e2e3a46f6127c9908bf71b05bb3f5469b53e463a81ebf639a62b1da91`;
  base SHA `1c2eb90cf4c319eea0439a693dc53a2850c952ab`; model route
  `grok-4.6`. Wrapper recorded no `STOP:` token. The implementer proceeds
  under the required pre-code `continue` gate for this card.
- **Changed-file scope (allowance):**
  `docs/plans/workflow-execution-spine-consolidation-plan-2026-08-20.md`,
  `docs/plans/goal-workflow-execution-spine-consolidation-2026-08-20.md`,
  `docs/plans/workflow-execution-spine-consolidation-execution-log-2026-08-20.md`,
  `tests/live_agentic_harness/threaded_comparison_manifest_final50.json`.
  Forbidden and byte-unchanged: `threaded_comparison_manifest_final5.json`,
  `threaded_comparison_manifest.json`, and the evidence directory.
- **Stop-rule carve-out:** only the old “final-five inputs contradictory”
  *count* contradiction is waived for this operator-authorized amendment.
  All other stop rules remain active.
- **Next unblocked card:** post-commit Grok `[XHARD-REVIEW]` of the complete
  T0.4 diff; then evidence/log integration. T7.1/T7.2/T7.3 briefs must
  reference final50. No live run on this card.
 
## 2026-08-20 — T0.2 [XHARD-REVIEW] contract and overlap freeze

- **Disposition:** `continue`; Grok 4.6 wrapper-routed review at `20:06Z`.
- **Receipt/result:** `T0.2-receipt.json`; result digest `3d83446906b99fa81bc1c1240464be57d634ebb1436af592d7ec68564e6ce883`.
- **Wrapper outcome:** exit was blocked only by a false-positive allowance violation caused by pre-existing untracked plan/goal documents under old base-SHA accounting.

## 2026-08-20 — T0.2 allowance adjudication

- **Disposition:** `correct`; Grok 4.6 at `20:19Z`; receipt `T0.2-allowance-adjudication-receipt.json`; result digest `15d5b839b70d6638bbcb9d23661e5c03cf4410dd827aaf1e3339a858d1a7c3ee`.
- **Process correction:** changed-file accounting must use process lifetime; finding `F-T03-CHANGED-FILES-BASELINE` introduced.

## 2026-08-20 — T0.3 revision2

- **Disposition:** passed; Luna implementer commit `1c2eb90cf4c319eea0439a693dc53a2850c952ab` applied the ignore-rule accounting fix.
- **Receipt/result:** `T0.3-revision2-receipt.json`; result digest `99db4517319931e5da45d979707cf488fd2153274cf750075d871d2ce6b64e4a`; 17 focused tests passed.

## 2026-08-20 — T0.3 revision2 re-review

- **Disposition:** CLEAN; fresh independent Luna review; receipt `T0.3-revision2-rereview-receipt.json`; result digest `c0e339a955582225fe357e811a10d90915e3337febe9778e682e26d3b08f8df0`.
- **Closed findings:** `F-T03-IGNORE-RULE-NEW-CREATE`, `F-T03-CHANGED-FILES-BASELINE`, `F-T03-REVIEW-MUTATING-SELF-DISPATCH`, `F-T03-REREVIEW-CHAIN-OPEN`, and `F-T03-D427-UNREVIEWED-CANDIDATE`.
- **Review quarantine:** `T0.3-revision-review-receipt.INVALID-MUTATING-REVIEW.json` was invalidated and quarantined.

## 2026-08-20 — T0.3 review adjudication

- **Disposition:** `stop`; Grok at `20:57Z` on the invalid mutating review; receipt `T0.3-review-adjudication-receipt.json`; result digest `25a4efae51e5e7dbe7ac9df916057a378c42e46c6a808ccc01a30a5a62f4c2c1`.
- **Resolution:** the revision2 and independent re-review chain above resolves the issue; do not reopen it.

## 2026-08-20 — Operator directive: fifty scenarios

- The operator directive quoted in the brief supersedes the five-scenario finale count. `T0.4-plan-amendment-50` implements 50 scenarios × 2 modes (staged and threaded) = 100 legs, concurrency 10, 10 waves, tag `final-50x2`, and one authoritative G7.2 run.

## 2026-08-20 — T0.4 plan amendment 50 brief

- Luna brief agent receipt `T0.4-plan-amendment-50-brief-receipt.json` produced the review brief, implementer brief, and allowance.

## 2026-08-20 — T0.4 plan amendment 50 pre-code review

- Fresh Grok XHARD review; receipt `T0.4-plan-amendment-50-review-receipt.json`; exit `0`; `changed_files: []`; result digest `d26b080e2e3a46f6127c9908bf71b05bb3f5469b53e463a81ebf639a62b1da91`.
- All adversarial checks passed; `JUDGMENT_REQUIRED: none`; amendment was coherent, complete, and non-conflicting.

## 2026-08-20 — T0.4 plan amendment 50 implementer

- Grok 4.6 commit `b34eb5ad8f6ec70053a2d0a1822122ac02a2b2f9` (`docs(exec-spine): amend G7 finale to 50x2/100 legs`); receipt `T0.4-plan-amendment-50-receipt.json`.
- Changed files were exactly the four allowed paths: plan, goal, execution log, and `threaded_comparison_manifest_final50.json`.
- `final50` has schema `1`, staged and threaded modes, 50 unique entries, entries 1–5 byte-identical to final5, and no null locks. final5 and the canonical six-entry manifest remain unchanged (`857bf9cb…` and `96b287c0…`).
- Wrapper `ALLOWANCE_VIOLATION` was recorded and adjudicated in the next entry.

## 2026-08-20 — T0.4 allowance adjudication

- **Disposition:** `correct`; fresh Grok review; receipt `T0.4-allowance-adjudication-receipt.json`; result digest `fb21fabb395adbf5e39ae36df3fa472794c7e43ba77ef8f2bbccc1afc277242d`.
- The violation was a false positive caused by a self-contradictory allowance file: `"**"` in `forbidden` overrode the concrete `allowed` list. Commit `b34eb5ad` is allowance-compliant.
- **Process correction:** mutating-card allowances must use a concrete `allowed` list with `forbidden: []`, matching the T0.3-revision2 shape.

## 2026-08-20 — T0.4 post-commit review

- Fresh independent Grok XHARD review of complete diff `1c2eb90c..b34eb5ad`; receipt `T0.4-postcommit-review-receipt.json`; exit `0`; `changed_files: []`; result digest `a658f716f758636642817ee100c885ef4642b23a72b027c343f95b7787c4aa75`.
- Must findings: none; `JUDGMENT_REQUIRED: none`. Production path verified: `--manifest final50 --concurrency 10` produced 100 unique legs in 10 waves with model-free preflight. Plan, goal, log, and manifest are consistent.

## 2026-08-20 — Residual risks and next card

- `scripts/validate_workflow_execution_spine_evidence.py` still hard-codes `mode == "5x2"` and exactly 10 leg receipts; `CARD_ORDER` and `GATE_CARDS["G0"]` omit T0.4. A follow-on card must retarget the validator before G7 evidence close; this is outside the T0.4 allowance and is not a G0 blocker.
- `external_workflows/corpus/` is not mounted in this worktree. final50 locked-input digests match catalog metadata, but T7.1 preflight still needs the corpus mount for source-file presence.
- T0.4 is an intentional out-of-sequence operator insert; the G0 graph remains `T0.0 → T0.1 → T0.3 → T0.2 → G0`.
- Test shards were already consistent with the plan (focused T1.x–T6.2 shards plus singleton `broad_suite_once_v1`); no shard changes were required.
- **Next unblocked card:** `T0.2-recertification` — fresh Grok XHARD review of the contract/overlap freeze on then-reviewed SHA `b34eb5ad`, with a regenerated brief referencing the amended plan and final50 identity; then G0 gate.

## G0 custody re-proof — 2026-08-21

- **Disposition:** the four independent re-review must findings are corrected in this one permitted revision; one author-correct commit and a fresh independent complete-diff review remain for closure of `G0-MUST-CUSTODY-001`. This is the adjudicated rerun of `G0-revision-custody`, whose no-commit result digest was `2d885fba20ba473d03212ab99367025864d2b94cb2407722eb61ef03a421583c`.
- **Task/gate/label/role:** `G0-revision-custody-rerun-2`; `G0`; `G0 [HARD-REVISION] correct custody re-proof entry for four must findings (chain link, proof provenance, tree-diff, UTC end)`; implementer; route `codex:gpt-5.6-luna`.
- **Binding adjudication:** `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/G0-custody-stop-adjudication-receipt.json`; adjudication `correct`; result digest `221f5ba2528ac2b324f77130ffa3f3807a8e9032fbf28e61615b749c3ccce242`. It establishes that `exec-spine-orchestrator` is this orchestrator's supervisor-created hosting session, matching the `supervisor.log` relaunch at `2026-08-20T23:41:06Z`, and is excluded from the §3.2/§13 protected-state boundary. No other tmux session receives that exclusion.

### Base custody and ancestry

- **Worktree/branch:** `/workspace/vibecomfy-exec-spine-20260820/exec-spine`; `fixer/workflow-execution-spine-consolidation`.
- **Immutable input/base and pre-commit HEAD:** `16c38d362492a53ffec97944ca77925c15a475f9`; `git rev-parse HEAD` exit `0`, result `16c38d362492a53ffec97944ca77925c15a475f9`.
- **Planning commit/tree:** `5fc6be9dbe811df77e43d440ad087440e8bd57b5`; plan SHA-256 `475c8480124e25cca7a5f1a1c1f2aad049499b670cd1b994d8d4feaae995a35e`.
- **Authorized remote:** `git ls-remote origin refs/heads/main` exit `0`, observed `054bce5bdc9c63d68ac7e6141063e1f029a70dcb`, matching the authorized SHA. No fetch was needed and no worktree ref was changed.
- **Ancestry exits:** `git merge-base --is-ancestor 5fc6be9d HEAD` exit `0`; `git merge-base --is-ancestor 054bce5b HEAD` exit `1` as expected.
- **Complete ancestry chain (forward):** `5fc6be9d → 80e60329 → 3629a8d8 → d1dfd8ad → d427f7f6 → 1c2eb90c → b34eb5ad → 337debc5 → ceba112b → f8abb577 → a653d0d2 → d8b406da → ac0b84c2 → 16c38d36`.
- **History/ref custody:** pre-commit reflog showed the existing chain ending at `16c38d36`, with the complete path above; no reset, stash, merge, ref mutation, history rewrite, amend, push, or integration occurred. HEAD remained `16c38d36` until the single permitted log correction commit.

### Tree-identical merge proof

- **Required simulation:** remote `054bce5bdc9c63d68ac7e6141063e1f029a70dcb` with plan `5fc6be9dbe811df77e43d440ad087440e8bd57b5`.
- **Primary command/result:** `git merge-tree --write-tree 054bce5bdc9c63d68ac7e6141063e1f029a70dcb 5fc6be9dbe811df77e43d440ad087440e8bd57b5` returned exit `128` because this Git does not support `--write-tree` (`fatal: unknown rev --write-tree`); this read-only command did not mutate the worktree.
- **Actual disposable-clone rerun:** `git clone --no-local --no-hardlinks /workspace/vibecomfy-exec-spine-20260820/exec-spine /tmp/g0-revision-custody-rerun-2/merge/disposable-clone`; `git checkout --detach 5fc6be9dbe811df77e43d440ad087440e8bd57b5`; `git merge --no-commit --no-ff 054bce5bdc9c63d68ac7e6141063e1f029a70dcb`. Clone/checkout/merge exits were `0/0/0`; actual merge output was `Automatic merge went well; stopped before committing as requested`; `git status --short` exit `0` with empty output, so conflict status was clean. Exact commands, paths, timestamps, outputs, and exits are recorded in `/tmp/g0-revision-custody-rerun-2/merge/command-register.txt`.
- **Trees and non-tautological comparison:** simulated merge tree from `git write-tree` is `38cc90e21d4710863032d4246fee6a115655c269`; planning tree from `git rev-parse 5fc6be9dbe811df77e43d440ad087440e8bd57b5^{tree}` is `38cc90e21d4710863032d4246fee6a115655c269`; exact comparison `git diff --quiet 38cc90e21d4710863032d4246fee6a115655c269 5fc6be9dbe811df77e43d440ad087440e8bd57b5^{tree}` exit `0` (`tree_diff_exit=0`). This compares the simulated merge tree to the planning commit tree and does not use `HEAD^{tree}`.
- **Normalized proof:** `/tmp/g0-revision-custody-rerun-2/merge/normalized-proof.txt`; SHA-256 `fd5de1c8b6ec2100914e1122368bdd8ad2a99b492b26f8518918c06d3a9f51af`. Its canonical text records this rerun's actual absolute source/clone paths and commands, so it is not genuinely identical to the prior-root normalization (`8c7d3c3357bb1f0dbac02d7498868a80496d35f8fbfc3a251bb8fa5f5f8354de`); the new digest is recorded instead. Raw merge output, exits, status, both tree OIDs, and comparison evidence are under `/tmp/g0-revision-custody-rerun-2/merge/`.

### Protected cleanup and manifest comparison

- **T0.0 comparable cleanup bytes:** current SHA-256 equals the T0.0 values for `docs/plans/codebase-structural-cleanup-master-plan.md` (`9c2f692f9f9d2d4bf146603075c1812be011340ae70b098a99c48928547a8e73`), `docs/plans/goal-codebase-structural-cleanup-2026-08-20.md` (`90c1cd0284a7a872cbbe91c8bc7c37e1c6516cd759718d058d41fe1589967890`), and `docs/plans/codebase-structural-cleanup-execution-log-2026-08-20.md` (`01ecd89b4d25f1e289b637a222662c6994a4a7fb645bd4b8ac55c1e45c9e2490`). These are qualified byte comparisons only for paths with an available T0.0 digest.
- **Six-entry manifest:** `tests/live_agentic_harness/threaded_comparison_manifest.json` current SHA-256 `96b287c04718a59e09c4d8046ec4df9b7131644a709ee50eb8cb8a236086c323`, equal to the T0.0 six-entry manifest digest.
- **Index/current scope evidence:** `git ls-files -s --` for the four protected paths and the current SHA outputs are in `/tmp/g0-revision-custody-rerun-2/protected/`; no validator, manifest, receipt, plan, goal, or evidence file was written. The only permitted repository path for this card is this execution log.
- **Structural cleanup evidence:** `docs/plans/codebase-structural-cleanup-evidence/` is absent. T0.0 supplied no digest for this path; this is not an unchanged-path claim.

### Qualified environmental re-baseline

- **tmux:** current `tmux ls` exit `0`: `exec-spine-orchestrator: 1 windows`; `tmux list-windows -a -F '#{session_name}|#{window_index}|#{window_name}'` exit `0`: `exec-spine-orchestrator|0|bash`. The adjudication records the supervisor-hosting purpose and historical creation/relaunch `2026-08-20T23:41:06Z` and excludes this one session from §3.2/§13. Current identity/window count is recorded, not asserted unchanged from T0.0. No other tmux session was present; the exclusion does not cover any other session.
- **`/workspace/omp-replaces-hermes`:** exists=yes; `git -C ... rev-parse --is-inside-work-tree` exit `128` (`not a git repository`). Current sorted path-list-with-directories SHA-256 is `6e385a62071c92a43b256052b4805fb79578ff5d2057c8f5f4b6e76a39ba8f05`; this is a qualified current observation with no comparable T0.0 baseline and no unchanged-state claim. Current `health.log` stat is `type=regular file|size=257308|mtime=1787278393|inode=913082`; current digest is `1b4737e4c467b73f80c84ed2e3d82753ca4a098ae92e74e7b014e0d3d68aa6d4`; T0.0 recorded only present/untouched, so no byte-identity or unchanged-state claim is made.
- **`/workspace/arnold`:** current `HEAD` `3299a4f076c9d811314ef081bfb594cdf8c084a6`, branch `main`, dirty count `9`; current `git status --short` is captured at `/tmp/g0-revision-custody-rerun-2/environment/arnold-status.txt`. This is a current baseline, not an unchanged-path proof.
- **Docker:** `docker ps` exit `127`; command unavailable (`error: command not found: docker`).
- **r5 comparison:** expected `/workspace/omp-replaces-hermes/Astrid/.megaplan/bakeoffs/phase-5-20260505/comparison.json` is absent; no current digest is invented; absence is recorded against T0.0 digest `94f47ceba5496129e3b0d6604283ac180db37baf110ee9fe3369d84df88fec14`.

### Command/evidence register and custody controls

- **UTC interval:** actual revision rerun start `2026-08-21T02:13:52Z`; actual rerun end `2026-08-21T02:14:14Z`. All revision command timestamps and outputs are under `/tmp/g0-revision-custody-rerun-2/`, with `preflight/`, `merge/`, `protected/`, and `environment/` paths.
- **Read-only command results:** base/branch/status/show/reflog: `/tmp/g0-revision-custody-rerun-2/preflight/`; remote/merge/trees: `/tmp/g0-revision-custody-rerun-2/merge/`; ancestry and expected exits: `/tmp/g0-revision-custody-rerun-2/preflight/`; protected hashes/index/absence: `/tmp/g0-revision-custody-rerun-2/protected/`; tmux/docker/Arnold/omp/r5: `/tmp/g0-revision-custody-rerun-2/environment/`. The initial unsupported probe (`merge-tree --write-tree`, exit `128`) is preserved in the prior entry; the actual disposable-clone rerun and corrected ancestry-range commands passed.
- **Non-mutation:** validator, wrapper, manifest, receipts, plan, goal, cleanup files, protected state, and every repository path other than this execution log were untouched. The only merge command was the permitted uncommitted disposable-clone simulation; no repository merge commit or integration occurred. No tests, full suite, focused product tests, live model/runtime calls, secret access, push, history/ref mutation, or network operation other than the prescribed `git ls-remote` occurred.
- **Rejected alternatives:** no worktree fetch, no merge commit, no textual-similarity substitution for tree identity, no `HEAD^{tree}` tautological comparison, no prior scratch-root reuse, no claim of unchanged state where T0.0 lacks a comparable baseline, and no STOP on the adjudicated hosting-session signal.
- **Residual risks:** Docker remains unavailable; `/workspace/omp-replaces-hermes` and structural-cleanup evidence lack T0.0 comparable baselines; the external health log and current external path-list observation differ from prior non-baseline sentinels; the execution worktree contains pre-existing untracked evidence/status noise that was not touched.
- **Next unblocked card:** `T0.2-recertification` — fresh Grok XHARD review of the contract/overlap freeze, then G0 gate review; no integration follows this custody card.
- **JUDGMENT_REQUIRED:** none.
- **Correct-content preservation and handoff:** all previously verified correct content remains, including remote SHA, both ancestry exits, protected cleanup and six-entry manifest digests, adjudicated tmux exclusion, qualified baselines, non-mutation statement, residual risks, next unblocked card, and `JUDGMENT_REQUIRED: none`. Exactly one author-correct commit containing only this correction is permitted; a different routed reviewer must perform the fresh independent complete-diff review over `ac0b84c2..<new commit>` before `G0-MUST-CUSTODY-001` closes.

## G0 evidence log — post-T0.4 sequence and gate disposition (2026-08-21)

- **Task/gate/label/role:** `evidence-log G0`; `G0`; `evidence-log G0 gate sequence and disposition`; evidence recorder.
- **Disposition:** **PASS**. The complete post-T0.4 sequence is closed in order; all four must finding families (`G0-MUST-VALIDATOR-001`, `G0-MUST-MANIFEST-001`, `G0-MUST-CUSTODY-001` with `.A/.B/.C/.D`, and `G0-MUST-RECERT-001`) have revision evidence and independent closed re-reviews. `G0-JR-RECERT-001` is adjudicated `correct`. The wrapper chain is closed, one review per phase is respected, and no unresolved judgment remains.
- **Input/output SHAs:** amended-final T0.4 baseline `b34eb5ad8f6ec70053a2d0a1822122ac02a2b2f9`; post-sequence repository input `ea3bf7a6a441763c17f6c3718cdf7de3d1cb58b4`; evidence output is this log/manifest update from that immutable base. Planning SHA-256 `475c8480124e25cca7a5f1a1c1f2aad049499b670cd1b994d8d4feaae995a35e`.
- **Model routes:** Grok `grok-4.6` for XHARD recertification/adjudication and STOP adjudication; Luna `codex:gpt-5.6-luna` for the independent gate review, briefs, HARD revisions, and final custody re-review. Receipt `model_route`, `resolved_model`, launcher argv, PID, and timestamps are authoritative for every item below.
- **Launcher forms:** Grok wrapper invocation was `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=<receipt brief_path> --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`; Luna invocation was `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=<receipt brief_path> --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`. These are the exact argv forms recorded in each receipt; each row gives the query file, PID, UTC interval, and exit.

### Ordered receipt register

1. **T0.2 recertification — continue.** Receipt `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/T0.2-recertification-receipt.json` SHA-256 `83ca1deabbd53715d0efd096f79151f0d4d22ac99603f39ea42d1589dc372397`; brief SHA-256 `dd82f64ae48d300b40d2e10e60de2c70aa633a2f1e17d18aa04fdfddd40c5166`; result SHA-256 `8dcecaaf6ef05eda47a2032e5d92b45b929d3e00fe2d0fb5509ecda84ad8b251`; input `337debc5e92c63e1aa049b8bc04015738b98d01f`; Grok PID `12939`; `2026-08-20T23:11:56Z` → `2026-08-20T23:18:28Z`; exit `0`; no commit/files; query `t02-recertification-brief.md`.
2. **G0 recertification adjudication — continue.** Receipt `.../receipts/G0-recert-adjudication-receipt.json` SHA-256 `84923733c27fae5e52fd3cb7d7c9a4225c3b351d6c9dc5914ac337e19f55e646`; brief `257c6a868ebafde0851b204082b0835730de24eb3d27ae0d19a288a9c0faca90`; result `2601675c5c389e9a25bbd657faf52f401ab9cd21819a08cdfdadfd1a88c31f38`; input `337debc5e92c63e1aa049b8bc04015738b98d01f`; Grok PID `13542`; `2026-08-20T23:33:16Z` → `2026-08-20T23:38:28Z`; exit `0`; no commit/files; query `g0-recert-adjudication.md`.
3. **Luna G0 gate review — four must findings opened.** Receipt `.../receipts/G0-gate-review-receipt.json` SHA-256 `f598ed112ba08b5c7b11f2c7164102ac98d75eb55a10da6770dece734770cb49`; brief `4095cd98fcecf7819d55afd36228ae3a2c69cac7aea750deefc3172defc0c0e9`; result `4a9dce6f82d4df3e2302a4c48591099e0eb05300da489a2f2ee39ebdfb535877`; input `337debc5e92c63e1aa049b8bc04015738b98d01f`; Luna PID `13358`; `2026-08-20T23:24:52Z` → `2026-08-20T23:31:49Z`; exit `0`; no commit/files; query `g0-gate-review-brief.md`. Findings were `G0-MUST-VALIDATOR-001`, `G0-MUST-MANIFEST-001`, custody family `G0-MUST-CUSTODY-001/.A/.B/.C/.D`, and recertification judgment family `G0-MUST-RECERT-001`/`G0-JR-RECERT-001`.
4. **Validator revision brief.** Receipt `.../receipts/G0-revision-validator-brief-receipt.json` SHA-256 `d4e838c497d92bf0aaf73d71ecc8571b1b39eeec2e3b2caa38cb89877b8e6a5f`; brief `8d06573a0c2df23b27e680642564f7c36ee0c0181ebcb43ee002488b36d6f340`; result `642a5ca16fbe3ac6fb26958068488e8c10d5f41d14464ddf16e644b7e0903b33`; input `337debc5e92c63e1aa049b8bc04015738b98d01f`; Luna PID `13932`; `23:44:10Z` → `23:46:52Z`; exit `0`; no commit/files; query `g0-revision-validator-brief-agent.md`.
5. **Validator revision.** Receipt `.../receipts/G0-revision-validator-receipt.json` SHA-256 `20cc62834124c0b8a1b215ca525e8ab99999036c341439e05b2efacf43d4f5d2`; brief `0ce024c03f071b1d4846c129f25ef25ddc0ba834ec966bd6f799348059885fb7`; result `79fe0467b2a802c01377eb6ac26a441d9805c16a1ad450deed68f868506890f8`; input `337debc5e92c63e1aa049b8bc04015738b98d01f`; Grok PID `14046`; `23:47:05Z` → `2026-08-21T00:00:38Z`; exit `0`; commit `ceba112bee6d45893e8b016412c895be3696d8a1`; files validator/tests plus ignored cache bytecode as recorded in the receipt; query `g0-revision-validator-brief.md`.
6. **Validator allowance violation artifact.** `.../receipts/G0-revision-validator-violation.json` SHA-256 `6aded1fe342faf22c750b78a61d6d9b7780bb34a6e1ed0c91283cbc8955808a6`; no launcher/PID/result because this is the recorded violation object; violation was the three ignored cache paths, not a hidden finding.
7. **Validator violation adjudication.** Receipt `.../receipts/G0-revision-validator-adjudication-receipt.json` SHA-256 `65482c74d1746c624b31b99f9759a3dcbf4b81c03a2d847faed38c9eb7f9cab3`; brief `59113d3ed305c9eee17b5cffe11192d8160ec0c8657e4fe1fac81aaa8083a6bc`; result `df3afa345af8aac6f0326c7850e115c794283199c850e568a4671c11c81015c9`; input `ceba112bee6d45893e8b016412c895be3696d8a1`; Grok PID `14463`; `00:02:24Z` → `00:06:53Z`; exit `0`; no commit/files; query `g0-revision-validator-adjudication.md`; classification `correct`, then independent re-review required.
8. **Validator independent re-review — closed.** Receipt `.../receipts/G0-revision-validator-rereview-receipt.json` SHA-256 `5ee08c60d9125249fd07b72e979b9a5f4f89cf478085cb26413f149e7a412929`; brief `bf479caa9aef89e7b255f1634d30b1a45205d5d602f9e141412bacb10902b07e`; result `5055de55d77fb3d4ec00db1ef538fd11874822e064e96de8441a55821bad984b`; input `a653d0d2ac8643af85708cd99ca12f12d8a7523e`; Grok PID `16803`; `00:52:16Z` → `01:00:08Z`; exit `0`; no commit/files; query `g0-revision-validator-rereview.md`; `G0-MUST-VALIDATOR-001` CLOSED, `JUDGMENT_REQUIRED: none`.
9. **Wrapper revision brief.** Receipt `.../receipts/G0-revision-wrapper-brief-receipt.json` SHA-256 `003e93ea29f23bc7bb7c7f83c75def8c94a81c3e19f3759ca8e984bba918cd8b`; brief `75faeb636a1e884f6df5a364957505f2631da7453be203e7ccd093261033402d`; result `8b0ad66f24fd6e0bdd39633c22bc7e965ee5238e44065208f9c409c844362681`; input `ceba112bee6d45893e8b016412c895be3696d8a1`; Luna PID `14651`; `00:07:47Z` → `00:10:30Z`; exit `0`; no commit/files; query `g0-revision-wrapper-brief-agent.md`.
10. **Wrapper revision 1.** Receipt `.../receipts/G0-revision-wrapper-receipt.json` SHA-256 `b248f73b34b95a242efef431616774c109e72409e0c6a25e5a13a27e51804c80`; brief `a7f908bdfcb1002de1d87a462c95005d821f1198043cca40ea4256b9c4ee8753`; result `0083bc9a8adf26244ee41a7dc0dec1ee85604724b8317b6ba6cd9a0c21b61bbc`; input `ceba112bee6d45893e8b016412c895be3696d8a1`; Luna PID `14757`; `00:10:40Z` → `00:19:30Z`; exit `0`; commit `f8abb57731162b29619164f919a37d72f53cf2ac`; wrapper/tests changed; query `g0-revision-wrapper-brief.md`.
11. **Wrapper revision 1 re-review.** Receipt `.../receipts/G0-revision-wrapper-rereview-receipt.json` SHA-256 `4df9af7a44993a93e396d03b46d4f6d616e5bf79bda6d3f4778a42176bff15c5`; brief `913654f9f2d2491d46cb82912bf95af20ecf02b8f8696eb3a700a5f26acee6c1`; result `b0e52a42371546532b760d32263484c055669e457c9148192ed830ab6d7b8f51`; input `f8abb57731162b29619164f919a37d72f53cf2ac`; Luna PID `15220`; `00:19:51Z` → `00:25:21Z`; exit `0`; no commit/files; query `g0-revision-wrapper-rereview.md`; clean.
12. **Wrapper revision 2 brief.** Receipt `.../receipts/G0-revision-wrapper-revision2-brief-receipt.json` SHA-256 `1a9b2484d3bfcbb554572dad98b35e3d66e9a64516e6c141149a58145cf9dfac`; brief `f3a0ae9650eb998f8d90c511f8cfaf34e7bb37ffcf9cb6d97f697654d30cffd5`; result `eb08f503028922277c6159917866131b01e9547dd3e290031d6675cae1372db4`; input `f8abb57731162b29619164f919a37d72f53cf2ac`; Luna PID `15432`; `00:25:47Z` → `00:28:03Z`; exit `0`; no commit/files; query `g0-revision-wrapper-revision2-brief-agent.md`.
13. **Wrapper revision 2.** Receipt `.../receipts/G0-revision-wrapper-revision2-receipt.json` SHA-256 `43898d2de35a6e7d810f2ed2e0665935c14649d87f0ccd5452567246e8956f01`; brief `62f96085005723d4650d262b3542530cf150ab41ec7a92fad3c24b45e0bf2855`; result `5b0bfc058555e47701f76feb51d1905793cdd1d552bcc990d8cb81f9b3c4e48d`; input `f8abb57731162b29619164f919a37d72f53cf2ac`; Luna PID `15529`; `00:28:08Z` → `00:46:57Z`; exit `0`; commit `a653d0d2ac8643af85708cd99ca12f12d8a7523e`; wrapper/tests changed; query `g0-revision-wrapper-revision2-brief.md`.
14. **Wrapper revision 2 re-review — closed.** Receipt `.../receipts/G0-revision-wrapper-revision2-rereview-receipt.json` SHA-256 `983de5d73129682f9b0917596af747634516d0b15806f2f6a40aa22b95036319`; brief `cba2129c7c12efa3bdec16522b186f592d4192218f4f2e6cfea101f70c5ab48d`; result `26638c3e050c963799308ec285999bdd28f701d9777759bc9d08c91707da9bf5`; input `a653d0d2ac8643af85708cd99ca12f12d8a7523e`; Luna PID `16579`; `00:47:21Z` → `00:52:02Z`; exit `0`; no commit/files; query `g0-revision-wrapper-revision2-rereview.md`; no findings, no judgment.
15. **Manifest revision brief.** Receipt `.../receipts/G0-revision-manifest-brief-receipt.json` SHA-256 `5a489e98e554a223964c1cbfff45b879a027d9531f059e464ab0dee553504787`; brief `2bfc58ed275da8909200b02ae8fe66638fd9ed4e86716430eb4e0bcc84a7fe47`; result `f39063837bc9a9850bb6600896a30e1e4998608325d813f13706108dc9305737`; input `a653d0d2ac8643af85708cd99ca12f12d8a7523e`; Luna PID `17134`; `01:01:27Z` → `01:06:39Z`; exit `0`; no commit/files; query `g0-revision-manifest-brief-agent.md`.
16. **Manifest revision 1.** Receipt `.../receipts/G0-revision-manifest-receipt.json` SHA-256 `7cfcd4413075fcbcfdebab2e762f6b210487965887b05aa13ba57d3d6d843582`; brief `853d28162d0ac10d58ee7933e15c83efa1e92611abb3416e9b1e1cc4f3f07dc5`; result `5e0b99a325e6f153cedf9d57d1addb251debf84ecc458a9ccb73af138e3d6fc0`; input `a653d0d2ac8643af85708cd99ca12f12d8a7523e`; Luna PID `17258`; `01:06:44Z` → `01:10:07Z`; exit `0`; commit `d8b406da6b1a4f924c7c66c84966b1269936a28a`; manifest changed; query `g0-revision-manifest-brief.md`.
17. **Manifest revision 1 re-review.** Receipt `.../receipts/G0-revision-manifest-rereview-receipt.json` SHA-256 `6e3895ba6cfb3c3d62463db275dfa41f593b2bfdea270ef2323ce458d54fd089`; brief `87634fd70072a7394c7f19403cb7936c602011401276ab0e2a28f162ee4973e5`; result `d41046b178429776018c6d797a0a495946ffb3dcebc5668b655eafab7ff6ddbe`; input `d8b406da6b1a4f924c7c66c84966b1269936a28a`; Luna PID `17473`; `01:10:28Z` → `01:14:50Z`; exit `0`; no commit/files; query `g0-revision-manifest-rereview.md`; historical T0.4 heading captures resolved, current judgment none.
18. **Manifest revision 2 brief.** Receipt `.../receipts/G0-revision-manifest-revision2-brief-receipt.json` SHA-256 `1ff4ca7397c7c9d1577a97a725f63f7b368a2d0062155f9cd57d10d1b4e2932c`; brief `126758a31072fd66a1e247b65de13d22d866952c5612a18dc5885b4e9d945c4d`; result `e19e3c6fad2049d40daa0e886a0c0e5e3d6d632aba1c59dc9e03452b9a403789`; input `d8b406da6b1a4f924c7c66c84966b1269936a28a`; Luna PID `17678`; `01:15:14Z` → `01:17:32Z`; exit `0`; no commit/files; query `g0-revision-manifest-revision2-brief-agent.md`.
19. **Manifest revision 2.** Receipt `.../receipts/G0-revision-manifest-revision2-receipt.json` SHA-256 `389675070fc184e0e50d93de169264065c717ebc159edc8062abae814e1e9c35`; brief `d30a6612961931a6b4234b98e74f18b068f6463660216bf51a7250331abfaec7`; result `bca96ae4e96f5e9534d32e1eb26f4403fb45eea828b67c4fbd05c428e9854a5b`; input `d8b406da6b1a4f924c7c66c84966b1269936a28a`; Luna PID `17777`; `01:17:37Z` → `01:19:37Z`; exit `0`; commit `ac0b84c214d9219f70039f5070781689340dafd9`; manifest changed; query `g0-revision-manifest-revision2-brief.md`.
20. **Manifest revision 2 re-review — closed.** Receipt `.../receipts/G0-revision-manifest-revision2-rereview-receipt.json` SHA-256 `dde6a2e688180aed21317c211896a4bcb825da63cf1d1dbe29da84aa7b707fbd`; brief `e14819347fd1415dc4ebed5805519ad927edab006deb98f73f89e96fded688c4`; result `76f334a13a02b732081540c0dc9c4f4f15455f3bd1f6396adefcf4845d43f5f8`; input `ac0b84c214d9219f70039f5070781689340dafd9`; Luna PID `18003`; `01:19:56Z` → `01:23:09Z`; exit `0`; no commit/files; query `g0-revision-manifest-revision2-rereview.md`; `G0-MUST-MANIFEST-001` CLOSED, current judgment none.
21. **Custody revision brief.** Receipt `.../receipts/G0-revision-custody-brief-receipt.json` SHA-256 `749bad3d4af488419543bb0bb18ea3e3159fc125cc03ef3e2f2832b874624813`; brief `8819bf4da0d42ab54a73a26ed8a6d5735ec4202bde7e1a6d025867b6f8d1c7cc`; result `28508842f3b8413b413496a5fcc15604e31916bd7aa7557e8e64a72d5ad57d75`; input `ac0b84c214d9219f70039f5070781689340dafd9`; Luna PID `18208`; `01:23:59Z` → `01:27:19Z`; exit `0`; no commit/files; query `g0-revision-custody-brief-agent.md`.
22. **Custody revision — STOP signal recorded.** Receipt `.../receipts/G0-revision-custody-receipt.json` SHA-256 `afc220db9574fe76d94a88371fff47723fd7c43a984e143ba7ef7672303f1738`; brief `c6c235613db02804ab5c04b8db2548d820c6f05ebcc2e55f92345acfd2816801`; result `2d885fba20ba473d03212ab99367025864d2b94cb2407722eb61ef03a421583c`; input `ac0b84c214d9219f70039f5070781689340dafd9`; Luna PID `18337`; `01:27:24Z` → `01:32:22Z`; exit `0`; no commit/files; query `g0-revision-custody-brief.md`.
23. **Custody STOP adjudication — correct.** Receipt `.../receipts/G0-custody-stop-adjudication-receipt.json` SHA-256 `f12255a97fab591c2a128c75a998f386b737f15e6dc7f5328851bb8366b0c989`; brief `9cbad987f098d3d361a2332912e4d05a19091547b42a0382a01b26f3511975f6`; result `221f5ba2528ac2b324f77130ffa3f3807a8e9032fbf28e61615b749c3ccce242`; input `ac0b84c214d9219f70039f5070781689340dafd9`; Grok PID `18651`; `01:33:01Z` → `01:37:44Z`; exit `0`; no commit/files; query `g0-custody-stop-adjudication.md`. `exec-spine-orchestrator` is supervisor-created hosting infrastructure and excluded from the protected boundary; no other tmux session is excluded.
24. **Custody rerun brief.** Receipt `.../receipts/G0-revision-custody-rerun-brief-receipt.json` SHA-256 `c6dcaca2133b5a6cc4b14f13c9e21a76b6a418502376581c6a23f985accf814e`; brief `d84e3979269bf259693080ce2d8073e7bcdc4441acc0e57d852b01cdc1ad3a0f`; result `1b2ff502219387ff9d94ca14cb3f29bef3b3f89cdcafdd56cb3d704f54e48c76`; input `ac0b84c214d9219f70039f5070781689340dafd9`; Luna PID `19003`; `01:43:41Z` → `01:45:23Z`; exit `0`; no commit/files; query `g0-revision-custody-rerun-brief-agent.md`.
25. **Custody rerun.** Receipt `.../receipts/G0-revision-custody-rerun-receipt.json` SHA-256 `2ebd9801fcc44ed11541acfad0ea8291993b429a32472c07225d6f147891ba3f`; brief `5d666e9ec37282a9a035684f56d88a38017ac478a88c1eb1b7217dd94c5c8e67`; result `c471dc8f19010f2a2885519d11b0e0e479bf1eac40ffdfcb02bbe68b6b5996c8`; input `ac0b84c214d9219f70039f5070781689340dafd9`; Luna PID `19113`; `01:46:51Z` → `01:56:59Z`; exit `0`; commit `16c38d362492a53ffec97944ca77925c15a475f9`; execution-log-only change; query `g0-revision-custody-rerun-brief.md`.
26. **Custody rerun re-review brief.** Receipt `.../receipts/G0-revision-custody-rerun-rereview-brief-receipt.json` SHA-256 `c671096636714350dd4c42ff4581fff18292ffbf41d5f7c72a76a48a8f1d878a`; brief `1fbdc87bcc0ab783dbafb79294510e41597789f5b14d15b5057726580298047a`; result `154647743f9484079c9e59cdd7b4c46f0c1bd3d9690825a101c678b967d08cd0`; input `16c38d362492a53ffec97944ca77925c15a475f9`; Luna PID `19574`; `01:57:49Z` → `02:01:37Z`; exit `0`; no commit/files; query `g0-revision-custody-rerun-rereview-brief-agent.md`.
27. **Custody rerun re-review.** Receipt `.../receipts/G0-revision-custody-rerun-rereview-receipt.json` SHA-256 `1c14f5cce69e4dc7b3ec352d636a80d03677e58680c67767541eaacd163bb26f`; brief `691e842d4a64b548b8bafbca274caac03a59e77448b38e110150259cfaea0589`; result `90d1c5cd8841a9079fe541c85323d8723fb7e7f436afc1096dbbde4ddbde5e41`; input `16c38d362492a53ffec97944ca77925c15a475f9`; Luna PID `19687`; `02:01:45Z` → `02:08:16Z`; exit `0`; no commit/files; query `g0-revision-custody-rerun-rereview.md`; clean but re-proof needed correction.
28. **Custody rerun-2 brief.** Receipt `.../receipts/G0-revision-custody-rerun-2-brief-receipt.json` SHA-256 `65a7d65224db2a33e3b64d16ece62c6295dcca58a602f034639de596d6696ab3`; brief `c021f392a0b2011f1bad6ca392d6ce810ea0c38f357f28ce5d286aaf4ea0004b`; result `d7ff80c296c1862a59bb69651cc40cbf548eee30aa3dea8e351d9ef6112c4ac3`; input `16c38d362492a53ffec97944ca77925c15a475f9`; Luna PID `19862`; `02:09:13Z` → `02:11:52Z`; exit `0`; no commit/files; query `g0-revision-custody-rerun-2-brief-agent.md`.
29. **Custody rerun-2 correction.** Receipt `.../receipts/G0-revision-custody-rerun-2-receipt.json` SHA-256 `2dac4e9f15b98a15be275b64ee9f2ade66fc3040fe425e5b3e7f6b63a882b0da`; brief `a2a3f634bb23e429aefe36ea10ba98fdca2899c2f7440c5f88072c4ba31c0105`; result `6538da770349978698110cc9e96549c201c963ad959ef07fc5ea3d9e51af9dcd`; input `16c38d362492a53ffec97944ca77925c15a475f9`; Luna PID `19956`; `02:11:56Z` → `02:23:10Z`; exit `0`; commit `ea3bf7a6a441763c17f6c3718cdf7de3d1cb58b4`; execution-log-only change; query `g0-revision-custody-rerun-2.md`.
30. **Custody rerun-2 re-review brief.** Receipt `.../receipts/G0-revision-custody-rerun-2-rereview-brief-receipt.json` SHA-256 `29f945e6936a70ac800da1c22245325dd3b94593a36f23415c39b3945e77bee4`; brief `2a6c8c3057fc022539b67619a84d6b28bcdd69bc92612c476d00c401ea761169`; result `2e2cc15e983936e192baccd81b1dcfa0d5fb2eef0e3779de382fb388f2c8413c`; input `ea3bf7a6a441763c17f6c3718cdf7de3d1cb58b4`; Luna PID `20446`; `02:23:42Z` → `02:26:42Z`; exit `0`; no commit/files; query `g0-revision-custody-rerun-2-rereview-brief-agent.md`.
31. **Final custody re-review — closed.** Receipt `.../receipts/G0-revision-custody-rerun-2-rereview-receipt.json` SHA-256 `e4f9bcdef13234088651dd5acc017f93c6ff8e5be16cef85f086b702b6bcd7a4`; brief `edf38d43456625aa1f94660a6aa764970d694099d38d318b1e86525fcaf1d6ab`; result `5bd75c55a4e1db3dfe5bb8b4a77382210e9308215caef76c0f37d095becdd4bc`; input `ea3bf7a6a441763c17f6c3718cdf7de3d1cb58b4`; Luna PID `20544`; `02:26:47Z` → `02:31:38Z`; exit `0`; no commit/files; query `g0-revision-custody-rerun-2-rereview.md`; all custody findings closed, qualified baselines and `JUDGMENT_REQUIRED: none` present.

### Finding closure, custody proof, and false-latch adjudication

- **Validator:** `G0-MUST-VALIDATOR-001` classification `XHARD`; revision `ceba112bee6d45893e8b016412c895be3696d8a1`; violation was explicitly recorded and adjudicated `correct`; independent closed re-review result `5055de55d77fb3d4ec00db1ef538fd11874822e064e96de8441a55821bad984b`.
- **Wrapper:** two revisions, `f8abb57731162b29619164f919a37d72f53cf2ac` then `a653d0d2ac8643af85708cd99ca12f12d8a7523e`; both independent re-reviews are clean (`b0e52a42371546532b760d32263484c055669e457c9148192ed830ab6d7b8f51`, `26638c3e050c963799308ec285999bdd28f701d9777759bc9d08c91707da9bf5`); no extra review was inserted.
- **Manifest:** `G0-MUST-MANIFEST-001` classification `HARD`; revisions `d8b406da6b1a4f924c7c66c84966b1269936a28a` then `ac0b84c214d9219f70039f5070781689340dafd9`; independent final re-review `76f334a13a02b732081540c0dc9c4f4f15455f3bd1f6396adefcf4845d43f5f8`.
- **Custody:** `G0-MUST-CUSTODY-001` and `.A/.B/.C/.D`, classification `HARD`, close on final result `5bd75c55a4e1db3dfe5bb8b4a77382210e9308215caef76c0f37d095becdd4bc`. The adjudication result `221f5ba2528ac2b324f77130ffa3f3807a8e9032fbf28e61615b749c3ccce242` is binding: `exec-spine-orchestrator` is supervisor-created hosting infrastructure, excluded from the protected boundary; no other tmux session is excluded.
- **Corrected custody proof:** chain through `16c38d362492a53ffec97944ca77925c15a475f9`; rerun root `/tmp/g0-revision-custody-rerun-2/`; normalized proof `/tmp/g0-revision-custody-rerun-2/merge/normalized-proof.txt`, SHA-256 `fd5de1c8b6ec2100914e1122368bdd8ad2a99b492b26f8518918c06d3a9f51af`; simulated merge tree `38cc90e21d4710863032d4246fee6a115655c269` equals `5fc6be9dbe811df77e43d440ad087440e8bd57b5^{tree}`; non-tautological tree comparison exit `0`; actual proof interval ended `2026-08-21T02:14:14Z`. The corrected entry preserves qualified custody baselines, not false unchanged-state claims.
- **Recertification:** `G0-MUST-RECERT-001` and `G0-JR-RECERT-001` close through Grok adjudication result `2601675c5c389e9a25bbd657faf52f401ab9cd21819a08cdfdadfd1a88c31f38`; disposition `continue`, judgment `correct`.
- **Historical false latches:** T0.2's receipt captures `## JUDGMENT_REQUIRED`, but the adjudication receipt body says `JUDGMENT_REQUIRED: none` and continues; this is not an open judgment. The custody STOP wrapper latch is the known substring false-latch (`JUDGMENT_REQUIRED: none` inside `stop_or_judgment`); Grok's receipt-body adjudication is `correct`, not a new finding. Validator residual-heading and T0.4 historical-heading captures were adjudicated/re-reviewed and are closed. **Unresolved `JUDGMENT_REQUIRED`: none.**

### Custody controls, residual risk, and handoff

- **Protected-state checks:** `git rev-parse HEAD` before this evidence change was `ea3bf7a6a441763c17f6c3718cdf7de3d1cb58b4`; `test-shards.json` is byte-identical to that base; final-five data is preserved byte-for-byte. Receipts are read-only and unchanged. No product tests, full suite, live/model/runtime calls, secret access, push, merge, ref mutation, history rewrite, or network operation occurred.
- **Residual risks:** Docker is unavailable (`docker ps` exit `127`); `/workspace/omp-replaces-hermes` and structural-cleanup evidence lack comparable T0.0 baselines; current external health/path-list and Arnold state are qualified observations; pre-existing untracked evidence/status noise remains untouched. These are documented custody qualifications, not suppressed findings.
- **Rejected alternatives:** no new task IDs that would make `CARD_ORDER` reject the manifest; no `test-shards.json` mutation or fabricated live run; no receipt edits; no prior scratch-root reuse; no `HEAD^{tree}` tautological comparison; no textual-similarity substitution for tree identity; no exclusion of any tmux session other than the adjudicated supervisor-created `exec-spine-orchestrator`; no claim of unchanged state without a comparable baseline.
- **Next unblocked card:** `T1.1`.
## G1 / T1.1 — evidence-log T1.1 card sequence and disposition (2026-08-21)

- **Task/gate/label/role:** `T1.1` / `G1` / `evidence-log T1.1 card sequence and disposition` / `evidence`.
- **Model route:** `codex:gpt-5.6-luna` (`openai-codex/gpt-5.6-luna`).
- **Disposition/status:** complete. This is one canonical `T1.1` evidence entry after G0 and before `T1.2`; no `G1` completion record is created here.
- **Input/base:** implementation base `fbdd5596db7638d62f40def7b534012ebb1a7567`; reviewed/integrated target `4f38adb816effe9440fe3292193aff14bd7dff3d`.
- **Plan provenance:** plan SHA-256 `475c8480124e25cca7a5f1a1c1f2aad049499b670cd1b994d8d4feaae995a35e`; prior G0 evidence and receipts were read-only inputs.

### Ordered T1.1 sequence and receipt register

The following is the complete canonical card sequence. Existing receipts and
briefs are preserved unchanged. Receipt SHA-256 values are hashes of the
repository receipt files; `brief_sha256` and `result_sha256` are the wrapper
fields recorded in each receipt.

1. **Brief preparation — `t11-brief`.** Task `t11-brief`; gate unset in the
   receipt; label `T1.1 brief preparation (pre-code review + implementer)`;
   role `brief`; route `codex:gpt-5.6-luna`; receipt
   `receipts/t11-brief-receipt.json`, SHA-256
   `31ae7101172a08d488e378ee7cf77ee4b13466442def6ce83dec74cc65ef3391`;
   brief SHA-256
   `e5771f1bf2a1ee4f839087baf64c6802e39b6c88e48b48ceedc877da22b3e747`;
   result SHA-256
   `81fc7f29667e6734e6cf6c271d074a21e2117156f6887d018c47245035dbc0e1`;
   base `fbdd5596db7638d62f40def7b534012ebb1a7567`; PID `21101`;
   `2026-08-21T02:50:52Z` → `2026-08-21T02:56:53Z`; exit `0`; no
   commits/files.
2. **Pre-code review — `T1.1-precode-review`.** Task `T1.1-precode-review`;
   gate `G1`; label `G1 [XHARD-REVIEW] T1.1 immutable WorkflowSnapshot
   pre-code contract review`; role `reviewer`; route `grok-4.6`; receipt
   `receipts/T1.1-precode-review-receipt.json`, SHA-256
   `d77e790ca2cbde8591bd0af30a2f47a13147c3f21bc4ced996e80439e15f1249`;
   brief SHA-256
   `20997a372921847214050cb911de52929ca74ed79738bd8f7b26b7253b566181`;
   result SHA-256
   `919649f7fb4f650840c033e083df4fd48882de6e8d5b486a8824fa536cf4ebb9`;
   base `fbdd5596db7638d62f40def7b534012ebb1a7567`; PID `21228`;
   `2026-08-21T02:57:01Z` → `2026-08-21T03:13:01Z`; exit `0`;
   disposition `continue`; no commits/files.
3. **Original implementation attempt — `T1.1`.** Task `T1.1`; gate `G1`;
   label `T1.1 [XHARD] Immutable WorkflowSnapshot`; role `implementer`;
   route `grok-4.6`; receipt `receipts/T1.1-receipt.json`, SHA-256
   `1509c48d0db93737bcc25449ac92f419e42556ebed3be1d52f1e04d28fbe2494`;
   brief SHA-256
   `b7b2d3d1d300b7ffb2d5d326fec42a5a05c44455f0ebdb7220fd16d1a05c4c13`;
   result SHA-256
   `0261cad0b01f802811ca1a7ecf51989e63e15735c6ddc2bb12fec3d74f54f04c`;
   base `fbdd5596db7638d62f40def7b534012ebb1a7567`; PID `21429`;
   `2026-08-21T03:13:06Z` → `2026-08-21T03:20:36Z`; exit `0`; no
   commits/files. The preserved `T1.1-JR-PRECODE-RECEIPT-001` stop was the
   obsolete `g0/`-path precondition. It is not a card failure and this
   receipt is not deleted or edited.
4. **Rerun brief — `t11-rerun-brief`.** Task `t11-rerun-brief`; gate unset in
   the receipt; label `T1.1-rerun implementer brief preparation`; role
   `brief`; route `codex:gpt-5.6-luna`; receipt
   `receipts/t11-rerun-brief-receipt.json`, SHA-256
   `fcb2ba9def6af0977a846993a6f66e30f9b3e063ac3d622bd207636867b20dbf`;
   brief SHA-256
   `147a5b6a43b79cc2480a0529f958734fb4952895fe3345e91a857e139151441d`;
   result SHA-256
   `48199e43c76f1171be818d9528472e2588dd3c12621f44c7646ffc58f0d2c177`;
   base `fbdd5596db7638d62f40def7b534012ebb1a7567`; PID `21695`;
   `2026-08-21T03:21:28Z` → `2026-08-21T03:24:04Z`; exit `0`; no
   commits/files.
5. **Rerun implementation — non-receipted wrapper anomaly.** The canonical
   task remains `T1.1`; no top-level `T1.1-rerun` task is added. The fresh
   Grok `grok-4.6` implementer completed normally and authored commit
   `4f38adb816effe9440fe3292193aff14bd7dff3d` at
   `2026-08-21T04:08:39Z`. Its detached omp session exited at
   `2026-08-21T04:09:05Z`, but the wrapper died during the `03:42Z`
   supervisor relaunch teardown before writing a receipt. Wrapper PID,
   wrapper start timestamp, wrapper end timestamp, receipt SHA-256,
   brief SHA-256, result SHA-256, and wrapper exit are **unavailable**;
   they are not invented. The known launcher-side recovery fact is session
   identifier prefix `01a02258-…`, not a wrapper receipt substitute. This is
   an infrastructure anomaly, not a card failure.
6. **Verification brief — `T1.1-rerun-verify-brief-agent`.** Task
   `T1.1-rerun-verify-brief-agent`; gate unset in the receipt; label
   `T1.1 verification brief preparation (wrapper-recovery for preserved
   commit 4f38adb8)`; role `brief`; route `codex:gpt-5.6-luna`; receipt
   `receipts/T1.1-rerun-verify-brief-agent-receipt.json`, SHA-256
   `8397b7cada39c9ed811d785f97ce7fb63af566cc24c8c7d715ba91817b756549`;
   brief SHA-256
   `eec0b02717c83e79fa6466099c82ac921f571d803361cccac250a218662ac662`;
   result SHA-256
   `2fcd744f94bc28d51041b2be4aef85bf537de3c6cb657c7a91a97e26d1a16946`;
   base/target `4f38adb816effe9440fe3292193aff14bd7`; PID `22869`;
   `2026-08-21T04:48:40Z` → `2026-08-21T04:50:54Z`; exit `0`; no
   commits/files.
7. **Verification rerun — `T1.1-rerun-verify`.** Task
   `T1.1-rerun-verify`; gate unset in the receipt; label `T1.1 [XHARD]
   Immutable WorkflowSnapshot — verification re-dispatch of preserved
   commit 4f38adb8 (wrapper died before receipt)`; role `implementer`;
   route `grok-4.6`; receipt
   `receipts/T1.1-rerun-verify-receipt.json`, SHA-256
   `37546336afbd66e236820801b1b60bcdcabe892b1557bd101b78ab6eca7ca47f`;
   brief SHA-256
   `24c49c913466203f90cc81a188239458800035f92d874e33796bedcd73f6d8ec`;
   result SHA-256
   `3f85202159d17981a2da1ee15e2c6a043bd191aedc26c29db9158ae1da140d5c`;
   base/target `4f38adb816effe9440fe3292193aff14bd7`; PID `22970`;
   `2026-08-21T04:51:01Z` → `2026-08-21T05:01:31Z`; exit `0`; no
   commits/files. This regenerated machine-record and focused-test
   evidence for the preserved commit; it was not reimplementation or
   review.
8. **Review brief — `T1.1-review-brief-agent`.** Task
   `T1.1-review-brief-agent`; gate unset in the receipt; label `T1.1
   post-implementation review brief preparation (commit 4f38adb8)`; role
   `brief`; route `codex:gpt-5.6-luna`; receipt
   `receipts/T1.1-review-brief-agent-receipt.json`, SHA-256
   `b96774553b0abd3698329ebeec8218b974a13312b7bcaa7de17fb4e7ea80286d`;
   brief SHA-256
   `2d86ea8840eebd37929039379de8a3c0296a7aea28787143d51abd616498f6c1`;
   result SHA-256
   `da2b352c0bb77a291c968c1d091eb31ce375fd017c560527e27b665a58164f7d`;
   base/target `4f38adb816effe9440fe3292193aff14bd7dff3d`; PID `23191`;
   `2026-08-21T05:02:05Z` → `2026-08-21T05:03:53Z`; exit `0`; no
   commits/files.
9. **Independent post-code review — `T1.1-review`.** Task
   `T1.1-review`; gate unset in the receipt; label `T1.1 [XHARD-REVIEW]
   post-implementation review of preserved commit 4f38adb8 (Immutable
   WorkflowSnapshot)`; role `reviewer`; route `grok-4.6`; receipt
   `receipts/T1.1-review-receipt.json`, SHA-256
   `03ea2f8a1e163e6609d4324cd75b8d59c449f60d6bff05feb685d638cc559699`;
   brief SHA-256
   `c5a7e8698d24b977d85e587d0244a9736e9b13f3466acde493b0185b5d10b41e`;
   result SHA-256
   `5748dde6c69477cf3a57ad80606bf7cbd97730261cddab60a2ea5875609e9788`;
   base/target `4f38adb816effe9440fe3292193aff14bd7dff3d`; PID `23287`;
   `2026-08-21T05:04:00Z` → `2026-08-21T05:22:53Z`; exit `0`; no
   commits/files; disposition `continue`.
10. **Integration brief — `T1.1-integration-brief-agent`.** Task
    `T1.1-integration-brief-agent`; gate unset in the receipt; label
    `T1.1 integration brief preparation (commit 4f38adb8)`; role `brief`;
    route `codex:gpt-5.6-luna`; receipt
    `receipts/T1.1-integration-brief-agent-receipt.json`, SHA-256
    `241c2a514b5d48f93f12ff8f96b9b5931dcf4595a70c370dd171b5e1278c0f74`;
    brief SHA-256
    `f8b8bb35c56ee89653457c30c4620ff64b8bf045328ea2db16f1d1f2cbee4ca0`;
    result SHA-256
    `1d1da210258bce284e66dca0316aac3664d63f28483de8c7b774a5c3fb58fef1`;
    base/target `4f38adb816effe9440fe3292193aff14bd7dff3d`; PID `23607`;
    `2026-08-21T05:23:46Z` → `2026-08-21T05:25:49Z`; exit `0`; no
    commits/files.
11. **Integration — `T1.1-integration`.** Task `T1.1-integration`; gate
    unset in the receipt; label `T1.1 integration of reviewed commit
    4f38adb8 (Immutable WorkflowSnapshot)`; role `integration`; route
    `codex:gpt-5.6-luna`; receipt
    `receipts/T1.1-integration-receipt.json`, SHA-256
    `e205cfb9d0e57184349426cf2c707256aea71b2b80f9ac2586eec568c9c06459`;
    brief SHA-256
    `a93a5ee5b21dafd83df4508cbee525bdca8f2c6df593eb5e996e2e686abb64bc`;
    result SHA-256
    `6c08b3b7a5d3c9a45e4d5cca7c1d1ed1cd98637fbabbfdd730c1ed87cc4c4b5f`;
    base/target `4f38adb816effe9440fe3292193aff14bd7dff3d`; PID `23705`;
    `2026-08-21T05:25:56Z` → `2026-08-21T05:32:14Z`; exit `0`; no
    commits/files; applied `4f38adb8`; first branch push succeeded before
    this evidence card, and this evidence card does not push.
12. **Evidence brief — `evidence-log-T1.1-brief-agent`.** Task
    `evidence-log-T1.1-brief-agent`; gate unset in the receipt; label
    `T1.1 evidence brief preparation`; role `brief`; route
    `codex:gpt-5.6-luna`; receipt
    `receipts/evidence-log-T1.1-brief-agent-receipt.json`, SHA-256
    `8c40db5fe2eaa86540475d73f3ad68b2d62d903563b1eaece03a42d119b2105d`;
    brief SHA-256
    `980a869e12cf0f40346e1054c02c4d711dab51c08de9dfa12ba700e6b18f10b3`;
    result SHA-256
    `2c7a189616ab8cfcaa02ca3639e332b2d23489824382c5fe04485e619e6af2ce`;
    base/target `4f38adb816effe9440fe3292193aff14bd7dff3d`; PID `24250`;
    `2026-08-21T05:32:43Z` → `2026-08-21T05:38:53Z`; exit `0`; no
    commits/files. Evidence recording itself runs no product tests.

### Integrated implementation and focused evidence

The accepted implementation is commit
`4f38adb816effe9440fe3292193aff14bd7dff3d`, parent
`fbdd5596db7638d62f40def7b534012ebb1a7567`, authored by `POM
<peter@omalley.io>`, message `feat(exec-spine): freeze immutable
WorkflowSnapshot on ingest door`. The exact 13 changed files are:

- `tests/test_graph_inspection.py`
- `tests/test_ingest_snapshot.py`
- `tests/test_snapshot_api_workflows.py`
- `vibecomfy/comfy_nodes/agent/_frag_entrypoint.py`
- `vibecomfy/comfy_nodes/agent/_frag_ingest.py`
- `vibecomfy/comfy_nodes/agent/_frag_state.py`
- `vibecomfy/comfy_nodes/agent/_turn_state_machine.py`
- `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`
- `vibecomfy/comfy_nodes/agent/executor_durable.py`
- `vibecomfy/executor/graph_inspection.py`
- `vibecomfy/ingest/normalize.py`
- `vibecomfy/ingest/snapshot.py`
- `vibecomfy/porting/edit/session.py`

All 13 files are within the frozen 17-file allowance. Acceptance is the
reviewed immutable snapshot implementation: UI/API/`{prompt: API}` shape
detection occurs once; caller inputs are not mutated; one retained immutable
`WorkflowSnapshot` is semantic authority; canonical `VibeWorkflow`, source
representation/digest, semantic hash version, layout reference, raw sidecar,
stable identity/topology, and session/turn lineage are retained; canonical
JSON/hash behavior reuses existing primitives; model Python, inspection,
comparison, and replay consume the retained snapshot; and opaque/UI-only/
unknown-node data survives projection.

Authoritative focused evidence was read from disposable root
`/tmp/t11-integration-fsRm4h/` and was not regenerated:

- `metadata.txt`: Python `3.11.11` at
  `/root/.pyenv/versions/3.11.11/bin/python3`, pytest `9.1.1`,
  `2026-08-21T05:27:49Z` → `2026-08-21T05:29:27Z`, exit `1`;
  command `/root/.pyenv/shims/python3 -m pytest -q
  tests/test_ingest_snapshot.py tests/test_snapshot_api_workflows.py
  tests/test_ir_laws.py tests/test_graph_inspection.py`;
  command SHA-256
  `56529040a45f9c3438c164d75a6d68df6d10076ad5d196388103faf8618db3c3`;
  output SHA-256
  `a7bd04d5f2b8d89775641fb3c68ce54a7ab69dbb67d25d3daba9696200f5bf02`.
- `baseline-classification.txt`: baseline source
  `5fc6be9dbe811df77e43d440ad087440e8bd57b5`; baseline output SHA-256
  `d93f6f7bf90a9d53b223d0e308c9554674d15cf8e63ae292b017157bfaa52c93`;
  `6 failed, 173 passed, 1 xfailed`; six expected failures present, no
  unexpected failures; classification `baseline-equivalent/no introduced
  failures`.
- The six baseline failures are `test_snapshot_incoming_edge_sig_captured`,
  `test_snapshot_outgoing_edge_sig_captured`, law-3 `envelope`, law-3
  `definitions`, law-3 `unknown-schema`, and law-5
  `test_law_5_boundary_has_no_provisional_exceptions`. They are identical to
  the T0.0 baseline; zero were introduced. They are not relabelled as a T1.1
  failure and are not suppressed.
- `test-shards.json` was read and byte-compared unchanged:
  current and base SHA-256 are both
  `f0f1824368988de00857af70a58d7914c39f2a7914c9eba5840e76438d7cc3e3`.
  It was not edited.

### Residual-risk adjudication

The independent post-code review result
`5748dde6c69477cf3a57ad80606bf7cbd97730261cddab60a2ea5875609e9788`
returned disposition `continue`. It adjudicated all seven verifier-listed
items as residual risks, not open must findings:

1. `compare_snapshot_authority` remains test-only.
2. `_ensure_ingest_workflow` retains an empty-state fallthrough second-ingest door.
3. `inspect_graph` retains a raw-dict first-ingest path.
4. Durable replay does not invoke comparison against the persisted artifact.
5. `from_ui`/prompt-API has an intermediate api-snapshot overwrite.
6. Baseline edge-signature red tests remain.
7. Precode-continue envelope encoding remains.

There is no open must finding, no new `JUDGMENT_REQUIRED`, and no unresolved
judgment. The original pre-code false stop remains historical evidence only.

### Controls, rejected alternatives, and handoff

- No merge to `main`, no promotion, no live model/runtime/provider calls, no
  secret access, and protected state was untouched. No wrapper was run and no
  agent was dispatched by this evidence recording.
- No product tests or full suite were run by this evidence agent; the focused
  result above is authoritative integration evidence only.
- Rejected alternatives: rewriting prior log entries; adding top-level
  `T1.1-rerun`, `T1.1-rerun-verify`, or other non-canonical task IDs; editing
  any receipt; modifying `test-shards.json`; relabelling baseline failures;
  suppressing failures; inventing the dead wrapper PID/timestamps/digests;
  widening the 17-file allowance; running a live/model/runtime/provider call;
  accessing secrets or protected state; pushing from this evidence card; or
  marking `G1` complete.
- Exactly one canonical `T1.1` task record is inserted in the machine
  manifest. The evidence commit is authored as `POM
  <peter@omalley.io>`, has message prefix `docs(exec-spine):`, contains only
  the three allowance files, and is not pushed.
- **Next unblocked card:** `T1.2 [XHARD]`. Handoff is validator execution by
  the orchestrator, then dispatch of canonical `T1.2`.

### T1.1 wrapper-death recovery verification-3

This append-only recovery note records an infrastructure anomaly and the three
verification recovery attempts for the preserved evidence commit
`f86e6a2afd6e62d5d9113d642c9c66a8469e38b6`. It does not re-implement or
re-review T1.1, and it does not mark `G1` complete.

1. **Original wrapper-death anomaly — `evidence-log-T1.1`.** Wrapper PID
   `24373` started at `2026-08-21T05:39:01Z`. The child completed and
   committed `f86e6a2a` at `2026-08-21T05:47:21Z`, but the wrapper died before
   writing `evidence-log-T1.1-receipt.json`; the result body was not persisted.
   The allowance was released when `active-allowances.json` became `{}` at
   mtime `2026-08-21T05:48:32Z`; no receipt exists. This is an infrastructure
   anomaly, not a card failure.
2. **First verification recovery attempt — `evidence-log-T1.1-verify`.**
   Wrapper PID `24931`; interval
   `2026-08-21T05:54:17Z` → `2026-08-21T05:55:06Z`; exit `0`; result digest
   `8b1bf05d19386d76eb4e6a148a9bf9d24b126f9437d13a386383eea0620de1db`;
   `changed_files: []`; `commits: []`. It hard-stopped because its brief
   omitted the three known pre-existing dirty-state exceptions. This is a
   brief defect, not a card failure. Its receipt is preserved unchanged at
   `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-T1.1-verify-receipt.json`.
3. **Second verification recovery attempt — `evidence-log-T1.1-verify-2`.**
   Wrapper PID `25171`; interval
   `2026-08-21T05:59:46Z` → `2026-08-21T06:04:15Z`; exit `0`; base
   `f86e6a2a`; result digest
   `33f3903ec37abea56eba03869931a4e1147501d3d78305c0822fa9ed85b267ef`;
   `changed_files: []`; `commits: []`. It passed every verification gate but
   hard-stopped on the self-referential requirement to record its own receipt
   digest and end timestamp before wrapper exit. This is a brief defect, not a
   card failure. Its receipt is preserved unchanged at
   `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-T1.1-verify-2-receipt.json`.
4. **Third corrected verification dispatch — `evidence-log-T1.1-verify-3`.**
   The live registry entry records task ID
   `evidence-log-T1.1-verify-3`, wrapper PID `25455`, and wrapper start
   `2026-08-21T06:08:21Z`. Its receipt path is
   `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-T1.1-verify-3-receipt.json`.
   This note intentionally records no receipt digest, end timestamp, exit,
   final commit SHA, or other post-exit wrapper fact; the wrapper writes those
   after the child exits, and the next evidence agent records them.

Across this recovery sequence: no merge to `main`, no promotion, no live
model/runtime/provider calls, no secret access, and protected state was
untouched. The preserved receipts and prior evidence remain unchanged.
The next unblocked card remains `T1.2 [XHARD]`, after the orchestrator runs the
evidence validator. `JUDGMENT_REQUIRED`: none.

## G1 / T1.2 — evidence-log T1.2 card sequence and disposition (2026-08-21)

- **Task/gate/label/role:** `T1.2`; `G1`; `evidence-log T1.2 card sequence and disposition (Immutable SchemaSnapshot)`; `evidence`.
- **Required card disposition:** **T1.2 `[XHARD]` Immutable `SchemaSnapshot`: PASS**.
- **Model route:** `codex:gpt-5.6-luna` (`openai-codex/gpt-5.6-luna`) for brief preparation, integration brief/integration, and evidence; `grok-4.6` for the XHARD pre-code review, implementation, post-implementation review, revision, and independent re-review.
- **Input/output SHAs:** immutable implementation-chain base `8c67cf3c78059a3356136e3223750d921bb4b7d1`; original implementation commit `a109003ff32def89a7cae266e342764ce36562c9`; reviewed/revised/integrated target `0a8e55ff8d0a7412e750237e9623ba147bb152f2`. Plan SHA-256 is `475c8480124e25cca7a5f1a1c1f2aad049499b670cd1b994d8d4feaae995a35e`. The evidence commit is based on target `0a8e55ff`.
- **Card contract:** Freeze runtime/cache/request identity, content digest, precedence, generation, conflicts, timestamp/version, per-class schema, and missing classes at ingress. Precedence is explicit request snapshot, verified connected `/object_info`, then configured content-addressed cache. Workflow observation is non-authoritative. Replay cannot perform a fresh ambient lookup.

  Define `touched_schema_classes(operation, snapshot)` for field, add/remove, link/socket, mode, and layout operations. Unknown untouched nodes remain preserved. Any operation whose validity depends on unknown endpoint/node schema fails closed.

  Acceptance: isolated worktrees resolve proven TTS/Qwen schemas; LayerMask stays unsupported until exact pack schema is supplied; no positional alias becomes durable authority without a proven name.
- **G1 review contract:** one graph, one schema snapshot, lossless sidecar, touched-only blocking, and no ambient replay lookup.

### Ordered T1.2 sequence and receipt register

Receipt SHA-256 values below are hashes of the preserved repository receipt files. `brief_sha256` and `result_sha256` are the exact wrapper fields recorded in each receipt. No receipt was edited.

1. **Brief preparation — `T1.2-brief`.** Luna brief agent; role `brief`; route `codex:gpt-5.6-luna`; receipt `receipts/T1.2-brief-receipt.json`, SHA-256 `9315a45a0ea58d30990ee100cdceb63052c45af22db9f58b4ba83327d1554f6e`; brief digest `39546eaf473e4f2790d4677aa492024abe5e8ee06562f32acb0815cb5e950fbb`; result digest `b999605a3886ebd86367d050f47ad52ec18099336d1e4a44830f67d3b1f1e0ba`; base `8c67cf3c78059a3356136e3223750d921bb4b7d1`; wrapper PID `25737`; `2026-08-21T06:15:32Z` → `2026-08-21T06:20:36Z`; exit `0`; no commits or changed files. It produced the pre-code and implementer briefs.
2. **Fresh pre-code contract review — `T1.2-precode-review`.** Grok `grok-4.6`; role `reviewer`; receipt `receipts/T1.2-precode-review-receipt.json`, SHA-256 `1054f6b9e7cb027833a72b02182073d487c1ee7cb4c665a3726007de1a423844`; brief digest `7c5edf0e237ba7aff6fc9668eaa22e75eebec03d78b91d69f2ea08dd1e800113`; result digest `45eaaa99f4a6e185233192611f7d142d60d6178fa383188581f0afdc8483c223`; base `8c67cf3c78059a3356136e3223750d921bb4b7d1`; wrapper PID `26320`; `2026-08-21T06:35:28Z` → `2026-08-21T06:45:49Z`; exit `0`; disposition `continue`; no commits or changed files. Its historical T0.2/G0 `JUDGMENT_REQUIRED` strings are closed false latches, not a T1.2 card judgment.
3. **Original implementation — `T1.2`.** Grok `[XHARD]`; role `implementer`; receipt `receipts/T1.2-receipt.json`, SHA-256 `cfa3fc7ec4db632384245bb2a96ee521f3fe299d6c3147dada279da10b37435e`; brief digest `f724436124cad11bb82dabbfa94f8d5450185d040c80235483d89ae66fa3a340`; result digest `8583745400ed26156962d549dfc482aba1be5e44239e419d24d0b43bb3f90a2f`; base `8c67cf3c78059a3356136e3223750d921bb4b7d1`; wrapper PID `26491`; `2026-08-21T06:46:01Z` → `2026-08-21T07:18:11Z`; exit `0`; commit `a109003ff32def89a7cae266e342764ce36562c9` (`feat(exec-spine): freeze immutable SchemaSnapshot at ingress`). Changed files were exactly:
   - `tests/test_schema.py`
   - `vibecomfy/comfy_nodes/agent/candidate_transaction.py`
   - `vibecomfy/porting/edit/ops.py`
   - `vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json`
   - `vibecomfy/schema/__init__.py`
   - `vibecomfy/schema/cache.py`
   - `vibecomfy/schema/provider.py`
   - `vibecomfy/schema/types.py`
   
   The receipt's `### JUDGMENT_REQUIRED` heading is a result-body heading false latch, not a card-level judgment.
4. **Post-implementation review brief — `T1.2-review-brief-agent`.** Luna brief agent; role `brief`; route `codex:gpt-5.6-luna`; receipt `receipts/T1.2-review-brief-agent-receipt.json`, SHA-256 `ef1417c7ff89d0a7ed6ebf2679bf72e084a550d040d319af6894e8a3254c08c0`; brief digest `4c89b9e4f60124a23cb71ed294e251d55f9fce7c420b1d263b1f548f89186d15`; result digest `af7f2f6daee8d23ae2acbeba2d71330d44e813a05db34c569b3d6c025180d2da`; base/target `a109003ff32def89a7cae266e342764ce36562c9`; wrapper PID `26964`; `2026-08-21T07:18:55Z` → `2026-08-21T07:21:03Z`; exit `0`; no commits or changed files.
5. **Independent post-implementation review — `T1.2-review`.** Fresh Grok `grok-4.6`; role `reviewer`; receipt `receipts/T1.2-review-receipt.json`, SHA-256 `24a0b867cd1b379154f6343610d138e0fe7b2db4cd3455acec647a4b650696d0`; brief digest `35c2f8648d046194d8f8bf68ce3079cb5de0d0fa5cada89b7a132f887674ad8c`; result digest `51d80ab50d81b27d7715a8d5697a54244ee296b33aba17787b94aa4b796a060c`; base/target `a109003ff32def89a7cae266e342764ce36562c9`; wrapper PID `27062`; `2026-08-21T07:21:12Z` → `2026-08-21T07:45:39Z`; exit `0`; no commits or changed files. It found exactly two must findings: `T1.2-MUST-001` (production-shaped UID identities were not resolved to catalog classes and layout identities were omitted from touched-schema closure) and `T1.2-MUST-002` (the immutable witness snapshot was not hash-bound/consistently validated and provider authority could prefer an unbound snapshot).
6. **Revision brief — `T1.2-revision-brief-agent`.** Luna brief agent; role `brief`; route `codex:gpt-5.6-luna`; receipt `receipts/T1.2-revision-brief-agent-receipt.json`, SHA-256 `ce51e014f33c8b9a1143cd9787722c4e61b7512b848af4f490411adaf2f06496`; brief digest `7603ec4e36f847d72bbeb78877767846db63313bcd2ff3a74f2d7dea8c84cc86`; result digest `5dafcc6fb296255f65faaeb47d725c5bfa7bae8a48d6ee74c8f84cb2fe4752ed`; base `a109003ff32def89a7cae266e342764ce36562c9`; wrapper PID `27385`; `2026-08-21T07:46:12Z` → `2026-08-21T07:49:13Z`; exit `0`; no commits or changed files.
7. **Revision — `T1.2-revision`.** Grok `[XHARD-REVISION]`; role `implementer`; receipt `receipts/T1.2-revision-receipt.json`, SHA-256 `f01ceb906c832287f1d39e045facbf09e01fbb08a23c6b1f6006e23deac5baec`; brief digest `2932f844ee0b370c1b92f8dda40ca281d73252ca7e91b00493daa669a15e0a20`; result digest `7d6251fafb5ae0c3dc3d126c615e1eddd2c0cae0138aab16d8e2b928f598f353`; base `a109003ff32def89a7cae266e342764ce36562c9`; wrapper PID `27487`; `2026-08-21T07:49:21Z` → `2026-08-21T08:29:10Z`; exit `0`; commit `0a8e55ff8d0a7412e750237e9623ba147bb152f2` (`fix(exec-spine): bind uid-class schema closure and hashed snapshots`). Changed files were exactly:
   - `tests/test_schema.py`
   - `vibecomfy/comfy_nodes/agent/candidate_transaction.py`
   - `vibecomfy/porting/edit/ops.py`
   - `vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json`
   - `vibecomfy/schema/types.py`
   
   The `## 7. Residual risks / JUDGMENT_REQUIRED` section heading is a false latch, not a card-level judgment.
8. **Re-review brief — `T1.2-rereview-brief-agent`.** Luna brief agent; role `brief`; route `codex:gpt-5.6-luna`; receipt `receipts/T1.2-rereview-brief-agent-receipt.json`, SHA-256 `10a3c68099ea3d3ad5b79b299df1f6a81e27c8e13d8fa10513afe2f30f5e0c82`; brief digest `17117dfd3d1c75988c65706ba985e649acecd9fc64b441b1132226759f03af33`; result digest `5e8d6838fc0cca1824dfa65968ce9e5936ea83fdc3e5a5890cbc3a9521e9c5c1`; base `0a8e55ff8d0a7412e750237e9623ba147bb152f2`; wrapper PID `27927`; `2026-08-21T08:29:36Z` → `2026-08-21T08:31:58Z`; exit `0`; no commits or changed files.
9. **Prominent wrapper-death anomaly during re-review dispatch.** `receipts/wrapper-death-note-t12-rereview.json`, SHA-256 `de6545e38203a27d3b00d315c22252f5aae38f7ec51cad6ede35b7201f08e8dc`, records the first `T1.2-revision-rereview` wrapper PID `28014`, started `2026-08-21T08:32:01Z`, exited `2026-08-21T08:44:38Z` after `12m37s`, and wrote **no receipt**. The supervisor session was recreated at `2026-08-21T08:32:13Z`; no review result existed. The fresh wrapper-routed dispatch below is the same permitted re-review phase, not an additional review tier. No receipt digest, result digest, exit disposition, or other unavailable wrapper end-state is invented for PID `28014`. This is an infrastructure anomaly, not a card failure.
10. **Fresh independent complete-diff re-review — `T1.2-revision-rereview`.** Grok `grok-4.6`; role `reviewer`; receipt `receipts/T1.2-revision-rereview-receipt.json`, SHA-256 `a7c73b823ebdbbc1d5496bf0b16fe231e0a02c15c61adb668107e04c51ae75ef`; brief digest `8d76c6c813773071cee42c5038f98fd4b30d113688d258e73d4bf54d69622131`; result digest `cc41d00f3c0ae249567699d3c84296bfb743cf74c457dc4305b453bb351b9965`; base/target `0a8e55ff8d0a7412e750237e9623ba147bb152f2`; wrapper PID `28408`; `2026-08-21T08:45:29Z` → `2026-08-21T09:00:24Z`; exit `0`; no commits or changed files; disposition `continue`; `JUDGMENT_REQUIRED: none`. It reviewed complete diff `8c67cf3c..0a8e55ff`, closed both must findings, found no new must findings, and verified touched closure, fail-closed error, all ingress/receipt paths, production-shaped UID proof, snapshot hash binding, validation consistency, historic four-field compatibility, and removal of the unused receipt-root `schema_snapshot` property. The re-review-focused shard ran once separately before integration: `147 passed, 3 warnings in 0.88s`, exit `0`, disposable root `/tmp/t12-rereview-focused-hvwb7cn1`, output digest `6c694cc511d6232d8249e7299a32c7dddccbf6dde9deb3738c50ba96c2fec4d1`.
11. **Integration brief — `T1.2-integration-brief-agent`.** Luna brief agent; role `brief`; route `codex:gpt-5.6-luna`; receipt `receipts/T1.2-integration-brief-agent-receipt.json`, SHA-256 `b1e0dfd2fed25c41a40f74bb4e82eb8d7251c9d55bec0b44db60afca7e47b24a`; brief digest `eea7d6821f9e8529c024823ccc3d86ccdcd8e480ec8806921ac2df9b270eb044`; result digest `bdc32a9392fdf965aeca5e37f23227fd517af0330e34b22bcbc5e316bd9a69e3`; base `0a8e55ff8d0a7412e750237e9623ba147bb152f2`; wrapper PID `28727`; `2026-08-21T09:01:39Z` → `2026-08-21T09:03:29Z`; exit `0`; no commits or changed files. It produced `g0/t12-integration.md`, digest `7719384e2473908367bdd3d92d5d0ca33fd8fab42b5909522af5fdb526e6298c`, and `g0/t12-integration-allowance.json`, digest `e4ca7ce23860ee9290a465f4c176b63e478edd1bae962beba16570d68e7b4115`.
12. **Integration — `T1.2-integration`.** Luna integration agent; role `integration`; route `codex:gpt-5.6-luna`; receipt `receipts/T1.2-integration-receipt.json`, SHA-256 `a2cfa3e2f595c65f1c24fe925e85b6bcd603bc7c990d53fb0b1d6f92dcbe4fb8`; brief digest `7719384e2473908367bdd3d92d5d0ca33fd8fab42b5909522af5fdb526e6298c`; result digest `f2d32e6b57a0e42d3f2adea3a33e9d90e565bd96b3a263ee9efa6a1949a64139`; base/applied HEAD/target `0a8e55ff8d0a7412e750237e9623ba147bb152f2`; wrapper PID `28820`; `2026-08-21T09:03:35Z` → `2026-08-21T09:06:05Z`; exit `0`; no repository mutations and no commit created by integration. The focused shard ran once in fresh disposable root `/tmp/t12-integration-focused-vb3bca3z`: `147 passed, 3 warnings in 0.93s`, exit `0`, output digest `6de9720460744313f8c8e8aebe95c591a44e7f93fc55c44a348946e73c55b00a`. The second explicit-refspec branch push exited `0`, fast-forwarded `4f38adb816effe9440fe3292193aff14bd7dff3d -> 0a8e55ff8d0a7412e750237e9623ba147bb152f2`, and remote verification was recorded at `2026-08-21T09:05:38Z`. This evidence card did not push.

### Findings, revision chains, and residual-risk adjudication

- **`T1.2-MUST-001` — closed.** Severity `must`; classification `XHARD`; status/disposition `closed`. The review found that production-shaped UID identities were not resolved to catalog classes and layout identities were omitted from closure. Revision task `T1.2-revision` (`0a8e55ff`) uses identity extraction/class-map lookup and fail-closed `missing_touched_schema`; complete-diff independent re-review task `T1.2-revision-rereview` closed the finding. Revision receipt is `receipts/T1.2-revision-receipt.json` (SHA-256 `f01ceb906c832287f1d39e045facbf09e01fbb08a23c6b1f6006e23deac5baec`, result `7d6251fafb5ae0c3dc3d126c615e1eddd2c0cae0138aab16d8e2b928f598f353`); closing receipt is `receipts/T1.2-revision-rereview-receipt.json` (SHA-256 `a7c73b823ebdbbc1d5496bf0b16fe231e0a02c15c61adb668107e04c51ae75ef`, result `cc41d00f3c0ae249567699d3c84296bfb743cf74c457dc4305b453bb351b9965`). The initial review receipt is `receipts/T1.2-review-receipt.json` (SHA-256 `24a0b867cd1b379154f6343610d138e0fe7b2db4cd3455acec647a4b650696d0`, result `51d80ab50d81b27d7715a8d5697a54244ee296b33aba17787b94aa4b796a060c`).
- **`T1.2-MUST-002` — closed.** Severity `must`; classification `XHARD`; status/disposition `closed`. The review found that the witness snapshot was not included in the content hash and validation/provider authority were inconsistent. Revision binds `schema_snapshot` into `content_hash`, validates mismatch as `invalid_schema_snapshot`, preserves historic `schema_snapshot is None` compatibility, and removes the unused receipt-root property; complete-diff independent re-review closed the finding. Revision and closing receipt details are the same `T1.2-revision` and `T1.2-revision-rereview` receipts above. No must finding remains open.
- **False-latch adjudication:** the implementation `### JUDGMENT_REQUIRED` and revision `## 7. Residual risks / JUDGMENT_REQUIRED` headings are result-body headings, not card-level judgments. The successful independent re-review explicitly records `JUDGMENT_REQUIRED: none`.
- **Residual risk:** LayerMask remains unsupported until its exact pack schema is supplied; unknown touched schema remains fail-closed. This is the required contract, not a hidden pass.

### Controls, rejected alternatives, and handoff

- No merge to `main`, no promotion, no live model/runtime/provider calls, no secret access, and protected state was untouched. The evidence agent did not run the product shard, full suite, wrapper, another agent, or a push.
- `test-shards.json` was read and byte-compared unchanged at SHA-256 `f0f1824368988de00857af70a58d7914c39f2a7914c9eba5840e76438d7cc3e3`; it was not edited or staged.
- Rejected alternatives/failure proofs: accepting UID strings as catalog classes; omitting layout endpoints from closure; allowing unknown touched schema to proceed; trusting an unbound witness snapshot; validating only mapping presence; preferring an unbound snapshot over hashed `schemas`; treating the receipt-root `schema_snapshot` as authority; treating either result-heading latch as a card judgment; counting PID `28014` recovery as a second review; inventing unavailable receipt fields; changing the shard; or modifying the prior T1.1 entry. The correct response to any inconsistency is stop/fix the evidence, not hide it or widen the allowance.
- Exactly one canonical top-level `T1.2` task record is added to the machine manifest. Recovery/review phase IDs remain nested receipt/anomaly fields; no `G1` completion record and no non-canonical top-level task record is added.
- The evidence commit is one coherent commit authored as `POM <peter@omalley.io>` with message prefix `docs(exec-spine):`; it contains only this execution-log append and the manifest update, and is not pushed. No receipt, brief/allowance artifact, source, test, fixture, generated file, protected path, or other evidence-root file is changed.
- **Card disposition:** **T1.2 `[XHARD]` Immutable `SchemaSnapshot`: PASS**. **Next unblocked card:** `G1 [XHARD-REVIEW]`. `G1` is not marked complete.
- `JUDGMENT_REQUIRED`: none open.
 
### T1.2 validator-repair continuation and recovery digest finish (2026-08-21)

This append-only continuation completes the already-recorded `T1.2` evidence
chain. It does not add another `T1.2` entry, a `G1` completion record, or any
non-canonical top-level task ID.

1. **Blocked evidence disposition — `evidence-log-T1.2`.** The preserved
   receipt is `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-T1.2-receipt.json`,
   SHA-256
   `c83e86dbeac453e2c2a0da4f2e64e32bebdc9a6a9aba1a042b7675bcc5af78f1`.
   Its base was `0a8e55ff8d0a7412e750237e9623ba147bb152f2`; wrapper PID
   `29228`; interval `2026-08-21T09:11:14Z` → `2026-08-21T09:19:16Z`;
   exit `0`; result SHA-256
   `dd1c76a611bce542201dcf9b15d5ad352fa00b7b362e129fd9f669435d7a82ba`;
   changed files were exactly the manifest and this execution log; commits
   were `[]`. It stopped on the validator `NameError: _find_task`; this was
   an evidence-owned validator gap, not a product or T1.2 disposition change.

2. **Validator repair — `T1.2-validator-repair`.** The accepted receipt is
   `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/T1.2-validator-repair-receipt.json`,
   SHA-256
   `53822f4498c754fdb526582b36e7564f48c82ae4a441fc8246e27b95da96ad62`.
   The repair was based on `0a8e55ff8d0a7412e750237e9623ba147bb152f2`,
   committed as `1d8088423030700a4e54bc20608d62e53df7da56`; Grok PID `29798`;
   interval `2026-08-21T09:25:21Z` → `2026-08-21T09:58:16Z`; exit `0`;
   result SHA-256
   `bad768f5196384320ea1b1fc4e82f620acc1e25d4d2ef1e7d595853fe01ae690`;
   changed files were exactly
   `scripts/validate_workflow_execution_spine_evidence.py`; no other file
   was changed. The repair fixed the `_find_task`/embedded-receipt
   finding-chain path. The validator itself remains read-only for this finish.

3. **Independent repair review — `T1.2-validator-repair-review`.** The
   accepted receipt is
   `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/T1.2-validator-repair-review-receipt.json`,
   SHA-256
   `9174f42feacadd450eca2a8139cfed63762d4b3118c4413761fb2a57da534f92`;
   base `1d8088423030700a4e54bc20608d62e53df7da56`; Grok reviewer PID
   `30627`; interval `2026-08-21T10:04:11Z` → `2026-08-21T10:15:11Z`;
   exit `0`; result SHA-256
   `9ee239d42257651f7f981f513dacff8620229d9f07bdf6e434c53864124e9256`;
   disposition `continue`; zero must findings; no changed files or commits;
   `JUDGMENT_REQUIRED: none`. The review accepted the deterministic,
   non-spoofable reviewer-identity fallback, the production
   `sys._getframe(1)` path, and the evidence-owned artifact-digest mismatch
   pending this continuation. No historical false-latch heading is a new
   judgment.

4. **Finish-card dispatch custody.** The active allowance registry recorded
   PID `31126`, start `2026-08-21T10:20:32Z`, and this card's expected receipt
   path
   `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-T1.2-finish-brief-agent-receipt.json`.
   No post-exit receipt digest or end timestamp is recorded here because those
   wrapper facts are unavailable before exit.

The only pre-finish validator failure after the repair was the
evidence-owned `ARTIFACT_DIGEST` mismatch: current execution-log digest
`f79d0fd44160e98abf6e49b398816c58a1845267d3cfe7e160a9e8b080036ec9` versus
stale `tasks[5].recovery_note.sha256`
`d1566ea306cfaca2d46e282074f5987ae6be7516e14d387b6d667ced4be106aa`.
The final recovery-note digest is assigned in the manifest only after this
append. The T1.2 residual risk remains unchanged: LayerMask is unsupported
until its exact pack schema is supplied, and unknown touched schema remains
fail-closed.

No product tests, full suite, live/model/runtime/provider calls, secret
access, or protected-state access occurred. No push, merge to `main`, or
promotion occurred. `JUDGMENT_REQUIRED`: none.

### T1.2 post-repair integration recovery and adjudication finish (2026-08-21)

- **Task/gate/dispositions:** `T1.2-post-repair-integration` / `G1`
  completed in the original child; its wrapper death is the fifth `F1`
  wrapper-survival occurrence and is classified as an infrastructure anomaly,
  not a card failure. The recovery re-dispatch completed no work because the
  remote already matched the local head and correctly returned a genuine
  `JUDGMENT_REQUIRED`; that stop is closed by the adjudication. The
  `T1.2-integration-adjudication` disposition is **SATISFIED**. This
  `evidence-log-T1.2-repair-finish` append records those dispositions; no
  T1.2 product finding or revision remains open.
- **Original-child proof:** The durable pinned proof is
  `receipts/t12-post-repair-integration-original-child-proof.json`
  (SHA-256
  `ff9a62101ee141d37571448e49ca7ad76d6e2847fae01010629f874cad3258a2`).
  The codex child invoked the validator exactly once at
  `2026-08-21T10:30:52Z`, exit `0`, with stdout
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  and stdout digest
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  It then pushed the genuine fast-forward
  `0a8e55ff..9a64b35b`; remote verification completed at
  `2026-08-21T10:32:09Z`. The child changed no files and created no commit.
- **Original wrapper-death anomaly:** The wrapper for
  `T1.2-post-repair-integration` was PID `31443`, started
  `2026-08-21T10:28:20Z`, and died at approximately
  `2026-08-21T10:33:10Z` before writing a receipt. Receipt
  `receipts/wrapper-death-note-t12-post-repair-integration.json` is pinned
  with SHA-256
  `ed8a62e5437625354d60df57c9b6cdb4a9f427d27749ecd690bc395ad4268799`.
  Registry state was clean at observation; the child work had already landed.
  This is `F1` infrastructure evidence, not a failed T1.2 card; `H1` remains
  the fix.
- **Recovery re-dispatch:** `T1.2-post-repair-integration` used
  `codex:gpt-5.6-luna`, wrapper PID `31866` (child `31860`), interval
  `2026-08-21T10:34:44Z` → `2026-08-21T10:38:00Z`, exit `0`; receipt
  `receipts/T1.2-post-repair-integration-receipt.json`, SHA-256
  `4f2af18973686af46113dc701d4cd5368aee6cd1c0ee450984451931620cbef1`,
  brief digest
  `e04e9b4bed31f01de204fa293addda22effa75176e86bc473ef4fda7a3a48b9e`,
  result digest
  `36bd962e5f3dccff1d3d1a5c8ea82550c4eba13f013f27116f365e79d039230e`.
  It found remote `9a64b35b` already equal to local `9a64b35b`, so it
  performed no push, no validator invocation, no commit, and no file change.
  The genuine `JUDGMENT_REQUIRED` is preserved in the pinned original-child
  proof's `preflight_failure` record and is not an open integration failure.
- **Grok adjudication:** `T1.2-integration-adjudication` used `grok-4.6`,
  wrapper PID `32081`, interval `2026-08-21T10:38:52Z` →
  `2026-08-21T10:42:43Z`, exit `0`; receipt
  `receipts/T1.2-integration-adjudication-receipt.json`, SHA-256
  `af70776336b1e9be3681af20163d5ab44745af1379da73e1e5b9934fe8c7a666`,
  brief digest
  `33e5e62bb3ef7e7fee6e9ca15d81b10c30af743c611565019bb973d31cfde07a`,
  result digest
  `4eae20d2b0e9ad7d32c48bed465734f4d0f7abfced3cc3380e62201754e23ba5`.
  Result body line 1 is **SATISFIED**: T1.2 integration is complete at
  `9a64b35bd1e49a9f0dd59009bbdf5e7153ed296e`. It required no corrective
  push, validator re-run, or re-dispatch.
- **§15 stop-marker policy:** Record the genuine recovery
  `JUDGMENT_REQUIRED` and the adjudication's **SATISFIED** decision. The
  receipt `stop_or_judgment` fields are old-wrapper substring latches, not
  judgments, and are not used as dispositions.
- **Current batch evidence:** The orchestrator's validator invocation at
  `2026-08-21T10:44Z` exited `0` with
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`.
  No product tests, full suite, or other test runs occurred; no validator
  change was made in this evidence finish.
- **Input/output SHAs:** `9a64b35bd1e49a9f0dd59009bbdf5e7153ed296e` in;
  `9a64b35bd1e49a9f0dd59009bbdf5e7153ed296e` out. The manifest now records
  this integration SHA in both nested `target_sha` fields and nests the four
  post-repair receipt records using the existing receipt array schema.
- **Commit/files:** one coherent evidence commit, authored by
  `POM <peter@omalley.io>` with message prefix `docs(exec-spine):`; its
  changed files are exactly the execution log and manifest below, both within
  the three-file allowance:
  `docs/plans/workflow-execution-spine-consolidation-execution-log-2026-08-20.md`
  and
  `docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`.
  The third allowed file,
  `docs/plans/workflow-execution-spine-consolidation-evidence/test-shards.json`,
  remains byte-identical and is not edited or staged. No receipt is committed.
- **Findings/revisions and controls:** No T1.2 finding remains open. The
  wrapper-death is `F1` infrastructure risk; `H1` is pending. No protected
  state, source, validator, test, receipt, or other branch was changed; no
  merge to `main`, promotion, push, live/model/runtime call, or secret access
  occurred in this evidence finish.
- **Residual risks / handoff:** `F1` wrapper-survival remains open;
  `G1 [XHARD-REVIEW]` remains pending; the original-child proof is now pinned
  under the evidence receipts directory. Next unblocked card:
  `H1-wrapper-survival-stop-marker-precode-review`.

### G1 / T1.2 digest-repair chain and adjudication close (2026-08-21)

- **Task/gate/label/role:** `evidence-log-T1.2-digest-repair` / `G1` /
  `evidence-log T1.2 digest-repair chain: repair, review findings,
  adjudication A, integration, recurrence rule` / evidence.
- **Disposition:** **A. CLOSE-AND-TRACK**. The digest-repair card integrates
  as-is. The review's two findings are recorded below; finding 1 remains a
  tracked pre-existing validator gap, and finding 2 is satisfied by this
  disposition's recurrence rule and finding record.
- **Input/base and integrated commit:** `d1aa492921fc5f3aee2b2ef3efc275aedbbc2226`;
  the digest-repair implementation commit is `d1aa492921fc5f3aee2b2ef3efc275aedbbc2226`.
- **Model routes:** Luna (`codex:gpt-5.6-luna`, resolved
  `openai-codex/gpt-5.6-luna`) for implementer, reviewer, and integration;
  Grok (`grok-4.6`) for adjudication. Wrapper argv, PID, timestamps, and
  exits below are authoritative from the preserved receipts.

#### Ordered digest-repair receipt register

1. **Repair — `T1.2-evidence-digest-repair` (implementer, Luna).** Receipt
   `receipts/T1.2-evidence-digest-repair-receipt.json`, SHA-256
   `7a20d0056735f8b3ea6153a9812938c0032cec18ac711b060e43ea34996f301a`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T1.2-evidence-digest-repair.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `32560`; `2026-08-21T10:51:05Z` → `2026-08-21T10:53:06Z`;
   exit `0`; brief SHA-256
   `7f575ee6a3dd8f60ea3911fb7b5830f47d6e8562ba7000e11130709b2a9a1746`;
   result SHA-256
   `2b3968f82d921578b69a9ab7a6896cb4398b49b9ccab84edc62dcfb3bec901cb`.
   It refreshed `tasks[5].recovery_note.sha256` from `50263ce0…` to
   `d71d7935…`, changed only `manifest.json`, committed
   `d1aa492921fc5f3aee2b2ef3efc275aedbbc2226`, and its validator exited `0`.
2. **Review — `T1.2-evidence-digest-repair-review` (reviewer, Luna).** Receipt
   `receipts/T1.2-evidence-digest-repair-review-receipt.json`, SHA-256
   `c809190676e552178f2ff20f4a59fe9f2cd5a4dccf1ca76e99a2407ecf2fd167`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T1.2-evidence-digest-repair-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `32723`; `2026-08-21T10:53:32Z` → `2026-08-21T10:56:22Z`;
   exit `0`; brief SHA-256
   `b6c7f00760a7f2435aef2380076e6a6da59f9ed33abaf34e7d1ee3012c3c7d6b`;
   result SHA-256
   `687869a7e879f957df009e7e4db0b1a197058e4b9286d03a872976b7db4ee4b2`.
   The repair itself was confirmed correct by an independent digest check and
   minimal diff; the review recorded `JUDGMENT_REQUIRED:` with two findings:
   (1) pre-existing validator gap: `_iter_digest_refs` /
   `check_artifact_digests` (approximately validator lines 256–276) silently
   skips a string `path` paired with malformed, non-64-hex `sha256`/`digest`;
   (2) the repair receipt lacked a `residual_risks` entry containing the
   recurrence rule. Author verification was `POM <peter@omalley.io>` and the
   one-commit chain was confirmed.
3. **Adjudication — `T1.2-evidence-digest-repair-adjudication`
   (adjudication, Grok).** Receipt
   `receipts/T1.2-evidence-digest-repair-adjudication-receipt.json`, SHA-256
   `dbd15895e496eafdca530b890675b43f039eb8800eb365d7946e46123ef93861`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T1.2-evidence-digest-repair-adjudication.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `32858`; `2026-08-21T10:56:57Z` → `2026-08-21T10:59:39Z`;
   exit `0`; brief SHA-256
   `6ba13e21d451f6d4d469b0d58a44326134402ee59db6eb83ddb85822158710eb`;
   result SHA-256
   `08040d3ae232f1d6e7be72b35d3f7a6c7cde3c3d16257e8459daea4aa19411d3`.
   Decision **A. CLOSE-AND-TRACK**: integrate the repair as-is; track finding
   1 as the pre-existing validator gap; satisfy finding 2 by recording both
   findings and the recurrence rule in this evidence disposition.
4. **Integration — `T1.2-evidence-digest-repair-integration` (integration,
   Luna).** Receipt
   `receipts/T1.2-evidence-digest-repair-integration-receipt.json`, SHA-256
   `fb09914933ee1d122ace7acbed7d6fc67ced799eafe0ae52e3b5f5c28accbe96`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T1.2-evidence-digest-repair-integration.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `32962`; `2026-08-21T11:00:06Z` → `2026-08-21T11:02:52Z`;
   exit `0`; brief SHA-256
   `55ac29511046dd44635a4841400cef4e9d39439fb9be43859a0a015334fcdcf6`;
   result SHA-256
   `fde50d9309e2f0e6b35e3483be590dd8c386550483e8286455857e2fdd5c69a6`.
   Integration verified fast-forward push `9a64b35b..d1aa4929` via
   `git push origin HEAD:fixer/workflow-execution-spine-consolidation`;
   remote and local both verified at `d1aa4929`. The integration receipt
   changed no files and created no commit.

- **Tests/evidence:** the orchestrator's post-batch validator invocation at
  `2026-08-21T11:03Z` exited `0`. No other tests were run; no validator or
  implementation change was made in this evidence disposition.
- **Changed files and commit controls:** the digest-repair chain itself
  changed only `manifest.json`; review, adjudication, and integration changed
  no files. This evidence append is one coherent commit authored by
  `POM <peter@omalley.io>`, with message prefix `docs(exec-spine):`, and
  contains exactly the three allowed files: this execution log,
  `evidence/manifest.json`, and `evidence/test-shards.json`. No receipt is
  committed.
- **Residual risks / recurrence rule:** every future append to this execution
  log changes its digest; every evidence agent that appends MUST refresh
  `manifest.tasks[5].recovery_note.sha256` to the new log digest, as enforced
  by the validator. Finding 1 remains a pre-existing validator gap:
  `_iter_digest_refs` silently skips malformed (non-64-hex) digest strings
  paired with a path, so such a reference passes unchecked. It is tracked per
  adjudication A as a candidate future XHARD validator-hardening card and does
  not block G1.
- **Controls:** no product tests, full suite, live/model/runtime/provider
  calls, secret access, protected-state access, merge to `main`, promotion, or
  push occurred in this evidence append. The earlier integration push is
  recorded above as prior-card evidence. No branch other than the current
  branch was changed.
- **Next unblocked card:** `H1-wrapper-survival-stop-marker-precode-review`.

### G1 / T1.2 evidence-log shards-digest-repair revision (2026-08-21)

- **Task/gate/label/role:** `evidence-log-T1.2-shards-digest-repair` / `G1` /
  `evidence-log T1.2 shards-digest-repair chain + MUST-001 recurrence-rule
  recording (revision)` / evidence.
- **Disposition:** The shards digest-repair chain is recorded as **PASS**.
  The repair receipt's refreshed pins were independently confirmed correct.
  The review's `T1.2-MUST-001` is closed by this revision: the test-shards
  recurrence rule is now durably recorded in this evidence disposition and the
  execution log. The pre-authorized Grok adjudication path is
  `receipts/T1.2-evidence-digest-repair-adjudication-receipt.json`: receipts
  remain wrapper-written and immutable; the durable recording path is this
  evidence disposition.
- **Input/base and repair commit:** the shards repair was based on
  `27e65c47acf2dddfebf863ba5d17ae94eaef399b`, committed as
  `16990debf038379ace30b6b6d18dc91c66a7ba58`, and changed only
  `docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`.
  The current recording is the authorized revision on that commit.
- **Model route:** Luna (`codex:gpt-5.6-luna`, resolved
  `openai-codex/gpt-5.6-luna`) for repair and independent review. Wrapper argv,
  PIDs, timestamps, exits, brief digests, and result digests below are
  authoritative from the preserved receipts.

#### Ordered shards-digest-repair receipt register

1. **Repair — `T1.2-evidence-shards-digest-repair` (implementer, Luna).**
   Receipt `receipts/T1.2-evidence-shards-digest-repair-receipt.json`, SHA-256
   `8ebc292c02bb75f8db70e00de189107f8782d25fdfee09f952865fd7bc22497e`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T1.2-evidence-shards-digest-repair.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `33414`; `2026-08-21T11:10:54Z` → `2026-08-21T11:14:27Z`;
   exit `0`; brief SHA-256
   `00f4e0c7089396001bef89fd8c92c1f3a1c2906c9913fe6782c915acb8b6f1dd`;
   result SHA-256
   `018a4cfd30ad6eb160a59002035acb6bab0f7e1e07256b31a507105de6328ef8`.
   It refreshed the `test-shards.json` pins to
   `d96861fbd1743ef9597897e6751f37d8359974fb2b5a127b7f937ace0642e570`;
   validator exit was `0`.
2. **Review — `T1.2-evidence-shards-digest-repair-review` (reviewer, Luna).**
   Receipt `receipts/T1.2-evidence-shards-digest-repair-review-receipt.json`,
   SHA-256
   `fb58e2a2eac96802851f8d5a908fce67856c678436ee1c6f1488685e9aef2a7c`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T1.2-evidence-shards-digest-repair-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `33604`; `2026-08-21T11:14:50Z` → `2026-08-21T11:18:38Z`;
   exit `0`; brief SHA-256
   `d38b586b4a6c377ca1dee41f1121d42f6c9bb8c4afae07300062ff9a37c6de24`;
   result SHA-256
   `056b66ba5625fa3c4edb1cce7515f4a2685cf84427b72e6fac748756caeba6a9`.
   The review independently verified both live pins, the minimal repair diff,
   and author `POM <peter@omalley.io>`, then raised `MUST-001` because the
   test-shards recurrence rule was not yet durable. This revision records it.

- **Findings/revision and recording path:** `MUST-001` is closed by explicitly
  recording both validator-enforced recurrence rules: an execution-log edit
  requires refreshing `manifest.tasks[5].recovery_note.sha256`; a
  `test-shards.json` edit requires refreshing every
  `manifest.tasks[5].evidence_links[*].sha256` reference to that file and
  `manifest.tasks[6].shard_integrity.sha256`. The receipts are immutable and
  are nested in the manifest's existing T1.2 receipt register; this
  disposition is the durable recording path authorized by adjudication A.
- **Tests/evidence:** the required read-only evidence validator exits `0` on
  the committed state. No product tests, full suite, validator changes, or
  other tests were run.
- **Residual risks:** the two recurrence rules above remain validator-enforced
  obligations for future evidence edits. The pre-existing validator gap
  remains tracked per adjudication A: `_iter_digest_refs` silently skips
  malformed (non-64-hex) digest strings paired with a path; this is a
  candidate future XHARD validator-hardening card and does not block G1.
- **Changed files and controls:** this revision changes only the execution log
  and manifest; `test-shards.json` remains byte-identical at digest
  `d96861fbd1743ef9597897e6751f37d8359974fb2b5a127b7f937ace0642e570`.
  The evidence commit contains only the three allowed files, with no receipt
  committed. No other file, receipt, protected state, or branch changed; no
  push, merge to `main`, promotion, live/model/runtime/provider call, secret
  access, or wrapper dispatch occurred in this evidence recording.
- **Next unblocked card:** `H1-wrapper-survival-stop-marker-precode-review`.

### G1 / H1 — wrapper-survival + stop-marker chain (2026-08-21)

- **Task/gate/label/role:** `evidence-log-H1` / no gate / `evidence-log H1:
  pre-code review (v3 continue), implementer a7b18708, post-impl review
  continue, integration push` / evidence. This is the pre-G1 H1 hardening
  card. Disposition: **continue / complete**. The H1 chain is recorded
  without changing implementation, validator, or test code.
- **Model routes:** Grok `grok-4.6` for the pre-code review chain through
  v3; Luna `codex:gpt-5.6-luna` (resolved
  `openai-codex/gpt-5.6-luna`) for the implementer, reviewer, and integration.
  Wrapper argv, PIDs, timestamps, exits, brief digests, result digests, and
  receipt digests below are authoritative from the preserved receipts.

#### Ordered H1 receipt register

1. **Pre-code review v1 — `H1-wrapper-survival-stop-marker-precode-review`
   (Grok).** Receipt
   `receipts/H1-wrapper-survival-stop-marker-precode-review-receipt.json`,
   SHA-256
   `01371b234de0a0523a1b5c30c8a38d3a93b67ed9172af9f520a02de2124cd780`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker-precode-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `34456`; `2026-08-21T11:35:30Z` →
   `2026-08-21T12:13:23Z`; exit `0`; brief SHA-256
   `36faf849c6a4cad7ad2c3a4389694c9a3d6e99cddacc6b2ad438a5221fab7e5c`;
   result SHA-256
   `19aa66b82426503cc0f2d818d5b4c2f7308e2c8001a097662e8d8a900a9c7c27`.
   The body was a degenerate `continue` referring to phantom prior binding
   conditions, so it is recorded as **NO review**, not as a substantive
   disposition.
2. **Pre-code review v2 — `H1-wrapper-survival-stop-marker-precode-review-2`
   (Grok).** Receipt
   `receipts/H1-wrapper-survival-stop-marker-precode-review-2-receipt.json`,
   SHA-256
   `a5118b695940991db2fb1fb0a46dd6755613cc11d43edf881a9e7287b463e4d4`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker-precode-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `35060`; `2026-08-21T12:14:15Z` →
   `2026-08-21T12:28:11Z`; exit `0`; brief SHA-256
   `36faf849c6a4cad7ad2c3a4389694c9a3d6e99cddacc6b2ad438a5221fab7e5c`;
   result SHA-256
   `4fcf7a1ecce4b40f4967d93b84675f633fccd19a54c5824737b05317af3a431e`.
   The body again referenced prior binding conditions and is recorded as
   **NO review**.
3. **Pre-code adjudication — `H1-wrapper-survival-stop-marker-precode-adjudication`
   (Grok).** Receipt
   `receipts/H1-wrapper-survival-stop-marker-precode-adjudication-receipt.json`,
   SHA-256
   `48d3ab0f71739d1eadfcb5aaaa1d70d9eca6d928840c310fa8dfc8ced2ccc8d0`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker-precode-adjudication.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `35337`; `2026-08-21T12:29:00Z` →
   `2026-08-21T12:45:16Z`; exit `0`; brief SHA-256
   `e4b9afb77c07e21b5b6ae313e6f753894a48d327290d9f450a3655409a84ebb3`;
   result SHA-256
   `f9752bcc64dea42db003827e7f960a3a51073622cfa84974750eae97e6c0e2b5`.
   This was the third degenerate stub dispatch, also treated as **NO review**.
   The orchestrator's note
   `receipts/h1-precode-stub-note.json` (SHA-256
   `d0c3214a16fb16c6c69ebef657106e536d8bb849c9a9ddb7096134f48962a41e`)
   records the contamination: the briefs pointed the model at prior review
   artifacts. The three stub responses are superseded by v3; they do not
   consume the substantive one-review allowance.
4. **Substantive pre-code review v3 —
   `H1-wrapper-survival-stop-marker-precode-review-3` (Grok).** Receipt
   `receipts/H1-wrapper-survival-stop-marker-precode-review-3-receipt.json`,
   SHA-256
   `6083de36cfc3ca41f127130431081445150dd4f392d5b14e5ced70fb8c3e218c`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker-precode-review-3.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `35651`; `2026-08-21T12:45:53Z` →
   `2026-08-21T12:57:42Z`; exit `0`; brief SHA-256
   `398ca6258f805e0f6e94e5f1e9f823f06ca03f11e7c21f60ce0872dcc08aa5bf`;
   result SHA-256
   `890b41e8d94b96214f0ff58be1fd469ed8e7aae08ee8542eeea2b5570d7ce1e2`.
   Result: **continue**. The seven binding conditions were trap
   placement/body/exit, a no-clobber guard, partial-receipt fields, literal
   `_stop_marker`, and the required test coverage (including the exact
   literal-line-start matching rule). Residual risks were the install window,
   leaked ignore-probe on `os._exit`, orphaned-child pipes,
   `TASK_ALREADY_COMPLETED` on interrupted-receipt re-dispatch, column-0
   markers in code fences, and second-signal reentry. None is a §13 stop.
5. **Implementer abort — `H1-wrapper-survival-stop-marker` (Luna).** Receipt
   `receipts/H1-wrapper-survival-stop-marker-receipt.json`, SHA-256
   `4d20133abfda3523e1bcf35b502856a2a84c1478dd2b1a2a4bc9b092654ba3fd`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `35851`; `2026-08-21T12:58:18Z` →
   `2026-08-21T12:59:00Z`; exit `0`; brief SHA-256
   `868b9178d48ae167d7679fb7ba0573f335c53a693c73729a5cc6176c4503f4cb`;
   result SHA-256
   `cee8dcce755bb9a782846798f1f37e77a0835642e3193f7b61966df60a0203b9`.
   The brief claimed immutable base `9a64b35b`, while the actual base was
   `bef05ff5`; the implementer performed a clean no-mutation abort. The brief
   was corrected before the rerun.
6. **Implementer rerun — `H1-wrapper-survival-stop-marker-rerun` (Luna).**
   Receipt `receipts/H1-wrapper-survival-stop-marker-rerun-receipt.json`,
   SHA-256
   `dfecc03f3bfdd4fe7a4abd783a3fa7c5a0f234812727434696716124aae99c4d`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `35960`; `2026-08-21T12:59:25Z` →
   `2026-08-21T13:07:22Z`; exit `0`; brief SHA-256
   `cd194c4a7b95015647acd19bc1f11e416b740ff6121bd2b70aa2bfe3b9bf7860`;
   result SHA-256
   `da48052390d593b9f13a7f3ba9cae6e2e81e7976a90e946218c8f8e623887bf6`.
   Commit `a7b187083694090d661c05d6831ccd0f845b990d` was created on base
   `bef05ff5c5240d0bf30fdeff8a2904e653d70f07`. It changed only
   `scripts/run_workflow_execution_spine_agent.py` (+65) and
   `tests/test_run_workflow_execution_spine_agent.py` (+137/−18). The
   implementation adds SIGTERM/SIGHUP/SIGINT trapping with a partial
   `status=interrupted` receipt containing `preserved_args`, wrapper/child
   PIDs, timestamps, and signal, exits with `os._exit(128+signum)`, protects
   an interrupted receipt from clobbering, best-effort releases the registry,
   and latches literal `^JUDGMENT_REQUIRED:` / `^STOP:` markers.
7. **Post-implementation review —
   `H1-wrapper-survival-stop-marker-review` (Luna).** Receipt
   `receipts/H1-wrapper-survival-stop-marker-review-receipt.json`, SHA-256
   `0f13b95f33114a152558daddae98d34d151e388585427f4596bd0561caee1b71`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `36877`; `2026-08-21T13:07:45Z` →
   `2026-08-21T13:12:27Z`; exit `0`; brief SHA-256
   `af1dad44dfed02c3eb102e6b4b666ed006a44e81f32bf6904e51373b32825e2b`;
   result SHA-256
   `1cd8c999c664443027bc119f37d55d62b7e898d5977b893d49b4f4e677319222`.
   Result: **continue**. All seven v3 binding conditions were verified
   against the implementation. The focused shard
   `python3 -m pytest tests/test_run_workflow_execution_spine_agent.py -q`
   passed `12 passed` under Python 3.11.11; pytest warned about the unknown
   `timeout` config option, non-blocking.
8. **Integration — `H1-wrapper-survival-stop-marker-integration` (Luna).**
   Receipt
   `receipts/H1-wrapper-survival-stop-marker-integration-receipt.json`,
   SHA-256
   `90b94cdf53d6acc19eef0bd5b97480c4330f6bfec1cb200e613b28c9515290ad`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H1-wrapper-survival-stop-marker-integration.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `37186`; `2026-08-21T13:12:52Z` →
   `2026-08-21T13:16:04Z`; exit `0`; brief SHA-256
   `018b0f60984e0a5777d11cd184da535602313762410c3d374efb29a0140f1c36`;
   result SHA-256
   `ad0aca2ded60e9b3cd17e7f1aa3b063948d1e9c3a219334ad80a9e781b1e13fc`.
   Integration verified exit `0`, the focused shard once, and fast-forward push
   `bef05ff5..a7b18708` via
   `git push origin HEAD:fixer/workflow-execution-spine-consolidation`;
   remote and local both verified at `a7b18708`.

- **Findings/revisions:** The three degenerate stub dispatches were rejected
  as reviews; v3 supplied the substantive continue and its seven binding
  conditions. The immutable-base abort was clean and was followed by the
  corrected-base rerun. The degenerate-stub failure mode is fixed by
  contamination-free briefs: review briefs MUST NOT point the model at prior
  review artifacts.
- **Tests/evidence:** The reviewer-recorded focused shard passed `12 passed`;
  no other tests were run. The required read-only evidence validator exits
  `0` on the committed state with
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`.
  No validator change was made.
- **Residual risks and recurrence rules:** H1's accepted residual risks are
  the install window, leaked ignore-probe on `os._exit`, orphaned-child pipes,
  `TASK_ALREADY_COMPLETED` on interrupted-receipt re-dispatch, code-fence
  column-0 markers, and second-signal reentry; none is a §13 stop. Both
  recurrence rules remain validator-enforced: an execution-log edit requires
  refreshing `manifest.tasks[5].recovery_note.sha256`; a `test-shards.json`
  edit requires refreshing every matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256`. The pre-existing validator gap
  remains tracked per adjudication A: `_iter_digest_refs` silently skips
  malformed non-64-hex digest strings paired with a path; it is a candidate
  future XHARD card and does not block G1.
- **Commit/files/controls:** This evidence append is one coherent commit
  authored by `POM <peter@omalley.io>` with message prefix
  `docs(exec-spine):`; the changed files are exactly the three allowed files:
  this execution log, `evidence/manifest.json`, and
  `evidence/test-shards.json`. No receipt is committed. No other file,
  protected state, or branch changed; no push, merge to `main`, promotion,
  live/model/runtime/provider call, secret access, or wrapper dispatch
  occurred in this evidence recording. The earlier integration push is
  recorded above as prior-card evidence.
- **Next unblocked card:** `H2-dead-pid-sweep-precode-review`.
 
### G1 / H2 — dead-PID sweep chain (2026-08-21)

- **Task/gate/label/role:** `evidence-log-H2` / no gate /
  `evidence-log H2: pre-code continue, implementer da959d56, review continue,
  integration push` / evidence.
- **Disposition:** `continue`. This is the pre-G1 hardening card directed by
  operator directive 2026-08-21 §15 item 2. The H2 chain is recorded from the
  five preserved receipts below; receipt files are evidence inputs only and
  are not committed.
- **Model routes:** Grok `grok-4.6` for the substantive pre-code review;
  Luna `codex:gpt-5.6-luna` for the implementer, corrected rerun, post-
  implementation review, and integration.

#### Ordered H2 receipt register

1. **Pre-code review — `H2-dead-pid-sweep-precode-review` (Grok).** Receipt
   `receipts/H2-dead-pid-sweep-precode-review-receipt.json`, SHA-256
   `5fcd50a84e049760bb651a4e7cb3d2269a8b2a505fbb20f64763a67b50d08b67`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H2-dead-pid-sweep-precode-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `37818`; `2026-08-21T13:27:34Z` →
   `2026-08-21T13:40:43Z`; exit `0`; brief SHA-256
   `80a48110cfbf10b60f5b5eb1d81b1803f7b1a0fac51065309474f303e855193c`;
   result SHA-256
   `ed6e7c57e9a36c8526020914586479d4de318b888bcb4b23d839c8a108f253e8`.
   Result: **continue** with five binding conditions: retain the existing
   flock and guard-time-only sweep; clear only an integer dead PID whose
   `now - start_ts_epoch` is strictly greater than the 60-second grace;
   keep missing/non-integer PIDs on the existing six-hour path and never
   clear live PIDs; preserve `now - start_ts_epoch` as the age basis with no
   death timestamp; preserve the exact
   `stale-allowance-cleared.json` keys and put class distinctions only in
   `reason`; and inject epochs/PIDs in deterministic tests without sleeping.
   The review also required the protected behaviors to remain unchanged:
   `_pid_exists`, overlap/candidate logic, registry and lock paths, receipt
   schema, signal handling, child launch, and no timers or threads.
   Accepted residual risks were PID reuse, EPERM being classified as dead by
   the unchanged PID probe and therefore clearing at 60 seconds, the
   same-host PID-namespace assumption, the pre-existing in-memory sweep then
   overlap failure not persisting the registry, no-dispatch-no-sweep, and the
   absence of `wrapper-death-note-t12-precode.json`.
2. **Implementer gate abort — `H2-dead-pid-sweep` (Luna).** Receipt
   `receipts/H2-dead-pid-sweep-receipt.json`, SHA-256
   `bdde7d80f93ad7a0f1bf6deca385e42d7014154eb054e8ce3b83062d6132f8b0`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H2-dead-pid-sweep.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `38082`; `2026-08-21T13:41:10Z` →
   `2026-08-21T13:43:19Z`; exit `0`; brief SHA-256
   `86e45b302c50c921d057db0c127dfa6bbfc924bd480743e7ca6b8f806bd040fd`;
   result SHA-256
   `9df630c0782cebb962a73a008895280beab41d8ac3542c184cd9514e6369cdff`.
   Mutation stopped cleanly with no changed files or commits: the receipt
   stores only `result_sha256`, not the result body, so the strict gate could
   not verify `continue`. The brief gate was fixed by recording the
   orchestrator-verified disposition and embedding the binding conditions
   before rerun.
3. **Implementer rerun — `H2-dead-pid-sweep-rerun` (Luna).** Receipt
   `receipts/H2-dead-pid-sweep-rerun-receipt.json`, SHA-256
   `3b7c3c68a411bfdb36005256f9f2319748b79b04917a865bca074d6ad9269249`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H2-dead-pid-sweep.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `38209`; `2026-08-21T13:43:43Z` →
   `2026-08-21T13:52:53Z`; exit `0`; brief SHA-256
   `3b0fba52c2b1e328af1df3c605a6c715b6a7a75bbf36f35498a1ac9f40369817`;
   result SHA-256
   `e168388fb50d3d67e81efa08f9c4746987bb08e53367650877c1bf284ac86c16`.
   Commit `da959d56631eb219721a2c06bc8cb66e404f94b5` was created on base
   `28aa48af801d35c48d7ff4668bf9f2e0fe4520ed`, changing only
   `scripts/run_workflow_execution_spine_agent.py` (+27/−2) and
   `tests/test_run_workflow_execution_spine_agent.py` (+179). The repair
   adds `DEAD_PID_GRACE_SECONDS = 60`; clears dead integer PIDs only when
   age is greater than 60 seconds under the existing flock and guard-time
   sweep; keeps missing/non-integer PIDs on the six-hour path; never clears
   live PIDs; and preserves the exact `stale-allowance-cleared.json` keys.
4. **Post-implementation review — `H2-dead-pid-sweep-review` (Luna).**
   Receipt `receipts/H2-dead-pid-sweep-review-receipt.json`, SHA-256
   `a73a85af51cd8dc878ccad211e8fc81d9fcfdbc7324e8617f6c1b98f96b9389b`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H2-dead-pid-sweep-review.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `39145`; `2026-08-21T13:53:26Z` →
   `2026-08-21T13:56:02Z`; exit `0`; brief SHA-256
   `5b063fdd89eff333eaf87889abfc408ab44f56e96cb37616a975974e7a259a89`;
   result SHA-256
   `1f2d20140feecb642c9ca091ee9f8f5e61249f4c6a8f90226cc1051a246618f6`.
   Result: **continue**, with no must findings. All five pre-code conditions
   were verified against wrapper lines 182–215 and tests lines 114–283.
   The focused shard
   `python3 -m pytest tests/test_run_workflow_execution_spine_agent.py -q`
   passed `20 passed` with one pre-existing unknown-`timeout` pytest
   configuration warning.
5. **Integration — `H2-dead-pid-sweep-integration` (Luna).** Receipt
   `receipts/H2-dead-pid-sweep-integration-receipt.json`, SHA-256
   `04ccf0c946b13aa20bb5c3d5c620052190694f5e2c593acef57862db9d7723e7`;
   wrapper
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H2-dead-pid-sweep-integration.md --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   PID `39463`; `2026-08-21T13:56:19Z` →
   `2026-08-21T13:59:05Z`; exit `0`; brief SHA-256
   `76d3f32ce48f09ff8a4ab27839996f3350a7f6d3f2f199e0a350e83824e78519`;
   result SHA-256
   `af7ccb133108993aeb0816a3f8b1fecddeb31663f9ae7e00fc1e833e2f833b91`.
   Integration ran the focused shard exactly once with exit `0` and
   `20 passed, 1 warning`, then fast-forward pushed
   `a7b187083694090d661c05d6831ccd0f845b990d` →
   `da959d56631eb219721a2c06bc8cb66e404f94b5` using
   `git push origin HEAD:fixer/workflow-execution-spine-consolidation`.
   Remote and local were both verified at `da959d56`.

- **Findings/revisions:** The first implementer attempt was a clean gate abort
  because the receipt exposed only `result_sha256`; no mutation occurred.
  The corrected brief recorded the orchestrator-verified `continue` and
  embedded all five conditions, after which the rerun created `da959d56`.
  The post-implementation review found no must findings. This brief-gate
  lesson is binding for future implementer gates: receipts contain only the
  result digest, never the result body; briefs must embed binding conditions
  or explicitly state an orchestrator-verified disposition. The two H1/H2
  gate aborts each cost approximately two minutes.
- **Tests/evidence:** The H2 reviewer-recorded focused shard passed
  `20 passed` with one pre-existing unknown-`timeout` warning, and the
  integration agent ran it exactly once. No other tests were run by the H2
  chain. The required read-only evidence validator exits `0` on the
  committed state with
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`.
  No validator or test change was made by this evidence recording.
- **Residual risks and recurrence rules:** Accepted H2 risks are PID reuse;
  EPERM-PID semantics clearing at 60 seconds through the unchanged
  `_pid_exists`; the same-host PID-namespace assumption; the pre-existing
  in-memory sweep/overlap failure not persisting the registry; and
  no-dispatch-no-sweep. The absence of
  `wrapper-death-note-t12-precode.json` remains explicit. Both recurrence
  rules are validator-enforced: an execution-log edit requires refreshing
  `manifest.tasks[5].recovery_note.sha256`; a `test-shards.json` edit
  requires refreshing every matching `manifest.tasks[5].evidence_links[*].sha256`
  and `manifest.tasks[6].shard_integrity.sha256`. The pre-existing validator
  gap remains tracked per adjudication A:
  `_iter_digest_refs` silently skips malformed non-64-hex digest strings
  paired with a path; it is a candidate future XHARD card and does not block
  G1.
- **Commit/files/controls:** This evidence append is one coherent commit
  authored by `POM <peter@omalley.io>` with message prefix
  `docs(exec-spine):`; the changed files are exactly the three allowed files:
  this execution log, `evidence/manifest.json`, and `evidence/test-shards.json`.
  No receipt is committed. No other file, protected state, or branch changed;
  no push, merge to `main`, promotion, live/model/runtime/provider call,
  secret access, or wrapper dispatch occurred in this evidence recording. The
  earlier H2 integration push is recorded above as prior-card evidence.
- **Next unblocked card:** `H3-overlap-narrow-precode-review`.

### G1 / H3 — PLAN §9 STOP — H3-overlap-narrow (2026-08-21)

- **Task/gate/label/role:** `evidence-log-H3-stop` / no gate / `H3
  [XHARD-REVIEW] pre-code contract review of read-only overlap narrowing
  (OVERLAP-NARROW)` / evidence.
- **Disposition:** **STOP — `JUDGMENT_REQUIRED`**. This is the H3 pre-code
  gate STOP required by plan §9: an XHARD pre-code review that does not return
  `continue` stops the affected card. No H3 mutation occurred.
- **Input/base:** `6eb55a7e98ad8f0c45c69acc0702373b4cc73074`; H1 and H2 are
  complete, and H2's implementation/integration commit was pushed as
  `da959d56631eb219721a2c06bc8cb66e404f94b5`. At this stop the local
  evidence-recording HEAD is `6eb55a7e98ad8f0c45c69acc0702373b4`; the
  remote implementation SHA remains `da959d56`.

#### Ordered H3 pre-code dispatch register

1. **`H3-overlap-narrow-precode-review` (Grok).** Wrapper PID `40141`;
   `2026-08-21T14:09:27Z` → `2026-08-21T14:22:57Z`; exit `0`; receipt
   `receipts/H3-overlap-narrow-precode-review-receipt.json`, receipt SHA-256
   `d52b395552e3c4cbce20b2bbc492b22a21c62c3823ece4afbafb651bb04bdd9c`;
   result SHA-256
   `9e84b047b70ce57fbfc8de55f419e47711c79e648892e8766ef516df1b8d270a`.
   The wrapper captured a degenerate 301-byte final-message-only stub:
   “Disposition is unchanged: `JUDGMENT_REQUIRED` on must 1–3 (lock hold,
   contradictory overlap predicate, read-only + mutator snapshot hazard).”
2. **`H3-overlap-narrow-precode-adjudication` (Grok).** Wrapper PID
   `40379`; `2026-08-21T14:23:38Z` → `2026-08-21T14:41:36Z`; exit `0`;
   receipt `receipts/H3-overlap-narrow-precode-adjudication-receipt.json`,
   receipt SHA-256
   `0032f2f82ad19b77c2a9eb0ab0fb510eb22986e6ccf9f05f7f985ca4de86cee3`;
   result SHA-256
   `21fd413af6fe0b6e9600bfd05a12d54bef9f5ba4a2b938280531afd2b380580e`.
   The wrapper captured a degenerate 291-byte final-message-only stub:
   “The H3 pre-code verdict stands: `JUDGMENT_REQUIRED` on the
   contradictory overlap predicate (finding 2). Findings 1 and 3 are real
   hazards but out of this card's frozen repair.”

- **Coherent verdict:** Both Grok dispatches returned degenerate stub-tail
  captures because the launcher persisted only the final message; the
  substantive review body was not persisted. Treat the coherent stub core
  as the verdict, not as `continue`: `JUDGMENT_REQUIRED` on the contradictory
  overlap predicate (finding 2). Findings 1 (lock hold) and 3 (read-only +
  mutator snapshot hazard) are real hazards but outside H3's frozen repair.
  Neither dispatch returned `continue`.
- **Stop note:** the orchestrator-recorded coherent core and stop rule are
  preserved at
  `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/h3-precode-stop-note.json`.
- **Operator escalation:** operator direction is required on (a) whether
  read-only + mutating concurrency must remain overlapping, meaning
  OVERLAP-NARROW applies only to read-only pairs, and (b) whether the
  snapshot hazard requires a wrapper-guard card before any read-only parallel
  window is used.
- **Queue impact:** H3 is STOPPED. Per operator §15 ordering, H4
  (evidence-brief, no pre-code review) and G1 remain queued behind this H3
  stop. The next unblocked action is operator direction on H3; no further
  Grok dispatches will be made for H3 until the operator resolves the
  contract contradiction.
- **Residual risks and recurrence rules:** Every execution-log edit requires
  refreshing `manifest.tasks[5].recovery_note.sha256` to the current log
  digest. Every `test-shards.json` edit requires refreshing every matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256` to the current shard digest;
  both rules are validator-enforced. The pre-existing validator gap remains
  tracked and adjudicated A: `_iter_digest_refs` silently skips malformed
  non-64-hex digest strings paired with a path. The H3 pre-code gate exposed
  stub-tail captures from the Grok review capability (final-message-only
  capture); the substantive body was not persisted, so the coherent stub
  core is recorded as `JUDGMENT_REQUIRED`, never as `continue`. H1 and H2
  residual risks already recorded above remain unchanged.
- **Controls:** no H3 mutation, no further H3 Grok dispatch, no tests,
  implementation, validator change, receipt edit, live/model/runtime call,
  secret access, push, merge to `main`, promotion, or wrapper dispatch
  occurred in this evidence recording.
- **Commit/files:** this STOP record is to be one coherent commit authored by
  `POM <peter@omalley.io>` with message prefix `docs(exec-spine):`; the
  changed files are exactly the three allowed files: this execution log,
  `evidence/manifest.json`, and `evidence/test-shards.json`. No receipt is
  committed, and no other file, protected state, branch, or ref changes.

### G1 / H4 — evidence-brief guard chain (2026-08-21)

- **Task/gate/label/role:** `evidence-log-H4` / no gate /
  `evidence-log H4: implementer 4cdabf5d, review (MUST-001/002), revision
  acec7cc1, re-review continue, integration push acec7cc1` / evidence.
- **Disposition:** **continue / complete**. This is the pre-G1 hardening card
  directed by operator directive 2026-08-21 §15 item 5. The H4 chain is
  recorded from the five preserved receipts below; receipt files are evidence
  inputs only and are not committed.
- **Model route:** Luna (`codex:gpt-5.6-luna`, resolved
  `openai-codex/gpt-5.6-luna`) for implementer, reviewer, revision,
  re-review, and integration. Wrapper commands, PIDs, timestamps, exits,
  brief digests, result digests, and receipt digests below are authoritative
  from the preserved receipts.

#### Ordered H4 receipt register

1. **Implementer — `H4-evidence-brief` (Luna).** Receipt
   `receipts/H4-evidence-brief-receipt.json`, SHA-256
   `0d44b3e23bc9e5fc5cb6212037d91bbb10b8eb7db2febf297896a77ca17947d4`;
   wrapper `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H4-evidence-brief.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   wrapper PID `41424`, launcher child PID `41430`;
   `2026-08-21T15:03:06Z` → `2026-08-21T15:12:24Z`; exit `0`; brief
   SHA-256 `465a6549ecbbe6e4f5c0625b4769a94c3738f1261e74c43cb35ffcb818d3cba2`;
   result SHA-256
   `7be9266ad948a7239bd109bd56c7e65c1249946f99fd09cac4a07b01bcb06d2f`.
   Commit `4cdabf5dda30c53b84462c10279f6107a63afd80`
   (`fix(exec-spine): guard evidence briefs against self-referential receipt
   fields`) was based on `de75b418`; changed exactly
   `scripts/run_workflow_execution_spine_agent.py` and
   `tests/test_run_workflow_execution_spine_agent.py`.
2. **Post-implementation review — `H4-evidence-brief-review` (Luna).**
   Receipt `receipts/H4-evidence-brief-review-receipt.json`, SHA-256
   `4b9bb4471886a2898bba451ec232762996baf372f2ea03b9b46262e0a6132be8`;
   wrapper `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H4-evidence-brief-review.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   wrapper PID `42661`, launcher child PID `42667`;
   `2026-08-21T15:13:31Z` → `2026-08-21T15:18:57Z`; exit `0`; brief
   SHA-256 `e255d3de79257d2333f1ef4d594a7b2e29fdcbb7d56c1eefd1b3eef34fa7556c`;
   result SHA-256
   `dc3a4902424b7509643ea1a0b4864b0e18bf3b51de48b1e4e358a6dbadc80599`.
   Disposition: **correct**, with exactly two must findings, both
   **mechanical**. `H4-MUST-001` identified compound-negation/explanation
   fail-open behavior when contradictory instructions remained in one
   semicolon-separated clause. `H4-MUST-002` identified missed requirement-form
   instructions such as `is required`, `must contain`, and `is mandatory`
   naming the evidence agent's own post-exit fields. Guard ordering, complete
   docstring guidance, and non-evidence-role behavior were correct; the
   reviewer did not run pytest.
3. **Revision — `H4-evidence-brief-revision` (Luna).** Receipt
   `receipts/H4-evidence-brief-revision-receipt.json`, SHA-256
   `224b4d7a61a84ebfbd75a33e8b47b204c5cecf0ff1493e7d86e2afa7d5b6abc7`;
   wrapper `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H4-evidence-brief-revision.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   wrapper PID `42849`, launcher child PID `42855`;
   `2026-08-21T15:20:04Z` → `2026-08-21T15:25:40Z`; exit `0`; brief
   SHA-256 `4415fff3e282ee905f8673a79b891affcbbac101f18010972def0d8c6c44a0a1`;
   result SHA-256
   `f04674530370d52607bc425b24d1c4657ca46101dc7f1da04d9d9ead761a8823`.
   Commit `acec7cc1b2c68dcadb33851947202d5adc04f672`
   (`fix(exec-spine): repair evidence-brief fail-open guard bypasses`) was
   based on `4cdabf5d`; it changed exactly the same two implementation/test
   files. The repair applies per-clause instruction-scope evaluation with
   semicolon splitting, adds requirement-form detection for
   `is required`/`must contain`/`is mandatory`/`must include`/`needed in the
   result`/`expected in the result`, and adds tests for all review
   counterexamples with a side-effect-free harness.
4. **Independent re-review — `H4-evidence-brief-rereview` (Luna).** Receipt
   `receipts/H4-evidence-brief-rereview-receipt.json`, SHA-256
   `51a55fb0e84ab3855502e2aa5ec8baabef30b17889278f19d62482f8dc04983c`;
   wrapper `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H4-evidence-brief-rereview.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   wrapper PID `44245`, launcher child PID `44251`;
   `2026-08-21T15:26:18Z` → `2026-08-21T15:31:20Z`; exit `0`; brief
   SHA-256 `fdf27bace0c5577fe85d7fcd5b782d25d73fad28405584c4333ee85107a11f0e`;
   result SHA-256
   `60e4a2a9add256de6fa5c3f9988447fe2a38a409427b3136f20ed6c044a3a03e`.
   Disposition: **continue**, `findings: []`. `H4-MUST-001` and
   `H4-MUST-002` are closed; every supplied counterexample was verified
   rejected or passed as intended, and no new must or should finding was
   raised. The bounded phrase set leaves future synonyms such as
   `finished_at`, `completion timestamp`, `receipt SHA-256`, and
   `receipt checksum` as acknowledged residual risk, not an open finding.
5. **Integration — `H4-evidence-brief-integration` (Luna).** Receipt
   `receipts/H4-evidence-brief-integration-receipt.json`, SHA-256
   `46cff743b746c3c22ca901d14338a9c6bbaa2d407650cc9aa79fa5a889d99cc1`;
   wrapper `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/H4-evidence-brief-integration.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine --timeout=3600`;
   wrapper PID `44884`, launcher child PID `44890`;
   `2026-08-21T15:32:02Z` → `2026-08-21T15:34:04Z`; exit `0`; brief
   SHA-256 `768d0d285497a6c11c652ebe992bd1bc5f7f2769df2f845f3ff51bbd11801151`;
   result SHA-256
   `1f6ee1b6d8c045a9779f5b5efce1ed12393e2215dc049e9f3acb27e5f5df8644`.
   The focused wrapper shard ran exactly once:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
   tests/test_run_workflow_execution_spine_agent.py` → `46 passed, 1 warning`,
   exit `0`. Worktree status was identical before and after. Integration
   created no commit and fast-forward pushed `da959d56..acec7cc1` via
   `git push origin HEAD:fixer/workflow-execution-spine-consolidation`;
   remote, local, and integration target were all verified at `acec7cc1`.

- **Findings/revision/re-review:** The review raised exactly
  `H4-MUST-001` and `H4-MUST-002`, both mechanical. One revision,
  `acec7cc1`, repaired per-clause scope and requirement-form detection; the
  one independent re-review returned `continue` and closed both findings.
  This satisfies operator §13/§14: exactly one substantive review, exactly
  one revision, and exactly one re-review.
- **Tests/evidence:** The integration-recorded focused wrapper shard passed
  `46 passed, 1 warning`, exit `0`, and ran once. The required read-only
  evidence validator exits `0` on the committed state with
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`.
  No other tests were run; no validator or implementation change was made.
- **Residual risks and recurrence rules:** An execution-log edit requires
  refreshing `manifest.tasks[5].recovery_note.sha256`. A `test-shards.json`
  edit requires refreshing every matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256`; both rules are
  validator-enforced. The pre-existing validator gap remains tracked per
  adjudication A: `_iter_digest_refs` silently skips malformed non-64-hex
  digest strings paired with a path; it is a candidate future XHARD card and
  does not block G1. H4's guard phrase set is intentionally bounded:
  `finished_at`, `completion timestamp`, `receipt SHA-256`, and
  `receipt checksum` need deliberate future coverage, while ownership
  scoping between historical receipt facts and the current evidence agent's
  own post-exit fields must be preserved. H4 was dispatched while H3 was
  STOPPED: operator §15 ordering put G1 after the landed H1/H2 micro-patches
  and defers H3 overlap-narrow to before the T3.1/T3.2 read-only windows;
  H3 remains escalated pending operator direction.
- **Controls:** This evidence recording changed no receipt, protected state,
  source, validator, or runtime/test implementation. No other file, receipt,
  protected state, branch, or ref changed; no push, merge to `main`,
  promotion, live/model/runtime/provider call, secret access, or wrapper
  dispatch occurred in this evidence recording. The earlier H4 integration
  push is recorded above as prior-card evidence.
- **Commit/files:** This evidence append is one coherent commit authored by
  `POM <peter@omalley.io>` with message prefix `docs(exec-spine):`; the
  changed files are exactly the three allowed files: this execution log,
  `evidence/manifest.json`, and `evidence/test-shards.json`. No receipt is
  committed.
- **Next unblocked card:** `G1-gate-review` — Grok `[XHARD-REVIEW]` gate
  review of T1.1/T1.2. H3-overlap-narrow remains STOPPED pending operator
  direction and is deferred to before the T3.1/T3.2 read-only windows per
  operator §15/Grok ordering.
### G1 — fresh Grok gate review disposition (2026-08-21)

- **Task/gate/label/role:** `G1-gate-review` / `G1` /
  `evidence-log G1: fresh Grok gate review continue — T1 phase
  (WorkflowSnapshot + SchemaSnapshot) passes` / reviewer.
- **Model route and receipt:** Grok `grok-4.6`; receipt
  `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/G1-gate-review-receipt.json`.
  The receipt records base `f36ed7ed783e757403d05381c4c57e65ff48e81e`,
  exit `0`, no commits, no changed files, and an empty `stop_or_judgment`.
  The wrapper invocation was
  `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
  --model=grok-4.6
  --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/G1-gate-review.md
  --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
  --timeout=3600`; wrapper PID `45863`, launcher child PID `45869`;
  `2026-08-21T15:44:09Z` → `2026-08-21T15:55:34Z`; exit `0`; brief
  SHA-256 `a2171f832567d3b3bafea5856e12b51767b665b289d4394a855abc513b40a5e4`;
  result SHA-256
  `acec07fab0b858d9273ba4bd85c41caf08e157b812615111bff0978591262a36`.
- **Review scope:** T1 product diff
  `fbdd5596db7638d62f40def7b534012ebb1a7567..0a8e55ff8d0a7412e750237e9623ba147bb152f2`
  at review HEAD `f36ed7ed783e757403d05381c4c57e65ff48e81e`.
  The scope includes `4f38adb8` (T1.1 WorkflowSnapshot) and
  `a109003f` plus `0a8e55ff` (T1.2 SchemaSnapshot).
- **Disposition:** **continue**. Open must findings: **none**.
  `T1.2-MUST-001` (UID/layout-touched unknown schema would proceed) and
  `T1.2-MUST-002` (`schema_snapshot` unbound from `content_hash`, allowing
  replay to accept a swapped snapshot) were confirmed closed by `0a8e55ff`
  and the independent `T1.2-revision-rereview`, which also returned
  `continue`.
- **G1 acceptance points verified:** UI, API, and `{prompt: API}` inputs
  produce one canonical graph per input shape; the immutable retained
  snapshot is consumed by model Python, inspection, comparison, and replay;
  opaque unknown-node data survives projection; sidecar, layout, and
  lineage data remain lossless; schema precedence is request snapshot,
  verified connected `/object_info`, then content-addressed cache, with
  workflow observation non-authoritative; `touched_schema_classes` covers
  field, add/remove, link/socket, mode, and layout changes with fail-closed
  unknown-touched handling; replay performs no ambient lookup.
- **Accepted residual risks (not must findings):**
  `from_ui` builds the API snapshot and attaches the UI snapshot over it,
  so the final retained snapshot is UI; `compare_snapshot_authority` is
  used in tests and mixed-shape rejection but durable replay does not
  re-invoke it against persisted artifacts (T2 scope);
  `_ensure_ingest_workflow` retains an empty-state second-ingest door
  (first-ingest only); and `parse_edit_delta` schema-snapshot threading is
  deferred to the T2.1 gateway rather than being a G1 must.
- **Rejected alternatives:** treating prior T1.1/T1.2 `continue` receipts
  as the G1 authority; treating delta-threading as a G1 must; and treating
  the H3 stop (`de75b418`, wrapper overlap-narrow pre-code) as a T1
  replan or stop. H3 is outside T1 product scope and does not reopen the
  T1.1/T1.2 must findings.
- **T1 disposition and next card:** T1 is complete: T1.1 and T1.2 each
  completed pre-code continue → implementation → review →
  MUST-001/002 revision → independent re-review continue → integration,
  and G1 was the missing gate now supplied by this review. The next
  unblocked card is `T2.1` `[XHARD]`, one operation-admission gateway
  `admit_operation(snapshot, canonical_operation)`, with a Grok
  implementer and Grok pre-code `[XHARD-REVIEW]` under plan §6 G2,
  §8 lifecycle, and operator §§13–14.
- **Residual recurrence rules:** An execution-log edit requires refreshing
  `manifest.tasks[5].recovery_note.sha256`. A `test-shards.json` edit
  requires refreshing every matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256`; both rules are
  validator-enforced. The pre-existing validator gap remains tracked per
  adjudication A: `_iter_digest_refs` silently skips malformed
  non-64-hex digest strings paired with a path; it is a candidate future
  XHARD card and does not block T2.x.
- **H3 control:** H3-overlap-narrow remains STOPPED pending operator
  direction (`JUDGMENT_REQUIRED`, `de75b418`), outside T1/G1, and is
  deferred to before the T3.1/T3.2 read-only windows per operator §15/Grok
  ordering.
- **Controls:** This evidence recording changes no receipt, protected
  state, source, validator, runtime/test implementation, or branch.
  No push, merge to `main`, promotion, live/model/runtime/provider call,
  secret access, or wrapper dispatch occurred in this evidence recording.
  The required read-only evidence validator is to be run after this
  evidence commit; no tests are run.
- **Commit/files:** This evidence append is one coherent commit authored by
  `POM <peter@omalley.io>` with message prefix `docs(exec-spine):`;
  the changed files are exactly the three allowed files: this execution
  log, `evidence/manifest.json`, and `evidence/test-shards.json`. No
  receipt is committed.
## G2 / T2.1 — evidence-log T2.1 card sequence and disposition (2026-08-21)

- **Task/gate/label/role:** `evidence-log-T2.1` / `G2` /
  `evidence-log T2.1 card sequence and disposition` / evidence.
- **Disposition:** **PASS/complete**. T2.1 is a closed card. The complete
  sequence is pre-code stop → JR resolution → pre-code continue →
  implementation → post-implementation review → one revision → one
  independent revision re-review → integration. The operator §13/§14 rule is
  satisfied: one pre-code review phase (with the recorded JR escalation), one
  post-implementation review, and one revision re-review; no stacked
  adjudication was added.
- **Card contract and custody:** the card input/base was
  `fec6cb12fbee5bc6d5d67b9fb013cfa9bbd67ed7`; implementation commit
  `0716a8bcc829b8a18149c1c39cfd8bbb05a39087`; revision and integrated target
  `993cadd3cfa7760c4ef4954f9afaa44e48bf8898`. The implementation allowance
  contained 20 files under `vibecomfy/porting/edit/**` plus the named agent,
  executor, and test files; its recorded allowance digest begins
  `7b656c3b`. The revision contained 14 files within that frozen allowance.
  Receipts, the validator, implementation, runtime, and protected state were
  read-only inputs to this evidence record.

### Ordered T2.1 receipt register

The following seven receipts are the complete canonical T2.1 sequence.
Receipt files remain unchanged. Receipt SHA-256 values below are hashes of
the repository receipt files; `brief_sha256` and `result_sha256` are the
wrapper-recorded brief and result digests.

1. **Pre-code review — `T2.1-precode-review`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.1 one operation-admission gateway pre-code contract
   review`; role reviewer; route/resolved model `grok-4.6`; receipt
   `receipts/T2.1-precode-review-receipt.json`; receipt SHA-256
   `54df416198b3f265257b13fc72f99b12f3d71b7143b293915e981003b28bc088`;
   PID `46420`; `2026-08-21T16:02:49Z` → `2026-08-21T16:17:42Z`; exit `0`;
   base `fec6cb12fbee5bc6d5d67b9fb013cfa9bbd67ed7`; no target, commits, or
   changed files; brief SHA-256
   `15c71f842e28f4163cce1cc45020043f4871a7f6efdf2054083fcdc0fb411a9f`;
   result SHA-256
   `d5ceed095aade1f78e742fa6b682f9aa3ed4a6d55d15e41e84e50219208b4c5f`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1-precode-review.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record
   `g0/T2.1-precode-review-dispatch.log` ends with the
   `launch_omp_agent` marker. Disposition `stop` with
   `T2.1-JR-001` (allowance freeze: resolve by freezing the concrete
   allowance list, `forbidden: []`) and `T2.1-JR-002` (all layout operations
   route through the same gateway, not a second layout admission function).
   The allowance freeze was applied; this was not an unhandled judgment.

2. **Pre-code re-review — `T2.1-precode-review-2`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.1 pre-code re-review after allowance freeze
   (T2.1-JR-001/JR-002)`; role reviewer; route/resolved model `grok-4.6`;
   receipt `receipts/T2.1-precode-review-2-receipt.json`; receipt SHA-256
   `b9a08b2191c31f448f1a1e009216b34f803cf29fc2fd2ee3262461bf165ba753`;
   PID `46775`; `2026-08-21T16:18:54Z` → `2026-08-21T16:29:58Z`; exit `0`;
   base `fec6cb12fbee5bc6d5d67b9fb013cfa9bbd67ed7`; no target, commits, or
   changed files; brief SHA-256
   `91a973ebfccb504a7d124323eb787ef3525f559410ed2c8802d2a1e9a1b588df`;
   result SHA-256
   `2aacf08a2d24c3bbe1cc1c81ccb262d0e99c58e411927b016f40e842e21e3295`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1-precode-review-2.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record
   `g0/T2.1-precode-review-2-dispatch.log`. Disposition `continue`.
   Binding pre-code conditions were recorded; the later post-implementation
   review found that the commit did not fully meet MUST-001..004, which the
   single revision fixed.

3. **Implementation — `T2.1`.** Gate `G2`; label
   `T2.1 [XHARD] One operation-admission gateway (admit_operation)`; role
   implementer; route/resolved model `grok-4.6`; receipt
   `receipts/T2.1-receipt.json`; receipt SHA-256
   `2024e881515216a0c6a805e7dac34de3036ac20675e027f6300602418c913ed0`;
   PID `47099`; `2026-08-21T16:30:37Z` → `2026-08-21T17:07:36Z`; exit `0`;
   base `fec6cb12fbee5bc6d5d67b9fb013cfa9bbd67ed7`; commit
   `0716a8bcc829b8a18149c1c39cfd8bbb05a39087`
   (`feat(exec-spine): add one operation-admission gateway`); 20 changed
   files within the frozen allowance; brief SHA-256
   `e8e9a19045880f43739e0c51ed6e7fab8e488d001a07772eeffaebb695071001`;
   result SHA-256
   `cd1f639efc25cf4559e37ac2250417737ed28665ba003cb001f19e6be8c4364f`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.1-dispatch.log`.
   The focused shard result was `98 passed, 3 failed, 57 warnings`, exit `1`.
   The three failures were claimed and later independently confirmed
   pre-existing on `fec6cb12`: envelope
   (`test_agent_delta_turn_result_produces_accepted_batch_only`),
   LawNode port (`test_diff_inverse_over_field_mode_link_and_node_edits`),
   and add_node replay
   (`test_diff_cumulative_replay_and_undo_roundtrip`).

4. **Post-implementation review — `T2.1-review`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.1 post-implementation review of commit 0716a8bc
   (one operation-admission gateway)`; role reviewer; route/resolved model
   `grok-4.6`; receipt `receipts/T2.1-review-receipt.json`; receipt SHA-256
   `1f4c9267942dd00657c501335b8d7efa31437b9bfb146115917e03a74f12a2de`;
   PID `48033`; `2026-08-21T17:08:29Z` → `2026-08-21T17:22:23Z`; exit `0`;
   base `0716a8bcc829b8a18149c1c39cfd8bbb05a39087`; no target, commits, or
   changed files; brief SHA-256
   `d65f7c9933ef33c87db69f1c05ab4d0ee3499c0d24d92ccc75bafb4ee92538d4`;
   result SHA-256
   `3c003d5a360c0979c08f058bb89529515b64c983c72727d05fbf5e46533e6d3e`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1-review.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.1-review-dispatch.log`.
   Disposition `correct`. Findings were:
   `T2.1-MUST-001` authority: `_interpret_ops`, `apply_batch`, and
   `require_known_schema_for_operation` discarded the gateway result, so
   rejected proposals could enter the accepted delta;
   `T2.1-MUST-002` authority: `verify_apply`/`lint_delta` honored only
   `missing_touched_schema`/`unsupported_op`, allowing other typed reasons
   to produce `ok=True`/`surviving`;
   `T2.1-MUST-003` schema: `snapshot=None` failed open, so
   layout/preview/session/accepted-batch-parse callers skipped
   `require_known_touched_schema`;
   `T2.1-MUST-004` authority: Python-source DSL `_InterpretRunner` bypassed
   the gateway;
   `T2.1-MUST-005` mechanical: routing proof was cosmetic (unused
   `_admit_operation` import, `_ = admit_operation`, and an
   `inspect.getsource` substring test);
   `T2.1-SHOULD-001` mechanical: `rejected_ops_are_invisible` was tautological
   and a second layout validator remained after the gateway.
   The focused-shard failures were independently classified pre-existing via
   a `git archive fec6cb12` base copy: HEAD `98 passed/3 failed`, base
   `93 passed/3 failed`, with the same three failure IDs.

5. **Revision — `T2.1-revision`.** Gate unset in the receipt; label
   `T2.1 [XHARD-REVISION] enforce the one operation-admission gateway on all
   consumers (MUST-001..005)`; role implementer; route/resolved model
   `grok-4.6`; receipt `receipts/T2.1-revision-receipt.json`; receipt SHA-256
   `b4ab06ce7b8590136b6fa58f0065d42047f2abd02b5dbf1f5dbc4978eb7291f0`;
   PID `48352`; `2026-08-21T17:23:24Z` → `2026-08-21T18:20:29Z`; exit `0`;
   base `0716a8bcc829b8a18149c1c39cfd8bbb05a39087`; commit
   `993cadd3cfa7760c4ef4954f9afaa44e48bf8898`
   (`fix(exec-spine): enforce admit_operation as sole admission authority`);
   14 changed files within the frozen allowance; brief SHA-256
   `437a9bf94d986e6690a77cca6098b694f47d8a60c7a5e1fce0c8b755aa831be1`;
   result SHA-256
   `2e639f263f7b91cd4da26c7497a42dfc06e2657af288b74d6c1a974f82b5a618`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1-revision.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.1-revision-dispatch.log`.
   Per-finding closure: MUST-001 binds `AdmissionRejected`, preventing IR
   and `landed_ops` commits while propagating `typed_reason` and
   `evidence_refs`; MUST-002 blocks `ok=True` and lint `surviving` for any
   typed rejection; MUST-003 fails closed on absent catalogs for
   schema-dependent operations and passes real snapshots from callers;
   MUST-004 makes `_InterpretRunner._apply` admit before
   `apply_edit_cow`; MUST-005 removes the unused import/binding and replaces
   cosmetic proof with behavioral consumption tests; SHOULD-001 makes
   `rejected_ops_are_invisible` a meaningful gate and removes the second
   layout admission validator. The focused shard was `102 passed, 3 failed,
   57 warnings`, exit `1`, with the same three pre-existing failure IDs.

6. **Revision re-review — `T2.1-revision-rereview`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.1 revision re-review of the complete card diff
   fec6cb12..993cadd3`; role reviewer; route/resolved model `grok-4.6`;
   receipt `receipts/T2.1-revision-rereview-receipt.json`; receipt SHA-256
   `b998fed83c9f6a24ea890341dbdf286dff650fbbdb1c02577661b5f5f20fc9cb`;
   PID `49532`; `2026-08-21T18:23:38Z` → `2026-08-21T18:40:35Z`; exit `0`;
   base `993cadd3cfa7760c4ef4954f9afaa44e48bf8898`; no target, commits, or
   changed files; brief SHA-256
   `c330febc0e5a280904a276815030f6528594a96f3af7ff2435029ddffbd52053`;
   result SHA-256
   `506c6a1fd2d65c16df4065a4d9a006ab1a0c79cbdd8eb34262b7815cf0a6a9dd`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1-revision-rereview.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record
   `g0/T2.1-revision-rereview-dispatch.log`. Disposition `continue`;
   MUST-001..005 and SHOULD-001 are all **CLOSED**, findings are none, and
   `JUDGMENT_REQUIRED: none`. The focused shard was independently
   re-classified pre-existing on `fec6cb12`: HEAD `102 passed/3 failed`,
   base `93 passed/3 failed`, same three failure IDs.

7. **Integration — `T2.1-integration`.** Gate unset in the receipt; label
   `T2.1-integration: apply reviewed 0716a8bc + 993cadd3, run T2.1 focused
   shard once, fast-forward push`; role integration; route
   `codex:gpt-5.6-luna`, resolved model `openai-codex/gpt-5.6-luna`; receipt
   `receipts/T2.1-integration-receipt.json`; receipt SHA-256
   `dd99e49257f8e28686dd1a184502ff65b9f6e3d8e131c508e5a69c03daf98059`;
   PID `49993`; `2026-08-21T18:45:29Z` → `2026-08-21T18:48:33Z`; exit `0`;
   base `993cadd3cfa7760c4ef4954f9afaa44e48bf8898`; no commits or changed
   files; brief SHA-256
   `7533ed37240fcd4db96cd3d3de35b37889d8d0cb6725dff6b1628a571160dd6b`;
   result SHA-256
   `63f513dfe33fe16af38336d1cc72a9c9376752315bd0a23420cd69f3f2d369a8`.
   Wrapper invocation: `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=codex:gpt-5.6-luna --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.1-integration.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.1-integration-dispatch.log`.
   Verified lineage `acec7cc1 → f36ed7ed → fec6cb12 → 0716a8bc →
   993cadd3`. The T2.1 focused shard ran exactly once:
   `102 passed, 3 failed, 57 warnings`, exit `1`, same three pre-existing
   failure IDs; stdout digest `82f110ac…`. Integration fast-forward pushed
   `acec7cc1..993cadd3` via
   `git push origin HEAD:fixer/workflow-execution-spine-consolidation`;
   `remote_after == 993cadd3cfa7760c4ef4954f9afaa44e48bf8898`.

### T2.1 disposition, revision closure, and handoff

- **JR resolution:** `T2.1-JR-001` was resolved by freezing the concrete
  allowance list with `forbidden: []`; `T2.1-JR-002` was resolved by routing
  layout operations through the same `admit_operation` gateway rather than
  creating a second layout admission function. The pre-code stop was
  therefore handled and followed by the recorded re-review `continue`.
- **Finding closure:** the single revision closed MUST-001 (gateway result is
  authoritative), MUST-002 (all typed reasons reject), MUST-003 (missing
  catalog/schema-dependent operations fail closed and callers pass snapshots),
  MUST-004 (Python-source DSL admits first), MUST-005 (behavioral routing
  proof), and SHOULD-001 (meaningful rejected-invisibility gate and no second
  layout admission validator). The independent re-review found none open.
- **Focused evidence:** the three pre-existing delta-contract failures remain
  tracked in `test-shards.json`: envelope,
  `test_agent_delta_turn_result_produces_accepted_batch_only`; LawNode port,
  `test_diff_inverse_over_field_mode_link_and_node_edits`; and add_node
  replay, `test_diff_cumulative_replay_and_undo_roundtrip`. They are outside
  T2.x mutation scope and are not relabeled as T2.1 regressions.
- **Integration proof:** the integrated local and remote target are both
  `993cadd3cfa7760c4ef4954f9afaa44e48bf8898`; the only prior-card push was
  the integration fast-forward above. This evidence recording does not push.
- **Residual risks and recurrence rules:** every execution-log edit requires
  refreshing `manifest.tasks[5].recovery_note.sha256`; every
  `test-shards.json` edit requires refreshing every matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256`. Both rules are
  validator-enforced. The layout digest helpers
  `assert_layout_operation_envelope` and `compute_layout_operation_digest`
  still default `snapshot=None` but are integrity paths; `set_node_geometry`
  without a snapshot fails closed. `add_group`, `set_group_geometry`, and
  `remove_group` remain shape-admitted without a catalog because T1.2 treats
  group IDs as optional. Live providers without a frozen `.snapshot` skip
  `require_known_touched_schema` when working IR is present, although
  `_validate_one` still runs; layout group identity is checked only when a
  working IR is supplied. H3-overlap-narrow remains STOPPED pending operator
  direction (wrapper pre-code `JUDGMENT_REQUIRED`, `de75b418`), outside T2.x
  and deferred until before the T3.1/T3.2 read-only windows per §15/Grok
  ordering. The pre-existing validator gap
  `_iter_digest_refs` silently skips malformed non-64-hex digest strings;
  it remains tracked per adjudication A as a candidate future XHARD card.
- **Controls:** no other file, receipt, protected state, branch, or ref
  changed in this evidence recording; no push, merge to `main`, promotion,
  live/model/runtime/provider call, secret access, wrapper dispatch, review,
  validator change, or product/test run occurred here. No receipt is
  committed. The integration push and focused-shard run above are historical
  T2.1 integration evidence.
- **Next unblocked card:** `T2.2` `[XHARD]` Closed checkpoint and typed
  terminal projector (freeze the transition table before implementation;
  both modes use one projector). Grok implementer with Grok pre-code
  `[XHARD-REVIEW]` per plan §6 G2 / §8 lifecycle; one review per phase per
  §13/§14.
- **Evidence commit:** one coherent commit authored by
  `POM <peter@omalley.io>` with message prefix `docs(exec-spine):`; exactly
  the three allowed files are changed. The required read-only evidence
  validator runs after this append; no tests are run by the evidence agent.

- **Validator proof:** The required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  exited `0` and emitted
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`;
  stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests were run by this evidence recorder.

## G2 / T2.2 — evidence-log T2.2 card sequence and disposition (2026-08-21)

### Ordered T2.2 receipt register

1. **Pre-code review — `T2.2-precode-review`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.2 closed checkpoint and typed terminal projector
   pre-code contract review`; role `reviewer`; model route/resolved model
   `grok-4.6`; receipt
   `receipts/T2.2-precode-review-receipt.json`; receipt SHA-256
   `019b383349515c87930c0693bcaf60b300382ca1097098c13f848074c640a226`;
   brief SHA-256
   `24b9ef27f5ed48d3d1b6a68f9dfa8213ab911fbe73a7c68e103adf0cc3f24c29`;
   result SHA-256
   `7fc99c4d970efb56dc7126dac59f80e1d9ac9d605ccbf81b2656039e609633cf`;
   PID `50543`; `2026-08-21T19:00:37Z` →
   `2026-08-21T19:21:52Z`; exit `0`; base
   `48f81d64a74885548c5793dffd552eec60d626a0`; no commits or changed files.
   Wrapper invocation:
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6
   --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2-precode-review.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record
   `g0/T2.2-precode-review-dispatch.log`. Disposition `continue` with binding
   conditions: freeze the seven-row transition table verbatim, use one
   mode-neutral projector, preserve T2.1's `AdmissionAllowed` authority, and
   keep H3 outside T2.2.

2. **Implementer first run — `T2.2`.** Gate unset in the receipt; label
   `T2.2 [XHARD] Closed checkpoint and typed terminal projector`; role
   `implementer`; model route/resolved model `grok-4.6`; receipt
   `receipts/T2.2-receipt.json`; receipt SHA-256
   `f714fb5f355168b3f690cd713278b8d6b60c6bbf7f5e298748a83df8f6c73286`;
   brief SHA-256
   `0860abb6ae3497e4e8a22182fc8440f2cc529c4e9e2e6bb9392aaae832ff5d5f`;
   result SHA-256
   `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
   (empty stdout); PID `51098`; `2026-08-21T19:27:52Z` →
   `2026-08-21T20:27:52Z`; exit `124` from the wrapper per-dispatch timeout;
   base `48f81d64a74885548c5793dffd552eec60d626a0`; no commit. The wrapper
   invocation was
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6 --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.2-dispatch.log`. The
   `receipts/wrapper-death-note-t22-implementer.json` recovery note
   (receipt SHA-256
   `44128fb0812dd72ecef370cf8eae69d46d131ad4feeccd20811d2afbc89305e8`)
   records F6 `LAUNCHER-TIMEOUT`: wrapper PID `51092`, launcher child PID
   `51098`, empty result, and 14 modified allowance files left uncommitted.
   Per the F6 lesson, the same phase was re-dispatched under a new task ID
   after restoring the partial paths; this was one interrupted run, not a
   second review or a second card.

3. **Implementer rerun — `T2.2-rerun`.** Gate unset in the receipt; label
   `T2.2 [XHARD] Closed checkpoint and typed terminal projector (rerun after
   launcher timeout)`; role `implementer`; model route/resolved model
   `grok-4.6`; receipt `receipts/T2.2-rerun-receipt.json`; receipt SHA-256
   `225a00a969f4c094a0bb89e6e49a13227a366beeb2eee4745383dccf3047c5e4`;
   brief SHA-256
   `38d94d227a19931af19cae3904d6ddb4570ee18a097ed195006de81172a151b7`;
   result SHA-256
   `8e191d314861519ba811ee83a2a3e8b6214ef09caeaf32b9a6930179971852b7`;
   PID `52451`; `2026-08-21T20:30:51Z` →
   `2026-08-21T21:12:24Z`; exit `0`; base
   `48f81d64a74885548c5793dffd552eec60d626a0`; commit
   `40d1f8e5d1f322e8de2c66e1b8fd9d292ec6890d`
   (`feat(exec-spine): add closed checkpoint and typed terminal projector`);
   16 files in the frozen implementation allowance. Wrapper invocation:
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6
   --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2-rerun.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.2-rerun-dispatch.log`.
   The owned focused subset exited `0` with `57 passed`. The full listed
   shard was `354 passed, 2 skipped, 27 failed`; sampled failures
   (`PassThroughImage` `unknown_target`,
   `_find_link_to_target_in_ledger` missing, and `_fresh_v2_apply_turn`
   `receipt.is_applyable is False`) reproduced identically at detached base
   `48f81d64` under `/tmp/t22-rerun/base-48f81d64`, so they are pre-existing
   T2.1 admit/schema failures outside T2.2.

4. **Post-implementation review — `T2.2-review`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.2 post-implementation review of commit 40d1f8e5
   (closed checkpoint and typed terminal projector)`; role `reviewer`; model
   route/resolved model `grok-4.6`; receipt
   `receipts/T2.2-review-receipt.json`; receipt SHA-256
   `c29912880dfecc4ba7f2ad5fc79912d70ba081e50db2ad49bc35d78b43e593f1`;
   brief SHA-256
   `2ea3594bbee555b290bffaa07d794d64e7451e12f32c8ed272494ac673a996f6`;
   result SHA-256
   `dfc59c0d53f8d87566f92dec3c01be02c44adb4fe57b4edb1fd0236a77c75ae5`;
   PID `53607`; `2026-08-21T21:22:17Z` →
   `2026-08-21T21:43:00Z`; exit `0`; base
   `40d1f8e5d1f322e8de2c66e1b8fd9d292ec6890d`; no commits or changed files.
   Wrapper invocation:
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6
   --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2-review.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.2-review-dispatch.log`.
   Disposition `correct`, `JUDGMENT_REQUIRED: none`, with three MUST and
   three SHOULD findings. MUST-001: `recover_terminal_checkpoint` ignored
   `accepted_batch`, so stamped applied durables recovered as
   `undetermined` without deltas. MUST-002: the frozen
   `ImplementationResult.durable_response` nested `mappingproxy` caused the
   durable projector to raise `TypeError`, dropping row-6 applied work in
   both modes. MUST-003: rejected stamps left public `candidate`, `graph`,
   and `accepted_batch` visible instead of audit-only. SHOULD-001 identified
   manufactured `AdmissionAllowed()` for applied close; SHOULD-002 identified
   candidate/edit narrative inference without replay proof; SHOULD-003
   identified that focused tests had not exercised the stamped-durable
   production path.

5. **Revision — `T2.2-revision`.** Gate unset in the receipt; label
   `T2.2 [XHARD-REVISION] repair stamped-durable recover, freeze-safety, and
   rejected-candidate authority (MUST-001..003)`; role `implementer`; model
   route/resolved model `grok-4.6`; receipt
   `receipts/T2.2-revision-receipt.json`; receipt SHA-256
   `c102accaa25cc112f0a2e79b0d94fac4aaa03f930defb55a14cd1773b1e6f8a8`;
   brief SHA-256
   `b40fbd3391ce0bd4df09a4ba6133890d2f3397efdb7603ce2c8a81017302938e`;
   result SHA-256
   `827de00e6e9044ce164c313d86f039c75844d03605acaa53406cc8df096cd740`;
   PID `54853`; `2026-08-21T21:53:25Z` →
   `2026-08-21T22:37:35Z`; exit `0`; base
   `40d1f8e5d1f322e8de2c66e1b8fd9d292ec6890d`; commit
   `24a42b14e99dea9f4096fc210fba293e8c901f05`
   (`fix(exec-spine): repair stamped-durable recover, freeze, and authority
   paths`); 8 files in the frozen allowance. Wrapper invocation:
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6
   --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2-revision.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.2-revision-dispatch.log`.
   Per-finding closure: MUST-001 extracts operations from
   `accepted_batch[*].op` and recovers stamped applied plus receipt as
   `applied`, with operations and Apply eligibility. MUST-002 thaws
   JSON-ish `mappingproxy`/tuple values before deepcopy, making the
   projector pickle-safe without widening to `executor/contracts.py`.
   MUST-003 moves rejected candidate/graph/accepted-batch data under
   `audit["rejected_candidate"]` and removes the public keys. SHOULD-001 is
   addressed as the explicit residual fact
   `admission_residual=t2.3_persistence_carries_real_admission`, while close
   still requires an `AdmissionAllowed` token; SHOULD-002 requires replay or
   receipt evidence before inferring `applied`; SHOULD-003 adds eight
   production-path tests. The listed shard was `27 failed, 362 passed,
   2 skipped`, exit `1`, with the same pre-existing failure set.

6. **Revision re-review — `T2.2-rereview`.** Gate `G2`; label
   `G2 [XHARD-REVIEW] T2.2 re-review of the complete card diff
   48f81d64..24a42b14 after revision`; role `reviewer`; model
   route/resolved model `grok-4.6`; receipt
   `receipts/T2.2-rereview-receipt.json`; receipt SHA-256
   `c1a4e2a50af110dc746922c6d238dfc501b27c975a05a42cf05847de14538cfe`;
   brief SHA-256
   `cb036697525adba61da536782499a78ae767a7f6ebcde815fac440a290501e59`;
   result SHA-256
   `f44e06ad74629d34879d26a05e82d992ccd2e25daf941ea652e2be8c090e9081`;
   PID `57135`; `2026-08-21T22:38:07Z` →
   `2026-08-21T23:00:43Z`; exit `0`; base
   `24a42b14e99dea9f4096fc210fba293e8c901f05`; no commits or changed files.
   Wrapper invocation:
   `/root/.codex/skills/subagent-launcher/launch_omp_agent.py
   --model=grok-4.6
   --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2-rereview.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record `g0/T2.2-rereview-dispatch.log`.
   Disposition `correct`; `JUDGMENT_REQUIRED: none`. MUST-001..003 are
   **CLOSED**; SHOULD-001 is **ADDRESSED** with the recorded
   `t2.3_persistence_carries_real_admission` residual and the required close
   token; SHOULD-002 and SHOULD-003 are **CLOSED**. The frozen seven-row
   transition table is verbatim, one mode-neutral projector remains, and
   the T2.1 gateway is consumed rather than duplicated. This is the one
   independent re-review allowed after the one revision.

### T2.2 disposition, revision closure, and handoff

- **Card disposition:** `PASS`/complete. The sequence is pre-code
  `continue`, one interrupted implementer run (exit `124`, F6 wrapper cap),
  rerun commit `40d1f8e5`, post-implementation `correct` review with three
  MUST and three SHOULD findings, one revision commit `24a42b14`, and one
  independent re-review `correct` closing all findings. One review per phase
  per operator §13/§14/§17 was respected; no stacked adjudication occurred.
- **Focused evidence and the 27 pre-existing IDs:** the focused T2.2 shard
  is recorded as `362 passed, 27 failed (pre-existing), 2 skipped`, exit `1`.
  The 27 failures reproduced at detached base `48f81d64` and are outside
  T2.2 scope: `test_porting_edit_session.py::TestRenderEditRerenderIdentity::test_session_rerender_keeps_locked_names_after_topology_change`;
  `TestEditSessionResolution::test_apply_batch_resolves_bare_rhs_when_exactly_one_schema_output_matches`;
  `TestEditSessionPrimitiveLowering::test_original_link_endpoint_uses_litegraph_origin_slot`;
  `test_apply_batch_successful_add_and_rewire_still_commits`;
  `test_apply_batch_lowers_schema_less_dict_widget_assignment_to_set_node_field_op`;
  `test_apply_batch_upsert_link_removes_stale_duplicate_target_links`;
  `test_apply_batch_exec_accepts_semantic_io_names_for_new_node_wiring`;
  `test_apply_batch_exec_accepts_semantic_io_names_for_existing_node_assignments`;
  `test_apply_batch_infers_true_splice_anchor_from_two_line_rewire`;
  `test_apply_batch_does_not_treat_simple_new_link_as_splice`;
  `test_apply_batch_places_five_node_cluster_in_dataflow_order`;
  `test_near_inherits_group`; `test_pipeline_cluster_shares_group`;
  `test_splice_prefers_downstream_group`;
  `test_splice_neither_has_group_ungrouped_with_diagnostic`;
  `TestDoneGateAByteFaithfulness::test_done_candidate_matches_working_ui_byte_for_byte`;
  `TestDoneGateAGuardFailure::test_done_detects_missing_landed_ops`;
  `test_done_detects_external_working_ui_mutation`;
  `test_done_diagnostics_include_teaching_hints`;
  `TestDoneGateCSummary::test_summary_gate_failure_includes_error_diagnostics`;
  `TestSessionDeltaHistory::test_cas_noop_batch_still_records_source_and_diff_stays_minimal`;
  and the six `test_comfy_nodes_agent_session.py` cases:
  `test_prepare_cas_records_receipt_without_advancing_baseline`,
  `test_prepare_rejects_stale_typed_evidence_candidate_plan_and_generation`,
  `test_finalize_requires_matching_nonce_and_verified_post_apply_hash_before_baseline_advance`,
  `test_finalize_uses_typed_semantic_postcondition_not_raw_native_widget_carriers`,
  `test_rollback_restores_prepare_time_baseline_from_nonterminal_state`, and
  `test_reconcile_returns_durable_receipts_and_repairs_index`. Their observed
  classes are the T2.1 `PassThroughImage`/admit-schema, ledger-link,
  snapshot/delta-contract, and `_fresh_v2_apply_turn` `receipt.is_applyable`
  failures; none was introduced by T2.2.
- **Residual risks and recurrence rules:** execution-log edits require
  refreshing `manifest.tasks[5].recovery_note.sha256` to the current full-log
  SHA-256. `test-shards.json` edits require refreshing every matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256` to the current shard-file
  SHA-256. T2.3 owns durable submit/delta/candidate/hash persistence and the
  crash-after-receipt-before-projection matrix; the real `admit_operations`
  outcome is not on the stamp, residual
  `t2.3_persistence_carries_real_admission`. Recover short-circuit
  `core.py:1769-1773` does not thread `request_graph`; stamped
  `authority_rejected` durables lacking `original_graph` project `{}` as
  original graph, with the public rejected product absent and Apply
  ineligible. Browser apply UI still keys on `no_candidate`/`candidate`
  (outside allowance), so consumers must tolerate MUST-003's absent public
  keys. The 27 pre-existing listed-shard failures are unchanged. H3 overlap
  narrow remains STOPPED pending operator direction (wrapper pre-code
  `JUDGMENT_REQUIRED`, `de75b418`); deferred, and the remaining run will
  serialize batches so H3 is not needed for parallelism. The pre-existing
  validator gap `_iter_digest_refs` silently skips malformed non-64-hex
  digest strings; it remains tracked per adjudication A.
- **Controls:** this evidence append changes only the three allowed evidence
  files. No receipt, protected state, branch, or other file is changed; no
  push, merge, promotion, live/model/runtime call, secret access, wrapper
  dispatch, review, validator change, or product/test run is performed by
  this evidence recorder.
- **Next unblocked card:** after the T2.2 integration push, §18 comprehensive
  pre-review `PRE-REVIEW-REMAINING`: one Grok/stealth `[XHARD-REVIEW]` of
  the complete remaining plan T2.3→G7 plus the §16 wrapper-timeout raise,
  §18 finale flow, and §19 validator-routing amendment. It must return
  `continue` before implementation resumes; subsequent batches follow §18.

### T2.2 integration disposition, closure, and handoff

- **Integration register entry 7 — `T2.2-integration`.** Gate unset in the
  receipt; label `T2.2-integration: apply reviewed chain, run T2.2 focused
  shard once, fast-forward push`; role `integration`; model route/resolved
  model `stealth/ox-alpha`; receipt
  `receipts/T2.2-integration-receipt.json`; receipt SHA-256
  `332c21d81d7c33ba1d8f74aec5639768f55f57c21b0760e8e41e303cda6284c8`;
  brief SHA-256
  `20a369b6b061161f7c91bfe64dee0940092c3c171e2d8fad3fae384017a0136f`;
  result SHA-256
  `33546317d52e8b0c2c6f485a1968a1d5463c750e55e01e3315fa74d61c51dc92`;
  wrapper PID `58438`; `2026-08-21T23:17:13Z` →
  `2026-08-21T23:28:11Z`; exit `0`; base
  `c83d2e59cae670c056564f297061062b0a880763`; no commits and zero changed
  files under the read-only allowance. Wrapper invocation:
  `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
  --model=stealth/ox-alpha
  --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/T2.2-integration.md
  --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
  --timeout=3600`; dispatch record `g0/T2.2-integration-dispatch.log`.
- **Lineage verified, then pushed atomically:** the parent chain is
  `993cadd3cfa7760c4ef4954f9afaa44e48bf8898` →
  `48f81d64a74885548c5793dffd552eec60d626a0` →
  `40d1f8e5d1f322e8de2c66e1b8fd9d292ec6890d` →
  `24a42b14e99dea9f4096fc210fba293e8c901f05` →
  `5399a5aa8ae441f55410f30db4b4aae7faa3a98f` →
  `c83d2e59cae670c056564f297061062b0a880763`; all six objects report type
  `commit` via `git cat-file -t`; `git rev-list` showed exactly five commits
  ahead of the remote (`48f81d64`, `40d1f8e5`, `24a42b14`, `5399a5aa`,
  `c83d2e59`); `git merge-base --is-ancestor` proved the push a
  fast-forward.
- **Focused shard ran exactly once at the integrated state:** command
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
  tests/test_terminal_checkpoint.py tests/test_porting_edit_kernel.py
  tests/test_executor_threaded_edits.py tests/test_porting_edit_session.py
  tests/test_authority_receipts.py
  tests/test_comfy_nodes_agent_session.py`; exit `1` with
  `27 failed, 362 passed, 2 skipped, 136 warnings in 203.85s`; stdout
  SHA-256
  `e27ebc030da3ad6918f70737ab43770767cdd6114bf7dbbf6bb42fb5484edd08`;
  stderr SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
  (empty); scratch preserved at `/tmp/t22-integration/shard.stdout` and
  `/tmp/t22-integration/shard.stderr`. The 27 FAILED nodeids were
  `comm -3`-identical against the recorded pre-existing set (review table
  at `g0/T2.2-review-dispatch.log`, independently confirmed at base
  `48f81d64`), and assertion classes match row-for-row: 21
  `test_porting_edit_session.py` admit/schema/done-gate cousins and six
  `test_comfy_nodes_agent_session.py` `receipt.is_applyable is False`
  cases. No new or different failure appeared.
- **Fast-forward push:** `git push origin
  HEAD:fixer/workflow-execution-spine-consolidation` advanced the remote
  with fast-forward range notation `993cadd3..c83d2e59` and no force; the
  post-push `git ls-remote` returned
  `remote_after == c83d2e59cae670c056564f297061062b0a880763`. The
  integration SHA is `c83d2e59cae670c056564f297061062b0a880763`.
- **Card CLOSED end-to-end:** pre-code review returned `continue`; the
  implementer first run was interrupted (exit `124`, wrapper-death-note
  `t22-implementer`); rerun commit `40d1f8e5`; post-implementation review
  opened MUST-001..003 plus SHOULD-001..003; revision commit `24a42b14`;
  re-review `correct` closed all findings; evidence commit `c83d2e59`;
  integration pushed to remote `c83d2e59`. No phase of T2.2 remains open.
- **Directive-20 route-fix lineage note:** commit
  `5399a5aa8ae441f55410f30db4b4aae7faa3a98f`
  (`fix(exec-spine): route all wrapper model routes to stealth/ox-alpha
  (operator directive 20)`) is part of the pushed lineage and is
  operator-authorized; its review is folded into the §18 comprehensive
  pre-review scope rather than dispatched as a separate review. Cherry-
  picking or reordering any of the six commits, or excluding `5399a5aa`,
  was forbidden and was not done.
- **Residual risks:** the 27 listed-shard failures remain open upstream
  debt owned outside T2.2 (the T2.1 admit/schema cousins), with counts
  reconfirmed by the integration run. The pushed lineage is immutable
  history: no commit may be cherry-picked out of order or dropped. The
  carried T2.2 residuals stand unchanged: recover short-circuit
  `core.py:1769-1773` does not thread `request_graph`; browser apply UI
  still keys on `no_candidate`/`candidate` outside the allowance;
  `t2.3_persistence_carries_real_admission`; H3-overlap-narrow remains
  STOPPED pending operator direction (`de75b418`) with remaining batches
  serialized; the validator gap `_iter_digest_refs` silently skipping
  malformed non-64-hex digest strings remains tracked per adjudication A;
  execution-log edits require refreshing
  `manifest.tasks[5].recovery_note.sha256`, and `test-shards.json` edits
  require refreshing matching
  `manifest.tasks[5].evidence_links[*].sha256` and
  `manifest.tasks[6].shard_integrity.sha256`.
- **Controls:** this evidence append changes only the three allowed
  evidence files in one coherent commit authored by
  `POM <peter@omalley.io>`. No receipt, protected state, branch, or other
  file is changed; no push, merge, promotion, live/model/runtime call,
  secret access, wrapper dispatch, review, validator change, or product/
  test run is performed by this evidence recorder; no receipt is
  committed. The lineage verification, focused shard run, and push above
  are historical `T2.2-integration` evidence.
- **Next unblocked card:** `PRE-REVIEW-REMAINING` — the §18 comprehensive
  pre-review (`stealth/ox-alpha` `[XHARD-REVIEW]`) of the complete
  remaining plan T2.3→G7 plus the §16 wrapper-timeout raise (3600→7200),
  the finale amendment (validator 100→50 leg receipts; T7.2/G7 wording:
  50 scenarios split 25 staged + 25 threaded = 50 legs at concurrency 10;
  smoke = final-five ×2 modes = 10 legs pre-finale), and the directive-20
  route-fix review. It must return `continue` before implementation
  resumes; subsequent batches follow §18.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## §18 comprehensive pre-review — PRE-REVIEW-REMAINING disposition (2026-08-21)

### PRE-REVIEW-REMAINING register and verdict

1. **Comprehensive pre-code review — `PRE-REVIEW-REMAINING`.** Gate `G7`
   in the receipt; scope is the ONE §18 comprehensive pre-review of the
   complete remaining plan T2.3→G7 plus the §16 wrapper-timeout raise, the
   finale amendment, the §19 validator-routing amendment, and the
   directive-20 route-fix verification; label
   `§18 ONE comprehensive pre-review: complete remaining plan T2.3→G7 +
   §16 timeout raise + finale amendment + validator routing + directive-20
   route fix + H3 overlap adjudication`; role `reviewer`; model
   route/resolved model `stealth/ox-alpha`; receipt
   `receipts/PRE-REVIEW-REMAINING-receipt.json`; receipt SHA-256
   `6b6fc6df129a4503be06411cf93d137f169aa3c27aeb79aa5f515d37b6ac300c`;
   brief SHA-256
   `6f698d9c6033aeeb5d839abec33a63860751a7f3d652018a234cf2e0a4258859`;
   result SHA-256
   `eb8660fe57320faa043cd59d3748e0109ce035801da080e41bfe9362a4d1d7e1`;
   wrapper PID `59206`; `2026-08-21T23:40:32Z` →
   `2026-08-21T23:50:38Z`; exit `0`; base
   `d9459c80635909e13d19f69e1c3566e0114280d9`; no commits and no changed
   files under the read-only allowance (`allowed: []`,
   `forbidden: ["**"]`). Wrapper invocation:
   `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py
   --model=stealth/ox-alpha
   --query-file=/workspace/vibecomfy-exec-spine-20260820/g0/PRE-REVIEW-REMAINING.md
   --project-dir=/workspace/vibecomfy-exec-spine-20260820/exec-spine
   --timeout=3600`; dispatch record
   `g0/PRE-REVIEW-REMAINING-dispatch.log`.
- **Verdict:** `continue` — `JUDGMENT_REQUIRED: none`, `commit: none`,
  `changed_files: []` — with thirteen binding conditions. Card contracts
  are sound under the conditions: A (T2.3→G7 card contracts), B
  (allowances/batch boundaries plus H3 adjudication), C (schema closure
  and terminal semantics preserved), D (new §18 finale flow coherent),
  and E (directive-20 route fix `5399a5aa` verified correct and safe:
  both legacy routes remap to `(HERMES_LAUNCHER, "stealth/ox-alpha")`,
  unknown routes rejected outright, no conditional fallback). The review
  also recorded one base-state deviation: local HEAD `d9459c80` is one
  docs-only commit ahead of remote `c83d2e59` → Condition 1.

### Binding conditions (13, binding on remaining batches)

- **C1 — push base:** local HEAD `d9459c80` (docs-only T2.2 disposition
  commit) is one ahead of remote `c83d2e59`; the next integration push
  must include it, and subsequent briefs must cite the pushed SHA as the
  latest reviewed integration base.
- **C2 — §16 scope:** change only the argparse default at
  `run_workflow_execution_spine_agent.py:564` (3600→7200); stop emitting
  explicit `--timeout=3600` in orchestrator/brief templates (plan §10
  examples are stale), else the raise is inert. Focused proof:
  a `VCSPINE_FAKE_LAUNCHER` stub sleeping >3600s completes exit 0.
- **C3 — validator routing:** `_route_for_label` (135–140) and the G7
  check (150–151) become set-membership accepting
  `{grok-4.6, codex:gpt-5.6-luna, stealth/ox-alpha}` per label class;
  historical records keep validating, new records dispatch as
  `stealth/ox-alpha` per §20; must land in Batch 0/1 before the first
  post-amendment receipt is recorded.
- **C4 — validator finale count:** `check_live_run` (324–342) requires
  exactly 50 unique leg receipts at concurrency 10 with the recorded
  25/25 staged/threaded split; the smoke run is recorded
  `authoritative: false` / `non_authoritative` so `LIVE_RUN_SINGLETON`
  ignores it (line 326 already excludes that status).
- **C5 — harness split support:** extend
  `compare_pipeline_modes.run_comparison` minimally for one-invocation
  25/25 execution with a frozen, digested scenario→mode map recorded in
  the live_run and per-leg assessments emitted; `compare_pair`
  skipped/adjusted for single-leg scenarios; do NOT alter deep-copy
  isolation (763), the session_id ban (745–749), manifest-order
  reconstruction (790–795), or validate-only zero-model-call behavior
  (153–223).
- **C6 — smoke path untouched:** the smoke uses the current paired path
  with the final5 manifest (10 legs); validate-only first with
  `model_calls: 0`; smoke is validation only and never counted toward the
  finale.
- **C7 — registry lock fix (required before any parallel window is
  used):** shrink `_registry_guard`'s critical section (unlock+close
  after candidate write, ~307) AND make `_registry_release` take LOCK_EX
  around its read-modify-write (328–337); both halves together or not at
  all.
- **C8 — overlap predicate:** keep same-worktree ⇒ unconditional overlap
  (`_allowances_overlap`, 246–251); no read-only exemption for
  same-worktree pairs.
- **C9 — readonly flag contract (if introduced):** empty `allowed`
  accepted only with `readonly=true`; readonly exemptions apply only
  across distinct worktrees; wrapper flags `ALLOWANCE_VIOLATION` for any
  changed file on a readonly registration.
- **C10 — batch/gate fusion:** batch reviews discharge the co-terminous
  gate reviews per the B1–B6 mapping below; no per-card pre/post reviews;
  must-findings fixed in the next batch or batch revision; up to 3 end
  reviews routed `stealth/ox-alpha` precede the final runs.
- **C11 — closure/terminal invariants carried forward:** T3.1's
  durable-resume owner names the T2.2 checkpoint/receipt schema as its
  touched closure; T4.2/T4.3 project terminal state exclusively through
  the T2.2 mode-neutral projector; T3.2's persisted correction is
  audit-only, never public candidate/graph/accepted_batch; T5.2
  `undetermined` strictly on missing/contradictory evidence.
- **C12 — split freeze and honest reporting:** scenario→mode assignment
  fixed and digested before T7.2; report presents smoke and finale scores
  separately with per-leg product pass/fail/undetermined; no second
  authoritative finale; the §12 final-five waiver and §18 smoke waiver
  are the only active waivers.
- **C13 — hygiene rider (non-blocking):** fold removal of dead
  `GROK_LAUNCHER` (43) and the unimported `Iterable` annotation on
  `_receipt_files` (189) into the Batch 0/1 wrapper touch — no dedicated
  card.

### Batch decomposition B0–B6 with gate fusion

```
B0 (infra, first commits of Batch 1): §16 timeout raise (C2) ·
    validator routing/count amendments (C3, C4) · registry lock fix (C7) ·
    overlap predicate (C8/C9) · hygiene rider (C13)
B1: T2.3                        → batch review doubles as G2
B2: T3.1 + T3.2                 → G3      (read-only retry/protocol inventories may run concurrently)
B3: T4.1 → T4.2 → T4.3          → G4      (adapter inventories may overlap)
B4: T5.1 → T5.2 → T5.3 → T5.4 → T5.5 → G5   (test-shard inventory may overlap final G5 review)
B5: T6.1 → T6.2 → T6.3          → G6
B6: T7.1 → T7.2 → T7.3          → ≤3 end reviews (stealth/ox-alpha) + smoke loop + authoritative finale
```

Intra-batch order follows §7's serial edges; serialization boundaries are
exactly the gates; the three §7 read-only windows are preserved; no
per-card loops (must-findings fixed in next batch or batch revision,
C10). The Condition-5 harness extension lands in the Batch 6 window but
is implemented and validate-only-tested alongside the T7.1 preflight.

### Finale mechanics confirmed by the pre-review

- Smoke works unmodified today: final5 manifest × both PIPELINE_MODES =
  10 legs; `threaded_comparison_manifest_final5.json` validates and its
  digests match validator `FINAL_FIVE`.
- The authoritative 50-leg split does NOT fit the current harness:
  `run_comparison` hard-runs both modes per entry and `compare_pair`
  requires both legs → Condition 5 extension needed in the Batch 6
  window. Two half-manifest process invocations were considered and
  rejected (breaks the ONE-authoritative-invocation rule and the
  singleton live_run record).
- final50 verified: 50 entries, 50 unique ids, 50 unique locked digests,
  and `entries[:5] == final5['entries']` byte-for-byte (final-five
  immutability holds).
- Consequence accepted: with a split finale there are no staged/threaded
  pairs in G7; locked-core comparability comes from the smoke run, so the
  report must present smoke (10 legs, both modes) and finale (50 legs)
  scores separately and honestly (C12).

### H3 STOP resolution (operator escalation answered by this pre-review)

- **Lock hold CONFIRMED real hazard:** `_registry_guard` acquires
  `fcntl.flock(LOCK_EX)` (wrapper line 259) and returns with the lock
  still held (308), released only in `run()`'s finally via
  `_registry_release` (752); every other wrapper invocation blocks at
  registration for the entire child runtime, the dead-PID sweep cannot
  fire while any wrapper lives, and all §7 parallel windows are impossible
  today → becomes Condition 7 (both-half registry lock fix).
- **Overlap predicate ADJUDICATED conservative, not contradictory:** keep
  same-worktree unconditional overlap (246–251); H3's proposed read-only
  same-worktree exemption is REJECTED → Condition 8.
- **Snapshot hazard confirmed but contained:** the before/after whole-tree
  snapshot diff would false-flag a same-worktree concurrent mutator, but
  §8 step 1 gives every card a fresh clean worktree, snapshots walk
  `project_dir` only, `.git` is pruned, and the shared evidence dir is
  excluded — the hazard fires only for same-worktree concurrency, which
  the landed rule unconditionally rejects, and does not block plan §7
  cross-worktree read-only windows.
- The H3-overlap-narrow card is superseded by Conditions 7–9; the H3 stop
  is thereby adjudicated/resolved, and the wrapper touch (lock fix plus
  C13 hygiene) lands in Batch 0/1. If Condition 7 slips, serializing
  batches remains the acceptable fallback (§7 grants permission, not
  obligation).

### Residual risks carried from the pre-review

- Registry fix concurrency bug if only one half lands: guard-side-only
  shrink leaves `_registry_release`'s unlocked RMW racing under shortened
  locks (lost deletions, zombie allowances) — C7 is one atomic unit.
- §16 inertness from any surviving explicit `--timeout=3600` in
  orchestrator templates — audit template sites, not just the default.
- Validator membership sets permit legacy-route reuse in new records;
  §20 compliance rests on dispatch discipline plus batch-review
  spot-checks of `model_route` fields.
- Harness split extension must land with the T7.1 preflight and keep the
  smoke path byte-identical.
- `resolved_model` receipt fidelity depends on the hermes launcher
  printing `resolved=` on stderr; until verified once against real output,
  end reviews should not treat `resolved_model` as independent
  model-identity proof.
- Unpushed `d9459c80`: digest pins inside the manifest
  (`tasks[5].recovery_note.sha256`, shard-integrity pins) must stay
  consistent with the pushed branch at next integration (C1).

### Next unblocked card

Batch 1 implementation per §18 plus the pre-review's B0/B1 split: B0
infra first commits (C2 §16 timeout raise, C3 validator routing, C4
validator finale count, C7 registry lock fix, C8/C9 overlap, C13 hygiene),
then B1 = T2.3 (replay/concurrency persistence, plan lines 384–406), then
ONE batch review doubling as G2 (C10), then integration push including
`d9459c80` (C1), then evidence recording and validator.

### Controls

This evidence append changes only the three allowed evidence files in one
coherent commit authored by `POM <peter@omalley.io>`. No receipt,
protected state, branch, or other file is changed; no push, merge,
promotion, live/model/runtime call, secret access, wrapper dispatch,
review, validator change, or product/test run is performed by this
evidence recorder. No receipt is committed; the reviewed receipt stays an
untracked run artifact. The wrapper records this recorder's own `end_ts`
and receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## Batch 1 implementer — BATCH1-IMPLEMENTER disposition (2026-08-22)

### BATCH1-IMPLEMENTER register and verdict

- **Task/label/role/route:** `BATCH1-IMPLEMENTER` / no gate / `Batch 1
  implementer: B0 infra (timeout raise, validator routing+count, H3 lock
  fix, hygiene) + B1 T2.3 replay/concurrency` / implementer / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/BATCH1-IMPLEMENTER-receipt.json`;
  window `2026-08-22T00:01:13Z` → `2026-08-22T01:46:08Z`, launcher exit
  `0` after 6294.5 s; base `c469e4934d3f4aabc990d7aed3c59794a2ffce08`;
  commits `0f6cd65810a2dcfc7cdd83577d6c7b5e112f0916`
  (`fix(exec-spine): raise timeout default, amend validator
  routing/finale, shorten registry lock`) and
  `686a8e750e1b8ae67a1e40e8717e591de1b83b4b` (`test(exec-spine): cover
  T2.3 replay/concurrency failure injections`); brief SHA-256
  `6d3b2f8bbe745df9072b6709855fedeeb2f0fbeeeb62b21cfb582eb24b0b2585`;
  result SHA-256
  `ae0a59181f2ee315c3f618fe197d3288076ce94a1a7e0fc441ad655bb7a819ba`;
  `stop_or_judgment` empty.
- **Changed files (7, all within the 10-file allowance):**
  `scripts/run_workflow_execution_spine_agent.py`,
  `scripts/validate_workflow_execution_spine_evidence.py`,
  `docs/plans/workflow-execution-spine-consolidation-plan-2026-08-20.md`
  (only the two §10 `--timeout=` lines),
  `tests/test_run_workflow_execution_spine_agent.py`,
  `tests/test_workflow_execution_spine_evidence.py`,
  `tests/test_authority_receipts.py`,
  `tests/test_comfy_nodes_agent_session.py`.
- **Implementer-recorded focused commands:** B0 wrapper/validator lines
  green (`23 passed`, `50 passed`, combined `73 passed`); focused T2.3
  line `168 passed, 2 failed` — both failures are pre-existing production
  drift (residual risk 1 below); base-export control runs at pristine
  `c469e493` and `fec6cb12` reproduced the same reds before Batch 1.
- This evidence recorder's own wrapper PID is `65868`, start
  `2026-08-22T01:53:17Z` per `active-allowances.json`; this recorder's
  own `end_ts` and receipt digest are written by the wrapper after exit
  and are not recorded here.

### B0 infra items landed (binding-condition mapping)

- **C2 (§16):** argparse default in `run_workflow_execution_spine_agent.py`
  raised 3600 → 7200; no explicit `--timeout=3600` remains in
  briefs/templates (the two plan §10 lines amended). Stub proof: a real
  wrapper dispatched with no `--timeout` flag ran a fake launcher sleeping
  3610 s — past the old 3600 s default that would have killed it at
  ~3605 s — and exited `0`, with the launcher argv carrying
  `--timeout=7200`.
- **C3:** validator `_route_for_label` plus the G7 check are
  set-membership accepting exactly `{grok-4.6, codex:gpt-5.6-luna,
  stealth/ox-alpha}` per label class; unrouted labels keep legacy
  any-route behavior.
- **C4:** validator `check_live_run` requires exactly 50 unique leg
  receipts at concurrency 10 with a recorded 25/25 staged/threaded split;
  the smoke run recorded `authoritative: false`, so `LIVE_RUN_SINGLETON`
  ignores it.
- **C7 (H3 registry-lock fix, BOTH halves):** `_registry_guard`'s
  critical section ends at the candidate write (~ms, never spans the
  child runtime); `_registry_release` takes `LOCK_EX` around its
  read-modify-write; the threaded test proves zero lost deletions;
  interrupt-inside-critical-section self-deadlock is eliminated via
  `_ACTIVE_REGISTRY_LOCK` descriptor reuse; the E2E test proves a second
  wrapper completes while the first child still sleeps.
- **C8:** same-worktree unconditional overlap kept verbatim (no
  read-only exemption) — Condition 8 upheld.
- **C13 hygiene:** dead `GROK_LAUNCHER` removed; unimported `Iterable`
  annotation on `_receipt_files` folded.
- **C9 not introduced:** no `readonly` flag landed; empty-`allowed`
  read-only registrations remain accepted.

### B1 — T2.3 eight failure injections

Eight required failure injections across `tests/test_authority_receipts.py`
and `tests/test_comfy_nodes_agent_session.py`, each proven by a real test
driving the public session/authority paths:

| injection | behavior proven |
|---|---|
| duplicate same-turn request | same payload+key replays the recorded response on the SAME turn; exactly one turn and one idempotency record |
| stale turn | prepare on unknown turn ⇒ `StaleStateMismatch`; new submit supersedes `candidate_ready→superseded`; late accept rejected |
| duplicate idempotency key | typed conflict carrying both request hashes; no second turn |
| crash after delta before receipt | `load_authority_receipt is None`; recovery undetermined `unknown_evidence_not_guessed_applied`, no deltas |
| crash after receipt before projection | row-7 recovery applied deterministically from persisted receipt+delta with replay_verified; mode-neutral projector mirrors it |
| changed ambient cache | frozen-provider replay still matches after witness-freeze schema mutation |
| concurrent independent sessions | barrier-synchronized threads over distinct session dirs keep disjoint turns/idempotency records/receipts |
| process-global cache poisoning | poisoned content/manifest/object-info caches leave all authority identity hashes unchanged |

### Residual risks (as stated by the implementer)

1. **Two pre-existing failures remain in the focused T2.3 command**
   (`tests/test_authority_replay_sequential.py::{test_replay_matches_executor_candidate_on_multi_add_with_remove,
   test_recompute_apply_is_sequential_invariant}`): production drift —
   live executor ingest pins `use_comfy_converter=False`
   (`vibecomfy/porting/edit/session.py:444`, `_gates.py:314`) while
   `recompute_apply` uses the `from_ui` default converter, so replayed
   candidates diverge from executor candidates on multi-add+remove edits
   (`candidate_hash_mismatch`). Verified red on pristine exports of
   `c469e493` and `fec6cb12` (predates Batch 1). A one-line production fix
   exists but `vibecomfy/**` is outside the implementer allowance — needs
   an owner decision (T2.3 production repair or dedicated card); routed to
   the G2 batch review for classification.
2. Validator routing membership accepts exactly `{grok-4.6,
   codex:gpt-5.6-luna, stealth/ox-alpha}`; a future fourth route requires
   another amendment.
3. The live-run contract now requires an explicit
   `split: {staged: 25, threaded: 25}` field — T7.2 must record it that
   way (Condition 4 implementation).
4. Registry guard/release assume the single-threaded wrapper invariant
   (one critical section per process); multi-threaded double-guard in one
   process is out of contract.

### Parallel dispatches launched concurrently (context)

Per §21.1/§21.3 read-only windows, three dispatches launched alongside
Batch 1 close-out, all registering in `active-allowances.json` at
`2026-08-22T01:53:17Z`: `G2-BATCH1-REVIEW` (fresh worktree
`wt-g2-batch1-review` at `686a8e75`, PID 65870), `T3.1-INVENTORY`
(`wt-t31-inventory`, PID 65873), and `T3.2-INVENTORY`
(`wt-t32-inventory`, PID 65877). Their own evidence entries follow when
they close.

### Next unblocked card

The G2 batch review (ONE stealth review of the whole Batch 1 diff,
doubling as the G2 gate per C10; attack surface: duplicate authority,
accepted-delta drift, terminal ambiguity, privacy, replay
nondeterminism, idempotency, recovery), then integration push including
`d9459c80` + `c469e493` + Batch 1 (C1), then B2 (T3.1+T3.2
implementation) once the inventories close.

### Controls

This evidence append changes only the three allowed evidence files in one
coherent commit authored by `POM <peter@omalley.io>`. No receipt,
protected state, branch, or other file is changed; no push, merge,
promotion, live/model/runtime call, secret access, wrapper dispatch,
review, validator change, or product/test run is performed by this
evidence recorder. The reviewed BATCH1-IMPLEMENTER receipt stays an
untracked run artifact and is not committed. The wrapper records this
recorder's own `end_ts` and receipt digest after exit; neither is
computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  was run after these appends against the refreshed manifest digests and
  exited `0` with deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carrying stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## G2 batch/gate review — G2-BATCH1-REVIEW disposition (2026-08-22)

### G2-BATCH1-REVIEW register and verdict

- **Task/label/gate/role/route:** `G2-BATCH1-REVIEW` / `G2 [XHARD-REVIEW]
  batch/gate review of Batch 1 (B0 infra + B1 T2.3)` / gate `G2` /
  reviewer / model route `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/G2-BATCH1-REVIEW-receipt.json` (file
  SHA-256 `a386bbcf2be731a58c0ecdf90ac2cdbc4c329443d9458704abd50aeab2f30e02`);
  window `2026-08-22T01:53:17Z` → `2026-08-22T02:16:20Z`, launcher exit
  `0`; base `686a8e750e1b8ae67a1e40e8717e591de1b83b4b`; zero changed
  files, zero commits (read-only); brief SHA-256
  `be59a55d588196944276d9ba2d707ffb31532615c99d7a060ec6b1569a212b5c`;
  result SHA-256
  `d1d4c8e6a296a077f1b76869e395e89f96b7eb8bffd1b41b472f33ef2e1056d7`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/G2-BATCH1-REVIEW-dispatch.log`.
- **Verdict: `continue`.** Batch 1 (`c469e493..686a8e75`) satisfies all
  six landed B0 conditions (C2/C3/C4/C7/C8/C13) and the B1 T2.3
  acceptance; C9 n/a (not introduced).
- **Merge/default recommendation:** proceed with the integration push
  including `d9459c80..686a8e75` (C1), conditional on recording the four
  findings below as evidence-linked cards; R-G2-1 must close before
  Batch 2 completes; default routing unchanged.
- This evidence recorder's own wrapper PID is `68841`, start
  `2026-08-22T02:17:46Z` per `active-allowances.json`; this recorder's
  own `end_ts` and receipt digest are written by the wrapper after exit
  and are not recorded here.

### Findings recorded as evidence-linked cards (all open)

- **MF-G2-1** (must, HARD/mechanical): `_ACTIVE_REGISTRY_LOCK =
  lock_handle` at wrapper lines 266/322/325 lacks `global` → the module
  global stays `None`; `_registry_release`'s reuse branch (:343–344) is
  unreachable dead code and the comment at :254–257 documents an
  invariant that can never execute. Latent SIGINT-window robustness gap
  only (handlers install after the guard returns; release always takes
  LOCK_EX on a fresh fd; dead-PID sweep self-heals). Fix: one line +
  test, next batch revision.
- **MF-G2-2** (must, HARD/mechanical):
  `test_concurrent_registry_release_preserves_both_deletions` (test file
  :642–666) asserts only absence of thread exceptions — no post-state
  assertion that both deletions persisted; a regression dropping LOCK_EX
  could lose a deletion yet pass. Fix: add a final registry-empty
  assertion (+ iterations).
- **SH-G2-3** (should):
  `docs/plans/goal-workflow-execution-spine-consolidation-2026-08-20.md:145`
  still emits an explicit `--timeout=3600` template example — outside
  the implementer allowance; fix in next orchestrator/evidence touch.
- **R-G2-1** (residual, must-track — §7 classification): the two
  pre-existing failures in
  `tests/test_authority_replay_sequential.py::{test_replay_matches_executor_candidate_on_multi_add_with_remove,
  test_recompute_apply_is_sequential_invariant}` are PRE-EXISTING, NOT
  introduced by Batch 1 (empty diff over `vibecomfy/**` + failing module
  + conftest; mechanism visible in unchanged code:
  `use_comfy_converter=False` ingest pin at `session.py:~444` /
  `_gates.py:~314` vs the `from_ui`-default `recompute_apply`; failure
  signature `candidate_hash_mismatch`). Disposition: acceptable residual
  risk for G2, requiring a dedicated XHARD production-repair card; must
  close before Batch 2 completes; G6/G7 fail closed on it if ignored.

### Review-run focused command and validator environment

- The review re-ran the focused T2.3 command: `168 passed / 2 failed` —
  exactly the two known pre-existing R-G2-1 failures — exit `1`.
- The review-worktree validator exit `1` was root-caused environmental,
  not an evidence defect: receipts are untracked run artifacts absent in
  the fresh worktree; the HEAD validator against the operating manifest
  exits `0`, and the base validator against the same manifest also
  exits `0`.

### Next unblocked card

Integration push including `d9459c80..686a8e75` (C1), then B2
(T3.1+T3.2 implementation) once the inventories below close;
MF-G2-1/MF-G2-2 land in the next batch revision per C10.

## Read-only inventories — T3.1/T3.2 dispositions (2026-08-22)

### T3.1-INVENTORY register

- **Task/label/role/route:** `T3.1-INVENTORY` / `T3.1 [HARD]
  retry-ownership inventory (read-only, pre-implementation)` / inventory
  / model route `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/T3.1-INVENTORY-receipt.json` (file
  SHA-256 `b9a74cbcb3d0128f2e98cea8485e860e978cf39b7423d712ecacf02207bb1f4c`);
  window `2026-08-22T01:53:17Z` → `2026-08-22T02:05:53Z`, launcher exit
  `0`; base `686a8e750e1b8ae67a1e40e8717e591de1b83b4b`; zero changed
  files, zero commits (read-only); brief SHA-256
  `4623bffd1fd542d690378e4c1ac326c290fcf974e12fd91ced08f277fa1ef819`;
  result SHA-256
  `1078fc2553502dad7c913e7f8f40f218d4c700f117a9bc512a3df41b4a7a58d9`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/T3.1-INVENTORY-dispatch.log`.

### T3.2-INVENTORY register

- **Task/label/role/route:** `T3.2-INVENTORY` / `T3.2 [XHARD]
  batch-protocol / accepted-batch authority inventory (read-only,
  pre-implementation)` / inventory / model route `stealth/ox-alpha`,
  resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/T3.2-INVENTORY-receipt.json` (file
  SHA-256 `d5d7a1e8592ec72fecb7b483d20fc484f971aa0091d7a412492c3a9e2997fc3d`);
  window `2026-08-22T01:53:17Z` → `2026-08-22T02:08:21Z`, launcher exit
  `0`; base `686a8e750e1b8ae67a1e40e8717e591de1b83b4b`; zero changed
  files, zero commits (read-only); brief SHA-256
  `808ce0da1999038b986c840d52d9ae6738d2aec6f9400294e8e0e1b7932230cc`;
  result SHA-256
  `1e6c8cd4d76bfd34b6b65a2de26319e615d476168b3d503d1b576e0ea19a60ec`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/T3.2-INVENTORY-dispatch.log`.

### Parallel-wave note (C7 operationally proven)

All four tasks of the 02:10Z parallel wave (`evidence-log-BATCH1`,
`G2-BATCH1-REVIEW`, `T3.1-INVENTORY`, `T3.2-INVENTORY`) registered
concurrently in `active-allowances.json` at `2026-08-22T01:53:17Z`
(wrapper PIDs 65868/65896/65897/65898), completing across 02:04–02:16Z —
four simultaneous registrations with no blocking; the C7 registry lock
fix is operationally proven.

### Controls

This evidence append changes only allowed evidence files (execution log
+ manifest; test-shards.json untouched) in one coherent commit authored
by `POM <peter@omalley.io>`. No receipt, protected state, branch, or
other file is changed; no push, merge, promotion, live/model/runtime
call, secret access, wrapper dispatch, review, validator change, or
product/test run is performed by this evidence recorder. No receipt is
committed; the reviewed receipts stay untracked run artifacts. The
wrapper records this recorder's own `end_ts` and receipt digest after
exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## Batch 1 integration push — BATCH1-INTEGRATION disposition (2026-08-22)

### BATCH1-INTEGRATION register

- **Task/label/gate/role/route:** `BATCH1-INTEGRATION` /
  `BATCH1-INTEGRATION: apply reviewed chain, run named batch shard once,
  fast-forward push` / gate `G2` / integration / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/BATCH1-INTEGRATION-receipt.json` (file
  SHA-256 `2d6f78421cc54231da2dfed6ed8b8ddeda3e83d0487bbfe6003f5aad3b191a81`);
  window `2026-08-22T02:34:27Z` → `2026-08-22T02:37:43Z`, launcher exit
  `0`; base `b9c23c92cdf3b132f8baa0376910baf0a5b09018`; zero changed
  files, zero commits (read-only integration); brief SHA-256
  `2c3d7d80a138b65aadc7b6ddf91469f2252576e84521e4f8adac4184455560fc`;
  result SHA-256
  `402f9b980a2dbbb59e9712adc2b8d27001104a00a2c4dbfeeab4ea5beb4268ab`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/BATCH1-INTEGRATION-dispatch.log`.
- This evidence recorder's own wrapper PID is `69552`, start
  `2026-08-22T02:38:33Z` per `active-allowances.json`; this recorder's
  own `end_ts` and receipt digest are written by the wrapper after exit
  and are not recorded here.

### Push executed and verified — Condition 1 (C1) satisfied

- **Push executed:** `git push origin
  HEAD:fixer/workflow-execution-spine-consolidation` →
  `c83d2e59..b9c23c92`; plain fast-forward refspec, no force flag; all
  seven commits advanced in one atomic update; history untouched.
- **remote_after** verified via `git ls-remote` =
  `b9c23c92cdf3b132f8baa0376910baf0a5b09018`; fast-forward from
  `c83d2e59cae670c056564f297061062b0a880763`.
- **Condition 1 (C1) satisfied:** the push includes the docs-only T2.2
  disposition commit `d9459c80`, the pre-review evidence `c469e493`,
  Batch 1 B0/B1 commits `0f6cd658` + `686a8e75`, and evidence commits
  `baf1ee93` + `b9c23c92` (chain order `c83d2e59 → d9459c80 → c469e493
  → 0f6cd658 → 686a8e75 → baf1ee93 → b9c23c92`). Subsequent briefs cite
  `b9c23c92` as the latest reviewed integration base.

### Named batch shard — run once by the integration agent

- The focused T2.3 five-module command (`test_authority_receipts.py`,
  `test_authority_replay_sequential.py`,
  `test_agent_edit_artifact_replay.py`,
  `test_comfy_nodes_agent_transaction_storage.py`,
  `test_comfy_nodes_agent_session.py`) ran EXACTLY once: exit `1`,
  result `2 failed, 168 passed, 61 warnings in 1.66s` — matches the
  expected `168 passed, 2 failed` exactly.
- The two failures are exactly the pre-existing R-G2-1 set
  (`tests/test_authority_replay_sequential.py::{test_replay_matches_executor_candidate_on_multi_add_with_remove,
  test_recompute_apply_is_sequential_invariant}`); no new failures
  appeared.

### G2 follow-on cards queued (context)

- **BATCH1-REVISION**: MF-G2-1 registry-lock `global`, MF-G2-2
  release-test post-state assertion, SH-G2-3 goal-doc timeout template
  — all HARD/mechanical.
- **R-G2-1-REPAIR**: dedicated XHARD production repair of the replay
  converter drift; must close before Batch 2 completes.

### Next unblocked card

BATCH1-REVISION, then R-G2-1-REPAIR, then B2 (T3.1 + T3.2
implementation per the two completed inventories), then G3 batch
review.

### Controls

This evidence append changes only allowed evidence files (execution log
+ manifest; test-shards.json untouched) in one coherent commit authored
by `POM <peter@omalley.io>`. No receipt, protected state, branch, or
other file is changed; no merge, promotion, live/model/runtime call,
secret access, wrapper dispatch, review, validator change, or
product/test run is performed by this evidence recorder; the recorded
push was executed by the BATCH1-INTEGRATION agent, not by this
recorder. No receipt is committed; the reviewed receipts stay untracked
run artifacts. The wrapper records this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## G2 follow-on cards — BATCH1-REVISION and R-G2-1-REPAIR (2026-08-22)

### BATCH1-REVISION register

- **Task/label/gate/role/route:** `BATCH1-REVISION` / `BATCH1-REVISION:
  fix G2 must findings MF-G2-1 + MF-G2-2 + SH-G2-3 (registry lock global,
  release-test assertion, goal-doc timeout template)` / gate `G2` /
  implementer / model route `stealth/ox-alpha`, resolved
  `stealth/ox-alpha`.
- **Receipt/result:** `receipts/BATCH1-REVISION-receipt.json` (file
  SHA-256
  `35d80d66cacd8f3c2fc7dca56e2ac1ddbaf2e72003fa7d20714e135d989fd09c`);
  window `2026-08-22T02:45:25Z` → `2026-08-22T02:57:27Z`, launcher exit
  `0`; base `ed50918c6e979a05706907fa1ef9719ea12a460c`; commit
  `2e384645786cb287ee121764125de3c85bda15d4`; brief SHA-256
  `a9a5b85190bc1bced2144ae53c5c23f13d550fdbb445faa5c96c056853a834cf`;
  result SHA-256
  `5578f9d5fb31aecd08f98341f1401f781f02cb899aa36cb654f35e6a122290b2`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/BATCH1-REVISION-dispatch.log`.
- **Changed files (3, within allowance):**
  `docs/plans/goal-workflow-execution-spine-consolidation-2026-08-20.md`,
  `scripts/run_workflow_execution_spine_agent.py`,
  `tests/test_run_workflow_execution_spine_agent.py`.

### MF-G2-1 fixed (must/HARD)

`global _ACTIVE_REGISTRY_LOCK` added as the first statement of
`_registry_guard` (wrapper :262); the three module-global assignments
(wrapper :267/:323/:326 post-insert; :266/:322/:325 as found) now hit the
module global, and `_registry_release`'s reuse branch (:344–345) is live
instead of unreachable dead code. New test
`test_registry_guard_publishes_active_lock_for_interrupt_reuse` (test
file :642) spies `_json_write` during the candidate write to prove a live
handle is published on `.active-allowances.lock`, asserts the global is
cleared after the guard returns, and proves the reuse branch removes the
registry entry while keeping the descriptor open+locked (fresh-fd probe →
`BlockingIOError`; no second-flock block).

### MF-G2-2 fixed (must/HARD)

`test_concurrent_registry_release_preserves_both_deletions` (test file
:693) now runs 25 rounds with a post-state assertion `registry == {}`
after each round (:723); a LOCK_EX drop fails on lost update or corrupt
read-modify-write (no-op'ing flock reproduces `FileNotFoundError` +
lost-update + JSON-concatenation corruption; the old test passed
vacuously through all of it).

### SH-G2-3 fixed (should)

Goal doc :145 template now emits `--timeout=7200`; zero `3600`
occurrences remain in the goal doc.

### BATCH1-REVISION focused run

Final focused run: **51 passed, exit 0** (run 2; run 1 failed on the new
test's own assertion bug — descriptor liveness asserted after guard
return — fixed by observing liveness inside the spy and disclosed per the
run-at-most-once constraint).

### R-G2-1-REPAIR register

- **Task/label/gate/role/route:** `R-G2-1-REPAIR` / `R-G2-1-REPAIR
  [XHARD]: replay converter drift — align executor ingest
  use_comfy_converter with recompute_apply` / gate `G2` / implementer /
  model route `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/R-G2-1-REPAIR-receipt.json` (file
  SHA-256
  `7d369a56181a470a166ae32b21af2436ed800915b4e8e47cc84d0393abca3400`);
  window `2026-08-22T02:57:36Z` → `2026-08-22T03:09:31Z`, launcher exit
  `0`; base `2e384645786cb287ee121764125de3c85bda15d4`; commit
  `b8891ee010fa90d1d8148002d1959ddd39c25606`; brief SHA-256
  `aeb412b8c179933491bbefbb5cf47963f52f34d03c7f51cf05ff051aebf0edd0`;
  result SHA-256
  `4e149af1301fd215f7ca68c9e44bfd6bf2b593639d41f345a9907f50adad28b1`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/R-G2-1-REPAIR-dispatch.log`.
- **Changed file (1, within allowance):**
  `tests/test_authority_replay_sequential.py` only; no production file
  modified.

### R-G2-1 red reproduced and root cause re-diagnosed (evidence-corrected)

- **Red:** both tests failed (`candidate_hash_mismatch`;
  `'ecccd7df…' != '7804d399…'`).
- **Root cause re-diagnosed — NOT converter selection.** The G2 review's
  stated mechanism was empirically disproved (monkeypatch experiment at
  `/tmp/rg21-repair/prove_fix.py`: `use_comfy_converter` is not
  importable offline, and both ingest paths hit the identical
  `_normalize_ui_to_api` fallback). The decisive delta is
  `pin_untouched_ui`: the test harness `_sequential_candidate` modeled
  the executor as bare `emit_ui_json`, but the live executor's projector
  pipeline ends with `pin_untouched_ui(prior_ui, emitted, landed_ops)`
  (`session.py:462-469` `_emit_working_snapshot`, `checkpoint.py:519`,
  `_gates.py:298`, `authority_receipts.py:339-348` `recompute_apply`).
  Omitting the pin re-emitted untouched schema-less nodes best-effort
  (float positions + injected vibecomfy_id/uid props) vs pinned prior
  bytes → hash drift.

### R-G2-1 fix: test-harness repair

The helper now returns `pin_untouched_ui(submit, emitted, ops)` after the
interpret loop (test file :82), byte-identical to
`EditSession._emit_working_snapshot`; invariant assertions untouched; the
harness now enforces them against REAL executor bytes. Green: **2 passed,
exit 0**.

### R-G2-1 rejected alternatives

- Pin `use_comfy_converter=False` in `recompute_apply` — outside the
  allowance and empirically insufficient offline.
- Remove executor pins to match replay defaults — flips Law-1 door
  passthrough off for all live sessions; forbidden public-candidate
  change.

### R-G2-1 residual risk — flagged for G3 classification

Latent comfy-host ingest asymmetry remains: the executor ingests
`use_comfy_converter=False` while `recompute_apply` uses the `from_ui`
default True. Provably inert offline, but on hosts where the comfy
converter imports and diverges from `_normalize_ui_to_api`, replay could
drift from live candidates. Closing it requires editing
`vibecomfy/comfy_nodes/agent/authority_receipts.py` — outside R-G2-1's
allowance. The G3 batch review must classify whether R-G2-1 is CLOSED
(repair landed, tests green, residual flagged) or requires a follow-up
production card; no closure verdict is recorded here.

### G2 condition status and next unblocked card

R-G2-1's G2 condition "must close before Batch 2 completes" — the repair
card has landed (tests green); the residual classification is deferred to
the G3 batch review per C10/§18. Next unblocked card: B2-IMPLEMENTER
(T3.1 + T3.2; brief + allowance already written at
`g0/B2-IMPLEMENTER.md` / `-allowance.json`).

### Controls

This evidence append changes only allowed evidence files (execution log +
manifest; test-shards.json untouched) in one coherent commit authored by
`POM <peter@omalley.io>`. No receipt, protected state, branch, or other
file is changed; no push, merge, promotion, live/model/runtime call,
secret access, wrapper dispatch, review, validator change, or product/
test run is performed by this evidence recorder; the recorded repairs
were executed by the BATCH1-REVISION and R-G2-1-REPAIR agents, not by
this recorder. No receipt is committed; the reviewed receipts stay
untracked run artifacts. This evidence recorder's own wrapper PID is
`71632`, start `2026-08-22T03:10:34Z` per `active-allowances.json`; its
own receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-G2-FOLLOWON-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## B2 implementer + T4.2/T4.3 inventory dispositions (2026-08-22)

### B2-IMPLEMENTER register

- **Task/label/role/route:** `B2-IMPLEMENTER` / `B2 implementer: T3.1
  [HARD] nested retry ownership + T3.2 [XHARD] batch protocol and
  accepted-batch authority` / implementer / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/B2-IMPLEMENTER-receipt.json` (file
  SHA-256
  `8c48bc4bca34640ace335f3b485242da9763ab0543e2aa309616046932054a10`);
  window `2026-08-22T03:20:14Z` → `2026-08-22T04:16:14Z`, launcher exit
  `0`; base `903f6099f0c16c6cfe0c435ba33066a33956e28d` (R-G2-1
  precondition confirmed green at base); single commit
  `5396123eb7a955e0753e0b47a4f4516a773c66f8` covering both cards
  (provider hunks overlap; per-card split rejected); brief SHA-256
  `eeca8c48da5d5f038d2ebcdfa1783b415bfd55d9369bea3ae4e66920b485018a`;
  result SHA-256
  `d3d47748104d9b1d98ed936db8c97c636b4156271de055a66ee741ed1461c23e`;
  `stop_or_judgment` empty (`JUDGMENT_REQUIRED: none`); full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/B2-IMPLEMENTER-dispatch.log`.
- **Changed files (9, all within allowance):**
  `vibecomfy/comfy_nodes/agent/runtime.py`,
  `vibecomfy/comfy_nodes/agent/provider.py`,
  `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`,
  `vibecomfy/comfy_nodes/agent/_turn_state_machine.py`,
  `tests/live_agentic_harness/runner.py`,
  `tests/test_runtime_worker_retry.py`,
  `tests/test_executor_contracts.py`,
  `tests/test_comfy_nodes_agent_contracts.py`,
  `tests/test_comfy_nodes_agent_edit.py`. Protected state untouched
  (`5fc6be9d` unchanged).

### T3.1 landed — one owner + one total wall-clock budget

- **D1 retry freeze:** `_TURN_TOTAL_BUDGET_SECONDS` (env
  `VIBECOMFY_AGENT_TURN_TOTAL_BUDGET`, default 600s) with explicit
  deadlines flowing from all four entry points (`run_model_turn`,
  `run_agent_turn`, `_delta`, `_batch`) into `_run_worker(deadline=...)`;
  provider's ≤3-attempt loop wraps everything in
  `composed_model_call_budget()` (`provider.py`), ending the historical
  3×3-spawn budget multiplication with one shared deadline enforced
  pre-spawn and clamped per spawn. Budget exhaustion raises a truthful
  typed `TimeoutError` carrying full `retry_owner...` fields.
- **Owner map frozen as constants** (`runtime.py:113-170`):
  `runtime_worker_transport`, `runtime_json_correction`,
  `provider_batch_empty`, `harness_infrastructure`.

### D6 — the 480s disposition decision (the routed judgment)

A side-effect-free timed-out model request may NOT retry under the same
identity: completion requests carry no request-level idempotency key, so
the remote state of the timed-out request is unknowable (double-billing
risk, latency-pathology masking). The attempt ends with truthful typed
exhaustion carrying `retry_owner=harness_infrastructure`,
`retry_disposition=not_safe_to_retry_same_identity`,
`remote_uncertainty=timeout_before_response` (`runtime.py:1060-1089`);
the harness remains sole owner of exactly one retry under a NEW attempt
identity. The fixture vocabulary (`attempt_ledger_480s.json`) now equals
live behavior rather than contradicting it.

### Evidence fields made real and D2/D3/D4/D5 pins

- Every attempt row stamps
  `retry_owner/nesting_depth/attempt_deadline_seconds/remote_uncertainty/
  retry_disposition/durable_side_effect_free/request_idempotency_key`
  (`_stamp_retry_evidence`), preserved through canonical re-normalization
  in runtime and provider; harness `_attempt_record` carries a
  `retry_ownership` block per scenario attempt (`runner.py:343-395`).
- **D2/D3/D4/D5 pins:** hivemind 1 retry + 0.5s backoff inside the
  shared 450s phase deadline with deadline-checked-before-any-attempt
  behavior test; correction layers bounded by named constants
  (`_JSON_CONTRACT_MAX_ATTEMPTS`, `_BATCH_REPL_EMPTY_ATTEMPTS`, existing
  `_ITERATION_EXHAUSTION_MAX_CORRECTIONS`/`_CLASSIFY_MAX_PARSE_ATTEMPTS`);
  durable path replay-only with the 10s session-lock bound; harness
  `DEFAULT_INFRA_RETRIES==1`, `1200s`, `_RETRYABLE_INFRA_CLASSES` frozen.

### T3.2 landed — fence seam, native structured seam, correction slot

- Fence seam documented as the single stripping seam at
  `provider.py:208-212`; fail-closed
  `{empty, missing_batch_fence, multiple_batch_fences}` pinned; never
  merged, never rerun. Native structured seam frozen at the
  `payload["batch"]` mapping branch (`provider.py:1475-1480`) — bypasses
  fence parsing, no new transport built.
- **Correction slot:** exactly one bounded opportunity per batch turn,
  RESERVED in `model_request_path` before the first call
  (`edit_batch_repl.py:1103-1112`), consumed as a sibling record next to
  the untouched `protocol_retry` shape; final dispositions
  `unused/consumed_recovered/consumed_exhausted` land in audit metadata,
  turn records, response errors, and terminal diagnostics. **Session-level
  bound decision:** stays per-turn bound=1 — total corrections are already
  structurally capped at ≤ max_batches by the turn loop; a session-wide
  counter would add durable resume state without shrinking exposure
  (recorded at `edit_batch_repl.py:353-361`).
- Authority: ok∧landed admission rule + derived-envelope digest binding
  unit-pinned; duplicate-submit replay/conflict by idempotency key covered
  through `allocate_turn`/`record_idempotent_response`; accept-response
  echo provenance pinned derived-only (`_turn_state_machine.py:606-612`).
  Browser canonical-only contract untouched — 290 browser tests already
  lock it. `contracts.py` ModelAttemptEvidence not extended (outside the
  allowance) — evidence rides as additive dict keys outside the dataclass.

### Focused command results and disclosed defect fixes

| Command | Result |
|---|---|
| T3.1 pytest (runtime/executor/agent-contracts) | **358 passed**, exit 0 |
| T3.2 pytest (`-k batch or protocol or accepted_batch`) | **150 passed, 22 failed** — failure set byte-identical to pristine base `903f6099` (same selection run in a base worktree; symmetric diff empty); all 22 pre-existing prompt-content/loop-behavior failures not touched by this card |
| T3.2 node --test (3 browser suites) | **290 pass / 0 fail**, exit 0 |

First T3.2 python run failed 29; the implementer fixed 3 defects in its
own additions (dropped `first_detail` line, idempotency key passed via
payload instead of kwarg, tuple-vs-list accepted_batch shape) before the
final run above — disclosed per run-at-most-once.

### Residual risks and G3 classification flags

- Non-default `VIBECOMFY_ARNOLD_RUNTIME_MODULE` ignores the
  composed-deadline contextvar (opaque third-party retry semantics;
  flagged AMBIGUOUS in inventory — unchanged).
- The composed 600s default tightens real worst-case wall clock vs the
  prior unbounded 9×480s composition (env-tunable).
- The 22 pre-existing T3.2-scope failures remain: the implementer claims
  byte-identical-to-base (symmetric diff empty), but G3 review must
  classify introduced vs pre-existing.
- R-G2-1 residual (latent comfy-host ingest asymmetry, flagged at its
  own card below) still awaits G3 classification together with the
  22-failure set.

### T4.2-INVENTORY register

- **Task/label/role/route:** `T4.2-INVENTORY` / `T4.2 [HARD]
  staged-adapter inventory (read-only, pre-implementation)` / inventory /
  model route `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/T4.2-INVENTORY-receipt.json` (file
  SHA-256
  `324a177990f7cbbaedc4269c6f9b88bdb3d2418488dd230ec9cf5f07c164b458`);
  window `2026-08-22T03:21:12Z` → `2026-08-22T03:29:17Z`, launcher exit
  `0`; base `903f6099f0c16c6cfe0c435ba33066a33956e28d`; zero changed
  files, zero commits (read-only); brief SHA-256
  `2a286af025422b54cf014bf26a75c114028f1568bfe7677e39d8a3fa04a083e2`;
  result SHA-256
  `f71456bc06f54d31fe1d9ad1e092e8ecc41b46b01f714e44f6210a5a2b77a074`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/T4.2-INVENTORY-dispatch.log`.
- Surface inventoried: staged pipeline stages
  (classify → research → implement → no-candidate → reply), shared
  contract surfaces vs the T4.1 evidence list, research phase internals,
  wire-compatibility surface, reply-model distinct behavior, staged test
  coverage map; AMBIGUOUS items recorded (450s vs 600s deadline defaults
  on one env knob, per-ledger-entry tool-status encoding,
  executed-tool-call count bases across modes).

### T4.3-INVENTORY register

- **Task/label/role/route:** `T4.3-INVENTORY` / `T4.3 [HARD]
  threaded-adapter inventory (read-only, pre-implementation)` / inventory
  / model route `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/T4.3-INVENTORY-receipt.json` (file
  SHA-256
  `778f9d8ae91496abf418f1a6b7ff3fa1ab4c026352cb6f11a3858741936991a5`);
  window `2026-08-22T03:21:12Z` → `2026-08-22T03:30:56Z`, launcher exit
  `0`; base `903f6099f0c16c6cfe0c435ba33066a33956e28d`; zero changed
  files, zero commits (read-only); brief SHA-256
  `f74a161703e7ec7f7805417058f6dcd5464fc77460c01c7150189f80cd9e8853`;
  result SHA-256
  `adf418d1d5cf297fd5707c5237b3940f6d5ee201edf82ba63f402c7d56ec840a`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/T4.3-INVENTORY-dispatch.log`.
- Surface inventoried: classifier-free routing (sole `_run_classify`
  caller proven staged-only), graphless research, answer-only,
  attached-graph authority, continuation, terminal projection, threaded
  test coverage; ambiguous areas recorded (thread-store substrate built +
  production-bound but undriven, budget reserves unenforced, the shared
  450/600 deadline-default split).

### Three-way concurrent dispatch note

B2 (mutating, wrapper PID 71929) ran concurrently with both read-only
inventories (wrapper PIDs 72053/72054, both registered
`2026-08-22T03:21:12Z`) via separate worktrees — the §21 concurrent
window exploited with the registry-lock fix holding (no blocking,
no interference between the mutating and read-only registrations).

### Next unblocked card

G3 batch review: ONE stealth review of the whole B2 diff (BATCH1-REVISION
+ R-G2-1-REPAIR + B2 commits), doubling as the G3 gate per C10; it must
classify the R-G2-1 residual AND the 22 pre-existing T3.2-scope failures
(introduced vs pre-existing). Then integration push (`b9c23c92..HEAD`),
then B3.

### Controls

This evidence append changes only allowed evidence files (execution log +
manifest; test-shards.json untouched) in one coherent commit authored by
`POM <peter@omalley.io>`. No receipt, protected state, branch, or other
file is changed; no push, merge, promotion, live/model/runtime call,
secret access, wrapper dispatch, review, validator change, or product/
test run is performed by this evidence recorder; the recorded B2
implementation and inventories were executed by the B2-IMPLEMENTER,
T4.2-INVENTORY, and T4.3-INVENTORY agents, not by this recorder. No
receipt is committed; the reviewed receipts stay untracked run artifacts.
This evidence recorder's own wrapper PID is `75970`, start
`2026-08-22T04:17:08Z` per `active-allowances.json`; this recorder's own
receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-B2-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## G3 batch/gate review — G3-B2-REVIEW disposition (2026-08-22)

### G3-B2-REVIEW register

- **Task/label/role/route:** `G3-B2-REVIEW` / `G3 [XHARD-REVIEW] batch/gate
  review of the B2 window (BATCH1-REVISION + R-G2-1-REPAIR + B2
  T3.1/T3.2)` / reviewer / model route `stealth/ox-alpha`, resolved
  `stealth/ox-alpha`.
- **Receipt/result:** `receipts/G3-B2-REVIEW-receipt.json` (file SHA-256
  `1eff68938568792561bd7c95e404c0b7d8717365b756c917e041519a661688a9`);
  window `2026-08-22T04:25:41Z` → `2026-08-22T04:48:22Z`, launcher exit
  `0`; base `5396123eb7a955e0753e0b47a4f4516a773c66f8`; zero changed
  files, zero commits (read-only); brief SHA-256
  `87972cd5a279c25970447852f69b8b1747a44a825bee22b1bfc8ddbcee92e428`;
  result SHA-256
  `d3d4823802714f4f8efbc89a1ff2a84a22003306e3429d8f226620927cea543b`;
  `stop_or_judgment` empty (`JUDGMENT_REQUIRED: none`); full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/G3-B2-REVIEW-dispatch.log`.
- **Verdict: `continue`.** The complete B2 window
  (`2e384645..5396123e`) satisfies G3 gate acceptance for T3.1 [HARD]
  and T3.2 [XHARD], correctly closes the G2 findings, lands a genuine
  R-G2-1 repair, introduces zero test failures, and leaves protected
  state unchanged.

### Merge recommendation (advisory)

Proceed with the integration push `b9c23c92..5396123e` plus the pending
evidence-log-B2 append (`63d4d153`, already landed in this worktree);
default routing unchanged; land one small follow-up production card
before T7.2 (G3-RESIDUAL-RG21-ASYMMETRY below); the residual does not
block B3.

### T3.1 PASS — retry ownership and composed budget

- Owner map frozen as constants (`runtime.py:132-135`); composed budget
  via one min() contextvar deadline enforced pre-spawn and clamped per
  spawn with the provider wrap — the historical 3×3 multiplication is
  dead; D6/480s truthful typed exhaustion with harness-only
  new-identity retry; attempt evidence real (all seven keys stamped,
  preserved through canonical re-normalization).
- Review reproduced the focused command: **358 passed**, exit 0.

### T3.2 PASS — fence seam, native structured seam, correction slot

- Fence seam fail-closed on all eight scenarios (no-fence / malformed /
  multiple / valid+prose / empty-fence→typed identity no-op /
  duplicate-replay by idempotency key / valid-first-invalid-second
  atomic+reprompt-once); native structured bypass intact; correction
  slot exactly-once and persisted end-to-end; ok∧landed admission rule
  enforced with `accepted_batch` sole authority; accept-response echo
  provenance pinned derived-only.

### G2 findings closure

- **MF-G2-1 and MF-G2-2 verified genuine** fixes from BATCH1-REVISION
  (registry-lock module global published and reused; post-state
  registry-empty assertion), not vacuous passes.
- **SH-G2-3 fixed** (goal-doc timeout template now emits 7200s).
- **R-G2-1 CLOSED.** The repair strengthened the test harness —
  `_sequential_candidate` now returns
  `pin_untouched_ui(submit, emitted, ops)`, byte-identical to the live
  executor pipeline (`EditSession._emit_working_snapshot`); invariant
  assertions strengthened, not relaxed; both tests pass, independently
  reproduced by the review.

### Residuals (should-track, non-blocking)

- **G3-RESIDUAL-RG21-ASYMMETRY** (should, XHARD): executor ingests
  `use_comfy_converter=False` (`session.py:444`) while
  `recompute_apply` keeps the `from_ui` converter default True
  (`authority_receipts.py:320`). Provably inert offline (both paths hit
  the identical `_normalize_ui_to_api` fallback); latent only on hosts
  where the comfy converter imports AND diverges; drift direction is
  fail-closed (a false `candidate_hash_mismatch` rejection, never a
  false accept); one-line repairable at
  `vibecomfy/comfy_nodes/agent/authority_receipts.py` (outside
  R-G2-1's allowance). Must land before T7.2.
- **G3-RESIDUAL-ARNOLD-MODULE** (should): non-default
  `VIBECOMFY_ARNOLD_RUNTIME_MODULE` ignores the composed-deadline
  contextvar (opaque third-party retry semantics).
- The 600s composed default tightens worst-case wall clock vs the
  historical unbounded 9×480s composition (intended, env-tunable).
- Retry-evidence keys ride outside the frozen `ModelAttemptEvidence`
  dataclass as additive dict keys (`contracts.py` outside the
  allowance); preserved through re-normalization.

### 22 pre-existing T3.2-scope failures — CONFIRMED PRE-EXISTING

| Selection | Result |
|---|---|
| head `5396123e` | 150 passed, 22 failed |
| base `903f6099` export | 139 passed, 22 failed |
| failing-ID symmetric difference | **EMPTY** (`diff` exit 0) |

The +11 passes at head are exactly the new B2 pins;
introduced-by-B2 count: **0**. All 22 failures are pre-existing
prompt-content/loop-behavior assertions untouched by this card; owned
by T6.2's formal classification, with base/head evidence now recorded.

### Evidence coherence

The reviewer-worktree validator exit 1 was environmental: receipts are
untracked run artifacts absent in the fresh review worktree. A scratch
replica of the committed state validated **OK, exit 0**, stdout SHA-256
`1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`
(byte-exact match to the recorded deterministic digest). Manifest
final_five/findings/gates/live_runs/shards identical across the
window.

### Next unblocked card

Integration push `b9c23c92..HEAD` (including evidence commit
`63d4d153`), then evidence-log-integration, then B3-IMPLEMENTER
(T4.1+T4.2+T4.3; brief + allowance already written at
`g0/B3-IMPLEMENTER.md` / `-allowance.json`), then G4 batch review.

### Controls

This evidence append changes only allowed evidence files (execution log
+ manifest; test-shards.json untouched) in one coherent commit authored
by `POM <peter@omalley.io>`. No receipt, protected state, branch, or
other file is changed; no push, merge, promotion, live/model/runtime
call, secret access, wrapper dispatch, review, validator change, or
product/test run is performed by this evidence recorder; the recorded
G3 batch review was executed by the G3-B2-REVIEW agent, not by this
recorder. No receipt is committed; the reviewed receipts stay untracked
run artifacts. This evidence recorder's own wrapper PID is `77467`,
start `2026-08-22T04:48:59Z` per `active-allowances.json`; this
recorder's own receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-G3-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## B2-window integration push — B2-INTEGRATION disposition (2026-08-22)

### B2-INTEGRATION register

- **Task/label/gate/role/route:** `B2-INTEGRATION` /
  `B2-INTEGRATION: apply reviewed chain, run named batch shard once,
  fast-forward push` / gate `G3` / integration / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/B2-INTEGRATION-receipt.json` (file
  SHA-256 `8de10fc04f8362d8a8f1bb9accddf5d01ddcb701a5aae968a82e6336143d31d6`);
  window `2026-08-22T04:59:23Z` → `2026-08-22T05:04:31Z`, launcher exit
  `0`; base `d564de9e146dd69a08d5aaf9530efc4186d7fad2`; zero changed
  files, zero commits (read-only integration); brief SHA-256
  `1fe86e5d0a8c0ffb5840f980b3ec27617f41b98ef7bf812a25842f898bfc021c`;
  result SHA-256
  `0847ce49b73ad7af57f97d78e16aa951b1c6b06954767809d45c21a611fc0a52`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/B2-INTEGRATION-dispatch.log`.
- This evidence recorder's own wrapper PID is `78057`, start
  `2026-08-22T05:05:17Z` per `active-allowances.json`; this recorder's
  own `end_ts` and receipt digest are written by the wrapper after exit
  and are not recorded here.

### Push executed and verified

- **Push executed:** `git push origin
  HEAD:fixer/workflow-execution-spine-consolidation` →
  `b9c23c92..d564de9e`; plain two-dot range update = plain fast-forward
  refspec, no force flag, no rejection; all seven commits advanced in
  one atomic update; history untouched.
- **remote_after** verified via `git ls-remote` =
  `d564de9e146dd69a08d5aaf9530efc4186d7fad2` == local HEAD.
- **Push coverage:** the G2 follow-on repairs `2e384645` + `b8891ee0`
  with their follow-on evidence record `903f6099`, the B2 implementer
  commit `5396123e`, and the evidence commits `63d4d153` + `d564de9e`
  (chain order above remote-before `b9c23c92`: `ed50918c → 2e384645 →
  b8891ee0 → 903f6099 → 5396123e → 63d4d153 → d564de9e`). Subsequent
  briefs cite `d564de9e` as the latest reviewed integration base.

### Named batch shard — run once by the integration agent

- Command (verbatim): `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q
  -p no:cacheprovider tests/test_runtime_worker_retry.py
  tests/test_executor_contracts.py
  tests/test_comfy_nodes_agent_contracts.py` ran EXACTLY once under
  Python 3.11.11 / pytest 9.1.1: exit `0`, result `358 passed, 1
  warning in 1.59s` — matches the G3 review's recorded result exactly;
  zero failures, nothing new introduced.

### Next unblocked card

B3-IMPLEMENTER (T4.1 + T4.2 + T4.3; brief + allowance already written
at `g0/B3-IMPLEMENTER.md` / `-allowance.json`), then G4 batch review.
Also queued (non-blocking for B3): the G3-RESIDUAL-RG21-ASYMMETRY
follow-up production card (`vibecomfy/comfy_nodes/agent/authority_receipts.py`
ingest alignment), which must land before T7.2.

### Controls

This evidence append changes only allowed evidence files (execution log
+ manifest; test-shards.json untouched) in one coherent commit authored
by `POM <peter@omalley.io>`. No receipt, protected state, branch, or
other file is changed; no push, merge, promotion, live/model/runtime
call, secret access, wrapper dispatch, review, validator change, or
product/test run is performed by this evidence recorder; the recorded
push and named-shard run were executed by the B2-INTEGRATION agent, not
by this recorder. No receipt is committed; the reviewed receipts stay
untracked run artifacts. The wrapper records this recorder's own
`end_ts` and receipt digest after exit; neither is computed or recorded
here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## B3 implementer disposition — T4.1 + T4.2 + T4.3 (2026-08-22)

### B3-IMPLEMENTER register

- **Task/label/role/route:** `B3-IMPLEMENTER` / `B3 implementer: T4.1
  [XHARD] shared research evidence contract + T4.2 [HARD] staged adapter
  + T4.3 [HARD] threaded adapter` / implementer / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/B3-IMPLEMENTER-receipt.json` (file
  SHA-256
  `209db6f99a61663267149c7f5f8d716049f753a95e57bbe3baa03c4cebe39781`);
  window `2026-08-22T05:18:30Z` → `2026-08-22T06:30:59Z`, launcher exit
  `0`; base `69b6fcf17cf081d7726c882740462f51e5229d24`; commit
  `160042304761fbb6069ee0bc46b134c25625c071` — single batch commit (the
  three cards interlock through the shared contract layer; permitted per
  brief); 16 changed files, all within allowance (+1008/−106, zero
  violations verified programmatically against the machine allowance);
  result SHA-256
  `db1fd034b15c2fc339ade5fe8c8208538b01a11d81389d0b4570fc7ad07447a7`;
  `stop_or_judgment` empty (`JUDGMENT_REQUIRED: none`); full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/B3-IMPLEMENTER-dispatch.log`.

### T4.1 PASS — shared research evidence contract

- **Shared field set pinned:** `RESEARCH_EVIDENCE_SHARED_KEYS`
  (`contracts.py:2171`) = {mode, route, research_attempt, status,
  decision_turns, tool_calls_executed, tool_call_statuses,
  evidence_artifacts, citations, budget, diagnostics, ledger}; both
  carriers project every key (counts/bytes may differ).
- **Budget/deadline persisted:** staged trace budget snapshot
  (`agent_research_stage.py:1897`: deadline_seconds/turns_used/
  deadline_reached) and threaded `_durable_research_budget`
  (`contracts.py:2380`); also persisted on `StagePackage.budget` with
  additive-with-omission serialization verified byte-stable for legacy
  packages.
- **Unsupported-source parity:** policy moved to shared
  `contracts.source_policy_entries:2129`, applied by the threaded
  projection to the host-authored plan, plus a typed
  `research_phase_deadline` diagnostic on deadline exhaustion.
- **Typed per-entry status:** optional `EvidenceLedgerEntry.tool_status`
  (`evidence_pack.py:181`, additive emission at `:224`) stamped for
  executed AND refused calls at the single seam
  `tool_specs.project_tool_evidence:946`; status-prefixed prose
  conclusions unchanged.
- Cross-mode equality tests added
  (`tests/test_executor_threaded_mode.py:575-673`). Count bases frozen
  as a documented designed difference (staged counts network executions
  excluding cached replay; threaded counts any statement with an
  executed status incl. cached) rather than behaviorally unified —
  unifying would change RC2-gate inputs and live-harness attestation
  semantics for zero consumer value.

### T4.2 PASS — staged adapter freeze; deadline unified on 450s

- **Deadline decision (recorded): one canonical default.**
  `RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS = 450.0`
  (`tool_contracts.py:32`); both readers (`core.py:1364`,
  `edit_batch_repl.py:999`) read this single name — the batch-REPL's
  undocumented 600s outlier is gone. Rationale: core.py's own comment
  claimed parity with the batch-REPL path; three prior sites already
  said 450; the stage constant now aliases the same value.
- Five seams untouched and mode-neutral; wire bytes preserved
  additive-with-omission (`Report.to_dict` keeps orchestration_mode
  omission for staged); reply stays a separate spec'd provider call;
  new evidence fields are additive inside `report.research` only
  (envelope-level bytes stable). Wire tests added
  (`test_pipeline_mode_surface.py`: staged omission + envelope
  stability + both-carrier round-trip through
  `serialize_executor_result`; one updated pin
  `test_executor_flows.py:766` — the C5 "no ledger on research route"
  assertion became "compact typed ledger present, no bodies", the
  deliberate T4.1 alignment).

### T4.3 PASS — threaded adapter obligations; two decisions recorded

- **Continuation substrate DECISION: chat-artifact continuation frozen
  canonical.** `THREADED_CONTINUATION_SUBSTRATE = "chat_artifacts"`
  (`threaded.py:49`). Reasoning: the agent-edit host is the single
  session/turn/checkpoint/replay authority and single durable writer;
  wiring `host_ports.thread_*` into the driver would create a second
  write path with no reader (model memory comes from
  `read_session_chat`+PROMPT_MEMORY_MESSAGES below the kernel seam),
  adding lease-conflict failure surface over an already-proven carrier.
  Tests: poisoned-hook two-turn drive proves the driver never consumes
  thread_* hooks + substrate constant pinned
  (`test_executor_threaded_sessions.py`); Row-7 recovery
  (receipt+accepted_batch ⇒ applied, else undetermined) proven
  mode-identical (`test_executor_threaded_edits.py`).
- **Budget-reserve DECISION: advisory-only.** Reserves validate the
  ceiling partition but are not subtracted from host `max_batches` —
  enforcement would break the pinned 24-ceiling contract and duplicate
  the edit kernel's own atomic limits. Docstring records it; validation
  test passes again (the implementer initially dropped
  `ThreadedPurposeBudget.__post_init__` in an edit; restored and
  re-pinned).
- Classifier-free sentinels pass (no threaded request reaches
  `_run_classify`); graphless research via shared ToolSpec registry;
  answer-only inspect returns graph=None; terminal projection parity
  across modes tested directly.

### Focused command results and pre-existing-failure verification

| Command | Result |
|---|---|
| pytest focused batch (7 files) | **255 passed, 5 failed**, exit 1 |
| node --test (2 browser files) | **20/20 pass**, exit 0 |

The 5 pytest failures were verified IDENTICAL at base HEAD `69b6fcf1`
in a disposable worktree (removed afterward) — pre-existing, not
regressions: 3× `test_executor_flows.py` (rollback-graph promotion ×2,
pure-clarify narration text), 2× `test_executor_threaded_mode.py`
(graph identity-after-projection ×2); owned by T6.2 classification.
Disclosed per run-at-most-once: the pytest batch was iterated more than
once during development before the final quoted run.

### Residual risks

- Staged wire bytes gain additive keys inside `report.research`
  (budget/tool_call_statuses/etc.) when data exists — any external
  consumer doing exact-dict equality on that sub-object would notice;
  envelope-level bytes stable.
- Threaded `status` derivation keys off the host's typed
  `report.phase_deadline_seconds`/findings-budget marker; if the batch
  host ever stops writing those, threaded falls back to `"ok"`
  (fail-toward-ok on that one field, bounded by explicit
  `deadline_reached=False`).
- The 5 pre-existing base failures remain unfixed (outside card scope;
  files touched only where required).

### Next unblocked card

G4 batch review: ONE stealth review of the whole B3 diff (commit
`16004230`), doubling as the G4 gate per C10; attack surface: typed
route, graph/schema identity, accepted delta validity, terminal state,
failure family, evidence, idempotency, cost — never prose as
correctness. Then integration push (`d564de9e..HEAD`), then
G3-RESIDUAL-RG21-ASYMMETRY card, then B4 (T5.1→T5.5), then G5.

### Controls

This evidence append changes only allowed evidence files (execution log
+ manifest; test-shards.json untouched) in one coherent commit authored
by `POM <peter@omalley.io>`. No receipt, protected state, branch, or
other file is changed; no push, merge, promotion, live/model/runtime
call, secret access, wrapper dispatch, review, validator change, or
product/test run is performed by this evidence recorder; the recorded
B3 implementation was executed by the B3-IMPLEMENTER agent, not by this
recorder. No receipt is committed; the reviewed receipts stay untracked
run artifacts. This evidence recorder's own wrapper PID is `80240`,
start `2026-08-22T06:31:49Z` per `active-allowances.json`; this
recorder's own receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-B3-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## G4 batch/gate review — G4-B3-REVIEW disposition (2026-08-22)

### G4-B3-REVIEW register

- **Task/label/gate/role/route:** `G4-B3-REVIEW` / `G4 [XHARD-REVIEW]
  batch/gate review of the B3 window (T4.1+T4.2+T4.3)` / gate `G4` /
  reviewer / model route `stealth/ox-alpha`, resolved
  `stealth/ox-alpha`.
- **Receipt/result:** `receipts/G4-B3-REVIEW-receipt.json` (file
  SHA-256
  `6ce7647ef9cf1aa5eb2b416297223e02ce74548d8d174bad4565cd04751b4631`);
  window `2026-08-22T06:41:50Z` → `2026-08-22T07:00:58Z`, launcher exit
  `0`; base `160042304761fbb6069ee0bc46b134c25625c071`; zero changed
  files, zero commits (read-only); brief SHA-256
  `933ef231eb138b30359efd1a250f5d0e53882ddff2b821db5fc7f1198e8d4741`;
  result SHA-256
  `dee7ec0f1a27e6340025661ded4582c81ca8dabaf851b546f499ca6498f52faf`;
  `stop_or_judgment` empty (`JUDGMENT_REQUIRED: none`); full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/G4-B3-REVIEW-dispatch.log`.
- **Verdict: `continue`.** G4 discharged: the B3 window satisfies plan
  G4 acceptance plus the relevant binding conditions; NO must findings.
- **Window scope verified:** range `69b6fcf1..16004230` = exactly one
  commit, 16 files (+1008/−106) matching the B3 receipt's
  `changed_files`; no unauthorized files.

### Merge recommendation (advisory)

Integrate `16004230` together with the concurrently-landed evidence
commit `7821a86d` (evidence-log-B3, this operating worktree). Carry
the 5 pre-existing focused failures forward as known-failing with the
exact IDs below; they are not B3-introduced and do not block G4, but
they remain G7-blocking if still unfixed at finale time.

### T4.1 PASS — shared research evidence contract

- `RESEARCH_EVIDENCE_SHARED_KEYS` (12 keys) produced by BOTH carriers:
  staged `AgentResearchResult.to_dict`; threaded
  `_durable_research_evidence`.
- Attempt typing Python-derived on both sides (never prose);
  executed-call base reconciled over typed statuses only.
- Budget/deadline persisted both sides with `deadline_reached` always
  emitted; unsupported-source parity via a single shared
  `source_policy_entries` (duplicate constant deleted — one definition
  remains); per-ledger-entry `tool_status` stamped at the ONE seam,
  additive-with-omission.
- Cross-mode parity pinned by three new `test_t41_*` tests.

### T4.2 PASS — staged adapter freeze; deadline unified on 450s

- Exactly two env readers of `VIBECOMFY_RESEARCH_PHASE_DEADLINE`, both
  falling back to the single
  `RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS = 450.0` — the 600s outlier
  is gone.
- Wire compatibility preserved additive-with-omission (no renames,
  pinned); separate reply-model behavior untouched;
  closed-checkpoint projection authority intact at 4 sites.

### T4.3 PASS — threaded adapter obligations; decisions consistent

- Classifier-free: sole `_run_classify` call site sits inside
  `_run_staged_executor`, unreachable for threaded. Graphless
  research: no `run_agent_research_stage` on the threaded path;
  answer-only inspect returns graph=None.
- Accepted batch sole authority: projection refuses applied without
  persisted ops/replay_ok. Row-7 recovery fail-closed. ONE
  mode-neutral projector (`del mode`).
- Three recorded decisions consistent with code: continuation
  substrate = chat_artifacts consumed at `_frag_entrypoint.py:351`;
  reserves advisory-only with hard ceiling 24; deadline unified at
  450s.

### G4 attack surface walked

Typed route; graph/schema identity (untouched); accepted delta
validity; terminal state; failure family; evidence; idempotency; cost
— no prose-as-correctness found anywhere in the diff.

### 5 pre-existing failures — CONFIRMED PRE-EXISTING

Focused pytest at HEAD `16004230`: 255 passed, 5 failed. Base export
(`git archive 69b6fcf1`) reproduces all 5 with identical assertion
shapes; introduced-by-B3 count: **0**. Browser node batch: 20 pass /
0 fail. Carry-forward with exact IDs (known-failing; owned by T6.2
classification):

- `tests/test_executor_flows.py::TestSimpleEditFlow::test_simple_edit_pure_clarify_is_not_promoted_to_candidate`
  (pure-clarify narration text)
- `tests/test_executor_flows.py::test_terminal_no_candidate_reply_still_grounds_ids_against_original_graph`
  (rollback-graph promotion)
- `tests/test_executor_flows.py::test_terminal_no_candidate_response_does_not_promote_rollback_graph`
  (rollback-graph promotion)
- `tests/test_executor_threaded_mode.py::test_threaded_accepted_edit_survives_projection_failure`
  (graph identity-after-projection)
- `tests/test_executor_threaded_mode.py::test_threaded_run_uses_execute_profile_closed_checkpoint_and_hard_cap`
  (graph identity-after-projection)

### Evidence coherence

The reviewer-worktree validator exit 1 was environmental: receipts are
untracked run artifacts absent in the fresh review worktree, and the
T1.2-MUST-001 chain is Batch-1-era. The operating worktree validator
at `7821a86d` returns OK, exit 0. final-five/final50 unchanged across
the window.

### Next unblocked card

Integration push (`d564de9e..HEAD`, including `16004230` + `7821a86d`
+ this commit), then evidence-log-integration, then the
G3-RESIDUAL-RG21-ASYMMETRY card (XHARD, before T7.2), then
B4-IMPLEMENTER (T5.1→T5.5; brief + allowance already written at
`g0/B4-IMPLEMENTER.md` / `-allowance.json`), then G5 batch review
(test-shard inventory may overlap the final G5 review).

### Controls

This evidence append changes only allowed evidence files (execution
log + manifest; test-shards.json untouched) in one coherent commit
authored by `POM <peter@omalley.io>`. No receipt, protected state,
branch, or other file is changed; no push, merge, promotion,
live/model/runtime call, secret access, wrapper dispatch, review,
validator change, or product/test run is performed by this evidence
recorder; the recorded G4 batch review was executed by the
G4-B3-REVIEW agent, not by this recorder. No receipt is committed; the
reviewed receipts stay untracked run artifacts. This evidence
recorder's own wrapper PID is `81442`, start `2026-08-22T07:01:56Z`
per `active-allowances.json`; this recorder's own receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-G4-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## B3-window integration push — B3-INTEGRATION disposition (2026-08-22)

### B3-INTEGRATION register

- **Task/label/gate/role/route:** `B3-INTEGRATION` /
  `B3-INTEGRATION: apply reviewed chain, run named batch shard once,
  fast-forward push` / gate `` (empty) / integration / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/B3-INTEGRATION-receipt.json` (file
  SHA-256
  `1fc802a3c353024e07ee54447582a6b18cd1c5b4c303fb1c21f718786f02847a`);
  window `2026-08-22T07:11:18Z` → `2026-08-22T07:14:30Z`, launcher
  exit `0`; base `453d1af6f65eb64b708d9b7452e75fd23a38e1c0`; zero
  changed files, zero commits (read-only integration); brief SHA-256
  `941c07be19edb14c18bd98dade5c9621cbc32042dc524f841320d3c7e1e6da28`;
  result SHA-256
  `6b8ca99b9dcc65e7ef0eecf28045a0feb8f37f8f7ac18225135145bf4a296b68`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/B3-INTEGRATION-dispatch.log`.

### Push executed

- **Command:** `git push origin
  HEAD:fixer/workflow-execution-spine-consolidation` → range update
  `d564de9e..453d1af6`, fast-forward (no force; merge-base ancestor
  check true), exit `0`. Remote before (`git ls-remote`, live):
  `d564de9e146dd69a08d5aaf9530efc4186d7fad2`.
- **Remote after verified:** `git ls-remote` returns
  `453d1af6f65eb64b708d9b7452e75fd23a38e1c0` == local HEAD at record
  time (re-verified read-only by this recorder).
- **Pushed range covers four commits:** `69b6fcf1` (B2-window
  integration push disposition record riding this push per the
  established pattern), B3 implementer `16004230` (T4.1+T4.2+T4.3),
  evidence `7821a86d` (B3 implementer disposition), and `453d1af6`
  (G4 batch/gate review disposition).

### Named batch shard (run exactly once)

- Focused pytest over the 7 executor/threaded/pipeline files
  (`test_executor_flows`, `test_agent_research_shadow`,
  `test_executor_threaded_contracts`, `test_executor_threaded_mode`,
  `test_executor_threaded_sessions`, `test_executor_threaded_edits`,
  `test_pipeline_mode_surface`): **255 passed, 5 failed**, 29
  warnings in 6.43s, exit `1` (expected).
- The 5 failures are **exactly the G4 pre-existing set** — 3×
  `test_executor_flows.py` (rollback-graph promotion ×2,
  pure-clarify narration) + 2× `test_executor_threaded_mode.py`
  (graph identity-after-projection) — same families, same IDs;
  new failures: **0**; matches the G4 record.

### Next unblocked card

The `G3-RESIDUAL-RG21-ASYMMETRY` card (XHARD production repair,
`vibecomfy/comfy_nodes/agent/authority_receipts.py` converter
alignment; must land before T7.2; brief + allowance already written
at `g0/G3-RESIDUAL-RG21-ASYMMETRY.md` / `-allowance.json`), then its
evidence, then `B4-IMPLEMENTER` (T5.1→T5.5; brief + allowance at
`g0/B4-IMPLEMENTER.md` / `-allowance.json`), then G5 batch review
(test-shard inventory may overlap the final G5 review), then
integration + evidence.

### Controls

This evidence append changes only allowed evidence files (execution
log + manifest; test-shards.json untouched) in one coherent commit
authored by `POM <peter@omalley.io>`. No receipt, protected state,
branch, or other file is changed; no push, merge, promotion,
live/model/runtime call, secret access, wrapper dispatch, review,
validator change, or product/test run is performed by this evidence
recorder; the recorded push and shard run were executed by the
B3-INTEGRATION agent, not by this recorder. No receipt is committed;
the reviewed receipts stay untracked run artifacts. This evidence
recorder's own wrapper PID is `82072`, start `2026-08-22T07:15:11Z`
per `active-allowances.json`; this recorder's own receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-B3-INTEGRATION-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.

## G3-RESIDUAL-RG21-ASYMMETRY closure — residual repair disposition (2026-08-22)

### G3-RESIDUAL-RG21-ASYMMETRY register

- **Task/label/gate/role/route:** `G3-RESIDUAL-RG21-ASYMMETRY` /
  `G3-RESIDUAL-RG21-ASYMMETRY [XHARD]: align
  authority_receipts.recompute_apply converter with executor ingest
  (land before T7.2)` / gate `G3` / implementer / model route
  `stealth/ox-alpha`, resolved `stealth/ox-alpha`.
- **Receipt/result:** `receipts/G3-RESIDUAL-RG21-ASYMMETRY-receipt.json`
  (file SHA-256
  `bfa4f32ebe0935558b2168554973f0ecb3814186e8522c5896821c2471e185d6`);
  window `2026-08-22T07:23:04Z` → `2026-08-22T07:36:01Z`, launcher
  exit `0`; base `730fb7222e87c679c360a37884b59fb1db9472e7`
  (post-B3-integration; B3+G4 landed before it); commit
  `7c919305909fd81042d3d0691785fbd2a290d959`; changed file
  `vibecomfy/comfy_nodes/agent/authority_receipts.py` only (+12/−1,
  within allowance); brief SHA-256
  `9d7307c4efa035b20b8f36bd9d2392961043a6378fe8ca24218c5d0c731eff4b`;
  result SHA-256
  `b790ceff1bc872702663b134555a8191de464af3e155792b96d08c641bb95a3c`;
  `stop_or_judgment` empty; full body at
  `/workspace/vibecomfy-exec-spine-20260820/g0/G3-RESIDUAL-RG21-ASYMMETRY-dispatch.log`.

### Root cause

`recompute_apply` ingested the submit graph via
`from_ui(dict(submit_graph), schema_provider=schema_provider)`
(`authority_receipts.py:320` pre-fix), inheriting `from_ui`'s default
`use_comfy_converter=True` (`normalize.py:1230`), which attempts the
host's comfy converter `convert_ui_to_api`
(`normalize.py:516-549`). Live executor ingest pins `False` in both
twins (`session.py:444`, `_gates.py:314`). On comfy hosts where the
converter imports AND diverges from `_normalize_ui_to_api`, replay IR
≠ live IR → loud fail-closed `candidate_hash_mismatch`. In this
environment the bug is inert (no `comfy` module;
`check_comfy_compatibility()` fails `comfyui_version_unknown`), so
both selections collapse to `_normalize_ui_to_api` today.

### Fix

One call site (`authority_receipts.py:320`): `recompute_apply` now
passes `use_comfy_converter=False` with a comment citing both
executor pins. Replay selects the identical converter as live ingest
on every host.

### Failure-injection proof (simulated comfy host)

`/tmp/rg21-asymmetry/probe_converter_asymmetry.py` injects a fake
importable divergent `convert_ui_to_api` and patches
`check_comfy_compatibility` to OK, then compares `recompute_apply`
against the R-G2-1 executor-model candidate on the
sequential-invariant test's delta:

- Base: converter invoked **1× by replay only**, hashes diverge
  `7804d399…` vs `7b1ac49e…`, exit 3.
- Fixed: converter invocations **0** (the `False` pin never attempts
  the import), hash `7804d399…` = `7804d399…`, exit 0.

Divergence channel **structurally closed**:
`use_comfy_converter=False` never imports or calls the converter
(`normalize.py:479-481`) — no host can re-open the channel; not
merely unobserved.

### Tests

`tests/test_authority_replay_sequential.py` → **2 passed**, exit 0
(R-G2-1 intact, not weakened); `tests/test_authority_receipts.py` →
**11 passed**, exit 0. Each run once, caches disabled.

### Closure

**G3-RESIDUAL-RG21-ASYMMETRY CLOSED** (landed before T7.2 as
required).

### Next unblocked card

`B4-IMPLEMENTER` (T5.1→T5.5; brief + allowance at
`g0/B4-IMPLEMENTER.md` / `-allowance.json`), then G5 batch review
(test-shard inventory may overlap final G5 review), then integration
+ evidence.

### Controls

This evidence append changes only allowed evidence files (execution
log + manifest; test-shards.json untouched) in one coherent commit
authored by `POM <peter@omalley.io>`. No receipt, protected state,
branch, or other file is changed; no push, merge, promotion,
live/model/runtime call, secret access, wrapper dispatch, review,
validator change, or product/test run is performed by this evidence
recorder; the recorded residual repair was executed by the
G3-RESIDUAL-RG21-ASYMMETRY agent, not by this recorder. No receipt is
committed; the reviewed receipts stay untracked run artifacts. This
evidence recorder's own wrapper PID is `82717`, start
`2026-08-22T07:36:30Z` per `active-allowances.json`; this recorder's
own receipt path is
`docs/plans/workflow-execution-spine-consolidation-evidence/receipts/evidence-log-G3-RESIDUAL-receipt.json`,
written by the wrapper together with this recorder's own `end_ts` and
receipt digest after exit; neither is computed or recorded here.

- **Validator proof:** the required read-only command
  `python3 scripts/validate_workflow_execution_spine_evidence.py
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  runs after this append against the refreshed manifest digests; its
  deterministic passing output
  `OK: docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`
  carries stdout SHA-256
  `1000d84578b5ef510a6b2ae9d447148f7b707c055695707711e2086bd5727224`.
  No product tests are run by this evidence recorder.
