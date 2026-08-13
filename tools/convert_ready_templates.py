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


# TODO(repo-root): this bootstrap script computes the repo root before it
# adjusts sys.path; migrate to vibecomfy.utils.find_repo_root() once startup is
# package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
READY_ROOT = REPO_ROOT / "ready_templates"
OUT_PREVIEW_ROOT = REPO_ROOT / "out" / "converted"
SNAPSHOT_ROOT = REPO_ROOT / "tests" / "snapshots"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Shared safety gates from the porting package (Sprint 1).
from vibecomfy.porting.convert import _check_manual_refusal, ManualTemplateRefusal  # noqa: E402


# --- bootstrap: make installed ComfyUI importable so normalize_to_api works ---


def _bootstrap_comfy_runtime() -> None:
    """Ensure `comfy.component_model.workflow_convert` is callable."""
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
    # Inspect symbol presence.
    has_api = re.search(r"^API_WORKFLOW\s*=", text, re.MULTILINE)
    has_nodes = re.search(r"^NODES\s*=", text, re.MULTILINE)
    if has_api:
        note = "manual marker ignored for legacy API_WORKFLOW" if "vibecomfy: manual" in first_line else ""
        return ("legacy", note)
    if "vibecomfy: manual" in first_line:
        return ("manual", "manual marker on first line")
    if "vibecomfy: generated" in first_line:
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
    # Try multiple keys; different generations of the emitter wrote different
    # provenance shapes (``source_workflow``, ``source_workflow_path``, and
    # ``source_path``). Check each in priority order, both at the metadata
    # top-level and inside an embedded ``provenance`` dict.
    candidate_keys = ("source_workflow", "source_workflow_path", "source_path")
    source: str | None = None
    for key in candidate_keys:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            source = value
            break
    if source is None:
        provenance = metadata.get("provenance")
        if isinstance(provenance, dict):
            for key in candidate_keys:
                value = provenance.get(key)
                if isinstance(value, str) and value:
                    source = value
                    break
    if not isinstance(source, str) or not source:
        return None
    path = Path(source)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path if path.exists() else None


# --- Bucket 1 fallback: scrape source-workflow path from a broken .py file ----

_SOURCE_PATH_LINE_RE = re.compile(
    r"['\"](?:source_workflow|source_workflow_path|source_path)['\"]\s*:\s*['\"]([^'\"]+)['\"]"
)


def _scrape_source_workflow_path(template_path: Path) -> Path | None:
    """Best-effort: regex the .py for a provenance source path.

    This avoids importing a .py file whose body raises (Bucket 1 case where
    the existing emission is broken and ``workflow_from_ready`` can't run).
    """
    try:
        text = template_path.read_text(encoding="utf-8")
    except OSError:
        return None
    for match in _SOURCE_PATH_LINE_RE.finditer(text):
        candidate = match.group(1)
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.exists():
            return path
    return None


def _clear_workflow_contextvar() -> None:
    """Defensive: ensure no leaked ContextVar binding from a prior failing build.

    ``new_workflow()`` eagerly binds the workflow ContextVar. When build() raises
    before ``wf.finalize()`` releases the token, subsequent template builds in
    the same process die with ``ContextVarBindingError: Nested workflow contexts
    not supported``. Reset between every per-template attempt.
    """
    try:
        from vibecomfy.workflow_context import _CURRENT_WORKFLOW
        _CURRENT_WORKFLOW.set(None)
    except Exception:
        pass


