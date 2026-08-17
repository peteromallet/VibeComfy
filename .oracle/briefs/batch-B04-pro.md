# B04 — Atomic edit, precedent projection, claim refs (XHARD, DeepSeek Pro)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing batch B04 (all XHARD). B01 landed (`f5a45561`, mode plumbing + toggle
+ `two_step.py` seam). B02/B03 are in flight: policy types + tool gating, budgets +
output-cap plumbing, session authority + prompt + continuation loop. Coordinate: the B03
agent owns `two_step_session.py` and `build_two_step_execute_messages()`; you own the
EDIT/atomic/precedent/claim-ref machinery. If a shared file (e.g. `two_step.py`,
`contracts.py`) is mid-edit by another agent, extend it without clobbering their scope.

## Tasks

1. Execute state machine in `vibecomfy/executor/two_step.py`:
   - Research/tool continuations may precede editing.
   - Exactly ONE complete Python batch may be accepted.
   - One complete replacement is allowed ONLY after rejection.
   - After acceptance, further edit submissions are denied.
   - A second rejection returns no candidate.
   - Parse, resolution, CAS, channel, bounds, or done-gate failure returns zero Δ.

2. REUSE `EditSession.apply_batch()` as the parse/interpret/gate/commit authority
   (`vibecomfy/porting/edit/_parse_execute.py:22`). It already parses, calls `interpret()`,
   runs `verify_apply()`, and commits only after validation. Do NOT independently call
   parse/interpret/verify_apply again.

3. CAS definition: request baseline + current session revision ONLY (no model-supplied
   per-op old-values — do NOT extend grammar/op schemas). Typed stale-baseline diagnostics
   go to the one replacement continuation.

4. `render_fact_pack()` in `vibecomfy/porting/render.py`:
   - Stable fact IDs from canonical lens items (text = canonical rendered lines;
     topology = canonical tuples).
   - IDs reference facts; do NOT create another graph representation.
   - Preserve the Law 4 lens ceiling.
   - KEEP THIS SEPARATE from the canonical topology renderer so Law 4's complete-topology
     contract is not weakened.

5. Precedent projection:
   - `HivemindRecordView` (`vibecomfy/executor/contracts.py:2358`) + `serve_hivemind_record()`
     (`vibecomfy/executor/hivemind_tools.py:345`, currently surface-only) expose immutable
     surface+topology, NEVER raw workflow JSON.
   - Oversize bounds: 64 KiB rendered output / 128 nodes / 256 edges; rank exact
     query/class matches → 1-hop neighbors → 2-hop neighbors; stable ties
     `(class_type, uid)`; induced edges only; trim to byte ceiling; ALWAYS include
     `omitted_node_count`, `omitted_edge_count`, `global_topology_complete=false`.
   - Apply the same sanitization to workflow-valued ready-template observations
     (`vibecomfy/executor/lookup_tools.py:610` + projection in
     `vibecomfy/executor/tool_specs.py:359`).

6. Typed final contracts in `vibecomfy/executor/contracts.py`:
   `TwoStepClaimRefs`, `TwoStepSelfAssessment`, `TwoStepFinal`, `TwoStepExecutionReport`.

7. `validate_two_step_final()`:
   - delta_ids ⊆ accumulated accepted Δ ledger.
   - lens_fact_ids ⊆ current reply-lens facts.
   - evidence_ids ⊆ accumulated tool ledger.
   - Edit-success outcome requires nonempty accepted Δ.
   - Turn-1 Δ references valid in later turns only when present in that session.
   - Forged or cross-session references fail closed.

8. Map accepted work into the existing `ImplementationResult`, durable candidate, and
   `ExecutorResult` envelope. Delta IDs are metadata pointing to canonical accepted-batch
   operations, not a new delta body.

9. Tests:
   - `tests/test_executor_two_step_contracts.py`
   - `tests/test_executor_two_step_atomic.py`
   - `tests/test_executor_two_step_precedents.py`
   - Fact-ID cases to `tests/test_ir_laws.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_contracts.py \
  tests/test_executor_two_step_atomic.py \
  tests/test_executor_two_step_precedents.py \
  tests/test_porting_edit_session.py \
  tests/test_porting_edit_session_harness.py \
  tests/test_porting_edit_delta_contract.py \
  tests/test_ir_laws.py
```

Required fault injections: stale baseline; unknown schema; socket/literal mismatch;
invalid mixed batch; done-gate failure; first rejection then valid replacement; two
rejected submissions; research timeout + empty result; forged evidence ID; forged lens
fact ID; cross-session delta ID; claimed edit with zero accepted Δ.

## Constraints
- Commit ONLY this batch's scope: `git add -A && git commit -m "B04: atomic edit + precedent projection + claim refs"`.
- Do not start B05 work.
- Report: files changed, gate output, deviations.
