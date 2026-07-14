"""Check effective_section_ranks vs topology rank for multipass natural kinds."""
import sys
sys.path.insert(0, "tests")
from test_reorganise_compile import _node, _with_io
from vibecomfy.porting.reorganise.compile import (
    compile_layout_plan,
    _effective_section_ranks,
    _compile_section_ownership_phase,
    _compile_section_topologies,
    _classify_layout_phase,
    _CompileTraceAccumulator,
    LayoutCompileOptions,
)
from vibecomfy.porting.reorganise.parse import parse_layout_plan
from vibecomfy.porting.reorganise.graph_facts import extract_graph_facts


def build(ui, sections):
    plan = parse_layout_plan({"version": 1, "sections": sections, "unassigned_policy": "reject"})
    facts = extract_graph_facts(ui)
    trace = _CompileTraceAccumulator(facts)
    classification = _classify_layout_phase(facts, trace=trace)
    compiled_sections = _compile_section_ownership_phase(plan, facts, classification, LayoutCompileOptions(), trace=trace)
    topos = _compile_section_topologies(compiled_sections, facts)
    eff = _effective_section_ranks(compiled_sections, topos)
    return compiled_sections, topos, eff


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
natural = [
    {"id": "load_stage", "kind": "loaders", "nodes": [["", "load"]]},
    {"id": "sample_1", "kind": "sampling", "nodes": [["", "sample-1"]]},
    {"id": "decode_1", "kind": "decode", "nodes": [["", "decode-1"]]},
    {"id": "resize_stage", "kind": "postprocess", "nodes": [["", "resize"]]},
    {"id": "sample_2", "kind": "sampling", "nodes": [["", "sample-2"]]},
    {"id": "decode_2", "kind": "decode", "nodes": [["", "decode-2"]]},
    {"id": "output_stage", "kind": "output", "nodes": [["", "save"]]},
]
secs, topos, eff = build(ui, natural)
topo_by_id = {t.section_id: t for t in topos}
print("section | kind | topo_rank | effective_rank")
for s in secs:
    print(f"  {s.id:14s} | {s.kind:12s} | topo={topo_by_id[s.id].rank} | eff={eff[s.id]}")
