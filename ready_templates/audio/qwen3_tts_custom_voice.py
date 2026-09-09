# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import SaveAudioMP3
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSCustomVoice


DEFAULT_PROMPT = 'VibeComfy generated this short Qwen voice smoke test from a reusable Python template.'
DEFAULT_SEED = 123


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='1', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='audio',
    inputs=PUBLIC_INPUT_METADATA,
    custom_node_packs={'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSCustomVoice'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/qwen_tts/1038lab/qwen3_tts_custom_voice.json', 'source_id': 'audio/qwen3_tts_custom_voice', 'upstream_source_id': 'qwen3_tts_custom_voice', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/qwen_tts/1038lab/qwen3_tts_custom_voice.json', 'output_mode': 'ready_template', 'ready_id': 'audio/qwen3_tts_custom_voice'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    ailab_qwen3ttscustomvoice = AILab_Qwen3TTSCustomVoice(
        _id='1',
        instruct='Calm, clear, friendly delivery.',
        language='English',
        model_size='0.6B',
        seed=DEFAULT_SEED,
        text=DEFAULT_PROMPT,
    )

    saveaudiomp3 = SaveAudioMP3(
        _id='2',
        filename_prefix='audio/qwen3_tts_custom_voice',
        audio=ailab_qwen3ttscustomvoice,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one', filename_prefix='audio/qwen3_tts_custom_voice')

