# Exact receipt-custody audit

Date: 2026-08-30  
Checkout: `43b60c0463b8872f886d90a3440317f3ec60b460` (`luna/fix-release-outcome`)  
Manifest: `docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json`  
Authoritative source: `/tmp/t7-r1/repo-snap-f4134569`, exact source HEAD `05202e78cd7fdb20c28231f5a6da8af90ab1409c` (receipt bytes transferred to `/tmp/t7-r1-receipts-transfer.0uC9LA/receipts`).

## Contract and method

The canonical validator makes `gates[].evidence_sequence[]` receipt paths the
required custody set (`check_nested_record_accounting`). Other `receipt_path`
strings in task metadata, live-run metadata, and historical artifact lists are
not required by that validator and were treated as text candidates, not as
copy targets.

For every required missing checkout basename, the source was accepted only if
it existed in the authoritative snapshot, its claimed manifest SHA (where
present) matched the source bytes, it decoded as a JSON object, its resolved
destination was contained by the canonical evidence directory, and the
canonical secret-pattern scan was clean. Bytes were then copied unchanged;
no receipt was synthesized or overwritten.

## Classification

The nested validator-required set contained 110 unique missing checkout
basenames. 102 had provenance-clean source bytes and were copied. The copied
set is exactly:

```text
BUG-FIX-APPLY-receipt.json
BUG-FIX-RECOMMENDATIONS-receipt.json
DEEP-AUDIT-FIX-1-ADJUDICATION-receipt.json
DEEP-AUDIT-FIX-1-REVISION-2-CONTINUATION-receipt.json
DEEP-AUDIT-FIX-1-REVISION-2-receipt.json
DEEP-AUDIT-FIX-1-REVISION-receipt.json
DEEP-AUDIT-FIX-1-receipt.json
DEEP-AUDIT-FIX-2-ADJUDICATION-receipt.json
DEEP-AUDIT-FIX-2-REVISION-2-receipt.json
DEEP-AUDIT-FIX-2-REVISION-receipt.json
DEEP-AUDIT-FIX-2-receipt.json
DEEP-AUDIT-FIX-3-ADJUDICATION-receipt.json
DEEP-AUDIT-FIX-3-REVISION-2-receipt.json
DEEP-AUDIT-FIX-3-REVISION-receipt.json
DEEP-AUDIT-FIX-3-receipt.json
DEEP-AUDIT-FIX-4-ADJUDICATION-receipt.json
DEEP-AUDIT-FIX-4-REVISION-2-receipt.json
DEEP-AUDIT-FIX-4-REVISION-receipt.json
DEEP-AUDIT-FIX-4-receipt.json
DEEP-AUDIT-REVIEW-1-REREVIEW-receipt.json
DEEP-AUDIT-REVIEW-1-receipt.json
DEEP-AUDIT-REVIEW-2-REREVIEW-receipt.json
DEEP-AUDIT-REVIEW-2-receipt.json
DEEP-AUDIT-REVIEW-3-REREVIEW-receipt.json
DEEP-AUDIT-REVIEW-3-receipt.json
DEEP-AUDIT-REVIEW-4-REREVIEW-receipt.json
DEEP-AUDIT-REVIEW-4-receipt.json
G0-custody-stop-adjudication-receipt.json
G0-gate-review-receipt.json
G0-recert-adjudication-receipt.json
G0-revision-custody-brief-receipt.json
G0-revision-custody-receipt.json
G0-revision-custody-rerun-2-brief-receipt.json
G0-revision-custody-rerun-2-receipt.json
G0-revision-custody-rerun-2-rereview-brief-receipt.json
G0-revision-custody-rerun-2-rereview-receipt.json
G0-revision-custody-rerun-brief-receipt.json
G0-revision-custody-rerun-receipt.json
G0-revision-custody-rerun-rereview-brief-receipt.json
G0-revision-custody-rerun-rereview-receipt.json
G0-revision-manifest-brief-receipt.json
G0-revision-manifest-receipt.json
G0-revision-manifest-rereview-receipt.json
G0-revision-manifest-revision2-brief-receipt.json
G0-revision-manifest-revision2-receipt.json
G0-revision-manifest-revision2-rereview-receipt.json
G0-revision-validator-adjudication-receipt.json
G0-revision-validator-brief-receipt.json
G0-revision-validator-receipt.json
G0-revision-validator-rereview-receipt.json
G0-revision-validator-violation.json
G0-revision-wrapper-brief-receipt.json
G0-revision-wrapper-receipt.json
G0-revision-wrapper-rereview-receipt.json
G0-revision-wrapper-revision2-brief-receipt.json
G0-revision-wrapper-revision2-receipt.json
G0-revision-wrapper-revision2-rereview-receipt.json
G1-gate-review-receipt.json
G6-B5-REVISION-2-receipt.json
G6-B5-REVISION-receipt.json
G6-DEEP-REVISION-receipt.json
G6-FINAL-REREVIEW-2-receipt.json
G6-FINAL-REREVIEW-receipt.json
G6-FINAL-REVISION-receipt.json
G6-JR-ADJUDICATION-receipt.json
G6-PROMOTE-BATCH-RECORDS-receipt.json
G6-REREVIEW-receipt.json
G6-REVIEW-receipt.json
G7-REVIEW-receipt.json
HARNESS-SPLIT-EXTENSION-REVIEW-receipt.json
HARNESS-SPLIT-EXTENSION-receipt.json
R1-BATCH-REREVIEW-receipt.json
R1-BATCH-REVIEW-receipt.json
R1-FAILURE-ANALYSIS-receipt.json
R1-FIX-APPLY-receipt.json
R1-FIX-REVISION-2-receipt.json
R1-FIX-REVISION-receipt.json
R1-RE-RUN-20-receipt.json
R1-ROOT-CAUSE-receipt.json
R2-BATCH-REVIEW-receipt.json
R2-FAILURE-ANALYSIS-2-receipt.json
R2-FAILURE-ANALYSIS-receipt.json
R2-FIX-APPLY-receipt.json
R2-RE-RUN-20-receipt.json
R2-ROOT-CAUSE-receipt.json
R3-BATCH-REVIEW-receipt.json
R3-FAILURE-ANALYSIS-receipt.json
R3-FIX-APPLY-receipt.json
R3-RE-RUN-20-receipt.json
R3-ROOT-CAUSE-receipt.json
SMOKE-JR-ADJUDICATION-receipt.json
SMOKE-RUN-2-receipt.json
SMOKE-RUN-receipt.json
T0.2-recertification-receipt.json
T6.1-FREEZE-SHARDS-COMMIT-receipt.json
T6.1-FREEZE-SHARDS-receipt.json
T6.2-FOCUSED-SHARDS-receipt.json
T6.3-BROAD-SUITE-receipt.json
T7.2-FINALE-SPLIT-receipt.json
T7.2-FINALE-receipt.json
WRAPPER-ROUTE-FIX-receipt.json
WRAPPER-ROUTE-THINKING-receipt.json
```

