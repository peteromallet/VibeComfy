from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.nodes.index import index_custom_node_examples
from vibecomfy.schema import NodeSchema, RuntimeSchemaProvider, SchemaProvider, get_schema_provider, schemas_for
from vibecomfy.search.aliases import tokenize
from vibecomfy.search.bootstrap import ensure_indexes

SearchSource = Literal["object_info", "node_index", "custom_node_examples", "curated"]


@dataclass(frozen=True)
class SearchEntry:
    class_type: str
    pack: str | None = None
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    tasks: tuple[str, ...] = field(default_factory=tuple)
    source: SearchSource = "curated"
    path: str | None = None


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
    coverage_path: str | Path = "workflow_corpus/manifests/coverage.json",
) -> list[SearchEntry]:
    ensure_indexes(auto_sync=auto_sync)
    entries: list[SearchEntry] = []
    entries.extend(_object_info_entries(schema_provider, warnings=warnings))
    entries.extend(_node_index_entries(Path(node_index_path)))
    entries.extend(_custom_example_entries(custom_nodes_root))
    entries.extend(_curated_entries(Path(coverage_path)))
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
