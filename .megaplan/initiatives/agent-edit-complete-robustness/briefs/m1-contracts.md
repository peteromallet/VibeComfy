# M1 — Versioned Operation, Projection, Identity, Undo, and Migration Contracts

## Outcome

Create the authoritative typed/versioned contract layer that every later
adapter, verifier, controller, recovery path, and cross-language fixture uses.

## Scope

Add the projection registry; bind operation families to forward and rollback
projections; make prepared authority explicit; ratify identity, Undo, legacy,
root-scope, and whole-workflow policies; add browser/Python golden fixtures.

## Locked decisions

- No unqualified canonical graph hash.
- Unknown projection/delta versions fail closed.
- Titles and positions are never identity fallback.
- Forward and rollback use the same semantic projection family.
- Root workflow scope is the only supported mutation scope in this epic.

## Open questions

- Is Undo transient, workflow-persistent, or journal-durable?
- Is `workflow_v1` supported or explicitly forbidden?
- How are legacy prepared transactions resumed, migrated, or retired?
- Which fields are semantic, layout-only, derived, defaulted, opaque, or
  unsupported?

## Constraints

Do not move LiteGraph access or orchestration yet. Preserve existing incident
behavior and version compatibility only through explicit adapters.

## Done criteria

- Browser and Python hashes match for every golden fixture.
- All transaction payloads require delta/projection versions and authority.
- Unsupported operations/scopes fail before prepare or mutation.
- Undo and legacy policies are encoded in tests and documentation.

## Touchpoints

`canonical_delta.js`, `graph_projection.js`,
`layout_verification_contract.js`, `agent_edit_transaction.js`,
`candidate_transaction.py`, `session.py`, schemas, fixtures, docs.

## Anti-scope

No native-adapter extraction, controller rewrite, subgraph support, or UI work.
