"""Experiment: multipass workflow with NATURAL section kinds to see how the
kind-wall (_SECTION_MIN_RANKS) merges repeated stages into one global wall.
"""
import sys
sys.path.insert(0, "tests")
from test_reorganise_compile import _node, _with_io, _layouts_by_uid
from vibecomfy.porting.reorganise.compile import compile_layout_plan, _effective_section_ranks
from vibecomfy.porting.reorganise.parse import parse_layout_plan
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts


def run(plan_sections, ui, label):
    plan = parse_layout_plan({"version": 1, "sections": plan_sections, "unassigned_policy": "reject"})
    facts = extract_graph_facts(ui)
    result = compile_layout_plan(plan, facts)
    print(f"\n=== {label} ===")
    print("ok:", result.ok)
    if not result.ok:
        for d in result.diagnostics:
            print("  diag:", d.code, d.message)
        return
    topo = {t.section_id: t for t in result.section_topologies}
    # effective ranks (what drives x placement)
    from vibecomfy.porting.reorganise.compile import _compile_section_topologies, _compile_sections
    # just print topology ranks
    for sid, t in sorted(topo.items(), key=lambda kv: kv[1].rank):
        print(f"  topo {sid}: rank={t.rank} island={t.island_index} scc={t.scc_id} preds={t.predecessor_ids} succs={t.successor_ids}")
    layouts = _layouts_by_uid(result)
    for uid in sorted(layouts, key=lambda u: (layouts[u].x, layouts[u].y)):
        print(f"  layout {uid}: x={layouts[uid].x} y={layouts[uid].y} section={layouts[uid].section_id}")


# Multipass with NATURAL kinds: loaders/sampling/decode/output
ui = {
    "nodes": [
        _with_io(_node(1, "LoadImage", "load"), outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [10]}]),
        _with_io(_node(2, "KSampler", "sample-1"), inputs=[{"name": "latent_image", "type": "IMAGE", "link": 10}], outputs=[{"name": "LATENT", "type": "LATENT", "links": [11]}]),
        _with_io(_node(3, "VAEDecode", "decode-1"), inputs=[{"name": "samples", "type": "LATENT", "link": 11}], outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [12]}]),
        _with_io(_node(4, "ImageResize", "resize"), inputs=[{"name": "image", "type": "IMAGE", "link": 12}], outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [13]}]),
        _with_io(_node(5, "KSampler", "sample-2"), inputs=[{"name": "latent_image", "type": "IMAGE", "link": 13}], outputs=[{"name": "LATENT", "type": "LATENT", "links": [14]}]),
        _with_io(_node(6, "VAEDecode", "decode-2"), inputs=[{"name": "samples", "type": "LATENT", "link": 14}], outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [15]}]),
        _with_io(_node(7, "SaveImage", "save"), inputs=[{"name": "images", "type": "IMAGE", "link": 15}]),
    ],
    "links": [
        [10, 1, 0, 2, 0, "IMAGE"],
        [11, 2, 0, 3, 0, "LATENT"],
        [12, 3, 0, 4, 0, "IMAGE"],
        [13, 4, 0, 5, 0, "IMAGE"],
        [14, 5, 0, 6, 0, "LATENT"],
        [15, 6, 0, 7, 0, "IMAGE"],
    ],
}

# NATURAL kinds
natural = [
    {"id": "load_stage", "kind": "loaders", "nodes": [["", "load"]]},
    {"id": "sample_1", "kind": "sampling", "nodes": [["", "sample-1"]]},
    {"id": "decode_1", "kind": "decode", "nodes": [["", "decode-1"]]},
    {"id": "resize_stage", "kind": "postprocess", "nodes": [["", "resize"]]},
    {"id": "sample_2", "kind": "sampling", "nodes": [["", "sample-2"]]},
    {"id": "decode_2", "kind": "decode", "nodes": [["", "decode-2"]]},
    {"id": "output_stage", "kind": "output", "nodes": [["", "save"]]},
]
run(natural, ui, "NATURAL KINDS (loaders/sampling/decode/postprocess/output)")

# Now print the effective_ranks directly
plan = parse_layout_plan({"version": 1, "sections": natural, "unassigned_policy": "reject"})
facts = extract_graph_facts(ui)
# Need _CompileSection objects; emulate via compile result
result = compile_layout_plan(plan, facts)
print("\n--- effective_ranks via compile internals ---")
# Recompute: build sections the same way compile does
