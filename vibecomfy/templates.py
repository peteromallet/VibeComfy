from __future__ import annotations

import warnings
import json
import re
import tomllib
from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from vibecomfy.handles import Handle
from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_input, bind_output, ready_node, ready_workflow
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeInput, VibeWorkflow
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.workflow_context import _current_workflow_or_raise


_OUTPUT_KIND_HEURISTIC: dict[str, str] = {
    "SaveImage": "image",
    "PreviewImage": "image",
    "SaveVideo": "video",
    "VHS_VideoCombine": "video",
    "CreateVideo": "video",
    "SaveAudio": "audio",
    "SaveAudioMP3": "audio",
    "PreviewAudio": "audio",
}

_MODEL_DISAGREEMENT_WARNED = False
_SYMBOLIC_REF_DEPRECATION_WARNED = False
_FILENAME_KWARGS = frozenset({
    "unet_name",
    "vae_name",
    "clip_name",
    "clip_name1",
    "clip_name2",
    "lora_name",
    "ckpt_name",
})


def _category_qualified_template_id(template_id: str, source_path: str | None) -> str:
    if "/" in template_id or not source_path:
        return template_id
    path = Path(source_path)
    if path.parent.name and path.parent.parent.name == "ready_templates":
        return f"{path.parent.name}/{template_id}"
    return template_id


def _derive_output_kind(class_type: str | None) -> str | None:
    if not class_type:
        return None
    if class_type in _OUTPUT_KIND_HEURISTIC:
        return _OUTPUT_KIND_HEURISTIC[class_type]
    lowered = class_type.lower()
    if "video" in lowered:
        return "video"
    if "audio" in lowered:
        return "audio"
    if "image" in lowered:
        return "image"
    return None


def new_workflow(
    metadata: Mapping[str, Any],
    *,
    source_path: str | None = None,
    source_type: str | None = None,
) -> VibeWorkflow:
    """Create a ready-template workflow and apply module metadata.

    Convenience wrapper for template authoring; for runtime use see
    ``vibecomfy.registry.ready_template``. Generated templates should pass
    ``source_path=__file__`` because the fallback here is this helper module.

    The returned workflow eagerly binds the ``workflow_context`` ContextVar so
    that subsequent ``node(...)`` / typed-wrapper calls at module body can
    discover the active workflow without an enclosing ``with`` block.
    ``finalize()`` releases the binding.  The workflow also supports use as a
    context manager (``with new_workflow(...) as wf:``) for callers that prefer
    explicit scoping.
    """
    raw_workflow_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    workflow_id = _category_qualified_template_id(raw_workflow_id, source_path)
    metadata = dict(metadata)
    metadata["ready_template"] = workflow_id
    metadata["workflow_template"] = workflow_id.rsplit("/", 1)[-1]
    provenance = metadata.get("provenance")
    wf = ready_workflow(
        workflow_id,
        source_path=source_path or __file__,
        provenance=provenance if isinstance(provenance, Mapping) else None,
    )
    wf.metadata.update(metadata)

    # Eagerly bind the ContextVar so that node()/typed-wrapper calls in the
    # caller's body can find the active workflow.  finalize() releases this
    # binding.  Skipping if the workflow is already bound (e.g. caller is using
    # ``with new_workflow(...) as wf:``); the ``with`` form will then re-bind a
    # fresh token in __enter__.
    if getattr(wf, "_workflow_context_token", None) is None:
        from vibecomfy.workflow_context import active_workflow, bind_workflow

        # Defensive: if a *different* previous workflow leaked its binding
        # (e.g. its build() raised before finalize() could release the token),
        # clear it so a brand-new template can be built.  Only do this when the
        # leaked workflow itself has no token attribute — a sign that its owner
        # has been garbage-collected and can never run __exit__.  Genuine nested
        # ``with new_workflow(...) as wf:`` blocks where the outer workflow is
        # still held by the caller will fall through to bind_workflow() and
        # raise ``Nested workflow contexts not supported``, preserving Block A's
        # contract.
        existing = active_workflow()
        if existing is not None and existing is not wf:
            existing_token = getattr(existing, "_workflow_context_token", None)
            if existing_token is None:
                from vibecomfy.workflow_context import _CURRENT_WORKFLOW

                _CURRENT_WORKFLOW.set(None)

        wf._workflow_context_token = bind_workflow(wf)

    return wf


