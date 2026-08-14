# MEGADO B03 REWORK 7 (oracle blocking issue) — ghost consumer endpoint must fail closed

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `e82d54bf` — fix on top, do not revert.

## The issue (B03 oracle FAIL, finding 3)

`vibecomfy/porting/layout/delta.py:122` records `unknown_consumer`, but `:345` deliberately gives it NO UID attribution, and the global `_after_issues` result is DISCARDED at `:516`. Reproduction (oracle): snapshot an existing source, then add `VibeEdge("1", "0", "ghost", "input")` — the canonical helper reports `unknown_consumer:ghost`, but the semantic delta ends up `{}`, so the pin fence sees no issue → no `RefusedEmit` → a later downstream bare `KeyError` (the ghost consumer is never resolved).

## What to change

1. **Attribute `unknown_consumer` to the known source UID** (the source endpoint IS known even when the consumer is ghost), so the issue lands on a snapshot-present fence target and refuses.
2. **Propagate global unresolved issues through a centrally enforced typed refusal** so even FULLY ghost endpoints (both endpoints missing) cannot escape: the canonical helper must surface unresolved issues in the `semantic_link_set` result such that `_has_link_delta` in `widget_shape_fence.py` refuses — never an empty `{}` followed by a bare `KeyError`.
3. **Add fixtures** (in `tests/test_layout_delta.py` / `tests/test_ui_emitter_widget_shape_verdict.py`):
   - known-source → missing-consumer (ghost) edge: `semantic_link_set` carries an attributed issue AND the pin fence raises `RefusedEmit` (not `{}` + `KeyError`);
   - fully missing-endpoint edge: same — typed refusal, never a bare crash.
4. Keep all prior B03 guarantees (dedupe, port identity, reroute/channel resolution, clone alias corroboration, 10k-hop bound, deterministic diagnostics, genuine-difference refusal).

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py
```
Expected exit 0, including the two new ghost-endpoint fixtures. Then B02 preservation (slow ~6-7 min):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_b02_rich_preservation.py
```
Expected 4/4 (0 corpus mismatches — do not regress the VHS recovery from rework 6).

## Report
Return: exact change (file:line), how issues now reach the fence, fixture names, focused + B02 pytest output. Do NOT commit.
