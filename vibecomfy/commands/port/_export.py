from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.layout_store import read_store, store_from_ui_json, write_store
from vibecomfy.porting.latency import FALLBACK_LATENCY_BUDGET_MS
from vibecomfy.porting.ui_emitter import default_output_path


def _print_change_report(
    report: Any,
    *,
    json_mode: bool = False,
    prior_store_existed: bool | None = None,
) -> None:
    """Print a ChangeReport to stderr (text) or stdout (JSON)."""
    from dataclasses import asdict  # noqa: PLC0415
    if json_mode:
        print(json.dumps({"change_report": asdict(report)}, indent=2, sort_keys=True))
    else:
        ce = report.content_edits
        ids = report.identity_stabilization
        lines = ["[change-report]"]
        lines.append(
            f"  content: preserved={len(ce.preserved)} edited={len(ce.edited)}"
            f" new={len(ce.new_auto_placed)} removed={len(ce.removed)}"
            f" virtual_wires_degraded={len(ce.virtual_wires_degraded)}"
        )
        # removed_named entries (uid + class_type per removed node)
        removed_named = getattr(ce, "removed_named", None) or []
        if removed_named:
            lines.append(f"  removed_named: {len(removed_named)} entry/ies")
            for rn in removed_named:
                lines.append(f"    uid={rn['uid']} class={rn.get('class_type', 'unknown')}")
        # stripped_helpers count
        stripped = getattr(ce, "stripped_helpers", None) or []
        if stripped:
            lines.append(f"  stripped_helpers: {len(stripped)}")
        # no prior layout found marker — fires on a genuine fresh layout:
        # prior store absent, nodes were placed, and no named removals or stripped helpers.
        if (
            prior_store_existed is False
            and ce.new_auto_placed
            and not removed_named
            and not stripped
        ):
            lines.append("  no prior layout found — fresh layout applied")
        if ids.bridge_minted:
            lines.append(f"  identity: bridge_minted={len(ids.bridge_minted)}")
        if ids.unmatched_legacy:
            lines.append(f"  identity: unmatched_legacy={len(ids.unmatched_legacy)}")
        if ids.definition_relayout:
            lines.append(f"  identity: definition_relayout={ids.definition_relayout}")
        print("\n".join(lines), file=sys.stderr)


def _print_from_overrides(
    overrides: dict[str, Any],
    *,
    json_mode: bool = False,
) -> None:
    """Print ``--from`` overrides (conflict resolution) to stderr or stdout.

    Called when both a sidecar and ``--from`` exist and ``--from`` entries
    override specific UIDs.  The sidecar is the base; ``--from`` provides
    explicit per-uid overrides.
    """
    if json_mode:
        print(json.dumps({"from_overrides": sorted(overrides.keys())}, indent=2, sort_keys=True))
    else:
        lines = [f"[from-overrides] {len(overrides)} uid(s) overridden from --from:"]
        for uid in sorted(overrides):
            lines.append(f"  {uid}")
        print("\n".join(lines), file=sys.stderr)


