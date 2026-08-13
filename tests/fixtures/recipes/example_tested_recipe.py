"""A canonical tested recipe fixture for `vibecomfy test verify`.

Build a tiny synthetic VibeWorkflow that doesn't depend on heavy models, so
the snapshot baseline stays stable across environments.
"""
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def build():
    wf = VibeWorkflow(id="example-tested-recipe", source=WorkflowSource(id="example-tested-recipe"))
    wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "noop.safetensors"})
    wf.nodes["2"] = VibeNode(
        id="2",
        class_type="SaveImage",
        inputs={"filename_prefix": "out/example_tested"},
    )
    wf.edges.append(VibeEdge(from_node="1", from_output=0, to_node="2", to_input="images"))
    return wf
