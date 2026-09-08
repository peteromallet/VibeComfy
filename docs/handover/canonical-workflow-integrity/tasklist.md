# Tasklist v3 — same work, explicit responsibility slots

Future work only. Model/reasoning resolution comes exclusively from run.yaml; every task below is normal and uses worker_normal. No XHARD task is currently justified. Coordinator owns dispatch/counters, reviewers inspect independently, oracle adjudicates consequential uncertainty. NS references mean principles in northstar.md; I references mean implementation criteria in acceptance-ledger.md.

| ID | Outcome / scope | Real dependency and synchronization | Role/class | Acceptance / NS |
|---|---|---|---|---|
| C0 | Preserve/reconcile current source using existing Git/run tools; record actual isolated delivery base and recoverable relevant dirty/untracked bytes | Delivery authorization first; once before mutation, recheck affected source drift; no standalone model gate | worker_normal / normal | Source agreement, no original overwrite; I1,I7; N1,N5,N6 |
| T0 | Reuse PreviewAny evidence; resolve one opaque-node fixture, <=0.5 engineer-day | C0; keep only a short finding if needed, no rediscovery/catalog | worker_normal / normal | Existing preserve/normalize/refuse path; I1,I2; N1,N2,N3,N6 |
| T1 | Existing emitter preparation + canonical publisher enforce content/bundle/sidecar/revision identity and atomic refusal | T0; owns vibecomfy/porting/emit/emit_prepare.py, vibecomfy/workflow_bundle.py, bundle/emitter tests; serialize shared T2 edits | worker_normal / normal | I1,I2,I7; N1,N2,N3,N4,N5 |
| T2 | Public export shares necessary checks, no forced canonical persistence; flags/drafts/recovery remain | T1 for shared implementation; isolated CLI-test preparation may overlap. vibecomfy/commands/port/_export.py and proposed tests/test_canonical_export_integrity.py | worker_normal / normal | I3,I7; N2,N3,N5,N6 |
| T3 | Test Python/typed semantic parity first; fix only demonstrated mismatch, retain actual no-op/rollback/revision behavior | C0 for independent work; wait only if consuming T1/T2 failed invariant or touching shared files. vibecomfy/porting/edit/{session.py,_parse_execute.py,typed_tools.py}; edit/revision tests | worker_normal / normal | I4,I5,I7; N1,N4,N5,N6 |
| T4 | Correct actual docs/help and integrate affected verification | T1–T3 settled; docs/api/m6-public-api.md, docs/architecture/vibeworkflow-ir-everywhere.md, docs/architecture/agent_panel.md, relevant CLI help | worker_normal / normal | I6,I7; N2,N3,N4,N6 |

S1_READY = C0/T0 resolved, T1/T2 coherent on one candidate, I1/I2/I3/I7 scoped tests/evidence ready. ALL_REQUIRED_WORK_AND_TESTS = C0–T4 integrated, required tests passed and I1–I7 evidence ready. These are the only model review triggers declared in run.yaml. Source checkpoints/tests are not extra reviewer gates.

## Proposed validation commands (not executed by planning)

Q0 — focused known preservation fixtures:
```sh
timeout 300 python3 -m pytest -q tests/test_porting_emitter.py::test_canonical_emitter_filters_only_edges_to_removed_ui_only_nodes tests/test_workflow_bundle.py::test_real_converter_backed_public_capture_roundtrips_pair tests/test_workflow_bundle.py::test_canonical_roundtrip_preserves_explicit_none_input_default
```
Q1 — save/bundle/emitter affected checks:
```sh
timeout 600 python3 -m pytest -q tests/test_workflow_bundle.py tests/test_porting_emitter.py
```
Q2 — proposed NEW CLI module, implement before invoking:
```sh
timeout 300 python3 -m pytest -q tests/test_canonical_export_integrity.py
```
Q3 — parity/atomic/revision affected checks:
```sh
timeout 600 python3 -m pytest -q tests/test_porting_edit_apply.py tests/test_porting_edit_revision_lifecycle.py
```
Q4 — docs/help inspection aid (not proof of behavior); manually compare documented entrypoints to tested implementation:
```sh
timeout 60 rg -n 'export_to_json|execution-ready|semantic digest|draft|force-drop|apply_batch|apply_ops' docs/api/m6-public-api.md docs/architecture/vibeworkflow-ir-everywhere.md docs/architecture/agent_panel.md vibecomfy/commands/port
```
Q5 — single final affected matrix, after proposed tests exist:
```sh
timeout 900 python3 -m pytest -q tests/test_canonical_export_integrity.py tests/test_workflow_bundle.py tests/test_porting_emitter.py tests/test_porting_edit_apply.py tests/test_porting_edit_revision_lifecycle.py tests/test_runtime_execution.py tests/test_canonical_user_paths.py
```

Use existing environment and temporary fixtures; no live provider/GPU/server/download/install, <=1 GiB local output. Reuse passing receipts only for matching candidate/input/environment identities and criteria. After correction rerun affected coverage, not the entire matrix by default. compileall is removed as redundant evidence: pytest imports affected code, while docs require source/behavior comparison.

No new custody executable, packet builder, additional reviewer layer, generic normalization engine or speculative compatibility machinery is a task. Unrelated compatibility deletion and broad unknown-node coverage remain deferred. Planning artifact consistency checks do not invoke Q0–Q5 or certify I criteria.
