"""Tests for vibecomfy.testing.assertions (T5)."""
from __future__ import annotations

import pytest

from vibecomfy.testing import (
    assert_compiles_cleanly,
    assert_edge,
    assert_input_value,
    assert_node_present,
    assert_no_dangling_handles,
    assert_output_kind,
)
from vibecomfy.testing.fixtures import make_workflow_factory
from vibecomfy.workflow import VibeEdge, VibeNode


def _basic_wf():
    wf = make_workflow_factory()(id="basic")
    wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "x.safetensors"})
    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"images": ["1", 0], "filename_prefix": "out"})
    wf.edges.append(VibeEdge(from_node="1", from_output=0, to_node="2", to_input="images"))
    return wf


def test_assert_node_present_positive():
    wf = _basic_wf()
    assert_node_present(wf, "SaveImage", count=1)


def test_assert_node_present_negative_count():
    wf = _basic_wf()
    with pytest.raises(AssertionError) as exc:
        assert_node_present(wf, "SaveImage", count=2)
    assert wf.id in str(exc.value)


def test_assert_edge_positive():
    wf = _basic_wf()
    assert_edge(wf, "1", "2", to_input="images")


def test_assert_edge_negative_missing():
    wf = _basic_wf()
    with pytest.raises(AssertionError):
        assert_edge(wf, "1", "2", to_input="latent")


def test_assert_input_value_positive():
    wf = _basic_wf()
    assert_input_value(wf, "2", "filename_prefix", "out")


def test_assert_input_value_negative():
    wf = _basic_wf()
    with pytest.raises(AssertionError) as exc:
        assert_input_value(wf, "2", "filename_prefix", "other")
    assert "filename_prefix" in str(exc.value)


def test_assert_output_kind_positive():
    wf = _basic_wf()
    wf.finalize_metadata()
    assert_output_kind(wf, "SaveImage")


def test_assert_compiles_cleanly_positive():
    wf = _basic_wf()
    assert_compiles_cleanly(wf)


def test_assert_no_dangling_handles_positive():
    wf = _basic_wf()
    assert_no_dangling_handles(wf)