def node(
    *args: Any,
    _id: str | None = None,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a ready-template node.

    v2.6.4 Fix 5: ``wf`` is now optional — reads from the ContextVar set by
    ``new_workflow(...)`` when omitted. This matches the typed-wrapper
    convention, so ``raw_call('<uuid>', '<id>', ...)`` works inside a
    ``with new_workflow(...) as wf:`` block without passing ``wf`` explicitly.

    Backward compat: legacy ``node(wf, class_type, source_id, ...)`` and the
    v2.5 id-free ``node(wf, class_type, ...)`` forms still work — the first
    positional arg can be either a VibeWorkflow or the class_type str.
    """
    # Disambiguate: first positional may be a VibeWorkflow (legacy) or the
    # class_type (new ContextVar form).
    if args and isinstance(args[0], VibeWorkflow):
        wf = args[0]
        rest = args[1:]
    else:
        wf = _current_workflow_or_raise()
        rest = args
    if not rest:
        raise TypeError("node() requires a class_type argument")
    class_type = rest[0]
    if not isinstance(class_type, str):
        raise TypeError(f"node() class_type must be str, got {type(class_type).__name__}")
    # Optional positional source id (legacy form: node(wf, class_type, source_id, ...))
    if len(rest) >= 2 and _id is None:
        _id = str(rest[1]) if rest[1] is not None else None
    elif len(rest) > 2:
        raise TypeError(f"node() got too many positional args: {len(rest)}")

    explicit_outputs = kwargs.pop("_outputs", None)
    # Durable node identity (M2): a carried _uid is applied verbatim to the
    # created node so the ready-template round-trip preserves uids. Popped before
    # coercion so it never reaches the graph as an input/widget.
    _uid = kwargs.pop("_uid", None)
    pass_raw = bool(kwargs.pop("pass_raw", False))
    outputs = tuple(explicit_outputs) if explicit_outputs is not None else _normalized_output_names(class_type)
    kwargs = coerce_node_kwargs(wf, class_type, kwargs, pass_raw=pass_raw)
    if pass_raw:
        kwargs["pass_raw"] = True
    builder = ready_node(wf, class_type, source_id=str(_id) if _id is not None else None, outputs=outputs or None, extras=_extras, **kwargs)
    if _uid:
        builder.node.uid = str(_uid)
    return builder


def coerce_node_kwargs(
    wf: VibeWorkflow,
    class_type: str,
    kwargs: Mapping[str, Any],
    *,
    pass_raw: bool = False,
) -> dict[str, Any]:
    """Normalize v2.5 natural-form values before a node is created.

    This is deliberately shared by ready-template ``node(...)`` and raw
    ``wf.node(...)`` so generated wrappers remain thin and behavior is uniform.
    """
    if pass_raw:
        return dict(kwargs)
    coerced: dict[str, Any] = {}
    for key, value in kwargs.items():
        if _is_node_builder(value):
            value = _auto_resolve_node_builder(value)
        if isinstance(value, ModelAsset) and key in _FILENAME_KWARGS:
            value = value.filename
        elif isinstance(value, InputSpec):
            if key in _FILENAME_KWARGS:
                raise TypeError(
                    f"expected str for {key}, got InputSpec; did you mean InputSpec.default?"
                )
            value = value.default
        if key in _FILENAME_KWARGS and not isinstance(value, str):
            raise TypeError(f"expected str for {key}, got {type(value).__name__}")
        coerced[key] = value
    return coerced


def _is_node_builder(value: Any) -> bool:
    node = getattr(value, "node", None)
    return node is not None and hasattr(node, "class_type") and hasattr(node, "id") and callable(getattr(value, "out", None))


def _auto_resolve_node_builder(value: Any) -> Handle:
    node = value.node
    class_type = str(node.class_type)
    try:
        from vibecomfy.porting.object_info import class_has_list_output, class_output_count, output_names
    except ImportError as exc:
        raise ValueError(
            f"{class_type} node {node.id!r} requires explicit .out(...) because object_info schema is unavailable"
        ) from exc

    names = [str(name).strip().replace(" ", "_").upper() for name in output_names(class_type)]
    count = class_output_count(class_type)
    if class_has_list_output(class_type):
        raise ValueError(
            f"{class_type} node {node.id!r} has list outputs; specify .out('NAME') explicitly"
        )
    if count == 1 and not class_has_list_output(class_type):
        return value.out(0)
    if count > 1:
        detail = ", ".join(names) if names else f"{count} outputs"
        raise ValueError(
            f"{class_type} node {node.id!r} has {count} outputs ({detail}); "
            "specify .out('NAME') explicitly"
        )
    # Legacy and community nodes often lack object_info output schema in local
    # indexes. Generated templates historically treated those as single-output
    # nodes unless they supplied _outputs explicitly, so keep that compatibility
    # path while still rejecting known multi-output/list-output schemas above.
    return value.out(0)


def _at(
    wf: VibeWorkflow,
    _id: str,
    class_type: str,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Narrative-form alias of ``node`` with ``_id`` in position 2.

    .. deprecated::
        Prefer ``node(wf, class_type, _id, ...)``.  ``_at`` is retained as a
        compatibility alias for hand-authored templates that use the older
        ``_at(wf, ID["role"], "Class", ...)`` calling convention.  Generated
        ready-templates always use ``node``.

    Semantically identical to ``node(wf, class_type, _id, ...)``.
    """
    return node(wf, class_type, _id, _extras=_extras, **kwargs)


def _normalized_output_names(class_type: str) -> tuple[str, ...]:
    try:
        from vibecomfy.porting.object_info.consume import output_names
    except ImportError:
        return ()
    return tuple(name.strip().replace(" ", "_").upper() for name in output_names(class_type) if name)


@dataclass(frozen=True)
class SymbolicNodeRef:
    """Module-level public-input binding resolved from build() locals."""

    label: str

    def resolve(self, namespace: Mapping[str, Any], wf: VibeWorkflow) -> str:
        value = namespace.get(self.label)
        node_id = _node_id_from_binding(value)
        if node_id is None or node_id not in wf.nodes:
            raise ValueError(
                f"SymbolicNodeRef({self.label!r}) could not be resolved to a node "
                f"in workflow {wf.id!r}"
            )
        wf.metadata.setdefault("id_map", {})[self.label] = node_id
        return node_id


def ref(label: str) -> SymbolicNodeRef:
    global _SYMBOLIC_REF_DEPRECATION_WARNED
    if not _SYMBOLIC_REF_DEPRECATION_WARNED:
        warnings.warn(
            "vibecomfy.templates.ref('name') is a legacy generated-template fallback; "
            "new generated templates bind InputSpec.node to node objects inside build().",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        _SYMBOLIC_REF_DEPRECATION_WARNED = True
    return SymbolicNodeRef(label)


def _node_id_from_binding(value: Any) -> str | None:
    if isinstance(value, Handle):
        return str(value.node_id)
    node = getattr(value, "node", None)
    if node is not None and hasattr(node, "id"):
        return str(node.id)
    if hasattr(value, "id"):
        return str(value.id)
    if isinstance(value, str):
        return value
    return None


@dataclass(frozen=True)
class InputSpec:
    node: str | SymbolicNodeRef | Any
    field: str
    default: Any
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    description: str | None = None
    media_semantics: str | None = None

    def register(self, wf: VibeWorkflow, name: str, namespace: Mapping[str, Any] | None = None) -> None:
        node_id = self.resolve_node_id(wf, namespace=namespace)
        node = wf.nodes.get(node_id)
        if node is None:
            raise ValueError(
                f"InputSpec.register({name!r}): target node {node_id!r} does not exist "
                f"in workflow {wf.id!r}"
            )
        if self.field in node.inputs:
            value = node.inputs[self.field]
        elif self.field in node.widgets:
            value = node.widgets[self.field]
        else:
            raise ValueError(
                f"InputSpec.register({name!r}): field {self.field!r} not found in "
                f"node {node_id!r} ({node.class_type}) inputs or widgets"
            )
        input_type = self.type or _derive_input_type(node.class_type, self.field)
        wf.register_input(
            name,
            node_id,
            self.field,
            value,
            type=input_type,
            default=self.default,
            required=self.required,
            aliases=self.aliases,
            media_semantics=self.media_semantics,
        )
        for alias in self.aliases:
            if alias in wf.inputs:
                continue
            wf.inputs[alias] = VibeInput(
                name=alias,
                node_id=node_id,
                field=self.field,
                value=value,
                type=input_type,
                default=self.default,
                required=self.required,
                aliases=(),
                media_semantics=self.media_semantics,
            )

    def resolve_node_id(self, wf: VibeWorkflow, namespace: Mapping[str, Any] | None = None) -> str:
        if isinstance(self.node, SymbolicNodeRef):
            return self.node.resolve(namespace or {}, wf)
        node_id = _node_id_from_binding(self.node)
        if node_id is None:
            node_id = str(self.node)
        # If the literal source-workflow ID doesn't exist in the freshly-built
        # workflow (typical when emitter auto-assigns IDs that differ from the
        # source-JSON IDs), fall back to searching ``namespace`` for a local
        # variable that resolves to a matching node — this is how the legacy
        # ``def PUBLIC_INPUTS(**nodes):`` factory bridged the gap.
        node = wf.nodes.get(node_id)
        node_missing_or_wrong_field = node is None or (
            self.field not in node.inputs and self.field not in node.widgets
        )
        if node_missing_or_wrong_field and namespace:
            for value in namespace.values():
                candidate = _node_id_from_binding(value)
                if candidate is not None and candidate in wf.nodes:
                    candidate_node = wf.nodes[candidate]
                    if self.field in candidate_node.inputs or self.field in candidate_node.widgets:
                        return candidate
        return node_id


def _derive_input_type(class_type: str, field: str) -> str | None:
    try:
        from vibecomfy.porting.object_info import class_input_types
    except ImportError:
        return None
    return class_input_types(class_type).get(field)


@dataclass(frozen=True, init=False)
class ModelAsset:
    filename: str
    url: str
    subdir: str
    target_path: str | None = None
    sha256: str | None = None
    hf_revision: str | None = None
    size_bytes: int | None = None
    gated: bool = False

    def __init__(
        self,
        filename: str | None = None,
        url: str | None = None,
        subdir: str | None = None,
        *,
        target_path: str | None = None,
        sha256: str | None = None,
        hf_revision: str | None = None,
        size_bytes: int | None = None,
        gated: bool = False,
    ) -> None:
        if url is None or subdir is None:
            raise TypeError("ModelAsset requires url=... and subdir=...")
        if sha256 == "gated" or hf_revision == "gated":
            raise ValueError("Use ModelAsset(..., gated=True) instead of sha256='gated' or hf_revision='gated'.")
        derived_filename = filename or Path(urlsplit(url).path).name
        if not derived_filename:
            raise ValueError("ModelAsset filename could not be derived from url")
        object.__setattr__(self, "filename", derived_filename)
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "subdir", subdir)
        object.__setattr__(self, "target_path", target_path)
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "hf_revision", hf_revision)
        object.__setattr__(self, "size_bytes", size_bytes)
        object.__setattr__(self, "gated", bool(gated))


