"""Creative bug proposal engine for demo_factory.

An LLM proposes per-workflow, realistic, subtle, single-cause defects a
user/version-migration/editing-agent could introduce. Deterministic code
validates and applies proposals.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.porting.object_info import get_class

from vibecomfy.ingest.normalize import door_get_links, door_get_nodes, door_get_widgets_values, door_links, door_nodes
# The creative bar: seed the proposer with these examples of subtle bugs
_BUG_EXAMPLES = """
## Creative, realistic, single-cause defects (the bar we aim for):

1. **Second sampler reusing first pass's latent as noise** — In a two-pass img2img,
   the second sampler's `add_noise` input is wired to the first sampler's latent
   output instead of `EmptyLatentImage`. Both passes produce nearly identical
   images because the "random" noise is the same, but the wiring looks valid.

2. **Primitive silently overriding ControlNet strength to 0** — A PrimitiveNode
   (string or float) wired to ControlNet's `strength` input carries "0.0". The
   user edited the primitive's value but forgot that it overrides the ControlNet
   node's own widget. The workflow executes without error but produces no control
   effect.

3. **i2v first-frame taken from MASK instead of IMAGE** — An image-to-video node's
   `first_frame` input is wired to LoadImage's MASK output instead of IMAGE. The
   mask is typically black/white, so the video starts from a blank frame. The wiring
   is type-compatible (both are IMAGE), so it passes validation.

4. **LoRA distilled weights loaded in both branches** — A dual-branch workflow loads
   the same LoRA distilled weights in both the high-noise and low-noise branches. Due
   to a copy-paste error, the high-noise variant never activates its intended LoRA,
   but the workflow runs successfully.

5. **Audio sample-rate fed as video FPS** — An audio processing node receives a
   sample-rate value (e.g., 44100) where it expects frame rate (e.g., 24). The node
   clips or misinterprets the value, producing silent or garbled audio.

6. **Scheduler/sampler pair that disagrees** — A KSampler uses `dpmsolver++` but
   an upstream KSamplerAdvanced used `euler`. The denoise schedule expects
   continuity but gets a jump, producing visible artifacts.

7. **Hardcoded seed on a sampler the user thinks is randomized** — A sampler's
   `seed` widget is set to a fixed integer (not `-1`/`randomize`), so every run
   produces identical output. The user expected variation but gets determinism.

8. **VAE encode used instead of decode for preview** — A preview SaveImage node
   is wired to VAEEncode's output instead of VAEDecode's output. The preview shows
   latents (noise) instead of pixels, but the final export (wired correctly) is
   fine. This confuses the user into thinking the generation failed.

9. ** conditioning polarity flipped on a secondary sampler** — In a multi-sampler
   workflow, only the second sampler's positive/negative inputs are swapped. The
   first sampler works correctly, but the refinement pass inverts the style, producing
   inconsistent output.

10. **Frame count mismatch causing video duration desync** — A video combine node's
    `frame_count` widget is set to 120 but the upstream sampler only generated 60
    frames. The video pads or loops, creating timing issues.
"""


def _sanitize_graph_for_llm(graph: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized graph summary safe for LLM consumption.

    Removes large inline data (base64 images, audio blobs) and preserves only
    structural information: node IDs, types, widgets_values, inputs/outputs, and links.
    """
    nodes = []
    for node in door_get_nodes(graph, []):
        node_copy = {
            "id": node.get("id"),
            "type": node.get("type"),
            "pos": node.get("pos"),
            "inputs": node.get("inputs", []),
            "outputs": node.get("outputs", []),
        }
        # Include widgets_values but sanitize large values
        wv = door_get_widgets_values(node)
        if wv is not None:
            sanitized_wv = []
            for v in wv:
                if isinstance(v, str) and len(v) > 200:
                    sanitized_wv.append(f"<{len(v)} chars>")
                else:
                    sanitized_wv.append(v)
            node_copy["widgets_values"] = sanitized_wv
        nodes.append(node_copy)

    links = []
    for link in door_get_links(graph, []):
        if isinstance(link, list) and len(link) >= 6:
            # Sanitize large link IDs
            links.append([link[0], link[1], link[2], link[3], link[4], link[5]])

    return {
        "nodes": nodes,
        "links": links,
    }


