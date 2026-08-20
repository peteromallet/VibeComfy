"""LLM ingest helpers for generating structured workflow summaries.

Design (SD1/SD2):
- Only ``title``, ``description``, and ``tags`` are LLM-generated.
- Deterministic fields are computed by ``vibecomfy.analysis.workflow_summary``.
- Summaries are cached by input-hash + prompt-version to avoid redundant LLM calls.
- On LLM failure, returns ``None`` and logs a warning — never raises.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Bump this when the prompt format changes to invalidate cached summaries.
_PROMPT_VERSION = "1"

# Max token budget for the compact workflow representation sent to the LLM.
_MAX_COMPACT_TOKENS_ESTIMATE = 2048

# Known core ComfyUI node classes — the LLM is told to treat anything not
# in this list as a custom node.
_CORE_NODE_HINTS: list[str] = [
    "CheckpointLoaderSimple", "CLIPTextEncode", "KSampler",
    "VAELoader", "VAEDecode", "SaveImage", "PreviewImage",
    "LoadImage", "EmptyLatentImage", "KSamplerSelect",
    "CLIPLoader", "UNETLoader", "VAEEncode", "ModelSamplingSD3",
    "LoraLoaderModelOnly", "ControlNetApply", "ControlNetApplyAdvanced",
    "ImageScale", "ImageUpscaleWithModel", "ConditioningCombine",
    "ConditioningAverage", "SetLatentNoiseMask", "PadImageForOutpaint",
]

_PROMPT_TEMPLATE = """You are a ComfyUI workflow analyst. Given the compact workflow representation below, produce a structured summary as JSON.

Return ONLY valid JSON with exactly these fields:
- title: short, human-readable name (<=80 chars)
- description: 1-2 sentences describing what the workflow does
- tags: list of 3-10 lowercase kebab-case searchable tags

Workflow data:
{compact_json}

