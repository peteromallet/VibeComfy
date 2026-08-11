"""Scaffold for the ORACLE-7 session decomposition (T-043, SPINE).

T-044 will move the ``_artifact_store`` extraction ranges out of
``vibecomfy.comfy_nodes.agent.session`` (transaction artifact storage:
transaction dirs, lifecycle logs, derived receipts, and index recovery) into
this module.  When filled, this module's ``__all__`` must list exactly the name
set its ranges contribute to the session namespace so ``session``'s
``from ._artifact_store import *`` façade reproduces the identical top-level
attributes — the same contract ``edit`` uses for its ``_frag_*`` fragments.

Currently empty by design: the pinned session surface (S5, frozen manifest
23/31/23) is still defined directly in ``session``, so this module contributes
no names yet and imports cleanly as a no-op.
"""
