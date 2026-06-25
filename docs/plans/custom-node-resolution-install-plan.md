# Agentic Custom Node Resolution And Install Plan

## Problem

The agent-edit loop can now search local schemas, workflow/message precedent, and the web, but a missing custom node still becomes a practical dead end too early. In the Hotshot case, local `search(focus_types=["Hotshot"])` correctly reported that no installed node class was visible, but the workflow the user wanted was still plausible: the agent needed to discover the right custom node pack, inspect enough interface metadata to draft the graph, and return an installable proposal instead of treating "not installed" as final.

The root issue is that VibeComfy currently has two separate concepts:

- **Runnable graph authority:** the live ComfyUI `/object_info` schema. This is the only authority for a graph that can run now.
- **External package evidence:** Comfy Registry, ComfyUI-Manager, GitHub, examples, and prior workflows. These can tell us what to install and can sometimes provide provisional node schemas before install.

The tool needs an automatic bridge between those concepts. Missing local schema should trigger resolution and evidence gathering, not a hard stop.

## Current State

Useful pieces already exist:

- `search(focus_types=[...])` is a local schema lookup. It should stay that way and be explicit about its scope.
- `research("query", sources=[...])` lets the agent choose source tiers: workflows, messages, web.
- `vibecomfy.registry.pack_resolver` already talks to Comfy Registry for pack resolution.
- `vibecomfy.node_packs.install_pack()` already handles install side effects, install sentinels, lockfile updates, ComfyUI-Manager fallback, git clone fallback, and the capability confirmation gate.
- `vibecomfy/commands/nodes.py` already exposes `nodes lookup`, `nodes install-plan`, `nodes install`, and `nodes ensure`.
- The browser panel has agent routes in `vibecomfy/comfy_nodes/agent/routes.py`, but no route yet for custom-node resolution or install proposals.

Missing pieces:

- No resolver service that turns a missing class/query into ranked install candidates plus provisional schemas.
- No panel endpoint for a candidate install proposal.
- No panel endpoint/button that invokes the existing installer and then reloads/rebaselines Comfy.
- No automatic enrichment hook after a local schema miss.

## Target Flow

For a request like "Switch to generating 16 frames with Hotshot":

1. The agent tries `search(focus_types=["Hotshot"])`.
2. Local schema returns no installed Hotshot classes.
3. The edit engine automatically makes the miss available as a resolvable event, with guidance that this means "not installed locally", not "does not exist".
4. The agent can call `research("Hotshot ComfyUI video custom node", sources=["web", "messages", "workflows"])` or the engine can attach missing-node resolution evidence automatically.
5. The resolver searches Comfy Registry, ComfyUI-Manager DB, web/GitHub, examples, and prior workflows.
6. If it finds a candidate pack with registry `comfy-nodes` metadata, the agent gets provisional input/output signatures and provenance.
7. The agent drafts a graph using provisional schemas, marking missing packs as install requirements.
8. Apply does not pretend the graph is runnable. It returns an install proposal with package, repo, version, dependencies, provenance, and expected node classes.
9. The panel shows an install action. The user confirms.
10. Backend calls the existing `install_pack()` path.
11. Comfy is reloaded or restarted.
12. VibeComfy rebaselines `/object_info`, validates that expected classes now exist locally, and resumes the agent turn or asks the user to retry from the updated canvas.

This keeps the agent in charge of choosing searches and interpreting evidence, while the system supplies safe automatic plumbing at the point where "missing locally" used to become a blocker.

## Architecture

### 1. Resolution Service

Add a backend module, for example `vibecomfy/custom_nodes/resolution.py`, with one main entry point:

```python
resolve_missing_custom_node(
    query: str,
    *,
    missing_class: str | None = None,
    source_hints: Sequence[str] = ("registry", "manager", "web", "workflows", "messages"),
) -> MissingNodeResolution
```

The result should include:

- ranked package candidates
- candidate source: registry, manager, github, workflow, message, web
- package slug/name
- repository URL
- registry id when present
- version when known
- dependencies when known
- expected Comfy node class names
- provisional node schemas when known
- evidence URLs/snippets
- confidence and warnings

