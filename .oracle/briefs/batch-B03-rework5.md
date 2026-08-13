# MEGADO B03 REWORK 5 (oracle blocking issue) — GetNode input-chain resolution

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B03 is in the tree at `59a5f16c` — fix on top, do not revert.

## The issue (B03 oracle FAIL, finding 3)

`vibecomfy/porting/layout/delta.py:199-201` emits `helper_input_unsupported` for every edge entering a `GetNode`. But the repo EXPLICITLY supports this connected display topology (`tests/test_virtual_wire_round_trip.py:70`):

```text
source → SetNode → Reroute → GetNode → consumer
```

The compiler resolves the GetNode's outbound through its channel and removes helper-touching display edges (`vibecomfy/_compile/_resolve.py:136`).

Independent unchanged-workflow reproduction:

```text
before == after:
  uid-dynamic:0 → consumer:images

before_resolution_issues: helper_input_unsupported:get
after_resolution_issues:  helper_input_unsupported:11
result: RefusedEmit
```

A valid unchanged pin refuses solely because of fabricated resolution issues. Also `delta.py:412` attaches any global issue to every snapshot node (fan-out amplification).

## What to change

In `vibecomfy/porting/layout/delta.py` (canonical_semantic_link_set / resolution):
1. **Resolve GetNode INPUT chains** the way the compiler does: an edge entering a GetNode through its channel (SetNode → [Reroute...] → GetNode) is a display edge — resolve the GetNode's outbound to the channel's terminal source (the SetNode's unique inbound terminal), then continue passthrough to the consumer. Never emit `helper_input_unsupported` for a resolvable channel edge.
2. Fail closed ONLY for genuinely unresolvable helper inputs: zero/multiple inbound candidates, cyclic traversal, or a GetNode whose channel cannot be traced to a unique SetNode terminal.
3. Fix the issue fan-out at `delta.py:412`: a global resolution issue must not attach to every snapshot node — attribute issues to the nodes actually involved (or keep them global but do NOT turn them into per-node deltas that refuse unrelated pins). An unchanged workflow must produce zero resolution issues.
4. Add regressions:
   - unchanged `source → SetNode → Reroute → GetNode → consumer` → NO delta, NO refusal (mirror test_virtual_wire_round_trip.py:70);
   - changed source through the channel → delta/refuse;
   - ambiguous channel (two SetNodes feeding one GetNode) → fail closed.

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_ui_emitter_widget_shape_verdict.py tests/test_layout_delta.py tests/test_virtual_wire_round_trip.py
```
Expected exit 0. Then B02 preservation (slow, ~6 min):
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_b02_rich_preservation.py
```
Expected 4/4 (or the known baseline subset — mismatches must stay at/below the rework-4 level of 29, zero new refusals).

## Report
Return: exact change (file:line), the channel-resolution rule, the issue-attribution fix, each new regression, focused + B02 pytest output. Do NOT commit.
