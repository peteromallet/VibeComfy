from __future__ import annotations

import keyword
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from vibecomfy.porting.emitter import _compute_variable_names
from vibecomfy.workflow import VibeWorkflow


_CLASS_ALIASES: dict[str, str] = {
    "UNETLoader": "diffusion",
    "UNETLoaderGGUF": "diffusion",
    "UnetLoaderGGUF": "diffusion",
    "VAELoader": "vae",
    "CLIPLoader": "text_encoder",
    "DualCLIPLoader": "text_encoder",
    "DualCLIPLoaderGGUF": "text_encoder",
    "CLIPVisionLoader": "clip_vision",
    "LoadImage": "image",
    "LoadAudio": "audio",
    "KSampler": "sampler",
    "KSamplerAdvanced": "sampler",
    "SamplerCustomAdvanced": "sampler",
    "VAEDecode": "decoded",
    "VAEDecodeTiled": "decoded",
    "LTXVDecoder": "decoded",
    "VHS_VideoCombine": "video_output",
    "CreateVideo": "video_output",
    "SaveImage": "saveimage",
    "SaveVideo": "savevideo",
    "SaveAudio": "saveaudio",
}

_TERMINAL_OUTPUT_CLASSES: frozenset[str] = frozenset({"SaveImage", "SaveVideo", "SaveAudio", "PreviewImage"})

_DOWNSTREAM_ALIASES: dict[tuple[str, str], str] = {
    ("KSampler", "positive"): "positive_text",
    ("KSampler", "negative"): "negative_text",
    ("KSampler", "model"): "model_sampling",
    ("KSampler", "latent_image"): "latent",
    ("KSamplerAdvanced", "positive"): "positive_text",
    ("KSamplerAdvanced", "negative"): "negative_text",
    ("CFGGuider", "positive"): "positive_text",
    ("CFGGuider", "negative"): "negative_text",
    ("WanImageToVideo", "clip_vision_output"): "clip_vision_features",
    ("CreateVideo", "images"): "decoded",
    ("VHS_VideoCombine", "images"): "decoded",
    ("SaveVideo", "video"): "video_output",
    ("SaveImage", "images"): "image_output",
}

_PUBLIC_INPUT_ALIASES: dict[str, str] = {
    "prompt": "positive_text",
    "positive_prompt": "positive_text",
    "negative_prompt": "negative_text",
    "image": "image",
    "start_image": "start_image",
    "end_image": "end_image",
    "audio": "audio",
    "voice": "voice",
    "seed": "sampler",
    "steps": "sampler",
    "cfg": "sampler",
}
_GENERIC_PUBLIC_INPUT_NAMES: frozenset[str] = frozenset(
    {
        "model",
        "width",
        "height",
        "length",
        "frames",
        "fps",
        "output_fps",
        "sampler_name",
        "scheduler",
        "denoise",
    }
)


@dataclass(frozen=True, slots=True)
class NameRow:
    node_id: str
    class_type: str
    current_name: str
    proposed_name: str
    reason: str
    candidates: tuple[str, ...] = ()
    fallback: bool = False
    terminal: bool = False


def analyze_names(workflow: VibeWorkflow, *, strategy: str) -> dict[str, Any]:
    current_names = _compute_variable_names(workflow.nodes, workflow.edges)
    proposed_rows = _role_based_names(workflow, current_names)
    selected_key = "current_name" if strategy == "current" else "proposed_name"
    rows = [
        {
            "node_id": row.node_id,
            "class_type": row.class_type,
            "current_name": row.current_name,
            "proposed_name": row.proposed_name,
            "selected_name": getattr(row, selected_key),
            "reason": row.reason,
            "candidates": list(row.candidates),
            "fallback": row.fallback,
            "terminal": row.terminal,
            "renamed": row.proposed_name != row.current_name,
        }
        for row in proposed_rows
    ]
    rename_count = sum(1 for row in rows if row["renamed"])
    ambiguous_count = sum(1 for row in rows if len(row["candidates"]) > 1)
    fallback_count = sum(1 for row in rows if row["fallback"])
    return {
        "workflow": workflow.id,
        "source": {
            "id": workflow.source.id,
            "path": workflow.source.path,
            "source_type": workflow.source.source_type,
        },
        "strategy": strategy,
        "rows": rows,
        "summary": {
            "node_count": len(rows),
            "rename_count": rename_count,
            "rename_percent": round((rename_count / len(rows)) * 100) if rows else 0,
            "ambiguous_count": ambiguous_count,
            "fallback_count": fallback_count,
        },
    }


