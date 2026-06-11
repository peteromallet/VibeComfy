"""Render a typed-wrapper Python module from a list of ``ClassSpec``.

Output shape — illustrated by one class:

    class KSampler:
        \"\"\"Typed wrapper for the ComfyUI node class ``KSampler``.

        Auto-generated from /object_info; do not edit by hand. Re-run
        ``vibecomfy nodes generate-wrappers <pack>`` to refresh.
        \"\"\"

        CLASS_TYPE = "KSampler"
        OUTPUTS = ("LATENT",)
        OUTPUT_TYPES = ("LATENT",)

        @staticmethod
        def add(
            wf: "VibeWorkflow",
            *,
            model: "Handle",
            positive: "Handle",
            negative: "Handle",
            latent_image: "Handle",
            seed: int = 0,
            steps: int = 20,
            cfg: float = 8.0,
            sampler_name: str = "euler",
            scheduler: str = "normal",
            denoise: float = 1.0,
        ) -> "_NodeBuilder":
            \"\"\"Add a ``KSampler`` node and return the builder.

            Source: object_info snapshot ComfyUI-LTXVideo@runpod-snapshot.json sha256:abc123
            \"\"\"
            return wf.node(
                "KSampler",
                model=model,
                positive=positive,
                negative=negative,
                latent_image=latent_image,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler_name=sampler_name,
                scheduler=scheduler,
                denoise=denoise,
            )

The class is a namespace; ``.add(wf, ...)`` returns the same ``_NodeBuilder``
that ``wf.node("KSampler", ...)`` would. Callers can use:

    sampler = KSampler.add(wf, model=unet.out(0), positive=pos.out(0), ...)
    sampler.out(0)  # -> Handle

Each pack lives in its own module ``vibecomfy/nodes/<slug>.py``. The
``__init__.py`` of ``vibecomfy.nodes`` is left unchanged by this codegen —
callers explicitly import the pack module they want (consistent with the
"explicit registries" rule in CLAUDE.md).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from vibecomfy.porting.wrapper_discovery import ClassSpec, InputFieldSpec


# Generator version — bump when the rendered shape changes in a way that
# would break byte-identical determinism across runs.
GENERATOR_VERSION = "1.0.0"

# Socket types ComfyUI treats as "linked from another node" rather than
# widgets. These map to ``Handle`` in the wrapper signature.
LINK_SOCKET_TYPES: frozenset[str] = frozenset(
    {
        "MODEL", "CLIP", "VAE", "LATENT", "IMAGE", "MASK", "CONDITIONING",
        "CONTROL_NET", "STYLE_MODEL", "CLIP_VISION", "CLIP_VISION_OUTPUT",
        "AUDIO", "VIDEO", "NOISE", "SIGMAS", "SAMPLER", "GUIDER", "GLIGEN",
        "PHOTOMAKER", "LORA_MODEL", "WAN_VIDEO_MODEL", "WAN_VIDEO_VAE",
        "WANVIDEOTEXTEMBEDS", "WANVIDEOBLOCKSWAPARGS", "WANVIDEOLORA",
        "FLOAT_LIST", "INT_LIST", "STRING_LIST", "MASK_LIST", "IMAGE_LIST",
        "FLUX_GUIDANCE", "DEPTH_MODEL", "FACEANALYSIS", "INSIGHTFACE",
        "UPSCALE_MODEL", "BBOX_DETECTOR", "SEGS", "SEGM_DETECTOR",
        "DETECTOR", "RGTHREE_CONTEXT", "LTXV_LATENT_GUIDE", "TRACK_DATA",
        "STRING_LIST_DICT",
    }
)

# Scalar widget types and their Python annotation.
SCALAR_TYPE_TO_ANNOTATION: dict[str, str] = {
    "INT": "int",
    "FLOAT": "float",
    "STRING": "str",
    "BOOLEAN": "bool",
    "BOOL": "bool",
}

_HEADER_GENERATED_MARKER = "# vibecomfy:generated"


@dataclass(frozen=True, slots=True)
class RenderResult:
    """The output of rendering one pack."""

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
    """Render one pack to a Python module string and return the result.

    ``out_dir`` is the directory under which ``<slug>.py`` will live. The file
    is not written by this function — call ``RenderResult.write()`` or use
    the higher-level CLI helper to persist it.
    """
    timestamp = timestamp or _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
    module_name = _slug_to_module_name(pack_slug)
    module_path = out_dir / f"{module_name}.py"

    classes_text, skipped = _render_classes(specs)
    provenance = _provenance_line(specs)
    source_input = _provenance_fingerprint_input(pack_slug, specs)
    source_sha = hashlib.sha256(source_input.encode("utf-8")).hexdigest()

    header = _render_header(
        pack_slug=pack_slug,
        provenance=provenance,
        source_sha256=source_sha,
        timestamp=timestamp,
        class_count=len(specs) - len(skipped),
    )
    body = header + "\n" + _RENDERED_IMPORTS + "\n\n" + classes_text
    if not body.endswith("\n"):
        body += "\n"

    return RenderResult(
        pack_slug=pack_slug,
        module_path=module_path,
        source_text=body,
        source_sha256=source_sha,
        class_count=len(specs) - len(skipped),
        skipped_classes=tuple(skipped),
    )


def parse_generated_header(source_text: str) -> dict[str, str] | None:
    """Extract the generated-header key/value pairs from a wrapper module.

    Returns ``None`` if the file does not look like a generated wrapper.
    """
    head = source_text.splitlines()[:25]
    if not any(_HEADER_GENERATED_MARKER in line for line in head):
        return None
    out: dict[str, str] = {}
    for line in head:
        m = re.match(r"#\s*([\w.]+):\s*(.+?)\s*$", line.strip())
        if m and line.startswith("#"):
            key = m.group(1)
            if key in {"source_sha256", "source", "pack", "generator_version", "generated_at", "classes"}:
                out[key] = m.group(2)
    return out or None


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


_RENDERED_IMPORTS = (
    "from __future__ import annotations\n"
    "\n"
    "from typing import TYPE_CHECKING, Any\n"
    "\n"
    "if TYPE_CHECKING:  # pragma: no cover\n"
    "    from vibecomfy.handles import Handle  # noqa: F401\n"
    "    from vibecomfy.workflow import VibeWorkflow, _NodeBuilder  # noqa: F401\n"
)


def _render_header(
    *,
    pack_slug: str,
    provenance: str,
    source_sha256: str,
    timestamp: _dt.datetime,
    class_count: int,
) -> str:
    iso = timestamp.replace(microsecond=0).isoformat()
    lines = [
        f"{_HEADER_GENERATED_MARKER}",
        f"# pack: {pack_slug}",
        f"# source: {provenance}",
        f"# source_sha256: {source_sha256}",
        f"# generator_version: {GENERATOR_VERSION}",
        f"# generated_at: {iso}",
        f"# classes: {class_count}",
        "#",
        "# DO NOT EDIT — regenerate with:",
        f"#   vibecomfy nodes generate-wrappers {pack_slug}",
        "",
        '"""Auto-generated typed wrappers for the ' + pack_slug + ' custom-node pack.',
        "",
        "Each class in this module wraps one ComfyUI node class. The wrappers",
        "are thin builders around ``VibeWorkflow.node()`` — calling",
        "``ClassName.add(wf, ...)`` is equivalent to ``wf.node('ClassType', ...)``",
        "but gives editors type-checked kwargs and a place to attach docstrings.",
        '"""',
    ]
    return "\n".join(lines) + "\n"


