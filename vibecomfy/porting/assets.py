from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from vibecomfy.model_assets import _node_class_type, _strip_download_true, _subdir_for_model
from vibecomfy.porting.report import AssetCandidate, AssetCheckResult, PortIssue


from vibecomfy.ingest.normalize import door_get_nodes
_MODEL_NAME_SUFFIXES = (
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".gguf",
    ".onnx",
)

_MODEL_INPUT_KEY_HINTS = (
    "model",
    "ckpt",
    "checkpoint",
    "unet",
    "vae",
    "clip",
    "lora",
    "controlnet",
    "encoder",
)


@dataclass(slots=True)
class AssetAnalysis:
    candidates: list[AssetCandidate] = field(default_factory=list)
    diagnostics: list[PortIssue] = field(default_factory=list)
    checks: list[AssetCheckResult] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.to_json() for candidate in self.candidates],
            "diagnostics": [diagnostic.to_json() for diagnostic in self.diagnostics],
            "checks": [check.to_json() for check in self.checks],
        }


def analyze_model_assets(
    *,
    raw_workflow: Mapping[str, Any] | None = None,
    api_prompt: Mapping[str, Any] | None = None,
    scratchpad_path: str | Path | None = None,
    ready_metadata: Mapping[str, Any] | None = None,
    ready_requirements: Mapping[str, Any] | None = None,
    head_check: bool = False,
    head_client: Callable[[str, float], Any] | None = None,
    head_timeout_seconds: float = 5.0,
) -> AssetAnalysis:
    candidates: list[AssetCandidate] = []
    if raw_workflow is not None:
        candidates.extend(candidates_from_raw_workflow(raw_workflow))
    if api_prompt is not None:
        candidates.extend(candidates_from_api_prompt(api_prompt))
    if scratchpad_path is not None:
        metadata, requirements = metadata_from_python_module(scratchpad_path)
        candidates.extend(candidates_from_ready_metadata(metadata, source="scratchpad_metadata"))
        candidates.extend(candidates_from_ready_requirements(requirements, source="scratchpad_ready_requirements"))
    if ready_metadata is not None:
        candidates.extend(candidates_from_ready_metadata(ready_metadata, source="ready_metadata"))
    if ready_requirements is not None:
        candidates.extend(candidates_from_ready_requirements(ready_requirements, source="ready_requirements"))

    merged = _merge_candidates(candidates)
    checks = check_asset_urls(
        merged,
        head_client=head_client,
        timeout_seconds=head_timeout_seconds,
    ) if head_check else []
    diagnostics = filename_only_warnings(merged)
    diagnostics.extend(head_check_warnings(checks))
    return AssetAnalysis(candidates=merged, diagnostics=diagnostics, checks=checks)


