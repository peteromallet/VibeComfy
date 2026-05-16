"""Tests for the pytest-vibecomfy plugin (T10)."""
from __future__ import annotations


def test_plugin_collects_test_workflow_file(pytester):
    pytester.makepyfile(
        test_workflow_demo="""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

def test_compiles_cleanly():
    wf = VibeWorkflow(id='plugin-demo', source=WorkflowSource(id='plugin-demo'))
    wf.nodes['1'] = VibeNode(id='1', class_type='CheckpointLoaderSimple', inputs={'ckpt_name': 'x.safetensors'})
    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'images': ['1', 0], 'filename_prefix': 'out'})
    return wf
"""
    )
    result = pytester.runpytest("-q", "--tb=short")
    result.assert_outcomes(passed=1)


def test_plain_test_functions_in_workflow_files_still_run(pytester):
    pytester.makepyfile(
        test_workflow_mixed="""
def test_just_arithmetic():
    assert 1 + 1 == 2
"""
    )
    result = pytester.runpytest("-q")
    result.assert_outcomes(passed=1)
