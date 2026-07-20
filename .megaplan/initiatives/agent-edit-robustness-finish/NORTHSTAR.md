# North Star: One Transaction, One Owner at Every Boundary

Every Agent Edit operation is a versioned canonical delta coordinated by one
workflow-scoped controller, executed through one native LiteGraph adapter,
judged by one operation-specific verifier, and completed by durable finalize or
verified rollback.

The finished architecture has exactly one owner for each consequential
decision:

- the projection registry owns structural, layout, and workflow projection
  meaning;
- the native adapter alone observes and mutates LiteGraph;
- the verifier alone compares transaction preconditions, landed operations,
  postconditions, and rollback outcomes;
- the workflow controller alone coordinates lifecycle and asynchronous commit
  authority;
- the API module alone owns Agent Edit transport;
- the lifecycle reducer alone owns legal state transitions; and
- stable identifiers, never titles, positions, or incidental order, identify
  workflows, scopes, nodes, groups, sessions, turns, candidates, and
  transactions.

There is no production `candidateGraph` or whole-graph path to native forward
mutation. Whole-graph loading may exist only as an explicitly authorized,
receipt-bound compensation strategy. Compatibility code survives only when it
implements a declared, versioned migration contract; otherwise it is deleted.

Every workflow tab has an isolated complete context. An async continuation can
commit only while its workflow, activation, operation, submit/apply epoch,
session, turn, candidate, transaction, lease, generation, and panel authority
remain current. Switching tabs or refreshing never transfers authority.

Every durable post-prepare state has an idempotent recovery action. A generic
terminal error without retry, reconciliation, verified rollback, or exact
retained recovery evidence is forbidden.

The exact `a66422e…`, `eb45e…`, detached `Displays / Labels`, duplicate-title,
and workflow-tab isolation incidents remain permanent gates. Real ComfyUI must
prove forward success, native serialization, verification, finalize, refresh,
persistence, injected failure, rollback, recovery, and switching for every
supported transaction family.

“Completely cleaned up” means the old owners, dead exports, copied helpers,
fallback mutation paths, title-identity heuristics, stale ledger exceptions,
and obsolete compatibility facades are removed; `vibecomfy_roundtrip.js` is
only bootstrap/event/view composition; all S3/S4 rows are closed; static CI
guards make regression architecturally illegal; and the final proof map and
completion manifest directly prove every requirement.

Root workflow scope is the boundary of this epic. Nested scopes and subgraphs
must fail closed before mutation and are deliberately deferred.
