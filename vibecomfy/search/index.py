from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.nodes.index import index_custom_node_examples
from vibecomfy.schema import NodeSchema, RuntimeSchemaProvider, SchemaProvider, get_schema_provider, schemas_for
from vibecomfy.search.aliases import ADAPT_PATTERN_ALIASES, normalize_text, tokenize
from vibecomfy.search.bootstrap import ensure_indexes
from vibecomfy.ingest.workflow_source import load_workflow_source

SearchSource = Literal[
    "object_info",
    "node_index",
    "custom_node_examples",
    "curated",
    "ready_template",
    "source_workflow",
    "external_workflow",
]


@dataclass(frozen=True)
class SearchEntry:
    class_type: str
    pack: str | None = None
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    tasks: tuple[str, ...] = field(default_factory=tuple)
    source: SearchSource = "curated"
    path: str | None = None
    template_id: str | None = None
    source_workflow_path: str | None = None
    source_workflow_available: bool = False
    source_workflow_parseable: bool = False
    adapt_pattern_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SearchWarning:
    source: str
    message: str


def build_search_corpus(
    *,
    auto_sync: bool = False,
    schema_provider: SchemaProvider | None = None,
    warnings: list[SearchWarning] | None = None,
    node_index_path: str | Path = "node_index.json",
    custom_nodes_root: str | Path = "custom_nodes",
    coverage_path: str | Path = "ready_templates/sources/manifests/coverage.json",
    template_index_path: str | Path = "template_index.json",
    workflow_index_path: str | Path = "workflow_index.json",
    external_workflow_index_path: str | Path = "external_workflow_index.json",
) -> list[SearchEntry]:
    ensure_indexes(auto_sync=auto_sync)
    entries: list[SearchEntry] = []
    entries.extend(_object_info_entries(schema_provider, warnings=warnings))
    entries.extend(_node_index_entries(Path(node_index_path)))
    entries.extend(_custom_example_entries(custom_nodes_root))
    entries.extend(_curated_entries(Path(coverage_path)))
    entries.extend(_ready_template_entries(Path(template_index_path)))
    return _dedupe(entries)


