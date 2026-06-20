from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from vibecomfy._compile._graph import node_id_sort_key


HF_SPLIT_FILES_DIRS = {
    "text_encoders",
    "diffusion_models",
    "vae",
    "clip_vision",
    "loras",
    "latent_upscale_models",
    "controlnet",
    "checkpoints",
    "unet",
}

_CLASS_TYPE_SUBDIRS = {
    "CheckpointLoaderSimple": "checkpoints",
    "CLIPLoader": "text_encoders",
    "DualCLIPLoaderGGUF": "text_encoders",
    "VAELoader": "vae",
    "VAELoaderKJ": "vae",
    "LoraLoader": "loras",
    "LoraLoaderModelOnly": "loras",
    "ControlNetLoader": "controlnet",
    "UNETLoader": "diffusion_models",
    "UnetLoaderGGUF": "diffusion_models",
}

_MODEL_INPUT_SUBDIRS = {
    "ckpt_name": "checkpoints",
    "clip_name": "text_encoders",
    "clip_name1": "text_encoders",
    "clip_name2": "text_encoders",
    "lora_name": "loras",
    "model_name": "diffusion_models",
    "text_encoder": "text_encoders",
    "unet_name": "diffusion_models",
    "upscale_model": "upscale_models",
    "vae_name": "vae",
}

_CLASS_FIELD_SUBDIRS = {
    ("CLIPVisionLoader", "clip_name"): "clip_vision",
    ("LatentUpscaleModelLoader", "model_name"): "latent_upscale_models",
    ("LoadWanVideoT5TextEncoder", "model_name"): "text_encoders",
    ("WanVideoTextEncodeCached", "model_name"): "text_encoders",
    ("WanVideoVAELoader", "model_name"): "vae",
    ("WanVideoModelLoader", "model_name"): "diffusion_models",
    ("WanVideoLoraSelect", "lora"): "loras",
    ("WanVideoLoraSelectMulti", "lora"): "loras",
}

if TYPE_CHECKING:
    from vibecomfy.registry.models_loader import ModelEntry
    from vibecomfy.workflow import VibeWorkflow

_HF_SPLIT_FILES_RE = re.compile(r"/split_files/([^/]+)/[^/]+$")


