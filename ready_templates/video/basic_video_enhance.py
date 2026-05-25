# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ReadyMetadata, new_workflow
from vibecomfy.nodes.core import ImageScaleBy
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine

READY_METADATA = ReadyMetadata.build(
    capability='video_enhance',
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}},
    approach='VHS_LoadVideo -> ImageScaleBy -> VHS_VideoCombine, avoiding gated model downloads.',
    runtime_note='Frame interpolation is intentionally not enabled in the default app-active route because the prior GIMM-VFI asset is license-gated without HF_TOKEN.',
    provenance={'source_workflow': 'ready_templates/video/basic_video_enhance.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    image, frame_count, audio, video_info = VHS_LoadVideo(
        video='video_enhance_input.mp4',
    )

    imagescaleby = ImageScaleBy(upscale_method='lanczos', scale_by=2.0, image=image)

    vhs_videocombine = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='video-enhance',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        audio=audio,
        images=imagescaleby,
    )

    return wf.finalize({}, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video-enhance')

