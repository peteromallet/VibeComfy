# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import SaveAudioMP3
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceDesign


DEFAULT_SEED = 124

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    custom_node_packs={'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceDesign'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json', 'source_id': 'qwen3_tts_voice_design', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json', 'source_ref': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json', 'source_kind': 'raw_json', 'indexed_id': None, 'workflow_source_id': 'qwen3_tts_voice_design', 'workflow_source_type': 'api', 'raw_workflow_shape': 'api', 'source_hash': 'sha256:d2f182b8933ed8ddaa50ccf89895e89fa9a2f5109a327eeab8335c94ef2295b0', 'workflow_shape': {'nodes': 2, 'runtime_nodes': 2, 'helper_nodes': 0, 'edges': 1, 'inputs': 1, 'outputs': 1}, 'output_mode': 'ready_template', 'ready_id': 'audio/qwen3_tts_voice_design'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    ailab_qwen3ttsvoicedesign = AILab_Qwen3TTSVoiceDesign(
        instruct='A warm narrator voice with crisp diction and a neutral studio tone.',
        language='English',
        seed=DEFAULT_SEED,
        text='This is a compact Qwen voice design smoke test for reusable VibeComfy audio templates.',
    )

    saveaudiomp3 = SaveAudioMP3(
        filename_prefix='audio/qwen3_tts_voice_design',
        audio=ailab_qwen3ttsvoicedesign,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=ailab_qwen3ttsvoicedesign, field='seed', default=DEFAULT_SEED, type='INT'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one', filename_prefix='audio/qwen3_tts_voice_design')

