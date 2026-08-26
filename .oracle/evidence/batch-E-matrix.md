# Batch E Evidence Matrix

| command | source_kind | commit | rung | preflight verdict | strict verdict | stub verdict |
|---|---|---|---|---|---|---|
| `vibecomfy schemas ensure --manifest <comparison.json>` (fixture pack) | `on_demand_static` or `on_demand_import` (honest tier from `extract_pack_schemas` method) | `git rev-parse HEAD` of the ephemeral clone (`locked_commit`) — `a7f3c1d`-style sha7 in filename `fixture-pack@on_demand_*-{sha7}.json` | `ast` (static parse) or `import` (stubbed-subprocess `INPUT_TYPES`) — attested as `extraction_rung` in `provenance.json` | empty cache → fail with `vibecomfy schemas ensure --manifest <m>` in message; after ensure → green, `resolution_tiers[scenario][FixtureNode].source_kind == on_demand_*` | `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1` → fail even after on-demand capture (“runtime_only strict rejects on-demand”) | `@stub.json` / `workflow_json_stub` never passes (filtered in index provider + explicit `_is_stub_index_row` check) |

Test: `tests/test_batch_e_e2e.py::test_e2e_fixture_missing_ensure_preflight_green` (plus `test_doctor_prints_ensure_command` and `test_validate_coverage_manifest_gap_helper`).

Fixture is a local git repo with `custom_nodes/fixture-pack/nodes.py` (real `FixtureNode` with `INPUT_TYPES`), cloned via the LRU sandbox provider and extracted with the real ladder — not a hand-authored `@stub.json` presented as live.