Eight required nested basenames had no source in the authoritative snapshot;
they remain absent (all are in `manifest.gates[7].evidence_sequence[56:64]`):

```text
DEEP-AUDIT-RE-RUN-20-receipt.json
MANIFEST-REGEN-FIX4-receipt.json
T29A-REDACT-WRITEPATH-receipt.json
T29A-REVIEW-receipt.json
T29A-REVISION-receipt.json
T29A-REREVIEW-receipt.json
T29A-ADJUDICATION-receipt.json
T29A-REVISION-2-receipt.json
```

The following 19 missing basenames occur only in non-nested historical/task
metadata or live-run/artifact text. They are over-broad candidates for this
validator contract and were deliberately not copied:

```text
B2-IMPLEMENTER-receipt.json
B3-IMPLEMENTER-receipt.json
B4-COMMIT-T5.5-receipt.json
B4-IMPLEMENTER-receipt.json
T0.2-receipt.json
T0.4-plan-amendment-50-receipt.json
T1.1-review-receipt.json
T1.2-validator-repair-receipt.json
T1.2-validator-repair-review-receipt.json
T7.2-FINALE-SPLIT-receipt.json
evidence-log-T1.1-receipt.json
evidence-log-T1.1-verify-receipt.json
evidence-log-T1.1-verify-2-receipt.json
evidence-log-T1.1-verify-3-receipt.json
evidence-log-T1.2-finish-brief-agent-receipt.json
evidence-log-T1.2-receipt.json
t00-receipt.json
t01-receipt.json
wrapper-death-note-t12-rereview.json
```

The pre-existing `t0-3-bootstrap-receipt.json` was preserved and was not part
of the copy set.

## Validation and residuals

The independent custody audit passed: 102/102 copied files matched the
authoritative source bytes, claimed manifest SHA, JSON-object requirement,
containment check, and canonical secret scan; no unreferenced receipt was
added.

Canonical validator command:

```text
python scripts/validate_workflow_execution_spine_evidence.py docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json
```

It exits 1 with the first semantic failure after custody restoration:

```text
NESTED_RECORD_ACCOUNTING: nested T0.2-recertification entry field disposition untruthful: entry 'continue' != receipt None
```

This is not a source-custody failure: the receipt is present, byte- and
digest-authentic, and the authoritative receipt itself lacks `disposition`.
The eight source-absent receipts were intentionally not synthesized; if the
semantic failure is repaired elsewhere, the canonical validator will next
stop on the absent `DEEP-AUDIT-RE-RUN-20-receipt.json` (and then the remaining
seven absent T29A/manifest-regeneration receipts).

Focused test command:

```text
pytest -q tests/test_workflow_execution_spine_evidence.py
```

Result: 39 passed, 1 failed. The failure is the same expected full-validation
baseline test and the same truthful T0.2 disposition mismatch; no quarantine
or test code was changed.
