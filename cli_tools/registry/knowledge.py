#!/usr/bin/env python3
"""ComfyUI Knowledge - semantic access to nodes for agents."""

import json
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "node_cache.json"


class ComfyKnowledge:
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
        from cli_tools.search import expand_query

        query_lower = query.lower()
        words = expand_query(query)
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
        """Convert workflow JSON to readable format with pattern detection.

        Combines agent-friendly pattern detection with existing analysis functions.
        """
        from cli_tools.analysis import analyze_workflow, get_workflow_info

        nodes = workflow.get("nodes", [])
        links = workflow.get("links", [])

        if not nodes:
            return "Empty workflow"

        # Get existing analysis
        info = get_workflow_info(workflow)
        analysis = analyze_workflow(workflow)

        # Get types for pattern detection
        types = [n.get("type", "unknown") for n in nodes]

        # Detect pattern (agent-friendly labels)
        pattern = self._detect_pattern(types)

        # Extract key parameters
        params = self._extract_params(nodes)

        # Format output
        lines = []
        lines.append(f"## Pattern: {pattern}")
        lines.append("")

        if params:
            lines.append("## Key Parameters")
            for k, v in params.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

        # Variables (SetNode/GetNode) from existing analysis
        if analysis.get('variables'):
            lines.append(f"## Variables ({len(analysis['variables'])})")
            for var in analysis['variables'][:5]:
                lines.append(f"  ${var['name']} <- Node {var['source_id']} ({var['source_type']})")
            lines.append("")

        # Loops from existing analysis
        if analysis.get('loops'):
            lines.append(f"## Loops ({len(analysis['loops'])})")
            for loop in analysis['loops']:
                iters = loop.get('iterations', '?')
                lines.append(f"  {loop['name']}: {iters} iterations")
            lines.append("")

        # Flow paths from existing analysis
        if analysis.get('pipelines'):
            lines.append("## Flow")
            for pipeline in analysis['pipelines'][:5]:
                path_nodes = [str(nid) for nid, _ in pipeline['path'][:8]]
                if len(pipeline['path']) > 8:
                    path_nodes.append('...')
                lines.append(f"  [{pipeline['category']}] {' -> '.join(path_nodes)}")
            lines.append("")

        lines.append(f"## Stats: {info['node_count']} nodes, {info['link_count']} connections, {len(info['type_counts'])} unique types")

        return "\n".join(lines)

    def _detect_pattern(self, types):
        """Identify workflow pattern from node types (agent-friendly labels)."""
        types_lower = [t.lower() for t in types]

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

        # Known parameter mappings: node_type -> [(widget_index, param_name), ...]
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
