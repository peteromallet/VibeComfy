# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import ImageScaleBy
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine

READY_METADATA = ReadyMetadata.build(
    capability='video_enhance',
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite'], 'custom_node_refs': [{'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}]},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}},
    approach='VHS_LoadVideo -> ImageScaleBy -> VHS_VideoCombine, avoiding gated model downloads.',
    runtime_note='Frame interpolation is intentionally not enabled in the default app-active route because the prior GIMM-VFI asset is license-gated without HF_TOKEN. The typed route preserves source audio and source FPS through the VHS outputs.',
    provenance={'source_workflow': 'ready_templates/video/basic_video_enhance.py'},
)

PUBLIC_INPUT_METADATA = {
    'video_ref': InputSpec(node='1', field='video', default='video_enhance_input.mp4', type='CHOICE', required=True, media_semantics='video'),
    'scale': InputSpec(node='2', field='scale_by', default=2.0, type='FLOAT'),
    'upscale_method': InputSpec(node='2', field='upscale_method', default='lanczos', type='CHOICE'),
}

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    image, _, audio, frame_rate = VHS_LoadVideo(_id='1', video='video_enhance_input.mp4')

    imagescaleby = ImageScaleBy(
        _id='2',
        upscale_method='lanczos',
        scale_by=2.0,
        image=image,
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='3',
        frame_rate=frame_rate,
        filename_prefix='video-enhance',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        audio=audio,
        images=imagescaleby,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video-enhance')
