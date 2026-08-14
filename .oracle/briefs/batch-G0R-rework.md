# MEGADO G0R REWORK (oracle issues) — landed-count guard fail-open

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run only the focused tests.

## The oracle issue (G0R checkpoint FAIL, finding 2)

The landed-count guard is sound at the core check (`assessor.py:670` reads `change_details.landed_operation_count`, requires int > 0, rejects missing/zero/negative/string/float/bool), but the exemption helper **`_explicitly_non_edit_route` at `tests/live_agentic_harness/assessor.py:214` fails open**: it never reads `response.route`; it trusts self-declared `outcome.kind` and `no_candidate_reason`. Demonstrated fail-open cases:

- `route="revise"`, `graph_unchanged=false`, `outcome.kind="clarify"`, no count → passes with zero errors.
- `graph_unchanged=false`, `no_candidate_reason="route_not_applyable"`, no count → passes with zero errors.
- Conversely, `route="respond"` with `outcome.kind="candidate"` is NOT recognized as a non-edit route.

Also: `tests/test_live_agentic_harness_guard_contract.py:995` currently LOCKS IN the first fail-open case (accepts `graph_unchanged=false` + `outcome.kind=clarify`) — that test must be replaced with negative controls.

## What to change

1. **Make `_explicitly_non_edit_route` (or the guard path around it) use the canonical route**, not self-declared outcome/reason:
   - Read the actual `response.route` (find how route is carried in the assessor response envelope — check `implementation_result`, `response`/`turn`/`classification` fields; grep for `"route"` in assessor.py and the harness artifacts to find the authoritative field).
   - A non-edit route claiming `graph_unchanged=false` must fail a separate route/graph consistency check (edit-route self-relabeling cannot bypass all structured checks).
   - Accepted grounded refusals remain configuration-authorized (`allow_safe_refusal`) and structurally unchanged — those are legitimately exempt.
   - Known canonical non-edit routes (e.g. `respond`, `clarify`, `research`-only, `explain`-only) are exempt ONLY when the response actually took that route AND the graph is unchanged or the refusal is authorized. An edit-route envelope (`revise`/`apply`) with `graph_unchanged=false` and no positive landed count must fail closed even if it self-labels `outcome.kind=clarify` or `no_candidate_reason=route_not_applyable`.

2. **Replace the fail-open test at `test_live_agentic_harness_guard_contract.py:995`** with negative controls proving:
   - edit-route self-relabeling (`route=revise` + `outcome.kind=clarify` + `graph_unchanged=false`, no count) → FAILS;
   - `no_candidate_reason="route_not_applyable"` with `graph_unchanged=false`, no count → FAILS;
   - failure outcomes cannot bypass all structured checks;
   - and keep a positive control: a genuine non-edit route with unchanged graph still exempt.

3. **Preserve** the existing positive controls (missing/zero/negative/string/float/bool landed counts fail; grounded-refusal with `allow_safe_refusal` exempt; explicit non-edit routes exempt when truthful).

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -q tests/test_live_agentic_harness_guard_contract.py tests/test_live_agentic_assessor_score_honesty.py -x
```

Add your new negative controls to the guard-contract file so the slice covers them. Expected: all G0R fixtures pass including the new fail-closed negative controls.

## Report

Return: exact changes (files + line refs, especially how you read the canonical route), the fixture names added/replaced, and the pytest output. Do NOT commit.
