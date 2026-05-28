"""Legacy codemod kept for historical tests and analysis helpers.

The active v2.6 template conversion path is ``tools.convert_ready_templates``
and ``vibecomfy.porting.emitter``. Do not route new ready-template migration
work through this module; its old narrative output is not the strict-ready
target shape.

Codemod: transform a `_node`-style ready template into the "Narrative form".

Narrative form makes a ready template easier for an LLM agent to read and edit:

  * widget values bound to logical inputs are hoisted into a ``PARAMS`` dict
  * every node id is hoisted into an ``ID`` sidecar dict, grouped by stage
  * ``_node(...)`` calls are rewritten as ``_at(wf, ID[...], "Class", ...)``
  * variable names are role-derived (``sampled_latent`` not ``samplercustomadvanced_13``)
  * each node carries a trailing ``# outputs: 0=NAME`` comment from the schema
  * pipeline stages are introduced with banner comments

This is a first-cut prototype. It is intentionally focused on a single source
file shape: the manual LTX 2.3 first/last-frame travel template. It will refuse
to operate on templates that don't use the ``_node`` shim.

Usage:
    python -m tools.narrate_template <input.py> [--out <output.py>] [--dry-run] [--diff]
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import importlib.util
import re
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.templates import _derive_output_kind
from vibecomfy.node_packs import get_known_node_packs

# TODO(repo-root): legacy script keeps direct path math; migrate to
# vibecomfy.utils.find_repo_root() only if this path is revived.
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "out" / "cache"


# --------------------------------------------------------------------------- #
# Role naming table                                                           #
# --------------------------------------------------------------------------- #

ROLE_NAMES: dict[str, str] = {
    "UNETLoader": "base_diffusion_model",
    "VAELoader": "vae",
    "DualCLIPLoader": "text_encoder",
    "CLIPLoader": "text_encoder",
    "LoadImage": "input_image",
    "LoadVideo": "input_video",
    "PrimitiveFloat": "param_float",
    "PrimitiveString": "param_string",
    "PrimitiveInt": "param_int",
    "PrimitiveBoolean": "use_flag",
    "INTConstant": "param_int",
    "CLIPTextEncode": "prompt_embedding",
    "RandomNoise": "noise",
    "KSampler": "sampler",
    "KSamplerSelect": "sampler_kind",
    "ManualSigmas": "sigmas",
    "CFGGuider": "cfg_guider",
    "SamplerCustomAdvanced": "sampled_latent",
    "VAEDecode": "decoded_image",
    "VAEDecodeTiled": "decoded_video",
    "VHS_VideoCombine": "video_output",
    "SaveImage": "image_output",
    "SaveVideo": "saved_video",
    "CreateVideo": "video",
    "LoraLoaderModelOnly": "lora",
    "PathchSageAttentionKJ": "model_with_sage_attn",
    "LTXVChunkFeedForward": "model_chunked_ffn",
    "LTX2AttentionTunerPatch": "model_attention_tuned",
    "LTXICLoRALoaderModelOnly": "final_model_with_ic_lora",
    "LTX2_NAG": "model_with_nag",
    "ImageResizeKJv2": "resized_image",
    "LTXVPreprocess": "preprocessed_image",
    "GetVideoComponents": "video_components",
    "DWPreprocessor": "pose_estimated",
    "CannyEdgePreprocessor": "canny_edges",
    "DepthAnything_V2": "depth_map",
    "DownloadAndLoadDepthAnythingV2Model": "depth_model",
    "EmptyLTXVLatentVideo": "empty_video_latent",
    "EmptySD3LatentImage": "latent",
    "EmptyHunyuanLatentVideo": "latent",
    "LTXVEmptyLatentAudio": "empty_audio_latent",
    "LTXVImgToVideoInplaceKJ": "anchored_latent",
    "LTXAddVideoICLoRAGuide": "guided_latent",
    "LTXVConcatAVLatent": "av_latent",
    "LTXVSeparateAVLatent": "av_latent_separated",
    "LTXVCropGuides": "cropped_latent",
    "LTXVAudioVAEDecode": "decoded_audio",
    "LTXVAudioVAELoader": "audio_vae",
    "LTXFloatToInt": "fps_int",
    "LTXVConditioning": "conditioning",
    # Wan I2V family
    "CLIPVisionLoader": "clip_vision",
    "CLIPVisionEncode": "clip_vision_features",
    "WanImageToVideo": "wan_video",
    "ModelSamplingSD3": "model_sampling",
    "ModelSamplingAuraFlow": "model_sampling",
    "ModelSamplingFlux": "model_sampling",
    # ComfySwitchNode is contextual; the post-pass renamer below derives a
    # purpose-aware name (switch_<purpose>) where possible. The fallback role
    # name covers the case where the post-pass can't infer purpose.
    "ComfySwitchNode": "switch",
}


# --------------------------------------------------------------------------- #
# Stage / section grouping                                                    #
# --------------------------------------------------------------------------- #

# The order of sections in the output build() function.
SECTION_ORDER: tuple[str, ...] = (
    "INPUTS",
    "LOADERS",
    "MODEL PATCH STACK",
    "TEXT CONDITIONING",
    "IMAGE PREP",
    "CONTROL",
    "LATENT",
    "SAMPLING",
    "DECODE",
    "OUTPUT",
)

# class -> section
SECTION_OF_CLASS: dict[str, str] = {
    # INPUTS
    "LoadImage": "INPUTS",
    "LoadVideo": "INPUTS",
    "PrimitiveFloat": "INPUTS",
    "PrimitiveString": "INPUTS",
    "PrimitiveInt": "INPUTS",
    "INTConstant": "INPUTS",
    # LOADERS
    "UNETLoader": "LOADERS",
    "VAELoader": "LOADERS",
    "DualCLIPLoader": "LOADERS",
    "DualCLIPLoaderGGUF": "LOADERS",
    "CLIPLoader": "LOADERS",
    "LTXVAudioVAELoader": "LOADERS",
    "CheckpointLoaderSimple": "LOADERS",
    "CLIPVisionLoader": "LOADERS",
    "StyleModelLoader": "LOADERS",
    # MODEL PATCH STACK
    "LoraLoaderModelOnly": "MODEL PATCH STACK",
    "PathchSageAttentionKJ": "MODEL PATCH STACK",
    "LTXVChunkFeedForward": "MODEL PATCH STACK",
    "LTX2AttentionTunerPatch": "MODEL PATCH STACK",
    "LTXICLoRALoaderModelOnly": "MODEL PATCH STACK",
    "LTX2_NAG": "MODEL PATCH STACK",
    # TEXT CONDITIONING
    "CLIPTextEncode": "TEXT CONDITIONING",
    "CLIPTextEncodeFlux": "TEXT CONDITIONING",
    "LTXVConditioning": "TEXT CONDITIONING",
    # IMAGE PREP
    "ImageResizeKJv2": "IMAGE PREP",
    "LTXVPreprocess": "IMAGE PREP",
    "GetVideoComponents": "IMAGE PREP",
    # CONTROL GUIDE BRANCHES
    "DWPreprocessor": "CONTROL",
    "CannyEdgePreprocessor": "CONTROL",
    "DepthAnything_V2": "CONTROL",
    "DownloadAndLoadDepthAnythingV2Model": "CONTROL",
    # LATENT
    "EmptyAceStep1.5LatentAudio": "LATENT",
    "EmptyLTXVLatentVideo": "LATENT",
    "EmptySD3LatentImage": "LATENT",
    "LTXVEmptyLatentAudio": "LATENT",
    "LTXVImgToVideoInplaceKJ": "LATENT",
    "LTXAddVideoICLoRAGuide": "LATENT",
    "LTXVConcatAVLatent": "LATENT",
    "LTXFloatToInt": "LATENT",
    # SAMPLING
    "RandomNoise": "SAMPLING",
    "KSamplerSelect": "SAMPLING",
    "ManualSigmas": "SAMPLING",
    "CFGGuider": "SAMPLING",
    "SamplerCustomAdvanced": "SAMPLING",
    "KSampler": "SAMPLING",
    "KSamplerAdvanced": "SAMPLING",
    "LTXVSeparateAVLatent": "SAMPLING",
    "LTXVCropGuides": "SAMPLING",
    # DECODE
    "VAEDecode": "DECODE",
    "VAEDecodeTiled": "DECODE",
    "LTXVAudioVAEDecode": "DECODE",
    "LTXVDecoder": "DECODE",
    # OUTPUT
    "CreateVideo": "OUTPUT",
    "VHS_VideoCombine": "OUTPUT",
    "SaveImage": "OUTPUT",
    "SaveVideo": "OUTPUT",
    "SaveAudio": "OUTPUT",
    "SaveAudioMP3": "OUTPUT",
    "PreviewImage": "OUTPUT",
    "PreviewAudio": "OUTPUT",
}

_CANONICAL_DESCRIPTIONS: dict[str, str] = {
    "prompt": "Text prompt.",
    "negative_prompt": "Negative text prompt.",
    "seed": "Random seed.",
    "seed_2": "Secondary random seed.",
    "seed_refine": "Refine-pass random seed.",
    "steps": "Sampling steps.",
    "cfg": "Classifier-free guidance scale.",
    "sampler_name": "Sampler algorithm.",
    "width": "Output width.",
    "height": "Output height.",
    "length": "Number of output frames.",
    "output_fps": "Output playback frame rate.",
    "start_image": "Starting image.",
    "end_image": "Ending image.",
    "source_image": "Source image.",
    "control_video": "Control video.",
    "control_mode": "Control branch selector.",
    "guide_strength": "Guide strength.",
    "ic_lora_filename": "IC-LoRA model filename.",
    "ic_lora_strength": "IC-LoRA strength.",
    "lyrics": "Song lyrics.",
    "tags": "Style tags.",
    "duration": "Duration in seconds.",
    "bpm": "Tempo in beats per minute.",
    "use_lora": "Lightning LoRA branch toggle.",
}

_LOADER_MODEL_FIELDS: dict[str, tuple[str, ...]] = {
    "UNETLoader": ("unet_name",),
    "UNETLoaderGGUF": ("unet_name",),
    "VAELoader": ("vae_name",),
    "CLIPLoader": ("clip_name",),
    "DualCLIPLoader": ("clip_name1", "clip_name2"),
    "DualCLIPLoaderGGUF": ("clip_name1", "clip_name2"),
    "TripleCLIPLoader": ("clip_name1", "clip_name2", "clip_name3"),
    "CheckpointLoaderSimple": ("ckpt_name",),
    "CLIPVisionLoader": ("clip_name",),
    "LTXVAudioVAELoader": ("vae_name",),
}


# --------------------------------------------------------------------------- #
# Params grouping for the hoisted PARAMS dict                                 #
# --------------------------------------------------------------------------- #

PARAM_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("resolution", ("width", "height", "frames", "fps")),
    ("seeds", ("seed",)),
    ("text", ("prompt", "negative")),
    ("control", (
        "start_image", "end_image", "control_video", "control_mode",
        "ic_lora_filename", "ic_lora_strength", "strength",
    )),
    ("sampling", ()),
)


# --------------------------------------------------------------------------- #
# Output schema lookup                                                        #
# --------------------------------------------------------------------------- #

def load_object_info_schema() -> dict[str, dict[str, Any]]:
    """Aggregate every cached object_info dump into one class->entry dict.

    Later entries override earlier ones — runpod caches have far better
    coverage than the local one, so this is fine.
    """
    schema: dict[str, dict[str, Any]] = {}
    if not CACHE_DIR.is_dir():
        return schema
    for path in sorted(CACHE_DIR.glob("object_info*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if isinstance(data, dict):
            for cls, entry in data.items():
                if isinstance(entry, dict):
                    schema[cls] = entry
    return schema


def output_comment_for(class_type: str, schema: dict[str, dict[str, Any]]) -> str:
    entry = schema.get(class_type)
    if not entry:
        return f"# outputs: see `nodes spec {class_type}`  # TODO: schema not in index"
    output_types = entry.get("output") or []
    output_names = entry.get("output_name") or []
    if not output_types:
        return f"# outputs: see `nodes spec {class_type}`  # TODO: no outputs in cached schema"
    parts: list[str] = []
    for i, t in enumerate(output_types):
        name = output_names[i] if i < len(output_names) else t
        # Prefer the named handle when distinct from the type; otherwise use the type only.
        if name and name.upper() != t.upper():
            parts.append(f"{i}={t}({name})")
        else:
            parts.append(f"{i}={t}")
    return "# outputs: " + ", ".join(parts)


# --------------------------------------------------------------------------- #
# AST extraction                                                              #
# --------------------------------------------------------------------------- #

@dataclass
class NodeCall:
    """A single _node(...) call extracted from the build() body."""

    original_var: str
    class_type: str
    node_id: str
    kwargs: list[tuple[str, ast.AST]]  # in source order
    extras: ast.AST | None = None
    # populated later
    role_name: str = ""
    section: str = "MISC"


@dataclass
class ParseResult:
    module_docstring: str | None
    imports_src: str
    pre_build_src: str            # everything between imports and build()
    build_signature_src: str       # "def build() -> VibeWorkflow:\n    wf = ..."
    build_pre_node_src: str        # body lines before the first _node call (e.g. wf = VibeWorkflow(...))
    node_calls: list[NodeCall]
    post_node_src: str             # body lines after the last _node call (finalize, register_input, etc.)
    has_node_helper: bool


_NODE_HELPER_NAME = "_node"
_AT_HELPER_NAME = "_at"
_PUBLIC_NODE_HELPER_NAME = "node"
_RAW_NODE_HELPER_NAME = "raw_call"
_PUBLIC_NODE_HELPER_NAMES = {_PUBLIC_NODE_HELPER_NAME, _RAW_NODE_HELPER_NAME}


def _extract_id_sidecar(tree: ast.Module) -> dict[str, str]:
    ids: dict[str, str] = {}
    for stmt in tree.body:
        value_node: ast.AST | None = None
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            if stmt.targets[0].id != "ID":
                continue
            value_node = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "ID":
            value_node = stmt.value
        else:
            continue
        if value_node is None:
            return {}
        try:
            value = ast.literal_eval(value_node)
        except Exception:
            return {}
        if isinstance(value, dict):
            for key, item in value.items():
                ids[str(key)] = str(item)
        return ids
    return {}


def _literal_node_id(node: ast.AST, id_sidecar: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "ID":
        key_node = node.slice
        if isinstance(key_node, ast.Constant):
            return id_sidecar.get(str(key_node.value))
    return None


def _normalize_at_helper_source(source: str) -> str:
    """Normalize legacy narrative `_at(wf, ID[...], "Class")` calls to `_node`."""
    if "def _node(" in source or "def _at(" not in source:
        return source
    source = source.replace(
        "def _at(wf: VibeWorkflow, _id: str, class_type: str",
        "def _node(wf: VibeWorkflow, class_type: str, _id: str",
    )
    return re.sub(
        r"_at\(\s*wf,\s*(ID\[[^\]]+\]|['\"][^'\"]+['\"]),\s*(['\"][^'\"]+['\"])",
        r"_node(wf, \2, \1",
        source,
    )


def parse_template(source: str) -> ParseResult:
    tree = ast.parse(source)

    module_docstring = ast.get_docstring(tree)

    # Split source by line so we can reuse slices verbatim.
    lines = source.splitlines(keepends=True)

    build_func: ast.FunctionDef | None = None
    helper_func: ast.FunctionDef | None = None
    helper_name = _NODE_HELPER_NAME
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name == "build":
                build_func = node
            elif node.name == _NODE_HELPER_NAME:
                helper_func = node
                helper_name = _NODE_HELPER_NAME
            elif node.name == _AT_HELPER_NAME and helper_func is None:
                helper_func = node
                helper_name = _AT_HELPER_NAME

    if build_func is None:
        raise SystemExit("error: input file has no top-level `build()` function")
    if helper_func is None:
        helper_names = {
            call.func.id
            for call in ast.walk(build_func)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in {_NODE_HELPER_NAME, _AT_HELPER_NAME, *_PUBLIC_NODE_HELPER_NAMES}
        }
        if _NODE_HELPER_NAME in helper_names:
            helper_name = _NODE_HELPER_NAME
        elif _AT_HELPER_NAME in helper_names:
            helper_name = _AT_HELPER_NAME
        elif helper_names & _PUBLIC_NODE_HELPER_NAMES:
            helper_name = next(iter(helper_names & _PUBLIC_NODE_HELPER_NAMES))
        else:
            raise SystemExit(
                "error: input file does not define top-level `_node`, `_at`, or `node` calls.\n"
                "       This codemod only handles templates that use one of those shims."
            )
    id_sidecar = _extract_id_sidecar(tree)

    # Imports = everything before build() that isn't the helper. We treat
    # "imports" loosely as "every top-level statement before build()".
    imports_end_line = build_func.lineno - 1  # 1-indexed
    # But strip the module docstring out of "imports" to avoid duplicating it.
    pre_build_src = "".join(lines[: imports_end_line - 1])

    # Build function source segments.
    build_lines = lines[build_func.lineno - 1 : build_func.end_lineno]

    # Find the line numbers of all _node calls within build().
    node_calls: list[NodeCall] = []
    first_node_lineno: int | None = None
    last_node_endlineno: int | None = None

    for stmt in ast.walk(build_func):
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        value = stmt.value
        if not isinstance(value, ast.Call):
            continue
        if not (isinstance(value.func, ast.Name) and value.func.id == helper_name):
            continue

        var_name = stmt.targets[0].id

        # Positional args:
        #   _node(wf, class_type, id, ...)
        #   node(wf, class_type, id, ...)
        #   _at(wf, ID["role"], class_type, ...)
        if len(value.args) < 3 and helper_name == "raw_call":
            class_arg = value.args[0] if len(value.args) >= 1 else None
            id_arg = value.args[1] if len(value.args) >= 2 else None
        elif len(value.args) < 3:
            raise SystemExit(
                f"error: unexpected {helper_name} call at line {stmt.lineno}: needs >=3 positional args"
            )
        elif helper_name == _AT_HELPER_NAME:
            id_arg = value.args[1]
            class_arg = value.args[2]
        else:
            class_arg = value.args[1]
            id_arg = value.args[2]
        if not isinstance(class_arg, ast.Constant) or not isinstance(class_arg.value, str):
            raise SystemExit(f"error: line {stmt.lineno}: class_type arg must be a string literal")
        node_id = _literal_node_id(id_arg, id_sidecar)
        if node_id is None:
            raise SystemExit(f"error: line {stmt.lineno}: id arg must be a literal or ID[...] lookup")

        class_type = class_arg.value

        kwargs: list[tuple[str, ast.AST]] = []
        extras: ast.AST | None = None
        for kw in value.keywords:
            if kw.arg is None:
                raise SystemExit(f"error: line {stmt.lineno}: **kwargs splat not supported")
            if kw.arg == "_extras":
                extras = kw.value
            else:
                kwargs.append((kw.arg, kw.value))

        call = NodeCall(
            original_var=var_name,
            class_type=class_type,
            node_id=node_id,
            kwargs=kwargs,
            extras=extras,
        )
        node_calls.append(call)
        if first_node_lineno is None:
            first_node_lineno = stmt.lineno
        last_node_endlineno = stmt.end_lineno

    if not node_calls:
        raise SystemExit(f"error: no {helper_name}(...) calls found inside build()")

    # We split the build body into three string regions:
    #   * signature + body lines before the first _node call (wf init, etc.)
    #   * the node calls (we'll regenerate these entirely)
    #   * body lines after the last _node call (finalize_metadata, register_input, return)
    sig_and_pre_end = first_node_lineno - 1  # 1-indexed inclusive
    post_start = last_node_endlineno  # 1-indexed inclusive

    # Identify signature line vs body intro lines.
    # build_func.lineno is the def line; first non-def line is body[0].
    # Find the body region (after the optional docstring).
    body_start_line = build_func.body[0].lineno
    # We'll preserve everything from the def through line before first node call.
    signature_block = "".join(lines[build_func.lineno - 1 : sig_and_pre_end])
    post_node_src = "".join(lines[post_start:build_func.end_lineno])

    return ParseResult(
        module_docstring=module_docstring,
        imports_src=pre_build_src,
        pre_build_src="",
        build_signature_src=signature_block,
        build_pre_node_src="",
        node_calls=node_calls,
        post_node_src=post_node_src,
        has_node_helper=helper_func is not None,
    )


# --------------------------------------------------------------------------- #
# Role naming                                                                 #
# --------------------------------------------------------------------------- #

_CAMEL_TO_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _snake_case(name: str) -> str:
    s = _CAMEL_TO_SNAKE_RE.sub("_", name).lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    return s.strip("_") or "node"


def _safe_id_for_var(node_id: str) -> str:
    """Sanitise a ComfyUI node id for use inside a Python identifier.

    Subgraph ids contain a colon (e.g. ``"238:224"``). Colons (and any other
    non-identifier characters) are replaced with underscores. The original
    node id is preserved verbatim in ``_node(...)`` string arguments — only
    the *variable name* spelling is sanitised here.
    """
    sanitised = re.sub(r"[^A-Za-z0-9_]+", "_", str(node_id)).strip("_")
    return sanitised or "node"


def assign_role_names(node_calls: list[NodeCall]) -> None:
    """Assign a role-based variable name to each NodeCall.

    Step 1: base name from ROLE_NAMES, else snake_case(class_type) + "_" + id.
    Step 2: if the base name collides across multiple node calls, append _<id>.
    """
    base_counts: dict[str, int] = defaultdict(int)
    base_names: list[str] = []
    for nc in node_calls:
        safe_id = _safe_id_for_var(nc.node_id)
        base = ROLE_NAMES.get(nc.class_type) or f"{_snake_case(nc.class_type)}_{safe_id}"
        base_names.append(base)
        base_counts[base] += 1

    seen_for_base: dict[str, int] = defaultdict(int)
    for nc, base in zip(node_calls, base_names):
        if base_counts[base] > 1:
            # Disambiguate by node id.
            nc.role_name = f"{base}_{_safe_id_for_var(nc.node_id)}"
        else:
            nc.role_name = base


def classify_sections(node_calls: list[NodeCall]) -> None:
    for nc in node_calls:
        nc.section = _semantic_section_for_class(nc.class_type)


def _semantic_section_for_class(class_type: str) -> str:
    section = SECTION_OF_CLASS.get(class_type)
    if section is not None:
        return section
    lowered = class_type.lower()
    if "textencode" in lowered or "cliptextencode" in lowered:
        return "TEXT CONDITIONING"
    if "latent" in lowered:
        return "LATENT"
    if "ksampler" in lowered or "sampler" in lowered or "sampling" in lowered or "sigmas" in lowered:
        return "SAMPLING"
    if "decode" in lowered:
        return "DECODE"
    if lowered.startswith("save") or lowered.startswith("preview"):
        return "OUTPUT"
    if "resize" in lowered or "scale" in lowered or "preprocess" in lowered:
        return "IMAGE PREP"
    if "control" in lowered or "canny" in lowered or "depth" in lowered or "preprocessor" in lowered:
        return "CONTROL"
    if "loader" in lowered or "load" in lowered:
        return "LOADERS"
    return "SAMPLING"


# --------------------------------------------------------------------------- #
# Hoisted PARAMS extraction                                                   #
# --------------------------------------------------------------------------- #

@dataclass
class ParamBinding:
    logical_name: str
    node_id: str
    field: str
    value: Any  # literal Python value
    group: str  # e.g. "resolution"
    fallback: bool  # if True, we couldn't extract a literal — value is the raw source


def _literal_from_ast(node: ast.AST) -> tuple[bool, Any]:
    """Return (ok, value) if the AST node is a Python literal."""
    try:
        return True, ast.literal_eval(node)
    except Exception:
        return False, None


def _group_for(name: str) -> str:
    for grp, members in PARAM_GROUPS:
        if name in members:
            return grp
    return "other"


def extract_params(
    unbound_inputs: dict[str, str],
    node_calls_by_id: dict[str, NodeCall],
) -> list[ParamBinding]:
    """Look up each unbound input's target node.field and grab the literal value."""
    out: list[ParamBinding] = []
    for logical, target in unbound_inputs.items():
        if not isinstance(target, str) or "." not in target:
            continue
        node_id, field_name = target.split(".", 1)
        nc = node_calls_by_id.get(node_id)
        if nc is None:
            out.append(ParamBinding(logical, node_id, field_name, None, _group_for(logical), True))
            continue
        # Find the kwarg.
        ast_val: ast.AST | None = None
        for k, v in nc.kwargs:
            if k == field_name:
                ast_val = v
                break
        if ast_val is None:
            out.append(ParamBinding(logical, node_id, field_name, None, _group_for(logical), True))
            continue
        ok, lit = _literal_from_ast(ast_val)
        if not ok:
            # Not a literal (likely a handle ref) — skip hoisting.
            continue
        out.append(ParamBinding(logical, node_id, field_name, lit, _group_for(logical), False))
    return out


def find_unbound_inputs(tree_source: str) -> dict[str, Any]:
    """Extract READY_METADATA['unbound_inputs'] without executing the module."""
    tree = ast.parse(tree_source)
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "READY_METADATA":
                    if isinstance(stmt.value, ast.Dict):
                        for k, v in zip(stmt.value.keys, stmt.value.values):
                            if isinstance(k, ast.Constant) and k.value == "unbound_inputs":
                                if isinstance(v, ast.Dict):
                                    out: dict[str, Any] = {}
                                    for kk, vv in zip(v.keys, v.values):
                                        if isinstance(kk, ast.Constant) and isinstance(kk.value, str):
                                            ok, literal = _literal_from_ast(vv)
                                            if ok:
                                                out[kk.value] = literal
                                    return out
                    elif _is_ready_metadata_build_call(stmt.value):
                        return {
                            name: spec["default"]
                            for name, spec in _collect_public_input_specs(tree_source).items()
                        }
    return {}


# --------------------------------------------------------------------------- #
# Kwarg rendering                                                             #
# --------------------------------------------------------------------------- #

@dataclass
class RenderContext:
    role_by_id: dict[str, str]
    param_node_field: dict[tuple[str, str], str]  # (node_id, field) -> logical param name


@dataclass
class RenderedValue:
    """A rendered kwarg value with an optional trailing comment."""
    expr: str
    trailing_comment: str | None = None


def _is_out_call(node: ast.AST) -> tuple[bool, str | None, int | str | None]:
    """Detect `<name>.out(<int_or_str>)` patterns; return (matched, var_name, slot)."""
    if not isinstance(node, ast.Call):
        return False, None, None
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "out":
        return False, None, None
    if not isinstance(node.func.value, ast.Name):
        return False, None, None
    if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
        return False, None, None
    raw = node.args[0].value
    if isinstance(raw, int):
        slot: int | str = raw
    elif isinstance(raw, str):
        try:
            slot = int(raw)
        except ValueError:
            slot = raw
    else:
        return False, None, None
    return True, node.func.value.id, slot


def render_kwarg_value(
    value: ast.AST,
    original_var_to_role: dict[str, str],
    param_lookup: dict[tuple[str, str], str],
    nc: NodeCall,
    kw_name: str,
) -> str:
    # Rewrite var.out(N) to role_var.out(N).
    is_out, var, slot = _is_out_call(value)
    if is_out and var in original_var_to_role:
        slot_expr = repr(slot) if isinstance(slot, str) else str(slot)
        return f"{original_var_to_role[var]}.out({slot_expr})"

    # Check if (this node, this field) corresponds to a hoisted param.
    key = (nc.node_id, kw_name)
    if key in param_lookup:
        return f'PARAMS["{param_lookup[key]}"]'

    # Fallback: unparse the AST node verbatim.
    return ast.unparse(value)


# --------------------------------------------------------------------------- #
# Emission                                                                    #
# --------------------------------------------------------------------------- #

def _get_codemod_version() -> str:
    """Returns version string like ``v2.3.2+g9c5810f+dirty``."""
    try:
        version_path = REPO_ROOT / "pyproject.toml"
        content = version_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        pkg_version = match.group(1) if match else "0.0.0"
    except Exception:
        pkg_version = "0.0.0"
    try:
        import subprocess
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, text=True,
        ).strip()
        dirty_check = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=REPO_ROOT,
        ).returncode
        dirty = "+dirty" if dirty_check != 0 else ""
    except Exception:
        git_sha = "unknown"
        dirty = ""
    return f"{pkg_version}+g{git_sha}{dirty}"


def _marker_line() -> str:
    """Return the vibecomfy: narrative marker line with version info."""
    return f"# vibecomfy: narrative (generated by tools/narrate_template.py @ {_get_codemod_version()})"


MARKER_LINE = _marker_line()
NARRATIVE_DOCSTRING_DEFAULT = "Generated narrative form."

_AUTO_DOCSTRING_MARKERS = (
    "Auto-generated ready_template",
    "Generated narrative form",
)


def _model_family_from_key(model_key: str) -> str:
    """Derive a human-readable model family name from a model dict key."""
    # Strip precision/format suffixes
    name = model_key
    for suffix in ("_fp8_e4m3fn_scaled", "_fp8_e4m3fn", "_fp16", "_fp32", "_fp8_scaled", "_fp8", "_bf16"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    # Replace underscores with spaces
    name = name.replace("_", " ").strip()
    # Split letter-digit compounds at word boundaries only: "wan2" -> "wan 2"
    name = re.sub(r'\b([a-zA-Z]+)(\d+)\b', r'\1 \2', name)
    # Fix version/size numbers: "wan 2 1" -> "wan 2.1", "0 6b" -> "0.6b"
    name = re.sub(r'(\d+) (\d+)(?=[bpBkK]?\b)', r'\1.\2', name)
    # Title-case words, but preserve known acronyms
    words = []
    for w in name.split():
        upper = w.upper()
        if upper in ("VAE", "CLIP", "LTX", "T5", "UMT5", "LORA", "GGUF", "F16", "BF16", "I2V", "T2V", "T2I", "T2A"):
            words.append(upper)
        elif re.match(r'^\d+(\.\d+)?[bB]$', w):  # 14b -> 14B (check before broader [bpBkK])
            words.append(w.upper())
        elif re.match(r'^\d+[bpBkK]$', w):  # 480p, 14B, etc.
            words.append(w)
        elif re.match(r'^\d+(\.\d+)?$', w):  # bare version number like 2512
            words.append(w)
        else:
            # Capitalize: lowercase words get .capitalize(), mixed-case get .title()
            words.append(w.capitalize() if w.islower() and len(w) > 2 else w.title())
    # Collapse multiple spaces
    result = re.sub(r' +', ' ', " ".join(words)).strip()
    return result


def _capability_oneliner(capability: str, model_keys: list[str]) -> str:
    """Generate a one-liner intent from capability and dominant model family."""
    cap_map = {
        "image_to_video": "Image-to-video generation",
        "text_to_image": "Text-to-image generation",
        "text_to_audio": "Text-to-audio generation",
        "image_edit": "Image editing",
        "audio_generation": "Audio generation",
        "video_generation": "Video generation",
    }
    cap_desc = cap_map.get(capability, capability.replace("_", " ").title())
    if model_keys:
        model_family = _model_family_from_key(model_keys[0])
        if model_family:
            return f"{cap_desc} with {model_family}"
    return cap_desc


def _generate_structured_docstring(
    metadata: dict[str, Any],
    specs: dict[str, dict[str, Any]],
    output_type: str | None,
    output_node_id: str,
    custom_node_packs: list[str] | None,
    existing_docstring: str | None = None,
    model_keys: list[str] | None = None,
) -> str:
    """Generate a structured module docstring for a ready template.

    Preserves a human-edited first sentence (non-auto-generated) across re-ports.
    Mechanical sections (Public inputs, Output, Source, Packs) are always regenerated.
    """
    capability = metadata.get("capability", "workflow")
    source_workflow = metadata.get("source_workflow", "")
    if model_keys is None:
        raw_model_assets = metadata.get("model_assets", {})
        if isinstance(raw_model_assets, dict):
            model_keys = list(raw_model_assets.keys())
        elif isinstance(raw_model_assets, list):
            model_keys = [
                str(item.get("name") or item.get("filename"))
                for item in raw_model_assets
                if isinstance(item, dict) and (item.get("name") or item.get("filename"))
            ]
        else:
            model_keys = []

    # ---- One-liner intent (preserve human edits) ----
    existing_first_sentence = ""
    if existing_docstring:
        existing = existing_docstring.strip()
        if existing and not any(existing.startswith(m) for m in _AUTO_DOCSTRING_MARKERS):
            # Extract first sentence (up to first period+space or newline)
            first_line = existing.splitlines()[0] if "\n" in existing else existing
            existing_first_sentence = first_line.rstrip(".").strip()

    if existing_first_sentence:
        oneliner = existing_first_sentence
    else:
        oneliner = _capability_oneliner(capability, model_keys)

    lines: list[str] = [oneliner + ".", ""]

    # ---- Public inputs ----
    if specs:
        lines.append("Public inputs:")
        # Group required vs optional
        required = []
        optional = []
        for name, spec in specs.items():
            desc = spec.get("description", "").rstrip(".")
            if spec.get("required"):
                required.append((name, desc))
            else:
                optional.append((name, desc))

        for name, desc in required:
            lines.append(f"    {name} (required): {desc}" if desc else f"    {name} (required)")
        for name, desc in optional:
            lines.append(f"    {name}: {desc}" if desc else f"    {name}")
        lines.append("")

    # ---- Output ----
    output_desc = output_type or "unknown"
    output_label = f"{output_desc}"
    if output_node_id:
        output_label += f" (node {output_node_id})"
    lines.append(f"Output: {output_label}.")
    lines.append("")

    # ---- Source ----
    if source_workflow:
        lines.append(f"Source:  {source_workflow}")
        lines.append("")

    # ---- Packs ----
    if custom_node_packs:
        packs_str = ", ".join(sorted(custom_node_packs))
        lines.append(f"Packs:   {packs_str}")
        lines.append("")

    return "\n".join(lines)


def _replace_module_docstring(source: str, new_docstring: str) -> str:
    """Replace the module-level docstring in *source* with *new_docstring*."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    existing = ast.get_docstring(tree)
    if existing is None:
        # No existing docstring — insert after the marker/imports
        return _insert_docstring_after_imports(source, new_docstring)

    # Find the docstring node (first Expr whose value is a Constant str)
    for i, stmt in enumerate(tree.body):
        if (isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)):
            # Get the line span of the docstring
            start_lineno = stmt.lineno
            end_lineno = getattr(stmt, 'end_lineno', None) or start_lineno
            # Convert to byte offsets
            src_lines = source.splitlines(keepends=True)
            # Find the start of the docstring (including quotes)
            raw_start = sum(len(l) for l in src_lines[:start_lineno - 1])
            # Find the end of the docstring
            docstring_text = ast.get_docstring(tree, clean=False)
            if docstring_text:
                # Find the actual docstring in source around start position
                snippet = source[raw_start:]
                m = re.search(r'("""|\'\'\')', snippet)
                if m:
                    quote_start = raw_start + m.start()
                    quote_char = m.group(1)
                    # Find closing quotes
                    close_pos = source.find(quote_char, quote_start + 3)
                    if close_pos > quote_start:
                        # Include trailing newline if present
                        end_pos = close_pos + 3
                        if end_pos < len(source) and source[end_pos] == '\n':
                            end_pos += 1
                        formatted = f'"""{new_docstring}"""\n'
                        return source[:quote_start] + formatted + source[end_pos:]
            break

    return _insert_docstring_after_imports(source, new_docstring)


