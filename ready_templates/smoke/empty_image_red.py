# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import OutputSpec, ReadyMetadata, new_workflow, public
from vibecomfy.nodes.core import EmptyImage, SaveImage


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='runtime_smoke',
    approach='minimal Python ready template for cloud/runtime/artifact validation',
    runtime_note='No model assets; use corpus/model matrices for production model coverage.',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        emptyimage = EmptyImage(
            color=16711680,
            height=public('height', default=64),
            width=public('width', default=64),
        )

        saveimage = SaveImage(
            filename_prefix='vibecomfy_ready_smoke_red',
            images=emptyimage,
        )

        return wf.finalize({}, filename_prefix='vibecomfy_ready_smoke_red', spec=OUTPUT_SPEC)

