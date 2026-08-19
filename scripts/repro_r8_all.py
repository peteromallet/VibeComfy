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
    if not d.is_dir():
        print(f"### {scen}: MISSING DIR")
        continue
    resp_path = d / "response.json"
    final_path = d / "final.ui.json"
    orig_path = d / "original.ui.json"
    resp = json.loads(resp_path.read_text())
    session_id = resp.get("session_id")
    sess = SESSION_ROOT / session_id if session_id else None
    base_path = sess / "two_step_base_graph.json" if sess else None
    base = json.loads(base_path.read_text()) if base_path and base_path.is_file() else None
    post = json.loads(final_path.read_text()) if final_path.is_file() else None

    # extract ops from accepted_batch
    ops = []
    ab = resp.get("accepted_batch") or []
    for item in ab:
        if isinstance(item, dict) and isinstance(item.get("op"), dict):
            ops.append(item["op"])

    # emit-door replay
    if base is not None and post is not None:
        replayed = _apply_delta_ops(base, ops, schema_provider=schema_provider)
        eq = (replayed == post)
    else:
        replayed = None
        eq = None

    # judge-style replay
    from vibecomfy.ingest.normalize import _assert_nonempty_ingest_preserved, _named_import
    from vibecomfy.porting.edit._diff import diff
    from vibecomfy.porting.edit._interpret import interpret
    from vibecomfy.porting.edit.ops import parse_edit_delta

    judge_leftover = None
    judge_ok = None
    if orig_path.is_file() and final_path.is_file() and ops:
        pre_ir = json.loads(orig_path.read_text())
        post_ir = json.loads(final_path.read_text())
        try:
            pre_wf = _named_import(dict(pre_ir), schema_provider=schema_provider, use_comfy_converter=False)
            _assert_nonempty_ingest_preserved(dict(pre_ir), pre_wf)
            post_wf = _named_import(dict(post_ir), schema_provider=schema_provider, use_comfy_converter=False)
            _assert_nonempty_ingest_preserved(dict(post_ir), post_wf)
            parsed = parse_edit_delta(list(ops))
            result = interpret(pre_wf, parsed, schema_provider=schema_provider)
            judge_ok = result.ok
            leftover = diff(result.workflow, post_wf, schema_provider=schema_provider)
            judge_leftover = len(leftover)
        except Exception as exc:
            judge_leftover = f"EXC {exc}"

    print(f"### {scen}")
    print(f"    session={session_id}")
    print(f"    ops={len(ops)} kinds={[o.get('op') for o in ops]}")
    print(f"    emit-door replay==post: {eq}")
    print(f"    judge interpret ok={judge_ok} leftover={judge_leftover}")