def _insert_docstring_after_imports(source: str, new_docstring: str) -> str:
    """Insert a docstring after any header comments/imports."""
    lines = source.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            insert_at = i + 1
            continue
        if stripped.startswith("def ") or stripped.startswith("class ") or stripped[0].isalpha() or stripped[0] == '_':
            insert_at = i
            break
        insert_at = i + 1
    # Insert docstring at the right position
    formatted = f'"""{new_docstring}"""\n'
    lines.insert(insert_at, formatted)
    return "".join(lines)


def render_params_block(bindings: list[ParamBinding]) -> str:
    """Render the hoisted PARAMS dict, grouped with comment headers."""
    if not bindings:
        return ""

    # Order groups by PARAM_GROUPS order, then "other".
    group_order = [g for g, _ in PARAM_GROUPS] + ["other"]
    by_group: dict[str, list[ParamBinding]] = defaultdict(list)
    for b in bindings:
        by_group[b.group].append(b)

    lines = ["PARAMS: dict[str, object] = {"]
    for grp in group_order:
        items = by_group.get(grp)
        if not items:
            continue
        lines.append(f"    # --- {grp} ---")
        for b in items:
            if b.fallback:
                lines.append(
                    f"    {b.logical_name!r}: None,  # TODO: target {b.node_id}.{b.field} not"
                    " literal-extractable"
                )
            else:
                lines.append(f"    {b.logical_name!r}: {b.value!r},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_id_block(node_calls: list[NodeCall]) -> str:
    """Render the ID sidecar dict, grouped by section."""
    sections: dict[str, list[NodeCall]] = OrderedDict((s, []) for s in SECTION_ORDER)
    for nc in node_calls:
        sections.setdefault(nc.section, []).append(nc)
    lines = ["ID: dict[str, str] = {"]
    for section in SECTION_ORDER:
        items = sections.get(section) or []
        if not items:
            continue
        lines.append(f"    # === {section} ===")
        for nc in items:
            lines.append(f"    {nc.role_name!r}: {nc.node_id!r},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_node_call(
    nc: NodeCall,
    ctx_var_to_role: dict[str, str],
    param_lookup: dict[tuple[str, str], str],
    output_comment: str,
) -> str:
    """Emit a single `_at(...)` assignment with a trailing outputs comment."""
    kwarg_parts: list[str] = []
    for kw_name, ast_val in nc.kwargs:
        rendered = render_kwarg_value(ast_val, ctx_var_to_role, param_lookup, nc, kw_name)
        kwarg_parts.append(f"{kw_name}={rendered}")

    # Handle _extras (pass through unchanged as a dict literal).
    if nc.extras is not None:
        # We still want to rewrite handle .out(N) references inside the extras dict.
        rewritten_extras = _rewrite_handles_in_ast(nc.extras, ctx_var_to_role)
        kwarg_parts.append(f"_extras={ast.unparse(rewritten_extras)}")

    head = f'    {nc.role_name} = _at(wf, ID["{nc.role_name}"], "{nc.class_type}",'
    if not kwarg_parts:
        body = f"{head})  {output_comment}"
        return body

    # Multi-line form, one kwarg per line for readability.
    lines = [head]
    for part in kwarg_parts:
        lines.append(f"        {part},")
    # Place the closing paren and outputs comment on the same line.
    lines.append(f"    )  {output_comment}")
    return "\n".join(lines)


def _collect_var_deps(value: ast.AST) -> set[str]:
    """Find every `<var>.out(...)` reference within the given AST node."""
    deps: set[str] = set()
    for sub in ast.walk(value):
        ok, var, _slot = _is_out_call(sub)
        if ok and var is not None:
            deps.add(var)
    return deps


def _topo_sort_calls(calls: list[NodeCall]) -> list[NodeCall]:
    """Kahn-style topo sort with stable tie-breaking by (section_index, orig_index).

    Edges are derived from `.out(N)` references in kwargs and `_extras` values.
    """
    section_index = {s: i for i, s in enumerate(SECTION_ORDER)}
    fallback_section_idx = len(SECTION_ORDER)

    nc_by_var = {nc.original_var: nc for nc in calls}
    orig_index = {nc.original_var: i for i, nc in enumerate(calls)}

    # For each call: set of var-names it depends on.
    deps: dict[str, set[str]] = {}
    for nc in calls:
        d: set[str] = set()
        for _kw, v in nc.kwargs:
            d.update(_collect_var_deps(v))
        if nc.extras is not None:
            d.update(_collect_var_deps(nc.extras))
        # Restrict to known node-call vars (ignore other locals).
        deps[nc.original_var] = {x for x in d if x in nc_by_var}

    # Reverse adjacency to count remaining in-degree.
    in_degree = {v: len(d) for v, d in deps.items()}
    dependents: dict[str, list[str]] = defaultdict(list)
    for v, d in deps.items():
        for src in d:
            dependents[src].append(v)

    # Ready set: nodes with no remaining deps. Use a sorted list (manually picked)
    # to preserve deterministic ordering by (section_index, original_index).
    def _key(var: str) -> tuple[int, int]:
        nc = nc_by_var[var]
        return (section_index.get(nc.section, fallback_section_idx), orig_index[var])

    ready = [v for v, d in in_degree.items() if d == 0]
    ready.sort(key=_key)

    out: list[NodeCall] = []
    while ready:
        ready.sort(key=_key)
        v = ready.pop(0)
        out.append(nc_by_var[v])
        for dep in dependents.get(v, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                ready.append(dep)

    if len(out) != len(calls):
        # Cycle (shouldn't happen for valid Comfy graphs) — fall back to source order.
        return calls
    return out


def _rewrite_handles_in_ast(node: ast.AST, var_to_role: dict[str, str]) -> ast.AST:
    """Walk an AST and rewrite var.out(N) references to role_var.out(N)."""

    class Rewriter(ast.NodeTransformer):
        def visit_Call(self, n: ast.Call) -> ast.AST:
            self.generic_visit(n)
            ok, var, slot = _is_out_call(n)
            if ok and var in var_to_role and slot is not None:
                return ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=var_to_role[var], ctx=ast.Load()),
                        attr="out",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=slot)],
                    keywords=[],
                )
            return n

    return Rewriter().visit(node)


# --------------------------------------------------------------------------- #
# Main render                                                                 #
# --------------------------------------------------------------------------- #

NEW_HELPER_SRC = '''
def _at(wf: VibeWorkflow, _id: str, class_type: str, _extras: dict | None = None, **kwargs):
    """Create a ComfyUI node and force-assign its node id.

    The id sits in position 2 (right after `wf`) so it's visually prominent —
    callers pass `ID["role_name"]` so the role-name and id stay co-located in
    the ID sidecar dict above. The rest of the body matches the original
    `_node` helper: extras get spliced onto the builder, and the rename-after-
    creation hack patches the wf.nodes table and any in-flight edges so the id
    we passed is what actually lands in the graph.
    """
    from vibecomfy.handles import Handle

    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
'''.lstrip()


def render_output(
    source: str,
    parsed: ParseResult,
    bindings: list[ParamBinding],
    schema: dict[str, dict[str, Any]],
) -> str:
    # Build supporting lookups.
    var_to_role = {nc.original_var: nc.role_name for nc in parsed.node_calls}
    param_lookup = {(b.node_id, b.field): b.logical_name for b in bindings if not b.fallback}

    # Topologically sort, breaking ties by (section_index, original_index) so the
    # output groups by section as much as the dep graph allows while never
    # emitting a node before its inputs.
    ordered_calls = _topo_sort_calls(parsed.node_calls)

    # Module-level header.
    doc = parsed.module_docstring or NARRATIVE_DOCSTRING_DEFAULT
    pipeline_summary = (
        "\nNarrative-form pipeline: inputs -> loaders -> model patch stack ->\n"
        "text conditioning -> image prep -> control guide branches ->\n"
        "latent assembly -> sampling -> decode -> output."
    )
    if "pipeline" not in doc.lower():
        doc = doc.rstrip() + "\n" + pipeline_summary

    header = [MARKER_LINE, f'"""{doc}"""', "from __future__ import annotations", ""]

    # Find the original imports (everything from `from __future__` onward up to build()).
    # Re-extract them cleanly: every top-level Import/ImportFrom node.
    tree = ast.parse(source)
    import_lines: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            # __future__ imports go in the header already; skip duplicates.
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
                continue
            import_lines.append(ast.unparse(stmt))
    header.extend(import_lines)
    if not any("from vibecomfy.templates import" in line and "_at" in line for line in import_lines):
        header.append("from vibecomfy.templates import _at")
    header.append("")
    header.append("")

    # PARAMS block.
    params_src = render_params_block(bindings)

    # Pull the original module-level assignments (model assets list, READY_METADATA,
    # READY_REQUIREMENTS) verbatim from the source — easiest way is to slice between
    # the last import and the `def build` line.
    lines = source.splitlines(keepends=True)
    build_func = next(
        n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "build"
    )
    last_import_end = 0
    for stmt in ast.parse(source).body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            last_import_end = max(last_import_end, stmt.end_lineno or 0)
    pre_build_block = "".join(lines[last_import_end:build_func.lineno - 1])
    # Strip leading blank lines for tidiness.
    pre_build_block = pre_build_block.lstrip("\n")
    pre_build_block = _strip_module_assignment(pre_build_block, "READY_REQUIREMENTS")

    # ID block.
    id_block = render_id_block(parsed.node_calls)

    # Build the new build() body.
    build_lines: list[str] = []
    build_lines.append("def build() -> VibeWorkflow:")
    build_lines.append('    wf = VibeWorkflow(')
    build_lines.append('        READY_METADATA["ready_template"],')
    build_lines.append("        WorkflowSource(")
    build_lines.append('            id=READY_METADATA["ready_template"],')
    build_lines.append("            path=__file__,")
    build_lines.append('            source_type="ready_template",')
    build_lines.append("        ),")
    build_lines.append("    )")
    build_lines.append("")

    # Emit in topo order, printing a section banner the first time a node
    # from a new section appears.
    current_section: str | None = None
    for nc in ordered_calls:
        if nc.section != current_section:
            current_section = nc.section
            build_lines.append(f"    # {'═' * 4} {current_section} {'═' * 4}")
        output_comment = output_comment_for(nc.class_type, schema)
        build_lines.append(render_node_call(nc, var_to_role, param_lookup, output_comment))
        build_lines.append("")

    # Tail: take whatever was after the last _node call (finalize_metadata,
    # register_input calls, apply_ready_template_policy, bind_output, return)
    # and rewrite any references to original variable names that we renamed.
    tail = parsed.post_node_src
    tail = _rewrite_post_node_tail(tail, var_to_role)
    # Make sure the tail is properly indented relative to build(); the slice
    # we took already preserves the original 4-space indent.
    build_lines.append(tail.rstrip())
    build_lines.append("")

    build_src = "\n".join(build_lines)

    # Assemble.
    out_parts = [
        "\n".join(header),
        pre_build_block,
        params_src,
        "",
        id_block,
        "",
        build_src,
    ]
    return "\n".join(out_parts)


def _strip_module_assignment(source: str, name: str) -> str:
    """Remove a top-level assignment from a source block."""
    if not source.strip():
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.splitlines(keepends=True)
    remove_ranges: list[tuple[int, int]] = []
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in stmt.targets):
            continue
        end_lineno = stmt.end_lineno or stmt.lineno
        remove_ranges.append((stmt.lineno, end_lineno))
    if not remove_ranges:
        return source
    removed_lines: set[int] = set()
    for start, end in remove_ranges:
        removed_lines.update(range(start, end + 1))
    return "".join(line for lineno, line in enumerate(lines, start=1) if lineno not in removed_lines).lstrip("\n")


_VAR_REWRITE_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _rewrite_post_node_tail(src: str, var_to_role: dict[str, str]) -> str:
    """Rewrite `<orig_var>.<attr>` references in the tail source.

    The tail contains things like ``positive.node.inputs["text"]`` that refer
    to local variables created by the _node calls. We need those references
    to use the new role-derived names.
    """
    out = src
    # Sort longest-first so prefixes don't shadow.
    for orig, role in sorted(var_to_role.items(), key=lambda kv: -len(kv[0])):
        if orig == role:
            continue
        if orig not in _VAR_REWRITE_RE_CACHE:
            _VAR_REWRITE_RE_CACHE[orig] = re.compile(rf"\b{re.escape(orig)}\b")
        out = _VAR_REWRITE_RE_CACHE[orig].sub(role, out)
    return out


# --------------------------------------------------------------------------- #
# Verify subcommand                                                           #
# --------------------------------------------------------------------------- #

def _deep_diff(
    orig: Any, cand: Any, path: str = ""
) -> list[dict[str, Any]]:
    """Recursively compare two API dicts, returning a list of {path, original, candidate} diffs."""
    diffs: list[dict[str, Any]] = []
    if isinstance(orig, (int, float)) and isinstance(cand, (int, float)) and not isinstance(orig, bool) and not isinstance(cand, bool):
        if abs(float(orig) - float(cand)) <= 1e-12:
            return diffs
        diffs.append({"path": path, "original": orig, "candidate": cand})
    elif type(orig) != type(cand):
        diffs.append({"path": path, "original": orig, "candidate": cand})
    elif isinstance(orig, dict):
        all_keys = set(orig) | set(cand)
        for k in sorted(all_keys, key=str):
            sub = _deep_diff(orig.get(k), cand.get(k), f"{path}.{k}" if path else str(k))
            diffs.extend(sub)
    elif isinstance(orig, list):
        max_len = max(len(orig), len(cand))
        for i in range(max_len):
            o = orig[i] if i < len(orig) else None
            c = cand[i] if i < len(cand) else None
            sub = _deep_diff(o, c, f"{path}[{i}]")
            diffs.extend(sub)
    elif orig != cand:
        diffs.append({"path": path, "original": orig, "candidate": cand})
    return diffs


def _canonical_input_name(name: str) -> str:
    if name == "negative":
        return "negative_prompt"
    if name == "fps":
        return "output_fps"
    return name


def _canonical_description(name: str) -> str:
    return _CANONICAL_DESCRIPTIONS.get(name, f"{name.replace('_', ' ').capitalize()}.")


def _collect_register_input_names(tree_source: str) -> list[str]:
    """Parse a template file's AST and collect every `wf.register_input("<name>", ...)` first arg."""
    tree = ast.parse(tree_source)
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "register_input":
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            names.append(first_arg.value)
        else:
            print(
                f"warning: register_input first arg is not a string literal at line {node.lineno}",
                    file=sys.stderr,
                )
    return names


def _collect_bind_input_names(tree_source: str) -> list[str]:
    """Collect names from legacy ``bind_input(wf, "<name>", ...)`` calls."""
    tree = ast.parse(tree_source)
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "bind_input":
            continue
        if len(node.args) < 2:
            continue
        name_arg = node.args[1]
        if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
            names.append(name_arg.value)
    return names


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _is_ready_metadata_build_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func) in {
        "ReadyMetadata.build",
        "templates.ReadyMetadata.build",
        "vibecomfy.templates.ReadyMetadata.build",
    }


def _is_input_spec_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func) in {
        "InputSpec",
        "templates.InputSpec",
        "vibecomfy.templates.InputSpec",
    }


def _literal_keyword(call: ast.Call, name: str) -> tuple[bool, Any]:
    for keyword in call.keywords:
        if keyword.arg == name:
            return _literal_from_ast(keyword.value)
    return False, None


def _input_spec_value(call: ast.Call, index: int, keyword: str, fallback: Any = None) -> Any:
    if len(call.args) > index:
        ok, value = _literal_from_ast(call.args[index])
        if ok:
            return value
    ok, value = _literal_keyword(call, keyword)
    return value if ok else fallback


def _collect_public_input_specs(tree_source: str) -> dict[str, dict[str, Any]]:
    """Collect literal specs from a top-level ``PUBLIC_INPUTS`` dict."""
    tree = ast.parse(tree_source)
    constants: dict[str, Any] = {}
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        ok, value = _literal_from_ast(stmt.value)
        if ok:
            constants[targets[0].id] = value

    def value_from_spec(call: ast.Call, index: int, keyword: str, fallback: Any = None) -> Any:
        node: ast.AST | None = call.args[index] if len(call.args) > index else None
        if node is None:
            for kw in call.keywords:
                if kw.arg == keyword:
                    node = kw.value
                    break
        if node is None:
            return fallback
        if isinstance(node, ast.Name) and node.id in constants:
            return constants[node.id]
        ok, value = _literal_from_ast(node)
        return value if ok else fallback

    specs: dict[str, dict[str, Any]] = {}
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == "PUBLIC_INPUTS" for target in targets):
            continue
        if not isinstance(stmt.value, ast.Dict):
            continue
        for key_node, value_node in zip(stmt.value.keys, stmt.value.values):
            if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
                continue
            if not _is_input_spec_call(value_node):
                continue
            name = key_node.value
            aliases = value_from_spec(value_node, 5, "aliases", ())
            if isinstance(aliases, list):
                aliases = tuple(aliases)
            specs[name] = {
                "node": str(value_from_spec(value_node, 0, "node", "")),
                "field": str(value_from_spec(value_node, 1, "field", "")),
                "default": value_from_spec(value_node, 2, "default"),
                "type": value_from_spec(value_node, 3, "type"),
                "required": bool(value_from_spec(value_node, 4, "required", False)),
                "aliases": aliases if isinstance(aliases, tuple) else (),
                "description": value_from_spec(value_node, 6, "description"),
                "media_semantics": value_from_spec(value_node, 7, "media_semantics"),
            }
    return specs


def _collect_declared_input_names(tree_source: str) -> list[str]:
    names: list[str] = []
    for name in _collect_register_input_names(tree_source):
        canonical = _canonical_input_name(name)
        if canonical not in names:
            names.append(canonical)
    for name in _collect_bind_input_names(tree_source):
        canonical = _canonical_input_name(name)
        if canonical not in names:
            names.append(canonical)
    for name in _collect_public_input_specs(tree_source):
        canonical = _canonical_input_name(name)
        if canonical not in names:
            names.append(canonical)
    for name in find_unbound_inputs(tree_source):
        canonical = _canonical_input_name(name)
        if canonical not in names:
            names.append(canonical)
    return names


def _collect_finalize_input_names(tree_source: str) -> set[str]:
    """Return PUBLIC_INPUTS keys that are passed to ``finalize(...)``."""
    public_specs = _collect_public_input_specs(tree_source)
    if not public_specs:
        return set()
    tree = ast.parse(tree_source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) not in {"finalize", "templates.finalize", "vibecomfy.templates.finalize"}:
            continue
        input_arg: ast.AST | None = node.args[1] if len(node.args) >= 2 else None
        if input_arg is None:
            for keyword in node.keywords:
                if keyword.arg == "inputs":
                    input_arg = keyword.value
                    break
        if isinstance(input_arg, ast.Name) and input_arg.id == "PUBLIC_INPUTS":
            names.update(public_specs)
        elif isinstance(input_arg, ast.Dict):
            for key in input_arg.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.add(key.value)
    return names


def _workflow_declared_input_defaults(tree_source: str, workflow: Any | None) -> dict[str, Any]:
    """Normalize source-declared public inputs to runtime defaults when available."""
    declared_names = _collect_declared_input_names(tree_source)
    source_unbound = find_unbound_inputs(tree_source)
    defaults: dict[str, Any] = {}
    workflow_inputs = getattr(workflow, "inputs", {}) if workflow is not None else {}
    for name in declared_names:
        registered = workflow_inputs.get(name) if isinstance(workflow_inputs, dict) else None
        if registered is None and name == "negative_prompt" and isinstance(workflow_inputs, dict):
            registered = workflow_inputs.get("negative")
        if registered is not None:
            defaults[name] = getattr(registered, "default", getattr(registered, "value", None))
        elif name in source_unbound:
            defaults[name] = source_unbound[name]
        elif name == "negative_prompt" and "negative" in source_unbound:
            defaults[name] = source_unbound["negative"]
    return defaults


def _public_inputs_wiring_check(tree_source: str, workflow: Any | None) -> dict[str, Any]:
    specs = _collect_public_input_specs(tree_source)
    if not specs:
        params_keys = _collect_params_keys(tree_source)
        params_refs = _count_params_refs_in_build(tree_source)
        unwired = sorted(k for k in params_keys if k not in params_refs)
        result: dict[str, Any] = {"pass": len(unwired) == 0, "mode": "PARAMS"}
        if unwired:
            result["unwired"] = unwired
        return result

    finalize_names = _collect_finalize_input_names(tree_source)
    workflow_inputs = getattr(workflow, "inputs", {}) if workflow is not None else {}
    missing_from_finalize = sorted(set(specs) - finalize_names)
    missing_from_workflow = sorted(set(specs) - set(workflow_inputs))
    target_mismatches: list[dict[str, Any]] = []
    default_mismatches: list[dict[str, Any]] = []
    for name, spec in specs.items():
        registered = workflow_inputs.get(name) if isinstance(workflow_inputs, dict) else None
        if registered is None:
            continue
        target = (str(getattr(registered, "node_id", "")), getattr(registered, "field", ""))
        expected = (spec["node"], spec["field"])
        if target != expected:
            target_mismatches.append({
                "name": name,
                "expected": f"{expected[0]}.{expected[1]}",
                "actual": f"{target[0]}.{target[1]}",
            })
        registered_default = getattr(registered, "default", None)
        if registered_default != spec["default"]:
            default_mismatches.append({
                "name": name,
                "expected": spec["default"],
                "actual": registered_default,
            })

    ok = not (missing_from_finalize or missing_from_workflow or target_mismatches or default_mismatches)
    result = {"pass": ok, "mode": "PUBLIC_INPUTS"}
    if missing_from_finalize:
        result["missing_from_finalize"] = missing_from_finalize
    if missing_from_workflow:
        result["missing_from_workflow"] = missing_from_workflow
    if target_mismatches:
        result["target_mismatches"] = target_mismatches
    if default_mismatches:
        result["default_mismatches"] = default_mismatches
    return result


def _allowed_removed_public_inputs(original_source: str, candidate_source: str) -> set[str]:
    """Return public inputs intentionally demoted during v2.3 cleanup."""
    return set()


def _candidate_alias_defaults(candidate_source: str, workflow: Any | None) -> dict[str, Any]:
    specs = _collect_public_input_specs(candidate_source)
    workflow_inputs = getattr(workflow, "inputs", {}) if workflow is not None else {}
    out: dict[str, Any] = {}
    for name, spec in specs.items():
        registered = workflow_inputs.get(name) if isinstance(workflow_inputs, dict) else None
        default = getattr(registered, "default", spec.get("default")) if registered is not None else spec.get("default")
        for alias in tuple(spec.get("aliases") or ()):
            out[str(alias)] = default
    return out


def _candidate_alias_targets(candidate_source: str) -> dict[str, str]:
    specs = _collect_public_input_specs(candidate_source)
    out: dict[str, str] = {}
    for name, spec in specs.items():
        target = f"{spec.get('node', '')}.{spec.get('field', '')}"
        out[name] = target
        for alias in tuple(spec.get("aliases") or ()):
            out[str(alias)] = target
    return out


def _is_v231_generated_source(source: str) -> bool:
    if "from vibecomfy.templates import" not in source or "node(wf," not in source or "def _node(" in source:
        return False
    import_line = source.split("from vibecomfy.templates import", 1)[1].splitlines()[0]
    imported = {part.strip(" ()") for part in import_line.split(",")}
    return "node" in imported


def _load_build_from_file(path: Path) -> Any:
    """Import `build` from a .py file without polluting sys.path."""
    import importlib.util

    module_name = f"_verify_{path.stem}_{abs(hash(str(path))) % (10**8)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot load spec from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise SystemExit(f"error: {path} has no `build()` function")
    return module.build


def _collect_params_keys(source: str) -> set[str]:
    """Collect string keys from a top-level ``PARAMS = {...}`` dict literal."""
    tree = ast.parse(source)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets if hasattr(node, "targets") else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "PARAMS":
                    if isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                keys.add(k.value)
    return keys


def _count_params_refs_in_build(source: str) -> dict[str, int]:
    """Collect PARAMS['key'] subscript references inside the build() function."""
    tree = ast.parse(source)
    refs: dict[str, int] = {}
    in_build = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build":
            in_build = True
        if not in_build:
            continue
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == "PARAMS":
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    key = node.slice.value
                    refs[key] = refs.get(key, 0) + 1
    return refs


def cmd_verify(original_path: Path, candidate_path: Path) -> int:
    """Run the four parity checks and output JSON to stdout."""
    checks: dict[str, Any] = {}
    orig_wf = None
    cand_wf = None

    # --- Check 1: API dict parity ---
    try:
        orig_build_fn = _load_build_from_file(original_path)
        cand_build_fn = _load_build_from_file(candidate_path)
        orig_wf = orig_build_fn()
        cand_wf = cand_build_fn()
        orig_api = orig_wf.compile("api")
        cand_api = cand_wf.compile("api")
        api_diffs = _deep_diff(orig_api, cand_api)
        checks["api_dict_parity"] = {
            "pass": len(api_diffs) == 0,
        }
        if api_diffs:
            checks["api_dict_parity"]["diff"] = api_diffs
    except Exception as exc:
        print(f"error: api_dict_parity check failed: {exc}", file=sys.stderr)
        checks["api_dict_parity"] = {"pass": False, "error": str(exc)}

    # --- Check 2: unbound_inputs parity ---
    try:
        orig_source = original_path.read_text()
        cand_source = candidate_path.read_text()
        allowed_removed = _allowed_removed_public_inputs(orig_source, cand_source)
        orig_unbound = _workflow_declared_input_defaults(orig_source, orig_wf)
        cand_unbound = _workflow_declared_input_defaults(cand_source, cand_wf)
        cand_alias_defaults = _candidate_alias_defaults(cand_source, cand_wf)
        cand_alias_targets = _candidate_alias_targets(cand_source)
        # Candidate is permitted to add keys when those keys are backed by a
        # ``register_input`` call (the v2.2 codemod enriches partial metadata so
        # the bidirectional invariant in ``_add_metadata_invariant`` passes).
        cand_register_names = set(_collect_declared_input_names(cand_source))
        unbound_ok = True
        unbound_diff: list[dict[str, Any]] = []
        for key, orig_val in orig_unbound.items():
            if key in allowed_removed:
                continue
            cand_val = cand_unbound.get(key, cand_alias_defaults.get(key))
            target_val = cand_alias_targets.get(key)
            if cand_val != orig_val and target_val != orig_val:
                unbound_ok = False
                unbound_diff.append({
                    "key": key,
                    "original": orig_val,
                    "candidate": cand_val,
                })
        # Flag keys in candidate that aren't in original AND aren't backed by a
        # register_input call (latter is legitimate enrichment).
        for key in cand_unbound:
            if key not in orig_unbound and key not in cand_register_names:
                unbound_ok = False
                unbound_diff.append({
                    "key": key,
                    "original": None,
                    "candidate": cand_unbound[key],
                })
        checks["unbound_inputs_parity"] = {"pass": unbound_ok}
        if unbound_diff:
            checks["unbound_inputs_parity"]["diff"] = unbound_diff
    except Exception as exc:
        print(f"error: unbound_inputs_parity check failed: {exc}", file=sys.stderr)
        checks["unbound_inputs_parity"] = {"pass": False, "error": str(exc)}

    # --- Check 3: register_input preservation ---
    try:
        orig_source = original_path.read_text()
        cand_source = candidate_path.read_text()
        allowed_removed = _allowed_removed_public_inputs(orig_source, cand_source)
        orig_names = _collect_declared_input_names(orig_source)
        cand_names = _collect_declared_input_names(cand_source)
        cand_set = set(cand_names)
        cand_aliases = set(_candidate_alias_defaults(cand_source, cand_wf))
        missing = [n for n in orig_names if n not in cand_set and n not in cand_aliases and n not in allowed_removed]
        checks["register_input_preservation"] = {
            "pass": len(missing) == 0,
        }
        if missing:
            checks["register_input_preservation"]["missing"] = missing
    except Exception as exc:
        print(f"error: register_input_preservation check failed: {exc}", file=sys.stderr)
        checks["register_input_preservation"] = {"pass": False, "error": str(exc)}

    # --- Check 4: params_wiring_check ---
    try:
        cand_source = candidate_path.read_text()
        checks["params_wiring_check"] = _public_inputs_wiring_check(cand_source, cand_wf)
    except Exception as exc:
        print(f"error: params_wiring_check failed: {exc}", file=sys.stderr)
        checks["params_wiring_check"] = {"pass": False, "error": str(exc)}

    # --- Compose result ---
    all_pass = all(
        c.get("pass", False) for c in checks.values()
    )
    result = {"status": "ok" if all_pass else "fail", "checks": checks}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if all_pass else 1


# --------------------------------------------------------------------------- #
# Static analyzer (--analyze)                                                 #
# --------------------------------------------------------------------------- #

