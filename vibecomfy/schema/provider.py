from __future__ import annotations

import asyncio
import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from vibecomfy.comfy_command import has_comfyui_runtime
from vibecomfy.runtime.client import ComfyClient
from vibecomfy.runtime.server import comfy_server

from .cache import (
    CACHE_METADATA_KEY,
    load_object_info_cache,
    object_info_cache_candidates,
    object_info_cache_path,
    runtime_fingerprint,
    validate_object_info_cache,
    write_object_info_cache,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InputSpec:
    type: str | None = None
    required: bool = False
    default: Any = None
    choices: list[Any] | None = None
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class OutputSpec:
    type: str | None = None
    name: str | None = None


@dataclass
class SchemaSourceInfo:
    """Provenance metadata describing where a schema came from and with what confidence.

    This is intentionally a plain (non-frozen) dataclass so callers can
    mutate it incrementally while merging evidence from multiple providers.
    """

    provider_name: str = "unknown"
    source_path: str | None = None
    cache_path: str | None = None
    server_url: str | None = None
    package: str | None = None
    version: str | None = None
    hash: str | None = None
    confidence: float = 1.0
    conflicts: list[str] = field(default_factory=list)
    ignored_evidence: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "source_path": self.source_path,
            "cache_path": self.cache_path,
            "server_url": self.server_url,
            "package": self.package,
            "version": self.version,
            "hash": self.hash,
            "confidence": self.confidence,
            "conflicts": list(self.conflicts),
            "ignored_evidence": list(self.ignored_evidence),
        }


@dataclass(frozen=True)
class SourceScanWarning:
    code: str
    message: str
    class_type: str | None = None
    path: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "class_type": self.class_type,
            "path": self.path,
        }


@dataclass(frozen=True)
class NodeSchema:
    class_type: str
    pack: str | None
    inputs: dict[str, InputSpec]
    outputs: list[OutputSpec]
    # -- provenance fields (defaults so existing code works unchanged) ------
    source_provider: str = "unknown"
    source_path: str | None = None
    source_cache_path: str | None = None
    source_server_url: str | None = None
    source_package: str | None = None
    source_version: str | None = None
    source_hash: str | None = None
    confidence: float = 1.0
    conflicts: tuple[str, ...] = ()
    ignored_evidence: tuple[str, ...] = ()


class SchemaIndexError(ValueError):
    def __init__(self, path: Path, cause: Exception) -> None:
        super().__init__(f"{path} could not be read: {type(cause).__name__}: {cause}")
        self.path = path
        self.cause = cause


@runtime_checkable
class SchemaProvider(Protocol):
    def get_schema(self, class_type: str) -> NodeSchema | None: ...


def schema_for(provider: object | None, class_type: str) -> object | None:
    builtin = _builtin_schema(class_type)
    if builtin is not None:
        return builtin
    if provider is None:
        return None
    getter = getattr(provider, "get_schema", None) or getattr(provider, "get", None)
    if not callable(getter):
        return None
    return getter(class_type)


def _builtin_schema(class_type: str) -> NodeSchema | None:
    if class_type == "vibecomfy.exec":
        from vibecomfy.comfy_nodes.exec_node import EXEC_SLOT_COUNT

        inputs = {
            "source": InputSpec("STRING", required=True),
            "io": InputSpec("JSON", required=True),
        }
        inputs.update({f"in_{index}": InputSpec("*", required=False) for index in range(EXEC_SLOT_COUNT)})
        return NodeSchema(
            class_type="vibecomfy.exec",
            pack="vibecomfy",
            inputs=inputs,
            outputs=[OutputSpec("*", f"out_{index}") for index in range(EXEC_SLOT_COUNT)],
            source_provider="vibecomfy_builtin",
            source_package="vibecomfy",
            confidence=1.0,
        )
    if class_type == "vibecomfy.code":
        return NodeSchema(
            class_type="vibecomfy.code",
            pack="vibecomfy",
            inputs={
                "value": InputSpec("*", required=False),
                "runtime_backed": InputSpec("BOOLEAN", required=False),
                "runtime_contract_version": InputSpec("STRING", required=False),
                "execution_mode": InputSpec("STRING", required=False),
                "timeout_ms": InputSpec("INT", required=False),
                "max_source_bytes": InputSpec("INT", required=False),
                "allowed_builtins": InputSpec("JSON", required=False),
                "redaction_policy": InputSpec("JSON", required=False),
                "policy_version": InputSpec("STRING", required=False),
                "passthrough_on_non_json": InputSpec("BOOLEAN", required=False),
                "vibecomfy_uid": InputSpec("STRING", required=False),
                "kind": InputSpec("STRING", required=False),
                "io": InputSpec("DICT", required=False),
                "source": InputSpec("STRING", required=False),
                "spec": InputSpec("STRING", required=False),
            },
            outputs=[OutputSpec("*", "value")],
            source_provider="vibecomfy_builtin",
            source_package="vibecomfy",
            confidence=1.0,
        )
    if class_type == "vibecomfy.loop":
        return NodeSchema(
            class_type="vibecomfy.loop",
            pack="vibecomfy",
            inputs={"value": InputSpec("*", required=False)},
            outputs=[OutputSpec("*", "value")],
            source_provider="vibecomfy_builtin",
            source_package="vibecomfy",
            confidence=1.0,
        )
    return None