class ReadyMetadata:
    @classmethod
    def build(
        cls,
        *,
        capability: str,
        template_id: str | None = None,
        inputs: dict[str, InputSpec] | None = None,
        models: dict[str, ModelAsset] | None = None,
        output_prefix: str | None = None,
        edit_guide_extra: str | None = None,
        requirements: Mapping[str, Any] | None = None,
        custom_node_packs: Mapping[str, Any] | None = None,
        **extras: Any,
    ) -> dict[str, Any]:
        source_path = _caller_source_path()
        template_id = _derive_template_id(template_id, source_path)
        qualified_template_id = _category_qualified_template_id(template_id, str(source_path) if source_path else None)
        inputs = dict(inputs or {})
        models = dict(models or {})
        output_prefix = output_prefix or qualified_template_id
        coverage_row = _coverage_manifest_row(qualified_template_id)
        model_assets = [
            _model_asset_metadata(model)
            for model in models.values()
        ]
        derived_requirements = _requirements_with_models(requirements, model_assets)
        metadata: dict[str, Any] = {
            "ready_template": qualified_template_id,
            "workflow_template": qualified_template_id.rsplit("/", 1)[-1],
            "capability": capability,
            "output_prefix": output_prefix,
            "unbound_inputs": {
                name: spec.default
                for name, spec in inputs.items()
            },
            "model_assets": model_assets,
            "edit_guide": _derive_edit_guide(inputs, edit_guide_extra),
            "requirements": derived_requirements,
            "source_role": "materialized_ready_python_template",
        }
        if custom_node_packs:
            metadata["custom_node_packs"] = {
                str(name): dict(value)
                for name, value in custom_node_packs.items()
                if isinstance(value, Mapping)
            }
        if "coverage_tier" not in extras and isinstance(coverage_row.get("coverage_tier"), str):
            metadata["coverage_tier"] = coverage_row["coverage_tier"]
        source_workflow = _derive_source_workflow(extras, coverage_row, source_path)
        if source_workflow:
            metadata["source_workflow"] = source_workflow
        metadata["vibecomfy_version"] = extras.pop("vibecomfy_version", None) or _project_version()
        metadata["comfy_core"] = extras.pop("comfy_core", None) or _comfy_core_metadata()
        provenance = extras.get("provenance")
        if not isinstance(provenance, Mapping) and source_workflow:
            provenance = {"source_workflow": source_workflow}
            extras["provenance"] = provenance
        elif isinstance(provenance, Mapping) and source_workflow and "source_workflow" not in provenance:
            provenance = {**dict(provenance), "source_workflow": source_workflow}
            extras["provenance"] = provenance
        if isinstance(provenance, Mapping):
            metadata.update({
                key: value
                for key, value in provenance.items()
                if key not in metadata
            })
        metadata.update({
            key: value
            for key, value in extras.items()
            if value is not None
        })
        return metadata


