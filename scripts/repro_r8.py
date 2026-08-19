import json
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/vc-twostep")

SCEN = Path("/private/tmp/vc-twostep/out/agentic/one-step-30-r8/attempts/3d-converts-image-to-3d-model/attempt_1/3d-converts-image-to-3d-model")

pre_ir = json.loads((SCEN / "original.ui.json").read_text())
post_ir = json.loads((SCEN / "final.ui.json").read_text())
response = json.loads((SCEN / "response.json").read_text())

print("=== pre_ir (original.ui.json) ===")
print(json.dumps(pre_ir, indent=2))
print("\n=== post_ir (final.ui.json) keys ===")
print(list(post_ir.keys()))

# extract accepted_batch
accepted_batch = response.get("accepted_batch") or []
print("\n=== accepted_batch ===")
print(json.dumps(accepted_batch, indent=2))

delta_ops = [item["op"] for item in accepted_batch if isinstance(item, dict) and "op" in item]
print("\n=== delta_ops ===")
print(json.dumps(delta_ops, indent=2))

from vibecomfy.schema import get_schema_provider
schema_provider = get_schema_provider("auto")

from vibecomfy.ingest.normalize import _assert_nonempty_ingest_preserved, _named_import

def lift(ir):
    raw = dict(ir)
    wf = _named_import(raw, schema_provider=schema_provider, use_comfy_converter=False)
    _assert_nonempty_ingest_preserved(raw, wf)
    return wf

pre_wf = lift(pre_ir)
post_wf = lift(post_ir)

print("\n=== pre_wf nodes ===")
for nid, node in pre_wf.nodes.items():
    print("id", nid, "uid", getattr(node, "uid", None), "class", getattr(node, "class_type", None))
    print("  widgets:", dict(getattr(node, "widgets", {}) or {}))
    print("  inputs:", dict(getattr(node, "inputs", {}) or {}))
    raw = getattr(node, "raw_widgets", None)
    if raw is not None:
        print("  raw_widgets.values:", getattr(raw, "values", None))

print("\n=== post_wf nodes ===")
for nid, node in post_wf.nodes.items():
    print("id", nid, "uid", getattr(node, "uid", None), "class", getattr(node, "class_type", None))
    print("  widgets:", dict(getattr(node, "widgets", {}) or {}))
    print("  inputs:", dict(getattr(node, "inputs", {}) or {}))
    raw = getattr(node, "raw_widgets", None)
    if raw is not None:
        print("  raw_widgets.values:", getattr(raw, "values", None))

from vibecomfy.porting.edit._diff import diff
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import parse_edit_delta, op_to_dict

ops = parse_edit_delta(list(delta_ops))
print("\n=== parsed ops ===")
for op in ops:
    print(repr(op))

result = interpret(pre_wf, ops, schema_provider=schema_provider)
print("\n=== interpret ok?", result.ok)
for d in result.diagnostics:
    print("  diag:", d.code, getattr(d, "message", ""))

leftover = diff(result.workflow, post_wf, schema_provider=schema_provider)
print("\n=== leftover diff(interpret(pre,Δ), post) count =", len(leftover))
for op in leftover:
    print("  ", op_to_dict(op))

expected = diff(pre_wf, post_wf, schema_provider=schema_provider)
print("\n=== expected diff(pre, post) count =", len(expected))
for op in expected:
    print("  ", op_to_dict(op))
