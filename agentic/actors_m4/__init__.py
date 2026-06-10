"""M4 structural evidence builders — nuanced multi-edit template-change scenarios.

Each builder loads (or faithfully mirrors) a real Wan/LTX base workflow, performs
the canonical "correct" edit, finalizes metadata, compiles, and freezes the golden
evidence pack. These double as golden-run regression guards: the fake/structural
run calls them, and a real agent must independently reproduce equivalent evidence.
"""

from __future__ import annotations

from agentic.actors_m4.ltx_firstlast_disable_resize_rewire import (
    build_m4_ltx_firstlast_disable_resize_rewire_evidence,
)
from agentic.actors_m4.ltx_i2v_swap_tiled_vae_decode import (
    build_m4_ltx_i2v_swap_tiled_vae_decode_evidence,
)
from agentic.actors_m4.wan22_i2v_second_pass_refine import (
    build_m4_wan22_i2v_second_pass_refine_evidence,
)
from agentic.actors_m4.wan22_stack_highlow_noise_lora import (
    build_m4_wan22_stack_highlow_noise_lora_evidence,
)
from agentic.actors_m4.wan_t2v_append_frame_interpolation import (
    build_m4_wan_t2v_append_frame_interpolation_evidence,
)
from agentic.actors_m4.wan_t2v_splice_modelpatch_before_loras import (
    build_m4_wan_t2v_splice_modelpatch_before_loras_evidence,
)

_M4_BUILDERS = {
    "wan22-i2v-second-pass-refine": build_m4_wan22_i2v_second_pass_refine_evidence,
    "wan-t2v-append-frame-interpolation": build_m4_wan_t2v_append_frame_interpolation_evidence,
    "ltx-i2v-swap-tiled-vae-decode": build_m4_ltx_i2v_swap_tiled_vae_decode_evidence,
    "wan22-stack-highlow-noise-lora": build_m4_wan22_stack_highlow_noise_lora_evidence,
    "ltx-firstlast-disable-resize-rewire": build_m4_ltx_firstlast_disable_resize_rewire_evidence,
    "wan-t2v-splice-modelpatch-before-loras": build_m4_wan_t2v_splice_modelpatch_before_loras_evidence,
}

__all__ = ["_M4_BUILDERS"]
