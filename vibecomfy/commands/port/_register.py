from __future__ import annotations

import argparse

from ._shared import PORT_HELP
from ._widgets import _cmd_port_widgets
from ._export import _cmd_port_export
from ._validate_call import _cmd_port_validate_call
from ._doctor_all import _cmd_port_doctor_all
from ._inventory import _cmd_port_inventory
from ._repair import _cmd_port_repair
from ._rules import _cmd_port_rules
from ._lint import _cmd_port_lint
from ._simulate import _cmd_port_simulate


def register(subparsers) -> None:
    port = subparsers.add_parser(
        "port",
        description=PORT_HELP,
        epilog=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    port_subparsers = port.add_subparsers(dest="port_cmd", required=True)

    widgets = port_subparsers.add_parser(
        "widgets",
        help="Suggest widget-only schema entries for unresolved positional aliases.",
        description=(
            "Report widget_alias_unresolved diagnostics grouped by class and suggest "
            "widget-only schema entries from local node_index/object_info data when available."
        ),
    )
    widgets.add_argument("workflow")
    widgets.add_argument("--json", action="store_true")
    widgets.set_defaults(func=_cmd_port_widgets)

    export = port_subparsers.add_parser("export", help="Export a loaded workflow as API JSON or UI JSON with optional layout-sidecar preservation.")
    export.add_argument("workflow")
    export.add_argument("--ready", action="store_true")
    export.add_argument("--to", default="json")
    export.add_argument("--json", action="store_true")
    export.add_argument("--object-info-cache")
    export.add_argument("--out", default=None, help="Output file path (required for --to ui).")
    export.add_argument(
        "--persist-sidecar",
        action="store_true",
        help="Persist the optional layout sidecar next to the loaded Python source; implied only when --out is omitted.",
    )
    export.add_argument("--strict", action="store_true", help="Raise ValueError on schema-less or low-confidence node class types.")
    export.add_argument("--main-positions", action="store_true", help="Include main positions in emitted UI JSON (no-op, wired for future use).")
    export.add_argument("--no-virtual-wires", action="store_true", help="Omit SetNode/GetNode virtual wire resolution.")
    export.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any prior store (sidecar, --from, breadcrumb) and emit a fresh layout.",
    )
    export.add_argument(
        "--from",
        dest="from_path",
        default=None,
        help="Path to a prior emitted UI JSON to use as the preserve source (loaded via store_from_ui_json).",
    )
    export.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the recovery report and change summary without writing files.",
    )
    export.add_argument(
        "--force-drop",
        action="store_true",
        help="Explicitly drop editor-only nodes detected in the prior UI JSON.",
    )
    export.add_argument(
        "--change-report-out",
        default=None,
        help="Override path for the structured change-report artifact (default: <output>.change-report.json).",
    )
    export.set_defaults(func=_cmd_port_export)

    validate_call = port_subparsers.add_parser("validate-call", help="Validate one node call against authoring schema.")
    validate_call.add_argument("class_type")
    validate_call.add_argument("--kwargs", required=True, help="JSON object of node kwargs to validate.")
    validate_call.add_argument("--json", action="store_true")
    validate_call.add_argument("--object-info-cache")
    validate_call.set_defaults(func=_cmd_port_validate_call)

    doctor_all = port_subparsers.add_parser("doctor-all", help="Run port, install-plan, validate, doctor, and runtime doctor sections.")
    doctor_all.add_argument("workflow")
    doctor_all.add_argument("--ready", action="store_true")
    doctor_all.add_argument("--json", action="store_true")
    doctor_all.add_argument("--object-info-cache")
    doctor_all.set_defaults(func=_cmd_port_doctor_all)

    inventory = port_subparsers.add_parser(
        "inventory",
        help="Repo-only readability inventory for checked-in ready templates.",
        description=(
            "Emit a deterministic, versioned JSON report built from the static "
            "ready_templates/**/*.py glob. Never consults plugin/cwd/user-global paths."
        ),
    )
    inventory.add_argument("--ready", action="store_true", default=True, help=argparse.SUPPRESS)
    inventory.add_argument("--json", action="store_true")
    inventory.set_defaults(func=_cmd_port_inventory)

    repair = port_subparsers.add_parser(
        "repair",
        help="Dry-run marker-aware manual-template repair analysis and review packets.",
        description=(
            "Analyze a checked-in manual ready template in mechanical or semantic mode. "
            "Dry-run is the default; pass --write to allow edits."
        ),
    )
    repair.add_argument("workflow")
    repair.add_argument("--mode", choices=("mechanical", "semantic"), required=True)
    repair.add_argument("--json", action="store_true")
    repair.add_argument("--review-out", default="out/review_packets")
    repair.add_argument("--write", action="store_true")
    repair.set_defaults(func=_cmd_port_repair)

    rules = port_subparsers.add_parser(
        "rules",
        help="Codemod rule introspection.",
    )
    rules.add_argument("--explain", action="store_true", help="Show detailed rule behavior descriptions")
    rules.add_argument("--json", action="store_true")
    rules.set_defaults(func=_cmd_port_rules)

    lint = port_subparsers.add_parser(
        "lint",
        help="Convention enforcer over generated templates.",
    )
    lint.add_argument("workflow", nargs="?", help="Ready template file path or ID")
    lint.add_argument("--all", action="store_true", help="Lint all ready_templates/**/*.py")
    lint.add_argument("--json", action="store_true")
    lint.set_defaults(func=_cmd_port_lint)

    simulate = port_subparsers.add_parser(
        "simulate",
        help="Bounded simulation of a pure generated-template rule.",
    )
    simulate.add_argument("--rule", required=True, help="Rule spec (e.g. drop_set_id_map=true)")
    simulate.add_argument("--all", action="store_true", help="Simulate corpus-wide")
    simulate.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON; exit 2 when templates are unsupported, 1 on failure.",
    )
    simulate.set_defaults(func=_cmd_port_simulate)
