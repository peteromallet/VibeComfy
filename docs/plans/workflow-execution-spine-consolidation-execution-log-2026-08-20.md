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

- **Disposition:** custody re-proof complete; commit and independent complete-diff review are the only remaining closure steps for `G0-MUST-CUSTODY-001` at entry time. This is the adjudicated rerun of `G0-revision-custody`, whose no-commit result digest was `2d885fba20ba473d03212ab99367025864d2b94cb2407722eb61ef03a421583c`.
- **Task/gate/label/role:** `G0-revision-custody-rerun`; `G0`; `G0 [HARD-REVISION] re-run base and protected-state custody proof with adjudicated re-baseline`; implementer; route `codex:gpt-5.6-luna`.
- **Binding adjudication:** `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/G0-custody-stop-adjudication-receipt.json`; adjudication `correct`; result digest `221f5ba2528ac2b324f77130ffa3f3807a8e9032fbf28e61615b749c3ccce242`. It establishes that `exec-spine-orchestrator` is this orchestrator's supervisor-created hosting session, matching the `supervisor.log` relaunch at `2026-08-20T23:41:06Z`, and is excluded from the §3.2/§13 protected-state boundary. No other tmux session receives that exclusion.

### Base custody and ancestry

- **Worktree/branch:** `/workspace/vibecomfy-exec-spine-20260820/exec-spine`; `fixer/workflow-execution-spine-consolidation`.
- **Immutable input/base and pre-commit HEAD:** `ac0b84c214d9219f70039f5070781689340dafd9`; `git rev-parse HEAD` exit `0`, result `ac0b84c214d9219f70039f5070781689340dafd9`.
- **Planning commit/tree:** `5fc6be9dbe811df77e43d440ad087440e8bd57b5`; plan SHA-256 `475c8480124e25cca7a5f1a1c1f2aad049499b670cd1b994d8d4feaae995a35e`.
- **Authorized remote:** `git ls-remote origin refs/heads/main` exit `0`, observed `054bce5bdc9c63d68ac7e6141063e1f029a70dcb`, matching the authorized SHA. No fetch was needed and no worktree ref was changed.
- **Ancestry exits:** `git merge-base --is-ancestor 5fc6be9d HEAD` exit `0`; `git merge-base --is-ancestor 054bce5b HEAD` exit `1` as expected.
- **Complete ancestry chain (forward):** `5fc6be9d → 80e60329 → 3629a8d8 → d1dfd8ad → d427f7f6 → 1c2eb90c → b34eb5ad → 337debc5 → ceba112b → f8abb577 → a653d0d2 → d8b406da → ac0b84c2`.
- **History/ref custody:** pre-commit reflog showed the existing chain ending at `ac0b84c2`; no reset, stash, merge, ref mutation, history rewrite, amend, push, or integration occurred. HEAD remained `ac0b84c2` until the single permitted log commit.

### Tree-identical merge proof

- **Required simulation:** remote `054bce5bdc9c63d68ac7e6141063e1f029a70dcb` with plan `5fc6be9dbe811df77e43d440ad087440e8bd57b5`.
- **Primary command/result:** `git merge-tree --write-tree 054bce5bdc9c63d68ac7e6141063e1f029a70dcb 5fc6be9dbe811df77e43d440ad087440e8bd57b5` returned exit `128` because this Git does not support `--write-tree` (`fatal: unknown rev --write-tree`); this read-only command did not mutate the worktree.
- **Equivalent disposable-clone command:** `git clone --no-local --no-hardlinks "$PWD" /tmp/g0-revision-custody-rerun/merge/disposable-clone`; `git checkout --detach 5fc6be9dbe811df77e43d440ad087440e8bd57b5`; `git merge --no-commit --no-ff 054bce5bdc9c63d68ac7e6141063e1f029a70dcb`. Clone/checkout/merge exits were `0/0/0`; merge output was `Automatic merge went well; stopped before committing as requested`; conflict status was clean.
- **Trees:** simulation merge tree `38cc90e21d4710863032d4246fee6a115655c269`; `git rev-parse 5fc6be9d^{tree}` planning tree `38cc90e21d4710863032d4246fee6a115655c269`; `git diff --quiet 5fc6be9d^{tree} HEAD^{tree}` in the disposable simulation exit `0` (`tree_diff_exit=0`).
- **Normalized proof:** `/tmp/g0-revision-custody-rerun/merge/normalized-proof.txt`; SHA-256 `8c7d3c3357bb1f0dbac02d7498868a80496d35f8fbfc3a251bb8fa5f5f8354de`. Raw merge output, exit codes, both tree OIDs, status, and tree-diff evidence are under `/tmp/g0-revision-custody-rerun/merge/`.

### Protected cleanup and manifest comparison

