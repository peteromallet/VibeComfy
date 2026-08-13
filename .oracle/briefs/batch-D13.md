# MEGADO BATCH D13 [HARD] — Corpus integrity, satisfiability, and semantic rubrics

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — you are the executor (GPT-5.6 Sol, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only. `external_workflows/` is symlinked into the worktree (2827 corpus JSONs).

## Context
The 100-scenario corpus at tests/live_agentic_harness/scenarios/ has integrity issues: 40 scenarios are `expect_graph_changed:false`, of which 3 are MISLABELED EDITS (query_type:edit, apply:true, a desired block, but expect_graph_changed:false) that can no-op and still pass; the remaining 37 query non-edits have NO answer-quality judge/rubric; 2 are health controls. The runner discovers scenarios by unrestricted glob — stray files can silently change the lane. The final B09 measurement needs a stable, hashed scenario manifest and source-workflow hashes.

## Tasks (from .oracle/tasklist.md D13)

1. **Check in an authoritative manifest** for the current 100 scenarios: stable ID, path, descriptor SHA-256, inclusion status, source-workflow ID and hash where applicable.
2. **Make runner discovery consume the manifest** rather than an unrestricted glob. Reject missing, changed, duplicate, or unmanifested files.
3. **Audit scenario/query/schema/operation/rubric coherence**, prioritizing all anomalous or revised cases.
4. **Correct the three mislabeled edits** (query_type:edit, apply:true, desired block, expect_graph_changed:false):
   - `video-video-inpainting-with-spline-based-cut-and-dra-485ff2.json`
   - `video-image-to-video-conversion-with-moonvalley-d7853c.json`
   - `multi-3d-preview-and-image-output-workflow-d93baf.json`
   Set edit/change expectations truthfully if satisfiable; otherwise rewrite or replace while preserving coverage; NEVER let them pass as no-ops.
5. **Classify the remaining 37 query non-edits**: 35 semantic product scenarios get explicit expected-answer criteria (rubric: grounded, relevant, correct → pass; hallucinated/wrong/irrelevant/vacuous/empty-but-valid → fail); `live-graph-explanation-smoke` and `speed-distillation-research` become explicit health controls.
6. **Ensure every retained edit `desired` block feeds an active judge** (the edit-intent judge must consume the desired block).
7. **Record every rewrite/replacement** and preserve matched-versus-revised reporting (e.g. a REVISIONS.md or manifest field).
8. **Provision + hash source workflows**: hash the source-workflow JSONs from external_workflows/corpus/ referenced by the scenarios; resolve every workflow_path.

## Verification (run, retain output)
- The manifest selects exactly 100 unique ID/stem-matched scenarios; runner rejects a stray/unmanifested file.
- The 40 no-change-routed cases reconcile as 35 semantic non-edits + 2 health controls + 3 corrected edits.
- The 3 corrected edits cannot pass without a judged graph change or legitimate grounded refusal.
- All 35 semantic non-edits have evidence-backed rubrics.
- Source-workflow hashes resolve (no missing workflow_path).
- Run: `.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_live_agentic_harness_runner_persistence.py tests/test_structural_harness_runner.py tests/test_live_agentic_harness_guard_contract.py` (expect green; the rerunfailures plugin binds a socket and cannot run here).

## Report
Return: manifest location + shape, runner discovery change, the 3 corrected scenarios (before/after), the rubric format for the 35, the health-control marking, rewrite/replacement record, source-hash coverage, pytest output. Do NOT commit.
