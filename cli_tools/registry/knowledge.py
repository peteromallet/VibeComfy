#!/usr/bin/env python3
"""ComfyUI Knowledge - semantic access to nodes for agents."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "node_cache.json"


class ComfyKnowledge:
    # Task aliases map common use-cases to search terms
    TASK_ALIASES = {
        # Audio
        "beat detection": ["onset", "bpm", "beat", "drum detector", "audio"],
        "audio reactive": ["audio reactive", "amplitude", "rms", "sound reactive"],
        "fft": ["frequency", "spectral", "spectrum", "fft"],
        # Video generation models
        "ltx": ["ltx", "ltx2", "ltx-2", "lightricks", "ltxvideo", "ltxv", "stg", "gemma", "tiled sampler", "looping"],
        "wan": ["wan", "wan2", "wan2.1", "wan2.2", "wanvideo", "vace"],
        "i2v": ["i2v", "image2video", "image to video", "img2vid", "svd", "stable video"],
        "v2v": ["v2v", "video2video", "video to video", "vid2vid"],
        "t2v": ["t2v", "text2video", "text to video", "txt2vid"],
        "animatediff": ["animatediff", "animate", "motion", "lcm", "hotshotxl"],
        # Image generation
        "controlnet": ["controlnet", "canny", "depth", "pose", "lineart", "openpose"],
        "upscale": ["upscale", "esrgan", "realesrgan", "4x", "super resolution"],
        "interpolation": ["interpolation", "rife", "film", "frame", "tween"],
        "inpaint": ["inpaint", "outpaint", "mask", "fill"],
        "video": ["video", "animate", "animatediff", "frames", "sequence"],
        "lora": ["lora", "loha", "lycoris", "adapter"],
        "flux": ["flux", "bfl", "schnell", "dev", "guidance"],
        "sdxl": ["sdxl", "xl", "1024"],
        "sd15": ["sd15", "sd1.5", "1.5", "512"],
        # Processing
        "face": ["face", "insightface", "faceid", "portrait", "headshot", "reactor"],
        "segmentation": ["segment", "sam", "sam2", "clipseg", "mask", "cutout"],
        "style transfer": ["style", "ipadapter", "ip-adapter", "reference"],
        "text to image": ["txt2img", "text2img", "ksampler", "sampler"],
        "image to image": ["img2img", "image2image", "denoise"],
        "depth": ["depth", "midas", "zoe", "marigold", "depthanything"],
        "pose": ["pose", "openpose", "dwpose", "skeleton"],
        "workflow": ["workflow", "pattern", "pipeline", "recipe"],
        # Effects
        "glitch": ["glitch", "distort", "corrupt", "databend"],
        "dither": ["dither", "halftone", "retro", "pixel"],
        # Klein/Deforum
        "klein": ["klein", "deforum", "flux2", "temporal", "v2v"],
        "deforum": ["deforum", "klein", "motion", "temporal", "warp", "optical flow"],
    }

    def __init__(self, cache_path=None):
        self.cache_path = Path(cache_path) if cache_path else CACHE_FILE
        self.nodes = {}
        self._load_cache()

    def _load_cache(self):
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                self.nodes = json.load(f)

    def search_nodes(self, query, limit=10):
        """Search nodes with multi-word support, task aliases, and weighted scoring."""
        query_lower = query.lower()

        # Expand query with task aliases
        expanded_terms = set(query_lower.split())
        for task, aliases in self.TASK_ALIASES.items():
            if task in query_lower or any(a in query_lower for a in aliases):
                expanded_terms.update(aliases)

        words = list(expanded_terms)
        results = []

        for name, node in self.nodes.items():
            score = 0
            name_lower = name.lower()
            category = node.get("category", "").lower()
            description = node.get("description", "").lower()
            input_types = node.get("input_types", "").lower()
            output_types = node.get("output_types", node.get("return_types", "")).lower()
            author = node.get("author", "").lower()
            pack = node.get("pack", "").lower()

            # Exact phrase match bonus
            if query_lower in name_lower:
                score += 15
            if query_lower in description:
                score += 5

            # Multi-word matching
            for word in words:
                if word in name_lower:
                    score += 10
                if word in category:
                    score += 5
                if word in description:
                    score += 3
                if word in input_types:
                    score += 2
                if word in output_types:
                    score += 2
                if word in author:
                    score += 4
                if word in pack:
                    score += 3

            if score > 0:
                results.append({
                    "name": name,
                    "score": score,
                    "category": node.get("category", ""),
                    "description": node.get("description", "")[:150],
                    "pack": node.get("pack", ""),
                    "author": node.get("author", ""),
                })

        return sorted(results, key=lambda x: -x["score"])[:limit]

    def get_node_spec(self, name):
        if name in self.nodes:
            return self.nodes[name]
        name_lower = name.lower()
        for node_name, node in self.nodes.items():
            if node_name.lower() == name_lower:
                return node
        return None

    def get_nodes_by_pack(self, pack_id):
        return [n for n in self.nodes.values() if n.get("pack_id") == pack_id]

    def get_nodes_by_category(self, category):
        cat_lower = category.lower()
        return [n for n in self.nodes.values() if cat_lower in n.get("category", "").lower()]

    def explain_workflow(self, workflow):
        """Basic workflow stats - use simplify_workflow for full explanation."""
        nodes = workflow.get("nodes", [])
        types = {}
        for n in nodes:
            t = n.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        lines = [f"Nodes: {len(nodes)}", f"Types: {len(types)} unique", "", "Breakdown:"]
        for t, count in sorted(types.items(), key=lambda x: -x[1]):
            lines.append(f"  {t}: {count}")
        return "\n".join(lines)

    def simplify_workflow(self, workflow):
        """Convert workflow JSON to readable format with pattern detection."""
        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])

        if not nodes:
            return "Empty workflow"

        # Build node lookup
        node_map = {n.get("id"): n for n in nodes}
        types = [n.get("type", "unknown") for n in nodes]

        # Detect pattern
        pattern = self._detect_pattern(types)

        # Extract key parameters
        params = self._extract_params(nodes)

        # Build connection graph
        graph = self._build_graph(nodes, links)

        # Find flow paths
        flow = self._trace_flow(graph, node_map)

        # Format output
        lines = []
        lines.append(f"## Pattern: {pattern}")
        lines.append("")

        if params:
            lines.append("## Key Parameters")
            for k, v in params.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

        lines.append("## Flow")
        for path in flow:
            lines.append(f"  {path}")
        lines.append("")

        lines.append(f"## Stats: {len(nodes)} nodes, {len(links)} connections")

        return "\n".join(lines)

    def _detect_pattern(self, types):
        """Identify workflow pattern from node types."""
        types_lower = [t.lower() for t in types]
        types_str = " ".join(types_lower)

        # Pattern detection rules
        patterns = []

        # Model type
        if any("flux" in t for t in types_lower):
            patterns.append("Flux")
        elif any("wan" in t for t in types_lower):
            patterns.append("WAN")
        elif any("ltx" in t for t in types_lower):
            patterns.append("LTX")
        elif any("animatediff" in t for t in types_lower):
            patterns.append("AnimateDiff")
        elif any("sdxl" in t or "xl" in t for t in types_lower):
            patterns.append("SDXL")
        elif any("sd15" in t or "sd1.5" in t for t in types_lower):
            patterns.append("SD1.5")

        # Generation type
        if any("loadvideo" in t or "vhs_load" in t for t in types_lower):
            if any("ksampler" in t or "sampler" in t for t in types_lower):
                patterns.append("v2v")
            else:
                patterns.append("video-processing")
        elif any("loadimage" in t for t in types_lower):
            if any("vaeencode" in t for t in types_lower):
                patterns.append("img2img")
            elif any("ipadapter" in t for t in types_lower):
                patterns.append("style-transfer")
            else:
                patterns.append("i2v")
        elif any("emptylatent" in t for t in types_lower):
            patterns.append("txt2img")

        # Modifiers
        if any("controlnet" in t for t in types_lower):
            patterns.append("+ControlNet")
        if any("lora" in t for t in types_lower):
            patterns.append("+LoRA")
        if any("ipadapter" in t for t in types_lower):
            patterns.append("+IPAdapter")
        if any("upscale" in t for t in types_lower):
            patterns.append("+Upscale")
        if any("inpaint" in t for t in types_lower):
            patterns.append("+Inpaint")
        if any("face" in t or "reactor" in t for t in types_lower):
            patterns.append("+Face")

        return " ".join(patterns) if patterns else "Custom"

    def _extract_params(self, nodes):
        """Extract key generation parameters from nodes."""
        params = {}

        # Known parameter mappings: node_type -> (widget_index, param_name)
        param_map = {
            "KSampler": [(0, "seed"), (2, "steps"), (3, "cfg"), (4, "sampler"), (5, "scheduler")],
            "KSamplerAdvanced": [(2, "steps"), (3, "cfg"), (4, "sampler"), (5, "scheduler")],
            "CheckpointLoaderSimple": [(0, "model")],
            "LoraLoader": [(0, "lora"), (1, "strength")],
            "EmptyLatentImage": [(0, "width"), (1, "height"), (2, "batch")],
            "CLIPTextEncode": [(0, "prompt")],
        }

        for node in nodes:
            node_type = node.get("type", "")
            widgets = node.get("widgets_values", [])

            if node_type in param_map and widgets:
                for idx, name in param_map[node_type]:
                    if idx < len(widgets):
                        val = widgets[idx]
                        # Truncate long strings
                        if isinstance(val, str) and len(val) > 50:
                            val = val[:47] + "..."
                        # Skip None/empty
                        if val is not None and val != "":
                            params[name] = val

        return params

    def _build_graph(self, nodes, links):
        """Build adjacency graph from links."""
        # links format: [link_id, from_node, from_slot, to_node, to_slot, type]
        graph = {"out": {}, "in": {}}  # out[node_id] = [(target, type)], in[node_id] = [(source, type)]

        for link in links:
            if len(link) >= 6:
                _, from_node, _, to_node, _, link_type = link[:6]
                if from_node not in graph["out"]:
                    graph["out"][from_node] = []
                if to_node not in graph["in"]:
                    graph["in"][to_node] = []
                graph["out"][from_node].append((to_node, link_type))
                graph["in"][to_node].append((from_node, link_type))

        return graph

    def _trace_flow(self, graph, node_map):
        """Trace main flow paths through the graph."""
        # Find entry points (nodes with no inputs)
        all_nodes = set(node_map.keys())
        nodes_with_inputs = set(graph["in"].keys())
        entry_points = all_nodes - nodes_with_inputs

        # Find exit points (nodes with no outputs or are output types)
        nodes_with_outputs = set(graph["out"].keys())
        output_types = {"SaveImage", "PreviewImage", "VHS_VideoCombine", "SaveVideo"}
        exit_points = set()
        for nid, node in node_map.items():
            if node.get("type") in output_types:
                exit_points.add(nid)
        if not exit_points:
            exit_points = all_nodes - nodes_with_outputs

        # Trace paths from entries to exits
        paths = []
        visited_global = set()

        for entry in sorted(entry_points):
            if entry in visited_global:
                continue
            path = self._trace_single_path(entry, graph, node_map, exit_points, visited_global)
            if path:
                paths.append(path)

        # Format paths
        formatted = []
        for path in paths[:5]:  # Limit to 5 main paths
            node_names = []
            for nid in path:
                node = node_map.get(nid, {})
                ntype = node.get("type", "?")
                # Shorten common prefixes
                ntype = ntype.replace("CheckpointLoaderSimple", "Checkpoint")
                ntype = ntype.replace("CLIPTextEncode", "CLIP")
                ntype = ntype.replace("EmptyLatentImage", "EmptyLatent")
                node_names.append(ntype)
            formatted.append(" -> ".join(node_names))

        return formatted if formatted else ["No clear flow detected"]

    def _trace_single_path(self, start, graph, node_map, exits, visited):
        """Trace a single path through the graph using DFS."""
        path = [start]
        visited.add(start)
        current = start

        while current not in exits:
            outputs = graph["out"].get(current, [])
            if not outputs:
                break

            # Prefer MODEL/LATENT/IMAGE connections
            next_node = None
            priority_types = ["MODEL", "LATENT", "IMAGE", "CONDITIONING"]

            for ptype in priority_types:
                for target, ltype in outputs:
                    if ltype == ptype and target not in visited:
                        next_node = target
                        break
                if next_node:
                    break

            # Fallback to any unvisited
            if not next_node:
                for target, _ in outputs:
                    if target not in visited:
                        next_node = target
                        break

            if not next_node:
                break

            path.append(next_node)
            visited.add(next_node)
            current = next_node

        return path if len(path) > 1 else None

    def list_categories(self):
        """List all unique categories with counts."""
        from collections import defaultdict
        cats = defaultdict(int)
        for node in self.nodes.values():
            cat = node.get("category", "uncategorized")
            cats[cat] += 1
        return sorted(cats.items(), key=lambda x: -x[1])

    def list_packs(self):
        """List all unique packs with counts."""
        from collections import defaultdict
        packs = defaultdict(int)
        for node in self.nodes.values():
            pack = node.get("pack", "unknown")
            packs[pack] += 1
        return sorted(packs.items(), key=lambda x: -x[1])

    def search_by_author(self, author, limit=20):
        """Find all nodes by a specific author."""
        author_lower = author.lower()
        results = []
        for name, node in self.nodes.items():
            if author_lower in node.get("author", "").lower():
                results.append({
                    "name": name,
                    "category": node.get("category", ""),
                    "description": node.get("description", "")[:100],
                })
        return results[:limit]

    def stats(self):
        packs = set(n.get("pack", n.get("pack_id")) for n in self.nodes.values())
        with_desc = sum(1 for n in self.nodes.values() if n.get("description"))
        authors = set(n.get("author") for n in self.nodes.values() if n.get("author"))
        return {
            "total_nodes": len(self.nodes),
            "total_packs": len(packs),
            "with_descriptions": with_desc,
            "unique_authors": len(authors),
        }
