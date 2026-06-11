"""Round-trip fidelity falsification spike (the harness behind docs/roadmap_agentic_comfyui.md §11.5).

Reproduces, against ComfyUI's OWN converter (the independent oracle), the four measurements that
de-risked the IR-canonical "Python -> JSON, made non-fragile" bet:

  T1  preserve-replay round-trip is LOSSLESS on untouched content, incl. subgraph bodies
  T2  editing an EXISTING node (preserve-replay + widget patch) lands EXACTLY the intended change
  T3  the created-node codec is BROKEN today (emit drops the control_after_generate slot ->
      6-element widgets_values -> oracle reads it shifted) and the FIX (emit the injection-aware
      7-element form) is verified
  T4  the "never silently corrupt" spine: an oracle-diff detector ALLOWs a clean edit and
      REFUSEs a corrupting one

This is exploratory/spike code, not production. It is the seed of the oracle-gated property test
the plan calls for (roadmap §11.3 / Phase 0). Run from the repo root:

    PYENV_VERSION=3.11.11 python scripts/roundtrip_fidelity_spike.py

Requires the vendored vendor/ComfyUI submodule initialized and a running ComfyUI on :8188 for
object_info (or adapt _object_info()). NOTE: works around the pyproject `comfy_nodes` packaging
bug (it is registered as a comfyui.custom_nodes *package* but is a module) via a __path__ shim;
fix that bug for real so this shim is unnecessary.
"""
from __future__ import annotations
import copy, glob, importlib, json, urllib.request

ENV_KEYS = ("id", "revision", "last_node_id", "last_link_id", "groups", "config", "extra", "version", "definitions")


def _boot_oracle():
    """Bootstrap ComfyUI's own UI->API converter as the independent oracle."""
    try:  # work around the pyproject comfy_nodes packaging bug during the catalog walk
        importlib.import_module("vibecomfy.comfy_nodes").__path__ = []
    except Exception:
        pass
    from vibecomfy import comfy_backend as cb
    assert cb.ensure_nodes(), "vendored vendor/ComfyUI not initialized"
    from comfy.component_model.workflow_convert import convert_ui_to_api

    def oracle(ui):
        r = convert_ui_to_api(copy.deepcopy(ui))
        return r[0] if isinstance(r, tuple) else r

    return oracle


def _object_info(class_type):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:8188/api/object_info/{class_type}", timeout=30))[class_type]["input"]


def _widget_layout(class_type):
    """Widget names in editor order, INCLUDING ComfyUI's frontend-injected control widgets.

    object_info alone is insufficient: control_after_generate is a *flag* on (e.g.) the seed
    spec, not an input, so the editor injects an extra widget after it. ~19% of classes (141/742)
    carry such a flag, so any codec for created nodes must replicate this injection.
    """
    req = _object_info(class_type).get("required", {})
    def is_w(s):
        t = s[0] if isinstance(s, list) and s else s
        return isinstance(t, list) or t in ("INT", "FLOAT", "STRING", "BOOLEAN")
    names = [n for n, s in req.items() if is_w(s)]
    for n, s in list(req.items()):
        if isinstance(s, list) and len(s) > 1 and isinstance(s[1], dict) and s[1].get("control_after_generate"):
            if n in names:
                names.insert(names.index(n) + 1, "control_after_generate")
            break
    return names


def capture(ui):
    """Envelope-aware verbatim capture: per-node raw + the envelope (definitions/groups/...)."""
    return {"env": {k: ui[k] for k in ENV_KEYS if k in ui},
            "nodes": [copy.deepcopy(n) for n in ui.get("nodes", [])],
            "links": ui.get("links", [])}


def replay(cap):
    ui = copy.deepcopy(cap["env"]); ui["nodes"] = copy.deepcopy(cap["nodes"]); ui["links"] = copy.deepcopy(cap["links"])
    return ui


def _find(key):
    for p in glob.glob("workflow_corpus/**/*.json", recursive=True):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if key in p and isinstance(d, dict) and isinstance(d.get("nodes"), list):
            return p
    return None


