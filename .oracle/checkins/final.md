# ORACLE FINAL OVERALL REVIEW — schema-capture 4-item contract

**Verdict: PASS**
**HEAD reviewed:** `d2975269aa447b470e49165e9245ad62c8a0c4f0` (`oracle-run`, base `96a9d810`)
**Stop classification:** none (not blocked / failed / undetermined / retryable / escalate)

Delegated Spark (`openrouter/meta/muse-spark-1.2-contributor`) owned the one-shot full suite, e2e evidence audit, KISS, North Star, focused-filter classify, and live registry probe. Oracle validated citations against the worktree.

---

## Agent-goal criteria → evidence

| # | Criterion | Evidence | Result | Disposition |
|---|---|---|---|---|
| 1 | `vibecomfy schemas ensure --manifest` — registry → ephemeral clone → r1/r2 ladder → persist honest tier | `vibecomfy/commands/schemas.py` (`allow_import=True` ~692, `_ensure_clone`/`_enforce_cap` ~622/718, no `allow_embedded`); `vibecomfy/schema/ensure_capture.py` `persist_on_demand_pack`; Batch C `5f3e635f` + checkin `.oracle/checkins/batch-C.md` | r3 fail-closed (B deferred); `rg clone_and_extract_packs vibecomfy/commands/schemas.py` empty | **PASS** |
| 1a | Persist glue + honest identity | `ensure_capture.py:27-31` `SOURCE_KIND_BY_RUNG`; `full_pack_refresh=False`; two-layer hygiene 271–298; provenance `repo/locked_commit/extraction_rung/registry_pack_version/source_kind`; `on_demand.py:193` stamps `on_demand_import` not `on_demand_runtime`. Batch A `b430bbcb` | `pytest tests/test_ensure_capture.py` 9 passed (A checkin + E-verify) | **PASS** |
| 2 | Preflight accepts `on_demand_*` as themselves; stub rejected; strict runtime-only | `scenario_obligations.py:45-48` allowlist; `:863-869` exact `source_kind` match; `:880-888` `VIBECOMFY_OBLIGATION_RUNTIME_ONLY`; `@on_demand_` ne**PASS** at `d2975269aa447b470e49165e9245ad62c8a0c4f0` (`oracle-run`, base `96a9d810`).

No stop classification (`blocked` / `failed` / `undetermined` / `retryable` / `escalate`). Registry is reachable; Batch B remains deferred.

Spark (`openrouter/meta/muse-spark-1.2-contributor`) owned the one-shot full suite, the fixture e2e audit, KISS, North Star, focused-filter classification, and the live registry probe. Citations were checked against the worktree.

## Agent-goal mapping

| Criterion | Evidence | Result | Disposition |
|---|---|---|---|
| **1. `schemas ensure --manifest`** — registry → ephemeral clone → r1/r2 → persist honest tier | `vibecomfy/commands/schemas.py` (`allow_import=True`, `_ensure_clone` + `_enforce_cap`, no `allow_embedded`); `vibecomfy/schema/ensure_capture.py`; Batch C `5f3e635f` | r3 fail-closed (B deferred); `clone_and_extract_packs` not used from `commands/schemas.py` | **PASS** |
| **1a. Persist glue + honest identity** | `SOURCE_KIND_BY_RUNG` (`ast`→`on_demand_static`, `import`→`on_demand_import`); `full_pack_refresh=False`; two-layer hygiene; provenance `repo` / `locked_commit` / `extraction_rung` / `registry_pack_version`. Stamp at `on_demand.py:193` is `on_demand_import`. Batch A `b430bbcb` | `tests/test_ensure_capture.py` 9 passed | **PASS** |
| **2. Preflight bridge + strict flag** | `DECLARED_SCHEMA_SOURCES` allowlist; exact `source_kind` match; `@on_demand_` cannot satisfy `authoritative_object_info`; `VIBECOMFY_OBLIGATION_RUNTIME_ONLY`. Batch D `86e4a6ba` | preflight + p4 caches 53 passed; with ensure_capture + e2e: 66 passed | **PASS** |
| **3. Doctor / `validate-coverage --manifest`** | `format_schema_gap` shared helper; manifest gaps exit 1 with `ensure_command`; doctor reports only (no clone/extract). Batch E `d2975269` | `test_doctor_prints_ensure_command`, `test_validate_coverage_manifest_gap_helper` | **PASS** |
| **4. Fixture e2e + SKILL** | `tests/test_batch_e_e2e.py` (real `FixtureNode.INPUT_TYPES` git pack, not `@stub.json`); `.oracle/evidence/batch-E-matrix.md`; `docs/agent-skill/SKILL.md` section **Schema Capture and Preflight (Batch E)** | Spark e2e audit **E2E-PASS**; `4 passed` in Batch E receipts | **PASS** |
| Focused `pytest tests/ -k "schema or on_demand or obligation" -q` | Batch E verify receipt: `22 failed, 641 passed, 4 skipped, 7847 deselected` | Keyword is overbroad (authority receipts, ready-templates, widget resolver). Contract files green except 2 quarantined `test_schemas_ensure` (`tests/quarantine/node_resolution_surface.txt`) | **PASS scoped** |
| One-owner full suite | Spark ran `PYTHONHASHSEED=0 python3 -m pytest -n 8 -q -p no:cacheprovider --ignore=tests/test_live_agentic_watchdog.py --tb=line` (no `.venv`; watchdog needs `arnold`). Receipt: `.oracle/receipts/final-full-suite.log` | **`435 failed, 7899 passed, 143 skipped, 1 xfailed, 1 error in 456.73s`**. A–E: **0 new failures** (only the 2 quarantined `test_schemas_ensure`). `test_ensure_capture` / `test_batch_e_e2e` / `test_scenario_obligation_preflight` / `test_p4_objectinfo_caches` all green | **PASS as run-once**; tree-wide is not green (fixer-box baseline, missing corpus, IR-threaded tests). No schema-capture regression |
| Live / expensive once | Spark: `https://api.comfy.org/nodes?limit=1` HTTP 200; `resolve_pack("comfyui-indextts2")` OK; IndexTTS/LayerMask class names are ambiguous (registry live). No clone; committed cache clean | **LIVE-REACHABLE** — goal stop `blocked` not triggered | **PASS** |

