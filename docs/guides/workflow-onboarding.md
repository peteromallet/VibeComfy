# Import and edit a ComfyUI workflow

For ordinary Python functions that should appear as editable executable graph
nodes, see [Custom Python workflow nodes](custom-python-workflows.md). That
guide covers inline functions, complete source capsules, installed packages,
the CLI, and runtime validation.

Hivemind is the canonical public source for community workflows. Search it
through Astrid, select an accepted resource/revision, and pull that one source
on demand before importing. VibeComfy keeps the resulting bundle in the local
`workflows/` ingestion store; it does not bulk-mirror the public catalogue.

Import turns the selected ComfyUI JSON workflow into a canonical bundle that
you or a coding agent can inspect and edit. Start in the directory where you
want to keep your workflows. These examples assume VibeComfy is installed; in
an editable checkout, `python -m vibecomfy.cli` is equivalent to `vibecomfy`.

## 1. Import the source

```bash
vibecomfy import path/to/my_workflow.json
```

This creates a folder relative to your current directory:

```text
workflows/my_workflow/
  workflow.py
  workflow.vibe.json
  source.json
```

| File | What it is for |
| --- | --- |
| `workflow.py` | Your editable workflow: node calls, values, and connections. |
| `workflow.vibe.json` | VibeComfy's companion data for identity, source bookkeeping, and visual layout. Keep it beside the Python file. |
| `source.json` | The unchanged original JSON, for comparison or a fresh import. Editing it does not change `workflow.py`. |

Source hashes and conversion provenance use the existing bundle metadata.
There is no separate import manifest. Move or share the whole folder to keep
these files together; importing preserves the graph, not the models or custom
node packages it depends on.

Import converts JSON without executing its generated Python. Commands that
load `workflow.py` (such as bundle inspection, editing, and validation) build
the Python workflow and therefore pass through VibeComfy's source-execution
gate. In an interactive terminal, review and confirm the prompt. In a trusted
non-interactive job, make the opt-in explicit:

```bash
vibecomfy --yes inspect workflows/my_workflow
vibecomfy --yes edit workflows/my_workflow set sampler.steps 30
vibecomfy --yes validate workflows/my_workflow
```

`--yes` is audited as an explicit bypass. `--non-interactive` refuses if the
source has not been authorized; do not add `--yes` to automate unreviewed
workflow code. `vibecomfy node <ClassType>` reads node source as text and does
not import it. The Astrid-native task route records workflow changes in
Astrid's task history and requires its own explicit Python-execution consent
for canonical bundles; see the Astrid task examples below.

The folder name comes from the source filename, with unusual characters
sanitized. Use the path printed by the command. To choose a destination:

```bash
vibecomfy import path/to/my_workflow.json --out workflows/my_variant
```

`--out` names a **directory**, not a Python file. Existing destinations are
refused so an import cannot replace your edits. `--dry-run` previews the
conversion without creating the output folder; `--json` returns the result
and diagnostics for scripts or agents. By default this is local work: the
bundle lives on disk and is not recorded in Astrid.

To record the imported workflow and later accepted edits in an existing Astrid
project, opt in explicitly:

```bash
vibecomfy import path/to/my_workflow.json --project demo
```

This standalone CLI route submits project-scoped Astrid tasks for origin and
subsequent changes. The project must already exist. Without `--project`, the
CLI stays local and reports `tracking: untracked`. If you are already working
inside Astrid, use Astrid's native task route instead; it imports the raw file
with `astrid media import`, then creates one `vibecomfy.import` task to record
the canonical origin. See Astrid's [VibeComfy CLI journey](https://github.com/peteromallet/Astrid/blob/main/docs/guides/cli-journeys.md#vibecomfy-import-inspect-edit-validate-run)
for that invocation and the history commands. Astrid-native executors inherit
the admitted task and project context; they do not take VibeComfy's
`--project` option or create a nested task.

## 2. Find what you want to change

The import result prints the file paths and follow-up commands. You can open
`workflow.py` immediately. When you want help understanding it, these optional
commands describe the workflow built from that code:

```bash
vibecomfy edit workflows/my_workflow targets
vibecomfy inspect workflows/my_workflow
vibecomfy analyze info workflows/my_workflow
```

`edit targets` lists this graph's editable node instances, stable UIDs,
readable targets, classes, and fields. `inspect` and `analyze info` summarize
graph details, public inputs/outputs, and declared model and custom-node
requirements. These commands inspect the loaded Python and companion; they do
not merely print the source file. Use the graph-specific targets and fields to
locate corresponding calls in `workflow.py`.

To understand one node, use its ComfyUI class name:

```bash
vibecomfy node SaveImage
```

By default this shows the node's identity and schema provenance, all known
inputs and outputs, and its implementation class source when that source is
available locally. Inputs include types, required flags, defaults, choices,
and ranges where known. Outputs include socket names and types.

Ask for only the sections you need:

```bash
vibecomfy node SaveImage --inputs
vibecomfy node SaveImage --outputs
vibecomfy node SaveImage --source
vibecomfy node SaveImage --inputs --outputs
```

