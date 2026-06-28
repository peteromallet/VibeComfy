"""Internal implementation package for agent-edit pipeline stages and helpers.

This package holds the decomposed modules extracted from
``vibecomfy.comfy_nodes.agent.edit``.  The public import path remains
``vibecomfy.comfy_nodes.agent.edit`` (the ``edit.py`` facade module),
which re-exports public symbols and threads facade-owned mutable state
into the internal implementation.

Leaf modules in this package must not import the public
``vibecomfy.comfy_nodes.agent.edit`` facade.  Mutable facade-owned
values (in particular ``_SESSION_ROOT``) are threaded through explicit
parameters rather than copied into internal module state.
"""
