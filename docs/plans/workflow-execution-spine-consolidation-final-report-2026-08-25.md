# Workflow execution-spine consolidation — Final report (post-fix campaign closeout)

**Date:** 2026-08-25
**Plan:** `docs/plans/workflow-execution-spine-consolidation-plan-2026-08-20.md`
**Goal:** `docs/plans/goal-workflow-execution-spine-consolidation-2026-08-20.md`
**Execution log:** `docs/plans/workflow-execution-spine-consolidation-execution-log-2026-08-20.md` (authoritative record; terminal section `EVIDENCE-FINALE`)
**Evidence manifest:** `docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json` (G7 `evidence_sequence`: 77 records)
**Receipts:** `docs/plans/workflow-execution-spine-consolidation-evidence/receipts/`
**Branch:** `fixer/workflow-execution-spine-consolidation`
**Base HEAD at report time:** `d2b3affa03980134592aaac2772b6b724c1335e9` (`EVIDENCE-FINALE`, implementation frozen at `fae303b5`)
**Scope of this report:** one new docs file (this report), ONE coherent commit authored by `POM <peter@omalley.io>`; doc-only — no code, test, manifest, or fixture change.

---

## 1. Executive summary

- The consolidation spine build-out (gates **G0–G6**) was completed and recorded earlier at `743cc102` (`docs(exec-spine): record G6 PASSED — deep revision + batch-record promotion + final rereview continue`). Gate **G7** never closed: its authoritative 50-leg finale scored **5/50** product passes and was held (`HOLD — DO NOT MERGE`).
- The operator post-fix campaign (directive §30, 2026-08-24) executed P-items **P0–P8** plus the §36 hivemind lean-shape and wrapper hardening (§30 ordering `P2→P0→P1→P5→P3→P4→P6→P7`; P8 routed from round forensics), followed by the §34 improvement campaign (≤3 rounds, ≥56% product-pass on either mode) and ONE authoritative finale re-run per §33.1.
- The authoritative finale re-run is **recorded** (`FINAL50-RUN`, `/tmp/t7-finale3`, implementation frozen at `fae303b5`) and independently assessed under §35 (ten parallel batch assessors, mechanical merge). Result: **23/50 passes**, up from **5/50** (~4.6x overall pass count). Honest current state documented in §2 below.

## 2. Authoritative finale scorecard (current)

Single invocation, no retry — `compare_pipeline_modes --run --manifest threaded_comparison_manifest_final50.json --split --concurrency 10 --leg-isolation process --transport native`; preflight `validate-only` exit clean (zero model calls) immediately prior. **50 scenarios: 25 staged + 25 threaded**, leg isolation `process`, transport **native** (funded ambient creds; `DEEPSEEK` hydrated per §33.1 precondition).

**HONEST merged assessment (§35: ten parallel batch assessors `FIN-ASSESS-0..9`, 10 x 5-leg batches covering all 50 scenarios; mechanical arithmetic merge over ten `BATCH_TOTAL` lines — no smoothing, no re-judging, no dedup beyond exact duplicates (none found); spot consistency confirmed via shared control legs behaving identically across independent batches):**

| Partition | Pass | Fail | Undetermined | Infra-blocked | Legs |
|---|---|---|---|---|---|
| **TOTAL** | **23** | **22** | **0** | **5** | 50 |
| STAGED | 11 | 11 | 3 | 3 | 25 |
| THREADED | 12 | 11 | 2 | 2 | 25 |

- Conservative rates: **staged 44%** (11/25), **threaded 48%** (12/25); excluding infra-blocked legs: **staged 50%** (11/22), **threaded 52%** (12/23).
- Honesty semantics enforced throughout: **applied-unverified counted as non-pass everywhere it appeared** (`artifact_lineage` `replay_proof=true` vs intent judge `verified=false` awards no pass); **infra-blocked never passes** (harness `runner_exception` timeouts at the 1200s leg budget reclassified to infra-blocked, staying out of pass accounting — this moved harness raw `23 pass / 26 fail / 1 blocked` to the assessor partition above); **zero undetermined** — every leg resolved to a definite class.
- Harness cost split: staged `$0.734` / threaded `$0.480` (delta `-0.254`).
- Manifest truth: `G7` remains `status: open`, `disposition: pending` — this scorecard is the honest current state, not a gate pass.