Add `--json` to any of these commands for structured output. A schema can be
available from cached ComfyUI metadata even when the implementation source is
not installed. In that case the default view still shows the interface and
explains why source is unavailable. An explicit `--source` request exits
nonzero when unavailable, even with other filters. Source lookup reads local
Python files without importing the
custom node or starting ComfyUI. It shows the implementation class, not all
of the helper code or dependencies that class may call.

Source lookup uses your configured custom-node directory and local ComfyUI
installation. If needed, point it at a checkout explicitly:

```bash
COMFYUI_PATH=/path/to/ComfyUI vibecomfy node SaveImage --source
```

Use `vibecomfy nodes list` to discover class names. If you have a captured
ComfyUI `/object_info` response, `--object-info-cache <file.json>` selects that
schema evidence. The existing `vibecomfy nodes spec <ClassType>` remains
available as the schema-only JSON interface.

Some workflows also expose named public controls. `analyze info` lists their
inputs; `inspect --field <name>` traces an existing public control to its node
and field. A workflow need not expose every prompt, seed, or step count as a
public control: you can still edit its existing Python node arguments. For a
node class's general schema and implementation, use
`vibecomfy node <ClassType>`; this describes the class, while
`edit targets` describes the specific editable instances in this workflow.

Inspection can report missing schemas. If that prevents it from describing
the graph, use `doctor` as described below and read the generated Python in
the meantime.

## 3. Edit the workflow

For a small graph change, use the VibeComfy edit command. It resolves targets
from this bundle, applies typed operations through the canonical edit service,
and updates the Python/companion pair together. A batch is one ordered,
atomic transition, so an added node can be named by a later operation in that
same batch:

```bash
vibecomfy edit workflows/my_workflow set sampler.steps 30
vibecomfy edit workflows/my_workflow set prompt.text --value-file prompts/alternate.txt
vibecomfy edit workflows/my_workflow batch edits.json
vibecomfy edit workflows/my_workflow --project demo set sampler.steps 30
```

The positional value is parsed as JSON when possible and otherwise treated as
text. Use `--value-file` for a long or multiline string; the file contents are
used exactly, including line breaks, without shell quoting or JSON escaping.

The command family also has `add`, `remove`, `connect`, `disconnect`, and
`mode`. `edit <bundle> targets` lists the graph-specific target names and
fields; `vibecomfy node <ClassType>` gives the class schema. `add` accepts an
explicit `--uid` so a later operation in the same batch can reference the new
node. Connections name a source node, target node, and target input;
`--source-output` selects a named output or index when needed.

```text
vibecomfy edit <bundle> [--project demo] add <ClassType> [--uid <uid>] [--fields '<JSON>'] [--inputs '<JSON>']
vibecomfy edit <bundle> [--project demo] remove <target>
vibecomfy edit <bundle> [--project demo] connect <source> <target> <target_input> [--source-output <output>]
vibecomfy edit <bundle> [--project demo] disconnect <target> <target_input>
vibecomfy edit <bundle> [--project demo] mode <target> enabled|muted|bypassed
```

For example, this ordered batch adds a node with a stable UID, then refers to
that new node in the next operation:

```json
{
  "schema_version": 1,
  "expected_revision": 0,
  "ops": [
    {"op": "add_node", "class_type": "Integer", "uid": "new-integer", "fields": {"value": 2}},
    {"op": "edit_node", "target": "new-integer", "field": "value", "value": 3}
  ]
}
```

This adds an `Integer` node and changes it in the next operation using the
explicit UID. The same batch can also connect a newly added node by referring
to its UID in a later `upsert_link`. For another node class, check
`vibecomfy node <ClassType>` and use `edit targets` to identify existing
endpoints. Save the operations as `edits.json`, then run:

```bash
vibecomfy edit workflows/my_workflow batch edits.json
```

Pass `-` (or omit the filename) to read the same JSON from standard input.
The wrapper and its ordered `ops` list are one transition.

Place `--project demo` after the bundle and before the edit verb to record an
accepted change in Astrid. Local mode is the default. `--dry-run` previews
without saving, and `--out <directory>` writes a separate bundle while keeping
the input unchanged. Each successful batch produces one accepted revision; a
failed batch leaves the saved bundle unchanged. The command reports the files
and the matching validation command.

To make several related changes together, save an ordered operation list in
`edits.json` and pass it to `batch` (or use `-` to read the same document from
standard input). The JSON batch is the automation surface; named verbs are
convenient forms of those typed operations. See the [edit skill](../agent-skill/skills/edit-comfy-workflow/SKILL.md)
for operation details and examples.

You can also edit the Python directly. Open
`workflows/my_workflow/workflow.py` and change the existing argument that
controls the behavior you want. For example, if a `SaveImage` call contains:

```python
filename_prefix='out/port'
```

change that argument to:

```python
filename_prefix='out/edited'
```

This changes the output filename prefix when the workflow is eventually run.
Keep the surrounding node call and its image connection intact. Prompts,
seeds, and step counts can be adjusted at their corresponding calls in the
same way. Confirm unfamiliar argument names with `vibecomfy node <ClassType> --inputs`.