The resolver should not hide candidates through deterministic relevance filtering. It can bound result count, normalize obvious aliases, and tag provenance, but the model should see enough evidence to decide.

### 2. Registry Client

Extend `vibecomfy.registry.pack_resolver` or add a sibling client that supports:

- package search
- package detail
- version list/detail
- `comfy-nodes` schema fetch

Important behavior:

- Do not use `versions/latest/comfy-nodes`; it is not reliable.
- Fetch package detail first, then use `latest_version.version`.
- Treat registry schemas as provisional until the pack is installed and live `/object_info` confirms them.
- Preserve registry warnings when schemas are unavailable or null.

### 3. Provisional Schema Adapter

Convert registry `comfy_nodes` entries to VibeComfy authoring schemas:

- `comfy_node_name` -> class type
- `input_types` JSON string -> required/optional inputs and widget metadata
- `return_types` JSON string -> outputs
- `return_names` JSON string -> output names when present
- `output_is_list` -> output list metadata
- `category`, `description`, `deprecated`, `experimental` -> provenance metadata

These schemas should be usable for authoring and linting, but must carry `source="registry"` or equivalent so apply/runtime can require installed validation before claiming runnability.

### 4. Agent-Edit Hook

Insert the automatic hook after local schema lookup misses in the batch REPL resolver:

- If `search(focus_types=[...])` returns zero local schemas, attach a "missing local schema" diagnostic.
- Include a next-action hint that the agent may call `research(...)` or use `resolve_missing_custom_node(...)` if exposed as a query primitive.
- Optionally auto-run a bounded resolver call for the same terms and include its evidence in the next model report.

The key is that this should be automatic enough that the model does not need to remember a special recovery ritual, but still agentic enough that the model chooses follow-up searches and the final candidate.

### 5. Query Primitive

Add a first-class query primitive if automatic research evidence is not enough:

```python
resolve_custom_node("HotshotXL", sources=["registry", "manager", "web", "messages", "workflows"])
```

This should be read-only. It should never install anything. It returns candidates and provisional schemas.

### 6. Install Proposal Contract

When a candidate graph depends on missing packs, the agent-edit response should be able to return:

```json
{
  "status": "requires_custom_nodes",
  "install_proposals": [
    {
      "pack_name": "ComfyUI-VideoHelperSuite",
      "repo": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
      "registry_id": "comfyui-videohelpersuite",
      "version": "1.7.9",
      "dependencies": ["opencv-python", "imageio-ffmpeg"],
      "expected_classes": ["VHS_LoadVideoPath"],
      "evidence": [...]
    }
  ],
  "candidate_graph": {...}
}
```

The graph can be previewed, but Apply should not mark it runnable until the install/validation phase succeeds.

### 7. Panel Endpoints

Add routes alongside the existing agent routes:

- `POST /vibecomfy/custom-nodes/resolve`
- `POST /vibecomfy/custom-nodes/install`
- `GET /vibecomfy/custom-nodes/install-status`
- Optional: `POST /vibecomfy/custom-nodes/probe-schema`

`resolve` is read-only. `install` uses `vibecomfy.node_packs.install_pack()` and therefore inherits the existing capability gate, sentinel, lockfile, cm-cli, and git clone behavior.

### 8. Panel UX

When agent-edit returns `requires_custom_nodes`, the panel should show:

- pack name
- repo URL
- source: registry/manager/GitHub/workflow/message
- version/commit if known
- pip dependencies
- expected node classes
- warning that the install may require Comfy reload/restart
- "Install custom nodes" action

After install, the panel should run reload/rebaseline and then show whether expected classes appeared in local `/object_info`.

## Endpoint Tests

These endpoints were tested directly on 2026-06-24.