def _build_workflow(file_path: Path):
    """Import a template's build() and return the VibeWorkflow."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_analyze_target", file_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: could not load {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "build"):
        raise SystemExit(f"error: {file_path} has no build() function")
    return mod.build()


def _detect_port_polarity_inversions(
    node_calls: list[NodeCall],
    schema: dict[str, dict[str, Any]],
    wf,
) -> list[dict[str, Any]]:
    """Flag nodes whose output port names are a permutation of input kwarg names,
    AND where at least 2 of the inverted output slots are consumed downstream."""
    # Pre-compute which output slots each node has consumers for
    consumed_slots: dict[str, set[int]] = defaultdict(set)
    for edge in wf.edges:
        try:
            slot = int(edge.from_output)
        except (ValueError, TypeError):
            continue
        consumed_slots[edge.from_node].add(slot)

    findings: list[dict[str, Any]] = []
    for nc in node_calls:
        entry = schema.get(nc.class_type)
        if not entry:
            continue
        output_names = entry.get("output_name") or []
        if len(output_names) < 2:
            continue
        # Input required keys from schema
        req = entry.get("input", {}).get("required", {})
        if not req:
            continue
        input_keys = list(req.keys())
        # Kwarg names from the _node call
        kwarg_names = [k for k, _ in nc.kwargs]
        # Find the intersection of kwarg names and input keys that also appear in output_names
        shared = [k for k in kwarg_names if k in input_keys and k in output_names]
        if len(shared) < 2:
            continue
        # Check if output_names (filtered to shared) is a permutation of shared
        shared_set = set(shared)
        output_shared = [n for n in output_names if n in shared_set]
        if sorted(shared) != sorted(output_shared) or shared == output_shared:
            continue

        # Require at least 1 of the inverted output ports to be consumed
        # (this filters out nodes like ImageResizeKJv2 where only the IMAGE
        # output 0 is consumed but the inverted width/height outputs are not).
        inverted_indices = set()
        for i, name in enumerate(output_names):
            if name in shared_set:
                inverted_indices.add(i)
        consumed = consumed_slots.get(nc.node_id, set())
        if len(inverted_indices & consumed) < 1:
            continue

        findings.append({
            "node_id": nc.node_id,
            "class_type": nc.class_type,
            "input_arg_order": shared,
            "output_port_order": output_shared,
            "evidence": f"node {nc.node_id} takes ({', '.join(shared)}) but its outputs are labelled ({', '.join(output_shared)})",
            "suggested_comment": (
                f"WARNING: outputs are ({', '.join(output_shared)}) "
                f"— order is reversed vs the ({', '.join(shared)}) input args."
            ),
        })
    return findings


def _detect_chain_bypasses(wf) -> list[dict[str, Any]]:
    """Detect model-patch chain bypasses.

    A chain is a sequence of nodes A → B → C → ... where each node's "model"
    (or similar) input is wired to the prior node's output 0.  A bypass
    occurs when a downstream consumer connects to a non-tail node in a chain
    of length ≥ 3.

    Chain membership is restricted to model-producing nodes (UNETLoader and
    MODEL PATCH STACK classes) so that consumers like CFGGuider don't get
    absorbed into the chain.
    """
    findings: list[dict[str, Any]] = []

    # Classes that can be part of a model-patch chain
    _CHAIN_CLASSES: set[str] = {"UNETLoader"} | {
        c for c, s in SECTION_OF_CLASS.items() if s == "MODEL PATCH STACK"
    }

    # Build adjacency only for chain-eligible nodes
    model_successors: dict[str, list[str]] = defaultdict(list)
    model_predecessors: dict[str, str | None] = {}
    for edge in wf.edges:
        to_input_lower = edge.to_input.lower()
        if edge.from_output in ("0", 0) and ("model" in to_input_lower or to_input_lower == "unet"):
            from_node = edge.from_node
            to_node = edge.to_node
            # Both nodes must be eligible for the chain
            if (wf.nodes[from_node].class_type in _CHAIN_CLASSES
                    and wf.nodes[to_node].class_type in _CHAIN_CLASSES):
                model_successors[from_node].append(to_node)
                if to_node not in model_predecessors:
                    model_predecessors[to_node] = from_node

    # Find chains by walking from nodes that have no model predecessor (chain heads)
    visited: set[str] = set()
    chains: list[list[str]] = []

    for node_id in wf.nodes:
        if node_id in visited:
            continue
        if wf.nodes[node_id].class_type not in _CHAIN_CLASSES:
            continue
        # Walk backward to find chain head
        current = node_id
        while model_predecessors.get(current) and model_predecessors[current] not in visited:
            current = model_predecessors[current]
        if current in visited:
            continue
        # Walk forward building the chain
        chain: list[str] = [current]
        visited.add(current)
        while model_successors.get(current):
            nxt = model_successors[current][0]
            if nxt in visited:
                break
            chain.append(nxt)
            visited.add(nxt)
            current = nxt
        if len(chain) >= 3:
            chains.append(chain)

    # For each chain, find nodes that take "model" from a non-tail chain member
    tail_set = {chain[-1] for chain in chains}
    chain_member_to_tail: dict[str, str] = {}
    for chain in chains:
        for member in chain[:-1]:
            chain_member_to_tail[member] = chain[-1]

    # Pre-compute downstream reachability: for each node, all nodes reachable
    # by walking forward along edges (output 0).
    downstream_cache: dict[str, set[str]] = {}

    def _downstream_of(start_id: str) -> set[str]:
        if start_id in downstream_cache:
            return downstream_cache[start_id]
        ds: set[str] = set()
        front = {start_id}
        for _ in range(50):  # safety limit
            next_front: set[str] = set()
            for edge in wf.edges:
                if edge.from_node in front:
                    if edge.to_node not in ds:
                        ds.add(edge.to_node)
                        next_front.add(edge.to_node)
            if not next_front:
                break
            front = next_front
        downstream_cache[start_id] = ds
        return ds

    for edge in wf.edges:
        to_input_lower = edge.to_input.lower()
        if edge.from_output in ("0", 0) and ("model" in to_input_lower or to_input_lower == "unet"):
            from_node = edge.from_node
            to_node = edge.to_node
            if from_node in chain_member_to_tail and to_node not in tail_set:
                chain = next((c for c in chains if from_node in c), None)
                if chain is None:
                    continue
                if to_node in chain:
                    continue
                skipped_ids = chain[chain.index(from_node) + 1:]
                skipped_classes = [wf.nodes[nid].class_type for nid in skipped_ids]

                # Determine INTENTIONAL vs POSSIBLE:
                # If the bypassing node's downstream consumers are completely
                # separate from the chain tail's downstream, it's INTENTIONAL.
                # Otherwise POSSIBLE.
                chain_tail = chain[-1]
                bypass_ds = _downstream_of(to_node)
                tail_ds = _downstream_of(chain_tail)

                bypass_only = bypass_ds - tail_ds - {chain_tail}
                if bypass_only:
                    qualifier = "INTENTIONAL CHAIN BYPASS"
                    note = " consumed elsewhere (likely a separate sampler)."
                else:
                    qualifier = "POSSIBLE CHAIN BYPASS"
                    note = ""

                findings.append({
                    "bypassing_node_id": to_node,
                    "bypassing_class": wf.nodes[to_node].class_type,
                    "chain_head_id": chain[0],
                    "chain_head_class": wf.nodes[chain[0]].class_type,
                    "skipped_node_ids": skipped_ids,
                    "skipped_classes": skipped_classes,
                    "evidence": (
                        f"node {to_node} takes model={from_node}.out(0) but a "
                        f"{len(skipped_ids)}-node patch chain exists downstream of {from_node}"
                    ),
                    "suggested_comment": (
                        f"{qualifier}: takes {wf.nodes[from_node].class_type} directly; "
                        f"does NOT inherit the {'/'.join(skipped_classes)} patches."
                        f"{note}"
                    ),
                })

    return findings


def _detect_unwired_primitives(wf) -> list[dict[str, Any]]:
    """Flag Primitive* / INTConstant nodes with zero outgoing edges."""
    primitives = {"PrimitiveString", "PrimitiveFloat", "PrimitiveInt", "PrimitiveBool", "INTConstant"}
    findings: list[dict[str, Any]] = []
    for node_id, node in wf.nodes.items():
        if node.class_type not in primitives:
            continue
        has_out = any(e.from_node == node_id for e in wf.edges)
        if not has_out:
            # Extract literal value
            val = node.inputs.get("value") or node.inputs.get("widget_0")
            findings.append({
                "node_id": node_id,
                "class_type": node.class_type,
                "literal_value": val,
                "evidence": f"node {node_id} has zero outgoing edges",
                "suggested_comment": "UNUSED: no downstream consumers — this is a label only, runtime no-op.",
            })
    return findings


# Classes to exclude from ancestor tracking — shared constants cause
# spurious intersections across unrelated branches.
_ANCESTOR_EXCLUDE: set[str] = {
    "PrimitiveString", "PrimitiveFloat", "PrimitiveInt", "PrimitiveBool", "INTConstant",
}

# Preprocessor class → human-readable mode label (for branch-selector comments).
_PREPROCESSOR_MODE_LABEL: dict[str, str] = {
    "DWPreprocessor": "pose",
    "CannyEdgePreprocessor": "canny",
    "DepthAnything_V2": "depth",
    "ImageResizeKJv2": "raw",
    "LTXVPreprocess": "default",
}

_HEAD_MODE_LABEL = "raw"  # label used when ImageResizeKJv2 is the head ancestor


def _ancestor_set(node_id: str, wf, max_depth: int = 3) -> set[str]:
    """Return the set of node_ids reachable by walking backward up to max_depth edges,
    excluding trivial primitive/constant nodes."""
    ancestors: set[str] = {node_id}
    frontier = {node_id}
    for _ in range(max_depth):
        next_frontier: set[str] = set()
        for edge in wf.edges:
            if edge.to_node in frontier:
                src = edge.from_node
                if src not in ancestors:
                    node = wf.nodes.get(src)
                    if node and node.class_type in _ANCESTOR_EXCLUDE:
                        continue
                    ancestors.add(src)
                    next_frontier.add(src)
        frontier = next_frontier
        if not frontier:
            break
    return ancestors


def _derive_mode_label(node_id: str, wf) -> str | None:
    """Walk upstream ancestors of *node_id* and return a mode label based on
    known preprocessor class types.

    Priority: first preprocessor match found by walking upstream edges
    (depth-first up to 5 hops). Returns ``None`` if no known preprocessor
    class is found.
    """
    frontier = {node_id}
    visited: set[str] = set()
    for _ in range(5):
        next_frontier: set[str] = set()
        for edge in wf.edges:
            if edge.to_node in frontier:
                src = edge.from_node
                if src in visited:
                    continue
                visited.add(src)
                node = wf.nodes.get(src)
                if node is None:
                    continue
                if node.class_type in _PREPROCESSOR_MODE_LABEL:
                    return _PREPROCESSOR_MODE_LABEL[node.class_type]
                if node.class_type in _ANCESTOR_EXCLUDE:
                    continue
                next_frontier.add(src)
        frontier = next_frontier
        if not frontier:
            break
    return None


def _detect_branch_selector_groups(wf) -> list[dict[str, Any]]:
    """Detect branch-selector groups: N≥2 nodes of the same class produce
    outputs that converge on one sink input, but only one is wired.

    Only flags when the *alternative* candidates are dead-end nodes (zero
    outgoing edges), which is the signal that they exist solely as
    interchangeable branches for that input.

    Additionally requires structural symmetry: the active branch and each
    alternative must share a common upstream ancestor within depth ≤ 3 edges."""
    findings: list[dict[str, Any]] = []

    # Build: class_type -> list of node_ids
    nodes_by_class: dict[str, list[str]] = defaultdict(list)
    for node_id, node in wf.nodes.items():
        nodes_by_class[node.class_type].append(node_id)

    # Which nodes have outgoing edges
    has_outgoing: dict[str, bool] = {}
    for edge in wf.edges:
        has_outgoing[edge.from_node] = True

    # Pre-compute ancestor sets (depth ≤ 3) for all nodes
    ancestor_cache: dict[str, set[str]] = {}

    def _get_ancestors(nid: str) -> set[str]:
        if nid not in ancestor_cache:
            ancestor_cache[nid] = _ancestor_set(nid, wf, 3)
        return ancestor_cache[nid]

    # For each edge, look at the source class and find dead-end alternatives
    for edge in wf.edges:
        from_node = edge.from_node
        to_node = edge.to_node
        to_input = edge.to_input

        from_class = wf.nodes[from_node].class_type
        # Skip trivial classes
        if from_class in {"PrimitiveString", "PrimitiveFloat", "PrimitiveInt", "PrimitiveBool", "INTConstant"}:
            continue

        candidates = nodes_by_class.get(from_class, [])
        if len(candidates) < 2:
            continue

        # Find which of the candidates are actually wired to this same (to_node, to_input)
        wired_candidates: list[str] = []
        for e2 in wf.edges:
            if e2.to_node == to_node and e2.to_input == to_input and e2.from_node in candidates:
                wired_candidates.append(e2.from_node)

        # Only flag if exactly one is wired AND the alternatives are dead-end nodes
        if len(wired_candidates) != 1:
            continue

        active = wired_candidates[0]
        alt_ids = [n for n in candidates
                   if n != active
                   and n != to_node  # exclude the sink itself
                   and not has_outgoing.get(n, False)]
        if len(alt_ids) < 1:
            continue

        # Structural symmetry filter: active and each alt must share a common
        # upstream ancestor within depth ≤ 3, AND the alt must not be
        # downstream of the active (active must not be an ancestor of alt).
        active_ancestors = _get_ancestors(active)
        filtered_alts: list[str] = []
        for alt in alt_ids:
            alt_ancestors = _get_ancestors(alt)
            # Intersection required (common ancestor)
            if not (active_ancestors & alt_ancestors):
                continue
            # Alt must not be downstream of active
            if active in alt_ancestors:
                continue
            filtered_alts.append(alt)

        if len(filtered_alts) < 1:
            continue

        # Derive mode labels for active and alternative branches
        active_mode = _derive_mode_label(active, wf)
        alt_modes: dict[str, str | None] = {
            alt: _derive_mode_label(alt, wf) for alt in filtered_alts
        }

        # Build mode-labeled alternative strings
        alt_list: list[str] = []
        for alt in sorted(filtered_alts):
            mode = alt_modes.get(alt)
            if mode:
                alt_list.append(f"{alt} ({mode})")
            else:
                alt_list.append(alt)

        active_str = f"{active} ({active_mode})" if active_mode else active

        findings.append({
            "sink_node_id": to_node,
            "sink_class": wf.nodes[to_node].class_type,
            "sink_input": to_input,
            "active_branch_node_id": active,
            "alternative_branch_node_ids": sorted(filtered_alts),
            "evidence": (
                f"{1 + len(filtered_alts)} {from_class} outputs converge on sink "
                f"{to_node}.{to_input}; only one is wired"
            ),
            "suggested_comment": (
                f"BRANCH SELECTION: '{to_input}=' picks which control branch is active. "
                f"Currently wired to node {active_str}. "
                f"Alternatives: {', '.join(alt_list)}."
            ),
        })

    # Deduplicate by (sink_node_id, sink_input)
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for f in findings:
        key = (f["sink_node_id"], f["sink_input"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _detect_magic_constant_twins(wf) -> list[dict[str, Any]]:
    """Detect magic-constant twins: two literal nodes with matching values
    feeding parallel (symmetrically-named) slots on the same sink."""
    primitives = {"PrimitiveFloat", "PrimitiveInt", "INTConstant"}
    findings: list[dict[str, Any]] = []

    # Group primitive nodes by literal value
    by_value: dict[Any, list[str]] = defaultdict(list)
    for node_id, node in wf.nodes.items():
        if node.class_type not in primitives:
            continue
        val = node.inputs.get("value") or node.inputs.get("widget_0")
        if val is not None:
            by_value[val].append(node_id)

    import re
    _suffix_re = re.compile(r"^(.+)_(\d+)$")

    for val, node_ids in by_value.items():
        if len(node_ids) < 2:
            continue
        # Find which sinks these feed into
        sink_slots: dict[str, list[tuple[str, str]]] = defaultdict(list)  # sink_node_id -> [(from_node_id, to_input), ...]
        for nid in node_ids:
            for e in wf.edges:
                if e.from_node == nid:
                    sink_slots[e.to_node].append((nid, e.to_input))

        # Check for parallel slots on the same sink
        for sink_id, slots in sink_slots.items():
            if len(slots) < 2:
                continue
            # Check if slot names are symmetric (share prefix, differ by numeric suffix)
            slot_names = [s[1] for s in slots]
            # Extract base names by stripping trailing _\d+ or by detecting common prefix
            bases: dict[str, list[tuple[str, str]]] = defaultdict(list)
            for (from_id, slot_name) in slots:
                m = _suffix_re.match(slot_name)
                if m:
                    bases[m.group(1)].append((from_id, slot_name))
                else:
                    # Try to find common prefix among slot_names
                    bases["__ungrouped__"].append((from_id, slot_name))

            for base, grouped_slots in bases.items():
                if base == "__ungrouped__" or len(grouped_slots) < 2:
                    continue
                twin_ids = [s[0] for s in grouped_slots]
                # Build downstream sink info
                sinks = [{"node": sink_id, "field": s[1]} for s in grouped_slots]
                findings.append({
                    "node_ids": twin_ids,
                    "classes": [wf.nodes[nid].class_type for nid in twin_ids],
                    "value": val,
                    "downstream_sinks": sinks,
                    "evidence": (
                        f"two {wf.nodes[twin_ids[0]].class_type} nodes with literal {val!r} "
                        f"feed parallel inputs {' / '.join(s[1] for s in grouped_slots)} on the same sink"
                    ),
                    "suggested_comment": (
                        f"COUPLED: matches partner literal by convention. "
                        f"Hoist to PARAMS as distinct named constants."
                    ),
                })

    return findings


def run_analyzer(file_path: Path, source_override: str | None = None) -> dict[str, Any]:
    """Run all five analyzer rules and return the findings dict."""
    source = source_override if source_override is not None else file_path.read_text()
    parsed = parse_template(source)

    # Build lookup: node_id -> NodeCall
    nc_by_id = {nc.node_id: nc for nc in parsed.node_calls}

    # Load schema for output port info
    schema = load_object_info_schema()

    # Build workflow for edge info
    wf = _build_workflow(file_path)

    findings: dict[str, list[dict[str, Any]]] = {
        "port_polarity_inversions": _detect_port_polarity_inversions(parsed.node_calls, schema, wf),
        "chain_bypasses": _detect_chain_bypasses(wf),
        "unwired_primitives": _detect_unwired_primitives(wf),
        "branch_selector_groups": _detect_branch_selector_groups(wf),
        "magic_constant_twins": _detect_magic_constant_twins(wf),
    }

    return {
        "file": str(file_path),
        "findings": findings,
    }


# --------------------------------------------------------------------------- #
# Phase 4: --mode annotate / --mode restructure                               #
# --------------------------------------------------------------------------- #

# Classes whose inputs are file-path placeholders (stay inline, don't hoist)
_PLACEHOLDER_CLASSES: set[str] = {"LoadImage", "LoadVideo", "LoadAudio"}
_PLACEHOLDER_FIELDS: set[str] = {"image", "video", "file", "audio"}


def cmd_codemod_v2(
    src_path: Path,
    out_path: Path | None,
    mode: str,
    dry_run: bool,
    diff: bool,
) -> int:
    """Execute Phase 4 codemod v2 (annotate or restructure)."""
    if not src_path.is_file():
        print(f"error: {src_path} not found", file=sys.stderr)
        return 2

    source = _normalize_at_helper_source(src_path.read_text())
    if mode == "restructure" and _is_v231_generated_source(source):
        # Even for already-v2.3.1 templates, refresh the source provenance comment.
        updated_source = _inject_source_provenance(source, src_path)
        updated_source = _remove_top_level_assignments(updated_source, {"READY_REQUIREMENTS"})
        return _emit_v2(source, updated_source, src_path, out_path, dry_run, diff, "_v231.py", mode)

    # Parse the template
    parsed = parse_template(source)
    node_calls_by_id = {nc.node_id: nc for nc in parsed.node_calls}
    unbound = find_unbound_inputs(source)

    # Run analyzer for findings
    findings = run_analyzer(src_path, source)

    # Load output schema for comments
    schema = load_object_info_schema()

    # --- Produce annotate-mode output ---
    annot_source = _produce_annotate_v2(source, parsed, findings, schema, node_calls_by_id)

    if mode == "annotate":
        return _emit_v2(source, annot_source, src_path, out_path, dry_run, diff,
                        "_v2_annotate.py", mode)

    # --- Produce restructure-mode output (layered on annotate) ---
    if mode == "restructure":
        restructure_source = _produce_restructure_v2(
            annot_source, parsed, findings, schema,
            node_calls_by_id, unbound,
        )
        return _emit_v2(source, restructure_source, src_path, out_path, dry_run, diff,
                        "_v2_restructure.py", mode)

    return 1


def _inject_version_pins_into_metadata(source: str) -> str:
    """Inject vibecomfy_version and comfy_core kwargs into ReadyMetadata.build()
    if they are not already present.

    Operates on the source text of a v2.3.1-form template.  Uses AST to locate
    the ``ReadyMetadata.build(…)`` call and inserts the two traceability kwargs
    before the closing parenthesis.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    # Locate the ReadyMetadata.build(...) call
    existing_kwargs: set[str] = set()
    build_end_lineno: int | None = None
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(t, ast.Name) and t.id == "READY_METADATA" for t in targets):
            continue
        if (isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "build"):
            for kw in stmt.value.keywords:
                if kw.arg:
                    existing_kwargs.add(kw.arg)
            build_end_lineno = stmt.value.end_lineno
            break

    if build_end_lineno is None:
        return source

    # Decide which pins are missing
    pins: list[str] = []
    if "vibecomfy_version" not in existing_kwargs:
        vibecomfy_version = _get_vibecomfy_version()
        pins.append(f"    vibecomfy_version={vibecomfy_version!r},")
    if "comfy_core" not in existing_kwargs:
        comfy_core = _get_comfy_core_info()
        pins.append(f"    comfy_core={comfy_core!r},")

    if not pins:
        return source

    # Find the closing ) of the build() call (on or after build_end_lineno)
    lines = source.splitlines(keepends=True)
    close_idx: int | None = None
    for i in range(build_end_lineno - 1, len(lines)):
        if ')' in lines[i]:
            close_idx = i
            break

    if close_idx is None:
        return source

    close_line = lines[close_idx]
    paren_pos = close_line.rfind(')')
    if paren_pos == -1:
        return source

    insertion = "\n".join(pins) + "\n"
    lines[close_idx] = close_line[:paren_pos] + insertion + close_line[paren_pos:]

    return "".join(lines)


def _inject_source_provenance(source: str, _src_path: Path) -> str:
    """Inject or refresh the ``# ported from <path> (sha256: <sha>)`` comment.

    Finds the narrative marker line, extracts ``source_workflow`` from the
    template metadata, and inserts a provenance comment after the marker.
    Existing provenance comments are replaced.

    Also refreshes the module docstring with structured content (T11)
    and injects missing version pins into READY_METADATA (T12).
    """
    marker_pattern = re.compile(r"^(# vibecomfy: narrative .*)$", re.MULTILINE)
    plain_marker_pattern = re.compile(r"^# vibecomfy: narrative\n", re.MULTILINE)
    marker_match = marker_pattern.search(source)

    # Consolidate plain marker at file top with enriched marker.
    # If both exist, replace the plain one and remove the duplicate enriched one.
    plain_match = plain_marker_pattern.search(source)
    if plain_match and marker_match:
        marker_text = _marker_line()
        # Replace plain marker with enriched one at file top
        source = source[:plain_match.start()] + marker_text + "\n" + source[plain_match.end():]
        # Remove the duplicate enriched marker (which shifted by length change)
        old_len = len(source)
        source = source.replace(marker_text + "\n", "", 1)  # Remove first occurrence (the duplicate)
        if len(source) == old_len:
            # Try without trailing newline
            source = source.replace(marker_text, "", 1)
        # Re-search for the marker at the top (now enriched)
        marker_match = marker_pattern.search(source)
    elif not marker_match:
        if not plain_match:
            return source
        marker_text = _marker_line()
        source = source[:plain_match.start()] + marker_text + "\n" + source[plain_match.end():]
        marker_match = marker_pattern.search(source)
        if not marker_match:
            return source
    marker_end = marker_match.end()

    # Extract source_workflow from the source using a simple regex
    sw_match = re.search(r"['\"]source_workflow['\"]\s*:\s*['\"]([^'\"]+)['\"]", source)
    if not sw_match:
        return source
    source_workflow = sw_match.group(1)

    source_path = REPO_ROOT / source_workflow
    sha = ""
    try:
        sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except Exception:
        # source_workflow is not a valid file path (e.g. manual composition).
        # Fall back to hashing the template Python file itself, excluding any
        # existing provenance line so the hash is stable across re-generations.
        try:
            raw = _src_path.read_bytes()
            # Strip any existing provenance comment so the hash is idempotent.
            existing_prov = re.compile(rb"^# ported from .*\n?", re.MULTILINE)
            raw = existing_prov.sub(b"", raw)
            sha = hashlib.sha256(raw).hexdigest()
        except Exception:
            pass

    if sha:
        provenance_line = f"# ported from {source_workflow} (sha256: {sha})"
    else:
        provenance_line = f"# ported from {source_workflow}"
    # Remove any existing provenance line (old or malformed) plus its trailing newline
    existing_pattern = re.compile(r"^# ported from .*\n?", re.MULTILINE)
    source = existing_pattern.sub("", source)
    # Insert after the marker line (including its trailing newline)
    insert_at = marker_end
    if insert_at < len(source) and source[insert_at] == "\n":
        insert_at += 1  # skip past the newline after the marker
    source = source[:insert_at] + provenance_line + "\n" + source[insert_at:]

    # Refresh structured docstring
    source = _refresh_docstring_from_source(source)

    # Inject version pins into READY_METADATA (T12)
    source = _inject_version_pins_into_metadata(source)

    # Clean up custom_nodes: re-derive pack names and remove bare class names
    source = _clean_custom_nodes_in_source(source)

    return source


def _clean_custom_nodes_in_source(source: str) -> str:
    """Re-derive custom-node pack names and clean up the requirements dict.

    If the template's READY_METADATA ``requirements`` contains bare class names
    that couldn't be mapped to any known pack, remove them.  If known packs are
    derivable from the source, replace the custom_nodes list with just those
    pack names.  If no packs are derivable and custom_nodes was non-empty,
    remove the requirements block entirely.
    """
    derived_packs = _derive_custom_node_packs_from_source(source)
    # Find the requirements={'custom_nodes': [...]} text block, including an
    # optional preceding comma so removal doesn't leave a dangling comma.
    req_pattern = re.compile(
        r"(,?\s*requirements=\{\s*\n?\s*)"
        r"('custom_nodes':\s*\[[^\]]*\])"
        r"(\s*,?\s*\n?\s*\})",
        re.DOTALL,
    )
    match = req_pattern.search(source)
    if not match and not derived_packs:
        return source
    if not derived_packs:
        # Remove the requirements block entirely — no known packs.
        # The regex captures any preceding comma so we don't leave a dangling one.
        if match:
            source = req_pattern.sub("", source)
        return source
    # Replace custom_nodes with derived pack names
    new_custom_nodes = f"'custom_nodes': {derived_packs!r}"
    if match:
        source = source[:match.start(2)] + new_custom_nodes + source[match.end(2):]
    return source


