# REWORK — registry fallback: 3 remaining gated classes unresolvable

Follow-up to your registry-fallback commit (7a362ec2, check-in PASS). Three classes still fail resolve on the box:

1. `llama_cpp_instruct_adv` / `llama_cpp_model_loader` / `llama_cpp_parameters` — your fallback maps them to `stavsap/ComfyUI-llama-cpp`, but that repo is **404 Not Found** (verified: `git ls-remote` fails). Find the REAL repo carrying these exact class names (search GitHub, ComfyUI-Manager's node database JSON at https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/node_db/new/ , custom_node_refs.py, or the workflow corpus in tests/live_agentic_harness/external_workflows/corpus/5b54bf476f4234aa.json which uses them). Add the correct URL to PACK_URL_FALLBACKS. If the pack is genuinely gone upstream, record that in the failure string — do not fake it.
2. `ACN_AdvancedControlNetApply` — your fallback captured comfyui-advanced-controlnet via AST but only got `ControlNetLoaderWithLoraAdvanced` (1 class). The ACN class lives in a different module of https://github.com/Suzie1/ComfyUI-Advanced-ControlNet (likely `advanced/model_controlnet.py` or nodes.py). The static AST run only parsed one file. Fix: either extend the extraction to walk all .py files in the cloned pack for that class, or switch that pack to rung 2 import. Acceptance: ensure produces ACN_AdvancedControlNetApply with on_demand_* provenance.
3. `easy int` — Easy-Use import captured 140 classes (forLoop* present) but no `easy int`. Check the actual Easy-Use source in the sandbox clone (~/.cache/vibecomfy/schema-sandbox/) for `easy int` / `"easy int"` NODE_CLASS_MAPPINGS key. If absent in current master, find which version/commit has it (git log / tags) and pin that version for this pack in the fallback map; if renamed, record the rename as a failure note (do not fake).

## ACCEPTANCE
- Box rerun: `vibecomfy schemas ensure --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json` exits 0 with EMPTY still-missing list (or names only genuinely-dead classes with evidence).
- Focused tests still green; no ComfyUI serve; ephemeral only.
- Commit: "schemas-ensure: fallback rework — correct llama-cpp repo, full-pack ACN extraction, easy int version pin".

## RULES
- Same compose-map mechanisms; no rubric edits; no docs/plans/**; report verbatim.
