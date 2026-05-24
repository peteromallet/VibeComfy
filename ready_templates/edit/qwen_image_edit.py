# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGNorm, CLIPLoader, ComfySwitchNode, ImageScaleToTotalPixels, KSampler, LoadImage, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, TextEncodeQwenImageEdit, UNETLoader, VAEDecode, VAEEncode, VAELoader

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


DEFAULT_PROMPT = 'Remove all UI text elements from the image. Keep the feeling that the characters and scene are in water. Also, remove the green UI elements at the bottom.'
DEFAULT_SEED = 344147753686358
MODEL_NAME = 'qwen_image_edit_fp8_e4m3fn.safetensors'
MODEL_NAME_2 = 'qwen_2.5_vl_7b_fp8_scaled.safetensors'
MODEL_NAME_3 = 'qwen_image_vae.safetensors'
MODEL_NAME_4 = 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors'


MODELS = {
    'qwen_image_edit_fp8_e4m3fn': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors', sha256='393c6743d1de2e9031b5197027b36116f2096958ccc0223526d34e1860266021', hf_revision='83ae44f23af827155718b906c7dcc195a37c60b4', size_bytes=20430635136, subdir='diffusion_models'),
    'qwen_2_5_vl_7b_fp8_scaled': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors', sha256='cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=9384670680, subdir='text_encoders'),
    'qwen_image_vae': ModelAsset(url='https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors', sha256='a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f', hf_revision='c232bcb51c1523899c62d6dcaa960b2627668de5', size_bytes=253806246, subdir='vae'),
    'qwen_image_edit_lightning_4steps_v1_0_bf16': ModelAsset(url='https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors', sha256='d8132c32e7df906603dd6b072ff2fb0af88ab15ef0f3ac697a2011c8b47bbeb1', hf_revision='e74da8d4e71a54b341de86aa9f8d2509165aa513', size_bytes=849608296, subdir='loras'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('unetloader'), field='unet_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('textencodeqwenimageedit'), field='prompt', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('ksampler'), field='seed', default=DEFAULT_SEED),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'sampler_name': InputSpec(node=ref('ksampler'), field='sampler_name', default='euler'),
    'source_image': InputSpec(node=ref('image'), field='image', default='image_qwen_image_edit_input_image.png'),
    'input_image': InputSpec(node=ref('image'), field='image', default='image_qwen_image_edit_input_image.png'),
    'image': InputSpec(node=ref('image'), field='image', default='image_qwen_image_edit_input_image.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    provenance={'source_workflow': 'workflow_corpus/official/edit/qwen_image_edit.json'},
)

# === Subgraph functions ===

def qwen_image_edit(
    *,
    image,
    prompt: str,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    lora_name: str,
    enable_turbo_mode: bool,
):
    """Qwen-Image-Edit - single-image variant.

    Materialized from subgraph 74a8e1e2-9cb8-4112-978e-06ce1b5793f1 in workflow_corpus/official/edit/qwen_image_edit.json.
    Inner nodes: VAELoader, TextEncodeQwenImageEditx2, CFGNorm, ModelSamplingAuraFlow, VAEDecode, CLIPLoader, VAEEncode, MarkdownNote, LoraLoaderModelOnly, UNETLoader, PrimitiveFloatx2, PrimitiveIntx2, PrimitiveBoolean, KSampler, ComfySwitchNodex3.
    """

    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type_='qwen_image', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    markdownnote = raw_call('MarkdownNote', '97',
        widget_0='You can test and find the best setting by yourself. The following table is for reference.\n\n| Model            | Steps | CFG |\n|---------------------|---------------|---------------|\n| Offical             | 50               | 4.0               \n| comfy             | 20                | 2.5               |\n| fp8_e4m3fn + 4steps LoRA    | 4               | 1.0               |\n',
    )

    primitiveint = raw_call('PrimitiveInt', '103',
        value=4,
        control_after_generate='fixed',
    )

    primitivefloat = raw_call('PrimitiveFloat', '105', value=1)

    primitiveint_2 = raw_call('PrimitiveInt', '106',
        value=20,
        control_after_generate='fixed',
    )

    primitivefloat_2 = raw_call('PrimitiveFloat', '107', value=2.5)
    primitiveboolean = raw_call('PrimitiveBoolean', '111', value=enable_turbo_mode)

    textencodeqwenimageedit = TextEncodeQwenImageEdit(
        prompt=prompt,
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    textencodeqwenimageedit_2 = TextEncodeQwenImageEdit(
        prompt='',
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    vaeencode = VAEEncode(pixels=image, vae=vaeloader)
    loraloadermodelonly = LoraLoaderModelOnly(lora_name=lora_name, model=unetloader)

    comfyswitchnode_2 = ComfySwitchNode(
        widget_0=False,
        on_false=primitivefloat_2,
        on_true=primitivefloat,
        switch=primitiveboolean,
    )

    comfyswitchnode_3 = ComfySwitchNode(
        widget_0=False,
        on_false=primitiveint_2,
        on_true=primitiveint,
        switch=primitiveboolean,
    )

    comfyswitchnode = ComfySwitchNode(
        widget_0=False,
        on_false=unetloader,
        on_true=loraloadermodelonly,
        switch=primitiveboolean,
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=comfyswitchnode)
    cfgnorm = CFGNorm(widget_0=1, model=modelsamplingauraflow)

    ksampler = KSampler(
        seed=344147753686358,
        sampler_name=1,
        scheduler='euler',
        denoise='simple',
        widget_6=1,
        steps=comfyswitchnode_3,
        cfg=comfyswitchnode_2,
        latent_image=vaeencode,
        model=cfgnorm,
        negative=textencodeqwenimageedit_2,
        positive=textencodeqwenimageedit,
    )

    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(image='image_qwen_image_edit_input_image.png')

        # Loaders
        unetloader = UNETLoader(unet_name=MODEL_NAME)
        cliploader = CLIPLoader(clip_name=MODEL_NAME_2, type_='qwen_image')
        vaeloader = VAELoader(vae_name=MODEL_NAME_3)

        # Inputs
        primitiveint = raw_call('PrimitiveInt', '102:103', value=4)
        primitivefloat = raw_call('PrimitiveFloat', '102:105', value=1)
        primitiveint_2 = raw_call('PrimitiveInt', '102:106', value=20)
        primitivefloat_2 = raw_call('PrimitiveFloat', '102:107', value=2.5)
        primitiveboolean = raw_call('PrimitiveBoolean', '102:111', value=False)

        imagescaletototalpixels = ImageScaleToTotalPixels(
            upscale_method='lanczos',
            megapixels=1.5,
            image=image,
        )

        textencodeqwenimageedit = TextEncodeQwenImageEdit(
            prompt=DEFAULT_PROMPT,
            clip=cliploader,
            image=image,
            vae=vaeloader,
        )

        textencodeqwenimageedit_2 = TextEncodeQwenImageEdit(
            prompt='',
            clip=cliploader,
            image=image,
            vae=vaeloader,
        )

        vaeencode = VAEEncode(pixels=image, vae=vaeloader)

        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=MODEL_NAME_4,
            model=unetloader,
        )

        comfyswitchnode = ComfySwitchNode(
            on_false=primitivefloat_2,
            on_true=primitivefloat,
            switch=primitiveboolean,
        )

        comfyswitchnode_2 = ComfySwitchNode(
            on_false=primitiveint_2,
            on_true=primitiveint,
            switch=primitiveboolean,
        )

        comfyswitchnode_3 = ComfySwitchNode(
            on_false=unetloader,
            on_true=loraloadermodelonly,
            switch=primitiveboolean,
        )

        modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=comfyswitchnode_3)
        cfgnorm = CFGNorm(model=modelsamplingauraflow)

        # Sampling
        ksampler = KSampler(
            seed=DEFAULT_SEED,
            sampler_name='euler',
            steps=comfyswitchnode_2,
            cfg=comfyswitchnode,
            latent_image=vaeencode,
            model=cfgnorm,
            negative=textencodeqwenimageedit_2,
            positive=textencodeqwenimageedit,
        )

        # Decode
        vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

        # Outputs
        saveimage = SaveImage(images=vaedecode)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