def schema_registry_empty(provider: object | None) -> bool:
    try:
        schemas = schemas_for(provider)
    except Exception:
        return False
    return schemas is not None and len(schemas) == 0


def schemas_for(provider: object | None) -> dict[str, object] | None:
    schemas = getattr(provider, "schemas", None)
    if not callable(schemas):
        return None
    return schemas()


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
            schema = _schema_from_index_row(row)
            if schema is not None:
                schemas[schema.class_type] = schema
        return schemas


class SourceSchemaProvider:
    """Best-effort INPUT_TYPES reader for installed custom-node source trees."""

    def __init__(
        self,
        roots: list[str | Path] | None = None,
        *,
        max_roots: int = 8,
        max_files_per_root: int = 2_000,
        max_total_files: int = 5_000,
    ) -> None:
        self.scan_warnings: list[SourceScanWarning] = []
        self.max_roots = max(0, max_roots)
        self.max_files_per_root = max(0, max_files_per_root)
        self.max_total_files = max(0, max_total_files)
        raw_roots = _default_source_roots() if roots is None else roots
        self.roots = self._bounded_roots([Path(root) for root in raw_roots])
        self._schemas: dict[str, NodeSchema | None] = {}
        self._provenance: dict[str, SchemaSourceInfo] = {}

    def get(self, class_type: str) -> NodeSchema | None:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type not in self._schemas:
            self._schemas[class_type] = self._find_schema(class_type)
        return self._schemas[class_type]

    def provenance_for(self, class_type: str) -> SchemaSourceInfo | None:
        return self._provenance.get(class_type)

    def warnings(self) -> list[SourceScanWarning]:
        return list(self.scan_warnings)

    def _bounded_roots(self, roots: list[Path]) -> list[Path]:
        bounded: list[Path] = []
        seen: set[Path] = set()
        for root in roots:
            normalized = root.expanduser()
            key = normalized.resolve() if normalized.exists() else normalized
            if key in seen:
                continue
            seen.add(key)
            if len(bounded) >= self.max_roots:
                self.scan_warnings.append(
                    SourceScanWarning(
                        code="source_scan_root_cap_skipped",
                        message=f"source scan root cap {self.max_roots} skipped {normalized}",
                        path=str(normalized),
                    )
                )
                continue
            bounded.append(normalized)
        return bounded

    def _find_schema(self, class_type: str) -> NodeSchema | None:
        for path in _direct_python_files(self.roots, class_type):
            schema = self._schema_from_path(path, class_type)
            if schema is not None or class_type in self._provenance:
                return schema
        for path in _candidate_python_files(
            self.roots,
            class_type,
            warnings=self.scan_warnings,
            max_files_per_root=self.max_files_per_root,
            max_total_files=self.max_total_files,
        ):
            schema = self._schema_from_path(path, class_type)
            if schema is not None or class_type in self._provenance:
                return schema
        return None

    def _schema_from_path(self, path: Path, class_type: str) -> NodeSchema | None:
        schema = _schema_from_python_source(path, class_type)
        if schema is not None:
            info = SchemaSourceInfo(
                provider_name="source_parser",
                source_path=str(path),
                package=schema.pack,
                confidence=0.9,
            )
            self._provenance[class_type] = info
            for warning in self.scan_warnings:
                if warning.class_type == class_type:
                    info.ignored_evidence.append(warning.code)
            return NodeSchema(
                class_type=schema.class_type,
                pack=schema.pack,
                inputs=schema.inputs,
                outputs=schema.outputs,
                source_provider=info.provider_name,
                source_path=info.source_path,
                source_package=info.package,
                confidence=info.confidence,
                ignored_evidence=tuple(info.ignored_evidence),
            )
        if _source_contains_class(path, class_type):
            warning = SourceScanWarning(
                code="dynamic_input_types_miss",
                message=f"{class_type} in {path} did not expose a statically parseable INPUT_TYPES return",
                class_type=class_type,
                path=str(path),
            )
            self.scan_warnings.append(warning)
            self._provenance[class_type] = SchemaSourceInfo(
                provider_name="source_parser",
                source_path=str(path),
                package=path.parent.name,
                confidence=0.0,
                ignored_evidence=[warning.code],
            )
        return None


class ObjectInfoSchemaProvider:
    """Schema provider backed by a captured ComfyUI /object_info JSON file."""

    def __init__(self, object_info_path: str | Path) -> None:
        self.object_info_path = Path(object_info_path)
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            data = load_object_info_cache(self.object_info_path)
            if data is None:
                raise SchemaIndexError(self.object_info_path, ValueError("expected object_info JSON object"))
            self._schemas = {
                class_type: _schema_from_object_info(class_type, info)
                for class_type, info in data.items()
                if class_type != CACHE_METADATA_KEY and isinstance(info, dict)
            }
        return self._schemas


