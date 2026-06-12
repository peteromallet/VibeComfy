"""Lazy consumer for the structured object_info cache.

Reads per-pack JSON files and ``index.json`` on first access.
All public functions are deterministic and do not require ComfyUI or network.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.errors import ArityDisagreementError, ObjectInfoIdentityAmbiguityError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CACHE_DIR: Path = Path(__file__).resolve().parent.parent / "cache" / "object_info"
INDEX_PATH: Path = CACHE_DIR / "index.json"

# ``comfy_metadata.json`` lives at the package root (vibecomfy/) and pins the
# ComfyUI snapshot the object_info cache was captured against. Used only to make
# fail-closed schema errors actionable ("refresh the snapshot").
METADATA_PATH: Path = Path(__file__).resolve().parent.parent.parent / "comfy_metadata.json"

# ComfyUI types that are link-only sockets — NOT widget controls.
# These are excluded from object_info_widget_order.
_WIDGET_LIKE_TYPES: frozenset[str] = frozenset({
    "MODEL", "CLIP", "VAE", "IMAGE", "LATENT", "CONDITIONING", "MASK",
    "AUDIO", "VIDEO", "hidden",
})

_CURATED_WIDGET_ORDERS: dict[str, list[str | None]] = {
    # The checked-in object_info cache does not include LTX2_NAG in all
    # environments. Curate only the missing fallback slot; WIDGET_SCHEMA owns
    # the first three widget names and asks object_info for index 3.
    "LTX2_NAG": ["nag_scale", "nag_alpha", "nag_tau", "inplace"],
}

_CURATED_OUTPUTS: dict[str, list[dict[str, str]]] = {
    # Core classes used by checked-in tests and v2.3 generated templates. These
    # labels are stable ComfyUI socket names and keep named handles available
    # when the large generated object_info cache is not committed.
    "CLIPTextEncode": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "CLIPLoader": [{"name": "CLIP", "type": "CLIP"}],
    "CLIPVisionEncode": [{"name": "CLIP_VISION_OUTPUT", "type": "CLIP_VISION_OUTPUT"}],
    "CLIPVisionLoader": [{"name": "CLIP_VISION", "type": "CLIP_VISION"}],
    "CFGGuider": [{"name": "GUIDER", "type": "GUIDER"}],
    "CFGNorm": [{"name": "patched_model", "type": "MODEL"}],
    "ComfySwitchNode": [{"name": "output", "type": "*"}],
    "ConditioningZeroOut": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "CreateVideo": [{"name": "VIDEO", "type": "VIDEO"}],
    "DepthAnything_V2": [{"name": "image", "type": "IMAGE"}],
    "DownloadAndLoadDepthAnythingV2Model": [{"name": "da_v2_model", "type": "MODEL"}],
    "DualCLIPLoader": [{"name": "CLIP", "type": "CLIP"}],
    "EmptyAceStep1.5LatentAudio": [{"name": "LATENT", "type": "LATENT"}],
    "EmptyLTXVLatentVideo": [{"name": "LATENT", "type": "LATENT"}],
    "EmptySD3LatentImage": [{"name": "LATENT", "type": "LATENT"}],
    "GetVideoComponents": [{"name": "images", "type": "IMAGE"}],
    "ImageResizeKJv2": [{"name": "IMAGE", "type": "IMAGE"}],
    "ImageScaleToTotalPixels": [{"name": "IMAGE", "type": "IMAGE"}],
    "INTConstant": [{"name": "value", "type": "INT"}],
    "KSampler": [{"name": "LATENT", "type": "LATENT"}],
    "KSamplerSelect": [{"name": "SAMPLER", "type": "SAMPLER"}],
    "LoadImage": [{"name": "IMAGE", "type": "IMAGE"}],
    "LoadVideo": [{"name": "VIDEO", "type": "VIDEO"}],
    "LoraLoaderModelOnly": [{"name": "MODEL", "type": "MODEL"}],
    "ManualSigmas": [{"name": "SIGMAS", "type": "SIGMAS"}],
    "ModelSamplingAuraFlow": [{"name": "MODEL", "type": "MODEL"}],
    "ModelSamplingSD3": [{"name": "MODEL", "type": "MODEL"}],
    "PathchSageAttentionKJ": [{"name": "MODEL", "type": "MODEL"}],
    "PrimitiveBoolean": [{"name": "BOOLEAN", "type": "BOOLEAN"}],
    "PrimitiveFloat": [{"name": "FLOAT", "type": "FLOAT"}],
    "PrimitiveInt": [{"name": "INT", "type": "INT"}],
    "RandomNoise": [{"name": "NOISE", "type": "NOISE"}],
    "SamplerCustomAdvanced": [{"name": "output", "type": "LATENT"}],
    "TextEncodeAceStepAudio1.5": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "TextEncodeQwenImageEdit": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "UNETLoader": [{"name": "MODEL", "type": "MODEL"}],
    "VAEDecode": [{"name": "IMAGE", "type": "IMAGE"}],
    "VAEDecodeAudio": [{"name": "AUDIO", "type": "AUDIO"}],
    "VAEDecodeTiled": [{"name": "IMAGE", "type": "IMAGE"}],
    "VAEEncode": [{"name": "LATENT", "type": "LATENT"}],
    "VAELoader": [{"name": "VAE", "type": "VAE"}],
    "WanImageToVideo": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTX2AttentionTunerPatch": [{"name": "model", "type": "MODEL"}],
    "LTX2_NAG": [{"name": "model", "type": "MODEL"}],
    "LTXAddVideoICLoRAGuide": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTXFloatToInt": [{"name": "INT", "type": "INT"}],
    "LTXICLoRALoaderModelOnly": [
        {"name": "model", "type": "MODEL"},
        {"name": "latent_downscale_factor", "type": "FLOAT"},
    ],
    "LTXVAudioVAELoader": [{"name": "Audio VAE", "type": "VAE"}],
    "LTXVChunkFeedForward": [{"name": "model", "type": "MODEL"}],
    "LTXVConcatAVLatent": [{"name": "latent", "type": "LATENT"}],
    "LTXVConditioning": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
    ],
    "LTXVCropGuides": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTXVEmptyLatentAudio": [{"name": "Latent", "type": "LATENT"}],
    "LTXVImgToVideoInplaceKJ": [{"name": "latent", "type": "LATENT"}],
    "LTXVPreprocess": [{"name": "output_image", "type": "IMAGE"}],
    "LTXVSeparateAVLatent": [
        {"name": "video_latent", "type": "LATENT"},
        {"name": "audio_latent", "type": "LATENT"},
    ],
    # controlnet_aux classes used by the v2.3 pilot. These packs were absent
    # from the local object_info cache during the audit, but their single image
    # output is stable and needed by both codemod readability and Handle.out().
    "CannyEdgePreprocessor": [{"name": "IMAGE", "type": "IMAGE"}],
    "DWPreprocessor": [{"name": "IMAGE", "type": "IMAGE"}],
}

# ---------------------------------------------------------------------------
# Internal lazy state
# ---------------------------------------------------------------------------

_index: dict[str, str] | None = None
_pack_cache: dict[str, dict[str, dict[str, Any]]] = {}


@dataclass(frozen=True)
class ObjectInfoIdentity:
    pack_slug: str
    git_commit: str | None = None
    evidence_identity: str | None = None


@dataclass(frozen=True)
class ObjectInfoLookupWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ObjectInfoLookupResult:
    entry: dict[str, Any] | None
    source: str
    low_confidence: bool = False
    warning: ObjectInfoLookupWarning | None = None


def _normalize_output_name(name: str) -> str:
    cleaned = name.strip().replace(" ", "_")
    return cleaned.upper()


def _load_index() -> dict[str, str]:
    global _index
    if _index is None:
        if INDEX_PATH.is_file():
            with open(INDEX_PATH, "r", encoding="utf-8") as fh:
                _index = json.load(fh)
        else:
            _index = {}
    return _index


def _load_pack(filename: str) -> dict[str, dict[str, Any]]:
    if filename not in _pack_cache:
        filepath = CACHE_DIR / filename
        if filepath.is_file():
            with open(filepath, "r", encoding="utf-8") as fh:
                _pack_cache[filename] = json.load(fh)
        else:
            _pack_cache[filename] = {}
    return _pack_cache[filename]


def _all_pack_filenames() -> list[str]:
    filenames = {
        str(path.name)
        for path in CACHE_DIR.glob("*.json")
        if path.name != INDEX_PATH.name
    }
    filenames.update(str(filename) for filename in _load_index().values())
    return sorted(filenames)


def _resolve_class_type(class_type: str) -> dict[str, Any] | None:
    idx = _load_index()
    filename = idx.get(class_type)
    if filename is None:
        return None
    pack = _load_pack(filename)
    return pack.get(class_type)


def _identity_matches(
    entry: dict[str, Any],
    *,
    pack_slug: str,
    git_commit: str | None,
    evidence_identity: str | None,
) -> bool:
    if entry.get("pack_slug") != pack_slug:
        return False
    if git_commit is not None:
        return entry.get("git_commit") == git_commit
    return entry.get("evidence_identity") == evidence_identity


def _identity_key(pack_slug: str, git_commit: str | None, evidence_identity: str | None) -> tuple[str, str]:
    if git_commit is not None and evidence_identity is not None:
        raise ValueError("identity lookup accepts git_commit or evidence_identity, not both")
    if git_commit is None and evidence_identity is None:
        raise ValueError("identity lookup requires git_commit or evidence_identity")
    return (
        pack_slug,
        f"git_commit:{git_commit}" if git_commit is not None else f"evidence_identity:{evidence_identity}",
    )


def _identity_lookup_matches(
    class_type: str,
    *,
    pack_slug: str,
    git_commit: str | None,
    evidence_identity: str | None,
) -> list[tuple[str, dict[str, Any]]]:
    _identity_key(pack_slug, git_commit, evidence_identity)
    matches: list[tuple[str, dict[str, Any]]] = []
    for filename in _all_pack_filenames():
        entry = _load_pack(filename).get(class_type)
        if isinstance(entry, dict) and _identity_matches(
            entry,
            pack_slug=pack_slug,
            git_commit=git_commit,
            evidence_identity=evidence_identity,
        ):
            matches.append((filename, entry))
    return matches


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_class(class_type: str) -> dict[str, Any] | None:
    """Return the normalized cache entry for *class_type*, or ``None``.

    The returned dict has keys:
    ``pack``, ``pack_version``, ``python_module``, ``category``, ``name``,
    ``display_name``, ``description``, ``inputs``, ``input_order``,
    ``input_order_all``, ``object_info_widget_order``, ``outputs``, ``function``.
    """
    entry = _resolve_class_type(class_type)
    if entry is not None:
        return entry
    curated_outputs = _CURATED_OUTPUTS.get(class_type)
    if curated_outputs is None:
        return None
    return {"outputs": curated_outputs}


def resolve_class_entry(
    class_type: str,
    identity: ObjectInfoIdentity | dict[str, Any] | None = None,
    *,
    allow_class_fallback: bool = True,
) -> ObjectInfoLookupResult:
    """Resolve an object_info entry, preferring an explicit pack identity.

    Class-only callers can pass no identity and get the historical cache/curated
    lookup semantics. Identity-aware callers get a provenance-sensitive result
    with source and warning metadata when a fallback is used or blocked.
    """
    normalized_identity = _coerce_identity(identity)
    if normalized_identity is None:
        entry = get_class(class_type)
        return ObjectInfoLookupResult(
            entry=entry,
            source="class" if entry is not None else "miss",
            low_confidence=False,
        )

    try:
        entry = get_class_by_identity(
            class_type,
            pack_slug=normalized_identity.pack_slug,
            git_commit=normalized_identity.git_commit,
            evidence_identity=normalized_identity.evidence_identity,
        )
    except ObjectInfoIdentityAmbiguityError:
        raise
    if entry is not None:
        return ObjectInfoLookupResult(entry=entry, source="identity", low_confidence=False)

    if not allow_class_fallback:
        return ObjectInfoLookupResult(
            entry=None,
            source="identity_miss",
            low_confidence=True,
            warning=ObjectInfoLookupWarning(
                code="identity_cache_miss",
                message=(
                    f"No object_info cache entry for {class_type} matched identity "
                    f"{_identity_label(normalized_identity)}."
                ),
            ),
        )

    fallback = get_class(class_type)
    if fallback is None:
        return ObjectInfoLookupResult(
            entry=None,
            source="miss",
            low_confidence=True,
            warning=ObjectInfoLookupWarning(
                code="identity_cache_miss",
                message=(
                    f"No object_info cache entry for {class_type} matched identity "
                    f"{_identity_label(normalized_identity)}, and class fallback was unavailable."
                ),
            ),
        )

    if _entry_has_authoritative_identity(fallback):
        code = "provenanced_cache_miss_fallback"
        message = (
            f"No object_info cache entry for {class_type} matched identity "
            f"{_identity_label(normalized_identity)}; using a different provenanced class cache entry."
        )
    else:
        code = "unprovenanced_cache_fallback"
        message = (
            f"No object_info cache entry for {class_type} matched identity "
            f"{_identity_label(normalized_identity)}; using non-authoritative class fallback."
        )
    return ObjectInfoLookupResult(
        entry=fallback,
        source="class_fallback",
        low_confidence=True,
        warning=ObjectInfoLookupWarning(code=code, message=message),
    )


def get_class_by_identity(
    class_type: str,
    *,
    pack_slug: str,
    git_commit: str | None = None,
    evidence_identity: str | None = None,
) -> dict[str, Any] | None:
    """Return the cache entry for *class_type* keyed by explicit pack identity."""
    matches = _identity_lookup_matches(
        class_type,
        pack_slug=pack_slug,
        git_commit=git_commit,
        evidence_identity=evidence_identity,
    )
    if not matches:
        return None
    if len(matches) > 1:
        raise ObjectInfoIdentityAmbiguityError(
            (
                f"multiple object_info cache entries matched {class_type} for pack {pack_slug}; "
                "provide a more specific identity or refresh duplicate cache files."
            ),
            class_type=class_type,
            pack_slug=pack_slug,
            git_commit=git_commit,
            evidence_identity=evidence_identity,
            matches=[
                {
                    "filename": filename,
                    "pack_version": entry.get("pack_version"),
                    "git_commit": entry.get("git_commit"),
                    "evidence_identity": entry.get("evidence_identity"),
                    "source_kind": entry.get("source_kind"),
                }
                for filename, entry in matches
            ],
        )
    return matches[0][1]


def has_class_identity(
    class_type: str,
    *,
    pack_slug: str,
    git_commit: str | None = None,
    evidence_identity: str | None = None,
) -> bool:
    """Return True when an explicit object_info identity resolves for *class_type*."""
    return get_class_by_identity(
        class_type,
        pack_slug=pack_slug,
        git_commit=git_commit,
        evidence_identity=evidence_identity,
    ) is not None


def _coerce_identity(identity: ObjectInfoIdentity | dict[str, Any] | None) -> ObjectInfoIdentity | None:
    if identity is None:
        return None
    if isinstance(identity, ObjectInfoIdentity):
        return identity
    pack_slug = identity.get("pack_slug") or identity.get("pack") or identity.get("slug")
    git_commit = identity.get("git_commit") or identity.get("commit")
    evidence_identity = identity.get("evidence_identity")
    if not pack_slug:
        raise ValueError("object_info identity requires pack_slug")
    if git_commit and evidence_identity:
        raise ValueError("object_info identity accepts git_commit or evidence_identity, not both")
    if not git_commit and not evidence_identity:
        raise ValueError("object_info identity requires git_commit or evidence_identity")
    return ObjectInfoIdentity(
        pack_slug=str(pack_slug),
        git_commit=str(git_commit) if git_commit else None,
        evidence_identity=str(evidence_identity) if evidence_identity else None,
    )


def _identity_label(identity: ObjectInfoIdentity) -> str:
    key = f"git_commit={identity.git_commit}" if identity.git_commit else f"evidence_identity={identity.evidence_identity}"
    return f"pack_slug={identity.pack_slug}, {key}"


def _entry_has_authoritative_identity(entry: dict[str, Any]) -> bool:
    if entry.get("git_commit"):
        return True
    source_kind = str(entry.get("source_kind") or "")
    return bool(entry.get("evidence_identity")) and source_kind not in {
        "",
        "legacy_object_info_import",
        "structured_cache_copy",
    }


def object_info_widget_order(class_type: str) -> list[str | None]:
    """Return the ordered widget names (excluding link-only sockets) for *class_type*.

    Returns an empty list when the class is not found in the cache.
    This is a raw object_info fallback — callers should prefer the curated
    ``WIDGET_SCHEMA`` table and only use this when no curated entry exists.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return list(_CURATED_WIDGET_ORDERS.get(class_type, []))
    order = list(entry.get("object_info_widget_order", []))
    if class_type in _CURATED_WIDGET_ORDERS and "apply_to_all" not in order:
        return list(_CURATED_WIDGET_ORDERS[class_type])
    return order


