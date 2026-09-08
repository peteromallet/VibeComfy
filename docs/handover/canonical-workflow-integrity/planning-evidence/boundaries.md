> Historical planning evidence, not executable product certification. Source line numbers refer to the audited baseline. Local receipt/manifest references in this note are provenance descriptions; the compact history and exact published source identity are in ../history.md and ../provenance.md.

# Export/publication boundary exploration

The minimal migration is to make canonical product entrypoints acquire a `WorkflowBundle` (or capture one) while preserving the existing three contracts. Draft save is `emit_bundle`/`capture_bundle`: it already creates semantic/UI digests, provenance and revision identity, atomically publishes Python plus `.vibe.json`, and only requires staged Python loadability and identity (`vibecomfy/workflow_bundle.py:1708-1739,1742-1815`). Do not route draft save through `WorkflowBundle.compile`; compile invokes model/node/schema preconditions (`:1352-1396,1055-1100`) and would violate N2.

UI export/canvas materialization should use the bundle’s sidecar validation and `materialize_ui`, retaining `--out`, `--persist-sidecar`, `--from`, breadcrumb lookup, recovery reports, strict mode, force-drop, and no-write preview behavior in `vibecomfy/commands/port/_export.py:308-411,414-640`. It needs canonical/captured provenance plus canvas safety/fidelity, but not queue readiness. The existing docs explicitly separate `canvas_apply_allowed` from `queue_allowed` (`docs/text-to-graph/mvp.md:410-435,871-893`). API JSON export can remain a projection (`compile("api")`) without itself authorizing execution. Keep `export_to_json` as a compatibility delegate until callers migrate; do not remove it in this plan.

Queue already has the required fence. `authorized_queue_payload` validates authority and calls `ApprovedProjectionRecord.assert_matches` against the current bundle before either server or embedded transport (`vibecomfy/runtime/execution.py:61-129`). `run` and `run_embedded` require the approved record/bundle pair (`vibecomfy/runtime/run.py:61-77,254-269`). No new queue gate or transport collapse is justified.

Trust/provenance remain separate from queue readiness: `load_bundle` marks compatibility JSON as `import_evidence`; `capture_bundle` is the explicit transition to canonical authored provenance (`workflow_bundle.py:1577-1696,1849-1902`). Preserve that distinction and avoid unexpected writes: only publication commands write, while `--out`/preview paths retain current sidecar rules.

Meaningful edit parity work is bounded: existing tests already show Python batches and typed ops converge on `interpret`/apply-gate and preserve unknown-but-representable edits (`tests/test_porting_edit_apply.py:256-322`; dirty evidence adds provider/replay parity around `:163-250`). Add only a focused parity assertion that equivalent batch/typed changes produce the same semantic delta, untouched UID records, and apply eligibility. Do not rewrite both front doors or force identical session-CAS APIs; Python batch lacks `expected_revision` today.

Existing revision/publication coverage should be extended, not replaced: `tests/test_workflow_bundle.py:41-154,893-1004`, `tests/test_porting_edit_revision_lifecycle.py:97-154,743-819`, and `tests/test_runtime_execution.py:78-135`. Proposed commands:

```text
pytest -q tests/test_workflow_bundle.py tests/test_runtime_execution.py
pytest -q tests/test_porting_edit_apply.py tests/test_porting_edit_revision_lifecycle.py
pytest -q tests/test_canonical_user_paths.py
```

Defer universal loader replacement, deleting compatibility aliases, generated-Python rewrite, blanket unknown-node rejection, and new runtime abstractions. The frozen dirty diff shows useful bounded fixes for omitted submit revision identity and representable UI/schema noise; these should be separately reviewed against fidelity reports, not conflated with export migration.
