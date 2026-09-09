"""Deterministic renderer for the canonical public node-function ABI."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .discovery import ClassSpec, InputFieldSpec

GENERATOR_VERSION = "2.0.0"
LINK_SOCKET_TYPES: frozenset[str] = frozenset(
    {
        "MODEL", "CLIP", "VAE", "LATENT", "IMAGE", "MASK", "CONDITIONING",
        "CONTROL_NET", "STYLE_MODEL", "CLIP_VISION", "CLIP_VISION_OUTPUT",
        "AUDIO", "VIDEO", "NOISE", "SIGMAS", "SAMPLER", "GUIDER", "GLIGEN",
        "PHOTOMAKER", "LORA_MODEL", "WAN_VIDEO_MODEL", "WAN_VIDEO_VAE",
        "WANVIDEOTEXTEMBEDS", "WANVIDEOBLOCKSWAPARGS", "WANVIDEOLORA",
        "FLOAT_LIST", "INT_LIST", "STRING_LIST", "MASK_LIST", "IMAGE_LIST",
        "FLUX_GUIDANCE", "DEPTH_MODEL", "FACEANALYSIS", "INSIGHTFACE",
        "UPSCALE_MODEL", "BBOX_DETECTOR", "SEGS", "SEGM_DETECTOR", "DETECTOR",
        "RGTHREE_CONTEXT", "LTXV_LATENT_GUIDE", "TRACK_DATA", "STRING_LIST_DICT",
    }
)
SCALAR_TYPE_TO_ANNOTATION: dict[str, str] = {
    "INT": "int", "FLOAT": "float", "STRING": "str", "BOOLEAN": "bool", "BOOL": "bool",
}
_HEADER_GENERATED_MARKER = "# vibecomfy:generated"


@dataclass(frozen=True, slots=True)
class RenderResult:
    pack_slug: str
    module_path: Path
    source_text: str
    source_sha256: str
    class_count: int
    skipped_classes: tuple[str, ...]


def render_pack(
    pack_slug: str,
    specs: Sequence[ClassSpec],
    *,
    out_dir: Path,
    timestamp: _dt.datetime | None = None,
) -> RenderResult:
    """Render one deterministic module; ``timestamp`` is API-compatible but ignored."""
    del timestamp
    module_path = out_dir / f"{_slug_to_module_name(pack_slug)}.py"
    source_input = _provenance_fingerprint_input(pack_slug, specs)
    source_sha = hashlib.sha256(source_input.encode("utf-8")).hexdigest()
    functions, exports, class_types = _render_functions(specs)
    header = _render_header(
        pack_slug=pack_slug,
        provenance=_provenance_line(specs),
        source_sha256=source_sha,
        class_count=len(specs),
    )
    body = header + "\n" + _RENDERED_IMPORTS + "\n\n" + functions
    body += f"__all__ = {exports!r}\n"
    body += f"__vibecomfy_class_types__ = {class_types!r}\n"
    if not body.endswith("\n"):
        body += "\n"
    return RenderResult(pack_slug, module_path, body, source_sha, len(specs), ())


def render_pack_stub(pack_slug: str, specs: Sequence[ClassSpec], *, out_dir: Path) -> str:
    """Render the matching ``.pyi`` artifact from the same ``ClassSpec`` input."""
    del out_dir
    records = _function_records(specs)
    source_sha = hashlib.sha256(_provenance_fingerprint_input(pack_slug, specs).encode("utf-8")).hexdigest()
    lines = [
        _HEADER_GENERATED_MARKER,
        f"# pack: {pack_slug}",
        f"# source: {_provenance_line(specs)}",
        f"# source_sha256: {source_sha}",
        f"# generator_version: {GENERATOR_VERSION}",
        "# generated_at: 1970-01-01T00:00:00+00:00",
        f"# classes: {len(specs)}",
        "",
        '"""Type stubs for generated public node wrappers."""',
        "from __future__ import annotations",
        "",
        "from typing import Any, Literal",
        "",
        "from vibecomfy.workflow import VibeWorkflow",
        "",
        "class _Omitted: ...",
        "_UNSET: _Omitted",
        "",
    ]
    for name, spec in records:
        lines.extend([f"def {name}(", "    *args: VibeWorkflow,", "    _id: str | None = ...,"])
        lines.extend(f"    {p['name']}: {_annotation_for(p)} = ...," for p in _parameter_specs(spec))
        lines.extend(["    pass_raw: bool = ...,", "    **_extras: Any,", ") -> Any: ...", ""])
    lines.append(f"__all__ = {[name for name, _ in records]!r}")
    return "\n".join(lines) + "\n"


def parse_generated_header(source_text: str) -> dict[str, str] | None:
    head = source_text.splitlines()[:25]
    if not any(_HEADER_GENERATED_MARKER in line for line in head):
        return None
    out: dict[str, str] = {}
    for line in head:
        match = re.match(r"#\s*([\w.]+):\s*(.+?)\s*$", line.strip())
        if match and line.startswith("#"):
            key = match.group(1)
            if key in {"source_sha256", "source", "pack", "generator_version", "generated_at", "classes"}:
                out[key] = match.group(2)
    return out or None


def prune_stale_wrappers(out_dir: Path, *, live_modules: Sequence[str]) -> tuple[Path, ...]:
    """Remove stale canonical generated pairs while preserving hand-authored files."""
    live = set(live_modules) | {"__init__", "index"}
    removed: list[Path] = []
    for path in sorted(out_dir.glob("*")):
        if path.suffix not in {".py", ".pyi"} or path.stem in live or not path.is_file():
            continue
        if parse_generated_header(path.read_text(encoding="utf-8")) is None:
            continue
        path.unlink()
        removed.append(path)
    return tuple(removed)


_RENDERED_IMPORTS = (
    "from __future__ import annotations\n\n"
    "from typing import Any, Literal\n\n"
    "from vibecomfy.templates import _current_workflow_or_raise, node\n"
    "from vibecomfy.workflow import VibeWorkflow\n\n"
    "class _Omitted:\n    pass\n\n"
    "_UNSET = _Omitted()"
)


def _render_header(*, pack_slug: str, provenance: str, source_sha256: str, class_count: int) -> str:
    lines = [
        _HEADER_GENERATED_MARKER,
        f"# pack: {pack_slug}",
        f"# source: {provenance}",
        f"# source_sha256: {source_sha256}",
        f"# generator_version: {GENERATOR_VERSION}",
        "# generated_at: 1970-01-01T00:00:00+00:00",
        f"# classes: {class_count}",
        "#",
        "# DO NOT EDIT — regenerate with:",
        f"#   vibecomfy nodes generate-wrappers {pack_slug}",
        "",
        f'"""Auto-generated public wrappers for the {pack_slug} custom-node pack.',
        "",
        "Each function wraps one ComfyUI node class and delegates through the",
        "public ``vibecomfy.templates.node`` ABI.",
        '"""',
    ]
    return "\n".join(lines) + "\n"