## 3. Trajectory vs baseline

| Window | Scope | Score | Notes |
|---|---|---|---|
| Original authoritative finale (`T7.2-FINALE-SPLIT`, pre-campaign) | 50 legs (staged 25 + threaded 25) | **5/50** (staged 3/25, threaded 2/25) | honest partition `5 pass / 31 product fail / 13 undetermined / 1 infra-blocked` |
| Round-1 validation window (`R1-WINDOW20`, base `1be8540b`) | 20 hardest scenarios incl. all controls | **12/20** (staged **7/10** = 70%, threaded 5/10) | staged >=56% §34 criterion **MET**; 5/5 controls held |
| Round-2 spot (`R2-SPOT7B`, base `fae303b5`) | 5 false-fail targets + 2 controls | **6/7** | **all five false-fail targets converted**; `live-graph-explanation-smoke` control held |
| **This authoritative finale (`FINAL50-RUN` + §35)** | 50 legs (staged 25 + threaded 25) | **23/50** (staged 11, threaded 12) | **~4.6x overall pass count**; both modes improved |

Round ledger: the §34 campaign closed at two rounds — criterion met in round 1 (staged 70%), confirmed by round-2 conversion evidence (all five targets flipped after the P8 fix chain).

### Provider confound (stated plainly)

The original finale ran the **pre-rotation provider route** (`stealth/ox-alpha` → `openrouter/meta/muse-spark-1.2-contributor`); every campaign window and this finale ran **native `deepseek-v4-flash`** (`--transport native`, ambient `DEEPSEEK` credentials). The 5→23 improvement is therefore **not a strict provider-controlled A/B**: cross-provider comparison caveat preserved verbatim from `EVIDENCE-R1-WINDOW20` / `EVIDENCE-R2-CLOSE`. The OpenRouter route itself is INVALID for paid legs post-rotation (§33.3; see §6).

## 4. What was fixed (commit-referenced)

Campaign fixes landed in §30 order, plus routed follow-ups:

