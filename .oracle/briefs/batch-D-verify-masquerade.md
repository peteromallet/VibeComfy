# VERIFY — tier masquerade construction (read-only + tmp probes)

You are ox-alpha attacking Batch D preflight at HEAD `86e4a6ba` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not commit. You MAY run python in tmp caches and pytest.

This is the R3 trust boundary. Goal: actually CONSTRUCT a masquerade, do not
just read the happy-path tests. If you cannot construct one, say BLOCKED with
the exact gate that stopped you (file:line).

Read:
- `git diff 5f3e635f..86e4a6ba -- tests/live_agentic_harness/scenario_obligations.py tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py`
- `.oracle/plan.md` Batch D + Checkpoint D
- Executor receipt `.oracle/receipts/batch-D-execution.log` (concatenated Grok thinking — include the kernel follow-up about stub test matching GapNode vs Stubbed)

## Attack vectors — attempt each

Use a tmp cache + call `preflight_scenario_obligations` (or the resolver it uses)
with a synthetic obligation declaration. Cite file:line of the gate.

A. On-demand pack JSON `source_kind=on_demand_static` + declaration `authoritative_object_info` → must FAIL (no masquerade).
B. On-demand pack JSON `source_kind=on_demand_import` + declaration `on_demand_static` → must FAIL (no silent upgrade across on-demand rungs).
C. Filename `@on_demand_*.json` whose JSON `source_kind` LIES as `runtime_object_info` / `runtime_capture` + declaration `authoritative_object_info` → must FAIL (filename cannot bless a lie).
D. `@stub.json` indexed+attested, or `source_kind=workflow_json_stub`, + any live declaration → must FAIL.
E. `NodeSchema.source_provider` overwritten to `object_info_index` while pack JSON says `on_demand_static` + declaration `on_demand_static` → must PASS using pack JSON, not provider overwrite.
F. Ledger provenance `source_kind` disagrees with pack JSON → must FAIL.
G. Missing pin (no `repo` and no `locked_commit`) on an otherwise matching on-demand file → must FAIL.
H. `on_demand_runtime` as declaration source → must be REJECTED (invalid; stamp migrated in A).
I. `runtime_only=True` or `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1` with honest `on_demand_static` declaration + matching file → must FAIL and name the strict flag; must NOT claim `schemas ensure` is enough.
J. Preflight must not import/call `OnDemandInstallSchemaProvider.get_schema` (no clone). Grep the D delta.

For A, C, D, H: actually construct the tmp objects and print ok/error. Do not skip because a unit test exists — the test may be matching the wrong class (executor already found one such bug: GapNode vs Stubbed / path containing "stub").

## Return (max 400 words)

For each A–J: BLOCKED or OPEN + file:line + one-line probe result.
Any OPEN masquerade that would stamp or accept a higher tier is a blocking finding.
North Star disposition: ALIGNED / NOT ALIGNED on: tier masquerade, silent upgrade, stub-as-truth, ceremonial validation.
