from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit.apply import apply_delta
from vibecomfy.porting.edit.ops import EditOp
from vibecomfy.porting.edit_session_ir_utils import (
    _api_one_hop_neighbors,
    _changed_edge_endpoint_node_ids,
    _done_gate_b_uids_for_ops,
    _node_id_sort_key,
    _subset_api_by_node_ids,
    _workflow_uid_to_node_id,
)
from vibecomfy.porting.edit_session_types import (
    CompactDiagnostic,
    DoneResult,
    _diag,
)

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


class _GatesMixin:
    def done(self) -> DoneResult:
        """Finalize the session: run Gate A and Gate B proof checks.

        Gate A replays all landed ops over ``original_ui`` through the
        deterministic ``apply_delta`` path (which internally resolves,
        applies, and calls ``guard_full_ui``).  It then asserts the
        recomputed candidate is deep-equal to the current ``working_ui``.

        Gate B compiles the current working UI and recomputed candidate
        through the normal UI -> ``VibeWorkflow`` -> ``compile("api")`` oracle,
        narrows both API graphs to the touched region induced by landed ops,
        and compares them with ``parity.compile_equivalent``.

        If zero ops have landed, it verifies that ``working_ui`` is still
        identical to ``original_ui``.
        """
        ops = tuple(self.landed_ops)

        if not ops:
            if self.working_ui != self.original_ui:
                return DoneResult(
                    ok=False,
                    summary=(
                        "Gate A failed: working_ui differs from original_ui "
                        "even though zero ops were landed."
                    ),
                    diagnostics=(
                        _diag(
                            "done_gate_a_mismatch",
                            (
                                "Zero ops landed but working_ui != original_ui. "
                                "This means something mutated working_ui outside "
                                "the edit-op path."
                            ),
                            severity="error",
                        ),
                    ),
                )
            gate_b = self._done_gate_b(self.working_ui, self.working_ui, ops)
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

        candidate, all_diags = self._replay_landed_ops_for_done(ops)

        if candidate is None:
            return DoneResult(
                ok=False,
                summary=(
                    f"Gate A: apply_delta over original_ui failed "
                    f"({len(all_diags)} diagnostic(s))."
                ),
                diagnostics=all_diags,
            )

        if candidate != self.working_ui:
            return DoneResult(
                ok=False,
                summary=(
                    "Gate A: recomputed candidate does not match working_ui. "
                    "The landed ops do not deterministically reproduce "
                    "the current state from the original."
                ),
                diagnostics=(
                    _diag(
                        "done_gate_a_mismatch",
                        (
                            "Recomputing all landed ops over original_ui "
                            "produced a candidate that differs from working_ui. "
                            "Ops may have been applied out of order or "
                            "working_ui may have been mutated externally."
                        ),
                        severity="error",
                    ),
                ),
            )

        gate_b = self._done_gate_b(self.working_ui, candidate, ops)
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

    def _replay_landed_ops_for_done(
        self,
        ops: tuple[Any, ...],
    ) -> tuple[dict[str, Any] | None, tuple[CompactDiagnostic, ...]]:
        """Replay landed ops in order for Gate A.

        ``apply_delta`` resolves a tuple against the input graph before it
        mutates that graph.  Batch edit statements are sequential, so a rewire
        may reference a node minted by an earlier add-node statement.  Replaying
        one op at a time preserves that sequential contract while still proving
        deterministic reproduction from ``original_ui``.
        """
        candidate: dict[str, Any] = deepcopy(self.original_ui)
        for op in ops:
            applied = apply_delta(
                candidate,
                (op,),
                schema_provider=self.schema_provider,
            )
            if not applied.ok or applied.candidate is None:
                issue_diagnostics = tuple(
                    self._compact_port_issue(issue) for issue in applied.diagnostics
                )
                guard_issues: tuple[CompactDiagnostic, ...] = ()
                if applied.guard_result is not None and applied.guard_result.diagnostics:
                    guard_issues = tuple(
                        self._compact_port_issue(issue)
                        for issue in applied.guard_result.diagnostics
                    )
                return None, issue_diagnostics + guard_issues
            candidate = applied.candidate
        return candidate, ()

    def _workflow_from_ui(self, ui_json: Mapping[str, Any]) -> VibeWorkflow:
        from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api

        api = normalize_to_api(
            deepcopy(dict(ui_json)),
            schema_provider=self.schema_provider,
            use_comfy_converter=False,
        )
        workflow = convert_to_vibe_format(
            api,
            schema_provider=self.schema_provider,
        )
        workflow.finalize_metadata()
        return workflow

    def _done_gate_b(
        self,
        working_ui: Mapping[str, Any],
        candidate_ui: Mapping[str, Any],
        ops: tuple[EditOp, ...],
    ) -> DoneResult:
        compiled_original = self._compile_ui_for_done_gate_b(self.original_ui, label="original")
        if isinstance(compiled_original, DoneResult):
            return compiled_original
        original_workflow, original_api = compiled_original

        compiled_working = self._compile_ui_for_done_gate_b(working_ui, label="working")
        if isinstance(compiled_working, DoneResult):
            return compiled_working
        working_workflow, working_api = compiled_working

        compiled_candidate = self._compile_ui_for_done_gate_b(candidate_ui, label="candidate")
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
                "Gate B failed: current working UI and replayed candidate are "
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

    def _compile_ui_for_done_gate_b(
        self,
        ui_json: Mapping[str, Any],
        *,
        label: str,
    ) -> tuple[VibeWorkflow, dict[str, Any]] | DoneResult:
        try:
            workflow = self._workflow_from_ui(ui_json)
            api = workflow.compile("api")
        except Exception as exc:
            return DoneResult(
                ok=False,
                summary=f"Gate B failed: {label} UI did not compile through the oracle.",
                diagnostics=(
                    _diag(
                        "done_gate_b_compile_failed",
                        f"Gate B could not compile {label} UI: {type(exc).__name__}: {exc}",
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

        for scope_path, uid in _done_gate_b_uids_for_ops(ops):
            qualified_uid = self.ledger.qualified_uid(scope_path, uid)
            for mapping in (original_uid_to_node_id, working_uid_to_node_id, candidate_uid_to_node_id):
                node_id = mapping.get(qualified_uid)
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