Batch check-ins already on disk: A `b430bbcb` PASS · C `5f3e635f` PASS · D `86e4a6ba` PASS · E `d2975269` PASS.

## North Star

Ephemeral clone, honest provenance, fail-closed command, and compose-don't-duplicate all **hold**. KISS-PASS. No parallel schema system.

Anti-patterns **avoided**: stub-as-truth, permanent installs, unactionable preflight wall, silent tier upgrade. Production has no `on_demand_runtime` persist token.

**Residual, not blocking:** unstamped non-`@on_demand_` files can still satisfy `authoritative_object_info` via the FINAL5 `@local.json` legacy-ingest clause. On-demand filenames are excluded; this is not a static→runtime masquerade.

**Intentional fail-closed:** `test_live_agentic_split_finale.py` failed full-suite preflight on undeclared gated classes in `image-generates-a-2x2-seed-variation`. Plan OQ2: FINAL50 stays red; fixture e2e only; no campaign `SCHEMA_EVIDENCE_REQUIREMENTS` rows in this run.

## Sync authorization

- **Authorized:** `git push -u origin oracle-run` (no force-push). Local `origin/oracle-run` does not exist yet.
- **Not authorized as a fast-forward:** `origin/main` is `054bce5b` (PR #155 `integrate/ir-threaded`). `git merge-base --is-ancestor origin/main HEAD` is **NO** (merge-base `a0d441f3`). This branch is based on box HEAD `origin/fixer/workflow-execution-spine-consolidation` (`96a9d810`). Fast-forwarding `main` to `d2975269` is not a fast-forward and is forbidden.

Landing on `main` needs a **merge** (or rebase onto current `main`) as a separate operator step.

Durable write-up: `.oracle/checkins/final.md`. Spark receipts: `.oracle/findings/final-review/`.
one owner) | `.oracle/receipts/final-full-suite.log` + `.oracle/findings/final-review/final-suite.txt` | 7899 passed / 435 failed / 1 error; 0 A–E NEW |
| E2E fixture audit | `.oracle/findings/final-review/final-e2e.txt` | E2E-PASS |
| KISS/YAGNI | `.oracle/findings/final-review/final-kiss.txt` | KISS-PASS |
| North Star | `.oracle/findings/final-review/final-northstar.txt` | NORTHSTAR-PASS |
| Focused classify | `.oracle/findings/final-review/final-focused-classify.txt` | FOCUSED-GREEN-IF-SCOPED |
| Live registry | `.oracle/findings/final-review/final-live.txt` | LIVE-REACHABLE |

Suite side-effect (`custom_nodes.lock` test pin `pinnedsha` + 3 layout.json) restored after the sweep; committed cache never dirty.