def finalize(
    wf: VibeWorkflow,
    inputs: dict[str, InputSpec],
    metadata: dict[str, Any],
    *,
    output_node: Any = None,
    output_kind: str | None = None,
    **bind_kwargs: Any,
) -> VibeWorkflow:
    """Backward-compatible free-function shim for ``VibeWorkflow.finalize``."""
    return wf.finalize(inputs, metadata=metadata, output_node=output_node, output_kind=output_kind, **bind_kwargs)


def _finalize_impl(
    wf: VibeWorkflow,
    inputs: dict[str, InputSpec],
    metadata: dict[str, Any],
    *,
    output_node: Any = None,
    output_kind: str | None = None,
    **bind_kwargs: Any,
) -> VibeWorkflow:
    """Finalize ready-template metadata, public inputs, and output binding.

    When ``output_kind`` is omitted, it is inferred best-effort from the
    output node class type, then from ``output_type`` if present. If
    ``output_node`` is omitted, a single terminal Save/Create/Preview node is
    selected; multiple candidates require an explicit output binding.
    """
    # Release the eager ContextVar binding that ``new_workflow()`` set, BEFORE
    # any work that might raise — otherwise an exec_failed/validate path leaves
    # the binding stuck across the next template's build() and the regen tool
    # cascades into ``ContextVarBindingError``.  ``new_workflow()`` exists to
    # let module-body node() calls discover the active workflow; by the time we
    # reach finalize, that purpose is served.
    token = getattr(wf, "_workflow_context_token", None)
    if token is not None:
        try:
            from vibecomfy.workflow_context import reset_workflow

            reset_workflow(token)
        except Exception:
            pass
        wf._workflow_context_token = None

    source_path = bind_kwargs.pop("source_path", None)
    requirements = bind_kwargs.pop("requirements", None)
    if source_path is None:
        source_path = wf.source.path or str(Path.cwd())

    # Merge metadata['requirements'] custom_nodes into explicit requirements.
    meta_reqs = metadata.get("requirements")
    if isinstance(meta_reqs, dict) and (meta_reqs.get("custom_nodes") or meta_reqs.get("custom_node_refs")):
        meta_normalized, _warnings = normalize_custom_node_requirements(meta_reqs)
        meta_custom = list(meta_normalized["custom_nodes"])
        if requirements is None:
            requirements = {}
        existing_custom = list(requirements.get("custom_nodes") or [])
        requirements["custom_nodes"] = sorted(set(existing_custom + meta_custom))
        if meta_normalized.get("custom_node_refs"):
            existing_refs = list(requirements.get("custom_node_refs") or [])
            requirements["custom_node_refs"] = [*existing_refs, *meta_normalized["custom_node_refs"]]

    # Fall back to metadata output_prefix when filename_prefix not provided.
    if "filename_prefix" not in bind_kwargs:
        output_prefix_fallback = metadata.get("output_prefix")
        if output_prefix_fallback is not None:
            bind_kwargs["filename_prefix"] = output_prefix_fallback

    caller_locals = _caller_build_locals()
    try:
        output_node_id = _resolve_output_node(wf, output_node, caller_locals)
    except ValueError as exc:
        if output_node is not None or "could not be auto-detected" not in str(exc):
            raise
        output_node_id = None

    output_class_type = wf.nodes.get(output_node_id).class_type if output_node_id in wf.nodes else None
    derived_output_kind = output_kind or _derive_output_kind(output_class_type)
    if derived_output_kind is None:
        derived_output_kind = _derive_output_kind(str(bind_kwargs.get("output_type") or ""))

    requirements = _requirements_with_models(requirements, metadata.get("model_assets", []))

    wf.finalize_metadata()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        apply_ready_template_policy(wf, metadata, source_path=str(source_path), requirements=requirements)

    for name, spec in inputs.items():
        spec.register(wf, name, namespace=caller_locals)

    _assert_public_input_invariant(wf, inputs, namespace=caller_locals)

    if output_node_id is not None:
        artifact_kind = bind_kwargs.pop("artifact_kind", None) or derived_output_kind
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            bind_output(
                wf,
                output_node_id,
                artifact_kind=artifact_kind,
                **bind_kwargs,
            )
    return wf


