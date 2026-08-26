# FINAL REVIEW — classify focused-filter failures (READ-ONLY, no pytest)

You are Spark, read-only. Repo
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle` HEAD `d2975269`.
Do NOT run pytest (another agent owns the full suite). Do NOT edit source.

Done criterion: `pytest tests/ -k "schema or on_demand or obligation" -q` green.

Existing receipt already ran a close equivalent:
`.oracle/findings/batch-E-verify/batch-E-verify-tests.txt`
quotes:
```
tests/ -k "schema or on_demand or obligation" --ignore=test_live_agentic_watchdog -q
22 failed, 641 passed, 4 skipped, 7847 deselected, 29 warnings in 95.90s
```
and names some failures (2 quarantined `test_schemas_ensure` + ~20 others:
`test_authority_receipts`, `test_cli_affordances`, `test_comfy_nodes_agent_edit`,
`test_compact_widget_resolver` missing corpus, `test_ready_templates`, …).

The receipt does NOT list all 22 names. Reconstruct the set as completely as
you can from that file plus:

- `tests/quarantine/*.txt` (especially `node_resolution_surface.txt`,
  `ready_templates_surface.txt`, `agent_cli_surface.txt`,
  `schema_oracle_surface.txt`)
- `.oracle/receipts/batch-E-execution.log`
- `.oracle/receipts/batch-C-verify-tests.log` if it has the same filter
- `git diff --stat 96a9d810..d2975269 -- tests/` to see which test files
  this branch actually touched

## Classify

For every failure name you can identify:

| test | file | in quarantine list? | file touched by A–E? | introduced by this branch? | disposition |

Disposition vocabulary:
- QUARANTINED-BASELINE — listed in tests/quarantine, ignore for greenness
- UNTOUCHED-PREEXISTING — file not in A–E diff; not a contract regression
- CONTRACT-REGRESSION — in A–E files or traceback would implicate new glue
- UNKNOWN — you cannot name it from receipts

Also answer: does the literal `-k "schema or on_demand or obligation"` collect
unrelated tests (authority receipts, ready templates, compact widget) because
the keyword is too broad? If yes, the done-criterion "green" may mean the
*schema-capture* subset, not every substring match. Say so explicitly.

## Return (max 400 words)

- How many of the 22 you identified by name
- Table (compact)
- Whether the done criterion is literally unmet vs keyword-overbroad + quarantined
- Verdict: FOCUSED-GREEN | FOCUSED-GREEN-IF-SCOPED | FOCUSED-REGRESSION