def _render_classes(specs: Sequence[ClassSpec]) -> tuple[str, list[str]]:
    rendered: list[str] = []
    skipped: list[str] = []
    used_names: set[str] = set()
    for spec in sorted(specs, key=lambda s: s.class_type):
        py_name = _class_name_for(spec.class_type)
        if not py_name or py_name in used_names:
            skipped.append(spec.class_type)
            continue
        used_names.add(py_name)
        rendered.append(_render_one_class(spec, py_name))
    return "\n\n".join(rendered) + ("\n" if rendered else ""), skipped


def _render_one_class(spec: ClassSpec, py_name: str) -> str:
    lines: list[str] = []
    lines.append(f"class {py_name}:")
    docstring = _class_docstring(spec)
    lines.extend(_indent(docstring, 4))
    lines.append("")
    lines.append(f"    CLASS_TYPE = {spec.class_type!r}")
    lines.append(f"    OUTPUTS: tuple[str, ...] = {_repr_tuple(spec.outputs)}")
    lines.append(f"    OUTPUT_TYPES: tuple[str, ...] = {_repr_tuple(spec.output_types)}")
    lines.append("")
    lines.append("    @staticmethod")
    sig_lines = _render_add_signature(spec)
    lines.extend(sig_lines)
    lines.append(f"        \"\"\"Add a ``{spec.class_type}`` node to ``wf`` and return the builder.")
    lines.append("")
    lines.append(f"        Source: {spec.source_provenance}")
    lines.append("        \"\"\"")
    lines.extend(_render_add_body(spec))
    return "\n".join(lines)


