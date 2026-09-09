# Tasklist v5 — integrity plus consolidated Pythonic emission delivery

Future work only. Model/reasoning resolution comes from run.yaml; the E1 route resolves through the configured worker_xhard slot. Coordinator owns dispatch/counters, reviewers inspect independently, oracle adjudicates consequential uncertainty. NS references mean principles in northstar.md; I references mean implementation criteria in acceptance-ledger.md.

| ID | Outcome / scope | Real dependency and synchronization | Role/class | Acceptance / NS |
|---|---|---|---|---|
| C0 | Preserve/reconcile current source using existing Git/run tools; record actual isolated delivery base and recoverable relevant dirty/untracked bytes | Delivery authorization first; once before mutation, recheck affected source drift; no standalone model gate | worker_normal / normal | Source agreement, no original overwrite; I1,I7; N1,N5,N6 |
| T0 | Reuse current PreviewAny retention evidence; resolve one opaque-node fixture, <=0.5 engineer-day | C0; keep only a short finding if needed, no rediscovery/catalog | worker_normal / normal | Existing preserve/normalize/refuse path; I1,I2; N1,N2,N3,N6 |
| E0 | Establish failing baseline evidence for natural AST/source shape, live edits, helper lowering, effective semantics, custody, and unknown diagnostics (A1–A6); record importer-shaped exact-syntax assertions that must become behavioral plus identity assertions | C0; use existing emission suites and fixtures; no new framework or source implementation | worker_normal / normal | I8,I9,I7; A1–A6; N1,N2,N3,N5,N6 |
| E1 | Implement the one coupled execution-projection/emitter/finalization/identity kernel: topological constructor kwargs with variables/handles, resolver-owned helper lowering, compact identity/provenance/native-port custody, and no routine replay | E0 and T0; shared emitter/bundle files serialize with T1; route is **worker_xhard / xhard Sol** because projection, value authority, editability, and identity/native-port custody are one nonlocal contract. If custody requires routine IDs or value replay, return to D1 rather than weaken acceptance | worker_xhard / xhard Sol | I8,I9,I7; A1–A6; N1,N2,N3,N4,N5,N6 |
| T1 | Test and integrate current H3 emitter/bundle publication after E1, then fix only demonstrated content/sidecar/revision or atomic-refusal gaps | T0 and E1; current entrypoints are vibecomfy/porting/emit/emit_prepare.py, vibecomfy/workflow_bundle.py:emit_bundle/_atomic_publish_pair/emit_bundle_with_candidate, and existing bundle/emitter tests; shared publication changes serialize | worker_normal / normal | I1,I2,I7,I8,I9; N1,N2,N3,N4,N5 |
| T2 | Test the existing public export split first, then fix only demonstrated gaps; preserve layout-sidecar opt-in, draft/recovery/force-drop behavior and avoid forced canonical persistence | T1; isolated CLI-test preparation may overlap. Current entrypoint vibecomfy/commands/port/_export.py:_should_persist_sidecar/_cmd_port_export; add tests/test_canonical_export_integrity.py | worker_normal / normal | I3,I7,I9; N2,N3,N5,N6 |
| T3 | Prepare and integrate Python/typed semantic parity and emission regression evidence; fix only demonstrated mismatch, retain no-op/rollback/revision behavior | Fixture preparation may begin after C0; integration waits for E1 and any T1/T2 invariant it consumes. Existing paths: tests/test_porting_emitter.py, tests/test_h3_generated_editability.py, tests/test_native_subgraph_expansion.py, tests/test_native_h3_boundary_mapping.py, tests/test_h3_schema_widgets.py, tests/test_workflow_bundle.py, plus vibecomfy/porting/edit/{session.py,_parse_execute.py,typed_tools.py} and edit/revision tests | worker_normal / normal | I4,I5,I7,I8,I9; A1–A6; N1,N4,N5,N6 |
| E2 | Regenerate the exact saved H3 JSON through the shared path; perform the practical prompt/source/mask/duration/seed edit, rebuild and effective wiring/custody comparison; correct truthful guides/CLI status | Shared E1 contract, T1/T2 integration, and T3 evidence; use assets/h3/MiniMax_H3_AV_EncodeDecode_Inpaint.json and the normal VibeComfy entrypoint, with no manual cleanup or bespoke restoration patch | worker_normal / normal | I10,I7; A7; N2,N3,N4,N5,N6 |
| T4 | Correct actual docs/help and integrate the final affected verification | E2 and T1–T3 settled; include docs/guides/workflow-onboarding.md, docs/api/m6-public-api.md, docs/architecture/vibeworkflow-ir-everywhere.md, docs/architecture/agent_panel.md, and relevant CLI help; stale H3 boundary claims must match current code | worker_normal / normal | I6,I7,I10; A7; N2,N3,N4,N6 |