def _function_records(specs: Sequence[ClassSpec]) -> list[tuple[str, ClassSpec]]:
    used: set[str] = set()
    records: list[tuple[str, ClassSpec]] = []
    for spec in sorted(specs, key=lambda item: item.class_type):
        base = _class_name_for(spec.class_type) or "Node"
        name = _unique_name(base, used)
        used.add(name)
        records.append((name, spec))
    return sorted(records, key=lambda item: (item[0], item[1].class_type))


def _render_functions(specs: Sequence[ClassSpec]) -> tuple[str, list[str], dict[str, str]]:
    records = _function_records(specs)
    text = "\n\n".join(_render_one_function(spec, name) for name, spec in records)
    return text + ("\n\n" if text else ""), [name for name, _ in records], {name: spec.class_type for name, spec in records}


def _render_one_function(spec: ClassSpec, name: str) -> str:
    params = _parameter_specs(spec)
    lines = [f"def {name}(", "    *args: VibeWorkflow,", "    _id: str | None = None,"]
    lines.extend(f"    {p['name']}: {_annotation_for(p)} = _UNSET," for p in params)
    lines.extend(["    pass_raw: bool = False,", "    **_extras: Any,", ") -> Any:"])
    lines.extend(_indent(_function_docstring(spec), 4))
    lines.extend([
        "    if len(args) > 1:",
        f"        raise TypeError(f\"{name}() takes at most 1 positional argument, got {{len(args)}}\")",
        "    wf = args[0] if args else _current_workflow_or_raise()",
        "    _kwargs: dict[str, Any] = {}",
    ])
    for p in params:
        lines.extend([f"    if {p['name']} is not _UNSET:", f"        _kwargs[{p['original']!r}] = {p['name']}"])
    lines.extend(["    _kwargs.update(_extras)", f"    return node(wf, {spec.class_type!r}, _id, pass_raw=pass_raw, **_kwargs)"])
    return "\n".join(lines)


def _function_docstring(spec: ClassSpec) -> str:
    lines = [f'"""Public wrapper for the ComfyUI node ``{spec.class_type}``.']
    display = _clean_doc_value(spec.display_name)
    if display and display != spec.class_type:
        display_lines = display.splitlines()
        lines.extend(["", f"Display name: {display_lines[0]}", *display_lines[1:]])
    if spec.category:
        lines.extend(["", f"Category: {spec.category}"])
    if spec.description:
        first = next((line.strip() for line in spec.description.splitlines() if line.strip()), "")
        if first:
            lines.extend(["", first])
    returns = ", ".join(str(value).strip() for value in spec.outputs).strip() or "None"
    lines.extend(["", f"Returns: {returns}", "", f"Source: {spec.source_provenance}", '"""'])
    return "\n".join(lines)


