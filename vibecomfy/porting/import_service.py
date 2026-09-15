"""Shared ComfyUI workflow import and origin artifact builder.

This is the package-owned import boundary used by both the local CLI and
Astrid's already-admitted ``vibecomfy.import`` task.  It owns conversion and
the initial canonical bundle identity, but never writes runtime events or
creates a task.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.porting.convert import (
    _build_emitted_workflow_from_text,
    port_convert_workflow,
)
from vibecomfy.porting.workbench import analyze_source, load_port_source
from vibecomfy.porting.provenance import extract_provenance
from vibecomfy.schema import ConversionSchemaProvider
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA
from vibecomfy.workflow_bundle import emit_bundle_with_candidate, load_bundle
from vibecomfy.security.provenance import Provenance


@dataclass(frozen=True, slots=True)
class ImportArtifacts:
    """Exact immutable member bytes plus the JSON origin receipt."""

    source_bytes: bytes
    python_bytes: bytes
    companion_bytes: bytes
    report: dict[str, Any]


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _conversion_provider() -> ConversionSchemaProvider:
    """Build the bounded, offline provider used by the import service."""
    package_root = Path(__file__).resolve().parents[1]
    repository_root = package_root.parent
    local_node_index = Path.cwd() / "node_index.json"
    return ConversionSchemaProvider(
        node_index_path=local_node_index if local_node_index.is_file() else repository_root / "node_index.json",
        object_info_index_root=package_root / "porting" / "cache" / "object_info",
        widget_schema=WIDGET_SCHEMA,
        enable_runtime=False,
    )


def _member_digests(source: bytes, python: bytes, companion: bytes) -> dict[str, str]:
    return {
        "workflow.py": _sha256(python),
        "workflow.vibe.json": _sha256(companion),
        "source.json": _sha256(source),
    }


def import_workflow_bytes(
    source_bytes: bytes,
    *,
    workflow_id: str,
    schema_provider: Any | None = None,
    source_provenance: Mapping[str, Any] | None = None,
) -> ImportArtifacts:
    """Convert source JSON bytes into an inspectable canonical workflow pair.

    The original input is returned without decoding/re-encoding.  Conversion
    is performed against a temporary ``source.json`` path so generated Python
    and its companion refer to the stable bundle member name rather than a
    temporary directory. ``source_provenance`` carries the external origin
    (for example a Hivemind evidence ID and revision) into the bundle's closed
    provenance. The caller owns publication of all returned files.
    """
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("workflow_id must be a non-empty string")
    if workflow_id != workflow_id.strip():
        raise ValueError("workflow_id must not have leading or trailing whitespace")

    try:
        decoded = json.loads(source_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"source workflow must be UTF-8 JSON: {exc}") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError("source workflow JSON must be an object")

    provider = schema_provider or _conversion_provider()
    with tempfile.TemporaryDirectory(prefix="vibecomfy-import-") as temporary:
        root = Path(temporary)
        source_path = root / "source.json"
        python_path = root / "workflow.py"
        source_path.write_bytes(source_bytes)

        loaded = load_port_source(str(source_path), schema_provider=provider)
        loaded.source_ref = "source.json"
        loaded.source_path = "source.json"
        loaded.workflow.id = workflow_id
        loaded.workflow.source.id = workflow_id
        loaded.workflow.source.path = "source.json"
        for key in ("source_ref", "source_path", "source_workflow_path", "source_workflow"):
            if key in loaded.workflow.source.provenance:
                loaded.workflow.source.provenance[key] = "source.json"

        analysis = analyze_source(
            "source.json",
            schema_provider=provider,
            loaded_source=loaded,
        )
        # ``source.json`` is the local bundle member; these fields preserve
        # where that member came from (for example a pinned Hivemind record).
        # They are closed by the bundle writer and do not put local paths into
        # generated Python.
        if source_provenance:
            # External callers may annotate the source origin, but this
            # boundary owns the digest of the bytes it actually imported.
            allowed_origin_fields = {
                "origin_kind",
                "origin_uri",
                "origin_pin",
                "origin_revision",
                "source_digest",
                "title",
            }
            unknown_fields = set(source_provenance) - allowed_origin_fields
            if unknown_fields:
                raise ValueError(
                    "unsupported source provenance fields: "
                    + ", ".join(sorted(str(field) for field in unknown_fields))
                )
            supplied_digest = source_provenance.get("source_digest")
            actual_digest = _sha256(source_bytes)
            if supplied_digest is not None and supplied_digest != actual_digest:
                raise ValueError(
                    "source provenance digest does not match the admitted source bytes"
                )
            analysis.provenance.update(dict(source_provenance))
            analysis.provenance["source_digest"] = actual_digest
        # Preserve authored node evidence independently from runtime pins.
        # Mixed/conflicting versions must remain observable after re-emission.
        embedded_source_provenance = extract_provenance(loaded.raw_workflow or decoded).to_json()
        conversion_provenance = dict(analysis.provenance)
        conversion_provenance["source_provenance"] = embedded_source_provenance
        registered_inputs = {
            str(name): (str(item.node_id), str(item.field))
            for name, item in loaded.workflow.inputs.items()
        }
        converted = port_convert_workflow(
            loaded.workflow,
            source_path="source.json",
            provenance=conversion_provenance,
            source_hash=analysis.source_hash,
            workflow_shape=analysis.workflow_shape,
            registered_inputs=registered_inputs,
            # Source evidence is carried above. Do not re-enter native
            # boundary normalization with raw JSON after load_port_source.
            # Draft imports retain unresolved-schema evidence. Runtime schema
            # access remains opt-in and is never booted by origin creation.
            schema_provider=None,
            preserve_node_ids=True,
        )
        if converted.validation is None or not converted.validation.ok:
            details = converted.validation.error if converted.validation is not None else "validation was not produced"
            raise ValueError(f"workflow conversion did not pass its structural/parity gate: {details}")

        from vibecomfy.porting.emit.ui import is_litegraph_candidate

        candidate = (
            loaded.raw_workflow
            if isinstance(loaded.raw_workflow, dict) and is_litegraph_candidate(loaded.raw_workflow)
            else None
        )
        emitted_workflow = _build_emitted_workflow_from_text(converted.text)
        bundle = emit_bundle_with_candidate(
            emitted_workflow,
            python_path,
            conversion_provenance,
            candidate,
            operation="imported",
            source_provenance={
                "operation": "imported",
                **{
                    key: analysis.provenance[key]
                    for key in ("source_kind", "ready_id")
                    if key in analysis.provenance
                },
            }
            | {
                "source_hash": analysis.source_hash,
                "workflow_shape": analysis.workflow_shape,
                "output_mode": "scratchpad",
                "source_type": str(loaded.workflow.source.source_type),
                "source_provenance": embedded_source_provenance,
            },
            source_format="scratchpad",
        )

        python_bytes = python_path.read_bytes()
        companion_bytes = python_path.with_suffix(".vibe.json").read_bytes()
        # The generated source is the canonical import artifact. Re-open that
        # exact source/companion pair before reporting its identity, so report
        # revision and digests describe what a later CLI/Astrid consumer loads
        # rather than only the pre-render IR used to emit it.
        bundle = load_bundle(python_path, trust=Provenance.USER_CONFIRMED)
        members = _member_digests(source_bytes, python_bytes, companion_bytes)
        validation = converted.validation.to_json()
        diagnostics = [issue.to_json() for issue in analysis.diagnostics]
        readiness = {
            "status": "conversion_validated" if validation.get("ok") else "conversion_needs_attention",
            "run_readiness": "not_assessed",
            "note": "Import validates conversion structure and parity; run readiness is checked separately with `vibecomfy validate <bundle>`.",
        }
        after = {
            "revision_id": bundle.revision_id,
            "parent_revision": None,
            "semantic_digest": bundle.semantic_digest,
            "ui_digest": bundle.ui_digest,
            "members": members,
        }
        origin_report = {
            "schema_version": 1,
            "transition_kind": "origin",
            "workflow_id": workflow_id,
            "workflow_identity": bundle.workflow_identity,
            "revision_id": bundle.revision_id,
            "parent_revision": None,
            "parent_task_id": None,
            "origin_task_id": None,
            "before": None,
            "after": after,
            "members": members,
            "source": {
                "member": "source.json",
                "sha256": members["source.json"],
                "source_hash": analysis.source_hash,
                "workflow_shape": analysis.workflow_shape,
            },
            "validation": {
                "structural_and_parity": validation,
                "analysis_ok": analysis.ok,
            },
            "readiness": readiness,
            "diagnostics": diagnostics,
            "provenance": conversion_provenance,
        }
        # Assert the service's byte-level custody promise before returning.
        if members["source.json"] != _sha256(source_bytes):
            raise AssertionError("origin report source digest does not match source bytes")
        if hashlib.sha256(python_bytes).hexdigest() != members["workflow.py"][7:]:
            raise AssertionError("origin report Python digest does not match emitted bytes")
        if hashlib.sha256(companion_bytes).hexdigest() != members["workflow.vibe.json"][7:]:
            raise AssertionError("origin report companion digest does not match emitted bytes")

    return ImportArtifacts(
        source_bytes=source_bytes,
        python_bytes=python_bytes,
        companion_bytes=companion_bytes,
        report=origin_report,
    )


__all__ = ["ImportArtifacts", "import_workflow_bytes"]