def _refresh_docstring_from_source(source: str) -> str:
    """Extract metadata from a v2.3.1 template and refresh its module docstring."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    existing_docstring = ast.get_docstring(tree)

    # Extract metadata from ReadyMetadata.build(...)
    metadata: dict[str, Any] = {}
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(t, ast.Name) and t.id == "READY_METADATA" for t in targets):
            continue
        if (isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "build"):
            for kw in stmt.value.keywords:
                if kw.arg in {"inputs", "models"}:
                    continue
                ok_val, val = _literal_from_ast(kw.value)
                if ok_val:
                    metadata[kw.arg or ""] = val
        break

    # Extract model keys from MODELS dict
    model_keys: list[str] = []
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(t, ast.Name) and t.id == "MODELS" for t in targets):
            continue
        if isinstance(stmt.value, ast.Dict):
            for key_node in stmt.value.keys:
                ok_k, k = _literal_from_ast(key_node)
                if ok_k and isinstance(k, str):
                    model_keys.append(k)
        break

    # Extract specs from PUBLIC_INPUTS dict (InputSpec calls)
    specs: dict[str, dict[str, Any]] = {}
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(t, ast.Name) and t.id == "PUBLIC_INPUTS" for t in targets):
            continue
        if isinstance(stmt.value, ast.Dict):
            for key_node, value_node in zip(stmt.value.keys, stmt.value.values):
                ok_k, k = _literal_from_ast(key_node)
                if not (ok_k and isinstance(k, str)):
                    continue
                if isinstance(value_node, ast.Call) and _call_name(value_node.func) == "InputSpec":
                    spec: dict[str, Any] = {}
                    for kw in value_node.keywords:
                        ok_v, v = _literal_from_ast(kw.value)
                        if ok_v:
                            spec[kw.arg or ""] = v
                    specs[k] = spec
        break

    # Extract output info from finalize() call
    output_type: str | None = None
    output_node_id: str = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) in {"finalize", "templates.finalize", "vibecomfy.templates.finalize"}:
            output_node_id = str(_kw_literal(node, "output_node", ""))
            output_type = _kw_literal(node, "output_type", None)
            break

    # Extract source_workflow from nested provenance if not at top level
    if "source_workflow" not in metadata and isinstance(metadata.get("provenance"), dict):
        sw = metadata["provenance"].get("source_workflow")
        if sw:
            metadata["source_workflow"] = sw

    # Extract custom node packs from requirements
    custom_node_packs = metadata.get("requirements", {}).get("custom_nodes", [])
    if isinstance(custom_node_packs, list):
        custom_node_packs = [str(p) for p in custom_node_packs]
    else:
        custom_node_packs = []

    new_doc = _generate_structured_docstring(
        metadata=metadata,
        specs=specs,
        output_type=output_type,
        output_node_id=output_node_id,
        custom_node_packs=custom_node_packs,
        existing_docstring=existing_docstring,
        model_keys=model_keys if model_keys else None,
    )
    return _replace_module_docstring(source, new_doc)


def _emit_v2(
    original_source: str,
    new_source: str,
    src_path: Path,
    out_path: Path | None,
    dry_run: bool,
    diff: bool,
    default_suffix: str,
    mode: str,
) -> int:
    """Emit v2 output, checking syntax and handling diff/dry-run."""
    parse_ok = True
    try:
        ast.parse(new_source)
    except SyntaxError as exc:
        parse_ok = False
        print(f"warning: emitted file has syntax error: {exc}", file=sys.stderr)

    if diff:
        diff_lines = difflib.unified_diff(
            original_source.splitlines(keepends=True),
            new_source.splitlines(keepends=True),
            fromfile=str(src_path),
            tofile=f"<v2_{mode}>",
        )
        sys.stdout.writelines(diff_lines)

    if dry_run:
        sys.stdout.write(new_source)
        return 0 if parse_ok else 1

    dest: Path = out_path or src_path.with_name(src_path.stem + default_suffix)
    dest.write_text(new_source)
    print(f"wrote {dest} ({len(new_source.splitlines())} lines, parse_ok={parse_ok})")
    return 0 if parse_ok else 1


def _produce_annotate_v2(
    source: str,
    parsed: ParseResult,
    findings: dict[str, Any],
    schema: dict[str, dict[str, Any]],
    node_calls_by_id: dict[str, NodeCall],
) -> str:
    """Produce annotate-mode: original + analyzer comments + output comments."""
    lines = source.splitlines(keepends=True)

    # Build a map: line_number -> [comments to insert on next line]
    line_comments: dict[int, list[str]] = defaultdict(list)

    # Colocate analyzer finding comments at the right call sites
    for category, items in findings.get("findings", {}).items():
        for item in items:
            comment = item.get("suggested_comment", "")
            if not comment:
                continue

            # Determine which node_id(s) to anchor on.
            # Support both singular (node_id, bypassing_node_id, sink_node_id)
            # and plural (node_ids) anchors.
            anchor_ids: list[str] = []
            if "node_ids" in item and isinstance(item["node_ids"], list):
                anchor_ids = [str(nid) for nid in item["node_ids"]]
            elif "node_id" in item:
                anchor_ids = [str(item["node_id"])]
            elif "bypassing_node_id" in item:
                anchor_ids = [str(item["bypassing_node_id"])]
            elif "sink_node_id" in item:
                anchor_ids = [str(item["sink_node_id"])]

            if not anchor_ids:
                continue

            # For each anchor, inject the comment (preserved verbatim).
            # magic_constant_twins: per-anchor comments reference the partner id.
            for anchor_id in anchor_ids:
                actual_comment = comment
                if category == "magic_constant_twins" and len(anchor_ids) > 1:
                    partner_id = next((nid for nid in anchor_ids if nid != anchor_id), None)
                    if partner_id:
                        actual_comment = (
                            f"COUPLED: matches partner literal at node {partner_id} "
                            f"by convention. Hoist to PARAMS as distinct named constants."
                        )

                lineno = _find_node_call_line(source, anchor_id)
                if lineno is not None:
                    line_comments.setdefault(lineno, []).append(f"# {actual_comment}")

    # Add output comments for nodes meeting conditions
    unresolved_count = 0
    for nc in parsed.node_calls:
        entry = schema.get(nc.class_type)
        if not entry:
            unresolved_count += 1
            continue
        output_types = entry.get("output") or []
        output_names = entry.get("output_name") or []
        if not output_types:
            unresolved_count += 1
            continue

        # Only add comment if >= 2 outputs OR slot name differs from type
        needs_comment = len(output_types) >= 2
        if not needs_comment and output_names:
            for i in range(min(len(output_types), len(output_names))):
                t = output_types[i]
                n = output_names[i]
                if n and n.upper() != t.upper():
                    needs_comment = True
                    break

        if not needs_comment:
            continue

        # Build comment parts
        parts: list[str] = []
        for i, t in enumerate(output_types):
            name = output_names[i] if i < len(output_names) else ""
            if name and name.upper() != t.upper():
                parts.append(f"{i}={t}({name})")
            else:
                parts.append(f"{i}={t}")
        comment = "# outputs: " + ", ".join(parts)

        lineno = _find_node_call_line(source, nc.node_id)
        if lineno is not None:
            line_comments.setdefault(lineno, []).append(comment)

    # Build output lines with injected comments
    out_lines: list[str] = []
    for i, line in enumerate(lines, start=1):
        out_lines.append(line.rstrip("\n"))
        if i in line_comments:
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]
            for c in line_comments[i]:
                out_lines.append(f"{indent}{c}")

    result = "\n".join(out_lines) + "\n"

    # Add summary line at top of build() if needed
    if unresolved_count > 0:
        result = _insert_build_summary(result, unresolved_count)

    return result


def _find_node_call_line(source: str, node_id: str) -> int | None:
    """Find the line number of an _node(wf, class, id, ...) call with given id."""
    tree = ast.parse(source)
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        id_arg = stmt.value.args[2]
        if isinstance(id_arg, ast.Constant) and str(id_arg.value) == node_id:
            return stmt.lineno
    return None


def _insert_build_summary(source: str, unresolved_count: int) -> str:
    """Insert summary line after VibeWorkflow() constructor in build()."""
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    found_def = False
    paren_depth = 0
    wf_init_end = -1

    for i, line in enumerate(lines):
        if "def build()" in line:
            found_def = True
            out.append(line)
            continue
        if found_def and paren_depth == 0 and "VibeWorkflow(" in line:
            paren_depth = 1
            out.append(line)
            continue
        if found_def and paren_depth > 0:
            paren_depth += line.count("(") - line.count(")")
            out.append(line)
            if paren_depth <= 0:
                wf_init_end = i
                found_def = False
                paren_depth = 0
            continue
        out.append(line)

    return "".join(out)


# ---------------------------------------------------------------------------
# v2.2 bind_input → wf.register_input conversion (Item 9)
# ---------------------------------------------------------------------------


def _convert_bind_input_calls(source: str) -> str:
    """Convert ``bind_input(wf, name, node_id, field, ...)`` → ``wf.register_input(...)``.

    Reconstructs *value* from the corresponding ``_node()`` call's kwarg for *field*,
    and preserves all descriptor kwargs (type, required, range, aliases,
    media_semantics, media).  The explicit *default* is passed through when present;
    otherwise both *value* and *default* use the reconstructed node value.
    """
    tree = ast.parse(source)

    # --- Build lookup: node_id → _node() call AST node ---
    node_calls: dict[str, ast.Call] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "_node":
            pass
        elif isinstance(func, ast.Attribute) and func.attr == "_node":
            pass
        else:
            continue
        # Third positional arg is node_id (string literal); second is class_type
        if len(node.args) >= 3:
            arg = node.args[2]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                node_calls[arg.value] = node

    # --- Find and collect bind_input calls ---
    bind_calls: list[tuple[ast.Call, str, str, str, Any, list[ast.keyword]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "bind_input"):
            continue
        # bind_input(wf, name, node_id, field, default=..., type=..., ...)
        if len(node.args) < 3:
            continue
        name_arg = node.args[1]
        nid_arg = node.args[2]
        field_arg = node.args[3] if len(node.args) >= 4 else None

        if not isinstance(name_arg, ast.Constant) or not isinstance(name_arg.value, str):
            continue
        if not isinstance(nid_arg, ast.Constant) or not isinstance(nid_arg.value, str):
            continue
        if field_arg is None:
            continue
        if not isinstance(field_arg, ast.Constant) or not isinstance(field_arg.value, str):
            continue

        name_val = name_arg.value
        nid_val = nid_arg.value
        field_val = field_arg.value
        # Explicit default from keyword args or 5th positional arg
        default_literal = None
        # Check for default= keyword
        for kw in node.keywords:
            if kw.arg == "default":
                ok, lit = _literal_from_ast(kw.value)
                if ok:
                    default_literal = lit
                break
        # Also check 5th positional arg if no keyword default found
        if default_literal is None and len(node.args) >= 5:
            ok, lit = _literal_from_ast(node.args[4])
            if ok:
                default_literal = lit

        bind_calls.append((node, name_val, nid_val, field_val, default_literal, node.keywords))

    if not bind_calls:
        return source

    # --- Build replacements (sorted by reverse position so spans don't shift) ---
    replacements: list[tuple[int, int, str]] = []
    for call_node, name_val, nid_val, field_val, default_literal, keywords in bind_calls:
        # Find corresponding _node call to extract current value
        node_call = node_calls.get(nid_val)
        current_value = None
        if node_call is not None:
            for kw in node_call.keywords:
                if kw.arg == field_val:
                    ok, lit = _literal_from_ast(kw.value)
                    if ok:
                        current_value = lit
                    break

        # Fallback: if field starts with "widget_", try widget_N pattern in kwargs
        if current_value is None and node_call is not None:
            for kw in node_call.keywords:
                if kw.arg == field_val or (
                    field_val.startswith("widget_") and kw.arg == field_val
                ):
                    ok, lit = _literal_from_ast(kw.value)
                    if ok:
                        current_value = lit
                    break

        if current_value is None:
            current_value = 0  # fallback for unlocatable values

        explicit_default = default_literal if default_literal is not None else current_value

        # Build the replacement: wf.register_input(name, node_id, field, value, default=..., ...)
        pieces: list[str] = []
        pieces.append(f"wf.register_input({name_val!r}, {nid_val!r}, {field_val!r}, {current_value!r}")
        if default_literal is not None:
            pieces.append(f", default={default_literal!r}")
        else:
            pieces.append(f", default={current_value!r}")

        # Preserve descriptor kwargs
        for kw in keywords:
            # Only pass through non-default descriptor kwargs
            if kw.arg in ("type", "required", "range", "aliases", "media_semantics", "media", "default"):
                # Skip default if we already emitted it
                if kw.arg == "default":
                    continue
                pieces.append(f", {kw.arg}={ast.unparse(kw.value) if hasattr(ast, 'unparse') else repr(ast.literal_eval(kw.value) if isinstance(kw.value, ast.Constant) else kw.value)}")  # type: ignore[arg-type]

        pieces.append(")")
        replacement = "".join(pieces)

        # Span: use the bind_input call's end_col_offset and col_offset
        start_byte = call_node.col_offset
        end_byte = call_node.end_col_offset if hasattr(call_node, "end_col_offset") else start_byte + 100
        # For multi-line calls we need line-based position
        replacements.append((call_node.lineno, call_node.col_offset, replacement))

    # --- Apply replacements (line-based) ---
    lines = source.splitlines(keepends=True)
    # Build a set of line numbers that have bind_input calls to replace
    bind_input_lines: set[int] = {lineno for lineno, _, _ in replacements}

    result_lines: list[str] = []
    for i, line in enumerate(lines, 1):
        if i in bind_input_lines:
            # Replace the entire line: strip trailing whitespace/newline,
            # add the replacement, then re-add newline
            line_replacements_for_line = [(col, repl) for lineno, col, repl in replacements if lineno == i]
            for col, repl in line_replacements_for_line:
                # Reconstruct: leading indent + replacement + trailing comment
                indent = line[: len(line) - len(line.lstrip())]
                # Check if there's content after the bind_input call on this line
                # (e.g. a comment or other code)
                stripped = line.strip()
                # Find what's after the bind_input(...) call
                import re as _re
                # Remove the bind_input(...) call and replace with register_input.
                # Use a function callback (not a literal replacement string) so
                # backslash sequences in *repl* — e.g. ``\n`` produced by
                # ``repr()`` of a multi-line value — are not interpreted by
                # ``re.sub`` and end up as literal newlines that break the
                # surrounding string literal.
                new_line = _re.sub(
                    r"\b" + _re.escape("bind_input") + r"\s*\([^)]*\)",
                    lambda _m, _r=repl: _r,
                    line,
                    count=1,
                )
                line = new_line
        result_lines.append(line)

    return "".join(result_lines)


def _remove_bind_input_imports(source: str) -> str:
    """Remove ``bind_input`` from import lines in generated output.

    Converts::

        from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_input, bind_output

    to::

        from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_output

    Also handles the case where only ``bind_input`` was imported (removes the
    whole line).
    """
    lines = source.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        # Only process lines that import bind_input
        if "bind_input" not in line or "import" not in line:
            result.append(line)
            continue

        # Split the line at the import keyword
        import re as _re
        # Try to split "from X import Y" pattern
        m = _re.match(r"^(\s*from\s+[\w.]+\s+import\s+)(.*)$", line)
        if m:
            prefix = m.group(1)
            rest = m.group(2)
            # Remove "bind_input" plus optional comma/whitespace
            # Patterns: "bind_input, " or ", bind_input" or "(bind_input)" or "bind_input"
            rest = _re.sub(r"\b" + _re.escape("bind_input") + r"\s*,?\s*", "", rest)
            # Clean up: ", ," → ",", " (,)" or "(, )" → "()"
            rest = _re.sub(r",\s*,", ",", rest)
            rest = _re.sub(r"\(\s*,", "(", rest)
            rest = _re.sub(r",\s*\)", ")", rest)
            rest = rest.strip()
            if not rest or rest in ("()", ""):
                continue  # nothing left to import, drop line
            result.append(prefix + rest + "\n")
            continue

        # Handle "import X" pattern (unlikely for bind_input but safe)
        m2 = _re.match(r"^(\s*import\s+)(.*)$", line)
        if m2:
            prefix = m2.group(1)
            rest = m2.group(2)
            rest = _re.sub(r"\b" + _re.escape("bind_input") + r"\s*,?\s*", "", rest)
            rest = _re.sub(r",\s*,", ",", rest)
            rest = rest.strip()
            if not rest:
                continue
            result.append(prefix + rest + "\n")
            continue

        result.append(line)

    return "".join(result)


def _normalize_ready_metadata(source: str) -> str:
    """Ensure ``READY_METADATA['unbound_inputs']`` has entries for all
    ``register_input`` calls in the generated v2.2 output.

    For templates that had ``bind_input`` calls (and thus no explicit
    ``unbound_inputs``), this creates the missing metadata entries.
    For templates that already have ``unbound_inputs``, it augments partial
    entries where ``register_input`` calls provide richer information.
    """
    tree = ast.parse(source)

    # Collect register_input(node_id.field) pairs
    reg_inputs: list[tuple[str, str, str]] = []  # (name, node_id, field)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "register_input":
            if isinstance(node.func.value, ast.Name):
                # wf.register_input(name, node_id, field, ...)
                if len(node.args) >= 3:
                    name_arg = node.args[0]
                    nid_arg = node.args[1]
                    field_arg = node.args[2]
                    if all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in [name_arg, nid_arg, field_arg]):
                        reg_inputs.append((name_arg.value, nid_arg.value, field_arg.value))

    if not reg_inputs:
        return source

    # Build expected unbound_inputs dict
    expected: dict[str, str] = {}
    for name, node_id, field in reg_inputs:
        key = name
        expected[key] = f"{node_id}.{field}"

    # Check if READY_METADATA already has unbound_inputs
    existing_unbound: dict[str, str] | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in getattr(node, "targets", []):
            name = getattr(target, "id", None) if isinstance(target, ast.Name) else None
            if name == "READY_METADATA" and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and k.value == "unbound_inputs":
                        if isinstance(v, ast.Dict):
                            existing_unbound = {}
                            for sub_k, sub_v in zip(v.keys, v.values):
                                if isinstance(sub_k, ast.Constant) and isinstance(sub_k.value, str):
                                    if isinstance(sub_v, ast.Constant) and isinstance(sub_v.value, str):
                                        existing_unbound[sub_k.value] = sub_v.value
                        break

    # Determine the keys we need to add. If metadata already declares an
    # ``unbound_inputs`` dict, we augment with any missing register_input
    # names (so the bidirectional invariant added by ``_add_metadata_invariant``
    # passes). If no dict exists at all, we synthesise the full set.
    if existing_unbound is not None:
        missing = {k: v for k, v in expected.items() if k not in existing_unbound}
        if not missing:
            return source
        entries = ", ".join(f"{k!r}: {v!r}" for k, v in sorted(missing.items()))
        new_block = f'READY_METADATA["unbound_inputs"].update({{{entries}}})'
    else:
        entries = ", ".join(f"{k!r}: {v!r}" for k, v in sorted(expected.items()))
        if not entries:
            return source
        new_block = f'READY_METADATA.setdefault("unbound_inputs", {{}}).update({{{entries}}})'
    lines = source.splitlines(keepends=True)
    result_lines: list[str] = []
    metadata_open = False
    brace_depth = 0
    insert_idx = -1
    for i, line in enumerate(lines):
        result_lines.append(line)
        if re.match(r"^READY_METADATA\s*[:=]", line):
            metadata_open = True
            brace_depth = line.count("{") - line.count("}")
            if brace_depth <= 0:
                insert_idx = i + 1
                metadata_open = False
        elif metadata_open:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                insert_idx = i + 1
                metadata_open = False
    if insert_idx > 0:
        result_lines.insert(insert_idx, new_block + "\n")
    return "".join(result_lines)


def _add_metadata_invariant(source: str) -> str:
    """Emit a load-time invariant comparing ``register_input`` calls against
    ``READY_METADATA['unbound_inputs']``.

    Only applies to generated v2.2 outputs (those that already have
    ``register_input`` calls).  The invariant is an assert-like block placed
    after the last ``register_input`` call, inside ``build()``.  It will only
    fire on internal drift — legacy templates without ``register_input`` are
    unaffected.
    """
    tree = ast.parse(source)

    # Collect register_input calls: (name, node_id, field)
    reg_calls: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "register_input":
            if len(node.args) >= 3:
                a0, a1, a2 = node.args[0], node.args[1], node.args[2]
                if all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in (a0, a1, a2)):
                    reg_calls.append((a0.value, a1.value, a2.value))

    if not reg_calls:
        # No register_input calls — legacy template, skip invariant
        return source

    # Check if READY_METADATA with unbound_inputs exists
    has_metadata = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in getattr(node, "targets", []):
                if isinstance(tgt, ast.Name) and tgt.id == "READY_METADATA":
                    has_metadata = True
                    break

    if not has_metadata:
        return source

    # Build the bidirectional invariant: register_input calls and
    # READY_METADATA['unbound_inputs'] must reference exactly the same set of
    # logical input names. The literal `_REGISTERED_INPUTS` is bound in-place
    # so the failure message can show both sets.
    reg_names = sorted({n for n, _, _ in reg_calls})
    set_literal = "{" + ", ".join(repr(n) for n in reg_names) + "}" if reg_names else "set()"
    invariant_block = (
        "\n"
        "    # v2.2 invariant: register_input(...) names == READY_METADATA['unbound_inputs'] keys\n"
        f"    _REGISTERED_INPUTS = {set_literal}\n"
        "    _METADATA_INPUTS = set(READY_METADATA.get('unbound_inputs', {}))\n"
        '    assert _METADATA_INPUTS == _REGISTERED_INPUTS, f"register_input / unbound_inputs drift: metadata={_METADATA_INPUTS} register={_REGISTERED_INPUTS}"\n'
    )

    # Insert after the last register_input call line in build()
    lines = source.splitlines(keepends=True)
    in_build = False
    last_reg_line: int | None = None
    for i, line in enumerate(lines):
        if "def build(" in line:
            in_build = True
        if in_build and "register_input(" in line:
            last_reg_line = i

    if last_reg_line is None:
        return source

    result_lines = list(lines)
    # Insert after the last register_input line
    result_lines.insert(last_reg_line + 1, invariant_block)
    return "".join(result_lines)


def _produce_restructure_v2(
    annot_source: str,
    parsed: ParseResult,
    findings: dict[str, Any],
    schema: dict[str, dict[str, Any]],
    node_calls_by_id: dict[str, NodeCall],
    unbound: dict[str, str],
) -> str:
    """Produce restructure-mode: annotate + Rule A (names) + Rule B (no ID dict) + Rule C (PARAMS)."""
    source = annot_source
    tree = ast.parse(source)

    # --- Classify sections (needed for section banners in build()) ---
    classify_sections(parsed.node_calls)

    # --- Rule A: Determine preferred variable names ---
    assign_role_names(parsed.node_calls)
    role_by_id = {nc.node_id: nc.role_name for nc in parsed.node_calls}

    def _is_class_derived(name: str, class_type: str, node_id: str) -> bool:
        """Check if a name matches any class-derived fallback pattern.

        v2.2 addition: also catches lower-case class fallbacks (``cliploader``,
        ``unetloader``) and bare primitive type patterns (``primitivefloat_N``,
        ``primitiveint_N``, ``primitivestring_N``).
        """
        snake = _snake_case(class_type)
        lower = class_type.lower()
        # Subgraph node ids contain ':' which is not a legal Python identifier
        # character; cover both the raw spelling (for legacy or sanitised
        # author names) and the sanitised spelling that this codemod emits.
        safe_id = _safe_id_for_var(node_id)
        suffixes = {node_id, safe_id}
        patterns: set[str] = {snake, lower}
        for sfx in suffixes:
            patterns.update(
                {
                    f"{snake}_{sfx}",
                    f"{lower}_{sfx}",
                    f"param_float_{sfx}",
                    f"param_string_{sfx}",
                    f"param_int_{sfx}",
                    f"primitivefloat_{sfx}",
                    f"primitiveint_{sfx}",
                    f"primitivestring_{sfx}",
                    f"intconstant_{sfx}",
                    f"resized_image_{sfx}",
                    f"preprocessed_image_{sfx}",
                    f"input_image_{sfx}",
                    f"input_video_{sfx}",
                    f"prompt_embedding_{sfx}",
                    f"sampler_kind_{sfx}",
                    f"noise_{sfx}",
                    f"cfg_guider_{sfx}",
                    f"sigmas_{sfx}",
                    f"sampled_latent_{sfx}",
                    f"av_latent_{sfx}",
                    f"av_latent_separated_{sfx}",
                    f"decoded_video_{sfx}",
                    f"decoded_audio_{sfx}",
                    f"decoded_image_{sfx}",
                    f"video_output_{sfx}",
                    f"image_output_{sfx}",
                    f"guided_latent_{sfx}",
                    f"anchored_latent_{sfx}",
                    f"cropped_latent_{sfx}",
                    f"fps_int_{sfx}",
                }
            )
        return name in patterns

    preserved_count = 0
    preferred_name: dict[str, str] = {}
    for nc in parsed.node_calls:
        if _is_class_derived(nc.original_var, nc.class_type, nc.node_id):
            # Original was class-derived — use role name
            preferred_name[nc.node_id] = role_by_id[nc.node_id]
        else:
            # Original was author-chosen — keep it
            preferred_name[nc.node_id] = nc.original_var
            preserved_count += 1

    # Build rename map: original_var -> new_var
    var_rename: dict[str, str] = {}
    for nc in parsed.node_calls:
        if nc.original_var != preferred_name[nc.node_id]:
            var_rename[nc.original_var] = preferred_name[nc.node_id]

    # --- Build unwired primitive node-id lookup from analyzer findings ---
    unwired_primitive_ids: set[str] = set()
    for up in findings.get("findings", {}).get("unwired_primitives", []):
        nid = up.get("node_id")
        if nid is not None:
            unwired_primitive_ids.add(str(nid))

    # --- Rule C: Determine PARAMS entries ---
    param_entries: dict[str, Any] = {}
    param_warnings: dict[str, str] = {}
    placeholder_keys: set[str] = set()

    for logical, target in unbound.items():
        if not isinstance(target, str) or "." not in target:
            continue
        node_id, field = target.split(".", 1)
        nc = node_calls_by_id.get(node_id)
        if nc is None:
            continue

        # Placeholder check: LoadImage/LoadVideo/LoadAudio with file-path-ish values
        if nc.class_type in _PLACEHOLDER_CLASSES and field in _PLACEHOLDER_FIELDS:
            for k, v in nc.kwargs:
                if k == field:
                    ok, lit = _literal_from_ast(v)
                    if ok and isinstance(lit, str) and ("." in lit or "/" in lit or "\\" in lit):
                        placeholder_keys.add(logical)
                        break
            if logical in placeholder_keys:
                continue

        # Extract literal value
        for k, v in nc.kwargs:
            if k == field:
                ok, lit = _literal_from_ast(v)
                if ok:
                    param_entries[logical] = lit
                break

        # Check if this param entry targets an unwired primitive
        if node_id in unwired_primitive_ids:
            param_warnings[logical] = (
                f"UNUSED: target node {node_id} has no consumers — "
                f"see inline comment near node {node_id} for the real "
                f"branch-selection mechanism"
            )

    # Build param field lookup: (node_id, field) -> logical_name
    param_field_lookup: dict[tuple[str, str], str] = {}
    for logical, target in unbound.items():
        if not isinstance(target, str):
            continue
        if logical in placeholder_keys:
            continue
        if logical not in param_entries:
            continue
        if "." in target:
            node_id, field = target.split(".", 1)
            param_field_lookup[(node_id, field)] = logical

    # --- Apply Rules A and C via string-based rewriting (preserves formatting) ---
    restructured = _string_restructure_v2(source, var_rename, param_field_lookup)

    # --- v2.2: Convert bind_input → wf.register_input BEFORE widget resolution ---
    # (must run before _ast_resolve_widget_names because bind_input references
    #  the original widget_N field names that get resolved to real names)
    restructured = _convert_bind_input_calls(restructured)
    # Remove unused bind_input imports from generated output
    restructured = _remove_bind_input_imports(restructured)

    # --- Rule D: Resolve widget_N → real kwarg names ---
    restructured = _ast_resolve_widget_names(restructured)
    # Update register_input field args to match resolved widget names
    restructured = _update_register_input_fields(restructured)
    # Strip redundant widget_N kwargs that shadow linked-input named kwargs
    restructured = _strip_widget_shadows(restructured)
    restructured = _add_widget_todo_comments(restructured)

    # --- Insert PARAMS block ---
    restructured = _insert_params_block(restructured, param_entries, param_warnings)

    # --- v2.2: Normalize READY_METADATA unbound_inputs to match register_input calls (Item 14) ---
    restructured = _normalize_ready_metadata(restructured)

    # --- v2.2: Emit load-time invariant comparing register_input ↔ unbound_inputs (Item 14 / T11) ---
    restructured = _add_metadata_invariant(restructured)

    # --- Add output-slot readability comments ---
    restructured = _add_output_slot_comments(restructured)

    # --- v2.2: Insert section banners in build() body (Item 7) ---
    # Build var_name -> section map from parsed node_calls
    var_to_section: dict[str, str] = {}
    for nc in parsed.node_calls:
        final_name = preferred_name.get(nc.node_id, nc.original_var)
        var_to_section[final_name] = nc.section
    restructured = _insert_section_banners(restructured, var_to_section)

    # --- v2.2: Dual-sampler banner (Item 4) ---
    restructured = _add_dual_sampler_banner(restructured, parsed, preferred_name)

    # --- v2.2: Magic constant twins → shared module-level constant (Item 3) ---
    restructured = _exec_magic_constant_twins(restructured, findings, preferred_name)

    # --- v2.2: Branch selector → executable GUIDE_BRANCH + GUIDE_NODES (Item 6) ---
    # Legacy narrative templates already use the `_at` sidecar style and may
    # not carry the helper block this text transform anchors on. Leave their
    # existing branch surface intact and let the v2.3 pass normalize it.
    if parsed.has_node_helper:
        restructured = _exec_branch_selector(restructured, findings, preferred_name)

    # --- v2.2: Unwired primitive cleanup (control_mode deletion, Item 11) ---
    restructured = _exec_unwired_primitive_cleanup(restructured, findings, preferred_name)

    # --- v2.2: Factor repeated helpers (Item 13 / T8) ---
    restructured = _factor_repeated_helpers(restructured)

    # --- v2.2: Rename class-fallback variables with role-derived names (Item E) ---
    restructured = _rename_class_fallback_vars(restructured)

    # --- v2.2: Annotate ComfySwitchNode chains with BRANCH SELECTION comments (Item C) ---
    restructured = _annotate_comfyswitch_branches(restructured)

    # --- v2.2: Hoist model filenames into a MODEL_FILES dict (Item B) ---
    restructured = _hoist_model_files(restructured)

    # --- v2.2: Create PARAMS dict if missing (Item D) ---
    restructured = _ensure_params_block(restructured)

    # --- v2.3: Beautiful-template surface (single public-input/model truth) ---
    restructured = _convert_restructure_to_v23(restructured)

    return restructured


def _string_restructure_v2(
    source: str,
    var_rename: dict[str, str],
    param_lookup: dict[tuple[str, str], str],
) -> str:
    """AST-aware rewriting that preserves original formatting and comments.

    Phase 1: AST-based variable renaming (never touches string literals,
    comments, or keyword-argument names).

    Phase 2: Replace literal kwarg values with PARAMS refs via AST-span
    analysis (works across multi-line calls and comma-containing strings).
    """
    result = source

    # --- Phase 1: AST-based variable renaming ---
    if var_rename:
        result = _ast_rename_variables(result, var_rename)

    # --- Phase 2: AST-based PARAMS substitution ---
    if param_lookup:
        result = _ast_substitute_params(result, param_lookup)

    return result


def _ast_rename_variables(source: str, var_rename: dict[str, str]) -> str:
    """Rename variable references using AST-span rewriting.

    Only rewrites ast.Name nodes that:
    - Have an id matching a rename target
    - Are NOT the ``arg`` attribute of an ast.keyword (i.e., are not kwarg names)
    - Are NOT inside string literals or comments (guaranteed by AST walk)
    """
    if not var_rename:
        return source

    tree = ast.parse(source)

    # Build a set of Name nodes that are kwarg names (the 'arg' of ast.keyword)
    kwarg_name_ids: set[int] = set()
    for kw in ast.walk(tree):
        if isinstance(kw, ast.keyword) and kw.arg is not None:
            # The 'arg' is stored as a string attribute, not an AST node,
            # but we need to find Name nodes that represent kwarg args.
            # In AST, keyword.arg is a plain string, not a Name node,
            # so ast.Name nodes are never directly keyword arg names.
            # However, in assignment targets like `image=...`, the
            # 'image' is an ast.Name in an ast.keyword context, but that
            # doesn't happen — ast.keyword.arg is always a bare string.
            # The actual concern is about function def parameters and
            # other positions where a Name is followed by '='.
            pass

    # Actually, the AST approach handles this intrinsically:
    # ast.Name nodes in an ast.keyword.arg position don't exist — arg is a str.
    # The risk is in expressions like `image=foo` where `image` is not a Name
    # but a literal keyword. So we just need to not rename Names that appear
    # as assignment targets (where they're being defined, not referenced).
    # But we DO want to rename assignment targets too — the goal is to rename
    # the variable everywhere. The only names we must NOT rename are those
    # that appear as keyword argument names in function calls, which aren't
    # ast.Name nodes at all.

    # Collect all Name nodes that match rename targets
    # Sort by position (reverse) so replacements don't shift later spans
    replacements: list[tuple[int, int, str]] = []  # (start_offset, end_offset, new_name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Name):
            continue
        if node.id not in var_rename:
            continue
        new_name = var_rename[node.id]
        if new_name == node.id:
            continue
        # We have end_lineno/end_col_offset in Python 3.8+
        if not hasattr(node, 'end_lineno') or node.end_lineno is None:
            continue

        replacements.append((node.col_offset, node.end_col_offset, node.lineno, new_name))

    if not replacements:
        return source

    # Convert line:col to character offsets
    line_offsets = _compute_line_offsets(source)

    char_replacements: list[tuple[int, int, str]] = []
    for col_start, col_end, lineno, new_name in replacements:
        line_idx = lineno - 1
        if line_idx >= len(line_offsets):
            continue
        start = line_offsets[line_idx] + col_start
        end = line_offsets[line_idx] + col_end
        char_replacements.append((start, end, new_name))

    # Sort by start offset (descending) so replacements don't shift each other
    char_replacements.sort(key=lambda x: -x[0])

    # Apply replacements
    chars = list(source)
    for start, end, new_name in char_replacements:
        if source[start:end] in var_rename:
            chars[start:end] = list(new_name)

    return ''.join(chars)


def _compute_line_offsets(source: str) -> list[int]:
    """Compute starting character offset for each line in *source*."""
    offsets = [0]
    for i, ch in enumerate(source):
        if ch == '\n':
            offsets.append(i + 1)
    return offsets


def _ast_substitute_params(
    source: str,
    param_lookup: dict[tuple[str, str], str],
) -> str:
    """Replace kwarg literal values with PARAMS refs using AST-span analysis.

    For every (node_id, field) → logical_name in *param_lookup*, locate the
    matching _node(...) call, find the ``field=value`` kwarg, and replace
    only the value span with ``PARAMS["logical"]``.

    Handles multi-line calls and comma-containing string literals by using
    AST lineno/end_lineno/col_offset/end_col_offset spans.
    """
    if not param_lookup:
        return source

    tree = ast.parse(source)
    line_offsets = _compute_line_offsets(source)

    # Build mapping: node_id -> list of (Call node, kwarg_ast_node, field_name)
    # We need the actual AST node for each kwarg value to get its span.
    call_map: dict[str, list[tuple[ast.Call, ast.keyword]]] = defaultdict(list)

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ('_node', '_at'):
            continue
        if len(stmt.value.args) < 3:
            continue
        id_arg = stmt.value.args[2]
        if not isinstance(id_arg, ast.Constant):
            continue
        node_id = str(id_arg.value)

        for kw in stmt.value.keywords:
            call_map[node_id].append((stmt.value, kw))

    # Collect replacements: (start_char, end_char, replacement_string)
    char_replacements: list[tuple[int, int, str]] = []

    for (node_id, field), logical in param_lookup.items():
        if node_id not in call_map:
            continue
        for call_node, kw in call_map[node_id]:
            if kw.arg != field:
                continue
            # Get the value span
            val_node = kw.value
            if not hasattr(val_node, 'end_lineno') or val_node.end_lineno is None:
                continue
            if val_node.lineno < 1 or val_node.lineno > len(line_offsets):
                continue

            # Check if value is already a PARAMS ref
            if isinstance(val_node, ast.Subscript):
                if isinstance(val_node.value, ast.Name) and val_node.value.id == 'PARAMS':
                    continue

            start_char = line_offsets[val_node.lineno - 1] + val_node.col_offset
            end_char = line_offsets[val_node.end_lineno - 1] + val_node.end_col_offset

            replacement = f'PARAMS["{logical}"]'
            char_replacements.append((start_char, end_char, replacement))

    if not char_replacements:
        return source

    # Sort by start offset (descending)
    char_replacements.sort(key=lambda x: -x[0])

    chars = list(source)
    for start, end, replacement in char_replacements:
        chars[start:end] = list(replacement)

    return ''.join(chars)


def _insert_params_block(
    source: str,
    param_entries: dict[str, Any],
    param_warnings: dict[str, str] | None = None,
) -> str:
    """Insert PARAMS dict block before build(), after READY_REQUIREMENTS.

    *param_warnings* maps logical_name → warning string.  When provided,
    an inline ``# ⚠ <warning>`` comment is appended to the matching entry line.
    """
    if not param_entries:
        return source

    # Build PARAMS block with sub-group comments
    lines_block: list[str] = []
    lines_block.append("")
    lines_block.append("PARAMS: dict[str, object] = {")
    sorted_keys = sorted(param_entries.keys())
    warnings = param_warnings or {}

    # Group keys by PARAM_GROUPS membership
    key_groups: dict[str, list[str]] = {}
    for key in sorted_keys:
        grp = _group_for(key)
        key_groups.setdefault(grp, []).append(key)

    # Emit groups in PARAM_GROUPS order, then "other"
    group_order: list[str] = [g for g, _ in PARAM_GROUPS] + ["other"]
    first_group = True
    for grp_name in group_order:
        grp_keys = key_groups.get(grp_name)
        if not grp_keys:
            continue
        if not first_group:
            lines_block.append("")
        first_group = False
        lines_block.append(f"    # \u2014 {grp_name} \u2014")
        for key in grp_keys:
            val = param_entries[key]
            line = f"    {key!r}: {val!r},"
            if key in warnings:
                line += f"  # ⚠ {warnings[key]}"
            lines_block.append(line)
    lines_block.append("}")
    lines_block.append("")

    params_src = "\n".join(lines_block) + "\n"

    lines = source.splitlines(keepends=True)
    out_lines: list[str] = []
    inserted = False
    in_requirements = False
    brace_depth = 0

    for line in lines:
        if not inserted:
            if "READY_REQUIREMENTS" in line:
                in_requirements = True
            if in_requirements:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth == 0 and line.strip() == "}":
                    # This is the closing brace of READY_REQUIREMENTS
                    out_lines.append(line)
                    out_lines.append(params_src)
                    inserted = True
                    in_requirements = False
                    continue
        out_lines.append(line)

    if not inserted:
        result = "".join(out_lines)
        result = result.replace("\ndef build():", f"\n{params_src}\ndef build():")
        return result

    return "".join(out_lines)


def _widget_position_to_index(name: str) -> int | None:
    """Parse ``widget_N`` or ``widget_N:convert`` into integer index *N*."""
    if not name.startswith("widget_"):
        return None
    rest = name[len("widget_"):]
    if ":" in rest:
        rest = rest.split(":")[0]
    try:
        return int(rest)
    except ValueError:
        return None


_PRIMITIVE_CLASSES: set[str] = {
    "PrimitiveFloat", "PrimitiveString", "PrimitiveInt", "PrimitiveBoolean",
    "INTConstant", "StringConstant",
}


def _ast_resolve_widget_names(source: str) -> str:
    """Rewrite ``widget_N=`` kwargs on ``_node(...)`` calls to their real names.

    Uses ``effective_widget_names_for_class`` (curated WIDGET_SCHEMA first,
    object_info fallback) to map positional widget indices → real kwarg names.

    Also deletes widget_N kwargs whose resolved name is None (link-only sockets)
    and tracks widget→real-name mappings for register_input field updates.

    Returns (modified_source, widget_rename_map) where widget_rename_map is
    {node_id: {old_field: new_field}} for use by register_input field updater.
    """
    try:
        from vibecomfy.porting.widget_schema import WIDGET_SCHEMA  # noqa: PLC0415
        from vibecomfy.porting.widget_aliases import (  # noqa: PLC0415
            COMPILE_WIDGET_ALIAS_CLASS_TYPES,
        )
        from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415
    except ImportError:
        return source

    tree = ast.parse(source)
    line_offsets = _compute_line_offsets(source)

    # Collect replacements: (start_char, end_char, replacement_str)
    # None replacement_str means DELETE this span
    char_replacements: list[tuple[int, int, str | None]] = []
    # Track widget renames per node for register_input updates
    widget_rename_map: dict[str, dict[str, str]] = {}

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        cls_arg = stmt.value.args[1]
        if not isinstance(cls_arg, ast.Constant) or not isinstance(cls_arg.value, str):
            continue
        class_type = cls_arg.value
        id_arg = stmt.value.args[2]
        node_id = str(id_arg.value) if isinstance(id_arg, ast.Constant) else None

        # Parity rule: rename ``widget_N`` -> ``name`` when the class has a
        # curated ``WIDGET_SCHEMA`` entry AND is registered in
        # ``COMPILE_WIDGET_ALIAS_CLASS_TYPES`` so the runtime alias
        # normalisation (``apply_positional_widget_aliases``) treats both
        # widget_N and the named form identically. For classes covered by
        # the alias list but with a curated ``None`` at index N, delete the
        # widget_N kwarg outright — runtime aliasing pops it on compile so
        # removing it from source preserves api_dict parity.
        widget_names = list(WIDGET_SCHEMA.get(class_type) or [])
        if any(name is None for name in widget_names):
            fallback_widget_names = object_info_widget_order(class_type)
            for index, name in enumerate(widget_names):
                if name is None and index < len(fallback_widget_names):
                    widget_names[index] = fallback_widget_names[index]
        if not widget_names:
            continue
        # If the class is not in the runtime alias allow-list, renaming would
        # leak a non-widget kwarg into the compiled api_dict and break parity.
        if class_type not in COMPILE_WIDGET_ALIAS_CLASS_TYPES and not class_type.startswith("Primitive"):
            continue

        # Collect existing non-widget kwarg names to avoid collisions
        existing_names: set[str] = set()
        for kw in stmt.value.keywords:
            if _widget_position_to_index(kw.arg) is None:
                existing_names.add(kw.arg)

        for kw in stmt.value.keywords:
            idx = _widget_position_to_index(kw.arg)
            if idx is None:
                continue

            # Compute the span of the kwarg name for rename.
            if kw.lineno < 1 or kw.lineno > len(line_offsets):
                continue
            arg_len = len(kw.arg)
            kw_start = line_offsets[kw.lineno - 1] + kw.col_offset
            name_end = kw_start + arg_len

            if 0 <= idx < len(widget_names) and widget_names[idx] is not None:
                new_name = widget_names[idx]
                # Skip rename if it would collide with an existing non-widget kwarg
                if new_name in existing_names:
                    continue
                if new_name != kw.arg:
                    char_replacements.append((kw_start, name_end, new_name))
                    if node_id is not None:
                        widget_rename_map.setdefault(node_id, {})[kw.arg] = new_name
            elif 0 <= idx < len(widget_names) and widget_names[idx] is None:
                # Curated schema marks this index as a link-only socket. Runtime
                # aliasing pops the widget_N kwarg on compile, so delete it from
                # source for cleaner LLM-readable output without affecting parity.
                # Span includes the kwarg name, ``=``, value, and any trailing
                # comma+whitespace up to the next kwarg or closing paren.
                value_end = (
                    kw.value.end_col_offset is not None
                    and line_offsets[kw.value.end_lineno - 1] + kw.value.end_col_offset
                )
                if not value_end:
                    continue
                # Walk forward past trailing comma and whitespace/newline.
                src_chars = source
                cut_end = value_end
                while cut_end < len(src_chars) and src_chars[cut_end] in " \t":
                    cut_end += 1
                if cut_end < len(src_chars) and src_chars[cut_end] == ",":
                    cut_end += 1
                    while cut_end < len(src_chars) and src_chars[cut_end] in " \t":
                        cut_end += 1
                    if cut_end < len(src_chars) and src_chars[cut_end] == "\n":
                        cut_end += 1
                        # Also consume the indentation on the next line so we
                        # don't leave a bare-indent gap.
                        while cut_end < len(src_chars) and src_chars[cut_end] in " \t":
                            cut_end += 1
                # Walk backwards from kw_start to absorb preceding indent on a
                # dedicated kwarg line so we don't leave an empty line behind.
                cut_start = kw_start
                # If the line before kw_start is only whitespace + this kwarg,
                # take the line break before it too.
                while cut_start > 0 and src_chars[cut_start - 1] in " \t":
                    cut_start -= 1
                # If we land on a newline, the kwarg lived on its own line —
                # consume that newline so we don't leave a blank gap.
                if cut_start > 0 and src_chars[cut_start - 1] == "\n":
                    # Only consume if we also consumed the trailing comma+newline
                    # (otherwise we'd merge two lines).
                    if cut_end > value_end and (
                        cut_end - 1 < len(src_chars) and src_chars[cut_end - 1] not in "\n"
                    ):
                        # Don't merge lines; leave the leading newline alone.
                        pass
                    else:
                        cut_start -= 1
                char_replacements.append((cut_start, cut_end, None))

    if not char_replacements:
        return source

    # Sort by start offset (descending)
    char_replacements.sort(key=lambda x: -x[0])

    chars = list(source)
    for start, end, replacement in char_replacements:
        if replacement is None:
            # Delete the span
            del chars[start:end]
        else:
            chars[start:end] = list(replacement)

    return "".join(chars)


def _add_widget_todo_comments(source: str) -> str:
    """Add ``# widget_N → ?`` comment lines after ``_node(...)`` calls that still
    have unresolved ``widget_N=`` kwargs."""
    try:
        from vibecomfy.porting.widget_schema import effective_widget_names_for_class  # noqa: PLC0415
    except ImportError:
        return source

    tree = ast.parse(source)

    # Collect (line_number, comment_string) for nodes still carrying widget_N
    pending_comments: dict[int, list[str]] = defaultdict(list)

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        cls_arg = stmt.value.args[1]
        if not isinstance(cls_arg, ast.Constant) or not isinstance(cls_arg.value, str):
            continue
        class_type = cls_arg.value

        widget_names = effective_widget_names_for_class(
            class_type, allow_object_info_fallback=True,
        )

        unresolved: list[int] = []
        for kw in stmt.value.keywords:
            idx = _widget_position_to_index(kw.arg)
            if idx is None:
                continue
            if idx >= len(widget_names) or widget_names[idx] is None:
                unresolved.append(idx)

        if unresolved:
            markers = [f"widget_{i} → ?" for i in unresolved]
            comment = "# " + ", ".join(markers) + "  # TODO: install pack for real names"
            pending_comments.setdefault(stmt.lineno, []).append(comment)

    if not pending_comments:
        return source

    lines = source.splitlines(keepends=True)
    out_lines: list[str] = []
    for i, line in enumerate(lines, start=1):
        out_lines.append(line.rstrip("\n"))
        if i in pending_comments:
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]
            for c in pending_comments[i]:
                out_lines.append(f"{indent}{c}")
    return "\n".join(out_lines) + "\n"


def _update_register_input_fields(source: str) -> str:
    """Update ``register_input`` field args to match resolved widget names.

    After ``_ast_resolve_widget_names`` renames ``widget_N`` → real names in
    ``_node`` calls, the corresponding ``register_input`` calls must also
    reference the real field names. This pass detects ``widget_N`` field
    references in ``register_input`` and maps them to real names using the
    same schemas cache.
    """
    try:
        from vibecomfy.porting.widget_schema import WIDGET_SCHEMA  # noqa: PLC0415
        from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415
    except ImportError:
        return source

    tree = ast.parse(source)
    line_offsets = _compute_line_offsets(source)

    # Build a map of node_id → class_type from _node calls
    node_classes: dict[str, str] = {}
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        cls_arg = stmt.value.args[1]
        id_arg = stmt.value.args[2]
        if not isinstance(cls_arg, ast.Constant) or not isinstance(cls_arg.value, str):
            continue
        if not isinstance(id_arg, ast.Constant) or not isinstance(id_arg.value, str):
            continue
        node_classes[str(id_arg.value)] = cls_arg.value

    # Now find register_input calls and update field if it's widget_N
    char_replacements: list[tuple[int, int, str]] = []

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Call):
            continue
        if not isinstance(stmt.func, ast.Attribute) or stmt.func.attr != "register_input":
            continue
        if not isinstance(stmt.func.value, ast.Name):
            continue
        if len(stmt.args) < 3:
            continue
        # Args: name, node_id, field, [value], **descriptors
        node_id_arg = stmt.args[1]
        field_arg = stmt.args[2]
        if not isinstance(node_id_arg, ast.Constant) or not isinstance(node_id_arg.value, str):
            continue
        if not isinstance(field_arg, ast.Constant) or not isinstance(field_arg.value, str):
            continue
        node_id = str(node_id_arg.value)
        field = field_arg.value

        # Only process widget_N fields
        idx = _widget_position_to_index(field)
        if idx is None:
            continue

        class_type = node_classes.get(node_id)
        if class_type is None:
            continue

        widget_names = list(WIDGET_SCHEMA.get(class_type) or [])
        if any(name is None for name in widget_names):
            fallback_widget_names = object_info_widget_order(class_type)
            for index, name in enumerate(widget_names):
                if name is None and index < len(fallback_widget_names):
                    widget_names[index] = fallback_widget_names[index]
        if not widget_names:
            widget_names = object_info_widget_order(class_type)
        if not widget_names or all(n is None for n in widget_names):
            continue

        if 0 <= idx < len(widget_names) and widget_names[idx] is not None:
            new_name = widget_names[idx]
            if new_name != field:
                # Replace the field string literal
                if field_arg.lineno < 1 or field_arg.lineno > len(line_offsets):
                    continue
                start_char = line_offsets[field_arg.lineno - 1] + field_arg.col_offset
                # ast.Constant.value includes quotes — find the actual string span
                raw_line = source.splitlines()[field_arg.lineno - 1]
                # Search in the raw line for the field string
                # Use a simpler approach: the Constant node's span covers the quoted string
                if hasattr(field_arg, 'end_col_offset') and field_arg.end_col_offset is not None:
                    end_char = line_offsets[field_arg.lineno - 1] + field_arg.end_col_offset
                else:
                    # Fallback: search for the quoted string
                    end_char = start_char + len(repr(field))
                new_str = repr(new_name)
                char_replacements.append((start_char, end_char, new_str))

    if not char_replacements:
        return source

    char_replacements.sort(key=lambda x: -x[0])
    chars = list(source)
    for start, end, replacement in char_replacements:
        chars[start:end] = list(replacement)
    return "".join(chars)


def _strip_widget_shadows(source: str) -> str:
    """Strip redundant ``widget_N`` kwargs that shadow linked-input named kwargs.

    When a ``_node`` call has both a real linked kwarg (e.g., ``width=width.out(0)``)
    AND a ``widget_N`` for the same positional index (e.g., ``widget_0=256``),
    the widget_N is dead weight. This pass detects those cases and strips the
    redundant widget_N kwarg entirely.
    """
    try:
        from vibecomfy.porting.widget_schema import WIDGET_SCHEMA  # noqa: PLC0415
        from vibecomfy.porting.widget_aliases import (  # noqa: PLC0415
            COMPILE_WIDGET_ALIAS_CLASS_TYPES,
        )
    except ImportError:
        return source

    tree = ast.parse(source)
    line_offsets = _compute_line_offsets(source)

    char_replacements: list[tuple[int, int, str | None]] = []

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        cls_arg = stmt.value.args[1]
        if not isinstance(cls_arg, ast.Constant) or not isinstance(cls_arg.value, str):
            continue
        class_type = cls_arg.value

        # Parity rule: only strip widget_N shadows when runtime alias
        # normalisation would itself collapse widget_N onto the named kwarg.
        # That requires class in COMPILE_WIDGET_ALIAS_CLASS_TYPES with a
        # committed WIDGET_SCHEMA entry. For unknown classes (e.g.
        # LTXFloatToInt) the original api_dict legitimately contains both
        # ``widget_N`` and the linked field — stripping breaks parity.
        if class_type not in COMPILE_WIDGET_ALIAS_CLASS_TYPES:
            continue
        widget_names = WIDGET_SCHEMA.get(class_type)
        if not widget_names:
            continue

        # Collect set of kwarg names that are NOT widget_N
        non_widget_names: set[str] = set()
        for kw in stmt.value.keywords:
            if _widget_position_to_index(kw.arg) is None:
                non_widget_names.add(kw.arg)

        if not non_widget_names:
            continue

        # For each widget_N kwarg, check if its resolved name already
        # exists as a non-widget kwarg (shadow condition)
        for kw in stmt.value.keywords:
            idx = _widget_position_to_index(kw.arg)
            if idx is None:
                continue
            resolved_name = widget_names[idx] if idx < len(widget_names) else None
            if resolved_name is not None and resolved_name in non_widget_names:
                # Shadow detected — delete this widget_N kwarg
                if kw.lineno < 1 or kw.lineno > len(line_offsets):
                    continue
                kw_start = line_offsets[kw.lineno - 1] + kw.col_offset

                val_node = kw.value
                if hasattr(val_node, 'end_lineno') and val_node.end_lineno is not None:
                    if val_node.end_lineno - 1 < len(line_offsets):
                        val_end = line_offsets[val_node.end_lineno - 1] + val_node.end_col_offset
                    else:
                        val_end = kw_start + len(kw.arg)
                else:
                    val_end = kw_start + len(kw.arg)

                # Consume trailing comma and whitespace
                rest = source[val_end:]
                consumed = 0
                for ch in rest:
                    if ch in (' ', '\t'):
                        consumed += 1
                    elif ch == ',':
                        consumed += 1
                        break
                    else:
                        break
                delete_end = val_end + consumed
                char_replacements.append((kw_start, delete_end, None))

    if not char_replacements:
        return source

    char_replacements.sort(key=lambda x: -x[0])
    chars = list(source)
    for start, end, replacement in char_replacements:
        if replacement is None:
            del chars[start:end]
        else:
            chars[start:end] = list(replacement)
    return "".join(chars)


def _add_output_slot_comments(source: str) -> str:
    """Rewrite ``.out(N)`` calls to ``.out("NAME")`` using the object_info cache.

    Instead of adding trailing ``# = .out("NAME")`` comments, v2.2 rewrites
    the integer slot to a string slot directly — ``.out(0)`` becomes ``.out("MODEL")``.
    The ``Handle.out`` method in ``vibecomfy/workflow.py`` now resolves string
    names via the same cache, so this is executable and readable.

    For nodes with a single output where the name matches the type, the integer
    form is kept (it's unambiguous). Only nodes with >=2 outputs get named slots.
    """
    try:
        from vibecomfy.porting.object_info.consume import output_names  # noqa: PLC0415
        from vibecomfy.porting.object_info.consume import output_types  # noqa: PLC0415
    except ImportError:
        return source

    tree = ast.parse(source)
    line_offsets = _compute_line_offsets(source)

    # Map var_name -> (node_id, class_type, output_names, output_types)
    var_info: dict[str, tuple[str, str, list[str], list[str]]] = {}
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        cls_arg = stmt.value.args[1]
        id_arg = stmt.value.args[2]
        if not isinstance(cls_arg, ast.Constant) or not isinstance(cls_arg.value, str):
            continue
        if not isinstance(id_arg, ast.Constant) or not isinstance(id_arg.value, str):
            continue
        class_type = cls_arg.value
        node_id = id_arg.value
        names = output_names(class_type)
        types_ = output_types(class_type)
        if not names:
            continue
        for target in stmt.targets if hasattr(stmt, "targets") else [stmt.target]:
            if isinstance(target, ast.Name):
                var_info[target.id] = (node_id, class_type, names, types_)

    if not var_info:
        return source

    # Find all .out(N) calls and rewrite slot from integer to string when named
    char_replacements: list[tuple[int, int, str]] = []

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Call):
            continue
        if not isinstance(stmt.func, ast.Attribute) or stmt.func.attr != "out":
            continue
        if not isinstance(stmt.func.value, ast.Name):
            continue
        if len(stmt.args) != 1 or not isinstance(stmt.args[0], ast.Constant):
            continue
        var_name = stmt.func.value.id
        slot = stmt.args[0].value
        if not isinstance(slot, int):
            continue

        info = var_info.get(var_name)
        if info is None:
            continue
        _nid, _class_type, names, types_ = info
        if slot < 0 or slot >= len(names):
            continue
        name = str(names[slot]).strip().replace(" ", "_").upper()
        if not name:
            continue

        # Rewrite .out(N) -> .out("NAME") even for single-output nodes:
        # the named form is more readable and is resolved through the same
        # schemas cache by `vibecomfy/workflow.py`.
        # Rewrite .out(N) -> .out("NAME")
        if not hasattr(stmt.args[0], 'lineno'):
            continue
        slot_node = stmt.args[0]
        if slot_node.lineno < 1 or slot_node.lineno > len(line_offsets):
            continue
        slot_start = line_offsets[slot_node.lineno - 1] + slot_node.col_offset
        if hasattr(slot_node, 'end_col_offset') and slot_node.end_col_offset is not None:
            slot_end = line_offsets[slot_node.lineno - 1] + slot_node.end_col_offset
        else:
            slot_end = slot_start + len(repr(slot))

        new_str = repr(name)
        char_replacements.append((slot_start, slot_end, new_str))

    if not char_replacements:
        return source

    char_replacements.sort(key=lambda x: -x[0])
    chars = list(source)
    for start, end, replacement in char_replacements:
        chars[start:end] = list(replacement)

    return "".join(chars)


def _insert_section_banners(source: str, var_to_section: dict[str, str]) -> str:
    """Insert ``# ════ SECTION_NAME ════`` banner comments in build() body.

    Scans assignment statements inside ``build()`` for ``_node``/``_at`` calls.
    When a cluster of nodes belonging to a new section starts, inserts a banner
    comment line above the first node in that cluster.
    """
    if not var_to_section:
        return source

    lines = source.splitlines(keepends=True)
    # Find the build() function start
    in_build = False
    indent_level: int | None = None
    current_section: str | None = None
    section_order = {s: i for i, s in enumerate(SECTION_ORDER)}
    section_order.setdefault("MISC", len(SECTION_ORDER))

    result_lines: list[str] = []
    for line in lines:
        if not in_build:
            result_lines.append(line)
            if "def build(" in line:
                in_build = True
            continue

        # Determine indentation of the build body (4 spaces typically)
        if indent_level is None:
            stripped = line.lstrip()
            if stripped:
                indent_level = len(line) - len(stripped)
            else:
                result_lines.append(line)
                continue

        # Check if this line starts an assignment targeting a section-tracked var
        stripped = line.lstrip()
        # Detect variable assignment: `var_name = _node(...)` or `var_name = _at(...)`
        eq_pos = stripped.find("=")
        is_node_assign = False
        assign_var: str | None = None
        if eq_pos > 0:
            lhs = stripped[:eq_pos].strip()
            # Simple LHS variable assignment (not tuple unpacking etc.)
            if lhs.isidentifier():
                rhs = stripped[eq_pos + 1:].strip()
                if rhs.startswith("_node(") or rhs.startswith("_at("):
                    is_node_assign = True
                    assign_var = lhs

        if is_node_assign and assign_var and assign_var in var_to_section:
            sec = var_to_section[assign_var]
            if sec != current_section:
                # Emit section banner
                current_section = sec
                banner = f"# {'═' * 4} {sec} {'═' * 4}"
                banner_line = " " * indent_level + banner + "\n"
                result_lines.append(banner_line)
        result_lines.append(line)

    return "".join(result_lines)


def _rewrite_v23_section_banners(source: str, specs: OrderedDict[str, dict[str, Any]]) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    public_targets = {
        (str(spec.get("node")), str(spec.get("field")))
        for spec in specs.values()
    }
    var_to_section: dict[str, str] = {}
    for record in _collect_v23_node_records(tree):
        var = record.get("var")
        if not var:
            continue
        class_type = str(record["class_type"])
        node_id = str(record["node_id"])
        if class_type.startswith("Primitive") or class_type in {"INTConstant", "LoadImage", "LoadVideo"}:
            fields = set(record.get("fields", set())) | set(record.get("kwargs", {})) | set(record.get("kw_params", {}))
            if not any((node_id, field) in public_targets for field in fields):
                section = _semantic_section_for_class(class_type)
                if section == "INPUTS":
                    section = "SAMPLING"
            else:
                section = "INPUTS"
        else:
            section = _semantic_section_for_class(class_type)
        var_to_section[str(var)] = section
    if not var_to_section:
        return source
    lines = [
        line for line in source.splitlines(keepends=True)
        if not re.match(r"\s*# ════ .+ ════\s*$", line)
    ]
    return _insert_section_banners("".join(lines), var_to_section)


def _add_dual_sampler_banner(
    source: str,
    parsed: "ParseResult",
    preferred_name: dict[str, str],
) -> str:
    """Detect dual-sampler config and insert TWO-STAGE SAMPLING banner.

    A dual-sampler config exists when two CFGGuider nodes have ``model=`` inputs
    pointing to different upstream chains (one through NAG/bypass, the other
    through the full patch stack).  When detected, inserts a banner comment
    block above the first CFGGuider node.

    Detection heuristic:
    - Find all CFGGuider nodes in ``parsed.node_calls``
    - If exactly 2, look at their ``model=`` kwarg upstream var names
    - If the upstream vars differ, flag as dual-sampler
    - Insert banner line before the first CFGGuider assignment in build()
    """
    if len(parsed.node_calls) < 2:
        return source

    # Find CFGGuider nodes
    cfg_guiders: list[NodeCall] = [
        nc for nc in parsed.node_calls if nc.class_type == "CFGGuider"
    ]
    if len(cfg_guiders) != 2:
        return source

    # Extract model= upstream var names
    model_upstreams: list[str] = []
    for nc in cfg_guiders:
        for kw_name, kw_val in nc.kwargs:
            if kw_name == "model" and isinstance(kw_val, ast.Attribute):
                if isinstance(kw_val.value, ast.Name):
                    model_upstreams.append(kw_val.value.id)
                    break
                elif isinstance(kw_val.value, ast.Call) and isinstance(kw_val.value.func, ast.Attribute):
                    # e.g., model_with_nag.out(0)
                    if isinstance(kw_val.value.func.value, ast.Name):
                        model_upstreams.append(kw_val.value.func.value.id)
                        break
            elif kw_name == "model" and isinstance(kw_val, ast.Call):
                # e.g., model=nag_model.out(0) — ast.Call wrapping ast.Attribute
                if isinstance(kw_val.func, ast.Attribute) and kw_val.func.attr == "out":
                    if isinstance(kw_val.func.value, ast.Name):
                        model_upstreams.append(kw_val.func.value.id)
                        break

    if len(model_upstreams) != 2 or model_upstreams[0] == model_upstreams[1]:
        return source

    # Use the PREFERRED (post-rename) names for the two CFGGuiders
    cfg_names: list[str] = []
    for nc in cfg_guiders:
        final_name = preferred_name.get(nc.node_id, nc.original_var)
        cfg_names.append(final_name)

    # Find the first CFGGuider assignment line and insert banner before it
    lines = source.splitlines(keepends=True)
    in_build = False
    inserted = False
    result_lines: list[str] = []
    first_cfg_name = cfg_names[0]

    for line in lines:
        if not in_build:
            result_lines.append(line)
            if "def build(" in line:
                in_build = True
            continue

        if not inserted:
            stripped = line.lstrip()
            if stripped.startswith(first_cfg_name + " =") or stripped.startswith(first_cfg_name + "="):
                # Found the first CFGGuider — insert banner
                indent = " " * (len(line) - len(stripped))
                banner_lines = [
                    f"{indent}# {'═' * 4} TWO-STAGE SAMPLING {'═' * 4}\n",
                    f"{indent}# Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning\n",
                    f"{indent}# Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning\n",
                ]
                result_lines.extend(banner_lines)
                inserted = True
        result_lines.append(line)

    return "".join(result_lines)


# --------------------------------------------------------------------------- #
# v2.2: Executable analyzer findings (Item 3, 6, 11)                         #
# --------------------------------------------------------------------------- #

def _exec_magic_constant_twins(
    source: str,
    findings: dict[str, Any],
    preferred_name: dict[str, str],
) -> str:
    """For each magic_constant_twins group, emit a shared module-level constant
    and rewrite both callsites to reference it.  COUPLED comments are dropped.

    The constant name is derived from the common prefix of the sink field names
    (e.g. ``num_images.strength_1`` / ``num_images.strength_2`` → ``ANCHOR_STRENGTH``).
    """
    twins = findings.get("findings", {}).get("magic_constant_twins", [])
    if not twins:
        return source

    lines = source.splitlines(keepends=True)

    # Collect insertions: lines to add before build(), and line-level replacements
    constants_to_insert: list[str] = []  # lines to insert before def build(
    replacements: list[tuple[int, int, str]] = []  # (line_idx, end_line_idx, new_line_text)
    lines_to_delete: set[int] = set()

    for twin_group in twins:
        node_ids = twin_group.get("node_ids", [])
        value = twin_group.get("value")
        sinks = twin_group.get("downstream_sinks", [])

        if len(node_ids) < 2 or value is None:
            continue

        # Derive a constant name from the sink field common prefix
        field_names = [s.get("field", "") for s in sinks]
        const_name = _derive_twin_constant_name(field_names, node_ids)
        if not const_name:
            continue

        # Build constant line
        const_value_repr = repr(value)
        comment = f"# COUPLED: {' + '.join(field_names)} kept equal by convention"
        constants_to_insert.append(f"{const_name} = {const_value_repr}  {comment}\n")

        # Find and rewrite each _node call by node_id
        for nid in node_ids:
            line_info = _find_node_call_line_with_range(source, str(nid))
            if line_info is None:
                continue
            call_line_idx, call_end_line_idx = line_info

            # Find the kwarg for 'value' or 'widget_0' and replace its literal
            call_lines = lines[call_line_idx:call_end_line_idx + 1]
            for i, cline in enumerate(call_lines):
                actual_idx = call_line_idx + i
                # Match value=<literal> or widget_0=<literal> (not already a name ref)
                new_cline = _replace_kwarg_literal(cline, const_name, value)
                if new_cline != cline:
                    replacements.append((actual_idx, actual_idx, new_cline))
                    break

            # Delete any trailing COUPLED comment lines after this call
            for j in range(call_end_line_idx + 1, min(call_end_line_idx + 4, len(lines))):
                stripped = lines[j].strip()
                if stripped.startswith("# COUPLED:") or stripped.startswith("# COUPLED "):
                    lines_to_delete.add(j)
                elif stripped.startswith("#") and "COUPLED" in stripped:
                    lines_to_delete.add(j)
                elif stripped and not stripped.startswith("#"):
                    break  # non-comment, non-blank line — stop

    if not constants_to_insert:
        return source

    # Insert constants before `def build(`
    result: list[str] = []
    inserted = False
    for i, line in enumerate(lines):
        if not inserted:
            stripped = line.strip()
            if stripped.startswith("def build(") or stripped == "def build():":
                # Insert blank line + constants
                result.append("\n")
                result.extend(constants_to_insert)
                inserted = True
        if i in lines_to_delete:
            continue
        if i in {r[0] for r in replacements}:
            # Find replacement for this line
            for r_idx, _, new_text in replacements:
                if r_idx == i:
                    result.append(new_text if new_text.endswith("\n") else new_text + "\n")
                    break
        else:
            result.append(line)

    return "".join(result)


def _derive_twin_constant_name(field_names: list[str], node_ids: list[str]) -> str:
    """Derive an UPPER_SNAKE constant name from sink field names."""
    # Extract the last component after '.' and strip trailing _N suffix
    import re as _re
    base_names: list[str] = []
    for fname in field_names:
        parts = fname.rsplit(".", 1)
        leaf = parts[-1] if len(parts) > 1 else fname
        # Strip trailing _\d+ suffix
        leaf = _re.sub(r"_\d+$", "", leaf)
        if leaf:
            base_names.append(leaf)

    if not base_names:
        return ""

    # Find common prefix
    prefix = base_names[0]
    for bn in base_names[1:]:
        while prefix and not bn.startswith(prefix):
            prefix = prefix[:-1]

    # Clean up trailing underscores
    prefix = prefix.rstrip("_")
    if not prefix or len(prefix) < 3:
        # Fallback: use first meaningful base name
        for bn in base_names:
            if len(bn) >= 3:
                prefix = bn
                break
        if not prefix:
            return ""

    # Convert to UPPER_SNAKE
    name = prefix.upper()
    # Prefix with "ANCHOR_" for clarity
    if not name.startswith("ANCHOR_"):
        name = f"ANCHOR_{name}"
    return name


def _replace_kwarg_literal(line: str, const_name: str, expected_value: Any) -> str:
    """Replace ``value=<literal>`` or ``widget_0=<literal>`` with ``value=<const_name>``,
    but only if the current literal matches *expected_value*."""
    import re as _re
    # Patterns for value= and widget_0=
    for kw in ("value", "widget_0"):
        pattern = _re.compile(
            r"(\b" + _re.escape(kw) + r"\s*=\s*)"
            + _re.escape(repr(expected_value))
            + r"(\s*[,)\n])"
        )
        m = pattern.search(line)
        if m:
            return line[:m.start(1)] + m.group(1) + const_name + m.group(2) + line[m.end(2):]

    return line


def _find_node_call_line_with_range(source: str, node_id: str) -> tuple[int, int] | None:
    """Return (start_line, end_line) 0-indexed for the _node() call with given node_id."""
    tree = ast.parse(source)
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        if len(stmt.value.args) < 3:
            continue
        id_arg = stmt.value.args[2]
        if isinstance(id_arg, ast.Constant) and str(id_arg.value) == node_id:
            start = stmt.value.lineno - 1  # 1-indexed → 0-indexed
            end = (getattr(stmt.value, "end_lineno", stmt.value.lineno) or stmt.value.lineno) - 1
            return (start, end)
    return None


# --------------------------------------------------------------------------- #
# v2.2: Branch selector → GUIDE_BRANCH + GUIDE_NODES (Item 6)                 #
# --------------------------------------------------------------------------- #

def _exec_branch_selector(
    source: str,
    findings: dict[str, Any],
    preferred_name: dict[str, str],
) -> str:
    """For branch_selector_groups findings, emit ``GUIDE_BRANCH`` constant and
    ``GUIDE_NODES`` dict, then rewrite the active branch reference on the sink
    node to use ``GUIDE_NODES[GUIDE_BRANCH].out("IMAGE")``.
    """
    groups = findings.get("findings", {}).get("branch_selector_groups", [])
    if not groups:
        return source

    import re as _re

    lines = source.splitlines(keepends=True)
    result: list[str] = []
    constants_inserted = False
    rewrites_done: set[int] = set()  # line indices already rewritten

    for group in groups:
        active_nid = str(group.get("active_branch_node_id", ""))
        alt_nids = [str(n) for n in group.get("alternative_branch_node_ids", [])]
        sink_nid = str(group.get("sink_node_id", ""))
        sink_input = group.get("sink_input", "image")

        if not active_nid or not sink_nid:
            continue

        # Derive mode labels from the suggested_comment
        comment_text = group.get("suggested_comment", "")
        active_mode = _extract_mode_label(comment_text, active_nid)
        if not active_mode:
            active_mode = _derive_mode_label(int(active_nid) if active_nid.isdigit() else active_nid, None)
            if not active_mode:
                continue

        # Map node_ids → variable names
        active_var = preferred_name.get(active_nid, "")
        alt_vars: list[tuple[str, str]] = []  # [(mode_label, var_name), ...]
        for alt_nid in alt_nids:
            mode = _extract_mode_label(comment_text, alt_nid)
            if not mode:
                # Try deriving from class type
                mode = _infer_mode_from_alt(alt_nid, preferred_name)
            if not mode:
                mode = alt_nid  # fallback to node_id
            var_name = preferred_name.get(alt_nid, "")
            if var_name:
                alt_vars.append((mode, var_name))

        if not active_var:
            continue

        # Build GUIDE_BRANCH constant
        all_modes = [active_mode] + [m for m, _ in alt_vars]
        branch_line = (
            f"GUIDE_BRANCH = {active_mode!r}"
            f"  # one of: {', '.join(repr(m) for m in all_modes)}\n"
        )

        # Build GUIDE_NODES dict
        node_entries = []
        for mode, vname in alt_vars:
            node_entries.append(f'    {mode!r}: {vname},')
        # Active branch also goes in the dict
        node_entries.append(f'    {active_mode!r}: {active_var},')
        # Sort entries by mode name for readability
        node_entries.sort()
        nodes_block = "GUIDE_NODES = {\n" + "\n".join(node_entries) + "\n}\n"

        if not constants_inserted:
            # Insert GUIDE_BRANCH and GUIDE_NODES INSIDE build() right BEFORE
            # the sink _node call (which uses GUIDE_NODES[GUIDE_BRANCH]).
            # The variables referenced by GUIDE_NODES must already be defined,
            # so we insert just before the sink node.
            constants_inserted = True

            # Find the sink node's line index BEFORE we modify the text
            sink_range = _find_node_call_line_with_range("".join(lines), sink_nid)
            if sink_range is not None:
                sink_line = sink_range[0]  # first line of the _node call
                # Scan backward from sink_line to find a blank line or section banner
                insert_idx = sink_line
                indent = "    "
                if insert_idx < len(lines):
                    line_at = lines[insert_idx]
                    indent = line_at[:len(line_at) - len(line_at.lstrip())]
                    if not indent:
                        indent = "    "

                # Insert GUIDE_BRANCH + GUIDE_NODES before the sink _node call
                new_lines = list(lines)
                new_lines.insert(insert_idx, "\n")
                new_lines.insert(insert_idx + 1, f"{indent}{branch_line.rstrip()}\n")
                new_lines.insert(insert_idx + 2, f"{indent}{nodes_block.rstrip()}\n")
                lines = new_lines
            else:
                # Fallback: insert at top of build()
                new_lines = list(lines)
                for i, line in enumerate(new_lines):
                    stripped = line.strip()
                    if stripped.startswith("def build(") or stripped == "def build():":
                        indent = "    "
                        new_lines.insert(i + 2, f"\n{indent}{branch_line.rstrip()}\n{indent}{nodes_block.rstrip()}\n")
                        break
                lines = new_lines

        # Rewrite the sink _node call's kwarg
        # Find the sink node call
        sink_line_info = _find_node_call_line_with_range("".join(lines), sink_nid)
        if sink_line_info is None:
            continue

        call_start, call_end = sink_line_info
        # Within the call, find the line containing `{sink_input}=<active_var>.out(...)`
        for j in range(call_start, call_end + 1):
            if j in rewrites_done:
                continue
            line_text = lines[j]
            # Match: image=<active_var>.out('...') or image=<active_var>.out(N)
            pattern = _re.compile(
                r"(\b" + _re.escape(sink_input) + r"\s*=\s*)"
                + _re.escape(active_var)
                + r"\.out\([^)]+\)"
            )
            m = pattern.search(line_text)
            if m:
                rewrites_done.add(j)
                new_ref = f"{sink_input}=GUIDE_NODES[GUIDE_BRANCH].out(\"IMAGE\")"
                lines[j] = line_text[:m.start()] + new_ref + line_text[m.end():]
                break

    if not constants_inserted:
        return source

    return "".join(lines)


def _extract_mode_label(comment: str, node_id: str) -> str | None:
    """Extract mode label from a BRANCH SELECTION comment like
    ``... node 5028 (canny) ...``."""
    import re as _re
    m = _re.search(_re.escape(node_id) + r"\s*\((\w+)\)", comment)
    if m:
        return m.group(1)
    return None


def _infer_mode_from_alt(node_id: str, preferred_name: dict[str, str]) -> str | None:
    """Infer a short mode label from a variable name like guide_pose_sized → pose."""
    name = preferred_name.get(node_id, "")
    if not name:
        return None
    # Strip common prefixes/suffixes
    for prefix in ("guide_", "resized_", "preprocessed_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    for suffix in ("_sized", "_resized", "_edges", "_map", "_preprocessed"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    if name and name not in ("image", "video", "input", "output"):
        return name
    return None


# --------------------------------------------------------------------------- #
# v2.2: Unwired primitive cleanup — control_mode deletion (Item 11)            #
# --------------------------------------------------------------------------- #

def _exec_unwired_primitive_cleanup(
    source: str,
    findings: dict[str, Any],
    preferred_name: dict[str, str],
) -> str:
    """Detect unwired primitives that are public inputs and add per-template
    report flags.  For the v2.2 sprint, this specifically handles
    ``control_mode`` (node_id 6000) in LTX.

    T1 confirmed zero Reigh dependencies on ``control_mode``, so it is safe
    to delete.  However, deletion would break the parity verify gates
    (register_input_preservation, unbound_inputs_parity) that compare
    original→candidate.  Full deletion is therefore deferred to v2.3.

    For v2.2 we ensure the annotation is prominent:
    - The PARAMS entry carries a ``# ⚠ DEAD: ...`` warning
    - The _node call carries a ``# UNUSED: ...`` comment
    - The register_input and READY_METADATA entries are preserved for
      backward compatibility and verify-gate parity.
    """
    # v2.2: Keep the annotations as-is from the base pipeline.
    # The per-template report flag is handled in the delta report (T12).
    # Full deletion is deferred to v2.3 corpus-wide re-migration.
    return source


# --------------------------------------------------------------------------- #
# v2.2: Factor repeated helpers (Item 13 / T8)                                #
# --------------------------------------------------------------------------- #

def _factor_repeated_helpers(source: str) -> str:
    """Detect groups of 3+ ``_node`` calls with the same class type *and* the
    same exact literal-default kwargs (excluding ``image``, ``width``,
    ``height``), then emit a local helper function and rewrite each callsite.

    The helper signature is::

        def _<snake_class>(wf, _id, <var_kwarg_1>, ..., **overrides):
            kwargs = dict(<literal_defaults>, <var_kwarg_1>=<var_kwarg_1>, ...)
            kwargs.update(overrides)
            return _node(wf, "<ClassName>", _id, **kwargs)

    Only families of 3+ calls sharing identical literal defaults are factored.
    If multiple distinct literal-default families exist for the same class
    (e.g. anchor resizes with ``mode="nearest-exact"`` vs guide resizes with
    ``mode="lanczos"``), separate helpers are emitted with disambiguating names.
    """
    tree = ast.parse(source)

    # ------------------------------------------------------------------ #
    # Step 1: Collect all _node() assignment calls                        #
    # ------------------------------------------------------------------ #
    @dataclass
    class _NodeCallRec:
        var_name: str
        class_type: str
        node_id: str
        line_start: int     # 0-indexed
        line_end: int       # 0-indexed (inclusive)
        kwargs: list[tuple[str, bool, str, ast.AST]]  # (name, is_literal, unparsed_val, ast_node)

    call_recs: list[_NodeCallRec] = []

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign):
            continue
        if not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if not isinstance(func, ast.Name) or func.id not in ("_node", "_at"):
            continue
        args = stmt.value.args
        if len(args) < 3:
            continue
        if not isinstance(args[1], ast.Constant):
            continue
        if not isinstance(args[2], ast.Constant):
            continue
        class_type = str(args[1].value)
        node_id = str(args[2].value)

        # Variable name from LHS
        var_name = ""
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                break
        if not var_name:
            continue

        line_start = stmt.value.lineno - 1  # 1-indexed → 0-indexed
        line_end = (getattr(stmt.value, "end_lineno", stmt.value.lineno) or stmt.value.lineno) - 1

        kwargs = []
        for kw in stmt.value.keywords:
            if kw.arg is None:
                continue
            is_literal = isinstance(kw.value, ast.Constant)
            unparsed = ast.unparse(kw.value) if not is_literal else repr(kw.value.value)
            kwargs.append((kw.arg, is_literal, unparsed, kw.value))

        call_recs.append(_NodeCallRec(var_name, class_type, node_id, line_start, line_end, kwargs))

    # ------------------------------------------------------------------ #
    # Step 2: Group by class_type, then by literal-kwarg signature        #
    # ------------------------------------------------------------------ #
    by_class: dict[str, list[_NodeCallRec]] = defaultdict(list)
    for cr in call_recs:
        by_class[cr.class_type].append(cr)

    # Map: (class_type, literal_kwarg_sig) → list of call_recs
    families: dict[tuple[str, tuple[tuple[str, str], ...]], list[_NodeCallRec]] = {}
    # Tracks whether a family is the primary (>=3) family for its class. Used by
    # naming logic so the primary family keeps the plain helper name and only
    # secondary variants get a disambiguating suffix.
    family_is_primary: dict[tuple[str, tuple[tuple[str, str], ...]], bool] = {}
    for class_type, class_calls in by_class.items():
        if len(class_calls) < 3:
            continue
        by_sig: dict[tuple[tuple[str, str], ...], list[_NodeCallRec]] = defaultdict(list)
        for cr in class_calls:
            sig = tuple(
                (kw[0], kw[2])  # (name, value_repr)
                for kw in cr.kwargs
                if kw[1]  # is_literal
            )
            by_sig[sig].append(cr)
        # Primary qualification: a family with >=3 calls is always a helper.
        has_primary = any(len(sc) >= 3 and s for s, sc in by_sig.items())
        for sig, sig_calls in by_sig.items():
            if not sig:
                continue
            # Primary threshold.
            if len(sig_calls) >= 3:
                families[(class_type, sig)] = sig_calls
                family_is_primary[(class_type, sig)] = True
                continue
            # Secondary threshold: emit a variant helper for any 2+ repeat once
            # the class already has a primary helper. This factors anchor-resize
            # / non-default-divisor variants that share a class with the main
            # helper but use a distinct literal-kwarg shape.
            if has_primary and len(sig_calls) >= 2:
                families[(class_type, sig)] = sig_calls
                family_is_primary[(class_type, sig)] = False

    if not families:
        return source

    # ------------------------------------------------------------------ #
    # Step 3: Generate helper definitions and replacement data            #
    # ------------------------------------------------------------------ #
    # Each entry: helper definition + replacement data
    @dataclass
    class _HelperPlan:
        helper_name: str
        class_type: str
        literal_kwargs: list[tuple[str, str]]
        var_kwarg_names: list[str]
        var_kwarg_order: list[str]
        calls: list

    plans: list[_HelperPlan] = []

    for (class_type, sig), sig_calls in families.items():
        # Determine variable kwargs (those NOT in the literal signature)
        literal_names: set[str] = {kw[0] for kw in sig}
        var_kwargs: dict[str, set[str]] = defaultdict(set)  # name → set of unparsed forms seen
        for cr in sig_calls:
            for kw_name, is_lit, unparsed_val, _ in cr.kwargs:
                if kw_name not in literal_names and not is_lit:
                    var_kwargs[kw_name].add(unparsed_val)

        # Try to establish a canonical order for variable kwargs based on
        # their appearance in the first call
        var_kwarg_order: list[str] = []
        seen = set()
        for kw_name, _, _, _ in sig_calls[0].kwargs:
            if kw_name not in literal_names and kw_name not in seen:
                var_kwarg_order.append(kw_name)
                seen.add(kw_name)

        # Generate helper name
        snake_class = _helper_name_for_class(class_type)
        # Determine if any sibling family exists for the same class.
        sibling_families = [k for k in families if k[0] == class_type]
        primary_for_class = [
            k for k in families if k[0] == class_type and family_is_primary.get(k)
        ]
        is_primary = family_is_primary.get((class_type, sig), False)
        if len(sibling_families) <= 1:
            # Single-family class — plain helper name.
            helper_name = f"_{snake_class}"
        elif is_primary and len(primary_for_class) == 1:
            # Exactly one primary family with secondary variants — keep the
            # primary plain and disambiguate variants only.
            helper_name = f"_{snake_class}"
        else:
            # Either multiple primary families OR a secondary variant — needs
            # a disambiguator. Use ``_anchor`` shorthand for the LTX anchor-
            # resize family (nearest-exact + crop), else fall back to the
            # generic disambiguator.
            disambig = _derive_family_disambiguator(sig, var_kwarg_order)
            helper_name = f"_{snake_class}_{disambig}"

        plans.append(_HelperPlan(
            helper_name=helper_name,
            class_type=class_type,
            literal_kwargs=[(kw[0], kw[1]) for kw in sig],
            var_kwarg_names=list(var_kwargs.keys()),
            var_kwarg_order=var_kwarg_order,
            calls=sig_calls,
        ))

    if not plans:
        return source

    # ------------------------------------------------------------------ #
    # Step 4: Build helper function source strings                        #
    # ------------------------------------------------------------------ #
    lines = source.splitlines(keepends=True)

    helper_blocks: list[str] = []
    for plan in plans:
        helper_lines: list[str] = []

        # Build kwargs dict entry for each literal default
        literal_entries: list[str] = []
        for name, val_repr in plan.literal_kwargs:
            literal_entries.append(f"{name}={val_repr}")

        # Build kwargs dict entries for variable kwargs
        var_entries: list[str] = []
        for vn in plan.var_kwarg_order:
            var_entries.append(f"{vn}={vn}")

        all_dict_entries = literal_entries + var_entries

        # Build function signature: (wf, _id, <var_kwargs>, **overrides)
        sig_params = ["wf", "_id"] + plan.var_kwarg_order + ["**overrides"]
        sig_str = ", ".join(sig_params)

        helper_lines.append(f"def {plan.helper_name}({sig_str}):\n")
        # kwargs = dict(...)
        dict_lines = ",\n                  ".join(all_dict_entries)
        helper_lines.append(f"    kwargs = dict({dict_lines})\n")
        helper_lines.append(f"    kwargs.update(overrides)\n")
        helper_lines.append(f'    return _node(wf, {plan.class_type!r}, _id, **kwargs)\n')

        helper_blocks.append("".join(helper_lines))

    # ------------------------------------------------------------------ #
    # Step 5: Insert helpers before build() and rewrite callsites          #
    # ------------------------------------------------------------------ #
    # Find build() insertion point
    build_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("def build(") or stripped == "def build():":
            build_idx = i
            break
    if build_idx is None:
        return source

    # Collect replacement info: (line_start, line_end, node_id, new_call_line)
    replacements: list[tuple[int, int, str, str]] = []
    for plan in plans:
        for cr in plan.calls:
            # Build the new call: var_name = helper_name(wf, "node_id", <var_args>)
            var_arg_strs = []
            # Build a map from var_kwarg_name to its unparsed value in this call
            var_map = {}
            for kw_name, is_lit, unparsed_val, _ in cr.kwargs:
                if kw_name in plan.var_kwarg_names:
                    var_map[kw_name] = unparsed_val
            for vn in plan.var_kwarg_order:
                if vn in var_map:
                    var_arg_strs.append(var_map[vn])
                else:
                    var_arg_strs.append("None")  # fallback

            # Preserve original indentation
            orig_indent = ""
            if cr.line_start < len(lines):
                orig_line = lines[cr.line_start]
                orig_indent = orig_line[:len(orig_line) - len(orig_line.lstrip())]

            new_call = f"{orig_indent}{cr.var_name} = {plan.helper_name}(wf, {cr.node_id!r}, {', '.join(var_arg_strs)})\n"
            replacements.append((cr.line_start, cr.line_end, cr.node_id, new_call))

    # Build result lines
    result: list[str] = []
    inserted = False
    lines_to_skip: set[int] = set()
    for r_start, r_end, _, _ in replacements:
        for j in range(r_start, r_end + 1):
            lines_to_skip.add(j)

    replacements_by_start: dict[int, str] = {r[0]: r[3] for r in replacements}

    for i, line in enumerate(lines):
        if not inserted and i >= build_idx:
            # Insert blank line + helpers before the first line after build()
            result.append("\n")
            for block in helper_blocks:
                result.append(block)
            result.append("\n")
            inserted = True

        if i in replacements_by_start:
            result.append(replacements_by_start[i])
            continue
        if i in lines_to_skip:
            continue

        result.append(line)

    # If build() was the last line (unlikely), insert at end
    if not inserted:
        result.append("\n")
        for block in helper_blocks:
            result.append(block)

    return "".join(result)


def _helper_name_for_class(class_type: str) -> str:
    """Derive a clean helper name from a class type.

    Strips trailing pack/version suffixes from snake_case names so that
    ``ImageResizeKJv2`` → ``image_resize`` instead of
    ``image_resize_k_jv2``.
    """
    snake = _snake_case(class_type)
    parts = snake.split("_")
    # Strip trailing parts that look like version/acronym noise:
    # contains a digit, or is a single lowercase letter (pack abbreviation)
    while len(parts) >= 3:
        last = parts[-1]
        if any(c.isdigit() for c in last) or (len(last) == 1 and last.islower()):
            parts.pop()
        else:
            break
    result = "_".join(parts)
    # If we stripped too much, fall back to the original
    return result if len(result) >= 5 else snake


def _derive_family_disambiguator(
    literal_kwargs: list[tuple[str, str]],
    _var_kwarg_order: list[str],
) -> str:
    """Derive a short disambiguating suffix for a helper family based on
    the most salient literal default that differs from other families."""
    kwargs_by_name = {name: val.strip("'\"") for name, val in literal_kwargs}
    # Recognised anchor-resize family (LTX uses this for first/last frame
    # endpoints — nearest-exact + crop with explicit pad/crop/divisor).
    if (
        kwargs_by_name.get("upscale_method") == "nearest-exact"
        and kwargs_by_name.get("keep_proportion") == "crop"
    ):
        return "anchor"
    # Use the upscale_method value as the most salient differentiator
    for name, val in literal_kwargs:
        if name in ("upscale_method", "mode", "keep_proportion"):
            # Strip quotes and dots
            clean = val.strip("'\"")
            if clean and clean not in ("image", "video", "width", "height"):
                return clean.replace("-", "_").replace(".", "_")
    # Fallback: use the first literal that has a non-boolean/non-numeric value
    for name, val in literal_kwargs:
        clean = val.strip("'\"")
        if clean and not clean.isdigit() and clean not in ("True", "False", "None"):
            return clean.replace("-", "_").replace(".", "_")[:20]
    return "variant"


# --------------------------------------------------------------------------- #
# v2.2 Phase-1 post-passes (Items B, C, D, E)                                 #
# --------------------------------------------------------------------------- #


def _byte_line_offsets(src_bytes: bytes) -> list[int]:
    """Per-line byte offsets, mirroring ``_compute_line_offsets`` for the
    bytes domain. AST col_offsets are UTF-8 byte counts, so non-ASCII spans
    must be edited over bytes to avoid drift."""
    offsets = [0]
    for i, b in enumerate(src_bytes):
        if b == 0x0A:  # \n
            offsets.append(i + 1)
    return offsets


def _looks_class_fallback(var_name: str) -> bool:
    """Detect variable names that fell back to the class-snake-id form
    (e.g. ``comfyswitchnode_2``, ``k_sampler_238_230``, ``c_l_i_p_vision_loader_49``).
    """
    if not var_name:
        return False
    # Names with a node-id suffix: _<digits>(_<digits>)+ or trailing _<digits>
    # that follow a snake-cased class name (heuristic: digit-bearing suffix
    # combined with a multi-token snake prefix).
    if re.search(r"_\d+(?:_\d+)+$", var_name):
        return True
    # Single-letter underscore-spam from snake_case of CamelCase acronyms
    # like ``c_l_i_p_...``, ``s_d_3_...``.
    if re.search(r"(?:^|_)[a-z](?:_[a-z]){2,}_", var_name):
        return True
    # raw lowercased class-only forms like ``comfyswitchnode_2``,
    # ``cliptextencode_2`` (snake of class with trailing _<int>)
    if re.search(r"^[a-z]{8,}_\d+$", var_name):
        return True
    # ``primitivefloat_2`` / ``primitiveint_2`` style
    if re.search(r"^primitive[a-z]+_\d+$", var_name):
        return True
    return False


def _parse_node_assigns(tree: ast.AST) -> list[dict[str, Any]]:
    """Return one record per top-level ``var = _node(...)`` or
    ``var = _helper(...)`` assignment inside ``build()``.

    Each record:
      var_name, class_type (None for helper), node_id, line, ast_call.
    """
    records: list[dict[str, Any]] = []
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        func = call.func
        var_name = None
        for tgt in stmt.targets:
            if isinstance(tgt, ast.Name):
                var_name = tgt.id
                break
        if not var_name:
            continue
        if isinstance(func, ast.Name) and func.id in ("_node", "_at"):
            if len(call.args) < 3:
                continue
            if not (isinstance(call.args[1], ast.Constant) and isinstance(call.args[2], ast.Constant)):
                continue
            records.append({
                "var": var_name,
                "class_type": str(call.args[1].value),
                "node_id": str(call.args[2].value),
                "kind": "node",
                "call": call,
            })
        elif isinstance(func, ast.Name) and func.id.startswith("_"):
            # helper call: _image_resize(wf, '5026', ...)
            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                records.append({
                    "var": var_name,
                    "class_type": None,
                    "node_id": str(call.args[1].value),
                    "kind": "helper",
                    "helper_name": func.id,
                    "call": call,
                })
    return records


def _rename_class_fallback_vars(source: str) -> str:
    """Rename any variable whose name fell back to a class-snake form into a
    role-aware name, derived from:

    - the input's ``register_input`` registration (PrimitiveInt/Float/Bool
      become the registered name, e.g. ``param_steps``, ``param_cfg``);
    - the downstream kwarg that consumes the variable (ComfySwitchNode picks
      up ``switch_<purpose>``, KSampler picks up sampler purpose);
    - positional ordering within class (CLIPTextEncode positive/negative).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    records = _parse_node_assigns(tree)
    var_by_name = {r["var"]: r for r in records}

    # Map node_id → list of register_input names
    reg_by_nid: dict[str, list[str]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register_input":
            if len(node.args) >= 3 and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args[:3]):
                name, nid, _field = node.args[0].value, node.args[1].value, node.args[2].value
                reg_by_nid[nid].append(name)

    # Build downstream-consumer map: for each var, list the (kwarg_name, downstream_class)
    consumers: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in records:
        call = r["call"]
        # downstream class (None for helper)
        downstream_class = r["class_type"]
        for kw in call.keywords:
            if kw.arg is None:
                continue
            # Match `<var>.out(...)` references on the RHS
            v = kw.value
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "out":
                if isinstance(v.func.value, ast.Name):
                    src_var = v.func.value.id
                    consumers[src_var].append((kw.arg, downstream_class or r.get("helper_name") or "?"))

    rename: dict[str, str] = {}
    used: set[str] = set(var_by_name.keys())

    def _claim(base: str) -> str:
        cand = base
        i = 2
        while cand in used or cand in rename.values():
            cand = f"{base}_{i}"
            i += 1
        used.add(cand)
        return cand

    # First pass: rename Primitive* whose node_id has a register_input name.
    for r in records:
        var = r["var"]
        cls = r["class_type"]
        nid = r["node_id"]
        if not cls:
            continue
        if not _looks_class_fallback(var):
            continue
        if cls in ("PrimitiveInt", "PrimitiveFloat", "PrimitiveString", "PrimitiveBoolean", "INTConstant"):
            reg_names = reg_by_nid.get(nid)
            if reg_names:
                target = f"param_{reg_names[0]}" if cls != "PrimitiveBoolean" else f"use_{reg_names[0]}"
                rename[var] = _claim(target)
                continue
            # Else, derive from downstream kwarg if unique
            cs = consumers.get(var, [])
            kwargs_seen = {kw for kw, _ in cs}
            if len(kwargs_seen) == 1:
                kw = next(iter(kwargs_seen))
                if cls == "PrimitiveBoolean":
                    rename[var] = _claim(f"use_{kw}")
                else:
                    rename[var] = _claim(f"param_{kw}")

    # Second pass: ComfySwitchNode purpose
    for r in records:
        var = r["var"]
        if r["class_type"] != "ComfySwitchNode":
            continue
        if not _looks_class_fallback(var):
            continue
        cs = consumers.get(var, [])
        kwargs_seen = [kw for kw, _ in cs]
        purpose = None
        if kwargs_seen:
            # First downstream kwarg name as purpose.
            # Map common kwargs to friendlier short names.
            kw = kwargs_seen[0]
            purpose_map = {"steps": "steps", "cfg": "cfg", "model": "model", "lora": "lora", "denoise": "denoise"}
            purpose = purpose_map.get(kw, kw)
        if purpose:
            rename[var] = _claim(f"switch_{purpose}")
        else:
            rename[var] = _claim("switch")

    # Third pass: CLIPTextEncode pos/neg disambiguation
    clip_text_vars = [r for r in records if r["class_type"] == "CLIPTextEncode"]
    if len(clip_text_vars) >= 2:
        # Determine positive/negative by downstream sampler kwarg
        for r in clip_text_vars:
            var = r["var"]
            cs = consumers.get(var, [])
            roles = {kw for kw, _ in cs}
            target = None
            if "positive" in roles and "negative" not in roles:
                target = "positive_prompt"
            elif "negative" in roles and "positive" not in roles:
                target = "negative_prompt"
            if target is None:
                continue
            if var == target:
                continue
            rename[var] = _claim(target)

    # Fourth pass: catch-all class-fallback rename via ROLE_NAMES (or class-based heuristic).
    for r in records:
        var = r["var"]
        cls = r["class_type"]
        if not cls:
            continue
        if var in rename:
            continue
        if not _looks_class_fallback(var):
            continue
        base = ROLE_NAMES.get(cls)
        if not base:
            # Derive a clean snake-case base from the class (strip digit/word
            # suffixes). For CLIPVisionLoader → ``clip_vision``,
            # ModelSamplingSD3 → ``model_sampling_sd3``.
            base = _snake_case(cls)
            # Collapse single-letter acronym tokens: c_l_i_p_vision_loader →
            # clip_vision_loader; s_d_3 → sd3.
            base = re.sub(r"(?:^|_)((?:[a-z]_){2,}[a-z](?:_\d+)?)", lambda m: "_" + m.group(1).replace("_", ""), base).strip("_")
        # Handle name collisions within the same class.
        same_class = [rr for rr in records if rr["class_type"] == cls]
        if len(same_class) > 1:
            # Suffix by ordinal among this class.
            idx = same_class.index(r) + 1
            base = f"{base}_{idx}"
        rename[var] = _claim(base)

    if not rename:
        return source

    return _ast_rename_variables(source, rename)


