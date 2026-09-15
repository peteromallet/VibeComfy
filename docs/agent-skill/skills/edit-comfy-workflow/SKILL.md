---
name: edit-comfy-workflow
description: Edit an existing VibeComfy or ComfyUI workflow, ready template, recipe, scratchpad, or target graph. Use when the user asks to tweak prompts/seeds/steps/resolution, alter nodes, splice a pattern into a workflow, convert JSON to editable Python, or make a graph change without necessarily running it.
---

# Edit Comfy Workflow

Use this when the graph needs to change. Follow the same shape as the agentic tests: identify the target, inspect it, materialize an editable Python surface if needed, make the smallest graph change, then validate.

## Shared Edit Spine

Use the same spine as the Comfy app agent edit path and the structural/live agentic tests:

```text
target graph -> inspect/research -> Python editable surface -> VibeWorkflow edit -> finalize_metadata -> validate/doctor -> candidate or run
```

For package-side edits, the editable surface is a recipe, scratchpad, or ready template. For the Comfy app, the same idea returns a candidate UI graph plus apply eligibility. Do not treat an edit candidate as an executed result; execution belongs to `run-comfy-workflow`.

## Fast Path

```bash
vibecomfy inspect <target>
vibecomfy analyze info <target>
```

If the target is raw JSON, load it only as import evidence and materialize Python before editing:

```bash
vibecomfy import <workflow.json>
vibecomfy inspect workflows/<source-stem> --json
vibecomfy edit workflows/<source-stem> targets
vibecomfy edit workflows/<source-stem> set sampler.steps 30
vibecomfy validate workflows/<source-stem> --json
```

The import folder contains editable `workflow.py`, its canonical
`workflow.vibe.json` companion, and byte-identical `source.json`; provenance
stays in the bundle metadata. Standalone import and edit are local and
untracked by default. To record origin and accepted changes in Astrid, add
`--project <existing-project>` to the standalone `import` and `edit` commands.
For edits, put common options after the bundle and before the verb, for example
`vibecomfy edit workflows/my_workflow --project demo set sampler.steps 30`.
If you are already using Astrid, use its native `media import` followed by a
`vibecomfy.import` task; Astrid supplies the project/task context, so the
executor does not take VibeComfy's `--project` option. The
[workflow onboarding guide](../../../guides/workflow-onboarding.md) gives the
Astrid-native task command and history path.

Loading a canonical bundle executes its `workflow.py` to build the graph, so
inspection, typed editing, capture, and validation use VibeComfy's existing
Python-consent gate. In a terminal, let the prompt ask before proceeding. For
an unattended command, use the explicit `vibecomfy --yes ...` opt-in only when
the user has authorized this source; `--non-interactive` otherwise refuses.
An Astrid-native canonical-bundle task must include the explicit
`python_execution_consent: "confirmed"` input. Do not infer that consent from
task admission or from an `authority_context` value. Importing raw workflow
JSON and inspecting a UI JSON graph do not execute workflow Python.

The `edit` command supports `set`, `add`, `remove`, `connect`, `disconnect`,
`mode`, and `batch`. A batch file or standard input lets an agent submit a
single ordered group of typed changes; later operations can refer to a node
added earlier in that batch. A failed batch does not save partial changes.
Use `--dry-run` to preview and `--out <directory>` to write a separate bundle.
For simple direct changes, you can instead edit existing node arguments in
`workflow.py`. If you use a recipe that loads the imported folder as a
`VibeWorkflow`, common supported controls are `set_prompt`, `set_seed`,
`set_steps`, and `set_input`; first check available fields with
`vibecomfy inspect <folder> --field <field>`. For unfamiliar node parameters,
use `vibecomfy node <ClassType> --inputs` and visible graph evidence. Validate and
diagnose the artifact you edited: the imported folder for direct edits, or
the separate recipe `.py` if you created a variation. Validating the source
folder does not check a recipe that loads it.