def _print_recovery_report(
    recovery_report: list[dict[str, Any]],
    *,
    json_mode: bool = False,
) -> None:
    """Print a structured recovery report to stderr (text) or stdout (JSON).

    The recovery report is populated by ``emit_ui_json`` only on the non-strict
    warn-and-emit path.  It records per-node provenance for schema-less nodes,
    low-confidence widget-schema-fallback nodes, and any widget-length-check
    warnings encountered during emission.

    Precedence note: ``--strict`` fails *before* the report is populated
    (``emit_ui_json`` raises ``ValueError``) — the except-arm in
    ``_cmd_port_export`` handles that path separately and the recovery report
    is never printed.
    """
    node_entries = [e for e in recovery_report if "node_id" in e]
    widget_shape_counts = _widget_shape_verdict_counts(node_entries)
    if json_mode:
        orphaned_count = sum(1 for e in node_entries if e.get("orphaned_route"))
        payload: dict[str, Any] = {
            "recovery_report": {
                "summary": {
                    "total_nodes": len(node_entries),
                    "schema_less": sum(1 for e in node_entries if e.get("schema_less")),
                    "low_confidence": sum(
                        1 for e in node_entries
                        if not e.get("schema_less") and e.get("confidence") is not None and e["confidence"] <= 0.3
                    ),
                    "widget_length_check_warnings": sum(
                        1 for e in node_entries if e.get("widget_length_check")
                    ),
                    "nodes_with_diagnostic": sum(1 for e in node_entries if e.get("diagnostic")),
                    "orphaned_routes": orphaned_count,
                    "widget_shape": widget_shape_counts,
                },
                "entries": node_entries,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        lines: list[str] = ["[recovery-report]"]
        schema_less_nodes = [e for e in node_entries if e.get("schema_less")]
        low_conf_nodes = [
            e for e in node_entries
            if not e.get("schema_less") and e.get("confidence") is not None and e["confidence"] <= 0.3
        ]
        widget_warn_nodes = [e for e in node_entries if e.get("widget_length_check")]
        orphaned_nodes = [e for e in node_entries if e.get("orphaned_route")]
        pinned_nodes = [e for e in node_entries if e.get("widget_shape_verdict") == "pin_opaque"]
        refused_nodes = [e for e in node_entries if e.get("widget_shape_verdict") == "refuse"]

        lines.append(
            "  widget-shape verdicts: "
            f"safe={widget_shape_counts['safe_to_regenerate']}, "
            f"pinned={widget_shape_counts['pin_opaque']}, "
            f"refused={widget_shape_counts['refuse']}"
        )

        if schema_less_nodes:
            lines.append(f"  schema-less nodes ({len(schema_less_nodes)}):")
            for e in schema_less_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): schema-less — "
                    f"best-effort slots from link appearance order"
                )
        if low_conf_nodes:
            lines.append(f"  low-confidence nodes ({len(low_conf_nodes)}):")
            for e in low_conf_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): "
                    f"confidence={e['confidence']} (widget_schema_fallback)"
                )
        if widget_warn_nodes:
            lines.append(f"  widget-length-check warnings ({len(widget_warn_nodes)}):")
            for e in widget_warn_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): {e.get('widget_length_check')}"
                )
        if pinned_nodes:
            lines.append(f"  pinned widget-shape nodes ({len(pinned_nodes)}):")
            for e in pinned_nodes:
                lines.append(f"    {_format_widget_shape_node_line(e)}")
        if refused_nodes:
            lines.append(f"  refused widget-shape nodes ({len(refused_nodes)}):")
            for e in refused_nodes:
                lines.append(f"    {_format_widget_shape_node_line(e)}")
        if orphaned_nodes:
            lines.append(f"  orphaned virtual-wire routes ({len(orphaned_nodes)}):")
            for e in orphaned_nodes:
                lines.append(
                    f"    {e['node_id']}({e['class_type']}): "
                    f"broadcast name={e.get('broadcast_name')!r} — "
                    f"no matching SetNode source"
                )
        stripped_entries = [e for e in recovery_report if "stripped_helpers" in e]
        if stripped_entries:
            _stripped_entry = stripped_entries[0]
            _stripped_count = _stripped_entry.get("count", 0)
            if _stripped_count > 0:
                _stripped_ids = _stripped_entry.get("stripped_helpers", [])
                lines.append(f"  stripped virtual-wire helpers ({_stripped_count}): {', '.join(_stripped_ids)}")
        if (
            not schema_less_nodes
            and not low_conf_nodes
            and not widget_warn_nodes
            and not pinned_nodes
            and not refused_nodes
            and not orphaned_nodes
        ):
            lines.append("  (no issues — all nodes resolved with high confidence)")
        print("\n".join(lines), file=sys.stderr)


def _widget_shape_verdict_counts(recovery_report: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "safe_to_regenerate": 0,
        "pin_opaque": 0,
        "refuse": 0,
    }
    for entry in recovery_report:
        verdict = entry.get("widget_shape_verdict")
        if verdict in counts:
            counts[verdict] += 1
    return counts


def _format_widget_shape_node_line(entry: dict[str, Any]) -> str:
    reasons = entry.get("widget_shape_reasons")
    if not reasons:
        details = entry.get("widget_shape_details")
        if isinstance(details, dict):
            reasons = details.get("reasons")
    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "unknown"
    return f"{entry['node_id']}({entry['class_type']}): reasons={reason_text}"


def _emit_refused_emit(
    exc: Exception,
    *,
    json_mode: bool,
) -> None:
    diff = getattr(exc, "diff", {})
    if json_mode:
        payload = {
            "status": "refused",
            "reason": str(exc),
            "refused_emit": diff,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=repr))
        return

    print(
        f"port export refused: {exc}",
        file=sys.stderr,
    )
    if diff:
        print(
            json.dumps({"refused_emit": diff}, indent=2, sort_keys=True, default=repr),
            file=sys.stderr,
        )


