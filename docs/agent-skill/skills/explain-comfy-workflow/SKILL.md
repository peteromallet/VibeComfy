---
name: explain-comfy-workflow
description: Explain an existing VibeComfy or ComfyUI workflow, ready template, recipe, scratchpad, target graph, node chain, model path, prompt path, or runtime result. Use when the user asks what a workflow does, how it works, what a node or setting means, why a graph is wired a certain way, what will happen if it runs, or wants answers about a workflow without necessarily editing or executing it.
---

# Explain Comfy Workflow

Use this for understanding, not mutation. Push toward the same VibeComfy evidence path as edit/run/debug, but stop at a clear answer unless the user asks to change or execute the graph.

## Fast Path

```bash
vibecomfy inspect <workflow>
vibecomfy analyze info <workflow>
```

If the target is raw JSON, inspect it as import evidence and use the positional-source conversion path when a Python explanation is needed:

```bash
vibecomfy port check <workflow.json> --json
```

If the question depends on class behavior, sockets, or widgets:

```bash
vibecomfy nodes spec <ClassType>
```

Use `search-comfy-workflows` only when local evidence is not enough to explain a custom node, model family, or community workflow pattern.

## What To Answer

Shape the explanation around the user's question:

- what the workflow makes
- the main data path: loaders -> conditioning -> sampler/generator -> decode/output
- important public inputs, prompts, seeds, steps, dimensions, frame/audio controls, or model choices
- custom nodes, models, and missing dependencies
- likely runtime constraints or reasons it may not run
- where the answer came from: command output, node ids, file path, metadata, or run artifact

Keep it concrete. Name exact node classes and ids when they matter. Do not invent field meanings; inspect the graph or node spec.

## Boundaries

- Do not edit the workflow; hand off to `edit-comfy-workflow`.
- Do not run GPU work just to explain a static graph; hand off to `run-comfy-workflow` only when the user asks for execution or output proof.
- Do not diagnose a failure beyond the available evidence; hand off to `debug-comfy-workflow` when logs, validation errors, or missing assets are central.
- Do not search Hivemind for every question. Start with the local graph and escalate only when semantics or precedent are missing.

## Return Shape

Answer in plain language with a compact evidence trail:

- target workflow or file
- short purpose summary
- main node/data path
- relevant knobs or dependencies
- uncertainties or next proof step, if any

If the answer is based on a run, cite the `RunResult` fields or `out/runs/<run_id>/metadata.json`. If it is based on an edit candidate, say it is a candidate graph, not an executed result.
