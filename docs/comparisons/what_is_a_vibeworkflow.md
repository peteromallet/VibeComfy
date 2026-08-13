# What Is a VibeWorkflow?

## Why

Agents can't reason reliably about raw ComfyUI JSON.

ComfyUI speaks two JSON dialects, and both scatter meaning:

- UI JSON spreads a workflow across node ids, link arrays, positional widget arrays, and editor state.
- API JSON drops layout entirely and hides connections inside input values as link pairs like `["12", 0]`.

If every agent, recipe, and test has to re-decode that puzzle, every one of them will do it slightly differently — and often poorly. So VibeComfy makes one bet:

> When being used by agentically, a workflow should have one inspectable center that agents can easily read, edit, and validate — and everything else should be derived from it.

JSON stays what ComfyUI stores and executes. VibeWorkflow is what agents think about.

## How

The design follows four rules, all consequences of that one belief:

1. **One model in the middle.** Like a compiler's AST, VibeWorkflow is an intermediate representation. Every input dialect converges on it; every output is derived from it.

```text
from_ui ───────┐                              ┌── compile("api")
from_api ──────┼──▶ VibeWorkflow (the IR) ───┼── emit_ui_json(...)
from_envelope ─┘                              └── to_envelope()
```

2. **One meaning per fact.** Connectivity lives in `edges`; values live in `node.inputs`; public parameters (like prompt or seed) live in `workflow.inputs`. You never have to guess which field is authoritative.

3. **Derive, don't cache.** There is no stored `compiled_api`. `compile("api")` rebuilds the prompt fresh every time, so an edit can never be shadowed by a stale payload. Graphs are small; eliminating cache invalidation is worth the recompute.

4. **Preserve what you don't understand; be honest about what you can't guarantee.** Open bags (`metadata`, `groups`, `raw_widgets`) carry editor data VibeComfy doesn't own. Round-trips are scoped promises, not magic — and strict mode refuses rather than pretends.

## What

### Practically this is how this looks

Take two connected nodes from a text-to-video workflow — the `KSampler` and
the `VAEDecode` it feeds. On the ComfyUI canvas they are boxes with a wire
between them; as raw JSON — what an agent would otherwise read — they are
this, grouped in the workflow's `nodes` array:

```json
{
  "nodes": [
    {
      "id": 3,
      "type": "KSampler",
      "inputs": [
        {"name": "model", "type": "MODEL", "link": 95},
        {"name": "positive", "type": "CONDITIONING", "link": 46},
        {"name": "negative", "type": "CONDITIONING", "link": 52},
        {"name": "latent_image", "type": "LATENT", "link": 91}
      ],
      "outputs": [{"name": "LATENT", "type": "LATENT", "links": [35]}],
      "widgets_values": [82628696717253, "randomize", 30, 6, "uni_pc", "simple", 1]
    },
    {
      "id": 8,
      "type": "VAEDecode",
      "inputs": [
        {"name": "samples", "type": "LATENT", "link": 35},
        {"name": "vae", "type": "VAE", "link": 76}
      ],
      "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [96]}],
      "widgets_values": []
    }
  ]
}
```

The wire between them is not inside either node — it lives in the workflow's
separate `links` array:

```json
{
  "links": [
    [35, 3, 0, 8, 0, "LATENT"]
  ]
}
```

Accurate, but the agent's job is reconstruction: `35` is a link id, not a
value — the connection exists only as this positional tuple saying "link 35:
node 3's output 0 → node 8's input 0, a LATENT". Each node also carries other
dangling links (`95`, `46`, `52`, `91`, `76`) the agent must resolve
elsewhere. And `widgets_values` is a positional array with no names — the
seed is `82628696717253`, but nothing says which position is the seed. 

The VibeWorkflow layer says the same thing in ordinary code:

```python
ksampler = KSampler(
    _id='3',
    seed=82628696717253,
    steps=30,
    cfg=6,
    sampler_name='uni_pc',
    model=modelsamplingsd3,
    positive=positive,
    negative=negative,
    latent_image=emptyhunyuanlatentvideo,
)

vaedecode = VAEDecode(_id='8', samples=ksampler, vae=vaeloader)
```

Both describe the same graph. One is a puzzle to decode — link ids, a
separate link table, positional widget arrays — the other carries names,
call sites, and intent in one view. That is the entire reason the agent-edit
panel can act on "make the sampler faster" or "raise the cfg" without first
decoding a graph.

And this is not just a demo for two-node graphs — the same surface carries
everything a ComfyUI workflow can throw at it. Subgraphs — like the
`9b9009e4-…` uuid node from the example above, which stands for a whole
nested pipeline — materialize into a plain function you call with named
arguments:

```python
edited = text_to_image_z_image_base(
    width=1024,
    height=1024,
    unet_name='z_image_bf16.safetensors',
    clip_name='qwen_3_4b.safetensors',
    vae_name='ae.safetensors',
    prompt=prompt,
    steps=25,
    cfg=4,
)
```

