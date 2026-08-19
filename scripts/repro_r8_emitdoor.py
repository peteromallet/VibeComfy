import json
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/vc-twostep")

from vibecomfy.schema import get_schema_provider
from vibecomfy.executor.two_step_session import _apply_delta_ops

ROOT = Path("/private/tmp/vc-twostep")
SESSION_ROOT = ROOT / "out/editor_sessions"

scenarios = [
    "audio-tts-narration-using-indextts-2",
    "image-animatediff-video-generation-with-vae-d20410",
    "image-two-stage-qwen-image-generation",
    "multi-image-to-video-generation-with",
]

schema_provider = get_schema_provider("auto")

def diff_graphs(a, b, path="$"):
    out = []
    if type(a) != type(b):
        return [f"{path}: type {type(a).__name__} vs {type(b).__name__}"]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: MISSING in replayed")
            elif k not in b:
                out.append(f"{path}.{k}: MISSING in post")
            else:
                out.extend(diff_graphs(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff_graphs(x, y, f"{path}[{i}]"))
    else:
        if a != b:
            out.append(f"{path}: {a!r} vs {b!r}")
    return out

for scen in scenarios:
    d = ROOT / "out/agentic/one-step-30-r8/attempts" / scen / "attempt_1" / scen
    resp = json.loads((d / "response.json").read_text())
    session_id = resp.get("session_id")
    sess = SESSION_ROOT / session_id
    base = json.loads((sess / "two_step_base_graph.json").read_text())
    post = json.loads((d / "final.ui.json").read_text())
    ops = [item["op"] for item in (resp.get("accepted_batch") or []) if isinstance(item, dict) and isinstance(item.get("op"), dict)]

    print(f"\n{'='*70}\n### {scen}\n    session={session_id}")
    print("    ops:")
    for o in ops:
        print("      ", json.dumps(o))

    replayed = _apply_delta_ops(base, ops, schema_provider=schema_provider)
    diffs = diff_graphs(replayed, post)
    print(f"    emit-door replay==post: {replayed == post}  ({len(diffs)} diffs)")
    for line in diffs[:40]:
        print("      ", line)