def _default_change_report_path(out_path: Path) -> Path:
    """Return the default sibling artifact path for a UI export."""
    if out_path.suffix == ".json":
        return out_path.with_suffix(".change-report.json")
    return out_path.with_name(f"{out_path.name}.change-report.json")


def _reroute_uids_for_workflow(workflow: Any) -> frozenset[str]:
    """Return preserve-identity keys for reroute nodes in *workflow*."""
    return frozenset(
        (node.uid or node_id)
        for node_id, node in workflow.nodes.items()
        if node.class_type == "Reroute"
    )


def _artifact_payload(
    *,
    change_report: Any,
    felt_report: Any,
) -> dict[str, Any]:
    """Build the structured change-report artifact payload."""
    latency = dataclasses.asdict(felt_report.latency) if getattr(felt_report, "latency", None) else None
    return {
        "change_report": dataclasses.asdict(change_report),
        "felt": dataclasses.asdict(felt_report),
        "latency": latency,
        "version": 1,
    }


def _print_felt_violation_summary(
    felt_report: Any,
    *,
    artifact_path: Path | None = None,
) -> None:
    """Emit a concise stderr summary for a felt-gate failure."""
    lines = [felt_report.summary]
    for violation in felt_report.violations:
        lines.append(
            "  "
            f"uid={violation.uid} reason={violation.reason}"
            f" prior_pos={violation.prior_pos}"
            f" current_pos={violation.current_pos}"
            f" delta_px={violation.delta_px}"
        )
    if artifact_path is not None:
        lines.append(f"  artifact={artifact_path}")
    if getattr(felt_report, "latency", None) is None:
        lines.append(
            f"  latency=not_measured fallback_budget_ms={int(FALLBACK_LATENCY_BUDGET_MS)}"
        )
    print("\n".join(lines), file=sys.stderr)


