# Custom Python workflow nodes

VibeComfy supports readable Python functions as ordinary, visible ComfyUI
nodes. The function body is not called while a graph is being built. Calling a
function proxy lowers one `vibecomfy.exec` node with fixed physical `in_N` /
`out_N` sockets and a semantic typed `io` contract.

## Inline functions

```python
from vibecomfy import VibeWorkflow, python_node


@python_node(inputs={"value": "INT", "gain": "INT"}, outputs={"value": "INT"})
def multiply(value: "INT", gain: "INT" = 2) -> "INT":
    return {"value": value * gain}


def build() -> VibeWorkflow:
    workflow = VibeWorkflow("custom-python")
    first = multiply(workflow, value=3)
    second = multiply(workflow, value=first.value, gain=4)
    return workflow.finalize_metadata()
```

Every call is a separate editable graph node. Handles use the declared output
names (`first.value`), while the serialized graph uses `in_0` and `out_0`
so the existing edit, compile, and queue paths remain authoritative. Literals
and defaults are captured as node values; wires remain ordinary graph edges.

Use `result=outputs(...)` when a function returns an ordered tuple/list or a
single value. Result adaptation is explicit; VibeComfy never guesses whether a
list or mapping should be unpacked.

## Complete modules and installed packages

Use a source capsule for a complete module or project. Preparation reads and
hashes selected files without importing them; runtime imports the verified
digest-qualified snapshot only at the existing `vibecomfy.exec` execution
boundary.

```python
from vibecomfy import python_node

process = python_node.from_source(
    "image_tools",
    entrypoint="pipeline:process",  # relative to the package root
    inputs={"image": "IMAGE"},
    outputs={"image": "IMAGE"},
)
```

`from_installed` declares a worker-installed package and keeps its ordinary
fully qualified import name, including absolute self-imports:

```python
process = python_node.from_installed(
    entrypoint="image_tools.pipeline:process",
    inputs={"image": "IMAGE"},
    outputs={"image": "IMAGE"},
)
```

Snapshot entrypoints are `module:function` relative to `package_root`;
installed entrypoints are fully qualified. Snapshot files are bounded to 4 MiB
encoded, 16 MiB expanded, and 512 members. Relative imports and selected small
data files are preserved. Dependencies are inspected in the selected ComfyUI
worker, but imports and installations never happen during validation or
inspection. Install missing distributions through normal setup tooling first.
The read-only `vibecomfy.inspect_dependency_readiness(payload)` helper reports
the selected worker's installed versions and never installs anything.

## Editing and validation

The CLI uses the same canonical edit service as typed and canvas edits:

```bash
vibecomfy edit workflows/custom-python exec add \
  --source-body "return {'value': value + 1}" \
  --ports ports.json --bindings bindings.json --uid increment
vibecomfy edit workflows/custom-python exec inspect increment --json
vibecomfy edit workflows/custom-python exec export increment --destination exported_source
vibecomfy validate workflows/custom-python
```

Use `--dry-run` to prove that an add or update publishes no files. Source,
interface, and wiring changes are one atomic transition. Shared inline
definitions can be updated together; an explicitly selected instance can be
copied on edit. A native canvas edit is captured as an aggregate canonical
state and must pass the same revision and identity checks.

The readable `workflow.py` is the semantic authoring surface. The companion
`workflow.vibe.json` owns identity, presentation, and custody evidence; it is
not a second graph authority. `source.json` remains the unchanged original
import evidence. Inspecting, validating, and emitting do not execute source;
queueing the workflow executes `vibecomfy.exec` in process with ComfyUI's full
privileges and without a reliable timeout.

For a real result, run through an existing worker and inspect the run evidence:

```bash
vibecomfy run workflows/custom-python --runtime server --server-url http://127.0.0.1:8188
# inspect out/runs/<run-id>/metadata.json and the collected outputs
```

The server must already have the declared installed packages, custom nodes,
and models. A no-GPU unit call is useful for contract tests but does not prove
that Comfy's queue accepted and executed the graph.

## Pip-installed ComfyUI validation

The optional `comfy` extra exercises the installed ComfyUI package without
requiring a full checkout:

```bash
python3.11 -m venv .venv-comfy-smoke
.venv-comfy-smoke/bin/python -m pip install -e '.[dev,comfy]' \
  --extra-index-url https://nodes.appmana.com/simple/
VIBECOMFY_COMFY_SMOKE=1 .venv-comfy-smoke/bin/python -m pytest -q \
  tests/test_porting_ui_emitter.py::test_comfy_release_smoke_convert_ui_to_api \
  tests/test_layer4_smoke.py::test_layer4_zod_conformance
```

The Layer 4 test also needs the `zod` npm package available to Node.js. These
smokes validate the emitted LiteGraph envelope and ComfyUI's
`convert_ui_to_api`; they do not download models or claim that a queue ran.
The corpus-wide Layer 3 gate remains a separate compatibility check because
the pip converter intentionally omits virtual and subgraph-interior UI nodes;
VibeComfy keeps its identity-preserving fail-closed behavior when that output
cannot be mapped bijectively to the source UI graph.