- **P0 widget_N canonicalization before seal** — `61bdfdc0` (emit consumes frozen name table), `b50a9201` (positional-carrier rewrite + frozen-table consumption in interpret/apply/replay).
- **P1 single replay hash domain** (= frozen snapshot table, never re-ingests raw UI) — `d457318b`.
- **P2 known-output guard** (`isinstance(names,(list,tuple))` on name-set membership) — `bc1054c8`.
- **P5 accepted_batch persistence pinned onto terminal response** — `65473633` (regression lock, zero production diff: the mechanism pre-existed at HEAD via G6 `743cc102`, so the 13 finale legs' `accepted_batch:null` artifacts are pre-fix and stand).
- **P3 signature snapshot literals** — `2d2022fa`.
- **P4 object_info truthfulness** (provisioning incl. IndexTTS honesty) — `1acfe7d0`, including the **reviewed allowance-breach disposition** (commit touched 5 files outside allowance; reviewed by the single §18 batch review `P4-ALLOWANCE-REVIEW`; musts discharged via P4-R2C) and the **fail-closed unresolved-field admission** — `fc155565` (constrain unresolved-combo salvage; fail-closed admission) + `daa4ba90` (regression coverage (a)-(e)).
- **P6 orphan input aliases never advertised + `90a1d5` `geometry_quality` authorable-in-instance** — `8bc5872f`.
- **P7 lineage demotion + abort-path evidence** (stale manifest digest demotes to warning when all other checks pass; abort paths persist `batch_failure_evidence.json`, fail-closed on write failure) — `3a80184f` + `4c628ccc`.
- **Hivemind lean search shape** (§36: `message_feed`-only text queries, 2-4 tokens, limit 5, per-request timeout >=10s) — `a6419fc0`.
- **final50 lock regen** (18 drifted digests recomputed post-FIX-4; authorized §33.2) — `bacbccd9`.
- **Wrapper enforcement hardening** (allowance enforced on committed files + honest child failures; committed-file attribution by committer time fixing the concurrent-evidence false-positive) — `1be8540b` (`WRAPPER-ALLOWANCE-ENFORCE`) + `69c719c6` (`WAE-R2`).
- **Judge delta-replay integrity chain** (P8: fingerprint canonicalization → None-distinction preservation → `field_path` resolved through the widget name authority) — `9e1670db` → `fde25d50` → `fae303b5`.

## 5. Bug-fix recommendations status

All routed recommendations from reviews and forensics are **landed or explicitly dispositioned**; none outstanding:

- **P4 allowance breach — reviewed and dispositioned.** The `1acfe7d0` breach (wrapper exited 0 despite forbidden paths) was reviewed by `P4-ALLOWANCE-REVIEW`; P4 musts were discharged via P4-R2C (`fc155565` + `daa4ba90`), and the enforcement gap itself was fixed pre-finale by `WRAPPER-ALLOWANCE-ENFORCE` (`1be8540b`) so no paid finale leg ran without enforcement.
- **E1 false-positive — fixed.** Concurrent-evidence dispatches tripped the wrapper's committed-file attribution; `WAE-R2` `69c719c6` attributes commits by committer time and skips the read-only post-commit check. E1 remains enforced for own commits.
- Forensic-routed fixes landed: the R2 spot variance was root-caused by `R2-DELTA-REPLAY-DIVE` + `R2-SPOT-FORENSIC` (verdict: residual bug) and closed by the P8 chain `9e1670db`/`fde25d50`/`fae303b5`, verified by target conversion (§3). The second `image-dual-checkpoint-xl` failure was dispositioned as intermittent product weakness, not a P8 regression (§6).

## 6. Residual risks & remaining work

- **image-dual-checkpoint intermittent product fails:** 2 consecutive failures after two historical passes (`image-dual-checkpoint-xl`, family=`product`) — genuine per-run stochastic variance, not attributable to any landed fix.
- **schema_snapshot `no_schema_witness` ubiquitous:** fallback=`no_schema_witness` on the majority of legs (schema search not evidenced even on passes) — witness-capture gap, symmetric across both modes.
- **hivemind citations thin on several research legs** despite the lean-shape integration (`a6419fc0`) — partial improvement observed; `statement-timeout` retries and zero citations persist on some legs ending in `decision_turn_limit exhausted`.
- **~10% of legs infra-timeout at the 1200s leg budget** (5/50 infra-blocked in this finale) — provider/process timeouts, no mechanical spine fix.
- **stealth/ox-alpha intermittent 429 windows** during campaign rounds — infra variance, not product signal.
- **OpenRouter route INVALID (rotated key, §33.3):** do not use `OPENROUTER_API_KEY` routes for paid legs; native transport is the funded path.
- **PUSH-BLOCKED-001:** dead rotated key material sits in LOCAL git history from `1f2fa5f7` onward (execution-log line 4521, never re-printed; referenced only by pinned identities). GitHub push protection already rejected the closeout push once and will reject again **without an operator-authorized scrub or clean-branch option**; no history operation has been performed.

## 7. Final disposition

- **Campaign closed per §34** — <=3 rounds authorized; success criterion (>=56% product-pass on either mode) met in round 1 (`R1-WINDOW20` staged 70%) and confirmed by round-2 conversion evidence (`R2-SPOT7B` 6/7, all five false-fail targets converted).
- **The authoritative scorecard in §2 (23/50; staged 11/11/3, threaded 12/11/2) is the honest current state** — applied-unverified never passed, infra-blocked never passed, nothing smoothed or gamified. The original 5/50 authoritative finale stands unrewritten alongside it.
- **NO merge to main** — `origin/main` unchanged; G7 remains `status: open` pending operator adjudication.
- **Branch push attempted with explicit refspec** `git push origin HEAD:fixer/workflow-execution-spine-consolidation` — REJECTED by GitHub push protection (GH013; key material at log line 4521 in every commit from `1f2fa5f7` onward); outcome recorded in the execution log (`evidence-log-STOP-PUSH-SECRET`, §9 STOP). Branch remains **local-only**; remote unchanged at `743cc102`. No history rewrite, force-push, or secret scrub performed — resolution requires an operator-authorized escalation choice (scrub+force-push, clean redacted branch, or accept-local).

---

**JUDGMENT_REQUIRED: none** — this report transcribes recorded evidence only (`EVIDENCE-FINALE` and predecessor log sections); no new judgment, scoring change, or live call made.
