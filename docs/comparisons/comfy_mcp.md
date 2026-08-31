# VibeComfy And Comfy MCP

[Comfy MCP](https://github.com/Comfy-Org/comfy-mcp) gives an agent a doorway
into ComfyUI. VibeComfy gives an agent a way to understand and safely change
the workflows it finds there.

Comfy MCP is an MCP server built on `comfy-cli`. It exposes ComfyUI operations
as tools an MCP-speaking client can call: inspect the live installation, search
nodes and models, fetch templates, change declared slots, validate workflows,
run jobs, monitor them, and collect outputs. That is valuable infrastructure.
It gives agents a standard control surface instead of making every client build
its own ComfyUI integration.

VibeComfy addresses a different problem. Its central question is not only:

> How can an agent call ComfyUI?

It is:

> How can an agent understand a real workflow, find proven patterns for
> achieving a result, make a complex grounded edit, verify it, and leave behind
> something another agent can understand later?

## The Difference

| Concern | Comfy MCP | VibeComfy |
|---|---|---|
| Primary role | Expose ComfyUI and `comfy-cli` capabilities through MCP tools. | Provide an agent-native workflow authoring, knowledge and reasoning layer. |
| Interface | Tool calls available to any MCP client. | Readable Python built around `VibeWorkflow`. |
| Workflow changes | Edit declared template slots and operate on workflow JSON. | Change values, wiring, nodes, blocks, subgraphs, and composed workflows using tools built for complex changes. |
| Understanding | Supply live node schemas, workflow notes, templates, and validation results. | Make graph intent inspectable through named calls, metadata, public inputs, provenance, and output contracts. |
| Best practices | Give the agent access to the available operations. | Guide the agent through curated templates, local precedents, community research, and workflow-specific skills. |
| Lifecycle | Launch, inspect, run, monitor, and manage ComfyUI. | Discover, translate, edit, compose, validate, compile, execute, and preserve the result. |

## Why Tool Access Is Not Enough

A tool can expose a node's schema or set a declared slot. It cannot, by itself,
decide which proven workflow pattern fits a particular result, which node
belongs in a particular model family, what part of a large graph expresses the
user's intent, or how to preserve subgraph boundaries and dependencies during
a structural edit.

Comfy MCP provides useful discovery and validation primitives; it should not be
described as merely a queue button. But the protocol layer deliberately leaves
workflow reasoning to the agent using it.

That reasoning layer is where VibeComfy concentrates. It searches curated
templates, local examples, and community knowledge for grounded precedents,
then turns workflow JSON into readable Python, applies the edit, validates both
graph structure and declared contracts, and compiles the result back into the
API JSON ComfyUI runs.

## The Design Choice

These projects are complementary, not competing implementations of the same
idea.

Comfy MCP standardizes how an agent reaches ComfyUI. VibeComfy focuses on what
the agent needs to know and preserve once it starts working on the graph.

For the representation at the center of that work, see
[What Is a VibeWorkflow?](what_is_a_vibeworkflow.md).
