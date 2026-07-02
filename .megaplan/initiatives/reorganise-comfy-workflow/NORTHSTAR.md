# North Star: Reorganise Comfy Workflow

Ship a layout-only ComfyUI workflow reorganisation capability that makes messy workflows readable, grouped, named, colored, and left-to-right without changing runtime behavior.

The system must preserve the lossless LiteGraph graph as source of truth, expose intuitive Pythonic workflow projections plus explicit graph facts to agents, accept only strict semantic `LayoutPlan v1` output, and compile final node/group coordinates deterministically.

The first release is conservative: explicit `/reorganise_comfy_workflow` and CLI preview/apply surfaces first, main-flow integration as suggestion-only until golden fixtures prove stable visual quality and idempotence.