def _build_proposer_prompt(graph: dict[str, Any], n: int = 10) -> str:
    """Build the prompt for the bug proposer LLM."""
    sanitized = _sanitize_graph_for_llm(graph)
    graph_summary = json.dumps(sanitized, indent=2)

    return f"""You are a devious, world-class ComfyUI QA engineer. Your job is to plant the most CREATIVE, UNEXPECTED, hard-to-spot single-cause defects in THIS workflow — the kind that stump a junior developer and read like a genuine support ticket. Prioritize surprising, workflow-specific bugs and avoid safe/generic ones.

## The workflow

```json
{graph_summary}
```

## The bar

{_BUG_EXAMPLES}

## Your task

First BRAINSTORM broadly (think laterally — wild, sneaky, surprising ideas that exploit THIS graph's real structure: multiple samplers, ControlNet, LoRA branches, two-stage passes, audio/video merges, reference inputs, VAE/model selection, etc.). Then return the {n} best — ones that are BOTH creative AND technically valid.

Each defect must be:
1. **Single-cause** — one node, one link, or one widget value is wrong.
2. **Surprising but plausible** — a clever mistake a human or editing agent could make; NOT obvious sabotage (deleting a node, CFG=100).
3. **Valid** — the broken workflow still passes schema validation and has a reachable output.
4. **Interesting** — the user-visible symptom is something a real user would notice and report.

AVOID these TIRED, overused families unless yours is genuinely novel: prompt/conditioning positive↔negative swaps, seed/noise "randomize→fixed" locks, trivial output-slot rewires/bypasses, blunt CFG/steps/denoise cranks, basic aspect-ratio typos.

## Output format

Return a JSON object with a `proposals` array. Each proposal must have:

```json
{{
  "proposals": [
    {{
      "edit_type": "set_widget" | "rewire_input" | "mute_node" | "remove_feature",
      "target_node_id": "<node ID (int or string)>",
      "widget_index": <int, for set_widget>,
      "new_value": <new widget value, for set_widget>,
      "input_name": "<input name on target node, for rewire_input>",
      "new_source_node_id": "<node ID to wire from, for rewire_input>",
      "new_source_output_slot": "<output slot index, for rewire_input>",
      "mode_value": <int, for mute_node (bypass=4, mute=5)>,
      "feature_type": <"upscale" | "refinement_pass" | "controlnet" | "audio_merge" | "face_detailer" | "lora_loader", for remove_feature>,
      "why_realistic": "<1-2 sentences explaining why this is plausible>",
      "user_symptom": "<what the user would actually observe, in their words>",
      "summary": "<short bug slug for campaign tracking, e.g. 'sampler-noise-reuse'>"
    }}
  ]
}}
```

## Edit types

- `set_widget`: Change a `widgets_values[index]` on a node.
- `rewire_input`: Move the link feeding `target.inputs[input_name]` to a different source.
- `mute_node`: Set `node["mode"]` to 4 (bypass) or 5 (mute).
- `remove_feature`: Remove a discrete functional subgraph (upscale node, refinement pass, ControlNet+preprocessor, audio merge, face-detailer, LoRA loader) and reroute downstream inputs to the feature's upstream source.

## Constraints

- Exploit the SPECIFIC structure of THIS workflow (two samplers → latent reuse; ControlNet → strength/preprocessor mismatch; LoRA branch → wrong-branch apply; two-stage → second pass reuses first; audio merge → wrong source; etc.).
- Do NOT propose generic bugs that would apply to any workflow.
- Each `user_symptom` must sound like a genuine support ticket, not a diagnostic.
- Be creative and VARIED — no two proposals should share a root-cause family.

Now propose {n} defects."""


@dataclass
class BugProposal:
    """A bug proposal from the creative engine."""
    edit_type: str  # "set_widget", "rewire_input", "mute_node", "remove_feature"
    target_node_id: str | int
    widget_index: int | None = None
    new_value: Any = None
    input_name: str | None = None
    new_source_node_id: str | int | None = None
    new_source_output_slot: int | None = None
    mode_value: int | None = None
    why_realistic: str = ""
    user_symptom: str = ""
    summary: str = ""
    # For remove_feature edit type
    feature_type: str | None = None  # "upscale", "refinement_pass", "controlnet", "audio_merge", "face_detailer", "lora_loader"
    # For swap_links edit type
    other_target_node_id: str | int | None = None
    other_input_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "edit_type": self.edit_type,
            "target_node_id": self.target_node_id,
            "widget_index": self.widget_index,
            "new_value": self.new_value,
            "input_name": self.input_name,
            "new_source_node_id": self.new_source_node_id,
            "new_source_output_slot": self.new_source_output_slot,
            "mode_value": self.mode_value,
            "why_realistic": self.why_realistic,
            "user_symptom": self.user_symptom,
            "summary": self.summary,
            "feature_type": self.feature_type,
            "other_target_node_id": self.other_target_node_id,
            "other_input_name": self.other_input_name,
        }


