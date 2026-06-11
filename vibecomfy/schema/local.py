from __future__ import annotations

import json
from pathlib import Path

from .parsing import schema_from_index_row
from .types import NodeSchema, SchemaIndexError


class LocalSchemaProvider:
    def __init__(self, index_path: str | Path = "node_index.json") -> None:
        self.index_path = Path(index_path)
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            self._schemas = self._load()
        return self._schemas

    def _load(self) -> dict[str, NodeSchema]:
        if not self.index_path.exists():
            return {}
        try:
            rows = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SchemaIndexError(self.index_path, exc) from exc
        if isinstance(rows, dict):
            rows = list(rows.values())
        if not isinstance(rows, list):
            return {}
        schemas: dict[str, NodeSchema] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            schema = schema_from_index_row(row)
            if schema is not None:
                schemas[schema.class_type] = schema
        return schemas
