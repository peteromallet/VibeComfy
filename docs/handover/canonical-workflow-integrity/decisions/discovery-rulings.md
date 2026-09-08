> Historical planning evidence, not executable product certification. Source line numbers refer to the audited baseline. Local receipt/manifest references in this note are provenance descriptions; the compact history and exact published source identity are in ../history.md and ../provenance.md.

# Astra synthesis — settled discovery wave 1

**Decision: accept the bounded architecture, require one local correction before fresh contract review. No full discovery wave 2 is needed. This is not final plan acceptance or implementation certification.**

Verified all five SHA-256 entries in `evidence/settled-wave-1-manifest.json` against the files read. Reviewed the complete North Star, frozen goal, plan/tasklist, and both independent wave-1 critiques. BASE remains `6254cf5e88b4d16eafcc15d4b9f36253b3f8ad6b`. Only this run artifact was written; no product tests or mutations occurred.

The architecture already uses the existing semantic interpreter, bundle publisher, UI materialization boundary and durable Apply/Queue authorities. Corrections below settle ownership and proof; none changes the frozen authority or adds user scope. Apply them together, then perform the already-budgeted fresh contract review and one coherent correction/delta verification if needed.

## Finding dispositions

| Finding | Taxonomy | Disposition and required delta | Planning criteria | North Star alignment |
|---|---|---|---|---|
| Fidelity 1: repeated T0/T1 discovery | stale_or_repeated | **Accept, narrow.** T0 reuses named existing fixtures and writes one short decision note at `findings/preservation-decision.md` in the future run. It records the known PreviewAny decision, the representative opaque case and their evidence pointers. Keep the half-day ceiling; begin T1 directly when existing evidence answers the question. No fixture catalog/schema project. | P2,P3 | N1,N3 retain preservation evidence; N6 removes repeated discovery. |
| Fidelity 2: unnamed degraded draft result | contract_violation | **Accept.** Replace “degraded draft result/status” with preservation through existing IR/raw metadata or an existing explicit emission/refusal diagnostic before publication. Do not promise a new result type. Scope the positive opaque-node test to one representative class/UID/widgets/properties/edge case. | P2,P3 | N1,N2,N3 protect drafts and expose unsupported preservation; N6 avoids a new framework. |
| Fidelity 3 and Operations 2: CLI verification placeholder | required_evidence_gap | **Accept.** Name a concrete proposed module, e.g. `tests/test_port_export_canonical_integrity.py`, and its exact command. Its scenarios cover draft UI export, `--out`, `--persist-sidecar`, `--from`/breadcrumb, strict refusal, visible `--force-drop`, preview no-write and API projection. State temporary directories and no provider/server/model. | P3,P4,P6 | N2,N3,N5 prove the user-facing boundary; N6 bounds the suite. |
| Operations 2 reference to broad `tests -k` | stale_or_repeated | **Reject as stale evidence.** That selector is absent from the hash-verified settled tasklist; it appeared in v1. The current missing CLI command remains valid and is accepted above. | P1 | N3 requires accurate evidence; N6 avoids correcting an already-removed issue. |
| Fidelity 4: alternate normalization ownership | contract_violation | **Accept as ownership clarification.** Choose the pre-bundle approach. Keep normalization policy at the existing emitter preparation boundary (`porting/emit/emit_prepare.py`); the canonical bundle writer consumes that prepared workflow and exact drop evidence before constructing bundle, sidecar and revision. Do not implement a second normalizer/rebuild branch in the publisher. Stage bytes and retain unconditional equality against this exact intended bundle. Implementation may adapt the private preparation return plumbing as narrowly required. | P2,P3,P5 | N1,N3,N5 ensure the returned bundle describes published content; N4,N6 keep one rule owner. |
| Fidelity 5: edit restraint | optional_improvement | **Accept as no-change confirmation.** Keep focused equivalent semantic-delta/untouched-UID parity and existing durable fences. No identical report prose, second interpreter or Python CAS absent a demonstrated caller. | P2,P3 | N1,N4,N5 preserve behavior and authority; N6 avoids speculative API work. |
| Operations 1: T1/T2 shared bundle writes | implementation_defect | **Accept.** T2 bundle mutations wait for T1. Command-only inspection/test preparation may proceed concurrently, but do not schedule concurrent mutation of `workflow_bundle.py` or the same test file. Amend the opening “T1/T2 can proceed in parallel” sentence. | P3,P4 | N1,N3 protect the shared publication contract; N4,N6 avoid conflicting ownership. |
| Operations 3: durable classification artifact | required_evidence_gap | **Accept the durable-location need; reject mandatory schema/digest-table bureaucracy.** The short T0 note above names fixtures, exact observed change and preserve/normalize/refuse decision, with relevant assertions/digests linked only where needed to support that decision. No new artifact schema or all-fields inventory is required. | P1,P3 | N3 makes the decision reviewable; N6 prefers existing evidence and a bounded note. |
| Operations 4: dirty-source gate | required_evidence_gap | **Accept with corrected stop semantics.** Add a separate prerequisite C0 before T0–T4 product mutation. Name the exact receipt/comparison command or proposed helper path and command. Capture current HEAD, staged/unstaged binary-capable diffs and recoverable relevant untracked bytes; compare the frozen tracked manifest/diff without modifying it. Classify relevant changes as adopted, superseded by named fix, or preserved out of scope. Implement in isolation from an explicitly recorded base. Mismatch pauses mutation for reconciliation; it does not automatically demand user approval or discard concurrent work. Stop only on unresolved scope/authority conflict. | P1,P3,P4 | N1,N5 preserve newer work; N6 permits routine isolated reconciliation. |
| Operations 5: CLI environment | optional_improvement | **Accept into the CLI row.** State hermetic temporary-directory tests, no provider/server/models; no separate task or gate. | P4 | N2 separates save from readiness; N6 bounds cost. |
| Fresh delta: T4 “exact rg checks” and final affected matrix remain unnamed | required_evidence_gap | **Accept local completion.** Replace placeholders with concrete commands and exact proposed documentation paths; list the final affected-file pytest command once. The current `timeout` executable exists on this host (`/opt/homebrew/bin/timeout`), so no portability work is needed for this plan. | P3,P4 | N3 makes claimed verification inspectable; N6 avoids broad or repeated testing. |

