# Bundle compile import-order investigation

Starting candidate: `b34e2b5d2457caa3597ef355632a3baa52d6c234` (includes
`01f38461` and the runtime-requirement emission transfer).

Both reproductions ran as separate `sys.executable -c` subprocesses, with the
candidate as their working directory. They used the same in-memory fixture as
the original interface probe: `VibeWorkflow('astrid-interface-probe',
WorkflowSource('astrid-interface-probe'))` with one `Integer` node,
`uid='integer-node'`, `value=7`, loaded through public `load_bundle(workflow)`.
Both called `bundle.compile(models_root=Path.cwd() / 'models')` without a
supplied schema provider. This fixture has no model dependency; the check
exercises public compilation and import order, not model installation or GPU
execution. No mocked provider, queue, server, or compiler was used.

The public bundle-first path fails before schema initialization completes.
Importing `vibecomfy.runtime` first succeeds with the same semantic digest.
This is an import dependency defect, not a fixture or model-root setup error.

The cycle is `workflow_bundle.compile -> schema.call_validation ->
schema.provider -> runtime.client` (initializing `runtime.__init__`) `->
runtime.run -> runtime.reconciliation -> porting.widgets.__init__ ->
porting.widgets.aliases -> schema.schema_for`. The last import reads the
partially initialized public schema package.

The owner fix defers historical-widget implementation imports in
`runtime/reconciliation.py` until `reconcile_before_queue` is called, next to
the existing deferred snapshot import. The annotation-only reconciliation
type is imported under `TYPE_CHECKING`. Admission, publication, managed-session
ownership, and execution behavior remain unchanged.

One focused subprocess regression in `tests/test_workflow_bundle.py` compiles
the same fixture in both orders, asserts the candidate module path and exact
API projection, and compares complete approval records. It failed before the
owner fix with the same circular import.

The unchanged fixture succeeds in both fresh processes after the fix. Complete
approval records also compare equal in the regression test. The subprocess
stderr contains only the existing disconnected-node layout warning; there is
no post-fix traceback. The post-fix output below describes the fixed working
tree on the recorded base SHA; the final owner-fix commit contains this report.

## Post-fix subprocess output

```text
--- bundle-first exit=0 ---
interpreter: /Users/peteromalley/.pyenv/versions/3.11.11/bin/python
python: 3.11.11 (main, Jan 28 2025, 20:35:47) [Clang 15.0.0 (clang-1500.1.0.2.5)]
candidate base SHA: b34e2b5d2457caa3597ef355632a3baa52d6c234
fixture: astrid-interface-probe; Integer uid=integer-node value=7
models_root: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/models
module: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/workflow_bundle.py
semantic_digest: 7611d186632864c9e49150868206fd2fe620d4aa80d703859130fb27ed3c5f00
result: ApprovedProjectionRecord
api: {"1": {"class_type": "Integer", "inputs": {"value": 7}}}
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: integer-node
--- runtime-first exit=0 ---
interpreter: /Users/peteromalley/.pyenv/versions/3.11.11/bin/python
python: 3.11.11 (main, Jan 28 2025, 20:35:47) [Clang 15.0.0 (clang-1500.1.0.2.5)]
candidate base SHA: b34e2b5d2457caa3597ef355632a3baa52d6c234
fixture: astrid-interface-probe; Integer uid=integer-node value=7
models_root: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/models
module: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/workflow_bundle.py
semantic_digest: 7611d186632864c9e49150868206fd2fe620d4aa80d703859130fb27ed3c5f00
result: ApprovedProjectionRecord
api: {"1": {"class_type": "Integer", "inputs": {"value": 7}}}
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: integer-node

```

## Validation

- Regression before owner fix: 1 failed with the reproduced circular import.
- Regression after owner fix: 1 passed, 1 warning in 2.12 seconds.
- Existing focused suite: `python -m pytest -q tests/test_runtime_dependency_contract.py tests/test_workflow_bundle.py --basetemp=.pytest_cache/import-order-focused`:
  137 passed, 7 warnings in 38.34 seconds. All temporary test files are within
  the candidate worktree.
- Affected tests: `python -m pytest -q tests/test_runtime_reconciliation.py tests/test_runtime_execution.py tests/test_runtime_run.py tests/test_schema.py tests/test_schema_target_authority.py tests/test_historical_widget_reconciliation.py tests/test_widget_aliases.py --basetemp=.pytest_cache/import-order-affected -o cache_dir=.pytest_cache/affected-cache`:
  260 passed, 1 failed, 1 warning in 50.23 seconds.
- The sole failure is
  `tests/test_schema.py::test_touched_schema_classes_fail_closed_and_preserve_untouched`.
  Its `KnownPromptNode` input snapshot is rejected by existing admission code
  for incomplete/unknown input-spec fields. Re-running that test after
  temporarily restoring `runtime/reconciliation.py` exactly to starting HEAD
  (`git diff --exit-code -- vibecomfy/runtime/reconciliation.py` returned 0)
  produced the identical error: 1 failed, 1 warning in 0.92 seconds. The owner
  fix was restored afterward. This unrelated baseline failure is retained and
  reported; no admission contract, fixture, or quarantine was changed.
- After restoring the owner fix, the subprocess regression plus
  `tests/test_runtime_reconciliation.py` passed again: 9 passed, 1 warning in
  2.93 seconds. `git diff --check` also passed.