def _role_based_names(workflow: VibeWorkflow, current_names: dict[str, str]) -> list[NameRow]:
    raw: dict[str, _NameChoice] = {}
    public_names = _public_inputs_by_node(workflow)
    downstream = _downstream_by_node(workflow)
    for node_id in sorted(workflow.nodes, key=_id_sort_key):
        node = workflow.nodes[node_id]
        current_name = current_names[node_id]
        choice = _choose_role_name(node_id, node.class_type, current_name, public_names, downstream)
        raw[node_id] = choice

    counts: Counter[str] = Counter(choice.name for choice in raw.values())
    seen: Counter[str] = Counter()
    rows: list[NameRow] = []
    for node_id in sorted(workflow.nodes, key=_id_sort_key):
        choice = raw[node_id]
        seen[choice.name] += 1
        proposed = choice.name
        if counts[choice.name] > 1:
            proposed = f"{choice.name}_{seen[choice.name]}"
        rows.append(
            NameRow(
                node_id=node_id,
                class_type=workflow.nodes[node_id].class_type,
                current_name=current_names[node_id],
                proposed_name=proposed,
                reason=choice.reason,
                candidates=choice.candidates,
                fallback=choice.fallback,
                terminal=choice.terminal,
            )
        )
    return rows


@dataclass(frozen=True, slots=True)
class _NameChoice:
    name: str
    reason: str
    candidates: tuple[str, ...] = ()
    fallback: bool = False
    terminal: bool = False


def _choose_role_name(
    node_id: str,
    class_type: str,
    current_name: str,
    public_names: dict[str, list[str]],
    downstream: dict[str, list[tuple[str, str]]],
) -> _NameChoice:
    if class_type in _TERMINAL_OUTPUT_CLASSES:
        return _NameChoice(current_name, "terminal, no rename", terminal=True)

    candidates: list[tuple[str, str]] = []
    public_candidates = _public_candidates(public_names.get(node_id, []), class_type)
    if public_candidates:
        candidates.append((_best_public_candidate(public_candidates, class_type), _public_reason(public_names[node_id])))

    for target_class, target_input in downstream.get(node_id, []):
        downstream_name = _downstream_name(class_type, target_class, target_input)
        if downstream_name is not None:
            candidates.append((downstream_name, f"downstream: {target_class}.{target_input}"))

    if class_type in _CLASS_ALIASES:
        candidates.append((_CLASS_ALIASES[class_type], f"class alias: {class_type}"))

    unique = _dedupe(name for name, _reason in candidates)
    if unique:
        chosen_name, reason = candidates[0]
        return _NameChoice(_safe_name(chosen_name), reason, tuple(_safe_name(name) for name in unique))
    return _NameChoice(current_name, "class-name fallback", fallback=True)


def _public_inputs_by_node(workflow: VibeWorkflow) -> dict[str, list[str]]:
    by_node: dict[str, list[str]] = defaultdict(list)
    for name, public_input in workflow.inputs.items():
        by_node[str(public_input.node_id)].append(name)
    return {node_id: sorted(names) for node_id, names in by_node.items()}


def _downstream_by_node(workflow: VibeWorkflow) -> dict[str, list[tuple[str, str]]]:
    by_node: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in workflow.edges:
        target = workflow.nodes.get(edge.to_node)
        if target is not None:
            by_node[edge.from_node].append((target.class_type, edge.to_input))
    return {node_id: sorted(values) for node_id, values in by_node.items()}


def _downstream_name(class_type: str, target_class: str, target_input: str) -> str | None:
    if (target_class, target_input) in _DOWNSTREAM_ALIASES:
        name = _DOWNSTREAM_ALIASES[(target_class, target_input)]
        if class_type == "WanImageToVideo" and target_class == "KSampler" and target_input == "latent_image":
            return "video_setup"
    elif target_input in {"positive", "negative"}:
        name = f"{target_input}_text" if "TextEncode" in class_type else target_input
    elif target_input in {"latent_image", "images", "video", "audio"}:
        name = target_input
    else:
        return None
    if class_type == "CLIPTextEncode" and name in {"positive", "negative"}:
        return f"{name}_text"
    return name


def _public_candidates(names: list[str], class_type: str) -> list[str]:
    if class_type in {"KSampler", "KSamplerAdvanced", "SamplerCustomAdvanced"}:
        if any(name in {"seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"} for name in names):
            return ["sampler"]
    candidates: list[str] = []
    for name in names:
        if name in _GENERIC_PUBLIC_INPUT_NAMES:
            continue
        if name in _PUBLIC_INPUT_ALIASES:
            candidates.append(_PUBLIC_INPUT_ALIASES[name])
    return candidates


def _best_public_candidate(names: list[str], class_type: str) -> str:
    if class_type in {"KSampler", "KSamplerAdvanced", "SamplerCustomAdvanced"} and any(
        name in {"sampler", "seed", "steps", "cfg"} for name in names
    ):
        return "sampler"
    for preferred in ("positive_text", "negative_text", "start_image", "end_image", "image", "audio", "voice"):
        if preferred in names:
            return preferred
    return names[0]


def _public_reason(names: list[str]) -> str:
    quoted = ",".join(repr(name) for name in names)
    return f"PUBLIC_INPUTS[{quoted}]"


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _safe_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", value.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _id_sort_key(node_id: str) -> tuple[Any, ...]:
    parts = str(node_id).split(":")
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, str(node_id))