def main():
    oracle = _boot_oracle()
    results = {}

    # T1: preserve-replay round-trip lossless vs the oracle (incl. subgraph bodies)
    t1 = {}
    for key in ("z_image", "qwen_image_edit", "wan_t2v", "ltx2_3_single"):
        p = _find(key)
        if not p:
            continue
        ui = json.load(open(p)); rp = replay(capture(ui))
        t1[key] = oracle(ui) == oracle(rp)
    results["T1_replay_lossless_oracle"] = t1
    print("T1 preserve-replay lossless (oracle):", t1)

    # T2: edit an existing KSampler.steps, preserve-replay the rest, expect exactly one diff
    p = _find("wan_t2v"); orig = json.load(open(p))
    ksid = next(str(n["id"]) for n in orig["nodes"] if n["type"] == "KSampler")
    idx = _widget_layout("KSampler").index("steps")
    edited = copy.deepcopy(orig)
    kn = next(n for n in edited["nodes"] if str(n["id"]) == ksid)
    old = kn["widgets_values"][idx]; kn["widgets_values"][idx] = 25
    a, b = oracle(orig), oracle(edited)
    diffs = {nid: {k for k in set(a[nid]["inputs"]) | set(b[nid]["inputs"]) if a[nid]["inputs"].get(k) != b[nid]["inputs"].get(k)}
             for nid in a if nid in b and a[nid]["inputs"] != b[nid]["inputs"]}
    results["T2_existing_edit_exact"] = (diffs == {ksid: {"steps"}})
    print("T2 existing-node edit exact:", results["T2_existing_edit_exact"], diffs)

    # T3: created node -- broken 6-el codec vs the injection-aware 7-el fix
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource
    from vibecomfy.porting.emit.ui import emit_ui_json
    from vibecomfy.schema import get_schema_provider
    wf = VibeWorkflow(id="t3", source=WorkflowSource(id="t3", path=None, source_type="api"))
    wf.node("KSampler", seed=999, steps=30, cfg=4.5, sampler_name="dpmpp_2m", scheduler="karras", denoise=0.7)
    wf.finalize_metadata()
    ui = emit_ui_json(wf, schema_provider=get_schema_provider("auto"))
    ksn = next(n for n in ui["nodes"] if n["type"] == "KSampler"); wv = ksn["widgets_values"]
    want = {"seed": 999, "steps": 30, "cfg": 4.5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.7}
    broken = {k: next(v for v in oracle(ui).values() if v.get("class_type") == "KSampler")["inputs"].get(k) for k in want}
    inj = _widget_layout("KSampler").index("control_after_generate")
    ksn["widgets_values"] = wv[:inj] + ["randomize"] + wv[inj:]  # the fix
    fixed = {k: next(v for v in oracle(ui).values() if v.get("class_type") == "KSampler")["inputs"].get(k) for k in want}
    results["T3_created_broken"] = (broken != want)
    results["T3_created_fix_works"] = (fixed == want)
    print("T3 created-node broken:", broken != want, "| fix works:", fixed == want)

    # T4: corruption-detector (the 'never silently corrupt' spine)
    def detect(orig_ui, edited_ui, intended):
        a, b = oracle(orig_ui), oracle(edited_ui)
        changed = {(nid, k) for nid in a if nid in b
                   for k in set(a[nid]["inputs"]) | set(b[nid]["inputs"]) if a[nid]["inputs"].get(k) != b[nid]["inputs"].get(k)}
        return "ALLOW" if not (changed - intended) else "REFUSE"
    good = copy.deepcopy(orig); next(n for n in good["nodes"] if str(n["id"]) == ksid)["widgets_values"][idx] = 25
    bad = copy.deepcopy(orig); kn = next(n for n in bad["nodes"] if str(n["id"]) == ksid)
    kn["widgets_values"] = kn["widgets_values"][:1] + kn["widgets_values"][2:]  # drop control slot -> shift corruption
    v_good = detect(orig, good, {(ksid, "steps")}); v_bad = detect(orig, bad, {(ksid, "steps")})
    results["T4_detector"] = (v_good == "ALLOW" and v_bad == "REFUSE")
    print("T4 corruption-detector ALLOW clean / REFUSE corrupt:", results["T4_detector"], f"(good={v_good} bad={v_bad})")

    print("\nALL PASS:", all(v is True for k, v in results.items() if k != "T1_replay_lossless_oracle")
          and all(t1.values()))
    return results


if __name__ == "__main__":
    main()