def effective_widget_names_for_class(class_type: str, *, allow_object_info_fallback: bool = False) -> list[str | None]:
    """Return curated widget names, optionally falling back to cached object_info."""
    from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)
    if allow_object_info_fallback:
        return object_info_widget_order(class_type)
    return []


def output_names(class_type: str) -> list[str]:
    """Return ordered output names for *class_type* (e.g. ``["MODEL"]``).

    Returns an empty list when the class is not found in the cache.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return [o["name"] for o in _CURATED_OUTPUTS.get(class_type, [])]
    names = [o.get("name", "") for o in entry.get("outputs", [])]
    return names or [o["name"] for o in _CURATED_OUTPUTS.get(class_type, [])]


def output_types(class_type: str) -> list[str]:
    """Return ordered output types for *class_type* (e.g. ``["MODEL"]``).

    Returns an empty list when the class is not found in the cache.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return [o["type"] for o in _CURATED_OUTPUTS.get(class_type, [])]
    types = [o.get("type", "") for o in entry.get("outputs", [])]
    return types or [o["type"] for o in _CURATED_OUTPUTS.get(class_type, [])]


def class_defaults(class_type: str) -> dict[str, Any]:
    """Return schema default values by input name for *class_type*.

    Only inputs with an explicit object_info ``default`` are returned. The
    lookup is offline and deterministic; unknown classes return ``{}``.
    """
    entry = get_class(class_type)
    if entry is None:
        return {}
    defaults: dict[str, Any] = {}
    for name, spec in _iter_input_specs(entry):
        metadata = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        if "default" in metadata:
            defaults[name] = metadata["default"]
    return defaults