def extract_from_raw_workflow(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract structured model asset entries from a ComfyUI workflow JSON object."""

    if not isinstance(raw, Mapping):
        return []
    has_nodes = bool(raw.get("nodes"))
    has_subgraphs = bool(_subgraphs(raw))
    if not has_nodes and not has_subgraphs:
        return []

    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for node in _iter_workflow_nodes(raw):
        for entry in _entries_from_node(node):
            key = (entry["name"], entry["subdir"])
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    return entries


def entries_from_scratchpad_path(path: str | Path) -> list[dict[str, Any]]:
    """Read structured model assets from a materialized ready scratchpad."""

    module_ast = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    constants: dict[str, Any] = {}
    for node in module_ast.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        try:
            value = _literal_eval_with_constants(node.value, constants)
        except (ValueError, TypeError):
            continue
        for name in names:
            constants[name] = value
        if "READY_REQUIREMENTS" not in names:
            continue
        requirements = value
        if not isinstance(requirements, Mapping):
            return []
        models = requirements.get("models", [])
        if not isinstance(models, list):
            return []
        return _normalise_requirement_entries(models)
    return []


def resolve_referenced_assets(
    workflow: VibeWorkflow,
    *,
    registry: Sequence[ModelEntry] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve model-picker inputs in a built workflow to downloadable assets.

    Authored ``model_assets`` is still the preferred place for bespoke URLs, but
    runtime workflows can patch model picker fields dynamically. This resolver
    prevents those final values from drifting away from the files staged by
    ``--ensure-models``.
    """
    from vibecomfy.registry.models_loader import load_registry

    entries = tuple(registry) if registry is not None else load_registry()
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for reference in _referenced_model_values(workflow):
        asset = _asset_for_reference(reference, registry=entries)
        if asset is None:
            unresolved.append(_unresolved_asset_for_reference(reference))
            continue
        key = (asset["name"], asset["subdir"])
        if key in seen:
            continue
        seen.add(key)
        resolved.append(asset)
    return resolved, unresolved


def _literal_eval_with_constants(node: ast.AST, constants: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.Dict):
        return {
            _literal_eval_with_constants(key, constants): _literal_eval_with_constants(value, constants)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.List):
        return [_literal_eval_with_constants(element, constants) for element in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_eval_with_constants(element, constants) for element in node.elts)
    return ast.literal_eval(node)


def _entries_from_node(node: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    properties = node.get("properties", {})
    if not isinstance(properties, Mapping):
        return []
    models = properties.get("models", [])
    if not isinstance(models, list):
        return []
    class_type = _node_class_type(node)
    entries: list[dict[str, Any]] = []
    for model in models:
        entry = _normalise_model_entry(model, class_type=class_type)
        if entry is not None:
            entries.append(entry)
    return entries


def _referenced_model_values(workflow: VibeWorkflow) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for node in workflow.runtime_nodes().values():
        for field, value in node.inputs.items():
            subdir = _subdir_for_model_reference(node.class_type, field)
            if subdir is None or not isinstance(value, str) or not value:
                continue
            if _is_none_model_value(value):
                continue
            key = (node.id, node.class_type, field, value)
            if key in seen:
                continue
            seen.add(key)
            references.append(
                {
                    "node_id": node.id,
                    "class_type": node.class_type,
                    "field": field,
                    "value": value,
                    "subdir": subdir,
                }
            )
    return references


def _subdir_for_model_reference(class_type: str, field: str) -> str | None:
    return _CLASS_FIELD_SUBDIRS.get((class_type, field), _MODEL_INPUT_SUBDIRS.get(field))


def _asset_for_reference(
    reference: Mapping[str, str],
    *,
    registry: Sequence[ModelEntry],
) -> dict[str, Any] | None:
    value = reference["value"].replace("\\", "/")
    subdir = reference["subdir"].replace("\\", "/")
    expected_paths = {f"{subdir}/{value}", f"{subdir}/{Path(value).name}"}
    for entry in registry:
        for target in entry.targets:
            target_path = target.path.replace("\\", "/")
            if target_path not in expected_paths and not (
                target_path.startswith(f"{subdir}/") and target_path.endswith(f"/{value}")
            ):
                continue
            url = _url_for_registry_entry(entry)
            if not url:
                return None
            if target_path.startswith(f"{subdir}/"):
                name = target_path[len(subdir) + 1 :]
                asset_subdir = subdir
            else:
                name = Path(target_path).name
                asset_subdir = str(Path(target_path).parent)
            asset: dict[str, Any] = {"name": name, "url": url, "subdir": asset_subdir}
            if getattr(entry, "sha256", None):
                asset["sha256"] = entry.sha256
            if getattr(entry, "size_bytes", None) is not None:
                asset["size_bytes"] = entry.size_bytes
            revision = getattr(entry.source, "revision", None)
            if revision:
                asset["hf_revision"] = revision
            asset.update(_reference_metadata(reference, reference_type="registry-backed", downloadable=True))
            return asset
    return None


def _url_for_registry_entry(entry: ModelEntry) -> str | None:
    source = entry.source
    if source.url:
        return source.url
    if source.kind == "huggingface" and source.repo and source.filename:
        revision = getattr(source, "revision", None) or "main"
        return f"https://huggingface.co/{source.repo}/resolve/{revision}/{source.filename}"
    return None


def _is_none_model_value(value: str) -> bool:
    return value in {"none", "None"}


def _looks_like_runtime_input(value: str) -> bool:
    return value.startswith(("http://", "https://", "/", "./", "../")) or value in {"none", "None"}


def _unresolved_asset_for_reference(reference: Mapping[str, str]) -> dict[str, str | bool]:
    value = reference["value"]
    return {
        "name": value,
        "subdir": reference["subdir"],
        **_reference_metadata(
            reference,
            reference_type=_model_reference_type(value),
            downloadable=False,
        ),
        "unresolved": True,
    }


def _reference_metadata(
    reference: Mapping[str, str],
    *,
    reference_type: str,
    downloadable: bool,
) -> dict[str, str | bool]:
    return {
        "node_id": reference["node_id"],
        "class_type": reference["class_type"],
        "field": reference["field"],
        "value": reference["value"],
        "reference_type": reference_type,
        "downloadable": downloadable,
    }


def _model_reference_type(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return "external-url"
    if value.startswith("/") or value.startswith("\\\\") or re.match(r"^[A-Za-z]:[\\/]", value):
        return "absolute-path"
    return "relative-path"


def _normalise_requirement_entries(models: Iterable[Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for model in models:
        if not isinstance(model, Mapping):
            continue
        entry = _normalise_model_entry(model, class_type="")
        if entry is None:
            continue
        key = (entry["name"], entry["subdir"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    return entries


def _normalise_model_entry(model: Any, *, class_type: str) -> dict[str, Any] | None:
    if not isinstance(model, Mapping):
        return None
    name = model.get("name")
    url = model.get("url")
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(url, str) or not url:
        return None
    subdir = _subdir_for_model(model, class_type=class_type, url=url)
    entry: dict[str, Any] = {"name": name, "url": _strip_download_true(url), "subdir": subdir}
    target_path = model.get("target_path")
    if isinstance(target_path, str) and target_path:
        entry["target_path"] = target_path
    sha256 = model.get("sha256")
    if isinstance(sha256, str) and sha256:
        entry["sha256"] = sha256
    hf_revision = model.get("hf_revision") or model.get("revision")
    if isinstance(hf_revision, str) and hf_revision:
        entry["hf_revision"] = hf_revision
    size_bytes = model.get("size_bytes")
    if isinstance(size_bytes, int) and size_bytes >= 0:
        entry["size_bytes"] = size_bytes
    if model.get("gated") is True:
        entry["gated"] = True
    return entry


def _subdir_for_model(model: Mapping[str, Any], *, class_type: str, url: str) -> str:
    directory = model.get("directory")
    if isinstance(directory, str) and directory:
        return directory
    subdir = model.get("subdir")
    if isinstance(subdir, str) and subdir:
        return subdir
    split_subdir = _hf_split_files_subdir(url)
    if split_subdir is not None:
        return split_subdir
    return _CLASS_TYPE_SUBDIRS.get(class_type, "checkpoints")


def _hf_split_files_subdir(url: str) -> str | None:
    path = urlsplit(url).path
    match = _HF_SPLIT_FILES_RE.search(path)
    if not match:
        return None
    subdir = match.group(1)
    if subdir not in HF_SPLIT_FILES_DIRS:
        return None
    return subdir


def _strip_download_true(url: str) -> str:
    parsed = urlsplit(url)
    params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if not (key == "download" and value == "true")]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query and urlencode(params), parsed.fragment))


def _iter_workflow_nodes(raw: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield from _sorted_nodes(raw.get("nodes"))
    for subgraph in _subgraphs(raw):
        yield from _iter_workflow_nodes(subgraph)


def _subgraphs(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    definitions = raw.get("definitions", {})
    if not isinstance(definitions, Mapping):
        return []
    subgraphs = definitions.get("subgraphs", [])
    if not isinstance(subgraphs, list):
        return []
    return [subgraph for subgraph in subgraphs if isinstance(subgraph, Mapping)]


def _sorted_nodes(nodes: Any) -> list[Mapping[str, Any]]:
    if isinstance(nodes, Mapping):
        values = nodes.values()
    elif isinstance(nodes, list):
        values = nodes
    else:
        return []
    return sorted(
        [node for node in values if isinstance(node, Mapping)],
        key=lambda node: node_id_sort_key(node.get("id"), allow_compound=False),
    )


def _node_class_type(node: Mapping[str, Any]) -> str:
    for key in ("class_type", "type"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    properties = node.get("properties", {})
    if isinstance(properties, Mapping):
        value = properties.get("Node name for S&R")
        if isinstance(value, str) and value:
            return value
    return ""


__all__ = [
    "HF_SPLIT_FILES_DIRS",
    "entries_from_scratchpad_path",
    "extract_from_raw_workflow",
    "resolve_referenced_assets",
]
