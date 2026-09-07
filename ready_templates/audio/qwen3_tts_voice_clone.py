# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import LoadAudio, SaveAudioMP3
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone


DEFAULT_SEED = 125
SPEECH_SMOKE_WAV = 'speech_smoke.wav'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='2', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='audio',
    inputs=PUBLIC_INPUT_METADATA,
    custom_node_packs={'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json', 'source_id': 'audio/qwen3_tts_voice_clone', 'upstream_source_id': 'qwen3_tts_voice_clone', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json', 'output_mode': 'ready_template', 'ready_id': 'audio/qwen3_tts_voice_clone'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadaudio = LoadAudio(_id='1', audio=SPEECH_SMOKE_WAV, widget_0='speech_smoke.wav')

    ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
        _id='2',
        target_text='This Qwen voice clone template uses a tiny bundled reference clip and runs as a reusable audio smoke test.',
        model_size='0.6B',
        language='English',
        reference_text='This is a short reference audio sample for workflow smoke testing.',
        seed=DEFAULT_SEED,
        reference_audio=loadaudio,
    )

    saveaudiomp3 = SaveAudioMP3(
        _id='3',
        filename_prefix='audio/qwen3_tts_voice_clone',
        audio=ailab_qwen3ttsvoiceclone,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one', filename_prefix='audio/qwen3_tts_voice_clone')