def _call_deepseek(prompt: str, *, temperature: float = 0.7) -> dict[str, Any]:
    """Call DeepSeek via the same path used by the live agentic harness.

    ``temperature`` defaults to 0.7 (balanced, used by the judge/filter). The
    creative proposer passes a higher value (~1.1) to encourage divergent,
    novel defect ideas instead of the same safe families.
    """
    import httpx

    # Load credentials from the canonical path
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        env_path = os.path.expanduser("~/Documents/banodoco-workspace/brain-of-bndc/.env")
        try:
            for line in open(env_path):
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not found in environment or canonical env file")

    # Use DeepSeek's API directly (matches adapter pattern).  Native
    # api.deepseek.com rejects OpenRouter-only dated aliases
    # (``deepseek-v4-flash-0731``); send the bare revision name it accepts
    # (``deepseek-v4-flash``).  VIBECOMFY_OPENROUTER_MODEL is still honored so
    # a caller pointed at an OpenRouter base URL can override the slug.
    base_url = os.environ.get("VIBECOMFY_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("VIBECOMFY_OPENROUTER_MODEL", "deepseek-v4-flash")
    if "api.deepseek.com" in base_url and "-" in model:
        family = "deepseek-v4-flash" if "flash" in model else "deepseek-v4-pro"
        model = family
    client = httpx.Client(timeout=120.0)

    try:
        response = client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 8000,
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Handle empty content
        if not content or not content.strip():
            raise ValueError("DeepSeek returned empty content")

        # Extract JSON from markdown code block if present
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0].strip()

        parsed = json.loads(content)
        return parsed
    finally:
        client.close()


