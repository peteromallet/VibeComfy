import json
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/vc-twostep")

from vibecomfy.schema import get_schema_provider
from vibecomfy.ingest.normalize import _assert_nonempty_ingest_preserved, _named_import
from vibecomfy.porting.edit._diff import diff
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import parse_edit_delta, op_to_dict
from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field

ROOT = Path("/private/tmp/vc-twostep")
SCEN = ROOT / "out/agentic/one-step-30-r8/attempts/3d-converts-image-to-3d-model/attempt_1/3d-converts-image-to-3d-model"

pre_ir = json.loads((SCEN / "original.ui.json").read_text())
post_ir = json.loads((SCEN / "final.ui.json").read_text())

schema_provider = get_schema_provider("auto")

pre_wf = _named_import(dict(pre_ir), schema_provider=schema_provider, use_comfy_converter=False)
post_wf = _named_import(dict(post_ir), schema_provider=schema_provider, use_comfy_converter=False)

ops = parse_edit_delta([{"op": "set_node_field", "target": ["", "28", "Polygon_count"], "value": "500K-Triangle"}])

# What does widget_index_for_field return for pre node 28?
node28 = pre_wf.nodes["28"]
print("widget_index_for_field(Polygon_count) =", widget_index_for_field(node28, "Polygon_count", schema_provider=schema_provider))
print("widget_index_for_field(Seed) =", widget_index_for_field(node28, "Seed", schema_provider=schema_provider))

result = interpret(pre_wf, ops, schema_provider=schema_provider)
print("interpret ok:", result.ok)
print("result node 28 widgets:", dict(getattr(result.workflow.nodes["28"], "widgets", {}) or {}))
print("result node 28 inputs:", dict(getattr(result.workflow.nodes["28"], "inputs", {}) or {}))
print("post node 28 widgets:", dict(getattr(post_wf.nodes["28"], "widgets", {}) or {}))
print("post node 28 inputs:", dict(getattr(post_wf.nodes["28"], "inputs", {}) or {}))
