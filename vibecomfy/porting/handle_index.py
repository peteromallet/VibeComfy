from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.schema import InputSpec, LocalSchemaProvider, NodeSchema, OutputSpec, schemas_for
from vibecomfy.porting.object_info.consume import get_class, list_classes


@dataclass(frozen=True)
class CompatibleInput:
    class_type: str
    kwarg: str
    required: bool

    def to_json(self) -> dict[str, Any]:
        return {"class": self.class_type, "kwarg": self.kwarg, "required": self.required}


@dataclass(frozen=True)
class CompatibleProducer:
    class_type: str
    output_slot: int
    output_type: str
    output_name: str | None
    feeds_kwarg: str
    feeds_type: str

    def to_json(self) -> dict[str, Any]:
        payload = {
            "class": self.class_type,
            "output_slot": self.output_slot,
            "output_type": self.output_type,
            "feeds_kwarg": self.feeds_kwarg,
            "feeds_type": self.feeds_type,
        }
        if self.output_name:
            payload["output_name"] = self.output_name
        return payload


_CACHE: dict[tuple[str | None, float | None], "HandleCompatibilityIndex"] = {}


class HandleCompatibilityIndex:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self.schemas = schemas
        self.inputs_by_type: dict[str, list[CompatibleInput]] = {}
        self.outputs_by_type: dict[str, list[tuple[str, int, str | None]]] = {}
        for class_type, schema in schemas.items():
            for kwarg, spec in schema.inputs.items():
                if spec.type:
                    self.inputs_by_type.setdefault(_norm_type(spec.type), []).append(
                        CompatibleInput(class_type=class_type, kwarg=kwarg, required=bool(spec.required))
                    )
            for index, output in enumerate(schema.outputs):
                if output.type:
                    self.outputs_by_type.setdefault(_norm_type(output.type), []).append(
                        (class_type, index, output.name)
                    )
        for rows in self.inputs_by_type.values():
            rows.sort(key=lambda item: (item.class_type, item.kwarg))
        for rows in self.outputs_by_type.values():
            rows.sort(key=lambda item: (item[0], item[1], item[2] or ""))

    def consumers_for_type(self, type_name: str) -> list[CompatibleInput]:
        return list(self.inputs_by_type.get(_norm_type(type_name), []))

    def producers_for_class_inputs(self, class_type: str) -> list[CompatibleProducer]:
        target = self.schemas.get(class_type)
        if target is None:
            return []
        rows: list[CompatibleProducer] = []
        for kwarg, spec in target.inputs.items():
            if not spec.type:
                continue
            feed_type = _norm_type(spec.type)
            for producer_class, slot, output_name in self.outputs_by_type.get(feed_type, []):
                rows.append(
                    CompatibleProducer(
                        class_type=producer_class,
                        output_slot=slot,
                        output_type=feed_type,
                        output_name=output_name,
                        feeds_kwarg=kwarg,
                        feeds_type=feed_type,
                    )
                )
        return sorted(rows, key=lambda item: (item.feeds_kwarg, item.class_type, item.output_slot))


def compatibility_index(provider: Any | None = None) -> HandleCompatibilityIndex:
    provider = provider or LocalSchemaProvider()
    cache_path = _provider_cache_path(provider)
    mtime = Path(cache_path).stat().st_mtime if cache_path and Path(cache_path).exists() else None
    key = (cache_path, mtime)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    schemas = _all_schemas(provider)
    index = HandleCompatibilityIndex(schemas)
    _CACHE.clear()
    _CACHE[key] = index
    return index


def _provider_cache_path(provider: Any) -> str | None:
    object_info = getattr(provider, "_object_info", None)
    path = getattr(object_info, "object_info_path", None)
    return str(path) if path is not None else None


def _norm_type(type_name: str) -> str:
    return str(type_name).strip().upper()


def _all_schemas(provider: Any) -> dict[str, NodeSchema]:
    merged: dict[str, NodeSchema] = {}
    local = schemas_for(provider) or {}
    merged.update({k: v for k, v in local.items() if isinstance(v, NodeSchema)})
    for class_type in list_classes():
        if class_type in merged:
            continue
        schema = _schema_from_cached_object_info(class_type)
        if schema is not None:
            merged[class_type] = schema
    return merged


def _schema_from_cached_object_info(class_type: str) -> NodeSchema | None:
    entry = get_class(class_type)
    if not isinstance(entry, dict):
        return None
    inputs: dict[str, InputSpec] = {}
    for group_name, group in (entry.get("inputs") or {}).items():
        if not isinstance(group, dict):
            continue
        for name, raw in group.items():
            inputs[str(name)] = _input_spec(raw, required=group_name == "required")
    outputs = [
        OutputSpec(type=item.get("type"), name=item.get("name"))
        for item in (entry.get("outputs") or [])
        if isinstance(item, dict)
    ]
    return NodeSchema(
        class_type=class_type,
        pack=entry.get("pack"),
        inputs=inputs,
        outputs=outputs,
        source_provider="object_info_cache",
    )


def _input_spec(raw: Any, *, required: bool) -> InputSpec:
    typ = None
    attrs: dict[str, Any] = {}
    choices = None
    if isinstance(raw, (list, tuple)) and raw:
        typ = raw[0]
        if isinstance(typ, list):
            choices = list(typ)
            typ = "CHOICE"
        if len(raw) > 1 and isinstance(raw[1], dict):
            attrs = raw[1]
    elif isinstance(raw, dict):
        typ = raw.get("type")
        attrs = raw
        if isinstance(raw.get("choices"), list):
            choices = list(raw["choices"])
    elif isinstance(raw, str):
        typ = raw
    return InputSpec(
        type=str(typ) if typ is not None else None,
        required=required,
        default=attrs.get("default"),
        choices=choices,
        min=attrs.get("min"),
        max=attrs.get("max"),
    )