class ObjectInfoIndexSchemaProvider:
    """Schema provider backed by ``object_info/index.json`` class-to-file rows."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self._index: dict[str, str] | None = None
        self._file_cache: dict[str, dict[str, Any]] = {}
        self._schemas: dict[str, NodeSchema | None] = {}

    def get(self, class_type: str) -> NodeSchema | None:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type not in self._schemas:
            self._schemas[class_type] = self._load_schema(class_type)
        return self._schemas[class_type]

    def schemas(self) -> dict[str, NodeSchema]:
        loaded: dict[str, NodeSchema] = {}
        for class_type in self._load_index():
            schema = self.get_schema(class_type)
            if schema is not None:
                loaded[class_type] = schema
        return loaded

    def _load_index(self) -> dict[str, str]:
        if self._index is not None:
            return self._index
        data = load_object_info_cache(self.index_path)
        if data is None:
            self._index = {}
        else:
            self._index = {
                str(key): str(value)
                for key, value in data.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        return self._index

    def raw_widget_order(self, class_type: str) -> list[str | None] | None:
        """Return the raw ``object_info_widget_order`` including ``None``/null entries.

        Returns ``None`` when the class is not found in the cache.
        This is the authoritative slot-count source (nulls denote UI-only slots);
        the compacted null-free list is for widget VALUES emission only.
        """
        filename = self._load_index().get(class_type)
        if not filename:
            return None
        data = self._file_cache.get(filename)
        if data is None:
            data = load_object_info_cache(self.root / filename) or {}
            self._file_cache[filename] = data
        info = data.get(class_type)
        if not isinstance(info, dict):
            return None
        raw_order = info.get("object_info_widget_order")
        if isinstance(raw_order, list):
            return [name if isinstance(name, str) else None for name in raw_order]
        return None

    def _load_schema(self, class_type: str) -> NodeSchema | None:
        filename = self._load_index().get(class_type)
        if not filename:
            return None
        data = self._file_cache.get(filename)
        if data is None:
            data = load_object_info_cache(self.root / filename) or {}
            self._file_cache[filename] = data
        info = data.get(class_type)
        if not isinstance(info, dict):
            return None
        schema = _schema_from_object_info(class_type, info)
        return NodeSchema(
            class_type=schema.class_type,
            pack=schema.pack,
            inputs=schema.inputs,
            outputs=schema.outputs,
            source_provider="object_info_index",
            source_cache_path=str(self.root / filename),
            source_package=schema.pack,
        )


class CompositeSchemaProvider:
    def __init__(self, *providers: SchemaProvider) -> None:
        self.providers = providers

    def get(self, class_type: str) -> NodeSchema | None:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        for provider in self.providers:
            schema = provider.get_schema(class_type)
            if schema is not None:
                return schema
        return None


class AuthoringSchemaProvider:
    """Offline schema provider for schema-only authoring and CLI inspection.

    Unlike ``ConversionSchemaProvider``, this provider intentionally prefers the
    committed structured object_info cache before local/generated
    ``node_index.json`` so schema-only commands are not shadowed by stale local
    indexes.
    """

    def __init__(
        self,
        *,
        object_info_index_root: str | Path | None = None,
        object_info_cache_path: str | Path | None = None,
        object_info_cache_dir: str | Path = "out/cache",
        source_roots: list[str | Path] | None = None,
        node_index_path: str | Path = "node_index.json",
    ) -> None:
        self.object_info_index_root = Path(object_info_index_root) if object_info_index_root is not None else _default_object_info_index_root()
        self.object_info_cache_path = Path(object_info_cache_path) if object_info_cache_path is not None else None
        self.object_info_cache_dir = Path(object_info_cache_dir)
        self.node_index_path = Path(node_index_path)
        self._providers: tuple[SchemaProvider, ...] = self._build_providers(source_roots=source_roots)

    def get(self, class_type: str) -> NodeSchema | None:
        return self.get_schema(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        for provider in self._providers:
            try:
                schema = provider.get_schema(class_type)
            except SchemaIndexError:
                continue
            if schema is not None:
                return schema
        return None

    def schemas(self) -> dict[str, NodeSchema]:
        merged: dict[str, NodeSchema] = {}
        for provider in reversed(self._providers):
            schemas = schemas_for(provider)
            if schemas is not None:
                merged.update({str(key): value for key, value in schemas.items() if isinstance(value, NodeSchema)})
        return merged

    def _build_providers(self, *, source_roots: list[str | Path] | None) -> tuple[SchemaProvider, ...]:
        providers: list[SchemaProvider] = []
        if self.object_info_cache_path is not None:
            providers.append(ObjectInfoSchemaProvider(self.object_info_cache_path))
        providers.append(ObjectInfoIndexSchemaProvider(self.object_info_index_root))
        if self.object_info_cache_path is None:
            providers.extend(ObjectInfoSchemaProvider(path) for path in object_info_cache_candidates(self.object_info_cache_dir))
        providers.append(SourceSchemaProvider(source_roots))
        providers.append(LocalSchemaProvider(self.node_index_path))
        return tuple(providers)


class ConversionSchemaProvider:
    """Deterministic offline schema provider for port check/convert.

    Precedence order (first hit wins):

    1. **Committed node_index.json** - `LocalSchemaProvider` against the
       pinned `node_index_path`.
    2. **Provenance-matched object_info cache** - `ObjectInfoSchemaProvider`
       loaded from `object_info_cache_path` only when its fingerprint
       metadata matches the expected runtime identity.
    3. **Source parser** - `SourceSchemaProvider` scanning installed
       custom-node source trees under `source_roots`.
    4. **Widget schema fallback** - positional `widget_N` -> named input
       aliases from the local `WIDGET_SCHEMA` table (lowest priority).
    5. **Runtime** - `RuntimeSchemaProvider` is consulted *only* when
       `enable_runtime=True` (off by default).

    Each `get_schema` hit records a `SchemaSourceInfo` provenance note
    via `_logger.info` so callers can attribute emission decisions.

    Returns `None` for unknown types - never silently falls through to
    a live network call behind the `enable_runtime` flag.
    """

    def __init__(
        self,
        *,
        node_index_path: str | Path = "node_index.json",
        source_roots: list[str | Path] | None = None,
        object_info_cache_path: str | Path | None = None,
        object_info_index_root: str | Path | None = None,
        widget_schema: dict[str, list[str | None]] | None = None,
        runtime_server_url: str | None = None,
        enable_runtime: bool = False,
    ) -> None:
        self._local = LocalSchemaProvider(node_index_path)
        self._source = SourceSchemaProvider(source_roots)
        self._expected_cache_fingerprint = runtime_fingerprint(runtime_server_url)
        self._expected_cache_identity = self._object_info_cache_expected_identity(runtime_server_url)
        self._rejected_object_info_cache: SchemaSourceInfo | None = None
        self._object_info: ObjectInfoSchemaProvider | None = None
        if object_info_cache_path is not None:
            self._object_info = self._validated_object_info_provider(object_info_cache_path)
        self._object_info_index: ObjectInfoIndexSchemaProvider | None = None
        if object_info_index_root is not None:
            self._object_info_index = ObjectInfoIndexSchemaProvider(object_info_index_root)
        self._widget_schema: dict[str, list[str | None]] = widget_schema or {}
        self._runtime: RuntimeSchemaProvider | None = None
        if enable_runtime:
            self._runtime = RuntimeSchemaProvider(server_url=runtime_server_url)
        self._enable_runtime = enable_runtime

    def get_schema(self, class_type: str) -> NodeSchema | None:
        # 1. Committed node_index.json
        schema = self._local.get_schema(class_type)
        if schema is not None:
            _logger.info(
                "schema hit: %s provider=node_index path=%s",
                class_type,
                self._local.index_path,
            )
            return self._with_provenance(
                schema,
                SchemaSourceInfo(
                    provider_name="node_index",
                    source_path=str(self._local.index_path),
                    confidence=1.0,
                ),
            )

        # 2. Provenance-matched object_info cache
        if self._object_info is not None:
            try:
                schema = self._object_info.get_schema(class_type)
            except SchemaIndexError:
                schema = None
            if schema is not None:
                cache_info = self._object_info_cache_info()
                _logger.info(
                    "schema hit: %s provider=object_info_cache path=%s confidence=%s conflicts=%s",
                    class_type,
                    self._object_info.object_info_path,
                    cache_info.confidence,
                    cache_info.conflicts,
                )
                return self._with_provenance(schema, cache_info)
            else:
                _logger.info(
                    "schema miss in object_info_cache: %s path=%s",
                    class_type,
                    self._object_info.object_info_path,
                )

        # 3. Source parser
        if self._object_info_index is not None:
            schema = self._object_info_index.get_schema(class_type)
            if schema is not None:
                cache_path = self._object_info_index.root / (self._object_info_index._load_index().get(class_type) or "")
                _logger.info(
                    "schema hit: %s provider=object_info_index root=%s",
                    class_type,
                    self._object_info_index.root,
                )
                return self._with_provenance(
                    schema,
                    self._object_info_index_cache_info(schema, cache_path),
                )

        # 3. Source parser
        schema = self._source.get_schema(class_type)
        if schema is not None:
            source_info = self._source.provenance_for(class_type) or SchemaSourceInfo(
                provider_name="source_parser",
                source_path=schema.source_path,
                package=schema.pack,
                confidence=0.9,
            )
            _logger.info(
                "schema hit: %s provider=source_parser roots=%s",
                class_type,
                self._source.roots,
            )
            return self._with_provenance(schema, source_info)

        # 4. Widget schema fallback - build a minimal NodeSchema from aliases
        widget_names = self._widget_schema.get(class_type)
        if widget_names is not None:
            _logger.info(
                "schema hit: %s provider=widget_schema_fallback names=%s",
                class_type,
                widget_names,
            )
            fallback_schema = self._widget_names_to_schema(class_type, widget_names)
            return self._with_provenance(
                fallback_schema,
                SchemaSourceInfo(
                    provider_name="widget_schema",
                    confidence=0.3,
                ),
            )

        # 5. Runtime (only when explicitly enabled)
        if self._runtime is not None:
            schema = self._runtime.get_schema(class_type)
            if schema is not None:
                _logger.info(
                    "schema hit: %s provider=runtime server=%s",
                    class_type,
                    self._runtime.server_url,
                )
                return self._with_provenance(
                    schema,
                    SchemaSourceInfo(
                        provider_name="runtime",
                        server_url=self._runtime.server_url,
                        cache_path=str(self._runtime.cache_path) if self._runtime.cache_path else None,
                        confidence=0.6,
                    ),
                )

        _logger.info("schema miss: %s (no provider had it)", class_type)
        return None

    @staticmethod
    def _widget_names_to_schema(class_type: str, names: list[str | None]) -> NodeSchema:
        inputs: dict[str, InputSpec] = {}
        outputs: list[OutputSpec] = []
        for idx, name in enumerate(names):
            if name is not None:
                inputs[name] = InputSpec(type=None, required=False)
        return NodeSchema(
            class_type=class_type,
            pack=None,
            inputs=inputs,
            outputs=outputs,
            source_provider="widget_schema",
            confidence=0.3,
        )

    def _object_info_cache_info(self) -> SchemaSourceInfo:
        if self._object_info is None:
            return SchemaSourceInfo(provider_name="object_info_cache", confidence=0.0)
        path = self._object_info.object_info_path
        data = load_object_info_cache(path) or {}
        metadata = data.get("_cache_metadata")
        info = SchemaSourceInfo(
            provider_name="object_info_cache",
            cache_path=str(path),
            confidence=0.8,
        )
        metadata_fingerprint: str | None = None
        if isinstance(metadata, dict):
            for key in ("runtime_fingerprint", "fingerprint", "cache_fingerprint"):
                value = metadata.get(key)
                if isinstance(value, str) and value:
                    metadata_fingerprint = value
                    break
            info.hash = metadata_fingerprint
            package = metadata.get("package")
            version = metadata.get("version")
            if isinstance(package, str):
                info.package = package
            if isinstance(version, str):
                info.version = version
        else:
            info.confidence = 0.5
            info.ignored_evidence.append("metadata_less_cache")

        filename_fingerprint = _cache_fingerprint_for_path(path)
        if metadata_fingerprint is None and filename_fingerprint is not None:
            info.hash = filename_fingerprint

        observed = metadata_fingerprint or filename_fingerprint
        if observed is not None and observed != self._expected_cache_fingerprint:
            info.confidence = min(info.confidence, 0.4)
            info.conflicts.append(
                f"stale_cache_fingerprint:{observed}!={self._expected_cache_fingerprint}"
            )
        elif observed is None:
            info.confidence = min(info.confidence, 0.5)
            info.ignored_evidence.append("missing_cache_fingerprint")
        return info

    def _validated_object_info_provider(self, path: str | Path) -> ObjectInfoSchemaProvider | None:
        cache_path = Path(path)
        data = load_object_info_cache(cache_path)
        result = validate_object_info_cache(
            data,
            expected=self._expected_cache_identity,
            policy="strict",
            cache_path=cache_path,
        )
        if result.ok:
            return ObjectInfoSchemaProvider(cache_path)
        self._rejected_object_info_cache = self._object_info_cache_rejection_info(cache_path, result)
        _logger.warning(
            "rejected object_info cache: path=%s reason=%s expected=%s actual=%s conflicts=%s",
            cache_path,
            result.reason,
            result.expected,
            result.actual,
            self._rejected_object_info_cache.conflicts,
        )
        return None

    def _object_info_cache_rejection_info(self, path: Path, result: Any) -> SchemaSourceInfo:
        info = SchemaSourceInfo(
            provider_name="object_info_cache",
            cache_path=str(path),
            confidence=0.0,
        )
        reason = result.reason or "unknown"
        conflict_prefix = (
            "rejected_metadata_less_object_info_cache"
            if reason == "cache_metadata_missing"
            else "rejected_stale_object_info_cache"
            if reason
            in {
                "cache_format_version_missing",
                "cache_format_version_mismatch",
                "cache_checksum_mismatch",
                "cache_runtime_fingerprint_mismatch",
                "cache_server_url_mismatch",
                "cache_authored_pack_fingerprint_mismatch",
                "cache_authored_index_fingerprint_mismatch",
            }
            else "rejected_invalid_object_info_cache"
        )
        info.conflicts.append(f"{conflict_prefix}:{reason}")
        metadata_hash = result.actual.get("runtime_fingerprint") or result.actual.get("checksum")
        if isinstance(metadata_hash, str):
            info.hash = metadata_hash
        return info

    def _object_info_index_cache_info(self, schema: NodeSchema, cache_path: Path) -> SchemaSourceInfo:
        info = SchemaSourceInfo(
            provider_name="object_info_index",
            cache_path=str(cache_path),
            package=schema.pack,
            confidence=0.7,
        )
        data = load_object_info_cache(cache_path) or {}
        metadata = data.get(CACHE_METADATA_KEY)
        if isinstance(metadata, dict):
            authored_pack = metadata.get("authored_pack_fingerprint")
            authored_index = metadata.get("authored_index_fingerprint")
            checksum = metadata.get("checksum")
            package = metadata.get("package")
            version = metadata.get("version")
            for value in (authored_pack, authored_index, checksum):
                if isinstance(value, str) and value:
                    info.hash = value
                    break
            if isinstance(package, str):
                info.package = package
            if isinstance(version, str):
                info.version = version
        return info

    def _object_info_cache_expected_identity(self, runtime_server_url: str | None) -> dict[str, Any]:
        return {"runtime_fingerprint": self._expected_cache_fingerprint}

    @staticmethod
    def _with_provenance(schema: NodeSchema, info: SchemaSourceInfo) -> NodeSchema:
        # NodeSchema is frozen, so we must construct a new one with provenance.
        return NodeSchema(
            class_type=schema.class_type,
            pack=schema.pack,
            inputs=schema.inputs,
            outputs=schema.outputs,
            source_provider=info.provider_name,
            source_path=info.source_path,
            source_cache_path=info.cache_path,
            source_server_url=info.server_url,
            source_package=info.package,
            source_version=info.version,
            source_hash=info.hash,
            confidence=info.confidence,
            conflicts=tuple(info.conflicts),
            ignored_evidence=tuple(info.ignored_evidence),
        )


class RuntimeSchemaProvider:
    def __init__(
        self,
        *,
        server_url: str | None = None,
        cache_dir: str | Path = "out/cache",
        log_path: str | Path | None = None,
    ) -> None:
        self.server_url = server_url
        self.cache_path = object_info_cache_path(server_url=server_url, cache_dir=cache_dir)
        self.log_path = log_path
        self._object_info: dict[str, Any] | None = None
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            self._schemas = {
                class_type: _schema_from_object_info(class_type, info)
                for class_type, info in self.object_info().items()
                if class_type != CACHE_METADATA_KEY and isinstance(info, dict)
            }
        return self._schemas

    def object_info(self) -> dict[str, Any]:
        if self._object_info is None:
            cached = self._load_valid_cached_object_info()
            if cached is not None:
                self._set_object_info(cached)
            else:
                self._set_object_info(_run_async(self.object_info_async()))
        return self._object_info

    async def object_info_async(self) -> dict[str, Any]:
        cached = self._load_valid_cached_object_info()
        if cached is not None:
            self._set_object_info(cached)
            return self._object_info
        async with comfy_server(server_url=self.server_url, log_path=self.log_path) as active_url:
            data = await ComfyClient(active_url).object_info()
        write_object_info_cache(
            self.cache_path,
            data,
            runtime_fingerprint=runtime_fingerprint(self.server_url),
            server_url=active_url,
        )
        self._set_object_info(data)
        return self._object_info

    def _load_valid_cached_object_info(self) -> dict[str, Any] | None:
        cached = load_object_info_cache(self.cache_path)
        result = validate_object_info_cache(
            cached,
            expected=self._cache_validation_expected(),
            policy="strict",
            cache_path=self.cache_path,
        )
        if result.ok:
            return cached if isinstance(cached, dict) else None
        if cached is not None:
            _logger.warning(
                "rejected runtime object_info cache: path=%s reason=%s expected=%s actual=%s",
                self.cache_path,
                result.reason,
                result.expected,
                result.actual,
            )
        return None

    def _cache_validation_expected(self) -> dict[str, Any]:
        return {"runtime_fingerprint": runtime_fingerprint(self.server_url)}

    def _set_object_info(self, data: dict[str, Any]) -> None:
        if self._object_info != data:
            self._schemas = None
        self._object_info = data


def get_schema_provider(
    prefer: Literal["runtime", "local", "authoring", "auto"] = "auto",
    *,
    server_url: str | None = None,
) -> RuntimeSchemaProvider | LocalSchemaProvider | AuthoringSchemaProvider | CompositeSchemaProvider:
    if prefer == "runtime":
        return RuntimeSchemaProvider(server_url=server_url)
    if prefer == "local":
        return LocalSchemaProvider()
    if prefer == "authoring":
        return get_authoring_schema_provider()
    if prefer != "auto":
        raise ValueError(f"Unknown schema provider preference: {prefer}")
    if server_url:
        return RuntimeSchemaProvider(server_url=server_url)
    if Path("node_index.json").exists():
        return LocalSchemaProvider()
    if has_comfyui_runtime():
        return RuntimeSchemaProvider(server_url=server_url)
    return LocalSchemaProvider()


def get_authoring_schema_provider(
    *,
    object_info_cache_path: str | Path | None = None,
    object_info_index_root: str | Path | None = None,
    node_index_path: str | Path = "node_index.json",
) -> AuthoringSchemaProvider:
    return AuthoringSchemaProvider(
        object_info_cache_path=object_info_cache_path,
        object_info_index_root=object_info_index_root,
        node_index_path=node_index_path,
    )


def _default_object_info_index_root() -> Path:
    return Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info"


def _schema_from_object_info(class_type: str, info: dict[str, Any]) -> NodeSchema:
    parsed_inputs: dict[str, InputSpec] = {}
    input_groups = info.get("input")
    if not isinstance(input_groups, dict):
        input_groups = info.get("inputs", {})
    if isinstance(input_groups, dict):
        for group_name, group in input_groups.items():
            required = group_name == "required"
            if isinstance(group, dict):
                for name, spec in group.items():
                    parsed_inputs[str(name)] = _parse_input_spec(spec, required=required)
    inputs = _order_object_info_inputs(parsed_inputs, info)
    outputs = _parse_outputs(info)
    pack = _first_string(info, "pack", "package", "category")
    return NodeSchema(class_type=class_type, pack=pack, inputs=inputs, outputs=outputs)


def _order_object_info_inputs(inputs: dict[str, InputSpec], info: dict[str, Any]) -> dict[str, InputSpec]:
    ordered: dict[str, InputSpec] = {}
    for name in _object_info_input_order(info):
        if name in inputs and name not in ordered:
            ordered[name] = inputs[name]
    for name, spec in inputs.items():
        if name not in ordered:
            ordered[name] = spec
    return ordered


def _object_info_input_order(info: dict[str, Any]) -> list[str]:
    widget_order = info.get("object_info_widget_order")
    if isinstance(widget_order, list):
        return [str(name) for name in widget_order if isinstance(name, str) and name]

    input_order_all = info.get("input_order_all")
    if isinstance(input_order_all, list):
        return [str(name) for name in input_order_all if isinstance(name, str) and name]

    input_order = info.get("input_order")
    if isinstance(input_order, dict):
        names: list[str] = []
        for group in ("required", "optional", "hidden"):
            values = input_order.get(group)
            if isinstance(values, list):
                names.extend(str(name) for name in values if isinstance(name, str) and name)
        return names
    return []


def _cache_fingerprint_for_path(path: Path) -> str | None:
    name = path.name
    if not name.startswith("object_info.") or not name.endswith(".json"):
        return None
    middle = name[len("object_info.") : -len(".json")]
    if not middle:
        return None
    return middle


def _schema_from_index_row(row: dict[str, Any]) -> NodeSchema | None:
    class_type = _first_string(row, "class_type", "class_name", "name", "id", "node", "display_name")
    if not class_type:
        return None
    pack = _first_string(row, "pack", "package", "source", "category")
    inputs: dict[str, InputSpec] = {}
    raw_inputs = row.get("inputs") or row.get("input")
    if isinstance(raw_inputs, dict):
        if "required" in raw_inputs or "optional" in raw_inputs:
            for group_name, group in raw_inputs.items():
                if isinstance(group, dict):
                    for name, spec in group.items():
                        inputs[str(name)] = _parse_input_spec(spec, required=group_name == "required")
        else:
            for name, spec in raw_inputs.items():
                inputs[str(name)] = _parse_input_spec(spec, required=False)
    elif isinstance(raw_inputs, list):
        for item in raw_inputs:
            if isinstance(item, str):
                inputs[item] = InputSpec(required=False)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                inputs[item["name"]] = _parse_input_spec(item, required=bool(item.get("required", False)))
    return NodeSchema(class_type=class_type, pack=pack, inputs=inputs, outputs=_parse_index_outputs(row))


def _parse_index_outputs(row: dict[str, Any]) -> list[OutputSpec]:
    output_types = row.get("output_types") or row.get("outputs") or row.get("output")
    if isinstance(output_types, str):
        parts = [part.strip() for part in output_types.split(",")]
        return [OutputSpec(type=part) for part in parts if part]
    if isinstance(output_types, list):
        outputs: list[OutputSpec] = []
        for item in output_types:
            if isinstance(item, dict):
                outputs.append(OutputSpec(type=_first_string(item, "type"), name=_first_string(item, "name")))
            elif item is not None:
                outputs.append(OutputSpec(type=str(item)))
        return outputs
    return []


def _parse_input_spec(raw: Any, *, required: bool) -> InputSpec:
    typ: Any = None
    attrs: dict[str, Any] = {}
    choices: list[Any] | None = None
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


def _parse_outputs(info: dict[str, Any]) -> list[OutputSpec]:
    normalized_outputs = info.get("outputs")
    if isinstance(normalized_outputs, list):
        outputs: list[OutputSpec] = []
        for item in normalized_outputs:
            if isinstance(item, dict):
                outputs.append(
                    OutputSpec(
                        type=_first_string(item, "type"),
                        name=_first_string(item, "name"),
                    )
                )
            elif item is not None:
                outputs.append(OutputSpec(type=str(item)))
        return outputs

    raw_outputs = info.get("output") or []
    names = info.get("output_name") or info.get("output_names") or []
    outputs: list[OutputSpec] = []
    if isinstance(raw_outputs, (list, tuple)):
        for index, raw in enumerate(raw_outputs):
            name = names[index] if isinstance(names, (list, tuple)) and index < len(names) else None
            outputs.append(OutputSpec(type=str(raw) if raw is not None else None, name=str(name) if name else None))
    return outputs


def _default_source_roots() -> list[Path]:
    return [
        Path("custom_nodes"),
        Path("vendor") / "ComfyUI",
    ]


_SOURCE_SCAN_EXCLUDED_DIRS = frozenset({".git", "__pycache__", "venv", ".venv", "node_modules"})


def _direct_python_files(roots: list[Path], class_type: str) -> list[Path]:
    return [path for root in roots if (path := root / f"{class_type}.py").is_file()]


def _candidate_python_files(
    roots: list[Path],
    class_type: str,
    *,
    warnings: list[SourceScanWarning] | None = None,
    max_files_per_root: int = 2_000,
    max_total_files: int = 5_000,
) -> list[Path]:
    candidates: list[Path] = []
    total_scanned = 0
    for root in roots:
        if not root.exists():
            continue
        direct = root / f"{class_type}.py"
        if direct.is_file():
            candidates.append(direct)
        try:
            root_scanned = 0
            for path in sorted(root.rglob("*.py")):
                if path == direct:
                    continue
                if any(part in _SOURCE_SCAN_EXCLUDED_DIRS for part in path.parts):
                    continue
                if root_scanned >= max_files_per_root:
                    if warnings is not None:
                        warnings.append(
                            SourceScanWarning(
                                code="source_scan_file_cap_skipped",
                                message=f"source scan file cap {max_files_per_root} reached under {root}",
                                path=str(root),
                            )
                        )
                    break
                if total_scanned >= max_total_files:
                    if warnings is not None:
                        warnings.append(
                            SourceScanWarning(
                                code="source_scan_total_file_cap_skipped",
                                message=f"source scan total file cap {max_total_files} reached before {path}",
                                path=str(path),
                            )
                        )
                    return sorted(dict.fromkeys(candidates))
                root_scanned += 1
                total_scanned += 1
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if f"class {class_type}" in text or f'"{class_type}"' in text or f"'{class_type}'" in text:
                    candidates.append(path)
        except OSError:
            continue
    return sorted(dict.fromkeys(candidates))


def _schema_from_python_source(path: Path, class_type: str) -> NodeSchema | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_type:
            class_values = _class_literal_values(node)
            input_types = _input_types_return(node, class_values)
            if not isinstance(input_types, dict):
                return None
            return _schema_from_object_info(
                class_type,
                {
                    "pack": path.parent.name,
                    "input": input_types,
                    "output": _class_literal_attr(node, "RETURN_TYPES") or [],
                    "output_name": _class_literal_attr(node, "RETURN_NAMES") or [],
                },
            )
    return None


def _source_contains_class(path: Path, class_type: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except (OSError, SyntaxError):
        return False
    return any(isinstance(node, ast.ClassDef) and node.name == class_type for node in ast.walk(tree))


def _class_literal_values(node: ast.ClassDef) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for stmt in node.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.target is not None:
            targets = [stmt.target]
            value = stmt.value
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                parsed = _literal_eval_node(value, values)
                if parsed is not _UNPARSEABLE:
                    values[target.id] = parsed
    return values


def _class_literal_attr(node: ast.ClassDef, name: str) -> Any:
    values = _class_literal_values(node)
    return values.get(name)


def _input_types_return(node: ast.ClassDef, class_values: dict[str, Any]) -> Any:
    for stmt in node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name != "INPUT_TYPES":
            continue
        for child in ast.walk(stmt):
            if isinstance(child, ast.Return) and child.value is not None:
                parsed = _literal_eval_node(child.value, class_values)
                return None if parsed is _UNPARSEABLE else parsed
    return None


_UNPARSEABLE = object()


def _literal_eval_node(node: ast.AST, class_values: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        values = [_literal_eval_node(item, class_values) for item in node.elts]
        return _UNPARSEABLE if _UNPARSEABLE in values else values
    if isinstance(node, ast.Tuple):
        values = [_literal_eval_node(item, class_values) for item in node.elts]
        return _UNPARSEABLE if _UNPARSEABLE in values else tuple(values)
    if isinstance(node, ast.Dict):
        out: dict[Any, Any] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=False):
            if key_node is None:
                return _UNPARSEABLE
            key = _literal_eval_node(key_node, class_values)
            value = _literal_eval_node(value_node, class_values)
            if key is _UNPARSEABLE:
                return _UNPARSEABLE
            if value is _UNPARSEABLE:
                continue
            out[key] = value
        return out
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.attr in class_values:
        return class_values[node.attr]
    if isinstance(node, ast.Name):
        return class_values.get(node.id, _UNPARSEABLE)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_eval_node(node.operand, class_values)
        if isinstance(value, (int, float)):
            return -value
    return _UNPARSEABLE


def _first_string(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise RuntimeError("RuntimeSchemaProvider synchronous access cannot run inside an active event loop; use object_info_async().")
