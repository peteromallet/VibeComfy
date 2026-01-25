#!/usr/bin/env python3
"""Scrape ComfyUI Registry API and build local node cache."""

import json
import time
import urllib.request
from pathlib import Path

API_BASE = "https://api.comfy.org"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "node_cache.json"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "VibeComfy/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def scrape_registry(limit_packs=None, verbose=True):
    DATA_DIR.mkdir(exist_ok=True)
    existing = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            existing = json.load(f)
        if verbose:
            print(f"Loaded {len(existing)} existing nodes")

    all_nodes = existing.copy()
    page = 1
    total_packs = 0
    new_nodes = 0
    total_pages = 999

    while page <= total_pages:
        url = f"{API_BASE}/nodes?page={page}&limit=50"
        data = fetch_json(url)
        total_pages = data.get("totalPages", 1)
        packs = data.get("nodes", [])
        if not packs:
            break

        for pack in packs:
            pack_id = pack.get("id")
            version = pack.get("latest_version", {}).get("version")
            if not pack_id or not version:
                continue
            try:
                nodes_url = f"{API_BASE}/nodes/{pack_id}/versions/{version}/comfy-nodes"
                nodes_data = fetch_json(nodes_url)
                for node in nodes_data.get("comfy_nodes", []):
                    node_name = node.get("comfy_node_name", "")
                    if node_name and node_name not in all_nodes:
                        all_nodes[node_name] = {
                            "name": node_name,
                            "pack_id": pack_id,
                            "category": node.get("category", ""),
                            "description": node.get("description", ""),
                            "input_types": node.get("input_types", ""),
                            "return_types": node.get("return_types", ""),
                        }
                        new_nodes += 1
                time.sleep(0.05)
            except Exception:
                pass
            total_packs += 1
            if limit_packs and total_packs >= limit_packs:
                break

        if limit_packs and total_packs >= limit_packs:
            break
        if verbose and page % 10 == 0:
            print(f"Page {page}/{total_pages} - {len(all_nodes)} nodes ({new_nodes} new)")
        page += 1

    with open(CACHE_FILE, "w") as f:
        json.dump(all_nodes, f, indent=2)
    if verbose:
        print(f"Done: {len(all_nodes)} total nodes ({new_nodes} new)")
    return len(all_nodes)


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scrape_registry(limit)
