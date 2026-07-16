# Agent Edit Complete Robustness — North Star

Every Agent Edit operation is a versioned canonical delta executed by one
workflow-scoped controller through one native LiteGraph adapter, verified by
one operation-specific verifier, and completed by durable finalize or verified
rollback.

No other module may independently:

- decide graph or entity identity;
- define structural or layout projection semantics;
- inspect or mutate the live LiteGraph graph;
- compare transaction preconditions or postconditions;
- coordinate transaction lifecycle;
- own Agent Edit transport;
- commit an asynchronous result after its workflow authority has expired.

The existing transaction spine remains the durable aggregate. The known
`a66422e…`, `eb45e…`, detached `Displays / Labels`, and workflow-tab isolation
repairs are permanent acceptance gates, not temporary patches.

Complete robustness means all nine conditions in
`docs/plans/agent-edit-complete-robustness-architecture.md` are proven by
authoritative current-state evidence, including real ComfyUI success,
failure, refresh, switching, rollback, and persistence tests.

Root workflow scope is the supported boundary for this epic. Nested scopes and
subgraphs fail closed before mutation until a later native-adapter epic adds
them deliberately.
