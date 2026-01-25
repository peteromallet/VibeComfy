#!/usr/bin/env python3
"""Build embeddings for semantic search over ComfyUI nodes.

Uses sentence-transformers with numpy/pickle storage - simple and portable.
"""

import json
import pickle
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "node_cache.json"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.pkl"


def build_embeddings(model_name="all-MiniLM-L6-v2"):
    """Build embeddings from node cache using sentence-transformers."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("pip install sentence-transformers")
        return

    # Load nodes
    nodes = json.load(open(CACHE_FILE))
    print(f"Loaded {len(nodes)} nodes")

    # Build texts for embedding
    names = []
    texts = []
    for name, node in nodes.items():
        names.append(name)
        # Combine searchable fields
        text = f"{name} {node.get('category', '')} {node.get('description', '')} {node.get('input_types', '')[:300]}"
        texts.append(text)

    # Load model and encode
    print(f"Loading model {model_name}...")
    model = SentenceTransformer(model_name)
    
    print("Encoding embeddings (this takes ~2 min)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    # Save to pickle
    data = {
        "names": names,
        "embeddings": embeddings,
        "model": model_name,
    }
    with open(EMBEDDINGS_FILE, "wb") as f:
        pickle.dump(data, f)

    print(f"Saved {len(names)} embeddings to {EMBEDDINGS_FILE}")
    print(f"File size: {EMBEDDINGS_FILE.stat().st_size / 1024 / 1024:.1f} MB")


def search_semantic(query, limit=10):
    """Semantic search over nodes using cosine similarity."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("pip install sentence-transformers")
        return []

    if not EMBEDDINGS_FILE.exists():
        print("Run: python -m cli_tools.registry.embeddings")
        return []

    # Load embeddings
    with open(EMBEDDINGS_FILE, "rb") as f:
        data = pickle.load(f)

    names = data["names"]
    embeddings = data["embeddings"]
    model_name = data["model"]

    # Encode query
    model = SentenceTransformer(model_name)
    query_embedding = model.encode([query])[0]

    # Cosine similarity
    similarities = np.dot(embeddings, query_embedding) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
    )

    # Top results
    top_idx = np.argsort(similarities)[::-1][:limit]

    # Load node cache for metadata
    nodes = json.load(open(CACHE_FILE))

    results = []
    for idx in top_idx:
        name = names[idx]
        node = nodes.get(name, {})
        results.append({
            "name": name,
            "score": float(similarities[idx]),
            "category": node.get("category", ""),
            "description": node.get("description", "")[:100],
        })

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:])
        print(f"Searching: {query}\n")
        results = search_semantic(query)
        for r in results:
            print(f"  [{r['score']:.3f}] {r['name']} ({r['category']})")
            if r['description']:
                print(f"          {r['description']}")
    else:
        build_embeddings()
