# Cleanup execution log

## ORACLE-1 (T-001..T-006) — PASS
- T-001 baseline receipt: PASS (make check 0, full pytest 0, 347/20/5.8% truth, quarantine 14).
- T-002 ownership ledger: PASS. T-003 batch/provider ledger: PASS. T-004 edit manifest (472): PASS. T-005 session manifest (23/31/23): PASS. T-006 generated/lazy policy: PASS.
- Round 2 fixes: manifest marks load_agent_generated_scratchpad required_post_split; ownership wording = duck-typed seam (no signature-identical claim).
- Oracle: PASS.

## ORACLE-2 (T-007..T-013) — PASS
- T-007 testing shim delete: PASS (441 tests green). T-008 schema forks delete: PASS (7 schema failures verified pre-existing baseline). T-009 YAML shim delete: PASS. T-010 route wrappers: PASS (86 route tests green). T-011/T-012 docs: PASS (+round fixes for 4 extra stale refs caught by oracle). T-013 duplicate helper: PASS (32 delta tests green).
- Boundary gate: make check first run exit 2 at browser-smoke — ONE timing flake (roundtrip diagnostics waitFor), passes isolated + standalone browser-smoke exit 0; second run in progress. Lockfile pin restored after gate churn.
- Oracle rounds: 1 FAIL (manifest/ownership accuracy) → fixes; 2 FAIL (wire-protocol edit_session.py) → fix; 3 FAIL (false-positive test filenames) → clarified; 4 PASS.
