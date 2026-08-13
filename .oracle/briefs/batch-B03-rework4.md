# MEGADO B03 REWORK 4 (oracle blocking issue) — SetNode-as-source must resolve passthrough

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `1e6b28c9` — fix on top, do not revert.

## The issue (B03 oracle FAIL, finding 3)

`vibecomfy/porting/layout/delta.py:167` unconditionally emits `setnode_as_source` whenever a `SetNode` has an outbound edge. A real corpus case has one unambiguous inbound and outbound path:

```
36:2 → SetNode 37:LATENT → 40:samples
```

This is resolvable passthrough topology — the compiler already resolves the same case at `vibecomfy/_compile/_resolve.py:172`. B03 instead returns empty semantics + `setnode_as_source:37`, and because resolution issues attach to every node (`delta.py:405`), all 114 nodes get a fabricated delta and an unrelated pinned node refuses. This also breaks B02 preservation (corpus file `011c7ad91694b8c4.json` refuses with 340 mismatches; bypassing only B03's delta computation makes it complete with zero mismatches).

## What to change

In `vibecomfy/porting/layout/delta.py` (the `canonical_semantic_link_set` helper around `:167`): when a `SetNode` (or `GetNode`) is used as a SOURCE with an outbound edge, resolve it through its UNIQUE inbound terminal — passthrough, exactly as the compiler does (`_compile/_resolve.py:172`):
- ONE unambiguous inbound candidate → substitute the inbound terminal (source uid + output) for the SetNode output;
- ZERO or MULTIPLE inbound candidates, or cyclic/unresolved traversal → fail closed (keep the issue, but only for those genuinely ambiguous cases);
- never emit `setnode_as_source` for a resolvable single-inbound case.

Keep all existing behavior (dedupe, port identity, reroute resolution, clone alias corroboration, 10k-hop bound, sorted diagnostics). Do not revive `output_link_count_mismatch`.

## Add regressions (in tests/test_layout_delta.py + tests/test_ui_emitter_widget_shape_verdict.py as appropriate)
1. Unchanged/equivalent direct-SetNode passthrough (`A → SetNode → B`, unchanged) → NO delta, no refusal.
2. Changed-source via SetNode (inbound terminal changes) → delta/refuse.
3. Changed-port via SetNode → delta/refuse.
4. Ambiguous SetNode source (two inbound candidates) → fail closed with the issue.

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py
```
Expected exit 0. Then the B02 preservation suite (slow, allow up to ~5 min):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_b02_rich_preservation.py
```
Expected 4/4 (the corpus file `011c7ad91694b8c4.json` must complete with zero mismatches).

## Report
Return: exact change (file:line), the passthrough resolution rule, each new regression name, focused + B02 pytest output. Do NOT commit.
