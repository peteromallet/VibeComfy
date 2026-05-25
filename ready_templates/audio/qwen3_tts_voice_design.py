# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import SaveAudioMP3
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceDesign


DEFAULT_PROMPT = 'This is a compact Qwen voice design smoke test for reusable VibeComfy audio templates.'
DEFAULT_SEED = 3294

READY_METADATA = ReadyMetadata.build(
    capability='text_to_speech_voice_design',
    requirements={'custom_nodes': ['ComfyUI-QwenTTS']},
    custom_node_packs={'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceDesign'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'pinned'}},
    approach='text-to-speech from a natural language voice description',
    runtime_variant='qwen3-tts-smoke',
    runtime_note='Voice design currently requires the 1.7B Qwen3-TTS path exposed by the custom node.',
    input_fixtures=[],
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    ailab_qwen3ttsvoicedesign = AILab_Qwen3TTSVoiceDesign(
        instruct='A warm narrator voice with crisp diction and a neutral studio tone.',
        language='English',
        seed=DEFAULT_SEED,
        text=DEFAULT_PROMPT,
    )

    saveaudiomp3 = SaveAudioMP3(
        filename_prefix='audio/qwen3_tts_voice_design',
        audio=ailab_qwen3ttsvoicedesign,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=ailab_qwen3ttsvoicedesign, field='seed', default=DEFAULT_SEED),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one')

