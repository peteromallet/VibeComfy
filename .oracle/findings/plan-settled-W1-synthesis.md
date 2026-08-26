# Settled-plan wave synthesis (W1) — 2026-08-26

Critics: plan-settled-1-simplicity (ox-alpha), plan-settled-2-reuse (ox-alpha). Same plan snapshot (plan.md @ 3d1e9486+).

| # | Finding | Disposition | Rationale |
|---|---|---|---|
| 1 | Defer Batch B (rung 3 embedded) — ship A/C/D/E with r3 fail-closed; land B only when a real class reaches it | **ACCEPT** | Plan's own effort section blesses this; removes the unproven XHARD slice from critical path; North Star tier honesty intact via r1/r2. B becomes conditional follow-on. |
| 2 | Drop `on_demand_runtime` alias; migrate single stamp (on_demand.py:193) to `on_demand_import` | **ACCEPT** | One constant, no permanent alias surface; fewer masquerade checks in D. |
| 3 | `--comfy-version`: flag-or-env, fail closed; drop core-cache sniffing | **ACCEPT** (both critics) | Hidden coupling; fail-closed message names the fix. |
| 4 | Preflight payload dual representation | **ACCEPT — resolve to parallel `resolution_tiers` map** | Critics split (dict vs map); oracle picks map: existing boolean comparisons untouched, zero caller risk, one mechanism. |
| 5 | Doctor becomes one-line pointer to `schemas validate-coverage --manifest` | **ACCEPT** | Matches goal's "or"; no second reporting surface. |
| 6 | Fix plan-vs-code line drift (normalize_entry extract.py:110; _provenance_row scenario_obligations.py:745) | **ACCEPT** | Cosmetic; prevents executor anchoring on stale lines. |
| 7 | Dedup "Effort and huge-run" section in plan.md | **ACCEPT** | Cosmetic. |

Reuse verification (critic 2): all compose-map symbols verified present at HEAD with matching semantics; no parallel mechanisms proposed.

Pre-settled critique slot: skipped — plan already settled (planned from complete exploration evidence).
