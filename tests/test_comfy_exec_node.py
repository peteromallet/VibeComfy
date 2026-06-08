from __future__ import annotations

import pytest

import vibecomfy.comfy_nodes.exec_node as exec_node_module
from vibecomfy.comfy_nodes.exec_node import (
    EXEC_SLOT_COUNT,
    ExecNodeContractError,
    VibeComfyExec,
    clone_exec_input,
    compile_source_body,
    parse_io,
    run_source_body,
    semantic_inputs_from_slots,
    validate_exec_result,
)


def test_parse_io_accepts_json_string_and_maps_semantic_inputs() -> None:
    io_spec = parse_io(
        '{"inputs":[["image","IMAGE"],["strength","FLOAT"]],"outputs":[["image","IMAGE"]]}'
    )

    values = semantic_inputs_from_slots(io_spec, {"in_0": "pixels"})

    assert io_spec["inputs"] == (("image", "IMAGE"), ("strength", "FLOAT"))
    assert io_spec["outputs"] == (("image", "IMAGE"),)
    assert values == {"image": "pixels", "strength": None}


def test_parse_io_accepts_dict_payload() -> None:
    io_spec = parse_io({"inputs": [["image", "IMAGE"]], "outputs": [["mask", "MASK"]]})

    assert io_spec == {"inputs": (("image", "IMAGE"),), "outputs": (("mask", "MASK"),)}


def test_validate_exec_result_requires_dict() -> None:
    with pytest.raises(ExecNodeContractError, match="must return a dict"):
        validate_exec_result("not-a-dict", parse_io({"outputs": [["image", "IMAGE"]]}))


def test_validate_exec_result_requires_exact_declared_output_keys() -> None:
    io_spec = parse_io({"outputs": [["image", "IMAGE"], ["mask", "MASK"]]})

    with pytest.raises(ExecNodeContractError, match="missing \\['mask'\\]"):
        validate_exec_result({"image": "pixels"}, io_spec)

    with pytest.raises(ExecNodeContractError, match="unexpected \\['extra'\\]"):
        validate_exec_result({"image": "pixels", "mask": "m", "extra": 1}, io_spec)

    assert validate_exec_result({"image": "pixels", "mask": "m"}, io_spec) == (
        "pixels",
        "m",
    ) + tuple([None] * (EXEC_SLOT_COUNT - 2))


def test_clone_exec_input_recursively_copies_nested_python_containers() -> None:
    original = {"latent": {"samples": [1, 2]}, "items": [{"value": 3}]}

    cloned = clone_exec_input(original)
    cloned["latent"]["samples"].append(4)
    cloned["items"][0]["value"] = 9

    assert original == {"latent": {"samples": [1, 2]}, "items": [{"value": 3}]}


@pytest.mark.skipif(exec_node_module.torch is None, reason="torch not installed")
def test_clone_exec_input_clones_torch_tensor_and_mask() -> None:
    tensor = exec_node_module.torch.tensor([[1.0, 2.0]])
    mask = exec_node_module.torch.tensor([[0.25, 0.5]])

    cloned_tensor = clone_exec_input(tensor)
    cloned_mask = clone_exec_input(mask)
    cloned_tensor[0, 0] = 9.0
    cloned_mask[0, 1] = 0.0

    assert float(tensor[0, 0]) == 1.0
    assert float(mask[0, 1]) == 0.5


@pytest.mark.skipif(exec_node_module.torch is None, reason="torch not installed")
def test_clone_exec_input_clones_latent_samples_tensor() -> None:
    latent = {"samples": exec_node_module.torch.tensor([[1.0, 2.0]])}

    cloned = clone_exec_input(latent)
    cloned["samples"][0, 1] = 7.0

    assert float(latent["samples"][0, 1]) == 2.0


def test_run_source_body_reports_body_line_numbers() -> None:
    runner = compile_source_body(
        "\nvalue = amount + 1\nraise ValueError('boom')\n",
        ["amount"],
        filename="<exec-test>",
    )

    with pytest.raises(RuntimeError, match=r"<exec-test>:2: boom"):
        run_source_body(runner, {"amount": 4})


def test_compile_source_body_rejects_invalid_python_input_names() -> None:
    with pytest.raises(ExecNodeContractError, match="not a valid Python identifier"):
        compile_source_body("return {}", ["not-valid"])


def test_exec_node_help_and_examples_warn_about_unsandboxed_execution() -> None:
    assert "no sandbox" in VibeComfyExec.HELP.lower()
    assert "freeze or kill" in VibeComfyExec.HELP.lower()
    assert set(VibeComfyExec.EXAMPLES) == {
        "brightness_contrast",
        "pil_resize",
        "mask_from_luminance",
        "debug_shape_passthrough",
    }
    assert "return {\"image\": image}" in VibeComfyExec.EXAMPLES["debug_shape_passthrough"]["source"]