LoRAs load as ordinary calls:

```python
loraloadermodelonly = LoraLoaderModelOnly(
    lora_name=LORA_NAME,
    strength_model=GUIDE_STRENGTH,
    model=unetloader,
)
```

Even whole custom-node ecosystems — audio, video, control nets, model
caching — appear as typed imports with their required node packs declared in
one place:

```python
from vibecomfy.nodes.wanvideowrapper import (
    WanVideoModelLoader,
    WanVideoSampler,
    WanVideoSetBlockSwap,
    WanVideoVAELoader,
)
```

The workflow keeps one inspectable center whether it is two nodes or two
hundred: named calls, explicit wiring, subgraphs as plain functions, custom
nodes as typed imports — and everything else derived from it.

For the fuller case for this representation, see
[Why Python, Not JSON?](why_python_not_json.md) — and for how this compares
with the ComfyScript-style alternative, see
[VibeComfy And ComfyScript](comfyscript.md).

### Getting in and out

```python
from vibecomfy.ingest import from_api, from_envelope, from_ui

wf = from_ui(ui_json)          # LiteGraph canvas export
wf = from_api(api_dict)        # ComfyUI prompt
wf = from_envelope(envelope)   # VibeComfy's versioned serialization

envelope = wf.to_envelope()    # the one writer
api_prompt = wf.compile("api") # fresh, portable execution payload
ui_json = wf.emit_ui_json()    # reconstructed canvas JSON
```

The envelope is not a second model — it's the IR serialized, versioned, read by exactly one decoder.

### A typical edit

```python
wf = from_ui(json.loads(Path("workflow.json").read_text()))
wf.set_input("prompt", "a brass automaton in a winter garden")

report = wf.validate()
if not report.ok:
    raise ValueError("; ".join(i.message for i in report.issues))

api_prompt = wf.compile("api")   # sees the edit, or fails loudly
```

### What round-trips actually promise

| Path | Guarantee |
| --- | --- |
| Envelope → IR → envelope | Structure and metadata preserved (provenance is deliberately re-tainted) |
| API → IR → API | Semantic equivalence, not byte-for-byte identity |
| UI → IR → UI | Best-effort, deterministic; strict mode refuses low-confidence widget reconstruction |
| API → IR → UI | Layout never existed, so it's synthesized |

### The shape

```python
@dataclass
class VibeWorkflow:
    id: str
    source: WorkflowSource
    nodes: dict[str, VibeNode]      # graph-local id -> node
    edges: list[VibeEdge]           # canonical connectivity — the one owner
    inputs: dict[str, VibeInput]    # public edit bindings (prompt, seed, ...)
    outputs: list[VibeOutput]
    requirements: WorkflowRequirements
    metadata: dict[str, Any]        # open bag, loss-preserving transport
    strict_types: bool = False
    groups: list[dict[str, Any]]    # LiteGraph group records
```

Key node details:

- **id vs uid:** `id` is the graph-local key (LiteGraph may renumber it on paste/merge); `uid` is VibeComfy's durable identity, stamped into `properties["vibecomfy_uid"]` on UI emission so round-trips survive renumbering.
- **mode** keeps LiteGraph's raw integers: 2 = muted, 4 = bypassed, everything else = active. An IntEnum would be prettier but would drop unfamiliar modes.
- **Widgets:** `raw_widgets` preserves the observed positional evidence for reconstruction; the editable values live in `inputs` and `widgets`. UI emission rebuilds `widgets_values` positionally — current values win, raw evidence fills gaps, schema defaults come last.

### Validation tiers

| Stage | When | On failure |
| --- | --- | --- |
| Edit-time binding | `set_input()`, `connect()`, etc. | Bad refs raise `ValueError`; type mismatches warn if `strict_types=True` |
| `validate()` | On demand | Returns a `ValidationReport` (structure, contracts, a real trial compile, optional schema checks) |
| `compile()` | Derivation | `WorkflowCompileError` with stable codes |
| Session preflight | Before queueing | `SchemaValidationError` with a `next_action`; drift and model-policy gates |

Requirements are also inferred structurally: dotted `class_type` prefixes become custom-node requirements; `*_name` fields with model-file extensions become model requirements.

### Provenance

Provenance is fail-closed. All external ingestion tags nodes `untrusted_source`, whatever the JSON claims; missing or unknown tags read the same way. `confirm_node()` promotes to `user_confirmed`. This prevents accidental confused-deputy actions — it is not hardened against an attacker who already controls the process.

### Legacy duality, visible not hidden

Hand-built inputs may still contain raw API link pairs, and `compile()` accepts them; if an edge covers the same field, the edge deterministically wins. New code should use edges only.

A deprecated shape-sniffing dispatcher still exists while callers migrate; named constructors are the contract.

## The one-sentence version

Because raw JSON is a reconstruction problem, VibeComfy gives every workflow one honest center — three doors in, one writer out, fresh compilation always — so agents reason about a model, not a puzzle.