## Baseline schema failure evidence

```text
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_touched_schema_classes_fail_closed_and_preserve_untouched ________
vibecomfy/porting/edit/ops.py:559: in require_known_schema_for_operation
    snapshot, _payload = _validated_schema_argument(
vibecomfy/porting/edit/admit.py:691: in _validated_schema_argument
    return value, _schema_snapshot_payload(value, label=label)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
vibecomfy/porting/edit/admit.py:670: in _schema_snapshot_payload
    _validate_schema_payload_structure(payload, label=label)
vibecomfy/porting/edit/admit.py:509: in _validate_schema_payload_structure
    raise _schema_validation_error(spec_path, "input spec has incomplete or unknown fields")
E   vibecomfy.schema.types.SchemaSnapshotError: operation schema authority.schemas['KnownPromptNode'].inputs['prompt'] has malformed schema evidence: input spec has incomplete or unknown fields

The above exception was the direct cause of the following exception:
tests/test_schema.py:2611: in test_touched_schema_classes_fail_closed_and_preserve_untouched
    parse_edit_op(field_op, schema_snapshot=snapshot)
vibecomfy/porting/edit/ops.py:610: in parse_edit_op
    require_known_schema_for_operation(data, schema_snapshot)
vibecomfy/porting/edit/ops.py:564: in require_known_schema_for_operation
    raise EditOpParseError(
E   vibecomfy.porting.edit.ops.EditOpParseError: operation schema authority.schemas['KnownPromptNode'].inputs['prompt'] has malformed schema evidence: input spec has incomplete or unknown fields
---------------------------- Captured log teardown -----------------------------
WARNING  vibecomfy.comfy_nodes.agent.routes:routes.py:2299 vibecomfy agent routes module could not register server routes: No module named 'comfy'
=============================== warnings summary ===============================
../../../../../../.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121
  /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py:121: UserWarning: pytest-rerunfailures not installed; runpod flake-retry markers skipped
    res = hook_impl.function(*args)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
pytest gate counts: passed=0 failed=1 errors=0 skipped=0 xfailed=0 xpassed=0 quarantined_failures=0 unexpected_failures=1 stale_quarantines=245
======================== NEW FAILURES (not quarantined) ========================
  NEW FAIL: tests/test_schema.py::test_touched_schema_classes_fail_closed_and_preserve_untouched
1 new failure(s) detected — add a scoped tests/quarantine/*.txt entry only if intentional.
=========================== short test summary info ============================
FAILED tests/test_schema.py::test_touched_schema_classes_fail_closed_and_preserve_untouched
1 failed, 1 warning in 0.92s

```

## Full pre-fix subprocess output

```text
--- bundle-first exit=1 ---
interpreter: /Users/peteromalley/.pyenv/versions/3.11.11/bin/python
python: 3.11.11 (main, Jan 28 2025, 20:35:47) [Clang 15.0.0 (clang-1500.1.0.2.5)]
candidate SHA: b34e2b5d2457caa3597ef355632a3baa52d6c234
fixture: astrid-interface-probe; Integer uid=integer-node value=7
models_root: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/models
module: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/workflow_bundle.py
semantic_digest: 7611d186632864c9e49150868206fd2fe620d4aa80d703859130fb27ed3c5f00
Traceback (most recent call last):
  File "<string>", line 21, in <module>
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/workflow_bundle.py", line 2652, in compile
    from vibecomfy.schema import get_authoring_schema_provider
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/schema/__init__.py", line 3, in <module>
    from .call_validation import NodeCallValidationIssue, NodeCallValidationReport, validate_node_call
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/schema/call_validation.py", line 6, in <module>
    from vibecomfy.schema.provider import SchemaProvider, schema_for
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/schema/provider.py", line 14, in <module>
    from vibecomfy.runtime.client import ComfyClient
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/runtime/__init__.py", line 1, in <module>
    from .run import (
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/runtime/run.py", line 54, in <module>
    from .reconciliation import assert_execution_snapshot, build_execution_snapshot
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/runtime/reconciliation.py", line 12, in <module>
    from vibecomfy.porting.widgets.historical import (
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/porting/widgets/__init__.py", line 3, in <module>
    from .aliases import (
  File "/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/porting/widgets/aliases.py", line 14, in <module>
    from vibecomfy.schema import schema_for
ImportError: cannot import name 'schema_for' from partially initialized module 'vibecomfy.schema' (most likely due to a circular import) (/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/schema/__init__.py)
--- runtime-first exit=0 ---
interpreter: /Users/peteromalley/.pyenv/versions/3.11.11/bin/python
python: 3.11.11 (main, Jan 28 2025, 20:35:47) [Clang 15.0.0 (clang-1500.1.0.2.5)]
candidate SHA: b34e2b5d2457caa3597ef355632a3baa52d6c234
fixture: astrid-interface-probe; Integer uid=integer-node value=7
models_root: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/models
module: /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.otto/worktrees/multi-repo-publish-20260930/vibecomfy/workflow_bundle.py
semantic_digest: 7611d186632864c9e49150868206fd2fe620d4aa80d703859130fb27ed3c5f00
result: ApprovedProjectionRecord
api: {"1": {"class_type": "Integer", "inputs": {"value": 7}}}
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: integer-node

```
