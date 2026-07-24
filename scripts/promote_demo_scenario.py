#!/usr/bin/env python3
"""Promote a proven demo-scenario case into the picker manifest.

For each case:
  - materialize original.ui.json (== broken.ui.json provenance) and
    candidate.ui.json (== response.candidate_graph) into the run_dir if absent
    (most creative-pipeline cases never wrote the snapshot files, but the data
    is fully present in response.json);
  - append a manifest entry matching the existing shape to
    demo_scenarios.json (idempotent: updates if id already present).

Does NOT touch the bundle gz. Run scripts/build_demo_scenario_assets.py after.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Overridable so additive (or other campaign) cases written outside the canonical
# demo-candidate-factory dir can be promoted without editing this script.
CASES_ROOT = Path(
    os.environ.get("VIBECOMFY_PROMOTE_CASES_ROOT")
    or str(ROOT / "out" / "demo-candidate-factory" / "20260723-001" / "cases")
)
MANIFEST = ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "demo_scenarios.json"


def _find_response(case_dir: Path) -> tuple[str, Path]:
    """Return (attempt_label, response_path) for the latest attempt."""
    atts = sorted(
        [d.name for d in (case_dir / "attempts").iterdir() if d.is_dir() and d.name.isdigit()],
        key=int,
    )
    if not atts:
        raise RuntimeError(f"{case_dir.name}: no attempts/")
    last = atts[-1]
    for cand in [
        case_dir / "attempts" / last / "response.json",
        case_dir / "attempts" / last / "attempts" / last / "response.json",
    ]:
        if cand.exists():
            return last, cand
    raise RuntimeError(f"{case_dir.name}: response.json not found for attempt {last}")


def _materialize_snapshots(case_dir: Path, attempt: str, resp_path: Path) -> Path:
    """Ensure run_dir has original.ui.json, candidate.ui.json, response.json."""
    run_dir = case_dir / "attempts" / attempt
    broken = json.loads((case_dir / "broken" / "broken.ui.json").read_text(encoding="utf-8"))
    resp = json.loads(resp_path.read_text(encoding="utf-8"))

    candidate = resp.get("candidate_graph")
    if not isinstance(candidate, dict) or not candidate.get("nodes"):
        candidate = resp.get("evidence", {}).get("implementation", {}).get("graph")
    if not isinstance(candidate, dict) or not candidate.get("nodes"):
        raise RuntimeError(f"{case_dir.name}: no candidate_graph in response")

    orig_path = run_dir / "original.ui.json"
    cand_path = run_dir / "candidate.ui.json"
    resp_copy = run_dir / "response.json"

    if not orig_path.exists():
        orig_path.write_text(json.dumps(broken, ensure_ascii=False, indent=2), encoding="utf-8")
    if not cand_path.exists():
        cand_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    # Always refresh response.json copy so the bundle's projected fields are current.
    resp_copy.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def _node_packs(graph: dict) -> list[str]:
    """Infer required node packs from node type prefixes (comfy-core excluded)."""
    # Common comfy-core prefixes that do NOT require a custom pack.
    core = {
        "KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced",
        "CFGGuider", "KSamplerSelect", "RandomNoise", "RandomNoiseGenerator",
        "CLIPTextEncode", "CLIPLoader", "DualCLIPLoader", "UNETLoader",
        "CheckpointLoaderSimple", "VAEDecode", "VAEEncode", "VAELoader",
        "SaveImage", "SaveVideo", "SaveAudio", "SaveAudioMP3", "PreviewImage",
        "LoadImage", "LoadAudio", "LoadCheckpoint", "LoadVAE",
        "EmptyLatentImage", "EmptySD3LatentImage", "EmptyHunyuanLatentVideo",
        "EmptyFlux2LatentImage", "EmptyLTXVLatentVideo", "EmptyAceStep1.5LatentAudio",
        "ModelSamplingSD3", "ModelSamplingAuraFlow", "ModelSamplingDiscrete",
        "ModelSamplingFlux", "CreateVideo", "CreateAudio", "GetImageSize",
        "ImageScale", "ImageScaleBy", "ImageScaleToTotalPixels", "ImageConcatMulti",
        "ImageGridComposite2x2", "ConditioningZeroOut", "Flux2Scheduler",
        "LoraLoader", "LoraLoaderModelOnly", "LTXFloatToInt", "PrimitiveNode",
        "Reroute", "Note", "LatentBlend", "LatentComposite", "ImageComposite",
    }
    packs: set[str] = set()
    for n in graph.get("nodes", []):
        t = (n.get("type") or "").strip()
        if not t or t in core:
            continue
        # Custom node packs typically carry a recognizable prefix before a dot/underscore.
        # ComfyUI-Easy-Use nodes are the most common in this campaign (ComfySwitchNode etc.)
        if t.startswith("Comfy"):
            packs.add("ComfyUI-Easy-Use")
        elif t.startswith("LTX"):
            packs.add("ComfyUI-LTXVideoWrapper")
        elif t.startswith("AILab_Qwen3"):
            packs.add("ComfyUI-Qwen3")
        elif t.startswith("HyVideo") or t.startswith("Hunyuan"):
            packs.add("ComfyUI-HunyuanVideoWrapper")
        else:
            # Fallback: keep the type itself as a hint pack marker.
            packs.add(t)
    return sorted(packs) or ["ComfyUI-Easy-Use"]


def _category(graph: dict, fault_family: str) -> str:
    types = {(n.get("type") or "") for n in graph.get("nodes", [])}
    joined = " ".join(types).lower()
    ff = (fault_family or "").lower()
    if any(k in joined for k in ["savevideo", "createvideo", "emptyhunyuan", "emptyltxv", "hyvideo", "ltx"]):
        return "video"
    if any(k in joined for k in ["saveaudio", "qwen3tts", "acestep", "saveaudiomp3"]):
        return "audio / TTS" if "tts" in joined or "qwen3" in joined else "audio"
    if "conditioning" in ff or "swap" in ff or "polarity" in ff or "prompt" in ff:
        return "image / conditioning"
    if "noise" in ff or "seed" in ff or "randomize" in ff:
        return "image / determinism"
    return "image"


def promote(case_id: str, *, title: str, query: str, description: str,
            category: str | None, required_node_packs: list[str] | None) -> dict:
    case_dir = CASES_ROOT / case_id
    if not case_dir.exists():
        raise RuntimeError(f"case dir not found: {case_dir}")

    status = json.loads((case_dir / "status.json").read_text(encoding="utf-8"))
    attempt, resp_path = _find_response(case_dir)
    run_dir = _materialize_snapshots(case_dir, attempt, resp_path)

    broken = json.loads((case_dir / "broken" / "broken.ui.json").read_text(encoding="utf-8"))
    resp = json.loads(resp_path.read_text(encoding="utf-8"))

    fault_family = status.get("fault_family") or ""
    cat = category or _category(broken, fault_family)
    packs = required_node_packs or _node_packs(broken)

    entry = {
        "id": case_id,
        "title": title,
        "query": query,
        "description": description,
        "category": cat,
        "required_node_packs": packs,
        "asset": f"{case_id}.json",
        "run_location": {
            "run_dir": f"cases/{case_id}/attempts/{attempt}",
            "original_ui": "original.ui.json",
            "candidate_ui": "candidate.ui.json",
            "response_json": "response.json",
        },
    }

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenarios = manifest.setdefault("scenarios", [])
    scenarios = [s for s in scenarios if s.get("id") != case_id]
    scenarios.append(entry)
    manifest["scenarios"] = scenarios
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


# Promotions to apply (id, title, query, description, category, packs)
# Inquiries/authors taken verbatim from the case status.json inquiry field.
PROMOTIONS = [
    dict(
        case_id="ed9a5be99385",
        title="Every image comes out horizontally squished",
        query="All my images are squished horizontally — people look short and fat, objects are distorted, even though I’m using a square-ish prompt. It’s like the aspect ratio is being collapsed.",
        description="Repairs a latent width/height mismatch fault in an AuraFlow/SD3 text-to-image workflow. The empty latent was created with width and height swapped, so the model samples a distorted canvas that decodes into a squished image.",
        category="image / latent",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    dict(
        case_id="8db8a2f9e772",
        title="I get a completely different video every time I queue",
        query="I’m getting a completely different video each time I run the workflow, even though I didn’t change the prompt. It’s like the seed isn’t being held constant across runs.",
        description="Repairs a seed control mode fault in a Hunyuan video-generation workflow. The sampler’s seed control was set to 'increment' instead of 'fixed', so each run advances the seed and produces a different video.",
        category="video / Hunyuan",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    dict(
        case_id="37f088b8cac9",
        title="The second image is always identical to the first",
        query="Every time I run the workflow, the second image is exactly the same, even though the first image changes. I want the second pass to vary like the first.",
        description="Repairs a hardcoded-seed fault in a Flux2 two-stage workflow. The second stage’s RandomNoise node had its control set to 'fixed', so both stages share the same noise and the refinement reproduces the first image.",
        category="image / Flux2",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    dict(
        case_id="c37839d25229",
        title="Every image is exactly the same, even after restarting",
        query="Every image I generate is exactly the same, even after restarting the workflow and hitting queue multiple times. I expected variation between runs.",
        description="Repairs a noise-randomize-locked fault in a Flux2 workflow. The RandomNoise node’s control widget was set to 'fixed' instead of 'randomize', so every run starts from identical noise and yields identical output.",
        category="image / Flux2",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    dict(
        case_id="fa48d41b426e",
        title="The generated audio is completely silent",
        query="The generated audio is completely silent – no speech at all, just a blank audio file. The workflow runs without errors but nothing comes out.",
        description="Repairs an empty TTS prompt fault in a Qwen3 voice-clone workflow. The target text widget was left blank, so the synthesizer has nothing to speak and emits silence.",
        category="audio / TTS",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    dict(
        case_id="525d2dd119c0",
        title="The result looks like the prompt guidance is flipped",
        query="Something’s off with the generation — the result comes out wrong, like the prompt guidance is flipped — the negative prompt seems to be driving the image instead of the positive. Can you fix it so the result matches what I described?",
        description="Repairs a conditioning polarity swap fault in a Flux2 workflow. The positive and negative conditioning inputs to the sampler were reversed, so the model is guided away from the intended prompt and toward the negative prompt.",
        category="image / conditioning",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    dict(
        case_id="3270acf50658",
        title="The LoRA style never shows up, and the prompt feels inverted",
        query="I loaded a style LoRA but the result doesn’t reflect it at all, and the whole image feels like it’s being pushed away from my prompt rather than toward it. The conditioning seems to be fighting the LoRA.",
        description="Repairs a conditioning polarity swap fault on a LoRA-loaded AuraFlow workflow. Positive and negative conditioning were wired to the wrong sampler inputs, so the LoRA’s style contribution is suppressed and the model inverts the prompt intent.",
        category="image / conditioning",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
    # --- ADDITIVE demos (feature removed → fixer re-adds it) ---
    dict(
        case_id="4446f9745c7c",
        title="The upscale step vanished — my images lost their detail",
        query="I had an upscale/resize step in this image workflow and it’s gone — the final image comes out lower resolution than it should, it lost the extra detail the upscale pass used to add. Can you add that step back where it belongs so the output is restored?",
        description="Additive restore: the upscaler node was removed from a basic image-upscale workflow, leaving a resolution gap. The fixer re-adds the ImageScale node and rewires it so the output regains the intended resolution (verdict: alternative_repair).",
        category="image / upscale",
        required_node_packs=["ComfyUI-Easy-Use"],
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="promote only this case id")
    args = parser.parse_args()
    for spec in PROMOTIONS:
        if args.only and spec["case_id"] != args.only:
            continue
        entry = promote(**spec)
        print(f"promoted {entry['id']}: {entry['title']}  [{entry['category']}]")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(f"\nmanifest now has {len(manifest['scenarios'])} scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
