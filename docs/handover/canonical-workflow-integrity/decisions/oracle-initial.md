> Historical planning evidence, not executable product certification. Source line numbers refer to the audited baseline. Local receipt/manifest references in this note are provenance descriptions; the compact history and exact published source identity are in ../history.md and ../provenance.md.

# Astra initial architecture adjudication

Planning-only leaf judgment; no settled-plan verdict. Read `agent_goal.md`, `acceptance-ledger.md`, `custody.json`, `findings/explore-fidelity.md`, v1 plan/tasklist and relevant BASE source plus frozen diff. No product mutations or tests. These are incremental constraints, not a restatement of the frozen scope.

## OI1 — normalize the intended candidate, never waive staged identity/content binding

Disposition: require the plan to preserve unconditional staged semantic equality against the exact bundle being published. If an already-supported, narrowly justified transformation is accepted, perform it before constructing the expected bundle/sidecar/revision, or reconstruct those from its result. Return the bundle that describes the bytes actually published. Keep the normalization diagnostic associated with the source-to-result transition.

Evidence: BASE `workflow_bundle.py:1693-1724` and `:1886-1920` construct a bundle before emission; `:1795-1809` validates staged semantics and sidecar binding; `:1436-1449` derives revision identity from semantic/UI digests and parent. Simply allowing a mismatch leaves a successful result whose semantic digest/revision may describe missing content. A sidecar bound to the original graph can also fail against the transformed graph. Regression acceptance must compare returned bundle, reloaded Python, sidecar bind and revision inputs, including a case with a sidecar, not merely check that a destination file exists.

North Star: N1, N3, N5. This uses the existing bundle and atomic publisher rather than a second authority (N4, N6).

## OI2 — the known PreviewAny rule is evidence of a transformation, not a general preservation exemption

Disposition: reuse the existing disconnected UI-only rule as the bounded known counterexample; do not spend a fresh spike rediscovering it. Its class list does not license arbitrary semantic drift, nor establish that all disconnected authored content is disposable. Ordinary save must preserve authored content where existing representation permits it. Any accepted normalization must identify the exact affected UIDs/classes and attributable edges, and demonstrate no other semantic change. Keep save behavior separate from the existing explicitly lossy export option. Do not introduce another global loss toggle or general normalization framework.

Evidence: BASE `emit_prepare.py:84-108` filters UI-only nodes and preserves direct live passthroughs; the fidelity memo cites the existing positive passthrough test. That evidence is narrower than “unknown/custom nodes round-trip” and narrower than “all UI-only removal is harmless.” The bounded preservation spike may resolve whether the known disconnected fixture should be preserved or explicitly normalized; it must not reopen arbitrary digest acceptance.

North Star: N1, N2, N3, N6. Unknown/custom execution correctness can be deferred; raw authored class/UID/payload/edge preservation or an explicit degraded result cannot be silently deferred out of the save contract.

## OI3 — metadata classification must not silently equate unfamiliar with presentation

Disposition: keep schema/queue readiness separate from storage. The frozen dirty removal of the unknown-property check is not authority to ignore all extra properties. A bounded property-preservation fixture must verify whether existing IR raw metadata already owns them; reuse that owner. Position/size coercion is a presentation-boundary decision and must not weaken strict semantic binding or turn omission into claimed full fidelity.

Evidence: frozen `source-working.diff` workflow-bundle hunks delete `unknown_properties` rejection and label extra keys ignorable; the same diff permits malformed positions/sizes to be dropped. These are separate decisions from the dirty identity-only publication change and must receive separate dispositions.

North Star: N1, N2, N3, N4. This requires classification at existing boundaries, not a new schema gate (N6).

## OI4 — future source reconciliation must preserve both the snapshot and newer work

Disposition: future implementation starts in an isolated checkout only after a custody receipt names its actual implementation base. Before mutation, capture current source HEAD, staged and unstaged binary-capable diffs, status including untracked paths, and recoverable bytes for in-scope untracked work; hashes alone do not preserve bytes. Compare that receipt to this planning snapshot. Classify relevant dirty hunks as adopted, superseded by a named planned fix, or preserved out of scope. Carry accepted hunks into the isolated checkout; do not overwrite, reset, stash, commit or clean the original source as a shortcut. If changes arrived concurrently, re-inventory/reconcile rather than silently using the old snapshot. Stop only when a conflicting source choice changes scope or cannot be adjudicated within existing authorization.

This planning run needs no source mutation or new source commit. Its frozen diff remains evidence, not an implementation baseline. `source-working-manifest.json` covers tracked modified paths; `custody.json` lists additional untracked audit files, so neither alone certifies a complete recoverable source snapshot. The future custody checkpoint must precede implementation tasks, not sit at the end of the task graph.

North Star: N1, N5, N6. Protects newer human work without forcing unnecessary permission for routine isolated reconciliation.
