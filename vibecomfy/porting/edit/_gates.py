from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit.ops import EditOp
from vibecomfy.porting.edit._ir_utils import (
    _api_one_hop_neighbors,
    _changed_edge_endpoint_node_ids,
    _compile_ready_workflow_copy,
    _done_gate_b_uids_for_ops,
    _node_id_sort_key,
    _subset_api_by_node_ids,
    _workflow_uid_to_node_id,
)
from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    DoneResult,
    _diag,
)

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


class _GatesMixin:
    def done(self) -> DoneResult:
        """Finalize the session: run Gate A and Gate B proof checks.

        Gate A replays ``interpret`` over the retained ``(wf_i, Δ_i)``
        history from ``wf_0`` and emits that replayed IR.  The emit-side
        snapshot (not a Law-5 graph surface) must equal that candidate.
        The independent emit-exit guard (``guard_exit_ui``) then runs as
        a hard gate: a candidate that does not round-trip against the
        original ingest is not done.

        Gate B compiles the retained IR and the replayed IR through
        ``compile(\"api\")``, narrows both API graphs to the touched region,
        and compares them with ``parity.compile_equivalent``.
        """
        ops = tuple(self.landed_ops)

        if not ops:
            if self.workflow is None or self._wf0 is None:
                return DoneResult(
                    ok=False,
                    summary="Gate A failed: retained IR is missing.",
                    diagnostics=(
                        _diag(
                            "done_gate_a_missing_ir",
                            "Zero-ops done() requires the retained ingest IR.",
                            severity="error",
                        ),
                    ),
                )
            try:
                original_ui = self._emit_working_snapshot(self._wf0, ops=())
                current_ui = self._emit_working_snapshot(self.workflow, ops=())
            except Exception as exc:
                return DoneResult(
                    ok=False,
                    summary=f"Gate A failed: emit of the retained IR failed: {exc}",
                    diagnostics=(
                        _diag(
                            "done_gate_a_emit_failed",
                            f"Gate A emit of the retained IR failed: {exc}",
                            severity="error",
                        ),
                    ),
                )
            if current_ui != original_ui:
                return DoneResult(
                    ok=False,
                    summary=(
                        "Gate A failed: emit(current IR) differs from emit(wf_0) "
                        "even though zero ops were landed."
                    ),
                    diagnostics=(
                        _diag(
                            "done_gate_a_mismatch",
                            (
                                "Zero ops landed but emit(current) != emit(wf_0). "
                                "The retained IR drifted outside the edit-op path."
                            ),
                            severity="error",
                        ),
                    ),
                )
            gate_b = self._done_gate_b_from_ir(ops)
            if not gate_b.ok:
                return gate_b
            gate_c_summary = self._done_gate_c(ops)
            return DoneResult(
                ok=True,
                summary=(
                    "No edits applied — identity verified; Gate B passed. "
                    f"Summary: {gate_c_summary}"
                ),
            )

        replayed, ir_diags = self._replay_interpret_for_done()
        if replayed is None:
            return DoneResult(
                ok=False,
                summary=(
                    f"Gate A: interpret replay over (wf_0, Δ_i) failed "
                    f"({len(ir_diags)} diagnostic(s))."
                ),
                diagnostics=ir_diags,
            )

        try:
            candidate_ui = self._emit_working_snapshot(replayed)
        except Exception as exc:
            return DoneResult(
                ok=False,
                summary=f"Gate A failed: emit of the replayed IR failed: {exc}",
                diagnostics=(
                    _diag(
                        "done_gate_a_emit_failed",
                        f"Gate A emit of the replayed IR failed: {exc}",
                        severity="error",
                    ),
                ),
            )

        try:
            current_ui = self._emit_working_snapshot(self.workflow, ops=ops)
        except Exception as exc:
            return DoneResult(
                ok=False,
                summary=f"Gate A failed: emit of the current IR failed: {exc}",
                diagnostics=(
                    _diag(
                        "done_gate_a_emit_failed",
                        f"Gate A emit of the current IR failed: {exc}",
                        severity="error",
                    ),
                ),
            )
        if candidate_ui != current_ui:
            return DoneResult(
                ok=False,
                summary=(
                    "Gate A failed: replayed emit candidate does not match "
                    "emit(current IR)."
                ),
                diagnostics=(
                    _diag(
                        "done_gate_a_mismatch",
                        (
                            "Replaying interpret over (wf_0, Δ_i) and emitting "
                            "the candidate does not match emit(current IR). "
                            "The retained IR drifted outside the edit-op path "
                            "or emit is not a pure function of the IR."
                        ),
                        severity="error",
                    ),
                ),
            )

        from vibecomfy.porting.emit.ui import guard_exit_ui

        try:
            baseline_ui = self._emit_working_snapshot(self._wf0, ops=())
        except Exception as exc:
            return DoneResult(
                ok=False,
                summary=f"Gate A failed: emit of wf_0 failed: {exc}",
                diagnostics=(
                    _diag(
                        "done_gate_a_emit_failed",
                        f"Gate A emit of wf_0 failed: {exc}",
                        severity="error",
                    ),
                ),
            )
        exit_guard = guard_exit_ui(baseline_ui, candidate_ui, ops)
        if not exit_guard.ok:
            guard_diags = tuple(
                _diag(
                    issue.code,
                    issue.message,
                    severity=getattr(issue, "severity", "error") or "error",
                    detail=getattr(issue, "detail", None),
                )
                for issue in exit_guard.diagnostics
            ) or (
                _diag(
                    "done_gate_a_exit_guard",
                    "The emit-exit guard rejected the candidate.",
                    severity="error",
                ),
            )
            return DoneResult(
                ok=False,
                summary=(
                    "Gate A failed: emit-exit guard rejected the candidate "
                    f"({len(guard_diags)} diagnostic(s))."
                ),
                diagnostics=guard_diags,
            )

        gate_b = self._done_gate_b_from_ir(ops, replayed=replayed)
        if not gate_b.ok:
            return gate_b

        gate_c_summary = self._done_gate_c(ops)
        return DoneResult(
            ok=True,
            summary=(
                f"Gate A passed: {len(ops)} edit operation(s) verified. "
                f"Gate B passed: touched compile region is isomorphic. "
                f"Summary: {gate_c_summary}"
            ),
        )

    def _replay_interpret_for_done(self) -> tuple[Any | None, tuple[CompactDiagnostic, ...]]:
        from vibecomfy.porting.edit._interpret import interpret
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        workflow = getattr(self, "_wf0", None)
        if workflow is None:
            return None, (
                _diag(
                    "done_gate_a_missing_wf0",
                    "Gate A could not replay interpret: ingest IR is missing.",
                    severity="error",
                ),
            )
        workflow = _cow_workflow_copy(workflow)
        for entry in getattr(self, "history", []) or ():
            _pre, delta, _recorded_ops = entry
            result = interpret(
                workflow,
                delta,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
            )
            if not result.ok:
                return None, result.diagnostics
            workflow = result.workflow
        return workflow, ()

    def _done_gate_b_from_ir(
        self,
        ops: tuple[EditOp, ...],
        *,
        replayed: Any | None = None,
    ) -> DoneResult:
        original = getattr(self, "_wf0", None) or getattr(self, "workflow", None)
        working = getattr(self, "workflow", None)
        candidate = replayed if replayed is not None else working
        if original is None or working is None or candidate is None:
            return DoneResult(
                ok=False,
                summary=(
                    "Gate B failed: the retained IR is missing, so the "
                    "compile-isomorphism check cannot run."
                ),
                diagnostics=(
                    _diag(
                        "done_gate_b_missing_ir",
                        "Gate B requires the retained IR (original/working/candidate); "
                        "none is available.",
                        severity="error",
                    ),
                ),
            )
        return self._done_gate_b_workflows(
            original_workflow=original,
            working_workflow=working,
            candidate_workflow=candidate,
            ops=ops,
        )

    def _replay_landed_ops_for_done(
        self,
        ops: tuple[Any, ...],
    ) -> tuple[dict[str, Any] | None, tuple[CompactDiagnostic, ...]]:
        """Replay interpret history and emit the candidate for Gate A."""
        del ops
        replayed, ir_diags = self._replay_interpret_for_done()
        if replayed is None:
            return None, ir_diags
        try:
            return self._emit_working_snapshot(replayed), ()
        except Exception as exc:
            return None, (
                _diag(
                    "done_gate_a_emit_failed",
                    f"Gate A emit of the replayed IR failed: {exc}",
                    severity="error",
                ),
            )

    def _workflow_from_ui(self, ui_json: Mapping[str, Any]) -> VibeWorkflow:
        from vibecomfy.ingest.normalize import (
            _assert_nonempty_ingest_preserved,
            _named_import,
        )

        workflow = _named_import(
            dict(ui_json),
            schema_provider=self.schema_provider,
            use_comfy_converter=False,
        )
        _assert_nonempty_ingest_preserved(ui_json, workflow)
        self._assert_resolver_map_integrity(workflow)
        return workflow

    def _assert_resolver_map_integrity(self, workflow: VibeWorkflow) -> None:
        """ONE resolver authority: fail closed on ambiguous uid/binding maps.

        The render and the edit tools share this IR.  Two nodes sharing a uid
        (or one binding resolving to two uids) would make the render-visible
        vocabulary ambiguous and every ``resolve_target`` first-match — a
        silent parity break.  This is a hydration-door invariant, not a new
        authority: it only rejects IRs whose resolver map cannot be one-to-one.
        """
        from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names

        uid_to_node: dict[str, str] = {}
        for nid, node in (workflow.nodes or {}).items():
            uid = str(getattr(node, "uid", "") or "")
            if uid:
                prior = uid_to_node.setdefault(uid, str(nid))
                if prior != str(nid):
                    raise WorkflowIngestError(
                        "ambiguous resolver map: nodes "
                        f"{prior!r} and {str(nid)!r} share uid {uid!r}."
                    )
        try:
            names = _compute_variable_names(workflow.nodes, list(workflow.edges))
        except Exception:  # noqa: BLE001 - binding derivation is best-effort
            return
        binding_to_uid: dict[str, str] = {}
        for nid, name in names.items():
            node = workflow.nodes.get(nid)
            uid = str(getattr(node, "uid", "") or "")
            if not uid:
                continue
            prior = binding_to_uid.setdefault(name, uid)
            if prior != uid:
                raise WorkflowIngestError(
                    f"ambiguous resolver map: binding {name!r} resolves to "
                    f"both uid {prior!r} and uid {uid!r}."
                )

    def _done_gate_b_workflows(
        self,
        *,
        original_workflow: VibeWorkflow,
        working_workflow: VibeWorkflow,
        candidate_workflow: VibeWorkflow,
        ops: tuple[EditOp, ...],
    ) -> DoneResult:
        compiled_original = self._compile_workflow_for_done_gate_b(original_workflow, label="original")
        if isinstance(compiled_original, DoneResult):
            return compiled_original
        original_workflow, original_api = compiled_original

        compiled_working = self._compile_workflow_for_done_gate_b(working_workflow, label="working")
        if isinstance(compiled_working, DoneResult):
            return compiled_working
        working_workflow, working_api = compiled_working

        compiled_candidate = self._compile_workflow_for_done_gate_b(candidate_workflow, label="candidate")
        if isinstance(compiled_candidate, DoneResult):
            return compiled_candidate
        candidate_workflow, candidate_api = compiled_candidate

        region_ids = self._done_gate_b_region_node_ids(
            ops=ops,
            original_workflow=original_workflow,
            original_api=original_api,
            working_workflow=working_workflow,
            working_api=working_api,
            candidate_workflow=candidate_workflow,
            candidate_api=candidate_api,
        )
        working_region = _subset_api_by_node_ids(working_api, region_ids)
        candidate_region = _subset_api_by_node_ids(candidate_api, region_ids)

        from vibecomfy.porting import parity

        ok, diffs = parity.compile_equivalent(working_region, candidate_region)
        if ok:
            return DoneResult(ok=True, summary="Gate B passed.")
        return DoneResult(
            ok=False,
            summary=(
                "Gate B failed: current working IR and replayed candidate are "
                "not compile-equivalent over the touched region."
            ),
            diagnostics=(
                _diag(
                    "done_gate_b_compile_isomorphism_failed",
                    "Touched-region compile equivalence failed.",
                    severity="error",
                    detail={
                        "region_node_ids": tuple(sorted(region_ids, key=_node_id_sort_key)),
                        "working_region_node_ids": tuple(sorted(working_region, key=_node_id_sort_key)),
                        "candidate_region_node_ids": tuple(sorted(candidate_region, key=_node_id_sort_key)),
                        "diffs": tuple(diffs),
                    },
                ),
            ),
        )

    def _done_gate_c(self, ops: tuple[EditOp, ...]) -> str:
        """Gate C: generate a plain-language summary from landed ops and ledger state.

        Covers: added/removed nodes, field changes, rewired edges, mode changes,
        socket types, and adjacent same-type inputs.
        """
        if not ops:
            return "No operations were applied."

        parts: list[str] = []
        op_kinds: dict[str, int] = {}
        for op in ops:
            kind = type(op).__name__
            op_kinds[kind] = op_kinds.get(kind, 0) + 1

        for op in ops:
            sentence = self._summarize_op(op)
            if sentence:
                parts.append(sentence)

        if not parts:
            return (
                f"{len(ops)} operation(s) applied: "
                + ", ".join(f"{count} {kind}" for kind, count in op_kinds.items())
                + "."
            )

        return " ".join(parts)

    def _compile_workflow_for_done_gate_b(
        self,
        workflow: VibeWorkflow,
        *,
        label: str,
    ) -> tuple[VibeWorkflow, dict[str, Any]] | DoneResult:
        try:
            # The compile oracle requires numeric output slots on runtime
            # nodes; interpret-written edges carry named ports, so project
            # the retained IR onto a compile-ready copy first.
            api = _compile_ready_workflow_copy(workflow).compile("api")
        except Exception as exc:
            return DoneResult(
                ok=False,
                summary=f"Gate B failed: {label} IR did not compile through the oracle.",
                diagnostics=(
                    _diag(
                        "done_gate_b_compile_failed",
                        f"Gate B could not compile {label} IR: {type(exc).__name__}: {exc}",
                        severity="error",
                        detail={"label": label, "exception_type": type(exc).__name__},
                    ),
                ),
            )
        return workflow, api

    def _done_gate_b_region_node_ids(
        self,
        *,
        ops: tuple[EditOp, ...],
        original_workflow: VibeWorkflow,
        original_api: Mapping[str, Any],
        working_workflow: VibeWorkflow,
        working_api: Mapping[str, Any],
        candidate_workflow: VibeWorkflow,
        candidate_api: Mapping[str, Any],
    ) -> set[str]:
        original_uid_to_node_id = _workflow_uid_to_node_id(original_workflow)
        working_uid_to_node_id = _workflow_uid_to_node_id(working_workflow)
        candidate_uid_to_node_id = _workflow_uid_to_node_id(candidate_workflow)

        original_ids = set(str(node_id) for node_id in original_api)
        working_ids = set(str(node_id) for node_id in working_api)
        candidate_ids = set(str(node_id) for node_id in candidate_api)
        live_ids = working_ids | candidate_ids
        region: set[str] = set()

        added_ids = live_ids - original_ids
        removed_ids = original_ids - live_ids
        region.update(added_ids)

        for _scope_path, uid in _done_gate_b_uids_for_ops(ops):
            for mapping in (original_uid_to_node_id, working_uid_to_node_id, candidate_uid_to_node_id):
                node_id = mapping.get(uid)
                if node_id is not None:
                    region.add(str(node_id))

        for node_id in removed_ids:
            region.update(_api_one_hop_neighbors(original_api, {node_id}))

        region.update(_changed_edge_endpoint_node_ids(original_api, working_api))
        region.update(_changed_edge_endpoint_node_ids(original_api, candidate_api))

        expanded = set(region)
        expanded.update(_api_one_hop_neighbors(working_api, region))
        expanded.update(_api_one_hop_neighbors(candidate_api, region))
        expanded.update(_api_one_hop_neighbors(original_api, region | removed_ids))
        return {node_id for node_id in expanded if node_id in live_ids}


def _route_gate_c_suffix(route: str | None) -> str:
    """Return a route-aware suffix for gate C edit summaries.

    direct_edit is a focused, targeted change — the summary reflects that.
    Other routes return an empty suffix (no change to existing summaries).
    """
    if route == "direct_edit":
        return " Change focus verified."
    return ""
