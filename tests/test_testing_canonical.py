from __future__ import annotations

from vibecomfy.testing.canonical import canonical_equal, canonical_form


def test_canonical_form_treats_id_renumbered_graphs_as_equal() -> None:
    left = {
        "10": {"class_type": "Constant", "inputs": {"value": 1}},
        "20": {"class_type": "SaveImage", "inputs": {"images": ["10", 0]}},
    }
    right = {
        "a": {"class_type": "Constant", "inputs": {"value": 1}},
        "b": {"class_type": "SaveImage", "inputs": {"images": ["a", 0]}},
    }

    assert canonical_equal(left, right)
    assert canonical_form(left) == canonical_form(left)


def test_canonical_form_ignores_comfy_meta_annotations() -> None:
    left = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
            "_meta": {"title": "CheckpointLoaderSimple"},
        }
    }
    right = {
        "loader": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        }
    }

    assert canonical_equal(left, right)


def test_parallel_vaedecode_nodes_are_distinguished_by_downstream_consumers() -> None:
    left = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "a"}},
        "5": {"class_type": "PreviewImage", "inputs": {"images": ["3", 0]}},
    }
    swapped_consumers = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": "a"}},
        "5": {"class_type": "PreviewImage", "inputs": {"images": ["2", 0]}},
    }
    wrong = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "a"}},
        "5": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": "b"}},
    }

    assert canonical_equal(left, swapped_consumers)
    assert not canonical_equal(left, wrong)


def test_symmetric_interchangeable_branches_preserve_multiplicity() -> None:
    left = {
        "1": {"class_type": "Constant", "inputs": {"value": 1}},
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
        "4": {"class_type": "PreviewImage", "inputs": {"images": ["2", 0]}},
        "5": {"class_type": "PreviewImage", "inputs": {"images": ["3", 0]}},
    }
    renumbered = {
        "root": {"class_type": "Constant", "inputs": {"value": 1}},
        "decode_b": {"class_type": "VAEDecode", "inputs": {"samples": ["root", 0]}},
        "preview_b": {"class_type": "PreviewImage", "inputs": {"images": ["decode_b", 0]}},
        "decode_a": {"class_type": "VAEDecode", "inputs": {"samples": ["root", 0]}},
        "preview_a": {"class_type": "PreviewImage", "inputs": {"images": ["decode_a", 0]}},
    }

    assert canonical_equal(left, renumbered)
