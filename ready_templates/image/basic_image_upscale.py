# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import ImageScaleBy, LoadImage, SaveImage


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='image_upscale',
    approach='Core ComfyUI lanczos ImageScaleBy; maps Reigh image-upscale parameters without external API calls.',
    runtime_note='This preserves the task contract but is not FlashVSR/RealESRGAN model super-resolution.',
    provenance={'source_workflow': 'ready_templates/image/basic_image_upscale.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        image, mask = LoadImage(
            image=public('image', default='image_upscale_input.png'),
        )

        imagescaleby = ImageScaleBy(upscale_method='lanczos', scale_by=2.0, image=image)
        saveimage = SaveImage(filename_prefix='image-upscale', images=imagescaleby)

        return wf.finalize({}, filename_prefix='image-upscale', spec=OUTPUT_SPEC)