def _resolve_preserve_source(
    args: argparse.Namespace,
    py_path: Path,
    workflow: Any,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve the preserve source for ``port export --to ui``.

    Precedence (highest first):
    1. ``--fresh`` → no preserve (returns ``None, None, None``).
    2. ``--from <path>`` + sidecar conflict → sidecar wins as base;
       ``--from`` entries are per-uid overrides surfaced in the change report.
    3. ``--from <path>`` only → load via ``store_from_ui_json``.
    4. Sidecar only → ``read_store(py_path)``.
    5. Breadcrumb auto-discovery → look for a prior emitted UI JSON at the
       default output path, check ``extra.vibecomfy.prior_path`` matches
       ``py_path``, and if so load it via ``store_from_ui_json``.
    6. No source → fresh (returns ``None, None, None``).

    Returns ``(store_envelope | None, prior_path_str | None,
    from_overrides | None, prior_ui_payload | None)``.
    ``from_overrides`` is a dict ``{uid: entry}`` listing UIDs explicitly
    overridden from ``--from`` when both sidecar and ``--from`` exist, else ``None``.
    ``prior_ui_payload`` is only populated from a real UI JSON source; sidecar
    stores remain furniture-only.
    """
    # 1. --fresh overrides everything
    if getattr(args, "fresh", False):
        return None, None, None, None

    # 2. Check for both --from and sidecar (conflict case)
    from_path = getattr(args, "from_path", None)
    sidecar_store = read_store(py_path)

    if from_path and sidecar_store:
        # Conflict policy: sidecar wins as base; --from provides per-uid overrides
        from_store = store_from_ui_json(from_path)
        from_ui_payload = _read_ui_payload(from_path)
        from_entries = from_store.get("entries", {})
        base_entries = sidecar_store.get("entries", {})

        # Identify overridden UIDs: keys present in both that differ
        overrides: dict[str, Any] = {}
        for uid, from_entry in from_entries.items():
            if uid in base_entries and from_entry != base_entries[uid]:
                overrides[uid] = from_entry
            elif uid not in base_entries:
                # New UIDs from --from that aren't in sidecar are also overrides
                overrides[uid] = from_entry

        if overrides:
            # Merge: base = sidecar, apply --from overrides on top
            merged = dict(sidecar_store)
            merged_entries = dict(base_entries)
            merged_entries.update(overrides)
            merged["entries"] = merged_entries
            return merged, str(py_path), overrides, from_ui_payload
        else:
            # No differences — sidecar is authoritative
            return sidecar_store, str(py_path), None, None

    # 3. --from <path> only
    if from_path:
        store = store_from_ui_json(from_path)
        return store, str(from_path), None, _read_ui_payload(from_path)

    # 4. Sidecar only
    if sidecar_store:
        return sidecar_store, str(py_path), None, None

    # 5. Breadcrumb auto-discovery: look for a prior emitted UI JSON at the
    #    default output path and check its extra.vibecomfy.prior_path.
    candidate_path = default_output_path(workflow, source_template=py_path.stem)
    if candidate_path.exists():
        try:
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            extra_vc = candidate.get("extra", {}).get("vibecomfy", {})
            breadcrumb_prior = extra_vc.get("prior_path")
            if breadcrumb_prior and Path(breadcrumb_prior).resolve() == py_path.resolve():
                store = store_from_ui_json(candidate_path)
                return store, str(candidate_path), None, candidate
        except (json.JSONDecodeError, OSError):
            pass

    # 6. No source → fresh
    return None, None, None, None


def _read_ui_payload(path: str | Path) -> dict[str, Any] | None:
    try:
        candidate = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    if isinstance(candidate, dict) and isinstance(candidate.get("nodes"), list):
        return candidate
    return None


def _cmd_port_export(args: argparse.Namespace) -> int:
    from vibecomfy.commands import port as _port

    if args.to == "json":
        try:
            schema_provider = _port._build_authoring_provider(args)
            workflow = _port.load_workflow_reference(
                args.workflow,
                schema_provider=schema_provider,
                allow_scratchpad=True,
                ready=getattr(args, "ready", False),
            )
            payload = {
                "status": "ok",
                "workflow": args.workflow,
                "format": "api",
                "api": workflow.export_to_json(format="api"),
            }
        except Exception as exc:
            print(f"port export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload["api"], indent=2, sort_keys=True))
        return 0

    if args.to == "ui":
        recovery_report: list[dict[str, Any]] = []
        change_report_out: list = []
        try:
            schema_provider = _port._build_conversion_provider(args)
            workflow = _port.load_workflow_reference(
                args.workflow,
                schema_provider=schema_provider,
                allow_scratchpad=True,
                ready=getattr(args, "ready", False),
            )
            # Prefer the real on-disk .py path from the loaded workflow so the
            # layout-store sidecar is written next to the actual template file.
            _src = getattr(workflow, "source", None)
            _src_path = getattr(_src, "path", None) if _src else None
            if _src_path and Path(_src_path).suffix == ".py" and Path(_src_path).exists():
                py_path = Path(_src_path)
            else:
                py_path = Path(args.workflow)
            store, prior_path_str, from_overrides, prior_ui_payload = _resolve_preserve_source(args, py_path, workflow)

            # M5 Step 16: when the preserve source is a UI JSON on disk (--from
            # or breadcrumb auto-discovery), load it as the guard's "original"
            # so refuse.guard_emit can refuse a corrupted re-emit.
            guard_original_ui: dict[str, Any] | None = None
            if prior_path_str and prior_path_str != str(py_path):
                try:
                    _prior_text = Path(prior_path_str).read_text(encoding="utf-8")
                    _candidate = json.loads(_prior_text)
                    if isinstance(_candidate, dict) and isinstance(_candidate.get("nodes"), list):
                        guard_original_ui = _candidate
                except Exception:
                    guard_original_ui = None

            # Extract sidecar sections for explicit kwargs (for callers that pre-resolved them)
            sidecar_groups = store.get("groups") if store else None
            sidecar_extra = store.get("extra") if store else None
            sidecar_definitions = store.get("definitions") if store else None
            _force_drop = bool(getattr(args, "force_drop", False))
            # Wrap emit_ui_json so we can retry with --force-drop on EditorAheadError.
            _emit_kwargs: dict[str, Any] = dict(
                prior_store=store,
                prior_path=prior_path_str,
                strict=getattr(args, "strict", False),
                include_main_positions=getattr(args, "main_positions", False),
                include_virtual_wires=not getattr(args, "no_virtual_wires", False),
                recovery_report=recovery_report,
                groups=sidecar_groups,
                extra=sidecar_extra,
                definitions=sidecar_definitions,
                change_report_out=change_report_out,
                guard_original_ui=guard_original_ui,
                prior_ui_payload=prior_ui_payload,
            )
            try:
                ui_payload = _port.emit_ui_json(
                    workflow,
                    schema_provider=schema_provider,
                    force_drop_editor_only=False,
                    **_emit_kwargs,
                )
            except Exception as _emit_exc:
                if type(_emit_exc).__name__ == "EditorAheadError" and _force_drop:
                    ui_payload = _port.emit_ui_json(
                        workflow,
                        schema_provider=schema_provider,
                        force_drop_editor_only=True,
                        **_emit_kwargs,
                    )
                else:
                    raise
            if args.out:
                out_path = Path(args.out)
            else:
                out_path = default_output_path(workflow, source_template=py_path.stem)
            change_report_path = Path(
                getattr(args, "change_report_out", "") or _default_change_report_path(out_path)
            )
            include_virtual_wires = not getattr(args, "no_virtual_wires", False)
            reroute_uids = (
                frozenset()
                if getattr(args, "fresh", False) or not include_virtual_wires
                else _reroute_uids_for_workflow(workflow)
            )
            felt_report = (
                _port.evaluate_felt_delta(
                    store,
                    ui_payload,
                    change_report_out[0],
                    reroute_uids=reroute_uids,
                )
                if change_report_out
                else None
            )
            artifact_payload = (
                _artifact_payload(change_report=change_report_out[0], felt_report=felt_report)
                if change_report_out and felt_report is not None
                else None
            )

            dry_run = getattr(args, "dry_run", False)
            if dry_run:
                print(f"[dry-run] would write to {out_path}", file=sys.stderr)
                if artifact_payload is not None:
                    print(f"[dry-run] would write to {change_report_path}", file=sys.stderr)
            else:
                if artifact_payload is not None:
                    change_report_path.parent.mkdir(parents=True, exist_ok=True)
                    change_report_path.write_text(
                        json.dumps(artifact_payload, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                if felt_report is not None and not felt_report.ok and not felt_report.skipped_snapshot_absent:
                    _print_felt_violation_summary(felt_report, artifact_path=change_report_path)
                    return 5
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(ui_payload, indent=2, sort_keys=True), encoding="utf-8")
                print(f"wrote {out_path}")
            if dry_run and felt_report is not None and not felt_report.ok and not felt_report.skipped_snapshot_absent:
                _print_felt_violation_summary(felt_report, artifact_path=change_report_path)
                return 5

            # Emit layout sidecar alongside the UI JSON (best-effort).
            # Build the store from the freshly-emitted ui_payload (which carries
            # correct positions in properties['vibecomfy_uid']).  Do NOT call
            # write_layout(py_path, workflow) here: a workflow loaded from a .py
            # file has no _ui metadata so write_layout would overwrite the valid
            # convert-time sidecar with empty entries.
            if not dry_run:
                try:
                    write_store(py_path, store_from_ui_json(ui_payload))
                except Exception:
                    pass  # Sidecar write is best-effort; never block the main export

            # --- Change report ---
            if change_report_out:
                _print_change_report(
                    change_report_out[0],
                    json_mode=bool(getattr(args, "json", False)),
                    prior_store_existed=store is not None,
                )

            # --- From-overrides report (conflict: --from over sidecar) ---
            if from_overrides:
                _print_from_overrides(from_overrides, json_mode=bool(getattr(args, "json", False)))

            # --- Recovery report (non-strict path) ---
            if recovery_report:
                _print_recovery_report(recovery_report, json_mode=bool(getattr(args, "json", False)))
        except ValueError as exc:
            # Strict-mode failure: schema-less or low-confidence nodes.
            # emit_ui_json raises ValueError BEFORE populating recovery_report,
            # so we report the failure message directly.
            print(f"port export strict failed: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            # M5 Step 16: refusal-spine surfaces RefusedEmit as a typed failure.
            # Detect by class name to avoid an import cycle on the cold path.
            if type(exc).__name__ == "RefusedEmit":
                if recovery_report:
                    _print_recovery_report(recovery_report, json_mode=bool(getattr(args, "json", False)))
                _emit_refused_emit(exc, json_mode=bool(getattr(args, "json", False)))
                return 3
            # EditorAheadError: editor-only nodes detected in prior UI JSON.
            if type(exc).__name__ == "EditorAheadError":
                editor_only = getattr(exc, "editor_only_uids", [])
                uid_list = ", ".join(
                    f"uid={e['uid']} class={e['class_type']}" for e in editor_only
                )
                print(
                    f"port export refused: editor is ahead — {len(editor_only)} node(s) "
                    f"exist in the prior UI JSON but not in the Python IR: {uid_list}. "
                    f"Re-run `port convert <prior.json>` to import them, "
                    f"or pass --force-drop to discard explicitly.",
                    file=sys.stderr,
                )
                return 4
            print(f"port export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0

    print(f"unsupported export target: {args.to!r}; supported values: json, ui", file=sys.stderr)
    return 2
