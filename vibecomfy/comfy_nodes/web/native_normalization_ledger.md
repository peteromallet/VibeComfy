# Native Normalization Ledger — NON-AUTHORITATIVE DERIVED VIEW

This document is explanatory only. The sole machine authority is
`tests/fixtures/agent_edit/native_authority_ledger_v1.json`.

The machine ledger assigns every detected production native-access tuple to
exactly one stable `NGA-*` row. Each row records its source region, exact access
counts, purpose, semantic owner, target API, migration slice,
projection/identity effect, normalization category, concrete test or fixture
proof, and support status. The browser ownership contract validates that schema
and fails on unmatched source access, duplicate mappings, count drift, stale
rows, unknown enum values, placeholder metadata, and unknown keys.

The checked-in scanner deliberately uses only Node built-ins so fresh CI does
not depend on an incidental parser installation. It is conservative: it scans
all production `web/*.js`, tracks direct and computed graph acquisition,
destructuring, and chained local aliases to a fixed point, and inventories
native graph operations, group construction/configuration, dynamic
socket/widget rebuild, stable-identity and normalization helpers, plus relevant
canvas invalidation/draw access.

Open support statuses in the JSON authority identify the remaining migration
work:

- `migration_debt`: intentional S3/S4 access awaiting adapter ownership.
- `blocking_migration`: layout/group behavior that cannot be supported until
  the versioned layout operation contract is implemented.
- `supported_adapter_owner`, `permitted_canvas`, `permitted_harness`, and
  `projection_only`: reviewed access that is already in its declared owner.

The former hand-maintained numbered table and its 56-row summary were removed
because they duplicated and could drift from the machine authority.
