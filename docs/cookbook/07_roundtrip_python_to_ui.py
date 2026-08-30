"""
07_roundtrip_python_to_ui.py — Roundtrip: Python workflow ↔ ComfyUI API JSON
==============================================================================

Demonstrate bidirectional conversion:
  - Python → API JSON (``wf.export_to_json()`` / ``wf.compile('api')``)
  - API JSON → Python (``port check`` / ``port convert``)

Also shows ``wf.lookup_id()`` for node introspection, ``wf.strict_types`` for
type-safe connections, and the inherent limitations of roundtripping.

Build-only by default — no GPU or network at module level.
"""

from __future__ import annotations

from vibecomfy.templates import ReadyMetadata, new_workflow, node
from vibecomfy.workflow import VibeWorkflow


# ---------------------------------------------------------------------------
# 1. Build a workflow and export to ComfyUI API JSON
# ---------------------------------------------------------------------------

METADATA = ReadyMetadata.build(
    capability="image",
    template_id="cookbook/roundtrip_demo",
    models={},
    output_prefix="image/RoundtripDemo",
)


def build_workflow() -> VibeWorkflow:
    """Build a simple workflow for roundtrip demonstration."""
    with new_workflow(METADATA, source_path=__file__) as wf:
        ckpt = node("CheckpointLoaderSimple", ckpt_name="v1-5-pruned-emaonly.safetensors")
        positive = node("CLIPTextEncode", text="a roundtrip test image", clip=ckpt.out(1))
        negative = node("CLIPTextEncode", text="blurry", clip=ckpt.out(1))
        latent = node("EmptyLatentImage", width=512, height=512, batch_size=1)
        sampled = node("KSampler",
            seed=99, steps=20, cfg=7.0,
            sampler_name="euler", scheduler="normal", denoise=1.0,
            model=ckpt.out(0), positive=positive.out(0),
            negative=negative.out(0), latent_image=latent.out(0),
        )
        decoded = node("VAEDecode", samples=sampled.out(0), vae=ckpt.out(2))
        save = node("SaveImage", filename_prefix="RoundtripDemo", images=decoded.out(0))
        return wf.finalize({}, output_type="SaveImage")


# ---------------------------------------------------------------------------
# 2. Export to API JSON (Python → UI)
# ---------------------------------------------------------------------------

def export_to_api_json(wf: VibeWorkflow) -> dict:
    """Convert a VibeWorkflow to ComfyUI API-format JSON.

    Two equivalent APIs:
      - wf.compile('api')   — lower-level, returns dict
      - wf.export_to_json() — v2.7 convenience wrapper
    """
    return wf.compile("api")


# ---------------------------------------------------------------------------
# 3. Inspect nodes with lookup_id()
# ---------------------------------------------------------------------------

def inspect_nodes(wf: VibeWorkflow) -> list[tuple[str, dict]]:
    """Use ``wf.lookup_id()`` to get rich info about each node."""
    results = []
    for node_id in list(wf.nodes.keys())[:3]:  # limit for readability
        try:
            info = wf.lookup_id(node_id)
            results.append((node_id, info))
        except KeyError:
            pass
    return results


# ---------------------------------------------------------------------------
# 4. Roundtrip limitations
# ---------------------------------------------------------------------------

ROUNDTRIP_LIMITATIONS = """
Roundtrip limitations (v2.7):
  - Python → API JSON is lossless for standard node calls.
  - API JSON → Python requires schema indexes (``vibecomfy sources sync``).
  - Widget aliases, custom node pack pins, and subgraph materialization
    are preserved on Python→API export but may shift during API→Python import
    if the source JSON uses legacy widget_N keys.
  - Use ``vibecomfy port doctor-all`` to audit roundtrip fidelity.
  - Hand-authored templates may not survive auto-conversion unchanged;
    use ``python -m vibecomfy.cli copy-to-recipe <id>`` for editable copies.
"""


# ---------------------------------------------------------------------------
# 5. Demonstrate (no GPU)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    wf = build_workflow()

    # Export to API JSON
    api = export_to_api_json(wf)
    print(f"API JSON: {len(api)} nodes")

    # Inspect nodes
    for node_id, info in inspect_nodes(wf):
        print(f"  Node {node_id}: class_type={info.get('class_type', '?')}")

    # Strict types demo
    print(f"\nwf.strict_types = {wf.strict_types}")
    print("  When True, wf.connect() warns about incompatible socket types.")

    # Id map
    id_map = wf.id_map()
    if id_map:
        print(f"id_map: {len(id_map)} entries")

    print(ROUNDTRIP_LIMITATIONS)
    print("✓ Roundtrip concepts demonstrated.")
