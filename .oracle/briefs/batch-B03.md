# MEGADO BATCH B03 [HARD] — Canonical semantic pin comparison

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — you are the executor (GPT-5.6 Sol, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context
Pinned-opaque emission currently refuses on ANY link delta. Exploration verified: the pin gate is boolean on any link delta (`widget_shape_fence.py:93-109,249-250`: pin_opaque requires `not has_link_delta`); comparison is uid-keyed but multiset-counted (`layout/delta.py:64,70,88-90`), so 1↔N same-source fan-out = delta; the rewrite layer never refuses on count (`ui.py:1709-1806` stamps IR ids unconditionally; refusal strings at `ui.py:1646-1658` are dead). The known reproduction: Set/Get broadcast lowering expands 1 raw link → 4 lowered links, false-refusing pins (44/131 corpus nodes exposed). Reroute 1:1, loop-cloned consumer UIDs, and nested subgraphs also break pins.

B02/elegance are DONE and on the branch: `VibeWorkflow` IR is the canonical lossless representation with stable UIDs (`properties.vibecomfy_uid`).

## Tasks (from .oracle/tasklist.md B03)

1. **Add fixtures for**: flat Set/Get fan-out; 1:1 reroute lowering; loop-cloned consumer UIDs; nested subgraphs; multi-output nodes; genuine removed/repointed/orphaned consumers.
2. **Replace the raw UID-keyed multiset comparison with ONE canonical semantic-set helper**:
   - preserve input/output port identity;
   - dedupe multiplicity;
   - normalize reroutes to terminal endpoints;
   - normalize loop-cloned UIDs to their canonical consumer UID (use `parse_uid`/`clone_uid` at `lowering.py:317`).
3. **Feed the canonical before/after sets into the pin fence** (`widget_shape_fence.py`).
4. **Refuse when semantic sets genuinely differ** or endpoint resolution is ambiguous/unresolved.
5. **Preserve canonical before/after sets in diagnostics**.
6. **Do NOT revive dead link-count refusal strings or construct a second topology abstraction.**

## Key files
- `vibecomfy/porting/emit/ui.py` (pin emission `:1709-1806`, refusal strings `:1646-1658`)
- `vibecomfy/porting/layout/delta.py` (comparison `:64,70,88-90`)
- `vibecomfy/porting/emit/widget_shape_fence.py` (`:93-109,249-250`)
- `vibecomfy/porting/lowering.py` (`:317` clone_uid, `:865-907` loop lowering)
- `vibecomfy/porting/subgraph_resolve.py` (`:56-76`), `vibecomfy/porting/convert.py` (`:257-292`)
- tests: `tests/test_ui_emitter_widget_shape_verdict.py`, `tests/test_porting_ui_emitter.py`, `tests/test_ui_emitter_parity.py`, `tests/test_b02_rich_preservation.py`

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py -k 'pin or pinned or semantic or consumer or broadcast or reroute'
```
Plus the full files:
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py tests/test_ui_emitter_parity.py tests/test_b02_rich_preservation.py
```
Expected exit 0 (the rerunfailures plugin binds a socket and cannot run here).

## Acceptance
- Multiplicity-only Set/Get expansion passes.
- Equivalent reroute, loop-clone, link-renumbering, and nested lowering passes.
- Added, removed, repointed, orphaned, or output-port-changed consumers refuse.
- Unresolved/cyclic paths terminate deterministically and fail closed.
- Multi-output identity is preserved.
- B02 preservation tests remain green (test_b02_rich_preservation.py must still pass 4/4).

## Report
Return: helper location + signature, the canonical-set algorithm (dedupe/reroute/clone normalization), fixture names, diagnostics shape, pytest output. Do NOT commit.
