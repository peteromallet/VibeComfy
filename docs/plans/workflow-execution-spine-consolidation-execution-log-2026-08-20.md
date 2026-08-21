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