## Bounded prototype and ticket dispositions

**Prototype — T0 only, future execution:** the representative opaque-node preservation question remains legitimately open. Use existing mechanisms and fixtures; choose preserved output or existing explicit refusal within the half-day ceiling. PreviewAny's current terminal/passthrough behavior is already evidenced and is not a new research question. Alignment: N1,N2,N3,N6. Criteria: P2,P3. No prototype is authorized during this planning run.

**Ticket/defer — no new implementation tasks:** a degraded-status/result framework, arbitrary custom-node semantic coverage, universal normalization or edit languages, new Python CAS without a caller, transport collapse and duplicate readiness/revision gates remain out of scope. Record these in the plan's deferrals; do not create a ticketing subsystem or launch more agents. Alignment: N4,N5,N6. Criteria: P2,P4.

## Minimum concrete validation delta

The corrected tasklist can use this exact proposed focused export command after adding the named module:

```text
timeout 300 python3 -m pytest -q tests/test_port_export_canonical_integrity.py
```

Name the planned test functions/scenarios within that row or its linked acceptance matrix so the command's coverage is reviewable. For T1 add assertions that the returned bundle, reloaded Python, sidecar binding and revision inputs describe the same normalized content, including a sidecar-present case. A successful file write alone is not acceptance. Include negative loss/rejection with destination bytes unchanged. These assertions extend existing bundle/emitter tests rather than require another framework.

C0 is a future implementation prerequisite distinct from final planning custody verification. The frozen manifest is tracked-file evidence, not a complete untracked-byte backup. The planning closeout still compares current source evidence and reports concurrent changes without overwriting them.

## P1–P6 discovery status

| Criterion | Discovery disposition |
|---|---|
| P1 | **Accept current evidence distinction**, with stale `-k` critique rejected. Final current-source comparison remains host closeout work. |
| P2 | **Accept architecture**, subject to local degraded-result/one-owner wording and bounded T0 correction. |
| P3 | **Correction required:** exact commands/paths, normalization owner, serialized shared writes and separate C0 prerequisite. |
| P4 | **Correction required:** operational custody command and final affected matrix; existing budgets remain sufficient. |
| P5 | **Discovery adjudicated; not complete.** Both independent critiques are dispositioned here. Fresh contract review must examine the corrected artifacts and exact manifest before final Astra freeze. |
| P6 | **Correction required:** exact export verification and a brief concrete before/after example of a one-field edit preserving unrelated authored content, plus the ordered C0→T0→T1→T2/T3→T4 sequence with genuine dependencies. No implementation-proof claim. |

No residual issue here requires a new architecture, expanded scope, second settled wave, product execution, or user permission. A fresh contract review may still identify a genuine contradiction; it must cite the corrected artifact and concrete consequence rather than reopen already-dispositioned preferences.