| Purpose | Endpoint | Result |
| --- | --- | --- |
| Registry package search | `https://api.comfy.org/nodes/search?search=HotshotXL&limit=5&page=1` | HTTP 200, `nodes: []`, `total: 0` |
| Registry package search | `https://api.comfy.org/nodes/search?search=hotshot&limit=5&page=1` | HTTP 200, `nodes: []`, `total: 0` |
| Registry package detail | `https://api.comfy.org/nodes/comfyui-videohelpersuite` | HTTP 200, latest version `1.7.9`, repo `https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite` |
| Registry version detail | `https://api.comfy.org/nodes/comfyui-videohelpersuite/versions/1.7.9` | HTTP 200, dependencies include `opencv-python`, `imageio-ffmpeg`, `downloadUrl` is present |
| Registry node schemas | `https://api.comfy.org/nodes/comfyui-videohelpersuite/versions/1.7.9/comfy-nodes` | HTTP 200, `comfy_nodes` count `10`, includes `input_types` and `return_types` JSON strings |
| Registry latest shortcut | `https://api.comfy.org/nodes/ComfyUI-VideoHelperSuite/versions/latest` | HTTP 404; do not use |
| Registry latest schemas shortcut | `https://api.comfy.org/nodes/ComfyUI-VideoHelperSuite/versions/latest/comfy-nodes` | HTTP 200 but `comfy_nodes: null`; do not use |
| Registry package detail | `https://api.comfy.org/nodes/comfyui-animatediff-evolved` | HTTP 200, latest version `1.5.7`, repo `https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved` |
| Registry latest node schemas | `https://api.comfy.org/nodes/comfyui-animatediff-evolved/versions/1.5.7/comfy-nodes` | HTTP 200 but `comfy_nodes: null`; fallback required |
| ComfyUI-Manager DB | `https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/node_db/new/custom-node-list.json` | HTTP 200, `custom_nodes` list with `title`, `reference`, `files`, `install_type`, `description` |
| ComfyUI-Manager node map | `https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/main/node_db/new/extension-node-map.json` | HTTP 200, maps repo URL to node class lists; contains `VHS_LoadVideoPath`, `VHS_VideoCombine`, and AnimateDiff class references; no Hotshot hit |
| Hivemind unified feed | `https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1/unified_feed?...` | HTTP 200 with publishable anon key; found HotshotXL, VideoHelperSuite, and AnimateDiff community messages |
| GitHub repository search | `https://api.github.com/search/repositories?q=HotshotXL%20ComfyUI` | HTTP 200 unauthenticated; found `KintCark/Hotshot-XL-Gradio-Cpu-Termux`, which appears not to be a Comfy custom-node repo |
| GitHub code search | `https://api.github.com/search/code?q=HotshotXLModelLoader` | HTTP 401 unauthenticated; use authenticated API, raw fetch, or temp clone fallback |
| GitHub repo contents | `https://api.github.com/repos/Kosinkadink/ComfyUI-VideoHelperSuite/contents` | HTTP 200 unauthenticated; enough to discover raw source files after a repo candidate is known |
| GitHub raw source | `https://raw.githubusercontent.com/Kosinkadink/ComfyUI-VideoHelperSuite/main/videohelpersuite/nodes.py` | HTTP 200; AST parse finds `NODE_CLASS_MAPPINGS` with 40 VHS classes |
| Live Comfy schema | `http://127.0.0.1:8190/object_info` | HTTP 200 locally; current instance returned 794 installed classes, with no Hotshot, VHS, or AnimateDiff classes installed |
| Registry class search | `https://api.comfy.org/nodes/search?comfy_node_search=ADE_AnimateDiffLoaderGen1` | HTTP 200, resolves `ComfyUI-AnimateDiff-Evolved` |
| Registry class search | `https://api.comfy.org/nodes/search?comfy_node_search=HotshotXL` | HTTP 200, zero results because Hotshot is not an AnimateDiff-Evolved node class name |
| AnimateDiff source probe | `https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved` | Source text mentions HotshotXL support, but `NODE_CLASS_MAPPINGS` contains ADE node names, not Hotshot node names |

The important endpoint for registry-backed provisional node signatures is:

```text
GET https://api.comfy.org/nodes/{registry_id}/versions/{version}/comfy-nodes
```

The implementation must first fetch:

```text
GET https://api.comfy.org/nodes/{registry_id}
```

Then read `latest_version.version` and request the concrete version schema endpoint.

For ComfyUI-Manager-backed class-to-repo discovery, the most useful endpoint is:

```text
GET https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/main/node_db/new/extension-node-map.json
```

`custom-node-list.json` is useful package metadata, but `extension-node-map.json`
is the better class lookup surface.

## HotshotXL Through AnimateDiff-Evolved

