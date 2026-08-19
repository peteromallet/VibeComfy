import json
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/vc-twostep")

from vibecomfy.executor.two_step_session import _apply_delta_ops
from vibecomfy.executor.two_step import _two_step_schema_provider

ROOT = Path("/private/tmp/vc-twostep")
SESSION_ROOT = ROOT / "out/editor_sessions"

scenarios = [
    "audio-tts-narration-using-indextts-2",
    "image-animatediff-video-generation-with-vae-d20410",
    "image-two-stage-qwen-image-generation",
    "multi-image-to-video-generation-with",
]

composite = _two_step_schema_provider()

for scen in scenarios:
    d = ROOT / "out/agentic/one-step-30-r8/attempts" / scen / "attempt_1" / scen
    resp = json.loads((d / "response.json").read_text())
    session_id = resp.get("session_id")
    sess = SESSION_ROOT / session_id
    base = json.loads((sess / "two_step_base_graph.json").read_text())
    final = json.loads((d / "final.ui.json").read_text())
    ops = [item["op"] for item in (resp.get("accepted_batch") or []) if isinstance(item, dict) and isinstance(item.get("op"), dict)]
    replayed = _apply_delta_ops(base, ops, schema_provider=composite)
    print(f"{scen}: replay(composite)==final: {replayed == final}")