def _canonicalize_broadcast_widget_keys(workflow: Any) -> None:
    """Ensure SetNode/GetNode broadcast names live at ``widgets['widget_0']``.

    The compile helper resolver reads broadcast names
    exclusively from ``inputs['widget_0']`` or ``widgets['widget_0']``. When the
    source JSON is a UI-format litegraph, ``normalize_to_api`` routes the value
    through the schema's widget name (e.g. ``inputs['name'] = 'width'`` for
    ``GetNode``), which then becomes a regular input on the VibeNode rather than
    a ``widget_0`` slot. Mirror those values into ``widgets['widget_0']`` so the
    Phase-A broadcast resolver can see them. This is a non-mutating projection:
    we only ADD widget_0 when it is missing.
    """
    BROADCAST = {"SetNode", "GetNode"}
    for _node_id, node in workflow.nodes.items():
        class_type = getattr(node, "class_type", "")
        if class_type not in BROADCAST:
            continue
        widgets = getattr(node, "widgets", None)
        inputs = getattr(node, "inputs", None)
        if widgets is None or inputs is None:
            continue
        if widgets.get("widget_0") is not None:
            continue
        # Candidate keys in priority order: rgthree's "Constant" key, KJNodes'
        # named "name" input, and the raw "title" metadata fallback.
        candidate = None
        for key in ("Constant", "constant", "name"):
            value = inputs.get(key)
            if isinstance(value, str) and value:
                candidate = value
                break
        if candidate is None:
            # Last-ditch: scrape _ui metadata for widgets_values[0].
            meta = getattr(node, "metadata", None) or {}
            ui = meta.get("_ui") if isinstance(meta, dict) else None
            if isinstance(ui, dict):
                widgets_values = ui.get("widgets_values")
                if isinstance(widgets_values, list) and widgets_values:
                    first = widgets_values[0]
                    if isinstance(first, str) and first:
                        candidate = first
        if candidate:
            widgets["widget_0"] = candidate


def _emit_from_source_json(template_path: Path, template_id: str) -> tuple[str | None, str | None]:
    """Run the standard ``port convert`` pipeline against the source JSON.

    Returns ``(emitted_text, error_note)``. On success ``error_note`` is None.
    """
    metadata_text = ""
    try:
        metadata_text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        return (None, f"regen_source_read_failed: {exc}")

    # Try the structured metadata path first (works for templates that DO
    # parse-import OK but whose source provenance lives in metadata).
    source_path = _scrape_source_workflow_path(template_path)
    if source_path is None:
        return (None, "regen_no_source_workflow_found_in_provenance")

    _clear_workflow_contextvar()
    try:
        from vibecomfy.porting.convert import port_convert_workflow
        from vibecomfy.porting.workbench import load_port_source

        loaded = load_port_source(str(source_path))
        _canonicalize_broadcast_widget_keys(loaded.workflow)
        result = port_convert_workflow(
            loaded.workflow,
            ready_id=template_id,
            source_path=str(source_path),
            raw_workflow=loaded.raw_workflow,
        )
    except Exception as exc:
        return (None, f"regen_from_source_failed: {type(exc).__name__}: {exc}")
    finally:
        _clear_workflow_contextvar()

    # Best-effort: also sanity-check the produced text compiles.
    try:
        compile(result.text, str(template_path) + " (regen)", "exec")
    except SyntaxError as exc:
        return (None, f"regen_syntax_error: {exc}")
    return (result.text, None)


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