Rules:
- Be concise and factual. Do not invent details not present in the data.
- Infer purpose from node classes and output types.
- A node class is "custom" if not in this core list: {core_nodes}
- Do NOT include markdown, code fences, or any text outside the JSON object.
"""


def build_compact_prompt(workflow: Any) -> str:
    """Build a minimal-token prompt for the LLM summarizer.

    Extracts a lightweight, structured representation of *workflow* (a
    ``VibeWorkflow`` or a dict with expected corpus-json keys) and formats
    it into an LLM prompt that requests a JSON summary.

    Parameters
    ----------
    workflow : VibeWorkflow or dict
        The workflow to summarize.

    Returns
    -------
    str
        A prompt string suitable for sending to an LLM.
    """
    compact = _build_compact_repr(workflow)
    compact_json = json.dumps(compact, indent=2, ensure_ascii=False, default=str)
    # Truncate if needed.
    if len(compact_json) > _MAX_COMPACT_TOKENS_ESTIMATE * 4:
        compact_json = compact_json[:_MAX_COMPACT_TOKENS_ESTIMATE * 4] + "\n..."
    return _PROMPT_TEMPLATE.format(
        compact_json=compact_json,
        core_nodes=", ".join(_CORE_NODE_HINTS),
    )


def summarize_workflow(
    workflow: Any,
    *,
    llm_client: Any = None,
    cache_dir: str | None = None,
) -> dict[str, Any] | None:
    """Generate a structured summary for *workflow* via LLM.

    Combines deterministic analysis (from ``vibecomfy.analysis``) with
    LLM-generated semantic fields (title, description, tags).  Results are
    cached by a hash of the workflow inputs + prompt version so identical
    workflows are never re-summarized.

    Parameters
    ----------
    workflow : VibeWorkflow or dict
        The workflow to summarize.
    llm_client : optional
        An LLM client with a ``complete(prompt: str) -> str`` method.
        If ``None``, a warning is logged and ``None`` is returned.
    cache_dir : str or None
        Directory for on-disk cache.  If ``None``, caching is in-memory only.

    Returns
    -------
    dict or None
        A ``WorkflowSummary``-compatible dict on success, or ``None`` if
        the LLM is unavailable or the response cannot be parsed.
    """
    from vibecomfy.analysis.workflow_summary import (
        compute_complexity_score,
        derive_flags,
        detect_custom_nodes,
        infer_media_type,
        infer_task_type,
    )

    # Compute deterministic fields first — these never depend on the LLM.
    task_type = infer_task_type(workflow)
    media_type = infer_media_type(workflow)
    flags = derive_flags(workflow)
    complexity = compute_complexity_score(workflow)
    custom_nodes = detect_custom_nodes(workflow)

    # Build the LLM prompt for semantic fields.
    prompt = build_compact_prompt(workflow)

    # Check cache.
    cache_key = _compute_cache_key(prompt)
    cached = _cache_get(cache_key, cache_dir)
    if cached is not None:
        return {
            "title": cached.get("title", ""),
            "description": cached.get("description", ""),
            "tags": cached.get("tags", []),
            "task_type": task_type,
            "media_type": media_type,
            "flags": flags,
            "complexity": complexity,
        }

    # LLM call with graceful degradation.
    if llm_client is None:
        logger.warning(
            "summarize_workflow: no LLM client provided; returning deterministic "
            "fields only (title/description/tags will be empty)."
        )
        return {
            "title": "",
            "description": "",
            "tags": [],
            "task_type": task_type,
            "media_type": media_type,
            "flags": flags,
            "complexity": complexity,
        }

    try:
        raw_response = llm_client.complete(prompt)
    except Exception as exc:
        logger.warning(
            "summarize_workflow: LLM call failed (%s); returning None.", exc
        )
        return None

    parsed = _extract_json(raw_response)
    if parsed is None:
        logger.warning(
            "summarize_workflow: failed to parse JSON from LLM response; "
            "returning None. Raw (first 200 chars): %r",
            raw_response[:200] if raw_response else "<empty>",
        )
        return None

    # Validate required fields.
    if not _is_valid_llm_summary(parsed):
        logger.warning(
            "summarize_workflow: LLM response missing required fields; "
            "returning None. Parsed keys: %s",
            sorted(parsed.keys()) if isinstance(parsed, dict) else type(parsed),
        )
        return None

    result = {
        "title": str(parsed.get("title", "")),
        "description": str(parsed.get("description", "")),
        "tags": _coerce_str_list(parsed.get("tags")),
        "task_type": task_type,
        "media_type": media_type,
        "flags": flags,
        "complexity": complexity,
    }

    # Write through cache.
    _cache_put(cache_key, {
        "title": result["title"],
        "description": result["description"],
        "tags": result["tags"],
    }, cache_dir)

    return result


# ── internal helpers ────────────────────────────────────────────────────

def _build_compact_repr(workflow: Any) -> dict[str, Any]:
    """Extract a lightweight structured representation from a workflow.

    Accepts both ``VibeWorkflow`` objects and plain dicts (corpus JSON shape).
    """
    if isinstance(workflow, dict):
        from vibecomfy.ingest.normalize import from_api, from_envelope, from_ui

        try:
            try:
                workflow = from_envelope(workflow)
            except (TypeError, ValueError):
                try:
                    workflow = from_ui(workflow, use_comfy_converter=False)
                except (TypeError, ValueError):
                    workflow = from_api(workflow)
        except (TypeError, ValueError):
            return {
                "node_classes": {},
                "node_count": 0,
                "edge_count": 0,
                "outputs": [],
                "models": [],
                "custom_nodes_req": [],
            }

    # VibeWorkflow (or any IR object ingested through the named doors).
    if hasattr(workflow, "nodes") and hasattr(workflow, "outputs"):
        node_classes: dict[str, int] = {}
        for node in workflow.nodes.values():
            ct = node.class_type
            node_classes[ct] = node_classes.get(ct, 0) + 1

        output_types: list[str] = [
            o.output_type for o in workflow.outputs
        ]

        models: list[str] = list(workflow.requirements.models)
        custom_nodes_req: list[str] = list(workflow.requirements.custom_nodes)

        return {
            "node_classes": node_classes,
            "node_count": len(workflow.nodes),
            "edge_count": len(workflow.edges),
            "outputs": output_types[:20],
            "models": models[:10],
            "custom_nodes_req": custom_nodes_req[:20],
        }

    # Fallback.
    return {"error": "unknown workflow format"}


def _compute_cache_key(prompt: str) -> str:
    """Compute a stable cache key from the prompt and version."""
    h = hashlib.sha256()
    h.update(_PROMPT_VERSION.encode())
    h.update(prompt.encode())
    return h.hexdigest()


# ── In-memory cache (simplest; on-disk is add-on) ──────────────────────
_cache: dict[str, dict[str, Any]] = {}


def _cache_get(key: str, cache_dir: str | None = None) -> dict[str, Any] | None:
    """Retrieve a cached LLM response."""
    if key in _cache:
        return _cache[key]
    if cache_dir is not None:
        from pathlib import Path
        cache_path = Path(cache_dir) / f"{key}.json"
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                _cache[key] = data
                return data
            except (json.JSONDecodeError, OSError):
                pass
    return None


def _cache_put(
    key: str, data: dict[str, Any], cache_dir: str | None = None
) -> None:
    """Store a cached LLM response."""
    _cache[key] = data
    if cache_dir is not None:
        from pathlib import Path
        cache_path = Path(cache_dir) / f"{key}.json"
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to write cache file %s: %s", cache_path, exc)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a model response."""
    if not text:
        return None
    text = text.strip()
    # Strip markdown code fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: find the first {...} block.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _is_valid_llm_summary(data: dict[str, Any]) -> bool:
    """Check that the LLM response has the required fields."""
    if not isinstance(data, dict):
        return False
    required = {"title", "description"}
    return required.issubset(data.keys())


def _coerce_str_list(value: Any) -> list[str]:
    """Coerce a value to a list of strings."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]
