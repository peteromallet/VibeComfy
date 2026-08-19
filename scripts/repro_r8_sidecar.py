import json
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/vc-twostep")

from vibecomfy.schema import get_schema_provider
from vibecomfy.executor.two_step_session import _apply_delta_ops

ROOT = Path("/private/tmp/vc-twostep")
SESSION_ROOT = ROOT / "out/editor_sessions"

scenarios = [
    "3d-converts-image-to-3d-model",
    "3d-generates-a-3d-mesh-from",
    "audio-tts-narration-using-indextts-2",
    "image-animatediff-video-generation-with-vae-d20410",
    "image-image-editing-with-qwen-image",
    "image-style-transfer-using-ip-adapter",
    "image-two-stage-qwen-image-generation",
    "multi-3d-preview-and-image-output-workflow-d93baf",
    "multi-image-to-video-generation-with",
]

schema_provider = get_schema_provider("auto")

for scen in scenarios:
    d = ROOT / "out/agentic/one-step-30-r8/attempts" / scen / "attempt_1" / scen
    resp = json.loads((d / "response.json").read_text())
    session_id = resp.get("session_id")
    sess = SESSION_ROOT / session_id
    base = json.loads((sess / "two_step_base_graph.json").read_text())
    final = json.loads((d / "final.ui.json").read_text())
    sidecar = json.loads((sess / "two_step_workflow.json").read_text())
    ops = [item["op"] for item in (resp.get("accepted_batch") or []) if isinstance(item, dict) and isinstance(item.get("op"), dict)]

    replayed = _apply_delta_ops(base, ops, schema_provider=schema_provider)
    print(f"{scen}: sidecar==final={sidecar==final}  replay==final={replayed==final}  replay==sidecar={replayed==sidecar}")
