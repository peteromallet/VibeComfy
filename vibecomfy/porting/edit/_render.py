from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.emitter import EmissionDiagnostic, emit_agent_edit_python
from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    _diag,
    _extract_uid_name_pairs,
)

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


class _RenderMixin:
    def render(self) -> str:
        # Batch 3 (IR authority): renders ALWAYS come from the retained IR
        # (seeded at construction by the agent path, refreshed once per
        # committed batch from the apply engine's candidate).  render() never
        # re-derives the IR from working_ui JSON and never re-ingests.
        # Batch 4 (Law 5): binding names are a pure function of the IR, so
        # no name locks are seeded or validated here.
        if self.workflow is None:
            # Last-resort ingest for sessions constructed without an IR.
            # Renders never re-derive from working_ui after the IR exists.
            self.workflow = self._workflow_from_ui(self.original_ui)
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        # Never mutate the retained IR.  Agent-edit emit keeps Get/Set/
        # Reroute/Primitive* as surface nodes, so helper-stripping is not
        # applied even on the copy.
        workflow = _cow_workflow_copy(self.workflow)
        emission_diagnostics: list[EmissionDiagnostic] = []
        started = perf_counter()
        source = emit_agent_edit_python(
            workflow,
            diagnostics=emission_diagnostics,
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        parsed_names = _extract_uid_name_pairs(source)
        for _uid, name in parsed_names:
            self.unbound_names.discard(name)
        all_diagnostics = [CompactDiagnostic.from_emission(item) for item in emission_diagnostics]
        if self.render_budget_ms is not None and elapsed_ms > self.render_budget_ms:
            all_diagnostics.append(
                _diag(
                    "render_budget_exceeded",
                    (
                        f"EditSession.render exceeded the configured render budget "
                        f"({elapsed_ms:.1f}ms > {self.render_budget_ms:.1f}ms)."
                    ),
                    severity="warning",
                    detail={"elapsed_ms": elapsed_ms, "budget_ms": self.render_budget_ms},
                )
            )
        self.render_count += 1
        self.last_rendered_source = source
        self.last_rendered_workflow = workflow
        self.last_render_diagnostics = tuple(all_diagnostics)
        return source