def _class_docstring(spec: ClassSpec) -> str:
    parts: list[str] = []
    parts.append(f'"""Typed wrapper for the ComfyUI node class ``{spec.class_type}``.')
    if spec.display_name and spec.display_name != spec.class_type:
        parts.append("")
        parts.append(f"Display name: {spec.display_name}")
    if spec.category:
        parts.append("")
        parts.append(f"Category: {spec.category}")
    if spec.description:
        # First non-empty line only — descriptions can be long and we want
        # docstrings to stay scannable.
        first = next((line for line in spec.description.splitlines() if line.strip()), "")
        if first:
            parts.append("")
            parts.append(first.strip())
    parts.append('"""')
    return "\n".join(parts)


def _render_add_signature(spec: ClassSpec) -> list[str]:
    fields = _sorted_fields(spec.inputs)
    lines = ["    def add("]
    lines.append("        wf: \"VibeWorkflow\",")
    if fields:
        lines.append("        *,")
        for field in fields:
            lines.append(f"        {_signature_param(field)},")
    lines.append("    ) -> \"_NodeBuilder\":")
    return lines


def _render_add_body(spec: ClassSpec) -> list[str]:
    fields = _sorted_fields(spec.inputs)
    if not fields:
        return [f"        return wf.node({spec.class_type!r})"]
    # Partition fields into identifier-safe source names (emit as
    # ``source=py_name``) and non-identifier source names (need ``**{...}``
    # spread because Python kwargs forbid dots / spaces in identifiers).
    identifier_fields: list[InputFieldSpec] = []
    odd_fields: list[InputFieldSpec] = []
    for field in fields:
        if _is_python_identifier(field.name):
            identifier_fields.append(field)
        else:
            odd_fields.append(field)
    lines = [f"        return wf.node("]
    lines.append(f"            {spec.class_type!r},")
    for field in identifier_fields:
        py_name = _safe_param_name(field.name)
        if py_name == field.name:
            lines.append(f"            {field.name}={py_name},")
        else:
            lines.append(f"            {field.name}={py_name},")
    if odd_fields:
        lines.append("            **{")
        for field in odd_fields:
            py_name = _safe_param_name(field.name)
            lines.append(f"                {field.name!r}: {py_name},")
        lines.append("            },")
    lines.append("        )")
    return lines


