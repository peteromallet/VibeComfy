from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cache import CACHE_METADATA_KEY
from .parsing import schema_from_object_info
from .types import NodeSchema, SchemaIndexError


class ObjectInfoFileSchemaProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._object_info: dict[str, Any] | None = None
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            self._schemas = schemas_from_object_info(self.object_info())
        return self._schemas

    def object_info(self) -> dict[str, Any]:
        if self._object_info is None:
            self._object_info = load_object_info_file(self.path)
        return self._object_info


def load_object_info_file(path: str | Path) -> dict[str, Any]:
    object_info_path = Path(path)
    try:
        data = json.loads(object_info_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SchemaIndexError(object_info_path, exc) from exc
    return data if isinstance(data, dict) else {}


def schemas_from_object_info(object_info: dict[str, Any]) -> dict[str, NodeSchema]:
    return {
        class_type: schema_from_object_info(class_type, info)
        for class_type, info in object_info.items()
        if class_type != CACHE_METADATA_KEY and isinstance(info, dict)
    }