def check_asset_urls(
    candidates: Iterable[AssetCandidate],
    *,
    head_client: Callable[[str, float], Any] | None = None,
    timeout_seconds: float = 5.0,
) -> list[AssetCheckResult]:
    client = head_client or _default_head_client
    by_url: dict[str, list[AssetCandidate]] = {}
    for candidate in candidates:
        if candidate.url:
            by_url.setdefault(candidate.url, []).append(candidate)

    results: list[AssetCheckResult] = []
    for url, url_candidates in sorted(by_url.items()):
        started = time.monotonic()
        try:
            response = client(url, timeout_seconds)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            raw_status = response.get("status_code") if isinstance(response, Mapping) else getattr(response, "status_code")
            status_code = int(raw_status)
            final_url = getattr(response, "url", None)
            if final_url is None and isinstance(response, Mapping):
                final_url = response.get("url") or response.get("final_url")
            final_url_value = str(final_url) if final_url is not None else url
            ok = 200 <= status_code < 400
            results.append(
                AssetCheckResult(
                    url=url,
                    ok=ok,
                    status_code=status_code,
                    final_url=final_url_value,
                    elapsed_ms=elapsed_ms,
                    error=None if ok else _status_error(status_code),
                    detail={
                        "candidate_names": sorted({candidate.name for candidate in url_candidates}),
                        "duplicate_count": len(url_candidates),
                    },
                )
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            status_code = getattr(exc, "code", None)
            error = _status_error(int(status_code)) if status_code is not None else f"{type(exc).__name__}: {exc}"
            results.append(
                AssetCheckResult(
                    url=url,
                    ok=False,
                    status_code=int(status_code) if status_code is not None else None,
                    elapsed_ms=elapsed_ms,
                    error=error,
                    detail={
                        "candidate_names": sorted({candidate.name for candidate in url_candidates}),
                        "duplicate_count": len(url_candidates),
                    },
                )
            )
    return results


def head_check_warnings(checks: Iterable[AssetCheckResult]) -> list[PortIssue]:
    warnings: list[PortIssue] = []
    for check in checks:
        if check.ok:
            continue
        warnings.append(
            PortIssue(
                code="model_asset_head_check_failed",
                message=f"Model asset URL HEAD check failed for {check.url!r}.",
                severity="warning",
                detail={
                    "url": check.url,
                    "status_code": check.status_code,
                    "final_url": check.final_url,
                    "error": check.error,
                    **check.detail,
                },
                recommendation="Verify the model URL is public, license-accessible, and not returning 404 before RunPod validation.",
            )
        )
    return warnings


def candidates_from_raw_workflow(raw: Mapping[str, Any]) -> list[AssetCandidate]:
    candidates: list[AssetCandidate] = []
    for node in _iter_workflow_nodes(raw):
        properties = node.get("properties", {})
        if not isinstance(properties, Mapping):
            continue
        models = properties.get("models", [])
        if not isinstance(models, list):
            continue
        class_type = _node_class_type(node)
        node_id = node.get("id")
        for model in models:
            candidate = _candidate_from_model_entry(
                model,
                source="ui_properties",
                class_type=class_type,
                node_id=str(node_id) if node_id is not None else None,
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def candidates_from_api_prompt(api_prompt: Mapping[str, Any]) -> list[AssetCandidate]:
    candidates: list[AssetCandidate] = []
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _node_sort_key(item[0])):
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        if not isinstance(class_type, str) or not isinstance(inputs, Mapping):
            continue
        for key, value in inputs.items():
            if not isinstance(value, str) or not _looks_like_model_input(key, value):
                continue
            candidates.append(
                AssetCandidate(
                    name=value,
                    source="api_prompt",
                    subdir=_subdir_for_model({"name": value}, class_type=class_type, url=""),
                    node_id=str(node_id),
                    class_type=class_type,
                    metadata={"input": key},
                )
            )
    return candidates


def candidates_from_ready_metadata(metadata: Mapping[str, Any], *, source: str = "ready_metadata") -> list[AssetCandidate]:
    models = metadata.get("model_assets", [])
    if not isinstance(models, list):
        return []
    return [
        candidate
        for candidate in (
            _candidate_from_model_entry(model, source=source, class_type="", node_id=None)
            for model in models
        )
        if candidate is not None
    ]


def candidates_from_ready_requirements(requirements: Mapping[str, Any], *, source: str = "ready_requirements") -> list[AssetCandidate]:
    models = requirements.get("models", [])
    if not isinstance(models, list):
        return []
    return [
        candidate
        for candidate in (
            _candidate_from_model_entry(model, source=source, class_type="", node_id=None)
            for model in models
        )
        if candidate is not None
    ]


def metadata_from_python_module(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    module_ast = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    metadata: dict[str, Any] = {}
    requirements: dict[str, Any] = {}
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
        if "READY_METADATA" in names:
            if isinstance(value, Mapping):
                metadata = dict(value)
        if "READY_REQUIREMENTS" in names:
            if isinstance(value, Mapping):
                requirements = dict(value)
    return metadata, requirements


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


def filename_only_warnings(candidates: Iterable[AssetCandidate]) -> list[PortIssue]:
    warnings: list[PortIssue] = []
    for candidate in candidates:
        if candidate.url:
            continue
        warnings.append(
            PortIssue(
                code="filename_only_asset_candidate",
                message=f"Model asset candidate {candidate.name!r} has no source URL.",
                severity="warning",
                node_id=candidate.node_id,
                class_type=candidate.class_type,
                detail={
                    "name": candidate.name,
                    "source": candidate.source,
                    "subdir": candidate.subdir,
                    **candidate.metadata,
                },
                recommendation="Add a URL-bearing model asset entry before fetch, staging, or RunPod validation.",
            )
        )
    return warnings


def _candidate_from_model_entry(
    model: Any,
    *,
    source: str,
    class_type: str,
    node_id: str | None,
) -> AssetCandidate | None:
    if isinstance(model, str):
        name = model
        if not _looks_like_model_filename(name):
            return None
        return AssetCandidate(
            name=name,
            source=source,
            subdir=_subdir_for_model({"name": name}, class_type=class_type, url=""),
            node_id=node_id,
            class_type=class_type or None,
        )
    if not isinstance(model, Mapping):
        return None
    name = model.get("name")
    if not isinstance(name, str) or not name:
        return None
    url = model.get("url")
    url_value = _strip_download_true(url) if isinstance(url, str) and url else None
    subdir = _subdir_for_model(model, class_type=class_type, url=url_value or "")
    metadata = {
        key: value
        for key, value in model.items()
        if key not in {"name", "url", "subdir", "directory"}
    }
    return AssetCandidate(
        name=name,
        url=url_value,
        subdir=subdir,
        source=source,
        node_id=node_id,
        class_type=class_type or None,
        metadata=metadata,
    )


def _merge_candidates(candidates: Iterable[AssetCandidate]) -> list[AssetCandidate]:
    merged: dict[tuple[str, str | None, str | None], AssetCandidate] = {}
    for candidate in candidates:
        key = (candidate.name, candidate.url, candidate.subdir)
        existing = merged.get(key)
        if existing is None:
            candidate.metadata.setdefault("sources", [candidate.source])
            merged[key] = candidate
            continue
        sources = list(existing.metadata.get("sources", [existing.source]))
        if candidate.source not in sources:
            sources.append(candidate.source)
        existing.metadata["sources"] = sources
        if existing.node_id is None and candidate.node_id is not None:
            existing.node_id = candidate.node_id
        if existing.class_type is None and candidate.class_type is not None:
            existing.class_type = candidate.class_type
        existing.metadata.update({key: value for key, value in candidate.metadata.items() if key != "sources"})
    return sorted(merged.values(), key=lambda candidate: (candidate.name, candidate.subdir or "", candidate.url or ""))


def _looks_like_model_input(key: str, value: str) -> bool:
    lowered_key = key.lower()
    return _looks_like_model_filename(value) and any(hint in lowered_key for hint in _MODEL_INPUT_KEY_HINTS)


def _looks_like_model_filename(value: str) -> bool:
    lowered = value.lower()
    return any(lowered.endswith(suffix) for suffix in _MODEL_NAME_SUFFIXES)


def _status_error(status_code: int) -> str:
    if status_code == 404:
        return "not_found"
    if status_code in {401, 403}:
        return "license_gated_or_forbidden"
    if 300 <= status_code < 400:
        return "redirect_not_followed"
    return f"http_status_{status_code}"


def _default_head_client(url: str, timeout_seconds: float) -> Any:
    import urllib.request

    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return {
            "status_code": int(response.status),
            "url": response.geturl(),
        }


def _iter_workflow_nodes(raw: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield from _sorted_node_values(door_get_nodes(raw))
    definitions = raw.get("definitions", {})
    if not isinstance(definitions, Mapping):
        return
    subgraphs = definitions.get("subgraphs", [])
    if not isinstance(subgraphs, list):
        return
    for subgraph in subgraphs:
        if isinstance(subgraph, Mapping):
            yield from _iter_workflow_nodes(subgraph)


def _sorted_node_values(nodes: Any) -> list[Mapping[str, Any]]:
    if isinstance(nodes, Mapping):
        values = nodes.values()
    elif isinstance(nodes, list):
        values = nodes
    else:
        return []
    return sorted(
        [node for node in values if isinstance(node, Mapping)],
        key=lambda node: _node_sort_key(node.get("id")),
    )


def _node_sort_key(node_id: Any) -> tuple[int, str]:
    try:
        return (int(node_id), str(node_id))
    except (TypeError, ValueError):
        return (10**12, str(node_id))


__all__ = [
    "AssetAnalysis",
    "analyze_model_assets",
    "check_asset_urls",
    "candidates_from_api_prompt",
    "candidates_from_raw_workflow",
    "candidates_from_ready_metadata",
    "candidates_from_ready_requirements",
    "filename_only_warnings",
    "head_check_warnings",
    "metadata_from_python_module",
]