def propose_bugs(golden: dict[str, Any], n: int = 10) -> list[BugProposal]:
    """Propose creative bugs for a workflow using DeepSeek.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.
    n:
        Number of proposals to request.

    Returns
    -------
    list[BugProposal]
        Structured bug proposals.
    """
    prompt = _build_proposer_prompt(golden, n=n)

    # Retry on transient errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = _call_deepseek(prompt, temperature=1.1)
            break
        except (ValueError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                print(f"DeepSeek call failed (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                import time
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            else:
                print(f"DeepSeek call failed after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            print(f"DeepSeek call failed with unexpected error: {e}")
            raise

    proposals = []
    for item in result.get("proposals", []):
        try:
            proposals.append(BugProposal(
                edit_type=item.get("edit_type", ""),
                target_node_id=item.get("target_node_id"),
                widget_index=item.get("widget_index"),
                new_value=item.get("new_value"),
                input_name=item.get("input_name"),
                new_source_node_id=item.get("new_source_node_id"),
                new_source_output_slot=item.get("new_source_output_slot"),
                mode_value=item.get("mode_value"),
                why_realistic=item.get("why_realistic", ""),
                user_symptom=item.get("user_symptom", ""),
                summary=item.get("summary", f"bug-{len(proposals)}"),
            ))
        except Exception as e:
            # Skip malformed proposals
            print(f"Skipping malformed proposal: {e}")
            continue

    return proposals


def _find_link_source(graph: dict[str, Any], to_node: Any, to_slot: Any) -> tuple[Any, Any]:
    """Return (from_node, from_slot) of the link feeding `to_node:to_slot`."""
    for link in door_get_links(graph, []):
        if not isinstance(link, list) or len(link) < 6:
            continue
        if str(link[3]) == str(to_node) and str(link[4]) == str(to_slot):
            return link[1], link[2]
    return None, None


def _find_node(graph: dict[str, Any], node_id: Any) -> dict[str, Any] | None:
    """Find a node by ID in the graph."""
    nid_str = str(node_id)
    for node in door_get_nodes(graph, []):
        if str(node.get("id")) == nid_str:
            return node
    return None


def _find_node_input(
    node: dict[str, Any],
    input_name: str,
) -> tuple[int, dict[str, Any]] | None:
    """Return an exact named input and its slot index."""
    for index, node_input in enumerate(node.get("inputs", []) or []):
        if str(node_input.get("name")) == str(input_name):
            return index, node_input
    return None


def _find_link_by_id(
    graph: dict[str, Any],
    link_id: Any,
) -> list[Any] | None:
    """Return one LiteGraph link row by id."""
    for link in door_get_links(graph, []) or []:
        if isinstance(link, list) and len(link) >= 6 and link[0] == link_id:
            return link
    return None


def _rebuild_output_link_references(graph: dict[str, Any]) -> None:
    """Make node output link-id lists agree with the graph's link rows."""
    by_source: dict[tuple[str, int], list[Any]] = {}
    for link in door_get_links(graph, []) or []:
        if not isinstance(link, list) or len(link) < 6:
            continue
        by_source.setdefault((str(link[1]), int(link[2])), []).append(link[0])

    for node in door_get_nodes(graph, []) or []:
        for fallback_slot, output in enumerate(node.get("outputs", []) or []):
            slot = output.get("slot_index")
            if not isinstance(slot, int):
                slot = fallback_slot
            if isinstance(door_get_links(output), list):
                output["links"] = list(
                    by_source.get((str(node.get("id")), slot), [])
                )


def apply_bug(golden: dict[str, Any], proposal: BugProposal) -> dict[str, Any] | None:
    """Deterministically apply a bug proposal to a deepcopy of golden.

    Returns the broken graph, or None if the proposal is inapplicable.
    """
    broken = copy.deepcopy(golden)

    # Find target node
    target = _find_node(broken, proposal.target_node_id)
    if target is None:
        return None

    if proposal.edit_type == "set_widget":
        # Apply widget value change
        widgets_values = door_get_widgets_values(target, [])
        if not isinstance(widgets_values, list):
            return None

        idx = proposal.widget_index
        if idx is None or idx < 0 or idx >= len(widgets_values):
            return None

        widgets_values[idx] = proposal.new_value
        target["widgets_values"] = widgets_values

    elif proposal.edit_type == "rewire_input":
        # Rewire input to new source
        input_name = proposal.input_name
        new_source_id = proposal.new_source_node_id
        new_source_slot = proposal.new_source_output_slot

        if input_name is None or new_source_id is None or new_source_slot is None:
            return None

        # Find the input on target
        target_input = None
        target_input_index = None
        for i, inp in enumerate(target.get("inputs", [])):
            if str(inp.get("name")) == str(input_name):
                target_input = inp
                target_input_index = i
                break

        if target_input is None:
            return None

        # Find new source node
        new_source = _find_node(broken, new_source_id)
        if new_source is None:
            return None

        # Get old link info
        old_link_id = target_input.get("link")
        old_from_node, old_from_slot = None, None
        old_to_slot = None
        old_link_type = None

        # Find the old link in links array
        old_link_entry = None
        for link in door_get_links(broken, []):
            if not isinstance(link, list) or len(link) < 6:
                continue
            if link[0] == old_link_id:
                old_link_entry = link
                old_from_node = link[1]
                old_from_slot = link[2]
                old_to_slot = link[4]
                old_link_type = link[5]
                break

        # Remove old link from array
        if old_link_entry is not None:
            broken["links"] = [l for l in door_links(broken) if l != old_link_entry]

        # Create new link
        new_id = max((l[0] for l in door_links(broken) if isinstance(l, list)), default=0) + 1
        door_links(broken).append([
            new_id,
            new_source_id,
            new_source_slot,
            proposal.target_node_id,
            old_to_slot if old_to_slot is not None else input_name,
            old_link_type if old_link_type is not None else "*",
        ])

        # Update target input
        target_input["link"] = new_id

        # Update source output links
        if old_link_entry is not None:
            old_source = _find_node(broken, old_from_node)
            if old_source is not None:
                for out in old_source.get("outputs", []):
                    if isinstance(door_get_links(out), list):
                        out["links"] = [x for x in door_links(out) if x != old_link_id]

        # Add new link to source output
        for out in new_source.get("outputs", []):
            if out.get("slot_index") == new_source_slot:
                if isinstance(door_get_links(out), list):
                    door_links(out).append(new_id)
                else:
                    out["links"] = [new_id]

    elif proposal.edit_type == "mute_node":
        # Set node mode to bypass/mute
        mode = proposal.mode_value or 4
        target["mode"] = mode

    elif proposal.edit_type == "disconnect_link":
        if proposal.input_name is None:
            return None
        target_input_match = _find_node_input(target, proposal.input_name)
        if target_input_match is None:
            return None
        _, target_input = target_input_match
        link_id = target_input.get("link")
        if link_id is None or _find_link_by_id(broken, link_id) is None:
            return None
        broken["links"] = [
            link for link in door_get_links(broken, [])
            if not (
                isinstance(link, list)
                and len(link) >= 6
                and link[0] == link_id
            )
        ]
        target_input["link"] = None
        _rebuild_output_link_references(broken)

    elif proposal.edit_type == "swap_links":
        if (
            proposal.input_name is None
            or proposal.other_target_node_id is None
            or proposal.other_input_name is None
        ):
            return None
        other_target = _find_node(broken, proposal.other_target_node_id)
        if other_target is None:
            return None
        first_match = _find_node_input(target, proposal.input_name)
        second_match = _find_node_input(other_target, proposal.other_input_name)
        if first_match is None or second_match is None:
            return None
        _, first_input = first_match
        _, second_input = second_match
        first_link = _find_link_by_id(broken, first_input.get("link"))
        second_link = _find_link_by_id(broken, second_input.get("link"))
        if first_link is None or second_link is None or first_link is second_link:
            return None
        first_source = (first_link[1], first_link[2])
        second_source = (second_link[1], second_link[2])
        first_link[1], first_link[2] = second_source
        second_link[1], second_link[2] = first_source
        _rebuild_output_link_references(broken)

    elif proposal.edit_type == "remove_feature":
        # Remove a discrete feature subgraph and reroute downstream inputs
        feature_type = proposal.feature_type
        if feature_type is None:
            feature_type = "generic"

        # Build node and link indexes
        nodes_index = {str(n.get("id")): n for n in door_get_nodes(broken, [])}
        target_id = str(proposal.target_node_id)

        # Find feature nodes based on type
        feature_nodes = _find_feature_nodes(broken, target_id, feature_type)

        if not feature_nodes:
            # If no feature nodes found, just remove the target node
            feature_nodes = [target_id]

        # Remove each feature node and reroute its downstream connections
        for node_id in feature_nodes:
            node_to_remove = nodes_index.get(node_id)
            if node_to_remove is None:
                continue

            # Find all incoming and outgoing links
            incoming_links = []
            outgoing_links = []

            for link in door_get_links(broken, []):
                if not isinstance(link, list) or len(link) < 6:
                    continue
                link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]

                if str(to_node) == node_id:
                    # Preserve original endpoint value types (ComfyUI LiteGraph
                    # uses int node ids in links); prior str() coercion created
                    # int/str mismatches that the apply validator misread as
                    # absent endpoints.
                    incoming_links.append((link_id, from_node, from_slot, to_slot, link_type))
                elif str(from_node) == node_id:
                    outgoing_links.append((link_id, from_slot, to_node, to_slot, link_type))

            # For each outgoing link, try to reroute to an incoming source
            for out_link_id, out_slot, to_n, to_s, l_type in outgoing_links:
                # Find the target node and input
                target_node = nodes_index.get(str(to_n))
                if target_node is None:
                    continue

                target_input = None
                target_input_index = None
                for i, inp in enumerate(target_node.get("inputs", [])):
                    if str(inp.get("link")) == str(out_link_id):
                        target_input = inp
                        target_input_index = i
                        break

                if target_input is None:
                    continue

                # Try to reroute to the first incoming link's source
                if incoming_links:
                    in_link_id, in_from_node, in_from_slot, in_to_slot, _ = incoming_links[0]

                    # Create new link
                    new_id = max((l[0] for l in door_links(broken) if isinstance(l, list)), default=0) + 1
                    door_links(broken).append([
                        new_id,
                        in_from_node,
                        in_from_slot,
                        to_n,
                        to_s,
                        l_type,
                    ])

                    # Update target input
                    target_input["link"] = new_id

                    # Update source output links
                    source_node = nodes_index.get(str(in_from_node))
                    if source_node is not None:
                        for out in source_node.get("outputs", []):
                            if isinstance(door_get_links(out), list):
                                door_links(out).append(new_id)

                # Remove old link from links array
                broken["links"] = [l for l in door_links(broken) if not (isinstance(l, list) and l and l[0] == out_link_id)]

            # Remove incoming links
            for in_link_id, _, _, _, _ in incoming_links:
                broken["links"] = [l for l in door_links(broken) if not (isinstance(l, list) and l and l[0] == in_link_id)]

            # Remove the node itself
            broken["nodes"] = [n for n in door_nodes(broken) if str(n.get("id")) != node_id]

        # Sweep orphaned references to removed nodes from surviving nodes.
        # The headless apply-validator rejects graphs that still reference a
        # removed node's instance id/uuid in widgets_values or properties
        # (it presents as "custom-node classes that could not be found"). Remove
        # any widget value or link that names a now-absent node id.
        removed_ids = {str(nid) for nid in feature_nodes}
        _strip_orphan_references(broken, removed_ids)

    else:
        return None

    return broken


def _strip_orphan_references(graph: dict[str, Any], removed_ids: set[str]) -> None:
    """Remove references to deleted node ids from surviving nodes and links.

    - drops any link whose endpoint touches a removed node;
    - rebuilds every surviving node's ``outputs[*].links`` so it only contains
      link ids still present in the links array (the reroute path appends the
      new link id but never prunes the stale one, which the apply validator
      reports as a dangling link);
    - clears widget values that are exactly a removed id (or a dict/string
      embedding one) so the apply validator does not see dangling instance refs.
    Mutates ``graph`` in place.
    """
    if not removed_ids:
        return

    def _refs_removed(value: Any) -> bool:
        if isinstance(value, str):
            return value in removed_ids
        if isinstance(value, dict):
            return any(
                isinstance(v, str) and v in removed_ids
                for v in value.values()
            )
        return False

    # Drop links touching removed nodes (defensive; rerouting should already
    # have handled the feature's own links, but cross-references can linger).
    graph["links"] = [
        l for l in door_get_links(graph, [])
        if not (
            isinstance(l, list) and len(l) >= 4
            and (str(l[1]) in removed_ids or str(l[3]) in removed_ids)
        )
    ]

    # Rebuild each node's output link-id lists from the surviving links array.
    live_link_ids = {
        l[0] for l in door_get_links(graph, []) if isinstance(l, list) and l
    }
    for node in door_get_nodes(graph, []):
        for out in node.get("outputs", []) or []:
            links = door_get_links(out)
            if isinstance(links, list):
                pruned = [lid for lid in links if lid in live_link_ids]
                out["links"] = pruned
        # Also clear stale input.link references.
        for inp in node.get("inputs", []) or []:
            lk = inp.get("link")
            if lk is not None and lk not in live_link_ids:
                inp["link"] = None

        wv = door_get_widgets_values(node)
        if isinstance(wv, list):
            node["widgets_values"] = [
                None if _refs_removed(v) else v for v in wv
            ]
        props = node.get("properties")
        if isinstance(props, dict):
            for key in list(props.keys()):
                if _refs_removed(props[key]):
                    props[key] = None


# Per-feature matching rules. ``categories`` matches object_info ``category``
# substrings (robust: covers comfy-core class families); ``keywords`` matches
# the node TYPE name substrings (covers custom-node classes absent from the
# cache, e.g. FaceDetailer).
_FEATURE_RULES: dict[str, dict[str, list[str]]] = {
    "upscale": {
        "categories": ["upscaling"],
        "keywords": [
            "upscale", "imagescale", "image_scale", "scaleby", "scaletototal",
            "scale_to_total", "imageupscale", "resize",
        ],
    },
    "refinement_pass": {
        "categories": ["sampling"],
        "keywords": ["ksampler", "sampler", "refine"],
    },
    "controlnet": {
        "categories": ["conditioning/controlnet", "controlnet"],
        "keywords": ["controlnet", "control", "applycontrolnet", "controlapply"],
    },
    "lora_loader": {
        "categories": [],  # model/loaders is too broad (CLIPLoader etc.)
        "keywords": ["lora"],
    },
    "audio_merge": {
        "categories": ["audio"],
        "keywords": ["audio", "merge", "concat", "mix"],
    },
    "face_detailer": {
        "categories": [],
        "keywords": ["face", "detailer"],
    },
}


def _node_matches_feature(node_type: str, feature_type: str) -> bool:
    """True when a node TYPE belongs to the given feature family.

    Uses object_info ``category`` first (robust across comfy-core class
    families), then falls back to TYPE-name keyword matching for custom-node
    classes absent from the cache.
    """
    rules = _FEATURE_RULES.get(feature_type)
    if not rules:
        return False
    ntype = (node_type or "").lower()
    if not ntype:
        return False
    for kw in rules["keywords"]:
        if kw in ntype:
            return True
    # Route the per-class category lookup through the shared object_info
    # chokepoint (``get_class`` reads the same per-pack cache the
    # ``AuthoringSchemaProvider`` index layer reads) rather than a duplicate
    # hardcoded monolithic JSON. Falls open to keyword matching above when the
    # class is absent (e.g. uninstalled custom nodes).
    info = get_class(node_type)
    if isinstance(info, dict):
        cat = (info.get("category") or "").lower()
        for sub in rules["categories"]:
            if sub in cat:
                return True
    return False


def find_feature_node_ids(graph: dict[str, Any], feature_type: str) -> list[str]:
    """Return ALL node ids in ``graph`` belonging to the feature family.

    Used by the campaign runner to pick the node to remove for an additive
    case. Never falls back to an unrelated node — returns ``[]`` when nothing
    matches so the caller can SKIP the case instead of removing the wrong node.
    """
    out = []
    for node in door_get_nodes(graph, []):
        if _node_matches_feature(node.get("type") or "", feature_type):
            out.append(str(node.get("id")))
    return out


def _find_feature_nodes(graph: dict[str, Any], target_id: str, feature_type: str) -> list[str]:
    """The single feature node to remove for an additive fault.

    Returns ``[target_id]`` (the node the campaign runner picked) — SURGICAL by
    design. The prior implementation expanded to EVERY node of the same family,
    which for ``refinement_pass`` (keywords ``ksampler/sampler`` + category
    ``sampling``) removed the *entire* sampling infrastructure (11+ nodes), and
    for ``audio_merge`` (keywords ``audio/merge/concat/mix``) removed every audio
    node. That left an unrecoverable graph the fixer could never re-add, so only
    the single-node ``ImageScaleBy`` upscale case ever passed.

    ``apply_bug`` reroutes the removed node's outgoing links to its upstream
    source and strips orphan references, so removing exactly one feature node
    yields a VALID broken graph (downstream stays connected) with one clear gap
    to re-add — the additive shape that reliably passes the oracle.
    """
    nodes_index = {str(n.get("id")): n for n in door_get_nodes(graph, [])}
    if target_id not in nodes_index:
        return []
    return [target_id]


def _output_reachable(graph: dict[str, Any]) -> bool:
    """Check if the graph has a reachable output (Save* node)."""
    for node in door_get_nodes(graph, []):
        node_type = (node.get("type") or "").lower()
        if "save" in node_type:
            # Check if it has any input linked
            for inp in node.get("inputs", []):
                if inp.get("link") is not None:
                    return True
    return False


def judge(proposals: list[BugProposal], golden: dict[str, Any]) -> list[BugProposal]:
    """Judge and filter proposals to the best 1-2.

    Criteria:
    - Applicable (apply_bug succeeds)
    - Single-cause (by construction from proposer)
    - Broken graph has reachable output
    - Reads realistic + interesting
    - Deprioritize trivial output-rewires
    """
    scored = []

    for prop in proposals:
        broken = apply_bug(golden, prop)
        if broken is None:
            continue

        if not _output_reachable(broken):
            continue

        # Score based on realism and non-triviality
        score = 0

        # Prefer non-rewire bugs (rewires are often too obvious)
        if prop.edit_type != "rewire_input":
            score += 2

        # Prefer bugs with specific, realistic explanations
        if len(prop.why_realistic) > 50 and "version" not in prop.why_realistic.lower():
            score += 1

        # Prefer bugs with specific user symptoms
        if len(prop.user_symptom) > 40 and "broken" not in prop.user_symptom.lower():
            score += 1

        # Penalize generic summaries
        if prop.summary.startswith("bug-"):
            score -= 1

        scored.append((score, prop))

    # Sort by score and return top 2
    scored.sort(key=lambda x: x[0], reverse=True)
    return [prop for _, prop in scored[:2]]