def _clean_doc_value(value: str | None) -> str:
    if not value:
        return ""
    return "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()


def _parameter_specs(spec: ClassSpec) -> list[dict[str, Any]]:
    # ABI names are occupied by the workflow/id/control parameters and must
    # remain available for arbitrary Comfy input keys via a unique suffix.
    used: set[str] = {"args", "_id", "pass_raw", "_extras"}
    result: list[dict[str, Any]] = []
    for field in _sorted_fields(spec.inputs):
        base = _safe_param_name(field.name)
        name = _unique_name(base, used)
        used.add(name)
        result.append({"name": name, "original": field.name, "field": field})
    return result


def _annotation_for(param: dict[str, Any]) -> str:
    field: InputFieldSpec = param["field"]
    if field.type == "COMBO" and field.options and all(isinstance(value, str) for value in field.options):
        return f"Literal[{', '.join(repr(value) for value in field.options)}] | _Omitted"
    return f"{SCALAR_TYPE_TO_ANNOTATION.get(field.type, 'Any')} | _Omitted"


def _sorted_fields(inputs: dict[str, InputFieldSpec]) -> list[InputFieldSpec]:
    def tier(field: InputFieldSpec) -> int:
        return 0 if field.required and field.type in LINK_SOCKET_TYPES else (1 if field.required else 2)
    return sorted(inputs.values(), key=lambda field: (tier(field), field.name))


def _class_name_for(class_type: str) -> str:
    cleaned = re.sub(r"[\s\-/]+", "_", class_type)
    cleaned = re.sub(r"[\(\)\[\]\{\}]", "", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_") or "Node"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned += "_"
    return cleaned


def _safe_param_name(field_name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", field_name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_") or "value"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned += "_"
    return cleaned


def _unique_name(value: str, used: set[str]) -> str:
    candidate = value
    index = 2
    while candidate in used:
        candidate = f"{value}_{index}"
        index += 1
    return candidate


def _slug_to_module_name(pack_slug: str) -> str:
    name = re.sub(r"[^0-9A-Za-z_]+", "_", pack_slug.lower())
    return re.sub(r"_+", "_", name).strip("_") or "pack"


def _indent(text: str, level: int) -> list[str]:
    pad = " " * level
    return [pad + line if line else "" for line in text.splitlines()]


def _provenance_line(specs: Sequence[ClassSpec]) -> str:
    if not specs:
        return "no specs"
    values = sorted({spec.source_provenance for spec in specs})
    return values[0] if len(values) == 1 else "; ".join(values)


def _provenance_fingerprint_input(pack_slug: str, specs: Sequence[ClassSpec]) -> str:
    blob = {
        "pack_slug": pack_slug,
        "generator_version": GENERATOR_VERSION,
        "classes": [
            {
                "pack_slug": spec.pack_slug,
                "class_type": spec.class_type,
                "outputs": list(spec.outputs),
                "output_types": list(spec.output_types),
                "is_output_node": spec.is_output_node,
                "category": spec.category,
                "display_name": spec.display_name,
                "description": spec.description,
                "source_provenance": spec.source_provenance,
                "inputs": {
                    name: {
                        "type": field.type,
                        "required": field.required,
                        "default": field.default if field.has_default else None,
                        "has_default": field.has_default,
                        "options": list(field.options) if field.options is not None else None,
                        "widget_metadata": field.widget_metadata,
                    }
                    for name, field in sorted(spec.inputs.items())
                },
            }
            for spec in sorted(specs, key=lambda item: item.class_type)
        ],
    }
    return json.dumps(blob, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def render_widget_schema(specs: Sequence[ClassSpec]) -> str:
    lines: list[str] = []
    for spec in sorted(specs, key=lambda item: item.class_type):
        fields = [field for field in spec.inputs.values() if field.type not in LINK_SOCKET_TYPES]
        if not fields:
            continue
        lines.append(f"    # source: {spec.source_provenance}")
        lines.append(f"    {spec.class_type!r}: {{")
        lines.append('        "widget_order": (')
        lines.extend(f"            {field.name!r}," for field in fields)
        lines.extend(["        ),", "    },"])
    return "\n".join(lines)


__all__ = ["GENERATOR_VERSION", "RenderResult", "parse_generated_header", "prune_stale_wrappers", "render_pack", "render_pack_stub", "render_widget_schema"]
