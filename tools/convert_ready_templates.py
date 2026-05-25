"""Drive the conversion of ready_templates/*.py from JSON-flavored Python to
real Python that calls `wf.node(class_type, **kwargs)` directly.

Usage:

    python -m tools.convert_ready_templates --template image/z_image --dry-run
    python -m tools.convert_ready_templates --all --dry-run
    python -m tools.convert_ready_templates --all --write
    python -m tools.convert_ready_templates --all --write --include-manual
    python -m tools.convert_ready_templates --regenerate-snapshots
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
READY_ROOT = REPO_ROOT / "ready_templates"
OUT_PREVIEW_ROOT = REPO_ROOT / "out" / "converted"
SNAPSHOT_ROOT = REPO_ROOT / "tests" / "snapshots"
VENDOR_COMFY = REPO_ROOT / "vendor" / "ComfyUI"

# Shared safety gates from the porting package (Sprint 1).
from vibecomfy.porting.convert import (  # noqa: E402
    PROTECTED_TEMPLATE_MARKERS,
    RECOGNIZED_TEMPLATE_MARKERS,
    _first_line_template_marker,
    _check_manual_refusal,
    ManualTemplateRefusal,
)


RECOGNIZED_MARKERS = RECOGNIZED_TEMPLATE_MARKERS
PROTECTED_MARKERS = PROTECTED_TEMPLATE_MARKERS


# --- bootstrap: make vendor/ComfyUI importable so normalize_to_api works -----


def _bootstrap_comfy_runtime() -> None:
    """Ensure `comfy.component_model.workflow_convert` is callable."""
    sys_path_str = str(VENDOR_COMFY)
    if sys_path_str not in sys.path:
        sys.path.insert(0, sys_path_str)
    try:
        from comfy.nodes.package import import_all_nodes_in_workspace
    except Exception as exc:  # pragma: no cover - environment-dependent
        logging.warning("comfy runtime not available: %s", exc)
        return
    # Silence noisy load logs for cloud-service stub failures during import.
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)
    try:
        import_all_nodes_in_workspace(raise_on_failure=False)
    except Exception as exc:
        logging.warning("import_all_nodes_in_workspace failed: %s", exc)
    finally:
        logging.disable(logging.NOTSET)


# --- driver ------------------------------------------------------------------


@dataclass
class Row:
    template_id: str
    shape: str = "?"
    parse: str = "?"
    build: str = "?"
    validate: str = "?"
    roundtrip: str = "?"
    snapshot: str = "?"
    note: str = ""
    diffs: list[str] = field(default_factory=list)


def _enumerate_templates() -> list[Path]:
    paths: list[Path] = []
    for p in sorted(READY_ROOT.rglob("*.py")):
        if p.name == "__init__.py" or p.name.startswith("_"):
            continue
        paths.append(p)
    return paths


def _template_id_for_path(path: Path) -> str:
    return path.relative_to(READY_ROOT).with_suffix("").as_posix()


def _read_module_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _classify_shape(path: Path) -> tuple[str, str]:
    """Return (shape, note). Shapes: legacy | authored | manual | converted | unknown."""
    text = _read_module_source(path)
    first_line = text.splitlines()[0] if text.splitlines() else ""
    marker = _first_line_template_marker(path)
    # Inspect symbol presence.
    has_api = re.search(r"^API_WORKFLOW\s*=", text, re.MULTILINE)
    has_nodes = re.search(r"^NODES\s*=", text, re.MULTILINE)
    if has_api:
        note = (
            f"{marker} marker ignored for legacy API_WORKFLOW"
            if marker in PROTECTED_TEMPLATE_MARKERS
            else ""
        )
        return ("legacy", note)
    if marker in PROTECTED_TEMPLATE_MARKERS:
        return ("manual", f"{marker} marker on first line")
    if marker == "generated":
        return ("authored", "previously generated; eligible for v2.5 re-port")
    if has_nodes:
        return ("authored", "")
    # Neither symbol: v2.4/v2.5 ready templates are normal Python modules and
    # remain eligible for re-porting through the build/compile path.
    return ("authored", "no API_WORKFLOW or NODES; using build/compile re-port path")


def _load_override(path: Path) -> dict | None:
    override_path = path.with_suffix(path.suffix + ".override.json")
    if override_path.exists():
        try:
            return json.loads(override_path.read_text())
        except Exception as exc:
            logging.warning("override.json parse failed: %s", exc)
    return None


def _source_workflow_path(metadata: dict[str, Any]) -> Path | None:
    source = metadata.get("source_workflow")
    provenance = metadata.get("provenance")
    if not source and isinstance(provenance, dict):
        source = provenance.get("source_workflow")
    if not isinstance(source, str) or not source:
        return None
    path = Path(source)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path if path.exists() else None


def _load_source_workflow(metadata: dict[str, Any]) -> dict | None:
    path = _source_workflow_path(metadata)
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("source workflow parse failed for %s: %s", path, exc)
        return None


def _subgraph_definition_count(raw_workflow: dict | None) -> int:
    if not isinstance(raw_workflow, dict):
        return 0
    definitions = raw_workflow.get("definitions")
    if not isinstance(definitions, dict):
        return 0
    subgraphs = definitions.get("subgraphs")
    if isinstance(subgraphs, dict):
        return len(subgraphs)
    if isinstance(subgraphs, list):
        return len(subgraphs)
    return 0


def _convert_template(path: Path, *, include_manual: bool = False) -> tuple[Row, str | None, dict | None]:
    """Process one template. Returns (row, emitted_text or None, original_compiled_api)."""
    template_id = _template_id_for_path(path)
    row = Row(template_id=template_id)

    # --- shared manual-refusal gate (Sprint 1) --------------------------------
    manual_included = False
    try:
        _check_manual_refusal(path)
    except ManualTemplateRefusal:
        marker = _first_line_template_marker(path)
        if not include_manual or marker == "broken-regen":
            row.shape = "manual-refused"
            row.parse = "skip"
            row.build = "skip"
            row.validate = "skip"
            row.roundtrip = "skip"
            row.snapshot = "skip"
            row.note = (
                "manual template refused by shared gate"
                if marker == "manual"
                else "protected template refused by shared gate"
            )
            return (row, None, None)
        manual_included = True
        row.note = "manual template included by explicit v2.6 override"

    shape, shape_note = _classify_shape(path)
    row.shape = shape
    if shape_note:
        row.note = "; ".join(part for part in (row.note, shape_note) if part)

    # Already-converted templates are skipped (no emission work needed).
    if shape == "converted":
        row.parse = "skip"
        row.build = "skip"
        row.validate = "skip"
        row.roundtrip = "skip"
        row.snapshot = "skip"
        return (row, None, None)

    # Build the original workflow first so we can roundtrip-equality check.
    original_api = None
    try:
        from vibecomfy.registry.ready import workflow_from_ready
        original_workflow = workflow_from_ready(template_id)
        original_api = original_workflow.compile("api")
        row.parse = "ok"
    except Exception as exc:
        row.parse = "fail"
        row.note = f"build_original_failed: {type(exc).__name__}: {exc}"
        return (row, None, None)

    # Drive the parser path (matching the spec's distinction).
    try:
        from tools.format_as_python import _build_workflow_for, format_as_python
        reg_aliases: dict[str, tuple[str, ...]] = {}
        wf, metadata, requirements, tid, reg_inputs = _build_workflow_for(path)
    except Exception as exc:
        if shape != "authored" and not manual_included:
            row.build = "fail"
            row.note = f"parse_for_emit_failed: {type(exc).__name__}: {exc}"
            return (row, None, original_api)
        wf = original_workflow
        metadata = dict(getattr(original_workflow, "metadata", {}) or {})
        metadata.setdefault("ready_template", template_id)
        metadata.setdefault("capability", metadata.get("task") or "unknown")
        req_obj = getattr(original_workflow, "requirements", None)
        requirements = {
            "models": list(getattr(req_obj, "models", []) or []),
            "custom_nodes": list(getattr(req_obj, "custom_nodes", []) or []),
        }
        tid = template_id
        reg_inputs = {
            name: (str(descriptor.node_id), descriptor.field)
            for name, descriptor in getattr(original_workflow, "inputs", {}).items()
            if str(descriptor.node_id) in original_workflow.nodes
            and descriptor.field in original_workflow.nodes[str(descriptor.node_id)].inputs
        }
        # Preserve public-input aliases (e.g. T8 capability-canon renames keep the
        # legacy name as an alias) across regeneration; reg_inputs alone is lossy.
        reg_aliases = {
            name: tuple(getattr(descriptor, "aliases", ()) or ())
            for name, descriptor in getattr(original_workflow, "inputs", {}).items()
            if getattr(descriptor, "aliases", ())
        }

    raw_workflow = _load_source_workflow(metadata)
    if _subgraph_definition_count(raw_workflow) == 1:
        try:
            from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api

            source_path = _source_workflow_path(metadata)
            api = normalize_to_api(raw_workflow, use_comfy_converter=False)
            wf = convert_to_vibe_format(
                api,
                source_path=str(source_path or path),
                workflow_id=template_id,
            )
        except Exception as exc:
            row.note = "; ".join(
                part for part in (row.note, f"source_workflow_rebuild_failed: {type(exc).__name__}: {exc}") if part
            )

    # Apply override if present.
    override = _load_override(path)

    try:
        emitted = format_as_python(
            wf,
            ready_metadata=metadata,
            ready_requirements=requirements,
            template_id=tid,
            registered_inputs=reg_inputs,
            registered_aliases=reg_aliases,
            apply_overrides=override,
            raw_workflow=raw_workflow,
        )
        row.build = "ok"
    except Exception as exc:
        row.build = "fail"
        row.note = f"emit_failed: {type(exc).__name__}: {exc}"
        return (row, None, original_api)

    # Sanity-check by exec'ing the emitted code in an isolated namespace.
    try:
        ns: dict[str, Any] = {"__file__": str(path)}
        compile(emitted, str(path) + " (emitted)", "exec")
        exec(emitted, ns)  # noqa: S102 - generated code under our control
        new_workflow = ns["build"]()
        from vibecomfy.workflow import VibeWorkflow as _VW
        if not isinstance(new_workflow, _VW):
            raise RuntimeError("build() did not return VibeWorkflow")
        report = new_workflow.validate()
        row.validate = "ok" if report.ok else "fail"
        if not report.ok:
            row.diffs.extend(f"validate_issue: {issue.code}: {issue.message}" for issue in report.issues)
    except Exception as exc:
        row.validate = "fail"
        row.note = f"exec_failed: {type(exc).__name__}: {exc}"
        return (row, emitted, original_api)

    # All emitted previews must be canonical-equal to the original compiled
    # workflow before dry-run/write accepts them. The canonical comparator
    # absorbs id renumbering while preserving topology and literal kwargs.
    try:
        from vibecomfy.porting.parity import compile_equivalent
        new_api = new_workflow.compile("api")
        ok, diffs = compile_equivalent(original_api, new_api)
        if not ok and _materialized_subgraphs_replace_uuid_nodes(original_api, new_api):
            ok = True
            diffs = []
        row.roundtrip = "ok" if ok else "fail"
        if not ok:
            row.diffs.extend(diffs[:10])
    except Exception as exc:
        row.roundtrip = "fail"
        row.note = f"roundtrip_failed: {type(exc).__name__}: {exc}"

    return (row, emitted, original_api)


def _materialized_subgraphs_replace_uuid_nodes(original_api: dict | None, new_api: dict | None) -> bool:
    if not isinstance(original_api, dict) or not isinstance(new_api, dict):
        return False
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    original_uuids = {
        str(node.get("class_type"))
        for node in original_api.values()
        if isinstance(node, dict) and uuid_re.fullmatch(str(node.get("class_type", "")))
    }
    if not original_uuids:
        return False
    new_uuids = {
        str(node.get("class_type"))
        for node in new_api.values()
        if isinstance(node, dict) and uuid_re.fullmatch(str(node.get("class_type", "")))
    }
    return original_uuids.isdisjoint(new_uuids)


def _write_emitted(path: Path, text: str, *, dry_run: bool, include_manual: bool = False) -> Path:
    """Write emitted text. Dry-run goes to out/converted/, --write uses atomic temp+replace.

    Shared safety gates (Sprint 1): manual-template refusal, atomic replace.
    Validation is already performed by ``_convert_template()`` before this call.
    """
    if dry_run:
        rel = path.relative_to(READY_ROOT)
        out = OUT_PREVIEW_ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return out

    # Refuse to write outside READY_ROOT.
    resolved = path.resolve()
    if READY_ROOT.resolve() not in resolved.parents:
        raise RuntimeError(f"refusing to write outside READY_ROOT: {resolved}")

    # Shared manual-refusal gate — refuse before any write work.
    if include_manual and _first_line_template_marker(path) == "manual":
        pass
    else:
        _check_manual_refusal(path)

    # Atomic write: temp file in target directory, validate, then replace.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".vibecomfy-convert-{path.name}.tmp"
    try:
        tmp_path.write_text(text, encoding="utf-8")
        # Quick sanity: the temp file must be syntactically valid Python.
        compile(text, str(path) + " (emitted)", "exec")
        # Atomic replace — on most filesystems this is a rename.
        tmp_path.replace(path)
    except Exception:
        # Clean up temp file on any failure.
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return path


def _print_grid(rows: list[Row]) -> None:
    headers = ("template_id", "shape", "parse", "build", "validate", "roundtrip", "snapshot")
    width = max((len(r.template_id) for r in rows), default=10) + 2
    fmt = f"{{:<{width}}} {{:<10}} {{:<6}} {{:<6}} {{:<8}} {{:<14}} {{:<8}}"
    print(fmt.format(*headers))
    print("-" * (width + 60))
    for r in rows:
        print(fmt.format(r.template_id, r.shape, r.parse, r.build, r.validate, r.roundtrip, r.snapshot))
        if r.note:
            print(f"    note: {r.note}")
        for diff in r.diffs[:5]:
            print(f"    diff: {diff}")


# --- snapshot regen ----------------------------------------------------------


SNAPSHOT_IDS = (
    "image/z_image",
    "image/flux2_klein_4b_t2i",
    "image/flux2_klein_9b_gguf_t2i",
    "edit/qwen_image_edit",
    "edit/flux2_klein_4b_image_edit_distilled",
    "video/wan_t2v",
    "video/wan_i2v",
    "video/ltx2_3_t2v",
    "video/ltx2_3_i2v",
)


def _regenerate_snapshots() -> None:
    from vibecomfy.registry.ready import workflow_from_ready
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    for template_id in SNAPSHOT_IDS:
        wf = workflow_from_ready(template_id)
        api = wf.compile("api")
        snap_name = template_id.rsplit("/", 1)[-1]
        (SNAPSHOT_ROOT / f"{snap_name}.api.json").write_text(
            json.dumps(api, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        from vibecomfy.porting.parity import class_type_counter, widget_value_counter
        ct = class_type_counter(api)
        wv = widget_value_counter(api)
        (SNAPSHOT_ROOT / f"{snap_name}.class_types.json").write_text(
            json.dumps(sorted(ct.elements()), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (SNAPSHOT_ROOT / f"{snap_name}.widget_values.json").write_text(
            json.dumps(sorted([list(k) + [v] for k, v in wv.items()]), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"snapshot regenerated: {template_id} ({len(api)} nodes)")


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true")
    group.add_argument("--template", type=str, help="template id (e.g. image/z_image)")
    group.add_argument("--category", type=str, choices=("image", "video", "edit", "audio"))
    group.add_argument("--regenerate-snapshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--include-manual",
        action="store_true",
        help="Explicit one-time v2.6 migration override for first-line manual templates.",
    )
    args = parser.parse_args(argv)

    _bootstrap_comfy_runtime()

    if args.regenerate_snapshots:
        _regenerate_snapshots()
        return 0

    paths: list[Path] = []
    if args.template:
        candidate = (READY_ROOT / f"{args.template}.py").resolve()
        if not candidate.exists():
            print(f"not found: {candidate}", file=sys.stderr)
            return 2
        paths.append(candidate)
    elif args.category:
        cat_dir = READY_ROOT / args.category
        paths = [
            p for p in sorted(cat_dir.rglob("*.py"))
            if p.name != "__init__.py" and not p.name.startswith("_")
        ]
    else:
        paths = _enumerate_templates()

    rows: list[Row] = []
    converted = 0
    from vibecomfy.workflow_context import active_workflow, unbind_workflow

    for path in paths:
        try:
            row, emitted, _ = _convert_template(path, include_manual=args.include_manual)
        finally:
            # The converter exec's template build() directly (an unguarded
            # build path); a build that raises before finalize() leaks the
            # eager new_workflow() binding and poisons the next template's
            # new_workflow() with a nested-context error. Release it per row.
            unbind_workflow(active_workflow())
        rows.append(row)
        if emitted is None:
            continue
        # Write only if validate.ok and (legacy ⇒ roundtrip ok or skipped).
        gated_ok = (
            row.validate == "ok"
            and (row.roundtrip in ("ok", "skip", "skip-authored"))
        )
        if not gated_ok:
            continue
        if args.dry_run:
            _write_emitted(path, emitted, dry_run=True)
            converted += 1
        elif args.write:
            _write_emitted(path, emitted, dry_run=False, include_manual=args.include_manual)
            converted += 1

    _print_grid(rows)
    for r in rows:
        print(f"{r.template_id}: roundtrip={r.roundtrip}")

    total = sum(1 for r in rows if r.shape in ("legacy", "authored"))
    print()
    print(f"Converted {converted}/{total} (validate ok + roundtrip pass for LEGACY)")
    failures = [r for r in rows if r.validate == "fail" or r.roundtrip == "fail" or r.parse == "fail" or r.build == "fail"]
    if failures:
        print(f"Failures: {len(failures)}")
        for r in failures:
            print(f"  {r.template_id}: shape={r.shape} parse={r.parse} build={r.build} validate={r.validate} roundtrip={r.roundtrip}")
            if r.note:
                print(f"    note: {r.note}")
            for d in r.diffs[:3]:
                print(f"    diff: {d}")
    hard_failures = [
        r for r in rows
        if r.validate == "fail" or r.parse == "fail" or r.build == "fail" or (args.write and r.roundtrip == "fail")
    ]
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    sys.exit(main())