`ComfyUI-AnimateDiff-Evolved` does support HotshotXL, but not by exposing
`HotshotXL...` node classes. The package exposes AnimateDiff/ADE node classes
such as:

- `ADE_AnimateDiffLoaderGen1`
- `ADE_LoadAnimateDiffModel`
- `ADE_ApplyAnimateDiffModel`
- `ADE_StandardStaticContextOptions`

HotshotXL appears in package source and documentation as a supported SDXL motion
module format. The resolver therefore needs two different query modes:

- **class lookup:** exact or fuzzy lookup over node class names, using local
  `/object_info`, registry `comfy_node_search`, Manager `extension-node-map`,
  and static `NODE_CLASS_MAPPINGS`.
- **capability/source lookup:** text search over package README/docs/source,
  examples, workflows, Hivemind, and web results for concepts that are not node
  class names, such as `HotshotXL`.

For this case, searching by `HotshotXLModelLoader` or `HotshotXL` should not
only return "no node found". It should return evidence that `ComfyUI-AnimateDiff-
Evolved` is a likely package because its docs/source mention HotshotXL support,
while clearly noting that the installable node classes are ADE classes.

This is relevant only as **intent disambiguation**. It must not cause the agent
to invent or search for non-existent `HotshotXL...` node classes forever. If the
user intent is "use HotshotXL as the motion model", the resolver can offer
AnimateDiff-Evolved with ADE node classes and a HotshotXL model-file requirement.
If the user intent is literally "use a node class named Hotshot", the correct
result is "no such installed or registered node class found" plus candidate
packages that mention HotshotXL as a capability.

## Security Model

Resolution is read-only. It may fetch JSON, GitHub metadata, README text, examples, and static source files. It must not execute package code.

Install is side-effecting and must remain behind explicit user confirmation:

- network access
- filesystem writes
- package code download
- possible pip installs
- Comfy restart/reload impact

Use the existing `install_pack()` capability fence instead of adding a parallel install implementation.

Temporary clone/static scan fallback is allowed only for source inspection:

- clone into a temp/cache directory
- parse Python AST for `NODE_CLASS_MAPPINGS`, `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES`
- do not import the package
- do not run install scripts
- do not run embedded code or examples

## Implementation Phases

1. **Registry schema client**
   - Add typed client methods for detail, version detail, and `comfy-nodes`.
   - Add tests with mocked HTTP responses and one optional live smoke script.

2. **Provisional schema conversion**
   - Convert registry `comfy_nodes` to VibeComfy `NodeSchema`.
   - Add provenance/confidence fields or wrap schemas in a candidate object.

3. **Missing-node resolver**
   - Combine registry, ComfyUI-Manager DB, existing `research(...)` tiers, and GitHub/web evidence.
   - Preserve candidate evidence instead of filtering aggressively.

4. **Agent-edit integration**
   - Attach resolver evidence after local `search(...)` misses.
   - Add `resolve_custom_node(...)` query primitive if needed.
   - Teach the prompt that missing local schemas can become install proposals.

5. **Install proposal response**
   - Add `requires_custom_nodes` outcome or extend the existing response contract.
   - Include install proposals and candidate graph metadata.

6. **Panel install route and UI**
   - Add `POST /vibecomfy/custom-nodes/install`.
   - Wire it to `install_pack()`.
   - Show install proposal details and confirmation action.

7. **Reload and validation**
   - After install, trigger or instruct Comfy reload/restart.
   - Rebaseline local `/object_info`.
   - Verify expected classes exist before marking the graph runnable.

8. **End-to-end tests**
   - Unit-test registry parsing and schema conversion.
   - Unit-test missing-node miss -> resolution evidence.
   - Route-test resolve/install proposal envelopes.
   - Browser-test panel install proposal rendering.
   - Smoke-test a known registry pack such as `ComfyUI-VideoHelperSuite`.

## Open Risks

- Hotshot/HotshotXL did not appear in Comfy Registry search during testing. The resolver must fall back to Manager DB, GitHub search, web search, prior workflows, and static source scan.
- Not every registry package publishes `comfy-nodes` schemas. `ComfyUI-AnimateDiff-Evolved` latest version returned `comfy_nodes: null`.
- Registry schemas can be stale or incomplete. Live `/object_info` after install remains the final authority.
- Some installs require restart rather than hot reload. The panel must represent that clearly.
- Ambiguous package names should be surfaced as evidence for agent/user choice, not silently collapsed.

