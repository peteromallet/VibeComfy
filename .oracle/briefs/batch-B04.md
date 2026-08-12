# B04 — Real-schema authority and apply-time combo validation

Executor: DeepSeek V4 Flash (normal executor).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. Put real schemas before provisional evidence everywhere.
   - Touch: `vibecomfy/comfy_nodes/agent/_frag_research.py`, `vibecomfy/comfy_nodes/agent/edit_batch_repl.py`, and focused agent tests.
   - Change all applicable `CompositeSchemaProvider` construction so an existing live/real schema wins and provisional workflow/registry evidence fills only missing classes/fields. The `_frag_research.py:821` one-line swap already landed in G0 (rider); B04 covers the remaining inconsistent sites at `_frag_research.py:874` and `edit_batch_repl.py:1115` plus widget-name derivation.
   - Derive widget/input names presented to the batch editor from the winning real schema.

2. Enforce semantic combo membership before candidate mutation.
   - Touch as required: `vibecomfy/porting/edit/apply_values.py`, `vibecomfy/porting/edit/apply_resolve_base.py`, `vibecomfy/porting/edit/apply_resolve_add.py`, `tests/test_porting_edit_apply_values.py`, and focused end-to-end edit tests.
   - Ensure both add-node values and set-field values use the same validation. Invalid semantic choices are blocking `value_not_in_enum` issues and never reach a candidate. Retain the deliberate warning behavior for missing local asset filenames; do not turn asset inventory into a semantic enum.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q \
  tests/test_porting_edit_apply_values.py \
  tests/test_porting_edit_apply.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  tests/test_comfy_nodes_agent_edit.py \
  -k 'real_schema_precedes_provisional or real_schema_widget_names_drive_batch_catalog or invalid_combo_rejected_before_candidate or asset_enum_accepts_missing_local_asset'
```

```bash
.venv/bin/python -m pytest -q tests/test_porting_edit_apply_values.py tests/test_porting_edit_apply.py tests/test_comfy_nodes_agent_backend_spine.py tests/test_comfy_nodes_agent_edit.py
```

## Acceptance criteria

- A conflicting provisional schema cannot shadow a real schema at any hydration site.
- Batch-visible widget names and choices come from the winning real schema.
- Invalid semantic combo values fail before graph mutation for both add and set paths; no candidate artifact contains the invalid value.
- Valid/coercible choices still land, and missing local model/asset filenames retain their existing warning-only policy.

## Report
"B04 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
