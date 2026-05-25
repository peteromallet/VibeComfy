# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import EmptyImage, SaveImage

READY_METADATA = ReadyMetadata.build(
    capability='runtime_smoke',
    approach='minimal Python ready template for cloud/runtime/artifact validation',
    runtime_note='No model assets; use corpus/model matrices for production model coverage.',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    emptyimage = EmptyImage(color=16711680, height=64, width=64)

    saveimage = SaveImage(
        filename_prefix='vibecomfy_ready_smoke_red',
        images=emptyimage,
    )


    PUBLIC_INPUTS = {
        'width': InputSpec(node=emptyimage, field='width', default=64),
        'height': InputSpec(node=emptyimage, field='height', default=64),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='vibecomfy_ready_smoke_red')

