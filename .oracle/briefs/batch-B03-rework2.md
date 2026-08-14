# MEGADO B03 REWORK (oracle blocking issue) — symmetric loop-clone normalization

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `e353e768` — fix on top, do not revert.

## The issue (B03 oracle FAIL, finding 3)

In `vibecomfy/porting/layout/delta.py`, the canonical semantic-link sets are computed asymmetrically: the BEFORE (snapshot) set is canonicalized WITHOUT loop-clone aliases, while the AFTER (live) set applies `after_aliases`. Result: an UNCHANGED already-lowered workflow fabricates a semantic link delta and may wrongly refuse a valid pin.

Reproduced by the oracle:

```text
before:
  source/image -> loop:iter0:consumer/images
  source/image -> loop:iter1:consumer/images
after:
  source/image -> consumer/images
```

The workflow was unchanged after `capture_ingest_snapshot`, yet `compute_field_delta` returned `semantic_link_set` deltas for the source and both consumers.

## What to change

1. In `vibecomfy/porting/layout/delta.py` (`compute_field_delta` around `:334-339`): apply the SAME alias normalization to the before/snapshot set as the after/live set — normalize loop-clone UIDs (`clone_uid`/`parse_uid`/`make_uid` at `lowering.py:317`) on BOTH sides so an unchanged lowered workflow yields an EMPTY semantic delta. The before set must be canonicalized with its own aliases (aliases derivable from the snapshot graph, not the live graph).
2. Add a regression: capture_ingest_snapshot → no mutation → compute_field_delta must return no `semantic_link_set` deltas for an already-lowered loop workflow (the exact oracle reproduction above).
3. Keep the genuine-difference cases refusing (removed/repointed/orphaned consumers still refuse).

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py
```

Expected exit 0, including the new no-mutation loop regression. Also re-run the stress checks (5000-hop chain / 5000-node ring fail-closed / fan-out) to confirm no termination regression.

## Report
Return: exact changes (files + line refs), how aliases are derived for the snapshot side, the new regression name, pytest output. Do NOT commit.
