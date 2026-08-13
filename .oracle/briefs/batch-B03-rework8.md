# MEGADO B03 REWORK 8 [HARD] — resolution issues must ALWAYS reach the fence

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — executor GPT-5.6 Sol, workspace-write. You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `cb015415` — fix on top, do not revert.

## The issue (B03 oracle FAIL, finding 3 — third round on issue propagation)

Two independently reproduced cases return NO delta despite canonical resolution issues, both ending in a bare `KeyError` during emission instead of a typed refusal:

1. **Existing consumer, then `ghost source → new Reroute → consumer`**: helper reports `unknown_source:ghost`, but `compute_field_delta()` returns `{}`.
2. **Existing pin, then `new source → ghost consumer`**: helper reports `unknown_consumer:ghost-consumer`, but delta returns `{}`.

Plus a third: an issue attributed to a SCHEMA-BACKED snapshot node is ignored because `widget_shape_fence.py:226` returns `SAFE_TO_REGENERATE` when `static_reasons` is empty — resolution issues are not consulted in that branch.

Root: the attribution core only surfaces issues attributed to snapshot-present nodes; new-node/ghost issues are dropped from the `semantic_link_set` result. And the fence's `SAFE_TO_REGENERATE` decision at `widget_shape_fence.py:226` never checks `before_resolution_issues`/`after_resolution_issues`.

## What to change

1. **`vibecomfy/porting/layout/delta.py`**: propagate ALL canonical resolution issues into the `semantic_link_set` result unconditionally — attributed to the known endpoint when one exists (source known → attribute to source; consumer known → attribute to consumer), and as a global `unresolved` bucket when neither endpoint exists. `compute_field_delta()` must NEVER return `{}` while `canonical_semantic_link_set` reported resolution issues. This must hold for new-node and ghost-endpoint cases alike.
2. **`vibecomfy/porting/widget_shape_fence.py`**:
   - `SAFE_TO_REGENERATE` (and any other non-refuse decision path) must check `before_resolution_issues`/`after_resolution_issues` — any resolution issue forces refuse (fail closed), regardless of `static_reasons`.
   - The decision must be: refuse if semantic sets differ OR any resolution issue exists OR static reasons exist; never SAFE when the canonical set carries issues.
3. **Add fixtures** (in `tests/test_layout_delta.py` + `tests/test_ui_emitter_widget_shape_verdict.py`):
   - `ghost source → new Reroute → consumer`: `semantic_link_set` carries `unknown_source` attributed to the consumer (known side), delta non-empty, fence refuses, NO bare KeyError;
   - `new source → ghost consumer`: `unknown_consumer` attributed to the new source, delta non-empty, fence refuses, NO KeyError;
   - schema-backed snapshot node WITH a resolution issue: fence refuses (not SAFE_TO_REGENERATE), NO KeyError;
   - a fully-global unresolved case (both endpoints ghost) still refuses via the global bucket.
4. Keep all prior guarantees: dedupe, port identity, reroute/channel resolution, clone alias corroboration, 10k-hop bound, deterministic diagnostics, genuine-difference refusal, corpus 0-mismatch (B02 4/4).

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py
```
Expected exit 0, including the new fixtures. Then B02 preservation (slow ~4-7 min):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_b02_rich_preservation.py
```
Expected 4/4 (0 corpus mismatches).

## Report
Return: exact changes (file:line), the issue-propagation rule, the fence decision table, fixture names, focused + B02 pytest output. Do NOT commit.
