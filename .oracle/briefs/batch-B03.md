# B03 — Semantic pinned-consumer guard (HARD — grok)

Executor: grok (per user directive: grok is the extremely hard task doer).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. **Replace pinned-output link cardinality checks with semantic terminal-consumer equivalence.**
   - Touch: `vibecomfy/porting/emit/ui.py`, `tests/test_porting_ui_emitter.py`.
   - For each pinned node output, compare the set of terminal consumers `{(target_uid, target_input)}` before and after lowering, traversing reroutes and broadcast Set/Get expansion. Link IDs and fan-out cardinality are representation details, not semantics.
   - Preserve fail-closed behavior when an endpoint cannot be resolved. Reject added, removed, or repointed semantic consumers even when link counts happen to match.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py -k 'pinned_semantic_consumer'
```

Four focused tests pass: broadcast expansion and reroute renumbering are accepted; same-cardinality repointing and dropped/added terminal consumers are rejected.

```bash
.venv/bin/python -m pytest -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_porting_ui_emitter.py tests/test_ui_emitter_parity.py
```

## Acceptance criteria

- The known Set/Get broadcast pattern that expands one raw link to four lowered links emits successfully when terminal consumers are unchanged.
- Link-ID changes and reroute insertion/removal do not cause false refusal when terminal `(target_uid, target_input)` sets are equal.
- Repointing, adding, or dropping a real consumer is refused with before/after semantic sets in diagnostics.
- Unresolved endpoints remain a typed refusal, not an assumed equivalence.

## Report
"B03 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
