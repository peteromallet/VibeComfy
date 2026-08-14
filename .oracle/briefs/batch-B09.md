# MEGADO BATCH B09 — Reproducible final gate and report (Flash executor)

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites EXCEPT the deterministic gates listed below (those you MUST run).

## Context
All prior batches passed oracle review: G0R (scorer/narrator), B01 (typed evidence/provenance/redaction), D13 (manifest + rubrics + 3 corrected edits + 2 health controls), B04 (schema authority), B03 (semantic pin comparison), B05-lite (transactional rollback), B06 (universal UI evidence + tri-state judges), B07-lite (explicit transport; **OpenRouter canonical; pass `--transport openrouter`**), B08-cut (endpoint integrity). This batch: ONE canonical 100-scenario live lane + the durable comparison report. NO implementation changes — test-failure fixes route back through the oracle to the owning batch.

## Tasks (from .oracle/tasklist.md B09)

1. **Preflight required ignored data**:
   - `external_workflows/` — mandatory for the canonical run (provisioned: 2827 corpus JSONs, symlinked + gitignored; D13 verified 98 source hashes).
   - historical `out/agentic/` — mandatory ONLY for historical comparison + flaky-ID claims. It is ABSENT → record that: no historical comparison, no flaky-set derivation, no regression-vs-variance claims.
2. **Emit the authoritative manifest artifacts**: D13's `tests/live_agentic_harness/scenario_manifest.json` is the ONLY hash authority — extend/copy it with aggregate + `primary_source`; do NOT create a parallel manifest.
3. **Extend the B02 preservation summary or make B09 preflight the sole corpus-hash owner** — do not maintain two hash systems.
4. **Embed commit, selection, configuration, and corpus digests in `run_summary.json`.**
5. **Cite report evidence by stable scenario ID and SHA**, never checkout-relative artifact paths.
6. **Run deterministic gates**:
   - focused G0R/B01/D13/B04/B03/B05/B06/B07/B08 tests (the per-batch focused slices);
   - complete non-GPU suite (`make full-pytest` or the equivalent pytest run — use `-p no:rerunfailures` since the socket plugin cannot bind here);
   - B02/elegance preservation suite (`tests/test_b02_rich_preservation.py` — 4/4 expected, 0 corpus mismatches).
7. **Run ONE canonical 100-scenario lane** with:
   - exact commit; scenario/workflow manifest hashes; default production profile; **explicit `--transport openrouter`** (B07: harness no-flag default is now OpenRouter, but pass it explicitly); resolved per-stage models; concurrency (max-workers 6); timeout; exactly ONE typed-empty infrastructure retry.
   - Command shape: `.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-final --transport openrouter --profile default --max-workers 6 --infra-retries 1 --json`
8. **Report** (from persisted evidence ONLY):
   - suite first-attempt and eventual rates over 100;
   - semantic-product rates over 98 (excluding the 2 health controls);
   - infra-adjusted semantic rate (final passes / (100 − final typed persistent-empty failures)); OTHER infra classes (timeout, capacity) shown separately, never silently removed;
   - health-control results separately;
   - refusal pass/fail/undetermined + judge availability;
   - provenance + UI-artifact coverage;
   - matched (97) vs D13-revised (3) subsets separately — no aggregate improvement caused by D13 changes described as pure product gain;
   - remaining Class C/D ceiling (explicit).
9. **Flaky scenarios**: prior artifacts ABSENT → name NO flaky IDs, make NO regression-versus-variance claim.
10. **Correct documentation drift**: update the complete-picture status/table + G0 verdict; supersession banners on historical sections; mark canonical-graph elegance plan landed; remove stale "missing rich ingest" claims from the improvement doc; verify commit/work mapping before citing `192d4b8f`/`0f515870`.

## Sense-check precommit (adversary predictions — cover these FIRST)

From `.oracle/sensecheck-remaining-2026-08-13.md`:
1. **A second hash authority** — extend D13's `scenario_manifest.py:91` authority; do not regenerate a parallel manifest.
2. **Irreproducible arithmetic** — current summary only counts aggregate passes (`runner.py:324`); add a standalone reducer that reloads persisted evidence and reproduces first/eventual/infra-adjusted, 98-product, two-control, refusal tri-state, UI/provenance coverage, 97/3 matched/revised results. Unknown values labeled unknown, never inferred.
3. **Unsupported historical claims** — `out/agentic/` absent → item 9 inapplicable.

## Verification (run, retain output)
- `make full-pytest` (or the full non-GPU suite) exits 0 (with `-p no:rerunfailures`).
- The manifest preflight passes before model calls (100 scenarios, hashes match).
- The canonical lane completes exactly 100 manifest-selected scenarios; `run_summary.json` has `complete=true`.
- The report arithmetic reproduces from persisted artifacts (run the reducer twice; identical output).

## Acceptance (from tasklist)
- All deterministic suites pass.
- Corpus + manifest preflight passes before model calls.
- Canonical lane: exactly 100 manifest-selected scenarios.
- Report arithmetic reproduces from persisted artifacts.
- Product rates exclude health controls.
- Historical comparisons made only from portable hashed evidence (none available → none made).
- Flaky scenarios reported as inconclusive/variance, not pass/fail (none named).
- Documentation no longer describes landed work as in flight.
- Cumulative oracle verdict PASS.

## Report
Return: preflight results, deterministic gate results, lane run summary (complete=true, 100 scenarios, rates), the reducer + reproducibility proof, matched-vs-revised breakdown, doc-drift edits, pytest output. Do NOT commit.
