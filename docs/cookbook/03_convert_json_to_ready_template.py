"""
03_convert_json_to_ready_template.py — Import ComfyUI JSON and create a ready template
================================================================================

Take a ComfyUI API-format JSON file and convert it into a Python ready template
using the canonical ``import`` / ``validate`` / ``doctor`` / ``templates create`` pipeline.

All work is build-only by default.  The actual conversion CLI commands are
shown in ``if __name__ == '__main__'``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# The conversion pipeline uses CLI commands.  This tutorial explains the
# concepts and demonstrates the programmatic API path.
# ---------------------------------------------------------------------------

# --- Concept: what the CLI does ---
#
#   1. vibecomfy import workflow.json
#      Creates the canonical editable workflow bundle and preserves source evidence.
#
#   2. vibecomfy validate workflows/workflow
#      Checks the authored Python graph and reports structural/schema issues.
#
#   3. vibecomfy templates create workflows/workflow --id image/my_template --out ready_templates/image/my_template.py
#      Produces a candidate from the edited bundle; it does not regenerate source.json.


def explain_pipeline() -> None:
    """Print the conversion pipeline steps (no filesystem or network access)."""
    steps = [
        ("1. Import", "vibecomfy import my_workflow.json"),
        ("2. Validate", "vibecomfy validate workflows/my_workflow --json"),
        ("3. Doctor", "vibecomfy doctor workflows/my_workflow --json"),
        ("4. Create candidate", "vibecomfy templates create workflows/my_workflow --id image/my_template --out ready_templates/image/my_template.py"),
        ("5. Copy for hand-editing", "python -m vibecomfy.cli copy-to-recipe image/my_template --out my_recipe.py --strip-markers"),
    ]
    print("Port conversion pipeline:")
    for label, cmd in steps:
        print(f"  {label:30s} {cmd}")


# ---------------------------------------------------------------------------
# Programmatic path (build-only, import-safe)
# ---------------------------------------------------------------------------

def load_and_inspect_json(path: str) -> dict:
    """Load a ComfyUI API JSON and return basic stats — no GPU, no network."""
    import json
    from pathlib import Path

    raw = json.loads(Path(path).read_text())
    nodes = {k: v for k, v in raw.items() if isinstance(v, dict) and "class_type" in v}
    class_types = sorted({v["class_type"] for v in nodes.values()})
    return {
        "path": path,
        "node_count": len(nodes),
        "class_types": class_types,
    }


if __name__ == "__main__":
    explain_pipeline()

    # Example: inspect the wan_i2v.json workflow corpus entry
    import json
    from pathlib import Path

    corpus_path = Path(__file__).resolve().parents[2] / "ready_templates/sources" / "official" / "video" / "wan_i2v.json"
    if corpus_path.exists():
        info = load_and_inspect_json(str(corpus_path))
        print(f"\nExample: {info['path']}")
        print(f"  Nodes: {info['node_count']}")
        print(f"  Class types: {', '.join(info['class_types'])}")
    else:
        print("\n(ready_templates/sources not found — clone the repo to see a real example)")
