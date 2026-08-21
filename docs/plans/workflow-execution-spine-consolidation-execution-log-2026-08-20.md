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
