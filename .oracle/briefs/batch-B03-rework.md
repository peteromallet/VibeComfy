# MEGADO B03 REWORK — pin test timeout regression (infinite loop)

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B03 implementation is in the working tree (uncommitted, from the Sol executor) — fix on top, do not revert.

## The regression (reproduced by orchestrator)

`tests/test_ui_emitter_widget_shape_verdict.py::test_power_lora_style_overflow_pins_from_full_raw_ui_payload`:
- Pre-B03 (stashed): **1 passed in 45.33s**.
- With B03: **TimeoutError (>60.0s, pytest-timeout)**.

So the new canonical semantic-set traversal in `vibecomfy/porting/layout/delta.py` (the B03 helper) hangs on this scenario — most likely a non-terminating loop through reroute/cycle paths or a pathological expansion. The tasklist acceptance explicitly requires: "Unresolved/cyclic paths terminate deterministically and fail closed."

## What to do

1. **Reproduce and root-cause the hang**: run
   `.venv/bin/python -m pytest -p no:rerunfailures -q "tests/test_ui_emitter_widget_shape_verdict.py::test_power_lora_style_overflow_pins_from_full_raw_ui_payload" --timeout=120`
   with faulthandler/pdb or add tracing to find where the traversal spins (which graph: reroute chain? broadcast fan-out? a cycle? a set/loop clone chain?).
2. **Fix the traversal to terminate deterministically**: add explicit cycle/visited-set protection (terminate + fail closed on cycles), bound the fan-out walk, and make reroute-normalization terminate. The semantic helper must return a verdict for every input in bounded time.
3. **Confirm the test passes again in reasonable time** (<60s, ideally much less) AND all B03 fixtures still pass.

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py
```

Expected: all pass including `test_power_lora_style_overflow_pins_from_full_raw_ui_payload` (no timeout). Also run the B03 semantic fixtures:

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py -k 'semantic or pin or consumer or broadcast or reroute or loop or nested or multi_output'
```

## Report
Return: root cause (which path spun, file:line), the termination fix, fixture results incl. the fixed test's runtime, pytest output. Do NOT commit.