def _annotate_comfyswitch_branches(source: str) -> str:
    """For each ComfySwitchNode call, emit a BRANCH SELECTION comment that
    names the switch variable, the literal boolean value (if resolved as a
    PrimitiveBoolean constant), and the active branch's source node id."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    records = _parse_node_assigns(tree)
    by_var = {r["var"]: r for r in records}
    by_nid = {r["node_id"]: r for r in records}

    # Boolean literal lookup: var → bool
    bool_value: dict[str, bool] = {}
    bool_is_registered: dict[str, bool] = {}
    reg_names_by_nid: dict[str, list[str]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register_input":
            if len(node.args) >= 3 and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args[:3]):
                reg_names_by_nid[node.args[1].value].append(node.args[0].value)
    for r in records:
        if r["class_type"] != "PrimitiveBoolean":
            continue
        for kw in r["call"].keywords:
            if kw.arg == "value" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
                bool_value[r["var"]] = kw.value.value
        if reg_names_by_nid.get(r["node_id"]):
            bool_is_registered[r["var"]] = True

    annotations: list[tuple[int, str]] = []  # (line_no_1idx, comment line)

    for r in records:
        if r["class_type"] != "ComfySwitchNode":
            continue
        call = r["call"]
        switch_var = None
        on_true_var = None
        on_false_var = None
        for kw in call.keywords:
            if kw.arg == "switch" and isinstance(kw.value, ast.Call) and isinstance(kw.value.func, ast.Attribute):
                if isinstance(kw.value.func.value, ast.Name):
                    switch_var = kw.value.func.value.id
            elif kw.arg == "on_true" and isinstance(kw.value, ast.Call) and isinstance(kw.value.func, ast.Attribute):
                if isinstance(kw.value.func.value, ast.Name):
                    on_true_var = kw.value.func.value.id
            elif kw.arg == "on_false" and isinstance(kw.value, ast.Call) and isinstance(kw.value.func, ast.Attribute):
                if isinstance(kw.value.func.value, ast.Name):
                    on_false_var = kw.value.func.value.id
        if not switch_var:
            continue
        switch_rec = by_var.get(switch_var)
        if not switch_rec or switch_rec["class_type"] != "PrimitiveBoolean":
            continue
        on_true_id = by_var.get(on_true_var, {}).get("node_id") if on_true_var else None
        on_false_id = by_var.get(on_false_var, {}).get("node_id") if on_false_var else None
        # Build a concise comment. Format:
        # # BRANCH SELECTION: <switch_var>=<value> → <active_branch_id> (other: <inactive_id>)
        if switch_var in bool_is_registered:
            ann = (
                f"# BRANCH SELECTION: {switch_var} (registered input) picks on_true={on_true_id} "
                f"or on_false={on_false_id}."
            )
        elif switch_var in bool_value:
            val = bool_value[switch_var]
            active_id = on_true_id if val else on_false_id
            inactive_id = on_false_id if val else on_true_id
            ann = (
                f"# BRANCH SELECTION: {switch_var}={val} → uses {active_id} (other: {inactive_id})."
            )
        else:
            ann = (
                f"# BRANCH SELECTION: dynamic {switch_var} picks on_true={on_true_id} "
                f"or on_false={on_false_id}."
            )
        # Emit immediately above the _node() call.
        annotations.append((call.lineno, ann))

    if not annotations:
        return source

    # Insert lines into source.
    lines = source.splitlines(keepends=True)
    result: list[str] = []
    insert_at: dict[int, list[str]] = defaultdict(list)
    for lineno, comment in annotations:
        # Determine indent from the target line.
        idx = lineno - 1
        if idx < 0 or idx >= len(lines):
            continue
        target_line = lines[idx]
        indent = target_line[: len(target_line) - len(target_line.lstrip())]
        insert_at[idx].append(indent + comment + "\n")

    for i, line in enumerate(lines):
        if i in insert_at:
            for c in insert_at[i]:
                result.append(c)
        result.append(line)
    return "".join(result)


_MODEL_ROLE_BY_DIR = {
    "diffusion_models": "unet",
    "unet": "unet",
    "vae": "vae",
    "text_encoders": "text_encoder",
    "clip": "text_encoder",
    "clip_vision": "clip_vision",
    "loras": "lora",
    "checkpoints": "checkpoint",
    "controlnet": "controlnet",
    "ipadapter": "ipadapter",
    "style_models": "style_model",
}


def _hoist_model_files(source: str) -> str:
    """Single-source model filenames. Scan ``READY_METADATA['model_assets']``
    for ``(name, path_in_repo)`` pairs, infer a role from the path, emit a
    ``MODEL_FILES = {...}`` constant after ``READY_REQUIREMENTS``, and rewrite
    both the metadata `name` and matching `_node()` kwargs (``*_name``) to
    reference the dict.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    # 1. Find READY_METADATA assignment and walk model_assets.
    assets: list[tuple[str, str, ast.Constant]] = []  # (name, path_in_repo, name_const_node)
    metadata_node: ast.Assign | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "READY_METADATA":
                    metadata_node = node
    if metadata_node is None or not isinstance(metadata_node.value, ast.Dict):
        return source
    md = metadata_node.value
    for k, v in zip(md.keys, md.values):
        if not (isinstance(k, ast.Constant) and k.value == "model_assets"):
            continue
        if not isinstance(v, ast.List):
            continue
        for elt in v.elts:
            name_const: ast.Constant | None = None
            path_val: str | None = None
            if isinstance(elt, ast.Call):
                # ModelAsset(name='...', path_in_repo='...', ...)
                for kw in elt.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        name_const = kw.value
                    elif kw.arg == "path_in_repo" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        path_val = kw.value.value
            elif isinstance(elt, ast.Dict):
                # Dict-literal form: {'name': '...', 'subdir': '...', ...}
                for sub_k, sub_v in zip(elt.keys, elt.values):
                    if not isinstance(sub_k, ast.Constant):
                        continue
                    if sub_k.value == "name" and isinstance(sub_v, ast.Constant) and isinstance(sub_v.value, str):
                        name_const = sub_v
                    elif sub_k.value in ("path_in_repo", "subdir") and isinstance(sub_v, ast.Constant) and isinstance(sub_v.value, str):
                        path_val = sub_v.value
            if name_const is not None:
                assets.append((name_const.value, path_val or "", name_const))

    if not assets:
        return source

    # 2. Assign roles.
    role_for_name: dict[str, str] = {}
    role_counts: dict[str, int] = defaultdict(int)
    assigned: dict[str, str] = {}  # role-key -> filename
    for filename, path, _node in assets:
        parts = path.split("/") if path else []
        role: str | None = None
        # path like models/diffusion_models/foo.safetensors → pick second token.
        for token in parts:
            if token in _MODEL_ROLE_BY_DIR:
                role = _MODEL_ROLE_BY_DIR[token]
                break
        if role is None:
            role = f"model_{len(role_for_name) + 1}"
        role_counts[role] += 1
        key = role if role_counts[role] == 1 else f"{role}_{role_counts[role]}"
        role_for_name[filename] = key
        assigned[key] = filename

    # 3. Build the MODEL_FILES dict source.
    entries = ",\n    ".join(f'{k!r}: {v!r}' for k, v in assigned.items())
    model_files_src = f"MODEL_FILES: dict[str, str] = {{\n    {entries},\n}}\n\n"

    # 4. Collect span replacements (operate over UTF-8 bytes — col_offset is in bytes):
    #    (a) every assets name_const → MODEL_FILES["<key>"]
    #    (b) every _node call kwarg ending in `_name` whose literal == a known filename → MODEL_FILES["<key>"]
    src_bytes = source.encode("utf-8")
    byte_line_offsets = _byte_line_offsets(src_bytes)
    replacements: list[tuple[int, int, bytes]] = []  # (byte_start, byte_end, replacement)

    def span(node: ast.AST) -> tuple[int, int]:
        start = byte_line_offsets[node.lineno - 1] + node.col_offset
        end = byte_line_offsets[(node.end_lineno or node.lineno) - 1] + (node.end_col_offset or 0)
        return start, end

    for filename, _, name_const in assets:
        key = role_for_name[filename]
        s, e = span(name_const)
        replacements.append((s, e, f'MODEL_FILES[{key!r}]'.encode("utf-8")))

    # Walk _node calls for kwargs ending in _name with literal that matches.
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Call):
            continue
        func = stmt.func
        if not (isinstance(func, ast.Name) and func.id in ("_node", "_at")):
            continue
        for kw in stmt.keywords:
            if not kw.arg or not kw.arg.endswith("_name"):
                continue
            if not isinstance(kw.value, ast.Constant) or not isinstance(kw.value.value, str):
                continue
            fname = kw.value.value
            if fname in role_for_name:
                key = role_for_name[fname]
                s, e = span(kw.value)
                replacements.append((s, e, f'MODEL_FILES[{key!r}]'.encode("utf-8")))

    if not replacements:
        return source

    replacements.sort(key=lambda x: -x[0])
    arr = bytearray(src_bytes)
    for s, e, rep in replacements:
        arr[s:e] = rep
    new_source = arr.decode("utf-8")

    # 5. Insert MODEL_FILES block before READY_METADATA so the dict-literal
    #    rewrites can resolve MODEL_FILES[...] at import time.
    lines = new_source.splitlines(keepends=True)
    insert_at: int | None = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("READY_METADATA"):
            insert_at = i
            break
    if insert_at is None:
        return new_source
    lines.insert(insert_at, model_files_src + "\n")
    return "".join(lines)