def _resolve_output_node(wf: VibeWorkflow, output_node: Any, namespace: Mapping[str, Any]) -> str:
    if output_node is None:
        return _autodetect_output_node(wf)
    if isinstance(output_node, SymbolicNodeRef):
        return output_node.resolve(namespace, wf)
    node_id = _node_id_from_binding(output_node)
    if node_id is not None:
        return node_id
    return str(output_node)


def _autodetect_output_node(wf: VibeWorkflow) -> str:
    outgoing = {str(edge.from_node) for edge in wf.edges}
    candidates = [
        str(node_id)
        for node_id, node in wf.nodes.items()
        if str(node_id) not in outgoing and _is_terminal_output_class(node.class_type)
    ]
    candidates.sort(key=lambda item: (int(item) if item.isdigit() else 1 << 30, item))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError("output_node could not be auto-detected; specify explicitly")
    detail = ", ".join(f"{node_id}:{wf.nodes[node_id].class_type}" for node_id in candidates)
    raise ValueError(f"ambiguous output_node; specify explicitly ({detail})")


def _is_terminal_output_class(class_type: str) -> bool:
    if class_type in _OUTPUT_KIND_HEURISTIC:
        return True
    lowered = class_type.lower()
    return (
        lowered.startswith(("save", "preview", "create"))
        or "save" in lowered
        or "preview" in lowered
    )


