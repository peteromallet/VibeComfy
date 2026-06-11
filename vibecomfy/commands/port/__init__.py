from __future__ import annotations

# Backward-compatible public surface for ``vibecomfy.commands.port``.
#
# This package was split out of a single ``port.py`` god-file.  Every symbol
# that tests or other modules import from ``vibecomfy.commands.port`` is
# re-exported here, and every symbol that tests monkeypatch via
# ``vibecomfy.commands.port.<name>`` is bound as a module attribute on this
# package so the patch points stay valid.  Handlers in the submodules access
# the monkeypatch-sensitive names via this package object (``from
# vibecomfy.commands import port as _port; _port.<name>(...)``) so patching the
# package attribute takes effect.

# --- Shared / monkeypatch-sensitive symbols ---
from ._shared import (
    PORT_HELP,
    READY_ROOT,
    _apply_strict_ready_template_gate,
    _attach_contract_fields,
    _attach_report_strict_ready,
    _attach_top_level_strict_ready,
    _build_authoring_provider,
    _build_conversion_provider,
    _build_validate_call_provider,
    _emit_convert_payload,
    _emit_strict_ready_load_failure,
    _inject_schema_source_metadata,
    _object_info_cache_is_useful,
    _render_check,
)

# Names that handlers dereference via this package so that
# ``monkeypatch.setattr("vibecomfy.commands.port.<name>", ...)`` works.
from vibecomfy.registry import load_workflow_reference
from vibecomfy.porting.emit.ui import default_output_path, emit_ui_json
from vibecomfy.porting.layout import evaluate_felt_delta

# --- Command handlers ---
from ._check import _cmd_port_check, build_port_check_payload
from ._convert import _cmd_port_convert, _run_convert_all
from ._widgets import _cmd_port_widgets, _render_widgets
from ._export import (
    _artifact_payload,
    _cmd_port_export,
    _default_change_report_path,
    _emit_refused_emit,
    _format_widget_shape_node_line,
    _print_change_report,
    _print_felt_violation_summary,
    _print_from_overrides,
    _print_recovery_report,
    _read_ui_payload,
    _reroute_uids_for_workflow,
    _resolve_preserve_source,
    _widget_shape_verdict_counts,
)
from ._validate_call import _cmd_port_validate_call
from ._doctor_all import (
    _cmd_port_doctor_all,
    _doctor_all_doctor,
    _doctor_all_nodes_install_plan,
    _doctor_all_port_check,
    _doctor_all_runtime_doctor,
    _doctor_all_section,
    _doctor_all_validate,
    _first_next_action,
    _normalize_findings,
    _payload_next_action,
)
from ._inventory import _cmd_port_inventory, _render_inventory
from ._repair import _cmd_port_repair
from ._rules import _cmd_port_rules
from ._lint import _cmd_port_lint
from ._simulate import _cmd_port_simulate

from ._register import register


__all__ = [
    "register",
    "_cmd_port_check",
    "_cmd_port_convert",
    "_cmd_port_export",
    "_cmd_port_inventory",
    "_cmd_port_repair",
    "_cmd_port_widgets",
    "_cmd_port_validate_call",
    "_cmd_port_doctor_all",
    "_cmd_port_lint",
    "_cmd_port_rules",
    "_cmd_port_simulate",
]