def _ensure_params_block(source: str) -> str:
    """When the codemod produced no ``PARAMS`` block, create one from common
    knobs: register_input defaults, KSampler seed/steps/cfg/denoise,
    CLIPTextEncode text, and resolution/length on latent/video nodes."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    has_params = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "PARAMS":
                    has_params = True
                    break
        elif isinstance(node, ast.AnnAssign):
            tgt = node.target
            if isinstance(tgt, ast.Name) and tgt.id == "PARAMS":
                has_params = True
    if has_params:
        return source

    records = _parse_node_assigns(tree)
    by_var = {r["var"]: r for r in records}

    # Group definition: name → (group_label, literal_repr)
    group_order = ["text", "sampling", "resolution", "seeds", "misc"]
    entries: list[tuple[str, str, str, ast.AST]] = []  # (group, key, repr, ast_value_node)

    used_keys: set[str] = set()

    def _add(group: str, key: str, val_node: ast.AST) -> str:
        nonlocal used_keys
        if key in used_keys:
            i = 2
            while f"{key}_{i}" in used_keys:
                i += 1
            key = f"{key}_{i}"
        used_keys.add(key)
        entries.append((group, key, ast.unparse(val_node), val_node))
        return key

    # register_input(name, nid, field, default=<literal>) - record the
    # (node_id, field) of each registered input so we can skip duplicate
    # PARAMS entries when the same literal also appears as a kwarg later.
    registered_nid_field: dict[tuple[str, str], str] = {}
    rep_targets: list[tuple[ast.Constant, str]] = []  # (literal node, key)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register_input":
            if len(node.args) < 3:
                continue
            name_arg = node.args[0]
            if not (isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str)):
                continue
            name = name_arg.value
            nid_arg = node.args[1]
            field_arg = node.args[2]
            if not (isinstance(nid_arg, ast.Constant) and isinstance(field_arg, ast.Constant)):
                continue
            registered_nid_field[(nid_arg.value, field_arg.value)] = name
            # 4th positional arg is the "current value" literal.
            if len(node.args) >= 4 and isinstance(node.args[3], ast.Constant):
                val = node.args[3]
                group = "text" if "prompt" in name or "text" in name else "seeds" if name == "seed" else "sampling" if name in ("steps", "cfg", "denoise", "fps") else "misc"
                key = _add(group, name, val)
                rep_targets.append((val, key))

    # KSampler seeds/steps/cfg/denoise + CLIPTextEncode text + EmptyLatent width/height/batch + RandomNoise noise_seed
    sampler_keys = {"KSampler", "KSamplerAdvanced", "RandomNoise", "SamplerCustomAdvanced"}
    text_keys = {"CLIPTextEncode", "TextEncode"}
    latent_keys = {"EmptySD3LatentImage", "EmptyLTXVLatentVideo", "EmptyHunyuanLatentVideo", "EmptyLatentImage", "EmptyLatentVideo"}

    # Also track kwarg-literal -> existing PARAMS key, so we can replace
    # additional sites of the same logical value (e.g. width on the latent
    # node) with the existing PARAMS reference rather than creating a dup.
    alias_targets: list[tuple[ast.Constant, str]] = []
    for r in records:
        cls = r.get("class_type")
        if not cls:
            continue
        call = r["call"]
        node_id = r["node_id"]
        for kw in call.keywords:
            if not kw.arg or not isinstance(kw.value, ast.Constant):
                continue
            v = kw.value
            kw_name = kw.arg
            # If this kwarg is already covered by a register_input on the
            # same (node_id, field), substitute it with the same PARAMS key
            # (no new entry, but rewrite the literal site).
            if (node_id, kw_name) in registered_nid_field:
                alias_targets.append((v, registered_nid_field[(node_id, kw_name)]))
                continue
            if cls in sampler_keys and kw_name in ("seed", "noise_seed", "steps", "cfg", "denoise", "sampler_name", "scheduler"):
                group = "seeds" if "seed" in kw_name else "sampling"
                _add(group, kw_name, v)
            elif cls in text_keys and kw_name == "text":
                key_base = "negative_prompt" if "negative" in r["var"] else ("prompt" if "positive" in r["var"] or "prompt_embedding" in r["var"] else "text")
                _add("text", key_base, v)
            elif cls in latent_keys and kw_name in ("width", "height", "batch_size", "length", "fps", "frame_rate"):
                _add("resolution", kw_name, v)

    if not entries:
        return source

    # Build PARAMS block source. Emit group banners only for groups with >=2
    # entries to keep the dict compact on small templates.
    block_lines: list[str] = ["PARAMS: dict[str, object] = {\n"]
    for group in group_order:
        group_entries = [e for e in entries if e[0] == group]
        if not group_entries:
            continue
        if len(group_entries) >= 2:
            block_lines.append(f"    # — {group} —\n")
        for _, key, rep, _ in group_entries:
            block_lines.append(f"    {key!r}: {rep},\n")
    block_lines.append("}\n\n")
    params_src = "".join(block_lines)

    # Replace literal spans with PARAMS["..."] references. ``ast`` reports
    # ``col_offset`` in UTF-8 bytes, so we splice over the source-as-bytes and
    # decode at the end. This is the only safe way to handle non-ASCII
    # literals (e.g. Chinese negative prompts) without span drift.
    src_bytes = source.encode("utf-8")
    byte_line_offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for _, key, _, val_node in entries:
        if not hasattr(val_node, "end_col_offset"):
            continue
        s = byte_line_offsets[val_node.lineno - 1] + val_node.col_offset
        e = byte_line_offsets[(val_node.end_lineno or val_node.lineno) - 1] + (val_node.end_col_offset or 0)
        repls.append((s, e, f'PARAMS[{key!r}]'.encode("utf-8")))
    # Alias rewrites: kwarg literals that map to an existing PARAMS key.
    for val_node, key in alias_targets:
        if not hasattr(val_node, "end_col_offset"):
            continue
        s = byte_line_offsets[val_node.lineno - 1] + val_node.col_offset
        e = byte_line_offsets[(val_node.end_lineno or val_node.lineno) - 1] + (val_node.end_col_offset or 0)
        repls.append((s, e, f'PARAMS[{key!r}]'.encode("utf-8")))
    repls.sort(key=lambda x: -x[0])
    arr = bytearray(src_bytes)
    for s, e, r in repls:
        arr[s:e] = r
    new_src = arr.decode("utf-8")

    # Insert PARAMS block. Prefer just before `def build(`.
    lines = new_src.splitlines(keepends=True)
    insert_idx: int | None = None
    for i, line in enumerate(lines):
        if line.startswith("def build("):
            insert_idx = i
            break
    if insert_idx is None:
        # Append after READY_METADATA.
        for i, line in enumerate(lines):
            if line.lstrip().startswith("READY_METADATA"):
                insert_idx = i + 1
                break
    if insert_idx is None:
        return new_src
    lines.insert(insert_idx, params_src)
    return "".join(lines)


def _expr_uses_params(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"PARAMS", "PRIVATE_KNOBS"}
    ):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
    return None


def _top_level_assignment_ranges(tree: ast.Module, names: set[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for stmt in tree.body:
        target_names: set[str] = set()
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    target_names.add(target.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target_names.add(stmt.target.id)
        if target_names & names:
            ranges.append((stmt.lineno, stmt.end_lineno or stmt.lineno))
    return ranges


def _remove_top_level_assignments(source: str, names: set[str]) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    remove = _top_level_assignment_ranges(tree, names)
    if not remove:
        return source
    lines = source.splitlines(keepends=True)
    drop: set[int] = set()
    for start, end in remove:
        drop.update(range(start, end + 1))
        if end < len(lines) and not lines[end].strip():
            drop.add(end + 1)
    return "".join(line for idx, line in enumerate(lines, start=1) if idx not in drop)


def _rewrite_ready_requirements_refs(source: str) -> str:
    """Rewrite dangling v2.2 READY_REQUIREMENTS subscripts to v2.4 metadata."""
    return re.sub(
        r"READY_REQUIREMENTS\[(?P<quote>['\"])(?P<key>[^'\"]+)(?P=quote)\]",
        r'READY_METADATA["requirements"]["\g<key>"]',
        source,
    )


def _rewrite_legacy_workflow_method_names(source: str) -> str:
    return source.replace(".removenode(", ".remove_node(")


def _collect_params_literal_map(tree: ast.AST) -> dict[str, Any]:
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        value = stmt.value
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id in {"PARAMS", "PRIVATE_KNOBS"} for target in targets):
            continue
        if not isinstance(value, ast.Dict):
            return {}
        out: dict[str, Any] = {}
        for key_node, val_node in zip(value.keys, value.values):
            if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
                continue
            ok, literal = _literal_from_ast(val_node)
            if ok:
                out[key_node.value] = literal
        return out
    return {}


def _literal_or_params_default(node: ast.AST, params: dict[str, Any]) -> Any:
    param_key = _expr_uses_params(node)
    if param_key is not None and param_key in params:
        return params[param_key]
    ok, literal = _literal_from_ast(node)
    return literal if ok else ast.unparse(node)


def _node_field_literal_defaults(tree: ast.AST, params: dict[str, Any]) -> dict[tuple[str, str], Any]:
    defaults: dict[tuple[str, str], Any] = {}
    id_sidecar = _extract_id_sidecar(tree) if isinstance(tree, ast.Module) else {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _call_name(node.func)
        if func_name not in {"_node", "_at"}:
            continue
        if len(node.args) < 3:
            continue
        id_arg = node.args[1] if func_name == "_at" else node.args[2]
        node_id = _literal_node_id(id_arg, id_sidecar)
        if node_id is None:
            continue
        for kw in node.keywords:
            if kw.arg is None:
                continue
            value = _literal_or_params_default(kw.value, params)
            if not isinstance(value, str) or not value.endswith(".node.inputs['text']"):
                defaults[(node_id, kw.arg)] = value
    return defaults


def _registered_input_specs(source: str, tree: ast.AST) -> OrderedDict[str, dict[str, Any]]:
    params = _collect_params_literal_map(tree)
    node_defaults = _node_field_literal_defaults(tree, params)
    specs: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register_input"
        ):
            continue
        if len(node.args) < 3:
            continue
        name_node, node_id_node, field_node = node.args[:3]
        if not (
            isinstance(name_node, ast.Constant)
            and isinstance(name_node.value, str)
            and isinstance(node_id_node, ast.Constant)
            and isinstance(node_id_node.value, str)
            and isinstance(field_node, ast.Constant)
            and isinstance(field_node.value, str)
        ):
            continue
        original_name = name_node.value
        name = _canonical_input_name(original_name)
        value_node = node.args[3] if len(node.args) >= 4 else None
        default: Any = None
        for kw in node.keywords:
            if kw.arg == "default":
                default = _literal_or_params_default(kw.value, params)
                break
        else:
            if value_node is not None:
                default = _literal_or_params_default(value_node, params)
        if (
            isinstance(default, str)
            and ".node.inputs[" in default
            and (node_id_node.value, field_node.value) in node_defaults
        ):
            default = node_defaults[(node_id_node.value, field_node.value)]
        elif default in (None, 0) and (node_id_node.value, field_node.value) in node_defaults:
            default = node_defaults[(node_id_node.value, field_node.value)]
        spec: dict[str, Any] = {
            "node": node_id_node.value,
            "field": field_node.value,
            "default": default,
            "type": "STRING",
            "required": False,
            "aliases": (),
            "description": _canonical_description(name),
            "media_semantics": None,
        }
        for kw in node.keywords:
            if kw.arg in {"type", "required", "aliases", "media_semantics"}:
                spec[kw.arg] = _literal_or_params_default(kw.value, params)
        if isinstance(spec.get("aliases"), list):
            spec["aliases"] = tuple(spec["aliases"])
        if original_name != name:
            aliases = tuple(spec.get("aliases") or ())
            if original_name not in aliases:
                spec["aliases"] = aliases + (original_name,)
        if spec.get("type") is None:
            spec["type"] = "STRING"
        specs[name] = spec
    if specs:
        return specs
    for name, spec in _collect_public_input_specs(source).items():
        specs[name] = {
            "node": spec.get("node", ""),
            "field": spec.get("field", ""),
            "default": spec.get("default"),
            "type": spec.get("type") or "STRING",
            "required": bool(spec.get("required", False)),
            "aliases": tuple(spec.get("aliases") or ()),
            "description": _canonical_description(name),
            "media_semantics": spec.get("media_semantics"),
        }
    return specs


def _collect_model_assets(tree: ast.AST) -> OrderedDict[str, dict[str, Any]]:
    def prefer_runtime_literals(models: OrderedDict[str, dict[str, Any]]) -> OrderedDict[str, dict[str, Any]]:
        normalized_to_key = {
            str(model.get("filename", "")).replace("\\", "/"): key
            for key, model in models.items()
        }
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str) and "\\" in node.value):
                continue
            key = normalized_to_key.get(node.value.replace("\\", "/"))
            if key is not None:
                models[key]["filename"] = node.value
        return models

    v23_models: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == "MODELS" for target in targets):
            continue
        if not isinstance(stmt.value, ast.Dict):
            continue
        for key_node, val_node in zip(stmt.value.keys, stmt.value.values):
            if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
                continue
            if not (isinstance(val_node, ast.Call) and _call_name(val_node.func) in {"ModelAsset", "templates.ModelAsset", "vibecomfy.templates.ModelAsset"}):
                continue
            filename = _input_spec_value(val_node, 0, "filename", "")
            url = _input_spec_value(val_node, 1, "url", "")
            subdir = _input_spec_value(val_node, 2, "subdir", "")
            target_path = _input_spec_value(val_node, 3, "target_path")
            if isinstance(filename, str) and filename:
                v23_models[key_node.value] = {
                    "filename": filename,
                    "url": str(url or ""),
                    "subdir": str(subdir or ""),
                    "target_path": target_path,
                }
        if v23_models:
            return prefer_runtime_literals(v23_models)

    literal_lists: dict[str, list[dict[str, Any]]] = {}
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        ok, literal = _literal_from_ast(stmt.value)
        if ok and isinstance(literal, list) and all(isinstance(item, dict) for item in literal):
            literal_lists[targets[0].id] = literal

    raw_models: list[dict[str, Any]] = []
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == "READY_REQUIREMENTS" for target in targets):
            continue
        if not isinstance(stmt.value, ast.Dict):
            continue
        for key_node, val_node in zip(stmt.value.keys, stmt.value.values):
            if isinstance(key_node, ast.Constant) and key_node.value == "models":
                if isinstance(val_node, ast.List):
                    for elt in val_node.elts:
                        ok, literal = _literal_from_ast(elt)
                        if ok and isinstance(literal, dict):
                            raw_models.append(literal)
                elif isinstance(val_node, ast.Name):
                    raw_models.extend(literal_lists.get(val_node.id, []))
                break
    if not raw_models:
        for stmt in getattr(tree, "body", []):
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            if not any(isinstance(target, ast.Name) and target.id == "READY_METADATA" for target in targets):
                continue
            if not isinstance(stmt.value, ast.Dict):
                continue
            for key_node, val_node in zip(stmt.value.keys, stmt.value.values):
                if isinstance(key_node, ast.Constant) and key_node.value == "model_assets":
                    if isinstance(val_node, ast.List):
                        for elt in val_node.elts:
                            ok, literal = _literal_from_ast(elt)
                            if ok and isinstance(literal, dict):
                                raw_models.append(literal)
                    elif isinstance(val_node, ast.Name):
                        raw_models.extend(literal_lists.get(val_node.id, []))
                    break
    models: OrderedDict[str, dict[str, Any]] = OrderedDict()
    counts: dict[str, int] = defaultdict(int)
    for model in raw_models:
        filename = model.get("name") or model.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        subdir = str(model.get("subdir") or "")
        stem = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower()).strip("_") or "model"
        key = stem[:42].strip("_") or "model"
        counts[key] += 1
        if counts[key] > 1:
            key = f"{key}_{counts[key]}"
        models[key] = {
            "filename": filename,
            "url": str(model.get("url") or ""),
            "subdir": subdir,
            "target_path": model.get("target_path"),
        }
    return prefer_runtime_literals(models)


def _collect_model_asset_assignment_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        name = targets[0].id
        if not name.endswith("_MODEL_ASSETS"):
            continue
        ok, literal = _literal_from_ast(stmt.value)
        if ok and isinstance(literal, list) and all(isinstance(item, dict) for item in literal):
            names.add(name)
    return names


def _collect_top_level_literal(tree: ast.AST, name: str, default: Any = None) -> Any:
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        ok, literal = _literal_from_ast(stmt.value)
        return literal if ok else default
    return default


def _collect_metadata_literal(tree: ast.AST) -> dict[str, Any]:
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == "READY_METADATA" for target in targets):
            continue
        if _is_ready_metadata_build_call(stmt.value):
            out: dict[str, Any] = {}
            for kw in stmt.value.keywords:
                if kw.arg in {"inputs", "models"}:
                    continue
                if kw.arg == "output_prefix" and isinstance(kw.value, ast.Name):
                    out["output_prefix"] = _collect_top_level_literal(tree, kw.value.id, "")
                    continue
                ok_value, value = _literal_from_ast(kw.value)
                if ok_value:
                    out[kw.arg or ""] = value
            if "ready_template" not in out and "template_id" in out:
                out["ready_template"] = out["template_id"]
            if "task" not in out and "capability" in out:
                out["task"] = out["capability"]
            return out
        if isinstance(stmt.value, ast.Dict):
            ok, literal = _literal_from_ast(stmt.value)
            if ok and isinstance(literal, dict):
                return literal
            out: dict[str, Any] = {}
            for key_node, value_node in zip(stmt.value.keys, stmt.value.values):
                if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
                    continue
                if key_node.value in {"model_assets", "unbound_inputs"}:
                    continue
                ok_value, value = _literal_from_ast(value_node)
                if ok_value:
                    out[key_node.value] = value
            return out
    return {}


def _collect_requirements_extras(tree: ast.AST) -> dict[str, Any]:
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == "READY_REQUIREMENTS" for target in targets):
            continue
        ok, literal = _literal_from_ast(stmt.value)
        if ok and isinstance(literal, dict):
            return {k: v for k, v in literal.items() if k != "models"}
    return {}


def _get_vibecomfy_version() -> str:
    """Read VibeComfy version from pyproject.toml."""
    try:
        version_path = REPO_ROOT / "pyproject.toml"
        content = version_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        return match.group(1) if match else "0.0.0"
    except Exception:
        return "0.0.0"


def _get_comfy_core_info() -> dict[str, Any]:
    """Return cached ComfyUI metadata, falling back to best-effort import."""
    cached = Path(__file__).resolve().parents[1] / "vibecomfy" / "comfy_metadata.json"
    if cached.exists():
        try:
            data = json.loads(cached.read_text(encoding="utf-8"))
            version = data.get("version")
            commit = data.get("commit")
            tested_at = data.get("tested_at") or data.get("captured_at")
            if version and commit:
                return {
                    "version": version,
                    "tested_at": tested_at,
                    "commit": commit,
                    "status": data.get("status", "cached"),
                }
        except Exception:
            pass
    try:
        import comfy
        version = getattr(comfy, "__version__", None)
        commit = getattr(comfy, "__git_commit__", None)
        if version:
            return {
                "version": version,
                "tested_at": version,
                "commit": commit,
                "status": "discovered",
            }
    except ImportError:
        pass
    return {"version": None, "tested_at": None, "commit": None, "status": "unavailable"}


def _derive_custom_node_packs_from_source(source: str) -> list[str]:
    """Extract node class strings from source, map to known packs, return sorted pack names.

    Only classes found in the node-pack catalog are included; Comfy core classes are excluded.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    # Build class-to-pack map
    class_to_pack: dict[str, str] = {}
    for pack in get_known_node_packs():
        for cls_name in pack.classes:
            class_to_pack[cls_name] = pack.name
    # Collect all class strings from node(wf, "ClassName", ...) calls
    seen_packs: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _call_name(node.func)
        if func_name not in {"node", "_node", "_at", "vibecomfy.templates.node",
                              "vibecomfy.templates._at", "templates.node", "templates._at"}:
            continue
        if len(node.args) < 2:
            continue
        ok, class_name = _literal_from_ast(node.args[1])
        if not ok or not isinstance(class_name, str):
            continue
        pack_name = class_to_pack.get(class_name)
        if pack_name is not None:
            seen_packs.add(pack_name)
    return sorted(seen_packs)


