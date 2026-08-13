# VibeComfy And ComfyScript

ComfyScript compiles a graph into runnable-looking Python. VibeComfy translates
a graph into an inspectable, self-describing workflow contract for agents.

ComfyScript gives you a compact Python script view of a graph. That can be good
for CLI use or for a human who already understands the workflow in the editor.
VibeComfy is agent-native: the Python is meant to carry the graph, public inputs,
subgraphs, dependencies, provenance, and output contract in one inspectable view.

## The Difference

| Concern | ComfyScript-style output | VibeComfy output |
|---|---|---|
| Goal | Script a graph. | Translate a graph into an agent-editable workflow. |
| Shape | One compact procedural file. | Ready template or recipe built around `VibeWorkflow`. |
| Complex features | Subgraph boundaries are lost; helpers are inlined without names or provenance. | Subgraphs can become named Python functions with provenance. |
| Inputs | Values are mostly inline arguments. | Public inputs are declared with `InputSpec`. |
| Dependencies | This example does not carry model/node-pack requirements as a contract. | `ReadyMetadata` records models, custom-node packs, commits, schema hashes, runtime packages, and source provenance. |
| Agent use | The agent must infer intent from order, positional args, `None`, and comments. | The agent can inspect explicit metadata, named kwargs, sections, public inputs, and output contracts. |

## Example: First/Middle/Last Frame

Both snippets below come from generated Python views of the same complex LTX
first/middle/last-frame workflow.

The ComfyScript-style output is short, but the important meaning is mostly
implicit:

```python
# _ = LTXVPreprocess(image, 18)
image2, width2, height2, _ = ImageResizeKJv2(None, 32, height, image2, 'crop', None, 'lanczos', width, 'cpu', None)
image2 = ResizeImagesByLongerEdge(image2, 1536)
# _ = LTXVPreprocess(image2, 18)

string = TextGenerateLTX2Prompt(clip, None, string, 'off', resized2, True)
string = ComfySwitchNode(prompt, string, True)
conditioning = CLIPTextEncode(clip, string)
positive, negative = LTXVConditioning(24.0, conditioning2, conditioning)
resized2 = ImageStitch(None, _, None, None, None, resized2)

latent = EmptyLTXVLatentVideo(None, int2, int3, int)
positive2, negative2, latent = LTXVAddGuideMulti(latent, negative, None, positive, vae)
model = LTX2AttentionTunerPatch(None, None, None, model, None, None, None)
latent, _ = SamplerCustomAdvanced(guider, latent, noise, sampler, sigmas)

# _ = VHSVideoCombine('LTX-2', 'video/h264-mp4', 24.0, image4, None, None, None, None, None, None)
```

For an agent, this is a weak surface. The graph is flattened. Several important
calls depend on positional `None` placeholders. The `_` value is used as a real
variable in `ImageStitch(...)`, so the script would raise `NameError` if `_` was
not assigned by earlier execution. The final video node is commented out, so an
agent cannot tell whether the missing output is intentional, vestigial, or a
conversion error.

There is also no local contract that says which values are safe user inputs,
which node packs and models must exist, or what artifact the workflow promises
to produce.

VibeComfy preserves that context:

```python
PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node=SymbolicNodeRef('comfyswitchnode'), field='switch', default=True),
    'middleframe_strength': InputSpec(node=SymbolicNodeRef('positive_4'), field='num_guides.strength_2', default=0.3),
    'seed': InputSpec(node=SymbolicNodeRef('randomnoise'), field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node=SymbolicNodeRef('image_2'), field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'prompt': InputSpec(node=SymbolicNodeRef('cliptextencode'), field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_video_vae_bf16_KJ.safetensors', ...]},
    custom_node_packs={'ComfyUI-KJNodes': {...}, 'ComfyUI-LTXVideo': {...}},
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch / PathchSageAttentionKJ'}],
)

def prompt_enhancer(*, clip, image, enabled, prompt, _public_input_refs=None):
    """PROMPT ENHANCER - single-image variant.

    Materialized from subgraph 8fa4f93a-67ee-463f-ba43-249580c0bfb1.
    Inner nodes: StringConcatenate, ComfySwitchNode, TextGenerateLTX2Prompt.
    """
    ...

return wf.finalize(
    PUBLIC_INPUT_METADATA,
    output_node=vhs_videocombine,
    output_type='VHS_VideoCombine',
    name='video',
    artifact_kind='video',
    mime_type='video/mp4',
    expected_cardinality='one',
    filename_prefix='LTX-2',
)
```

That extra structure is the point. It gives an agent a single view of what the
workflow is, what can be changed, what must be installed, where subgraphs came
from, how to validate the result, and what ComfyUI should receive at runtime.

## The Design Choice

ComfyScript proves that Python is a useful way to control ComfyUI. VibeComfy
takes the same basic idea further: Python becomes the durable translation layer
for agentic editing.

The goal is not the shortest script. The goal is a workflow representation that
lets an agent safely understand, patch, compose, validate, export, and run modern
ComfyUI graphs. The shape of that representation is the
[What Is a VibeWorkflow?](what_is_a_vibeworkflow.md) object.
