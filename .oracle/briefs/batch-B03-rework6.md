# MEGADO B03 REWORK 6 (oracle-adjacent regression) — VHS schema-less pin false refusal

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `59a5f16c` + rework-5 working-tree changes (uncommitted) — fix on top, do not revert.

## The regression (orchestrator-verified)

B02 preservation (`tests/test_b02_rich_preservation.py::test_corpus_rich_preservation_zero_mismatches`) went from **4/4 PASS at pre-B03 base `e1bef3bf`** to 6 corpus files refused at HEAD: `2cedcc6c5431dd67`, `5b2141b686cd7192`, `63a23af8786ffa44`, `be037bf05bec284e`, `c958ee58b616d95a`, `e9f5972f924aaa1c`.

Per-file diagnosis (`2cedcc6c5431dd67`): 4 nodes (35, 56, 131, 143, all `VHS_VideoCombine`) refuse with reasons `['schema_less', 'dict_row_dynamic_widgets', 'link_delta']`. At base the same file passed (mismatches=[], pin_opaque=51). The `link_delta` reason is NEW from B03 — the semantic-set comparison fabricates a delta for these schema-less dict-row nodes whose topology did NOT change, which blocks `_observed_dynamic_widgets_recoverable` (requires `not has_link_delta`).

These VHS nodes are schema-less (no object-info schema) with dynamic dict-row widgets — exactly the class that must be preserved via observed-shape recovery when unchanged.

## What to investigate and fix

1. Reproduce: `.venv/bin/python -m pytest -p no:rerunfailures -q "tests/test_b02_rich_preservation.py::test_corpus_rich_preservation_zero_mismatches"` (slow ~6-7 min; or run the checker directly on `external_workflows/corpus/2cedcc6c5431dd67.json` via `scripts/check_b02_rich_preservation.py check_envelope`).
2. Find WHY the semantic link sets differ for these unchanged VHS nodes: compute `compute_field_delta` before/after for `2cedcc6c5431dd67` and dump `semantic_link_set` — is `before != after`, or is it `before_resolution_issues`/`after_resolution_issues` non-empty (a Set/Get/reroute ambiguity on these nodes' connections)?
3. Fix at the root:
   - If resolution issues are fabricated for these nodes' plumbing, resolve them (consistent with reworks 4+5: passthrough Set/Get channels, terminal resolution, fail closed only on genuine ambiguity).
   - If the sets genuinely differ for unchanged topology, fix the canonicalization (snapshot vs live alias symmetry etc.).
   - The target: for `2cedcc6c5431dd67`, `5b2141b686cd7192`, `63a23af8786ffa44`, `be037bf05bec284e`, `c958ee58b616d95a`, `e9f5972f924aaa1c` the pin check must emit with ZERO mismatches, exactly as at base.
4. Keep all prior B03 guarantees: multiplicity dedupe, port identity, reroute/channel resolution, clone alias corroboration, 10k-hop bound, deterministic diagnostics, fail-closed on genuine differences/ambiguity, `output_link_count_mismatch` not revived.

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py
```
Then (slow):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_b02_rich_preservation.py
```
Expected 4/4 (0 corpus mismatches), matching the pre-B03 base.

## Report
Return: root cause (which axis differed, file:line), the fix, per-file mismatch counts before/after, focused + B02 pytest output. Do NOT commit.
