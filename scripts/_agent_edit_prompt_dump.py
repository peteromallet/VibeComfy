#!/usr/bin/env python3
"""Dump the turn-0 agent-edit prompt for a ready-template workflow.

CLI: ``python scripts/_agent_edit_prompt_dump.py --ready-id <id> --out-dir <dir>``

Uses the RuneXX fallback chain when ``--ready-id`` is omitted or not found:

1. ``video/ltx2_3_runexx_first_last_frame``
2. First ``ready_templates/video/*runexx*`` match
3. ``video/wan_t2v``

Outputs
-------
``<id_sanitized>.prompt.txt``
    System and user messages with documented section separators.

``<id_sanitized>.metrics.json``
    Character counts and metadata for the prompt dump.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.comfy_nodes.agent.edit import _format_available_node_names, _present_class_types
from vibecomfy.comfy_nodes.agent.provider import build_batch_messages
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.registry.ready import ready_template_ids
from vibecomfy.schema import get_schema_provider


def _resolve_ready_id(requested: str | None) -> str:
    """Resolve the ready-id with the RuneXX fallback chain.

    Priority:
    1. Explicit ``--ready-id`` if it exists.
    2. ``video/ltx2_3_runexx_first_last_frame``.
    3. First ``ready_templates/video/*runexx*`` match (sorted).
    4. ``video/wan_t2v``.
    """
    ids = set(ready_template_ids())

    if requested:
        if requested in ids:
            return requested
        # Try partial path-name match (last component)
        for tid in sorted(ids):
            if tid.endswith("/" + requested) or tid == requested:
                return tid
        print(f"Warning: requested ready-id '{requested}' not found; falling back to RuneXX chain.",
              file=sys.stderr)

    # Step 2: video/ltx2_3_runexx_first_last_frame
    primary = "video/ltx2_3_runexx_first_last_frame"
    if primary in ids:
        return primary

    # Step 3: first video/*runexx* match
    video_runexx = sorted(
        tid for tid in ids
        if tid.startswith("video/") and "runexx" in tid.lower()
    )
    if video_runexx:
        return video_runexx[0]

    # Step 4: video/wan_t2v
    wan = "video/wan_t2v"
    if wan in ids:
        return wan

    raise SystemExit(
        f"No suitable ready template found. "
        f"Requested: {requested!r}. Available video templates: "
        f"{sorted(t for t in ids if t.startswith('video/'))}"
    )


def _sanitize(value: str) -> str:
    """Sanitize a string for use in a filename."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:80]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump turn-0 agent-edit prompt for a ready-template workflow."
    )
    parser.add_argument(
        "--ready-id",
        default=None,
        help="Ready template ID (e.g. video/ltx2_3_runexx_first_last_frame). "
             "Falls back to the RuneXX chain when omitted or not found.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Output directory for .prompt.txt and .metrics.json files.",
    )
    args = parser.parse_args()

    ready_id = _resolve_ready_id(args.ready_id)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Resolved ready-id: {ready_id}")

    # -- Load workflow --------------------------------------------------------
    workflow = load_workflow_any(ready_id)
    # Use the authoring provider so custom-node schemas cached under
    # vibecomfy/porting/cache/object_info are available even when no ComfyUI
    # runtime is running.  "auto" falls back to LocalSchemaProvider which
    # returns empty outside a live ComfyUI environment.
    schema_provider = get_schema_provider("authoring")

    # Emit UI JSON from the VibeWorkflow so we can feed it to EditSession.
    # The authoring provider may reject some ready templates whose widget
    # shapes don't match the cached schema (e.g. LTX-2.3 templates).  Fall
    # back to the lenient "auto" provider for emit-only when that happens.
    try:
        ui_json = emit_ui_json(workflow, schema_provider=schema_provider)
    except Exception:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ui_json = emit_ui_json(workflow, schema_provider=get_schema_provider("auto"))

    # -- Build EditSession (mirrors _stage_agent_batch_repl) ------------------
    session = EditSession(ui_json, schema_provider=schema_provider)
    python_source = session.render()
    present_types = _present_class_types(session)
    signature_catalog = session.search(focus_types=present_types, formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))

    # -- Build the turn-0 messages --------------------------------------------
    task = "Describe the current workflow state."
    messages = build_batch_messages(
        task=task,
        turn_number=0,
        python_source=python_source,
        signature_catalog=signature_catalog if isinstance(signature_catalog, str) else "",
        available_node_names=available_node_names,
        budget_remaining=3,
        max_batches=5,
    )

    system_msg = messages[0]["content"]
    user_msg = messages[1]["content"]

    # -- Compute metrics ------------------------------------------------------
    system_chars = len(system_msg)
    user_chars = len(user_msg)
    total_chars = system_chars + user_chars
    catalog_chars = len(signature_catalog) if isinstance(signature_catalog, str) else 0
    names_chars = len(available_node_names)
    python_chars = len(python_source)
    task_chars = len(task)

    metrics = {
        "ready_id": ready_id,
        "system_chars": system_chars,
        "user_chars": user_chars,
        "total_chars": total_chars,
        "catalog_chars": catalog_chars,
        "names_chars": names_chars,
        "python_chars": python_chars,
        "task_chars": task_chars,
        "present_type_count": len(present_types),
        "available_name_count": (
            len([n for n in available_node_names.splitlines() if n.strip()])
            if available_node_names
            else 0
        ),
    }

    # -- Write output files ---------------------------------------------------
    safe_id = _sanitize(ready_id)

    prompt_path = out_dir / f"{safe_id}.prompt.txt"
    prompt_lines = [
        "=== SYSTEM ===",
        system_msg,
        "",
        "=== USER ===",
        user_msg,
    ]
    prompt_path.write_text("\n".join(prompt_lines), encoding="utf-8")
    print(f"Wrote prompt: {prompt_path}")

    metrics_path = out_dir / f"{safe_id}.metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote metrics: {metrics_path}")

    # Quick summary to stdout
    print(
        f"\nSummary: system={system_chars} chars, user={user_chars} chars, "
        f"total={total_chars} chars, python={python_chars} chars, "
        f"catalog={catalog_chars} chars, names={names_chars} chars"
    )


if __name__ == "__main__":
    main()
