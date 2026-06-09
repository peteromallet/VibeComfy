from __future__ import annotations

def test_workflow_uses_ir_neutral_helper_module() -> None:
    import vibecomfy.workflow as workflow

    assert workflow.workflow_helpers.__name__ == "vibecomfy._workflow_helpers"
    assert workflow.helper_resolve.__name__ == "vibecomfy._helper_resolve"