def class_input_types(class_type: str) -> dict[str, str]:
    """Return best-effort input type names by input name for *class_type*."""
    entry = get_class(class_type)
    if entry is None:
        return {}
    return {
        name: _normalize_input_type(spec[0] if spec else None)
        for name, spec in _iter_input_specs(entry)
    }


def class_output_count(class_type: str) -> int:
    """Return the number of declared outputs for *class_type*.

    Fails OPEN: an unknown class (absent from both the object_info snapshot and
    the curated fallback) reports ``0``. Codegen sites that rely on the count to
    determine output arity must use :func:`require_class_output_count` instead so
    a genuinely-unknown node fails CLOSED with a named, actionable error.
    """
    return len(output_names(class_type))


def class_is_known(class_type: str) -> bool:
    """Return True when *class_type* has a usable output schema.

    A class is "known" when it resolves in the object_info snapshot OR has a
    curated ``_CURATED_OUTPUTS`` fallback. Unknown classes are exactly the ones
    for which :func:`output_names` / :func:`class_output_count` fail open with an
    empty list / zero.
    """
    if _resolve_class_type(class_type) is not None:
        return True
    return class_type in _CURATED_OUTPUTS


def snapshot_version() -> str:
    """Return the ComfyUI version string the object_info snapshot was captured

    against, read from ``comfy_metadata.json``. Best-effort: returns
    ``"unknown"`` if the metadata file is absent or unreadable.
    """
    try:
        with open(METADATA_PATH, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return "unknown"
    version = meta.get("version") if isinstance(meta, dict) else None
    return str(version) if version else "unknown"


def check_output_arity_consensus(class_type: str, ui_output_count: int | None) -> int:
    """Return the cached output count after checking cache vs UI arity evidence.

    Unknown classes preserve historical defaults: the cached count is returned
    without raising or warning because there is no reliable snapshot evidence to
    compare against.
    """
    cached_count = class_output_count(class_type)
    if ui_output_count is None or not class_is_known(class_type):
        return cached_count
    if cached_count < ui_output_count:
        entry = get_class(class_type) or {}
        raise ArityDisagreementError(
            (
                f"output arity disagreement for {class_type}: cached snapshot "
                f"declares {cached_count} outputs but UI declares {ui_output_count}. "
                "Refresh the object_info schema snapshot."
            ),
            class_type=class_type,
            snapshot_pack=entry.get("pack"),
            snapshot_version=entry.get("pack_version"),
            snapshot_output_count=cached_count,
            ui_output_count=ui_output_count,
        )
    if cached_count > ui_output_count:
        warnings.warn(
            (
                f"output arity disagreement for {class_type}: cached snapshot "
                f"declares {cached_count} outputs but UI declares {ui_output_count}; "
                "continuing because the extra cached outputs may be unused."
            ),
            stacklevel=2,
        )
    return cached_count


def require_class_output_count(class_type: str, ui_output_count: int | None = None) -> int:
    """Return class output count while enforcing typed cache-vs-UI arity checks."""
    return check_output_arity_consensus(class_type, ui_output_count)


def class_has_list_output(class_type: str) -> bool:
    """Return True when any declared output is marked OUTPUT_IS_LIST."""
    entry = get_class(class_type)
    if entry is None:
        return any(bool(o.get("is_list")) for o in _CURATED_OUTPUTS.get(class_type, []))
    return any(bool(o.get("is_list")) for o in entry.get("outputs", []))


def list_classes() -> list[str]:
    """Return all class types in the cache, sorted deterministically."""
    idx = _load_index()
    if idx:
        return sorted(idx.keys())
    return sorted(_CURATED_OUTPUTS)


def _iter_input_specs(entry: dict[str, Any]) -> list[tuple[str, list[Any]]]:
    inputs = entry.get("inputs")
    if not isinstance(inputs, dict):
        return []
    ordered = entry.get("input_order_all")
    names: list[str] = [str(name) for name in ordered] if isinstance(ordered, list) else []
    by_name: dict[str, list[Any]] = {}
    for section in ("required", "optional"):
        values = inputs.get(section)
        if not isinstance(values, dict):
            continue
        for name, spec in values.items():
            if isinstance(spec, list):
                by_name[str(name)] = spec
            elif isinstance(spec, str):
                by_name[str(name)] = [spec]
    if not names:
        names = sorted(by_name)
    return [(name, by_name[name]) for name in names if name in by_name]


def _normalize_input_type(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "ENUM"
    if value is None:
        return ""
    return str(value)


def reset_cache() -> None:
    """Clear the module-level object-info index and pack cache.

    Callers should invoke this after writing new object_info cache files
    (e.g. after an ``ensure_env`` run) so that subsequent ``consume`` reads
    pick up the latest on-disk state.
    """
    global _index, _pack_cache
    _index = None
    _pack_cache.clear()


def cache_stats() -> dict[str, Any]:
    """Return summary stats about the loaded cache (for debugging)."""
    idx = _load_index()
    return {
        "total_classes": len(idx),
        "packs_cached": len(_pack_cache),
        "cache_dir": str(CACHE_DIR),
    }
