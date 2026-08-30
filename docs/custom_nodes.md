# Custom Nodes

Pinned custom-node packs:

```text
ComfyUI-KJNodes b7646ad70a7daa7aeb919ca542274758d26ba2df https://github.com/kijai/ComfyUI-KJNodes.git
ComfyUI-QwenTTS d8122a8ba835b65fd65c113d2b273b1ad1579293 https://github.com/1038lab/ComfyUI-QwenTTS.git
ComfyUI-WanVideoWrapper df8f3e49daaad117cf3090cc916c83f3d001494c https://github.com/kijai/ComfyUI-WanVideoWrapper.git
```

The lockfile is `custom_nodes.lock`.

For custom-node packs, the enforced identity is the git URL plus immutable
commit SHA. An entry's `pip_packages` is an unversioned inventory hint used by
local catalog install, doctor, and ready-template metadata; it is not a pip
lock and is not folded into `uv.lock`. RunPod provisioning continues to clone
the pinned pack and install its `requirements.txt`, plus the hard-coded
`NODE_PACK_COMPAT_DEPS` compatibility additions.

ComfyUI-QwenTTS is required by `ready_templates/video/ltx2_3_runexx_talking_avatar_qwen_tts.py`. The lockfile entry pins upstream HEAD at lock time. Run `vibecomfy nodes install ComfyUI-QwenTTS` to install locally; the verb will UPSERT the lockfile to your installed SHA.

The opt-in P1 GPU smoke test is documented in [RunPod P1 Smoke Test](runpod/smoke.md). It provisions a real RunPod pod, so run it only with `pytest --runpod -m runpod tests/smoke/test_p1_runpod.py`.

## Resolution Policy

Custom-node handling is now a catalog-backed workflow, not just a doc note.

- `vibecomfy doctor <workflow-or-scratchpad>` reports unknown classes and suggests known packs.
- `vibecomfy nodes install-plan <workflow-or-scratchpad>` prints the custom-node repos and pip packages needed for a workflow.
- Ready templates declare `READY_REQUIREMENTS["custom_nodes"]`; `python -m tools.refresh_template_index` exposes that static evidence to downstream tooling.
- `scripts/runpod_matrix_remote.py` carries compatibility patches for known stale workflow class names, such as older Video-Depth-Anything nodes that now map to Kijai's `DepthAnything_V2` pack.

The current catalog includes WanVideoWrapper, LTXVideo, KJNodes, VideoHelperSuite, ControlNet Aux, DepthAnythingV2, GGUF, DarioFT Qwen3-TTS, and 1038lab QwenTTS. New workflow failures should generally become catalog entries or compatibility patches, not one-off matrix hacks.

VibeComfy scans these folders for workflow examples:

```text
example_workflows/
workflow/
workflows/
example/
examples/
```

Current local inventory:

- Official templates: 23
- External workflows/examples: 51
- Runtime node definitions from Comfy: 1,202

Known warnings during local and RunPod runtime loading:

- `sageattention` is not installed, so WanVideoWrapper loads without that acceleration path.
- `onnx` is not installed, so FantasyPortrait nodes are not available.

These warnings do not block the current smoke workflows, but workflows requiring those optional nodes should report a concrete missing dependency before being treated as runnable.
