# M1 versioned Agent Edit contracts

New Agent Edit authority uses `candidate_transaction_v2` with a mandatory,
immutable `prepared_authority_v1`.  The authority contains an explicit
`delta_v1` declaration bound to wire schema `2.0.0`, root scope, stable UUID
workflow identity, issued session/turn/candidate/transaction IDs, plan hash,
positive generation, lease nonce, typed pre/post projection references, an
equal rollback projection family, a versioned restoration strategy, and an
authority-receipt digest.

`projection_registry_v1` is the semantic owner.  It registers `structural_v1`
and `layout_v1`; `workflow_v1` is recognized only to reject it for forward
Agent Edit. Layout authority also carries a structural no-op witness. A
projection digest is always represented as
`{kind:"projection_ref_v1", projection, digest}`, never a bare graph hash.

Only `{kind:"root",path:""}` (`root_scope_v1`) may mutate. Definitions,
nested scope paths, cross-scope links, native IDs, titles, positions, paths,
and indexes have no authority fallback. `field_registry_v1` classifies exact
fields; unknown fields are unsupported and `vibecomfy.exec` dynamic `io` is
derived-native.

Undo is `journal_durable_v1`: a finalized journal owns inverse/restore
authority, baseline CAS, and identity fencing. Browser `undoStack` is a
non-authoritative cache. The compensating workflow transaction is M5 work.

Historic `candidate_transaction_v1` terminal records are audit-only. Nonterminal
v1 records classify as `legacy_prepared_nonresumable` with rebaseline/cancel;
rollback is offered only when an exact stored restoration strategy names its
original contract. Other old shapes are `legacy_non_resumable`.
