from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit_ledger import EditLedger
from vibecomfy.porting.emitter import EmissionDiagnostic, emit_agent_edit_python
from vibecomfy.porting.edit_session_types import (
    CompactDiagnostic,
    _diag,
    _extract_uid_name_pairs,
)

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


class _RenderMixin:
    def render(self) -> str:
        self.ledger = EditLedger.ingest(self.working_ui)
        workflow = self._workflow_from_ui(self.working_ui)
        from vibecomfy.porting.helper_resolve import resolve_helpers

        resolve_diagnostics = resolve_helpers(workflow, {})
        emission_diagnostics: list[EmissionDiagnostic] = []
        started = perf_counter()
        source = emit_agent_edit_python(
            workflow,
            diagnostics=emission_diagnostics,
            raw_workflow=self.working_ui,
            variable_name_locks=self.name_by_uid or None,
            strict_variable_name_locks=bool(self.name_by_uid),
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        parsed_names = _extract_uid_name_pairs(source)
        lock_diagnostics = self._seed_or_validate_name_locks(parsed_names)
        all_diagnostics = [CompactDiagnostic.from_emission(item) for item in emission_diagnostics]
        all_diagnostics.extend(
            _diag(
                f"resolve_{item.code}",
                item.message,
                severity=item.severity,
                detail={
                    "node_id": item.node_id,
                    "class_type": item.class_type,
                    **dict(item.detail),
                },
            )
            for item in resolve_diagnostics.diagnostics
        )
        all_diagnostics.extend(lock_diagnostics)
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

    def _seed_or_validate_name_locks(
        self,
        parsed_names: list[tuple[str, str]],
    ) -> list[CompactDiagnostic]:
        diagnostics: list[CompactDiagnostic] = []
        seen_render_uids: set[str] = set()
        seen_render_names: set[str] = set()
        for uid, name in parsed_names:
            seen_render_uids.add(uid)
            seen_render_names.add(name)
            self.unbound_names.discard(name)
            locked_name = self.name_by_uid.get(uid)
            locked_uid = self.uid_by_name.get(name)
            if locked_name is None and locked_uid is None:
                self.name_by_uid[uid] = name
                self.uid_by_name[name] = uid
                continue
            if locked_name is not None and locked_name != name:
                diagnostics.append(
                    _diag(
                        "render_name_lock_mismatch",
                        f"Uid {uid!r} re-rendered as {name!r} instead of locked name {locked_name!r}.",
                        severity="error",
                        detail={"uid": uid, "expected_name": locked_name, "actual_name": name},
                    )
                )
                continue
            if locked_uid is not None and locked_uid != uid:
                diagnostics.append(
                    _diag(
                        "render_uid_lock_mismatch",
                        f"Name {name!r} is already locked to uid {locked_uid!r}, not {uid!r}.",
                        severity="error",
                        detail={"name": name, "expected_uid": locked_uid, "actual_uid": uid},
                    )
                )
                continue
            self.name_by_uid.setdefault(uid, name)
            self.uid_by_name.setdefault(name, uid)

        if self.name_by_uid:
            missing_uids = sorted(uid for uid in self.name_by_uid if uid not in seen_render_uids)
            for uid in missing_uids:
                diagnostics.append(
                    _diag(
                        "render_locked_uid_missing",
                        f"Previously locked uid {uid!r} was absent from the latest render.",
                        severity="error",
                        detail={"uid": uid, "locked_name": self.name_by_uid[uid]},
                    )
                )
        if self.uid_by_name:
            missing_names = sorted(name for name in self.uid_by_name if name not in seen_render_names)
            for name in missing_names:
                diagnostics.append(
                    _diag(
                        "render_locked_name_missing",
                        f"Previously locked name {name!r} was absent from the latest render.",
                        severity="error",
                        detail={"name": name, "locked_uid": self.uid_by_name[name]},
                    )
                )

        return diagnostics
