# MEGADO B03 REWORK 3 [HARD] — canonical semantic-set defects (oracle issues 1–5)

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — executor GPT-5.6 Sol, workspace-write. You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `5ae0f66c` — fix on top, do not revert. The B03 oracle verdict is at `.oracle/checkins/batch-B03.md` (latest FAIL).

## The five oracle issues (lines vs `5ae0f66c`, file `vibecomfy/porting/layout/delta.py`)

1. **[delta.py:264] Snapshot aliases inferred from UID shape alone.** The snapshot side aliases loop clones purely from the textual `*:iterN:*` UID pattern, while the live side requires validated lowering metadata. Consequences: an ordinary consumer UID like `ordinary:iter0:consumer` with NO lowering metadata gets structurally aliased on the snapshot side only → fabricated delta on an unchanged graph. Fix: do NOT infer snapshot lowering aliases from UID shape alone. Persist lowering provenance (or corroborate aliases through validated lowering metadata, e.g. the `vibecomfy.lowering` node metadata / `clone_uid` chain) or require independently validated aliases on BOTH sides. Add an ordinary clone-shaped UID regression (`ordinary:iter0:consumer`, no metadata → NO delta on unchanged graph).

2. **[delta.py:408] Incident attribution loses repointed clones.** Per-node incident slicing uses UNALIASED snapshot UIDs, so a global semantic change can vanish: snapshot = two loop clones both consuming source A; after = one clone repointed to new source B, other stays on A. Global canonical set changes, but `compute_field_delta` returns `{}`. Fix: attribute incident links using CANONICAL aliases and ensure every global semantic difference reaches a snapshot-present fence target. Add the one-clone-to-new-source repoint regression (must refuse).

3. **[delta.py:80] Helper inbound identity discarded.** Helper inbound indexing drops the helper's INPUT port: two distinct inbound helper edges with identical source/output collapse into one candidate and resolve without ambiguity. Fix: preserve helper target-input identity during ambiguity detection; distinct inbound helper endpoints must fail closed. Add a two-distinct-inbound-edges regression.

4. **[delta.py:72] Duplicate-UID diagnostics order-dependent.** Duplicate-UID diagnostics are insertion-order-dependent (reversing a three-node mapping changes which duplicates are reported). Fix: deterministic diagnostics independent of mapping insertion order (sort by canonical key).

5. **[test_ui_emitter_widget_shape_verdict.py:885] Fixture gaps.** The "nested subgraph" fixture is a scoped-UID helper unit test, not a real nested workflow. No concrete multi-output node fixture. Fix: add a REAL nested-subgraph fixture and a CONCRETE multi-output-node fixture (with output-port identity), plus the regressions from issues 1–3.

## Constraints
- Keep: multiplicity dedupe, terminal source/output + consumer/input identity, reroute/Set/Get resolution, fail-closed on unresolved/cyclic, 10k-hop termination bound, sorted diagnostics.
- `output_link_count_mismatch` stays dead (do not revive count-based refusal).
- B02 preservation tests must remain green.

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py
```
Expected exit 0. Also stress: 5000-hop chain / 5000-node ring fail-closed / fan-out / determinism across reversed link order.

## Report
Return: per-issue changes (file:line), how aliases are now corroborated (provenance/metadata path), each new regression name, stress results, pytest output. Do NOT commit.