After a direct Python edit, run `vibecomfy edit <bundle> capture` to publish
the Python/companion pair and record the aggregate change. Add `--project` to
track that capture in Astrid. Capture does not invent individual edit
operations. A browser candidate and ComfyUI canvas Apply are not tracked
automatically; use explicit project-bound capture to add an applied canvas to
the Astrid history. Import, accepted edit, capture, validation, and execution
are separate actions: validation checks the exact edited bundle but does not
run generation.

Typed edits and UI capture regenerate Python from the canonical graph. If a
captured Python file contains extra executable code that the graph cannot
represent, VibeComfy refuses the rewrite and leaves all three bundle files
unchanged. Continue editing Python and capture it, or restore canonical
generated source before switching back to typed edits.

Use `vibecomfy validate` and `vibecomfy doctor` for preflight. Use
`vibecomfy templates create` when intentionally promoting an imported,
reviewed bundle to a ready template; `import` remains the single onboarding
path.

If the target is a ready template and the edit is user-specific:

```bash
vibecomfy copy-to-recipe <ready_id> --out recipes/<name>.py
```

Then edit the Python recipe, scratchpad, or template.

## Edit Shape

### Custom Python node

For a readable executable function, declare it once and call it with the
workflow as the first argument:

```python
from vibecomfy import python_node

@python_node(inputs={"value": "INT"}, outputs={"value": "INT"})
def increment(value):
    return {"value": value + 1}

first = increment(wf, value=1)
second = increment(wf, value=first.value)
```

Each call is a distinct `vibecomfy.exec` node. The function body is inert
while building, `io` names the typed semantic ports, and the existing graph
edges carry physical `in_N` sockets. Use `python_node.from_source(...)` for
a full module/project and `python_node.from_installed(...)` for an
environment-bound package. Snapshot entrypoints are package-relative;
installed entrypoints are fully qualified. A shared source identity can be
updated for all calls, while an explicitly selected call can be copied on
edit. Preserve helper files by capturing the project root rather than
extracting one function from its module.

The CLI convenience form uses the same canonical session and atomic bundle
publisher:

```bash
vibecomfy edit BUNDLE exec add --source-body "return {'value': value + 1}" --ports ports.json
vibecomfy edit BUNDLE exec inspect TARGET --json
vibecomfy edit BUNDLE exec export TARGET --destination exported_source
```

Validate source syntax, IO names, bindings, revision identity, and the exact
Python/companion pair. A successful edit is not runtime evidence; queue it
through `run-comfy-workflow` for that.

Use the lightest public API that fits:

```python
from vibecomfy.cli_loader import load_bundle

def build():
    wf = load_bundle("image/z_image").workflow
    wf.set_prompt("a glass teapot on basalt")
    wf.set_seed(42)
    wf.set_steps(20)
    return wf.finalize_metadata()
```

Reach for patches when decorating an existing graph. Reach for blocks or direct `VibeWorkflow` methods only when the edit changes handles, splices nodes, or rewires topology.

Never invent node fields, sockets, or class names. Use `vibecomfy node <ClassType> --inputs`, visible graph data, local precedents, or `search-comfy-workflows`.

## Validate

```bash
vibecomfy validate <edited.py>
vibecomfy doctor <edited.py> --json
```

For converted source workflows:

```bash
vibecomfy port doctor-all <source_or_edited_workflow> --json
```

If the edit adds custom nodes:

```bash
vibecomfy nodes install-plan <edited.py>
```

## Return Shape

For package-side edits, return the edited file path and validation evidence:

- recipe/scratchpad/template path
- changed intent in plain language
- `vibecomfy validate` / `vibecomfy doctor` status
- any node/model install plan

For Comfy app style edits, the returned object is a candidate envelope: `outcome.kind`, `candidate.graph`, `apply_eligibility`, graph hashes, change details, and artifact paths such as `candidate.ui.json` / `response.json`. The user still has to Apply or run it.

## Boundaries

- Do not run GPU work unless the user asked to execute or validation requires it.
- Do not promote a one-off composition to `ready_templates`; use `recipes/`.
- Keep upstream JSON close to upstream. Put local edits in Python.
- If the environment is missing, hand off to `vibecomfy-setup`; if execution fails, hand off to `debug-comfy-workflow`.