def _caller_build_locals() -> Mapping[str, Any]:
    frame = inspect.currentframe()
    try:
        cursor = frame.f_back if frame is not None else None
        while cursor is not None:
            if cursor.f_code.co_name == "build":
                return dict(cursor.f_locals)
            cursor = cursor.f_back
        return {}
    finally:
        del frame


def finalize_ready(
    wf: VibeWorkflow,
    metadata: Mapping[str, Any],
    *,
    source_path: str,
    requirements: Mapping[str, Any] | None = None,
) -> VibeWorkflow:
    """Finalize a hand-authored ready template without exposing legacy helpers."""
    wf.finalize_metadata()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        apply_ready_template_policy(wf, metadata, source_path=source_path, requirements=requirements)
    return wf


def template_input(wf: VibeWorkflow, name: str, node_id: str, field: str, *args: Any, **kwargs: Any) -> None:
    """Bind a public input from a hand-authored ready template."""
    if args:
        if len(args) > 1 or "default" in kwargs:
            raise TypeError("template_input accepts at most one positional default")
        kwargs["default"] = args[0]
    node = wf.nodes.get(str(node_id))
    if field == "widget_0" and node is not None and field not in node.inputs and field not in node.widgets:
        if "value" in node.inputs or "value" in node.widgets:
            field = "value"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_input(wf, name, node_id, field, **kwargs)


