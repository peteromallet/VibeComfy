import json
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/vc-twostep")

from vibecomfy.schema import get_schema_provider
from vibecomfy.executor.two_step_session import _apply_delta_ops

SCEN = Path("/private/tmp/vc-twostep/out/agentic/one-step-30-r8/attempts/3d-converts-image-to-3d-model/attempt_1/3d-converts-image-to-3d-model")
SESS = Path("/private/tmp/vc-twostep/out/editor_sessions/two-step-f74bd608a9b73bdaed8bb25a")

base = json.loads((SESS / "two_step_base_graph.json").read_text())
post = json.loads((SCEN / "final.ui.json").read_text())
sidecar = json.loads((SESS / "two_step_workflow.json").read_text())

ops = [{"op": "set_node_field", "target": ["", "28", "Polygon_count"], "value": "500K-Triangle"}]

schema_provider = get_schema_provider("auto")

replayed = _apply_delta_ops(base, ops, schema_provider=schema_provider)
print("=== emit-door replay == post? ", replayed == post)
print("=== emit-door replay == sidecar? ", replayed == sidecar)
print("=== post == sidecar? ", post == sidecar)

if replayed != post:
    print("\n--- replayed ---")
    print(json.dumps(replayed, indent=2, sort_keys=True))
    print("\n--- post ---")
    print(json.dumps(post, indent=2, sort_keys=True))

# Also check: does replay without schema provider work?
replayed_noschema = _apply_delta_ops(base, ops, schema_provider=None)
print("\n=== emit-door replay (no schema) == post? ", replayed_noschema == post)