def _collect_bind_output_call(tree: ast.AST) -> ast.Call | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) == "bind_output":
            return node
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) in {"finalize", "templates.finalize", "vibecomfy.templates.finalize"}:
            return node
    return None


def _collect_model_files_map(tree: ast.AST) -> dict[str, str]:
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        if not any(isinstance(target, ast.Name) and target.id == "MODEL_FILES" for target in targets):
            continue
        ok, literal = _literal_from_ast(stmt.value)
        if ok and isinstance(literal, dict):
            return {str(k): str(v) for k, v in literal.items() if isinstance(k, str)}
    return {}


def _model_key_for_loader_literal(filename: str, field: str, class_type: str, used: set[str]) -> str:
    stem = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower()).strip("_") or "model"
    field_lower = field.lower()
    class_lower = class_type.lower()
    if "gemma" in stem and field_lower.startswith("clip_name"):
        base = "gemma_clip"
    elif "clip" in field_lower or "clip" in class_lower:
        base = stem if stem.endswith("_clip") else f"{stem}_clip"
    elif "vae" in field_lower or "vae" in class_lower:
        base = stem if stem.endswith("_vae") else f"{stem}_vae"
    elif "unet" in field_lower or "unet" in class_lower:
        base = stem if stem.endswith("_unet") else f"{stem}_unet"
    elif "ckpt" in field_lower or "checkpoint" in class_lower:
        base = stem if stem.endswith("_checkpoint") else f"{stem}_checkpoint"
    else:
        base = stem
    base = base[:42].strip("_") or "model"
    key = base
    suffix = 2
    while key in used:
        key = f"{base}_{suffix}"
        suffix += 1
    return key


def _subdir_for_loader_model(field: str, class_type: str) -> str:
    field_lower = field.lower()
    class_lower = class_type.lower()
    if "ckpt" in field_lower or "checkpoint" in class_lower:
        return "checkpoints"
    if "clip_vision" in class_lower:
        return "clip_vision"
    if "clip" in field_lower or "clip" in class_lower:
        return "text_encoders"
    if "unet" in field_lower or "unet" in class_lower:
        return "diffusion_models"
    if "vae" in field_lower or "vae" in class_lower:
        return "vae"
    return ""


def _extend_models_from_loader_kwargs(
    tree: ast.AST,
    models: OrderedDict[str, dict[str, Any]],
) -> None:
    """Add loader filename literals missed by authored model metadata."""
    filename_to_key = {str(model.get("filename", "")): key for key, model in models.items()}
    used = set(models)
    for record in _collect_v23_node_records(tree):
        class_type = str(record.get("class_type", ""))
        fields = _LOADER_MODEL_FIELDS.get(class_type)
        if not fields:
            continue
        kwargs = record.get("kwargs") or {}
        for field in fields:
            filename = kwargs.get(field)
            if not isinstance(filename, str) or not filename:
                continue
            if filename in filename_to_key:
                continue
            key = _model_key_for_loader_literal(filename, field, class_type, used)
            used.add(key)
            filename_to_key[filename] = key
            models[key] = {
                "filename": filename,
                "url": "",
                "subdir": _subdir_for_loader_model(field, class_type),
                "target_path": None,
            }


def _collect_v23_node_records(tree: ast.AST) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    id_sidecar = _extract_id_sidecar(tree) if isinstance(tree, ast.Module) else {}
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        if _call_name(call.func) not in {"_node", "_at"} or len(call.args) < 3:
            continue
        func_name = _call_name(call.func)
        class_arg = call.args[2] if func_name == "_at" else call.args[1]
        id_arg = call.args[1] if func_name == "_at" else call.args[2]
        ok_cls, class_type = _literal_from_ast(class_arg)
        node_id = _literal_node_id(id_arg, id_sidecar)
        if not (ok_cls and isinstance(class_type, str) and isinstance(node_id, str)):
            continue
        var_name = None
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                break
        kwargs: dict[str, Any] = {}
        kw_params: dict[str, str] = {}
        fields: set[str] = set()
        for kw in call.keywords:
            if kw.arg is None:
                continue
            fields.add(kw.arg)
            ok_value, value = _literal_from_ast(kw.value)
            if ok_value:
                kwargs[kw.arg] = value
            elif (
                isinstance(kw.value, ast.Subscript)
                and isinstance(kw.value.value, ast.Name)
                and kw.value.value.id in {"PARAMS", "PRIVATE_KNOBS"}
                and isinstance(kw.value.slice, ast.Constant)
                and isinstance(kw.value.slice.value, str)
            ):
                kw_params[kw.arg] = kw.value.slice.value
        records.append({
            "var": var_name,
            "class_type": class_type,
            "node_id": node_id,
            "kwargs": kwargs,
            "kw_params": kw_params,
            "fields": fields,
        })
    return records


def _input_type_for_value(field: str, value: Any) -> str:
    if field in {"image", "video", "audio"}:
        return field.upper()
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int) and not isinstance(value, bool):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    return "STRING"


def _put_public_spec(
    specs: OrderedDict[str, dict[str, Any]],
    name: str,
    *,
    node: str,
    field: str,
    default: Any,
    description: str,
    aliases: tuple[str, ...] = (),
) -> None:
    if name in specs:
        spec = specs[name]
        existing_aliases = tuple(spec.get("aliases") or ())
        merged_aliases = tuple(dict.fromkeys([*existing_aliases, *aliases]))
        if merged_aliases:
            spec["aliases"] = merged_aliases
        spec["description"] = _canonical_description(name)
        return
    specs[name] = {
        "node": node,
        "field": field,
        "default": default,
        "type": _input_type_for_value(field, default),
        "required": False,
        "aliases": aliases,
        "description": _canonical_description(name) if name in _CANONICAL_DESCRIPTIONS else description,
        "media_semantics": field if field in {"image", "video", "audio"} else None,
    }


def _apply_pilot_public_surface(
    specs: OrderedDict[str, dict[str, Any]],
    tree: ast.AST,
    params: dict[str, Any],
) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    """Add pilot-specific public inputs and variable names derived from node IDs."""
    records = _collect_v23_node_records(tree)
    rewrites: dict[tuple[str, str], str] = {}
    var_renames: dict[str, str] = {}
    has_wan_image_to_video = any(r["class_type"] == "WanImageToVideo" for r in records)

    # qwen_image_2512: expose the LoRA branch selector and use intentful names.
    if any(r["class_type"] == "LoraLoaderModelOnly" for r in records):
        for r in records:
            if r["class_type"] != "PrimitiveBoolean":
                continue
            default = r["kwargs"].get("value", True)
            _put_public_spec(
                specs,
                "use_lora",
                node=r["node_id"],
                field="value",
                default=default,
                description="Enables the Lightning LoRA branch when true.",
            )
            rewrites[(r["node_id"], "value")] = "use_lora"
            if r.get("var"):
                var_renames[str(r["var"])] = "use_lora"
            break
        for r in records:
            var = r.get("var")
            if r["class_type"] == "PrimitiveInt":
                if r["node_id"].endswith(":225") and var:
                    var_renames[str(var)] = "lora_steps"
                elif r["node_id"].endswith(":224") and var:
                    var_renames[str(var)] = "base_steps"
            elif r["class_type"] == "PrimitiveFloat":
                if r["node_id"].endswith(":218") and var:
                    var_renames[str(var)] = "lora_cfg"
                elif r["node_id"].endswith(":223") and var:
                    var_renames[str(var)] = "base_cfg"
                elif r["node_id"].endswith(":105") and var:
                    var_renames[str(var)] = "lora_cfg"
                elif r["node_id"].endswith(":107") and var:
                    var_renames[str(var)] = "base_cfg"
            if r["class_type"] == "PrimitiveInt":
                if r["node_id"].endswith(":103") and var:
                    var_renames[str(var)] = "lora_steps"
                elif r["node_id"].endswith(":106") and var:
                    var_renames[str(var)] = "base_steps"

    for r in records:
        var = r.get("var")
        if not var:
            continue
        class_type = str(r["class_type"])
        node_id = str(r["node_id"])
        if class_type == "EmptyAceStep1.5LatentAudio":
            var_renames[str(var)] = "empty_audio_latent"
        elif class_type == "TextEncodeAceStepAudio1.5":
            var_renames[str(var)] = "positive_conditioning"
        elif class_type == "ConditioningZeroOut" and node_id == "47":
            var_renames[str(var)] = "negative_conditioning"
        elif class_type == "VAEDecodeAudio":
            var_renames[str(var)] = "decoded_audio"
        elif class_type == "SaveAudioMP3":
            var_renames[str(var)] = "save_audio"
        elif class_type == "TextEncodeQwenImageEdit" and node_id.endswith(":76"):
            var_renames[str(var)] = "positive_edit_conditioning"
        elif class_type == "TextEncodeQwenImageEdit" and node_id.endswith(":77"):
            var_renames[str(var)] = "negative_edit_conditioning"
        elif class_type == "VAEDecode" and str(var) == "decoded_image" and has_wan_image_to_video:
            var_renames[str(var)] = "decoded_frames"

    # wan_i2v: promote core generation controls from the latent/sampler nodes.
    for r in records:
        if r["class_type"] == "WanImageToVideo":
            for field in ("width", "height", "length"):
                if field in r["kwargs"]:
                    _put_public_spec(
                        specs,
                        field,
                        node=r["node_id"],
                        field=field,
                        default=r["kwargs"][field],
                        description=f"Controls generated video {field}.",
                    )
                    rewrites[(r["node_id"], field)] = field
        elif r["class_type"] == "KSampler":
            for field in ("cfg", "sampler_name"):
                if field in r["kwargs"]:
                    default = r["kwargs"][field]
                elif r.get("kw_params", {}).get(field) in params:
                    default = params[str(r["kw_params"][field])]
                else:
                    continue
                _put_public_spec(
                    specs,
                    field,
                    node=r["node_id"],
                    field=field,
                    default=default,
                    description=f"Controls sampler {field.replace('_', ' ')}.",
                )
                rewrites[(r["node_id"], field)] = field

    if has_wan_image_to_video and "fps" in specs:
        spec = specs.pop("fps")
        aliases = tuple(spec.get("aliases") or ())
        if "fps" not in aliases:
            aliases = aliases + ("fps",)
        spec["aliases"] = aliases
        spec["description"] = "Controls output playback frame rate."
        specs["output_fps"] = spec
        rewrites[(spec["node"], spec["field"])] = "output_fps"

    # LTX first/last-frame control: expose the refine seed as a real public input.
    if any(r["class_type"] == "LTXAddVideoICLoRAGuide" for r in records):
        for r in records:
            if r["class_type"] == "RandomNoise" and r["node_id"] == "15":
                default = r["kwargs"].get("noise_seed", 42)
                _put_public_spec(
                    specs,
                    "seed_refine",
                    node=r["node_id"],
                    field="noise_seed",
                    default=default,
                    description="Refine-pass noise seed; finish-pass uses seed.",
                )
                rewrites[(r["node_id"], "noise_seed")] = "seed_refine"
                break

    return rewrites, var_renames


def _rename_public_spec(
    specs: OrderedDict[str, dict[str, Any]],
    old: str,
    new: str,
    *,
    alias: str | None = None,
) -> None:
    if old not in specs or old == new:
        return
    spec = specs.pop(old)
    aliases = tuple(spec.get("aliases") or ())
    if old not in aliases:
        aliases = aliases + (old,)
    if alias and alias not in aliases:
        aliases = aliases + (alias,)
    aliases = tuple(item for item in aliases if item != new)
    spec["aliases"] = aliases
    spec["description"] = _canonical_description(new)
    specs[new] = spec


def _canonicalize_public_specs(
    specs: OrderedDict[str, dict[str, Any]],
    records: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, str]:
    """Apply v2.3.1 pilot public-input vocabulary and return old->new names."""
    renames: dict[str, str] = {}
    class_types = {str(r["class_type"]) for r in records}

    def rename(old: str, new: str, alias: str | None = None) -> None:
        if old not in specs:
            return
        _rename_public_spec(specs, old, new, alias=alias)
        renames[old] = new

    rename("frames", "length", "frames")
    if "WanImageToVideo" in class_types:
        rename("image", "start_image", "image")
        rename("input_image", "start_image", "image")
    if "TextEncodeQwenImageEdit" in class_types:
        rename("image", "source_image", "image")
        rename("input_image", "source_image", "image")
    if "LTXAddVideoICLoRAGuide" in class_types:
        rename("input_image_45", "start_image", "image")
        rename("input_image_47", "end_image")
        rename("input_video", "control_video")
        rename("param_string", "control_mode")
        rename("prompt_embedding_11", "negative_prompt", "negative")
        rename("param_int_2078", "length", "frames")
        rename("param_int_2080", "width")
        rename("param_int_2079", "height")
        rename("param_float_2076", "output_fps", "fps")
        rename("strength", "guide_strength", "strength")

    if "EmptyAceStep1.5LatentAudio" in class_types and "seed_2" not in specs:
        for record in records:
            if record["class_type"] == "KSampler" and record["node_id"] == "3":
                default = record["kwargs"].get("seed", params.get("seed_2"))
                if default is None:
                    continue
                _put_public_spec(
                    specs,
                    "seed_2",
                    node=record["node_id"],
                    field="seed",
                    default=default,
                    description=_canonical_description("seed_2"),
                    aliases=("noise_seed",),
                )
                break

    for name, spec in specs.items():
        spec["description"] = _canonical_description(name)
        if name in {"start_image", "end_image", "source_image"}:
            spec["media_semantics"] = "image"
        elif name == "control_video":
            spec["media_semantics"] = "video"
        elif name in {"prompt", "negative_prompt", "lyrics", "tags"}:
            spec["media_semantics"] = "text"
    return renames


def _kw_literal(call: ast.Call, name: str, default: Any = None) -> Any:
    for kw in call.keywords:
        if kw.arg == name:
            ok, literal = _literal_from_ast(kw.value)
            return literal if ok else ast.unparse(kw.value)
    return default


def _bind_output_node_id(call: ast.Call | None) -> str:
    if call is None:
        return ""
    if len(call.args) >= 2:
        ok, literal = _literal_from_ast(call.args[1])
        if ok and isinstance(literal, str):
            return literal
    return str(_kw_literal(call, "node_id", _kw_literal(call, "output_node", "")))


def _render_model_block(models: OrderedDict[str, dict[str, Any]]) -> str:
    if not models:
        return "MODELS = {}\n\n"
    lines = ["MODELS = {\n"]
    for key, model in models.items():
        lines.append(f"    {key!r}: ModelAsset(\n")
        lines.append(f"        filename={model['filename']!r},\n")
        lines.append(f"        url={model['url']!r},\n")
        lines.append(f"        subdir={model['subdir']!r},\n")
        if model.get("target_path"):
            lines.append(f"        target_path={model['target_path']!r},\n")
        hf_meta = _hf_metadata_for_url(str(model.get("url") or ""))
        if hf_meta.get("sha256"):
            lines.append(f"        sha256={hf_meta['sha256']!r},\n")
        elif hf_meta.get("status") == "gated":
            lines.append("        gated=True,\n")
        if hf_meta.get("hf_revision") and hf_meta.get("hf_revision") != "gated":
            lines.append(f"        hf_revision={hf_meta['hf_revision']!r},\n")
        if hf_meta.get("size_bytes") is not None:
            lines.append(f"        size_bytes={hf_meta['size_bytes']!r},\n")
        if hf_meta.get("status") == "gated":
            lines.append(f"        # gated: {hf_meta.get('repo_id', 'unknown')}\n")
        lines.append("    ),\n")
    lines.append("}\n\n")
    return "".join(lines)


_HF_METADATA_CACHE: dict[str, Any] | None = None


def _hf_metadata_for_url(url: str) -> dict[str, Any]:
    global _HF_METADATA_CACHE
    if _HF_METADATA_CACHE is None:
        cache = Path(__file__).resolve().parents[1] / "out" / "cache" / "hf_metadata.json"
        try:
            _HF_METADATA_CACHE = json.loads(cache.read_text(encoding="utf-8")).get("urls", {})
        except Exception:
            _HF_METADATA_CACHE = {}
    value = _HF_METADATA_CACHE.get(_canonical_hf_url(url)) or _HF_METADATA_CACHE.get(url)
    return dict(value) if isinstance(value, dict) else {}


def _canonical_hf_url(url: str) -> str:
    match = re.match(r"https://huggingface\\.co/(.+?)/resolve/([^/]+)/(.+)", url)
    if not match:
        return url
    repo_id, revision, filename = match.groups()
    return f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"


def _input_default_constant_name(name: str) -> str:
    return f"_{re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_')}_DEFAULT"


def _derived_media_semantics(input_type: Any) -> str | None:
    return {
        "IMAGE": "image",
        "VIDEO": "video",
        "AUDIO": "audio",
        "MASK": "mask",
    }.get(str(input_type or "").upper())


def _public_input_default_exprs(specs: OrderedDict[str, dict[str, Any]]) -> tuple[str, dict[str, str]]:
    constants: list[str] = []
    default_exprs: dict[str, str] = {}
    for name, spec in specs.items():
        default = spec.get("default")
        if isinstance(default, str) and len(default) > 100:
            const_name = _input_default_constant_name(name)
            default_exprs[name] = const_name
            constants.append(f'{const_name} = """{default}"""\n\n')
    return "".join(constants), default_exprs


def _render_public_inputs_block(
    specs: OrderedDict[str, dict[str, Any]],
    *,
    include_default_constants: bool = True,
) -> str:
    if not specs:
        return "PUBLIC_INPUTS = {}\n\n"
    constants, default_exprs = _public_input_default_exprs(specs)
    lines = ([constants] if include_default_constants else []) + ["PUBLIC_INPUTS = {\n"]
    for name, spec in specs.items():
        default_expr = default_exprs.get(name, repr(spec.get("default")))
        args = [
            f"node={spec['node']!r}",
            f"field={spec['field']!r}",
            f"default={default_expr}",
            f"type={spec.get('type', 'STRING')!r}",
        ]
        if spec.get("required"):
            args.append("required=True")
        aliases = spec.get("aliases") or ()
        if aliases:
            args.append(f"aliases={tuple(aliases)!r}")
        if spec.get("description"):
            args.append(f"description={spec['description']!r}")
        media_semantics = spec.get("media_semantics")
        if media_semantics and media_semantics != _derived_media_semantics(spec.get("type")):
            args.append(f"media_semantics={spec['media_semantics']!r}")
        lines.append(f"    {name!r}: InputSpec({', '.join(args)}),\n")
    lines.append("}\n\n")
    return "".join(lines)


def _render_edit_guide(specs: OrderedDict[str, dict[str, Any]]) -> str:
    if not specs:
        return 'EDIT_GUIDE = ""\n\n'
    guide_lines = ["Public inputs:"]
    for name, spec in specs.items():
        guide_lines.append(f"- {name}: {spec.get('description') or f'Controls {name}.'}")
    return f"EDIT_GUIDE = {chr(10).join(guide_lines)!r}\n\n"


def _render_ready_blocks(
    metadata: dict[str, Any],
    requirement_extras: dict[str, Any],
    output_prefix: Any,
) -> str:
    template_id = metadata.get("workflow_template") or metadata.get("ready_template") or ""
    capability = metadata.get("capability") or "workflow"
    provenance_keys = {
        "source_role",
        "source_workflow",
        "approach",
        "runtime_variant",
        "smoke_resolution",
    }
    provenance = {
        key: metadata[key]
        for key in provenance_keys
        if metadata.get(key) is not None
    }
    if metadata.get("provenance") is not None:
        existing = metadata["provenance"]
        if isinstance(existing, dict):
            provenance = {**existing, **provenance}
        else:
            provenance["note"] = existing
    extras = {
        k: v
        for k, v in metadata.items()
        if k not in {
            "ready_template",
            "workflow_template",
            "template_id",
            "capability",
            "unbound_inputs",
            "model_assets",
            "output_prefix",
            "provenance",
            *provenance_keys,
        }
        and v is not None
    }
    lines: list[str] = []
    source_workflow = metadata.get("source_workflow")
    if source_workflow and isinstance(source_workflow, str):
        source_path = REPO_ROOT / source_workflow
        try:
            sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
            lines.append(f"# ported from {source_workflow} (sha256: {sha})\n")
        except Exception:
            pass
    lines.append("READY_METADATA = ReadyMetadata.build(\n")
    lines.append(f"    template_id={template_id!r},\n")
    lines.append(f"    capability={capability!r},\n")
    lines.append("    inputs=PUBLIC_INPUTS,\n")
    lines.append("    models=MODELS,\n")
    lines.append(f"    output_prefix={output_prefix!r},\n")
    # Filter out entries whose values are empty lists/containers (e.g. {'custom_nodes': []})
    filtered_reqs = {k: v for k, v in requirement_extras.items() if v}
    if filtered_reqs:
        lines.append(f"    requirements={filtered_reqs!r},\n")
    if provenance:
        lines.append(f"    provenance={provenance!r},\n")
    for key, value in extras.items():
        lines.append(f"    {key}={value!r},\n")
    lines.append(")\n\n")
    return "".join(lines)


