# VERIFY — mixed-pack / mixed-declaration preflight (read-only + tmp probe)

You are ox-alpha probing Batch D at HEAD `86e4a6ba` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not commit. Tmp-cache python probes are allowed.

Executor deviation (must judge, not rubber-stamp): cache files do NOT stamp
`authoritative_object_info`. FINAL5 pins are `@local.json` with **no**
`source_kind`. They pass via a legacy-ingest clause of a runtime-family
recognizer. That is required for IndexTTS/LayerMask but is a masquerade-adjacent
hole if it also blesses on-demand files or unstamped random JSON.

## Mixed-pack contract to probe

One tmp cache, one pack identity, TWO classes:

- Class R: runtime capture (filename `@local.json` or `@runpod-snapshot` /
  `runtime_core`; optional missing `source_kind` like FINAL5).
- Class G: on-demand capture (`source_kind=on_demand_static`, filename contains
  `@on_demand_`).

Declarations:
1. R declared `authoritative_object_info`, G declared `on_demand_static` → both ok; `resolution_tiers` records actual cache stamps (R runtime-family / legacy, G `on_demand_static`). Boolean `resolution` payload still bools.
2. BOTH declared `authoritative_object_info` → R ok, G FAIL (G must not ride R's pack).
3. BOTH declared `on_demand_static` → G ok, R FAIL unless R's cache stamp is exactly `on_demand_static` (runtime must not satisfy on-demand declaration either — exact match, no downgrade-as-alias).
4. Unstamped `@local.json` for a NEW class that is NOT IndexTTS/LayerMask, declared `authoritative_object_info` → report whether the legacy clause is pack-name-scoped or filename-scoped. Filename-scoped = OPEN hole. Quote file:line.

Also:
- Confirm preflight reads pack-JSON `source_kind`, not `NodeSchema.source_provider`.
- Confirm `resolution` booleans unchanged; tiers live in `resolution_tiers`.
- Confirm campaign `SCHEMA_EVIDENCE_REQUIREMENTS` and assessment rubrics were NOT edited in `git diff 5f3e635f..86e4a6ba -- . ':!.oracle'`.
- Confirm no network / no clone in preflight path.

Construct the tmp mixed pack if cheap (copy patterns from
`tests/test_scenario_obligation_preflight.py`). Print ok/fail per class.

## Return (max 400 words)

- Mixed-pack: SAFE / UNSAFE with per-case results (1–4).
- Legacy-ingest scope: pack-name-scoped / filename-scoped / other — blocking?
- Boolean payload intact: yes/no.
- Campaign rows untouched: yes/no.
- Findings (empty if none).
