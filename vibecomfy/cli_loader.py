from __future__ import annotations

from pathlib import Path

from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.registry.ready import ready_template_ids, workflow_from_ready
from vibecomfy.scratchpad_loader import load_scratchpad
from vibecomfy.workflow import VibeWorkflow

# `get_schema_provider` lives behind `vibecomfy.schema.provider`, which
# top-imports the runtime client. Importing it eagerly defeats the
# cheap-import promise for `vibecomfy.testing`. Resolve lazily on first call.


def load_workflow_any(path_or_id: str) -> VibeWorkflow:
    value = str(path_or_id)
    ready_id = _ready_id_for(value)
    if ready_id is not None:
        return workflow_from_ready(ready_id)

    try:
        path = resolve_workflow_path(value)
    except FileNotFoundError as exc:
        if _looks_like_path(value):
            raise
        raise KeyError(f"Workflow id not found: {value}") from exc

    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return load_scratchpad(path, provenance_override="user_confirmed")
    if suffix == ".json":
        from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

        schema_provider = get_schema_provider("auto")
        raw = load_workflow_json(path)
        api = normalize_to_api(raw, schema_provider=schema_provider, comfy_converter_strict=True)
        return convert_to_vibe_format(api, source_path=path, schema_provider=schema_provider)
    raise FileNotFoundError(path)


def _ready_id_for(value: str) -> str | None:
    ids = ready_template_ids()
    if value in ids:
        return value
    if "/" in value:
        return None
    matches = [template_id for template_id in ids if Path(template_id).name == value]
    if len(matches) == 1:
        return matches[0]
    return None


def _looks_like_path(value: str) -> bool:
    path = Path(value)
    return bool(path.suffix) or path.is_absolute() or any(part in value for part in ("/", "\\"))


__all__ = ["load_workflow_any"]
