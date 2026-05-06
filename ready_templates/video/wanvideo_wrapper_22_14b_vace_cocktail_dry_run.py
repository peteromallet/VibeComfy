# vibecomfy: manual
"""Sprint 3.5 Wan 2.2 VACE cocktail feasibility dry-run template."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


FIXTURE_MANIFEST_PATH = "reigh-worker/scripts/dual_run_compare/fixtures/sprint35/manifest.json"
WGP_DEFAULT_PATH = "reigh-worker/Wan2GP/defaults/wan_2_2_vace_lightning_baseline_2_2_2.json"
COCKTAIL_DEFAULT_PATH = "reigh-worker/Wan2GP/defaults/vace_fun_14B_cocktail_2_2.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(relative_path: str) -> dict[str, Any]:
    with (_repo_root() / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _optional_json(relative_path: str) -> dict[str, Any]:
    try:
        return _read_json(relative_path)
    except FileNotFoundError:
        return {}


def _scheduler_timesteps(steps: int, shift: float) -> list[float]:
    if steps <= 1:
        return [1000.0]
    raw = [1000.0 + (1.0 - 1000.0) * index / (steps - 1) for index in range(steps)]
    timesteps: list[float] = []
    for value in raw:
        normalized = value / 1000.0
        shifted = shift * normalized / (1.0 + (shift - 1.0) * normalized)
        timesteps.append(shifted * 1000.0)
    return timesteps


def _first_step_below(timesteps: list[float], threshold: float) -> int:
    for index, value in enumerate(timesteps, start=1):
        if value <= threshold:
            return max(index - 1, 0)
    return len(timesteps)


def _derive_wgp_schedule(defaults: dict[str, Any]) -> dict[str, Any]:
    steps = int(defaults["num_inference_steps"])
    flow_shift = float(defaults["flow_shift"])
    switch_threshold = float(defaults["switch_threshold"])
    switch_threshold2 = float(defaults["switch_threshold2"])
    timesteps = _scheduler_timesteps(steps, flow_shift)
    phase_2_start = _first_step_below(timesteps, switch_threshold)
    phase_3_start = _first_step_below(timesteps, switch_threshold2)
    return {
        "guidance_phases": defaults["guidance_phases"],
        "num_inference_steps": steps,
        "guidance_scales": [
            defaults["guidance_scale"],
            defaults["guidance2_scale"],
            defaults["guidance3_scale"],
        ],
        "flow_shift": defaults["flow_shift"],
        "switch_threshold": defaults["switch_threshold"],
        "switch_threshold2": defaults["switch_threshold2"],
        "model_switch_phase": defaults["model_switch_phase"],
        "sample_solver": defaults["sample_solver"],
        "phase_step_allocation": [
            phase_2_start,
            phase_3_start - phase_2_start,
            steps - phase_3_start,
        ],
        "phase_model_topology": ["HIGH", "HIGH", "LOW"],
        "derived_timesteps": [round(value, 3) for value in timesteps],
    }


_fixture_manifest = _optional_json(FIXTURE_MANIFEST_PATH)
_wgp_defaults = _optional_json(WGP_DEFAULT_PATH)
_cocktail_defaults = _optional_json(COCKTAIL_DEFAULT_PATH)
_wgp_schedule = _derive_wgp_schedule(_wgp_defaults) if _wgp_defaults else _fixture_manifest.get("wgp_schedule", {})
_cocktail_model = _cocktail_defaults.get("model", {})
_model_assets = _fixture_manifest.get("model_assets", {})

READY_METADATA = {
    "ready_template": "video/wanvideo_wrapper_22_14b_vace_cocktail_dry_run",
    "workflow_template": "wanvideo_wrapper_22_14b_vace_cocktail_dry_run",
    "capability": "video_to_video",
    "source_role": "manual_sprint35_feasibility_template",
    "source_workflow": None,
    "coverage_tier": "sprint35_dry_run",
    "approach": "Wan 2.2 VACE cocktail explicit HIGH/HIGH/LOW three-sampler dry run",
    "fixture_manifest_path": FIXTURE_MANIFEST_PATH,
    "route_key": _fixture_manifest.get("route_key"),
    "threshold_route_key": _fixture_manifest.get("threshold_route_key"),
    "threshold_version": _fixture_manifest.get("threshold_version"),
    "model_default_path": WGP_DEFAULT_PATH,
    "cocktail_default_path": COCKTAIL_DEFAULT_PATH,
    "model_default_id": _fixture_manifest.get("model_name"),
    "model_name": _wgp_defaults.get("model", {}).get("name") or _cocktail_model.get("name"),
    "architecture": _wgp_defaults.get("model", {}).get("architecture") or _cocktail_model.get("architecture"),
    "seed": _fixture_manifest.get("seed", _wgp_defaults.get("seed")),
    "width": _fixture_manifest.get("width"),
    "height": _fixture_manifest.get("height"),
    "fps": _fixture_manifest.get("fps"),
    "num_frames": _fixture_manifest.get("num_frames", 49),
    "wgp_schedule": _wgp_schedule,
    "high_model_checkpoint": "WanVideo\\Wan2_2_Fun_VACE_A14B_HIGH_mbf16.safetensors",
    "low_model_checkpoint": "WanVideo\\Wan2_2_Fun_VACE_A14B_LOW_mbf16.safetensors",
    "vace_module": "WanVideo\\Wan2_2_Fun_VACE_A14B_HIGH_mbf16.safetensors",
    "model_asset_urls": {
        "high": _model_assets.get("high_model_urls", []),
        "low": _model_assets.get("low_model_urls", []),
    },
    "cocktail_loras": _cocktail_model.get("loras") or _model_assets.get("cocktail_loras", []),
    "cocktail_lora_multipliers": (
        _cocktail_model.get("loras_multipliers") or _model_assets.get("cocktail_lora_multipliers", [])
    ),
    "phase_count": _wgp_schedule.get("guidance_phases"),
    "phase_step_allocation": _wgp_schedule.get("phase_step_allocation"),
    "phase_model_topology": _wgp_schedule.get("phase_model_topology"),
    "source_evidence": [
        WGP_DEFAULT_PATH,
        COCKTAIL_DEFAULT_PATH,
        FIXTURE_MANIFEST_PATH,
        "docs/migration-vibecomfy.md#Q17",
    ],
    "runtime_note": "Feasibility-only dry run; explicit sampler chain mirrors WGP model switch behavior.",
}

READY_REQUIREMENTS = {
    "models": [],
    "custom_nodes": [
        "ComfyUI-KJNodes",
        "ComfyUI-VideoHelperSuite",
        "ComfyUI-WanVideoWrapper",
    ],
}


def build() -> VibeWorkflow:
    """Build the Sprint 3.5 Wan 2.2 VACE cocktail dry-run workflow."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    prompt = _text_from_fixture("prompt.txt", "cinematic travel transition between the provided anchors")
    negative_prompt = _text_from_fixture("negative_prompt.txt", "")
    schedule = READY_METADATA["wgp_schedule"]
    phase_steps = schedule["phase_step_allocation"]
    guidance_scales = schedule["guidance_scales"]

    t5 = _node(
        wf,
        "LoadWanVideoT5TextEncoder",
        "10",
        model_name="umt5-xxl-enc-bf16.safetensors",
        precision="bf16",
        load_device="offload_device",
        quantization="disabled",
    )
    vae = _node(
        wf,
        "WanVideoVAELoader",
        "11",
        model_name="wanvideo\\Wan2_2_VAE_bf16.safetensors",
        precision="bf16",
    )
    loras = _node(
        wf,
        "WanVideoLoraSelectMulti",
        "12",
        lora_0="WanVideo\\loras\\Wan21_CausVid_14B_T2V_lora_rank32_v2.safetensors",
        strength_0=1,
        lora_1="WanVideo\\loras\\DetailEnhancerV1.safetensors",
        strength_1=0.2,
        lora_2="WanVideo\\loras\\Wan21_AccVid_T2V_14B_lora_rank32_fp16.safetensors",
        strength_2=0.5,
        lora_3="WanVideo\\loras\\Wan21_T2V_14B_MoviiGen_lora_rank32_fp16.safetensors",
        strength_3=0.5,
        lora_4="none",
        strength_4=1,
        prev_lora=False,
        merge_loras=False,
    )
    high_model = _node(
        wf,
        "WanVideoModelLoader",
        "20",
        model=READY_METADATA["high_model_checkpoint"],
        base_precision="bf16",
        quantization="default",
        load_device="offload_device",
        attention_mode="sdpa",
        lora=loras.out(0),
    )
    low_model = _node(
        wf,
        "WanVideoModelLoader",
        "21",
        model=READY_METADATA["low_model_checkpoint"],
        base_precision="bf16",
        quantization="default",
        load_device="offload_device",
        attention_mode="sdpa",
        lora=loras.out(0),
    )
    text_embeds = _node(
        wf,
        "WanVideoTextEncode",
        "30",
        positive_prompt=prompt,
        negative_prompt=negative_prompt,
        force_offload=True,
        use_diskcache=False,
        device="gpu",
        t5=t5.out(0),
    )
    start_image = _node(
        wf,
        "LoadImage",
        "40",
        image=_fixture_input("start_image"),
        widget_1="image",
    )
    end_image = _node(
        wf,
        "LoadImage",
        "41",
        image=_fixture_input("end_image"),
        widget_1="image",
    )
    guidance_video = _node(
        wf,
        "VHS_LoadVideo",
        "42",
        video=_fixture_input("guidance_video"),
        frame_load_cap=READY_METADATA["num_frames"],
        skip_first_frames=0,
    )
    image_size = _node(
        wf,
        "GetImageSizeAndCount",
        "43",
        image=guidance_video.out(0),
    )
    vace_start_end = _node(
        wf,
        "WanVideoVACEStartToEndFrame",
        "44",
        widget_0=READY_METADATA["num_frames"],
        widget_1=0,
        end_image=end_image.out(0),
        start_image=start_image.out(0),
    )
    vace_module = _node(
        wf,
        "WanVideoVACEModelSelect",
        "45",
        widget_0=READY_METADATA["vace_module"],
    )
    vace_encode = _node(
        wf,
        "WanVideoVACEEncode",
        "46",
        height=image_size.out(1),
        mask=vace_start_end.out(1),
        ref_images=vace_start_end.out(2),
        vae=vae.out(0),
        vace_model=vace_module.out(0),
        vace_video=guidance_video.out(0),
        width=image_size.out(0),
    )
    phase_1 = _sampler(
        wf,
        "50",
        steps=phase_steps[0],
        cfg=guidance_scales[0],
        seed=READY_METADATA["seed"],
        model=high_model.out(0),
        text_embeds=text_embeds.out(0),
        image_embeds=vace_encode.out(0),
    )
    phase_2 = _sampler(
        wf,
        "51",
        steps=phase_steps[1],
        cfg=guidance_scales[1],
        seed=READY_METADATA["seed"],
        model=high_model.out(0),
        text_embeds=text_embeds.out(0),
        image_embeds=vace_encode.out(0),
        samples=phase_1.out(0),
    )
    phase_3 = _sampler(
        wf,
        "52",
        steps=phase_steps[2],
        cfg=guidance_scales[2],
        seed=READY_METADATA["seed"],
        model=low_model.out(0),
        text_embeds=text_embeds.out(0),
        image_embeds=vace_encode.out(0),
        samples=phase_2.out(0),
    )
    decoded = _node(
        wf,
        "WanVideoDecode",
        "60",
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization="default",
        samples=phase_3.out(0),
        vae=vae.out(0),
    )
    _node(
        wf,
        "VHS_VideoCombine",
        "70",
        frame_rate=READY_METADATA["fps"],
        loop_count=0,
        filename_prefix="sprint35_vibecomfy_candidate",
        format="video/h264-mp4",
        pingpong=False,
        save_output=True,
        images=decoded.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _sampler(
    wf: VibeWorkflow,
    node_id: str,
    *,
    steps: int,
    cfg: float,
    seed: int,
    model: Any,
    text_embeds: Any,
    image_embeds: Any,
    samples: Any | None = None,
) -> Any:
    kwargs = {
        "steps": steps,
        "cfg": float(cfg),
        "scheduler": "euler",
        "shift": READY_METADATA["wgp_schedule"]["flow_shift"],
        "seed": int(seed),
        "control_after_generate": "fixed",
        "force_offload": True,
        "riflex_freq_index": 0,
        "denoise_strength": 1,
        "add_noise": False,
        "start_step": 0,
        "end_step": -1,
        "return_with_leftover_noise": False,
        "preview_method": "comfy",
        "scheduler_args": "",
        "image_embeds": image_embeds,
        "model": model,
        "text_embeds": text_embeds,
    }
    if samples is not None:
        kwargs["samples"] = samples
    return _node(wf, "WanVideoSampler", node_id, **kwargs)


def _text_from_fixture(relative_path: str, fallback: str) -> str:
    path = _repo_root() / "reigh-worker/scripts/dual_run_compare/fixtures/sprint35" / relative_path
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return fallback


def _fixture_input(key: str) -> str:
    input_refs = _fixture_manifest.get("input_refs", {})
    return str(Path("sprint35") / input_refs.get(key, key))


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs: Any):
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
