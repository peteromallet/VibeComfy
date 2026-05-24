# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import ConditioningZeroOut, DualCLIPLoader, KSampler, ModelSamplingAuraFlow, SaveAudioMP3, UNETLoader, VAEDecodeAudio, VAELoader

# --- legacy SymbolicNodeRef shim (this template is marked manual; the
# public ``vibecomfy.templates.ref`` symbol is retired) -------------------
class SymbolicNodeRef:
    """Local copy of the retired ``vibecomfy.templates.SymbolicNodeRef``."""

    __slots__ = ("label",)

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return f"SymbolicNodeRef({self.label!r})"

    def __eq__(self, other):
        return isinstance(other, SymbolicNodeRef) and self.label == other.label

    def __hash__(self):
        return hash(("SymbolicNodeRef", self.label))

    def resolve(self, namespace, wf):
        value = namespace.get(self.label)
        node_id = None
        if hasattr(value, "node_id"):
            node_id = str(value.node_id)
        elif hasattr(value, "node") and value.node is not None and hasattr(value.node, "id"):
            node_id = str(value.node.id)
        elif hasattr(value, "id"):
            node_id = str(value.id)
        elif isinstance(value, str):
            node_id = value
        if node_id is None or node_id not in wf.nodes:
            raise ValueError(
                f"SymbolicNodeRef({self.label!r}) could not be resolved to a node "
                f"in workflow {wf.id!r}"
            )
        wf.metadata.setdefault("id_map", {})[self.label] = node_id
        return node_id


def ref(label):
    """Local copy of the retired ``vibecomfy.templates.ref``."""

    return SymbolicNodeRef(label)
# --- end legacy shim -----------------------------------------------------


DEFAULT_SEED = 561594583201063
GUIDE_STRENGTH = 1
MODEL_NAME = 'qwen_0.6b_ace15.safetensors'
MODEL_NAME_2 = 'qwen_4b_ace15.safetensors'
MODEL_NAME_3 = 'ace_1.5_vae.safetensors'
MODEL_NAME_4 = 'acestep_v1.5_turbo.safetensors'


MODELS = {
    'qwen_0_6b_ace15': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors', sha256='fd4590c82153b8ddb67e15a2e7aaa8afa8b83a858c8a9b82a4831063156aa7a7', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=1191588248, subdir='text_encoders'),
    'qwen_4b_ace15': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors', sha256='ffe5ffb855086c2ab55e467e9859fb01894781020a0376484dd19de166b79873', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=8379154232, subdir='text_encoders'),
    'ace_1_5_vae': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors', sha256='6de92e3a862acd287e08b024ac90f0783a8635451b728721a33ff03565bcb2bb', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=337431732, subdir='vae'),
    'acestep_v1_5_turbo': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors', sha256='3f6e0797fad420a39bd33979eb6e840e30989e34a3794e843d23b60ec6e422d7', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=4787825604, subdir='diffusion_models'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME_4),
    'seed': InputSpec(node=ref('textencodeacestepaudio1_5'), field='seed', default=DEFAULT_SEED),
    'steps': InputSpec(node=ref('ksampler'), field='steps', default=1),
    'lyrics': InputSpec(node=ref('textencodeacestepaudio1_5'), field='lyrics', default='Verse\nTiny signal in the night.'),
    'tags': InputSpec(node=ref('textencodeacestepaudio1_5'), field='tags', default='synthwave, short instrumental'),
    'duration': InputSpec(node=ref('textencodeacestepaudio1_5'), field='duration', default=2),
    'bpm': InputSpec(node=ref('textencodeacestepaudio1_5'), field='bpm', default=120),
    'cfg': InputSpec(node=ref('ksampler'), field='cfg', default=GUIDE_STRENGTH),
    'sampler_name': InputSpec(node=ref('ksampler'), field='sampler_name', default='euler'),
    'seed_2': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'noise_seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_audio_song',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='audio/vibecomfy_ace_step_smoke',
    requirements={'custom_nodes': ['EmptyAceStep1', 'TextEncodeAceStepAudio1']},
    approach='ACE-Step 1.5 text-to-audio song generation',
    runtime_note='Official subgraph materialized to API-shaped nodes for VibeComfy smoke execution.',
    smoke_duration_seconds=2,
    subgraph_materialized=True,
    provenance={'source_workflow': 'workflow_corpus/official/audio/ace_step_1_5_t2a_song.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Loaders
        dualcliploader = DualCLIPLoader(
            _id='105',
            clip_name1=MODEL_NAME,
            clip_name2=MODEL_NAME_2,
            type_='ace',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        vaeloader = VAELoader(_id='106', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        emptyacestep1_5latentaudio = raw_call(wf, 'EmptyAceStep1.5LatentAudio', '122',
            seconds=2,
        )
        wf.metadata.setdefault('id_map', {})['emptyacestep1_5latentaudio'] = emptyacestep1_5latentaudio.node.id

        unetloader = UNETLoader(_id='125', unet_name=MODEL_NAME_4)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        modelsamplingauraflow = ModelSamplingAuraFlow(
            _id='78',
            shift=3,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingauraflow'] = modelsamplingauraflow.node.id

        textencodeacestepaudio1_5 = raw_call(wf, 'TextEncodeAceStepAudio1.5', '124',
            bpm=120,
            cfg_scale=1.5,
            duration=2,
            keyscale='E minor',
            language='en',
            lyrics='Verse\nTiny signal in the night.',
            min_p=0.9,
            seed=DEFAULT_SEED,
            tags='synthwave, short instrumental',
            temperature=0,
            timesignature='4',
            top_p=0.85,
            clip=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['textencodeacestepaudio1_5'] = textencodeacestepaudio1_5.node.id

        conditioningzeroout = ConditioningZeroOut(
            _id='47',
            conditioning=textencodeacestepaudio1_5,
        )
        wf.metadata.setdefault('id_map', {})['conditioningzeroout'] = conditioningzeroout.node.id

        # Sampling
        ksampler = KSampler(
            _id='3',
            seed=DEFAULT_SEED,
            steps=1,
            cfg=GUIDE_STRENGTH,
            sampler_name='euler',
            latent_image=emptyacestep1_5latentaudio,
            model=modelsamplingauraflow,
            negative=conditioningzeroout,
            positive=textencodeacestepaudio1_5,
        )
        wf.metadata.setdefault('id_map', {})['ksampler'] = ksampler.node.id

        vaedecodeaudio = VAEDecodeAudio(_id='123', samples=ksampler, vae=vaeloader)
        wf.metadata.setdefault('id_map', {})['vaedecodeaudio'] = vaedecodeaudio.node.id
        # Outputs
        saveaudiomp3 = SaveAudioMP3(
            _id='59',
            filename_prefix='audio/vibecomfy_ace_step_smoke',
            audio=vaedecodeaudio,
        )
        wf.metadata.setdefault('id_map', {})['saveaudiomp3'] = saveaudiomp3.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one')