For graph changes, use the Python node calls and supported `VibeWorkflow`
methods such as `add_node`, `connect`, and `remove_node`. The
[editing skill](../agent-skill/skills/edit-comfy-workflow/SKILL.md) explains the
agent workflow; [Authoring](../authoring.md) covers Python composition.
The companion JSON is maintained by VibeComfy: do not repair validation
errors by manually changing its identity or binding fields.

After directly editing Python, run:

```bash
vibecomfy edit workflows/my_workflow capture
```

Capture publishes the canonical pair and records the aggregate change without
inventing individual edit operations. When no trusted pre-capture snapshot is
available, capture starts a new baseline and reports that the earlier graph
diff is unavailable. Add `--project demo` before `capture` to record it in
Astrid. A ComfyUI browser candidate or canvas Apply is not tracked
automatically; capture it explicitly if it should enter project history.

Typed edits and UI capture regenerate Python from the canonical workflow graph.
If captured `workflow.py` includes extra executable Python that the graph cannot
represent, VibeComfy refuses to rewrite it and leaves the bundle unchanged.
Continue editing that Python and capture it, or restore a canonical generated
source before using typed edits.

For a tracked import or edit, the command prints the Astrid task ID and history
commands. Inspect the event history with `astrid tasks show <TASK_ID>` and
`astrid tasks events <TASK_ID>`. If VibeComfy times out after the task was
admitted, resume materialization with:

```bash
vibecomfy recover <TASK_ID>
```

Recovery reads the already-settled task output digests and never admits a
second edit. If the local bundle changed while the task was running, VibeComfy
preserves that folder and refuses to replace it; pass `--out <directory>` to
write the settled task result as a separate bundle.

## 4. Validate the edited workflow

After saving your edit, run:

```bash
vibecomfy validate workflows/my_workflow
```

A successful check prints `ok`. Validation reloads the Python and companion,
checks their relationship, and checks compilation against the available node
schemas. It does not queue generation. An error should be fixed in the
workflow or its dependencies, then checked again.

Read warnings as well as the exit status: a schema-less fallback means some
node details could not be checked, even if the command completed successfully.

To investigate missing node schemas, models, or other dependency findings:

```bash
vibecomfy doctor workflows/my_workflow
```

`doctor` uses local information. Model-presence checks depend on a configured
`VIBECOMFY_MODELS_ROOT`; it cannot inventory an unconfigured remote server.

A successful import means an editable bundle was created. A successful
validation means the available checks passed. Neither establishes that a
particular ComfyUI server has all the dependencies or that generation will
succeed.

Both commands accept `workflow.py` directly as well as the folder. Always
validate the file or folder you actually edited. Add `--json` for structured
results and use the exit status to detect failures in automation.

## If something needs attention

| Situation | Next step |
| --- | --- |
| The destination already exists | Open that folder to continue editing, or import to a different `--out` directory. |
| A class schema is missing | Run `doctor` on the imported folder. `vibecomfy schemas ensure workflows/my_workflow/workflow.py` is the schema-recovery entry point; follow its diagnostics for your environment. |
| You want a limited structural check while schemas are missing | Use `vibecomfy validate workflows/my_workflow --no-schema`. This is a weaker check, not full schema validation. |
| Import reports `unsupported_boundary_encoding` | The source contains a native subgraph boundary the importer cannot safely represent. No completed folder is published. Keep the source and the diagnostic when reporting the problem. |
| A load asks for confirmation | Loading authored Python follows the existing capability policy. In intentional unattended use, `--yes` accepts those prompts; `--non-interactive` refuses actions that require confirmation. |

## Make a separate variation with Python

Directly editing the imported Python is the shortest path. If you want a
separate recipe that loads it and changes public controls, save the following
as **`recipes/workflow_variation.py`**, not as the imported `workflow.py`:

```python
from vibecomfy.cli_loader import load_bundle


def build():
    wf = load_bundle("workflows/my_workflow").workflow
    wf.set_prompt("a glass teapot on basalt")
    wf.set_seed(42)
    wf.set_steps(20)
    return wf.finalize_metadata()
```

This example requires the loaded workflow to expose those public controls.
Run from the project directory so its relative path resolves, and validate
**the variation**:

```bash
vibecomfy validate recipes/workflow_variation.py
```

The variation depends on the imported folder. Keep both when moving it to
another project.

## Next steps

- **Run the edited workflow:** follow the [run-workflow skill](../agent-skill/skills/run-comfy-workflow/SKILL.md) to choose a runtime and check its dependencies.
- **Export back to ComfyUI:** see [Emitting a UI view](../authoring.md#emitting-a-ui-view).
- **Add a reusable library template:** follow [Adding templates and models](../templates/adding_templates_models.md).
- **Use advanced conversion controls:** the [porting workbench](../templates/porting_workbench.md) documents `port check`, `port convert`, and strict-ready promotion. `workflows onboard` prints a multi-step plan; it does not execute an import.
