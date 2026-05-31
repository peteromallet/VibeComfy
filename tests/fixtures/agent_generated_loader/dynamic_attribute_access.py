from vibecomfy.workflow import VibeWorkflow

getattr(VibeWorkflow, "node")


def build():
    raise AssertionError("build must not run")