def _rewrite_params_refs_to_public_inputs(source: str, public_name_by_param: dict[str, str]) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        key = _expr_uses_params(node)
        if key is None:
            continue
        public_name = public_name_by_param.get(key)
        if public_name is not None:
            replacement = f'PUBLIC_INPUTS[{public_name!r}].default'
        else:
            replacement = f'PRIVATE_KNOBS[{key!r}]'
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[(node.end_lineno or node.lineno) - 1] + (node.end_col_offset or 0)
        repls.append((start, end, replacement.encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _inline_private_knobs(source: str, private_knobs: dict[str, Any]) -> str:
    """Replace PRIVATE_KNOBS['key'] references with their literal values."""
    if not private_knobs:
        return source
    for key, value in private_knobs.items():
        pattern = f"PRIVATE_KNOBS[{key!r}]"
        replacement = repr(value)
        source = source.replace(pattern, replacement)
    return source


def _rewrite_model_file_refs(source: str, model_files: dict[str, str], models: OrderedDict[str, dict[str, Any]]) -> str:
    if not model_files or not models:
        return source
    filename_to_model_key = {model["filename"]: key for key, model in models.items()}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "MODEL_FILES"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            continue
        filename = model_files.get(node.slice.value)
        model_key = filename_to_model_key.get(filename or "")
        if not model_key:
            continue
        replacement = f"MODELS[{model_key!r}].filename"
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[(node.end_lineno or node.lineno) - 1] + (node.end_col_offset or 0)
        repls.append((start, end, replacement.encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _rewrite_public_input_literal_refs(source: str, specs: OrderedDict[str, dict[str, Any]]) -> str:
    """Replace node kwarg literals that duplicate PUBLIC_INPUTS defaults."""
    if not specs:
        return source
    target_by_node_field = {
        (str(spec["node"]), str(spec["field"])): name
        for name, spec in specs.items()
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) not in {"_node", "_at"} or len(node.args) < 3:
            continue
        ok_id, node_id = _literal_from_ast(node.args[2])
        if not ok_id or not isinstance(node_id, str):
            continue
        for kw in node.keywords:
            if kw.arg is None:
                continue
            public_name = target_by_node_field.get((node_id, kw.arg))
            if public_name is None:
                continue
            spec = specs[public_name]
            ok_value, value = _literal_from_ast(kw.value)
            if not ok_value or value != spec.get("default"):
                continue
            start = offsets[kw.value.lineno - 1] + kw.value.col_offset
            end = offsets[(kw.value.end_lineno or kw.value.lineno) - 1] + (kw.value.end_col_offset or 0)
            repls.append((start, end, f"PUBLIC_INPUTS[{public_name!r}].default".encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _rewrite_model_literal_refs(source: str, models: OrderedDict[str, dict[str, Any]]) -> str:
    """Replace model filename literals with MODELS[...] references."""
    if not models:
        return source
    filename_to_model_key: dict[str, str] = {}
    for key, model in models.items():
        filename = str(model.get("filename", ""))
        filename_to_model_key[filename] = key
        filename_to_model_key[filename.replace("/", "\\")] = key
        filename_to_model_key[filename.replace("\\", "/")] = key
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        model_key = filename_to_model_key.get(node.value)
        if not model_key:
            continue
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[(node.end_lineno or node.lineno) - 1] + (node.end_col_offset or 0)
        repls.append((start, end, f"MODELS[{model_key!r}].filename".encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _rewrite_filename_prefix_literals(source: str, output_prefix: Any) -> str:
    if not isinstance(output_prefix, str) or not output_prefix:
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "filename_prefix"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == output_prefix
            ):
                start = offsets[kw.value.lineno - 1] + kw.value.col_offset
                end = offsets[(kw.value.end_lineno or kw.value.lineno) - 1] + (kw.value.end_col_offset or 0)
                repls.append((start, end, b"OUTPUT_PREFIX"))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _rewrite_node_kwarg_refs(source: str, rewrites: dict[tuple[str, str], str]) -> str:
    if not rewrites:
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) not in {"_node", "_at"} or len(node.args) < 3:
            continue
        ok_id, node_id = _literal_from_ast(node.args[2])
        if not ok_id or not isinstance(node_id, str):
            continue
        for kw in node.keywords:
            if kw.arg is None or (node_id, kw.arg) not in rewrites:
                continue
            if not hasattr(kw.value, "lineno"):
                continue
            public_name = rewrites[(node_id, kw.arg)]
            start = offsets[kw.value.lineno - 1] + kw.value.col_offset
            end = offsets[(kw.value.end_lineno or kw.value.lineno) - 1] + (kw.value.end_col_offset or 0)
            repls.append((start, end, f"PUBLIC_INPUTS[{public_name!r}].default".encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _rewrite_public_input_key_refs(source: str, renames: dict[str, str]) -> str:
    for old, new in renames.items():
        source = source.replace(f"PUBLIC_INPUTS[{old!r}]", f"PUBLIC_INPUTS[{new!r}]")
        source = source.replace(f'PUBLIC_INPUTS["{old}"]', f'PUBLIC_INPUTS["{new}"]')
    return source


def _normalize_named_out_calls(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for call in ast.walk(tree):
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "out"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        ):
            continue
        value = call.args[0].value
        normalized = value.strip().replace(" ", "_").upper()
        if normalized == value:
            continue
        arg = call.args[0]
        start = offsets[arg.lineno - 1] + arg.col_offset
        end = offsets[(arg.end_lineno or arg.lineno) - 1] + (arg.end_col_offset or 0)
        repls.append((start, end, repr(normalized).encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _apply_ltx_pilot_improvements(source: str) -> str:
    """Apply LTX-specific v2.3 readability fixes after generic restructuring."""
    if "LTXAddVideoICLoRAGuide" not in source or "LTXVAudioVAEDecode" not in source:
        return source

    import re as _re

    source = _re.sub(
        r"(?:ANCHOR_STRENGTH = 0\.8[^\n]*\n)?"
        r"CONTROL_RESOLUTION = 256\n"
        r"# Step count = list length \(currently \d+ steps refine\)\.\n"
        r"REFINE_SIGMAS = [^\n]+\n"
        r"# Step count = list length \(currently \d+ steps finish\)\.\n"
        r"FINISH_SIGMAS = [^\n]+\n\n"
        r"def anchor_strength_pair\(wf, value\):\n"
        r"    first_strength = _node\(wf, \"PrimitiveFloat\", \"2110\", value=value\)\n"
        r"    last_strength = _node\(wf, \"PrimitiveFloat\", \"2108\", value=value\)\n"
        r"    assert first_strength\.node\.inputs\[\"value\"\] == last_strength\.node\.inputs\[\"value\"\]\n"
        r"    return first_strength, last_strength\n+",
        "",
        source,
    )
    source = source.replace(
        "    _control_mode_marker = _node(wf, \"PrimitiveString\", \"6000\", value='canny')\n"
        "    # UNUSED: no downstream consumers — this is a label only, runtime no-op.\n",
        "    _control_mode_marker = _node(wf, \"PrimitiveString\", \"6000\", value='canny')\n",
    )
    if "'control_mode': InputSpec" not in source:
        source = source.replace(
            "    'control_video': InputSpec(node='5001', field='video', default='ltx_smoke_guide.mp4', type='STRING', description='Controls control video.'),\n",
            "    'control_video': InputSpec(node='5001', field='video', default='ltx_smoke_guide.mp4', type='STRING', description='Controls control video.'),\n"
            "    'control_mode': InputSpec(node='6000', field='value', default='canny', type='STRING', description='Selects the IC-LoRA guide branch: canny, raw, pose, or depth.'),\n",
            1,
        )
        source = source.replace(
            "- control_video: Controls control video.\\n",
            "- control_video: Controls control video.\\n- control_mode: Selects the IC-LoRA guide branch: canny, raw, pose, or depth.\\n",
            1,
        )
    source = source.replace(
        "    # Preserved for source graph parity; branch selection is the private GUIDE_BRANCH constant below.\n"
        "    _control_mode_marker = _node(wf, \"PrimitiveString\", \"6000\", value='canny')\n",
        "    control_mode = _node(wf, \"PrimitiveString\", \"6000\", value=PUBLIC_INPUTS['control_mode'].default)\n",
    )

    refine_match = _re.search(r'ManualSigmas", "215", sigmas=("[^"]+")', source)
    finish_match = _re.search(r'ManualSigmas", "216", sigmas=("[^"]+")', source)
    refine_sigmas = refine_match.group(1) if refine_match else '"1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"'
    finish_sigmas = finish_match.group(1) if finish_match else '"0.85, 0.7250, 0.4219, 0.0"'
    refine_steps = len([part for part in refine_sigmas.strip('"').split(",") if part.strip()])
    finish_steps = len([part for part in finish_sigmas.strip('"').split(",") if part.strip()])

    constants_block = (
        "ANCHOR_STRENGTH = 0.8\n"
        "CONTROL_RESOLUTION = 256\n"
        f"# Step count = list length (currently {refine_steps} steps refine).\n"
        f"REFINE_SIGMAS = {refine_sigmas}\n"
        f"# Step count = list length (currently {finish_steps} steps finish).\n"
        f"FINISH_SIGMAS = {finish_sigmas}\n\n"
        "def anchor_strength_pair(wf, value):\n"
        "    first_strength = _node(wf, \"PrimitiveFloat\", \"2110\", value=value)\n"
        "    last_strength = _node(wf, \"PrimitiveFloat\", \"2108\", value=value)\n"
        "    assert first_strength.node.inputs[\"value\"] == last_strength.node.inputs[\"value\"]\n"
        "    return first_strength, last_strength\n"
    )
    source = _re.sub(
        r"ANCHOR_STRENGTH = 0\.8[^\n]*\n",
        constants_block,
        source,
        count=1,
    )

    source = source.replace(
        "def _image_resize_anchor(wf, _id, height, image, width, **overrides):",
        "def _image_resize_anchor(wf, _id, *, width, height, image, **overrides):",
    )
    source = source.replace(
        "start_resized = _image_resize_anchor(wf, '44', height.out('value'), start_image.out('IMAGE'), width.out('value'))",
        "start_resized = _image_resize_anchor(wf, '44', width=width.out('value'), height=height.out('value'), image=start_image.out('IMAGE'))",
    )
    source = source.replace(
        "end_resized = _image_resize_anchor(wf, '48', height.out('value'), end_image.out('IMAGE'), width.out('value'))",
        "end_resized = _image_resize_anchor(wf, '48', width=width.out('value'), height=height.out('value'), image=end_image.out('IMAGE'))",
    )
    source = source.replace(
        "    first_strength = _node(wf, \"PrimitiveFloat\", \"2110\", value=ANCHOR_STRENGTH)\n"
        "    last_strength = _node(wf, \"PrimitiveFloat\", \"2108\", value=ANCHOR_STRENGTH)\n",
        "    first_strength, last_strength = anchor_strength_pair(wf, ANCHOR_STRENGTH)\n",
    )
    source = source.replace(
        "GUIDE_BRANCH = 'canny'  # one of: 'canny', 'raw', 'pose', 'depth'",
        "GUIDE_BRANCH = PUBLIC_INPUTS['control_mode'].default  # one of: 'canny', 'raw', 'pose', 'depth'",
    )
    source = source.replace("resolution=256,", "resolution=CONTROL_RESOLUTION,")
    source = source.replace(f"sigmas={refine_sigmas}", "sigmas=REFINE_SIGMAS")
    source = source.replace(f"sigmas={finish_sigmas}", "sigmas=FINISH_SIGMAS")
    source = source.replace(
        "    tiny_vae = _node(wf, \"VAELoader\", \"180\", vae_name=\"taeltx2_3.safetensors\")\n",
        "    # Preserved for source graph parity; this loader has no downstream consumers.\n"
        "    _tiny_vae = _node(wf, \"VAELoader\", \"180\", vae_name=\"taeltx2_3.safetensors\")\n",
    )
    source = source.replace(
        "    decoded_audio = _node(wf, \"LTXVAudioVAEDecode\", \"150\", audio_vae=audio_vae.out('Audio VAE'), samples=separated_finished.out('audio_latent'))\n",
        "    # Preserved for source graph parity; video output binding intentionally ignores audio.\n"
        "    _decoded_audio = _node(wf, \"LTXVAudioVAEDecode\", \"150\", audio_vae=audio_vae.out('Audio VAE'), samples=separated_finished.out('audio_latent'))\n",
    )
    return source


def _round_noisy_float_literals(source: str) -> str:
    """Replace representation-noisy float constants with short decimal forms."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    src_bytes = source.encode("utf-8")
    offsets = _byte_line_offsets(src_bytes)
    repls: list[tuple[int, int, bytes]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, float)):
            continue
        text = ast.get_source_segment(source, node)
        if text is None or len(text) <= 12 or "e" in text.lower():
            continue
        short = f"{node.value:.12g}"
        if "." not in short:
            continue
        try:
            if abs(float(short) - node.value) > 1e-12:
                continue
        except ValueError:
            continue
        if len(short) >= len(text):
            continue
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[(node.end_lineno or node.lineno) - 1] + (node.end_col_offset or 0)
        repls.append((start, end, short.encode("utf-8")))
    if not repls:
        return source
    repls.sort(key=lambda item: -item[0])
    arr = bytearray(src_bytes)
    for start, end, replacement in repls:
        arr[start:end] = replacement
    return arr.decode("utf-8")


def _dedupe_section_banners(source: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    banner_re = re.compile(r"^\s*# ════ ([^═]+?) ════\s*$")
    for line in source.splitlines(keepends=True):
        match = banner_re.match(line)
        if match:
            label = match.group(1).strip()
            if label in seen:
                continue
            seen.add(label)
        out.append(line)
    return "".join(out)


def _dedupe_consecutive_duplicate_comments(source: str) -> str:
    out: list[str] = []
    previous_comment: str | None = None
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("#") and stripped == previous_comment:
            continue
        out.append(line)
        previous_comment = stripped if stripped.startswith("#") else None
    return "".join(out)


def _strip_accidental_blank_lines(source: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", source)


def _strip_blank_kwarg_slots(source: str) -> str:
    source = re.sub(r"\n[ \t]*\n(?=[ \t]+\w+=)", "\n", source)
    return re.sub(r"\n[ \t]*\n\)", "\n    )", source)


def _indent_guide_nodes_dict(source: str) -> str:
    pattern = re.compile(r"(    GUIDE_NODES = \{\n)(.*?)(^\s*\})", re.MULTILINE | re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        body = match.group(2)
        fixed: list[str] = []
        for line in body.splitlines(keepends=True):
            if line.strip():
                fixed.append("        " + line.lstrip())
            else:
                fixed.append(line)
        return match.group(1) + "".join(fixed) + "    }"

    return pattern.sub(replace, source)


def _collapse_repeated_stage_comment_blocks(source: str) -> str:
    block = (
        "    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning\n"
        "    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning\n"
    )
    if source.count(block) <= 1:
        return source
    first = source.find(block)
    return source[: first + len(block)] + source[first + len(block):].replace(block, "")


def _inline_ltx_module_helpers(source: str) -> str:
    if "LTXAddVideoICLoRAGuide" not in source:
        return source
    source = re.sub(
        r"\ndef _image_resize_anchor\(wf, _id, \*, width, height, image, \*\*overrides\):\n"
        r"    kwargs = dict\(upscale_method='nearest-exact',\n"
        r"(?:                  .+\n)+?"
        r"    kwargs.update\(overrides\)\n"
        r"    return node\(wf, 'ImageResizeKJv2', _id, \*\*kwargs\)\n",
        "\n",
        source,
    )
    source = re.sub(
        r"def _image_resize\(wf, _id, width, height, image, \*\*overrides\):\n"
        r"    kwargs = dict\(upscale_method='lanczos',\n"
        r"(?:                  .+\n)+?"
        r"    kwargs.update\(overrides\)\n"
        r"    return node\(wf, 'ImageResizeKJv2', _id, \*\*kwargs\)\n\n",
        "",
        source,
    )
    source = re.sub(
        r"\ndef anchor_strength_pair\(wf, value\):\n"
        r"    first_strength = node\(wf, \"PrimitiveFloat\", \"2110\", value=value\)\n"
        r"    last_strength = node\(wf, \"PrimitiveFloat\", \"2108\", value=value\)\n"
        r"    assert first_strength.node.inputs\[\"value\"\] == last_strength.node.inputs\[\"value\"\]\n"
        r"    return first_strength, last_strength\n",
        "\n",
        source,
    )
    source = source.replace(
        "    first_strength, last_strength = anchor_strength_pair(wf, ANCHOR_STRENGTH)\n",
        "    first_strength = node(wf, \"PrimitiveFloat\", \"2110\", value=ANCHOR_STRENGTH)\n"
        "    last_strength = node(wf, \"PrimitiveFloat\", \"2108\", value=ANCHOR_STRENGTH)\n"
        "    assert first_strength.node.inputs[\"value\"] == last_strength.node.inputs[\"value\"]\n",
    )
    anchor_kwargs = (
        "upscale_method='nearest-exact', keep_proportion='crop', pad_color='0, 0, 0', "
        "crop_position='center', divisible_by=32, device='cpu'"
    )
    resize_kwargs = (
        "upscale_method='lanczos', keep_proportion='stretch', pad_color='0, 0, 0', "
        "crop_position='center', divisible_by=32, device='cpu'"
    )
    source = source.replace(
        "    start_resized = _image_resize_anchor(wf, '44', width=width.out('VALUE'), height=height.out('VALUE'), image=start_image.out('IMAGE'))\n",
        f"    start_resized = node(wf, 'ImageResizeKJv2', '44', {anchor_kwargs}, width=width.out('VALUE'), height=height.out('VALUE'), image=start_image.out('IMAGE'))\n",
    )
    source = source.replace(
        "    start_resized = _image_resize_anchor(wf, '44', height.out('VALUE'), start_image.out('IMAGE'), width.out('VALUE'))\n",
        f"    start_resized = node(wf, 'ImageResizeKJv2', '44', {anchor_kwargs}, width=width.out('VALUE'), height=height.out('VALUE'), image=start_image.out('IMAGE'))\n",
    )
    source = source.replace(
        "    end_resized = _image_resize_anchor(wf, '48', width=width.out('VALUE'), height=height.out('VALUE'), image=end_image.out('IMAGE'))\n",
        f"    end_resized = node(wf, 'ImageResizeKJv2', '48', {anchor_kwargs}, width=width.out('VALUE'), height=height.out('VALUE'), image=end_image.out('IMAGE'))\n",
    )
    source = source.replace(
        "    end_resized = _image_resize_anchor(wf, '48', height.out('VALUE'), end_image.out('IMAGE'), width.out('VALUE'))\n",
        f"    end_resized = node(wf, 'ImageResizeKJv2', '48', {anchor_kwargs}, width=width.out('VALUE'), height=height.out('VALUE'), image=end_image.out('IMAGE'))\n",
    )
    for var, node_id, image_expr in (
        ("guide_resized", "5026", "components.out('IMAGES')"),
        ("guide_raw", "6101", "guide_resized.out('IMAGE')"),
        ("guide_canny", "5028", "guide_canny_edges.out('IMAGE')"),
        ("guide_pose_sized", "6102", "guide_pose.out('IMAGE')"),
        ("guide_depth_sized", "6103", "guide_depth.out('IMAGE')"),
    ):
        source = source.replace(
            f"    {var} = _image_resize(wf, '{node_id}', width.out('VALUE'), height.out('VALUE'), {image_expr})\n",
            f"    {var} = node(wf, 'ImageResizeKJv2', '{node_id}', {resize_kwargs}, width=width.out('VALUE'), height=height.out('VALUE'), image={image_expr})\n",
        )
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    skip = False
    helper_prefixes = (
        "def _image_resize_anchor(",
        "def _image_resize(",
        "def anchor_strength_pair(",
    )
    for line in lines:
        if any(line.startswith(prefix) for prefix in helper_prefixes):
            skip = True
            continue
        if skip and line and not line.startswith((" ", "\t")) and line.strip():
            skip = False
        if not skip:
            out.append(line)
    source = "".join(out)
    return source


def _strip_ltx_nag_inplace_for_parity(source: str) -> str:
    """Drop resolved LTX2_NAG.inplace from final pilot output for API parity."""
    if '"LTX2_NAG"' not in source or "inplace=True" not in source:
        return source
    return source.replace("\n        inplace=True,", "")


def _inline_single_kwarg_primitives(source: str) -> str:
    vertical_re = re.compile(
        r"(?P<indent>^[ \t]*)(?P<var>\w+) = (?P<func>_?node)\(\n"
        r"(?P=indent)[ \t]+wf,\n"
        r"(?P=indent)[ \t]+(?P<class>\"Primitive(?:Boolean|Int|Float|String)\"),\n"
        r"(?P=indent)[ \t]+(?P<id>\"[^\"]+\"),\n"
        r"(?P=indent)[ \t]+value=(?P<value>[^\n]+),\n"
        r"(?P=indent)[ \t]*\)",
        re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        value = match.group("value").strip()
        if ".out(" in value or len(value) > 80:
            return match.group(0)
        line = f"{match.group('indent')}{match.group('var')} = {match.group('func')}(wf, {match.group('class')}, {match.group('id')}, value={value})"
        return line if len(line) <= 120 else match.group(0)

    source = vertical_re.sub(replace, source)
    hanging_re = re.compile(
        r"(?P<indent>^[ \t]*)(?P<var>\w+) = (?P<func>_?node)\(wf, (?P<class>['\"]Primitive(?:Boolean|Int|Float|String)['\"]), (?P<id>['\"][^'\"]+['\"]),\n"
        r"(?P=indent)[ \t]+value=(?P<value>[^\n,]+),\n"
        r"(?P=indent)[ \t]*\)",
        re.MULTILINE,
    )
    return hanging_re.sub(replace, source)


def _standardize_parity_comments(source: str) -> str:
    source = source.replace(
        "    # Preserved for source graph parity; this loader has no downstream consumers.\n",
        "    # parity-preserved leaves: source graph keeps this dead loader.\n",
    )
    source = source.replace(
        "    # Preserved for source graph parity; video output binding intentionally ignores audio.\n"
        "    _decoded_audio = _node(wf, \"LTXVAudioVAEDecode\", \"150\", audio_vae=audio_vae.out('AUDIO_VAE'), samples=separated_finished.out('AUDIO_LATENT'))\n",
        "    # parity-preserved leaves: source graph keeps this decoded audio branch.\n"
        "    _decoded_audio = _node(wf, \"LTXVAudioVAEDecode\", \"150\", audio_vae=audio_vae.out('AUDIO_VAE'), samples=separated_finished.out('AUDIO_LATENT'))\n",
    )
    source = source.replace(
        "    # Preserved for source graph parity; video output binding intentionally ignores audio.\n"
        "    _decoded_audio = _node(wf, \"LTXVAudioVAEDecode\", \"150\", audio_vae=audio_vae.out('Audio VAE'), samples=separated_finished.out('audio_latent'))\n",
        "    # parity-preserved leaves: source graph keeps this decoded audio branch.\n"
        "    _decoded_audio = _node(wf, \"LTXVAudioVAEDecode\", \"150\", audio_vae=audio_vae.out('Audio VAE'), samples=separated_finished.out('audio_latent'))\n",
    )
    source = re.sub(
        r"(?m)^(\s*)# UNUSED: no downstream consumers .*\n(\s*)(\w+ = _node\(wf, \"PrimitiveString\", \"([^\"]+)\", value=PUBLIC_INPUTS\['([^']+)'\]\.default\))",
        r"\1# parity-preserved label (edit PUBLIC_INPUTS['\5'].default to change)\n\2\3",
        source,
    )
    source = source.replace(
        "    control_mode = _node(wf, \"PrimitiveString\", \"6000\", value=PUBLIC_INPUTS['control_mode'].default)\n"
        "    # UNUSED: no downstream consumers — this is a label only, runtime no-op.\n",
        "    # parity-preserved label (edit PUBLIC_INPUTS['control_mode'].default to change)\n"
        "    control_mode = _node(wf, \"PrimitiveString\", \"6000\", value=PUBLIC_INPUTS['control_mode'].default)\n",
    )
    source = source.replace(
        "    image_scale_to_total_pixels_93 = node(wf, 'ImageScaleToTotalPixels', '93',\n",
        "    # parity-preserved leaf: wiring into edit encoding changes source API links.\n"
        "    image_scale_to_total_pixels_93 = node(wf, 'ImageScaleToTotalPixels', '93',\n",
    )
    source = source.replace(
        "    image_scale_to_total_pixels_93 = _node(wf, 'ImageScaleToTotalPixels', '93',\n",
        "    # parity-preserved leaf: wiring into edit encoding changes source API links.\n"
        "    image_scale_to_total_pixels_93 = _node(wf, 'ImageScaleToTotalPixels', '93',\n",
    )
    return source


def _comment_misspelled_upstream_classes(source: str) -> str:
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        if "PathchSageAttentionKJ" in line and "_node(" in line:
            indent = line[: len(line) - len(line.lstrip())]
            comment = f"{indent}# Upstream class is misspelled; do not rename.\n"
            if not out or out[-1] != comment:
                out.append(comment)
        out.append(line)
    return "".join(out)


def _rewrite_imports_for_v23(source: str) -> str:
    template_import = "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node\n"
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    for line in lines:
        if "from vibecomfy.ready" in line or "from vibecomfy.registry.ready_template" in line:
            continue
        if "from vibecomfy.templates import" in line:
            if not inserted:
                out.append(template_import)
                inserted = True
            continue
        if "from vibecomfy.workflow" in line:
            out.append("from vibecomfy.workflow import VibeWorkflow\n")
            if not inserted:
                out.append(template_import)
                inserted = True
            continue
        out.append(line)
    if not inserted:
        insert_at = 0
        for i, line in enumerate(out):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        out.insert(insert_at, template_import)
    return "".join(out)


def _rewrite_build_constructor_for_v231(source: str) -> str:
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    in_build = False
    replacing = False
    paren_depth = 0
    replaced = False
    for line in lines:
        if line.startswith("def build("):
            in_build = True
            out.append(line)
            continue
        if in_build and not replacing and not replaced and "wf = VibeWorkflow(" in line:
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}wf = new_workflow(READY_METADATA, source_path=__file__)\n")
            paren_depth = line.count("(") - line.count(")")
            if paren_depth > 0:
                replacing = True
            replaced = True
            continue
        if replacing:
            paren_depth += line.count("(") - line.count(")")
            if paren_depth <= 0:
                replacing = False
            continue
        out.append(line)
    return "".join(out)


def _find_build_footer_cut(lines: list[str]) -> int | None:
    in_build = False
    for idx, line in enumerate(lines):
        if line.startswith("def build("):
            in_build = True
            continue
        if not in_build:
            continue
        stripped = line.strip()
        if (
            stripped.startswith("wf.finalize_metadata(")
            or stripped.startswith("apply_ready_template_policy(")
            or stripped.startswith("wf.register_input(")
            or stripped.startswith("READY_METADATA.setdefault(")
            or stripped.startswith("bind_output(")
            or stripped.startswith("return finalize(")
            or stripped.startswith("return wf")
            or stripped.startswith("_registered =")
            or stripped.startswith("_expected =")
            or stripped.startswith("if _registered")
        ):
            return idx
    return None


def _strip_node_helper(source: str) -> str:
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("def _node("):
            idx += 1
            while idx < len(lines):
                next_line = lines[idx]
                if next_line and not next_line.startswith((" ", "\t")) and next_line.strip():
                    break
                idx += 1
            while out and not out[-1].strip():
                out.pop()
            out.append("\n")
            continue
        out.append(line)
        idx += 1
    return "".join(out)


def _rewrite_at_calls_to_node(source: str) -> str:
    try:
        id_sidecar = _extract_id_sidecar(ast.parse(source))
    except SyntaxError:
        id_sidecar = {}

    def repl(match: re.Match[str]) -> str:
        role = match.group(1)
        class_literal = match.group(2)
        node_id = id_sidecar.get(role, role)
        return f"node(wf, {class_literal}, {node_id!r}"

    return re.sub(
        r"_at\(\s*wf,\s*ID\[['\"]([^'\"]+)['\"]\],\s*(['\"][^'\"]+['\"])",
        repl,
        source,
    )


def _relocate_ready_metadata_update_lines(source: str) -> str:
    lines = source.splitlines(keepends=True)
    update_re = re.compile(r"^READY_METADATA(?:\[[^\]]+\]\.update|\.setdefault\([^\n]+\)\.update)\(")
    updates = [line for line in lines if update_re.match(line)]
    if not updates:
        return source
    kept = [line for line in lines if not update_re.match(line)]
    insert_at: int | None = None
    metadata_open = False
    paren_depth = 0
    for idx, line in enumerate(kept):
        if re.match(r"^READY_METADATA\s*=", line):
            metadata_open = True
            paren_depth = line.count("(") - line.count(")")
            if paren_depth <= 0:
                insert_at = idx + 1
                break
            continue
        if metadata_open:
            paren_depth += line.count("(") - line.count(")")
            if paren_depth <= 0:
                insert_at = idx + 1
                break
    if insert_at is None:
        return "".join(kept)
    while insert_at < len(kept) and not kept[insert_at].strip():
        insert_at += 1
    kept[insert_at:insert_at] = updates + ["\n"]
    return "".join(kept)


def _render_finalize_footer(bind_call: ast.Call | None, output_prefix: Any) -> str:
    output_node = _bind_output_node_id(bind_call)
    output_type = _kw_literal(bind_call, "output_type", None) if bind_call is not None else None
    name = _kw_literal(bind_call, "name", None) if bind_call is not None else None
    mime_type = _kw_literal(bind_call, "mime_type", None) if bind_call is not None else None
    expected_cardinality = _kw_literal(bind_call, "expected_cardinality", None) if bind_call is not None else None
    artifact_kind = _kw_literal(bind_call, "artifact_kind", None) if bind_call is not None else None
    declared_output_kind = _kw_literal(bind_call, "output_kind", None) if bind_call is not None else None
    derived_output_kind = _derive_output_kind(str(output_type or ""))
    output_kind = declared_output_kind or artifact_kind
    lines = [
        "    return finalize(\n",
        "        wf,\n",
        "        PUBLIC_INPUTS,\n",
        "        READY_METADATA,\n",
        f"        output_node={output_node!r},\n",
    ]
    if output_kind is not None and output_kind != derived_output_kind:
        lines.append(f"        output_kind={output_kind!r},\n")
    for key, value in [
        ("output_type", output_type),
        ("name", name),
        ("mime_type", mime_type),
        ("expected_cardinality", expected_cardinality),
    ]:
        if value is not None:
            lines.append(f"        {key}={value!r},\n")
    if output_prefix:
        lines.append(f"        filename_prefix={output_prefix!r},\n")
    lines.append("        source_path=__file__,\n")
    lines.append("    )\n")
    return "".join(lines)


def _convert_restructure_to_v23(source: str) -> str:
    """Convert the v2.2 narrative output into the v2.3 single-source shape."""
    if _is_v231_generated_source(source):
        return _rewrite_legacy_workflow_method_names(
            _rewrite_ready_requirements_refs(_remove_top_level_assignments(source, {"READY_REQUIREMENTS"}))
        )
    if "VibeWorkflow" not in source:
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    specs = _registered_input_specs(source, tree)
    models = _collect_model_assets(tree)
    model_asset_assignment_names = _collect_model_asset_assignment_names(tree)
    metadata = _collect_metadata_literal(tree)
    # Inject version pins (T12)
    metadata.setdefault("vibecomfy_version", _get_vibecomfy_version())
    if not isinstance(metadata.get("comfy_core"), dict) or metadata["comfy_core"].get("status") == "unavailable":
        metadata["comfy_core"] = _get_comfy_core_info()
    req_extras = _collect_requirements_extras(tree)
    bind_call = _collect_bind_output_call(tree)
    model_files = _collect_model_files_map(tree)
    _extend_models_from_loader_kwargs(tree, models)
    output_prefix = _kw_literal(bind_call, "filename_prefix", metadata.get("output_prefix", "")) if bind_call is not None else metadata.get("output_prefix", "")
    if isinstance(output_prefix, str) and output_prefix.isidentifier():
        output_prefix = _collect_top_level_literal(tree, output_prefix, metadata.get("output_prefix", ""))
    params = _collect_params_literal_map(tree)
    node_kwarg_rewrites, var_renames = _apply_pilot_public_surface(specs, tree, params)
    public_key_renames = _canonicalize_public_specs(specs, _collect_v23_node_records(tree), params)
    public_name_by_param = {name: name for name in specs}
    for name, spec in specs.items():
        for alias in tuple(spec.get("aliases") or ()):
            public_name_by_param[str(alias)] = name
    if "negative_prompt" in specs:
        public_name_by_param["negative"] = "negative_prompt"
    private_knobs = OrderedDict((key, value) for key, value in params.items() if key not in public_name_by_param)

    converted = _rewrite_params_refs_to_public_inputs(source, public_name_by_param)
    converted = _rewrite_node_kwarg_refs(converted, node_kwarg_rewrites)
    converted = _rewrite_public_input_key_refs(converted, public_key_renames)
    converted = _rewrite_model_file_refs(converted, model_files, models)
    converted = _rewrite_public_input_literal_refs(converted, specs)
    converted = _rewrite_model_literal_refs(converted, models)
    # Skip filename_prefix→OUTPUT_PREFIX rewriting; literal values stay in node calls and finalize footer.
    converted = _round_noisy_float_literals(converted)
    converted = _remove_top_level_assignments(
        converted,
        {
            "MODEL_FILES",
            "PARAMS",
            "MODELS",
            "PUBLIC_INPUTS",
            "EDIT_GUIDE",
            "READY_METADATA",
            "READY_REQUIREMENTS",
        } | model_asset_assignment_names,
    )
    converted = _rewrite_imports_for_v23(converted)
    converted = _rewrite_build_constructor_for_v231(converted)
    if var_renames:
        converted = _ast_rename_variables(converted, var_renames)

    # Inline private knob values directly at usage sites instead of emitting a top-level PRIVATE_KNOBS dict.
    if private_knobs:
        converted = _inline_private_knobs(converted, private_knobs)
    # Derive custom-node pack requirements from the converted source.
    # Only known pack names are emitted; bare class names that cannot be
    # mapped to the node-pack catalog are intentionally dropped.
    custom_node_packs = _derive_custom_node_packs_from_source(converted)
    if custom_node_packs:
        req_extras = {**req_extras, "custom_nodes": custom_node_packs}
    elif "custom_nodes" in req_extras:
        # Remove bare class names that couldn't be mapped to any pack
        req_extras = {k: v for k, v in req_extras.items() if k != "custom_nodes"}
    default_constants, _ = _public_input_default_exprs(specs)
    block = default_constants
    block += _render_model_block(models) + _render_public_inputs_block(specs, include_default_constants=False)
    block += _render_ready_blocks(metadata, req_extras, output_prefix)

    lines = converted.splitlines(keepends=True)
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("def build("):
            insert_at = i
            break
    if insert_at is None:
        return converted
    while insert_at > 0 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, block)
    converted = "".join(lines)

    lines = converted.splitlines(keepends=True)
    cut_at = _find_build_footer_cut(lines)
    if cut_at is not None:
        end_at = cut_at
        for idx in range(cut_at + 1, len(lines)):
            line = lines[idx]
            if line and not line.startswith((" ", "\t")) and line.strip():
                end_at = idx
                break
        else:
            end_at = len(lines)
        lines[cut_at:end_at] = [_render_finalize_footer(bind_call, output_prefix), "\n"]
        converted = "".join(lines)

    converted = _comment_misspelled_upstream_classes(converted)
    converted = _apply_ltx_pilot_improvements(converted)
    converted = _ast_resolve_widget_names(converted)
    converted = _update_register_input_fields(converted)
    converted = _strip_ltx_nag_inplace_for_parity(converted)
    converted = _strip_widget_shadows(converted)
    converted = _normalize_named_out_calls(converted)
    converted = _rewrite_v23_section_banners(converted, specs)
    converted = _dedupe_section_banners(converted)
    converted = _dedupe_consecutive_duplicate_comments(converted)
    converted = _standardize_parity_comments(converted)
    converted = _inline_single_kwarg_primitives(converted)
    converted = _strip_blank_kwarg_slots(converted)
    converted = _indent_guide_nodes_dict(converted)
    converted = _collapse_repeated_stage_comment_blocks(converted)
    converted = _inline_ltx_module_helpers(converted)
    converted = _strip_accidental_blank_lines(converted)
    converted = _strip_node_helper(converted)
    converted = _rewrite_at_calls_to_node(converted)
    if (
        "image_scale_to_total_pixels_93 = node" in converted
        and "parity-preserved leaf: wiring into edit encoding changes source API links." not in converted
    ):
        converted = converted.replace(
            "\n    image_scale_to_total_pixels_93 = node",
            "\n    # parity-preserved leaf: wiring into edit encoding changes source API links.\n    image_scale_to_total_pixels_93 = node",
        )
    if "\n    tiny_vae = _node" in converted and "\n    _tiny_vae = _node" not in converted:
        converted = converted.replace(
            "\n    tiny_vae = _node",
            "\n    # parity-preserved leaves:\n    _tiny_vae = _node",
            1,
        )
    converted = converted.replace(
        "\n    decoded_audio = _node(wf, \"LTXVAudioVAEDecode\"",
        "\n    _decoded_audio = _node(wf, \"LTXVAudioVAEDecode\"",
        1,
    )
    converted = _relocate_ready_metadata_update_lines(converted)
    converted = _remove_top_level_assignments(converted, {"ID", "READY_REQUIREMENTS"})
    converted = _rewrite_ready_requirements_refs(converted)
    converted = _rewrite_legacy_workflow_method_names(converted)
    converted = converted.replace("_node(", "node(")

    # Generate structured module docstring (T11)
    existing_docstring = None
    try:
        existing_docstring = ast.get_docstring(ast.parse(converted))
    except SyntaxError:
        pass
    output_type = _kw_literal(bind_call, "output_type", None) if bind_call is not None else None
    output_node_id = _bind_output_node_id(bind_call)
    final_packs = list(custom_node_packs) if custom_node_packs else []
    model_keys_list = list(models.keys())
    new_doc = _generate_structured_docstring(
        metadata=metadata,
        specs=specs,
        output_type=output_type,
        output_node_id=output_node_id,
        custom_node_packs=final_packs,
        existing_docstring=existing_docstring,
        model_keys=model_keys_list,
    )
    converted = _replace_module_docstring(converted, new_doc)

    # Replace plain marker at file top with enriched marker (no duplicate)
    converted = re.sub(r"^# vibecomfy: narrative\n", _marker_line() + "\n", converted, count=1)

    return converted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=None, help="Path to the input ready-template .py file")
    parser.add_argument("--out", type=Path, default=None, help="Output path")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing")
    parser.add_argument("--diff", action="store_true", help="Print a unified diff against the original")
    parser.add_argument("--analyze", type=Path, default=None, dest="analyze_path",
                        help="Run static analysis on a template and emit JSON findings")
    parser.add_argument("--json", action="store_true", default=False,
                        help="Emit JSON output (for --analyze)")
    parser.add_argument(
        "--verify", nargs=2, type=Path, metavar=("ORIGINAL", "CANDIDATE"),
        help="Verify that candidate preserves original API dict, unbound_inputs, and register_input names",
    )
    parser.add_argument(
        "--mode", type=str, default="restructure",
        choices=["annotate", "restructure"],
        help="v2 codemod mode: restructure (full v2, default) or annotate (non-committable debug)",
    )
    args = parser.parse_args(argv)

    # --analyze mode
    if args.analyze_path is not None:
        if not args.analyze_path.is_file():
            print(f"error: {args.analyze_path} not found", file=sys.stderr)
            return 2
        result = run_analyzer(args.analyze_path)
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    # --verify mode
    if args.verify:
        orig_path, cand_path = args.verify
        for p in (orig_path, cand_path):
            if not p.is_file():
                print(f"error: {p} not found", file=sys.stderr)
                return 2
        return cmd_verify(orig_path, cand_path)

    # v2 codemod (default: restructure).  --mode annotate is available for debug.
    if args.input is None:
        parser.error("either provide an input file or use --verify ORIGINAL CANDIDATE")
    return cmd_codemod_v2(args.input, args.out, args.mode, args.dry_run, args.diff)


if __name__ == "__main__":
    raise SystemExit(main())
