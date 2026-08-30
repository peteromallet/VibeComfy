from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.ingest.normalize import _named_import
from vibecomfy.workflow import VibeWorkflow

if TYPE_CHECKING:
    # Deferred so `import vibecomfy.testing` does not transitively load
    # `vibecomfy.runtime.client`/`server`/`comfy_command` through
    # `vibecomfy.schema.provider`. `SchemaProvider` is only used as a type
    # annotation here.
    from vibecomfy.schema import SchemaProvider  # noqa: F401
from .ready import (
    _normalize_ready_template_id,
    _ready_lookup_key,
    ready_template_discovery,
    workflow_from_ready,
)
from vibecomfy.scratchpad_loader import load_scratchpad


def workflow_from_file(path: str, *, schema_provider: SchemaProvider | None = None) -> VibeWorkflow:
    raw = load_workflow_json(path)
    return _named_import(raw, source_path=path, schema_provider=schema_provider)


def workflow_from_id(workflow_id: str, *, schema_provider: SchemaProvider | None = None) -> VibeWorkflow:
    """Load a workflow by id from the ready-template registry or the indexed corpus."""
    discovery = ready_template_discovery()
    try:
        return workflow_from_ready(workflow_id, _discovery=discovery)
    except KeyError:
        pass

    index_paths = [Path("workflow_index.json"), Path("external_workflow_index.json")]
    existing_indexes = [path for path in index_paths if path.exists()]
    if not existing_indexes:
        raise FileNotFoundError("No workflow indexes found. Run `vibecomfy sources sync` first.")

    entries = []
    for index_path in existing_indexes:
        entries.extend(json.loads(index_path.read_text(encoding="utf-8")))

    match = _unique_corpus_entry(workflow_id, entries)
    raw = load_workflow_json(match["path"])
    return _named_import(
        raw,
        source_path=match["path"],
        workflow_id=match["id"],
        schema_provider=schema_provider,
    )


def _unique_corpus_entry(workflow_id: str, entries: list[Any]) -> dict[str, Any]:
    """Return the unique corpus row for an id, or refuse on alias/id/stem collisions."""
    query_id = _normalize_ready_template_id(workflow_id)
    query_key = _ready_lookup_key(workflow_id)
    rows = [entry for entry in entries if isinstance(entry, dict)]

    def _refuse_or_one(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not matches:
            return None
        if len(matches) > 1:
            candidates = sorted(str(entry.get("path", "")) for entry in matches)
            raise ValueError(
                f"Ambiguous workflow id {workflow_id!r}; candidates: "
                + ", ".join(candidates)
                + ". Remove the duplicate or use one canonical source."
            )
        return matches[0]

    match = _refuse_or_one(
        [
            entry
            for entry in rows
            if isinstance(entry.get("id"), str)
            and _normalize_ready_template_id(entry["id"]) == query_id
        ]
    )
    if match is not None:
        return match
    match = _refuse_or_one(
        [
            entry
            for entry in rows
            if isinstance(entry.get("id"), str)
            and _ready_lookup_key(entry["id"]) == query_key
        ]
    )
    if match is not None:
        return match
    match = _refuse_or_one(
        [
            entry
            for entry in rows
            if isinstance(entry.get("path"), str)
            and _ready_lookup_key(Path(entry["path"]).stem) == query_key
        ]
    )
    if match is not None:
        return match
    raise KeyError(f"Workflow not found: {workflow_id}")


workflow_from_template = workflow_from_id  # back-compat alias documented by the agent skill.


def load_workflow_reference(
    value: str,
    *,
    schema_provider: SchemaProvider | None = None,
    allow_scratchpad: bool = False,
    ready: bool = False,
) -> VibeWorkflow:
    if ready:
        return workflow_from_ready(value)
    path = Path(value)
    if value.endswith(".json") or (path.exists() and path.suffix.lower() == ".json"):
        return workflow_from_file(str(path), schema_provider=schema_provider)
    if not path.exists():
        try:
            return workflow_from_id(value, schema_provider=schema_provider)
        except (FileNotFoundError, KeyError):
            if not allow_scratchpad:
                raise
    if allow_scratchpad:
        return load_scratchpad(value, provenance_override="user_confirmed")
    return workflow_from_id(value, schema_provider=schema_provider)
