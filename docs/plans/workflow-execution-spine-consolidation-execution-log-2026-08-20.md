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