def _is_python_identifier(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def _signature_param(field: InputFieldSpec) -> str:
    py_name = _safe_param_name(field.name)
    annotation = _annotation_for(field)
    if field.has_default or _is_link_type(field.type) or not field.required:
        default = _default_repr(field)
        return f"{py_name}: {annotation} = {default}"
    return f"{py_name}: {annotation}"


def _annotation_for(field: InputFieldSpec) -> str:
    if _is_link_type(field.type):
        return '"Handle"'
    if field.type in SCALAR_TYPE_TO_ANNOTATION:
        return SCALAR_TYPE_TO_ANNOTATION[field.type]
    if field.type == "COMBO":
        return "str"
    if field.type == "UNKNOWN":
        return "Any"
    # Everything else — socket types not in the link-set — is also a Handle.
    return '"Handle"'


def _default_repr(field: InputFieldSpec) -> str:
    if _is_link_type(field.type) and not field.has_default:
        return "None"
    if not field.has_default:
        if field.type in SCALAR_TYPE_TO_ANNOTATION or field.type == "COMBO":
            if field.type == "INT":
                return "0"
            if field.type == "FLOAT":
                return "0.0"
            if field.type in {"BOOLEAN", "BOOL"}:
                return "False"
            return "\"\""
        return "None"
    return _python_literal(field.default)


def _python_literal(value: Any) -> str:
    # Use json.dumps for stable, deterministic formatting of primitives.
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    # Lists/dicts of primitives — dump deterministically.
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return repr(value)


def _is_link_type(type_name: str) -> bool:
    if type_name in LINK_SOCKET_TYPES:
        return True
    # Heuristic: ALL_CAPS_WITH_UNDERSCORES is conventionally a socket type.
    return type_name.isupper() and "_" in type_name and type_name not in SCALAR_TYPE_TO_ANNOTATION


def _sorted_fields(inputs: dict[str, InputFieldSpec]) -> list[InputFieldSpec]:
    # Required link sockets first, then required scalars, then optional in
    # name order. Within each tier names are sorted to guarantee determinism.
    def tier(f: InputFieldSpec) -> int:
        if f.required and _is_link_type(f.type):
            return 0
        if f.required:
            return 1
        return 2

    return sorted(inputs.values(), key=lambda f: (tier(f), f.name))


def _class_name_for(class_type: str) -> str | None:
    """Convert a ComfyUI class_type string to a valid Python identifier.

    Strips parenthesized suffixes (`Foo (rgthree)` -> `Foo_rgthree`) and
    replaces non-identifier characters with underscores.
    """
    cleaned = re.sub(r"[\s\-/]+", "_", class_type)
    cleaned = re.sub(r"[\(\)\[\]\{\}]", "", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        return None
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def _safe_param_name(field_name: str) -> str:
    py = re.sub(r"[^0-9A-Za-z_]+", "_", field_name)
    py = re.sub(r"_+", "_", py).strip("_")
    if not py:
        py = "value"
    if py[0].isdigit():
        py = f"_{py}"
    if keyword.iskeyword(py):
        py = f"{py}_"
    return py


def _slug_to_module_name(pack_slug: str) -> str:
    name = re.sub(r"[^0-9A-Za-z_]+", "_", pack_slug.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "pack"


def _repr_tuple(values: Sequence[str]) -> str:
    if not values:
        return "()"
    if len(values) == 1:
        return f"({values[0]!r},)"
    return "(" + ", ".join(repr(v) for v in values) + ")"


def _indent(text: str, level: int) -> list[str]:
    pad = " " * level
    return [pad + line if line else "" for line in text.splitlines()]


def _provenance_line(specs: Sequence[ClassSpec]) -> str:
    if not specs:
        return "no specs"
    unique = sorted({spec.source_provenance for spec in specs})
    return unique[0] if len(unique) == 1 else "; ".join(unique)


def _provenance_fingerprint_input(pack_slug: str, specs: Sequence[ClassSpec]) -> str:
    """Stable input to the source_sha256 header field.

    Hashes the pack slug + the canonical JSON-serialised list of specs. This
    makes the header SHA change iff the input data changed, regardless of
    which discovery source produced it.
    """
    blob = {
        "pack_slug": pack_slug,
        "generator_version": GENERATOR_VERSION,
        "classes": [
            {
                "class_type": s.class_type,
                "outputs": list(s.outputs),
                "output_types": list(s.output_types),
                "is_output_node": s.is_output_node,
                "category": s.category,
                "display_name": s.display_name,
                "inputs": {
                    name: {
                        "type": f.type,
                        "required": f.required,
                        "has_default": f.has_default,
                        "default": f.default if f.has_default else None,
                        "options": list(f.options) if f.options else None,
                    }
                    for name, f in sorted(s.inputs.items())
                },
            }
            for s in sorted(specs, key=lambda x: x.class_type)
        ],
    }
    return json.dumps(blob, sort_keys=True)


# ---------------------------------------------------------------------------
# WIDGET_SCHEMA emitter (auxiliary — ties to Sweep 2 widget gap-fill)
# ---------------------------------------------------------------------------


def render_widget_schema(specs: Sequence[ClassSpec]) -> str:
    """Render ``WIDGET_SCHEMA`` dict literal entries from specs.

    The output is a chunk of Python that can be concatenated into the
    ``WIDGET_SCHEMA`` dict in ``vibecomfy/porting/widget_schema.py``. Each
    entry lists the named widget fields in declaration order so positional
    ``widget_N`` aliases can be resolved without manual curation.
    """
    lines: list[str] = []
    for spec in sorted(specs, key=lambda s: s.class_type):
        # Only emit entries for classes with any scalar widget (non-link)
        # inputs — pure link classes already have everything they need.
        widget_fields = [
            f for f in spec.inputs.values()
            if not _is_link_type(f.type)
        ]
        if not widget_fields:
            continue
        names = [f.name for f in widget_fields]
        provenance = spec.source_provenance.replace('"', '\\"')
        lines.append(f"    # source: {provenance}")
        lines.append(f"    {spec.class_type!r}: {{")
        lines.append("        \"widget_order\": (")
        for n in names:
            lines.append(f"            {n!r},")
        lines.append("        ),")
        lines.append("    },")
    return "\n".join(lines)


__all__ = [
    "GENERATOR_VERSION",
    "RenderResult",
    "parse_generated_header",
    "render_pack",
    "render_widget_schema",
]