- **T0.0 comparable cleanup bytes:** current SHA-256 equals the T0.0 values for `docs/plans/codebase-structural-cleanup-master-plan.md` (`9c2f692f9f9d2d4bf146603075c1812be011340ae70b098a99c48928547a8e73`), `docs/plans/goal-codebase-structural-cleanup-2026-08-20.md` (`90c1cd0284a7a872cbbe91c8bc7c37e1c6516cd759718d058d41fe1589967890`), and `docs/plans/codebase-structural-cleanup-execution-log-2026-08-20.md` (`01ecd89b4d25f1e289b637a222662c6994a4a7fb645bd4b8ac55c1e45c9e2490`). These are qualified byte comparisons only for paths with an available T0.0 digest.
- **Six-entry manifest:** `tests/live_agentic_harness/threaded_comparison_manifest.json` current SHA-256 `96b287c04718a59e09c4d8046ec4df9b7131644a709ee50eb8cb8a236086c323`, equal to the T0.0 six-entry manifest digest.
- **Index/current scope evidence:** `git ls-files -s --` for the four protected paths and the current SHA outputs are in `/tmp/g0-revision-custody-rerun/protected/`; no validator, manifest, receipt, plan, goal, or evidence file was written. The only permitted repository path for this card is this execution log.
- **Structural cleanup evidence:** `docs/plans/codebase-structural-cleanup-evidence/` is absent. T0.0 supplied no digest for this path; this is not an unchanged-path claim.

### Qualified environmental re-baseline

- **tmux:** current `tmux ls` exit `0`: `exec-spine-orchestrator: 1 windows`; `tmux list-windows -a -F '#{session_name}|#{window_index}|#{window_name}'` exit `0`: `exec-spine-orchestrator|0|bash`. The adjudication records the supervisor-hosting purpose and historical creation/relaunch `2026-08-20T23:41:06Z` and excludes this one session from §3.2/§13. Current identity/window count is recorded, not asserted unchanged from T0.0. No other tmux session was present; the exclusion does not cover any other session.
- **`/workspace/omp-replaces-hermes`:** exists=yes; `git -C ... rev-parse --is-inside-work-tree` exit `128` (`not a git repository`). Current sorted path-list SHA-256 is `d40c3af0eb8ddc53a058f3b29d0df2ea3b06299ee7f18f5f8686660a290b4f6c`, re-observed equal to prior evidence but with no comparable T0.0 baseline. Current `health.log` stat is `type=regular file|size=256813|mtime=1787276593|inode=913082`; current digest is `578651c5e3cbf6462fa80539f2bd604b49cb18a0ac7f52d0e4eccf5083c517db`, versus prior sentinel `size=256318|mtime=1787274793|inode=913082|digest=84527b83a2d6e07a44bd5dde91f7c86e2dedc24a3a3e19b81f504b6bdf062815`. T0.0 recorded only present/untouched, so no byte-identity or unchanged-state claim is made.
- **`/workspace/arnold`:** current `HEAD` `3299a4f076c9d811314ef081bfb594cdf8c084a6`, branch `main`, dirty count `9`; current `git status --short` is captured at `/tmp/g0-revision-custody-rerun/environment/arnold-status.txt`. This is a current baseline, not an unchanged-path proof.
- **Docker:** `docker ps` exit `127`; command unavailable (`error: command not found: docker`).
- **r5 comparison:** expected `/workspace/omp-replaces-hermes/Astrid/.megaplan/bakeoffs/phase-5-20260505/comparison.json` is absent; no current digest is invented; absence is recorded against T0.0 digest `94f47ceba5496129e3b0d6604283ac180db37baf110ee9fe3369d84df88fec14`.

### Command/evidence register and custody controls

- **UTC interval:** start `2026-08-21T01:47:21Z`; all command timestamps and outputs are under `/tmp/g0-revision-custody-rerun/`, with separate `preflight/`, `merge/`, `ancestry/`, `protected/`, and `environment/` paths. End time is recorded by the implementer handoff after commit/review.
- **Read-only command results:** base/branch/status/reflog: `/tmp/g0-revision-custody-rerun/preflight/`; remote/merge/trees: `merge/`; ancestry and expected exits: `ancestry/`; protected hashes/index/absence: `protected/`; tmux/docker/Arnold/omp/r5: `environment/`. The initial two unsupported/syntax-invalid probes (`merge-tree --write-tree`, exit `128`; `rev-list --ancestry-path base HEAD`, exit `128`) are preserved; the permitted equivalent merge and corrected ancestry-range commands passed.
- **Non-mutation:** validator, wrapper, manifest, receipts, plan, goal, cleanup files, protected state, and every repository path other than this execution log were untouched. No tests, full suite, focused product tests, live model/runtime calls, secret access, push, merge/integration, or network operation other than the prescribed `git ls-remote` occurred.
- **Rejected alternatives:** no worktree fetch, no merge commit, no textual-similarity substitution for tree identity, no claim of unchanged state where T0.0 lacks a comparable baseline, and no STOP on the adjudicated hosting-session signal.
- **Residual risks:** Docker remains unavailable; `/workspace/omp-replaces-hermes` and structural-cleanup evidence lack T0.0 comparable baselines; the external health log changed relative to its prior non-baseline sentinel; the execution worktree contains pre-existing untracked evidence/status noise that was not touched.
- **Next unblocked card:** `T0.2-recertification` — fresh Grok XHARD review of the contract/overlap freeze, then G0 gate review; no integration follows this custody card.
- **JUDGMENT_REQUIRED:** none.
- **Required handoff:** one author-correct commit containing only this appended entry, followed by a fresh independent review of the complete base-to-commit diff to close `G0-MUST-CUSTODY-001`.
