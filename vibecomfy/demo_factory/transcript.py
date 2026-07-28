"""Transcript run_dir loader for demo_factory.

Loads a transcript run_dir containing original.ui.json (broken),
candidate.ui.json (repaired), request.json (user inquiry), and
metadata files.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranscriptRunDir:
    """A single transcript run_dir with golden/broken graphs and inquiry.

    Attributes
    ----------
    run_dir:
        Path to the transcript directory.
    golden:
        The repaired UI graph (candidate.ui.json).
    broken:
        The original broken UI graph (original.ui.json).
    inquiry:
        The user's original inquiry (request.json).
    classification:
        Optional classification metadata.
    flow_metadata:
        Optional flow metadata.
    """
    run_dir: Path
    golden: dict[str, Any]
    broken: dict[str, Any]
    inquiry: str
    classification: dict[str, Any] = field(default_factory=dict)
    flow_metadata: dict[str, Any] = field(default_factory=dict)


def load_transcript_run_dir(run_dir: Path | str) -> TranscriptRunDir:
    """Load a transcript run_dir into a structured object.

    Parameters
    ----------
    run_dir:
        Path to a transcript directory containing at minimum:
        - candidate.ui.json (repaired/golden graph)
        - original.ui.json (broken graph)
        - request.json (user inquiry)

    Returns
    -------
    TranscriptRunDir
        Structured transcript data.

    Raises
    ------
    FileNotFoundError
        If required files are missing.
    ValueError
        If JSON files are malformed or missing required fields.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Transcript directory not found: {run_dir}")

    # Load golden (repaired) graph
    golden_path = run_dir / "candidate.ui.json"
    if not golden_path.is_file():
        raise FileNotFoundError(f"Missing candidate.ui.json in {run_dir}")
    try:
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {golden_path}: {exc}") from exc

    # Load broken graph
    broken_path = run_dir / "original.ui.json"
    if not broken_path.is_file():
        raise FileNotFoundError(f"Missing original.ui.json in {run_dir}")
    try:
        broken = json.loads(broken_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {broken_path}: {exc}") from exc

    # Load inquiry
    request_path = run_dir / "request.json"
    if not request_path.is_file():
        raise FileNotFoundError(f"Missing request.json in {run_dir}")
    try:
        request_data = json.loads(request_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {request_path}: {exc}") from exc

    # Extract inquiry text from request
    inquiry = ""
    if isinstance(request_data, dict):
        # Try common keys
        inquiry = (
            request_data.get("query", "")
            or request_data.get("prompt", "")
            or request_data.get("request", "")
            or request_data.get("message", "")
            or str(request_data)
        )
    else:
        inquiry = str(request_data)

    # Load optional metadata
    classification_path = run_dir / "classification.json"
    classification = {}
    if classification_path.is_file():
        try:
            classification = json.loads(classification_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    flow_metadata_path = run_dir / "flow_metadata.json"
    flow_metadata = {}
    if flow_metadata_path.is_file():
        try:
            flow_metadata = json.loads(flow_metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    return TranscriptRunDir(
        run_dir=run_dir,
        golden=golden,
        broken=broken,
        inquiry=inquiry.strip(),
        classification=classification,
        flow_metadata=flow_metadata,
    )