S1_READY = C0/T0/E0/E1 resolved, T1/T2 coherent on one candidate, and I1/I2/I3/I7/I8/I9 scoped tests/evidence ready. ALL_REQUIRED_WORK_AND_TESTS = C0–T4 plus E0/E1/E2 integrated, required tests passed, and I1–I10 evidence ready. These are task dependencies, not additional review stages; run.yaml records these scopes without adding stages or caps. Source checkpoints/tests are not extra reviewer gates. Completion remains unproven until exact-candidate evidence exists.

## Consolidated scope, fidelity, and estimate

The Pythonic contract explicitly supersedes importer-shaped exact syntax with executable behavioral fidelity plus independently tested identity/provenance/native-port custody. Unexpected node/edge/widget loss remains an atomic refusal; no broad loss waiver is introduced. E1 is the only emitter implementation, so the canonical integrity and Pythonic plans share one kernel and do not create duplicate emitters or a second pretty mode.

The unified estimate is **7–10 ordinary focused engineer-days plus 1–2 days contingency**. This is less than summing the two plans because E0/T0 reuse existing audits and fixtures, E1 is one shared emitter/publication seam, T1/T2 consume the same candidate, T3 shares parity/regression evidence, and E2/T4 combine the H3 practical/doc handoff. It is an engineering budget, not an elapsed-time commitment.

## Proposed validation commands (not executed by planning)

Q0 — focused known preservation fixtures:
```sh
timeout 300 python3 -m pytest -q tests/test_porting_emitter.py::test_canonical_emitter_preserves_auxiliary_output_nodes_and_their_edges tests/test_workflow_bundle.py::test_real_converter_backed_public_capture_roundtrips_pair tests/test_workflow_bundle.py::test_canonical_roundtrip_preserves_explicit_none_input_default
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
timeout 600 python3 -m pytest -q tests/test_porting_edit_apply.py tests/test_porting_edit_revision_lifecycle.py tests/test_porting_edit_kernel.py tests/test_porting_edit_session.py
```
Q4 — docs/help inspection aid (not proof of behavior); manually compare documented entrypoints to tested implementation:
```sh
timeout 60 rg -n 'export_to_json|execution-ready|semantic digest|draft|force-drop|apply_batch|apply_ops' docs/api/m6-public-api.md docs/architecture/vibeworkflow-ir-everywhere.md docs/architecture/agent_panel.md vibecomfy/commands/port
```
Q5 — single final affected matrix, after proposed tests exist:
```sh
timeout 900 python3 -m pytest -q tests/test_canonical_export_integrity.py tests/test_workflow_bundle.py tests/test_porting_emitter.py tests/test_porting_edit_apply.py tests/test_porting_edit_revision_lifecycle.py tests/test_porting_edit_kernel.py tests/test_porting_edit_session.py tests/test_runtime_execution.py tests/test_canonical_user_paths.py tests/test_h3_generated_editability.py tests/test_native_subgraph_expansion.py tests/test_native_h3_boundary_mapping.py tests/test_h3_schema_widgets.py
```

Use existing environment and temporary fixtures; no live provider/GPU/server/download/install, <=1 GiB local output. Reuse passing receipts only for matching candidate/input/environment identities and criteria. After correction rerun affected coverage, not the entire matrix by default. compileall is removed as redundant evidence: pytest imports affected code, while docs require source/behavior comparison.

No new custody executable, packet builder, additional reviewer layer, generic normalization engine or speculative compatibility machinery is a task. Unrelated compatibility deletion and broad unknown-node coverage remain deferred. Planning artifact consistency checks do not invoke Q0–Q5 or certify I criteria.

Concrete dispatch briefs, selected source/base rules and startup environment are in [execution-start.md](./execution-start.md). Revalidate the recorded executables in C0; all Q commands remain prospective.

Q6 — E0/E1 focused emission contract (extend these existing suites with the required AST/edit/custody assertions before claiming I8/I9):
```sh
timeout 600 python3 -m pytest -q tests/test_porting_emitter.py tests/test_h3_generated_editability.py tests/test_native_subgraph_expansion.py tests/test_native_h3_boundary_mapping.py tests/test_h3_schema_widgets.py
```

## Observed current-main onboarding baseline

See evidence/h3-main-baseline.md. E0 captures actual port-check/convert refusal (MiniMax class, CLIP enum and schema input errors), rather than assuming the guide path already works. E1/E2 must make the exact source-backed draft conversion/practical edit outcome work through existing representation/schema owners while preserving execution fail-closed behavior. Do not invent schemas or treat missing GPU readiness as semantic loss. T4 corrects raw-JSON inspect/analyze instructions that current authority rejects. No fresh candidate was produced by this baseline; the file opened to the user is the pre-existing main candidate. It does not close I10.