def _object_info_entries(schema_provider: SchemaProvider | None, *, warnings: list[SearchWarning] | None = None) -> list[SearchEntry]:
    provider = schema_provider
    if provider is None:
        provider = get_schema_provider("auto")
        if not isinstance(provider, RuntimeSchemaProvider) and provider.__class__.__name__ != "RuntimeSchemaProvider":
            return []
    try:
        schemas = schemas_for(provider)
    except Exception as exc:
        if warnings is not None:
            warnings.append(
                SearchWarning(
                    source="object_info",
                    message=(
                        f"object_info schema discovery failed via {provider.__class__.__name__}: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                )
            )
        return []
    if schemas is None:
        return []
    return [_entry_from_schema(schema) for schema in schemas.values()]


def _entry_from_schema(schema: NodeSchema) -> SearchEntry:
    input_bits = [f"{name}:{spec.type}" if spec.type else name for name, spec in schema.inputs.items()]
    output_bits = [out.type or out.name for out in schema.outputs if out.type or out.name]
    tags = _clean_items([schema.pack, *input_bits, *output_bits])
    description = " ".join(
        part
        for part in [
            f"{schema.class_type} node",
            f"inputs {' '.join(input_bits)}" if input_bits else "",
            f"outputs {' '.join(str(bit) for bit in output_bits)}" if output_bits else "",
        ]
        if part
    )
    return SearchEntry(
        class_type=schema.class_type,
        pack=schema.pack,
        description=description,
        tags=tuple(tags),
        tasks=tuple(_infer_tasks(schema.class_type, tags, description)),
        source="object_info",
        path=None,
    )


def _node_index_entries(path: Path) -> list[SearchEntry]:
    rows = _read_json(path, default=[])
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list):
        return []
    entries: list[SearchEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        class_type = _first_string(row, "class_type", "name", "id", "node", "display_name")
        if not class_type:
            continue
        pack = _first_string(row, "pack", "package", "source", "category")
        path_value = _first_string(row, "path", "file")
        tags = _clean_items(_flatten(row.get("tags")) + _flatten(row.get("inputs")) + [pack])
        description = _description_from_row(row, class_type, tags)
        entries.append(
            SearchEntry(
                class_type=class_type,
                pack=pack,
                description=description,
                tags=tuple(tags),
                tasks=tuple(_infer_tasks(class_type, tags, description)),
                source="node_index",
                path=path_value,
            )
        )
    return entries


def _custom_example_entries(root: str | Path) -> list[SearchEntry]:
    entries: list[SearchEntry] = []
    for row in index_custom_node_examples(root):
        class_type = _first_string(row, "id", "class_type", "name")
        if not class_type:
            continue
        pack = _first_string(row, "pack", "package", "source")
        path_value = _first_string(row, "path")
        if not _is_python_path(path_value):
            continue
        tags = _clean_items([pack, "example_workflow", Path(path_value).stem if path_value else class_type])
        description = f"{class_type} custom-node example workflow"
        entries.append(
            SearchEntry(
                class_type=class_type,
                pack=pack,
                description=description,
                tags=tuple(tags),
                tasks=tuple(_infer_tasks(class_type, tags, description)),
                source="custom_node_examples",
                path=path_value,
            )
        )
    return entries


def _curated_entries(path: Path) -> list[SearchEntry]:
    data = _read_json(path, default={})
    rows = data.get("workflows", []) if isinstance(data, dict) else []
    entries: list[SearchEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        workflow_id = _first_string(row, "id")
        if not workflow_id:
            continue
        task = _first_string(row, "task")
        model_family = _first_string(row, "model_family")
        media = _first_string(row, "media")
        path_value = _first_string(row, "path")
        if not _is_python_path(path_value):
            continue
        source = _first_string(row, "source")
        tags = _clean_items([task, model_family, media, source, row.get("coverage_tier")])
        description = " ".join(
            str(part)
            for part in [workflow_id, task, model_family, media, row.get("note")]
            if part
        )
        entries.append(
            SearchEntry(
                class_type=workflow_id,
                pack=model_family,
                description=description,
                tags=tuple(tags),
                tasks=tuple(_unique_strings([task, *_infer_tasks(workflow_id, tags, description)])),
                source="curated",
                path=path_value,
            )
        )
    return entries


def _ready_template_entries(path: Path) -> list[SearchEntry]:
    data = _read_json(path, default={})
    rows = _row_list(data, "templates")
    if not isinstance(rows, list):
        return []
    coverage_rows = _coverage_rows(path.parent / "ready_templates/sources/manifests/coverage.json")
    entries: list[SearchEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        template_id = _first_string(row, "id", "template_id", "ready_template")
        if not template_id:
            continue
        path_value = _first_string(row, "path", "ready_template_path", "template_path")
        if not _is_python_path(path_value):
            continue
        source_workflow = _source_workflow_for_template(row, template_id, coverage_rows)
        capability = _first_string(row, "capability", "media_type", "media", "task")
        coverage_tier = _first_string(row, "coverage_tier")
        readiness = _first_string(row, "readiness_class", "readiness")
        public_inputs = _named_items(row.get("public_inputs"))
        public_outputs = _named_items(row.get("public_outputs"))
        custom_nodes = _flatten(row.get("custom_nodes"))
        model_count = row.get("model_count", row.get("models_count"))
        source_available = _path_exists(source_workflow)
        source_parseable = _workflow_source_parseable(source_workflow) if source_available else False
        adapt_pattern_keys = _infer_adapt_patterns(
            template_id,
            [
                path_value,
                source_workflow,
                capability,
                coverage_tier,
                readiness,
                *public_inputs,
                *public_outputs,
                *custom_nodes,
            ],
            "",
        )
        tags = _clean_items([
            "workflow",
            "ready_template",
            "template",
            "graph_backed" if source_parseable else None,
            "parseable_source" if source_parseable else None,
            template_id,
            Path(path_value).stem if path_value else None,
            Path(source_workflow).stem if source_workflow else None,
            capability,
            coverage_tier,
            readiness,
            *adapt_pattern_keys,
            *public_inputs,
            *public_outputs,
            *custom_nodes,
        ])
        description = " ".join(
            str(part)
            for part in [
                f"{template_id} ready template workflow",
                f"capability {capability}" if capability else "",
                f"inputs {', '.join(public_inputs[:6])}" if public_inputs else "",
                f"outputs {', '.join(public_outputs[:4])}" if public_outputs else "",
                f"custom nodes {', '.join(str(node) for node in custom_nodes[:5])}" if custom_nodes else "",
                f"{model_count} model{'s' if model_count != 1 else ''}" if isinstance(model_count, int) else "",
                f"template path {path_value}" if path_value else "",
                f"converted source workflow {Path(source_workflow).stem}" if source_workflow else "",
                f"source workflow path {source_workflow}" if source_workflow else "",
                "parseable source workflow available" if source_parseable else "",
                f"adapt patterns {', '.join(adapt_pattern_keys)}" if adapt_pattern_keys else "",
                readiness,
                coverage_tier,
            ]
            if part
        )
        entries.append(
            SearchEntry(
                class_type=template_id,
                pack=capability,
                description=description,
                tags=tuple(tags),
                tasks=tuple(_infer_tasks(template_id, tags, description)),
                source="ready_template",
                path=path_value,
                template_id=template_id,
                source_workflow_path=source_workflow,
                source_workflow_available=source_available,
                source_workflow_parseable=source_parseable,
                adapt_pattern_keys=tuple(adapt_pattern_keys),
            )
        )
    return entries


def _workflow_index_entries(path: Path, *, source_label: Literal["source_workflow", "external_workflow"]) -> list[SearchEntry]:
    rows = _row_list(_read_json(path, default=[]), "workflows")
    entries: list[SearchEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        workflow_id = _first_string(row, "id", "name", "workflow_id", "template_id")
        if not workflow_id:
            continue
        path_value = _first_string(row, "path", "file", "workflow_path", "source_workflow", "source_json")
        media_type = _first_string(row, "media_type", "media", "capability", "task")
        package = _first_string(row, "package", "pack", "source_package")
        source = _first_string(row, "source")
        public_inputs = _named_items(row.get("public_inputs"))
        public_outputs = _named_items(row.get("public_outputs"))
        custom_nodes = _flatten(row.get("custom_nodes"))
        model_count = row.get("model_count", row.get("models_count"))
        tags = _clean_items([
            "workflow",
            "workflow_json",
            "source_workflow" if source_label == "source_workflow" else "external_workflow",
            workflow_id,
            Path(path_value).stem if path_value else None,
            media_type,
            package,
            source,
            *public_inputs,
            *public_outputs,
            *custom_nodes,
        ])
        description = " ".join(
            str(part)
            for part in [
                f"{workflow_id} ComfyUI workflow JSON",
                f"media {media_type}" if media_type else "",
                f"inputs {', '.join(public_inputs[:6])}" if public_inputs else "",
                f"outputs {', '.join(public_outputs[:4])}" if public_outputs else "",
                f"custom nodes {', '.join(str(node) for node in custom_nodes[:5])}" if custom_nodes else "",
                f"{model_count} model{'s' if model_count != 1 else ''}" if isinstance(model_count, int) else "",
                f"package {package}" if package else "",
                f"path {path_value}" if path_value else "",
            ]
            if part
        )
        entries.append(
            SearchEntry(
                class_type=workflow_id,
                pack=package or media_type,
                description=description,
                tags=tuple(tags),
                tasks=tuple(_infer_tasks(workflow_id, tags, description)),
                source=source_label,
                path=path_value,
            )
        )
    return entries


def _description_from_row(row: dict[str, Any], class_type: str, tags: list[str]) -> str:
    explicit = _first_string(row, "description", "title", "display_name")
    if explicit:
        return explicit
    return " ".join(str(part) for part in [class_type, *tags] if part)


def _infer_tasks(class_type: str, tags: list[str] | tuple[str, ...], description: str) -> list[str]:
    haystack = " ".join([class_type, description, *tags]).lower()
    tasks: list[str] = []
    patterns = {
        "i2v": ("i2v", "image to video", "image_to_video"),
        "t2v": ("t2v", "text to video", "text_to_video"),
        "t2i": ("t2i", "text to image", "text_to_image"),
        "inpaint": ("inpaint", "inpainting"),
        "outpaint": ("outpaint", "outpainting"),
        "controlnet": ("controlnet", "control net"),
    }
    for task, needles in patterns.items():
        if any(needle in haystack for needle in needles):
            tasks.append(task)
    return tasks


def _infer_adapt_patterns(
    class_type: str,
    tags: list[Any] | tuple[Any, ...],
    description: str,
) -> list[str]:
    haystack = " ".join(str(part) for part in [class_type, description, *tags] if part)
    normalized = normalize_text(haystack)
    tokens = tokenize(haystack)
    patterns: list[str] = []
    for key, aliases in ADAPT_PATTERN_ALIASES.items():
        canonical_phrase = key.replace("_", " ")
        exact_terms = {canonical_phrase, *(normalize_text(alias) for alias in aliases)}
        if key in tokens or any(term and term in normalized for term in exact_terms):
            patterns.append(key)
    return patterns


def _dedupe(entries: list[SearchEntry]) -> list[SearchEntry]:
    seen: set[tuple[str, SearchSource, str | None]] = set()
    unique: list[SearchEntry] = []
    for entry in entries:
        key = (entry.class_type, entry.source, entry.path)
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _coverage_rows(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path, default={})
    rows = data.get("workflows", []) if isinstance(data, dict) else data
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _source_workflow_for_template(
    row: dict[str, Any],
    template_id: str,
    coverage_rows: list[dict[str, Any]],
) -> str | None:
    source_workflow = _first_string(row, "source_workflow", "source_workflow_path", "source_json")
    if _is_json_path(source_workflow):
        return source_workflow
    short_id = template_id.rsplit("/", 1)[-1]
    for coverage in coverage_rows:
        candidates = {
            str(coverage.get("id") or ""),
            str(coverage.get("ready_template") or ""),
            str(coverage.get("template_id") or ""),
        }
        media = coverage.get("media")
        workflow_id = coverage.get("id")
        if isinstance(media, str) and isinstance(workflow_id, str):
            candidates.add(f"{media}/{workflow_id}")
        if template_id in candidates or short_id in candidates:
            path = _first_string(coverage, "path", "source_workflow", "workflow_path")
            return path if _is_json_path(path) else None
    return None


def _path_exists(path: str | None) -> bool:
    return bool(path) and Path(path).exists()


def _workflow_source_parseable(path: str | None) -> bool:
    if not _is_json_path(path):
        return False
    return load_workflow_source(path).ok


def _is_json_path(path: str | None) -> bool:
    return bool(path) and Path(path).suffix.lower() == ".json"


def _is_python_path(path: str | None) -> bool:
    return bool(path) and Path(path).suffix.lower() == ".py"


def _row_list(data: Any, preferred_key: str) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    rows = data.get(preferred_key)
    if isinstance(rows, list):
        return rows
    for key in ("items", "entries", "results", "workflows", "templates"):
        rows = data.get(key)
        if isinstance(rows, list):
            return rows
    return [value for value in data.values() if isinstance(value, dict)]


def _first_string(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.keys()) + [item for val in value.values() for item in _flatten(val)]
    if isinstance(value, list):
        return [item for val in value for item in _flatten(val)]
    return [value] if isinstance(value, (str, int, float)) else []


def _named_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _clean_items(values: list[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        normalized = value.strip()
        if normalized and normalized not in items:
            items.append(normalized)
            items.extend(token for token in tokenize(normalized) if token not in items)
    return items


def _unique_strings(values: list[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in items:
            items.append(value)
    return items