## Implemented Contract

Implemented on 2026-06-24 as a resolver-driven, evidence-first install flow.
The final browser-facing install endpoint is:

```text
POST /vibecomfy/node-packs/install
```

The route accepts the selected resolver candidate, `expected_classes`,
`validation_mode`, `stable_install_hash`, and an explicit confirmation flag. It
delegates installs only to `vibecomfy.node_packs.install_pack()` and does not add
a second installer path.

Resolver candidates now carry:

- `expected_classes`, deduplicated from Registry, Manager, GitHub/static source,
  or capability evidence.
- `validation_mode=class_validatable` when concrete expected classes are
  available.
- `validation_mode=evidence_only` when evidence identifies a package but no
  concrete class can be validated.
- `stable_install_hash`, computed from stable package identity,
  `expected_classes`, and `validation_mode`, excluding volatile evidence and
  warning fields.
- per-source evidence, endpoint labels, cache-hit metadata, and warnings.

Normal panel install actions reject `evidence_only` proposals and proposals with
empty `expected_classes`. Evidence-only candidates remain visible as resolver
evidence, but they cannot be installed through the normal CTA or reported as
validated.

## Implemented Evidence Tiers

The resolver combines read-only evidence from:

- Comfy Registry package search/detail/version/schema endpoints.
- ComfyUI-Manager custom node map and custom node list metadata.
- Optional GitHub code search when an authenticated client is available.
- Unauthenticated GitHub repository/raw-source fallback when code search is
  unavailable or rate-limited.

Registry schema fetches use concrete versions. The implementation first resolves
package detail/version data, then fetches:

```text
GET https://api.comfy.org/nodes/{registry_id}/versions/{version}/comfy-nodes
```

Tests assert that the resolver does not use `latest` schema shortcuts for the
covered paths. All external schema evidence remains provisional and non-runnable
until local `/object_info` confirms the classes after install.

## Implemented Agent And Panel Flow

`requires_custom_nodes` is now a public, non-applyable route/outcome. It is
registered in the agent and executor public route contracts, deliberately kept
out of turn grammar primitives, and stripped of applyable candidate/graph fields
before durable turn serialization.

Local `search(...)` misses and `research(...)` output can surface resolver
evidence, warnings, provenance, candidate package identity, expected classes, and
validation mode. The browser normalizes and stores this evidence as custom-node
resolution state.

The panel install flow posts to `/vibecomfy/node-packs/install`, tracks
installing/installed/failure states, and handles validation outcomes:

- `installed` with `validated=true`: clears provisional resolver evidence and
  prompts a fresh retry against local schemas.
- `restart_required`: keeps install evidence visible and reports missing
  expected classes.
- `validation_failed` or install failure: keeps evidence visible for user/agent
  recovery.
- `validation_skipped`: does not mark the candidate runnable.

## Implemented Validation

After a mocked successful install, the route refreshes local schema state and
checks `expected_classes` against `/object_info`. Local `/object_info` remains
the sole runnable schema authority.

Security and capability-gate behavior:

- Missing explicit confirmation rejects before `install_pack()`.
- Capability-gate failures reject before post-install validation.
- `evidence_only` and empty-class proposals reject before install.
- Hash mismatch is tolerated only when the stable package identity still
  matches; otherwise the route re-resolves and rejects divergent identity.
- Resolver code remains read-only: it does not import custom-node packages,
  execute third-party code, shell out to install, or mutate `custom_nodes`.

## Verification Commands

Final batch verification uses the targeted files/modules that cover the
implemented resolver, search/research integration, install route, and gate
contract:

```bash
pytest tests/test_pack_resolver.py -v
pytest tests/test_porting_edit_session_harness.py tests/test_executor_research.py -v
pytest tests/test_comfy_nodes_agent_backend_spine.py tests/security/test_install_pack_gate.py -v
```

The broader backend spine file still includes known unrelated prompt-size
baseline failures from prior context. Those are not part of the custom node
install flow and should not be fixed under this plan.
