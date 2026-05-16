"""Test for example 1."""
from vibecomfy.testing import assert_compiles_cleanly, assert_node_present
from docs.testing_user_code_examples.example_01 import build as build_01  # noqa: E402


def test_compiles():
    wf = build_01()
    assert_compiles_cleanly(wf)
    assert_node_present(wf, "SaveImage", count=1)