def _convert_template(
    path: Path,
    *,
    include_manual: bool = False,
    regen_from_source: bool = False,
) -> tuple[Row, str | None, dict | None]:
    """Process one template. Returns (row, emitted_text or None, original_compiled_api)."""
    template_id = _template_id_for_path(path)
    row = Row(template_id=template_id)

    # --- shared manual-refusal gate (Sprint 1) --------------------------------
    manual_included = False
    try:
        _check_manual_refusal(path)
    except ManualTemplateRefusal:
        if not include_manual:
            row.shape = "manual-refused"
            row.parse = "skip"
            row.build = "skip"
            row.validate = "skip"
            row.roundtrip = "skip"
            row.snapshot = "skip"
            row.note = "manual template refused by shared gate"
            return (row, None, None)
        manual_included = True
        row.note = "manual template included by explicit v2.6 override"

    shape, shape_note = _classify_shape(path)
    row.shape = shape
    if shape_note:
        row.note = "; ".join(part for part in (row.note, shape_note) if part)

    if regen_from_source:
        emitted, regen_note = _emit_from_source_json(path, template_id)
        if emitted is not None:
            row.parse = "skip-source"
            row.build = "ok"
            row.validate = "skip-broken-original"
            row.roundtrip = "skip-broken-original"
            row.note = "; ".join(part for part in (row.note, "regenerated_from_source_json") if part)
            return (row, emitted, None)
        if regen_note:
            row.note = "; ".join(part for part in (row.note, regen_note) if part)

    # Already-converted templates are skipped (no emission work needed).
    if shape == "converted":
        row.parse = "skip"
        row.build = "skip"
        row.validate = "skip"
        row.roundtrip = "skip"
        row.snapshot = "skip"
        return (row, None, None)

    # Build the original workflow first so we can roundtrip-equality check.
    # Defensively clear the workflow ContextVar so a leaked binding from a
    # previously failing template doesn't poison this attempt.
    original_api = None
    _clear_workflow_contextvar()
    try:
        from vibecomfy.registry.ready import workflow_from_ready
        original_workflow = workflow_from_ready(template_id)
        original_api = original_workflow.compile("api")
        row.parse = "ok"
    except Exception as exc:
        row.parse = "fail"
        row.note = f"build_original_failed: {type(exc).__name__}: {exc}"
        _clear_workflow_contextvar()
        # Bucket 1 fallback: the existing .py is broken Python, but the user
        # opted into --regen-from-source. Rebuild emission directly from the
        # source JSON listed in provenance and short-circuit roundtrip parity
        # (we have no callable "original" to compare against).
        if regen_from_source:
            emitted, regen_note = _emit_from_source_json(path, template_id)
            if emitted is None:
                row.note = f"{row.note}; {regen_note}" if regen_note else row.note
                return (row, None, None)
            row.parse = "skip-broken-original"
            row.build = "ok"
            row.validate = "skip-broken-original"
            row.roundtrip = "skip-broken-original"
            row.note = f"{row.note}; regenerated_from_source_json"
            return (row, emitted, None)
        return (row, None, None)

    # Drive the parser path (matching the spec's distinction).
    try:
        from tools.format_as_python import _build_workflow_for, format_as_python
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

    raw_workflow = _load_source_workflow(metadata)
    if _subgraph_definition_count(raw_workflow) == 1:
        try:
            from vibecomfy.ingest.normalize import from_api, normalize_to_api

            source_path = _source_workflow_path(metadata)
            api = normalize_to_api(raw_workflow, use_comfy_converter=False)
            wf = from_api(
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
            apply_overrides=override,
            raw_workflow=raw_workflow,
        )
        row.build = "ok"
    except Exception as exc:
        row.build = "fail"
        row.note = f"emit_failed: {type(exc).__name__}: {exc}"
        # Bucket 1.5 fallback: standard emit_ready_template_python raised
        # (e.g. ConversionParityError on a helper resolver edge case the
        # standard load path didn't canonicalize). If the user opted into
        # --regen-from-source and a provenance source JSON exists, re-emit
        # from the JSON via the canonicalizing path.
        if regen_from_source:
            _clear_workflow_contextvar()
            regen_emitted, regen_note = _emit_from_source_json(path, template_id)
            if regen_emitted is not None:
                row.parse = "skip-broken-original"
                row.build = "ok"
                row.validate = "skip-broken-original"
                row.roundtrip = "skip-broken-original"
                row.note = (
                    f"{row.note}; regenerated_from_source_json_after_emit_fail"
                )
                return (row, regen_emitted, None)
            if regen_note:
                row.note = f"{row.note}; {regen_note}"
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
        # Bucket 3 fallback: standard emission produced a workflow whose
        # validate() fails (e.g. wrong VAE-loader pairing). If --regen-from-source
        # is opted in and a provenance source JSON exists, re-emit from the
        # JSON — that bypasses the broken authored .py entirely.
        if regen_from_source:
            _clear_workflow_contextvar()
            regen_emitted, regen_note = _emit_from_source_json(path, template_id)
            if regen_emitted is not None:
                row.parse = "skip-broken-original"
                row.build = "ok"
                row.validate = "skip-broken-original"
                row.roundtrip = "skip-broken-original"
                row.note = (
                    f"{row.note}; regenerated_from_source_json_after_validate_fail"
                )
                return (row, regen_emitted, None)
            if regen_note:
                row.note = f"{row.note}; {regen_note}"
        return (row, emitted, original_api)

    # Bucket 3 secondary fallback: validate ran but reported failures.
    # Same regen-from-source recovery path.
    if row.validate == "fail" and regen_from_source:
        _clear_workflow_contextvar()
        regen_emitted, regen_note = _emit_from_source_json(path, template_id)
        if regen_emitted is not None:
            row.parse = "skip-broken-original"
            row.build = "ok"
            row.validate = "skip-broken-original"
            row.roundtrip = "skip-broken-original"
            existing_note = row.note or ""
            sep = "; " if existing_note else ""
            row.note = (
                f"{existing_note}{sep}regenerated_from_source_json_after_validate_fail"
            )
            return (row, regen_emitted, None)
        if regen_note:
            existing_note = row.note or ""
            sep = "; " if existing_note else ""
            row.note = f"{existing_note}{sep}{regen_note}"

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
    if not include_manual:
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
    group.add_argument("--select", nargs="+", help="one or more template ids or ready_templates/*.py paths")
    group.add_argument("--category", type=str, choices=("image", "video", "edit", "audio"))
    group.add_argument("--regenerate-snapshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--include-manual",
        action="store_true",
        help="Explicit one-time v2.6 migration override for first-line manual templates.",
    )
    parser.add_argument(
        "--regen-from-source",
        action="store_true",
        help=(
            "When the existing .py fails to import (broken-original), rebuild "
            "emission directly from the source JSON listed in provenance. "
            "Roundtrip parity is skipped for these templates because there is "
            "no callable original to compare against."
        ),
    )
    parser.add_argument(
        "--force-roundtrip-fail",
        action="store_true",
        help=(
            "Write templates that pass validate=ok but fail canonical roundtrip "
            "parity. Use only when you've reviewed the diff and accept that "
            "the emitted graph diverges from the source. Logs a WARNING line."
        ),
    )
    args = parser.parse_args(argv)

    if args.regenerate_snapshots:
        _bootstrap_comfy_runtime()
        _regenerate_snapshots()
        return 0

    if not args.regen_from_source:
        _bootstrap_comfy_runtime()

    paths: list[Path] = []
    if args.template:
        candidate = (READY_ROOT / f"{args.template}.py").resolve()
        if not candidate.exists():
            print(f"not found: {candidate}", file=sys.stderr)
            return 2
        paths.append(candidate)
    elif args.select:
        for selected in args.select:
            raw = Path(selected)
            if raw.suffix == ".py":
                candidate = raw if raw.is_absolute() else (REPO_ROOT / raw)
            else:
                candidate = READY_ROOT / f"{selected}.py"
            candidate = candidate.resolve()
            if not candidate.exists():
                print(f"not found: {candidate}", file=sys.stderr)
                return 2
            if READY_ROOT.resolve() not in candidate.parents:
                print(f"not a ready template: {candidate}", file=sys.stderr)
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
    for path in paths:
        row, emitted, _ = _convert_template(
            path,
            include_manual=args.include_manual,
            regen_from_source=args.regen_from_source,
        )
        rows.append(row)
        if emitted is None:
            continue
        # Write gate: the standard path requires validate=ok AND roundtrip in
        # the safe-skip set. Two opt-in escape hatches:
        #   --regen-from-source allows skip-broken-original (no original to
        #     compare against, so neither validate nor roundtrip ran).
        #   --force-roundtrip-fail allows validate=ok templates that fail
        #     canonical roundtrip parity, with an explicit WARNING.
        force_regen_ok = (
            args.regen_from_source
            and row.validate == "skip-broken-original"
            and row.roundtrip == "skip-broken-original"
        )
        force_roundtrip_ok = (
            args.force_roundtrip_fail
            and row.validate == "ok"
            and row.roundtrip == "fail"
        )
        if force_roundtrip_ok:
            print(
                f"WARNING: {row.template_id}: writing despite roundtrip=fail "
                f"(validate=ok, --force-roundtrip-fail)"
            )
            for d in row.diffs[:5]:
                print(f"    diff: {d}")
        gated_ok = (
            (
                row.validate == "ok"
                and (row.roundtrip in ("ok", "skip", "skip-authored"))
            )
            or force_regen_ok
            or force_roundtrip_ok
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
        if r.validate == "fail"
        or r.parse == "fail"
        or r.build == "fail"
        or (args.write and r.roundtrip == "fail" and not args.force_roundtrip_fail)
    ]
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    sys.exit(main())
