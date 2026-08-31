# Why Python, Not JSON?

The core question here is: what text representation of a Comfy workflow is best
for agents to understand and actually work with?

Earlier versions of VibeComfy tried to give agents better tools for working
directly with ComfyUI JSON. That helped in narrow cases, but it still forced the
agent to reconstruct intent from graph ids, links, widget arrays, and
node-specific conventions.

This version uses Python as the authoring surface instead. JSON remains the
import/export and runtime format; Python is the translation layer where agents
read, edit, validate, and compose workflows.

This is an authoring layer rather than an agent protocol;
[VibeComfy And Comfy MCP](comfy_mcp.md) explains that boundary.

## What Text Representation Is Best For Agents?

For example, imagine you are not looking at the ComfyUI canvas. You are an
agent reading text and trying to answer: what does this workflow load, what can
I change, what does it output, and what custom nodes does it need?

A typical exported ComfyUI workflow gives you nodes like this:

```json
{
  "id": 43,
  "type": "VHS_VideoCombine",
  "inputs": [
    {"name": "images", "type": "IMAGE", "link": 271},
    {"name": "audio", "shape": 7, "type": "AUDIO", "link": 270},
    {"name": "frame_rate", "type": "FLOAT", "widget": {"name": "frame_rate"}, "link": 201}
  ],
  "outputs": [{"name": "Filenames", "type": "VHS_FILENAMES", "links": null}],
  "widgets_values": {
    "frame_rate": 25,
    "filename_prefix": "LTX-2",
    "format": "video/h264-mp4",
    "crf": 19,
    "save_output": true,
    "videopreview": {"params": {"filename": "LTX-2_01647-audio.mp4"}}
  },
  "properties": {
    "cnr_id": "comfyui-videohelpersuite",
    "Node name for S&R": "VHS_VideoCombine"
  }
}
```

That is accurate data, but most of the agent's work is reconstruction: follow
link `271`, separate user intent from editor state, find the public inputs
elsewhere, and infer that this node is the final video output.

The translated VibeComfy layer says the same kind of thing in ordinary code:

```python
PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node=SymbolicNodeRef('image_2'), field='image', type='IMAGE', required=True),
    'prompt': InputSpec(node=SymbolicNodeRef('cliptextencode'), field='text', type='STRING', required=True),
    'middleframe_strength': InputSpec(node=SymbolicNodeRef('positive_4'), field='num_guides.strength_2', default=0.3),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    custom_node_packs={'ComfyUI-KJNodes': {...}, 'ComfyUI-LTXVideo': {...}, 'ComfyUI-VideoHelperSuite': {...}},
)

vhs_videocombine = VHS_VideoCombine(
    frame_rate=24.0,
    filename_prefix='LTX-2',
    format='video/h264-mp4',
    crf=19,
    images=vaedecodetiled,
)

return wf.finalize(
    PUBLIC_INPUT_METADATA,
    output_node=vhs_videocombine,
    output_type='VHS_VideoCombine',
    artifact_kind='video',
    mime_type='video/mp4',
    expected_cardinality='one',
)
```

Both representations compile to the same runtime graph. But if the task is to
work in text, the Python version gives the agent names, call sites, public
inputs, dependencies, and output contracts in one view.

## Why Python Probably Works Better

The important difference is not JSON syntax versus Python syntax in the
abstract. It is ComfyUI's graph-specific JSON versus ordinary Python code with
named calls, explicit metadata, and a compiler back to ComfyUI's API format.

LLMs have extensive general competence with Python code. ComfyUI workflow JSON
is a narrower schema: graph ids, link arrays, widgets, node-specific
conventions, editor state, and custom-node quirks all matter at once.

- **Better comprehension.** Named variables, functions, kwargs, imports, and
  metadata declarations give the agent clues about intent, not just graph ids.
- **Lower reasoning overhead.** The agent can use its existing code-editing
  patterns instead of reconstructing meaning from nested JSON and link arrays.
- **Fewer clarification loops.** A readable Python workflow carries intent
  beside structure, so agents need less extra explanation to know what they are
  allowed to change.
- **Local-model accessibility.** We expect smaller local models to benefit from
  leaning on general Python competence instead of learning ComfyUI's graph
  schema from scratch; that still needs systematic evaluation.
- **Universal composition.** Once the workflow is Python, ordinary Python can
  wrap it: recipes, parameter sweeps, validation, tests, and higher-level
  orchestration all become straightforward.

## Why Not Enrich The JSON?

JSON is the shape ComfyUI ultimately needs at queue time. But it is a poor
editing format for agents. It gives them nested data, ids, links, widget
positions, and class names, but not much meaning about what the workflow is
trying to do.

Improving the JSON would help to a point. You could imagine an enriched export
that adds public inputs, dependency contracts, and output semantics around the
raw graph:

```json
{
  "nodes": {"43": {"type": "VHS_VideoCombine", "inputs": {"images": "$node.120.IMAGE"}}},
  "public_inputs": {
    "prompt": {"node": "16", "field": "text", "type": "STRING"},
    "image": {"node": "44", "field": "image", "type": "IMAGE"}
  },
  "requirements": {
    "custom_node_packs": ["ComfyUI-KJNodes", "ComfyUI-LTXVideo", "ComfyUI-VideoHelperSuite"],
    "models": ["LTX23_video_vae_bf16_KJ.safetensors"]
  },
  "outputs": {
    "video": {"node": "43", "type": "video/mp4", "cardinality": "one"}
  }
}
```

That would be better than raw graph JSON. But it only really works if ComfyUI
itself owns the format and every exporter, loader, extension, and downstream
tool preserves those fields. As an external tool, adding new semantics to the
exported JSON shape risks backward-compatibility problems with existing
workflows and existing ComfyUI expectations.

It would still be worse than Python for agent editing. The agent would be
decoding a richer data schema rather than editing a familiar programming
surface. The more meaning you add around graph JSON, the closer you get to
inventing a second authoring language beside it.

Any external representation has to track ComfyUI changes. The point of the
Python layer is to centralize that adaptation while giving agents a better text
format to edit.

VibeComfy takes the opposite route: translate the graph into ordinary Python,
let the agent work there, then compile back to the API JSON that ComfyUI already
accepts.

## Challenge: The Representation Must Stay Faithful

The real challenge for the Python approach is faithful translation. It has to
preserve the graph semantics needed for execution. VibeComfy is designed to
carry nodes, edges, widget values, public inputs, outputs, custom-node
requirements, model assets, subgraphs, and provenance through the Python layer.
For UI round-trips, editor layout is preserved where it is available.

That is the core bet: do not make agents become native ComfyUI JSON editors.
Give them a translation layer in the programming language where they already
show the strongest general competence. The object at the center of that layer
is described in [What Is a VibeWorkflow?](what_is_a_vibeworkflow.md).
