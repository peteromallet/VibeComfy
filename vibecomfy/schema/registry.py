from __future__ import annotations


def schema_for(provider: object | None, class_type: str) -> object | None:
    if provider is None:
        return None
    getter = getattr(provider, "get_schema", None) or getattr(provider, "get", None)
    if not callable(getter):
        return None
    return getter(class_type)


def schemas_for(provider: object | None) -> dict[str, object] | None:
    schemas = getattr(provider, "schemas", None)
    if not callable(schemas):
        return None
    return schemas()


def schema_registry_empty(provider: object | None) -> bool:
    try:
        schemas = schemas_for(provider)
    except Exception:
        return False
    return schemas is not None and len(schemas) == 0
