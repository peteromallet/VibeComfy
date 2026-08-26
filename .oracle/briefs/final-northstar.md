# FINAL REVIEW — North Star anti-pattern audit (READ-ONLY)

You are Spark, read-only. Repo
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle` HEAD `d2975269`.
Do NOT edit. Do NOT run pytest. Do NOT install packs.

North Star (cite every verdict against it):
`.oracle/northstar.md`

Anti-patterns to hunt in the A–E code (not in `.oracle/` prose):

1. Hand-authored / stub schemas presented as authoritative (R3 incident).
2. Permanent pack installs or venvs as a side effect of capture.
3. Preflight walls of unactionable failures (no exact ensure command).
4. Parallel schema systems where the existing ladder suffices.
5. Silent tier upgrades: static parse labeled runtime capture;
   `on_demand_static` satisfying `authoritative_object_info`;
   persist token `on_demand_runtime`; `source_kind` mismatch aliases.

## What to inspect (file:line, not vibes)

- `vibecomfy/schema/ensure_capture.py` persist tokens, tier order, mixed-pack
  hygiene, gap definition (stub/unattested = gap)
- `vibecomfy/schema/on_demand.py` stamp (must be `on_demand_import`, not
  `on_demand_runtime`); LRU sandbox path; no user-env install
- `vibecomfy/commands/schemas.py` ensure --manifest: clone via
  `_ensure_clone`, `allow_import=True`, no `allow_embedded`, fail-closed
  exit 1, no `clone_and_extract_packs`
- `tests/live_agentic_harness/scenario_obligations.py` allowlist
  `DECLARED_SCHEMA_SOURCES`, exact match of cache `source_kind` vs declaration,
  `resolution_tiers` separate from bool `resolution`, `runtime_only` /
  `VIBECOMFY_OBLIGATION_RUNTIME_ONLY`, stub reject
- `vibecomfy/commands/doctor.py` reporting only
- `tests/test_batch_e_e2e.py` fixture is real INPUT_TYPES source

Search:
```
rg -n "on_demand_runtime" vibecomfy tests --glob '!*.md'
rg -n "clone_and_extract_packs" vibecomfy/commands/schemas.py
rg -n "full_pack_refresh=True" vibecomfy/schema
rg -n "workflow_json_stub|@stub.json" vibecomfy/schema/ensure_capture.py tests/live_agentic_harness/scenario_obligations.py
rg -n "authoritative_object_info" tests/live_agentic_harness/scenario_obligations.py
```

Enduring qualities: ephemeral clone, honest provenance (tier + pack version +
commit + rung), fail closed, compose-don't-duplicate.

## Return (max 400 words)

Table: anti-pattern → AVOIDED / REPRODUCED → file:line evidence.
One-line each enduring quality: held / broken.
If any REPRODUCED: that is a merge blocker.
Verdict: NORTHSTAR-PASS or NORTHSTAR-FAIL.