def template_output(wf: VibeWorkflow, node_id: str, **kwargs: Any) -> None:
    """Bind a public output from a hand-authored ready template."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_output(wf, node_id, **kwargs)


def _derive_edit_guide(inputs: Mapping[str, InputSpec], extra: str | None = None) -> str:
    if not inputs and not extra:
        return ""
    lines = ["Public inputs:"]
    for name, spec in inputs.items():
        description = spec.description or f"Controls {name}."
        lines.append(f"- {name}: {description}")
    if extra:
        lines.append(str(extra))
    return "\n".join(lines)


def _requirements_with_models(
    requirements: Mapping[str, Any] | None,
    model_assets: Any,
) -> dict[str, Any]:
    derived_models = [
        dict(asset)
        for asset in model_assets
        if isinstance(asset, Mapping)
    ]
    merged: dict[str, Any] = dict(requirements or {})
    merged, _warnings = normalize_custom_node_requirements(merged)
    existing_models = merged.get("models")
    if existing_models:
        _warn_on_model_requirement_disagreement(existing_models, derived_models)
    elif derived_models:
        merged["models"] = derived_models
    return merged


def _model_requirement_names(models: Any) -> set[str]:
    names: set[str] = set()
    for model in models or []:
        if isinstance(model, Mapping):
            name = model.get("name")
        else:
            name = model
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _warn_on_model_requirement_disagreement(existing_models: Any, derived_models: list[dict[str, Any]]) -> None:
    global _MODEL_DISAGREEMENT_WARNED
    if _MODEL_DISAGREEMENT_WARNED:
        return
    existing_names = _model_requirement_names(existing_models)
    derived_names = _model_requirement_names(derived_models)
    if existing_names != derived_names:
        warnings.warn(
            "ReadyMetadata.build requirements['models'] differs from MODELS-derived model assets",
            stacklevel=3,
        )
        _MODEL_DISAGREEMENT_WARNED = True


def _model_asset_metadata(model: ModelAsset) -> dict[str, str]:
    data: dict[str, Any] = {
        "name": model.filename,
        "url": model.url,
        "subdir": model.subdir,
    }
    if model.target_path is not None:
        data["target_path"] = model.target_path
    if model.sha256 is not None:
        data["sha256"] = model.sha256
    if model.hf_revision is not None:
        data["hf_revision"] = model.hf_revision
    if model.size_bytes is not None:
        data["size_bytes"] = model.size_bytes
    if model.gated:
        data["gated"] = True
    return data


def _repo_root() -> Path:
    return find_repo_root()


def _caller_source_path() -> Path | None:
    this_file = Path(__file__).resolve()
    frame = inspect.currentframe()
    try:
        cursor = frame.f_back if frame is not None else None
        while cursor is not None:
            filename = cursor.f_code.co_filename
            if filename and filename not in {"<string>", "<stdin>"}:
                path = Path(filename).resolve()
                if path != this_file:
                    return path
            cursor = cursor.f_back
        return None
    finally:
        del frame


def _derive_template_id(template_id: str | None, source_path: Path | None) -> str:
    if template_id:
        return template_id
    if source_path is not None:
        try:
            return source_path.resolve().relative_to(_repo_root() / "ready_templates").with_suffix("").as_posix()
        except ValueError:
            return source_path.stem
    return "ready_template"


def _coverage_manifest_row(template_id: str) -> dict[str, Any]:
    path = _repo_root() / "workflow_corpus" / "manifests" / "coverage.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = data.get("workflows") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        rows = data if isinstance(data, list) else []
    short_id = template_id.rsplit("/", 1)[-1]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        candidates = {
            str(row.get("ready_template") or ""),
            str(row.get("template_id") or ""),
            str(row.get("id") or ""),
        }
        media = row.get("media")
        row_id = row.get("id")
        if isinstance(media, str) and isinstance(row_id, str):
            candidates.add(f"{media}/{row_id}")
        if template_id in candidates or short_id in candidates:
            return dict(row)
    return {}


def _derive_source_workflow(
    extras: Mapping[str, Any],
    coverage_row: Mapping[str, Any],
    source_path: Path | None,
) -> str | None:
    provenance = extras.get("provenance")
    if isinstance(provenance, Mapping) and isinstance(provenance.get("source_workflow"), str):
        return provenance["source_workflow"]
    explicit = extras.get("source_workflow")
    if isinstance(explicit, str):
        return explicit
    for key in ("path", "source_workflow", "workflow_path"):
        value = coverage_row.get(key)
        if isinstance(value, str) and value:
            return value
    if source_path is not None:
        try:
            text = source_path.read_text(encoding="utf-8")
        except OSError:
            return None
        match = re.search(r"^\s*#\s*ported from\s+(.+?)\s*$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).split(" (", 1)[0].strip()
        match = re.search(r"^\s*Source:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _project_version() -> str:
    try:
        data = tomllib.loads((_repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "0"
    project = data.get("project") if isinstance(data, Mapping) else None
    version = project.get("version") if isinstance(project, Mapping) else None
    return str(version) if version else "0"


def _comfy_core_metadata() -> dict[str, Any]:
    try:
        data = json.loads((_repo_root() / "vibecomfy" / "comfy_metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, Mapping):
        return {}
    core = data.get("core") if isinstance(data.get("core"), Mapping) else data
    return {
        key: value
        for key, value in core.items()
        if key in {"version", "commit", "tested_at", "status"}
    }


def _assert_public_input_invariant(
    wf: VibeWorkflow,
    inputs: Mapping[str, InputSpec],
    namespace: Mapping[str, Any] | None = None,
) -> None:
    specs = {
        name: (spec.resolve_node_id(wf, namespace=namespace), spec.field)
        for name, spec in inputs.items()
    }
    alias_names = {
        str(alias)
        for spec in inputs.values()
        for alias in spec.aliases
    }
    for name, (node_id, field) in specs.items():
        registered = wf.inputs.get(name)
        if registered is None:
            raise AssertionError(f"public input {name!r} was not registered")
        if (str(registered.node_id), registered.field) != (node_id, field):
            raise AssertionError(
                f"public input {name!r} target drift: "
                f"expected {node_id}.{field}, got {registered.node_id}.{registered.field}"
            )

    unexpected = {
            name
            for name, registered in wf.inputs.items()
            if name not in specs
            and name not in alias_names
            and (str(registered.node_id), registered.field) in set(specs.values())
        }
    if unexpected:
        raise AssertionError(
            "registered inputs target PUBLIC_INPUTS nodes but are not declared: "
            + ", ".join(sorted(unexpected))
        )


__all__ = [
    "InputSpec",
    "ModelAsset",
    "ReadyMetadata",
    "_at",
    "_current_workflow_or_raise",
    "_derive_output_kind",
    "finalize",
    "finalize_ready",
    "new_workflow",
    "node",
    "template_input",
    "template_output",
]
